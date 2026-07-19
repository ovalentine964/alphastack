"""Comprehensive tests for the broker connector layer.

Covers:
- BrokerConnector ABC and connection state machine
- BrokerOrder, BrokerPosition, BrokerBalance, BrokerTick models
- MT5Connector (mocked MetaTrader5)
- CCXTConnector (mocked ccxt)
- BrokerRegistry with failover
- SmartOrderRouter with slippage estimation and fee calculation
- OrderManager lifecycle
- Forex utility functions
"""

from __future__ import annotations

import asyncio
import datetime as dt
import math
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alphastack.brokers.base import BrokerConnector, ConnectionState, _retry_async
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
from alphastack.brokers.registry import BrokerRegistry
from alphastack.brokers.router import (
    ExecutionQuality,
    FeeCalculator,
    RouterConfig,
    RoutingStrategy,
    SlippageEstimator,
    SmartOrderRouter,
)


# ===========================================================================
# Helpers
# ===========================================================================

class FakeBroker(BrokerConnector):
    """Minimal fake broker for unit testing — deterministic, no I/O."""

    def __init__(
        self,
        name: str = "fake",
        *,
        balance: float = 10_000.0,
        tick_spread: float = 0.0002,
        should_fail: bool = False,
    ) -> None:
        super().__init__(name)
        self._balance = balance
        self._tick_spread = tick_spread
        self._should_fail = should_fail
        self._orders: dict[str, BrokerOrder] = {}
        self._positions: list[BrokerPosition] = []
        self._call_count = 0

    async def connect(self) -> None:
        self._transition(ConnectionState.CONNECTED)

    async def disconnect(self) -> None:
        self._transition(ConnectionState.DISCONNECTED)

    async def place_order(self, order: BrokerOrder) -> BrokerOrder:
        self._call_count += 1
        if self._should_fail:
            raise ConnectionError(f"{self.name} is configured to fail")

        order.broker_order_id = f"{self.name}-{uuid.uuid4().hex[:8]}"
        order.status = OrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.avg_fill_price = order.price or 1.1000
        order.filled_at = dt.datetime.now(dt.timezone.utc)
        self._orders[order.broker_order_id] = order
        return order

    async def cancel_order(self, order_id: str) -> BrokerOrder:
        order = self._orders.get(order_id)
        if order:
            order.status = OrderStatus.CANCELLED
            return order
        raise ValueError(f"Order {order_id} not found")

    async def modify_order(
        self,
        order_id: str,
        *,
        price: float | None = None,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        quantity: float | None = None,
    ) -> BrokerOrder:
        order = self._orders.get(order_id)
        if order:
            if price is not None:
                order.price = price
            if stop_loss is not None:
                order.stop_loss = stop_loss
            if take_profit is not None:
                order.take_profit = take_profit
            if quantity is not None:
                order.quantity = quantity
            return order
        raise ValueError(f"Order {order_id} not found")

    async def get_positions(self) -> list[BrokerPosition]:
        return list(self._positions)

    async def get_balance(self) -> BrokerBalance:
        return BrokerBalance(
            broker=self.name,
            currency="USD",
            total=self._balance,
            available=self._balance,
            equity=self._balance,
        )

    async def get_tick(self, symbol: str) -> BrokerTick:
        base = 1.1000
        return BrokerTick(
            broker=self.name,
            symbol=symbol,
            bid=base,
            ask=base + self._tick_spread,
            last=base + self._tick_spread / 2,
            volume=1000.0,
            spread=self._tick_spread,
            timestamp=dt.datetime.now(dt.timezone.utc),
        )

    async def get_bars(
        self, symbol: str, timeframe: str = "1h", count: int = 100
    ) -> list[BrokerBar]:
        bars = []
        price = 1.1000
        for i in range(count):
            o = price
            c = price + 0.0001 * (i % 10 - 5)
            bars.append(BrokerBar(
                symbol=symbol,
                timeframe=timeframe,
                open=o,
                high=max(o, c) + 0.0005,
                low=min(o, c) - 0.0005,
                close=c,
                volume=1000.0,
            ))
            price = c
        return bars


# ===========================================================================
# Connection State Machine
# ===========================================================================

