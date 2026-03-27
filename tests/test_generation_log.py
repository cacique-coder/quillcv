"""Tests for generation logging."""

import json

import pytest

from app.scoring.adapters.keyword_matcher import ATSResult
from app.cv_generation.adapters.generation_log import _score_breakdown, log_generation


@pytest.fixture(autouse=True)
def use_temp_log_dir(tmp_path, monkeypatch):
    """Use a temp directory for log files during tests."""
    monkeypatch.setattr("app.cv_generation.adapters.generation_log.LOG_DIR", tmp_path)
    monkeypatch.setattr("app.cv_generation.adapters.generation_log.LOG_FILE", tmp_path / "generations.jsonl")
    return tmp_path


class TestScoreBreakdown:
    def test_breakdown_sums_correctly(self, sample_ats_result):
        breakdown = _score_breakdown(sample_ats_result)
        assert "total" in breakdown
        assert "keywords_pts" in breakdown
        assert "sections_pts" in breakdown
        assert "formatting_pts" in breakdown
        assert "recommendations_pts" in breakdown

    def test_breakdown_matches_score(self, sample_ats_result):
        breakdown = _score_breakdown(sample_ats_result)
        assert breakdown["total"] == sample_ats_result.score


class TestLogGeneration:
    def test_creates_log_file(self, use_temp_log_dir):
        log_file = use_temp_log_dir / "generations.jsonl"
        ats = ATSResult(
            score=70, keyword_match_pct=60,
            matched_keywords=["python"], missing_keywords=["go"],
            section_checks={"summary": True, "experience": True, "education": True, "skills": True},
        )
        log_generation(
            attempt_id="test123",
            region="US",
            template_id="modern",
            cv_text="My CV text",
            job_description="Job desc",
            ats_original=ats,
            ats_generated=ats,
            generated_text="Generated text",
            cv_data={"name": "Test", "experience": [], "skills": []},
            timings={"parse_cv": 0.1, "ai_generate": 2.0},
        )
        assert log_file.exists()
        lines = log_file.read_text().strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["attempt_id"] == "test123"
        assert entry["region"] == "US"
        assert entry["score_original"] == 70

    def test_appends_multiple_entries(self, use_temp_log_dir):
        log_file = use_temp_log_dir / "generations.jsonl"
        ats = ATSResult(score=50, keyword_match_pct=40,
                        section_checks={"summary": True, "experience": True, "education": True, "skills": True})
        for i in range(3):
            log_generation(
                attempt_id=f"test{i}",
                region="US", template_id="modern",
                cv_text="cv", job_description="jd",
                ats_original=ats, ats_generated=ats,
                generated_text="gen", cv_data={"experience": [], "skills": []},
                timings={},
            )
        lines = log_file.read_text().strip().split("\n")
        assert len(lines) == 3
