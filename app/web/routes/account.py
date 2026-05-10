"""Account management routes: identity, career profile, credits, security, billing."""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse
from sqlalchemy import delete, func, select

from app.billing.entities import TOPUP_PACKS
from app.consent.use_cases.record_consent import get_client_ip, get_user_agent, record_consent
from app.cv_export.adapters.template_registry import REGIONS
from app.identity.adapters.fastapi_deps import require_auth
from app.identity.adapters.token_utils import hash_password, verify_password
from app.infrastructure.persistence.database import async_session
from app.infrastructure.persistence.orm_models import (
    ConsentRecord,
    Credit,
    Payment,
    SavedCV,
    User,
    WebAuthnCredential,
)
from app.web.routes.profile import _profile_dir
from app.web.routes.wizard import _region_fields
from app.web.templates import templates

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/account")
async def account_page(request: Request, user: User = Depends(require_auth)):
    """Main account page — requires authentication."""

    async with async_session() as db:
        # Credits record
        credits_result = await db.execute(
            select(Credit).where(Credit.user_id == user.id)
        )
        credits = credits_result.scalar_one_or_none()

        # Payment history, newest first
        payments_result = await db.execute(
            select(Payment)
            .where(Payment.user_id == user.id)
            .order_by(Payment.created_at.desc())
        )
        payments = payments_result.scalars().all()

        # Saved CV count
        cv_count_result = await db.execute(
            select(func.count())
            .select_from(SavedCV)
            .where(SavedCV.user_id == user.id)
        )
        saved_cv_count = cv_count_result.scalar() or 0

        # Passkeys
        passkeys_result = await db.execute(
            select(WebAuthnCredential).where(WebAuthnCredential.user_id == user.id)
        )
        passkeys = passkeys_result.scalars().all()

        # Most recent prompt-logging consent (only relevant when eligible)
        consent_row = await db.execute(
            select(ConsentRecord)
            .where(
                ConsentRecord.user_id == user.id,
                ConsentRecord.consent_type == "prompt_logging",
            )
            .order_by(ConsentRecord.created_at.desc())
            .limit(1)
        )
        last_prompt_consent = consent_row.scalar_one_or_none()
        prompt_logging_granted = bool(last_prompt_consent and last_prompt_consent.granted)

    # Career profile data (was on /profile — folded into /account).
    pii = request.state.session.get("pii") or {}
    cv_filename: str | None = None
    profile_dir = _profile_dir(user.id)
    if profile_dir.exists():
        for candidate in profile_dir.iterdir():
            if candidate.name.startswith("cv_file"):
                cv_filename = candidate.stem
                break

    return templates.TemplateResponse("account.html", {
        "request": request,
        "credits": credits,
        "payments": payments,
        "passkeys": passkeys,
        "saved_cv_count": saved_cv_count,
        "prompt_logging_eligible": user.prompt_logging_eligible,
        "prompt_logging_granted": prompt_logging_granted,
        # Career-profile data (was the /profile page)
        "pii": pii,
        "regions": list(REGIONS.values()),
        "region_fields": _region_fields(pii.get("region", "")),
        "cv_filename": cv_filename,
    })


@router.get("/account/topup")
async def buy_credits_page(request: Request, user: User = Depends(require_auth)):
    """Top-up picker — render every TOPUP_PACKS entry as a buy-card."""
    async with async_session() as db:
        credits_result = await db.execute(
            select(Credit).where(Credit.user_id == user.id)
        )
        credits = credits_result.scalar_one_or_none()

    # Decorate each pack so the template stays declarative
    packs = []
    for pack_id, pack in TOPUP_PACKS.items():
        packs.append({
            "id": pack_id,
            "credits": pack["credits"],
            "price_cents": pack["price_cents"],
            "price_aud": pack["price_cents"] / 100,
            "per_credit": pack["per_credit"],
            "name": pack["name"],
        })

    # Sort smallest → largest so the layout reads left-to-right
    packs.sort(key=lambda p: p["credits"])

    return templates.TemplateResponse("account_topup.html", {
        "request": request,
        "credits": credits,
        "packs": packs,
    })


@router.post("/account/prompt-logging")
async def update_prompt_logging_consent(
    request: Request,
    granted: str = Form(""),
    user: User = Depends(require_auth),
):
    """HTMX endpoint: opt in or out of prompt logging.

    No-op if the user has not been admin-flagged ``prompt_logging_eligible``
    (the toggle is hidden in the UI in that case, but we double-check here).
    """
    if not user.prompt_logging_eligible:
        return HTMLResponse(
            '<span class="toggle-card__status--off">Not enabled for your account.</span>'
        )

    grant = granted == "on"
    async with async_session() as db:
        await record_consent(
            db,
            consent_type="prompt_logging",
            granted=grant,
            user_id=user.id,
            email=user.email,
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
        )
        await db.commit()

    if grant:
        return HTMLResponse(
            '<span class="toggle-card__status--on">On &mdash; thank you for helping improve QuillCV.</span>'
        )
    return HTMLResponse(
        '<span class="toggle-card__status--off">Off &mdash; no prompts are saved.</span>'
    )


