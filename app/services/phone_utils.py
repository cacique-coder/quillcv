"""Phone number utilities for QuillCV.

Provides server-side normalisation of phone number inputs collected across
the wizard and onboarding flows.  Validation is intentionally lenient — we
do not want to reject unusual international formats.  The goal is to
produce a consistent, clean representation before storing in the PII vault.
"""

import re


def normalize_phone(raw: str) -> str:
    """Normalize a raw phone number string for storage.

    Rules applied:
    - Strip leading/trailing whitespace.
    - Return empty string as-is (field is optional everywhere).
    - Ensure the value starts with '+' when the first character is a digit
      (auto-prepend '+' so stored values are consistently E.164-ish).
    - Strip any character that is not +, digit, space, hyphen, or parenthesis.
    - Collapse runs of whitespace to a single space.
    - Truncate to 30 characters to guard against absurdly long inputs.

    This function does NOT validate correctness — it only normalises format.
    HTML-level pattern validation (``pattern="^\+?[\d\s\-\(\)\.]{7,20}$"``)
    handles basic structural checks on the client side.
    """
    if not raw:
        return ""

    value = raw.strip()
    if not value:
        return ""

    # Auto-prepend '+' when the user omitted it and started with digits
    if value and value[0].isdigit():
        value = "+" + value

    # Keep only characters meaningful in an international phone number
    value = re.sub(r"[^\d\s\+\-\(\)\.]", "", value)

    # Collapse runs of whitespace to a single space
    value = re.sub(r"\s+", " ", value).strip()

    # Hard cap — prevents storing garbage
    return value[:30]
