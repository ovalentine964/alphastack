"""FBS Broker Connector – MT5-based forex for African and global traders.

FBS is a popular forex broker in Africa supporting MetaTrader 5 with:
- Cent accounts (0.01 lot = 100 units = ~$0.01/pip on majors)
- Standard accounts (0.01 lot = 1,000 units = ~$0.10/pip on majors)
- Low minimum deposits (as low as $1 on cent accounts)
- Wide symbol coverage: forex, metals, indices, crypto

This connector wraps MT5Connector and adds FBS-specific features:
- FBS server name auto-detection
- Cent lot calculations for micro-accounts
- Auto-detect account type from balance
- FBS-specific symbol mapping
"""

from __future__ import annotations

import asyncio
import datetime as dt
from dataclasses import dataclass
from enum import Enum
from typing import Any

import structlog

from alphastack.brokers.base import BrokerConnector, ConnectionState
from alphastack.brokers.models import (
    BrokerBalance,
    BrokerBar,
    BrokerOrder,
    BrokerPosition,
    BrokerTick,
    OrderSide,
    OrderStatus,
    OrderType,
    PositionSide,
)
from alphastack.brokers.mt5_connector import MT5Connector

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# FBS account types
# ---------------------------------------------------------------------------

class FBSAccountType(str, Enum):
    """FBS account tier – determines lot sizing and pip values."""
    CENT = "cent"          # 0.01 lot = 100 units (~$0.01/pip on majors)
    STANDARD = "standard"  # 0.01 lot = 1,000 units (~$0.10/pip on majors)
    MICRO = "micro"        # 0.01 lot = 100 units, higher spreads
    ZERO = "zero"          # Raw spread + commission


# ---------------------------------------------------------------------------
# FBS server names
# ---------------------------------------------------------------------------

FBS_SERVERS: dict[str, str] = {
    "demo": "FBS-Demo",
    "real": "FBS-Real",
    "mt5-demo": "FBS-MT5",
    "mt5-real": "FBS-MT5 Real",
    "cent-demo": "FBS-Demo",
    "cent-real": "FBS-Real",
}


# ---------------------------------------------------------------------------
# FBS symbol mapping
# ---------------------------------------------------------------------------

# FBS MT5 uses standard symbol names for most pairs, but some have suffixes
# or non-standard names depending on the account type.

_FBS_SYMBOL_MAP: dict[str, dict[str, str]] = {
    # canonical → {account_type → mt5_symbol}
    "EUR/USD": {
        "cent": "EURUSD",
        "standard": "EURUSD",
        "micro": "EURUSD",
        "zero": "EURUSD",
    },
    "GBP/USD": {
        "cent": "GBPUSD",
        "standard": "GBPUSD",
        "micro": "GBPUSD",
        "zero": "GBPUSD",
    },
    "USD/JPY": {
        "cent": "USDJPY",
        "standard": "USDJPY",
        "micro": "USDJPY",
        "zero": "USDJPY",
    },
    "USD/CHF": {
        "cent": "USDCHF",
        "standard": "USDCHF",
        "micro": "USDCHF",
        "zero": "USDCHF",
    },
    "AUD/USD": {
        "cent": "AUDUSD",
        "standard": "AUDUSD",
        "micro": "AUDUSD",
        "zero": "AUDUSD",
    },
    "USD/CAD": {
        "cent": "USDCAD",
        "standard": "USDCAD",
        "micro": "USDCAD",
        "zero": "USDCAD",
    },
    "NZD/USD": {
        "cent": "NZDUSD",
        "standard": "NZDUSD",
        "micro": "NZDUSD",
        "zero": "NZDUSD",
    },
    "EUR/GBP": {
        "cent": "EURGBP",
        "standard": "EURGBP",
        "micro": "EURGBP",
        "zero": "EURGBP",
    },
    "EUR/JPY": {
        "cent": "EURJPY",
        "standard": "EURJPY",
        "micro": "EURJPY",
        "zero": "EURJPY",
    },
    "GBP/JPY": {
        "cent": "GBPJPY",
        "standard": "GBPJPY",
        "micro": "GBPJPY",
        "zero": "GBPJPY",
    },
    # Metals – popular in Africa
    "XAU/USD": {
        "cent": "XAUUSD",
        "standard": "XAUUSD",
        "micro": "XAUUSD",
        "zero": "XAUUSD",
    },
    "XAG/USD": {
        "cent": "XAGUSD",
        "standard": "XAGUSD",
        "micro": "XAGUSD",
        "zero": "XAGUSD",
    },
    # Crypto – FBS offers crypto CFDs
    "BTC/USD": {
        "cent": "BTCUSD",
        "standard": "BTCUSD",
        "micro": "BTCUSD",
        "zero": "BTCUSD",
    },
    "ETH/USD": {
        "cent": "ETHUSD",
        "standard": "ETHUSD",
        "micro": "ETHUSD",
        "zero": "ETHUSD",
    },
    "LTC/USD": {
        "cent": "LTCUSD",
        "standard": "LTCUSD",
        "micro": "LTCUSD",
        "zero": "LTCUSD",
    },
    "XRP/USD": {
        "cent": "XRPUSD",
        "standard": "XRPUSD",
        "micro": "XRPUSD",
        "zero": "XRPUSD",
    },
    # Indices – available on standard/zero accounts
    "US30": {
        "cent": "US30",
        "standard": "US30",
        "micro": "US30",
        "zero": "US30",
    },
    "NAS100": {
        "cent": "NAS100",
        "standard": "NAS100",
        "micro": "NAS100",
        "zero": "NAS100",
    },
    "SPX500": {
        "cent": "SPX500",
        "standard": "SPX500",
        "micro": "SPX500",
        "zero": "SPX500",
    },
}

