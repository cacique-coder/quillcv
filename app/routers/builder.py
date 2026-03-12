"""Manual CV builder — free, no AI, no credits required.

Users fill in their CV data via a form and get it rendered through
the same professional templates used by the AI generator.
"""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates

from app.database import async_session
from app.services.attempt_store import create_attempt, get_attempt, update_attempt
from app.services.cv_store import get_saved_cv, save_cv, update_cv
from app.services.pdf_generator import generate_pdf
from app.services.template_registry import REGIONS, TEMPLATES, list_regions, list_templates

logger = logging.getLogger(__name__)


def _region_fields_map() -> dict[str, dict]:
    """Build a map of region code -> conditional field flags for all regions."""
    result = {}
    for code, r in REGIONS.items():
        result[code] = {
            "photo": r.include_photo in ("required", "common", "optional"),
            "photo_level": r.include_photo,
            "references": r.include_references,
            "visa": r.include_visa_status,
            "dob": r.include_dob,
            "nationality": r.include_nationality,
            "marital": r.include_marital_status,
        }
    return result

router = APIRouter(prefix="/builder")
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


def _get_or_create_builder(request: Request) -> dict:
    """Get or create a builder attempt (separate from the AI wizard)."""
    attempt_id = request.session.get("builder_id")
    if attempt_id:
        attempt = get_attempt(attempt_id)
        if attempt:
            return attempt
    attempt_id = create_attempt()
    request.session["builder_id"] = attempt_id
    return get_attempt(attempt_id)


def _cv_data_from_attempt(attempt: dict) -> dict:
    """Build the cv_data dict from stored builder fields."""
    data = attempt.get("builder_data", {})
    return {
        "name": data.get("name", ""),
        "title": data.get("title", ""),
        "email": data.get("email", ""),
        "phone": data.get("phone", ""),
        "location": data.get("location", ""),
        "linkedin": data.get("linkedin", ""),
        "github": data.get("github", ""),
        "portfolio": data.get("portfolio", ""),
        "summary": data.get("summary", ""),
        "experience": data.get("experience", []),
        "skills": data.get("skills", []),
        "skills_grouped": data.get("skills_grouped", []),
        "education": data.get("education", []),
        "certifications": data.get("certifications", []),
        "projects": data.get("projects", []),
        "references": data.get("references", []),
        "languages": data.get("languages", []),
        # Region-specific fields
        "dob": data.get("dob", ""),
        "nationality": data.get("nationality", ""),
        "marital_status": data.get("marital_status", ""),
        "visa_status": data.get("visa_status", ""),
        "region": data.get("region", ""),
        "photo_url": data.get("photo_url", ""),
    }


def _parse_form_experience(form) -> list[dict]:
    """Parse dynamic experience entries from form data."""
    experiences = []
    i = 0
    while True:
        title = form.get(f"exp_title_{i}", "").strip()
        if not title and i > 0:
            break
        if title:
            bullets_raw = form.get(f"exp_bullets_{i}", "")
            bullets = [b.strip() for b in bullets_raw.split("\n") if b.strip()]
            experiences.append({
                "title": title,
                "company": form.get(f"exp_company_{i}", "").strip(),
                "location": form.get(f"exp_location_{i}", "").strip(),
                "date": form.get(f"exp_date_{i}", "").strip(),
                "tech": form.get(f"exp_tech_{i}", "").strip(),
                "bullets": bullets,
            })
        i += 1
        if i > 20:  # safety limit
            break
    return experiences


def _parse_form_education(form) -> list[dict]:
    """Parse dynamic education entries from form data."""
    entries = []
    i = 0
    while True:
        degree = form.get(f"edu_degree_{i}", "").strip()
        if not degree and i > 0:
            break
        if degree:
            entries.append({
                "degree": degree,
                "institution": form.get(f"edu_institution_{i}", "").strip(),
                "date": form.get(f"edu_date_{i}", "").strip(),
            })
        i += 1
        if i > 10:
            break
    return entries


