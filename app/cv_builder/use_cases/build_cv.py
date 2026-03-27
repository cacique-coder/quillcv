"""Build CV use case — business logic for the manual CV builder.

Contains all data transformation, form parsing, and CV data construction
functions. HTTP-specific concerns (request/response, session, templates)
remain in the router.
"""

import json
import logging

from app.cv_builder.entities import CV_TO_PII_BACKFILL_MAP, PII_TO_CV_FIELD_MAP
from app.cv_export.adapters.template_registry import REGIONS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Region field map
# ---------------------------------------------------------------------------


def region_fields_map() -> dict[str, dict]:
    """Build a map of region code -> conditional field flags for all regions.

    Returns a dict keyed by region code whose values describe which
    optional/region-specific fields are active for that region.
    """
    result = {}
    for code, r in REGIONS.items():
        result[code] = {
            "photo": r.include_photo in ("required", "common", "optional"),
            "photo_level": r.include_photo,
            "references": r.include_references,
            "visa": r.include_visa_status,
            "dob": r.include_dob,
            "nationality": r.include_nationality,
            "marital": r.include_marital_status,
        }
    return result


# ---------------------------------------------------------------------------
# CV data construction
# ---------------------------------------------------------------------------


def cv_data_from_attempt(attempt: dict) -> dict:
    """Build the cv_data dict from a stored builder attempt.

    Extracts ``builder_data`` from the attempt and returns a normalised dict
    with all canonical CV fields, defaulting missing list fields to ``[]``
    and string fields to ``""``.
    """
    data = attempt.get("builder_data", {})
    return {
        "name": data.get("name", ""),
        "title": data.get("title", ""),
        "email": data.get("email", ""),
        "phone": data.get("phone", ""),
        "location": data.get("location", ""),
        "linkedin": data.get("linkedin", ""),
        "github": data.get("github", ""),
        "portfolio": data.get("portfolio", ""),
        "summary": data.get("summary", ""),
        "experience": data.get("experience", []),
        "skills": data.get("skills", []),
        "skills_grouped": data.get("skills_grouped", []),
        "education": data.get("education", []),
        "certifications": data.get("certifications", []),
        "projects": data.get("projects", []),
        "references": data.get("references", []),
        "languages": data.get("languages", []),
        # Region-specific fields
        "dob": data.get("dob", ""),
        "nationality": data.get("nationality", ""),
        "marital_status": data.get("marital_status", ""),
        "visa_status": data.get("visa_status", ""),
        "region": data.get("region", ""),
        "photo_url": data.get("photo_url", ""),
    }


# ---------------------------------------------------------------------------
# Form parsing
# ---------------------------------------------------------------------------


def parse_form_experience(form) -> list[dict]:
    """Parse dynamic experience entries from form data.

    Iterates over indexed form fields (``exp_title_0``, ``exp_title_1``, …)
    and stops at the first missing title (after index 0) or after a safety
    limit of 20 entries.
    """
    experiences = []
    i = 0
    while True:
        title = form.get(f"exp_title_{i}", "").strip()
        if not title and i > 0:
            break
        if title:
            bullets_raw = form.get(f"exp_bullets_{i}", "")
            bullets = [
                b.strip().lstrip("•").lstrip("-").strip()
                for b in bullets_raw.split("\n")
                if b.strip()
            ]
            experiences.append({
                "title": title,
                "company": form.get(f"exp_company_{i}", "").strip(),
                "location": form.get(f"exp_location_{i}", "").strip(),
                "date": form.get(f"exp_date_{i}", "").strip(),
                "tech": form.get(f"exp_tech_{i}", "").strip(),
                "bullets": bullets,
            })
        i += 1
        if i > 20:  # safety limit
            break
    return experiences


def parse_form_education(form) -> list[dict]:
    """Parse dynamic education entries from form data.

    Iterates over indexed form fields (``edu_degree_0``, …) up to a limit
    of 10 entries.
    """
    entries = []
    i = 0
    while True:
        degree = form.get(f"edu_degree_{i}", "").strip()
        if not degree and i > 0:
            break
        if degree:
            entries.append({
                "degree": degree,
                "institution": form.get(f"edu_institution_{i}", "").strip(),
                "date": form.get(f"edu_date_{i}", "").strip(),
            })
        i += 1
        if i > 10:
            break
    return entries


def parse_form_references(form) -> list[dict]:
    """Parse reference entries from form data.

    Iterates over indexed form fields (``ref_name_0``, …) up to a limit
    of 5 entries.
    """
    refs = []
    i = 0
    while True:
        name = form.get(f"ref_name_{i}", "").strip()
        if not name and i > 0:
            break
        if name:
            refs.append({
                "name": name,
                "title": form.get(f"ref_title_{i}", "").strip(),
                "company": form.get(f"ref_company_{i}", "").strip(),
                "contact": form.get(f"ref_contact_{i}", "").strip(),
            })
        i += 1
        if i > 5:
            break
    return refs


