"""Credit management: purchase, deduct, check balance."""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.orm_models import Credit
from app.billing.entities import (
    ALPHA_PACK_CREDITS,
    ALPHA_PACK_PRICE_CENTS,
    ALPHA_USER_CAP,
    TOPUP_PACKS,
)


async def get_balance(db: AsyncSession, user_id: str) -> int:
    result = await db.execute(select(Credit.balance).where(Credit.user_id == user_id))
    return result.scalar_one_or_none() or 0


async def deduct_credit(db: AsyncSession, user_id: str) -> bool:
    """Atomically deduct 1 credit. Returns True if successful, False if insufficient."""
    result = await db.execute(
        update(Credit)
        .where(Credit.user_id == user_id, Credit.balance > 0)
        .values(
            balance=Credit.balance - 1,
            total_used=Credit.total_used + 1,
        )
        .execution_options(synchronize_session=False)
    )
    await db.commit()
    return result.rowcount > 0


async def add_credits(db: AsyncSession, user_id: str, amount: int):
    """Add credits to a user's account."""
    result = await db.execute(
        update(Credit)
        .where(Credit.user_id == user_id)
        .values(
            balance=Credit.balance + amount,
            total_purchased=Credit.total_purchased + amount,
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount == 0:
        # No credit record exists — create one
        db.add(Credit(user_id=user_id, balance=amount, total_purchased=amount, total_used=0))
    await db.commit()


async def has_credits(db: AsyncSession, user_id: str) -> bool:
    return (await get_balance(db, user_id)) > 0
