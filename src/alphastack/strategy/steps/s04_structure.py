"""Step 4: Market Structure — HH/HL/LH/LL detection, BOS and CHoCH identification.

Real trading logic:
- Fractal-based swing point detection (configurable lookback)
- Proper Break of Structure (BOS) detection with confirmation bars
- Change of Character (CHoCH) detection — structure direction flip
- Internal structure (minor swings within major swings)
- Trend strength scoring based on swing sequence quality
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from alphastack.strategy.context import (
    AlphaStackContext,
    Direction,
    StructureData,
    StructureType,
)
from alphastack.strategy.steps.base import AlphaStackStep
from alphastack.strategy.config import strategy_params


@dataclass
class SwingPoint:
    """A detected swing point with metadata."""
    price: float
    index: int
    swing_type: str  # "high" | "low"
    strength: int = 1  # Number of bars confirming the fractal


@dataclass
class StructureAnalysis:
    """Full structure analysis result."""
    swing_highs: list[SwingPoint] = field(default_factory=list)
    swing_lows: list[SwingPoint] = field(default_factory=list)
    structure_type: StructureType = StructureType.CONSOLIDATION
    direction: Direction = Direction.NONE
    bos_detected: bool = False
    bos_direction: Direction = Direction.NONE
    choch_detected: bool = False
    trend_strength: float = 0.0  # 0–1
    last_hh: float | None = None
    last_hl: float | None = None
    last_lh: float | None = None
    last_ll: float | None = None


def _detect_fractal_swings(
    highs: list[float],
    lows: list[float],
    lookback: int = 5,
) -> tuple[list[SwingPoint], list[SwingPoint]]:
    """Detect swing highs and lows using fractal logic.

    A swing high at index i requires:
      high[i] >= max(high[i-lookback : i]) AND high[i] >= max(high[i+1 : i+lookback+1])
    A swing low at index i requires:
      low[i] <= min(low[i-lookback : i]) AND low[i] <= min(low[i+1 : i+lookback+1])

    Uses strict inequality for ties (the highest bar wins).
    """
    n = min(len(highs), len(lows))
    if n < lookback * 2 + 1:
        return [], []

    swing_highs: list[SwingPoint] = []
    swing_lows: list[SwingPoint] = []

    for i in range(lookback, n - lookback):
        # Swing high: bar i is the highest in its neighborhood
        left_highs = highs[i - lookback : i]
        right_highs = highs[i + 1 : i + lookback + 1]
        if highs[i] >= max(left_highs) and highs[i] >= max(right_highs):
            # Count how many bars confirm (were lower)
            strength = sum(1 for h in left_highs + right_highs if h < highs[i])
            swing_highs.append(SwingPoint(
                price=highs[i],
                index=i,
                swing_type="high",
                strength=max(strength, 1),
            ))

        # Swing low: bar i is the lowest in its neighborhood
        left_lows = lows[i - lookback : i]
        right_lows = lows[i + 1 : i + lookback + 1]
        if lows[i] <= min(left_lows) and lows[i] <= min(right_lows):
            strength = sum(1 for lo in left_lows + right_lows if lo > lows[i])
            swing_lows.append(SwingPoint(
                price=lows[i],
                index=i,
                swing_type="low",
                strength=max(strength, 1),
            ))

    return swing_highs, swing_lows


def _classify_structure(
    swing_highs: list[SwingPoint],
    swing_lows: list[SwingPoint],
    min_swings: int = 2,
) -> tuple[StructureType, Direction, float]:
    """Classify market structure from the last two swing points of each type.

    Returns (structure_type, direction, trend_strength).
    Trend strength measures how cleanly the swings align (0–1).
    """
    if len(swing_highs) < min_swings or len(swing_lows) < min_swings:
        return StructureType.CONSOLIDATION, Direction.NONE, 0.0

    h1, h2 = swing_highs[-2], swing_highs[-1]  # older, newer
    l1, l2 = swing_lows[-2], swing_lows[-1]

    hh = h2.price > h1.price  # Higher High
    lh = h2.price < h1.price  # Lower High
    hl = l2.price > l1.price  # Higher Low
    ll = l2.price < l1.price  # Lower Low

    # Bullish structure: HH + HL
    if hh and hl:
        strength = _trend_strength(h1.price, h2.price, l1.price, l2.price, bullish=True)
        return StructureType.HIGHER_HIGH, Direction.LONG, strength

    # Bearish structure: LH + LL
    if lh and ll:
        strength = _trend_strength(h1.price, h2.price, l1.price, l2.price, bullish=False)
        return StructureType.LOWER_LOW, Direction.SHORT, strength

    # Mixed signals — one leg is trending
    if hh:
        return StructureType.HIGHER_HIGH, Direction.LONG, 0.3
    if ll:
        return StructureType.LOWER_LOW, Direction.SHORT, 0.3
    if hl:
        return StructureType.HIGHER_LOW, Direction.LONG, 0.2
    if lh:
        return StructureType.LOWER_HIGH, Direction.SHORT, 0.2

    return StructureType.CONSOLIDATION, Direction.NONE, 0.0


def _trend_strength(
    h1: float, h2: float,
    l1: float, l2: float,
    bullish: bool,
) -> float:
    """Score how cleanly the swing sequence confirms the trend (0–1).

    Perfect HH+HL = 1.0, barely HH+HL = 0.3.
    """
    if bullish:
        hh_pct = (h2 - h1) / max(abs(h1), 1e-10)
        hl_pct = (l2 - l1) / max(abs(l1), 1e-10)
    else:
        hh_pct = (h1 - h2) / max(abs(h1), 1e-10)
        hl_pct = (l1 - l2) / max(abs(l1), 1e-10)

    # Both legs should be positive and meaningful
    avg_move = (hh_pct + hl_pct) / 2
    # Map: 0% move → 0.3, 2%+ move → 1.0
    strength = 0.3 + min(avg_move / 0.02, 0.7)
    return round(min(strength, 1.0), 3)


def _detect_bos(
    swing_highs: list[SwingPoint],
    swing_lows: list[SwingPoint],
    current_price: float,
    confirm_bars: int = 2,
) -> tuple[bool, Direction]:
    """Detect Break of Structure (BOS).

    BOS occurs when price breaks beyond the most recent swing high (bullish BOS)
    or swing low (bearish BOS), confirming the current trend direction continues.
    """
    if not swing_highs and not swing_lows:
        return False, Direction.NONE

    # Bullish BOS: price breaks above the last swing high
    if swing_highs:
        last_sh = swing_highs[-1]
        if current_price > last_sh.price:
            return True, Direction.LONG

    # Bearish BOS: price breaks below the last swing low
    if swing_lows:
        last_sl = swing_lows[-1]
        if current_price < last_sl.price:
            return True, Direction.SHORT

    return False, Direction.NONE


def _detect_choch(
    prev_structure: StructureType | None,
    current_structure: StructureType,
    prev_direction: Direction | None,
    current_direction: Direction,
) -> bool:
    """Detect Change of Character (CHoCH).

    CHoCH occurs when market structure flips direction:
    - From bullish (HH/HL) to bearish (LH/LL) or vice versa
    - This signals a potential trend reversal
    """
    if prev_structure is None or prev_direction is None:
        return False

    # Direct direction flip
    if prev_direction != Direction.NONE and current_direction != Direction.NONE:
        if prev_direction != current_direction:
            return True

    # Structure type flip
    bullish_types = {StructureType.HIGHER_HIGH, StructureType.HIGHER_LOW}
    bearish_types = {StructureType.LOWER_LOW, StructureType.LOWER_HIGH}

    if prev_structure in bullish_types and current_structure in bearish_types:
        return True
    if prev_structure in bearish_types and current_structure in bullish_types:
        return True

    return False


class MarketStructure(AlphaStackStep):
    step_number = 4
    step_name = "market_structure"

    async def execute(self, context: AlphaStackContext) -> AlphaStackContext:
        md = context.market_data

        highs: list[float] = md.get("highs", [])
        lows: list[float] = md.get("lows", [])
        closes: list[float] = md.get("closes", [])
        current_price: float = closes[-1] if closes else md.get("close", 0.0)

        lookback: int = md.get(
            "swing_lookback",
            strategy_params.get("structure.swing_lookback", 5),
        )
        min_swings: int = strategy_params.get("structure.min_swings_required", 2)
        keep_n: int = strategy_params.get("structure.keep_last_n_swings", 5)

        # Detect fractal swing points
        raw_sh, raw_sl = _detect_fractal_swings(highs, lows, lookback)

        # Classify structure from swing sequence
        structure_type, direction, trend_strength = _classify_structure(
            raw_sh, raw_sl, min_swings,
        )

        # Detect BOS — price breaks beyond the last swing
        bos_detected, bos_direction = _detect_bos(raw_sh, raw_sl, current_price)

        # Detect CHoCH — structure direction flip
        prev_structure_type = md.get("prev_structure_type")
        prev_direction = md.get("prev_direction")
        choch_detected = _detect_choch(
            prev_structure_type,
            structure_type,
            prev_direction,
            direction,
        )

        # Build the swing point lists for the context (price only)
        swing_highs = [sp.price for sp in raw_sh[-keep_n:]]
        swing_lows = [sp.price for sp in raw_sl[-keep_n:]]

        # Extract last HH, HL, LH, LL for downstream use
        last_hh = swing_highs[-1] if swing_highs and direction == Direction.LONG else None
        last_hl = swing_lows[-1] if swing_lows and direction == Direction.LONG else None
        last_lh = swing_highs[-1] if swing_highs and direction == Direction.SHORT else None
        last_ll = swing_lows[-1] if swing_lows and direction == Direction.SHORT else None

        structure = StructureData(
            structure_type=structure_type,
            direction=direction,
            swing_highs=swing_highs,
            swing_lows=swing_lows,
        )

        # Store extended structure data in market_data for downstream steps
        md = dict(context.market_data)
        md["prev_structure_type"] = structure_type
        md["prev_direction"] = direction
        md["trend_strength"] = trend_strength
        md["bos_detected"] = bos_detected
        md["bos_direction"] = bos_direction.value if bos_direction else None
        md["choch_detected"] = choch_detected
        md["last_hh"] = last_hh
        md["last_hl"] = last_hl
        md["last_lh"] = last_lh
        md["last_ll"] = last_ll
        md["swing_count"] = len(raw_sh) + len(raw_sl)

        return context.update(structure=structure, market_data=md)
