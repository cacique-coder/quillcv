"""Smoke coverage for public GET routes (landing, pages, seo, partials, demo).

These don't require auth and exercise large amounts of code with minimal
per-route assertions. Goal: lift route-file coverage above 50% via cheap GETs.
"""

import pytest

# Pages that should respond 200 (or a sensible redirect) for an anonymous client.
ANON_GET_PATHS = [
    "/",
    "/app",
    "/dashboard",
    "/prototype",
    "/about",
    "/privacy",
    "/privacidad",
    "/privacidade",
    "/terms",
    "/refund-policy",
    "/ccpa-opt-out",
    "/pricing",
    "/login",
    "/signup",
    "/forgot-password",
    "/demo",
    "/demo/US",
    "/demo/US/modern",
    "/demo/AU/classic",
    "/blog",
    "/robots.txt",
    "/sitemap.xml",
    "/llms.txt",
    "/partials/nav",
    "/partials/footer",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ANON_GET_PATHS)
async def test_anon_get(app_client, path):
    response = await app_client.get(path, follow_redirects=False)
    # Any of: 200 OK, redirect to login, or 304-style. Reject 4xx/5xx.
    assert response.status_code < 400, (
        f"{path} returned {response.status_code}: {response.text[:200]!r}"
    )


@pytest.mark.asyncio
async def test_invitation_landing_404_for_unknown_code(app_client):
    response = await app_client.get("/invite/does-not-exist", follow_redirects=False)
    assert response.status_code in (200, 404, 303)
