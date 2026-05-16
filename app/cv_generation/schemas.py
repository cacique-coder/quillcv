"""Pydantic schemas for LLM responses.

These validate the JSON the LLM is asked to return at every call site. They
exist alongside `app/cv_generation/entities.py` (plain dataclasses) — the
dataclasses remain the canonical domain types consumed by the renderer; the
schemas are an edge-of-system validation layer. Callers typically do
`schema.model_dump()` and feed the result into the existing builder logic.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, RootModel

# ── CV ────────────────────────────────────────────────────────


class ExperienceSchema(BaseModel):
    """One job entry on the CV. All fields are optional — the prompt may omit any of them."""

    model_config = ConfigDict(extra="allow")

    title: str = ""
    company: str = ""
    date: str = ""
    location: str = ""
    tech: str = ""
    bullets: list[str] = Field(default_factory=list)


class EducationSchema(BaseModel):
    model_config = ConfigDict(extra="allow")

    degree: str = ""
    institution: str = ""
    date: str = ""


class SkillGroupSchema(BaseModel):
    model_config = ConfigDict(extra="allow")

    category: str = ""
    items: list[str] = Field(default_factory=list)


class ProjectSchema(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = ""
    description: str = ""
    url: str = ""
    tech: list[str] = Field(default_factory=list)


class ReferenceSchema(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = ""
    title: str = ""
    company: str = ""
    email: str = ""
    phone: str = ""


class CVDataSchema(BaseModel):
    """Tailored CV payload returned by the generator.

    ``extra="allow"`` because the prompt dynamically appends extra sections
    (publications, talks, awards, languages, etc.) depending on the source
    CV. They are validated loosely as either lists of strings or strings.
    """

    model_config = ConfigDict(extra="allow")

    name: str = ""
    title: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin: str = ""
    github: str = ""
    portfolio: str = ""
    summary: str = ""
    experience: list[ExperienceSchema] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    skills_grouped: list[SkillGroupSchema] = Field(default_factory=list)
    education: list[EducationSchema] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    projects: list[ProjectSchema] = Field(default_factory=list)
    references: list[ReferenceSchema] = Field(default_factory=list)


# ── Cover letter ──────────────────────────────────────────────


class CoverLetterSchema(BaseModel):
    """Cover letter payload. The ``_analysis`` debug field is ignored on parse."""

    model_config = ConfigDict(extra="ignore")

    recipient: str = "Hiring Manager"
    company_name: str = ""
    date: str = ""
    salutation: str = "Dear Hiring Manager,"
    opening: str = ""
    body_paragraphs: list[str] = Field(default_factory=list)
    contribution: str = ""
    closing: str = ""
    sign_off: str = "Kind regards,"
    name: str = ""


# ── Keywords ──────────────────────────────────────────────────


class KeywordCategoriesSchema(RootModel[dict[str, list[str]]]):
    """LLM keyword extraction returns ``{ category: [keywords] }``."""


class KeywordCategorizationSchema(RootModel[dict[str, str]]):
    """``categorize_missing_keywords`` returns ``{ keyword: category }``."""


# ── Quality review ────────────────────────────────────────────


class QualityFlagSchema(BaseModel):
    model_config = ConfigDict(extra="allow")

    item: str = ""
    section: str = ""
    category: str = ""  # certification|skill|experience|personal_info|phrasing|other
    severity: str = ""  # remove|improve
    reason: str = ""
    suggestion: str = ""


class QualityReviewSchema(BaseModel):
    model_config = ConfigDict(extra="allow")

    flags: list[QualityFlagSchema] = Field(default_factory=list)
    summary: str = ""


# ── Template recommendation (wizard) ──────────────────────────


class TemplateRecommendationSchema(BaseModel):
    """Returned by the AI template-recommender on wizard step 3."""

    model_config = ConfigDict(extra="allow")

    recommended: list[str] = Field(default_factory=list)
    reason: str = ""