# Reverse mapping: MT5 symbol → canonical
_FBS_REVERSE_MAP: dict[str, str] = {}
for _canonical, _variants in _FBS_SYMBOL_MAP.items():
    for _atype, _mt5_sym in _variants.items():
        _FBS_REVERSE_MAP[_mt5_sym] = _canonical


# ---------------------------------------------------------------------------
# Cent lot calculator
# ---------------------------------------------------------------------------

@dataclass
class FBSCentLotInfo:
    """Breakdown of cent lot sizing for FBS.

    On a cent account:
    - 0.01 lot = 100 units of base currency
    - For EUR/USD: 0.01 lot → $0.01/pip
    - For USD/JPY: 0.01 lot → ~¥1/pip ≈ $0.007/pip
    - Margin for 0.01 lot EUR/USD at 1:1000 = $0.001
    """

    lots: float
    units: float           # Actual units of base currency
    pip_value_usd: float   # USD value per pip
    margin_required: float # Margin in account currency
    contract_size: float   # Units per lot (100 for cent, 100000 for standard)
    account_type: FBSAccountType = FBSAccountType.CENT

    @property
    def risk_per_pip(self) -> float:
        """Alias for pip_value_usd – how much you gain/lose per pip."""
        return self.pip_value_usd


def calculate_fbs_cent_lot(
    lots: float,
    symbol: str = "EUR/USD",
    price: float = 1.0850,
    leverage: float = 1000.0,
    account_type: FBSAccountType = FBSAccountType.CENT,
) -> FBSCentLotInfo:
    """Calculate pip value and margin for FBS cent lots.

    Parameters
    ----------
    lots : float
        Lot size (e.g. 0.01 for micro position).
    symbol : str
        Canonical symbol (e.g. "EUR/USD").
    price : float
        Current price.
    leverage : float
        Account leverage (default 1:1000 for FBS cent).
    account_type : FBSAccountType
        Account tier.

    Returns
    -------
    FBSCentLotInfo
        Full breakdown of position sizing.
    """
    # Contract size depends on account type
    contract_sizes = {
        FBSAccountType.CENT: 1_000,       # Cent lots: 0.01 lot = 100 units
        FBSAccountType.STANDARD: 100_000,  # Standard lots
        FBSAccountType.MICRO: 1_000,       # Micro lots
        FBSAccountType.ZERO: 100_000,      # Zero spread accounts
    }
    contract_size = contract_sizes[account_type]

    units = lots * contract_size

    # Pip value calculation
    # For XXX/USD pairs: pip_value = pip_size * units
    # For USD/XXX pairs: pip_value = pip_size * units / price
    parts = symbol.split("/")
    if len(parts) != 2:
        # Non-forex symbols (indices, crypto) – approximate
        if "BTC" in symbol:
            pip_value = 0.01 * units * price  # BTC pip = $0.01 per unit
        elif "ETH" in symbol:
            pip_value = 0.01 * units
        else:
            pip_value = 0.01 * units  # Index default
    elif parts[1] == "USD":
        # Quote is USD – pip value is straightforward
        pip_size = 0.01 if parts[0] == "JPY" else 0.0001
        pip_value = pip_size * units
    elif parts[0] == "USD":
        # Base is USD – pip value depends on price
        pip_size = 0.01 if parts[1] == "JPY" else 0.0001
        pip_value = (pip_size * units) / price if price else 0.0
    else:
        # Cross pair – approximate using USD conversion
        pip_size = 0.01 if "JPY" in symbol else 0.0001
        pip_value = pip_size * units  # Caller should convert

    # Margin = (lots * contract_size * price) / leverage
    margin = (lots * contract_size * price) / leverage if leverage > 0 else 0.0

    return FBSCentLotInfo(
        lots=lots,
        units=units,
        pip_value_usd=pip_value,
        margin_required=margin,
        contract_size=contract_size,
        account_type=account_type,
    )


