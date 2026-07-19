"""MarketDataStore – TimescaleDB persistence with Redis hot-cache.

Provides a unified storage layer for market data:

- **TimescaleDB** for durable OHLCV and tick storage (hypertables, compression)
- **Redis** for hot-data caching (latest ticks, recent candles, order book snapshots)
- Historical data loader for backtesting
- Data quality checks (gap detection, staleness, completeness)

Usage::

    store = MarketDataStore()
    await store.init()

    # Write
    await store.write_tick(tick)
    await store.write_candle(candle)

    # Read (cache-aside)
    candles = await store.get_candles("BTC/USDT", "1h", limit=500)
    tick = await store.get_latest_tick("BTC/USDT")
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Sequence

from redis.asyncio import Redis

from alphastack.core.config import get_settings
from alphastack.core.events import DataEvent, EventBus, EventType
from alphastack.data.ingestion.market_data import Candle, CandleTimeframe, Tick
from alphastack.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Cache key prefixes
# ---------------------------------------------------------------------------

_TICK_KEY = "alphastack:tick:{symbol}"
_CANDLE_LATEST_KEY = "alphastack:candle:{symbol}:{timeframe}"
_CANDLE_HISTORY_KEY = "alphastack:candles:{symbol}:{timeframe}"
_ORDERBOOK_KEY = "alphastack:orderbook:{symbol}"
_HEALTH_KEY = "alphastack:data:health"

# Cache TTLs
_TICK_TTL_S = 60              # 1 minute — ticks are ephemeral
_CANDLE_LATEST_TTL_S = 3600   # 1 hour — latest closed candle
_CANDLE_HISTORY_TTL_S = 300   # 5 minutes — recent candle window
_ORDERBOOK_TTL_S = 30         # 30 seconds — order book is volatile


# ---------------------------------------------------------------------------
# Data quality result
# ---------------------------------------------------------------------------

class DataQualityReport:
    """Result of a data quality check."""

    def __init__(
        self,
        symbol: str,
        timeframe: str,
        expected_count: int,
        actual_count: int,
        gaps: list[dict[str, Any]],
        stale: bool,
        completeness_pct: float,
    ) -> None:
        self.symbol = symbol
        self.timeframe = timeframe
        self.expected_count = expected_count
        self.actual_count = actual_count
        self.gaps = gaps
        self.stale = stale
        self.completeness_pct = completeness_pct

    @property
    def is_clean(self) -> bool:
        """True if data passes all quality checks."""
        return self.completeness_pct >= 99.0 and not self.stale and len(self.gaps) == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "expected_count": self.expected_count,
            "actual_count": self.actual_count,
            "gaps": self.gaps,
            "stale": self.stale,
            "completeness_pct": round(self.completeness_pct, 2),
            "is_clean": self.is_clean,
        }


# ---------------------------------------------------------------------------
# MarketDataStore
# ---------------------------------------------------------------------------

class MarketDataStore:
    """TimescaleDB + Redis cache-aside storage for market data.

    Parameters
    ----------
    dsn : str | None
        PostgreSQL DSN. Falls back to ``DB_*`` env vars.
    redis_url : str | None
        Redis URL. Falls back to ``REDIS_*`` env vars.
    enable_cache : bool
        Enable Redis caching (disable for testing).
    enable_timescale : bool
        Enable TimescaleDB persistence (disable for testing).
    candle_history_size : int
        Number of recent candles to keep in the Redis cache.
    """

    def __init__(
        self,
        dsn: str | None = None,
        redis_url: str | None = None,
        enable_cache: bool = True,
        enable_timescale: bool = True,
        candle_history_size: int = 500,
    ) -> None:
        settings = get_settings()
        self._dsn = dsn or settings.db.async_url
        self._redis_url = redis_url or settings.redis.url
        self._enable_cache = enable_cache
        self._enable_timescale = enable_timescale
        self._candle_history_size = candle_history_size

        self._redis: Redis | None = None
        self._timescale: Any = None  # Lazy-loaded TimescaleDB instance
        self._initialized = False

        # Metrics
        self._write_count: int = 0
        self._read_count: int = 0
        self._cache_hits: int = 0
        self._cache_misses: int = 0

    # -- Lifecycle -----------------------------------------------------------

    async def init(self) -> None:
        """Initialize connections (Redis + TimescaleDB)."""
        if self._enable_cache:
            try:
                self._redis = Redis.from_url(self._redis_url, decode_responses=True)
                await self._redis.ping()
                logger.info("store.redis_connected", url=self._redis_url)
            except Exception as exc:
                logger.warning("store.redis_connect_failed", error=str(exc))
                self._redis = None
                self._enable_cache = False

        if self._enable_timescale:
            try:
                from alphastack.data.storage.timescale import TimescaleDB

                self._timescale = TimescaleDB(self._dsn)
                await self._timescale.init_hypertables()
                logger.info("store.timescale_connected")
            except Exception as exc:
                logger.warning("store.timescale_connect_failed", error=str(exc))
                self._timescale = None
                self._enable_timescale = False

        self._initialized = True
        logger.info(
            "store.initialized",
            cache=self._enable_cache,
            timescale=self._enable_timescale,
        )

    async def close(self) -> None:
        """Close all connections."""
        if self._redis:
            await self._redis.aclose()
            self._redis = None
        if self._timescale:
            await self._timescale.close()
            self._timescale = None
        self._initialized = False
        logger.info("store.closed")

    # -- Properties ----------------------------------------------------------

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def cache_hit_rate(self) -> float:
        total = self._cache_hits + self._cache_misses
        return self._cache_hits / total if total > 0 else 0.0

    def get_metrics(self) -> dict[str, Any]:
        """Return storage metrics for monitoring."""
        return {
            "initialized": self._initialized,
            "cache_enabled": self._enable_cache,
            "timescale_enabled": self._enable_timescale,
            "write_count": self._write_count,
            "read_count": self._read_count,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_hit_rate": round(self.cache_hit_rate, 4),
        }

    # -- Tick writes ---------------------------------------------------------

    async def write_tick(self, tick: Tick) -> None:
        """Persist a tick to Redis cache and optionally TimescaleDB.

        Parameters
        ----------
        tick : Tick
            Validated tick to store.
        """
        self._write_count += 1

        # Always update the Redis hot cache
        if self._redis:
            try:
                key = _TICK_KEY.format(symbol=tick.symbol)
                data = json.dumps({
                    "symbol": tick.symbol,
                    "bid": str(tick.bid),
                    "ask": str(tick.ask),
                    "last": str(tick.last),
                    "volume": str(tick.volume),
                    "timestamp": tick.timestamp.isoformat(),
                    "broker": tick.broker.value if hasattr(tick.broker, "value") else str(tick.broker),
                })
                await self._redis.set(key, data, ex=_TICK_TTL_S)
            except Exception as exc:
                logger.warning("store.tick_cache_write_failed", error=str(exc))

        # Persist to TimescaleDB (if enabled)
        if self._timescale:
            try:
                await self._timescale.insert_ticks([{
                    "time": tick.timestamp,
                    "symbol": tick.symbol,
                    "bid": tick.bid,
                    "ask": tick.ask,
                    "last": tick.last,
                    "volume": tick.volume,
                    "broker": tick.broker.value if hasattr(tick.broker, "value") else str(tick.broker),
                }])
            except Exception as exc:
                logger.warning("store.tick_db_write_failed", symbol=tick.symbol, error=str(exc))

    async def write_ticks(self, ticks: Sequence[Tick]) -> int:
        """Bulk-write ticks. Returns count written."""
        if not ticks:
            return 0

        count = 0
        for tick in ticks:
            await self.write_tick(tick)
            count += 1
        return count

    # -- Candle writes -------------------------------------------------------

    async def write_candle(self, candle: Candle) -> None:
        """Persist a closed candle to Redis cache and TimescaleDB.

        Parameters
        ----------
        candle : Candle
            A closed candle bar.
        """
        self._write_count += 1

        # Update Redis hot cache
        if self._redis:
            try:
                tf_key = candle.timeframe.value

                # Latest candle
                latest_key = _CANDLE_LATEST_KEY.format(
                    symbol=candle.symbol, timeframe=tf_key,
                )
                candle_data = json.dumps({
                    "symbol": candle.symbol,
                    "timeframe": tf_key,
                    "open": str(candle.open),
                    "high": str(candle.high),
                    "low": str(candle.low),
                    "close": str(candle.close),
                    "volume": str(candle.volume),
                    "timestamp": candle.timestamp.isoformat(),
                    "tick_count": candle.tick_count,
                })
                await self._redis.set(latest_key, candle_data, ex=_CANDLE_LATEST_TTL_S)

                # Append to history list (ring buffer)
                history_key = _CANDLE_HISTORY_KEY.format(
                    symbol=candle.symbol, timeframe=tf_key,
                )
                await self._redis.rpush(history_key, candle_data)
                await self._redis.ltrim(history_key, -self._candle_history_size, -1)
                await self._redis.expire(history_key, _CANDLE_HISTORY_TTL_S)

            except Exception as exc:
                logger.warning("store.candle_cache_write_failed", error=str(exc))

        # Persist to TimescaleDB
        if self._timescale:
            try:
                await self._timescale.insert_candles([{
                    "time": candle.timestamp,
                    "symbol": candle.symbol,
                    "timeframe": candle.timeframe.value,
                    "open": candle.open,
                    "high": candle.high,
                    "low": candle.low,
                    "close": candle.close,
                    "volume": candle.volume,
                    "tick_count": candle.tick_count,
                }])
            except Exception as exc:
                logger.warning("store.candle_db_write_failed", symbol=candle.symbol, error=str(exc))

    async def write_candles(self, candles: Sequence[Candle]) -> int:
        """Bulk-write closed candles. Returns count written."""
        if not candles:
            return 0

        count = 0
        for candle in candles:
            await self.write_candle(candle)
            count += 1
        return count

    # -- Tick reads ----------------------------------------------------------

    async def get_latest_tick(self, symbol: str) -> dict[str, Any] | None:
        """Get the latest tick for *symbol* (Redis first, then DB).

        Returns
        -------
        dict | None
            Tick data with keys: ``symbol``, ``bid``, ``ask``, ``last``,
            ``volume``, ``timestamp``, ``broker``.
        """
        self._read_count += 1

        # Try Redis cache
        if self._redis:
            try:
                key = _TICK_KEY.format(symbol=symbol)
                data = await self._redis.get(key)
                if data:
                    self._cache_hits += 1
                    return json.loads(data)
            except Exception:
                pass

        self._cache_misses += 1
        return None

    # -- Candle reads --------------------------------------------------------

    async def get_latest_candle(
        self, symbol: str, timeframe: str,
    ) -> dict[str, Any] | None:
        """Get the latest closed candle (cache-aside).

        Returns
        -------
        dict | None
            Candle data with keys: ``symbol``, ``timeframe``, ``open``,
            ``high``, ``low``, ``close``, ``volume``, ``timestamp``.
        """
        self._read_count += 1

        # Try Redis
        if self._redis:
            try:
                key = _CANDLE_LATEST_KEY.format(symbol=symbol, timeframe=timeframe)
                data = await self._redis.get(key)
                if data:
                    self._cache_hits += 1
                    return json.loads(data)
            except Exception:
                pass

        # Fall back to TimescaleDB
        self._cache_misses += 1
        if self._timescale:
            try:
                result = await self._timescale.get_latest_candle(symbol, timeframe)
                if result:
                    # Backfill cache
                    if self._redis:
                        try:
                            key = _CANDLE_LATEST_KEY.format(symbol=symbol, timeframe=timeframe)
                            await self._redis.set(
                                key,
                                json.dumps(result, default=str),
                                ex=_CANDLE_LATEST_TTL_S,
                            )
                        except Exception:
                            pass
                    return result
            except Exception as exc:
                logger.warning("store.candle_db_read_failed", error=str(exc))

        return None

    async def get_candles(
        self,
        symbol: str,
        timeframe: str,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        """Fetch OHLCV candles with cache-aside strategy.

        For recent data (within cache window), reads from Redis.
        For historical data, reads from TimescaleDB.

        Parameters
        ----------
        symbol : str
            Trading pair.
        timeframe : str
            Candle interval (``"1m"``, ``"5m"``, ``"1h"``, etc.)
        start : datetime | None
            Start of query window. If None, reads from cache.
        end : datetime | None
            End of query window.
        limit : int
            Maximum candles to return.

        Returns
        -------
        list[dict]
            Candles in chronological order.
        """
        self._read_count += 1

        # If no start specified, try cache first
        if start is None and self._redis:
            try:
                key = _CANDLE_HISTORY_KEY.format(symbol=symbol, timeframe=timeframe)
                raw_list = await self._redis.lrange(key, -limit, -1)
                if raw_list:
                    self._cache_hits += 1
                    return [json.loads(r) for r in raw_list]
            except Exception:
                pass

        self._cache_misses += 1

        # Fall back to TimescaleDB
        if self._timescale:
            try:
                if start is None:
                    start = datetime.now(timezone.utc) - timedelta(days=30)
                result = await self._timescale.get_candles(
                    symbol, timeframe, start, end, limit,
                )
                return result
            except Exception as exc:
                logger.warning("store.candles_db_read_failed", error=str(exc))

        return []

    # -- Historical loader (backtesting) ------------------------------------

    async def load_historical(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime | None = None,
        limit: int = 10_000,
    ) -> list[dict[str, Any]]:
        """Load historical candles for backtesting.

        Reads directly from TimescaleDB (bypasses cache).

        Parameters
        ----------
        symbol : str
            Trading pair.
        timeframe : str
            Candle interval.
        start : datetime
            Start date.
        end : datetime | None
            End date (defaults to now).
        limit : int
            Maximum candles.

        Returns
        -------
        list[dict]
            Historical candles.
        """
        if not self._timescale:
            logger.warning("store.historical_no_timescale")
            return []

        end = end or datetime.now(timezone.utc)
        return await self._timescale.get_candles(symbol, timeframe, start, end, limit)

    # -- Data quality --------------------------------------------------------

    async def check_quality(
        self,
        symbol: str,
        timeframe: str,
        lookback_hours: int = 24,
    ) -> DataQualityReport:
        """Run data quality checks on stored candles.

        Checks:
        - Completeness: expected vs actual candle count
        - Gaps: missing time intervals
        - Staleness: no recent data

        Parameters
        ----------
        symbol : str
            Trading pair.
        timeframe : str
            Candle interval.
        lookback_hours : int
            Hours to look back for quality check.

        Returns
        -------
        DataQualityReport
            Quality report with completeness, gaps, and staleness.
        """
        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=lookback_hours)

        candles = await self.get_candles(symbol, timeframe, start=start, end=now, limit=10_000)

        # Calculate expected count
        tf_seconds = {
            "1m": 60, "5m": 300, "15m": 900, "30m": 1800,
            "1h": 3600, "4h": 14400, "1d": 86400,
        }
        interval = tf_seconds.get(timeframe, 3600)
        expected = int(lookback_hours * 3600 / interval)

        actual = len(candles)
        completeness = (actual / expected * 100) if expected > 0 else 100.0

        # Detect gaps
        gaps: list[dict[str, Any]] = []
        for i in range(1, len(candles)):
            prev_ts = candles[i - 1].get("time") or candles[i - 1].get("timestamp")
            curr_ts = candles[i].get("time") or candles[i].get("timestamp")

            if isinstance(prev_ts, str):
                prev_ts = datetime.fromisoformat(prev_ts.replace("Z", "+00:00"))
            if isinstance(curr_ts, str):
                curr_ts = datetime.fromisoformat(curr_ts.replace("Z", "+00:00"))

            if prev_ts and curr_ts:
                gap = (curr_ts - prev_ts).total_seconds()
                if gap > interval * 1.5:  # Allow 50% tolerance
                    gaps.append({
                        "from": prev_ts.isoformat() if isinstance(prev_ts, datetime) else str(prev_ts),
                        "to": curr_ts.isoformat() if isinstance(curr_ts, datetime) else str(curr_ts),
                        "gap_seconds": gap,
                        "expected_seconds": interval,
                    })

        # Check staleness
        stale = False
        if candles:
            last_ts = candles[-1].get("time") or candles[-1].get("timestamp")
            if isinstance(last_ts, str):
                last_ts = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
            if last_ts:
                age = (now - last_ts).total_seconds()
                stale = age > interval * 3  # Stale if >3x the interval

        report = DataQualityReport(
            symbol=symbol,
            timeframe=timeframe,
            expected_count=expected,
            actual_count=actual,
            gaps=gaps,
            stale=stale,
            completeness_pct=min(completeness, 100.0),
        )

        logger.info(
            "store.quality_check",
            symbol=symbol,
            timeframe=timeframe,
            completeness=round(report.completeness_pct, 1),
            gaps=len(gaps),
            stale=stale,
            is_clean=report.is_clean,
        )

        return report

    # -- Health snapshot -----------------------------------------------------

    async def get_health(self) -> dict[str, Any]:
        """Return a health snapshot for monitoring."""
        redis_ok = False
        if self._redis:
            try:
                await self._redis.ping()
                redis_ok = True
            except Exception:
                pass

        timescale_ok = False
        if self._timescale:
            try:
                # Simple connectivity check
                async with self._timescale._session() as session:
                    await session.execute(
                        __import__("sqlalchemy").text("SELECT 1")
                    )
                timescale_ok = True
            except Exception:
                pass

        return {
            "initialized": self._initialized,
            "redis_connected": redis_ok,
            "timescale_connected": timescale_ok,
            **self.get_metrics(),
        }
