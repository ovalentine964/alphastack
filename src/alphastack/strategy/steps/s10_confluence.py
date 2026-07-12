"""Step 10: Confluence Engine — weighted scoring of all signals (steps 1-9)."""

from __future__ import annotations

from alphastack.strategy.context import (
    AlphaStackContext,
    ConfluenceResult,
    Direction,
)
from alphastack.strategy.steps.base import AlphaStackStep

# Weights for each signal source (must sum to 1.0)
_WEIGHTS: dict[str, float] = {
    "fundamental": 0.05,
    "market_bias": 0.15,
    "session": 0.05,
    "structure": 0.20,
    "sr_levels": 0.10,
    "liquidity": 0.10,
    "smc": 0.15,
    "rsi": 0.10,
    "candlestick": 0.10,
}


def _score_bias(bias_value: str, direction: Direction) -> float:
    """Score how well a bias aligns with the target direction."""
    if direction == Direction.NONE:
        return 0.0
    aligned = (direction == Direction.LONG and bias_value == "bullish") or (
        direction == Direction.SHORT and bias_value == "bearish"
    )
    return 1.0 if aligned else -0.5


class ConfluenceEngine(AlphaStackStep):
    step_number = 10
    step_name = "confluence_engine"

    async def execute(self, context: AlphaStackContext) -> AlphaStackContext:
        # Determine preliminary direction from structure
        direction = context.structure.direction

        component_scores: dict[str, float] = {}

        # 1. Fundamental
        component_scores["fundamental"] = _score_bias(context.fundamental.bias.value, direction)

        # 2. Market bias
        component_scores["market_bias"] = _score_bias(context.bias.bias.value, direction)

        # 3. Session (volatility bonus if aligned)
        vol = context.session.volatility
        component_scores["session"] = vol if direction != Direction.NONE else 0.0

        # 4. Structure
        struct_score = 1.0 if context.structure.direction != Direction.NONE else 0.0
        component_scores["structure"] = struct_score

        # 5. S/R levels — proximity to key level
        sr_score = 0.0
        price = context.market_data.get("close", 0.0)
        if direction == Direction.LONG and context.sr_levels.support:
            nearest = min(context.sr_levels.support, key=lambda l: abs(l.price - price))
            sr_score = nearest.strength
        elif direction == Direction.SHORT and context.sr_levels.resistance:
            nearest = min(context.sr_levels.resistance, key=lambda l: abs(l.price - price))
            sr_score = nearest.strength
        component_scores["sr_levels"] = sr_score

        # 6. Liquidity — nearby pool strength
        liq_score = max((p.strength for p in context.liquidity_pools), default=0.0)
        component_scores["liquidity"] = liq_score

        # 7. SMC — order block / FVG alignment
        smc_score = 0.0
        for ob in context.smc.order_blocks:
            if (ob.direction == Direction.LONG and direction == Direction.LONG) or (
                ob.direction == Direction.SHORT and direction == Direction.SHORT
            ):
                smc_score = max(smc_score, 0.7)
        for fvg in context.smc.fvgs:
            if (fvg.direction == Direction.LONG and direction == Direction.LONG) or (
                fvg.direction == Direction.SHORT and direction == Direction.SHORT
            ):
                smc_score = max(smc_score, 0.5)
        component_scores["smc"] = smc_score

        # 8. RSI
        rsi_score = 0.0
        if direction == Direction.LONG and context.rsi.signal == "oversold":
            rsi_score = 0.8
        elif direction == Direction.SHORT and context.rsi.signal == "overbought":
            rsi_score = 0.8
        elif context.rsi.divergence != "none":
            rsi_score = 0.6
        component_scores["rsi"] = rsi_score

        # 9. Candlestick
        component_scores["candlestick"] = context.candlestick.pattern_score

        # --- Weighted confluence ---
        raw_score = sum(
            component_scores[k] * _WEIGHTS.get(k, 0.0) for k in component_scores
        )
        # Map to 0-100
        confluence_score = max(0.0, min(raw_score * 100, 100.0))

        # Direction decision
        if confluence_score < 40:
            final_direction = Direction.NONE
        else:
            final_direction = direction

        confluence = ConfluenceResult(
            score=round(confluence_score, 2),
            direction=final_direction,
            component_scores=component_scores,
        )

        return context.update(confluence=confluence)
