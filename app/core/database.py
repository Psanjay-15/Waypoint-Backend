"""Async SQLAlchemy engine, session factory, and schema creation."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    """Declarative base — all ORM models inherit from this."""


engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — one session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


_ADDITIVE_MIGRATIONS: tuple[str, ...] = ()


async def create_all() -> None:
    import importlib

    importlib.import_module("app.db.models")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for stmt in _ADDITIVE_MIGRATIONS:
            await conn.execute(text(stmt))
