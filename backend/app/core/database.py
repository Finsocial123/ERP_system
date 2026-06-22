from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


DEFAULT_ASYNC_SQLITE_URL = "sqlite+aiosqlite:///./erp_phase1.db"


def _normalize_sync_database_url(raw_url: str) -> str:
    url = make_url(raw_url)

    if url.drivername == "postgresql+asyncpg":
        return url.set(
            drivername="postgresql+psycopg"
        ).render_as_string(hide_password=False)

    if url.drivername == "postgresql":
        return url.set(
            drivername="postgresql+psycopg"
        ).render_as_string(hide_password=False)

    if url.drivername == "sqlite+aiosqlite":
        return url.set(
            drivername="sqlite"
        ).render_as_string(hide_password=False)

    return raw_url


def _normalize_async_database_url(raw_url: str) -> str:
    url = make_url(raw_url)

    if url.drivername in {
        "postgresql",
        "postgresql+psycopg",
        "postgresql+psycopg2",
    }:
        return url.set(
            drivername="postgresql+asyncpg"
        ).render_as_string(hide_password=False)

    if url.drivername == "sqlite":
        return url.set(
            drivername="sqlite+aiosqlite"
        ).render_as_string(hide_password=False)

    return raw_url


raw_async_database_url = settings.ASYNC_DATABASE_URL

if (
    settings.DATABASE_URL
    and not settings.DATABASE_URL.startswith("sqlite")
    and raw_async_database_url == DEFAULT_ASYNC_SQLITE_URL
):
    raw_async_database_url = settings.DATABASE_URL


SYNC_DATABASE_URL = _normalize_sync_database_url(settings.DATABASE_URL)
ASYNC_DATABASE_URL = _normalize_async_database_url(raw_async_database_url)


# ----------------------------------------------------------------------
# Sync engine
# ----------------------------------------------------------------------

if SYNC_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        SYNC_DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False,
    )
else:
    engine = create_engine(
        SYNC_DATABASE_URL,
        poolclass=NullPool,
        pool_pre_ping=True,
        echo=False,
    )


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ----------------------------------------------------------------------
# Async engine
# ----------------------------------------------------------------------

if ASYNC_DATABASE_URL.startswith("sqlite"):
    async_engine = create_async_engine(
        ASYNC_DATABASE_URL,
        echo=False,
    )
else:
    async_engine = create_async_engine(
        ASYNC_DATABASE_URL,
        poolclass=NullPool,
        pool_pre_ping=True,
        echo=False,
    )


AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_async_db():
    async with AsyncSessionLocal() as db:
        yield db


async def get_session_factory():
    return AsyncSessionLocal