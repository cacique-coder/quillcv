"""Invitation redemption routes: /invite/{code} landing and POST redeem."""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select

from app.billing.session_balance import set_cached_balance
from app.billing.use_cases.manage_credits import add_credits, get_balance
from app.identity.adapters.fastapi_deps import get_current_user, require_auth
from app.infrastructure.persistence.database import async_session
from app.infrastructure.persistence.orm_models import Invitation, User
from app.web.templates import templates

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/invite/{code}")
async def invite_landing(request: Request, code: str):
    """Show invitation details and prompt to sign up or log in."""
    user = await get_current_user(request)

    async with async_session() as db:
        result = await db.execute(select(Invitation).where(Invitation.code == code))
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
async def invite_redeem(request: Request, code: str, user: User = Depends(require_auth)):
    """Redeem an invitation for the currently logged-in user."""

    async with async_session() as db:
        result = await db.execute(select(Invitation).where(Invitation.code == code))
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

        # Grant credits using the credit service (invitation redemption is a
        # gift, not a purchase — bumps total_granted, not total_purchased).
        await add_credits(db, user.id, invitation.credits, as_grant=True)

        from app.infrastructure.instrumentation import record_custom_event

        record_custom_event(
            "InvitationRedeemed",
            {
                "user_id": user.id,
                "credits_granted": invitation.credits,
                "invitation_code": code,
            },
        )

        # Refresh cached balance in session so the nav bar updates immediately.
        new_balance = await get_balance(db, user.id)
        set_cached_balance(request.state.session, new_balance)

    logger.info("Invitation %s redeemed by user %s — %d credits granted", code, user.id, invitation.credits)

    return RedirectResponse("/app?invite_redeemed=1", status_code=303)
