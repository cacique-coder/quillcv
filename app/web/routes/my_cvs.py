"""My CVs — list and manage saved CVs."""

import json
import logging
import re

from fastapi import APIRouter, Request
from fastapi.responses import Response

from app.cv_export.adapters.docx_export import generate_docx
from app.cv_export.adapters.puppeteer_pdf import generate_pdf
from app.infrastructure.persistence.cv_repo import get_saved_cv, list_saved_cvs
from app.infrastructure.persistence.database import async_session
from app.web.templates import templates

logger = logging.getLogger(__name__)

router = APIRouter()

# Tokens that survive into rendered HTML when the PII vault is missing values.
# Matches both fixed (e.g. <<DOB>>) and indexed (e.g. <<EMAIL_1>>) placeholders.
_PII_TOKEN_RE = re.compile(r"<<[A-Z][A-Z0-9_]*>>")

_TOKEN_LABELS = {
    "CANDIDATE_NAME": "name",
    "CANDIDATE_SLUG": "name",
    "EMAIL": "email",
    "PHONE": "phone",
    "DOB": "date of birth",
    "DOCUMENT_ID": "document ID",
    "LINKEDIN_URL": "LinkedIn URL",
    "GITHUB_URL": "GitHub URL",
    "PORTFOLIO_URL": "portfolio URL",
    "REF_NAME": "reference name",
    "REF_EMAIL": "reference email",
    "REF_PHONE": "reference phone",
}

# Sentinel strings seeded by STARTER_BUILDER_DATA (see app/web/routes/builder.py).
# Their presence in a saved CV means the user kept the demo copy without
# personalising it — same UX problem as an unfilled vault.
_STARTER_SENTINELS = {
    "Your job title": "job title",
    "City, Country": "location",
    "Company name": "employer",
    "University name": "school",
    "Two to four sentences highlighting": "summary",
}


def _detect_missing_fields(rendered: str, cv_data: dict | None = None) -> list[str]:
    """Collect human-readable labels for unresolved tokens, starter sentinels,
    and empty contact fields. Empty list means the CV looks fully personalised."""
    seen: list[str] = []

    for token in _PII_TOKEN_RE.findall(rendered):
        # Strip "<<", ">>" and trailing index ("EMAIL_1" -> "EMAIL")
        inner = token[2:-2]
        key = inner.rsplit("_", 1)[0] if inner.rsplit("_", 1)[-1].isdigit() else inner
        label = _TOKEN_LABELS.get(key, key.replace("_", " ").lower())
        if label not in seen:
            seen.append(label)

    for needle, label in _STARTER_SENTINELS.items():
        if needle in rendered and label not in seen:
            seen.append(label)

    if cv_data:
        for key, label in (("name", "name"), ("email", "email"), ("phone", "phone")):
            if not (cv_data.get(key) or "").strip() and label not in seen:
                seen.append(label)

    return seen


def _missing_token_banner(rendered: str, cv_data: dict | None = None, cv_id: str = "") -> str:
    """Return an HTML banner if any PII placeholders or starter sentinels survive.

    Empty string when the CV looks fully personalised.
    """
    seen = _detect_missing_fields(rendered, cv_data)
    if not seen:
        return ""

    fields = ", ".join(seen)
    edit_link = (
        f'or <a href="/builder/edit/{cv_id}" style="color:#7c2d12;'
        'text-decoration:underline;font-weight:600;">re-edit the CV</a> '
        if cv_id
        else ""
    )
    return (
        '<div style="max-width:800px;margin:1rem auto;padding:0.85rem 1rem;'
        "background:#fff7ed;border:1px solid #fdba74;border-radius:6px;"
        "color:#7c2d12;font-family:system-ui,-apple-system,Segoe UI,sans-serif;"
        'font-size:0.9rem;line-height:1.5;">'
        "<strong>Some values are missing.</strong> "
        f"Unfilled or placeholder fields: <em>{fields}</em>. "
        'Update your <a href="/account/pii" style="color:#7c2d12;'
        'text-decoration:underline;font-weight:600;">profile vault</a> '
        f"{edit_link}"
        "to fill them in."
        "</div>"
    )


