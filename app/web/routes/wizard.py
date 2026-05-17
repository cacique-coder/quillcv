import json
import logging

from fastapi import APIRouter, File, Form, Request, UploadFile
from starlette.responses import RedirectResponse

from app.consent.use_cases.record_consent import (
    CURRENT_POLICY_VERSION,
    get_client_ip,
    get_user_agent,
    record_age_confirmation,
    record_consent,
)
from app.cv_export.adapters.template_registry import REGIONS, list_regions, list_templates
from app.cv_generation.use_cases.region_warnings import region_warnings_dicts
from app.identity.adapters.fastapi_deps import get_current_user
from app.infrastructure.persistence.attempt_store import (
    create_attempt,
    get_attempt,
    get_document_filename,
    save_document,
    update_attempt,
)
from app.infrastructure.persistence.database import async_session
from app.infrastructure.phone_utils import normalize_phone
from app.web.templates import templates

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/wizard")


def _is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"


def _step_response(template_name: str, ctx: dict, step: int):
    """Render a wizard step partial and tell HTMX to push the matching URL.

    HX-Push-Url updates the browser address bar so step transitions are
    bookmarkable and the back button on the progress tabs works as a real
    navigation. Step GET routes already serve the full shell when HX-Request
    is absent, so a direct reload at /wizard/step/N keeps working.
    """
    resp = templates.TemplateResponse(template_name, ctx)
    resp.headers["HX-Push-Url"] = f"/wizard/step/{step}"
    return resp


async def _ensure_session_pii(request: Request) -> dict | None:
    """Return the user's PII map, re-unlocking the vault from the DB when the
    session cache has been pruned. Writes the result back into the session so
    later steps don't repeat the unlock."""
    user = await get_current_user(request)
    if not user:
        return None
    from app.pii.adapters.vault import unlock_vault, unlock_vault_server_key

    pii: dict | None = None
    is_oauth = bool(getattr(user, "provider", None)) and not getattr(user, "password_hash", None)
    async with async_session() as db:
        if is_oauth:
            pii = await unlock_vault_server_key(db, user_id=user.id)
        else:
            password = request.state.session.get("_pii_password")
            if password:
                pii = await unlock_vault(db, user_id=user.id, password=password)
    if pii:
        request.state.session["pii"] = pii
    return pii


def _wizard_shell(request: Request, step: int):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "initial_step": step,
    })


def _region_fields(code: str) -> dict:
    """Return which conditional fields a region requires."""
    r = REGIONS.get(code)
    if not r:
        return {"photo": False, "references": False, "visa": False}
    return {
        "photo": r.include_photo in ("required", "common", "optional"),
        "photo_level": r.include_photo,
        "references": r.include_references,
        "visa": r.include_visa_status,
        "dob": r.include_dob,
        "nationality": r.include_nationality,
        "marital": r.include_marital_status,
    }


def _check_pii_completeness(attempt: dict, pii: dict, region_code: str) -> tuple[bool, list[str]]:
    """Check if all required PII fields are filled based on the region.

    Returns (is_complete, missing_fields) where missing_fields is a list of
    human-readable field names that are still needed.
    """
    fields = _region_fields(region_code)
    missing = []

    # Helper: check attempt first, then vault
    def _has(key: str) -> bool:
        return bool((attempt.get(key) or "").strip() or (pii.get(key) or "").strip())

    # Always required
    if not _has("full_name"):
        missing.append("Full name")
    if not _has("email"):
        missing.append("Contact email")
    if not _has("phone"):
        missing.append("Phone number")

    # Region-conditional
    if fields.get("dob") and not _has("dob"):
        missing.append("Date of birth")
    if fields.get("nationality") and not _has("nationality"):
        missing.append("Nationality")
    if fields.get("marital") and not _has("marital_status"):
        missing.append("Marital status")
    # Work rights are opt-in: only require visa_status if the user has
    # explicitly chosen to include them on the CV. Region defaults no longer
    # force the field — see step 2 "Include my work rights" checkbox.
    if (
        fields.get("visa")
        and attempt.get("include_work_rights")
        and not _has("visa_status")
    ):
        missing.append("Visa / work rights")
    if fields.get("references"):
        refs = attempt.get("references") or pii.get("references") or []
        has_ref = any(r.get("name", "").strip() for r in refs) if refs else False
        if not has_ref:
            missing.append("At least one reference")

    # Document ID: only required for CO/VE
    if region_code in ("CO", "VE") and not _has("document_id"):
        missing.append("Cédula / National ID")

    return (len(missing) == 0, missing)


