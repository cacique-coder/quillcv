"""Store and retrieve Job records — target job applications for CV generation.

Encrypted fields (cv_data_json, cv_rendered_html, cover_letter_json,
cover_letter_html, quality_review_json, keywords_json) are encrypted at rest
using the server Fernet key via ``app.infrastructure.crypto``.

All public functions accept an ``AsyncSession`` and are fully async.
"""

import logging

from cryptography.fernet import InvalidToken
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.crypto import decrypt_data, encrypt_data
from app.infrastructure.persistence.orm_models import Job

logger = logging.getLogger(__name__)

# Fields whose values are encrypted at rest.
_ENCRYPTED_FIELDS = frozenset({
    "cv_data_json",
    "cv_rendered_html",
    "cover_letter_json",
    "cover_letter_html",
    "quality_review_json",
    "keywords_json",
})


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _encrypt_fields(fields: dict) -> dict:
    """Return a copy of *fields* with encrypted-field values Fernet-encrypted.

    Only fields whose keys are in ``_ENCRYPTED_FIELDS`` and whose values are
    non-None strings are encrypted.  Everything else passes through unchanged.
    """
    out = dict(fields)
    for key in _ENCRYPTED_FIELDS:
        if key in out and out[key] is not None:
            out[key] = encrypt_data(str(out[key]))
    return out


def _safe_decrypt(value: str | None) -> str | None:
    """Decrypt a Fernet token, returning the original value on failure.

    Falls back gracefully for legacy rows written before encryption was
    enabled, or for ``None`` values.
    """
    if value is None:
        return None
    try:
        return decrypt_data(value)
    except (InvalidToken, Exception):
        return value  # Not encrypted (legacy row) — return as-is


def _decrypt_job(job: Job) -> Job:
    """Decrypt all encrypted fields on a Job in-place and return it."""
    job.cv_data_json = _safe_decrypt(job.cv_data_json)
    job.cv_rendered_html = _safe_decrypt(job.cv_rendered_html)
    job.cover_letter_json = _safe_decrypt(job.cover_letter_json)
    job.cover_letter_html = _safe_decrypt(job.cover_letter_html)
    job.quality_review_json = _safe_decrypt(job.quality_review_json)
    job.keywords_json = _safe_decrypt(job.keywords_json)
    return job


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def create_job(
    db: AsyncSession,
    *,
    user_id: str,
    job_description: str,
    region: str,
    job_url: str = "",
    job_title: str = "",
    company_name: str = "",
    offer_appeal: str = "",
    template_id: str = "",
) -> Job:
    """Persist a new Job record and return it (decrypted, ready for use).

    The job starts in ``draft`` status.  Generated output fields are all
    ``None`` until a generation run completes.
    """
    job = Job(
        user_id=user_id,
        job_url=job_url,
        job_title=job_title,
        company_name=company_name,
        job_description=job_description,
        offer_appeal=offer_appeal,
        region=region,
        template_id=template_id,
        status="draft",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    logger.info("Created job %s (user=%s, region=%s)", job.id, user_id, region)
    return job


async def get_job(
    db: AsyncSession,
    job_id: str,
    *,
    user_id: str | None = None,
) -> Job | None:
    """Retrieve a single Job by ID, decrypting generated output fields.

    Pass ``user_id`` to scope the lookup to a specific owner — this prevents
    one user from reading another user's job data.
    """
    query = select(Job).where(Job.id == job_id)
    if user_id is not None:
        query = query.where(Job.user_id == user_id)

    result = await db.execute(query)
    job = result.scalar_one_or_none()
    if job is None:
        return None

    return _decrypt_job(job)


async def update_job(
    db: AsyncSession,
    job_id: str,
    **fields,
) -> Job | None:
    """Update arbitrary fields on a Job and return the refreshed record.

    Caller is responsible for scoping by user_id before calling if needed
    (e.g. verify ownership with ``get_job(..., user_id=...)`` first).

    Generated output fields listed in ``_ENCRYPTED_FIELDS`` are automatically
    re-encrypted before writing.  All other fields are written as-is.

    Returns ``None`` if the job does not exist.
    """
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        return None

    encrypted = _encrypt_fields(fields)
    for key, value in encrypted.items():
        if hasattr(job, key):
            setattr(job, key, value)
        else:
            logger.warning("update_job: unknown field %r — skipping", key)

    await db.commit()
    await db.refresh(job)
    logger.info("Updated job %s (fields=%s)", job_id, list(fields.keys()))
    return _decrypt_job(job)


async def list_jobs(
    db: AsyncSession,
    user_id: str,
    *,
    limit: int = 50,
) -> list[Job]:
    """Return the most-recent jobs for a user, newest first.

    Generated output fields are decrypted on each returned Job.
    """
    query = (
        select(Job)
        .where(Job.user_id == user_id)
        .order_by(Job.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    jobs = list(result.scalars().all())

    for job in jobs:
        _decrypt_job(job)

    return jobs


async def delete_job(
    db: AsyncSession,
    job_id: str,
    user_id: str,
) -> bool:
    """Delete a Job owned by the given user.

    Returns ``True`` if a row was deleted, ``False`` if not found or not owned
    by ``user_id``.
    """
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == user_id)
    )
    job = result.scalar_one_or_none()
    if job is None:
        return False

    await db.delete(job)
    await db.commit()
    logger.info("Deleted job %s (user=%s)", job_id, user_id)
    return True
