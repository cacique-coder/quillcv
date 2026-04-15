"""Auto-detect target region from job URL domain and job description text.

Detection runs in two passes:
  1. URL domain matching against known job-board domains (high confidence).
  2. Text scanning for city / country signals in the job description (medium
     confidence).

If neither pass yields a result the caller's ``fallback_region`` (typically
the user's profile region) is returned with ``"low"`` confidence.
"""

import logging
import re
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Domain → region mapping
# ---------------------------------------------------------------------------

# Exact hostname (without "www.") → ISO region code.
DOMAIN_REGION_MAP: dict[str, str] = {
    # Australia
    "seek.com.au": "AU",
    "indeed.com.au": "AU",
    "jora.com.au": "AU",
    # United States
    "indeed.com": "US",
    "glassdoor.com": "US",
    "monster.com": "US",
    # United Kingdom
    "indeed.co.uk": "UK",
    "reed.co.uk": "UK",
    "totaljobs.com": "UK",
    "cv-library.co.uk": "UK",
    # Canada
    "indeed.ca": "CA",
    "jobbank.gc.ca": "CA",
    "workopolis.com": "CA",
    # New Zealand
    "seek.co.nz": "NZ",
    "trademe.co.nz": "NZ",
    "indeed.co.nz": "NZ",
    # Germany
    "indeed.de": "DE",
    "stepstone.de": "DE",
    "xing.com": "DE",
    # France
    "indeed.fr": "FR",
    "pole-emploi.fr": "FR",
    "apec.fr": "FR",
    # Netherlands
    "indeed.nl": "NL",
    "nationalevacaturebank.nl": "NL",
    # India
    "naukri.com": "IN",
    "indeed.co.in": "IN",
    "shine.com": "IN",
    # Brazil
    "catho.com.br": "BR",
    "indeed.com.br": "BR",
    "vagas.com.br": "BR",
    "infojobs.com.br": "BR",
    # UAE
    "bayt.com": "AE",
    "gulftalent.com": "AE",
    "indeed.ae": "AE",
    # Japan
    "indeed.co.jp": "JP",
    "en-japan.com": "JP",
    # Colombia
    "computrabajo.com.co": "CO",
    "elempleo.com": "CO",
    # Venezuela
    "computrabajo.com.ve": "VE",
}

# These are global platforms — URL alone cannot determine region.
_GLOBAL_DOMAINS: frozenset[str] = frozenset({
    "linkedin.com",
    "www.linkedin.com",
    "wellfound.com",
    "angel.co",
    "remote.co",
    "weworkremotely.com",
    "remoteok.com",
    "greenhouse.io",
    "lever.co",
    "workable.com",
})

# Country-code TLD → region (last-resort heuristic, medium confidence).
_TLD_REGION_MAP: dict[str, str] = {
    ".au": "AU",
    ".uk": "UK",
    ".ca": "CA",
    ".nz": "NZ",
    ".de": "DE",
    ".fr": "FR",
    ".nl": "NL",
    ".in": "IN",
    ".br": "BR",
    ".ae": "AE",
    ".jp": "JP",
    ".co": "CO",
    ".ve": "VE",
}

# ---------------------------------------------------------------------------
# Text location signals — ordered from most to least distinctive.
# Each entry is (compiled_regex, region_code).
# ---------------------------------------------------------------------------