def _bind_llm_context(request: Request, attempt_id: str) -> None:
    """Tag the current request's LLM-tracking context with the active session.

    A "session" here = one wizard flow = one ``attempt_id``. Calling this on
    every wizard handler means any LLM call that fires inside the request
    inherits the attempt_id + user_id, so APIRequestLog rows group cleanly
    by session in the admin cost dashboard. Each generation pipeline run
    inside the session gets its own ``transaction_id`` (an "iteration") set
    downstream in ``run_generation_pipeline``.
    """
    from app.infrastructure.llm.client import set_llm_context

    user = getattr(request.state, "user", None)
    set_llm_context(
        service="wizard",
        attempt_id=attempt_id,
        user_id=user.id if user else None,
    )


def _get_or_create_attempt(request: Request) -> dict:
    """Get the current attempt from session, or create a new one.

    Also binds the attempt_id to the LLM-tracking context vars so every
    LLM call within this request lands in APIRequestLog tagged with the
    session — see ``_bind_llm_context`` for the model.
    """
    attempt_id = request.state.session.get("attempt_id")
    if attempt_id:
        attempt = get_attempt(attempt_id)
        if attempt:
            _bind_llm_context(request, attempt_id)
            return attempt
    # Create new attempt
    attempt_id = create_attempt()
    request.state.session["attempt_id"] = attempt_id
    _bind_llm_context(request, attempt_id)
    return get_attempt(attempt_id)


# ------------------------------------------------------------------
# Wizard shell — serves the full page; step routes serve partials
# ------------------------------------------------------------------

@router.get("")
@router.get("/")
async def wizard_shell(request: Request):
    attempt = _get_or_create_attempt(request)
    step = max(1, min(6, attempt.get("step", 1)))
    return _wizard_shell(request, step)


@router.get("/new")
async def wizard_new(request: Request, from_cv: str | None = None):
    """Start a brand-new wizard attempt, optionally seeded from a saved CV."""
    old_attempt_id = request.state.session.get("attempt_id")
    new_attempt_id = create_attempt()
    request.state.session["attempt_id"] = new_attempt_id

    if from_cv:
        await _seed_from_saved_cv(request, new_attempt_id, from_cv, old_attempt_id)

    return RedirectResponse(url="/wizard/step/1", status_code=303)


async def _seed_from_saved_cv(
    request: Request,
    new_attempt_id: str,
    cv_id: str,
    old_attempt_id: str | None,
) -> None:
    """Seed a new attempt from a saved CV row if the caller is authorised to access it."""
    from sqlalchemy import select

    from app.infrastructure.persistence.cv_repo import decrypt_saved_cv
    from app.infrastructure.persistence.orm_models import SavedCV

    current_user = await get_current_user(request)

    async with async_session() as db:
        result = await db.execute(select(SavedCV).where(SavedCV.id == cv_id))
        cv = result.scalar_one_or_none()

    if not cv:
        logger.info("WizardSeed[%s] cv_id=%s not found — skipping seed", new_attempt_id, cv_id)
        return

    # Ownership check: authenticated users must own the row; anonymous users
    # may access it only if it belongs to their previous session attempt.
    if current_user:
        authorised = cv.user_id == current_user.id
    else:
        authorised = bool(old_attempt_id and cv.attempt_id == old_attempt_id)

    if not authorised:
        logger.info(
            "WizardSeed[%s] cv_id=%s ownership check failed — skipping seed",
            new_attempt_id, cv_id,
        )
        return

    cv = decrypt_saved_cv(cv)

    try:
        cv_data = json.loads(cv.cv_data_json) if cv.cv_data_json else {}
    except (json.JSONDecodeError, TypeError):
        cv_data = {}

    seed: dict = {"step": 1}
    if cv.region:
        seed["region"] = cv.region
    if cv.template_id:
        seed["template_id"] = cv.template_id
    if cv.markdown:
        seed["cv_text"] = cv.markdown

    # Identity fields (full_name/email/phone) and references are NOT seeded
    # from the saved CV — they always come from the PII vault on render in
    # step2(). The saved cv_data_json contains redacted placeholder tokens
    # (e.g. ``<<FULL_NAME>>``), so seeding from it would leak placeholders.

    # Per-CV professional voice: preserve the voice that was used the first
    # time this CV was tailored, so re-running the wizard from a saved CV
    # keeps the same self_description / values / offer_appeal as defaults.
    if getattr(cv, "self_description", None):
        seed["self_description"] = cv.self_description
    if getattr(cv, "values_text", None):
        seed["values"] = cv.values_text
    if getattr(cv, "offer_appeal", None):
        seed["offer_appeal"] = cv.offer_appeal

    update_attempt(new_attempt_id, **seed)
    logger.info("WizardSeed[%s] seeded from cv_id=%s", new_attempt_id, cv.id)


