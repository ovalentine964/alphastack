"""Integration test — full trade lifecycle from signal to execution.

Tests the complete flow:
Signal → Pipeline → Risk Governor → Order → Broker → Fill → Event
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from alphastack.brokers.models import (
    BrokerOrder,
    OrderSide,
    OrderStatus,
    OrderType,
)
from alphastack.core.events import (
    Event,
    EventType,
    SignalEvent,
    TradeEvent,
)
from alphastack.risk.exposure import ExposureManager, PositionExposure
from alphastack.risk.governor import RiskGovernor, TradeApproval, TradeRequest
from alphastack.risk.validators import TradeValidator
from tests.conftest import InMemoryEventBus, MockBrokerConnector


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _signal_to_execution(
    bus: InMemoryEventBus,
    broker: MockBrokerConnector,
    validator: TradeValidator,
    exposure: ExposureManager,
    signal: SignalEvent,
) -> tuple[TradeApproval, BrokerOrder | None]:
    """Simulate the full lifecycle: signal → risk check → order → fill."""
    # 1. Publish signal event
    await bus.publish(signal)

    # 2. Validate trade
    validation = validator.validate_pre_trade(
        symbol=signal.symbol,
        direction=signal.side,
        entry_price=1.1050,
        stop_loss=1.1000 if signal.side == "long" else 1.1100,
        size=0.1,
    )
    if not validation.valid:
        return TradeApproval(
            approved=False,
            rejection_reason="; ".join(validation.errors),
        ), None

    # 3. Check exposure
    ok, reason = exposure.check_add_position(
        symbol=signal.symbol,
        direction=signal.side,
        size=0.1,
        price=1.1050,
        balance=10_000.0,
        session="london",
    )
    if not ok:
        return TradeApproval(approved=False, rejection_reason=reason), None

    # 4. Place order
    order = BrokerOrder(
        symbol=signal.symbol,
        side=OrderSide.BUY if signal.side == "long" else OrderSide.SELL,
        order_type=OrderType.MARKET,
        quantity=0.1,
        price=1.1050,
    )
    filled = await broker.place_order(order)

    # 5. Track position
    exposure.add_position(PositionExposure(
        symbol=signal.symbol,
        direction=signal.side,
        size=0.1,
        entry_price=filled.avg_fill_price,
        session="london",
    ))

    # 6. Publish trade event
    trade_event = TradeEvent(
        order_id=filled.id,
        symbol=signal.symbol,
        side="buy" if signal.side == "long" else "sell",
        quantity=0.1,
        price=filled.avg_fill_price,
        status="filled",
        source="integration_test",
    )
    await bus.publish(trade_event)

    return TradeApproval(approved=True, adjusted_size=0.1), filled


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestTradeLifecycle:
    """End-to-end trade lifecycle integration tests."""

    @pytest.mark.asyncio
    async def test_full_lifecycle_long(self) -> None:
        """Signal → validation → risk → order → fill → event."""
        bus = InMemoryEventBus()
        broker = MockBrokerConnector()
        validator = TradeValidator()
        exposure = ExposureManager(max_open_positions=5)

        await broker.connect()

        signal = SignalEvent(
            symbol="EUR/USD",
            side="long",
            strength=0.85,
            timeframe="1h",
            strategy="alphastack_v1",
            source="test",
        )

        approval, order = await _signal_to_execution(
            bus, broker, validator, exposure, signal,
        )

        assert approval.approved is True
        assert order is not None
        assert order.status == OrderStatus.FILLED
        assert order.filled_quantity == 0.1

        # Verify events were published
        assert len(bus.published_events) == 2
        assert bus.published_events[0].type == EventType.SIGNAL
        assert bus.published_events[1].type == EventType.TRADE

        # Verify position tracked
        assert len(exposure._positions) == 1
        assert exposure._positions[0].symbol == "EUR/USD"

    @pytest.mark.asyncio
    async def test_full_lifecycle_short(self) -> None:
        """Short trade lifecycle."""
        bus = InMemoryEventBus()
        broker = MockBrokerConnector()
        validator = TradeValidator()
        exposure = ExposureManager(max_open_positions=5)

        await broker.connect()

        signal = SignalEvent(
            symbol="GBP/USD",
            side="short",
            strength=-0.7,
            timeframe="4h",
            strategy="alphastack_v1",
            source="test",
        )

        approval, order = await _signal_to_execution(
            bus, broker, validator, exposure, signal,
        )

        assert approval.approved is True
        assert order is not None
        assert order.side == OrderSide.SELL

    @pytest.mark.asyncio
    async def test_rejected_by_exposure(self) -> None:
        """Trade rejected when exposure limit is hit."""
        bus = InMemoryEventBus()
        broker = MockBrokerConnector()
        validator = TradeValidator()
        exposure = ExposureManager(max_open_positions=0)  # no positions allowed

        await broker.connect()

        signal = SignalEvent(
            symbol="EUR/USD", side="long", strength=0.8,
            timeframe="1h", strategy="test", source="test",
        )

        approval, order = await _signal_to_execution(
            bus, broker, validator, exposure, signal,
        )

        assert approval.approved is False
        assert "Max open positions" in approval.rejection_reason
        assert order is None

    @pytest.mark.asyncio
    async def test_rejected_by_validation(self) -> None:
        """Trade rejected by validator (bad parameters)."""
        bus = InMemoryEventBus()
        broker = MockBrokerConnector()
        validator = TradeValidator()
        exposure = ExposureManager()

        await broker.connect()

        # Manually call with invalid params
        result = validator.validate_pre_trade(
            symbol="EUR/USD",
            direction="long",
            entry_price=0.0,  # invalid
            stop_loss=1.1000,
            size=0.1,
        )
        assert result.valid is False

    @pytest.mark.asyncio
    async def test_multiple_trades_sequence(self) -> None:
        """Multiple trades should accumulate positions."""
        bus = InMemoryEventBus()
        broker = MockBrokerConnector()
        validator = TradeValidator()
        exposure = ExposureManager(max_open_positions=10)

        await broker.connect()

        symbols = ["EUR/USD", "GBP/USD", "USD/JPY"]
        for sym in symbols:
            signal = SignalEvent(
                symbol=sym, side="long", strength=0.7,
                timeframe="1h", strategy="test", source="test",
            )
            approval, _ = await _signal_to_execution(
                bus, broker, validator, exposure, signal,
            )
            assert approval.approved is True

        assert len(exposure._positions) == 3
        assert len(bus.published_events) == 6  # 3 signals + 3 trades

    @pytest.mark.asyncio
    async def test_broker_tracks_orders(self) -> None:
        """Mock broker should retain order history."""
        broker = MockBrokerConnector()
        await broker.connect()

        order1 = BrokerOrder(
            symbol="EUR/USD", side=OrderSide.BUY,
            order_type=OrderType.MARKET, quantity=0.1, price=1.1050,
        )
        order2 = BrokerOrder(
            symbol="GBP/USD", side=OrderSide.SELL,
            order_type=OrderType.LIMIT, quantity=0.2, price=1.3000,
        )

        r1 = await broker.place_order(order1)
        r2 = await broker.place_order(order2)

        assert len(broker._orders) == 2
        assert r1.broker_order_id.startswith("MOCK-")
        assert r2.broker_order_id.startswith("MOCK-")