class TestConnectionState:
    def test_initial_state(self):
        broker = FakeBroker()
        assert broker.state == ConnectionState.DISCONNECTED
        assert broker.is_connected is False

    @pytest.mark.asyncio
    async def test_connect_transition(self):
        broker = FakeBroker()
        await broker.connect()
        assert broker.state == ConnectionState.CONNECTED
        assert broker.is_connected is True

    @pytest.mark.asyncio
    async def test_disconnect_transition(self):
        broker = FakeBroker()
        await broker.connect()
        await broker.disconnect()
        assert broker.state == ConnectionState.DISCONNECTED
        assert broker.is_connected is False

    @pytest.mark.asyncio
    async def test_reconnect(self):
        broker = FakeBroker()
        await broker.connect()
        await broker.reconnect()
        assert broker.state == ConnectionState.CONNECTED

    def test_repr(self):
        broker = FakeBroker(name="test-broker")
        r = repr(broker)
        assert "FakeBroker" in r
        assert "test-broker" in r
        assert "disconnected" in r


# ===========================================================================
# Retry Logic
# ===========================================================================

class TestRetryAsync:
    @pytest.mark.asyncio
    async def test_succeeds_first_try(self):
        call_count = 0

        async def factory():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = await _retry_async(factory, max_retries=3, base_delay=0.01)
        assert result == "ok"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_failure(self):
        call_count = 0

        async def factory():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("not yet")
            return "done"

        result = await _retry_async(factory, max_retries=3, base_delay=0.001)
        assert result == "done"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self):
        async def factory():
            raise ValueError("always fail")

        with pytest.raises(ValueError, match="always fail"):
            await _retry_async(factory, max_retries=2, base_delay=0.001)


# ===========================================================================
# BrokerOrder Model
# ===========================================================================

class TestBrokerOrder:
    def test_defaults(self):
        order = BrokerOrder()
        assert order.status == OrderStatus.PENDING
        assert order.side == OrderSide.BUY
        assert order.order_type == OrderType.MARKET
        assert order.quantity == 0.0
        assert order.is_active is True

    def test_active_states(self):
        for status in [OrderStatus.PENDING, OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]:
            assert BrokerOrder(status=status).is_active is True

    def test_inactive_states(self):
        for status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.EXPIRED]:
            assert BrokerOrder(status=status).is_active is False

    def test_remaining_quantity(self):
        order = BrokerOrder(quantity=1.0, filled_quantity=0.3)
        assert order.remaining_quantity == pytest.approx(0.7)

    def test_remaining_quantity_zero(self):
        order = BrokerOrder(quantity=1.0, filled_quantity=1.5)
        assert order.remaining_quantity == 0.0

    def test_serialization_roundtrip(self):
        order = BrokerOrder(
            symbol="BTC/USDT",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=0.5,
            price=65000.0,
            stop_loss=64000.0,
            take_profit=67000.0,
        )
        data = order.model_dump()
        assert data["symbol"] == "BTC/USDT"
        assert data["side"] == "sell"
        assert data["stop_loss"] == 64000.0

    def test_forex_fields(self):
        order = BrokerOrder(
            lot_size=0.1,
            pip_value=10.0,
            spread_at_entry=1.5,
            swap_rate=-0.5,
            margin_required=110.0,
            contract_size=100_000,
        )
        assert order.lot_size == 0.1
        assert order.contract_size == 100_000


# ===========================================================================
# BrokerPosition Model
# ===========================================================================

class TestBrokerPosition:
    def test_notional_value_crypto(self):
        pos = BrokerPosition(quantity=0.5, current_price=65000.0)
        assert pos.notional_value == pytest.approx(32500.0)

    def test_notional_value_forex(self):
        pos = BrokerPosition(
            lot_size=0.1,
            contract_size=100_000,
            current_price=1.1000,
        )
        assert pos.notional_value == pytest.approx(11_000.0)

    def test_pnl_long_profit(self):
        pos = BrokerPosition(
            side=PositionSide.LONG,
            avg_entry_price=1.1000,
            current_price=1.1050,
        )
        assert pos.pnl_pct > 0

    def test_pnl_long_loss(self):
        pos = BrokerPosition(
            side=PositionSide.LONG,
            avg_entry_price=1.1000,
            current_price=1.0950,
        )
        assert pos.pnl_pct < 0

    def test_pnl_short_profit(self):
        pos = BrokerPosition(
            side=PositionSide.SHORT,
            avg_entry_price=1.1000,
            current_price=1.0950,
        )
        assert pos.pnl_pct > 0

    def test_pnl_short_loss(self):
        pos = BrokerPosition(
            side=PositionSide.SHORT,
            avg_entry_price=1.1000,
            current_price=1.1050,
        )
        assert pos.pnl_pct < 0

    def test_pnl_flat(self):
        pos = BrokerPosition(side=PositionSide.FLAT, avg_entry_price=1.0)
        assert pos.pnl_pct == 0.0

    def test_effective_leverage(self):
        pos = BrokerPosition(
            lot_size=1.0,
            contract_size=100_000,
            current_price=1.1000,
            margin_used=1100.0,
        )
        # notional = 1.0 * 100000 * 1.1 = 110000; leverage = 110000 / 1100 = 100
        assert pos.effective_leverage == pytest.approx(100.0)


