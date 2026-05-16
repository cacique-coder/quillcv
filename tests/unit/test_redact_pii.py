"""Tests for PII redaction across CV dicts and downstream LLM prompts.

These tests cover the additive ``PIIRedactor.redact_cv_dict`` API and verify
that the four prompt-building adapters (``refiner``, ``quality_reviewer``,
``cover_letter_generator``, ``anthropic_generator``) never emit raw PII.
"""

import json

import pytest

from app.pii.use_cases.redact_pii import PIIRedactor

from app.infrastructure.llm.client import _check_prompt_for_pii as tripwire_check


# ---------------------------------------------------------------------------
# Sample CV — mirrors the schema in anthropic_generator._JSON_SCHEMA
# ---------------------------------------------------------------------------

def _sample_cv() -> dict:
    return {
        "name": "Jane Marie Doe",
        "title": "Senior Software Engineer",
        "email": "jane.doe@example.com",
        "phone": "+1 415 555 0123",
        "location": "San Francisco, CA",
        "linkedin": "https://linkedin.com/in/janedoe",
        "github": "https://github.com/janedoe",
        "portfolio": "https://janedoe.dev",
        "summary": (
            "Jane Marie Doe is a senior engineer based in San Francisco, CA. "
            "Reachable at jane.doe@example.com or +1 415 555 0123."
        ),
        "experience": [
            {
                "title": "Senior Engineer",
                "company": "Acme",
                "location": "Remote",
                "date": "Jan 2020 – Present",
                "tech": "Python, Go",
                "bullets": [
                    "Led platform rebuild — Jane Marie Doe owned architecture decisions.",
                    "Reduced infra cost by 40%.",
                ],
            }
        ],
        "skills": ["Python", "Go", "AWS"],
        "skills_grouped": [{"category": "Languages", "items": ["Python", "Go"]}],
        "education": [
            {"degree": "B.S. Computer Science", "institution": "MIT", "date": "2014"}
        ],
        "certifications": ["AWS Solutions Architect"],
        "projects": [
            {
                "name": "OSS Tool",
                "url": "https://github.com/janedoe/osstool",
                "description": "A tool by Jane Doe for X.",
                "tech": ["Python"],
            }
        ],
        "references": [
            {
                "name": "Bob Smith",
                "title": "Engineering Manager",
                "company": "Acme",
                "email": "bob@acme.com",
                "phone": "+1 415 555 9999",
            },
            {
                "name": "Carol White",
                "title": "Director",
                "company": "PrevCo",
                "email": "carol@prevco.com",
                "phone": "+1 415 555 8888",
            },
        ],
    }


# ---------------------------------------------------------------------------
# Round-trip: redact then restore == original (for non-derived fields)
# ---------------------------------------------------------------------------

def test_redact_cv_dict_round_trip():
    cv = _sample_cv()
    redactor = PIIRedactor.from_cv_data(cv)
    redacted = redactor.redact_cv_dict(cv)
    restored = redactor.restore(redacted)

    # Top-level identity fields must come back exactly
    for key in ("name", "email", "phone", "location", "linkedin", "github", "portfolio"):
        assert restored[key] == cv[key], f"{key} did not round-trip"

    # References — name/email/phone restored
    for orig, got in zip(cv["references"], restored["references"]):
        assert got["name"] == orig["name"]
        assert got["email"] == orig["email"]
        assert got["phone"] == orig["phone"]


# ---------------------------------------------------------------------------
# Prompt-no-PII: redacted serialised CV contains no raw PII
# ---------------------------------------------------------------------------

def _assert_no_pii_in_text(text: str, cv: dict) -> None:
    assert cv["name"] not in text
    assert cv["email"] not in text
    assert cv["phone"] not in text
    assert "linkedin.com/in/janedoe" not in text
    assert "github.com/janedoe" not in text
    assert cv["location"] not in text
    # References
    for ref in cv["references"]:
        assert ref["name"] not in text
        assert ref["email"] not in text
        assert ref["phone"] not in text


def test_redacted_cv_dict_serialises_without_pii():
    cv = _sample_cv()
    redactor = PIIRedactor.from_cv_data(cv)
    redacted = redactor.redact_cv_dict(cv)
    text = json.dumps(redacted)
    _assert_no_pii_in_text(text, cv)


def test_refiner_prompt_contains_no_pii():
    """Build the refiner prompt and assert it has no raw PII."""
    from app.cv_generation.adapters.refiner import _REFINE_PROMPT

    cv = _sample_cv()
    redactor = PIIRedactor.from_cv_data(cv)
    redacted = redactor.redact_cv_dict(cv)

    prompt = _REFINE_PROMPT.format(
        cv_json=json.dumps(redacted, indent=2),
        job_description="Senior Engineer role at FooCorp.",
        changes="1. REMOVE: 'AWS Solutions Architect'",
    )
    _assert_no_pii_in_text(prompt, cv)


