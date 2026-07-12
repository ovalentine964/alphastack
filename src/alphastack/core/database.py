"""Database connection management for AlphaStack (async PostgreSQL via SQLAlchemy)."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from alphastack.core.config import get_settings
from alphastack.utils.logger import get_logger

logger = get_logger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Return (and lazily create) the singleton async engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.db.async_url,
            pool_size=settings.db.pool_size,
            max_overflow=settings.db.max_overflow,
            pool_timeout=settings.db.pool_timeout,
            echo=settings.db.echo,
            pool_pre_ping=True,
        )
        logger.info(
            "database.engine_created",
            host=settings.db.host,
            port=settings.db.port,
            db=settings.db.name,
            pool_size=settings.db.pool_size,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the session factory bound to the engine."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency – yields an async session, auto-commits/rollbacks."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Create all tables (for dev / testing only – use Alembic in prod)."""
    from alphastack.core.models import Base  # noqa: F811

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("database.tables_created")


async def close_db() -> None:
    """Dispose the engine and release all connections."""
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("database.engine_disposed")


# ---------------------------------------------------------------------------
# Alembic migration helpers
# ---------------------------------------------------------------------------

def run_migrations(alembic_cfg_path: str = "alembic.ini") -> None:
    """Run Alembic migrations programmatically (CLI or startup hook).

    Args:
        alembic_cfg_path: Path to alembic.ini.
    """
    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config(alembic_cfg_path)
    command.upgrade(alembic_cfg, "head")
    logger.info("database.migrations_applied")
