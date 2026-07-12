"""Trade explainability — human-readable rationale for every trade decision."""

from __future__ import annotations

import enum
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


class TradeDirection(enum.Enum):
    LONG = "long"
    SHORT = "short"
    HOLD = "hold"


@dataclass
class FactorContribution:
    """A single factor's contribution to a trade decision."""
    factor_name: str
    value: float
    weight: float
    contribution: float  # value * weight
    direction: str = ""  # "bullish" | "bearish" | "neutral"
    explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "factor": self.factor_name,
            "value": round(self.value, 4),
            "weight": round(self.weight, 4),
            "contribution": round(self.contribution, 4),
            "direction": self.direction,
            "explanation": self.explanation,
        }


@dataclass
class TradeExplanation:
    """Complete explanation for a trade decision."""
    explanation_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    symbol: str = ""
    direction: TradeDirection = TradeDirection.HOLD
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    position_size: float = 0.0
    confidence: float = 0.0
    factors: list[FactorContribution] = field(default_factory=list)
    risk_benefit: dict[str, Any] = field(default_factory=dict)
    rationale: str = ""
    audit_trail: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def summary(self) -> str:
        """One-line summary of the trade decision."""
        return (
            f"{self.direction.value.upper()} {self.symbol} @ {self.entry_price:.2f} | "
            f"Confidence: {self.confidence:.1%} | "
            f"R:R {self.risk_benefit.get('risk_reward_ratio', 'N/A')}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.explanation_id,
            "symbol": self.symbol,
            "direction": self.direction.value,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "position_size": self.position_size,
            "confidence": round(self.confidence, 4),
            "factors": [f.to_dict() for f in self.factors],
            "risk_benefit": self.risk_benefit,
            "rationale": self.rationale,
            "audit_trail": self.audit_trail,
        }


class TradeExplainer:
    """Generate human-readable explanations for trade decisions.

    Provides factor contribution breakdowns, risk/benefit analysis,
    and compliance-ready audit trails.
    """

    def __init__(self) -> None:
        self._explanations: dict[str, TradeExplanation] = {}

    def explain(
        self,
        symbol: str,
        direction: TradeDirection,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        position_size: float,
        factors: dict[str, tuple[float, float]],  # name → (value, weight)
        confidence: float = 0.5,
    ) -> TradeExplanation:
        """Generate a full trade explanation.

        Args:
            symbol: Ticker symbol.
            direction: Trade direction.
            entry_price: Planned entry price.
            stop_loss: Stop-loss price.
            take_profit: Take-profit price.
            position_size: Position size as fraction of portfolio.
            factors: Dict of factor_name → (value, weight).
            confidence: Overall trade confidence.

        Returns:
            Complete TradeExplanation.
        """
        explanation = TradeExplanation(
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            position_size=position_size,
            confidence=confidence,
        )

        # Factor contributions
        for name, (value, weight) in factors.items():
            contribution = value * weight
            if contribution > 0.05:
                dir_label = "bullish"
            elif contribution < -0.05:
                dir_label = "bearish"
            else:
                dir_label = "neutral"

            explanation.factors.append(FactorContribution(
                factor_name=name,
                value=value,
                weight=weight,
                contribution=contribution,
                direction=dir_label,
                explanation=self._explain_factor(name, value, weight),
            ))

        # Sort by absolute contribution descending
        explanation.factors.sort(
            key=lambda f: abs(f.contribution), reverse=True
        )

        # Risk/benefit analysis
        risk = abs(entry_price - stop_loss)
        reward = abs(take_profit - entry_price)
        rr_ratio = round(reward / risk, 2) if risk > 0 else 0.0

        explanation.risk_benefit = {
            "risk_per_share": round(risk, 2),
            "reward_per_share": round(reward, 2),
            "risk_reward_ratio": rr_ratio,
            "max_loss_pct": round(risk / entry_price * 100, 2) if entry_price > 0 else 0,
            "max_gain_pct": round(reward / entry_price * 100, 2) if entry_price > 0 else 0,
            "position_risk_pct": round(position_size * 100, 2),
        }

        # Rationale
        top_factors = explanation.factors[:3]
        factor_summary = ", ".join(
            f"{f.factor_name} ({f.direction})" for f in top_factors
        )
        explanation.rationale = (
            f"{'Long' if direction == TradeDirection.LONG else 'Short'} {symbol} at {entry_price:.2f} "
            f"driven primarily by {factor_summary}. "
            f"Risk/reward ratio of {rr_ratio}:1 with {position_size:.1%} portfolio allocation."
        )

        # Audit trail
        explanation.audit_trail = [
            f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Trade signal generated for {symbol}",
            f"Direction: {direction.value} | Entry: {entry_price} | SL: {stop_loss} | TP: {take_profit}",
            f"Confidence: {confidence:.1%} | Factors analyzed: {len(factors)}",
            f"Risk/reward: {rr_ratio}:1 | Position: {position_size:.1%}",
        ]

        self._explanations[explanation.explanation_id] = explanation
        return explanation

    def _explain_factor(self, name: str, value: float, weight: float) -> str:
        """Generate a human-readable explanation for a single factor."""
        abs_val = abs(value)
        if abs_val > 0.7:
            strength = "strong"
        elif abs_val > 0.4:
            strength = "moderate"
        else:
            strength = "weak"

        direction = "bullish" if value > 0 else "bearish" if value < 0 else "neutral"
        return f"{name}: {strength} {direction} signal (weight: {weight:.0%})"

    def get_explanation(self, explanation_id: str) -> TradeExplanation | None:
        return self._explanations.get(explanation_id)

    def list_explanations(self) -> list[dict[str, Any]]:
        return [
            {
                "id": e.explanation_id,
                "symbol": e.symbol,
                "direction": e.direction.value,
                "confidence": e.confidence,
                "summary": e.summary(),
            }
            for e in self._explanations.values()
        ]

    def audit_report(self, explanation_id: str) -> str:
        """Generate a compliance audit report for a trade decision."""
        exp = self._explanations.get(explanation_id)
        if exp is None:
            return f"No explanation found for {explanation_id}"

        lines = [
            "=" * 60,
            "TRADE DECISION AUDIT REPORT",
            "=" * 60,
            f"ID: {exp.explanation_id}",
            f"Symbol: {exp.symbol}",
            f"Direction: {exp.direction.value}",
            f"Entry: {exp.entry_price:.2f}",
            f"Stop-Loss: {exp.stop_loss:.2f}",
            f"Take-Profit: {exp.take_profit:.2f}",
            f"Position Size: {exp.position_size:.1%}",
            f"Confidence: {exp.confidence:.1%}",
            "",
            "FACTOR BREAKDOWN:",
        ]
        for f in exp.factors:
            lines.append(
                f"  {f.factor_name}: {f.contribution:+.4f} "
                f"({f.direction}) — {f.explanation}"
            )

        lines.extend([
            "",
            "RISK/REWARD:",
            f"  Risk: {exp.risk_benefit['max_loss_pct']:.1f}%",
            f"  Reward: {exp.risk_benefit['max_gain_pct']:.1f}%",
            f"  Ratio: {exp.risk_benefit['risk_reward_ratio']}:1",
            "",
            "RATIONALE:",
            f"  {exp.rationale}",
            "",
            "AUDIT TRAIL:",
        ])
        for entry in exp.audit_trail:
            lines.append(f"  {entry}")

        lines.append("=" * 60)
        return "\n".join(lines)
