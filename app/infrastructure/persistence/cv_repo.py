"""Store and retrieve generated CV content as sanitized markdown.

Converts rendered HTML CVs to clean markdown and stores them in the database
alongside the structured cv_data JSON. This allows reusing content without
re-generating via AI, saving API costs.

PII handling:
- Before saving, all text fields are run through PIIRedactor.redact() so that
  real names, emails, phones, DOBs etc. are stored as stable placeholders.
- cv_data_json and markdown are encrypted at rest with the server Fernet key.
- On user retrieval, caller should call restore_cv_pii() to swap tokens back.
- Admin retrieval skips restore — admins see placeholder-only data.
"""

import json
import logging
import re

import markdownify
import nh3
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.crypto import decrypt_data, encrypt_data
from app.infrastructure.persistence.orm_models import SavedCV
from app.pii.use_cases.redact_pii import PIIRedactor

logger = logging.getLogger(__name__)

# nh3 allowlist — strip everything to get pure text structure
_ALLOWED_TAGS = {
    "h1", "h2", "h3", "h4", "h5", "h6",
    "p", "br", "hr",
    "ul", "ol", "li",
    "strong", "em", "b", "i",
    "a", "span", "div",
    "table", "thead", "tbody", "tr", "th", "td",
}
_ALLOWED_ATTRIBUTES: dict[str, set[str]] = {
    "a": {"href"},
}


def html_to_markdown(rendered_html: str) -> str:
    """Convert rendered CV HTML to clean, sanitized markdown.

    1. Strip <style> blocks (CSS from CV templates)
    2. Sanitize HTML with nh3 (remove scripts, event handlers, etc.)
    3. Convert to markdown
    4. Clean up whitespace
    """
    # Remove style blocks before sanitization
    html = re.sub(r'<style[^>]*>.*?</style>', '', rendered_html, flags=re.DOTALL)

    # Sanitize — removes scripts, onclick, onerror, data URIs, etc.
    clean_html = nh3.clean(
        html,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        link_rel="noopener",
        url_schemes={"http", "https", "mailto"},
    )

    # Convert to markdown
    md = markdownify.markdownify(
        clean_html,
        heading_style="ATX",
        bullets="-",
        strip=["img"],
    )

    # Clean up excessive whitespace
    md = re.sub(r'\n{3,}', '\n\n', md)
    md = md.strip()

    return md


def _make_redactor(cv_data: dict) -> PIIRedactor:
    """Build a PIIRedactor from cv_data fields."""
    return PIIRedactor(
        full_name=cv_data.get("full_name") or cv_data.get("name") or "",
        dob=cv_data.get("dob") or "",
        document_id=cv_data.get("document_id") or "",
        references=cv_data.get("references") or [],
        linkedin_url=cv_data.get("linkedin") or "",
        github_url=cv_data.get("github") or "",
    )


def _redact_cv_data(cv_data: dict, redactor: PIIRedactor) -> dict:
    """Return a copy of cv_data with all string values redacted."""
    import copy


    # We need to redact each string value. We reuse _walk_restore with a
    # custom approach: serialise to JSON, redact the JSON text, then parse back.
    raw_json = json.dumps(cv_data, default=str)
    redacted_json = redactor.redact(raw_json)
    try:
        return json.loads(redacted_json)
    except json.JSONDecodeError:
        # Fallback: return original if redaction broke the JSON
        logger.warning("PII redaction produced invalid JSON — storing original (without sensitive data)")
        return copy.deepcopy(cv_data)


async def save_cv(
    db: AsyncSession,
    *,
    attempt_id: str,
    source: str,
    region: str,
    template_id: str,
    rendered_html: str,
    cv_data: dict,
    user_id: str | None = None,
    label: str = "",
    job_title: str = "",
    self_description: str = "",
    values_text: str = "",
    offer_appeal: str = "",
) -> SavedCV:
    """Convert rendered HTML to markdown, redact PII, encrypt, and store."""
    markdown = html_to_markdown(rendered_html)

    # Strip internal metadata from stored JSON
    data_copy = {k: v for k, v in cv_data.items() if not k.startswith("_")}

    # Redact PII from both markdown and structured data before storing
    redactor = _make_redactor(data_copy)
    markdown = redactor.redact(markdown)
    data_copy = _redact_cv_data(data_copy, redactor)

    # Encrypt at rest
    encrypted_json = encrypt_data(json.dumps(data_copy, default=str))
    encrypted_markdown = encrypt_data(markdown)

    saved = SavedCV(
        user_id=user_id,
        attempt_id=attempt_id,
        source=source,
        label=label,
        job_title=job_title,
        region=region,
        template_id=template_id,
        markdown=encrypted_markdown,
        cv_data_json=encrypted_json,
        self_description=self_description or "",
        values_text=values_text or "",
        offer_appeal=offer_appeal or "",
    )
    db.add(saved)
    await db.commit()
    await db.refresh(saved)

    logger.info("Saved CV %s (source=%s, attempt=%s)", saved.id, source, attempt_id)
    return saved


