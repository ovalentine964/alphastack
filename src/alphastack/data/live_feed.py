"""LiveMarketFeed – real-time Binance WebSocket feed with candle aggregation.

Connects to Binance (or any CCXT-supported exchange) via WebSocket for
real-time tick streaming, aggregates ticks into OHLCV candles (M1/M5/M15),
and publishes to the Redis Streams EventBus on the ``market_data`` channel.

No API keys required for public market data endpoints.

Usage::

    feed = LiveMarketFeed(symbols=["BTC/USDT", "ETH/USDT"])
    await feed.start()
    # ... live ticks and candles flowing ...
    await feed.stop()

Or as an async context manager::

    async with LiveMarketFeed(symbols=["BTC/USDT"]) as feed:
        async for event in feed.stream():
            print(event)
"""

from __future__ import annotations

import asyncio
import json
import time
import traceback
from collections import defaultdict, deque
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, AsyncIterator

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
# Configuration
# ---------------------------------------------------------------------------

# Reconnection backoff parameters
_RECONNECT_BASE_DELAY_S: float = 1.0
_RECONNECT_MAX_DELAY_S: float = 60.0
_RECONNECT_BACKOFF_FACTOR: float = 2.0
_RECONNECT_MAX_ATTEMPTS: int = 50

# Tick staleness detection
_STALE_TICK_THRESHOLD_S: float = 30.0

# How often to check for new ticks from the WS cache (seconds)
_TICK_POLL_INTERVAL_S: float = 0.1

# Default timeframes for candle aggregation
_DEFAULT_TIMEFRAMES: list[CandleTimeframe] = [
    CandleTimeframe.M1,
    CandleTimeframe.M5,
    CandleTimeframe.M15,
]


# ---------------------------------------------------------------------------
# Feed status
# ---------------------------------------------------------------------------

class LiveFeedStatus(str, Enum):
    """Health status for the live feed."""
    IDLE = "idle"
    CONNECTING = "connecting"
    STREAMING = "streaming"
    RECONNECTING = "reconnecting"
    STOPPED = "stopped"
    ERROR = "error"


# ---------------------------------------------------------------------------
# LiveMarketFeed
# ---------------------------------------------------------------------------

