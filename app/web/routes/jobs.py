"""Jobs routes — dashboard and wizard for target job applications.

Flow:
    GET  /jobs                    — list all jobs for the authenticated user
    GET  /jobs/new                — wizard step 1 (job details)
    POST /jobs/new/step/1/save    — save job description + auto-detect region
    POST /jobs/new/step/2/save    — save region + template choice
    GET  /jobs/new/step/3         — review page before generation
    POST /jobs/scrape-job         — HTMX: scrape a job URL and return text
    GET  /jobs/{job_id}           — job detail / results page
    DELETE /jobs/{job_id}         — delete a job (HTMX)
    POST /jobs/{job_id}/generate  — HTTP fallback: run generation pipeline
    GET  /jobs/{job_id}/download-pdf
    GET  /jobs/{job_id}/download-docx
    GET  /jobs/{job_id}/download-cover-letter-pdf
    GET  /jobs/{job_id}/download-cover-letter-docx
"""

import json
import logging

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse, Response

from app.cv_export.adapters.template_registry import REGIONS, list_regions, list_templates, list_templates_by_category
from app.cv_generation.adapters.region_detector import detect_region
from app.identity.adapters.fastapi_deps import get_current_user
from app.infrastructure.persistence.database import async_session
from app.infrastructure.persistence.job_repo import create_job, delete_job, get_job, list_jobs, update_job
from app.web.templates import templates

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------


async def _require_user(request: Request):
    """Return the current user, or None if unauthenticated.

    Callers should redirect to /login when this returns None.
    """
    return await get_current_user(request)


# ---------------------------------------------------------------------------
# GET /jobs — dashboard
# ---------------------------------------------------------------------------


@router.get("")
@router.get("/")
async def jobs_list(request: Request):
    """Show all jobs for the authenticated user."""
    user = await _require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    async with async_session() as db:
        jobs = await list_jobs(db, user.id)

    return templates.TemplateResponse("jobs.html", {
        "request": request,
        "user": user,
        "jobs": jobs,
    })


# ---------------------------------------------------------------------------
# GET /jobs/new — wizard step 1
# ---------------------------------------------------------------------------


@router.get("/new")
async def jobs_new(request: Request):
    """Render the job wizard.

    Full page navigation → ``new_job.html`` (extends base.html, includes step 1).
    HTMX swap (back button from step 2) → just the step 1 partial.
    """
    user = await _require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    pii = request.state.session.get("pii") or {}
    ctx = {"request": request, "user": user, "pii": pii}

    # HTMX request → return just the partial for in-page swap
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/job_wizard/step1_job.html", ctx)

    # Full page navigation → return the host page with layout
    return templates.TemplateResponse("new_job.html", ctx)


# ---------------------------------------------------------------------------
# POST /jobs/scrape-job — HTMX: scrape URL and return description text
# ---------------------------------------------------------------------------


@router.post("/scrape-job")
async def jobs_scrape_job(request: Request, job_url: str = Form("")):
    """Scrape a job posting URL and return an HTMX partial with the description."""
    from app.cv_generation.adapters.job_scraper import scrape_job_url

    result = await scrape_job_url(job_url)
    return templates.TemplateResponse("partials/wizard/job_scrape_result.html", {
        "request": request,
        "success": result["success"],
        "text": result["text"],
        "title": result["title"],
        "error": result["error"],
    })


# ---------------------------------------------------------------------------
# POST /jobs/new/step/1/save — save job + detect region
# ---------------------------------------------------------------------------


