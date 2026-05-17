"""Atomic credit clawback when a Stripe charge is refunded.

Called by the ``charge.refunded`` webhook handler.  Uses the same
UPDATE ... RETURNING pattern as grant_purchase_credits to prevent
double-clawback if Stripe replays the event.

Policy on negative balances
----------------------------
We intentionally allow the balance to go negative after a refund.
Clamping to zero would let a user spend their credits *then* get
a full refund and keep the CV outputs for free.  A negative balance
means subsequent ``deduct_credit`` calls will fail (balance must be
> 0), so the user is effectively locked out until they buy again.
Admins can manually zero-out the balance via /admin if needed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.use_cases.manage_credits import add_credits
from app.infrastructure.persistence.orm_models import Payment

logger = logging.getLogger(__name__)


@dataclass
class ReverseResult:
    """Outcome of a credit clawback attempt.

    reversed=True  — this call found the payment row (status='completed'),
                     flipped it to 'refunded', and decremented credits.
    reversed=False — already refunded (idempotent no-op) or row missing.
    """

    reversed: bool
    payment_id: str | None = None
    user_id: str | None = None
    credits_reversed: int | None = None


async def reverse_purchase_credits(
    db: AsyncSession,
    *,
    stripe_payment_intent: str,
) -> ReverseResult:
    """Atomically clawback credits for a refunded Stripe payment.

    Matches by ``stripe_payment_intent`` because ``charge.refunded``
    provides the payment-intent ID (not the checkout session ID).

    The status transition  completed → refunded  is the mutual-exclusion
    guard: only one caller can win the RETURNING row.  Subsequent calls
    (Stripe webhook replays) get no row back and become no-ops.
    """
    result = await db.execute(
        update(Payment)
        .where(
            Payment.stripe_payment_intent == stripe_payment_intent,
            Payment.status == "completed",
        )
        .values(status="refunded")
        .returning(
            Payment.id,
            Payment.user_id,
            Payment.credits_granted,
        )
    )
    row = result.first()
    await db.commit()

    if row is None:
        logger.info(
            "reverse_purchase_credits: no-op for payment_intent %s "
            "(already refunded, not yet completed, or not found)",
            stripe_payment_intent,
        )
        return ReverseResult(reversed=False)

    payment_id, user_id, credits_granted = row

    # Negative amount — add_credits handles negative deltas by adjusting
    # balance only (never decrements lifetime total_purchased counter).
    # Balance is intentionally allowed to go negative; see module docstring.
    await add_credits(db, user_id, -credits_granted)

    logger.info(
        "reverse_purchase_credits: clawed back %d credits from user %s "
        "(payment_intent %s)",
        credits_granted,
        user_id,
        stripe_payment_intent,
    )

    return ReverseResult(
        reversed=True,
        payment_id=payment_id,
        user_id=user_id,
        credits_reversed=credits_granted,
    )
