"""E2E test fixtures.

These tests drive a real browser against a running uvicorn instance.
The server is expected at ``E2E_BASE_URL`` (default http://localhost:8000) — start it
with ``mise run dev`` before invoking ``pytest tests/e2e``.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import httpx
import pytest


E2E_BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def base_url() -> str:
    return E2E_BASE_URL


@pytest.fixture(scope="session", autouse=True)
def _require_running_server(base_url: str) -> Iterator[None]:
    try:
        httpx.get(f"{base_url}/", timeout=2.0)
    except Exception as exc:
        pytest.skip(f"E2E server at {base_url} unreachable ({exc!r}). Start it with `mise run dev`.")
    yield


@pytest.fixture
def browser_context_args(browser_context_args: dict) -> dict:
    """Don't reuse storage between tests — each signup needs a clean session cookie."""
    return {**browser_context_args, "storage_state": None}
