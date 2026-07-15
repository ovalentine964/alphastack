"""Analytics Routes – performance, equity curve, win-rate, PnL history, risk.

Provides aggregated analytics data computed from the trade store and
portfolio service.  These endpoints are consumed by the web and mobile
frontends for the analytics dashboard.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from alphastack.api.rest.deps import portfolio_service, trade_store
from alphastack.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/analytics")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class PerformanceResponse(BaseModel):
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


class EquityPoint(BaseModel):
    date: str
    equity: float
    drawdown_pct: float


class EquityCurveResponse(BaseModel):
    points: list[EquityPoint]
    initial_capital: float
    current_equity: float


class WinRateResponse(BaseModel):
    win_rate: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    breakeven_trades: int
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    profit_factor: float


class PnlHistoryPoint(BaseModel):
    date: str
    realized_pnl: float
    cumulative_pnl: float
    trade_count: int


class RiskMetrics(BaseModel):
    max_drawdown_pct: float
    current_drawdown_pct: float
    var_95: float
    var_99: float
    sharpe_ratio: float
    sortino_ratio: float
    avg_risk_per_trade: float
    max_consecutive_losses: int
    risk_reward_avg: float


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/performance", response_model=PerformanceResponse)
async def get_performance() -> PerformanceResponse:
    """Portfolio performance metrics — delegates to /portfolio/performance."""
    from alphastack.api.rest.routes.portfolio import get_performance as _perf
    return await _perf()


@router.get("/equity-curve", response_model=EquityCurveResponse)
async def get_equity_curve(
    days: int = Query(90, ge=1, le=365),
) -> EquityCurveResponse:
    """Equity curve over time from closed trades."""
    closed = trade_store.list_trades(status_filter="closed")
    initial_capital = 10000.0  # TODO: pull from config / broker balance
    cumulative = initial_capital
    peak = initial_capital
    points: list[EquityPoint] = []

    # Build a point per closed trade (ordered by close time)
    sorted_trades = sorted(closed, key=lambda t: t.get("closed_at") or "")
    for t in sorted_trades[-days:]:
        pnl = t.get("pnl") or 0.0
        cumulative += pnl
        peak = max(peak, cumulative)
        dd = ((peak - cumulative) / peak * 100) if peak else 0.0
        points.append(EquityPoint(
            date=(t.get("closed_at") or datetime.now(timezone.utc).isoformat())[:10],
            equity=round(cumulative, 2),
            drawdown_pct=round(dd, 2),
        ))

    # Always include at least the starting point
    if not points:
        points.append(EquityPoint(
            date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            equity=initial_capital,
            drawdown_pct=0.0,
        ))

    return EquityCurveResponse(
        points=points,
        initial_capital=initial_capital,
        current_equity=round(cumulative, 2),
    )


@router.get("/win-rate", response_model=WinRateResponse)
async def get_win_rate() -> WinRateResponse:
    """Win/loss statistics."""
    closed = trade_store.list_trades(status_filter="closed")
    pnls = [t.get("pnl") or 0 for t in closed]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    breakeven = [p for p in pnls if p == 0]
    n = len(pnls) or 1

    return WinRateResponse(
        win_rate=round(len(wins) / n * 100, 2),
        total_trades=len(closed),
        winning_trades=len(wins),
        losing_trades=len(losses),
        breakeven_trades=len(breakeven),
        avg_win=round(sum(wins) / len(wins), 4) if wins else 0.0,
        avg_loss=round(sum(losses) / len(losses), 4) if losses else 0.0,
        largest_win=round(max(wins, default=0), 4),
        largest_loss=round(min(losses, default=0), 4),
        profit_factor=round(
            sum(wins) / abs(sum(losses)), 4
        ) if losses else 0.0,
    )


@router.get("/pnl-history", response_model=list[PnlHistoryPoint])
async def get_pnl_history(
    period: str = Query("30d"),
) -> list[PnlHistoryPoint]:
    """Daily PnL history for charting."""
    closed = trade_store.list_trades(status_filter="closed")
    # Group by date
    by_date: dict[str, list[float]] = {}
    for t in closed:
        date_str = (t.get("closed_at") or "")[:10]
        if not date_str:
            continue
        by_date.setdefault(date_str, []).append(t.get("pnl") or 0.0)

    cumulative = 0.0
    points: list[PnlHistoryPoint] = []
    for date_str in sorted(by_date.keys()):
        daily_pnls = by_date[date_str]
        daily_total = sum(daily_pnls)
        cumulative += daily_total
        points.append(PnlHistoryPoint(
            date=date_str,
            realized_pnl=round(daily_total, 4),
            cumulative_pnl=round(cumulative, 4),
            trade_count=len(daily_pnls),
        ))

    return points


@router.get("/risk", response_model=RiskMetrics)
async def get_risk_metrics() -> RiskMetrics:
    """Risk analytics — drawdown, VaR, consecutive losses."""
    closed = trade_store.list_trades(status_filter="closed")
    pnls = [t.get("pnl") or 0 for t in closed]
    n = len(pnls) or 1

    # Drawdown
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for p in pnls:
        cumulative += p
        peak = max(peak, cumulative)
        dd = (peak - cumulative) / max(abs(peak), 1.0) * 100
        max_dd = max(max_dd, dd)

    # VaR (simple percentile method)
    sorted_pnls = sorted(pnls) if pnls else [0.0]
    var_95_idx = max(int(n * 0.05), 0)
    var_99_idx = max(int(n * 0.01), 0)

    # Max consecutive losses
    max_consec = 0
    current_consec = 0
    for p in pnls:
        if p < 0:
            current_consec += 1
            max_consec = max(max_consec, current_consec)
        else:
            current_consec = 0

    # Risk/reward
    wins = [p for p in pnls if p > 0]
    losses = [abs(p) for p in pnls if p < 0]
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 1.0
    rr = avg_win / avg_loss if avg_loss else 0.0

    mean_pnl = sum(pnls) / n
    variance = sum((p - mean_pnl) ** 2 for p in pnls) / n if n > 1 else 0.0
    vol = variance ** 0.5
    downside = [p for p in pnls if p < 0]
    down_var = sum(p ** 2 for p in downside) / n if downside else 0.0
    down_dev = down_var ** 0.5

    return RiskMetrics(
        max_drawdown_pct=round(max_dd, 2),
        current_drawdown_pct=round(max_dd, 2),  # simplified
        var_95=round(sorted_pnls[var_95_idx], 4),
        var_99=round(sorted_pnls[var_99_idx], 4),
        sharpe_ratio=round((mean_pnl / vol) * (252 ** 0.5), 4) if vol else 0.0,
        sortino_ratio=round((mean_pnl / down_dev) * (252 ** 0.5), 4) if down_dev else 0.0,
        avg_risk_per_trade=round(sum(losses) / len(losses), 4) if losses else 0.0,
        max_consecutive_losses=max_consec,
        risk_reward_avg=round(rr, 4),
    )
