"""Step 6: Liquidity Detection — equal highs/lows, stop clusters, liquidity pool mapping."""

from __future__ import annotations

from alphastack.strategy.context import AlphaStackContext, LiquidityPool
from alphastack.strategy.steps.base import AlphaStackStep


class LiquidityDetection(AlphaStackStep):
    step_number = 6
    step_name = "liquidity_detection"

    async def execute(self, context: AlphaStackContext) -> AlphaStackContext:
        md = context.market_data

        highs: list[float] = md.get("highs", [])
        lows: list[float] = md.get("lows", [])
        pip_size: float = md.get("pip_size", 0.0001)
        tolerance = pip_size * 10  # "equal" threshold

        pools: list[LiquidityPool] = []

        # --- Equal highs (buy-side liquidity above) ---
        for i in range(len(highs)):
            count = sum(1 for h in highs[i + 1 :] if abs(h - highs[i]) < tolerance)
            if count >= 2:
                pools.append(
                    LiquidityPool(
                        price=highs[i],
                        side="above",
                        strength=min((count + 1) / 5, 1.0),
                        label="equal_highs",
                    )
                )

        # --- Equal lows (sell-side liquidity below) ---
        for i in range(len(lows)):
            count = sum(1 for lo in lows[i + 1 :] if abs(lo - lows[i]) < tolerance)
            if count >= 2:
                pools.append(
                    LiquidityPool(
                        price=lows[i],
                        side="below",
                        strength=min((count + 1) / 5, 1.0),
                        label="equal_lows",
                    )
                )

        # --- Stop clusters from S/R levels ---
        for level in context.sr_levels.support:
            pools.append(
                LiquidityPool(
                    price=level.price,
                    side="below",
                    strength=level.strength * 0.7,
                    label="stop_cluster_support",
                )
            )
        for level in context.sr_levels.resistance:
            pools.append(
                LiquidityPool(
                    price=level.price,
                    side="above",
                    strength=level.strength * 0.7,
                    label="stop_cluster_resistance",
                )
            )

        # Deduplicate by price proximity, keep strongest
        pools = _deduplicate_pools(pools, tolerance)

        return context.update(liquidity_pools=pools)


def _deduplicate_pools(pools: list[LiquidityPool], tolerance: float) -> list[LiquidityPool]:
    """Remove duplicate pools within *tolerance*, keeping the strongest."""
    if not pools:
        return pools
    pools.sort(key=lambda p: p.strength, reverse=True)
    kept: list[LiquidityPool] = []
    for pool in pools:
        if not any(abs(pool.price - k.price) < tolerance for k in kept):
            kept.append(pool)
    return kept
