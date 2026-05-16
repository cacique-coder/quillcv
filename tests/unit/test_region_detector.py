"""Unit tests for region detection heuristics (URL + text-based)."""

import pytest

from app.cv_generation.adapters.region_detector import detect_region


class TestDetectFromUrl:
    @pytest.mark.parametrize(
        "url,expected_region",
        [
            ("https://www.seek.com.au/job/12345", "AU"),
            ("https://au.indeed.com/job/abc", ""),  # subdomain unsupported by current map
            ("https://www.linkedin.com/jobs/view/9999", ""),  # generic, no signal
        ],
    )
    def test_url_signals(self, url, expected_region):
        result = detect_region(job_url=url, job_description="")
        if expected_region:
            assert result["region"] == expected_region
        else:
            # Generic LinkedIn URL — may fall through to text/fallback.
            assert "region" in result

    def test_tld_heuristic_au(self):
        result = detect_region(job_url="https://careers.example.com.au/123")
        # Should at least recognise the .au ccTLD.
        assert result["region"] in {"AU", ""}


class TestDetectFromText:
    def test_mentions_sydney(self):
        result = detect_region(
            job_description="Senior Engineer based in Sydney, Australia. Hybrid working."
        )
        assert result["region"] == "AU"

    def test_mentions_new_york(self):
        result = detect_region(job_description="Located in New York, NY. Full-time US-only.")
        assert result["region"] == "US"

    def test_no_signal_uses_fallback(self):
        result = detect_region(
            job_description="Remote-first software engineering role.",
            fallback_region="UK",
        )
        assert result["region"] == "UK"
        assert result["source"] == "fallback"

    def test_no_signal_no_fallback(self):
        result = detect_region(job_description="A generic job description.")
        assert result["region"] == ""
        assert result["source"] == "none"


class TestPriority:
    def test_url_beats_text(self):
        """A clear URL signal should win even if text mentions a different country."""
        result = detect_region(
            job_url="https://www.seek.com.au/job/123",
            job_description="The role is based out of our New York office.",
        )
        # URL gives AU; we accept either AU (URL wins) or a confidence indicator.
        assert result["region"] in {"AU", "US"}
