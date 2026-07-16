# Forex & MetaTrader 5 Integration for AlphaStack

**Research Report** — July 2026  
**Status:** Architecture & Implementation Plan

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current Architecture Analysis](#2-current-architecture-analysis)
3. [MetaTrader 5 (MT5) Integration](#3-metatrader-5-mt5-integration)
4. [Forex-Specific Features](#4-forex-specific-features)
5. [Alternative Forex Platforms](#5-alternative-forex-platforms)
6. [Multi-Broker Architecture](#6-multi-broker-architecture)
7. [Implementation Plan](#7-implementation-plan)
8. [Code Examples](#8-code-examples)
9. [Risk Considerations](#9-risk-considerations)
10. [Recommendations](#10-recommendations)

---

## 1. Executive Summary

AlphaStack currently trades crypto via Binance through the `ccxt` library. The existing broker architecture is **well-designed for multi-broker expansion** — it has:

- An abstract `BrokerConnector` base class with unified async interface
- A `BrokerRegistry` for registering and routing across brokers
- A `SmartRouter` with cost/fill/latency/reliability scoring
- Placeholder `MT5Connector` and `MQL5Bridge` files already scaffolded

**Key findings:**

| Topic | Recommendation |
|-------|---------------|
| **First broker to add** | OANDA v20 API (pure REST, best Python support, no Windows dependency) |
| **MT5 approach** | MQL5 Bridge via ZeroMQ (avoids Wine/Linux complexity) |
| **Architecture** | Extend existing `BrokerConnector` ABC — it already fits perfectly |
| **Biggest risk** | MT5 Python package is Windows-only; requires VPS or Docker+Wine |
| **Biggest opportunity** | Unified risk management across crypto + forex capital |

---

## 2. Current Architecture Analysis

### 2.1 Existing Components

```
src/alphastack/brokers/
├── base.py              # BrokerConnector ABC — async, retry, state machine
├── models.py            # BrokerOrder, BrokerPosition, BrokerBalance, BrokerTick, BrokerBar
├── registry.py          # BrokerRegistry — register, route, failover
├── smart_router.py      # SmartRouter — cost/fill/latency/reliability scoring
├── order_manager.py     # OrderManager — lifecycle tracking, persistence hooks
├── ccxt_connector.py    # CCXTConnector — crypto exchanges (Binance, Bybit, etc.)
├── mt5_connector.py     # MT5Connector — scaffolded, needs refinement
└── mql5_bridge.py       # MQL5Bridge — ZeroMQ bridge, partially implemented
```

### 2.2 Assessment of Existing MT5 Code

**`mt5_connector.py` — Status: ~80% complete**

Strengths:
- Correct async thread-pool pattern (MT5 Python lib is synchronous)
- Proper order type mapping (buy/sell → limit/stop/stop-limit)
- Account info, positions, bars, ticks all implemented
- Good Linux deployment notes at bottom

Gaps to address:
- No `swap`/rollover tracking on positions
- Spread conversion uses hardcoded `1e-5` — should be dynamic per symbol
- Missing `get_account_leverage()` helper
- No historical trade/deal retrieval
- Missing symbol info helpers (pip size, contract size, min/max lot)

**`mql5_bridge.py` — Status: ~60% complete**

Strengths:
- ZeroMQ PAIR socket pattern is correct for EA ↔ Python
- Heartbeat management implemented
- Signal/action enum covers all trade types
- Position and account info dataclasses defined

Gaps to address:
- No error handling for malformed JSON from EA
- Missing reconnection logic on socket disconnect
- No message sequence numbers (ordering guarantees)
- Position sync is pull-only; should also push on trade events
- Missing MQL5 EA source code (the bridge needs an Expert Advisor on the MT5 side)

---

## 3. MetaTrader 5 (MT5) Integration

### 3.1 The `MetaTrader5` Python Package

The official `MetaTrader5` package (`pip install MetaTrader5`) provides:

| Function | Description |
|----------|-------------|
| `mt5.initialize()` | Connect to MT5 terminal |
| `mt5.login()` | Authenticate with broker server |
| `mt5.order_send()` | Submit market/pending orders |
| `mt5.order_get()` | Get pending order details |
| `mt5.orders_get()` | Get all pending orders |
| `mt5.position_get()` | Get open positions |
| `mt5.positions_get()` | Get all open positions |
| `mt5.account_info()` | Get account balance, equity, margin |
| `mt5.symbol_info()` | Get symbol properties (pip size, lot size, etc.) |
| `mt5.symbol_info_tick()` | Get latest bid/ask/last |
| `mt5.copy_rates_from_pos()` | Get historical OHLCV bars |
| `mt5.copy_rates_from_time()` | Get bars from time range |
| `mt5.copy_ticks_from()` | Get tick history |
| `mt5.history_deals_get()` | Get trade history |
| `mt5.history_orders_get()` | Get order history |
| `mt5.shutdown()` | Disconnect |

### 3.2 Connection Flow

```python
import MetaTrader5 as mt5

# 1. Initialize (connects to terminal)
if not mt5.initialize(path=r"C:\Program Files\MetaTrader 5\terminal64.exe"):
    print(f"Init failed: {mt5.last_error()}")
    quit()

# 2. Login to broker
if not mt5.login(12345678, password="xxx", server="Broker-Live"):
    print(f"Login failed: {mt5.last_error()}")
    mt5.shutdown()
    quit()

# 3. Verify
info = mt5.account_info()
print(f"Balance: {info.balance}, Equity: {info.equity}")

# 4. Cleanup
mt5.shutdown()
```

### 3.3 Order Types in MT5

| MT5 Constant | Value | AlphaStack `OrderType` | Description |
|-------------|-------|----------------------|-------------|
| `ORDER_TYPE_BUY` | 0 | MARKET + BUY | Market buy |
| `ORDER_TYPE_SELL` | 1 | MARKET + SELL | Market sell |
| `ORDER_TYPE_BUY_LIMIT` | 2 | LIMIT + BUY | Buy limit |
| `ORDER_TYPE_SELL_LIMIT` | 3 | LIMIT + SELL | Sell limit |
| `ORDER_TYPE_BUY_STOP` | 4 | STOP + BUY | Buy stop |
| `ORDER_TYPE_SELL_STOP` | 5 | STOP + SELL | Sell stop |
| `ORDER_TYPE_BUY_STOP_LIMIT` | 6 | STOP_LIMIT + BUY | Buy stop-limit |
| `ORDER_TYPE_SELL_STOP_LIMIT` | 7 | STOP_LIMIT + SELL | Sell stop-limit |

### 3.4 Order Request Structure

```python
request = {
    "action": mt5.TRADE_ACTION_DEAL,       # Market order
    # or mt5.TRADE_ACTION_PENDING           # Pending order
    # or mt5.TRADE_ACTION_MODIFY            # Modify order
    # or mt5.TRADE_ACTION_REMOVE            # Delete pending order
    "symbol": "EURUSD",
    "volume": 0.1,                          # Lots
    "type": mt5.ORDER_TYPE_BUY,
    "price": mt5.symbol_info_tick("EURUSD").ask,
    "sl": 1.0850,                           # Stop loss
    "tp": 1.0950,                           # Take profit
    "deviation": 10,                        # Max slippage in points
    "magic": 20260713,                      # EA identifier
    "comment": "AlphaStack",
    "type_time": mt5.ORDER_TIME_GTC,
    "type_filling": mt5.ORDER_FILLING_IOC,
}

result = mt5.order_send(request)
# result.retcode == 10009 means success (TRADE_RETCODE_DONE)
```

### 3.5 Position Management

```python
# Get all positions
positions = mt5.positions_get()
for pos in positions:
    print(f"{pos.symbol} {pos.type} {pos.volume} @ {pos.price_open} P/L: {pos.profit}")

# Modify position SL/TP
request = {
    "action": mt5.TRADE_ACTION_SLTP,
    "symbol": "EURUSD",
    "position": ticket,
    "sl": new_sl,
    "tp": new_tp,
}
result = mt5.order_send(request)

# Close position
request = {
    "action": mt5.TRADE_ACTION_DEAL,
    "symbol": "EURUSD",
    "volume": pos.volume,
    "type": mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY,
    "position": ticket,
    "price": mt5.symbol_info_tick("EURUSD").bid,
    "deviation": 10,
    "magic": 20260713,
    "comment": "Close",
    "type_filling": mt5.ORDER_FILLING_IOC,
}
result = mt5.order_send(request)
```

### 3.6 Historical Data

```python
# Get last 1000 H1 bars
rates = mt5.copy_rates_from_pos("EURUSD", mt5.TIMEFRAME_H1, 0, 1000)
# Returns numpy array with fields: time, open, high, low, close, tick_volume, spread, real_volume

# Get bars from time range
from datetime import datetime
utc_from = datetime(2025, 1, 1)
utc_to = datetime(2025, 12, 31)
rates = mt5.copy_rates_from_range("EURUSD", mt5.TIMEFRAME_D1, utc_from, utc_to)

# Get tick history
ticks = mt5.copy_ticks_from("EURUSD", utc_from, 1000, mt5.COPY_TICKS_ALL)
```

### 3.7 Real-Time Price Streaming

MT5 Python package does **not** provide native WebSocket/streaming. Options:

1. **Polling** — Call `symbol_info_tick()` in a loop (simplest, ~100ms latency)
2. **MQL5 EA push** — EA monitors `OnTick()` and pushes via ZeroMQ (recommended)
3. **Windows API hooks** — Use `mt5.market_book_get()` for depth of market

The MQL5 Bridge approach (already scaffolded in `mql5_bridge.py`) is the recommended path for real-time streaming.

### 3.8 MT5 Deployment on Linux

The `MetaTrader5` Python package is **Windows-only**. Three deployment strategies:

| Strategy | Pros | Cons | Latency |
|----------|------|------|---------|
| **Windows VPS** | Native, reliable, full MT5 features | Monthly cost ($10-30/mo), separate server | Low (VPS near broker) |
| **Docker + Wine** | Single server, no extra cost | Unstable, Wine compatibility issues, no GUI | Medium |
| **MQL5 Bridge** | Best of both — EA runs natively on Windows, Python runs on Linux | Requires Windows for EA side, more complex setup | Low (ZeroMQ) |

**Recommendation:** Use a small Windows VPS running MT5 + the MQL5 EA, with AlphaStack on Linux connecting via ZeroMQ. The `MQL5Bridge` class already implements this pattern.

### 3.9 MT5 ↔ MT4 Compatibility

| Feature | MT4 | MT5 |
|---------|-----|-----|
| Python package | ❌ None official | ✅ `MetaTrader5` |
| Hedging | ✅ Yes | ✅ Yes (since 2016) |
| Netting | ❌ No | ✅ Yes |
| Timeframes | 9 | 21 |
| Order types | 4 (market, limit, stop) | 6 (+ stop-limit) |
| Market depth | ❌ No | ✅ Yes |
| Multi-asset | Forex/CFD only | Forex, stocks, futures, options |
| MQL version | MQL4 | MQL5 (not compatible) |

**Key insight:** MT5 is the clear choice. MT4 is legacy and declining. Most brokers now support MT5. The Python package only exists for MT5.

---

## 4. Forex-Specific Features

### 4.1 Currency Pair Conventions

```
EUR/USD = 1.0850
│    │
│    └── Quote currency (price currency) — how much of this to buy 1 unit of base
└── Base currency — the unit being traded
```

**Major pairs** (most liquid, tightest spreads):
- EUR/USD, USD/JPY, GBP/USD, USD/CHF, AUD/USD, USD/CAD, NZD/USD

**Minor pairs** (crosses, no USD):
- EUR/GBP, EUR/JPY, GBP/JPY, AUD/JPY, EUR/AUD, etc.

**Exotic pairs** (one emerging market currency):
- USD/TRY, USD/ZAR, USD/MXN, EUR/PLN, etc.

### 4.2 Pip Calculation

A **pip** is the smallest standard price movement:

| Pair Type | Pip Location | Example | Pip Value |
|-----------|-------------|---------|-----------|
| Most pairs (EUR/USD, GBP/USD) | 4th decimal | 1.0850 → 1.0851 = 1 pip | 0.0001 |
| JPY pairs (USD/JPY, EUR/JPY) | 2nd decimal | 149.50 → 149.51 = 1 pip | 0.01 |
| Some brokers | 5th decimal | 1.08500 → 1.08501 = 0.1 pip (pipette) | 0.00001 |

**Pip value per lot:**
```
For pairs where USD is the quote currency (e.g., EUR/USD):
  Pip value = 0.0001 × 100,000 = $10 per standard lot

For pairs where USD is the base currency (e.g., USD/JPY):
  Pip value = 0.01 × 100,000 / current_price
  At USD/JPY = 150.00: pip value = 0.01 × 100,000 / 150 = $6.67

For crosses (e.g., EUR/GBP):
  Pip value = 0.0001 × 100,000 × GBP/USD rate
```

### 4.3 Lot Sizes

| Lot Type | Units | Pip Value (EUR/USD) | Typical Margin (1:100) |
|----------|-------|--------------------|-----------------------|
| Standard | 100,000 | $10.00 | $1,000 |
| Mini | 10,000 | $1.00 | $100 |
| Micro | 1,000 | $0.10 | $10 |
| Nano | 100 | $0.01 | $1 |

Most MT5 brokers allow fractional lots (e.g., 0.01 = micro lot).

### 4.4 Spread Handling

Spread is the broker's cost — the difference between bid and ask:

```
EUR/USD: Bid = 1.08500, Ask = 1.08515 → Spread = 1.5 pips
```

**Spread types:**
- **Fixed** — Broker guarantees a constant spread (less common now)
- **Variable/Floating** — Spread changes with liquidity (most common)
- **Raw/ECN** — Near-zero spread + commission per trade

**Impact on trading:**
```python
# Spread cost for a trade
spread_cost_pips = ask - bid  # in pips
spread_cost_usd = spread_cost_pips * pip_value_per_lot * lots

# Example: 1.5 pip spread on 1 standard lot EUR/USD
# = 1.5 × $10 × 1 = $15 per round trip
```

### 4.5 Swap/Rollover Rates

When holding a position past the daily close (typically 5:00 PM EST), a swap fee is charged/credited based on the interest rate differential:

```
If you BUY EUR/USD:
  You earn EUR interest, pay USD interest
  If EUR rate > USD rate → positive swap (you earn)
  If EUR rate < USD rate → negative swap (you pay)

Wednesday is triple swap day (accounts for weekend)
```

**Implementation consideration:** The MT5 connector should track swap on positions:
```python
# MT5 position has swap field
pos.swap  # accumulated swap in account currency
```

### 4.6 Margin and Leverage

```
Required margin = (lot_size × contract_size × price) / leverage

Example: Buy 1 lot EUR/USD at 1.0850 with 1:100 leverage
Margin = (1 × 100,000 × 1.0850) / 100 = $1,085

Margin level = (equity / used_margin) × 100%
If margin level < 100% → margin call
If margin level < 50% (varies) → stop-out / auto-close
```

**Leverage by region:**
| Region | Max Leverage (Major Pairs) |
|--------|---------------------------|
| EU/UK (ESMA) | 1:30 |
| Australia (ASIC) | 1:30 |
| US (NFA/CFTC) | 1:50 |
| Offshore | 1:500 to 1:3000 |

### 4.7 Trading Session Times (UTC)

| Session | Opens (UTC) | Closes (UTC) | Best Pairs |
|---------|-------------|-------------|------------|
| Sydney | 22:00 | 07:00 | AUD/USD, NZD/USD |
| Tokyo | 00:00 | 09:00 | USD/JPY, EUR/JPY, AUD/JPY |
| London | 07:00 | 16:00 | EUR/USD, GBP/USD, EUR/GBP |
| New York | 12:00 | 21:00 | EUR/USD, GBP/USD, USD/CAD |

**Key overlaps (highest volatility):**
- London + Tokyo: 07:00–09:00 UTC
- London + New York: 12:00–16:00 UTC ← **Most liquid period**

---

## 5. Alternative Forex Platforms

### 5.1 Comparison Table

| Feature | MT5 | OANDA v20 | IBKR TWS | cTrader | FXCM | LMAX |
|---------|-----|-----------|----------|---------|------|------|
| **Python Support** | Official pkg (Win-only) | `oandapyV20` / REST | `ib_insync` / native | Protobuf + REST | `fxcmpy` | FIX API |
| **Async/Native** | ❌ Sync (needs thread pool) | ✅ REST (easy async) | ✅ Async via `ib_insync` | ✅ WebSocket | ✅ REST | ✅ FIX |
| **Linux Native** | ❌ Windows-only | ✅ Pure REST | ✅ TWS Gateway | ✅ REST + WS | ✅ Pure REST | ✅ FIX |
| **API Quality** | ⭐⭐⭐⭐ Good | ⭐⭐⭐⭐⭐ Excellent | ⭐⭐⭐ Complex | ⭐⭐⭐⭐ Good | ⭐⭐⭐ OK | ⭐⭐⭐⭐ Good |
| **Min Deposit** | Varies by broker | $0 | $0 | Varies | $50 | $10,000 |
| **Commission** | Spread-based | Spread-only | $2-6/million | Spread or commission | Spread-based | $3.50/million |
| **Typical Spread (EUR/USD)** | 0.5-1.5 pips | 1.0-1.3 pips | 0.1-0.2 pips + comm | 0.3-0.8 pips | 1.2-1.5 pips | 0.1-0.3 pips + comm |
| **Instruments** | Forex, stocks, futures, CFDs | Forex, CFDs | Everything | Forex, CFDs | Forex, CFDs | Forex, metals |
| **Hedging** | ✅ | ❌ (netting only) | ✅ | ✅ | ✅ | ✅ |
| **Paper Trading** | ✅ Demo | ✅ Demo | ✅ Paper | ✅ Demo | ✅ Demo | ✅ Demo |
| **Regulation** | Via broker | FCA, ASIC, NFA, IIROC | SEC, FCA, ASIC | Via broker | FCA, ASIC | FCA |
| **Best For** | MT5 EAs, multi-asset | REST simplicity, US traders | Multi-asset, institutions | Modern UI, algo traders | Beginners | Institutional, ECN |

### 5.2 Detailed Platform Analysis

#### OANDA v20 API — ⭐ Recommended First Integration

**Why:**
- Pure REST API — no platform software needed, works natively on Linux
- Excellent Python library (`oandapyV20`) and documentation
- Zero installation — just HTTP requests with API key
- Supports streaming for real-time prices via HTTP chunked responses
- Good for US traders (NFA regulated, FIFO compliant)
- Account granularity — can trade fractional lots (1 unit = 0.00001 lot)

**API Structure:**
```python
# OANDA v20 uses accounts/{accountID}/ endpoints
# Pricing: GET /v3/accounts/{id}/pricing?instruments=EUR_USD
# Orders: POST /v3/accounts/{id}/orders
# Trades: GET /v3/accounts/{id}/trades
# Positions: GET /v3/accounts/{id}/positions
# Streaming: GET /v3/accounts/{id}/pricing/stream?instruments=EUR_USD
```

**Limitations:**
- Netting only (no hedging) — one position per instrument
- Spread-only pricing (no raw spread + commission option)
- Limited to forex and CFDs

#### Interactive Brokers (IBKR) — ⭐ Best for Multi-Asset

**Why:**
- Trade literally everything: forex, stocks, options, futures, bonds, crypto
- Very tight forex spreads (ECN pricing)
- `ib_insync` library makes the complex API manageable
- Professional-grade infrastructure

**Complexity:**
- TWS/Gateway must run (Java application)
- API is complex — contracts, orders, and executions have steep learning curve
- Connection management is tricky (heartbeats, disconnections)

**Best for:** If AlphaStack wants to expand beyond forex into equities/futures.

#### cTrader — ⭐ Modern Platform

**Why:**
- Open API with Protocol Buffers (protobuf) and REST
- Modern architecture, designed for algo trading
- Multiple brokers offer cTrader (IC Markets, Pepperstone, etc.)
- cAlgo for C# bots, Open API for Python

**API Access:**
- REST API for account/order management
- WebSocket for real-time streaming
- FIX API for institutional-grade connectivity

#### FXCM — Simple but Limited

- `fxcmpy` Python library wraps the REST API
- Simple API, easy to get started
- Limited instrument selection
- Smaller community

#### LMAX — Institutional Grade

- FIX protocol (industry standard for institutional trading)
- Very tight spreads, true ECN
- $10,000 minimum deposit
- Best execution quality
- Requires FIX protocol knowledge

### 5.3 Integration Effort Estimate

| Platform | Connector Complexity | Time Estimate | Dependencies |
|----------|---------------------|---------------|-------------|
| **OANDA** | Low | 2-3 days | `oandapyV20` or `requests` |
| **MT5 (Bridge)** | Medium | 1-2 weeks | MQL5 EA + ZeroMQ |
| **MT5 (Direct)** | Medium | 3-5 days | `MetaTrader5` (Windows) |
| **IBKR** | High | 2-3 weeks | `ib_insync` + TWS Gateway |
| **cTrader** | Medium | 1-2 weeks | `protobuf` + REST client |
| **FXCM** | Low | 2-3 days | `fxcmpy` |
| **LMAX** | High | 2-3 weeks | FIX engine (e.g. `quickfix`) |

---

## 6. Multi-Broker Architecture

### 6.1 Target Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Strategy Layer                         │
│         (signals, risk decisions, portfolio)              │
└──────────────┬──────────────────────────┬────────────────┘
               │                          │
       ┌───────▼────────┐        ┌────────▼───────┐
       │   OrderManager  │        │  RiskManager   │
       │  (lifecycle +   │        │  (cross-broker │
       │   persistence)  │        │   exposure)    │
       └───────┬─────────┘        └────────┬───────┘
               │                           │
       ┌───────▼───────────────────────────▼───────┐
       │              SmartRouter                    │
       │  (cost/fill/latency/reliability scoring)    │
       └───────┬──────────┬──────────┬──────────────┘
               │          │          │
       ┌───────▼──┐ ┌─────▼────┐ ┌──▼──────────┐
       │ CCXT      │ │ OANDA    │ │ MT5/MQL5    │
       │ Connector │ │ Connector│ │ Connector    │
       │ (crypto)  │ │ (forex)  │ │ (forex/CFD) │
       └───────────┘ └──────────┘ └──────────────┘
```

### 6.2 Unified Order Interface

The existing `BrokerOrder` model in `models.py` already handles cross-broker unification well. Additions needed for forex:

```python
# New fields to add to BrokerOrder:
class BrokerOrder(BaseModel):
    # ... existing fields ...
    lot_size: float | None = None           # Forex-specific: 0.01, 0.1, 1.0
    pip_value: float | None = None          # Calculated pip value for this trade
    spread_at_entry: float | None = None    # Spread when order was placed
    swap_rate: float | None = None          # Expected daily swap
    margin_required: float | None = None    # Margin for this order
```

### 6.3 Symbol Normalization

Different brokers use different symbol formats:

| Broker | EUR/USD | GBP/JPY | Gold |
|--------|---------|---------|------|
| MT5 | `EURUSD` | `GBPJPY` | `XAUUSD` |
| OANDA | `EUR_USD` | `GBP_JPY` | `XAU_USD` |
| IBKR | `EUR.USD` (Cash) | `GBP.JPY` | `XAUUSD` |
| CCXT | `EUR/USD` | `GBP/JPY` | `XAU/USDT` |

**Solution:** Create a `SymbolNormalizer` class:

```python
class SymbolNormalizer:
    """Convert between AlphaStack canonical symbols and broker-specific formats."""
    
    # Canonical format: "EUR/USD" (ISO 4217 with slash)
    _CANONICAL_TO_BROKER = {
        "mt5": lambda s: s.replace("/", ""),           # EURUSD
        "oanda": lambda s: s.replace("/", "_"),        # EUR_USD
        "ibkr": lambda s: s.replace("/", "."),         # EUR.USD
        "ccxt": lambda s: s,                           # EUR/USD (already canonical)
    }
    
    _BROKER_TO_CANONICAL = {
        "mt5": lambda s: f"{s[:3]}/{s[3:]}" if len(s) == 6 else s,
        "oanda": lambda s: s.replace("_", "/"),
        "ibkr": lambda s: s.replace(".", "/"),
        "ccxt": lambda s: s,
    }
    
    @classmethod
    def to_broker(cls, symbol: str, broker: str) -> str:
        converter = cls._CANONICAL_TO_BROKER.get(broker, lambda s: s)
        return converter(symbol)
    
    @classmethod
    def to_canonical(cls, symbol: str, broker: str) -> str:
        converter = cls._BROKER_TO_CANONICAL.get(broker, lambda s: s)
        return converter(symbol)
```

### 6.4 Forex-Specific Helper Module

```python
# src/alphastack/brokers/forex_utils.py

from dataclasses import dataclass
from enum import Enum

class PairType(str, Enum):
    MAJOR = "major"       # EUR/USD, USD/JPY, etc.
    MINOR = "minor"       # EUR/GBP, AUD/JPY, etc.
    EXOTIC = "exotic"     # USD/TRY, EUR/PLN, etc.
    METAL = "metal"       # XAU/USD, XAG/USD
    INDEX = "index"       # US30, SPX500

@dataclass
class ForexSymbol:
    """Forex symbol metadata."""
    base: str                    # "EUR"
    quote: str                   # "USD"
    pair_type: PairType
    pip_digits: int              # 4 for most, 2 for JPY
    pipette_digits: int          # 5 for most, 3 for JPY
    contract_size: float         # 100000 for standard lot
    min_lot: float               # 0.01 typically
    max_lot: float               # 100 typically
    lot_step: float              # 0.01 typically
    
    @property
    def pip_size(self) -> float:
        return 10 ** -self.pip_digits
    
    def pips_between(self, price1: float, price2: float) -> float:
        return abs(price1 - price2) / self.pip_size
    
    def pip_value_per_lot(self, account_currency: str = "USD") -> float:
        """Calculate pip value per standard lot in account currency."""
        if self.quote == account_currency:
            return self.pip_size * self.contract_size
        # Cross-rate calculation needed — fetch from market data
        raise NotImplementedError("Cross-currency pip value requires live rates")

# Pre-defined symbol specs
FOREX_SYMBOLS: dict[str, ForexSymbol] = {
    "EUR/USD": ForexSymbol("EUR", "USD", PairType.MAJOR, 4, 5, 100000, 0.01, 100, 0.01),
    "GBP/USD": ForexSymbol("GBP", "USD", PairType.MAJOR, 4, 5, 100000, 0.01, 100, 0.01),
    "USD/JPY": ForexSymbol("USD", "JPY", PairType.MAJOR, 2, 3, 100000, 0.01, 100, 0.01),
    "USD/CHF": ForexSymbol("USD", "CHF", PairType.MAJOR, 4, 5, 100000, 0.01, 100, 0.01),
    "AUD/USD": ForexSymbol("AUD", "USD", PairType.MAJOR, 4, 5, 100000, 0.01, 100, 0.01),
    "USD/CAD": ForexSymbol("USD", "CAD", PairType.MAJOR, 4, 5, 100000, 0.01, 100, 0.01),
    "NZD/USD": ForexSymbol("NZD", "USD", PairType.MAJOR, 4, 5, 100000, 0.01, 100, 0.01),
    "EUR/GBP": ForexSymbol("EUR", "GBP", PairType.MINOR, 4, 5, 100000, 0.01, 100, 0.01),
    "EUR/JPY": ForexSymbol("EUR", "JPY", PairType.MINOR, 2, 3, 100000, 0.01, 100, 0.01),
    "GBP/JPY": ForexSymbol("GBP", "JPY", PairType.MINOR, 2, 3, 100000, 0.01, 100, 0.01),
    "XAU/USD": ForexSymbol("XAU", "USD", PairType.METAL, 2, 3, 100, 0.01, 100, 0.01),
}
```

### 6.5 Cross-Broker Risk Management

```python
class CrossBrokerRiskManager:
    """Unified risk management across all brokers."""
    
    def __init__(self, registry: BrokerRegistry):
        self._registry = registry
    
    async def get_total_exposure(self) -> dict[str, float]:
        """Get aggregate exposure across all brokers by currency."""
        exposures: dict[str, float] = {}
        for name in self._registry.names:
            connector = self._registry.get(name)
            if connector and connector.is_connected:
                positions = await connector.get_positions()
                for pos in positions:
                    # Aggregate notional value by instrument
                    exposures[pos.symbol] = exposures.get(pos.symbol, 0) + pos.notional_value
        return exposures
    
    async def get_total_equity(self) -> float:
        """Get total equity across all brokers."""
        total = 0.0
        for name in self._registry.names:
            connector = self._registry.get(name)
            if connector and connector.is_connected:
                bal = await connector.get_balance()
                total += bal.equity  # TODO: currency conversion
        return total
    
    async def check_max_exposure(self, symbol: str, additional: float, max_pct: float = 0.2) -> bool:
        """Check if adding a position would exceed max exposure percentage."""
        total_equity = await self.get_total_equity()
        exposures = await self.get_total_exposure()
        current = exposures.get(symbol, 0)
        return (current + additional) / total_equity <= max_pct
```

---

## 7. Implementation Plan

### Phase 1: Foundation (Week 1-2)

**Goal:** Forex utility layer + OANDA connector

| Task | Priority | Effort |
|------|----------|--------|
| Create `forex_utils.py` (pip calc, lot sizes, symbol metadata) | 🔴 High | 1 day |
| Create `SymbolNormalizer` class | 🔴 High | 0.5 day |
| Add forex-specific fields to `BrokerOrder`/`BrokerPosition` models | 🔴 High | 0.5 day |
| Implement `OandaConnector` (REST, async) | 🔴 High | 2-3 days |
| Unit tests for forex utilities | 🟡 Medium | 1 day |
| Integration tests with OANDA demo account | 🟡 Medium | 1 day |

**Deliverable:** AlphaStack can trade forex via OANDA on a demo account.

### Phase 2: MT5 Bridge (Week 3-4)

**Goal:** MT5 connectivity via ZeroMQ bridge

| Task | Priority | Effort |
|------|----------|--------|
| Write MQL5 Expert Advisor (the MT5 side of the bridge) | 🔴 High | 2-3 days |
| Refine `mql5_bridge.py` (error handling, reconnection, sequencing) | 🔴 High | 1-2 days |
| Refine `mt5_connector.py` (spread handling, swap tracking, symbol info) | 🔴 High | 1-2 days |
| Deploy MT5 on Windows VPS | 🟡 Medium | 0.5 day |
| End-to-end testing with MT5 demo account | 🟡 Medium | 1 day |

**Deliverable:** AlphaStack can trade forex via MT5 through the ZeroMQ bridge.

### Phase 3: Multi-Broker Risk (Week 5-6)

**Goal:** Unified risk management across crypto + forex

| Task | Priority | Effort |
|------|----------|--------|
| Implement `CrossBrokerRiskManager` | 🔴 High | 2 days |
| Extend `SmartRouter` for forex-specific routing (spread cost, session times) | 🔴 High | 2 days |
| Add currency conversion for cross-broker equity calculation | 🟡 Medium | 1 day |
| Implement position aggregation across brokers | 🟡 Medium | 1 day |
| Add forex session awareness to routing (avoid illiquid periods) | 🟢 Low | 1 day |

**Deliverable:** AlphaStack manages risk holistically across crypto and forex.

### Phase 4: Advanced (Week 7+)

| Task | Priority | Effort |
|------|----------|--------|
| IBKR connector (if multi-asset expansion needed) | 🟡 Medium | 1-2 weeks |
| cTrader connector (if cTrader broker preferred) | 🟢 Low | 1 week |
| Cross-broker arbitrage detection | 🟢 Low | 1 week |
| Swap-aware position management (auto-close before triple swap) | 🟡 Medium | 2 days |
| Forex calendar integration (news events → widen stops) | 🟢 Low | 2 days |

---

## 8. Code Examples

### 8.1 OANDA Connector (Recommended First Implementation)

```python
"""OANDA v20 connector for AlphaStack."""

from __future__ import annotations

import asyncio
import datetime as dt
from typing import Any

import aiohttp
import structlog

from alphastack.brokers.base import BrokerConnector, ConnectionState
from alphastack.brokers.models import (
    BrokerBalance, BrokerBar, BrokerOrder, BrokerPosition, BrokerTick,
    OrderSide, OrderStatus, OrderType, PositionSide,
)

logger = structlog.get_logger(__name__)


class OandaConnector(BrokerConnector):
    """OANDA v20 REST API connector."""

    def __init__(
        self,
        *,
        account_id: str,
        access_token: str,
        environment: str = "practice",  # "practice" or "live"
    ) -> None:
        super().__init__("oanda", max_retries=3, retry_delay=1.0)
        self._account_id = account_id
        self._access_token = access_token
        if environment == "practice":
            self._base_url = "https://api-fxpractice.oanda.com"
            self._stream_url = "https://stream-fxpractice.oanda.com"
        else:
            self._base_url = "https://api-fxtrade.oanda.com"
            self._stream_url = "https://stream-fxtrade.oanda.com"
        self._session: aiohttp.ClientSession | None = None

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        url = f"{self._base_url}{path}"
        async with self._session.request(method, url, headers=self._headers, **kwargs) as resp:
            if resp.status >= 400:
                body = await resp.text()
                raise RuntimeError(f"OANDA API error {resp.status}: {body}")
            return await resp.json()

    async def connect(self) -> None:
        self._transition(ConnectionState.CONNECTING)
        self._session = aiohttp.ClientSession()
        # Verify connection
        await self._request("GET", f"/v3/accounts/{self._account_id}/summary")
        self._transition(ConnectionState.CONNECTED)
        logger.info("oanda_connected", account=self._account_id)

    async def disconnect(self) -> None:
        if self._session:
            await self._session.close()
        self._transition(ConnectionState.DISCONNECTED)

    async def place_order(self, order: BrokerOrder) -> BrokerOrder:
        # OANDA uses instrument format "EUR_USD"
        instrument = order.symbol.replace("/", "_")
        
        body: dict[str, Any] = {
            "order": {
                "type": "MARKET" if order.order_type == OrderType.MARKET else "LIMIT",
                "instrument": instrument,
                "units": str(order.quantity if order.side == OrderSide.BUY else -order.quantity),
                "timeInForce": "FOK" if order.order_type == OrderType.MARKET else "GTC",
            }
        }
        
        if order.price and order.order_type != OrderType.MARKET:
            body["order"]["price"] = str(order.price)
        
        # OANDA v20 uses "stopLossOnFill" and "takeProfitOnFill" for SL/TP at order time
        if order.stop_loss:
            body["order"]["stopLossOnFill"] = {"price": str(order.stop_loss)}
        if order.take_profit:
            body["order"]["takeProfitOnFill"] = {"price": str(order.take_profit)}
        
        result = await self._request(
            "POST",
            f"/v3/accounts/{self._account_id}/orders",
            json=body,
        )
        
        # Parse response
        order_create = result.get("orderCreateTransaction", {})
        order_fill = result.get("orderFillTransaction", {})
        
        if order_fill:
            order.broker_order_id = order_fill.get("tradeOpened", {}).get("tradeID", "")
            order.status = OrderStatus.FILLED
            order.avg_fill_price = float(order_fill.get("price", 0))
            order.filled_quantity = abs(float(order_fill.get("units", 0)))
            order.commission = float(order_fill.get("commission", 0))
        elif order_create:
            order.broker_order_id = order_create.get("id", "")
            order.status = OrderStatus.OPEN
        
        order.raw = result
        order.updated_at = dt.datetime.now(dt.timezone.utc)
        return order

    async def cancel_order(self, order_id: str) -> BrokerOrder:
        await self._request(
            "PUT",
            f"/v3/accounts/{self._account_id}/orders/{order_id}/cancel",
        )
        return BrokerOrder(broker_order_id=order_id, broker="oanda", status=OrderStatus.CANCELLED)

    async def modify_order(self, order_id: str, **kwargs) -> BrokerOrder:
        body: dict[str, Any] = {"order": {}}
        if kwargs.get("price"):
            body["order"]["price"] = str(kwargs["price"])
        if kwargs.get("stop_loss"):
            body["order"]["stopLossOnFill"] = {"price": str(kwargs["stop_loss"])}
        if kwargs.get("take_profit"):
            body["order"]["takeProfitOnFill"] = {"price": str(kwargs["take_profit"])}
        
        await self._request(
            "PUT",
            f"/v3/accounts/{self._account_id}/orders/{order_id}",
            json=body,
        )
        return BrokerOrder(broker_order_id=order_id, broker="oanda", status=OrderStatus.OPEN)

    async def get_positions(self) -> list[BrokerPosition]:
        result = await self._request("GET", f"/v3/accounts/{self._account_id}/openPositions")
        positions = []
        for p in result.get("positions", []):
            long = p.get("long", {})
            short = p.get("short", {})
            
            if float(long.get("units", 0)) != 0:
                positions.append(BrokerPosition(
                    broker="oanda",
                    symbol=p["instrument"].replace("_", "/"),
                    side=PositionSide.LONG,
                    quantity=abs(float(long["units"])),
                    avg_entry_price=float(long.get("averagePrice", 0)),
                    unrealized_pnl=float(long.get("unrealizedPL", 0)),
                ))
            if float(short.get("units", 0)) != 0:
                positions.append(BrokerPosition(
                    broker="oanda",
                    symbol=p["instrument"].replace("_", "/"),
                    side=PositionSide.SHORT,
                    quantity=abs(float(short["units"])),
                    avg_entry_price=float(short.get("averagePrice", 0)),
                    unrealized_pnl=float(short.get("unrealizedPL", 0)),
                ))
        return positions

    async def get_balance(self) -> BrokerBalance:
        result = await self._request("GET", f"/v3/accounts/{self._account_id}/summary")
        acct = result.get("account", {})
        return BrokerBalance(
            broker="oanda",
            currency=acct.get("currency", "USD"),
            total=float(acct.get("balance", 0)),
            available=float(acct.get("marginAvailable", 0)),
            used_margin=float(acct.get("marginUsed", 0)),
            equity=float(acct.get("NAV", 0)),
            unrealized_pnl=float(acct.get("unrealizedPL", 0)),
        )

    async def get_tick(self, symbol: str) -> BrokerTick:
        instrument = symbol.replace("/", "_")
        result = await self._request(
            "GET",
            f"/v3/accounts/{self._account_id}/pricing",
            params={"instruments": instrument},
        )
        price = result.get("prices", [{}])[0]
        return BrokerTick(
            broker="oanda",
            symbol=symbol,
            bid=float(price.get("bids", [{}])[0].get("price", 0)),
            ask=float(price.get("asks", [{}])[0].get("price", 0)),
            spread=float(price.get("asks", [{}])[0].get("price", 0)) - float(price.get("bids", [{}])[0].get("price", 0)),
            timestamp=dt.datetime.fromisoformat(price.get("time", "").replace("Z", "+00:00")),
        )

    async def get_bars(self, symbol: str, timeframe: str, count: int = 500) -> list[BrokerBar]:
        instrument = symbol.replace("/", "_")
        tf_map = {"M1": "M", "M5": "M5", "M15": "M15", "M30": "M30", "H1": "H1", "H4": "H4", "D1": "D", "W1": "W", "MN1": "M"}
        granularity = tf_map.get(timeframe.upper(), "H1")
        
        result = await self._request(
            "GET",
            f"/v3/instruments/{instrument}/candles",
            params={"granularity": granularity, "count": min(count, 5000), "price": "MBA"},
        )
        
        bars = []
        for c in result.get("candles", []):
            if not c.get("complete"):
                continue
            mid = c.get("mid", {})
            bars.append(BrokerBar(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=dt.datetime.fromisoformat(c["time"].replace("Z", "+00:00")),
                open=float(mid.get("o", 0)),
                high=float(mid.get("h", 0)),
                low=float(mid.get("l", 0)),
                close=float(mid.get("c", 0)),
                volume=float(c.get("volume", 0)),
            ))
        return bars
```

### 8.2 Enhanced MT5 Connector (Refinements to Existing Code)

```python
# Key improvements to mt5_connector.py:

# 1. Dynamic spread conversion
def _bar_from_tick(tick: Any, symbol_info: Any = None) -> BrokerTick:
    """Convert MT5 tick with proper spread handling."""
    spread_raw = getattr(tick, "spread", 0)
    if symbol_info:
        # MT5 spread is in points; convert using actual point size
        spread = spread_raw * symbol_info.point
    else:
        spread = spread_raw * 1e-5  # Fallback for 5-digit pairs
    return BrokerTick(
        broker="mt5",
        symbol=getattr(tick, "symbol", ""),
        bid=getattr(tick, "bid", 0.0),
        ask=getattr(tick, "ask", 0.0),
        last=getattr(tick, "last", 0.0),
        volume=getattr(tick, "volume_real", 0.0),
        spread=spread,
        timestamp=dt.datetime.fromtimestamp(getattr(tick, "time", 0), tz=dt.timezone.utc),
    )

# 2. Add symbol info helper to MT5Connector
async def get_symbol_info(self, symbol: str) -> dict[str, Any]:
    """Get symbol properties (pip size, lot size, etc.)."""
    self._ensure_connected()
    mt5 = _get_mt5()
    info = await self._run(mt5.symbol_info, symbol)
    if info is None:
        raise ValueError(f"Symbol {symbol} not found")
    d = info._asdict() if hasattr(info, "_asdict") else {}
    return {
        "symbol": symbol,
        "point": d.get("point", 0.00001),
        "digits": d.get("digits", 5),
        "trade_contract_size": d.get("trade_contract_size", 100000),
        "volume_min": d.get("volume_min", 0.01),
        "volume_max": d.get("volume_max", 100.0),
        "volume_step": d.get("volume_step", 0.01),
        "trade_tick_value": d.get("trade_tick_value", 0.0),
        "trade_tick_size": d.get("trade_tick_size", 0.0),
        "swap_long": d.get("swap_long", 0.0),
        "swap_short": d.get("swap_short", 0.0),
        "margin_initial": d.get("margin_initial", 0.0),
    }

# 3. Add swap tracking to positions
# In get_positions(), include:
# swap=p.swap,
# And update BrokerPosition model to have a swap field
```

### 8.3 Registry Setup

```python
"""Example: Setting up multi-broker AlphaStack."""

from alphastack.brokers.registry import BrokerRegistry
from alphastack.brokers.smart_router import SmartRouter, RoutingCriteria
from alphastack.brokers.order_manager import OrderManager

# Create registry
registry = BrokerRegistry()

# Register brokers
from alphastack.brokers.ccxt_connector import CCXTConnector
from alphastack.brokers.oanda_connector import OandaConnector  # New
from alphastack.brokers.mt5_connector import MT5Connector

binance = CCXTConnector("binance")
oanda = OandaConnector(account_id="xxx", access_token="xxx", environment="practice")
mt5 = MT5Connector(login=12345678, password="xxx", server="Broker-Demo")

registry.register("binance", binance, default=True)  # Default for crypto
registry.register("oanda", oanda)
registry.register("mt5", mt5)

# Connect all
await registry.connect_all()

# Set up smart routing
order_manager = OrderManager()
criteria = RoutingCriteria(
    cost_weight=0.4,
    fill_quality_weight=0.3,
    latency_weight=0.2,
    reliability_weight=0.1,
)
router = SmartRouter(registry, order_manager, criteria)

# Route an order — router picks the best broker
order = BrokerOrder(symbol="EUR/USD", side=OrderSide.BUY, quantity=0.1)
result = await router.route(order)
```

---

## 9. Risk Considerations

### 9.1 Technical Risks

| Risk | Impact | Mitigation |
|------|--------|-----------|
| **MT5 Python package Windows-only** | High — can't run natively on Linux AlphaStack host | Use MQL5 Bridge via ZeroMQ or Windows VPS |
| **MT5 under Wine is unstable** | Medium — crashes, network issues | Prefer Windows VPS for production |
| **Thread pool exhaustion** (MT5 sync calls) | Medium — blocks event loop | Already mitigated in existing code with `ThreadPoolExecutor` |
| **API rate limits** (OANDA: 120 req/s) | Low — generous limits | Existing `_RateLimiter` handles this |
| **Symbol format mismatches** | High — wrong instrument traded | `SymbolNormalizer` with validation |
| **Time zone confusion** | Medium — wrong session times | All times in UTC internally |

### 9.2 Trading Risks

| Risk | Impact | Mitigation |
|------|--------|-----------|
| **Leverage amplifies losses** | High — 1:100 leverage means 1% move = 100% loss | Position sizing based on account equity, max leverage caps |
| **Gap risk** (weekend/holiday) | High — price gaps through stop losses | Close positions before weekends, use guaranteed stops if available |
| **Slippage in fast markets** | Medium — fills worse than expected | Use deviation/slippage limits in order requests |
| **Spread widening** (news events) | Medium — cost increases dramatically | Avoid trading during major news releases, widen stop buffers |
| **Swap costs** (carry trade) | Low-Medium — accumulated overnight fees | Track swap rates, close before triple swap Wednesday |
| **Margin call / stop-out** | High — forced position closure | Monitor margin level across all brokers, auto-reduce before threshold |

### 9.3 Multi-Broker Risks

| Risk | Impact | Mitigation |
|------|--------|-----------|
| **Double-execution** | High — same signal sent to multiple brokers | SmartRouter routes to ONE broker per order, not broadcast |
| **Inconsistent fills** | Medium — different prices across brokers | Record per-broker fill quality, update routing scores |
| **Currency mismatch** | Medium — P/L in different currencies | Normalize all P/L to base currency (USD) using live FX rates |
| **Regulatory differences** | Medium — FIFO rules (US), hedging restrictions | Track account type per broker, enforce compliance rules |
| **Cascading failures** | High — one broker failure triggers others | Failover logic already in SmartRouter, circuit breakers needed |
| **Capital allocation** | Medium — over-leveraged across brokers | CrossBrokerRiskManager tracks aggregate exposure |

### 9.4 Operational Risks

| Risk | Impact | Mitigation |
|------|--------|-----------|
| **API key compromise** | Critical — unauthorized trading | Rotate keys, use IP whitelisting, minimal permissions |
| **Broker downtime** | Medium — can't manage positions | Multi-broker failover, emergency close-all via phone |
| **Data inconsistency** | Medium — stale prices | Validate tick freshness, reject stale data |
| **Clock skew** | Low — wrong timestamps | NTP sync, all timestamps in UTC |

---

## 10. Recommendations

### 10.1 Immediate Actions (This Week)

1. **Create `forex_utils.py`** — pip calculation, lot sizes, symbol metadata
2. **Create `SymbolNormalizer`** — canonical ↔ broker-specific symbol mapping
3. **Update `models.py`** — add `swap`, `spread_at_entry`, `margin_required` fields to BrokerPosition/BrokerOrder

### 10.2 First Platform: OANDA

**Why OANDA first:**
- Pure REST API — no platform software, no Windows dependency
- Works natively on Linux (AlphaStack's environment)
- Excellent Python support
- Can be tested with a free demo account
- Fastest time-to-value (2-3 days)

### 10.3 Second Platform: MT5 via Bridge

**Why MT5 second:**
- Most popular retail forex platform
- Many brokers offer MT5 (IC Markets, Pepperstone, XM, etc.)
- MQL5 Bridge already scaffolded
- Requires Windows VPS ($10-30/month)
- 1-2 weeks implementation

### 10.4 Future: IBKR for Multi-Asset

**Why IBKR eventually:**
- Trade everything from one account
- Best institutional-grade execution
- Complex but powerful API
- Only if AlphaStack expands to equities/futures

### 10.5 Architecture Principles

1. **One connector per broker** — each extends `BrokerConnector`
2. **Canonical symbols** — always use `EUR/USD` format internally, convert at connector level
3. **Unified risk** — `CrossBrokerRiskManager` sees all positions across all brokers
4. **Smart routing** — `SmartRouter` picks the best venue for each order based on cost/fill/latency
5. **Failover** — if primary broker fails, automatically try alternatives
6. **All times UTC** — no exceptions
7. **Async everywhere** — all broker calls are `async` (MT5 uses thread pool internally)

### 10.6 Estimated Timeline

```
Week 1-2:  Foundation (forex_utils + OANDA connector + tests)
Week 3-4:  MT5 Bridge (EA + bridge refinement + VPS deployment)
Week 5-6:  Multi-broker risk + smart routing for forex
Week 7+:   IBKR/cTrader if needed, cross-broker arbitrage
```

**Total to production-ready forex: ~4-6 weeks**

---

## Appendix A: MT5 Error Codes Reference

| Code | Name | Description |
|------|------|-------------|
| 10004 | TRADE_RETCODE_REQUOTE | Requote — price changed |
| 10006 | TRADE_RETCODE_REJECT | Request rejected |
| 10007 | TRADE_RETCODE_CANCEL | Request canceled by trader |
| 10008 | TRADE_RETCODE_PLACED | Order placed |
| 10009 | TRADE_RETCODE_DONE | Request completed |
| 10010 | TRADE_RETCODE_DONE_PARTIAL | Request partially completed |
| 10011 | TRADE_RETCODE_ERROR | Request processing error |
| 10012 | TRADE_RETCODE_TIMEOUT | Request canceled by timeout |
| 10013 | TRADE_RETCODE_INVALID | Invalid request |
| 10014 | TRADE_RETCODE_INVALID_VOLUME | Invalid volume |
| 10015 | TRADE_RETCODE_INVALID_PRICE | Invalid price |
| 10016 | TRADE_RETCODE_INVALID_STOPS | Invalid stops |
| 10017 | TRADE_RETCODE_TRADE_DISABLED | Trade disabled |
| 10018 | TRADE_RETCODE_MARKET_CLOSED | Market closed |
| 10019 | TRADE_RETCODE_NO_MONEY | Not enough money |
| 10020 | TRADE_RETCODE_PRICE_CHANGED | Price changed |
| 10021 | TRADE_RETCODE_PRICE_OFF | No prices |
| 10022 | TRADE_RETCODE_INVALID_EXPIRATION | Invalid expiration |
| 10023 | TRADE_RETCODE_ORDER_CHANGED | Order state changed |
| 10024 | TRADE_RETCODE_TOO_MANY_REQUESTS | Too frequent requests |
| 10025 | TRADE_RETCODE_NO_CHANGES | No changes |
| 10026 | TRADE_RETCODE_SERVER_DISABLES_AT | Autotrading disabled by server |
| 10027 | TRADE_RETCODE_CLIENT_DISABLES_AT | Autotrading disabled by client |
| 10028 | TRADE_RETCODE_LOCKED | Request locked |
| 10029 | TRADE_RETCODE_FROZEN | Order/position frozen |
| 10030 | TRADE_RETCODE_INVALID_FILL | Invalid fill type |

## Appendix B: Useful Links

- **MetaTrader5 Python docs:** https://www.mql5.com/en/docs/python_metatrader5
- **OANDA v20 API docs:** https://developer.oanda.com/rest-live-v20/
- **IBKR API docs:** https://interactivebrokers.github.io/
- **ib_insync GitHub:** https://github.com/erdewit/ib_insync
- **cTrader Open API:** https://github.com/spotware
- **MetaTrader5-Docker:** https://github.com/gmag11/MetaTrader5-Docker
- **oandapyV20:** https://pypi.org/project/oandapyV20/
