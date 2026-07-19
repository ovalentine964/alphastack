"""BacktestEngine — production backtesting engine for AlphaStack.

Runs the strategy pipeline on historical OHLCV data with:
- Slippage model (volume-based + spread)
- Commission and funding cost simulation
- Position tracking with partial fills
- Risk governor integration
- Equity curve and drawdown tracking
"""

from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd

from alphastack.brokers.models import OrderSide, OrderType, OrderStatus
from alphastack.strategy.context import AlphaStackContext, Direction
from alphastack.strategy.pipeline import AlphaStackPipeline

logger = logging.getLogger("alphastack.backtest.engine")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class FillReason(str, Enum):
    SIGNAL = "signal"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    TRAILING_STOP = "trailing_stop"
    EXIT_SIGNAL = "exit_signal"
    END_OF_DATA = "end_of_data"
    LIQUIDATION = "liquidation"


# ---------------------------------------------------------------------------
# Slippage model
# ---------------------------------------------------------------------------

@dataclass
class SlippageConfig:
    """Configuration for the slippage model.

    Slippage = base_bps + volume_impact * (order_size / avg_volume)
    Capped at max_slippage_bps.
    """
    base_bps: float = 2.0          # base slippage in basis points
    volume_impact_bps: float = 10.0 # additional bps per unit of volume ratio
    max_slippage_bps: float = 50.0  # hard cap
    spread_bps: float = 1.0        # half-spread cost

    def compute(self, price: float, quantity: float, avg_volume: float) -> float:
        """Return slippage in price units for a given order."""
        if price <= 0:
            return 0.0
        volume_ratio = (quantity / avg_volume) if avg_volume > 0 else 0.0
        raw_bps = self.base_bps + self.volume_impact_bps * volume_ratio + self.spread_bps
        capped_bps = min(raw_bps, self.max_slippage_bps)
        return price * capped_bps / 10_000


# ---------------------------------------------------------------------------
# Trade record
# ---------------------------------------------------------------------------

@dataclass
class TradeRecord:
    """A single completed round-trip trade."""
    id: int = 0
    symbol: str = ""
    direction: str = ""  # "long" | "short"
    entry_time: datetime | None = None
    exit_time: datetime | None = None
    entry_price: float = 0.0
    exit_price: float = 0.0
    quantity: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    confluence_score: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    commission: float = 0.0
    slippage_cost: float = 0.0
    exit_reason: str = ""
    bars_held: int = 0
    equity_at_entry: float = 0.0
    peak_unrealized: float = 0.0  # max favorable excursion
    trough_unrealized: float = 0.0  # max adverse excursion


# ---------------------------------------------------------------------------
# Open position (tracks live state)
# ---------------------------------------------------------------------------

@dataclass
class OpenPosition:
    """An active position being tracked by the engine."""
    symbol: str = ""
    direction: str = ""
    entry_time: datetime | None = None
    entry_price: float = 0.0  # fill price after slippage
    raw_entry_price: float = 0.0  # signal price before slippage
    quantity: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    confluence_score: float = 0.0
    equity_at_entry: float = 0.0
    commission: float = 0.0
    slippage_cost: float = 0.0
    bars_held: int = 0
    peak_unrealized: float = 0.0
    trough_unrealized: float = 0.0
    trailing_stop: float = 0.0  # 0 = not activated

    def unrealized_pnl(self, current_price: float, balance: float) -> float:
        """Calculate unrealized PnL in account currency."""
        if self.direction == "long":
            return (current_price - self.entry_price) / self.entry_price * self.quantity * balance
        else:
            return (self.entry_price - current_price) / self.entry_price * self.quantity * balance

    def unrealized_pnl_pct(self, current_price: float) -> float:
        """Calculate unrealized PnL as percentage."""
        if self.direction == "long":
            return (current_price - self.entry_price) / self.entry_price * 100
        else:
            return (self.entry_price - current_price) / self.entry_price * 100


