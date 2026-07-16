"""Unit tests for forex utility functions.

Tests cover pip calculation, position sizing, margin calculation,
spread cost, and swap cost for major/minor/exotic currency pairs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import pytest


# ---------------------------------------------------------------------------
# Inline reference implementations (to be moved to forex_utils.py later)
# ---------------------------------------------------------------------------

class PairType(str, Enum):
    MAJOR = "major"
    MINOR = "minor"
    EXOTIC = "exotic"
    METAL = "metal"


@dataclass
class ForexSymbol:
    """Forex symbol metadata."""
    base: str
    quote: str
    pair_type: PairType
    pip_digits: int          # 4 for most, 2 for JPY
    contract_size: float     # 100_000 for standard lot
    min_lot: float = 0.01
    max_lot: float = 100.0
    lot_step: float = 0.01

    @property
    def pip_size(self) -> float:
        return 10 ** -self.pip_digits

    def pips_between(self, price1: float, price2: float) -> float:
        return abs(price1 - price2) / self.pip_size

    def pip_value_per_lot(self, account_currency: str = "USD", quote_rate: float = 1.0) -> float:
        """Pip value per standard lot in account currency.

        For pairs where quote == account currency: pip_size * contract_size.
        For crosses: multiply by the quote-to-account conversion rate.
        """
        base_value = self.pip_size * self.contract_size
        if self.quote == account_currency:
            return base_value
        return base_value * quote_rate


# Pre-defined symbol specs
FOREX_SYMBOLS: dict[str, ForexSymbol] = {
    "EUR/USD": ForexSymbol("EUR", "USD", PairType.MAJOR, 4, 100_000),
    "GBP/USD": ForexSymbol("GBP", "USD", PairType.MAJOR, 4, 100_000),
    "USD/JPY": ForexSymbol("USD", "JPY", PairType.MAJOR, 2, 100_000),
    "USD/CHF": ForexSymbol("USD", "CHF", PairType.MAJOR, 4, 100_000),
    "AUD/USD": ForexSymbol("AUD", "USD", PairType.MAJOR, 4, 100_000),
    "USD/CAD": ForexSymbol("USD", "CAD", PairType.MAJOR, 4, 100_000),
    "NZD/USD": ForexSymbol("NZD", "USD", PairType.MAJOR, 4, 100_000),
    "EUR/GBP": ForexSymbol("EUR", "GBP", PairType.MINOR, 4, 100_000),
    "EUR/JPY": ForexSymbol("EUR", "JPY", PairType.MINOR, 2, 100_000),
    "GBP/JPY": ForexSymbol("GBP", "JPY", PairType.MINOR, 2, 100_000),
    "USD/TRY": ForexSymbol("USD", "TRY", PairType.EXOTIC, 4, 100_000),
    "XAU/USD": ForexSymbol("XAU", "USD", PairType.METAL, 2, 100),
}


# ---------------------------------------------------------------------------
# Helper functions under test
# ---------------------------------------------------------------------------

def calculate_pip_size(symbol: str) -> float:
    """Return the pip size for a given symbol."""
    sym = FOREX_SYMBOLS.get(symbol)
    if sym is None:
        raise ValueError(f"Unknown symbol: {symbol}")
    return sym.pip_size


def calculate_position_size(
    account_balance: float,
    risk_pct: float,
    stop_loss_pips: float,
    pip_value_per_lot: float,
    lot_step: float = 0.01,
    min_lot: float = 0.01,
    max_lot: float = 100.0,
) -> float:
    """Calculate position size in lots based on risk percentage.

    lot_size = (balance * risk_pct / 100) / (stop_loss_pips * pip_value_per_lot)
    """
    if stop_loss_pips <= 0 or pip_value_per_lot <= 0:
        raise ValueError("stop_loss_pips and pip_value_per_lot must be positive")
    risk_amount = account_balance * risk_pct / 100.0
    raw_lots = risk_amount / (stop_loss_pips * pip_value_per_lot)
    # Round down to lot_step
    stepped = math.floor(raw_lots / lot_step) * lot_step
    return max(min_lot, min(stepped, max_lot))


def calculate_margin(
    lots: float,
    contract_size: float,
    price: float,
    leverage: float,
) -> float:
    """Required margin = (lots * contract_size * price) / leverage."""
    if leverage <= 0:
        raise ValueError("Leverage must be positive")
    return (lots * contract_size * price) / leverage


def calculate_spread_cost(
    spread_pips: float,
    pip_value_per_lot: float,
    lots: float,
) -> float:
    """Spread cost in account currency = spread_pips * pip_value * lots."""
    return spread_pips * pip_value_per_lot * lots


def calculate_swap_cost(
    swap_rate_per_day: float,
    lots: float,
    days_held: int,
) -> float:
    """Swap cost = swap_rate * lots * days.  Positive = earned, negative = paid."""
    return swap_rate_per_day * lots * days_held


# ===========================================================================
# TESTS — Pip Calculation
# ===========================================================================

class TestPipCalculation:

    def test_eurusd_pip_size(self):
        assert calculate_pip_size("EUR/USD") == pytest.approx(0.0001)

    def test_gbpusd_pip_size(self):
        assert calculate_pip_size("GBP/USD") == pytest.approx(0.0001)

    def test_usdjpy_pip_size(self):
        """JPY pairs use 2nd decimal place → pip = 0.01."""
        assert calculate_pip_size("USD/JPY") == pytest.approx(0.01)

    def test_eurjpy_pip_size(self):
        """Cross JPY pair also uses 0.01."""
        assert calculate_pip_size("EUR/JPY") == pytest.approx(0.01)

    def test_gbpjpy_pip_size(self):
        assert calculate_pip_size("GBP/JPY") == pytest.approx(0.01)

    def test_audusd_pip_size(self):
        assert calculate_pip_size("AUD/USD") == pytest.approx(0.0001)

    def test_usdchf_pip_size(self):
        assert calculate_pip_size("USD/CHF") == pytest.approx(0.0001)

    def test_unknown_symbol_raises(self):
        with pytest.raises(ValueError, match="Unknown symbol"):
            calculate_pip_size("XYZ/ABC")

    def test_xauusd_pip_size(self):
        """Gold uses 2 decimal places → pip = 0.01."""
        assert calculate_pip_size("XAU/USD") == pytest.approx(0.01)

    def test_pips_between_eurusd(self):
        sym = FOREX_SYMBOLS["EUR/USD"]
        assert sym.pips_between(1.1000, 1.1050) == pytest.approx(50.0)

    def test_pips_between_usdjpy(self):
        sym = FOREX_SYMBOLS["USD/JPY"]
        assert sym.pips_between(150.00, 150.50) == pytest.approx(50.0)

    def test_pips_between_same_price(self):
        sym = FOREX_SYMBOLS["EUR/USD"]
        assert sym.pips_between(1.1000, 1.1000) == pytest.approx(0.0)


# ===========================================================================
# TESTS — Pip Value Per Lot
# ===========================================================================

class TestPipValuePerLot:

    def test_eurusd_pip_value(self):
        """EUR/USD: pip_size(0.0001) * contract(100_000) = $10."""
        sym = FOREX_SYMBOLS["EUR/USD"]
        assert sym.pip_value_per_lot() == pytest.approx(10.0)

    def test_gbpusd_pip_value(self):
        sym = FOREX_SYMBOLS["GBP/USD"]
        assert sym.pip_value_per_lot() == pytest.approx(10.0)

    def test_usdjpy_pip_value_usd_quote(self):
        """USD/JPY with quote_rate to convert JPY→USD at 150."""
        sym = FOREX_SYMBOLS["USD/JPY"]
        # pip_size(0.01) * contract(100_000) = 1000 JPY → / 150 = ~$6.67
        val = sym.pip_value_per_lot(account_currency="USD", quote_rate=1.0 / 150.0)
        assert val == pytest.approx(1000.0 / 150.0, rel=1e-4)

    def test_eurgbp_pip_value_with_conversion(self):
        """EUR/GBP cross: needs GBP/USD rate to convert to USD."""
        sym = FOREX_SYMBOLS["EUR/GBP"]
        # pip_size(0.0001) * contract(100_000) = 10 GBP → * 1.27 USD/GBP = $12.70
        val = sym.pip_value_per_lot(account_currency="USD", quote_rate=1.27)
        assert val == pytest.approx(10.0 * 1.27, rel=1e-4)

    def test_xauusd_pip_value(self):
        """XAU/USD: pip_size(0.01) * contract(100) = $1."""
        sym = FOREX_SYMBOLS["XAU/USD"]
        assert sym.pip_value_per_lot() == pytest.approx(1.0)


# ===========================================================================
# TESTS — Position Sizing
# ===========================================================================

class TestPositionSizing:

    def test_basic_sizing(self):
        """$10,000 account, 1% risk, 50 pip SL, $10/pip → 0.20 lots."""
        lots = calculate_position_size(
            account_balance=10_000,
            risk_pct=1.0,
            stop_loss_pips=50,
            pip_value_per_lot=10.0,
        )
        assert lots == pytest.approx(0.20)

    def test_small_account(self):
        """$1,000 account, 2% risk, 30 pip SL → 0.06 lots."""
        lots = calculate_position_size(
            account_balance=1_000,
            risk_pct=2.0,
            stop_loss_pips=30,
            pip_value_per_lot=10.0,
        )
        assert lots == pytest.approx(0.06)

    def test_large_sl_reduces_size(self):
        """Wide stop loss → smaller position to keep risk constant."""
        lots = calculate_position_size(
            account_balance=10_000,
            risk_pct=1.0,
            stop_loss_pips=100,
            pip_value_per_lot=10.0,
        )
        assert lots == pytest.approx(0.10)

    def test_min_lot_clamp(self):
        """If calculated size < min_lot, clamp to min_lot."""
        lots = calculate_position_size(
            account_balance=100,
            risk_pct=1.0,
            stop_loss_pips=50,
            pip_value_per_lot=10.0,
            min_lot=0.01,
        )
        assert lots == pytest.approx(0.01)

    def test_max_lot_clamp(self):
        """If calculated size > max_lot, clamp to max_lot."""
        lots = calculate_position_size(
            account_balance=1_000_000,
            risk_pct=2.0,
            stop_loss_pips=10,
            pip_value_per_lot=10.0,
            max_lot=5.0,
        )
        assert lots == pytest.approx(5.0)

    def test_invalid_stop_loss(self):
        with pytest.raises(ValueError):
            calculate_position_size(10_000, 1.0, 0, 10.0)

    def test_invalid_pip_value(self):
        with pytest.raises(ValueError):
            calculate_position_size(10_000, 1.0, 50, 0.0)

    def test_lot_step_rounding(self):
        """Size should round down to nearest lot_step."""
        lots = calculate_position_size(
            account_balance=10_000,
            risk_pct=1.0,
            stop_loss_pips=37,
            pip_value_per_lot=10.0,
            lot_step=0.01,
        )
        # raw = 100 / 370 ≈ 0.2702 → floor to 0.27
        assert lots == pytest.approx(0.27)
        assert lots % 0.01 == pytest.approx(0.0, abs=1e-9)


# ===========================================================================
# TESTS — Margin Calculation
# ===========================================================================

class TestMarginCalculation:

    def test_eurusd_margin_100x(self):
        """1 lot EUR/USD at 1.1050, 1:100 leverage → $1,105 margin."""
        margin = calculate_margin(lots=1.0, contract_size=100_000, price=1.1050, leverage=100)
        assert margin == pytest.approx(1_105.0)

    def test_micro_lot_margin(self):
        """0.01 lot EUR/USD at 1.1050, 1:100 → $11.05 margin."""
        margin = calculate_margin(lots=0.01, contract_size=100_000, price=1.1050, leverage=100)
        assert margin == pytest.approx(11.05)

    def test_usdjpy_margin(self):
        """1 lot USD/JPY at 150.00, 1:100 → 100,000 × 150 / 100 = $150,000."""
        margin = calculate_margin(lots=1.0, contract_size=100_000, price=150.00, leverage=100)
        assert margin == pytest.approx(150_000.0)

    def test_low_leverage_increases_margin(self):
        """1:30 leverage (EU regulation) → higher margin requirement."""
        margin_100 = calculate_margin(1.0, 100_000, 1.1000, 100)
        margin_30 = calculate_margin(1.0, 100_000, 1.1000, 30)
        assert margin_30 > margin_100
        assert margin_30 == pytest.approx(margin_100 * 100 / 30)

    def test_xauusd_margin(self):
        """1 lot XAU/USD at 2350.00, 1:100, contract_size=100."""
        margin = calculate_margin(1.0, 100, 2350.00, 100)
        assert margin == pytest.approx(2_350.0)

    def test_zero_leverage_raises(self):
        with pytest.raises(ValueError):
            calculate_margin(1.0, 100_000, 1.1000, 0)


# ===========================================================================
# TESTS — Spread Cost
# ===========================================================================

class TestSpreadCost:

    def test_eurusd_spread_cost(self):
        """1.5 pip spread, 1 lot EUR/USD → $15."""
        cost = calculate_spread_cost(spread_pips=1.5, pip_value_per_lot=10.0, lots=1.0)
        assert cost == pytest.approx(15.0)

    def test_tight_spread_ecn(self):
        """0.2 pip raw spread on ECN, 1 lot → $2."""
        cost = calculate_spread_cost(spread_pips=0.2, pip_value_per_lot=10.0, lots=1.0)
        assert cost == pytest.approx(2.0)

    def test_micro_lot_spread(self):
        """1.5 pip spread, 0.01 lot → $0.15."""
        cost = calculate_spread_cost(spread_pips=1.5, pip_value_per_lot=10.0, lots=0.01)
        assert cost == pytest.approx(0.15)

    def test_usdjpy_spread_cost(self):
        """1.2 pip spread on USD/JPY, 1 lot, pip value ~$6.67."""
        cost = calculate_spread_cost(spread_pips=1.2, pip_value_per_lot=6.67, lots=1.0)
        assert cost == pytest.approx(8.004)

    def test_spread_cost_scales_linearly(self):
        cost_1 = calculate_spread_cost(1.5, 10.0, 1.0)
        cost_2 = calculate_spread_cost(1.5, 10.0, 2.0)
        assert cost_2 == pytest.approx(cost_1 * 2)

    def test_zero_spread(self):
        cost = calculate_spread_cost(0.0, 10.0, 1.0)
        assert cost == pytest.approx(0.0)


# ===========================================================================
# TESTS — Swap Cost
# ===========================================================================

class TestSwapCost:

    def test_positive_swap_earned(self):
        """Positive swap rate → trader earns overnight."""
        cost = calculate_swap_cost(swap_rate_per_day=3.50, lots=1.0, days_held=1)
        assert cost == pytest.approx(3.50)

    def test_negative_swap_paid(self):
        """Negative swap rate → trader pays overnight."""
        cost = calculate_swap_cost(swap_rate_per_day=-2.00, lots=1.0, days_held=1)
        assert cost == pytest.approx(-2.00)

    def test_triple_swap_wednesday(self):
        """Wednesday triple swap: 3 days charged on one day."""
        daily = -2.00
        cost = calculate_swap_cost(daily, lots=1.0, days_held=3)
        assert cost == pytest.approx(-6.00)

    def test_week_held(self):
        """5 days held at $3.50/day/lot → $17.50."""
        cost = calculate_swap_cost(3.50, 1.0, 5)
        assert cost == pytest.approx(17.50)

    def test_swap_scales_with_lots(self):
        cost_1 = calculate_swap_cost(-2.0, 1.0, 1)
        cost_5 = calculate_swap_cost(-2.0, 5.0, 1)
        assert cost_5 == pytest.approx(cost_1 * 5)

    def test_zero_swap(self):
        cost = calculate_swap_cost(0.0, 1.0, 30)
        assert cost == pytest.approx(0.0)

    def test_long_position_carry_positive(self):
        """Buy AUD/USD (high rate) vs USD (lower rate) → positive swap."""
        # AUD rate ~4.35%, USD rate ~5.25% → actually negative for long AUD
        # But let's test the math with a positive rate
        cost = calculate_swap_cost(1.20, 0.5, 30)
        assert cost == pytest.approx(18.0)
