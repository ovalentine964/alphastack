"""Chain-of-thought reasoning engine for market analysis."""

from __future__ import annotations

import enum
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


class ReasoningStepType(enum.Enum):
    """Types of reasoning steps."""
    OBSERVATION = "observation"
    HYPOTHESIS = "hypothesis"
    EVIDENCE = "evidence"
    INFERENCE = "inference"
    CONCLUSION = "conclusion"


@dataclass
class ReasoningStep:
    """A single step in a reasoning chain."""
    step_type: ReasoningStepType
    content: str
    confidence: float = 0.5  # 0.0 – 1.0
    evidence_refs: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReasoningChain:
    """A complete chain of reasoning steps leading to a conclusion."""
    chain_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    topic: str = ""
    steps: list[ReasoningStep] = field(default_factory=list)
    conclusion: str = ""
    overall_confidence: float = 0.0
    created_at: float = field(default_factory=time.time)

    def add_step(self, step_type: ReasoningStepType, content: str,
                 confidence: float = 0.5, **kwargs: Any) -> ReasoningStep:
        """Append a reasoning step."""
        step = ReasoningStep(
            step_type=step_type,
            content=content,
            confidence=confidence,
            **kwargs,
        )
        self.steps.append(step)
        return step

    def finalize(self, conclusion: str) -> float:
        """Compute overall confidence and set conclusion.

        The overall confidence is the product of all step confidences
        (compounding uncertainty), with a minimum floor of 0.01.
        """
        self.conclusion = conclusion
        if not self.steps:
            self.overall_confidence = 0.0
            return self.overall_confidence

        product = 1.0
        for step in self.steps:
            product *= max(0.01, step.confidence)
        # Normalize by number of steps to avoid runaway low scores
        n = len(self.steps)
        self.overall_confidence = round(product ** (1.0 / max(n, 1)), 4)
        return self.overall_confidence

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "chain_id": self.chain_id,
            "topic": self.topic,
            "steps": [
                {
                    "type": s.step_type.value,
                    "content": s.content,
                    "confidence": s.confidence,
                    "evidence_refs": s.evidence_refs,
                }
                for s in self.steps
            ],
            "conclusion": self.conclusion,
            "overall_confidence": self.overall_confidence,
        }


class ChainOfThoughtEngine:
    """Engine for structured multi-step market reasoning.

    Builds reasoning chains that collect observations, form hypotheses,
    weigh evidence, and arrive at explainable conclusions.
    """

    def __init__(self) -> None:
        self._chains: dict[str, ReasoningChain] = {}

    def start_chain(self, topic: str) -> ReasoningChain:
        """Begin a new reasoning chain."""
        chain = ReasoningChain(topic=topic)
        self._chains[chain.chain_id] = chain
        return chain

    def get_chain(self, chain_id: str) -> ReasoningChain | None:
        """Retrieve a reasoning chain by ID."""
        return self._chains.get(chain_id)

    def list_chains(self) -> list[dict[str, Any]]:
        """List all stored chains with summary info."""
        return [
            {
                "chain_id": c.chain_id,
                "topic": c.topic,
                "steps": len(c.steps),
                "confidence": c.overall_confidence,
            }
            for c in self._chains.values()
        ]

    def analyze_market_signal(
        self,
        symbol: str,
        price_data: dict[str, Any],
        indicators: dict[str, float],
        news_sentiment: float | None = None,
    ) -> ReasoningChain:
        """Run a full chain-of-thought analysis on a market signal.

        Args:
            symbol: Ticker symbol.
            price_data: Recent price info (open, high, low, close, volume).
            indicators: Technical indicator values.
            news_sentiment: Optional sentiment score (-1 to 1).

        Returns:
            Completed reasoning chain with conclusion.
        """
        chain = self.start_chain(topic=f"Market analysis for {symbol}")

        # Step 1: Observe current state
        close = price_data.get("close", 0)
        chain.add_step(
            ReasoningStepType.OBSERVATION,
            f"{symbol} closed at {close}",
            confidence=0.95,
        )

        # Step 2: Note technical indicators
        indicator_parts = []
        for name, value in indicators.items():
            indicator_parts.append(f"{name}={value:.4f}")
        chain.add_step(
            ReasoningStepType.OBSERVATION,
            f"Technical indicators: {', '.join(indicator_parts)}",
            confidence=0.90,
        )

        # Step 3: Form hypothesis from indicators
        bullish_signals = 0
        bearish_signals = 0
        for name, value in indicators.items():
            if "rsi" in name.lower():
                if value < 30:
                    bullish_signals += 1
                elif value > 70:
                    bearish_signals += 1
            elif "macd" in name.lower():
                if value > 0:
                    bullish_signals += 1
                else:
                    bearish_signals += 1

        if bullish_signals > bearish_signals:
            hypothesis = "Technical indicators suggest bullish momentum"
            hyp_conf = min(0.5 + 0.1 * (bullish_signals - bearish_signals), 0.85)
        elif bearish_signals > bullish_signals:
            hypothesis = "Technical indicators suggest bearish momentum"
            hyp_conf = min(0.5 + 0.1 * (bearish_signals - bullish_signals), 0.85)
        else:
            hypothesis = "Technical indicators are neutral"
            hyp_conf = 0.5

        chain.add_step(ReasoningStepType.HYPOTHESIS, hypothesis, confidence=hyp_conf)

        # Step 4: Incorporate news sentiment if available
        if news_sentiment is not None:
            if news_sentiment > 0.2:
                sentiment_note = "Positive news sentiment supports bullish case"
                s_conf = min(0.5 + news_sentiment * 0.3, 0.8)
            elif news_sentiment < -0.2:
                sentiment_note = "Negative news sentiment supports bearish case"
                s_conf = min(0.5 + abs(news_sentiment) * 0.3, 0.8)
            else:
                sentiment_note = "Neutral news sentiment — no directional bias"
                s_conf = 0.5
            chain.add_step(
                ReasoningStepType.EVIDENCE,
                sentiment_note,
                confidence=s_conf,
                evidence_refs=["news_sentiment"],
            )

        # Step 5: Infer direction
        direction = "bullish" if bullish_signals > bearish_signals else (
            "bearish" if bearish_signals > bullish_signals else "neutral"
        )
        chain.add_step(
            ReasoningStepType.INFERENCE,
            f"Aggregate analysis suggests {direction} outlook for {symbol}",
            confidence=hyp_conf,
        )

        # Step 6: Conclusion
        action = "consider long" if direction == "bullish" else (
            "consider short" if direction == "bearish" else "hold / wait"
        )
        chain.finalize(
            conclusion=f"Signal: {direction.upper()} — {action} for {symbol}"
        )

        return chain

    def to_dict(self) -> dict[str, Any]:
        """Serialize all chains."""
        return {cid: c.to_dict() for cid, c in self._chains.items()}
