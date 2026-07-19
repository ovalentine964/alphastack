"""Step 7: Smart Money Concepts — order blocks, FVGs, breaker blocks, premium/discount.

Real trading logic:
- Order block detection with ATR-based impulsive move threshold
- Fair value gap (FVG) detection with fill tracking
- Breaker block identification (failed OBs that become S/R)
- Premium/Discount zone calculation (based on swing range)
- Order flow bias from OB/FVG confluence
- Mitigation tracking (when price returns to an OB/FVG zone)
"""

from __future__ import annotations

from alphastack.strategy.context import (
    AlphaStackContext,
    Direction,
    FairValueGap,
    OrderBlock,
    SMCData,
)
from alphastack.strategy.steps.base import AlphaStackStep


def _compute_body(o: float, c: float) -> float:
    return abs(c - o)


def _is_bullish_candle(o: float, c: float) -> bool:
    return c > o


def _is_bearish_candle(o: float, c: float) -> bool:
    return c < o


def _detect_order_blocks(
    opens: list[float],
    highs: list[float],
    lows: list[float],
    closes: list[float],
    atr_values: list[float] | None = None,
    lookback: int = 50,
    impulsive_threshold_atr: float = 1.0,
) -> list[OrderBlock]:
    """Detect order blocks — the last opposing candle before an impulsive move.

    A bullish OB:
      1. A bearish candle (close < open)
      2. Followed by a strong bullish move (candle body > threshold)
      3. The bullish candle closes above the bearish candle's high

    A bearish OB:
      1. A bullish candle (close > open)
      2. Followed by a strong bearish move
      3. The bearish candle closes below the bullish candle's low

    The OB zone is the body of the opposing candle (high to low).
    """
    n = min(len(opens), len(highs), len(lows), len(closes))
    if n < 3:
        return []

    obs: list[OrderBlock] = []
    start = max(2, n - lookback)

    for i in range(start, n):
        # ATR-based threshold for "impulsive" move
        if atr_values and i < len(atr_values) and atr_values[i] > 0:
            threshold = atr_values[i] * impulsive_threshold_atr
        else:
            # Fallback: 1.5× the average body of last 10 candles
            recent_bodies = [_compute_body(opens[j], closes[j]) for j in range(max(0, i - 10), i)]
            avg_body = sum(recent_bodies) / max(len(recent_bodies), 1)
            threshold = avg_body * 1.5 if avg_body > 0 else 0.0

        if threshold <= 0:
            continue

        prev_body = _compute_body(opens[i - 1], closes[i - 1])
        curr_body = _compute_body(opens[i], closes[i])

        # Bullish OB: bearish candle at i-1, then strong bullish candle at i
        if (_is_bearish_candle(opens[i - 1], closes[i - 1])
                and _is_bullish_candle(opens[i], closes[i])
                and curr_body > threshold
                and closes[i] > highs[i - 1]):
            obs.append(OrderBlock(
                high=highs[i - 1],
                low=lows[i - 1],
                direction=Direction.LONG,
            ))

        # Bearish OB: bullish candle at i-1, then strong bearish candle at i
        elif (_is_bullish_candle(opens[i - 1], closes[i - 1])
              and _is_bearish_candle(opens[i], closes[i])
              and curr_body > threshold
              and closes[i] < lows[i - 1]):
            obs.append(OrderBlock(
                high=highs[i - 1],
                low=lows[i - 1],
                direction=Direction.SHORT,
            ))

    # Check mitigation: price returned to OB zone → OB is "used up"
    current_price = closes[-1] if closes else 0.0
    for ob in obs:
        if ob.direction == Direction.LONG:
            # Bullish OB mitigated when price drops below OB low
            ob.mitigated = current_price <= ob.low
        else:
            # Bearish OB mitigated when price rises above OB high
            ob.mitigated = current_price >= ob.high

    # Keep last 5 unmitigated OBs
    return [ob for ob in obs if not ob.mitigated][-5:]


