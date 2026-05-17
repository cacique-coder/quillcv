"""Unit tests for the template-picker pagination markup.

Verifies:
1. All 17 templates are rendered as thumbnails in the builder.html Jinja source
   with correct data-page attributes and the right initial hidden state.
2. The tmpl_visuals map covers every registered template ID so no thumbnail
   falls back to the identical default cream card.
3. Each template in tmpl_visuals has a unique background color so pages look
   visually different when the user pages through them.
"""

from __future__ import annotations

import math
import pathlib
import re

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BUILDER_HTML = pathlib.Path(__file__).parent.parent.parent / "app" / "templates" / "builder.html"
TEMPLATE_PY = (
    pathlib.Path(__file__).parent.parent.parent
    / "app"
    / "cv_export"
    / "adapters"
    / "template_registry.py"
)

TMPL_PER_PAGE = 4


def _builder_source() -> str:
    return BUILDER_HTML.read_text()


def _all_template_ids() -> list[str]:
    """Return all template IDs registered in template_registry.TEMPLATES."""
    from app.cv_export.adapters.template_registry import TEMPLATES

    return list(TEMPLATES.keys())


def _extract_tmpl_visuals_block(source: str) -> str:
    """Return the raw text of the {% set tmpl_visuals = { ... } %} block."""
    match = re.search(r"\{%-?\s*set\s+tmpl_visuals\s*=\s*\{(.+?)\}\s*%\}", source, re.DOTALL)
    assert match, "Could not locate tmpl_visuals block in builder.html"
    return match.group(1)


def _parse_tmpl_visuals_ids(source: str) -> list[str]:
    """Extract template IDs declared in the tmpl_visuals Jinja dict.

    Each top-level entry looks like:
        'classic':  {'bg': ..., 'accent': ..., ...},

    We identify them by the pattern: single-quoted key followed by a colon then
    a brace-opening, which distinguishes template IDs from the inner property keys
    (bg, accent, center, dark) whose values are strings or booleans, not dicts.
    """
    block = _extract_tmpl_visuals_block(source)
    # Match top-level keys — they are followed by ': {' (with optional whitespace)
    return re.findall(r"'([a-z0-9_-]+)'\s*:\s*\{", block)


def _parse_tmpl_visuals_bgs(source: str) -> list[str]:
    """Extract all 'bg' hex values declared in tmpl_visuals."""
    block = _extract_tmpl_visuals_block(source)
    return re.findall(r"'bg'\s*:\s*'(#[0-9a-fA-F]{3,6})'", block)


# ---------------------------------------------------------------------------
# Tests: tmpl_visuals coverage
# ---------------------------------------------------------------------------


class TestTmplVisualsCompleteness:
    """Every registered template should have an explicit entry in tmpl_visuals."""

    def test_all_templates_have_visual_hint(self):
        """No template should fall back to the default cream background."""
        source = _builder_source()
        declared = set(_parse_tmpl_visuals_ids(source))
        registered = set(_all_template_ids())
        missing = registered - declared
        assert not missing, (
            f"Templates missing from tmpl_visuals (will render as identical cream cards): {missing}"
        )

    def test_no_extra_ids_in_visuals(self):
        """tmpl_visuals should not reference IDs that don't exist in the registry."""
        source = _builder_source()
        declared = set(_parse_tmpl_visuals_ids(source))
        registered = set(_all_template_ids())
        phantom = declared - registered
        assert not phantom, (
            f"tmpl_visuals references IDs not in template registry: {phantom}"
        )


class TestTmplVisualsDistinctiveness:
    """Background colors must be visually distinct so pages look different."""

    def test_all_bg_colors_are_unique(self):
        """No two templates should share the same bg hex value."""
        source = _builder_source()
        bgs = _parse_tmpl_visuals_bgs(source)
        # Normalise to lowercase for comparison
        bgs_lower = [b.lower() for b in bgs]
        duplicates = [b for b in set(bgs_lower) if bgs_lower.count(b) > 1]
        assert not duplicates, (
            f"Duplicate bg colors in tmpl_visuals (thumbnails will look identical): {duplicates}"
        )

    def test_accent_stripe_color_present_in_each_entry(self):
        """Every tmpl_visuals entry must have an 'accent' key for the stripe."""
        source = _builder_source()
        block = _extract_tmpl_visuals_block(source)
        ids = _parse_tmpl_visuals_ids(source)
        # Count accent entries
        accent_count = len(re.findall(r"'accent'\s*:", block))
        assert accent_count == len(ids), (
            f"Expected {len(ids)} 'accent' entries in tmpl_visuals, found {accent_count}. "
            "Every template needs an accent stripe color."
        )