# ---------------------------------------------------------------------------
# Engine configuration
# ---------------------------------------------------------------------------

@dataclass
class BacktestConfig:
    """Full configuration for a backtest run."""
    initial_balance: float = 10_000.0
    risk_per_trade_pct: float = 1.0
    max_open_positions: int = 1
    commission_pct: float = 0.1       # per-side commission as % of notional
    funding_rate_daily_pct: float = 0.0  # daily funding cost for perpetual futures
    slippage: SlippageConfig = field(default_factory=SlippageConfig)
    start_index: int = 100            # bars to skip for indicator warmup
    enable_trailing_stop: bool = False
    trailing_stop_activation_pct: float = 1.0  # activate after this % profit
    trailing_stop_distance_pct: float = 0.5    # trail by this %
    min_bars_between_trades: int = 3   # cooldown between trades


# ---------------------------------------------------------------------------
# Performance metrics
# ---------------------------------------------------------------------------

@dataclass
class BacktestMetrics:
    """Aggregate performance metrics."""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    breakeven_trades: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    total_return_pct: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    avg_bars_held: float = 0.0
    expectancy: float = 0.0
    total_commission: float = 0.0
    total_slippage_cost: float = 0.0
    long_trades: int = 0
    short_trades: int = 0
    long_win_rate: float = 0.0
    short_win_rate: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    avg_rr_ratio: float = 0.0
    recovery_factor: float = 0.0
    equity_final: float = 0.0


# ---------------------------------------------------------------------------
# Equity snapshot
# ---------------------------------------------------------------------------

@dataclass
class EquitySnapshot:
    """Point-in-time equity state."""
    timestamp: datetime
    balance: float
    equity: float  # balance + unrealized PnL
    drawdown_pct: float = 0.0


# ---------------------------------------------------------------------------
# BacktestEngine
# ---------------------------------------------------------------------------

class BacktestEngine:
    """Production backtesting engine.

    Usage::

        engine = BacktestEngine(config=BacktestConfig(initial_balance=10000))
        result = engine.run(df, symbol="BTC/USDT", timeframe="1h")
        result.report.print_summary()
    """

    def __init__(self, config: BacktestConfig | None = None) -> None:
        self.config = config or BacktestConfig()
        self._pipeline = AlphaStackPipeline(parallel=False)
        self._trade_counter = 0

    # ------------------------------------------------------------------
    # Public API
