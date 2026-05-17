"""Onboarding routes: /onboarding (GET + POST) and /account/pii (GET + POST).

The onboarding page collects PII from a newly registered user and stores it
in the encrypted PII vault.  It is shown once after first login when the vault
contains only the minimal seeded data.  The same form is reused at
/account/pii for users who want to update their personal information later.
"""

import logging

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from app.cv_export.adapters.template_registry import list_regions
from app.identity.adapters.fastapi_deps import require_auth
from app.infrastructure.persistence.database import async_session
from app.infrastructure.persistence.orm_models import User
from app.infrastructure.phone_utils import normalize_phone
from app.pii.adapters.vault import (
    get_session_pii,
    unlock_vault,
    unlock_vault_server_key,
    upsert_vault,
)
from app.web.templates import templates

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_oauth_user(user) -> bool:
    """Return True when the user authenticated via OAuth (no password)."""
    return bool(user.provider) and not user.password_hash


async def _save_pii(request: Request, user, pii: dict) -> None:
    """Encrypt and persist PII, then refresh the session cache."""
    password = request.state.session.get("_pii_password")

    async with async_session() as db:
        if password:
            await upsert_vault(db, user_id=user.id, pii=pii, password=password)
        else:
            # OAuth user — use server key
            await upsert_vault(db, user_id=user.id, pii=pii, password=None)

    # Refresh the in-session PII cache
    request.state.session["pii"] = pii
    # Mark onboarding complete so auth redirects stop sending here
    request.state.session["pii_onboarded"] = True


def _references_from_form(form) -> list[dict]:
    """Parse up to two reference entries (indices 1 and 2) from a submitted form.

    Mirrors the wizard step-2 layout (ref_name_N, ref_title_N, ref_company_N,
    ref_email_N, ref_phone_N). Entries with no name are dropped.
    """
    refs: list[dict] = []
    for idx in (1, 2):
        name = (form.get(f"ref_name_{idx}") or "").strip()
        if not name:
            continue
        refs.append({
            "name": name,
            "title": (form.get(f"ref_title_{idx}") or "").strip(),
            "company": (form.get(f"ref_company_{idx}") or "").strip(),
            "email": (form.get(f"ref_email_{idx}") or "").strip(),
            "phone": normalize_phone(form.get(f"ref_phone_{idx}") or ""),
        })
    return refs


# ---------------------------------------------------------------------------
# Routes: /onboarding
# ---------------------------------------------------------------------------


@router.get("/onboarding")
async def onboarding_page(request: Request, user: User = Depends(require_auth)):
    """Show the PII onboarding form."""

    # If already onboarded in this session, go straight to the app
    if request.state.session.get("pii_onboarded"):
        return RedirectResponse("/app", status_code=303)

    pii = get_session_pii(request)
    return templates.TemplateResponse(
        "onboarding.html",
        {
            "request": request,
            "pii": pii,
            "is_oauth": _is_oauth_user(user),
            "mode": "onboarding",
            "regions": list_regions(),
        },
    )


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
    location: str = Form(""),
    linkedin: str = Form(""),
    github: str = Form(""),
    portfolio: str = Form(""),
    user: User = Depends(require_auth),
):
    """Save PII to the vault and redirect to /app."""

    form = await request.form()
    references = _references_from_form(form)

    full_name = full_name.strip()
    if not full_name:
        pii = get_session_pii(request)
        return templates.TemplateResponse(
            "onboarding.html",
            {
                "request": request,
                "pii": pii,
                "is_oauth": _is_oauth_user(user),
                "mode": "onboarding",
                "regions": list_regions(),
                "errors": ["Full name is required."],
            },
            status_code=422,
        )

    pii = {
        "full_name": full_name,
        "email": email.strip(),
        "phone": normalize_phone(phone),
        "country": country.strip(),
        "dob": dob.strip(),
        "document_id": document_id.strip(),
        "nationality": nationality.strip(),
        "marital_status": marital_status.strip(),
        "location": location.strip(),
        "linkedin": linkedin.strip(),
        "github": github.strip(),
        "portfolio": portfolio.strip(),
        "references": references,
    }

    await _save_pii(request, user, pii)
    logger.info("PII onboarding completed for user_id=%s", user.id)

    return RedirectResponse("/app", status_code=303)


# ---------------------------------------------------------------------------
# Routes: /account/pii  (update PII from account settings)
# ---------------------------------------------------------------------------


@router.get("/account/pii")
async def account_pii_page(request: Request, user: User = Depends(require_auth)):
    """Show the PII update form from account settings."""

    pii = get_session_pii(request)

    # If the session PII cache is empty, try to re-unlock the vault.
    # This can happen when a user navigates here in a fresh browser tab
    # after the session PII was cleared.
    if not pii:
        async with async_session() as db:
            if _is_oauth_user(user):
                pii = await unlock_vault_server_key(db, user_id=user.id) or {}
            else:
                password = request.state.session.get("_pii_password")
                if password:
                    pii = await unlock_vault(db, user_id=user.id, password=password) or {}

    return templates.TemplateResponse(
        "onboarding.html",
        {
            "request": request,
            "pii": pii,
            "is_oauth": _is_oauth_user(user),
            "mode": "account",
            "regions": list_regions(),
        },
    )


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
    location: str = Form(""),
    linkedin: str = Form(""),
    github: str = Form(""),
    portfolio: str = Form(""),
    user: User = Depends(require_auth),
):
    """Save updated PII to the vault from account settings."""

    form = await request.form()
    references = _references_from_form(form)

    full_name = full_name.strip()
    if not full_name:
        pii = get_session_pii(request)
        return templates.TemplateResponse(
            "onboarding.html",
            {
                "request": request,
                "pii": pii,
                "is_oauth": _is_oauth_user(user),
                "mode": "account",
                "regions": list_regions(),
                "errors": ["Full name is required."],
            },
            status_code=422,
        )

    pii = {
        "full_name": full_name,
        "email": email.strip(),
        "phone": normalize_phone(phone),
        "country": country.strip(),
        "dob": dob.strip(),
        "document_id": document_id.strip(),
        "nationality": nationality.strip(),
        "marital_status": marital_status.strip(),
        "location": location.strip(),
        "linkedin": linkedin.strip(),
        "github": github.strip(),
        "portfolio": portfolio.strip(),
        "references": references,
    }

    await _save_pii(request, user, pii)
    logger.info("PII updated via account settings for user_id=%s", user.id)

    return RedirectResponse("/account?pii_saved=1", status_code=303)