def _detect_fvgs(
    opens: list[float],
    highs: list[float],
    lows: list[float],
    closes: list[float],
    min_gap_pct: float = 0.001,
) -> list[FairValueGap]:
    """Detect Fair Value Gaps (FVGs) — 3-candle imbalance.

    Bullish FVG: candle 3's low > candle 1's high (gap up through candle 2).
    Bearish FVG: candle 1's low > candle 3's high (gap down through candle 2).

    FVGs represent areas where price moved too fast and may return to "fill".
    """
    n = min(len(opens), len(highs), len(lows), len(closes))
    if n < 3:
        return []

    fvgs: list[FairValueGap] = []

    # Compute minimum gap size relative to average range
    avg_range = sum(highs[i] - lows[i] for i in range(min(n, 20))) / min(n, 20)
    min_gap = avg_range * min_gap_pct * 100  # Scale factor

    for i in range(2, n):
        # Bullish FVG: gap between candle 1 high and candle 3 low
        gap_low = highs[i - 2]   # Top of candle 1
        gap_high = lows[i]       # Bottom of candle 3
        if gap_high > gap_low and (gap_high - gap_low) > min_gap:
            fvgs.append(FairValueGap(
                high=gap_high,
                low=gap_low,
                direction=Direction.LONG,
            ))

        # Bearish FVG: gap between candle 3 high and candle 1 low
        gap_low_b = lows[i - 2]   # Bottom of candle 1
        gap_high_b = highs[i]     # Top of candle 3
        if gap_low_b > gap_high_b and (gap_low_b - gap_high_b) > min_gap:
            fvgs.append(FairValueGap(
                high=gap_low_b,
                low=gap_high_b,
                direction=Direction.SHORT,
            ))

    # Check fill status
    current_price = closes[-1] if closes else 0.0
    for fvg in fvgs:
        if fvg.direction == Direction.LONG:
            # Bullish FVG filled when price drops below gap low
            fvg.filled = current_price <= fvg.low
        else:
            # Bearish FVG filled when price rises above gap high
            fvg.filled = current_price >= fvg.high

    # Keep last 5 unfilled FVGs
    return [fvg for fvg in fvgs if not fvg.filled][-5:]


def _detect_breaker_blocks(
    all_obs: list[OrderBlock],
    highs: list[float],
    lows: list[float],
    closes: list[float],
    current_price: float,
) -> list[OrderBlock]:
    """Detect breaker blocks — failed order blocks that become S/R.

    A breaker block forms when:
    1. An order block gets mitigated (price enters the zone)
    2. Price then reverses strongly away from the OB
    3. The failed OB becomes a new support/resistance level

    Bullish breaker: bearish OB that was mitigated, price then rallied
    Bearish breaker: bullish OB that was mitigated, price then dropped
    """
    if not all_obs or len(closes) < 3:
        return []

    breakers: list[OrderBlock] = []

    for ob in all_obs:
        if not ob.mitigated:
            continue

        # Check if price reversed after mitigation
        if ob.direction == Direction.LONG:
            # Bullish OB was mitigated (price dropped to OB zone)
            # If price is now above OB, it acted as support → bullish breaker
            if current_price > ob.high:
                breakers.append(OrderBlock(
                    high=ob.high,
                    low=ob.low,
                    direction=Direction.LONG,
                ))
        else:
            # Bearish OB was mitigated (price rose to OB zone)
            # If price is now below OB, it acted as resistance → bearish breaker
            if current_price < ob.low:
                breakers.append(OrderBlock(
                    high=ob.high,
                    low=ob.low,
                    direction=Direction.SHORT,
                ))

    return breakers[-3:]  # Keep last 3


