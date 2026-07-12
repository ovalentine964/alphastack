"""Feature Engineering – technical indicators, normalization, feature store."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from alphastack.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Feature vector
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class FeatureVector:
    """A single feature row for a symbol at a point in time."""

    symbol: str
    timestamp: datetime
    features: dict[str, float]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_array(self, feature_names: list[str]) -> np.ndarray:
        """Return features as an ordered numpy array."""
        return np.array([self.features.get(f, 0.0) for f in feature_names], dtype=np.float64)


# ---------------------------------------------------------------------------
# Technical indicator calculator (TA-Lib wrapper)
# ---------------------------------------------------------------------------

class TechnicalIndicators:
    """Compute technical indicators on OHLCV DataFrames.

    Expects columns: time, open, high, low, close, volume.
    """

    @staticmethod
    def sma(series: pd.Series, period: int = 20) -> pd.Series:
        """Simple Moving Average."""
        return series.rolling(window=period, min_periods=1).mean()

    @staticmethod
    def ema(series: pd.Series, period: int = 20) -> pd.Series:
        """Exponential Moving Average."""
        return series.ewm(span=period, adjust=False).mean()

    @staticmethod
    def rsi(series: pd.Series, period: int = 14) -> pd.Series:
        """Relative Strength Index."""
        delta = series.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)
        avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
        avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))

    @staticmethod
    def macd(
        series: pd.Series,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        """MACD (line, signal, histogram)."""
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram

    @staticmethod
    def bollinger_bands(
        series: pd.Series,
        period: int = 20,
        std_dev: float = 2.0,
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        """Bollinger Bands (upper, middle, lower)."""
        middle = series.rolling(window=period, min_periods=1).mean()
        std = series.rolling(window=period, min_periods=1).std()
        upper = middle + std_dev * std
        lower = middle - std_dev * std
        return upper, middle, lower

    @staticmethod
    def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """Average True Range."""
        prev_close = close.shift(1)
        tr = pd.concat([
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ], axis=1).max(axis=1)
        return tr.ewm(alpha=1 / period, min_periods=period).mean()

    @staticmethod
    def stochastic(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        k_period: int = 14,
        d_period: int = 3,
    ) -> tuple[pd.Series, pd.Series]:
        """Stochastic Oscillator (%K, %D)."""
        lowest_low = low.rolling(window=k_period, min_periods=1).min()
        highest_high = high.rolling(window=k_period, min_periods=1).max()
        k = 100 * (close - lowest_low) / (highest_high - lowest_low).replace(0, np.nan)
        d = k.rolling(window=d_period, min_periods=1).mean()
        return k, d

    @staticmethod
    def vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
        """Volume-Weighted Average Price (cumulative)."""
        typical_price = (high + low + close) / 3
        cum_tp_vol = (typical_price * volume).cumsum()
        cum_vol = volume.cumsum()
        return cum_tp_vol / cum_vol.replace(0, np.nan)

    @staticmethod
    def adx(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int = 14,
    ) -> pd.Series:
        """Average Directional Index."""
        prev_high = high.shift(1)
        prev_low = low.shift(1)
        prev_close = close.shift(1)

        plus_dm = (high - prev_high).clip(lower=0)
        minus_dm = (prev_low - low).clip(lower=0)
        plus_dm[plus_dm < minus_dm] = 0
        minus_dm[minus_dm < plus_dm] = 0

        tr = pd.concat([
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ], axis=1).max(axis=1)

        atr = tr.ewm(alpha=1 / period, min_periods=period).mean()
        plus_di = 100 * plus_dm.ewm(alpha=1 / period, min_periods=period).mean() / atr
        minus_di = 100 * minus_dm.ewm(alpha=1 / period, min_periods=period).mean() / atr
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
        return dx.ewm(alpha=1 / period, min_periods=period).mean()


# ---------------------------------------------------------------------------
# Feature normaliser
# ---------------------------------------------------------------------------

class FeatureNormalizer:
    """Z-score or min-max normalization for feature vectors."""

    def __init__(self, method: str = "zscore") -> None:
        self.method = method
        self._means: dict[str, float] = {}
        self._stds: dict[str, float] = {}
        self._mins: dict[str, float] = {}
        self._maxs: dict[str, float] = {}

    def fit(self, df: pd.DataFrame, feature_cols: list[str]) -> None:
        """Learn normalization parameters from *df*."""
        for col in feature_cols:
            self._means[col] = float(df[col].mean())
            self._stds[col] = float(df[col].std() or 1.0)
            self._mins[col] = float(df[col].min())
            self._maxs[col] = float(df[col].max())

    def transform(self, value: float, feature_name: str) -> float:
        """Normalize a single value."""
        if self.method == "zscore":
            mean = self._means.get(feature_name, 0.0)
            std = self._stds.get(feature_name, 1.0)
            return (value - mean) / std if std else 0.0
        elif self.method == "minmax":
            mn = self._mins.get(feature_name, 0.0)
            mx = self._maxs.get(feature_name, 1.0)
            return (value - mn) / (mx - mn) if mx != mn else 0.0
        return value

    def fit_transform(self, df: pd.DataFrame, feature_cols: list[str]) -> pd.DataFrame:
        """Fit and transform in one step."""
        self.fit(df, feature_cols)
        result = df.copy()
        for col in feature_cols:
            result[col] = result[col].apply(lambda v: self.transform(v, col))
        return result


# ---------------------------------------------------------------------------
# Feature store interface
# ---------------------------------------------------------------------------

class FeatureStore:
    """In-memory feature store backed by Redis (when available) or dict."""

    def __init__(self) -> None:
        self._store: dict[str, FeatureVector] = {}

    def put(self, fv: FeatureVector) -> None:
        """Store a feature vector (key = symbol)."""
        self._store[fv.symbol] = fv

    def get(self, symbol: str) -> FeatureVector | None:
        return self._store.get(symbol)

    def get_all(self) -> dict[str, FeatureVector]:
        return dict(self._store)

    def clear(self) -> None:
        self._store.clear()


# ---------------------------------------------------------------------------
# Feature engineering pipeline
# ---------------------------------------------------------------------------

class FeatureEngineeringPipeline:
    """End-to-end: OHLCV DataFrame → feature vectors."""

    def __init__(
        self,
        indicators: TechnicalIndicators | None = None,
        normalizer: FeatureNormalizer | None = None,
        store: FeatureStore | None = None,
    ) -> None:
        self.indicators = indicators or TechnicalIndicators()
        self.normalizer = normalizer or FeatureNormalizer()
        self.store = store or FeatureStore()

    def compute(self, df: pd.DataFrame, symbol: str) -> FeatureVector:
        """Compute all features for the latest row of *df*.

        Args:
            df: OHLCV DataFrame with columns: time, open, high, low, close, volume.
            symbol: Asset symbol.

        Returns:
            FeatureVector for the most recent bar.
        """
        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]

        features: dict[str, float] = {}

        # Moving averages
        features["sma_20"] = float(self.indicators.sma(close, 20).iloc[-1])
        features["sma_50"] = float(self.indicators.sma(close, 50).iloc[-1])
        features["ema_12"] = float(self.indicators.ema(close, 12).iloc[-1])
        features["ema_26"] = float(self.indicators.ema(close, 26).iloc[-1])

        # RSI
        features["rsi_14"] = float(self.indicators.rsi(close, 14).iloc[-1])

        # MACD
        macd_line, signal_line, histogram = self.indicators.macd(close)
        features["macd"] = float(macd_line.iloc[-1])
        features["macd_signal"] = float(signal_line.iloc[-1])
        features["macd_hist"] = float(histogram.iloc[-1])

        # Bollinger Bands
        bb_upper, bb_mid, bb_lower = self.indicators.bollinger_bands(close)
        features["bb_upper"] = float(bb_upper.iloc[-1])
        features["bb_middle"] = float(bb_mid.iloc[-1])
        features["bb_lower"] = float(bb_lower.iloc[-1])
        features["bb_width"] = float((bb_upper.iloc[-1] - bb_lower.iloc[-1]) / bb_mid.iloc[-1]) if bb_mid.iloc[-1] else 0.0

        # ATR
        features["atr_14"] = float(self.indicators.atr(high, low, close, 14).iloc[-1])

        # Stochastic
        k, d = self.indicators.stochastic(high, low, close)
        features["stoch_k"] = float(k.iloc[-1])
        features["stoch_d"] = float(d.iloc[-1])

        # ADX
        features["adx_14"] = float(self.indicators.adx(high, low, close, 14).iloc[-1])

        # VWAP
        features["vwap"] = float(self.indicators.vwap(high, low, close, volume).iloc[-1])

        # Price-derived
        features["close"] = float(close.iloc[-1])
        features["volume"] = float(volume.iloc[-1])
        features["price_change_pct"] = float((close.iloc[-1] / close.iloc[-2] - 1) * 100) if len(close) > 1 else 0.0

        fv = FeatureVector(
            symbol=symbol,
            timestamp=df["time"].iloc[-1] if "time" in df.columns else datetime.utcnow(),
            features=features,
        )
        self.store.put(fv)
        return fv