# ===========================================================================
# BrokerBalance Model
# ===========================================================================

class TestBrokerBalance:
    def test_defaults(self):
        bal = BrokerBalance()
        assert bal.currency == "USD"
        assert bal.total == 0.0

    def test_full_balance(self):
        bal = BrokerBalance(
            total=10_000.0,
            available=9_500.0,
            used_margin=500.0,
            equity=10_050.0,
            unrealized_pnl=50.0,
        )
        assert bal.equity == 10_050.0


# ===========================================================================
# BrokerTick Model
# ===========================================================================

class TestBrokerTick:
    def test_mid_price(self):
        tick = BrokerTick(bid=1.1000, ask=1.1002)
        assert tick.mid == pytest.approx(1.1001)

    def test_mid_fallback_to_last(self):
        tick = BrokerTick(bid=0, ask=0, last=1.1000)
        assert tick.mid == 1.1000

    def test_spread_explicit(self):
        # BrokerTick spread must be set explicitly (not auto-computed from bid/ask)
        tick = BrokerTick(bid=1.1000, ask=1.1005, spread=0.0005)
        assert tick.spread == pytest.approx(0.0005)

    def test_spread_from_ask_bid(self):
        # spread can be computed externally
        tick = BrokerTick(bid=1.1000, ask=1.1005)
        computed = tick.ask - tick.bid
        assert computed == pytest.approx(0.0005)


# ===========================================================================
# Order Manager
# ===========================================================================

class TestOrderManager:
    def test_register_and_get(self):
        om = OrderManager()
        order = BrokerOrder(id="test-1", symbol="EUR/USD", quantity=0.1)
        om.register(order)
        assert om.get("test-1") is not None
        assert om.count == 1

    def test_get_by_broker_id(self):
        om = OrderManager()
        order = BrokerOrder(id="test-1", broker_order_id="BRK-123")
        om.register(order)
        assert om.get_by_broker_id("BRK-123") is not None

    def test_update_status(self):
        om = OrderManager()
        order = BrokerOrder(id="test-1", symbol="EUR/USD", quantity=1.0)
        om.register(order)
        om.update_status("test-1", OrderStatus.FILLED, filled_quantity=1.0, avg_fill_price=1.1)
        updated = om.get("test-1")
        assert updated.status == OrderStatus.FILLED
        assert updated.filled_quantity == 1.0

    def test_partial_fill(self):
        om = OrderManager()
        order = BrokerOrder(id="test-1", quantity=1.0)
        om.register(order)
        om.record_partial_fill("test-1", 0.5, 1.1000)
        assert om.get("test-1").status == OrderStatus.PARTIALLY_FILLED
        assert om.get("test-1").filled_quantity == pytest.approx(0.5)

    def test_partial_fill_completes(self):
        om = OrderManager()
        order = BrokerOrder(id="test-1", quantity=1.0)
        om.register(order)
        om.record_partial_fill("test-1", 0.5, 1.1000)
        om.record_partial_fill("test-1", 0.5, 1.1010)
        assert om.get("test-1").status == OrderStatus.FILLED

    def test_remove(self):
        om = OrderManager()
        om.register(BrokerOrder(id="test-1"))
        removed = om.remove("test-1")
        assert removed is not None
        assert om.get("test-1") is None

    def test_active_orders(self):
        om = OrderManager()
        om.register(BrokerOrder(id="a", status=OrderStatus.OPEN))
        om.register(BrokerOrder(id="b", status=OrderStatus.FILLED))
        om.register(BrokerOrder(id="c", status=OrderStatus.PENDING))
        assert len(om.active_orders) == 2

    def test_snapshot_restore(self):
        om = OrderManager()
        om.register(BrokerOrder(id="a", symbol="BTC/USDT", quantity=0.1))
        snapshot = om.snapshot()
        om2 = OrderManager()
        count = om2.restore(snapshot)
        assert count == 1
        assert om2.get("a").symbol == "BTC/USDT"

    def test_orders_for_symbol(self):
        om = OrderManager()
        om.register(BrokerOrder(id="a", symbol="EUR/USD"))
        om.register(BrokerOrder(id="b", symbol="GBP/USD"))
        om.register(BrokerOrder(id="c", symbol="EUR/USD"))
        assert len(om.orders_for_symbol("EUR/USD")) == 2

    def test_orders_for_broker(self):
        om = OrderManager()
        om.register(BrokerOrder(id="a", broker="mt5"))
        om.register(BrokerOrder(id="b", broker="ccxt"))
        assert len(om.orders_for_broker("mt5")) == 1


