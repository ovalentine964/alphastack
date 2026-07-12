"""Simple backtester — runs AlphaStack pipeline on historical OHLCV data and calculates performance metrics."""

from __future__ import annotations

import asyncio
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from alphastack.strategy.context import AlphaStackContext, Direction
from alphastack.strategy.pipeline import AlphaStackPipeline


# ---------------------------------------------------------------------------
# Trade record
# ---------------------------------------------------------------------------

@dataclass
class TradeRecord:
    """A single completed trade from the backtest."""
    entry_time: datetime
    exit_time: datetime | None = None
    symbol: str = ""
    direction: str = ""
    entry_price: float = 0.0
    exit_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: list[float] = field(default_factory=list)
    position_size: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    confluence_score: float = 0.0
    exit_reason: str = ""


# ---------------------------------------------------------------------------
# Performance metrics
# ---------------------------------------------------------------------------

@dataclass
class BacktestMetrics:
    """Aggregate performance metrics from a backtest run."""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    total_return_pct: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    avg_holding_bars: float = 0.0
    expectancy: float = 0.0
    calmar_ratio: float = 0.0


# ---------------------------------------------------------------------------
# Backtester
# ---------------------------------------------------------------------------

class Backtester:
    """Runs AlphaStack pipeline on historical OHLCV bars.

    Usage::

        bt = Backtester(initial_balance=10000.0)
        metrics = bt.run(ohlcv_data, symbol="EUR/USD", timeframe="1H")
    """

    def __init__(
        self,
        initial_balance: float = 10_000.0,
        risk_pct: float = 1.0,
        max_open_trades: int = 1,
        commission_pct: float = 0.0,
    ) -> None:
        self._initial_balance = initial_balance
        self._risk_pct = risk_pct
        self._max_open_trades = max_open_trades
        self._commission_pct = commission_pct

    def run(
        self,
        ohlcv: dict[str, list[float]],
        symbol: str = "EUR/USD",
        timeframe: str = "1H",
        start_index: int = 100,
    ) -> tuple[BacktestMetrics, list[TradeRecord]]:
        """Run backtest on OHLCV data. Returns metrics and trade list."""
        closes = ohlcv["closes"]
        n = len(closes)
        if n < start_index + 10:
            return BacktestMetrics(), []

        balance = self._initial_balance
        peak_balance = balance
        max_dd = 0.0
        trades: list[TradeRecord] = []
        equity_curve: list[float] = []
        open_trade: TradeRecord | None = None
        pipeline = AlphaStackPipeline(parallel=False)

        for i in range(start_index, n):
            # Build window of data up to bar i
            window = {
                "opens": ohlcv["opens"][:i + 1],
                "highs": ohlcv["highs"][:i + 1],
                "lows": ohlcv["lows"][:i + 1],
                "closes": ohlcv["closes"][:i + 1],
                "volumes": ohlcv["volumes"][:i + 1],
                "close": closes[i],
                "high_impact_events": [],
                "news_sentiment": 0.0,
                "volatility_index": 14.0,
                "atr_pips": self._estimate_atr(ohlcv, i),
                "pip_size": 0.0001,
                "spread_pips": 1.5,
                "account_balance": balance,
                "risk_pct": self._risk_pct,
                "pip_value": 10.0,
                "stop_multiplier": 1.5,
                "rsi_period": 14,
                "entry_price": closes[i],
                "timeframe_closes": {
                    "1h": closes[max(0, i - 30):i + 1],
                    "4h": closes[max(0, i - 30):i + 1],
                },
                "htf_closes": closes[max(0, i - 30):i + 1],
            }

            now = datetime(2025, 1, 1, tzinfo=timezone.utc)
            ctx = AlphaStackContext(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=now,
                market_data=window,
            )

            # Run pipeline synchronously
            result = asyncio.get_event_loop().run_until_complete(pipeline.run(ctx))

            # Check exit conditions for open trade
            if open_trade is not None:
                should_exit, exit_reason = self._check_exit(open_trade, closes[i], result)
                if should_exit:
                    open_trade.exit_time = now
                    open_trade.exit_price = closes[i]
                    open_trade.exit_reason = exit_reason
                    if open_trade.direction == "long":
                        open_trade.pnl = (open_trade.exit_price - open_trade.entry_price) * open_trade.position_size / open_trade.entry_price * balance
                    else:
                        open_trade.pnl = (open_trade.entry_price - open_trade.exit_price) * open_trade.position_size / open_trade.entry_price * balance
                    open_trade.pnl -= balance * open_trade.position_size * self._commission_pct / 100
                    open_trade.pnl_pct = (open_trade.pnl / balance) * 100
                    balance += open_trade.pnl
                    trades.append(open_trade)
                    open_trade = None

            # Check for new entry
            if open_trade is None and result.confluence.direction != Direction.NONE:
                direction = "long" if result.confluence.direction == Direction.LONG else "short"
                sl = result.stop_loss.price
                size = result.sizing.position_size

                if size > 0 and sl > 0:
                    open_trade = TradeRecord(
                        entry_time=now,
                        symbol=symbol,
                        direction=direction,
                        entry_price=closes[i],
                        stop_loss=sl,
                        take_profit=result.take_profit.levels,
                        position_size=size,
                        confluence_score=result.confluence.score,
                    )

            # Track equity
            equity = balance
            if open_trade and open_trade.direction == "long":
                equity += (closes[i] - open_trade.entry_price) * open_trade.position_size / open_trade.entry_price * balance
            elif open_trade and open_trade.direction == "short":
                equity += (open_trade.entry_price - closes[i]) * open_trade.position_size / open_trade.entry_price * balance
            equity_curve.append(equity)

            if equity > peak_balance:
                peak_balance = equity
            dd = peak_balance - equity
            if dd > max_dd:
                max_dd = dd

        # Close any remaining open trade
        if open_trade:
            open_trade.exit_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
            open_trade.exit_price = closes[-1]
            open_trade.exit_reason = "end_of_data"
            if open_trade.direction == "long":
                open_trade.pnl = (open_trade.exit_price - open_trade.entry_price) * open_trade.position_size / open_trade.entry_price * balance
            else:
                open_trade.pnl = (open_trade.entry_price - open_trade.exit_price) * open_trade.position_size / open_trade.entry_price * balance
            balance += open_trade.pnl
            trades.append(open_trade)

        metrics = self._compute_metrics(trades, equity_curve, max_dd)
        return metrics, trades

    def _check_exit(
        self,
        trade: TradeRecord,
        current_price: float,
        ctx: AlphaStackContext,
    ) -> tuple[bool, str]:
        """Check if an open trade should be closed."""
        # Stop loss hit
        if trade.direction == "long" and current_price <= trade.stop_loss:
            return True, "stop_loss"
        if trade.direction == "short" and current_price >= trade.stop_loss:
            return True, "stop_loss"

        # Take profit hit
        if trade.take_profit:
            tp = trade.take_profit[0]
            if trade.direction == "long" and current_price >= tp:
                return True, "take_profit"
            if trade.direction == "short" and current_price <= tp:
                return True, "take_profit"

        # Exit signal from pipeline
        if ctx.exit_signal.should_exit:
            return True, ctx.exit_signal.reason

        return False, ""

    def _estimate_atr(self, ohlcv: dict, index: int, period: int = 14) -> float:
        """Estimate ATR in pips."""
        start = max(0, index - period)
        highs = ohlcv["highs"][start:index + 1]
        lows = ohlcv["lows"][start:index + 1]
        closes = ohlcv["closes"][start:index + 1]
        if len(closes) < 2:
            return 50.0
        trs = []
        for i in range(1, len(closes)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
            trs.append(tr)
        atr = sum(trs) / len(trs) if trs else 0.001
        return atr / 0.0001  # convert to pips

    def _compute_metrics(
        self,
        trades: list[TradeRecord],
        equity_curve: list[float],
        max_dd: float,
    ) -> BacktestMetrics:
        """Compute aggregate performance metrics."""
        if not trades:
            return BacktestMetrics()

        pnls = [t.pnl for t in trades]
        winners = [p for p in pnls if p > 0]
        losers = [p for p in pnls if p <= 0]

        total_pnl = sum(pnls)
        win_rate = len(winners) / len(trades) if trades else 0.0
        avg_win = sum(winners) / len(winners) if winners else 0.0
        avg_loss = sum(losers) / len(losers) if losers else 0.0

        gross_profit = sum(winners)
        gross_loss = abs(sum(losers))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

        # Sharpe ratio (annualized, assuming daily returns)
        if len(pnls) > 1:
            mean_return = np.mean(pnls)
            std_return = np.std(pnls, ddof=1)
            sharpe = (mean_return / std_return) * math.sqrt(252) if std_return > 0 else 0.0
        else:
            sharpe = 0.0

        # Sortino ratio
        downside = [p for p in pnls if p < 0]
        if downside and len(pnls) > 1:
            downside_std = np.std(downside, ddof=1)
            sortino = (np.mean(pnls) / downside_std) * math.sqrt(252) if downside_std > 0 else 0.0
        else:
            sortino = 0.0

        # Max drawdown from equity curve
        max_dd_pct = 0.0
        if equity_curve:
            peak = equity_curve[0]
            for eq in equity_curve:
                if eq > peak:
                    peak = eq
                dd_pct = (peak - eq) / peak * 100 if peak > 0 else 0
                if dd_pct > max_dd_pct:
                    max_dd_pct = dd_pct

        total_return_pct = (total_pnl / self._initial_balance) * 100

        # Expectancy
        expectancy = (win_rate * avg_win + (1 - win_rate) * avg_loss) if trades else 0.0

        # Calmar ratio
        calmar = total_return_pct / max_dd_pct if max_dd_pct > 0 else 0.0

        return BacktestMetrics(
            total_trades=len(trades),
            winning_trades=len(winners),
            losing_trades=len(losers),
            win_rate=round(win_rate, 4),
            total_pnl=round(total_pnl, 2),
            total_return_pct=round(total_return_pct, 2),
            avg_win=round(avg_win, 2),
            avg_loss=round(avg_loss, 2),
            profit_factor=round(profit_factor, 2),
            max_drawdown=round(max_dd, 2),
            max_drawdown_pct=round(max_dd_pct, 2),
            sharpe_ratio=round(sharpe, 2),
            sortino_ratio=round(sortino, 2),
            expectancy=round(expectancy, 2),
            calmar_ratio=round(calmar, 2),
        )