# ------------------------------------------------------------------
# Step 1: Country
# ------------------------------------------------------------------

@router.get("/step/1")
async def step1(request: Request):
    if not _is_htmx(request):
        return _wizard_shell(request, 1)
    attempt = _get_or_create_attempt(request)

    # Resolve the vault country. Prefer session PII; fall back to unlocking the
    # vault from the DB when the session cache is empty (e.g. trimmed sessions
    # or fresh tab) so the user's default country still wins on first paint.
    pii = request.state.session.get("pii") or {}
    if not pii.get("country"):
        pii = await _ensure_session_pii(request) or pii
    vault_country = (pii.get("country") or "").strip()
    vault_country = vault_country if vault_country in REGIONS else ""

    # Preserve the user's explicit choice once they've advanced past step 1
    # (Back button on step 2 returns here). Otherwise prefer the vault country
    # so a stale attempt left behind before the vault was set never wins.
    attempt_region = (attempt.get("region") or "").strip()
    has_explicit_choice = attempt_region in REGIONS and attempt.get("step", 1) >= 2

    if has_explicit_choice:
        selected = attempt_region
    elif vault_country:
        selected = vault_country
    else:
        selected = "AU"

    return _step_response("partials/wizard/step1_country.html", {
        "request": request,
        "regions": list_regions(),
        "selected_region": selected,
        "region_config": REGIONS.get(selected, REGIONS["AU"]),
        "fields": _region_fields(selected),
    }, step=1)


@router.post("/step/1/save")
async def step1_save(request: Request, region: str = Form("AU")):
    """Save step 1 and move to step 2."""
    attempt = _get_or_create_attempt(request)
    update_attempt(attempt["id"], region=region, step=2)
    return await step2(request)


# ------------------------------------------------------------------
# Step 2: Your Details
# ------------------------------------------------------------------

@router.get("/step/2")
async def step2_get(request: Request):
    if not _is_htmx(request):
        return _wizard_shell(request, 2)
    return await step2(request)


async def step2(request: Request):
    attempt = _get_or_create_attempt(request)
    region = attempt.get("region", "AU")
    region_config = REGIONS.get(region, REGIONS["AU"])
    fields = _region_fields(region)
    current_user = await get_current_user(request)
    age_already_confirmed = bool(current_user and current_user.age_confirmed_at)

    # Merge PII vault values into the attempt for rendering.
    #
    # Identity fields (full_name/email/phone/dob/document_id/nationality/
    # marital_status) and references are vault-authoritative: PII edits in
    # the wizard are written back to the vault on submit (see step 2 save
    # below), so the vault is the source of truth. Forcing the vault to
    # win on render also avoids leaking redacted placeholder tokens from
    # `_seed_from_saved_cv` (where cv_data_json contains tokens like
    # ``<<FULL_NAME>>``).
    #
    # Voice fields (self_description, values) fall back vault → empty only
    # when the attempt has no value, so a per-CV voice seeded by
    # `_seed_from_saved_cv` is preserved.
    pii = request.state.session.get("pii") or {}
    pii_prefilled = bool(pii)
    for key in ("full_name", "email", "phone", "dob", "document_id",
                "nationality", "marital_status"):
        if pii.get(key):
            attempt[key] = pii[key]

    for key in ("self_description", "values"):
        if not attempt.get(key) and pii.get(key):
            attempt[key] = pii[key]

    # References: vault wins when populated (vault-authoritative, like the
    # identity fields above).
    if pii.get("references"):
        attempt["references"] = pii["references"]

    # Check PII completeness based on region requirements
    pii_complete, pii_missing = _check_pii_completeness(attempt, pii, region)
    pii_incomplete = not pii_complete

    return _step_response("partials/wizard/step2_details.html", {
        "request": request,
        "attempt": attempt,
        "region": region,
        "region_config": region_config,
        "fields": fields,
        "dev_mode": request.app.state.dev_mode,
        "age_already_confirmed": age_already_confirmed,
        "pii_prefilled": pii_prefilled,
        "pii_incomplete": pii_incomplete,
        "pii_missing": pii_missing,
    }, step=2)


