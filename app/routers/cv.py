import asyncio
import json
import re
import time

from fastapi import APIRouter, Request
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.services.cv_parser import parse_cv
from app.services.ats_analyzer import analyze_ats
from app.services.ai_generator import generate_tailored_cv
from app.services.attempt_store import get_attempt, get_document_bytes, get_document_filename, update_attempt
from app.services.cv_refiner import apply_review_fixes
from app.services.cv_reviewer import review_cv_quality
from app.services.generation_log import log_generation
from app.services.keyword_extractor import extract_keywords_llm
from app.services.pdf_generator import generate_pdf
from app.services.template_registry import get_region, get_template, REGION_RULES

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


@router.post("/analyze")
async def analyze(request: Request):
    """Parse CV from attempt store, run ATS analysis, and generate tailored CV."""
    attempt_id = request.session.get("attempt_id")
    if not attempt_id:
        return templates.TemplateResponse(
            "partials/error.html",
            {"request": request, "error": "No active session. Please start from the beginning."},
        )

    attempt = get_attempt(attempt_id)
    if not attempt:
        return templates.TemplateResponse(
            "partials/error.html",
            {"request": request, "error": "Session expired. Please start again."},
        )

    # Read CV file from attempt store
    cv_bytes = get_document_bytes(attempt_id, "cv_file")
    cv_filename = get_document_filename(attempt_id, "cv_file")
    if not cv_bytes or not cv_filename:
        return templates.TemplateResponse(
            "partials/error.html",
            {"request": request, "error": "No CV file found. Please go back to step 3 and upload your CV."},
        )

    timings = {}

    # Parse CV
    t0 = time.monotonic()
    try:
        cv_text = parse_cv(cv_filename, cv_bytes)
    except ValueError as e:
        return templates.TemplateResponse(
            "partials/error.html",
            {"request": request, "error": str(e)},
        )
    timings["parse_cv"] = round(time.monotonic() - t0, 2)

    if not cv_text.strip():
        return templates.TemplateResponse(
            "partials/error.html",
            {"request": request, "error": "Could not extract text from the CV file."},
        )

    # Get settings from attempt
    region_code = attempt.get("region", "AU")
    template_id = attempt.get("template_id", "modern")
    job_description = attempt.get("job_description", "")

    llm = request.app.state.llm
    llm_fast = request.app.state.llm_fast

    # Extract keywords with LLM (fast model) or fall back to regex
    t0 = time.monotonic()
    keyword_data = await extract_keywords_llm(job_description, llm_fast)
    if keyword_data:
        job_keywords = keyword_data["all_keywords"]
        keyword_categories = keyword_data["categories"]
        timings["keyword_extraction"] = round(time.monotonic() - t0, 2)
        # Cache on the attempt for re-use
        update_attempt(attempt_id, extracted_keywords=keyword_data)
    else:
        job_keywords = None  # will fall back to regex in analyze_ats
        keyword_categories = None
        timings["keyword_extraction"] = round(time.monotonic() - t0, 2)

    # Run ATS analysis with LLM-extracted keywords
    t0 = time.monotonic()
    ats_result = analyze_ats(cv_text, job_description, keywords_override=job_keywords)
    timings["ats_original"] = round(time.monotonic() - t0, 2)

    # Get template and region info
    selected_template = get_template(template_id) or get_template("modern")
    region_config = get_region(region_code) or get_region("US")
    region_rules = REGION_RULES.get(region_code, REGION_RULES["US"])

    # Generate tailored CV
    t0 = time.monotonic()
    cv_data = await generate_tailored_cv(
        cv_text, job_description, ats_result.missing_keywords,
        region=region_config, llm=llm, attempt=attempt,
        ats_result=ats_result, keyword_categories=keyword_categories,
    )
    timings["ai_generate"] = round(time.monotonic() - t0, 2)

    if cv_data is None:
        return templates.TemplateResponse(
            "partials/error.html",
            {"request": request, "error": "CV generation failed. Please try again."},
        )

    # Strip internal metadata before rendering
    llm_usage = cv_data.pop("_llm_usage", {})

    # Render the CV through the selected Jinja2 template
    rendered_cv = templates.get_template(
        f"cv_templates/{template_id}.html"
    ).render(**cv_data)

    # Re-attach for logging
    cv_data["_llm_usage"] = llm_usage

    # Run ATS and quality review in parallel (both read generated data)
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

    # Log generation for analysis
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

    # Cache the result + quality review flags for apply-fixes endpoint
    review_flags = quality_review.get("flags", []) if quality_review else []
    update_attempt(
        attempt_id,
        cv_data=cv_data,
        rendered_cv=rendered_cv,
        cv_text_preview=cv_text[:500],
        quality_review_flags=review_flags,
    )

    return templates.TemplateResponse(
        "partials/results.html",
        {
            "request": request,
            "ats_original": ats_result,
            "ats_generated": ats_generated,
            "generated_cv": rendered_cv,
            "cv_text": cv_text[:500],
            "template": selected_template,
            "region": region_code,
            "region_rules": region_rules,
            "quality_review": quality_review,
        },
    )


