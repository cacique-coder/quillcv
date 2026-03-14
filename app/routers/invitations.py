"""Invitation redemption routes: /invite/{code} landing and POST redeem."""

import logging
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.auth.dependencies import get_current_user
from app.database import async_session
from app.models import Invitation
from app.services.credit_service import add_credits

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


@router.get("/invite/{code}")
async def invite_landing(request: Request, code: str):
    """Show invitation details and prompt to sign up or log in."""
    user = await get_current_user(request)

    async with async_session() as db:
        result = await db.execute(
            select(Invitation).where(Invitation.code == code)
        )
        invitation = result.scalar_one_or_none()

    if not invitation:
        return HTMLResponse(status_code=404)

    return templates.TemplateResponse(
        "invite.html",
        {
            "request": request,
            "user": user,
            "invitation": invitation,
            "code": code,
        },
    )


@router.post("/invite/{code}/redeem")
async def invite_redeem(request: Request, code: str):
    """Redeem an invitation for the currently logged-in user."""
    user = await get_current_user(request)

    if not user:
        # Preserve the invite code through the auth flow via query param
        return RedirectResponse(f"/login?invite={code}", status_code=303)

    async with async_session() as db:
        result = await db.execute(
            select(Invitation).where(Invitation.code == code)
        )
        invitation = result.scalar_one_or_none()

        if not invitation:
            return HTMLResponse(status_code=404)

        if invitation.redeemed_by:
            # Already redeemed — show the landing page with the "claimed" state
            return RedirectResponse(f"/invite/{code}", status_code=303)

        # Lock the invitation to this user
        if invitation.email and invitation.email != user.email.lower():
            # Invitation is restricted to a different email
            return templates.TemplateResponse(
                "invite.html",
                {
                    "request": request,
                    "user": user,
                    "invitation": invitation,
                    "code": code,
                    "error": "This invitation is for a different email address.",
                },
                status_code=403,
            )

        invitation.redeemed_by = user.id
        invitation.redeemed_at = datetime.now(UTC)
        await db.commit()

        # Grant credits using the credit service
        await add_credits(db, user.id, invitation.credits)

    logger.info("Invitation %s redeemed by user %s — %d credits granted", code, user.id, invitation.credits)

    return RedirectResponse("/app?invite_redeemed=1", status_code=303)
