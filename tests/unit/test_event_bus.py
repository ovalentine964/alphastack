"""Unit tests for the Event Bus system."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from alphastack.core.events import (
    AgentEvent,
    DataEvent,
    Event,
    EventType,
    RiskEvent,
    SignalEvent,
    TradeEvent,
)


# ===========================================================================
# Event Model Tests
# ===========================================================================

class TestEventModels:
    def test_event_has_unique_id(self):
        e1 = Event(type=EventType.SIGNAL)
        e2 = Event(type=EventType.SIGNAL)
        assert e1.id != e2.id

    def test_signal_event_defaults(self):
        evt = SignalEvent(symbol="EUR/USD", side="long", strength=0.85)
        assert evt.type == EventType.SIGNAL
        assert evt.symbol == "EUR/USD"
        assert evt.side == "long"

    def test_trade_event_defaults(self):
        evt = TradeEvent(order_id="ORD-001", symbol="BTC/USD", side="buy", quantity=0.1, price=50000)
        assert evt.type == EventType.TRADE
        assert evt.order_id == "ORD-001"

    def test_risk_event_defaults(self):
        evt = RiskEvent(level="critical", rule="max_drawdown", message="Breached")
        assert evt.type == EventType.RISK
        assert evt.level == "critical"

    def test_data_event_defaults(self):
        evt = DataEvent(symbol="EUR/USD", data_type="ohlcv")
        assert evt.type == EventType.DATA

    def test_agent_event_defaults(self):
        evt = AgentEvent(agent_id="analyst-1", action="analyze", confidence=0.9)
        assert evt.type == EventType.AGENT

    def test_to_stream_message_roundtrip(self):
        original = SignalEvent(symbol="EUR/USD", side="long", strength=0.85, source="test")
        msg = original.to_stream_message()
        assert "data" in msg
        restored = Event.from_stream_message({b"data": msg["data"].encode()})
        assert restored.type == EventType.SIGNAL
        assert restored.id == original.id

    def test_timestamp_auto_set(self):
        evt = Event(type=EventType.DATA)
        assert evt.timestamp is not None

    def test_payload_and_metadata(self):
        evt = Event(
            type=EventType.SIGNAL,
            payload={"key": "value"},
            metadata={"source": "test"},
        )
        assert evt.payload["key"] == "value"
        assert evt.metadata["source"] == "test"


# ===========================================================================
# In-Memory Event Bus Tests
# ===========================================================================

class TestInMemoryEventBus:
    """Test the InMemoryEventBus from conftest (used in integration tests)."""

    @pytest.mark.asyncio
    async def test_publish_and_subscribe(self, event_bus):
        received: list[Event] = []

        async def handler(evt: Event):
            received.append(evt)

        event_bus.subscribe(EventType.SIGNAL, handler)
        evt = SignalEvent(symbol="EUR/USD", side="long", strength=0.8)
        await event_bus.publish(evt)
        assert len(received) == 1
        assert received[0].symbol == "EUR/USD"

    @pytest.mark.asyncio
    async def test_multiple_handlers(self, event_bus):
        count = {"a": 0, "b": 0}

        async def handler_a(evt):
            count["a"] += 1

        async def handler_b(evt):
            count["b"] += 1

        event_bus.subscribe(EventType.SIGNAL, handler_a)
        event_bus.subscribe(EventType.SIGNAL, handler_b)
        await event_bus.publish(SignalEvent(symbol="X", side="long"))
        assert count["a"] == 1
        assert count["b"] == 1

    @pytest.mark.asyncio
    async def test_handler_only_for_subscribed_type(self, event_bus):
        signals: list[Event] = []
        trades: list[Event] = []

        async def sig_handler(evt):
            signals.append(evt)

        async def trade_handler(evt):
            trades.append(evt)

        event_bus.subscribe(EventType.SIGNAL, sig_handler)
        event_bus.subscribe(EventType.TRADE, trade_handler)

        await event_bus.publish(SignalEvent(symbol="X", side="long"))
        await event_bus.publish(TradeEvent(order_id="1", symbol="X", side="buy", quantity=0.1, price=1.0))

        assert len(signals) == 1
        assert len(trades) == 1

    @pytest.mark.asyncio
    async def test_published_events_tracked(self, event_bus):
        await event_bus.publish(SignalEvent(symbol="A", side="long"))
        await event_bus.publish(SignalEvent(symbol="B", side="short"))
        assert len(event_bus.published_events) == 2

    @pytest.mark.asyncio
    async def test_clear(self, event_bus):
        await event_bus.publish(SignalEvent(symbol="A", side="long"))
        event_bus.clear()
        assert len(event_bus.published_events) == 0

    @pytest.mark.asyncio
    async def test_publish_returns_event_id(self, event_bus):
        evt = SignalEvent(symbol="X", side="long")
        result_id = await event_bus.publish(evt)
        assert result_id == evt.id


# ===========================================================================
# Event Ordering
# ===========================================================================

class TestEventOrdering:
    @pytest.mark.asyncio
    async def test_events_received_in_order(self, event_bus):
        received_ids: list[str] = []

        async def handler(evt):
            received_ids.append(evt.id)

        event_bus.subscribe(EventType.SIGNAL, handler)

        events = [SignalEvent(symbol=f"SYM-{i}", side="long") for i in range(10)]
        for e in events:
            await event_bus.publish(e)

        assert received_ids == [e.id for e in events]

    @pytest.mark.asyncio
    async def test_different_types_interleaved(self, event_bus):
        received: list[str] = []

        async def handler(evt):
            received.append(evt.type.value)

        event_bus.subscribe(EventType.SIGNAL, handler)
        event_bus.subscribe(EventType.TRADE, handler)
        event_bus.subscribe(EventType.RISK, handler)

        await event_bus.publish(SignalEvent(symbol="X", side="long"))
        await event_bus.publish(TradeEvent(order_id="1", symbol="X", side="buy", quantity=0.1, price=1.0))
        await event_bus.publish(RiskEvent(level="warning", rule="test", message="test"))

        assert received == ["signal", "trade", "risk"]


# ===========================================================================
# Event Serialization
# ===========================================================================

class TestEventSerialization:
    def test_roundtrip_all_types(self):
        events = [
            SignalEvent(symbol="EUR/USD", side="long", strength=0.8),
            TradeEvent(order_id="1", symbol="BTC/USD", side="buy", quantity=0.1, price=50000),
            RiskEvent(level="critical", rule="dd", message="breach"),
            DataEvent(symbol="EUR/USD", data_type="tick"),
            AgentEvent(agent_id="a1", action="decide", confidence=0.9),
        ]
        for original in events:
            msg = original.to_stream_message()
            restored = Event.from_stream_message({b"data": msg["data"].encode()})
            assert restored.id == original.id
            assert restored.type == original.type

    def test_unknown_fields_preserved(self):
        evt = Event(type=EventType.SIGNAL, payload={"custom_field": 42})
        msg = evt.to_stream_message()
        restored = Event.from_stream_message({b"data": msg["data"].encode()})
        assert restored.payload["custom_field"] == 42
