"""Portfolio Routes – positions, P&L, performance metrics."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from alphastack.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/portfolio")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class Position(BaseModel):
    symbol: str
    side: str  # long / short
    quantity: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    weight_pct: float  # % of portfolio


class PnLSummary(BaseModel):
    total_realized_pnl: float
    total_unrealized_pnl: float
    total_pnl: float
    today_pnl: float
    win_rate: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    best_trade_pnl: float
    worst_trade_pnl: float
    total_trades: int
    winning_trades: int
    losing_trades: int


class PerformanceMetrics(BaseModel):
    total_return_pct: float
    annualized_return_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown_pct: float
    calmar_ratio: float
    volatility_annual_pct: float
    avg_trade_duration_hours: float
    expectancy: float
    recovery_factor: float
    start_date: datetime
    end_date: datetime
    trading_days: int


# ---------------------------------------------------------------------------
# Helpers (read from trade store)
# ---------------------------------------------------------------------------

def _get_open_trades() -> list[dict[str, Any]]:
    from alphastack.api.rest.routes.trades import _TRADES
    return [t for t in _TRADES.values() if t["status"] == "open"]


def _get_closed_trades() -> list[dict[str, Any]]:
    from alphastack.api.rest.routes.trades import _TRADES
    return [t for t in _TRADES.values() if t["status"] == "closed"]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=list[Position])
async def get_positions() -> list[Position]:
    """Current open positions."""
    open_trades = _get_open_trades()
    if not open_trades:
        return []

    # Estimate current prices from entry (in prod, fetch live prices)
    positions: list[Position] = []
    total_value = 0.0
    for t in open_trades:
        # Simulate current price slightly different from entry
        entry = t.get("entry_price") or 0.0
        current = entry * 1.005  # placeholder
        qty = t["quantity"]
        side = "long" if t["side"] == "buy" else "short"
        multiplier = 1 if side == "long" else -1
        unrealized = (current - entry) * qty * multiplier
        unrealized_pct = ((current / entry) - 1) * 100 * multiplier if entry else 0.0
        value = current * qty
        total_value += value
        positions.append(Position(
            symbol=t["symbol"],
            side=side,
            quantity=qty,
            entry_price=round(entry, 6),
            current_price=round(current, 6),
            unrealized_pnl=round(unrealized, 4),
            unrealized_pnl_pct=round(unrealized_pct, 4),
            weight_pct=0.0,  # filled below
        ))

    # Compute weights
    for p in positions:
        val = p.current_price * p.quantity
        p.weight_pct = round((val / total_value * 100) if total_value else 0.0, 2)

    return positions


@router.get("/pnl", response_model=PnLSummary)
async def get_pnl() -> PnLSummary:
    """P&L summary across all trades."""
    open_trades = _get_open_trades()
    closed_trades = _get_closed_trades()

    total_realized = sum(t.get("pnl") or 0 for t in closed_trades)

    # Unrealized (same placeholder logic as positions)
    total_unrealized = 0.0
    for t in open_trades:
        entry = t.get("entry_price") or 0.0
        current = entry * 1.005
        qty = t["quantity"]
        multiplier = 1 if t["side"] == "buy" else -1
        total_unrealized += (current - entry) * qty * multiplier

    wins = [t for t in closed_trades if (t.get("pnl") or 0) > 0]
    losses = [t for t in closed_trades if (t.get("pnl") or 0) < 0]
    win_rate = len(wins) / len(closed_trades) * 100 if closed_trades else 0.0
    avg_win = sum(t["pnl"] for t in wins) / len(wins) if wins else 0.0
    avg_loss = sum(t["pnl"] for t in losses) / len(losses) if losses else 0.0
    gross_profit = sum(t["pnl"] for t in wins)
    gross_loss = abs(sum(t["pnl"] for t in losses)) or 1.0
    profit_factor = gross_profit / gross_loss

    all_pnls = [t.get("pnl") or 0 for t in closed_trades]
    return PnLSummary(
        total_realized_pnl=round(total_realized, 4),
        total_unrealized_pnl=round(total_unrealized, 4),
        total_pnl=round(total_realized + total_unrealized, 4),
        today_pnl=round(total_realized, 4),  # simplified
        win_rate=round(win_rate, 2),
        profit_factor=round(profit_factor, 4),
        avg_win=round(avg_win, 4),
        avg_loss=round(avg_loss, 4),
        best_trade_pnl=round(max(all_pnls, default=0), 4),
        worst_trade_pnl=round(min(all_pnls, default=0), 4),
        total_trades=len(closed_trades),
        winning_trades=len(wins),
        losing_trades=len(losses),
    )


@router.get("/performance", response_model=PerformanceMetrics)
async def get_performance() -> PerformanceMetrics:
    """Performance metrics for the portfolio."""
    closed = _get_closed_trades()
    now = datetime.now(timezone.utc)
    pnls = [t.get("pnl") or 0 for t in closed]
    total_return = sum(pnls)

    # Simplified metrics (replace with proper calculation in production)
    n = len(pnls) or 1
    mean_pnl = total_return / n
    variance = sum((p - mean_pnl) ** 2 for p in pnls) / n if n > 1 else 0.0
    volatility = variance ** 0.5
    sharpe = (mean_pnl / volatility) if volatility else 0.0

    return PerformanceMetrics(
        total_return_pct=round(total_return / 10000 * 100, 4),  # assume 10k base
        annualized_return_pct=round(total_return / 10000 * 100 * (252 / max(n, 1)), 4),
        sharpe_ratio=round(sharpe, 4),
        sortino_ratio=round(sharpe * 1.1, 4),  # placeholder
        max_drawdown_pct=round(abs(min(pnls, default=0)) / 10000 * 100, 4),
        calmar_ratio=0.0,
        volatility_annual_pct=round(volatility * (252 ** 0.5) / 10000 * 100, 4),
        avg_trade_duration_hours=24.0,
        expectancy=round(mean_pnl, 4),
        recovery_factor=round(total_return / abs(min(pnls, default=1)), 4),
        start_date=now,
        end_date=now,
        trading_days=n,
    )
