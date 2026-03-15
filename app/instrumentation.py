"""New Relic instrumentation helpers.

All functions are no-ops when the newrelic package is not installed or the
agent is not active, so the app runs without New Relic in development.
"""

import logging

logger = logging.getLogger(__name__)

try:
    import newrelic.agent as _nr
    _NR_AVAILABLE = True
except ImportError:
    _nr = None
    _NR_AVAILABLE = False


def add_custom_attributes(attrs: dict) -> None:
    """Add custom attributes to the current New Relic transaction."""
    if not _NR_AVAILABLE:
        return
    for key, value in attrs.items():
        _nr.add_custom_attribute(key, value)


def record_custom_event(event_type: str, params: dict) -> None:
    """Record a custom event in New Relic Insights."""
    if not _NR_AVAILABLE:
        return
    app = _nr.application()
    _nr.record_custom_event(event_type, params, application=app)


def record_llm_event(*, model: str, service: str, input_tokens: int,
                     output_tokens: int, cost_usd: float, duration_ms: int,
                     user_id: str | None = None, status: str = "success",
                     error_message: str | None = None,
                     cache_read_tokens: int = 0,
                     cache_creation_tokens: int = 0) -> None:
    """Record an LLM API call as a custom event + add attributes to current transaction."""
    params = {
        "model": model,
        "service": service,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": cache_read_tokens,
        "cache_creation_tokens": cache_creation_tokens,
        "cost_usd": cost_usd,
        "duration_ms": duration_ms,
        "status": status,
    }
    if user_id:
        params["user_id"] = user_id
    if error_message:
        params["error_message"] = error_message

    record_custom_event("LLMCall", params)
    add_custom_attributes({f"llm.{k}": v for k, v in params.items()})


class external_segment:
    """Context manager for wrapping external API calls as New Relic external segments.

    Usage:
        with external_segment("anthropic", "api.anthropic.com", "messages.create"):
            response = await client.messages.create(...)
    """
    def __init__(self, library: str, url: str, method: str = ""):
        self._segment = None
        if _NR_AVAILABLE:
            txn = _nr.current_transaction()
            if txn:
                self._segment = _nr.ExternalTrace(txn, library, url, method)

    def __enter__(self):
        if self._segment:
            self._segment.__enter__()
        return self

    def __exit__(self, *args):
        if self._segment:
            self._segment.__exit__(*args)
