"""Super admin routes: API request logs, cost tracking, usage analytics."""

import logging
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select

from app.auth.dependencies import get_current_user
from app.database import async_session
from app.models import APIRequestLog

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")

PAGE_SIZE = 50

# Emails allowed to access admin. If empty, dev mode allows any logged-in user.
ADMIN_EMAILS: set[str] = set(
    e.strip() for e in os.environ.get("ADMIN_EMAILS", "daniel@example.com").split(",") if e.strip()
)


def _is_admin(user) -> bool:
    """Return True if the user is permitted to access admin pages."""
    if not user:
        return False
    # Dev mode: no ADMIN_EMAILS set — allow any authenticated user
    if not ADMIN_EMAILS:
        return True
    return user.email in ADMIN_EMAILS


@router.get("/admin")
async def admin_dashboard(request: Request):
    """Admin dashboard with summary stats and recent requests."""
    user = await get_current_user(request)
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

        # Recent 50 requests
        recent_result = await db.execute(
            select(APIRequestLog)
            .order_by(APIRequestLog.created_at.desc())
            .limit(PAGE_SIZE)
        )
        recent_requests = recent_result.scalars().all()

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
        },
    )


@router.get("/admin/requests")
async def admin_requests_list(request: Request, page: int = 1):
    """Paginated list of all API request logs."""
    user = await get_current_user(request)
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
async def admin_transaction_detail(request: Request, transaction_id: str):
    """Detail view for a single transaction — all requests sharing that transaction_id."""
    user = await get_current_user(request)
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
