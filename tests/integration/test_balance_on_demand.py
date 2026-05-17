"""Integration tests for the on-demand credit balance refactor.

The middleware no longer caches the balance in the session. Instead it
reads Credit.balance directly from the DB on every authenticated request.

Scenarios covered:
1. Admin grants credits → target user's *very next* request shows the new
   balance without any re-login.
2. After a credit deduction, the next request shows the decremented balance.
"""

from __future__ import annotations

import pytest

from app.billing.use_cases.manage_credits import add_credits, deduct_credit, get_balance
from app.infrastructure.persistence.orm_models import Credit, User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_user(db_session, *, email: str, balance: int = 0) -> User:
    from app.identity.adapters.token_utils import hash_password

    async with db_session() as db:
        user = User(
            email=email,
            name="Test",
            password_hash=hash_password("testpassword123"),
            is_active=True,
        )
        db.add(user)
        await db.flush()
        db.add(Credit(user_id=user.id, balance=balance, total_purchased=balance, total_used=0))
        await db.commit()
        await db.refresh(user)
    return user


async def _login(client, *, email: str, password: str = "testpassword123") -> None:
    from tests.conftest import csrf_post

    response = await csrf_post(
        client,
        "/login",
        {"email": email, "password": password},
        follow_redirects=False,
    )
    assert response.status_code in (303, 307), (
        f"Login failed (status={response.status_code}, body={response.text[:200]!r})"
    )


def _parse_balance(html: str) -> int | None:
    """Extract the credit balance integer from rendered nav HTML.

    Looks for patterns like '>5 credits<' or '>1 credit<' in the nav.
    """
    import re

    # The nav renders something like: "5 credits" or "1 credit"
    match = re.search(r"(\d+)\s+credits?", html)
    if match:
        return int(match.group(1))
    return None


# ---------------------------------------------------------------------------
# 1. Admin grant is visible immediately — no re-login required
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAdminGrantVisibleImmediately:
    async def test_balance_updates_without_relogin(self, app_client, db_session):
        """After an admin credits a user, the next request shows the new balance."""
        user = await _make_user(db_session, email="grant_ondemand@example.com", balance=3)

        # Log the user in so the session is established.
        await _login(app_client, email=user.email)

        # Verify starting balance appears in the nav.
        response = await app_client.get("/partials/nav", follow_redirects=False)
        assert response.status_code == 200
        initial_balance = _parse_balance(response.text)
        assert initial_balance == 3, f"Expected 3, got {initial_balance!r}. HTML: {response.text[:400]}"

        # Admin grants 10 credits directly in the DB — simulates POST /admin/users/{id}/credits.
        async with db_session() as db:
            await add_credits(db, user.id, 10, as_grant=True)

        # Verify DB was updated.
        async with db_session() as db:
            assert await get_balance(db, user.id) == 13

        # The very next request must show 13 — no re-login, no cache busting needed.
        response = await app_client.get("/partials/nav", follow_redirects=False)
        assert response.status_code == 200
        new_balance = _parse_balance(response.text)
        assert new_balance == 13, (
            f"Expected 13 after admin grant, got {new_balance!r}. "
            f"Session cache would have shown 3. HTML: {response.text[:400]}"
        )


# ---------------------------------------------------------------------------
# 2. Credit deduction is visible immediately on the next request
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestDeductVisibleImmediately:
    async def test_deduct_reflected_on_next_request(self, app_client, db_session):
        """After a credit is spent, the next authenticated request shows the new balance."""
        user = await _make_user(db_session, email="deduct_ondemand@example.com", balance=5)

        await _login(app_client, email=user.email)

        # Verify starting balance.
        response = await app_client.get("/partials/nav", follow_redirects=False)
        assert response.status_code == 200
        assert _parse_balance(response.text) == 5

        # Deduct one credit out-of-band (simulates the /ws/analyze pipeline).
        async with db_session() as db:
            success = await deduct_credit(db, user.id)
        assert success is True

        # Next request must reflect the deduction immediately.
        response = await app_client.get("/partials/nav", follow_redirects=False)
        assert response.status_code == 200
        balance_after = _parse_balance(response.text)
        assert balance_after == 4, (
            f"Expected 4 after deduction, got {balance_after!r}. HTML: {response.text[:400]}"
        )
