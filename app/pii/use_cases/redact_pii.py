"""PII redaction for CV text before sending to external AI APIs.

Replaces the user's name, email addresses, phone numbers, date of birth,
document ID (cédula / national ID), and reference contacts with stable
placeholders so that the LLM never sees real identity data.  After generation
the placeholders are swapped back to real values.

Usage:
    redactor = PIIRedactor(full_name="Jane Doe")
    redacted_text = redactor.redact(cv_text)
    # ... send redacted_text to LLM, get cv_data dict back ...
    restored_data = redactor.restore(cv_data)

Extended usage (with additional PII from vault):
    redactor = PIIRedactor(
        full_name="Jane Doe",
        dob="1990-05-15",
        document_id="12345678",
        references=[
            {"name": "Bob Smith", "email": "bob@example.com", "phone": "+1 555 0100"},
        ],
    )
"""

import copy
import re
from dataclasses import dataclass, field

# Stable tokens — deliberately ugly so the LLM won't confuse them with real content
_NAME_TOKEN = "<<CANDIDATE_NAME>>"  # noqa: S105
_EMAIL_TOKEN_PREFIX = "<<EMAIL_"       # noqa: S105  # <<EMAIL_1>>, <<EMAIL_2>>, ...
_PHONE_TOKEN_PREFIX = "<<PHONE_"       # noqa: S105  # <<PHONE_1>>, <<PHONE_2>>, ...
_DOB_TOKEN = "<<DOB>>"  # noqa: S105
_DOCUMENT_ID_TOKEN = "<<DOCUMENT_ID>>"  # noqa: S105
_REF_NAME_PREFIX = "<<REF_NAME_"       # <<REF_NAME_1>>, ...
_REF_EMAIL_PREFIX = "<<REF_EMAIL_"     # <<REF_EMAIL_1>>, ...
_REF_PHONE_PREFIX = "<<REF_PHONE_"     # <<REF_PHONE_1>>, ...
_LINKEDIN_TOKEN = "<<LINKEDIN_URL>>"  # noqa: S105
_GITHUB_TOKEN = "<<GITHUB_URL>>"  # noqa: S105
_PORTFOLIO_TOKEN = "<<PORTFOLIO_URL>>"  # noqa: S105
_LOCATION_TOKEN = "<<LOCATION>>"  # noqa: S105

# Fields in a CV dict that contain free-form text we want to scrub for embedded PII
# (names/emails/phones inadvertently mentioned inside summary, bullets, etc.)
_TEXT_SCAN_TOP_LEVEL = ("title", "summary")
_TEXT_SCAN_EXP_FIELDS = ("title", "company", "location", "tech")
_TEXT_SCAN_PROJECT_FIELDS = ("name", "description", "url")
_TEXT_SCAN_EDU_FIELDS = ("degree", "institution")

# Patterns
_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
)

# International phone patterns — covers:
#   +61 400 123 456, (02) 9123 4567, +1-555-123-4567, 0400 123 456, etc.
_PHONE_RE = re.compile(
    r"(?<!\d)"                 # not preceded by digit
    r"(?:"
    r"\+[\d]{1,3}[\s\-.]?"    # international prefix
    r")?"
    r"(?:\(?\d{1,4}\)?[\s\-.]?)"  # area code / first group
    r"(?:[\d][\d\s\-\.]{5,12}\d)" # remaining digits with separators
    r"(?!\d)",                 # not followed by digit
)

# LinkedIn URLs — linkedin.com/in/username or linkedin.com/in/first-last-hash
_LINKEDIN_RE = re.compile(
    r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w\-\.]+/?",
    re.IGNORECASE,
)

# GitHub URLs — github.com/username (but not github.com/orgs/ or github.com/features/)
_GITHUB_RE = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/(?!orgs/|features/|about/|pricing|enterprise|sponsors)[\w\-\.]+/?",
    re.IGNORECASE,
)

# Generic portfolio/personal site URLs that contain the person's name
# (matched dynamically based on name variants, not a static regex)

