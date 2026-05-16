"""Shared fixtures for QuillCV tests."""


import re

import pytest

from app.infrastructure.llm.client import LLMClient, LLMResult
from app.scoring.adapters.keyword_matcher import ATSResult

# ── CSRF helpers ─────────────────────────────────────────────
# CSRFMiddleware sets request.state.csrf_token from the session and rejects any
# POST/PUT/PATCH/DELETE without a matching `csrf_token` form field or
# `X-CSRF-Token` header. Tests that POST need to obtain a token first.

_CSRF_INPUT_RE = re.compile(r'name=["\']csrf_token["\']\s+value=["\']([^"\']+)["\']')


async def fetch_csrf_token(client, path: str = "/") -> str:
    """GET `path` and return the csrf_token embedded in the response form.

    The AsyncClient must be configured with `cookies` enabled (default) so the
    session cookie carrying this token rides on the subsequent POST.
    """
    resp = await client.get(path)
    match = _CSRF_INPUT_RE.search(resp.text)
    if not match:
        raise AssertionError(
            f"No csrf_token input found in GET {path} response. "
            f"Status={resp.status_code}, body_head={resp.text[:200]!r}"
        )
    return match.group(1)


async def csrf_post(client, path: str, data: dict, *, csrf_path: str | None = None, **kwargs):
    """POST `data` to `path` after fetching a CSRF token via `csrf_path` (defaults to `path`)."""
    token = await fetch_csrf_token(client, csrf_path or path)
    return await client.post(path, data={**data, "csrf_token": token}, **kwargs)

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


# ── In-memory DB + module monkeypatch ────────────────────────
# `db_session` returns the SQLite sessionmaker after rewriting every
# `from ... import async_session` import in the app to point at it. The
# old per-test fixtures (mock_db_for_auth, mock_db_for_pages) replicate
# this manually; new tests should depend on `db_session` instead.

_ASYNC_SESSION_CONSUMERS = (
    "app.infrastructure.persistence.database.async_session",
    "app.features.async_session",
    "app.web.routes.auth.async_session",
    "app.web.routes.payments.async_session",
    "app.web.routes.landing.async_session",
    "app.web.routes.account.async_session",
    "app.web.routes.admin.async_session",
    "app.web.routes.invitations.async_session",
    "app.web.routes.onboarding.async_session",
    "app.web.routes.profile.async_session",
    "app.web.routes.my_cvs.async_session",
    "app.web.routes.builder.async_session",
    "app.web.routes.wizard.async_session",
    "app.web.routes.cv.async_session",
    "app.identity.adapters.fastapi_deps.async_session",
)


@pytest.fixture
async def db_session(monkeypatch, tmp_path):
    """SQLite-backed sessionmaker, swapped in for every `async_session` consumer."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    db_path = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
    sm = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    for target in _ASYNC_SESSION_CONSUMERS:
        try:
            monkeypatch.setattr(target, sm)
        except AttributeError:
            # Module may not import async_session at the top level; skip silently.
            pass

    # File-backed stores that some routes touch.
    monkeypatch.setattr("app.infrastructure.persistence.attempt_store.ATTEMPTS_DIR", tmp_path / "attempts")
    monkeypatch.setattr("app.cv_generation.adapters.generation_log.LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr("app.cv_generation.adapters.generation_log.LOG_FILE", tmp_path / "logs" / "gen.jsonl")

    from app.infrastructure.persistence.database import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Reset feature-flag cache so prior tests don't leak overrides into this one.
    try:
        from app import features as _features
        _features._cache.clear()
    except Exception:
        pass

    yield sm
    await engine.dispose()

    # And clear again on teardown for tests that don't depend on db_session.
    try:
        from app import features as _features
        _features._cache.clear()
    except Exception:
        pass


# ── Feature flag overrides ───────────────────────────────────


@pytest.fixture
def feature_flags():
    """Context manager that patches the in-memory flag cache for one test.

    Usage:
        async def test_eoi_branch(feature_flags):
            with feature_flags(open_signups=False):
                ...
    """
    from contextlib import contextmanager

    @contextmanager
    def _override(**overrides):
        from app import features as features_mod
        original = dict(features_mod._cache)
        features_mod._cache.update(overrides)
        try:
            yield
        finally:
            features_mod._cache.clear()
            features_mod._cache.update(original)

    return _override
