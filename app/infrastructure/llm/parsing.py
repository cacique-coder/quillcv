"""Shared LLM JSON-response parsing utilities.

Consolidates the markdown-fence + brace-extraction logic that used to live
in `_extract_json_object` inside `anthropic_generator.py` and adds a
Pydantic validation pass on top. Adapter call sites should use
`parse_llm_json` or `generate_validated` instead of hand-rolling extraction
and `json.loads`.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, TypeVar

from pydantic import BaseModel, ValidationError

if TYPE_CHECKING:
    from app.infrastructure.llm.client import LLMClient

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# ```json ... ``` or ``` ... ``` fenced block, dotall so newlines inside are kept.
_FENCED_BLOCK_RE = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.DOTALL)


def extract_json(raw: str) -> str | None:
    """Strip markdown noise and return the first plausible JSON payload.

    Resolution order:
        1. First ```json ... ``` (or generic ```...```) fenced block.
        2. First balanced ``{ ... }`` object via brace counting.
        3. First balanced ``[ ... ]`` array via bracket counting.
        4. The stripped raw string itself if it already looks like JSON.

    Returns ``None`` when no plausible candidate is found.
    """
    if not raw:
        return None

    text = raw.strip()

    # 1. Fenced block
    match = _FENCED_BLOCK_RE.search(text)
    if match:
        candidate = match.group(1).strip()
        if candidate:
            return candidate

    # 2/3. Balanced first object or array
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        start = text.find(open_ch)
        if start == -1:
            continue
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == open_ch:
                depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]

    # 4. Naked JSON
    if text.startswith(("{", "[")):
        return text

    return None


def _format_validation_errors(exc: ValidationError, limit: int = 3) -> str:
    """Pretty short summary of the first ``limit`` validation errors."""
    parts: list[str] = []
    for err in exc.errors()[:limit]:
        loc = ".".join(str(p) for p in err.get("loc", ()))
        msg = err.get("msg", "invalid")
        parts.append(f"{loc or '<root>'}: {msg}")
    if len(exc.errors()) > limit:
        parts.append(f"…and {len(exc.errors()) - limit} more")
    return "; ".join(parts)


def parse_llm_json(raw: str, schema: type[T], *, context: str = "") -> T | None:
    """Parse ``raw`` into a Pydantic model, returning ``None`` on failure.

    On ValidationError or extraction failure, logs a WARNING with the first
    few errors and a head/tail snippet of the raw response so a human can
    diagnose without needing the full prompt log.
    """
    payload = extract_json(raw)
    if payload is None:
        logger.warning(
            "llm_parse: no JSON found context=%s head=%r tail=%r",
            context or "<unset>",
            (raw or "")[:120],
            (raw or "")[-120:],
        )
        return None

    try:
        return schema.model_validate_json(payload)
    except ValidationError as exc:
        logger.warning(
            "llm_parse: validation failed context=%s errors=%s head=%r tail=%r",
            context or "<unset>",
            _format_validation_errors(exc),
            payload[:120],
            payload[-120:],
        )
        return None
    except ValueError as exc:
        # Truncated / not-JSON-at-all payload — `model_validate_json` raises ValueError.
        logger.warning(
            "llm_parse: not valid JSON context=%s error=%s head=%r",
            context or "<unset>",
            exc,
            payload[:120],
        )
        return None


async def generate_validated(
    llm: "LLMClient",
    prompt: str,
    schema: type[T],
    *,
    retries: int = 1,
    context: str = "",
) -> T | None:
    """Call the LLM, parse + validate the response, and retry once on failure.

    On the retry, the validation error text is appended to the prompt so the
    model can self-correct. Returns ``None`` if every attempt fails, matching
    the graceful-degradation behaviour of the legacy adapters.
    """
    attempt_prompt = prompt
    last_error_summary: str | None = None
    for attempt in range(retries + 1):
        result = await llm.generate(attempt_prompt)
        parsed = parse_llm_json(result.text, schema, context=context)
        if parsed is not None:
            return parsed
        # Build retry prompt with the previous error context if we have one.
        last_error_summary = "previous response failed validation"
        if attempt >= retries:
            break
        attempt_prompt = (
            f"{prompt}\n\nYour previous response failed validation: "
            f"{last_error_summary}. Return ONLY valid JSON matching the schema described above."
        )
    return None