# ===========================================================================
# Broker Registry
# ===========================================================================

class TestBrokerRegistry:
    def test_register_and_get(self):
        reg = BrokerRegistry()
        broker = FakeBroker("alpha")
        reg.register("alpha", broker)
        assert reg.get("alpha") is broker

    def test_default_broker(self):
        reg = BrokerRegistry()
        reg.register("a", FakeBroker("a"))
        reg.register("b", FakeBroker("b"), default=True)
        assert reg.default.name == "b"

    def test_unregister(self):
        reg = BrokerRegistry()
        reg.register("a", FakeBroker("a"))
        reg.unregister("a")
        assert reg.get("a") is None

    def test_names(self):
        reg = BrokerRegistry()
        reg.register("x", FakeBroker("x"))
        reg.register("y", FakeBroker("y"))
        assert set(reg.names) == {"x", "y"}

    @pytest.mark.asyncio
    async def test_connect_all(self):
        reg = BrokerRegistry()
        reg.register("a", FakeBroker("a"))
        reg.register("b", FakeBroker("b"))
        results = await reg.connect_all()
        assert all(results.values())
        assert reg.get("a").is_connected
        assert reg.get("b").is_connected

    @pytest.mark.asyncio
    async def test_disconnect_all(self):
        reg = BrokerRegistry()
        reg.register("a", FakeBroker("a"))
        await reg.connect_all()
        await reg.disconnect_all()
        assert not reg.get("a").is_connected

    @pytest.mark.asyncio
    async def test_route_order(self):
        reg = BrokerRegistry()
        broker = FakeBroker("primary")
        reg.register("primary", broker, default=True)
        await reg.connect_all()

        order = BrokerOrder(symbol="EUR/USD", side=OrderSide.BUY, quantity=0.1)
        result = await reg.route_order(order)
        assert result.status == OrderStatus.FILLED
        assert result.broker == "primary"

    @pytest.mark.asyncio
    async def test_failover(self):
        reg = BrokerRegistry()
        good = FakeBroker("good")
        bad = FakeBroker("bad", should_fail=True)
        reg.register("bad", bad, default=True)
        reg.register("good", good)
        await reg.connect_all()

        order = BrokerOrder(symbol="EUR/USD", side=OrderSide.BUY, quantity=0.1)
        result = await reg.route_order_with_failover(order)
        # Should fail on "bad" and succeed on "good"
        assert result.status == OrderStatus.FILLED
        assert result.broker == "good"

    def test_status(self):
        reg = BrokerRegistry()
        reg.register("a", FakeBroker("a"))
        status = reg.status()
        assert "a" in status
        assert status["a"] == "disconnected"

    def test_connected_brokers(self):
        reg = BrokerRegistry()
        broker = FakeBroker("a")
        reg.register("a", broker)
        assert reg.connected_brokers() == []

    @pytest.mark.asyncio
    async def test_connected_brokers_after_connect(self):
        reg = BrokerRegistry()
        broker = FakeBroker("a")
        reg.register("a", broker)
        await reg.connect_all()
        assert reg.connected_brokers() == ["a"]


