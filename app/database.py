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
    """Run Alembic migrations on app startup.

    Uses asyncio.to_thread because Alembic's upgrade() is synchronous.
    Any pending migrations are applied before the app begins serving requests.
    """
    from alembic import command
    from alembic.config import Config

    def _run_upgrade():
        alembic_cfg = Config("alembic.ini")
        logger.info("Running Alembic migrations to head...")
        command.upgrade(alembic_cfg, "head")
        logger.info("Alembic migrations complete.")

    await asyncio.to_thread(_run_upgrade)


async def get_db() -> AsyncSession:
    """Dependency: yield a database session."""
    async with async_session() as session:
        yield session
