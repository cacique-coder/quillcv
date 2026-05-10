"""Manual CV builder — free, no AI, no credits required.

Users fill in their CV data via a form and get it rendered through
the same professional templates used by the AI generator.
"""

import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import Response

from app.cv_builder.use_cases.build_cv import (
    apply_pii_prefill,
    compute_pii_backfill,
    cv_data_from_attempt,
    default_save_label,
    parse_form_into_builder_data,
    region_fields_map,
    restore_pii_tokens,
)
from app.cv_export.adapters.docx_export import generate_docx
from app.cv_export.adapters.puppeteer_pdf import generate_pdf
from app.cv_export.adapters.template_registry import TEMPLATES, list_regions, list_templates
from app.infrastructure.persistence.attempt_store import create_attempt, get_attempt, update_attempt
from app.infrastructure.persistence.cv_repo import get_saved_cv, save_cv, update_cv
from app.infrastructure.persistence.database import async_session
from app.web.templates import templates

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/builder")

# ---------------------------------------------------------------------------
# Starter CV — seeded once on first visit so the canvas is never empty
# ---------------------------------------------------------------------------

STARTER_BUILDER_DATA: dict = {
    # Personal — left blank so PII vault can fill them in
    "name": "",
    "email": "",
    "phone": "",
    "linkedin": "",
    "github": "",
    "portfolio": "",
    # Profile defaults
    "title": "Your job title",
    "location": "City, Country",
    "summary": (
        "Two to four sentences highlighting the strengths you want this CV to lead with. "
        "Mention the role you're targeting, the scale of work you've delivered, and the "
        "technologies or methods you've owned."
    ),
    "experience": [
        {
            "title": "Senior Engineer",
            "company": "Company name",
            "location": "City, Country",
            "date": "2022 – Present",
            "tech": "Python, FastAPI, PostgreSQL",
            "bullets": [
                "Led a small team to ship a critical feature on time and on scope.",
                "Owned the migration of a legacy system, reducing operational cost by ~30%.",
                "Mentored two engineers; both promoted within 18 months.",
            ],
        }
    ],
    "education": [
        {
            "degree": "Bachelor of Computer Science",
            "institution": "University name",
            "date": "2018",
        }
    ],
    "skills": ["Python", "JavaScript", "PostgreSQL", "Docker", "AWS"],
    "certifications": [],
    "projects": [],
    "references": [],
    "languages": [],
    # Region-specific fields
    "dob": "",
    "nationality": "",
    "marital_status": "",
    "visa_status": "",
    "photo_url": "",
    # Display defaults — Australia is QuillCV's primary market
    "template_id": "modern",
    "region": "AU",
}


def _get_or_create_builder(request: Request) -> dict:
    """Get or create a builder attempt (separate from the AI wizard).

    On first visit (new attempt), seeds ``builder_data`` with ``STARTER_BUILDER_DATA``
    so the canvas always shows real, editable content rather than empty placeholders.
    Existing in-progress attempts are returned as-is.
    """
    attempt_id = request.state.session.get("builder_id")
    if attempt_id:
        attempt = get_attempt(attempt_id)
        if attempt:
            return attempt
    attempt_id = create_attempt()
    request.state.session["builder_id"] = attempt_id
    update_attempt(attempt_id, builder_data=STARTER_BUILDER_DATA)
    return get_attempt(attempt_id)