def parse_form_into_builder_data(form) -> dict:
    """Parse all relevant fields from a submitted builder form into a builder_data dict.

    Handles scalar fields, comma/newline-delimited list fields, and
    dynamic indexed sub-forms (experience, education, references).
    Also derives ``photo_url`` from the hidden ``photo_path`` field.

    Returns a dict suitable for storing as the ``builder_data`` of an attempt.
    """
    template_id = form.get("template_id", "modern").strip()
    region = form.get("region", "US").strip()

    skills_raw = form.get("skills", "")
    skills = [s.strip() for s in skills_raw.split(",") if s.strip()]

    certs_raw = form.get("certifications", "")
    certifications = [c.strip() for c in certs_raw.split("\n") if c.strip()]

    languages_raw = form.get("languages", "")
    languages = [lang.strip() for lang in languages_raw.split(",") if lang.strip()]

    photo_path = form.get("photo_path", "").strip()
    photo_url = f"/photos/serve/{photo_path}" if photo_path else ""

    return {
        "name": form.get("name", "").strip(),
        "title": form.get("title", "").strip(),
        "email": form.get("email", "").strip(),
        "phone": form.get("phone", "").strip(),
        "location": form.get("location", "").strip(),
        "linkedin": form.get("linkedin", "").strip(),
        "github": form.get("github", "").strip(),
        "portfolio": form.get("portfolio", "").strip(),
        "summary": form.get("summary", "").strip(),
        "experience": parse_form_experience(form),
        "skills": skills,
        "education": parse_form_education(form),
        "certifications": certifications,
        "references": parse_form_references(form),
        "languages": languages,
        "dob": form.get("dob", "").strip(),
        "nationality": form.get("nationality", "").strip(),
        "marital_status": form.get("marital_status", "").strip(),
        "visa_status": form.get("visa_status", "").strip(),
        "photo_url": photo_url,
        "region": region,
        "template_id": template_id,
    }


# ---------------------------------------------------------------------------
# PII handling
# ---------------------------------------------------------------------------


def apply_pii_prefill(cv_data: dict, pii: dict) -> dict:
    """Pre-fill empty cv_data fields from the PII vault.

    Mutates ``cv_data`` in-place (also returns it for convenience).
    Only fills a field if it is currently empty AND the PII vault has a
    non-empty value for the corresponding key.
    """
    for pii_key, cv_key in PII_TO_CV_FIELD_MAP.items():
        if not cv_data.get(cv_key) and pii.get(pii_key):
            cv_data[cv_key] = pii[pii_key]
    return cv_data


def restore_pii_tokens(stored_data: dict, pii: dict) -> dict:
    """Replace PII placeholder tokens in a stored CV data dict with real values.

    Serialises ``stored_data`` to JSON, performs string replacements for each
    known token, and deserialises back to a dict.  Returns the restored dict.
    """
    candidate_slug = (pii.get("full_name") or "").lower().replace(" ", "-")
    token_replacements = {
        "<<CANDIDATE_NAME>>": pii.get("full_name", ""),
        "<<EMAIL_1>>": pii.get("email", ""),
        "<<PHONE_1>>": pii.get("phone", ""),
        "<<DOB>>": pii.get("dob", ""),
        "<<DOCUMENT_ID>>": pii.get("document_id", ""),
        "<<LINKEDIN_URL>>": pii.get("linkedin", ""),
        "<<GITHUB_URL>>": pii.get("github", ""),
        "<<PORTFOLIO_URL>>": pii.get("portfolio", ""),
        "<<CANDIDATE_SLUG>>": candidate_slug,
    }
    raw = json.dumps(stored_data)
    for token, real_val in token_replacements.items():
        if real_val:
            raw = raw.replace(token, real_val)
    return json.loads(raw)


def compute_pii_backfill(cv_data: dict, pii: dict) -> dict:
    """Determine which PII vault fields should be back-filled from cv_data.

    Returns a (possibly empty) dict of PII vault updates — fields that are
    missing from the vault but present in cv_data. Does NOT mutate either
    argument.
    """
    updates: dict = {}
    for cv_key, pii_key in CV_TO_PII_BACKFILL_MAP.items():
        if not pii.get(pii_key) and cv_data.get(cv_key):
            updates[pii_key] = cv_data[cv_key]
    return updates


# ---------------------------------------------------------------------------
# Label generation
# ---------------------------------------------------------------------------


def default_save_label(cv_data: dict, template_id: str) -> str:
    """Generate a default save label when the user has not provided one.

    Uses the candidate name from ``cv_data`` and the template ID, e.g.
    ``"Jane Smith — Modern"`` or ``"CV — Classic"`` when the name is absent.
    """
    cv_name = cv_data.get("name", "")
    if cv_name:
        return f"{cv_name} — {template_id.title()}"
    return f"CV — {template_id.title()}"
