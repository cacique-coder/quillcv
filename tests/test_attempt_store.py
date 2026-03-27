"""Tests for attempt store — session persistence."""


import pytest

from app.infrastructure.persistence.attempt_store import (
    create_attempt,
    get_attempt,
    get_document_bytes,
    get_document_filename,
    save_document,
    update_attempt,
)


@pytest.fixture(autouse=True)
def clean_test_attempts(tmp_path, monkeypatch):
    """Use a temp directory for attempts during tests."""
    test_dir = tmp_path / "attempts"
    test_dir.mkdir()
    monkeypatch.setattr("app.services.attempt_store.ATTEMPTS_DIR", test_dir)
    return test_dir


class TestCreateAttempt:
    def test_creates_attempt(self):
        attempt_id = create_attempt()
        assert len(attempt_id) == 16
        assert attempt_id.isalnum()

    def test_attempt_retrievable(self):
        attempt_id = create_attempt()
        data = get_attempt(attempt_id)
        assert data is not None
        assert data["id"] == attempt_id
        assert data["step"] == 1

    def test_unique_ids(self):
        ids = {create_attempt() for _ in range(10)}
        assert len(ids) == 10


class TestUpdateAttempt:
    def test_updates_fields(self):
        attempt_id = create_attempt()
        update_attempt(attempt_id, region="AU", template_id="modern")
        data = get_attempt(attempt_id)
        assert data["region"] == "AU"
        assert data["template_id"] == "modern"

    def test_preserves_existing_fields(self):
        attempt_id = create_attempt()
        update_attempt(attempt_id, region="AU")
        update_attempt(attempt_id, template_id="tech")
        data = get_attempt(attempt_id)
        assert data["region"] == "AU"
        assert data["template_id"] == "tech"

    def test_sets_updated_at(self):
        attempt_id = create_attempt()
        update_attempt(attempt_id, region="US")
        data = get_attempt(attempt_id)
        assert "updated_at" in data


class TestGetAttempt:
    def test_nonexistent_returns_none(self):
        assert get_attempt("nonexistent_id_1234") is None


class TestDocumentStorage:
    def test_save_and_retrieve_document(self):
        attempt_id = create_attempt()
        content = b"This is my CV content"
        save_document(attempt_id, "cv_file", "resume.pdf", content)

        retrieved = get_document_bytes(attempt_id, "cv_file")
        assert retrieved == content

    def test_get_document_filename(self):
        attempt_id = create_attempt()
        save_document(attempt_id, "cv_file", "my_resume.pdf", b"content")

        filename = get_document_filename(attempt_id, "cv_file")
        assert filename == "my_resume.pdf"

    def test_missing_document_returns_none(self):
        attempt_id = create_attempt()
        assert get_document_bytes(attempt_id, "cv_file") is None
        assert get_document_filename(attempt_id, "cv_file") is None

    def test_overwrite_document(self):
        attempt_id = create_attempt()
        save_document(attempt_id, "cv_file", "v1.pdf", b"version 1")
        save_document(attempt_id, "cv_file", "v2.pdf", b"version 2")

        assert get_document_bytes(attempt_id, "cv_file") == b"version 2"
        assert get_document_filename(attempt_id, "cv_file") == "v2.pdf"

    def test_multiple_documents(self):
        attempt_id = create_attempt()
        save_document(attempt_id, "cv_file", "resume.pdf", b"cv content")
        save_document(attempt_id, "extra_doc_0", "cover.pdf", b"cover letter")

        assert get_document_bytes(attempt_id, "cv_file") == b"cv content"
        assert get_document_bytes(attempt_id, "extra_doc_0") == b"cover letter"
