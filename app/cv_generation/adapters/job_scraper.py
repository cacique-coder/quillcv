"""Scrape a job posting URL using headless Chromium via Puppeteer."""

import asyncio
import logging
import re
import tempfile
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
SCRAPE_SCRIPT = PROJECT_ROOT / "scrape_job.js"

# Maximum characters to return — enough for the AI, prevents huge payloads
MAX_TEXT_LENGTH = 15_000


def _is_valid_url(url: str) -> bool:
    """Return True if the URL looks like a valid http/https URL."""
    try:
        parsed = urlparse(url.strip())
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def _clean_text(text: str) -> str:
    """Normalise whitespace and strip control characters from scraped text."""
    # Remove non-printable chars (keep newlines and tabs)
    text = re.sub(r"[^\x09\x0A\x0D\x20-\x7E\x80-\xFF]", "", text)
    # Collapse excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# Phrases that strongly indicate the page is an anti-bot challenge, login wall,
# or other interstitial — not the actual job description. Match case-insensitively.
# Be conservative: only add phrases that are extremely unlikely to appear inside
# a legitimate job posting.
_BLOCKED_SIGNATURES = (
    "just a moment",                       # Cloudflare interstitial title
    "ray id for this request",             # Cloudflare error pages
    "additional verification required",    # Indeed / Cloudflare
    "checking your browser before",        # Cloudflare DDoS challenge
    "enable javascript and cookies to continue",  # Cloudflare
    "attention required! | cloudflare",    # Cloudflare 1020
    "please verify you are a human",       # generic captcha
    "press & hold to confirm you are",     # Datadome / PerimeterX
    "access denied",                       # generic block (Akamai / others)
    "you have been blocked",               # Cloudflare / Sucuri
    "sign in to continue to indeed",       # Indeed login wall
    "join linkedin to see this job",       # LinkedIn login wall
    "sign in to view this job",            # LinkedIn login wall
)


def _blocked_signature(text: str) -> str | None:
    """Return the matched sentinel phrase if the text looks like a block page."""
    haystack = text.lower()
    for phrase in _BLOCKED_SIGNATURES:
        if phrase in haystack:
            return phrase
    return None


def _blocked_error_for(url: str) -> str:
    """Return a user-facing error message for a blocked page, tailored per host."""
    host = urlparse(url).netloc.lower()
    if "indeed." in host:
        return ("Indeed blocked the request with a Cloudflare challenge. "
                "Please copy the job description from Indeed and paste it below.")
    if "linkedin." in host:
        return ("LinkedIn blocked the request. "
                "Please copy the job description from LinkedIn and paste it below.")
    return ("The site blocked our automated request (anti-bot challenge). "
            "Please copy the job description and paste it below.")


async def scrape_job_url(url: str) -> dict:
    """Scrape a job posting URL using headless Chromium.

    Returns:
        {"success": True,  "text": "...", "title": "...", "error": None}
        {"success": False, "text": "",    "title": "",    "error": "reason"}
    """
    if not url or not url.strip():
        return {"success": False, "text": "", "title": "", "error": "No URL provided."}

    url = url.strip()
    if not _is_valid_url(url):
        return {"success": False, "text": "", "title": "", "error": "Invalid URL — must start with http:// or https://."}

    if not SCRAPE_SCRIPT.exists():
        logger.error("scrape_job.js not found at %s", SCRAPE_SCRIPT)
        return {"success": False, "text": "", "title": "", "error": "Scraper script not available."}

    output_file = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            output_file = Path(f.name)

        proc = await asyncio.create_subprocess_exec(
            "node", str(SCRAPE_SCRIPT), url, str(output_file),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            _stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=20)
        except TimeoutError:
            try:
                proc.kill()
            except Exception:
                logger.debug("Failed to kill scraper process for %s", url)
            logger.warning("Job scrape timed out for %s", url)
            return {"success": False, "text": "", "title": "", "error": "The page took too long to load. Try pasting the description manually."}

        if proc.returncode != 0:
            err_detail = stderr.decode(errors="replace").strip()
            logger.warning("scrape_job.js exited %d for %s: %s", proc.returncode, url, err_detail)
            return {"success": False, "text": "", "title": "", "error": "Could not load the page. The site may be blocking automated access — paste the description manually."}

        if not output_file.exists():
            logger.error("Scraper produced no output file for %s", url)
            return {"success": False, "text": "", "title": "", "error": "Scraper produced no output."}

        raw = output_file.read_text(encoding="utf-8", errors="replace")
        text = _clean_text(raw)

        # Reject anti-bot / login-wall pages even when they're long enough to
        # have slipped past the min-length check. Cloudflare's "Just a moment…"
        # interstitial on Indeed is ~200 chars, well above 50.
        signature = _blocked_signature(text)
        if signature:
            logger.info("Job scrape blocked by interstitial (%r) for %s", signature, url)
            return {"success": False, "text": "", "title": "", "error": _blocked_error_for(url)}

        if len(text) < 50:
            # Provide a LinkedIn-specific hint when the site blocks the request
            if "linkedin.com" in url.lower():
                return {"success": False, "text": "", "title": "",
                        "error": "LinkedIn blocked the request. Please copy the job description from LinkedIn and paste it below."}
            return {"success": False, "text": "", "title": "", "error": "No job description text found on that page. Try pasting manually."}

        # Extract an optional title from the first line if the scraper prefixed it
        title = ""
        lines = text.splitlines()
        if lines and lines[0].startswith("Job Title:"):
            title = lines[0].removeprefix("Job Title:").strip()
            text = "\n".join(lines[1:]).strip()
        elif lines and lines[0].startswith("Page:"):
            title = lines[0].removeprefix("Page:").strip()
            text = "\n".join(lines[1:]).strip()

        # Trim to max length
        if len(text) > MAX_TEXT_LENGTH:
            text = text[:MAX_TEXT_LENGTH]

        return {"success": True, "text": text, "title": title, "error": None}

    except Exception:
        logger.exception("Unexpected error scraping %s", url)
        return {"success": False, "text": "", "title": "", "error": "An unexpected error occurred. Please paste the description manually."}
    finally:
        if output_file and output_file.exists():
            output_file.unlink(missing_ok=True)
