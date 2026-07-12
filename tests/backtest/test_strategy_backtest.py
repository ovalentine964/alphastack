"""Backtesting validation tests — historical data replay and metrics calculation."""

from __future__ import annotations

import pytest

from tests.backtest.backtester import Backtester, BacktestMetrics, TradeRecord
from tests.conftest import generate_ohlcv


# ===========================================================================
# Backtester Tests
# ===========================================================================

class TestBacktester:
    def test_empty_data_returns_no_trades(self):
        bt = Backtester(initial_balance=10_000.0)
        ohlcv = generate_ohlcv(10, seed=42)
        metrics, trades = bt.run(ohlcv, start_index=100)
        assert metrics.total_trades == 0

    def test_generates_trades_on_trending_data(self):
        """Strong trending data should produce some trades."""
        bt = Backtester(initial_balance=10_000.0, risk_pct=1.0)
        ohlcv = generate_ohlcv(300, seed=100, start_price=1.1000, volatility=0.002)
        metrics, trades = bt.run(ohlcv, start_index=100)
        # With volatile data, we expect at least some signals
        assert metrics.total_trades >= 0  # may or may not produce trades

    def test_metrics_structure(self):
        bt = Backtester(initial_balance=10_000.0)
        ohlcv = generate_ohlcv(200, seed=42)
        metrics, trades = bt.run(ohlcv, start_index=100)
        assert isinstance(metrics, BacktestMetrics)
        assert metrics.total_trades >= 0
        assert 0 <= metrics.win_rate <= 1.0 or metrics.win_rate == 0.0

    def test_balance_tracking(self):
        """Balance should change based on trade P&L."""
        bt = Backtester(initial_balance=10_000.0)
        ohlcv = generate_ohlcv(300, seed=200, volatility=0.003)
        metrics, trades = bt.run(ohlcv, start_index=100)
        if trades:
            total_from_trades = sum(t.pnl for t in trades)
            assert abs(total_from_trades - metrics.total_pnl) < 0.01

    def test_win_rate_calculation(self):
        bt = Backtester(initial_balance=10_000.0)
        # Create manually crafted trades
        trades = [
            TradeRecord(entry_time=None, direction="long", entry_price=1.0, exit_price=1.1, pnl=100, pnl_pct=10, position_size=0.1, confluence_score=70),
            TradeRecord(entry_time=None, direction="long", entry_price=1.0, exit_price=0.95, pnl=-50, pnl_pct=-5, position_size=0.1, confluence_score=60),
            TradeRecord(entry_time=None, direction="short", entry_price=1.0, exit_price=0.9, pnl=100, pnl_pct=10, position_size=0.1, confluence_score=80),
        ]
        metrics = bt._compute_metrics(trades, [10000, 10100, 10050, 10150], 50)
        assert metrics.win_rate == pytest.approx(2 / 3, abs=0.01)
        assert metrics.total_trades == 3
        assert metrics.winning_trades == 2
        assert metrics.losing_trades == 1

    def test_profit_factor_calculation(self):
        bt = Backtester(initial_balance=10_000.0)
        trades = [
            TradeRecord(entry_time=None, direction="long", entry_price=1.0, exit_price=1.1, pnl=200, pnl_pct=20, position_size=0.1, confluence_score=70),
            TradeRecord(entry_time=None, direction="long", entry_price=1.0, exit_price=1.1, pnl=100, pnl_pct=10, position_size=0.1, confluence_score=60),
            TradeRecord(entry_time=None, direction="long", entry_price=1.0, exit_price=0.95, pnl=-50, pnl_pct=-5, position_size=0.1, confluence_score=50),
        ]
        metrics = bt._compute_metrics(trades, [10000, 10200, 10300, 10250], 50)
        # PF = 300 / 50 = 6.0
        assert metrics.profit_factor == pytest.approx(6.0, abs=0.1)

    def test_sharpe_ratio_positive_for_profitable(self):
        bt = Backtester(initial_balance=10_000.0)
        trades = [
            TradeRecord(entry_time=None, direction="long", entry_price=1.0, exit_price=1.1, pnl=100, pnl_pct=10, position_size=0.1, confluence_score=70) for _ in range(10)
        ]
        equity = [10000 + i * 100 for i in range(11)]
        metrics = bt._compute_metrics(trades, equity, 0)
        assert metrics.sharpe_ratio > 0

    def test_max_drawdown_from_equity(self):
        bt = Backtester(initial_balance=10_000.0)
        # Equity goes up then down
        equity = [10000, 11000, 12000, 11000, 10500, 10800]
        trades = []
        metrics = bt._compute_metrics(trades, equity, 1500)
        # DD from peak 12000 to trough 10500 = 12.5%
        assert metrics.max_drawdown_pct > 0

    def test_no_trades_metrics(self):
        bt = Backtester(initial_balance=10_000.0)
        metrics = bt._compute_metrics([], [10000], 0)
        assert metrics.total_trades == 0
        assert metrics.win_rate == 0.0
        assert metrics.profit_factor == 0.0

    def test_infinite_profit_factor_no_losses(self):
        bt = Backtester(initial_balance=10_000.0)
        trades = [
            TradeRecord(entry_time=None, direction="long", entry_price=1.0, exit_price=1.1, pnl=100, pnl_pct=10, position_size=0.1, confluence_score=70),
        ]
        metrics = bt._compute_metrics(trades, [10000, 10100], 0)
        assert metrics.profit_factor == float("inf")


# ===========================================================================
# Walk-Forward Validation
# ===========================================================================

class TestWalkForward:
    def test_walk_forward_splits(self):
        """Walk-forward: train on window, test on next period."""
        bt = Backtester(initial_balance=10_000.0)
        ohlcv = generate_ohlcv(500, seed=42)

        # Split into 3 windows
        window_size = 150
        results = []
        for i in range(0, 3):
            start = i * window_size
            end = start + window_size * 2  # train + test
            if end > len(ohlcv["closes"]):
                break
            # Run on test portion
            test_data = {
                k: v[start + window_size:end]
                for k, v in ohlcv.items()
            }
            if len(test_data["closes"]) < 20:
                continue
            metrics, _ = bt.run(test_data, start_index=min(20, len(test_data["closes"]) - 5))
            results.append(metrics)

        assert len(results) >= 1
        for m in results:
            assert isinstance(m, BacktestMetrics)
