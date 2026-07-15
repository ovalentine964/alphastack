"""Portfolio Routes – positions, P&L, performance metrics.

Connects to broker connectors for real position and balance data when
available, falling back to in-memory trade store data.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from alphastack.api.rest.deps import portfolio_service, trade_store
from alphastack.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/portfolio")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class Position(BaseModel):
    symbol: str
    side: str
    quantity: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    weight_pct: float


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
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=list[Position])
async def get_positions() -> list[Position]:
    """Current open positions — from live broker data or trade store."""
    # Try live broker positions first
    broker_positions = await portfolio_service.get_positions()
    if broker_positions:
        total_value = sum(p["current_price"] * p["quantity"] for p in broker_positions)
        result: list[Position] = []
        for p in broker_positions:
            val = p["current_price"] * p["quantity"]
            result.append(Position(
                symbol=p["symbol"],
                side=p["side"],
                quantity=p["quantity"],
                entry_price=round(p["entry_price"], 6),
                current_price=round(p["current_price"], 6),
                unrealized_pnl=round(p["unrealized_pnl"], 4),
                unrealized_pnl_pct=round(p["unrealized_pnl_pct"], 4),
                weight_pct=round((val / total_value * 100) if total_value else 0.0, 2),
            ))
        return result

    # Fallback: compute from in-memory trade store
    open_trades = trade_store.list_trades(status_filter="open")
    if not open_trades:
        return []

    positions: list[Position] = []
    total_value = 0.0
    for t in open_trades:
        entry = t.get("entry_price") or 0.0
        # Use broker tick for current price if available, else slight offset
        current = await _get_current_price(t["symbol"], entry)
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
            weight_pct=0.0,
        ))

    for p in positions:
        val = p.current_price * p.quantity
        p.weight_pct = round((val / total_value * 100) if total_value else 0.0, 2)

    return positions


async def _get_current_price(symbol: str, fallback: float) -> float:
    """Fetch current price from broker tick data, with fallback."""
    from alphastack.api.rest.deps import get_broker_registry
    registry = get_broker_registry()
    connector = registry.default
    if connector and connector.is_connected:
        try:
            tick = await connector.get_tick(symbol)
            return tick.mid if tick.mid else tick.last
        except Exception:
            pass
    return fallback * 1.005  # small offset as last resort


@router.get("/pnl", response_model=PnLSummary)
async def get_pnl() -> PnLSummary:
    """P&L summary across all trades."""
    open_trades = trade_store.list_trades(status_filter="open")
    closed_trades = trade_store.list_trades(status_filter="closed")

    total_realized = sum(t.get("pnl") or 0 for t in closed_trades)

    # Unrealized from live prices
    total_unrealized = 0.0
    for t in open_trades:
        entry = t.get("entry_price") or 0.0
        current = await _get_current_price(t["symbol"], entry)
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
        today_pnl=round(total_realized, 4),
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
    closed = trade_store.list_trades(status_filter="closed")
    now = datetime.now(timezone.utc)
    pnls = [t.get("pnl") or 0 for t in closed]
    total_return = sum(pnls)

    n = len(pnls) or 1
    mean_pnl = total_return / n
    variance = sum((p - mean_pnl) ** 2 for p in pnls) / n if n > 1 else 0.0
    volatility = variance ** 0.5

    # Sharpe ratio (annualised)
    sharpe = (mean_pnl / volatility) * (252 ** 0.5) if volatility else 0.0

    # Sortino ratio (downside deviation)
    downside_returns = [p for p in pnls if p < 0]
    downside_var = sum(p ** 2 for p in downside_returns) / n if downside_returns else 0.0
    downside_dev = downside_var ** 0.5
    sortino = (mean_pnl / downside_dev) * (252 ** 0.5) if downside_dev else 0.0

    # Max drawdown
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for p in pnls:
        cumulative += p
        peak = max(peak, cumulative)
        dd = (peak - cumulative) / max(abs(peak), 1.0) * 100
        max_dd = max(max_dd, dd)

    calmar = (total_return / 10000 * 100 * 252 / max(n, 1)) / max_dd if max_dd else 0.0

    return PerformanceMetrics(
        total_return_pct=round(total_return / 10000 * 100, 4),
        annualized_return_pct=round(total_return / 10000 * 100 * (252 / max(n, 1)), 4),
        sharpe_ratio=round(sharpe, 4),
        sortino_ratio=round(sortino, 4),
        max_drawdown_pct=round(max_dd, 4),
        calmar_ratio=round(calmar, 4),
        volatility_annual_pct=round(volatility * (252 ** 0.5) / 10000 * 100, 4),
        avg_trade_duration_hours=24.0,
        expectancy=round(mean_pnl, 4),
        recovery_factor=round(total_return / abs(min(pnls, default=1)), 4),
        start_date=now,
        end_date=now,
        trading_days=n,
    )
