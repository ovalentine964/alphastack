"""Step 13: Take Profit — risk:reward targets with partial TP levels."""

from __future__ import annotations

from alphastack.strategy.context import AlphaStackContext, Direction, TakeProfit
from alphastack.strategy.steps.base import AlphaStackStep


class TakeProfitStep(AlphaStackStep):
    step_number = 13
    step_name = "take_profit"

    async def execute(self, context: AlphaStackContext) -> AlphaStackContext:
        if context.confluence.direction == Direction.NONE:
            return context.update(take_profit=TakeProfit())

        direction = context.confluence.direction
        current_price: float = context.market_data.get("close", 0.0)
        stop_price: float = context.stop_loss.price
        pip_size: float = context.market_data.get("pip_size", 0.0001)

        # Risk distance
        risk_distance = abs(current_price - stop_price)
        if risk_distance == 0:
            return context.update(take_profit=TakeProfit())

        # Default R:R multipliers for partial TPs
        rr_multipliers: list[float] = context.market_data.get("rr_multipliers", [1.5, 2.5, 4.0])

        tp_levels: list[float] = []
        for rr in rr_multipliers:
            if direction == Direction.LONG:
                tp = current_price + risk_distance * rr
            else:
                tp = current_price - risk_distance * rr
            tp_levels.append(round(tp, 5))

        # Overall R:R (use the first TP as primary)
        rr_ratio = rr_multipliers[0] if rr_multipliers else 0.0

        # Override with nearest S/R level if it's closer than TP1
        if direction == Direction.LONG and context.sr_levels.resistance:
            nearest_res = min(context.sr_levels.resistance, key=lambda l: abs(l.price - tp_levels[0]))
            if nearest_res.price < tp_levels[0] and nearest_res.price > current_price:
                tp_levels[0] = round(nearest_res.price, 5)
        elif direction == Direction.SHORT and context.sr_levels.support:
            nearest_sup = min(context.sr_levels.support, key=lambda l: abs(l.price - tp_levels[0]))
            if nearest_sup.price > tp_levels[0] and nearest_sup.price < current_price:
                tp_levels[0] = round(nearest_sup.price, 5)

        tp = TakeProfit(levels=tp_levels, rr_ratio=round(rr_ratio, 2))
        return context.update(take_profit=tp)
