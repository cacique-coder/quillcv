"""Static content pages: about, privacy policy, terms of service, CCPA opt-out."""

import logging

from fastapi import APIRouter, Form, Request

from app.infrastructure.persistence.database import async_session
from app.infrastructure.persistence.orm_models import ConsentRecord
from app.web.templates import templates

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/about")
async def about_page(request: Request):
    response = templates.TemplateResponse("about.html", {"request": request})
    response.headers["Cache-Control"] = "public, max-age=86400, stale-while-revalidate=3600"
    return response


@router.get("/privacy")
async def privacy_page(request: Request):
    response = templates.TemplateResponse("privacy.html", {"request": request})
    response.headers["Cache-Control"] = "public, max-age=86400, stale-while-revalidate=3600"
    return response


@router.get("/privacidad")
async def privacidad_page(request: Request):
    response = templates.TemplateResponse("privacidad.html", {"request": request, "html_lang": "es"})
    response.headers["Cache-Control"] = "public, max-age=86400, stale-while-revalidate=3600"
    return response


@router.get("/privacidade")
async def privacidade_page(request: Request):
    response = templates.TemplateResponse("privacidade.html", {"request": request, "html_lang": "pt-BR"})
    response.headers["Cache-Control"] = "public, max-age=86400, stale-while-revalidate=3600"
    return response


@router.get("/terms")
async def terms_page(request: Request):
    response = templates.TemplateResponse("terms.html", {"request": request})
    response.headers["Cache-Control"] = "public, max-age=86400, stale-while-revalidate=3600"
    return response


@router.get("/ccpa-opt-out")
async def ccpa_optout_page(request: Request):
    """CCPA/CPRA 'Do Not Sell or Share' opt-out form."""
    user = getattr(request.state, "user", None)
    prefill_email = user.email if user else ""
    return templates.TemplateResponse(
        "ccpa_optout.html",
        {"request": request, "prefill_email": prefill_email, "submitted": False},
    )


@router.post("/ccpa-opt-out")
async def ccpa_optout_submit(
    request: Request,
    email: str = Form(...),
    opt_out_confirmed: bool = Form(False),
):
    """Record a CCPA opt-out request and show confirmation."""
    user = getattr(request.state, "user", None)
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent", "")[:512]

    async with async_session() as db:
        record = ConsentRecord(
            user_id=user.id if user else None,
            consent_type="ccpa_opt_out",
            email=email.strip().lower(),
            granted=False,  # opted OUT — not granting sale/share
            ip_address=ip,
            user_agent=ua,
        )
        db.add(record)
        await db.commit()

    logger.info("CCPA opt-out recorded for %s (confirmed=%s)", email, opt_out_confirmed)

    return templates.TemplateResponse(
        "ccpa_optout.html",
        {
            "request": request,
            "prefill_email": email,
            "submitted": True,
        },
    )
