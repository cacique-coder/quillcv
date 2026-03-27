"""Builder domain entities and data structures.

Defines the canonical CV data schema used by the manual builder.
"""

# Canonical set of fields that make up a CV in the builder domain.
# Any field added here must also be handled in cv_data_from_attempt().
CV_DATA_FIELDS = (
    "name",
    "title",
    "email",
    "phone",
    "location",
    "linkedin",
    "github",
    "portfolio",
    "summary",
    "experience",
    "skills",
    "skills_grouped",
    "education",
    "certifications",
    "projects",
    "references",
    "languages",
    # Region-specific fields
    "dob",
    "nationality",
    "marital_status",
    "visa_status",
    "region",
    "photo_url",
)

# PII vault key -> builder cv_data key mapping used when pre-filling the form
# from the user's stored profile.
PII_TO_CV_FIELD_MAP: dict[str, str] = {
    "full_name": "name",
    "email": "email",
    "phone": "phone",
    "dob": "dob",
    "nationality": "nationality",
    "marital_status": "marital_status",
    "location": "location",
    "linkedin": "linkedin",
    "github": "github",
    "portfolio": "portfolio",
}

# cv_data key -> PII vault key mapping used when back-filling the vault from
# a saved CV (the inverse of the subset of PII_TO_CV_FIELD_MAP that excludes
# PII-only fields like dob/nationality/marital_status).
CV_TO_PII_BACKFILL_MAP: dict[str, str] = {
    "phone": "phone",
    "email": "email",
    "location": "location",
    "linkedin": "linkedin",
    "github": "github",
    "portfolio": "portfolio",
}

# PII placeholder tokens used when storing CVs — replaced on load with real values.
PII_TOKEN_MAP_KEYS = (
    "<<CANDIDATE_NAME>>",
    "<<EMAIL_1>>",
    "<<PHONE_1>>",
    "<<DOB>>",
    "<<DOCUMENT_ID>>",
    "<<LINKEDIN_URL>>",
    "<<GITHUB_URL>>",
    "<<PORTFOLIO_URL>>",
    "<<CANDIDATE_SLUG>>",
)
