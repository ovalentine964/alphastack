# Fix: MT5 & Broker Integration — Critical Bug Fixes

**Date:** 2026-07-11
**Source:** `review_9_mt5_integration.md` — 3 Critical + related P0 issues
**Status:** Ready for implementation

---

## Bug 1: MT5 Pending Order Pricing Bug 🔴

### Problem

In `MT5Connector._place_order_sync()`, the pricing logic falls back to market price for limit/stop orders when `order.price` is missing. This defeats the purpose of pending orders and can cause immediate execution or broker rejection.

**Broken code:**
```python
tick = mt5.symbol_info_tick(mt5_symbol)
price = order.price or (tick.ask if order.side == OrderSide.BUY else tick.bid)
```

### Root Cause

The `or` fallback merges the market-order path with the pending-order path. For MARKET orders, fetching the current tick is correct. For LIMIT/STOP orders, falling back to market price is semantically wrong — the user explicitly wants a non-market price.

### Fix

Replace the single-line pricing with order-type-aware branching. Add price validation for pending orders relative to current market price.

```python
# In MT5Connector._place_order_sync()

def _place_order_sync(self, order: UnifiedOrder) -> BrokerOrderResult:
    mt5_symbol = self._to_broker_symbol(order.symbol)
    info = mt5.symbol_info(mt5_symbol)
    if info is None:
        raise BrokerError(self.broker_id, f"Symbol {mt5_symbol} not found")

    # --- FIX: Order-type-aware pricing ---
    tick = mt5.symbol_info_tick(mt5_symbol)
    if tick is None:
        raise BrokerError(self.broker_id, f"No tick data for {mt5_symbol}")

    if order.order_type == OrderType.MARKET:
        price = tick.ask if order.side == OrderSide.BUY else tick.bid
    elif order.order_type in (OrderType.LIMIT, OrderType.STOP, OrderType.STOP_LIMIT):
        if not order.price:
            raise BrokerError(
                self.broker_id,
                f"{order.order_type.value} order requires a price"
            )
        price = order.price

        # Validate price vs market for LIMIT orders
        if order.order_type == OrderType.LIMIT:
            if order.side == OrderSide.BUY and price >= tick.ask:
                raise BrokerError(
                    self.broker_id,
                    f"Buy limit price {price} must be below ask {tick.ask}"
                )
            if order.side == OrderSide.SELL and price <= tick.bid:
                raise BrokerError(
                    self.broker_id,
                    f"Sell limit price {price} must be above bid {tick.bid}"
                )
        # Validate STOP orders — stop price must be on the correct side of market
        elif order.order_type == OrderType.STOP:
            if order.side == OrderSide.BUY and price <= tick.ask:
                raise BrokerError(
                    self.broker_id,
                    f"Buy stop price {price} must be above ask {tick.ask}"
                )
            if order.side == OrderSide.SELL and price >= tick.bid:
                raise BrokerError(
                    self.broker_id,
                    f"Sell stop price {price} must be below bid {tick.bid}"
                )
    else:
        raise BrokerError(self.broker_id, f"Unsupported order type: {order.order_type}")

    # --- Resolve filling mode dynamically (fixes hard-coded IOC) ---
    if info.filling_mode & mt5.SYMBOL_FILLING_IOC:
        filling = mt5.ORDER_FILLING_IOC
    elif info.filling_mode & mt5.SYMBOL_FILLING_FOK:
        filling = mt5.ORDER_FILLING_FOK
    else:
        filling = mt5.ORDER_FILLING_RETURN

    # --- Build MT5 order request ---
    mt5_order_type = self._map_order_type(order.order_type, order.side)

    request = {
        "action": mt5.TRADE_ACTION_DEAL if order.order_type == OrderType.MARKET else mt5.TRADE_ACTION_PENDING,
        "symbol": mt5_symbol,
        "volume": float(order.quantity),
        "type": mt5_order_type,
        "price": price,
        "deviation": self._config.get("deviation", 30),
        "magic": self._config.get("magic_number", 202607),
        "comment": order.order_id[:31],  # MT5 comment max 31 chars
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": filling,
    }

    # Attach SL/TP if provided
    if order.stop_loss:
        request["sl"] = float(order.stop_loss)
    if order.take_profit:
        request["tp"] = float(order.take_profit)

    result = mt5.order_send(request)
    if result is None:
        raise BrokerError(self.broker_id, f"order_send returned None: {mt5.last_error()}")
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        raise BrokerError(
            self.broker_id,
            f"Order rejected: retcode={result.retcode}, comment={result.comment}"
        )

    return BrokerOrderResult(
        broker_order_id=str(result.order),
        broker_price=result.price,
        broker_volume=result.volume,
        status=OrderStatus.FILLED if order.order_type == OrderType.MARKET else OrderStatus.PENDING,
    )
```

### Key Changes

| What | Before | After |
|------|--------|-------|
| Market order pricing | Mixed with pending logic | Dedicated branch: uses `tick.ask/bid` |
| Limit/stop pricing | Falls back to market price | Raises `BrokerError` if price missing |
| Price validation | None | Validates limit below ask, stop above ask (and vice versa for sells) |
| Filling mode | Hard-coded `IOC` | Dynamic from `symbol_info().filling_mode` bitmask |
| Error messages | Generic | Includes actual prices for debugging |

### Test Cases

```python
def test_buy_limit_must_be_below_ask():
    """Buy limit at or above ask should raise BrokerError."""
    connector = MT5Connector(...)
    order = UnifiedOrder(
        symbol="EUR/USD",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        price=1.1050,  # above current ask of 1.1040
        quantity=0.01,
    )
    with pytest.raises(BrokerError, match="must be below ask"):
        connector.place_order(order)

def test_limit_order_requires_price():
    """Limit order without price should raise BrokerError."""
    order = UnifiedOrder(
        symbol="EUR/USD",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        price=None,
        quantity=0.01,
    )
    with pytest.raises(BrokerError, match="requires a price"):
        connector.place_order(order)

def test_market_order_uses_tick_price():
    """Market order should use tick price, not order.price."""
    order = UnifiedOrder(
        symbol="EUR/USD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.01,
    )
    result = connector.place_order(order)
    assert result.broker_price == pytest.approx(1.1040, abs=0.0001)  # tick.ask
```

