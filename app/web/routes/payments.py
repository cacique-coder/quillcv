"""Stripe payment routes: checkout session creation and webhook handling."""

import logging
import os

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from app.billing.entities import (
    ALPHA_PACK_CREDITS,
    ALPHA_PACK_PRICE_CENTS,
    TOPUP_PACKS,
    user_can_see_pack,
)
from app.billing.session_balance import set_cached_balance
from app.billing.use_cases.grant_purchase_credits import grant_purchase_credits
from app.billing.use_cases.manage_credits import (
    get_balance,
)
from app.billing.use_cases.reverse_purchase_credits import reverse_purchase_credits
from app.identity.adapters.fastapi_deps import require_auth
from app.identity.use_cases.authenticate import count_alpha_users
from app.infrastructure.email.smtp import send_payment_confirmation_email
from app.infrastructure.persistence.database import async_session
from app.infrastructure.persistence.orm_models import Payment, User
from app.web.templates import templates

logger = logging.getLogger(__name__)

router = APIRouter()

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_ID = os.environ.get("STRIPE_PRICE_ID", "")  # Alpha pack price ID


def _get_stripe():
    """Lazy import stripe to avoid startup errors when key isn't set."""
    import stripe

    stripe.api_key = STRIPE_SECRET_KEY
    return stripe


# Friendly messages for ?error=… and ?status=… query params on /pricing.
# Kept in code (not just template) so the strings are easy to grep and
# adjust without round-tripping through Jinja.
_PRICING_ERROR_MESSAGES = {
    "payments_not_configured": (
        "Payments aren't configured yet — please email hello@quillcv.com "
        "and we'll sort you out."
    ),
    "sold_out": (
        "Alpha is sold out for the moment. Top-up packs below are still available."
    ),
    "invalid_pack": (
        "That top-up pack doesn't exist. Pick one of the packs below."
    ),
    "tier_locked": (
        "That pack is reserved for founders. Pick one of the packs below."
    ),
}


@router.get("/pricing")
async def pricing_page(
    request: Request,
    error: str = "",
    status: str = "",
    pack: str = "",
):
    async with async_session() as db:
        alpha_count = await count_alpha_users(db)

    spots_remaining = max(0, 200 - alpha_count)

    error_message = _PRICING_ERROR_MESSAGES.get(error) if error else None

    # Cancelled-checkout banner needs to know which pack to retry. "alpha"
    # routes back to /checkout/alpha; anything in TOPUP_PACKS routes to
    # /checkout/topup/{pack}. Anything else, we drop the retry button and
    # just show a plain cancel notice.
    cancel_retry_url = None
    if status == "cancelled":
        if pack == "alpha":
            cancel_retry_url = "/checkout/alpha"
        elif pack in TOPUP_PACKS:
            cancel_retry_url = f"/checkout/topup/{pack}"

    return templates.TemplateResponse(
        "pricing.html",
        {
            "request": request,
            "spots_remaining": spots_remaining,
            "alpha_count": alpha_count,
            "stripe_enabled": bool(STRIPE_SECRET_KEY),
            "topup_packs": TOPUP_PACKS,
            "page_description": "QuillCV pricing — $29 for 40 ATS-optimized CV generations during alpha. Credits never expire. No subscriptions.",
            "error_code": error or None,
            "error_message": error_message,
            "checkout_status": status or None,
            "cancel_pack": pack or None,
            "cancel_retry_url": cancel_retry_url,
        },
    )


@router.get("/account/topup")
async def topup_page(
    request: Request,
    error: str = "",
    user: User = Depends(require_auth),
):
    """In-app credit top-up page."""
    user_tier = getattr(user, "tier", "public")
    visible_packs = {
        pack_id: pack
        for pack_id, pack in TOPUP_PACKS.items()
        if user_can_see_pack(pack, user_tier)
    }
    error_message = _PRICING_ERROR_MESSAGES.get(error) if error else None
    return templates.TemplateResponse(
        "topup.html",
        {
            "request": request,
            "topup_packs": visible_packs,
            "stripe_enabled": bool(STRIPE_SECRET_KEY),
            "balance": request.state.balance,
            "page_title": "Top up credits",
            "error_message": error_message,
        },
    )