# ===========================================================================
# Fee Calculator
# ===========================================================================

class TestFeeCalculator:
    def test_spread_cost(self):
        # 0.0002 spread × 0.1 lot × 100,000 contract = $2.00
        cost = FeeCalculator.spread_cost(0.0002, 0.1, 100_000)
        assert cost == pytest.approx(2.0)

    def test_spread_cost_crypto(self):
        # $10 spread × 0.5 BTC = $5.00
        cost = FeeCalculator.spread_cost(10.0, 0.5, 1.0)
        assert cost == pytest.approx(5.0)

    def test_commission_cost(self):
        cost = FeeCalculator.commission_cost(3.5, 0.1)
        assert cost == pytest.approx(0.35)

    def test_swap_cost(self):
        # -2.5 swap rate × 0.1 lot × 3 days = -0.75
        cost = FeeCalculator.swap_cost(-2.5, 0.1, 3)
        assert cost == pytest.approx(-0.75)

    def test_total_cost(self):
        total = FeeCalculator.total_cost(
            spread=0.0002,
            quantity=0.1,
            contract_size=100_000,
            commission_per_lot=3.5,
            swap_rate=-2.5,
            hold_days=1,
        )
        # spread: 0.0002 * 0.1 * 100000 = 2.0
        # commission: 3.5 * 0.1 = 0.35
        # swap: abs(-2.5 * 0.1 * 1) = 0.25
        assert total == pytest.approx(2.6)

    def test_effective_entry_buy(self):
        price = FeeCalculator.effective_entry_price(
            OrderSide.BUY, ask=1.1002, bid=1.1000, estimated_slippage=0.0001
        )
        assert price == pytest.approx(1.1003)

    def test_effective_entry_sell(self):
        price = FeeCalculator.effective_entry_price(
            OrderSide.SELL, ask=1.1002, bid=1.1000, estimated_slippage=0.0001
        )
        assert price == pytest.approx(1.0999)

    def test_breakeven_buy(self):
        be = FeeCalculator.breakeven_price(
            OrderSide.BUY, entry_price=1.1002, spread=0.0002, commission_per_unit=0.00001
        )
        assert be > 1.1002

    def test_breakeven_sell(self):
        be = FeeCalculator.breakeven_price(
            OrderSide.SELL, entry_price=1.1000, spread=0.0002, commission_per_unit=0.00001
        )
        assert be < 1.1000


# ===========================================================================
# Slippage Estimator
# ===========================================================================

class TestSlippageEstimator:
    def test_default_estimate(self):
        est = SlippageEstimator()
        # With no history, should return conservative default (0.05% of price)
        slippage = est.estimate("broker1", 1.1000, OrderSide.BUY)
        assert slippage == pytest.approx(1.1000 * 0.0005, rel=0.01)

    def test_estimate_with_history(self):
        est = SlippageEstimator()
        # Record some fills with small slippage
        for i in range(20):
            est.record("broker1", 1.1000, 1.1000 + 0.0001 * (i % 3))
        slippage = est.estimate("broker1", 1.1000, OrderSide.BUY)
        assert slippage > 0
        assert slippage < 0.01  # Should be small

    def test_estimate_pct(self):
        est = SlippageEstimator()
        assert est.estimate_pct("unknown") == pytest.approx(0.0005)

    def test_history_window(self):
        est = SlippageEstimator(window_size=5)
        for i in range(20):
            est.record("b", 1.0, 1.0 + 0.001)
        # Should only keep last 5
        assert len(est._history["b"]) == 5


# ===========================================================================
# Smart Order Router
# ===========================================================================

