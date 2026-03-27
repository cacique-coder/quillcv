import re

from app.scoring.entities import ATSResult

# Common ATS-expected section headings
EXPECTED_SECTIONS = [
    "summary",
    "experience",
    "education",
    "skills",
]

# Words/patterns that often appear in job descriptions as key requirements
NOISE_WORDS = {
    # Determiners, pronouns, prepositions, conjunctions
    "the", "and", "or", "a", "an", "in", "on", "at", "to", "for", "of",
    "with", "is", "are", "was", "were", "be", "been", "being", "have",
    "has", "had", "do", "does", "did", "will", "would", "could", "should",
    "may", "might", "shall", "can", "need", "must", "we", "you", "our",
    "your", "this", "that", "it", "as", "by", "from", "not", "but",
    "about", "into", "through", "during", "before", "after", "above",
    "below", "between", "up", "down", "out", "off", "over", "under",
    "again", "further", "then", "once", "here", "there", "when", "where",
    "why", "how", "all", "each", "every", "both", "few", "more", "most",
    "other", "some", "such", "no", "nor", "only", "own", "same", "so",
    "than", "too", "very", "just", "also", "able", "work", "working",
    "role", "team", "including", "across", "well", "within", "using",
    "experience", "opportunity", "join", "looking", "ideal", "candidate",
    "strong", "excellent", "good", "great", "minimum", "required",
    "preferred", "plus", "bonus", "years", "year",
    # Common job-ad filler — not CV-relevant
    "job", "company", "companies", "organization", "organizations",
    "believe", "believes", "bad", "tired", "mission", "help", "helps",
    "write", "writes", "better", "faster", "back", "get", "gets",
    "enjoying", "enjoy", "build", "building", "built", "like",
    "something", "everything", "everywhere", "next", "generation",
    "things", "thing", "make", "makes", "making", "made",
    "want", "wants", "find", "finds", "take", "takes", "give", "gives",
    "come", "run", "see", "set", "new", "first", "last", "long",
    "high", "part", "know", "day", "way", "who", "what", "which",
    "their", "them", "they", "its", "etc", "per", "via",
    "million", "billion", "funding", "founded",
    # Job-posting boilerplate
    "legally", "protected", "equal", "employer", "employment",
    "regardless", "race", "gender", "age", "disability", "veteran",
    "status", "sexual", "orientation", "national", "origin",
    "accommodation", "applicant", "applicants", "apply", "application",
    "salary", "range", "base", "compensation", "benefits", "equity",
    "offer", "offers", "offered", "pay", "paid",
    # More generic filler
    "those", "order", "employees", "candidates", "accessible",
    "accommodations", "includes", "ground", "scratch", "error",
    "closely", "internally", "objectives", "content", "region",
    "regional", "providing", "opportunities", "support",
}

# Words that only matter as part of multi-word phrases, not standalone
WEAK_STANDALONE = {
    "model", "level", "office", "post", "scale", "large", "real",
    "world", "open", "source", "subject", "matter", "fast", "paced",
    "hands", "results", "driven", "cross", "value", "sales",
    "delivered", "consumable", "collateral", "documents", "provision",
    "acting", "broader", "align", "improving", "require",
    "function", "partner", "use", "best",
    "practices", "provide", "leaders", "react",
    "implementation", "implementations",
    # Filler words in bigrams
    "primary", "focus", "term", "helping", "define", "globally",
    "recognized", "clear", "path", "demonstrate", "specific",
    "different", "love", "flexing", "life", "cycle",
    "understand", "successfully", "dedicated",
}


