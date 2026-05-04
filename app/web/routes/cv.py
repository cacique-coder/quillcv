import logging
import re
import time

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response

from app.cv_export.adapters.docx_export import generate_docx
from app.cv_export.adapters.puppeteer_pdf import generate_pdf
from app.cv_export.adapters.template_registry import REGION_RULES, get_template
from app.cv_generation.adapters.pdfplumber_parser import parse_cv
from app.cv_generation.adapters.refiner import apply_review_fixes
from app.cv_generation.use_cases.generate_cv import run_generation_pipeline
from app.infrastructure.llm.client import set_llm_context
from app.infrastructure.persistence.attempt_store import (
    get_attempt,
    get_document_bytes,
    get_document_filename,
    update_attempt,
)
from app.scoring.adapters.keyword_matcher import analyze_ats
from app.web.templates import templates

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# WebSocket endpoint — real-time progress during CV generation
# ---------------------------------------------------------------------------


@router.websocket("/ws/analyze")
async def ws_analyze(websocket: WebSocket):
    attempt_id = websocket.query_params.get("attempt_id", "")
    if not attempt_id or not get_attempt(attempt_id):
        logger.warning("WebSocket rejected — invalid attempt_id=%r", attempt_id)
        await websocket.close(code=4000, reason="Invalid attempt")
        return

    await websocket.accept()
    ws_start = time.monotonic()
    current_step: list[str] = ["(not started)"]  # mutable cell for finally block

    logger.info("WebSocket connected attempt=%s", attempt_id)

    async def send_progress(step: str, detail: str) -> None:
        current_step[0] = step
        step_elapsed = round((time.monotonic() - ws_start) * 1000)
        logger.info(
            "WebSocket progress attempt=%s step=%r detail=%r elapsed=%dms",
            attempt_id,
            step,
            detail,
            step_elapsed,
        )
        try:
            await websocket.send_json({"type": "progress", "step": step, "detail": detail})
        except (WebSocketDisconnect, RuntimeError) as err:
            raise WebSocketDisconnect() from err

    try:
        llm = websocket.app.state.llm
        llm_fast = websocket.app.state.llm_fast

        # WebSocket connections bypass BaseHTTPMiddleware, so the session
        # middleware never runs and websocket.state.session is never set.
        # Manually load the session from the cookie before resolving the user.
        from app.identity.adapters.fastapi_deps import get_current_user
        from app.infrastructure.middleware.session import _COOKIE_NAME, _load_session

        _ws_session_id = websocket.cookies.get(_COOKIE_NAME)
        _ws_session_data = (await _load_session(_ws_session_id) if _ws_session_id else None) or {}
        websocket.state.session = _ws_session_data

        ws_user = await get_current_user(websocket)
        ws_user_id = ws_user.id if ws_user else None

        result = await run_generation_pipeline(
            attempt_id,
            llm,
            llm_fast,
            on_progress=send_progress,
            user_id=ws_user_id,
            pii=_ws_session_data.get("pii") or {},
            pii_password=_ws_session_data.get("_pii_password"),
        )

        total_ms = round((time.monotonic() - ws_start) * 1000)
        result.get("quality_review") and (
            # _llm_usage lives inside cv_data; surface it for the log if present
            result.get("quality_review", {}) or {}
        )
        # Pull usage from cv_data if available (pipeline stores it there)
        attempt_data = {}
        try:
            from app.infrastructure.persistence.attempt_store import get_attempt as _get

            attempt_data = _get(attempt_id) or {}
        except Exception:
            logger.debug("Failed to retrieve attempt data for %s", attempt_id)
        cv_data = attempt_data.get("cv_data") or {}
        usage = cv_data.get("_llm_usage", {})
        if usage:
            logger.info(
                "WebSocket complete attempt=%s duration=%dms input_tokens=%s output_tokens=%s cost_usd=%s",
                attempt_id,
                total_ms,
                usage.get("input_tokens", "?"),
                usage.get("output_tokens", "?"),
                usage.get("cost_usd", "?"),
            )
        else:
            logger.info(
                "WebSocket complete attempt=%s duration=%dms",
                attempt_id,
                total_ms,
            )

        # Render the final HTML
        html = templates.get_template("partials/results.html").render(request=websocket, **result)
        await websocket.send_json({"type": "complete", "html": html})

    except WebSocketDisconnect:
        elapsed_ms = round((time.monotonic() - ws_start) * 1000)
        logger.info("WebSocket disconnected attempt=%s step=%r elapsed=%dms", attempt_id, current_step[0], elapsed_ms)
        return
    except ValueError as e:
        elapsed_ms = round((time.monotonic() - ws_start) * 1000)
        logger.warning(
            "WebSocket validation error attempt=%s step=%r elapsed=%dms error=%r",
            attempt_id,
            current_step[0],
            elapsed_ms,
            str(e),
        )
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except (WebSocketDisconnect, RuntimeError):
            pass
    except Exception:
        elapsed_ms = round((time.monotonic() - ws_start) * 1000)
        logger.exception(
            "WebSocket generation failed attempt=%s step=%r elapsed=%dms",
            attempt_id,
            current_step[0],
            elapsed_ms,
        )
        try:
            await websocket.send_json({"type": "error", "message": "Generation failed. Please try again."})
        except (WebSocketDisconnect, RuntimeError):
            pass
    finally:
        try:
            await websocket.close()
        except (WebSocketDisconnect, RuntimeError):
            pass


