"""Performance metrics engine for paper trading.

Computes win rate, profit factor, Sharpe/Sortino ratios, drawdown,
and other key statistics from a stream of closed trade results.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from alphastack.utils.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Individual trade record
# ---------------------------------------------------------------------------

@dataclass
class TradeRecord:
    """A single closed trade for metrics computation."""

    id: str
    symbol: str
    side: str  # "long" | "short"
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float  # realized P&L in quote currency
    pnl_pct: float  # percentage return on notional
    entry_time: datetime
    exit_time: datetime
    commission: float = 0.0
    slippage_bps: float = 0.0
    reasoning: str = ""
    strategy: str = ""
    tags: list[str] = field(default_factory=list)

    @property
    def duration_minutes(self) -> float:
        return (self.exit_time - self.entry_time).total_seconds() / 60.0

    @property
    def is_win(self) -> bool:
        return self.pnl > 0

    @property
    def is_loss(self) -> bool:
        return self.pnl < 0


# ---------------------------------------------------------------------------
# Equity snapshot
# ---------------------------------------------------------------------------

@dataclass
class EquitySnapshot:
    """Point-in-time equity reading."""

    timestamp: datetime
    equity: float
    balance: float  # excluding unrealized
    unrealized_pnl: float = 0.0


# ---------------------------------------------------------------------------
# Performance Metrics
# ---------------------------------------------------------------------------

class PerformanceMetrics:
    """Real-time performance calculator for paper trading.

    Call ``record_trade()`` for each closed trade and ``snapshot_equity()``
    periodically.  All getters compute on the fly from the accumulated data.
    """

    def __init__(
        self,
        initial_balance: float = 10_000.0,
        risk_free_rate: float = 0.05,
        annualization_factor: float = 365.0,
    ) -> None:
        self.initial_balance = initial_balance
        self.risk_free_rate = risk_free_rate
        self.annualization_factor = annualization_factor

        self._trades: list[TradeRecord] = []
        self._equity_curve: list[EquitySnapshot] = []
        self._peak_equity: float = initial_balance
        self._started_at: datetime = datetime.now(timezone.utc)

        # Pre-computed caches (invalidated on new data)
        self._returns_cache: list[float] | None = None

        log.info("metrics_initialized", initial_balance=initial_balance)

    # -- Data ingestion -----------------------------------------------------

    def record_trade(self, trade: TradeRecord) -> None:
        """Record a completed trade."""
        self._trades.append(trade)
        self._returns_cache = None  # invalidate cache
        log.debug(
            "trade_recorded",
            trade_id=trade.id,
            symbol=trade.symbol,
            pnl=trade.pnl,
            pnl_pct=trade.pnl_pct,
        )

    def snapshot_equity(
        self,
        equity: float,
        balance: float,
        unrealized_pnl: float = 0.0,
    ) -> None:
        """Record an equity curve data point."""
        snap = EquitySnapshot(
            timestamp=datetime.now(timezone.utc),
            equity=equity,
            balance=balance,
            unrealized_pnl=unrealized_pnl,
        )
        self._equity_curve.append(snap)
        if equity > self._peak_equity:
            self._peak_equity = equity

    # -- Internal helpers ---------------------------------------------------

    def _returns(self) -> list[float]:
        """Percentage returns per equity snapshot."""
        if self._returns_cache is not None:
            return self._returns_cache

        if len(self._equity_curve) < 2:
            self._returns_cache = []
            return []

        rets: list[float] = []
        for i in range(1, len(self._equity_curve)):
            prev = self._equity_curve[i - 1].equity
            curr = self._equity_curve[i].equity
            if prev > 0:
                rets.append((curr - prev) / prev)
        self._returns_cache = rets
        return rets

    # -- Core metrics -------------------------------------------------------

    @property
    def trade_count(self) -> int:
        return len(self._trades)

    @property
    def win_count(self) -> int:
        return sum(1 for t in self._trades if t.is_win)

    @property
    def loss_count(self) -> int:
        return sum(1 for t in self._trades if t.is_loss)

    @property
    def breakeven_count(self) -> int:
        return self.trade_count - self.win_count - self.loss_count

    @property
    def win_rate(self) -> float:
        """Win rate as a fraction (0.0 – 1.0)."""
        if not self._trades:
            return 0.0
        return self.win_count / self.trade_count

    @property
    def total_pnl(self) -> float:
        return sum(t.pnl for t in self._trades)

    @property
    def total_commission(self) -> float:
        return sum(t.commission for t in self._trades)

    @property
    def net_pnl(self) -> float:
        return self.total_pnl - self.total_commission

    @property
    def avg_trade_pnl(self) -> float:
        if not self._trades:
            return 0.0
        return self.total_pnl / self.trade_count

    # -- Win / Loss breakdown -----------------------------------------------

    @property
    def avg_win(self) -> float:
        wins = [t.pnl for t in self._trades if t.is_win]
        return sum(wins) / len(wins) if wins else 0.0

    @property
    def avg_loss(self) -> float:
        losses = [t.pnl for t in self._trades if t.is_loss]
        return sum(losses) / len(losses) if losses else 0.0

    @property
    def largest_win(self) -> float:
        wins = [t.pnl for t in self._trades if t.is_win]
        return max(wins) if wins else 0.0

    @property
    def largest_loss(self) -> float:
        losses = [t.pnl for t in self._trades if t.is_loss]
        return min(losses) if losses else 0.0

    @property
    def avg_win_pct(self) -> float:
        wins = [t.pnl_pct for t in self._trades if t.is_win]
        return sum(wins) / len(wins) if wins else 0.0

    @property
    def avg_loss_pct(self) -> float:
        losses = [t.pnl_pct for t in self._trades if t.is_loss]
        return sum(losses) / len(losses) if losses else 0.0

    # -- Profit factor & risk-reward ----------------------------------------

    @property
    def profit_factor(self) -> float:
        """Gross profits / gross losses.  ∞ if no losses."""
        gross_profit = sum(t.pnl for t in self._trades if t.is_win)
        gross_loss = abs(sum(t.pnl for t in self._trades if t.is_loss))
        if gross_loss == 0:
            return float("inf") if gross_profit > 0 else 0.0
        return gross_profit / gross_loss

    @property
    def risk_reward_ratio(self) -> float:
        """Average win / |average loss|.  Higher is better."""
        avg_l = self.avg_loss
        if avg_l == 0:
            return float("inf") if self.avg_win > 0 else 0.0
        return self.avg_win / abs(avg_l)

    @property
    def expectancy(self) -> float:
        """Expected value per trade: (win_rate × avg_win) - (loss_rate × |avg_loss|)."""
        loss_rate = 1.0 - self.win_rate
        return (self.win_rate * self.avg_win) - (loss_rate * abs(self.avg_loss))

    # -- Drawdown -----------------------------------------------------------

    @property
    def max_drawdown(self) -> float:
        """Maximum drawdown as a positive fraction (0.0 – 1.0)."""
        if not self._equity_curve:
            return 0.0
        peak = self._equity_curve[0].equity
        max_dd = 0.0
        for snap in self._equity_curve:
            if snap.equity > peak:
                peak = snap.equity
            dd = (peak - snap.equity) / peak if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd
        return max_dd

    @property
    def current_drawdown(self) -> float:
        """Current drawdown from peak as a positive fraction."""
        if not self._equity_curve:
            return 0.0
        current = self._equity_curve[-1].equity
        if self._peak_equity <= 0:
            return 0.0
        return max(0.0, (self._peak_equity - current) / self._peak_equity)

    @property
    def max_drawdown_duration_hours(self) -> float:
        """Longest drawdown duration in hours."""
        if len(self._equity_curve) < 2:
            return 0.0

        peak = self._equity_curve[0].equity
        dd_start = self._equity_curve[0].timestamp
        max_duration = 0.0
        in_dd = False

        for snap in self._equity_curve:
            if snap.equity >= peak:
                if in_dd:
                    dur = (snap.timestamp - dd_start).total_seconds() / 3600.0
                    max_duration = max(max_duration, dur)
                peak = snap.equity
                in_dd = False
            else:
                if not in_dd:
                    dd_start = snap.timestamp
                    in_dd = True

        # Handle ongoing drawdown
        if in_dd:
            dur = (self._equity_curve[-1].timestamp - dd_start).total_seconds() / 3600.0
            max_duration = max(max_duration, dur)

        return max_duration

    # -- Ratios (Sharpe, Sortino, Calmar) -----------------------------------

    def _annualized_return(self) -> float:
        """Annualized return from equity curve."""
        if len(self._equity_curve) < 2:
            return 0.0
        first = self._equity_curve[0].equity
        last = self._equity_curve[-1].equity
        if first <= 0:
            return 0.0

        elapsed_days = (
            self._equity_curve[-1].timestamp - self._equity_curve[0].timestamp
        ).total_seconds() / 86400.0
        if elapsed_days <= 0:
            return 0.0

        total_return = (last - first) / first
        # Annualize with overflow guard
        ratio = self.annualization_factor / elapsed_days
        try:
            base = 1 + total_return
            if base <= 0:
                return total_return
            return base ** ratio - 1
        except (OverflowError, ValueError, ZeroDivisionError):
            # For very short periods with large returns, cap at a reasonable value
            if total_return > 0:
                return float('inf')
            return -1.0

    def _annualized_volatility(self, downside_only: bool = False) -> float:
        """Annualized standard deviation of returns."""
        rets = self._returns()
        if len(rets) < 2:
            return 0.0

        if downside_only:
            rets = [r for r in rets if r < 0]
            if len(rets) < 2:
                return 0.0

        mean = sum(rets) / len(rets)
        variance = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
        daily_vol = math.sqrt(variance)
        return daily_vol * math.sqrt(self.annualization_factor)

    @property
    def sharpe_ratio(self) -> float:
        """Annualized Sharpe ratio."""
        vol = self._annualized_volatility()
        if vol == 0:
            return 0.0
        ann_ret = self._annualized_return()
        return (ann_ret - self.risk_free_rate) / vol

    @property
    def sortino_ratio(self) -> float:
        """Annualized Sortino ratio (penalizes only downside volatility)."""
        vol = self._annualized_volatility(downside_only=True)
        if vol == 0:
            return 0.0
        ann_ret = self._annualized_return()
        return (ann_ret - self.risk_free_rate) / vol

    @property
    def calmar_ratio(self) -> float:
        """Annualized return / max drawdown."""
        mdd = self.max_drawdown
        if mdd == 0:
            return float("inf") if self._annualized_return() > 0 else 0.0
        return self._annualized_return() / mdd

    # -- Streaks ------------------------------------------------------------

    @property
    def max_consecutive_wins(self) -> int:
        max_streak = 0
        current = 0
        for t in self._trades:
            if t.is_win:
                current += 1
                max_streak = max(max_streak, current)
            else:
                current = 0
        return max_streak

    @property
    def max_consecutive_losses(self) -> int:
        max_streak = 0
        current = 0
        for t in self._trades:
            if t.is_loss:
                current += 1
                max_streak = max(max_streak, current)
            else:
                current = 0
        return max_streak

    # -- Duration -----------------------------------------------------------

    @property
    def uptime_hours(self) -> float:
        return (datetime.now(timezone.utc) - self._started_at).total_seconds() / 3600.0

    @property
    def avg_trade_duration_minutes(self) -> float:
        if not self._trades:
            return 0.0
        return sum(t.duration_minutes for t in self._trades) / len(self._trades)

    # -- Slippage stats -----------------------------------------------------

    @property
    def avg_slippage_bps(self) -> float:
        if not self._trades:
            return 0.0
        return sum(t.slippage_bps for t in self._trades) / len(self._trades)

    # -- Export --------------------------------------------------------------

    def summary(self) -> dict[str, Any]:
        """Full metrics summary as a dict."""
        return {
            "trade_count": self.trade_count,
            "win_count": self.win_count,
            "loss_count": self.loss_count,
            "breakeven_count": self.breakeven_count,
            "win_rate": round(self.win_rate, 4),
            "total_pnl": round(self.total_pnl, 2),
            "total_commission": round(self.total_commission, 2),
            "net_pnl": round(self.net_pnl, 2),
            "avg_trade_pnl": round(self.avg_trade_pnl, 2),
            "avg_win": round(self.avg_win, 2),
            "avg_loss": round(self.avg_loss, 2),
            "largest_win": round(self.largest_win, 2),
            "largest_loss": round(self.largest_loss, 2),
            "avg_win_pct": round(self.avg_win_pct, 4),
            "avg_loss_pct": round(self.avg_loss_pct, 4),
            "profit_factor": round(self.profit_factor, 3) if self.profit_factor != float("inf") else "inf",
            "risk_reward_ratio": round(self.risk_reward_ratio, 3) if self.risk_reward_ratio != float("inf") else "inf",
            "expectancy": round(self.expectancy, 2),
            "max_drawdown": round(self.max_drawdown, 4),
            "current_drawdown": round(self.current_drawdown, 4),
            "max_drawdown_duration_hours": round(self.max_drawdown_duration_hours, 1),
            "sharpe_ratio": round(self.sharpe_ratio, 3) if math.isfinite(self.sharpe_ratio) else str(self.sharpe_ratio),
            "sortino_ratio": round(self.sortino_ratio, 3) if math.isfinite(self.sortino_ratio) else str(self.sortino_ratio),
            "calmar_ratio": round(self.calmar_ratio, 3) if math.isfinite(self.calmar_ratio) else str(self.calmar_ratio),
            "max_consecutive_wins": self.max_consecutive_wins,
            "max_consecutive_losses": self.max_consecutive_losses,
            "avg_trade_duration_minutes": round(self.avg_trade_duration_minutes, 1),
            "avg_slippage_bps": round(self.avg_slippage_bps, 2),
            "uptime_hours": round(self.uptime_hours, 1),
            "initial_balance": self.initial_balance,
            "current_equity": round(self._equity_curve[-1].equity, 2) if self._equity_curve else self.initial_balance,
        }

    def equity_curve_data(self) -> list[dict[str, Any]]:
        """Export equity curve for charting."""
        return [
            {
                "timestamp": s.timestamp.isoformat(),
                "equity": round(s.equity, 2),
                "balance": round(s.balance, 2),
                "unrealized_pnl": round(s.unrealized_pnl, 2),
            }
            for s in self._equity_curve
        ]

    def trades_data(self) -> list[dict[str, Any]]:
        """Export all trade records."""
        return [
            {
                "id": t.id,
                "symbol": t.symbol,
                "side": t.side,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "quantity": t.quantity,
                "pnl": round(t.pnl, 2),
                "pnl_pct": round(t.pnl_pct, 4),
                "entry_time": t.entry_time.isoformat(),
                "exit_time": t.exit_time.isoformat(),
                "duration_minutes": round(t.duration_minutes, 1),
                "commission": round(t.commission, 4),
                "slippage_bps": round(t.slippage_bps, 2),
                "reasoning": t.reasoning,
                "strategy": t.strategy,
                "tags": t.tags,
            }
            for t in self._trades
        ]
