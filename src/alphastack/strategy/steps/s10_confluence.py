"""Step 10: Confluence Engine — true multi-factor consensus with independent
direction signals from each component.

Real trading logic:
- Each component independently votes LONG, SHORT, or NEUTRAL
- Weighted majority voting determines final direction
- Component agreement metric (how many factors agree)
- Regime-adaptive weight allocation
- Minimum consensus threshold (require N agreeing components)
- Confidence-adjusted confluence score (alignment × certainty)
"""

from __future__ import annotations

from alphastack.strategy.context import (
    AlphaStackContext,
    ConfluenceResult,
    Direction,
)
from alphastack.strategy.steps.base import AlphaStackStep
from alphastack.strategy.config import strategy_params

# Default weights — overridden by config at runtime
_DEFAULT_WEIGHTS: dict[str, float] = {
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


def _vote_from_bias(bias_value: str) -> Direction:
    """Derive a direction vote from a bias string."""
    if bias_value == "bullish":
        return Direction.LONG
    if bias_value == "bearish":
        return Direction.SHORT
    return Direction.NONE


def _vote_from_signal(signal: str) -> Direction:
    """Derive a direction vote from RSI signal."""
    if signal == "oversold":
        return Direction.LONG
    if signal == "overbought":
        return Direction.SHORT
    return Direction.NONE


def _vote_from_divergence(div: str) -> Direction:
    """Derive a direction vote from RSI divergence."""
    if div == "bullish":
        return Direction.LONG
    if div == "bearish":
        return Direction.SHORT
    return Direction.NONE


def _vote_from_candle_patterns(context: AlphaStackContext) -> Direction:
    """Derive direction from candlestick pattern consensus."""
    long_count = sum(1 for p in context.candlestick.patterns if p.direction == Direction.LONG)
    short_count = sum(1 for p in context.candlestick.patterns if p.direction == Direction.SHORT)
    if long_count > short_count:
        return Direction.LONG
    if short_count > long_count:
        return Direction.SHORT
    return Direction.NONE


def _vote_from_smc(context: AlphaStackContext, price: float) -> Direction:
    """Derive direction from SMC (order blocks + FVGs) near current price."""
    long_score = 0.0
    short_score = 0.0

    for ob in context.smc.order_blocks:
        if ob.mitigated:
            continue
        # Bullish OB: price is in the OB zone → long signal
        if ob.direction == Direction.LONG and ob.low <= price <= ob.high:
            long_score = max(long_score, 0.7)
        # Bearish OB: price is in the OB zone → short signal
        elif ob.direction == Direction.SHORT and ob.low <= price <= ob.high:
            short_score = max(short_score, 0.7)

    for fvg in context.smc.fvgs:
        if fvg.filled:
            continue
        if fvg.direction == Direction.LONG and fvg.low <= price <= fvg.high:
            long_score = max(long_score, 0.5)
        elif fvg.direction == Direction.SHORT and fvg.low <= price <= fvg.high:
            short_score = max(short_score, 0.5)

    # Order flow bias from extended SMC data
    order_flow = context.market_data.get("smc_order_flow_bias", "none")
    flow_confidence = context.market_data.get("smc_order_flow_confidence", 0.0)
    if order_flow == "long":
        long_score += flow_confidence * 0.3
    elif order_flow == "short":
        short_score += flow_confidence * 0.3

    if long_score > short_score * 1.2:
        return Direction.LONG
    if short_score > long_score * 1.2:
        return Direction.SHORT
    return Direction.NONE


def _vote_from_sr(context: AlphaStackContext, price: float) -> Direction:
    """Derive direction from S/R proximity — near support = long, near resistance = short."""
    if context.sr_levels.support:
        nearest_sup = min(context.sr_levels.support, key=lambda l: abs(l.price - price))
        dist_pct = abs(nearest_sup.price - price) / max(price, 1e-9)
        if dist_pct < 0.005:  # within 0.5%
            return Direction.LONG
    if context.sr_levels.resistance:
        nearest_res = min(context.sr_levels.resistance, key=lambda l: abs(l.price - price))
        dist_pct = abs(nearest_res.price - price) / max(price, 1e-9)
        if dist_pct < 0.005:
            return Direction.SHORT
    return Direction.NONE


def _vote_from_structure_bos(context: AlphaStackContext) -> Direction:
    """Derive direction from BOS/CHoCH signals (extended data from step 4)."""
    bos_direction = context.market_data.get("bos_direction")
    choch_detected = context.market_data.get("choch_detected", False)

    if choch_detected:
        # CHoCH is a reversal signal — use structure direction
        return context.structure.direction

    if bos_direction == "long":
        return Direction.LONG
    elif bos_direction == "short":
        return Direction.SHORT

    return context.structure.direction


def _vote_from_session_quality(context: AlphaStackContext) -> Direction:
    """Session quality doesn't suggest direction, but amplifies other signals.

    Returns NONE (neutral direction) but the quality score is used for weighting.
    """
    return Direction.NONE


class ConfluenceEngine(AlphaStackStep):
    step_number = 10
    step_name = "confluence_engine"

    async def execute(self, context: AlphaStackContext) -> AlphaStackContext:
        price = context.market_data.get("close", 0.0)

        # Load weights from config (regime-adaptive)
        regime = context.market_data.get("regime", None)
        weights = strategy_params.weights_for_regime(regime) if regime else strategy_params.get("confluence.weights", _DEFAULT_WEIGHTS)
        if not weights:
            weights = _DEFAULT_WEIGHTS

        # --- Phase 1: Each component casts an independent direction vote ---
        votes: dict[str, Direction] = {}
        votes["fundamental"] = _vote_from_bias(context.fundamental.bias.value)
        votes["market_bias"] = _vote_from_bias(context.bias.bias.value)
        votes["session"] = _vote_from_session_quality(context)
        votes["structure"] = _vote_from_structure_bos(context)
        votes["sr_levels"] = _vote_from_sr(context, price)
        votes["liquidity"] = Direction.NONE  # liquidity targets don't imply direction
        votes["smc"] = _vote_from_smc(context, price)
        votes["rsi"] = _vote_from_signal(context.rsi.signal)
        # Also factor in divergence as a separate signal
        rsi_div_vote = _vote_from_divergence(context.rsi.divergence)
        votes["candlestick"] = _vote_from_candle_patterns(context)

        # --- Phase 2: Weighted vote counting ---
        long_weight = 0.0
        short_weight = 0.0
        for component, vote in votes.items():
            w = weights.get(component, 0.0)
            if vote == Direction.LONG:
                long_weight += w
            elif vote == Direction.SHORT:
                short_weight += w
        # Add RSI divergence as a bonus (half-weight)
        if rsi_div_vote == Direction.LONG:
            long_weight += weights["rsi"] * 0.5
        elif rsi_div_vote == Direction.SHORT:
            short_weight += weights["rsi"] * 0.5

        # Consensus direction: whichever side has more weighted support
        if long_weight > short_weight:
            final_direction = Direction.LONG
        elif short_weight > long_weight:
            final_direction = Direction.SHORT
        else:
            final_direction = Direction.NONE

        # --- Phase 3: Score alignment strength ---
        component_scores: dict[str, float] = {}

        # Fundamental
        if votes["fundamental"] == final_direction:
            component_scores["fundamental"] = 1.0
        elif votes["fundamental"] == Direction.NONE:
            component_scores["fundamental"] = 0.0
        else:
            component_scores["fundamental"] = -0.5

        # Market bias
        if votes["market_bias"] == final_direction:
            component_scores["market_bias"] = 1.0
        elif votes["market_bias"] == Direction.NONE:
            component_scores["market_bias"] = 0.0
        else:
            component_scores["market_bias"] = -0.5

        # Session (volatility contributes regardless of direction)
        session_quality = context.market_data.get("session_quality", context.session.volatility)
        component_scores["session"] = session_quality

        # Structure (with trend strength weighting)
        if votes["structure"] == final_direction:
            trend_strength = context.market_data.get("trend_strength", 0.5)
            component_scores["structure"] = 0.5 + trend_strength * 0.5
        elif votes["structure"] == Direction.NONE:
            component_scores["structure"] = 0.0
        else:
            component_scores["structure"] = -0.5

        # S/R levels (strength-weighted)
        if votes["sr_levels"] == final_direction:
            sr_list = context.sr_levels.support if final_direction == Direction.LONG else context.sr_levels.resistance
            if sr_list:
                nearest = min(sr_list, key=lambda l: abs(l.price - price))
                component_scores["sr_levels"] = nearest.strength
            else:
                component_scores["sr_levels"] = 0.5
        elif votes["sr_levels"] == Direction.NONE:
            component_scores["sr_levels"] = 0.0
        else:
            component_scores["sr_levels"] = -0.3

        # Liquidity (pool strength)
        liq_score = max((p.strength for p in context.liquidity_pools), default=0.0)
        component_scores["liquidity"] = liq_score

        # SMC (OB + FVG alignment)
        smc_score = 0.0
        for ob in context.smc.order_blocks:
            if ob.direction == final_direction and not ob.mitigated:
                smc_score = max(smc_score, 0.7)
        for fvg in context.smc.fvgs:
            if fvg.direction == final_direction and not fvg.filled:
                smc_score = max(smc_score, 0.5)
        for bb in context.smc.breaker_blocks:
            if bb.direction == final_direction:
                smc_score = max(smc_score, 0.6)
        # Bonus from premium/discount zone
        zone = context.market_data.get("smc_zone", "neutral")
        if final_direction == Direction.LONG and zone == "discount":
            smc_score = min(smc_score + 0.2, 1.0)
        elif final_direction == Direction.SHORT and zone == "premium":
            smc_score = min(smc_score + 0.2, 1.0)
        component_scores["smc"] = smc_score

        # RSI (signal + divergence + momentum)
        rsi_score = 0.0
        if votes["rsi"] == final_direction:
            rsi_score = 0.8
        elif rsi_div_vote == final_direction:
            rsi_score = 0.6
        # RSI trendline break bonus
        rsi_tl_break = context.market_data.get("rsi_trendline_break", "none")
        if (final_direction == Direction.LONG and rsi_tl_break == "bullish_break"):
            rsi_score = min(rsi_score + 0.2, 1.0)
        elif (final_direction == Direction.SHORT and rsi_tl_break == "bearish_break"):
            rsi_score = min(rsi_score + 0.2, 1.0)
        component_scores["rsi"] = rsi_score

        # Candlestick (pattern strength)
        candle_score = 0.0
        for p in context.candlestick.patterns:
            if p.direction == final_direction:
                candle_score = max(candle_score, p.strength)
        # Bonus for multiple agreeing patterns
        agreeing_patterns = sum(
            1 for p in context.candlestick.patterns if p.direction == final_direction
        )
        if agreeing_patterns >= 2:
            candle_score = min(candle_score + 0.15, 1.0)
        component_scores["candlestick"] = candle_score

        # --- Phase 4: Weighted confluence score ---
        raw_score = sum(
            component_scores[k] * weights.get(k, 0.0) for k in component_scores
        )
        # Map to 0-100
        confluence_score = max(0.0, min(raw_score * 100, 100.0))

        # --- Phase 5: Component agreement check ---
        min_agreeing = strategy_params.get("confluence.min_agreeing_components", 3)
        agreeing = sum(1 for v in votes.values() if v == final_direction)

        # Direction decision: require minimum consensus
        if agreeing < min_agreeing:
            final_direction = Direction.NONE

        # Also require score above threshold
        threshold = strategy_params.get("confluence.threshold", 40)
        if confluence_score < threshold:
            final_direction = Direction.NONE

        # --- Compute agreement ratio for confidence ---
        total_votes = len(votes)
        agreement_ratio = agreeing / total_votes if total_votes > 0 else 0.0

        confluence = ConfluenceResult(
            score=round(confluence_score, 2),
            direction=final_direction,
            component_scores=component_scores,
        )

        # Store agreement metrics in market_data for journal
        md = dict(context.market_data)
        md["confluence_agreement_ratio"] = round(agreement_ratio, 3)
        md["confluence_agreeing_count"] = agreeing
        md["confluence_long_weight"] = round(long_weight, 3)
        md["confluence_short_weight"] = round(short_weight, 3)

        return context.update(confluence=confluence, market_data=md)