@router.post("/checkout/alpha")
async def create_alpha_checkout(request: Request, user: User = Depends(require_auth)):
    """Create a Stripe checkout session for the alpha pack."""

    if not STRIPE_SECRET_KEY:
        return RedirectResponse("/pricing?error=payments_not_configured", status_code=303)

    # Check alpha cap
    async with async_session() as db:
        alpha_count = await count_alpha_users(db)
    if alpha_count >= 100:
        return RedirectResponse("/pricing?error=sold_out", status_code=303)

    stripe = _get_stripe()

    base_url = str(request.base_url).rstrip("/")
    # NOTE: automatic_tax requires Stripe Tax to be enabled in the dashboard
    # with at least one tax registration (start with AU GST). Until then
    # Stripe will simply collect $0 tax. See docs/ops/stripe-tax-setup.md.
    # invoice_creation makes Stripe send the customer a hosted PDF receipt
    # (legal/tax document). Our own confirmation email is still sent —
    # they're complementary, not duplicates.
    session = stripe.checkout.Session.create(
        mode="payment",
        customer_email=user.email,
        metadata={"user_id": user.id, "pack": "alpha"},
        line_items=[
            {
                "price": STRIPE_PRICE_ID,
                "quantity": 1,
            }
        ]
        if STRIPE_PRICE_ID
        else [
            {
                "price_data": {
                    "currency": "aud",
                    "product_data": {
                        "name": "QuillCV Alpha Pack — 40 CV Generations",
                        "description": "Founders cohort. Credits never expire.",
                    },
                    "unit_amount": ALPHA_PACK_PRICE_CENTS,
                },
                "quantity": 1,
            }
        ],
        invoice_creation={"enabled": True},
        automatic_tax={"enabled": True},
        success_url=f"{base_url}/checkout/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{base_url}/pricing?status=cancelled&pack=alpha",
    )

    # Record pending payment
    async with async_session() as db:
        payment = Payment(
            user_id=user.id,
            stripe_session_id=session.id,
            amount_cents=ALPHA_PACK_PRICE_CENTS,
            credits_granted=ALPHA_PACK_CREDITS,
            status="pending",
        )
        db.add(payment)
        await db.commit()

    return RedirectResponse(session.url, status_code=303)


@router.post("/checkout/topup/{pack_id}")
async def create_topup_checkout(request: Request, pack_id: str, user: User = Depends(require_auth)):
    """Create a Stripe checkout session for a top-up credit pack."""

    if not STRIPE_SECRET_KEY:
        return RedirectResponse("/pricing?error=payments_not_configured", status_code=303)

    pack = TOPUP_PACKS.get(pack_id)
    if not pack:
        return RedirectResponse("/pricing?error=invalid_pack", status_code=303)

    if not user_can_see_pack(pack, getattr(user, "tier", "public")):
        logger.info(
            "TopupBlocked user_id=%s pack=%s required_tier=%s user_tier=%s",
            user.id, pack_id, pack.get("tier"), getattr(user, "tier", "public"),
        )
        return RedirectResponse("/account/topup?error=tier_locked", status_code=303)

    stripe = _get_stripe()

    base_url = str(request.base_url).rstrip("/")
    # See alpha route comment re: automatic_tax + invoice_creation.
    session = stripe.checkout.Session.create(
        mode="payment",
        customer_email=user.email,
        metadata={"user_id": user.id, "pack": pack_id},
        line_items=[
            {
                "price_data": {
                    "currency": "aud",
                    "product_data": {
                        "name": f"QuillCV — {pack['name']}",
                        "description": "Credits never expire.",
                    },
                    "unit_amount": pack["price_cents"],
                },
                "quantity": 1,
            }
        ],
        invoice_creation={"enabled": True},
        automatic_tax={"enabled": True},
        success_url=f"{base_url}/checkout/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{base_url}/pricing?status=cancelled&pack={pack_id}",
    )

    # Record pending payment
    async with async_session() as db:
        payment = Payment(
            user_id=user.id,
            stripe_session_id=session.id,
            amount_cents=pack["price_cents"],
            credits_granted=pack["credits"],
            status="pending",
        )
        db.add(payment)
        await db.commit()

    return RedirectResponse(session.url, status_code=303)


