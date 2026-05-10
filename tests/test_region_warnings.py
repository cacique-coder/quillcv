"""Tests for region-convention warnings.

Covers the non-blocking warnings surfaced in the wizard when user-supplied
data conflicts with the selected region's CV conventions. Read-only — never
gates submission. The required-field path is covered separately by
``_check_pii_completeness`` in the wizard router.
"""

from app.cv_generation.use_cases.region_warnings import (
    RegionWarning,
    region_warnings,
    region_warnings_dicts,
)

# ─── Helpers ────────────────────────────────────────────────────────


def _fields(warnings: list[RegionWarning]) -> set[str]:
    return {w.field for w in warnings}


# ─── Photo conventions ──────────────────────────────────────────────


class TestPhotoWarnings:
    def test_au_with_photo_warns(self):
        """AU region recommends no photo — uploading one should warn."""
        attempt = {"photo_path": "user123/photo.jpg"}
        warnings = region_warnings(attempt, {}, "AU")
        photo = [w for w in warnings if w.field == "photo"]
        assert len(photo) == 1
        assert photo[0].severity == "warning"
        assert "Australia" in photo[0].message

    def test_us_with_photo_warns(self):
        attempt = {"photo_path": "user123/photo.jpg"}
        warnings = region_warnings(attempt, {}, "US")
        assert any(w.field == "photo" and w.severity == "warning" for w in warnings)

    def test_uk_with_photo_warns(self):
        attempt = {"photo_path": "user123/photo.jpg"}
        warnings = region_warnings(attempt, {}, "UK")
        assert any(w.field == "photo" and w.severity == "warning" for w in warnings)

    def test_de_with_photo_no_warning(self):
        """Germany expects a photo (include_photo='common') — no warning."""
        attempt = {"photo_path": "user123/photo.jpg"}
        warnings = region_warnings(attempt, {}, "DE")
        assert not any(w.field == "photo" for w in warnings)

    def test_jp_with_photo_no_warning(self):
        """Japan requires a photo — no warning."""
        attempt = {"photo_path": "user123/photo.jpg"}
        warnings = region_warnings(attempt, {}, "JP")
        assert not any(w.field == "photo" for w in warnings)

    def test_nl_with_photo_info_only(self):
        """NL is 'optional' — should be info, not warning."""
        attempt = {"photo_path": "user123/photo.jpg"}
        warnings = region_warnings(attempt, {}, "NL")
        photo = [w for w in warnings if w.field == "photo"]
        assert len(photo) == 1
        assert photo[0].severity == "info"

    def test_us_no_photo_no_warning(self):
        warnings = region_warnings({}, {}, "US")
        assert not any(w.field == "photo" for w in warnings)

    def test_photo_in_pii_vault_also_triggers(self):
        """Defensive: photo persisted in PII vault should also be detected."""
        warnings = region_warnings({}, {"photo_path": "x.jpg"}, "AU")
        assert any(w.field == "photo" for w in warnings)


# ─── References ─────────────────────────────────────────────────────


class TestReferenceWarnings:
    def test_us_with_references_warns(self):
        attempt = {"references": [{"name": "Jane Doe", "email": "j@x.com"}]}
        warnings = region_warnings(attempt, {}, "US")
        refs = [w for w in warnings if w.field == "references"]
        assert len(refs) == 1
        assert refs[0].severity == "warning"
        assert "outdated" in refs[0].message.lower()

    def test_uk_with_references_warns(self):
        attempt = {"references": [{"name": "Jane Doe"}]}
        warnings = region_warnings(attempt, {}, "UK")
        assert any(w.field == "references" for w in warnings)

    def test_au_with_references_no_warning(self):
        """Australia includes references — no warning."""
        attempt = {"references": [{"name": "Jane Doe"}]}
        warnings = region_warnings(attempt, {}, "AU")
        assert not any(w.field == "references" for w in warnings)

    def test_us_empty_references_list_no_warning(self):
        attempt = {"references": [{"name": ""}]}
        warnings = region_warnings(attempt, {}, "US")
        assert not any(w.field == "references" for w in warnings)

    def test_us_references_in_vault_triggers(self):
        warnings = region_warnings({}, {"references": [{"name": "Jane"}]}, "US")
        assert any(w.field == "references" for w in warnings)


# ─── DOB / marital / nationality ────────────────────────────────────


