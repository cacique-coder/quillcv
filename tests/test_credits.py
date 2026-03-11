"""Tests for credit service: balance, deduction, purchase."""

import pytest

from app.services.credit_service import get_balance, deduct_credit, add_credits, has_credits


@pytest.fixture(autouse=True)
async def setup_test_db(monkeypatch, tmp_path):
    """Use a temp database for credit tests."""
    db_path = tmp_path / "test.db"

    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    test_engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
    test_session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    monkeypatch.setattr("app.database.engine", test_engine)
    monkeypatch.setattr("app.database.async_session", test_session)

    from app.database import Base
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    return test_session


async def _create_test_user(session_factory):
    """Create a test user and return their ID."""
    from app.models import User, Credit
    async with session_factory() as db:
        user = User(email="credit@test.com", name="Credit Test")
        db.add(user)
        await db.flush()
        credit = Credit(user_id=user.id, balance=0, total_purchased=0, total_used=0)
        db.add(credit)
        await db.commit()
        return user.id


@pytest.mark.asyncio
class TestCreditService:
    async def test_initial_balance_is_zero(self, setup_test_db):
        session_factory = setup_test_db
        user_id = await _create_test_user(session_factory)
        async with session_factory() as db:
            balance = await get_balance(db, user_id)
        assert balance == 0

    async def test_add_credits(self, setup_test_db):
        session_factory = setup_test_db
        user_id = await _create_test_user(session_factory)
        async with session_factory() as db:
            await add_credits(db, user_id, 50)
            balance = await get_balance(db, user_id)
        assert balance == 50

    async def test_deduct_credit(self, setup_test_db):
        session_factory = setup_test_db
        user_id = await _create_test_user(session_factory)
        async with session_factory() as db:
            await add_credits(db, user_id, 5)
        async with session_factory() as db:
            success = await deduct_credit(db, user_id)
            balance = await get_balance(db, user_id)
        assert success is True
        assert balance == 4

    async def test_deduct_fails_when_empty(self, setup_test_db):
        session_factory = setup_test_db
        user_id = await _create_test_user(session_factory)
        async with session_factory() as db:
            success = await deduct_credit(db, user_id)
        assert success is False

    async def test_has_credits(self, setup_test_db):
        session_factory = setup_test_db
        user_id = await _create_test_user(session_factory)
        async with session_factory() as db:
            assert not await has_credits(db, user_id)
            await add_credits(db, user_id, 10)
            assert await has_credits(db, user_id)
