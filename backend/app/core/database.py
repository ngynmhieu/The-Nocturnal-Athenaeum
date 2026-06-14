"""Database engine + session factory (shared infrastructure).

Connects to Supabase Postgres via the session pooler using the async
`asyncpg` driver. The engine is created once at import time and reused for
the whole process lifetime — matching our long-lived uvicorn backend.
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from backend.app.core.config import settings

# pool_pre_ping checks a connection is alive before handing it out, which
# avoids errors from connections the pooler has already recycled.
engine = create_async_engine(settings.database_url, pool_pre_ping=True)

SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base class every ORM model (conversations, messages, ...) inherits from."""


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields a session and closes it after the request."""
    async with SessionLocal() as session:
        yield session
