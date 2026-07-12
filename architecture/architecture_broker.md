# Alpha Stack — Broker Abstraction Layer Architecture

> **Version:** 1.0 · **Date:** 2026-07-11 · **Author:** Architecture Team
> **Source Research:** [`research/research_broker_connection.md`](../research/research_broker_connection.md), [`research/research_hybrid_broker_architecture.md`](../research/research_hybrid_broker_architecture.md), [`research/research_multi_broker_integration.md`](../research/research_multi_broker_integration.md) — Broker connection, hybrid broker architecture, and multi-broker integration
> **Status:** Architecture Complete

---

**Author:** Broker Integration Architect
**Date:** 2026-07-11
**Status:** Architecture Design
**Dependencies:** Hybrid Broker Architecture Research, Multi-Broker Integration Research, Broker Connection Research, Execution Algorithms Research

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Design Principles](#2-design-principles)
3. [System Architecture Overview](#3-system-architecture-overview)
4. [Core Interface: `BrokerConnector`](#4-core-interface-brokerconnector)
5. [Connector Implementations](#5-connector-implementations)
6. [Symbol Normalization Layer](#6-symbol-normalization-layer)
7. [Unified Order Manager](#7-unified-order-manager)
8. [Portfolio Aggregator](#8-portfolio-aggregator)
9. [Smart Order Router](#9-smart-order-router)
10. [Execution Engine](#10-execution-engine)
11. [Connection Lifecycle & Resilience](#11-connection-lifecycle--resilience)
12. [Credential Vault & Security](#12-credential-vault--security)
13. [Event Bus & Real-Time Data](#13-event-bus--real-time-data)
14. [Error Taxonomy & Recovery](#14-error-taxonomy--recovery)
15. [Performance & Rate Limiting](#15-performance--rate-limiting)
16. [Deployment Architecture](#16-deployment-architecture)
17. [Testing Strategy](#17-testing-strategy)
18. [Implementation Roadmap](#18-implementation-roadmap)
19. [Appendices](#19-appendices)

---

## 1. Executive Summary

### Problem

Alpha Stack currently connects to a single broker (FXPesa via MT5) for forex only. To become a multi-asset, multi-broker platform, we need a unified abstraction layer that lets the strategy engine, risk engine, and portfolio view operate broker-agnostically.

### Solution

A **plugin-based broker abstraction layer** where each broker is a connector implementing a standard interface. The core system never knows which broker it's talking to — it speaks one language, and the connectors translate.

```
Strategy Engine → "Buy 0.1 BTC/USD at market" → Unified Order Manager → Smart Router → CCXT Connector → Binance
                 ↕ same interface ↕                                                                              
                 "Buy 1.0 EUR/USD at market" → MT5 Connector → FXPesa
```

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Language | Python 3.11+ | Best ecosystem (ccxt, MT5, ta-lib), async/await native |
| Async model | `asyncio` | Concurrent broker connections without threads |
| Connector pattern | Abstract base class + plugins | Add brokers without touching core |
| Crypto library | CCXT | 104+ exchanges, unified API, MIT, actively maintained |
| State management | PostgreSQL + Redis | ACID for orders/positions, Redis for real-time cache |
| Event system | Async event bus (in-process) + Redis Streams (cross-process) | Low-latency internal, durable cross-service |
| Credential storage | Per-broker AES-256 encryption, derived from user master key | Security isolation between brokers |

---

## 2. Design Principles

### P1: Plugin Architecture
Every broker is a connector module implementing `BrokerConnector`. Adding a new broker = writing a new class. Zero changes to core.

### P2: Event-Driven
All connectors emit typed events (`OrderFilled`, `PositionUpdated`, `BalanceChanged`, `PriceTick`) to a central event bus. Core components subscribe to events, never poll.

### P3: Stateless Core
The Alpha Stack core (order manager, risk engine, portfolio aggregator) holds no broker-specific state. All state flows through normalized data structures. Broker quirks are absorbed by connectors.

### P4: Failover by Default
If a broker connection drops, the system automatically retries, reconnects, and optionally routes to alternatives. No silent failures.

### P5: Progressive Complexity
Start simple (spread filter + limit orders at $7 capital). Add TWAP/VWAP/SOR only when position sizes justify it ($500+). The architecture supports both — the execution engine decides which path.

### P6: Security by Isolation
Each broker's credentials are encrypted with a separate derived key. Compromising one broker connection doesn't expose others. Credentials never leave the user's device.

---

## 3. System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ALPHA STACK CORE                                    │
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │   Strategy    │  │     Risk     │  │  Portfolio    │  │  Execution     │  │
│  │   Engine      │  │     Engine   │  │  Aggregator   │  │  Engine        │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └───────┬────────┘  │
│         │                  │                  │                   │          │
│  ┌──────┴──────────────────┴──────────────────┴───────────────────┴───────┐  │
│  │                        UNIFIED ORDER MANAGER                           │  │
│  │              (Single source of truth for all orders)                   │  │
│  └──────────────────────────────────┬────────────────────────────────────┘  │
│                                     │                                       │
│  ┌──────────────────────────────────┴────────────────────────────────────┐  │
│  │                      SMART ORDER ROUTER                               │  │
│  │          (Best execution, failover, arbitrage detection)              │  │
│  └──────────────────────────────────┬────────────────────────────────────┘  │
│                                     │                                       │
│  ┌──────────────────────────────────┴────────────────────────────────────┐  │
│  │                    BROKER CONNECTOR REGISTRY                          │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │  │
│  │  │   MT5    │  │   CCXT   │  │   REST   │  │   FIX    │  │  IBKR  │ │  │
│  │  │Connector │  │Connector │  │Connector │  │Connector │  │Connec. │ │  │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └───┬────┘ │  │
│  └───────┼──────────────┼──────────────┼──────────────┼────────────┼──────┘  │
│          │              │              │              │            │         │
│  ┌───────┴──────────────┴──────────────┴──────────────┴────────────┴──────┐  │
│  │                         EVENT BUS (asyncio.Queue)                      │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                      CREDENTIAL VAULT (AES-256)                       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
           │                │               │              │           │
     ┌─────┴─────┐    ┌────┴────┐    ┌─────┴─────┐  ┌────┴────┐ ┌────┴────┐
     │  FXPesa   │    │ Binance │    │   OANDA   │  │   IBKR  │ │   IG    │
     │   MT5     │    │  Bybit  │    │           │  │   FIX   │ │ Markets │
     │           │    │  OKX    │    │           │  │         │ │         │
     └───────────┘    └─────────┘    └───────────┘  └─────────┘ └─────────┘
       Forex            Crypto          Forex        Multi-asset    Forex/CFD
```

### Data Flow: Order Placement

```
1. Strategy Engine emits: OrderRequest(symbol="EUR/USD", side="buy", type="limit", qty=0.1, price=1.0850)
2. Unified Order Manager:
   a. Validates order structure
   b. Assigns internal order_id (UUID)
   c. Records order in PostgreSQL (status=PENDING)
   d. Passes to Risk Engine for pre-trade check
3. Risk Engine:
   a. Checks total exposure across all brokers
   b. Checks margin availability
   c. Checks correlation limits
   d. Returns: APPROVED / REJECTED(reason)
4. Smart Order Router:
   a. Queries which brokers can trade EUR/USD
   b. Scores each broker (spread, liquidity, latency, fees, reliability)
   c. Selects best broker (or splits across brokers for large orders)
5. Broker Connector (e.g., MT5Connector):
   a. Translates UnifiedOrder → broker-specific format
   b. Sends order via broker API
   c. Receives confirmation (broker_order_id, fill status)
   d. Emits event: OrderFilled(order_id, broker_order_id, fill_price, fill_qty)
6. Unified Order Manager:
   a. Updates order status in PostgreSQL
   b. Updates position in Portfolio Aggregator
   c. Emits event to Strategy Engine
```

---

## 4. Core Interface: `BrokerConnector`

This is the contract every broker connector must implement. It's the single most important abstraction in the system.

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, AsyncIterator, Callable, Any
import asyncio


# ─── Enums ────────────────────────────────────────────────────────────────────

class BrokerType(Enum):
    MT5 = "mt5"
    CCXT = "ccxt"
    REST_API = "rest_api"
    FIX = "fix"
    WEBSOCKET = "websocket"
    IBKR = "ibkr"

class AssetClass(Enum):
    FOREX = "forex"
    CRYPTO = "crypto"
    CFD = "cfd"
    EQUITIES = "equities"
    FUTURES = "futures"
    OPTIONS = "options"

class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"

class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"

class OrderStatus(Enum):
    PENDING = "pending"            # Created, not yet sent to broker
    SUBMITTED = "submitted"        # Sent to broker, awaiting ack
    OPEN = "open"                  # Acknowledged by broker, working
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"

class ConnectionStatus(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    DEGRADED = "degraded"          # Connected but high latency / errors
    DISABLED = "disabled"          # Manually disabled by user


# ─── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class BrokerCredentials:
    broker_id: str                  # Unique ID for this connection (UUID)
    broker_type: BrokerType
    endpoint: str                   # Server URL / exchange name
    api_key: str
    api_secret: str
    additional: dict = field(default_factory=dict)  # Broker-specific fields
    # additional may contain: login, passphrase, account_id, sender_comp_id, etc.

@dataclass
class UnifiedOrder:
    order_id: str                   # Alpha Stack internal UUID
    symbol: str                     # Normalized symbol (e.g., "EUR/USD", "BTC/USD")
    side: OrderSide
    order_type: OrderType
    quantity: float                 # In base currency units (lots for forex, coins for crypto)
    price: Optional[float]          # Limit price (None for market orders)
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    trailing_stop_pips: Optional[float] = None
    time_in_force: str = "GTC"      # GTC, IOC, FOK, DAY
    broker_id: Optional[str] = None # Set by router (None = auto-route)
    asset_class: Optional[AssetClass] = None
    metadata: dict = field(default_factory=dict)  # Strategy metadata, tags

@dataclass
class OrderConfirmation:
    order_id: str                   # Alpha Stack internal ID
    broker_order_id: str            # Broker's order ID
    broker_id: str
    status: OrderStatus
    fill_price: Optional[float] = None
    fill_quantity: Optional[float] = None
    commission: Optional[float] = None
    commission_currency: Optional[str] = None
    timestamp: Optional[int] = None
    raw_response: Optional[dict] = None  # Raw broker response for debugging

@dataclass
class UnifiedPosition:
    position_id: str                # Alpha Stack internal ID
    symbol: str                     # Normalized
    side: OrderSide
    quantity: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float
    margin_used: float
    broker_id: str
    asset_class: AssetClass
    opened_at: Optional[int] = None
    metadata: dict = field(default_factory=dict)

@dataclass
class UnifiedBalance:
    currency: str
    available: float                # Free to use
    locked: float                   # In orders / margin
    total: float
    broker_id: str
    usd_equivalent: Optional[float] = None  # Converted for aggregation

@dataclass
class UnifiedTicker:
    symbol: str
    bid: float
    ask: float
    last: float
    high_24h: Optional[float] = None
    low_24h: Optional[float] = None
    volume_24h: Optional[float] = None
    timestamp: int                  # Unix ms
    broker_id: str
    spread: float = 0.0             # Computed: ask - bid

@dataclass
class UnifiedOHLCV:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    broker_id: str

@dataclass
class BrokerCapabilities:
    """Describes what a broker connection can do."""
    broker_id: str
    broker_type: BrokerType
    asset_classes: list[AssetClass]
    supports_streaming: bool
    supports_stop_loss: bool
    supports_take_profit: bool
    supports_trailing_stop: bool
    supports_limit_orders: bool
    supports_stop_orders: bool
    supports_bracket_orders: bool
    supports_partial_fills: bool
    supports_oco_orders: bool      # One-Cancels-Other
    min_quantity: dict              # {symbol: min_qty}
    max_quantity: dict              # {symbol: max_qty}
    quantity_step: dict             # {symbol: step_size}
    rate_limits: dict               # {endpoint: (max_requests, per_seconds)}


# ─── Abstract Base Class ─────────────────────────────────────────────────────

class BrokerConnector(ABC):
    """
    Abstract base class for all broker connectors.

    Every broker (MT5, CCXT, OANDA, IBKR, FIX) implements this interface.
    The core system only interacts with this interface — never with
    broker-specific APIs directly.

    Threading model: All methods are async. Connectors use asyncio internally.
    A single connector instance handles one broker connection.
    """

    def __init__(self, credentials: BrokerCredentials):
        self._credentials = credentials
        self._connection_status = ConnectionStatus.DISCONNECTED
        self._capabilities: Optional[BrokerCapabilities] = None
        self._event_callback: Optional[Callable] = None

    @property
    def broker_id(self) -> str:
        return self._credentials.broker_id

    @property
    def broker_type(self) -> BrokerType:
        return self._credentials.broker_type

    @property
    def connection_status(self) -> ConnectionStatus:
        return self._connection_status

    # ─── Lifecycle ────────────────────────────────────────────────────────────

    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish connection to the broker.
        Returns True on success. Raises ConnectionError on failure.
        Must be idempotent — calling connect() when already connected is a no-op.
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """
        Clean disconnect. Release resources. Cancel subscriptions.
        Must be idempotent.
        """
        pass

    @abstractmethod
    async def health_check(self) -> ConnectionStatus:
        """
        Probe the connection. Returns current status.
        Used by the circuit breaker and monitoring.
        """
        pass

    def set_event_callback(self, callback: Callable) -> None:
        """Register a callback for broker events (fills, position changes, etc.)."""
        self._event_callback = callback

    # ─── Capabilities ─────────────────────────────────────────────────────────

    @abstractmethod
    async def get_capabilities(self) -> BrokerCapabilities:
        """Return what this broker connection supports."""
        pass

    @abstractmethod
    async def supports_symbol(self, symbol: str) -> bool:
        """Check if this broker can trade the given normalized symbol."""
        pass

    # ─── Market Data ──────────────────────────────────────────────────────────

    @abstractmethod
    async def get_symbols(self) -> list[str]:
        """Get all tradeable symbols (normalized)."""
        pass

    @abstractmethod
    async def get_ticker(self, symbol: str) -> UnifiedTicker:
        """Get current bid/ask/last for a symbol."""
        pass

    @abstractmethod
    async def get_orderbook(self, symbol: str, depth: int = 20) -> dict:
        """Get order book / depth of market."""
        pass

    @abstractmethod
    async def get_ohlcv(
        self, symbol: str, timeframe: str, limit: int = 100
    ) -> list[UnifiedOHLCV]:
        """
        Get candlestick data.
        timeframe: "1m", "5m", "15m", "1h", "4h", "1d", "1w"
        """
        pass

    # ─── Trading ──────────────────────────────────────────────────────────────

    @abstractmethod
    async def place_order(self, order: UnifiedOrder) -> OrderConfirmation:
        """
        Place an order on this broker.
        Returns OrderConfirmation with broker_order_id and status.
        Raises BrokerError on failure.
        """
        pass

    @abstractmethod
    async def cancel_order(self, broker_order_id: str) -> bool:
        """Cancel an open order. Returns True if cancelled. Raises if not found."""
        pass

    @abstractmethod
    async def modify_order(
        self,
        broker_order_id: str,
        price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> bool:
        """Modify an existing order's price, SL, or TP."""
        pass

    # ─── Account ──────────────────────────────────────────────────────────────

    @abstractmethod
    async def get_balance(self) -> list[UnifiedBalance]:
        """Get account balance(s). Returns list because multi-currency accounts."""
        pass

    @abstractmethod
    async def get_positions(self) -> list[UnifiedPosition]:
        """Get all open positions on this broker."""
        pass

    @abstractmethod
    async def get_open_orders(self) -> list[UnifiedOrder]:
        """Get all pending/working orders on this broker."""
        pass

    @abstractmethod
    async def get_order_status(self, broker_order_id: str) -> OrderConfirmation:
        """Query the status of a specific order."""
        pass

    # ─── Streaming (Optional) ─────────────────────────────────────────────────

    async def subscribe_ticker(self, symbol: str) -> AsyncIterator[UnifiedTicker]:
        """
        Subscribe to real-time price updates.
        Default implementation: raises NotImplementedError.
        Override in connectors that support streaming.
        """
        raise NotImplementedError(f"{self.broker_type} does not support ticker streaming")

    async def subscribe_trades(self) -> AsyncIterator[OrderConfirmation]:
        """
        Subscribe to real-time trade execution updates.
        Default implementation: raises NotImplementedError.
        """
        raise NotImplementedError(f"{self.broker_type} does not support trade streaming")

    async def subscribe_positions(self) -> AsyncIterator[UnifiedPosition]:
        """
        Subscribe to real-time position changes.
        Default implementation: raises NotImplementedError.
        """
        raise NotImplementedError(f"{self.broker_type} does not support position streaming")

    # ─── Internal Helpers ─────────────────────────────────────────────────────

    def _emit_event(self, event_type: str, data: dict) -> None:
        """Emit an event to the registered callback."""
        if self._event_callback:
            self._event_callback(event_type, self.broker_id, data)

    def _to_broker_symbol(self, normalized: str) -> str:
        """Convert normalized symbol to broker-specific format. Override if needed."""
        return normalized

    def _from_broker_symbol(self, broker_symbol: str) -> str:
        """Convert broker-specific symbol to normalized. Override if needed."""
        return broker_symbol
```

---

## 5. Connector Implementations

### 5.1 MT5 Connector (Forex)

```python
import MetaTrader5 as mt5
import asyncio
from concurrent.futures import ThreadPoolExecutor

class MT5Connector(BrokerConnector):
    """
    MetaTrader 5 connector for forex brokers (FXPesa, Exness, ICMarkets, etc.).

    MT5 Python API is synchronous and Windows-only. This connector wraps it
    in a ThreadPoolExecutor to make it async-compatible.

    Deployment: Requires Windows (or Wine/Bottles on Linux) with MT5 terminal.
    """

    # Symbol format: "EURUSD" (no separator) → normalized "EUR/USD"
    SYMBOL_MAP = {
        "EURUSD": "EUR/USD", "GBPUSD": "GBP/USD", "USDJPY": "USD/JPY",
        "AUDUSD": "AUD/USD", "USDCAD": "USD/CAD", "NZDUSD": "NZD/USD",
        "USDCHF": "USD/CHF", "XAUUSD": "XAU/USD", "XAGUSD": "XAG/USD",
        # Extensible — loaded from config
    }
    SYMBOL_MAP_REVERSE = {v: k for k, v in SYMBOL_MAP.items()}

    def __init__(self, credentials: BrokerCredentials):
        super().__init__(credentials)
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="mt5")
        self._login = int(credentials.additional["login"])
        self._server = credentials.endpoint
        self._password = credentials.api_secret

    async def connect(self) -> bool:
        if self._connection_status == ConnectionStatus.CONNECTED:
            return True

        self._connection_status = ConnectionStatus.CONNECTING

        # Run blocking MT5 calls in thread pool
        loop = asyncio.get_event_loop()
        success = await loop.run_in_executor(self._executor, self._do_connect)

        if success:
            self._connection_status = ConnectionStatus.CONNECTED
            self._emit_event("connected", {"broker_id": self.broker_id})
        else:
            self._connection_status = ConnectionStatus.DISCONNECTED
        return success

    def _do_connect(self) -> bool:
        if not mt5.initialize():
            return False
        authorized = mt5.login(
            login=self._login,
            password=self._password,
            server=self._server,
            timeout=10000,
        )
        return bool(authorized)

    async def disconnect(self) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(self._executor, mt5.shutdown)
        self._connection_status = ConnectionStatus.DISCONNECTED

    async def health_check(self) -> ConnectionStatus:
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(self._executor, mt5.terminal_info)
        if info is None or not info.connected:
            self._connection_status = ConnectionStatus.DISCONNECTED
        elif info.ping_last > 1000:  # >1s latency
            self._connection_status = ConnectionStatus.DEGRADED
        else:
            self._connection_status = ConnectionStatus.CONNECTED
        return self._connection_status

    async def place_order(self, order: UnifiedOrder) -> OrderConfirmation:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, self._place_order_sync, order)

    def _place_order_sync(self, order: UnifiedOrder) -> OrderConfirmation:
        mt5_symbol = self.SYMBOL_MAP_REVERSE.get(order.symbol, order.symbol.replace("/", ""))

        mt5_type = mt5.ORDER_TYPE_BUY if order.side == OrderSide.BUY else mt5.ORDER_TYPE_SELL

        if order.order_type == OrderType.MARKET:
            action = mt5.TRADE_ACTION_DEAL
        elif order.order_type in (OrderType.LIMIT, OrderType.STOP):
            action = mt5.TRADE_ACTION_PENDING

        tick = mt5.symbol_info_tick(mt5_symbol)
        price = order.price or (tick.ask if order.side == OrderSide.BUY else tick.bid)

        request = {
            "action": action,
            "symbol": mt5_symbol,
            "volume": order.quantity,
            "type": mt5_type,
            "price": price,
            "deviation": 30,  # 3 pips max slippage
            "magic": 202607,
            "comment": f"AS-{order.order_id[:8]}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        if order.stop_loss:
            request["sl"] = order.stop_loss
        if order.take_profit:
            request["tp"] = order.take_profit

        result = mt5.order_send(request)

        if result is None:
            raise BrokerError(self.broker_id, "order_send returned None", recoverable=True)

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            raise BrokerError(
                self.broker_id,
                f"Order rejected: {result.comment} (code {result.retcode})",
                recoverable=result.retcode in (10013, 10014, 10016),
            )

        confirmation = OrderConfirmation(
            order_id=order.order_id,
            broker_order_id=str(result.order),
            broker_id=self.broker_id,
            status=OrderStatus.FILLED if order.order_type == OrderType.MARKET else OrderStatus.OPEN,
            fill_price=result.price,
            fill_quantity=result.volume,
            timestamp=int(result.time),
            raw_response={"retcode": result.retcode, "comment": result.comment},
        )

        self._emit_event("order_placed", confirmation.__dict__)
        return confirmation

    async def get_ticker(self, symbol: str) -> UnifiedTicker:
        loop = asyncio.get_event_loop()
        mt5_symbol = self.SYMBOL_MAP_REVERSE.get(symbol, symbol.replace("/", ""))
        tick = await loop.run_in_executor(self._executor, mt5.symbol_info_tick, mt5_symbol)

        if tick is None:
            raise BrokerError(self.broker_id, f"No tick data for {symbol}")

        return UnifiedTicker(
            symbol=symbol,
            bid=tick.bid,
            ask=tick.ask,
            last=tick.last,
            timestamp=int(tick.time * 1000),
            broker_id=self.broker_id,
            spread=tick.ask - tick.bid,
        )

    async def get_balance(self) -> list[UnifiedBalance]:
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(self._executor, mt5.account_info)
        if info is None:
            raise BrokerError(self.broker_id, "Failed to get account info")

        return [UnifiedBalance(
            currency="USD",  # MT5 accounts are typically denominated in USD
            available=info.margin_free,
            locked=info.margin - info.margin_free if info.margin else 0,
            total=info.balance,
            broker_id=self.broker_id,
        )]

    async def get_positions(self) -> list[UnifiedPosition]:
        loop = asyncio.get_event_loop()
        positions = await loop.run_in_executor(self._executor, mt5.positions_get)
        if positions is None:
            return []

        result = []
        for pos in positions:
            result.append(UnifiedPosition(
                position_id=str(pos.ticket),
                symbol=self._from_broker_symbol(pos.symbol),
                side=OrderSide.BUY if pos.type == mt5.ORDER_TYPE_BUY else OrderSide.SELL,
                quantity=pos.volume,
                entry_price=pos.price_open,
                current_price=pos.price_current,
                unrealized_pnl=pos.profit,
                realized_pnl=0,
                margin_used=pos.margin,
                broker_id=self.broker_id,
                asset_class=AssetClass.FOREX,
            ))
        return result

    def _from_broker_symbol(self, broker_symbol: str) -> str:
        return self.SYMBOL_MAP.get(broker_symbol, broker_symbol)

    def _to_broker_symbol(self, normalized: str) -> str:
        return self.SYMBOL_MAP_REVERSE.get(normalized, normalized.replace("/", ""))
```

### 5.2 CCXT Connector (Crypto)

```python
import ccxt.async_support as ccxt
from typing import Optional

class CCXTConnector(BrokerConnector):
    """
    Crypto exchange connector via CCXT library.

    Supports 104+ exchanges: Binance, Bybit, OKX, Kraken, Coinbase, etc.
    Exchange is selected by credentials.endpoint (e.g., "binance", "bybit").

    CCXT handles: rate limiting, symbol normalization, order format translation.
    """

    def __init__(self, credentials: BrokerCredentials):
        super().__init__(credentials)
        self._exchange = None
        self._markets = {}

    async def connect(self) -> bool:
        if self._connection_status == ConnectionStatus.CONNECTED:
            return True

        self._connection_status = ConnectionStatus.CONNECTING

        exchange_name = self._credentials.endpoint  # "binance", "bybit", etc.
        exchange_class = getattr(ccxt, exchange_name, None)
        if exchange_class is None:
            raise BrokerError(self.broker_id, f"Unknown exchange: {exchange_name}", recoverable=False)

        self._exchange = exchange_class({
            "apiKey": self._credentials.api_key,
            "secret": self._credentials.api_secret,
            "enableRateLimit": True,
            "options": {
                "defaultType": self._credentials.additional.get("type", "spot"),
            },
        })

        # Set sandbox if configured
        if self._credentials.additional.get("sandbox", False):
            self._exchange.set_sandbox_mode(True)

        await self._exchange.load_markets()
        self._markets = self._exchange.markets
        self._connection_status = ConnectionStatus.CONNECTED
        self._emit_event("connected", {"broker_id": self.broker_id})
        return True

    async def disconnect(self) -> None:
        if self._exchange:
            await self._exchange.close()
        self._connection_status = ConnectionStatus.DISCONNECTED

    async def health_check(self) -> ConnectionStatus:
        try:
            await self._exchange.fetch_time()
            self._connection_status = ConnectionStatus.CONNECTED
        except Exception:
            self._connection_status = ConnectionStatus.DISCONNECTED
        return self._connection_status

    async def place_order(self, order: UnifiedOrder) -> OrderConfirmation:
        try:
            ccxt_symbol = self._to_broker_symbol(order.symbol)  # "BTC/USDT"

            params = {}
            if order.stop_loss:
                params["stopLoss"] = {"triggerPrice": order.stop_loss}
            if order.take_profit:
                params["takeProfit"] = {"triggerPrice": order.take_profit}

            result = await self._exchange.create_order(
                symbol=ccxt_symbol,
                type=order.order_type.value,
                side=order.side.value,
                amount=order.quantity,
                price=order.price,
                params=params,
            )

            confirmation = OrderConfirmation(
                order_id=order.order_id,
                broker_order_id=result["id"],
                broker_id=self.broker_id,
                status=self._map_order_status(result.get("status", "open")),
                fill_price=result.get("average") or result.get("price"),
                fill_quantity=result.get("filled"),
                commission=result.get("fee", {}).get("cost"),
                commission_currency=result.get("fee", {}).get("currency"),
                timestamp=result.get("timestamp"),
                raw_response=result,
            )

            self._emit_event("order_placed", confirmation.__dict__)
            return confirmation

        except ccxt.InsufficientFunds as e:
            raise BrokerError(self.broker_id, f"Insufficient funds: {e}", recoverable=False)
        except ccxt.InvalidOrder as e:
            raise BrokerError(self.broker_id, f"Invalid order: {e}", recoverable=False)
        except ccxt.NetworkError as e:
            raise BrokerError(self.broker_id, f"Network error: {e}", recoverable=True)
        except ccxt.ExchangeNotAvailable as e:
            raise BrokerError(self.broker_id, f"Exchange unavailable: {e}", recoverable=True)

    async def get_ticker(self, symbol: str) -> UnifiedTicker:
        ccxt_symbol = self._to_broker_symbol(symbol)
        ticker = await self._exchange.fetch_ticker(ccxt_symbol)

        return UnifiedTicker(
            symbol=symbol,
            bid=ticker.get("bid", 0),
            ask=ticker.get("ask", 0),
            last=ticker.get("last", 0),
            high_24h=ticker.get("high"),
            low_24h=ticker.get("low"),
            volume_24h=ticker.get("baseVolume"),
            timestamp=ticker.get("timestamp", 0),
            broker_id=self.broker_id,
            spread=(ticker.get("ask", 0) or 0) - (ticker.get("bid", 0) or 0),
        )

    async def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 100) -> list[UnifiedOHLCV]:
        ccxt_symbol = self._to_broker_symbol(symbol)
        ccxt_tf = timeframe  # CCXT uses "1m", "5m", "1h", "1d" — same as our standard

        ohlcv = await self._exchange.fetch_ohlcv(ccxt_symbol, ccxt_tf, limit=limit)

        return [
            UnifiedOHLCV(
                timestamp=bar[0],
                open=bar[1],
                high=bar[2],
                low=bar[3],
                close=bar[4],
                volume=bar[5],
                broker_id=self.broker_id,
            )
            for bar in ohlcv
        ]

    async def get_balance(self) -> list[UnifiedBalance]:
        balance = await self._exchange.fetch_balance()
        result = []

        for currency, data in balance.items():
            if isinstance(data, dict) and data.get("total", 0) and data["total"] > 0:
                result.append(UnifiedBalance(
                    currency=currency,
                    available=data.get("free", 0),
                    locked=data.get("used", 0),
                    total=data["total"],
                    broker_id=self.broker_id,
                ))

        return result

    async def get_positions(self) -> list[UnifiedPosition]:
        # For spot: positions are just balances
        # For futures/swaps: use fetch_positions
        positions = await self._exchange.fetch_positions()
        result = []

        for pos in positions:
            if abs(pos.get("contracts", 0)) > 0:
                result.append(UnifiedPosition(
                    position_id=pos.get("id", ""),
                    symbol=self._from_broker_symbol(pos["symbol"]),
                    side=OrderSide.BUY if pos["side"] == "long" else OrderSide.SELL,
                    quantity=abs(pos["contracts"]),
                    entry_price=pos.get("entryPrice", 0),
                    current_price=pos.get("markPrice", 0),
                    unrealized_pnl=pos.get("unrealizedPnl", 0),
                    realized_pnl=0,
                    margin_used=pos.get("initialMargin", 0),
                    broker_id=self.broker_id,
                    asset_class=AssetClass.CRYPTO,
                ))

        return result

    # ─── Streaming ────────────────────────────────────────────────────────────

    async def subscribe_ticker(self, symbol: str) -> AsyncIterator[UnifiedTicker]:
        """Stream real-time ticker via CCXT Pro WebSocket."""
        try:
            import ccxt.pro as ccxtpro
            exchange_pro = ccxtpro.binance({
                "apiKey": self._credentials.api_key,
                "secret": self._credentials.api_secret,
            })

            ccxt_symbol = self._to_broker_symbol(symbol)
            while True:
                ticker = await exchange_pro.watch_ticker(ccxt_symbol)
                yield UnifiedTicker(
                    symbol=symbol,
                    bid=ticker.get("bid", 0),
                    ask=ticker.get("ask", 0),
                    last=ticker.get("last", 0),
                    timestamp=ticker.get("timestamp", 0),
                    broker_id=self.broker_id,
                )
        finally:
            await exchange_pro.close()

    # ─── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _map_order_status(ccxt_status: str) -> OrderStatus:
        return {
            "open": OrderStatus.OPEN,
            "closed": OrderStatus.FILLED,
            "canceled": OrderStatus.CANCELLED,
            "expired": OrderStatus.EXPIRED,
        }.get(ccxt_status, OrderStatus.PENDING)

    def _to_broker_symbol(self, normalized: str) -> str:
        """Normalized "BTC/USD" → CCXT "BTC/USDT" (most exchanges use USDT pairs)."""
        # This mapping is exchange-specific and loaded from config
        mapping = self._credentials.additional.get("symbol_map", {})
        return mapping.get(normalized, normalized)

    def _from_broker_symbol(self, broker_symbol: str) -> str:
        mapping = self._credentials.additional.get("symbol_map_reverse", {})
        return mapping.get(broker_symbol, broker_symbol)
```

### 5.3 REST API Connector (OANDA, IG Markets)

```python
import aiohttp
import json
from typing import Optional

class RESTAPIConnector(BrokerConnector):
    """
    Generic REST API connector for brokers with HTTP APIs.

    Configured via an API specification that defines endpoints, auth method,
    and response formats. One connector class serves OANDA, IG Markets,
    and any future REST-based broker.

    The spec is loaded from a JSON/YAML config per broker.
    """

    def __init__(self, credentials: BrokerCredentials, api_spec: dict):
        super().__init__(credentials)
        self._spec = api_spec  # Loaded from config/registry
        self._session: Optional[aiohttp.ClientSession] = None

    async def connect(self) -> bool:
        if self._connection_status == ConnectionStatus.CONNECTED:
            return True

        self._connection_status = ConnectionStatus.CONNECTING

        headers = self._build_auth_headers()

        self._session = aiohttp.ClientSession(
            base_url=self._credentials.endpoint,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=30),
        )

        # Verify connection
        verify_endpoint = self._spec["endpoints"]["account"]["details"]
        async with self._session.get(verify_endpoint) as resp:
            if resp.status == 200:
                self._connection_status = ConnectionStatus.CONNECTED
                self._emit_event("connected", {"broker_id": self.broker_id})
                return True
            else:
                await self._session.close()
                self._session = None
                self._connection_status = ConnectionStatus.DISCONNECTED
                raise BrokerError(self.broker_id, f"Connection failed: HTTP {resp.status}")

    async def disconnect(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None
        self._connection_status = ConnectionStatus.DISCONNECTED

    async def health_check(self) -> ConnectionStatus:
        try:
            endpoint = self._spec["endpoints"]["account"]["details"]
            async with self._session.get(endpoint) as resp:
                self._connection_status = (
                    ConnectionStatus.CONNECTED if resp.status == 200
                    else ConnectionStatus.DEGRADED
                )
        except Exception:
            self._connection_status = ConnectionStatus.DISCONNECTED
        return self._connection_status

    async def place_order(self, order: UnifiedOrder) -> OrderConfirmation:
        endpoint = self._spec["endpoints"]["orders"]["create"]
        body = self._format_order_body(order)

        async with self._session.post(endpoint, json=body) as resp:
            data = await resp.json()

            if resp.status not in (200, 201):
                raise BrokerError(
                    self.broker_id,
                    f"Order failed: {data.get('errorMessage', resp.status)}",
                )

            return self._parse_order_response(order, data)

    def _build_auth_headers(self) -> dict:
        auth_type = self._spec["auth"]["type"]
        if auth_type == "bearer":
            return {"Authorization": f"Bearer {self._credentials.api_key}"}
        elif auth_type == "oanda":
            return {"Authorization": f"Bearer {self._credentials.api_key}"}
        elif auth_type == "ig":
            return {
                "X-API-KEY": self._credentials.api_key,
                "CST": self._credentials.additional.get("cst", ""),
                "X-SECURITY-TOKEN": self._credentials.additional.get("security_token", ""),
            }
        elif auth_type == "hmac":
            # For HMAC-based APIs (Kraken, etc.)
            return self._build_hmac_headers()
        return {}

    def _format_order_body(self, order: UnifiedOrder) -> dict:
        """Translate UnifiedOrder to broker-specific request body using spec."""
        template = self._spec["order_format"]
        # Apply template substitution from order fields
        return {
            key: self._resolve_template(value, order)
            for key, value in template.items()
        }

    def _parse_order_response(self, order: UnifiedOrder, response: dict) -> OrderConfirmation:
        """Parse broker response into OrderConfirmation using spec mapping."""
        mapping = self._spec["response_mapping"]
        return OrderConfirmation(
            order_id=order.order_id,
            broker_order_id=self._extract(response, mapping["order_id"]),
            broker_id=self.broker_id,
            status=OrderStatus.OPEN,
            fill_price=self._extract(response, mapping.get("fill_price")),
            fill_quantity=self._extract(response, mapping.get("fill_quantity")),
            raw_response=response,
        )

    @staticmethod
    def _extract(data: dict, path: Optional[str]) -> Any:
        """Extract value from nested dict using dot notation path."""
        if not path:
            return None
        keys = path.split(".")
        for key in keys:
            if isinstance(data, dict):
                data = data.get(key)
            else:
                return None
        return data
```

### 5.4 FIX Protocol Connector (Institutional)

```python
class FIXConnector(BrokerConnector):
    """
    FIX 4.4 / 5.0 protocol connector for institutional brokers.

    Uses a FIX engine (quickfix or simplesonfix) for session management.
    This is the lowest-latency, highest-throughput connector.

    Use cases: Prime brokers, dark pools, institutional venues.
    """

    def __init__(self, credentials: BrokerCredentials):
        super().__init__(credentials)
        self._fix_session = None
        self._gateway = credentials.additional.get("gateway", "quickfix")

    async def connect(self) -> bool:
        # FIX connection setup
        # Requires FIX engine library installed
        # Session parameters: SenderCompID, TargetCompID, host, port, heartbeat
        pass

    async def place_order(self, order: UnifiedOrder) -> OrderConfirmation:
        # Build FIX NewOrderSingle (MsgType=D)
        # Fields: ClOrdID, Symbol, Side, OrdType, OrderQty, Price, TimeInForce
        # Send via FIX session
        pass

    # ... other methods
```

### 5.5 Interactive Brokers Connector

```python
from ib_insync import IB, Forex, Stock, Future, Crypto, MarketOrder, LimitOrder

class IBKRConnector(BrokerConnector):
    """
    Interactive Brokers connector using ib_insync library.

    Supports: Forex, stocks, options, futures, crypto, bonds, CFDs.
    Requires: TWS or IB Gateway running (Java application).
    """

    def __init__(self, credentials: BrokerCredentials):
        super().__init__(credentials)
        self._ib = IB()
        self._host = credentials.endpoint or "127.0.0.1"
        self._port = int(credentials.additional.get("port", 4001))
        self._client_id = int(credentials.additional.get("client_id", 1))

    async def connect(self) -> bool:
        await self._ib.connectAsync(self._host, self._port, clientId=self._client_id)
        self._connection_status = ConnectionStatus.CONNECTED
        return True

    async def disconnect(self) -> None:
        self._ib.disconnect()
        self._connection_status = ConnectionStatus.DISCONNECTED

    async def place_order(self, order: UnifiedOrder) -> OrderConfirmation:
        contract = self._resolve_contract(order.symbol, order.asset_class)

        if order.order_type == OrderType.MARKET:
            ib_order = MarketOrder(order.side.value.upper(), order.quantity)
        elif order.order_type == OrderType.LIMIT:
            ib_order = LimitOrder(order.side.value.upper(), order.quantity, order.price)

        if order.stop_loss:
            ib_order.auxPrice = order.stop_loss

        trade = self._ib.placeOrder(contract, ib_order)
        await asyncio.sleep(0.5)  # Wait for ack

        return OrderConfirmation(
            order_id=order.order_id,
            broker_order_id=str(trade.order.orderId),
            broker_id=self.broker_id,
            status=self._map_status(trade.orderStatus.status),
            fill_price=trade.orderStatus.avgFillPrice,
            fill_quantity=trade.orderStatus.filled,
        )

    def _resolve_contract(self, symbol: str, asset_class: AssetClass):
        """Convert normalized symbol to IB Contract object."""
        base, quote = symbol.split("/")
        if asset_class == AssetClass.FOREX:
            return Forex(f"{base}{quote}")
        elif asset_class == AssetClass.CRYPTO:
            return Crypto(base, "PAXOS", quote)
        elif asset_class == AssetClass.EQUITIES:
            return Stock(base, "SMART", quote)
        elif asset_class == AssetClass.FUTURES:
            return Future(base, self._credentials.additional.get("expiry", ""), "CME")
```

---

## 6. Symbol Normalization Layer

### 6.1 The Problem

Every broker uses different symbol formats:

| Normalized | MT5 | CCXT (Binance) | OANDA | IBKR | IG Markets |
|------------|-----|----------------|-------|------|------------|
| `EUR/USD` | `EURUSD` | `EUR/USDT` | `EUR_USD` | `EUR.USD` | `CS.D.EURUSD.TODAY.IP` |
| `BTC/USD` | N/A | `BTC/USDT` | `BTC_USD` | `BTC.USD` | `CS.D.BITCOIN.TODAY.IP` |
| `XAU/USD` | `XAUUSD` | N/A | `XAU_USD` | XAUUSD | `CS.D.GOLD.TODAY.IP` |
| `SPX500` | `SP500` | N/A | `SPX500_USD` | `ES` (CME) | `IX.D.SPTRD.DAILY.IP` |

### 6.2 The Solution

A `SymbolRegistry` that maintains bidirectional mappings between normalized symbols and each broker's native format.

```python
class SymbolRegistry:
    """
    Central registry for symbol normalization.

    Maps between Alpha Stack's normalized format and each broker's native format.
    Loaded from a config file (YAML/JSON) and extensible at runtime.
    """

    def __init__(self):
        self._to_broker: dict[str, dict[str, str]] = {}  # normalized → {broker_type: native}
        self._from_broker: dict[str, dict[str, str]] = {}  # broker_type → {native: normalized}

    def load_from_config(self, config: dict) -> None:
        """
        Load symbol mappings from config.

        Config format:
        {
            "EUR/USD": {
                "mt5": "EURUSD",
                "ccxt_binance": null,
                "ccxt_bybit": null,
                "oanda": "EUR_USD",
                "ibkr": "EUR.USD",
                "ig": "CS.D.EURUSD.TODAY.IP"
            },
            "BTC/USD": {
                "mt5": null,
                "ccxt_binance": "BTC/USDT",
                "ccxt_bybit": "BTC/USDT",
                "oanda": "BTC_USD",
                "ibkr": "BTC.USD",
                "ig": "CS.D.BITCOIN.TODAY.IP"
            }
        }
        """
        for normalized, mappings in config.items():
            self._to_broker[normalized] = mappings
            for broker_type, native in mappings.items():
                if native:
                    if broker_type not in self._from_broker:
                        self._from_broker[broker_type] = {}
                    self._from_broker[broker_type][native] = normalized

    def to_broker(self, normalized: str, broker_type: str) -> Optional[str]:
        """Convert normalized symbol to broker-specific format. Returns None if not supported."""
        return self._to_broker.get(normalized, {}).get(broker_type)

    def from_broker(self, native: str, broker_type: str) -> Optional[str]:
        """Convert broker-specific symbol to normalized format."""
        return self._from_broker.get(broker_type, {}).get(native)

    def get_supported_brokers(self, normalized: str) -> list[str]:
        """Which broker types can trade this symbol?"""
        mappings = self._to_broker.get(normalized, {})
        return [bt for bt, native in mappings.items() if native is not None]

    def is_tradeable(self, normalized: str, broker_type: str) -> bool:
        """Can this broker trade this symbol?"""
        return self.to_broker(normalized, broker_type) is not None
```

### 6.3 Timeframe Mapping

```python
TIMEFRAME_MAP = {
    "1m":  {"mt5": "TIMEFRAME_M1",  "ccxt": "1m",  "oanda": "M1",   "ibkr": "1 min",  "ig": "MINUTE"},
    "5m":  {"mt5": "TIMEFRAME_M5",  "ccxt": "5m",  "oanda": "M5",   "ibkr": "5 mins", "ig": "MINUTE_5"},
    "15m": {"mt5": "TIMEFRAME_M15", "ccxt": "15m", "oanda": "M15",  "ibkr": "15 mins","ig": "MINUTE_15"},
    "1h":  {"mt5": "TIMEFRAME_H1",  "ccxt": "1h",  "oanda": "H1",   "ibkr": "1 hour", "ig": "HOUR"},
    "4h":  {"mt5": "TIMEFRAME_H4",  "ccxt": "4h",  "oanda": "H4",   "ibkr": "4 hours","ig": "HOUR_4"},
    "1d":  {"mt5": "TIMEFRAME_D1",  "ccxt": "1d",  "oanda": "D",    "ibkr": "1 day",  "ig": "DAY"},
    "1w":  {"mt5": "TIMEFRAME_W1",  "ccxt": "1w",  "oanda": "W",    "ibkr": "1 week", "ig": "WEEK"},
}
```

---

## 7. Unified Order Manager

The Order Manager is the single source of truth for all orders across all brokers.

```python
class UnifiedOrderManager:
    """
    Manages the lifecycle of all orders across all brokers.

    Responsibilities:
    - Assign internal order IDs
    - Validate orders before submission
    - Track order state transitions
    - Persist order history to PostgreSQL
    - Emit events on state changes
    """

    def __init__(
        self,
        registry: BrokerConnectorRegistry,
        router: SmartOrderRouter,
        risk_engine: CrossBrokerRiskEngine,
        db: Database,
        event_bus: EventBus,
    ):
        self._registry = registry
        self._router = router
        self._risk = risk_engine
        self._db = db
        self._events = event_bus
        self._active_orders: dict[str, UnifiedOrder] = {}

    async def submit_order(self, order: UnifiedOrder) -> OrderConfirmation:
        """
        Full order submission pipeline:
        1. Validate order structure
        2. Pre-trade risk check
        3. Route to best broker
        4. Submit to broker connector
        5. Track and persist
        """

        # 1. Validate
        self._validate_order(order)

        # 2. Risk check
        approved, reason = await self._risk.pre_trade_check(order)
        if not approved:
            order.metadata["rejection_reason"] = reason
            await self._db.save_order(order, OrderStatus.REJECTED)
            self._events.emit("order_rejected", {"order": order, "reason": reason})
            raise RiskError(f"Pre-trade check failed: {reason}")

        # 3. Route
        if not order.broker_id:
            order.broker_id = await self._router.route_order(order)

        # 4. Persist as PENDING
        order.status = OrderStatus.PENDING
        await self._db.save_order(order, OrderStatus.PENDING)
        self._active_orders[order.order_id] = order

        # 5. Submit
        try:
            connector = self._registry.get_connector(order.broker_id)
            confirmation = await connector.place_order(order)

            # 6. Update state
            await self._db.update_order_status(
                order.order_id,
                confirmation.status,
                confirmation.broker_order_id,
                confirmation.fill_price,
            )

            self._events.emit("order_submitted", {
                "order": order,
                "confirmation": confirmation,
            })

            return confirmation

        except BrokerError as e:
            # Handle failure — try failover if recoverable
            if e.recoverable:
                return await self._failover_submit(order)
            else:
                await self._db.update_order_status(order.order_id, OrderStatus.REJECTED)
                raise

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order by internal ID."""
        order = await self._db.get_order(order_id)
        if not order:
            raise ValueError(f"Order not found: {order_id}")

        connector = self._registry.get_connector(order.broker_id)
        success = await connector.cancel_order(order.broker_order_id)

        if success:
            await self._db.update_order_status(order_id, OrderStatus.CANCELLED)
            self._events.emit("order_cancelled", {"order_id": order_id})

        return success

    async def modify_order(
        self,
        order_id: str,
        price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> bool:
        """Modify an existing order."""
        order = await self._db.get_order(order_id)
        if not order:
            raise ValueError(f"Order not found: {order_id}")

        connector = self._registry.get_connector(order.broker_id)
        return await connector.modify_order(order.broker_order_id, price, stop_loss, take_profit)

    async def _failover_submit(self, order: UnifiedOrder) -> OrderConfirmation:
        """Try alternative brokers after primary fails."""
        alternatives = await self._router.get_alternatives(order, exclude=[order.broker_id])

        for broker_id in alternatives:
            try:
                order.broker_id = broker_id
                connector = self._registry.get_connector(broker_id)
                confirmation = await connector.place_order(order)

                self._events.emit("order_failover", {
                    "order": order,
                    "failed_broker": order.broker_id,
                    "routed_to": broker_id,
                })

                return confirmation

            except BrokerError:
                continue

        raise RuntimeError(f"All brokers failed for order {order.order_id}")

    def _validate_order(self, order: UnifiedOrder) -> None:
        """Structural validation."""
        if not order.symbol:
            raise ValueError("Order must have a symbol")
        if order.quantity <= 0:
            raise ValueError("Quantity must be positive")
        if order.order_type in (OrderType.LIMIT, OrderType.STOP_LIMIT) and not order.price:
            raise ValueError(f"{order.order_type.value} order requires a price")
```

---

## 8. Portfolio Aggregator

```python
class PortfolioAggregator:
    """
    Aggregates positions, balances, and P&L across all connected brokers.

    Provides a unified view regardless of how many brokers are connected
    or what asset classes they support.
    """

    def __init__(self, registry: BrokerConnectorRegistry, symbol_registry: SymbolRegistry):
        self._registry = registry
        self._symbols = symbol_registry
        self._price_cache: dict[str, float] = {}  # symbol → USD price

    async def get_aggregated_balance(self, base_currency: str = "USD") -> dict:
        """
        Total balance across all brokers, converted to base currency.

        Returns:
        {
            "total": 28450.00,
            "available": 18719.50,
            "by_broker": {
                "fxpesa_mt5": {"total": 10000, "available": 8000, "currency": "USD"},
                "binance": {"total": 13450, "available": 7719.50, "currency": "USDT"},
                "oanda": {"total": 5000, "available": 3000, "currency": "USD"},
            },
            "by_asset_class": {
                "forex": 15000,
                "crypto": 13450,
            }
        }
        """
        result = {
            "total": 0.0,
            "available": 0.0,
            "by_broker": {},
            "by_asset_class": {},
        }

        tasks = []
        for broker_id, connector in self._registry.get_all_connectors().items():
            tasks.append(self._fetch_broker_balance(broker_id, connector, base_currency))

        broker_balances = await asyncio.gather(*tasks, return_exceptions=True)

        for broker_balance in broker_balances:
            if isinstance(broker_balance, Exception):
                continue  # Skip failed brokers
            result["total"] += broker_balance["total_converted"]
            result["available"] += broker_balance["available_converted"]
            result["by_broker"][broker_balance["broker_id"]] = broker_balance
            asset_class = broker_balance.get("asset_class", "unknown")
            result["by_asset_class"][asset_class] = (
                result["by_asset_class"].get(asset_class, 0) + broker_balance["total_converted"]
            )

        return result

    async def get_aggregated_positions(self) -> list[UnifiedPosition]:
        """All open positions across all brokers, sorted by unrealized P&L."""
        tasks = []
        for broker_id, connector in self._registry.get_all_connectors().items():
            tasks.append(connector.get_positions())

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_positions = []
        for result in results:
            if not isinstance(result, Exception):
                all_positions.extend(result)

        all_positions.sort(key=lambda p: p.unrealized_pnl, reverse=True)
        return all_positions

    async def get_unified_pnl(self, base_currency: str = "USD") -> dict:
        """
        Total P&L across all brokers.

        Returns:
        {
            "realized": 500.00,
            "unrealized": 1234.56,
            "total": 1734.56,
            "by_broker": {...},
            "by_asset_class": {...},
        }
        """
        positions = await self.get_aggregated_positions()

        pnl = {
            "realized": 0.0,
            "unrealized": 0.0,
            "by_broker": {},
            "by_asset_class": {},
        }

        for pos in positions:
            # Convert P&L to base currency if needed
            unrealized = pos.unrealized_pnl  # TODO: currency conversion
            pnl["unrealized"] += unrealized
            pnl["realized"] += pos.realized_pnl

            # By broker
            if pos.broker_id not in pnl["by_broker"]:
                pnl["by_broker"][pos.broker_id] = {"realized": 0, "unrealized": 0}
            pnl["by_broker"][pos.broker_id]["unrealized"] += unrealized

            # By asset class
            ac = pos.asset_class.value if pos.asset_class else "unknown"
            if ac not in pnl["by_asset_class"]:
                pnl["by_asset_class"][ac] = {"realized": 0, "unrealized": 0}
            pnl["by_asset_class"][ac]["unrealized"] += unrealized

        pnl["total"] = pnl["realized"] + pnl["unrealized"]
        return pnl

    async def get_margin_utilization(self) -> dict:
        """
        Margin usage across all brokers.

        Returns:
        {
            "total_margin_used": 9700,
            "total_equity": 28450,
            "utilization_pct": 34.1,
            "by_broker": {
                "fxpesa_mt5": {"margin": 2000, "equity": 10000, "pct": 20.0},
                "binance": {"margin": 7700, "equity": 13450, "pct": 57.2},
            }
        }
        """
        # Implementation: fetch balance from each broker, compute margin ratios
        pass
```

---

## 9. Smart Order Router

```python
class SmartOrderRouter:
    """
    Routes orders to the best broker for execution.

    Scoring factors:
    - Spread (30%): Lower spread = lower cost
    - Liquidity (25%): More depth = less slippage
    - Latency (20%): Faster fill = less price movement
    - Fees (15%): Lower commission = more profit
    - Reliability (10%): Higher uptime = fewer missed trades

    Also handles:
    - Failover routing when primary broker is down
    - Arbitrage detection across brokers
    - Order splitting for large positions
    """

    WEIGHTS = {
        "spread": 0.30,
        "liquidity": 0.25,
        "latency": 0.20,
        "fees": 0.15,
        "reliability": 0.10,
    }

    def __init__(
        self,
        registry: BrokerConnectorRegistry,
        symbol_registry: SymbolRegistry,
        circuit_breaker: CircuitBreaker,
    ):
        self._registry = registry
        self._symbols = symbol_registry
        self._breaker = circuit_breaker
        self._latency_cache: dict[str, float] = {}  # broker_id → avg latency ms
        self._reliability_scores: dict[str, float] = {}  # broker_id → 0.0-1.0

    async def route_order(self, order: UnifiedOrder) -> str:
        """Select the best broker for this order. Returns broker_id."""
        candidates = await self._get_capable_brokers(order)

        if not candidates:
            raise RoutingError(f"No broker available for {order.symbol}")

        if len(candidates) == 1:
            return candidates[0]

        # Score each candidate
        scores = {}
        for broker_id in candidates:
            score = await self._score_broker(broker_id, order)
            scores[broker_id] = score

        best = max(scores, key=scores.get)
        return best

    async def get_alternatives(
        self, order: UnifiedOrder, exclude: list[str] = []
    ) -> list[str]:
        """Get alternative brokers ranked by score, excluding specified ones."""
        candidates = await self._get_capable_brokers(order)
        candidates = [c for c in candidates if c not in exclude]

        scored = []
        for broker_id in candidates:
            score = await self._score_broker(broker_id, order)
            scored.append((broker_id, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [broker_id for broker_id, _ in scored]

    async def detect_arbitrage(self, symbol: str) -> Optional[dict]:
        """
        Check for cross-broker arbitrage opportunities.

        Returns opportunity dict if buy_price on broker A < sell_price on broker B,
        after accounting for fees on both sides.
        """
        prices = {}

        tasks = []
        for broker_id, connector in self._registry.get_all_connectors().items():
            if self._breaker.is_available(broker_id):
                tasks.append(self._fetch_quote(broker_id, connector, symbol))

        quotes = await asyncio.gather(*tasks, return_exceptions=True)

        for quote in quotes:
            if not isinstance(quote, Exception):
                prices[quote["broker_id"]] = quote

        # Find arbitrage: buy cheap, sell expensive
        best_buy = None
        best_sell = None

        for broker_id, quote in prices.items():
            if best_buy is None or quote["ask"] < best_buy["ask"]:
                best_buy = {"broker_id": broker_id, "ask": quote["ask"]}
            if best_sell is None or quote["bid"] > best_sell["bid"]:
                best_sell = {"broker_id": broker_id, "bid": quote["bid"]}

        if best_buy and best_sell and best_buy["broker_id"] != best_sell["broker_id"]:
            gross_profit = best_sell["bid"] - best_buy["ask"]
            if gross_profit > 0:
                # Estimate total fees (conservative)
                fee_pct = 0.001  # 0.1% per side
                total_fees = (best_buy["ask"] + best_sell["bid"]) * fee_pct
                net_profit = gross_profit - total_fees

                if net_profit > 0:
                    return {
                        "symbol": symbol,
                        "buy_at": best_buy["broker_id"],
                        "buy_price": best_buy["ask"],
                        "sell_at": best_sell["broker_id"],
                        "sell_price": best_sell["bid"],
                        "gross_profit_per_unit": gross_profit,
                        "estimated_fees": total_fees,
                        "net_profit_per_unit": net_profit,
                    }

        return None

    async def _get_capable_brokers(self, order: UnifiedOrder) -> list[str]:
        """Find all connected brokers that can handle this order."""
        capable = []
        for broker_id, connector in self._registry.get_all_connectors().items():
            if not self._breaker.is_available(broker_id):
                continue
            if not connector.connection_status == ConnectionStatus.CONNECTED:
                continue
            if not await connector.supports_symbol(order.symbol):
                continue
            capable.append(broker_id)
        return capable

    async def _score_broker(self, broker_id: str, order: UnifiedOrder) -> float:
        """Score a broker for this specific order (higher = better)."""
        connector = self._registry.get_connector(broker_id)

        # Fetch current spread
        try:
            ticker = await connector.get_ticker(order.symbol)
            spread_score = max(0, 1.0 - (ticker.spread / 0.0010))  # Normalize: 0 spread = 1.0
        except Exception:
            spread_score = 0.5  # Unknown = neutral

        # Latency score (from cache)
        avg_latency = self._latency_cache.get(broker_id, 100)
        latency_score = max(0, 1.0 - (avg_latency / 1000))  # 0ms = 1.0, 1000ms = 0.0

        # Reliability score
        reliability_score = self._reliability_scores.get(broker_id, 0.9)

        # Fee score (from capabilities)
        fee_score = 0.8  # Default; override from connector capabilities

        # Liquidity score (simplified)
        liquidity_score = 0.7  # Default; would need orderbook depth analysis

        return (
            spread_score * self.WEIGHTS["spread"]
            + liquidity_score * self.WEIGHTS["liquidity"]
            + latency_score * self.WEIGHTS["latency"]
            + fee_score * self.WEIGHTS["fees"]
            + reliability_score * self.WEIGHTS["reliability"]
        )

    async def _fetch_quote(self, broker_id: str, connector, symbol: str) -> dict:
        """Fetch a quote for arbitrage detection."""
        ticker = await connector.get_ticker(symbol)
        return {
            "broker_id": broker_id,
            "bid": ticker.bid,
            "ask": ticker.ask,
            "spread": ticker.spread,
        }
```

---

## 10. Execution Engine

The Execution Engine decides *how* to execute orders based on capital level and order size. At $7, it's simple. At $50K+, it's institutional-grade.

```python
class ExecutionEngine:
    """
    Selects and applies execution algorithms based on order size and capital.

    Evolution path:
    - $7-$50:      Simple (spread filter + limit orders)
    - $50-$500:    + Partial fill handling, session filtering
    - $500-$5K:    + Basic TWAP, trailing stops
    - $5K-$50K:    + VWAP benchmarking, slippage analytics
    - $50K+:       + Full algo suite, multi-venue routing
    """

    def __init__(
        self,
        order_manager: UnifiedOrderManager,
        router: SmartOrderRouter,
        capital_tracker: CapitalTracker,
    ):
        self._order_manager = order_manager
        self._router = router
        self._capital = capital_tracker

    async def execute(self, signal: dict) -> OrderConfirmation:
        """
        Execute a trading signal with appropriate execution logic.

        signal = {
            "symbol": "EUR/USD",
            "side": "buy",
            "strategy": "momentum_v1",
            "confidence": 0.85,
            "entry_price": 1.0850,
            "stop_loss": 1.0800,
            "take_profit": 1.0920,
        }
        """
        capital = self._capital.get_total_capital()
        order_size = self._calculate_position_size(signal, capital)

        # Build order
        order = UnifiedOrder(
            order_id=str(uuid4()),
            symbol=signal["symbol"],
            side=OrderSide(signal["side"]),
            order_type=self._select_order_type(signal, capital),
            quantity=order_size,
            price=signal.get("entry_price"),
            stop_loss=signal.get("stop_loss"),
            take_profit=signal.get("take_profit"),
            metadata={"strategy": signal["strategy"], "confidence": signal["confidence"]},
        )

        # Apply execution filters based on capital level
        if capital < 50:
            return await self._execute_simple(order, signal)
        elif capital < 500:
            return await self._execute_filtered(order, signal)
        elif capital < 5000:
            return await self._execute_twap(order, signal)
        else:
            return await self._execute_institutional(order, signal)

    async def _execute_simple(self, order: UnifiedOrder, signal: dict) -> OrderConfirmation:
        """
        Simple execution for small capital ($7-$50).
        Rules: spread check, session filter, limit orders preferred.
        """
        # 1. Spread filter: reject if spread > 2x 1-hour average
        connector = self._registry.get_connector(order.broker_id)
        ticker = await connector.get_ticker(order.symbol)
        avg_spread = await self._get_average_spread(order.symbol, period="1h")

        if ticker.spread > avg_spread * 2:
            raise ExecutionRejected(f"Spread too wide: {ticker.spread:.5f} > 2x avg {avg_spread:.5f}")

        # 2. Session filter: only trade during liquid sessions
        if not self._is_liquid_session():
            raise ExecutionRejected("Outside liquid trading hours (London-NY overlap)")

        # 3. News filter
        if self._is_near_news_event():
            raise ExecutionRejected("Too close to high-impact news event")

        # 4. Submit as limit order if possible
        if order.order_type == OrderType.MARKET and order.price:
            order.order_type = OrderType.LIMIT  # Try limit first

        return await self._order_manager.submit_order(order)

    async def _execute_filtered(self, order: UnifiedOrder, signal: dict) -> OrderConfirmation:
        """Filtered execution for medium capital ($50-$500). Adds partial fill handling."""
        # Simple filters + position management
        confirmation = await self._execute_simple(order, signal)

        if confirmation.status == OrderStatus.PARTIALLY_FILLED:
            # Handle partial fill: wait for remainder or adjust
            await self._handle_partial_fill(order, confirmation)

        return confirmation

    async def _execute_twap(self, order: UnifiedOrder, signal: dict) -> OrderConfirmation:
        """
        TWAP execution for larger orders ($500-$5000).
        Splits order into time-weighted slices to minimize market impact.
        """
        if order.quantity < 0.1:  # Below TWAP threshold
            return await self._execute_filtered(order, signal)

        # Split into 3-5 slices over 5-15 minutes
        num_slices = min(5, max(3, int(order.quantity / 0.02)))
        slice_qty = order.quantity / num_slices
        interval_seconds = 300  # 5 minutes between slices

        fills = []
        remaining = order.quantity

        for i in range(num_slices):
            slice_order = UnifiedOrder(
                order_id=f"{order.order_id}_twap_{i}",
                symbol=order.symbol,
                side=order.side,
                order_type=OrderType.LIMIT,
                quantity=min(slice_qty, remaining),
                price=order.price,  # Adjust price each slice based on market
                stop_loss=order.stop_loss,
                take_profit=order.take_profit,
                broker_id=order.broker_id,
                metadata={**order.metadata, "twap_slice": i, "twap_total": num_slices},
            )

            try:
                fill = await self._order_manager.submit_order(slice_order)
                fills.append(fill)
                remaining -= fill.fill_quantity or 0

                if remaining <= 0:
                    break

                if i < num_slices - 1:
                    await asyncio.sleep(interval_seconds)

            except BrokerError as e:
                if not e.recoverable:
                    raise
                continue  # Skip failed slice, try next

        # Aggregate fills
        total_filled = sum(f.fill_quantity or 0 for f in fills)
        avg_price = sum((f.fill_price or 0) * (f.fill_quantity or 0) for f in fills) / total_filled if total_filled else 0

        return OrderConfirmation(
            order_id=order.order_id,
            broker_order_id=fills[0].broker_order_id if fills else "",
            broker_id=order.broker_id or "",
            status=OrderStatus.FILLED if total_filled >= order.quantity else OrderStatus.PARTIALLY_FILLED,
            fill_price=avg_price,
            fill_quantity=total_filled,
        )

    async def _execute_institutional(self, order: UnifiedOrder, signal: dict) -> OrderConfirmation:
        """
        Institutional execution for large capital ($50K+).
        Full algo suite: TWAP + VWAP benchmarking + multi-venue routing.
        """
        # Delegate to TWAP for now; VWAP/SOR added when capital justifies
        return await self._execute_twap(order, signal)

    def _select_order_type(self, signal: dict, capital: float) -> OrderType:
        """Choose order type based on signal and capital."""
        if capital < 50:
            return OrderType.LIMIT  # Always limit at small capital
        return OrderType(signal.get("order_type", "market"))

    def _calculate_position_size(self, signal: dict, capital: float) -> float:
        """Kelly criterion or fixed fractional position sizing."""
        risk_per_trade = capital * 0.02  # 2% risk per trade
        sl_distance = abs(signal.get("entry_price", 0) - signal.get("stop_loss", 0))

        if sl_distance <= 0:
            return 0.01  # Minimum lot size

        # For forex: 1 pip = $0.10 per 0.01 lot on major pairs
        pip_value = 0.10  # Simplified; should be per-symbol
        sl_pips = sl_distance * 10000  # Convert to pips

        position_size = risk_per_trade / (sl_pips * pip_value)
        return max(0.01, round(position_size, 2))  # Min 0.01 lots

    def _is_liquid_session(self) -> bool:
        """Check if current time is within London-NY overlap (13:00-17:00 UTC)."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        return 13 <= now.hour < 17

    def _is_near_news_event(self) -> bool:
        """Check if a high-impact news event is within 30 minutes."""
        # Would integrate with economic calendar API
        return False

    async def _get_average_spread(self, symbol: str, period: str = "1h") -> float:
        """Get average spread over the specified period from tick history."""
        # Would query historical tick data from TimescaleDB
        return 0.0008  # Default: 0.8 pips for EUR/USD
```

---

## 11. Connection Lifecycle & Resilience

### 11.1 Connection Manager

```python
class ConnectionManager:
    """
    Manages the lifecycle of all broker connections.

    Responsibilities:
    - Establish and maintain connections
    - Health monitoring (periodic probes)
    - Auto-reconnection with exponential backoff
    - Circuit breaker integration
    - Connection event logging
    """

    def __init__(self, registry: BrokerConnectorRegistry, event_bus: EventBus):
        self._registry = registry
        self._events = event_bus
        self._health_task: Optional[asyncio.Task] = None
        self._reconnect_tasks: dict[str, asyncio.Task] = {}

    async def start(self, credentials: list[BrokerCredentials]) -> None:
        """Connect to all configured brokers and start health monitoring."""
        for creds in credentials:
            await self._connect_broker(creds)

        self._health_task = asyncio.create_task(self._health_loop())

    async def stop(self) -> None:
        """Disconnect all brokers and stop monitoring."""
        if self._health_task:
            self._health_task.cancel()

        for task in self._reconnect_tasks.values():
            task.cancel()

        for broker_id, connector in self._registry.get_all_connectors().items():
            await connector.disconnect()

    async def _connect_broker(self, credentials: BrokerCredentials) -> None:
        """Connect a single broker with retry."""
        connector = self._registry.create_connector(credentials)

        for attempt in range(3):
            try:
                await connector.connect()
                self._registry.register(credentials.broker_id, connector)
                self._events.emit("broker_connected", {"broker_id": credentials.broker_id})
                return
            except Exception as e:
                wait = min(2 ** attempt, 30)
                await asyncio.sleep(wait)

        self._events.emit("broker_connection_failed", {
            "broker_id": credentials.broker_id,
            "error": str(e),
        })

    async def _health_loop(self) -> None:
        """Periodic health check for all connections."""
        while True:
            await asyncio.sleep(30)  # Check every 30 seconds

            for broker_id, connector in self._registry.get_all_connectors().items():
                try:
                    status = await connector.health_check()

                    if status == ConnectionStatus.DISCONNECTED:
                        if broker_id not in self._reconnect_tasks:
                            self._reconnect_tasks[broker_id] = asyncio.create_task(
                                self._reconnect(broker_id)
                            )

                except Exception as e:
                    self._events.emit("health_check_error", {
                        "broker_id": broker_id,
                        "error": str(e),
                    })

    async def _reconnect(self, broker_id: str) -> None:
        """Reconnect with exponential backoff."""
        connector = self._registry.get_connector(broker_id)
        credentials = self._registry.get_credentials(broker_id)

        for attempt in range(10):
            try:
                wait = min(2 ** attempt, 300)  # Max 5 minutes
                await asyncio.sleep(wait)

                await connector.disconnect()
                await connector.connect()

                self._events.emit("broker_reconnected", {"broker_id": broker_id})
                return

            except Exception as e:
                self._events.emit("reconnect_failed", {
                    "broker_id": broker_id,
                    "attempt": attempt + 1,
                    "error": str(e),
                })

        self._events.emit("broker_permanently_disconnected", {"broker_id": broker_id})
        del self._reconnect_tasks[broker_id]
```

### 11.2 Circuit Breaker

```python
class CircuitBreaker:
    """
    Prevents cascading failures from a single broker.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Broker is failing, requests are blocked
    - HALF_OPEN: Testing if broker has recovered

    Transitions:
    - CLOSED → OPEN: After N failures in M seconds
    - OPEN → HALF_OPEN: After recovery timeout
    - HALF_OPEN → CLOSED: On successful request
    - HALF_OPEN → OPEN: On failure
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        failure_window: int = 60,      # seconds
        recovery_timeout: int = 60,    # seconds
    ):
        self._threshold = failure_threshold
        self._window = failure_window
        self._recovery = recovery_timeout

        self._failures: dict[str, list[float]] = {}  # broker_id → [timestamps]
        self._state: dict[str, str] = {}             # broker_id → CLOSED/OPEN/HALF_OPEN
        self._opened_at: dict[str, float] = {}       # broker_id → timestamp when opened

    def record_success(self, broker_id: str) -> None:
        """Record a successful operation."""
        if self._state.get(broker_id) == "HALF_OPEN":
            self._state[broker_id] = "CLOSED"
            self._failures[broker_id] = []

    def record_failure(self, broker_id: str) -> None:
        """Record a failed operation."""
        now = time.time()

        if broker_id not in self._failures:
            self._failures[broker_id] = []

        # Add failure timestamp, prune old ones
        self._failures[broker_id].append(now)
        self._failures[broker_id] = [
            t for t in self._failures[broker_id] if now - t < self._window
        ]

        # Check if threshold exceeded
        if len(self._failures[broker_id]) >= self._threshold:
            self._state[broker_id] = "OPEN"
            self._opened_at[broker_id] = now

    def is_available(self, broker_id: str) -> bool:
        """Check if the broker is available for requests."""
        state = self._state.get(broker_id, "CLOSED")

        if state == "CLOSED":
            return True

        if state == "OPEN":
            # Check if recovery timeout has passed
            if time.time() - self._opened_at.get(broker_id, 0) > self._recovery:
                self._state[broker_id] = "HALF_OPEN"
                return True  # Allow one test request
            return False

        if state == "HALF_OPEN":
            return True  # Allow test requests

        return False
```

---

## 12. Credential Vault & Security

```python
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
import base64
import os

class BrokerCredentialVault:
    """
    Encrypted storage for broker credentials.

    Security model:
    - Each broker's credentials encrypted with a separate derived key
    - Master key derived from user's master password (PBKDF2, 600K iterations)
    - Credentials NEVER stored in plaintext
    - Credentials NEVER sent to Alpha Stack servers
    - Credentials only decrypted in memory when needed
    """

    def __init__(self, master_password: str, salt: bytes = None):
        self._salt = salt or os.urandom(16)
        self._master_key = self._derive_key(master_password)
        self._store: dict[str, bytes] = {}  # broker_id → encrypted data

    def _derive_key(self, password: str) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self._salt,
            iterations=600_000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))

    def store(self, broker_id: str, credentials: BrokerCredentials) -> None:
        """Encrypt and store credentials for a broker."""
        # Generate broker-specific key (isolation)
        broker_salt = os.urandom(16)
        broker_key = self._derive_broker_key(broker_id, broker_salt)

        # Encrypt
        fernet = Fernet(broker_key)
        data = json.dumps({
            "broker_type": credentials.broker_type.value,
            "endpoint": credentials.endpoint,
            "api_key": credentials.api_key,
            "api_secret": credentials.api_secret,
            "additional": credentials.additional,
        }).encode()
        encrypted = fernet.encrypt(data)

        # Store: salt + encrypted data
        self._store[broker_id] = broker_salt + encrypted

    def retrieve(self, broker_id: str) -> BrokerCredentials:
        """Decrypt and return credentials for a broker."""
        if broker_id not in self._store:
            raise KeyError(f"No credentials for broker: {broker_id}")

        stored = self._store[broker_id]
        broker_salt = stored[:16]
        encrypted = stored[16:]

        broker_key = self._derive_broker_key(broker_id, broker_salt)
        fernet = Fernet(broker_key)
        data = json.loads(fernet.decrypt(encrypted))

        return BrokerCredentials(
            broker_id=broker_id,
            broker_type=BrokerType(data["broker_type"]),
            endpoint=data["endpoint"],
            api_key=data["api_key"],
            api_secret=data["api_secret"],
            additional=data.get("additional", {}),
        )

    def delete(self, broker_id: str) -> None:
        """Securely remove credentials."""
        if broker_id in self._store:
            # Overwrite before deleting
            self._store[broker_id] = os.urandom(len(self._store[broker_id]))
            del self._store[broker_id]

    def _derive_broker_key(self, broker_id: str, salt: bytes) -> bytes:
        """Derive a unique key per broker from the master key."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt + broker_id.encode(),
            iterations=100_000,
        )
        return base64.urlsafe_b64encode(kdf.derive(self._master_key))
```

---

## 13. Event Bus & Real-Time Data

```python
from typing import Callable, Any
from collections import defaultdict

class EventBus:
    """
    In-process async event bus for inter-component communication.

    Events are typed and dispatched to registered handlers.
    For cross-process communication, events are also published to Redis Streams.
    """

    def __init__(self):
        self._handlers: dict[str, list[Callable]] = defaultdict(list)

    def on(self, event_type: str, handler: Callable) -> None:
        """Register a handler for an event type."""
        self._handlers[event_type].append(handler)

    def off(self, event_type: str, handler: Callable) -> None:
        """Unregister a handler."""
        if handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)

    def emit(self, event_type: str, data: dict) -> None:
        """Emit an event to all registered handlers."""
        for handler in self._handlers.get(event_type, []):
            try:
                asyncio.create_task(handler(data))
            except Exception as e:
                logger.error(f"Event handler error ({event_type}): {e}")


# Standard event types
EVENT_TYPES = {
    # Connection events
    "broker_connected":        "A broker connection was established",
    "broker_disconnected":     "A broker connection was lost",
    "broker_reconnected":      "A broker connection was re-established",
    "broker_connection_failed":"Failed to connect to a broker",

    # Order events
    "order_submitted":         "Order sent to broker",
    "order_filled":            "Order fully filled",
    "order_partially_filled":  "Order partially filled",
    "order_cancelled":         "Order cancelled",
    "order_rejected":          "Order rejected by broker or risk engine",
    "order_failover":          "Order re-routed to alternative broker",

    # Position events
    "position_opened":         "New position opened",
    "position_closed":         "Position closed",
    "position_updated":        "Position P&L updated",

    # Market events
    "price_update":            "Real-time price tick",
    "spread_alert":            "Spread exceeded threshold",
    "arbitrage_detected":      "Cross-broker arbitrage opportunity",

    # Risk events
    "margin_warning":          "Margin utilization above threshold",
    "drawdown_alert":          "Drawdown limit approached",
    "correlation_alert":       "Correlated position warning",
}
```

---

## 14. Error Taxonomy & Recovery

```python
class BrokerError(Exception):
    """Base error for all broker operations."""
    def __init__(self, broker_id: str, message: str, recoverable: bool = True):
        self.broker_id = broker_id
        self.recoverable = recoverable
        super().__init__(f"[{broker_id}] {message}")

class ConnectionLostError(BrokerError):
    """Broker connection dropped unexpectedly."""
    pass

class AuthError(BrokerError):
    """Authentication failed (bad credentials, expired token)."""
    recoverable = False

class InsufficientFundsError(BrokerError):
    """Not enough margin or balance."""
    recoverable = False

class SymbolNotFoundError(BrokerError):
    """Symbol not available on this broker."""
    recoverable = False

class RateLimitError(BrokerError):
    """Broker rate limit exceeded."""
    pass

class OrderRejectedError(BrokerError):
    """Broker rejected the order."""
    def __init__(self, broker_id: str, reason: str, broker_code: Optional[int] = None):
        self.broker_code = broker_code
        super().__init__(broker_id, f"Order rejected: {reason}")

class RoutingError(BrokerError):
    """No suitable broker found for the order."""
    recoverable = False

class RiskError(Exception):
    """Pre-trade risk check failed."""
    pass

class ExecutionRejected(Exception):
    """Execution filter rejected the order (spread, session, news)."""
    pass


# ─── Error Recovery Matrix ────────────────────────────────────────────────────
#
# Error Type             | Recovery Strategy
# -----------------------|----------------------------------------------------
# ConnectionLost         | Auto-reconnect (exponential backoff), failover
# AuthError              | Notify user, prompt re-authentication
# InsufficientFunds      | Reject order, notify user
# SymbolNotFound         | Try alternative broker, or reject
# RateLimit              | Backoff + retry, or route to alternative
# OrderRejected          | Log reason, try alternative broker if recoverable
# RoutingError           | Notify user: no broker available for this symbol
# RiskError              | Reject order, notify user
# ExecutionRejected      | Skip trade, log reason
# Unknown                | Log, alert, circuit breaker trip
```

---

## 15. Performance & Rate Limiting

### 15.1 Rate Limit Tracker

```python
class RateLimitTracker:
    """
    Tracks API usage per broker to avoid hitting rate limits.

    Each broker has different limits:
    - Binance: 1200 req/min (weighted)
    - Bybit: 120 req/5s
    - OKX: 20 req/2s per endpoint
    - OANDA: 120 req/min
    """

    def __init__(self):
        self._usage: dict[str, list[float]] = defaultdict(list)
        self._limits: dict[str, dict] = {}  # broker_id → {limit, window}

    def configure(self, broker_id: str, max_requests: int, window_seconds: int):
        self._limits[broker_id] = {"max": max_requests, "window": window_seconds}

    async def acquire(self, broker_id: str) -> None:
        """Wait until a request slot is available."""
        if broker_id not in self._limits:
            return  # No limit configured

        limit = self._limits[broker_id]
        now = time.time()

        # Prune old entries
        self._usage[broker_id] = [
            t for t in self._usage[broker_id]
            if now - t < limit["window"]
        ]

        # Wait if at limit
        while len(self._usage[broker_id]) >= limit["max"]:
            oldest = self._usage[broker_id][0]
            wait_time = limit["window"] - (now - oldest)
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            self._usage[broker_id].pop(0)
            now = time.time()

        self._usage[broker_id].append(now)
```

### 15.2 Connection Pooling

```python
# Key performance rules:
#
# 1. PERSISTENT CONNECTIONS: Never reconnect per-request.
#    Each connector maintains a single connection to its broker.
#
# 2. CONCURRENT QUERIES: Use asyncio.gather() to query all brokers simultaneously.
#    Don't serialize broker queries.
#
# 3. SMART CACHING:
#    - Symbol lists: cache for 5 minutes (rarely change)
#    - Account info: cache for 1 minute
#    - Prices: NEVER cache (always fetch live)
#    - OHLCV: cache completed candles, fetch latest live
#
# 4. CIRCUIT BREAKER: Don't waste requests on failing brokers.
#
# 5. RATE LIMIT AWARENESS: Track usage, throttle proactively.
```

---

## 16. Deployment Architecture

### 16.1 Service Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    Docker Compose / K8s                        │
│                                                               │
│  ┌───────────────┐  ┌───────────────┐  ┌──────────────────┐  │
│  │  alpha-stack   │  │  alpha-stack   │  │  alpha-stack     │  │
│  │  core-api      │  │  broker-worker │  │  market-data     │  │
│  │                │  │                │  │                  │  │
│  │  REST API      │  │  All broker    │  │  Price feeds     │  │
│  │  WebSocket     │  │  connectors    │  │  OHLCV cache     │  │
│  │  Auth          │  │  Order manager │  │  Symbol registry │  │
│  └───────┬───────┘  └───────┬───────┘  └────────┬─────────┘  │
│          │                  │                    │             │
│  ┌───────┴──────────────────┴────────────────────┴──────────┐ │
│  │                     Redis Streams                         │ │
│  │            (Event bus + real-time data cache)             │ │
│  └───────┬──────────────────────────────────────────────────┘ │
│          │                                                     │
│  ┌───────┴──────────────────────────────────────────────────┐ │
│  │                     PostgreSQL                            │ │
│  │     (Orders, positions, accounts, audit log)              │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │              TimescaleDB (on PostgreSQL)                  │ │
│  │           (OHLCV, tick data, spread history)              │ │
│  └──────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘

        External:
        ┌──────────────┐
        │ MT5 Bridge    │  (Windows VM or local Windows machine)
        │ (Python + MT5)│  ← Only needed for MT5 broker
        └──────────────┘
```

### 16.2 Container Configuration

```yaml
# docker-compose.yml
services:
  core-api:
    build: ./core
    ports: ["8000:8000"]
    depends_on: [postgres, redis]
    environment:
      DATABASE_URL: postgresql://alphastack:***@postgres:5432/alphastack
      REDIS_URL: redis://redis:6379

  broker-worker:
    build: ./broker
    depends_on: [postgres, redis]
    environment:
      DATABASE_URL: postgresql://alphastack:***@postgres:5432/alphastack
      REDIS_URL: redis://redis:6379
      MT5_BRIDGE_URL: ws://mt5-bridge:8765
    deploy:
      replicas: 1  # Single worker to manage all broker connections

  market-data:
    build: ./market-data
    depends_on: [redis]
    environment:
      REDIS_URL: redis://redis:6379

  postgres:
    image: postgres:16
    volumes: ["pgdata:/var/lib/postgresql/data"]

  redis:
    image: redis:7-alpine
    volumes: ["redis-data:/data"]

  # MT5 Bridge (optional — only if using MT5 broker)
  mt5-bridge:
    build: ./mt5-bridge
    platform: windows  # Or deploy separately on Windows VM
    environment:
      MT5_TERMINAL_PATH: C:\Program Files\MetaTrader 5\terminal64.exe
```

---

## 17. Testing Strategy

### 17.1 Test Pyramid

```
                    ┌──────────────┐
                    │  E2E Tests   │  ← Full order lifecycle with sandbox/testnet
                    │   (few)      │
                    ├──────────────┤
                    │ Integration  │  ← Real broker APIs (sandbox mode)
                    │   Tests      │
                    │  (moderate)  │
                    ├──────────────┤
                    │   Unit       │  ← Mock connectors, test routing/risk/order logic
                    │   Tests      │
                    │   (many)     │
                    └──────────────┘
```

### 17.2 Mock Connector for Testing

```python
class MockBrokerConnector(BrokerConnector):
    """
    Mock connector for unit testing.
    Simulates broker behavior without real API calls.
    """

    def __init__(self, credentials: BrokerCredentials):
        super().__init__(credentials)
        self._orders: dict[str, OrderConfirmation] = {}
        self._positions: list[UnifiedPosition] = []
        self._balance = [UnifiedBalance("USD", 10000, 0, 10000, credentials.broker_id)]
        self._fail_next: bool = False  # Inject failures

    async def connect(self) -> bool:
        self._connection_status = ConnectionStatus.CONNECTED
        return True

    async def place_order(self, order: UnifiedOrder) -> OrderConfirmation:
        if self._fail_next:
            self._fail_next = False
            raise BrokerError(self.broker_id, "Simulated failure", recoverable=True)

        confirmation = OrderConfirmation(
            order_id=order.order_id,
            broker_order_id=f"mock_{uuid4().hex[:8]}",
            broker_id=self.broker_id,
            status=OrderStatus.FILLED,
            fill_price=order.price or 1.0850,
            fill_quantity=order.quantity,
        )
        self._orders[confirmation.broker_order_id] = confirmation
        return confirmation
```

### 17.3 Test Scenarios

| Scenario | What to Test |
|----------|-------------|
| Happy path | Order placed → filled → position created → P&L updated |
| Connection loss | Broker disconnects → auto-reconnect → orders resume |
| Failover | Primary broker fails → order routed to alternative |
| Circuit breaker | 5 failures → broker marked unhealthy → no more orders sent |
| Rate limiting | 100 rapid requests → throttled to stay within limits |
| Partial fill | Order 50% filled → remaining tracked → complete on next fill |
| Risk rejection | Order exceeds max exposure → rejected before broker submission |
| Spread filter | Spread 3x average → order rejected by execution filter |
| Multi-broker | Same symbol on 2 brokers → router selects best |
| Arbitrage | Price discrepancy detected → alert emitted |
| Credential rotation | Old API key → new API key → seamless transition |

---

## 18. Implementation Roadmap

### Phase 1: Foundation (Weeks 1-3) — "Make It Work"

```
Week 1: Core interfaces + MT5 connector
  ├── [ ] Define BrokerConnector ABC
  ├── [ ] Define all data classes (UnifiedOrder, UnifiedPosition, etc.)
  ├── [ ] Implement MT5Connector (wrap existing FXPesa code)
  ├── [ ] SymbolRegistry with MT5 mappings
  └── [ ] Unit tests with MockBrokerConnector

Week 2: CCXT connector + registry
  ├── [ ] Implement CCXTConnector (Binance testnet first)
  ├── [ ] BrokerConnectorRegistry
  ├── [ ] ConnectionManager (connect, reconnect, health check)
  ├── [ ] EventBus (in-process)
  └── [ ] Integration tests with Binance testnet

Week 3: Order manager + basic portfolio
  ├── [ ] UnifiedOrderManager (submit, cancel, track)
  ├── [ ] PortfolioAggregator (aggregated balance + positions)
  ├── [ ] PostgreSQL schema (orders, positions, accounts)
  └── [ ] End-to-end test: place order → track → aggregate
```

### Phase 2: Routing & Risk (Weeks 4-6) — "Make It Smart"

```
Week 4: Smart routing
  ├── [ ] SmartOrderRouter (scoring, selection)
  ├── [ ] FailoverRouter (automatic failover)
  ├── [ ] CircuitBreaker
  └── [ ] RateLimitTracker

Week 5: Execution engine
  ├── [ ] ExecutionEngine (simple, filtered, TWAP tiers)
  ├── [ ] Spread filter, session filter, news filter
  ├── [ ] Position sizing (Kelly / fixed fractional)
  └── [ ] Execution logging + slippage tracking

Week 6: Risk engine
  ├── [ ] CrossBrokerRiskEngine
  ├── [ ] Pre-trade checks (exposure, margin, correlation)
  ├── [ ] Margin monitoring
  └── [ ] Alert system (margin warning, drawdown alert)
```

### Phase 3: Production Hardening (Weeks 7-9) — "Make It Reliable"

```
Week 7: REST + FIX connectors
  ├── [ ] RESTAPIConnector (OANDA first)
  ├── [ ] FIXConnector (institutional — if needed)
  ├── [ ] IBKRConnector (if TWS available)
  └── [ ] Symbol mappings for all new brokers

Week 8: Security + credentials
  ├── [ ] BrokerCredentialVault
  ├── [ ] Per-broker key isolation
  ├── [ ] Credential rotation support
  └── [ ] Audit logging

Week 9: Monitoring + observability
  ├── [ ] Prometheus metrics (order latency, fill rate, error rate)
  ├── [ ] Grafana dashboards
  ├── [ ] Alert rules (connection down, high error rate, margin warning)
  └── [ ] Redis Streams for cross-process events
```

### Phase 4: Advanced (Weeks 10-12) — "Make It Scale"

```
Week 10: Streaming
  ├── [ ] WebSocket price feeds (CCXT Pro, OANDA streaming)
  ├── [ ] Real-time position updates
  └── [ ] Real-time P&L calculation

Week 11: Arbitrage + analytics
  ├── [ ] ArbitrageDetector
  ├── [ ] Slippage analytics dashboard
  ├── [ ] Execution quality reporting
  └── [ ] Historical spread analysis

Week 12: Optimization
  ├── [ ] Performance profiling
  ├── [ ] Connection pooling optimization
  ├── [ ] Cache tuning
  └── [ ] Load testing
```

---

## 19. Appendices

### A. Database Schema

```sql
-- Orders table
CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(4) NOT NULL,
    order_type VARCHAR(20) NOT NULL,
    quantity DECIMAL(20, 8) NOT NULL,
    price DECIMAL(20, 8),
    stop_loss DECIMAL(20, 8),
    take_profit DECIMAL(20, 8),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    broker_id VARCHAR(50),
    broker_order_id VARCHAR(100),
    fill_price DECIMAL(20, 8),
    fill_quantity DECIMAL(20, 8),
    commission DECIMAL(20, 8),
    asset_class VARCHAR(20),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    filled_at TIMESTAMPTZ
);

CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_broker ON orders(broker_id);
CREATE INDEX idx_orders_symbol ON orders(symbol);

-- Positions table
CREATE TABLE positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(4) NOT NULL,
    quantity DECIMAL(20, 8) NOT NULL,
    entry_price DECIMAL(20, 8) NOT NULL,
    current_price DECIMAL(20, 8),
    unrealized_pnl DECIMAL(20, 8) DEFAULT 0,
    realized_pnl DECIMAL(20, 8) DEFAULT 0,
    margin_used DECIMAL(20, 8) DEFAULT 0,
    broker_id VARCHAR(50) NOT NULL,
    broker_position_id VARCHAR(100),
    asset_class VARCHAR(20),
    opened_at TIMESTAMPTZ DEFAULT NOW(),
    closed_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_positions_broker ON positions(broker_id);
CREATE INDEX idx_positions_symbol ON positions(symbol);
CREATE INDEX idx_positions_open ON positions(closed_at) WHERE closed_at IS NULL;

-- Broker connections table
CREATE TABLE broker_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    broker_type VARCHAR(20) NOT NULL,
    label VARCHAR(100),
    endpoint VARCHAR(200),
    -- Credentials stored in encrypted vault, NOT in database
    status VARCHAR(20) DEFAULT 'disconnected',
    capabilities JSONB DEFAULT '{}',
    last_connected_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Execution audit log
CREATE TABLE execution_log (
    id BIGSERIAL PRIMARY KEY,
    order_id UUID REFERENCES orders(id),
    event_type VARCHAR(50) NOT NULL,
    broker_id VARCHAR(50),
    latency_ms INTEGER,
    slippage_pips DECIMAL(10, 4),
    spread_at_fill DECIMAL(10, 6),
    details JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- OHLCV data (TimescaleDB hypertable)
CREATE TABLE ohlcv (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(5) NOT NULL,
    open DECIMAL(20, 8) NOT NULL,
    high DECIMAL(20, 8) NOT NULL,
    low DECIMAL(20, 8) NOT NULL,
    close DECIMAL(20, 8) NOT NULL,
    volume DECIMAL(20, 8) NOT NULL,
    broker_id VARCHAR(50)
);

SELECT create_hypertable('ohlcv', 'time');
CREATE INDEX idx_ohlcv_symbol_tf ON ohlcv(symbol, timeframe, time DESC);
```

### B. Configuration File Structure

```yaml
# config/brokers.yaml
brokers:
  fxpesa_mt5:
    type: mt5
    label: "FXPesa Forex"
    endpoint: "FXPesa-Live"
    # Credentials loaded from encrypted vault at runtime
    asset_classes: [forex, cfd]
    symbols:
      EUR/USD: "EURUSD"
      GBP/USD: "GBPUSD"
      XAU/USD: "XAUUSD"

  binance:
    type: ccxt
    label: "Binance Crypto"
    endpoint: "binance"
    asset_classes: [crypto]
    additional:
      type: "spot"  # or "future", "margin"
      sandbox: false
    symbols:
      BTC/USD: "BTC/USDT"
      ETH/USD: "ETH/USDT"

  oanda:
    type: rest_api
    label: "OANDA Forex"
    endpoint: "https://api-fxtrade.oanda.com"
    asset_classes: [forex, cfd]
    api_spec_file: "config/oanda_spec.yaml"
    symbols:
      EUR/USD: "EUR_USD"
      GBP/USD: "GBP_USD"

execution:
  capital_tiers:
    simple: {max_capital: 50, filters: [spread, session, news]}
    filtered: {max_capital: 500, filters: [spread, session, news, partial_fill]}
    twap: {max_capital: 5000, filters: [spread, session, news, twap]}
    institutional: {max_capital: null, filters: [spread, session, news, twap, vwap]}

  spread_filter:
    max_multiplier: 2.0  # Reject if spread > 2x 1-hour average

  session_filter:
    allowed_hours_utc: {start: 13, end: 17}  # London-NY overlap

  risk:
    max_exposure_pct: 20         # Max 20% of capital in single position
    max_total_exposure_pct: 80   # Max 80% total margin utilization
    max_correlation: 0.8         # Reject correlated positions above this
    max_drawdown_pct: 15         # Emergency stop at 15% drawdown

routing:
  weights:
    spread: 0.30
    liquidity: 0.25
    latency: 0.20
    fees: 0.15
    reliability: 0.10

circuit_breaker:
  failure_threshold: 5
  failure_window_seconds: 60
  recovery_timeout_seconds: 60
```

### C. Technology Stack Summary

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Language | Python | 3.11+ | Core runtime |
| Async | asyncio | stdlib | Concurrent broker connections |
| HTTP | aiohttp | 3.9+ | REST API calls |
| WebSocket | websockets | 12+ | Real-time data |
| MT5 | MetaTrader5 | 5.0+ | MT5 broker connector |
| Crypto | ccxt | 4.0+ | Crypto exchange connector |
| IBKR | ib_insync | 0.9+ | Interactive Brokers connector |
| Database | PostgreSQL | 16+ | Orders, positions, accounts |
| Time series | TimescaleDB | 2.x | OHLCV, tick data |
| Cache | Redis | 7+ | Real-time cache, event bus |
| Encryption | cryptography | 42+ | Credential vault (Fernet/AES) |
| Monitoring | Prometheus + Grafana | latest | Metrics and dashboards |
| Containers | Docker + Compose | latest | Deployment |

---

*This architecture document is the blueprint for Alpha Stack's broker abstraction layer. It defines the interfaces, implementations, and operational patterns needed to connect to any broker through a single unified system. Start with Phase 1 (MT5 + CCXT), validate the abstractions work, then add brokers and sophistication as capital grows.*
