# QuillCV

ATS-optimized CV builder that tailors CVs to specific job descriptions with region-specific formatting for 12 countries.

## What it does

1. Parses your existing CV (PDF, DOCX, or plain text)
2. Analyzes the target job description for keywords and requirements
3. Searches for similar-profile CVs online as reference
4. Generates an ATS-optimized CV tailored to the role
5. Provides ATS scoring, keyword gap analysis, and recommendations

Supports region-specific formats for AU, US, UK, CA, NZ, DE, FR, NL, IN, BR, AE, and JP — each with appropriate conventions for photos, personal details, references, and page length.

## Tech stack

- **Backend**: Python 3.14, FastAPI, Jinja2
- **Frontend**: HTMX + server-rendered HTML
- **AI**: Multi-provider LLM abstraction (Anthropic, OpenAI, Gemini, Claude Code CLI)
- **CV parsing**: pdfplumber (PDF), python-docx (DOCX)
- **Photo storage**: Local + Cloudflare R2
- **PDF generation**: Puppeteer
- **Database**: PostgreSQL (Docker) + SQLAlchemy async
- **Payments**: Stripe
- **Dev orchestration**: mise + honcho (Procfile.dev)

## Setup

### Prerequisites

- [mise](https://mise.jdx.dev/) — pins Python 3.14, runs the dev tasks
- Docker + Docker Compose — runs Postgres for dev
- Node.js — only needed for PDF generation (Puppeteer); usually picked up by your system or installed via mise
- (Optional) [`claude` CLI](https://github.com/anthropics/claude-code) on `$PATH` if you want `LLM_PROVIDER=claude-code` (no API spend in dev)

### One-time install

```bash
mise install              # provisions Python 3.14 from mise.toml
mise run install          # pip install -r requirements.txt (incl. honcho)
npm install               # Node deps for PDF generation
cp .env.example .env      # then edit .env — see below
```

### Environment variables

`.env.example` is the source of truth; copy it to `.env` and fill in
what you need. The key knob is `LLM_PROVIDER`:

| `LLM_PROVIDER` | Heavy model | Light model | Requires |
|---|---|---|---|
| `anthropic` | claude-sonnet-4 | claude-haiku-4-5 | `ANTHROPIC_API_KEY` |
| `openai`    | gpt-5           | gpt-4o-mini      | `OPENAI_API_KEY` |
| `gemini`    | gemini-2.5-pro  | gemini-2.5-flash-lite | `GOOGLE_API_KEY` |
| `claude-code` | sonnet (CLI)  | haiku (CLI)      | `claude` on PATH (uses your Claude subscription) |

If `LLM_PROVIDER` is unset and no `*_API_KEY` is in the environment,
the app auto-falls-back to `claude-code`. The startup log prints the
final selection: `LLM[heavy]: provider=… model=… | LLM_PROVIDER=…`.
You can also `curl localhost:8000/up` to see what's wired.

Other variables (Cloudflare R2 for photo persistence, Stripe keys for
payments) are optional and documented in `.env.example`.

### Run — development

The day-to-day flow is foreman-style: Postgres in Docker, uvicorn on
the host (so the host's `claude` CLI, debuggers, and reload all work
natively).

```bash
mise run dev              # honcho boots: db (docker) + web (uvicorn). Ctrl-C stops both.
```

Useful sub-tasks:

```bash
mise run dev:db           # only Postgres (foreground)
mise run dev:web          # only uvicorn (assumes db up)
mise run dev:docker       # full in-container stack (legacy mode)
```

After `mise run dev`, the app is at <http://localhost:8000>.

### Run — production

```bash
gunicorn app.main:app -c gunicorn.conf.py
```

## Quality checks

```bash
mise run lint          # Ruff linter
mise run security      # Bandit security scanner
mise run audit         # pip-audit for known CVEs
mise run test          # Pytest with coverage
mise run check         # All of the above
```

## CV templates

46 ATS-optimized HTML/CSS templates covering general-purpose designs (classic, modern, minimal, executive, tech, compact) and specialized formats (academic, federal, consulting, healthcare, legal, creative, and region-specific like europass, lebenslauf, rirekisho, curriculo).