# Date of birth — common formats: YYYY-MM-DD, DD/MM/YYYY, DD.MM.YYYY, Month D YYYY
_DOB_RE = re.compile(
    r"\b(?:"
    r"\d{4}[-/]\d{2}[-/]\d{2}"                        # YYYY-MM-DD / YYYY/MM/DD
    r"|\d{1,2}[-/.]\d{1,2}[-/.]\d{4}"                 # DD-MM-YYYY / DD/MM/YYYY
    r"|(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"\s+\d{1,2},?\s+\d{4}"                           # Month D YYYY
    r")\b",
    re.IGNORECASE,
)


@dataclass
class PIIRedactor:
    """Redact and restore PII in CV text and structured CV data."""

    full_name: str
    dob: str = ""
    document_id: str = ""
    references: list[dict] = field(default_factory=list)
    linkedin_url: str = ""
    github_url: str = ""
    portfolio_url: str = ""
    location: str = ""

    _emails: list[str] = field(default_factory=list, init=False)
    _phones: list[str] = field(default_factory=list, init=False)
    _name_variants: list[str] = field(default_factory=list, init=False)
    _linkedin: str = field(default="", init=False)
    _github: str = field(default="", init=False)
    _portfolio: str = field(default="", init=False)
    _location: str = field(default="", init=False)

    def __post_init__(self):
        self.full_name = self.full_name.strip()
        self._name_variants = _name_variants(self.full_name)
        self._linkedin = self.linkedin_url.strip()
        self._github = self.github_url.strip()
        self._portfolio = (self.portfolio_url or "").strip()
        self._location = (self.location or "").strip()

    @classmethod
    def from_cv_data(cls, cv_data: dict) -> "PIIRedactor":
        """Construct a redactor seeded with the CV dict's own PII fields."""
        return cls(
            full_name=cv_data.get("full_name") or cv_data.get("name") or "",
            dob=cv_data.get("dob") or "",
            document_id=cv_data.get("document_id") or "",
            references=cv_data.get("references") or [],
            linkedin_url=cv_data.get("linkedin") or "",
            github_url=cv_data.get("github") or "",
            portfolio_url=cv_data.get("portfolio") or "",
            location=cv_data.get("location") or "",
        )

    def redact(self, text: str) -> str:
        """Replace PII in raw CV text with tokens. Returns redacted text."""
        # 1. Extract and replace emails
        self._emails = []
        def _replace_email(m: re.Match) -> str:
            email = m.group(0)
            if email not in self._emails:
                self._emails.append(email)
            idx = self._emails.index(email) + 1
            return f"{_EMAIL_TOKEN_PREFIX}{idx}>>"
        text = _EMAIL_RE.sub(_replace_email, text)

        # 2. Redact LinkedIn URLs (contain name slugs like daniel-zambrano)
        if self._linkedin:
            text = text.replace(self._linkedin, _LINKEDIN_TOKEN)
        text = _LINKEDIN_RE.sub(_LINKEDIN_TOKEN, text)

        # 3. Redact GitHub URLs (usernames often match real names)
        if self._github:
            text = text.replace(self._github, _GITHUB_TOKEN)
        text = _GITHUB_RE.sub(_GITHUB_TOKEN, text)

        # 4. Redact URLs containing name variants (portfolio sites, personal domains)
        # Only match slug forms that appear in URL-like context (after / . or @) to
        # avoid clobbering plain-text name occurrences that step 6 handles correctly.
        for variant in self._name_variants:
            # Match name in URL slug form: daniel-zambrano, daniel.zambrano, danielzambrano
            slug_variants = [
                variant.lower().replace(" ", "-"),   # daniel-zambrano
                variant.lower().replace(" ", "."),   # daniel.zambrano
                variant.lower().replace(" ", ""),    # danielzambrano
                variant.lower().replace(" ", "_"),   # daniel_zambrano
            ]
            for slug in slug_variants:
                if slug and len(slug) > 3:
                    # Lookbehind: slug must be preceded by a URL separator (/ . @)
                    # Lookahead: slug must end at a word/URL boundary
                    text = re.sub(
                        r'(?<=[/\.@])' + re.escape(slug) + r'(?=[/\.\s"\']|$)',
                        "<<CANDIDATE_SLUG>>",
                        text,
                        flags=re.IGNORECASE,
                    )

        # 5. Extract and replace phones
        self._phones = []
        def _replace_phone(m: re.Match) -> str:
            phone = m.group(0).strip()
            if phone not in self._phones:
                self._phones.append(phone)
            idx = self._phones.index(phone) + 1
            return f"{_PHONE_TOKEN_PREFIX}{idx}>>"
        text = _PHONE_RE.sub(_replace_phone, text)

        # 6. Replace name variants (longest first to avoid partial matches)
        for variant in self._name_variants:
            text = re.sub(re.escape(variant), _NAME_TOKEN, text, flags=re.IGNORECASE)

        # 7. Redact reference contacts (name, email, phone within reference blocks)
        for i, ref in enumerate(self.references, 1):
            if ref.get("name"):
                text = re.sub(re.escape(ref["name"]), f"{_REF_NAME_PREFIX}{i}>>", text, flags=re.IGNORECASE)
            # Reference email/phone are already caught by regexes above, but we
            # also assign them explicit ref-specific tokens so restore() is precise.
            if ref.get("email"):
                text = text.replace(f"{_EMAIL_TOKEN_PREFIX}", f"{_REF_EMAIL_PREFIX}")
                # More targeted: replace any occurrence of the raw email value (if not yet tokenised)
                text = text.replace(ref["email"], f"{_REF_EMAIL_PREFIX}{i}>>")
            if ref.get("phone"):
                text = text.replace(ref["phone"], f"{_REF_PHONE_PREFIX}{i}>>")

        # 8. Redact DOB if provided
        if self.dob:
            text = text.replace(self.dob, _DOB_TOKEN)
        # Also redact DOB matched by pattern when not provided explicitly
        if not self.dob:
            text = _DOB_RE.sub(_DOB_TOKEN, text)

        # 9. Redact document ID if provided
        if self.document_id:
            text = text.replace(self.document_id, _DOCUMENT_ID_TOKEN)

        return text

    def redact_cv_dict(self, cv_data: dict) -> dict:
        """Return a deep-redacted copy of a structured CV dict.

        Replaces top-level identity fields (name, email, phone, location,
        linkedin, github, portfolio, dob) with stable tokens; replaces every
        reference's name/email/phone with REF tokens; and scrubs any embedded
        PII inside free-text fields (summary, experience bullets, project
        descriptions, etc.) using the same regex/name-variant logic as
        ``redact()`` for raw text.

        After this call you can serialise the result to JSON and embed it in
        an LLM prompt safely. Use ``restore()`` on the parsed response to
        swap real values back in.
        """
        out = copy.deepcopy(cv_data)

        # 1. Top-level identity fields → tokens (only if non-empty)
        if out.get("name"):
            out["name"] = _NAME_TOKEN
        if out.get("email"):
            email = str(out["email"])
            if email not in self._emails:
                self._emails.append(email)
            idx = self._emails.index(email) + 1
            out["email"] = f"{_EMAIL_TOKEN_PREFIX}{idx}>>"
        if out.get("phone"):
            phone = str(out["phone"])
            if phone not in self._phones:
                self._phones.append(phone)
            idx = self._phones.index(phone) + 1
            out["phone"] = f"{_PHONE_TOKEN_PREFIX}{idx}>>"
        if out.get("location"):
            # Track for restore
            self._location = out["location"] if not self._location else self._location
            out["location"] = _LOCATION_TOKEN
        if out.get("linkedin"):
            self._linkedin = out["linkedin"] if not self._linkedin else self._linkedin
            out["linkedin"] = _LINKEDIN_TOKEN
        if out.get("github"):
            self._github = out["github"] if not self._github else self._github
            out["github"] = _GITHUB_TOKEN
        if out.get("portfolio"):
            self._portfolio = out["portfolio"] if not self._portfolio else self._portfolio
            out["portfolio"] = _PORTFOLIO_TOKEN
        if out.get("dob"):
            self.dob = out["dob"] if not self.dob else self.dob
            out["dob"] = _DOB_TOKEN
        if out.get("document_id"):
            self.document_id = out["document_id"] if not self.document_id else self.document_id
            out["document_id"] = _DOCUMENT_ID_TOKEN

        # 2. References → ref tokens (must come before text scrub so we
        # don't double-tokenize embedded ref emails/phones into <<EMAIL_n>>).
        refs = out.get("references")
        if refs:
            # Seed self.references for restore() if not already populated
            if not self.references:
                self.references = [dict(r) for r in refs if isinstance(r, dict)]
            new_refs = []
            for i, ref in enumerate(refs, 1):
                if not isinstance(ref, dict):
                    new_refs.append(ref)
                    continue
                r = dict(ref)
                if r.get("name"):
                    r["name"] = f"{_REF_NAME_PREFIX}{i}>>"
                if r.get("email"):
                    r["email"] = f"{_REF_EMAIL_PREFIX}{i}>>"
                if r.get("phone"):
                    r["phone"] = f"{_REF_PHONE_PREFIX}{i}>>"
                new_refs.append(r)
            out["references"] = new_refs

        # 3. Walk the rest of the dict and run text-redaction on free-form
        # string values. Skip the structured identity fields we already
        # tokenized, and skip the references list we already handled.
        _STRUCTURED_KEYS = {
            "name", "email", "phone", "location", "linkedin", "github",
            "portfolio", "dob", "document_id", "references",
        }
        for k, v in list(out.items()):
            if k in _STRUCTURED_KEYS or k.startswith("_"):
                continue
            out[k] = _walk_text_redact(v, self._redact_text_for_dict)

        return out

    def _redact_text_for_dict(self, text: str) -> str:
        """Scrub PII from a free-form text string using current state.

        Unlike ``redact()`` (which resets ``_emails``/``_phones``), this method
        appends to the existing lists so tokens stay consistent across the
        whole CV dict.
        """
        if not text or not isinstance(text, str):
            return text

        # Emails
        def _replace_email(m: re.Match) -> str:
            email = m.group(0)
            if email not in self._emails:
                self._emails.append(email)
            idx = self._emails.index(email) + 1
            return f"{_EMAIL_TOKEN_PREFIX}{idx}>>"
        text = _EMAIL_RE.sub(_replace_email, text)

        # LinkedIn / GitHub URLs
        if self._linkedin:
            text = text.replace(self._linkedin, _LINKEDIN_TOKEN)
        text = _LINKEDIN_RE.sub(_LINKEDIN_TOKEN, text)
        if self._github:
            text = text.replace(self._github, _GITHUB_TOKEN)
        text = _GITHUB_RE.sub(_GITHUB_TOKEN, text)

        # Portfolio URL (literal match only — no generic regex to avoid false positives)
        if self._portfolio:
            text = text.replace(self._portfolio, _PORTFOLIO_TOKEN)

        # Slug forms of the candidate name in URLs
        for variant in self._name_variants:
            slug_variants = [
                variant.lower().replace(" ", "-"),
                variant.lower().replace(" ", "."),
                variant.lower().replace(" ", ""),
                variant.lower().replace(" ", "_"),
            ]
            for slug in slug_variants:
                if slug and len(slug) > 3:
                    text = re.sub(
                        r'(?<=[/\.@])' + re.escape(slug) + r'(?=[/\.\s"\']|$)',
                        "<<CANDIDATE_SLUG>>",
                        text,
                        flags=re.IGNORECASE,
                    )

        # Phones
        def _replace_phone(m: re.Match) -> str:
            phone = m.group(0).strip()
            if phone not in self._phones:
                self._phones.append(phone)
            idx = self._phones.index(phone) + 1
            return f"{_PHONE_TOKEN_PREFIX}{idx}>>"
        text = _PHONE_RE.sub(_replace_phone, text)

        # Name variants (longest first)
        for variant in self._name_variants:
            text = re.sub(re.escape(variant), _NAME_TOKEN, text, flags=re.IGNORECASE)

        # Location literal
        if self._location:
            text = text.replace(self._location, _LOCATION_TOKEN)

        # Reference identifiers
        for i, ref in enumerate(self.references, 1):
            if ref.get("name"):
                text = re.sub(re.escape(ref["name"]), f"{_REF_NAME_PREFIX}{i}>>", text, flags=re.IGNORECASE)
            if ref.get("email"):
                text = text.replace(ref["email"], f"{_REF_EMAIL_PREFIX}{i}>>")
            if ref.get("phone"):
                text = text.replace(ref["phone"], f"{_REF_PHONE_PREFIX}{i}>>")

        # DOB / document ID
        if self.dob:
            text = text.replace(self.dob, _DOB_TOKEN)
        if self.document_id:
            text = text.replace(self.document_id, _DOCUMENT_ID_TOKEN)

        return text

    def restore(self, cv_data: dict) -> dict:
        """Replace tokens back to real values in the structured CV data dict.

        Walks the entire dict/list tree so tokens in nested fields
        (experience bullets, references, etc.) are also restored.
        """
        return _walk_restore(cv_data, self._build_replacement_map())

    def _build_replacement_map(self) -> dict[str, str]:
        """Build a token→real-value mapping."""
        mapping: dict[str, str] = {_NAME_TOKEN: self.full_name}
        for i, email in enumerate(self._emails, 1):
            mapping[f"{_EMAIL_TOKEN_PREFIX}{i}>>"] = email
        for i, phone in enumerate(self._phones, 1):
            mapping[f"{_PHONE_TOKEN_PREFIX}{i}>>"] = phone

        if self._linkedin:
            mapping[_LINKEDIN_TOKEN] = self._linkedin
        if self._github:
            mapping[_GITHUB_TOKEN] = self._github
        if self._portfolio:
            mapping[_PORTFOLIO_TOKEN] = self._portfolio
        if self._location:
            mapping[_LOCATION_TOKEN] = self._location
        # Restore slug placeholder with the name (best effort)
        mapping["<<CANDIDATE_SLUG>>"] = self.full_name.lower().replace(" ", "-")

        if self.dob:
            mapping[_DOB_TOKEN] = self.dob
        if self.document_id:
            mapping[_DOCUMENT_ID_TOKEN] = self.document_id

        for i, ref in enumerate(self.references, 1):
            if ref.get("name"):
                mapping[f"{_REF_NAME_PREFIX}{i}>>"] = ref["name"]
            if ref.get("email"):
                mapping[f"{_REF_EMAIL_PREFIX}{i}>>"] = ref["email"]
            if ref.get("phone"):
                mapping[f"{_REF_PHONE_PREFIX}{i}>>"] = ref["phone"]

        return mapping


