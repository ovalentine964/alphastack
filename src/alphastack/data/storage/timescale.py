"""TimescaleDB Storage – hypertable management, tick storage, backtesting queries."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Sequence

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    and_,
    func,
    text,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from alphastack.core.config import get_settings
from alphastack.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# ORM base
# ---------------------------------------------------------------------------

class TimescaleBase(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class OHLCVRow(TimescaleBase):
    __tablename__ = "ohlcv"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    timeframe: Mapped[str] = mapped_column(String(8), primary_key=True)
    open: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    high: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    low: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    close: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    volume: Mapped[Decimal] = mapped_column(Numeric(30, 8))
    tick_count: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (
        Index("idx_ohlcv_symbol_tf_time", "symbol", "timeframe", "time"),
    )


class TickRow(TimescaleBase):
    __tablename__ = "ticks"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    bid: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    ask: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    last: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    volume: Mapped[Decimal] = mapped_column(Numeric(30, 8))
    broker: Mapped[str] = mapped_column(String(32))

    __table_args__ = (
        Index("idx_ticks_symbol_time", "symbol", "time"),
    )


# ---------------------------------------------------------------------------
# TimescaleDB connection manager
# ---------------------------------------------------------------------------

class TimescaleDB:
    """Manages the TimescaleDB connection, hypertable creation, and queries."""

    def __init__(self, dsn: str | None = None) -> None:
        settings = get_settings()
        self._dsn = dsn or settings.db.async_url.replace("+asyncpg", "+psycopg2")
        self._async_dsn = dsn or settings.db.async_url
        self._engine = create_async_engine(
            self._async_dsn,
            pool_size=settings.db.pool_size,
            max_overflow=settings.db.max_overflow,
            pool_timeout=settings.db.pool_timeout,
            echo=settings.db.echo,
        )
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)

    @property
    def session(self) -> async_sessionmaker[AsyncSession]:
        return self._session_factory

    # -- schema management ---------------------------------------------------

    async def init_hypertables(self) -> None:
        """Create tables and convert to TimescaleDB hypertables."""
        async with self._engine.begin() as conn:
            await conn.run_sync(TimescaleBase.metadata.create_all)
            # Create hypertables (idempotent)
            for table, chunk_interval in [("ohlcv", "1 day"), ("ticks", "1 hour")]:
                await conn.execute(text(
                    f"SELECT create_hypertable('{table}', 'time_chunk_interval', "
                    f"chunk_time_interval => INTERVAL '{chunk_interval}', "
                    f"if_not_exists => TRUE);"
                ).execution_options(autocommit=True))
            # Compression policy for older data
            await conn.execute(text(
                "SELECT add_compression_policy('ohlcv', INTERVAL '7 days', if_not_exists => TRUE);"
            ).execution_options(autocommit=True))
            await conn.execute(text(
                "SELECT add_compression_policy('ticks', INTERVAL '1 day', if_not_exists => TRUE);"
            ).execution_options(autocommit=True))
        logger.info("timescale_hypertables_ready")

    # -- write ---------------------------------------------------------------

    async def insert_candles(self, rows: Sequence[dict[str, Any]]) -> int:
        """Bulk-insert OHLCV candles. Returns count inserted."""
        if not rows:
            return 0
        async with self._session() as session:
            async with session.begin():
                for r in rows:
                    session.add(OHLCVRow(**r))
            return len(rows)

    async def insert_ticks(self, rows: Sequence[dict[str, Any]]) -> int:
        """Bulk-insert raw ticks. Returns count inserted."""
        if not rows:
            return 0
        async with self._session() as session:
            async with session.begin():
                for r in rows:
                    session.add(TickRow(**r))
            return len(rows)

    # -- queries (backtesting-optimised) ------------------------------------

    async def get_candles(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime | None = None,
        limit: int = 5000,
    ) -> list[dict[str, Any]]:
        """Fetch OHLCV candles for backtesting."""
        end = end or datetime.now(timezone.utc)
        async with self._session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT time, symbol, timeframe, open, high, low, close, volume, tick_count
                    FROM ohlcv
                    WHERE symbol = :symbol
                      AND timeframe = :timeframe
                      AND time >= :start
                      AND time < :end
                    ORDER BY time ASC
                    LIMIT :limit
                    """
                ),
                {"symbol": symbol, "timeframe": timeframe, "start": start, "end": end, "limit": limit},
            )
            return [dict(row._mapping) for row in result]

    async def get_latest_candle(self, symbol: str, timeframe: str) -> dict[str, Any] | None:
        """Get the most recent closed candle."""
        async with self._session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT time, symbol, timeframe, open, high, low, close, volume, tick_count
                    FROM ohlcv
                    WHERE symbol = :symbol AND timeframe = :timeframe
                    ORDER BY time DESC
                    LIMIT 1
                    """
                ),
                {"symbol": symbol, "timeframe": timeframe},
            )
            row = result.first()
            return dict(row._mapping) if row else None

    async def get_ticks(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        limit: int = 50_000,
    ) -> list[dict[str, Any]]:
        """Fetch raw ticks (for high-fidelity backtesting)."""
        async with self._session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT time, symbol, bid, ask, last, volume, broker
                    FROM ticks
                    WHERE symbol = :symbol
                      AND time >= :start
                      AND time < :end
                    ORDER BY time ASC
                    LIMIT :limit
                    """
                ),
                {"symbol": symbol, "start": start, "end": end, "limit": limit},
            )
            return [dict(row._mapping) for row in result]

    async def close(self) -> None:
        await self._engine.dispose()
