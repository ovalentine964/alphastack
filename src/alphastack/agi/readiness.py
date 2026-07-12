"""AGI readiness assessment for trading systems."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any


class ReadinessLevel(enum.IntEnum):
    """AGI readiness levels for trading systems."""
    L1 = 1  # Narrow AI — single-task automation
    L2 = 2  # Multi-task — several coordinated capabilities
    L3 = 3  # Adaptive — learns and adjusts strategies
    L4 = 4  # Generalized — handles novel market conditions
    L5 = 5  # Superhuman — exceeds human trader performance


@dataclass
class CapabilityScore:
    """Score for a specific AI capability."""
    name: str
    current: float  # 0.0 – 1.0
    target: float  # 0.0 – 1.0
    description: str = ""

    @property
    def gap(self) -> float:
        return max(0.0, self.target - self.current)

    @property
    def achieved(self) -> bool:
        return self.current >= self.target


@dataclass
class GapAnalysis:
    """Identified gaps between current and required capabilities."""
    missing_capabilities: list[str] = field(default_factory=list)
    partial_capabilities: list[dict[str, Any]] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    priority_actions: list[str] = field(default_factory=list)


@dataclass
class IntegrationRoadmap:
    """Roadmap for advancing AGI readiness."""
    phases: list[dict[str, Any]] = field(default_factory=list)
    estimated_timeline_weeks: int = 0
    dependencies: dict[str, list[str]] = field(default_factory=dict)


_CAPABILITY_REGISTRY: dict[str, dict[str, Any]] = {
    "market_data_ingestion": {
        "description": "Real-time and historical market data processing",
        "level": ReadinessLevel.L1,
        "weight": 0.10,
    },
    "pattern_recognition": {
        "description": "Technical and fundamental pattern detection",
        "level": ReadinessLevel.L2,
        "weight": 0.12,
    },
    "risk_management": {
        "description": "Position sizing, stop-loss, portfolio risk",
        "level": ReadinessLevel.L2,
        "weight": 0.12,
    },
    "strategy_generation": {
        "description": "Creating and optimizing trading strategies",
        "level": ReadinessLevel.L3,
        "weight": 0.11,
    },
    "causal_reasoning": {
        "description": "Understanding cause-effect in markets",
        "level": ReadinessLevel.L3,
        "weight": 0.10,
    },
    "multi_timeframe_analysis": {
        "description": "Analyzing across different timeframes",
        "level": ReadinessLevel.L3,
        "weight": 0.09,
    },
    "natural_language_understanding": {
        "description": "News, reports, social media comprehension",
        "level": ReadinessLevel.L4,
        "weight": 0.08,
    },
    "adversarial_robustness": {
        "description": "Handling market manipulation and regime changes",
        "level": ReadinessLevel.L4,
        "weight": 0.08,
    },
    "meta_learning": {
        "description": "Learning how to learn new market patterns",
        "level": ReadinessLevel.L4,
        "weight": 0.10,
    },
    "self_improvement": {
        "description": "Autonomous strategy refinement",
        "level": ReadinessLevel.L5,
        "weight": 0.10,
    },
}


class AGIReadiness:
    """Assess and track AGI readiness of the trading system.

    Evaluates current capabilities against target levels, produces gap
    analyses, and generates integration roadmaps.
    """

    def __init__(self) -> None:
        self._scores: dict[str, CapabilityScore] = {}
        self._initialize_default_scores()

    def _initialize_default_scores(self) -> None:
        """Set conservative baseline scores."""
        for name, meta in _CAPABILITY_REGISTRY.items():
            self._scores[name] = CapabilityScore(
                name=name,
                current=0.0,
                target=meta["level"] / 5.0,
                description=meta["description"],
            )

    def update_score(self, capability: str, score: float) -> None:
        """Update the current score for a capability.

        Args:
            capability: Capability name.
            score: New score between 0.0 and 1.0.

        Raises:
            KeyError: If capability is not registered.
            ValueError: If score is outside [0, 1].
        """
        if capability not in self._scores:
            raise KeyError(f"Unknown capability: {capability}")
        if not 0.0 <= score <= 1.0:
            raise ValueError(f"Score must be in [0, 1], got {score}")
        self._scores[capability].current = score

    def get_score(self, capability: str) -> CapabilityScore:
        """Get the score object for a capability."""
        return self._scores[capability]

    def compute_readiness_level(self) -> ReadinessLevel:
        """Compute the overall readiness level based on weighted scores.

        Returns the highest level where all lower-level capabilities
        meet their targets.
        """
        level_scores: dict[int, list[tuple[float, float]]] = {}
        for name, score in self._scores.items():
            meta = _CAPABILITY_REGISTRY.get(name, {})
            level = meta.get("level", ReadinessLevel.L1)
            weight = meta.get("weight", 1.0)
            level_scores.setdefault(level.value, []).append(
                (score.current, weight)
            )

        achieved_level = ReadinessLevel.L1
        for level_val in sorted(level_scores.keys()):
            entries = level_scores[level_val]
            total_weight = sum(w for _, w in entries)
            if total_weight == 0:
                continue
            weighted = sum(s * w for s, w in entries) / total_weight
            if weighted >= 0.7:  # 70% threshold per level
                achieved_level = ReadinessLevel(level_val)
            else:
                break
        return achieved_level

    def compute_overall_score(self) -> float:
        """Compute the weighted overall readiness score (0–1)."""
        total_weight = 0.0
        weighted_sum = 0.0
        for name, score in self._scores.items():
            weight = _CAPABILITY_REGISTRY.get(name, {}).get("weight", 1.0)
            weighted_sum += score.current * weight
            total_weight += weight
        return weighted_sum / total_weight if total_weight > 0 else 0.0

    def gap_analysis(self) -> GapAnalysis:
        """Perform gap analysis identifying missing, partial, and strong capabilities."""
        analysis = GapAnalysis()
        for name, score in self._scores.items():
            if score.achieved:
                analysis.strengths.append(name)
            elif score.current < score.target * 0.3:
                analysis.missing_capabilities.append(name)
            else:
                analysis.partial_capabilities.append({
                    "name": name,
                    "current": score.current,
                    "target": score.target,
                    "gap": score.gap,
                })

        # Sort partials by gap descending (biggest gap = highest priority)
        analysis.partial_capabilities.sort(
            key=lambda x: x["gap"], reverse=True
        )
        analysis.priority_actions = [
            f"Improve {p['name']} from {p['current']:.1%} to {p['target']:.1%}"
            for p in analysis.partial_capabilities[:5]
        ]
        return analysis

    def generate_roadmap(self) -> IntegrationRoadmap:
        """Generate an integration roadmap based on current gaps."""
        roadmap = IntegrationRoadmap()
        gap = self.gap_analysis()

        # Phase 1: Fix missing capabilities
        if gap.missing_capabilities:
            roadmap.phases.append({
                "phase": 1,
                "name": "Foundation",
                "capabilities": gap.missing_capabilities,
                "goal": "Establish baseline for all core capabilities",
            })

        # Phase 2: Strengthen partial capabilities
        if gap.partial_capabilities:
            roadmap.phases.append({
                "phase": 2,
                "name": "Enhancement",
                "capabilities": [p["name"] for p in gap.partial_capabilities],
                "goal": "Bring all capabilities to target levels",
            })

        # Phase 3: Push toward L4/L5
        roadmap.phases.append({
            "phase": len(roadmap.phases) + 1,
            "name": "Advanced",
            "capabilities": ["meta_learning", "self_improvement"],
            "goal": "Achieve generalized and superhuman trading capabilities",
        })

        roadmap.estimated_timeline_weeks = len(roadmap.phases) * 12
        roadmap.dependencies = {
            "causal_reasoning": ["pattern_recognition", "market_data_ingestion"],
            "meta_learning": ["strategy_generation", "causal_reasoning"],
            "self_improvement": ["meta_learning", "adversarial_robustness"],
        }
        return roadmap

    def to_dict(self) -> dict[str, Any]:
        """Serialize the readiness state."""
        return {
            "level": self.compute_readiness_level().name,
            "overall_score": round(self.compute_overall_score(), 4),
            "capabilities": {
                name: {
                    "current": round(s.current, 4),
                    "target": round(s.target, 4),
                    "gap": round(s.gap, 4),
                    "achieved": s.achieved,
                }
                for name, s in self._scores.items()
            },
        }
