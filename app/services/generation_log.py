"""Logs each CV generation run to a JSONL file for analysis and debugging.

Each line is a self-contained JSON object with the full pipeline state:
ATS before/after, keywords gained/still missing, score breakdown, timing, etc.

Log file: app/logs/generations.jsonl

PII note: The ``*_preview`` fields (cv_text_preview, generated_text_preview,
job_desc_preview) are run through PIIRedactor before writing so that real names,
emails, and phones are never persisted in the log.
"""
import json
import logging
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.services.ats_analyzer import ATSResult
from app.services.pii_redactor import PIIRedactor

LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_FILE = LOG_DIR / "generations.jsonl"


def _score_breakdown(ats: ATSResult) -> dict:
    """Recreate the individual score components for debugging."""
    kw_pts = min(ats.keyword_match_pct * 0.4, 40)
    sections_found = sum(ats.section_checks.values())
    section_pts = (sections_found / max(len(ats.section_checks), 1)) * 30
    format_pts = max(0, 20 - len(ats.formatting_issues) * 5)
    rec_pts = max(0, 10 - len(ats.recommendations) * 2)
    return {
        "total": ats.score,
        "keywords_pts": round(kw_pts, 1),
        "sections_pts": round(section_pts, 1),
        "formatting_pts": round(format_pts, 1),
        "recommendations_pts": round(rec_pts, 1),
    }


def log_generation(
    attempt_id: str,
    region: str,
    template_id: str,
    cv_text: str,
    job_description: str,
    ats_original: ATSResult,
    ats_generated: ATSResult,
    generated_text: str,
    cv_data: dict,
    timings: dict[str, float],
    full_name: str = "",
):
    """Append a generation log entry."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Keywords that were missing and got added
    gained = [kw for kw in ats_generated.matched_keywords if kw in ats_original.missing_keywords]
    still_missing = ats_generated.missing_keywords

    # Redact PII from preview snippets before logging
    _redactor = PIIRedactor(
        full_name=full_name or cv_data.get("full_name") or cv_data.get("name") or "",
    )
    cv_preview = _redactor.redact(cv_text[:1000])
    gen_preview = _redactor.redact(generated_text[:1000])
    jd_preview = _redactor.redact(job_description[:1000])

    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "attempt_id": attempt_id,
        "region": region,
        "template_id": template_id,
        "timings_sec": timings,

        # ATS comparison
        "score_original": ats_original.score,
        "score_generated": ats_generated.score,
        "score_delta": ats_generated.score - ats_original.score,
        "breakdown_original": _score_breakdown(ats_original),
        "breakdown_generated": _score_breakdown(ats_generated),

        # Keywords
        "job_keywords_total": len(ats_original.matched_keywords) + len(ats_original.missing_keywords),
        "original_keyword_match_pct": ats_original.keyword_match_pct,
        "generated_keyword_match_pct": ats_generated.keyword_match_pct,
        "keywords_gained": gained,
        "keywords_gained_count": len(gained),
        "keywords_still_missing": still_missing[:30],
        "keywords_still_missing_count": len(still_missing),

        # Sections
        "sections_original": ats_original.section_checks,
        "sections_generated": ats_generated.section_checks,

        # Formatting
        "formatting_issues_original": ats_original.formatting_issues,
        "formatting_issues_generated": ats_generated.formatting_issues,

        # Recommendations still firing on generated CV
        "recommendations_generated": ats_generated.recommendations,

        # Content stats
        "cv_input_chars": len(cv_text),
        "cv_output_chars": len(generated_text),
        "job_desc_chars": len(job_description),
        "experience_count": len(cv_data.get("experience", [])),
        "skills_count": len(cv_data.get("skills", [])),

        # LLM usage & cost
        "llm": cv_data.get("_llm_usage", {}),

        # Redacted text previews for manual review — no real PII
        "cv_text_preview": cv_preview,
        "generated_text_preview": gen_preview,
        "job_desc_preview": jd_preview,
    }

    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


_cleanup_logger = logging.getLogger(__name__)


def cleanup_old_logs(max_age_days: int = 90) -> dict[str, int]:
    """Remove log entries older than *max_age_days* from all JSONL logs in LOG_DIR.

    Rewrites ``generations.jsonl`` in-place, keeping only entries whose ``ts``
    field is within the retention window.  Also deletes any other ``*.log`` /
    ``*.jsonl`` files in LOG_DIR whose modification time is older than the
    retention window.

    Returns a summary dict: ``{"generations_kept": N, "generations_removed": N,
    "extra_files_removed": N}``.

    Wire this into a periodic task (e.g. APScheduler, a startup hook that runs
    weekly, or a cron job calling ``python -c "from app.services.generation_log
    import cleanup_old_logs; cleanup_old_logs()"``) so it runs automatically.
    """
    cutoff = datetime.now(UTC) - timedelta(days=max_age_days)
    summary = {"generations_kept": 0, "generations_removed": 0, "extra_files_removed": 0}

    # --- Rotate generations.jsonl ---
    if LOG_FILE.exists():
        kept: list[str] = []
        removed = 0
        try:
            with open(LOG_FILE) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        ts_str = entry.get("ts", "")
                        # ts field is written as "%Y-%m-%dT%H:%M:%S" (naive UTC)
                        entry_dt = datetime.fromisoformat(ts_str).replace(tzinfo=UTC)
                        if entry_dt >= cutoff:
                            kept.append(line)
                        else:
                            removed += 1
                    except (json.JSONDecodeError, ValueError):
                        # Keep malformed lines — do not silently discard them
                        kept.append(line)

            if removed > 0:
                LOG_FILE.write_text("\n".join(kept) + ("\n" if kept else ""))
                _cleanup_logger.info(
                    "generation_log cleanup: removed %d entries older than %d days, kept %d",
                    removed,
                    max_age_days,
                    len(kept),
                )
        except OSError as exc:
            _cleanup_logger.warning("generation_log cleanup failed to read %s: %s", LOG_FILE, exc)

        summary["generations_kept"] = len(kept)
        summary["generations_removed"] = removed

    # --- Remove stale auxiliary log files (*.log, *.jsonl) in LOG_DIR ---
    extra_removed = 0
    if LOG_DIR.exists():
        for log_path in LOG_DIR.iterdir():
            if log_path == LOG_FILE:
                continue
            if log_path.suffix not in {".log", ".jsonl"}:
                continue
            try:
                mtime = datetime.fromtimestamp(log_path.stat().st_mtime, tz=UTC)
                if mtime < cutoff:
                    log_path.unlink()
                    extra_removed += 1
                    _cleanup_logger.info("generation_log cleanup: deleted stale log %s", log_path.name)
            except OSError as exc:
                _cleanup_logger.warning("generation_log cleanup: could not remove %s: %s", log_path, exc)

    summary["extra_files_removed"] = extra_removed
    return summary
