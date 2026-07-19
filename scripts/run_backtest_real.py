#!/usr/bin/env python3
"""Run a production backtest on BTC/USDT using real CCXT data.

Usage:
    python scripts/run_backtest_real.py
    python scripts/run_backtest_real.py --symbol ETH/USDT --days 60 --timeframe 4h
    python scripts/run_backtest_real.py --balance 50000 --risk 2.0 --exchange okx
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from alphastack.backtest.data_loader import load_ccxt
from alphastack.backtest.engine import BacktestConfig, BacktestEngine, SlippageConfig
from alphastack.backtest.report import BacktestReport


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AlphaStack Real-Data Backtester",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/run_backtest_real.py
  python scripts/run_backtest_real.py --symbol ETH/USDT --days 60
  python scripts/run_backtest_real.py --balance 50000 --risk 2.0 --commission 0.075
        """,
    )
    parser.add_argument("--symbol", "-s", type=str, default="BTC/USDT", help="Trading pair (default: BTC/USDT)")
    parser.add_argument("--timeframe", "-t", type=str, default="1h", help="Candle timeframe (default: 1h)")
    parser.add_argument("--days", "-d", type=int, default=30, help="Days of history (default: 30)")
    parser.add_argument("--exchange", "-e", type=str, default="binance", help="CCXT exchange (default: binance)")
    parser.add_argument("--balance", "-b", type=float, default=10_000, help="Initial balance USD (default: 10000)")
    parser.add_argument("--risk", "-r", type=float, default=1.0, help="Risk per trade %% (default: 1.0)")
    parser.add_argument("--commission", type=float, default=0.1, help="Commission %% per side (default: 0.1)")
    parser.add_argument("--funding", type=float, default=0.01, help="Daily funding rate %% (default: 0.01)")
    parser.add_argument("--slippage-bps", type=float, default=2.0, help="Base slippage bps (default: 2.0)")
    parser.add_argument("--trailing", action="store_true", help="Enable trailing stop")
    parser.add_argument("--output", "-o", type=str, help="Output directory for reports")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    parser.add_argument("--since", type=str, help="Start date (ISO format, e.g. 2025-06-01)")
    parser.add_argument("--until", type=str, help="End date (ISO format, e.g. 2025-07-01)")

    args = parser.parse_args()
    setup_logging(args.verbose)

    # Parse dates
    since = datetime.fromisoformat(args.since) if args.since else None
    until = datetime.fromisoformat(args.until) if args.until else None

    # ── Fetch data ─────────────────────────────────────────────────────
    print(f"\n📡 Fetching {args.symbol} {args.timeframe} data from {args.exchange}...")
    try:
        df = load_ccxt(
            symbol=args.symbol,
            timeframe=args.timeframe,
            days=args.days,
            exchange_id=args.exchange,
            since=since,
            until=until,
        )
    except Exception as e:
        print(f"❌ Failed to fetch data: {e}")
        sys.exit(1)

    print(f"   Loaded {len(df)} candles: {df['timestamp'].iloc[0]} → {df['timestamp'].iloc[-1]}")
    print(f"   Price range: ${df['low'].min():,.2f} – ${df['high'].max():,.2f}")

    # ── Configure backtest ─────────────────────────────────────────────
    config = BacktestConfig(
        initial_balance=args.balance,
        risk_per_trade_pct=args.risk,
        commission_pct=args.commission,
        funding_rate_daily_pct=args.funding,
        slippage=SlippageConfig(
            base_bps=args.slippage_bps,
            spread_bps=1.0,
        ),
        enable_trailing_stop=args.trailing,
        start_index=100,
    )

    # ── Run backtest ───────────────────────────────────────────────────
    print(f"\n🚀 Running backtest with $${args.balance:,.0f} balance, {args.risk}% risk/trade...")
    engine = BacktestEngine(config=config)
    result = engine.run(df, symbol=args.symbol, timeframe=args.timeframe)

    # ── Print report ───────────────────────────────────────────────────
    result.report.print_summary()

    # ── Save outputs ───────────────────────────────────────────────────
    if args.output:
        out_dir = Path(args.output)
    else:
        out_dir = Path("backtest_results") / f"{args.symbol.replace('/', '_')}_{args.timeframe}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    out_dir.mkdir(parents=True, exist_ok=True)

    result.report.save_json(out_dir / "report.json")
    result.report.save_csv(out_dir / "trades.csv")
    result.report.save_equity_csv(out_dir / "equity_curve.csv")

    print(f"\n📁 Reports saved to: {out_dir}/")
    print(f"   report.json       — full metrics & trades")
    print(f"   trades.csv        — trade log")
    print(f"   equity_curve.csv  — equity over time")

    # Exit code
    sys.exit(0 if result.metrics.total_pnl >= 0 else 1)


if __name__ == "__main__":
    main()
