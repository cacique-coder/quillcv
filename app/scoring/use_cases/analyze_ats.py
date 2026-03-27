"""Scoring use case — ATS analysis.

Thin wrapper that re-exports the main analysis function and result type
from the keyword_matcher adapter.
"""

from app.scoring.adapters.keyword_matcher import (
    ATSResult,
    analyze_ats,
    extract_keywords,
)

__all__ = ["ATSResult", "analyze_ats", "extract_keywords"]