@router.get("/checkout/success")
async def checkout_success(
    request: Request,
    session_id: str = "",
    user: User = Depends(require_auth),
):
    """Post-checkout success page. Verify with Stripe and grant credits.

    Concurrent webhook + success-redirect hits are safe: the credit grant
    runs inside grant_purchase_credits() which uses an atomic
    UPDATE ... WHERE status != 'completed' RETURNING ... — only one caller
    wins the transition and grants credits.
    """
    if not session_id:
        return RedirectResponse("/", status_code=303)

    credits_granted = ALPHA_PACK_CREDITS

    if STRIPE_SECRET_KEY:
        stripe = _get_stripe()
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            if session.payment_status == "paid":
                pack_id = (session.metadata or {}).get("pack", "alpha")
                if pack_id in TOPUP_PACKS:
                    credits_granted = TOPUP_PACKS[pack_id]["credits"]
                else:
                    credits_granted = ALPHA_PACK_CREDITS

                async with async_session() as db:
                    grant = await grant_purchase_credits(
                        db,
                        stripe_session_id=session_id,
                        stripe_payment_intent=session.payment_intent,
                        pack_id=pack_id,
                    )

                    if grant.granted:
                        # We won the race — record analytics + email.
                        # Use credits_granted from the DB row (source of
                        # truth) rather than the locally-computed value.
                        credits_granted = grant.credits_granted or credits_granted

                        from app.infrastructure.instrumentation import record_custom_event

                        record_custom_event(
                            "CreditPurchase",
                            {
                                "user_id": user.id,
                                "credits_granted": grant.credits_granted,
                                "amount_cents": grant.amount_cents,
                                "currency": grant.currency or "aud",
                                "stripe_session_id": session_id,
                            },
                        )

                        # Refresh cached balance in session so nav bar updates immediately.
                        new_balance = await get_balance(db, user.id)
                        set_cached_balance(request.state.session, new_balance)

                        # Send payment confirmation email — non-fatal on failure
                        try:
                            await send_payment_confirmation_email(
                                to_email=user.email,
                                name=getattr(user, "name", "") or "",
                                credits=grant.credits_granted,
                                amount_cents=grant.amount_cents,
                                currency=(grant.currency or "aud").upper(),
                            )
                        except Exception:
                            logger.exception("Failed to send payment confirmation email to %s", user.email)
                    else:
                        # Already granted (likely by webhook). Refresh
                        # the cached balance so the success page still
                        # renders correct numbers in the nav bar.
                        new_balance = await get_balance(db, user.id)
                        set_cached_balance(request.state.session, new_balance)
        except Exception:
            logger.exception("Error verifying checkout session")

    return templates.TemplateResponse(
        "checkout_success.html",
        {
            "request": request,
            "credits": credits_granted,
        },
    )


