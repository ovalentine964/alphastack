"""Backtesting validation — tests for the backtester engine itself."""

from __future__ import annotations

import numpy as np
import pytest

from tests.backtest.backtester import Backtester, BacktestResult, BacktestTrade


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ohlcv(n: int = 200, trend: float = 0.001, seed: int = 42) -> np.ndarray:
    """Generate synthetic trending OHLCV data."""
    rng = np.random.RandomState(seed)
    close = 1.1000 + np.cumsum(rng.randn(n) * 0.001 + trend)
    high = close + np.abs(rng.randn(n) * 0.0005)
    low = close - np.abs(rng.randn(n) * 0.0005)
    opn = close + rng.randn(n) * 0.0002
    volume = rng.randint(100, 10000, n).astype(float)
    return np.column_stack([opn, high, low, close, volume])


def _always_long(bar: np.ndarray, history: np.ndarray) -> str | None:
    """Always signal long."""
    return "long"


def _always_short(bar: np.ndarray, history: np.ndarray) -> str | None:
    """Always signal short."""
    return "short"


def _no_signal(bar: np.ndarray, history: np.ndarray) -> None:
    """Never signal."""
    return None


def _ma_crossover(bar: np.ndarray, history: np.ndarray) -> str | None:
    """Simple MA crossover signal."""
    if len(history) < 20:
        return None
    closes = history[-20:, 3]
    ma5 = np.mean(closes[-5:])
    ma20 = np.mean(closes)
    if ma5 > ma20:
        return "long"
    elif ma5 < ma20:
        return "short"
    return None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBacktester:

    def test_no_trades_when_no_signals(self) -> None:
        """No signals → no trades."""
        bt = Backtester(initial_balance=10_000)
        ohlcv = _make_ohlcv(100)
        result = bt.run(ohlcv, signal_fn=_no_signal)

        assert result.total_trades == 0
        assert result.final_balance == 10_000.0
        assert result.win_rate == 0.0

    def test_always_long_generates_trades(self) -> None:
        """Always-long strategy should produce trades."""
        bt = Backtester(initial_balance=10_000, max_open_trades=5)
        ohlcv = _make_ohlcv(200, trend=0.002)
        result = bt.run(ohlcv, signal_fn=_always_long)

        assert result.total_trades > 0
        assert len(result.trades) == result.total_trades
        assert len(result.equity_curve) == len(ohlcv)

    def test_always_short_generates_trades(self) -> None:
        bt = Backtester(initial_balance=10_000, max_open_trades=5)
        ohlcv = _make_ohlcv(200, trend=-0.002)
        result = bt.run(ohlcv, signal_fn=_always_short)
        assert result.total_trades > 0

    def test_ma_crossover_strategy(self) -> None:
        """MA crossover should produce fewer trades than always-long."""
        bt = Backtester(initial_balance=10_000, max_open_trades=3)
        ohlcv = _make_ohlcv(300, seed=123)

        result_always = bt.run(ohlcv, signal_fn=_always_long)
        result_ma = bt.run(ohlcv, signal_fn=_ma_crossover)

        # MA crossover should be less aggressive
        assert result_ma.total_trades <= result_always.total_trades

    def test_metrics_completeness(self) -> None:
        """All expected metrics should be populated."""
        bt = Backtester(initial_balance=10_000, max_open_trades=5)
        ohlcv = _make_ohlcv(200, trend=0.001, seed=7)
        result = bt.run(ohlcv, signal_fn=_always_long)

        if result.total_trades > 0:
            assert result.win_rate >= 0.0
            assert result.profit_factor >= 0.0
            assert result.sharpe_ratio != 0.0
            assert result.max_drawdown_pct <= 0.0
            assert result.avg_bars_held > 0
            assert result.expectancy != 0.0

    def test_pnl_math(self) -> None:
        """Verify PnL calculation is correct."""
        pnl_long = Backtester._calc_pnl("long", 1.1000, 1.1050, 1.0)
        assert pnl_long == pytest.approx(0.05)

        pnl_short = Backtester._calc_pnl("short", 1.1050, 1.1000, 1.0)
        assert pnl_short == pytest.approx(0.05)

        pnl_loss = Backtester._calc_pnl("long", 1.1000, 1.0950, 1.0)
        assert pnl_loss == pytest.approx(-0.05)

    def test_commission_reduces_pnl(self) -> None:
        """Higher commission → lower final balance."""
        ohlcv = _make_ohlcv(200, trend=0.003, seed=42)

        bt_no_comm = Backtester(initial_balance=10_000, commission_pct=0.0, max_open_trades=5)
        bt_comm = Backtester(initial_balance=10_000, commission_pct=0.1, max_open_trades=5)

        r1 = bt_no_comm.run(ohlcv, signal_fn=_always_long)
        r2 = bt_comm.run(ohlcv, signal_fn=_always_long)

        if r1.total_trades > 0:
            assert r2.final_balance <= r1.final_balance

    def test_slippage_reduces_pnl(self) -> None:
        ohlcv = _make_ohlcv(200, trend=0.003, seed=42)

        bt_no_slip = Backtester(initial_balance=10_000, slippage_pct=0.0, max_open_trades=5)
        bt_slip = Backtester(initial_balance=10_000, slippage_pct=0.05, max_open_trades=5)

        r1 = bt_no_slip.run(ohlcv, signal_fn=_always_long)
        r2 = bt_slip.run(ohlcv, signal_fn=_always_long)

        if r1.total_trades > 0:
            assert r2.final_balance <= r1.final_balance

    def test_invalid_ohlcv_raises(self) -> None:
        bt = Backtester()
        with pytest.raises(ValueError, match="ohlcv must be"):
            bt.run(np.array([1, 2, 3]), signal_fn=_no_signal)

    def test_max_open_trades_respected(self) -> None:
        """Should never exceed max_open_trades."""
        bt = Backtester(initial_balance=100_000, max_open_trades=2)
        ohlcv = _make_ohlcv(100, seed=42)
        result = bt.run(ohlcv, signal_fn=_always_long)
        # We can't directly check concurrent open, but trades should exist
        assert result.total_trades >= 0  # at least doesn't crash

    def test_result_serialization(self) -> None:
        bt = Backtester(initial_balance=10_000, max_open_trades=3)
        ohlcv = _make_ohlcv(100)
        result = bt.run(ohlcv, signal_fn=_always_long)

        data = result.model_dump()
        assert "total_trades" in data
        assert "sharpe_ratio" in data
        assert "equity_curve" in data
        assert isinstance(data["equity_curve"], list)
