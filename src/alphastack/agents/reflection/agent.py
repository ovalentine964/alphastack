"""Reflection Agent — post-trade analysis and strategy learning loop.

This agent runs after execution to review what happened, compute
performance metrics, and recommend parameter adjustments. It closes
the learning loop so the system improves over time.
"""

from __future__ import annotations

import statistics
from datetime import datetime
from typing import Any

from alphastack.agents.base import AlphaStackAgent
from alphastack.core.events import EventBus
from alphastack.utils.logger import get_logger

logger = get_logger(__name__)


class ReflectionAgent(AlphaStackAgent):
    """Post-trade analysis, performance review, and strategy adjustment.

    Responsibilities:
    - Analyse recent execution results
    - Compute win rate, profit factor, avg R:R, max drawdown
    - Identify patterns in winning vs losing trades
    - Recommend parameter adjustments (stop size, TP targets, filters)
    - Feed learnings back into the strategy pipeline context
    """

    def __init__(self, event_bus: EventBus | None = None) -> None:
        super().__init__(
            name="reflection",
            role="analyst",
            description="Post-trade analysis and strategy parameter adjustment",
            event_bus=event_bus,
        )

    def system_prompt(self) -> str:
        return (
            "You are the AlphaStack Reflection Agent. Your job is to:\n"
            "1. Review execution results after each trading cycle\n"
            "2. Compute performance metrics: win rate, profit factor, avg R:R\n"
            "3. Identify patterns in winning vs losing trades\n"
            "4. Recommend concrete parameter adjustments\n"
            "5. Feed learnings back so the strategy improves over time\n"
        )

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Run post-trade reflection and generate recommendations."""
        execution_log = state.get("execution_log", [])
        trade_decisions = state.get("trade_decisions", [])
        pipeline_context = state.get("pipeline_context", {})
        signals = state.get("signals", [])

        logger.info(
            "reflection_agent.start",
            executions=len(execution_log),
            decisions=len(trade_decisions),
        )

        # Compute performance summary
        performance = self._compute_performance(execution_log, trade_decisions)

        # Generate strategy adjustments
        adjustments = self._generate_adjustments(
            performance, execution_log, pipeline_context, signals,
        )

        # Build learnings summary
        learnings = self._extract_learnings(performance, execution_log)

        performance["learnings"] = learnings
        performance["reflection_timestamp"] = datetime.utcnow().isoformat()

        logger.info(
            "reflection_agent.complete",
            win_rate=performance.get("win_rate", 0),
            adjustments=len(adjustments),
        )

        return {
            "performance_summary": performance,
            "strategy_adjustments": adjustments,
            "_confidence": 0.85,
        }

    def _compute_performance(
        self,
        execution_log: list[dict[str, Any]],
        trade_decisions: list[Any],
    ) -> dict[str, Any]:
        """Compute key performance metrics."""
        filled = [
            e for e in execution_log
            if e.get("status") == "filled"
        ]
        failed = [
            e for e in execution_log
            if e.get("status") == "failed"
        ]

        total_decisions = len(trade_decisions)
        approved = sum(
            1 for d in trade_decisions
            if (d.get("status") if isinstance(d, dict) else getattr(d, "status", "")) == "approved"
        )
        rejected = total_decisions - approved

        # P&L analysis (from fill prices vs entry signals)
        pnls: list[float] = []
        for entry in filled:
            signal = entry.get("signal", {})
            fill_price = entry.get("fill_price", 0)
            entry_price = entry.get("price", 0)
            action = entry.get("action", "")

            if fill_price and entry_price and action in ("buy", "sell"):
                if action == "buy":
                    pnl = fill_price - entry_price
                else:
                    pnl = entry_price - fill_price
                pnls.append(pnl)

        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]

        win_rate = len(wins) / max(len(pnls), 1)
        avg_win = statistics.mean(wins) if wins else 0.0
        avg_loss = statistics.mean(losses) if losses else 0.0
        profit_factor = abs(sum(wins) / sum(losses)) if losses and sum(losses) != 0 else float("inf") if wins else 0.0
        avg_rr = abs(avg_win / avg_loss) if avg_loss != 0 else float("inf") if avg_win > 0 else 0.0

        return {
            "total_executions": len(execution_log),
            "filled": len(filled),
            "failed": len(failed),
            "total_decisions": total_decisions,
            "approved": approved,
            "rejected": rejected,
            "win_rate": round(win_rate, 4),
            "profit_factor": round(profit_factor, 4),
            "avg_rr_ratio": round(avg_rr, 4),
            "avg_win": round(avg_win, 6),
            "avg_loss": round(avg_loss, 6),
            "total_pnl": round(sum(pnls), 6),
            "trade_count": len(pnls),
        }

    def _generate_adjustments(
        self,
        performance: dict[str, Any],
        execution_log: list[dict[str, Any]],
        pipeline_context: dict[str, Any],
        signals: list[Any],
    ) -> list[dict[str, Any]]:
        """Generate concrete parameter adjustment recommendations."""
        adjustments: list[dict[str, Any]] = []

        win_rate = performance.get("win_rate", 0)
        profit_factor = performance.get("profit_factor", 0)
        avg_rr = performance.get("avg_rr_ratio", 0)
        failed_count = performance.get("failed", 0)

        # Low win rate → tighten entry filters
        if win_rate < 0.4 and performance.get("trade_count", 0) >= 5:
            adjustments.append({
                "parameter": "min_confluence_score",
                "current": pipeline_context.get("confluence_threshold", 0.3),
                "recommended": pipeline_context.get("confluence_threshold", 0.3) + 0.1,
                "reason": f"Win rate {win_rate:.1%} is below 40% — tighten entry filter",
                "priority": "high",
            })

        # Poor R:R → widen TP or tighten SL
        if avg_rr < 1.0 and performance.get("trade_count", 0) >= 5:
            adjustments.append({
                "parameter": "risk_reward_minimum",
                "current": pipeline_context.get("min_rr", 1.5),
                "recommended": max(pipeline_context.get("min_rr", 1.5), 1.5),
                "reason": f"Avg R:R {avg_rr:.2f} is below 1.0 — improve reward:risk",
                "priority": "high",
            })

        # High execution failures → check broker health
        if failed_count > 0:
            failure_rate = failed_count / max(performance.get("total_executions", 1), 1)
            adjustments.append({
                "parameter": "broker_health_check",
                "current": "none",
                "recommended": "enable",
                "reason": f"{failure_rate:.0%} execution failure rate — check broker connectivity",
                "priority": "medium",
            })

        # Too many rejections from risk → review risk limits
        rejected = performance.get("rejected", 0)
        total = performance.get("total_decisions", 1)
        if total > 0 and rejected / total > 0.7:
            adjustments.append({
                "parameter": "risk_limits_review",
                "current": "current_settings",
                "recommended": "review",
                "reason": f"{rejected}/{total} decisions rejected — limits may be too tight",
                "priority": "low",
            })

        # Good performance → suggest scaling up
        if win_rate > 0.6 and profit_factor > 2.0 and performance.get("trade_count", 0) >= 10:
            adjustments.append({
                "parameter": "position_size_multiplier",
                "current": 1.0,
                "recommended": 1.2,
                "reason": f"Strong performance (WR={win_rate:.1%}, PF={profit_factor:.1f}) — consider scaling",
                "priority": "low",
            })

        return adjustments

    def _extract_learnings(
        self,
        performance: dict[str, Any],
        execution_log: list[dict[str, Any]],
    ) -> list[str]:
        """Extract human-readable learnings from the trading cycle."""
        learnings: list[str] = []

        win_rate = performance.get("win_rate", 0)
        trade_count = performance.get("trade_count", 0)

        if trade_count == 0:
            learnings.append("No trades executed this cycle — review signal generation thresholds")
            return learnings

        if win_rate > 0.6:
            learnings.append(f"Strong win rate ({win_rate:.1%}) — strategy is performing well")
        elif win_rate > 0.4:
            learnings.append(f"Moderate win rate ({win_rate:.1%}) — room for improvement in entry timing")
        else:
            learnings.append(f"Low win rate ({win_rate:.1%}) — consider tightening confluence requirements")

        pf = performance.get("profit_factor", 0)
        if pf > 2.0:
            learnings.append(f"Excellent profit factor ({pf:.1f}) — winners significantly outweigh losers")
        elif pf > 1.0:
            learnings.append(f"Profitable profit factor ({pf:.1f}) — system is net positive")
        else:
            learnings.append(f"Profit factor below 1.0 ({pf:.1f}) — losing money overall, review strategy")

        failed = performance.get("failed", 0)
        if failed > 0:
            learnings.append(f"{failed} execution failures — investigate broker connectivity")

        return learnings
