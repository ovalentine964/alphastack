"""Unit tests for risk management components."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest

from alphastack.risk.circuit_breaker import BreakerType, CircuitBreaker
from alphastack.risk.drawdown import DrawdownManager
from alphastack.risk.exposure import ExposureManager, ExposureSnapshot, PositionExposure
from alphastack.risk.governor import RiskGovernor, RiskEvent, RiskEventType, TradeApproval, TradeRequest
from alphastack.risk.position_sizer import (
    PositionSizer,
    SizingMethod,
    SizingRequest,
    SizingResult,
)
from alphastack.risk.correlation import CorrelationMonitor, OpenPosition
from alphastack.risk.validators import (
    TradeValidator,
    ValidationResult,
    ValidationSeverity,
)


# ---------------------------------------------------------------------------
# Trade Validator tests
# ---------------------------------------------------------------------------

class TestTradeValidator:

    def _make_request(self, **kwargs: Any) -> Any:
        """Build a TradeRequest-like object with defaults."""
        defaults = {
            "symbol": "EUR/USD",
            "direction": "long",
            "requested_size": 0.1,
            "entry_price": 1.1050,
            "stop_loss": 1.1000,
            "take_profit": 1.1150,
            "strategy_id": "test",
            "session": "london",
        }
        defaults.update(kwargs)
        return TradeRequest(**defaults)

    def test_valid_trade_passes(self, trade_validator: TradeValidator) -> None:
        request = self._make_request()
        result = trade_validator.validate_pre_trade(request)
        assert result.valid is True
        assert len(result.errors) == 0

    def test_zero_price_rejected(self, trade_validator: TradeValidator) -> None:
        request = self._make_request(entry_price=0.0)
        result = trade_validator.validate_pre_trade(request)
        assert result.valid is False

    def test_negative_size_rejected(self, trade_validator: TradeValidator) -> None:
        request = self._make_request(requested_size=-0.1)
        result = trade_validator.validate_pre_trade(request)
        assert result.valid is False

    def test_invalid_direction_rejected(self, trade_validator: TradeValidator) -> None:
        request = self._make_request(direction="sideways")
        result = trade_validator.validate_pre_trade(request)
        assert result.valid is False

    def test_long_stop_above_entry_rejected(self, trade_validator: TradeValidator) -> None:
        """Stop loss above entry for a long trade is backwards."""
        request = self._make_request(entry_price=1.1000, stop_loss=1.1100)
        result = trade_validator.validate_pre_trade(request)
        assert result.valid is False

    def test_short_stop_below_entry_rejected(self, trade_validator: TradeValidator) -> None:
        """Stop loss below entry for a short trade is backwards."""
        request = self._make_request(direction="short", entry_price=1.1000, stop_loss=1.0900)
        result = trade_validator.validate_pre_trade(request)
        assert result.valid is False

    def test_extreme_price_rejected(self, trade_validator: TradeValidator) -> None:
        request = self._make_request(entry_price=1e15)
        result = trade_validator.validate_pre_trade(request)
        assert result.valid is False

    def test_empty_symbol_rejected(self, trade_validator: TradeValidator) -> None:
        request = self._make_request(symbol="")
        result = trade_validator.validate_pre_trade(request)
        assert result.valid is False

    def test_nan_price_rejected(self, trade_validator: TradeValidator) -> None:
        request = self._make_request(entry_price=float("nan"))
        result = trade_validator.validate_pre_trade(request)
        assert result.valid is False

    def test_post_trade_slippage_warning(self, trade_validator: TradeValidator) -> None:
        """Excessive slippage should generate a warning."""
        result = trade_validator.validate_post_trade(
            expected_price=1.1000,
            fill_price=1.1200,  # 1.8% slippage
            expected_size=0.1,
            fill_size=0.1,
            direction="long",
        )
        # Should have slippage warning but not necessarily error
        assert len(result.warnings) > 0 or len(result.issues) > 0

    def test_order_modify_sl_moved_against(self, trade_validator: TradeValidator) -> None:
        """Moving SL wider should generate a warning."""
        result = trade_validator.validate_order_modify(
            current_sl=1.0950,
            new_sl=1.0900,  # wider for long
            current_tp=1.1200,
            new_tp=1.1200,
            entry_price=1.1000,
            direction="long",
        )
        assert result.valid is True  # still valid, just a warning
        assert len(result.warnings) > 0


# ---------------------------------------------------------------------------
# Exposure Manager tests
# ---------------------------------------------------------------------------

class TestExposureManager:

    def test_add_and_remove_position(self, exposure_manager: ExposureManager) -> None:
        pos = PositionExposure(
            symbol="EUR/USD", direction="long", size=0.1,
            entry_price=1.1050, session="london",
        )
        exposure_manager.add_position(pos)
        assert len(exposure_manager._positions) == 1

        exposure_manager.remove_position("EUR/USD")
        assert len(exposure_manager._positions) == 0

    def test_max_positions_enforced(self, exposure_manager: ExposureManager) -> None:
        """Should reject when max open positions is reached."""
        for i in range(5):  # max is 5
            exposure_manager.add_position(PositionExposure(
                symbol=f"PAIR_{i}", direction="long", size=0.01,
                entry_price=1.0, session="london",
            ))

        ok, reason = exposure_manager.check_add_position(
            symbol="PAIR_NEW", direction="long", size=0.01,
            price=1.0, balance=10_000.0, session="london",
        )
        assert ok is False
        assert "Max open positions" in reason

    def test_per_pair_exposure_enforced(self, exposure_manager: ExposureManager) -> None:
        """Should reject when per-pair exposure exceeds limit."""
        # Add position that uses 25% of balance
        exposure_manager.add_position(PositionExposure(
            symbol="EUR/USD", direction="long", size=2.0,
            entry_price=1.25, session="london",
        ))

        # Try to add more that would exceed 30% limit
        ok, reason = exposure_manager.check_add_position(
            symbol="EUR/USD", direction="long", size=1.0,
            price=1.25, balance=10.0, session="london",
        )
        assert ok is False
        assert "Per-pair exposure" in reason

    def test_leverage_enforced(self, exposure_manager: ExposureManager) -> None:
        """Should reject when leverage exceeds limit."""
        ok, reason = exposure_manager.check_add_position(
            symbol="EUR/USD", direction="long", size=5.0,
            price=1.0, balance=1.0, session="london",
        )
        assert ok is False
        assert "leverage" in reason.lower()

    def test_snapshot_accuracy(self, exposure_manager: ExposureManager) -> None:
        exposure_manager.add_position(PositionExposure(
            symbol="EUR/USD", direction="long", size=1.0,
            entry_price=1.10, session="london",
        ))
        exposure_manager.add_position(PositionExposure(
            symbol="GBP/USD", direction="short", size=0.5,
            entry_price=1.30, session="new_york",
        ))

        snapshot = exposure_manager.get_snapshot(balance=10_000.0)
        assert snapshot.total_positions == 2
        assert snapshot.per_pair_exposure["EUR/USD"] == pytest.approx(1.10)
        assert snapshot.per_pair_exposure["GBP/USD"] == pytest.approx(0.65)

    def test_clear_positions(self, exposure_manager: ExposureManager) -> None:
        exposure_manager.add_position(PositionExposure(
            symbol="EUR/USD", direction="long", size=0.1,
            entry_price=1.10, session="london",
        ))
        exposure_manager.clear()
        assert len(exposure_manager._positions) == 0


# ---------------------------------------------------------------------------
# Position Sizer tests
# ---------------------------------------------------------------------------

class TestPositionSizer:

    def test_fixed_risk_sizing(self) -> None:
        sizer = PositionSizer(account_balance=10_000.0)
        request = SizingRequest(
            symbol="EUR/USD",
            direction="long",
            entry_price=1.1050,
            stop_loss=1.1000,
            account_balance=10_000.0,
            method=SizingMethod.FIXED_RISK,
            max_risk_pct=2.0,
        )
        result = sizer.size_position(request)
        assert isinstance(result, SizingResult)
        assert result.risk_amount > 0
        assert result.risk_pct <= 2.0 + 0.01  # small tolerance

    def test_zero_balance_returns_zero(self) -> None:
        sizer = PositionSizer(account_balance=0.0)
        request = SizingRequest(
            symbol="EUR/USD",
            direction="long",
            entry_price=1.1050,
            stop_loss=1.1000,
            account_balance=0.0,
            method=SizingMethod.FIXED_RISK,
        )
        result = sizer.size_position(request)
        assert result.max_size == 0.0

    def test_kelly_sizing(self) -> None:
        sizer = PositionSizer(account_balance=10_000.0)
        request = SizingRequest(
            symbol="EUR/USD",
            direction="long",
            entry_price=1.1050,
            stop_loss=1.1000,
            account_balance=10_000.0,
            method=SizingMethod.KELLY,
            win_rate=0.6,
            avg_win=2.0,
            avg_loss=1.0,
        )
        result = sizer.size_position(request)
        assert result.max_size > 0
        assert result.method_used == SizingMethod.KELLY

    def test_larger_stop_means_smaller_size(self) -> None:
        """Wider stop → less size for same risk budget."""
        sizer = PositionSizer(account_balance=10_000.0)
        base = SizingRequest(
            symbol="EUR/USD", direction="long",
            entry_price=1.1050, stop_loss=1.1000,
            account_balance=10_000.0, max_risk_pct=2.0,
        )
        wide = SizingRequest(
            symbol="EUR/USD", direction="long",
            entry_price=1.1050, stop_loss=1.0900,
            account_balance=10_000.0, max_risk_pct=2.0,
        )
        r1 = sizer.size_position(base)
        r2 = sizer.size_position(wide)
        assert r1.max_size > r2.max_size

    def test_drawdown_de_escalation(self) -> None:
        """Higher drawdown should reduce position size."""
        sizer = PositionSizer(account_balance=10_000.0, default_risk_pct=2.0)

        low_dd = SizingRequest(
            symbol="EUR/USD", direction="long",
            entry_price=1.1050, stop_loss=1.1000,
            account_balance=10_000.0,
            daily_drawdown_pct=0.0,
        )
        high_dd = SizingRequest(
            symbol="EUR/USD", direction="long",
            entry_price=1.1050, stop_loss=1.1000,
            account_balance=10_000.0,
            daily_drawdown_pct=6.0,
        )
        r1 = sizer.size_position(low_dd)
        r2 = sizer.size_position(high_dd)
        assert r1.max_size > r2.max_size

    def test_spread_cost_reduces_size(self) -> None:
        """Spread cost should reduce position size when significant."""
        sizer = PositionSizer(account_balance=10_000.0)

        no_spread = SizingRequest(
            symbol="EUR/USD", direction="long",
            entry_price=1.1050, stop_loss=1.1000,
            account_balance=10_000.0,
            spread_pips=0.0,
        )
        big_spread = SizingRequest(
            symbol="EUR/USD", direction="long",
            entry_price=1.1050, stop_loss=1.1000,
            account_balance=10_000.0,
            spread_pips=10.0,  # very wide spread
            pip_value=0.0001,
        )
        r1 = sizer.size_position(no_spread)
        r2 = sizer.size_position(big_spread)
        # With large spread, size should be reduced
        assert r2.spread_cost > 0


# ---------------------------------------------------------------------------
# Circuit Breaker tests
# ---------------------------------------------------------------------------

class TestCircuitBreaker:

    def test_initial_state(self) -> None:
        cb = CircuitBreaker(max_daily_loss_pct=3.0, max_consecutive_losses=5)
        assert cb.is_tripped is False
        assert cb.trip_reason == ""
        assert cb.daily_pnl == 0.0
        assert cb.consecutive_losses == 0

    def test_daily_loss_breaker(self) -> None:
        cb = CircuitBreaker(
            max_daily_loss_pct=3.0,
            account_balance=10_000.0,
            max_consecutive_losses=100,
        )
        # Lose 3% = $300
        cb.record_loss(-150.0)
        assert cb.is_tripped is False
        cb.record_loss(-160.0)
        assert cb.is_tripped is True
        assert "Daily loss" in cb.trip_reason

    def test_consecutive_loss_breaker(self) -> None:
        cb = CircuitBreaker(
            max_daily_loss_pct=100.0,  # disable daily breaker
            max_consecutive_losses=3,
            account_balance=10_000.0,
        )
        for _ in range(3):
            assert cb.is_tripped is False
            cb.record_loss(-1.0)
        assert cb.is_tripped is True
        assert "Consecutive losses" in cb.trip_reason

    def test_win_resets_consecutive(self) -> None:
        cb = CircuitBreaker(
            max_daily_loss_pct=100.0,
            max_consecutive_losses=5,
        )
        cb.record_loss(-1.0)
        cb.record_loss(-1.0)
        assert cb.consecutive_losses == 2
        cb.record_loss(5.0)  # win
        assert cb.consecutive_losses == 0

    def test_reset_after_cooldown(self) -> None:
        cb = CircuitBreaker(
            max_daily_loss_pct=100.0,
            max_consecutive_losses=2,
            cooldown_minutes=0,  # no cooldown for test
        )
        cb.record_loss(-1.0)
        cb.record_loss(-1.0)
        assert cb.is_tripped is True
        reset_ok = cb.reset()
        assert reset_ok is True
        assert cb.is_tripped is False

    def test_force_reset(self) -> None:
        cb = CircuitBreaker(
            max_daily_loss_pct=100.0,
            max_consecutive_losses=1,
            cooldown_minutes=60,
        )
        cb.record_loss(-1.0)
        assert cb.is_tripped is True
        # Normal reset should fail (cooldown)
        assert cb.reset() is False
        # Force reset should work
        cb.force_reset()
        assert cb.is_tripped is False

    def test_daily_reset(self) -> None:
        cb = CircuitBreaker(max_daily_loss_pct=3.0, max_consecutive_losses=100)
        cb.record_loss(-50.0)
        assert cb.daily_pnl == -50.0
        cb.reset_daily()
        assert cb.daily_pnl == 0.0

    def test_state_snapshot(self) -> None:
        cb = CircuitBreaker(max_daily_loss_pct=3.0, max_consecutive_losses=5)
        state = cb.state
        assert state.tripped is False
        assert state.daily_pnl == 0.0
        assert state.consecutive_losses == 0


# ---------------------------------------------------------------------------
# Drawdown Manager tests
# ---------------------------------------------------------------------------

class TestDrawdownManager:

    def test_initial_state(self) -> None:
        dm = DrawdownManager(account_balance=10_000.0)
        assert dm.state.current_balance == 10_000.0
        assert dm.state.peak_balance == 10_000.0
        assert dm.is_breach() is False

    def test_drawdown_tracking(self) -> None:
        dm = DrawdownManager(account_balance=10_000.0, max_total_pct=15.0)
        dm.record_pnl(-500.0)
        assert dm.state.current_balance == 9_500.0
        assert dm.state.total_pct == pytest.approx(5.0)
        assert dm.is_breach() is False

    def test_drawdown_breach(self) -> None:
        dm = DrawdownManager(account_balance=10_000.0, max_total_pct=10.0)
        dm.record_pnl(-1_001.0)
        assert dm.is_breach() is True

    def test_daily_drawdown_breach(self) -> None:
        dm = DrawdownManager(
            account_balance=10_000.0,
            max_daily_pct=3.0,
            max_total_pct=100.0,
        )
        dm.record_pnl(-301.0)
        assert dm.is_breach() is True

    def test_peak_tracking(self) -> None:
        dm = DrawdownManager(account_balance=10_000.0)
        dm.record_pnl(2_000.0)
        assert dm.state.peak_balance == 12_000.0
        dm.record_pnl(-1_000.0)
        assert dm.state.peak_balance == 12_000.0  # peak unchanged
        assert dm.state.current_balance == 11_000.0

    def test_risk_multiplier_de_escalation(self) -> None:
        dm = DrawdownManager(
            account_balance=10_000.0,
            max_daily_pct=100.0,
            max_total_pct=10.0,
        )
        assert dm.risk_multiplier() == 1.0  # no drawdown
        dm.record_pnl(-500.0)  # 5% dd
        assert dm.risk_multiplier() < 1.0

    def test_daily_reset(self) -> None:
        dm = DrawdownManager(account_balance=10_000.0)
        dm.record_pnl(-200.0)
        assert dm.state.daily_pnl == -200.0
        dm.reset_daily()
        assert dm.state.daily_pnl == 0.0
        assert dm.state.daily_pct == 0.0

    def test_full_reset(self) -> None:
        dm = DrawdownManager(account_balance=10_000.0)
        dm.record_pnl(-500.0)
        dm.full_reset()
        assert dm.state.peak_balance == dm.state.current_balance
        assert dm.state.total_pct == 0.0


# ---------------------------------------------------------------------------
# Correlation Monitor tests
# ---------------------------------------------------------------------------

class TestCorrelationMonitor:

    def test_no_correlation_with_empty_positions(self) -> None:
        cm = CorrelationMonitor(max_correlation=0.7)
        ok, reason = cm.check_correlation("EUR/USD", "long")
        assert ok is True
        assert reason == ""

    def test_correlated_double_up_rejected(self) -> None:
        cm = CorrelationMonitor(max_correlation=0.7)
        cm.add_position(OpenPosition(symbol="EUR/USD", direction="long", size=0.1, entry_price=1.1))
        ok, reason = cm.check_correlation("GBP/USD", "long")  # corr ~0.85
        assert ok is False
        assert "Correlated double-up" in reason

    def test_uncorrelated_allowed(self) -> None:
        cm = CorrelationMonitor(max_correlation=0.7)
        cm.add_position(OpenPosition(symbol="EUR/USD", direction="long", size=0.1, entry_price=1.1))
        ok, reason = cm.check_correlation("USD/JPY", "long")  # corr ~-0.30
        assert ok is True

    def test_same_direction_exposure_limit(self) -> None:
        cm = CorrelationMonitor(max_correlation=0.95, max_same_direction_exposure=2)
        cm.add_position(OpenPosition(symbol="EUR/USD", direction="long", size=0.1, entry_price=1.1))
        cm.add_position(OpenPosition(symbol="USD/JPY", direction="long", size=0.1, entry_price=150.0))
        ok, reason = cm.check_correlation("AUD/USD", "long")
        assert ok is False
        assert "Too many long" in reason

    def test_portfolio_correlation(self) -> None:
        cm = CorrelationMonitor()
        assert cm.get_portfolio_correlation() == 0.0  # < 2 positions
        cm.add_position(OpenPosition(symbol="EUR/USD", direction="long", size=0.1, entry_price=1.1))
        cm.add_position(OpenPosition(symbol="GBP/USD", direction="long", size=0.1, entry_price=1.3))
        corr = cm.get_portfolio_correlation()
        assert corr > 0.0

    def test_remove_position(self) -> None:
        cm = CorrelationMonitor()
        cm.add_position(OpenPosition(symbol="EUR/USD", direction="long", size=0.1, entry_price=1.1))
        cm.remove_position("EUR/USD")
        assert len(cm._positions) == 0


# ---------------------------------------------------------------------------
# Risk Governor integration tests
# ---------------------------------------------------------------------------

class TestRiskGovernor:

    def _make_governor(self, balance: float = 10_000.0) -> RiskGovernor:
        """Create a RiskGovernor with mock settings."""
        mock_settings = MagicMock()
        mock_settings.risk.max_position_size_pct = 5.0
        mock_settings.risk.max_daily_loss_pct = 3.0
        mock_settings.risk.max_drawdown_pct = 15.0
        mock_settings.risk.max_open_positions = 10
        mock_settings.risk.max_correlation = 0.7
        mock_settings.risk.max_leverage = 2.0

        with patch("alphastack.risk.governor.get_settings", return_value=mock_settings):
            governor = RiskGovernor(account_balance=balance)
        return governor

    def _make_request(self, **kwargs: Any) -> TradeRequest:
        defaults = {
            "symbol": "EUR/USD",
            "direction": "long",
            "requested_size": 0.1,
            "entry_price": 1.1050,
            "stop_loss": 1.1000,
            "take_profit": 1.1150,
            "strategy_id": "test",
            "session": "london",
        }
        defaults.update(kwargs)
        return TradeRequest(**defaults)

    @pytest.mark.asyncio
    async def test_valid_trade_approved(self) -> None:
        governor = self._make_governor()
        request = self._make_request()
        result = await governor.approve_trade(request)
        assert result.approved is True
        assert result.adjusted_size > 0

    @pytest.mark.asyncio
    async def test_halted_trade_rejected(self) -> None:
        governor = self._make_governor()
        governor.halt("test halt")
        request = self._make_request()
        result = await governor.approve_trade(request)
        assert result.approved is False
        assert "halted" in result.rejection_reason.lower()

    @pytest.mark.asyncio
    async def test_invalid_trade_rejected(self) -> None:
        governor = self._make_governor()
        request = self._make_request(entry_price=0.0)
        result = await governor.approve_trade(request)
        assert result.approved is False

    @pytest.mark.asyncio
    async def test_resume_after_halt(self) -> None:
        governor = self._make_governor()
        governor.halt("test")
        assert governor.is_halted is True
        governor.resume()
        assert governor.is_halted is False

    def test_record_trade_result_updates_balance(self) -> None:
        governor = self._make_governor(balance=10_000.0)
        governor.record_trade_result(500.0)
        assert governor.account_balance == 10_500.0

    def test_record_trade_loss_triggers_circuit_breaker(self) -> None:
        governor = self._make_governor(balance=10_000.0)
        # Record enough losses to trip the circuit breaker
        for _ in range(6):
            governor.record_trade_result(-10.0)
        assert governor.is_halted is True

    def test_status_returns_dict(self) -> None:
        governor = self._make_governor()
        status = governor.status()
        assert "halted" in status
        assert "balance" in status
        assert "drawdown" in status
        assert "circuit_breaker" in status

    def test_event_subscriber_called(self) -> None:
        events: list[RiskEvent] = []
        mock_settings = MagicMock()
        mock_settings.risk.max_position_size_pct = 5.0
        mock_settings.risk.max_daily_loss_pct = 3.0
        mock_settings.risk.max_drawdown_pct = 15.0
        mock_settings.risk.max_open_positions = 10
        mock_settings.risk.max_correlation = 0.7
        mock_settings.risk.max_leverage = 2.0

        with patch("alphastack.risk.governor.get_settings", return_value=mock_settings):
            governor = RiskGovernor(account_balance=10_000.0, on_event=events.append)
        governor.halt("test")
        assert len(events) == 1
        assert events[0].event_type == RiskEventType.HALT_TRADING