@router.get("")
async def builder_page(request: Request):
    """Main builder page with the form."""
    attempt = _get_or_create_builder(request)
    # /builder is the "new CV" entry point. If a prior /builder/edit/{id}
    # session left editing_cv_id on the reused attempt, save would try to
    # UPDATE that (possibly deleted) row and surface "CV not found".
    if attempt.get("editing_cv_id"):
        update_attempt(attempt["id"], editing_cv_id=None)
        attempt = get_attempt(attempt["id"])
    cv_data = cv_data_from_attempt(attempt)

    # Pre-fill from PII vault when builder fields are empty
    pii = request.state.session.get("pii") or {}
    if pii:
        apply_pii_prefill(cv_data, pii)

    region = attempt.get("builder_data", {}).get("region", "US")
    template_id = attempt.get("builder_data", {}).get("template_id", "modern")

    template_options = [(t.id, t.name) for t in list_templates()]
    region_options = [(r.code, f"{r.flag} {r.name}") for r in list_regions()]
    region_fields = region_fields_map()

    return templates.TemplateResponse(
        "builder.html",
        {
            "request": request,
            "cv_data": cv_data,
            "template_options": template_options,
            "region_options": region_options,
            "selected_region": region,
            "selected_template": template_id,
            "region_fields_json": json.dumps(region_fields),
            "dev_mode": request.app.state.dev_mode,
            "editing_cv_id": None,
            "editing_label": "",
            "editing_job_title": "",
            "page_crumbs": [
                {"label": "Create", "href": "/dashboard"},
                {"label": "Builder", "href": "/builder"},
                {"label": "New CV"},
            ],
        },
    )


@router.get("/edit/{cv_id}")
async def builder_edit(cv_id: str, request: Request):
    """Load a saved CV into the builder for editing."""
    pii = request.state.session.get("pii") or {}
    async with async_session() as db:
        saved = await get_saved_cv(db, cv_id, pii=pii)

    if not saved:
        from fastapi.responses import RedirectResponse

        return RedirectResponse("/my-cvs", status_code=303)

    # Parse the stored cv_data_json back into builder_data
    stored_data: dict = {}
    if saved.cv_data_json:
        try:
            stored_data = json.loads(saved.cv_data_json)
            if pii:
                stored_data = restore_pii_tokens(stored_data, pii)
                # Also pre-fill empty profile fields from PII vault after token restore
                profile_field_map = {
                    "full_name": "name",
                    "email": "email",
                    "phone": "phone",
                    "location": "location",
                    "linkedin": "linkedin",
                    "github": "github",
                    "portfolio": "portfolio",
                }
                for pii_key, cv_key in profile_field_map.items():
                    if not stored_data.get(cv_key) and pii.get(pii_key):
                        stored_data[cv_key] = pii[pii_key]
        except Exception:
            logger.warning("Failed to parse cv_data_json for CV %s", cv_id)

    # Merge stored data with template/region from the SavedCV columns
    builder_data = {**stored_data, "template_id": saved.template_id, "region": saved.region}

    # Create a fresh builder attempt for this edit session
    attempt_id = create_attempt()
    request.state.session["builder_id"] = attempt_id
    update_attempt(attempt_id, builder_data=builder_data, editing_cv_id=cv_id)

    cv_data = cv_data_from_attempt({"builder_data": builder_data})
    region = saved.region
    template_id = saved.template_id

    template_options = [(t.id, t.name) for t in list_templates()]
    region_options = [(r.code, f"{r.flag} {r.name}") for r in list_regions()]
    region_fields = region_fields_map()

    return templates.TemplateResponse(
        "builder.html",
        {
            "request": request,
            "cv_data": cv_data,
            "template_options": template_options,
            "region_options": region_options,
            "selected_region": region,
            "selected_template": template_id,
            "region_fields_json": json.dumps(region_fields),
            "dev_mode": request.app.state.dev_mode,
            "editing_cv_id": cv_id,
            "editing_label": saved.label or "Untitled CV",
            "editing_job_title": saved.job_title or "",
            "page_crumbs": [
                {"label": "Create", "href": "/dashboard"},
                {"label": "Builder", "href": "/builder"},
                {"label": saved.label or "Edit CV"},
            ],
        },
    )


