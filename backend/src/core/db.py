"""Async SQLAlchemy engine, session factory and the `get_session` dependency.

Modules must not import this from a router. Routers receive a fully-built
service; only a module's repository layer ever sees a session.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from src.core.config import get_settings


class Base(DeclarativeBase):
    """Shared declarative base. Each module declares its own tables against it."""


@lru_cache
def get_engine() -> AsyncEngine:
    settings = get_settings()


    is_asyncpg = settings.database_url.startswith("postgresql+asyncpg")
    connect_args = (
        {"statement_cache_size": 0, "prepared_statement_cache_size": 0}
        if is_asyncpg
        else {}
    )

    return create_async_engine(
        settings.database_url,
        echo=settings.db_echo,
        pool_pre_ping=True,
        # Bounded on purpose. max_overflow=0 means the pool never silently
        # grows past pool_size; a leak surfaces as a timeout here rather than
        # as an EMAXCONNSESSION error from the pooler, which is easier to trace.
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        # Recycle before the pooler drops an idle connection server-side,
        # otherwise the first query on a stale connection fails.
        pool_recycle=300,
        pool_timeout=30,
        connect_args=connect_args,
    )


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a session scoped to one request."""
    async with get_session_factory()() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
