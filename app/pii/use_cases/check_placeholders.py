"""Post-generation quality gate: detect placeholder text in CV output.

Catches cases where the AI left template tokens, example data, or
redaction tokens instead of real content.  Returns a list of issues
found so the caller can decide whether to retry or warn the user.
"""

import re

# Redaction tokens that should have been restored
_REDACTION_TOKENS = re.compile(
    r"<<(?:CANDIDATE_NAME|EMAIL_\d+|PHONE_\d+|LINKEDIN_URL|GITHUB_URL|PORTFOLIO_URL|DOB|DOCUMENT_ID|CANDIDATE_SLUG|REF_NAME_\d+|REF_EMAIL_\d+|REF_PHONE_\d+)>>"
)

# Common LLM placeholder patterns
_BRACKET_PLACEHOLDERS = re.compile(
    r"\[(?:Your |Full |First |Last )?"
    r"(?:Name|Email|Phone|Address|City|Country|LinkedIn|Title|Company"
    r"|University|Degree|Date|URL|Number|Here)\]",
    re.IGNORECASE,
)

# Example / dummy domains
_EXAMPLE_EMAILS = re.compile(
    r"[a-zA-Z0-9._%+\-]+@(?:example|placeholder|test|sample|dummy|your)"
    r"\.(?:com|org|net|email)",
    re.IGNORECASE,
)

# Obviously fake phone numbers
_DUMMY_PHONES = re.compile(
    r"(?:\+?0{2,3}[\s\-.]?)?0{3,4}[\s\-.]?0{3,4}[\s\-.]?0{3,4}"  # 000 000 000 etc.
    r"|"
    r"123[\-\s.]?456[\-\s.]?789\d?"  # 123-456-7890
    r"|"
    r"\+00\s"  # +00 prefix
)

# Lorem ipsum
_LOREM = re.compile(r"lorem\s+ipsum", re.IGNORECASE)


def check_placeholders(cv_data: dict) -> list[dict]:
    """Scan structured CV data for placeholder content.

    Returns a list of dicts: [{"field": "name", "value": "...", "reason": "..."}]
    Empty list means the CV passed the check.
    """
    issues: list[dict] = []

    # Check identity fields — these are the most visible and damaging if wrong
    _check_field(issues, cv_data, "name", required=True)
    _check_field(issues, cv_data, "email", required=True)
    _check_field(issues, cv_data, "phone", required=True)
    _check_field(issues, cv_data, "location", required=False)
    _check_field(issues, cv_data, "title", required=False)
    _check_field(issues, cv_data, "summary", required=False)
    _check_field(issues, cv_data, "linkedin", required=False)

    # Walk nested structures for leftover tokens
    _walk_check(issues, cv_data, path="")

    # Deduplicate by (field, reason)
    seen = set()
    unique = []
    for issue in issues:
        key = (issue["field"], issue["reason"])
        if key not in seen:
            seen.add(key)
            unique.append(issue)

    return unique


def _check_field(issues: list, data: dict, field: str, required: bool):
    """Check a top-level field for placeholder content."""
    value = data.get(field, "")
    if not isinstance(value, str):
        return

    if required and not value.strip():
        issues.append({
            "field": field,
            "value": "",
            "reason": f"Required field '{field}' is empty",
        })
        return

    if not value.strip():
        return

    _scan_string(issues, field, value)


def _scan_string(issues: list, field: str, value: str):
    """Run all placeholder pattern checks against a string value."""
    if _REDACTION_TOKENS.search(value):
        issues.append({
            "field": field,
            "value": value[:100],
            "reason": "Contains unreplaced redaction token",
        })

    if _BRACKET_PLACEHOLDERS.search(value):
        issues.append({
            "field": field,
            "value": value[:100],
            "reason": "Contains bracket placeholder text",
        })

    if field == "email" and _EXAMPLE_EMAILS.search(value):
        issues.append({
            "field": field,
            "value": value[:100],
            "reason": "Contains example/dummy email domain",
        })

    if field == "phone" and _DUMMY_PHONES.search(value):
        issues.append({
            "field": field,
            "value": value[:100],
            "reason": "Contains obviously fake phone number",
        })

    if _LOREM.search(value):
        issues.append({
            "field": field,
            "value": value[:100],
            "reason": "Contains lorem ipsum text",
        })


def _walk_check(issues: list, obj, path: str):
    """Recursively check all strings in the data structure for redaction tokens."""
    if isinstance(obj, str):
        if _REDACTION_TOKENS.search(obj):
            issues.append({
                "field": path or "(root)",
                "value": obj[:100],
                "reason": "Contains unreplaced redaction token",
            })
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _walk_check(issues, v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _walk_check(issues, item, f"{path}[{i}]")
