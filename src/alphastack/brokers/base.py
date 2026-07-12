"""BrokerConnector – abstract base class for all broker integrations."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any

import structlog

from alphastack.brokers.models import (
    BrokerBalance,
    BrokerBar,
    BrokerOrder,
    BrokerPosition,
    BrokerTick,
)

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Connection state machine
# ---------------------------------------------------------------------------

class ConnectionState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Retry helper
# ---------------------------------------------------------------------------

async def _retry_async(
    coro_factory: Any,
    *,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
) -> Any:
    """Execute *coro_factory()* with exponential-backoff retries."""
    last_exc: Exception | None = None
    delay = base_delay
    for attempt in range(1, max_retries + 1):
        try:
            return await coro_factory()
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "retry_attempt",
                attempt=attempt,
                max_retries=max_retries,
                delay=delay,
                error=str(exc),
            )
            if attempt < max_retries:
                await asyncio.sleep(delay)
                delay = min(delay * backoff_factor, max_delay)
    raise last_exc  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ABC
# ---------------------------------------------------------------------------

class BrokerConnector(ABC):
    """Unified interface that every broker connector must implement.

    Implementations should be **async** – all I/O-bound methods return
    ``await``-ables so callers can compose them with ``asyncio.gather``.
    """

    def __init__(self, name: str, *, max_retries: int = 3, retry_delay: float = 1.0) -> None:
        self.name = name
        self._state = ConnectionState.DISCONNECTED
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._reconnect_task: asyncio.Task[None] | None = None

    # -- properties ---------------------------------------------------------

    @property
    def state(self) -> ConnectionState:
        return self._state

    @property
    def is_connected(self) -> bool:
        return self._state == ConnectionState.CONNECTED

    # -- lifecycle ----------------------------------------------------------

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the broker."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Gracefully close the connection."""

    async def reconnect(self) -> None:
        """Attempt to re-establish connection after a drop."""
        logger.info("reconnecting", broker=self.name)
        self._state = ConnectionState.RECONNECTING
        try:
            await self.disconnect()
        except Exception:
            pass  # Best-effort disconnect
        try:
            await self.connect()
        except Exception as exc:
            self._state = ConnectionState.ERROR
            logger.error("reconnect_failed", broker=self.name, error=str(exc))
            raise

    # -- orders -------------------------------------------------------------

    @abstractmethod
    async def place_order(self, order: BrokerOrder) -> BrokerOrder:
        """Submit an order and return the updated model with broker-assigned ID."""

    @abstractmethod
    async def cancel_order(self, order_id: str) -> BrokerOrder:
        """Cancel an active order by its broker-assigned ID."""

    @abstractmethod
    async def modify_order(
        self,
        order_id: str,
        *,
        price: float | None = None,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        quantity: float | None = None,
    ) -> BrokerOrder:
        """Modify an existing order's parameters."""

    # -- account ------------------------------------------------------------

    @abstractmethod
    async def get_positions(self) -> list[BrokerPosition]:
        """Return all open positions."""

    @abstractmethod
    async def get_balance(self) -> BrokerBalance:
        """Return current account balance."""

    # -- market data --------------------------------------------------------

    @abstractmethod
    async def get_tick(self, symbol: str) -> BrokerTick:
        """Return the latest tick/quote for *symbol*."""

    @abstractmethod
    async def get_bars(
        self, symbol: str, timeframe: str, count: int = 500
    ) -> list[BrokerBar]:
        """Return historical OHLCV bars."""

    # -- retry wrappers (call from subclasses) ------------------------------

    async def _with_retry(self, coro_factory: Any) -> Any:
        """Run *coro_factory* with the connector's retry settings."""
        return await _retry_async(
            coro_factory,
            max_retries=self._max_retries,
            base_delay=self._retry_delay,
        )

    # -- helpers ------------------------------------------------------------

    def _transition(self, new_state: ConnectionState) -> None:
        old = self._state
        self._state = new_state
        if old != new_state:
            logger.info(
                "connection_state_change",
                broker=self.name,
                old=old.value,
                new=new_state.value,
            )

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r} state={self._state.value!r}>"
