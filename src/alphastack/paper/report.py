"""Paper trading report generator.

Produces daily and weekly performance reports with trade breakdowns,
risk analysis, and actionable insights.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from alphastack.paper.metrics import PerformanceMetrics, TradeRecord
from alphastack.utils.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Report types
# ---------------------------------------------------------------------------

class ReportGenerator:
    """Generates performance reports for paper trading."""

    def __init__(self, metrics: PerformanceMetrics) -> None:
        self.metrics = metrics

    # -- Daily report -------------------------------------------------------

    def daily_report(self, date: datetime | None = None) -> str:
        """Generate a daily performance report.

        Parameters
        ----------
        date : datetime | None
            The day to report. Defaults to today (UTC).
        """
        if date is None:
            date = datetime.now(timezone.utc)

        day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        trades = [
            t for t in self.metrics._trades
            if day_start <= t.exit_time < day_end
        ]

        return self._render_report(
            title=f"📊 Daily Report — {day_start.strftime('%Y-%m-%d')}",
            trades=trades,
            period_start=day_start,
            period_end=day_end,
        )

    # -- Weekly report ------------------------------------------------------

    def weekly_report(self, week_start: datetime | None = None) -> str:
        """Generate a weekly performance report.

        Parameters
        ----------
        week_start : datetime | None
            Monday of the week. Defaults to this week (UTC).
        """
        if week_start is None:
            now = datetime.now(timezone.utc)
            week_start = now - timedelta(days=now.weekday())
            week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

        week_end = week_start + timedelta(days=7)

        trades = [
            t for t in self.metrics._trades
            if week_start <= t.exit_time < week_end
        ]

        return self._render_report(
            title=f"📈 Weekly Report — {week_start.strftime('%Y-%m-%d')} to {(week_end - timedelta(days=1)).strftime('%Y-%m-%d')}",
            trades=trades,
            period_start=week_start,
            period_end=week_end,
        )

    # -- Full report --------------------------------------------------------

    def full_report(self) -> str:
        """Generate a full lifetime performance report."""
        trades = self.metrics._trades
        period_start = self.metrics._started_at
        period_end = datetime.now(timezone.utc)

        return self._render_report(
            title="📋 Full Performance Report",
            trades=trades,
            period_start=period_start,
            period_end=period_end,
        )

    # -- Rendering ----------------------------------------------------------

    def _render_report(
        self,
        title: str,
        trades: list[TradeRecord],
        period_start: datetime,
        period_end: datetime,
    ) -> str:
        """Render a markdown report."""
        lines: list[str] = []

        # Header
        lines.append(f"# {title}")
        lines.append(f"**Period:** {period_start.strftime('%Y-%m-%d %H:%M')} → {period_end.strftime('%Y-%m-%d %H:%M')} UTC")
        lines.append(f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
        lines.append("")

        # Overall metrics
        lines.append("## 📊 Performance Summary")
        lines.append("")

        summary = self.metrics.summary()
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Total Trades | {summary['trade_count']} |")
        lines.append(f"| Win Rate | {summary['win_rate']:.1%} |")
        lines.append(f"| Net P&L | ${summary['net_pnl']:,.2f} |")
        lines.append(f"| Profit Factor | {summary['profit_factor']} |")
        lines.append(f"| Sharpe Ratio | {summary['sharpe_ratio']} |")
        lines.append(f"| Sortino Ratio | {summary['sortino_ratio']} |")
        lines.append(f"| Max Drawdown | {summary['max_drawdown']:.2%} |")
        lines.append(f"| Current Drawdown | {summary['current_drawdown']:.2%} |")
        lines.append(f"| Avg Trade P&L | ${summary['avg_trade_pnl']:,.2f} |")
        lines.append(f"| Risk-Reward Ratio | {summary['risk_reward_ratio']} |")
        lines.append(f"| Expectancy | ${summary['expectancy']:,.2f} |")
        lines.append("")

        # Period-specific stats
        if trades:
            period_wins = sum(1 for t in trades if t.is_win)
            period_losses = sum(1 for t in trades if t.is_loss)
            period_pnl = sum(t.pnl for t in trades)
            period_win_rate = period_wins / len(trades) if trades else 0

            lines.append("## 📅 Period Stats")
            lines.append("")
            lines.append(f"| Metric | Value |")
            lines.append(f"|--------|-------|")
            lines.append(f"| Trades | {len(trades)} |")
            lines.append(f"| Wins | {period_wins} |")
            lines.append(f"| Losses | {period_losses} |")
            lines.append(f"| Win Rate | {period_win_rate:.1%} |")
            lines.append(f"| Period P&L | ${period_pnl:,.2f} |")
            lines.append("")

            # Symbol breakdown
            symbols: dict[str, list[TradeRecord]] = {}
            for t in trades:
                symbols.setdefault(t.symbol, []).append(t)

            if symbols:
                lines.append("## 🏷️ Symbol Breakdown")
                lines.append("")
                lines.append("| Symbol | Trades | Win Rate | P&L | Avg P&L |")
                lines.append("|--------|--------|----------|-----|---------|")
                for sym, sym_trades in sorted(symbols.items()):
                    sym_wins = sum(1 for t in sym_trades if t.is_win)
                    sym_pnl = sum(t.pnl for t in sym_trades)
                    sym_avg = sym_pnl / len(sym_trades)
                    sym_wr = sym_wins / len(sym_trades)
                    lines.append(
                        f"| {sym} | {len(sym_trades)} | {sym_wr:.1%} | ${sym_pnl:,.2f} | ${sym_avg:,.2f} |"
                    )
                lines.append("")

            # Strategy breakdown
            strategies: dict[str, list[TradeRecord]] = {}
            for t in trades:
                strategies.setdefault(t.strategy or "default", []).append(t)

            if len(strategies) > 1:
                lines.append("## 🧠 Strategy Breakdown")
                lines.append("")
                lines.append("| Strategy | Trades | Win Rate | P&L | Profit Factor |")
                lines.append("|----------|--------|----------|-----|---------------|")
                for strat, strat_trades in sorted(strategies.items()):
                    strat_wins = sum(1 for t in strat_trades if t.is_win)
                    strat_pnl = sum(t.pnl for t in strat_trades)
                    gross_profit = sum(t.pnl for t in strat_trades if t.is_win)
                    gross_loss = abs(sum(t.pnl for t in strat_trades if t.is_loss))
                    pf = gross_profit / gross_loss if gross_loss > 0 else float("inf")
                    strat_wr = strat_wins / len(strat_trades)
                    pf_str = f"{pf:.2f}" if pf != float("inf") else "∞"
                    lines.append(
                        f"| {strat} | {len(strat_trades)} | {strat_wr:.1%} | ${strat_pnl:,.2f} | {pf_str} |"
                    )
                lines.append("")

            # Trade log (last 20)
            lines.append("## 📝 Trade Log (Last 20)")
            lines.append("")
            lines.append("| # | Symbol | Side | Entry | Exit | Qty | P&L | Duration | Reason |")
            lines.append("|---|--------|------|-------|------|-----|-----|----------|--------|")
            for i, t in enumerate(trades[-20:], 1):
                dur = f"{t.duration_minutes:.0f}m"
                pnl_sign = "+" if t.pnl >= 0 else ""
                reason = (t.reasoning[:50] + "...") if len(t.reasoning) > 50 else t.reasoning
                lines.append(
                    f"| {i} | {t.symbol} | {t.side} | {t.entry_price:,.2f} | {t.exit_price:,.2f} | "
                    f"{t.quantity:.4f} | {pnl_sign}${t.pnl:,.2f} | {dur} | {reason} |"
                )
            lines.append("")

            # Best and worst trades
            if len(trades) > 1:
                best = max(trades, key=lambda t: t.pnl)
                worst = min(trades, key=lambda t: t.pnl)

                lines.append("## 🏆 Notable Trades")
                lines.append("")
                lines.append(f"**Best Trade:** {best.symbol} {best.side} — ${best.pnl:,.2f} ({best.pnl_pct:.2%})")
                lines.append(f"  - Entry: {best.entry_price:,.2f} → Exit: {best.exit_price:,.2f}")
                lines.append(f"  - {best.reasoning[:100]}")
                lines.append("")
                lines.append(f"**Worst Trade:** {worst.symbol} {worst.side} — ${worst.pnl:,.2f} ({worst.pnl_pct:.2%})")
                lines.append(f"  - Entry: {worst.entry_price:,.2f} → Exit: {worst.exit_price:,.2f}")
                lines.append(f"  - {worst.reasoning[:100]}")
                lines.append("")

        else:
            lines.append("*No trades executed during this period.*")
            lines.append("")

        # Risk metrics
        lines.append("## ⚠️ Risk Metrics")
        lines.append("")
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Max Drawdown | {summary['max_drawdown']:.2%} |")
        lines.append(f"| Current Drawdown | {summary['current_drawdown']:.2%} |")
        lines.append(f"| Max DD Duration | {summary['max_drawdown_duration_hours']:.1f}h |")
        lines.append(f"| Max Consecutive Wins | {summary['max_consecutive_wins']} |")
        lines.append(f"| Max Consecutive Losses | {summary['max_consecutive_losses']} |")
        lines.append(f"| Avg Slippage | {summary['avg_slippage_bps']:.1f} bps |")
        lines.append(f"| Total Commission | ${summary['total_commission']:,.2f} |")
        lines.append(f"| Uptime | {summary['uptime_hours']:.1f}h |")
        lines.append("")

        # Account status
        lines.append("## 💰 Account Status")
        lines.append("")
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Initial Balance | ${summary['initial_balance']:,.2f} |")
        lines.append(f"| Current Equity | ${summary['current_equity']:,.2f} |")
        lines.append(f"| Total Return | {(summary['current_equity'] - summary['initial_balance']) / summary['initial_balance']:.2%} |")
        lines.append(f"| Avg Trade Duration | {summary['avg_trade_duration_minutes']:.0f} min |")
        lines.append("")

        return "\n".join(lines)

    # -- JSON export --------------------------------------------------------

    def export_json(self, path: str | Path | None = None) -> dict[str, Any]:
        """Export full metrics and trades as JSON.

        Parameters
        ----------
        path : str | Path | None
            If provided, write to this file. Otherwise return the dict.
        """
        data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "metrics": self.metrics.summary(),
            "equity_curve": self.metrics.equity_curve_data(),
            "trades": self.metrics.trades_data(),
        }

        if path:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w") as f:
                json.dump(data, f, indent=2, default=str)
            log.info("report_exported", path=str(p))

        return data
