"""Step 12: Stop Loss — structure-based and ATR-based stop placement."""

from __future__ import annotations

from alphastack.strategy.context import AlphaStackContext, Direction, StopLoss
from alphastack.strategy.steps.base import AlphaStackStep
from alphastack.strategy.config import strategy_params


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
        atr_multiplier: float = md.get(
            "stop_atr_multiplier",
            strategy_params.get("stop_loss.atr_multiplier", 1.5),
        )
        buffer_pips: float = md.get(
            "stop_buffer_pips",
            strategy_params.get("stop_loss.buffer_pips", 5.0),
        )

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
        """Place stop beyond the nearest swing point.

        For LONG: nearest swing low *below* entry (not the absolute min).
        For SHORT: nearest swing high *above* entry (not the absolute max).
        This prevents stops from being placed excessively far away.
        """
        buffer = buffer_pips * pip_size

        if direction == Direction.LONG:
            swing_lows = context.structure.swing_lows
            # Filter to swing lows strictly below current price, pick the nearest
            candidates = [sl for sl in swing_lows if sl < current_price]
            if candidates:
                nearest = max(candidates)  # highest of the lows below price
                return nearest - buffer
            # Fallback: ATR-based distance (1.5 × ATR)
            atr_pips: float = context.market_data.get("atr_pips", 50.0)
            fallback_mult = strategy_params.get("stop_loss.fallback_atr_multiplier", 1.5)
            return current_price - atr_pips * fallback_mult * pip_size
        else:
            swing_highs = context.structure.swing_highs
            # Filter to swing highs strictly above current price, pick the nearest
            candidates = [sh for sh in swing_highs if sh > current_price]
            if candidates:
                nearest = min(candidates)  # lowest of the highs above price
                return nearest + buffer
            # Fallback: ATR-based distance
            atr_pips: float = context.market_data.get("atr_pips", 50.0)
            fallback_mult = strategy_params.get("stop_loss.fallback_atr_multiplier", 1.5)
            return current_price + atr_pips * fallback_mult * pip_size