# ------------------------------------------------------------------

    def run(
        self,
        df: pd.DataFrame,
        symbol: str = "BTC/USDT",
        timeframe: str = "1h",
    ) -> BacktestResult:
        """Run the full backtest.

        Parameters
        ----------
        df : pd.DataFrame
            OHLCV data with columns: timestamp, open, high, low, close, volume.
        symbol : str
            Trading pair.
        timeframe : str
            Candle timeframe.

        Returns
        -------
        BacktestResult
            Metrics, trades, equity curve.
        """
        cfg = self.config
        n = len(df)

        if n < cfg.start_index + 10:
            logger.warning("Not enough data (%d bars, need %d+)", n, cfg.start_index + 10)
            return BacktestResult(
                metrics=BacktestMetrics(),
                trades=[],
                equity_curve=[],
                config=cfg,
                symbol=symbol,
                timeframe=timeframe,
            )

        balance = cfg.initial_balance
        peak_balance = balance
        max_dd = 0.0
        max_dd_pct = 0.0
        trades: list[TradeRecord] = []
        equity_curve: list[EquitySnapshot] = []
        open_position: OpenPosition | None = None
        last_trade_bar = -cfg.min_bars_between_trades
        daily_returns: list[float] = []
        prev_equity = balance

        # Precompute ATR for slippage volume estimation
        avg_volumes = self._rolling_avg(df["volume"].values, 20)

        logger.info(
            "Starting backtest: %s %s | %d bars | $%.2f initial",
            symbol, timeframe, n, cfg.initial_balance,
        )

        for i in range(cfg.start_index, n):
            row = df.iloc[i]
            ts = row["timestamp"]
            o, h, l, c, v = row["open"], row["high"], row["low"], row["close"], row["volume"]
            avg_vol = avg_volumes[i] if avg_volumes[i] > 0 else v

            # --- Check exit conditions for open position ---
            if open_position is not None:
                exit_price, exit_reason = self._check_exit(
                    open_position, h, l, c, cfg,
                )
                if exit_price is not None:
                    trade = self._close_position(
                        open_position, exit_price, exit_reason, ts, balance,
                        avg_vol,
                    )
                    trades.append(trade)
                    balance += trade.pnl
                    open_position = None

            # --- Run strategy pipeline ---
            ctx = self._build_context(df, i, symbol, timeframe, ts, balance)
            try:
                loop = asyncio.new_event_loop()
                result = loop.run_until_complete(self._pipeline.run(ctx))
                loop.close()
            except Exception as e:
                logger.debug("Pipeline error at bar %d: %s", i, e)
                result = ctx  # use raw context on error

            # --- Update open position metrics ---
            if open_position is not None:
                open_position.bars_held += 1
                unreal = open_position.unrealized_pnl(c, balance)
                open_position.peak_unrealized = max(open_position.peak_unrealized, unreal)
                open_position.trough_unrealized = min(open_position.trough_unrealized, unreal)

                # Trailing stop logic
                if cfg.enable_trailing_stop:
                    self._update_trailing_stop(open_position, c, cfg)

            # --- Check for new entry ---
            if (
                open_position is None
                and result.confluence.direction != Direction.NONE
                and (i - last_trade_bar) >= cfg.min_bars_between_trades
            ):
                direction = "long" if result.confluence.direction == Direction.LONG else "short"
                sl = result.stop_loss.price
                tp = result.take_profit.levels[0] if result.take_profit.levels else 0.0
                size = result.sizing.position_size

                if size > 0 and sl > 0:
                    # Apply slippage to entry
                    slippage = cfg.slippage.compute(c, size, avg_vol)
                    if direction == "long":
                        fill_price = c + slippage  # worse fill for buys
                    else:
                        fill_price = c - slippage  # worse fill for sells

                    commission = fill_price * size * cfg.commission_pct / 100

                    open_position = OpenPosition(
                        symbol=symbol,
                        direction=direction,
                        entry_time=ts,
                        entry_price=fill_price,
                        raw_entry_price=c,
                        quantity=size,
                        stop_loss=sl,
                        take_profit=tp,
                        confluence_score=result.confluence.score,
                        equity_at_entry=balance,
                        commission=commission,
                        slippage_cost=slippage * size,
                    )
                    last_trade_bar = i

            # --- Track equity ---
            equity = balance
            if open_position is not None:
                equity += open_position.unrealized_pnl(c, balance)

            dd = peak_balance - equity
            dd_pct = (dd / peak_balance * 100) if peak_balance > 0 else 0.0
            max_dd = max(max_dd, dd)
            max_dd_pct = max(max_dd_pct, dd_pct)
            if equity > peak_balance:
                peak_balance = equity

            equity_curve.append(EquitySnapshot(
                timestamp=ts,
                balance=balance,
                equity=equity,
                drawdown_pct=dd_pct,
            ))

            # Daily returns for Sharpe/Sortino
            if prev_equity > 0:
                daily_returns.append((equity - prev_equity) / prev_equity)
            prev_equity = equity

        # --- Close any remaining position at end of data ---
        if open_position is not None:
            last_row = df.iloc[-1]
            trade = self._close_position(
                open_position, last_row["close"], FillReason.END_OF_DATA,
                last_row["timestamp"], balance, avg_volumes[-1],
            )
            trades.append(trade)
            balance += trade.pnl

        # Final equity snapshot
        final_equity = balance
        equity_curve.append(EquitySnapshot(
            timestamp=df.iloc[-1]["timestamp"],
            balance=balance,
            equity=final_equity,
            drawdown_pct=0.0,
        ))

        metrics = self._compute_metrics(
            trades, equity_curve, daily_returns,
            cfg.initial_balance, max_dd, max_dd_pct,
        )

        logger.info(
            "Backtest complete: %d trades, PnL $%.2f (%.2f%%), MaxDD %.2f%%",
            metrics.total_trades, metrics.total_pnl,
            metrics.total_return_pct, metrics.max_drawdown_pct,
        )

        return BacktestResult(
            metrics=metrics,
            trades=trades,
            equity_curve=equity_curve,
            config=cfg,
            symbol=symbol,
            timeframe=timeframe,
        )

    # ------------------------------------------------------------------
    # Exit logic