def _parse_form_references(form) -> list[dict]:
    """Parse reference entries from form data."""
    refs = []
    i = 0
    while True:
        name = form.get(f"ref_name_{i}", "").strip()
        if not name and i > 0:
            break
        if name:
            refs.append({
                "name": name,
                "title": form.get(f"ref_title_{i}", "").strip(),
                "company": form.get(f"ref_company_{i}", "").strip(),
                "contact": form.get(f"ref_contact_{i}", "").strip(),
            })
        i += 1
        if i > 5:
            break
    return refs


@router.get("")
async def builder_page(request: Request):
    """Main builder page with the form."""
    attempt = _get_or_create_builder(request)
    cv_data = _cv_data_from_attempt(attempt)
    region = attempt.get("builder_data", {}).get("region", "US")
    template_id = attempt.get("builder_data", {}).get("template_id", "modern")

    template_options = [(t.id, t.name) for t in list_templates()]
    region_options = [(r.code, f"{r.flag} {r.name}") for r in list_regions()]
    region_fields = _region_fields_map()

    return templates.TemplateResponse("builder.html", {
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
    })


@router.get("/edit/{cv_id}")
async def builder_edit(cv_id: str, request: Request):
    """Load a saved CV into the builder for editing."""
    async with async_session() as db:
        saved = await get_saved_cv(db, cv_id)

    if not saved:
        from fastapi.responses import RedirectResponse
        return RedirectResponse("/my-cvs", status_code=303)

    # Parse the stored cv_data_json back into builder_data
    stored_data: dict = {}
    if saved.cv_data_json:
        try:
            stored_data = json.loads(saved.cv_data_json)
        except Exception:
            logger.warning("Failed to parse cv_data_json for CV %s", cv_id)

    # Merge stored data with template/region from the SavedCV columns
    builder_data = {**stored_data, "template_id": saved.template_id, "region": saved.region}

    # Create a fresh builder attempt for this edit session
    attempt_id = create_attempt()
    request.session["builder_id"] = attempt_id
    update_attempt(attempt_id, builder_data=builder_data, editing_cv_id=cv_id)

    cv_data = _cv_data_from_attempt({"builder_data": builder_data})
    region = saved.region
    template_id = saved.template_id

    template_options = [(t.id, t.name) for t in list_templates()]
    region_options = [(r.code, f"{r.flag} {r.name}") for r in list_regions()]
    region_fields = _region_fields_map()

    return templates.TemplateResponse("builder.html", {
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
    })


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

    # Parse all fields
    template_id = form.get("template_id", "modern").strip()
    region = form.get("region", "US").strip()

    # Guard: if nothing meaningful is filled in yet, return a friendly nudge
    # rather than rendering an empty CV template.
    _has_content = any(
        form.get(f, "").strip()
        for f in ("name", "title", "summary", "exp_title_0", "edu_degree_0", "skills")
    )
    if not _has_content:
        return Response(
            '<div class="builder-preview-empty" style="padding:2.5rem 1rem;text-align:center;">'
            '<p style="color:var(--text-muted);font-size:0.9rem;">Start filling in your details and the preview will appear here automatically.</p>'
            '</div>',
            media_type="text/html",
        )

    skills_raw = form.get("skills", "")
    skills = [s.strip() for s in skills_raw.split(",") if s.strip()]

    certs_raw = form.get("certifications", "")
    certifications = [c.strip() for c in certs_raw.split("\n") if c.strip()]

    languages_raw = form.get("languages", "")
    languages = [lang.strip() for lang in languages_raw.split(",") if lang.strip()]

    # Photo URL from hidden field (set by photo upload partial)
    photo_path = form.get("photo_path", "").strip()
    photo_url = f"/photos/serve/{photo_path}" if photo_path else ""

    builder_data = {
        "name": form.get("name", "").strip(),
        "title": form.get("title", "").strip(),
        "email": form.get("email", "").strip(),
        "phone": form.get("phone", "").strip(),
        "location": form.get("location", "").strip(),
        "linkedin": form.get("linkedin", "").strip(),
        "github": form.get("github", "").strip(),
        "portfolio": form.get("portfolio", "").strip(),
        "summary": form.get("summary", "").strip(),
        "experience": _parse_form_experience(form),
        "skills": skills,
        "education": _parse_form_education(form),
        "certifications": certifications,
        "references": _parse_form_references(form),
        "languages": languages,
        "dob": form.get("dob", "").strip(),
        "nationality": form.get("nationality", "").strip(),
        "marital_status": form.get("marital_status", "").strip(),
        "visa_status": form.get("visa_status", "").strip(),
        "photo_url": photo_url,
        "region": region,
        "template_id": template_id,
    }

    # Save to attempt store — preserve editing_cv_id if present
    editing_cv_id = attempt.get("editing_cv_id")
    extra = {"editing_cv_id": editing_cv_id} if editing_cv_id else {}
    update_attempt(attempt["id"], builder_data=builder_data, **extra)

    # Render CV with selected template
    cv_data = _cv_data_from_attempt({"builder_data": builder_data})
    rendered_cv = templates.get_template(
        f"cv_templates/{template_id}.html"
    ).render(**cv_data)

    # Cache for PDF download
    update_attempt(attempt["id"], rendered_cv=rendered_cv, cv_data=cv_data)

    # Persist CV as sanitized markdown for reuse
    try:
        async with async_session() as db:
            await save_cv(
                db,
                attempt_id=attempt["id"],
                source="builder",
                region=region,
                template_id=template_id,
                rendered_html=rendered_cv,
                cv_data=cv_data,
            )
    except Exception:
        logger.exception("Failed to save builder CV (attempt=%s)", attempt["id"])

    return templates.TemplateResponse("partials/builder_preview.html", {
        "request": request,
        "generated_cv": rendered_cv,
        "template_name": (TEMPLATES.get(template_id) or TEMPLATES["modern"]).name,
        "region": region,
    })


