"""Coverage for /builder/* GET routes."""

import pytest


@pytest.mark.asyncio
async def test_builder_index_authed(authed_client):
    client, _user = authed_client
    response = await client.get("/builder", follow_redirects=False)
    assert response.status_code < 500


@pytest.mark.asyncio
async def test_builder_index_anonymous(app_client):
    response = await app_client.get("/builder", follow_redirects=False)
    assert response.status_code < 500


@pytest.mark.asyncio
async def test_builder_edit_unknown_cv(authed_client):
    client, _user = authed_client
    response = await client.get("/builder/edit/no-such-id", follow_redirects=False)
    # Either redirects, 404s, or renders empty form — never 5xx.
    assert response.status_code < 500


@pytest.mark.asyncio
async def test_builder_download_pdf_without_session(authed_client):
    client, _user = authed_client
    response = await client.get("/builder/download-pdf", follow_redirects=False)
    assert response.status_code < 500


@pytest.mark.asyncio
async def test_builder_download_docx_without_session(authed_client):
    client, _user = authed_client
    response = await client.get("/builder/download-docx", follow_redirects=False)
    assert response.status_code < 500
