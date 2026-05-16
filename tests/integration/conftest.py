"""Integration-test fixtures: ASGI client, authed/admin clients, edge-service mocks."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient


# ── ASGI clients ─────────────────────────────────────────────


@pytest.fixture
async def app_client(db_session) -> AsyncIterator[AsyncClient]:
    """An httpx.AsyncClient wired to the FastAPI app on an in-memory DB.

    Depends on `db_session` (defined in tests/conftest.py) so every request
    sees the SQLite test database instead of production Postgres.
    """
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def _seed_user(
    db_session,
    *,
    email: str,
    name: str = "Test User",
    password: str = "testpassword123",
    role: str = "consumer",
    credits: int = 5,
) -> Any:
    """Insert a user + a credit row directly into the in-memory DB and return the row."""
    from app.identity.adapters.token_utils import hash_password
    from app.infrastructure.persistence.orm_models import Credit, User

    async with db_session() as db:
        user = User(
            email=email.lower(),
            name=name,
            password_hash=hash_password(password),
            role=role,
            is_active=True,
        )
        db.add(user)
        await db.flush()
        db.add(Credit(user_id=user.id, balance=credits, total_purchased=credits, total_used=0))
        await db.commit()
        await db.refresh(user)
    return user


async def _login_client(client: AsyncClient, *, email: str, password: str) -> None:
    """Drive /login through the live form so the session cookie + JWT match."""
    from tests.conftest import csrf_post

    response = await csrf_post(
        client,
        "/login",
        {"email": email, "password": password},
        follow_redirects=False,
    )
    assert response.status_code in (303, 307), (
        f"Login did not redirect (status={response.status_code}, body={response.text[:200]!r})"
    )


@pytest.fixture
async def authed_client(app_client, db_session) -> AsyncIterator[tuple[AsyncClient, Any]]:
    """`app_client` already logged in as a freshly-seeded consumer user."""
    user = await _seed_user(db_session, email="authed@example.com")
    await _login_client(app_client, email=user.email, password="testpassword123")
    yield app_client, user


@pytest.fixture
async def admin_client(app_client, db_session) -> AsyncIterator[tuple[AsyncClient, Any]]:
    """`app_client` already logged in as an admin user."""
    user = await _seed_user(db_session, email="admin@example.com", role="admin")
    await _login_client(app_client, email=user.email, password="testpassword123")
    yield app_client, user


# ── External-service mocks ───────────────────────────────────


class _StripeStub:
    """Minimal Stripe stub. Each call appends to `calls`; replace returned IDs as needed."""

    def __init__(self):
        self.calls: list[tuple[str, dict]] = []
        self.checkout_session = {"id": "cs_test_123", "url": "https://stripe.test/checkout/cs_test_123"}
        self.webhook_payload: dict | None = None

    def create_checkout_session(self, **kwargs):
        self.calls.append(("checkout.session.create", kwargs))
        return self.checkout_session

    def construct_event(self, payload: bytes, sig_header: str, secret: str) -> dict:
        self.calls.append(("webhook.construct_event", {"sig": sig_header}))
        if self.webhook_payload is None:
            raise ValueError("No webhook_payload set on stripe_mock")
        return self.webhook_payload


@pytest.fixture
def stripe_mock(monkeypatch) -> _StripeStub:
    """Monkeypatch the stripe SDK entry points the app calls."""
    import stripe

    stub = _StripeStub()
    monkeypatch.setattr(stripe.checkout.Session, "create", lambda **kw: stub.create_checkout_session(**kw))
    monkeypatch.setattr(stripe.Webhook, "construct_event", stub.construct_event)
    return stub


class _R2Stub:
    """In-memory replacement for the boto3 S3 client used by the R2 adapter."""

    def __init__(self):
        self.objects: dict[tuple[str, str], bytes] = {}
        self.calls: list[tuple[str, dict]] = []

    def put_object(self, *, Bucket, Key, Body, **kwargs):
        self.calls.append(("put_object", {"Bucket": Bucket, "Key": Key, **kwargs}))
        if isinstance(Body, (bytes, bytearray)):
            self.objects[(Bucket, Key)] = bytes(Body)
        else:
            self.objects[(Bucket, Key)] = Body.read()
        return {"ETag": '"stub"'}

    def get_object(self, *, Bucket, Key):
        self.calls.append(("get_object", {"Bucket": Bucket, "Key": Key}))
        data = self.objects[(Bucket, Key)]
        return {"Body": _BytesBody(data), "ContentLength": len(data)}

    def delete_object(self, *, Bucket, Key):
        self.calls.append(("delete_object", {"Bucket": Bucket, "Key": Key}))
        self.objects.pop((Bucket, Key), None)
        return {}


class _BytesBody:
    def __init__(self, data: bytes):
        self._data = data

    def read(self) -> bytes:
        return self._data


@pytest.fixture
def r2_mock(monkeypatch) -> _R2Stub:
    """Replace boto3 client usage inside app.infrastructure.storage.r2 with an in-memory stub."""
    stub = _R2Stub()

    def _fake_client(*args, **kwargs):
        return stub

    # The R2 adapter typically calls boto3.client("s3", ...) at module load or per-call.
    import boto3
    monkeypatch.setattr(boto3, "client", _fake_client)
    return stub


@pytest.fixture
def smtp_mock(monkeypatch) -> list[dict]:
    """Capture every outbound email into a list of dicts instead of hitting SMTP."""
    captured: list[dict] = []

    async def _send_invitation_email(**kwargs):
        captured.append({"kind": "invitation", **kwargs})

    async def _send_welcome_email(**kwargs):
        captured.append({"kind": "welcome", **kwargs})

    async def _send_password_reset_email(**kwargs):
        captured.append({"kind": "password_reset", **kwargs})

    import app.infrastructure.email.smtp as smtp_mod

    if hasattr(smtp_mod, "send_invitation_email"):
        monkeypatch.setattr(smtp_mod, "send_invitation_email", _send_invitation_email)
    if hasattr(smtp_mod, "send_welcome_email"):
        monkeypatch.setattr(smtp_mod, "send_welcome_email", _send_welcome_email)
    if hasattr(smtp_mod, "send_password_reset_email"):
        monkeypatch.setattr(smtp_mod, "send_password_reset_email", _send_password_reset_email)

    return captured
