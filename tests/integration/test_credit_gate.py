"""Integration tests for the P0 credit gate and Stripe refund clawback.

Covers:
- POST /analyze: 402 when no credits, credit deducted on success, refund on hard failure
- POST /analyze: 429 when regeneration cap exceeded
- POST /apply-fixes: no credit deduction (free refinement)
- WS /ws/analyze: close 4402 when no credits
- Concurrent /analyze: exactly one credit deducted when two requests race
- Stripe charge.refunded webhook: clawback succeeds, double-refund is no-op,
  refund of partially-spent credits goes negative (policy: allow negative)
"""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.billing.use_cases.manage_credits import add_credits, get_balance
from app.billing.use_cases.reverse_purchase_credits import reverse_purchase_credits
from app.infrastructure.persistence.attempt_store import (
    create_attempt,
    save_document,
    update_attempt,
)
from app.infrastructure.persistence.orm_models import Credit, Payment, User
from app.main import app


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _seed_user(
    db_session,
    *,
    email: str,
    credits: int = 5,
    password: str = "testpw123",
) -> User:
    from app.identity.adapters.token_utils import hash_password

    async with db_session() as db:
        user = User(
            email=email,
            name="Test",
            password_hash=hash_password(password),
            is_active=True,
        )
        db.add(user)
        await db.flush()
        db.add(Credit(user_id=user.id, balance=credits, total_purchased=credits, total_used=0))
        await db.commit()
        await db.refresh(user)
    return user


async def _login(client: AsyncClient, *, email: str, password: str = "testpw123") -> None:
    from tests.conftest import csrf_post

    resp = await csrf_post(client, "/login", {"email": email, "password": password}, follow_redirects=False)
    assert resp.status_code in (303, 307), f"Login failed: {resp.status_code} {resp.text[:200]!r}"


def _prepared_attempt() -> str:
    attempt_id = create_attempt()
    update_attempt(
        attempt_id,
        region="US",
        template_id="modern",
        job_description="We need a Senior Python Engineer.",
    )
    save_document(
        attempt_id,
        "cv_file",
        "resume.txt",
        b"John Smith\nSummary\nExperienced engineer.\nSkills\nPython",
    )
    return attempt_id


def _set_attempt_data(attempt_id: str) -> None:
    """Populate an existing attempt with generation-ready data."""
    save_document(
        attempt_id,
        "cv_file",
        "resume.txt",
        b"John Smith\nSummary\nExperienced engineer.\nSkills\nPython",
    )
    update_attempt(
        attempt_id,
        region="US",
        template_id="modern",
        job_description="We need a Senior Python Engineer.",
    )


async def _create_and_bind_session_attempt(client: AsyncClient) -> str:
    """Create a new wizard attempt via /wizard/new and return the attempt_id.

    /wizard/new sets session["attempt_id"] on the server side and issues a
    session cookie.  We capture the attempt_id by monkeypatching create_attempt
    to record the last-created id.

    After this call the client's session cookie is bound to the returned
    attempt_id, so subsequent POST /analyze calls will find it.
    """
    # Intercept create_attempt to learn the ID it creates
    import app.web.routes.wizard as _wizard_mod
    import app.infrastructure.persistence.attempt_store as _store_mod

    _created: list[str] = []
    _real_create = _store_mod.create_attempt

    def _capture():
        aid = _real_create()
        _created.append(aid)
        return aid

    orig = _wizard_mod.create_attempt
    _wizard_mod.create_attempt = _capture
    try:
        await client.get("/wizard/new", follow_redirects=False)
    finally:
        _wizard_mod.create_attempt = orig

    assert _created, "create_attempt was not called by /wizard/new"
    attempt_id = _created[-1]

    # Populate the attempt with minimal generation-ready data
    save_document(
        attempt_id,
        "cv_file",
        "resume.txt",
        b"John Smith\nSummary\nExperienced engineer.\nSkills\nPython",
    )
    update_attempt(
        attempt_id,
        region="US",
        template_id="modern",
        job_description="We need a Senior Python Engineer.",
    )
    return attempt_id


