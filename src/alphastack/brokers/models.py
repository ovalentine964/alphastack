"""Unified broker domain models.

Every connector maps its native responses into these models so the rest of
AlphaStack works with a single, broker-agnostic representation.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"


class OrderStatus(str, Enum):
    PENDING = "pending"
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class TimeInForce(str, Enum):
    GTC = "gtc"  # Good-Til-Cancelled
    IOC = "ioc"  # Immediate-or-Cancel
    FOK = "fok"  # Fill-or-Kill
    DAY = "day"  # Day order


class PositionSide(str, Enum):
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


# ---------------------------------------------------------------------------
# Order
# ---------------------------------------------------------------------------

class BrokerOrder(BaseModel):
    """Unified order representation across all brokers."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    broker_order_id: str = ""  # Venue-assigned ID after submission
    broker: str = ""
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    order_type: OrderType = OrderType.MARKET
    quantity: float = 0.0
    price: float | None = None  # Limit / stop price
    stop_price: float | None = None
    trailing_stop_distance: float | None = None
    trailing_stop_offset: float | None = None
    time_in_force: TimeInForce = TimeInForce.GTC
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    avg_fill_price: float = 0.0
    commission: float = 0.0
    slippage: float = 0.0
    stop_loss: float | None = None
    take_profit: float | None = None
    comment: str = ""
    magic_number: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    filled_at: datetime | None = None
    raw: dict[str, Any] = Field(default_factory=dict)  # Original broker response

    # -- Forex-specific fields ----------------------------------------------
    lot_size: float | None = None          # Forex lots (0.01, 0.1, 1.0, …)
    pip_value: float | None = None         # Calculated pip value for this trade
    spread_at_entry: float | None = None   # Spread in pips when order was placed
    swap_rate: float | None = None         # Expected daily swap cost per lot
    margin_required: float | None = None   # Margin needed for this order
    contract_size: float | None = None     # Units per standard lot (100 000 for forex)

    @property
    def is_active(self) -> bool:
        return self.status in (OrderStatus.PENDING, OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED)

    @property
    def remaining_quantity(self) -> float:
        return max(0.0, self.quantity - self.filled_quantity)


# ---------------------------------------------------------------------------
# Position
# ---------------------------------------------------------------------------

class BrokerPosition(BaseModel):
    """Unified position representation."""

    broker: str = ""
    symbol: str = ""
    side: PositionSide = PositionSide.FLAT
    quantity: float = 0.0
    avg_entry_price: float = 0.0
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    margin_used: float = 0.0
    leverage: float = 1.0
    contract_size: float = 1.0   # Units per standard lot (100 000 for forex; 1.0 for crypto)
    lot_size: float = 0.0        # Number of lots (for forex; 0.0 for crypto)
    swap: float = 0.0            # Accumulated swap/rollover cost
    spread_at_entry: float = 0.0 # Spread in pips when position was opened
    stop_loss: float | None = None
    take_profit: float | None = None
    open_time: datetime | None = None
    magic_number: int = 0
    raw: dict[str, Any] = Field(default_factory=dict)

    @property
    def notional_value(self) -> float:
        """Notional value of the position.

        For forex: ``lots × contract_size × price``
        For crypto: ``quantity × price`` (contract_size defaults to 1.0)
        """
        if self.lot_size > 0:
            return abs(self.lot_size * self.contract_size * self.current_price)
        return abs(self.quantity * self.current_price)

    @property
    def effective_leverage(self) -> float:
        """Notional value divided by margin used (0 if no margin)."""
        if self.margin_used <= 0:
            return 0.0
        return self.notional_value / self.margin_used

    @property
    def pnl_pct(self) -> float:
        if self.avg_entry_price == 0:
            return 0.0
        if self.side == PositionSide.LONG:
            return (self.current_price - self.avg_entry_price) / self.avg_entry_price * 100
        elif self.side == PositionSide.SHORT:
            return (self.avg_entry_price - self.current_price) / self.avg_entry_price * 100
        return 0.0


# ---------------------------------------------------------------------------
# Balance
# ---------------------------------------------------------------------------

class BrokerBalance(BaseModel):
    """Unified account balance."""

    broker: str = ""
    currency: str = "USD"
    total: float = 0.0
    available: float = 0.0
    used_margin: float = 0.0
    free_margin: float = 0.0
    equity: float = 0.0
    unrealized_pnl: float = 0.0
    margin_level: float = 0.0  # percentage
    raw: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Tick / Quote
# ---------------------------------------------------------------------------

class BrokerTick(BaseModel):
    """Unified tick/quote data."""

    broker: str = ""
    symbol: str = ""
    bid: float = 0.0
    ask: float = 0.0
    last: float = 0.0
    volume: float = 0.0
    spread: float = 0.0           # Spread in price units
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    raw: dict[str, Any] = Field(default_factory=dict)

    # -- Forex-specific fields ----------------------------------------------
    swap_long: float = 0.0         # Daily swap rate for long positions
    swap_short: float = 0.0        # Daily swap rate for short positions
    spread_pips: float = 0.0       # Spread converted to pips (set by connector)

    @property
    def mid(self) -> float:
        if self.bid and self.ask:
            return (self.bid + self.ask) / 2.0
        return self.last


# ---------------------------------------------------------------------------
# OHLCV Bar
# ---------------------------------------------------------------------------

class BrokerBar(BaseModel):
    """Unified OHLCV bar."""

    symbol: str = ""
    timeframe: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: float = 0.0
    tick_volume: float = 0.0
    spread: float = 0.0
