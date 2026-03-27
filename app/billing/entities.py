"""Billing domain entities and constants."""

from dataclasses import dataclass


@dataclass
class CreditBalance:
    user_id: str
    balance: int
    total_purchased: int
    total_used: int


ALPHA_PACK_CREDITS = 15
ALPHA_PACK_PRICE_CENTS = 999  # $9.99 AUD
ALPHA_USER_CAP = 100

TOPUP_PACKS = {
    "starter": {"credits": 10, "price_cents": 1500, "name": "Starter — 10 Credits", "per_credit": "$1.50"},
    "standard": {"credits": 25, "price_cents": 3000, "name": "Standard — 25 Credits", "per_credit": "$1.20"},
    "pro": {"credits": 50, "price_cents": 4900, "name": "Pro — 50 Credits", "per_credit": "$0.98"},
}
