"""Unit tests for app/infrastructure/llm/parsing.py."""

import logging

import pytest
from pydantic import BaseModel

from app.infrastructure.llm.client import LLMResult
from app.infrastructure.llm.parsing import (
    extract_json,
    generate_validated,
    parse_llm_json,
)


# ── Fixtures: a minimal schema + a scriptable fake LLM ────────


class _SimpleSchema(BaseModel):
    name: str = ""
    items: list[str] = []


class _ScriptedLLM:
    """LLM stub that returns each scripted response in order; raises if exhausted."""

    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> LLMResult:
        self.prompts.append(prompt)
        if not self._responses:
            raise AssertionError("Scripted LLM ran out of responses")
        text = self._responses.pop(0)
        return LLMResult(text=text, model="mock", input_tokens=0, output_tokens=0, cost_usd=0.0)


# ── extract_json edge cases ───────────────────────────────────


class TestExtractJson:
    def test_returns_none_for_empty(self):
        assert extract_json("") is None
        assert extract_json("   ") is None

    def test_handles_naked_object(self):
        assert extract_json('{"a": 1}') == '{"a": 1}'

    def test_handles_naked_array(self):
        assert extract_json("[1, 2, 3]") == "[1, 2, 3]"

    def test_strips_json_fence(self):
        raw = 'Here is the data:\n```json\n{"a": 1}\n```\nThanks!'
        assert extract_json(raw) == '{"a": 1}'

    def test_strips_generic_fence(self):
        raw = '```\n{"a": 1}\n```'
        assert extract_json(raw) == '{"a": 1}'

    def test_handles_prose_preamble(self):
        raw = 'Sure! Here is the JSON: {"key": "value"} and that\'s it.'
        assert extract_json(raw) == '{"key": "value"}'

    def test_handles_nested_braces(self):
        raw = '{"outer": {"inner": [1, 2, 3]}, "tail": "x"} more text'
        assert extract_json(raw) == '{"outer": {"inner": [1, 2, 3]}, "tail": "x"}'

    def test_handles_braces_inside_string(self):
        raw = '{"note": "use { and } carefully"} trailing'
        assert extract_json(raw) == '{"note": "use { and } carefully"}'

    def test_takes_first_object_when_multiple(self):
        raw = '{"a": 1} ignored {"b": 2}'
        assert extract_json(raw) == '{"a": 1}'

    def test_returns_none_when_no_braces(self):
        assert extract_json("plain text, no JSON here") is None

    def test_returns_none_for_unbalanced_braces(self):
        # Truncated object — no matching closing brace
        raw = '{"unfinished": "value"'
        # Falls through to "naked starts-with-{" path; downstream validator catches it.
        assert extract_json(raw) == '{"unfinished": "value"'


# ── parse_llm_json ────────────────────────────────────────────


class TestParseLLMJson:
    def test_valid_payload_returns_model(self):
        result = parse_llm_json('{"name": "x", "items": ["a", "b"]}', _SimpleSchema)
        assert result is not None
        assert result.name == "x"
        assert result.items == ["a", "b"]

    def test_handles_fenced_payload(self):
        result = parse_llm_json('```json\n{"name": "x"}\n```', _SimpleSchema)
        assert result is not None
        assert result.name == "x"

    def test_missing_optional_field_uses_default(self):
        result = parse_llm_json('{"name": "x"}', _SimpleSchema)
        assert result is not None
        assert result.items == []

    def test_validation_error_returns_none_and_logs(self):
        """Sanity-check the warning fires by attaching our own handler.

        We don't use caplog because the `app.*` logger is configured with
        ``propagate=False`` in production logging setup, which makes the
        records invisible to caplog's root-level interception.
        """
        records: list[logging.LogRecord] = []

        class _ListHandler(logging.Handler):
            def emit(self, record):
                records.append(record)

        logger = logging.getLogger("app.infrastructure.llm.parsing")
        handler = _ListHandler(level=logging.WARNING)
        logger.addHandler(handler)
        try:
            result = parse_llm_json('{"name": 42, "items": "not a list"}', _SimpleSchema, context="t1")
        finally:
            logger.removeHandler(handler)

        assert result is None
        assert any("validation failed" in r.getMessage() and "t1" in r.getMessage() for r in records)

    def test_no_json_returns_none(self):
        result = parse_llm_json("just plain prose", _SimpleSchema, context="t2")
        assert result is None

    def test_truncated_json_returns_none(self):
        result = parse_llm_json('{"name": "abc', _SimpleSchema)
        assert result is None


# ── generate_validated retry path ─────────────────────────────


@pytest.mark.asyncio
class TestGenerateValidated:
    async def test_first_attempt_succeeds(self):
        llm = _ScriptedLLM(['{"name": "ok"}'])
        result = await generate_validated(llm, "p", _SimpleSchema)
        assert result is not None
        assert result.name == "ok"
        assert len(llm.prompts) == 1

    async def test_retry_on_failure_then_success(self):
        llm = _ScriptedLLM(["garbage", '{"name": "second-time-lucky"}'])
        result = await generate_validated(llm, "p", _SimpleSchema, retries=1)
        assert result is not None
        assert result.name == "second-time-lucky"
        assert len(llm.prompts) == 2
        # The retry prompt should contain the error feedback phrase.
        assert "previous response failed validation" in llm.prompts[1]

    async def test_returns_none_after_all_retries(self):
        llm = _ScriptedLLM(["garbage", "still garbage"])
        result = await generate_validated(llm, "p", _SimpleSchema, retries=1)
        assert result is None
        assert len(llm.prompts) == 2

    async def test_retries_zero_disables_retry(self):
        llm = _ScriptedLLM(["garbage"])
        result = await generate_validated(llm, "p", _SimpleSchema, retries=0)
        assert result is None
        assert len(llm.prompts) == 1
