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

## Design System (post-Phase-G)

Canonical CSS load order in `app/templates/base.html`:

```
tokens.css → base.css → components.css → app-ui.css → wizard.css → marketing.css → style.css
                                                                                  → shell.css (only when body_layout='app')
landing.css                                                                       (only when included via head_extra)
```

- **`app/static/design/`** holds upstream-bundle files verbatim (`tokens.css`, `base.css`, `landing.css`, `shell.css`, `icons.js`). Treat as read-only reference; don't hand-edit.
- **`app/static/tokens.css`** is the canonical token file (warm cream palette, dark via `[data-theme="dark"]`). Legacy aliases at the bottom (`--bg → --paper`, etc.) — do not introduce new uses; they get deleted once consumers migrate.
- **Buttons**: single-dash naming. Use `.btn-primary / .btn-accent / .btn-ghost / .btn-secondary / .btn-sm / .btn-lg / .btn-full / .btn-disabled`. Never `.btn--*` BEM in templates.
- **Layouts**: `{% block body_layout %}app{% endblock %}` opts an authenticated page into the sidebar+topbar shell. Default is `marketing` (header + footer).
- **Component library**: `app/templates/macros/components.html` (small composables) + `app/templates/partials/components/*.html` (full sections). See `docs/DESIGN_SYSTEM.md` for the catalog.
- **Out of scope**: `app/templates/cv_templates/**`, `app/templates/cover_letter_templates/**`, `app/templates/emails/**` — these stay on inline styles for the print/email pipeline.

When extending the look: shared classes first (`components.css`); only fall back to a page-scoped `<style>` block if a pattern is genuinely one-off.