# ---------------------------------------------------------------------------
# HTTP fallback — kept for clients without WebSocket support
# ---------------------------------------------------------------------------


@router.post("/analyze")
async def analyze(request: Request):
    """Parse CV from attempt store, run ATS analysis, and generate tailored CV."""
    attempt_id = request.state.session.get("attempt_id")
    if not attempt_id:
        return templates.TemplateResponse(
            "partials/error.html",
            {"request": request, "error": "No active session. Please start from the beginning."},
        )

    # TODO(billing): de-dup concurrent /analyze calls per attempt before enabling credit gating
    http_user = getattr(request.state, "user", None)
    http_user_id = http_user.id if http_user else None

    try:
        result = await run_generation_pipeline(
            attempt_id,
            request.app.state.llm,
            request.app.state.llm_fast,
            user_id=http_user_id,
            pii=request.state.session.get("pii") or {},
            pii_password=request.state.session.get("_pii_password"),
        )
    except ValueError as e:
        return templates.TemplateResponse(
            "partials/error.html",
            {"request": request, "error": str(e)},
        )

    return templates.TemplateResponse(
        "partials/results.html",
        {"request": request, **result},
    )


# ---------------------------------------------------------------------------
# Apply fixes (unchanged — stays HTTP)
# ---------------------------------------------------------------------------


