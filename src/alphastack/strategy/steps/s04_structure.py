"""Step 4: Market Structure — HH/HL/LH/LL detection, BOS and CHoCH identification."""

from __future__ import annotations

from alphastack.strategy.context import (
    AlphaStackContext,
    Direction,
    StructureData,
    StructureType,
)
from alphastack.strategy.steps.base import AlphaStackStep


def _detect_swings(highs: list[float], lows: list[float], lookback: int = 3) -> tuple[list[float], list[float]]:
    """Return swing highs and swing lows using a simple lookback method."""
    swing_highs: list[float] = []
    swing_lows: list[float] = []

    for i in range(lookback, len(highs) - lookback):
        if highs[i] == max(highs[i - lookback : i + lookback + 1]):
            swing_highs.append(highs[i])
        if lows[i] == min(lows[i - lookback : i + lookback + 1]):
            swing_lows.append(lows[i])

    return swing_highs, swing_lows


def _classify_structure(swing_highs: list[float], swing_lows: list[float]) -> tuple[StructureType, Direction]:
    """Classify market structure from recent swing points."""
    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return StructureType.CONSOLIDATION, Direction.NONE

    hh = swing_highs[-1] > swing_highs[-2]
    hl = swing_lows[-1] > swing_lows[-2]
    lh = swing_highs[-1] < swing_highs[-2]
    ll = swing_lows[-1] < swing_lows[-2]

    if hh and hl:
        return StructureType.HIGHER_HIGH, Direction.LONG
    if lh and ll:
        return StructureType.LOWER_LOW, Direction.SHORT
    if hh:
        return StructureType.HIGHER_HIGH, Direction.LONG
    if ll:
        return StructureType.LOWER_LOW, Direction.SHORT
    if hl:
        return StructureType.HIGHER_LOW, Direction.LONG
    if lh:
        return StructureType.LOWER_HIGH, Direction.SHORT

    return StructureType.CONSOLIDATION, Direction.NONE


class MarketStructure(AlphaStackStep):
    step_number = 4
    step_name = "market_structure"

    async def execute(self, context: AlphaStackContext) -> AlphaStackContext:
        md = context.market_data

        highs: list[float] = md.get("highs", [])
        lows: list[float] = md.get("lows", [])

        lookback: int = md.get("swing_lookback", 3)
        swing_highs, swing_lows = _detect_swings(highs, lows, lookback)
        structure_type, direction = _classify_structure(swing_highs, swing_lows)

        # Detect Break of Structure (BOS) — price breaks beyond the last swing
        current_price: float = md.get("close", 0.0)
        bos = False
        choch = False

        if swing_highs and current_price > swing_highs[-1]:
            bos = True
        if swing_lows and current_price < swing_lows[-1]:
            bos = True

        # Change of Character (CHoCH): structure flips direction
        prev_structure = context.market_data.get("prev_structure", None)
        if prev_structure and prev_structure != structure_type.value:
            choch = True

        structure = StructureData(
            structure_type=structure_type,
            direction=direction,
            swing_highs=swing_highs[-5:],  # keep last 5
            swing_lows=swing_lows[-5:],
        )

        return context.update(structure=structure)
