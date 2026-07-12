"""Python ↔ Rust bridge for AlphaStack.

Imports the native PyO3 module `alphastack_rust_core` and re-exports every
class/function with pure-Python fallbacks so the rest of the codebase can
always ``from alphastack.core.rust_bridge import ...`` regardless of whether
the Rust extension is available.

Usage::

    from alphastack.core.rust_bridge import (
        TickProcessor, Indicators, SignalEngine,
        OrderBookAnalyzer, RiskCalculator, BacktestEngine,
        RUST_AVAILABLE,
    )
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Try importing the Rust extension
# ---------------------------------------------------------------------------

RUST_AVAILABLE: bool = False

try:
    import alphastack_rust_core as _rust  # type: ignore[import-untyped]

    # Re-export Rust classes
    Tick = _rust.PyTick
    Candle = _rust.PyCandle
    TickProcessor = _rust.PyTickProcessor
    Indicators = _rust.PyIndicators
    SignalEngine = _rust.PySignalEngine
    OrderBookSnapshot = _rust.OrderBookSnapshot
    OrderBookAnalyzer = _rust.PyOrderBookAnalyzer
    RiskCalculator = _rust.PyRiskCalculator
    BacktestEngine = _rust.PyBacktestEngine
    BacktestResult = _rust.PyBacktestResult
    StructurePoint = _rust.StructurePoint
    Level = _rust.Level
    MacdResult = _rust.MacdResult
    BollingerResult = _rust.BollingerResult
    AdxResult = _rust.AdxResult

    RUST_AVAILABLE = True
    logger.info("✅ Rust core loaded — high-performance path active")

except ImportError:
    logger.warning(
        "⚠️  Rust core not available — falling back to Python implementations. "
        "Run `maturin develop --release` in src/rust_core/ to build the native module."
    )

    # -----------------------------------------------------------------------
    # Pure-Python fallback implementations
    # -----------------------------------------------------------------------

    class Tick:  # type: ignore[no-redef]
        """Fallback Tick."""
        __slots__ = ("timestamp_ms", "price", "volume", "side")

        def __init__(self, timestamp_ms: int, price: float, volume: float, side: str):
            self.timestamp_ms = timestamp_ms
            self.price = price
            self.volume = volume
            self.side = side

        def __repr__(self) -> str:
            return f"Tick(ts={self.timestamp_ms}, price={self.price}, vol={self.volume}, side={self.side})"

    class Candle:  # type: ignore[no-redef]
        """Fallback Candle."""
        __slots__ = ("timestamp_ms", "open", "high", "low", "close", "volume",
                      "buy_volume", "sell_volume", "tick_count")

        def __init__(self, timestamp_ms: int, open_: float, high: float,
                     low: float, close: float, volume: float,
                     buy_volume: float = 0.0, sell_volume: float = 0.0,
                     tick_count: int = 0):
            self.timestamp_ms = timestamp_ms
            self.open = open_
            self.high = high
            self.low = low
            self.close = close
            self.volume = volume
            self.buy_volume = buy_volume
            self.sell_volume = sell_volume
            self.tick_count = tick_count

        def __repr__(self) -> str:
            return (f"Candle(ts={self.timestamp_ms}, O={self.open}, H={self.high}, "
                    f"L={self.low}, C={self.close}, V={self.volume})")

    class TickProcessor:  # type: ignore[no-redef]
        """Fallback TickProcessor — minimal Python implementation."""

        def __init__(self, interval_ms: int = 60_000, bucket_size: float = 0.01):
            self.interval_ms = interval_ms
            self.bucket_size = bucket_size
            self._ticks: list[Tick] = []
            self._candles: list[Candle] = []
            self._current: Optional[Candle] = None
            self._vol_profile: dict[int, float] = {}

        def ingest_tick(self, tick: Tick) -> Optional[Candle]:
            candle_start = (tick.timestamp_ms // self.interval_ms) * self.interval_ms
            completed = None
            if self._current and self._current.timestamp_ms == candle_start:
                self._current.high = max(self._current.high, tick.price)
                self._current.low = min(self._current.low, tick.price)
                self._current.close = tick.price
                self._current.volume += tick.volume
                self._current.tick_count += 1
                if tick.side == "buy":
                    self._current.buy_volume += tick.volume
                else:
                    self._current.sell_volume += tick.volume
            else:
                if self._current:
                    self._candles.append(self._current)
                    completed = self._current
                self._current = Candle(
                    candle_start, tick.price, tick.price, tick.price,
                    tick.price, tick.volume,
                    tick.volume if tick.side == "buy" else 0.0,
                    tick.volume if tick.side == "sell" else 0.0,
                    1,
                )
            bucket = round(tick.price / self.bucket_size)
            self._vol_profile[bucket] = self._vol_profile.get(bucket, 0.0) + tick.volume
            self._ticks.append(tick)
            return completed

        def flush(self) -> Optional[Candle]:
            if self._current:
                c = self._current
                self._candles.append(c)
                self._current = None
                return c
            return None

        def get_candles(self) -> list[Candle]:
            return list(self._candles)

        def get_volume_profile(self) -> list[tuple[float, float]]:
            return [(b * self.bucket_size, v) for b, v in self._vol_profile.items()]

        def poc(self) -> Optional[float]:
            if not self._vol_profile:
                return None
            bucket = max(self._vol_profile, key=self._vol_profile.get)  # type: ignore[arg-type]
            return bucket * self.bucket_size

        def tick_count(self) -> int:
            return len(self._ticks)

        def reset(self) -> None:
            self._ticks.clear()
            self._candles.clear()
            self._current = None
            self._vol_profile.clear()

    class Indicators:  # type: ignore[no-redef]
        """Fallback Indicators — pure-Python with numpy if available."""

        def __init__(self) -> None:
            pass

        @staticmethod
        def rsi(closes: list[float], period: int = 14) -> list[float]:
            if len(closes) < period + 1:
                return [50.0] * len(closes)
            result = [50.0] * len(closes)
            gains = losses = 0.0
            for i in range(1, period + 1):
                d = closes[i] - closes[i - 1]
                if d >= 0:
                    gains += d
                else:
                    losses -= d
            ag = gains / period
            al = losses / period
            result[period] = 100.0 - 100.0 / (1.0 + ag / al) if al else 100.0
            for i in range(period + 1, len(closes)):
                d = closes[i] - closes[i - 1]
                g, l = (d, 0.0) if d >= 0 else (0.0, -d)
                ag = (ag * (period - 1) + g) / period
                al = (al * (period - 1) + l) / period
                result[i] = 100.0 - 100.0 / (1.0 + ag / al) if al else 100.0
            return result

        @staticmethod
        def vwap(prices: list[float], volumes: list[float]) -> list[float]:
            cum_pv = cum_v = 0.0
            result = []
            for p, v in zip(prices, volumes):
                cum_pv += p * v
                cum_v += v
                result.append(cum_pv / cum_v if cum_v else p)
            return result

    class SignalEngine:  # type: ignore[no-redef]
        """Fallback SignalEngine."""

        def __init__(self) -> None:
            pass

        @staticmethod
        def confluence_score(signals: list[float],
                             weights: Optional[list[float]] = None) -> float:
            w = weights or [1.0] * len(signals)
            tw = sum(w)
            if tw == 0:
                return 0.0
            return max(0.0, min(1.0, sum(s * wi for s, wi in zip(signals, w)) / tw))

    class OrderBookSnapshot:  # type: ignore[no-redef]
        pass

    class OrderBookAnalyzer:  # type: ignore[no-redef]
        def __init__(self, max_history: int = 1000) -> None:
            self._history: list = []
            self.max_history = max_history
        def push(self, snap: Any) -> None:
            if len(self._history) >= self.max_history:
                self._history.pop(0)
            self._history.append(snap)
        def snapshot_count(self) -> int:
            return len(self._history)
        def clear(self) -> None:
            self._history.clear()

    class RiskCalculator:  # type: ignore[no-redef]
        """Fallback RiskCalculator."""
        def __init__(self) -> None: pass

        @staticmethod
        def kelly_fraction(win_rate: float, win_loss_ratio: float) -> float:
            if win_loss_ratio == 0:
                return 0.0
            return max(0.0, min(1.0, win_rate - (1.0 - win_rate) / win_loss_ratio))

        @staticmethod
        def position_size(capital: float, risk_pct: float,
                          entry: float, stop_loss: float) -> float:
            risk = capital * risk_pct
            per_unit = abs(entry - stop_loss)
            return risk / per_unit if per_unit else 0.0

        @staticmethod
        def sharpe_ratio(returns: list[float], risk_free_rate: float = 0.0) -> float:
            import math
            n = len(returns)
            if n == 0:
                return 0.0
            mean = sum(returns) / n
            var = sum((r - mean) ** 2 for r in returns) / n
            std = math.sqrt(var)
            return (mean - risk_free_rate) / std if std else 0.0

    class BacktestEngine:  # type: ignore[no-redef]
        """Fallback BacktestEngine — delegates to Python only."""
        def __init__(self, initial_capital: float = 10_000.0,
                     fee_rate: float = 0.001, slippage_pct: float = 0.0005):
            self.initial_capital = initial_capital
            self.fee_rate = fee_rate
            self.slippage_pct = slippage_pct

    class BacktestResult:  # type: ignore[no-redef]
        pass

    class StructurePoint:  # type: ignore[no-redef]
        pass

    class Level:  # type: ignore[no-redef]
        pass

    class MacdResult:  # type: ignore[no-redef]
        pass

    class BollingerResult:  # type: ignore[no-redef]
        pass

    class AdxResult:  # type: ignore[no-redef]
        pass


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def check_rust() -> dict[str, Any]:
    """Return a status dict about the Rust layer."""
    return {
        "available": RUST_AVAILABLE,
        "backend": "rust" if RUST_AVAILABLE else "python_fallback",
        "modules": [
            "tick_processor", "indicators", "signal_compute",
            "order_book", "risk_calculator", "backtest_engine",
        ],
    }