@router.post("/step/2/save")
async def step2_save(
    request: Request,
    full_name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    visa_status: str = Form(""),
    include_work_rights: str = Form(""),
    nationality: str = Form(""),
    marital_status: str = Form(""),
    ref_name_1: str = Form(""),
    ref_title_1: str = Form(""),
    ref_company_1: str = Form(""),
    ref_email_1: str = Form(""),
    ref_phone_1: str = Form(""),
    ref_name_2: str = Form(""),
    ref_title_2: str = Form(""),
    ref_company_2: str = Form(""),
    ref_email_2: str = Form(""),
    ref_phone_2: str = Form(""),
    # Age gate — required for all users
    age_confirmed: str = Form(""),
    # Sensitive data consents — only required when the respective field is submitted
    consent_photo: str = Form(""),
    consent_dob: str = Form(""),
    consent_document_id: str = Form(""),
):
    """Save step 2 and move to step 3.

    Enforces age gate (18+) and validates sensitive data consent checkboxes.
    For authenticated users who have already confirmed their age on a previous
    visit, the age gate check is skipped and the checkbox is pre-ticked in the
    template. Consent events are recorded in the consent_records audit table.
    """
    attempt = _get_or_create_attempt(request)
    region = attempt.get("region", "AU")
    region_config = REGIONS.get(region, REGIONS["AU"])
    fields = _region_fields(region)

    pii_prefilled = bool(request.state.session.get("pii"))

    # ------------------------------------------------------------------
    # Age gate validation
    # ------------------------------------------------------------------
    current_user = await get_current_user(request)
    # Capture id while the object is fresh; used later in upsert_vault
    user_id = current_user.id if current_user else None

    # If the authenticated user has already confirmed their age in a previous
    # session, we skip the checkbox requirement — they've already consented.
    already_age_confirmed = bool(
        current_user and current_user.age_confirmed_at
    )

    # ------------------------------------------------------------------
    # Build references list from form fields (needed by _render_error)
    # ------------------------------------------------------------------
    references = []
    for _i, (ref_n, ref_t, ref_c, ref_e, ref_p) in enumerate([
        (ref_name_1, ref_title_1, ref_company_1, ref_email_1, ref_phone_1),
        (ref_name_2, ref_title_2, ref_company_2, ref_email_2, ref_phone_2),
    ], 1):
        if ref_n.strip():
            references.append({
                "name": ref_n.strip(),
                "title": ref_t.strip(),
                "company": ref_c.strip(),
                "email": ref_e.strip(),
                "phone": normalize_phone(ref_p),
            })

    def _render_error(error: str, extra: dict | None = None) -> templates.TemplateResponse:
        pii = request.state.session.get("pii") or {}
        attempt_with_overrides = {
            **attempt,
            "full_name": full_name,
            "email": email,
            "phone": phone,
            "nationality": nationality,
            "marital_status": marital_status,
            "visa_status": visa_status,
            "include_work_rights": bool(include_work_rights),
            "references": references,
        }
        pii_complete, pii_missing = _check_pii_completeness(attempt_with_overrides, pii, region)
        ctx = {
            "request": request,
            "attempt": attempt_with_overrides,
            "region": region,
            "region_config": region_config,
            "fields": fields,
            "dev_mode": request.app.state.dev_mode,
            "error": error,
            # Must be re-passed so the template knows whether to show the checkbox
            "age_already_confirmed": already_age_confirmed,
            "pii_prefilled": pii_prefilled,
            "pii_incomplete": not pii_complete,
            "pii_missing": pii_missing,
        }
        if extra:
            ctx.update(extra)
        return _step_response("partials/wizard/step2_details.html", ctx, step=2)

    if not already_age_confirmed and not age_confirmed:
        return _render_error(
            "You must confirm you are 18 years of age or older to continue.",
            {"age_error": True},
        )

    # ------------------------------------------------------------------
    # Sensitive data consent validation
    # ------------------------------------------------------------------
    # Photo consent: required when a photo is relevant for this region
    # and the user is providing one (we cannot know server-side whether
    # they actually uploaded a photo since photos use a separate HTMX
    # endpoint, so we validate consent when the region shows the field).
    if fields.get("photo") and not consent_photo:
        return _render_error(
            "Please provide your consent to process your CV photo before continuing.",
            {"photo_consent_error": True},
        )

    # DOB consent: required when region collects date of birth
    if fields.get("dob") and not consent_dob:
        return _render_error(
            "Please provide your consent to process your date of birth before continuing.",
            {"dob_consent_error": True},
        )

    # ------------------------------------------------------------------
    # Full name validation
    # ------------------------------------------------------------------
    if not full_name.strip():
        return _render_error(
            "Your full name is required — we use it to protect your privacy during AI generation.",
        )

    # ------------------------------------------------------------------
    # Email format validation (only when a value is provided)
    # ------------------------------------------------------------------
    import re as _re
    if email.strip() and not _re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()):
        return _render_error("Please enter a valid email address.")

    # ------------------------------------------------------------------
    # Reference contact validation
    # Each reference with a name must have at least one contact method
    # (email or phone) so the employer can actually reach them.
    # ------------------------------------------------------------------
    for idx, ref in enumerate(references, start=1):
        if not ((ref.get("email") or "").strip() or (ref.get("phone") or "").strip()):
            return _render_error(
                f"Reference {idx} ({ref.get('name')}) needs at least one contact method — add an email or phone number.",
                {"reference_error_index": idx},
            )

    # ------------------------------------------------------------------
    # Persist consent records for authenticated users
    # ------------------------------------------------------------------
    if current_user:
        from sqlalchemy import select

        from app.infrastructure.persistence.orm_models import User as UserModel

        ip = get_client_ip(request)
        ua = get_user_agent(request)

        async with async_session() as db:
            # Re-load the user inside this session so we can mutate it
            db_user = await db.scalar(select(UserModel).where(UserModel.id == current_user.id))

            if not already_age_confirmed and age_confirmed and db_user:
                # Record age confirmation and stamp the user row
                await record_age_confirmation(db, db_user, ip_address=ip, user_agent=ua)
                # Sync back to request state so downstream checks see the updated flag
                current_user.age_confirmed_at = db_user.age_confirmed_at

            # Record sensitive data consents submitted this step
            for consent_type, submitted in [
                ("sensitive_data_photo", consent_photo),
                ("sensitive_data_dob", consent_dob),
                ("sensitive_data_document_id", consent_document_id),
            ]:
                if submitted:
                    await record_consent(
                        db,
                        user_id=user_id,
                        consent_type=consent_type,
                        granted=True,
                        email=current_user.email,
                        ip_address=ip,
                        user_agent=ua,
                        policy_version=CURRENT_POLICY_VERSION,
                    )

            await db.commit()

    update_attempt(
        attempt["id"],
        full_name=full_name.strip(),
        email=email.strip(),
        phone=normalize_phone(phone),
        visa_status=visa_status if include_work_rights else "",
        include_work_rights=bool(include_work_rights),
        nationality=nationality.strip(),
        marital_status=marital_status,
        references=references,
        step=3,
    )

    # ------------------------------------------------------------------
    # Persist identity fields + references to the PII vault so they
    # pre-fill on future wizard runs. step2() declares the vault is
    # authoritative for these fields, so writes here close the loop.
    # Voice fields move to step 3 (Personalization).
    # ------------------------------------------------------------------
    if user_id:
        from app.pii.adapters.vault import upsert_vault
        pii = request.state.session.get("pii") or {}
        pii["full_name"] = full_name.strip()
        pii["email"] = email.strip()
        pii["phone"] = normalize_phone(phone)
        pii["nationality"] = nationality.strip()
        pii["marital_status"] = marital_status
        pii["references"] = references
        password = request.state.session.get("_pii_password")
        async with async_session() as db:
            await upsert_vault(db, user_id=user_id, pii=pii, password=password or None)
        request.state.session["pii"] = pii

    return await step3(request)


