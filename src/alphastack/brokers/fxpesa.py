"""FXPesa (Kenya) broker connector – MT5-based forex for East African traders.

FXPesa is a Kenyan CFD/forex broker offering MetaTrader 5 accounts with:
- Cent accounts (0.01 lot = 1,000 units = ~$0.10/pip on majors)
- Standard accounts (0.01 lot = 1,000 units)
- M-Pesa deposits and withdrawals via their API
- KES-denominated accounts with USD trading

This connector wraps MT5Connector and adds FXPesa-specific features:
- Kenya-specific symbol mapping (FXPesa uses non-standard suffixes)
- Cent lot calculations for $7 micro-accounts
- M-Pesa payment integration
- Demo account support via FXPesa-Demo server
"""

from __future__ import annotations

import asyncio
import datetime as dt
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx
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
# FXPesa account types
# ---------------------------------------------------------------------------

class FXPesaAccountType(str, Enum):
    """FXPesa account tier – determines lot sizing and pip values."""
    CENT = "cent"          # 0.01 lot = 100 units (~$0.01/pip on majors)
    STANDARD = "standard"  # 0.01 lot = 1,000 units (~$0.10/pip on majors)
    PREMIUM = "premium"    # 0.01 lot = 1,000 units, tighter spreads


# ---------------------------------------------------------------------------
# FXPesa symbol mapping
# ---------------------------------------------------------------------------

# FXPesa MT5 uses suffix-based symbol names that vary by account type.
# Cent accounts: "EURUSDc", "GBPUSDc", etc.
# Standard: "EURUSD", "GBPUSD", etc.
# Some symbols have unusual names on FXPesa.

_FXPESA_SYMBOL_MAP: dict[str, dict[str, str]] = {
    # canonical → {account_type → mt5_symbol}
    "EUR/USD": {
        "cent": "EURUSDc",
        "standard": "EURUSD",
        "premium": "EURUSD",
    },
    "GBP/USD": {
        "cent": "GBPUSDc",
        "standard": "GBPUSD",
        "premium": "GBPUSD",
    },
    "USD/JPY": {
        "cent": "USDJPYc",
        "standard": "USDJPY",
        "premium": "USDJPY",
    },
    "USD/CHF": {
        "cent": "USDCHFc",
        "standard": "USDCHF",
        "premium": "USDCHF",
    },
    "AUD/USD": {
        "cent": "AUDUSDc",
        "standard": "AUDUSD",
        "premium": "AUDUSD",
    },
    "USD/CAD": {
        "cent": "USDCADc",
        "standard": "USDCAD",
        "premium": "USDCAD",
    },
    "NZD/USD": {
        "cent": "NZDUSDc",
        "standard": "NZDUSD",
        "premium": "NZDUSD",
    },
    "EUR/GBP": {
        "cent": "EURGB Pc",  # FXPesa quirk
        "standard": "EURGBP",
        "premium": "EURGBP",
    },
    "EUR/JPY": {
        "cent": "EURJPYc",
        "standard": "EURJPY",
        "premium": "EURJPY",
    },
    "GBP/JPY": {
        "cent": "GBPJPYc",
        "standard": "GBPJPY",
        "premium": "GBPJPY",
    },
    "XAU/USD": {
        "cent": "XAUUSDc",
        "standard": "XAUUSD",
        "premium": "XAUUSD",
    },
    "XAG/USD": {
        "cent": "XAGUSDc",
        "standard": "XAGUSD",
        "premium": "XAGUSD",
    },
    # Kenya-relevant crosses
    "USD/KES": {
        "cent": "USDKESc",
        "standard": "USDKES",
        "premium": "USDKES",
    },
    "EUR/KES": {
        "cent": "EURKESc",
        "standard": "EURKES",
        "premium": "EURKES",
    },
    "GBP/KES": {
        "cent": "GBPKESc",
        "standard": "GBPKES",
        "premium": "GBPKES",
    },
}

