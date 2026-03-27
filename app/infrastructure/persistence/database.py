"""SQLAlchemy async database setup."""

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config.settings import database_config

logger = logging.getLogger(__name__)

_config = database_config()

engine = create_async_engine(
    _config["url"],
    echo=_config.get("echo", False),
    pool_size=_config.get("pool_size", 5),
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db():
    """Run Alembic migrations on startup.

    Uses a Postgres advisory lock so only one gunicorn worker runs
    migrations — the others wait and skip.

    In development, migrations are skipped unless RUN_MIGRATIONS=1 is set.
    Run `alembic upgrade head` manually instead.
    """
    import os

    app_env = os.environ.get("APP_ENV", "")
    run_migrations = os.environ.get("RUN_MIGRATIONS", "")
    if app_env == "development" and run_migrations != "1":
        logger.info("Skipping auto-migration in development (set RUN_MIGRATIONS=1 to enable)")
        return

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text

    # Step 1: Alembic migrations with advisory lock (prevents deadlock
    # when multiple gunicorn workers start simultaneously)
    MIGRATION_LOCK_ID = 900100  # arbitrary unique int for pg_advisory_lock

    def _run_upgrade():
        from sqlalchemy import create_engine
        sync_url = _config["url"].replace("+asyncpg", "")
        sync_engine = create_engine(sync_url)
        with sync_engine.connect() as conn:
            # Try to acquire lock — non-blocking
            got_lock = conn.execute(
                text(f"SELECT pg_try_advisory_lock({MIGRATION_LOCK_ID})")
            ).scalar()
            if got_lock:
                try:
                    alembic_cfg = Config("alembic.ini")
                    logger.info("Running Alembic migrations to head...")
                    command.upgrade(alembic_cfg, "head")
                    logger.info("Alembic migrations complete.")
                finally:
                    conn.execute(text(f"SELECT pg_advisory_unlock({MIGRATION_LOCK_ID})"))
                    conn.commit()
            else:
                logger.info("Another worker is running migrations — skipping.")
        sync_engine.dispose()

    await asyncio.to_thread(_run_upgrade)


async def get_db() -> AsyncSession:
    """Dependency: yield a database session."""
    async with async_session() as session:
        yield session
