"""Shared fixtures for QuillCV tests."""


import pytest

from app.scoring.adapters.keyword_matcher import ATSResult
from app.infrastructure.llm.client import LLMClient, LLMResult

# ── Sample data ──────────────────────────────────────────────

SAMPLE_JOB_DESCRIPTION = """\
About The Role

We are looking for a Senior Software Engineer to join our platform team.

Responsibilities:
- Design and build scalable microservices using Python and Go
- Implement CI/CD pipelines and improve developer tooling
- Mentor junior engineers and conduct code reviews
- Work with PostgreSQL, Redis, and Kubernetes

Requirements:
- 5+ years of software development experience
- Strong proficiency in Python and at least one other language
- Experience with cloud platforms (AWS or GCP)
- Solid understanding of distributed systems
- Excellent communication skills
"""

SAMPLE_CV_TEXT = """\
John Smith
john@example.com | +1 555 123 4567 | San Francisco, CA

Summary
Senior software engineer with 8 years of experience building web applications
and distributed systems. Passionate about clean code and mentoring.

Experience
Senior Engineer — Acme Corp — 2020-Present
- Built microservices handling 10M requests/day using Python and FastAPI
- Reduced deployment time by 60% implementing CI/CD with GitHub Actions
- Mentored 5 junior developers through structured pairing program

Software Engineer — StartupCo — 2016-2020
- Developed REST APIs serving 50K daily active users
- Migrated monolith to microservices architecture on AWS

Education
B.S. Computer Science — MIT — 2016

Skills
Python, Go, PostgreSQL, Redis, Docker, Kubernetes, AWS, CI/CD
"""

SAMPLE_CV_DATA = {
    "name": "John Smith",
    "title": "Senior Software Engineer",
    "email": "john@example.com",
    "phone": "+1 555 123 4567",
    "location": "San Francisco, CA",
    "linkedin": "",
    "github": "",
    "portfolio": "",
    "summary": "Senior software engineer with 8 years of experience.",
    "experience": [
        {
            "title": "Senior Engineer",
            "company": "Acme Corp",
            "location": "SF",
            "date": "2020 – Present",
            "tech": "Python, FastAPI",
            "bullets": [
                "Built microservices handling 10M requests/day",
                "Reduced deployment time by 60%",
            ],
        }
    ],
    "skills": ["Python", "Go", "PostgreSQL", "Redis", "Docker", "Kubernetes"],
    "skills_grouped": [],
    "education": [{"degree": "B.S. Computer Science", "institution": "MIT", "date": "2016"}],
    "certifications": ["Duolingo English: Advanced", "AWS Solutions Architect"],
    "projects": [],
    "references": [],
}


# ── Mock LLM ─────────────────────────────────────────────────

class MockLLM(LLMClient):
    """LLM client that returns pre-configured responses for testing."""

    def __init__(self, response_text: str = "{}"):
        self._response = response_text

    async def generate(self, prompt: str) -> LLMResult:
        return LLMResult(
            text=self._response,
            model="mock-model",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.001,
        )


@pytest.fixture
def mock_llm():
    """Returns a factory for MockLLM with configurable responses."""
    def _make(response_text: str = "{}"):
        return MockLLM(response_text)
    return _make


@pytest.fixture
def sample_job_description():
    return SAMPLE_JOB_DESCRIPTION


@pytest.fixture
def sample_cv_text():
    return SAMPLE_CV_TEXT


@pytest.fixture
def sample_cv_data():
    return dict(SAMPLE_CV_DATA)  # fresh copy


@pytest.fixture
def sample_ats_result():
    """A realistic ATSResult for testing."""
    return ATSResult(
        score=65,
        keyword_match_pct=55,
        matched_keywords=["python", "microservices", "ci/cd"],
        missing_keywords=["go", "kubernetes", "distributed systems"],
        formatting_issues=[],
        section_checks={"summary": True, "experience": True, "education": True, "skills": True},
        recommendations=["Add missing keywords where truthful: go, kubernetes"],
    )
