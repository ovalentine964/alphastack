"""Shared test fixtures for AlphaStack test suite."""

from __future__ import annotations

import asyncio
import math
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest
import pytest_asyncio

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
)
from alphastack.core.events import Event, EventBus, EventType, SignalEvent, TradeEvent
from alphastack.risk.exposure import ExposureManager, PositionExposure
from alphastack.risk.position_sizer import PositionSizer, SizingMethod, SizingRequest
from alphastack.risk.validators import TradeValidator
from alphastack.strategy.context import (
    AlphaStackContext,
    Bias,
    CandlestickData,
    ConfluenceResult,
    Direction,
    ExitSignal,
    FundamentalData,
    JournalEntry,
    LiquidityPool,
    MarketBias,
    PositionSizing,
    RSIData,
    SMCData,
    Session,
    SessionData,
    SRLevels,
    Level,
    StructureData,
    StructureType,
    StopLoss,
    TakeProfit,
    TradeManagement,
)


# ---------------------------------------------------------------------------
# Event loop
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# Mock Broker
# ---------------------------------------------------------------------------

class MockBrokerConnector(BrokerConnector):
    """In-memory mock broker for testing — no real I/O."""

    def __init__(self, name: str = "mock") -> None:
        super().__init__(name)
        self._connected = False
        self._positions: dict[str, BrokerPosition] = {}
        self._orders: dict[str, BrokerOrder] = {}
        self._balance = BrokerBalance(
            broker="mock",
            currency="USD",
            total=10_000.0,
            available=10_000.0,
            used_margin=0.0,
            free_margin=10_000.0,
            equity=10_000.0,
            unrealized_pnl=0.0,
            margin_level=0.0,
        )
        self._tick_counter = 0

    async def connect(self) -> None:
        self._connected = True
        self._transition(ConnectionState.CONNECTED)

    async def disconnect(self) -> None:
        self._connected = False
        self._transition(ConnectionState.DISCONNECTED)

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def get_balance(self) -> BrokerBalance:
        return self._balance

    async def get_positions(self) -> list[BrokerPosition]:
        return list(self._positions.values())

    async def place_order(self, order: BrokerOrder) -> BrokerOrder:
        order.status = OrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.avg_fill_price = order.price or 1.1000
        order.broker_order_id = f"MOCK-{uuid.uuid4().hex[:8]}"
        order.filled_at = datetime.now(timezone.utc)
        self._orders[order.id] = order
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

    async def get_tick(self, symbol: str) -> BrokerTick:
        self._tick_counter += 1
        base = 1.1000 + (self._tick_counter % 100) * 0.0001
        return BrokerTick(
            broker="mock",
            symbol=symbol,
            bid=base,
            ask=base + 0.0002,
            last=base + 0.0001,
            volume=1000.0,
            spread=0.0002,
            timestamp=datetime.now(timezone.utc),
        )

    async def get_bars(
        self, symbol: str, timeframe: str = "1h", count: int = 500
    ) -> list[BrokerBar]:
        bars: list[BrokerBar] = []
        np.random.seed(hash(symbol) % 2**31)
        price = 1.1000
        for i in range(count):
            delta = np.random.randn() * 0.001
            o = price
            c = price + delta
            h = max(o, c) + abs(np.random.randn() * 0.0005)
            l = min(o, c) - abs(np.random.randn() * 0.0005)
            bars.append(BrokerBar(
                symbol=symbol,
                timeframe=timeframe,
                open=o, high=h, low=l, close=c,
                volume=float(np.random.randint(100, 10000)),
            ))
            price = c
        return bars


@pytest.fixture
def mock_broker() -> MockBrokerConnector:
    """Provide a fresh mock broker for each test."""
    return MockBrokerConnector()


# ---------------------------------------------------------------------------
# Event Bus (in-memory, no Redis)
# ---------------------------------------------------------------------------

