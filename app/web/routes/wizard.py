import json
import logging

from fastapi import APIRouter, File, Form, Request, UploadFile

from app.consent.use_cases.record_consent import (
    CURRENT_POLICY_VERSION,
    get_client_ip,
    get_user_agent,
    record_age_confirmation,
    record_consent,
)
from app.cv_export.adapters.template_registry import REGIONS, list_regions, list_templates, list_templates_by_category
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
    if fields.get("visa") and not _has("visa_status"):
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


def _get_or_create_attempt(request: Request) -> dict:
    """Get the current attempt from session, or create a new one."""
    attempt_id = request.state.session.get("attempt_id")
    if attempt_id:
        attempt = get_attempt(attempt_id)
        if attempt:
            return attempt
    # Create new attempt
    attempt_id = create_attempt()
    request.state.session["attempt_id"] = attempt_id
    return get_attempt(attempt_id)


# ------------------------------------------------------------------
# Step 1: Country
# ------------------------------------------------------------------

@router.get("/step/1")
async def step1(request: Request):
    attempt = _get_or_create_attempt(request)
    # Pre-select from PII vault country when the attempt has no region yet.
    # Vault country codes match REGIONS keys (e.g. "AU", "US").
    pii = request.state.session.get("pii") or {}
    vault_country = pii.get("country", "")
    selected = attempt.get("region") or (vault_country if vault_country in REGIONS else "AU")
    return templates.TemplateResponse("partials/wizard/step1_country.html", {
        "request": request,
        "regions": list_regions(),
        "selected_region": selected,
        "region_config": REGIONS.get(selected, REGIONS["AU"]),
        "fields": _region_fields(selected),
    })


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
    """Navigate back to step 2 — re-fill from stored attempt."""
    return await step2(request)


async def step2(request: Request):
    attempt = _get_or_create_attempt(request)
    region = attempt.get("region", "AU")
    region_config = REGIONS.get(region, REGIONS["AU"])
    fields = _region_fields(region)
    current_user = await get_current_user(request)
    age_already_confirmed = bool(current_user and current_user.age_confirmed_at)

    # Merge PII vault values as defaults — attempt values always take priority
    pii = request.state.session.get("pii") or {}
    pii_prefilled = bool(pii)
    for key in ("full_name", "email", "phone", "dob", "document_id", "nationality", "marital_status",
                "self_description", "values"):
        if not attempt.get(key) and pii.get(key):
            attempt[key] = pii[key]

    # Merge vault references as defaults when the attempt has none yet
    if not attempt.get("references") and pii.get("references"):
        attempt["references"] = pii["references"]

    # Check PII completeness based on region requirements
    pii_complete, pii_missing = _check_pii_completeness(attempt, pii, region)
    pii_incomplete = not pii_complete

    return templates.TemplateResponse("partials/wizard/step2_details.html", {
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
    })


@router.post("/step/2/save")
async def step2_save(
    request: Request,
    full_name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    visa_status: str = Form(""),
    nationality: str = Form(""),
    marital_status: str = Form(""),
    self_description: str = Form(""),
    values: str = Form(""),
    offer_appeal: str = Form(""),
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
            "self_description": self_description,
            "values": values,
            "offer_appeal": offer_appeal,
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
        return templates.TemplateResponse("partials/wizard/step2_details.html", ctx)

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
        visa_status=visa_status,
        nationality=nationality.strip(),
        marital_status=marital_status,
        self_description=self_description,
        values=values,
        offer_appeal=offer_appeal,
        references=references,
        step=3,
    )

    # ------------------------------------------------------------------
    # Persist voice fields + references to the PII vault so they
    # pre-fill on future wizard runs.
    # `offer_appeal` is intentionally excluded — it is role-specific.
    # ------------------------------------------------------------------
    if user_id:
        from app.pii.adapters.vault import upsert_vault
        pii = request.state.session.get("pii") or {}
        pii["references"] = references
        if self_description:
            pii["self_description"] = self_description
        if values:
            pii["values"] = values
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
# Step 3: Documents
# ------------------------------------------------------------------

@router.get("/step/3")
async def step3_get(request: Request):
    return await step3(request)


async def step3(request: Request):
    attempt = _get_or_create_attempt(request)
    cv_filename = get_document_filename(attempt["id"], "cv_file")
    return templates.TemplateResponse("partials/wizard/step3_documents.html", {
        "request": request,
        "attempt": attempt,
        "cv_filename": cv_filename,
    })


@router.post("/step/3/save")
async def step3_save(
    request: Request,
    job_description: str = Form(""),
    cv_file: UploadFile = File(None),
    cv_text: str = Form(""),
    extra_docs: list[UploadFile] = File(None),
):
    """Save step 3 (documents + job description) and move to step 4."""
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
        return templates.TemplateResponse("partials/wizard/step3_documents.html", {
            "request": request,
            "attempt": attempt,
            "cv_filename": None,
            "error": "Please upload a CV file or describe your experience before continuing.",
        })

    # Save extra documents
    if extra_docs:
        for i, doc in enumerate(extra_docs[:2]):
            if doc and doc.filename:
                doc_bytes = await doc.read()
                if doc_bytes:
                    save_document(attempt["id"], f"extra_doc_{i}", doc.filename, doc_bytes)

    # Auto-select template: use cached AI recommendation or region default.
    job_description = job_description or attempt.get("job_description", "")
    region = attempt.get("region", "AU")
    cached_rec = attempt.get("template_recommendation")
    if cached_rec and cached_rec.get("job_hash") == _hash(job_description) and cached_rec.get("templates"):
        template_id = cached_rec["templates"][0]
    else:
        region_templates = list_templates(region=region)
        template_id = region_templates[0].id if region_templates else "modern"

    update_attempt(attempt["id"], job_description=job_description, template_id=template_id, step=4)

    return await step4(request)


# ------------------------------------------------------------------
# Step 4: Review & Generate  (was step 5 — template step removed)
# ------------------------------------------------------------------

@router.get("/step/4")
async def step4_get(request: Request):
    return await step4(request)


async def step4(request: Request):
    attempt = _get_or_create_attempt(request)
    region = attempt.get("region", "AU")
    region_config = REGIONS.get(region, REGIONS["AU"])
    cv_filename = get_document_filename(attempt["id"], "cv_file")

    # Check PII completeness based on region requirements
    pii = request.state.session.get("pii") or {}
    pii_complete, pii_missing = _check_pii_completeness(attempt, pii, region)
    pii_incomplete = not pii_complete

    return templates.TemplateResponse("partials/wizard/step5_review.html", {
        "request": request,
        "attempt": attempt,
        "region_config": region_config,
        "cv_filename": cv_filename,
        "pii_incomplete": pii_incomplete,
        "pii_missing": pii_missing,
    })


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
        raw = (await llm.generate(prompt)).text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            if raw.endswith("```"):
                raw = raw[:raw.rfind("```")]
            raw = raw.strip()
        result = json.loads(raw)
        valid_ids = {t.id for t in available}
        recommended = [tid for tid in result.get("recommended", []) if tid in valid_ids]
        reason = result.get("reason", "")
        if recommended:
            return recommended[:3], reason
    except Exception:
        logger.exception("AI template recommendation failed, using fallback")

    return ["modern", "classic", "professional"], "Modern is a versatile choice for most roles."
