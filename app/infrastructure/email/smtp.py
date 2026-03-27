"""Mailgun email service for QuillCV.

Async integration using httpx (already in requirements.txt).
US Mailgun region: api.mailgun.net

Dev mode detection: when SESSION_SECRET is the default dev value, emails are
logged rather than sent, so no real credentials are needed locally.

Usage:
    from app.services.email_service import send_welcome_email, send_invitation_email
    await send_welcome_email(to_email="user@example.com", name="Alice")
"""

from __future__ import annotations

import logging
import os
import re
from enum import StrEnum
from pathlib import Path

import httpx
from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MAILGUN_API_KEY = os.environ.get("MAILGUN_API_KEY", "")
MAILGUN_DOMAIN = os.environ.get("MAILGUN_DOMAIN", "")
MAILGUN_API_BASE = "https://api.mailgun.net/v3"

# In sandbox/dev, Mailgun requires the from address to use the sandbox domain.
_IS_SANDBOX = MAILGUN_DOMAIN.startswith("sandbox") if MAILGUN_DOMAIN else False
FROM_ADDRESS = (
    f"QuillCV <postmaster@{MAILGUN_DOMAIN}>"
    if _IS_SANDBOX
    else f"QuillCV <noreply@{MAILGUN_DOMAIN}>"
)

# Dev mode: True when using the default development session secret.
# Note: even in dev mode, if Mailgun credentials are set we send real emails
# (to the sandbox) so you can test the full flow.
_IS_DEV_MODE = (
    os.environ.get("SESSION_SECRET", "quillcv-dev-secret-change-in-prod")
    == "quillcv-dev-secret-change-in-prod"
)

# Jinja2 environment scoped to the email templates directory.
_TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates" / "emails"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
    trim_blocks=True,
    lstrip_blocks=True,
)

# Simple RFC-5322-ish email pattern for fast validation (not exhaustive).
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------------------------------------------------------------------------
# Email type enum — separation between transactional and marketing
# ---------------------------------------------------------------------------

class EmailType(StrEnum):
    """Category of email — used for Mailgun tagging and future routing rules."""
    TRANSACTIONAL = "transactional"
    MARKETING = "marketing"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _validate_email(address: str) -> None:
    """Raise ValueError if *address* does not look like a valid email."""
    if not address or not _EMAIL_RE.match(address.strip()):
        raise ValueError(f"Invalid email address: {address!r}")


def _render(template_name: str, context: dict) -> str:
    """Render a Jinja2 template by name with the given context dict."""
    tmpl = _jinja_env.get_template(template_name)
    return tmpl.render(**context)