@router.post("/account/update-profile")
async def update_profile(
    request: Request,
    name: str = Form(""),
    user: User = Depends(require_auth),
):
    """HTMX endpoint: update display name."""

    name = name.strip()
    if not name:
        return HTMLResponse('<p class="account-error">Name cannot be empty.</p>')

    async with async_session() as db:
        result = await db.execute(select(User).where(User.id == user.id))
        db_user = result.scalar_one_or_none()
        if db_user:
            db_user.name = name
            await db.commit()

    return HTMLResponse('<p class="account-success">Name updated successfully.</p>')


@router.post("/account/change-password")
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    user: User = Depends(require_auth),
):
    """HTMX endpoint: change password."""

    if not user.password_hash:
        return HTMLResponse('<p class="account-error">No password set on this account.</p>')

    if not verify_password(current_password, user.password_hash):
        return HTMLResponse('<p class="account-error">Current password is incorrect.</p>')

    if len(new_password) < 8:
        return HTMLResponse('<p class="account-error">New password must be at least 8 characters.</p>')

    async with async_session() as db:
        result = await db.execute(select(User).where(User.id == user.id))
        db_user = result.scalar_one_or_none()
        if db_user:
            db_user.password_hash = hash_password(new_password)
            await db.commit()

    return HTMLResponse('<p class="account-success">Password changed successfully.</p>')


@router.post("/account/delete")
async def delete_account(
    request: Request,
    confirm: str = Form(""),
    user: User = Depends(require_auth),
):
    """Delete account and all associated data after explicit confirmation."""

    if confirm.strip() != "DELETE":
        return HTMLResponse('<p class="account-error">Please type DELETE to confirm.</p>')

    user_id = user.id

    async with async_session() as db:
        await db.execute(delete(WebAuthnCredential).where(WebAuthnCredential.user_id == user_id))
        await db.execute(delete(SavedCV).where(SavedCV.user_id == user_id))
        await db.execute(delete(Credit).where(Credit.user_id == user_id))
        await db.execute(delete(Payment).where(Payment.user_id == user_id))
        await db.execute(delete(User).where(User.id == user_id))
        await db.commit()

    # Clear session
    request.state.session.clear()

    return HTMLResponse(
        '<p class="account-success">Account deleted.</p>',
        headers={"HX-Redirect": "/"},
    )


@router.post("/account/career/save")
async def career_save(
    request: Request,
    region: str = Form(""),
    self_description: str = Form(""),
    values: str = Form(""),
    linkedin: str = Form(""),
    github: str = Form(""),
    portfolio: str = Form(""),
    location: str = Form(""),
    cv_file: UploadFile = File(None),
    user: User = Depends(require_auth),
):
    """Save the career-profile section of /account.

    Career-profile fields (region preference, voice, values, links, location,
    base CV, references) live alongside the existing PII vault blob — same
    storage backend, same encryption — but PII fields (full_name, dob,
    document_id, references) are *only* editable via /account/pii. This
    endpoint never touches them.
    """
    pii = request.state.session.get("pii") or {}

    # Reference fields come through as ref_name_1, ref_email_1, ref_phone_1, …
    form = await request.form()
    refs: list[dict] = []
    for idx in (1, 2, 3, 4):
        name = (form.get(f"ref_name_{idx}") or "").strip()
        email = (form.get(f"ref_email_{idx}") or "").strip()
        phone = (form.get(f"ref_phone_{idx}") or "").strip()
        if name or email or phone:
            refs.append({"name": name, "email": email, "phone": phone})

    pii.update({
        "region": region,
        "self_description": self_description,
        "values": values,
        "linkedin": linkedin.strip(),
        "github": github.strip(),
        "portfolio": portfolio.strip(),
        "location": location.strip(),
    })
    if refs:
        pii["references"] = refs

    from app.pii.adapters.vault import upsert_vault
    password = request.state.session.get("_pii_password")
    try:
        async with async_session() as db:
            await upsert_vault(db, user_id=user.id, pii=pii, password=password or None)
        request.state.session["pii"] = pii
    except Exception:
        logger.exception("Failed to upsert career profile for user=%s", user.id)
        return HTMLResponse(
            '<p class="account-error">Couldn\'t save career profile. Please try again.</p>'
        )

    # Optional base CV upload
    cv_saved = False
    if cv_file and cv_file.filename:
        file_bytes = await cv_file.read()
        if file_bytes:
            from app.infrastructure.crypto import encrypt_data
            profile_dir = _profile_dir(user.id)
            ext = Path(cv_file.filename).suffix.lower()
            dest = profile_dir / f"cv_file{ext}.enc"
            try:
                dest.write_text(encrypt_data(file_bytes.hex()))
                cv_saved = True
                logger.info("Saved profile CV for user=%s (%d bytes)", user.id, len(file_bytes))
            except Exception:
                logger.exception("Failed to save profile CV for user=%s", user.id)

    msg = "Career profile saved."
    if cv_saved:
        msg += " Base CV updated."
    return HTMLResponse(f'<p class="account-success">{msg}</p>')