def _strip_boilerplate(text: str) -> str:
    """Remove non-relevant sections from a job description.

    Strips: company intro/marketing, EEO/diversity statements, privacy/legal,
    salary/benefits, and application instructions. Keeps: role description,
    responsibilities, qualifications, requirements, and nice-to-haves.
    """
    text_lower = text.lower()

    # Cut everything after EEO / legal / privacy sections
    eeo_markers = [
        "equal opportunity", "equal employment", "we are committed to",
        "committed to providing equal", "regardless of race",
        "applicant privacy", "privacy policy", "handles applicant data",
        "if you need assistance or an accommodation",
        "reasonable accommodation",
    ]
    for marker in eeo_markers:
        idx = text_lower.find(marker)
        if idx > 0:
            text = text[:idx]
            text_lower = text.lower()
            break

    # Cut company intro/marketing before the role description starts
    role_markers = [
        "about the role", "about this role", "the role",
        "what you'll do", "what you will do", "in this role",
        "responsibilities", "your responsibilities",
        "job description", "role overview", "position overview",
        "key responsibilities", "what we're looking for",
    ]
    for marker in role_markers:
        idx = text_lower.find(marker)
        if idx > 0 and idx < len(text) // 2:
            text = text[idx:]
            break

    return text.strip()


def extract_keywords(text: str) -> list[str]:
    """Extract meaningful keywords/phrases from job description.

    Focuses on skills, technologies, and professional competencies.
    Filters out company descriptions, boilerplate, and generic words.
    """
    # Strip irrelevant sections first
    text = _strip_boilerplate(text)
    text_lower = text.lower()

    # Detect likely company/product names (capitalized words mid-sentence)
    company_words = set()
    for match in re.finditer(r'(?<=[a-z]\s)([A-Z][a-z]{2,})', text):
        company_words.add(match.group(1).lower())

    # 1. Extract multi-word technical terms (e.g., "CI/CD", "Node.js")
    tech_patterns = re.findall(
        r'\b[a-zA-Z][a-zA-Z0-9]*(?:[/.+#-][a-zA-Z0-9]+)+\b', text
    )

    # 2. Extract bigram skill phrases (e.g., "error monitoring", "customer success")
    bigrams = re.findall(r'\b([a-zA-Z]{3,})\s+([a-zA-Z]{3,})\b', text_lower)

    # 3. Extract individual words
    words = re.findall(r'\b[a-zA-Z]{2,}\b', text_lower)

    all_noise = NOISE_WORDS | WEAK_STANDALONE

    # Count word frequency — words that repeat are more likely to be important
    word_freq: dict[str, int] = {}
    for w in words:
        if w not in all_noise:
            word_freq[w] = word_freq.get(w, 0) + 1

    keywords = []
    seen = set()

    # Add tech patterns first (highest priority)
    for term in tech_patterns:
        term_lower = term.lower()
        # Skip domains/URLs
        if re.search(r'\.(com|io|ai|org|net|co|edu|gov)\b', term_lower):
            continue
        # Skip common non-tech patterns that match due to slashes/hyphens
        if term_lower in ('and/or',):
            continue
        # Skip hyphenated non-tech terms (keep things like ci/cd, node.js, c#, c++)
        # but drop made-up compounds like "can-doer", "sales-consumable", "value-delivered"
        if '-' in term_lower:
            # Only keep well-known hyphenated tech/skill terms
            parts = term_lower.split('-')
            # If any part is a noise or weak word, skip the whole thing
            if any(p in all_noise for p in parts):
                continue
        if term_lower not in seen:
            seen.add(term_lower)
            keywords.append(term_lower)

    # Add meaningful bigrams — both words must be non-noise
    for w1, w2 in bigrams:
        phrase = f"{w1} {w2}"
        if phrase in seen:
            continue
        if w1 in all_noise or w2 in all_noise:
            continue
        if len(w1) <= 3 or len(w2) <= 3:
            continue
        if w1 == w2:
            continue
        # Skip bigrams containing detected company/product names
        if w1 in company_words or w2 in company_words:
            continue
        seen.add(phrase)
        seen.add(w1)
        seen.add(w2)
        keywords.append(phrase)

    # Add remaining individual words — only if they repeat (2+) and are meaningful
    for word in words:
        if word in all_noise or word in seen or len(word) <= 4:
            continue
        if word in company_words:
            continue
        freq = word_freq.get(word, 0)
        if freq >= 2:
            seen.add(word)
            keywords.append(word)

    return keywords


