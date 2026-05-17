"""Filter improvement suggestions to remove personal-detail items.

Quality-review flags and ATS recommendations that reference identity fields
(name, email, phone, address, etc.) are not "content to improve" — they are
user-supplied data that the platform already knows (or can't change without
asking the user).  Surfacing them as suggestions would be misleading.

This module provides a single public function, ``filter_personal_detail_items``,
which strips such items from the suggestions before they reach the UI.

What counts as a CONTENT improvement (kept):
    summary, experience bullets, skills coverage, keyword density, dates,
    achievements, tense, grammar, length, formatting, certifications,
    relevance of entries, weak phrasing.

What is a PERSONAL DETAIL (filtered out):
    name, full_name, email, phone, address, location, city, country,
    linkedin, github, portfolio, website, url, dob, date_of_birth,
    nationality, marital_status, visa_status, document_id, photo.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Personal-detail field names — exact or substring matches on flag.category
# and flag.section (case-insensitive).
# ---------------------------------------------------------------------------

_PERSONAL_FIELDS: frozenset[str] = frozenset({
    "name",
    "full_name",
    "email",
    "phone",
    "address",
    "location",
    "city",
    "country",
    "linkedin",
    "github",
    "portfolio",
    "website",
    "url",
    "dob",
    "date_of_birth",
    "nationality",
    "marital_status",
    "visa_status",
    "document_id",
    "photo",
    "photo_url",
    "personal_info",  # category value used by quality_reviewer
})

# Phrases in recommendation text that indicate personal-detail advice.
_PERSONAL_RECOMMENDATION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\badd\s+(your\s+)?(full\s+)?name\b", re.I),
    re.compile(r"\badd\s+(your\s+)?email\b", re.I),
    re.compile(r"\binclude\s+(your\s+)?email\b", re.I),
    re.compile(r"\badd\s+(your\s+)?phone\b", re.I),
    re.compile(r"\binclude\s+(your\s+)?phone\b", re.I),
    re.compile(r"\badd\s+(your\s+)?(a\s+)?contact\s+(number|details?)\b", re.I),
    re.compile(r"\badd\s+(your\s+)?(linkedin|github|portfolio|website)\b", re.I),
    re.compile(r"\binclude\s+(your\s+)?(linkedin|github|portfolio|website)\b", re.I),
    re.compile(r"\bprovide\s+(your\s+)?contact\b", re.I),
    re.compile(r"\bmissing\s+(your\s+)?(name|email|phone|address|location)\b", re.I),
    re.compile(r"\b(name|email|phone|address|location)\s+is\s+missing\b", re.I),
    re.compile(r"\bno\s+(email|phone|name|contact)\s+(address\s+)?provided\b", re.I),
]


def _is_personal_detail_flag(flag: dict) -> bool:
    """Return True if a quality-review flag describes a personal-detail issue."""
    category = (flag.get("category") or "").strip().lower()
    section = (flag.get("section") or "").strip().lower()

    if category in _PERSONAL_FIELDS:
        return True
    if section in _PERSONAL_FIELDS:
        return True

    # Check if item text or reason mentions personal-field language
    item_text = (flag.get("item") or "").lower()
    reason_text = (flag.get("reason") or "").lower()
    combined = f"{item_text} {reason_text}"

    for field in _PERSONAL_FIELDS:
        # Whole-word match so "email" doesn't fire on "email_marketing_experience"
        if re.search(r'\b' + re.escape(field) + r'\b', combined):
            return True

    return False


def _is_personal_detail_recommendation(rec: str) -> bool:
    """Return True if an ATS recommendation string is about personal details."""
    for pattern in _PERSONAL_RECOMMENDATION_PATTERNS:
        if pattern.search(rec):
            return True
    return False


def filter_personal_detail_items(
    quality_flags: list[dict] | None,
    ats_recommendations: list[str] | None,
) -> tuple[list[dict], list[str]]:
    """Strip personal-detail entries from quality flags and ATS recommendations.

    Args:
        quality_flags: List of flag dicts from ``quality_review.flags``.
            Each dict has ``category``, ``section``, ``item``, ``reason``, etc.
        ats_recommendations: List of plain-text recommendation strings from
            ``ats_result.recommendations`` (may be None or absent on older runs).

    Returns:
        (filtered_flags, filtered_recommendations) — both are new lists; the
        originals are not mutated.  Filtered items are logged at DEBUG level.
    """
    filtered_flags: list[dict] = []
    for flag in (quality_flags or []):
        if _is_personal_detail_flag(flag):
            logger.debug(
                "filter_suggestions: dropping personal-detail flag category=%r item=%r",
                flag.get("category"),
                flag.get("item", "")[:80],
            )
        else:
            filtered_flags.append(flag)

    filtered_recs: list[str] = []
    for rec in (ats_recommendations or []):
        if _is_personal_detail_recommendation(rec):
            logger.debug(
                "filter_suggestions: dropping personal-detail recommendation %r",
                rec[:120],
            )
        else:
            filtered_recs.append(rec)

    return filtered_flags, filtered_recs
