"""Atomic credit grant for completed Stripe checkouts.

This module exists to ensure credit grants happen exactly once per Stripe
session, even when the success-redirect handler and the webhook handler
race each other (which is the common case — Stripe redirects the user back
to /checkout/success at the same moment it fires the webhook).

The trick: do the status transition with an atomic UPDATE ... WHERE
status = 'pending' RETURNING ...  — whichever caller wins gets a row
back; the loser gets nothing and skips the credit grant. Using `pending`
(rather than `!= completed`) also prevents `failed`/`expired` rows from
being flipped to `completed` by a late or replayed webhook. The DB does
the mutual exclusion for us, no app-level lock needed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.use_cases.manage_credits import add_credits
from app.infrastructure.persistence.orm_models import Payment, User

logger = logging.getLogger(__name__)


@dataclass
class GrantResult:
    """Outcome of attempting to grant credits for a Stripe session.

    granted=True means *this* call performed the work (transitioned
    pending→completed and added credits). granted=False means another
    path already handled it (or the row doesn't exist) and we no-opped.
    """

    granted: bool
    payment_id: str | None = None
    user_id: str | None = None
    amount_cents: int | None = None
    currency: str | None = None
    credits_granted: int | None = None


async def grant_purchase_credits(
    db: AsyncSession,
    *,
    stripe_session_id: str,
    stripe_payment_intent: str | None,
    pack_id: str = "alpha",
) -> GrantResult:
    """Atomically transition a Payment to completed and grant credits.

    Uses UPDATE ... RETURNING to claim the row in a single statement, so
    concurrent callers (webhook + success-redirect) are mutually exclusive
    by virtue of the DB. The first caller commits the status change and
    grants credits; subsequent callers see no rows returned and exit
    without granting.

    Postgres supports RETURNING natively. SQLite supports it from 3.35
    onwards (the test suite runs on 3.40+) so the same code path works
    in tests.
    """

    result = await db.execute(
        update(Payment)
        .where(
            Payment.stripe_session_id == stripe_session_id,
            Payment.status == "pending",
        )
        .values(
            status="completed",
            stripe_payment_intent=stripe_payment_intent,
        )
        .returning(
            Payment.id,
            Payment.user_id,
            Payment.amount_cents,
            Payment.currency,
            Payment.credits_granted,
        )
    )
    row = result.first()
    await db.commit()

    if row is None:
        # Either: (a) another path already completed this session, or
        # (b) no Payment row exists for this session_id. Either way we
        # don't grant credits.
        logger.info(
            "grant_purchase_credits: no-op for session %s (already completed or missing)",
            stripe_session_id,
        )
        return GrantResult(granted=False)

    payment_id, user_id, amount_cents, currency, credits_granted = row

    await add_credits(db, user_id, credits_granted)

    if pack_id == "alpha":
        await db.execute(
            update(User)
            .where(User.id == user_id, User.tier == "public")
            .values(tier="founder")
        )
        await db.commit()
        logger.info(
            "grant_purchase_credits: upgraded user %s to founder tier",
            user_id,
        )

    logger.info(
        "grant_purchase_credits: granted %d credits to user %s for session %s",
        credits_granted,
        user_id,
        stripe_session_id,
    )

    return GrantResult(
        granted=True,
        payment_id=payment_id,
        user_id=user_id,
        amount_cents=amount_cents,
        currency=currency,
        credits_granted=credits_granted,
    )
