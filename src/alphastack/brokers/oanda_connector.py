"""OANDA v20 REST API connector for AlphaStack.

Uses httpx async client (already in dependencies) for all HTTP communication
with the OANDA v20 API.  Supports both practice (demo) and live environments.

OANDA-specific conventions:
- Positions are **netting** (one per instrument, no hedging).
- Lot sizes are expressed as **units** (1 standard lot = 100,000 units).
- Instrument format uses underscores: ``EUR_USD``, ``GBP_JPY``, ``XAU_USD``.
- Spread is implicit in the bid/ask – no separate spread field.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import math
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
    TimeInForce,
)
from alphastack.core.config import get_settings

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# OANDA-specific constants
# ---------------------------------------------------------------------------

# OANDA v20 API endpoints
_PRACTICE_URL = "https://api-fxpractice.oanda.com"
_LIVE_URL = "https://api-fxtrade.oanda.com"
_PRACTICE_STREAM_URL = "https://stream-fxpractice.oanda.com"
_LIVE_STREAM_URL = "https://stream-fxtrade.oanda.com"

# 1 standard lot = 100,000 units in OANDA
_UNITS_PER_LOT = 100_000

# Map AlphaStack order types → OANDA v20 type strings
_OANDA_ORDER_TYPE: dict[OrderType, str] = {
    OrderType.MARKET: "MARKET",
    OrderType.LIMIT: "LIMIT",
    OrderType.STOP: "STOP",
    OrderType.STOP_LIMIT: "STOP_LIMIT",
    OrderType.TRAILING_STOP: "TRAILING_STOP_LOSS",
}

# Map AlphaStack TimeInForce → OANDA timeInForce
_OANDA_TIF: dict[TimeInForce, str] = {
    TimeInForce.GTC: "GTC",
    TimeInForce.IOC: "IOC",
    TimeInForce.FOK: "FOK",
    TimeInForce.DAY: "GTD",  # OANDA doesn't have DAY; use GTD with expiry
}

# OANDA granularity strings
_OANDA_GRANULARITY: dict[str, str] = {
    "S5": "S5", "S10": "S10", "S15": "S15", "S30": "S30",
    "M1": "M", "M2": "M2", "M4": "M4", "M5": "M5",
    "M10": "M10", "M15": "M15", "M30": "M30",
    "H1": "H1", "H2": "H2", "H3": "H3", "H4": "H4", "H6": "H6", "H8": "H8", "H12": "H12",
    "D1": "D", "W1": "W", "MN1": "M",
}


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

class _RateLimiter:
    """Simple token-bucket rate limiter for OANDA API (120 req/s limit)."""

    def __init__(self, requests_per_second: float = 100.0) -> None:
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
# Symbol conversion helpers
# ---------------------------------------------------------------------------

def _to_oanda_symbol(symbol: str) -> str:
    """Convert canonical ``EUR/USD`` → OANDA ``EUR_USD``."""
    return symbol.replace("/", "_")


def _from_oanda_symbol(oanda_symbol: str) -> str:
    """Convert OANDA ``EUR_USD`` → canonical ``EUR/USD``."""
    return oanda_symbol.replace("_", "/")


def _lots_to_units(lots: float) -> int:
    """Convert standard lots to OANDA units (1 lot = 100,000 units)."""
    return int(round(lots * _UNITS_PER_LOT))


def _units_to_lots(units: int) -> float:
    """Convert OANDA units to standard lots."""
    return abs(units) / _UNITS_PER_LOT


# ---------------------------------------------------------------------------
# OANDA Connector
# ---------------------------------------------------------------------------

class OandaConnector(BrokerConnector):
    """OANDA v20 REST API connector.

    Parameters
    ----------
    account_id : str | None
        OANDA account ID (falls back to ``OANDA_ACCOUNT_ID`` env var).
    access_token : str | None
        OANDA API token (falls back to ``OANDA_API_KEY`` env var).
    environment : str
        ``"practice"`` for demo or ``"live"`` for production.
    """

    def __init__(
        self,
        *,
        account_id: str | None = None,
        access_token: str | None = None,
        environment: str | None = None,
    ) -> None:
        super().__init__("oanda", max_retries=3, retry_delay=1.0)
        cfg = get_settings().oanda
        self._account_id = account_id or cfg.account_id
        self._access_token = access_token or cfg.api_key.get_secret_value()
        self._environment = (environment or cfg.environment).lower()

        if self._environment == "live":
            self._base_url = _LIVE_URL
            self._stream_url = _LIVE_STREAM_URL
        else:
            self._base_url = _PRACTICE_URL
            self._stream_url = _PRACTICE_STREAM_URL

        self._client: httpx.AsyncClient | None = None
        self._limiter = _RateLimiter()
        self._symbol_cache: dict[str, dict[str, Any]] = {}

    # -- HTTP helpers -------------------------------------------------------

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
            "Accept-Datetime-Format": "UNIX",
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute an HTTP request with rate limiting and error handling."""
        if self._client is None:
            raise RuntimeError("OANDA client not connected – call connect() first")

        await self._limiter.acquire()
        url = f"{self._base_url}{path}"

        try:
            resp = await self._client.request(
                method, url, headers=self._headers, params=params, json=json,
            )
        except httpx.HTTPError as exc:
            raise ConnectionError(f"OANDA HTTP error: {exc}") from exc

        if resp.status_code == 401:
            raise ConnectionError(
                "OANDA authentication failed (HTTP 401).  "
                "Verify OANDA_API_KEY and OANDA_ACCOUNT_ID are correct."
            )
        if resp.status_code == 403:
            raise PermissionError(
                "OANDA access denied (HTTP 403).  "
                "Check that the API key has the required scopes."
            )
        if resp.status_code == 429:
            retry_after = float(resp.headers.get("Retry-After", "1"))
            logger.warning("oanda_rate_limited", retry_after=retry_after)
            await asyncio.sleep(retry_after)
            # Retry once
            resp = await self._client.request(
                method, url, headers=self._headers, params=params, json=json,
            )

        if resp.status_code >= 400:
            body = resp.text
            raise RuntimeError(
                f"OANDA API error {resp.status_code} on {method} {path}: {body}"
            )

        return resp.json()

    # -- lifecycle ----------------------------------------------------------

    async def connect(self) -> None:
        self._transition(ConnectionState.CONNECTING)

        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )

        # Verify connectivity and credentials
        try:
            result = await self._request("GET", f"/v3/accounts/{self._account_id}/summary")
            acct = result.get("account", {})
            logger.info(
                "oanda_connected",
                account=self._account_id,
                currency=acct.get("currency", "USD"),
                balance=acct.get("balance", "0"),
            )
        except Exception:
            await self._client.aclose()
            self._client = None
            self._transition(ConnectionState.ERROR)
            raise

        self._transition(ConnectionState.CONNECTED)

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
        self._transition(ConnectionState.DISCONNECTED)
        logger.info("oanda_disconnected")

    # -- orders -------------------------------------------------------------

    async def place_order(self, order: BrokerOrder) -> BrokerOrder:
        """Submit an order to OANDA.

        OANDA uses **units** not lots: positive = buy, negative = sell.
        1 standard lot = 100,000 units.
        """
        instrument = _to_oanda_symbol(order.symbol)
        units = _lots_to_units(order.quantity)
        if order.side == OrderSide.SELL:
            units = -units

        oanda_type = _OANDA_ORDER_TYPE.get(order.order_type, "MARKET")
        tif = _OANDA_TIF.get(order.time_in_force, "GTC")
        if oanda_type == "MARKET":
            tif = "FOK"

        body: dict[str, Any] = {
            "order": {
                "type": oanda_type,
                "instrument": instrument,
                "units": str(units),
                "timeInForce": tif,
            }
        }

        # Price for non-market orders
        if order.price and oanda_type != "MARKET":
            body["order"]["price"] = str(order.price)

        # Stop-loss and take-profit on fill
        if order.stop_loss:
            body["order"]["stopLossOnFill"] = {"price": _fmt_price(order.stop_loss)}
        if order.take_profit:
            body["order"]["takeProfitOnFill"] = {"price": _fmt_price(order.take_profit)}

        # Trailing stop distance (in price units)
        if order.trailing_stop_distance and oanda_type == "TRAILING_STOP_LOSS":
            body["order"]["distance"] = str(order.trailing_stop_distance)

        # Client extensions (comment / magic)
        if order.comment or order.magic_number:
            extensions: dict[str, Any] = {}
            if order.comment:
                extensions["comment"] = order.comment
            if order.magic_number:
                extensions["tag"] = str(order.magic_number)
            body["order"]["clientExtensions"] = extensions

        result = await self._request(
            "POST",
            f"/v3/accounts/{self._account_id}/orders",
            json=body,
        )

        # Parse response
        order_fill = result.get("orderFillTransaction", {})
        order_create = result.get("orderCreateTransaction", {})
        related = result.get("relatedTransactionIDs", [])

        if order_fill:
            trade_opened = order_fill.get("tradeOpened", {})
            order.broker_order_id = trade_opened.get("tradeID", "")
            order.status = OrderStatus.FILLED
            order.avg_fill_price = float(order_fill.get("price", 0))
            order.filled_quantity = _units_to_lots(int(order_fill.get("units", 0)))
            order.commission = float(order_fill.get("commission", 0))
            order.slippage = float(order_fill.get("slippage", 0))
        elif order_create:
            order.broker_order_id = order_create.get("id", "")
            order.status = OrderStatus.OPEN
        else:
            order.status = OrderStatus.REJECTED
            order.raw = {"error": "No fill or create transaction in response"}

        order.raw = result
        order.updated_at = dt.datetime.now(dt.timezone.utc)

        logger.info(
            "oanda_order_placed",
            order_id=order.id,
            broker_order_id=order.broker_order_id,
            status=order.status.value,
            fill_price=order.avg_fill_price,
        )
        return order

    async def cancel_order(self, order_id: str) -> BrokerOrder:
        """Cancel a pending order by its OANDA order ID."""
        await self._request(
            "PUT",
            f"/v3/accounts/{self._account_id}/orders/{order_id}/cancel",
        )
        order = BrokerOrder(
            broker_order_id=order_id,
            broker="oanda",
            status=OrderStatus.CANCELLED,
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
        """Modify a pending order.  OANDA requires the full order body on PUT."""
        # Fetch current order to merge with changes
        current = await self._request(
            "GET",
            f"/v3/accounts/{self._account_id}/orders/{order_id}",
        )
        existing = current.get("order", {})

        order_body: dict[str, Any] = {
            "type": existing.get("type", "LIMIT"),
            "instrument": existing.get("instrument", ""),
            "units": existing.get("units", "0"),
            "timeInForce": existing.get("timeInForce", "GTC"),
        }

        if price is not None:
            order_body["price"] = str(price)
        elif "price" in existing:
            order_body["price"] = existing["price"]

        if stop_loss is not None:
            order_body["stopLossOnFill"] = {"price": _fmt_price(stop_loss)}
        if take_profit is not None:
            order_body["takeProfitOnFill"] = {"price": _fmt_price(take_profit)}
        if quantity is not None:
            # Preserve sign of existing units
            existing_units = int(existing.get("units", 0))
            sign = 1 if existing_units >= 0 else -1
            order_body["units"] = str(sign * _lots_to_units(quantity))

        body = {"order": order_body}

        await self._request(
            "PUT",
            f"/v3/accounts/{self._account_id}/orders/{order_id}",
            json=body,
        )

        order = BrokerOrder(
            broker_order_id=order_id,
            broker="oanda",
            status=OrderStatus.OPEN,
        )
        order.updated_at = dt.datetime.now(dt.timezone.utc)
        return order

    async def close_position(self, symbol: str, *, side: str | None = None) -> dict[str, Any]:
        """Close an open position.

        Parameters
        ----------
        symbol : str
            Canonical symbol (``EUR/USD``).
        side : str, optional
            ``"long"`` or ``"short"``.  If None, OANDA closes the entire position.

        Returns
        -------
        dict
            OANDA response with ``longOrderFillTransaction`` and/or
            ``shortOrderFillTransaction``.
        """
        instrument = _to_oanda_symbol(symbol)
        body: dict[str, Any] = {}

        if side == "long":
            body["longUnits"] = "ALL"
        elif side == "short":
            body["shortUnits"] = "ALL"
        else:
            body["longUnits"] = "ALL"
            body["shortUnits"] = "ALL"

        result = await self._request(
            "PUT",
            f"/v3/accounts/{self._account_id}/positions/{instrument}/close",
            json=body,
        )
        return result

    # -- account ------------------------------------------------------------

    async def get_positions(self) -> list[BrokerPosition]:
        """Return all open positions.

        OANDA is netting — each instrument has at most one position with
        ``long`` and ``short`` sub-objects indicating direction.
        """
        result = await self._request(
            "GET",
            f"/v3/accounts/{self._account_id}/openPositions",
        )

        positions: list[BrokerPosition] = []
        for p in result.get("positions", []):
            instrument = p.get("instrument", "")
            symbol = _from_oanda_symbol(instrument)

            long = p.get("long", {})
            short = p.get("short", {})

            long_units = int(long.get("units", 0))
            short_units = int(short.get("units", 0))

            if long_units != 0:
                positions.append(BrokerPosition(
                    broker="oanda",
                    symbol=symbol,
                    side=PositionSide.LONG,
                    quantity=_units_to_lots(long_units),
                    avg_entry_price=float(long.get("averagePrice", 0)),
                    unrealized_pnl=float(long.get("unrealizedPL", 0)),
                    margin_used=float(long.get("marginUsed", 0)),
                    raw=p,
                ))

            if short_units != 0:
                positions.append(BrokerPosition(
                    broker="oanda",
                    symbol=symbol,
                    side=PositionSide.SHORT,
                    quantity=_units_to_lots(short_units),
                    avg_entry_price=float(short.get("averagePrice", 0)),
                    unrealized_pnl=float(short.get("unrealizedPL", 0)),
                    margin_used=float(short.get("marginUsed", 0)),
                    raw=p,
                ))

        return positions

    async def get_balance(self) -> BrokerBalance:
        """Return account balance and margin info."""
        result = await self._request(
            "GET",
            f"/v3/accounts/{self._account_id}/summary",
        )
        acct = result.get("account", {})

        return BrokerBalance(
            broker="oanda",
            currency=acct.get("currency", "USD"),
            total=float(acct.get("balance", 0)),
            available=float(acct.get("marginAvailable", 0)),
            used_margin=float(acct.get("marginUsed", 0)),
            free_margin=float(acct.get("marginAvailable", 0)),
            equity=float(acct.get("NAV", 0)),
            unrealized_pnl=float(acct.get("unrealizedPL", 0)),
            margin_level=_safe_float(acct.get("marginCallMarginUsed", 0)),
            raw=acct,
        )

    async def get_account(self) -> dict[str, Any]:
        """Return the full OANDA account object."""
        result = await self._request(
            "GET",
            f"/v3/accounts/{self._account_id}/summary",
        )
        return result.get("account", {})

    # -- market data --------------------------------------------------------

    async def get_price(self, symbol: str) -> BrokerTick:
        """Fetch the latest price for a single instrument."""
        instrument = _to_oanda_symbol(symbol)
        result = await self._request(
            "GET",
            f"/v3/accounts/{self._account_id}/pricing",
            params={"instruments": instrument},
        )

        prices = result.get("prices", [])
        if not prices:
            raise ValueError(f"No price data for {symbol}")

        return _parse_oanda_tick(prices[0], symbol)

    async def get_prices(self, symbols: list[str]) -> list[BrokerTick]:
        """Fetch latest prices for multiple instruments in a single request."""
        instruments = ",".join(_to_oanda_symbol(s) for s in symbols)
        result = await self._request(
            "GET",
            f"/v3/accounts/{self._account_id}/pricing",
            params={"instruments": instruments},
        )

        ticks: list[BrokerTick] = []
        for price in result.get("prices", []):
            inst = price.get("instrument", "")
            sym = _from_oanda_symbol(inst)
            ticks.append(_parse_oanda_tick(price, sym))

        return ticks

    async def get_tick(self, symbol: str) -> BrokerTick:
        """Alias for ``get_price`` (satisfies BrokerConnector ABC)."""
        return await self.get_price(symbol)

    async def get_bars(
        self,
        symbol: str,
        timeframe: str,
        count: int = 500,
    ) -> list[BrokerBar]:
        """Fetch historical OHLCV candles.

        Parameters
        ----------
        symbol : str
            Canonical symbol (``EUR/USD``).
        timeframe : str
            AlphaStack timeframe string (``M1``, ``M5``, ``H1``, ``D1``, …).
        count : int
            Number of candles (max 5000 per OANDA).
        """
        instrument = _to_oanda_symbol(symbol)
        granularity = _OANDA_GRANULARITY.get(timeframe.upper(), "H1")

        result = await self._request(
            "GET",
            f"/v3/instruments/{instrument}/candles",
            params={
                "granularity": granularity,
                "count": min(count, 5000),
                "price": "MBA",  # Mid, Bid, Ask
            },
        )

        bars: list[BrokerBar] = []
        for c in result.get("candles", []):
            if not c.get("complete"):
                continue

            mid = c.get("mid", {})
            bid = c.get("bid", {})
            ask = c.get("asks", c.get("ask", {}))

            bars.append(BrokerBar(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=_parse_oanda_time(c.get("time", "")),
                open=float(mid.get("o", 0)),
                high=float(mid.get("h", 0)),
                low=float(mid.get("l", 0)),
                close=float(mid.get("c", 0)),
                volume=int(c.get("volume", 0)),
            ))

        return bars

    # -- streaming (optional) -----------------------------------------------

    async def stream_prices(
        self,
        symbols: list[str],
        callback: Any,
    ) -> None:
        """Stream real-time prices via OANDA's streaming endpoint.

        This is a long-running coroutine.  Call it as a background task::

            task = asyncio.create_task(
                connector.stream_prices(["EUR/USD"], my_callback)
            )

        The callback receives a ``BrokerTick`` for each price update.
        """
        if self._client is None:
            raise RuntimeError("OANDA client not connected")

        instruments = ",".join(_to_oanda_symbol(s) for s in symbols)
        url = f"{self._stream_url}/v3/accounts/{self._account_id}/pricing/stream"
        params = {"instruments": instruments}

        async with self._client.stream(
            "GET", url, headers=self._headers, params=params,
        ) as resp:
            async for line in resp.aiter_lines():
                if not line:
                    continue
                try:
                    import json as _json
                    data = _json.loads(line)
                except Exception:
                    continue

                if data.get("type") == "PRICE":
                    inst = data.get("instrument", "")
                    sym = _from_oanda_symbol(inst)
                    tick = _parse_oanda_tick(data, sym)
                    if asyncio.iscoroutinefunction(callback):
                        await callback(tick)
                    else:
                        callback(tick)

    # -- helpers ------------------------------------------------------------

    async def get_instrument_details(self, symbol: str) -> dict[str, Any]:
        """Fetch instrument metadata (pip location, trade sizes, etc.)."""
        instrument = _to_oanda_symbol(symbol)
        result = await self._request(
            "GET",
            f"/v3/accounts/{self._account_id}/instruments",
            params={"instruments": instrument},
        )

        instruments = result.get("instruments", [])
        if not instruments:
            raise ValueError(f"Instrument {symbol} not found")

        inst = instruments[0]
        pip_location = int(inst.get("pipLocation", -4))
        pip_size = 10 ** pip_location

        details = {
            "symbol": symbol,
            "oanda_instrument": instrument,
            "pip_size": pip_size,
            "pip_location": pip_location,
            "display_precision": int(inst.get("displayPrecision", 5)),
            "trade_units_precision": int(inst.get("tradeUnitsPrecision", 0)),
            "minimum_trade_size": int(inst.get("minimumTradeSize", "1")),
            "maximum_trailing_stop_distance": inst.get("maximumTrailingStopDistance", ""),
            "minimum_trailing_stop_distance": inst.get("minimumTrailingStopDistance", ""),
            "maximum_position_size": inst.get("maximumPositionSize", ""),
            "maximum_order_units": inst.get("maximumOrderUnits", ""),
            "margin_rate": inst.get("marginRate", "0.01"),
            "tags": inst.get("tags", []),
        }

        self._symbol_cache[symbol] = details
        return details

    async def pip_size(self, symbol: str) -> float:
        """Return the pip size for *symbol*."""
        if symbol in self._symbol_cache:
            return self._symbol_cache[symbol]["pip_size"]
        details = await self.get_instrument_details(symbol)
        return details["pip_size"]


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _fmt_price(price: float) -> str:
    """Format a price with enough precision for OANDA."""
    if price == 0:
        return "0"
    # Use 5 significant digits for most pairs, more for JPY pairs
    if abs(price) > 10:
        return f"{price:.3f}"
    return f"{price:.5f}"


def _safe_float(val: Any, default: float = 0.0) -> float:
    """Safely convert a value to float."""
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _parse_oanda_time(time_str: str) -> dt.datetime:
    """Parse an OANDA timestamp string to a UTC datetime."""
    if not time_str:
        return dt.datetime.now(dt.timezone.utc)
    # OANDA returns RFC 3339 (e.g. "2024-01-15T12:30:00.000000000Z")
    # or UNIX timestamp as string when Accept-Datetime-Format: UNIX
    try:
        ts = float(time_str)
        return dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc)
    except ValueError:
        pass
    # Fall back to ISO parsing
    clean = time_str.replace("Z", "+00:00")
    return dt.datetime.fromisoformat(clean)


def _parse_oanda_tick(price: dict[str, Any], symbol: str) -> BrokerTick:
    """Parse an OANDA pricing response into a BrokerTick."""
    bids = price.get("bids", [])
    asks = price.get("asks", [])

    bid = float(bids[0]["price"]) if bids else 0.0
    ask = float(asks[0]["price"]) if asks else 0.0
    spread = ask - bid if bid and ask else 0.0

    return BrokerTick(
        broker="oanda",
        symbol=symbol,
        bid=bid,
        ask=ask,
        last=(bid + ask) / 2 if bid and ask else 0.0,
        volume=0.0,  # OANDA doesn't provide volume in pricing endpoint
        spread=spread,
        timestamp=_parse_oanda_time(price.get("time", "")),
        raw=price,
    )
