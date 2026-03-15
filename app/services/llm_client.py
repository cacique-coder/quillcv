import asyncio
import contextvars
import logging
import os
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# Pricing per million tokens (USD) — update when model changes
MODEL_PRICING = {
    # Anthropic
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "claude-sonnet-4-20250514:thinking": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00},
    "claude-opus-4-6": {"input": 15.00, "output": 75.00},
    # OpenAI
    "gpt-5": {"input": 1.25, "output": 10.00},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-5-mini": {"input": 0.25, "output": 2.00},
    # Google Gemini — current as of March 2026
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
    "gemini-2.5-flash-lite": {"input": 0.10, "output": 0.40},
}

# ---------------------------------------------------------------------------
# Context vars for tracking — set by callers before generate()
# ---------------------------------------------------------------------------

_current_service = contextvars.ContextVar("llm_service", default="unknown")
_current_attempt_id = contextvars.ContextVar("llm_attempt_id", default=None)
_current_user_id = contextvars.ContextVar("llm_user_id", default=None)
_current_transaction_id = contextvars.ContextVar("llm_transaction_id", default=None)


def set_llm_context(
    *,
    service: str = "unknown",
    attempt_id: str | None = None,
    user_id: str | None = None,
    transaction_id: str | None = None,
    inherit: bool = False,
) -> None:
    """Set context for the next LLM call(s). Call before generate().

    If inherit=True, existing context values are preserved for fields not
    explicitly provided (useful for service-level tagging within a pipeline).
    """
    _current_service.set(service)
    if not inherit or attempt_id is not None:
        _current_attempt_id.set(attempt_id)
    if not inherit or user_id is not None:
        _current_user_id.set(user_id)
    if transaction_id is not None:
        _current_transaction_id.set(transaction_id)
    elif not inherit:
        # Fresh context — generate a new transaction_id
        _current_transaction_id.set(uuid.uuid4().hex)


@dataclass
class LLMResult:
    """Response from an LLM call, with optional usage/cost metadata."""
    text: str
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = MODEL_PRICING.get(model)
    if not pricing:
        return 0.0
    return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000


async def _log_to_db(
    transaction_id: str,
    attempt_id: str | None,
    user_id: str | None,
    service: str,
    model: str,
    prompt_chars: int,
    input_tokens: int,
    output_tokens: int,
    cache_read: int,
    cache_creation: int,
    cost_usd: float,
    duration_ms: int,
    status: str,
    error_message: str | None = None,
) -> None:
    """Fire-and-forget DB log."""
    try:
        from app.database import async_session
        from app.models import APIRequestLog
        async with async_session() as db:
            db.add(APIRequestLog(
                transaction_id=transaction_id,
                attempt_id=attempt_id,
                user_id=user_id,
                service=service,
                model=model,
                prompt_chars=prompt_chars,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read_tokens=cache_read,
                cache_creation_tokens=cache_creation,
                cost_usd=cost_usd,
                duration_ms=duration_ms,
                status=status,
                error_message=error_message,
            ))
            await db.commit()
    except Exception:
        logger.warning("Failed to log API request to DB", exc_info=True)

    from app.instrumentation import record_llm_event
    record_llm_event(
        model=model,
        service=service,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read,
        cache_creation_tokens=cache_creation,
        cost_usd=cost_usd,
        duration_ms=duration_ms,
        user_id=user_id,
        status=status,
        error_message=error_message,
    )


class LLMClient(ABC):
    @abstractmethod
    async def generate(self, prompt: str) -> LLMResult:
        """Send a prompt and return the response with usage metadata."""


