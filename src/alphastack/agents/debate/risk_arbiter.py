"""Risk Arbiter — final decision maker in the debate system.

Scores the bull and bear reasoning chains using confidence-weighted voting,
then produces a final verdict: EXECUTE, REJECT, or MODIFY.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any

from alphastack.agi.reasoning import ReasoningChain, ReasoningStepType
from alphastack.utils.logger import get_logger

logger = get_logger(__name__)


class DebateVerdict(enum.Enum):
    """Possible debate outcomes."""
    EXECUTE = "execute"
    REJECT = "reject"
    MODIFY = "modify"


@dataclass
class DebateResult:
    """Complete result of a debate session."""

    verdict: DebateVerdict
    confidence: float  # 0.0 – 1.0
    bull_confidence: float
    bear_confidence: float
    reasoning: str
    modified_signal: dict[str, Any] | None = None
    transcript: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "confidence": self.confidence,
            "bull_confidence": self.bull_confidence,
            "bear_confidence": self.bear_confidence,
            "reasoning": self.reasoning,
            "modified_signal": self.modified_signal,
            "transcript": self.transcript,
        }


class RiskArbiter:
    """Evaluates bull and bear arguments and delivers a final verdict.

    Uses confidence-weighted voting: each side's conclusion confidence
    acts as a vote weight. The side with higher weighted confidence wins,
    with thresholds for MODIFY when the margin is thin.
    """

    # Thresholds
    EXECUTE_THRESHOLD = 0.55   # bull must exceed this to approve
    REJECT_THRESHOLD = 0.55    # bear must exceed this to reject
    MODIFY_MARGIN = 0.10       # if margin < this, suggest modification

    def __init__(self) -> None:
        self.name = "risk_arbiter"

    def adjudicate(
        self,
        signal: dict[str, Any],
        bull_chain: ReasoningChain,
        bear_chain: ReasoningChain,
        risk_context: dict[str, Any] | None = None,
    ) -> DebateResult:
        """Score both sides and produce a final verdict.

        Parameters
        ----------
        signal : dict
            The original trade signal.
        bull_chain : ReasoningChain
            The bull's completed reasoning chain.
        bear_chain : ReasoningChain
            The bear's completed reasoning chain.
        risk_context : dict | None
            Portfolio risk context (drawdown, positions, etc.).

        Returns
        -------
        DebateResult
            The arbiter's verdict with full reasoning and transcript.
        """
        symbol = signal.get("symbol", "UNKNOWN")
        side = signal.get("side", "long")

        bull_conf = bull_chain.overall_confidence
        bear_conf = bear_chain.overall_confidence

        # Apply risk context penalty if available
        risk_penalty = 0.0
        risk_notes: list[str] = []
        if risk_context:
            drawdown = risk_context.get("drawdown_pct", 0.0)
            daily_loss = risk_context.get("daily_loss_pct", 0.0)
            positions = risk_context.get("open_positions", 0)
            max_positions = risk_context.get("max_positions", 10)

            if drawdown > 5.0:
                penalty = min(drawdown / 100.0, 0.15)
                risk_penalty += penalty
                risk_notes.append(f"drawdown={drawdown:.1f}% (penalty={penalty:.3f})")
            if daily_loss > 2.0:
                penalty = min(daily_loss / 50.0, 0.10)
                risk_penalty += penalty
                risk_notes.append(f"daily_loss={daily_loss:.1f}% (penalty={penalty:.3f})")
            if positions >= max_positions:
                risk_penalty += 0.20
                risk_notes.append(f"max positions reached ({positions}/{max_positions})")

        # Apply penalty to bull confidence (makes it harder to execute)
        adjusted_bull = max(0.01, bull_conf - risk_penalty)
        adjusted_bear = bear_conf

        # Confidence-weighted vote
        margin = adjusted_bull - adjusted_bear
        total_weight = adjusted_bull + adjusted_bear
        bull_pct = adjusted_bull / total_weight if total_weight > 0 else 0.5
        bear_pct = adjusted_bear / total_weight if total_weight > 0 else 0.5

        # Determine verdict
        if adjusted_bull >= self.EXECUTE_THRESHOLD and margin > self.MODIFY_MARGIN:
            verdict = DebateVerdict.EXECUTE
            confidence = adjusted_bull
            reasoning = (
                f"Bull case wins: confidence={adjusted_bull:.3f} vs bear={adjusted_bear:.3f} "
                f"(margin={margin:.3f}). Signal strength and confluence support execution."
            )
            modified_signal = None

        elif adjusted_bear >= self.REJECT_THRESHOLD and margin < -self.MODIFY_MARGIN:
            verdict = DebateVerdict.REJECT
            confidence = adjusted_bear
            reasoning = (
                f"Bear case wins: confidence={adjusted_bear:.3f} vs bull={adjusted_bull:.3f} "
                f"(margin={margin:.3f}). Risk signals outweigh bullish thesis."
            )
            modified_signal = None

        elif abs(margin) <= self.MODIFY_MARGIN:
            # Thin margin — suggest modification (reduce size, tighten stops)
            verdict = DebateVerdict.MODIFY
            confidence = max(adjusted_bull, adjusted_bear)
            reasoning = (
                f"Debate inconclusive: bull={adjusted_bull:.3f}, bear={adjusted_bear:.3f} "
                f"(margin={margin:.3f}). Suggesting position size reduction and tighter stops."
            )
            modified_signal = self._build_modified_signal(signal, bull_pct, bear_pct)

        else:
            # Default to reject on ambiguity
            verdict = DebateVerdict.REJECT
            confidence = adjusted_bear
            reasoning = (
                f"Ambiguous outcome: bull={adjusted_bull:.3f}, bear={adjusted_bear:.3f}. "
                f"Defaulting to REJECT for capital preservation."
            )
            modified_signal = None

        # Add risk notes
        if risk_notes:
            reasoning += f" Risk factors: {'; '.join(risk_notes)}"

        # Build transcript
        transcript = self._build_transcript(
            signal, bull_chain, bear_chain,
            adjusted_bull, adjusted_bear, verdict, reasoning,
        )

        result = DebateResult(
            verdict=verdict,
            confidence=confidence,
            bull_confidence=adjusted_bull,
            bear_confidence=adjusted_bear,
            reasoning=reasoning,
            modified_signal=modified_signal,
            transcript=transcript,
        )

        logger.info(
            "debate.arbiter.verdict",
            symbol=symbol,
            verdict=verdict.value,
            bull_conf=adjusted_bull,
            bear_conf=adjusted_bear,
            margin=margin,
        )
        return result

    def _build_modified_signal(
        self,
        signal: dict[str, Any],
        bull_pct: float,
        bear_pct: float,
    ) -> dict[str, Any]:
        """Build a modified signal with reduced size and tighter stops."""
        modified = dict(signal)

        # Reduce position size based on bull confidence ratio
        original_qty = modified.get("quantity", 1.0)
        modified["quantity"] = round(original_qty * bull_pct, 4)
        modified["size_reduction_pct"] = round((1.0 - bull_pct) * 100, 1)

        # Tighten stop loss by 25%
        if modified.get("stop_loss") is not None:
            entry = modified.get("entry_price", modified.get("price", 0))
            sl = modified["stop_loss"]
            if entry > 0 and sl > 0:
                sl_distance = abs(entry - sl)
                tightened = sl_distance * 0.75
                if modified.get("side") == "long":
                    modified["stop_loss"] = round(entry - tightened, 2)
                else:
                    modified["stop_loss"] = round(entry + tightened, 2)
                modified["stop_tightened"] = True

        modified["debate_modification"] = (
            f"Size reduced by {modified['size_reduction_pct']}% "
            f"due to inconclusive debate (bull={bull_pct:.1%}, bear={bear_pct:.1%})"
        )
        return modified

    def _build_transcript(
        self,
        signal: dict[str, Any],
        bull_chain: ReasoningChain,
        bear_chain: ReasoningChain,
        adjusted_bull: float,
        adjusted_bear: float,
        verdict: DebateVerdict,
        reasoning: str,
    ) -> list[dict[str, Any]]:
        """Build a full audit transcript of the debate."""
        transcript: list[dict[str, Any]] = []

        # Round 1: Bull presents
        transcript.append({
            "round": 1,
            "speaker": "bull",
            "chain": bull_chain.to_dict(),
            "confidence": bull_chain.overall_confidence,
        })

        # Round 2: Bear presents
        transcript.append({
            "round": 2,
            "speaker": "bear",
            "chain": bear_chain.to_dict(),
            "confidence": bear_chain.overall_confidence,
        })

        # Round 3: Arbiter adjudication
        transcript.append({
            "round": 3,
            "speaker": "risk_arbiter",
            "adjusted_bull_confidence": adjusted_bull,
            "adjusted_bear_confidence": adjusted_bear,
            "verdict": verdict.value,
            "reasoning": reasoning,
        })

        return transcript