class InMemoryEventBus:
    """In-memory event bus for testing — no Redis dependency."""

    def __init__(self) -> None:
        self._handlers: dict[EventType, list[Any]] = {}
        self._published: list[Event] = []

    def subscribe(self, event_type: EventType, handler: Any) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    async def publish(self, event: Event) -> str:
        self._published.append(event)
        for handler in self._handlers.get(event.type, []):
            await handler(event)
        return event.id

    @property
    def published_events(self) -> list[Event]:
        return self._published

    def clear(self) -> None:
        self._published.clear()


@pytest.fixture
def event_bus() -> InMemoryEventBus:
    """Provide a fresh in-memory event bus."""
    return InMemoryEventBus()


# ---------------------------------------------------------------------------
# Market data generator
# ---------------------------------------------------------------------------

def generate_ohlcv(
    n: int = 500,
    start_price: float = 1.1000,
    volatility: float = 0.001,
    seed: int = 42,
) -> dict[str, list[float]]:
    """Generate synthetic OHLCV data as dict of lists."""
    rng = np.random.RandomState(seed)
    closes: list[float] = []
    opens: list[float] = []
    highs: list[float] = []
    lows: list[float] = []
    volumes: list[float] = []

    price = start_price
    for _ in range(n):
        delta = rng.randn() * volatility
        o = price
        c = price + delta
        h = max(o, c) + abs(rng.randn() * volatility * 0.5)
        l = min(o, c) - abs(rng.randn() * volatility * 0.5)
        vol = float(rng.randint(100, 10000))
        opens.append(round(o, 6))
        highs.append(round(h, 6))
        lows.append(round(l, 6))
        closes.append(round(c, 6))
        volumes.append(vol)
        price = c

    return {
        "opens": opens,
        "highs": highs,
        "lows": lows,
        "closes": closes,
        "volumes": volumes,
    }


@pytest.fixture
def sample_ohlcv() -> dict[str, list[float]]:
    """Generate synthetic OHLCV data (500 bars)."""
    return generate_ohlcv(500)


@pytest.fixture
def sample_ohlcv_array(sample_ohlcv: dict[str, list[float]]) -> np.ndarray:
    """OHLCV as numpy array (legacy compat)."""
    return np.column_stack([
        sample_ohlcv["opens"],
        sample_ohlcv["highs"],
        sample_ohlcv["lows"],
        sample_ohlcv["closes"],
        sample_ohlcv["volumes"],
    ])


@pytest.fixture
def sample_features(sample_ohlcv_array: np.ndarray) -> np.ndarray:
    """Create simple feature matrix from OHLCV."""
    close = sample_ohlcv_array[:, 3].astype(float)
    returns = np.diff(close) / close[:-1]
    sma_20 = np.convolve(close, np.ones(20) / 20, mode="valid")
    rsi_like = returns[-len(sma_20):] / (np.abs(returns[-len(sma_20):]) + 1e-8)

    min_len = min(len(sma_20), len(rsi_like))
    features = np.column_stack([
        sma_20[-min_len:],
        rsi_like[-min_len:],
        returns[-min_len:],
    ])
    return features.astype(np.float32)


@pytest.fixture
def sample_labels(sample_features: np.ndarray) -> np.ndarray:
    """Binary labels: 1 if next return > 0, else 0."""
    np.random.seed(42)
    return (np.random.randn(len(sample_features)) > 0).astype(np.float32)


# ---------------------------------------------------------------------------
# Event fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_signal_event() -> SignalEvent:
    return SignalEvent(
        symbol="EUR/USD",
        side="long",
        strength=0.85,
        timeframe="1h",
        strategy="alphastack_v1",
        source="test",
    )


@pytest.fixture
def sample_trade_event() -> TradeEvent:
    return TradeEvent(
        order_id="ORD-001",
        symbol="EUR/USD",
        side="buy",
        quantity=0.1,
        price=1.1050,
        order_type="market",
        status="filled",
        source="test",
    )


# ---------------------------------------------------------------------------
# Risk fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def trade_validator() -> TradeValidator:
    return TradeValidator()


