import asyncio
import logging
import re
import time
from collections.abc import Callable, Coroutine
from pathlib import Path

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates

from app.database import async_session
from app.services.ai_generator import generate_tailored_cv
from app.services.llm_client import set_llm_context
from app.services.ats_analyzer import analyze_ats
from app.services.attempt_store import get_attempt, get_document_bytes, get_document_filename, update_attempt
from app.services.cv_parser import parse_cv
from app.services.cv_refiner import apply_review_fixes
from app.services.cv_reviewer import review_cv_quality
from app.services.cv_store import save_cv
from app.services.generation_log import log_generation
from app.services.keyword_extractor import extract_keywords_llm
from app.services.docx_generator import generate_docx
from app.services.pdf_generator import generate_pdf
from app.services.pii_redactor import PIIRedactor
from app.services.placeholder_check import check_placeholders
from app.services.template_registry import REGION_RULES, get_region, get_template

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")

# Type alias for progress callback
ProgressCallback = Callable[[str, str], Coroutine]


async def _noop_progress(step: str, detail: str) -> None:
    """No-op progress callback for the HTTP endpoint."""
    pass


async def _run_generation_pipeline(
    attempt_id: str,
    llm,
    llm_fast,
    on_progress: ProgressCallback = _noop_progress,
    user_id: str | None = None,
) -> dict:
    """Shared CV generation pipeline used by both HTTP and WebSocket endpoints.

    Returns a dict with all data needed to render results, or raises an exception.
    Keys: ats_original, ats_generated, generated_cv, cv_text, template,
          region, region_rules, quality_review, timings.
    """
    import uuid as _uuid_mod

    logger.info("Pipeline[%s] START user=%s", attempt_id, user_id)

    pipeline_transaction_id = _uuid_mod.uuid4().hex
    set_llm_context(
        service="pipeline",
        attempt_id=attempt_id,
        user_id=user_id,
        transaction_id=pipeline_transaction_id,
    )

    attempt = get_attempt(attempt_id)
    if not attempt:
        logger.info("Pipeline[%s] FAIL: session expired — attempt not found", attempt_id)
        raise ValueError("Session expired. Please start again.")

    cv_bytes = get_document_bytes(attempt_id, "cv_file")
    cv_filename = get_document_filename(attempt_id, "cv_file")
    logger.info("Pipeline[%s] attempt loaded: cv_file=%s filename=%s", attempt_id, "yes" if cv_bytes else "NO", cv_filename)
    if not cv_bytes or not cv_filename:
        logger.info("Pipeline[%s] FAIL: no CV file found", attempt_id)
        raise ValueError("No CV file found. Please go back to step 3 and upload your CV.")

    timings = {}

    # 1. Parse CV
    await on_progress("Reading your CV", "Parsing document structure")
    t0 = time.monotonic()
    cv_text = parse_cv(cv_filename, cv_bytes)
    timings["parse_cv"] = round(time.monotonic() - t0, 2)
    logger.info("Pipeline[%s] step=parse_cv duration=%.2fs chars=%d", attempt_id, timings["parse_cv"], len(cv_text))

    if not cv_text.strip():
        raise ValueError("Could not extract text from the CV file.")

    # PII redaction — replace name/email/phone with tokens before sending to AI
    full_name = attempt.get("full_name", "").strip()
    redactor = PIIRedactor(full_name=full_name) if full_name else None
    if redactor:
        cv_text_for_llm = redactor.redact(cv_text)
    else:
        cv_text_for_llm = cv_text

    # Get settings
    region_code = attempt.get("region", "AU")
    template_id = attempt.get("template_id", "modern")
    job_description = attempt.get("job_description", "")

    # 2. Extract keywords
    await on_progress("Scanning the job description", "Extracting keywords & requirements")
    t0 = time.monotonic()
    keyword_data = await extract_keywords_llm(job_description, llm_fast)
    if keyword_data:
        job_keywords = keyword_data["all_keywords"]
        keyword_categories = keyword_data["categories"]
        update_attempt(attempt_id, extracted_keywords=keyword_data)
    else:
        job_keywords = None
        keyword_categories = None
    timings["keyword_extraction"] = round(time.monotonic() - t0, 2)
    logger.info("Pipeline[%s] step=keywords duration=%.2fs found=%d", attempt_id, timings["keyword_extraction"], len(job_keywords) if job_keywords else 0)

    # 3. ATS analysis on original
    await on_progress("Running ATS check", "Scoring your original CV")
    t0 = time.monotonic()
    ats_result = analyze_ats(cv_text, job_description, keywords_override=job_keywords)
    timings["ats_original"] = round(time.monotonic() - t0, 2)
    logger.info("Pipeline[%s] step=ats_original duration=%.2fs score=%d", attempt_id, timings["ats_original"], ats_result.score)

    # Get template and region info
    selected_template = get_template(template_id) or get_template("modern")
    region_config = get_region(region_code) or get_region("US")
    region_rules = REGION_RULES.get(region_code, REGION_RULES["US"])

    # 4. Generate tailored CV (the slow step)
    await on_progress("Writing your new CV", "AI at work — this is the big one")
    t0 = time.monotonic()
    cv_data = await generate_tailored_cv(
        cv_text_for_llm, job_description, ats_result.missing_keywords,
        region=region_config, llm=llm, attempt=attempt,
        ats_result=ats_result, keyword_categories=keyword_categories,
    )
    timings["ai_generate"] = round(time.monotonic() - t0, 2)
    logger.info("Pipeline[%s] step=ai_generate duration=%.2fs success=%s", attempt_id, timings["ai_generate"], cv_data is not None)

    if cv_data is None:
        raise ValueError("CV generation failed. Please try again.")

    # Restore real PII values from tokens
    if redactor:
        cv_data = redactor.restore(cv_data)

    # Quality gate — catch any leftover placeholders
    placeholder_issues = check_placeholders(cv_data)
    if placeholder_issues:
        logger.warning(
            "Placeholder issues in generated CV (attempt=%s): %s",
            attempt_id, placeholder_issues,
        )

    # 5. Render template
    await on_progress("Rendering the template", "Laying out your final design")
    llm_usage = cv_data.pop("_llm_usage", {})
    rendered_cv = templates.get_template(
        f"cv_templates/{template_id}.html"
    ).render(**cv_data)
    cv_data["_llm_usage"] = llm_usage
    logger.info("Pipeline[%s] step=render template=%s html_len=%d", attempt_id, template_id, len(rendered_cv))

    # 6. ATS + quality review in parallel
    await on_progress("Final ATS comparison", "Scoring the result and reviewing quality")
    t0 = time.monotonic()
    generated_text = re.sub(r'<style[^>]*>.*?</style>', '', rendered_cv, flags=re.DOTALL)
    generated_text = re.sub(r'<[^>]+>', ' ', generated_text)
    generated_text = re.sub(r'\s+', ' ', generated_text).strip()

    async def _ats():
        return analyze_ats(generated_text, job_description, keywords_override=job_keywords)

    async def _review():
        return await review_cv_quality(
            cv_data, job_description,
            region_name=region_config.name, llm=llm_fast,
        )

    ats_generated, quality_review = await asyncio.gather(_ats(), _review())
    timings["ats_generated"] = round(time.monotonic() - t0, 2)
    logger.info("Pipeline[%s] step=ats_review duration=%.2fs ats_score=%d review=%s", attempt_id, timings["ats_generated"], ats_generated.score, "ok" if quality_review else "failed")

    # Log generation
    log_generation(
        attempt_id=attempt_id,
        region=region_code,
        template_id=template_id,
        cv_text=cv_text,
        job_description=job_description,
        ats_original=ats_result,
        ats_generated=ats_generated,
        generated_text=generated_text,
        cv_data=cv_data,
        timings=timings,
    )

    from app.instrumentation import record_custom_event
    record_custom_event("CVGeneration", {
        "user_id": user_id,
        "attempt_id": attempt_id,
        "region": region_code,
        "template_id": template_id,
        "score_original": ats_result.score,
        "score_generated": ats_generated.score,
        "duration_sec": sum(timings.values()),
    })

    # Cache results
    review_flags = quality_review.get("flags", []) if quality_review else []
    update_attempt(
        attempt_id,
        cv_data=cv_data,
        rendered_cv=rendered_cv,
        cv_text_preview=cv_text[:500],
        quality_review_flags=review_flags,
    )

    # Persist CV as sanitized markdown for reuse
    try:
        async with async_session() as db:
            await save_cv(
                db,
                attempt_id=attempt_id,
                source="ai",
                region=region_code,
                template_id=template_id,
                rendered_html=rendered_cv,
                cv_data=cv_data,
            )
    except Exception:
        logger.exception("Failed to save CV to database (attempt=%s)", attempt_id)

    logger.info("Pipeline[%s] COMPLETE timings=%s", attempt_id, timings)
    return {
        "ats_original": ats_result,
        "ats_generated": ats_generated,
        "generated_cv": rendered_cv,
        "cv_text": cv_text[:500],
        "template": selected_template,
        "region": region_code,
        "region_rules": region_rules,
        "quality_review": quality_review,
    }


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
            attempt_id, step, detail, step_elapsed,
        )
        try:
            await websocket.send_json({"type": "progress", "step": step, "detail": detail})
        except (WebSocketDisconnect, RuntimeError) as err:
            raise WebSocketDisconnect() from err

    try:
        llm = websocket.app.state.llm
        llm_fast = websocket.app.state.llm_fast

        # WebSocket connections bypass BaseHTTPMiddleware, so resolve user directly
        from app.auth.dependencies import get_current_user
        ws_user = await get_current_user(websocket)
        ws_user_id = ws_user.id if ws_user else None

        result = await _run_generation_pipeline(
            attempt_id, llm, llm_fast, on_progress=send_progress,
            user_id=ws_user_id,
        )

        total_ms = round((time.monotonic() - ws_start) * 1000)
        llm_usage = result.get("quality_review") and (
            # _llm_usage lives inside cv_data; surface it for the log if present
            result.get("quality_review", {}) or {}
        )
        # Pull usage from cv_data if available (pipeline stores it there)
        attempt_data = {}
        try:
            from app.services.attempt_store import get_attempt as _get
            attempt_data = _get(attempt_id) or {}
        except Exception:
            pass
        cv_data = attempt_data.get("cv_data") or {}
        usage = cv_data.get("_llm_usage", {})
        if usage:
            logger.info(
                "WebSocket complete attempt=%s duration=%dms "
                "input_tokens=%s output_tokens=%s cost_usd=%s",
                attempt_id, total_ms,
                usage.get("input_tokens", "?"),
                usage.get("output_tokens", "?"),
                usage.get("cost_usd", "?"),
            )
        else:
            logger.info(
                "WebSocket complete attempt=%s duration=%dms",
                attempt_id, total_ms,
            )

        # Render the final HTML
        html = templates.get_template("partials/results.html").render(**result)
        await websocket.send_json({"type": "complete", "html": html})

    except WebSocketDisconnect:
        elapsed_ms = round((time.monotonic() - ws_start) * 1000)
        logger.info("WebSocket disconnected attempt=%s step=%r elapsed=%dms", attempt_id, current_step[0], elapsed_ms)
        return
    except ValueError as e:
        elapsed_ms = round((time.monotonic() - ws_start) * 1000)
        logger.warning(
            "WebSocket validation error attempt=%s step=%r elapsed=%dms error=%r",
            attempt_id, current_step[0], elapsed_ms, str(e),
        )
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except (WebSocketDisconnect, RuntimeError):
            pass
    except Exception:
        elapsed_ms = round((time.monotonic() - ws_start) * 1000)
        logger.exception(
            "WebSocket generation failed attempt=%s step=%r elapsed=%dms",
            attempt_id, current_step[0], elapsed_ms,
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

    http_user = getattr(request.state, "user", None)
    http_user_id = http_user.id if http_user else None

    try:
        result = await _run_generation_pipeline(
            attempt_id,
            request.app.state.llm,
            request.app.state.llm_fast,
            user_id=http_user_id,
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
    rendered_cv = templates.get_template(
        f"cv_templates/{template_id}.html"
    ).render(**updated_data)
    updated_data["_llm_usage"] = llm_usage

    generated_text = re.sub(r'<style[^>]*>.*?</style>', '', rendered_cv, flags=re.DOTALL)
    generated_text = re.sub(r'<[^>]+>', ' ', generated_text)
    generated_text = re.sub(r'\s+', ' ', generated_text).strip()

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
