"""Unified Order Manager – single source of truth for all orders across brokers.

Tracks the full lifecycle of every order (pending → open → partially_filled →
filled / cancelled / rejected) and provides persistence hooks.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Callable, Coroutine

import structlog

from alphastack.brokers.models import BrokerOrder, OrderStatus

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Persistence callback type
# ---------------------------------------------------------------------------

PersistFn = Callable[[BrokerOrder], Coroutine[Any, Any, None]]


# ---------------------------------------------------------------------------
# Order Manager
# ---------------------------------------------------------------------------

class OrderManager:
    """In-memory order registry with optional persistence callbacks.

    The manager does **not** talk to brokers directly – it is a bookkeeper
    that the registry / smart router update after each broker interaction.
    """

    def __init__(self, *, on_change: PersistFn | None = None) -> None:
        # order.id → BrokerOrder
        self._orders: dict[str, BrokerOrder] = {}
        # broker_order_id → order.id (reverse lookup)
        self._broker_index: dict[str, str] = {}
        # Persist callback (e.g. write to DB)
        self._on_change = on_change

    # -- CRUD ---------------------------------------------------------------

    def register(self, order: BrokerOrder) -> None:
        """Register a new order with the manager."""
        self._orders[order.id] = order
        if order.broker_order_id:
            self._broker_index[order.broker_order_id] = order.id
        logger.info(
            "order_registered",
            order_id=order.id,
            broker=order.broker,
            symbol=order.symbol,
            status=order.status.value,
        )
        self._persist(order)

    def get(self, order_id: str) -> BrokerOrder | None:
        return self._orders.get(order_id)

    def get_by_broker_id(self, broker_order_id: str) -> BrokerOrder | None:
        oid = self._broker_index.get(broker_order_id)
        if oid:
            return self._orders.get(oid)
        return None

    def remove(self, order_id: str) -> BrokerOrder | None:
        order = self._orders.pop(order_id, None)
        if order and order.broker_order_id:
            self._broker_index.pop(order.broker_order_id, None)
        return order

    # -- lifecycle updates --------------------------------------------------

    def update_status(self, order_id: str, status: OrderStatus, **kwargs: Any) -> BrokerOrder | None:
        """Update an order's status and optional fields."""
        order = self._orders.get(order_id)
        if order is None:
            return None

        old_status = order.status
        order.status = status
        order.updated_at = dt.datetime.now(dt.timezone.utc)

        if "filled_quantity" in kwargs:
            order.filled_quantity = kwargs["filled_quantity"]
        if "avg_fill_price" in kwargs:
            order.avg_fill_price = kwargs["avg_fill_price"]
        if "commission" in kwargs:
            order.commission = kwargs["commission"]
        if "slippage" in kwargs:
            order.slippage = kwargs["slippage"]
        if "broker_order_id" in kwargs:
            order.broker_order_id = kwargs["broker_order_id"]
            self._broker_index[order.broker_order_id] = order.id
        if "raw" in kwargs:
            order.raw = kwargs["raw"]

        if status == OrderStatus.FILLED and old_status != OrderStatus.FILLED:
            order.filled_at = dt.datetime.now(dt.timezone.utc)

        logger.info(
            "order_status_updated",
            order_id=order_id,
            old_status=old_status.value,
            new_status=status.value,
            filled=order.filled_quantity,
        )

        self._persist(order)
        return order

    def record_partial_fill(
        self,
        order_id: str,
        fill_qty: float,
        fill_price: float,
        commission: float = 0.0,
    ) -> BrokerOrder | None:
        """Record a partial fill event."""
        order = self._orders.get(order_id)
        if order is None:
            return None

        order.filled_quantity += fill_qty
        if order.avg_fill_price == 0:
            order.avg_fill_price = fill_price
        else:
            # Weighted average
            total_filled = order.filled_quantity
            prev_filled = total_filled - fill_qty
            order.avg_fill_price = (
                (order.avg_fill_price * prev_filled + fill_price * fill_qty) / total_filled
            )
        order.commission += commission
        order.updated_at = dt.datetime.now(dt.timezone.utc)

        if order.filled_quantity >= order.quantity:
            order.status = OrderStatus.FILLED
            order.filled_at = dt.datetime.now(dt.timezone.utc)
        else:
            order.status = OrderStatus.PARTIALLY_FILLED

        logger.info(
            "partial_fill",
            order_id=order_id,
            fill_qty=fill_qty,
            fill_price=fill_price,
            total_filled=order.filled_quantity,
            status=order.status.value,
        )

        self._persist(order)
        return order

    # -- queries ------------------------------------------------------------

    @property
    def active_orders(self) -> list[BrokerOrder]:
        return [o for o in self._orders.values() if o.is_active]

    @property
    def filled_orders(self) -> list[BrokerOrder]:
        return [o for o in self._orders.values() if o.status == OrderStatus.FILLED]

    @property
    def all_orders(self) -> list[BrokerOrder]:
        return list(self._orders.values())

    def orders_for_broker(self, broker: str) -> list[BrokerOrder]:
        return [o for o in self._orders.values() if o.broker == broker]

    def orders_for_symbol(self, symbol: str) -> list[BrokerOrder]:
        return [o for o in self._orders.values() if o.symbol == symbol]

    @property
    def count(self) -> int:
        return len(self._orders)

    @property
    def active_count(self) -> int:
        return sum(1 for o in self._orders.values() if o.is_active)

    # -- persistence --------------------------------------------------------

    def _persist(self, order: BrokerOrder) -> None:
        """Fire-and-forget persistence callback."""
        if self._on_change:
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._on_change(order))
            except RuntimeError:
                pass  # No event loop – skip

    # -- snapshot / restore -------------------------------------------------

    def snapshot(self) -> list[dict[str, Any]]:
        """Serialize all orders to dicts (for persistence)."""
        return [o.model_dump(mode="json") for o in self._orders.values()]

    def restore(self, orders_data: list[dict[str, Any]]) -> int:
        """Restore orders from serialized dicts. Returns count restored."""
        count = 0
        for d in orders_data:
            order = BrokerOrder.model_validate(d)
            self.register(order)
            count += 1
        return count
