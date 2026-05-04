"""Landing page and public routes."""

from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from app.identity.adapters.fastapi_deps import get_current_user, require_auth
from app.identity.use_cases.authenticate import count_alpha_users
from app.infrastructure.persistence.attempt_store import get_attempt
from app.infrastructure.persistence.cv_repo import list_saved_cvs
from app.infrastructure.persistence.database import async_session
from app.infrastructure.persistence.orm_models import PIIVault, User
from app.web.templates import templates
from sqlalchemy import select

router = APIRouter()

_QUOTE = (
    '"The secret of getting ahead is getting started." — Mark Twain'
)


def _humanize_delta(dt: datetime | None) -> str:
    """Return a human-readable relative time string for *dt* (UTC-aware or naive)."""
    if dt is None:
        return ""
    now = datetime.now(UTC)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    delta = now - dt
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        m = seconds // 60
        return f"{m}m ago"
    if seconds < 86400:
        h = seconds // 3600
        return f"{h}h ago"
    if seconds < 172800:
        return "yesterday"
    if seconds < 604800:
        d = seconds // 86400
        return f"{d} days ago"
    if seconds < 1_209_600:
        return "last week"
    w = seconds // 604800
    return f"{w} weeks ago"


@router.get("/prototype")
async def prototype(request: Request):
    return templates.TemplateResponse("prototype.html", {"request": request})


@router.get("/")
async def landing(request: Request):
    user = await get_current_user(request)
    if user:
        return RedirectResponse("/dashboard", status_code=302)

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
    """Redirect signed-in users to the dashboard; anonymous users are caught by require_auth."""
    return RedirectResponse("/dashboard", status_code=302)


@router.get("/dashboard")
async def dashboard(request: Request, user: User = Depends(require_auth)):
    """Main dashboard for authenticated users."""
    today = date.today()
    today_pretty = today.strftime("%A · %-d %B %Y")

    # --- In-progress wizard attempt ---
    resume = None
    attempt_id = request.state.session.get("attempt_id")
    if attempt_id:
        attempt = get_attempt(attempt_id)
        if attempt and 2 <= attempt.get("step", 0) <= 5 and attempt.get("job_description"):
            jd_snippet = (attempt["job_description"][:60]).strip()
            step = attempt["step"]
            resume = {
                "step": step,
                "title": jd_snippet,
                "url": f"/wizard/step/{step}",
            }

    async with async_session() as db:
        # --- Recent CVs (top 4, newest first) ---
        all_cvs = await list_saved_cvs(db, user_id=user.id)
        recent_cvs = [
            {
                "id": cv.id,
                "title": cv.label or cv.job_title or "Untitled CV",
                "region": cv.region,
                "template": cv.template_id,
                "score": None,   # SavedCV has no score field; Job.ats_generated_score lives separately
                "updated_human": _humanize_delta(cv.created_at),
            }
            for cv in all_cvs[:4]
        ]

        # --- Vault ---
        vault = None
        result = await db.execute(
            select(PIIVault).where(PIIVault.user_id == user.id)
        )
        pii_row = result.scalar_one_or_none()
        if pii_row:
            vault = {
                "updated_human": _humanize_delta(pii_row.updated_at),
                "configured": True,
            }

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "today_pretty": today_pretty,
            "quote": _QUOTE,
            "resume": resume,
            "recent_cvs": recent_cvs,
            "vault": vault,
        },
    )
