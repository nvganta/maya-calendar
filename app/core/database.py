import os
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Lazy engine/session — only created when first needed (not at import time).
# This lets tests import Base without requiring DATABASE_URL to be set.
_engine = None
_async_session = None


def _get_engine():
    global _engine
    if _engine is None:
        from app.core.config import get_settings
        settings = get_settings()

        engine_kwargs = {}
        if os.getenv("VERCEL") or os.getenv("RENDER"):
            from sqlalchemy.pool import NullPool
            engine_kwargs["poolclass"] = NullPool

        _engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG, **engine_kwargs)
    return _engine


def _get_session_factory():
    global _async_session
    if _async_session is None:
        _async_session = async_sessionmaker(_get_engine(), class_=AsyncSession, expire_on_commit=False)
    return _async_session


async def get_db():
    """FastAPI dependency — yields a session."""
    session_factory = _get_session_factory()
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


@asynccontextmanager
async def get_session():
    """Async context manager for use outside FastAPI DI (e.g., background workers)."""
    session_factory = _get_session_factory()
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.close()
