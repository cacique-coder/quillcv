"""SQLAlchemy async database setup."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config.settings import database_config

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
    """Create all tables. Call on app startup."""
    from app.models import APIRequestLog, ConsentRecord, Credit, ExpressionOfInterest, Invitation, Payment, PIIVault, SavedCV, User, WebAuthnCredential  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:
    """Dependency: yield a database session."""
    async with async_session() as session:
        yield session
