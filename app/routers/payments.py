"""Stripe payment routes: checkout session creation and webhook handling."""

import logging
import os
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth.dependencies import get_current_user
from app.database import async_session
from app.models import Payment
from app.services.credit_service import (
    ALPHA_PACK_CREDITS,
    ALPHA_PACK_PRICE_CENTS,
    TOPUP_PACKS,
    add_credits,
)
from app.services.user_service import count_alpha_users

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")

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

    return templates.TemplateResponse("pricing.html", {
        "request": request,
        "spots_remaining": spots_remaining,
        "alpha_count": alpha_count,
        "stripe_enabled": bool(STRIPE_SECRET_KEY),
        "topup_packs": TOPUP_PACKS,
        "page_description": "QuillCV pricing — $29 for 40 ATS-optimized CV generations during alpha. Credits never expire. No subscriptions.",
    })


@router.post("/checkout/alpha")
async def create_alpha_checkout(request: Request):
    """Create a Stripe checkout session for the alpha pack."""
    user = await get_current_user(request)
    if not user:
        return RedirectResponse("/login?next=/pricing", status_code=303)

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
        line_items=[{
            "price": STRIPE_PRICE_ID,
            "quantity": 1,
        }] if STRIPE_PRICE_ID else [{
            "price_data": {
                "currency": "aud",
                "product_data": {
                    "name": "QuillCV Alpha Pack — 40 CV Generations",
                    "description": "Founders cohort. Credits never expire.",
                },
                "unit_amount": ALPHA_PACK_PRICE_CENTS,
            },
            "quantity": 1,
        }],
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
async def create_topup_checkout(request: Request, pack_id: str):
    """Create a Stripe checkout session for a top-up credit pack."""
    user = await get_current_user(request)
    if not user:
        return RedirectResponse("/login?next=/pricing", status_code=303)

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
        line_items=[{
            "price_data": {
                "currency": "aud",
                "product_data": {
                    "name": f"QuillCV — {pack['name']}",
                    "description": "Credits never expire.",
                },
                "unit_amount": pack["price_cents"],
            },
            "quantity": 1,
        }],
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
async def checkout_success(request: Request, session_id: str = ""):
    """Post-checkout success page. Verify with Stripe and grant credits."""
    user = await get_current_user(request)
    if not user or not session_id:
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
                    result = await db.execute(
                        select(Payment).where(Payment.stripe_session_id == session_id)
                    )
                    payment = result.scalar_one_or_none()
                    if payment and payment.status != "completed":
                        payment.status = "completed"
                        payment.stripe_payment_intent = session.payment_intent
                        await db.commit()

                        await add_credits(db, user.id, credits_granted)
        except Exception:
            logger.exception("Error verifying checkout session")

    return templates.TemplateResponse("checkout_success.html", {
        "request": request,
        "credits": credits_granted,
    })


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
                result = await db.execute(
                    select(Payment).where(Payment.stripe_session_id == session_id)
                )
                payment = result.scalar_one_or_none()
                if payment and payment.status != "completed":
                    payment.status = "completed"
                    payment.stripe_payment_intent = session.get("payment_intent")
                    await db.commit()

                    await add_credits(db, user_id, credits_to_grant)

    return {"status": "ok"}