class TestPiiFieldWarnings:
    def test_us_with_dob_warns(self):
        warnings = region_warnings({"dob": "1990-01-01"}, {}, "US")
        dob = [w for w in warnings if w.field == "dob"]
        assert len(dob) == 1
        assert dob[0].severity == "warning"

    def test_de_with_dob_no_warning(self):
        """Germany expects DOB."""
        warnings = region_warnings({"dob": "1990-01-01"}, {}, "DE")
        assert not any(w.field == "dob" for w in warnings)

    def test_us_with_marital_status_warns(self):
        warnings = region_warnings({"marital_status": "single"}, {}, "US")
        assert any(w.field == "marital_status" for w in warnings)

    def test_in_with_marital_status_no_warning(self):
        """India includes marital status."""
        warnings = region_warnings({"marital_status": "single"}, {}, "IN")
        assert not any(w.field == "marital_status" for w in warnings)

    def test_uk_with_nationality_warns(self):
        warnings = region_warnings({"nationality": "British"}, {}, "UK")
        assert any(w.field == "nationality" for w in warnings)

    def test_de_with_nationality_no_warning(self):
        """Germany includes nationality."""
        warnings = region_warnings({"nationality": "German"}, {}, "DE")
        assert not any(w.field == "nationality" for w in warnings)


# ─── Empty / unknown / edge cases ───────────────────────────────────


class TestEdgeCases:
    def test_empty_attempt_no_warnings(self):
        assert region_warnings({}, {}, "US") == []

    def test_empty_attempt_au_no_warnings(self):
        assert region_warnings({}, {}, "AU") == []

    def test_unknown_region_returns_empty(self):
        """Unknown region codes must not crash — return empty list."""
        attempt = {"photo_path": "x.jpg", "dob": "1990-01-01"}
        assert region_warnings(attempt, {}, "ZZ") == []

    def test_unknown_region_with_pii_returns_empty(self):
        assert region_warnings({}, {"photo_path": "x.jpg"}, "XYZ") == []

    def test_missing_pii_keys_no_crash(self):
        """Missing/None values shouldn't blow up the helper checks."""
        attempt = {"dob": None, "marital_status": "", "references": None}
        assert region_warnings(attempt, {}, "US") == []

    def test_dicts_helper_returns_plain_dicts(self):
        attempt = {"dob": "1990-01-01"}
        out = region_warnings_dicts(attempt, {}, "US")
        assert isinstance(out, list)
        assert out and isinstance(out[0], dict)
        assert {"severity", "field", "message"} <= set(out[0].keys())


# ─── Spelling check (advisory, opt-in via cv_text) ──────────────────


class TestSpellingWarnings:
    def test_us_with_british_spellings_info(self):
        cv_text = (
            "I organised the colour palette and led the programme. "
            "Specialised in optimising customer experience."
        )
        warnings = region_warnings({}, {}, "US", cv_text=cv_text)
        spell = [w for w in warnings if w.field == "cv_text"]
        assert len(spell) == 1
        assert spell[0].severity == "info"

    def test_uk_with_american_spellings_info(self):
        cv_text = (
            "I organized the color palette and ran the program. "
            "Specialized in optimizing customer experience."
        )
        warnings = region_warnings({}, {}, "UK", cv_text=cv_text)
        assert any(w.field == "cv_text" and w.severity == "info" for w in warnings)

    def test_below_threshold_no_warning(self):
        """Only one British marker — should not flag."""
        cv_text = "I organised the team."
        warnings = region_warnings({}, {}, "US", cv_text=cv_text)
        assert not any(w.field == "cv_text" for w in warnings)

    def test_no_cv_text_skipped(self):
        warnings = region_warnings({}, {}, "US")
        assert not any(w.field == "cv_text" for w in warnings)

    def test_non_english_region_skipped(self):
        cv_text = "organised colour programme specialised optimised"
        # French region — spelling != American/British so the check is skipped.
        warnings = region_warnings({}, {}, "FR", cv_text=cv_text)
        assert not any(w.field == "cv_text" for w in warnings)


# ─── Combined scenarios ─────────────────────────────────────────────


class TestCombinations:
    def test_us_with_everything_discouraged(self):
        attempt = {
            "photo_path": "x.jpg",
            "dob": "1990-01-01",
            "marital_status": "single",
            "nationality": "American",
            "references": [{"name": "Jane Doe"}],
        }
        warnings = region_warnings(attempt, {}, "US")
        assert _fields(warnings) >= {
            "photo", "dob", "marital_status", "nationality", "references",
        }
        # All five are warnings (not info) for the US region.
        assert all(w.severity == "warning" for w in warnings)

    def test_attempt_overrides_pii(self):
        """Attempt and vault are both checked — either source counts."""
        warnings = region_warnings({"dob": "1990-01-01"}, {"dob": ""}, "US")
        assert any(w.field == "dob" for w in warnings)
