"""Consent recording service.

Records all user consent actions to the consent_records table for audit trail.
Required by LGPD (Brazil), Ley 1581 (Colombia), and CPRA (California).
"""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ConsentRecord, User

# Increment this string whenever the privacy policy or terms of service change.
CURRENT_POLICY_VERSION = "2026-03-14"


async def record_consent(
    db: AsyncSession,
    consent_type: str,
    granted: bool,
    user_id: str | None = None,
    email: str = "",
    ip_address: str | None = None,
    user_agent: str | None = None,
    policy_version: str = CURRENT_POLICY_VERSION,
) -> ConsentRecord:
    """Write a single consent event to the audit log.

    Args:
        db:             Active async database session.
        consent_type:   One of the documented consent_type values (see ConsentRecord docstring).
        granted:        True if the user is granting consent, False if withholding/revoking.
        user_id:        ID of the authenticated user (nullable — used for CCPA opt-out).
        email:          Email address at time of submission for audit trail.
        ip_address:     Client IP at time of consent (IPv4 or IPv6, up to 45 chars).
        user_agent:     Browser user-agent string.
        policy_version: Version string of the policy being consented to.

    Returns:
        The persisted ConsentRecord instance (not yet committed — caller flushes or commits).
    """
    record = ConsentRecord(
        user_id=user_id,
        consent_type=consent_type,
        granted=granted,
        email=email,
        ip_address=ip_address,
        user_agent=user_agent,
        policy_version=policy_version,
    )
    db.add(record)
    await db.flush()
    return record


async def record_age_confirmation(
    db: AsyncSession,
    user: User,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Mark the user as having confirmed they are 18+ and write the consent record.

    Sets ``user.age_confirmed_at`` and inserts an ``age_verification`` consent entry.
    Does NOT commit — the caller is responsible for committing the transaction so that
    the user update and the consent record land atomically.
    """
    user.age_confirmed_at = datetime.now(UTC)

    await record_consent(
        db,
        user_id=user.id,
        consent_type="age_verification",
        granted=True,
        email=user.email,
        ip_address=ip_address,
        user_agent=user_agent,
    )


def get_client_ip(request) -> str | None:
    """Extract client IP from request, respecting X-Forwarded-For when behind a proxy."""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # X-Forwarded-For may be a comma-separated list; the first entry is the client
        return forwarded_for.split(",")[0].strip()
    return getattr(request.client, "host", None)


def get_user_agent(request) -> str | None:
    """Extract User-Agent header, truncated to 512 chars to fit the DB column."""
    ua = request.headers.get("user-agent", "")
    return ua[:512] if ua else None