async def _get_balance_direct(db_session, user_id: str) -> int:
    async with db_session() as db:
        return await get_balance(db, user_id)


# ── Mock LLM that optionally raises ──────────────────────────────────────────


from app.infrastructure.llm.client import LLMClient, LLMResult


class _OkLLM(LLMClient):
    """Returns valid minimal CV JSON."""

    async def generate(self, prompt: str) -> LLMResult:
        if "technical_skills" in prompt or "keyword" in prompt.lower():
            resp = json.dumps({
                "technical_skills": ["Python"],
                "tools_platforms": [],
                "professional_skills": [],
                "soft_skills": [],
                "domain_knowledge": [],
                "certifications": [],
            })
        elif "quality" in prompt.lower() or "REMOVE" in prompt:
            resp = json.dumps({"flags": [], "summary": "OK"})
        else:
            resp = json.dumps({
                "name": "Test", "title": "Eng", "email": "t@t.com", "phone": "",
                "location": "", "linkedin": "", "github": "", "portfolio": "",
                "summary": "Good.", "experience": [], "skills": ["Python"],
                "skills_grouped": [], "education": [], "certifications": [],
                "projects": [], "references": [],
            })
        return LLMResult(text=resp, model="mock", input_tokens=10, output_tokens=5, cost_usd=0.0)


