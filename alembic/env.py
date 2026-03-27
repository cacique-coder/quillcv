"""Alembic migration environment for QuillCV.

Uses the sync psycopg2 driver for migrations (Alembic does not require async).
The DATABASE_URL env var (or config/settings.py) provides the connection URL,
which is converted from postgresql+asyncpg:// to postgresql+psycopg2://.
"""

import logging
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Load .env for local development before importing app config.
from dotenv import load_dotenv

load_dotenv()

# Alembic Config object — gives access to alembic.ini values.
config = context.config

# Set up Python logging from alembic.ini if present.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

logger = logging.getLogger("alembic.env")

# ---------------------------------------------------------------------------
# Resolve database URL
# ---------------------------------------------------------------------------

def _sync_url(async_url: str) -> str:
    """Convert an async driver URL to the equivalent sync driver URL.

    postgresql+asyncpg://... -> postgresql+psycopg2://...
    postgresql://...         -> postgresql+psycopg2://...
    """
    if async_url.startswith("postgresql+asyncpg://"):
        return async_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    if async_url.startswith("postgresql://"):
        return async_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return async_url


def _get_url() -> str:
    """Return a synchronous database URL for Alembic."""
    # DATABASE_URL env var takes precedence (matches Rails-style convention in settings.py).
    raw_url = os.environ.get("DATABASE_URL")
    if not raw_url:
        # Fall back to app config.
        from config.settings import database_config
        raw_url = database_config()["url"]

    return _sync_url(raw_url)


# ---------------------------------------------------------------------------
# SQLAlchemy metadata — required for --autogenerate support.
# ---------------------------------------------------------------------------

# Import Base AND all models so SQLAlchemy metadata is fully populated.
from app.infrastructure.persistence.database import Base  # noqa: E402
import app.infrastructure.persistence.orm_models  # noqa: E402, F401  — registers all ORM classes on Base.metadata

target_metadata = Base.metadata

# ---------------------------------------------------------------------------
# Migration runners
# ---------------------------------------------------------------------------

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no live DB connection).

    Emits SQL to stdout rather than executing against the database.
    """
    url = _get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (live DB connection)."""
    url = _get_url()
    logger.info("Running migrations against: %s", url.split("@")[-1])  # hide credentials

    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = url

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
