# Alpha Stack — Hybrid Broker Architecture Research

**Date:** 2026-07-11  
**Purpose:** Research how to evolve Alpha Stack from a single-broker (FXPesa/MT5) system into a hybrid multi-broker platform supporting forex AND crypto simultaneously.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Multi-Broker Architecture Patterns](#2-multi-broker-architecture-patterns)
3. [Connection Method Abstraction](#3-connection-method-abstraction)
4. [Unified Account Model](#4-unified-account-model)
5. [Smart Order Routing Across Brokers](#5-smart-order-routing-across-brokers)
6. [User Experience Design](#6-user-experience-design)
7. [Security for Multi-Broker](#7-security-for-multi-broker)
8. [Implementation Roadmap](#8-implementation-roadmap)
9. [Technology Stack Recommendations](#9-technology-stack-recommendations)

---

## 1. Executive Summary

**Current State:** Alpha Stack connects to FXPesa via MetaTrader 5 for forex trading only. No crypto support.

**Target State:** Alpha Stack becomes a broker-agnostic platform where users connect any supported broker (forex, crypto, or both) and trade through a unified interface. The system handles:

- Multiple simultaneous broker connections
- Aggregated portfolio view across all brokers
- Smart order routing for best execution
- Cross-broker risk management
- Failover if one broker goes down

**Core Insight from Industry Research:** Professional multi-asset platforms like TraderEvolution, Quod Financial, and Interactive Brokers all follow the same pattern: a **single unified back-end** with a **broker connector abstraction layer**. Each broker is a plugin that implements a standard interface. The order management, risk engine, and portfolio view are broker-agnostic.

---

## 2. Multi-Broker Architecture Patterns

### 2.1 How Professional Platforms Handle It

**TraderEvolution Pattern (Industry Standard):**
- Single back-end engine handles ALL asset classes
- One order management system (OMS) for everything
- One risk engine calculates margin across all positions
- One account structure, one login, one portfolio view
- Brokers enable asset classes selectively (launch forex, add equities later, add crypto — no re-deployment)

**Interactive Brokers Pattern:**
- Universal account model: one IB account trades stocks, options, futures, forex, crypto, bonds
- Their TWS API / Web API / FIX connection all talk to the same back-end
- Smart order routing built-in: scans all connected venues for best price
- Cross-margin across asset classes

**MetaTrader Pattern (MT4/MT5):**
- Each broker is a separate server endpoint
- Client connects to one broker at a time
- No native multi-broker support (limitation)
- MT5 has a Python API (`MetaTrader5` library) — useful for our connector

### 2.2 Recommended Architecture for Alpha Stack

```
┌─────────────────────────────────────────────────────────┐
│                    ALPHA STACK CORE                       │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │  Strategy    │  │    Risk      │  │   Portfolio    │  │
│  │  Engine      │  │    Engine    │  │   Aggregator   │  │
│  └──────┬──────┘  └──────┬───────┘  └───────┬────────┘  │
│         │                │                   │           │
│  ┌──────┴────────────────┴───────────────────┴────────┐  │
│  │              UNIFIED ORDER MANAGER                  │  │
│  │         (Single source of truth for all orders)     │  │
│  └─────────────────────┬──────────────────────────────┘  │
│                        │                                  │
│  ┌─────────────────────┴──────────────────────────────┐  │
│  │           BROKER CONNECTOR ABSTRACTION              │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐│  │
│  │  │ MT5      │ │ CCXT     │ │ REST API │ │ FIX    ││  │
│  │  │Connector │ │Connector │ │Connector │ │Connec. ││  │
│  │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └───┬────┘│  │
│  └───────┼─────────────┼────────────┼────────────┼─────┘  │
└──────────┼─────────────┼────────────┼────────────┼────────┘
           │             │            │            │
     ┌─────┴─────┐ ┌────┴────┐ ┌─────┴─────┐ ┌───┴────┐
     │  FXPesa   │ │ Binance │ │   OANDA   │ │  IBKR  │
     │   MT5     │ │  Bybit  │ │ IG Markets│ │  FIX   │
     │           │ │  OKX    │ │           │ │        │
     └───────────┘ └─────────┘ └───────────┘ └────────┘
```

### 2.3 Key Design Principles

1. **Plugin Architecture:** Each broker connector is a separate module that implements a standard interface. Adding a new broker = adding a new plugin.
2. **Event-Driven:** All broker connectors emit events (order filled, position updated, balance changed) to a central event bus.
3. **Stateless Core:** The Alpha Stack core doesn't store broker-specific state. All state flows through the unified order manager.
4. **Failover Ready:** If one broker connection drops, the system can route to alternative brokers.

---

## 3. Connection Method Abstraction

### 3.1 The Unified BrokerConnector Interface

Every broker connector must implement this standard interface:

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional

class BrokerType(Enum):
    MT5 = "mt5"
    CCXT = "ccxt"          # Crypto exchanges via CCXT
    REST_API = "rest_api"   # OANDA, IG Markets
    FIX = "fix"             # Institutional
    WEBSOCKET = "websocket" # Real-time data feeds

class AssetClass(Enum):
    FOREX = "forex"
    CRYPTO = "crypto"
    CFD = "cfd"
    EQUITIES = "equities"
    FUTURES = "futures"

@dataclass
class BrokerCredentials:
    broker_id: str              # Unique identifier for this connection
    broker_type: BrokerType
    endpoint: str               # Server URL / exchange name
    api_key: str
    api_secret: str
    additional: dict            # Broker-specific (account_id, passphrase, etc.)

@dataclass
class UnifiedOrder:
    order_id: str
    symbol: str                 # Normalized symbol (e.g., "EUR/USD", "BTC/USDT")
    side: str                   # "buy" or "sell"
    order_type: str             # "market", "limit", "stop"
    quantity: float
    price: Optional[float]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    broker_id: str              # Which broker to route to
    asset_class: AssetClass

@dataclass
class UnifiedPosition:
    symbol: str
    side: str
    quantity: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    broker_id: str
    asset_class: AssetClass

@dataclass
class UnifiedBalance:
    currency: str
    available: float
    locked: float               # In orders
    total: float
    broker_id: str

class BrokerConnector(ABC):
    """Abstract base class for all broker connectors."""
    
    @abstractmethod
    async def connect(self, credentials: BrokerCredentials) -> bool:
        """Establish connection to the broker."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Clean disconnect from broker."""
        pass
    
    @abstractmethod
    async def is_connected(self) -> bool:
        """Check if connection is alive."""
        pass
    
    # --- Market Data ---
    @abstractmethod
    async def get_symbols(self) -> list[str]:
        """Get all tradeable symbols."""
        pass
    
    @abstractmethod
    async def get_ticker(self, symbol: str) -> dict:
        """Get current price for a symbol."""
        pass
    
    @abstractmethod
    async def get_orderbook(self, symbol: str, depth: int = 20) -> dict:
        """Get order book / depth of market."""
        pass
    
    @abstractmethod
    async def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 100) -> list:
        """Get candlestick data."""
        pass
    
    # --- Trading ---
    @abstractmethod
    async def place_order(self, order: UnifiedOrder) -> dict:
        """Place an order. Returns broker-specific order confirmation."""
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order."""
        pass
    
    @abstractmethod
    async def modify_order(self, order_id: str, **kwargs) -> bool:
        """Modify an existing order (price, SL, TP)."""
        pass
    
    # --- Account ---
    @abstractmethod
    async def get_balance(self) -> list[UnifiedBalance]:
        """Get account balance(s)."""
        pass
    
    @abstractmethod
    async def get_positions(self) -> list[UnifiedPosition]:
        """Get all open positions."""
        pass
    
    @abstractmethod
    async def get_open_orders(self) -> list[UnifiedOrder]:
        """Get all pending orders."""
        pass
    
    # --- Streaming ---
    @abstractmethod
    async def subscribe_ticker(self, symbol: str, callback) -> None:
        """Subscribe to real-time price updates."""
        pass
    
    @abstractmethod
    async def subscribe_trades(self, callback) -> None:
        """Subscribe to real-time trade executions."""
        pass
```

### 3.2 MT5 Connector (FXPesa — Forex)

```python
import MetaTrader5 as mt5

class MT5Connector(BrokerConnector):
    """Connector for MetaTrader 5 brokers (FXPesa, Exness, ICMarkets, etc.)"""
    
    def __init__(self):
        self._connected = False
    
    async def connect(self, credentials: BrokerCredentials) -> bool:
        if not mt5.initialize():
            raise ConnectionError(f"MT5 init failed: {mt5.last_error()}")
        
        authorized = mt5.login(
            login=int(credentials.additional["login"]),
            password=credentials.api_secret,
            server=credentials.endpoint,  # e.g., "FXPesa-Demo"
            timeout=10000
        )
        
        if not authorized:
            raise ConnectionError(f"MT5 login failed: {mt5.last_error()}")
        
        self._connected = True
        return True
    
    async def place_order(self, order: UnifiedOrder) -> dict:
        # Normalize to MT5 format
        mt5_type = mt5.ORDER_TYPE_BUY if order.side == "buy" else mt5.ORDER_TYPE_SELL
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": order.symbol,  # MT5 uses "EURUSD" (no slash)
            "volume": order.quantity,
            "type": mt5_type,
            "magic": 202607,
            "comment": f"AlphaStack-{order.order_id}",
        }
        
        if order.price:
            request["price"] = order.price
        
        if order.stop_loss:
            request["sl"] = order.stop_loss
        if order.take_profit:
            request["tp"] = order.take_profit
        
        result = mt5.order_send(request)
        return {"broker_order_id": result.order, "status": result.comment}
    
    # ... other methods follow same pattern
```

**Supported MT5 Brokers (Forex):**
- FXPesa (current)
- Exness
- ICMarkets
- Pepperstone
- XM
- Any MT5 broker

### 3.3 CCXT Connector (Crypto Exchanges)

CCXT is the gold standard for crypto exchange abstraction. It already provides a unified interface to **104+ crypto exchanges**.

```python
import ccxt.async_support as ccxt

class CCXTConnector(BrokerConnector):
    """Connector for crypto exchanges via CCXT library."""
    
    def __init__(self):
        self._exchange = None
    
    async def connect(self, credentials: BrokerCredentials) -> bool:
        # credentials.endpoint = "binance", "bybit", "okx", etc.
        exchange_class = getattr(ccxt, credentials.endpoint)
        
        self._exchange = exchange_class({
            "apiKey": credentials.api_key,
            "secret": credentials.api_secret,
            "options": {"defaultType": "spot"},  # or "future", "swap"
        })
        
        # Load markets
        await self._exchange.load_markets()
        self._connected = True
        return True
    
    async def place_order(self, order: UnifiedOrder) -> dict:
        # CCXT unified order interface
        result = await self._exchange.create_order(
            symbol=order.symbol,        # "BTC/USDT"
            type=order.order_type,      # "limit" or "market"
            side=order.side,            # "buy" or "sell"
            amount=order.quantity,
            price=order.price,
            params={
                "stopLoss": order.stop_loss,
                "takeProfit": order.take_profit,
            }
        )
        return {"broker_order_id": result["id"], "status": result["status"]}
    
    async def get_balance(self) -> list[UnifiedBalance]:
        balance = await self._exchange.fetch_balance()
        result = []
        for currency, data in balance.items():
            if isinstance(data, dict) and data.get("total", 0) > 0:
                result.append(UnifiedBalance(
                    currency=currency,
                    available=data.get("free", 0),
                    locked=data.get("used", 0),
                    total=data.get("total", 0),
                    broker_id=self._credentials.broker_id
                ))
        return result
```

**Supported Crypto Exchanges via CCXT:**
- Binance, Binance Futures
- Bybit, Bybit USDT Perpetual
- OKX (spot + futures)
- Coinbase Pro
- Kraken
- Bitget, Gate.io, KuCoin, and 90+ more

### 3.4 REST API Connector (OANDA, IG Markets)

```python
import aiohttp

class RESTAPIConnector(BrokerConnector):
    """Generic REST API connector for brokers with HTTP APIs."""
    
    def __init__(self, api_spec: dict):
        """
        api_spec defines the broker's API:
        - base_url, auth_method, endpoints for each action
        """
        self._spec = api_spec
        self._session = None
    
    async def connect(self, credentials: BrokerCredentials) -> bool:
        self._session = aiohttp.ClientSession(
            base_url=credentials.endpoint,
            headers=self._build_auth_headers(credentials)
        )
        # Verify connection
        async with self._session.get("/account") as resp:
            return resp.status == 200
    
    def _build_auth_headers(self, creds: BrokerCredentials) -> dict:
        if self._spec["auth"] == "bearer":
            return {"Authorization": f"Bearer {creds.api_key}"}
        elif self._spec["auth"] == "oanda":
            return {"Authorization": f"Bearer {creds.api_key}"}
        elif self._spec["auth"] == "hmac":
            # For IG Markets, etc.
            return {"X-API-KEY": creds.api_key}
```

**Supported REST API Brokers:**
- OANDA (REST v20 API)
- IG Markets (REST API)
- Any broker with HTTP API

### 3.5 FIX Protocol Connector (Institutional)

```python
# Using quickfix or similar FIX engine
class FIXConnector(BrokerConnector):
    """FIX protocol connector for institutional brokers."""
    
    def __init__(self):
        self._fix_session = None
    
    async def connect(self, credentials: BrokerCredentials) -> bool:
        # FIX 4.4 / 5.0 connection
        # Requires FIX engine (quickfix, simplesonfix, etc.)
        self._fix_session = FIXSession(
            host=credentials.endpoint,
            port=int(credentials.additional.get("port", 9876)),
            sender_comp_id=credentials.additional["sender_comp_id"],
            target_comp_id=credentials.additional["target_comp_id"],
        )
        return await self._fix_session.logon()
```

### 3.6 Connector Registry

```python
class BrokerConnectorRegistry:
    """Registry that manages all active broker connections."""
    
    def __init__(self):
        self._connectors: dict[str, BrokerConnector] = {}
        self._credentials: dict[str, BrokerCredentials] = {}
    
    async def add_broker(self, credentials: BrokerCredentials) -> str:
        """Add and connect a new broker."""
        connector = self._create_connector(credentials.broker_type)
        await connector.connect(credentials)
        self._connectors[credentials.broker_id] = connector
        self._credentials[credentials.broker_id] = credentials
        return credentials.broker_id
    
    async def remove_broker(self, broker_id: str) -> None:
        """Disconnect and remove a broker."""
        if broker_id in self._connectors:
            await self._connectors[broker_id].disconnect()
            del self._connectors[broker_id]
            del self._credentials[broker_id]
    
    def get_connector(self, broker_id: str) -> BrokerConnector:
        return self._connectors.get(broker_id)
    
    def get_all_connectors(self) -> dict[str, BrokerConnector]:
        return self._connectors
    
    def _create_connector(self, broker_type: BrokerType) -> BrokerConnector:
        match broker_type:
            case BrokerType.MT5:
                return MT5Connector()
            case BrokerType.CCXT:
                return CCXTConnector()
            case BrokerType.REST_API:
                return RESTAPIConnector(api_spec={})  # Loaded from config
            case BrokerType.FIX:
                return FIXConnector()
            case _:
                raise ValueError(f"Unknown broker type: {broker_type}")
```

---

## 4. Unified Account Model

### 4.1 Architecture

```
Alpha Stack User Account
├── Connection 1: FXPesa (MT5, Forex)
│   ├── Balance: $10,000 USD
│   ├── Positions: EUR/USD long, GBP/JPY short
│   └── Open Orders: 2 limit orders
├── Connection 2: Binance (CCXT, Crypto)
│   ├── Balance: 0.5 BTC, 5000 USDT
│   ├── Positions: BTC/USDT long
│   └── Open Orders: 1 stop order
└── Connection 3: OANDA (REST, Forex)
    ├── Balance: $5,000 USD
    ├── Positions: USD/JPY long
    └── Open Orders: none
```

### 4.2 Aggregated Portfolio View

```python
class PortfolioAggregator:
    """Aggregates positions and balances across all brokers."""
    
    def __init__(self, registry: BrokerConnectorRegistry):
        self._registry = registry
    
    async def get_aggregated_balance(self) -> dict:
        """Get total balance across all brokers, converted to base currency."""
        total = {"USD": 0, "BTC": 0, "ETH": 0}
        
        for broker_id, connector in self._registry.get_all_connectors().items():
            balances = await connector.get_balance()
            for bal in balances:
                # Convert to base currency using current rates
                usd_value = await self._convert_to_usd(bal.currency, bal.total)
                total["USD"] += usd_value
        
        return total
    
    async def get_aggregated_positions(self) -> list[UnifiedPosition]:
        """Get all positions across all brokers."""
        all_positions = []
        for broker_id, connector in self._registry.get_all_connectors().items():
            positions = await connector.get_positions()
            all_positions.extend(positions)
        return all_positions
    
    async def get_unified_pnl(self) -> dict:
        """Calculate total P&L across all brokers."""
        total_pnl = {"realized": 0, "unrealized": 0}
        
        for broker_id, connector in self._registry.get_all_connectors().items():
            positions = await connector.get_positions()
            for pos in positions:
                total_pnl["unrealized"] += await self._convert_to_usd(
                    pos.symbol, pos.unrealized_pnl
                )
        
        return total_pnl
```

### 4.3 Cross-Broker Risk Management

```python
class CrossBrokerRiskEngine:
    """Risk management that spans all connected brokers."""
    
    def __init__(self, portfolio: PortfolioAggregator):
        self._portfolio = portfolio
    
    async def check_total_exposure(self) -> dict:
        """Check if total exposure across all brokers exceeds limits."""
        positions = await self._portfolio.get_aggregated_positions()
        
        # Calculate net exposure per currency/asset
        exposure = {}
        for pos in positions:
            base_currency = pos.symbol.split("/")[0]
            usd_value = await self._convert_to_usd(pos.symbol, pos.quantity * pos.current_price)
            exposure[base_currency] = exposure.get(base_currency, 0) + usd_value
        
        return exposure
    
    async def check_margin_utilization(self) -> float:
        """Check total margin utilization as percentage across all brokers."""
        total_margin = 0
        total_equity = 0
        
        for broker_id, connector in self._registry.get_all_connectors().items():
            # Each broker reports margin differently
            # Normalize to USD equivalent
            margin_used = await self._get_margin_used(connector)
            equity = await self._get_equity(connector)
            total_margin += margin_used
            total_equity += equity
        
        return (total_margin / total_equity * 100) if total_equity > 0 else 0
    
    async def pre_trade_check(self, order: UnifiedOrder) -> tuple[bool, str]:
        """Validate order against risk limits before sending."""
        # 1. Check max position size per instrument
        # 2. Check max total exposure
        # 3. Check margin availability
        # 4. Check correlation limits (e.g., don't be long EUR/USD and short USD/CHF)
        # 5. Check max drawdown limits
        return True, "OK"
```

---

## 5. Smart Order Routing Across Brokers

### 5.1 Smart Order Router

```python
class SmartOrderRouter:
    """Routes orders to the best broker based on multiple factors."""
    
    def __init__(self, registry: BrokerConnectorRegistry):
        self._registry = registry
    
    async def route_order(self, order: UnifiedOrder) -> str:
        """
        Determine the best broker for this order.
        Returns the broker_id to use.
        """
        candidates = self._get_capable_brokers(order)
        
        if not candidates:
            raise ValueError(f"No broker available for {order.symbol}")
        
        if len(candidates) == 1:
            return candidates[0]
        
        # Score each candidate
        scores = {}
        for broker_id in candidates:
            score = await self._score_broker(broker_id, order)
            scores[broker_id] = score
        
        return max(scores, key=scores.get)
    
    def _get_capable_brokers(self, order: UnifiedOrder) -> list[str]:
        """Find brokers that can handle this asset class and symbol."""
        capable = []
        for broker_id, connector in self._registry.get_all_connectors().items():
            if connector.is_connected() and connector.supports_symbol(order.symbol):
                capable.append(broker_id)
        return capable
    
    async def _score_broker(self, broker_id: str, order: UnifiedOrder) -> float:
        """Score a broker for this specific order (higher = better)."""
        connector = self._registry.get_connector(broker_id)
        
        factors = {
            "spread": await self._get_spread_score(connector, order.symbol),    # Lower spread = better
            "liquidity": await self._get_liquidity_score(connector, order.symbol),  # More liquidity = better
            "latency": await self._get_latency_score(connector),                # Lower latency = better
            "fees": await self._get_fee_score(connector, order),                # Lower fees = better
            "reliability": self._get_reliability_score(broker_id),              # Historical uptime
        }
        
        weights = {"spread": 0.3, "liquidity": 0.25, "latency": 0.2, "fees": 0.15, "reliability": 0.1}
        
        return sum(factors[k] * weights[k] for k in factors)
```

### 5.2 Arbitrage Detection

```python
class ArbitrageDetector:
    """Detects price discrepancies between brokers."""
    
    async def detect_arbitrage(self, symbol: str) -> Optional[dict]:
        """
        Check if there's a price discrepancy worth exploiting.
        Returns arbitrage opportunity if found.
        """
        prices = {}
        for broker_id, connector in self._registry.get_all_connectors().items():
            ticker = await connector.get_ticker(symbol)
            prices[broker_id] = {
                "bid": ticker["bid"],
                "ask": ticker["ask"],
            }
        
        # Find: can we buy cheap on one broker and sell expensive on another?
        for buy_broker, buy_prices in prices.items():
            for sell_broker, sell_prices in prices.items():
                if buy_broker == sell_broker:
                    continue
                
                profit_per_unit = sell_prices["bid"] - buy_prices["ask"]
                if profit_per_unit > 0:
                    # Check if profit exceeds fees on both sides
                    total_fees = await self._estimate_fees(buy_broker, sell_broker, symbol)
                    net_profit = profit_per_unit - total_fees
                    
                    if net_profit > 0:
                        return {
                            "symbol": symbol,
                            "buy_at": buy_broker,
                            "buy_price": buy_prices["ask"],
                            "sell_at": sell_broker,
                            "sell_price": sell_prices["bid"],
                            "profit_per_unit": net_profit,
                        }
        
        return None
```

### 5.3 Failover Routing

```python
class FailoverRouter:
    """Handles broker failures by routing to alternatives."""
    
    async def execute_with_failover(self, order: UnifiedOrder, primary_broker: str) -> dict:
        """Execute order with automatic failover."""
        brokers_to_try = [primary_broker] + self._get_alternatives(order)
        
        for broker_id in brokers_to_try:
            try:
                connector = self._registry.get_connector(broker_id)
                if not connector.is_connected():
                    continue
                
                result = await connector.place_order(order)
                if broker_id != primary_broker:
                    logger.warning(f"Failover: routed to {broker_id} instead of {primary_broker}")
                return result
                
            except Exception as e:
                logger.error(f"Order failed on {broker_id}: {e}")
                continue
        
        raise RuntimeError(f"All brokers failed for order {order.order_id}")
    
    def _get_alternatives(self, order: UnifiedOrder) -> list[str]:
        """Get alternative brokers ranked by suitability."""
        alternatives = []
        for broker_id, connector in self._registry.get_all_connectors().items():
            if connector.supports_symbol(order.symbol) and connector.is_connected():
                alternatives.append(broker_id)
        return alternatives
```

---

## 6. User Experience Design

### 6.1 Adding a Broker Connection

The UX should feel like adding an email account to a mail app:

```
Settings → Broker Connections → + Add Connection

┌─────────────────────────────────────────────┐
│         ADD BROKER CONNECTION                │
│                                              │
│  Broker Type:                                │
│  ┌─────────────────────────────────────┐    │
│  │ ▼ MetaTrader 5 (Forex)              │    │
│  └─────────────────────────────────────┘    │
│                                              │
│  Select Broker:                              │
│  ┌─────────────────────────────────────┐    │
│  │ ▼ FXPesa                            │    │
│  └─────────────────────────────────────┘    │
│                                              │
│  Account Login:                              │
│  ┌─────────────────────────────────────┐    │
│  │ 12345678                            │    │
│  └─────────────────────────────────────┘    │
│                                              │
│  Password:                                   │
│  ┌─────────────────────────────────────┐    │
│  │ ••••••••••••                        │    │
│  └─────────────────────────────────────┘    │
│                                              │
│  Server:                                     │
│  ┌─────────────────────────────────────┐    │
│  │ FXPesa-Live                         │    │
│  └─────────────────────────────────────┘    │
│                                              │
│  [Test Connection]  [Save]  [Cancel]         │
└─────────────────────────────────────────────┘
```

### 6.2 Dashboard — Unified View

```
┌──────────────────────────────────────────────────────────────┐
│  ALPHA STACK — Portfolio Overview                             │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  Total Balance: $28,450.00    Unrealized P&L: +$1,234.56     │
│  Margin Used: 34.2%           Free Margin: $18,719.50        │
│                                                               │
│  ┌─── Connected Brokers ────────────────────────────────┐   │
│  │ 🟢 FXPesa (MT5)     │ $10,000  │ 3 positions │ +$450 │   │
│  │ 🟢 Binance (CCXT)   │ $13,450  │ 2 positions │ +$784 │   │
│  │ 🟢 OANDA (REST)     │ $5,000   │ 1 position  │ +$0.56│   │
│  └───────────────────────────────────────────────────────┘   │
│                                                               │
│  ┌─── All Positions ────────────────────────────────────┐    │
│  │ Symbol      │ Side │ Qty   │ Entry   │ Current │ P&L  │   │
│  │ EUR/USD     │ Long │ 1.0   │ 1.0850  │ 1.0892  │ +$420│   │
│  │ GBP/JPY     │ Short│ 0.5   │ 192.50  │ 191.80  │ +$350│   │
│  │ BTC/USDT    │ Long │ 0.1   │ 62,000  │ 65,500  │ +$350│   │
│  │ ETH/USDT    │ Long │ 2.0   │ 3,200   │ 3,442   │ +$484│   │
│  │ USD/JPY     │ Long │ 0.3   │ 155.20  │ 155.22  │ +$40 │   │
│  └───────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

### 6.3 Symbol Discovery

Users should be able to search and trade any symbol across all connected brokers:

```python
class SymbolRouter:
    """Routes symbol queries to the right broker(s)."""
    
    async def search_symbols(self, query: str) -> list[dict]:
        """Search for tradeable symbols across all brokers."""
        results = []
        for broker_id, connector in self._registry.get_all_connectors().items():
            symbols = await connector.get_symbols()
            for sym in symbols:
                if query.upper() in sym.upper():
                    results.append({
                        "symbol": sym,
                        "broker_id": broker_id,
                        "broker_type": connector.broker_type,
                    })
        return results
    
    def get_symbol_routing(self, symbol: str) -> list[str]:
        """Which brokers can trade this symbol?"""
        capable = []
        for broker_id, connector in self._registry.get_all_connectors().items():
            if connector.supports_symbol(symbol):
                capable.append(broker_id)
        return capable
```

---

## 7. Security for Multi-Broker

### 7.1 Credential Storage Architecture

```
Alpha Stack Security Model
├── User Authentication (Alpha Stack account)
│   └── JWT / session token
├── Broker Credential Storage
│   ├── Each broker's credentials encrypted with separate AES-256 key
│   ├── Encryption key derived from user's master password (PBKDF2/Argon2)
│   ├── Credentials NEVER stored in plaintext
│   └── Credentials NEVER logged
├── Credential Isolation
│   ├── Each broker connection has its own encrypted key
│   ├── Compromising one broker doesn't expose others
│   └── Credentials only decrypted in memory when needed
└── Transport Security
    ├── All API calls over TLS 1.3
    ├── Broker connections use TLS/SSL
    └── No credentials in URLs or query strings
```

### 7.2 Implementation

```python
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import os

class BrokerCredentialVault:
    """Encrypted storage for broker credentials."""
    
    def __init__(self, master_password: str, salt: bytes = None):
        self._salt = salt or os.urandom(16)
        self._master_key = self._derive_key(master_password)
    
    def _derive_key(self, password: str) -> bytes:
        """Derive encryption key from master password using PBKDF2."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self._salt,
            iterations=600_000,  # OWASP recommended minimum
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))
    
    def encrypt_credentials(self, credentials: BrokerCredentials) -> bytes:
        """Encrypt broker credentials for storage."""
        fernet = Fernet(self._master_key)
        data = json.dumps({
            "broker_id": credentials.broker_id,
            "broker_type": credentials.broker_type.value,
            "endpoint": credentials.endpoint,
            "api_key": credentials.api_key,
            "api_secret": credentials.api_secret,
            "additional": credentials.additional,
        }).encode()
        return fernet.encrypt(data)
    
    def decrypt_credentials(self, encrypted: bytes) -> BrokerCredentials:
        """Decrypt broker credentials (only in memory, never persisted)."""
        fernet = Fernet(self._master_key)
        data = json.loads(fernet.decrypt(encrypted))
        return BrokerCredentials(**data)
    
    def rotate_key(self, old_password: str, new_password: str):
        """Rotate the master encryption key."""
        # Re-encrypt all credentials with new key
        pass
```

### 7.3 Per-Broker Key Isolation

```python
class IsolatedCredentialStore:
    """
    Each broker gets its own encryption key.
    Compromising one key doesn't expose other brokers.
    """
    
    def __init__(self, master_password: str):
        self._master_key = self._derive_master_key(master_password)
        self._broker_keys: dict[str, bytes] = {}  # broker_id -> encrypted data
    
    def store(self, broker_id: str, credentials: BrokerCredentials):
        # Generate a unique key for this broker
        broker_salt = os.urandom(16)
        broker_key = self._derive_broker_key(broker_id, broker_salt)
        
        # Encrypt credentials with broker-specific key
        fernet = Fernet(broker_key)
        encrypted = fernet.encrypt(json.dumps(vars(credentials)).encode())
        
        # Store: broker_id -> {salt, encrypted_data}
        self._broker_keys[broker_id] = {
            "salt": broker_salt,
            "data": encrypted,
        }
    
    def retrieve(self, broker_id: str) -> BrokerCredentials:
        stored = self._broker_keys[broker_id]
        broker_key = self._derive_broker_key(broker_id, stored["salt"])
        fernet = Fernet(broker_key)
        decrypted = json.loads(fernet.decrypt(stored["data"]))
        return BrokerCredentials(**decrypted)
    
    def delete(self, broker_id: str):
        """Securely remove broker credentials."""
        if broker_id in self._broker_keys:
            # Overwrite memory before deleting
            self._broker_keys[broker_id] = None
            del self._broker_keys[broker_id]
```

### 7.4 Security Best Practices

1. **Never store API keys in environment variables** — use encrypted vault
2. **Rotate credentials** — support changing API keys without re-encrypting everything
3. **Audit logging** — log all credential access (who, when, which broker)
4. **Rate limiting** — prevent brute force on credential vault
5. **Session timeout** — auto-lock after inactivity
6. **Two-factor authentication** — for Alpha Stack account access
7. **IP whitelisting** — optionally restrict which IPs can access broker APIs

---

## 8. Implementation Roadmap

### Phase 1: Foundation (Weeks 1-3)
- [ ] Define `BrokerConnector` interface
- [ ] Implement `MT5Connector` (migrate current FXPesa integration)
- [ ] Implement `CCXTConnector` (Binance first)
- [ ] Build `BrokerConnectorRegistry`
- [ ] Basic credential vault

### Phase 2: Unified Layer (Weeks 4-6)
- [ ] `PortfolioAggregator` — unified balance and position view
- [ ] `UnifiedOrderManager` — order tracking across brokers
- [ ] `SymbolRouter` — search and route to correct broker
- [ ] Basic cross-broker risk checks

### Phase 3: Smart Routing (Weeks 7-9)
- [ ] `SmartOrderRouter` — best execution logic
- [ ] `FailoverRouter` — automatic failover
- [ ] `ArbitrageDetector` — cross-broker arbitrage alerts
- [ ] Performance monitoring and latency tracking

### Phase 4: Advanced (Weeks 10-12)
- [ ] REST API connector (OANDA, IG Markets)
- [ ] FIX protocol connector (institutional)
- [ ] Split order execution across brokers
- [ ] Advanced risk management (correlation, VaR)

### Phase 5: Polish (Weeks 13-14)
- [ ] UI for broker connection management
- [ ] Unified dashboard
- [ ] Credential rotation
- [ ] Documentation and onboarding flow

---

## 9. Technology Stack Recommendations

### Core
- **Language:** Python 3.11+ (async/await for concurrent broker connections)
- **Async Framework:** `asyncio` + `aiohttp` for HTTP, `websockets` for WS
- **Event Bus:** `asyncio.Queue` or Redis Streams for inter-component messaging

### Broker Libraries
| Broker Type | Library | Notes |
|-------------|---------|-------|
| MT5 | `MetaTrader5` (Python) | Official MT5 Python package |
| Crypto | `ccxt` / `ccxt.async_support` | 104+ exchanges, unified API |
| OANDA | `aiohttp` + OANDA v20 REST | Custom REST connector |
| FIX | `quickfix` / `simplesonfix` | FIX 4.4/5.0 engine |

### Security
- **Encryption:** `cryptography` (Fernet/AES-256)
- **Key Derivation:** PBKDF2 or Argon2 (via `argon2-cffi`)
- **Secrets Management:** Encrypted SQLite or Vault (HashiCorp)

### Data
- **Primary DB:** PostgreSQL (positions, orders, audit log)
- **Cache:** Redis (real-time prices, session state)
- **Time Series:** TimescaleDB or InfluxDB (OHLCV, tick data)

### Deployment
- **Containerization:** Docker + Docker Compose
- **Orchestration:** Kubernetes (for scaling connector workers)
- **Monitoring:** Prometheus + Grafana

---

## 10. Key Design Decisions

| Decision | Recommendation | Rationale |
|----------|---------------|-----------|
| Language | Python | Best ecosystem for trading (ccxt, MT5, ta-lib) |
| Async model | asyncio | Handle multiple broker connections concurrently |
| Crypto library | CCXT | Industry standard, 104+ exchanges, actively maintained |
| Order model | Unified (normalized) | Single order type regardless of broker |
| Position storage | PostgreSQL | Relational data, ACID transactions |
| Real-time data | WebSocket per broker | Lowest latency for price feeds |
| Credential storage | Encrypted per-user vault | Security isolation between brokers |
| Risk engine | Centralized | Single point of truth for cross-broker risk |

---

## Appendix A: Symbol Normalization

Different brokers use different symbol formats:

| Asset | MT5 | CCXT (Binance) | OANDA | Normalized |
|-------|-----|----------------|-------|------------|
| Euro/Dollar | EURUSD | EUR/USDT | EUR_USD | EUR/USD |
| Bitcoin | N/A | BTC/USDT | BTC/USD | BTC/USD |
| Gold | XAUUSD | — | XAU_USD | XAU/USD |
| S&P 500 | SP500 | — | SPX500_USD | SPX500 |

**Solution:** A symbol normalization layer that maps between formats:

```python
class SymbolNormalizer:
    """Maps between normalized symbols and broker-specific formats."""
    
    MAPPINGS = {
        "EUR/USD": {
            "mt5": "EURUSD",
            "binance": None,  # Not available
            "oanda": "EUR_USD",
        },
        "BTC/USD": {
            "mt5": None,  # Not available on most MT5
            "binance": "BTC/USDT",
            "oanda": "BTC_USD",
        },
    }
    
    def to_broker_symbol(self, normalized: str, broker_type: str) -> Optional[str]:
        return self.MAPPINGS.get(normalized, {}).get(broker_type)
    
    def from_broker_symbol(self, broker_symbol: str, broker_type: str) -> Optional[str]:
        for normalized, mappings in self.MAPPINGS.items():
            if mappings.get(broker_type) == broker_symbol:
                return normalized
        return None
```

---

## Appendix B: Error Handling Strategy

```python
class BrokerError(Exception):
    """Base error for broker operations."""
    def __init__(self, broker_id: str, message: str, recoverable: bool = True):
        self.broker_id = broker_id
        self.recoverable = recoverable
        super().__init__(f"[{broker_id}] {message}")

class ConnectionLostError(BrokerError):
    """Broker connection dropped."""
    pass

class InsufficientFundsError(BrokerError):
    """Not enough margin/balance."""
    recoverable = False

class SymbolNotFoundError(BrokerError):
    """Symbol not available on this broker."""
    recoverable = False

class RateLimitError(BrokerError):
    """Broker rate limit hit."""
    pass

# Error handling strategy:
# 1. ConnectionLost → auto-reconnect, failover to alternatives
# 2. InsufficientFunds → reject order, notify user
# 3. SymbolNotFound → try alternative broker
# 4. RateLimit → backoff and retry, or route to alternative
# 5. Unknown → log, alert, fail gracefully
```

---

## Appendix C: Performance Considerations

1. **Connection Pooling:** Maintain persistent connections to all brokers. Don't reconnect per-request.
2. **Concurrent Execution:** Use `asyncio.gather()` to query all brokers simultaneously.
3. **Caching:** Cache symbol lists, account info (refresh every 5 min). Don't cache prices.
4. **Circuit Breaker:** If a broker fails N times in M minutes, mark as unhealthy and stop routing there.
5. **Rate Limit Awareness:** Track each broker's rate limits and throttle accordingly.

```python
class CircuitBreaker:
    """Prevent cascading failures from a single broker."""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self._failures: dict[str, int] = {}
        self._tripped: dict[str, float] = {}
        self._threshold = failure_threshold
        self._recovery = recovery_timeout
    
    def record_failure(self, broker_id: str):
        self._failures[broker_id] = self._failures.get(broker_id, 0) + 1
        if self._failures[broker_id] >= self._threshold:
            self._tripped[broker_id] = time.time()
    
    def is_available(self, broker_id: str) -> bool:
        if broker_id in self._tripped:
            if time.time() - self._tripped[broker_id] > self._recovery:
                del self._tripped[broker_id]
                self._failures[broker_id] = 0
                return True
            return False
        return True
```

---

*This research provides the architectural foundation for transforming Alpha Stack from a single-broker system into a hybrid multi-broker platform. The key insight: treat each broker as a plugin implementing a standard interface, build a unified layer on top, and let the smart router handle the complexity.*
