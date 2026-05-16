"""Tests for landing page, pricing page, and public routes."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture(autouse=True)
async def mock_db_for_pages(monkeypatch, tmp_path):
    """Use a temp database for page tests."""
    db_path = tmp_path / "test.db"

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    test_engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
    test_session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    monkeypatch.setattr("app.infrastructure.persistence.database.engine", test_engine)
    monkeypatch.setattr("app.infrastructure.persistence.database.async_session", test_session)
    monkeypatch.setattr("app.web.routes.auth.async_session", test_session)
    monkeypatch.setattr("app.web.routes.payments.async_session", test_session)
    monkeypatch.setattr("app.web.routes.landing.async_session", test_session)
    monkeypatch.setattr("app.identity.adapters.fastapi_deps.async_session", test_session)

    monkeypatch.setattr("app.infrastructure.persistence.attempt_store.ATTEMPTS_DIR", tmp_path / "attempts")
    monkeypatch.setattr("app.cv_generation.adapters.generation_log.LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr("app.cv_generation.adapters.generation_log.LOG_FILE", tmp_path / "logs" / "gen.jsonl")

    from app.infrastructure.persistence.database import Base
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@pytest.mark.asyncio
class TestLandingPage:
    async def test_landing_loads_for_anonymous(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/")
        assert response.status_code == 200
        assert "QuillCV" in response.text
        assert "ATS" in response.text

    async def test_landing_has_cta(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/")
        assert response.status_code == 200
        assert "Get Started" in response.text or "Start Building" in response.text

    async def test_landing_shows_spots(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/")
        assert "spots" in response.text.lower() or "100" in response.text


@pytest.mark.asyncio
class TestPricingPage:
    async def test_pricing_loads(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/pricing")
        assert response.status_code == 200
        assert "$29" in response.text

    async def test_pricing_shows_features(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/pricing")
        assert "50 CV generations" in response.text
        assert "never expire" in response.text.lower()

    async def test_pricing_shows_spots_remaining(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/pricing")
        assert "100" in response.text  # spots remaining


@pytest.mark.asyncio
class TestAppPage:
    async def test_app_page_redirects_anonymous_to_landing(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/app")
        assert response.status_code == 200
        # Should show landing page content for anonymous users
        assert "ATS" in response.text
