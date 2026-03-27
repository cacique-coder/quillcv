"""PII domain entities — pure Python, no framework dependencies."""

from dataclasses import dataclass, field


@dataclass
class ReferenceContact:
    name: str = ""
    email: str = ""
    phone: str = ""


@dataclass
class PIIProfile:
    """PII associated with a candidate's CV submission."""

    full_name: str
    dob: str = ""
    document_id: str = ""
    linkedin_url: str = ""
    github_url: str = ""
    references: list[ReferenceContact] = field(default_factory=list)
