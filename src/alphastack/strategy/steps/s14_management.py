"""Step 14: Trade Management — trailing stops, breakeven logic."""

from __future__ import annotations

from alphastack.strategy.context import (
    AlphaStackContext,
    Direction,
    ManagementAction,
    TradeManagement,
)
from alphastack.strategy.steps.base import AlphaStackStep


class TradeManagementStep(AlphaStackStep):
    step_number = 14
    step_name = "trade_management"

    async def execute(self, context: AlphaStackContext) -> AlphaStackContext:
        if context.confluence.direction == Direction.NONE:
            return context.update(management=TradeManagement())

        direction = context.confluence.direction
        current_price: float = context.market_data.get("close", 0.0)
        stop_price: float = context.stop_loss.price
        entry_price: float = context.market_data.get("entry_price", current_price)
        pip_size: float = context.market_data.get("pip_size", 0.0001)
        atr_pips: float = context.stop_loss.atr_value or context.market_data.get("atr_pips", 50.0)

        risk_distance = abs(entry_price - stop_price)
        actions: list[ManagementAction] = []

        # --- Breakeven: move stop to entry after 1R profit ---
        if direction == Direction.LONG:
            be_trigger = entry_price + risk_distance
        else:
            be_trigger = entry_price - risk_distance

        actions.append(
            ManagementAction(
                action="breakeven",
                trigger_price=round(be_trigger, 5),
                params={"description": "Move stop to entry after 1R profit"},
            )
        )

        # --- Trailing stop: ATR-based trail ---
        trail_distance = atr_pips * pip_size * 1.0  # 1x ATR trail
        if direction == Direction.LONG:
            trail_trigger = entry_price + risk_distance * 1.5  # start trailing at 1.5R
            actions.append(
                ManagementAction(
                    action="trail",
                    trigger_price=round(trail_trigger, 5),
                    params={
                        "trail_distance": round(trail_distance, 5),
                        "method": "atr",
                        "description": "Trail stop by 1x ATR once 1.5R reached",
                    },
                )
            )
        else:
            trail_trigger = entry_price - risk_distance * 1.5
            actions.append(
                ManagementAction(
                    action="trail",
                    trigger_price=round(trail_trigger, 5),
                    params={
                        "trail_distance": round(trail_distance, 5),
                        "method": "atr",
                        "description": "Trail stop by 1x ATR once 1.5R reached",
                    },
                )
            )

        # --- Partial close at TP1 ---
        if context.take_profit.levels:
            actions.append(
                ManagementAction(
                    action="partial_close",
                    trigger_price=context.take_profit.levels[0],
                    params={
                        "close_pct": 50,
                        "description": "Close 50% at TP1",
                    },
                )
            )

        mgmt = TradeManagement(actions=actions)
        return context.update(management=mgmt)
