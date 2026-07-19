"""Step 6: Liquidity Detection — equal highs/lows, stop clusters, liquidity pool mapping.

Real trading logic:
- Equal highs/lows detection (buy-side / sell-side liquidity pools)
- Swing-point-based stop cluster identification
- Volume profile liquidity zones (high-volume nodes act as magnets)
- Liquidity sweep detection (price takes out a level then reverses)
- Deduplication with ATR-adaptive tolerance
"""

from __future__ import annotations

from alphastack.strategy.context import AlphaStackContext, LiquidityPool
from alphastack.strategy.steps.base import AlphaStackStep
from alphastack.strategy.config import strategy_params


def _find_equal_levels(
    prices: list[float],
    tolerance: float,
    min_equal: int = 2,
    side: str = "above",
) -> list[LiquidityPool]:
    """Find equal highs or lows — price levels tested multiple times.

    Equal highs (buy-side liquidity): stops rest above these levels.
    Equal lows (sell-side liquidity): stops rest below these levels.

    When price sweeps these levels, it's likely hunting stops.
    """
    if len(prices) < min_equal:
        return []

    pools: list[LiquidityPool] = []
    used: set[int] = set()

    for i in range(len(prices)):
        if i in used:
            continue

        cluster = [i]
        for j in range(i + 1, len(prices)):
            if j in used:
                continue
            if abs(prices[j] - prices[i]) < tolerance:
                cluster.append(j)

        if len(cluster) >= min_equal:
            avg_price = sum(prices[k] for k in cluster) / len(cluster)
            strength = min(len(cluster) / 5.0, 1.0)

            pools.append(LiquidityPool(
                price=round(avg_price, 6),
                side=side,
                strength=round(strength, 3),
                label=f"equal_{'highs' if side == 'above' else 'lows'}",
            ))
            used.update(cluster)

    return pools


def _find_stop_clusters(
    sr_support: list,
    sr_resistance: list,
    atr_tolerance: float,
) -> list[LiquidityPool]:
    """Identify stop-loss clusters from S/R levels.

    Stops typically cluster just beyond S/R levels:
    - Below support → sell-side liquidity (buy stops below)
    - Above resistance → buy-side liquidity (sell stops above)
    """
    pools: list[LiquidityPool] = []

    for level in sr_support:
        # Stops cluster just below support
        pools.append(LiquidityPool(
            price=level.price - atr_tolerance,
            side="below",
            strength=level.strength * 0.7,
            label="stop_cluster_support",
        ))

    for level in sr_resistance:
        # Stops cluster just above resistance
        pools.append(LiquidityPool(
            price=level.price + atr_tolerance,
            side="above",
            strength=level.strength * 0.7,
            label="stop_cluster_resistance",
        ))

    return pools