def _detect_premium_discount(
    swing_highs: list[float],
    swing_lows: list[float],
    current_price: float,
) -> tuple[str, float]:
    """Determine if price is in a premium or discount zone.

    Premium zone: above the equilibrium (50%) of the range → sell zone
    Discount zone: below the equilibrium → buy zone
    Equilibrium: the 50% Fibonacci level of the swing range

    Returns (zone_label, position_in_range 0-1).
    """
    if not swing_highs or not swing_lows:
        return "neutral", 0.5

    range_high = max(swing_highs[-3:]) if len(swing_highs) >= 3 else max(swing_highs)
    range_low = min(swing_lows[-3:]) if len(swing_lows) >= 3 else min(swing_lows)

    swing_range = range_high - range_low
    if swing_range <= 0:
        return "neutral", 0.5

    position = (current_price - range_low) / swing_range

    if position > 0.6:
        return "premium", round(position, 3)
    elif position < 0.4:
        return "discount", round(position, 3)
    else:
        return "equilibrium", round(position, 3)


def _compute_order_flow_bias(
    obs: list[OrderBlock],
    fvgs: list[FairValueGap],
) -> tuple[Direction, float]:
    """Compute order flow bias from OB and FVG confluence.

    Bullish: more unmitigated bullish OBs + unfilled bullish FVGs
    Bearish: more unmitigated bearish OBs + unfilled bearish FVGs
    """
    long_score = 0.0
    short_score = 0.0

    for ob in obs:
        if not ob.mitigated:
            if ob.direction == Direction.LONG:
                long_score += 0.7
            else:
                short_score += 0.7

    for fvg in fvgs:
        if not fvg.filled:
            if fvg.direction == Direction.LONG:
                long_score += 0.5
            else:
                short_score += 0.5

    total = long_score + short_score
    if total == 0:
        return Direction.NONE, 0.0

    if long_score > short_score * 1.2:
        confidence = long_score / total
        return Direction.LONG, round(confidence, 3)
    elif short_score > long_score * 1.2:
        confidence = short_score / total
        return Direction.SHORT, round(confidence, 3)
    else:
        return Direction.NONE, round(abs(long_score - short_score) / total, 3)


class SmartMoneyConcepts(AlphaStackStep):
    step_number = 7
    step_name = "smart_money_concepts"

    async def execute(self, context: AlphaStackContext) -> AlphaStackContext:
        md = context.market_data

        opens: list[float] = md.get("opens", [])
        highs: list[float] = md.get("highs", [])
        lows: list[float] = md.get("lows", [])
        closes: list[float] = md.get("closes", [])
        atr_values: list[float] = md.get("atr_values", [])
        current_price: float = closes[-1] if closes else 0.0

        # --- Order Blocks ---
        order_blocks = _detect_order_blocks(
            opens, highs, lows, closes,
            atr_values if atr_values else None,
        )

        # --- Fair Value Gaps ---
        fvgs = _detect_fvgs(opens, highs, lows, closes)

        # --- Breaker Blocks (from ALL OBs, including mitigated) ---
        all_obs = _detect_order_blocks(
            opens, highs, lows, closes,
            atr_values if atr_values else None,
            lookback=100,  # Look further back for breakers
        )
        # Mark mitigation on ALL OBs for breaker detection
        for ob in all_obs:
            if ob.direction == Direction.LONG:
                ob.mitigated = current_price <= ob.low
            else:
                ob.mitigated = current_price >= ob.high

        breaker_blocks = _detect_breaker_blocks(
            all_obs, highs, lows, closes, current_price,
        )

        # --- Premium / Discount zone ---
        zone, zone_position = _detect_premium_discount(
            context.structure.swing_highs,
            context.structure.swing_lows,
            current_price,
        )

        # --- Order flow bias ---
        order_flow_bias, order_flow_confidence = _compute_order_flow_bias(order_blocks, fvgs)

        smc = SMCData(
            order_blocks=order_blocks,
            fvgs=fvgs,
            breaker_blocks=breaker_blocks,
        )

        # Store extended SMC data in market_data
        md = dict(context.market_data)
        md["smc_zone"] = zone
        md["smc_zone_position"] = zone_position
        md["smc_order_flow_bias"] = order_flow_bias.value
        md["smc_order_flow_confidence"] = order_flow_confidence
        md["smc_ob_count"] = len(order_blocks)
        md["smc_fvg_count"] = len(fvgs)
        md["smc_breaker_count"] = len(breaker_blocks)

        return context.update(smc=smc, market_data=md)
