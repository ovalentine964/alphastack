#!/usr/bin/env python3
"""Launch AlphaStack paper trading on BTC/USDT.

Usage:
    python scripts/start_paper_trading.py
    python scripts/start_paper_trading.py --balance 50000 --cycles 100
    python scripts/start_paper_trading.py --symbols BTC/USDT ETH/USDT --slippage 3
"""

from __future__ import annotations

import argparse
import asyncio
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure the src directory is on the path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from alphastack.paper.trader import PaperConfig, PaperTrader
from alphastack.paper.report import ReportGenerator
from alphastack.utils.logger import setup_logging, get_logger

log = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AlphaStack Paper Trader — Shadow Mode",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--balance",
        type=float,
        default=10_000.0,
        help="Initial virtual balance in USDT (default: 10000)",
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=["BTC/USDT"],
        help="Symbols to trade (default: BTC/USDT)",
    )
    parser.add_argument(
        "--timeframe",
        default="1h",
        help="Analysis timeframe (default: 1h)",
    )
    parser.add_argument(
        "--cycles",
        type=int,
        default=None,
        help="Number of cycles to run (default: unlimited)",
    )
    parser.add_argument(
        "--slippage",
        type=float,
        default=5.0,
        help="Simulated slippage in basis points (default: 5)",
    )
    parser.add_argument(
        "--commission",
        type=float,
        default=0.001,
        help="Commission percentage (default: 0.001 = 0.1%%)",
    )
    parser.add_argument(
        "--journal",
        default="data/paper_journal.jsonl",
        help="Path to journal file (default: data/paper_journal.jsonl)",
    )
    parser.add_argument(
        "--report-interval",
        type=int,
        default=24,
        help="Hours between auto-generated reports (default: 24)",
    )
    parser.add_argument(
        "--no-orchestrator",
        action="store_true",
        help="Run in standalone mode without the full orchestrator",
    )
    parser.add_argument(
        "--hitl",
        action="store_true",
        help="Enable human-in-the-loop approval (disabled by default in paper mode)",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()

    # Setup logging
    setup_logging(level="INFO", json_output=True)

    log.info("=" * 60)
    log.info("AlphaStack Paper Trader — Starting")
    log.info("=" * 60)

    # Build config
    config = PaperConfig(
        initial_balance=args.balance,
        symbols=args.symbols,
        default_timeframe=args.timeframe,
        slippage_bps=args.slippage,
        commission_pct=args.commission,
        journal_path=args.journal,
        human_in_the_loop=args.hitl,
    )

    # Initialize orchestrator
    orchestrator = None
    if not args.no_orchestrator:
        try:
            from alphastack.agents.orchestrator.graph import AlphaStackOrchestrator
            orchestrator = AlphaStackOrchestrator(
                human_in_the_loop=config.human_in_the_loop,
                hitl_threshold=config.hitl_threshold,
            )
            log.info("orchestrator_loaded")
        except Exception as exc:
            log.warning(
                "orchestrator_load_failed",
                error=str(exc),
                fallback="standalone mode",
            )

    # Create trader
    trader = PaperTrader(
        config=config,
        orchestrator=orchestrator,
    )

    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()

    def handle_shutdown(sig: int) -> None:
        log.info("shutdown_signal_received", signal=sig)
        trader.stop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda s=sig: handle_shutdown(s))
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            signal.signal(sig, lambda s, _: handle_shutdown(s))

    # Print startup banner
    print("\n" + "=" * 60)
    print("  AlphaStack Paper Trader — Shadow Mode")
    print("=" * 60)
    print(f"  Balance:    ${config.initial_balance:,.2f} {config.currency}")
    print(f"  Symbols:    {', '.join(config.symbols)}")
    print(f"  Timeframe:  {config.default_timeframe}")
    print(f"  Slippage:   {config.slippage_bps} bps")
    print(f"  Commission: {config.commission_pct:.3%}")
    print(f"  Journal:    {config.journal_path}")
    if orchestrator:
        print(f"  Pipeline:   Full (news → strategy → debate → risk → execution)")
    else:
        print(f"  Pipeline:   Standalone (no orchestrator)")
    if args.cycles:
        print(f"  Cycles:     {args.cycles}")
    else:
        print(f"  Cycles:     Unlimited (Ctrl+C to stop)")
    print("=" * 60 + "\n")

    # Run
    try:
        await trader.start(cycles=args.cycles)
    except KeyboardInterrupt:
        log.info("interrupted_by_user")
    finally:
        # Generate final report
        log.info("generating_final_report")

        report_gen = ReportGenerator(trader.metrics)

        # Save reports
        report_dir = Path("data/reports")
        report_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        # Full report
        full_report = report_gen.full_report()
        report_path = report_dir / f"paper_report_{ts}.md"
        report_path.write_text(full_report)
        print(f"\n📄 Full report: {report_path}")

        # JSON export
        json_path = report_dir / f"paper_metrics_{ts}.json"
        report_gen.export_json(json_path)
        print(f"📊 Metrics JSON: {json_path}")

        # Print summary to console
        status = trader.status()
        print("\n" + "=" * 60)
        print("  Final Status")
        print("=" * 60)
        print(f"  Balance:   ${status['balance']:,.2f}")
        print(f"  Equity:    ${status['equity']:,.2f}")
        print(f"  Trades:    {status['metrics']['trade_count']}")
        print(f"  Win Rate:  {status['metrics']['win_rate']:.1%}")
        print(f"  Net P&L:   ${status['metrics']['net_pnl']:,.2f}")
        print(f"  Max DD:    {status['metrics']['max_drawdown']:.2%}")
        print(f"  Sharpe:    {status['metrics']['sharpe_ratio']:.3f}")
        print(f"  Cycles:    {status['cycle_count']}")
        print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
