"""Helpers for writing and reading the session-cached credit balance.

All code that sets ``session["cached_balance"]`` should go through
``set_cached_balance`` so that the companion ``cached_balance_set_at``
timestamp is always written atomically.  The middleware uses that
timestamp to detect when an out-of-band balance change (e.g. an admin
grant) has made the cached value stale.
"""

from __future__ import annotations

from datetime import UTC, datetime


def set_cached_balance(session: dict, balance: int) -> None:
    """Write the balance and a precise UTC timestamp into *session*.

    Both keys are written in a single call so they can never diverge.
    The session object must be the mutable dict exposed by the session
    middleware (i.e. ``request.state.session``).
    """
    session["cached_balance"] = balance
    session["cached_balance_set_at"] = datetime.now(UTC).isoformat()
