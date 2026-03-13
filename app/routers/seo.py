"""SEO infrastructure routes: robots.txt and sitemap.xml."""

from datetime import date

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse, Response

from app.services.template_registry import list_regions, list_templates

router = APIRouter()

BASE_URL = "https://quillcv.com"

ROBOTS_TXT = """\
User-agent: *
Allow: /
Disallow: /app
Disallow: /wizard/
Disallow: /apply-fixes
Disallow: /download-pdf
Disallow: /checkout/
Disallow: /photos/
Disallow: /account
Disallow: /my-cvs
Disallow: /builder
Disallow: /admin

# AI Crawlers — allowed for discoverability
User-agent: GPTBot
Allow: /

User-agent: ChatGPT-User
Allow: /

User-agent: Google-Extended
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: ClaudeBot
Allow: /

# Block low-value scrapers
User-agent: CCBot
Disallow: /

User-agent: Bytespider
Disallow: /

Sitemap: https://quillcv.com/sitemap.xml
"""


@router.get("/robots.txt", include_in_schema=False)
async def robots_txt():
    """Serve robots.txt for web crawlers."""
    return PlainTextResponse(ROBOTS_TXT)


@router.get("/sitemap.xml", include_in_schema=False)
async def sitemap_xml():
    """Dynamically generate sitemap.xml listing all public pages."""
    today = date.today().isoformat()

    urls: list[str] = []

    # Static public pages
    static_pages = [
        ("/", "1.0", "weekly"),
        ("/pricing", "0.8", "monthly"),
        ("/demo", "0.9", "weekly"),
        ("/about", "0.5", "monthly"),
        ("/privacy", "0.3", "yearly"),
        ("/terms", "0.3", "yearly"),
    ]
    for path, priority, changefreq in static_pages:
        urls.append(
            f"  <url>\n"
            f"    <loc>{BASE_URL}{path}</loc>\n"
            f"    <lastmod>{today}</lastmod>\n"
            f"    <changefreq>{changefreq}</changefreq>\n"
            f"    <priority>{priority}</priority>\n"
            f"  </url>"
        )

    # Country code to hreflang mapping
    HREFLANG_MAP = {
        "AU": "en-AU", "US": "en-US", "UK": "en-GB", "CA": "en-CA",
        "NZ": "en-NZ", "DE": "en-DE", "FR": "en-FR", "NL": "en-NL",
        "IN": "en-IN", "BR": "en-BR", "AE": "en-AE", "JP": "en-JP",
    }

    # Country pages: /demo/{country_code}
    regions = list_regions()
    for region in regions:
        path = f"/demo/{region.code.lower()}"
        hreflang_links = ""
        for alt_region in regions:
            alt_path = f"/demo/{alt_region.code.lower()}"
            alt_lang = HREFLANG_MAP.get(alt_region.code, f"en-{alt_region.code}")
            hreflang_links += f'    <xhtml:link rel="alternate" hreflang="{alt_lang}" href="{BASE_URL}{alt_path}"/>\n'
        hreflang_links += f'    <xhtml:link rel="alternate" hreflang="x-default" href="{BASE_URL}/demo"/>\n'
        urls.append(
            f"  <url>\n"
            f"    <loc>{BASE_URL}{path}</loc>\n"
            f"    <lastmod>{today}</lastmod>\n"
            f"    <changefreq>monthly</changefreq>\n"
            f"    <priority>0.7</priority>\n"
            f"{hreflang_links}"
            f"  </url>"
        )

    # Template + country combos: /demo/{country_code}/{template_id}
    templates = list_templates()
    for region in regions:
        for template in templates:
            if region.code in template.regions:
                path = f"/demo/{region.code.lower()}/{template.id}"
                urls.append(
                    f"  <url>\n"
                    f"    <loc>{BASE_URL}{path}</loc>\n"
                    f"    <lastmod>{today}</lastmod>\n"
                    f"    <changefreq>monthly</changefreq>\n"
                    f"    <priority>0.6</priority>\n"
                    f"  </url>"
                )

    url_block = "\n".join(urls)
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n'
        '        xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
        f"{url_block}\n"
        "</urlset>"
    )

    return Response(content=xml, media_type="application/xml")


LLMS_TXT = """\
# QuillCV

> ATS-optimized CV builder that tailors your CV to job descriptions with 12 country formats.

QuillCV is a web application that helps job seekers create CVs optimized for Applicant Tracking Systems (ATS). Users paste a job description, upload their existing CV, and receive a tailored version with matched keywords, proper formatting, and country-specific conventions.

## Features
- AI-powered CV generation tailored to specific job descriptions
- ATS keyword extraction and matching with scoring
- 12 country formats: AU, US, UK, CA, NZ, DE, FR, NL, IN, BR, AE, JP
- Quality review with AI-flagged weak points and fix suggestions
- Multiple professional templates (classic, modern, minimal, executive, tech, compact, and more)
- PDF and HTML download options

## Target Users
- International job seekers applying across countries
- Career changers reframing experience for new industries
- Tech professionals needing keyword-matched CVs
- Anyone applying to jobs that use ATS screening

## Links
- Website: https://quillcv.com
- Templates: https://quillcv.com/demo
- Pricing: https://quillcv.com/pricing
"""


@router.get("/llms.txt", include_in_schema=False)
async def llms_txt():
    """Serve llms.txt for AI crawler discoverability."""
    return PlainTextResponse(LLMS_TXT)
