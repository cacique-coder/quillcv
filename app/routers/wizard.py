import json
import logging
from pathlib import Path

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.templating import Jinja2Templates

from app.services.attempt_store import (
    create_attempt,
    get_attempt,
    get_document_filename,
    save_document,
    update_attempt,
)
from app.services.template_registry import REGIONS, list_regions, list_templates, list_templates_by_category

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/wizard")
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


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


def _get_or_create_attempt(request: Request) -> dict:
    """Get the current attempt from session, or create a new one."""
    attempt_id = request.session.get("attempt_id")
    if attempt_id:
        attempt = get_attempt(attempt_id)
        if attempt:
            return attempt
    # Create new attempt
    attempt_id = create_attempt()
    request.session["attempt_id"] = attempt_id
    return get_attempt(attempt_id)


# ------------------------------------------------------------------
# Step 1: Country
# ------------------------------------------------------------------

@router.get("/step/1")
async def step1(request: Request):
    attempt = _get_or_create_attempt(request)
    selected = attempt.get("region", "AU")
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
    return templates.TemplateResponse("partials/wizard/step2_details.html", {
        "request": request,
        "attempt": attempt,
        "region": region,
        "region_config": region_config,
        "fields": fields,
        "dev_mode": request.app.state.dev_mode,
    })


@router.post("/step/2/save")
async def step2_save(
    request: Request,
    full_name: str = Form(""),
    visa_status: str = Form(""),
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
):
    """Save step 2 and move to step 3."""
    attempt = _get_or_create_attempt(request)

    # Build references list from form fields
    references = []
    for _i, (name, title, company, email, phone) in enumerate([
        (ref_name_1, ref_title_1, ref_company_1, ref_email_1, ref_phone_1),
        (ref_name_2, ref_title_2, ref_company_2, ref_email_2, ref_phone_2),
    ], 1):
        if name.strip():
            references.append({
                "name": name, "title": title, "company": company,
                "email": email, "phone": phone,
            })

    if not full_name.strip():
        # Re-render step 2 with validation error
        region = attempt.get("region", "AU")
        region_config = REGIONS.get(region, REGIONS["AU"])
        fields = _region_fields(region)
        return templates.TemplateResponse("partials/wizard/step2_details.html", {
            "request": request,
            "attempt": {**attempt, "full_name": full_name},
            "region": region,
            "region_config": region_config,
            "fields": fields,
            "dev_mode": request.app.state.dev_mode,
            "error": "Your full name is required — we use it to protect your privacy during AI generation.",
        })

    update_attempt(
        attempt["id"],
        full_name=full_name.strip(),
        visa_status=visa_status,
        self_description=self_description,
        values=values,
        offer_appeal=offer_appeal,
        references=references,
        step=3,
    )
    return await step3(request)


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
    extra_docs: list[UploadFile] = File(None),
):
    """Save step 3 (documents + job description) and move to step 4."""
    attempt = _get_or_create_attempt(request)

    # Save CV file if provided (or keep existing)
    if cv_file and cv_file.filename:
        file_bytes = await cv_file.read()
        if file_bytes:
            save_document(attempt["id"], "cv_file", cv_file.filename, file_bytes)

    # Save extra documents
    if extra_docs:
        for i, doc in enumerate(extra_docs[:2]):
            if doc and doc.filename:
                doc_bytes = await doc.read()
                if doc_bytes:
                    save_document(attempt["id"], f"extra_doc_{i}", doc.filename, doc_bytes)

    update_attempt(attempt["id"], job_description=job_description, step=4)

    # Now go to step 4 (template recommendation via AI)
    return await step4(request)


# ------------------------------------------------------------------
# Step 4: Template (AI-powered recommendation)
# ------------------------------------------------------------------

@router.get("/step/4")
async def step4_get(request: Request):
    return await step4(request)


async def step4(request: Request):
    attempt = _get_or_create_attempt(request)
    region = attempt.get("region", "AU")
    region_config = REGIONS.get(region, REGIONS["AU"])
    job_description = attempt.get("job_description", "")

    # Filter templates by region
    available_templates = list_templates(region=region)

    # Check if we already have a cached AI recommendation for this job description
    cached_rec = attempt.get("template_recommendation")
    if cached_rec and cached_rec.get("job_hash") == _hash(job_description):
        recommended = cached_rec["templates"]
        recommendation_reason = cached_rec["reason"]
    else:
        # Call AI for recommendation (fast model — lightweight task)
        from app.services.llm_client import set_llm_context
        user = request.state.user
        set_llm_context(
            service="template_recommender",
            attempt_id=attempt.get("id"),
            user_id=user.id if user else None,
        )
        llm = request.app.state.llm_fast
        recommended, recommendation_reason = await _recommend_templates(
            llm, region, region_config.name, job_description
        )
        # Cache the result
        update_attempt(attempt["id"], template_recommendation={
            "templates": recommended,
            "reason": recommendation_reason,
            "job_hash": _hash(job_description),
        })

    # Group templates by category for UI
    categories = ["universal", "industry", "region", "specialty"]
    grouped = {}
    available_ids = {t.id for t in available_templates}
    for cat in categories:
        cat_templates = [t for t in list_templates_by_category(cat) if t.id in available_ids]
        if cat_templates:
            grouped[cat] = cat_templates

    return templates.TemplateResponse("partials/wizard/step4_template.html", {
        "request": request,
        "attempt": attempt,
        "region": region,
        "region_config": region_config,
        "templates": available_templates,
        "grouped_templates": grouped,
        "recommended": recommended,
        "recommendation_reason": recommendation_reason,
    })


@router.post("/step/4/save")
async def step4_save(request: Request, template_id: str = Form("modern")):
    """Save template selection and move to step 5."""
    attempt = _get_or_create_attempt(request)
    update_attempt(attempt["id"], template_id=template_id, step=5)
    return await step5(request)


# ------------------------------------------------------------------
# Step 5: Review & Generate
# ------------------------------------------------------------------

@router.get("/step/5")
async def step5_get(request: Request):
    return await step5(request)


async def step5(request: Request):
    attempt = _get_or_create_attempt(request)
    region = attempt.get("region", "AU")
    region_config = REGIONS.get(region, REGIONS["AU"])
    cv_filename = get_document_filename(attempt["id"], "cv_file")

    return templates.TemplateResponse("partials/wizard/step5_review.html", {
        "request": request,
        "attempt": attempt,
        "region_config": region_config,
        "cv_filename": cv_filename,
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
    from app.services.llm_client import set_llm_context
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
