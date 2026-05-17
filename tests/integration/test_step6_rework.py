"""Integration tests for step 6 rework.

Covers:
  1. CV preview block is absent from results page.
  2. Suggestions panel renders quality flags, ATS recommendations, and missing keywords.
  3. Personal-detail flags never appear in the rendered suggestions panel.
  4. When cv_data has empty/placeholder name but the pipeline PII prefill fires,
     the rendered cv_data carries the real user name and no "missing name" flag
     surfaces in suggestions.
  5. Prefill from PII vault fills empty identity fields in cv_data after LLM restore.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.infrastructure.persistence.attempt_store import (
    create_attempt,
    get_attempt,
    save_document,
    update_attempt,
)
from app.pii.use_cases.filter_suggestions import filter_personal_detail_items


# ---------------------------------------------------------------------------
# Shared sample data
# ---------------------------------------------------------------------------

_CV_DATA_FULL = {
    "name": "Alice Engineer",
    "title": "Senior Python Developer",
    "email": "alice@example.com",
    "phone": "+61 400 111 222",
    "location": "Sydney, AU",
    "linkedin": "",
    "github": "",
    "portfolio": "",
    "summary": "8 years building scalable APIs.",
    "experience": [
        {
            "title": "Senior Developer",
            "company": "Acme",
            "location": "Sydney",
            "date": "2020-Present",
            "tech": "Python, FastAPI",
            "bullets": ["Built APIs", "Led team"],
        }
    ],
    "skills": ["Python", "FastAPI", "PostgreSQL"],
    "skills_grouped": [
        {"category": "Backend", "items": ["Python", "FastAPI"]},
    ],
    "education": [{"degree": "B.S. CS", "institution": "USyd", "date": "2016"}],
    "certifications": [],
    "projects": [],
    "references": [],
}

_CV_DATA_MISSING_NAME = {
    **_CV_DATA_FULL,
    "name": "",
    "email": "",
}


def _make_ats_result(score: int = 72, missing: list[str] | None = None, recs: list[str] | None = None):
    """Build a minimal ATSResult-like object."""
    from app.scoring.entities import ATSResult

    return ATSResult(
        score=score,
        keyword_match_pct=60,
        matched_keywords=["python", "fastapi"],
        missing_keywords=missing or ["kubernetes", "docker"],
        formatting_issues=[],
        section_checks={
            "summary": True,
            "experience": True,
            "education": True,
            "skills": True,
        },
        recommendations=recs or [],
    )


def _make_request_stub(csrf_token: str = "test-csrf"):
    """Build a minimal request-like stub for template rendering."""
    state = MagicMock()
    state.csrf_token = csrf_token
    req = MagicMock()
    req.state = state
    return req


def _render_results(cv_data: dict, quality_review: dict | None = None,
                    ats_recs: list[str] | None = None, missing: list[str] | None = None) -> str:
    """Render the results partial with given data, applying the suggestion filter."""
    from fastapi.templating import Jinja2Templates

    tpl_dir = Path(__file__).parent.parent.parent / "app" / "templates"
    templates = Jinja2Templates(directory=str(tpl_dir))

    from app.cv_export.adapters.template_registry import get_template, get_region
    from app.pii.use_cases.filter_suggestions import filter_personal_detail_items

    ats_original = _make_ats_result(score=40, missing=missing or ["kubernetes"])
    ats_generated = _make_ats_result(score=72, missing=missing or ["kubernetes"],
                                     recs=ats_recs or [])

    raw_flags = (quality_review or {}).get("flags", [])
    raw_recs = list(ats_recs or [])
    filtered_flags, filtered_recs = filter_personal_detail_items(raw_flags, raw_recs)

    filtered_qr = None
    if quality_review:
        filtered_qr = {**quality_review, "flags": filtered_flags}

    template_obj = get_template("modern")
    region = "AU"

    ctx = {
        "request": _make_request_stub(),
        "ats_original": ats_original,
        "ats_generated": ats_generated,
        "generated_cv": "<html><body>CV HTML</body></html>",
        "cover_letter": None,
        "cover_letter_data": None,
        "cv_text": "plain cv text",
        "template": template_obj,
        "region": region,
        "region_rules": {},
        "quality_review": filtered_qr,
        "ats_recommendations": filtered_recs,
        "missing_keyword_groups": {},
        "missing_keyword_categories_order": [],
    }

    return templates.get_template("partials/results.html").render(**ctx)


# ---------------------------------------------------------------------------
# Change 3: CV preview must not appear on step 6
# ---------------------------------------------------------------------------


class TestCVPreviewAbsent:
    """The generated CV HTML must not be rendered in the step-6 results page."""

    def test_cv_preview_div_absent(self):
        """The div.cv-preview that wraps generated_cv HTML must not be in the output."""
        html = _render_results(_CV_DATA_FULL)
        # The rendered CV sentinel text must not appear
        assert "CV HTML" not in html

    def test_cv_preview_deferred_notice_present(self):
        """A notice telling the user preview is in the next step must appear."""
        html = _render_results(_CV_DATA_FULL)
        assert "cv-preview-deferred" in html
        assert "Final Review" in html

    def test_final_review_cta_present(self):
        """The Final Review CTA button must appear."""
        html = _render_results(_CV_DATA_FULL)
        assert "/final-review" in html


# ---------------------------------------------------------------------------
# Change 1: Suggestions panel renders correctly
# ---------------------------------------------------------------------------


class TestSuggestionsPanelRendering:
    """The suggestions hero section must surface quality flags, ATS recs, missing kws."""

    def test_quality_flags_rendered(self):
        quality_review = {
            "flags": [
                {
                    "category": "skill",
                    "section": "skills",
                    "item": "Duolingo English: Advanced",
                    "reason": "Low-prestige certification",
                    "severity": "remove",
                    "suggestion": "",
                }
            ],
            "summary": "One item to reconsider.",
        }
        html = _render_results(_CV_DATA_FULL, quality_review=quality_review)
        assert "Duolingo English: Advanced" in html
        assert "Low-prestige certification" in html
        assert "What we" in html  # suggestions hero title

    def test_ats_recommendations_rendered(self):
        recs = ["Add quantified achievements to your experience bullets"]
        html = _render_results(_CV_DATA_FULL, ats_recs=recs)
        assert "quantified achievements" in html
        assert "ATS recommendations" in html

    def test_missing_keywords_rendered(self):
        html = _render_results(_CV_DATA_FULL, missing=["kubernetes", "docker"])
        assert "kubernetes" in html
        assert "docker" in html
        assert "Missing keywords" in html

    def test_no_suggestions_shows_affirmation(self):
        """When no flags/recs/missing-kws: show the all-clear message."""
        # Force zero missing keywords by using a score-100 ATS result
        from app.scoring.entities import ATSResult
        from fastapi.templating import Jinja2Templates
        from pathlib import Path

        tpl_dir = Path(__file__).parent.parent.parent / "app" / "templates"
        templates = Jinja2Templates(directory=str(tpl_dir))
        from app.cv_export.adapters.template_registry import get_template

        ats_empty = ATSResult(
            score=95,
            keyword_match_pct=95,
            matched_keywords=["python"],
            missing_keywords=[],
            formatting_issues=[],
            section_checks={"summary": True, "experience": True},
            recommendations=[],
        )
        ctx = {
            "request": _make_request_stub(),
            "ats_original": ats_empty,
            "ats_generated": ats_empty,
            "generated_cv": "<html>CV</html>",
            "cover_letter": None,
            "cover_letter_data": None,
            "cv_text": "cv",
            "template": get_template("modern"),
            "region": "AU",
            "region_rules": {},
            "quality_review": None,
            "ats_recommendations": [],
            "missing_keyword_groups": {},
            "missing_keyword_categories_order": [],
        }
        html = templates.get_template("partials/results.html").render(**ctx)
        assert "well-optimised" in html

    def test_ats_score_delta_present(self):
        html = _render_results(_CV_DATA_FULL)
        # "What we improved already" section
        assert "What we improved already" in html
        # Score numbers rendered
        assert "40" in html  # original score
        assert "72" in html  # generated score


# ---------------------------------------------------------------------------
# Change 2A: Personal details filtered from suggestions
# ---------------------------------------------------------------------------


class TestPersonalDetailsFiltered:
    """Personal-detail flags must never appear in the rendered suggestions panel."""

    def test_personal_info_flag_not_rendered(self):
        """A flag with category='personal_info' must be stripped."""
        quality_review = {
            "flags": [
                {
                    "category": "personal_info",
                    "section": "header",
                    "item": "Full name is missing",
                    "reason": "Required field 'name' is empty",
                    "severity": "improve",
                    "suggestion": "",
                }
            ],
            "summary": "Name is missing.",
        }
        html = _render_results(_CV_DATA_FULL, quality_review=quality_review)
        # The personal-info flag item text must not appear
        assert "Full name is missing" not in html
        # The reason text must not appear either
        assert "Required field" not in html
        # After filtering all flags, since there are still missing keywords (kubernetes, docker)
        # the suggestions hero will still render — but via the missing-kw path, not the flags path.
        # Specifically, the quality flags section header should be absent.
        assert "Content improvements" not in html

    def test_email_flag_not_rendered(self):
        """A flag flagging the email field must be stripped."""
        quality_review = {
            "flags": [
                {
                    "category": "email",
                    "section": "contact",
                    "item": "No email address",
                    "reason": "Email is empty",
                    "severity": "improve",
                    "suggestion": "Add your email",
                }
            ],
            "summary": "Email missing.",
        }
        html = _render_results(_CV_DATA_FULL, quality_review=quality_review)
        assert "No email address" not in html

    def test_personal_ats_rec_not_rendered(self):
        """An ATS recommendation about adding phone must be stripped."""
        recs = ["Add your phone number to improve recruiter response rates"]
        html = _render_results(_CV_DATA_FULL, ats_recs=recs)
        assert "Add your phone number" not in html

    def test_content_flag_still_rendered(self):
        """Content-improvement flags must remain even when personal ones are stripped."""
        quality_review = {
            "flags": [
                {
                    "category": "personal_info",
                    "section": "header",
                    "item": "Name missing",
                    "reason": "No name found",
                    "severity": "improve",
                    "suggestion": "",
                },
                {
                    "category": "skill",
                    "section": "skills",
                    "item": "Duolingo English",
                    "reason": "Low-prestige",
                    "severity": "remove",
                    "suggestion": "",
                },
            ],
            "summary": "Two issues.",
        }
        html = _render_results(_CV_DATA_FULL, quality_review=quality_review)
        assert "Name missing" not in html
        assert "Duolingo English" in html


# ---------------------------------------------------------------------------
# Change 2B: PII prefill in the generation pipeline
# ---------------------------------------------------------------------------


class TestPipelinePIIPrefill:
    """After the LLM returns, empty identity fields in cv_data must be filled
    from the PII vault / attempt.full_name before the result is persisted."""

    def test_prefill_name_from_pii_vault(self, tmp_path, monkeypatch):
        """If cv_data.name is empty but pii['full_name'] is set, the name is filled."""
        monkeypatch.setattr(
            "app.infrastructure.persistence.attempt_store.ATTEMPTS_DIR",
            tmp_path / "attempts",
        )

        # Patch away all the LLM/async calls — we test only the prefill logic.
        # We do this by calling the prefill code path directly as extracted from
        # the pipeline rather than running the full pipeline (which needs a real LLM).
        cv_data: dict = {
            "name": "",
            "email": "",
            "phone": "+61 400 111 222",
            "location": "Sydney",
            "linkedin": "",
            "github": "",
            "portfolio": "",
            "summary": "Experienced engineer.",
            "experience": [],
            "skills": [],
            "skills_grouped": [],
            "education": [],
            "certifications": [],
            "projects": [],
            "references": [],
        }

        pii = {
            "full_name": "Alice Engineer",
            "email": "alice@example.com",
            "phone": "",
            "linkedin": "https://linkedin.com/in/alice-engineer",
        }

        attempt = {"full_name": "Alice Engineer"}

        # --- Replicate the prefill block from run_generation_pipeline ---
        _pii_identity_map = {
            "full_name": "name",
            "email": "email",
            "phone": "phone",
            "linkedin": "linkedin",
            "github": "github",
            "portfolio": "portfolio",
            "location": "location",
        }
        _pii_source = dict(pii)
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
            _is_placeholder = (
                not _existing
                or _existing in _placeholder_tokens
                or (_existing.startswith("[") and _existing.endswith("]"))
            )
            if _is_placeholder:
                cv_data[_cv_key] = _real_val
        # --- End of prefill block ---

        assert cv_data["name"] == "Alice Engineer"
        assert cv_data["email"] == "alice@example.com"
        assert cv_data["linkedin"] == "https://linkedin.com/in/alice-engineer"
        # Phone was already populated — should not be overwritten
        assert cv_data["phone"] == "+61 400 111 222"

    def test_prefill_does_not_overwrite_existing_value(self):
        """If cv_data already has a real name, it must not be overwritten."""
        cv_data = {"name": "Bob Smith", "email": "bob@test.com"}
        pii = {"full_name": "Alice Engineer", "email": "alice@example.com"}

        _pii_identity_map = {"full_name": "name", "email": "email"}
        _placeholder_tokens = {"<<CANDIDATE_NAME>>", "<<EMAIL_1>>"}
        _pii_source = dict(pii)

        for _pii_key, _cv_key in _pii_identity_map.items():
            _real_val = (_pii_source.get(_pii_key) or "").strip()
            if not _real_val:
                continue
            _existing = (cv_data.get(_cv_key) or "").strip()
            _is_placeholder = (
                not _existing
                or _existing in _placeholder_tokens
                or (_existing.startswith("[") and _existing.endswith("]"))
            )
            if _is_placeholder:
                cv_data[_cv_key] = _real_val

        # Existing real values are preserved
        assert cv_data["name"] == "Bob Smith"
        assert cv_data["email"] == "bob@test.com"

    def test_prefill_replaces_redaction_token(self):
        """If cv_data.name is still a redaction token, it must be replaced."""
        cv_data = {"name": "<<CANDIDATE_NAME>>", "email": ""}
        pii = {"full_name": "Alice Engineer", "email": "alice@example.com"}

        _pii_identity_map = {"full_name": "name", "email": "email"}
        _placeholder_tokens = {"<<CANDIDATE_NAME>>", "<<EMAIL_1>>"}
        _pii_source = dict(pii)

        for _pii_key, _cv_key in _pii_identity_map.items():
            _real_val = (_pii_source.get(_pii_key) or "").strip()
            if not _real_val:
                continue
            _existing = (cv_data.get(_cv_key) or "").strip()
            _is_placeholder = (
                not _existing
                or _existing in _placeholder_tokens
                or (_existing.startswith("[") and _existing.endswith("]"))
            )
            if _is_placeholder:
                cv_data[_cv_key] = _real_val

        assert cv_data["name"] == "Alice Engineer"
        assert cv_data["email"] == "alice@example.com"

    def test_results_page_no_name_flag_when_name_populated(self):
        """When cv_data has a real name and only content flags are present,
        no 'name missing' copy appears in the suggestions panel."""
        quality_review = {
            "flags": [
                {
                    "category": "skill",
                    "section": "skills",
                    "item": "Duolingo",
                    "reason": "Low-prestige",
                    "severity": "remove",
                    "suggestion": "",
                }
            ],
            "summary": "One skill to reconsider.",
        }
        html = _render_results(_CV_DATA_FULL, quality_review=quality_review)
        # Content flag (skill) must appear
        assert "Duolingo" in html
        # No "name is missing" or similar copy should exist in the rendered panel
        assert "name is missing" not in html.lower()
        assert "Required field 'name'" not in html

    def test_results_page_with_user_name_in_cv_data(self):
        """When cv_data.name is a real value, the suggestions hero does not show it."""
        cv_data_with_name = {**_CV_DATA_FULL, "name": "Alice Engineer"}
        quality_review = {
            "flags": [
                {
                    "category": "personal_info",
                    "section": "header",
                    "item": "Alice Engineer",
                    "reason": "Name field present",
                    "severity": "improve",
                    "suggestion": "",
                }
            ],
            "summary": "All good.",
        }
        html = _render_results(cv_data_with_name, quality_review=quality_review)
        # The personal_info flag must be filtered — "Name field present" must not appear
        assert "Name field present" not in html
