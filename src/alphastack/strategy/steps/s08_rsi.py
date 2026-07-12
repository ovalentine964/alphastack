"""Step 8: RSI Confirmation — divergence detection, overbought/oversold zones."""

from __future__ import annotations

import math

from alphastack.strategy.context import AlphaStackContext, RSIData
from alphastack.strategy.steps.base import AlphaStackStep


def _compute_rsi(closes: list[float], period: int = 14) -> float:
    """Compute RSI using the standard Wilder smoothing method."""
    if len(closes) < period + 1:
        return 50.0  # not enough data

    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _detect_divergence(prices: list[float], rsi_values: list[float], lookback: int = 5) -> str:
    """Detect bullish/bearish divergence between price and RSI."""
    if len(prices) < lookback * 2 or len(rsi_values) < lookback * 2:
        return "none"

    p_recent = prices[-lookback:]
    p_prev = prices[-lookback * 2 : -lookback]
    r_recent = rsi_values[-lookback:]
    r_prev = rsi_values[-lookback * 2 : -lookback]

    # Bullish: price makes lower low but RSI makes higher low
    if min(p_recent) < min(p_prev) and min(r_recent) > min(r_prev):
        return "bullish"

    # Bearish: price makes higher high but RSI makes lower high
    if max(p_recent) > max(p_prev) and max(r_recent) < max(r_prev):
        return "bearish"

    return "none"


class RSIConfirmation(AlphaStackStep):
    step_number = 8
    step_name = "rsi_confirmation"

    async def execute(self, context: AlphaStackContext) -> AlphaStackContext:
        md = context.market_data

        closes: list[float] = md.get("closes", [])
        period: int = md.get("rsi_period", 14)

        # Compute RSI
        rsi_value = _compute_rsi(closes, period)

        # Overbought / oversold
        if rsi_value >= 70:
            signal = "overbought"
        elif rsi_value <= 30:
            signal = "oversold"
        else:
            signal = "neutral"

        # Build rolling RSI series for divergence detection
        rsi_series: list[float] = []
        for end in range(period + 1, len(closes) + 1):
            rsi_series.append(_compute_rsi(closes[:end], period))

        divergence = _detect_divergence(closes, rsi_series)

        rsi_data = RSIData(
            value=round(rsi_value, 2),
            signal=signal,
            divergence=divergence,
        )

        return context.update(rsi=rsi_data)
