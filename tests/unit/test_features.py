"""Unit tests for app/features.py (feature flag registry)."""

import pytest

from app import features


@pytest.fixture(autouse=True)
def reset_cache():
    """Each test starts with an empty in-memory cache."""
    original = dict(features._cache)
    features._cache.clear()
    yield
    features._cache.clear()
    features._cache.update(original)


class TestIsEnabled:
    def test_unknown_key_returns_false(self):
        assert features.is_enabled("nope_not_a_real_flag") is False

    def test_default_for_known_flag(self):
        """With an empty cache, ``is_enabled`` falls back to the spec default."""
        spec = features.REGISTRY["open_signups"]
        assert features.is_enabled("open_signups") is spec.default()

    def test_cache_override_wins(self):
        features._cache["open_signups"] = False
        assert features.is_enabled("open_signups") is False
        features._cache["open_signups"] = True
        assert features.is_enabled("open_signups") is True


@pytest.mark.asyncio
class TestRoundTrip:
    async def test_set_flag_unknown_key_raises(self, db_session):
        with pytest.raises(KeyError):
            await features.set_flag("does_not_exist", True)

    async def test_set_flag_persists_and_updates_cache(self, db_session):
        await features.set_flag("open_signups", False, updated_by="test-user")
        assert features.is_enabled("open_signups") is False

        # The DB row should reflect the new value too.
        from sqlalchemy import select

        from app.infrastructure.persistence.orm_models import FeatureFlag

        async with db_session() as db:
            rows = await db.execute(select(FeatureFlag).where(FeatureFlag.key == "open_signups"))
            row = rows.scalar_one()
        assert row.enabled is False
        assert row.updated_by == "test-user"

    async def test_refresh_cache_loads_from_db(self, db_session):
        from app.infrastructure.persistence.orm_models import FeatureFlag

        async with db_session() as db:
            db.add(FeatureFlag(key="open_signups", enabled=False, updated_by="seed"))
            await db.commit()

        # Cache is empty until refresh runs.
        assert "open_signups" not in features._cache
        await features.refresh_cache()
        assert features._cache["open_signups"] is False

    async def test_list_flags_reports_default_and_override(self, db_session):
        # No row -> override is None, enabled follows default.
        listing = await features.list_flags()
        entry = next(f for f in listing if f["key"] == "open_signups")
        assert entry["override"] is None
        assert entry["enabled"] == entry["default"]

        # With a row -> override surfaces.
        await features.set_flag("open_signups", False)
        listing = await features.list_flags()
        entry = next(f for f in listing if f["key"] == "open_signups")
        assert entry["override"] is False
        assert entry["enabled"] is False
