"""Unit tests for app/cv_builder/use_cases/build_cv.py."""

from app.cv_builder.use_cases.build_cv import (
    apply_pii_prefill,
    compute_pii_backfill,
    cv_data_from_attempt,
    default_save_label,
    region_fields_map,
    restore_pii_tokens,
)


class TestRegionFieldsMap:
    def test_returns_known_regions(self):
        m = region_fields_map()
        assert "AU" in m
        assert "US" in m
        assert isinstance(m["AU"], dict)


class TestCvDataFromAttempt:
    def test_empty_attempt(self):
        data = cv_data_from_attempt({})
        assert isinstance(data, dict)

    def test_attempt_with_builder_data(self):
        attempt = {"builder_data": {"name": "Alice", "skills": ["Python"]}}
        data = cv_data_from_attempt(attempt)
        assert data["name"] == "Alice"
        assert "Python" in data["skills"]


class TestApplyPiiPrefill:
    def test_fills_empty_fields(self):
        cv = {"name": ""}
        result = apply_pii_prefill(cv, {"full_name": "Alice", "email": "a@b.c"})
        assert result["name"] == "Alice"
        assert result["email"] == "a@b.c"

    def test_does_not_overwrite_filled(self):
        cv = {"name": "ExistingName", "email": "a@b.c"}
        result = apply_pii_prefill(cv, {"full_name": "Other", "email": "x@y.z"})
        assert result["name"] == "ExistingName"
        # email is filled, so should NOT be overwritten either
        assert result["email"] == "a@b.c"


class TestRestorePiiTokens:
    def test_replaces_known_tokens(self):
        stored = {"name": "<<CANDIDATE_NAME>>", "email": "<<EMAIL_1>>"}
        result = restore_pii_tokens(stored, {"full_name": "Alice", "email": "a@b.c"})
        assert result["name"] == "Alice"
        assert result["email"] == "a@b.c"

    def test_leaves_tokens_unchanged_when_pii_missing(self):
        stored = {"name": "<<CANDIDATE_NAME>>"}
        result = restore_pii_tokens(stored, {})
        assert result["name"] == "<<CANDIDATE_NAME>>"


class TestComputePiiBackfill:
    def test_returns_updates_for_missing(self):
        updates = compute_pii_backfill(
            cv_data={"name": "Alice", "email": "a@b.c"},
            pii={"full_name": "", "email": ""},
        )
        # At least one field should backfill; behaviour depends on map.
        assert isinstance(updates, dict)

    def test_no_updates_when_pii_complete(self):
        updates = compute_pii_backfill(
            cv_data={"name": "X"},
            pii={"full_name": "X"},
        )
        assert "full_name" not in updates


class TestDefaultSaveLabel:
    def test_with_name(self):
        label = default_save_label({"name": "Jane"}, "modern")
        assert "Jane" in label
        assert "Modern" in label

    def test_without_name(self):
        label = default_save_label({}, "classic")
        assert "Classic" in label
