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


@pytest.mark.asyncio
async def test_my_cvs_other_user_cv_404(authed_client, db_session):
    """A signed-in user must not be able to read another user's CV.

    Ownership is enforced inside ``cv_repo.get_saved_cv`` (filters by
    ``user_id`` when supplied) and every consumer route in my_cvs.py +
    builder.py passes ``request.state.user.id``. The query returns None
    when the CV belongs to someone else, which the route renders as 404.
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "subpath",
    [
        "download",
        "download-docx",
        "cover-letter/download",
        "cover-letter/download-docx",
        "all/download-pdf",
        "all/download-docx",
    ],
)
async def test_my_cvs_other_user_download_routes_404(authed_client, db_session, subpath):
    """Every download route on /my-cvs/{cv_id}/* must refuse another user's CV."""
    from app.identity.adapters.token_utils import hash_password
    from app.infrastructure.persistence.orm_models import SavedCV, User

    client, _ = authed_client
    async with db_session() as db:
        other = User(
            email=f"other-{subpath.replace('/', '-')}@example.com",
            name="Other",
            password_hash=hash_password("x" * 12),
            is_active=True,
        )
        db.add(other)
        await db.flush()
        cv = SavedCV(
            user_id=other.id, attempt_id="att1", source="builder",
            label="Their CV", region="US", template_id="modern",
            markdown="", cv_data_json="{}",
        )
        db.add(cv)
        await db.commit()
        cv_id = cv.id

    response = await client.get(f"/my-cvs/{cv_id}/{subpath}", follow_redirects=False)
    # All ownership-gated downloads should return 404 (or redirect for unauth);
    # never 200 with the other user's content.
    assert response.status_code in (303, 404)


@pytest.mark.asyncio
async def test_builder_edit_other_user_cv_redirects(authed_client, db_session):
    """/builder/edit/{cv_id} must not load another user's CV."""
    from app.identity.adapters.token_utils import hash_password
    from app.infrastructure.persistence.orm_models import SavedCV, User

    client, _ = authed_client
    async with db_session() as db:
        other = User(
            email="other-builder@example.com", name="Other",
            password_hash=hash_password("x" * 12), is_active=True,
        )
        db.add(other)
        await db.flush()
        cv = SavedCV(
            user_id=other.id, attempt_id="att1", source="builder",
            label="Their CV", region="US", template_id="modern",
            markdown="", cv_data_json="{}",
        )
        db.add(cv)
        await db.commit()
        cv_id = cv.id

    response = await client.get(f"/builder/edit/{cv_id}", follow_redirects=False)
    # builder_edit redirects to /my-cvs when not found — confirms ownership filter.
    assert response.status_code == 303
    assert "/my-cvs" in response.headers.get("location", "")
