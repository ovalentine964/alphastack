"""Signal Routes – active signals, signal history.

Wired to the SignalStore which subscribes to the event bus for real-time
signals from the strategy pipeline, with demo data fallback.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from alphastack.api.rest.deps import signal_store
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
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=SignalListResponse)
async def list_active_signals(
    symbol: str | None = None,
    strategy_id: str | None = None,
) -> SignalListResponse:
    """List currently active signals."""
    items = signal_store.list_active(symbol=symbol, strategy_id=strategy_id)
    return SignalListResponse(
        signals=[Signal(**_coerce_signal(s)) for s in items],
        total=len(items),
    )


@router.get("/history", response_model=SignalListResponse)
async def signal_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    symbol: str | None = None,
) -> SignalListResponse:
    """Signal history (all signals, active and expired)."""
    items = signal_store.list_all(symbol=symbol)
    total = len(items)
    start = (page - 1) * page_size
    page_items = items[start : start + page_size]
    return SignalListResponse(
        signals=[Signal(**_coerce_signal(s)) for s in page_items],
        total=total,
    )


def _coerce_signal(s: dict) -> dict:
    """Ensure signal dict has correct types for the Signal schema."""
    created = s.get("created_at")
    if isinstance(created, str):
        created = datetime.fromisoformat(created)
    expires = s.get("expires_at")
    if isinstance(expires, str):
        expires = datetime.fromisoformat(expires)
    return {
        **s,
        "created_at": created or datetime.utcnow(),
        "expires_at": expires,
    }
