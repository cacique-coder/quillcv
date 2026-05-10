"""Region-convention warnings for the wizard.

Surfaces non-blocking warnings when the user has supplied data the selected
region recommends *against* (e.g. a photo for a US/UK CV) or violates other
soft conventions on the ``RegionConfig``. This is intentionally separate from
``_check_pii_completeness`` in the wizard router — that function checks
*required* fields and gates submission; this one is read-only feedback.

All rules are derived from fields on ``RegionConfig`` so behaviour stays in
sync with the registry without hardcoding country codes.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from app.cv_export.adapters.template_registry import REGIONS


@dataclass
class RegionWarning:
    severity: str  # "warning" | "info"
    field: str  # wizard field this attaches to (e.g. "photo", "dob")
    message: str

    def to_dict(self) -> dict:
        return asdict(self)


def _has(attempt: dict, pii: dict, key: str) -> bool:
    """True if ``key`` is present and non-empty in either the attempt or vault."""
    val = attempt.get(key)
    if isinstance(val, str) and val.strip():
        return True
    if val and not isinstance(val, str):
        return True
    val = pii.get(key)
    if isinstance(val, str) and val.strip():
        return True
    if val and not isinstance(val, str):
        return True
    return False


def _has_photo(attempt: dict, pii: dict) -> bool:
    """Photos aren't persisted on the attempt today, but defensively check both
    sources so the rule stays correct if ``photo_path`` is later stored."""
    return _has(attempt, pii, "photo_path") or _has(attempt, pii, "photo")


def _has_references(attempt: dict, pii: dict) -> bool:
    refs = attempt.get("references") or pii.get("references") or []
    if not isinstance(refs, list):
        return False
    return any((r.get("name") or "").strip() for r in refs if isinstance(r, dict))


# Word lists for spelling detection. Conservative: only common, unambiguous
# markers. Flagged only when at least 3 hits to keep false positives low.
_BRITISH_MARKERS = {
    "organised", "organisation", "organising",
    "colour", "colours", "favour", "favourite", "behaviour",
    "programme", "programmes",
    "centre", "centres",
    "analyse", "analysed", "analysing",
    "specialised", "specialising",
    "recognise", "recognised",
    "optimise", "optimised", "optimising",
    "labour", "honour", "neighbour",
    "travelled", "travelling",
    "licence",  # noun form
}

_AMERICAN_MARKERS = {
    "organized", "organization", "organizing",
    "color", "colors", "favor", "favorite", "behavior",
    "program", "programs",
    "center", "centers",
    "analyze", "analyzed", "analyzing",
    "specialized", "specializing",
    "recognize", "recognized",
    "optimize", "optimized", "optimizing",
    "labor", "honor", "neighbor",
    "traveled", "traveling",
    "license",  # both noun and verb in American
}


def _spelling_hits(text: str, markers: set[str]) -> int:
    """Count case-insensitive whole-word marker hits in ``text``."""
    if not text:
        return 0
    import re
    lowered = text.lower()
    pattern = r"\b(" + "|".join(re.escape(m) for m in markers) + r")\b"
    return len(re.findall(pattern, lowered))


def region_warnings(
    attempt: dict,
    pii: dict,
    region_code: str,
    *,
    cv_text: str | None = None,
) -> list[RegionWarning]:
    """Return warnings for data that conflicts with the region's conventions.

    Read-only — never blocks submission. Unknown regions return an empty list.

    Args:
        attempt: wizard attempt dict (current step values + persisted state).
        pii: PII vault dict (acts as default source for shared fields).
        region_code: e.g. "AU", "US", "DE". Unknown codes yield ``[]``.
        cv_text: optional parsed CV body for the spelling check. When ``None``
            the spelling check is skipped (it is purely advisory).
    """
    region = REGIONS.get(region_code)
    if region is None:
        return []

    warnings: list[RegionWarning] = []

    # ------------------------------------------------------------------
    # Photo conventions
    # ------------------------------------------------------------------
    if _has_photo(attempt, pii):
        if region.include_photo == "no":
            warnings.append(RegionWarning(
                severity="warning",
                field="photo",
                message=(
                    f"{region.name} CVs should not include a photo — "
                    "many ATS systems reject CVs with images and including "
                    "a photo can introduce hiring bias."
                ),
            ))
        elif region.include_photo == "optional":
            warnings.append(RegionWarning(
                severity="info",
                field="photo",
                message=(
                    f"A photo is optional in {region.name} — including one is "
                    "becoming less common. Skip it if you're unsure."
                ),
            ))

    # ------------------------------------------------------------------
    # Date of birth
    # ------------------------------------------------------------------
    if _has(attempt, pii, "dob") and not region.include_dob:
        warnings.append(RegionWarning(
            severity="warning",
            field="dob",
            message=(
                f"Date of birth is not expected on a {region.name} CV — "
                "including it can lead to age-bias screening."
            ),
        ))

    # ------------------------------------------------------------------
    # Marital status
    # ------------------------------------------------------------------
    if _has(attempt, pii, "marital_status") and not region.include_marital_status:
        warnings.append(RegionWarning(
            severity="warning",
            field="marital_status",
            message=(
                f"Marital status is not expected on a {region.name} CV — "
                "consider removing it to keep the focus on your experience."
            ),
        ))

    # ------------------------------------------------------------------
    # Nationality
    # ------------------------------------------------------------------
    if _has(attempt, pii, "nationality") and not region.include_nationality:
        warnings.append(RegionWarning(
            severity="warning",
            field="nationality",
            message=(
                f"Nationality is not expected on a {region.name} CV — "
                "work-rights questions are typically handled separately."
            ),
        ))

    # ------------------------------------------------------------------
    # References
    # ------------------------------------------------------------------
    if _has_references(attempt, pii) and not region.include_references:
        warnings.append(RegionWarning(
            severity="warning",
            field="references",
            message=(
                f"{region.name} CVs typically omit references. "
                "'References available upon request' is also outdated — "
                "leave it off entirely and provide referees only when asked."
            ),
        ))

    # ------------------------------------------------------------------
    # Page length: hook for later — we don't know the generated page
    # count at wizard-submit time. TODO: wire in once the export pipeline
    # surfaces a reliable page count.
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Spelling mismatch (advisory)
    # ------------------------------------------------------------------
    # Only meaningful for English-language regions. Skip otherwise.
    # TODO: extend to parse cv_text from the uploaded document when the
    # wizard exposes parsed body text directly.
    if cv_text and region.spelling in ("American", "British"):
        if region.spelling == "American":
            hits = _spelling_hits(cv_text, _BRITISH_MARKERS)
            if hits >= 3:
                warnings.append(RegionWarning(
                    severity="info",
                    field="cv_text",
                    message=(
                        f"Your CV uses British spellings (organised, colour, "
                        f"programme — {hits} matches) but {region.name} "
                        "expects American spelling. Consider running a quick "
                        "find-and-replace before submitting."
                    ),
                ))
        else:  # British
            hits = _spelling_hits(cv_text, _AMERICAN_MARKERS)
            if hits >= 3:
                warnings.append(RegionWarning(
                    severity="info",
                    field="cv_text",
                    message=(
                        f"Your CV uses American spellings (organized, color, "
                        f"program — {hits} matches) but {region.name} "
                        "expects British spelling. Consider switching before "
                        "submitting."
                    ),
                ))

    return warnings


def region_warnings_dicts(
    attempt: dict,
    pii: dict,
    region_code: str,
    *,
    cv_text: str | None = None,
) -> list[dict]:
    """Convenience wrapper for templates — returns plain dicts."""
    return [w.to_dict() for w in region_warnings(attempt, pii, region_code, cv_text=cv_text)]
