#!/usr/bin/env python3
"""CLI backtest runner for AlphaStack strategies.

Usage:
    python scripts/run_backtest.py --bars 500 --seed 42
    python scripts/run_backtest.py --data data/EURUSD_1h.csv --balance 50000 --risk 1.5
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tests.backtest.backtester import Backtester, BacktestMetrics, TradeRecord
from tests.conftest import generate_ohlcv


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_csv_data(path: str) -> dict[str, list[float]]:
    """Load OHLCV from CSV into dict format expected by backtester."""
    data = np.genfromtxt(path, delimiter=",", skip_header=1)
    if data.ndim == 1:
        raise ValueError(f"Failed to parse CSV at {path}")
    if data.shape[1] < 5:
        raise ValueError(f"Expected at least 5 columns (O,H,L,C,V), got {data.shape[1]}")
    return {
        "opens": data[:, 0].tolist(),
        "highs": data[:, 1].tolist(),
        "lows": data[:, 2].tolist(),
        "closes": data[:, 3].tolist(),
        "volumes": data[:, 4].tolist(),
    }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def print_report(metrics: BacktestMetrics, trades: list[TradeRecord], strategy_name: str, initial_balance: float) -> None:
    """Pretty-print backtest results."""
    print("\n" + "=" * 60)
    print(f"  BACKTEST REPORT — {strategy_name}")
    print("=" * 60)
    print(f"  Initial Balance:   ${initial_balance:,.2f}")
    final = initial_balance + metrics.total_pnl
    print(f"  Final Balance:     ${final:,.2f}")
    print(f"  Return:            {metrics.total_return_pct:+.2f}%")
    print("-" * 60)
    print(f"  Total Trades:      {metrics.total_trades}")
    print(f"  Win Rate:          {metrics.win_rate:.1%}")
    print(f"  Profit Factor:     {metrics.profit_factor}")
    print(f"  Expectancy:        ${metrics.expectancy:+.2f}")
    print("-" * 60)
    print(f"  Sharpe Ratio:      {metrics.sharpe_ratio}")
    print(f"  Sortino Ratio:     {metrics.sortino_ratio}")
    print(f"  Calmar Ratio:      {metrics.calmar_ratio}")
    print(f"  Max Drawdown:      {metrics.max_drawdown_pct:.2f}%")
    print(f"  Max DD Amount:     ${metrics.max_drawdown:,.2f}")
    print("-" * 60)
    print(f"  Avg Win:           ${metrics.avg_win:+.2f}")
    print(f"  Avg Loss:          ${metrics.avg_loss:+.2f}")
    print("="" * 60)

    if trades:
        print("\n  Last 5 trades:")
        for t in trades[-5:]:
            print(
                f"    {t.direction:5s} @ {t.entry_price:.5f} → {t.exit_price:.5f}"
                f"  PnL: ${t.pnl:+.2f}  ({t.exit_reason})"
            )
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="AlphaStack Backtest Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--data", type=str, help="Path to OHLCV CSV file")
    parser.add_argument("--balance", "-b", type=float, default=10_000, help="Initial balance")
    parser.add_argument("--risk", "-r", type=float, default=1.0, help="Risk per trade (%%)")
    parser.add_argument("--commission", type=float, default=0.0, help="Commission (%%)")
    parser.add_argument("--bars", type=int, default=500, help="Number of synthetic bars (if no CSV)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for synthetic data")
    parser.add_argument("--start", type=int, default=100, help="Start index for backtest")
    parser.add_argument("--symbol", type=str, default="EUR/USD", help="Symbol name")

    args = parser.parse_args()

    # Load data
    if args.data:
        print(f"Loading data from {args.data}...")
        ohlcv = load_csv_data(args.data)
    else:
        print(f"Generating {args.bars} synthetic bars (seed={args.seed})...")
        ohlcv = generate_ohlcv(args.bars, seed=args.seed)

    n = len(ohlcv["closes"])
    print(f"Data bars: {n}")

    # Build backtester
    bt = Backtester(
        initial_balance=args.balance,
        risk_pct=args.risk,
        commission_pct=args.commission,
    )

    # Run AlphaStack pipeline backtest
    print(f"Running AlphaStack pipeline backtest on {args.symbol}...")
    metrics, trades = bt.run(
        ohlcv,
        symbol=args.symbol,
        start_index=args.start,
    )

    # Report
    print_report(metrics, trades, f"AlphaStack Pipeline ({args.symbol})", args.balance)

    # Exit code based on profitability
    sys.exit(0 if metrics.total_pnl >= 0 else 1)


if __name__ == "__main__":
    main()
