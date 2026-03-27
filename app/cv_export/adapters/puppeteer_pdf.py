"""Generate PDF from rendered CV HTML using Puppeteer."""

import asyncio
import logging
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
GENERATE_SCRIPT = PROJECT_ROOT / "generate_pdf.js"

# Minimal HTML wrapper so the CV renders standalone with proper encoding
_HTML_WRAPPER = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
        @page {{ margin: 1.5cm; }}
    </style>
</head>
<body>
{content}
</body>
</html>"""


async def generate_pdf(rendered_html: str) -> bytes | None:
    """Convert rendered CV HTML to PDF bytes.

    Returns PDF bytes on success, None on failure.
    """
    html_file = None
    pdf_file = None
    try:
        # Write HTML to temp file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", delete=False, encoding="utf-8"
        ) as f:
            f.write(_HTML_WRAPPER.format(content=rendered_html))
            html_file = Path(f.name)

        pdf_file = html_file.with_suffix(".pdf")

        proc = await asyncio.create_subprocess_exec(
            "node", str(GENERATE_SCRIPT), str(html_file), str(pdf_file),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        _stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)

        if proc.returncode != 0:
            logger.error("PDF generation failed: %s", stderr.decode())
            return None

        if not pdf_file.exists():
            logger.error("PDF file not created")
            return None

        return pdf_file.read_bytes()

    except TimeoutError:
        logger.error("PDF generation timed out")
        return None
    except Exception:
        logger.exception("PDF generation error")
        return None
    finally:
        if html_file and html_file.exists():
            html_file.unlink(missing_ok=True)
        if pdf_file and pdf_file.exists():
            pdf_file.unlink(missing_ok=True)
