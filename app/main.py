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
    os.environ.get("SESSION_SECRET", "quillcv-dev-secret-change-in-prod")
    == "quillcv-dev-secret-change-in-prod"
)

from app.logging_config import setup_logging
setup_logging(dev_mode=_dev_mode_for_logging)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Framework + application imports (after logging is configured)
# ---------------------------------------------------------------------------

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from starlette.middleware.base import BaseHTTPMiddleware  # noqa: E402

from app.middleware import AuthContextMiddleware, RequestContextMiddleware  # noqa: E402
from app.session import SQLiteSessionMiddleware, init_session_db  # noqa: E402
from app.routers import account as account_router  # noqa: E402
from app.routers import admin as admin_router  # noqa: E402
from app.routers import auth as auth_router  # noqa: E402
from app.routers import builder, cv, demo, my_cvs, photos, wizard  # noqa: E402
from app.routers import landing as landing_router  # noqa: E402
from app.routers import payments as payments_router  # noqa: E402
from app.routers import invitations as invitations_router  # noqa: E402
from app.routers import onboarding as onboarding_router  # noqa: E402
from app.routers import pages as pages_router  # noqa: E402
from app.routers import seo as seo_router  # noqa: E402
from app.services.llm_client import ClaudeCodeClient, create_llm_client  # noqa: E402

# ---------------------------------------------------------------------------
# Request logging middleware
# ---------------------------------------------------------------------------

_SKIP_PREFIXES = ("/static/", "/favicon.ico")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with method, path, status, duration, and client IP."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if any(path.startswith(p) for p in _SKIP_PREFIXES):
            return await call_next(request)

        t0 = time.monotonic()
        response = await call_next(request)
        duration_ms = round((time.monotonic() - t0) * 1000)

        rid = getattr(request.state, "request_id", "-")
        client_ip = request.client.host if request.client else "-"
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.database import init_db
    await init_db()
    await init_session_db()
    yield


app = FastAPI(title="QuillCV", lifespan=lifespan)

# Dev mode: enabled when using the default session secret (i.e. local development)
app.state.dev_mode = _dev_mode_for_logging

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RequestContextMiddleware)  # adds request_id context var
app.add_middleware(AuthContextMiddleware)

# Server-side session middleware backed by SQLite.  Must be outermost so that
# sessions are available when AuthContextMiddleware runs.
app.add_middleware(SQLiteSessionMiddleware)

# LLM clients: primary (heavy) for CV generation, fast (light) for lightweight tasks.
# Set LLM_PROVIDER=anthropic|openai|gemini to switch provider; defaults to "anthropic".
# Dev mode (no API key present) falls back to ClaudeCodeClient via the Claude CLI.
_has_api_key = any(
    os.environ.get(k)
    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY")
)
if _has_api_key:
    _provider = os.environ.get("LLM_PROVIDER", "anthropic")
    app.state.llm = create_llm_client(_provider, "heavy")
    app.state.llm_fast = create_llm_client(_provider, "light")
else:
    app.state.llm = ClaudeCodeClient(model="sonnet")
    app.state.llm_fast = ClaudeCodeClient(model="haiku")

app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).parent / "static"),
    name="static",
)


# Health check — Kamal requires this to verify the app is running
@app.get("/up", include_in_schema=False)
async def health_check():
    return {"status": "ok"}


# SEO infrastructure (robots.txt, sitemap.xml)
app.include_router(seo_router.router)

# Static content pages (about, privacy, terms)
app.include_router(pages_router.router)

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
app.include_router(builder.router)
app.include_router(my_cvs.router)
app.include_router(cv.router)
app.include_router(demo.router)
app.include_router(photos.router)
app.include_router(pages_router.router)