async def update_cv(
    db: AsyncSession,
    *,
    cv_id: str,
    region: str,
    template_id: str,
    rendered_html: str,
    cv_data: dict,
    label: str = "",
    job_title: str = "",
    self_description: str | None = None,
    values_text: str | None = None,
    offer_appeal: str | None = None,
) -> SavedCV | None:
    """Update an existing saved CV — redacts PII and re-encrypts."""
    result = await db.execute(select(SavedCV).where(SavedCV.id == cv_id))
    saved = result.scalar_one_or_none()
    if not saved:
        return None

    markdown = html_to_markdown(rendered_html)
    data_copy = {k: v for k, v in cv_data.items() if not k.startswith("_")}

    # Redact PII before storing
    redactor = _make_redactor(data_copy)
    markdown = redactor.redact(markdown)
    data_copy = _redact_cv_data(data_copy, redactor)

    saved.region = region
    saved.template_id = template_id
    saved.markdown = encrypt_data(markdown)
    saved.cv_data_json = encrypt_data(json.dumps(data_copy, default=str))
    if label:
        saved.label = label
    if job_title:
        saved.job_title = job_title
    # Voice fields: only overwrite when the caller explicitly passed a value.
    if self_description is not None:
        saved.self_description = self_description
    if values_text is not None:
        saved.values_text = values_text
    if offer_appeal is not None:
        saved.offer_appeal = offer_appeal

    await db.commit()
    await db.refresh(saved)
    logger.info("Updated CV %s", saved.id)
    return saved


def decrypt_saved_cv(saved: SavedCV) -> SavedCV:
    """Decrypt the encrypted fields on a SavedCV in-place.

    Call this before returning a SavedCV to the application layer.
    Does nothing if the field is not a Fernet token (backwards-compat with
    rows written before encryption was enabled).
    """
    from cryptography.fernet import InvalidToken

    def _safe_decrypt(value: str) -> str:
        try:
            return decrypt_data(value)
        except (InvalidToken, Exception):
            return value  # Not encrypted (legacy row) — return as-is

    saved.cv_data_json = _safe_decrypt(saved.cv_data_json)
    saved.markdown = _safe_decrypt(saved.markdown)
    return saved


def restore_cv_pii(saved: SavedCV, pii: dict) -> SavedCV:
    """Swap PII placeholders back to real values in a (decrypted) SavedCV.

    ``pii`` is the dict stored in ``request.session["pii"]``.
    Mutates the SavedCV object's fields in-place and returns it.
    Admin callers should NOT call this — they should see placeholders.
    """
    if not pii:
        return saved

    redactor = PIIRedactor(
        full_name=pii.get("full_name", ""),
        dob=pii.get("dob", ""),
        document_id=pii.get("document_id", ""),
        references=pii.get("references", []),
        linkedin_url=pii.get("linkedin", ""),
        github_url=pii.get("github", ""),
    )
    # Prime email/phone lists from pii so restore map is populated
    if pii.get("email"):
        redactor._emails = [pii["email"]]
    if pii.get("phone"):
        redactor._phones = [pii["phone"]]

    # Restore cv_data_json
    try:
        cv_data = json.loads(saved.cv_data_json)
        cv_data = redactor.restore(cv_data)
        saved.cv_data_json = json.dumps(cv_data, default=str)
    except (json.JSONDecodeError, Exception):
        logger.debug("Failed to restore PII in cv_data_json for saved CV")

    # Restore markdown
    replacement_map = redactor._build_replacement_map()
    from app.pii.use_cases.redact_pii import _walk_restore
    saved.markdown = _walk_restore(saved.markdown, replacement_map)

    return saved


async def get_saved_cv(
    db: AsyncSession,
    saved_cv_id: str,
    *,
    pii: dict | None = None,
) -> SavedCV | None:
    """Retrieve a saved CV by ID, decrypt it, and optionally restore PII.

    ``pii``: pass ``request.session.get("pii")`` for user requests.
             Omit (or pass None) for admin requests — placeholders remain.
    """
    result = await db.execute(select(SavedCV).where(SavedCV.id == saved_cv_id))
    saved = result.scalar_one_or_none()
    if not saved:
        return None

    saved = decrypt_saved_cv(saved)
    if pii:
        saved = restore_cv_pii(saved, pii)
    return saved


async def list_saved_cvs(
    db: AsyncSession,
    user_id: str | None = None,
    attempt_id: str | None = None,
    *,
    pii: dict | None = None,
) -> list[SavedCV]:
    """List saved CVs, optionally filtered by user or attempt.

    ``pii``: pass ``request.session.get("pii")`` for user requests.
             Omit for admin requests.
    """
    query = select(SavedCV).order_by(SavedCV.created_at.desc())
    if user_id:
        query = query.where(SavedCV.user_id == user_id)
    if attempt_id:
        query = query.where(SavedCV.attempt_id == attempt_id)
    result = await db.execute(query)
    cvs = list(result.scalars().all())

    for cv in cvs:
        decrypt_saved_cv(cv)
        if pii:
            restore_cv_pii(cv, pii)

    return cvs
