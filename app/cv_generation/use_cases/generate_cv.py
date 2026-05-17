"""CV generation pipeline use case.

Orchestrates the full pipeline: parse CV → extract keywords → ATS score →
AI generate → PII restore → render → review → persist.

This module is transport-agnostic — it does not know about HTTP or WebSockets.
Callers supply a ``ProgressCallback`` to receive step notifications.
"""

import asyncio
import json
import logging
import re
import time
from collections.abc import Callable, Coroutine
from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.cv_export.adapters.template_registry import REGION_RULES, get_region, get_template
from app.cv_generation.adapters.anthropic_generator import categorize_missing_keywords, generate_tailored_cv
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


def _derive_cv_label(attempt: dict, cover_letter_data: dict | None) -> tuple[str, str]:
    """Derive (label, job_title) for the SavedCV row from job context.

    Priority:
      1. company_name from cover letter (most reliable when CL was generated)
      2. first non-empty line of job_description (cleaned of common prefixes)
      3. fall back to a generic "Tailored CV" label
    """
    company = ""
    if cover_letter_data:
        company = (cover_letter_data.get("company_name") or "").strip()

    job_desc = (attempt.get("job_description") or "").strip()
    first_line = ""
    for line in job_desc.splitlines():
        s = line.strip()
        if s:
            first_line = s
            break
    for prefix in ("Job Title:", "Job:", "Role:", "Position:", "Page:", "Title:"):
        if first_line.lower().startswith(prefix.lower()):
            first_line = first_line[len(prefix):].strip()
            break
    first_line = first_line[:80]

    if company and first_line:
        label = f"{company} — {first_line[:60]}"
    elif company:
        label = company
    elif first_line:
        label = first_line
    else:
        label = "Tailored CV"

    return label[:255], first_line[:255]


import sys as _sys
_tpl_dir = Path(__file__).parent.parent.parent / "templates"
templates = Jinja2Templates(directory=_tpl_dir)
if _sys.version_info >= (3, 14):
    from jinja2 import Environment, FileSystemLoader
    templates.env = Environment(loader=FileSystemLoader(str(_tpl_dir)), autoescape=True, cache_size=0)

# Type alias for progress callback
ProgressCallback = Callable[[str, str], Coroutine]


