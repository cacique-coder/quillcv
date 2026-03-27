"""Sanitize user inputs before they reach the LLM to mitigate prompt injection."""

import logging
import re

logger = logging.getLogger(__name__)

# Patterns that indicate prompt injection attempts
_INJECTION_PATTERNS = [
    # Direct instruction overrides
    r"ignore\s+(all\s+)?(previous|above|prior|earlier)\s+(instructions?|prompts?|rules?|context)",
    r"disregard\s+(all\s+)?(previous|above|prior|earlier)\s+(instructions?|prompts?|rules?|context)",
    r"forget\s+(all\s+)?(previous|above|prior|earlier)\s+(instructions?|prompts?|rules?|context)",
    # Role hijacking
    r"you\s+are\s+now\s+(a|an|the)\s+",
    r"act\s+as\s+(a|an|the)\s+(system|admin|root|developer)",
    r"switch\s+to\s+(system|admin|root|developer)\s+(mode|role)",
    r"enter\s+(system|admin|root|developer)\s+(mode|role)",
    # System prompt extraction
    r"(reveal|show|print|output|repeat|display)\s+(your|the|system)\s+(system\s+)?(prompt|instructions?|rules?)",
    r"what\s+(are|is)\s+your\s+(system\s+)?(prompt|instructions?|rules?)",
    # Delimiter escape attempts
    r"<\s*/?\s*(system|instruction|prompt|rule)",
    r"\[/?system\]",
    r"```\s*(system|instruction|prompt)",
    # Command execution attempts
    r"(execute|run|call|invoke|perform)\s+(system|shell|bash|cmd|command|os)\s",
    r"(subprocess|os\.system|exec|eval)\s*\(",
    # New task injection
    r"(new|additional|extra)\s+(task|instruction|objective|goal)\s*:",
    r"actually,?\s+(instead|rather|forget)",
]

_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]

# Max length for user inputs (CV text and job description)
MAX_CV_LENGTH = 50_000
MAX_JOB_DESC_LENGTH = 15_000


def sanitize_user_input(text: str, max_length: int, field_name: str) -> str:
    """Sanitize user-provided text before it enters an LLM prompt.

    Returns the cleaned text. Raises ValueError if the input is rejected.
    """
    if not text or not text.strip():
        raise ValueError(f"{field_name} is empty")

    # Truncate to max length
    if len(text) > max_length:
        logger.warning(
            "%s truncated from %d to %d chars", field_name, len(text), max_length
        )
        text = text[:max_length]

    # Check for injection patterns
    flags = detect_injection(text)
    if flags:
        logger.warning(
            "Prompt injection detected in %s: %s", field_name, ", ".join(flags)
        )
        text = neutralize(text, flags)

    return text


def detect_injection(text: str) -> list[str]:
    """Return list of matched injection pattern descriptions, empty if clean."""
    matches = []
    for pattern in _COMPILED_PATTERNS:
        if pattern.search(text):
            matches.append(pattern.pattern)
    return matches


def neutralize(text: str, flags: list[str]) -> str:
    """Neutralize detected injection attempts by escaping control-like phrases."""
    # Replace angle brackets that could be delimiter escapes
    text = text.replace("<", "&lt;").replace(">", "&gt;")

    # Break up instruction-override phrases by inserting zero-width spaces
    overrides = [
        "ignore", "disregard", "forget", "override",
        "system prompt", "new task", "new instruction",
    ]
    for word in overrides:
        # Case-insensitive replacement with zero-width space insertion
        pattern = re.compile(re.escape(word), re.IGNORECASE)
        text = pattern.sub(lambda m: m.group(0)[0] + "\u200b" + m.group(0)[1:], text)

    return text
