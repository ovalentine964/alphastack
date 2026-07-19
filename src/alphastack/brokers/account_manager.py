"""Multi-broker Account Manager – aggregate balances, track deposits, manage withdrawals.

Provides a unified view across FXPesa (forex), MEXC (crypto), and Binance (crypto)
accounts.  Designed for $7 micro-accounts with cent lots.

Usage::

    manager = AccountManager()
    manager.register("fxpesa", fxpesa_connector)
    manager.register("mexc", mexc_connector)
    manager.register("binance", binance_connector)

    await manager.connect_all()

    # Get aggregated view
    summary = await manager.get_aggregate_balance()
    print(f"Total equity: ${summary.total_equity:.2f}")

    # Track a deposit
    manager.record_deposit("fxpesa", 700, "KES", "M-Pesa STK Push")

    await manager.disconnect_all()
"""

from __future__ import annotations

import asyncio
import datetime as dt
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog

from alphastack.brokers.base import BrokerConnector, ConnectionState
from alphastack.brokers.models import (
    BrokerBalance,
    BrokerPosition,
    BrokerTick,
)

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Transaction types
# ---------------------------------------------------------------------------

class TransactionType(str, Enum):
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRANSFER = "transfer"       # Internal transfer between brokers
    FEE = "fee"                 # Brokerage fee
    SWAP = "swap"               # Swap/rollover charge
    PROFIT = "profit"           # Realized P&L
    LOSS = "loss"


class TransactionStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# Transaction record
# ---------------------------------------------------------------------------

@dataclass
class Transaction:
    """Record of a deposit, withdrawal, or transfer."""

    id: str
    broker: str
    tx_type: TransactionType
    amount: float
    currency: str
    status: TransactionStatus = TransactionStatus.PENDING
    description: str = ""
    reference: str = ""          # External reference (M-Pesa ID, TX hash, etc.)
    created_at: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))
    completed_at: dt.datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_pending(self) -> bool:
        return self.status == TransactionStatus.PENDING

    def complete(self) -> None:
        self.status = TransactionStatus.COMPLETED
        self.completed_at = dt.datetime.now(dt.timezone.utc)

    def fail(self, reason: str = "") -> None:
        self.status = TransactionStatus.FAILED
        self.completed_at = dt.datetime.now(dt.timezone.utc)
        if reason:
            self.metadata["failure_reason"] = reason


# ---------------------------------------------------------------------------
# Per-broker account snapshot
# ---------------------------------------------------------------------------

@dataclass
class BrokerAccountSnapshot:
    """Snapshot of a single broker account."""

    broker: str
    balance: BrokerBalance
    positions: list[BrokerPosition]
    open_position_count: int = 0
    total_unrealized_pnl: float = 0.0
    total_margin_used: float = 0.0
    timestamp: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))

    @property
    def equity(self) -> float:
        return self.balance.equity

    @property
    def available(self) -> float:
        return self.balance.available


# ---------------------------------------------------------------------------
# Aggregate balance
# ---------------------------------------------------------------------------

@dataclass
class AggregateBalance:
    """Aggregated balance across all broker accounts."""

    total_equity: float = 0.0
    total_available: float = 0.0
    total_margin_used: float = 0.0
    total_unrealized_pnl: float = 0.0
    total_realized_pnl: float = 0.0

    # Per-broker breakdown
    broker_balances: dict[str, BrokerAccountSnapshot] = field(default_factory=dict)

    # Currency conversions (to USD)
    total_equity_usd: float = 0.0
    total_available_usd: float = 0.0

    timestamp: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))

    @property
    def margin_utilization_pct(self) -> float:
        """Percentage of equity used as margin."""
        if self.total_equity <= 0:
            return 0.0
        return (self.total_margin_used / self.total_equity) * 100

    @property
    def open_position_count(self) -> int:
        return sum(s.open_position_count for s in self.broker_balances.values())

    def summary_text(self) -> str:
        """Human-readable summary for logging/display."""
        lines = [
            "═══ Aggregate Balance ═══",
            f"Total Equity:      ${self.total_equity_usd:>10.2f}",
            f"Total Available:   ${self.total_available_usd:>10.2f}",
            f"Margin Used:       ${self.total_margin_used:>10.2f}",
            f"Unrealized P&L:    ${self.total_unrealized_pnl:>+10.2f}",
            f"Open Positions:    {self.open_position_count:>10d}",
            f"Margin Utilization:{self.margin_utilization_pct:>9.1f}%",
            "",
            "─── Per Broker ───",
        ]
        for name, snap in self.broker_balances.items():
            lines.append(
                f"  {name:<16} equity=${snap.equity:>8.2f}  "
                f"avail=${snap.available:>8.2f}  "
                f"pnl={snap.total_unrealized_pnl:>+8.2f}  "
                f"pos={snap.open_position_count}"
            )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Account Manager
