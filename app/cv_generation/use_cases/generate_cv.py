"""CV generation pipeline use case.

Orchestrates the full pipeline: parse CV → extract keywords → ATS score →
AI generate → PII restore → render → review → persist.

This module is transport-agnostic — it does not know about HTTP or WebSockets.
Callers supply a ``ProgressCallback`` to receive step notifications.
"""

import asyncio
import logging
import re
import time
from collections.abc import Callable, Coroutine
from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.cv_export.adapters.template_registry import REGION_RULES, get_region, get_template
from app.cv_generation.adapters.anthropic_generator import generate_tailored_cv
from app.cv_generation.adapters.cover_letter_generator import generate_cover_letter
from app.cv_generation.adapters.generation_log import log_generation
from app.cv_generation.adapters.keyword_llm import extract_keywords_llm
from app.cv_generation.adapters.pdfplumber_parser import parse_cv
from app.cv_generation.adapters.quality_reviewer import review_cv_quality
from app.infrastructure.llm.client import set_llm_context
from app.infrastructure.persistence.attempt_store import (
    get_attempt,
    get_document_bytes,
    get_document_filename,
    update_attempt,
)
from app.infrastructure.persistence.cv_repo import save_cv
from app.infrastructure.persistence.database import async_session
from app.pii.use_cases.check_placeholders import check_placeholders
from app.pii.use_cases.redact_pii import PIIRedactor
from app.scoring.adapters.keyword_matcher import analyze_ats

logger = logging.getLogger(__name__)

import sys as _sys
_tpl_dir = Path(__file__).parent.parent.parent / "templates"
templates = Jinja2Templates(directory=_tpl_dir)
if _sys.version_info >= (3, 14):
    from jinja2 import Environment, FileSystemLoader
    templates.env = Environment(loader=FileSystemLoader(str(_tpl_dir)), autoescape=True, cache_size=0)

# Type alias for progress callback
ProgressCallback = Callable[[str, str], Coroutine]


async def _noop_progress(step: str, detail: str) -> None:
    """No-op progress callback for the HTTP endpoint."""
    pass


