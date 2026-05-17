"""Application-level middleware for QuillCV."""

import contextvars
import hmac
import logging
import os
import secrets
import uuid
from typing import ClassVar
from urllib.parse import parse_qs

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, Response

logger = logging.getLogger(__name__)

_SKIP_PREFIXES = ("/static/", "/favicon.ico")
_IS_PRODUCTION = os.environ.get("APP_ENV", "development") == "production"

# ---------------------------------------------------------------------------
# CSRF token helpers
# ---------------------------------------------------------------------------

# Endpoints that must be excluded from CSRF checks (Stripe posts without a
# browser session — it signs requests with a separate webhook secret instead).
_CSRF_EXEMPT_PATHS = {"/webhook/stripe"}

_CSRF_FIELD = "csrf_token"
_CSRF_HEADER = "X-CSRF-Token"
_CSRF_SESSION_KEY = "_csrf_token"


def _generate_csrf_token() -> str:
    """Return a 32-byte URL-safe random token."""
    return secrets.token_urlsafe(32)


def _csrf_tokens_equal(a: str, b: str) -> bool:
    """Constant-time comparison to prevent timing attacks."""
    return hmac.compare_digest(a.encode(), b.encode())

# ---------------------------------------------------------------------------
# Request-scoped context vars — accessible from any async code in the stack
# ---------------------------------------------------------------------------

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
client_ip_var: contextvars.ContextVar[str] = contextvars.ContextVar("client_ip", default="-")
session_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("session_id", default="-")
user_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("user_id", default="-")


class CSRFMiddleware(BaseHTTPMiddleware):
    """CSRF protection for all state-mutating (POST/PUT/PATCH/DELETE) requests.

    Strategy:
    - On GET requests: generate a token (if not already in session) and attach
      it to request.state.csrf_token so templates can embed it in forms.
    - On POST (and other mutating) requests: compare the token submitted via the
      hidden form field OR the X-CSRF-Token header against the session token.
    - Returns 403 on mismatch.  Exempt paths (e.g. /webhook/stripe) are skipped.
    - The session must already be loaded before this middleware runs
      (SQLiteSessionMiddleware must be outermost / registered last).
    """

    _MUTATING_METHODS: ClassVar[set[str]] = {"POST", "PUT", "PATCH", "DELETE"}

    async def dispatch(self, request: Request, call_next) -> Response:
        # Ensure the session has a CSRF token.  We attach it to state so
        # templates rendered during GET requests can include it.
        session = getattr(request.state, "session", None) or {}
        token: str = session.get(_CSRF_SESSION_KEY, "")
        if not token:
            token = _generate_csrf_token()
            session[_CSRF_SESSION_KEY] = token
            # Mark session dirty so SQLiteSessionMiddleware persists it.
            if hasattr(request.state, "session"):
                request.state.session[_CSRF_SESSION_KEY] = token

        request.state.csrf_token = token

        if request.method in self._MUTATING_METHODS:
            if request.url.path not in _CSRF_EXEMPT_PATHS:
                # Try the header first (used by HTMX), then the form field.
                submitted = request.headers.get(_CSRF_HEADER, "")
                if not submitted:
                    # We need to read the form body.  FastAPI/Starlette caches
                    # the body so reading it here does not consume it for the
                    # downstream handler.
                    try:
                        body = await request.body()
                        parsed = parse_qs(body.decode("utf-8", errors="replace"))
                        submitted = parsed.get(_CSRF_FIELD, [""])[0]
                    except Exception:
                        submitted = ""

                if not submitted or not _csrf_tokens_equal(token, submitted):
                    logger.warning(
                        "CSRF token mismatch: path=%s method=%s",
                        request.url.path,
                        request.method,
                    )
                    return HTMLResponse(
                        "<h1>403 Forbidden</h1><p>Invalid or missing CSRF token.</p>",
                        status_code=403,
                    )

        return await call_next(request)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assign a short request ID to every request and expose it via context vars.

    The request ID is available as:
    - request.state.request_id
    - request_id_var.get() from any async code
    - X-Request-Id response header
    """

    async def dispatch(self, request: Request, call_next):
        rid = uuid.uuid4().hex[:8]
        request.state.request_id = rid
        request_id_var.set(rid)
        client_ip_var.set(request.client.host if request.client else "-")
        response = await call_next(request)
        response.headers["X-Request-Id"] = rid
        if _IS_PRODUCTION:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


class AuthContextMiddleware(BaseHTTPMiddleware):
    """Inject authenticated user and credit balance into request.state for every request.

    Balance is read directly from the DB on every authenticated request — one
    indexed PK lookup per request.  There is no session cache: this guarantees
    that admin grants, webhook credits, and any out-of-band balance change are
    visible to the user immediately without requiring a re-login.

    Routers that need the user for *business logic* (auth guards, redirects,
    DB writes) may still call get_current_user() directly — the result is cheap
    because the session is already loaded by SessionMiddleware at this point.
    """

    async def dispatch(self, request: Request, call_next):
        request.state.user = None
        request.state.balance = 0
        request.state.is_production = _IS_PRODUCTION

        if not any(request.url.path.startswith(p) for p in _SKIP_PREFIXES):
            from app.identity.adapters.fastapi_deps import get_current_user

            user = await get_current_user(request)
            request.state.user = user
            if user:
                try:
                    from app.billing.use_cases.manage_credits import get_balance
                    from app.infrastructure.persistence.database import async_session

                    async with async_session() as db:
                        request.state.balance = await get_balance(db, user.id)
                except Exception:
                    logger.exception("Failed to read credit balance for user %s", user.id)
                user_id_var.set(user.id)
                from app.infrastructure.instrumentation import add_custom_attributes
                add_custom_attributes({"user_id": user.id})

        return await call_next(request)