# ---------------------------------------------------------------------------
# Tests: pagination markup structure
# ---------------------------------------------------------------------------


class TestTemplatePaginationMarkup:
    """Verify the data-page / hidden structure in builder.html Jinja source."""

    def test_tmpl_per_page_is_four(self):
        """tmpl_per_page must be 4 (matches the existing UX contract)."""
        source = _builder_source()
        assert "tmpl_per_page = 4" in source, "tmpl_per_page must be set to 4"

    def test_data_page_attribute_is_rendered_from_loop_index(self):
        """data-page must be computed from loop.index0 // tmpl_per_page + 1."""
        source = _builder_source()
        assert "loop.index0 // tmpl_per_page + 1" in source, (
            "data-page computation must use loop.index0 // tmpl_per_page + 1"
        )

    def test_hidden_attribute_uses_page_num_vs_start_page(self):
        """Thumbnails not on the start page must receive the hidden attribute."""
        source = _builder_source()
        assert "page_num != ns.start_page" in source and "hidden" in source, (
            "Thumbnails on pages != start_page must get the hidden attribute"
        )

    def test_expected_page_count_for_17_templates(self):
        """With 17 templates and 4 per page, we expect ceil(17/4) = 5 pages."""
        from app.cv_export.adapters.template_registry import list_templates

        total = len(list_templates())
        expected_pages = math.ceil(total / TMPL_PER_PAGE)
        assert expected_pages == 5, (
            f"Expected 5 pages for {total} templates at {TMPL_PER_PAGE} per page, "
            f"got {expected_pages}"
        )

    def test_page_distribution(self):
        """Verify how many templates fall on each page (last page may have fewer)."""
        from app.cv_export.adapters.template_registry import list_templates

        templates = list_templates()
        total = len(templates)
        pages: dict[int, list[str]] = {}
        for i, t in enumerate(templates):
            page = i // TMPL_PER_PAGE + 1
            pages.setdefault(page, []).append(t.id)

        # Pages 1–4 must have exactly 4 templates; page 5 has the remainder.
        for page_num in range(1, 5):
            assert len(pages.get(page_num, [])) == 4, (
                f"Page {page_num} should have 4 templates, got {len(pages.get(page_num, []))}"
            )
        last_page = math.ceil(total / TMPL_PER_PAGE)
        remainder = total % TMPL_PER_PAGE or TMPL_PER_PAGE
        assert len(pages.get(last_page, [])) == remainder, (
            f"Last page ({last_page}) should have {remainder} templates, "
            f"got {len(pages.get(last_page, []))}"
        )


# ---------------------------------------------------------------------------
# Tests: CSS fix — [hidden] on grid children
# ---------------------------------------------------------------------------


class TestBuilderCssHiddenRule:
    """Confirm the defensive [hidden] CSS rule is present in builder.css."""

    BUILDER_CSS = (
        pathlib.Path(__file__).parent.parent.parent / "app" / "static" / "builder.css"
    )

    def test_hidden_rule_present(self):
        """builder.css must explicitly set display:none on .tmpl-pick .t[hidden]."""
        css = self.BUILDER_CSS.read_text()
        assert ".tmpl-pick .t[hidden]" in css, (
            "builder.css must include '.tmpl-pick .t[hidden] { display: none !important; }' "
            "to ensure grid children respect the hidden attribute across all browsers"
        )
        # Also verify it sets display:none
        assert "display: none" in css or "display:none" in css, (
            "The [hidden] rule must set display: none"
        )

    def test_t_stripe_rule_present(self):
        """builder.css must define .tmpl-pick .t .t-stripe for the accent stripe."""
        css = self.BUILDER_CSS.read_text()
        assert ".tmpl-pick .t .t-stripe" in css, (
            "builder.css must define .tmpl-pick .t .t-stripe for the per-template accent stripe"
        )