# Reverse mapping: MT5 symbol → canonical
_FXPESA_REVERSE_MAP: dict[str, str] = {}
for _canonical, _variants in _FXPESA_SYMBOL_MAP.items():
    for _atype, _mt5_sym in _variants.items():
        _FXPESA_REVERSE_MAP[_mt5_sym] = _canonical


# ---------------------------------------------------------------------------
# FXPesa server names
# ---------------------------------------------------------------------------

_FXPESA_SERVERS: dict[str, str] = {
    "demo": "FXPesa-Demo",
    "live": "FXPesa-Live",
    "cent-demo": "FXPesaCent-Demo",
    "cent-live": "FXPesaCent-Live",
}


# ---------------------------------------------------------------------------
# Cent lot calculator
# ---------------------------------------------------------------------------

@dataclass
class CentLotInfo:
    """Breakdown of cent lot sizing for FXPesa.

    On a cent account:
    - 0.01 lot = 1,000 units of base currency
    - For EUR/USD: 0.01 lot → $0.10/pip
    - For USD/JPY: 0.01 lot → ~¥10/pip ≈ $0.07/pip
    - Margin for 0.01 lot EUR/USD at 1:400 = $2.50
    """

    lots: float
    units: float          # Actual units of base currency
    pip_value_usd: float  # USD value per pip
    margin_required: float # Margin in account currency
    contract_size: float  # Units per lot (1000 for cent, 100000 for standard)
    account_type: FXPesaAccountType = FXPesaAccountType.CENT

    @property
    def risk_per_pip(self) -> float:
        """Alias for pip_value_usd – how much you gain/lose per pip."""
        return self.pip_value_usd


def calculate_cent_lot(
    lots: float,
    symbol: str = "EUR/USD",
    price: float = 1.0850,
    leverage: float = 400.0,
    account_type: FXPesaAccountType = FXPesaAccountType.CENT,
) -> CentLotInfo:
    """Calculate pip value and margin for FXPesa cent lots.

    Parameters
    ----------
    lots : float
        Lot size (e.g. 0.01 for micro position).
    symbol : str
        Canonical symbol (e.g. "EUR/USD").
    price : float
        Current price.
    leverage : float
        Account leverage (default 1:400 for FXPesa cent).
    account_type : FXPesaAccountType
        Account tier.

    Returns
    -------
    CentLotInfo
        Full breakdown of position sizing.
    """
    # Contract size depends on account type
    contract_sizes = {
        FXPesaAccountType.CENT: 1_000,       # Cent lots
        FXPesaAccountType.STANDARD: 100_000,  # Standard lots
        FXPesaAccountType.PREMIUM: 100_000,   # Premium lots
    }
    contract_size = contract_sizes[account_type]

    units = lots * contract_size

    # Pip value calculation
    # For XXX/USD pairs: pip_value = pip_size * units
    # For USD/XXX pairs: pip_value = pip_size * units / price
    parts = symbol.split("/")
    if len(parts) != 2:
        pip_value = 0.0001 * units  # Assume 4-digit
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

    return CentLotInfo(
        lots=lots,
        units=units,
        pip_value_usd=pip_value,
        margin_required=margin,
        contract_size=contract_size,
        account_type=account_type,
    )


# ---------------------------------------------------------------------------
# M-Pesa integration
# ---------------------------------------------------------------------------

@dataclass
class MPesaConfig:
    """M-Pesa API configuration for FXPesa deposits/withdrawals.

    FXPesa exposes an M-Pesa integration via their partner API.
    These are the credentials needed for STK Push (deposit) and
    B2C (withdrawal) requests.
    """

    consumer_key: str = ""
    consumer_secret: str = ""
    passkey: str = ""
    shortcode: str = ""          # FXPesa's M-Pesa paybill number
    callback_url: str = ""       # Your callback endpoint
    environment: str = "sandbox"  # "sandbox" or "production"

    @property
    def base_url(self) -> str:
        if self.environment == "production":
            return "https://api.safaricom.co.ke"
        return "https://sandbox.safaricom.co.ke"


