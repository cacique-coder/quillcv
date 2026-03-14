"""Application-level middleware for QuillCV."""

import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

_SKIP_PREFIXES = ("/static/", "/favicon.ico")
_IS_PRODUCTION = os.environ.get("APP_ENV", "development") == "production"


class AuthContextMiddleware(BaseHTTPMiddleware):
    """Inject authenticated user and credit balance into request.state for every request.

    This eliminates the need for each router to call get_current_user() and
    get_balance() solely for populating nav template variables.  Routers that
    need the user for *business logic* (auth guards, redirects, DB writes) may
    still call get_current_user() directly — the result is cheap because the
    session is already loaded by SessionMiddleware at this point.
    """

    async def dispatch(self, request: Request, call_next):
        request.state.user = None
        request.state.balance = 0
        request.state.is_production = _IS_PRODUCTION

        if not any(request.url.path.startswith(p) for p in _SKIP_PREFIXES):
            from app.auth.dependencies import get_current_user
            from app.database import async_session
            from app.services.credit_service import get_balance

            user = await get_current_user(request)
            request.state.user = user
            if user:
                async with async_session() as db:
                    request.state.balance = await get_balance(db, user.id)

        return await call_next(request)