@router.post("/preview")
async def builder_preview(request: Request):
    """Save form data and return rendered CV preview.

    Auto-preview fires on every keystroke (after 800ms debounce), so the form
    may be nearly empty. We still render — the templates handle missing fields
    gracefully — but we return a lightweight "keep typing" placeholder if there
    is truly no meaningful content yet.
    """
    attempt = _get_or_create_builder(request)
    form = await request.form()

    # Guard: if nothing meaningful is filled in yet, return a friendly nudge
    # rather than rendering an empty CV template.
    _has_content = any(
        form.get(f, "").strip() for f in ("name", "title", "summary", "exp_title_0", "edu_degree_0", "skills")
    )
    if not _has_content:
        return Response(
            '<div class="builder-preview-empty" style="padding:2.5rem 1rem;text-align:center;">'
            '<p style="color:var(--text-muted);font-size:0.9rem;">Start filling in your details and the preview will appear here automatically.</p>'
            "</div>",
            media_type="text/html",
        )

    builder_data = parse_form_into_builder_data(form)
    template_id = builder_data["template_id"]
    region = builder_data["region"]

    # Save to attempt store — preserve editing_cv_id if present
    editing_cv_id = attempt.get("editing_cv_id")
    extra = {"editing_cv_id": editing_cv_id} if editing_cv_id else {}
    update_attempt(attempt["id"], builder_data=builder_data, **extra)

    # Render CV with selected template
    cv_data = cv_data_from_attempt({"builder_data": builder_data})
    rendered_cv = templates.get_template(f"cv_templates/{template_id}.html").render(**cv_data)

    # Cache for PDF download
    update_attempt(attempt["id"], rendered_cv=rendered_cv, cv_data=cv_data)

    return templates.TemplateResponse(
        "partials/builder_preview.html",
        {
            "request": request,
            "generated_cv": rendered_cv,
            "template_name": (TEMPLATES.get(template_id) or TEMPLATES["modern"]).name,
            "region": region,
        },
    )


@router.post("/save")
async def builder_save(request: Request):
    """Save the current CV with a user-chosen name."""
    attempt_id = request.state.session.get("builder_id")
    if not attempt_id:
        return Response('<div class="save-error">No active session.</div>', media_type="text/html")

    attempt = get_attempt(attempt_id)
    if not attempt:
        return Response('<div class="save-error">No active session.</div>', media_type="text/html")

    if not attempt.get("rendered_cv"):
        builder_data = attempt.get("builder_data", {})
        template_id = builder_data.get("template_id", "modern")
        cv_data = cv_data_from_attempt(attempt)
        rendered_cv = templates.get_template(f"cv_templates/{template_id}.html").render(**cv_data)
        update_attempt(attempt_id, rendered_cv=rendered_cv, cv_data=cv_data)
        attempt["rendered_cv"] = rendered_cv
        attempt["cv_data"] = cv_data

    form = await request.form()
    label = form.get("save_label", "").strip()[:255]
    job_title = form.get("save_job_title", "").strip()[:255]

    # If the full builder form was included (save button uses hx-include="#builder-form, ..."),
    # parse fresh data so we never save stale attempt store data (e.g. when the user fills in
    # the education tab and saves before the 800ms auto-preview debounce fires).
    if form.get("name") is not None or form.get("template_id") is not None:
        fresh_builder_data = parse_form_into_builder_data(form)
        template_id = fresh_builder_data["template_id"]

        cv_data = cv_data_from_attempt({"builder_data": fresh_builder_data})
        rendered_cv = templates.get_template(f"cv_templates/{template_id}.html").render(**cv_data)

        editing_cv_id = attempt.get("editing_cv_id")
        extra = {"editing_cv_id": editing_cv_id} if editing_cv_id else {}
        update_attempt(attempt_id, builder_data=fresh_builder_data, rendered_cv=rendered_cv, cv_data=cv_data, **extra)
        attempt = get_attempt(attempt_id)

    if not label:
        tpl_id = attempt.get("builder_data", {}).get("template_id", "modern")
        label = default_save_label(attempt.get("cv_data", {}), tpl_id)

    builder_data = attempt.get("builder_data", {})
    editing_cv_id = attempt.get("editing_cv_id")
    region = builder_data.get("region", "US")
    template_id = builder_data.get("template_id", "modern")

    # Backfill PII vault with values from CV data that are missing from the vault.
    # This ensures <<PHONE_1>>, <<EMAIL_1>> etc. tokens can be restored on load.
    user = getattr(request.state, "user", None)
    pii = request.state.session.get("pii") or {}
    if pii and user:
        cv = attempt.get("cv_data", {})
        backfill_updates = compute_pii_backfill(cv, pii)
        if backfill_updates:
            pii.update(backfill_updates)
            request.state.session["pii"] = pii
            from app.pii.adapters.vault import upsert_vault

            async with async_session() as db:
                password = request.state.session.get("_pii_password")
                await upsert_vault(db, user_id=user.id, pii=pii, password=password)

    try:
        async with async_session() as db:
            user_id = user.id if user else None
            saved = None
            action_word = "Saved"
            if editing_cv_id:
                saved = await update_cv(
                    db,
                    cv_id=editing_cv_id,
                    region=region,
                    template_id=template_id,
                    rendered_html=attempt["rendered_cv"],
                    cv_data=attempt.get("cv_data", {}),
                    label=label,
                    job_title=job_title,
                    self_description=attempt.get("self_description", "") or "",
                    values_text=attempt.get("values", "") or "",
                    offer_appeal=attempt.get("offer_appeal", "") or "",
                    references=(attempt.get("cv_data") or {}).get("references") or None,
                )
                if saved:
                    action_word = "Updated"
                else:
                    # Row is gone (deleted, wrong tenant, or stale attempt
                    # carrying an orphan id). Drop editing_cv_id and persist
                    # as a new CV so the user's work isn't lost.
                    logger.warning(
                        "Save fell back to insert: editing_cv_id=%s missing (attempt=%s)",
                        editing_cv_id,
                        attempt_id,
                    )
                    update_attempt(attempt_id, editing_cv_id=None)
            if not saved:
                saved = await save_cv(
                    db,
                    attempt_id=attempt_id,
                    source="builder",
                    region=region,
                    template_id=template_id,
                    rendered_html=attempt["rendered_cv"],
                    cv_data=attempt.get("cv_data", {}),
                    user_id=user_id,
                    label=label,
                    job_title=job_title,
                    self_description=attempt.get("self_description", "") or "",
                    values_text=attempt.get("values", "") or "",
                    offer_appeal=attempt.get("offer_appeal", "") or "",
                    references=(attempt.get("cv_data") or {}).get("references") or None,
                )
        return Response(
            f'<div class="save-success">{action_word} as "<strong>{label}</strong>"'
            f"{' for ' + job_title if job_title else ''}"
            f' <span class="save-date">{saved.created_at.strftime("%d %b %Y %H:%M")}</span></div>',
            media_type="text/html",
        )
    except Exception:
        logger.exception("Failed to save CV (attempt=%s)", attempt_id)
        return Response(
            '<div class="save-error">Failed to save. Please try again.</div>',
            media_type="text/html",
        )


