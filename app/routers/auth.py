"""Auth routes: sign up, sign in, sign out, OAuth callbacks, password reset."""

import hashlib
import logging
import os
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.auth.dependencies import get_current_user
from app.auth.utils import create_access_token, hash_password
from app.database import async_session
from app.models import ConsentRecord, ExpressionOfInterest, Invitation, PasswordResetToken, User
from app.services.credit_service import add_credits, get_balance
from app.services.email_service import send_password_reset_email, send_welcome_email
from app.services.pii_vault import (
    pii_from_user,
    unlock_vault,
    unlock_vault_server_key,
    upsert_vault,
)
from app.services.user_service import (
    authenticate_user,
    create_user,
    get_user_by_email,
    get_user_by_provider,
    update_last_login,
)

PASSWORD_RESET_TTL_MINUTES = 60

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")

# OAuth config (optional — works without these)
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")


@router.get("/signup")
async def signup_page(request: Request, invite: str | None = None):
    user = await get_current_user(request)
    if user:
        return RedirectResponse("/app", status_code=303)

    # If an invite code is provided, look it up and show the real signup form.
    invitation = None
    invite_error = None
    if invite:
        async with async_session() as db:
            result = await db.execute(
                select(Invitation).where(Invitation.code == invite)
            )
            invitation = result.scalar_one_or_none()

        if not invitation:
            invite_error = "This invitation link is invalid."
            invitation = None
        elif invitation.redeemed_by:
            invite_error = "This invitation has already been claimed."
            invitation = None

    return templates.TemplateResponse("auth/signup.html", {
        "request": request,
        "invitation": invitation,
        "invite_error": invite_error,
    })