class LiveMarketFeed:
    """Real-time market data feed from Binance (or any CCXT exchange).

    Connects via WebSocket, aggregates ticks into candles, and optionally
    publishes events to a Redis Streams EventBus.

    Parameters
    ----------
    exchange_id : str
        CCXT exchange id (default ``"binance"``).
    symbols : list[str]
        Trading pairs to stream (e.g. ``["BTC/USDT", "ETH/USDT"]``).
    timeframes : list[CandleTimeframe] | None
        Candle timeframes to aggregate. Defaults to M1, M5, M15.
    event_bus : EventBus | None
        Redis Streams event bus. If provided, events are published on
        the ``market_data`` stream.
    api_key, secret : str | None
        Exchange credentials. Not needed for public market data.
    sandbox : bool
        Use exchange testnet.
    validate_ticks : bool
        Enable tick validation (rejects bad data).
    """

    def __init__(
        self,
        exchange_id: str = "binance",
        symbols: list[str] | None = None,
        timeframes: list[CandleTimeframe] | None = None,
        event_bus: Any | None = None,
        api_key: str | None = None,
        secret: str | None = None,
        sandbox: bool = False,
        validate_ticks: bool = True,
    ) -> None:
        self._exchange_id = exchange_id
        self._symbols = symbols or ["BTC/USDT", "ETH/USDT"]
        self._timeframes = timeframes or _DEFAULT_TIMEFRAMES
        self._bus = event_bus
        self._api_key = api_key
        self._secret = secret
        self._sandbox = sandbox
        self._validate_ticks = validate_ticks

        # CCXT exchange instances
        self._exchange: Any = None       # REST (for historical bars)
        self._ws_exchange: Any = None    # WebSocket (ccxt.pro)

        # Core components
        self._aggregator = CandleAggregator(self._timeframes)

        # State
        self._status = LiveFeedStatus.IDLE
        self._running = False
        self._stream_task: asyncio.Task[None] | None = None
        self._reconnect_task: asyncio.Task[None] | None = None

        # Tick tracking
        self._last_tick: dict[str, Tick] = {}           # symbol → latest Tick
        self._last_tick_ts: dict[str, float] = {}       # symbol → monotonic time
        self._tick_count: int = 0
        self._candle_count: int = 0
        self._error_count: int = 0
        self._started_at: float = 0.0

        # Closed candle history (ring buffer per symbol+timeframe)
        self._candle_history: dict[str, dict[str, deque[Candle]]] = defaultdict(
            lambda: defaultdict(lambda: deque(maxlen=500))
        )

        # User callbacks
        self._on_tick_callbacks: list[Any] = []
        self._on_candle_callbacks: list[Any] = []

        # Raw tick queue from WS → processing loop
        self._tick_queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(maxsize=50_000)

    # -- Properties ---------------------------------------------------------

    @property
    def status(self) -> LiveFeedStatus:
        return self._status

    @property
    def is_streaming(self) -> bool:
        return self._status == LiveFeedStatus.STREAMING

    @property
    def symbols(self) -> list[str]:
        return list(self._symbols)

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

    def get_latest_tick(self, symbol: str) -> Tick | None:
        """Return the most recent tick for *symbol*."""
        return self._last_tick.get(symbol)

    def get_latest_candle(self, symbol: str, timeframe: CandleTimeframe) -> Candle | None:
        """Return the most recent closed candle."""
        history = self._candle_history.get(symbol, {}).get(timeframe.value)
        return history[-1] if history else None

    def get_candle_history(
        self, symbol: str, timeframe: CandleTimeframe, count: int = 100
    ) -> list[Candle]:
        """Return recent closed candles (most recent last)."""
        history = self._candle_history.get(symbol, {}).get(timeframe.value, deque())
        return list(history)[-count:]

    def get_health(self) -> dict[str, Any]:
        """Return a health snapshot for monitoring."""
        now = time.monotonic()
        time_since_last: float | None = None
        is_stale = False

        if self._last_tick_ts:
            oldest = min(self._last_tick_ts.values())
            time_since_last = now - oldest
            is_stale = time_since_last > _STALE_TICK_THRESHOLD_S

        return {
            "status": self._status.value,
            "exchange": self._exchange_id,
            "symbols": self._symbols,
            "tick_count": self._tick_count,
            "candle_count": self._candle_count,
            "error_count": self._error_count,
            "uptime_seconds": round(self.uptime_seconds, 1),
            "time_since_last_tick_s": round(time_since_last, 2) if time_since_last else None,
            "is_stale": is_stale,
            "latest_prices": {
                sym: str(tick.last)
                for sym, tick in self._last_tick.items()
            },
        }

    # -- Callbacks ----------------------------------------------------------

    def on_tick(self, callback: Any) -> None:
        """Register an async callback invoked on every validated tick."""
        self._on_tick_callbacks.append(callback)

    def on_candle(self, callback: Any) -> None:
        """Register an async callback invoked on every closed candle."""
        self._on_candle_callbacks.append(callback)

    # -- Lifecycle ----------------------------------------------------------

    async def start(self, symbols: list[str] | None = None) -> None:
        """Connect to the exchange and start streaming ticks.

        Parameters
        ----------
        symbols : list[str] | None
            Override symbols (uses constructor symbols if not provided).
        """
        if symbols:
            self._symbols = symbols

        if not self._symbols:
            raise ValueError("No symbols specified")

        self._status = LiveFeedStatus.CONNECTING
        self._running = True
        self._started_at = time.monotonic()

        try:
            await self._connect_exchanges()
        except Exception as exc:
            self._status = LiveFeedStatus.ERROR
            self._running = False
            logger.error("live_feed.connect_failed", error=str(exc))
            raise

        # Start the streaming task
        self._stream_task = asyncio.create_task(
            self._stream_loop(), name="live-feed-stream"
        )
        self._status = LiveFeedStatus.STREAMING
        logger.info(
            "live_feed.started",
            exchange=self._exchange_id,
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

        # Drain the tick queue
        while not self._tick_queue.empty():
            try:
                self._tick_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        # Close exchanges
        await self._disconnect_exchanges()

        self._status = LiveFeedStatus.STOPPED
        logger.info(
            "live_feed.stopped",
            tick_count=self._tick_count,
            candle_count=self._candle_count,
            uptime_s=round(self.uptime_seconds, 1),
        )

    async def __aenter__(self) -> LiveMarketFeed:
        await self.start()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.stop()

    # -- Exchange connection ------------------------------------------------

    async def _connect_exchanges(self) -> None:
        """Initialize CCXT REST and WebSocket exchange instances."""
        try:
            import ccxt.async_support as ccxt_async
        except ImportError:
            import ccxt as ccxt_async  # type: ignore[no-redef]

        try:
            import ccxt.pro as ccxt_pro
        except ImportError:
            raise ImportError(
                "ccxt.pro is required for WebSocket streaming. "
                "Install with: pip install 'ccxt[pro]'"
            )

        # REST exchange (for historical bars, fallback polling)
        exchange_class = getattr(ccxt_async, self._exchange_id, None)
        if exchange_class is None:
            raise ValueError(f"Unknown CCXT exchange: {self._exchange_id}")

        config: dict[str, Any] = {
            "enableRateLimit": True,
        }
        if self._api_key:
            config["apiKey"] = self._api_key
        if self._secret:
            config["secret"] = self._secret

        self._exchange = exchange_class(config)
        if self._sandbox:
            self._exchange.set_sandbox_mode(True)

        # Load markets to verify connectivity
        await self._exchange.load_markets()
        logger.info("live_feed.rest_connected", exchange=self._exchange_id)

        # WebSocket exchange (for real-time streaming)
        ws_class = getattr(ccxt_pro, self._exchange_id, None)
        if ws_class is None:
            raise ValueError(f"ccxt.pro does not support: {self._exchange_id}")

        ws_config: dict[str, Any] = {"enableRateLimit": True}
        if self._api_key:
            ws_config["apiKey"] = self._api_key
        if self._secret:
            ws_config["secret"] = self._secret

        self._ws_exchange = ws_class(ws_config)
        if self._sandbox:
            self._ws_exchange.set_sandbox_mode(True)

        logger.info("live_feed.ws_initialized", exchange=self._exchange_id)

    async def _disconnect_exchanges(self) -> None:
        """Close both REST and WebSocket exchange connections."""
        for name, ex in [("ws", self._ws_exchange), ("rest", self._exchange)]:
            if ex:
                try:
                    await ex.close()
                except Exception as exc:
                    logger.debug("live_feed.close_error", exchange=name, error=str(exc))

        self._ws_exchange = None
        self._exchange = None

    # -- Streaming ----------------------------------------------------------

    async def _stream_loop(self) -> None:
        """Main streaming loop — runs WS ticker and processes ticks."""
        try:
            # Start the WebSocket ticker consumer in background
            ws_task = asyncio.create_task(
                self._ws_ticker_loop(), name="live-feed-ws"
            )
            # Start the tick processor
            process_task = asyncio.create_task(
                self._tick_processor_loop(), name="live-feed-processor"
            )

            # Wait for both; if either fails, stop the other
            done, pending = await asyncio.wait(
                [ws_task, process_task],
                return_when=asyncio.FIRST_EXCEPTION,
            )

            # Cancel remaining
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            # Check for exceptions
            for task in done:
                if task.exception():
                    raise task.exception()

        except asyncio.CancelledError:
            return
        except Exception as exc:
            self._error_count += 1
            logger.error(
                "live_feed.stream_error",
                error=str(exc),
                traceback=traceback.format_exc(),
            )
            if self._running:
                await self._schedule_reconnect()

    async def _ws_ticker_loop(self) -> None:
        """Consume WebSocket tickers from ccxt.pro and queue raw data."""
        ws = self._ws_exchange
        if ws is None:
            raise RuntimeError("WebSocket exchange not initialized")

        logger.info("live_feed.ws_starting", symbols=self._symbols)

        while self._running:
            try:
                for symbol in self._symbols:
                    if not self._running:
                        return

                    ticker = await ws.watch_ticker(symbol)

                    # Build raw tick dict
                    raw_tick = {
                        "symbol": symbol,
                        "bid": float(ticker.get("bid") or 0),
                        "ask": float(ticker.get("ask") or 0),
                        "last": float(ticker.get("last") or 0),
                        "volume": float(ticker.get("quoteVolume") or ticker.get("baseVolume") or 0),
                        "timestamp": ticker.get("timestamp"),
                        "raw": ticker,
                    }

                    # Non-blocking enqueue
                    try:
                        self._tick_queue.put_nowait(raw_tick)
                    except asyncio.QueueFull:
                        # Drop oldest to make room
                        try:
                            self._tick_queue.get_nowait()
                        except asyncio.QueueEmpty:
                            pass
                        self._tick_queue.put_nowait(raw_tick)

            except asyncio.CancelledError:
                return
            except Exception as exc:
                if not self._running:
                    return
                logger.warning("live_feed.ws_tick_error", error=str(exc))
                await asyncio.sleep(1)

    async def _tick_processor_loop(self) -> None:
        """Process raw ticks from the queue: validate, aggregate, publish."""
        while self._running:
            try:
                # Block briefly for a tick
                raw = await asyncio.wait_for(
                    self._tick_queue.get(), timeout=1.0
                )
                if raw is None:
                    continue

                await self._process_raw_tick(raw)

            except asyncio.TimeoutError:
                # No tick within timeout — check staleness
                continue
            except asyncio.CancelledError:
                return
            except Exception as exc:
                self._error_count += 1
                logger.warning("live_feed.process_error", error=str(exc))

    async def _process_raw_tick(self, raw: dict[str, Any]) -> None:
        """Validate, aggregate, and publish a single tick."""
        symbol = raw["symbol"]
        now = datetime.now(timezone.utc)

        # Parse timestamp
        ts_raw = raw.get("timestamp")
        if ts_raw and isinstance(ts_raw, (int, float)) and ts_raw > 0:
            # CCXT timestamps are in milliseconds
            if ts_raw > 1e12:
                ts_raw = ts_raw / 1000.0
            timestamp = datetime.fromtimestamp(ts_raw, tz=timezone.utc)
        else:
            timestamp = now

        # Build domain Tick
        try:
            tick = Tick(
                symbol=symbol,
                broker=BrokerSource.CCXT,
                bid=Decimal(str(raw["bid"])),
                ask=Decimal(str(raw["ask"])),
                last=Decimal(str(raw["last"])),
                volume=Decimal(str(raw.get("volume", 0))),
                timestamp=timestamp,
                raw=raw.get("raw", {}),
            )
        except (InvalidOperation, ValueError, KeyError) as exc:
            logger.debug("live_feed.tick_parse_error", symbol=symbol, error=str(exc))
            return

        # Validate
        if self._validate_ticks:
            is_valid, reason = self._validate_tick(tick)
            if not is_valid:
                logger.debug("live_feed.tick_rejected", symbol=symbol, reason=reason)
                return

        # Update state
        self._last_tick[symbol] = tick
        self._last_tick_ts[symbol] = time.monotonic()
        self._tick_count += 1

        # Aggregate into candles
        closed_candles = self._aggregator.process_tick(tick)

        for candle in closed_candles:
            self._candle_count += 1
            tf_key = candle.timeframe.value
            self._candle_history[symbol][tf_key].append(candle)

            # Publish candle to EventBus
            if self._bus:
                try:
                    from alphastack.core.events import DataEvent
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
                except Exception as exc:
                    logger.debug("live_feed.candle_publish_error", error=str(exc))

            # Invoke candle callbacks
            for cb in self._on_candle_callbacks:
                try:
                    result = cb(candle)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception:
                    logger.exception("live_feed.candle_callback_error")

        # Publish tick to EventBus
        if self._bus:
            try:
                from alphastack.core.events import DataEvent
                await self._bus.publish(DataEvent(
                    symbol=symbol,
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
                logger.debug("live_feed.tick_publish_error", error=str(exc))

        # Invoke tick callbacks
        for cb in self._on_tick_callbacks:
            try:
                result = cb(tick)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                logger.exception("live_feed.tick_callback_error")

    # -- Tick validation ----------------------------------------------------

    def _validate_tick(self, tick: Tick) -> tuple[bool, str]:
        """Validate a tick for sanity. Returns (is_valid, reason)."""
        # Check for finite values
        for field_name in ("bid", "ask", "last", "volume"):
            val = getattr(tick, field_name)
            try:
                v = float(val)
                if v != v:  # NaN check
                    return False, f"nan_{field_name}"
            except (ValueError, OverflowError):
                return False, f"invalid_{field_name}"

        # Bid/ask must be positive
        if tick.bid <= 0 or tick.ask <= 0:
            return False, "non_positive_bid_ask"

        # Bid must be <= ask
        if tick.bid > tick.ask + Decimal("0.01"):
            return False, "bid_gt_ask"

        # Spread sanity: reject if spread > 10% of mid-price
        mid = tick.mid
        if mid > 0 and tick.spread > 0:
            spread_pct = float(tick.spread / mid * 100)
            if spread_pct > 10.0:
                return False, f"spread_too_wide_{spread_pct:.1f}pct"

        return True, "ok"

    # -- Reconnection -------------------------------------------------------

    async def _schedule_reconnect(self) -> None:
        """Schedule a reconnection attempt with exponential backoff."""
        if not self._running:
            return

        self._status = LiveFeedStatus.RECONNECTING
        self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def _reconnect_loop(self) -> None:
        """Reconnection loop with exponential backoff."""
        delay = _RECONNECT_BASE_DELAY_S

        for attempt in range(1, _RECONNECT_MAX_ATTEMPTS + 1):
            if not self._running:
                return

            logger.info(
                "live_feed.reconnect_attempt",
                attempt=attempt,
                delay_s=round(delay, 1),
            )

            try:
                # Best-effort disconnect
                await self._disconnect_exchanges()

                # Reconnect
                await self._connect_exchanges()

                # Success — restart streaming
                self._status = LiveFeedStatus.STREAMING
                self._stream_task = asyncio.create_task(
                    self._stream_loop(), name="live-feed-stream-reconnected"
                )
                logger.info("live_feed.reconnected", attempt=attempt)
                return

            except Exception as exc:
                logger.warning(
                    "live_feed.reconnect_failed",
                    attempt=attempt,
                    error=str(exc),
                    next_delay_s=round(delay, 1),
                )
                await asyncio.sleep(delay)
                delay = min(delay * _RECONNECT_BACKOFF_FACTOR, _RECONNECT_MAX_DELAY_S)

        # Exhausted all attempts
        self._status = LiveFeedStatus.ERROR
        logger.error("live_feed.reconnect_exhausted", max_attempts=_RECONNECT_MAX_ATTEMPTS)

    # -- Historical bars (for backtesting / warm-up) ------------------------

    async def load_historical_bars(
        self,
        symbol: str,
        timeframe: str = "1m",
        count: int = 500,
    ) -> list[dict[str, Any]]:
        """Fetch historical OHLCV bars from the REST API.

        Useful for warming up indicators before live streaming starts.

        Parameters
        ----------
        symbol : str
            Trading pair (e.g. ``"BTC/USDT"``).
        timeframe : str
            Candle interval (``"1m"``, ``"5m"``, ``"1h"``, etc.)
        count : int
            Number of bars to fetch.

        Returns
        -------
        list[dict]
            OHLCV bars with keys: ``timestamp``, ``open``, ``high``, ``low``,
            ``close``, ``volume``.
        """
        if not self._exchange:
            raise RuntimeError("Exchange not connected — call start() first")

        ohlcv = await self._exchange.fetch_ohlcv(symbol, timeframe, limit=count)
        bars = []
        for c in (ohlcv or []):
            bars.append({
                "timestamp": datetime.fromtimestamp(c[0] / 1000, tz=timezone.utc),
                "open": float(c[1]),
                "high": float(c[2]),
                "low": float(c[3]),
                "close": float(c[4]),
                "volume": float(c[5]),
            })
        return bars

    # -- Async iterator interface -------------------------------------------

    async def stream(self) -> AsyncIterator[dict[str, Any]]:
        """Async generator that yields live market events.

        Yields dicts with ``event_type`` ("tick" or "candle") and the
        corresponding data. Useful for consumers that want to iterate
        over live data::

            async for event in feed.stream():
                if event["event_type"] == "tick":
                    print(f'{event["symbol"]}: {event["last"]}')
        """
        # Register callbacks that push to an internal queue
        event_queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(maxsize=10_000)

        async def _tick_handler(tick: Tick) -> None:
            await event_queue.put({
                "event_type": "tick",
                "symbol": tick.symbol,
                "bid": str(tick.bid),
                "ask": str(tick.ask),
                "last": str(tick.last),
                "volume": str(tick.volume),
                "timestamp": tick.timestamp.isoformat(),
            })

        async def _candle_handler(candle: Candle) -> None:
            await event_queue.put({
                "event_type": "candle",
                "symbol": candle.symbol,
                "timeframe": candle.timeframe.value,
                "open": str(candle.open),
                "high": str(candle.high),
                "low": str(candle.low),
                "close": str(candle.close),
                "volume": str(candle.volume),
                "timestamp": candle.timestamp.isoformat(),
                "tick_count": candle.tick_count,
            })

        self.on_tick(_tick_handler)
        self.on_candle(_candle_handler)

        try:
            while self._running:
                try:
                    event = await asyncio.wait_for(event_queue.get(), timeout=1.0)
                    if event is not None:
                        yield event
                except asyncio.TimeoutError:
                    continue
        except asyncio.CancelledError:
            return
        finally:
            # Remove callbacks to avoid leaks
            if _tick_handler in self._on_tick_callbacks:
                self._on_tick_callbacks.remove(_tick_handler)
            if _candle_handler in self._on_candle_callbacks:
                self._on_candle_callbacks.remove(_candle_handler)
