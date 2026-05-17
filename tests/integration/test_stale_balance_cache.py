"""Integration tests for the stale-session balance-cache fix.

Scenarios covered:
1. Admin grant → target user's next request shows fresh balance (no re-login).
2. Deduct during /analyze → user's next request shows new balance.
3. Refund clawback (reverse_purchase_credits) → balance refreshes on next request.
4. Stripe webhook grant (grant_purchase_credits) → same staleness check passes.
5. Old-style session (no cached_balance_set_at) → safe fallback to cached value.
6. Credit row missing → safe fallback to cached value.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.billing.session_balance import set_cached_balance
from app.billing.use_cases.manage_credits import add_credits, deduct_credit, get_balance
from app.infrastructure.persistence.orm_models import Credit, Payment, User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_user(db_session, *, email: str, balance: int = 0) -> User:
    from app.identity.adapters.token_utils import hash_password

    async with db_session() as db:
        user = User(
            email=email,
            name="Test",
            password_hash=hash_password("pw"),
            is_active=True,
        )
        db.add(user)
        await db.flush()
        db.add(Credit(user_id=user.id, balance=balance, total_purchased=balance, total_used=0))
        await db.commit()
        await db.refresh(user)
    return user


async def _call_refresh(session: dict, user_id: str) -> int:
    """Invoke the middleware helper directly (no HTTP needed for unit-style tests)."""
    from app.infrastructure.middleware.main import _refresh_balance_if_stale

    return await _refresh_balance_if_stale(session, user_id)


# ---------------------------------------------------------------------------
# 1. Admin grant → balance refreshes on next request
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAdminGrantRefreshesCache:
    async def test_grant_makes_cache_stale_and_middleware_refreshes(self, db_session):
        user = await _make_user(db_session, email="grant@example.com", balance=5)

        # Simulate session written at login (balance = 5, timestamp = now).
        session: dict = {}
        set_cached_balance(session, 5)
        assert session["cached_balance"] == 5

        # Admin grants 10 more credits — DB balance becomes 15.
        async with db_session() as db:
            await add_credits(db, user.id, 10, as_grant=True)

        # Verify DB is updated.
        async with db_session() as db:
            assert await get_balance(db, user.id) == 15

        # Middleware detects stale cache and refetches.
        fresh = await _call_refresh(session, user.id)

        assert fresh == 15
        assert session["cached_balance"] == 15
        # Timestamp must have been updated.
        assert "cached_balance_set_at" in session

    async def test_no_refetch_when_balance_unchanged(self, db_session):
        """When last_change_at <= set_at, the cached value is returned as-is."""
        user = await _make_user(db_session, email="unchanged@example.com", balance=7)

        session: dict = {}
        set_cached_balance(session, 7)
        original_set_at = session["cached_balance_set_at"]

        # No balance change — refresh should return cached value.
        fresh = await _call_refresh(session, user.id)

        assert fresh == 7
        # set_at must not have changed (no write happened).
        assert session["cached_balance_set_at"] == original_set_at


# ---------------------------------------------------------------------------
# 2. Deduct → balance refreshes on next request
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestDeductRefreshesCache:
    async def test_deduct_bumps_last_change_at(self, db_session):
        user = await _make_user(db_session, email="deduct@example.com", balance=3)

        session: dict = {}
        set_cached_balance(session, 3)

        # Deduct one credit.
        async with db_session() as db:
            success = await deduct_credit(db, user.id)
        assert success is True

        # Middleware sees stale cache and refetches.
        fresh = await _call_refresh(session, user.id)

        assert fresh == 2
        assert session["cached_balance"] == 2


# ---------------------------------------------------------------------------
# 3. Refund clawback → balance refreshes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestRefundRefreshesCache:
    async def test_refund_clawback_triggers_refresh(self, db_session):
        # Create user with 15 credits + a completed payment.
        async with db_session() as db:
            user = User(email="refund_stale@example.com", name="R")
            db.add(user)
            await db.flush()
            db.add(Credit(user_id=user.id, balance=15, total_purchased=15, total_used=0))
            payment = Payment(
                user_id=user.id,
                stripe_session_id="cs_stale_refund",
                stripe_payment_intent="pi_stale_refund",
                amount_cents=2900,
                credits_granted=15,
                status="completed",
            )
            db.add(payment)
            await db.commit()
            await db.refresh(user)

        session: dict = {}
        set_cached_balance(session, 15)

        # Clawback via reverse_purchase_credits.
        from app.billing.use_cases.reverse_purchase_credits import reverse_purchase_credits

        async with db_session() as db:
            result = await reverse_purchase_credits(db, stripe_payment_intent="pi_stale_refund")
        assert result.reversed is True

        # Middleware detects stale cache.
        fresh = await _call_refresh(session, user.id)

        assert fresh == 0
        assert session["cached_balance"] == 0


# ---------------------------------------------------------------------------
# 4. Stripe grant_purchase_credits → balance refreshes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestStripePurchaseGrantRefreshesCache:
    async def test_purchase_grant_triggers_refresh(self, db_session):
        async with db_session() as db:
            user = User(email="stripe_stale@example.com", name="S")
            db.add(user)
            await db.flush()
            db.add(Credit(user_id=user.id, balance=0, total_purchased=0, total_used=0))
            payment = Payment(
                user_id=user.id,
                stripe_session_id="cs_stale_purchase",
                stripe_payment_intent=None,
                amount_cents=999,
                credits_granted=15,
                status="pending",
            )
            db.add(payment)
            await db.commit()
            await db.refresh(user)

        session: dict = {}
        set_cached_balance(session, 0)

        from app.billing.use_cases.grant_purchase_credits import grant_purchase_credits

        async with db_session() as db:
            result = await grant_purchase_credits(
                db,
                stripe_session_id="cs_stale_purchase",
                stripe_payment_intent="pi_stale_purchase",
            )
        assert result.granted is True

        fresh = await _call_refresh(session, user.id)

        assert fresh == 15
        assert session["cached_balance"] == 15


# ---------------------------------------------------------------------------
# 5. Old-style session (no cached_balance_set_at) → safe fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestOldSessionFallback:
    async def test_missing_set_at_returns_cached_value(self, db_session):
        """Sessions written before this migration have no cached_balance_set_at.
        The middleware must NOT force a refetch and must NOT error.
        """
        user = await _make_user(db_session, email="legacy@example.com", balance=8)

        # Old-style session: only cached_balance, no timestamp.
        session: dict = {"cached_balance": 8}

        result = await _call_refresh(session, user.id)

        # Falls back to the cached value safely.
        assert result == 8
        # No timestamp was injected (we don't modify the session on fallback).
        assert "cached_balance_set_at" not in session


# ---------------------------------------------------------------------------
# 6. No credit row → safe fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestMissingCreditRowFallback:
    async def test_no_credit_row_returns_cached_zero(self, db_session):
        """If the Credit row doesn't exist yet, return cached value without error."""
        async with db_session() as db:
            user = User(email="nocredit@example.com", name="N", is_active=True)
            db.add(user)
            await db.commit()
            await db.refresh(user)

        session: dict = {}
        set_cached_balance(session, 0)

        result = await _call_refresh(session, user.id)

        assert result == 0


# ---------------------------------------------------------------------------
# 7. set_cached_balance helper writes both keys atomically
# ---------------------------------------------------------------------------


class TestSetCachedBalance:
    def test_writes_balance_and_timestamp(self):
        session: dict = {}
        before = datetime.now(UTC)
        set_cached_balance(session, 42)
        after = datetime.now(UTC)

        assert session["cached_balance"] == 42
        ts = datetime.fromisoformat(session["cached_balance_set_at"])
        assert before <= ts <= after

    def test_overwrites_existing_values(self):
        session: dict = {"cached_balance": 99, "cached_balance_set_at": "2020-01-01T00:00:00+00:00"}
        set_cached_balance(session, 5)
        assert session["cached_balance"] == 5
        ts = datetime.fromisoformat(session["cached_balance_set_at"])
        assert ts > datetime(2020, 1, 1, tzinfo=UTC)
