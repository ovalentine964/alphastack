"""Signal Routes – active signals, signal history."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from alphastack.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/signals")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SignalDirection(str, Enum):
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"


class SignalStrength(str, Enum):
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    VERY_STRONG = "very_strong"


class Signal(BaseModel):
    id: str
    symbol: str
    direction: SignalDirection
    strength: SignalStrength
    strategy_id: str
    confidence: float = Field(..., ge=0, le=1)
    entry_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    risk_reward: float | None = None
    reason: str = ""
    created_at: datetime
    expires_at: datetime | None = None
    is_active: bool = True


class SignalListResponse(BaseModel):
    signals: list[Signal]
    total: int


# ---------------------------------------------------------------------------
# In-memory signal store (demo)
# ---------------------------------------------------------------------------

_SIGNALS: dict[str, dict[str, Any]] = {}


def _seed_demo_signals() -> None:
    if _SIGNALS:
        return
    now = datetime.now(timezone.utc)
    demos = [
        {"symbol": "BTC/USDT", "direction": "long", "strength": "strong",
         "strategy_id": "smc_v1", "confidence": 0.85, "entry_price": 67200.0,
         "stop_loss": 66500.0, "take_profit": 69000.0, "risk_reward": 2.57,
         "reason": "Bullish order block at 67200 with volume confirmation"},
        {"symbol": "EUR/USD", "direction": "short", "strength": "moderate",
         "strategy_id": "mean_revert_v1", "confidence": 0.72, "entry_price": 1.0870,
         "stop_loss": 1.0920, "take_profit": 1.0780, "risk_reward": 1.8,
         "reason": "RSI overbought + bearish divergence on H4"},
        {"symbol": "ETH/USDT", "direction": "long", "strength": "very_strong",
         "strategy_id": "breakout_v1", "confidence": 0.91, "entry_price": 3520.0,
         "stop_loss": 3450.0, "take_profit": 3700.0, "risk_reward": 2.57,
         "reason": "Ascending triangle breakout with high volume"},
    ]
    for d in demos:
        sid = str(uuid.uuid4())
        _SIGNALS[sid] = {"id": sid, "is_active": True, "created_at": now.isoformat(), "expires_at": None, **d}


_seed_demo_signals()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=SignalListResponse)
async def list_active_signals(
    symbol: str | None = None,
    strategy_id: str | None = None,
) -> SignalListResponse:
    """List currently active signals."""
    items = [s for s in _SIGNALS.values() if s["is_active"]]
    if symbol:
        items = [s for s in items if s["symbol"].upper() == symbol.upper()]
    if strategy_id:
        items = [s for s in items if s["strategy_id"] == strategy_id]
    return SignalListResponse(signals=[Signal(**s) for s in items], total=len(items))


@router.get("/history", response_model=SignalListResponse)
async def signal_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    symbol: str | None = None,
) -> SignalListResponse:
    """Signal history (all signals, active and expired)."""
    items = list(_SIGNALS.values())
    if symbol:
        items = [s for s in items if s["symbol"].upper() == symbol.upper()]
    total = len(items)
    start = (page - 1) * page_size
    page_items = items[start : start + page_size]
    return SignalListResponse(signals=[Signal(**s) for s in page_items], total=total)
