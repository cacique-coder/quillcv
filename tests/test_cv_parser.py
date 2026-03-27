"""Tests for CV parser — file format detection and text extraction."""

import pytest

from app.cv_generation.adapters.pdfplumber_parser import parse_cv, parse_text


class TestParseCV:
    """Tests for parse_cv() dispatcher."""

    def test_txt_file(self):
        text = parse_cv("resume.txt", b"Hello world\nThis is my CV")
        assert "Hello world" in text
        assert "This is my CV" in text

    def test_md_file(self):
        text = parse_cv("resume.md", b"# My CV\n\n- Python\n- Go")
        assert "My CV" in text
        assert "Python" in text

    def test_unsupported_format_raises(self):
        with pytest.raises(ValueError, match="Unsupported file format"):
            parse_cv("resume.xlsx", b"data")

    def test_case_insensitive_extension(self):
        text = parse_cv("resume.TXT", b"content here")
        assert "content here" in text

    def test_empty_txt_file(self):
        text = parse_cv("empty.txt", b"")
        assert text == ""


class TestParseText:
    """Tests for plain text parser."""

    def test_utf8_text(self):
        text = parse_text("Résumé — Senior Engineer".encode())
        assert "Résumé" in text

    def test_invalid_utf8_handled(self):
        # Should not raise — uses errors="replace"
        text = parse_text(b"\xff\xfe Invalid bytes here")
        assert isinstance(text, str)