# ------------------------------------------------------------------
# Job URL scraper (HTMX endpoint — returns HTML partial)
# ------------------------------------------------------------------

@router.post("/scrape-job")
async def scrape_job(request: Request, job_url: str = Form("")):
    """Scrape a job posting URL and return an HTML partial for HTMX."""
    from app.cv_generation.adapters.job_scraper import scrape_job_url

    result = await scrape_job_url(job_url)
    return templates.TemplateResponse("partials/wizard/job_scrape_result.html", {
        "request": request,
        "success": result["success"],
        "text": result["text"],
        "title": result["title"],
        "error": result["error"],
    })


# ------------------------------------------------------------------
# Step 3: Personalization (Professional Voice)
# ------------------------------------------------------------------

@router.get("/step/3")
async def step3_get(request: Request):
    if not _is_htmx(request):
        return _wizard_shell(request, 3)
    return await step3(request)


async def step3(request: Request):
    attempt = _get_or_create_attempt(request)
    region = attempt.get("region", "AU")
    region_config = REGIONS.get(region, REGIONS["AU"])

    # Voice fields fall back vault → empty when the attempt has no value,
    # so a per-CV voice seeded from a saved CV is preserved.
    pii = request.state.session.get("pii") or {}
    for key in ("self_description", "values"):
        if not attempt.get(key) and pii.get(key):
            attempt[key] = pii[key]

    return _step_response("partials/wizard/step3_personalization.html", {
        "request": request,
        "attempt": attempt,
        "region": region,
        "region_config": region_config,
        "dev_mode": request.app.state.dev_mode,
    }, step=3)