class MPesaClient:
    """M-Pesa STK Push and B2C client for FXPesa account funding.

    Usage::

        mpesa = MPesaClient(config)
        await mpesa.connect()

        # Deposit via STK Push
        result = await mpesa.initiate_deposit(
            phone_number="254712345678",
            amount=1000,  # KES
            account_ref="FXPesa-12345",
        )

        # Check status
        status = await mpesa.check_status(result["checkout_request_id"])

        await mpesa.disconnect()
    """

    def __init__(self, config: MPesaConfig) -> None:
        self._config = config
        self._client: httpx.AsyncClient | None = None
        self._access_token: str = ""
        self._token_expires: dt.datetime | None = None

    async def connect(self) -> None:
        """Initialize HTTP client and obtain OAuth token."""
        self._client = httpx.AsyncClient(timeout=30.0)
        await self._refresh_token()

    async def disconnect(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _refresh_token(self) -> None:
        """Obtain a new OAuth access token from Safaricom."""
        if not self._client:
            raise RuntimeError("MPesaClient not connected")

        import base64
        credentials = base64.b64encode(
            f"{self._config.consumer_key}:{self._config.consumer_secret}".encode()
        ).decode()

        resp = await self._client.get(
            f"{self._config.base_url}/oauth/v1/generate?grant_type=client_credentials",
            headers={"Authorization": f"Basic {credentials}"},
        )
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data["access_token"]
        self._token_expires = dt.datetime.now(dt.timezone.utc) + dt.timedelta(
            seconds=int(data.get("expires_in", 3599))
        )

    async def _ensure_token(self) -> None:
        """Refresh token if expired."""
        if (
            self._token_expires is None
            or dt.datetime.now(dt.timezone.utc) >= self._token_expires
        ):
            await self._refresh_token()

    async def initiate_deposit(
        self,
        phone_number: str,
        amount: float,
        account_ref: str = "",
        description: str = "FXPesa Deposit",
    ) -> dict[str, Any]:
        """Initiate M-Pesa STK Push to deposit funds.

        Parameters
        ----------
        phone_number : str
            M-Pesa registered phone (format: 254XXXXXXXXX).
        amount : float
            Amount in KES.
        account_ref : str
            Account reference (your FXPesa account ID).
        description : str
            Transaction description.

        Returns
        -------
        dict
            STK Push response with CheckoutRequestID.
        """
        if not self._client:
            raise RuntimeError("MPesaClient not connected")

        await self._ensure_token()

        import hashlib
        import base64
        timestamp = dt.datetime.now().strftime("%Y%m%d%H%M%S")
        password_str = f"{self._config.shortcode}{self._config.passkey}{timestamp}"
        password = base64.b64encode(password_str.encode()).decode()

        payload = {
            "BusinessShortCode": self._config.shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(amount),
            "PartyA": phone_number,
            "PartyB": self._config.shortcode,
            "PhoneNumber": phone_number,
            "CallBackURL": self._config.callback_url,
            "AccountReference": account_ref or "FXPesa",
            "TransactionDescription": description,
        }

        resp = await self._client.post(
            f"{self._config.base_url}/mpesa/stkpush/v1/processrequest",
            json=payload,
            headers={"Authorization": f"Bearer {self._access_token}"},
        )
        resp.raise_for_status()
        result = resp.json()

        logger.info(
            "mpesa_stk_push_initiated",
            phone=phone_number,
            amount=amount,
            checkout_id=result.get("CheckoutRequestID"),
        )
        return result

    async def check_status(self, checkout_request_id: str) -> dict[str, Any]:
        """Check the status of an STK Push transaction.

        Parameters
        ----------
        checkout_request_id : str
            The CheckoutRequestID from initiate_deposit().

        Returns
        -------
        dict
            Transaction status response.
        """
        if not self._client:
            raise RuntimeError("MPesaClient not connected")

        await self._ensure_token()

        import hashlib
        import base64
        timestamp = dt.datetime.now().strftime("%Y%m%d%H%M%S")
        password_str = f"{self._config.shortcode}{self._config.passkey}{timestamp}"
        password = base64.b64encode(password_str.encode()).decode()

        payload = {
            "BusinessShortCode": self._config.shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "CheckoutRequestID": checkout_request_id,
        }

        resp = await self._client.post(
            f"{self._config.base_url}/mpesa/stkpushquery/v1/query",
            json=payload,
            headers={"Authorization": f"Bearer {self._access_token}"},
        )
        resp.raise_for_status()
        return resp.json()

    async def initiate_withdrawal(
        self,
        phone_number: str,
        amount: float,
        remarks: str = "FXPesa Withdrawal",
    ) -> dict[str, Any]:
        """Initiate M-Pesa B2C payment to withdraw funds.

        Parameters
        ----------
        phone_number : str
            Recipient M-Pesa phone (format: 254XXXXXXXXX).
        amount : float
            Amount in KES.
        remarks : str
            Transaction remarks.

        Returns
        -------
        dict
            B2C payment response with ConversationID.
        """
        if not self._client:
            raise RuntimeError("MPesaClient not connected")

        await self._ensure_token()

        payload = {
            "InitiatorName": "FXPesaAPI",
            "SecurityCredential": "",  # Encrypted by caller if needed
            "CommandID": "BusinessPayment",
            "Amount": int(amount),
            "PartyA": self._config.shortcode,
            "PartyB": phone_number,
            "Remarks": remarks,
            "QueueTimeOutURL": self._config.callback_url,
            "ResultURL": self._config.callback_url,
            "Occassion": "FXPesa",
        }

        resp = await self._client.post(
            f"{self._config.base_url}/mpesa/b2c/v1/paymentrequest",
            json=payload,
            headers={"Authorization": f"Bearer {self._access_token}"},
        )
        resp.raise_for_status()
        result = resp.json()

        logger.info(
            "mpesa_b2c_initiated",
            phone=phone_number,
            amount=amount,
            conversation_id=result.get("ConversationID"),
        )
        return result


# ---------------------------------------------------------------------------
# FXPesa Connector
# ---------------------------------------------------------------------------

class FXPesaConnector(MT5Connector):
    """FXPesa-specific MT5 connector for Kenyan forex traders.

    Extends MT5Connector with:
    - FXPesa server auto-detection
    - Cent account lot sizing (0.01 lot = ~$0.10/pip on EUR/USD)
    - Kenya-specific symbol mapping
    - M-Pesa deposit/withdrawal integration
    - Demo account support

    Parameters
    ----------
    login : int
        FXPesa MT5 account number.
    password : str
        MT5 password.
    account_type : FXPesaAccountType
        Account tier (cent, standard, premium).
    use_demo : bool
        Use demo server (default True for safety).
    mpesa_config : MPesaConfig | None
        M-Pesa credentials for deposits/withdrawals.
    """

    def __init__(
        self,
        *,
        login: int | None = None,
        password: str | None = None,
        server: str | None = None,
        account_type: FXPesaAccountType = FXPesaAccountType.CENT,
        use_demo: bool = True,
        mpesa_config: MPesaConfig | None = None,
        path: str | None = None,
        timeout: int = 60_000,
    ) -> None:
        # Resolve FXPesa server name
        if server is None:
            if account_type == FXPesaAccountType.CENT:
                server = _FXPESA_SERVERS["cent-demo" if use_demo else "cent-live"]
            else:
                server = _FXPESA_SERVERS["demo" if use_demo else "live"]

        super().__init__(
            login=login,
            password=password,
            server=server,
            path=path,
            timeout=timeout,
        )

        # Override the name for registry
        self.name = f"fxpesa:{account_type.value}"

        self._account_type = account_type
        self._use_demo = use_demo
        self._mpesa_config = mpesa_config
        self._mpesa: MPesaClient | None = None

        # Contract size for cent accounts
        self._contract_size = 1_000 if account_type == FXPesaAccountType.CENT else 100_000

    # -- lifecycle ----------------------------------------------------------

    async def connect(self) -> None:
        """Connect to FXPesa MT5 and optionally initialize M-Pesa."""
        await super().connect()
        logger.info(
            "fxpesa_connected",
            account_type=self._account_type.value,
            demo=self._use_demo,
            server=self._server,
        )

        # Initialize M-Pesa client if configured
        if self._mpesa_config and self._mpesa_config.consumer_key:
            self._mpesa = MPesaClient(self._mpesa_config)
            await self._mpesa.connect()
            logger.info("fxpesa_mpesa_connected")

    async def disconnect(self) -> None:
        """Disconnect from FXPesa and M-Pesa."""
        if self._mpesa:
            await self._mpesa.disconnect()
            self._mpesa = None
        await super().disconnect()

    # -- symbol mapping -----------------------------------------------------

    def to_mt5_symbol(self, canonical: str) -> str:
        """Convert canonical symbol to FXPesa MT5 format.

        Examples::

            connector.to_mt5_symbol("EUR/USD")  # → "EURUSDc" (cent) or "EURUSD" (standard)
            connector.to_mt5_symbol("XAU/USD")  # → "XAUUSDc" (cent) or "XAUUSD" (standard)
        """
        variants = _FXPESA_SYMBOL_MAP.get(canonical)
        if variants:
            return variants.get(self._account_type.value, canonical.replace("/", ""))
        return canonical.replace("/", "")

    def from_mt5_symbol(self, mt5_symbol: str) -> str:
        """Convert FXPesa MT5 symbol back to canonical format.

        Examples::

            connector.from_mt5_symbol("EURUSDc")  # → "EUR/USD"
            connector.from_mt5_symbol("XAUUSD")    # → "XAU/USD"
        """
        canonical = _FXPESA_REVERSE_MAP.get(mt5_symbol)
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
        leverage: float = 400.0,
    ) -> CentLotInfo:
        """Calculate pip value and margin for a cent lot position.

        Parameters
        ----------
        lots : float
            Lot size (e.g. 0.01).
        symbol : str
            Canonical symbol.
        price : float
            Current price.
        leverage : float
            Account leverage.

        Returns
        -------
        CentLotInfo
            Full position sizing breakdown.
        """
        return calculate_cent_lot(
            lots=lots,
            symbol=symbol,
            price=price,
            leverage=leverage,
            account_type=self._account_type,
        )

    def max_lots_for_balance(
        self,
        balance: float,
        symbol: str = "EUR/USD",
        price: float = 1.0850,
        leverage: float = 400.0,
        risk_pct: float = 2.0,
    ) -> float:
        """Calculate maximum lot size for a $7 micro-account.

        Parameters
        ----------
        balance : float
            Account balance in USD.
        symbol : str
            Canonical symbol.
        price : float
            Current price.
        leverage : float
            Account leverage.
        risk_pct : float
            Max risk as percentage of balance.

        Returns
        -------
        float
            Maximum lot size aligned to 0.01 step.
        """
        risk_amount = balance * (risk_pct / 100.0)
        # Margin for 0.01 lot
        info = self.cent_lot_info(0.01, symbol, price, leverage)
        if info.margin_required <= 0:
            return 0.0

        # Max lots by margin
        max_by_margin = balance / info.margin_required * 0.01

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
        """Place order with FXPesa symbol mapping."""
        # Map canonical → FXPesa MT5 symbol
        original_symbol = order.symbol
        order.symbol = self.to_mt5_symbol(original_symbol)

        # For cent accounts, validate lot size
        if self._account_type == FXPesaAccountType.CENT and order.quantity < 0.01:
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
        # FXPesa cent accounts show balance in cents
        # e.g., $7.00 shows as 700.00 on cent accounts
        # We normalize to USD for consistency
        if self._account_type == FXPesaAccountType.CENT:
            # MT5 reports cent account balance in cents
            # The raw value is already in the account currency
            # No conversion needed – MT5 handles this
            pass
        return balance

    # -- M-Pesa integration -------------------------------------------------

    async def mpesa_deposit(
        self,
        phone_number: str,
        amount_kes: float,
    ) -> dict[str, Any]:
        """Initiate M-Pesa deposit to FXPesa account.

        Parameters
        ----------
        phone_number : str
            M-Pesa phone (format: 254XXXXXXXXX).
        amount_kes : float
            Amount in KES.

        Returns
        -------
        dict
            STK Push response.

        Raises
        ------
        RuntimeError
            If M-Pesa is not configured.
        """
        if not self._mpesa:
            raise RuntimeError(
                "M-Pesa not configured. Pass MPesaConfig to FXPesaConnector."
            )

        result = await self._mpesa.initiate_deposit(
            phone_number=phone_number,
            amount=amount_kes,
            account_ref=f"FXPesa-{self._login}",
        )
        return result

    async def mpesa_withdraw(
        self,
        phone_number: str,
        amount_kes: float,
    ) -> dict[str, Any]:
        """Initiate M-Pesa withdrawal from FXPesa account.

        Parameters
        ----------
        phone_number : str
            M-Pesa phone (format: 254XXXXXXXXX).
        amount_kes : float
            Amount in KES.

        Returns
        -------
        dict
            B2C payment response.

        Raises
        ------
        RuntimeError
            If M-Pesa is not configured.
        """
        if not self._mpesa:
            raise RuntimeError(
                "M-Pesa not configured. Pass MPesaConfig to FXPesaConnector."
            )

        result = await self._mpesa.initiate_withdrawal(
            phone_number=phone_number,
            amount=amount_kes,
        )
        return result

    async def mpesa_check_deposit(self, checkout_request_id: str) -> dict[str, Any]:
        """Check status of an M-Pesa deposit.

        Parameters
        ----------
        checkout_request_id : str
            The CheckoutRequestID from mpesa_deposit().

        Returns
        -------
        dict
            Transaction status.
        """
        if not self._mpesa:
            raise RuntimeError("M-Pesa not configured")
        return await self._mpesa.check_status(checkout_request_id)

    # -- market data (override for symbol mapping) --------------------------

    async def get_tick(self, symbol: str) -> BrokerTick:
        """Get tick with FXPesa symbol mapping."""
        mt5_symbol = self.to_mt5_symbol(symbol)
        tick = await super().get_tick(mt5_symbol)
        tick.symbol = symbol  # Restore canonical
        return tick

    async def get_bars(
        self, symbol: str, timeframe: str, count: int = 500
    ) -> list[BrokerBar]:
        """Get bars with FXPesa symbol mapping."""
        mt5_symbol = self.to_mt5_symbol(symbol)
        bars = await super().get_bars(mt5_symbol, timeframe, count)
        for bar in bars:
            bar.symbol = symbol  # Restore canonical
        return bars

    # -- diagnostics --------------------------------------------------------

    def account_summary(self) -> dict[str, Any]:
        """Return FXPesa account configuration summary."""
        return {
            "broker": self.name,
            "account_type": self._account_type.value,
            "contract_size": self._contract_size,
            "demo": self._use_demo,
            "server": self._server,
            "login": self._login,
            "min_lot": 0.01,
            "pip_value_per_micro_lot": {
                "EUR/USD": 0.01,   # $0.01/pip at 0.01 lot on cent
                "GBP/USD": 0.01,
                "USD/JPY": 0.007,  # ~¥0.07/pip
                "XAU/USD": 0.01,   # $0.01/pip
            },
            "mpesa_enabled": self._mpesa is not None,
            "symbol_mapping_sample": {
                "EUR/USD": self.to_mt5_symbol("EUR/USD"),
                "XAU/USD": self.to_mt5_symbol("XAU/USD"),
            },
        }