@router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events (payment confirmation).

    See checkout_success() for a note on race-safety with the success
    redirect path — both call grant_purchase_credits() which serialises
    the status transition at the DB level.
    """
    if not STRIPE_SECRET_KEY or not STRIPE_WEBHOOK_SECRET:
        return {"status": "not_configured"}

    stripe = _get_stripe()
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except Exception:
        logger.exception("Stripe webhook signature verification failed")
        return {"status": "invalid_signature"}

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        session_id = session["id"]
        user_id = session.get("metadata", {}).get("user_id")

        webhook_pack_id = session.get("metadata", {}).get("pack", "alpha")
        if user_id and session.get("payment_status") == "paid":
            async with async_session() as db:
                from sqlalchemy import select

                from app.infrastructure.persistence.orm_models import User as _User

                grant = await grant_purchase_credits(
                    db,
                    stripe_session_id=session_id,
                    stripe_payment_intent=session.get("payment_intent"),
                    pack_id=webhook_pack_id,
                )

                if grant.granted:
                    from app.infrastructure.instrumentation import record_custom_event

                    record_custom_event(
                        "CreditPurchase",
                        {
                            "user_id": user_id,
                            "credits_granted": grant.credits_granted,
                            "amount_cents": grant.amount_cents,
                            "currency": grant.currency or "aud",
                            "stripe_session_id": session_id,
                        },
                    )

                    # Send payment confirmation email — look up user for name + email
                    try:
                        user_result = await db.execute(select(_User).where(_User.id == user_id))
                        webhook_user = user_result.scalar_one_or_none()
                        if webhook_user:
                            await send_payment_confirmation_email(
                                to_email=webhook_user.email,
                                name=webhook_user.name or "",
                                credits=grant.credits_granted,
                                amount_cents=grant.amount_cents,
                                currency=(grant.currency or "aud").upper(),
                            )
                    except Exception:
                        logger.exception(
                            "Failed to send payment confirmation email for webhook session %s",
                            session_id,
                        )

    elif event["type"] == "charge.refunded":
        # A charge (and therefore payment) was refunded by the merchant or
        # requested by the customer.  We claw back the credits that were
        # granted when the payment completed.  Stripe provides the
        # payment_intent ID on the charge object.
        #
        # Invariant on async_payment_failed: for Stripe Checkout one-time
        # payments, checkout.session.async_payment_failed fires BEFORE the
        # session ever reaches `payment_status=paid`, so
        # grant_purchase_credits never runs for them — there are no credits
        # to claw back.  We only mark the pending row as failed (below).
        # charge.refunded is the correct event for post-completion reversals.
        charge = event["data"]["object"]
        payment_intent = charge.get("payment_intent")
        if payment_intent:
            async with async_session() as db:
                reverse_result = await reverse_purchase_credits(
                    db,
                    stripe_payment_intent=payment_intent,
                )
            if reverse_result.reversed:
                logger.warning(
                    "Stripe refund: clawed back %d credits from user %s "
                    "(payment_intent %s)",
                    reverse_result.credits_reversed,
                    reverse_result.user_id,
                    payment_intent,
                )
            else:
                logger.info(
                    "Stripe refund: no-op for payment_intent %s "
                    "(already reversed or payment not found)",
                    payment_intent,
                )
        else:
            logger.warning("charge.refunded event missing payment_intent: %r", charge)

    elif event["type"] in ("checkout.session.expired", "checkout.session.async_payment_failed"):
        session = event["data"]["object"]
        session_id = session["id"]
        user_id = session.get("metadata", {}).get("user_id")
        new_status = "expired" if event["type"] == "checkout.session.expired" else "failed"

        # async_payment_failed fires before the session reaches payment_status=paid,
        # so grant_purchase_credits never ran for it — no credits to claw back.
        # We only mark the pending row as failed here.
        logger.warning(
            "Stripe payment %s for session %s user_id=%s",
            event["type"],
            session_id,
            user_id,
        )

        async with async_session() as db:
            from sqlalchemy import select

            result = await db.execute(select(Payment).where(Payment.stripe_session_id == session_id))
            payment = result.scalar_one_or_none()
            if payment and payment.status == "pending":
                payment.status = new_status
                await db.commit()
                logger.info(
                    "Payment %s marked %s (session %s user_id=%s)",
                    payment.id,
                    new_status,
                    session_id,
                    user_id,
                )

    return {"status": "ok"}
