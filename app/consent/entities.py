"""Consent domain entities and policy constants."""

from dataclasses import dataclass
from datetime import datetime

# Increment this string whenever the privacy policy or terms of service change.
CURRENT_POLICY_VERSION = "2026-03-14"


@dataclass
class ConsentRecord:
    user_id: str
    policy_version: str
    consented_at: datetime
    ip_address: str = ""
