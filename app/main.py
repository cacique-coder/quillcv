import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

# Load .env file before anything reads os.environ
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

# ---------------------------------------------------------------------------
# Logging — configured first so all module-level loggers inherit the setup
# ---------------------------------------------------------------------------

_dev_mode_for_logging = (
    os.environ.get("SESSION_SECRET", "quillcv-dev-secret-change-in-prod") == "quillcv-dev-secret-change-in-prod"
)

from app.infrastructure.logging import setup_logging  # noqa: E402

setup_logging(dev_mode=_dev_mode_for_logging)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Framework + application imports (after logging is configured)
# ---------------------------------------------------------------------------

from datetime import UTC  # noqa: E402

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from starlette.middleware.base import BaseHTTPMiddleware  # noqa: E402

from app.infrastructure.llm.client import ClaudeCodeClient, create_llm_client  # noqa: E402
from app.infrastructure.middleware.main import (  # noqa: E402
    AuthContextMiddleware,
    CSRFMiddleware,
    RequestContextMiddleware,
)
from app.infrastructure.middleware.session import SQLiteSessionMiddleware, init_session_db  # noqa: E402
from app.web.routes import account as account_router  # noqa: E402
from app.web.routes import admin as admin_router  # noqa: E402
from app.web.routes import auth as auth_router  # noqa: E402
from app.web.routes import blog as blog_router  # noqa: E402
from app.web.routes import builder, cv, demo, my_cvs, photos, profile, wizard  # noqa: E402
from app.web.routes import invitations as invitations_router  # noqa: E402
from app.web.routes import landing as landing_router  # noqa: E402
from app.web.routes import onboarding as onboarding_router  # noqa: E402
from app.web.routes import pages as pages_router  # noqa: E402
from app.web.routes import partials as partials_router  # noqa: E402
from app.web.routes import payments as payments_router  # noqa: E402
from app.web.routes import seo as seo_router  # noqa: E402

# ---------------------------------------------------------------------------
# Request logging middleware
# ---------------------------------------------------------------------------

_SKIP_PREFIXES = ("/static/", "/favicon.ico")


class StaticCacheMiddleware(BaseHTTPMiddleware):
    """Set long-lived Cache-Control for versioned static assets."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with method, path, status, duration, and client IP."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if any(path.startswith(p) for p in _SKIP_PREFIXES):
            return await call_next(request)

        t0 = time.monotonic()
        response = await call_next(request)
        duration_ms = round((time.monotonic() - t0) * 1000)

        getattr(request.state, "request_id", "-")
        status = response.status_code

        logger.info(
            "request",
            extra={
                "method": request.method,
                "path": path,
                "status": status,
                "duration_ms": duration_ms,
            },
        )
        return response


async def _cleanup_stale_payments() -> None:
    """Mark payments that have been pending for over 24 hours as expired.

    Stripe checkout sessions expire after 24 hours by default. If the webhook
    was missed or the user abandoned the flow, pending rows would otherwise
    remain stuck indefinitely.  This is safe to run multiple times — it only
    touches rows that are still in 'pending' status.
    """
    from datetime import datetime, timedelta

    from sqlalchemy import update

    from app.infrastructure.persistence.database import async_session
    from app.infrastructure.persistence.orm_models import Payment

    cutoff = datetime.now(UTC) - timedelta(hours=24)
    async with async_session() as db:
        result = await db.execute(
            update(Payment)
            .where(Payment.status == "pending", Payment.created_at < cutoff)
            .values(status="expired")
            .returning(Payment.id)
        )
        expired_ids = result.scalars().all()
        await db.commit()
        if expired_ids:
            logger.info(
                "Cleaned up %d stale pending payment(s) older than 24 h: %s",
                len(expired_ids),
                expired_ids,
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.infrastructure.persistence.database import init_db

    await init_db()
    await init_session_db()
    await _cleanup_stale_payments()
    yield


app = FastAPI(title="QuillCV", lifespan=lifespan)

# Dev mode: enabled when using the default session secret (i.e. local development)
app.state.dev_mode = _dev_mode_for_logging

app.add_middleware(StaticCacheMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RequestContextMiddleware)  # adds request_id context var
app.add_middleware(AuthContextMiddleware)
# CSRF must run after the session is loaded (session middleware is outermost,
# so it runs first and populates request.state.session before CSRF checks run).
app.add_middleware(CSRFMiddleware)

# Server-side session middleware backed by SQLite.  Must be outermost so that
# sessions are available when AuthContextMiddleware and CSRFMiddleware run.
app.add_middleware(SQLiteSessionMiddleware)

# LLM clients: primary (heavy) for CV generation, fast (light) for lightweight tasks.
# Set LLM_PROVIDER=anthropic|openai|gemini|claude-code to switch provider.
# - claude-code routes through the local `claude` CLI (uses your Claude
#   subscription, no API credit) — explicit opt-in, useful in dev.
# - When LLM_PROVIDER is unset and no API key is in the environment, we
#   also fall back to claude-code so a fresh dev container Just Works.
_has_api_key = any(os.environ.get(k) for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY"))
_explicit_provider = os.environ.get("LLM_PROVIDER", "").strip()
if _explicit_provider == "claude-code" or (not _has_api_key and not _explicit_provider):
    _selected_provider = "claude-code"
    app.state.llm = ClaudeCodeClient(model="sonnet")
    app.state.llm_fast = ClaudeCodeClient(model="haiku")
else:
    _selected_provider = _explicit_provider or "anthropic"
    app.state.llm = create_llm_client(_selected_provider, "heavy")
    app.state.llm_fast = create_llm_client(_selected_provider, "light")

# Expose for the /up healthcheck and emit a single startup line so it's
# obvious from the boot logs which provider/model is actually in use.
app.state.llm_info = {
    "provider": _selected_provider,
    "heavy": getattr(app.state.llm, "model", "?"),
    "light": getattr(app.state.llm_fast, "model", "?"),
    "explicit": bool(_explicit_provider),
}
logger.info(
    "LLM[heavy]: provider=%s model=%s | LLM[light]: provider=%s model=%s | LLM_PROVIDER=%s",
    _selected_provider, app.state.llm_info["heavy"],
    _selected_provider, app.state.llm_info["light"],
    _explicit_provider or "(unset → autodetected)",
)

app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).parent / "static"),
    name="static",
)


# Health check — Kamal requires this to verify the app is running.
# Also reports the active LLM so you can verify which provider is wired
# without grepping logs.
@app.get("/up", include_in_schema=False)
async def health_check():
    return {"status": "ok", "llm": getattr(app.state, "llm_info", {})}


# SEO infrastructure (robots.txt, sitemap.xml)
app.include_router(seo_router.router)

# Static content pages (about, privacy, terms)
app.include_router(pages_router.router)

# Blog
app.include_router(blog_router.router)

# HTMX partials (nav, footer auth fragments — never cached)
app.include_router(partials_router.router)

# Auth, payments, invitations, and onboarding
app.include_router(auth_router.router)
app.include_router(payments_router.router)
app.include_router(invitations_router.router)
app.include_router(onboarding_router.router)

# Landing page replaces the old / route
app.include_router(landing_router.router)

# App routes
app.include_router(admin_router.router)
app.include_router(account_router.router)
app.include_router(wizard.router)
app.include_router(profile.router)
app.include_router(builder.router)
app.include_router(my_cvs.router)
app.include_router(cv.router)
app.include_router(demo.router)
app.include_router(photos.router)
app.include_router(pages_router.router)