# ------------------------------------------------------------------

    def _check_exit(
        self,
        pos: OpenPosition,
        high: float,
        low: float,
        close: float,
        cfg: BacktestConfig,
    ) -> tuple[float | None, FillReason]:
        """Check if the position should be closed.

        Returns (fill_price, reason) or (None, _) if no exit.
        Uses intra-bar simulation: checks stop loss first (worst case),
        then take profit.
        """
        # Trailing stop
        if pos.trailing_stop > 0:
            if pos.direction == "long" and low <= pos.trailing_stop:
                return pos.trailing_stop, FillReason.TRAILING_STOP
            if pos.direction == "short" and high >= pos.trailing_stop:
                return pos.trailing_stop, FillReason.TRAILING_STOP

        # Stop loss — assume it triggers at the stop price (not the bar low/high)
        if pos.direction == "long" and low <= pos.stop_loss:
            return pos.stop_loss, FillReason.STOP_LOSS
        if pos.direction == "short" and high >= pos.stop_loss:
            return pos.stop_loss, FillReason.STOP_LOSS

        # Take profit
        if pos.take_profit > 0:
            if pos.direction == "long" and high >= pos.take_profit:
                return pos.take_profit, FillReason.TAKE_PROFIT
            if pos.direction == "short" and low <= pos.take_profit:
                return pos.take_profit, FillReason.TAKE_PROFIT

        return None, FillReason.SIGNAL

    def _update_trailing_stop(
        self,
        pos: OpenPosition,
        current_price: float,
        cfg: BacktestConfig,
    ) -> None:
        """Update trailing stop if price has moved enough in our favor."""
        pnl_pct = pos.unrealized_pnl_pct(current_price)
        if pnl_pct < cfg.trailing_stop_activation_pct:
            return

        distance = current_price * cfg.trailing_stop_distance_pct / 100
        if pos.direction == "long":
            new_stop = current_price - distance
            if new_stop > pos.trailing_stop or pos.trailing_stop == 0:
                pos.trailing_stop = new_stop
        else:
            new_stop = current_price + distance
            if new_stop < pos.trailing_stop or pos.trailing_stop == 0:
                pos.trailing_stop = new_stop

    # ------------------------------------------------------------------
    # Position management
