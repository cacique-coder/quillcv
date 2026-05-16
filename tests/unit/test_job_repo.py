"""Unit tests for app/infrastructure/persistence/job_repo.py."""

import pytest

from app.infrastructure.persistence.job_repo import (
    create_job,
    delete_job,
    get_job,
    list_jobs,
    update_job,
)


pytestmark = pytest.mark.asyncio


async def _seed_user(db_session, email: str):
    from app.identity.adapters.token_utils import hash_password
    from app.infrastructure.persistence.orm_models import User

    async with db_session() as db:
        user = User(email=email, name="X", password_hash=hash_password("x" * 12), is_active=True)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


class TestCreate:
    async def test_create_minimum_fields(self, db_session):
        user = await _seed_user(db_session, "create@example.com")
        async with db_session() as db:
            job = await create_job(
                db,
                user_id=user.id,
                job_description="Build APIs.",
                region="AU",
            )
        assert job.status == "draft"
        assert job.region == "AU"
        assert job.user_id == user.id

    async def test_create_with_optional_fields(self, db_session):
        user = await _seed_user(db_session, "opts@example.com")
        async with db_session() as db:
            job = await create_job(
                db,
                user_id=user.id,
                job_description="JD",
                region="US",
                job_url="https://example.com/role",
                job_title="Engineer",
                company_name="Acme",
                offer_appeal="great team",
                template_id="modern",
            )
        assert job.job_title == "Engineer"
        assert job.template_id == "modern"


class TestGet:
    async def test_get_existing(self, db_session):
        user = await _seed_user(db_session, "get@example.com")
        async with db_session() as db:
            created = await create_job(db, user_id=user.id, job_description="JD", region="UK")
        async with db_session() as db:
            fetched = await get_job(db, created.id)
        assert fetched is not None
        assert fetched.id == created.id

    async def test_get_scopes_by_user_id(self, db_session):
        owner = await _seed_user(db_session, "owner@example.com")
        intruder = await _seed_user(db_session, "intruder@example.com")
        async with db_session() as db:
            created = await create_job(db, user_id=owner.id, job_description="JD", region="UK")
        async with db_session() as db:
            should_miss = await get_job(db, created.id, user_id=intruder.id)
        assert should_miss is None

    async def test_get_missing_returns_none(self, db_session):
        async with db_session() as db:
            assert await get_job(db, "does-not-exist") is None


class TestUpdate:
    async def test_update_changes_fields(self, db_session):
        user = await _seed_user(db_session, "upd@example.com")
        async with db_session() as db:
            created = await create_job(db, user_id=user.id, job_description="JD", region="UK")
        async with db_session() as db:
            updated = await update_job(db, created.id, status="completed")
        assert updated is not None
        assert updated.status == "completed"


class TestListAndDelete:
    async def test_list_returns_only_owners_jobs(self, db_session):
        owner = await _seed_user(db_session, "list-owner@example.com")
        other = await _seed_user(db_session, "list-other@example.com")
        async with db_session() as db:
            await create_job(db, user_id=owner.id, job_description="J1", region="AU")
            await create_job(db, user_id=owner.id, job_description="J2", region="AU")
            await create_job(db, user_id=other.id, job_description="JX", region="UK")
        async with db_session() as db:
            jobs = await list_jobs(db, user_id=owner.id)
        assert len(jobs) == 2

    async def test_delete_removes_job(self, db_session):
        user = await _seed_user(db_session, "del@example.com")
        async with db_session() as db:
            created = await create_job(db, user_id=user.id, job_description="JD", region="AU")
        async with db_session() as db:
            ok = await delete_job(db, created.id, user_id=user.id)
        assert ok is True
        async with db_session() as db:
            assert await get_job(db, created.id) is None