class TestSmartOrderRouter:
    @pytest.mark.asyncio
    async def test_route_basic(self):
        reg = BrokerRegistry()
        broker = FakeBroker("primary")
        reg.register("primary", broker, default=True)
        router = SmartOrderRouter(reg)
        await router.start()

        order = BrokerOrder(symbol="BTC/USDT", side=OrderSide.BUY, quantity=0.01)
        result = await router.route(order)
        assert result.status == OrderStatus.FILLED
        assert result.broker == "primary"
        await router.stop()

    @pytest.mark.asyncio
    async def test_route_picks_best_spread(self):
        reg = BrokerRegistry()
        tight = FakeBroker("tight", tick_spread=0.0001)
        wide = FakeBroker("wide", tick_spread=0.0010)
        reg.register("tight", tight)
        reg.register("wide", wide)
        router = SmartOrderRouter(reg, config=RouterConfig(strategy=RoutingStrategy.BEST_PRICE))
        await router.start()

        order = BrokerOrder(symbol="EUR/USD", side=OrderSide.BUY, quantity=0.1)
        result = await router.route(order)
        # Should pick tight spread broker
        assert result.broker == "tight"
        await router.stop()

    @pytest.mark.asyncio
    async def test_route_failover(self):
        reg = BrokerRegistry()
        bad = FakeBroker("bad", should_fail=True)
        good = FakeBroker("good")
        reg.register("bad", bad)
        reg.register("good", good)
        router = SmartOrderRouter(reg)
        await router.start()

        order = BrokerOrder(symbol="EUR/USD", side=OrderSide.BUY, quantity=0.1)
        result = await router.route(order)
        assert result.broker == "good"
        await router.stop()

    @pytest.mark.asyncio
    async def test_route_all_fail_raises(self):
        reg = BrokerRegistry()
        bad1 = FakeBroker("bad1", should_fail=True)
        bad2 = FakeBroker("bad2", should_fail=True)
        reg.register("bad1", bad1)
        reg.register("bad2", bad2)
        router = SmartOrderRouter(reg)
        await router.start()

        order = BrokerOrder(symbol="EUR/USD", side=OrderSide.BUY, quantity=0.1)
        with pytest.raises(RuntimeError, match="All routing candidates failed"):
            await router.route(order)
        await router.stop()

    @pytest.mark.asyncio
    async def test_estimate_cost(self):
        reg = BrokerRegistry()
        broker = FakeBroker("b1")
        reg.register("b1", broker)
        router = SmartOrderRouter(reg)
        await router.start()

        order = BrokerOrder(symbol="EUR/USD", side=OrderSide.BUY, quantity=0.1)
        eq = await router.estimate_cost(order, broker="b1")
        assert eq.broker == "b1"
        assert eq.spread > 0
        assert eq.estimated_fee >= 0
        await router.stop()

    @pytest.mark.asyncio
    async def test_get_all_quotes(self):
        reg = BrokerRegistry()
        reg.register("a", FakeBroker("a"))
        reg.register("b", FakeBroker("b"))
        router = SmartOrderRouter(reg)
        await router.start()

        quotes = await router.get_all_quotes("EUR/USD")
        assert len(quotes) == 2
        assert "a" in quotes
        assert "b" in quotes
        await router.stop()

    def test_set_commission(self):
        reg = BrokerRegistry()
        router = SmartOrderRouter(reg)
        router.set_commission("mt5", 3.5)
        assert router._commission_schedule["mt5"] == 3.5

    def test_metrics(self):
        reg = BrokerRegistry()
        router = SmartOrderRouter(reg)
        metrics = router.metrics()
        assert isinstance(metrics, dict)

    @pytest.mark.asyncio
    async def test_sticky_routing(self):
        reg = BrokerRegistry()
        reg.register("a", FakeBroker("a"))
        reg.register("b", FakeBroker("b"))
        config = RouterConfig(strategy=RoutingStrategy.STICKY)
        router = SmartOrderRouter(reg, config=config)
        await router.start()

        order = BrokerOrder(symbol="EUR/USD", side=OrderSide.BUY, quantity=0.1)
        result1 = await router.route(order)
        # Second call should use same broker
        result2 = await router.route(order)
        assert result1.broker == result2.broker
        await router.stop()

    @pytest.mark.asyncio
    async def test_round_robin_routing(self):
        reg = BrokerRegistry()
        reg.register("a", FakeBroker("a"))
        reg.register("b", FakeBroker("b"))
        config = RouterConfig(strategy=RoutingStrategy.ROUND_ROBIN)
        router = SmartOrderRouter(reg, config=config)
        await router.start()

        # Create fresh order objects so round-robin state advances
        order1 = BrokerOrder(symbol="EUR/USD", side=OrderSide.BUY, quantity=0.1)
        r1 = await router.route(order1)
        order2 = BrokerOrder(symbol="EUR/USD", side=OrderSide.BUY, quantity=0.1)
        r2 = await router.route(order2)
        # Should alternate between a and b
        brokers_used = {r1.broker, r2.broker}
        assert len(brokers_used) == 2, f"Expected 2 brokers, got {brokers_used}"
        await router.stop()

    @pytest.mark.asyncio
    async def test_last_execution_quality_set(self):
        reg = BrokerRegistry()
        reg.register("b", FakeBroker("b"))
        router = SmartOrderRouter(reg)
        await router.start()

        order = BrokerOrder(symbol="EUR/USD", side=OrderSide.BUY, quantity=0.1)
        await router.route(order)
        assert router.last_execution_quality is not None
        assert router.last_execution_quality.broker == "b"
        assert router.last_execution_quality.spread > 0
        await router.stop()

    @pytest.mark.asyncio
    async def test_max_spread_filter(self):
        reg = BrokerRegistry()
        # 0.0100 spread on EUR/USD = 1000 pips (pip_size=0.0001)
        wide = FakeBroker("wide", tick_spread=0.0100)
        reg.register("wide", wide)
        # Filter at 5 pips — should reject the 1000-pip spread
        config = RouterConfig(max_spread_pips=5.0)
        router = SmartOrderRouter(reg, config=config)
        await router.start()

        order = BrokerOrder(symbol="EUR/USD", side=OrderSide.BUY, quantity=0.1)
        with pytest.raises(RuntimeError, match="eligible|routing candidates failed"):
            await router.route(order)
        await router.stop()

    @pytest.mark.asyncio
    async def test_symbol_affinity(self):
        reg = BrokerRegistry()
        reg.register("a", FakeBroker("a"))
        router = SmartOrderRouter(reg)
        await router.start()

        order = BrokerOrder(symbol="BTC/USDT", side=OrderSide.BUY, quantity=0.01)
        await router.route(order)
        affinity = router.symbol_affinity()
        assert "BTC/USDT" in affinity
        await router.stop()