@router.post("/new/step/1/save")
async def jobs_new_step1_save(
    request: Request,
    job_url: str = Form(""),
    job_description: str = Form(""),
    job_title: str = Form(""),
    company_name: str = Form(""),
    offer_appeal: str = Form(""),
):
    """Persist job details, detect target region, advance to step 2."""
    user = await _require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    # If a URL was given but no description yet, try to scrape it.
    if job_url.strip() and not job_description.strip():
        from app.cv_generation.adapters.job_scraper import scrape_job_url
        scraped = await scrape_job_url(job_url)
        if scraped["success"] and scraped["text"]:
            job_description = scraped["text"]
        if scraped["title"] and not job_title.strip():
            job_title = scraped["title"]

    if not job_description.strip():
        pii = request.state.session.get("pii") or {}
        return templates.TemplateResponse("partials/job_wizard/step1_job.html", {
            "request": request,
            "user": user,
            "pii": pii,
            "error": "Please paste a job description or provide a valid job URL.",
            "job_url": job_url,
            "job_title": job_title,
            "company_name": company_name,
            "offer_appeal": offer_appeal,
        })

    # Auto-detect region from URL / description; fall back to vault country.
    pii = request.state.session.get("pii") or {}
    fallback = pii.get("country", "AU")
    detected = detect_region(
        job_url=job_url,
        job_description=job_description,
        fallback_region=fallback if fallback in REGIONS else "AU",
    )
    region_code = detected["region"] or "AU"
    region_confidence = detected["confidence"]

    async with async_session() as db:
        job = await create_job(
            db,
            user_id=user.id,
            job_description=job_description,
            region=region_code,
            job_url=job_url.strip(),
            job_title=job_title.strip(),
            company_name=company_name.strip(),
            offer_appeal=offer_appeal,
            template_id="",
        )

    # Store the new job ID in session so subsequent wizard steps can find it.
    request.state.session["current_job_id"] = job.id
    logger.info("Created job %s for user=%s (region=%s, confidence=%s)", job.id, user.id, region_code, region_confidence)

    # Prepare template recommendations for step 2.
    available_templates = list_templates(region=region_code)
    categories = ["universal", "industry", "region", "specialty"]
    grouped = {}
    available_ids = {t.id for t in available_templates}
    for cat in categories:
        cat_tpls = [t for t in list_templates_by_category(cat) if t.id in available_ids]
        if cat_tpls:
            grouped[cat] = cat_tpls

    from app.web.routes.wizard import _region_fields

    return templates.TemplateResponse("partials/job_wizard/step2_config.html", {
        "request": request,
        "user": user,
        "job": job,
        "detected_region": region_code,
        "region_confidence": region_confidence,
        "regions": list_regions(),
        "templates": available_templates,
        "grouped_templates": grouped,
        "region_config": REGIONS.get(region_code, REGIONS["AU"]),
        "fields": _region_fields(region_code),
    })


# ---------------------------------------------------------------------------
# POST /jobs/new/step/2/save — save region + template
# ---------------------------------------------------------------------------


@router.post("/new/step/2/save")
async def jobs_new_step2_save(
    request: Request,
    region: str = Form("AU"),
):
    """Persist region, auto-select template, advance to review step."""
    user = await _require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    job_id = request.state.session.get("current_job_id")
    if not job_id:
        return RedirectResponse("/jobs/new", status_code=302)

    async with async_session() as db:
        job = await get_job(db, job_id, user_id=user.id)
        if not job:
            return RedirectResponse("/jobs", status_code=302)

        # Auto-select the best template for this region.
        # Keep any existing choice (e.g. from a retry); fall back to first
        # available template for the region, then "modern".
        template_id = job.template_id or ""
        if not template_id:
            region_templates = list_templates(region=region)
            template_id = region_templates[0].id if region_templates else "modern"

        job = await update_job(db, job_id, region=region, template_id=template_id)

    return await _render_step3(request, user, job)


# ---------------------------------------------------------------------------
# GET /jobs/new/step/3 — review before generation
# ---------------------------------------------------------------------------


@router.get("/new/step/3")
async def jobs_new_step3(request: Request):
    """Re-render the review step from session state."""
    user = await _require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    job_id = request.state.session.get("current_job_id")
    if not job_id:
        return RedirectResponse("/jobs/new", status_code=302)

    async with async_session() as db:
        job = await get_job(db, job_id, user_id=user.id)

    if not job:
        return RedirectResponse("/jobs", status_code=302)

    return await _render_step3(request, user, job)


async def _render_step3(request: Request, user, job):
    """Shared renderer for wizard step 3 (review + generate)."""
    from app.web.routes.wizard import _check_pii_completeness

    pii = request.state.session.get("pii") or {}
    region_code = job.region or "AU"
    region_config = REGIONS.get(region_code, REGIONS["AU"])

    # Check profile completeness for the selected region.
    # We pass an empty attempt dict so only vault data is checked.
    pii_complete, pii_missing = _check_pii_completeness({}, pii, region_code)

    return templates.TemplateResponse("partials/job_wizard/step3_review.html", {
        "request": request,
        "user": user,
        "job": job,
        "pii": pii,
        "region_config": region_config,
        "pii_complete": pii_complete,
        "pii_missing": pii_missing,
    })


