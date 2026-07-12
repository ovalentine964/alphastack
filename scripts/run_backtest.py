#!/usr/bin/env python3
"""CLI backtest runner for AlphaStack strategies.

Usage:
    python scripts/run_backtest.py --data data/EURUSD_1h.csv --strategy ma_crossover
    python scripts/run_backtest.py --data data/BTCUSDT_4h.csv --balance 50000 --risk 1.5
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tests.backtest.backtester import Backtester, BacktestResult


# ---------------------------------------------------------------------------
# Built-in strategies
# ---------------------------------------------------------------------------

def strategy_ma_crossover(bar: np.ndarray, history: np.ndarray) -> str | None:
    """Simple MA(5) / MA(20) crossover."""
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


def strategy_momentum(bar: np.ndarray, history: np.ndarray) -> str | None:
    """Momentum strategy: long if close > close[n-10], else short."""
    if len(history) < 10:
        return None
    current = bar[3]
    past = history[-10, 3]
    if current > past * 1.001:
        return "long"
    elif current < past * 0.999:
        return "short"
    return None


def strategy_mean_reversion(bar: np.ndarray, history: np.ndarray) -> str | None:
    """Mean reversion: fade moves > 2 std from mean."""
    if len(history) < 30:
        return None
    closes = history[-30:, 3]
    mean = np.mean(closes)
    std = np.std(closes)
    if std == 0:
        return None
    z_score = (bar[3] - mean) / std
    if z_score > 2.0:
        return "short"
    elif z_score < -2.0:
        return "long"
    return None


STRATEGIES = {
    "ma_crossover": strategy_ma_crossover,
    "momentum": strategy_momentum,
    "mean_reversion": strategy_mean_reversion,
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_csv_data(path: str) -> np.ndarray:
    """Load OHLCV from CSV. Expects columns: open, high, low, close, volume."""
    data = np.genfromtxt(path, delimiter=",", skip_header=1)
    if data.ndim == 1:
        raise ValueError(f"Failed to parse CSV at {path}")
    # Ensure at least 5 columns
    if data.shape[1] < 5:
        raise ValueError(f"Expected at least 5 columns (O,H,L,C,V), got {data.shape[1]}")
    return data[:, :5]


def generate_synthetic_data(n_bars: int = 500, seed: int = 42) -> np.ndarray:
    """Generate synthetic OHLCV for quick testing."""
    rng = np.random.RandomState(seed)
    close = 1.1000 + np.cumsum(rng.randn(n_bars) * 0.001)
    high = close + np.abs(rng.randn(n_bars) * 0.0005)
    low = close - np.abs(rng.randn(n_bars) * 0.0005)
    opn = close + rng.randn(n_bars) * 0.0002
    volume = rng.randint(100, 10000, n_bars).astype(float)
    return np.column_stack([opn, high, low, close, volume])


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def print_report(result: BacktestResult, strategy_name: str) -> None:
    """Pretty-print backtest results."""
    print("\n" + "=" * 60)
    print(f"  BACKTEST REPORT — {strategy_name}")
    print("=" * 60)
    print(f"  Initial Balance:   ${result.initial_balance:,.2f}")
    print(f"  Final Balance:     ${result.final_balance:,.2f}")
    print(f"  Return:            {result.return_pct:+.2f}%")
    print("-" * 60)
    print(f"  Total Trades:      {result.total_trades}")
    print(f"  Win Rate:          {result.win_rate:.1%}")
    print(f"  Profit Factor:     {result.profit_factor}")
    print(f"  Expectancy:        ${result.expectancy:+.2f}")
    print("-" * 60)
    print(f"  Sharpe Ratio:      {result.sharpe_ratio}")
    print(f"  Sortino Ratio:     {result.sortino_ratio}")
    print(f"  Calmar Ratio:      {result.calmar_ratio}")
    print(f"  Max Drawdown:      {result.max_drawdown_pct:.2f}%")
    print(f"  Max DD Amount:     ${result.max_drawdown_amount:,.2f}")
    print("-" * 60)
    print(f"  Avg Win:           ${result.avg_win:+.2f}")
    print(f"  Avg Loss:          ${result.avg_loss:+.2f}")
    print(f"  Avg Bars Held:     {result.avg_bars_held}")
    print("=" * 60)

    if result.trades:
        print("\n  Last 5 trades:")
        for t in result.trades[-5:]:
            print(
                f"    {t.side:5s} @ {t.entry_price:.5f} → {t.exit_price:.5f}"
                f"  PnL: ${t.pnl:+.2f}  ({t.bars_held} bars)"
            )
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="AlphaStack Backtest Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Strategies: " + ", ".join(STRATEGIES.keys()),
    )
    parser.add_argument("--data", type=str, help="Path to OHLCV CSV file")
    parser.add_argument(
        "--strategy", "-s",
        type=str,
        default="ma_crossover",
        choices=list(STRATEGIES.keys()),
        help="Strategy to backtest (default: ma_crossover)",
    )
    parser.add_argument("--balance", "-b", type=float, default=10_000, help="Initial balance")
    parser.add_argument("--risk", "-r", type=float, default=2.0, help="Risk per trade (%%)")
    parser.add_argument("--sl-mult", type=float, default=1.5, help="Stop loss ATR multiplier")
    parser.add_argument("--tp-mult", type=float, default=3.0, help="Take profit ATR multiplier")
    parser.add_argument("--commission", type=float, default=0.0, help="Commission (%%)")
    parser.add_argument("--slippage", type=float, default=0.0, help="Slippage (%%)")
    parser.add_argument("--max-trades", type=int, default=3, help="Max concurrent open trades")
    parser.add_argument("--bars", type=int, default=500, help="Number of synthetic bars (if no CSV)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for synthetic data")
    parser.add_argument("--csv-out", type=str, help="Save equity curve to CSV")

    args = parser.parse_args()

    # Load data
    if args.data:
        print(f"Loading data from {args.data}...")
        ohlcv = load_csv_data(args.data)
    else:
        print(f"Generating {args.bars} synthetic bars (seed={args.seed})...")
        ohlcv = generate_synthetic_data(args.bars, args.seed)

    print(f"Data shape: {ohlcv.shape}")

    # Build backtester
    bt = Backtester(
        initial_balance=args.balance,
        risk_per_trade_pct=args.risk,
        stop_loss_atr_mult=args.sl_mult,
        take_profit_atr_mult=args.tp_mult,
        commission_pct=args.commission,
        slippage_pct=args.slippage,
        max_open_trades=args.max_trades,
    )

    # Run
    strategy_fn = STRATEGIES[args.strategy]
    print(f"Running strategy: {args.strategy}")
    result = bt.run(ohlcv, signal_fn=strategy_fn)

    # Report
    print_report(result, args.strategy)

    # Save equity curve
    if args.csv_out:
        eq = np.array(result.equity_curve)
        np.savetxt(args.csv_out, eq, delimiter=",", header="equity", comments="")
        print(f"Equity curve saved to {args.csv_out}")

    # Exit code based on profitability
    sys.exit(0 if result.total_pnl >= 0 else 1)


if __name__ == "__main__":
    main()
