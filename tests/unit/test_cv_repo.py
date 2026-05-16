"""Unit tests for app/infrastructure/persistence/cv_repo.py."""

import os

import pytest

# cv_repo uses Fernet-backed encryption at rest; tests need a key in env.
if not os.environ.get("ENCRYPTION_KEY"):
    from cryptography.fernet import Fernet
    os.environ["ENCRYPTION_KEY"] = Fernet.generate_key().decode()

from app.infrastructure.persistence.cv_repo import (
    decrypt_saved_cv,
    get_saved_cv,
    html_to_markdown,
    list_saved_cvs,
    save_cv,
    update_cv,
)


pytestmark = pytest.mark.asyncio


_CV_DATA = {
    "name": "Alice",
    "email": "alice@example.com",
    "summary": "A summary",
    "experience": [{"title": "Eng", "company": "Acme", "date": "2020", "bullets": ["b"]}],
    "skills": ["Python"],
}


async def _seed_user(db_session, email: str):
    from app.identity.adapters.token_utils import hash_password
    from app.infrastructure.persistence.orm_models import User

    async with db_session() as db:
        user = User(email=email, name="X", password_hash=hash_password("x" * 12), is_active=True)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


class TestHtmlToMarkdown:
    def test_basic_conversion(self):
        md = html_to_markdown("<h1>Hello</h1><p>World</p>")
        assert "Hello" in md
        assert "World" in md


class TestSaveCV:
    async def test_save_creates_row(self, db_session):
        user = await _seed_user(db_session, "save@example.com")
        async with db_session() as db:
            saved = await save_cv(
                db,
                attempt_id="att1",
                source="builder",
                region="AU",
                template_id="modern",
                rendered_html="<h1>CV</h1>",
                cv_data=_CV_DATA,
                user_id=user.id,
                label="My CV",
            )
        assert saved.id
        assert saved.region == "AU"
        assert saved.template_id == "modern"
        assert saved.label == "My CV"
        # Encrypted at rest — raw JSON should not equal the original
        assert "alice@example.com" not in saved.cv_data_json

    async def test_save_with_references(self, db_session):
        user = await _seed_user(db_session, "refs@example.com")
        async with db_session() as db:
            saved = await save_cv(
                db,
                attempt_id="att1",
                source="ai",
                region="AU",
                template_id="classic",
                rendered_html="<p>X</p>",
                cv_data=_CV_DATA,
                user_id=user.id,
                references=[{"name": "Bob", "email": "bob@example.com"}],
            )
        assert saved.references_json is not None
        assert "bob@example.com" not in saved.references_json  # encrypted


class TestGetAndDecrypt:
    async def test_get_and_decrypt(self, db_session):
        user = await _seed_user(db_session, "get@example.com")
        async with db_session() as db:
            saved = await save_cv(
                db,
                attempt_id="att1",
                source="builder",
                region="AU",
                template_id="modern",
                rendered_html="<h1>X</h1>",
                cv_data=_CV_DATA,
                user_id=user.id,
            )
            cv_id = saved.id

        async with db_session() as db:
            fetched = await get_saved_cv(db, cv_id)
        assert fetched is not None
        # After decrypt, cv_data_json contains the redacted/tokenised payload
        # but it's a JSON-parsable string.
        import json
        parsed = json.loads(fetched.cv_data_json)
        assert "experience" in parsed

    async def test_get_missing_returns_none(self, db_session):
        async with db_session() as db:
            assert await get_saved_cv(db, "nope") is None


class TestListSavedCVs:
    async def test_list_filtered_by_user(self, db_session):
        owner = await _seed_user(db_session, "list-owner@example.com")
        other = await _seed_user(db_session, "list-other@example.com")
        async with db_session() as db:
            for label in ("A", "B"):
                await save_cv(
                    db, attempt_id="x", source="builder", region="AU", template_id="modern",
                    rendered_html="<p/>", cv_data=_CV_DATA, user_id=owner.id, label=label,
                )
            await save_cv(
                db, attempt_id="y", source="builder", region="AU", template_id="modern",
                rendered_html="<p/>", cv_data=_CV_DATA, user_id=other.id, label="OTHER",
            )
        async with db_session() as db:
            owner_cvs = await list_saved_cvs(db, user_id=owner.id)
        assert len(owner_cvs) == 2


class TestUpdateCV:
    async def test_update_changes_region_and_template(self, db_session):
        user = await _seed_user(db_session, "upd@example.com")
        async with db_session() as db:
            saved = await save_cv(
                db, attempt_id="x", source="builder", region="AU", template_id="modern",
                rendered_html="<p/>", cv_data=_CV_DATA, user_id=user.id,
            )
            cv_id = saved.id
        async with db_session() as db:
            updated = await update_cv(
                db, cv_id=cv_id, region="US", template_id="classic",
                rendered_html="<p>New</p>", cv_data=_CV_DATA,
            )
        assert updated is not None
        assert updated.region == "US"
        assert updated.template_id == "classic"
