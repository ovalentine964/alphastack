"""Correlation Monitor — prevent correlated double-ups and cross-pair exposure.

Real-time correlation tracking between open positions to avoid
concentrated risk from highly correlated pairs (e.g., EUR/USD + GBP/USD).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from alphastack.utils.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Position tracking
# ---------------------------------------------------------------------------

class OpenPosition(BaseModel):
    """An open position tracked for correlation analysis."""
    symbol: str
    direction: str  # long | short
    size: float
    entry_price: float
    opened_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Correlation data
# ---------------------------------------------------------------------------

class CorrelationPair(BaseModel):
    """Correlation between two symbols."""
    symbol_a: str
    symbol_b: str
    correlation: float  # -1 to +1
    sample_size: int = 0
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Default correlation matrix (known forex correlations)
# ---------------------------------------------------------------------------

# These are approximate long-term correlations for common forex pairs.
# In production, these would be computed from real-time price data.
DEFAULT_CORRELATIONS: dict[tuple[str, str], float] = {
    # Strong positive correlations
    ("EUR/USD", "GBP/USD"): 0.85,
    ("EUR/USD", "AUD/USD"): 0.70,
    ("EUR/USD", "NZD/USD"): 0.65,
    ("GBP/USD", "AUD/USD"): 0.60,
    ("GBP/USD", "NZD/USD"): 0.55,
    ("AUD/USD", "NZD/USD"): 0.90,
    ("USD/CHF", "USD/JPY"): 0.40,
    # Strong negative correlations
    ("EUR/USD", "USD/CHF"): -0.90,
    ("EUR/USD", "USD/JPY"): -0.30,
    ("GBP/USD", "USD/CHF"): -0.70,
    ("AUD/USD", "USD/CHF"): -0.60,
    # Cross pairs
    ("EUR/GBP", "EUR/USD"): 0.40,
    ("EUR/GBP", "GBP/USD"): -0.50,
}


# ---------------------------------------------------------------------------
# Correlation Monitor
# ---------------------------------------------------------------------------

class CorrelationMonitor:
    """Monitors correlation between open positions to prevent concentrated risk.

    Prevents:
    - Taking the same trade through correlated pairs (e.g., EUR/USD + GBP/USD long)
    - Doubling exposure through inverse pairs
    """

    def __init__(
        self,
        max_correlation: float = 0.7,
        max_same_direction_exposure: int = 3,
        correlations: dict[tuple[str, str], float] | None = None,
    ) -> None:
        self._max_correlation = max_correlation
        self._max_same_dir_exposure = max_same_direction_exposure
        self._correlations = correlations or dict(DEFAULT_CORRELATIONS)
        self._positions: list[OpenPosition] = []
        self._correlation_cache: dict[str, CorrelationPair] = {}

    # -- Position management ------------------------------------------------

    def add_position(self, position: OpenPosition) -> None:
        """Register an open position."""
        self._positions.append(position)
        log.debug(
            "correlation_position_added",
            symbol=position.symbol,
            direction=position.direction,
            total_positions=len(self._positions),
        )

    def remove_position(self, symbol: str) -> None:
        """Remove a closed position."""
        self._positions = [p for p in self._positions if p.symbol != symbol]
        log.debug(
            "correlation_position_removed",
            symbol=symbol,
            total_positions=len(self._positions),
        )

    def clear(self) -> None:
        """Remove all tracked positions."""
        self._positions.clear()

    # -- Correlation checks -------------------------------------------------

    def check_correlation(
        self,
        symbol: str,
        direction: str,
    ) -> tuple[bool, str]:
        """Check if a new position violates correlation limits.

        Returns:
            (ok, reason) — ok=True if allowed, reason explains rejection or warning.
        """
        if not self._positions:
            return True, ""

        # Check against each open position
        for pos in self._positions:
            corr = self._get_correlation(symbol, pos.symbol)

            if corr is None:
                continue  # Unknown correlation — allow but could flag

            abs_corr = abs(corr)

            # Same direction, high positive correlation = double-up risk
            if direction == pos.direction and abs_corr >= self._max_correlation:
                return False, (
                    f"Correlated double-up: {symbol} {direction} correlates "
                    f"{corr:.2f} with {pos.symbol} {pos.direction}"
                )

            # Opposite direction, high negative correlation = hedged but locked
            if direction != pos.direction and corr <= -self._max_correlation:
                # This is actually a hedge — warn but allow
                pass  # Could add a warning

        # Check total same-direction exposure
        same_dir_count = sum(
            1 for p in self._positions if p.direction == direction
        )
        if same_dir_count >= self._max_same_dir_exposure:
            return False, (
                f"Too many {direction} positions: "
                f"{same_dir_count} >= {self._max_same_dir_exposure}"
            )

        return True, ""

    def get_portfolio_correlation(self) -> float:
        """Compute average absolute correlation across all open positions.

        Returns 0 if fewer than 2 positions.
        """
        if len(self._positions) < 2:
            return 0.0

        total_corr = 0.0
        pairs = 0
        for i, a in enumerate(self._positions):
            for b in self._positions[i + 1:]:
                corr = self._get_correlation(a.symbol, b.symbol)
                if corr is not None:
                    total_corr += abs(corr)
                    pairs += 1

        return total_corr / pairs if pairs > 0 else 0.0

    def get_exposure_by_direction(self) -> dict[str, int]:
        """Count positions by direction."""
        result: dict[str, int] = {}
        for pos in self._positions:
            result[pos.direction] = result.get(pos.direction, 0) + 1
        return result

    # -- Correlation lookup -------------------------------------------------

    def _get_correlation(self, symbol_a: str, symbol_b: str) -> float | None:
        """Look up the correlation between two symbols."""
        if symbol_a == symbol_b:
            return 1.0

        # Try both orderings
        key = (symbol_a, symbol_b)
        rev_key = (symbol_b, symbol_a)

        if key in self._correlations:
            return self._correlations[key]
        if rev_key in self._correlations:
            return self._correlations[rev_key]

        return None  # Unknown

    def update_correlation(
        self,
        symbol_a: str,
        symbol_b: str,
        correlation: float,
        sample_size: int = 0,
    ) -> None:
        """Update the correlation value between two symbols (from live data)."""
        self._correlations[(symbol_a, symbol_b)] = correlation
        self._correlation_cache[f"{symbol_a}:{symbol_b}"] = CorrelationPair(
            symbol_a=symbol_a,
            symbol_b=symbol_b,
            correlation=correlation,
            sample_size=sample_size,
        )

    # -- Status -------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        """Return current correlation monitor status."""
        return {
            "open_positions": len(self._positions),
            "positions": [
                {"symbol": p.symbol, "direction": p.direction, "size": p.size}
                for p in self._positions
            ],
            "portfolio_correlation": round(self.get_portfolio_correlation(), 3),
            "exposure_by_direction": self.get_exposure_by_direction(),
            "max_correlation_threshold": self._max_correlation,
        }
