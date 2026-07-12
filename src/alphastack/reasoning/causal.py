"""Causal inference for market price movements."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any
import uuid


class CausalStrength(enum.Enum):
    """Strength of a causal relationship."""
    NEGLIGIBLE = "negligible"
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    DOMINANT = "dominant"


@dataclass
class EventImpact:
    """The impact of a specific event on price."""
    event_type: str
    description: str
    price_change_pct: float
    volume_change_pct: float = 0.0
    timestamp: float = 0.0
    confidence: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "description": self.description,
            "price_change_pct": round(self.price_change_pct, 4),
            "volume_change_pct": round(self.volume_change_pct, 4),
            "confidence": round(self.confidence, 4),
        }


@dataclass
class CausalLink:
    """A causal relationship between an event and price movement."""
    link_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    cause: str = ""
    effect: str = ""
    strength: CausalStrength = CausalStrength.NEGLIGIBLE
    correlation: float = 0.0
    is_causal: bool = False  # True causation vs mere correlation
    evidence: list[str] = field(default_factory=list)
    counterfactual: str = ""
    confidence: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return {
            "link_id": self.link_id,
            "cause": self.cause,
            "effect": self.effect,
            "strength": self.strength.value,
            "correlation": round(self.correlation, 4),
            "is_causal": self.is_causal,
            "evidence": self.evidence,
            "counterfactual": self.counterfactual,
            "confidence": round(self.confidence, 4),
        }


class CausalInference:
    """Infer causal relationships between events and price movements.

    Distinguishes true causation from correlation using temporal ordering,
    confound detection, and counterfactual reasoning.
    """

    def __init__(self) -> None:
        self._links: dict[str, CausalLink] = {}
        self._event_history: list[EventImpact] = []

    def record_event(self, event: EventImpact) -> None:
        """Record a market event and its observed impact."""
        self._event_history.append(event)

    def infer_causality(
        self,
        cause: str,
        effect: str,
        correlation: float,
        temporal_precedence: bool = True,
        confound_present: bool = False,
        repeated_observation: bool = False,
    ) -> CausalLink:
        """Infer whether a cause-effect relationship is truly causal.

        Uses a simple heuristic scoring model:
        - Temporal precedence: cause happened before effect (+0.3)
        - High correlation: |r| > 0.5 (+0.2)
        - No confound: no known third variable (+0.2)
        - Repeated observation: seen multiple times (+0.2)
        - Dose-response: stronger cause → stronger effect (+0.1)

        Args:
            cause: Description of the cause.
            effect: Description of the effect.
            correlation: Observed correlation (-1 to 1).
            temporal_precedence: Did cause precede effect?
            confound_present: Is a confounding variable suspected?
            repeated_observation: Has this been observed multiple times?

        Returns:
            A CausalLink with causality assessment.
        """
        score = 0.0
        evidence: list[str] = []

        if temporal_precedence:
            score += 0.3
            evidence.append("Temporal precedence established")
        else:
            evidence.append("No temporal precedence — likely not causal")

        abs_corr = abs(correlation)
        if abs_corr > 0.5:
            score += 0.2
            evidence.append(f"Strong correlation ({correlation:.3f})")
        elif abs_corr > 0.3:
            score += 0.1
            evidence.append(f"Moderate correlation ({correlation:.3f})")
        else:
            evidence.append(f"Weak correlation ({correlation:.3f})")

        if not confound_present:
            score += 0.2
            evidence.append("No confounding variables detected")
        else:
            evidence.append("Confound present — causation uncertain")

        if repeated_observation:
            score += 0.2
            evidence.append("Repeatedly observed across multiple events")
        else:
            evidence.append("Single observation — needs replication")

        # Determine strength
        is_causal = score >= 0.6
        if score >= 0.8:
            strength = CausalStrength.STRONG
        elif score >= 0.6:
            strength = CausalStrength.MODERATE
        elif score >= 0.4:
            strength = CausalStrength.WEAK
        else:
            strength = CausalStrength.NEGLIGIBLE

        link = CausalLink(
            cause=cause,
            effect=effect,
            strength=strength,
            correlation=correlation,
            is_causal=is_causal,
            evidence=evidence,
            confidence=round(min(score, 1.0), 4),
        )
        self._links[link.link_id] = link
        return link

    def counterfactual(
        self,
        cause: str,
        effect: str,
        actual_outcome: float,
        estimated_without_cause: float,
    ) -> str:
        """Generate a counterfactual reasoning statement.

        Args:
            cause: The cause event.
            effect: The effect observed.
            actual_outcome: What actually happened (price change %).
            estimated_without_cause: Estimated outcome without the cause.

        Returns:
            Human-readable counterfactual statement.
        """
        diff = actual_outcome - estimated_without_cause
        direction = "higher" if diff > 0 else "lower"
        statement = (
            f"Without '{cause}', {effect} would likely have been "
            f"{abs(diff):.2f}% {direction} "
            f"(actual: {actual_outcome:+.2f}%, counterfactual: {estimated_without_cause:+.2f}%)"
        )

        # Update the latest link's counterfactual if exists
        if self._links:
            latest = list(self._links.values())[-1]
            latest.counterfactual = statement

        return statement

    def news_impact_score(self, headline: str, sentiment: float,
                          relevance: float = 1.0) -> EventImpact:
        """Score the impact of a news event.

        Args:
            headline: News headline text.
            sentiment: Sentiment score (-1 to 1).
            relevance: Relevance to the asset (0 to 1).

        Returns:
            EventImpact with estimated price impact.
        """
        # Base impact from sentiment magnitude
        base_impact = abs(sentiment) * 2.0  # max ~2% move

        # Scale by relevance
        scaled_impact = base_impact * relevance

        # Direction from sentiment sign
        price_change = scaled_impact if sentiment > 0 else -scaled_impact

        impact = EventImpact(
            event_type="news",
            description=headline,
            price_change_pct=round(price_change, 4),
            volume_change_pct=round(scaled_impact * 50, 2),  # volume spikes with impact
            confidence=round(min(relevance * (0.5 + abs(sentiment) * 0.5), 1.0), 4),
        )
        self.record_event(impact)
        return impact

    def correlation_vs_causation(
        self,
        var_a: str,
        var_b: str,
        correlation: float,
        potential_confound: str | None = None,
    ) -> dict[str, Any]:
        """Analyze whether a correlation implies causation.

        Args:
            var_a: First variable.
            var_b: Second variable.
            correlation: Observed correlation.
            potential_confound: Known confounding variable if any.

        Returns:
            Analysis dict with assessment and reasoning.
        """
        analysis: dict[str, Any] = {
            "variables": [var_a, var_b],
            "correlation": round(correlation, 4),
            "assessment": "unknown",
            "reasoning": [],
        }

        if potential_confound:
            analysis["reasoning"].append(
                f"Potential confound: {potential_confound} may drive both variables"
            )
            analysis["assessment"] = "likely_spurious"
            analysis["reasoning"].append(
                "High correlation with known confound → likely not causal"
            )
        elif abs(correlation) > 0.7:
            analysis["assessment"] = "worth_investigating"
            analysis["reasoning"].append(
                "Strong correlation — warrants causal investigation"
            )
            analysis["reasoning"].append(
                "Need temporal ordering and intervention evidence to confirm"
            )
        elif abs(correlation) > 0.4:
            analysis["assessment"] = "weak_association"
            analysis["reasoning"].append(
                "Moderate correlation — may be partially causal"
            )
        else:
            analysis["assessment"] = "unlikely_causal"
            analysis["reasoning"].append(
                "Weak correlation — unlikely to be causal"
            )

        return analysis

    def get_links(self) -> list[CausalLink]:
        """Get all inferred causal links."""
        return list(self._links.values())

    def get_event_history(self) -> list[EventImpact]:
        """Get all recorded events."""
        return list(self._event_history)

    def to_dict(self) -> dict[str, Any]:
        return {
            "links": [l.to_dict() for l in self._links.values()],
            "event_count": len(self._event_history),
        }