@router.get("/my-cvs")
async def my_cvs_page(request: Request):
    """List all saved CVs for the current user/session."""
    user = request.state.user if hasattr(request.state, "user") else None
    user_id = user.id if user else None

    # Also check for anonymous CVs tied to builder/wizard sessions
    attempt_ids = []
    if builder_id := request.state.session.get("builder_id"):
        attempt_ids.append(builder_id)
    if wizard_id := request.state.session.get("attempt_id"):
        attempt_ids.append(wizard_id)

    pii = request.state.session.get("pii") or {}
    async with async_session() as db:
        cvs = []
        if user_id:
            cvs = await list_saved_cvs(db, user_id=user_id, pii=pii)
        # Also fetch session-based CVs (anonymous users)
        for aid in attempt_ids:
            session_cvs = await list_saved_cvs(db, attempt_id=aid, pii=pii)
            existing_ids = {c.id for c in cvs}
            for cv in session_cvs:
                if cv.id not in existing_ids:
                    cvs.append(cv)

        # Sort by created_at descending
        cvs.sort(key=lambda c: c.created_at, reverse=True)

    # Flag any CV that still carries unresolved tokens, starter sentinels,
    # or an empty contact triple — surfaced as a card badge in the template.
    cv_status: dict[str, list[str]] = {}
    for cv in cvs:
        try:
            data = json.loads(cv.cv_data_json) if cv.cv_data_json else {}
        except (json.JSONDecodeError, TypeError):
            data = {}
        # Use cv_data_json itself as the "rendered" haystack — it carries the
        # same starter strings and tokens we want to detect, without paying
        # for a full template render per card.
        haystack = cv.cv_data_json or ""
        missing = _detect_missing_fields(haystack, data)
        if missing:
            cv_status[cv.id] = missing

    return templates.TemplateResponse(
        "my_cvs.html",
        {
            "request": request,
            "saved_cvs": cvs,
            "cv_status": cv_status,
        },
    )


@router.get("/my-cvs/{cv_id}/preview")
async def my_cv_preview(request: Request, cv_id: str):
    """Return rendered CV HTML for preview."""
    pii = request.state.session.get("pii") or {}
    async with async_session() as db:
        saved = await get_saved_cv(db, cv_id, pii=pii)

    if not saved:
        return Response("CV not found", status_code=404)

    cv_data = json.loads(saved.cv_data_json)
    # Fallback: replace any leftover PII tokens with vault values
    if pii:
        candidate_slug = (pii.get("full_name") or "").lower().replace(" ", "-")
        token_replacements = {
            "<<CANDIDATE_NAME>>": pii.get("full_name", ""),
            "<<EMAIL_1>>": pii.get("email", ""),
            "<<PHONE_1>>": pii.get("phone", ""),
            "<<DOB>>": pii.get("dob", ""),
            "<<DOCUMENT_ID>>": pii.get("document_id", ""),
            "<<LINKEDIN_URL>>": pii.get("linkedin", ""),
            "<<GITHUB_URL>>": pii.get("github", ""),
            "<<PORTFOLIO_URL>>": pii.get("portfolio", ""),
            "<<CANDIDATE_SLUG>>": candidate_slug,
        }
        raw = json.dumps(cv_data)
        for token, real_val in token_replacements.items():
            if real_val:
                raw = raw.replace(token, real_val)
        cv_data = json.loads(raw)

    rendered = templates.get_template(f"cv_templates/{saved.template_id}.html").render(**cv_data)

    banner = _missing_token_banner(rendered, cv_data=cv_data, cv_id=cv_id)
    return Response(banner + rendered, media_type="text/html")