@router.post("/step/3/save")
async def step3_save(
    request: Request,
    self_description: str = Form(""),
    values: str = Form(""),
    offer_appeal: str = Form(""),
    featured_achievement: str = Form(""),
):
    """Save voice fields and move to step 4 (Job & CV)."""
    attempt = _get_or_create_attempt(request)
    update_attempt(
        attempt["id"],
        self_description=self_description,
        values=values,
        offer_appeal=offer_appeal,
        featured_achievement=featured_achievement,
        step=4,
    )

    # Persist voice → PII vault so they pre-fill on future wizard runs.
    # `offer_appeal` is intentionally excluded — it is role-specific.
    current_user = await get_current_user(request)
    if current_user:
        from app.pii.adapters.vault import upsert_vault
        pii = request.state.session.get("pii") or {}
        if self_description:
            pii["self_description"] = self_description
        if values:
            pii["values"] = values
        password = request.state.session.get("_pii_password")
        async with async_session() as db:
            await upsert_vault(db, user_id=current_user.id, pii=pii, password=password or None)
        request.state.session["pii"] = pii

    return RedirectResponse(url="/wizard/step/4", status_code=303)


# ------------------------------------------------------------------
# Step 4: Documents (job description + CV)
# ------------------------------------------------------------------

@router.get("/step/4")
async def step4_get(request: Request):
    if not _is_htmx(request):
        return _wizard_shell(request, 4)
    return await step4(request)


async def step4(request: Request):
    attempt = _get_or_create_attempt(request)
    cv_filename = get_document_filename(attempt["id"], "cv_file")
    region = attempt.get("region", "AU")
    region_config = REGIONS.get(region, REGIONS["AU"])
    pii = request.state.session.get("pii") or {}
    warnings = region_warnings_dicts(attempt, pii, region)
    return _step_response("partials/wizard/step4_documents.html", {
        "request": request,
        "attempt": attempt,
        "cv_filename": cv_filename,
        "region_config": region_config,
        "warnings": warnings,
    }, step=4)


