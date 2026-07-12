"""Unit tests for risk management components."""

from __future__ import annotations

import pytest

from alphastack.risk.exposure import ExposureManager, ExposureSnapshot, PositionExposure
from alphastack.risk.position_sizer import (
    PositionSizer,
    SizingMethod,
    SizingRequest,
    SizingResult,
)
from alphastack.risk.validators import (
    TradeValidator,
    ValidationResult,
    ValidationSeverity,
)


# ---------------------------------------------------------------------------
# Trade Validator tests
# ---------------------------------------------------------------------------

class TestTradeValidator:

    def test_valid_trade_passes(self, trade_validator: TradeValidator) -> None:
        result = trade_validator.validate_pre_trade(
            symbol="EUR/USD",
            direction="long",
            entry_price=1.1050,
            stop_loss=1.1000,
            size=0.1,
        )
        assert result.valid is True
        assert len(result.errors) == 0

    def test_zero_price_rejected(self, trade_validator: TradeValidator) -> None:
        result = trade_validator.validate_pre_trade(
            symbol="EUR/USD",
            direction="long",
            entry_price=0.0,
            stop_loss=1.1000,
            size=0.1,
        )
        assert result.valid is False
        assert any("price" in e.lower() for e in result.errors)

    def test_negative_size_rejected(self, trade_validator: TradeValidator) -> None:
        result = trade_validator.validate_pre_trade(
            symbol="EUR/USD",
            direction="long",
            entry_price=1.1050,
            stop_loss=1.1000,
            size=-0.1,
        )
        assert result.valid is False

    def test_invalid_direction_rejected(self, trade_validator: TradeValidator) -> None:
        result = trade_validator.validate_pre_trade(
            symbol="EUR/USD",
            direction="sideways",
            entry_price=1.1050,
            stop_loss=1.1000,
            size=0.1,
        )
        assert result.valid is False

    def test_long_stop_above_entry_rejected(self, trade_validator: TradeValidator) -> None:
        """Stop loss above entry for a long trade is backwards."""
        result = trade_validator.validate_pre_trade(
            symbol="EUR/USD",
            direction="long",
            entry_price=1.1000,
            stop_loss=1.1100,
            size=0.1,
        )
        assert result.valid is False

    def test_short_stop_below_entry_rejected(self, trade_validator: TradeValidator) -> None:
        """Stop loss below entry for a short trade is backwards."""
        result = trade_validator.validate_pre_trade(
            symbol="EUR/USD",
            direction="short",
            entry_price=1.1000,
            stop_loss=1.0900,
            size=0.1,
        )
        assert result.valid is False

    def test_extreme_price_rejected(self, trade_validator: TradeValidator) -> None:
        result = trade_validator.validate_pre_trade(
            symbol="EUR/USD",
            direction="long",
            entry_price=1e15,
            stop_loss=1.1000,
            size=0.1,
        )
        assert result.valid is False


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
        sizer = PositionSizer()
        request = SizingRequest(
            symbol="EUR/USD",
            direction="long",
            entry_price=1.1050,
            stop_loss=1.1000,
            account_balance=10_000.0,
            method=SizingMethod.FIXED_RISK,
            max_risk_pct=2.0,
        )
        result = sizer.calculate(request)
        assert isinstance(result, SizingResult)
        assert result.risk_amount > 0
        assert result.risk_pct <= 2.0 + 0.01  # small tolerance

    def test_zero_balance_returns_zero(self) -> None:
        sizer = PositionSizer()
        request = SizingRequest(
            symbol="EUR/USD",
            direction="long",
            entry_price=1.1050,
            stop_loss=1.1000,
            account_balance=0.0,
            method=SizingMethod.FIXED_RISK,
        )
        result = sizer.calculate(request)
        assert result.max_size == 0.0

    def test_kelly_sizing(self) -> None:
        sizer = PositionSizer()
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
        result = sizer.calculate(request)
        assert result.max_size > 0
        assert result.method_used == SizingMethod.KELLY

    def test_larger_stop_means_smaller_size(self) -> None:
        """Wider stop → less size for same risk budget."""
        sizer = PositionSizer()
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
        r1 = sizer.calculate(base)
        r2 = sizer.calculate(wide)
        assert r1.max_size > r2.max_size