@router.post("/apply-fixes")
async def apply_fixes(request: Request):
    """Apply selected quality review fixes to the generated CV."""
    attempt_id = request.state.session.get("attempt_id")
    if not attempt_id:
        return templates.TemplateResponse(
            "partials/error.html",
            {"request": request, "error": "No active session."},
        )

    attempt = get_attempt(attempt_id)
    if not attempt or not attempt.get("cv_data"):
        return templates.TemplateResponse(
            "partials/error.html",
            {"request": request, "error": "No generated CV found. Please generate first."},
        )

    form = await request.form()

    cached_flags = attempt.get("quality_review_flags", [])
    selected_indices = form.getlist("selected")

    flags = []
    for idx_str in selected_indices:
        try:
            idx = int(idx_str)
            if 0 <= idx < len(cached_flags):
                flag = dict(cached_flags[idx])
                user_note = str(form.get(f"instruction_{idx}", "")).strip()
                if user_note:
                    flag["user_instruction"] = user_note
                flags.append(flag)
        except (ValueError, IndexError):
            pass

    if not flags:
        return templates.TemplateResponse(
            "partials/error.html",
            {"request": request, "error": "No fixes selected."},
        )

    cv_data = attempt["cv_data"]
    job_description = attempt.get("job_description", "")
    template_id = attempt.get("template_id", "modern")
    region_code = attempt.get("region", "US")

    llm_fast = request.app.state.llm_fast

    import uuid as _uuid_mod

    fix_user = getattr(request.state, "user", None)
    set_llm_context(
        service="apply_fixes",
        attempt_id=attempt_id,
        user_id=fix_user.id if fix_user else None,
        transaction_id=_uuid_mod.uuid4().hex,
    )

    updated_data = await apply_review_fixes(cv_data, flags, job_description, llm=llm_fast)
    if updated_data is None:
        return templates.TemplateResponse(
            "partials/error.html",
            {"request": request, "error": "Failed to apply fixes. Please try again."},
        )

    llm_usage = updated_data.pop("_llm_usage", {})
    rendered_cv = templates.get_template(f"cv_templates/{template_id}.html").render(**updated_data)
    updated_data["_llm_usage"] = llm_usage

    generated_text = re.sub(r"<style[^>]*>.*?</style>", "", rendered_cv, flags=re.DOTALL)
    generated_text = re.sub(r"<[^>]+>", " ", generated_text)
    generated_text = re.sub(r"\s+", " ", generated_text).strip()

    keyword_data = attempt.get("extracted_keywords")
    job_keywords = keyword_data["all_keywords"] if keyword_data else None
    ats_generated = analyze_ats(generated_text, job_description, keywords_override=job_keywords)

    update_attempt(attempt_id, cv_data=updated_data, rendered_cv=rendered_cv)

    selected_template = get_template(template_id) or get_template("modern")
    region_rules = REGION_RULES.get(region_code, REGION_RULES["US"])

    cv_text = attempt.get("cv_text_preview", "")
    cv_bytes = get_document_bytes(attempt_id, "cv_file")
    cv_filename = get_document_filename(attempt_id, "cv_file")
    if cv_bytes and cv_filename:
        try:
            full_cv_text = parse_cv(cv_filename, cv_bytes)
        except ValueError:
            full_cv_text = cv_text
    else:
        full_cv_text = cv_text

    ats_original = analyze_ats(full_cv_text, job_description, keywords_override=job_keywords)

    return templates.TemplateResponse(
        "partials/results.html",
        {
            "request": request,
            "ats_original": ats_original,
            "ats_generated": ats_generated,
            "generated_cv": rendered_cv,
            "cv_text": full_cv_text[:500],
            "template": selected_template,
            "region": region_code,
            "region_rules": region_rules,
            "quality_review": None,
            "fixes_applied": len(flags),
        },
    )


# ---------------------------------------------------------------------------
# PDF download (unchanged)
# ---------------------------------------------------------------------------


@router.get("/download-pdf")
async def download_pdf(request: Request):
    """Generate and download the CV as PDF."""
    attempt_id = request.state.session.get("attempt_id")
    if not attempt_id:
        return Response("No active session", status_code=400)

    attempt = get_attempt(attempt_id)
    if not attempt or not attempt.get("rendered_cv"):
        return Response("No generated CV found. Please generate your CV first.", status_code=400)

    rendered_cv = attempt["rendered_cv"]
    cv_name = attempt.get("cv_data", {}).get("name", "CV") or "CV"
    safe_name = "".join(c for c in cv_name if c.isalnum() or c in " -_").strip() or "CV"

    pdf_bytes = await generate_pdf(rendered_cv)
    if pdf_bytes is None:
        return Response("PDF generation failed. Please try again.", status_code=500)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name} - QuillCV.pdf"',
        },
    )


@router.get("/download-docx")
async def download_docx(request: Request):
    """Generate and download the CV as DOCX."""
    attempt_id = request.state.session.get("attempt_id")
    if not attempt_id:
        return Response("No active session", status_code=400)

    attempt = get_attempt(attempt_id)
    if not attempt or not attempt.get("cv_data"):
        return Response("No generated CV found. Please generate your CV first.", status_code=400)

    cv_data = attempt["cv_data"]
    region_code = attempt.get("region", "AU") or "AU"
    template_id = attempt.get("template_id", "classic") or "classic"
    cv_name = cv_data.get("name", "CV") or "CV"
    safe_name = "".join(c for c in cv_name if c.isalnum() or c in " -_").strip() or "CV"

    try:
        docx_bytes = generate_docx(cv_data, region_code=region_code, template_id=template_id)
    except Exception:
        logger.exception("DOCX generation failed for attempt=%s", attempt_id)
        return Response("DOCX generation failed. Please try again.", status_code=500)

    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name} - QuillCV.docx"',
        },
    )
