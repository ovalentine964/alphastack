"""Step 11: Position Sizing — risk-based sizing accounting for spread costs."""

from __future__ import annotations

from alphastack.strategy.context import AlphaStackContext, Direction, PositionSizing
from alphastack.strategy.steps.base import AlphaStackStep


class PositionSizingStep(AlphaStackStep):
    step_number = 11
    step_name = "position_sizing"

    async def execute(self, context: AlphaStackContext) -> AlphaStackContext:
        md = context.market_data

        # If no trade signal, zero size
        if context.confluence.direction == Direction.NONE:
            return context.update(sizing=PositionSizing())

        account_balance: float = md.get("account_balance", 10_000.0)
        risk_pct: float = md.get("risk_pct", 1.0)  # % of account to risk
        pip_size: float = md.get("pip_size", 0.0001)
        spread_pips: float = md.get("spread_pips", 1.5)
        pip_value: float = md.get("pip_value", 10.0)  # $ per pip per standard lot

        # Estimate stop distance (use ATR * multiplier or fixed from step 12)
        atr_pips: float = md.get("atr_pips", 50.0)
        stop_multiplier: float = md.get("stop_multiplier", 1.5)
        stop_distance_pips = atr_pips * stop_multiplier + spread_pips  # include spread

        if stop_distance_pips <= 0:
            return context.update(sizing=PositionSizing())

        # Risk in account currency
        risk_amount = account_balance * (risk_pct / 100)

        # Position size in standard lots
        position_size = risk_amount / (stop_distance_pips * pip_value)

        # Round down to 2 decimal places (micro-lot precision)
        position_size = max(round(position_size, 2), 0.01)

        sizing = PositionSizing(
            position_size=position_size,
            risk_amount=round(risk_amount, 2),
            risk_pct=risk_pct,
        )

        return context.update(sizing=sizing)