@router.get("/download-pdf")
async def builder_download_pdf(request: Request):
    """Download the manually built CV as PDF."""
    attempt_id = request.state.session.get("builder_id")
    if not attempt_id:
        return Response("No active session", status_code=400)

    attempt = get_attempt(attempt_id)
    if not attempt or not attempt.get("rendered_cv"):
        return Response("No CV preview found. Please preview first.", status_code=400)

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
async def builder_download_docx(request: Request):
    """Download the manually built CV as DOCX."""
    attempt_id = request.state.session.get("builder_id")
    if not attempt_id:
        return Response("No active session", status_code=400)

    attempt = get_attempt(attempt_id)
    if not attempt or not attempt.get("cv_data"):
        return Response("No CV preview found. Please preview first.", status_code=400)

    cv_data = attempt.get("cv_data", {})
    builder_data = attempt.get("builder_data", {})
    region_code = builder_data.get("region", "AU") or "AU"
    template_id = builder_data.get("template_id", "classic") or "classic"
    cv_name = cv_data.get("name", "CV") or "CV"
    safe_name = "".join(c for c in cv_name if c.isalnum() or c in " -_").strip() or "CV"

    try:
        docx_bytes = generate_docx(cv_data, region_code=region_code, template_id=template_id)
    except Exception:
        logger.exception("DOCX generation failed for builder attempt=%s", attempt_id)
        return Response("DOCX generation failed. Please try again.", status_code=500)

    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name} - QuillCV.docx"',
        },
    )