@pytest.fixture
def exposure_manager() -> ExposureManager:
    return ExposureManager(
        max_open_positions=5,
        max_per_pair_pct=30.0,
        max_per_session_pct=50.0,
        max_leverage=3.0,
    )


@pytest.fixture
def position_sizer() -> PositionSizer:
    return PositionSizer()


@pytest.fixture
def sample_trade_request() -> dict[str, Any]:
    return {
        "symbol": "EUR/USD",
        "direction": "long",
        "requested_size": 0.1,
        "entry_price": 1.1050,
        "stop_loss": 1.1000,
        "take_profit": 1.1150,
        "strategy_id": "test_strategy",
        "session": "london",
    }


# ---------------------------------------------------------------------------
# Strategy context fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_context() -> AlphaStackContext:
    """A minimal strategy context with market data for pipeline tests."""
    ohlcv = generate_ohlcv(200, seed=42)
    return AlphaStackContext(
        symbol="EUR/USD",
        timeframe="1H",
        timestamp=datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
        market_data={
            **ohlcv,
            "close": ohlcv["closes"][-1],
            "high_impact_events": [],
            "news_sentiment": 0.1,
            "volatility_index": 14.0,
            "atr_pips": 50.0,
            "pip_size": 0.0001,
            "spread_pips": 1.5,
            "account_balance": 10_000.0,
            "risk_pct": 1.0,
            "pip_value": 10.0,
            "stop_multiplier": 1.5,
            "rsi_period": 14,
        },
    )


@pytest.fixture
def bullish_context() -> AlphaStackContext:
    """A context with strong bullish signals across all steps."""
    ohlcv = generate_ohlcv(200, seed=100, start_price=1.1000, volatility=0.001)
    return AlphaStackContext(
        symbol="EUR/USD",
        timeframe="1H",
        timestamp=datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
        market_data={
            **ohlcv,
            "close": ohlcv["closes"][-1],
            "high_impact_events": [],
            "news_sentiment": 0.6,
            "volatility_index": 12.0,
            "atr_pips": 40.0,
            "pip_size": 0.0001,
            "spread_pips": 1.0,
            "account_balance": 10_000.0,
            "risk_pct": 1.0,
            "pip_value": 10.0,
            "stop_multiplier": 1.5,
            "rsi_period": 14,
            "entry_price": ohlcv["closes"][-1],
        },
        fundamental=FundamentalData(bias=Bias.BULLISH, news_sentiment=0.6, macro_regime="risk_on"),
        bias=MarketBias(bias=Bias.BULLISH, trend_strength=0.8, htf_bias=Bias.BULLISH),
        session=SessionData(active=Session.LONDON, volatility=1.0, typical_range_pips=50.0),
        structure=StructureData(
            structure_type=StructureType.HIGHER_HIGH,
            direction=Direction.LONG,
            swing_highs=[1.1050, 1.1080],
            swing_lows=[1.0980, 1.1010],
        ),
        sr_levels=SRLevels(
            support=[Level(price=1.0980, strength=0.8, touches=3, label="support")],
            resistance=[Level(price=1.1150, strength=0.6, touches=2, label="resistance")],
        ),
        rsi=RSIData(value=35.0, signal="oversold", divergence="none"),
        candlestick=CandlestickData(pattern_score=0.5),
        confluence=ConfluenceResult(score=72.0, direction=Direction.LONG),
        stop_loss=StopLoss(price=1.0980, stop_type="structure", atr_value=40.0),
        take_profit=TakeProfit(levels=[1.1100, 1.1150, 1.1200], rr_ratio=2.0),
        sizing=PositionSizing(position_size=0.25, risk_amount=100.0, risk_pct=1.0),
    )


# ---------------------------------------------------------------------------
# Model / ML fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_model_dir(tmp_path: Any) -> str:
    d = tmp_path / "models"
    d.mkdir()
    return str(d)
