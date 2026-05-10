"""Profile routes — manage the user's persistent identity and base CV document.

The profile stores PII vault data (name, contact details, preferences) and an
optional base CV file that pre-fills every new job wizard run.  These routes
replace the manual re-entry that previously happened in wizard steps 1–2.
"""

import logging
from pathlib import Path

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse, Response

from app.cv_export.adapters.template_registry import REGIONS
from app.identity.adapters.fastapi_deps import get_current_user
from app.infrastructure.persistence.database import async_session
from app.infrastructure.phone_utils import normalize_phone
from app.web.routes.wizard import _region_fields
from app.web.templates import templates

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profile", tags=["profile"])

# Profile-level CV uploads live here (keyed by user_id, not attempt_id).
_PROFILES_DIR = Path(__file__).parent.parent.parent / "uploads" / "profiles"


def _profile_dir(user_id: str) -> Path:
    """Return (and create if needed) the upload dir for a user's profile CV."""
    safe_id = "".join(c for c in user_id if c.isalnum())
    d = _PROFILES_DIR / safe_id
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# GET /profile — show the profile page
# ---------------------------------------------------------------------------


@router.get("")
@router.get("/")
async def profile_page(request: Request):
    """Career profile lives at /account#career-profile now. Permanent redirect."""
    return RedirectResponse("/account#career-profile", status_code=301)


# ---------------------------------------------------------------------------
# GET /profile/region-change/{code} — live-update region summary + Section 3
# ---------------------------------------------------------------------------


@router.get("/region-change/{code}")
async def profile_region_change(request: Request, code: str):
    """Return region-summary HTML plus an OOB swap for Section 3 regional fields.

    Fired by the radio buttons in Section 2 so picking a new default region
    immediately reveals the conditional fields (photo, DOB, visa, etc.) that
    the chosen country expects on a CV.
    """
    region_config = REGIONS.get(code, REGIONS["AU"])
    fields = _region_fields(code)
    pii = request.state.session.get("pii") or {}

    # Mirror the chosen region into the session view of PII so the partial's
    # "Your selected region doesn't require extra personal details" copy
    # picks the right branch before the form is saved.
    pii_view = {**pii, "region": code}

    return templates.TemplateResponse("partials/profile/region_change.html", {
        "request": request,
        "region_config": region_config,
        "fields": fields,
        "pii": pii_view,
        "oob": True,
    })


# ---------------------------------------------------------------------------
# POST /profile/save — persist profile data (HTMX endpoint)
# ---------------------------------------------------------------------------


@router.post("/save")
async def profile_save(
    request: Request,
    full_name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    visa_status: str = Form(""),
    nationality: str = Form(""),
    marital_status: str = Form(""),
    dob: str = Form(""),
    self_description: str = Form(""),
    values: str = Form(""),
    country: str = Form(""),
    linkedin: str = Form(""),
    github: str = Form(""),
    portfolio: str = Form(""),
    location: str = Form(""),
    cv_file: UploadFile = File(None),
):
    """Save profile fields to the PII vault.  Returns an HTMX success partial."""
    current_user = await get_current_user(request)
    if not current_user:
        return RedirectResponse("/login", status_code=302)

    if not full_name.strip():
        return templates.TemplateResponse("partials/profile/save_result.html", {
            "request": request,
            "success": False,
            "error": "Full name is required.",
        })

    # Merge new values into the existing PII vault snapshot.
    pii = request.state.session.get("pii") or {}
    pii.update({
        "full_name": full_name.strip(),
        "email": email.strip(),
        "phone": normalize_phone(phone),
        "visa_status": visa_status,
        "nationality": nationality.strip(),
        "marital_status": marital_status,
        "dob": dob.strip(),
        "self_description": self_description,
        "values": values,
        "country": country,
        "linkedin": linkedin.strip(),
        "github": github.strip(),
        "portfolio": portfolio.strip(),
        "location": location.strip(),
    })

    # Persist to the vault.
    from app.pii.adapters.vault import upsert_vault
    password = request.state.session.get("_pii_password")
    try:
        async with async_session() as db:
            await upsert_vault(db, user_id=current_user.id, pii=pii, password=password or None)
        request.state.session["pii"] = pii
    except Exception:
        logger.exception("Failed to upsert PII vault for user=%s", current_user.id)
        return templates.TemplateResponse("partials/profile/save_result.html", {
            "request": request,
            "success": False,
            "error": "Failed to save profile. Please try again.",
        })

    # Save base CV file if one was provided.
    cv_saved_filename: str | None = None
    if cv_file and cv_file.filename:
        file_bytes = await cv_file.read()
        if file_bytes:
            from app.infrastructure.crypto import encrypt_data
            profile_dir = _profile_dir(current_user.id)
            ext = Path(cv_file.filename).suffix.lower()
            dest = profile_dir / f"cv_file{ext}.enc"
            try:
                dest.write_text(encrypt_data(file_bytes.hex()))
                cv_saved_filename = cv_file.filename
                logger.info("Saved profile CV for user=%s (%d bytes)", current_user.id, len(file_bytes))
            except Exception:
                logger.exception("Failed to save profile CV for user=%s", current_user.id)

    return templates.TemplateResponse("partials/profile/save_result.html", {
        "request": request,
        "success": True,
        "cv_saved_filename": cv_saved_filename,
    })
