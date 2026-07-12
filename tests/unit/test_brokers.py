"""Unit tests for broker connectors."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alphastack.brokers.models import (
    BrokerBalance,
    BrokerOrder,
    BrokerPosition,
    BrokerTick,
    OrderSide,
    OrderStatus,
    OrderType,
)
from tests.conftest import MockBrokerConnector


# ---------------------------------------------------------------------------
# MockBrokerConnector tests
# ---------------------------------------------------------------------------

class TestMockBrokerConnector:

    @pytest.mark.asyncio
    async def test_connect_disconnect(self) -> None:
        broker = MockBrokerConnector()
        assert broker.is_connected is False

        await broker.connect()
        assert broker.is_connected is True

        await broker.disconnect()
        assert broker.is_connected is False

    @pytest.mark.asyncio
    async def test_get_balance(self) -> None:
        broker = MockBrokerConnector()
        await broker.connect()
        balance = await broker.get_balance()
        assert isinstance(balance, BrokerBalance)
        assert balance.equity == 10_000.0
        assert balance.free == 10_000.0

    @pytest.mark.asyncio
    async def test_place_order(self) -> None:
        broker = MockBrokerConnector()
        await broker.connect()

        order = BrokerOrder(
            symbol="EUR/USD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=0.1,
            price=1.1050,
        )
        result = await broker.place_order(order)

        assert result.status == OrderStatus.FILLED
        assert result.filled_quantity == 0.1
        assert result.broker_order_id.startswith("MOCK-")

    @pytest.mark.asyncio
    async def test_cancel_order(self) -> None:
        broker = MockBrokerConnector()
        await broker.connect()

        order = BrokerOrder(
            symbol="EUR/USD",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=0.1,
            price=1.1000,
        )
        placed = await broker.place_order(order)
        cancelled = await broker.cancel_order(placed.id)
        assert cancelled is True
        assert broker._orders[placed.id].status == OrderStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_order(self) -> None:
        broker = MockBrokerConnector()
        await broker.connect()
        result = await broker.cancel_order("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_tick(self) -> None:
        broker = MockBrokerConnector()
        await broker.connect()

        tick = await broker.get_tick("EUR/USD")
        assert isinstance(tick, BrokerTick)
        assert tick.symbol == "EUR/USD"
        assert tick.bid > 0
        assert tick.ask > tick.bid

    @pytest.mark.asyncio
    async def test_modify_order(self) -> None:
        broker = MockBrokerConnector()
        await broker.connect()

        order = BrokerOrder(
            symbol="EUR/USD",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=0.1,
            price=1.1000,
        )
        placed = await broker.place_order(order)
        modified = await broker.modify_order(placed.id, quantity=0.2)
        assert modified is not None
        assert modified.quantity == 0.2


# ---------------------------------------------------------------------------
# BrokerOrder model tests
# ---------------------------------------------------------------------------

class TestBrokerModels:

    def test_order_defaults(self) -> None:
        order = BrokerOrder()
        assert order.status == OrderStatus.PENDING
        assert order.side == OrderSide.BUY
        assert order.order_type == OrderType.MARKET
        assert order.quantity == 0.0

    def test_order_serialization(self) -> None:
        order = BrokerOrder(
            symbol="EUR/USD",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=0.5,
            price=1.1200,
        )
        data = order.model_dump()
        assert data["symbol"] == "EUR/USD"
        assert data["side"] == "sell"
        assert data["quantity"] == 0.5

    def test_tick_creation(self) -> None:
        tick = BrokerTick(
            symbol="GBP/USD",
            bid=1.3000,
            ask=1.3002,
            timestamp=datetime.now(timezone.utc),
        )
        assert tick.symbol == "GBP/USD"
        assert tick.ask > tick.bid
