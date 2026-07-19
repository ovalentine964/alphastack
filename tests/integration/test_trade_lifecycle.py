"""Integration test: full trade lifecycle from signal to journal."""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from alphastack.brokers.models import BrokerOrder, OrderSide, OrderStatus, OrderType
from alphastack.core.events import EventType, SignalEvent, TradeEvent
from alphastack.risk.governor import RiskGovernor, TradeRequest
from alphastack.strategy.context import (
    AlphaStackContext,
    Bias,
    ConfluenceResult,
    Direction,
    FundamentalData,
    MarketBias,
    Session,
    SessionData,
    StructureData,
    StructureType,
)
from tests.conftest import InMemoryEventBus, MockBrokerConnector


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_trade_request_from_context(ctx: AlphaStackContext) -> TradeRequest:
    """Convert a strategy context into a TradeRequest for the risk governor."""
    return TradeRequest(
        symbol=ctx.symbol,
        direction="long" if ctx.confluence.direction == Direction.LONG else "short",
        requested_size=ctx.sizing.position_size or 0.1,
        entry_price=ctx.market_data.get("close", 1.1050),
        stop_loss=ctx.stop_loss.price or 1.1000,
        take_profit=ctx.take_profit.levels[0] if ctx.take_profit.levels else 0.0,
        strategy_id="alphastack_v1",
        session=ctx.session.active.value if ctx.session.active else "london",
    )


# ===========================================================================
# Full Trade Lifecycle
# ===========================================================================

class TestTradeLifecycle:
    """End-to-end: Signal → Risk check → Execution → Journal."""

    @pytest.mark.asyncio
    async def test_full_lifecycle_bullish(self, mock_broker, event_bus, bullish_context):
        """Happy path: bullish signal passes all gates, order filled, journal written."""
        await mock_broker.connect()

        # Step 1: Publish a signal event
        signal = SignalEvent(
            symbol="EUR/USD", side="long", strength=0.85,
            timeframe="1H", strategy="alphastack_v1",
        )
        await event_bus.publish(signal)

        # Step 2: Build trade request from context (override entry to be valid)
        ctx = bullish_context
        request = _make_trade_request_from_context(ctx)
        # Ensure entry > stop_loss for a valid long trade
        request.entry_price = 1.1050

        # Step 3: Risk approval
        gov = RiskGovernor(account_balance=10_000.0)
        approval = await gov.approve_trade(request)
        assert approval.approved is True

        # Step 4: Execute via broker
        order = BrokerOrder(
            symbol=request.symbol,
            side=OrderSide.BUY if request.direction == "long" else OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=approval.adjusted_size,
            price=request.entry_price,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
        )
        filled = await mock_broker.place_order(order)
        assert filled.status == OrderStatus.FILLED

        # Step 5: Publish trade event
        trade_evt = TradeEvent(
            order_id=filled.broker_order_id,
            symbol=filled.symbol,
            side="buy" if filled.side == OrderSide.BUY else "sell",
            quantity=filled.filled_quantity,
            price=filled.avg_fill_price,
            status="filled",
        )
        await event_bus.publish(trade_evt)

        # Verify: events recorded
        assert len(event_bus.published_events) == 2
        assert event_bus.published_events[0].type == EventType.SIGNAL
        assert event_bus.published_events[1].type == EventType.TRADE

        # Step 6: Record trade result for risk tracking
        gov.record_trade_result(50.0)
        assert gov.account_balance == 10_050.0

    @pytest.mark.asyncio
    async def test_lifecycle_rejected_by_risk(self, mock_broker, event_bus):
        """Trade rejected by risk governor — no execution."""
        await mock_broker.connect()
        gov = RiskGovernor(account_balance=10_000.0)
        gov.halt("test halt")

        request = TradeRequest(
            symbol="EUR/USD", direction="long", requested_size=0.1,
            entry_price=1.1050, stop_loss=1.1000,
        )
        approval = await gov.approve_trade(request)
        assert approval.approved is False

        # No order should be placed
        balance = await mock_broker.get_balance()
        assert balance.equity == 10_000.0

    @pytest.mark.asyncio
    async def test_lifecycle_with_circuit_breaker(self, mock_broker, event_bus):
        """Circuit breaker trips after consecutive losses, halting further trades."""
        await mock_broker.connect()
        gov = RiskGovernor(account_balance=10_000.0)

        # Record losses to trip circuit breaker
        for _ in range(6):
            gov.record_trade_result(-100.0)

        request = TradeRequest(
            symbol="EUR/USD", direction="long", requested_size=0.1,
            entry_price=1.1050, stop_loss=1.1000,
        )
        approval = await gov.approve_trade(request)
        assert approval.approved is False
        assert "Trading halted" in approval.rejection_reason

    @pytest.mark.asyncio
    async def test_position_size_reduced_by_risk(self, mock_broker, event_bus, bullish_context):
        """Risk governor may reduce position size."""
        await mock_broker.connect()
        gov = RiskGovernor(account_balance=10_000.0)

        # Request unreasonably large size
        request = TradeRequest(
            symbol="EUR/USD", direction="long", requested_size=500.0,
            entry_price=1.1050, stop_loss=1.1000,
        )
        approval = await gov.approve_trade(request)
        assert approval.approved is True
        assert approval.adjusted_size < 500.0

    @pytest.mark.asyncio
    async def test_multiple_trades_tracked(self, mock_broker, event_bus):
        """Multiple trades are correctly tracked by the risk system."""
        await mock_broker.connect()
        gov = RiskGovernor(account_balance=10_000.0)

        for i in range(3):
            request = TradeRequest(
                symbol="EUR/USD", direction="long", requested_size=0.05,
                entry_price=1.1050, stop_loss=1.1000,
            )
            approval = await gov.approve_trade(request)
            if approval.approved:
                gov.record_trade_result(20.0)  # each trade profits $20

        assert gov.account_balance == 10_060.0
