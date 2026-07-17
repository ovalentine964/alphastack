"""MT5 Bridge Connector — talks to the MT5 Docker bridge service via REST API.

This connector allows AlphaStack (running on Linux/Fly.io) to trade forex
through MetaTrader 5 running in a Docker container with Wine.

The bridge service runs at a configurable URL (e.g., https://alphastack-mt5.fly.dev)
and exposes a REST API for MT5 operations.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import os
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

logger = structlog.get_logger(__name__)


class MT5BridgeConnector(BrokerConnector):
    """Connector for the MT5 Docker bridge service.

    Communicates with the bridge via HTTP REST API. The bridge runs
    MetaTrader 5 under Wine in a separate Docker container.
    """

    def __init__(
        self,
        *,
        bridge_url: str | None = None,
        login: int | None = None,
        password: str | None = None,
        server: str | None = None,
        max_retries: int = 3,
        retry_delay: float = 2.0,
    ) -> None:
        super().__init__("mt5-bridge", max_retries=max_retries, retry_delay=retry_delay)
        self._bridge_url = (
            bridge_url
            or os.environ.get("MT5_BRIDGE_URL", "")
        )
        self._login = login or int(os.environ.get("MT5_LOGIN", "0"))
        self._password = password or os.environ.get("MT5_PASSWORD", "")
        self._server = server or os.environ.get("MT5_SERVER", "")
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._bridge_url,
                timeout=30.0,
            )
        return self._client

    async def _get(self, path: str, **kwargs) -> Any:
        client = await self._get_client()
        resp = await client.get(path, **kwargs)
        resp.raise_for_status()
        return resp.json()

    async def _post(self, path: str, **kwargs) -> Any:
        client = await self._get_client()
        resp = await client.post(path, **kwargs)
        resp.raise_for_status()
        return resp.json()

    # ── Lifecycle ─────────────────────────────────────────

    async def connect(self) -> None:
        self._transition(ConnectionState.CONNECTING)
        if not self._bridge_url:
            raise ConnectionError("MT5_BRIDGE_URL not set")
        if not self._login:
            raise ConnectionError("MT5_LOGIN not set")

        try:
            result = await self._post("/connect", json={
                "login": self._login,
                "password": self._password,
                "server": self._server,
            })
            self._transition(ConnectionState.CONNECTED)
            logger.info("mt5_bridge_connected", login=self._login, server=self._server)
        except Exception as e:
            self._transition(ConnectionState.ERROR)
            raise ConnectionError(f"MT5 bridge connect failed: {e}")

    async def disconnect(self) -> None:
        try:
            await self._post("/disconnect")
        except:
            pass
        self._transition(ConnectionState.DISCONNECTED)
        if self._client:
            await self._client.aclose()
        logger.info("mt5_bridge_disconnected")

    # ── Account ───────────────────────────────────────────

    async def get_balance(self) -> BrokerBalance:
        data = await self._get("/account")
        return BrokerBalance(
            broker="mt5-bridge",
            currency=data.get("currency", "USD"),
            total=data.get("balance", 0),
            available=data.get("free_margin", 0),
            used_margin=data.get("margin", 0),
            free_margin=data.get("free_margin", 0),
            equity=data.get("equity", 0),
            unrealized_pnl=data.get("profit", 0),
            margin_level=data.get("margin_level", 0),
            raw=data,
        )

    # ── Positions ─────────────────────────────────────────

    async def get_positions(self) -> list[BrokerPosition]:
        data = await self._get("/positions")
        result = []
        for p in data:
            result.append(BrokerPosition(
                broker="mt5-bridge",
                symbol=p.get("symbol", ""),
                side=PositionSide.LONG if p.get("side") == "buy" else PositionSide.SHORT,
                quantity=p.get("volume", 0),
                avg_entry_price=p.get("price_open", 0),
                current_price=p.get("price_current", 0),
                unrealized_pnl=p.get("profit", 0),
                margin_used=0,
                swap=p.get("swap", 0),
                magic_number=p.get("magic", 0),
                raw=p,
            ))
        return result

    # ── Market Data ───────────────────────────────────────

    async def get_tick(self, symbol: str) -> BrokerTick:
        data = await self._get(f"/symbol/{symbol}")
        return BrokerTick(
            broker="mt5-bridge",
            symbol=symbol,
            bid=data.get("bid", 0),
            ask=data.get("ask", 0),
            last=(data.get("bid", 0) + data.get("ask", 0)) / 2,
            volume=0,
            spread=data.get("spread", 0),
            timestamp=dt.datetime.now(dt.timezone.utc),
        )

    async def get_bars(self, symbol: str, timeframe: str = "H1", count: int = 200) -> list[BrokerBar]:
        data = await self._get(f"/bars/{symbol}", params={"timeframe": timeframe, "count": count})
        bars = []
        for r in data:
            bars.append(BrokerBar(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=dt.datetime.fromtimestamp(r.get("time", 0), tz=dt.timezone.utc),
                open=r.get("open", 0),
                high=r.get("high", 0),
                low=r.get("low", 0),
                close=r.get("close", 0),
                volume=r.get("volume", 0),
                tick_volume=r.get("volume", 0),
                spread=r.get("spread", 0) * 0.0001,  # Approximate
            ))
        return bars

    # ── Orders ────────────────────────────────────────────

    async def place_order(self, order: BrokerOrder) -> BrokerOrder:
        request = {
            "symbol": order.symbol,
            "volume": order.quantity,
            "order_type": "BUY" if order.side == OrderSide.BUY else "SELL",
        }
        if order.price:
            request["price"] = order.price
        if order.stop_loss:
            request["sl"] = order.stop_loss
        if order.take_profit:
            request["tp"] = order.take_profit
        if order.comment:
            request["comment"] = order.comment

        try:
            result = await self._post("/order", json=request)
            order.broker_order_id = str(result.get("ticket", ""))
            order.status = OrderStatus.FILLED
            order.avg_fill_price = result.get("price", 0)
            order.filled_quantity = result.get("volume", order.quantity)
            logger.info("mt5_bridge_order_placed", order_id=order.id, broker_order_id=order.broker_order_id)
        except httpx.HTTPStatusError as e:
            order.status = OrderStatus.REJECTED
            order.raw = {"error": str(e)}
            logger.warning("mt5_bridge_order_failed", order_id=order.id, error=str(e))

        order.updated_at = dt.datetime.now(dt.timezone.utc)
        return order

    async def cancel_order(self, order_id: str) -> BrokerOrder:
        # MT5 bridge doesn't have a direct cancel endpoint for pending orders
        # This would need to be implemented in the bridge
        order = BrokerOrder(broker_order_id=order_id, broker="mt5-bridge", status=OrderStatus.CANCELLED)
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
        # Would need to be implemented in the bridge
        order = BrokerOrder(broker_order_id=order_id, broker="mt5-bridge", status=OrderStatus.OPEN)
        order.updated_at = dt.datetime.now(dt.timezone.utc)
        return order