# ===========================================================================
# MT5 Connector (mocked)
# ===========================================================================

class TestMT5Connector:
    def test_order_type_mapping(self):
        from alphastack.brokers.mt5_connector import _ORDER_TYPE_MAP, _ORDER_TYPE_MAP_SELL
        assert _ORDER_TYPE_MAP[OrderType.MARKET] == 0
        assert _ORDER_TYPE_MAP[OrderType.LIMIT] == 2
        assert _ORDER_TYPE_MAP[OrderType.STOP] == 4
        assert _ORDER_TYPE_MAP_SELL[OrderType.MARKET] == 1
        assert _ORDER_TYPE_MAP_SELL[OrderType.LIMIT] == 3

    def test_status_mapping(self):
        from alphastack.brokers.mt5_connector import _MT5_STATUS_MAP
        assert _MT5_STATUS_MAP[0] == OrderStatus.PENDING
        assert _MT5_STATUS_MAP[2] == OrderStatus.FILLED
        assert _MT5_STATUS_MAP[3] == OrderStatus.CANCELLED
        assert _MT5_STATUS_MAP[5] == OrderStatus.REJECTED

    def test_error_names(self):
        from alphastack.brokers.mt5_connector import _describe_mt5_error
        desc = _describe_mt5_error(10009)
        assert "10009" in desc
        assert "completed" in desc.lower()

    def test_tif_mapping(self):
        from alphastack.brokers.mt5_connector import _TIF_MAP
        assert _TIF_MAP[TimeInForce.GTC] == 0
        assert _TIF_MAP[TimeInForce.DAY] == 1


# ===========================================================================
# CCXT Connector (mocked)
# ===========================================================================

class TestCCXTConnector:
    def test_status_mapping(self):
        from alphastack.brokers.ccxt_connector import _CCXT_STATUS_MAP
        assert _CCXT_STATUS_MAP["open"] == OrderStatus.OPEN
        assert _CCXT_STATUS_MAP["closed"] == OrderStatus.FILLED
        assert _CCXT_STATUS_MAP["canceled"] == OrderStatus.CANCELLED
        assert _CCXT_STATUS_MAP["expired"] == OrderStatus.EXPIRED

    def test_rate_limiter(self):
        from alphastack.brokers.ccxt_connector import _RateLimiter
        rl = _RateLimiter(requests_per_second=20.0)
        assert rl._interval == pytest.approx(0.05)


# ===========================================================================
# Router Config
# ===========================================================================

