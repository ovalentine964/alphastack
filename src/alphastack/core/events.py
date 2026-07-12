"""Event bus system for AlphaStack using Redis Streams."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine

from pydantic import BaseModel, Field
from redis.asyncio import Redis

from alphastack.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Event base & types
# ---------------------------------------------------------------------------

class EventType(str, Enum):
    SIGNAL = "signal"
    TRADE = "trade"
    RISK = "risk"
    DATA = "data"
    AGENT = "agent"


class Event(BaseModel):
    """Base event model."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    type: EventType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_stream_message(self) -> dict[str, str]:
        """Serialize for XADD."""
        return {"data": self.model_dump_json()}

    @classmethod
    def from_stream_message(cls, raw: dict[bytes, bytes]) -> Event:
        """Deserialize from XREAD output."""
        data = raw.get(b"data", b"{}")
        return cls.model_validate_json(data)


class SignalEvent(Event):
    """A trading signal emitted by a strategy or agent."""

    type: EventType = EventType.SIGNAL
    symbol: str = ""
    side: str = ""  # "long" | "short" | "flat"
    strength: float = 0.0  # -1.0 to 1.0
    timeframe: str = ""
    strategy: str = ""


class TradeEvent(Event):
    """An order execution or fill event."""

    type: EventType = EventType.TRADE
    order_id: str = ""
    symbol: str = ""
    side: str = ""  # "buy" | "sell"
    quantity: float = 0.0
    price: float = 0.0
    order_type: str = "market"  # "market" | "limit" | "stop"
    status: str = "new"  # "new" | "filled" | "cancelled" | "rejected"


class RiskEvent(Event):
    """A risk limit breach or warning."""

    type: EventType = EventType.RISK
    level: str = "warning"  # "info" | "warning" | "critical"
    rule: str = ""
    message: str = ""
    current_value: float = 0.0
    limit: float = 0.0


class DataEvent(Event):
    """New market data received."""

    type: EventType = EventType.DATA
    symbol: str = ""
    data_type: str = "ohlcv"  # "ohlcv" | "tick" | "orderbook"
    interval: str = ""


class AgentEvent(Event):
    """An agent decision or action."""

    type: EventType = EventType.AGENT
    agent_id: str = ""
    action: str = ""  # "analyze" | "decide" | "execute" | "report"
    reasoning: str = ""
    confidence: float = 0.0


# ---------------------------------------------------------------------------
# Event Bus (Redis Streams)
# ---------------------------------------------------------------------------

STREAM_PREFIX = "alphastack:events"
CONSUMER_GROUP = "alphastack_workers"

EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


class EventBus:
    """Redis Streams-based event bus with consumer groups.

    Usage::

        bus = EventBus(redis_url="redis://localhost:6379/0")
        await bus.connect()
        await bus.publish(SignalEvent(symbol="BTC/USDT", side="long", strength=0.85))
        await bus.subscribe(EventType.SIGNAL, my_handler)
        await bus.listen()
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0") -> None:
        self._redis_url = redis_url
        self._redis: Redis | None = None
        self._handlers: dict[EventType, list[EventHandler]] = {}
        self._running = False

    # -- lifecycle -----------------------------------------------------------

    async def connect(self) -> None:
        self._redis = Redis.from_url(self._redis_url, decode_responses=False)
        await self._redis.ping()
        logger.info("event_bus.connected", redis_url=self._redis_url)

    async def close(self) -> None:
        if self._redis:
            await self._redis.aclose()
            self._redis = None
        logger.info("event_bus.closed")

    @property
    def redis(self) -> Redis:
        if self._redis is None:
            raise RuntimeError("EventBus not connected – call connect() first")
        return self._redis

    # -- stream helpers ------------------------------------------------------

    @staticmethod
    def _stream_key(event_type: EventType) -> str:
        return f"{STREAM_PREFIX}:{event_type.value}"

    # -- publish -------------------------------------------------------------

    async def publish(self, event: Event, max_len: int = 100_000) -> str:
        """Publish an event to its typed stream. Returns the stream entry ID."""
        key = self._stream_key(event.type)
        entry_id = await self.redis.xadd(
            key,
            event.to_stream_message(),
            maxlen=max_len,
            approximate=True,
        )
        logger.debug("event_bus.published", event_type=event.type.value, entry_id=entry_id)
        return entry_id

    # -- subscribe -----------------------------------------------------------

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Register an async handler for a given event type."""
        self._handlers.setdefault(event_type, []).append(handler)
        logger.info("event_bus.subscribed", event_type=event_type.value, handler=handler.__name__)

    # -- consumer group setup ------------------------------------------------

    async def _ensure_group(self, stream_key: str) -> None:
        try:
            await self.redis.xgroup_create(stream_key, CONSUMER_GROUP, id="0", mkstream=True)
        except Exception:
            pass  # BUSYGROUP means it already exists

    # -- listen loop ---------------------------------------------------------

    async def listen(
        self,
        consumer_name: str = "worker-1",
        count: int = 10,
        block_ms: int = 5000,
    ) -> None:
        """Block and process events from all subscribed streams.

        Call with ``asyncio.create_task`` or ``await`` in your main loop.
        """
        if not self._handlers:
            logger.warning("event_bus.no_handlers")
            return

        streams = {self._stream_key(et): ">" for et in self._handlers}
        for key in streams:
            await self._ensure_group(key)

        self._running = True
        logger.info("event_bus.listening", streams=list(streams.keys()))

        while self._running:
            try:
                results = await self.redis.xreadgroup(
                    groupname=CONSUMER_GROUP,
                    consumername=consumer_name,
                    streams=streams,
                    count=count,
                    block=block_ms,
                )
                if not results:
                    continue

                for stream_key, messages in results:
                    event_type_str = stream_key.decode().rsplit(":", 1)[-1]
                    try:
                        event_type = EventType(event_type_str)
                    except ValueError:
                        logger.warning("event_bus.unknown_type", raw=event_type_str)
                        continue

                    for entry_id, fields in messages:
                        event = Event.from_stream_message(fields)
                        for handler in self._handlers.get(event_type, []):
                            try:
                                await handler(event)
                            except Exception:
                                logger.exception(
                                    "event_bus.handler_error",
                                    event_type=event_type.value,
                                    handler=handler.__name__,
                                )
                        await self.redis.xack(stream_key, CONSUMER_GROUP, entry_id)

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("event_bus.listen_error")
                await asyncio.sleep(1)

        self._running = False

    def stop(self) -> None:
        """Signal the listen loop to exit."""
        self._running = False