# ---------------------------------------------------------------------------

class AccountManager:
    """Multi-broker account aggregation and management.

    Parameters
    ----------
    default_currency : str
        Reporting currency (default USD).
    exchange_rates : dict[str, float] | None
        Manual exchange rates for currency conversion.
        Keys are ``"FROM/TO"`` pairs (e.g. ``"KES/USD"``).
    """

    def __init__(
        self,
        default_currency: str = "USD",
        exchange_rates: dict[str, float] | None = None,
    ) -> None:
        self._brokers: dict[str, BrokerConnector] = {}
        self._default_currency = default_currency
        self._exchange_rates: dict[str, float] = exchange_rates or {}
        self._transactions: list[Transaction] = []
        self._snapshots: dict[str, BrokerAccountSnapshot] = {}
        self._tx_counter: int = 0

        # Default exchange rates (approximate)
        self._exchange_rates.setdefault("KES/USD", 0.0065)   # ~154 KES/USD
        self._exchange_rates.setdefault("USD/KES", 154.0)
        self._exchange_rates.setdefault("EUR/USD", 1.085)
        self._exchange_rates.setdefault("GBP/USD", 1.265)
        self._exchange_rates.setdefault("USDT/USD", 1.0)
        self._exchange_rates.setdefault("USDC/USD", 1.0)
        self._exchange_rates.setdefault("BTC/USD", 0.0)  # Dynamic

    # -- broker registration ------------------------------------------------

    def register(self, name: str, connector: BrokerConnector) -> None:
        """Register a broker connector."""
        self._brokers[name] = connector
        logger.info("account_manager_registered", broker=name)

    def unregister(self, name: str) -> None:
        """Unregister a broker."""
        self._brokers.pop(name, None)
        self._snapshots.pop(name, None)

    @property
    def broker_names(self) -> list[str]:
        return list(self._brokers.keys())

    def get_connector(self, name: str) -> BrokerConnector | None:
        return self._brokers.get(name)

    # -- lifecycle ----------------------------------------------------------

    async def connect_all(self) -> dict[str, bool]:
        """Connect all registered brokers. Returns success map."""
        results: dict[str, bool] = {}

        async def _connect(name: str, connector: BrokerConnector) -> None:
            try:
                await connector.connect()
                results[name] = True
            except Exception as exc:
                logger.error("account_manager_connect_failed", broker=name, error=str(exc))
                results[name] = False

        await asyncio.gather(
            *[_connect(n, c) for n, c in self._brokers.items()]
        )
        return results

    async def disconnect_all(self) -> None:
        """Disconnect all registered brokers."""
        await asyncio.gather(
            *[c.disconnect() for c in self._brokers.values()],
            return_exceptions=True,
        )

    # -- balance aggregation ------------------------------------------------

    async def get_broker_snapshot(self, name: str) -> BrokerAccountSnapshot:
        """Get a snapshot of a single broker's account."""
        connector = self._brokers.get(name)
        if connector is None:
            raise KeyError(f"Unknown broker: {name}")
        if not connector.is_connected:
            raise RuntimeError(f"Broker {name} is not connected")

        balance = await connector.get_balance()
        positions = await connector.get_positions()

        snapshot = BrokerAccountSnapshot(
            broker=name,
            balance=balance,
            positions=positions,
            open_position_count=len(positions),
            total_unrealized_pnl=sum(p.unrealized_pnl for p in positions),
            total_margin_used=sum(p.margin_used for p in positions),
        )
        self._snapshots[name] = snapshot
        return snapshot

    async def get_aggregate_balance(self) -> AggregateBalance:
        """Fetch and aggregate balances from all connected brokers.

        Returns
        -------
        AggregateBalance
            Unified view of all accounts with USD conversion.
        """
        tasks: dict[str, asyncio.Task[BrokerAccountSnapshot]] = {}

        for name, connector in self._brokers.items():
            if connector.is_connected:
                tasks[name] = asyncio.create_task(self.get_broker_snapshot(name))

        # Collect results with timeout
        snapshots: dict[str, BrokerAccountSnapshot] = {}
        for name, task in tasks.items():
            try:
                snapshots[name] = await asyncio.wait_for(task, timeout=15.0)
            except Exception as exc:
                logger.warning("account_manager_snapshot_failed", broker=name, error=str(exc))

        # Aggregate
        agg = AggregateBalance(broker_balances=snapshots)

        for name, snap in snapshots.items():
            currency = snap.balance.currency
            rate = self._get_rate(currency, self._default_currency)

            agg.total_equity += snap.equity
            agg.total_available += snap.available
            agg.total_margin_used += snap.total_margin_used
            agg.total_unrealized_pnl += snap.total_unrealized_pnl
            agg.total_equity_usd += snap.equity * rate
            agg.total_available_usd += snap.available * rate

        agg.timestamp = dt.datetime.now(dt.timezone.utc)
        return agg

    # -- position aggregation -----------------------------------------------

    async def get_all_positions(self) -> list[dict[str, Any]]:
        """Get all open positions across all brokers.

        Returns
        -------
        list[dict]
            Each dict includes position data plus broker name and USD value.
        """
        all_positions: list[dict[str, Any]] = []

        for name, connector in self._brokers.items():
            if not connector.is_connected:
                continue
            try:
                positions = await connector.get_positions()
                for pos in positions:
                    rate = self._get_rate(
                        self._snapshots.get(name, BrokerAccountSnapshot(broker=name, balance=BrokerBalance())).balance.currency,
                        self._default_currency,
                    )
                    all_positions.append({
                        "broker": name,
                        "symbol": pos.symbol,
                        "side": pos.side.value,
                        "quantity": pos.quantity,
                        "avg_entry": pos.avg_entry_price,
                        "current_price": pos.current_price,
                        "unrealized_pnl": pos.unrealized_pnl,
                        "unrealized_pnl_usd": pos.unrealized_pnl * rate,
                        "margin_used": pos.margin_used,
                        "leverage": pos.leverage,
                        "lot_size": pos.lot_size,
                    })
            except Exception as exc:
                logger.warning("account_manager_positions_failed", broker=name, error=str(exc))

        return all_positions

    # -- transaction tracking -----------------------------------------------

    def _next_tx_id(self) -> str:
        self._tx_counter += 1
        return f"TX-{self._tx_counter:06d}"

    def record_deposit(
        self,
        broker: str,
        amount: float,
        currency: str,
        description: str = "",
        reference: str = "",
    ) -> Transaction:
        """Record a deposit transaction.

        Parameters
        ----------
        broker : str
            Broker name.
        amount : float
            Deposit amount.
        currency : str
            Currency of the deposit.
        description : str
            Human-readable description.
        reference : str
            External reference (M-Pesa ID, TX hash, etc.).

        Returns
        -------
        Transaction
            The recorded transaction.
        """
        tx = Transaction(
            id=self._next_tx_id(),
            broker=broker,
            tx_type=TransactionType.DEPOSIT,
            amount=amount,
            currency=currency,
            description=description,
            reference=reference,
        )
        self._transactions.append(tx)
        logger.info(
            "account_manager_deposit_recorded",
            tx_id=tx.id,
            broker=broker,
            amount=amount,
            currency=currency,
        )
        return tx

    def record_withdrawal(
        self,
        broker: str,
        amount: float,
        currency: str,
        description: str = "",
        reference: str = "",
    ) -> Transaction:
        """Record a withdrawal transaction."""
        tx = Transaction(
            id=self._next_tx_id(),
            broker=broker,
            tx_type=TransactionType.WITHDRAWAL,
            amount=amount,
            currency=currency,
            description=description,
            reference=reference,
        )
        self._transactions.append(tx)
        logger.info(
            "account_manager_withdrawal_recorded",
            tx_id=tx.id,
            broker=broker,
            amount=amount,
            currency=currency,
        )
        return tx

    def record_transfer(
        self,
        from_broker: str,
        to_broker: str,
        amount: float,
        currency: str,
        description: str = "",
    ) -> tuple[Transaction, Transaction]:
        """Record an internal transfer between brokers.

        Returns
        -------
        tuple[Transaction, Transaction]
            (withdrawal from source, deposit to destination).
        """
        tx_out = Transaction(
            id=self._next_tx_id(),
            broker=from_broker,
            tx_type=TransactionType.TRANSFER,
            amount=amount,
            currency=currency,
            description=f"Transfer to {to_broker}: {description}",
            metadata={"destination": to_broker},
        )
        tx_in = Transaction(
            id=self._next_tx_id(),
            broker=to_broker,
            tx_type=TransactionType.TRANSFER,
            amount=amount,
            currency=currency,
            description=f"Transfer from {from_broker}: {description}",
            metadata={"source": from_broker},
        )
        self._transactions.extend([tx_out, tx_in])
        return tx_out, tx_in

    def complete_transaction(self, tx_id: str) -> Transaction | None:
        """Mark a transaction as completed."""
        for tx in self._transactions:
            if tx.id == tx_id:
                tx.complete()
                return tx
        return None

    def fail_transaction(self, tx_id: str, reason: str = "") -> Transaction | None:
        """Mark a transaction as failed."""
        for tx in self._transactions:
            if tx.id == tx_id:
                tx.fail(reason)
                return tx
        return None

    def get_transactions(
        self,
        broker: str | None = None,
        tx_type: TransactionType | None = None,
        status: TransactionStatus | None = None,
        limit: int = 100,
    ) -> list[Transaction]:
        """Get filtered transaction history.

        Parameters
        ----------
        broker : str | None
            Filter by broker name.
        tx_type : TransactionType | None
            Filter by transaction type.
        status : TransactionStatus | None
            Filter by status.
        limit : int
            Max results.

        Returns
        -------
        list[Transaction]
            Matching transactions, newest first.
        """
        result = self._transactions
        if broker:
            result = [t for t in result if t.broker == broker]
        if tx_type:
            result = [t for t in result if t.tx_type == tx_type]
        if status:
            result = [t for t in result if t.status == status]
        return sorted(result, key=lambda t: t.created_at, reverse=True)[:limit]

    def pending_deposits(self, broker: str | None = None) -> list[Transaction]:
        """Get all pending deposit transactions."""
        return self.get_transactions(
            broker=broker,
            tx_type=TransactionType.DEPOSIT,
            status=TransactionStatus.PENDING,
        )

    # -- currency conversion ------------------------------------------------

    def set_exchange_rate(self, pair: str, rate: float) -> None:
        """Set or update an exchange rate.

        Parameters
        ----------
        pair : str
            Currency pair in ``"FROM/TO"`` format (e.g. ``"KES/USD"``).
        rate : float
            Exchange rate.
        """
        self._exchange_rates[pair] = rate
        # Also set the inverse
        from_c, to_c = pair.split("/")
        self._exchange_rates[f"{to_c}/{from_c}"] = 1.0 / rate if rate else 0.0

    def _get_rate(self, from_currency: str, to_currency: str) -> float:
        """Get the conversion rate from one currency to another."""
        if from_currency == to_currency:
            return 1.0

        pair = f"{from_currency}/{to_currency}"
        rate = self._exchange_rates.get(pair)
        if rate is not None:
            return rate

        # Try reverse
        reverse_pair = f"{to_currency}/{from_currency}"
        reverse_rate = self._exchange_rates.get(reverse_pair)
        if reverse_rate and reverse_rate > 0:
            return 1.0 / reverse_rate

        # Try via USD
        if from_currency != "USD" and to_currency != "USD":
            from_usd = self._get_rate(from_currency, "USD")
            to_usd = self._get_rate("USD", to_currency)
            if from_usd > 0 and to_usd > 0:
                return from_usd * to_usd

        logger.warning(
            "account_manager_no_rate",
            from_currency=from_currency,
            to_currency=to_currency,
        )
        return 1.0  # Fallback: assume 1:1

    def convert_amount(
        self,
        amount: float,
        from_currency: str,
        to_currency: str | None = None,
    ) -> float:
        """Convert an amount between currencies.

        Parameters
        ----------
        amount : float
            Amount to convert.
        from_currency : str
            Source currency.
        to_currency : str | None
            Target currency (defaults to default_currency).

        Returns
        -------
        float
            Converted amount.
        """
        to_curr = to_currency or self._default_currency
        rate = self._get_rate(from_currency, to_curr)
        return amount * rate

    # -- portfolio analytics ------------------------------------------------

    async def portfolio_summary(self) -> dict[str, Any]:
        """Generate a comprehensive portfolio summary.

        Returns
        -------
        dict
            Portfolio metrics including allocations, P&L, and risk.
        """
        agg = await self.get_aggregate_balance()
        positions = await self.get_all_positions()

        # Asset allocation by broker
        allocations: dict[str, float] = {}
        for name, snap in agg.broker_balances.items():
            rate = self._get_rate(snap.balance.currency, "USD")
            allocations[name] = snap.equity * rate

        # Asset allocation by type (forex vs crypto)
        forex_exposure = 0.0
        crypto_exposure = 0.0
        for pos in positions:
            symbol = pos["symbol"]
            notional = abs(pos["quantity"] * pos["current_price"])
            if "/" in symbol and any(c in symbol for c in ["USD", "EUR", "GBP", "JPY", "CHF"]):
                forex_exposure += notional
            else:
                crypto_exposure += notional

        return {
            "total_equity_usd": agg.total_equity_usd,
            "total_available_usd": agg.total_available_usd,
            "total_unrealized_pnl": agg.total_unrealized_pnl,
            "open_positions": len(positions),
            "margin_utilization_pct": agg.margin_utilization_pct,
            "broker_allocations": allocations,
            "forex_exposure_usd": forex_exposure,
            "crypto_exposure_usd": crypto_exposure,
            "pending_deposits": len(self.pending_deposits()),
            "transaction_count": len(self._transactions),
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        }

    # -- diagnostics --------------------------------------------------------

    def status(self) -> dict[str, str]:
        """Return connection state of all registered brokers."""
        return {name: c.state.value for name, c in self._brokers.items()}

    def connected_brokers(self) -> list[str]:
        """Return names of connected brokers."""
        return [n for n, c in self._brokers.items() if c.is_connected]
