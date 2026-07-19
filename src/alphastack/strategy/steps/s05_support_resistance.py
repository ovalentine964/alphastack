"""Step 5: Support & Resistance — key level identification with multi-touch validation.

Real trading logic:
- Pivot-based S/R detection with configurable lookback
- ATR-adaptive bucket sizing for level clustering
- Multi-touch validation with exponential recency decay
- Volume-weighted strength scoring (when volume data available)
- Confluence with swing points from Step 4
- Psychological round-number level detection
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

from alphastack.strategy.context import AlphaStackContext, Level, SRLevels
from alphastack.strategy.steps.base import AlphaStackStep
from alphastack.strategy.config import strategy_params


def _round_to_nearest(price: float, step: float) -> float:
    """Round price to the nearest step."""
    return round(round(price / step) * step, 10)


def _find_pivot_highs(highs: list[float], lookback: int) -> list[tuple[float, int]]:
    """Find swing highs (local maxima) using a simple fractal method."""
    pivots = []
    for i in range(lookback, len(highs) - lookback):
        window = highs[i - lookback : i + lookback + 1]
        if highs[i] == max(window):
            # Only count if it's strictly the highest (handles ties)
            if window.count(highs[i]) == 1:
                pivots.append((highs[i], i))
    return pivots


def _find_pivot_lows(lows: list[float], lookback: int) -> list[tuple[float, int]]:
    """Find swing lows (local minima) using a simple fractal method."""
    pivots = []
    for i in range(lookback, len(lows) - lookback):
        window = lows[i - lookback : i + lookback + 1]
        if lows[i] == min(window):
            if window.count(lows[i]) == 1:
                pivots.append((lows[i], i))
    return pivots


def _cluster_levels(
    pivots: list[tuple[float, int]],
    cluster_tolerance: float,
    n_bars: int,
    decay: float = 0.95,
) -> list[dict]:
    """Cluster nearby pivot prices into single S/R levels.

    Each level gets:
    - price: average of clustered pivots
    - touches: number of pivots in the cluster
    - strength: decay-weighted score (recent touches count more)
    - last_test_index: index of most recent test
    """
    if not pivots:
        return []

    # Sort by price
    pivots = sorted(pivots, key=lambda x: x[0])
    clusters: list[list[tuple[float, int]]] = [[pivots[0]]]

    for price, idx in pivots[1:]:
        last_cluster = clusters[-1]
        cluster_avg = np_mean([p for p, _ in last_cluster])
        if abs(price - cluster_avg) < cluster_tolerance:
            last_cluster.append((price, idx))
        else:
            clusters.append([(price, idx)])

    levels = []
    for cluster in clusters:
        avg_price = np_mean([p for p, _ in cluster])
        touches = len(cluster)
        last_idx = max(idx for _, idx in cluster)

        # Decay-weighted strength: recent touches matter more
        weight_sum = 0.0
        for _, idx in cluster:
            age_bars = n_bars - idx
            weight_sum += decay ** age_bars

        # Normalize: more touches + more recent = stronger
        max_possible = touches  # if all at bar 0
        strength = min(weight_sum / max(max_possible, 1), 1.0)

        levels.append({
            "price": round(avg_price, 6),
            "touches": touches,
            "strength": round(strength, 3),
            "last_test_index": last_idx,
        })

    return levels


def _detect_psychological_levels(
    current_price: float,
    pip_size: float,
    n_levels: int = 5,
) -> list[float]:
    """Detect nearby psychological round-number levels.

    In FX, levels like 1.1000, 1.1050, 1.1100 are significant.
    In crypto, levels like 30000, 35000, 40000 matter.
    """
    if current_price <= 0:
        return []

    # Determine the step size based on price magnitude
    magnitude = 10 ** math.floor(math.log10(current_price))
    step = magnitude * 0.005  # 0.5% of magnitude

    # For very small prices (crypto), use 1% steps
    if current_price < 1:
        step = magnitude * 0.01

    # Find the nearest round number
    base = round(current_price / step) * step

    levels = []
    for i in range(-n_levels, n_levels + 1):
        level = base + i * step
        if level > 0 and level != current_price:
            levels.append(round(level, 6))

    return levels


def np_mean(values: list[float]) -> float:
    """Simple mean (avoid numpy import for small lists)."""
    if not values:
        return 0.0
    return sum(values) / len(values)


def _volume_weighted_strength(
    price: float,
    volumes: list[float],
    closes: list[float],
    tolerance: float,
) -> float:
    """Boost S/R strength if high volume occurred near the level.

    Volume confirmation adds conviction to S/R levels.
    """
    if not volumes or not closes:
        return 0.0

    vol_sum = 0.0
    total_vol = sum(volumes)
    if total_vol == 0:
        return 0.0

    for i, (close, vol) in enumerate(zip(closes, volumes)):
        if abs(close - price) < tolerance:
            vol_sum += vol

    # Ratio of volume near level vs total volume
    vol_ratio = vol_sum / total_vol
    # Map to 0–0.3 boost (don't let volume alone make a level strong)
    return min(vol_ratio * 3.0, 0.3)


class SupportResistance(AlphaStackStep):
    step_number = 5
    step_name = "support_resistance"

    async def execute(self, context: AlphaStackContext) -> AlphaStackContext:
        md = context.market_data

        highs: list[float] = md.get("highs", [])
        lows: list[float] = md.get("lows", [])
        closes: list[float] = md.get("closes", [])
        volumes: list[float] = md.get("volumes", [])
        pip_size: float = md.get("pip_size", 0.0001)
        atr_pips: float = md.get("atr_pips", 50.0)
        current_price: float = closes[-1] if closes else md.get("close", 0.0)

        # Configuration
        bucket_method = strategy_params.get("sr.bucket_method", "atr_relative")
        min_touches = strategy_params.get("sr.min_touches", 2)
        recency_decay = strategy_params.get("sr.recency_decay", 0.95)
        zone_tolerance_atr = strategy_params.get("sr.zone_tolerance_atr", 0.2)
        max_levels = strategy_params.get("sr.max_levels", 10)
        pivot_lookback = strategy_params.get("structure.swing_lookback", 5)

        # Compute bucket/cluster size
        if bucket_method == "atr_relative":
            atr_bucket_mult = strategy_params.get("sr.atr_bucket_multiplier", 0.5)
            bucket_step = atr_pips * pip_size * atr_bucket_mult
        else:
            fixed_bucket = strategy_params.get("sr.fixed_bucket_pips", 50.0)
            bucket_step = fixed_bucket * pip_size

        zone_tolerance = atr_pips * pip_size * zone_tolerance_atr
        n_bars = len(closes)

        # --- Method 1: Pivot-based S/R (fractal detection) ---
        pivot_highs = _find_pivot_highs(highs, pivot_lookback)
        pivot_lows = _find_pivot_lows(lows, pivot_lookback)

        pivot_resistance = _cluster_levels(pivot_highs, bucket_step, n_bars, recency_decay)
        pivot_support = _cluster_levels(pivot_lows, bucket_step, n_bars, recency_decay)

        # --- Method 2: Price bucketing (high/low clustering) ---
        support_hits: Counter[float] = Counter()
        resistance_hits: Counter[float] = Counter()

        for low in lows:
            bucket = _round_to_nearest(low, bucket_step)
            support_hits[bucket] += 1

        for high in highs:
            bucket = _round_to_nearest(high, bucket_step)
            resistance_hits[bucket] += 1

        # --- Merge methods: combine pivot + bucketing ---
        support_levels: list[Level] = []
        resistance_levels: list[Level] = []

        # Add pivot-based levels
        for lvl in pivot_resistance:
            if lvl["price"] > current_price + zone_tolerance and lvl["touches"] >= min_touches:
                vol_boost = _volume_weighted_strength(
                    lvl["price"], volumes, closes, zone_tolerance,
                )
                support_levels.append(Level(
                    price=lvl["price"],
                    strength=min(lvl["strength"] + vol_boost, 1.0),
                    touches=lvl["touches"],
                    label="pivot_resistance",
                ))

        for lvl in pivot_support:
            if lvl["price"] < current_price - zone_tolerance and lvl["touches"] >= min_touches:
                vol_boost = _volume_weighted_strength(
                    lvl["price"], volumes, closes, zone_tolerance,
                )
                support_levels.append(Level(
                    price=lvl["price"],
                    strength=min(lvl["strength"] + vol_boost, 1.0),
                    touches=lvl["touches"],
                    label="pivot_support",
                ))

        # Add bucket-based levels (if not already covered)
        for p, hits in support_hits.most_common(max_levels):
            if p < current_price - zone_tolerance and hits >= min_touches:
                # Check if a pivot level already covers this price
                if not any(abs(l.price - p) < zone_tolerance for l in support_levels):
                    strength = min(hits / max(len(lows), 1), 1.0)
                    vol_boost = _volume_weighted_strength(p, volumes, closes, zone_tolerance)
                    support_levels.append(Level(
                        price=p,
                        strength=min(strength + vol_boost, 1.0),
                        touches=hits,
                        label="cluster_support",
                    ))

        for p, hits in resistance_hits.most_common(max_levels):
            if p > current_price + zone_tolerance and hits >= min_touches:
                if not any(abs(l.price - p) < zone_tolerance for l in resistance_levels):
                    strength = min(hits / max(len(highs), 1), 1.0)
                    vol_boost = _volume_weighted_strength(p, volumes, closes, zone_tolerance)
                    resistance_levels.append(Level(
                        price=p,
                        strength=min(strength + vol_boost, 1.0),
                        touches=hits,
                        label="cluster_resistance",
                    ))

        # --- Add swing-based levels from Step 4 ---
        for sh in context.structure.swing_highs:
            if sh > current_price + zone_tolerance:
                if not any(abs(l.price - sh) < zone_tolerance for l in resistance_levels):
                    resistance_levels.append(Level(
                        price=sh, strength=0.5, touches=1, label="swing_high",
                    ))
        for sl in context.structure.swing_lows:
            if sl < current_price - zone_tolerance:
                if not any(abs(l.price - sl) < zone_tolerance for l in support_levels):
                    support_levels.append(Level(
                        price=sl, strength=0.5, touches=1, label="swing_low",
                    ))

        # --- Psychological round-number levels ---
        psych_levels = _detect_psychological_levels(current_price, pip_size)
        for pl in psych_levels:
            if pl > current_price and not any(abs(l.price - pl) < zone_tolerance for l in resistance_levels):
                resistance_levels.append(Level(
                    price=pl, strength=0.3, touches=0, label="psychological",
                ))
            elif pl < current_price and not any(abs(l.price - pl) < zone_tolerance for l in support_levels):
                support_levels.append(Level(
                    price=pl, strength=0.3, touches=0, label="psychological",
                ))

        # Sort: strongest first
        support_levels.sort(key=lambda l: l.strength, reverse=True)
        resistance_levels.sort(key=lambda l: l.strength, reverse=True)

        # Trim to max
        support_levels = support_levels[:max_levels]
        resistance_levels = resistance_levels[:max_levels]

        sr = SRLevels(support=support_levels, resistance=resistance_levels)
        return context.update(sr_levels=sr)
