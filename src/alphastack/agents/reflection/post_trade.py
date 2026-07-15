"""Post-trade reflection, correction engine, and skill creator.

Implements the self-correction learning loop:
  completed trade → reflection → corrections → skill extraction → memory
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
# PostTradeReflection
# ──────────────────────────────────────────────────────────────────────


class PostTradeReflection:
    """Reflect on a single completed trade using chain-of-thought reasoning.

    Identifies whether the signal, execution, timing, or risk management
    was the primary contributor to the outcome.
    """

    def __init__(self, reasoning_engine: ChainOfThoughtEngine | None = None) -> None:
        self._engine = reasoning_engine or ChainOfThoughtEngine()

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

        # 3. Hypothesise root cause
        diagnosis = self._diagnose(trade, signal_score, slippage, hold_duration)
        chain.add_step(
            ReasoningStepType.HYPOTHESIS,
            diagnosis["hypothesis"],
            confidence=diagnosis["confidence"],
        )

        # 4. Evidence
        for ev in diagnosis.get("evidence", []):
            chain.add_step(
                ReasoningStepType.EVIDENCE,
                ev["text"],
                confidence=ev.get("confidence", 0.7),
            )

        # 5. Conclusion
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