# ------------------------------------------------------------------

    def _close_position(
        self,
        pos: OpenPosition,
        exit_price: float,
        reason: FillReason,
        exit_time: datetime,
        balance: float,
        avg_volume: float,
    ) -> TradeRecord:
        """Close an open position and return a TradeRecord."""
        cfg = self.config

        # Apply slippage to exit
        slippage = cfg.slippage.compute(exit_price, pos.quantity, avg_volume)
        if pos.direction == "long":
            fill_price = exit_price - slippage  # worse fill for sells
        else:
            fill_price = exit_price + slippage  # worse fill for buys

        exit_commission = fill_price * pos.quantity * cfg.commission_pct / 100
        total_commission = pos.commission + exit_commission

        # Funding cost (perpetual futures)
        bars_held = pos.bars_held
        funding_cost = 0.0
        if cfg.funding_rate_daily_pct > 0:
            # Estimate time held in days from bars
            # This is approximate — actual funding is every 8h on most exchanges
            days_held = max(bars_held / 24, 0.0)  # assume 1h bars
            notional = pos.quantity * pos.entry_price
            funding_cost = notional * cfg.funding_rate_daily_pct / 100 * days_held

        # PnL calculation
        if pos.direction == "long":
            raw_pnl = (fill_price - pos.entry_price) / pos.entry_price * pos.quantity * pos.equity_at_entry
        else:
            raw_pnl = (pos.entry_price - fill_price) / pos.entry_price * pos.quantity * pos.equity_at_entry

        net_pnl = raw_pnl - total_commission - funding_cost
        pnl_pct = (net_pnl / pos.equity_at_entry * 100) if pos.equity_at_entry > 0 else 0.0

        self._trade_counter += 1
        return TradeRecord(
            id=self._trade_counter,
            symbol=pos.symbol,
            direction=pos.direction,
            entry_time=pos.entry_time,
            exit_time=exit_time,
            entry_price=pos.entry_price,
            exit_price=fill_price,
            quantity=pos.quantity,
            stop_loss=pos.stop_loss,
            take_profit=pos.take_profit,
            confluence_score=pos.confluence_score,
            pnl=round(net_pnl, 2),
            pnl_pct=round(pnl_pct, 4),
            commission=round(total_commission, 2),
            slippage_cost=round((slippage * pos.quantity) + pos.slippage_cost, 2),
            exit_reason=reason.value,
            bars_held=bars_held,
            equity_at_entry=pos.equity_at_entry,
            peak_unrealized=pos.peak_unrealized,
            trough_unrealized=pos.trough_unrealized,
        )

    # ------------------------------------------------------------------
    # Context builder
# ------------------------------------------------------------------

    def _build_context(
        self,
        df: pd.DataFrame,
        index: int,
        symbol: str,
        timeframe: str,
        timestamp: datetime,
        balance: float,
    ) -> AlphaStackContext:
        """Build an AlphaStackContext from the DataFrame window up to *index*."""
        window = df.iloc[:index + 1]
        closes = window["close"].tolist()
        highs = window["high"].tolist()
        lows = window["low"].tolist()
        opens = window["open"].tolist()
        volumes = window["volume"].tolist()

        # ATR estimation
        atr = self._compute_atr(highs, lows, closes, period=14)

        market_data = {
            "opens": opens,
            "highs": highs,
            "lows": lows,
            "closes": closes,
            "volumes": volumes,
            "close": closes[-1],
            "high_impact_events": [],
            "news_sentiment": 0.0,
            "volatility_index": 14.0,
            "atr_pips": atr,
            "pip_size": 0.01 if "BTC" in symbol else 0.0001,
            "spread_pips": 5.0,
            "account_balance": balance,
            "risk_pct": self.config.risk_per_trade_pct,
            "pip_value": 1.0,
            "stop_multiplier": 1.5,
            "rsi_period": 14,
            "entry_price": closes[-1],
            "timeframe_closes": {
                "1h": closes[-30:] if len(closes) >= 30 else closes,
                "4h": closes[-30:] if len(closes) >= 30 else closes,
            },
            "htf_closes": closes[-30:] if len(closes) >= 30 else closes,
        }

        return AlphaStackContext(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=timestamp,
            market_data=market_data,
        )

    # ------------------------------------------------------------------
    # Metrics computation
