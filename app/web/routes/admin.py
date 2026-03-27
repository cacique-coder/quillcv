"""Super admin routes: API request logs, cost tracking, usage analytics."""

import logging
import secrets
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select

from app.identity.adapters.fastapi_deps import require_auth
from app.infrastructure.email.smtp import send_invitation_email
from app.infrastructure.persistence.database import async_session
from app.infrastructure.persistence.orm_models import APIRequestLog, ExpressionOfInterest, Invitation, User
from app.web.templates import templates

logger = logging.getLogger(__name__)

router = APIRouter()

PAGE_SIZE = 50

def _is_admin(user) -> bool:
    """Return True if the user has the admin role."""
    if not user:
        return False
    return getattr(user, "role", "consumer") == "admin"


@router.get("/admin")
async def admin_dashboard(request: Request, user: User = Depends(require_auth)):
    """Admin dashboard with summary stats and recent requests."""
    if not _is_admin(user):
        # Return 404 — don't reveal the admin section exists
        return HTMLResponse(status_code=404)

    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    async with async_session() as db:
        # Total requests and total cost
        totals_result = await db.execute(
            select(
                func.count(APIRequestLog.id).label("total_requests"),
                func.coalesce(func.sum(APIRequestLog.cost_usd), 0).label("total_cost"),
            )
        )
        totals = totals_result.one()

        # Cost today
        today_result = await db.execute(
            select(func.coalesce(func.sum(APIRequestLog.cost_usd), 0))
            .where(APIRequestLog.created_at >= today_start)
        )
        cost_today = today_result.scalar() or 0.0

        # Unique generation attempts (for avg cost per generation)
        gen_result = await db.execute(
            select(func.count(func.distinct(APIRequestLog.attempt_id)))
            .where(APIRequestLog.attempt_id.isnot(None))
        )
        unique_generations = gen_result.scalar() or 0
        avg_cost = (totals.total_cost / unique_generations) if unique_generations > 0 else 0.0

        # Cost by model
        model_rows = await db.execute(
            select(
                APIRequestLog.model,
                func.count(APIRequestLog.id).label("calls"),
                func.coalesce(func.sum(APIRequestLog.cost_usd), 0).label("cost"),
                func.coalesce(func.sum(APIRequestLog.input_tokens), 0).label("input_tokens"),
                func.coalesce(func.sum(APIRequestLog.output_tokens), 0).label("output_tokens"),
            )
            .group_by(APIRequestLog.model)
            .order_by(func.sum(APIRequestLog.cost_usd).desc())
        )
        cost_by_model = model_rows.all()

        # Cost by service
        service_rows = await db.execute(
            select(
                APIRequestLog.service,
                func.count(APIRequestLog.id).label("calls"),
                func.coalesce(func.sum(APIRequestLog.cost_usd), 0).label("cost"),
            )
            .group_by(APIRequestLog.service)
            .order_by(func.sum(APIRequestLog.cost_usd).desc())
        )
        cost_by_service = service_rows.all()

        # EOI stats
        eoi_count_result = await db.execute(
            select(func.count(ExpressionOfInterest.id))
        )
        eoi_count = eoi_count_result.scalar() or 0

        # Recent EOIs
        eoi_result = await db.execute(
            select(ExpressionOfInterest)
            .order_by(ExpressionOfInterest.created_at.desc())
            .limit(20)
        )
        recent_eois = eoi_result.scalars().all()

        # Recent 50 requests
        recent_result = await db.execute(
            select(APIRequestLog)
            .order_by(APIRequestLog.created_at.desc())
            .limit(PAGE_SIZE)
        )
        recent_requests = recent_result.scalars().all()

        # Cost per CV — group by transaction_id, most recent first
        cv_cost_result = await db.execute(
            select(
                APIRequestLog.transaction_id,
                APIRequestLog.attempt_id,
                APIRequestLog.user_id,
                func.count(APIRequestLog.id).label("api_calls"),
                func.coalesce(func.sum(APIRequestLog.cost_usd), 0).label("total_cost"),
                func.coalesce(func.sum(APIRequestLog.input_tokens), 0).label("total_input"),
                func.coalesce(func.sum(APIRequestLog.output_tokens), 0).label("total_output"),
                func.coalesce(func.sum(APIRequestLog.duration_ms), 0).label("total_duration"),
                func.min(APIRequestLog.created_at).label("started_at"),
                func.string_agg(APIRequestLog.service.distinct(), ', ').label("services"),
                func.string_agg(APIRequestLog.model.distinct(), ', ').label("models"),
            )
            .group_by(APIRequestLog.transaction_id, APIRequestLog.attempt_id, APIRequestLog.user_id)
            .order_by(func.min(APIRequestLog.created_at).desc())
            .limit(PAGE_SIZE)
        )
        cv_costs = cv_cost_result.all()

    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "user": user,
            "total_requests": totals.total_requests,
            "total_cost": totals.total_cost,
            "cost_today": cost_today,
            "avg_cost": avg_cost,
            "unique_generations": unique_generations,
            "cost_by_model": cost_by_model,
            "cost_by_service": cost_by_service,
            "recent_requests": recent_requests,
            "cv_costs": cv_costs,
            "eoi_count": eoi_count,
            "recent_eois": recent_eois,
        },
    )