# ---------------------------------------------------------------------------
# POST /jobs/new/step/3/save-pii — inline PII save (first-time users)
# ---------------------------------------------------------------------------


@router.post("/new/step/3/save-pii")
async def jobs_new_step3_save_pii(
    request: Request,
    full_name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
):
    """Save minimal PII (name/email/phone) inline and re-render step 3."""
    from app.infrastructure.phone_utils import normalize_phone
    from app.pii.adapters.vault import upsert_vault

    user = await _require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    full_name = full_name.strip()
    if not full_name:
        job_id = request.state.session.get("current_job_id")
        if not job_id:
            return RedirectResponse("/jobs/new", status_code=302)
        async with async_session() as db:
            job = await get_job(db, job_id, user_id=user.id)
        return await _render_step3(request, user, job)

    pii = request.state.session.get("pii") or {}
    pii["full_name"] = full_name
    if email.strip():
        pii["email"] = email.strip()
    if phone.strip():
        pii["phone"] = normalize_phone(phone)

    password = request.state.session.get("_pii_password")
    async with async_session() as db:
        await upsert_vault(db, user_id=user.id, pii=pii, password=password or None)

    request.state.session["pii"] = pii
    request.state.session["pii_onboarded"] = True

    job_id = request.state.session.get("current_job_id")
    if not job_id:
        return RedirectResponse("/jobs/new", status_code=302)

    async with async_session() as db:
        job = await get_job(db, job_id, user_id=user.id)

    return await _render_step3(request, user, job)


# ---------------------------------------------------------------------------
# GET /jobs/{job_id} — job detail / results
# ---------------------------------------------------------------------------


@router.get("/{job_id}")
async def job_detail(request: Request, job_id: str):
    """Show the job detail page (includes generated CV and cover letter if ready)."""
    user = await _require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    async with async_session() as db:
        job = await get_job(db, job_id, user_id=user.id)

    if not job:
        return Response("Job not found", status_code=404)

    pii = request.state.session.get("pii") or {}
    region_config = REGIONS.get(job.region, REGIONS.get("AU"))

    # Parse stored JSON blobs if generation is complete.
    cv_data = None
    cover_letter_data = None
    if job.cv_data_json:
        try:
            cv_data = json.loads(job.cv_data_json)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Could not parse cv_data_json for job=%s", job_id)

    if job.cover_letter_json:
        try:
            cover_letter_data = json.loads(job.cover_letter_json)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Could not parse cover_letter_json for job=%s", job_id)

    return templates.TemplateResponse("job_detail.html", {
        "request": request,
        "user": user,
        "job": job,
        "pii": pii,
        "region_config": region_config,
        "cv_data": cv_data,
        "cover_letter_data": cover_letter_data,
    })


# ---------------------------------------------------------------------------
# DELETE /jobs/{job_id} — delete a job (HTMX)
# ---------------------------------------------------------------------------


@router.delete("/{job_id}")
async def job_delete(request: Request, job_id: str):
    """Delete a job owned by the current user.  Returns an empty 200 for HTMX."""
    user = await _require_user(request)
    if not user:
        return Response(status_code=401)

    async with async_session() as db:
        deleted = await delete_job(db, job_id, user.id)

    if not deleted:
        return Response("Job not found or not owned by you", status_code=404)

    # If this was the active wizard job, clear it from session.
    if request.state.session.get("current_job_id") == job_id:
        request.state.session.pop("current_job_id", None)

    # HTMX expects an empty body; the swap removes the row from the DOM.
    return Response(status_code=200)


# ---------------------------------------------------------------------------
# POST /jobs/{job_id}/generate — HTTP fallback generation
# ---------------------------------------------------------------------------


