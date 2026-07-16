"""Forex utility module – symbol metadata, pip/lot calculations, and standard definitions.

Provides the mathematical foundation for forex position sizing, risk
calculations, and cross-broker symbol normalization used throughout
AlphaStack's forex integration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PairType(str, Enum):
    """Classification of forex instrument types."""
    MAJOR = "major"       # EUR/USD, USD/JPY, etc.
    MINOR = "minor"       # EUR/GBP, AUD/JPY, etc. (crosses, no USD)
    EXOTIC = "exotic"     # USD/TRY, EUR/PLN, etc.
    METAL = "metal"       # XAU/USD, XAG/USD
    INDEX = "index"       # US30, SPX500


# ---------------------------------------------------------------------------
# ForexSymbol dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ForexSymbol:
    """Immutable metadata for a single forex instrument.

    Attributes:
        symbol: Canonical symbol (e.g. ``"EUR/USD"``).
        base_currency: ISO 4217 base currency (e.g. ``"EUR"``).
        quote_currency: ISO 4217 quote currency (e.g. ``"USD"``).
        pip_digits: Number of decimal places that define a pip
            (4 for most pairs, 2 for JPY pairs).
        contract_size: Units of base currency per standard lot
            (100 000 for forex, 100 for gold, etc.).
        min_lot: Minimum tradeable lot size.
        max_lot: Maximum tradeable lot size.
        lot_step: Smallest increment for lot size (broker alignment).
        pair_type: Classification of the instrument.
    """

    symbol: str
    base_currency: str
    quote_currency: str
    pip_digits: int
    contract_size: float = 100_000.0
    min_lot: float = 0.01
    max_lot: float = 100.0
    lot_step: float = 0.01
    pair_type: PairType = PairType.MAJOR

    # -- derived properties -------------------------------------------------

    @property
    def pip_size(self) -> float:
        """The pip size as a float (e.g. 0.0001 for EUR/USD, 0.01 for USD/JPY)."""
        return 10.0 ** -self.pip_digits

    @property
    def pipette_digits(self) -> int:
        """One extra decimal place beyond the pip (fractional pip)."""
        return self.pip_digits + 1

    # -- helpers ------------------------------------------------------------

    def pips_between(self, price1: float, price2: float) -> float:
        """Return the absolute distance between two prices in pips."""
        return abs(price1 - price2) / self.pip_size

    def pip_value_per_lot(self, account_currency: str = "USD") -> float:
        """Pip value per standard lot in *account_currency*.

        For pairs where the quote currency matches *account_currency*
        the calculation is trivial: ``pip_size × contract_size``.

        For pairs where the **base** currency matches *account_currency*
        the formula is ``pip_size × contract_size / price`` — the caller
        must supply the current price via :meth:`pip_value_per_lot_at`.

        For cross-currency pairs the caller must supply a cross rate.

        Raises ``ValueError`` when the account currency is neither the
        base nor the quote (cross-rate calculation needed — use
        :meth:`pip_value_per_lot_at` with a live rate).
        """
        if self.quote_currency == account_currency:
            return self.pip_size * self.contract_size
        if self.base_currency == account_currency:
            # Requires a price — use the convenience overload
            raise ValueError(
                f"{self.symbol}: account currency {account_currency} is the base "
                f"currency. Use pip_value_per_lot_at(price) instead."
            )
        raise ValueError(
            f"{self.symbol}: account currency {account_currency} is neither "
            f"base ({self.base_currency}) nor quote ({self.quote_currency}). "
            f"Use pip_value_per_lot_at(price, cross_rate) with a live cross rate."
        )

    def pip_value_per_lot_at(
        self,
        price: float,
        cross_rate: float = 1.0,
        account_currency: str = "USD",
    ) -> float:
        """Pip value per standard lot, handling all currency combinations.

        Args:
            price: Current price of this symbol (base/quote).
            cross_rate: Conversion rate from the quote currency to
                *account_currency*.  Defaults to 1.0 (quote == account).
            account_currency: The denomination of the trading account.

        Returns:
            Pip value per standard lot in *account_currency*.
        """
        if self.quote_currency == account_currency:
            return self.pip_size * self.contract_size * cross_rate
        if self.base_currency == account_currency:
            # pip value = pip_size * contract_size / price
            return (self.pip_size * self.contract_size) / price if price else 0.0
        # General cross-rate case
        return self.pip_size * self.contract_size * cross_rate

    def validate_lot_size(self, lots: float) -> float:
        """Snap *lots* to the nearest valid lot step and clamp to [min, max].

        Raises ``ValueError`` if the result is below *min_lot*.
        """
        if self.lot_step > 0:
            lots = round(lots / self.lot_step) * self.lot_step
        lots = max(self.min_lot, min(self.max_lot, lots))
        # Re-round after clamping in case min/max aren't aligned
        if self.lot_step > 0:
            lots = round(lots / self.lot_step) * self.lot_step
        if lots < self.min_lot:
            raise ValueError(
                f"Lot size {lots} is below minimum {self.min_lot} for {self.symbol}"
            )
        return lots


# ---------------------------------------------------------------------------
# Pure calculation helpers
# ---------------------------------------------------------------------------

def calculate_pip_value(
    price: float,
    pip_size: float,
    contract_size: float,
    lot_size: float,
    cross_rate: float = 1.0,
) -> float:
    """Calculate the monetary pip value for a given position.

    Returns the pip value in the quote (or account) currency for the
    specified lot size.

    Args:
        price: Current price of the instrument.
        pip_size: The pip size (e.g. 0.0001 for EUR/USD).
        contract_size: Units per standard lot (e.g. 100 000).
        lot_size: Number of lots.
        cross_rate: Quote → account currency rate (default 1.0).

    Returns:
        Monetary value of one pip movement for this position.
    """
    return pip_size * contract_size * lot_size * cross_rate


def calculate_position_size(
    balance: float,
    risk_pct: float,
    stop_loss_pips: float,
    pip_value_per_lot: float,
    lot_step: float = 0.01,
    min_lot: float = 0.01,
    max_lot: float = 100.0,
) -> float:
    """Calculate the position size (in lots) for a given risk budget.

    Uses the fixed-risk model: ``risk_amount / (SL_pips × pip_value_per_lot)``.

    Args:
        balance: Account balance in account currency.
        risk_pct: Maximum risk as a percentage (e.g. 1.0 for 1%).
        stop_loss_pips: Distance from entry to stop-loss in pips.
        pip_value_per_lot: Monetary value of one pip per standard lot.
        lot_step: Minimum lot increment for broker alignment.
        min_lot: Minimum allowed lot size.
        max_lot: Maximum allowed lot size.

    Returns:
        Position size in lots, aligned to *lot_step*.
    """
    if stop_loss_pips <= 0 or pip_value_per_lot <= 0:
        return 0.0

    risk_amount = balance * (risk_pct / 100.0)
    lots = risk_amount / (stop_loss_pips * pip_value_per_lot)

    # Align to lot step
    if lot_step > 0:
        lots = round(lots / lot_step) * lot_step

    # Clamp
    lots = max(min_lot, min(max_lot, lots))

    return lots


def calculate_margin(
    lots: float,
    contract_size: float,
    price: float,
    leverage: float,
) -> float:
    """Calculate the margin required to open a position.

    Args:
        lots: Number of lots.
        contract_size: Units per standard lot.
        price: Current price of the instrument.
        leverage: Account leverage (e.g. 100 for 1:100).

    Returns:
        Required margin in account currency.
    """
    if leverage <= 0:
        raise ValueError(f"Leverage must be positive, got {leverage}")
    notional = lots * contract_size * price
    return notional / leverage


def calculate_spread_cost(
    spread_pips: float,
    pip_value_per_lot: float,
    lot_size: float,
) -> float:
    """Calculate the cost of the spread for a trade.

    Args:
        spread_pips: Current spread in pips.
        pip_value_per_lot: Monetary value of one pip per lot.
        lot_size: Number of lots.

    Returns:
        Spread cost in account currency.
    """
    return spread_pips * pip_value_per_lot * lot_size


def calculate_swap_cost(
    swap_rate: float,
    lot_size: float,
    days: int = 1,
    contract_size: float = 100_000.0,
) -> float:
    """Calculate accumulated swap (rollover) cost.

    Args:
        swap_rate: Daily swap rate per lot (positive = earn, negative = pay).
        lot_size: Number of lots.
        days: Number of days the position is held.
        contract_size: Units per standard lot.

    Returns:
        Total swap cost (negative = cost, positive = credit) in
        account currency.  Wednesday triple-swap is **not** applied
        automatically — the caller should multiply by 3 if
        ``days`` spans a Wednesday.
    """
    return swap_rate * lot_size * days


# ---------------------------------------------------------------------------
# Symbol normalizer
# ---------------------------------------------------------------------------

class SymbolNormalizer:
    """Convert between AlphaStack canonical symbols and broker-specific formats.

    Canonical format: ``"EUR/USD"`` (ISO 4217 with slash separator).
    """

    # Canonical → broker-specific
    _TO_BROKER: dict[str, Any] = {
        "mt5": lambda s: s.replace("/", ""),            # EURUSD
        "oanda": lambda s: s.replace("/", "_"),         # EUR_USD
        "ibkr": lambda s: s.replace("/", "."),          # EUR.USD
        "ccxt": lambda s: s,                            # EUR/USD (already canonical)
    }

    # Broker-specific → canonical
    _FROM_BROKER: dict[str, Any] = {
        # MT5: 6-char codes (EURUSD) or metals (XAUUSD)
        "mt5": lambda s: (
            f"{s[:3]}/{s[3:]}" if len(s) == 6 and s.isalpha() else s
        ),
        "oanda": lambda s: s.replace("_", "/"),
        "ibkr": lambda s: s.replace(".", "/"),
        "ccxt": lambda s: s,
    }

    @classmethod
    def to_broker(cls, symbol: str, broker: str) -> str:
        """Convert a canonical symbol to a broker-specific format.

        Examples::

            SymbolNormalizer.to_broker("EUR/USD", "mt5")   # → "EURUSD"
            SymbolNormalizer.to_broker("EUR/USD", "oanda")  # → "EUR_USD"
            SymbolNormalizer.to_broker("EUR/USD", "ccxt")   # → "EUR/USD"
        """
        converter = cls._TO_BROKER.get(broker, lambda s: s)
        return converter(symbol)

    @classmethod
    def to_canonical(cls, symbol: str, broker: str) -> str:
        """Convert a broker-specific symbol to the canonical format.

        Examples::

            SymbolNormalizer.to_canonical("EURUSD", "mt5")   # → "EUR/USD"
            SymbolNormalizer.to_canonical("EUR_USD", "oanda") # → "EUR/USD"
        """
        converter = cls._FROM_BROKER.get(broker, lambda s: s)
        return converter(symbol)


# ---------------------------------------------------------------------------
# Standard symbol definitions
# ---------------------------------------------------------------------------

FOREX_SYMBOLS: dict[str, ForexSymbol] = {
    # -- Major pairs --------------------------------------------------------
    "EUR/USD": ForexSymbol(
        symbol="EUR/USD", base_currency="EUR", quote_currency="USD",
        pip_digits=4, contract_size=100_000, pair_type=PairType.MAJOR,
    ),
    "GBP/USD": ForexSymbol(
        symbol="GBP/USD", base_currency="GBP", quote_currency="USD",
        pip_digits=4, contract_size=100_000, pair_type=PairType.MAJOR,
    ),
    "USD/JPY": ForexSymbol(
        symbol="USD/JPY", base_currency="USD", quote_currency="JPY",
        pip_digits=2, contract_size=100_000, pair_type=PairType.MAJOR,
    ),
    "USD/CHF": ForexSymbol(
        symbol="USD/CHF", base_currency="USD", quote_currency="CHF",
        pip_digits=4, contract_size=100_000, pair_type=PairType.MAJOR,
    ),
    "AUD/USD": ForexSymbol(
        symbol="AUD/USD", base_currency="AUD", quote_currency="USD",
        pip_digits=4, contract_size=100_000, pair_type=PairType.MAJOR,
    ),
    "USD/CAD": ForexSymbol(
        symbol="USD/CAD", base_currency="USD", quote_currency="CAD",
        pip_digits=4, contract_size=100_000, pair_type=PairType.MAJOR,
    ),
    "NZD/USD": ForexSymbol(
        symbol="NZD/USD", base_currency="NZD", quote_currency="USD",
        pip_digits=4, contract_size=100_000, pair_type=PairType.MAJOR,
    ),

    # -- Minor pairs (crosses) ---------------------------------------------
    "EUR/GBP": ForexSymbol(
        symbol="EUR/GBP", base_currency="EUR", quote_currency="GBP",
        pip_digits=4, contract_size=100_000, pair_type=PairType.MINOR,
    ),
    "EUR/JPY": ForexSymbol(
        symbol="EUR/JPY", base_currency="EUR", quote_currency="JPY",
        pip_digits=2, contract_size=100_000, pair_type=PairType.MINOR,
    ),
    "GBP/JPY": ForexSymbol(
        symbol="GBP/JPY", base_currency="GBP", quote_currency="JPY",
        pip_digits=2, contract_size=100_000, pair_type=PairType.MINOR,
    ),
    "EUR/AUD": ForexSymbol(
        symbol="EUR/AUD", base_currency="EUR", quote_currency="AUD",
        pip_digits=4, contract_size=100_000, pair_type=PairType.MINOR,
    ),
    "EUR/CHF": ForexSymbol(
        symbol="EUR/CHF", base_currency="EUR", quote_currency="CHF",
        pip_digits=4, contract_size=100_000, pair_type=PairType.MINOR,
    ),
    "GBP/AUD": ForexSymbol(
        symbol="GBP/AUD", base_currency="GBP", quote_currency="AUD",
        pip_digits=4, contract_size=100_000, pair_type=PairType.MINOR,
    ),
    "GBP/CHF": ForexSymbol(
        symbol="GBP/CHF", base_currency="GBP", quote_currency="CHF",
        pip_digits=4, contract_size=100_000, pair_type=PairType.MINOR,
    ),
    "AUD/JPY": ForexSymbol(
        symbol="AUD/JPY", base_currency="AUD", quote_currency="JPY",
        pip_digits=2, contract_size=100_000, pair_type=PairType.MINOR,
    ),
    "CAD/JPY": ForexSymbol(
        symbol="CAD/JPY", base_currency="CAD", quote_currency="JPY",
        pip_digits=2, contract_size=100_000, pair_type=PairType.MINOR,
    ),
    "NZD/JPY": ForexSymbol(
        symbol="NZD/JPY", base_currency="NZD", quote_currency="JPY",
        pip_digits=2, contract_size=100_000, pair_type=PairType.MINOR,
    ),
    "AUD/NZD": ForexSymbol(
        symbol="AUD/NZD", base_currency="AUD", quote_currency="NZD",
        pip_digits=4, contract_size=100_000, pair_type=PairType.MINOR,
    ),

    # -- Exotic pairs -------------------------------------------------------
    "USD/TRY": ForexSymbol(
        symbol="USD/TRY", base_currency="USD", quote_currency="TRY",
        pip_digits=4, contract_size=100_000, pair_type=PairType.EXOTIC,
    ),
    "USD/ZAR": ForexSymbol(
        symbol="USD/ZAR", base_currency="USD", quote_currency="ZAR",
        pip_digits=4, contract_size=100_000, pair_type=PairType.EXOTIC,
    ),
    "USD/MXN": ForexSymbol(
        symbol="USD/MXN", base_currency="USD", quote_currency="MXN",
        pip_digits=4, contract_size=100_000, pair_type=PairType.EXOTIC,
    ),
    "EUR/PLN": ForexSymbol(
        symbol="EUR/PLN", base_currency="EUR", quote_currency="PLN",
        pip_digits=4, contract_size=100_000, pair_type=PairType.EXOTIC,
    ),

    # -- Metals -------------------------------------------------------------
    "XAU/USD": ForexSymbol(
        symbol="XAU/USD", base_currency="XAU", quote_currency="USD",
        pip_digits=2, contract_size=100, pair_type=PairType.METAL,
    ),
    "XAG/USD": ForexSymbol(
        symbol="XAG/USD", base_currency="XAG", quote_currency="USD",
        pip_digits=3, contract_size=5_000, pair_type=PairType.METAL,
    ),
}


# ---------------------------------------------------------------------------
# Structural forex correlation matrix
# ---------------------------------------------------------------------------

# High positive correlations between pairs sharing a common currency.
# Inverse correlations are expressed as negative values.
FOREX_CORRELATIONS: dict[str, dict[str, float]] = {
    "EUR/USD": {"GBP/USD": 0.85, "AUD/USD": 0.70, "NZD/USD": 0.65, "USD/CHF": -0.90, "USD/JPY": -0.30},
    "GBP/USD": {"EUR/USD": 0.85, "AUD/USD": 0.60, "NZD/USD": 0.55, "USD/CHF": -0.80, "USD/JPY": -0.25},
    "USD/JPY": {"USD/CHF": 0.80, "USD/CAD": 0.60, "EUR/USD": -0.30, "GBP/USD": -0.25},
    "USD/CHF": {"USD/JPY": 0.80, "EUR/USD": -0.90, "GBP/USD": -0.80},
    "AUD/USD": {"NZD/USD": 0.90, "EUR/USD": 0.70, "GBP/USD": 0.60, "USD/CAD": -0.50},
    "NZD/USD": {"AUD/USD": 0.90, "EUR/USD": 0.65, "GBP/USD": 0.55},
    "USD/CAD": {"AUD/USD": -0.50, "USD/JPY": 0.60},
    "EUR/GBP": {"EUR/USD": 0.60, "GBP/USD": -0.40},
    "EUR/JPY": {"GBP/JPY": 0.90, "USD/JPY": 0.50},
    "GBP/JPY": {"EUR/JPY": 0.90, "USD/JPY": 0.40},
}


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

def get_symbol(symbol: str) -> ForexSymbol:
    """Look up a ForexSymbol by canonical name.

    Raises ``KeyError`` if the symbol is not in the standard registry.
    """
    try:
        return FOREX_SYMBOLS[symbol]
    except KeyError:
        raise KeyError(
            f"Unknown forex symbol: {symbol!r}. "
            f"Known symbols: {', '.join(sorted(FOREX_SYMBOLS))}"
        )


def is_forex_symbol(symbol: str) -> bool:
    """Return ``True`` if *symbol* is a known forex/metal instrument."""
    return symbol in FOREX_SYMBOLS


def symbols_by_type(pair_type: PairType) -> list[str]:
    """Return all symbols of the given *pair_type*."""
    return [s.symbol for s in FOREX_SYMBOLS.values() if s.pair_type == pair_type]


def spread_in_pips(spread_raw: float, pip_size: float) -> float:
    """Convert a raw spread (price difference) to pips."""
    if pip_size <= 0:
        return 0.0
    return spread_raw / pip_size


def spread_in_pips_pct(spread_pips: float, price: float, pip_size: float) -> float:
    """Spread as a percentage of price, useful for cross-asset comparison.

    Returns the spread cost as a fraction (e.g. 0.0001 = 0.01%).
    """
    if price <= 0:
        return 0.0
    return (spread_pips * pip_size) / price