@router.get("/admin/requests")
async def admin_requests_list(request: Request, page: int = 1, user: User = Depends(require_auth)):
    """Paginated list of all API request logs."""
    if not _is_admin(user):
        return HTMLResponse(status_code=404)

    page = max(1, page)
    offset = (page - 1) * PAGE_SIZE

    async with async_session() as db:
        count_result = await db.execute(select(func.count(APIRequestLog.id)))
        total_count = count_result.scalar() or 0

        rows_result = await db.execute(
            select(APIRequestLog)
            .order_by(APIRequestLog.created_at.desc())
            .offset(offset)
            .limit(PAGE_SIZE)
        )
        requests = rows_result.scalars().all()

    total_pages = max(1, (total_count + PAGE_SIZE - 1) // PAGE_SIZE)

    return templates.TemplateResponse(
        "admin_requests.html",
        {
            "request": request,
            "user": user,
            "requests": requests,
            "page": page,
            "total_pages": total_pages,
            "total_count": total_count,
            "has_prev": page > 1,
            "has_next": page < total_pages,
        },
    )


@router.get("/admin/requests/{transaction_id}")
async def admin_transaction_detail(request: Request, transaction_id: str, user: User = Depends(require_auth)):
    """Detail view for a single transaction — all requests sharing that transaction_id."""
    if not _is_admin(user):
        return HTMLResponse(status_code=404)

    async with async_session() as db:
        rows_result = await db.execute(
            select(APIRequestLog)
            .where(APIRequestLog.transaction_id == transaction_id)
            .order_by(APIRequestLog.created_at.asc())
        )
        tx_requests = rows_result.scalars().all()

    if not tx_requests:
        return HTMLResponse(status_code=404)

    total_cost = sum(r.cost_usd for r in tx_requests)
    total_input = sum(r.input_tokens for r in tx_requests)
    total_output = sum(r.output_tokens for r in tx_requests)
    total_duration = sum(r.duration_ms for r in tx_requests)

    return templates.TemplateResponse(
        "admin_transaction.html",
        {
            "request": request,
            "user": user,
            "transaction_id": transaction_id,
            "tx_requests": tx_requests,
            "total_cost": total_cost,
            "total_input": total_input,
            "total_output": total_output,
            "total_duration": total_duration,
        },
    )


# ── Admin: Invitations ─────────────────────────────────────


@router.get("/admin/invitations")
async def admin_invitations(request: Request, user: User = Depends(require_auth)):
    """List all invitations and show the create form."""
    if not _is_admin(user):
        return HTMLResponse(status_code=404)

    async with async_session() as db:
        rows = await db.execute(
            select(Invitation).order_by(Invitation.created_at.desc())
        )
        invitations = rows.scalars().all()

        # Fetch redeemer emails for display
        redeemer_ids = [inv.redeemed_by for inv in invitations if inv.redeemed_by]
        redeemer_map: dict[str, str] = {}
        if redeemer_ids:
            user_rows = await db.execute(
                select(User.id, User.email).where(User.id.in_(redeemer_ids))
            )
            redeemer_map = {row.id: row.email for row in user_rows.all()}

    return templates.TemplateResponse(
        "admin_invitations.html",
        {
            "request": request,
            "user": user,
            "invitations": invitations,
            "redeemer_map": redeemer_map,
        },
    )


@router.post("/admin/invitations")
async def admin_create_invitation(
    request: Request,
    email: str = Form(""),
    credits: int = Form(...),
    note: str = Form(""),
    user: User = Depends(require_auth),
):
    """Create a new invitation code."""
    if not _is_admin(user):
        return HTMLResponse(status_code=404)

    # Generate a short URL-safe code (~8 printable chars)
    code = secrets.token_urlsafe(6)

    invitation = Invitation(
        code=code,
        email=email.lower().strip() if email.strip() else None,
        credits=credits,
        note=note.strip(),
    )

    async with async_session() as db:
        db.add(invitation)
        await db.commit()

    # Send invitation email if a recipient address was provided
    if invitation.email:
        base_url = str(request.base_url).rstrip("/")
        try:
            await send_invitation_email(
                to_email=invitation.email,
                invite_code=code,
                credits=credits,
                note=note.strip(),
                base_url=base_url,
            )
        except Exception:
            logger.exception("Failed to send invitation email to %s", invitation.email)

    return RedirectResponse("/admin/invitations", status_code=303)