@router.post("/{job_id}/generate")
async def job_generate(request: Request, job_id: str):
    """Trigger CV generation for a job and store the results.

    This is the HTTP (non-WebSocket) fallback.  For real-time progress,
    the frontend should use the WebSocket endpoint instead once it is wired up.
    """
    user = await _require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    async with async_session() as db:
        job = await get_job(db, job_id, user_id=user.id)

    if not job:
        return Response("Job not found", status_code=404)

    # Mark as generating.
    async with async_session() as db:
        await update_job(db, job_id, status="generating")

    # Build a transient attempt from the job + PII vault so the existing
    # generation pipeline can run without modification.
    import uuid as _uuid_mod

    from app.infrastructure.persistence.attempt_store import create_attempt, update_attempt as _update_attempt

    attempt_id = create_attempt()
    pii = request.state.session.get("pii") or {}
    _update_attempt(
        attempt_id,
        region=job.region,
        template_id=job.template_id or "modern",
        job_description=job.job_description,
        offer_appeal=job.offer_appeal,
        full_name=pii.get("full_name", ""),
        email=pii.get("email", ""),
        phone=pii.get("phone", ""),
        step=5,
    )

    from app.infrastructure.llm.client import set_llm_context
    set_llm_context(
        service="job_generate",
        attempt_id=attempt_id,
        user_id=user.id,
        transaction_id=_uuid_mod.uuid4().hex,
    )

    from app.cv_generation.use_cases.generate_cv import run_generation_pipeline

    try:
        result = await run_generation_pipeline(
            attempt_id,
            request.app.state.llm,
            request.app.state.llm_fast,
            user_id=user.id,
            pii=pii,
            pii_password=request.state.session.get("_pii_password"),
        )
    except ValueError as exc:
        async with async_session() as db:
            await update_job(db, job_id, status="error")
        return templates.TemplateResponse("partials/error.html", {
            "request": request,
            "error": str(exc),
        })
    except Exception:
        logger.exception("Generation failed for job=%s", job_id)
        async with async_session() as db:
            await update_job(db, job_id, status="error")
        return templates.TemplateResponse("partials/error.html", {
            "request": request,
            "error": "Generation failed. Please try again.",
        })

    # Persist the outputs back to the Job record.
    from app.infrastructure.persistence.attempt_store import get_attempt as _get_attempt

    attempt_data = _get_attempt(attempt_id) or {}
    cv_data = attempt_data.get("cv_data") or {}
    rendered_cv = attempt_data.get("rendered_cv", "")

    ats_original = result.get("ats_original", {})
    ats_generated = result.get("ats_generated", {})

    async with async_session() as db:
        await update_job(
            db,
            job_id,
            status="complete",
            cv_data_json=json.dumps(cv_data, default=str) if cv_data else None,
            cv_rendered_html=rendered_cv or None,
            ats_original_score=ats_original.get("score") if isinstance(ats_original, dict) else None,
            ats_generated_score=ats_generated.get("score") if isinstance(ats_generated, dict) else None,
            attempt_id=attempt_id,
        )

    # Redirect to the job detail page which shows the results.
    return RedirectResponse(f"/jobs/{job_id}", status_code=303)


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}/change-template — template picker for completed jobs
# POST /jobs/{job_id}/change-template — apply new template (resets to draft)
# ---------------------------------------------------------------------------


@router.get("/{job_id}/change-template")
async def job_change_template_get(request: Request, job_id: str):
    """Render an inline template picker so user can pick a different template."""
    user = await _require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    async with async_session() as db:
        job = await get_job(db, job_id, user_id=user.id)
    if not job:
        return Response("Job not found", status_code=404)

    available = list_templates(region=job.region or "AU")
    return templates.TemplateResponse("partials/job_wizard/change_template_picker.html", {
        "request": request,
        "job": job,
        "templates": available,
        "selected_template": job.template_id or "modern",
    })


@router.post("/{job_id}/change-template")
async def job_change_template_post(
    request: Request,
    job_id: str,
    template_id: str = Form("modern"),
):
    """Update the template and reset job to draft for regeneration."""
    user = await _require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    async with async_session() as db:
        job = await get_job(db, job_id, user_id=user.id)
        if not job:
            return Response("Job not found", status_code=404)
        await update_job(db, job_id, template_id=template_id, status="draft")

    return RedirectResponse(f"/jobs/{job_id}", status_code=303)


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------


async def _load_job_or_404(request: Request, job_id: str):
    """Load and verify job ownership.  Returns (user, job) or raises 404."""
    user = await _require_user(request)
    if not user:
        return None, None

    async with async_session() as db:
        job = await get_job(db, job_id, user_id=user.id)

    return user, job


