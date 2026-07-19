"""Post-trade reflection, correction engine, and skill creator.

Implements the self-correction learning loop:
  completed trade → reflection → corrections → skill extraction → memory

Enhanced with:
- Detailed trade journal with entry/exit reasoning
- Chart annotation data (price level snapshots at entry/exit)
- What-if analysis: "what would I do differently?"
- Signal quality decomposition
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from alphastack.agi.memory import EpisodicMemory, TradeEpisode
from alphastack.agi.reasoning import ChainOfThoughtEngine, ReasoningChain, ReasoningStepType
from alphastack.utils.logger import get_logger

logger = get_logger(__name__)

# ──────────────────────────────────────────────────────────────────────
# Correction model
# ──────────────────────────────────────────────────────────────────────


@dataclass
class Correction:
    """A concrete adjustment generated from reflection."""
    correction_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    category: str = ""       # signal | execution | timing | risk
    parameter: str = ""      # e.g. "min_confluence_score", "position_size_pct"
    old_value: Any = None
    new_value: Any = None
    reason: str = ""
    impact_score: float = 0.0  # 0–1, how much to weight this correction
    created_at: float = field(default_factory=time.time)
    applied: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "correction_id": self.correction_id,
            "category": self.category,
            "parameter": self.parameter,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "reason": self.reason,
            "impact_score": self.impact_score,
            "applied": self.applied,
        }


# ──────────────────────────────────────────────────────────────────────
# Chart Annotation (price level snapshots)
# ──────────────────────────────────────────────────────────────────────


@dataclass
class PriceLevel:
    """A notable price level for chart annotation."""
    price: float
    label: str
    level_type: str = ""  # "entry", "exit", "stop_loss", "take_profit", "support", "resistance"
    timestamp: float = 0.0
    color: str = "#ffffff"  # hex color for rendering


@dataclass
class ChartAnnotation:
    """Snapshot of price levels at entry and exit for visual journaling.

    Stores the key price levels so a chart can be rendered later showing:
    - Entry price with arrow
    - Exit price with arrow
    - Stop loss / take profit levels
    - Key support/resistance levels identified at the time
    - Price action during the hold period (OHLCV summary)
    """
    entry_annotation: PriceLevel | None = None
    exit_annotation: PriceLevel | None = None
    stop_loss: PriceLevel | None = None
    take_profit: PriceLevel | None = None
    key_levels: list[PriceLevel] = field(default_factory=list)
    # OHLCV snapshot during hold period
    hold_period_high: float = 0.0
    hold_period_low: float = 0.0
    hold_period_open: float = 0.0
    hold_period_close: float = 0.0
    hold_period_volume: float = 0.0
    # Max favorable/adverse excursion
    max_favorable_excursion: float = 0.0  # best price during trade
    max_adverse_excursion: float = 0.0    # worst price during trade
    mfe_timestamp: float = 0.0
    mae_timestamp: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "hold_period": {
                "open": self.hold_period_open,
                "high": self.hold_period_high,
                "low": self.hold_period_low,
                "close": self.hold_period_close,
                "volume": self.hold_period_volume,
            },
            "max_favorable_excursion": round(self.max_favorable_excursion, 6),
            "max_adverse_excursion": round(self.max_adverse_excursion, 6),
            "key_levels": [
                {"price": l.price, "label": l.label, "type": l.level_type, "color": l.color}
                for l in self.key_levels
            ],
        }
        if self.entry_annotation:
            result["entry"] = {
                "price": self.entry_annotation.price,
                "label": self.entry_annotation.label,
                "color": self.entry_annotation.color,
            }
        if self.exit_annotation:
            result["exit"] = {
                "price": self.exit_annotation.price,
                "label": self.exit_annotation.label,
                "color": self.exit_annotation.color,
            }
        if self.stop_loss:
            result["stop_loss"] = {
                "price": self.stop_loss.price,
                "label": self.stop_loss.label,
            }
        if self.take_profit:
            result["take_profit"] = {
                "price": self.take_profit.price,
                "label": self.take_profit.label,
            }
        return result


# ──────────────────────────────────────────────────────────────────────
# What-If Analysis
# ──────────────────────────────────────────────────────────────────────


@dataclass
class WhatIfAnalysis:
    """Analysis of what the agent would do differently.

    Generated by comparing the actual trade outcome with
    counterfactual scenarios.
    """
    original_decision: str = ""
    what_went_right: list[str] = field(default_factory=list)
    what_went_wrong: list[str] = field(default_factory=list)
    alternative_actions: list[dict[str, Any]] = field(default_factory=list)
    key_mistake: str = ""
    primary_lesson: str = ""
    confidence_in_hindsight: float = 0.0  # how obvious was the mistake

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_decision": self.original_decision,
            "what_went_right": self.what_went_right,
            "what_went_wrong": self.what_went_wrong,
            "alternative_actions": self.alternative_actions,
            "key_mistake": self.key_mistake,
            "primary_lesson": self.primary_lesson,
            "confidence_in_hindsight": round(self.confidence_in_hindsight, 2),
        }


# ──────────────────────────────────────────────────────────────────────
# Detailed Trade Journal Entry
# ──────────────────────────────────────────────────────────────────────


@dataclass
class DetailedTradeJournal:
    """Full trade journal entry with reasoning, chart data, and what-if analysis.

    This is the complete record of a trade — not just numbers, but the
    reasoning behind every decision, a visual snapshot, and a candid
    assessment of what to improve.
    """
    journal_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    trade_id: str = ""
    symbol: str = ""
    direction: str = ""  # "long" | "short"
    strategy: str = ""

    # Entry reasoning
    entry_reasoning: str = ""
    entry_signals: list[dict[str, Any]] = field(default_factory=list)
    entry_confidence: float = 0.0
    entry_regime: str = ""
    entry_timestamp: float = 0.0
    entry_price: float = 0.0
    entry_slippage_bps: float = 0.0

    # Exit reasoning
    exit_reasoning: str = ""
    exit_type: str = ""  # "take_profit", "stop_loss", "signal", "time", "manual"
    exit_price: float = 0.0
    exit_timestamp: float = 0.0
    exit_slippage_bps: float = 0.0

    # Position
    quantity: float = 0.0
    position_value: float = 0.0
    risk_amount: float = 0.0

    # Outcome
    pnl: float = 0.0
    pnl_pct: float = 0.0
    hold_duration_s: float = 0.0
    r_multiple: float = 0.0  # P&L in units of initial risk

    # Visual snapshot
    chart: ChartAnnotation = field(default_factory=ChartAnnotation)

    # Self-analysis
    what_if: WhatIfAnalysis = field(default_factory=WhatIfAnalysis)

    # Signal decomposition
    signal_scores: dict[str, float] = field(default_factory=dict)
    dominant_signal: str = ""
    signal_agreement: float = 0.0  # how much signals agreed (0-1)

    # Tags and lessons
    tags: list[str] = field(default_factory=list)
    lessons: list[str] = field(default_factory=list)

    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "journal_id": self.journal_id,
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "direction": self.direction,
            "strategy": self.strategy,
            "entry": {
                "reasoning": self.entry_reasoning,
                "signals": self.entry_signals,
                "confidence": round(self.entry_confidence, 4),
                "regime": self.entry_regime,
                "price": self.entry_price,
                "slippage_bps": round(self.entry_slippage_bps, 2),
                "timestamp": self.entry_timestamp,
            },
            "exit": {
                "reasoning": self.exit_reasoning,
                "type": self.exit_type,
                "price": self.exit_price,
                "slippage_bps": round(self.exit_slippage_bps, 2),
                "timestamp": self.exit_timestamp,
            },
            "position": {
                "quantity": self.quantity,
                "value": round(self.position_value, 2),
                "risk_amount": round(self.risk_amount, 2),
            },
            "outcome": {
                "pnl": round(self.pnl, 6),
                "pnl_pct": round(self.pnl_pct, 4),
                "r_multiple": round(self.r_multiple, 4),
                "hold_duration_s": round(self.hold_duration_s, 1),
            },
            "chart": self.chart.to_dict(),
            "what_if": self.what_if.to_dict(),
            "signals": {
                "scores": self.signal_scores,
                "dominant": self.dominant_signal,
                "agreement": round(self.signal_agreement, 4),
            },
            "tags": self.tags,
            "lessons": self.lessons,
        }


# ──────────────────────────────────────────────────────────────────────
# Skill model
# ──────────────────────────────────────────────────────────────────────


@dataclass
class TradeSkill:
    """Reusable trade template extracted from repeated winning patterns."""
    skill_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    pattern: str = ""        # "When X happens, do Y"
    conditions: dict[str, Any] = field(default_factory=dict)
    action_template: dict[str, Any] = field(default_factory=dict)
    win_count: int = 0
    loss_count: int = 0
    total_pnl: float = 0.0
    created_at: float = field(default_factory=time.time)
    active: bool = True

    @property
    def win_rate(self) -> float:
        total = self.win_count + self.loss_count
        return self.win_count / total if total else 0.0

    @property
    def success_rate(self) -> float:
        """Success rate adjusted by PnL magnitude."""
        total = self.win_count + self.loss_count
        if not total:
            return 0.0
        return self.win_rate * min(1.0, max(0.0, (self.total_pnl / max(abs(self.total_pnl), 1e-10))))

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "pattern": self.pattern,
            "conditions": self.conditions,
            "win_rate": round(self.win_rate, 4),
            "total_pnl": round(self.total_pnl, 6),
            "active": self.active,
        }


MAX_ACTIVE_SKILLS = 20


# ──────────────────────────────────────────────────────────────────────
# What-If Analyzer
# ──────────────────────────────────────────────────────────────────────


class WhatIfAnalyzer:
    """Generates what-if analysis for completed trades.

    Compares actual outcome with counterfactual scenarios to extract
    actionable lessons.
    """

    def analyze(self, trade: dict[str, Any], chain: ReasoningChain | None = None) -> WhatIfAnalysis:
        """Generate what-if analysis for a completed trade.

        Parameters
        ----------
        trade : dict
            Completed trade data.
        chain : ReasoningChain | None
            The reflection reasoning chain, if available.

        Returns
        -------
        WhatIfAnalysis
            What went right/wrong and what to do differently.
        """
        pnl = trade.get("pnl", 0.0)
        direction = trade.get("direction", "long")
        entry_price = trade.get("entry_price", 0.0)
        exit_price = trade.get("exit_price", 0.0)
        stop_loss = trade.get("stop_loss", 0.0)
        take_profit = trade.get("take_profit", 0.0)
        signal = trade.get("signal", {})
        hold_duration = trade.get("hold_duration_s", 0)
        max_adverse = trade.get("max_adverse_excursion", 0)
        max_favorable = trade.get("max_favorable_excursion", 0)

        analysis = WhatIfAnalysis()
        analysis.original_decision = f"{direction} at {entry_price}"

        is_win = pnl > 0
        price_move = exit_price - entry_price if direction == "long" else entry_price - exit_price

        # What went right
        if is_win:
            analysis.what_went_right.append(f"Directional call was correct ({direction})")
            if signal.get("confidence", 0) > 0.6:
                analysis.what_went_right.append(f"High signal confidence ({signal['confidence']:.2f}) validated")
            if max_adverse > 0 and stop_loss:
                sl_dist = abs(entry_price - stop_loss)
                if max_adverse < sl_dist * 0.8:
                    analysis.what_went_right.append("Stop loss was well-placed — never seriously threatened")
        else:
            # Even in losses, something might have been right
            if stop_loss and max_adverse:
                sl_dist = abs(entry_price - stop_loss)
                if max_adverse <= sl_dist * 1.1:
                    analysis.what_went_right.append("Risk management worked — loss contained near stop")

        # What went wrong
        if not is_win:
            analysis.what_went_wrong.append(f"Directional call was wrong — lost {abs(pnl):.4f}")
            if signal.get("confidence", 0) < 0.5:
                analysis.what_went_wrong.append(f"Entered with low signal confidence ({signal.get('confidence', 0):.2f})")
            if max_favorable > 0 and price_move < 0:
                # Trade was profitable at some point but we held through reversal
                analysis.what_went_wrong.append(
                    f"Trade was in profit (MFE={max_favorable:.4f}) but held through reversal"
                )
        else:
            # Even winners have room for improvement
            if max_favorable > 0 and exit_price != entry_price:
                capture_ratio = price_move / max_favorable if max_favorable > 0 else 0
                if capture_ratio < 0.5:
                    analysis.what_went_wrong.append(
                        f"Only captured {capture_ratio:.0%} of maximum favorable excursion — "
                        f"could have let profits run longer"
                    )

        # Alternative actions
        if not is_win:
            # What if we had tighter stop?
            if stop_loss and max_adverse:
                sl_dist = abs(entry_price - stop_loss)
                if max_adverse > sl_dist * 1.5:
                    analysis.alternative_actions.append({
                        "action": "tighter_stop",
                        "description": f"Stop at {entry_price - sl_dist * 0.75:.2f} instead of {stop_loss:.2f}",
                        "estimated_impact": f"Loss reduced by ~{25}%",
                    })

            # What if we had waited for better entry?
            if max_adverse > 0:
                analysis.alternative_actions.append({
                    "action": "better_entry",
                    "description": f"Wait for pullback — price moved {max_adverse:.4f} against before reversing",
                    "estimated_impact": "Reduced drawdown during trade",
                })

            # What if we had smaller position?
            analysis.alternative_actions.append({
                "action": "reduce_size",
                "description": "Use 50% position size on lower-confidence signals",
                "estimated_impact": f"Loss halved to {abs(pnl) / 2:.4f}",
            })

        # Key mistake and lesson
        if not is_win:
            if signal.get("confidence", 0) < 0.5:
                analysis.key_mistake = "Entered trade with insufficient signal confidence"
                analysis.primary_lesson = "Wait for stronger signal confluence before entering"
                analysis.confidence_in_hindsight = 0.8
            elif max_favorable > abs(price_move) * 2:
                analysis.key_mistake = "Held through reversal — didn't take partial profits"
                analysis.primary_lesson = "Trail stop to breakeven once trade reaches 1R profit"
                analysis.confidence_in_hindsight = 0.7
            else:
                analysis.key_mistake = "Directional thesis was incorrect for current regime"
                analysis.primary_lesson = "Check regime alignment before taking directional bets"
                analysis.confidence_in_hindsight = 0.6
        else:
            if max_favorable > 0:
                capture = price_move / max_favorable if max_favorable > 0 else 1.0
                if capture < 0.5:
                    analysis.key_mistake = "Exited too early — left money on the table"
                    analysis.primary_lesson = "Use trailing stops to capture more of extended moves"
                    analysis.confidence_in_hindsight = 0.5

        return analysis


# ──────────────────────────────────────────────────────────────────────
# PostTradeReflection
# ──────────────────────────────────────────────────────────────────────


class PostTradeReflection:
    """Reflect on a single completed trade using chain-of-thought reasoning.

    Identifies whether the signal, execution, timing, or risk management
    was the primary contributor to the outcome.

    Enhanced with:
    - Detailed trade journal with full reasoning chain
    - Chart annotation data for visual review
    - What-if analysis with alternative scenarios
    - Signal decomposition (which signals contributed most)
    """

    def __init__(self, reasoning_engine: ChainOfThoughtEngine | None = None) -> None:
        self._engine = reasoning_engine or ChainOfThoughtEngine()
        self._what_if = WhatIfAnalyzer()

    def reflect(self, trade: dict[str, Any]) -> ReasoningChain:
        """Run chain-of-thought reflection on a completed trade.

        Parameters
        ----------
        trade : dict
            Must contain: symbol, direction, entry_price, exit_price,
            pnl, signal (the signal that triggered the trade),
            fill_price, slippage (optional), hold_duration_s (optional).

        Returns
        -------
        ReasoningChain
            Completed reasoning chain with conclusion and diagnostics.
        """
        symbol = trade.get("symbol", "?")
        pnl = trade.get("pnl", 0.0)
        direction = trade.get("direction", "long")
        entry_price = trade.get("entry_price", 0.0)
        exit_price = trade.get("exit_price", 0.0)
        signal = trade.get("signal", {})
        slippage = trade.get("slippage", 0.0)
        hold_duration = trade.get("hold_duration_s", 0)

        chain = self._engine.start_chain(
            topic=f"Post-trade reflection: {symbol} {direction} P&L={pnl:+.4f}"
        )

        # 1. Observe outcome
        outcome = "win" if pnl > 0 else ("loss" if pnl < 0 else "breakeven")
        chain.add_step(
            ReasoningStepType.OBSERVATION,
            f"Trade closed: {direction} {symbol} entry={entry_price} exit={exit_price} "
            f"P&L={pnl:+.6f} ({outcome})",
            confidence=0.99,
        )

        # 2. Analyse signal quality
        signal_score = signal.get("confidence", signal.get("score", 0.5))
        signal_type = signal.get("type", signal.get("strategy", "unknown"))
        chain.add_step(
            ReasoningStepType.OBSERVATION,
            f"Triggering signal: type={signal_type}, confidence={signal_score:.2f}",
            confidence=0.90,
        )

        # 3. Analyse signal decomposition
        active_signals = trade.get("active_signals", [])
        if active_signals:
            chain.add_step(
                ReasoningStepType.OBSERVATION,
                f"Active signals at entry: {', '.join(str(s) for s in active_signals)}",
                confidence=0.85,
            )

        # 4. Hypothesise root cause
        diagnosis = self._diagnose(trade, signal_score, slippage, hold_duration)
        chain.add_step(
            ReasoningStepType.HYPOTHESIS,
            diagnosis["hypothesis"],
            confidence=diagnosis["confidence"],
        )

        # 5. Evidence
        for ev in diagnosis.get("evidence", []):
            chain.add_step(
                ReasoningStepType.EVIDENCE,
                ev["text"],
                confidence=ev.get("confidence", 0.7),
            )

        # 6. Conclusion
        chain.add_step(
            ReasoningStepType.INFERENCE,
            f"Root cause category: {diagnosis['category']}",
            confidence=diagnosis["confidence"],
        )

        chain.finalize(
            conclusion=(
                f"{outcome.upper()} on {symbol} — "
                f"primary issue: {diagnosis['category']} — "
                f"{diagnosis['recommendation']}"
            )
        )

        return chain

    def create_detailed_journal(
        self,
        trade: dict[str, Any],
        chain: ReasoningChain | None = None,
    ) -> DetailedTradeJournal:
        """Create a detailed trade journal entry with chart data and what-if analysis.

        Parameters
        ----------
        trade : dict
            Complete trade data.
        chain : ReasoningChain | None
            The reflection chain (if already computed).

        Returns
        -------
        DetailedTradeJournal
            Full journal entry with reasoning, chart, and what-if.
        """
        symbol = trade.get("symbol", "?")
        direction = trade.get("direction", "long")
        pnl = trade.get("pnl", 0.0)
        entry_price = trade.get("entry_price", 0.0)
        exit_price = trade.get("exit_price", 0.0)
        stop_loss = trade.get("stop_loss", 0.0)
        take_profit = trade.get("take_profit", 0.0)
        signal = trade.get("signal", {})
        hold_duration = trade.get("hold_duration_s", 0)
        quantity = trade.get("quantity", 0.0)

        # Build chart annotation
        chart = ChartAnnotation(
            entry_annotation=PriceLevel(
                price=entry_price,
                label=f"Entry {direction}",
                level_type="entry",
                timestamp=trade.get("entry_timestamp", 0),
                color="#2196F3",
            ),
            exit_annotation=PriceLevel(
                price=exit_price,
                label=f"Exit ({'win' if pnl > 0 else 'loss'})",
                level_type="exit",
                timestamp=trade.get("exit_timestamp", 0),
                color="#4CAF50" if pnl > 0 else "#F44336",
            ),
            stop_loss=PriceLevel(
                price=stop_loss,
                label="Stop Loss",
                level_type="stop_loss",
                color="#FF9800",
            ) if stop_loss else None,
            take_profit=PriceLevel(
                price=take_profit,
                label="Take Profit",
                level_type="take_profit",
                color="#8BC34A",
            ) if take_profit else None,
            max_favorable_excursion=trade.get("max_favorable_excursion", 0),
            max_adverse_excursion=trade.get("max_adverse_excursion", 0),
        )

        # Add support/resistance levels if available
        for level in trade.get("key_levels", []):
            chart.key_levels.append(PriceLevel(
                price=level.get("price", 0),
                label=level.get("label", ""),
                level_type=level.get("type", "support"),
                color="#9E9E9E",
            ))

        # Signal decomposition
        signal_scores: dict[str, float] = {}
        active_signals = trade.get("active_signals", [])
        for sig_name in (active_signals or []):
            signal_scores[str(sig_name)] = signal.get("confidence", 0.5)
        if not signal_scores and signal.get("strategy"):
            signal_scores[signal["strategy"]] = signal.get("confidence", 0.5)

        dominant = max(signal_scores, key=signal_scores.get) if signal_scores else ""
        agreement = 0.0
        if signal_scores:
            scores = list(signal_scores.values())
            if len(scores) > 1:
                # Agreement = 1 - normalized std dev of scores
                import statistics as stats
                mean_score = stats.mean(scores)
                std_score = stats.stdev(scores) if len(scores) > 1 else 0
                agreement = max(0, 1 - (std_score / max(mean_score, 0.01)))
            else:
                agreement = 1.0

        # R-multiple
        risk_amount = abs(entry_price - stop_loss) * quantity if stop_loss else abs(pnl)
        r_multiple = pnl / risk_amount if risk_amount > 0 else 0.0

        # Generate what-if analysis
        what_if = self._what_if.analyze(trade, chain)

        # Entry reasoning from chain
        entry_reasoning = ""
        exit_reasoning = ""
        if chain:
            for step in chain.steps:
                if step.step_type == ReasoningStepType.OBSERVATION and "entry" in step.content.lower():
                    entry_reasoning = step.content
                if step.step_type == ReasoningStepType.HYPOTHESIS:
                    exit_reasoning = step.content

        journal = DetailedTradeJournal(
            trade_id=trade.get("trade_id", ""),
            symbol=symbol,
            direction=direction,
            strategy=signal.get("type", signal.get("strategy", "unknown")),
            entry_reasoning=entry_reasoning or f"Signal: {signal.get('strategy', 'unknown')} at {entry_price}",
            entry_signals=[{"name": k, "score": v} for k, v in signal_scores.items()],
            entry_confidence=signal.get("confidence", signal.get("score", 0.5)),
            entry_regime=trade.get("regime", "unknown"),
            entry_timestamp=trade.get("entry_timestamp", 0),
            entry_price=entry_price,
            entry_slippage_bps=trade.get("entry_slippage", 0),
            exit_reasoning=exit_reasoning or f"Trade closed at {exit_price}",
            exit_type=trade.get("exit_type", "signal"),
            exit_price=exit_price,
            exit_timestamp=trade.get("exit_timestamp", 0),
            exit_slippage_bps=trade.get("exit_slippage", 0),
            quantity=quantity,
            position_value=entry_price * quantity,
            risk_amount=risk_amount,
            pnl=pnl,
            pnl_pct=((exit_price - entry_price) / entry_price * 100) if entry_price > 0 else 0,
            hold_duration_s=hold_duration,
            r_multiple=r_multiple,
            chart=chart,
            what_if=what_if,
            signal_scores=signal_scores,
            dominant_signal=dominant,
            signal_agreement=agreement,
        )

        # Auto-tag
        if pnl > 0:
            journal.tags.append("winner")
        elif pnl < 0:
            journal.tags.append("loser")
        else:
            journal.tags.append("breakeven")

        if abs(r_multiple) >= 2:
            journal.tags.append("big_win" if pnl > 0 else "big_loss")

        if trade.get("regime"):
            journal.tags.append(f"regime:{trade['regime']}")

        # Extract lessons from what-if
        if what_if.primary_lesson:
            journal.lessons.append(what_if.primary_lesson)
        for wrong in what_if.what_went_wrong:
            journal.lessons.append(wrong)

        return journal

    # -- internals --

    @staticmethod
    def _diagnose(
        trade: dict[str, Any],
        signal_score: float,
        slippage: float,
        hold_duration: float,
    ) -> dict[str, Any]:
        """Determine the root cause category and generate evidence."""
        pnl = trade.get("pnl", 0.0)
        entry_price = trade.get("entry_price", 1.0)
        price_move = abs(trade.get("exit_price", 0) - entry_price)
        expected_move = trade.get("expected_move", price_move * 1.2)

        evidence: list[dict[str, Any]] = []
        category = "unknown"

        # Check signal quality
        signal_weak = signal_score < 0.4
        if signal_weak and pnl < 0:
            category = "signal"
            evidence.append({
                "text": f"Low signal confidence ({signal_score:.2f}) combined with loss",
                "confidence": 0.8,
            })

        # Check execution (slippage)
        high_slippage = slippage > 0.005  # >0.5%
        if high_slippage:
            category = "execution" if category == "unknown" else category
            evidence.append({
                "text": f"High slippage detected ({slippage:.4f})",
                "confidence": 0.75,
            })

        # Check timing (held too long or too short)
        if hold_duration > 0 and expected_move > 0:
            capture_ratio = price_move / expected_move if expected_move else 0
            if capture_ratio < 0.3 and pnl < 0:
                category = "timing" if category == "unknown" else category
                evidence.append({
                    "text": f"Only captured {capture_ratio:.0%} of expected move",
                    "confidence": 0.7,
                })

        # Check risk management
        max_adverse = trade.get("max_adverse_excursion", 0)
        stop_loss = trade.get("stop_loss", 0)
        if stop_loss and entry_price and max_adverse:
            stop_distance = abs(entry_price - stop_loss)
            if max_adverse > stop_distance * 1.5 and pnl < 0:
                category = "risk" if category == "unknown" else category
                evidence.append({
                    "text": f"Max adverse excursion ({max_adverse:.4f}) exceeded stop distance ({stop_distance:.4f})",
                    "confidence": 0.75,
                })

        if category == "unknown":
            category = "signal" if pnl < 0 else "execution"

        hypothesis_map = {
            "signal": "The signal was weak or poorly calibrated for current conditions",
            "execution": "Execution quality degraded the trade outcome (slippage, fills)",
            "timing": "Entry/exit timing was suboptimal relative to price movement",
            "risk": "Risk management parameters did not adequately protect capital",
        }
        recommendation_map = {
            "signal": "Adjust strategy weights and increase confluence threshold",
            "execution": "Adjust position sizing or use limit orders",
            "timing": "Tighten entry criteria and review exit rules",
            "risk": "Adjust stop loss distance and review risk limits",
        }

        return {
            "category": category,
            "hypothesis": hypothesis_map.get(category, "Root cause unclear"),
            "confidence": min(0.5 + len(evidence) * 0.1, 0.9),
            "evidence": evidence,
            "recommendation": recommendation_map.get(category, "Review trade parameters"),
        }


# ──────────────────────────────────────────────────────────────────────
# CorrectionEngine
# ──────────────────────────────────────────────────────────────────────


class CorrectionEngine:
    """Generate and manage corrections from post-trade reflections.

    Corrections are stored in memory and applied to subsequent trades.
    """

    # Parameter adjustment templates keyed by (category, outcome)
    _ADJUSTMENTS: dict[tuple[str, str], dict[str, Any]] = {
        ("signal", "loss"): {
            "parameter": "min_confluence_score",
            "delta": 0.05,
            "reason": "Raise confluence threshold after signal-driven loss",
        },
        ("execution", "loss"): {
            "parameter": "position_size_pct",
            "delta": -0.02,
            "reason": "Reduce position size after execution-driven loss",
        },
        ("timing", "loss"): {
            "parameter": "entry_patience_bars",
            "delta": 1,
            "reason": "Increase entry patience after timing-driven loss",
        },
        ("risk", "loss"): {
            "parameter": "stop_loss_atr_mult",
            "delta": 0.2,
            "reason": "Widen stop after risk management failure",
        },
        ("signal", "win"): {
            "parameter": "min_confluence_score",
            "delta": -0.02,
            "reason": "Slightly relax confluence after signal-driven win",
        },
    }

    # Parameter bounds: (min, max) — prevents unbounded drift
    _PARAM_BOUNDS: dict[str, tuple[float, float]] = {
        "min_confluence_score": (0.1, 0.95),
        "position_size_pct": (0.001, 0.1),
        "entry_patience_bars": (1, 20),
        "stop_loss_atr_mult": (0.5, 5.0),
    }

    def __init__(self) -> None:
        self._corrections: list[Correction] = []

    def generate(
        self,
        chain: ReasoningChain,
        trade: dict[str, Any],
        current_params: dict[str, Any] | None = None,
    ) -> Correction | None:
        """Generate a correction from a reflection chain.

        Returns None if no correction is warranted (e.g. breakeven).
        """
        pnl = trade.get("pnl", 0.0)
        if pnl == 0:
            return None

        outcome = "win" if pnl > 0 else "loss"

        # Extract category from the inference step
        category = "signal"
        for step in reversed(chain.steps):
            if step.step_type == ReasoningStepType.INFERENCE:
                if "signal" in step.content.lower():
                    category = "signal"
                elif "execution" in step.content.lower():
                    category = "execution"
                elif "timing" in step.content.lower():
                    category = "timing"
                elif "risk" in step.content.lower():
                    category = "risk"
                break

        key = (category, outcome)
        template = self._ADJUSTMENTS.get(key)
        if not template:
            return None

        current = (current_params or {}).get(template["parameter"], 0)
        new_value = current + template["delta"]

        # Clamp to valid bounds to prevent unbounded parameter drift
        bounds = self._PARAM_BOUNDS.get(template["parameter"])
        if bounds:
            new_value = max(bounds[0], min(bounds[1], new_value))

        correction = Correction(
            category=category,
            parameter=template["parameter"],
            old_value=current,
            new_value=new_value,
            reason=template["reason"],
            impact_score=abs(pnl) / max(abs(pnl) + 1.0, 1.0),  # bounded 0–1
        )

        self._corrections.append(correction)
        logger.info(
            "correction_engine.generated",
            category=category,
            parameter=correction.parameter,
            impact=correction.impact_score,
        )
        return correction

    def get_active_corrections(self, max_age_s: float = 86400) -> list[Correction]:
        """Return unapplied corrections within max_age seconds."""
        now = time.time()
        return [
            c for c in self._corrections
            if not c.applied and (now - c.created_at) < max_age_s
        ]

    def apply_corrections(
        self,
        params: dict[str, Any],
        max_corrections: int = 5,
    ) -> dict[str, Any]:
        """Apply active corrections to a parameter dict.

        Returns a new dict with adjusted values.
        """
        adjusted = dict(params)
        applied = 0

        for correction in self.get_active_corrections():
            if applied >= max_corrections:
                break
            param = correction.parameter
            if param in adjusted:
                adjusted[param] = correction.new_value
            else:
                adjusted[param] = correction.new_value
            correction.applied = True
            applied += 1

        return adjusted

    def store_lessons(self, memory: EpisodicMemory, episode: TradeEpisode) -> None:
        """Store correction reasons as lessons on the episode."""
        recent = self.get_active_corrections(max_age_s=3600)
        for c in recent:
            lesson = f"[{c.category}] {c.reason} (impact={c.impact_score:.2f})"
            if lesson not in episode.lessons:
                episode.lessons.append(lesson)


# ──────────────────────────────────────────────────────────────────────
# SkillCreator
# ──────────────────────────────────────────────────────────────────────


class SkillCreator:
    """Extract reusable trade skills from repeated winning patterns.

    After 5+ similar wins with the same pattern, creates a skill.
    Skills are promoted/demoted based on ongoing success rate.
    Max 20 active skills (bounded).
    """

    def __init__(self, min_wins: int = 5, max_skills: int = MAX_ACTIVE_SKILLS) -> None:
        self._skills: dict[str, TradeSkill] = {}
        self._min_wins = min_wins
        self._max_skills = max_skills

    def record_trade(self, trade: dict[str, Any], memory: EpisodicMemory) -> TradeSkill | None:
        """Record a trade and check if it should create or update a skill.

        Returns the created/updated skill, or None.
        """
        symbol = trade.get("symbol", "")
        signal = trade.get("signal", {})
        pnl = trade.get("pnl", 0.0)
        direction = trade.get("direction", "long")

        # Build pattern key from signal characteristics
        pattern_key = self._extract_pattern_key(signal, symbol, direction)

        # Find existing skill with matching pattern
        existing = self._find_matching_skill(pattern_key)

        if existing:
            # Update existing skill stats
            if pnl > 0:
                existing.win_count += 1
            else:
                existing.loss_count += 1
            existing.total_pnl += pnl

            # Demote if win rate drops below 40%
            if existing.win_count + existing.loss_count >= 10 and existing.win_rate < 0.4:
                existing.active = False
                logger.info("skill_creator.demoted", skill_id=existing.skill_id, win_rate=existing.win_rate)

            return existing

        # Count similar winning trades in memory
        ref_episode = self._trade_to_episode(trade)
        similar = memory.find_similar(ref_episode, top_k=10)
        similar_wins = sum(1 for ep, score in similar if ep.outcome == "win" and score > 0.6)

        if similar_wins >= self._min_wins:
            return self._create_skill(trade, pattern_key, similar_wins)

        return None

    def get_applicable_skills(self, trade: dict[str, Any]) -> list[TradeSkill]:
        """Find active skills whose conditions match the given trade context."""
        signal = trade.get("signal", {})
        symbol = trade.get("symbol", "")
        direction = trade.get("direction", "long")
        pattern_key = self._extract_pattern_key(signal, symbol, direction)

        applicable = []
        for skill in self._skills.values():
            if not skill.active:
                continue
            if self._patterns_compatible(skill.pattern, pattern_key):
                applicable.append(skill)

        # Sort by win rate descending
        applicable.sort(key=lambda s: s.win_rate, reverse=True)
        return applicable

    def prune(self) -> int:
        """Remove lowest-performing skills if over the cap.

        Returns number of skills pruned.
        """
        if len(self._skills) <= self._max_skills:
            return 0

        # Sort by success rate ascending (worst first)
        sorted_skills = sorted(
            self._skills.values(),
            key=lambda s: s.success_rate,
        )

        prunable = [s for s in sorted_skills if not s.active]
        # If still over cap, also prune lowest active
        if len(prunable) < len(self._skills) - self._max_skills:
            for s in sorted_skills:
                if s not in prunable:
                    prunable.append(s)
                if len(self._skills) - len(prunable) <= self._max_skills:
                    break

        count = 0
        for s in prunable[: len(self._skills) - self._max_skills]:
            self._skills.pop(s.skill_id, None)
            count += 1

        return count

    # -- internals --

    @staticmethod
    def _extract_pattern_key(signal: dict[str, Any], symbol: str, direction: str) -> str:
        """Create a comparable pattern key from signal attributes."""
        strategy = signal.get("type", signal.get("strategy", "default"))
        timeframe = signal.get("timeframe", "1h")
        confluence = round(signal.get("confidence", signal.get("score", 0.5)), 1)
        return f"{symbol}:{direction}:{strategy}:{timeframe}:c{confluence}"

    def _find_matching_skill(self, pattern_key: str) -> TradeSkill | None:
        for skill in self._skills.values():
            if self._patterns_compatible(skill.pattern, pattern_key):
                return skill
        return None

    @staticmethod
    def _patterns_compatible(skill_pattern: str, trade_pattern: str) -> bool:
        """Check if two pattern keys are compatible (fuzzy match on confluence bucket)."""
        sp = skill_pattern.split(":")
        tp = trade_pattern.split(":")
        if len(sp) < 4 or len(tp) < 4:
            return False
        # Match on symbol, direction, strategy, timeframe (ignore exact confluence)
        return sp[:4] == tp[:4]

    def _create_skill(self, trade: dict[str, Any], pattern_key: str, win_count: int) -> TradeSkill:
        signal = trade.get("signal", {})
        symbol = trade.get("symbol", "?")
        strategy = signal.get("type", signal.get("strategy", "unknown"))

        skill = TradeSkill(
            name=f"{symbol} {strategy} pattern",
            pattern=pattern_key,
            conditions={
                "symbol": symbol,
                "direction": trade.get("direction", "long"),
                "strategy": strategy,
                "timeframe": signal.get("timeframe", "1h"),
            },
            action_template={
                "action": trade.get("direction", "long"),
                "position_size_pct": 0.02,
                "stop_loss_atr_mult": 2.0,
                "take_profit_atr_mult": 3.0,
            },
            win_count=win_count,
            loss_count=0,
            total_pnl=trade.get("pnl", 0.0),
        )

        self._skills[skill.skill_id] = skill
        self.prune()

        logger.info(
            "skill_creator.new_skill",
            skill_id=skill.skill_id,
            name=skill.name,
            win_count=win_count,
        )
        return skill

    @staticmethod
    def _trade_to_episode(trade: dict[str, Any]) -> TradeEpisode:
        """Convert a trade dict to a TradeEpisode for similarity search."""
        ep = TradeEpisode(
            symbol=trade.get("symbol", ""),
            direction=trade.get("direction", ""),
            entry_price=trade.get("entry_price", 0.0),
            exit_price=trade.get("exit_price", 0.0),
            pnl=trade.get("pnl", 0.0),
            pnl_pct=trade.get("pnl_pct", 0.0),
            indicators=trade.get("indicators", {}),
            market_context=trade.get("market_context", {}),
        )
        ep.finalize()
        return ep
