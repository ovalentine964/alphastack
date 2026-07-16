"""Unit tests for forex-specific risk management.

Tests cover margin monitoring, spread widening circuit breakers,
session guards, weekend gap protection, and cross-broker exposure.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, time, timezone, timedelta
from enum import Enum
from typing import Optional

import pytest

from alphastack.brokers.models import (
    BrokerBalance,
    BrokerPosition,
    PositionSide,
)


# ---------------------------------------------------------------------------
# Inline reference implementations for forex risk components
# ---------------------------------------------------------------------------

class MarginAlertLevel(str, Enum):
    WARNING = "warning"       # margin_level < alert_threshold
    CRITICAL = "critical"     # margin_level < stop_out_threshold
    SAFE = "safe"


@dataclass
class MarginStatus:
    level: MarginAlertLevel
    margin_level_pct: float
    used_margin: float
    free_margin: float
    equity: float


class MarginMonitor:
    """Monitors margin level and triggers alerts/stop-out."""

    def __init__(
        self,
        alert_threshold: float = 150.0,   # % margin level → warning
        stop_out_threshold: float = 50.0,  # % margin level → force close
    ):
        self.alert_threshold = alert_threshold
        self.stop_out_threshold = stop_out_threshold

    def check(self, equity: float, used_margin: float) -> MarginStatus:
        if used_margin <= 0:
            margin_level = float("inf")
        else:
            margin_level = (equity / used_margin) * 100.0

        if margin_level <= self.stop_out_threshold:
            level = MarginAlertLevel.CRITICAL
        elif margin_level <= self.alert_threshold:
            level = MarginAlertLevel.WARNING
        else:
            level = MarginAlertLevel.SAFE

        return MarginStatus(
            level=level,
            margin_level_pct=margin_level,
            used_margin=used_margin,
            free_margin=equity - used_margin,
            equity=equity,
        )

    def should_stop_out(self, equity: float, used_margin: float) -> bool:
        return self.check(equity, used_margin).level == MarginAlertLevel.CRITICAL

    def positions_to_close(
        self,
        positions: list[BrokerPosition],
        equity: float,
        used_margin: float,
        target_margin_level: float = 100.0,
    ) -> list[BrokerPosition]:
        """Return positions to close (worst P&L first) to reach target margin level."""
        status = self.check(equity, used_margin)
        if status.level != MarginAlertLevel.CRITICAL:
            return []

        # Sort by unrealized P&L ascending (close losers first)
        sorted_positions = sorted(positions, key=lambda p: p.unrealized_pnl)
        to_close: list[BrokerPosition] = []
        freed_margin = 0.0

        for pos in sorted_positions:
            to_close.append(pos)
            freed_margin += pos.margin_used
            new_used = used_margin - freed_margin
            if new_used > 0 and ((equity / new_used) * 100) >= target_margin_level:
                break

        return to_close


# ---------------------------------------------------------------------------
# Spread Circuit Breaker
# ---------------------------------------------------------------------------

@dataclass
class SpreadSnapshot:
    symbol: str
    spread_pips: float
    timestamp: datetime


class SpreadCircuitBreaker:
    """Halts trading when spread widens beyond threshold.

    Tracks rolling window of spread readings and opens the circuit
    if the current spread exceeds max_multiplier * average.
    """

    def __init__(
        self,
        max_multiplier: float = 3.0,       # spread > 3× avg → open circuit
        window_size: int = 100,             # rolling window readings
        recovery_readings: int = 10,        # consecutive normal readings to close
    ):
        self.max_multiplier = max_multiplier
        self.window_size = window_size
        self.recovery_readings = recovery_readings
        self._history: dict[str, list[float]] = {}
        self._open: dict[str, bool] = {}
        self._recovery_count: dict[str, int] = {}

    def record(self, symbol: str, spread_pips: float) -> None:
        history = self._history.setdefault(symbol, [])
        history.append(spread_pips)
        if len(history) > self.window_size:
            self._history[symbol] = history[-self.window_size:]

    def is_open(self, symbol: str) -> bool:
        return self._open.get(symbol, False)

    def check(self, symbol: str, spread_pips: float) -> bool:
        """Record spread and check circuit breaker. Returns True if circuit is OPEN (trading blocked)."""
        history = self._history.get(symbol, [])
        if len(history) < 5:  # Need minimum samples
            self.record(symbol, spread_pips)
            return False

        avg = sum(history) / len(history)
        if avg <= 0:
            self.record(symbol, spread_pips)
            return False

        if spread_pips > avg * self.max_multiplier:
            # Don't record spike into baseline history
            self._open[symbol] = True
            self._recovery_count[symbol] = 0
            return True

        if self._open.get(symbol, False):
            self._recovery_count[symbol] = self._recovery_count.get(symbol, 0) + 1
            self.record(symbol, spread_pips)
            if self._recovery_count[symbol] >= self.recovery_readings:
                self._open[symbol] = False
                self._recovery_count[symbol] = 0
                return False  # Circuit closed after recovery
            return True  # Still open during recovery

        self.record(symbol, spread_pips)
        return False


# ---------------------------------------------------------------------------
# Session Guard
# ---------------------------------------------------------------------------

class ForexSession(str, Enum):
    SYDNEY = "sydney"
    TOKYO = "tokyo"
    LONDON = "london"
    NEW_YORK = "new_york"
    OVERLAP_LONDON_NY = "london_ny_overlap"
    WEEKEND = "weekend"
    LOW_LIQUIDITY = "low_liquidity"


# Session times in UTC
SESSION_TIMES: dict[ForexSession, tuple[time, time]] = {
    ForexSession.SYDNEY: (time(22, 0), time(7, 0)),
    ForexSession.TOKYO: (time(0, 0), time(9, 0)),
    ForexSession.LONDON: (time(7, 0), time(16, 0)),
    ForexSession.NEW_YORK: (time(12, 0), time(21, 0)),
    ForexSession.OVERLAP_LONDON_NY: (time(12, 0), time(16, 0)),
}

# Low-liquidity windows (UTC) — between sessions
LOW_LIQUIDITY_WINDOWS: list[tuple[time, time]] = [
    (time(21, 0), time(22, 0)),   # After NY close, before Sydney
    (time(7, 0), time(7, 30)),    # Early London — thin liquidity
]


class SessionGuard:
    """Blocks trading during low-liquidity or weekend periods."""

    def __init__(
        self,
        blocked_sessions: list[ForexSession] | None = None,
        weekend_close_hour_utc: int = 21,  # Friday
        weekend_open_hour_utc: int = 22,   # Sunday
    ):
        self.blocked_sessions = blocked_sessions or [ForexSession.LOW_LIQUIDITY, ForexSession.WEEKEND]
        self.weekend_close_hour_utc = weekend_close_hour_utc
        self.weekend_open_hour_utc = weekend_open_hour_utc

    def get_session(self, dt: datetime) -> ForexSession:
        """Determine the current forex session for a given datetime."""
        wd = dt.weekday()  # 0=Mon, 6=Sun
        t = dt.time()

        # Weekend check
        if wd == 5:  # Saturday
            return ForexSession.WEEKEND
        if wd == 6 and t.hour < self.weekend_open_hour_utc:
            return ForexSession.WEEKEND
        if wd == 4 and t.hour >= self.weekend_close_hour_utc:  # Friday after close
            return ForexSession.WEEKEND

        # Low liquidity windows
        for start, end in LOW_LIQUIDITY_WINDOWS:
            if start <= end:
                if start <= t < end:
                    return ForexSession.LOW_LIQUIDITY
            else:  # Wraps midnight
                if t >= start or t < end:
                    return ForexSession.LOW_LIQUIDITY

        # Overlap
        if time(12, 0) <= t < time(16, 0):
            return ForexSession.OVERLAP_LONDON_NY

        # Individual sessions
        if time(7, 0) <= t < time(16, 0):
            return ForexSession.LONDON
        if time(12, 0) <= t < time(21, 0):
            return ForexSession.NEW_YORK
        if time(0, 0) <= t < time(9, 0):
            return ForexSession.TOKYO

        return ForexSession.SYDNEY

    def is_trading_allowed(self, dt: datetime) -> bool:
        session = self.get_session(dt)
        return session not in self.blocked_sessions

    def check(self, dt: datetime) -> tuple[bool, ForexSession]:
        session = self.get_session(dt)
        return (session not in self.blocked_sessions, session)


# ---------------------------------------------------------------------------
# Weekend Gap Protection
# ---------------------------------------------------------------------------

@dataclass
class GapRiskAssessment:
    symbol: str
    current_price: float
    stop_loss: float | None
    stop_distance_pips: float
    estimated_gap_pips: float
    gap_risk_score: float  # 0-1, higher = more risk
    should_close: bool


class WeekendGapProtector:
    """Assess and protect against weekend gap risk."""

    # Historical average weekend gaps (pips) for major pairs
    TYPICAL_GAP_PIPS: dict[str, float] = {
        "EUR/USD": 15.0,
        "GBP/USD": 25.0,
        "USD/JPY": 20.0,
        "AUD/USD": 18.0,
        "NZD/USD": 22.0,
        "USD/CHF": 15.0,
        "USD/CAD": 12.0,
        "EUR/GBP": 10.0,
        "EUR/JPY": 25.0,
        "GBP/JPY": 35.0,
    }

    def __init__(
        self,
        close_before_weekend: bool = True,
        gap_threshold_pips: float = 50.0,
        close_hours_before: int = 2,  # hours before market close
    ):
        self.close_before_weekend = close_before_weekend
        self.gap_threshold_pips = gap_threshold_pips
        self.close_hours_before = close_hours_before

    def assess_gap_risk(
        self,
        symbol: str,
        stop_loss: float | None,
        current_price: float,
        pip_size: float = 0.0001,
    ) -> GapRiskAssessment:
        typical_gap = self.TYPICAL_GAP_PIPS.get(symbol, 20.0)

        if stop_loss is not None:
            stop_dist = abs(current_price - stop_loss) / pip_size
        else:
            stop_dist = float("inf")

        # Gap risk = typical_gap / stop_distance (if gap > stop, high risk)
        if stop_dist > 0 and stop_dist != float("inf"):
            gap_risk = min(typical_gap / stop_dist, 1.0)
        else:
            gap_risk = 0.0

        should_close = (
            self.close_before_weekend
            and typical_gap >= self.gap_threshold_pips * 0.3  # close if gap could be significant
            and stop_dist < typical_gap * 2.0  # stop is within 2× gap range
        )

        return GapRiskAssessment(
            symbol=symbol,
            current_price=current_price,
            stop_loss=stop_loss,
            stop_distance_pips=stop_dist,
            estimated_gap_pips=typical_gap,
            gap_risk_score=gap_risk,
            should_close=should_close,
        )

    def should_close_position(self, symbol: str, stop_loss: float | None, current_price: float, pip_size: float = 0.0001) -> bool:
        return self.assess_gap_risk(symbol, stop_loss, current_price, pip_size).should_close


# ---------------------------------------------------------------------------
# Cross-Broker Exposure Calculator
# ---------------------------------------------------------------------------

@dataclass
class ExposureEntry:
    broker: str
    symbol: str
    notional_value: float
    side: PositionSide
    margin_used: float


class CrossBrokerExposure:
    """Calculate aggregate exposure across multiple brokers."""

    def __init__(self, max_per_symbol_pct: float = 20.0, max_total_exposure_pct: float = 50.0):
        self.max_per_symbol_pct = max_per_symbol_pct
        self.max_total_exposure_pct = max_total_exposure_pct

    def calculate_symbol_exposure(
        self,
        positions: list[BrokerPosition],
        symbol: str,
    ) -> float:
        """Net notional exposure for a symbol across all brokers."""
        total = 0.0
        for pos in positions:
            if pos.symbol == symbol:
                sign = 1.0 if pos.side == PositionSide.LONG else -1.0
                total += sign * pos.notional_value
        return total

    def calculate_total_exposure(self, positions: list[BrokerPosition]) -> float:
        """Absolute total notional across all positions."""
        return sum(abs(p.notional_value) for p in positions)

    def check_symbol_limit(
        self,
        positions: list[BrokerPosition],
        symbol: str,
        total_equity: float,
    ) -> tuple[bool, float]:
        """Check if symbol exposure is within limit. Returns (ok, pct)."""
        exposure = abs(self.calculate_symbol_exposure(positions, symbol))
        pct = (exposure / total_equity * 100) if total_equity > 0 else 0
        return (pct <= self.max_per_symbol_pct, pct)

    def check_total_limit(
        self,
        positions: list[BrokerPosition],
        total_equity: float,
    ) -> tuple[bool, float]:
        """Check total exposure is within limit. Returns (ok, pct)."""
        exposure = self.calculate_total_exposure(positions)
        pct = (exposure / total_equity * 100) if total_equity > 0 else 0
        return (pct <= self.max_total_exposure_pct, pct)

    def exposure_by_symbol(self, positions: list[BrokerPosition]) -> dict[str, float]:
        """Aggregate net exposure grouped by symbol."""
        result: dict[str, float] = {}
        for pos in positions:
            sign = 1.0 if pos.side == PositionSide.LONG else -1.0
            result[pos.symbol] = result.get(pos.symbol, 0.0) + sign * pos.notional_value
        return result

    def exposure_by_broker(self, positions: list[BrokerPosition]) -> dict[str, float]:
        """Aggregate absolute exposure grouped by broker."""
        result: dict[str, float] = {}
        for pos in positions:
            result[pos.broker] = result.get(pos.broker, 0.0) + abs(pos.notional_value)
        return result


# ===========================================================================
# TESTS — Margin Monitor
# ===========================================================================

class TestMarginMonitor:

    def test_safe_margin_level(self):
        monitor = MarginMonitor(alert_threshold=150, stop_out_threshold=50)
        status = monitor.check(equity=10_000, used_margin=2_000)
        assert status.level == MarginAlertLevel.SAFE
        assert status.margin_level_pct == pytest.approx(500.0)

    def test_warning_margin_level(self):
        monitor = MarginMonitor(alert_threshold=150, stop_out_threshold=50)
        status = monitor.check(equity=1_400, used_margin=1_000)
        assert status.level == MarginAlertLevel.WARNING
        assert status.margin_level_pct == pytest.approx(140.0)

    def test_critical_margin_level(self):
        monitor = MarginMonitor(alert_threshold=150, stop_out_threshold=50)
        status = monitor.check(equity=400, used_margin=1_000)
        assert status.level == MarginAlertLevel.CRITICAL
        assert status.margin_level_pct == pytest.approx(40.0)

    def test_exact_alert_threshold(self):
        monitor = MarginMonitor(alert_threshold=150, stop_out_threshold=50)
        status = monitor.check(equity=1_500, used_margin=1_000)
        assert status.level == MarginAlertLevel.WARNING

    def test_exact_stop_out_threshold(self):
        monitor = MarginMonitor(alert_threshold=150, stop_out_threshold=50)
        status = monitor.check(equity=500, used_margin=1_000)
        assert status.level == MarginAlertLevel.CRITICAL

    def test_no_margin_used(self):
        monitor = MarginMonitor()
        status = monitor.check(equity=10_000, used_margin=0)
        assert status.level == MarginAlertLevel.SAFE
        assert status.margin_level_pct == float("inf")

    def test_should_stop_out_true(self):
        monitor = MarginMonitor(stop_out_threshold=50)
        assert monitor.should_stop_out(equity=400, used_margin=1_000) is True

    def test_should_stop_out_false(self):
        monitor = MarginMonitor(stop_out_threshold=50)
        assert monitor.should_stop_out(equity=10_000, used_margin=1_000) is False

    def test_positions_to_close_empty_when_safe(self):
        monitor = MarginMonitor()
        positions = [
            BrokerPosition(broker="oanda", symbol="EUR/USD", margin_used=500, unrealized_pnl=-100),
        ]
        to_close = monitor.positions_to_close(positions, equity=10_000, used_margin=500)
        assert to_close == []

    def test_positions_to_close_worst_first(self):
        monitor = MarginMonitor(stop_out_threshold=50)
        positions = [
            BrokerPosition(broker="oanda", symbol="EUR/USD", margin_used=500, unrealized_pnl=-200),
            BrokerPosition(broker="oanda", symbol="GBP/USD", margin_used=500, unrealized_pnl=-50),
        ]
        # equity=500, used=1000 → margin_level=50% → critical
        to_close = monitor.positions_to_close(positions, equity=500, used_margin=1_000)
        assert len(to_close) >= 1
        # Worst P&L position should be closed first
        assert to_close[0].symbol == "EUR/USD"

    def test_free_margin_calculation(self):
        monitor = MarginMonitor()
        status = monitor.check(equity=10_000, used_margin=3_000)
        assert status.free_margin == pytest.approx(7_000.0)


# ===========================================================================
# TESTS — Spread Circuit Breaker
# ===========================================================================

class TestSpreadCircuitBreaker:

    def test_initial_state_closed(self):
        cb = SpreadCircuitBreaker()
        assert cb.is_open("EUR/USD") is False

    def test_normal_spread_keeps_closed(self):
        cb = SpreadCircuitBreaker(max_multiplier=3.0)
        for _ in range(20):
            cb.record("EUR/USD", 1.5)
        assert cb.check("EUR/USD", 1.6) is False
        assert cb.is_open("EUR/USD") is False

    def test_widened_spread_opens_circuit(self):
        cb = SpreadCircuitBreaker(max_multiplier=3.0)
        # Build baseline at ~1.5 pips
        for _ in range(20):
            cb.record("EUR/USD", 1.5)
        # Spike to 5.0 pips (3.3x > 3.0x)
        is_open = cb.check("EUR/USD", 5.0)
        assert is_open is True
        assert cb.is_open("EUR/USD") is True

    def test_recovery_after_normal_readings(self):
        cb = SpreadCircuitBreaker(max_multiplier=3.0, recovery_readings=5)
        for _ in range(20):
            cb.record("EUR/USD", 1.5)
        # Open circuit
        cb.check("EUR/USD", 5.0)
        assert cb.is_open("EUR/USD") is True

        # Recovery readings (need exactly recovery_readings=5 normal checks)
        for i in range(4):
            result = cb.check("EUR/USD", 1.5)
            assert result is True  # Still open

        result = cb.check("EUR/USD", 1.5)
        assert result is False  # Closed after recovery_readings
        assert cb.is_open("EUR/USD") is False

    def test_independent_per_symbol(self):
        cb = SpreadCircuitBreaker(max_multiplier=3.0)
        for _ in range(20):
            cb.record("EUR/USD", 1.5)
            cb.record("GBP/USD", 2.5)

        cb.check("EUR/USD", 5.0)  # Open for EUR/USD
        assert cb.is_open("EUR/USD") is True
        assert cb.is_open("GBP/USD") is False

    def test_minimum_samples_required(self):
        """Circuit breaker should not trigger with too few samples."""
        cb = SpreadCircuitBreaker(max_multiplier=3.0)
        cb.record("EUR/USD", 1.5)
        cb.record("EUR/USD", 1.5)
        is_open = cb.check("EUR/USD", 10.0)
        assert is_open is False

    def test_window_size_limits_history(self):
        cb = SpreadCircuitBreaker(window_size=10)
        for _ in range(50):
            cb.record("EUR/USD", 1.5)
        assert len(cb._history["EUR/USD"]) == 10

    def test_spread_at_multiplier_boundary(self):
        """Spread exactly at multiplier should NOT open (strictly greater)."""
        cb = SpreadCircuitBreaker(max_multiplier=3.0)
        for _ in range(20):
            cb.record("EUR/USD", 1.0)
        # avg=1.0, threshold=3.0, spread=3.0 → not strictly greater
        is_open = cb.check("EUR/USD", 3.0)
        assert is_open is False


# ===========================================================================
# TESTS — Session Guard
# ===========================================================================

class TestSessionGuard:

    def test_london_session_allows_trading(self):
        guard = SessionGuard()
        dt = datetime(2025, 6, 16, 10, 0, tzinfo=timezone.utc)  # Monday 10:00 UTC
        allowed, session = guard.check(dt)
        assert allowed is True
        assert session == ForexSession.LONDON

    def test_new_york_session(self):
        guard = SessionGuard()
        dt = datetime(2025, 6, 16, 15, 0, tzinfo=timezone.utc)
        allowed, session = guard.check(dt)
        assert allowed is True
        # Could be LONDON or OVERLAP depending on implementation
        assert session in (ForexSession.OVERLAP_LONDON_NY, ForexSession.NEW_YORK)

    def test_tokyo_session(self):
        guard = SessionGuard()
        dt = datetime(2025, 6, 16, 3, 0, tzinfo=timezone.utc)
        allowed, session = guard.check(dt)
        assert allowed is True
        assert session == ForexSession.TOKYO

    def test_saturday_blocked(self):
        guard = SessionGuard(blocked_sessions=[ForexSession.WEEKEND])
        dt = datetime(2025, 6, 21, 12, 0, tzinfo=timezone.utc)  # Saturday
        allowed, session = guard.check(dt)
        assert allowed is False
        assert session == ForexSession.WEEKEND

    def test_sunday_before_open_blocked(self):
        guard = SessionGuard(blocked_sessions=[ForexSession.WEEKEND])
        dt = datetime(2025, 6, 22, 18, 0, tzinfo=timezone.utc)  # Sunday 18:00 UTC
        allowed, session = guard.check(dt)
        assert allowed is False

    def test_sunday_after_open_allowed(self):
        guard = SessionGuard(blocked_sessions=[ForexSession.WEEKEND])
        dt = datetime(2025, 6, 22, 22, 30, tzinfo=timezone.utc)  # Sunday 22:30 UTC
        allowed, session = guard.check(dt)
        assert allowed is True

    def test_friday_evening_blocked(self):
        guard = SessionGuard(blocked_sessions=[ForexSession.WEEKEND])
        dt = datetime(2025, 6, 20, 21, 30, tzinfo=timezone.utc)  # Friday 21:30 UTC
        allowed, session = guard.check(dt)
        assert allowed is False
        assert session == ForexSession.WEEKEND

    def test_low_liquidity_blocked(self):
        guard = SessionGuard(blocked_sessions=[ForexSession.LOW_LIQUIDITY, ForexSession.WEEKEND])
        # 21:30 UTC — between NY close and Sydney open
        dt = datetime(2025, 6, 16, 21, 30, tzinfo=timezone.utc)
        allowed, session = guard.check(dt)
        assert allowed is False
        assert session == ForexSession.LOW_LIQUIDITY

    def test_london_ny_overlap_best_liquidity(self):
        guard = SessionGuard()
        dt = datetime(2025, 6, 16, 14, 0, tzinfo=timezone.utc)  # 14:00 UTC
        allowed, session = guard.check(dt)
        assert allowed is True
        assert session == ForexSession.OVERLAP_LONDON_NY

    def test_custom_blocked_sessions(self):
        guard = SessionGuard(blocked_sessions=[ForexSession.TOKYO])
        dt = datetime(2025, 6, 16, 3, 0, tzinfo=timezone.utc)
        allowed, session = guard.check(dt)
        assert allowed is False
        assert session == ForexSession.TOKYO

    def test_sydney_session(self):
        guard = SessionGuard(blocked_sessions=[ForexSession.WEEKEND])
        dt = datetime(2025, 6, 16, 23, 0, tzinfo=timezone.utc)  # 23:00 UTC
        allowed, session = guard.check(dt)
        assert allowed is True
        assert session == ForexSession.SYDNEY


# ===========================================================================
# TESTS — Weekend Gap Protection
# ===========================================================================

class TestWeekendGapProtection:

    def test_eurusd_low_gap_risk_with_wide_stop(self):
        protector = WeekendGapProtector()
        risk = protector.assess_gap_risk("EUR/USD", stop_loss=1.0900, current_price=1.1000)
        # Stop is 100 pips away, typical gap is 15 pips → low risk
        assert risk.gap_risk_score < 0.5
        assert risk.should_close is False

    def test_eurusd_high_gap_risk_with_tight_stop(self):
        protector = WeekendGapProtector()
        risk = protector.assess_gap_risk("EUR/USD", stop_loss=1.0995, current_price=1.1000)
        # Stop is only 5 pips away, typical gap is 15 pips → high risk
        assert risk.gap_risk_score > 0.5
        assert risk.should_close is True

    def test_gbpjpy_higher_gap_risk_than_eurusd(self):
        protector = WeekendGapProtector()
        risk_eu = protector.assess_gap_risk("EUR/USD", stop_loss=1.0990, current_price=1.1000)
        risk_gj = protector.assess_gap_risk("GBP/JPY", stop_loss=190.05, current_price=190.00)
        # GBP/JPY has higher typical gap (35 vs 15 pips)
        assert risk_gj.estimated_gap_pips > risk_eu.estimated_gap_pips

    def test_no_stop_loss_zero_risk(self):
        protector = WeekendGapProtector()
        risk = protector.assess_gap_risk("EUR/USD", stop_loss=None, current_price=1.1000)
        assert risk.gap_risk_score == 0.0
        assert risk.should_close is False

    def test_unknown_symbol_uses_default_gap(self):
        protector = WeekendGapProtector()
        risk = protector.assess_gap_risk("USD/SGD", stop_loss=1.3500, current_price=1.3550)
        # Default gap = 20 pips, stop distance = 50 pips
        assert risk.estimated_gap_pips == 20.0

    def test_should_close_position_method(self):
        protector = WeekendGapProtector()
        # Tight stop on volatile pair (JPY pair uses pip_size=0.01)
        assert protector.should_close_position("GBP/JPY", stop_loss=190.02, current_price=190.00, pip_size=0.01) is True
        # Wide stop on calm pair
        assert protector.should_close_position("EUR/USD", stop_loss=1.0900, current_price=1.1000) is False

    def test_gap_threshold_configuration(self):
        protector = WeekendGapProtector(gap_threshold_pips=100.0)
        risk = protector.assess_gap_risk("EUR/USD", stop_loss=1.0990, current_price=1.1000)
        # With higher threshold, fewer positions should be closed
        # threshold=100 → close_before condition: 15 >= 50 is False
        assert risk.should_close is False

    def test_close_hours_before_config(self):
        """Verify the protector tracks pre-close configuration."""
        protector = WeekendGapProtector(close_hours_before=4)
        assert protector.close_hours_before == 4


# ===========================================================================
# TESTS — Cross-Broker Exposure
# ===========================================================================

class TestCrossBrokerExposure:

    def _make_position(self, broker: str, symbol: str, side: PositionSide,
                       qty: float, price: float, margin: float = 0) -> BrokerPosition:
        return BrokerPosition(
            broker=broker,
            symbol=symbol,
            side=side,
            quantity=qty,
            current_price=price,
            margin_used=margin,
        )

    def test_symbol_exposure_single_broker(self):
        calc = CrossBrokerExposure()
        positions = [
            self._make_position("oanda", "EUR/USD", PositionSide.LONG, 100_000, 1.1000),
        ]
        exposure = calc.calculate_symbol_exposure(positions, "EUR/USD")
        assert exposure == pytest.approx(110_000.0)

    def test_symbol_exposure_multi_broker(self):
        calc = CrossBrokerExposure()
        positions = [
            self._make_position("oanda", "EUR/USD", PositionSide.LONG, 100_000, 1.1000),
            self._make_position("mt5", "EUR/USD", PositionSide.LONG, 50_000, 1.1000),
        ]
        exposure = calc.calculate_symbol_exposure(positions, "EUR/USD")
        assert exposure == pytest.approx(165_000.0)

    def test_net_exposure_long_short_offset(self):
        """Long on one broker, short on another → net exposure reduced."""
        calc = CrossBrokerExposure()
        positions = [
            self._make_position("oanda", "EUR/USD", PositionSide.LONG, 100_000, 1.1000),
            self._make_position("mt5", "EUR/USD", PositionSide.SHORT, 50_000, 1.1000),
        ]
        net = calc.calculate_symbol_exposure(positions, "EUR/USD")
        # 110_000 (long) - 55_000 (short) = 55_000
        assert net == pytest.approx(55_000.0)

    def test_total_exposure_sums_absolute(self):
        calc = CrossBrokerExposure()
        positions = [
            self._make_position("oanda", "EUR/USD", PositionSide.LONG, 100_000, 1.1000),
            self._make_position("mt5", "GBP/USD", PositionSide.SHORT, 50_000, 1.2700),
        ]
        total = calc.calculate_total_exposure(positions)
        assert total == pytest.approx(110_000 + 63_500)

    def test_symbol_limit_within(self):
        calc = CrossBrokerExposure(max_per_symbol_pct=20.0)
        positions = [
            self._make_position("oanda", "EUR/USD", PositionSide.LONG, 100_000, 1.1000),
        ]
        ok, pct = calc.check_symbol_limit(positions, "EUR/USD", total_equity=100_000)
        # 110_000 / 100_000 = 110% > 20% → False
        assert ok is False
        assert pct == pytest.approx(110.0)

    def test_symbol_limit_within_range(self):
        calc = CrossBrokerExposure(max_per_symbol_pct=20.0)
        positions = [
            self._make_position("oanda", "EUR/USD", PositionSide.LONG, 10_000, 1.1000),
        ]
        ok, pct = calc.check_symbol_limit(positions, "EUR/USD", total_equity=100_000)
        # 11_000 / 100_000 = 11% < 20% → True
        assert ok is True
        assert pct == pytest.approx(11.0)

    def test_total_limit_exceeded(self):
        calc = CrossBrokerExposure(max_total_exposure_pct=50.0)
        positions = [
            self._make_position("oanda", "EUR/USD", PositionSide.LONG, 100_000, 1.1000, margin=1100),
            self._make_position("mt5", "GBP/USD", PositionSide.LONG, 50_000, 1.2700, margin=635),
        ]
        ok, pct = calc.check_total_limit(positions, total_equity=10_000)
        # total = 110_000 + 63_500 = 173_500 → 1735% > 50%
        assert ok is False
        assert pct > 50.0

    def test_exposure_by_symbol(self):
        calc = CrossBrokerExposure()
        positions = [
            self._make_position("oanda", "EUR/USD", PositionSide.LONG, 100_000, 1.1000),
            self._make_position("mt5", "EUR/USD", PositionSide.LONG, 50_000, 1.1000),
            self._make_position("oanda", "GBP/USD", PositionSide.SHORT, 30_000, 1.2700),
        ]
        by_sym = calc.exposure_by_symbol(positions)
        assert by_sym["EUR/USD"] == pytest.approx(165_000.0)
        assert by_sym["GBP/USD"] == pytest.approx(-38_100.0)

    def test_exposure_by_broker(self):
        calc = CrossBrokerExposure()
        positions = [
            self._make_position("oanda", "EUR/USD", PositionSide.LONG, 100_000, 1.1000),
            self._make_position("mt5", "GBP/USD", PositionSide.SHORT, 50_000, 1.2700),
        ]
        by_broker = calc.exposure_by_broker(positions)
        assert by_broker["oanda"] == pytest.approx(110_000.0)
        assert by_broker["mt5"] == pytest.approx(63_500.0)

    def test_empty_positions(self):
        calc = CrossBrokerExposure()
        assert calc.calculate_total_exposure([]) == 0.0
        assert calc.calculate_symbol_exposure([], "EUR/USD") == 0.0

    def test_hedge_reduces_net_exposure(self):
        """Perfect hedge across brokers → zero net exposure."""
        calc = CrossBrokerExposure()
        positions = [
            self._make_position("oanda", "EUR/USD", PositionSide.LONG, 100_000, 1.1000),
            self._make_position("mt5", "EUR/USD", PositionSide.SHORT, 100_000, 1.1000),
        ]
        net = calc.calculate_symbol_exposure(positions, "EUR/USD")
        assert net == pytest.approx(0.0)
        # But total exposure (absolute) is still high
        total = calc.calculate_total_exposure(positions)
        assert total == pytest.approx(220_000.0)
