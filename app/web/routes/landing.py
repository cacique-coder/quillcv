"""Landing page and public routes."""

from fastapi import APIRouter, Depends, Request

from app.identity.adapters.fastapi_deps import get_current_user, require_auth
from app.identity.use_cases.authenticate import count_alpha_users
from app.infrastructure.persistence.database import async_session
from app.infrastructure.persistence.orm_models import User
from app.web.templates import templates

router = APIRouter()


@router.get("/prototype")
async def prototype(request: Request):
    return templates.TemplateResponse("prototype.html", {"request": request})


@router.get("/")
async def landing(request: Request):
    user = await get_current_user(request)
    if user:
        # Logged in users go to the app
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
            },
        )

    async with async_session() as db:
        alpha_count = await count_alpha_users(db)
    spots_remaining = max(0, 200 - alpha_count)

    return templates.TemplateResponse(
        "landing.html",
        {
            "request": request,
            "spots_remaining": spots_remaining,
            "page_description": "Build ATS-optimized CVs tailored to job descriptions. Multiple country formats, keyword matching, and AI-powered quality review. Alpha pricing: $9.99 for 15 generations.",
        },
    )


@router.get("/app")
async def app_page(request: Request, user: User = Depends(require_auth)):
    """Main app page for authenticated users."""

    from app.cv_export.adapters.template_registry import list_regions, list_templates

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "templates": list_templates(),
            "regions": list_regions(),
        },
    )
