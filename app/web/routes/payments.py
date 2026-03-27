"""Stripe payment routes: checkout session creation and webhook handling."""

import logging
import os

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from app.billing.entities import (
    ALPHA_PACK_CREDITS,
    ALPHA_PACK_PRICE_CENTS,
    TOPUP_PACKS,
)
from app.billing.use_cases.manage_credits import (
    add_credits,
    get_balance,
)
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


@router.get("/pricing")
async def pricing_page(request: Request):
    async with async_session() as db:
        alpha_count = await count_alpha_users(db)

    spots_remaining = max(0, 200 - alpha_count)

    return templates.TemplateResponse(
        "pricing.html",
        {
            "request": request,
            "spots_remaining": spots_remaining,
            "alpha_count": alpha_count,
            "stripe_enabled": bool(STRIPE_SECRET_KEY),
            "topup_packs": TOPUP_PACKS,
            "page_description": "QuillCV pricing — $29 for 40 ATS-optimized CV generations during alpha. Credits never expire. No subscriptions.",
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
        success_url=f"{base_url}/checkout/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{base_url}/pricing",
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

    stripe = _get_stripe()

    base_url = str(request.base_url).rstrip("/")
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
        success_url=f"{base_url}/checkout/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{base_url}/pricing",
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
    """Post-checkout success page. Verify with Stripe and grant credits."""
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
                    # Check if we already processed this
                    from sqlalchemy import select

                    result = await db.execute(select(Payment).where(Payment.stripe_session_id == session_id))
                    payment = result.scalar_one_or_none()
                    if payment and payment.status != "completed":
                        payment.status = "completed"
                        payment.stripe_payment_intent = session.payment_intent
                        await db.commit()

                        await add_credits(db, user.id, credits_granted)

                        from app.infrastructure.instrumentation import record_custom_event

                        record_custom_event(
                            "CreditPurchase",
                            {
                                "user_id": user.id,
                                "credits_granted": credits_granted,
                                "amount_cents": payment.amount_cents,
                                "currency": payment.currency or "aud",
                                "stripe_session_id": session_id,
                            },
                        )

                        # Refresh cached balance in session so nav bar updates immediately.
                        new_balance = await get_balance(db, user.id)
                        request.state.session["cached_balance"] = new_balance

                        # Send payment confirmation email — non-fatal on failure
                        try:
                            await send_payment_confirmation_email(
                                to_email=user.email,
                                name=getattr(user, "name", "") or "",
                                credits=credits_granted,
                                amount_cents=payment.amount_cents,
                                currency=payment.currency.upper() if payment.currency else "AUD",
                            )
                        except Exception:
                            logger.exception("Failed to send payment confirmation email to %s", user.email)
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
    """Handle Stripe webhook events (payment confirmation)."""
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

        if user_id and session.get("payment_status") == "paid":
            pack_id = session.get("metadata", {}).get("pack", "alpha")
            if pack_id in TOPUP_PACKS:
                credits_to_grant = TOPUP_PACKS[pack_id]["credits"]
            else:
                credits_to_grant = ALPHA_PACK_CREDITS

            async with async_session() as db:
                from sqlalchemy import select

                from app.infrastructure.persistence.orm_models import User as _User

                result = await db.execute(select(Payment).where(Payment.stripe_session_id == session_id))
                payment = result.scalar_one_or_none()
                if payment and payment.status != "completed":
                    payment.status = "completed"
                    payment.stripe_payment_intent = session.get("payment_intent")
                    await db.commit()

                    await add_credits(db, user_id, credits_to_grant)

                    from app.infrastructure.instrumentation import record_custom_event

                    record_custom_event(
                        "CreditPurchase",
                        {
                            "user_id": user_id,
                            "credits_granted": credits_to_grant,
                            "amount_cents": payment.amount_cents,
                            "currency": payment.currency or "aud",
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
                                credits=credits_to_grant,
                                amount_cents=payment.amount_cents,
                                currency=payment.currency.upper() if payment.currency else "AUD",
                            )
                    except Exception:
                        logger.exception(
                            "Failed to send payment confirmation email for webhook session %s",
                            session_id,
                        )

    elif event["type"] in ("checkout.session.expired", "checkout.session.async_payment_failed"):
        session = event["data"]["object"]
        session_id = session["id"]
        user_id = session.get("metadata", {}).get("user_id")
        new_status = "expired" if event["type"] == "checkout.session.expired" else "failed"

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
