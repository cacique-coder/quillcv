"""Tests for template registry — templates, regions, and configuration."""

from app.cv_export.adapters.template_registry import (
    REGION_RULES,
    CVTemplate,
    RegionConfig,
    get_region,
    get_template,
    list_regions,
    list_templates,
)


class TestTemplates:
    """Tests for CV template registry."""

    EXPECTED_TEMPLATES = [
        "classic", "modern", "minimal", "executive", "tech", "compact",
        "academic", "healthcare", "legal", "creative", "sales",
        "engineering", "education", "consulting", "nonprofit", "federal",
    ]

    def test_all_templates_exist(self):
        for tpl_id in self.EXPECTED_TEMPLATES:
            tpl = get_template(tpl_id)
            assert tpl is not None, f"Template '{tpl_id}' not found"
            assert isinstance(tpl, CVTemplate)

    def test_template_has_required_fields(self):
        for tpl_id in self.EXPECTED_TEMPLATES:
            tpl = get_template(tpl_id)
            assert tpl.id == tpl_id
            assert len(tpl.name) > 0
            assert len(tpl.description) > 0
            assert len(tpl.best_for) > 0

    def test_unknown_template_returns_none(self):
        assert get_template("nonexistent") is None

    def test_list_templates_returns_all(self):
        templates = list_templates()
        assert len(templates) == len(self.EXPECTED_TEMPLATES)

    def test_list_templates_returns_cvtemplate_instances(self):
        templates = list_templates()
        for tpl in templates:
            assert isinstance(tpl, CVTemplate)


class TestRegions:
    """Tests for region configuration."""

    EXPECTED_REGIONS = ["AU", "US", "UK", "CA", "NZ", "DE", "FR", "NL", "IN", "BR", "AE", "JP"]

    def test_all_regions_exist(self):
        for code in self.EXPECTED_REGIONS:
            region = get_region(code)
            assert region is not None, f"Region '{code}' not found"
            assert isinstance(region, RegionConfig)

    def test_region_has_required_fields(self):
        for code in self.EXPECTED_REGIONS:
            region = get_region(code)
            assert region.code == code
            assert len(region.name) > 0
            assert len(region.flag) > 0
            assert len(region.language) > 0
            assert len(region.page_length) > 0

    def test_unknown_region_returns_none(self):
        assert get_region("XX") is None

    def test_list_regions_returns_all(self):
        regions = list_regions()
        assert len(regions) == len(self.EXPECTED_REGIONS)

    def test_us_region_config(self):
        us = get_region("US")
        assert us.name == "United States"
        assert us.include_references is False  # US doesn't expect references on CV
        assert us.spelling == "American"

    def test_au_region_config(self):
        au = get_region("AU")
        assert au.name == "Australia"
        assert au.include_references is True  # AU expects references
        assert au.include_visa_status is True

    def test_de_region_includes_photo(self):
        de = get_region("DE")
        assert de.include_photo  # Germany expects photo (value is 'common', truthy)

    def test_region_rules_backward_compat(self):
        """REGION_RULES should exist for every region."""
        for code in self.EXPECTED_REGIONS:
            assert code in REGION_RULES, f"REGION_RULES missing '{code}'"
            rules = REGION_RULES[code]
            assert "notes" in rules
