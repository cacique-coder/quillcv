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

# TODO(billing): packs need a Stripe product/price sync step (one-way push:
# defined here -> Stripe products) so the on-site display always matches what
# Stripe charges. Tracked separately; for now `price_cents` and `credits` are
# the source of truth and Stripe is configured manually.
TOPUP_PACKS = {
    "mini":     {"credits": 5,   "price_cents":  799, "name": "Mini — 5 Credits",     "per_credit": "$1.60", "tier": "public"},
    "starter":  {"credits": 10,  "price_cents": 1500, "name": "Starter — 10 Credits", "per_credit": "$1.50", "tier": "public"},
    "standard": {"credits": 25,  "price_cents": 3000, "name": "Standard — 25 Credits","per_credit": "$1.20", "tier": "public"},
    "pro":      {"credits": 50,  "price_cents": 4900, "name": "Pro — 50 Credits",     "per_credit": "$0.98", "tier": "public"},
    "max":      {"credits": 100, "price_cents": 8900, "name": "Max — 100 Credits",    "per_credit": "$0.89", "tier": "public"},
}


def user_can_see_pack(pack: dict, user_tier: str) -> bool:
    """Visibility rule: public packs are visible to everyone; non-public
    packs are visible only to users at the matching tier (or higher in
    future hierarchies)."""
    pack_tier = (pack or {}).get("tier", "public")
    if pack_tier == "public":
        return True
    return user_tier == pack_tier