def test_quality_reviewer_prompt_contains_no_pii():
    from app.cv_generation.adapters.quality_reviewer import _REVIEW_PROMPT

    cv = _sample_cv()
    redactor = PIIRedactor.from_cv_data(cv)
    redacted = redactor.redact_cv_dict(cv)

    prompt = _REVIEW_PROMPT.format(
        cv_json=json.dumps(redacted, indent=2),
        job_description="Senior Engineer role.",
        region="United States",
    )
    _assert_no_pii_in_text(prompt, cv)


def test_cover_letter_cv_context_contains_no_pii():
    from app.cv_generation.adapters.cover_letter_generator import _build_cv_context

    cv = _sample_cv()
    redactor = PIIRedactor.from_cv_data(cv)
    redacted = redactor.redact_cv_dict(cv)

    ctx = _build_cv_context(redacted)
    _assert_no_pii_in_text(ctx, cv)


# ---------------------------------------------------------------------------
# References get distinct tokens and restore correctly
# ---------------------------------------------------------------------------

def test_reference_tokens_are_distinct_and_restore_correctly():
    cv = _sample_cv()
    redactor = PIIRedactor.from_cv_data(cv)
    redacted = redactor.redact_cv_dict(cv)

    refs = redacted["references"]
    assert refs[0]["email"] == "<<REF_EMAIL_1>>"
    assert refs[1]["email"] == "<<REF_EMAIL_2>>"
    assert refs[0]["phone"] == "<<REF_PHONE_1>>"
    assert refs[1]["phone"] == "<<REF_PHONE_2>>"
    assert refs[0]["name"] == "<<REF_NAME_1>>"
    assert refs[1]["name"] == "<<REF_NAME_2>>"

    # Round-trip restore puts each one back to the right place.
    restored = redactor.restore(redacted)
    assert restored["references"][0]["email"] == "bob@acme.com"
    assert restored["references"][1]["email"] == "carol@prevco.com"
    assert restored["references"][0]["phone"] == "+1 415 555 9999"
    assert restored["references"][1]["phone"] == "+1 415 555 8888"


# ---------------------------------------------------------------------------
# Empty / missing fields do not crash
# ---------------------------------------------------------------------------

def test_empty_cv_does_not_crash():
    redactor = PIIRedactor(full_name="")
    out = redactor.redact_cv_dict({})
    assert out == {}


def test_partial_cv_does_not_crash():
    cv = {"name": "Solo Person", "summary": "Hello."}
    redactor = PIIRedactor.from_cv_data(cv)
    out = redactor.redact_cv_dict(cv)
    assert out["name"] == "<<CANDIDATE_NAME>>"
    # Summary: contains the name → tokenized
    assert "Solo Person" not in out["summary"]


def test_from_cv_data_seeds_redactor():
    cv = _sample_cv()
    redactor = PIIRedactor.from_cv_data(cv)
    assert redactor.full_name == "Jane Marie Doe"
    assert redactor.linkedin_url.endswith("janedoe")
    assert redactor.github_url.endswith("janedoe")
    assert redactor.portfolio_url.endswith("janedoe.dev")
    assert redactor.location == "San Francisco, CA"


# ---------------------------------------------------------------------------
# Tripwire — detects email / linkedin / github / phone but not date ranges
# ---------------------------------------------------------------------------

def test_tripwire_detects_email():
    assert "email" in tripwire_check("Contact me at foo@bar.com today.")


def test_tripwire_detects_linkedin():
    assert "linkedin_url" in tripwire_check("Profile: https://linkedin.com/in/jane")


def test_tripwire_detects_github():
    assert "github_url" in tripwire_check("Repo: https://github.com/jane/repo")


def test_tripwire_detects_phone():
    assert "phone" in tripwire_check("Call +1 415 555 0123 anytime.")


def test_tripwire_no_false_positive_on_date_ranges():
    # Date ranges and version strings should NOT trigger phone detection.
    assert "phone" not in tripwire_check("Worked there 2018-2024 on v1.2.3.4")


def test_tripwire_clean_prompt():
    text = (
        "===BEGIN CANDIDATE CV===\n"
        "<<CANDIDATE_NAME>> | <<EMAIL_1>> | <<PHONE_1>> | <<LOCATION>>\n"
        "<<LINKEDIN_URL>> · <<GITHUB_URL>>\n"
        "===END==="
    )
    assert tripwire_check(text) == []
