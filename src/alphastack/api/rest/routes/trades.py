"""Trade Routes – list, create, detail, close.

Wired to the TradeStore service layer which connects to broker connectors
and the event bus when available, falling back to in-memory demo data.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from alphastack.api.rest.deps import trade_store
from alphastack.security.validators import InputValidator
from alphastack.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/trades")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class TradeStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    PENDING = "pending"


class TradeCreate(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=32)
    side: Side
    quantity: float = Field(..., gt=0)
    price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    strategy_id: str | None = None
    notes: str = ""


class TradeResponse(BaseModel):
    id: str
    symbol: str
    side: Side
    quantity: float
    entry_price: float | None
    exit_price: float | None
    stop_loss: float | None
    take_profit: float | None
    status: TradeStatus
    strategy_id: str | None
    pnl: float | None
    opened_at: datetime
    closed_at: datetime | None
    notes: str


class TradeListResponse(BaseModel):
    trades: list[TradeResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=TradeListResponse)
async def list_trades(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status_filter: TradeStatus | None = Query(None, alias="status"),
    symbol: str | None = None,
) -> TradeListResponse:
    """List trades with optional filters."""
    items = trade_store.list_trades(
        status_filter=status_filter.value if status_filter else None,
        symbol=symbol,
    )
    total = len(items)
    start = (page - 1) * page_size
    page_items = items[start : start + page_size]
    return TradeListResponse(
        trades=[TradeResponse(**t) for t in page_items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=TradeResponse, status_code=status.HTTP_201_CREATED)
async def create_trade(body: TradeCreate) -> TradeResponse:
    """Create a manual trade with input validation."""
    # Validate order parameters using the security validator
    validation = InputValidator.validate_order(
        symbol=body.symbol,
        side=body.side.value,
        order_type="market" if body.price is None else "limit",
        quantity=body.quantity,
        price=body.price,
        stop_loss=body.stop_loss,
        take_profit=body.take_profit,
    )
    if not validation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation failed: {'; '.join(validation.errors)}",
        )

    # Sanitize notes field
    if body.notes:
        notes_check = InputValidator.sanitize_string(body.notes, max_length=1000)
        if not notes_check:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid notes: {notes_check.errors}",
            )

    trade = trade_store.create_trade(body.model_dump())
    return TradeResponse(**trade)


@router.get("/{trade_id}", response_model=TradeResponse)
async def get_trade(trade_id: str) -> TradeResponse:
    """Get trade details by ID."""
    trade = trade_store.get_trade(trade_id)
    if not trade:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trade not found")
    return TradeResponse(**trade)


@router.put("/{trade_id}/close", response_model=TradeResponse)
async def close_trade(trade_id: str, exit_price: float | None = None) -> TradeResponse:
    """Close an open trade."""
    trade = trade_store.close_trade(trade_id, exit_price)
    if trade is None:
        existing = trade_store.get_trade(trade_id)
        if existing is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trade not found")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Trade is {existing['status']}, not open",
        )
    return TradeResponse(**trade)
