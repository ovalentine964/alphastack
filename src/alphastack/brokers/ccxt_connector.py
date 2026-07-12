"""CCXT connector – unified crypto exchange access.

Supports any exchange available in the ``ccxt`` library (Binance, Bybit,
MEXC, OKX, etc.) with optional WebSocket streaming for real-time data.
"""

from __future__ import annotations

import asyncio
import datetime as dt
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
from alphastack.core.config import get_settings

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Status mapping
# ---------------------------------------------------------------------------

_CCXT_STATUS_MAP: dict[str, OrderStatus] = {
    "open": OrderStatus.OPEN,
    "closed": OrderStatus.FILLED,
    "canceled": OrderStatus.CANCELLED,
    "cancelled": OrderStatus.CANCELLED,
    "expired": OrderStatus.EXPIRED,
    "rejected": OrderStatus.REJECTED,
}


# ---------------------------------------------------------------------------
# Rate-limiter helper
# ---------------------------------------------------------------------------

class _RateLimiter:
    """Simple token-bucket rate limiter for exchange APIs."""

    def __init__(self, requests_per_second: float = 10.0) -> None:
        self._interval = 1.0 / requests_per_second
        self._lock = asyncio.Lock()
        self._last: float = 0.0

    async def acquire(self) -> None:
        async with self._lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self._last
            if elapsed < self._interval:
                await asyncio.sleep(self._interval - elapsed)
            self._last = asyncio.get_event_loop().time()


# ---------------------------------------------------------------------------
# CCXT Connector
# ---------------------------------------------------------------------------