@router.post("/apply-fixes")
async def apply_fixes(request: Request):
    """Apply selected quality review fixes to the generated CV."""
    attempt_id = request.session.get("attempt_id")
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

    # Checkboxes send name="selected" value="0", "1", etc. (indices into cached flags)
    # User instructions come as instruction_0, instruction_1, etc.
    cached_flags = attempt.get("quality_review_flags", [])
    selected_indices = form.getlist("selected")

    flags = []
    for idx_str in selected_indices:
        try:
            idx = int(idx_str)
            if 0 <= idx < len(cached_flags):
                flag = dict(cached_flags[idx])  # copy
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

    # Apply fixes via LLM
    updated_data = await apply_review_fixes(cv_data, flags, job_description, llm=llm_fast)
    if updated_data is None:
        return templates.TemplateResponse(
            "partials/error.html",
            {"request": request, "error": "Failed to apply fixes. Please try again."},
        )

    # Re-render the CV template
    llm_usage = updated_data.pop("_llm_usage", {})
    rendered_cv = templates.get_template(
        f"cv_templates/{template_id}.html"
    ).render(**updated_data)
    updated_data["_llm_usage"] = llm_usage

    # Run ATS on the refined CV
    generated_text = re.sub(r'<style[^>]*>.*?</style>', '', rendered_cv, flags=re.DOTALL)
    generated_text = re.sub(r'<[^>]+>', ' ', generated_text)
    generated_text = re.sub(r'\s+', ' ', generated_text).strip()

    # Use cached keywords if available
    keyword_data = attempt.get("extracted_keywords")
    job_keywords = keyword_data["all_keywords"] if keyword_data else None
    ats_generated = analyze_ats(generated_text, job_description, keywords_override=job_keywords)

    # Update the cached attempt with refined data
    update_attempt(attempt_id, cv_data=updated_data, rendered_cv=rendered_cv)

    selected_template = get_template(template_id) or get_template("modern")
    region_rules = REGION_RULES.get(region_code, REGION_RULES["US"])

    # Re-run ATS on original for comparison
    cv_text = attempt.get("cv_text_preview", "")
    # For original score, use the full original — but we only have preview cached
    # Re-parse if we have the file, otherwise use a minimal comparison
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
            "quality_review": None,  # Fixes already applied
            "fixes_applied": len(flags),
        },
    )


@router.get("/download-pdf")
async def download_pdf(request: Request):
    """Generate and download the CV as PDF."""
    attempt_id = request.session.get("attempt_id")
    if not attempt_id:
        return Response("No active session", status_code=400)

    attempt = get_attempt(attempt_id)
    if not attempt or not attempt.get("rendered_cv"):
        return Response("No generated CV found. Please generate your CV first.", status_code=400)

    rendered_cv = attempt["rendered_cv"]
    cv_name = attempt.get("cv_data", {}).get("name", "CV") or "CV"
    # Sanitize filename
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