def _name_variants(full_name: str) -> list[str]:
    """Generate name variants to catch different orderings in the CV.

    For "Jane Marie Doe" we try: full name, first+last, last+first,
    sorted longest-first so replacements don't leave partial matches.
    """
    parts = full_name.split()
    if not parts:
        return []

    variants = {full_name}
    if len(parts) >= 2:
        first, last = parts[0], parts[-1]
        variants.add(f"{first} {last}")
        variants.add(f"{last} {first}")       # some formats list surname first
        variants.add(f"{last}, {first}")       # "Doe, Jane" format

    # Sort longest first
    return sorted(variants, key=len, reverse=True)


def _walk_text_redact(obj, redact_fn):
    """Recursively apply ``redact_fn`` to every string in a data structure.

    Used by ``redact_cv_dict`` to scrub embedded PII inside summary,
    experience bullets, project descriptions, etc.
    """
    if isinstance(obj, str):
        return redact_fn(obj)
    if isinstance(obj, dict):
        return {k: _walk_text_redact(v, redact_fn) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_walk_text_redact(item, redact_fn) for item in obj]
    return obj


def _walk_restore(obj, mapping: dict[str, str]):
    """Recursively replace tokens in strings throughout a data structure."""
    if isinstance(obj, str):
        for token, real in mapping.items():
            obj = obj.replace(token, real)
        return obj
    if isinstance(obj, dict):
        return {k: _walk_restore(v, mapping) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_walk_restore(item, mapping) for item in obj]
    return obj