class AnthropicAPIClient(LLMClient):
    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        import anthropic

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model

    async def generate(self, prompt: str) -> LLMResult:
        import time

        # Split on the first delimiter to extract system vs user content.
        split_marker = "===BEGIN CANDIDATE CV"
        if split_marker in prompt:
            idx = prompt.index(split_marker)
            system_text = prompt[:idx].strip()
            user_text = prompt[idx:].strip()
        else:
            system_text = ""
            user_text = prompt

        logger.info("LLM request model=%s prompt_chars=%d", self.model, len(prompt))
        t0 = time.monotonic()

        # Capture context before async call
        transaction_id = _current_transaction_id.get(None) or uuid.uuid4().hex
        attempt_id = _current_attempt_id.get(None)
        user_id = _current_user_id.get(None)
        service = _current_service.get("unknown")

        status = "success"
        error_message = None
        input_tokens = 0
        output_tokens = 0
        cache_read = 0
        cache_creation = 0
        cost = 0.0
        result_text = ""
        duration_s = 0.0

        try:
            from app.instrumentation import external_segment
            with external_segment("anthropic", "https://api.anthropic.com", "messages.create"):
                message = await self.client.messages.create(
                    model=self.model,
                    max_tokens=12000,
                    system=system_text,
                    messages=[{"role": "user", "content": user_text}],
                )

            duration_s = round(time.monotonic() - t0, 2)

            usage = message.usage
            input_tokens = usage.input_tokens
            output_tokens = usage.output_tokens
            cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
            cache_creation = getattr(usage, "cache_creation_input_tokens", 0) or 0
            cost = round(_estimate_cost(self.model, input_tokens, output_tokens), 6)

            logger.info(
                "LLM response model=%s input_tokens=%d output_tokens=%d "
                "cache_read=%d cache_creation=%d cost_usd=$%.4f duration=%.1fs",
                self.model, input_tokens, output_tokens,
                cache_read, cache_creation, cost, duration_s,
            )

            result_text = message.content[0].text

        except Exception as exc:
            duration_s = round(time.monotonic() - t0, 2)
            status = "error"
            error_message = str(exc)[:500]
            logger.error("LLM call failed model=%s error=%s", self.model, error_message)
            raise

        finally:
            asyncio.ensure_future(_log_to_db(
                transaction_id=transaction_id,
                attempt_id=attempt_id,
                user_id=user_id,
                service=service,
                model=self.model,
                prompt_chars=len(prompt),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read=cache_read,
                cache_creation=cache_creation,
                cost_usd=cost,
                duration_ms=round(duration_s * 1000),
                status=status,
                error_message=error_message,
            ))

        return LLMResult(
            text=result_text,
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            cache_read_tokens=cache_read,
            cache_creation_tokens=cache_creation,
        )


class ClaudeCodeClient(LLMClient):
    def __init__(self, model: str = "sonnet", timeout: int = 120):
        self.model = model
        self.timeout = timeout

    async def generate(self, prompt: str) -> LLMResult:
        import json
        import time

        # Remove CLAUDECODE env var so the CLI doesn't think it's nested
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

        model_tag = f"claude-code:{self.model}"
        logger.info("LLM request model=%s prompt_chars=%d", model_tag, len(prompt))
        t0 = time.monotonic()

        # Capture context before async call
        transaction_id = _current_transaction_id.get(None) or uuid.uuid4().hex
        attempt_id = _current_attempt_id.get(None)
        user_id = _current_user_id.get(None)
        service = _current_service.get("unknown")

        status = "success"
        error_message = None
        result_text = ""
        input_tokens = 0
        output_tokens = 0
        cache_read = 0
        cache_creation = 0
        cost = 0.0
        duration_s = 0.0
        actual_model = model_tag

        try:
            proc = await asyncio.create_subprocess_exec(
                "claude", "-p", prompt, "--model", self.model,
                "--output-format", "json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=self.timeout
                )
            except TimeoutError as err:
                proc.kill()
                await proc.communicate()
                status = "timeout"
                error_message = f"Claude CLI timed out after {self.timeout}s"
                raise RuntimeError(error_message) from err

            if proc.returncode != 0:
                status = "error"
                error_message = f"Claude CLI failed: {stderr.decode()[:200]}"
                raise RuntimeError(f"Claude CLI failed: {stderr.decode()}")

            duration_s = round(time.monotonic() - t0, 2)
            raw_output = stdout.decode().strip()

            # Parse JSON response from claude CLI
            try:
                data = json.loads(raw_output)
                result_text = data.get("result", "")
                cost = data.get("total_cost_usd", 0.0) or 0.0

                # Extract token usage
                usage = data.get("usage", {})
                input_tokens = usage.get("input_tokens", 0)
                output_tokens = usage.get("output_tokens", 0)
                cache_read = usage.get("cache_read_input_tokens", 0)
                cache_creation = usage.get("cache_creation_input_tokens", 0)

                # Get the actual model name from modelUsage
                model_usage = data.get("modelUsage", {})
                if model_usage:
                    actual_model = next(iter(model_usage))

            except (json.JSONDecodeError, KeyError):
                # Fallback: treat raw output as plain text
                result_text = raw_output
                logger.warning("Failed to parse claude CLI JSON output, using raw text")

            logger.info(
                "LLM response model=%s input_tokens=%d output_tokens=%d "
                "cache_read=%d cache_creation=%d cost_usd=$%.4f duration=%.1fs",
                actual_model, input_tokens, output_tokens,
                cache_read, cache_creation, cost, duration_s,
            )

        except Exception:
            duration_s = round(time.monotonic() - t0, 2)
            raise

        finally:
            asyncio.ensure_future(_log_to_db(
                transaction_id=transaction_id,
                attempt_id=attempt_id,
                user_id=user_id,
                service=service,
                model=actual_model,
                prompt_chars=len(prompt),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read=cache_read,
                cache_creation=cache_creation,
                cost_usd=cost,
                duration_ms=round(duration_s * 1000),
                status=status,
                error_message=error_message,
            ))

        return LLMResult(
            text=result_text,
            model=actual_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=round(cost, 6),
            cache_read_tokens=cache_read,
            cache_creation_tokens=cache_creation,
        )