@router.post("/signup")
async def signup_submit(
    request: Request,
    email: str = Form(...),
    name: str = Form(""),
    password: str = Form(""),
    confirm_password: str = Form(""),
    invite_code: str = Form(""),
    age_confirmed: str = Form(""),
):
    """Handle signup — either an Expression of Interest or a real account creation.

    When ``invite_code`` is present the handler creates a real user account,
    redeems the invitation, seeds the PII vault, and logs the user in.

    Without an invite code the handler records an Expression of Interest only.
    """
    # ── Invited signup — real account creation ────────────────────────────
    if invite_code:
        errors = []
        normalized_email = email.lower().strip()

        # Validate invite code
        async with async_session() as db:
            result = await db.execute(
                select(Invitation).where(Invitation.code == invite_code)
            )
            invitation = result.scalar_one_or_none()

        if not invitation:
            errors.append("This invitation link is invalid.")
        elif invitation.redeemed_by:
            errors.append("This invitation has already been claimed.")
        elif invitation.email and invitation.email.lower() != normalized_email:
            errors.append("This invitation is for a different email address.")

        # Validate age confirmation
        if not age_confirmed:
            errors.append("You must confirm that you are 18 years of age or older.")

        # Validate password
        if len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        elif password != confirm_password:
            errors.append("Passwords do not match.")

        # Validate email uniqueness (only if invite is still valid — avoids leaking info)
        existing_user = None
        if not errors:
            async with async_session() as db:
                existing_user = await get_user_by_email(db, normalized_email)
            if existing_user:
                errors.append("An account with this email already exists. Try signing in.")

        if errors:
            # Re-fetch invitation for the template (it may still be valid for display)
            async with async_session() as db:
                result = await db.execute(
                    select(Invitation).where(Invitation.code == invite_code)
                )
                inv_for_template = result.scalar_one_or_none()
                # Only pass to template if not yet redeemed
                if inv_for_template and inv_for_template.redeemed_by:
                    inv_for_template = None
            return templates.TemplateResponse("auth/signup.html", {
                "request": request,
                "errors": errors,
                "invitation": inv_for_template,
                "email_value": email,
                "name_value": name,
            })

        # Create the user account
        async with async_session() as db:
            new_user = await create_user(db, email=normalized_email, password=password, name=name.strip())

        # Redeem the invitation and grant credits
        async with async_session() as db:
            result = await db.execute(
                select(Invitation).where(Invitation.code == invite_code)
            )
            invitation = result.scalar_one_or_none()
            if invitation and not invitation.redeemed_by:
                invitation.redeemed_by = new_user.id
                invitation.redeemed_at = datetime.now(UTC)
                await db.commit()
                await add_credits(db, new_user.id, invitation.credits)

        # Record age confirmation consent
        async with async_session() as db:
            consent = ConsentRecord(
                user_id=new_user.id,
                consent_type="age_verification",
                granted=True,
                email=normalized_email,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent", "")[:512],
                policy_version=datetime.now(UTC).strftime("%Y-%m-%d"),
            )
            db.add(consent)
            # Also record terms acceptance
            terms = ConsentRecord(
                user_id=new_user.id,
                consent_type="terms_acceptance",
                granted=True,
                email=normalized_email,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent", "")[:512],
                policy_version=datetime.now(UTC).strftime("%Y-%m-%d"),
            )
            db.add(terms)
            await db.commit()

        # Set age_confirmed_at on the user record
        async with async_session() as db:
            result = await db.execute(select(User).where(User.id == new_user.id))
            u = result.scalar_one_or_none()
            if u:
                u.age_confirmed_at = datetime.now(UTC)
                await db.commit()

        # Log the user in
        token = create_access_token(new_user.id, new_user.email)
        request.state.session["auth_token"] = token

        # Seed the PII vault with password-derived encryption
        async with async_session() as db:
            pii = pii_from_user(new_user)
            await upsert_vault(db, user_id=new_user.id, pii=pii, password=password)

        request.state.session["pii"] = pii
        request.state.session["_pii_password"] = password
        request.state.session["pii_onboarded"] = False  # New user — needs onboarding

        # Seed credit balance in session so the nav bar reflects the granted credits
        # without an extra DB hit on every request.
        async with async_session() as db:
            request.state.session["cached_balance"] = await get_balance(db, new_user.id)

        logger.info("Invited signup: user %s created via invitation %s", new_user.id, invite_code)

        from app.instrumentation import record_custom_event
        record_custom_event("UserSignup", {
            "user_id": new_user.id,
            "method": "invitation",
        })

        # Send welcome email — fire-and-forget (failure is non-fatal)
        try:
            base_url = str(request.base_url).rstrip("/")
            await send_welcome_email(to_email=new_user.email, name=new_user.name)
        except Exception:
            logger.exception("Failed to send welcome email to %s", new_user.email)

        return RedirectResponse("/onboarding", status_code=303)

    # ── Expression of Interest (no invite code) ────────────────────────────
    async with async_session() as db:
        existing = await db.scalar(
            select(ExpressionOfInterest).where(ExpressionOfInterest.email == email.lower().strip())
        )
        if not existing:
            eoi = ExpressionOfInterest(
                email=email.lower().strip(),
                name=name.strip(),
                source="signup",
            )
            db.add(eoi)
            await db.commit()

    return templates.TemplateResponse(
        "partials/eoi_success.html",
        {"request": request},
        headers={"Content-Type": "text/html"},
    )


@router.get("/login")
async def login_page(request: Request, invite: str | None = None):
    user = await get_current_user(request)
    if user:
        # Already logged in — auto-redeem the invite if present, then go to app.
        if invite:
            return RedirectResponse(f"/invite/{invite}/redeem", status_code=303)
        return RedirectResponse("/app", status_code=303)
    return templates.TemplateResponse("auth/login.html", {
        "request": request,
        "google_enabled": bool(GOOGLE_CLIENT_ID),
        "github_enabled": bool(GITHUB_CLIENT_ID),
        "invite": invite,
    })


