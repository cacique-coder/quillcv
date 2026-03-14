"""Onboarding routes: /onboarding (GET + POST) and /account/pii (GET + POST).

The onboarding page collects PII from a newly registered user and stores it
in the encrypted PII vault.  It is shown once after first login when the vault
contains only the minimal seeded data.  The same form is reused at
/account/pii for users who want to update their personal information later.
"""

import logging
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth.dependencies import get_current_user
from app.database import async_session
from app.services.phone_utils import normalize_phone
from app.services.pii_vault import (
    get_session_pii,
    unlock_vault,
    unlock_vault_server_key,
    upsert_vault,
)
from app.services.template_registry import list_regions

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_oauth_user(user) -> bool:
    """Return True when the user authenticated via OAuth (no password)."""
    return bool(user.provider) and not user.password_hash


async def _save_pii(request: Request, user, pii: dict) -> None:
    """Encrypt and persist PII, then refresh the session cache."""
    password = request.session.get("_pii_password")

    async with async_session() as db:
        if password:
            await upsert_vault(db, user_id=user.id, pii=pii, password=password)
        else:
            # OAuth user — use server key
            await upsert_vault(db, user_id=user.id, pii=pii, password=None)

    # Refresh the in-session PII cache
    request.session["pii"] = pii
    # Mark onboarding complete so auth redirects stop sending here
    request.session["pii_onboarded"] = True


# ---------------------------------------------------------------------------
# Routes: /onboarding
# ---------------------------------------------------------------------------


@router.get("/onboarding")
async def onboarding_page(request: Request):
    """Show the PII onboarding form."""
    user = await get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    # If already onboarded in this session, go straight to the app
    if request.session.get("pii_onboarded"):
        return RedirectResponse("/app", status_code=303)

    pii = get_session_pii(request)
    return templates.TemplateResponse("onboarding.html", {
        "request": request,
        "pii": pii,
        "is_oauth": _is_oauth_user(user),
        "mode": "onboarding",
        "regions": list_regions(),
    })


@router.post("/onboarding")
async def onboarding_submit(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(""),
    phone: str = Form(""),
    country: str = Form(""),
    dob: str = Form(""),
    document_id: str = Form(""),
    nationality: str = Form(""),
    marital_status: str = Form(""),
):
    """Save PII to the vault and redirect to /app."""
    user = await get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    full_name = full_name.strip()
    if not full_name:
        pii = get_session_pii(request)
        return templates.TemplateResponse("onboarding.html", {
            "request": request,
            "pii": pii,
            "is_oauth": _is_oauth_user(user),
            "mode": "onboarding",
            "regions": list_regions(),
            "errors": ["Full name is required."],
        }, status_code=422)

    pii = {
        "full_name": full_name,
        "email": email.strip(),
        "phone": normalize_phone(phone),
        "country": country.strip(),
        "dob": dob.strip(),
        "document_id": document_id.strip(),
        "nationality": nationality.strip(),
        "marital_status": marital_status.strip(),
        "references": get_session_pii(request).get("references", []),
    }

    await _save_pii(request, user, pii)
    logger.info("PII onboarding completed for user_id=%s", user.id)

    return RedirectResponse("/app", status_code=303)


# ---------------------------------------------------------------------------
# Routes: /account/pii  (update PII from account settings)
# ---------------------------------------------------------------------------


@router.get("/account/pii")
async def account_pii_page(request: Request):
    """Show the PII update form from account settings."""
    user = await get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    pii = get_session_pii(request)

    # If the session PII cache is empty, try to re-unlock the vault.
    # This can happen when a user navigates here in a fresh browser tab
    # after the session PII was cleared.
    if not pii:
        async with async_session() as db:
            if _is_oauth_user(user):
                pii = await unlock_vault_server_key(db, user_id=user.id) or {}
            else:
                password = request.session.get("_pii_password")
                if password:
                    pii = await unlock_vault(db, user_id=user.id, password=password) or {}

    return templates.TemplateResponse("onboarding.html", {
        "request": request,
        "pii": pii,
        "is_oauth": _is_oauth_user(user),
        "mode": "account",
        "regions": list_regions(),
    })


@router.post("/account/pii")
async def account_pii_submit(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(""),
    phone: str = Form(""),
    country: str = Form(""),
    dob: str = Form(""),
    document_id: str = Form(""),
    nationality: str = Form(""),
    marital_status: str = Form(""),
):
    """Save updated PII to the vault from account settings."""
    user = await get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    full_name = full_name.strip()
    if not full_name:
        pii = get_session_pii(request)
        return templates.TemplateResponse("onboarding.html", {
            "request": request,
            "pii": pii,
            "is_oauth": _is_oauth_user(user),
            "mode": "account",
            "regions": list_regions(),
            "errors": ["Full name is required."],
        }, status_code=422)

    pii = {
        "full_name": full_name,
        "email": email.strip(),
        "phone": normalize_phone(phone),
        "country": country.strip(),
        "dob": dob.strip(),
        "document_id": document_id.strip(),
        "nationality": nationality.strip(),
        "marital_status": marital_status.strip(),
        "references": get_session_pii(request).get("references", []),
    }

    await _save_pii(request, user, pii)
    logger.info("PII updated via account settings for user_id=%s", user.id)

    return RedirectResponse("/account?pii_saved=1", status_code=303)
