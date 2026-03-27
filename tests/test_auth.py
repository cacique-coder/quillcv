"""Tests for authentication: signup, login, logout, JWT tokens."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.identity.adapters.token_utils import create_access_token, decode_access_token, hash_password, verify_password
from app.main import app


class TestPasswordHashing:
    def test_hash_and_verify(self):
        hashed = hash_password("mypassword123")
        assert verify_password("mypassword123", hashed)

    def test_wrong_password_fails(self):
        hashed = hash_password("mypassword123")
        assert not verify_password("wrongpassword", hashed)

    def test_hash_is_unique(self):
        h1 = hash_password("same_password")
        h2 = hash_password("same_password")
        assert h1 != h2  # bcrypt salts should differ


class TestJWT:
    def test_create_and_decode(self):
        token = create_access_token("user123", "test@example.com")
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "user123"
        assert payload["email"] == "test@example.com"

    def test_invalid_token_returns_none(self):
        assert decode_access_token("invalid.token.here") is None

    def test_empty_token_returns_none(self):
        assert decode_access_token("") is None


@pytest.fixture(autouse=True)
async def mock_db_for_auth(monkeypatch, tmp_path):
    """Use a temp database for auth tests."""
    db_path = tmp_path / "test.db"

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    test_engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
    test_session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    monkeypatch.setattr("app.infrastructure.persistence.database.engine", test_engine)
    monkeypatch.setattr("app.infrastructure.persistence.database.async_session", test_session)
    # Patch everywhere async_session is imported from app.infrastructure.persistence.database
    monkeypatch.setattr("app.web.routes.auth.async_session", test_session)
    monkeypatch.setattr("app.web.routes.payments.async_session", test_session)
    monkeypatch.setattr("app.web.routes.landing.async_session", test_session)
    monkeypatch.setattr("app.identity.adapters.fastapi_deps.async_session", test_session)

    # Also patch attempt store and generation log
    monkeypatch.setattr("app.infrastructure.persistence.attempt_store.ATTEMPTS_DIR", tmp_path / "attempts")
    monkeypatch.setattr("app.cv_generation.adapters.generation_log.LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr("app.cv_generation.adapters.generation_log.LOG_FILE", tmp_path / "logs" / "gen.jsonl")

    from app.infrastructure.persistence.database import Base
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@pytest.mark.asyncio
class TestSignupEndpoint:
    async def test_signup_page_loads(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/signup")
        assert response.status_code == 200
        assert "Create your account" in response.text

    async def test_signup_creates_user(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/signup", data={
                "email": "new@example.com",
                "password": "securepassword123",
                "name": "Test User",
            }, follow_redirects=False)
        assert response.status_code == 303
        assert "/app" in response.headers["location"]

    async def test_signup_short_password_rejected(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/signup", data={
                "email": "new@example.com",
                "password": "short",
                "name": "Test",
            })
        assert response.status_code == 200
        assert "8 characters" in response.text

    async def test_signup_duplicate_email_rejected(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # First signup
            await client.post("/signup", data={
                "email": "dup@example.com",
                "password": "securepassword123",
                "name": "Test",
            })
            # Second signup with same email
            response = await client.post("/signup", data={
                "email": "dup@example.com",
                "password": "anotherpassword123",
                "name": "Test2",
            })
        assert response.status_code == 200
        assert "already exists" in response.text


@pytest.mark.asyncio
class TestLoginEndpoint:
    async def test_login_page_loads(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/login")
        assert response.status_code == 200
        assert "Welcome back" in response.text

    async def test_login_with_valid_credentials(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Create account first
            await client.post("/signup", data={
                "email": "login@example.com",
                "password": "securepassword123",
                "name": "Login User",
            })
            # Logout
            await client.get("/logout")
            # Login
            response = await client.post("/login", data={
                "email": "login@example.com",
                "password": "securepassword123",
            }, follow_redirects=False)
        assert response.status_code == 303
        assert "/app" in response.headers["location"]

    async def test_login_with_wrong_password(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/signup", data={
                "email": "wrong@example.com",
                "password": "securepassword123",
                "name": "Test",
            })
            await client.get("/logout")
            response = await client.post("/login", data={
                "email": "wrong@example.com",
                "password": "wrongpassword",
            })
        assert response.status_code == 200
        assert "Invalid" in response.text


@pytest.mark.asyncio
class TestLogout:
    async def test_logout_redirects_to_home(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/logout", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/"
