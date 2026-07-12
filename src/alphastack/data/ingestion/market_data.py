"""Market Data Ingestion – real-time ticks, OHLCV aggregation, normalization."""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Callable

from alphastack.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------

class BrokerSource(str, Enum):
    MT5 = "mt5"
    CCXT = "ccxt"
    POLYGON = "polygon"
    FINNHUB = "finnhub"
    ALPHA_VANTAGE = "alpha_vantage"


class CandleTimeframe(str, Enum):
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"


@dataclass(frozen=True, slots=True)
class Tick:
    """Normalized tick across all brokers."""

    symbol: str
    broker: BrokerSource
    bid: Decimal
    ask: Decimal
    last: Decimal
    volume: Decimal
    timestamp: datetime  # UTC
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def mid(self) -> Decimal:
        return (self.bid + self.ask) / 2

    @property
    def spread(self) -> Decimal:
        return self.ask - self.bid


@dataclass(slots=True)
class Candle:
    """OHLCV candle bar."""

    symbol: str
    timeframe: CandleTimeframe
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    timestamp: datetime  # bar open time (UTC)
    tick_count: int = 0
    is_closed: bool = False

    def update(self, tick: Tick) -> None:
        """Incorporate a new tick into the current candle."""
        self.high = max(self.high, tick.last)
        self.low = min(self.low, tick.last)
        self.close = tick.last
        self.volume += tick.volume
        self.tick_count += 1


# ---------------------------------------------------------------------------
# Event bus (lightweight in-process pub/sub)
# ---------------------------------------------------------------------------

EventCallback = Callable[[str, dict[str, Any]], None]


class EventBus:
    """Simple synchronous event bus for data pipeline events."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventCallback]] = defaultdict(list)

    def subscribe(self, event: str, callback: EventCallback) -> None:
        self._subscribers[event].append(callback)

    def publish(self, event: str, payload: dict[str, Any]) -> None:
        for cb in self._subscribers.get(event, []):
            try:
                cb(event, payload)
            except Exception:
                logger.exception("event_callback_error", event=event)

    def clear(self) -> None:
        self._subscribers.clear()


# ---------------------------------------------------------------------------
# Abstract broker connector
# ---------------------------------------------------------------------------

class BrokerConnector(ABC):
    """Base class for broker data connectors."""

    def __init__(self, source: BrokerSource) -> None:
        self.source = source
        self._running = False

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def subscribe_ticks(self, symbols: list[str]) -> None: ...

    @abstractmethod
    async def _stream_ticks(self) -> Any:
        """Yield raw tick dicts from the broker websocket/API."""
        ...

    async def tick_generator(self):
        """Async generator that yields normalized Tick objects."""
        async for raw in self._stream_ticks():
            yield self._normalize(raw)

    def _normalize(self, raw: dict[str, Any]) -> Tick:
        """Override per-broker normalization. Default passthrough."""
        return Tick(
            symbol=raw["symbol"],
            broker=self.source,
            bid=Decimal(str(raw.get("bid", 0))),
            ask=Decimal(str(raw.get("ask", 0))),
            last=Decimal(str(raw.get("last", 0))),
            volume=Decimal(str(raw.get("volume", 0))),
            timestamp=raw.get("timestamp", datetime.now(timezone.utc)),
            raw=raw,
        )


# ---------------------------------------------------------------------------
# Candle Aggregator
# ---------------------------------------------------------------------------

class CandleAggregator:
    """Aggregates ticks into OHLCV candles for multiple symbols/timeframes."""

    def __init__(self, timeframes: list[CandleTimeframe] | None = None) -> None:
        self.timeframes = timeframes or [CandleTimeframe.M1, CandleTimeframe.M5, CandleTimeframe.H1]
        # Key: (symbol, timeframe) → current open candle
        self._candles: dict[tuple[str, CandleTimeframe], Candle] = {}

    def _bar_open_time(self, ts: datetime, tf: CandleTimeframe) -> datetime:
        """Compute the bar-open timestamp for *ts* given *tf*."""
        epoch = int(ts.timestamp())
        seconds = _tf_seconds(tf)
        bar_ts = epoch - (epoch % seconds)
        return datetime.fromtimestamp(bar_ts, tz=timezone.utc)

    def process_tick(self, tick: Tick) -> list[Candle]:
        """Feed a tick; return any *closed* candles."""
        closed: list[Candle] = []
        for tf in self.timeframes:
            key = (tick.symbol, tf)
            bar_open = self._bar_open_time(tick.timestamp, tf)
            current = self._candles.get(key)

            if current is None:
                candle = Candle(
                    symbol=tick.symbol,
                    timeframe=tf,
                    open=tick.last,
                    high=tick.last,
                    low=tick.last,
                    close=tick.last,
                    volume=tick.volume,
                    timestamp=bar_open,
                    tick_count=1,
                )
                self._candles[key] = candle
            elif current.timestamp < bar_open:
                # New bar period → close the old one
                current.is_closed = True
                closed.append(current)
                candle = Candle(
                    symbol=tick.symbol,
                    timeframe=tf,
                    open=tick.last,
                    high=tick.last,
                    low=tick.last,
                    close=tick.last,
                    volume=tick.volume,
                    timestamp=bar_open,
                    tick_count=1,
                )
                self._candles[key] = candle
            else:
                current.update(tick)
        return closed


def _tf_seconds(tf: CandleTimeframe) -> int:
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
# Market Data Pipeline (orchestrator)
# ---------------------------------------------------------------------------

class MarketDataPipeline:
    """Top-level orchestrator: connects brokers, aggregates, publishes events."""

    def __init__(
        self,
        connectors: list[BrokerConnector],
        event_bus: EventBus | None = None,
        timeframes: list[CandleTimeframe] | None = None,
    ) -> None:
        self.connectors = connectors
        self.bus = event_bus or EventBus()
        self.aggregator = CandleAggregator(timeframes)
        self._tasks: list[asyncio.Task] = []

    async def start(self, symbols: list[str]) -> None:
        """Connect all brokers and start ingesting."""
        for conn in self.connectors:
            await conn.connect()
            await conn.subscribe_ticks(symbols)
            task = asyncio.create_task(self._ingest(conn), name=f"ingest-{conn.source.value}")
            self._tasks.append(task)
        logger.info("pipeline_started", brokers=[c.source.value for c in self.connectors])

    async def stop(self) -> None:
        """Gracefully stop all ingestion tasks."""
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        for conn in self.connectors:
            await conn.disconnect()
        self._tasks.clear()
        logger.info("pipeline_stopped")

    async def _ingest(self, conn: BrokerConnector) -> None:
        try:
            async for tick in conn.tick_generator():
                self.bus.publish("tick", {"tick": tick})
                closed = self.aggregator.process_tick(tick)
                for candle in closed:
                    self.bus.publish("candle_closed", {"candle": candle})
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("ingest_error", broker=conn.source.value)
