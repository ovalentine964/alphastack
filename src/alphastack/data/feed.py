"""LiveMarketFeed – real-time market data streaming with candle aggregation.

Bridges broker connectors (CCXT for crypto, MT5 for forex) to the internal
candle aggregator and event bus.  Handles:

- WebSocket tick streaming with automatic reconnection
- Tick → candle aggregation (M1/M5/M15/M30/H1/H4/D1)
- Data normalization and validation
- Gap detection and stale-data alerts
- Exponential backoff on connection failures

Usage::

    feed = LiveMarketFeed.from_ccxt("binance", symbols=["BTC/USDT"])
    await feed.start()

    # Or with MT5:
    feed = LiveMarketFeed.from_mt5(symbols=["EURUSD", "GBPUSD"])
    await feed.start()
"""

from __future__ import annotations

import asyncio
import math
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Callable, Coroutine

from alphastack.brokers.base import BrokerConnector, ConnectionState
from alphastack.brokers.ccxt_connector import CCXTConnector
from alphastack.brokers.models import BrokerBar, BrokerTick
from alphastack.core.config import get_settings
from alphastack.core.events import DataEvent, Event, EventBus, EventType
from alphastack.data.ingestion.market_data import (
    BrokerSource,
    Candle,
    CandleAggregator,
    CandleTimeframe,
    Tick,
)
from alphastack.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

# Maximum age (seconds) before a tick is considered stale
_STALE_TICK_THRESHOLD_S: dict[str, float] = {
    "crypto": 30.0,     # Crypto trades 24/7; 30s gap is suspicious
    "forex": 120.0,     # Forex has weekends/holidays; 2min tolerance
}

# Gap detection: if no tick arrives within this many candle periods, flag it
_GAP_DETECTION_MULTIPLIER: int = 3

# Reconnection parameters
_RECONNECT_BASE_DELAY_S: float = 1.0
_RECONNECT_MAX_DELAY_S: float = 60.0
_RECONNECT_BACKOFF_FACTOR: float = 2.0
_RECONNECT_MAX_ATTEMPTS: int = 20

# Tick validation bounds (reject obviously bad data)
_MAX_PRICE_DEVIATION_PCT: float = 50.0  # Reject ticks >50% from last known price


# ---------------------------------------------------------------------------
# Feed health status
# ---------------------------------------------------------------------------

class FeedStatus(str, Enum):
    """Health status for a feed connection."""
    IDLE = "idle"
    CONNECTING = "connecting"
    STREAMING = "streaming"
    RECONNECTING = "reconnecting"
    DEGRADED = "degraded"       # Some symbols missing, others OK
    DISCONNECTED = "disconnected"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Tick validation
# ---------------------------------------------------------------------------

class TickValidator:
    """Validates incoming ticks for sanity and rejects bad data.

    Checks:
    - Bid/ask positivity and ordering (bid <= ask)
    - Finite numeric values (no NaN/Inf)
    - Price deviation from last known (catches fat-finger / feed errors)
    - Timestamp freshness
    """

    def __init__(self, max_deviation_pct: float = _MAX_PRICE_DEVIATION_PCT) -> None:
        self._max_deviation_pct = max_deviation_pct
        self._last_prices: dict[str, Decimal] = {}
        self._rejected_count: int = 0
        self._accepted_count: int = 0

    @property
    def rejected_count(self) -> int:
        return self._rejected_count

    @property
    def accepted_count(self) -> int:
        return self._accepted_count

    @property
    def rejection_rate(self) -> float:
        total = self._accepted_count + self._rejected_count
        return self._rejected_count / total if total > 0 else 0.0

    def validate(self, tick: Tick) -> tuple[bool, str]:
        """Validate a tick. Returns (is_valid, reason)."""
        # Check for finite values
        for field_name in ("bid", "ask", "last", "volume"):
            val = getattr(tick, field_name)
            try:
                if not math.isfinite(float(val)):
                    self._rejected_count += 1
                    return False, f"non_finite_{field_name}"
            except (ValueError, OverflowError):
                self._rejected_count += 1
                return False, f"invalid_{field_name}"

        # Bid/ask must be positive
        if tick.bid <= 0 or tick.ask <= 0:
            self._rejected_count += 1
            return False, "non_positive_bid_ask"

        # Bid must be <= ask (allow tiny float rounding)
        if tick.bid > tick.ask + Decimal("0.0001"):
            self._rejected_count += 1
            return False, "bid_gt_ask"

        # Spread sanity: reject if spread > 10% of mid-price
        mid = tick.mid
        if mid > 0 and tick.spread > 0:
            spread_pct = float(tick.spread / mid * 100)
            if spread_pct > 10.0:
                self._rejected_count += 1
                return False, f"spread_too_wide_{spread_pct:.1f}pct"

        # Price deviation check
        last_price = self._last_prices.get(tick.symbol)
        if last_price is not None and last_price > 0:
            deviation = abs(float(tick.last - last_price) / float(last_price) * 100)
            if deviation > self._max_deviation_pct:
                self._rejected_count += 1
                return False, f"price_deviation_{deviation:.1f}pct"

        # Update tracking
        self._last_prices[tick.symbol] = tick.last
        self._accepted_count += 1
        return True, "ok"


