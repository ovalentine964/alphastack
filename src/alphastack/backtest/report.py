"""Backtest report generator — terminal, JSON, and CSV output."""

from __future__ import annotations

import csv
import json
import logging
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING, TextIO

if TYPE_CHECKING:
    from alphastack.backtest.engine import BacktestResult

logger = logging.getLogger("alphastack.backtest.report")


class BacktestReport:
    """Generates formatted reports from a BacktestResult.

    Usage::

        report = BacktestReport(result)
        report.print_summary()           # terminal output
        report.save_json("report.json")  # JSON export
        report.save_csv("trades.csv")    # trades CSV
    """

    def __init__(self, result: "BacktestResult") -> None:
        self.result = result
        self.m = result.metrics
        self.t = result.trades
        self.c = result.config

    # ------------------------------------------------------------------
    # Terminal report
# ------------------------------------------------------------------

    def print_summary(self, file: TextIO | None = None) -> None:
        """Print a formatted summary to stdout (or *file*)."""
        lines = self.format_summary()
        output = "\n".join(lines)
        if file:
            file.write(output + "\n")
        else:
            print(output)

    def format_summary(self) -> list[str]:
        """Return the summary as a list of lines."""
        m = self.m
        r = self.result
        c = self.c
        final = m.equity_final

        lines = [
            "",
            "═" * 64,
            f"  ALPHASTACK BACKTEST REPORT — {r.symbol} {r.timeframe}",
            "═" * 64,
            "",
            "  ACCOUNT",
            f"    Initial Balance:     ${c.initial_balance:>14,.2f}",
            f"    Final Balance:       ${final:>14,.2f}",
            f"    Net PnL:             ${m.total_pnl:>+14,.2f}",
            f"    Total Return:        {m.total_return_pct:>+13.2f}%",
            "",
            "  TRADES",
            f"    Total Trades:        {m.total_trades:>14d}",
            f"    Win / Loss / BE:     {m.winning_trades} / {m.losing_trades} / {m.breakeven_trades}",
            f"    Win Rate:            {m.win_rate:>13.1%}",
            f"    Long Trades:         {m.long_trades:>14d}  (WR: {m.long_win_rate:.1%})",
            f"    Short Trades:        {m.short_trades:>14d}  (WR: {m.short_win_rate:.1%})",
            "",
            "  PROFITABILITY",
            f"    Profit Factor:       {m.profit_factor:>14.2f}",
            f"    Expectancy:          ${m.expectancy:>+14,.2f}",
            f"    Avg Win:             ${m.avg_win:>+14,.2f}",
            f"    Avg Loss:            ${m.avg_loss:>+14,.2f}",
            f"    Largest Win:         ${m.largest_win:>+14,.2f}",
            f"    Largest Loss:        ${m.largest_loss:>+14,.2f}",
            f"    Avg R:R Ratio:       {m.avg_rr_ratio:>14.2f}",
            "",
            "  RISK",
            f"    Max Drawdown:        ${m.max_drawdown:>14,.2f}",
            f"    Max Drawdown %:      {m.max_drawdown_pct:>13.2f}%",
            f"    Sharpe Ratio:        {m.sharpe_ratio:>14.2f}",
            f"    Sortino Ratio:       {m.sortino_ratio:>14.2f}",
            f"    Calmar Ratio:        {m.calmar_ratio:>14.2f}",
            f"    Recovery Factor:     {m.recovery_factor:>14.2f}",
            f"    Max Consec. Wins:    {m.max_consecutive_wins:>14d}",
            f"    Max Consec. Losses:  {m.max_consecutive_losses:>14d}",
            "",
            "  COSTS",
            f"    Total Commission:    ${m.total_commission:>14,.2f}",
            f"    Total Slippage:      ${m.total_slippage_cost:>14,.2f}",
            f"    Avg Bars Held:       {m.avg_bars_held:>14.1f}",
            "",
            "  PARAMETERS",
            f"    Risk/Trade:          {c.risk_per_trade_pct:>13.1f}%",
            f"    Commission:          {c.commission_pct:>13.2f}%",
            f"    Funding Rate/Day:    {c.funding_rate_daily_pct:>13.3f}%",
            f"    Slippage (base bps): {c.slippage.base_bps:>13.1f}",
            "═" * 64,
        ]

        # Trade log (last 10)
        if self.t:
            lines.append("")
            lines.append("  RECENT TRADES (last 10)")
            lines.append("  " + "─" * 60)
            lines.append(f"  {'#':>3} {'Dir':>5} {'Entry':>10} {'Exit':>10} {'PnL':>10} {'Reason':<16}")
            lines.append("  " + "─" * 60)
            for t in self.t[-10:]:
                lines.append(
                    f"  {t.id:>3} {t.direction:>5} {t.entry_price:>10.2f} "
                    f"{t.exit_price:>10.2f} {t.pnl:>+10.2f} {t.exit_reason:<16}"
                )
            lines.append("  " + "─" * 60)

        lines.append("")
        return lines

    # ------------------------------------------------------------------
    # JSON export
# ------------------------------------------------------------------

    def save_json(self, path: str | Path, *, indent: int = 2) -> None:
        """Save full report as JSON."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = self.result.to_dict()
        p.write_text(json.dumps(data, indent=indent, default=str))
        logger.info("Report saved to %s", p)

    # ------------------------------------------------------------------
    # CSV export (trades only)
# ------------------------------------------------------------------

    def save_csv(self, path: str | Path) -> None:
        """Save trade log as CSV."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)

        if not self.t:
            logger.warning("No trades to export")
            p.write_text("No trades\n")
            return

        fieldnames = [
            "id", "symbol", "direction", "entry_time", "exit_time",
            "entry_price", "exit_price", "quantity", "stop_loss", "take_profit",
            "pnl", "pnl_pct", "commission", "slippage_cost", "exit_reason",
            "bars_held", "confluence_score", "equity_at_entry",
            "peak_unrealized", "trough_unrealized",
        ]

        with open(p, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for t in self.t:
                writer.writerow({
                    "id": t.id,
                    "symbol": t.symbol,
                    "direction": t.direction,
                    "entry_time": t.entry_time.isoformat() if t.entry_time else "",
                    "exit_time": t.exit_time.isoformat() if t.exit_time else "",
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "quantity": t.quantity,
                    "stop_loss": t.stop_loss,
                    "take_profit": t.take_profit,
                    "pnl": t.pnl,
                    "pnl_pct": t.pnl_pct,
                    "commission": t.commission,
                    "slippage_cost": t.slippage_cost,
                    "exit_reason": t.exit_reason,
                    "bars_held": t.bars_held,
                    "confluence_score": t.confluence_score,
                    "equity_at_entry": t.equity_at_entry,
                    "peak_unrealized": t.peak_unrealized,
                    "trough_unrealized": t.trough_unrealized,
                })

        logger.info("Trade log saved to %s (%d trades)", p, len(self.t))

    # ------------------------------------------------------------------
    # Equity curve CSV
# ------------------------------------------------------------------

    def save_equity_csv(self, path: str | Path) -> None:
        """Save equity curve as CSV."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)

        with open(p, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["timestamp", "balance", "equity", "drawdown_pct"])
            writer.writeheader()
            for snap in self.result.equity_curve:
                writer.writerow({
                    "timestamp": snap.timestamp.isoformat(),
                    "balance": snap.balance,
                    "equity": snap.equity,
                    "drawdown_pct": snap.drawdown_pct,
                })

        logger.info("Equity curve saved to %s (%d points)", p, len(self.result.equity_curve))