async def run_generation_pipeline(
    attempt_id: str,
    llm,
    llm_fast,
    on_progress: ProgressCallback = _noop_progress,
    user_id: str | None = None,
    pii: dict | None = None,
    pii_password: str | None = None,
) -> dict:
    """Shared CV generation pipeline used by both HTTP and WebSocket endpoints.

    Returns a dict with all data needed to render results, or raises an exception.
    Keys: ats_original, ats_generated, generated_cv, cv_text, template,
          region, region_rules, quality_review, timings.
    """
    import uuid as _uuid_mod

    logger.info("Pipeline[%s] START user=%s", attempt_id, user_id)

    pipeline_transaction_id = _uuid_mod.uuid4().hex
    set_llm_context(
        service="pipeline",
        attempt_id=attempt_id,
        user_id=user_id,
        transaction_id=pipeline_transaction_id,
    )

    attempt = get_attempt(attempt_id)
    if not attempt:
        logger.info("Pipeline[%s] FAIL: session expired — attempt not found", attempt_id)
        raise ValueError("Session expired. Please start again.")

    cv_bytes = get_document_bytes(attempt_id, "cv_file")
    cv_filename = get_document_filename(attempt_id, "cv_file")
    logger.info("Pipeline[%s] attempt loaded: cv_file=%s filename=%s", attempt_id, "yes" if cv_bytes else "NO", cv_filename)
    if not cv_bytes or not cv_filename:
        logger.info("Pipeline[%s] FAIL: no CV file found", attempt_id)
        raise ValueError("No CV file found. Please go back to step 3 and upload your CV.")

    timings = {}

    # 1. Parse CV
    await on_progress("Reading your CV", "Parsing document structure")
    t0 = time.monotonic()
    cv_text = parse_cv(cv_filename, cv_bytes)
    timings["parse_cv"] = round(time.monotonic() - t0, 2)
    logger.info("Pipeline[%s] step=parse_cv duration=%.2fs chars=%d", attempt_id, timings["parse_cv"], len(cv_text))

    if not cv_text.strip():
        raise ValueError("Could not extract text from the CV file.")

    # PII redaction — replace name/email/phone with tokens before sending to AI
    full_name = attempt.get("full_name", "").strip()
    redactor = PIIRedactor(
        full_name=full_name,
        dob=pii.get("dob", "") if pii else "",
        document_id=pii.get("document_id", "") if pii else "",
        references=pii.get("references", []) if pii else [],
        linkedin_url=pii.get("linkedin", "") if pii else "",
        github_url=pii.get("github", "") if pii else "",
    ) if full_name else None
    if redactor:
        cv_text_for_llm = redactor.redact(cv_text)
    else:
        cv_text_for_llm = cv_text

    # Get settings
    region_code = attempt.get("region", "AU")
    template_id = attempt.get("template_id", "modern")
    job_description = attempt.get("job_description", "")

    # 2. Extract keywords
    await on_progress("Scanning the job description", "Extracting keywords & requirements")
    t0 = time.monotonic()
    keyword_data = await extract_keywords_llm(job_description, llm_fast)
    if keyword_data:
        job_keywords = keyword_data["all_keywords"]
        keyword_categories = keyword_data["categories"]
        update_attempt(attempt_id, extracted_keywords=keyword_data)
    else:
        job_keywords = None
        keyword_categories = None
    timings["keyword_extraction"] = round(time.monotonic() - t0, 2)
    logger.info("Pipeline[%s] step=keywords duration=%.2fs found=%d", attempt_id, timings["keyword_extraction"], len(job_keywords) if job_keywords else 0)

    # 3. ATS analysis on original
    await on_progress("Running ATS check", "Scoring your original CV")
    t0 = time.monotonic()
    ats_result = analyze_ats(cv_text, job_description, keywords_override=job_keywords)
    timings["ats_original"] = round(time.monotonic() - t0, 2)
    logger.info("Pipeline[%s] step=ats_original duration=%.2fs score=%d", attempt_id, timings["ats_original"], ats_result.score)

    # Get template and region info
    selected_template = get_template(template_id) or get_template("modern")
    region_config = get_region(region_code) or get_region("US")
    region_rules = REGION_RULES.get(region_code, REGION_RULES["US"])

    # 4. Generate tailored CV (the slow step)
    await on_progress("Writing your new CV", "AI at work — this is the big one")
    t0 = time.monotonic()
    cv_data = await generate_tailored_cv(
        cv_text_for_llm, job_description, ats_result.missing_keywords,
        region=region_config, llm=llm, attempt=attempt,
        ats_result=ats_result, keyword_categories=keyword_categories,
    )
    timings["ai_generate"] = round(time.monotonic() - t0, 2)
    logger.info("Pipeline[%s] step=ai_generate duration=%.2fs success=%s", attempt_id, timings["ai_generate"], cv_data is not None)

    if cv_data is None:
        import hashlib as _hashlib
        _input_len = len(cv_text_for_llm) + len(job_description)
        _last_char_hash = _hashlib.sha256(cv_text_for_llm[-64:].encode(errors="replace")).hexdigest()[:8]
        logger.error(
            "Pipeline[%s] generate_tailored_cv returned None — "
            "input_chars=%d last_char_hash=%s model=%s duration=%.2fs",
            attempt_id, _input_len, _last_char_hash,
            getattr(llm, "model", "unknown"), timings["ai_generate"],
        )
        raise ValueError("CV generation failed. Please try again.")

    # Restore real PII values from tokens
    if redactor:
        cv_data = redactor.restore(cv_data)

    # Quality gate — catch any leftover placeholders
    placeholder_issues = check_placeholders(cv_data)
    if placeholder_issues:
        logger.warning(
            "Placeholder issues in generated CV (attempt=%s): %s",
            attempt_id, placeholder_issues,
        )

    # 5. Render template
    await on_progress("Rendering the template", "Laying out your final design")
    llm_usage = cv_data.pop("_llm_usage", {})
    rendered_cv = templates.get_template(
        f"cv_templates/{template_id}.html"
    ).render(**cv_data)
    cv_data["_llm_usage"] = llm_usage
    logger.info("Pipeline[%s] step=render template=%s html_len=%d", attempt_id, template_id, len(rendered_cv))

    # 5b. Generate cover letter
    await on_progress("Writing your cover letter", "Crafting a tailored cover letter")
    t0 = time.monotonic()
    cover_letter_data = await generate_cover_letter(
        cv_data=cv_data,
        job_description=job_description,
        region=region_config,
        llm=llm,
        attempt=attempt,
        keyword_categories=keyword_categories,
    )
    timings["cover_letter"] = round(time.monotonic() - t0, 2)
    logger.info(
        "Pipeline[%s] step=cover_letter duration=%.2fs success=%s",
        attempt_id, timings["cover_letter"], cover_letter_data is not None,
    )

    # Restore PII in cover letter
    if cover_letter_data and redactor:
        cover_letter_data = redactor.restore(cover_letter_data)

    # Render cover letter HTML (simple template)
    cover_letter_html = None
    if cover_letter_data:
        cl_llm_usage = cover_letter_data.pop("_llm_usage", {})
        try:
            cover_letter_html = templates.get_template(
                "cover_letter_templates/formal.html"
            ).render(**cover_letter_data)
        except Exception:
            logger.exception("Pipeline[%s] Cover letter template render failed", attempt_id)
        cover_letter_data["_llm_usage"] = cl_llm_usage

    # 6. ATS + quality review in parallel
    await on_progress("Final ATS comparison", "Scoring the result and reviewing quality")
    t0 = time.monotonic()
    generated_text = re.sub(r'<style[^>]*>.*?</style>', '', rendered_cv, flags=re.DOTALL)
    generated_text = re.sub(r'<[^>]+>', ' ', generated_text)
    generated_text = re.sub(r'\s+', ' ', generated_text).strip()

    async def _ats():
        return analyze_ats(generated_text, job_description, keywords_override=job_keywords)

    async def _review():
        return await review_cv_quality(
            cv_data, job_description,
            region_name=region_config.name, llm=llm_fast,
        )

    ats_generated, quality_review = await asyncio.gather(_ats(), _review())
    timings["ats_generated"] = round(time.monotonic() - t0, 2)
    logger.info("Pipeline[%s] step=ats_review duration=%.2fs ats_score=%d review=%s", attempt_id, timings["ats_generated"], ats_generated.score, "ok" if quality_review else "failed")

    # Log generation
    log_generation(
        attempt_id=attempt_id,
        region=region_code,
        template_id=template_id,
        cv_text=cv_text,
        job_description=job_description,
        ats_original=ats_result,
        ats_generated=ats_generated,
        generated_text=generated_text,
        cv_data=cv_data,
        timings=timings,
    )

    from app.infrastructure.instrumentation import record_custom_event
    record_custom_event("CVGeneration", {
        "user_id": user_id,
        "attempt_id": attempt_id,
        "region": region_code,
        "template_id": template_id,
        "score_original": ats_result.score,
        "score_generated": ats_generated.score,
        "duration_sec": sum(timings.values()),
    })

    # Cache results
    review_flags = quality_review.get("flags", []) if quality_review else []
    update_attempt(
        attempt_id,
        cv_data=cv_data,
        rendered_cv=rendered_cv,
        cover_letter_data=cover_letter_data,
        cover_letter_html=cover_letter_html,
        cv_text_preview=cv_text[:500],
        quality_review_flags=review_flags,
    )

    # Backfill PII vault with values from generated CV data that are missing.
    # This ensures <<PHONE_1>>, <<EMAIL_1>> etc. tokens can be restored on load.
    if pii and user_id:
        backfill_map = {
            "phone": "phone",
            "email": "email",
            "location": "location",
            "linkedin": "linkedin",
            "github": "github",
            "portfolio": "portfolio",
        }
        vault_updated = False
        for pii_key, cv_key in backfill_map.items():
            if not pii.get(pii_key) and cv_data.get(cv_key):
                pii[pii_key] = cv_data[cv_key]
                vault_updated = True
        if vault_updated:
            try:
                from app.pii.adapters.vault import upsert_vault
                async with async_session() as db:
                    await upsert_vault(db, user_id=user_id, pii=pii, password=pii_password)
                logger.info("Pipeline[%s] PII vault backfilled for user_id=%s", attempt_id, user_id)
            except Exception:
                logger.exception("Pipeline[%s] Failed to backfill PII vault", attempt_id)

    # Persist CV as sanitized markdown for reuse
    try:
        async with async_session() as db:
            await save_cv(
                db,
                attempt_id=attempt_id,
                source="ai",
                region=region_code,
                template_id=template_id,
                rendered_html=rendered_cv,
                cv_data=cv_data,
                user_id=user_id,
            )
    except Exception:
        logger.exception("Failed to save CV to database (attempt=%s)", attempt_id)

    logger.info("Pipeline[%s] COMPLETE timings=%s", attempt_id, timings)
    return {
        "ats_original": ats_result,
        "ats_generated": ats_generated,
        "generated_cv": rendered_cv,
        "cover_letter": cover_letter_html,
        "cover_letter_data": cover_letter_data,
        "cv_text": cv_text[:500],
        "template": selected_template,
        "region": region_code,
        "region_rules": region_rules,
        "quality_review": quality_review,
    }