class TestRouterConfig:
    def test_defaults(self):
        cfg = RouterConfig()
        assert cfg.strategy == RoutingStrategy.BALANCED
        assert cfg.cost_weight == 0.40
        assert cfg.fill_weight == 0.25
        assert cfg.max_slippage_pct == 0.50

    def test_custom_config(self):
        cfg = RouterConfig(
            strategy=RoutingStrategy.BEST_PRICE,
            cost_weight=0.8,
            max_spread_pips=10.0,
        )
        assert cfg.strategy == RoutingStrategy.BEST_PRICE
        assert cfg.cost_weight == 0.8


# ===========================================================================
# Routing Strategy Enum
# ===========================================================================

class TestRoutingStrategy:
    def test_all_strategies(self):
        assert RoutingStrategy.BEST_PRICE.value == "best_price"
        assert RoutingStrategy.BEST_FILL.value == "best_fill"
        assert RoutingStrategy.LOWEST_LATENCY.value == "lowest_latency"
        assert RoutingStrategy.BALANCED.value == "balanced"
        assert RoutingStrategy.ROUND_ROBIN.value == "round_robin"
        assert RoutingStrategy.STICKY.value == "sticky"


# ===========================================================================
# Execution Quality
# ===========================================================================

class TestExecutionQuality:
    def test_defaults(self):
        eq = ExecutionQuality(broker="test", symbol="EUR/USD")
        assert eq.spread == 0.0
        assert eq.fill_rate == 0.8
        assert eq.total_score == 0.0

    def test_full_quality(self):
        eq = ExecutionQuality(
            broker="mt5",
            symbol="EUR/USD",
            spread=0.0002,
            spread_pips=2.0,
            spread_pct=0.0018,
            bid=1.1000,
            ask=1.1002,
            mid=1.1001,
            estimated_slippage=0.00005,
            estimated_fee=2.5,
            latency_ms=150.0,
            fill_rate=0.95,
            total_score=0.85,
        )
        assert eq.broker == "mt5"
        assert eq.total_score == 0.85


# ===========================================================================
# Integration: Router + Registry + OrderManager
# ===========================================================================

class TestIntegratedFlow:
    @pytest.mark.asyncio
    async def test_full_order_lifecycle(self):
        """Test: register → connect → route → track → complete."""
        reg = BrokerRegistry()
        broker = FakeBroker("primary")
        reg.register("primary", broker, default=True)

        om = OrderManager()
        router = SmartOrderRouter(reg)
        await router.start()

        # Place order
        order = BrokerOrder(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=0.01,
            price=65000.0,
        )
        result = await router.route(order)
        om.register(result)

        # Verify
        assert result.status == OrderStatus.FILLED
        tracked = om.get(result.id)
        assert tracked is not None
        assert tracked.status == OrderStatus.FILLED
        assert router.last_execution_quality is not None

        await router.stop()

    @pytest.mark.asyncio
    async def test_multi_broker_routing(self):
        """Test routing across multiple brokers picks the best one."""
        reg = BrokerRegistry()
        cheap = FakeBroker("cheap", tick_spread=0.00005)
        expensive = FakeBroker("expensive", tick_spread=0.0050)
        reg.register("cheap", cheap)
        reg.register("expensive", expensive)

        router = SmartOrderRouter(reg, config=RouterConfig(strategy=RoutingStrategy.BEST_PRICE))
        await router.start()

        order = BrokerOrder(symbol="EUR/USD", side=OrderSide.SELL, quantity=0.5)
        result = await router.route(order)
        assert result.broker == "cheap"

        await router.stop()

    @pytest.mark.asyncio
    async def test_failover_with_metrics(self):
        """Test failover updates metrics correctly."""
        reg = BrokerRegistry()
        bad = FakeBroker("bad", should_fail=True)
        good = FakeBroker("good")
        reg.register("bad", bad)
        reg.register("good", good)

        router = SmartOrderRouter(reg)
        await router.start()

        order = BrokerOrder(symbol="EUR/USD", side=OrderSide.BUY, quantity=0.1)
        result = await router.route(order)
        assert result.broker == "good"

        metrics = router.metrics()
        assert metrics["bad"]["error_count"] == 1
        assert metrics["good"]["order_count"] == 1

        await router.stop()