class OpenAIClient(LLMClient):
    def __init__(self, model: str = "gpt-4o"):
        import openai

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model

    async def generate(self, prompt: str) -> LLMResult:
        import time

        split_marker = "===BEGIN CANDIDATE CV"
        if split_marker in prompt:
            idx = prompt.index(split_marker)
            system_text = prompt[:idx].strip()
            user_text = prompt[idx:].strip()
        else:
            system_text = ""
            user_text = prompt

        logger.info("LLM request model=%s prompt_chars=%d", self.model, len(prompt))
        t0 = time.monotonic()

        transaction_id = _current_transaction_id.get(None) or uuid.uuid4().hex
        attempt_id = _current_attempt_id.get(None)
        user_id = _current_user_id.get(None)
        service = _current_service.get("unknown")

        status = "success"
        error_message = None
        input_tokens = 0
        output_tokens = 0
        cost = 0.0
        result_text = ""
        duration_s = 0.0

        try:
            messages = []
            if system_text:
                messages.append({"role": "system", "content": system_text})
            messages.append({"role": "user", "content": user_text})

            from app.instrumentation import external_segment
            with external_segment("openai", "https://api.openai.com", "chat.completions.create"):
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=12000,
                )

            duration_s = round(time.monotonic() - t0, 2)

            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens
            cost = round(_estimate_cost(self.model, input_tokens, output_tokens), 6)

            logger.info(
                "LLM response model=%s input_tokens=%d output_tokens=%d "
                "cost_usd=$%.4f duration=%.1fs",
                self.model, input_tokens, output_tokens, cost, duration_s,
            )

            result_text = response.choices[0].message.content

        except Exception as exc:
            duration_s = round(time.monotonic() - t0, 2)
            status = "error"
            error_message = str(exc)[:500]
            logger.error("LLM call failed model=%s error=%s", self.model, error_message)
            raise

        finally:
            asyncio.ensure_future(_log_to_db(
                transaction_id=transaction_id,
                attempt_id=attempt_id,
                user_id=user_id,
                service=service,
                model=self.model,
                prompt_chars=len(prompt),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read=0,
                cache_creation=0,
                cost_usd=cost,
                duration_ms=round(duration_s * 1000),
                status=status,
                error_message=error_message,
            ))

        return LLMResult(
            text=result_text,
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
        )


