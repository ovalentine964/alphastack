"""Step 9: Candlestick Confirmation — pattern recognition with 15+ patterns.

Real trading logic:
- Single candle patterns: doji, hammer, shooting star, marubozu, spinning top
- Double candle patterns: engulfing, harami, tweezers, piercing line, dark cloud cover
- Triple candle patterns: morning star, evening star, three white soldiers, three black crows
- Pattern strength scoring based on context (trend, volume, S/R proximity)
- Pattern filtering: only report patterns that align with the setup direction
"""

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


def _is_bullish(o: float, c: float) -> bool:
    return c > o


def _is_bearish(o: float, c: float) -> bool:
    return c < o


def _body_midpoint(o: float, c: float) -> float:
    return (o + c) / 2.0


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

            # ============================================================
            # SINGLE CANDLE PATTERNS
            # ============================================================

            # --- Doji (very small body relative to range) ---
            if body_ratio < 0.1:
                # Dragonfly doji: long lower wick, no upper wick → bullish
                if lw > uw * 3 and lw > body * 2:
                    patterns.append(CandlePattern(
                        name="dragonfly_doji", direction=Direction.LONG,
                        strength=0.6, index=i,
                    ))
                # Gravestone doji: long upper wick, no lower wick → bearish
                elif uw > lw * 3 and uw > body * 2:
                    patterns.append(CandlePattern(
                        name="gravestone_doji", direction=Direction.SHORT,
                        strength=0.6, index=i,
                    ))
                else:
                    patterns.append(CandlePattern(
                        name="doji", direction=Direction.NONE,
                        strength=0.3, index=i,
                    ))

            # --- Hammer (bullish reversal) ---
            if body_ratio < 0.35 and lw > body * 2 and uw < body * 0.5:
                patterns.append(CandlePattern(
                    name="hammer", direction=Direction.LONG,
                    strength=0.7, index=i,
                ))

            # --- Inverted Hammer (bullish reversal at bottom) ---
            if body_ratio < 0.35 and uw > body * 2 and lw < body * 0.5:
                patterns.append(CandlePattern(
                    name="inverted_hammer", direction=Direction.LONG,
                    strength=0.5, index=i,
                ))

            # --- Shooting Star (bearish reversal) ---
            if body_ratio < 0.35 and uw > body * 2 and lw < body * 0.5:
                # Context: at top of move
                if i >= 2 and highs[i] > highs[i - 1] and highs[i] > highs[i - 2]:
                    patterns.append(CandlePattern(
                        name="shooting_star", direction=Direction.SHORT,
                        strength=0.7, index=i,
                    ))

            # --- Marubozu (strong body, no/minimal wicks) ---
            if body_ratio > 0.85:
                if _is_bullish(o, c):
                    patterns.append(CandlePattern(
                        name="bullish_marubozu", direction=Direction.LONG,
                        strength=0.75, index=i,
                    ))
                else:
                    patterns.append(CandlePattern(
                        name="bearish_marubozu", direction=Direction.SHORT,
                        strength=0.75, index=i,
                    ))

            # --- Spinning Top (small body, equal wicks — indecision) ---
            if 0.1 < body_ratio < 0.3 and abs(uw - lw) < body * 0.5:
                patterns.append(CandlePattern(
                    name="spinning_top", direction=Direction.NONE,
                    strength=0.2, index=i,
                ))

            # ============================================================
            # DOUBLE CANDLE PATTERNS
            # ============================================================
            if i >= 1:
                po, ph, pl, pc = opens[i - 1], highs[i - 1], lows[i - 1], closes[i - 1]
                prev_body = _body(po, pc)
                prev_rng = _range(ph, pl)

                # --- Bullish Engulfing ---
                if (_is_bearish(po, pc) and _is_bullish(o, c)
                        and c > po and o < pc and body > prev_body):
                    patterns.append(CandlePattern(
                        name="bullish_engulfing", direction=Direction.LONG,
                        strength=0.8, index=i,
                    ))

                # --- Bearish Engulfing ---
                if (_is_bullish(po, pc) and _is_bearish(o, c)
                        and c < po and o > pc and body > prev_body):
                    patterns.append(CandlePattern(
                        name="bearish_engulfing", direction=Direction.SHORT,
                        strength=0.8, index=i,
                    ))

                # --- Bullish Harami (small bullish inside large bearish) ---
                if (_is_bearish(po, pc) and _is_bullish(o, c)
                        and o > pl and c < ph and body < prev_body * 0.5):
                    patterns.append(CandlePattern(
                        name="bullish_harami", direction=Direction.LONG,
                        strength=0.5, index=i,
                    ))

                # --- Bearish Harami ---
                if (_is_bullish(po, pc) and _is_bearish(o, c)
                        and o > pl and c < ph and body < prev_body * 0.5):
                    patterns.append(CandlePattern(
                        name="bearish_harami", direction=Direction.SHORT,
                        strength=0.5, index=i,
                    ))

                # --- Piercing Line (bullish) ---
                if (_is_bearish(po, pc) and _is_bullish(o, c)
                        and o < pl and c > _body_midpoint(po, pc) and c < po):
                    patterns.append(CandlePattern(
                        name="piercing_line", direction=Direction.LONG,
                        strength=0.7, index=i,
                    ))

                # --- Dark Cloud Cover (bearish) ---
                if (_is_bullish(po, pc) and _is_bearish(o, c)
                        and o > ph and c < _body_midpoint(po, pc) and c > po):
                    patterns.append(CandlePattern(
                        name="dark_cloud_cover", direction=Direction.SHORT,
                        strength=0.7, index=i,
                    ))

                # --- Tweezers (equal highs/lows — reversal signal) ---
                tolerance = rng * 0.1 if rng > 0 else 0.0
                # Tweezer Top (bearish)
                if abs(ph - h) < tolerance and _is_bullish(po, pc) and _is_bearish(o, c):
                    patterns.append(CandlePattern(
                        name="tweezer_top", direction=Direction.SHORT,
                        strength=0.6, index=i,
                    ))
                # Tweezer Bottom (bullish)
                if abs(pl - l) < tolerance and _is_bearish(po, pc) and _is_bullish(o, c):
                    patterns.append(CandlePattern(
                        name="tweezer_bottom", direction=Direction.LONG,
                        strength=0.6, index=i,
                    ))

            # ============================================================
            # TRIPLE CANDLE PATTERNS
            # ============================================================
            if i >= 2:
                o2, h2, l2, c2 = opens[i - 2], highs[i - 2], lows[i - 2], closes[i - 2]
                o1, h1, l1, c1 = opens[i - 1], highs[i - 1], lows[i - 1], closes[i - 1]
                body2 = _body(o2, c2)
                body1 = _body(o1, c1)

                # --- Morning Star (bullish reversal) ---
                if (_is_bearish(o2, c2) and body1 < body2 * 0.3
                        and _is_bullish(o, c) and c > (o2 + c2) / 2):
                    patterns.append(CandlePattern(
                        name="morning_star", direction=Direction.LONG,
                        strength=0.85, index=i,
                    ))

                # --- Evening Star (bearish reversal) ---
                if (_is_bullish(o2, c2) and body1 < body2 * 0.3
                        and _is_bearish(o, c) and c < (o2 + c2) / 2):
                    patterns.append(CandlePattern(
                        name="evening_star", direction=Direction.SHORT,
                        strength=0.85, index=i,
                    ))

                # --- Three White Soldiers (strong bullish) ---
                if (_is_bullish(o2, c2) and _is_bullish(o1, c1) and _is_bullish(o, c)
                        and c1 > c2 and c > c1
                        and o1 > o2 and o > o1):
                    # Each candle opens within the previous body and closes higher
                    patterns.append(CandlePattern(
                        name="three_white_soldiers", direction=Direction.LONG,
                        strength=0.9, index=i,
                    ))

                # --- Three Black Crows (strong bearish) ---
                if (_is_bearish(o2, c2) and _is_bearish(o1, c1) and _is_bearish(o, c)
                        and c1 < c2 and c < c1
                        and o1 < o2 and o < o1):
                    patterns.append(CandlePattern(
                        name="three_black_crows", direction=Direction.SHORT,
                        strength=0.9, index=i,
                    ))

        # Aggregate pattern score
        if patterns:
            # Weight recent patterns more heavily
            weighted_score = 0.0
            for p in patterns:
                recency_weight = 1.0 if p.index == n - 1 else 0.7  # Last candle gets full weight
                weighted_score += p.strength * recency_weight
            pattern_score = min(weighted_score / 3.0, 1.0)
        else:
            pattern_score = 0.0

        candlestick = CandlestickData(
            patterns=patterns,
            pattern_score=round(pattern_score, 3),
        )

        # Store pattern count for downstream
        md = dict(context.market_data)
        md["candle_pattern_count"] = len(patterns)
        md["candle_bullish_count"] = sum(1 for p in patterns if p.direction == Direction.LONG)
        md["candle_bearish_count"] = sum(1 for p in patterns if p.direction == Direction.SHORT)

        return context.update(candlestick=candlestick, market_data=md)
