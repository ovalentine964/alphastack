"""Step 15: Exit Conditions — time-based exits, signal invalidation."""

from __future__ import annotations

from datetime import timedelta

from alphastack.strategy.context import AlphaStackContext, Direction, ExitSignal
from alphastack.strategy.steps.base import AlphaStackStep


class ExitConditions(AlphaStackStep):
    step_number = 15
    step_name = "exit_conditions"

    async def execute(self, context: AlphaStackContext) -> AlphaStackContext:
        if context.confluence.direction == Direction.NONE:
            return context.update(exit_signal=ExitSignal())

        md = context.market_data
        direction = context.confluence.direction
        current_price: float = md.get("close", 0.0)
        entry_price: float = md.get("entry_price", current_price)
        entry_time = md.get("entry_time")
        max_hold_hours: int = md.get("max_hold_hours", 48)

        reasons: list[str] = []
        should_exit = False

        # --- Time-based exit ---
        if entry_time is not None:
            max_hold = timedelta(hours=max_hold_hours)
            if context.timestamp - entry_time > max_hold:
                should_exit = True
                reasons.append(f"Max hold time ({max_hold_hours}h) exceeded")

        # --- Signal invalidation: structure flip ---
        if direction == Direction.LONG and context.structure.direction == Direction.SHORT:
            should_exit = True
            reasons.append("Structure flipped bearish — signal invalidated")
        elif direction == Direction.SHORT and context.structure.direction == Direction.LONG:
            should_exit = True
            reasons.append("Structure flipped bullish — signal invalidated")

        # --- RSI reversal ---
        if direction == Direction.LONG and context.rsi.signal == "overbought":
            reasons.append("RSI overbought — consider tightening stop")
        elif direction == Direction.SHORT and context.rsi.signal == "oversold":
            reasons.append("RSI oversold — consider tightening stop")

        # --- Confluence drop ---
        if context.confluence.score < 25:
            should_exit = True
            reasons.append(f"Confluence dropped to {context.confluence.score:.0f} — below threshold")

        # --- Hit stop loss ---
        if direction == Direction.LONG and current_price <= context.stop_loss.price:
            should_exit = True
            reasons.append("Stop loss hit")
        elif direction == Direction.SHORT and current_price >= context.stop_loss.price:
            should_exit = True
            reasons.append("Stop loss hit")

        exit_signal = ExitSignal(
            should_exit=should_exit,
            reason=" | ".join(reasons) if reasons else "",
        )

        return context.update(exit_signal=exit_signal)
