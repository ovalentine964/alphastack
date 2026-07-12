"""Reflection loop for AlphaStack post-trade analysis.

Core concept: Agent generates analysis, then critiques and revises it
in a self-correction cycle.

Three reflection modes:
1. Pre-trade reflection: Review analysis for blind spots before executing
2. Post-trade reflection: Analyze what went right/wrong after close
3. Periodic strategy reflection: Weekly review of all trades
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


class ReflectionType(Enum):
    """Type of reflection being performed."""

    PRE_TRADE = "pre_trade"  # Before execution — blind spot check
    POST_TRADE = "post_trade"  # After close — lessons learned
    STRATEGY_REVIEW = "strategy_review"  # Periodic strategy assessment


class ReflectionOutcome(Enum):
    """Outcome of a reflection cycle."""

    CONFIRMED = "confirmed"  # Original analysis stands
    REVISED = "revised"  # Analysis updated based on critique
    REJECTED = "rejected"  # Analysis was fundamentally flawed
    DEFERRED = "deferred"  # Insufficient information to decide


@dataclass
class TradeReview:
    """Complete post-trade review record.

    Attributes
    ----------
    trade_id : str
        Unique trade identifier.
    symbol : str
        Trading pair/instrument.
    entry_thesis : str
        Original reason for entering.
    exit_thesis : str
        Reason for exiting.
    outcome : str
        "win", "loss", "breakeven"
    pnl : float
        Realized P&L.
    what_worked : list[str]
        Aspects of the trade that worked well.
    what_failed : list[str]
        Aspects that didn't work.
    lessons : list[str]
        Key takeaways for future trades.
    parameter_adjustments : dict[str, Any]
        Suggested parameter changes.
    """

    trade_id: str
    symbol: str
    entry_thesis: str
    exit_thesis: str
    outcome: str
    pnl: float
    what_worked: list[str] = field(default_factory=list)
    what_failed: list[str] = field(default_factory=list)
    lessons: list[str] = field(default_factory=list)
    parameter_adjustments: dict[str, Any] = field(default_factory=dict)
    reflection_count: int = 0
    confidence: float = 0.0


@dataclass
class ReflectionResult:
    """Result of a reflection loop execution."""

    original_analysis: str
    final_analysis: str
    critiques: list[str] = field(default_factory=list)
    revisions: list[str] = field(default_factory=list)
    outcome: ReflectionOutcome = ReflectionOutcome.CONFIRMED
    num_cycles: int = 0
    duration_ms: float = 0.0


# ---------------------------------------------------------------------------
# Reflection Loop
# ---------------------------------------------------------------------------


class ReflectionLoop:
    """Reflection loop for self-correcting analysis.

    Implements the Generate → Critique → Revise cycle.

    Usage
    -----
    ```python
    loop = ReflectionLoop(max_reflections=3)

    result = await loop.reflect(
        initial_analysis="Go long BTC at $67,500",
        critique_fn=my_critique_fn,
        revise_fn=my_revise_fn,
    )
    # result.final_analysis incorporates all self-corrections
    ```
    """

    def __init__(
        self,
        max_reflections: int = 3,
        improvement_threshold: float = 0.05,
    ) -> None:
        self.max_reflections = max_reflections
        self.improvement_threshold = improvement_threshold

    async def reflect(
        self,
        initial_analysis: str,
        critique_fn: Callable[..., Awaitable[str]],
        revise_fn: Callable[..., Awaitable[str]],
        context: str = "",
    ) -> ReflectionResult:
        """Run the reflection loop.

        Parameters
        ----------
        initial_analysis : str
            The initial trade analysis or thesis.
        critique_fn : Callable
            Async function: (analysis, context) → critique text.
            Should identify blind spots, missing factors, logical errors.
        revise_fn : Callable
            Async function: (analysis, critique, context) → revised analysis.
        context : str
            Additional context (market conditions, trade history, etc.).

        Returns
        -------
        ReflectionResult
            With final analysis incorporating all reflections.
        """
        start = time.monotonic()
        result = ReflectionResult(
            original_analysis=initial_analysis,
            final_analysis=initial_analysis,
        )

        current_analysis = initial_analysis

        for cycle in range(1, self.max_reflections + 1):
            # CRITIQUE
            try:
                critique = await critique_fn(current_analysis, context)
            except Exception as e:
                logger.error("Critique failed at cycle %d: %s", cycle, e)
                break

            result.critiques.append(critique)

            # Check if critique found issues
            if self._no_issues_found(critique):
                result.outcome = ReflectionOutcome.CONFIRMED
                logger.info("Reflection cycle %d: no issues found", cycle)
                break

            # REVISE
            try:
                revised = await revise_fn(current_analysis, critique, context)
            except Exception as e:
                logger.error("Revision failed at cycle %d: %s", cycle, e)
                break

            result.revisions.append(revised)

            # Check if revision meaningfully changed the analysis
            if self._is_similar(current_analysis, revised):
                result.outcome = ReflectionOutcome.CONFIRMED
                break

            current_analysis = revised
            result.num_cycles = cycle

        result.final_analysis = current_analysis
        result.duration_ms = (time.monotonic() - start) * 1000

        if result.revisions:
            result.outcome = ReflectionOutcome.REVISED

        logger.info(
            "Reflection completed: outcome=%s, cycles=%d, duration=%.0fms",
            result.outcome.value,
            result.num_cycles,
            result.duration_ms,
        )
        return result

    async def post_trade_reflect(
        self,
        trade_data: dict[str, Any],
        critique_fn: Callable[..., Awaitable[str]],
        revise_fn: Callable[..., Awaitable[str]],
    ) -> TradeReview:
        """Perform post-trade reflection and generate a TradeReview.

        Parameters
        ----------
        trade_data : dict
            Trade data including symbol, entry/exit prices, thesis, P&L.
        critique_fn : Callable
            Async function for critiquing trade analysis.
        revise_fn : Callable
            Async function for revising analysis.

        Returns
        -------
        TradeReview
            Structured post-trade review with lessons and adjustments.
        """
        trade_id = trade_data.get("trade_id", "unknown")
        symbol = trade_data.get("symbol", "unknown")
        entry_thesis = trade_data.get("entry_thesis", "")
        pnl = trade_data.get("pnl", 0.0)

        outcome = "win" if pnl > 0 else ("loss" if pnl < 0 else "breakeven")

        # Reflect on entry thesis
        reflection = await self.reflect(
            initial_analysis=entry_thesis,
            critique_fn=critique_fn,
            revise_fn=revise_fn,
            context=f"Trade {trade_id} on {symbol} resulted in {outcome} (P&L: {pnl:.2f})",
        )

        # Extract structured insights from reflections
        review = TradeReview(
            trade_id=trade_id,
            symbol=symbol,
            entry_thesis=entry_thesis,
            exit_thesis=trade_data.get("exit_thesis", ""),
            outcome=outcome,
            pnl=pnl,
            what_worked=self._extract_positives(reflection),
            what_failed=self._extract_negatives(reflection),
            lessons=self._extract_lessons(reflection),
            parameter_adjustments=self._extract_adjustments(reflection),
            reflection_count=reflection.num_cycles,
            confidence=0.8 if reflection.outcome == ReflectionOutcome.CONFIRMED else 0.6,
        )

        return review

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _no_issues_found(critique: str) -> bool:
        """Check if critique indicates no issues."""
        indicators = [
            "no issues",
            "no problems",
            "looks good",
            "analysis is sound",
            "no blind spots",
            "no_issues_found",
        ]
        return any(ind in critique.lower() for ind in indicators)

    @staticmethod
    def _is_similar(text_a: str, text_b: str) -> bool:
        """Check if two texts are substantially similar."""
        # Simple word overlap check
        words_a = set(text_a.lower().split())
        words_b = set(text_b.lower().split())
        if not words_a or not words_b:
            return True
        overlap = len(words_a & words_b) / max(len(words_a), len(words_b))
        return overlap > 0.9

    @staticmethod
    def _extract_positives(reflection: ReflectionResult) -> list[str]:
        """Extract what worked well from reflection."""
        positives = []
        for critique in reflection.critiques:
            if "good" in critique.lower() or "correct" in critique.lower():
                for line in critique.split("\n"):
                    if any(w in line.lower() for w in ["good", "correct", "right", "well"]):
                        positives.append(line.strip())
        return positives[:5]

    @staticmethod
    def _extract_negatives(reflection: ReflectionResult) -> list[str]:
        """Extract what didn't work from reflection."""
        negatives = []
        for critique in reflection.critiques:
            for line in critique.split("\n"):
                if any(w in line.lower() for w in ["missed", "failed", "wrong", "ignored", "overlooked"]):
                    negatives.append(line.strip())
        return negatives[:5]

    @staticmethod
    def _extract_lessons(reflection: ReflectionResult) -> list[str]:
        """Extract lessons from reflection."""
        lessons = []
        for revision in reflection.revisions:
            for line in revision.split("\n"):
                if any(w in line.lower() for w in ["lesson", "should", "next time", "remember"]):
                    lessons.append(line.strip())
        return lessons[:5]

    @staticmethod
    def _extract_adjustments(reflection: ReflectionResult) -> dict[str, Any]:
        """Extract parameter adjustment suggestions."""
        adjustments: dict[str, Any] = {}
        for revision in reflection.revisions:
            lower = revision.lower()
            if "stop loss" in lower or "stop-loss" in lower:
                adjustments["stop_loss_review"] = True
            if "position size" in lower:
                adjustments["position_size_review"] = True
            if "timeframe" in lower:
                adjustments["timeframe_review"] = True
            if "risk" in lower:
                adjustments["risk_parameters_review"] = True
        return adjustments