@router.post("/login")
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    invite_code: str = Form(""),
):
    async with async_session() as db:
        user = await authenticate_user(db, email, password)

    if not user:
        return templates.TemplateResponse("auth/login.html", {
            "request": request,
            "errors": ["Invalid email or password."],
            "email": email,
            "google_enabled": bool(GOOGLE_CLIENT_ID),
            "github_enabled": bool(GITHUB_CLIENT_ID),
            "invite": invite_code or None,
        })

    token = create_access_token(user.id, user.email)
    request.state.session["auth_token"] = token

    # Unlock PII vault and store decrypted PII map in the session.
    # If the vault doesn't exist yet (new user), seed it with minimal data
    # and redirect to onboarding so the user can complete their profile.
    async with async_session() as db:
        pii = await unlock_vault(db, user_id=user.id, password=password)
        vault_existed = pii is not None
        if pii is None:
            # First login — create the vault now with minimal seed data.
            pii = pii_from_user(user)
            await upsert_vault(db, user_id=user.id, pii=pii, password=password)

    request.state.session["pii"] = pii
    # Store the password temporarily in the session so the onboarding POST
    # handler can re-encrypt with the user's actual password without asking
    # them to type it again.  This is cleared after onboarding completes
    # (or on the next login).
    request.state.session["_pii_password"] = password
    # Mark whether onboarding has already been completed.
    # vault_existed == True means they completed onboarding in a prior session.
    request.state.session["pii_onboarded"] = vault_existed

    # Seed credit balance in session to avoid a DB hit on every request.
    async with async_session() as db:
        request.state.session["cached_balance"] = await get_balance(db, user.id)

    # Auto-redeem invite if one was passed through the login flow.
    if invite_code:
        async with async_session() as db:
            result = await db.execute(
                select(Invitation).where(Invitation.code == invite_code)
            )
            invitation = result.scalar_one_or_none()
            if (
                invitation
                and not invitation.redeemed_by
                and (not invitation.email or invitation.email.lower() == user.email.lower())
            ):
                invitation.redeemed_by = user.id
                invitation.redeemed_at = datetime.now(UTC)
                await db.commit()
                await add_credits(db, user.id, invitation.credits)
                logger.info(
                    "Invitation %s auto-redeemed for existing user %s — %d credits granted",
                    invite_code, user.id, invitation.credits,
                )
        if not vault_existed:
            return RedirectResponse("/onboarding?invite_redeemed=1", status_code=303)
        return RedirectResponse("/app?invite_redeemed=1", status_code=303)

    if not vault_existed:
        return RedirectResponse("/onboarding", status_code=303)
    return RedirectResponse("/app", status_code=303)


@router.get("/logout")
async def logout(request: Request):
    request.state.session.pop("auth_token", None)
    request.state.session.pop("pii", None)
    return RedirectResponse("/", status_code=303)


# ── OAuth: Google ─────────────────────────────────────────

