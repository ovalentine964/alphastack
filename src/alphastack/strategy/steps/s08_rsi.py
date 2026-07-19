"""Step 8: RSI Confirmation — divergence detection, overbought/oversold, RSI trendline breaks.

Real trading logic:
- Wilder's smoothing RSI calculation (standard method)
- Bullish/bearish divergence detection with configurable lookback
- RSI trendline break detection (RSI breaks its own trendline → momentum shift)
- Overbought/oversold zones with regime-adaptive thresholds
- RSI slope analysis for momentum strength
- Multi-zone signal: extreme zones (< 20, > 80) vs standard zones (< 30, > 70)
"""

from __future__ import annotations

from alphastack.strategy.context import AlphaStackContext, RSIData
from alphastack.strategy.steps.base import AlphaStackStep
from alphastack.strategy.config import strategy_params


def _compute_rsi_series(closes: list[float], period: int = 14) -> list[float]:
    """Compute full RSI series using Wilder's smoothing method.

    Returns a list of RSI values (same length as closes, first `period` values are 50.0).
    """
    if len(closes) < period + 1:
        return [50.0] * len(closes)

    rsi_values = [50.0] * period  # Pad start with neutral

    # Compute initial average gain/loss
    deltas = [closes[i] - closes[i - 1] for i in range(1, period + 1)]
    gains = [d if d > 0 else 0.0 for d in deltas]
    losses = [-d if d < 0 else 0.0 for d in deltas]

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    # First RSI value
    if avg_loss == 0:
        rsi_values.append(100.0)
    else:
        rs = avg_gain / avg_loss
        rsi_values.append(100.0 - (100.0 / (1.0 + rs)))

    # Continue with Wilder's smoothing
    for i in range(period + 1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gain = delta if delta > 0 else 0.0
        loss = -delta if delta < 0 else 0.0

        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

        if avg_loss == 0:
            rsi_values.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi_values.append(100.0 - (100.0 / (1.0 + rs)))

    return rsi_values


def _compute_rsi(closes: list[float], period: int = 14) -> float:
    """Compute current RSI value (last value from the series)."""
    series = _compute_rsi_series(closes, period)
    return series[-1] if series else 50.0


def _detect_divergence(
    prices: list[float],
    rsi_values: list[float],
    lookback: int = 10,
) -> str:
    """Detect bullish/bearish divergence between price and RSI.

    Bullish divergence: price makes lower low, RSI makes higher low
      → momentum is shifting bullish despite lower prices
    Bearish divergence: price makes higher high, RSI makes lower high
      → momentum is shifting bearish despite higher prices

    Uses swing detection for more reliable divergence identification.
    """
    if len(prices) < lookback * 2 or len(rsi_values) < lookback * 2:
        return "none"

    p_recent = prices[-lookback:]
    p_prev = prices[-lookback * 2 : -lookback]
    r_recent = rsi_values[-lookback:]
    r_prev = rsi_values[-lookback * 2 : -lookback]

    # Find swing lows in price and RSI
    p_recent_low = min(p_recent)
    p_prev_low = min(p_prev)
    r_recent_low = min(r_recent)
    r_prev_low = min(r_prev)

    # Find swing highs in price and RSI
    p_recent_high = max(p_recent)
    p_prev_high = max(p_prev)
    r_recent_high = max(r_recent)
    r_prev_high = max(r_prev)

    # Bullish divergence: price lower low + RSI higher low
    if p_recent_low < p_prev_low and r_recent_low > r_prev_low:
        # Strength check: RSI divergence should be meaningful
        rsi_diff = r_recent_low - r_prev_low
        if rsi_diff > 2.0:  # At least 2 RSI points of divergence
            return "bullish"

    # Bearish divergence: price higher high + RSI lower high
    if p_recent_high > p_prev_high and r_recent_high < r_prev_high:
        rsi_diff = r_prev_high - r_recent_high
        if rsi_diff > 2.0:
            return "bearish"

    return "none"


def _detect_rsi_trendline_break(
    rsi_values: list[float],
    lookback: int = 10,
) -> str:
    """Detect when RSI breaks its own trendline.

    A trendline break in RSI often precedes a price trendline break.
    - RSI breaking above its downtrend line → bullish signal
    - RSI breaking below its uptrend line → bearish signal
    """
    if len(rsi_values) < lookback + 2:
        return "none"

    recent_rsi = rsi_values[-lookback:]
    current_rsi = rsi_values[-1]

    # Simple linear regression on RSI
    n = len(recent_rsi)
    x_mean = (n - 1) / 2
    y_mean = sum(recent_rsi) / n

    numerator = sum((i - x_mean) * (recent_rsi[i] - y_mean) for i in range(n))
    denominator = sum((i - x_mean) ** 2 for i in range(n))

    if denominator == 0:
        return "none"

    slope = numerator / denominator
    intercept = y_mean - slope * x_mean

    # Expected RSI value from trendline
    expected_rsi = slope * (n - 1) + intercept

    # Break detection
    if slope < 0 and current_rsi > expected_rsi + 3:
        # RSI was in downtrend, now breaking above → bullish
        return "bullish_break"
    elif slope > 0 and current_rsi < expected_rsi - 3:
        # RSI was in uptrend, now breaking below → bearish
        return "bearish_break"

    return "none"


def _rsi_momentum(rsi_values: list[float], lookback: int = 5) -> float:
    """Compute RSI momentum (slope of recent RSI values).

    Returns a value from -1 (strong bearish momentum) to +1 (strong bullish).
    """
    if len(rsi_values) < lookback:
        return 0.0

    recent = rsi_values[-lookback:]
    # Simple slope: difference between first and last
    slope = (recent[-1] - recent[0]) / lookback

    # Normalize: RSI typically moves 0-100, slope of 5/bar is strong
    momentum = slope / 5.0
    return max(min(momentum, 1.0), -1.0)


def _get_signal_zone(
    rsi_value: float,
    ob_level: float,
    os_level: float,
) -> str:
    """Classify RSI into signal zones.

    Returns:
    - "extreme_overbought" (> 80): very strong sell signal
    - "overbought" (> ob_level): sell signal
    - "neutral_high" (50 to ob_level): slight bullish bias
    - "neutral_low" (os_level to 50): slight bearish bias
    - "oversold" (< os_level): buy signal
    - "extreme_oversold" (< 20): very strong buy signal
    """
    if rsi_value > 80:
        return "extreme_overbought"
    elif rsi_value >= ob_level:
        return "overbought"
    elif rsi_value > 50:
        return "neutral_high"
    elif rsi_value >= os_level:
        return "neutral_low"
    elif rsi_value >= 20:
        return "oversold"
    else:
        return "extreme_oversold"


class RSIConfirmation(AlphaStackStep):
    step_number = 8
    step_name = "rsi_confirmation"

    async def execute(self, context: AlphaStackContext) -> AlphaStackContext:
        md = context.market_data

        closes: list[float] = md.get("closes", [])
        period: int = md.get("rsi_period", strategy_params.get("rsi.period", 14))

        # Compute full RSI series (efficient — single pass)
        rsi_series = _compute_rsi_series(closes, period)
        rsi_value = rsi_series[-1] if rsi_series else 50.0

        # Regime-adaptive thresholds
        regime = md.get("regime", None)
        ob_level = strategy_params.get_regime_override("rsi.overbought", regime, 70) if regime else strategy_params.get("rsi.overbought", 70)
        os_level = strategy_params.get_regime_override("rsi.oversold", regime, 30) if regime else strategy_params.get("rsi.oversold", 30)

        # Signal zone classification
        signal_zone = _get_signal_zone(rsi_value, ob_level, os_level)

        # Standard signal for backward compatibility
        if "overbought" in signal_zone:
            signal = "overbought"
        elif "oversold" in signal_zone:
            signal = "oversold"
        else:
            signal = "neutral"

        # Divergence detection
        div_lookback = strategy_params.get("rsi.divergence_lookback", 10)
        divergence = _detect_divergence(closes, rsi_series, lookback=div_lookback)

        # RSI trendline break
        trendline_break = _detect_rsi_trendline_break(rsi_series, lookback=div_lookback)

        # RSI momentum
        momentum = _rsi_momentum(rsi_series)

        rsi_data = RSIData(
            value=round(rsi_value, 2),
            signal=signal,
            divergence=divergence,
        )

        # Store extended RSI data in market_data
        md = dict(context.market_data)
        md["rsi_series"] = rsi_series[-20:]  # Keep last 20 for downstream
        md["rsi_zone"] = signal_zone
        md["rsi_trendline_break"] = trendline_break
        md["rsi_momentum"] = round(momentum, 3)
        md["rsi_ob_level"] = ob_level
        md["rsi_os_level"] = os_level

        return context.update(rsi=rsi_data, market_data=md)
