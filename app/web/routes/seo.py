"""SEO infrastructure routes: robots.txt and sitemap.xml."""

from datetime import date

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse, Response

from app.cv_export.adapters.template_registry import list_regions, list_templates
from app.web.routes.blog import POSTS

router = APIRouter()

BASE_URL = "https://quillcv.com"

ROBOTS_TXT = """\
User-agent: *
Allow: /
Disallow: /app
Disallow: /wizard/
Disallow: /apply-fixes
Disallow: /download-pdf
Disallow: /download-docx
Disallow: /download-cover-letter-pdf
Disallow: /download-cover-letter-docx
Disallow: /download-all-pdf
Disallow: /download-all-docx
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

User-agent: OAI-SearchBot
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

    # Derive the most recent post date across all languages for blog index lastmod
    all_post_dates = [p["date_modified"] for posts in POSTS.values() for p in posts]
    latest_post_date = max(all_post_dates) if all_post_dates else today

    urls: list[str] = []

    # Static public pages (no hreflang)
    static_pages = [
        ("/", "1.0", "weekly"),
        ("/pricing", "0.8", "monthly"),
        ("/demo", "0.9", "weekly"),
        ("/about", "0.5", "monthly"),
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

    # Privacy pages — multilingual group with hreflang alternates
    PRIVACY_PAGES = [
        ("/privacy", "en"),
        ("/privacidad", "es"),
        ("/privacidade", "pt-BR"),
    ]
    privacy_hreflang_links = (
        f'    <xhtml:link rel="alternate" hreflang="en" href="{BASE_URL}/privacy"/>\n'
        f'    <xhtml:link rel="alternate" hreflang="es" href="{BASE_URL}/privacidad"/>\n'
        f'    <xhtml:link rel="alternate" hreflang="pt-BR" href="{BASE_URL}/privacidade"/>\n'
        f'    <xhtml:link rel="alternate" hreflang="x-default" href="{BASE_URL}/privacy"/>\n'
    )
    for path, _lang in PRIVACY_PAGES:
        urls.append(
            f"  <url>\n"
            f"    <loc>{BASE_URL}{path}</loc>\n"
            f"    <lastmod>{today}</lastmod>\n"
            f"    <changefreq>yearly</changefreq>\n"
            f"    <priority>0.3</priority>\n"
            f"{privacy_hreflang_links}"
            f"  </url>"
        )

    # Blog index pages — one per language with hreflang alternates
    BLOG_LANGS = [
        ("en", "en"),
        ("es", "es"),
        ("pt", "pt-BR"),
    ]
    for lang_code, _hreflang_code in BLOG_LANGS:
        path = f"/blog/{lang_code}"
        hreflang_links = ""
        for alt_lang_code, alt_hreflang_code in BLOG_LANGS:
            hreflang_links += (
                f'    <xhtml:link rel="alternate" hreflang="{alt_hreflang_code}"'
                f' href="{BASE_URL}/blog/{alt_lang_code}"/>\n'
            )
        hreflang_links += (
            f'    <xhtml:link rel="alternate" hreflang="x-default"'
            f' href="{BASE_URL}/blog/en"/>\n'
        )
        urls.append(
            f"  <url>\n"
            f"    <loc>{BASE_URL}{path}</loc>\n"
            f"    <lastmod>{latest_post_date}</lastmod>\n"
            f"    <changefreq>weekly</changefreq>\n"
            f"    <priority>0.7</priority>\n"
            f"{hreflang_links}"
            f"  </url>"
        )

    # Blog posts with hreflang alternates linking to translations
    # Build slug -> date_modified lookup per lang
    POSTS_BY_LANG_SLUG = {
        lang: {p["slug"]: p for p in posts}
        for lang, posts in POSTS.items()
    }
    BLOG_POST_TRANSLATIONS = [
        {
            "en": "/blog/en/why-pii-matters-in-cv-builders",
            "es": "/blog/es/por-que-importan-tus-datos-personales-en-un-cv",
            "pt": "/blog/pt/por-que-seus-dados-pessoais-importam-em-um-curriculo",
        },
    ]
    LANG_HREFLANG = {"en": "en", "es": "es", "pt": "pt-BR"}
    for translation_set in BLOG_POST_TRANSLATIONS:
        for lang_code, path in translation_set.items():
            slug = path.rsplit("/", 1)[-1]
            post_data = POSTS_BY_LANG_SLUG.get(lang_code, {}).get(slug)
            post_lastmod = post_data["date_modified"] if post_data else today
            hreflang_links = ""
            for alt_lang_code, alt_path in translation_set.items():
                alt_hreflang = LANG_HREFLANG[alt_lang_code]
                hreflang_links += (
                    f'    <xhtml:link rel="alternate" hreflang="{alt_hreflang}"'
                    f' href="{BASE_URL}{alt_path}"/>\n'
                )
            # x-default points to English
            hreflang_links += (
                f'    <xhtml:link rel="alternate" hreflang="x-default"'
                f' href="{BASE_URL}{translation_set["en"]}"/>\n'
            )
            urls.append(
                f"  <url>\n"
                f"    <loc>{BASE_URL}{path}</loc>\n"
                f"    <lastmod>{post_lastmod}</lastmod>\n"
                f"    <changefreq>monthly</changefreq>\n"
                f"    <priority>0.6</priority>\n"
                f"{hreflang_links}"
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
    templates_list = list_templates()
    for region in regions:
        for template in templates_list:
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

## Blog
- [Why Your PII Matters in CV Builders](https://quillcv.com/blog/en/why-pii-matters-in-cv-builders)
- [Por Qué Importan Tus Datos Personales](https://quillcv.com/blog/es/por-que-importan-tus-datos-personales-en-un-cv)
- [Por Que Seus Dados Pessoais Importam](https://quillcv.com/blog/pt/por-que-seus-dados-pessoais-importam-em-um-curriculo)
"""


@router.get("/llms.txt", include_in_schema=False)
async def llms_txt():
    """Serve llms.txt for AI crawler discoverability."""
    return PlainTextResponse(LLMS_TXT)
