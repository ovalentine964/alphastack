"""Market regime detection — classify market state and adapt strategy.

Classifies markets into regimes:
  - TRENDING: clear directional movement (ADX > 25, aligned EMAs)
  - RANGING: sideways consolidation (ADX < 20, Bollinger squeeze)
  - VOLATILE: high-ATR, erratic movement (ATR spike, wide bands)
  - BREAKOUT: transitioning from range to trend (volume + range expansion)

Provides regime-adaptive strategy selection for pipeline steps.
Uses Hidden Markov Model (HMM) inspired approach with observable features.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np

from alphastack.ai.signals import (
    compute_adx,
    compute_atr,
    compute_bollinger_bands,
    compute_ema,
    compute_rsi,
)
from alphastack.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Regime types
# ---------------------------------------------------------------------------

class MarketRegime(str, Enum):
    """Market regime classification."""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"
    BREAKOUT_UP = "breakout_up"
    BREAKOUT_DOWN = "breakout_down"
    UNKNOWN = "unknown"


class TrendStrength(str, Enum):
    """Strength of the current trend."""
    STRONG = "strong"      # ADX > 35
    MODERATE = "moderate"  # ADX 25-35
    WEAK = "weak"          # ADX 20-25
    NONE = "none"          # ADX < 20


@dataclass
class RegimeState:
    """Complete regime analysis result."""
    regime: MarketRegime
    confidence: float              # 0.0–1.0
    trend_strength: TrendStrength
    adx_value: float
    atr_ratio: float               # current ATR / historical ATR
    volatility_percentile: float   # 0.0–1.0 (where current vol sits in history)
    bollinger_width_pct: float     # Bollinger width as % of price
    ema_alignment: float           # -1 (fully bearish) to +1 (fully bullish)
    regime_duration_bars: int      # estimated bars in current regime
    features: dict[str, float] = field(default_factory=dict)

    @property
    def is_trending(self) -> bool:
        return self.regime in (MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN)

    @property
    def is_directional(self) -> bool:
        return self.regime in (
            MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN,
            MarketRegime.BREAKOUT_UP, MarketRegime.BREAKOUT_DOWN,
        )

    @property
    def direction(self) -> str:
        if self.regime in (MarketRegime.TRENDING_UP, MarketRegime.BREAKOUT_UP):
            return "long"
        if self.regime in (MarketRegime.TRENDING_DOWN, MarketRegime.BREAKOUT_DOWN):
            return "short"
        return "flat"


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------

class RegimeFeatureExtractor:
    """Extract observable features for regime classification.

    Features are normalized to [0, 1] range for consistent scoring.
    """

    def extract(
        self,
        opens: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        volumes: np.ndarray | None = None,
    ) -> dict[str, float]:
        """Extract regime features from OHLCV data.

        Returns dict of feature_name → value (mostly 0–1 range).
        """
        if volumes is None:
            volumes = np.ones(len(closes))

        features: dict[str, float] = {}

        # ADX (trend strength)
        adx = compute_adx(highs, lows, closes)
        adx_val = float(adx[-1]) if not np.isnan(adx[-1]) else 0.0
        features["adx"] = min(adx_val / 60.0, 1.0)  # normalize: 0-60 → 0-1
        features["adx_raw"] = adx_val

        # ATR ratio (current vs historical)
        atr = compute_atr(highs, lows, closes)
        if len(atr) > 20:
            atr_vals = atr[~np.isnan(atr)]
            if len(atr_vals) > 0:
                current_atr = float(atr_vals[-1])
                hist_atr = float(np.mean(atr_vals[-50:])) if len(atr_vals) >= 50 else float(np.mean(atr_vals))
                features["atr_ratio"] = min(current_atr / max(hist_atr, 1e-10), 3.0) / 3.0
                features["atr_raw"] = current_atr

                # Volatility percentile
                features["volatility_percentile"] = float(
                    np.sum(atr_vals <= current_atr) / len(atr_vals)
                )
            else:
                features["atr_ratio"] = 0.5
                features["atr_raw"] = 0.0
                features["volatility_percentile"] = 0.5
        else:
            features["atr_ratio"] = 0.5
            features["atr_raw"] = 0.0
            features["volatility_percentile"] = 0.5

        # Bollinger Band width (squeeze detection)
        bb_upper, bb_middle, bb_lower = compute_bollinger_bands(closes)
        if not np.isnan(bb_upper[-1]) and not np.isnan(bb_lower[-1]):
            bb_width = bb_upper[-1] - bb_lower[-1]
            current_price = float(closes[-1])
            features["bb_width_pct"] = bb_width / max(current_price, 1e-10) * 100

            # Historical BB width percentile
            bb_widths = []
            for i in range(len(closes)):
                if not np.isnan(bb_upper[i]) and not np.isnan(bb_lower[i]):
                    bb_widths.append(bb_upper[i] - bb_lower[i])
            if bb_widths:
                features["bb_width_percentile"] = float(
                    np.sum(np.array(bb_widths) <= bb_width) / len(bb_widths)
                )
            else:
                features["bb_width_percentile"] = 0.5
        else:
            features["bb_width_pct"] = 0.0
            features["bb_width_percentile"] = 0.5

        # EMA alignment (trend direction)
        ema_9 = compute_ema(closes, 9)
        ema_21 = compute_ema(closes, 21)
        ema_50 = compute_ema(closes, 50)
        if not any(np.isnan([ema_9[-1], ema_21[-1], ema_50[-1]])):
            alignment = 0.0
            if ema_9[-1] > ema_21[-1]:
                alignment += 0.33
            if ema_21[-1] > ema_50[-1]:
                alignment += 0.33
            if ema_9[-1] > ema_50[-1]:
                alignment += 0.34
            if ema_9[-1] < ema_21[-1]:
                alignment -= 0.33
            if ema_21[-1] < ema_50[-1]:
                alignment -= 0.33
            if ema_9[-1] < ema_50[-1]:
                alignment -= 0.34
            features["ema_alignment"] = alignment  # -1 to +1
        else:
            features["ema_alignment"] = 0.0

        # RSI position
        rsi = compute_rsi(closes)
        rsi_val = float(rsi[-1]) if not np.isnan(rsi[-1]) else 50.0
        features["rsi"] = rsi_val / 100.0  # normalize to 0-1
        features["rsi_raw"] = rsi_val

        # Volume trend (increasing/decreasing)
        if len(volumes) > 20:
            recent_vol = float(np.mean(volumes[-5:]))
            hist_vol = float(np.mean(volumes[-20:]))
            features["volume_ratio"] = min(recent_vol / max(hist_vol, 1.0), 3.0) / 3.0
        else:
            features["volume_ratio"] = 0.5

        # Price momentum (rate of change)
        if len(closes) > 10:
            roc = (closes[-1] - closes[-10]) / max(closes[-10], 1e-10)
            features["momentum_roc"] = float(np.clip(roc * 10, -1, 1))
        else:
            features["momentum_roc"] = 0.0

        # Range contraction/expansion
        if len(highs) > 20:
            recent_range = float(np.mean(highs[-5:] - lows[-5:]))
            hist_range = float(np.mean(highs[-20:] - lows[-20:]))
            features["range_expansion"] = min(recent_range / max(hist_range, 1e-10), 3.0) / 3.0
        else:
            features["range_expansion"] = 0.5

        return features


# ---------------------------------------------------------------------------
# Regime classifier
# ---------------------------------------------------------------------------

class RegimeClassifier:
    """Classify market regime from extracted features.

    Uses a rule-based scoring system inspired by HMM state classification.
    Each regime hypothesis is scored against the features; highest score wins.
    """

    # Feature weights for each regime hypothesis
    _REGIME_WEIGHTS: dict[str, dict[str, float]] = {
        "trending_up": {
            "adx": 0.30,
            "ema_alignment": 0.25,
            "momentum_roc": 0.15,
            "volume_ratio": 0.10,
            "range_expansion": 0.10,
            "atr_ratio": 0.10,
        },
        "trending_down": {
            "adx": 0.30,
            "ema_alignment": -0.25,  # negative weight — bearish alignment
            "momentum_roc": -0.15,
            "volume_ratio": 0.10,
            "range_expansion": 0.10,
            "atr_ratio": 0.10,
        },
        "ranging": {
            "adx": -0.30,  # low ADX = ranging
            "bb_width_percentile": -0.20,  # narrow bands
            "ema_alignment": -0.15,  # no alignment
            "atr_ratio": -0.15,  # low volatility
            "range_expansion": -0.10,
            "volume_ratio": -0.10,
        },
        "volatile": {
            "atr_ratio": 0.30,
            "bb_width_percentile": 0.25,
            "range_expansion": 0.20,
            "volume_ratio": 0.15,
            "adx": 0.10,
        },
        "breakout_up": {
            "range_expansion": 0.25,
            "volume_ratio": 0.25,
            "ema_alignment": 0.20,
            "momentum_roc": 0.15,
            "atr_ratio": 0.15,
        },
        "breakout_down": {
            "range_expansion": 0.25,
            "volume_ratio": 0.25,
            "ema_alignment": -0.20,
            "momentum_roc": -0.15,
            "atr_ratio": 0.15,
        },
    }

    def classify(self, features: dict[str, float]) -> tuple[MarketRegime, float]:
        """Classify regime from features.

        Returns (regime, confidence).
        """
        scores: dict[str, float] = {}

        for regime_name, weights in self._REGIME_WEIGHTS.items():
            score = 0.0
            for feature_name, weight in weights.items():
                feature_val = features.get(feature_name, 0.5)
                if weight > 0:
                    score += feature_val * weight
                else:
                    score += (1.0 - feature_val) * abs(weight)
            scores[regime_name] = score

        # Best regime
        best = max(scores, key=scores.get)  # type: ignore[arg-type]
        best_score = scores[best]

        # Normalize confidence
        total = sum(scores.values())
        confidence = best_score / max(total, 0.01)

        regime_map = {
            "trending_up": MarketRegime.TRENDING_UP,
            "trending_down": MarketRegime.TRENDING_DOWN,
            "ranging": MarketRegime.RANGING,
            "volatile": MarketRegime.VOLATILE,
            "breakout_up": MarketRegime.BREAKOUT_UP,
            "breakout_down": MarketRegime.BREAKOUT_DOWN,
        }

        return regime_map.get(best, MarketRegime.UNKNOWN), round(confidence, 3)


# ---------------------------------------------------------------------------
# Regime-adaptive strategy selector
# ---------------------------------------------------------------------------

@dataclass
class StrategyAdaptation:
    """Strategy parameter adjustments for the current regime."""
    regime: MarketRegime
    rsi_overbought: float
    rsi_oversold: float
    atr_multiplier_sl: float
    atr_multiplier_tp: float
    min_confluence: float
    position_size_factor: float  # 0.0–1.0 scaling
    preferred_timeframes: list[str]
    notes: str = ""


# Regime-specific parameter tables
_REGIME_ADAPTATIONS: dict[MarketRegime, StrategyAdaptation] = {
    MarketRegime.TRENDING_UP: StrategyAdaptation(
        regime=MarketRegime.TRENDING_UP,
        rsi_overbought=75,     # allow higher RSI in uptrend
        rsi_oversold=35,
        atr_multiplier_sl=1.5,
        atr_multiplier_tp=3.0,  # wider TP in trend
        min_confluence=35.0,    # lower threshold — trend is your friend
        position_size_factor=1.0,
        preferred_timeframes=["4h", "1h", "15m"],
        notes="Uptrend: favor long entries, wider TPs, trail stops",
    ),
    MarketRegime.TRENDING_DOWN: StrategyAdaptation(
        regime=MarketRegime.TRENDING_DOWN,
        rsi_overbought=65,
        rsi_oversold=25,       # allow lower RSI in downtrend
        atr_multiplier_sl=1.5,
        atr_multiplier_tp=3.0,
        min_confluence=35.0,
        position_size_factor=1.0,
        preferred_timeframes=["4h", "1h", "15m"],
        notes="Downtrend: favor short entries, wider TPs, trail stops",
    ),
    MarketRegime.RANGING: StrategyAdaptation(
        regime=MarketRegime.RANGING,
        rsi_overbought=65,     # tighter OB/OS in range
        rsi_oversold=35,
        atr_multiplier_sl=1.0,
        atr_multiplier_tp=1.5,  # tighter TP — take profits at range edges
        min_confluence=50.0,    # higher threshold — need more confirmation
        position_size_factor=0.7,  # smaller size in range
        preferred_timeframes=["1h", "15m", "5m"],
        notes="Range: fade extremes, tight TPs, reduce size",
    ),
    MarketRegime.VOLATILE: StrategyAdaptation(
        regime=MarketRegime.VOLATILE,
        rsi_overbought=80,     # extreme levels in vol
        rsi_oversold=20,
        atr_multiplier_sl=2.0,  # wider SL for volatility
        atr_multiplier_tp=2.0,
        min_confluence=60.0,    # high threshold — need strong signal
        position_size_factor=0.5,  # half size in volatile markets
        preferred_timeframes=["4h", "1h"],
        notes="Volatile: wider stops, half size, wait for clarity",
    ),
    MarketRegime.BREAKOUT_UP: StrategyAdaptation(
        regime=MarketRegime.BREAKOUT_UP,
        rsi_overbought=80,
        rsi_oversold=40,
        atr_multiplier_sl=1.5,
        atr_multiplier_tp=4.0,  # extended TP for breakout
        min_confluence=40.0,
        position_size_factor=0.8,
        preferred_timeframes=["1h", "15m"],
        notes="Breakout up: enter on pullback, extended targets, volume confirmation required",
    ),
    MarketRegime.BREAKOUT_DOWN: StrategyAdaptation(
        regime=MarketRegime.BREAKOUT_DOWN,
        rsi_overbought=60,
        rsi_oversold=20,
        atr_multiplier_sl=1.5,
        atr_multiplier_tp=4.0,
        min_confluence=40.0,
        position_size_factor=0.8,
        preferred_timeframes=["1h", "15m"],
        notes="Breakout down: enter on pullback, extended targets, volume confirmation required",
    ),
    MarketRegime.UNKNOWN: StrategyAdaptation(
        regime=MarketRegime.UNKNOWN,
        rsi_overbought=70,
        rsi_oversold=30,
        atr_multiplier_sl=1.5,
        atr_multiplier_tp=2.0,
        min_confluence=50.0,
        position_size_factor=0.6,
        preferred_timeframes=["1h"],
        notes="Unknown regime: conservative defaults, reduce exposure",
    ),
}


# ---------------------------------------------------------------------------
# Market Regime Detector (main interface)
# ---------------------------------------------------------------------------

class MarketRegimeDetector:
    """Detect market regime and provide strategy adaptations.

    Usage::

        detector = MarketRegimeDetector()
        state = detector.detect(opens, highs, lows, closes, volumes)
        adaptation = detector.get_adaptation(state.regime)
    """

    def __init__(self) -> None:
        self._feature_extractor = RegimeFeatureExtractor()
        self._classifier = RegimeClassifier()
        self._regime_history: list[tuple[float, MarketRegime]] = []
        self._max_history = 1000

    def detect(
        self,
        opens: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        volumes: np.ndarray | None = None,
    ) -> RegimeState:
        """Detect the current market regime.

        Returns a RegimeState with full analysis.
        """
        # Extract features
        features = self._feature_extractor.extract(opens, highs, lows, closes, volumes)

        # Classify regime
        regime, confidence = self._classifier.classify(features)

        # Determine trend strength
        adx_raw = features.get("adx_raw", 0.0)
        if adx_raw > 35:
            trend_strength = TrendStrength.STRONG
        elif adx_raw > 25:
            trend_strength = TrendStrength.MODERATE
        elif adx_raw > 20:
            trend_strength = TrendStrength.WEAK
        else:
            trend_strength = TrendStrength.NONE

        # Estimate regime duration
        duration = self._estimate_duration(regime)

        # Log and track
        self._regime_history.append((time.time(), regime))
        if len(self._regime_history) > self._max_history:
            self._regime_history = self._regime_history[-self._max_history:]

        logger.info(
            "regime.detected",
            regime=regime.value,
            confidence=confidence,
            trend_strength=trend_strength.value,
            adx=round(adx_raw, 1),
            atr_ratio=round(features.get("atr_ratio", 0.5), 3),
        )

        return RegimeState(
            regime=regime,
            confidence=confidence,
            trend_strength=trend_strength,
            adx_value=round(adx_raw, 2),
            atr_ratio=round(features.get("atr_ratio", 0.5), 3),
            volatility_percentile=round(features.get("volatility_percentile", 0.5), 3),
            bollinger_width_pct=round(features.get("bb_width_pct", 0.0), 4),
            ema_alignment=round(features.get("ema_alignment", 0.0), 3),
            regime_duration_bars=duration,
            features={k: round(v, 4) for k, v in features.items()},
        )

    def get_adaptation(self, regime: MarketRegime) -> StrategyAdaptation:
        """Get regime-adaptive strategy parameters."""
        return _REGIME_ADAPTATIONS.get(regime, _REGIME_ADAPTATIONS[MarketRegime.UNKNOWN])

    def get_adaptation_dict(self, regime: MarketRegime) -> dict[str, Any]:
        """Get adaptation as a plain dict (for serialization)."""
        adapt = self.get_adaptation(regime)
        return {
            "regime": adapt.regime.value,
            "rsi_overbought": adapt.rsi_overbought,
            "rsi_oversold": adapt.rsi_oversold,
            "atr_multiplier_sl": adapt.atr_multiplier_sl,
            "atr_multiplier_tp": adapt.atr_multiplier_tp,
            "min_confluence": adapt.min_confluence,
            "position_size_factor": adapt.position_size_factor,
            "preferred_timeframes": adapt.preferred_timeframes,
            "notes": adapt.notes,
        }

    def _estimate_duration(self, current: MarketRegime) -> int:
        """Estimate how many bars the current regime has been active."""
        if not self._regime_history:
            return 1

        count = 0
        for _, regime in reversed(self._regime_history):
            if regime == current:
                count += 1
            else:
                break
        return max(count, 1)

    @property
    def current_regime(self) -> MarketRegime | None:
        """Last detected regime."""
        if self._regime_history:
            return self._regime_history[-1][1]
        return None
