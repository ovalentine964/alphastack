"""Chain-of-thought reasoning for market analysis."""

from __future__ import annotations

import enum
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


class ThoughtStepType(enum.Enum):
    """Types of thought steps in the reasoning chain."""
    OBSERVE = "observe"
    COLLECT_EVIDENCE = "collect_evidence"
    WEIGH_EVIDENCE = "weigh_evidence"
    HYPOTHESIZE = "hypothesize"
    VALIDATE = "validate"
    CONCLUDE = "conclude"


@dataclass
class ThoughtStep:
    """A single step in the chain of thought."""
    step_type: ThoughtStepType
    content: str
    confidence: float = 0.5
    supporting_data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.step_type.value,
            "content": self.content,
            "confidence": round(self.confidence, 4),
            "data_keys": list(self.supporting_data.keys()),
        }


@dataclass
class ThoughtChain:
    """A complete chain of thought with trace logging."""
    chain_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    context: str = ""
    steps: list[ThoughtStep] = field(default_factory=list)
    conclusion: str = ""
    final_confidence: float = 0.0
    trace_log: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def add_step(self, step: ThoughtStep) -> None:
        """Add a step and log it to the trace."""
        self.steps.append(step)
        self.trace_log.append(
            f"[{step.step_type.value}] {step.content} "
            f"(conf={step.confidence:.2f})"
        )

    def finalize(self, conclusion: str) -> float:
        """Compute final confidence and set conclusion."""
        self.conclusion = conclusion
        if not self.steps:
            self.final_confidence = 0.0
            return 0.0
        # Weighted average of step confidences
        weights = {
            ThoughtStepType.OBSERVE: 0.15,
            ThoughtStepType.COLLECT_EVIDENCE: 0.20,
            ThoughtStepType.WEIGH_EVIDENCE: 0.25,
            ThoughtStepType.HYPOTHESIZE: 0.15,
            ThoughtStepType.VALIDATE: 0.15,
            ThoughtStepType.CONCLUDE: 0.10,
        }
        total_weight = 0.0
        weighted_sum = 0.0
        for step in self.steps:
            w = weights.get(step.step_type, 0.1)
            weighted_sum += step.confidence * w
            total_weight += w
        self.final_confidence = round(
            weighted_sum / total_weight if total_weight > 0 else 0.0, 4
        )
        return self.final_confidence

    def to_dict(self) -> dict[str, Any]:
        return {
            "chain_id": self.chain_id,
            "context": self.context,
            "steps": [s.to_dict() for s in self.steps],
            "conclusion": self.conclusion,
            "final_confidence": self.final_confidence,
            "trace_log": self.trace_log,
        }


