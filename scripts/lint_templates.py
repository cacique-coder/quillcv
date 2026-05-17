#!/usr/bin/env python3
"""
lint_templates.py — QuillCV template lint.

Walks app/templates/**/*.html and flags raw HTML tags that should be rendered
via macros in app/templates/macros/ui.html instead. Keeps the codebase
honest about the "components are macros, not inline patterns" convention.

USAGE
    python scripts/lint_templates.py

EXIT CODES
    0 — no FAIL violations (warnings allowed)
    1 — at least one FAIL violation

HOW TO ADD A NEW RULE
    Add an entry to RULES below. Each rule is a tuple:
        (severity, name, compiled_regex, hint)
    where severity is "FAIL" or "WARN". The regex is searched per-line.
    Hint is a short string telling the dev what macro to use instead.

EXCLUDED DIRECTORIES / FILES
    See EXCLUDED_PARTS below. These paths are intentionally allowed to use
    raw HTML (macro source, the catalogue itself, print/email templates).

DEPENDENCIES
    stdlib only — re, pathlib, sys.
"""

import re
import sys
from pathlib import Path

# ── Configuration ──────────────────────────────────────────────────────────

# Paths (relative to the repo root) whose contents are exempt from linting.
# Keep this list short and well-justified.
EXCLUDED_PARTS = (
    "app/templates/macros",                  # macro source — defines the canonical markup
    "app/templates/dev/components.html",     # catalogue intentionally shows raw markup
    "app/templates/cv_templates",            # print-rendered CVs, inline styles by design
    "app/templates/cover_letter_templates",  # same rationale as CV templates
    "app/templates/emails",                  # email HTML, inline styles by design
)

TEMPLATE_ROOT = Path("app/templates")

# Severity, rule name, regex, suggested macro / fix hint.
RULES = (
    ("FAIL", "raw-textarea",
     re.compile(r"<textarea\b"),
     "use text_area() macro"),
    ("FAIL", "raw-text-input",
     re.compile(r'<input\s+type="text"'),
     "use text_input() macro"),
    ("FAIL", "raw-email-input",
     re.compile(r'<input\s+type="email"'),
     'use text_input(type="email") macro'),
    ("FAIL", "raw-tel-input",
     re.compile(r'<input\s+type="tel"'),
     "use phone_input() macro"),
    ("FAIL", "raw-file-input",
     re.compile(r'<input\s+type="file"'),
     "use file_input() macro"),
    ("FAIL", "raw-select",
     # Match `<select` followed by whitespace or `>` — avoids matching tag
     # names that merely start with "select" (none exist today, but be safe).
     re.compile(r"<select(?=[\s>])"),
     "use select_input() macro"),
    ("WARN", "raw-btn",
     # Raw <button> using the project btn class. No button-rendering macro
     # exists yet, so this is a warning. Promote to FAIL once a macro lands.
     re.compile(r'<button\s+[^>]*class="btn\b'),
     "consider a button macro (none exists yet — wired as WARN for now)"),
)

# ── Implementation ─────────────────────────────────────────────────────────


def is_excluded(path: Path) -> bool:
    posix = path.as_posix()
    return any(
        posix == ex or posix.startswith(ex.rstrip("/") + "/")
        for ex in EXCLUDED_PARTS
    )


def scan_file(path: Path):
    """Yield (severity, rule_name, line_no, col_no, hint, snippet) tuples."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return
    for lineno, line in enumerate(text.splitlines(), start=1):
        for severity, name, rx, hint in RULES:
            for m in rx.finditer(line):
                col = m.start() + 1
                snippet = line.strip()[:80]
                yield (severity, name, lineno, col, hint, snippet)


def main() -> int:
    if not TEMPLATE_ROOT.is_dir():
        print(f"lint_templates: template root not found: {TEMPLATE_ROOT}",
              file=sys.stderr)
        return 2

    files = sorted(TEMPLATE_ROOT.rglob("*.html"))
    scanned = 0
    fails = 0
    warns = 0

    for f in files:
        if is_excluded(f):
            continue
        scanned += 1
        for severity, name, lineno, col, hint, snippet in scan_file(f):
            if severity == "FAIL":
                fails += 1
            else:
                warns += 1
            print(f"{severity}: {f}:{lineno}:{col}: [{name}] {snippet}")
            print(f"       hint: {hint}")

    print()
    print(
        f"lint_templates: {scanned} files scanned, "
        f"{fails} fails, {warns} warnings"
    )
    if fails:
        print(
            "lint_templates: --fix=NONE — see app/templates/macros/ui.html "
            "for the canonical macros to use instead."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