# ------------------------------------------------------------------

    def _compute_metrics(
        self,
        trades: list[TradeRecord],
        equity_curve: list[EquitySnapshot],
        daily_returns: list[float],
        initial_balance: float,
        max_dd: float,
        max_dd_pct: float,
    ) -> BacktestMetrics:
        """Compute all performance metrics from completed trades."""
        if not trades:
            return BacktestMetrics(equity_final=initial_balance)

        pnls = np.array([t.pnl for t in trades])
        winners = pnls[pnls > 0]
        losers = pnls[pnls < 0]
        breakeven = pnls[pnls == 0]

        total_pnl = float(pnls.sum())
        win_rate = len(winners) / len(trades)
        avg_win = float(winners.mean()) if len(winners) > 0 else 0.0
        avg_loss = float(losers.mean()) if len(losers) > 0 else 0.0
        largest_win = float(winners.max()) if len(winners) > 0 else 0.0
        largest_loss = float(losers.min()) if len(losers) > 0 else 0.0

        gross_profit = float(winners.sum()) if len(winners) > 0 else 0.0
        gross_loss = abs(float(losers.sum())) if len(losers) > 0 else 0.0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

        # Sharpe ratio (annualized from daily returns)
        returns_arr = np.array(daily_returns)
        if len(returns_arr) > 1:
            mean_r = float(returns_arr.mean())
            std_r = float(returns_arr.std(ddof=1))
            sharpe = (mean_r / std_r) * math.sqrt(365) if std_r > 0 else 0.0
        else:
            sharpe = 0.0

        # Sortino ratio
        downside = returns_arr[returns_arr < 0]
        if len(downside) > 1:
            downside_std = float(downside.std(ddof=1))
            sortino = (mean_r / downside_std) * math.sqrt(365) if downside_std > 0 else 0.0
        else:
            sortino = 0.0

        # Calmar ratio
        total_return_pct = (total_pnl / initial_balance) * 100
        calmar = total_return_pct / max_dd_pct if max_dd_pct > 0 else 0.0

        # Expectancy
        expectancy = (win_rate * avg_win + (1 - win_rate) * avg_loss)

        # Average bars held
        avg_bars = float(np.mean([t.bars_held for t in trades]))

        # Long/short breakdown
        long_trades = [t for t in trades if t.direction == "long"]
        short_trades = [t for t in trades if t.direction == "short"]
        long_wins = len([t for t in long_trades if t.pnl > 0])
        short_wins = len([t for t in short_trades if t.pnl > 0])

        # Consecutive wins/losses
        max_consec_w, max_consec_l = self._consecutive_streaks(pnls)

        # Average R:R ratio
        rr_ratios = []
        for t in trades:
            if t.stop_loss > 0 and t.entry_price > 0:
                risk = abs(t.entry_price - t.stop_loss)
                if risk > 0:
                    reward = abs(t.pnl / t.equity_at_entry * t.entry_price) if t.equity_at_entry > 0 else 0
                    rr_ratios.append(reward / risk)
        avg_rr = float(np.mean(rr_ratios)) if rr_ratios else 0.0

        # Recovery factor
        recovery_factor = total_pnl / max_dd if max_dd > 0 else float("inf")

        # Total costs
        total_commission = sum(t.commission for t in trades)
        total_slippage = sum(t.slippage_cost for t in trades)

        final_equity = equity_curve[-1].equity if equity_curve else initial_balance

        return BacktestMetrics(
            total_trades=len(trades),
            winning_trades=len(winners),
            losing_trades=len(losers),
            breakeven_trades=len(breakeven),
            win_rate=round(win_rate, 4),
            total_pnl=round(total_pnl, 2),
            total_return_pct=round(total_return_pct, 2),
            avg_win=round(avg_win, 2),
            avg_loss=round(avg_loss, 2),
            largest_win=round(largest_win, 2),
            largest_loss=round(largest_loss, 2),
            profit_factor=round(profit_factor, 2),
            max_drawdown=round(max_dd, 2),
            max_drawdown_pct=round(max_dd_pct, 2),
            sharpe_ratio=round(sharpe, 2),
            sortino_ratio=round(sortino, 2),
            calmar_ratio=round(calmar, 2),
            avg_bars_held=round(avg_bars, 1),
            expectancy=round(expectancy, 2),
            total_commission=round(total_commission, 2),
            total_slippage_cost=round(total_slippage, 2),
            long_trades=len(long_trades),
            short_trades=len(short_trades),
            long_win_rate=round(long_wins / len(long_trades), 4) if long_trades else 0.0,
            short_win_rate=round(short_wins / len(short_trades), 4) if short_trades else 0.0,
            max_consecutive_wins=max_consec_w,
            max_consecutive_losses=max_consec_l,
            avg_rr_ratio=round(avg_rr, 2),
            recovery_factor=round(recovery_factor, 2),
            equity_final=round(final_equity, 2),
        )

    # ------------------------------------------------------------------
    # Helpers