class GeminiClient(LLMClient):
    def __init__(self, model: str = "gemini-2.5-pro"):
        import google.genai  # noqa: F401 — validate import at construction time

        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required")
        self.api_key = api_key
        self.model = model

    async def generate(self, prompt: str) -> LLMResult:
        import time

        import google.genai
        from google.genai.types import GenerateContentConfig

        split_marker = "===BEGIN CANDIDATE CV"
        if split_marker in prompt:
            idx = prompt.index(split_marker)
            system_text = prompt[:idx].strip()
            user_text = prompt[idx:].strip()
        else:
            system_text = ""
            user_text = prompt

        logger.info("LLM request model=%s prompt_chars=%d", self.model, len(prompt))
        t0 = time.monotonic()

        transaction_id = _current_transaction_id.get(None) or uuid.uuid4().hex
        attempt_id = _current_attempt_id.get(None)
        user_id = _current_user_id.get(None)
        service = _current_service.get("unknown")

        status = "success"
        error_message = None
        input_tokens = 0
        output_tokens = 0
        cost = 0.0
        result_text = ""
        duration_s = 0.0

        try:
            client = google.genai.Client(api_key=self.api_key)

            config_kwargs: dict = {"max_output_tokens": 12000}
            if system_text:
                config_kwargs["system_instruction"] = system_text

            from app.instrumentation import external_segment
            with external_segment("google-genai", "https://generativelanguage.googleapis.com", "generate_content"):
                response = await client.aio.models.generate_content(
                    model=self.model,
                    contents=user_text,
                    config=GenerateContentConfig(**config_kwargs),
                )

            duration_s = round(time.monotonic() - t0, 2)

            input_tokens = response.usage_metadata.prompt_token_count or 0
            output_tokens = response.usage_metadata.candidates_token_count or 0
            # Gemini 2.5 thinking models bill thinking tokens at the output rate.
            # thoughts_token_count is absent on non-thinking models, so default to 0.
            thinking_tokens = getattr(response.usage_metadata, "thoughts_token_count", 0) or 0
            cost = round(_estimate_cost(self.model, input_tokens, output_tokens + thinking_tokens), 6)

            logger.info(
                "LLM response model=%s input_tokens=%d output_tokens=%d "
                "thinking_tokens=%d cost_usd=$%.4f duration=%.1fs",
                self.model, input_tokens, output_tokens, thinking_tokens, cost, duration_s,
            )

            result_text = response.text
            if not result_text:
                logger.warning("Gemini returned empty result_text model=%s finish_reason=%s",
                               self.model,
                               response.candidates[0].finish_reason if response.candidates else "no_candidates")

        except Exception as exc:
            duration_s = round(time.monotonic() - t0, 2)
            status = "error"
            error_message = str(exc)[:500]
            logger.error("LLM call failed model=%s error=%s", self.model, error_message)
            raise

        finally:
            asyncio.ensure_future(_log_to_db(
                transaction_id=transaction_id,
                attempt_id=attempt_id,
                user_id=user_id,
                service=service,
                model=self.model,
                prompt_chars=len(prompt),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read=0,
                cache_creation=0,
                cost_usd=cost,
                duration_ms=round(duration_s * 1000),
                status=status,
                error_message=error_message,
            ))

        return LLMResult(
            text=result_text,
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
        )


# ---------------------------------------------------------------------------
# Provider/model mapping and factory
# ---------------------------------------------------------------------------

# Maps provider name -> model tier -> model string
PROVIDER_MODELS: dict[str, dict[str, str]] = {
    "anthropic": {"heavy": "claude-sonnet-4-20250514", "light": "claude-haiku-4-5-20251001"},
    "openai":    {"heavy": "gpt-5",                    "light": "gpt-4o-mini"},
    "gemini":    {"heavy": "gemini-2.5-pro",            "light": "gemini-2.5-flash-lite"},
}


def create_llm_client(provider: str, tier: str) -> LLMClient:
    """Create an LLM client for the given provider and tier.

    Args:
        provider: "anthropic", "openai", or "gemini"
        tier:     "heavy" (CV generation) or "light" (keywords, review, refine)

    Returns:
        A concrete LLMClient implementation backed by the chosen provider/model.
    """
    models = PROVIDER_MODELS.get(provider)
    if not models:
        raise ValueError(
            f"Unknown provider: {provider!r}. Valid options: {list(PROVIDER_MODELS.keys())}"
        )

    model = models.get(tier)
    if not model:
        raise ValueError(f"Unknown tier: {tier!r}. Valid options: heavy, light")

    if provider == "anthropic":
        return AnthropicAPIClient(model=model)
    elif provider == "openai":
        return OpenAIClient(model=model)
    elif provider == "gemini":
        return GeminiClient(model=model)

    raise ValueError(f"No client implementation for provider: {provider!r}")