@router.post("/step/4/save")
async def step4_save(
    request: Request,
    job_description: str = Form(""),
    cv_file: UploadFile = File(None),
    cv_text: str = Form(""),
    extra_docs: list[UploadFile] = File(None),
):
    """Save step 4 (documents + job description) and move to step 5 (template picker)."""
    attempt = _get_or_create_attempt(request)

    # Save CV file if provided, or fall back to pasted text
    cv_file_saved = False
    if cv_file and cv_file.filename:
        file_bytes = await cv_file.read()
        if file_bytes:
            save_document(attempt["id"], "cv_file", cv_file.filename, file_bytes)
            cv_file_saved = True

    if not cv_file_saved and cv_text.strip():
        save_document(attempt["id"], "cv_file", "experience.txt", cv_text.strip().encode("utf-8"))
        cv_file_saved = True

    if not cv_file_saved and not get_document_filename(attempt["id"], "cv_file"):
        region = attempt.get("region", "AU")
        region_config = REGIONS.get(region, REGIONS["AU"])
        pii = request.state.session.get("pii") or {}
        warnings = region_warnings_dicts(attempt, pii, region)
        return _step_response("partials/wizard/step4_documents.html", {
            "request": request,
            "attempt": attempt,
            "cv_filename": None,
            "region_config": region_config,
            "warnings": warnings,
            "error": "Please upload a CV file or describe your experience before continuing.",
        }, step=4)

    # Save extra documents
    if extra_docs:
        for i, doc in enumerate(extra_docs[:2]):
            if doc and doc.filename:
                doc_bytes = await doc.read()
                if doc_bytes:
                    save_document(attempt["id"], f"extra_doc_{i}", doc.filename, doc_bytes)

    job_description = job_description or attempt.get("job_description", "")
    update_attempt(attempt["id"], job_description=job_description, step=5)

    return await step5(request)


# ------------------------------------------------------------------
# Step 5: Template picker
# ------------------------------------------------------------------

@router.get("/step/5")
async def step5_get(request: Request):
    if not _is_htmx(request):
        return _wizard_shell(request, 5)
    return await step5(request)


async def step5(request: Request):
    attempt = _get_or_create_attempt(request)
    region = attempt.get("region", "AU")
    region_config = REGIONS.get(region, REGIONS["AU"])

    templates_list = list_templates(region=region)
    grouped: dict[str, list] = {}
    for tpl in templates_list:
        grouped.setdefault(tpl.category, []).append(tpl)

    cached_rec = attempt.get("template_recommendation")
    if cached_rec and cached_rec.get("templates"):
        recommended = cached_rec["templates"][:3]
        recommendation_reason = cached_rec.get("reason", "")
    else:
        recommended = [t.id for t in templates_list[:3]]
        recommendation_reason = ""

    return _step_response("partials/wizard/step5_template.html", {
        "request": request,
        "attempt": attempt,
        "region_config": region_config,
        "templates": templates_list,
        "grouped_templates": grouped,
        "recommended": recommended,
        "recommendation_reason": recommendation_reason,
    }, step=5)


@router.post("/step/5/save")
async def step5_save(request: Request, template_id: str = Form("modern")):
    attempt = _get_or_create_attempt(request)
    update_attempt(attempt["id"], template_id=template_id, step=6)
    return await step6(request)


# ------------------------------------------------------------------
# Step 6: Review & Generate
# ------------------------------------------------------------------

@router.get("/step/6")
async def step6_get(request: Request):
    if not _is_htmx(request):
        return _wizard_shell(request, 6)
    return await step6(request)


async def step6(request: Request):
    attempt = _get_or_create_attempt(request)
    region = attempt.get("region", "AU")
    region_config = REGIONS.get(region, REGIONS["AU"])
    cv_filename = get_document_filename(attempt["id"], "cv_file")

    # Check PII completeness based on region requirements
    pii = request.state.session.get("pii") or {}
    pii_complete, pii_missing = _check_pii_completeness(attempt, pii, region)
    pii_incomplete = not pii_complete
    warnings = region_warnings_dicts(attempt, pii, region)
    job_keywords = _extract_keywords(attempt.get("job_description", ""))

    return _step_response("partials/wizard/step6_review.html", {
        "request": request,
        "attempt": attempt,
        "region_config": region_config,
        "cv_filename": cv_filename,
        "pii_incomplete": pii_incomplete,
        "pii_missing": pii_missing,
        "warnings": warnings,
        "job_keywords": job_keywords,
    }, step=6)