@router.post("/save")
async def builder_save(request: Request):
    """Save the current CV with a user-chosen name."""
    attempt_id = request.session.get("builder_id")
    if not attempt_id:
        return Response('<div class="save-error">No active session.</div>', media_type="text/html")

    attempt = get_attempt(attempt_id)
    if not attempt or not attempt.get("rendered_cv"):
        return Response('<div class="save-error">Preview your CV first before saving.</div>', media_type="text/html")

    form = await request.form()
    label = form.get("save_label", "").strip()[:255]
    job_title = form.get("save_job_title", "").strip()[:255]

    if not label:
        # Default label from CV name + template
        cv_name = attempt.get("cv_data", {}).get("name", "")
        tpl_id = attempt.get("builder_data", {}).get("template_id", "modern")
        label = f"{cv_name} — {tpl_id.title()}" if cv_name else f"CV — {tpl_id.title()}"

    builder_data = attempt.get("builder_data", {})
    editing_cv_id = attempt.get("editing_cv_id")
    region = builder_data.get("region", "US")
    template_id = builder_data.get("template_id", "modern")

    try:
        async with async_session() as db:
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
                )
                if not saved:
                    return Response(
                        '<div class="save-error">CV not found. It may have been deleted.</div>',
                        media_type="text/html",
                    )
                action_word = "Updated"
            else:
                saved = await save_cv(
                    db,
                    attempt_id=attempt_id,
                    source="builder",
                    region=region,
                    template_id=template_id,
                    rendered_html=attempt["rendered_cv"],
                    cv_data=attempt.get("cv_data", {}),
                    label=label,
                    job_title=job_title,
                )
                action_word = "Saved"
        return Response(
            f'<div class="save-success">{action_word} as "<strong>{label}</strong>"'
            f'{" for " + job_title if job_title else ""}'
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
    attempt_id = request.session.get("builder_id")
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