@router.get("/my-cvs/{cv_id}/download")
async def my_cv_download(request: Request, cv_id: str):
    """Download a saved CV as PDF."""
    pii = request.state.session.get("pii") or {}
    async with async_session() as db:
        saved = await get_saved_cv(db, cv_id, pii=pii)

    if not saved:
        return Response("CV not found", status_code=404)

    cv_data = json.loads(saved.cv_data_json)
    # Fallback: replace any leftover PII tokens with vault values
    if pii:
        candidate_slug = (pii.get("full_name") or "").lower().replace(" ", "-")
        token_replacements = {
            "<<CANDIDATE_NAME>>": pii.get("full_name", ""),
            "<<EMAIL_1>>": pii.get("email", ""),
            "<<PHONE_1>>": pii.get("phone", ""),
            "<<DOB>>": pii.get("dob", ""),
            "<<DOCUMENT_ID>>": pii.get("document_id", ""),
            "<<LINKEDIN_URL>>": pii.get("linkedin", ""),
            "<<GITHUB_URL>>": pii.get("github", ""),
            "<<PORTFOLIO_URL>>": pii.get("portfolio", ""),
            "<<CANDIDATE_SLUG>>": candidate_slug,
        }
        raw = json.dumps(cv_data)
        for token, real_val in token_replacements.items():
            if real_val:
                raw = raw.replace(token, real_val)
        cv_data = json.loads(raw)

    rendered = templates.get_template(f"cv_templates/{saved.template_id}.html").render(**cv_data)

    cv_name = cv_data.get("name", "CV") or "CV"
    safe_name = "".join(c for c in cv_name if c.isalnum() or c in " -_").strip() or "CV"
    label_part = f" - {saved.label}" if saved.label else ""

    pdf_bytes = await generate_pdf(rendered)
    if pdf_bytes is None:
        return Response("PDF generation failed", status_code=500)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}{label_part} - QuillCV.pdf"',
        },
    )


@router.get("/my-cvs/{cv_id}/download-docx")
async def my_cv_download_docx(request: Request, cv_id: str):
    """Download a saved CV as DOCX."""
    pii = request.state.session.get("pii") or {}
    async with async_session() as db:
        saved = await get_saved_cv(db, cv_id, pii=pii)

    if not saved:
        return Response("CV not found", status_code=404)

    cv_data = json.loads(saved.cv_data_json)
    # Fallback: replace any leftover PII tokens with vault values
    if pii:
        candidate_slug = (pii.get("full_name") or "").lower().replace(" ", "-")
        token_replacements = {
            "<<CANDIDATE_NAME>>": pii.get("full_name", ""),
            "<<EMAIL_1>>": pii.get("email", ""),
            "<<PHONE_1>>": pii.get("phone", ""),
            "<<DOB>>": pii.get("dob", ""),
            "<<DOCUMENT_ID>>": pii.get("document_id", ""),
            "<<LINKEDIN_URL>>": pii.get("linkedin", ""),
            "<<GITHUB_URL>>": pii.get("github", ""),
            "<<PORTFOLIO_URL>>": pii.get("portfolio", ""),
            "<<CANDIDATE_SLUG>>": candidate_slug,
        }
        raw = json.dumps(cv_data)
        for token, real_val in token_replacements.items():
            if real_val:
                raw = raw.replace(token, real_val)
        cv_data = json.loads(raw)

    region_code = saved.region or "AU"
    template_id = saved.template_id or "classic"
    cv_name = cv_data.get("name", "CV") or "CV"
    safe_name = "".join(c for c in cv_name if c.isalnum() or c in " -_").strip() or "CV"
    label_part = f" - {saved.label}" if saved.label else ""

    try:
        docx_bytes = generate_docx(cv_data, region_code=region_code, template_id=template_id)
    except Exception:
        logger.exception("DOCX generation failed for cv_id=%s", cv_id)
        return Response("DOCX generation failed", status_code=500)

    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}{label_part} - QuillCV.docx"',
        },
    )
