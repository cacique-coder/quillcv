"""Blog routes: index listing and individual post pages — multilingual (EN, ES, PT)."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.web.templates import templates

router = APIRouter()

SUPPORTED_LANGS = ["en", "es", "pt"]

LANG_LABELS = {
    "en": "English",
    "es": "Español",
    "pt": "Português",
}

POSTS = {
    "en": [
        {
            "slug": "why-pii-matters-in-cv-builders",
            "title": "Why Your Personal Information Matters More Than You Think When Building a CV",
            "description": "Most CV builders ask for sensitive details — your address, phone, ID number. Here's why that should concern you, and what to look for.",
            "date": "2026-03-15",
            "date_modified": "2026-03-15",
            "author": "Daniel Zambrano",
            "tags": ["privacy", "cv-tips", "data-protection"],
            "faq": [
                {
                    "q": "Can I delete my data completely from a CV builder?",
                    "a": "Look for platforms that offer true deletion — not just account deactivation. Your data should be removed from the database, backups, and analytics systems when you delete your account.",
                },
                {
                    "q": "Should my personal information be encrypted in a CV builder?",
                    "a": "Yes. Look for encryption at rest, ideally with a key derived from your password so even the platform operator cannot read your personal details.",
                },
                {
                    "q": "Do CV builders sell data to third parties?",
                    "a": "Some do. Check the privacy policy for terms like 'partners', 'affiliates', or 'third-party services'. If the language is vague, assume the worst.",
                },
                {
                    "q": "What happens to my CV data after I cancel?",
                    "a": "Many platforms retain data for 30 days or more after cancellation. Look for platforms with zero-retention policies that delete data immediately.",
                },
                {
                    "q": "Do CV builders use my resume to train AI?",
                    "a": "Some platforms use uploaded CVs as training data. Look for platforms that explicitly state they do not train AI models on user content.",
                },
            ],
        },
    ],
    "es": [
        {
            "slug": "por-que-importan-tus-datos-personales-en-un-cv",
            "title": "Por Qué Tus Datos Personales Importan Más de lo Que Crees al Crear un CV",
            "description": "La mayoría de los creadores de CV piden datos sensibles — tu dirección, teléfono, número de identificación. Aquí te explicamos por qué debería importarte y qué buscar.",
            "date": "2026-03-15",
            "date_modified": "2026-03-15",
            "author": "Daniel Zambrano",
            "tags": ["privacidad", "consejos-cv", "protección-de-datos"],
            "faq": [
                {
                    "q": "¿Puedo eliminar mis datos completamente de un creador de CV?",
                    "a": "Busca plataformas que ofrezcan eliminación real, no solo desactivación de cuenta. Tus datos deben borrarse de la base de datos, las copias de seguridad y los sistemas de analítica cuando eliminas tu cuenta.",
                },
                {
                    "q": "¿Debería estar cifrada mi información personal en un creador de CV?",
                    "a": "Sí. Busca cifrado en reposo, idealmente con una clave derivada de tu contraseña para que ni el propio operador de la plataforma pueda leer tus datos personales.",
                },
                {
                    "q": "¿Los creadores de CV venden datos a terceros?",
                    "a": "Algunos sí. Revisa la política de privacidad en busca de términos como 'socios', 'afiliados' o 'servicios de terceros'. Si el lenguaje es vago, asume lo peor.",
                },
                {
                    "q": "¿Qué pasa con mis datos después de cancelar?",
                    "a": "Muchas plataformas retienen los datos durante 30 días o más tras la cancelación. Busca plataformas con políticas de retención cero que eliminen los datos de inmediato.",
                },
                {
                    "q": "¿Los creadores de CV usan mi currículum para entrenar IA?",
                    "a": "Algunas plataformas usan los CVs subidos como datos de entrenamiento. Busca plataformas que indiquen explícitamente que no entrenan modelos de IA con el contenido de los usuarios.",
                },
            ],
        },
    ],
    "pt": [
        {
            "slug": "por-que-seus-dados-pessoais-importam-em-um-curriculo",
            "title": "Por Que Seus Dados Pessoais Importam Mais do Que Você Imagina ao Criar um Currículo",
            "description": "A maioria dos criadores de currículo pede dados sensíveis — seu endereço, telefone, número de identificação. Veja por que isso deve te preocupar e o que procurar.",
            "date": "2026-03-15",
            "date_modified": "2026-03-15",
            "author": "Daniel Zambrano",
            "tags": ["privacidade", "dicas-cv", "proteção-de-dados"],
            "faq": [
                {
                    "q": "Consigo excluir meus dados completamente de um criador de currículo?",
                    "a": "Procure plataformas que ofereçam exclusão de verdade — não apenas desativação de conta. Seus dados devem ser removidos do banco de dados, dos backups e dos sistemas de análise quando você exclui sua conta.",
                },
                {
                    "q": "Minhas informações pessoais devem ser criptografadas em um criador de currículo?",
                    "a": "Sim. Procure criptografia em repouso, idealmente com uma chave derivada da sua senha, para que nem o operador da plataforma consiga ler seus dados pessoais.",
                },
                {
                    "q": "Os criadores de currículo vendem dados para terceiros?",
                    "a": "Alguns vendem. Verifique a política de privacidade em busca de termos como 'parceiros', 'afiliados' ou 'serviços de terceiros'. Se a linguagem for vaga, presuma o pior.",
                },
                {
                    "q": "O que acontece com meus dados depois que cancelo?",
                    "a": "Muitas plataformas retêm dados por 30 dias ou mais após o cancelamento. Procure plataformas com políticas de retenção zero que excluam os dados imediatamente.",
                },
                {
                    "q": "Os criadores de currículo usam meu currículo para treinar IA?",
                    "a": "Algumas plataformas usam currículos enviados como dados de treinamento. Procure plataformas que declarem explicitamente que não treinam modelos de IA com o conteúdo dos usuários.",
                },
            ],
        },
    ],
}

# Maps (lang, slug) -> {other_lang: other_slug} for hreflang on post pages
TRANSLATIONS = {
    ("en", "why-pii-matters-in-cv-builders"): {
        "es": "por-que-importan-tus-datos-personales-en-un-cv",
        "pt": "por-que-seus-dados-pessoais-importam-em-um-curriculo",
    },
    ("es", "por-que-importan-tus-datos-personales-en-un-cv"): {
        "en": "why-pii-matters-in-cv-builders",
        "pt": "por-que-seus-dados-pessoais-importam-em-um-curriculo",
    },
    ("pt", "por-que-seus-dados-pessoais-importam-em-um-curriculo"): {
        "en": "why-pii-matters-in-cv-builders",
        "es": "por-que-importan-tus-datos-personales-en-un-cv",
    },
}

# Index-level i18n strings passed to the template
INDEX_STRINGS = {
    "en": {
        "title": "The QuillCV Blog",
        "tagline": "tips, privacy, and career advice",
        "read_more": "Read more \u2192",
        "page_title": "Blog \u2014 QuillCV | CV Tips, Privacy & Career Advice",
        "page_description": "Tips, privacy advice, and career insights from the QuillCV team.",
    },
    "es": {
        "title": "El Blog de QuillCV",
        "tagline": "consejos, privacidad y carrera profesional",
        "read_more": "Leer más \u2192",
        "page_title": "Blog \u2014 QuillCV | Consejos de CV, Privacidad y Carrera",
        "page_description": "Consejos, privacidad y orientación profesional del equipo de QuillCV.",
    },
    "pt": {
        "title": "O Blog do QuillCV",
        "tagline": "dicas, privacidade e carreira profissional",
        "read_more": "Ler mais \u2192",
        "page_title": "Blog \u2014 QuillCV | Dicas de Currículo, Privacidade e Carreira",
        "page_description": "Dicas, privacidade e orientação profissional da equipe do QuillCV.",
    },
}

_POSTS_BY_LANG_SLUG: dict[str, dict[str, dict]] = {
    lang: {p["slug"]: p for p in posts}
    for lang, posts in POSTS.items()
}


@router.get("/blog", response_class=HTMLResponse)
async def blog_redirect():
    return RedirectResponse("/blog/en", status_code=301)


@router.get("/blog/{lang}", response_class=HTMLResponse)
async def blog_index(request: Request, lang: str):
    if lang not in SUPPORTED_LANGS:
        return templates.TemplateResponse(
            "partials/error.html",
            {"request": request, "message": "Language not supported."},
            status_code=404,
        )

    strings = INDEX_STRINGS[lang]
    alternate_urls = {l: f"/blog/{l}" for l in SUPPORTED_LANGS}
    lang_posts = POSTS[lang]
    page_description = strings["page_description"]
    in_language_map = {"en": "en", "es": "es", "pt": "pt-BR"}

    structured_data = {
        "@context": "https://schema.org",
        "@type": "Blog",
        "name": strings["title"],
        "url": f"https://quillcv.com/blog/{lang}",
        "description": page_description,
        "inLanguage": in_language_map.get(lang, lang),
        "publisher": {
            "@type": "Organization",
            "name": "QuillCV",
            "url": "https://quillcv.com",
        },
        "blogPost": [
            {
                "@type": "BlogPosting",
                "headline": p["title"],
                "url": f"https://quillcv.com/blog/{lang}/{p['slug']}",
                "datePublished": p["date"],
            }
            for p in lang_posts
        ],
    }

    response = templates.TemplateResponse(
        "blog_index.html",
        {
            "request": request,
            "lang": lang,
            "lang_labels": LANG_LABELS,
            "supported_langs": SUPPORTED_LANGS,
            "posts": lang_posts,
            "strings": strings,
            "alternate_urls": alternate_urls,
            "page_title": strings["page_title"],
            "page_description": page_description,
            "structured_data": structured_data,
            "html_lang": in_language_map.get(lang, lang),
        },
    )
    response.headers["Cache-Control"] = "public, max-age=86400, stale-while-revalidate=3600"
    return response


@router.get("/blog/{lang}/{slug}", response_class=HTMLResponse)
async def blog_post(request: Request, lang: str, slug: str):
    if lang not in SUPPORTED_LANGS:
        return templates.TemplateResponse(
            "partials/error.html",
            {"request": request, "message": "Language not supported."},
            status_code=404,
        )

    post = _POSTS_BY_LANG_SLUG.get(lang, {}).get(slug)
    if post is None:
        return templates.TemplateResponse(
            "partials/error.html",
            {"request": request, "message": "Post not found."},
            status_code=404,
        )

    # Build alternate_urls for hreflang and language switcher
    translation_map = TRANSLATIONS.get((lang, slug), {})
    alternate_urls: dict[str, str] = {lang: f"/blog/{lang}/{slug}"}
    for other_lang, other_slug in translation_map.items():
        alternate_urls[other_lang] = f"/blog/{other_lang}/{other_slug}"

    in_language_map = {"en": "en", "es": "es", "pt": "pt-BR"}
    blog_index_names = {"en": "Blog", "es": "Blog", "pt": "Blog"}

    breadcrumb_schema = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": "https://quillcv.com"},
            {"@type": "ListItem", "position": 2, "name": blog_index_names.get(lang, "Blog"), "item": f"https://quillcv.com/blog/{lang}"},
            {"@type": "ListItem", "position": 3, "name": post["title"]},
        ],
    }

    blogposting_schema = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": post["title"],
        "description": post["description"],
        "datePublished": post["date"],
        "dateModified": post["date_modified"],
        "inLanguage": in_language_map.get(lang, lang),
        "author": {
            "@type": "Person",
            "name": post.get("author", "Daniel Zambrano"),
        },
        "publisher": {
            "@type": "Organization",
            "name": "QuillCV",
            "url": "https://quillcv.com",
        },
        "url": f"https://quillcv.com/blog/{lang}/{post['slug']}",
    }

    structured_data = [breadcrumb_schema, blogposting_schema]

    if post.get("faq"):
        structured_data.append({
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": faq["q"],
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": faq["a"],
                    },
                }
                for faq in post["faq"]
            ],
        })

    response = templates.TemplateResponse(
        f"blog/{lang}/{slug}.html",
        {
            "request": request,
            "lang": lang,
            "lang_labels": LANG_LABELS,
            "supported_langs": SUPPORTED_LANGS,
            "post": post,
            "alternate_urls": alternate_urls,
            "page_title": f"{post['title']} — QuillCV Blog",
            "page_description": post["description"],
            "structured_data": structured_data,
            "html_lang": in_language_map.get(lang, lang),
        },
    )
    response.headers["Cache-Control"] = "public, max-age=86400, stale-while-revalidate=3600"
    return response
