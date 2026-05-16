"""Tests for LLM-powered keyword extraction."""

import json

import pytest

from app.cv_generation.adapters.keyword_llm import extract_keywords_llm


@pytest.mark.asyncio
class TestExtractKeywordsLLM:

    async def test_successful_extraction(self, mock_llm, sample_job_description):
        response = json.dumps({
            "technical_skills": ["Python", "Go"],
            "tools_platforms": ["Docker", "Kubernetes"],
            "professional_skills": ["system design"],
            "soft_skills": ["communication"],
            "domain_knowledge": ["distributed systems"],
            "certifications": ["AWS"],
        })
        llm = mock_llm(response)
        result = await extract_keywords_llm(sample_job_description, llm)

        assert result is not None
        assert "categories" in result
        assert "all_keywords" in result
        assert "python" in result["all_keywords"]
        assert "docker" in result["all_keywords"]

    async def test_returns_none_on_failure(self, mock_llm, sample_job_description):
        llm = mock_llm("not json")
        result = await extract_keywords_llm(sample_job_description, llm)
        assert result is None

    async def test_categories_preserved(self, mock_llm, sample_job_description):
        response = json.dumps({
            "technical_skills": ["Python"],
            "tools_platforms": ["AWS"],
            "professional_skills": [],
            "soft_skills": [],
            "domain_knowledge": [],
            "certifications": [],
        })
        llm = mock_llm(response)
        result = await extract_keywords_llm(sample_job_description, llm)

        assert result is not None
        assert "Python" in result["categories"]["technical_skills"]
        assert "AWS" in result["categories"]["tools_platforms"]

    async def test_all_keywords_lowercased(self, mock_llm, sample_job_description):
        response = json.dumps({
            "technical_skills": ["Python", "GO"],
            "tools_platforms": [],
            "professional_skills": [],
            "soft_skills": [],
            "domain_knowledge": [],
            "certifications": [],
        })
        llm = mock_llm(response)
        result = await extract_keywords_llm(sample_job_description, llm)

        assert result is not None
        for kw in result["all_keywords"]:
            assert kw == kw.lower(), f"Keyword not lowercased: {kw}"
