"""Smoke tests for the DOCX exporter."""

import pytest

from app.cv_export.adapters.docx_export import generate_docx


@pytest.fixture
def cv_data():
    return {
        "name": "Alice Smith",
        "title": "Senior Engineer",
        "email": "alice@example.com",
        "phone": "+61 400 000 000",
        "location": "Sydney, AU",
        "summary": "Builder of systems.",
        "experience": [
            {
                "title": "Engineer",
                "company": "Acme",
                "date": "2020-2024",
                "location": "Sydney",
                "tech": "Python, FastAPI",
                "bullets": ["Built APIs", "Shipped fast"],
            },
        ],
        "skills": ["Python", "Go"],
        "skills_grouped": [{"category": "Languages", "items": ["Python", "Go"]}],
        "education": [{"degree": "BS CS", "institution": "ANU", "date": "2018"}],
        "certifications": ["AWS Solutions Architect"],
        "projects": [{"name": "OSS", "description": "An OSS project", "tech": ["Python"]}],
        "languages": ["English (native)"],
        "references": [],
    }


@pytest.mark.parametrize("template_id", ["classic", "modern", "minimal"])
@pytest.mark.parametrize("region_code", ["AU", "US", "UK"])
def test_generate_docx_returns_valid_bytes(cv_data, template_id, region_code):
    blob = generate_docx(cv_data, region_code=region_code, template_id=template_id)
    assert isinstance(blob, bytes)
    assert len(blob) > 1000  # docx files are zip archives, always non-trivial
    # DOCX files are ZIP archives — magic header "PK"
    assert blob[:2] == b"PK"


def test_generate_docx_minimal_payload():
    """Works even with mostly-empty data — should not crash on missing sections."""
    blob = generate_docx({"name": "X"}, region_code="AU", template_id="classic")
    assert blob[:2] == b"PK"
