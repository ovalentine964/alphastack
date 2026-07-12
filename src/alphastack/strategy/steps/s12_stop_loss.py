"""Step 12: Stop Loss — structure-based and ATR-based stop placement."""

from __future__ import annotations

from alphastack.strategy.context import AlphaStackContext, Direction, StopLoss
from alphastack.strategy.steps.base import AlphaStackStep


class StopLossStep(AlphaStackStep):
    step_number = 12
    step_name = "stop_loss"

    async def execute(self, context: AlphaStackContext) -> AlphaStackContext:
        md = context.market_data

        if context.confluence.direction == Direction.NONE:
            return context.update(stop_loss=StopLoss())

        direction = context.confluence.direction
        current_price: float = md.get("close", 0.0)
        pip_size: float = md.get("pip_size", 0.0001)
        atr_pips: float = md.get("atr_pips", 50.0)
        atr_multiplier: float = md.get("stop_atr_multiplier", 1.5)
        buffer_pips: float = md.get("stop_buffer_pips", 5.0)

        # --- Method 1: Structure-based stop ---
        structure_stop = self._structure_based_stop(context, direction, current_price, pip_size, buffer_pips)

        # --- Method 2: ATR-based stop ---
        atr_stop_distance = atr_pips * atr_multiplier * pip_size
        if direction == Direction.LONG:
            atr_stop = current_price - atr_stop_distance
        else:
            atr_stop = current_price + atr_stop_distance

        # Use the wider (more conservative) stop
        if direction == Direction.LONG:
            best_stop = min(structure_stop, atr_stop)
            stop_type = "structure" if structure_stop <= atr_stop else "atr"
        else:
            best_stop = max(structure_stop, atr_stop)
            stop_type = "structure" if structure_stop >= atr_stop else "atr"

        stop = StopLoss(
            price=round(best_stop, 5),
            stop_type=stop_type,
            atr_value=round(atr_pips, 2),
        )

        return context.update(stop_loss=stop)

    # ------------------------------------------------------------------

    @staticmethod
    def _structure_based_stop(
        context: AlphaStackContext,
        direction: Direction,
        current_price: float,
        pip_size: float,
        buffer_pips: float,
    ) -> float:
        """Place stop beyond the nearest swing point."""
        buffer = buffer_pips * pip_size

        if direction == Direction.LONG:
            swing_lows = context.structure.swing_lows
            if swing_lows:
                return min(swing_lows) - buffer
            # Fallback: 50 pips below
            return current_price - 50 * pip_size
        else:
            swing_highs = context.structure.swing_highs
            if swing_highs:
                return max(swing_highs) + buffer
            return current_price + 50 * pip_size
