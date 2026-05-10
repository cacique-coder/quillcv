"""E2E regression test for the signup flow.

Regression: a stale ``data/sessions.db`` owned by root caused the SQLite
session middleware to raise ``OperationalError: attempt to write a readonly
database`` *after* the user, consents, and PII vault had been written, so
signup partially-succeeded but the user got a 500 instead of being logged
in. A pure unit test wouldn't have caught it because each component worked
in isolation — the failure was in the middleware response phase.

This test drives the real browser against a running uvicorn so the full
middleware stack (session + CSRF + auth context) executes end-to-end.
"""

from __future__ import annotations

import os
import secrets
from typing import TYPE_CHECKING

import psycopg2
import pytest

if TYPE_CHECKING:
    from playwright.sync_api import Page


def _sync_dsn() -> str:
    raw = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/quillcv_dev")
    # SQLAlchemy-style URLs may carry a +asyncpg driver suffix that psycopg2 doesn't understand.
    return raw.replace("postgresql+asyncpg://", "postgresql://")


def _unique_email() -> str:
    return f"e2e-signup-{secrets.token_hex(4)}@test.invalid"


def _delete_user(email: str) -> None:
    with psycopg2.connect(_sync_dsn()) as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        row = cur.fetchone()
        if not row:
            return
        uid = row[0]
        cur.execute("DELETE FROM consent_records WHERE user_id = %s", (uid,))
        cur.execute("DELETE FROM pii_vault WHERE user_id = %s", (uid,))
        cur.execute("DELETE FROM credits WHERE user_id = %s", (uid,))
        cur.execute("DELETE FROM users WHERE id = %s", (uid,))
        conn.commit()


def _user_exists(email: str) -> bool:
    with psycopg2.connect(_sync_dsn()) as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM users WHERE email = %s", (email,))
        return cur.fetchone() is not None


@pytest.fixture
def signup_email() -> str:
    email = _unique_email()
    yield email
    _delete_user(email)


def test_open_signup_completes_without_500(page: "Page", base_url: str, signup_email: str) -> None:
    """Filling the signup form lands on /onboarding — proves the session middleware
    can write its store and the full post-create flow succeeds."""
    failed_responses: list[tuple[int, str]] = []
    page.on(
        "response",
        lambda resp: failed_responses.append((resp.status, resp.url))
        if resp.status >= 500
        else None,
    )

    page.goto(f"{base_url}/signup")
    page.fill('input[name="name"]', "E2E Tester")
    page.fill('input[name="email"]', signup_email)
    page.fill('input[name="password"]', "testpass1234")
    page.fill('input[name="confirm_password"]', "testpass1234")
    page.check('input[name="age_confirmed"]')
    page.click('button[type="submit"]')

    page.wait_for_url(f"{base_url}/onboarding", timeout=10_000)

    assert not failed_responses, f"5xx responses observed during signup: {failed_responses}"
    assert _user_exists(signup_email), "user row missing after signup"


def test_signup_session_persists_after_redirect(page: "Page", base_url: str, signup_email: str) -> None:
    """After signup, navigating to a protected page must NOT bounce back to /login —
    a regression where the session save silently failed would manifest as the user
    being treated as logged-out on the very next request."""
    page.goto(f"{base_url}/signup")
    page.fill('input[name="name"]', "Session Persist")
    page.fill('input[name="email"]', signup_email)
    page.fill('input[name="password"]', "testpass1234")
    page.fill('input[name="confirm_password"]', "testpass1234")
    page.check('input[name="age_confirmed"]')
    page.click('button[type="submit"]')
    page.wait_for_url(f"{base_url}/onboarding", timeout=10_000)

    page.goto(f"{base_url}/app")
    assert "/login" not in page.url, f"session lost — bounced to {page.url}"
