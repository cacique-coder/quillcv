"""Tests for ATS analyzer — keyword extraction, scoring, and section checks."""

from app.scoring.adapters.keyword_matcher import (
    ATSResult,
    _strip_boilerplate,
    analyze_ats,
    extract_keywords,
)


class TestStripBoilerplate:
    """Tests for _strip_boilerplate() — removing irrelevant job description sections."""

    def test_removes_eeo_section(self):
        text = "About The Role\nBuild APIs\nEqual opportunity employer regardless of race."
        result = _strip_boilerplate(text)
        assert "Equal opportunity" not in result
        assert "Build APIs" in result

    def test_removes_company_intro(self):
        # Intro must be in the first half for the marker to cut it
        text = "We are a great company founded in 2010.\nAbout The Role\nBuild scalable systems.\n" + "More details.\n" * 5
        result = _strip_boilerplate(text)
        assert "great company" not in result
        assert "Build scalable systems" in result

    def test_preserves_full_text_when_no_markers(self):
        text = "Build APIs using Python and Go. 5+ years experience required."
        result = _strip_boilerplate(text)
        assert "Build APIs" in result
        assert "5+ years" in result

    def test_handles_multiple_eeo_markers(self):
        text = "Build APIs\nWe are committed to providing equal opportunities.\nMore legal text."
        result = _strip_boilerplate(text)
        assert "Build APIs" in result
        assert "committed to providing equal" not in result

    def test_does_not_cut_role_marker_in_second_half(self):
        # Role markers should only cut if found in the first half
        text = "A" * 200 + "\nAbout The Role\nMore text"
        result = _strip_boilerplate(text)
        # The marker is past the midpoint, so it should be preserved
        assert "About The Role" in result


class TestExtractKeywords:
    """Tests for regex-based keyword extraction."""

    def test_extracts_tech_patterns(self):
        keywords = extract_keywords("Experience with CI/CD and Node.js required")
        lower_kw = [k.lower() for k in keywords]
        assert "ci/cd" in lower_kw
        assert "node.js" in lower_kw

    def test_filters_noise_words(self):
        keywords = extract_keywords("The company is looking for a candidate with experience")
        lower_kw = [k.lower() for k in keywords]
        assert "the" not in lower_kw
        assert "company" not in lower_kw
        assert "looking" not in lower_kw

    def test_extracts_bigrams(self):
        keywords = extract_keywords("distributed systems and error monitoring are key skills")
        lower_kw = [k.lower() for k in keywords]
        # Bigrams should be found if both words are meaningful
        assert any("distributed" in k for k in lower_kw)

    def test_filters_domains(self):
        keywords = extract_keywords("Visit sentry.io for more info about error monitoring")
        lower_kw = [k.lower() for k in keywords]
        assert "sentry.io" not in lower_kw

    def test_empty_input(self):
        assert extract_keywords("") == []

    def test_short_words_filtered(self):
        keywords = extract_keywords("Use API to get data from the DB and run ML ops")
        lower_kw = [k.lower() for k in keywords]
        # Very short words (<=4 chars) should be filtered for singles
        assert "use" not in lower_kw
        assert "get" not in lower_kw


class TestAnalyzeATS:
    """Tests for the main analyze_ats() function."""

    def test_basic_scoring(self, sample_cv_text, sample_job_description):
        result = analyze_ats(sample_cv_text, sample_job_description)
        assert isinstance(result, ATSResult)
        assert 0 <= result.score <= 100
        assert 0 <= result.keyword_match_pct <= 100

    def test_all_sections_found(self, sample_cv_text, sample_job_description):
        result = analyze_ats(sample_cv_text, sample_job_description)
        # Our sample CV has summary, experience, education, skills
        assert result.section_checks["summary"] is True
        assert result.section_checks["experience"] is True
        assert result.section_checks["education"] is True
        assert result.section_checks["skills"] is True

    def test_missing_section_detected(self, sample_job_description):
        cv_no_summary = "Experience\nBuilt things\nEducation\nMIT\nSkills\nPython"
        result = analyze_ats(cv_no_summary, sample_job_description)
        assert result.section_checks["summary"] is False

    def test_keywords_override(self, sample_cv_text, sample_job_description):
        custom_keywords = ["python", "nonexistent_skill_xyz", "postgresql"]
        result = analyze_ats(sample_cv_text, sample_job_description, keywords_override=custom_keywords)
        assert "python" in result.matched_keywords
        assert "nonexistent_skill_xyz" in result.missing_keywords
        assert len(result.matched_keywords) + len(result.missing_keywords) == 3

    def test_perfect_cv_scores_high(self, sample_job_description):
        perfect_cv = """
        Summary
        Senior engineer with 8 years experience in Python and Go.

        Experience
        Built microservices, CI/CD pipelines, mentored engineers.
        john@test.com +1 555 123 4567

        Education
        B.S. Computer Science

        Skills
        Python, Go, PostgreSQL, Redis, Kubernetes, AWS, distributed systems
        """
        result = analyze_ats(perfect_cv, sample_job_description)
        assert result.score >= 50  # Should score reasonably well

    def test_empty_cv_scores_low(self, sample_job_description):
        result = analyze_ats("", sample_job_description)
        assert result.score < 30

    def test_formatting_issues_detected(self, sample_job_description):
        cv_with_issues = "No email or phone here\n" * 100  # Very long, no contact
        result = analyze_ats(cv_with_issues, sample_job_description)
        assert len(result.formatting_issues) > 0
        assert any("email" in issue.lower() for issue in result.formatting_issues)

    def test_score_components_bounded(self, sample_cv_text, sample_job_description):
        result = analyze_ats(sample_cv_text, sample_job_description)
        # Score should never exceed 100 or go below 0
        assert 0 <= result.score <= 100

    def test_quantified_achievements_detected(self, sample_job_description):
        cv_with_numbers = """
        Summary
        Engineer

        Experience
        Improved performance by 40%, serving 10M users daily.
        john@test.com +1 555 123 4567

        Education
        MIT

        Skills
        Python
        """
        result = analyze_ats(cv_with_numbers, sample_job_description)
        # Should not recommend quantifying achievements since they exist
        assert not any("quantify" in r.lower() for r in result.recommendations)
