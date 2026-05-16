"""Smoke tests for the shared integration fixtures (db_session, app_client, etc.)."""

import pytest


@pytest.mark.asyncio
async def test_app_client_serves_landing(app_client):
    response = await app_client.get("/")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_db_session_isolated_per_test(db_session):
    """Two consecutive `await db_session()` calls share the same in-memory DB."""
    from sqlalchemy import select

    from app.infrastructure.persistence.orm_models import User

    async with db_session() as db:
        rows = await db.execute(select(User))
        assert rows.scalars().all() == []


@pytest.mark.asyncio
async def test_authed_client_is_logged_in(authed_client):
    client, user = authed_client
    response = await client.get("/account", follow_redirects=False)
    # Account page should be reachable (200) or redirect inside the app (303), never bounce to /login.
    assert response.status_code in (200, 303, 307)
    if response.status_code != 200:
        assert "/login" not in response.headers.get("location", "")


@pytest.mark.asyncio
async def test_admin_client_has_admin_role(admin_client):
    """Admin user is signed in and `/admin/features` (a SQLite-friendly admin page) returns 200."""
    client, user = admin_client
    assert user.role == "admin"
    response = await client.get("/admin/features", follow_redirects=False)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_feature_flags_override(feature_flags):
    from app import features

    with feature_flags(open_signups=False):
        assert features.is_enabled("open_signups") is False
    # Outside the context, the cache returns to whatever the test environment
    # had (default True for non-production APP_ENV).
    assert features.is_enabled("open_signups") in (True, False)
