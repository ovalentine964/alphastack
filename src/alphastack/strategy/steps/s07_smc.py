"""Step 7: Smart Money Concepts — order blocks, fair value gaps, breaker blocks."""

from __future__ import annotations

from alphastack.strategy.context import (
    AlphaStackContext,
    Direction,
    FairValueGap,
    OrderBlock,
    SMCData,
)
from alphastack.strategy.steps.base import AlphaStackStep


class SmartMoneyConcepts(AlphaStackStep):
    step_number = 7
    step_name = "smart_money_concepts"

    async def execute(self, context: AlphaStackContext) -> AlphaStackContext:
        md = context.market_data

        opens: list[float] = md.get("opens", [])
        highs: list[float] = md.get("highs", [])
        lows: list[float] = md.get("lows", [])
        closes: list[float] = md.get("closes", [])
        current_price: float = closes[-1] if closes else 0.0

        order_blocks = self._detect_order_blocks(opens, highs, lows, closes, current_price)
        fvgs = self._detect_fvgs(opens, highs, lows, closes)
        breaker_blocks = self._detect_breaker_blocks(order_blocks, highs, lows, current_price)

        smc = SMCData(
            order_blocks=order_blocks,
            fvgs=fvgs,
            breaker_blocks=breaker_blocks,
        )

        return context.update(smc=smc)

    # ------------------------------------------------------------------

    @staticmethod
    def _detect_order_blocks(
        opens: list[float],
        highs: list[float],
        lows: list[float],
        closes: list[float],
        current_price: float,
    ) -> list[OrderBlock]:
        """Detect the last bearish OB (for shorts) and bullish OB (for longs)."""
        obs: list[OrderBlock] = []
        n = min(len(opens), len(highs), len(lows), len(closes))

        for i in range(1, n):
            # Bullish OB: last bearish candle before a strong up move
            if closes[i - 1] < opens[i - 1] and closes[i] > opens[i] and closes[i] > highs[i - 1]:
                obs.append(OrderBlock(high=highs[i - 1], low=lows[i - 1], direction=Direction.LONG))

            # Bearish OB: last bullish candle before a strong down move
            if closes[i - 1] > opens[i - 1] and closes[i] < opens[i] and closes[i] < lows[i - 1]:
                obs.append(OrderBlock(high=highs[i - 1], low=lows[i - 1], direction=Direction.SHORT))

        # Mark mitigated OBs
        for ob in obs:
            if ob.direction == Direction.LONG and current_price < ob.low:
                ob.mitigated = True
            if ob.direction == Direction.SHORT and current_price > ob.high:
                ob.mitigated = True

        # Keep last 5 unmitigated
        return [ob for ob in obs if not ob.mitigated][-5:]

    @staticmethod
    def _detect_fvgs(
        opens: list[float],
        highs: list[float],
        lows: list[float],
        closes: list[float],
    ) -> list[FairValueGap]:
        """Detect Fair Value Gaps (3-candle imbalance)."""
        fvgs: list[FairValueGap] = []
        n = min(len(opens), len(highs), len(lows), len(closes))

        for i in range(2, n):
            # Bullish FVG: candle 1 high < candle 3 low
            if highs[i - 2] < lows[i]:
                fvgs.append(FairValueGap(high=lows[i], low=highs[i - 2], direction=Direction.LONG))
            # Bearish FVG: candle 1 low > candle 3 high
            if lows[i - 2] > highs[i]:
                fvgs.append(FairValueGap(high=lows[i - 2], low=highs[i], direction=Direction.SHORT))

        # Keep last 5
        return fvgs[-5:]

    @staticmethod
    def _detect_breaker_blocks(
        order_blocks: list[OrderBlock],
        highs: list[float],
        lows: list[float],
        current_price: float,
    ) -> list[OrderBlock]:
        """Breaker blocks = OBs that were mitigated and then became S/R."""
        # Simplified: re-use mitigated OBs (already filtered out above;
        # in production you'd keep a separate pool)
        return []