class ChainOfThought:
    """Step-by-step market analysis engine.

    Collects evidence, weighs it, forms hypotheses, and produces
    confidence-scored conclusions with full reasoning traces.
    """

    def __init__(self) -> None:
        self._chains: dict[str, ThoughtChain] = {}

    def start(self, context: str) -> ThoughtChain:
        """Start a new reasoning chain."""
        chain = ThoughtChain(context=context)
        self._chains[chain.chain_id] = chain
        return chain

    def observe(self, chain: ThoughtChain, observation: str,
                confidence: float = 0.9, data: dict[str, Any] | None = None) -> None:
        """Record an observation."""
        chain.add_step(ThoughtStep(
            step_type=ThoughtStepType.OBSERVE,
            content=observation,
            confidence=confidence,
            supporting_data=data or {},
        ))

    def collect_evidence(self, chain: ThoughtChain, evidence: str,
                         confidence: float = 0.7, data: dict[str, Any] | None = None) -> None:
        """Add a piece of evidence."""
        chain.add_step(ThoughtStep(
            step_type=ThoughtStepType.COLLECT_EVIDENCE,
            content=evidence,
            confidence=confidence,
            supporting_data=data or {},
        ))

    def weigh_evidence(self, chain: ThoughtChain, assessment: str,
                       confidence: float = 0.6) -> None:
        """Record evidence weighting assessment."""
        chain.add_step(ThoughtStep(
            step_type=ThoughtStepType.WEIGH_EVIDENCE,
            content=assessment,
            confidence=confidence,
        ))

    def hypothesize(self, chain: ThoughtChain, hypothesis: str,
                    confidence: float = 0.5) -> None:
        """State a hypothesis."""
        chain.add_step(ThoughtStep(
            step_type=ThoughtStepType.HYPOTHESIZE,
            content=hypothesis,
            confidence=confidence,
        ))

    def validate(self, chain: ThoughtChain, validation: str,
                 confidence: float = 0.6) -> None:
        """Record validation result."""
        chain.add_step(ThoughtStep(
            step_type=ThoughtStepType.VALIDATE,
            content=validation,
            confidence=confidence,
        ))

    def conclude(self, chain: ThoughtChain, conclusion: str) -> float:
        """Finalize the chain and return final confidence."""
        chain.add_step(ThoughtStep(
            step_type=ThoughtStepType.CONCLUDE,
            content=conclusion,
            confidence=0.5,  # Will be recalculated
        ))
        return chain.finalize(conclusion)

    def get_chain(self, chain_id: str) -> ThoughtChain | None:
        return self._chains.get(chain_id)

    def list_chains(self) -> list[dict[str, Any]]:
        return [
            {
                "chain_id": c.chain_id,
                "context": c.context,
                "steps": len(c.steps),
                "confidence": c.final_confidence,
            }
            for c in self._chains.values()
        ]

    def full_analysis(
        self,
        symbol: str,
        price: float,
        indicators: dict[str, float],
        volume_ratio: float = 1.0,
        sentiment: float | None = None,
    ) -> ThoughtChain:
        """Run a complete chain-of-thought analysis.

        Args:
            symbol: Ticker symbol.
            price: Current price.
            indicators: Technical indicator values.
            volume_ratio: Current volume / average volume.
            sentiment: Optional sentiment score (-1 to 1).

        Returns:
            Completed ThoughtChain with conclusion.
        """
        chain = self.start(f"Analysis: {symbol} at {price}")

        # Observe
        self.observe(chain, f"Price at {price}, volume ratio {volume_ratio:.2f}", 0.95)

        # Collect evidence from indicators
        for name, value in indicators.items():
            self.collect_evidence(
                chain,
                f"{name} = {value:.4f}",
                confidence=0.8,
                data={name: value},
            )

        # Weigh evidence
        bullish_count = 0
        bearish_count = 0
        for name, value in indicators.items():
            if "rsi" in name.lower():
                if value < 30:
                    bullish_count += 1
                elif value > 70:
                    bearish_count += 1
            elif "macd" in name.lower():
                if value > 0:
                    bullish_count += 1
                else:
                    bearish_count += 1
            elif "sma" in name.lower() or "ema" in name.lower():
                if value > price:
                    bearish_count += 1  # price below MA
                else:
                    bullish_count += 1

        evidence_summary = (
            f"Bullish signals: {bullish_count}, Bearish signals: {bearish_count}"
        )
        self.weigh_evidence(chain, evidence_summary, confidence=0.7)

        # Hypothesize
        if bullish_count > bearish_count:
            direction = "bullish"
            hyp_conf = min(0.5 + 0.08 * (bullish_count - bearish_count), 0.85)
        elif bearish_count > bullish_count:
            direction = "bearish"
            hyp_conf = min(0.5 + 0.08 * (bearish_count - bullish_count), 0.85)
        else:
            direction = "neutral"
            hyp_conf = 0.5

        self.hypothesize(chain, f"Hypothesis: {direction} outlook", confidence=hyp_conf)

        # Validate with volume and sentiment
        vol_conf = 0.6
        if volume_ratio > 1.5 and direction == "bullish":
            vol_conf = 0.8
        elif volume_ratio > 1.5 and direction == "bearish":
            vol_conf = 0.8
        self.validate(
            chain,
            f"Volume ratio {volume_ratio:.2f} {'confirms' if vol_conf > 0.65 else 'weakens'} {direction} hypothesis",
            confidence=vol_conf,
        )

        if sentiment is not None:
            sent_conf = 0.5 + abs(sentiment) * 0.3
            self.validate(
                chain,
                f"Sentiment {sentiment:+.2f} — {'supports' if (sentiment > 0) == (direction == 'bullish') else 'contradicts'} direction",
                confidence=sent_conf,
            )

        # Conclude
        action = "long" if direction == "bullish" else (
            "short" if direction == "bearish" else "hold"
        )
        self.conclude(chain, f"Signal: {direction} → {action} {symbol}")
        return chain
