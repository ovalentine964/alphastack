"""Unit tests for broker connectors (MT5 and CCXT — both mocked)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alphastack.brokers.base import BrokerConnector, ConnectionState
from alphastack.brokers.models import (
    BrokerBalance,
    BrokerBar,
    BrokerOrder,
    BrokerPosition,
    BrokerTick,
    OrderSide,
    OrderStatus,
    OrderType,
    PositionSide,
    TimeInForce,
)
from alphastack.brokers.order_manager import OrderManager


# ===========================================================================
# Mock Broker Connector (from conftest)
# ===========================================================================

class TestMockBroker:
    @pytest.mark.asyncio
    async def test_connect_disconnect(self, mock_broker):
        assert mock_broker.is_connected is False
        await mock_broker.connect()
        assert mock_broker.is_connected is True
        assert mock_broker.state == ConnectionState.CONNECTED
        await mock_broker.disconnect()
        assert mock_broker.is_connected is False

    @pytest.mark.asyncio
    async def test_place_order(self, mock_broker):
        await mock_broker.connect()
        order = BrokerOrder(
            symbol="EUR/USD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=0.1,
            price=1.1050,
        )
        result = await mock_broker.place_order(order)
        assert result.status == OrderStatus.FILLED
        assert result.filled_quantity == 0.1
        assert result.broker_order_id.startswith("MOCK-")

    @pytest.mark.asyncio
    async def test_cancel_order(self, mock_broker):
        await mock_broker.connect()
        order = BrokerOrder(symbol="EUR/USD", side=OrderSide.BUY, quantity=0.1)
        placed = await mock_broker.place_order(order)
        cancelled = await mock_broker.cancel_order(placed.id)
        assert cancelled.status == OrderStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_modify_order(self, mock_broker):
        await mock_broker.connect()
        order = BrokerOrder(symbol="EUR/USD", side=OrderSide.BUY, quantity=0.1, price=1.1050)
        placed = await mock_broker.place_order(order)
        modified = await mock_broker.modify_order(placed.id, stop_loss=1.1000)
        assert modified.stop_loss == 1.1000

    @pytest.mark.asyncio
    async def test_get_balance(self, mock_broker):
        await mock_broker.connect()
        balance = await mock_broker.get_balance()
        assert balance.equity == 10_000.0

    @pytest.mark.asyncio
    async def test_get_tick(self, mock_broker):
        await mock_broker.connect()
        tick = await mock_broker.get_tick("EUR/USD")
        assert tick.symbol == "EUR/USD"
        assert tick.bid > 0
        assert tick.ask > tick.bid

    @pytest.mark.asyncio
    async def test_get_bars(self, mock_broker):
        await mock_broker.connect()
        bars = await mock_broker.get_bars("EUR/USD", "1h", 50)
        assert len(bars) == 50
        assert all(b.open > 0 for b in bars)


# ===========================================================================
# BrokerOrder model
# ===========================================================================

class TestBrokerOrder:
    def test_is_active_states(self):
        for status in [OrderStatus.PENDING, OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]:
            order = BrokerOrder(status=status)
            assert order.is_active is True

    def test_inactive_states(self):
        for status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED]:
            order = BrokerOrder(status=status)
            assert order.is_active is False

    def test_remaining_quantity(self):
        order = BrokerOrder(quantity=1.0, filled_quantity=0.3)
        assert order.remaining_quantity == pytest.approx(0.7)

    def test_remaining_quantity_fully_filled(self):
        order = BrokerOrder(quantity=1.0, filled_quantity=1.0)
        assert order.remaining_quantity == 0.0


# ===========================================================================
# BrokerPosition model
# ===========================================================================

class TestBrokerPosition:
    def test_notional_value(self):
        pos = BrokerPosition(quantity=10.0, current_price=1.1)
        assert pos.notional_value == pytest.approx(11.0)

    def test_pnl_long(self):
        pos = BrokerPosition(
            side=PositionSide.LONG, quantity=1.0,
            avg_entry_price=1.1000, current_price=1.1050,
        )
        assert pos.pnl_pct > 0

    def test_pnl_short(self):
        pos = BrokerPosition(
            side=PositionSide.SHORT, quantity=1.0,
            avg_entry_price=1.1000, current_price=1.0950,
        )
        assert pos.pnl_pct > 0

    def test_pnl_flat(self):
        pos = BrokerPosition(side=PositionSide.FLAT, avg_entry_price=1.0)
        assert pos.pnl_pct == 0.0


# ===========================================================================
# BrokerTick model
# ===========================================================================

class TestBrokerTick:
    def test_mid_price(self):
        tick = BrokerTick(bid=1.1000, ask=1.1002)
        assert tick.mid == pytest.approx(1.1001)

    def test_mid_no_bid_ask(self):
        tick = BrokerTick(last=1.1000)
        assert tick.mid == 1.1000


# ===========================================================================
# Order Manager
# ===========================================================================

class TestOrderManager:
    def test_register_and_get(self):
        om = OrderManager()
        order = BrokerOrder(id="test-1", symbol="EUR/USD", side=OrderSide.BUY, quantity=0.1)
        om.register(order)
        assert om.get("test-1") is not None
        assert om.count == 1

    def test_get_by_broker_id(self):
        om = OrderManager()
        order = BrokerOrder(id="test-1", broker_order_id="BROKER-123", symbol="EUR/USD")
        om.register(order)
        found = om.get_by_broker_id("BROKER-123")
        assert found is not None
        assert found.id == "test-1"

    def test_update_status(self):
        om = OrderManager()
        order = BrokerOrder(id="test-1", symbol="EUR/USD", quantity=1.0)
        om.register(order)
        om.update_status("test-1", OrderStatus.FILLED, filled_quantity=1.0, avg_fill_price=1.1)
        assert om.get("test-1").status == OrderStatus.FILLED
        assert om.get("test-1").filled_quantity == 1.0

    def test_partial_fill(self):
        om = OrderManager()
        order = BrokerOrder(id="test-1", symbol="EUR/USD", quantity=1.0)
        om.register(order)
        om.record_partial_fill("test-1", 0.5, 1.1000)
        assert om.get("test-1").status == OrderStatus.PARTIALLY_FILLED
        assert om.get("test-1").filled_quantity == pytest.approx(0.5)

    def test_partial_fill_completes(self):
        om = OrderManager()
        order = BrokerOrder(id="test-1", symbol="EUR/USD", quantity=1.0)
        om.register(order)
        om.record_partial_fill("test-1", 0.5, 1.1000)
        om.record_partial_fill("test-1", 0.5, 1.1010)
        assert om.get("test-1").status == OrderStatus.FILLED
        assert om.get("test-1").filled_quantity == pytest.approx(1.0)

    def test_remove_order(self):
        om = OrderManager()
        order = BrokerOrder(id="test-1", symbol="EUR/USD")
        om.register(order)
        removed = om.remove("test-1")
        assert removed is not None
        assert om.get("test-1") is None

    def test_active_orders(self):
        om = OrderManager()
        om.register(BrokerOrder(id="a", status=OrderStatus.OPEN))
        om.register(BrokerOrder(id="b", status=OrderStatus.FILLED))
        om.register(BrokerOrder(id="c", status=OrderStatus.PENDING))
        assert len(om.active_orders) == 2

    def test_orders_for_symbol(self):
        om = OrderManager()
        om.register(BrokerOrder(id="a", symbol="EUR/USD"))
        om.register(BrokerOrder(id="b", symbol="GBP/USD"))
        assert len(om.orders_for_symbol("EUR/USD")) == 1

    def test_snapshot_restore(self):
        om = OrderManager()
        om.register(BrokerOrder(id="a", symbol="EUR/USD", quantity=0.1))
        snapshot = om.snapshot()
        om2 = OrderManager()
        restored = om2.restore(snapshot)
        assert restored == 1
        assert om2.get("a").symbol == "EUR/USD"


# ===========================================================================
# MT5 Connector (mocked)
# ===========================================================================

class TestMT5Connector:
    """Test MT5 connector with mocked MetaTrader5 module."""

    @pytest.fixture
    def mt5_module(self):
        """Mock MetaTrader5 Python module."""
        mock = MagicMock()
        mock.initialize.return_value = True
        mock.login.return_value = True
        mock.terminal_info.return_value = {"connected": True}
        mock.account_info.return_value = MagicMock(
            balance=10000.0, equity=10000.0, margin=0.0,
            free_margin=10000.0, currency="USD", margin_level=0.0,
        )
        mock.symbol_info_tick.return_value = MagicMock(
            bid=1.1000, ask=1.1002, last=1.1001, volume=100.0,
            time=1700000000,
        )
        mock.copy_rates_from_pos.return_value = [
            {"time": 1700000000, "open": 1.1, "high": 1.105, "low": 1.095,
             "close": 1.102, "tick_volume": 1000, "spread": 2}
        ]
        mock.order_send.return_value = MagicMock(
            retcode=10009, order=12345, price=1.1000, volume=0.1,
        )
        return mock

    def test_mt5_order_type_mapping(self):
        """Verify order type constants map correctly."""
        from alphastack.brokers.mt5_connector import _ORDER_TYPE_MAP, _ORDER_TYPE_MAP_SELL
        assert _ORDER_TYPE_MAP[OrderType.MARKET] == 0
        assert _ORDER_TYPE_MAP_SELL[OrderType.MARKET] == 1

    def test_mt5_status_mapping(self):
        """Verify MT5 status codes map to our OrderStatus."""
        from alphastack.brokers.mt5_connector import _MT5_STATUS_MAP
        assert _MT5_STATUS_MAP[2] == OrderStatus.FILLED
        assert _MT5_STATUS_MAP[3] == OrderStatus.CANCELLED


# ===========================================================================
# CCXT Connector (mocked)
# ===========================================================================

class TestCCXTConnector:
    """Test CCXT connector with mocked ccxt exchange."""

    def test_ccxt_status_mapping(self):
        """Verify CCXT status strings map correctly."""
        from alphastack.brokers.ccxt_connector import _CCXT_STATUS_MAP
        assert _CCXT_STATUS_MAP["open"] == OrderStatus.OPEN
        assert _CCXT_STATUS_MAP["closed"] == OrderStatus.FILLED
        assert _CCXT_STATUS_MAP["canceled"] == OrderStatus.CANCELLED

    def test_rate_limiter(self):
        """Verify rate limiter exists and is importable."""
        from alphastack.brokers.ccxt_connector import _RateLimiter
        rl = _RateLimiter(requests_per_second=10.0)
        assert rl._interval == pytest.approx(0.1)
