"""Scoring domain entities — pure Python, no framework dependencies."""

from dataclasses import dataclass, field


@dataclass
class ATSResult:
    score: int = 0
    keyword_match_pct: int = 0
    matched_keywords: list[str] = field(default_factory=list)
    missing_keywords: list[str] = field(default_factory=list)
    formatting_issues: list[str] = field(default_factory=list)
    section_checks: dict[str, bool] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
