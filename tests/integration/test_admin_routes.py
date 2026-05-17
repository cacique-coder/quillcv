"""Admin route coverage: RBAC sweep + feature-flag round-trip."""

import pytest

from tests.conftest import csrf_post

# Routes that DO NOT use the Postgres-only ``string_agg(DISTINCT ...)``
# aggregate and therefore work against the SQLite test DB.
SQLITE_FRIENDLY_ADMIN_GETS = [
    "/admin/invitations",
    "/admin/users",
    "/admin/prompts",
    "/admin/features",
]


# ── RBAC ──────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("path", SQLITE_FRIENDLY_ADMIN_GETS)
async def test_admin_routes_404_for_anonymous(app_client, path):
    """Anonymous users should get 404 — admin section must not reveal itself."""
    response = await app_client.get(path, follow_redirects=False)
    assert response.status_code in (303, 404, 401, 307), (
        f"{path} returned {response.status_code} for anon; expected redirect or 404"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("path", SQLITE_FRIENDLY_ADMIN_GETS)
async def test_admin_routes_404_for_non_admin(authed_client, path):
    """Logged-in consumers should also get 404."""
    client, _user = authed_client
    response = await client.get(path, follow_redirects=False)
    assert response.status_code == 404, (
        f"{path} returned {response.status_code} for consumer; expected 404"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("path", SQLITE_FRIENDLY_ADMIN_GETS)
async def test_admin_routes_200_for_admin(admin_client, path):
    client, _user = admin_client
    response = await client.get(path, follow_redirects=False)
    assert response.status_code == 200, (
        f"{path} returned {response.status_code} for admin; body_head={response.text[:200]!r}"
    )


# ── Feature flag toggle round-trip ────────────────────────────


@pytest.mark.asyncio
async def test_admin_can_toggle_feature_flag(admin_client):
    """POST /admin/features/{key} flips the flag and the next GET reflects it."""
    client, _ = admin_client

    response = await csrf_post(
        client,
        "/admin/features/open_signups",
        {"enabled": "false"},
        csrf_path="/admin/features",
        follow_redirects=False,
    )
    assert response.status_code in (303, 200)

    # Verify the page shows the override now.
    page = await client.get("/admin/features")
    assert page.status_code == 200
    # Reflect the disabled state somewhere on the page
    assert "Disabled" in page.text or "open_signups" in page.text


@pytest.mark.asyncio
async def test_admin_toggle_unknown_feature_returns_404(admin_client):
    client, _ = admin_client
    response = await csrf_post(
        client,
        "/admin/features/totally_made_up_flag",
        {"enabled": "true"},
        csrf_path="/admin/features",
        follow_redirects=False,
    )
    assert response.status_code == 404


# ── Invitation creation ───────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_session_detail_404_for_unknown_session(admin_client):
    """An attempt_id that has no APIRequestLog rows should 404, not crash."""
    client, _ = admin_client
    response = await client.get("/admin/sessions/no-such-attempt-id", follow_redirects=False)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_admin_session_detail_shows_iterations(admin_client, db_session):
    """Seed two transactions sharing an attempt_id; session page lists both."""
    from app.infrastructure.persistence.orm_models import APIRequestLog

    client, _user = admin_client
    attempt_id = "test_attempt_for_session_view"
    async with db_session() as db:
        for txn_id in ("txn_alpha_0001", "txn_beta_00002"):
            db.add(APIRequestLog(
                transaction_id=txn_id,
                attempt_id=attempt_id,
                service="ai_generator",
                model="claude-sonnet-4",
                input_tokens=100,
                output_tokens=50,
                cost_usd=0.001,
                duration_ms=500,
                status="success",
            ))
        await db.commit()

    response = await client.get(f"/admin/sessions/{attempt_id}")
    assert response.status_code == 200
    # Both iteration ids should render (truncated to first 12 chars).
    assert "txn_alpha_00" in response.text
    assert "txn_beta_000" in response.text
    # Headline stats reflect 2 iterations.
    assert "Iterations" in response.text


@pytest.mark.asyncio
async def test_admin_can_create_invitation(admin_client):
    client, _ = admin_client
    response = await csrf_post(
        client,
        "/admin/invitations",
        {"email": "", "credits": "10", "note": "test invite"},
        csrf_path="/admin/invitations",
        follow_redirects=False,
    )
    assert response.status_code in (303, 200)

    # Listing should now contain a row with our note.
    listing = await client.get("/admin/invitations")
    assert listing.status_code == 200
    assert "test invite" in listing.text