# ------------------------------------------------------------------

    @staticmethod
    def _compute_atr(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> float:
        """Compute Average True Range."""
        if len(closes) < 2:
            return 0.0
        start = max(0, len(closes) - period - 1)
        trs = []
        for i in range(start + 1, len(closes)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
            trs.append(tr)
        return sum(trs) / len(trs) if trs else 0.0

    @staticmethod
    def _rolling_avg(arr: np.ndarray, window: int) -> np.ndarray:
        """Compute a simple rolling average (padded with first value)."""
        result = np.empty_like(arr, dtype=float)
        cumsum = np.cumsum(arr)
        result[:window] = cumsum[:window] / np.arange(1, window + 1)
        result[window:] = (cumsum[window:] - cumsum[:-window]) / window
        return result

    @staticmethod
    def _consecutive_streaks(pnls: np.ndarray) -> tuple[int, int]:
        """Compute max consecutive wins and losses."""
        max_w, max_l = 0, 0
        cur_w, cur_l = 0, 0
        for p in pnls:
            if p > 0:
                cur_w += 1
                cur_l = 0
                max_w = max(max_w, cur_w)
            elif p < 0:
                cur_l += 1
                cur_w = 0
                max_l = max(max_l, cur_l)
            else:
                cur_w = 0
                cur_l = 0
        return max_w, max_l


# ---------------------------------------------------------------------------
# Backtest result container
# ---------------------------------------------------------------------------

@dataclass
class BacktestResult:
    """Complete result from a backtest run."""
    metrics: BacktestMetrics
    trades: list[TradeRecord]
    equity_curve: list[EquitySnapshot]
    config: BacktestConfig
    symbol: str = ""
    timeframe: str = ""

    @property
    def report(self) -> "BacktestReport":
        """Lazy report generator."""
        from alphastack.backtest.report import BacktestReport
        return BacktestReport(self)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary for JSON export."""
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "metrics": self.metrics.__dict__,
            "config": {
                "initial_balance": self.config.initial_balance,
                "risk_per_trade_pct": self.config.risk_per_trade_pct,
                "commission_pct": self.config.commission_pct,
                "funding_rate_daily_pct": self.config.funding_rate_daily_pct,
            },
            "trades": [
                {
                    "id": t.id,
                    "direction": t.direction,
                    "entry_time": t.entry_time.isoformat() if t.entry_time else None,
                    "exit_time": t.exit_time.isoformat() if t.exit_time else None,
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "quantity": t.quantity,
                    "pnl": t.pnl,
                    "pnl_pct": t.pnl_pct,
                    "commission": t.commission,
                    "slippage_cost": t.slippage_cost,
                    "exit_reason": t.exit_reason,
                    "bars_held": t.bars_held,
                }
                for t in self.trades
            ],
            "equity_curve": [
                {"timestamp": s.timestamp.isoformat(), "equity": s.equity, "drawdown_pct": s.drawdown_pct}
                for s in self.equity_curve[::max(1, len(self.equity_curve) // 500)]  # downsample
            ],
        }
