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


def _missing_token_banner(rendered: str) -> str:
    """Return an HTML banner if any PII placeholders are unresolved.

    Empty string when the CV is fully populated.
    """
    matches = _PII_TOKEN_RE.findall(rendered)
    if not matches:
        return ""

    seen: list[str] = []
    for token in matches:
        # Strip "<<", ">>" and trailing index ("EMAIL_1" -> "EMAIL")
        key = token[2:-2].rsplit("_", 1)[0] if token[2:-2].rsplit("_", 1)[-1].isdigit() else token[2:-2]
        label = _TOKEN_LABELS.get(key, key.replace("_", " ").lower())
        if label not in seen:
            seen.append(label)

    fields = ", ".join(seen)
    return (
        '<div style="max-width:800px;margin:1rem auto;padding:0.85rem 1rem;'
        "background:#fff7ed;border:1px solid #fdba74;border-radius:6px;"
        "color:#7c2d12;font-family:system-ui,-apple-system,Segoe UI,sans-serif;"
        'font-size:0.9rem;line-height:1.5;">'
        "<strong>Some values are missing.</strong> "
        f"The placeholders below are unresolved: <em>{fields}</em>. "
        'Update your <a href="/account/pii" style="color:#7c2d12;'
        'text-decoration:underline;font-weight:600;">profile vault</a> '
        "and reopen this preview to fill them in."
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

    async with async_session() as db:
        cvs = []
        if user_id:
            cvs = await list_saved_cvs(db, user_id=user_id)
        # Also fetch session-based CVs (anonymous users)
        for aid in attempt_ids:
            session_cvs = await list_saved_cvs(db, attempt_id=aid)
            existing_ids = {c.id for c in cvs}
            for cv in session_cvs:
                if cv.id not in existing_ids:
                    cvs.append(cv)

        # Sort by created_at descending
        cvs.sort(key=lambda c: c.created_at, reverse=True)

    return templates.TemplateResponse(
        "my_cvs.html",
        {
            "request": request,
            "saved_cvs": cvs,
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

    banner = _missing_token_banner(rendered)
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
