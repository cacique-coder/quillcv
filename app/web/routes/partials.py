"""HTMX partial endpoints — small HTML fragments loaded dynamically."""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.identity.adapters.fastapi_deps import get_current_user
from app.web.templates import templates

router = APIRouter(prefix="/partials", include_in_schema=False)
logger = logging.getLogger(__name__)


@router.get("/nav")
async def nav_partial(request: Request):
    """Return the auth-aware nav links fragment. Never cached."""
    user = await get_current_user(request)
    balance = 0
    if user:
        balance = request.state.session.get("cached_balance", 0)

    html = templates.TemplateResponse(
        "partials/nav_links.html",
        {"request": request, "user": user, "balance": balance},
    )
    html.headers["Cache-Control"] = "private, no-store"
    return html


@router.get("/footer")
async def footer_partial(request: Request):
    """Return the auth-aware footer link fragment. Never cached."""
    user = await get_current_user(request)
    html = templates.TemplateResponse(
        "partials/footer_links.html",
        {"request": request, "user": user},
    )
    html.headers["Cache-Control"] = "private, no-store"
    return html
