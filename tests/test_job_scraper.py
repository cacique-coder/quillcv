"""Tests for the job-posting URL scraper.

Regression target: when Indeed served a Cloudflare "Just a moment…" challenge
page (~193 chars), the scraper accepted it as a successful scrape and showed
the user "Full description loaded into the field below (193 characters)" with
the challenge text as the description. The result was:

    Page: Just a moment...
    Sign in
    Additional Verification Required
    Your Ray ID for this request is 9f87f85a7f5fdc10
    Return home   Troubleshooting Cloudflare Errors

These tests pin the detector to that specific input plus a few common
anti-bot / login-wall variants.
"""

from __future__ import annotations

import pytest

from app.cv_generation.adapters.job_scraper import (
    _blocked_error_for,
    _blocked_signature,
    _clean_text,
)


CLOUDFLARE_INDEED_PAGE = (
    "Page: Just a moment...\n"
    "Sign in\n"
    "Additional Verification Required\n"
    "Your Ray ID for this request is 9f87f85a7f5fdc10\n"
    "Return home   Troubleshooting Cloudflare Errors\n"
    "Need more help? Contact us\n"
)


class TestBlockedSignatureDetection:
    def test_cloudflare_indeed_challenge_is_detected(self):
        assert _blocked_signature(_clean_text(CLOUDFLARE_INDEED_PAGE)) is not None

    @pytest.mark.parametrize(
        "snippet",
        [
            "Just a moment...",
            "Your Ray ID for this request is abc123",
            "Additional Verification Required",
            "Checking your browser before accessing the site",
            "Please enable JavaScript and cookies to continue",
            "Attention Required! | Cloudflare",
            "Please verify you are a human",
            "Access denied. You don't have permission to view this page.",
            "You have been blocked.",
            "Sign in to continue to Indeed",
            "Join LinkedIn to see this job",
        ],
    )
    def test_known_block_phrases_detected(self, snippet: str):
        assert _blocked_signature(snippet) is not None, snippet

    def test_real_job_description_not_flagged(self):
        legit = (
            "Senior Software Engineer\n"
            "We are seeking an experienced backend engineer with 5+ years of\n"
            "experience in Python, FastAPI, and PostgreSQL. Responsibilities\n"
            "include designing distributed systems and mentoring junior staff.\n"
        )
        assert _blocked_signature(legit) is None

    def test_detection_is_case_insensitive(self):
        assert _blocked_signature("JUST A MOMENT...") is not None
        assert _blocked_signature("Your RAY ID FOR THIS REQUEST is xyz") is not None


class TestBlockedErrorMessages:
    def test_indeed_url_gets_indeed_message(self):
        msg = _blocked_error_for("https://au.indeed.com/jobs?vjk=abc")
        assert "Indeed" in msg
        assert "paste" in msg.lower()

    def test_linkedin_url_gets_linkedin_message(self):
        msg = _blocked_error_for("https://www.linkedin.com/jobs/view/123")
        assert "LinkedIn" in msg
        assert "paste" in msg.lower()

    def test_unknown_host_gets_generic_message(self):
        msg = _blocked_error_for("https://careers.example.com/job/999")
        assert "anti-bot" in msg.lower() or "blocked" in msg.lower()
        assert "paste" in msg.lower()


@pytest.mark.asyncio
class TestScrapeJobUrlIntegration:
    """End-to-end: feed scrape_job_url an output that mimics Indeed's
    Cloudflare challenge and verify it returns success=False."""

    async def test_cloudflare_challenge_returns_failure(self, monkeypatch, tmp_path):
        from app.cv_generation.adapters import job_scraper

        # Fake the Node subprocess: write the Cloudflare page to the output
        # file the scraper passes us, exit 0, return no stderr.
        async def fake_create_subprocess_exec(*args, **kwargs):
            output_path = args[3]  # node script url output_file
            with open(output_path, "w") as f:
                f.write(CLOUDFLARE_INDEED_PAGE)

            class _Proc:
                returncode = 0

                async def communicate(self):
                    return b"", b""

            return _Proc()

        monkeypatch.setattr(
            "asyncio.create_subprocess_exec",
            fake_create_subprocess_exec,
        )

        result = await job_scraper.scrape_job_url(
            "https://au.indeed.com/jobs?q=principal+software+engineer&vjk=5908d4ac1c98748e"
        )
        assert result["success"] is False
        assert result["text"] == ""
        assert "Indeed" in result["error"]
        assert "paste" in result["error"].lower()
