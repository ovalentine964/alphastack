"""Simple backtester engine for AlphaStack strategies.

Replays historical data through the same pipeline used in live trading
and computes performance metrics: win rate, Sharpe ratio, max drawdown,
profit factor, etc.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np
from pydantic import BaseModel, Field

from alphastack.utils.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class BacktestTrade(BaseModel):
    """A single trade in the backtest."""
    trade_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    symbol: str = ""
    side: str = ""  # long | short
    entry_price: float = 0.0
    exit_price: float = 0.0
    quantity: float = 0.0
    entry_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    exit_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    pnl: float = 0.0
    pnl_pct: float = 0.0
    bars_held: int = 0


class BacktestResult(BaseModel):
    """Aggregated backtest performance metrics."""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    max_drawdown_amount: float = 0.0
    calmar_ratio: float = 0.0
    avg_bars_held: float = 0.0
    expectancy: float = 0.0
    initial_balance: float = 0.0
    final_balance: float = 0.0
    return_pct: float = 0.0
    equity_curve: list[float] = Field(default_factory=list)
    trades: list[BacktestTrade] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Backtester
# ---------------------------------------------------------------------------

class Backtester:
    """Simple event-driven backtester.

    Replays OHLCV bars through a signal generator function and tracks
    hypothetical trades with configurable risk parameters.

    Usage::

        def my_signal(bar, history):
            # return "long", "short", or None
            ...

        bt = Backtester(initial_balance=10_000)
        result = bt.run(ohlcv_data, signal_fn=my_signal)
        print(result.sharpe_ratio, result.max_drawdown_pct)
    """

    def __init__(
        self,
        initial_balance: float = 10_000.0,
        risk_per_trade_pct: float = 2.0,
        stop_loss_atr_mult: float = 1.5,
        take_profit_atr_mult: float = 3.0,
        commission_pct: float = 0.0,
        slippage_pct: float = 0.0,
        max_open_trades: int = 3,
    ) -> None:
        self.initial_balance = initial_balance
        self.risk_per_trade_pct = risk_per_trade_pct
        self.stop_loss_atr_mult = stop_loss_atr_mult
        self.take_profit_atr_mult = take_profit_atr_mult
        self.commission_pct = commission_pct
        self.slippage_pct = slippage_pct
        self.max_open_trades = max_open_trades

    def run(
        self,
        ohlcv: np.ndarray,
        signal_fn: Any,
        symbol: str = "BACKTEST",
    ) -> BacktestResult:
        """Run a backtest over OHLCV data.

        Args:
            ohlcv: Array of shape (n_bars, 5) — [open, high, low, close, volume].
            signal_fn: Callable(bar, history) → "long" | "short" | None.
            symbol: Symbol name for trade records.

        Returns:
            BacktestResult with all metrics.
        """
        if ohlcv.ndim != 2 or ohlcv.shape[1] < 5:
            raise ValueError(f"ohlcv must be (n_bars, 5), got {ohlcv.shape}")

        n_bars = len(ohlcv)
        balance = self.initial_balance
        equity_curve = [balance]
        trades: list[BacktestTrade] = []
        open_trades: list[dict[str, Any]] = []

        # Pre-compute ATR
        highs = ohlcv[:, 1]
        lows = ohlcv[:, 2]
        closes = ohlcv[:, 3]
        tr = np.maximum(
            highs - lows,
            np.maximum(
                np.abs(highs - np.roll(closes, 1)),
                np.abs(lows - np.roll(closes, 1)),
            ),
        )
        tr[0] = highs[0] - lows[0]
        atr = np.convolve(tr, np.ones(14) / 14, mode="same")

        for i in range(14, n_bars):
            bar = ohlcv[i]
            history = ohlcv[:i]
            opn, high, low, close = bar[0], bar[1], bar[2], bar[3]
            current_atr = atr[i]

            # --- check exits for open trades ---
            still_open: list[dict[str, Any]] = []
            for trade in open_trades:
                exited = False
                exit_price = close

                if trade["side"] == "long":
                    if low <= trade["stop_loss"]:
                        exit_price = trade["stop_loss"]
                        exited = True
                    elif high >= trade["take_profit"]:
                        exit_price = trade["take_profit"]
                        exited = True
                else:  # short
                    if high >= trade["stop_loss"]:
                        exit_price = trade["stop_loss"]
                        exited = True
                    elif low <= trade["take_profit"]:
                        exit_price = trade["take_profit"]
                        exited = True

                if exited:
                    # Apply slippage
                    slip = exit_price * self.slippage_pct / 100
                    if trade["side"] == "long":
                        exit_price -= slip
                    else:
                        exit_price += slip

                    pnl = self._calc_pnl(
                        trade["side"], trade["entry_price"], exit_price, trade["quantity"],
                    )
                    commission = abs(exit_price * trade["quantity"]) * self.commission_pct / 100
                    pnl -= commission
                    balance += pnl

                    trades.append(BacktestTrade(
                        symbol=symbol,
                        side=trade["side"],
                        entry_price=trade["entry_price"],
                        exit_price=exit_price,
                        quantity=trade["quantity"],
                        entry_time=trade["entry_time"],
                        exit_time=datetime.now(timezone.utc),
                        pnl=round(pnl, 2),
                        pnl_pct=round(pnl / self.initial_balance * 100, 4),
                        bars_held=i - trade["entry_bar"],
                    ))
                else:
                    still_open.append(trade)

            open_trades = still_open

            # --- check for new signals ---
            if len(open_trades) < self.max_open_trades:
                signal = signal_fn(bar, history)
                if signal in ("long", "short"):
                    # Position sizing
                    risk_amount = balance * self.risk_per_trade_pct / 100
                    sl_distance = current_atr * self.stop_loss_atr_mult
                    if sl_distance > 0:
                        quantity = risk_amount / sl_distance
                    else:
                        quantity = 0

                    if quantity > 0:
                        entry_price = close + (close * self.slippage_pct / 100 * (1 if signal == "long" else -1))
                        entry_commission = abs(entry_price * quantity) * self.commission_pct / 100
                        balance -= entry_commission

                        if signal == "long":
                            sl = entry_price - sl_distance
                            tp = entry_price + current_atr * self.take_profit_atr_mult
                        else:
                            sl = entry_price + sl_distance
                            tp = entry_price - current_atr * self.take_profit_atr_mult

                        open_trades.append({
                            "side": signal,
                            "entry_price": entry_price,
                            "stop_loss": sl,
                            "take_profit": tp,
                            "quantity": quantity,
                            "entry_time": datetime.now(timezone.utc),
                            "entry_bar": i,
                        })

            equity_curve.append(balance + sum(
                self._calc_pnl(t["side"], t["entry_price"], close, t["quantity"])
                for t in open_trades
            ))

        # Close any remaining open trades at last close
        for trade in open_trades:
            pnl = self._calc_pnl(trade["side"], trade["entry_price"], closes[-1], trade["quantity"])
            balance += pnl
            trades.append(BacktestTrade(
                symbol=symbol,
                side=trade["side"],
                entry_price=trade["entry_price"],
                exit_price=closes[-1],
                quantity=trade["quantity"],
                entry_time=trade["entry_time"],
                exit_time=datetime.now(timezone.utc),
                pnl=round(pnl, 2),
                pnl_pct=round(pnl / self.initial_balance * 100, 4),
                bars_held=n_bars - 1 - trade["entry_bar"],
            ))

        return self._compute_metrics(trades, equity_curve, balance)

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def _compute_metrics(
        self,
        trades: list[BacktestTrade],
        equity_curve: list[float],
        final_balance: float,
    ) -> BacktestResult:
        """Compute all backtest performance metrics."""
        result = BacktestResult(
            initial_balance=self.initial_balance,
            final_balance=round(final_balance, 2),
            return_pct=round((final_balance / self.initial_balance - 1) * 100, 2),
            trades=trades,
            equity_curve=[round(e, 2) for e in equity_curve],
        )

        if not trades:
            return result

        pnls = [t.pnl for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]

        result.total_trades = len(trades)
        result.winning_trades = len(wins)
        result.losing_trades = len(losses)
        result.win_rate = round(len(wins) / len(trades), 4)
        result.total_pnl = round(sum(pnls), 2)
        result.avg_win = round(np.mean(wins), 2) if wins else 0.0
        result.avg_loss = round(np.mean(losses), 2) if losses else 0.0

        # Profit factor
        gross_profit = sum(wins) if wins else 0
        gross_loss = abs(sum(losses)) if losses else 0
        result.profit_factor = round(
            gross_profit / gross_loss if gross_loss > 0 else float("inf"), 2,
        )

        # Expectancy
        result.expectancy = round(
            result.win_rate * result.avg_win + (1 - result.win_rate) * result.avg_loss, 2,
        )

        # Sharpe ratio (annualized, assuming daily bars)
        returns = np.diff(equity_curve) / np.array(equity_curve[:-1])
        if len(returns) > 1 and np.std(returns) > 0:
            result.sharpe_ratio = round(
                np.mean(returns) / np.std(returns) * np.sqrt(252), 2,
            )

        # Sortino ratio
        downside = returns[returns < 0]
        if len(downside) > 0 and np.std(downside) > 0:
            result.sortino_ratio = round(
                np.mean(returns) / np.std(downside) * np.sqrt(252), 2,
            )

        # Max drawdown
        peak = np.maximum.accumulate(equity_curve)
        drawdown = (np.array(equity_curve) - peak) / peak * 100
        result.max_drawdown_pct = round(float(np.min(drawdown)), 2)
        result.max_drawdown_amount = round(float(np.min(np.array(equity_curve) - peak)), 2)

        # Calmar ratio
        if result.max_drawdown_pct < 0:
            annual_return = result.return_pct  # simplified
            result.calmar_ratio = round(annual_return / abs(result.max_drawdown_pct), 2)

        result.avg_bars_held = round(np.mean([t.bars_held for t in trades]), 1)

        return result

    @staticmethod
    def _calc_pnl(side: str, entry: float, exit: float, quantity: float) -> float:
        if side == "long":
            return (exit - entry) * quantity
        return (entry - exit) * quantity
