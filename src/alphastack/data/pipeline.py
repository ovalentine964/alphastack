"""DataPipeline – orchestrator coordinating feeds, storage, and event bus.

The DataPipeline is the top-level entry point for the data layer.  It:

1. Starts one or more LiveMarketFeed instances (CCXT for crypto, MT5 for forex)
2. Persists ticks and candles to MarketDataStore (TimescaleDB + Redis cache)
3. Publishes events to the Redis Streams EventBus
4. Monitors feed health and raises alerts on degradation
5. Provides a unified interface for the strategy pipeline to consume data

Usage::

    from alphastack.data import DataPipeline, LiveMarketFeed, MarketDataStore
    from alphastack.core.events import EventBus

    bus = EventBus()
    await bus.connect()

    feed_crypto = LiveMarketFeed.from_ccxt("binance", symbols=["BTC/USDT"])
    feed_forex = LiveMarketFeed.from_mt5(symbols=["EURUSD"])

    store = MarketDataStore()
    pipeline = DataPipeline(
        feeds=[feed_crypto, feed_forex],
        store=store,
        event_bus=bus,
    )
    await pipeline.start()
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine

from alphastack.core.events import DataEvent, EventBus, EventType
from alphastack.data.feed import FeedStatus, LiveMarketFeed
from alphastack.data.ingestion.market_data import Candle, CandleTimeframe, Tick
from alphastack.data.store import MarketDataStore
from alphastack.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Health check thresholds
# ---------------------------------------------------------------------------

# Interval (seconds) between health checks
_HEALTH_CHECK_INTERVAL_S: float = 30.0

# Alert if tick rate drops below this (ticks/minute per symbol)
_MIN_TICK_RATE_PER_MINUTE: float = 1.0

# Alert if any feed is in ERROR state for this long
_MAX_ERROR_DURATION_S: float = 300.0  # 5 minutes


# ---------------------------------------------------------------------------
# Pipeline status
# ---------------------------------------------------------------------------

class PipelineStatus:
    """Aggregated health status across all feeds and storage."""

    def __init__(self) -> None:
        self.feeds: dict[str, dict[str, Any]] = {}
        self.store: dict[str, Any] = {}
        self.started_at: float = 0.0
        self.uptime_seconds: float = 0.0
        self.total_ticks: int = 0
        self.total_candles: int = 0
        self.total_errors: int = 0
        self.alerts: list[str] = []

    @property
    def is_healthy(self) -> bool:
        """True if all feeds are streaming and no alerts."""
        return (
            len(self.alerts) == 0
            and all(
                f.get("status") == "streaming"
                for f in self.feeds.values()
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "healthy": self.is_healthy,
            "uptime_seconds": round(self.uptime_seconds, 1),
            "total_ticks": self.total_ticks,
            "total_candles": self.total_candles,
            "total_errors": self.total_errors,
            "feeds": self.feeds,
            "store": self.store,
            "alerts": self.alerts,
        }


# ---------------------------------------------------------------------------
# DataPipeline
# ---------------------------------------------------------------------------

class DataPipeline:
    """Orchestrates multiple market data feeds, storage, and event publishing.

    Parameters
    ----------
    feeds : list[LiveMarketFeed]
        Market data feeds to run (crypto, forex, etc.)
    store : MarketDataStore
        Storage backend (TimescaleDB + Redis).
    event_bus : EventBus | None
        Redis Streams event bus for publishing data events.
    health_check_interval : float
        Seconds between health checks.
    """

    def __init__(
        self,
        feeds: list[LiveMarketFeed],
        store: MarketDataStore,
        event_bus: EventBus | None = None,
        health_check_interval: float = _HEALTH_CHECK_INTERVAL_S,
    ) -> None:
        self._feeds = feeds
        self._store = store
        self._bus = event_bus
        self._health_interval = health_check_interval

        # Internal tasks
        self._health_task: asyncio.Task[None] | None = None
        self._store_task: asyncio.Task[None] | None = None
        self._running = False

        # Metrics
        self._started_at: float = 0.0
        self._total_ticks: int = 0
        self._total_candles: int = 0
        self._total_errors: int = 0
        self._alerts: list[str] = []

        # Queues for async store writes
        self._tick_queue: asyncio.Queue[Tick | None] = asyncio.Queue(maxsize=10_000)
        self._candle_queue: asyncio.Queue[Candle | None] = asyncio.Queue(maxsize=5_000)

    # -- Lifecycle -----------------------------------------------------------

    async def start(self) -> None:
        """Initialize storage and start all feeds.

        This is the main entry point.  It:
        1. Initializes the MarketDataStore (Redis + TimescaleDB)
        2. Registers tick/candle callbacks on each feed
        3. Starts all feeds
        4. Starts the health monitor
        5. Starts the async store writer
        """
        self._running = True
        self._started_at = time.monotonic()

        # Initialize storage
        await self._store.init()

        # Register callbacks on each feed
        for feed in self._feeds:
            feed.on_tick(self._on_tick)
            feed.on_candle(self._on_candle)

        # Start all feeds concurrently
        start_tasks = []
        for feed in self._feeds:
            start_tasks.append(asyncio.create_task(
                self._start_feed(feed), name=f"start-{feed.connector.name}"
            ))

        results = await asyncio.gather(*start_tasks, return_exceptions=True)
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self._total_errors += 1
                logger.error(
                    "pipeline.feed_start_failed",
                    feed=self._feeds[i].connector.name,
                    error=str(result),
                )

        # Start background tasks
        self._health_task = asyncio.create_task(
            self._health_loop(), name="pipeline-health"
        )
        self._store_task = asyncio.create_task(
            self._store_writer_loop(), name="pipeline-store-writer"
        )

        logger.info(
            "pipeline.started",
            feeds=[f.connector.name for f in self._feeds],
            symbols=sum(len(f.symbols) for f in self._feeds),
        )

    async def stop(self) -> None:
        """Gracefully stop all feeds and background tasks."""
        self._running = False

        # Stop feeds
        stop_tasks = [asyncio.create_task(feed.stop()) for feed in self._feeds]
        await asyncio.gather(*stop_tasks, return_exceptions=True)

        # Stop background tasks
        for task in (self._health_task, self._store_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Drain queues
        await self._tick_queue.put(None)  # Sentinel
        await self._candle_queue.put(None)

        # Close storage
        await self._store.close()

        logger.info(
            "pipeline.stopped",
            total_ticks=self._total_ticks,
            total_candles=self._total_candles,
            uptime_s=round(self.uptime_seconds, 1),
        )

    async def _start_feed(self, feed: LiveMarketFeed) -> None:
        """Start a single feed with error handling."""
        try:
            await feed.start()
        except Exception as exc:
            logger.error("pipeline.feed_start_error", feed=feed.connector.name, error=str(exc))
            raise

    # -- Properties ----------------------------------------------------------

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def uptime_seconds(self) -> float:
        if self._started_at <= 0:
            return 0.0
        return time.monotonic() - self._started_at

    @property
    def feeds(self) -> list[LiveMarketFeed]:
        return list(self._feeds)

    @property
    def store(self) -> MarketDataStore:
        return self._store

    # -- Callbacks (from feeds) ----------------------------------------------

    async def _on_tick(self, tick: Tick) -> None:
        """Handle a validated tick from any feed."""
        self._total_ticks += 1

        # Queue for async store write (non-blocking)
        try:
            self._tick_queue.put_nowait(tick)
        except asyncio.QueueFull:
            logger.warning("pipeline.tick_queue_full", symbol=tick.symbol)

        # Publish tick event to Redis Streams
        if self._bus:
            try:
                await self._bus.publish(DataEvent(
                    symbol=tick.symbol,
                    data_type="tick",
                    payload={
                        "bid": str(tick.bid),
                        "ask": str(tick.ask),
                        "last": str(tick.last),
                        "volume": str(tick.volume),
                        "timestamp": tick.timestamp.isoformat(),
                    },
                ))
            except Exception as exc:
                logger.warning("pipeline.tick_publish_failed", error=str(exc))

    async def _on_candle(self, candle: Candle) -> None:
        """Handle a closed candle from any feed."""
        self._total_candles += 1

        # Queue for async store write
        try:
            self._candle_queue.put_nowait(candle)
        except asyncio.QueueFull:
            logger.warning("pipeline.candle_queue_full", symbol=candle.symbol)

        # Publish candle event
        if self._bus:
            try:
                await self._bus.publish(DataEvent(
                    symbol=candle.symbol,
                    data_type="ohlcv",
                    interval=candle.timeframe.value,
                    payload={
                        "open": str(candle.open),
                        "high": str(candle.high),
                        "low": str(candle.low),
                        "close": str(candle.close),
                        "volume": str(candle.volume),
                        "timestamp": candle.timestamp.isoformat(),
                        "tick_count": candle.tick_count,
                    },
                ))
            except Exception as exc:
                logger.warning("pipeline.candle_publish_failed", error=str(exc))

    # -- Store writer --------------------------------------------------------

    async def _store_writer_loop(self) -> None:
        """Background task that drains tick/candle queues and writes to store."""
        while self._running:
            try:
                # Batch ticks (up to 100 at a time)
                ticks: list[Tick] = []
                for _ in range(100):
                    try:
                        tick = self._tick_queue.get_nowait()
                        if tick is None:
                            return
                        ticks.append(tick)
                    except asyncio.QueueEmpty:
                        break

                if ticks:
                    await self._store.write_ticks(ticks)

                # Batch candles (up to 50 at a time)
                candles: list[Candle] = []
                for _ in range(50):
                    try:
                        candle = self._candle_queue.get_nowait()
                        if candle is None:
                            return
                        candles.append(candle)
                    except asyncio.QueueEmpty:
                        break

                if candles:
                    await self._store.write_candles(candles)

                # Yield to the event loop
                await asyncio.sleep(0.05)  # 50ms batch interval

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("pipeline.store_writer_error", error=str(exc))
                await asyncio.sleep(1)

    # -- Health monitoring ---------------------------------------------------

    async def _health_loop(self) -> None:
        """Periodically check feed health and raise alerts."""
        while self._running:
            try:
                await asyncio.sleep(self._health_interval)
                await self._check_health()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("pipeline.health_check_error", error=str(exc))

    async def _check_health(self) -> None:
        """Run health checks on all feeds and storage."""
        alerts: list[str] = []

        for feed in self._feeds:
            health = feed.get_health()
            status = health.get("status", "unknown")

            # Check for error state
            if status in ("error", "disconnected"):
                alerts.append(f"Feed {feed.connector.name} is {status}")

            # Check for stale data
            if health.get("is_stale"):
                alerts.append(
                    f"Feed {feed.connector.name} data is stale "
                    f"(last tick {health.get('time_since_last_tick_s', '?')}s ago)"
                )

            # Check rejection rate
            validation = health.get("validation", {})
            rejection_rate = validation.get("rejection_rate", 0)
            if rejection_rate and rejection_rate > 0.1:  # >10% rejection
                alerts.append(
                    f"Feed {feed.connector.name} high tick rejection rate: "
                    f"{rejection_rate:.1%}"
                )

            # Check gaps
            if health.get("gap_count", 0) > 10:
                alerts.append(
                    f"Feed {feed.connector.name} has {health['gap_count']} data gaps"
                )

        # Check store health
        store_health = await self._store.get_health()
        if not store_health.get("redis_connected"):
            alerts.append("Redis cache is disconnected")
        if not store_health.get("timescale_connected"):
            alerts.append("TimescaleDB is disconnected")

        self._alerts = alerts

        if alerts:
            logger.warning("pipeline.health_alerts", alerts=alerts)
        else:
            logger.debug("pipeline.health_ok")

    # -- Public API ----------------------------------------------------------

    def get_status(self) -> PipelineStatus:
        """Return aggregated pipeline status."""
        status = PipelineStatus()
        status.started_at = self._started_at
        status.uptime_seconds = self.uptime_seconds
        status.total_ticks = self._total_ticks
        status.total_candles = self._total_candles
        status.total_errors = self._total_errors
        status.alerts = list(self._alerts)

        for feed in self._feeds:
            status.feeds[feed.connector.name] = feed.get_health()

        status.store = self._store.get_metrics()
        return status

    def get_feed(self, name: str) -> LiveMarketFeed | None:
        """Get a feed by connector name."""
        for feed in self._feeds:
            if feed.connector.name == name:
                return feed
        return None

    def get_market_snapshot(self, symbol: str, bars_count: int = 200) -> dict[str, Any]:
        """Get a market data snapshot from the first feed that has the symbol.

        Returns the dict shape expected by the strategy pipeline.
        """
        for feed in self._feeds:
            if symbol in feed.symbols:
                return feed.get_market_snapshot(symbol, bars_count)

        # Symbol not found in any feed
        return {
            "symbol": symbol,
            "bid": 0.0,
            "ask": 0.0,
            "last": 0.0,
            "spread_pips": 0.0,
            "volume": 0.0,
            "ohlcv": {},
            "timestamp": "",
        }

    async def load_historical(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime | None = None,
        limit: int = 10_000,
    ) -> list[dict[str, Any]]:
        """Load historical candles from the store for backtesting."""
        return await self._store.load_historical(symbol, timeframe, start, end, limit)

    async def check_data_quality(
        self,
        symbol: str,
        timeframe: str,
        lookback_hours: int = 24,
    ) -> dict[str, Any]:
        """Run data quality checks and return report as dict."""
        report = await self._store.check_quality(symbol, timeframe, lookback_hours)
        return report.to_dict()