@router.get("/{job_id}/download-pdf")
async def job_download_pdf(request: Request, job_id: str):
    """Download the generated CV as PDF."""
    from app.cv_export.adapters.puppeteer_pdf import generate_pdf

    user, job = await _load_job_or_404(request, job_id)
    if not user:
        return RedirectResponse("/login", status_code=302)
    if not job:
        return Response("Job not found", status_code=404)
    if not job.cv_rendered_html:
        return Response("CV not yet generated. Please generate first.", status_code=400)

    cv_name = _safe_cv_name(job)
    pdf_bytes = await generate_pdf(job.cv_rendered_html)
    if pdf_bytes is None:
        return Response("PDF generation failed. Please try again.", status_code=500)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{cv_name} - QuillCV.pdf"'},
    )


@router.get("/{job_id}/download-docx")
async def job_download_docx(request: Request, job_id: str):
    """Download the generated CV as DOCX."""
    from app.cv_export.adapters.docx_export import generate_docx

    user, job = await _load_job_or_404(request, job_id)
    if not user:
        return RedirectResponse("/login", status_code=302)
    if not job:
        return Response("Job not found", status_code=404)
    if not job.cv_data_json:
        return Response("CV not yet generated. Please generate first.", status_code=400)

    try:
        cv_data = json.loads(job.cv_data_json)
    except (json.JSONDecodeError, TypeError):
        return Response("CV data is corrupted.", status_code=500)

    cv_name = _safe_cv_name(job)
    region_code = job.region or "AU"
    template_id = job.template_id or "classic"

    try:
        docx_bytes = generate_docx(cv_data, region_code=region_code, template_id=template_id)
    except Exception:
        logger.exception("DOCX generation failed for job=%s", job_id)
        return Response("DOCX generation failed. Please try again.", status_code=500)

    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{cv_name} - QuillCV.docx"'},
    )


@router.get("/{job_id}/download-cover-letter-pdf")
async def job_download_cover_letter_pdf(request: Request, job_id: str):
    """Download the generated cover letter as PDF."""
    from app.cv_export.adapters.puppeteer_pdf import generate_pdf

    user, job = await _load_job_or_404(request, job_id)
    if not user:
        return RedirectResponse("/login", status_code=302)
    if not job:
        return Response("Job not found", status_code=404)
    if not job.cover_letter_html:
        return Response("Cover letter not yet generated.", status_code=400)

    cv_name = _safe_cv_name(job)
    pdf_bytes = await generate_pdf(job.cover_letter_html)
    if pdf_bytes is None:
        return Response("PDF generation failed. Please try again.", status_code=500)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{cv_name} - Cover Letter - QuillCV.pdf"'},
    )


@router.get("/{job_id}/download-cover-letter-docx")
async def job_download_cover_letter_docx(request: Request, job_id: str):
    """Download the generated cover letter as DOCX."""
    from app.cv_export.adapters.docx_export import generate_docx

    user, job = await _load_job_or_404(request, job_id)
    if not user:
        return RedirectResponse("/login", status_code=302)
    if not job:
        return Response("Job not found", status_code=404)
    if not job.cover_letter_json:
        return Response("Cover letter not yet generated.", status_code=400)

    try:
        cl_data = json.loads(job.cover_letter_json)
    except (json.JSONDecodeError, TypeError):
        return Response("Cover letter data is corrupted.", status_code=500)

    cv_name = _safe_cv_name(job)
    region_code = job.region or "AU"
    template_id = job.template_id or "classic"

    try:
        docx_bytes = generate_docx(cl_data, region_code=region_code, template_id=template_id)
    except Exception:
        logger.exception("Cover letter DOCX generation failed for job=%s", job_id)
        return Response("DOCX generation failed. Please try again.", status_code=500)

    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{cv_name} - Cover Letter - QuillCV.docx"'},
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _safe_cv_name(job) -> str:
    """Build a filesystem-safe display name from the job record."""
    parts = [job.job_title, job.company_name]
    name = " - ".join(p.strip() for p in parts if p and p.strip()) or "CV"
    return "".join(c for c in name if c.isalnum() or c in " -_").strip() or "CV"