def analyze_ats(
    cv_text: str,
    job_description: str,
    keywords_override: list[str] | None = None,
) -> ATSResult:
    """Analyze CV against job description for ATS compatibility.

    If keywords_override is provided (e.g., from LLM extraction), uses those
    instead of the regex-based extract_keywords fallback.
    """
    result = ATSResult()
    cv_lower = cv_text.lower()

    # 1. Keyword matching
    job_keywords = keywords_override if keywords_override is not None else extract_keywords(job_description)
    for kw in job_keywords:
        if kw in cv_lower:
            result.matched_keywords.append(kw)
        else:
            result.missing_keywords.append(kw)

    total = len(job_keywords)
    if total > 0:
        result.keyword_match_pct = round(
            len(result.matched_keywords) / total * 100
        )

    # 2. Section checks
    for section in EXPECTED_SECTIONS:
        # Check for the section heading in the CV
        pattern = rf'\b{section}\b'
        result.section_checks[section] = bool(re.search(pattern, cv_lower))

    # 3. Formatting issues
    if re.search(r'[│┃┆┇┊┋╎╏║]', cv_text):
        result.formatting_issues.append(
            "CV contains table/box-drawing characters that ATS may not parse"
        )
    if re.search(r'[\u2022\u25CF\u25CB\u25A0\u25AA]', cv_text):
        result.formatting_issues.append(
            "Uses special bullet characters — prefer simple dashes or asterisks"
        )
    if len(cv_text.split('\n')) > 80:
        result.formatting_issues.append(
            "CV appears very long — consider keeping it to 2 pages max"
        )
    if not re.search(r'\b[\w.+-]+@[\w-]+\.[\w.]+\b', cv_text):
        result.formatting_issues.append(
            "No email address detected — ensure contact info is in plain text"
        )
    if not re.search(r'\b\d{3,4}[\s.-]?\d{3,4}[\s.-]?\d{3,4}\b', cv_text):
        result.formatting_issues.append(
            "No phone number detected — include a contact number"
        )

    # 4. Recommendations
    if result.keyword_match_pct < 40:
        result.recommendations.append(
            "Low keyword match — incorporate more terms from the job description"
        )
    if result.missing_keywords:
        # Only recommend genuinely useful missing keywords (skip short/generic ones)
        actionable_missing = [kw for kw in result.missing_keywords if len(kw) >= 4][:10]
        if actionable_missing:
            result.recommendations.append(
                f"Add missing keywords where truthful: {', '.join(actionable_missing)}"
            )
    for section, found in result.section_checks.items():
        if not found:
            result.recommendations.append(
                f"Add a '{section.title()}' section — ATS systems expect standard headings"
            )
    # Broader check for quantified achievements
    has_metrics = re.search(
        r'\d+%|\$[\d,]+|\d+\+?\s*(years|users|clients|projects|team|developers|engineers|companies|customers|members|people|applications|services|endpoints)',
        cv_lower,
    )
    if not has_metrics:
        result.recommendations.append(
            "Quantify achievements — add metrics, percentages, or numbers"
        )

    # 5. Overall score
    score = 0
    score += min(result.keyword_match_pct * 0.4, 40)  # Up to 40 pts
    sections_found = sum(result.section_checks.values())
    score += (sections_found / len(EXPECTED_SECTIONS)) * 30  # Up to 30 pts
    score += max(0, 20 - len(result.formatting_issues) * 5)  # Up to 20 pts
    score += max(0, 10 - len(result.recommendations) * 2)  # Up to 10 pts
    result.score = max(0, min(100, round(score)))

    return result
