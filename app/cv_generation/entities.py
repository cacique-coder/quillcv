"""CV generation domain entities — pure Python, no framework dependencies."""

from dataclasses import dataclass, field


@dataclass
class Experience:
    title: str
    company: str
    date: str
    location: str = ""
    tech: str = ""
    bullets: list[str] = field(default_factory=list)


@dataclass
class Education:
    degree: str
    institution: str
    date: str = ""


@dataclass
class SkillGroup:
    category: str
    items: list[str] = field(default_factory=list)


@dataclass
class Project:
    name: str
    description: str = ""
    url: str = ""
    tech: list[str] = field(default_factory=list)


@dataclass
class Reference:
    name: str
    title: str = ""
    company: str = ""
    email: str = ""
    phone: str = ""


@dataclass
class CVData:
    name: str = ""
    title: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin: str = ""
    github: str = ""
    portfolio: str = ""
    summary: str = ""
    experience: list[Experience] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    skills_grouped: list[SkillGroup] = field(default_factory=list)
    education: list[Education] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)
    projects: list[Project] = field(default_factory=list)
    references: list[Reference] = field(default_factory=list)
