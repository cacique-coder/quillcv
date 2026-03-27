"""LLM-powered keyword extraction from job descriptions.

Replaces regex heuristics with a single Claude call that understands
job description structure and returns categorized, CV-relevant keywords.
"""
import json
import logging

from app.infrastructure.llm.client import LLMClient, set_llm_context

logger = logging.getLogger(__name__)

_EXTRACTION_PROMPT = """\
You are an ATS (Applicant Tracking System) keyword analyst. Given a job description, \
extract ONLY the keywords and phrases that a candidate should include in their CV to \
pass ATS screening.

Rules:
- Extract terms a candidate can truthfully claim on a CV
- Skip company names, product names, and internal jargon
- Skip EEO boilerplate, benefits, salary, and legal text
- Skip generic filler ("team player", "passionate", "excited")
- Use lowercase unless it's an acronym or proper tech name
- Each keyword should be 1-3 words, as it would appear on a CV
- Prefer the specific term used in the posting (e.g., "React Native" not just "React")

Output ONLY valid JSON, no markdown fences, no explanation:
{{
  "technical_skills": ["Python", "Node.js", "CI/CD", "AWS"],
  "tools_platforms": ["Sentry", "Jira", "Datadog"],
  "professional_skills": ["solutions engineering", "post-sales", "onboarding"],
  "soft_skills": ["presentation skills", "problem solving", "cross-functional collaboration"],
  "domain_knowledge": ["error monitoring", "software development lifecycle", "open-source"],
  "certifications": ["AWS Certified", "PMP"]
}}

Only include categories that have relevant keywords. Empty categories should be omitted.

===JOB DESCRIPTION===
{job_description}
===END JOB DESCRIPTION==="""


async def extract_keywords_llm(
    job_description: str,
    llm: LLMClient,
) -> dict:
    """Extract categorized keywords from a job description using an LLM.

    Returns a dict with:
      - "categories": dict of category_name -> list of keywords
      - "all_keywords": flat list of all keywords (lowercased for matching)
      - "llm_usage": token/cost metadata from the extraction call
    """
    set_llm_context(service="keyword_extractor", inherit=True)
    prompt = _EXTRACTION_PROMPT.format(job_description=job_description[:6000])

    try:
        result = await llm.generate(prompt)
        raw = result.text.strip()

        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            if "```" in raw:
                raw = raw[:raw.rfind("```")]
            raw = raw.strip()

        categories = json.loads(raw)

        # Build flat keyword list for ATS matching
        all_keywords = []
        seen = set()
        for _category, keywords in categories.items():
            if not isinstance(keywords, list):
                continue
            for kw in keywords:
                kw_lower = kw.lower().strip()
                if kw_lower and kw_lower not in seen:
                    seen.add(kw_lower)
                    all_keywords.append(kw_lower)

        return {
            "categories": categories,
            "all_keywords": all_keywords,
            "llm_usage": {
                "model": result.model,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "cost_usd": result.cost_usd,
            },
        }
    except Exception:
        logger.exception("LLM keyword extraction failed")
        return None