class CCXTConnector(BrokerConnector):
    """CCXT-based connector supporting any ccxt-compatible exchange.

    Parameters
    ----------
    exchange_id : str
        CCXT exchange id (``"binance"``, ``"bybit"``, ``"mexc"``, …).
    api_key, secret, passphrase : str | None
        Exchange credentials. Falls back to ``CCXT_*`` env vars.
    sandbox : bool
        Use exchange testnet/sandbox mode.
    rate_limit : float
        Max API requests per second (auto-detected from ccxt if ``0``).
    ws_enabled : bool
        Enable WebSocket for real-time tick streaming.
    """

    def __init__(
        self,
        exchange_id: str | None = None,
        *,
        api_key: str | None = None,
        secret: str | None = None,
        passphrase: str | None = None,
        sandbox: bool | None = None,
        rate_limit: float = 0.0,
        ws_enabled: bool = True,
    ) -> None:
        cfg = get_settings().ccxt
        self._exchange_id = (exchange_id or cfg.exchange).lower()
        self._api_key = api_key or cfg.api_key.get_secret_value()
        self._secret = secret or cfg.secret.get_secret_value()
        self._passphrase = passphrase or (cfg.passphrase.get_secret_value() if cfg.passphrase else None)
        self._sandbox = sandbox if sandbox is not None else cfg.sandbox
        self._ws_enabled = ws_enabled

        super().__init__(f"ccxt:{self._exchange_id}", max_retries=3, retry_delay=2.0)

        self._exchange: Any = None
        self._ws: Any = None
        self._limiter = _RateLimiter(rate_limit or 10.0)
        self._tick_cache: dict[str, BrokerTick] = {}

    # -- helpers ------------------------------------------------------------

    def _ensure_exchange(self) -> Any:
        if self._exchange is None:
            raise RuntimeError(f"CCXT exchange {self._exchange_id} is not initialized")
        return self._exchange

    async def _api(self, method: str, *args: Any, **kwargs: Any) -> Any:
        """Call an exchange method with rate limiting and retries."""
        ex = self._ensure_exchange()

        async def _call() -> Any:
            await self._limiter.acquire()
            fn = getattr(ex, method)
            return fn(*args, **kwargs)

        return await self._with_retry(_call)

    # -- lifecycle ----------------------------------------------------------

    async def connect(self) -> None:
        self._transition(ConnectionState.CONNECTING)

        try:
            import ccxt.async_support as ccxt_async
        except ImportError:
            import ccxt as ccxt_sync  # Fallback
            ccxt_async = ccxt_sync

        exchange_class = getattr(ccxt_async, self._exchange_id, None)
        if exchange_class is None:
            raise ValueError(f"Unknown CCXT exchange: {self._exchange_id}")

        config: dict[str, Any] = {
            "apiKey": self._api_key or None,
            "secret": self._secret or None,
            "enableRateLimit": True,
        }
        if self._passphrase:
            config["password"] = self._passphrase

        self._exchange = exchange_class(config)

        if self._sandbox:
            self._exchange.set_sandbox_mode(True)
            logger.info("ccxt_sandbox_enabled", exchange=self._exchange_id)

        # Verify connectivity
        await self._api("load_markets")
        self._transition(ConnectionState.CONNECTED)
        logger.info("ccxt_connected", exchange=self._exchange_id, sandbox=self._sandbox)

    async def disconnect(self) -> None:
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

        if self._exchange:
            await self._exchange.close()
            self._exchange = None

        self._transition(ConnectionState.DISCONNECTED)
        logger.info("ccxt_disconnected", exchange=self._exchange_id)

    # -- orders -------------------------------------------------------------

    async def place_order(self, order: BrokerOrder) -> BrokerOrder:
        ex = self._ensure_exchange()

        order_type = order.order_type.value
        side = order.side.value
        symbol = order.symbol

        params: dict[str, Any] = {}
        if order.stop_loss:
            params["stopLoss"] = {"triggerPrice": order.stop_loss}
        if order.take_profit:
            params["takeProfit"] = {"triggerPrice": order.take_profit}
        if order.time_in_force.value != "gtc":
            params["timeInForce"] = order.time_in_force.value.upper()
        if order.comment:
            params["clientOrderId"] = order.comment

        try:
            result = await self._api(
                "create_order",
                symbol,
                order_type,
                side,
                order.quantity,
                order.price,
                params,
            )

            order.broker_order_id = str(result.get("id", ""))
            raw_status = result.get("status", "open")
            order.status = _CCXT_STATUS_MAP.get(raw_status, OrderStatus.OPEN)
            order.avg_fill_price = float(result.get("average") or result.get("price") or 0)
            order.filled_quantity = float(result.get("filled") or 0)
            order.commission = sum(
                float(f.get("cost", 0))
                for f in (result.get("fees") or [])
            )
            order.raw = result

            logger.info(
                "ccxt_order_placed",
                order_id=order.id,
                broker_order_id=order.broker_order_id,
                status=order.status.value,
            )

        except Exception as exc:
            order.status = OrderStatus.REJECTED
            order.raw = {"error": str(exc)}
            logger.error("ccxt_order_failed", order_id=order.id, error=str(exc))

        order.updated_at = dt.datetime.now(dt.timezone.utc)
        return order

    async def cancel_order(self, order_id: str) -> BrokerOrder:
        ex = self._ensure_exchange()
        try:
            result = await self._api("cancel_order", order_id)
            order = BrokerOrder(
                broker_order_id=order_id,
                broker=self.name,
                status=OrderStatus.CANCELLED,
                raw=result,
            )
        except Exception as exc:
            order = BrokerOrder(
                broker_order_id=order_id,
                broker=self.name,
                status=OrderStatus.REJECTED,
                raw={"error": str(exc)},
            )
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
        """CCXT edit_order wrapper – not all exchanges support this."""
        ex = self._ensure_exchange()

        try:
            result = await self._api(
                "edit_order",
                order_id,
                None,  # symbol – let ccxt look it up
                None,  # type
                None,  # side
                quantity,
                price,
                {"stopLoss": stop_loss, "takeProfit": take_profit} if stop_loss or take_profit else {},
            )
            order = BrokerOrder(
                broker_order_id=order_id,
                broker=self.name,
                status=OrderStatus.OPEN,
                raw=result,
            )
        except Exception as exc:
            order = BrokerOrder(
                broker_order_id=order_id,
                broker=self.name,
                status=OrderStatus.REJECTED,
                raw={"error": str(exc)},
            )
        order.updated_at = dt.datetime.now(dt.timezone.utc)
        return order

    # -- account ------------------------------------------------------------

    async def get_positions(self) -> list[BrokerPosition]:
        ex = self._ensure_exchange()
        try:
            positions_raw = await self._api("fetch_positions")
        except Exception:
            return []

        result: list[BrokerPosition] = []
        for p in (positions_raw or []):
            contracts = float(p.get("contracts") or p.get("amount") or 0)
            if contracts == 0:
                continue
            result.append(BrokerPosition(
                broker=self.name,
                symbol=p.get("symbol", ""),
                side=PositionSide.LONG if p.get("side") == "long" else PositionSide.SHORT,
                quantity=contracts,
                avg_entry_price=float(p.get("entryPrice") or 0),
                current_price=float(p.get("markPrice") or p.get("info", {}).get("markPrice") or 0),
                unrealized_pnl=float(p.get("unrealizedPnl") or 0),
                leverage=float(p.get("leverage") or 1),
                raw=p,
            ))
        return result

    async def get_balance(self) -> BrokerBalance:
        ex = self._ensure_exchange()
        bal = await self._api("fetch_balance")

        usd = bal.get("USDT") or bal.get("USD") or bal.get("free", {})
        total = float(bal.get("total", {}).get("USDT") or bal.get("total", {}).get("USD") or 0)
        free = float(bal.get("free", {}).get("USDT") or bal.get("free", {}).get("USD") or 0)
        used = float(bal.get("used", {}).get("USDT") or bal.get("used", {}).get("USD") or 0)

        return BrokerBalance(
            broker=self.name,
            currency="USDT",
            total=total,
            available=free,
            used_margin=used,
            free_margin=free,
            equity=total,
            raw=bal,
        )

    # -- market data --------------------------------------------------------

    async def get_tick(self, symbol: str) -> BrokerTick:
        ex = self._ensure_exchange()
        ticker = await self._api("fetch_ticker", symbol)
        tick = BrokerTick(
            broker=self.name,
            symbol=symbol,
            bid=float(ticker.get("bid") or 0),
            ask=float(ticker.get("ask") or 0),
            last=float(ticker.get("last") or 0),
            volume=float(ticker.get("quoteVolume") or 0),
            spread=float(ticker.get("ask") or 0) - float(ticker.get("bid") or 0),
            timestamp=dt.datetime.fromtimestamp(
                (ticker.get("timestamp") or 0) / 1000, tz=dt.timezone.utc
            ) if ticker.get("timestamp") else dt.datetime.now(dt.timezone.utc),
            raw=ticker,
        )
        self._tick_cache[symbol] = tick
        return tick

    async def get_bars(
        self, symbol: str, timeframe: str, count: int = 500
    ) -> list[BrokerBar]:
        ex = self._ensure_exchange()

        # CCXT uses lowercase timeframe strings like "1h", "4h", "1d"
        tf = timeframe.lower()
        ohlcv = await self._api("fetch_ohlcv", symbol, tf, limit=count)

        bars: list[BrokerBar] = []
        for c in (ohlcv or []):
            bars.append(BrokerBar(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=dt.datetime.fromtimestamp(c[0] / 1000, tz=dt.timezone.utc),
                open=float(c[1]),
                high=float(c[2]),
                low=float(c[3]),
                close=float(c[4]),
                volume=float(c[5]),
            ))
        return bars

    # -- WebSocket (optional) -----------------------------------------------

    async def start_ws_ticker(self, symbols: list[str]) -> None:
        """Start a WebSocket ticker stream (exchange-specific)."""
        if not self._ws_enabled:
            return

        try:
            import ccxt.pro as ccxt_pro
        except ImportError:
            logger.warning("ccxt_pro_not_installed", msg="pip install ccxt[pro] for WS support")
            return

        exchange_class = getattr(ccxt_pro, self._exchange_id, None)
        if exchange_class is None:
            return

        config: dict[str, Any] = {
            "apiKey": self._api_key or None,
            "secret": self._secret or None,
        }
        if self._passphrase:
            config["password"] = self._passphrase

        self._ws = exchange_class(config)
        logger.info("ccxt_ws_starting", exchange=self._exchange_id, symbols=symbols)

        # Spawn background task
        asyncio.create_task(self._ws_ticker_loop(symbols))

    async def _ws_ticker_loop(self, symbols: list[str]) -> None:
        """Background loop consuming WebSocket tickers."""
        while self._ws and self.is_connected:
            try:
                for symbol in symbols:
                    ticker = await self._ws.watch_ticker(symbol)
                    self._tick_cache[symbol] = BrokerTick(
                        broker=self.name,
                        symbol=symbol,
                        bid=float(ticker.get("bid") or 0),
                        ask=float(ticker.get("ask") or 0),
                        last=float(ticker.get("last") or 0),
                        volume=float(ticker.get("quoteVolume") or 0),
                        spread=float(ticker.get("ask") or 0) - float(ticker.get("bid") or 0),
                        timestamp=dt.datetime.now(dt.timezone.utc),
                        raw=ticker,
                    )
            except Exception as exc:
                logger.error("ccxt_ws_error", error=str(exc))
                await asyncio.sleep(5)

    async def stop_ws(self) -> None:
        if self._ws:
            await self._ws.close()
            self._ws = None
