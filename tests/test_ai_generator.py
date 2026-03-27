"""Tests for AI generator — prompt building, JSON parsing, and region rules."""

import json

import pytest

from app.cv_export.adapters.template_registry import get_region
from app.cv_generation.adapters.anthropic_generator import (
    _build_ats_report,
    _build_keyword_context,
    _build_personal_context,
    _build_region_rules,
    _parse_cv_json,
    generate_tailored_cv,
)


class TestBuildRegionRules:
    """Tests for region-specific formatting rules."""

    def test_us_rules(self):
        us = get_region("US")
        rules = _build_region_rules(us)
        assert "United States" in rules
        assert "DO NOT INCLUDE" in rules
        assert "References" in rules  # US excludes references

    def test_au_rules_include_references(self):
        au = get_region("AU")
        rules = _build_region_rules(au)
        assert "Australia" in rules
        assert "References" in rules
        assert "Visa" in rules

    def test_de_rules_include_photo(self):
        de = get_region("DE")
        rules = _build_region_rules(de)
        assert "Germany" in rules

    def test_rules_contain_date_format(self):
        for code in ["US", "AU", "UK"]:
            region = get_region(code)
            rules = _build_region_rules(region)
            assert "Date format" in rules

    def test_rules_contain_page_length(self):
        us = get_region("US")
        rules = _build_region_rules(us)
        assert "Page length" in rules


class TestBuildATSReport:
    """Tests for ATS report formatting."""

    def test_includes_score(self, sample_ats_result):
        report = _build_ats_report(sample_ats_result)
        assert "65/100" in report

    def test_includes_keyword_match(self, sample_ats_result):
        report = _build_ats_report(sample_ats_result)
        assert "55%" in report

    def test_includes_recommendations(self, sample_ats_result):
        report = _build_ats_report(sample_ats_result)
        assert "Recommendations" in report


class TestBuildPersonalContext:
    """Tests for personal voice context building."""

    def test_empty_attempt(self):
        assert _build_personal_context({}) == ""

    def test_with_self_description(self):
        result = _build_personal_context({"self_description": "Hands-on developer"})
        assert "Hands-on developer" in result

    def test_with_references(self):
        refs = [{"name": "Jane", "title": "CTO", "company": "Acme", "email": "j@a.com", "phone": "123"}]
        result = _build_personal_context({"references": refs})
        assert "Jane" in result
        assert "CTO" in result

    def test_with_all_fields(self):
        result = _build_personal_context({
            "self_description": "desc",
            "values": "quality",
            "offer_appeal": "growth",
            "visa_status": "citizen",
        })
        assert "desc" in result
        assert "quality" in result
        assert "growth" in result
        assert "citizen" in result


class TestBuildKeywordContext:
    """Tests for keyword context formatting."""

    def test_flat_keywords(self):
        result = _build_keyword_context(["python", "go"], None)
        assert "python" in result
        assert "go" in result

    def test_categorized_keywords(self):
        categories = {
            "technical_skills": ["Python", "Go"],
            "tools_platforms": ["Docker", "AWS"],
        }
        result = _build_keyword_context(["unmatched"], categories)
        assert "Technical Skills" in result
        assert "Python" in result
        assert "Docker" in result

    def test_empty_keywords(self):
        assert _build_keyword_context([], None) == ""

    def test_missing_keywords_highlighted(self):
        categories = {"technical_skills": ["Python"]}
        result = _build_keyword_context(["Go", "Rust"], categories)
        assert "MISSING" in result
        assert "Go" in result


class TestParseCVJson:
    """Tests for JSON parsing of LLM output."""

    def test_valid_json(self):
        data = _parse_cv_json('{"name": "John", "title": "Engineer"}')
        assert data["name"] == "John"
        assert data["title"] == "Engineer"

    def test_strips_markdown_fences(self):
        data = _parse_cv_json('```json\n{"name": "John"}\n```')
        assert data["name"] == "John"

    def test_defaults_for_missing_fields(self):
        data = _parse_cv_json('{"name": "John"}')
        assert data["email"] == ""
        assert data["experience"] == []
        assert data["skills"] == []
        assert data["education"] == []

    def test_invalid_json_returns_none(self):
        assert _parse_cv_json("not json at all") is None
        assert _parse_cv_json("{broken: json}") is None

    def test_preserves_existing_data(self):
        data = _parse_cv_json('{"name": "John", "skills": ["Python", "Go"]}')
        assert data["skills"] == ["Python", "Go"]


@pytest.mark.asyncio
class TestGenerateTailoredCV:
    """Integration tests for CV generation with mock LLM."""

    async def test_successful_generation(self, mock_llm, sample_cv_text, sample_job_description, sample_ats_result):
        cv_json = json.dumps({
            "name": "John Smith",
            "title": "Senior Engineer",
            "email": "john@test.com",
            "phone": "+1 555 000 0000",
            "location": "SF",
            "linkedin": "",
            "github": "",
            "portfolio": "",
            "summary": "Experienced engineer.",
            "experience": [],
            "skills": ["Python"],
            "skills_grouped": [],
            "education": [],
            "certifications": [],
            "projects": [],
            "references": [],
        })
        llm = mock_llm(cv_json)
        region = get_region("US")
        result = await generate_tailored_cv(
            sample_cv_text, sample_job_description, ["go"],
            region=region, llm=llm,
        )
        assert result is not None
        assert result["name"] == "John Smith"
        assert "_llm_usage" in result

    async def test_invalid_llm_response_returns_none(self, mock_llm, sample_cv_text, sample_job_description):
        llm = mock_llm("This is not JSON")
        region = get_region("US")
        result = await generate_tailored_cv(
            sample_cv_text, sample_job_description, [],
            region=region, llm=llm,
        )
        assert result is None