@router.get("/auth/google")
async def google_login(request: Request):
    if not GOOGLE_CLIENT_ID:
        return RedirectResponse("/login", status_code=303)
    from authlib.integrations.starlette_client import OAuth
    oauth = OAuth()
    oauth.register(
        name="google",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )
    redirect_uri = str(request.url_for("google_callback"))
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/auth/google/callback")
async def google_callback(request: Request):
    if not GOOGLE_CLIENT_ID:
        return RedirectResponse("/login", status_code=303)
    from authlib.integrations.starlette_client import OAuth
    oauth = OAuth()
    oauth.register(
        name="google",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )
    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get("userinfo", {})
    email = userinfo.get("email")
    name = userinfo.get("name", "")
    sub = userinfo.get("sub")

    if not email:
        return RedirectResponse("/login?error=no_email", status_code=303)

    async with async_session() as db:
        user = await get_user_by_provider(db, "google", sub)
        if not user:
            user = await get_user_by_email(db, email)
        if not user:
            user = await create_user(db, email=email, name=name, provider="google", provider_id=sub)
        else:
            await update_last_login(db, user)

    auth_token = create_access_token(user.id, user.email)
    request.state.session["auth_token"] = auth_token

    # Unlock (or seed) PII vault using server key for OAuth users.
    async with async_session() as db:
        pii = await unlock_vault_server_key(db, user_id=user.id)
        vault_existed = pii is not None
        if pii is None:
            pii = pii_from_user(user)
            await upsert_vault(db, user_id=user.id, pii=pii, password=None)

    request.state.session["pii"] = pii
    request.state.session["pii_onboarded"] = vault_existed

    if not vault_existed:
        from app.instrumentation import record_custom_event
        record_custom_event("UserSignup", {
            "user_id": user.id,
            "method": "google",
        })

    # Seed credit balance in session.
    async with async_session() as db:
        request.state.session["cached_balance"] = await get_balance(db, user.id)

    if not vault_existed:
        return RedirectResponse("/onboarding", status_code=303)
    return RedirectResponse("/app", status_code=303)


# ── OAuth: GitHub ─────────────────────────────────────────

@router.get("/auth/github")
async def github_login(request: Request):
    if not GITHUB_CLIENT_ID:
        return RedirectResponse("/login", status_code=303)
    from authlib.integrations.starlette_client import OAuth
    oauth = OAuth()
    oauth.register(
        name="github",
        client_id=GITHUB_CLIENT_ID,
        client_secret=GITHUB_CLIENT_SECRET,
        authorize_url="https://github.com/login/oauth/authorize",
        access_token_url="https://github.com/login/oauth/access_token",
        api_base_url="https://api.github.com/",
        client_kwargs={"scope": "user:email"},
    )
    redirect_uri = str(request.url_for("github_callback"))
    return await oauth.github.authorize_redirect(request, redirect_uri)


@router.get("/auth/github/callback")
async def github_callback(request: Request):
    if not GITHUB_CLIENT_ID:
        return RedirectResponse("/login", status_code=303)
    from authlib.integrations.starlette_client import OAuth
    oauth = OAuth()
    oauth.register(
        name="github",
        client_id=GITHUB_CLIENT_ID,
        client_secret=GITHUB_CLIENT_SECRET,
        authorize_url="https://github.com/login/oauth/authorize",
        access_token_url="https://github.com/login/oauth/access_token",
        api_base_url="https://api.github.com/",
        client_kwargs={"scope": "user:email"},
    )
    token = await oauth.github.authorize_access_token(request)
    resp = await oauth.github.get("user", token=token)
    profile = resp.json()
    github_id = str(profile.get("id"))
    email = profile.get("email")
    name = profile.get("name") or profile.get("login", "")

    # If email not public, fetch from emails endpoint
    if not email:
        emails_resp = await oauth.github.get("user/emails", token=token)
        emails = emails_resp.json()
        primary = next((e for e in emails if e.get("primary")), None)
        email = primary["email"] if primary else None

    if not email:
        return RedirectResponse("/login?error=no_email", status_code=303)

    async with async_session() as db:
        user = await get_user_by_provider(db, "github", github_id)
        if not user:
            user = await get_user_by_email(db, email)
        if not user:
            user = await create_user(db, email=email, name=name, provider="github", provider_id=github_id)
        else:
            await update_last_login(db, user)

    auth_token = create_access_token(user.id, user.email)
    request.state.session["auth_token"] = auth_token

    # Unlock (or seed) PII vault using server key for OAuth users.
    async with async_session() as db:
        pii = await unlock_vault_server_key(db, user_id=user.id)
        vault_existed = pii is not None
        if pii is None:
            pii = pii_from_user(user)
            await upsert_vault(db, user_id=user.id, pii=pii, password=None)

    request.state.session["pii"] = pii
    request.state.session["pii_onboarded"] = vault_existed

    if not vault_existed:
        from app.instrumentation import record_custom_event
        record_custom_event("UserSignup", {
            "user_id": user.id,
            "method": "github",
        })

    # Seed credit balance in session.
    async with async_session() as db:
        request.state.session["cached_balance"] = await get_balance(db, user.id)

    if not vault_existed:
        return RedirectResponse("/onboarding", status_code=303)
    return RedirectResponse("/app", status_code=303)


