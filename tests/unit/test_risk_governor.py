"""Unit tests for the Risk Governor and all risk sub-systems."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from alphastack.risk.circuit_breaker import BreakerType, CircuitBreaker
from alphastack.risk.correlation import CorrelationMonitor, OpenPosition
from alphastack.risk.drawdown import DrawdownManager
from alphastack.risk.exposure import ExposureManager, PositionExposure
from alphastack.risk.governor import TradeApproval, RiskGovernor, RiskEvent, RiskEventType, TradeApproval, TradeRequest
from alphastack.risk.position_sizer import PositionSizer, SizingMethod, SizingRequest
from alphastack.risk.validators import TradeValidator, ValidationResult


# ---------------------------------------------------------------------------
# TradeRequest helper
# ---------------------------------------------------------------------------

def _trade_request(**overrides) -> TradeRequest:
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
    defaults.update(overrides)
    return TradeRequest(**defaults)


# ===========================================================================
# Drawdown Manager
# ===========================================================================

class TestDrawdownManager:
    def test_initial_state(self):
        dm = DrawdownManager(account_balance=1000.0)
        assert dm.state.current_balance == 1000.0
        assert dm.state.peak_balance == 1000.0
        assert dm.is_breach() is False

    def test_pnl_updates_balance(self):
        dm = DrawdownManager(account_balance=1000.0)
        dm.record_pnl(100.0)
        assert dm.state.current_balance == 1100.0
        assert dm.state.peak_balance == 1100.0

    def test_drawdown_from_peak(self):
        dm = DrawdownManager(account_balance=1000.0)
        dm.record_pnl(200.0)  # peak: 1200
        dm.record_pnl(-400.0)  # now: 800
        assert dm.state.current_balance == 800.0
        assert dm.state.peak_balance == 1200.0
        assert dm.state.total_drawdown == 400.0
        assert dm.state.total_pct > 0

    def test_daily_loss_breach(self):
        dm = DrawdownManager(account_balance=1000.0, max_daily_pct=3.0)
        dm.record_pnl(-35.0)  # 3.5% daily loss
        assert dm.is_breach() is True
        details = dm.breach_details()
        assert any("Daily" in d for d in details)

    def test_total_drawdown_breach(self):
        dm = DrawdownManager(account_balance=1000.0, max_total_pct=15.0)
        dm.record_pnl(500.0)  # peak: 1500
        dm.record_pnl(-300.0)  # now: 1200, DD = 20%
        assert dm.is_breach() is True

    def test_risk_multiplier_de_escalation(self):
        dm = DrawdownManager(account_balance=1000.0, max_daily_pct=10.0, max_total_pct=15.0)
        assert dm.risk_multiplier() == 1.0
        dm.record_pnl(-25.0)  # 2.5% daily DD
        assert dm.risk_multiplier() < 1.0

    def test_daily_reset(self):
        dm = DrawdownManager(account_balance=1000.0)
        dm.record_pnl(-20.0)
        assert dm.state.daily_pnl == -20.0
        dm.reset_daily()
        assert dm.state.daily_pnl == 0.0
        assert dm.state.daily_pct == 0.0

    def test_full_reset(self):
        dm = DrawdownManager(account_balance=1000.0)
        dm.record_pnl(-100.0)
        dm.full_reset()
        assert dm.state.current_balance == 900.0
        assert dm.state.peak_balance == 900.0
        assert dm.state.total_drawdown == 0.0

    def test_status_returns_dict(self):
        dm = DrawdownManager(account_balance=1000.0)
        status = dm.status()
        assert "current_balance" in status
        assert "risk_multiplier" in status


# ===========================================================================
# Circuit Breaker
# ===========================================================================

class TestCircuitBreaker:
    def test_initial_not_tripped(self):
        cb = CircuitBreaker(max_daily_loss_pct=3.0, account_balance=1000.0)
        assert cb.is_tripped is False

    def test_daily_loss_trips(self):
        cb = CircuitBreaker(max_daily_loss_pct=3.0, account_balance=1000.0)
        cb.record_loss(-35.0)  # 3.5%
        assert cb.is_tripped is True
        assert "Daily loss" in cb.trip_reason

    def test_consecutive_losses_trip(self):
        cb = CircuitBreaker(max_consecutive_losses=3, account_balance=1000.0)
        cb.record_loss(-1.0)
        cb.record_loss(-1.0)
        cb.record_loss(-1.0)
        assert cb.is_tripped is True
        assert "Consecutive" in cb.trip_reason

    def test_win_resets_consecutive(self):
        cb = CircuitBreaker(max_consecutive_losses=5, account_balance=1000.0)
        cb.record_loss(-1.0)
        cb.record_loss(-1.0)
        cb.record_loss(5.0)  # win
        assert cb.consecutive_losses == 0

    def test_cooldown_prevents_reset(self):
        cb = CircuitBreaker(max_daily_loss_pct=3.0, account_balance=1000.0, cooldown_minutes=30)
        cb.record_loss(-35.0)
        assert cb.reset() is False  # still in cooldown

    def test_force_reset(self):
        cb = CircuitBreaker(max_daily_loss_pct=3.0, account_balance=1000.0)
        cb.record_loss(-35.0)
        assert cb.is_tripped is True
        cb.force_reset()
        assert cb.is_tripped is False

    def test_daily_reset(self):
        cb = CircuitBreaker(max_daily_loss_pct=3.0, account_balance=1000.0)
        cb.record_loss(-20.0)
        cb.reset_daily()
        assert cb.daily_pnl == 0.0

    def test_state_snapshot(self):
        cb = CircuitBreaker(account_balance=1000.0)
        state = cb.state
        assert state.tripped is False
        assert state.daily_pnl == 0.0

    def test_status_returns_dict(self):
        cb = CircuitBreaker(account_balance=1000.0)
        status = cb.status()
        assert "tripped" in status


# ===========================================================================
# Position Sizer
# ===========================================================================

class TestPositionSizer:
    def test_fixed_risk_sizing(self):
        ps = PositionSizer(account_balance=10000.0, default_risk_pct=1.0)
        result = ps.size_position(SizingRequest(
            symbol="EUR/USD",
            direction="long",
            entry_price=1.1050,
            stop_loss=1.1000,
            account_balance=10000.0,
        ))
        assert result.max_size > 0
        assert result.risk_amount > 0

    def test_tighter_stop_larger_size(self):
        ps = PositionSizer(account_balance=10000.0)
        wide = ps.size_position(SizingRequest(
            symbol="EUR/USD", direction="long",
            entry_price=1.1050, stop_loss=1.1000, account_balance=10000.0,
        ))
        tight = ps.size_position(SizingRequest(
            symbol="EUR/USD", direction="long",
            entry_price=1.1050, stop_loss=1.1040, account_balance=10000.0,
        ))
        # Tighter stop should give larger size for same risk %
        assert tight.max_size >= wide.max_size

    def test_zero_stop_distance_gives_zero(self):
        ps = PositionSizer(account_balance=10000.0)
        result = ps.size_position(SizingRequest(
            symbol="EUR/USD", direction="long",
            entry_price=1.1050, stop_loss=1.1050, account_balance=10000.0,
        ))
        assert result.max_size == 0.0

    def test_kelly_sizing(self):
        ps = PositionSizer(account_balance=10000.0)
        result = ps.size_position(SizingRequest(
            symbol="EUR/USD", direction="long",
            entry_price=1.1050, stop_loss=1.1000, account_balance=10000.0,
            method=SizingMethod.KELLY,
            win_rate=0.6, avg_win=2.0, avg_loss=1.0,
        ))
        assert result.max_size > 0

    def test_kelly_negative_edge(self):
        ps = PositionSizer(account_balance=10000.0)
        result = ps.size_position(SizingRequest(
            symbol="EUR/USD", direction="long",
            entry_price=1.1050, stop_loss=1.1000, account_balance=10000.0,
            method=SizingMethod.KELLY,
            win_rate=0.3, avg_win=1.0, avg_loss=2.0,
        ))
        # Negative edge → min size
        assert result.max_size > 0

    def test_drawdown_de_escalation(self):
        ps = PositionSizer(account_balance=10000.0)
        normal = ps.size_position(SizingRequest(
            symbol="EUR/USD", direction="long",
            entry_price=1.1050, stop_loss=1.1000, account_balance=10000.0,
            daily_drawdown_pct=0.0,
        ))
        stressed = ps.size_position(SizingRequest(
            symbol="EUR/USD", direction="long",
            entry_price=1.1050, stop_loss=1.1000, account_balance=10000.0,
            daily_drawdown_pct=6.0,
        ))
        assert stressed.max_size <= normal.max_size

    def test_update_balance(self):
        ps = PositionSizer(account_balance=10000.0)
        ps.update_balance(5000.0)
        result = ps.size_position(SizingRequest(
            symbol="EUR/USD", direction="long",
            entry_price=1.1050, stop_loss=1.1000, account_balance=5000.0,
        ))
        assert result.risk_amount > 0


# ===========================================================================
# Correlation Monitor
# ===========================================================================

class TestCorrelationMonitor:
    def test_no_positions_allows_anything(self):
        cm = CorrelationMonitor(max_correlation=0.7)
        ok, reason = cm.check_correlation("EUR/USD", "long")
        assert ok is True

    def test_correlated_double_up_rejected(self):
        cm = CorrelationMonitor(max_correlation=0.7)
        cm.add_position(OpenPosition(symbol="EUR/USD", direction="long", size=0.1, entry_price=1.1))
        ok, reason = cm.check_correlation("GBP/USD", "long")  # corr ~0.85
        assert ok is False
        assert "Correlated" in reason

    def test_uncorrelated_allowed(self):
        cm = CorrelationMonitor(max_correlation=0.7)
        cm.add_position(OpenPosition(symbol="EUR/USD", direction="long", size=0.1, entry_price=1.1))
        ok, reason = cm.check_correlation("USD/JPY", "short")  # low corr
        assert ok is True

    def test_same_direction_exposure_limit(self):
        cm = CorrelationMonitor(max_correlation=0.95, max_same_direction_exposure=2)
        cm.add_position(OpenPosition(symbol="EUR/USD", direction="long", size=0.1, entry_price=1.1))
        cm.add_position(OpenPosition(symbol="USD/JPY", direction="long", size=0.1, entry_price=150.0))
        ok, reason = cm.check_correlation("AUD/USD", "long")
        assert ok is False
        assert "Too many" in reason

    def test_remove_position(self):
        cm = CorrelationMonitor(max_correlation=0.7)
        cm.add_position(OpenPosition(symbol="EUR/USD", direction="long", size=0.1, entry_price=1.1))
        cm.remove_position("EUR/USD")
        ok, _ = cm.check_correlation("GBP/USD", "long")
        assert ok is True

    def test_portfolio_correlation_empty(self):
        cm = CorrelationMonitor()
        assert cm.get_portfolio_correlation() == 0.0

    def test_portfolio_correlation_with_positions(self):
        cm = CorrelationMonitor()
        cm.add_position(OpenPosition(symbol="EUR/USD", direction="long", size=0.1, entry_price=1.1))
        cm.add_position(OpenPosition(symbol="GBP/USD", direction="long", size=0.1, entry_price=1.3))
        corr = cm.get_portfolio_correlation()
        assert corr > 0

    def test_update_correlation(self):
        cm = CorrelationMonitor()
        cm.update_correlation("CUSTOM/A", "CUSTOM/B", 0.95)
        cm.add_position(OpenPosition(symbol="CUSTOM/A", direction="long", size=0.1, entry_price=1.0))
        ok, reason = cm.check_correlation("CUSTOM/B", "long")
        assert ok is False


# ===========================================================================
# Exposure Manager
# ===========================================================================

class TestExposureManager:
    def test_add_within_limits(self):
        em = ExposureManager(max_open_positions=5)
        ok, _ = em.check_add_position("EUR/USD", "long", 0.1, 1.1, 10000.0)
        assert ok is True

    def test_max_positions_enforced(self):
        em = ExposureManager(max_open_positions=2)
        em.add_position(PositionExposure(symbol="A", direction="long", size=0.1, entry_price=1.0))
        em.add_position(PositionExposure(symbol="B", direction="long", size=0.1, entry_price=1.0))
        ok, reason = em.check_add_position("C", "long", 0.1, 1.0, 10000.0)
        assert ok is False
        assert "Max open positions" in reason

    def test_per_pair_exposure(self):
        em = ExposureManager(max_per_pair_pct=20.0)
        em.add_position(PositionExposure(symbol="EUR/USD", direction="long", size=1.0, entry_price=1.1))
        # 1.0 * 1.1 = 1.1, on 10 = 11%, add 1.0 more → 22% > 20%
        ok, reason = em.check_add_position("EUR/USD", "long", 1.0, 1.1, 10.0)
        assert ok is False

    def test_leverage_enforced(self):
        em = ExposureManager(max_leverage=2.0)
        # 10 units * 100 price = 1000 notional, on 1000 balance = 1x
        em.add_position(PositionExposure(symbol="X", direction="long", size=10, entry_price=100))
        ok, reason = em.check_add_position("Y", "long", 10, 100, 1000.0)
        assert ok is False  # total = 2000, leverage = 2x, at limit

    def test_remove_position(self):
        em = ExposureManager(max_open_positions=1)
        em.add_position(PositionExposure(symbol="EUR/USD", direction="long", size=0.1, entry_price=1.1))
        em.remove_position("EUR/USD")
        ok, _ = em.check_add_position("GBP/USD", "long", 0.1, 1.3, 10000.0)
        assert ok is True

    def test_snapshot(self):
        em = ExposureManager()
        em.add_position(PositionExposure(symbol="EUR/USD", direction="long", size=0.1, entry_price=1.1))
        snap = em.get_snapshot(balance=10000.0)
        assert snap.total_positions == 1


# ===========================================================================
# Trade Validator
# ===========================================================================

class TestTradeValidator:
    def test_valid_trade(self, trade_validator):
        req = _trade_request()
        result = trade_validator.validate_pre_trade(req)
        assert result.valid is True
        assert result.errors == []

    def test_zero_entry_price(self, trade_validator):
        req = _trade_request(entry_price=0.0)
        result = trade_validator.validate_pre_trade(req)
        assert result.valid is False

    def test_negative_stop_loss(self, trade_validator):
        req = _trade_request(stop_loss=-1.0)
        result = trade_validator.validate_pre_trade(req)
        assert result.valid is False

    def test_long_sl_above_entry(self, trade_validator):
        req = _trade_request(entry_price=1.1000, stop_loss=1.1100)
        result = trade_validator.validate_pre_trade(req)
        assert result.valid is False

    def test_short_sl_below_entry(self, trade_validator):
        req = _trade_request(direction="short", entry_price=1.1000, stop_loss=1.0900)
        result = trade_validator.validate_pre_trade(req)
        assert result.valid is False

    def test_invalid_direction(self, trade_validator):
        req = _trade_request(direction="sideways")
        result = trade_validator.validate_pre_trade(req)
        assert result.valid is False

    def test_zero_size(self, trade_validator):
        req = _trade_request(requested_size=0.0)
        result = trade_validator.validate_pre_trade(req)
        assert result.valid is False

    def test_empty_symbol(self, trade_validator):
        req = _trade_request(symbol="")
        result = trade_validator.validate_pre_trade(req)
        assert result.valid is False

    def test_post_trade_slippage(self, trade_validator):
        result = trade_validator.validate_post_trade(
            expected_price=1.1000, fill_price=1.1020,
            expected_size=0.1, fill_size=0.1, direction="long",
        )
        assert result.valid is True  # 0.18% slippage, within 1% limit

    def test_order_modify_sl_widening_warning(self, trade_validator):
        result = trade_validator.validate_order_modify(
            current_sl=1.0950, new_sl=1.0900,
            current_tp=1.1100, new_tp=1.1100,
            entry_price=1.1000, direction="long",
        )
        assert any("widening" in w.lower() or "against" in w.lower() for w in result.warnings)


# ===========================================================================
# Risk Governor (integration of all sub-systems)
# ===========================================================================

class TestRiskGovernor:
    def _governor(self, **kwargs) -> RiskGovernor:
        return RiskGovernor(account_balance=10000.0, **kwargs)

    @pytest.mark.asyncio
    async def test_approve_valid_trade(self):
        gov = self._governor()
        result = await gov.approve_trade(_trade_request())
        assert result.approved is True
        assert result.adjusted_size > 0

    @pytest.mark.asyncio
    async def test_reject_when_halted(self):
        gov = self._governor()
        gov.halt("manual test")
        result = await gov.approve_trade(_trade_request())
        assert result.approved is False
        assert "halted" in result.rejection_reason.lower()

    @pytest.mark.asyncio
    async def test_reject_circuit_breaker(self):
        gov = self._governor()
        # Trip the circuit breaker via consecutive losses
        for _ in range(6):
            gov.record_trade_result(-50.0)
        result = await gov.approve_trade(_trade_request())
        assert result.approved is False

    @pytest.mark.asyncio
    async def test_reject_drawdown_breach(self):
        gov = self._governor()
        # Push into drawdown breach
        gov.update_balance(10000.0)
        gov.record_trade_result(2000.0)  # peak: 12000
        gov.record_trade_result(-2500.0)  # now: 9500, DD = 20.8% > 15%
        result = await gov.approve_trade(_trade_request())
        assert result.approved is False

    @pytest.mark.asyncio
    async def test_position_sizing_may_reduce(self):
        gov = self._governor()
        # Request a very large size
        req = _trade_request(requested_size=100.0)
        result = await gov.approve_trade(req)
        assert result.approved is True
        assert result.adjusted_size <= 100.0

    @pytest.mark.asyncio
    async def test_resume_after_halt(self):
        gov = self._governor()
        gov.halt("test")
        assert gov.is_halted is True
        gov.resume()
        assert gov.is_halted is False

    @pytest.mark.asyncio
    async def test_events_published(self):
        events: list[RiskEvent] = []
        gov = self._governor(on_event=lambda e: events.append(e))
        await gov.approve_trade(_trade_request())
        assert any(e.event_type == RiskEventType.TRADE_APPROVED for e in events)

    def test_status_dict(self):
        gov = self._governor()
        status = gov.status()
        assert "halted" in status
        assert "drawdown" in status
        assert "circuit_breaker" in status

    @pytest.mark.asyncio
    async def test_update_balance(self):
        gov = self._governor()
        gov.update_balance(5000.0)
        assert gov.account_balance == 5000.0
