"""Shared test fixtures for AlphaStack test suite."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest
import pytest_asyncio

from alphastack.brokers.base import BrokerConnector
from alphastack.brokers.models import (
    BrokerBalance,
    BrokerOrder,
    BrokerPosition,
    BrokerTick,
    OrderSide,
    OrderStatus,
    OrderType,
)
from alphastack.core.events import Event, EventBus, EventType, SignalEvent, TradeEvent
from alphastack.risk.exposure import ExposureManager, PositionExposure
from alphastack.risk.position_sizer import PositionSizer, SizingMethod, SizingRequest
from alphastack.risk.validators import TradeValidator
from alphastack.strategy.context import AlphaStackContext, Bias, Direction, Session


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
            equity=10_000.0,
            free=10_000.0,
            used=0.0,
            currency="USD",
        )
        self._tick_counter = 0

    async def connect(self) -> None:
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def get_balance(self) -> BrokerBalance:
        return self._balance

    async def get_positions(self) -> list[BrokerPosition]:
        return list(self._positions.values())

    async def get_position(self, symbol: str) -> BrokerPosition | None:
        return self._positions.get(symbol)

    async def place_order(self, order: BrokerOrder) -> BrokerOrder:
        order.status = OrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.avg_fill_price = order.price or 1.1000
        order.broker_order_id = f"MOCK-{uuid.uuid4().hex[:8]}"
        self._orders[order.id] = order
        return order

    async def cancel_order(self, order_id: str) -> bool:
        order = self._orders.get(order_id)
        if order:
            order.status = OrderStatus.CANCELLED
            return True
        return False

    async def modify_order(self, order_id: str, **kwargs: Any) -> BrokerOrder | None:
        order = self._orders.get(order_id)
        if order:
            for k, v in kwargs.items():
                if hasattr(order, k):
                    setattr(order, k, v)
            return order
        return None

    async def get_tick(self, symbol: str) -> BrokerTick:
        self._tick_counter += 1
        base = 1.1000 + (self._tick_counter % 100) * 0.0001
        return BrokerTick(
            symbol=symbol,
            bid=base,
            ask=base + 0.0002,
            timestamp=datetime.now(timezone.utc),
        )

    async def get_bars(
        self, symbol: str, timeframe: str = "1h", limit: int = 100
    ) -> list[Any]:
        return []


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
# Test data generators
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_ohlcv() -> np.ndarray:
    """Generate synthetic OHLCV data (500 bars)."""
    np.random.seed(42)
    n = 500
    close = 1.1000 + np.cumsum(np.random.randn(n) * 0.001)
    high = close + np.abs(np.random.randn(n) * 0.0005)
    low = close - np.abs(np.random.randn(n) * 0.0005)
    opn = close + np.random.randn(n) * 0.0003
    volume = np.random.randint(100, 10000, n).astype(float)
    return np.column_stack([opn, high, low, close, volume])


@pytest.fixture
def sample_features(sample_ohlcv: np.ndarray) -> np.ndarray:
    """Create simple feature matrix from OHLCV."""
    close = sample_ohlcv[:, 3]
    returns = np.diff(close) / close[:-1]
    sma_20 = np.convolve(close, np.ones(20) / 20, mode="valid")
    rsi_like = returns[-len(sma_20):] / (np.abs(returns[-len(sma_20):]) + 1e-8)

    # Align lengths
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


@pytest.fixture
def sample_signal_event() -> SignalEvent:
    """A sample signal event."""
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
    """A sample trade event."""
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
    """Standard trade validator."""
    return TradeValidator()


@pytest.fixture
def exposure_manager() -> ExposureManager:
    """Standard exposure manager with test-friendly limits."""
    return ExposureManager(
        max_open_positions=5,
        max_per_pair_pct=30.0,
        max_per_session_pct=50.0,
        max_leverage=3.0,
    )


@pytest.fixture
def position_sizer() -> PositionSizer:
    """Standard position sizer."""
    return PositionSizer()


@pytest.fixture
def sample_trade_request() -> dict[str, Any]:
    """Sample trade request parameters."""
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
# Strategy context
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_context() -> AlphaStackContext:
    """A minimal strategy context for pipeline tests."""
    return AlphaStackContext(
        symbol="EUR/USD",
        timeframe="1h",
        current_price=1.1050,
        timestamp=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Model / ML fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_model_dir(tmp_path: Any) -> str:
    """Temporary directory for model artifacts."""
    d = tmp_path / "models"
    d.mkdir()
    return str(d)