# ── Password reset ─────────────────────────────────────────


@router.get("/forgot-password")
async def forgot_password_page(request: Request):
    """Show the forgot-password form."""
    user = await get_current_user(request)
    if user:
        return RedirectResponse("/app", status_code=303)
    return templates.TemplateResponse("auth/forgot_password.html", {"request": request})


@router.post("/forgot-password")
async def forgot_password_submit(request: Request, email: str = Form(...)):
    """Issue a password reset token and email a reset link.

    Always returns the same confirmation page regardless of whether the email
    exists — prevents user enumeration.
    """
    normalized = email.lower().strip()
    async with async_session() as db:
        user = await get_user_by_email(db, normalized)

    if user and user.password_hash:
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        expires_at = datetime.now(UTC) + timedelta(minutes=PASSWORD_RESET_TTL_MINUTES)

        async with async_session() as db:
            db.add(PasswordResetToken(
                user_id=user.id,
                token_hash=token_hash,
                expires_at=expires_at,
            ))
            await db.commit()

        base_url = str(request.base_url).rstrip("/")
        try:
            await send_password_reset_email(
                to_email=user.email,
                name=user.name,
                reset_token=raw_token,
                base_url=base_url,
                expires_minutes=PASSWORD_RESET_TTL_MINUTES,
            )
        except Exception:
            logger.exception("Failed to send password reset email to %s", user.email)
    else:
        logger.debug("Password reset requested for unknown/OAuth email: %s", normalized)

    return templates.TemplateResponse(
        "auth/forgot_password_sent.html",
        {"request": request},
    )


@router.get("/reset-password")
async def reset_password_page(request: Request, token: str = ""):
    """Show the new-password form for a valid reset token."""
    if not token:
        return RedirectResponse("/forgot-password", status_code=303)

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    now = datetime.now(UTC)

    async with async_session() as db:
        result = await db.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.used_at.is_(None),
                PasswordResetToken.expires_at > now,
            )
        )
        reset_token = result.scalar_one_or_none()

    if not reset_token:
        return templates.TemplateResponse(
            "auth/reset_password_invalid.html",
            {"request": request},
        )

    return templates.TemplateResponse(
        "auth/reset_password.html",
        {"request": request, "token": token},
    )


@router.post("/reset-password")
async def reset_password_submit(
    request: Request,
    token: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
):
    """Apply the new password if the reset token is still valid."""
    errors = []

    if len(password) < 8:
        errors.append("Password must be at least 8 characters.")
    elif password != confirm_password:
        errors.append("Passwords do not match.")

    if errors:
        return templates.TemplateResponse(
            "auth/reset_password.html",
            {"request": request, "token": token, "errors": errors},
        )

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    now = datetime.now(UTC)

    async with async_session() as db:
        result = await db.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.used_at.is_(None),
                PasswordResetToken.expires_at > now,
            )
        )
        reset_token = result.scalar_one_or_none()

        if not reset_token:
            return templates.TemplateResponse(
                "auth/reset_password_invalid.html",
                {"request": request},
            )

        user_result = await db.execute(select(User).where(User.id == reset_token.user_id))
        user = user_result.scalar_one_or_none()

        if not user:
            return templates.TemplateResponse(
                "auth/reset_password_invalid.html",
                {"request": request},
            )

        user.password_hash = hash_password(password)
        reset_token.used_at = now
        await db.commit()

    logger.info("Password reset completed for user %s", user.id)
    return RedirectResponse("/login?reset=1", status_code=303)
