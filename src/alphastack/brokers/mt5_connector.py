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
# MT5 error codes (for readable messages)
# ---------------------------------------------------------------------------

_MT5_ERROR_NAMES: dict[int, str] = {
    10004: "Requote – price changed",
    10006: "Request rejected",
    10007: "Request cancelled by trader",
    10008: "Order placed",
    10009: "Request completed",
    10010: "Request partially completed",
    10011: "Request processing error",
    10012: "Request cancelled by timeout",
    10013: "Invalid request",
    10014: "Invalid volume",
    10015: "Invalid price",
    10016: "Invalid stops",
    10017: "Trade disabled",
    10018: "Market closed",
    10019: "Not enough money",
    10020: "Price changed",
    10021: "No prices available",
    10022: "Invalid expiration",
    10023: "Order state changed",
    10024: "Too frequent requests",
    10025: "No changes",
    10026: "Autotrading disabled by server",
    10027: "Autotrading disabled by client",
    10028: "Request locked",
    10029: "Order/position frozen",
    10030: "Invalid fill type",
}


def _describe_mt5_error(retcode: int) -> str:
    """Return a human-readable description for an MT5 return code."""
    name = _MT5_ERROR_NAMES.get(retcode, "Unknown error")
    return f"[{retcode}] {name}"


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
        magic_number: int = 20260713,
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
        self._magic = magic_number
        # Cache of symbol point sizes for dynamic spread conversion
        self._symbol_points: dict[str, float] = {}

    # -- helpers ------------------------------------------------------------

    async def _run(self, fn: Any, *args: Any, **kwargs: Any) -> Any:
        """Run a blocking MT5 function in the thread pool."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, partial(fn, *args, **kwargs))

    def _ensure_connected(self) -> None:
        if not self.is_connected:
            raise RuntimeError("MT5 is not connected")

    def _get_point(self, symbol: str) -> float:
        """Return the cached point size for *symbol*, defaulting to 1e-5."""
        return self._symbol_points.get(symbol, 1e-5)

    def _spread_in_price(self, spread_points: int, symbol: str) -> float:
        """Convert MT5 spread (in points) to price difference."""
        return spread_points * self._get_point(symbol)

    # -- symbol info --------------------------------------------------------

    async def get_symbol_info(self, symbol: str) -> dict[str, Any]:
        """Return symbol properties (pip size, contract size, lot limits, etc.).

        Also updates the internal point-size cache used for spread conversion.
        """
        self._ensure_connected()
        mt5 = _get_mt5()
        info = await self._run(mt5.symbol_info, symbol)
        if info is None:
            raise ValueError(f"Symbol {symbol} not found in MT5")

        d = info._asdict() if hasattr(info, "_asdict") else {}
        point: float = d.get("point", 1e-5)
        digits: int = d.get("digits", 5)

        # Update point cache
        self._symbol_points[symbol] = point

        return {
            "symbol": symbol,
            "point": point,
            "digits": digits,
            "pip_size": point * 10 if digits in (3, 5) else point,  # pip = 10 points for 3/5-digit
            "trade_contract_size": d.get("trade_contract_size", 100000),
            "volume_min": d.get("volume_min", 0.01),
            "volume_max": d.get("volume_max", 100.0),
            "volume_step": d.get("volume_step", 0.01),
            "trade_tick_value": d.get("trade_tick_value", 0.0),
            "trade_tick_size": d.get("trade_tick_size", 0.0),
            "swap_long": d.get("swap_long", 0.0),
            "swap_short": d.get("swap_short", 0.0),
            "margin_initial": d.get("margin_initial", 0.0),
            "margin_maintenance": d.get("margin_maintenance", 0.0),
            "spread": d.get("spread", 0),
        }

    async def pip_size(self, symbol: str) -> float:
        """Return the pip size for *symbol* (0.0001 for most, 0.01 for JPY)."""
        info = await self.get_symbol_info(symbol)
        return info["pip_size"]

    async def contract_size(self, symbol: str) -> float:
        """Return the contract size for *symbol* (typically 100000)."""
        info = await self.get_symbol_info(symbol)
        return info["trade_contract_size"]

    async def min_lot(self, symbol: str) -> float:
        """Return the minimum tradeable lot size for *symbol*."""
        info = await self.get_symbol_info(symbol)
        return info["volume_min"]

    async def _warm_symbol_cache(self, symbols: list[str] | None = None) -> None:
        """Pre-populate point-size cache for *symbols* (or all visible symbols)."""
        mt5 = _get_mt5()
        if symbols is None:
            all_info = await self._run(mt5.symbols_get)
            symbols = [s.name for s in (all_info or [])]
        for sym in symbols:
            try:
                await self.get_symbol_info(sym)
            except Exception:
                pass  # Skip symbols that fail

    # -- tick helper --------------------------------------------------------

    def _tick_from_mt5(self, tick: Any, symbol: str | None = None) -> BrokerTick:
        """Convert an MT5 tick struct to a BrokerTick with dynamic spread."""
        sym = symbol or getattr(tick, "symbol", "")
        point = self._get_point(sym)
        spread_raw = getattr(tick, "spread", 0)
        bid = getattr(tick, "bid", 0.0)
        ask = getattr(tick, "ask", 0.0)

        # last may be 0 for forex (only bid/ask); fall back to mid
        last = getattr(tick, "last", 0.0)
        if not last and bid and ask:
            last = (bid + ask) / 2.0

        return BrokerTick(
            broker="mt5",
            symbol=sym,
            bid=bid,
            ask=ask,
            last=last,
            volume=getattr(tick, "volume_real", 0.0) or getattr(tick, "volume", 0.0),
            spread=spread_raw * point,
            timestamp=dt.datetime.fromtimestamp(getattr(tick, "time", 0), tz=dt.timezone.utc),
        )

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
            err_desc = f"code={err[0]}, msg={err[1]}" if err else "unknown"
            raise ConnectionError(
                f"MT5 initialize() failed – {err_desc}.  "
                "Check that the MT5 terminal is running and the path is correct."
            )

        if self._login:
            authorized = await self._run(mt5.login, self._login, self._password, self._server)
            if not authorized:
                err = await self._run(mt5.last_error)
                self._transition(ConnectionState.ERROR)
                err_desc = f"code={err[0]}, msg={err[1]}" if err else "unknown"
                raise ConnectionError(
                    f"MT5 login({self._login}) failed – {err_desc}.  "
                    "Verify login/password/server are correct and the account is active."
                )

        # Warm symbol cache for common forex pairs
        try:
            await self._warm_symbol_cache()
        except Exception as exc:
            logger.warning("mt5_symbol_cache_warm_failed", error=str(exc))

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
            "deviation": 10,  # Max slippage in points – critical for forex
            "magic": order.magic_number or self._magic,
            "comment": order.comment or f"AS:{order.id}",
        }

        if order.order_type == OrderType.MARKET:
            tick = await self._run(mt5.symbol_info_tick, order.symbol)
            req["price"] = tick.ask if order.side == OrderSide.BUY else tick.bid
            req["type_filling"] = 2  # ORDER_FILLING_IOC
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
            order.raw["error_description"] = _describe_mt5_error(retcode)
            logger.warning(
                "mt5_order_failed",
                order_id=order.id,
                retcode=retcode,
                description=_describe_mt5_error(retcode),
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
                order.raw["error_description"] = _describe_mt5_error(result_dict.get("retcode", 0))
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
            retcode = result_dict.get("retcode", 0)
            order.status = OrderStatus.OPEN if retcode == 10009 else OrderStatus.REJECTED
            if retcode != 10009:
                order.raw["error_description"] = _describe_mt5_error(retcode)
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
                swap=p.swap,  # Accumulated swap/rollover fees
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
        return self._tick_from_mt5(tick, symbol)

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

        point = self._get_point(symbol)
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
                spread=r["spread"] * point,  # Dynamic point-based conversion
            ))
        return bars

    # -- historical trades --------------------------------------------------

    async def get_history_deals(
        self,
        *,
        from_time: dt.datetime | None = None,
        to_time: dt.datetime | None = None,
        group: str = "*",
    ) -> list[dict[str, Any]]:
        """Retrieve historical deals (executed trades) from MT5.

        Parameters
        ----------
        from_time : datetime, optional
            Start of the query window. Defaults to 30 days ago.
        to_time : datetime, optional
            End of the query window. Defaults to now.
        group : str
            Symbol filter (``"*"`` for all).  Supports wildcards like ``"EUR*"``.

        Returns
        -------
        list[dict]
            Each dict contains deal fields: ticket, order, time, type, entry,
            symbol, volume, price, commission, swap, profit, magic, comment.
        """
        self._ensure_connected()
        mt5 = _get_mt5()

        if from_time is None:
            from_time = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=30)
        if to_time is None:
            to_time = dt.datetime.now(dt.timezone.utc)

        deals = await self._run(
            mt5.history_deals_get, from_time, to_time, group=group,
        )
        if deals is None:
            return []

        return [d._asdict() if hasattr(d, "_asdict") else dict(d) for d in deals]

    async def get_history_orders(
        self,
        *,
        from_time: dt.datetime | None = None,
        to_time: dt.datetime | None = None,
        group: str = "*",
    ) -> list[dict[str, Any]]:
        """Retrieve historical orders (including pending/cancelled) from MT5.

        Same parameters as ``get_history_deals``.
        """
        self._ensure_connected()
        mt5 = _get_mt5()

        if from_time is None:
            from_time = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=30)
        if to_time is None:
            to_time = dt.datetime.now(dt.timezone.utc)

        orders = await self._run(
            mt5.history_orders_get, from_time, to_time, group=group,
        )
        if orders is None:
            return []

        return [o._asdict() if hasattr(o, "_asdict") else dict(o) for o in orders]


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