# ------------------------------------------------------------------
# Region summary partial (for live update on step 1)
# ------------------------------------------------------------------

@router.get("/region-summary/{code}")
async def region_summary(request: Request, code: str):
    region_config = REGIONS.get(code, REGIONS["AU"])
    fields = _region_fields(code)
    return templates.TemplateResponse("partials/wizard/region_summary.html", {
        "request": request,
        "region_config": region_config,
        "fields": fields,
    })


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _extract_keywords(job_description: str, limit: int = 16) -> list[str]:
    """Extract likely keywords/skills from a job description."""
    import re
    text = job_description[:3000]
    patterns = [
        r'\b[A-Z][a-zA-Z]+(?:\.[a-zA-Z]+)+\b',  # dotted names: Node.js
        r'\b(?:Python|Ruby|Rails|JavaScript|TypeScript|React|Vue|Angular|Go|Rust|Java|Kotlin|Swift|PHP|C\+\+|C#|AWS|GCP|Azure|Docker|Kubernetes|PostgreSQL|MySQL|Redis|MongoDB|GraphQL|REST|API|CI/CD|TDD|Agile|Scrum|Git|Linux|DevOps|ML|AI|LLM|SaaS|B2B)\b',
    ]
    found: set[str] = set()
    for p in patterns:
        found.update(re.findall(p, text))
    word_freq: dict[str, int] = {}
    for w in re.findall(r'\b\w{4,}\b', text.lower()):
        word_freq[w] = word_freq.get(w, 0) + 1
    common = [w for w, c in sorted(word_freq.items(), key=lambda x: -x[1]) if c >= 2 and len(w) > 4][:8]
    result = list(found)[:limit // 2] + common[:limit // 2]
    return list(dict.fromkeys(result))[:limit]


def _hash(text: str) -> str:
    """Quick hash for cache invalidation."""
    import hashlib
    return hashlib.sha256(text.encode()).hexdigest()[:12]


async def _recommend_templates(llm, region: str, region_name: str, job_description: str) -> tuple[list[str], str]:
    """Use AI to recommend the best templates for the job description and region."""
    from app.infrastructure.llm.client import set_llm_context
    set_llm_context(service="template_recommender", inherit=True)

    available = list_templates(region=region)
    tpl_descriptions = "\n".join(
        f"- {t.id} [{t.category}]: {t.name} — {t.ai_description or t.description} "
        f"(Industries: {', '.join(t.industries) if t.industries else 'general'}, "
        f"Experience: {', '.join(t.experience_levels) if t.experience_levels else 'any'})"
        for t in available
    )

    prompt = f"""You are a CV formatting expert. Given a job description and target country, recommend the best CV templates from the available options.

Available templates for {region_name}:
{tpl_descriptions}

Target country: {region_name} ({region})

Job description:
{job_description[:3000]}

Respond with ONLY valid JSON, no markdown fences, no extra text:
{{"recommended": ["template_id_1", "template_id_2", "template_id_3"], "reason": "One sentence explaining why these templates suit this role and region."}}

Pick exactly 3 templates. The first should be the best match. Consider the candidate's likely industry and experience level based on the job description."""

    try:
        from app.cv_generation.schemas import TemplateRecommendationSchema
        from app.infrastructure.llm.parsing import parse_llm_json

        raw = (await llm.generate(prompt)).text
        parsed = parse_llm_json(raw, TemplateRecommendationSchema, context="wizard.template_rec")
        if parsed is not None:
            valid_ids = {t.id for t in available}
            recommended = [tid for tid in parsed.recommended if tid in valid_ids]
            if recommended:
                return recommended[:3], parsed.reason
    except Exception:
        logger.exception("AI template recommendation failed, using fallback")

    return ["modern", "classic", "professional"], "Modern is a versatile choice for most roles."
