"""Unit tests for app/cv_generation/schemas.py."""

import pytest
from pydantic import ValidationError

from app.cv_generation.schemas import (
    CoverLetterSchema,
    CVDataSchema,
    KeywordCategoriesSchema,
    KeywordCategorizationSchema,
    QualityFlagSchema,
    QualityReviewSchema,
    TemplateRecommendationSchema,
)


# ── CVDataSchema ──────────────────────────────────────────────


class TestCVDataSchema:
    def test_empty_payload_uses_all_defaults(self):
        cv = CVDataSchema()
        assert cv.name == ""
        assert cv.experience == []
        assert cv.skills == []
        assert cv.skills_grouped == []

    def test_full_payload_round_trips(self):
        payload = {
            "name": "Alice",
            "title": "Engineer",
            "email": "a@example.com",
            "summary": "Builder.",
            "experience": [
                {"title": "Eng", "company": "X", "date": "2020", "bullets": ["b1"]},
            ],
            "skills": ["Python", "Go"],
            "skills_grouped": [{"category": "Tech", "items": ["Python"]}],
            "education": [{"degree": "BS", "institution": "MIT"}],
            "projects": [{"name": "P", "tech": ["Python"]}],
            "references": [{"name": "R"}],
        }
        cv = CVDataSchema.model_validate(payload)
        dumped = cv.model_dump()
        assert dumped["name"] == "Alice"
        assert dumped["experience"][0]["bullets"] == ["b1"]
        assert dumped["skills_grouped"][0]["items"] == ["Python"]

    def test_extra_sections_preserved(self):
        """The prompt sometimes appends ad-hoc sections like 'publications'."""
        cv = CVDataSchema.model_validate({"name": "X", "publications": ["paper1", "paper2"]})
        dumped = cv.model_dump()
        assert dumped["publications"] == ["paper1", "paper2"]

    def test_partial_experience_filled_with_defaults(self):
        cv = CVDataSchema.model_validate({"experience": [{"title": "Only Title"}]})
        exp = cv.experience[0]
        assert exp.title == "Only Title"
        assert exp.company == ""
        assert exp.bullets == []

    def test_wrong_type_for_skills_rejected(self):
        with pytest.raises(ValidationError):
            CVDataSchema.model_validate({"skills": "should be a list"})


# ── CoverLetterSchema ─────────────────────────────────────────


class TestCoverLetterSchema:
    def test_defaults(self):
        cl = CoverLetterSchema()
        assert cl.recipient == "Hiring Manager"
        assert cl.salutation == "Dear Hiring Manager,"
        assert cl.sign_off == "Kind regards,"
        assert cl.body_paragraphs == []

    def test_analysis_field_is_dropped(self):
        """``_analysis`` is a debug field the model fills internally; we must not surface it."""
        cl = CoverLetterSchema.model_validate({"_analysis": {"notes": "thinking"}, "recipient": "Bob"})
        dumped = cl.model_dump()
        assert "_analysis" not in dumped
        assert dumped["recipient"] == "Bob"

    def test_body_paragraphs_round_trip(self):
        payload = {"body_paragraphs": ["para 1.", "para 2."], "sign_off": "Sincerely,"}
        cl = CoverLetterSchema.model_validate(payload)
        assert cl.body_paragraphs == ["para 1.", "para 2."]
        assert cl.sign_off == "Sincerely,"


# ── Keyword root models ───────────────────────────────────────


class TestKeywordSchemas:
    def test_categories_schema(self):
        schema = KeywordCategoriesSchema.model_validate(
            {"technical_skills": ["Python"], "tools_platforms": ["AWS"]}
        )
        assert schema.root["technical_skills"] == ["Python"]

    def test_categories_schema_rejects_non_list_values(self):
        with pytest.raises(ValidationError):
            KeywordCategoriesSchema.model_validate({"technical_skills": "Python"})

    def test_categorization_schema(self):
        schema = KeywordCategorizationSchema.model_validate({"python": "tech", "scrum": "process"})
        assert schema.root["python"] == "tech"
        assert schema.root["scrum"] == "process"


# ── Quality review ────────────────────────────────────────────


class TestQualityReviewSchema:
    def test_defaults(self):
        review = QualityReviewSchema()
        assert review.flags == []
        assert review.summary == ""

    def test_flag_round_trip(self):
        payload = {
            "flags": [
                {
                    "item": "Duolingo English: Advanced",
                    "section": "certifications",
                    "category": "certification",
                    "severity": "remove",
                    "reason": "Not relevant.",
                    "suggestion": "",
                }
            ],
            "summary": "1 item flagged",
        }
        review = QualityReviewSchema.model_validate(payload)
        assert review.flags[0].severity == "remove"
        assert review.summary == "1 item flagged"

    def test_flag_with_extra_fields_allowed(self):
        """``extra='allow'`` means LLM-added fields stay attached."""
        flag = QualityFlagSchema.model_validate({"item": "x", "confidence": 0.9})
        dumped = flag.model_dump()
        assert dumped["confidence"] == 0.9


# ── Template recommendation ───────────────────────────────────


class TestTemplateRecommendationSchema:
    def test_defaults(self):
        rec = TemplateRecommendationSchema()
        assert rec.recommended == []
        assert rec.reason == ""

    def test_round_trip(self):
        rec = TemplateRecommendationSchema.model_validate(
            {"recommended": ["modern", "classic", "tech"], "reason": "Tech role."}
        )
        assert rec.recommended == ["modern", "classic", "tech"]
        assert rec.reason == "Tech role."

    def test_recommended_must_be_list_of_strings(self):
        with pytest.raises(ValidationError):
            TemplateRecommendationSchema.model_validate({"recommended": "modern"})
