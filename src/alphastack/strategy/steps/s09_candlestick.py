"""Step 9: Candlestick Confirmation — pattern recognition (engulfing, pin bar, etc.)."""

from __future__ import annotations

from alphastack.strategy.context import (
    AlphaStackContext,
    CandlePattern,
    CandlestickData,
    Direction,
)
from alphastack.strategy.steps.base import AlphaStackStep


def _body(o: float, c: float) -> float:
    return abs(c - o)


def _upper_wick(h: float, o: float, c: float) -> float:
    return h - max(o, c)


def _lower_wick(l: float, o: float, c: float) -> float:
    return min(o, c) - l


def _range(h: float, l: float) -> float:
    return h - l if h > l else 1e-10


class CandlestickConfirmation(AlphaStackStep):
    step_number = 9
    step_name = "candlestick_confirmation"

    async def execute(self, context: AlphaStackContext) -> AlphaStackContext:
        md = context.market_data

        opens: list[float] = md.get("opens", [])
        highs: list[float] = md.get("highs", [])
        lows: list[float] = md.get("lows", [])
        closes: list[float] = md.get("closes", [])

        n = min(len(opens), len(highs), len(lows), len(closes))
        if n < 3:
            return context.update(candlestick=CandlestickData())

        patterns: list[CandlePattern] = []

        # Scan last 5 candles for patterns
        start = max(1, n - 5)
        for i in range(start, n):
            o, h, l, c = opens[i], highs[i], lows[i], closes[i]
            body = _body(o, c)
            rng = _range(h, l)
            if rng == 0:
                continue

            body_ratio = body / rng
            uw = _upper_wick(h, o, c)
            lw = _lower_wick(l, o, c)

            # --- Engulfing ---
            if i >= 1:
                po, pc = opens[i - 1], closes[i - 1]
                prev_body = _body(po, pc)
                # Bullish engulfing
                if pc < po and c > o and c > po and o < pc and body > prev_body:
                    patterns.append(CandlePattern(name="bullish_engulfing", direction=Direction.LONG, strength=0.8, index=i))
                # Bearish engulfing
                if pc > po and c < o and c < po and o > pc and body > prev_body:
                    patterns.append(CandlePattern(name="bearish_engulfing", direction=Direction.SHORT, strength=0.8, index=i))

            # --- Pin bar / hammer / shooting star ---
            if body_ratio < 0.35:
                # Hammer (bullish): long lower wick, small upper wick
                if lw > body * 2 and uw < body * 0.5:
                    patterns.append(CandlePattern(name="hammer", direction=Direction.LONG, strength=0.7, index=i))
                # Shooting star (bearish): long upper wick, small lower wick
                if uw > body * 2 and lw < body * 0.5:
                    patterns.append(CandlePattern(name="shooting_star", direction=Direction.SHORT, strength=0.7, index=i))
                # Doji
                if body_ratio < 0.1:
                    patterns.append(CandlePattern(name="doji", direction=Direction.NONE, strength=0.3, index=i))

            # --- Morning / Evening star (3-candle) ---
            if i >= 2:
                o2, c2 = opens[i - 2], closes[i - 2]
                o1, c1 = opens[i - 1], closes[i - 1]
                body2 = _body(o2, c2)
                body1 = _body(o1, c1)
                # Morning star
                if c2 < o2 and body1 < body2 * 0.3 and c > o and c > (o2 + c2) / 2:
                    patterns.append(CandlePattern(name="morning_star", direction=Direction.LONG, strength=0.85, index=i))
                # Evening star
                if c2 > o2 and body1 < body2 * 0.3 and c < o and c < (o2 + c2) / 2:
                    patterns.append(CandlePattern(name="evening_star", direction=Direction.SHORT, strength=0.85, index=i))

        # Aggregate pattern score (0-1)
        if patterns:
            pattern_score = min(sum(p.strength for p in patterns) / 3, 1.0)
        else:
            pattern_score = 0.0

        candlestick = CandlestickData(patterns=patterns, pattern_score=round(pattern_score, 3))
        return context.update(candlestick=candlestick)
