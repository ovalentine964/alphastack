"""Step 5: Support & Resistance — key level identification and strength scoring."""

from __future__ import annotations

from collections import Counter

from alphastack.strategy.context import AlphaStackContext, Level, SRLevels
from alphastack.strategy.steps.base import AlphaStackStep


def _round_to_nearest(price: float, step: float) -> float:
    """Round price to the nearest *step* (e.g. 0.0050 for FX)."""
    return round(round(price / step) * step, 10)


class SupportResistance(AlphaStackStep):
    step_number = 5
    step_name = "support_resistance"

    async def execute(self, context: AlphaStackContext) -> AlphaStackContext:
        md = context.market_data

        highs: list[float] = md.get("highs", [])
        lows: list[float] = md.get("lows", [])
        closes: list[float] = md.get("closes", [])
        pip_size: float = md.get("pip_size", 0.0001)
        current_price: float = closes[-1] if closes else 0.0

        # Bucket prices to nearest round number / pivot
        bucket_step = pip_size * 50  # ~50-pip zones
        tolerance = pip_size * 20

        support_hits: Counter[float] = Counter()
        resistance_hits: Counter[float] = Counter()

        for low in lows:
            bucket = _round_to_nearest(low, bucket_step)
            support_hits[bucket] += 1

        for high in highs:
            bucket = _round_to_nearest(high, bucket_step)
            resistance_hits[bucket] += 1

        # Build support levels (below current price)
        support_levels = [
            Level(price=p, strength=min(hits / max(len(lows), 1), 1.0), touches=hits, label="support")
            for p, hits in support_hits.most_common(10)
            if p < current_price - tolerance
        ][:5]

        # Build resistance levels (above current price)
        resistance_levels = [
            Level(price=p, strength=min(hits / max(len(highs), 1), 1.0), touches=hits, label="resistance")
            for p, hits in resistance_hits.most_common(10)
            if p > current_price + tolerance
        ][:5]

        # Also add swing-based levels from step 4
        for sh in context.structure.swing_highs:
            if sh > current_price + tolerance:
                resistance_levels.append(Level(price=sh, strength=0.5, touches=1, label="swing_high"))
        for sl in context.structure.swing_lows:
            if sl < current_price - tolerance:
                support_levels.append(Level(price=sl, strength=0.5, touches=1, label="swing_low"))

        # Sort by strength
        support_levels.sort(key=lambda l: l.strength, reverse=True)
        resistance_levels.sort(key=lambda l: l.strength, reverse=True)

        sr = SRLevels(support=support_levels[:5], resistance=resistance_levels[:5])
        return context.update(sr_levels=sr)
