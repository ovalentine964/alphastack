"""Signal generation engine — technical indicators, SMC, confluence scoring.

Provides production-ready signal generation using:
  - Technical indicators (RSI, MACD, Bollinger Bands, ATR, EMA, ADX, OBV)
  - Smart Money Concepts (order blocks, FVGs, breaker blocks, liquidity sweeps)
  - Support/Resistance level detection
  - Confluence scoring with weighted component aggregation
  - Signal confidence scoring

All functions operate on numpy arrays for performance.
Designed for integration with the AlphaStack 16-step pipeline.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np

from alphastack.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Signal types
# ---------------------------------------------------------------------------

class SignalSide(str, Enum):
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


class SignalStrength(str, Enum):
    WEAK = "weak"         # 0.0–0.3
    MODERATE = "moderate"  # 0.3–0.6
    STRONG = "strong"      # 0.6–0.8
    VERY_STRONG = "very_strong"  # 0.8–1.0


@dataclass
class Signal:
    """A trade signal with full context."""
    symbol: str
    side: SignalSide
    strength: float              # 0.0–1.0
    confluence_score: float      # 0.0–100.0
    confidence: float            # 0.0–1.0
    entry_price: float | None = None
    stop_loss: float | None = None
    take_profit: list[float] = field(default_factory=list)
    reasoning: str = ""
    timeframe: str = "1h"
    strategy: str = "alphastack"
    indicators: dict[str, float] = field(default_factory=dict)
    smc_context: dict[str, Any] = field(default_factory=dict)
    regime: str = "unknown"
    timestamp: float = field(default_factory=lambda: __import__('time').time())

    @property
    def strength_label(self) -> str:
        if self.strength < 0.3:
            return SignalStrength.WEAK.value
        if self.strength < 0.6:
            return SignalStrength.MODERATE.value
        if self.strength < 0.8:
            return SignalStrength.STRONG.value
        return SignalStrength.VERY_STRONG.value

    @property
    def is_actionable(self) -> bool:
        """Signal meets minimum thresholds for trade execution."""
        return (
            self.side != SignalSide.FLAT
            and self.strength >= 0.4
            and self.confluence_score >= 40.0
            and self.confidence >= 0.5
        )


# ---------------------------------------------------------------------------
# Technical indicators (numpy-based for performance)
# ---------------------------------------------------------------------------

def compute_rsi(closes: np.ndarray, period: int = 14) -> np.ndarray:
    """Compute RSI using Wilder's smoothing method.

    Returns array same length as input; first `period` values are NaN.
    """
    if len(closes) < period + 1:
        return np.full(len(closes), np.nan)

    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    # Wilder smoothing
    avg_gain = np.empty(len(closes))
    avg_loss = np.empty(len(closes))
    avg_gain[:] = np.nan
    avg_loss[:] = np.nan

    avg_gain[period] = np.mean(gains[:period])
    avg_loss[period] = np.mean(losses[:period])

    for i in range(period + 1, len(closes)):
        avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gains[i - 1]) / period
        avg_loss[i] = (avg_loss[i - 1] * (period - 1) + losses[i - 1]) / period

    rs = np.where(avg_loss > 0, avg_gain / avg_loss, 100.0)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    rsi[:period] = np.nan
    return rsi


def compute_macd(
    closes: np.ndarray,
    fast: int = 12,
    slow: int = 26,
    signal_period: int = 9,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute MACD line, signal line, and histogram.

    Returns (macd_line, signal_line, histogram).
    """
    ema_fast = _ema(closes, fast)
    ema_slow = _ema(closes, slow)
    macd_line = ema_fast - ema_slow
    signal_line = _ema(macd_line, signal_period)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def compute_bollinger_bands(
    closes: np.ndarray,
    period: int = 20,
    std_dev: float = 2.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute Bollinger Bands (upper, middle, lower)."""
    middle = _sma(closes, period)
    rolling_std = _rolling_std(closes, period)
    upper = middle + std_dev * rolling_std
    lower = middle - std_dev * rolling_std
    return upper, middle, lower


def compute_atr(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    period: int = 14,
) -> np.ndarray:
    """Compute Average True Range using Wilder's smoothing."""
    if len(closes) < 2:
        return np.full(len(closes), np.nan)

    tr = np.empty(len(closes))
    tr[0] = highs[0] - lows[0]
    for i in range(1, len(closes)):
        tr[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )

    atr = np.empty(len(closes))
    atr[:] = np.nan
    if len(tr) < period:
        return atr

    atr[period - 1] = np.mean(tr[:period])
    for i in range(period, len(closes)):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period

    return atr


def compute_ema(data: np.ndarray, period: int) -> np.ndarray:
    """Compute Exponential Moving Average."""
    return _ema(data, period)


def compute_adx(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    period: int = 14,
) -> np.ndarray:
    """Compute Average Directional Index."""
    if len(closes) < period + 1:
        return np.full(len(closes), np.nan)

    # True Range
    tr = compute_atr(highs, lows, closes, period=1)  # raw TR, not smoothed

    # Directional Movement
    up_move = np.diff(highs)
    down_move = -np.diff(lows)
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    # Smoothed TR, +DM, -DM (Wilder)
    atr_smooth = _wilders_smooth(tr[1:], period)
    plus_di = 100.0 * _wilders_smooth(plus_dm, period) / np.where(atr_smooth > 0, atr_smooth, 1.0)
    minus_di = 100.0 * _wilders_smooth(minus_dm, period) / np.where(atr_smooth > 0, atr_smooth, 1.0)

    # DX and ADX
    di_sum = plus_di + minus_di
    dx = np.where(di_sum > 0, 100.0 * np.abs(plus_di - minus_di) / di_sum, 0.0)
    adx = _wilders_smooth(dx, period)

    # Pad to match input length
    result = np.full(len(closes), np.nan)
    result[period:] = adx[: len(closes) - period]
    return result


def compute_obv(closes: np.ndarray, volumes: np.ndarray) -> np.ndarray:
    """Compute On-Balance Volume."""
    obv = np.zeros(len(closes))
    for i in range(1, len(closes)):
        if closes[i] > closes[i - 1]:
            obv[i] = obv[i - 1] + volumes[i]
        elif closes[i] < closes[i - 1]:
            obv[i] = obv[i - 1] - volumes[i]
        else:
            obv[i] = obv[i - 1]
    return obv


def compute_stochastic(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    k_period: int = 14,
    d_period: int = 3,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute Stochastic %K and %D."""
    k = np.full(len(closes), np.nan)
    for i in range(k_period - 1, len(closes)):
        window_high = np.max(highs[i - k_period + 1 : i + 1])
        window_low = np.min(lows[i - k_period + 1 : i + 1])
        if window_high != window_low:
            k[i] = 100.0 * (closes[i] - window_low) / (window_high - window_low)
        else:
            k[i] = 50.0

    d = _sma(k, d_period)
    return k, d


def compute_vwap(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    volumes: np.ndarray,
) -> np.ndarray:
    """Compute Volume-Weighted Average Price (cumulative)."""
    typical_price = (highs + lows + closes) / 3.0
    cumulative_tp_vol = np.cumsum(typical_price * volumes)
    cumulative_vol = np.cumsum(volumes)
    return np.where(cumulative_vol > 0, cumulative_tp_vol / cumulative_vol, closes)


# ---------------------------------------------------------------------------
# Helper functions (numpy)
# ---------------------------------------------------------------------------

def _ema(data: np.ndarray, period: int) -> np.ndarray:
    """Exponential Moving Average."""
    result = np.empty_like(data, dtype=float)
    result[:] = np.nan
    if len(data) < period:
        return result
    alpha = 2.0 / (period + 1)
    result[period - 1] = np.mean(data[:period])
    for i in range(period, len(data)):
        result[i] = alpha * data[i] + (1 - alpha) * result[i - 1]
    return result


def _sma(data: np.ndarray, period: int) -> np.ndarray:
    """Simple Moving Average (handles NaN)."""
    result = np.full(len(data), np.nan)
    for i in range(period - 1, len(data)):
        window = data[i - period + 1 : i + 1]
        valid = window[~np.isnan(window)]
        if len(valid) > 0:
            result[i] = np.mean(valid)
    return result


def _rolling_std(data: np.ndarray, period: int) -> np.ndarray:
    """Rolling standard deviation."""
    result = np.full(len(data), np.nan)
    for i in range(period - 1, len(data)):
        window = data[i - period + 1 : i + 1]
        valid = window[~np.isnan(window)]
        if len(valid) > 1:
            result[i] = np.std(valid, ddof=1)
    return result


def _wilders_smooth(data: np.ndarray, period: int) -> np.ndarray:
    """Wilder's smoothing (used in ADX, ATR)."""
    result = np.empty(len(data))
    result[:] = np.nan
    if len(data) < period:
        return result
    result[period - 1] = np.mean(data[:period])
    for i in range(period, len(data)):
        result[i] = (result[i - 1] * (period - 1) + data[i]) / period
    return result


# ---------------------------------------------------------------------------
# Smart Money Concepts (SMC) detection
# ---------------------------------------------------------------------------

@dataclass
class OrderBlock:
    """A detected order block."""
    high: float
    low: float
    direction: SignalSide
    index: int
    strength: float = 0.0
    mitigated: bool = False


@dataclass
class FairValueGap:
    """A detected fair value gap."""
    high: float
    low: float
    direction: SignalSide
    index: int
    filled: bool = False


@dataclass
class LiquiditySweep:
    """A detected liquidity sweep (stop hunt)."""
    level: float
    direction: SignalSide  # direction of expected move after sweep
    index: int
    strength: float = 0.0


class SMCDetector:
    """Smart Money Concepts pattern detector.

    Detects:
    - Order blocks (last opposing candle before impulsive move)
    - Fair value gaps (3-candle imbalance)
    - Liquidity sweeps (stop hunts above/below key levels)
    - Breaker blocks (failed order blocks that become S/R)
    """

    def __init__(
        self,
        ob_lookback: int = 50,
        fvg_min_gap_pct: float = 0.001,
        liquidity_threshold_atr: float = 1.5,
    ) -> None:
        self._ob_lookback = ob_lookback
        self._fvg_min_gap_pct = fvg_min_gap_pct
        self._liquidity_threshold_atr = liquidity_threshold_atr

    def detect_order_blocks(
        self,
        opens: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        atr: np.ndarray | None = None,
    ) -> list[OrderBlock]:
        """Detect order blocks — last opposing candle before impulsive move.

        A bullish OB: bearish candle followed by strong bullish move (>1.5× ATR).
        A bearish OB: bullish candle followed by strong bearish move.
        """
        if len(closes) < 3:
            return []

        blocks: list[OrderBlock] = []
        lookback = min(self._ob_lookback, len(closes) - 2)

        for i in range(len(closes) - lookback - 1, len(closes) - 1):
            body = abs(closes[i] - opens[i])
            if atr is not None and not np.isnan(atr[i]) and atr[i] > 0:
                threshold = atr[i] * self._liquidity_threshold_atr
            else:
                threshold = body * 2.0 if body > 0 else 0.0

            # Bullish OB: bearish candle followed by bullish impulsive move
            if closes[i] < opens[i]:  # bearish candle
                move = closes[i + 1] - opens[i + 1]
                if move > threshold and closes[i + 1] > opens[i + 1]:
                    strength = min(move / threshold, 3.0) / 3.0 if threshold > 0 else 0.5
                    blocks.append(OrderBlock(
                        high=float(highs[i]),
                        low=float(lows[i]),
                        direction=SignalSide.LONG,
                        index=i,
                        strength=strength,
                    ))

            # Bearish OB: bullish candle followed by bearish impulsive move
            elif closes[i] > opens[i]:  # bullish candle
                move = opens[i + 1] - closes[i + 1]
                if move > threshold and closes[i + 1] < opens[i + 1]:
                    strength = min(move / threshold, 3.0) / 3.0 if threshold > 0 else 0.5
                    blocks.append(OrderBlock(
                        high=float(highs[i]),
                        low=float(lows[i]),
                        direction=SignalSide.SHORT,
                        index=i,
                        strength=strength,
                    ))

        # Check mitigation (price returned to OB zone)
        current_price = float(closes[-1])
        for block in blocks:
            if block.direction == SignalSide.LONG:
                block.mitigated = current_price <= block.low
            else:
                block.mitigated = current_price >= block.high

        return blocks

    def detect_fair_value_gaps(
        self,
        highs: np.ndarray,
        lows: np.ndarray,
    ) -> list[FairValueGap]:
        """Detect fair value gaps (3-candle imbalance).

        Bullish FVG: candle 3's low > candle 1's high (gap up).
        Bearish FVG: candle 1's low > candle 3's high (gap down).
        """
        if len(highs) < 3:
            return []

        fvgs: list[FairValueGap] = []
        avg_range = np.mean(np.abs(highs - lows)) if len(highs) > 0 else 0.0
        min_gap = avg_range * self._fvg_min_gap_pct * 100  # scale factor

        for i in range(2, len(highs)):
            # Bullish FVG
            gap_low = float(highs[i - 2])
            gap_high = float(lows[i])
            if gap_high > gap_low and (gap_high - gap_low) > min_gap:
                fvgs.append(FairValueGap(
                    high=gap_high,
                    low=gap_low,
                    direction=SignalSide.LONG,
                    index=i - 1,
                ))

            # Bearish FVG
            gap_low = float(lows[i - 2])
            gap_high = float(highs[i])
            if gap_low > gap_high and (gap_low - gap_high) > min_gap:
                fvgs.append(FairValueGap(
                    high=gap_low,
                    low=gap_high,
                    direction=SignalSide.SHORT,
                    index=i - 1,
                ))

        # Check fill status
        current_price = float(highs[-1]) if len(highs) > 0 else 0.0
        for fvg in fvgs:
            if fvg.direction == SignalSide.LONG:
                fvg.filled = current_price <= fvg.low
            else:
                fvg.filled = current_price >= fvg.high

        return fvgs

    def detect_liquidity_sweeps(
        self,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        lookback: int = 20,
    ) -> list[LiquiditySweep]:
        """Detect liquidity sweeps (stop hunts).

        A sweep occurs when price briefly exceeds a recent swing high/low
        then reverses — indicating stop-loss hunting.
        """
        if len(closes) < lookback + 2:
            return []

        sweeps: list[LiquiditySweep] = []
        recent_highs = highs[-lookback:]
        recent_lows = lows[-lookback:]

        swing_high = float(np.max(recent_highs[:-1]))
        swing_low = float(np.min(recent_lows[:-1]))

        # Sweep of highs (bearish — expect downward move)
        if highs[-1] > swing_high and closes[-1] < swing_high:
            sweeps.append(LiquiditySweep(
                level=swing_high,
                direction=SignalSide.SHORT,
                index=len(closes) - 1,
                strength=0.7,
            ))

        # Sweep of lows (bullish — expect upward move)
        if lows[-1] < swing_low and closes[-1] > swing_low:
            sweeps.append(LiquiditySweep(
                level=swing_low,
                direction=SignalSide.LONG,
                index=len(closes) - 1,
                strength=0.7,
            ))

        return sweeps

    def analyze(
        self,
        opens: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        atr: np.ndarray | None = None,
    ) -> dict[str, Any]:
        """Run full SMC analysis and return structured results."""
        order_blocks = self.detect_order_blocks(opens, highs, lows, closes, atr)
        fvgs = self.detect_fair_value_gaps(highs, lows)
        sweeps = self.detect_liquidity_sweeps(highs, lows, closes)

        # Determine SMC bias
        bullish_score = sum(ob.strength for ob in order_blocks if ob.direction == SignalSide.LONG and not ob.mitigated)
        bullish_score += sum(0.5 for fvg in fvgs if fvg.direction == SignalSide.LONG and not fvg.filled)
        bullish_score += sum(s.strength for s in sweeps if s.direction == SignalSide.LONG)

        bearish_score = sum(ob.strength for ob in order_blocks if ob.direction == SignalSide.SHORT and not ob.mitigated)
        bearish_score += sum(0.5 for fvg in fvgs if fvg.direction == SignalSide.SHORT and not fvg.filled)
        bearish_score += sum(s.strength for s in sweeps if s.direction == SignalSide.SHORT)

        if bullish_score > bearish_score * 1.2:
            smc_bias = SignalSide.LONG
        elif bearish_score > bullish_score * 1.2:
            smc_bias = SignalSide.SHORT
        else:
            smc_bias = SignalSide.FLAT

        return {
            "bias": smc_bias,
            "order_blocks": order_blocks,
            "fair_value_gaps": fvgs,
            "liquidity_sweeps": sweeps,
            "bullish_score": round(bullish_score, 3),
            "bearish_score": round(bearish_score, 3),
        }


# ---------------------------------------------------------------------------
# Support/Resistance detection
# ---------------------------------------------------------------------------

@dataclass
class SRLevel:
    """A support or resistance level."""
    price: float
    strength: float      # 0.0–1.0
    touches: int
    level_type: str      # "support" | "resistance"
    last_test_index: int = -1


class SupportResistanceDetector:
    """Detect support and resistance levels using pivot points and clustering.

    Uses swing high/low detection with touch-count based strength scoring.
    """

    def __init__(
        self,
        pivot_lookback: int = 5,
        cluster_threshold_pct: float = 0.002,
        min_touches: int = 2,
    ) -> None:
        self._pivot_lookback = pivot_lookback
        self._cluster_threshold = cluster_threshold_pct
        self._min_touches = min_touches

    def detect(
        self,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        current_price: float | None = None,
    ) -> tuple[list[SRLevel], list[SRLevel]]:
        """Detect support and resistance levels.

        Returns (supports, resistance) lists sorted by price.
        """
        if current_price is None:
            current_price = float(closes[-1])

        # Find pivot points
        pivot_highs = self._find_pivot_highs(highs)
        pivot_lows = self._find_pivot_lows(lows)

        # Cluster nearby pivots into levels
        support_levels = self._cluster_levels(pivot_lows, closes, "support")
        resistance_levels = self._cluster_levels(pivot_highs, closes, "resistance")

        # Filter by minimum touches
        support_levels = [lvl for lvl in support_levels if lvl.touches >= self._min_touches]
        resistance_levels = [lvl for lvl in resistance_levels if lvl.touches >= self._min_touches]

        # Sort
        support_levels.sort(key=lambda x: x.price, reverse=True)  # closest to price first
        resistance_levels.sort(key=lambda x: x.price)

        return support_levels, resistance_levels

    def _find_pivot_highs(self, highs: np.ndarray) -> list[tuple[float, int]]:
        """Find swing highs (local maxima)."""
        pivots = []
        lb = self._pivot_lookback
        for i in range(lb, len(highs) - lb):
            if highs[i] == np.max(highs[i - lb : i + lb + 1]):
                pivots.append((float(highs[i]), i))
        return pivots

    def _find_pivot_lows(self, lows: np.ndarray) -> list[tuple[float, int]]:
        """Find swing lows (local minima)."""
        pivots = []
        lb = self._pivot_lookback
        for i in range(lb, len(lows) - lb):
            if lows[i] == np.min(lows[i - lb : i + lb + 1]):
                pivots.append((float(lows[i]), i))
        return pivots

    def _cluster_levels(
        self,
        pivots: list[tuple[float, int]],
        closes: np.ndarray,
        level_type: str,
    ) -> list[SRLevel]:
        """Cluster nearby pivot prices into single S/R levels."""
        if not pivots:
            return []

        # Sort by price
        pivots.sort(key=lambda x: x[0])
        clusters: list[list[tuple[float, int]]] = [[pivots[0]]]

        for price, idx in pivots[1:]:
            last_cluster = clusters[-1]
            cluster_avg = np.mean([p for p, _ in last_cluster])
            if abs(price - cluster_avg) / max(cluster_avg, 1e-10) < self._cluster_threshold:
                last_cluster.append((price, idx))
            else:
                clusters.append([(price, idx)])

        # Convert clusters to SRLevel objects
        levels = []
        for cluster in clusters:
            avg_price = np.mean([p for p, _ in cluster])
            touches = len(cluster)
            last_idx = max(idx for _, idx in cluster)

            # Strength: based on touches and recency
            recency = last_idx / max(len(closes) - 1, 1)
            strength = min(1.0, (touches / 5.0) * 0.6 + recency * 0.4)

            levels.append(SRLevel(
                price=round(float(avg_price), 6),
                strength=round(strength, 3),
                touches=touches,
                level_type=level_type,
                last_test_index=last_idx,
            ))

        return levels


# ---------------------------------------------------------------------------
# Confluence scoring engine
# ---------------------------------------------------------------------------

# Default confluence weights — matches strategy_params.yaml concept
DEFAULT_CONFLUENCE_WEIGHTS: dict[str, float] = {
    "trend_alignment": 0.15,
    "sr_proximity": 0.15,
    "smc_confluence": 0.15,
    "rsi_signal": 0.10,
    "macd_signal": 0.10,
    "bollinger_position": 0.08,
    "volume_confirmation": 0.07,
    "candlestick_pattern": 0.08,
    "session_quality": 0.06,
    "regime_fit": 0.06,
}


class ConfluenceScorer:
    """Compute confluence scores from multiple technical factors.

    Each factor produces a score from -1.0 (strongly bearish) to +1.0 (strongly bullish).
    The weighted sum determines direction and confidence.
    """

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        self._weights = weights or DEFAULT_CONFLUENCE_WEIGHTS
        total = sum(self._weights.values())
        if abs(total - 1.0) > 0.01:
            # Normalize weights to sum to 1.0
            self._weights = {k: v / total for k, v in self._weights.items()}

    def score(
        self,
        closes: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        volumes: np.ndarray | None = None,
        opens: np.ndarray | None = None,
        regime: str = "unknown",
        session_quality: float = 1.0,
    ) -> dict[str, Any]:
        """Compute confluence score from market data.

        Returns dict with:
            - score: float (0–100)
            - direction: SignalSide
            - component_scores: dict[str, float]
            - raw_score: float (-1 to +1)
        """
        if volumes is None:
            volumes = np.ones(len(closes))
        if opens is None:
            opens = closes.copy()

        component_scores: dict[str, float] = {}

        # 1. Trend alignment (EMA crossover)
        ema_fast = compute_ema(closes, 9)
        ema_slow = compute_ema(closes, 21)
        if not np.isnan(ema_fast[-1]) and not np.isnan(ema_slow[-1]):
            diff = (ema_fast[-1] - ema_slow[-1]) / max(ema_slow[-1], 1e-10)
            component_scores["trend_alignment"] = np.clip(diff * 100, -1, 1)
        else:
            component_scores["trend_alignment"] = 0.0

        # 2. S/R proximity
        sr = SupportResistanceDetector()
        supports, resistances = sr.detect(highs, lows, closes)
        current = float(closes[-1])
        sr_score = self._sr_proximity_score(current, supports, resistances)
        component_scores["sr_proximity"] = sr_score

        # 3. SMC confluence
        smc = SMCDetector()
        atr = compute_atr(highs, lows, closes)
        smc_result = smc.analyze(opens, highs, lows, closes, atr)
        smc_score = (smc_result["bullish_score"] - smc_result["bearish_score"])
        component_scores["smc_confluence"] = np.clip(smc_score, -1, 1)

        # 4. RSI signal
        rsi = compute_rsi(closes)
        rsi_val = rsi[-1] if not np.isnan(rsi[-1]) else 50.0
        if rsi_val < 30:
            rsi_score = (30 - rsi_val) / 30  # bullish (oversold)
        elif rsi_val > 70:
            rsi_score = -(rsi_val - 70) / 30  # bearish (overbought)
        else:
            rsi_score = (rsi_val - 50) / 50 * 0.3  # slight bias
        component_scores["rsi_signal"] = np.clip(rsi_score, -1, 1)

        # 5. MACD signal
        macd_line, signal_line, histogram = compute_macd(closes)
        if not np.isnan(histogram[-1]):
            # Normalize by price to make comparable across assets
            norm = max(abs(histogram[-1]) / max(current, 1e-10) * 1000, 0.01)
            macd_score = np.clip(histogram[-1] / (current * 0.001), -1, 1)
            component_scores["macd_signal"] = float(macd_score)
        else:
            component_scores["macd_signal"] = 0.0

        # 6. Bollinger Band position
        bb_upper, bb_middle, bb_lower = compute_bollinger_bands(closes)
        if not np.isnan(bb_upper[-1]) and not np.isnan(bb_lower[-1]):
            bb_width = bb_upper[-1] - bb_lower[-1]
            if bb_width > 0:
                bb_pos = (current - bb_lower[-1]) / bb_width  # 0=lower, 1=upper
                # Mean reversion: near lower = bullish, near upper = bearish
                bb_score = -(bb_pos - 0.5) * 2  # invert for mean reversion
                component_scores["bollinger_position"] = np.clip(bb_score, -1, 1)
            else:
                component_scores["bollinger_position"] = 0.0
        else:
            component_scores["bollinger_position"] = 0.0

        # 7. Volume confirmation
        if len(volumes) > 20:
            vol_sma = np.mean(volumes[-20:])
            vol_ratio = volumes[-1] / max(vol_sma, 1.0)
            # High volume confirms direction
            price_direction = 1.0 if closes[-1] > closes[-2] else -1.0
            vol_score = min(vol_ratio, 3.0) / 3.0 * price_direction
            component_scores["volume_confirmation"] = np.clip(vol_score, -1, 1)
        else:
            component_scores["volume_confirmation"] = 0.0

        # 8. Candlestick pattern (simplified — full patterns in pipeline step)
        candle_score = self._simple_candle_score(opens, highs, lows, closes)
        component_scores["candlestick_pattern"] = candle_score

        # 9. Session quality
        component_scores["session_quality"] = np.clip(session_quality * 2 - 1, -1, 1)

        # 10. Regime fit
        regime_score = self._regime_fit_score(regime, rsi_val, atr)
        component_scores["regime_fit"] = regime_score

        # Weighted sum
        raw_score = 0.0
        for factor, score_val in component_scores.items():
            weight = self._weights.get(factor, 0.0)
            raw_score += score_val * weight

        # Convert to 0-100 scale
        direction = SignalSide.LONG if raw_score > 0.05 else (SignalSide.SHORT if raw_score < -0.05 else SignalSide.FLAT)
        score_100 = round((abs(raw_score) * 100), 1)

        return {
            "score": min(score_100, 100.0),
            "direction": direction,
            "component_scores": {k: round(v, 4) for k, v in component_scores.items()},
            "raw_score": round(raw_score, 4),
        }

    @staticmethod
    def _sr_proximity_score(
        current: float,
        supports: list[SRLevel],
        resistances: list[SRLevel],
    ) -> float:
        """Score based on proximity to S/R levels.

        Near support (in uptrend) = bullish, near resistance = bearish.
        """
        if not supports and not resistances:
            return 0.0

        # Find nearest levels
        nearest_support_dist = float('inf')
        nearest_resistance_dist = float('inf')
        nearest_support_strength = 0.0
        nearest_resistance_strength = 0.0

        for s in supports:
            dist = abs(current - s.price) / max(current, 1e-10)
            if dist < nearest_support_dist:
                nearest_support_dist = dist
                nearest_support_strength = s.strength

        for r in resistances:
            dist = abs(current - r.price) / max(current, 1e-10)
            if dist < nearest_resistance_dist:
                nearest_resistance_dist = dist
                nearest_resistance_strength = r.strength

        # Closer to support = more bullish, closer to resistance = more bearish
        support_factor = max(0, 1 - nearest_support_dist * 50) * nearest_support_strength
        resistance_factor = max(0, 1 - nearest_resistance_dist * 50) * nearest_resistance_strength

        return np.clip(support_factor - resistance_factor, -1, 1)

    @staticmethod
    def _simple_candle_score(
        opens: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
    ) -> float:
        """Simple candlestick scoring from last few candles."""
        if len(closes) < 3:
            return 0.0

        score = 0.0
        # Last candle body vs range
        body = closes[-1] - opens[-1]
        wick_range = highs[-1] - lows[-1]
        if wick_range > 0:
            body_ratio = abs(body) / wick_range
            if body > 0:
                score += body_ratio * 0.5
            else:
                score -= body_ratio * 0.5

        # Engulfing pattern
        if len(closes) >= 2:
            prev_body = closes[-2] - opens[-2]
            if body > 0 and prev_body < 0 and abs(body) > abs(prev_body):
                score += 0.5  # bullish engulfing
            elif body < 0 and prev_body > 0 and abs(body) > abs(prev_body):
                score -= 0.5  # bearish engulfing

        return np.clip(score, -1, 1)

    @staticmethod
    def _regime_fit_score(regime: str, rsi: float, atr: np.ndarray) -> float:
        """Score how well current conditions fit the detected regime."""
        if regime == "trending":
            # Trending regime: ADX would be high, RSI trending
            if rsi > 55 or rsi < 45:
                return 0.5  # confirms trend
            return -0.2  # no clear trend
        elif regime == "ranging":
            # Range regime: RSI near 50, low ADX
            if 40 < rsi < 60:
                return 0.5  # confirms range
            return -0.2
        elif regime == "volatile":
            # High ATR regime
            if len(atr) > 1 and not np.isnan(atr[-1]):
                return 0.3
        return 0.0


# ---------------------------------------------------------------------------
# Signal confidence scoring
# ---------------------------------------------------------------------------

class ConfidenceScorer:
    """Score signal confidence based on multiple quality factors.

    Confidence is distinct from confluence — it measures how *reliable*
    the signal is, not how many factors agree.
    """

    def __init__(self) -> None:
        pass

    def score(
        self,
        confluence_score: float,
        component_scores: dict[str, float],
        regime: str = "unknown",
        session_quality: float = 1.0,
        data_quality: float = 1.0,
        indicator_agreement: float | None = None,
    ) -> float:
        """Compute signal confidence (0.0–1.0).

        Factors:
        - Confluence strength (higher score → higher confidence)
        - Component agreement (do components agree on direction?)
        - Regime clarity
        - Session quality
        - Data quality (completeness of market data)
        """
        factors: list[float] = []

        # 1. Confluence strength
        conf_factor = min(confluence_score / 80.0, 1.0)
        factors.append(conf_factor)

        # 2. Component agreement — how many components point the same way
        if component_scores:
            positive = sum(1 for v in component_scores.values() if v > 0.1)
            negative = sum(1 for v in component_scores.values() if v < -0.1)
            total = len(component_scores)
            agreement = max(positive, negative) / max(total, 1)
            factors.append(agreement)
        else:
            factors.append(0.5)

        # 3. Regime clarity
        regime_factor = {
            "trending": 0.8,
            "ranging": 0.6,
            "volatile": 0.4,
            "unknown": 0.3,
        }.get(regime, 0.3)
        factors.append(regime_factor)

        # 4. Session quality
        factors.append(session_quality)

        # 5. Data quality
        factors.append(data_quality)

        # 6. Indicator agreement (if provided)
        if indicator_agreement is not None:
            factors.append(indicator_agreement)

        # Weighted geometric mean (emphasizes low factors)
        if not factors:
            return 0.0

        # Use harmonic mean to penalize low factors
        n = len(factors)
        harmonic = n / sum(1.0 / max(f, 0.01) for f in factors)
        return round(min(harmonic, 1.0), 4)


# ---------------------------------------------------------------------------
# High-level signal generator
# ---------------------------------------------------------------------------

class SignalGenerator:
    """High-level signal generation combining all analysis components.

    Usage::

        gen = SignalGenerator()
        signal = gen.generate(
            symbol="EUR/USD",
            opens=opens, highs=highs, lows=lows, closes=closes,
            volumes=volumes, timeframe="1h",
        )
    """

    def __init__(
        self,
        confluence_weights: dict[str, float] | None = None,
    ) -> None:
        self._confluence = ConfluenceScorer(confluence_weights)
        self._confidence = ConfidenceScorer()
        self._smc = SMCDetector()
        self._sr = SupportResistanceDetector()

    def generate(
        self,
        symbol: str,
        opens: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        volumes: np.ndarray | None = None,
        timeframe: str = "1h",
        regime: str = "unknown",
        session_quality: float = 1.0,
    ) -> Signal:
        """Generate a trade signal from OHLCV data.

        Returns a Signal with confluence score, confidence, and levels.
        """
        if volumes is None:
            volumes = np.ones(len(closes))

        # Run confluence scoring
        result = self._confluence.score(
            closes=closes,
            highs=highs,
            lows=lows,
            volumes=volumes,
            opens=opens,
            regime=regime,
            session_quality=session_quality,
        )

        # Compute confidence
        confidence = self._confidence.score(
            confluence_score=result["score"],
            component_scores=result["component_scores"],
            regime=regime,
            session_quality=session_quality,
        )

        # Compute indicators for signal context
        rsi = compute_rsi(closes)
        macd_line, signal_line, histogram = compute_macd(closes)
        bb_upper, bb_middle, bb_lower = compute_bollinger_bands(closes)
        atr = compute_atr(highs, lows, closes)
        adx = compute_adx(highs, lows, closes)

        current_price = float(closes[-1])
        atr_val = float(atr[-1]) if not np.isnan(atr[-1]) else current_price * 0.01

        # Compute entry/SL/TP
        side = result["direction"]
        entry = current_price
        sl_distance = atr_val * 1.5

        if side == SignalSide.LONG:
            stop_loss = entry - sl_distance
            tp1 = entry + sl_distance * 1.5
            tp2 = entry + sl_distance * 2.5
            tp3 = entry + sl_distance * 4.0
        elif side == SignalSide.SHORT:
            stop_loss = entry + sl_distance
            tp1 = entry - sl_distance * 1.5
            tp2 = entry - sl_distance * 2.5
            tp3 = entry - sl_distance * 4.0
        else:
            stop_loss = None
            tp1 = tp2 = tp3 = None

        # Strength = normalized confluence * confidence
        strength = min(1.0, result["score"] / 80.0) * confidence

        # Build indicator dict
        indicators = {
            "rsi": round(float(rsi[-1]), 2) if not np.isnan(rsi[-1]) else 50.0,
            "macd": round(float(histogram[-1]), 6) if not np.isnan(histogram[-1]) else 0.0,
            "bb_upper": round(float(bb_upper[-1]), 6) if not np.isnan(bb_upper[-1]) else 0.0,
            "bb_lower": round(float(bb_lower[-1]), 6) if not np.isnan(bb_lower[-1]) else 0.0,
            "atr": round(atr_val, 6),
            "adx": round(float(adx[-1]), 2) if not np.isnan(adx[-1]) else 0.0,
        }

        # SMC context
        smc_result = self._smc.analyze(opens, highs, lows, closes, atr)
        smc_context = {
            "bias": smc_result["bias"].value,
            "bullish_score": smc_result["bullish_score"],
            "bearish_score": smc_result["bearish_score"],
            "active_obs": len([ob for ob in smc_result["order_blocks"] if not ob.mitigated]),
            "active_fvgs": len([fvg for fvg in smc_result["fair_value_gaps"] if not fvg.filled]),
        }

        # Build reasoning
        reasoning = self._build_reasoning(side, result, indicators, smc_result, regime)

        return Signal(
            symbol=symbol,
            side=side,
            strength=round(strength, 4),
            confluence_score=result["score"],
            confidence=confidence,
            entry_price=round(entry, 6),
            stop_loss=round(stop_loss, 6) if stop_loss is not None else None,
            take_profit=[
                round(tp, 6) for tp in [tp1, tp2, tp3] if tp is not None
            ],
            reasoning=reasoning,
            timeframe=timeframe,
            indicators=indicators,
            smc_context=smc_context,
            regime=regime,
        )

    @staticmethod
    def _build_reasoning(
        side: SignalSide,
        confluence: dict[str, Any],
        indicators: dict[str, float],
        smc: dict[str, Any],
        regime: str,
    ) -> str:
        """Build human-readable reasoning for the signal."""
        if side == SignalSide.FLAT:
            return "No clear directional bias — confluence below threshold."

        parts = [f"{'Bullish' if side == SignalSide.LONG else 'Bearish'} signal"]
        parts.append(f"confluence={confluence['score']:.1f}/100")

        # Top contributing factors
        sorted_components = sorted(
            confluence["component_scores"].items(),
            key=lambda x: abs(x[1]),
            reverse=True,
        )
        top_3 = sorted_components[:3]
        parts.append("factors: " + ", ".join(
            f"{k}={v:+.2f}" for k, v in top_3
        ))

        parts.append(f"RSI={indicators['rsi']:.1f}")
        parts.append(f"ADX={indicators['adx']:.1f}")
        parts.append(f"regime={regime}")

        if smc["bias"] != SignalSide.FLAT:
            parts.append(f"SMC={smc['bias'].value}")

        return " | ".join(parts)
