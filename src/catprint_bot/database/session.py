from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from catprint_bot.config import Settings

_engine = None
_session_factory = None


def init_db(settings: Settings) -> None:
    """Initialize the async engine and session factory. Call once at startup."""
    global _engine, _session_factory
    _engine = create_async_engine(settings.database_url, echo=False)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)


async def create_tables() -> None:
    """Create all tables if they don't exist."""
    from catprint_bot.database.models import Base

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async session for dependency injection."""
    async with _session_factory() as session:
        yield session


async def close_db() -> None:
    """Dispose engine on shutdown."""
    if _engine:
        await _engine.dispose()
