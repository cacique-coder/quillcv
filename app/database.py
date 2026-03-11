"""SQLAlchemy async database setup with SQLite."""

import os
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

DB_PATH = Path(__file__).parent.parent / "data" / "quillcv.db"
DB_URL = os.environ.get("DATABASE_URL", f"sqlite+aiosqlite:///{DB_PATH}")


engine = create_async_engine(DB_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db():
    """Create all tables. Call on app startup."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    from app.models import User, Credit, Payment, WebAuthnCredential  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:
    """Dependency: yield a database session."""
    async with async_session() as session:
        yield session
