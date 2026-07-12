"""Trade Routes – list, create, detail, close."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

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
    price: float | None = None  # None = market order
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
# In-memory trade store (replace with DB in production)
# ---------------------------------------------------------------------------

_TRADES: dict[str, dict[str, Any]] = {}


def _seed_demo_trades() -> None:
    """Pre-populate with demo data for development."""
    if _TRADES:
        return
    now = datetime.now(timezone.utc)
    demos = [
        {"symbol": "BTC/USDT", "side": "buy", "quantity": 0.5, "entry_price": 67500.0,
         "stop_loss": 66000.0, "take_profit": 71000.0, "status": "open", "pnl": None},
        {"symbol": "EUR/USD", "side": "sell", "quantity": 100000, "entry_price": 1.0850,
         "stop_loss": 1.0900, "take_profit": 1.0750, "status": "open", "pnl": None},
        {"symbol": "ETH/USDT", "side": "buy", "quantity": 5.0, "entry_price": 3500.0,
         "stop_loss": 3350.0, "take_profit": 3800.0, "status": "closed",
         "exit_price": 3750.0, "pnl": 1250.0},
    ]
    for d in demos:
        tid = str(uuid.uuid4())
        _TRADES[tid] = {
            "id": tid,
            **d,
            "strategy_id": "demo_v1",
            "opened_at": now.isoformat(),
            "closed_at": now.isoformat() if d["status"] == "closed" else None,
            "notes": "Demo trade",
        }


_seed_demo_trades()


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
    items = list(_TRADES.values())
    if status_filter:
        items = [t for t in items if t["status"] == status_filter.value]
    if symbol:
        items = [t for t in items if t["symbol"].upper() == symbol.upper()]

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
    """Create a manual trade."""
    tid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    trade = {
        "id": tid,
        "symbol": body.symbol,
        "side": body.side.value,
        "quantity": body.quantity,
        "entry_price": body.price,
        "exit_price": None,
        "stop_loss": body.stop_loss,
        "take_profit": body.take_profit,
        "status": "pending" if body.price is None else "open",
        "strategy_id": body.strategy_id,
        "pnl": None,
        "opened_at": now.isoformat(),
        "closed_at": None,
        "notes": body.notes,
    }
    _TRADES[tid] = trade
    logger.info("trade_created", trade_id=tid, symbol=body.symbol, side=body.side.value)
    return TradeResponse(**trade)


@router.get("/{trade_id}", response_model=TradeResponse)
async def get_trade(trade_id: str) -> TradeResponse:
    """Get trade details by ID."""
    trade = _TRADES.get(trade_id)
    if not trade:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trade not found")
    return TradeResponse(**trade)


@router.put("/{trade_id}/close", response_model=TradeResponse)
async def close_trade(trade_id: str, exit_price: float | None = None) -> TradeResponse:
    """Close an open trade."""
    trade = _TRADES.get(trade_id)
    if not trade:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trade not found")
    if trade["status"] != "open":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Trade is {trade['status']}, not open")

    now = datetime.now(timezone.utc)
    price = exit_price or trade["entry_price"]  # fallback
    entry = trade["entry_price"] or price
    qty = trade["quantity"]
    multiplier = 1 if trade["side"] == "buy" else -1
    pnl = (price - entry) * qty * multiplier

    trade["exit_price"] = price
    trade["pnl"] = round(pnl, 4)
    trade["status"] = "closed"
    trade["closed_at"] = now.isoformat()

    logger.info("trade_closed", trade_id=trade_id, pnl=trade["pnl"])
    return TradeResponse(**trade)
