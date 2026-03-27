"""Identity domain entities — pure Python, no framework dependencies."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class UserProfile:
    id: str
    email: str
    name: str = ""
    role: str = "consumer"
    is_active: bool = True
    created_at: datetime | None = None
    last_login: datetime | None = None
    age_confirmed_at: datetime | None = None
