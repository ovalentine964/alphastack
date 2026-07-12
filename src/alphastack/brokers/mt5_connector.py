"""MetaTrader 5 connector.

Wraps the ``MetaTrader5`` Python package.  On Linux the MT5 terminal runs
under Wine or on a remote Windows VPS – see deployment notes at the bottom
of this file.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from concurrent.futures import ThreadPoolExecutor
from functools import partial
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
    TimeInForce,
)
from alphastack.core.config import get_settings

logger = structlog.get_logger(__name__)

# Lazy import – MetaTrader5 is optional and Windows-only
_mt5: Any = None

def _get_mt5() -> Any:
    global _mt5
    if _mt5 is None:
        import MetaTrader5 as mt5
        _mt5 = mt5
    return _mt5


# ---------------------------------------------------------------------------
# Mapping helpers
# ---------------------------------------------------------------------------

_ORDER_TYPE_MAP: dict[OrderType, int] = {
    OrderType.MARKET: 0,  # ORDER_TYPE_BUY / ORDER_TYPE_SELL chosen by side
    OrderType.LIMIT: 2,   # ORDER_TYPE_BUY_LIMIT / ORDER_TYPE_SELL_LIMIT
    OrderType.STOP: 4,    # ORDER_TYPE_BUY_STOP / ORDER_TYPE_SELL_STOP
    OrderType.STOP_LIMIT: 6,
    OrderType.TRAILING_STOP: 4,  # Mapped to stop; trailing done via comment
}

_ORDER_TYPE_MAP_SELL: dict[OrderType, int] = {
    OrderType.MARKET: 1,
    OrderType.LIMIT: 3,
    OrderType.STOP: 5,
    OrderType.STOP_LIMIT: 7,
    OrderType.TRAILING_STOP: 5,
}

_TIF_MAP: dict[TimeInForce, int] = {
    TimeInForce.GTC: 0,  # ORDER_TIME_GTC
    TimeInForce.DAY: 1,  # ORDER_TIME_DAY
    TimeInForce.IOC: 3,  # ORDER_TIME_SPECIFIED
    TimeInForce.FOK: 3,
}

_MT5_STATUS_MAP: dict[int, OrderStatus] = {
    0: OrderStatus.PENDING,    # ORDER_STATE_STARTED
    1: OrderStatus.OPEN,       # ORDER_STATE_PLACED
    2: OrderStatus.FILLED,     # ORDER_STATE_FILLED
    3: OrderStatus.CANCELLED,  # ORDER_STATE_CANCELED
    4: OrderStatus.EXPIRED,    # ORDER_STATE_EXPIRED
    5: OrderStatus.REJECTED,   # ORDER_STATE_REJECTED
}


def _resolve_order_type(order: BrokerOrder) -> int:
    if order.side == OrderSide.SELL:
        return _ORDER_TYPE_MAP_SELL.get(order.order_type, 1)
    return _ORDER_TYPE_MAP.get(order.order_type, 0)


def _bar_from_tick(tick: Any) -> BrokerTick:
    return BrokerTick(
        broker="mt5",
        symbol=tick.symbol if hasattr(tick, "symbol") else "",
        bid=getattr(tick, "bid", 0.0),
        ask=getattr(tick, "ask", 0.0),
        last=getattr(tick, "last", 0.0),
        volume=getattr(tick, "volume", 0.0),
        spread=getattr(tick, "spread", 0.0) * 1e-5,  # MT5 spread in points
        timestamp=dt.datetime.fromtimestamp(getattr(tick, "time", 0), tz=dt.timezone.utc),
    )


# ---------------------------------------------------------------------------
# MT5 Connector
# ---------------------------------------------------------------------------

class MT5Connector(BrokerConnector):
    """MetaTrader 5 broker connector.

    All heavy MT5 calls are offloaded to a thread pool because the
    MetaTrader5 Python package is synchronous / blocking.
    """

    def __init__(
        self,
        *,
        login: int | None = None,
        password: str | None = None,
        server: str | None = None,
        path: str | None = None,
        timeout: int = 60_000,
        max_workers: int = 4,
    ) -> None:
        super().__init__("mt5", max_retries=3, retry_delay=2.0)
        cfg = get_settings().mt5
        self._login = login or cfg.login
        self._password = password or cfg.password.get_secret_value()
        self._server = server or cfg.server
        self._path = path or cfg.path
        self._timeout = timeout
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="mt5")
        self._connected_once = False

    # -- helpers ------------------------------------------------------------

    async def _run(self, fn: Any, *args: Any, **kwargs: Any) -> Any:
        """Run a blocking MT5 function in the thread pool."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, partial(fn, *args, **kwargs))

    def _ensure_connected(self) -> None:
        if not self.is_connected:
            raise RuntimeError("MT5 is not connected")

    # -- lifecycle ----------------------------------------------------------

    async def connect(self) -> None:
        self._transition(ConnectionState.CONNECTING)
        mt5 = _get_mt5()

        init_kwargs: dict[str, Any] = {"timeout": self._timeout}
        if self._login:
            init_kwargs["login"] = self._login
        if self._password:
            init_kwargs["password"] = self._password
        if self._server:
            init_kwargs["server"] = self._server
        if self._path:
            init_kwargs["path"] = self._path

        ok = await self._run(mt5.initialize, **init_kwargs)
        if not ok:
            err = await self._run(mt5.last_error)
            self._transition(ConnectionState.ERROR)
            raise ConnectionError(f"MT5 init failed: {err}")

        if self._login:
            authorized = await self._run(mt5.login, self._login, self._password, self._server)
            if not authorized:
                err = await self._run(mt5.last_error)
                self._transition(ConnectionState.ERROR)
                raise ConnectionError(f"MT5 login failed: {err}")

        self._transition(ConnectionState.CONNECTED)
        self._connected_once = True
        logger.info("mt5_connected", login=self._login, server=self._server)

    async def disconnect(self) -> None:
        mt5 = _get_mt5()
        await self._run(mt5.shutdown)
        self._transition(ConnectionState.DISCONNECTED)
        logger.info("mt5_disconnected")

    # -- orders -------------------------------------------------------------

    async def place_order(self, order: BrokerOrder) -> BrokerOrder:
        self._ensure_connected()
        mt5 = _get_mt5()

        action = 1 if order.order_type == OrderType.MARKET else 0  # TRADE_ACTION_DEAL vs TRADE_ACTION_PENDING
        req: dict[str, Any] = {
            "action": action,
            "symbol": order.symbol,
            "volume": order.quantity,
            "type": _resolve_order_type(order),
            "magic": order.magic_number,
            "comment": order.comment or f"AS:{order.id}",
        }

        if order.order_type == OrderType.MARKET:
            # Use market price
            tick = await self._run(mt5.symbol_info_tick, order.symbol)
            req["price"] = tick.ask if order.side == OrderSide.BUY else tick.bid
        else:
            req["price"] = order.price or 0.0
            req["type_time"] = _TIF_MAP.get(order.time_in_force, 0)
            req["type_filling"] = 2  # ORDER_FILLING_IOC

        if order.stop_loss:
            req["sl"] = order.stop_loss
        if order.take_profit:
            req["tp"] = order.take_profit

        result = await self._run(mt5.order_send, req)
        if result is None:
            err = await self._run(mt5.last_error)
            order.status = OrderStatus.REJECTED
            order.raw = {"error": str(err)}
            logger.error("mt5_order_rejected", order_id=order.id, error=str(err))
            return order

        result_dict = result._asdict() if hasattr(result, "_asdict") else dict(result)
        order.raw = result_dict
        retcode = result_dict.get("retcode", 0)

        if retcode == 10009:  # TRADE_RETCODE_DONE
            order.broker_order_id = str(result_dict.get("order", ""))
            order.status = OrderStatus.FILLED if order.order_type == OrderType.MARKET else OrderStatus.OPEN
            order.avg_fill_price = result_dict.get("price", 0.0)
            order.filled_quantity = result_dict.get("volume", order.quantity)
            logger.info(
                "mt5_order_placed",
                order_id=order.id,
                broker_order_id=order.broker_order_id,
                status=order.status.value,
            )
        else:
            order.status = OrderStatus.REJECTED
            logger.warning(
                "mt5_order_failed",
                order_id=order.id,
                retcode=retcode,
                comment=result_dict.get("comment", ""),
            )

        order.updated_at = dt.datetime.now(dt.timezone.utc)
        return order

    async def cancel_order(self, order_id: str) -> BrokerOrder:
        self._ensure_connected()
        mt5 = _get_mt5()

        req = {
            "action": 2,  # TRADE_ACTION_REMOVE
            "order": int(order_id),
        }
        result = await self._run(mt5.order_send, req)

        order = BrokerOrder(broker_order_id=order_id, broker="mt5", status=OrderStatus.CANCELLED)
        if result:
            result_dict = result._asdict() if hasattr(result, "_asdict") else dict(result)
            order.raw = result_dict
            if result_dict.get("retcode") != 10009:
                order.status = OrderStatus.REJECTED
        order.updated_at = dt.datetime.now(dt.timezone.utc)
        return order

    async def modify_order(
        self,
        order_id: str,
        *,
        price: float | None = None,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        quantity: float | None = None,
    ) -> BrokerOrder:
        self._ensure_connected()
        mt5 = _get_mt5()

        # Fetch current order to get symbol and existing values
        orders = await self._run(mt5.orders_get, ticket=int(order_id))
        if not orders:
            raise ValueError(f"Order {order_id} not found")

        o = orders[0]
        req: dict[str, Any] = {
            "action": 3,  # TRADE_ACTION_MODIFY
            "order": int(order_id),
            "price": price if price is not None else o.price_open,
            "sl": stop_loss if stop_loss is not None else o.sl,
            "tp": take_profit if take_profit is not None else o.tp,
        }

        result = await self._run(mt5.order_send, req)
        order = BrokerOrder(broker_order_id=order_id, broker="mt5")
        if result:
            result_dict = result._asdict() if hasattr(result, "_asdict") else dict(result)
            order.raw = result_dict
            order.status = OrderStatus.OPEN if result_dict.get("retcode") == 10009 else OrderStatus.REJECTED
        order.updated_at = dt.datetime.now(dt.timezone.utc)
        return order

    # -- account ------------------------------------------------------------

    async def get_positions(self) -> list[BrokerPosition]:
        self._ensure_connected()
        mt5 = _get_mt5()
        positions = await self._run(mt5.positions_get)
        if not positions:
            return []

        result: list[BrokerPosition] = []
        for p in positions:
            result.append(BrokerPosition(
                broker="mt5",
                symbol=p.symbol,
                side=PositionSide.LONG if p.type == 0 else PositionSide.SHORT,
                quantity=p.volume,
                avg_entry_price=p.price_open,
                current_price=p.price_current,
                unrealized_pnl=p.profit,
                margin_used=p.margin,
                magic_number=p.magic,
                raw=p._asdict() if hasattr(p, "_asdict") else {},
            ))
        return result

    async def get_balance(self) -> BrokerBalance:
        self._ensure_connected()
        mt5 = _get_mt5()
        info = await self._run(mt5.account_info)
        if info is None:
            raise RuntimeError("Failed to fetch MT5 account info")
        d = info._asdict() if hasattr(info, "_asdict") else {}
        return BrokerBalance(
            broker="mt5",
            currency=d.get("currency", "USD"),
            total=d.get("balance", 0.0),
            available=d.get("margin_free", 0.0),
            used_margin=d.get("margin", 0.0),
            free_margin=d.get("margin_free", 0.0),
            equity=d.get("equity", 0.0),
            unrealized_pnl=d.get("profit", 0.0),
            margin_level=d.get("margin_level", 0.0),
            raw=d,
        )

    # -- market data --------------------------------------------------------

    async def get_tick(self, symbol: str) -> BrokerTick:
        self._ensure_connected()
        mt5 = _get_mt5()
        tick = await self._run(mt5.symbol_info_tick, symbol)
        if tick is None:
            raise ValueError(f"No tick data for {symbol}")
        bt = _bar_from_tick(tick)
        bt.symbol = symbol
        return bt

    async def get_bars(
        self, symbol: str, timeframe: str, count: int = 500
    ) -> list[BrokerBar]:
        self._ensure_connected()
        mt5 = _get_mt5()

        tf_map: dict[str, int] = {
            "M1": 1, "M5": 5, "M15": 15, "M30": 30,
            "H1": 16385, "H4": 16388, "D1": 16408, "W1": 32769, "MN1": 49153,
        }
        mt5_tf = tf_map.get(timeframe.upper(), 16385)  # Default H1

        rates = await self._run(mt5.copy_rates_from_pos, symbol, mt5_tf, 0, count)
        if rates is None or len(rates) == 0:
            return []

        bars: list[BrokerBar] = []
        for r in rates:
            bars.append(BrokerBar(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=dt.datetime.fromtimestamp(r["time"], tz=dt.timezone.utc),
                open=r["open"],
                high=r["high"],
                low=r["low"],
                close=r["close"],
                volume=r["tick_volume"],
                tick_volume=r["tick_volume"],
                spread=r["spread"] * 1e-5,
            ))
        return bars


# ---------------------------------------------------------------------------
# Linux deployment notes
# ---------------------------------------------------------------------------
#
# MetaTrader 5's Python package only works on Windows.  To run on Linux:
#
# Option A – Wine
#   1. Install Wine (≥ 8.x) on your Linux server.
#   2. Install MT5 terminal under Wine (``wine mt5setup.exe``).
#   3. Install the Python package inside the same Wine prefix:
#        wine pip install MetaTrader5
#   4. Set ``MT5_PATH`` to the Wine-launched terminal64.exe.
#
# Option B – Remote Windows VPS
#   1. Rent a small Windows VPS (AWS, Azure, Vultr).
#   2. Run MT5 + the connector on the VPS.
#   3. Expose the connector's FastAPI/GRPC endpoint over TLS.
#   4. The Linux AlphaStack host connects remotely.
#
# Option C – MT5 Gateway Bridge
#   Use an open-source bridge (e.g. mt5-python-bridge) that exposes a REST
#   API from a Windows box, consumed by this connector on Linux.
# ---------------------------------------------------------------------------