def _find_volume_liquidity(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    volumes: list[float],
    n_zones: int = 5,
    zone_pct: float = 0.01,
) -> list[LiquidityPool]:
    """Find high-volume zones that act as liquidity magnets.

    High-volume price areas often serve as support/resistance
    because institutional orders were placed there.
    """
    if not volumes or len(volumes) < 10:
        return []

    price_min = min(lows[-100:]) if len(lows) >= 100 else min(lows)
    price_max = max(highs[-100:]) if len(highs) >= 100 else max(highs)
    price_range = price_max - price_min
    if price_range <= 0:
        return []

    # Create price bins
    n_bins = min(50, len(closes) // 2)
    if n_bins < 5:
        return []

    bin_size = price_range / n_bins
    bin_volumes = [0.0] * n_bins

    for close, vol in zip(closes, volumes):
        bin_idx = int((close - price_min) / bin_size)
        bin_idx = max(0, min(bin_idx, n_bins - 1))
        bin_volumes[bin_idx] += vol

    # Find top volume zones
    total_vol = sum(bin_volumes)
    if total_vol == 0:
        return []

    pools: list[LiquidityPool] = []
    sorted_bins = sorted(enumerate(bin_volumes), key=lambda x: x[1], reverse=True)

    for bin_idx, vol in sorted_bins[:n_zones]:
        zone_price = price_min + (bin_idx + 0.5) * bin_size
        vol_pct = vol / total_vol
        strength = min(vol_pct * 10, 1.0)  # Scale: 10% of volume = strength 1.0

        pools.append(LiquidityPool(
            price=round(zone_price, 6),
            side="above" if zone_price > closes[-1] else "below",
            strength=round(strength, 3),
            label="volume_node",
        ))

    return pools


def _detect_liquidity_sweeps(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    lookback: int = 20,
) -> list[dict]:
    """Detect recent liquidity sweeps — price takes out a level then reverses.

    A sweep of highs: price exceeds a recent swing high but closes below it.
    A sweep of lows: price drops below a recent swing low but closes above it.

    These are high-probability reversal signals in SMC trading.
    """
    if len(closes) < lookback + 2:
        return []

    sweeps = []
    recent_highs = highs[-lookback:]
    recent_lows = lows[-lookback:]

    # Swing high = highest high in lookback (excluding last bar)
    swing_high = max(recent_highs[:-1])
    swing_low = min(recent_lows[:-1])

    # Sweep of highs (bearish signal — expect downward move)
    if highs[-1] > swing_high and closes[-1] < swing_high:
        sweeps.append({
            "type": "sweep_highs",
            "level": swing_high,
            "expected_direction": "short",
            "strength": 0.7,
        })

    # Sweep of lows (bullish signal — expect upward move)
    if lows[-1] < swing_low and closes[-1] > swing_low:
        sweeps.append({
            "type": "sweep_lows",
            "level": swing_low,
            "expected_direction": "long",
            "strength": 0.7,
        })

    return sweeps


def _deduplicate_pools(pools: list[LiquidityPool], tolerance: float) -> list[LiquidityPool]:
    """Remove duplicate pools within tolerance, keeping the strongest."""
    if not pools:
        return pools

    pools.sort(key=lambda p: p.strength, reverse=True)
    kept: list[LiquidityPool] = []

    for pool in pools:
        if not any(abs(pool.price - k.price) < tolerance for k in kept):
            kept.append(pool)

    return kept


class LiquidityDetection(AlphaStackStep):
    step_number = 6
    step_name = "liquidity_detection"

    async def execute(self, context: AlphaStackContext) -> AlphaStackContext:
        md = context.market_data

        highs: list[float] = md.get("highs", [])
        lows: list[float] = md.get("lows", [])
        closes: list[float] = md.get("closes", [])
        volumes: list[float] = md.get("volumes", [])
        pip_size: float = md.get("pip_size", 0.0001)
        atr_pips: float = md.get("atr_pips", 50.0)

        # Tolerance for "equal" levels — ATR-adaptive
        zone_tolerance_atr = strategy_params.get("sr.zone_tolerance_atr", 0.2)
        tolerance = atr_pips * pip_size * zone_tolerance_atr

        # Minimum bars for a level to qualify
        min_equal = strategy_params.get("liquidity.min_equal_touches", 2)

        pools: list[LiquidityPool] = []

        # --- 1. Equal highs (buy-side liquidity above) ---
        pools.extend(_find_equal_levels(highs, tolerance, min_equal, side="above"))

        # --- 2. Equal lows (sell-side liquidity below) ---
        pools.extend(_find_equal_levels(lows, tolerance, min_equal, side="below"))

        # --- 3. Stop clusters from S/R levels ---
        pools.extend(_find_stop_clusters(
            context.sr_levels.support,
            context.sr_levels.resistance,
            tolerance,
        ))

        # --- 4. Volume-based liquidity zones ---
        pools.extend(_find_volume_liquidity(highs, lows, closes, volumes))

        # --- 5. Liquidity sweep detection ---
        sweeps = _detect_liquidity_sweeps(highs, lows, closes)
        for sweep in sweeps:
            pools.append(LiquidityPool(
                price=sweep["level"],
                side="above" if sweep["type"] == "sweep_highs" else "below",
                strength=sweep["strength"],
                label=sweep["type"],
            ))

        # --- Deduplicate ---
        pools = _deduplicate_pools(pools, tolerance)

        # Store sweep info in market_data for downstream
        md = dict(context.market_data)
        md["liquidity_sweeps"] = sweeps
        md["liquidity_pool_count"] = len(pools)

        return context.update(liquidity_pools=pools, market_data=md)