# ---------------------------------------------------------------------------
# FBS Connector
# ---------------------------------------------------------------------------

class FBSConnector(MT5Connector):
    """FBS-specific MT5 connector for African and global traders.

    Extends MT5Connector with:
    - FBS server auto-detection (FBS-Demo, FBS-Real, FBS-MT5)
    - Cent account lot sizing (0.01 lot = ~$0.01/pip on EUR/USD)
    - Auto-detect account type from balance
    - Symbol mapping for FBS-specific naming
    - Low minimum deposits (as low as $1 on cent accounts)

    Parameters
    ----------
    login : int
        FBS MT5 account number.
    password : str
        MT5 password.
    server : str | None
        FBS server name. Auto-detected if not provided.
    account_type : FBSAccountType | None
        Account tier. Auto-detected from balance if not provided.
    use_demo : bool
        Use demo server (default True for safety).
    path : str | None
        Path to MT5 terminal executable.
    timeout : int
        Connection timeout in milliseconds.
    """

    def __init__(
        self,
        *,
        login: int | None = None,
        password: str | None = None,
        server: str | None = None,
        account_type: FBSAccountType | None = None,
        use_demo: bool = True,
        path: str | None = None,
        timeout: int = 60_000,
    ) -> None:
        # Resolve FBS server name
        if server is None:
            server = FBS_SERVERS["demo" if use_demo else "real"]

        super().__init__(
            login=login,
            password=password,
            server=server,
            path=path,
            timeout=timeout,
        )

        # Override the name for registry
        self.name = "fbs"

        self._account_type = account_type
        self._use_demo = use_demo
        self._leverage = 1000.0  # Default FBS leverage
        self._auto_detect_account = account_type is None

    # -- lifecycle ----------------------------------------------------------

    async def connect(self) -> None:
        """Connect to FBS MT5 and auto-detect account type."""
        await super().connect()

        # Auto-detect account type from balance if not specified
        if self._auto_detect_account:
            await self._detect_account_type()

        logger.info(
            "fbs_connected",
            account_type=self._account_type.value if self._account_type else "unknown",
            demo=self._use_demo,
            server=self._server,
            login=self._login,
        )

    async def _detect_account_type(self) -> None:
        """Auto-detect account type based on balance and account info.

        Detection logic:
        - Balance < $100 → cent account (micro-deposits)
        - Balance >= $100 and leverage >= 1:500 → standard
        - Otherwise → standard
        """
        try:
            mt5 = await self._run(
                __import__("MetaTrader5", fromlist=["account_info"]).account_info
            )
            if mt5 is None:
                self._account_type = FBSAccountType.STANDARD
                return

            balance = mt5.balance
            leverage = mt5.leverage if hasattr(mt5, "leverage") else 1000

            self._leverage = float(leverage)

            # FBS cent accounts typically have small balances
            # and high leverage (1:1000 or 1:2000)
            if balance < 100.0 and leverage >= 500:
                self._account_type = FBSAccountType.CENT
                logger.info("fbs_auto_detected_cent", balance=balance, leverage=leverage)
            elif balance < 10.0:
                self._account_type = FBSAccountType.CENT
                logger.info("fbs_auto_detected_cent_micro", balance=balance)
            else:
                self._account_type = FBSAccountType.STANDARD
                logger.info("fbs_auto_detected_standard", balance=balance, leverage=leverage)

        except Exception as exc:
            logger.warning("fbs_account_detection_failed", error=str(exc))
            self._account_type = FBSAccountType.STANDARD  # Safe default

    # -- symbol mapping -----------------------------------------------------

    def to_mt5_symbol(self, canonical: str) -> str:
        """Convert canonical symbol to FBS MT5 format.

        Examples::

            connector.to_mt5_symbol("EUR/USD")  # → "EURUSD"
            connector.to_mt5_symbol("XAU/USD")  # → "XAUUSD"
            connector.to_mt5_symbol("BTC/USD")  # → "BTCUSD"
        """
        atype = self._account_type.value if self._account_type else "standard"
        variants = _FBS_SYMBOL_MAP.get(canonical)
        if variants:
            return variants.get(atype, canonical.replace("/", ""))
        return canonical.replace("/", "")

    def from_mt5_symbol(self, mt5_symbol: str) -> str:
        """Convert FBS MT5 symbol back to canonical format.

        Examples::

            connector.from_mt5_symbol("EURUSD")  # → "EUR/USD"
            connector.from_mt5_symbol("XAUUSD")   # → "XAU/USD"
        """
        canonical = _FBS_REVERSE_MAP.get(mt5_symbol)
        if canonical:
            return canonical
        # Fallback: try to split 6-char alpha symbol
        if len(mt5_symbol) >= 6 and mt5_symbol[:6].isalpha():
            return f"{mt5_symbol[:3]}/{mt5_symbol[3:6]}"
        return mt5_symbol

    # -- cent lot helpers ---------------------------------------------------

    def cent_lot_info(
        self,
        lots: float,
        symbol: str = "EUR/USD",
        price: float = 1.0850,
        leverage: float | None = None,
    ) -> FBSCentLotInfo:
        """Calculate pip value and margin for an FBS cent lot position.

        Parameters
        ----------
        lots : float
            Lot size (e.g. 0.01).
        symbol : str
            Canonical symbol.
        price : float
            Current price.
        leverage : float | None
            Account leverage. Uses detected leverage if not provided.

        Returns
        -------
        FBSCentLotInfo
            Full position sizing breakdown.
        """
        return calculate_fbs_cent_lot(
            lots=lots,
            symbol=symbol,
            price=price,
            leverage=leverage or self._leverage,
            account_type=self._account_type or FBSAccountType.CENT,
        )

    def max_lots_for_balance(
        self,
        balance: float,
        symbol: str = "EUR/USD",
        price: float = 1.0850,
        leverage: float | None = None,
        risk_pct: float = 2.0,
    ) -> float:
        """Calculate maximum lot size for a given balance.

        Parameters
        ----------
        balance : float
            Account balance in USD.
        symbol : str
            Canonical symbol.
        price : float
            Current price.
        leverage : float | None
            Account leverage. Uses detected leverage if not provided.
        risk_pct : float
            Max risk as percentage of balance.

        Returns
        -------
        float
            Maximum lot size aligned to 0.01 step.
        """
        lev = leverage or self._leverage
        risk_amount = balance * (risk_pct / 100.0)

        # Margin for 0.01 lot
        info = self.cent_lot_info(0.01, symbol, price, lev)
        if info.margin_required <= 0:
            return 0.0

        # Max lots by margin (use 80% of balance for safety)
        max_by_margin = (balance * 0.8) / info.margin_required * 0.01

        # Max lots by risk (assuming 20 pip SL)
        sl_pips = 20.0
        if info.pip_value_usd > 0:
            max_by_risk = risk_amount / (sl_pips * info.pip_value_usd / 0.01)
        else:
            max_by_risk = max_by_margin

        lots = min(max_by_margin, max_by_risk)
        # Align to 0.01
        lots = max(0.01, round(lots * 100) / 100)
        return lots

    # -- orders (override for symbol mapping) -------------------------------

    async def place_order(self, order: BrokerOrder) -> BrokerOrder:
        """Place order with FBS symbol mapping."""
        # Map canonical → FBS MT5 symbol
        original_symbol = order.symbol
        order.symbol = self.to_mt5_symbol(original_symbol)

        # For cent accounts, validate lot size
        if self._account_type == FBSAccountType.CENT and order.quantity < 0.01:
            order.quantity = 0.01  # Minimum cent lot

        try:
            result = await super().place_order(order)
        finally:
            # Restore canonical symbol for the caller
            order.symbol = original_symbol

        return result

    # -- account (override for cent balance display) ------------------------

    async def get_balance(self) -> BrokerBalance:
        """Get balance with cent account awareness."""
        balance = await super().get_balance()
        # FBS cent accounts show balance in cents
        # e.g., $5.00 shows as 500.00 on cent accounts
        # We normalize to USD for consistency
        if self._account_type == FBSAccountType.CENT:
            # MT5 reports cent account balance in the account currency
            # No conversion needed – MT5 handles this
            pass
        return balance

    # -- market data (override for symbol mapping) --------------------------

    async def get_tick(self, symbol: str) -> BrokerTick:
        """Get tick with FBS symbol mapping."""
        mt5_symbol = self.to_mt5_symbol(symbol)
        tick = await super().get_tick(mt5_symbol)
        tick.symbol = symbol  # Restore canonical
        return tick

    async def get_bars(
        self, symbol: str, timeframe: str, count: int = 500
    ) -> list[BrokerBar]:
        """Get bars with FBS symbol mapping."""
        mt5_symbol = self.to_mt5_symbol(symbol)
        bars = await super().get_bars(mt5_symbol, timeframe, count)
        for bar in bars:
            bar.symbol = symbol  # Restore canonical
        return bars

    # -- diagnostics --------------------------------------------------------

    def account_summary(self) -> dict[str, Any]:
        """Return FBS account configuration summary."""
        return {
            "broker": self.name,
            "account_type": self._account_type.value if self._account_type else "unknown",
            "leverage": self._leverage,
            "demo": self._use_demo,
            "server": self._server,
            "login": self._login,
            "min_lot": 0.01,
            "pip_value_per_micro_lot": {
                "EUR/USD": 0.01,   # $0.01/pip at 0.01 lot on cent
                "GBP/USD": 0.01,
                "USD/JPY": 0.007,  # ~¥0.07/pip
                "XAU/USD": 0.01,   # $0.01/pip
                "BTC/USD": 0.01,   # $0.01/pip on cent
            },
            "symbol_mapping_sample": {
                "EUR/USD": self.to_mt5_symbol("EUR/USD"),
                "XAU/USD": self.to_mt5_symbol("XAU/USD"),
                "BTC/USD": self.to_mt5_symbol("BTC/USD"),
            },
            "supported_symbols": list(_FBS_SYMBOL_MAP.keys()),
        }

    # -- helpers for setup wizard -------------------------------------------

    @classmethod
    def from_credentials(cls, credentials: dict[str, Any]) -> "FBSConnector":
        """Create an FBSConnector from a credentials dict.

        Expected keys:
        - login: int (MT5 account number)
        - password: str (MT5 password)
        - server: str | None (auto-detected if not provided)
        - use_demo: bool (default True)
        """
        return cls(
            login=int(credentials.get("login", 0)),
            password=credentials.get("password", ""),
            server=credentials.get("server"),
            use_demo=credentials.get("use_demo", True),
        )
