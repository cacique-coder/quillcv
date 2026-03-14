"""Credit management: purchase, deduct, check balance."""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Credit

ALPHA_PACK_CREDITS = 40
ALPHA_PACK_PRICE_CENTS = 2900  # $29.00 AUD
ALPHA_USER_CAP = 100

TOPUP_PACKS = {
    "starter": {"credits": 10, "price_cents": 1500, "name": "Starter — 10 Credits", "per_credit": "$1.50"},
    "standard": {"credits": 25, "price_cents": 3000, "name": "Standard — 25 Credits", "per_credit": "$1.20"},
    "pro": {"credits": 50, "price_cents": 4900, "name": "Pro — 50 Credits", "per_credit": "$0.98"},
}


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