async def _send(
    *,
    to: str,
    subject: str,
    html: str,
    text: str,
    email_type: EmailType = EmailType.TRANSACTIONAL,
    tags: list[str] | None = None,
) -> bool:
    """Send a multipart email via the Mailgun API.

    Returns True on success.  In dev mode the email is logged instead.
    Retries once on transient HTTP errors (5xx / network timeout).
    """
    _validate_email(to)

    all_tags = [email_type.value] + (tags or [])

    if not MAILGUN_API_KEY or not MAILGUN_DOMAIN:
        logger.info(
            "[EMAIL DEV] to=%s subject=%r tags=%s\n--- TEXT ---\n%s",
            to, subject, all_tags, text,
        )
        return True

    url = f"{MAILGUN_API_BASE}/{MAILGUN_DOMAIN}/messages"
    data: dict = {
        "from": FROM_ADDRESS,
        "to": to,
        "subject": subject,
        "html": html,
        "text": text,
        # Mailgun tracking tag parameter
        "o:tag": all_tags,
        # Mark as transactional so Mailgun skips unsubscribe footer for these
        "h:X-Mailgun-Tag": ", ".join(all_tags),
        # RFC 2369 List-Unsubscribe placeholder (populated per email below)
        "h:List-Unsubscribe": "<mailto:unsubscribe@quillcv.com>",
        "h:X-Mailer": "QuillCV/1.0",
    }

    async def _attempt() -> httpx.Response:
        async with httpx.AsyncClient(timeout=15.0) as client:
            return await client.post(
                url,
                auth=("api", MAILGUN_API_KEY),
                data=data,
            )

    for attempt in range(2):
        try:
            response = await _attempt()
            if response.status_code == 200:
                logger.info(
                    "Email sent to %s (subject=%r tags=%s)",
                    to, subject, all_tags,
                )
                return True
            if response.status_code < 500 or attempt == 1:
                # 4xx = permanent failure or second attempt failed — do not retry
                logger.error(
                    "Mailgun error %d for %s: %s",
                    response.status_code, to, response.text[:200],
                )
                return False
            # 5xx on first attempt — fall through to retry
            logger.warning(
                "Mailgun transient error %d, retrying once (to=%s)",
                response.status_code, to,
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            if attempt == 1:
                logger.error("Mailgun network error for %s: %s", to, exc)
                return False
            logger.warning("Mailgun network error, retrying once (to=%s): %s", to, exc)

    return False  # unreachable but satisfies type checker


# ---------------------------------------------------------------------------
# Public send functions — one per email type
# ---------------------------------------------------------------------------

async def send_welcome_email(*, to_email: str, name: str) -> bool:
    """Send a welcome email to a newly registered user.

    Args:
        to_email: Recipient email address.
        name:     Recipient display name (may be empty string).
    """
    display_name = name.strip() or to_email.split("@")[0]
    context = {"name": display_name, "email": to_email}
    html = _render("welcome.html", context)
    text = _render("welcome.txt", context)
    return await _send(
        to=to_email,
        subject="Welcome to QuillCV",
        html=html,
        text=text,
        tags=["welcome"],
    )


async def send_invitation_email(
    *,
    to_email: str,
    invite_code: str,
    credits: int,
    note: str = "",
    base_url: str = "https://quillcv.com",
) -> bool:
    """Send an invitation email with a signup link.

    Args:
        to_email:    Recipient email address.
        invite_code: The invitation code (used to build the signup URL).
        credits:     Number of credits the invitation grants.
        note:        Optional admin note shown in the email body.
        base_url:    Site base URL for constructing the invite link.
    """
    invite_url = f"{base_url.rstrip('/')}/signup?invite={invite_code}"
    context = {
        "invite_url": invite_url,
        "credits": credits,
        "note": note,
        "email": to_email,
    }
    html = _render("invitation.html", context)
    text = _render("invitation.txt", context)
    return await _send(
        to=to_email,
        subject="You're invited to QuillCV",
        html=html,
        text=text,
        tags=["invitation"],
    )


async def send_payment_confirmation_email(
    *,
    to_email: str,
    name: str,
    credits: int,
    amount_cents: int,
    currency: str = "AUD",
) -> bool:
    """Send a payment confirmation email after a successful Stripe checkout.

    Args:
        to_email:     Recipient email address.
        name:         Recipient display name.
        credits:      Number of credits purchased.
        amount_cents: Amount charged in the smallest currency unit.
        currency:     ISO 4217 currency code (e.g. "AUD").
    """
    display_name = name.strip() or to_email.split("@")[0]
    amount_formatted = f"{currency} ${amount_cents / 100:.2f}"
    context = {
        "name": display_name,
        "credits": credits,
        "amount": amount_formatted,
        "email": to_email,
    }
    html = _render("payment_confirmation.html", context)
    text = _render("payment_confirmation.txt", context)
    return await _send(
        to=to_email,
        subject="QuillCV — Payment Confirmed",
        html=html,
        text=text,
        tags=["payment-confirmation"],
    )


async def send_password_reset_email(
    *,
    to_email: str,
    name: str,
    reset_token: str,
    base_url: str = "https://quillcv.com",
    expires_minutes: int = 60,
) -> bool:
    """Send a password reset email with a one-time link.

    Args:
        to_email:        Recipient email address.
        name:            Recipient display name.
        reset_token:     Signed reset token (opaque to this service).
        base_url:        Site base URL for constructing the reset link.
        expires_minutes: Token TTL shown in the email body.
    """
    display_name = name.strip() or to_email.split("@")[0]
    reset_url = f"{base_url.rstrip('/')}/reset-password?token={reset_token}"
    context = {
        "name": display_name,
        "reset_url": reset_url,
        "expires_minutes": expires_minutes,
        "email": to_email,
    }
    html = _render("password_reset.html", context)
    text = _render("password_reset.txt", context)
    return await _send(
        to=to_email,
        subject="Reset your QuillCV password",
        html=html,
        text=text,
        tags=["password-reset"],
    )
