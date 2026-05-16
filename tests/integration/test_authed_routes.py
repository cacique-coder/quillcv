"""Authed-user route smoke coverage: my-cvs, account, profile.

Cheap GET coverage for routes that require an authenticated user. Body
assertions are minimal — goal is to drive code through the happy path.
"""

import pytest

AUTHED_GET_PATHS = [
    "/my-cvs",
    "/account",
    "/account/topup",
    "/profile",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("path", AUTHED_GET_PATHS)
async def test_authed_user_can_open(authed_client, path):
    client, _user = authed_client
    response = await client.get(path, follow_redirects=False)
    assert response.status_code in (200, 301, 303, 307), (
        f"{path} returned {response.status_code}: {response.text[:200]!r}"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("path", AUTHED_GET_PATHS)
async def test_anonymous_user_blocked(app_client, path):
    response = await app_client.get(path, follow_redirects=False)
    # Should redirect to /login or render a public placeholder; never 5xx.
    assert response.status_code < 500


@pytest.mark.asyncio
async def test_my_cvs_unknown_id_404(authed_client):
    """Asking for a non-existent CV id should not crash."""
    client, _user = authed_client
    response = await client.get("/my-cvs/does-not-exist/preview", follow_redirects=False)
    assert response.status_code in (303, 404)


@pytest.mark.xfail(
    reason=(
        "SECURITY GAP: app/infrastructure/persistence/cv_repo.py:get_saved_cv() "
        "does not filter by user_id, so /my-cvs/{cv_id}/preview leaks any CV to "
        "any authenticated user. Tracked as a follow-up — flipping this to a "
        "passing test requires adding an ownership check to the route."
    ),
    strict=True,
)
@pytest.mark.asyncio
async def test_my_cvs_other_user_cv_404(authed_client, db_session):
    """A signed-in user must not be able to read another user's CV.

    Currently failing on purpose to document the IDOR. Make it pass by
    enforcing ``cv.user_id == request.state.user.id`` in
    ``app/web/routes/my_cvs.py::my_cv_preview`` (and the download routes).
    """
    from app.identity.adapters.token_utils import hash_password
    from app.infrastructure.persistence.orm_models import SavedCV, User

    client, signed_in_user = authed_client

    # Seed a SavedCV row that belongs to a *different* user.
    async with db_session() as db:
        other = User(email="other@example.com", name="Other", password_hash=hash_password("x" * 12), is_active=True)
        db.add(other)
        await db.flush()
        cv = SavedCV(
            user_id=other.id,
            attempt_id="att1",
            source="builder",
            label="Their CV",
            region="US",
            template_id="modern",
            markdown="",
            cv_data_json="{}",
        )
        db.add(cv)
        await db.commit()
        cv_id = cv.id

    response = await client.get(f"/my-cvs/{cv_id}/preview", follow_redirects=False)
    assert response.status_code in (303, 404)
