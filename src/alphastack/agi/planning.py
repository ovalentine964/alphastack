"""Trade planning module with scenario analysis."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any
import uuid


class ScenarioType(enum.Enum):
    """Market scenario types."""
    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"


@dataclass
class TradeAction:
    """A planned trade action."""
    symbol: str
    direction: str  # "long" | "short"
    entry_price: float
    stop_loss: float
    take_profit: float
    position_size: float  # fraction of portfolio
    rationale: str = ""


@dataclass
class ScenarioPlan:
    """A plan for a specific market scenario."""
    scenario: ScenarioType
    probability: float  # 0.0 – 1.0
    actions: list[TradeAction] = field(default_factory=list)
    triggers: list[str] = field(default_factory=list)
    max_drawdown: float = 0.0
    expected_return: float = 0.0


@dataclass
class TradePlan:
    """A multi-day trade plan with scenario analysis."""
    plan_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    symbol: str = ""
    horizon_days: int = 5
    scenarios: list[ScenarioPlan] = field(default_factory=list)
    current_bias: ScenarioType | None = None
    created_at: float = field(default_factory=lambda: __import__("time").time())

    def risk_adjusted_score(self) -> float:
        """Compute a risk-adjusted expected return across scenarios.

        Returns probability-weighted expected return minus max drawdown penalty.
        """
        if not self.scenarios:
            return 0.0
        weighted_return = sum(
            s.probability * s.expected_return for s in self.scenarios
        )
        max_dd = max(s.max_drawdown for s in self.scenarios)
        # Penalize by 50% of max drawdown
        return round(weighted_return - 0.5 * max_dd, 4)

    def best_scenario(self) -> ScenarioPlan | None:
        """Return the scenario with the highest expected return."""
        if not self.scenarios:
            return None
        return max(self.scenarios, key=lambda s: s.expected_return)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "symbol": self.symbol,
            "horizon_days": self.horizon_days,
            "current_bias": self.current_bias.value if self.current_bias else None,
            "risk_adjusted_score": self.risk_adjusted_score(),
            "scenarios": [
                {
                    "scenario": s.scenario.value,
                    "probability": s.probability,
                    "expected_return": s.expected_return,
                    "max_drawdown": s.max_drawdown,
                    "actions": [
                        {
                            "symbol": a.symbol,
                            "direction": a.direction,
                            "entry": a.entry_price,
                            "stop_loss": a.stop_loss,
                            "take_profit": a.take_profit,
                            "size": a.position_size,
                            "rationale": a.rationale,
                        }
                        for a in s.actions
                    ],
                    "triggers": s.triggers,
                }
                for s in self.scenarios
            ],
        }


class TradePlanner:
    """Generate and manage multi-day trade plans with scenario analysis.

    Produces risk-adjusted plans that adapt to changing market conditions.
    """

    def __init__(self) -> None:
        self._plans: dict[str, TradePlan] = {}

    def create_plan(
        self,
        symbol: str,
        current_price: float,
        volatility: float,
        horizon_days: int = 5,
        portfolio_value: float = 100_000.0,
        max_risk_pct: float = 0.02,
    ) -> TradePlan:
        """Create a trade plan with bull/bear/sideways scenarios.

        Args:
            symbol: Ticker symbol.
            current_price: Current market price.
            volatility: Annualized volatility (e.g. 0.25 for 25%).
            horizon_days: Planning horizon in days.
            portfolio_value: Total portfolio value.
            max_risk_pct: Max risk per trade as fraction of portfolio.

        Returns:
            A TradePlan with three scenarios.
        """
        plan = TradePlan(symbol=symbol, horizon_days=horizon_days)

        # Daily volatility from annualized
        daily_vol = volatility / (252 ** 0.5)
        move_1d = current_price * daily_vol
        move_horizon = move_1d * (horizon_days ** 0.5)

        risk_amount = portfolio_value * max_risk_pct
        position_size = risk_amount / (move_horizon * 2) if move_horizon > 0 else 0

        # Bull scenario
        bull = ScenarioPlan(
            scenario=ScenarioType.BULL,
            probability=0.33,
            expected_return=round(move_horizon / current_price * 100, 2),
            max_drawdown=round(move_1d * 0.5 / current_price * 100, 2),
            triggers=["breakout above resistance", "positive earnings surprise"],
            actions=[TradeAction(
                symbol=symbol,
                direction="long",
                entry_price=current_price,
                stop_loss=round(current_price - 2 * move_1d, 2),
                take_profit=round(current_price + move_horizon * 1.5, 2),
                position_size=round(position_size / portfolio_value, 4),
                rationale="Bullish breakout play with momentum",
            )],
        )

        # Bear scenario
        bear = ScenarioPlan(
            scenario=ScenarioType.BEAR,
            probability=0.33,
            expected_return=round(move_horizon / current_price * 100, 2),
            max_drawdown=round(move_1d * 0.5 / current_price * 100, 2),
            triggers=["breakdown below support", "negative macro news"],
            actions=[TradeAction(
                symbol=symbol,
                direction="short",
                entry_price=current_price,
                stop_loss=round(current_price + 2 * move_1d, 2),
                take_profit=round(current_price - move_horizon * 1.5, 2),
                position_size=round(position_size / portfolio_value, 4),
                rationale="Bearish breakdown play with risk control",
            )],
        )

        # Sideways scenario
        sideways = ScenarioPlan(
            scenario=ScenarioType.SIDEWAYS,
            probability=0.34,
            expected_return=round(move_1d / current_price * 50, 2),
            max_drawdown=round(move_1d * 0.3 / current_price * 100, 2),
            triggers=["range-bound price action", "low volume"],
            actions=[TradeAction(
                symbol=symbol,
                direction="long",
                entry_price=round(current_price - move_1d, 2),
                stop_loss=round(current_price - 3 * move_1d, 2),
                take_profit=round(current_price + move_1d, 2),
                position_size=round(position_size * 0.5 / portfolio_value, 4),
                rationale="Range-bound mean-reversion play",
            )],
        )

        plan.scenarios = [bull, bear, sideways]
        self._plans[plan.plan_id] = plan
        return plan

    def adapt_plan(
        self,
        plan_id: str,
        new_scenario: ScenarioType,
        new_probability: float,
    ) -> TradePlan:
        """Adapt an existing plan to a shifted market regime.

        Adjusts scenario probabilities and rebalances actions.
        """
        plan = self._plans.get(plan_id)
        if plan is None:
            raise KeyError(f"Plan not found: {plan_id}")

        plan.current_bias = new_scenario
        remaining = 1.0 - new_probability
        for scenario in plan.scenarios:
            if scenario.scenario == new_scenario:
                scenario.probability = new_probability
            else:
                scenario.probability = remaining / max(
                    len(plan.scenarios) - 1, 1
                )
        return plan

    def get_plan(self, plan_id: str) -> TradePlan | None:
        return self._plans.get(plan_id)

    def list_plans(self) -> list[dict[str, Any]]:
        return [
            {
                "plan_id": p.plan_id,
                "symbol": p.symbol,
                "horizon": p.horizon_days,
                "score": p.risk_adjusted_score(),
            }
            for p in self._plans.values()
        ]
