"""Auth dependencies for FastAPI routes."""

from fastapi import HTTPException, Request
from sqlalchemy import select

from app.identity.adapters.token_utils import decode_access_token
from app.infrastructure.persistence.database import async_session
from app.infrastructure.persistence.orm_models import Credit, User


async def get_current_user(request: Request) -> User | None:
    """Get the current authenticated user from session cookie, or None."""
    token = request.state.session.get("auth_token")
    if not token:
        return None

    payload = decode_access_token(token)
    if not payload:
        return None

    async with async_session() as db:
        result = await db.execute(select(User).where(User.id == payload["sub"]))
        return result.scalar_one_or_none()


async def get_user_credits(user: User) -> int:
    """Get total credit balance for a user."""
    if not user:
        return 0
    async with async_session() as db:
        result = await db.execute(
            select(Credit.balance).where(Credit.user_id == user.id)
        )
        row = result.scalar_one_or_none()
        return row or 0


async def require_auth(request: Request) -> User:
    """Dependency: return the authenticated user or redirect to /login."""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return user
