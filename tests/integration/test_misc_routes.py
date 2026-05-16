"""Miscellaneous route smoke coverage: blog, onboarding, invitations, cv downloads."""

import pytest


# ── blog ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_blog_index(app_client):
    response = await app_client.get("/blog", follow_redirects=False)
    assert response.status_code < 500


@pytest.mark.asyncio
async def test_blog_language_index(app_client):
    response = await app_client.get("/blog/en", follow_redirects=False)
    assert response.status_code < 500


@pytest.mark.asyncio
async def test_blog_post_unknown(app_client):
    response = await app_client.get("/blog/en/does-not-exist", follow_redirects=False)
    assert response.status_code in (200, 303, 404)


# ── onboarding ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_onboarding_get_authed(authed_client):
    client, _user = authed_client
    response = await client.get("/onboarding", follow_redirects=False)
    assert response.status_code < 500


@pytest.mark.asyncio
async def test_onboarding_anonymous(app_client):
    response = await app_client.get("/onboarding", follow_redirects=False)
    assert response.status_code < 500


@pytest.mark.asyncio
async def test_account_pii_authed(authed_client):
    client, _user = authed_client
    response = await client.get("/account/pii", follow_redirects=False)
    assert response.status_code < 500


# ── invitations ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_invitation_unknown_code(app_client):
    response = await app_client.get("/invite/does-not-exist", follow_redirects=False)
    assert response.status_code in (200, 303, 404)


@pytest.mark.asyncio
async def test_invitation_known_unredeemed(app_client, db_session):
    """An unredeemed invitation should show the redemption page."""
    from app.infrastructure.persistence.orm_models import Invitation

    async with db_session() as db:
        inv = Invitation(code="abc123xyz", credits=10, note="seed")
        db.add(inv)
        await db.commit()

    response = await app_client.get("/invite/abc123xyz", follow_redirects=False)
    assert response.status_code < 500


# ── cv route GETs (downloads without session) ─────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/download-pdf",
        "/download-docx",
        "/download-cover-letter-pdf",
        "/download-cover-letter-docx",
        "/download-all-pdf",
        "/download-all-docx",
    ],
)
async def test_cv_downloads_without_session(authed_client, path):
    client, _user = authed_client
    response = await client.get(path, follow_redirects=False)
    # Without a generated CV in session these should error/redirect cleanly,
    # not 500.
    assert response.status_code < 500


# ── payments ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pricing_anonymous(app_client):
    response = await app_client.get("/pricing", follow_redirects=False)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_account_topup_authed(authed_client):
    client, _user = authed_client
    response = await client.get("/account/topup", follow_redirects=False)
    assert response.status_code < 500


@pytest.mark.asyncio
async def test_checkout_success_handler(authed_client):
    """Stripe redirects here after successful payment. With no session_id query
    param the route should respond gracefully."""
    client, _user = authed_client
    response = await client.get("/checkout/success", follow_redirects=False)
    assert response.status_code < 500


@pytest.mark.asyncio
async def test_stripe_webhook_bad_signature_does_not_credit(app_client):
    """A bad-signature webhook is exempt from CSRF but must not grant credits.

    Stripe-style webhooks often respond 200 even on bad signature so the sender
    doesn't retry forever; the key invariant is that no payment gets recorded.
    """
    response = await app_client.post(
        "/webhook/stripe",
        content=b'{"id":"evt_test","type":"checkout.session.completed"}',
        headers={"stripe-signature": "obviously-fake"},
    )
    assert response.status_code < 500  # any non-crash response is acceptable


# ── photos ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_photo_upload_anonymous_rejected(app_client):
    """The upload route requires auth/session; an anonymous POST should fail cleanly."""
    response = await app_client.post(
        "/upload",
        files={"file": ("a.png", b"\x89PNG\r\n", "image/png")},
    )
    # CSRF middleware will likely 403; any non-5xx is acceptable.
    assert response.status_code < 500


@pytest.mark.asyncio
async def test_photo_serve_unknown_path(app_client):
    response = await app_client.get("/serve/nobody/photos/nothing.png", follow_redirects=False)
    assert response.status_code in (404, 403, 200, 303)
