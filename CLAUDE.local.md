# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

**QuillCV** (quillcv.com) — ATS-optimized CV builder that:
- Parses job descriptions and the user's existing CV
- Searches for similar-profile CVs online as reference/inspiration
- Generates ATS-optimized CVs tailored to specific job descriptions
- Produces region-specific formats for 12 countries (AU, US, UK, CA, NZ, DE, FR, NL, IN, BR, AE, JP)
- Provides ATS scoring, checklist, missing keywords, and recommendations

## Key Concepts

- **ATS optimization**: Output CVs must be structured for Applicant Tracking Systems — clean formatting, keyword matching from job descriptions, standard section headings.
- **Region variants**: Each country has different CV conventions (photo requirements, personal details, references, date formats, page length). See `docs/cv-format-sources.md` for references.
- **Job description parsing**: Extract key skills, requirements, and keywords from job postings to inform CV tailoring.
- **CV parsing**: Extract experience, skills, and achievements from the user's source CV.
- **Similar CV search**: Find publicly available CVs with matching profiles online for structure and content inspiration.

## Business Model

- **Alpha pricing**: $29 for 50 CV generations (credit-based)
- **First 100 users** — alpha founders cohort
- **Post-alpha**: subscription model ($15-29/mo) with monthly generation caps
- **Extra credits**: ~$0.50-1 per generation after credits run out
- **Estimated cost per generation**: $0.10-0.25 (API + scraping)

## Tech Stack

- **Backend**: Python, FastAPI, Jinja2
- **Frontend**: HTMX + server-rendered HTML (no SPA framework)
- **AI**: Claude API (Anthropic SDK) for CV generation
- **CV parsing**: pdfplumber (PDF), python-docx (DOCX), plain text
- **Photo storage**: Local temp + Cloudflare R2 (boto3 S3-compatible)
- **PDF generation**: Puppeteer (existing Node.js script)
- **Templates**: 6 ATS-optimized designs (classic, modern, minimal, executive, tech, compact)

## Project Structure

```
app/
├── main.py                          # FastAPI app entry point
├── routers/
│   ├── cv.py                        # /analyze endpoint
│   ├── demo.py                      # /demo/{country}/{template} previews
│   └── photos.py                    # /photos/upload, /photos/serve
├── services/
│   ├── cv_parser.py                 # PDF, DOCX, TXT parsing
│   ├── ats_analyzer.py              # Keyword matching, scoring, checklist
│   ├── ai_generator.py              # Claude API for CV generation
│   ├── template_registry.py         # Templates + 12 country configs
│   ├── demo_data.py                 # Sample data per region for demos
│   └── storage.py                   # Local + Cloudflare R2 photo storage
├── templates/
│   ├── base.html                    # Layout with HTMX
│   ├── index.html                   # Main form
│   ├── demo_index.html              # Browse all countries
│   ├── demo_country.html            # Country detail + template list
│   ├── demo_preview.html            # Full template preview
│   ├── cv_templates/                # 6 HTML/CSS CV templates
│   └── partials/                    # HTMX fragments
├── static/style.css
└── uploads/                         # Local temp photo storage ({user_id}/photos/)
docs/
└── cv-format-sources.md             # Reference links per country
```

## Environment Variables

```bash
ANTHROPIC_API_KEY=...          # Required for AI CV generation
R2_ENDPOINT_URL=...            # Cloudflare R2 (optional, for photo persistence)
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_BUCKET=...
```

## User Profile

- Strong Ruby on Rails background
- Open to Python, Go, or C# — leveraging AI to learn new language idioms
- Targeting roles in AU and US markets
