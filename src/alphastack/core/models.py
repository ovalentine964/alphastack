"""SQLAlchemy ORM models + Pydantic schemas for AlphaStack."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# ===========================================================================
# SQLAlchemy Base
# ===========================================================================

class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Side(str, enum.Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, enum.Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderStatus(str, enum.Enum):
    NEW = "new"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class PositionSide(str, enum.Enum):
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


class SignalSide(str, enum.Enum):
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


class RiskLevel(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# ORM Models
# ---------------------------------------------------------------------------

class Account(Base):
    """Trading account / portfolio."""

    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    broker: Mapped[str] = mapped_column(String(64))
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    balance: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=0)
    equity: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=0)
    margin_used: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    positions: Mapped[list[Position]] = relationship(back_populates="account")
    orders: Mapped[list[Order]] = relationship(back_populates="account")


class Position(Base):
    """Open position."""

    __tablename__ = "positions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"))
    symbol: Mapped[str] = mapped_column(String(32))
    side: Mapped[PositionSide] = mapped_column(SAEnum(PositionSide))
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    entry_price: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    current_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=0)
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=0)
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=0)
    stop_loss: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), default=None)
    take_profit: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), default=None)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    account: Mapped[Account] = relationship(back_populates="positions")

    __table_args__ = (
        Index("ix_positions_account_symbol", "account_id", "symbol"),
    )


class Order(Base):
    """Order submitted to a broker."""

    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"))
    broker_order_id: Mapped[str | None] = mapped_column(String(128))
    symbol: Mapped[str] = mapped_column(String(32))
    side: Mapped[Side] = mapped_column(SAEnum(Side))
    order_type: Mapped[OrderType] = mapped_column(SAEnum(OrderType))
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), default=None)
    stop_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), default=None)
    filled_quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=0)
    avg_fill_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), default=None)
    status: Mapped[OrderStatus] = mapped_column(SAEnum(OrderStatus), default=OrderStatus.NEW)
    strategy: Mapped[str | None] = mapped_column(String(64))
    signal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    account: Mapped[Account] = relationship(back_populates="orders")

    __table_args__ = (
        Index("ix_orders_account_status", "account_id", "status"),
        Index("ix_orders_symbol_created", "symbol", "created_at"),
    )


class Signal(Base):
    """Trading signal from strategy or agent."""

    __tablename__ = "signals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol: Mapped[str] = mapped_column(String(32))
    side: Mapped[SignalSide] = mapped_column(SAEnum(SignalSide))
    strength: Mapped[float] = mapped_column(Float)  # -1.0 to 1.0
    timeframe: Mapped[str] = mapped_column(String(16))
    strategy: Mapped[str] = mapped_column(String(64))
    agent_id: Mapped[str | None] = mapped_column(String(64))
    reasoning: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_signals_symbol_strategy", "symbol", "strategy", "created_at"),
    )


class Trade(Base):
    """Executed trade (fill)."""

    __tablename__ = "trades"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"))
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"))
    symbol: Mapped[str] = mapped_column(String(32))
    side: Mapped[Side] = mapped_column(SAEnum(Side))
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    price: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    commission: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=0)
    slippage: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=0)
    strategy: Mapped[str | None] = mapped_column(String(64))
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_trades_symbol_executed", "symbol", "executed_at"),
    )


class MarketData(Base):
    """OHLCV candle data."""

    __tablename__ = "market_data"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32))
    timeframe: Mapped[str] = mapped_column(String(16))  # "1m", "5m", "1h", "1d", etc.
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    open: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    high: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    low: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    close: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    volume: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    source: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (
        Index("ix_market_data_symbol_tf_ts", "symbol", "timeframe", "timestamp", unique=True),
    )


class TickData(Base):
    """Tick-level price data."""

    __tablename__ = "tick_data"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    bid: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    ask: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    last: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    volume: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=0)
    source: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (
        Index("ix_tick_data_symbol_ts", "symbol", "timestamp"),
    )


class AgentDecision(Base):
    """Record of an agent's reasoning and decision."""

    __tablename__ = "agent_decisions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[str] = mapped_column(String(64))
    agent_type: Mapped[str] = mapped_column(String(64))  # "analyst", "risk", "executor", etc.
    symbol: Mapped[str | None] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(64))
    reasoning: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    input_data: Mapped[dict | None] = mapped_column(JSONB, default=None)
    output_data: Mapped[dict | None] = mapped_column(JSONB, default=None)
    latency_ms: Mapped[int | None] = mapped_column(Integer, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_agent_decisions_agent_ts", "agent_id", "created_at"),
    )


class RiskCheck(Base):
    """Risk management check record."""

    __tablename__ = "risk_checks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"))
    level: Mapped[RiskLevel] = mapped_column(SAEnum(RiskLevel))
    rule: Mapped[str] = mapped_column(String(128))
    passed: Mapped[bool] = mapped_column(Boolean)
    message: Mapped[str] = mapped_column(Text, default="")
    current_value: Mapped[float] = mapped_column(Float, default=0.0)
    limit_value: Mapped[float] = mapped_column(Float, default=0.0)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, default=None)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_risk_checks_account_ts", "account_id", "checked_at"),
    )


# ===========================================================================
# Pydantic Schemas (API request/response)
# ===========================================================================

class AccountCreate(BaseModel):
    name: str
    broker: str
    currency: str = "USD"


class AccountRead(BaseModel):
    id: uuid.UUID
    name: str
    broker: str
    currency: str
    balance: Decimal
    equity: Decimal
    is_active: bool

    model_config = {"from_attributes": True}


class OrderCreate(BaseModel):
    symbol: str
    side: Side
    order_type: OrderType = OrderType.MARKET
    quantity: Decimal
    price: Decimal | None = None
    stop_price: Decimal | None = None
    strategy: str | None = None


class OrderRead(BaseModel):
    id: uuid.UUID
    symbol: str
    side: Side
    order_type: OrderType
    quantity: Decimal
    price: Decimal | None
    status: OrderStatus
    filled_quantity: Decimal
    avg_fill_price: Decimal | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PositionRead(BaseModel):
    id: uuid.UUID
    symbol: str
    side: PositionSide
    quantity: Decimal
    entry_price: Decimal
    current_price: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal

    model_config = {"from_attributes": True}


class SignalCreate(BaseModel):
    symbol: str
    side: SignalSide
    strength: float = Field(ge=-1.0, le=1.0)
    timeframe: str
    strategy: str
    agent_id: str | None = None
    reasoning: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class SignalRead(BaseModel):
    id: uuid.UUID
    symbol: str
    side: SignalSide
    strength: float
    strategy: str
    confidence: float
    created_at: datetime

    model_config = {"from_attributes": True}


class TradeRead(BaseModel):
    id: uuid.UUID
    symbol: str
    side: Side
    quantity: Decimal
    price: Decimal
    commission: Decimal
    strategy: str | None
    executed_at: datetime

    model_config = {"from_attributes": True}


class AgentDecisionRead(BaseModel):
    id: uuid.UUID
    agent_id: str
    agent_type: str
    symbol: str | None
    action: str
    reasoning: str
    confidence: float
    latency_ms: int | None
    created_at: datetime

    model_config = {"from_attributes": True}
