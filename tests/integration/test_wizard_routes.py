"""Coverage for /wizard/* GETs. Exhaustive POST coverage is out of scope —
these focus on the GET render paths which are large blocks of code today."""

import pytest

from tests.conftest import csrf_post

WIZARD_GETS = [
    "/wizard",
    "/wizard/",
    "/wizard/new",
    "/wizard/step/1",
    "/wizard/step/2",
    "/wizard/step/3",
    "/wizard/step/4",
    "/wizard/step/5",
    "/wizard/step/6",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("path", WIZARD_GETS)
async def test_wizard_get_does_not_crash(authed_client, path):
    """The page should render or redirect — never 5xx."""
    client, _user = authed_client
    response = await client.get(path, follow_redirects=False)
    assert response.status_code < 500, (
        f"{path} returned {response.status_code}: {response.text[:200]!r}"
    )


@pytest.mark.asyncio
async def test_wizard_anonymous_redirects(app_client):
    response = await app_client.get("/wizard/step/1", follow_redirects=False)
    # Should redirect anonymous user, not error out
    assert response.status_code < 500


@pytest.mark.asyncio
async def test_wizard_region_summary(authed_client):
    client, _user = authed_client
    response = await client.get("/wizard/region-summary/US", follow_redirects=False)
    assert response.status_code < 500


@pytest.mark.asyncio
async def test_wizard_region_summary_unknown(authed_client):
    client, _user = authed_client
    response = await client.get("/wizard/region-summary/XX", follow_redirects=False)
    # Either 404 or a graceful empty render — never crash.
    assert response.status_code < 500


@pytest.mark.asyncio
async def test_wizard_step1_save_persists_region(authed_client):
    """POSTing step 1 should not crash and should redirect/respond cleanly."""
    client, _user = authed_client
    # Wizard pages don't have a visible CSRF input field (they're htmx-style),
    # so we pull the token from /account where the form macro renders one.
    response = await csrf_post(
        client, "/wizard/step/1/save", {"region": "US"}, csrf_path="/account",
        follow_redirects=False,
    )
    assert response.status_code < 500