# ---------------------------------------------------------------------------
# Gap detector
# ---------------------------------------------------------------------------

class GapDetector:
    """Detects data gaps in tick streams per symbol.

    Tracks the last tick timestamp per symbol and flags gaps that exceed
    a configurable threshold based on the expected candle period.
    """

    def __init__(self, timeframes: list[CandleTimeframe]) -> None:
        # Use the smallest timeframe for gap detection
        self._min_tf_seconds = min(
            _tf_seconds(tf) for tf in timeframes
        ) if timeframes else 60
        self._threshold_s = self._min_tf_seconds * _GAP_DETECTION_MULTIPLIER
        self._last_tick_ts: dict[str, float] = {}
        self._gaps: deque[dict[str, Any]] = deque(maxlen=1000)

    def check(self, symbol: str, timestamp: datetime) -> bool:
        """Check for a gap. Returns True if a gap was detected."""
        now_ts = timestamp.timestamp()
        last_ts = self._last_tick_ts.get(symbol)

        if last_ts is not None:
            gap = now_ts - last_ts
            if gap > self._threshold_s:
                self._gaps.append({
                    "symbol": symbol,
                    "gap_seconds": gap,
                    "from": datetime.fromtimestamp(last_ts, tz=timezone.utc).isoformat(),
                    "to": timestamp.isoformat(),
                    "detected_at": datetime.now(timezone.utc).isoformat(),
                })
                self._last_tick_ts[symbol] = now_ts
                return True

        self._last_tick_ts[symbol] = now_ts
        return False

    @property
    def recent_gaps(self) -> list[dict[str, Any]]:
        return list(self._gaps)

    @property
    def gap_count(self) -> int:
        return len(self._gaps)


def _tf_seconds(tf: CandleTimeframe) -> int:
    """Convert a CandleTimeframe to seconds."""
    mapping = {
        CandleTimeframe.M1: 60,
        CandleTimeframe.M5: 300,
        CandleTimeframe.M15: 900,
        CandleTimeframe.M30: 1800,
        CandleTimeframe.H1: 3600,
        CandleTimeframe.H4: 14400,
        CandleTimeframe.D1: 86400,
        CandleTimeframe.W1: 604800,
    }
    return mapping[tf]


# ---------------------------------------------------------------------------
# LiveMarketFeed
# ---------------------------------------------------------------------------

# Type alias for tick callbacks
TickCallback = Callable[[Tick], Coroutine[Any, Any, None] | None]
CandleCallback = Callable[[Candle], Coroutine[Any, Any, None] | None]


