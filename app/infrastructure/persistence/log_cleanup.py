"""Periodic cleanup utilities for database-backed log tables.

Wire each function into a periodic task so it runs automatically — for example:

    # Via APScheduler (add to app startup in main.py):
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from app.infrastructure.persistence.log_cleanup import cleanup_old_api_logs

    scheduler = AsyncIOScheduler()
    scheduler.add_job(cleanup_old_api_logs, "interval", days=1)
    scheduler.start()

    # Or as a one-off via CLI:
    python -c "
    import asyncio
    from app.infrastructure.persistence.log_cleanup import cleanup_old_api_logs
    asyncio.run(cleanup_old_api_logs())
    "

Default retention window: 90 days.  Pass ``max_age_days`` to override.
"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select

from app.infrastructure.persistence.database import async_session
from app.infrastructure.persistence.orm_models import APIRequestLog

logger = logging.getLogger(__name__)


async def cleanup_old_api_logs(max_age_days: int = 90) -> int:
    """Delete APIRequestLog rows older than *max_age_days*.

    Returns the number of rows deleted.

    Safe to call concurrently — each call opens its own session and issues a
    single DELETE ... WHERE created_at < cutoff statement.
    """
    cutoff = datetime.now(UTC) - timedelta(days=max_age_days)

    async with async_session() as db:
        # Count first so we can emit a meaningful log line.
        count_result = await db.execute(
            select(func.count()).select_from(APIRequestLog).where(APIRequestLog.created_at < cutoff)
        )
        count = count_result.scalar() or 0

        if count > 0:
            await db.execute(
                delete(APIRequestLog).where(APIRequestLog.created_at < cutoff)
            )
            await db.commit()
            logger.info(
                "api_log cleanup: deleted %d APIRequestLog rows older than %d days",
                count,
                max_age_days,
            )
        else:
            logger.debug(
                "api_log cleanup: no APIRequestLog rows older than %d days found",
                max_age_days,
            )

    return count