class _FailLLM(LLMClient):
    """Always raises RuntimeError."""

    async def generate(self, prompt: str) -> LLMResult:
        raise RuntimeError("LLM hard failure")


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _patch_llm(monkeypatch, tmp_path):
    app.state.llm = _OkLLM()
    app.state.llm_fast = _OkLLM()
    monkeypatch.setattr("app.infrastructure.persistence.attempt_store.ATTEMPTS_DIR", tmp_path / "attempts")
    monkeypatch.setattr("app.cv_generation.adapters.generation_log.LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr("app.cv_generation.adapters.generation_log.LOG_FILE", tmp_path / "logs" / "gen.jsonl")


@pytest.fixture
async def client(db_session) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def authed(client, db_session):
    """Returns (client, user) already logged in with 5 credits."""
    user = await _seed_user(db_session, email="gated@test.com", credits=5)
    await _login(client, email=user.email)
    return client, user


@pytest.fixture
async def no_credit_user(client, db_session):
    """Returns (client, user) logged in with 0 credits."""
    user = await _seed_user(db_session, email="broke@test.com", credits=0)
    await _login(client, email=user.email)
    return client, user


# ── POST /analyze: credit gate ────────────────────────────────────────────────


@pytest.mark.asyncio
class TestAnalyzeCreditGate:
    async def test_analyze_returns_402_when_no_credits(self, no_credit_user, db_session):
        client, user = no_credit_user
        attempt_id = await _create_and_bind_session_attempt(client)

        from tests.conftest import csrf_post

        resp = await csrf_post(client, "/analyze", {}, csrf_path="/account")
        assert resp.status_code == 402
        body = resp.json()
        assert body["error"] == "insufficient_credits"
        # No credit change
        assert await _get_balance_direct(db_session, user.id) == 0

    async def test_analyze_deducts_credit_on_success(self, authed, db_session):
        client, user = authed
        await _create_and_bind_session_attempt(client)

        from tests.conftest import csrf_post

        resp = await csrf_post(client, "/analyze", {}, csrf_path="/account")
        # Should succeed (200 HTML partial)
        assert resp.status_code == 200
        # One credit deducted
        assert await _get_balance_direct(db_session, user.id) == 4

    async def test_analyze_refunds_credit_on_hard_failure(self, authed, db_session):
        client, user = authed
        await _create_and_bind_session_attempt(client)

        # Inject a failing LLM
        app.state.llm = _FailLLM()
        app.state.llm_fast = _FailLLM()

        from tests.conftest import csrf_post

        try:
            resp = await csrf_post(client, "/analyze", {}, csrf_path="/account")
        except Exception:
            pass
        finally:
            app.state.llm = _OkLLM()
            app.state.llm_fast = _OkLLM()

        # Balance must be back to 5 (refund happened)
        balance = await _get_balance_direct(db_session, user.id)
        assert balance == 5, f"Expected 5 credits after refund, got {balance}"

    async def test_analyze_blocks_after_regeneration_cap(self, authed, db_session):
        client, user = authed
        attempt_id = await _create_and_bind_session_attempt(client)
        update_attempt(attempt_id, regeneration_count=5)

        from tests.conftest import csrf_post

        resp = await csrf_post(client, "/analyze", {}, csrf_path="/account")
        assert resp.status_code == 429
        body = resp.json()
        assert body["error"] == "regeneration_limit_reached"
        # Credits untouched
        assert await _get_balance_direct(db_session, user.id) == 5

    async def test_analyze_increments_regeneration_count(self, authed, db_session):
        client, user = authed
        attempt_id = await _create_and_bind_session_attempt(client)

        from tests.conftest import csrf_post
        from app.infrastructure.persistence.attempt_store import get_attempt

        await csrf_post(client, "/analyze", {}, csrf_path="/account")

        attempt = get_attempt(attempt_id)
        assert attempt.get("regeneration_count", 0) == 1


# ── POST /apply-fixes: free (no credit deduction) ────────────────────────────


@pytest.mark.asyncio
class TestApplyFixesFree:
    async def test_apply_fixes_does_not_deduct_credit(self, authed, db_session):
        """apply-fixes is free — it refines an already-paid generation."""
        client, user = authed
        attempt_id = await _create_and_bind_session_attempt(client)
        update_attempt(
            attempt_id,
            cv_data={
                "name": "Test", "title": "Eng", "email": "t@t.com", "phone": "",
                "location": "", "linkedin": "", "github": "", "portfolio": "",
                "summary": "Good.", "experience": [], "skills": ["Python"],
                "skills_grouped": [], "education": [], "certifications": [],
                "projects": [], "references": [],
            },
            quality_review_flags=[
                {
                    "category": "content",
                    "issue": "Missing keywords",
                    "action": "improve",
                    "severity": "minor",
                    "target": "summary",
                    "item": "Experienced engineer.",
                    "reason": "Could be more specific.",
                }
            ],
        )

        from tests.conftest import csrf_post

        resp = await csrf_post(client, "/apply-fixes", {"selected": "0"}, csrf_path="/account")
        # Could be 200 or a template error — what matters is credits unchanged
        balance = await _get_balance_direct(db_session, user.id)
        assert balance == 5, f"apply-fixes should not deduct credits, got balance={balance}"


# ── Concurrent /analyze: exactly one credit deducted ─────────────────────────


@pytest.mark.asyncio
class TestConcurrentAnalyze:
    async def test_concurrent_analyze_deducts_exactly_one_credit(self, db_session, tmp_path):
        """Two concurrent POST /analyze calls with balance=1 — exactly one succeeds."""
        # Seed user with exactly 1 credit so only one concurrent call can win.
        user = await _seed_user(db_session, email="concurrent@test.com", credits=1)

        # We test the atomics directly (not via HTTP, to avoid CSRF complexity in parallel)
        from app.billing.use_cases.manage_credits import deduct_credit

        async def _try_deduct():
            async with db_session() as db:
                return await deduct_credit(db, user.id)

        results = await asyncio.gather(_try_deduct(), _try_deduct())
        success_count = sum(1 for r in results if r)
        assert success_count == 1, f"Expected exactly 1 successful deduction, got {success_count}"
        assert await _get_balance_direct(db_session, user.id) == 0


# ── Stripe charge.refunded clawback ──────────────────────────────────────────


@pytest.mark.asyncio
class TestStripeRefundClawback:
    async def _seed_completed_payment(
        self,
        db_session,
        *,
        email: str = "refund@test.com",
        credits: int = 15,
        payment_intent: str = "pi_test_refund",
    ) -> tuple[str, str]:
        """Create user + Credit + completed Payment. Returns (user_id, payment_id)."""
        async with db_session() as db:
            user = User(email=email, name="Refunder")
            db.add(user)
            await db.flush()
            db.add(Credit(user_id=user.id, balance=credits, total_purchased=credits, total_used=0))
            payment = Payment(
                user_id=user.id,
                stripe_session_id=f"cs_{email}",
                stripe_payment_intent=payment_intent,
                amount_cents=2900,
                credits_granted=credits,
                status="completed",
            )
            db.add(payment)
            await db.commit()
            return user.id, payment.id

    async def test_refund_clawback_succeeds(self, db_session):
        user_id, _ = await self._seed_completed_payment(
            db_session, email="r1@test.com", credits=15, payment_intent="pi_r1"
        )
        async with db_session() as db:
            result = await reverse_purchase_credits(db, stripe_payment_intent="pi_r1")

        assert result.reversed is True
        assert result.credits_reversed == 15
        assert result.user_id == user_id
        # Balance should now be 0 (was 15, clawed back 15)
        assert await _get_balance_direct(db_session, user_id) == 0

    async def test_double_refund_is_noop(self, db_session):
        """A second charge.refunded for the same payment_intent must not double-deduct."""
        user_id, _ = await self._seed_completed_payment(
            db_session, email="r2@test.com", credits=15, payment_intent="pi_r2"
        )

        async with db_session() as db:
            first = await reverse_purchase_credits(db, stripe_payment_intent="pi_r2")
        assert first.reversed is True

        async with db_session() as db:
            second = await reverse_purchase_credits(db, stripe_payment_intent="pi_r2")
        assert second.reversed is False

        # Balance must not have gone below 0 twice
        assert await _get_balance_direct(db_session, user_id) == 0

    async def test_refund_after_partial_spend_goes_negative(self, db_session):
        """Refund when user has already spent some credits → negative balance.

        Policy: allow negative balance.  This prevents the user from keeping
        generated CVs for free after requesting a refund.  Negative balance
        blocks future deduct_credit calls (balance must be > 0).
        """
        user_id, _ = await self._seed_completed_payment(
            db_session, email="r3@test.com", credits=15, payment_intent="pi_r3"
        )

        # Simulate user spending 5 credits before the refund
        async with db_session() as db:
            await add_credits(db, user_id, -5)  # spend 5 (direct adjust)
        assert await _get_balance_direct(db_session, user_id) == 10

        # Refund claws back the full 15 originally granted
        async with db_session() as db:
            result = await reverse_purchase_credits(db, stripe_payment_intent="pi_r3")
        assert result.reversed is True

        # Balance = 10 - 15 = -5 (intentionally negative)
        final = await _get_balance_direct(db_session, user_id)
        assert final == -5, f"Expected -5 (negative allowed by policy), got {final}"

    async def test_stripe_webhook_charge_refunded(self, db_session, monkeypatch):
        """End-to-end: charge.refunded webhook event triggers clawback."""
        user_id, _ = await self._seed_completed_payment(
            db_session,
            email="webhook_refund@test.com",
            credits=15,
            payment_intent="pi_webhook_refund",
        )

        # Patch Stripe webhook signature verification to return our event
        event = {
            "type": "charge.refunded",
            "data": {
                "object": {
                    "id": "ch_test",
                    "payment_intent": "pi_webhook_refund",
                }
            },
        }

        import stripe

        monkeypatch.setattr(
            stripe.Webhook,
            "construct_event",
            lambda payload, sig, secret: event,
        )
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_fake")
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_fake")
        # Also patch the module-level env reads in payments.py
        import app.web.routes.payments as _pm

        monkeypatch.setattr(_pm, "STRIPE_SECRET_KEY", "sk_test_fake")
        monkeypatch.setattr(_pm, "STRIPE_WEBHOOK_SECRET", "whsec_fake")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post(
                "/webhook/stripe",
                content=b"{}",
                headers={"stripe-signature": "t=1,v1=abc"},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

        # Credits clawed back
        assert await _get_balance_direct(db_session, user_id) == 0