_TEXT_SIGNALS: list[tuple[re.Pattern[str], str]] = [
    # Australia
    (re.compile(r"\b(sydney|melbourne|brisbane|perth|adelaide|canberra|hobart|darwin)\b"), "AU"),
    (re.compile(r"\baustrali(?:a|an)\b"), "AU"),
    # United States
    (re.compile(r"\b(new york|san francisco|los angeles|chicago|seattle|austin|boston|denver|atlanta)\b"), "US"),
    (re.compile(r"\bunited states\b"), "US"),
    # United Kingdom
    (re.compile(r"\b(london|manchester|birmingham|edinburgh|glasgow|bristol|leeds|liverpool)\b"), "UK"),
    (re.compile(r"\bunited kingdom\b"), "UK"),
    # Canada
    (re.compile(r"\b(toronto|vancouver|montreal|ottawa|calgary|edmonton|winnipeg)\b"), "CA"),
    (re.compile(r"\bcanad(?:a|ian)\b"), "CA"),
    # New Zealand
    (re.compile(r"\b(auckland|wellington|christchurch|hamilton|dunedin)\b"), "NZ"),
    (re.compile(r"\bnew zealand\b"), "NZ"),
    # Germany
    (re.compile(r"\b(berlin|munich|hamburg|frankfurt|düsseldorf|köln|stuttgart)\b"), "DE"),
    (re.compile(r"\bgerman(?:y)?\b"), "DE"),
    # France
    (re.compile(r"\b(paris|lyon|marseille|toulouse|bordeaux|lille|nantes)\b"), "FR"),
    (re.compile(r"\bfranc(?:e|ais)\b"), "FR"),
    # Netherlands
    (re.compile(r"\b(amsterdam|rotterdam|den haag|utrecht|eindhoven)\b"), "NL"),
    (re.compile(r"\bnetherl(?:ands)?\b"), "NL"),
    # India
    (re.compile(r"\b(mumbai|bangalore|bengaluru|delhi|hyderabad|chennai|pune|kolkata)\b"), "IN"),
    (re.compile(r"\bindia(?:n)?\b"), "IN"),
    # Brazil
    (re.compile(r"\b(são paulo|rio de janeiro|brasília|curitiba|belo horizonte|salvador)\b"), "BR"),
    (re.compile(r"\bbra[sz]il\b"), "BR"),
    # UAE
    (re.compile(r"\b(dubai|abu dhabi|sharjah|ajman)\b"), "AE"),
    (re.compile(r"\buae\b|\bunited arab emirates\b"), "AE"),
    # Japan
    (re.compile(r"\b(tokyo|osaka|kyoto|yokohama|nagoya|fukuoka)\b"), "JP"),
    (re.compile(r"\bjapan(?:ese)?\b"), "JP"),
    # Colombia
    (re.compile(r"\b(bogotá|bogota|medellín|medellin|cali|barranquilla|cartagena)\b"), "CO"),
    (re.compile(r"\bcolombia(?:n)?\b"), "CO"),
    # Venezuela
    (re.compile(r"\b(caracas|maracaibo|valencia|barquisimeto)\b"), "VE"),
    (re.compile(r"\bvenezuel(?:a|an)\b"), "VE"),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_region(
    job_url: str = "",
    job_description: str = "",
    fallback_region: str = "",
) -> dict:
    """Detect the target region from a job URL and/or description.

    Detection strategy (highest confidence first):
      1. Exact job-board domain match from ``DOMAIN_REGION_MAP``.
      2. Subdomain suffix match (e.g. ``jobs.company.seek.com.au``).
      3. Country-code TLD heuristic (medium confidence).
      4. City / country keyword scan of the job description text.
      5. Caller-supplied ``fallback_region`` (low confidence).

    Args:
        job_url: The URL of the job posting (may be empty).
        job_description: The full text of the job description (may be empty).
        fallback_region: Region to use when no signal is found — typically the
            user's profile region.

    Returns:
        A dict with three keys:
            ``region``     — 2-char region code (e.g. ``"AU"``) or ``""``
            ``confidence`` — ``"high"``, ``"medium"``, or ``"low"``
            ``source``     — ``"url"``, ``"text"``, ``"fallback"``, or ``"none"``
    """
    # Pass 1 — URL domain matching
    if job_url:
        result = _detect_from_url(job_url)
        if result:
            return result

    # Pass 2 — text-based heuristics
    if job_description:
        result = _detect_from_text(job_description)
        if result:
            return result

    # Pass 3 — caller fallback
    if fallback_region:
        return {"region": fallback_region, "confidence": "low", "source": "fallback"}

    return {"region": "", "confidence": "low", "source": "none"}


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _detect_from_url(url: str) -> dict | None:
    """Attempt to determine region from the job posting URL.

    Returns a result dict on success, or ``None`` if the domain gives no
    useful signal (e.g. it is a global platform).
    """
    try:
        parsed = urlparse(url.strip())
        # urlparse requires a scheme; add one if missing so netloc is populated.
        if not parsed.netloc:
            parsed = urlparse("https://" + url.strip())
        hostname = parsed.netloc.lower().removeprefix("www.")
    except Exception:
        logger.debug("_detect_from_url: could not parse URL %r", url)
        return None

    # Exact match
    if hostname in DOMAIN_REGION_MAP:
        return {"region": DOMAIN_REGION_MAP[hostname], "confidence": "high", "source": "url"}

    # Subdomain suffix match (e.g. au.indeed.com → still a known domain)
    for domain, region in DOMAIN_REGION_MAP.items():
        if hostname.endswith("." + domain):
            return {"region": region, "confidence": "high", "source": "url"}

    # Global platforms — cannot determine region from URL alone
    if hostname in _GLOBAL_DOMAINS or any(hostname.endswith("." + d) for d in _GLOBAL_DOMAINS):
        return None

    # Country-code TLD fallback (medium confidence)
    for tld, region in _TLD_REGION_MAP.items():
        if hostname.endswith(tld):
            return {"region": region, "confidence": "medium", "source": "url"}

    return None


def _detect_from_text(text: str) -> dict | None:
    """Scan job description text for city / country location signals.

    Returns the first matching region with ``"medium"`` confidence, or
    ``None`` if no signal is found.
    """
    text_lower = text.lower()
    for pattern, region in _TEXT_SIGNALS:
        if pattern.search(text_lower):
            return {"region": region, "confidence": "medium", "source": "text"}
    return None
