"""User management: creation, lookup, OAuth linking."""

from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, Credit
from app.auth.utils import hash_password, verify_password


async def create_user(db: AsyncSession, email: str, password: str | None = None, name: str = "",
                      provider: str | None = None, provider_id: str | None = None) -> User:
    """Create a new user with optional password or OAuth provider."""
    user = User(
        email=email.lower().strip(),
        name=name,
        password_hash=hash_password(password) if password else None,
        provider=provider,
        provider_id=provider_id,
    )
    db.add(user)
    await db.flush()  # Ensure user.id is populated

    # Create empty credit record
    credit = Credit(user_id=user.id, balance=0, total_purchased=0, total_used=0)
    db.add(credit)

    await db.commit()
    await db.refresh(user)
    return user


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email.lower().strip()))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_provider(db: AsyncSession, provider: str, provider_id: str) -> User | None:
    result = await db.execute(
        select(User).where(User.provider == provider, User.provider_id == provider_id)
    )
    return result.scalar_one_or_none()


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    """Verify email + password. Returns user or None."""
    user = await get_user_by_email(db, email)
    if not user or not user.password_hash:
        return None
    if not verify_password(password, user.password_hash):
        return None
    user.last_login = datetime.now(timezone.utc)
    await db.commit()
    return user


async def update_last_login(db: AsyncSession, user: User):
    user.last_login = datetime.now(timezone.utc)
    await db.commit()


async def count_alpha_users(db: AsyncSession) -> int:
    """Count users who have purchased credits (alpha founders)."""
    result = await db.execute(
        select(func.count()).select_from(Credit).where(Credit.total_purchased > 0)
    )
    return result.scalar() or 0