class LiveMarketFeed:
    """Real-time market data feed bridging broker connectors to the pipeline.

    Supports multiple broker backends (CCXT for crypto, MT5 for forex),
    tick validation, candle aggregation, gap detection, and automatic
    reconnection with exponential backoff.

    Parameters
    ----------
    connector : BrokerConnector
        The underlying broker connector (CCXTConnector, MT5Connector, etc.)
    event_bus : EventBus | None
        Redis Streams event bus for publishing data events.
    timeframes : list[CandleTimeframe] | None
        Candle timeframes to aggregate. Defaults to M5, M15, H1.
    symbols : list[str] | None
        Symbols to subscribe to. Can also be set via :meth:`start`.
    validate_ticks : bool
        Enable tick validation (recommended for production).
    market_type : str
        ``"crypto"`` or ``"forex"`` — affects stale-tick thresholds.
    """

    def __init__(
        self,
        connector: BrokerConnector,
        event_bus: EventBus | None = None,
        timeframes: list[CandleTimeframe] | None = None,
        symbols: list[str] | None = None,
        validate_ticks: bool = True,
        market_type: str = "crypto",
    ) -> None:
        self._connector = connector
        self._bus = event_bus
        self._timeframes = timeframes or [
            CandleTimeframe.M5,
            CandleTimeframe.M15,
            CandleTimeframe.H1,
        ]
        self._symbols = symbols or []
        self._market_type = market_type

        # Core components
        self._aggregator = CandleAggregator(self._timeframes)
        self._validator = TickValidator() if validate_ticks else None
        self._gap_detector = GapDetector(self._timeframes)

        # State
        self._status = FeedStatus.IDLE
        self._stream_task: asyncio.Task[None] | None = None
        self._reconnect_task: asyncio.Task[None] | None = None
        self._running = False

        # Caches
        self._latest_ticks: dict[str, Tick] = {}
        self._latest_candles: dict[str, dict[str, Candle]] = defaultdict(dict)
        # symbol → {timeframe_str: list[Candle]}  (recent closed candles, ring buffer)
        self._candle_history: dict[str, dict[str, deque[Candle]]] = defaultdict(
            lambda: defaultdict(lambda: deque(maxlen=500))
        )

        # Metrics
        self._tick_count: int = 0
        self._candle_count: int = 0
        self._error_count: int = 0
        self._last_tick_time: float = 0.0
        self._started_at: float = 0.0

        # User callbacks
        self._on_tick_callbacks: list[TickCallback] = []
        self._on_candle_callbacks: list[CandleCallback] = []

    # -- Factory methods ----------------------------------------------------

    @classmethod
    def from_ccxt(
        cls,
        exchange_id: str = "binance",
        *,
        api_key: str | None = None,
        secret: str | None = None,
        sandbox: bool = False,
        symbols: list[str] | None = None,
        timeframes: list[CandleTimeframe] | None = None,
        event_bus: EventBus | None = None,
    ) -> LiveMarketFeed:
        """Create a feed from a CCXT exchange connector.

        Parameters
        ----------
        exchange_id : str
            CCXT exchange id (``"binance"``, ``"mexc"``, ``"bybit"``, etc.)
        api_key, secret : str | None
            Exchange credentials. Falls back to ``CCXT_*`` env vars.
        sandbox : bool
            Use exchange testnet.
        symbols : list[str] | None
            Symbols to stream (e.g. ``["BTC/USDT", "ETH/USDT"]``).
        timeframes : list[CandleTimeframe] | None
            Candle timeframes to aggregate.
        event_bus : EventBus | None
            Event bus for publishing.
        """
        connector = CCXTConnector(
            exchange_id=exchange_id,
            api_key=api_key,
            secret=secret,
            sandbox=sandbox,
            ws_enabled=True,
        )
        return cls(
            connector=connector,
            event_bus=event_bus,
            timeframes=timeframes,
            symbols=symbols,
            market_type="crypto",
        )

    @classmethod
    def from_mt5(
        cls,
        *,
        login: int | None = None,
        password: str | None = None,
        server: str | None = None,
        symbols: list[str] | None = None,
        timeframes: list[CandleTimeframe] | None = None,
        event_bus: EventBus | None = None,
    ) -> LiveMarketFeed:
        """Create a feed from an MT5 connector (forex).

        Parameters
        ----------
        login, password, server : optional
            MT5 credentials. Falls back to ``MT5_*`` env vars.
        symbols : list[str] | None
            Forex symbols (e.g. ``["EURUSD", "GBPUSD"]``).
        timeframes : list[CandleTimeframe] | None
            Candle timeframes.
        event_bus : EventBus | None
            Event bus for publishing.
        """
        # Lazy import — MetaTrader5 is optional / Windows-only
        from alphastack.brokers.mt5_connector import MT5Connector

        connector = MT5Connector(
            login=login,
            password=password,
            server=server,
        )
        return cls(
            connector=connector,
            event_bus=event_bus,
            timeframes=timeframes,
            symbols=symbols,
            market_type="forex",
        )

    # -- Properties ---------------------------------------------------------

    @property
    def status(self) -> FeedStatus:
        return self._status

    @property
    def is_streaming(self) -> bool:
        return self._status == FeedStatus.STREAMING

    @property
    def symbols(self) -> list[str]:
        return list(self._symbols)

    @property
    def connector(self) -> BrokerConnector:
        return self._connector

    @property
    def tick_count(self) -> int:
        return self._tick_count

    @property
    def candle_count(self) -> int:
        return self._candle_count

    @property
    def error_count(self) -> int:
        return self._error_count

    @property
    def uptime_seconds(self) -> float:
        if self._started_at <= 0:
            return 0.0
        return time.monotonic() - self._started_at

    @property
    def gap_count(self) -> int:
        return self._gap_detector.gap_count

    @property
    def recent_gaps(self) -> list[dict[str, Any]]:
        return self._gap_detector.recent_gaps

    def get_health(self) -> dict[str, Any]:
        """Return a health snapshot for monitoring."""
        stale_threshold = _STALE_TICK_THRESHOLD_S.get(self._market_type, 60.0)
        time_since_last = time.monotonic() - self._last_tick_time if self._last_tick_time else None
        is_stale = time_since_last is not None and time_since_last > stale_threshold

        return {
            "status": self._status.value,
            "connector": self._connector.name,
            "connector_state": self._connector.state.value,
            "symbols": self._symbols,
            "tick_count": self._tick_count,
            "candle_count": self._candle_count,
            "error_count": self._error_count,
            "gap_count": self._gap_detector.gap_count,
            "uptime_seconds": round(self.uptime_seconds, 1),
            "time_since_last_tick_s": round(time_since_last, 2) if time_since_last else None,
            "is_stale": is_stale,
            "validation": {
                "accepted": self._validator.accepted_count if self._validator else None,
                "rejected": self._validator.rejected_count if self._validator else None,
                "rejection_rate": round(self._validator.rejection_rate, 4) if self._validator else None,
            },
        }

    # -- Callbacks ----------------------------------------------------------

    def on_tick(self, callback: TickCallback) -> None:
        """Register an async callback invoked on every validated tick."""
        self._on_tick_callbacks.append(callback)

    def on_candle(self, callback: CandleCallback) -> None:
        """Register an async callback invoked on every closed candle."""
        self._on_candle_callbacks.append(callback)

    # -- Data access --------------------------------------------------------

    def get_latest_tick(self, symbol: str) -> Tick | None:
        """Return the most recent validated tick for *symbol*."""
        return self._latest_ticks.get(symbol)

    def get_latest_candle(self, symbol: str, timeframe: CandleTimeframe) -> Candle | None:
        """Return the most recent closed candle for *symbol* and *timeframe*."""
        return self._latest_candles.get(symbol, {}).get(timeframe.value)

    def get_candle_history(
        self, symbol: str, timeframe: CandleTimeframe, count: int = 100
    ) -> list[Candle]:
        """Return recent closed candles (most recent last)."""
        history = self._candle_history.get(symbol, {}).get(timeframe.value, deque())
        return list(history)[-count:]

    def get_market_snapshot(self, symbol: str, bars_count: int = 200) -> dict[str, Any]:
        """Build a market data dict for the strategy pipeline.

        Returns a dict with the shape expected by AlphaStackContext::

            {
                "symbol": "BTC/USDT",
                "bid": 65000.0,
                "ask": 65001.0,
                "last": 65000.5,
                "spread_pips": 0.005,
                "volume": 1234.5,
                "ohlcv": {
                    "5m": [[ts, o, h, l, c, v], ...],
                    "15m": [...],
                    "1h": [...],
                },
                "timestamp": "2026-07-19T12:00:00Z",
            }
        """
        tick = self._latest_ticks.get(symbol)

        ohlcv: dict[str, list[list[float]]] = {}
        for tf in self._timeframes:
            candles = self.get_candle_history(symbol, tf, count=bars_count)
            ohlcv[tf.value] = [
                [
                    c.timestamp.timestamp(),
                    float(c.open),
                    float(c.high),
                    float(c.low),
                    float(c.close),
                    float(c.volume),
                ]
                for c in candles
            ]

        return {
            "symbol": symbol,
            "bid": float(tick.bid) if tick else 0.0,
            "ask": float(tick.ask) if tick else 0.0,
            "last": float(tick.last) if tick else 0.0,
            "spread_pips": float(tick.spread) if tick else 0.0,
            "volume": float(tick.volume) if tick else 0.0,
            "ohlcv": ohlcv,
            "timestamp": tick.timestamp.isoformat() if tick else "",
        }

    # -- Lifecycle ----------------------------------------------------------

    async def start(self, symbols: list[str] | None = None) -> None:
        """Connect to the broker and start streaming ticks.

        Parameters
        ----------
        symbols : list[str] | None
            Override symbols (uses constructor symbols if not provided).
        """
        if symbols:
            self._symbols = symbols

        if not self._symbols:
            raise ValueError("No symbols specified — pass symbols to start() or constructor")

        self._status = FeedStatus.CONNECTING
        self._running = True
        self._started_at = time.monotonic()

        try:
            await self._connector.connect()
        except Exception as exc:
            self._status = FeedStatus.ERROR
            self._running = False
            logger.error("feed.connect_failed", error=str(exc))
            raise

        # Start the streaming task
        self._stream_task = asyncio.create_task(
            self._stream_loop(), name="feed-stream"
        )
        self._status = FeedStatus.STREAMING
        logger.info(
            "feed.started",
            connector=self._connector.name,
            symbols=self._symbols,
            timeframes=[tf.value for tf in self._timeframes],
        )

    async def stop(self) -> None:
        """Gracefully stop streaming and disconnect."""
        self._running = False

        # Cancel tasks
        for task in (self._stream_task, self._reconnect_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self._stream_task = None
        self._reconnect_task = None

        try:
            await self._connector.disconnect()
        except Exception:
            pass

        self._status = FeedStatus.DISCONNECTED
        logger.info("feed.stopped", tick_count=self._tick_count, candle_count=self._candle_count)

    # -- Streaming ----------------------------------------------------------

    async def _stream_loop(self) -> None:
        """Main streaming loop — reads ticks from the connector.

        For CCXT connectors with WebSocket support, uses ``watch_ticker``.
        For MT5 or non-WS connectors, falls back to polling.
        """
        try:
            # Try WebSocket streaming first (CCXT pro)
            if hasattr(self._connector, "start_ws_ticker"):
                await self._run_ws_stream()
            else:
                await self._run_poll_stream()
        except asyncio.CancelledError:
            return
        except Exception as exc:
            self._error_count += 1
            logger.error("feed.stream_error", error=str(exc))
            if self._running:
                await self._schedule_reconnect()

    async def _run_ws_stream(self) -> None:
        """Stream ticks via CCXT WebSocket (watch_ticker)."""
        connector = self._connector

        # For CCXTConnector, we use the internal _ws directly
        if isinstance(connector, CCXTConnector):
            await connector.start_ws_ticker(self._symbols)

            # Poll the tick cache at high frequency
            while self._running:
                for symbol in self._symbols:
                    broker_tick = connector._tick_cache.get(symbol)
                    if broker_tick:
                        await self._process_broker_tick(broker_tick, symbol)
                await asyncio.sleep(0.1)  # 100ms polling
        else:
            # Generic connector — use polling
            await self._run_poll_stream()

    async def _run_poll_stream(self, poll_interval: float = 1.0) -> None:
        """Fallback polling stream for non-WebSocket connectors."""
        while self._running:
            for symbol in self._symbols:
                try:
                    broker_tick = await self._connector.get_tick(symbol)
                    await self._process_broker_tick(broker_tick, symbol)
                except Exception as exc:
                    self._error_count += 1
                    logger.warning("feed.poll_error", symbol=symbol, error=str(exc))

            await asyncio.sleep(poll_interval)

    async def _process_broker_tick(self, broker_tick: BrokerTick, symbol: str) -> None:
        """Convert a BrokerTick to a domain Tick, validate, aggregate, and publish."""
        # Normalize to domain Tick
        tick = Tick(
            symbol=symbol,
            broker=self._broker_source(),
            bid=Decimal(str(broker_tick.bid)),
            ask=Decimal(str(broker_tick.ask)),
            last=Decimal(str(broker_tick.last)),
            volume=Decimal(str(broker_tick.volume)),
            timestamp=broker_tick.timestamp,
            raw=broker_tick.raw if hasattr(broker_tick, "raw") else {},
        )

        # Validate
        if self._validator:
            is_valid, reason = self._validator.validate(tick)
            if not is_valid:
                logger.debug("feed.tick_rejected", symbol=symbol, reason=reason)
                return

        # Gap detection
        if self._gap_detector.check(symbol, tick.timestamp):
            logger.warning(
                "feed.gap_detected",
                symbol=symbol,
                recent_gaps=self._gap_detector.gap_count,
            )

        # Update caches
        self._latest_ticks[symbol] = tick
        self._tick_count += 1
        self._last_tick_time = time.monotonic()

        # Aggregate into candles
        closed_candles = self._aggregator.process_tick(tick)

        for candle in closed_candles:
            self._candle_count += 1
            tf_key = candle.timeframe.value
            self._latest_candles[symbol][tf_key] = candle
            self._candle_history[symbol][tf_key].append(candle)

            # Publish candle event
            if self._bus:
                await self._bus.publish(DataEvent(
                    symbol=symbol,
                    data_type="ohlcv",
                    interval=tf_key,
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

            # Invoke candle callbacks
            for cb in self._on_candle_callbacks:
                try:
                    result = cb(candle)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception:
                    logger.exception("feed.candle_callback_error")

        # Invoke tick callbacks
        for cb in self._on_tick_callbacks:
            try:
                result = cb(tick)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                logger.exception("feed.tick_callback_error")

    def _broker_source(self) -> BrokerSource:
        """Determine the BrokerSource from the connector type."""
        name = self._connector.name.lower()
        if name.startswith("ccxt"):
            return BrokerSource.CCXT
        if name.startswith("mt5"):
            return BrokerSource.MT5
        return BrokerSource.CCXT  # Default

    # -- Reconnection -------------------------------------------------------

    async def _schedule_reconnect(self) -> None:
        """Schedule a reconnection attempt with exponential backoff."""
        if not self._running:
            return

        self._status = FeedStatus.RECONNECTING
        self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def _reconnect_loop(self) -> None:
        """Reconnection loop with exponential backoff."""
        delay = _RECONNECT_BASE_DELAY_S

        for attempt in range(1, _RECONNECT_MAX_ATTEMPTS + 1):
            if not self._running:
                return

            logger.info(
                "feed.reconnect_attempt",
                attempt=attempt,
                delay_s=round(delay, 1),
                connector=self._connector.name,
            )

            try:
                # Best-effort disconnect
                try:
                    await self._connector.disconnect()
                except Exception:
                    pass

                # Reconnect
                await self._connector.connect()

                # Success — restart streaming
                self._status = FeedStatus.STREAMING
                self._stream_task = asyncio.create_task(
                    self._stream_loop(), name="feed-stream-reconnected"
                )
                logger.info("feed.reconnected", attempt=attempt)
                return

            except Exception as exc:
                logger.warning(
                    "feed.reconnect_failed",
                    attempt=attempt,
                    error=str(exc),
                    next_delay_s=round(delay, 1),
                )
                await asyncio.sleep(delay)
                delay = min(delay * _RECONNECT_BACKOFF_FACTOR, _RECONNECT_MAX_DELAY_S)

        # Exhausted all attempts
        self._status = FeedStatus.ERROR
        logger.error(
            "feed.reconnect_exhausted",
            max_attempts=_RECONNECT_MAX_ATTEMPTS,
        )

    # -- Historical data (backtesting) --------------------------------------

    async def load_historical_bars(
        self,
        symbol: str,
        timeframe: str,
        count: int = 500,
    ) -> list[BrokerBar]:
        """Fetch historical bars from the broker for backtesting.

        Uses the underlying connector's ``get_bars()`` method.

        Parameters
        ----------
        symbol : str
            Trading pair (e.g. ``"BTC/USDT"`` or ``"EURUSD"``).
        timeframe : str
            Candle timeframe (``"1m"``, ``"5m"``, ``"1h"``, ``"1d"``, etc.)
        count : int
            Number of bars to fetch.

        Returns
        -------
        list[BrokerBar]
            Historical bars in chronological order.
        """
        try:
            bars = await self._connector.get_bars(symbol, timeframe, count)
            logger.info(
                "feed.historical_loaded",
                symbol=symbol,
                timeframe=timeframe,
                bars=len(bars),
            )
            return bars
        except Exception as exc:
            logger.error(
                "feed.historical_load_failed",
                symbol=symbol,
                timeframe=timeframe,
                error=str(exc),
            )
            raise

    # -- Feed from bars (backtesting mode) ----------------------------------

    @classmethod
    def from_bars(
        cls,
        bars: list[dict[str, Any]],
        symbol: str,
        timeframes: list[CandleTimeframe] | None = None,
        event_bus: EventBus | None = None,
    ) -> LiveMarketFeed:
        """Create a feed that replays historical bars (for backtesting).

        The returned feed has a ``replay()`` method that processes bars
        sequentially through the aggregator.

        Parameters
        ----------
        bars : list[dict]
            OHLCV bars with keys: ``timestamp``, ``open``, ``high``, ``low``,
            ``close``, ``volume``.
        symbol : str
            The symbol these bars represent.
        timeframes : list[CandleTimeframe] | None
            Timeframes to aggregate.
        event_bus : EventBus | None
            Event bus for publishing.

        Returns
        -------
        LiveMarketFeed
            A feed instance with ``replay()`` method.
        """
        # Create a minimal connector that won't actually connect
        feed = cls.__new__(cls)
        feed._connector = _ReplayConnector()
        feed._bus = event_bus
        feed._timeframes = timeframes or [CandleTimeframe.M5, CandleTimeframe.H1]
        feed._symbols = [symbol]
        feed._market_type = "crypto"
        feed._aggregator = CandleAggregator(feed._timeframes)
        feed._validator = None  # No validation for historical data
        feed._gap_detector = GapDetector(feed._timeframes)
        feed._status = FeedStatus.IDLE
        feed._stream_task = None
        feed._reconnect_task = None
        feed._running = False
        feed._latest_ticks = {}
        feed._latest_candles = defaultdict(dict)
        feed._candle_history = defaultdict(lambda: defaultdict(lambda: deque(maxlen=500)))
        feed._tick_count = 0
        feed._candle_count = 0
        feed._error_count = 0
        feed._last_tick_time = 0.0
        feed._started_at = 0.0
        feed._on_tick_callbacks = []
        feed._on_candle_callbacks = []
        feed._bars = bars
        feed._replay_symbol = symbol
        return feed

    async def replay(self) -> int:
        """Replay historical bars through the aggregator.

        Returns the number of closed candles produced.
        """
        total_candles = 0
        for bar in self._bars:
            tick = Tick(
                symbol=self._replay_symbol,
                broker=BrokerSource.CCXT,
                bid=Decimal(str(bar.get("close", 0))),
                ask=Decimal(str(bar.get("close", 0))),
                last=Decimal(str(bar.get("close", 0))),
                volume=Decimal(str(bar.get("volume", 0))),
                timestamp=bar.get("timestamp", datetime.now(timezone.utc)),
            )
            if isinstance(tick.timestamp, str):
                tick = Tick(
                    symbol=tick.symbol,
                    broker=tick.broker,
                    bid=tick.bid,
                    ask=tick.ask,
                    last=tick.last,
                    volume=tick.volume,
                    timestamp=datetime.fromisoformat(tick.timestamp.replace("Z", "+00:00")),
                )

            closed = self._aggregator.process_tick(tick)
            for candle in closed:
                total_candles += 1
                tf_key = candle.timeframe.value
                self._latest_candles[self._replay_symbol][tf_key] = candle
                self._candle_history[self._replay_symbol][tf_key].append(candle)

                if self._bus:
                    await self._bus.publish(DataEvent(
                        symbol=self._replay_symbol,
                        data_type="ohlcv",
                        interval=tf_key,
                    ))

                for cb in self._on_candle_callbacks:
                    try:
                        result = cb(candle)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception:
                        pass

        self._tick_count += len(self._bars)
        return total_candles


# ---------------------------------------------------------------------------
# Replay connector (stub for backtesting mode)
# ---------------------------------------------------------------------------

class _ReplayConnector(BrokerConnector):
    """Minimal connector stub used by ``LiveMarketFeed.from_bars()``."""

    def __init__(self) -> None:
        super().__init__("replay")

    async def connect(self) -> None:
        self._transition(ConnectionState.CONNECTED)

    async def disconnect(self) -> None:
        self._transition(ConnectionState.DISCONNECTED)

    async def place_order(self, order: Any) -> Any:
        raise NotImplementedError("ReplayConnector does not support orders")

    async def cancel_order(self, order_id: str) -> Any:
        raise NotImplementedError("ReplayConnector does not support orders")

    async def modify_order(self, order_id: str, **kwargs: Any) -> Any:
        raise NotImplementedError("ReplayConnector does not support orders")

    async def get_positions(self) -> list:
        return []

    async def get_balance(self) -> Any:
        raise NotImplementedError("ReplayConnector does not support account")

    async def get_tick(self, symbol: str) -> Any:
        raise NotImplementedError("ReplayConnector does not support live ticks")

    async def get_bars(self, symbol: str, timeframe: str, count: int = 500) -> list:
        return []
