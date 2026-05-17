"""Super admin routes: API request logs, cost tracking, usage analytics, user management."""

import logging
import secrets
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, or_, select

from app import features as feature_flags
from app.billing.use_cases.manage_credits import add_credits
from app.consent.use_cases.record_consent import get_client_ip, get_user_agent, record_consent
from app.identity.adapters.fastapi_deps import require_auth
from app.infrastructure.email.smtp import send_invitation_email
from app.infrastructure.persistence.database import async_session
from app.infrastructure.persistence.orm_models import (
    APIRequestLog,
    ConsentRecord,
    Credit,
    ExpressionOfInterest,
    Invitation,
    Payment,
    PromptLog,
    User,
)
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

        # Cost per Session — a "session" is one wizard flow (one attempt_id).
        # A session can contain multiple iterations (each = one transaction_id,
        # one generation pipeline run). Group by attempt_id so the headline
        # is total cost per CV iteration the user actually walked through.
        # Rows without an attempt_id (e.g. admin testing) are excluded — they
        # show up in the "Recent API Requests" log instead.
        cv_cost_result = await db.execute(
            select(
                APIRequestLog.attempt_id,
                APIRequestLog.user_id,
                func.count(func.distinct(APIRequestLog.transaction_id)).label("iterations"),
                func.count(APIRequestLog.id).label("api_calls"),
                func.coalesce(func.sum(APIRequestLog.cost_usd), 0).label("total_cost"),
                func.coalesce(func.sum(APIRequestLog.input_tokens), 0).label("total_input"),
                func.coalesce(func.sum(APIRequestLog.output_tokens), 0).label("total_output"),
                func.coalesce(func.sum(APIRequestLog.duration_ms), 0).label("total_duration"),
                func.min(APIRequestLog.created_at).label("started_at"),
                func.string_agg(APIRequestLog.service.distinct(), ', ').label("services"),
                func.string_agg(APIRequestLog.model.distinct(), ', ').label("models"),
            )
            .where(APIRequestLog.attempt_id.isnot(None))
            .group_by(APIRequestLog.attempt_id, APIRequestLog.user_id)
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


# ── Admin: Users ───────────────────────────────────────────


@router.get("/admin/users")
async def admin_users_list(
    request: Request,
    q: str = "",
    page: int = 1,
    user: User = Depends(require_auth),
):
    """Paginated, searchable list of all users."""
    if not _is_admin(user):
        return HTMLResponse(status_code=404)

    page = max(1, page)
    offset = (page - 1) * PAGE_SIZE
    q = q.strip()

    base = select(User)
    count_base = select(func.count(User.id))
    if q:
        like = f"%{q.lower()}%"
        cond = or_(func.lower(User.email).like(like), func.lower(User.name).like(like))
        base = base.where(cond)
        count_base = count_base.where(cond)

    async with async_session() as db:
        total = (await db.execute(count_base)).scalar() or 0
        rows = await db.execute(
            base.order_by(User.created_at.desc()).offset(offset).limit(PAGE_SIZE)
        )
        users = rows.scalars().all()

        # Credit balances for the visible users
        balance_map: dict[str, int] = {}
        if users:
            uids = [u.id for u in users]
            credits_rows = await db.execute(
                select(Credit.user_id, Credit.balance).where(Credit.user_id.in_(uids))
            )
            balance_map = {row.user_id: row.balance for row in credits_rows.all()}

    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

    return templates.TemplateResponse(
        "admin_users.html",
        {
            "request": request,
            "user": user,
            "users": users,
            "balance_map": balance_map,
            "q": q,
            "page": page,
            "total_pages": total_pages,
            "total_count": total,
            "has_prev": page > 1,
            "has_next": page < total_pages,
        },
    )


@router.get("/admin/users/{user_id}")
async def admin_user_detail(
    request: Request,
    user_id: str,
    user: User = Depends(require_auth),
):
    """Detail view for a single user — credits, payments, recent generations, consent state."""
    if not _is_admin(user):
        return HTMLResponse(status_code=404)

    async with async_session() as db:
        target_row = await db.execute(select(User).where(User.id == user_id))
        target = target_row.scalar_one_or_none()
        if not target:
            return HTMLResponse(status_code=404)

        credits_row = await db.execute(select(Credit).where(Credit.user_id == user_id))
        credits = credits_row.scalar_one_or_none()

        payments_row = await db.execute(
            select(Payment)
            .where(Payment.user_id == user_id)
            .order_by(Payment.created_at.desc())
            .limit(20)
        )
        payments = payments_row.scalars().all()

        recent_attempts = await db.execute(
            select(
                APIRequestLog.transaction_id,
                APIRequestLog.attempt_id,
                func.coalesce(func.sum(APIRequestLog.cost_usd), 0).label("total_cost"),
                func.count(APIRequestLog.id).label("api_calls"),
                func.min(APIRequestLog.created_at).label("started_at"),
            )
            .where(APIRequestLog.user_id == user_id)
            .group_by(APIRequestLog.transaction_id, APIRequestLog.attempt_id)
            .order_by(func.min(APIRequestLog.created_at).desc())
            .limit(20)
        )
        attempts = recent_attempts.all()

        consent_row = await db.execute(
            select(ConsentRecord)
            .where(
                ConsentRecord.user_id == user_id,
                ConsentRecord.consent_type == "prompt_logging",
            )
            .order_by(ConsentRecord.created_at.desc())
            .limit(1)
        )
        last_prompt_consent = consent_row.scalar_one_or_none()

        prompt_count_row = await db.execute(
            select(func.count(PromptLog.id)).where(PromptLog.user_id == user_id)
        )
        prompt_count = prompt_count_row.scalar() or 0

    return templates.TemplateResponse(
        "admin_user_detail.html",
        {
            "request": request,
            "user": user,
            "target": target,
            "credits": credits,
            "payments": payments,
            "attempts": attempts,
            "last_prompt_consent": last_prompt_consent,
            "prompt_count": prompt_count,
        },
    )


@router.post("/admin/users/{user_id}/credits")
async def admin_add_credits(
    request: Request,
    user_id: str,
    amount: int = Form(...),
    user: User = Depends(require_auth),
):
    """Grant credits to a user. ``amount`` may be negative to claw back."""
    if not _is_admin(user):
        return HTMLResponse(status_code=404)

    if amount == 0:
        return RedirectResponse(f"/admin/users/{user_id}", status_code=303)

    async with async_session() as db:
        target_row = await db.execute(select(User).where(User.id == user_id))
        if not target_row.scalar_one_or_none():
            return HTMLResponse(status_code=404)
        await add_credits(db, user_id, amount, as_grant=True)

    logger.info("Admin %s granted %d credits to user %s", user.email, amount, user_id)
    return RedirectResponse(f"/admin/users/{user_id}", status_code=303)


@router.post("/admin/users/{user_id}/toggle-active")
async def admin_toggle_active(
    request: Request,
    user_id: str,
    user: User = Depends(require_auth),
):
    """Toggle the user's is_active flag — disables sign-in without deleting data."""
    if not _is_admin(user):
        return HTMLResponse(status_code=404)

    if user_id == user.id:
        # Don't let an admin lock themselves out
        return RedirectResponse(f"/admin/users/{user_id}", status_code=303)

    async with async_session() as db:
        row = await db.execute(select(User).where(User.id == user_id))
        target = row.scalar_one_or_none()
        if not target:
            return HTMLResponse(status_code=404)
        target.is_active = not target.is_active
        await db.commit()

    return RedirectResponse(f"/admin/users/{user_id}", status_code=303)


@router.post("/admin/users/{user_id}/toggle-prompt-eligible")
async def admin_toggle_prompt_eligible(
    request: Request,
    user_id: str,
    user: User = Depends(require_auth),
):
    """Flip the user's prompt_logging_eligible flag.

    Setting to False also writes a granted=False ConsentRecord so any future
    prompt capture is blocked even if the user previously opted in.
    """
    if not _is_admin(user):
        return HTMLResponse(status_code=404)

    async with async_session() as db:
        row = await db.execute(select(User).where(User.id == user_id))
        target = row.scalar_one_or_none()
        if not target:
            return HTMLResponse(status_code=404)
        target.prompt_logging_eligible = not target.prompt_logging_eligible
        if not target.prompt_logging_eligible:
            await record_consent(
                db,
                consent_type="prompt_logging",
                granted=False,
                user_id=target.id,
                email=target.email,
                ip_address=get_client_ip(request),
                user_agent=get_user_agent(request),
            )
        await db.commit()

    return RedirectResponse(f"/admin/users/{user_id}", status_code=303)


# ── Admin: Captured prompt logs ────────────────────────────


PROMPTS_DISPLAY_LIMIT = 100


@router.get("/admin/prompts")
async def admin_prompts_list(
    request: Request,
    user: User = Depends(require_auth),
):
    """List the most recent captured prompts (consenting users only).

    Capped at PROMPTS_DISPLAY_LIMIT — older entries stay in the database
    but are not surfaced here; deep dives go through /admin/prompts/{id}.
    """
    if not _is_admin(user):
        return HTMLResponse(status_code=404)

    async with async_session() as db:
        rows = await db.execute(
            select(PromptLog)
            .order_by(PromptLog.created_at.desc())
            .limit(PROMPTS_DISPLAY_LIMIT)
        )
        logs = rows.scalars().all()

        email_map: dict[str, str] = {}
        uids = [log.user_id for log in logs if log.user_id]
        if uids:
            user_rows = await db.execute(
                select(User.id, User.email).where(User.id.in_(uids))
            )
            email_map = {row.id: row.email for row in user_rows.all()}

    return templates.TemplateResponse(
        "admin_prompts.html",
        {
            "request": request,
            "user": user,
            "logs": logs,
            "email_map": email_map,
            "display_limit": PROMPTS_DISPLAY_LIMIT,
            "shown_count": len(logs),
        },
    )


@router.get("/admin/prompts/{log_id}")
async def admin_prompt_detail(
    request: Request,
    log_id: str,
    user: User = Depends(require_auth),
):
    """View the full prompt + response for a single captured log entry."""
    if not _is_admin(user):
        return HTMLResponse(status_code=404)

    async with async_session() as db:
        row = await db.execute(select(PromptLog).where(PromptLog.id == log_id))
        log = row.scalar_one_or_none()
        if not log:
            return HTMLResponse(status_code=404)

        target_email = ""
        if log.user_id:
            email_row = await db.execute(
                select(User.email).where(User.id == log.user_id)
            )
            target_email = email_row.scalar_one_or_none() or ""

    return templates.TemplateResponse(
        "admin_prompt_detail.html",
        {
            "request": request,
            "user": user,
            "log": log,
            "target_email": target_email,
        },
    )


# ── Admin: Feature flags ───────────────────────────────────


@router.get("/admin/features")
async def admin_features(request: Request, user: User = Depends(require_auth)):
    """List registered feature flags with their effective state and override."""
    if not _is_admin(user):
        return HTMLResponse(status_code=404)

    flags = await feature_flags.list_flags()
    return templates.TemplateResponse(
        "admin_features.html",
        {
            "request": request,
            "user": user,
            "flags": flags,
        },
    )


@router.post("/admin/features/{key}")
async def admin_toggle_feature(
    request: Request,
    key: str,
    enabled: str = Form(...),
    user: User = Depends(require_auth),
):
    """Set a feature flag on or off. ``enabled`` is "true" or "false"."""
    if not _is_admin(user):
        return HTMLResponse(status_code=404)

    if key not in feature_flags.REGISTRY:
        return HTMLResponse(status_code=404)

    new_value = enabled.lower() in {"1", "true", "yes", "on"}
    await feature_flags.set_flag(key, new_value, updated_by=user.id)
    logger.info("Admin %s set feature flag %s=%s", user.email, key, new_value)
    return RedirectResponse("/admin/features", status_code=303)


# ── Admin: Session detail (one wizard flow → its iterations) ────


@router.get("/admin/sessions/{attempt_id}")
async def admin_session_detail(
    request: Request,
    attempt_id: str,
    user: User = Depends(require_auth),
):
    """One row per pipeline iteration inside a wizard session (attempt_id).

    A session = one wizard flow. Each iteration (transaction_id) is a single
    generation pipeline run, made of multiple LLM API calls. This page rolls
    them up so we can see how much one user spent across a CV.
    """
    if not _is_admin(user):
        return HTMLResponse(status_code=404)

    async with async_session() as db:
        iters_result = await db.execute(
            select(
                APIRequestLog.transaction_id,
                func.count(APIRequestLog.id).label("api_calls"),
                func.coalesce(func.sum(APIRequestLog.cost_usd), 0).label("total_cost"),
                func.coalesce(func.sum(APIRequestLog.input_tokens), 0).label("total_input"),
                func.coalesce(func.sum(APIRequestLog.output_tokens), 0).label("total_output"),
                func.coalesce(func.sum(APIRequestLog.duration_ms), 0).label("total_duration"),
                func.min(APIRequestLog.created_at).label("started_at"),
            )
            .where(APIRequestLog.attempt_id == attempt_id)
            .group_by(APIRequestLog.transaction_id)
            .order_by(func.min(APIRequestLog.created_at).asc())
        )
        iterations = iters_result.all()

        owner_email = ""
        owner_row = await db.execute(
            select(User.email)
            .join(APIRequestLog, APIRequestLog.user_id == User.id)
            .where(APIRequestLog.attempt_id == attempt_id)
            .limit(1)
        )
        owner_email = owner_row.scalar_one_or_none() or ""

    if not iterations:
        return HTMLResponse(status_code=404)

    total_cost = sum(i.total_cost for i in iterations)
    total_calls = sum(i.api_calls for i in iterations)
    total_duration = sum(i.total_duration for i in iterations)

    return templates.TemplateResponse(
        "admin_session.html",
        {
            "request": request,
            "user": user,
            "attempt_id": attempt_id,
            "owner_email": owner_email,
            "iterations": iterations,
            "total_cost": total_cost,
            "total_calls": total_calls,
            "total_duration": total_duration,
        },
    )