def _cached(attempt: dict, key: str):
    """Return cached value at ``key`` if non-empty, else None.

    For dicts/lists, non-empty means at least one entry.
    For strings, strips whitespace before testing truthiness.
    """
    val = attempt.get(key)
    if val is None:
        return None
    if isinstance(val, str):
        return val if val.strip() else None
    if isinstance(val, (dict, list)):
        return val if val else None
    return val


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

    # 1. Parse CV (cheap — always run)
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

    # 2. Extract keywords — skip if cached
    await on_progress("Scanning the job description", "Extracting keywords & requirements")
    cached_keywords = _cached(attempt, "extracted_keywords")
    if cached_keywords and cached_keywords.get("all_keywords"):
        keyword_data = cached_keywords
        job_keywords = keyword_data["all_keywords"]
        keyword_categories = keyword_data["categories"]
        logger.info("Pipeline[%s] step=keywords cached", attempt_id)
        timings["keyword_extraction"] = 0.0
    else:
        t0 = time.monotonic()
        keyword_data = await extract_keywords_llm(job_description, llm_fast)
        timings["keyword_extraction"] = round(time.monotonic() - t0, 2)
        if keyword_data:
            job_keywords = keyword_data["all_keywords"]
            keyword_categories = keyword_data["categories"]
            update_attempt(attempt_id, extracted_keywords=keyword_data)
        else:
            job_keywords = None
            keyword_categories = None
        logger.info("Pipeline[%s] step=keywords duration=%.2fs found=%d", attempt_id, timings["keyword_extraction"], len(job_keywords) if job_keywords else 0)

    # 3. ATS analysis on original (sync, ~0s — always recompute)
    await on_progress("Running ATS check", "Scoring your original CV")
    t0 = time.monotonic()
    ats_result = analyze_ats(cv_text, job_description, keywords_override=job_keywords)
    timings["ats_original"] = round(time.monotonic() - t0, 2)
    logger.info("Pipeline[%s] step=ats_original duration=%.2fs score=%d", attempt_id, timings["ats_original"], ats_result.score)

    # Get template and region info
    selected_template = get_template(template_id) or get_template("modern")
    region_config = get_region(region_code) or get_region("US")
    region_rules = REGION_RULES.get(region_code, REGION_RULES["US"])

    # 4. Generate tailored CV — skip if cached
    await on_progress("Writing your new CV", "AI at work — this is the big one")
    cached_cv_data = _cached(attempt, "cv_data")
    cached_rendered_cv = _cached(attempt, "rendered_cv")
    if cached_cv_data and cached_rendered_cv:
        cv_data = cached_cv_data
        rendered_cv = cached_rendered_cv
        logger.info("Pipeline[%s] step=ai_generate cached", attempt_id)
        timings["ai_generate"] = 0.0

        # Self-healing: if the candidate filled in references after the LLM
        # ran (or the LLM dropped them on the original run), reinstate them
        # and re-render the template only. No LLM call needed — references
        # are pure user input.
        attempt_refs = attempt.get("references") or []
        cached_refs = cv_data.get("references") or []
        refs_changed = (
            bool(attempt_refs)
            and [(r.get("name"), r.get("email")) for r in attempt_refs]
            != [(r.get("name"), r.get("email")) for r in cached_refs]
        )
        if refs_changed:
            cv_data["references"] = [dict(r) for r in attempt_refs if isinstance(r, dict)]
            llm_usage = cv_data.pop("_llm_usage", {})
            rendered_cv = templates.get_template(
                f"cv_templates/{template_id}.html"
            ).render(**cv_data)
            cv_data["_llm_usage"] = llm_usage
            update_attempt(attempt_id, cv_data=cv_data, rendered_cv=rendered_cv)
            logger.info(
                "Pipeline[%s] step=render refs_resynced count=%d",
                attempt_id, len(attempt_refs),
            )
        # Placeholder check still runs so warnings surface on resumed runs
        placeholder_issues = check_placeholders(cv_data)
        if placeholder_issues:
            logger.warning(
                "Placeholder issues in cached CV (attempt=%s): %s",
                attempt_id, placeholder_issues,
            )
    else:
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

        # Prefill identity fields from known PII so the generated CV never
        # contains empty or placeholder values for data the platform already has.
        # The PII vault is the authoritative source; the LLM output is secondary.
        _pii_identity_map = {
            "full_name": "name",   # User.name / vault full_name → cv_data.name
            "email":     "email",
            "phone":     "phone",
            "linkedin":  "linkedin",
            "github":    "github",
            "portfolio": "portfolio",
            "location":  "location",
        }
        _pii_source = pii or {}
        # Also treat attempt["full_name"] as authoritative for the name field
        # (it is set at step-2 from the wizard form before any LLM run).
        _attempt_full_name = (attempt.get("full_name") or "").strip()
        if _attempt_full_name:
            _pii_source = {**_pii_source, "full_name": _attempt_full_name}

        _placeholder_tokens = {
            "<<CANDIDATE_NAME>>", "<<EMAIL_1>>", "<<PHONE_1>>",
            "<<LINKEDIN_URL>>", "<<GITHUB_URL>>", "<<PORTFOLIO_URL>>",
            "<<LOCATION>>",
        }

        for _pii_key, _cv_key in _pii_identity_map.items():
            _real_val = (_pii_source.get(_pii_key) or "").strip()
            if not _real_val:
                continue
            _existing = (cv_data.get(_cv_key) or "").strip()
            # Overwrite if: empty, a redaction token, or a bracket placeholder
            _is_placeholder = (
                not _existing
                or _existing in _placeholder_tokens
                or (_existing.startswith("[") and _existing.endswith("]"))
            )
            if _is_placeholder:
                cv_data[_cv_key] = _real_val
                logger.info(
                    "Pipeline[%s] prefilled cv_data.%s from PII vault",
                    attempt_id, _cv_key,
                )

        # Make sure user-provided references survive even if the LLM dropped
        # the references array from its JSON output. The candidate filled
        # these in at step 2; they're authoritative — the LLM has no business
        # arbitrating whether they appear on the CV. If the model did echo
        # them back, prefer the candidate's version anyway (LLM occasionally
        # reformats name/title in ways the user didn't intend).
        attempt_refs = attempt.get("references") if attempt else None
        if attempt_refs:
            cv_data["references"] = [dict(r) for r in attempt_refs if isinstance(r, dict)]

        # Quality gate — catch any leftover placeholders
        placeholder_issues = check_placeholders(cv_data)
        if placeholder_issues:
            logger.warning(
                "Placeholder issues in generated CV (attempt=%s): %s",
                attempt_id, placeholder_issues,
            )

        # Structural sanity log
        logger.info(
            "Pipeline[%s] cv_data_shape title=%r summary_chars=%d experience=%d "
            "skills=%d skills_grouped=%d education=%d certifications=%d projects=%d",
            attempt_id,
            (cv_data.get("title") or "")[:80],
            len((cv_data.get("summary") or "")),
            len(cv_data.get("experience") or []),
            len(cv_data.get("skills") or []),
            len(cv_data.get("skills_grouped") or []),
            len(cv_data.get("education") or []),
            len(cv_data.get("certifications") or []),
            len(cv_data.get("projects") or []),
        )

        # 5. Render template
        await on_progress("Rendering the template", "Laying out your final design")
        llm_usage = cv_data.pop("_llm_usage", {})
        rendered_cv = templates.get_template(
            f"cv_templates/{template_id}.html"
        ).render(**cv_data)
        cv_data["_llm_usage"] = llm_usage

        # Persist cv_data + rendered_cv immediately so a crash in the parallel
        # block doesn't force a re-run of the expensive generation step.
        update_attempt(attempt_id, cv_data=cv_data, rendered_cv=rendered_cv)

    logger.info("Pipeline[%s] step=render template=%s html_len=%d", attempt_id, template_id, len(rendered_cv))

    # 5b. Strip HTML → plain text for ATS scoring (sync, instant — always recompute)
    generated_text = re.sub(r'<style[^>]*>.*?</style>', '', rendered_cv, flags=re.DOTALL)
    generated_text = re.sub(r'<[^>]+>', ' ', generated_text)
    generated_text = re.sub(r'\s+', ' ', generated_text).strip()

    # ATS score on generated CV — sync, no LLM, always recompute
    t0 = time.monotonic()
    ats_generated = analyze_ats(generated_text, job_description, keywords_override=job_keywords)
    timings["ats_generated"] = round(time.monotonic() - t0, 2)
    logger.info("Pipeline[%s] step=ats_generated duration=%.2fs score=%d", attempt_id, timings["ats_generated"], ats_generated.score)

    # 6. Cover letter + quality review + keyword categorisation in parallel
    # Only enqueue tasks whose results are not already cached.
    await on_progress("Polishing the result", "Cover letter, quality review and keyword grouping running together")

    async def _timed(key: str, coro):
        """Run *coro*, record its wall-time to ``timings[key]``, return result."""
        _t = time.monotonic()
        result = await coro
        timings[key] = round(time.monotonic() - _t, 2)
        return result

    # --- Cover letter ---
    # Gated by the `cover_letter` feature flag — when off, skip generation
    # entirely and surface results without the Cover Letter tab. The flag
    # was added because cover-letter prompts have been timing out via the
    # local claude CLI; see app/features.py.
    from app.features import is_enabled as _flag_enabled

    cover_letter_enabled = _flag_enabled("cover_letter")
    cover_letter_data = None
    cover_letter_html = None
    cached_cl_data = _cached(attempt, "cover_letter_data") if cover_letter_enabled else None
    if not cover_letter_enabled:
        logger.info("Pipeline[%s] step=cover_letter skipped (flag off)", attempt_id)
        run_cover_letter = False
    elif cached_cl_data:
        cover_letter_data = cached_cl_data
        cover_letter_html = attempt.get("cover_letter_html")
        logger.info("Pipeline[%s] step=cover_letter cached", attempt_id)
        run_cover_letter = False
    else:
        run_cover_letter = True

    # --- Quality review ---
    cached_review = _cached(attempt, "quality_review")
    if cached_review:
        quality_review = cached_review
        logger.info("Pipeline[%s] step=quality_review cached", attempt_id)
        run_review = False
    else:
        run_review = True

    # --- Categorize missing keywords ---
    cached_groups = _cached(attempt, "missing_keyword_groups")
    if cached_groups:
        missing_keyword_groups = cached_groups
        logger.info("Pipeline[%s] step=categorize_missing cached", attempt_id)
        run_categorize = False
    else:
        run_categorize = True

    async def _safe_cover_letter():
        try:
            result = await generate_cover_letter(
                cv_data=cv_data,
                job_description=job_description,
                region=region_config,
                llm=llm,
                attempt=attempt,
                keyword_categories=keyword_categories,
            )
        except Exception:
            logger.exception("Pipeline[%s] generate_cover_letter raised unexpectedly", attempt_id)
            result = None
        # Restore PII before persisting
        if result and redactor:
            result = redactor.restore(result)
        # Render cover letter HTML
        cl_html = None
        if result:
            cl_llm_usage = result.pop("_llm_usage", {})
            try:
                cl_html = templates.get_template(
                    "cover_letter_templates/formal.html"
                ).render(**result)
            except Exception:
                logger.exception("Pipeline[%s] Cover letter template render failed", attempt_id)
            result["_llm_usage"] = cl_llm_usage
        update_attempt(attempt_id, cover_letter_data=result, cover_letter_html=cl_html)
        return result, cl_html

    async def _run_review():
        result = await review_cv_quality(
            cv_data, job_description,
            region_name=region_config.name, llm=llm_fast,
        )
        update_attempt(
            attempt_id,
            quality_review=result,
            quality_review_flags=result.get("flags", []) if result else [],
        )
        return result

    async def _run_categorize():
        result = await categorize_missing_keywords(
            ats_generated.missing_keywords[:30],
            cv_data.get("skills_grouped") or [],
            llm_fast,
        )
        update_attempt(attempt_id, missing_keyword_groups=result)
        return result

    # Build task list from only the steps that still need to run
    parallel_tasks = []
    task_keys = []
    if run_cover_letter:
        parallel_tasks.append(_timed("cover_letter", _safe_cover_letter()))
        task_keys.append("cover_letter")
    if run_review:
        parallel_tasks.append(_timed("quality_review", _run_review()))
        task_keys.append("quality_review")
    if run_categorize:
        parallel_tasks.append(_timed("categorize_missing", _run_categorize()))
        task_keys.append("categorize_missing")

    parallel_t0 = time.monotonic()
    if parallel_tasks:
        gather_results = await asyncio.gather(*parallel_tasks)
        # Unpack results back to named variables
        result_iter = iter(gather_results)
        if run_cover_letter:
            cover_letter_data, cover_letter_html = next(result_iter)
        if run_review:
            quality_review = next(result_iter)
        if run_categorize:
            missing_keyword_groups = next(result_iter)
    timings["parallel_block"] = round(time.monotonic() - parallel_t0, 2)

    if run_cover_letter:
        logger.info(
            "Pipeline[%s] step=cover_letter duration=%.2fs success=%s",
            attempt_id, timings["cover_letter"], cover_letter_data is not None,
        )
    if run_review:
        logger.info(
            "Pipeline[%s] step=quality_review duration=%.2fs review=%s",
            attempt_id, timings["quality_review"], "ok" if quality_review else "failed",
        )
    if run_categorize:
        logger.info(
            "Pipeline[%s] step=categorize_missing duration=%.2fs mapped=%d",
            attempt_id, timings["categorize_missing"], len(missing_keyword_groups),
        )
    logger.info(
        "Pipeline[%s] step=parallel_block wall_time=%.2fs", attempt_id, timings["parallel_block"],
    )

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

    # Persist cv_text_preview (the only field not written by an inline step above)
    update_attempt(attempt_id, cv_text_preview=cv_text[:500])

    # Backfill PII vault with values from generated CV data that are missing.
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

    # Derive label/job_title once for both Job and SavedCV persistence
    label, job_title = _derive_cv_label(attempt, cover_letter_data)

    # Persist Job row (encrypted artefacts) for logged-in users so the
    # cover letter survives session expiry and `/my-cvs` can link to it.
    job_id: str | None = None
    if user_id:
        try:
            from app.infrastructure.persistence.job_repo import create_job, update_job
            company_name = ""
            if cover_letter_data:
                company_name = (cover_letter_data.get("company_name") or "").strip()
            async with async_session() as db:
                job = await create_job(
                    db,
                    user_id=user_id,
                    job_description=job_description,
                    region=region_code,
                    job_url=attempt.get("job_url", "") or "",
                    job_title=job_title,
                    company_name=company_name,
                    offer_appeal=attempt.get("offer_appeal", "") or "",
                    template_id=template_id,
                )
                update_fields: dict = {
                    "cv_data_json": json.dumps(
                        {k: v for k, v in cv_data.items() if not k.startswith("_")},
                        default=str,
                    ),
                    "cv_rendered_html": rendered_cv,
                    "status": "complete",
                }
                if cover_letter_data:
                    update_fields["cover_letter_json"] = json.dumps(
                        {k: v for k, v in cover_letter_data.items() if not k.startswith("_")},
                        default=str,
                    )
                if cover_letter_html:
                    update_fields["cover_letter_html"] = cover_letter_html
                if quality_review:
                    update_fields["quality_review_json"] = json.dumps(quality_review, default=str)
                await update_job(db, job.id, **update_fields)
                job_id = job.id
                logger.info("Pipeline[%s] persisted Job %s", attempt_id, job_id)
        except Exception:
            logger.exception(
                "Pipeline[%s] Job persistence failed — continuing without job link",
                attempt_id,
            )

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
                job_id=job_id,
                label=label,
                job_title=job_title,
                self_description=attempt.get("self_description", "") or "",
                values_text=attempt.get("values", "") or "",
                offer_appeal=attempt.get("offer_appeal", "") or "",
                references=cv_data.get("references") or attempt.get("references") or None,
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
        "missing_keyword_groups": missing_keyword_groups,
    }