---

## Bug 2: Docker Compose `platform: windows` is Invalid 🔴

### Problem

```yaml
# BROKEN — this does NOT work on a Linux host
mt5-bridge:
    build: ./mt5-bridge
    platform: windows   # ← Invalid: can't run Windows containers on Linux
```

`platform` in Docker Compose selects the build architecture (e.g., `linux/amd64`, `linux/arm64`). It does NOT enable running Windows containers on a Linux host. Docker on Linux has no Windows container runtime. This will fail at startup.

### Root Cause

The `MetaTrader5` Python package is **Windows-only** — it communicates with the MT5 terminal process (`terminal64.exe`) via COM/named pipes. There is no Linux-native MT5 terminal. The architecture correctly identifies the need for a WebSocket bridge (`MT5_BRIDGE_URL: ws://mt5-bridge:8765`), but the Docker configuration tries to run the bridge itself as a Linux container, which can't host the MT5 terminal.

### Fix: Proper MT5 Bridge Architecture

The MT5 bridge must run on a **separate Windows host** (VM or VPS). The Linux-side Alpha Stack connects to it over WebSocket.

#### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│  Linux Host (Pop!_OS / Ubuntu) — Alpha Stack Core           │
│                                                             │
│  docker-compose.yml                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  core-api    │  │  ccxt-svc    │  │  risk-engine  │     │
│  │  (Python)    │  │  (Python)    │  │  (Python)     │     │
│  └──────┬───────┘  └──────────────┘  └──────────────┘     │
│         │                                                   │
│  ┌──────▼───────────────────────────────────────────┐      │
│  │  mt5-bridge-client (WebSocket client)             │      │
│  │  • Connects to MT5_BRIDGE_URL                     │      │
│  │  • Auto-reconnect with exponential backoff        │      │
│  │  • Local order queue for offline buffering        │      │
│  │  • Health check endpoint for orchestrator         │      │
│  └──────┬───────────────────────────────────────────┘      │
└─────────┼───────────────────────────────────────────────────┘
          │ WebSocket (wss://mt5-bridge.internal:8765)
          │ + mTLS or shared-secret auth
          ▼
┌─────────────────────────────────────────────────────────────┐
│  Windows Host (VM or VPS) — MT5 Bridge Server               │
│                                                             │
│  ┌──────────────────────────────────────────────────┐      │
│  │  mt5-bridge-server (Python + asyncio)             │      │
│  │  • WebSocket server (websockets / aiohttp)        │      │
│  │  • Manages MetaTrader5 Python package lifecycle   │      │
│  │  • MT5 terminal auto-login & health monitoring    │      │
│  │  • Request queuing with concurrency limit         │      │
│  │  • Heartbeat + stale connection detection         │      │
│  └──────────────────┬───────────────────────────────┘      │
│                     │                                       │
│  ┌──────────────────▼───────────────────────────────┐      │
│  │  MetaTrader 5 Terminal (terminal64.exe)           │      │
│  │  • Broker: FXPesa / ICMarkets / etc.              │      │
│  │  • Account: configured via env vars               │      │
│  │  • VPS recommended: <2ms to broker                │      │
│  └──────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

#### 2a. Fix `docker-compose.yml` — Remove Invalid Directive

```yaml
# docker-compose.yml (Linux host)

services:
  core-api:
    build: ./core-api
    environment:
      - MT5_BRIDGE_URL=${MT5_BRIDGE_URL:-wss://mt5-bridge.internal:8765}
      - MT5_BRIDGE_SECRET=${MT5_BRIDGE_SECRET}
    depends_on:
      - postgres
      - redis

  ccxt-svc:
    build: ./ccxt-svc
    environment:
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis

  # mt5-bridge-client runs on Linux — it's a WebSocket CLIENT
  # that connects to the remote Windows MT5 bridge server
  mt5-bridge-client:
    build: ./mt5-bridge-client
    environment:
      - MT5_BRIDGE_URL=${MT5_BRIDGE_URL:-wss://mt5-bridge.internal:8765}
      - MT5_BRIDGE_SECRET=${MT5_BRIDGE_SECRET}
      - RECONNECT_INTERVAL=5
      - MAX_RECONNECT_INTERVAL=60
      - HEARTBEAT_INTERVAL=15
    depends_on:
      - core-api
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import asyncio,websockets; asyncio.run(websockets.connect('${MT5_BRIDGE_URL:-wss://localhost:8765}'))"]
      interval: 30s
      timeout: 10s
      retries: 3

  # ⚠️ NO mt5-bridge service here — it runs on the Windows host
  # The "platform: windows" line is REMOVED

  postgres:
    image: postgres:16
    volumes:
      - pgdata:/var/lib/postgresql/data
    environment:
      POSTGRES_DB: alphastack
      POSTGRES_PASSWORD: ${DB_PASSWORD}

  redis:
    image: redis:7-alpine
    volumes:
      - redisdata:/data

volumes:
  pgdata:
  redisdata:
```

#### 2b. MT5 Bridge Protocol Specification

Define a clear JSON-RPC-like protocol over WebSocket.

**Message format (JSON):**

```python
# shared/bridge_protocol.py

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import json
import time
import uuid


class MessageType(str, Enum):
    # Client → Server
    PLACE_ORDER = "place_order"
    CANCEL_ORDER = "cancel_order"
    MODIFY_ORDER = "modify_order"
    GET_POSITIONS = "get_positions"
    GET_BALANCE = "get_balance"
    GET_OPEN_ORDERS = "get_open_orders"
    GET_ORDER_STATUS = "get_order_status"
    GET_TICK = "get_tick"
    PING = "ping"

    # Server → Client
    ORDER_RESULT = "order_result"
    POSITIONS_DATA = "positions_data"
    BALANCE_DATA = "balance_data"
    ORDERS_DATA = "orders_data"
    TICK_DATA = "tick_data"
    PONG = "pong"
    ERROR = "error"

    # Server → Client (unsolicited)
    POSITION_UPDATE = "position_update"
    ORDER_UPDATE = "order_update"
    TERMINAL_STATUS = "terminal_status"


@dataclass
class BridgeMessage:
    """Wire format for MT5 bridge communication."""
    type: MessageType
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    payload: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps({
            "type": self.type.value,
            "id": self.id,
            "payload": self.payload,
            "ts": self.timestamp,
        })

    @classmethod
    def from_json(cls, raw: str) -> "BridgeMessage":
        data = json.loads(raw)
        return cls(
            type=MessageType(data["type"]),
            id=data.get("id", ""),
            payload=data.get("payload", {}),
            timestamp=data.get("ts", 0),
        )


# --- Authentication ---
# On WebSocket connect, client must send auth within 5 seconds:
# {"type": "auth", "payload": {"token": "<shared-secret>"}}
# Server responds: {"type": "auth_result", "payload": {"ok": true, "terminal_status": "connected"}}
# On failure: {"type": "auth_result", "payload": {"ok": false, "reason": "invalid token"}}
# Connection is closed after auth failure.
```

#### 2c. MT5 Bridge Server (Windows Side)

```python
# mt5-bridge-server/server.py
# Runs on Windows host alongside MT5 terminal

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional

import MetaTrader5 as mt5
import websockets
from websockets.server import serve

from shared.bridge_protocol import BridgeMessage, MessageType

logger = logging.getLogger("mt5-bridge-server")


@dataclass
class BridgeConfig:
    host: str = "0.0.0.0"
    port: int = 8765
    auth_secret: str = ""
    mt5_login: int = 0
    mt5_password: str = ""
    mt5_server: str = ""
    mt5_path: str = r"C:\Program Files\MetaTrader 5\terminal64.exe"
    max_concurrent_requests: int = 5
    heartbeat_interval: int = 15
    request_timeout: float = 30.0

    @classmethod
    def from_env(cls) -> "BridgeConfig":
        return cls(
            host=os.environ.get("BRIDGE_HOST", "0.0.0.0"),
            port=int(os.environ.get("BRIDGE_PORT", "8765")),
            auth_secret=os.environ.get("BRIDGE_SECRET", ""),
            mt5_login=int(os.environ.get("MT5_LOGIN", "0")),
            mt5_password=os.environ.get("MT5_PASSWORD", ""),
            mt5_server=os.environ.get("MT5_SERVER", ""),
            mt5_path=os.environ.get("MT5_PATH", r"C:\Program Files\MetaTrader 5\terminal64.exe"),
            max_concurrent_requests=int(os.environ.get("MAX_CONCURRENT", "5")),
            heartbeat_interval=int(os.environ.get("HEARTBEAT_INTERVAL", "15")),
        )


class MT5BridgeServer:
    def __init__(self, config: BridgeConfig):
        self.config = config
        self._semaphore = asyncio.Semaphore(config.max_concurrent_requests)
        self._authenticated_clients: set = set()
        self._terminal_connected = False

    async def start(self):
        """Initialize MT5 terminal and start WebSocket server."""
        if not self._init_mt5():
            logger.error("Failed to initialize MT5 terminal")
            return

        async with serve(
            self._handle_client,
            self.config.host,
            self.config.port,
            ping_interval=20,
            ping_timeout=10,
            max_size=1_048_576,  # 1MB max message
        ):
            logger.info(f"MT5 Bridge Server listening on {self.config.host}:{self.config.port}")
            await asyncio.Future()  # run forever

    def _init_mt5(self) -> bool:
        """Initialize and login to MT5 terminal."""
        if not mt5.initialize(path=self.config.mt5_path):
            logger.error(f"MT5 initialize failed: {mt5.last_error()}")
            return False

        if self.config.mt5_login:
            authorized = mt5.login(
                self.config.mt5_login,
                password=self.config.mt5_password,
                server=self.config.mt5_server,
            )
            if not authorized:
                logger.error(f"MT5 login failed: {mt5.last_error()}")
                mt5.shutdown()
                return False

        info = mt5.terminal_info()
        self._terminal_connected = info is not None and info.connected
        logger.info(f"MT5 terminal connected: {self._terminal_connected}")
        return True

    async def _handle_client(self, websocket):
        """Handle a single WebSocket client connection."""
        client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        logger.info(f"Client connected: {client_id}")

        authenticated = False

        try:
            async for raw_message in websocket:
                try:
                    msg = BridgeMessage.from_json(raw_message)
                except (json.JSONDecodeError, ValueError, KeyError) as e:
                    await websocket.send(BridgeMessage(
                        type=MessageType.ERROR,
                        payload={"error": f"Invalid message: {e}"},
                    ).to_json())
                    continue

                # Handle authentication
                if msg.type.value == "auth":
                    authenticated = await self._handle_auth(websocket, msg)
                    continue

                if not authenticated:
                    await websocket.send(BridgeMessage(
                        type=MessageType.ERROR,
                        payload={"error": "Not authenticated"},
                    ).to_json())
                    continue

                # Process trading requests
                await self._dispatch(websocket, msg)

        except websockets.ConnectionClosed:
            logger.info(f"Client disconnected: {client_id}")
        finally:
            self._authenticated_clients.discard(client_id)

    async def _handle_auth(self, websocket, msg: BridgeMessage) -> bool:
        """Authenticate client. Returns True if successful."""
        client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        token = msg.payload.get("token", "")

        if not self.config.auth_secret or token == self.config.auth_secret:
            self._authenticated_clients.add(client_id)
            await websocket.send(BridgeMessage(
                type=MessageType.PONG,  # reuse for auth_result
                id=msg.id,
                payload={"auth": True, "terminal_connected": self._terminal_connected},
            ).to_json())
            logger.info(f"Client authenticated: {client_id}")
            return True
        else:
            await websocket.send(BridgeMessage(
                type=MessageType.ERROR,
                id=msg.id,
                payload={"error": "Authentication failed"},
            ).to_json())
            logger.warning(f"Auth failed for {client_id}")
            return False

    async def _dispatch(self, websocket, msg: BridgeMessage):
        """Route request to appropriate handler with concurrency limiting."""
        handlers = {
            MessageType.PLACE_ORDER: self._handle_place_order,
            MessageType.CANCEL_ORDER: self._handle_cancel_order,
            MessageType.MODIFY_ORDER: self._handle_modify_order,
            MessageType.GET_POSITIONS: self._handle_get_positions,
            MessageType.GET_BALANCE: self._handle_get_balance,
            MessageType.GET_OPEN_ORDERS: self._handle_get_open_orders,
            MessageType.GET_ORDER_STATUS: self._handle_get_order_status,
            MessageType.GET_TICK: self._handle_get_tick,
            MessageType.PING: self._handle_ping,
        }

        handler = handlers.get(msg.type)
        if handler is None:
            await websocket.send(BridgeMessage(
                type=MessageType.ERROR,
                id=msg.id,
                payload={"error": f"Unknown message type: {msg.type.value}"},
            ).to_json())
            return

        async with self._semaphore:
            try:
                await asyncio.wait_for(
                    handler(websocket, msg),
                    timeout=self.config.request_timeout,
                )
            except asyncio.TimeoutError:
                await websocket.send(BridgeMessage(
                    type=MessageType.ERROR,
                    id=msg.id,
                    payload={"error": "Request timed out"},
                ).to_json())

    async def _handle_place_order(self, websocket, msg: BridgeMessage):
        """Execute MT5 order in thread pool (MT5 is synchronous)."""
        payload = msg.payload
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._mt5_place_order, payload)

        await websocket.send(BridgeMessage(
            type=MessageType.ORDER_RESULT,
            id=msg.id,
            payload=result,
        ).to_json())

    def _mt5_place_order(self, payload: dict) -> dict:
        """Synchronous MT5 order execution (runs in thread pool)."""
        try:
            request = {
                "action": payload.get("action", mt5.TRADE_ACTION_DEAL),
                "symbol": payload["symbol"],
                "volume": float(payload["volume"]),
                "type": payload["type"],
                "price": float(payload["price"]),
                "deviation": int(payload.get("deviation", 30)),
                "magic": int(payload.get("magic", 202607)),
                "comment": payload.get("comment", ""),
                "type_time": payload.get("type_time", mt5.ORDER_TIME_GTC),
                "type_filling": payload.get("type_filling", mt5.ORDER_FILLING_IOC),
            }
            if "sl" in payload:
                request["sl"] = float(payload["sl"])
            if "tp" in payload:
                request["tp"] = float(payload["tp"])

            result = mt5.order_send(request)
            if result is None:
                return {"ok": False, "error": str(mt5.last_error())}

            return {
                "ok": result.retcode == mt5.TRADE_RETCODE_DONE,
                "order_id": str(result.order),
                "price": result.price,
                "volume": result.volume,
                "retcode": result.retcode,
                "comment": result.comment,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def _handle_get_balance(self, websocket, msg: BridgeMessage):
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._mt5_get_balance)
        await websocket.send(BridgeMessage(
            type=MessageType.BALANCE_DATA,
            id=msg.id,
            payload=result,
        ).to_json())

    def _mt5_get_balance(self) -> dict:
        info = mt5.account_info()
        if info is None:
            return {"ok": False, "error": str(mt5.last_error())}
        return {
            "ok": True,
            "balance": info.balance,
            "equity": info.equity,
            "margin": info.margin,
            "free_margin": info.margin_free,
            "profit": info.profit,
            "currency": info.currency,
            "leverage": info.leverage,
        }

    async def _handle_get_positions(self, websocket, msg: BridgeMessage):
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._mt5_get_positions)
        await websocket.send(BridgeMessage(
            type=MessageType.POSITIONS_DATA,
            id=msg.id,
            payload=result,
        ).to_json())

    def _mt5_get_positions(self) -> dict:
        positions = mt5.positions_get()
        if positions is None:
            return {"ok": False, "error": str(mt5.last_error())}
        return {
            "ok": True,
            "positions": [
                {
                    "ticket": p.ticket,
                    "symbol": p.symbol,
                    "type": p.type,
                    "volume": p.volume,
                    "price_open": p.price_open,
                    "price_current": p.price_current,
                    "sl": p.sl,
                    "tp": p.tp,
                    "profit": p.profit,
                    "magic": p.magic,
                    "comment": p.comment,
                    "time": p.time,
                }
                for p in positions
            ],
        }

    async def _handle_get_open_orders(self, websocket, msg: BridgeMessage):
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._mt5_get_open_orders)
        await websocket.send(BridgeMessage(
            type=MessageType.ORDERS_DATA,
            id=msg.id,
            payload=result,
        ).to_json())

    def _mt5_get_open_orders(self) -> dict:
        orders = mt5.orders_get()
        if orders is None:
            return {"ok": False, "error": str(mt5.last_error())}
        return {
            "ok": True,
            "orders": [
                {
                    "ticket": o.ticket,
                    "symbol": o.symbol,
                    "type": o.type,
                    "volume": o.volume_current,
                    "price": o.price_open,
                    "sl": o.sl,
                    "tp": o.tp,
                    "magic": o.magic,
                    "comment": o.comment,
                    "time": o.time_setup,
                }
                for o in orders
            ],
        }

    async def _handle_get_order_status(self, websocket, msg: BridgeMessage):
        ticket = msg.payload.get("ticket")
        if not ticket:
            await websocket.send(BridgeMessage(
                type=MessageType.ERROR,
                id=msg.id,
                payload={"error": "Missing ticket"},
            ).to_json())
            return
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._mt5_get_order_status, int(ticket))
        await websocket.send(BridgeMessage(
            type=MessageType.ORDER_RESULT,
            id=msg.id,
            payload=result,
        ).to_json())

    def _mt5_get_order_status(self, ticket: int) -> dict:
        orders = mt5.orders_get(ticket=ticket)
        if orders and len(orders) > 0:
            o = orders[0]
            return {
                "ok": True,
                "status": "pending",
                "ticket": o.ticket,
                "symbol": o.symbol,
                "type": o.type,
                "volume": o.volume_current,
                "price": o.price_open,
            }
        # Not in pending orders — check history
        history = mt5.history_orders_get(ticket=ticket)
        if history and len(history) > 0:
            o = history[0]
            return {
                "ok": True,
                "status": "completed",
                "ticket": o.ticket,
                "symbol": o.symbol,
                "type": o.type,
                "volume": o.volume_current,
                "price": o.price_current,
            }
        return {"ok": False, "error": f"Order {ticket} not found"}

    async def _handle_get_tick(self, websocket, msg: BridgeMessage):
        symbol = msg.payload.get("symbol")
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._mt5_get_tick, symbol)
        await websocket.send(BridgeMessage(
            type=MessageType.TICK_DATA,
            id=msg.id,
            payload=result,
        ).to_json())

    def _mt5_get_tick(self, symbol: str) -> dict:
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return {"ok": False, "error": f"No tick for {symbol}"}
        return {
            "ok": True,
            "bid": tick.bid,
            "ask": tick.ask,
            "last": tick.last,
            "time": tick.time,
        }

    async def _handle_cancel_order(self, websocket, msg: BridgeMessage):
        ticket = msg.payload.get("ticket")
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._mt5_cancel_order, int(ticket))
        await websocket.send(BridgeMessage(
            type=MessageType.ORDER_RESULT,
            id=msg.id,
            payload=result,
        ).to_json())

    def _mt5_cancel_order(self, ticket: int) -> dict:
        request = {
            "action": mt5.TRADE_ACTION_REMOVE,
            "order": ticket,
        }
        result = mt5.order_send(request)
        if result is None:
            return {"ok": False, "error": str(mt5.last_error())}
        return {
            "ok": result.retcode == mt5.TRADE_RETCODE_DONE,
            "retcode": result.retcode,
            "comment": result.comment,
        }

    async def _handle_modify_order(self, websocket, msg: BridgeMessage):
        payload = msg.payload
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._mt5_modify_order, payload)
        await websocket.send(BridgeMessage(
            type=MessageType.ORDER_RESULT,
            id=msg.id,
            payload=result,
        ).to_json())

    def _mt5_modify_order(self, payload: dict) -> dict:
        request = {
            "action": mt5.TRADE_ACTION_MODIFY,
            "order": int(payload["ticket"]),
            "price": float(payload.get("price", 0)),
            "sl": float(payload.get("sl", 0)),
            "tp": float(payload.get("tp", 0)),
        }
        result = mt5.order_send(request)
        if result is None:
            return {"ok": False, "error": str(mt5.last_error())}
        return {
            "ok": result.retcode == mt5.TRADE_RETCODE_DONE,
            "retcode": result.retcode,
            "comment": result.comment,
        }

    async def _handle_ping(self, websocket, msg: BridgeMessage):
        await websocket.send(BridgeMessage(
            type=MessageType.PONG,
            id=msg.id,
            payload={"terminal_connected": self._terminal_connected},
        ).to_json())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    config = BridgeConfig.from_env()
    server = MT5BridgeServer(config)
    asyncio.run(server.start())
```

#### 2d. MT5 Bridge Client (Linux Side)

```python
# mt5-bridge-client/client.py
# Runs on Linux host inside Docker container

import asyncio
import json
import logging
import os
import time
import uuid
from typing import Optional, Callable, Awaitable

import websockets

from shared.bridge_protocol import BridgeMessage, MessageType

logger = logging.getLogger("mt5-bridge-client")


class MT5BridgeClient:
    """WebSocket client that connects to remote MT5 bridge server."""

    def __init__(
        self,
        bridge_url: str,
        auth_secret: str = "",
        reconnect_interval: float = 5.0,
        max_reconnect_interval: float = 60.0,
        heartbeat_interval: float = 15.0,
        request_timeout: float = 30.0,
    ):
        self.bridge_url = bridge_url
        self.auth_secret = auth_secret
        self._reconnect_interval = reconnect_interval
        self._max_reconnect_interval = max_reconnect_interval
        self._heartbeat_interval = heartbeat_interval
        self._request_timeout = request_timeout

        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._pending: dict[str, asyncio.Future] = {}
        self._connected = asyncio.Event()
        self._running = False
        self._on_disconnect: Optional[Callable] = None

    async def connect(self):
        """Start connection loop with auto-reconnect."""
        self._running = True
        backoff = self._reconnect_interval

        while self._running:
            try:
                async with websockets.connect(
                    self.bridge_url,
                    ping_interval=20,
                    ping_timeout=10,
                    max_size=1_048_576,
                ) as ws:
                    self._ws = ws
                    backoff = self._reconnect_interval  # reset on success

                    # Authenticate
                    if not await self._authenticate(ws):
                        logger.error("Authentication failed")
                        await asyncio.sleep(backoff)
                        continue

                    self._connected.set()
                    logger.info(f"Connected to MT5 bridge at {self.bridge_url}")

                    # Start heartbeat
                    heartbeat_task = asyncio.create_task(self._heartbeat_loop())

                    try:
                        await self._receive_loop(ws)
                    finally:
                        heartbeat_task.cancel()
                        self._connected.clear()

            except (websockets.ConnectionClosed, OSError, ConnectionRefusedError) as e:
                logger.warning(f"Bridge connection lost: {e}. Reconnecting in {backoff}s...")
                self._connected.clear()
                if self._on_disconnect:
                    await self._on_disconnect()
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, self._max_reconnect_interval)

    async def _authenticate(self, ws) -> bool:
        """Send auth message and verify response."""
        auth_msg = {"type": "auth", "payload": {"token": self.auth_secret}}
        await ws.send(json.dumps(auth_msg))

        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
            resp = json.loads(raw)
            return resp.get("payload", {}).get("auth", False)
        except (asyncio.TimeoutError, json.JSONDecodeError):
            return False

    async def _receive_loop(self, ws):
        """Process incoming messages, routing responses to pending futures."""
        async for raw in ws:
            try:
                msg = BridgeMessage.from_json(raw)
            except (json.JSONDecodeError, ValueError):
                continue

            # Route response to pending request
            if msg.id in self._pending:
                future = self._pending.pop(msg.id)
                if not future.done():
                    future.set_result(msg)
            elif msg.type in (MessageType.POSITION_UPDATE, MessageType.ORDER_UPDATE):
                # Handle unsolicited updates (push to event bus)
                logger.info(f"Received unsolicited update: {msg.type.value}")

    async def _heartbeat_loop(self):
        """Send periodic pings to detect silent connection drops."""
        while True:
            await asyncio.sleep(self._heartbeat_interval)
            try:
                result = await self.send_request(MessageType.PING, {})
                if not result.payload.get("terminal_connected"):
                    logger.warning("MT5 terminal is not connected on bridge server")
            except Exception as e:
                logger.error(f"Heartbeat failed: {e}")
                break

    async def send_request(
        self, msg_type: MessageType, payload: dict, timeout: float = None
    ) -> BridgeMessage:
        """Send a request and wait for response."""
        await self._connected.wait()

        msg = BridgeMessage(type=msg_type, payload=payload)
        future: asyncio.Future[BridgeMessage] = asyncio.get_event_loop().create_future()
        self._pending[msg.id] = future

        await self._ws.send(msg.to_json())

        try:
            return await asyncio.wait_for(future, timeout or self._request_timeout)
        except asyncio.TimeoutError:
            self._pending.pop(msg.id, None)
            raise TimeoutError(f"Bridge request {msg_type.value} timed out")

    # --- Public API (drop-in for MT5Connector) ---

    async def place_order(self, order_params: dict) -> dict:
        resp = await self.send_request(MessageType.PLACE_ORDER, order_params)
        return resp.payload

    async def cancel_order(self, ticket: int) -> dict:
        resp = await self.send_request(MessageType.CANCEL_ORDER, {"ticket": ticket})
        return resp.payload

    async def get_balance(self) -> dict:
        resp = await self.send_request(MessageType.GET_BALANCE, {})
        return resp.payload

    async def get_positions(self) -> dict:
        resp = await self.send_request(MessageType.GET_POSITIONS, {})
        return resp.payload

    async def get_open_orders(self) -> dict:
        resp = await self.send_request(MessageType.GET_OPEN_ORDERS, {})
        return resp.payload

    async def get_tick(self, symbol: str) -> dict:
        resp = await self.send_request(MessageType.GET_TICK, {"symbol": symbol})
        return resp.payload

    async def close(self):
        self._running = False
        if self._ws:
            await self._ws.close()
```

#### 2e. Windows Deployment Guide

Deploy the bridge server on a Windows VPS (AWS EC2 Windows, Azure Windows VM, or a local Windows machine).

**Requirements:**
- Windows Server 2019+ or Windows 10+
- Python 3.10+
- MetaTrader 5 terminal installed and logged in
- Network access to Linux host on port 8765

**Setup script (`setup-bridge.ps1`):**

```powershell
# Windows VPS setup script
param(
    [string]$Mt5Login,
    [string]$Mt5Password,
    [string]$Mt5Server,
    [string]$BridgeSecret
)

# Install Python if not present
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Install Python 3.10+ from https://python.org"
    exit 1
}

# Install dependencies
pip install MetaTrader5 websockets

# Set environment variables (persist for service)
[Environment]::SetEnvironmentVariable("MT5_LOGIN", $Mt5Login, "Machine")
[Environment]::SetEnvironmentVariable("MT5_PASSWORD", $Mt5Password, "Machine")
[Environment]::SetEnvironmentVariable("MT5_SERVER", $Mt5Server, "Machine")
[Environment]::SetEnvironmentVariable("BRIDGE_SECRET", $BridgeSecret, "Machine")
[Environment]::SetEnvironmentVariable("BRIDGE_PORT", "8765", "Machine")

# Register as Windows service (requires NSSM)
# nssm install MT5Bridge "C:\Python310\python.exe" "C:\mt5-bridge\server.py"
# nssm start MT5Bridge

Write-Host "Bridge server configured. Start with: python server.py"
```

#### 2f. Key Architecture Decisions

| Decision | Rationale |
|----------|-----------|
| WebSocket (not REST) | Persistent connection, low latency, server push for position updates |
| JSON (not protobuf) | Debuggability, human-readable wire format, Python-native |
| Auth via shared secret | Simple, sufficient for internal network; upgrade to mTLS for production |
| Concurrency semaphore | MT5 terminal is single-threaded; too many concurrent calls cause timeouts |
| Auto-reconnect with backoff | Network interruptions are inevitable between Linux host and Windows VPS |
| Heartbeat every 15s | Detects silent TCP drops faster than OS-level keepalive (~2 hours) |
| Thread pool for MT5 calls | MT5 Python package is synchronous; `run_in_executor` prevents blocking the event loop |

---

## Bug 3: CCXT Balance Iterator Bug 🔴

### Problem

In `CCXTConnector.get_balance()`, the code iterates over all keys in the `fetch_balance()` response and treats them as currency codes. But `fetch_balance()` returns metadata keys (`'info'`, `'free'`, `'used'`, `'total'`, `'timestamp'`, `'datetime'`, `'nonce'`) alongside actual currency keys (`'BTC'`, `'ETH'`, `'USDT'`).

**Broken code:**
```python
for currency, data in balance.items():
    if isinstance(data, dict) and data.get("total", 0) and data["total"] > 0:
        result.append(UnifiedBalance(
            currency=currency,  # ← 'info', 'free', 'total' etc. get here
            ...
        ))
```

**Impact:** The code tries to create `UnifiedBalance` objects with `currency='info'`, `currency='free'`, etc. This either raises exceptions (when `data` is not a dict in the expected shape) or produces garbage entries with nonsensical currencies.

### Root Cause

CCXT's `fetch_balance()` returns a flat dict mixing structured currency data with top-level metadata:

```python
{
    'info': {...},           # Raw exchange response (dict, but not currency data)
    'BTC': {'free': 0.5, 'used': 0.1, 'total': 0.6},  # ← valid currency
    'ETH': {'free': 10.0, 'used': 0.0, 'total': 10.0}, # ← valid currency
    'USDT': {'free': 1000, 'used': 500, 'total': 1500}, # ← valid currency
    'free': {'BTC': 0.5, 'ETH': 10.0, 'USDT': 1000},   # ← metadata
    'used': {'BTC': 0.1, 'ETH': 0.0, 'USDT': 500},     # ← metadata
    'total': {'BTC': 0.6, 'ETH': 10.0, 'USDT': 1500},  # ← metadata
    'timestamp': 1689100000,  # ← metadata (int, not dict)
    'datetime': '2025-07-11...',  # ← metadata (str, not dict)
}
```

### Fix

Use CCXT's built-in structure or explicitly filter out metadata keys.

```python
# In CCXTConnector.get_balance()

async def get_balance(self) -> list[UnifiedBalance]:
    """Fetch and parse account balances, filtering out metadata keys."""
    balance = await self._exchange.fetch_balance()
    result = []

    # --- FIX: Use the structured 'currencies' sub-dict if available,
    #     otherwise filter known metadata keys ---
    # CCXT provides a 'currencies' key with normalized currency data
    currency_data = balance.get("currencies", {})

    if currency_data:
        # Preferred path: use the structured currencies dict
        for currency, data in currency_data.items():
            if not isinstance(data, dict):
                continue
            total = float(data.get("total", 0) or 0)
            if total <= 0:
                continue
            result.append(UnifiedBalance(
                currency=currency,
                available=float(data.get("free", 0) or 0),
                locked=float(data.get("used", 0) or 0),
                total=total,
                usd_value=float(data.get("usd_value", 0) or 0),
            ))
    else:
        # Fallback: filter known metadata keys from the flat dict
        _METADATA_KEYS = frozenset({
            "info", "free", "used", "total",
            "timestamp", "datetime", "nonce",
        })
        for currency, data in balance.items():
            if currency in _METADATA_KEYS:
                continue
            if not isinstance(data, dict):
                continue
            total = float(data.get("total", 0) or 0)
            if total <= 0:
                continue
            result.append(UnifiedBalance(
                currency=currency,
                available=float(data.get("free", 0) or 0),
                locked=float(data.get("used", 0) or 0),
                total=total,
            ))

    return result
```

### Alternative Fix (Stricter)

If you want to be even more defensive, validate that the currency key looks like an actual currency code:

```python
import re

_CURRENCY_PATTERN = re.compile(r"^[A-Z0-9]{2,10}$")  # BTC, ETH, USDT, etc.

def _is_currency_key(key: str) -> bool:
    """Check if a key looks like a currency code (not metadata)."""
    return bool(_CURRENCY_PATTERN.match(key))

# In the fallback path:
for currency, data in balance.items():
    if not _is_currency_key(currency):
        continue
    # ...
```

### Test Cases

```python
import pytest
from unittest.mock import AsyncMock

@pytest.fixture
def mock_exchange():
    exchange = AsyncMock()
    return exchange

async def test_balance_skips_metadata_keys(mock_exchange):
    """Metadata keys like 'info', 'free', 'total' should not appear as currencies."""
    mock_exchange.fetch_balance.return_value = {
        "info": {"balances": []},
        "BTC": {"free": 0.5, "used": 0.1, "total": 0.6},
        "USDT": {"free": 1000, "used": 500, "total": 1500},
        "free": {"BTC": 0.5, "USDT": 1000},
        "used": {"BTC": 0.1, "USDT": 500},
        "total": {"BTC": 0.6, "USDT": 1500},
        "timestamp": 1689100000,
        "datetime": "2025-07-11T00:00:00Z",
    }

    connector = CCXTConnector(...)
    connector._exchange = mock_exchange
    balances = await connector.get_balance()

    currencies = {b.currency for b in balances}
    assert currencies == {"BTC", "USDT"}
    assert "info" not in currencies
    assert "free" not in currencies
    assert "total" not in currencies
    assert "timestamp" not in currencies

async def test_balance_excludes_zero_balances(mock_exchange):
    """Zero-balance currencies should be excluded."""
    mock_exchange.fetch_balance.return_value = {
        "BTC": {"free": 0.5, "used": 0.0, "total": 0.5},
        "ETH": {"free": 0.0, "used": 0.0, "total": 0.0},
        "USDT": {"free": 1000, "used": 0, "total": 1000},
    }

    connector = CCXTConnector(...)
    connector._exchange = mock_exchange
    balances = await connector.get_balance()

    currencies = {b.currency for b in balances}
    assert "ETH" not in currencies  # zero total
    assert currencies == {"BTC", "USDT"}

async def test_balance_uses_currencies_sub_dict(mock_exchange):
    """When 'currencies' key exists, use it instead of flat iteration."""
    mock_exchange.fetch_balance.return_value = {
        "info": {},
        "currencies": {
            "BTC": {"free": 0.5, "used": 0.1, "total": 0.6, "usd_value": 18000},
            "USDT": {"free": 1000, "used": 500, "total": 1500, "usd_value": 1500},
        },
        # Flat keys also present but should be ignored
        "BTC": {"free": 0.5, "used": 0.1, "total": 0.6},
        "free": {"BTC": 0.5, "USDT": 1000},
        "total": {"BTC": 0.6, "USDT": 1500},
    }

    connector = CCXTConnector(...)
    connector._exchange = mock_exchange
    balances = await connector.get_balance()

    assert len(balances) == 2
    btc = next(b for b in balances if b.currency == "BTC")
    assert btc.total == 0.6
    assert btc.usd_value == 18000
```

---

## Additional P0 Fixes (from Review)

### Fix 4: CCXT Streaming Hardcoded to Binance

**Problem:** `subscribe_ticker()` always creates `ccxtpro.binance()` regardless of the connector's exchange.

**Fix:**

```python
async def subscribe_ticker(self, symbol: str) -> AsyncIterator[UnifiedTicker]:
    import ccxt.pro as ccxtpro

    # Resolve exchange class dynamically from connector's exchange ID
    exchange_id = self._credentials.endpoint  # e.g., "binance", "bybit", "okx"
    exchange_class = getattr(ccxtpro, exchange_id, None)
    if exchange_class is None:
        raise BrokerError(
            self.broker_id,
            f"Streaming not supported for exchange: {exchange_id}"
        )

    exchange_pro = exchange_class({
        "apiKey": self._credentials.api_key,
        "secret": self._credentials.api_secret,
        "options": {"defaultType": "spot"},
    })

    try:
        while True:
            try:
                ticker = await exchange_pro.watch_ticker(self._to_broker_symbol(symbol))
                yield UnifiedTicker(
                    symbol=symbol,
                    bid=ticker.get("bid", 0),
                    ask=ticker.get("ask", 0),
                    last=ticker.get("last", 0),
                    volume=ticker.get("baseVolume", 0),
                    timestamp=ticker.get("timestamp", int(time.time() * 1000)),
                )
            except (ccxt.NetworkError, ccxt.ExchangeNotAvailable) as e:
                logger.warning(f"Ticker stream error for {self.broker_id}: {e}")
                await asyncio.sleep(1)
    finally:
        await exchange_pro.close()
```

### Fix 5: Add Post-Trade Reconciliation

**Problem:** The system never re-verifies order state with the broker after placement. Portfolio drifts from reality.

**Fix:**

```python
# broker/reconciliation.py

import asyncio
import logging
from datetime import datetime, timedelta

logger = logging.getLogger("reconciliation")


class OrderReconciler:
    """Periodically verify system state matches broker state."""

    def __init__(self, registry, db, interval_seconds: int = 30):
        self._registry = registry
        self._db = db
        self._interval = interval_seconds
        self._running = False

    async def start(self):
        self._running = True
        while self._running:
            try:
                await self._reconcile_all()
            except Exception as e:
                logger.error(f"Reconciliation cycle failed: {e}")
            await asyncio.sleep(self._interval)

    async def stop(self):
        self._running = False

    async def _reconcile_all(self):
        """Reconcile orders across all connected brokers."""
        for broker_id, connector in self._registry.get_all_connectors():
            try:
                await self._reconcile_broker(broker_id, connector)
            except Exception as e:
                logger.error(f"Reconciliation failed for {broker_id}: {e}")

    async def _reconcile_broker(self, broker_id: str, connector):
        """Compare system orders against broker state for one broker."""
        system_orders = await self._db.get_open_orders_for_broker(broker_id)
        if not system_orders:
            return

        broker_positions = set()
        broker_open_orders = set()

        # Fetch current broker state
        try:
            positions = await connector.get_positions()
            broker_positions = {p.get("broker_ticket") or p.get("id") for p in positions}
        except Exception as e:
            logger.warning(f"Failed to fetch positions from {broker_id}: {e}")

        try:
            open_orders = await connector.get_open_orders()
            broker_open_orders = {o.get("broker_order_id") for o in open_orders}
        except Exception as e:
            logger.warning(f"Failed to fetch open orders from {broker_id}: {e}")

        for sys_order in system_orders:
            broker_id_ref = sys_order.broker_order_id

            if sys_order.status == "pending":
                if broker_id_ref not in broker_open_orders:
                    # Order disappeared from broker — check what happened
                    try:
                        status = await self._check_order_fate(connector, sys_order)
                        if status != sys_order.status:
                            await self._db.update_order_status(
                                sys_order.order_id, status
                            )
                            logger.info(
                                f"Reconciled order {sys_order.order_id}: "
                                f"{sys_order.status} → {status}"
                            )
                    except Exception as e:
                        logger.warning(
                            f"Could not determine fate of order {sys_order.order_id}: {e}"
                        )

            elif sys_order.status == "filled":
                # Verify position still exists (might have been closed externally)
                if broker_id_ref and broker_id_ref not in broker_positions:
                    logger.warning(
                        f"Order {sys_order.order_id} marked as filled but "
                        f"position {broker_id_ref} not found on {broker_id}"
                    )
                    # Don't auto-update — flag for manual review

    async def _check_order_fate(self, connector, sys_order) -> str:
        """Determine what happened to an order that's no longer pending."""
        try:
            order_status = await connector.get_order_status(sys_order.broker_order_id)
            return order_status.get("status", "unknown")
        except Exception:
            return "unknown"
```

---

## Implementation Priority

| Priority | Fix | Effort | Risk if Skipped |
|----------|-----|--------|-----------------|
| **P0-1** | MT5 pending order pricing | 2h | Orders execute at wrong price or get rejected |
| **P0-2** | Docker Compose + bridge architecture | 1-2 days | MT5 integration completely non-functional |
| **P0-3** | CCXT balance iterator | 30min | Garbage balance data, wrong risk calculations |
| **P0-4** | CCXT streaming hardcoded | 30min | Streaming broken for all non-Binance exchanges |
| **P0-5** | Post-trade reconciliation | 4h | Portfolio state drifts silently from reality |

---

## Testing Strategy

### Unit Tests
- MT5 pricing: mock `mt5.symbol_info_tick()`, verify order requests for each order type
- Balance iterator: feed known `fetch_balance()` output, verify only currency entries returned
- Streaming: mock `ccxtpro` classes, verify correct exchange class instantiated

### Integration Tests
- MT5 bridge: run bridge server on Windows VM, client on Linux, verify round-trip order placement
- CCXT: use exchange sandbox/testnet, verify balance parsing with real API responses
- Reconciliation: simulate order state drift, verify detection and correction

### Chaos Tests
- Kill MT5 bridge server mid-order, verify client reconnects and order state is recovered
- Inject network latency (500ms+) between bridge client and server, verify timeout handling
- Corrupt WebSocket frames, verify client handles gracefully

---

*Fix document generated: 2026-07-11*
*Bugs addressed: 3 critical + 2 additional P0 fixes*
*Estimated implementation effort: 2-3 days for all P0 items*
