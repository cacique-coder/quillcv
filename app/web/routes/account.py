"""Account management routes: profile, credits, security, billing, danger zone."""

import logging

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import delete, func, select

from app.identity.adapters.fastapi_deps import require_auth
from app.identity.adapters.token_utils import hash_password, verify_password
from app.infrastructure.persistence.database import async_session
from app.infrastructure.persistence.orm_models import Credit, Payment, SavedCV, User, WebAuthnCredential
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

    return templates.TemplateResponse("account.html", {
        "request": request,
        "credits": credits,
        "payments": payments,
        "passkeys": passkeys,
        "saved_cv_count": saved_cv_count,
    })


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
