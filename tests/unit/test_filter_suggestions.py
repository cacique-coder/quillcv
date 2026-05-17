"""Unit tests for the personal-detail suggestion filter.

Verifies that quality-review flags and ATS recommendations that describe
identity/contact fields are stripped from the suggestions panel while
genuine content-improvement items are preserved.
"""

import pytest

from app.pii.use_cases.filter_suggestions import (
    filter_personal_detail_items,
    _is_personal_detail_flag,
    _is_personal_detail_recommendation,
)


class TestIsPersonalDetailFlag:
    """Tests for the flag-level filter."""

    def test_category_personal_info_filtered(self):
        flag = {
            "category": "personal_info",
            "section": "header",
            "item": "John Doe",
            "reason": "Name is missing",
        }
        assert _is_personal_detail_flag(flag) is True

    def test_category_email_filtered(self):
        flag = {
            "category": "email",
            "section": "contact",
            "item": "missing email",
            "reason": "No email address provided",
        }
        assert _is_personal_detail_flag(flag) is True

    def test_section_phone_filtered(self):
        flag = {
            "category": "other",
            "section": "phone",
            "item": "+61 000 000 000",
            "reason": "Phone number is missing",
        }
        assert _is_personal_detail_flag(flag) is True

    def test_item_text_name_mention_filtered(self):
        flag = {
            "category": "other",
            "section": "header",
            "item": "Your name field",
            "reason": "Required name field is empty",
        }
        assert _is_personal_detail_flag(flag) is True

    def test_reason_email_mention_filtered(self):
        flag = {
            "category": "completeness",
            "section": "contact",
            "item": "contact info",
            "reason": "Add your email to the contact section",
        }
        assert _is_personal_detail_flag(flag) is True

    def test_content_skill_kept(self):
        flag = {
            "category": "skill",
            "section": "skills",
            "item": "Duolingo English: Advanced",
            "reason": "Low-prestige certification",
            "severity": "remove",
        }
        assert _is_personal_detail_flag(flag) is False

    def test_content_phrasing_kept(self):
        flag = {
            "category": "phrasing",
            "section": "experience",
            "item": "Responsible for leading teams",
            "reason": "Weak action verb",
            "suggestion": "Use 'Led' instead of 'Responsible for'",
            "severity": "improve",
        }
        assert _is_personal_detail_flag(flag) is False

    def test_content_certification_kept(self):
        flag = {
            "category": "certification",
            "section": "certifications",
            "item": "Udemy Python Bootcamp",
            "reason": "Unaccredited course",
            "severity": "remove",
        }
        assert _is_personal_detail_flag(flag) is False

    def test_content_experience_kept(self):
        flag = {
            "category": "experience",
            "section": "experience",
            "item": "Helped with tasks",
            "reason": "Vague, lacks quantification",
            "severity": "improve",
        }
        assert _is_personal_detail_flag(flag) is False

    def test_linkedin_section_filtered(self):
        flag = {
            "category": "other",
            "section": "linkedin",
            "item": "linkedin.com/in/placeholder",
            "reason": "LinkedIn URL missing",
        }
        assert _is_personal_detail_flag(flag) is True

    def test_location_category_filtered(self):
        flag = {
            "category": "location",
            "section": "header",
            "item": "City, Country",
            "reason": "Location field is a placeholder",
        }
        assert _is_personal_detail_flag(flag) is True


class TestIsPersonalDetailRecommendation:
    """Tests for the recommendation text filter."""

    def test_add_phone_filtered(self):
        assert _is_personal_detail_recommendation("Add your phone number to the contact section") is True

    def test_include_email_filtered(self):
        assert _is_personal_detail_recommendation("Include your email address for recruiters") is True

    def test_add_linkedin_filtered(self):
        assert _is_personal_detail_recommendation("Add your LinkedIn profile URL") is True

    def test_missing_name_filtered(self):
        assert _is_personal_detail_recommendation("Missing your name from the document header") is True

    def test_provide_contact_filtered(self):
        assert _is_personal_detail_recommendation("Provide contact details for the recruiter") is True

    def test_content_rec_kept(self):
        assert _is_personal_detail_recommendation(
            "Add quantified achievements to your experience bullets"
        ) is False

    def test_keyword_density_kept(self):
        assert _is_personal_detail_recommendation(
            "Increase keyword density by including more Python references"
        ) is False

    def test_missing_section_header_kept(self):
        assert _is_personal_detail_recommendation(
            "Missing 'Education' section — add your academic background"
        ) is False

    def test_add_summary_kept(self):
        assert _is_personal_detail_recommendation(
            "Add a professional summary to improve ATS scoring"
        ) is False


class TestFilterPersonalDetailItems:
    """End-to-end tests for the public filter function."""

    def test_empty_inputs_return_empty_lists(self):
        flags, recs = filter_personal_detail_items(None, None)
        assert flags == []
        assert recs == []

    def test_all_content_flags_preserved(self):
        flags = [
            {
                "category": "skill",
                "section": "skills",
                "item": "Duolingo English",
                "reason": "Low-prestige",
                "severity": "remove",
            },
            {
                "category": "phrasing",
                "section": "experience",
                "item": "Was involved in",
                "reason": "Weak verb",
                "severity": "improve",
            },
        ]
        filtered, _ = filter_personal_detail_items(flags, [])
        assert len(filtered) == 2

    def test_personal_flags_removed(self):
        flags = [
            {
                "category": "personal_info",
                "section": "header",
                "item": "Full name missing",
                "reason": "No name found",
                "severity": "improve",
            },
            {
                "category": "skill",
                "section": "skills",
                "item": "Duolingo",
                "reason": "Low-prestige",
                "severity": "remove",
            },
        ]
        filtered, _ = filter_personal_detail_items(flags, [])
        assert len(filtered) == 1
        assert filtered[0]["category"] == "skill"

    def test_personal_recs_removed(self):
        recs = [
            "Add your phone number",
            "Include LinkedIn URL",
            "Add quantified achievements to experience bullets",
        ]
        _, filtered = filter_personal_detail_items([], recs)
        assert len(filtered) == 1
        assert "quantified" in filtered[0]

    def test_mixed_flags_and_recs(self):
        flags = [
            {"category": "email", "section": "contact", "item": "missing email", "reason": "No email", "severity": "improve"},
            {"category": "phrasing", "section": "experience", "item": "weak bullet", "reason": "Vague", "severity": "improve"},
        ]
        recs = [
            "Include your email address",
            "Quantify your achievements with numbers",
        ]
        filtered_flags, filtered_recs = filter_personal_detail_items(flags, recs)
        assert len(filtered_flags) == 1
        assert filtered_flags[0]["category"] == "phrasing"
        assert len(filtered_recs) == 1
        assert "Quantify" in filtered_recs[0]

    def test_does_not_mutate_inputs(self):
        flags = [{"category": "email", "item": "email", "reason": "missing", "section": "header", "severity": "improve"}]
        recs = ["Add your email"]
        original_flags = list(flags)
        original_recs = list(recs)
        filter_personal_detail_items(flags, recs)
        assert flags == original_flags
        assert recs == original_recs
