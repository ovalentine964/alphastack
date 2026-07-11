# Multi-Broker Integration Research — Alpha Stack

**Date:** 2026-07-11  
**Purpose:** Detailed API research for each broker Alpha Stack should support, with integration patterns and recommended phasing.

---

## Table of Contents

1. [MT5 Python Library (FXPesa)](#1-mt5-python-library-fxpesa)
2. [CCXT Library (Crypto Exchanges)](#2-ccxt-library-crypto-exchanges)
3. [OANDA REST API (v20)](#3-oanda-rest-api-v20)
4. [Interactive Brokers TWS API](#4-interactive-brokers-tws-api)
5. [IG Markets REST API](#5-ig-markets-rest-api)
6. [Unified Connector Design](#6-unified-connector-design)
7. [Recommended Integration Order](#7-recommended-integration-order)

---

## 1. MT5 Python Library (FXPesa)

### Package Info
- **Package:** `MetaTrader5` (PyPI: `metatrader5`)
- **Version:** 5.0.5735 (Apr 2026) — actively maintained by MetaQuotes
- **License:** MIT
- **Python:** 3.6+
- **Platform:** **Windows-only** (native), Linux via Wine/Bottles

### Connection

```python
import MetaTrader5 as mt5

# Initialize — launches/connects to MT5 terminal
if not mt5.initialize():
    print(f"initialize() failed, error code = {mt5.last_error()}")
    quit()

# Login to broker account
authorized = mt5.login(
    login=12345678,          # account number
    password="your_password", # investor password for read-only
    server="FXPesa-Demo"     # broker server name
)
if not authorized:
    print(f"login failed, error code = {mt5.last_error()}")
    mt5.shutdown()
    quit()
```

### Key Functions

| Function | Purpose |
|---|---|
| `mt5.initialize(path=...)` | Launch/connect to MT5 terminal |
| `mt5.login(login, password, server)` | Authenticate with broker |
| `mt5.shutdown()` | Disconnect and shutdown terminal |
| `mt5.terminal_info()` | Get terminal status (connection, trade allowed, etc.) |
| `mt5.account_info()` | Get account info (balance, equity, margin, leverage) |
| `mt5.symbols_get()` | Get all available symbols |
| `mt5.symbol_info(symbol)` | Get symbol specifications (spread, digits, volume limits) |
| `mt5.symbol_info_tick(symbol)` | Get latest tick (bid, ask, last, volume) |
| `mt5.copy_rates_from_pos(symbol, tf, start, count)` | Get OHLCV bars by position |
| `mt5.copy_rates_from_date(symbol, tf, date_from, date_to)` | Get OHLCV bars by date range |
| `mt5.copy_ticks_from(symbol, date_from, count, flags)` | Get tick data |
| `mt5.order_send(request)` | Place/modify/delete orders |
| `mt5.orders_get()` | Get active orders |
| `mt5.positions_get()` | Get open positions |
| `mt5.history_orders_get(date_from, date_to)` | Get order history |
| `mt5.history_deals_get(date_from, date_to)` | Get deal history |

### Order Send Structure

```python
request = {
    "action": mt5.TRADE_ACTION_DEAL,       # market order
    "symbol": "EURUSD",
    "volume": 0.1,
    "type": mt5.ORDER_TYPE_BUY,
    "price": mt5.symbol_info_tick("EURUSD").ask,
    "sl": 1.0700,                           # stop loss
    "tp": 1.0900,                           # take profit
    "deviation": 10,                        # max price deviation in points
    "magic": 123456,                        # EA identifier
    "comment": "Alpha Stack order",
    "type_time": mt5.ORDER_TIME_GTC,
    "type_filling": mt5.ORDER_FILLING_IOC,
}
result = mt5.order_send(request)
```

### OHLCV Data Format

```python
# Returns numpy array with fields: time, open, high, low, close, tick_volume, spread, real_volume
rates = mt5.copy_rates_from_pos("EURUSD", mt5.TIMEFRAME_H1, 0, 100)
# Convert to pandas:
import pandas as pd
df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')
```

### Error Handling

```python
error = mt5.last_error()
# Returns tuple: (error_code, error_description)
# Common codes:
# 0  = MT5_RES_S_OK (success)
# 1  = MT5_RES_FAIL (generic failure)
# 3  = MT5_RES_INVALID_PRICE
# 4  = MT5_RES_INVALID_PRICE_TRADE
# 5  = MT5_RES_INVALID_VOLUME
# 6  = MT5_RES_MARKET_CLOSED
# 10 = MT5_TRADE_RETCODE_REQUOTE
# 10013 = MT5_RES_INVALID_STOPS
```

### Reconnection Pattern

```python
def ensure_connection():
    if not mt5.terminal_info().connected:
        mt5.shutdown()
        if not mt5.initialize():
            raise ConnectionError(f"MT5 init failed: {mt5.last_error()}")
        if not mt5.login(login=LOGIN, password=PASSWORD, server=SERVER):
            raise ConnectionError(f"MT5 login failed: {mt5.last_error()}")
```

### Linux Deployment (Wine/Bottles)

- MT5 terminal runs under Wine on Linux
- Python package works with Wine Python or native Python connecting to Wine MT5
- **Bottles** (Flatpak) is the recommended approach for containerized Wine
- Setup: Install MT5 in a Bottle → run Python natively → `mt5.initialize(path="/path/to/terminal64.exe")`
- **Limitation:** Less stable than native Windows; requires Xvfb or virtual display for headless servers
- **Alternative:** Windows VPS with MT5 + remote Python connection

---

## 2. CCXT Library (Crypto Exchanges)

### Package Info
- **Package:** `ccxt` (pip/npm/composer)
- **Languages:** Python, JavaScript, PHP, C#, Go, Java
- **Exchanges:** 100+ centralized + DEX support
- **License:** MIT

### Key Exchanges for Alpha Stack

| Exchange | Spot | Futures | Sandbox | Rate Limit | Notes |
|---|---|---|---|---|---|
| **Binance** | ✅ | ✅ | ✅ | 1200/min | Largest liquidity, best API |
| **Bybit** | ✅ | ✅ | ✅ | 120/min | Strong derivatives |
| **OKX** | ✅ | ✅ | ✅ | 20/2s | Good unified account |
| **Kraken** | ✅ | ✅ | ❌ | 15/1s | Regulated, fiat ramps |
| **Coinbase** | ✅ | ✅ | ✅ | 10/1s | US-regulated |

### Unified API — Core Methods

```python
import ccxt

# Initialize exchange
exchange = ccxt.binance({
    'apiKey': 'YOUR_API_KEY',
    'secret': 'YOUR_SECRET',
    'enableRateLimit': True,      # auto rate limiting
    'options': {'defaultType': 'spot'},  # or 'future', 'margin'
})

# Sandbox/testnet
exchange.set_sandbox_mode(True)

# --- Market Data ---
markets = exchange.load_markets()              # all markets
ticker = exchange.fetch_ticker('BTC/USDT')     # latest ticker
orderbook = exchange.fetch_order_book('BTC/USDT', limit=20)
ohlcv = exchange.fetch_ohlcv('BTC/USDT', '1h', limit=100)  # [[ts,o,h,l,c,v], ...]
trades = exchange.fetch_trades('BTC/USDT', limit=50)

# --- Trading ---
balance = exchange.fetch_balance()              # all balances
usdt_balance = exchange.fetch_balance({'currency': 'USDT'})

# Market order
order = exchange.create_market_buy_order('BTC/USDT', 0.001)
order = exchange.create_market_sell_order('BTC/USDT', 0.001)

# Limit order
order = exchange.create_limit_buy_order('BTC/USDT', 0.001, 50000)
order = exchange.create_limit_sell_order('BTC/USDT', 0.001, 60000)

# Unified order method
order = exchange.create_order(
    symbol='BTC/USDT',
    type='limit',
    side='buy',
    amount=0.001,
    price=50000,
    params={'stopPrice': 49000}  # exchange-specific params
)

# Order management
open_orders = exchange.fetch_open_orders('BTC/USDT')
closed_orders = exchange.fetch_closed_orders('BTC/USDT')
order = exchange.fetch_order('ORDER_ID', 'BTC/USDT')
exchange.cancel_order('ORDER_ID', 'BTC/USDT')

# Positions (futures)
positions = exchange.fetch_positions()
```

### Unified Data Formats

```python
# Ticker
{
    'symbol': 'BTC/USDT',
    'timestamp': 1626787200000,
    'datetime': '2021-07-20T12:00:00.000Z',
    'high': 34000, 'low': 32000,
    'bid': 33000, 'bidVolume': 1.5,
    'ask': 33001, 'askVolume': 2.0,
    'last': 33000.5,
    'volume': 15000,        # 24h base volume
    'quoteVolume': 495000000,  # 24h quote volume
}

# OHLCV (array of arrays)
[
    [1626787200000, 33000, 33500, 32800, 33200, 500.5],  # [timestamp, O, H, L, C, Volume]
    ...
]

# Order
{
    'id': '12345',
    'symbol': 'BTC/USDT',
    'type': 'limit',
    'side': 'buy',
    'price': 50000,
    'amount': 0.001,
    'filled': 0.001,
    'remaining': 0,
    'status': 'closed',  # 'open', 'closed', 'canceled', 'expired'
    'timestamp': 1626787200000,
    'datetime': '2021-07-20T12:00:00.000Z',
    'fee': {'cost': 0.05, 'currency': 'USDT'},
}
```

### WebSocket (CCXT Pro)

```python
# CCXT Pro — paid add-on or open-source
import ccxt.pro as ccxtpro

exchange = ccxtpro.binance({'apiKey': '...', 'secret': '...'})

# Real-time ticker
while True:
    ticker = await exchange.watch_ticker('BTC/USDT')
    print(ticker['last'])

# Real-time order book
orderbook = await exchange.watch_order_book('BTC/USDT', limit=10)

# Real-time trades
trades = await exchange.watch_trades('BTC/USDT')

# Real-time OHLCV
ohlcv = await exchange.watch_ohlcv('BTC/USDT', '1m')

# Real-time orders/positions
orders = await exchange.watch_orders()
positions = await exchange.watch_positions()  # futures only
```

### Rate Limits by Exchange

| Exchange | REST Rate Limit | Notes |
|---|---|---|
| Binance | 1200 req/min (IP) | Weighted; orders = 10, market data = 1 |
| Bybit | 120 req/5s (IP) | Unified rate limit |
| OKX | 20 req/2s per endpoint | Per-endpoint limits |
| Kraken | 15 req/1s (private) | Stricter for private endpoints |
| Coinbase | 10 req/1s | Per IP |

---

## 3. OANDA REST API (v20)

### Overview
- **Type:** Pure REST API (no WebSocket library needed — streaming via HTTP chunked)
- **Python SDK:** `oandapyV20` (v0.7.2, MIT, last updated Aug 2021)
- **Alternative:** Direct HTTP requests (requests + v20 endpoints)
- **Accounts:** Practice (demo) and Live
- **Assets:** Forex, CFDs, metals, indices

### Authentication

```python
# Bearer token — generated from OANDA Account Management Portal
from oandapyV20 import API
import oandapyV20.endpoints.orders as orders
import oandapyV20.endpoints.instruments as instruments

api = API(access_token="YOUR_PERSONAL_ACCESS_TOKEN", environment="practice")
# environment: "practice" or "live"
```

### REST Endpoints

| Endpoint Group | Base Path | Key Operations |
|---|---|---|
| **Accounts** | `/v3/accounts/{id}` | GET account details, summary, instruments |
| **Orders** | `/v3/accounts/{id}/orders` | CREATE, GET, MODIFY, CANCEL, REPLACE |
| **Trades** | `/v3/accounts/{id}/trades` | GET open trades, close, modify |
| **Positions** | `/v3/accounts/{id}/positions` | GET, close |
| **Pricing** | `/v3/accounts/{id}/candles` | GET OHLCV candles |
| **Transactions** | `/v3/accounts/{id}/transactions` | GET transaction stream/history |

### Python SDK Usage

```python
from oandapyV20 import API
from oandapyV20.endpoints import accounts, orders, instruments, trades, positions

api = API(access_token="TOKEN", environment="practice")

# Get account info
r = accounts.AccountDetails(accountID="101-001-XXXXXXX-XXX")
api.request(r)
print(r.response['account']['balance'])

# Get candles (OHLCV)
params = {"count": 100, "granularity": "H1", "price": "MBA"}  # M=mid, B=bid, A=ask
r = instruments.InstrumentsCandles(instrument="EUR_USD", params=params)
api.request(r)
candles = r.response['candles']
# Each candle: {time, bid: {o,h,l,c}, ask: {o,h,l,c}, mid: {o,h,l,c}, volume, complete}

# Place market order
order_data = {
    "order": {
        "type": "MARKET",
        "instrument": "EUR_USD",
        "units": "1000",          # positive = buy, negative = sell
        "timeInForce": "FOK",
        "positionFill": "DEFAULT"
    }
}
r = orders.OrderCreate(accountID="101-001-XXXXXXX-XXX", data=order_data)
api.request(r)

# Place market order with TP/SL
from oandapyV20.contrib.requests import MarketOrderRequest, TakeProfitDetails, StopLossDetails

mktOrder = MarketOrderRequest(
    instrument="EUR_USD",
    units=1000,
    takeProfitOnFill=TakeProfitDetails(price=1.10000).data,
    stopLossOnFill=StopLossDetails(price=1.07000).data
).data

# Get open positions
r = positions.OpenPositions(accountID="101-001-XXXXXXX-XXX")
api.request(r)

# Close position
close_data = {"longUnits": "ALL"}  # or "shortUnits": "ALL"
r = positions.PositionClose(accountID="101-001-XXXXXXX-XXX", instrument="EUR_USD", data=close_data)
api.request(r)
```

### Streaming (Real-time Prices)

```python
import oandapyV20.endpoints.pricing as pricing

# Streaming endpoint — keeps HTTP connection open
r = pricing.PricingStream(accountID="101-001-XXXXXXX-XXX", params={"instruments": "EUR_USD,GBP_USD"})
api.request(r)
for tick in r.response:
    if tick['type'] == 'PRICE':
        print(f"{tick['instrument']}: bid={tick['bids'][0]['price']} ask={tick['asks'][0]['price']}")
```

### Practice vs Live

| Feature | Practice | Live |
|---|---|---|
| URL | `https://api-fxpractice.oanda.com` | `https://api-fxtrade.oanda.com` |
| Token | From AMP (practice account) | From AMP (live account) |
| Funding | Unlimited virtual money | Real money |
| Spreads | Simulated | Real market |
| Rate Limits | Relaxed | Standard |

---

## 4. Interactive Brokers TWS API

### Architecture
- **Client-Server:** TWS (Trader Workstation) or IB Gateway runs as server; Python connects as client
- **Connection:** TCP socket to `127.0.0.1:7497` (TWS) or `4001` (IB Gateway)
- **Python Library:** `ib_insync` (v0.9.86, BSD) — wraps official `ibapi` with asyncio

### Setup Requirements
1. Install TWS or IB Gateway (Java application)
2. Enable API connections in TWS: File → Global Configuration → API → Settings
3. Set socket port (7497 for TWS, 4001 for Gateway)
4. Trust localhost connections or whitelist IPs

### Connection

```python
from ib_insync import *

ib = IB()
ib.connect('127.0.0.1', 7497, clientId=1)

# Paper trading: use port 7497 with paper account, or TWS paper trading mode
```

### Supported Instruments

| Instrument Type | IB Class | Example |
|---|---|---|
| Forex | `Forex('EURUSD')` | EUR/USD |
| Stocks | `Stock('AAPL', 'SMART', 'USD')` | Apple |
| Futures | `Future('ES', '202403', 'CME')` | S&P 500 E-mini |
| Options | `Option('AAPL', '20240315', 150, 'C', 'SMART')` | Call option |
| CFDs | `CFD('AAPL', 'SMART', 'USD')` | CFD |
| Crypto | `Crypto('BTC', 'PAXOS', 'USD')` | Bitcoin |

### Core Operations

```python
from ib_insync import *

ib = IB()
ib.connect('127.0.0.1', 7497, clientId=1)

# --- Market Data ---
contract = Forex('EURUSD')
ib.qualifyContracts(contract)  # resolve contract details

# Real-time tick data
ticker = ib.reqMktData(contract, '', False, False)
# ticker.bid, ticker.ask, ticker.last, ticker.volume

# Historical OHLCV
bars = ib.reqHistoricalData(
    contract,
    endDateTime='',              # empty = now
    durationStr='30 D',          # lookback period
    barSizeSetting='1 hour',     # bar size
    whatToShow='MIDPOINT',       # MIDPOINT, BID, ASK, TRADES
    useRTH=True,                 # regular trading hours
    formatDate=1
)
df = util.df(bars)  # convert to pandas DataFrame
# Columns: date, open, high, low, close, volume, average, barCount

# --- Account ---
account = ib.accountSummary()
# Returns list of TagValue objects: TotalCashValue, NetLiquidation, etc.

portfolio = ib.portfolio()
# Returns list of PortfolioItem with contract, position, marketPrice, etc.

# --- Orders ---
contract = Forex('EURUSD')
order = MarketOrder('BUY', 20000)  # 20k units
trade = ib.placeOrder(contract, order)
ib.sleep(1)  # wait for fill
print(trade.orderStatus.status)  # 'Filled', 'Submitted', etc.

# Limit order
order = LimitOrder('BUY', 10000, 1.0800)
trade = ib.placeOrder(contract, order)

# Bracket order (entry + TP + SL)
parent = LimitOrder('BUY', 10000, 1.0800)
tp = LimitOrder('SELL', 10000, 1.0900)
sl = StopOrder('SELL', 10000, 1.0700)
bracket = BracketOrder(parent, tp, sl)  # not a real method — manual setup needed

# Modify order
order.lmtPrice = 1.0810
trade = ib.placeOrder(contract, order)  # same order object, updates existing

# Cancel
ib.cancelOrder(order)

# Open orders / trades
open_orders = ib.openOrders()
open_trades = ib.openTrades()
```

### Async Pattern

```python
import asyncio
from ib_insync import *

async def main():
    ib = IB()
    await ib.connectAsync('127.0.0.1', 7497, clientId=1)
    
    contract = Forex('EURUSD')
    bars = await ib.reqHistoricalDataAsync(
        contract, endDateTime='', durationStr='1 D',
        barSizeSetting='5 mins', whatToShow='MIDPOINT', useRTH=True
    )
    df = util.df(bars)
    print(df)

asyncio.run(main())
```

### Paper Trading

- TWS: Switch to paper trading mode (separate login)
- IB Gateway: Paper trading on port 7497 by default
- Paper account has separate credentials and account ID
- Simulates fills but may not match live exactly (slippage, fills)

---

## 5. IG Markets REST API

### Overview
- **Type:** REST API with streaming
- **Python Library:** `ig-trading-api` (v1.0.6, MIT, Sep 2023)
- **Assets:** Forex, indices, commodities, crypto, stocks
- **Account:** Demo and Live
- **Well-documented** API

### Connection

```python
from igapi import IG

ig = IG(api_key="YOUR_API_KEY", username="YOUR_USERNAME", 
        password="YOUR_PASSWORD", account="ACCOUNT_ID", 
        acc_type="demo")  # or "live"

ig.login()
```

### Core Operations

```python
# Account
account_info = ig.account()
balance = ig.getBalance()
available = ig.getAvailable()
deposit = ig.getDeposit()

# Market Data
price = ig.getPrice(epic="CS.D.EURUSD.TODAY.IP", resolution="HOUR", numPoints=100)
prices = ig.getPrices(epic="CS.D.EURUSD.TODAY.IP", resolution="HOUR", 
                       numPoints=100, start="2024-01-01", end="2024-01-31")

# Watchlists
watchlists = ig.watchlists()
watchlist = ig.watchlist(watchlist_id)

# Positions
positions = ig.getOpenPosition()
position = ig.getOpenPosition(deal_id="DEAL_ID")

# Create position
deal_ref = ig.createPosition(
    currency='USD',
    direction='BUY',
    epic='CS.D.EURUSD.TODAY.IP',
    expiry='-',              # '-' for spot/rolling
    orderType='MARKET',
    size=1,                  # in lots
    limitDistance=20,         # TP in pips
    stopDistance=40,          # SL in pips
    forceOpen=True,
    guaranteedStop=False
)

# Close position
deal_ref = ig.closePosition(
    deal_id='DEAL_ID',
    direction='SELL',
    epic='CS.D.EURUSD.TODAY.IP',
    expiry='-',
    orderType='MARKET',
    size=1
)

# Transactions
transactions = ig.getAccountTransactions(type='ALL', period=86400)  # last 24h
activities = ig.getAccountActivities()

ig.logout()
```

### Demo Account

- Free demo account with virtual £10,000
- Same API endpoints as live
- Register at: https://www.ig.com/uk/demo-account
- API key obtained from IG developer portal

---

## 6. Unified Connector Design

### Interface Pattern

All connectors should implement a common abstract interface so the Alpha Stack engine can swap brokers transparently.

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional
import pandas as pd

class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"

class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"

class OrderStatus(Enum):
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"

@dataclass
class Order:
    id: str
    symbol: str
    side: OrderSide
    type: OrderType
    amount: float
    price: Optional[float]
    filled: float
    remaining: float
    status: OrderStatus
    timestamp: int
    fee: Optional[dict] = None
    broker_metadata: Optional[dict] = None  # raw broker response

@dataclass
class Position:
    symbol: str
    side: OrderSide
    amount: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    timestamp: int
    broker_metadata: Optional[dict] = None

@dataclass
class Balance:
    currency: str
    total: float
    available: float
    locked: float  # in orders/margin

@dataclass
class OHLCV:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float

class BaseBrokerConnector(ABC):
    """Abstract base class for all broker connectors."""
    
    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to broker."""
        pass
    
    @abstractmethod
    def disconnect(self):
        """Close connection."""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Check connection status."""
        pass
    
    # --- Market Data ---
    @abstractmethod
    def fetch_ticker(self, symbol: str) -> dict:
        """Get latest price for symbol."""
        pass
    
    @abstractmethod
    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 100) -> list[OHLCV]:
        """Get OHLCV candle data."""
        pass
    
    @abstractmethod
    def fetch_orderbook(self, symbol: str, limit: int = 20) -> dict:
        """Get order book (bid/ask depth)."""
        pass
    
    # --- Account ---
    @abstractmethod
    def fetch_balance(self) -> list[Balance]:
        """Get account balances."""
        pass
    
    @abstractmethod
    def fetch_positions(self) -> list[Position]:
        """Get open positions."""
        pass
    
    # --- Orders ---
    @abstractmethod
    def create_order(self, symbol: str, side: OrderSide, type: OrderType,
                     amount: float, price: Optional[float] = None,
                     stop_loss: Optional[float] = None,
                     take_profit: Optional[float] = None) -> Order:
        """Place a new order."""
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel an open order."""
        pass
    
    @abstractmethod
    def fetch_order(self, order_id: str, symbol: str) -> Order:
        """Get order status."""
        pass
    
    @abstractmethod
    def fetch_open_orders(self, symbol: Optional[str] = None) -> list[Order]:
        """Get all open orders."""
        pass
    
    # --- Real-time (optional) ---
    def subscribe_ticker(self, symbol: str, callback):
        """Subscribe to real-time ticker updates. Override if supported."""
        raise NotImplementedError("Real-time not supported by this connector")
    
    def subscribe_orders(self, callback):
        """Subscribe to order updates. Override if supported."""
        raise NotImplementedError("Real-time not supported by this connector")
```

### Timeframe Mapping

```python
TIMEFRAME_MAP = {
    # Alpha Stack standard -> broker-specific
    "1m": {
        "mt5": mt5.TIMEFRAME_M1,
        "ccxt": "1m",
        "oanda": "M1",
        "ib": "1 min",
        "ig": "MINUTE",
    },
    "5m": {
        "mt5": mt5.TIMEFRAME_M5,
        "ccxt": "5m",
        "oanda": "M5",
        "ib": "5 mins",
        "ig": "MINUTE_5",
    },
    "15m": {
        "mt5": mt5.TIMEFRAME_M15,
        "ccxt": "15m",
        "oanda": "M15",
        "ib": "15 mins",
        "ig": "MINUTE_15",
    },
    "1h": {
        "mt5": mt5.TIMEFRAME_H1,
        "ccxt": "1h",
        "oanda": "H1",
        "ib": "1 hour",
        "ig": "HOUR",
    },
    "4h": {
        "mt5": mt5.TIMEFRAME_H4,
        "ccxt": "4h",
        "oanda": "H4",
        "ib": "4 hours",
        "ig": "HOUR_4",
    },
    "1d": {
        "mt5": mt5.TIMEFRAME_D1,
        "ccxt": "1d",
        "oanda": "D",
        "ib": "1 day",
        "ig": "DAY",
    },
}
```

### Symbol Mapping

Each broker uses different symbol formats:

| Standard | MT5 | CCXT (Binance) | OANDA | IB | IG |
|---|---|---|---|---|---|
| EUR/USD | `EURUSD` | `EUR/USDT` | `EUR_USD` | `EUR.USD` (Forex) | `CS.D.EURUSD.TODAY.IP` |
| GBP/USD | `GBPUSD` | `GBP/USDT` | `GBP_USD` | `GBP.USD` | `CS.D.GBPUSD.TODAY.IP` |
| BTC/USD | N/A | `BTC/USDT` | N/A | `BTC.USD` (Crypto) | `CS.D.BITCOIN.TODAY.IP` |

**Recommendation:** Maintain a symbol registry mapping internal normalized symbols to broker-specific formats.

### Handling Broker-Specific Features

| Feature | MT5 | CCXT | OANDA | IB | IG |
|---|---|---|---|---|---|
| Hedging mode | ✅ (built-in) | ❌ (net by default) | ✅ (per-account) | ✅ | ✅ |
| Partial fills | ✅ | ✅ | ❌ (all-or-nothing) | ✅ | ❌ |
| Bracket orders | ✅ | ❌ (manual) | ✅ (TP/SL on fill) | ✅ (native) | ✅ |
| Trailing stop | ✅ | ❌ (manual) | ✅ | ✅ | ✅ |
| Guaranteed stop | ❌ | ❌ | ❌ | ❌ | ✅ (IG only) |
| Account types | 1 (netting or hedge) | Spot/Margin/Future | Single | Multi-account | Single |

---

## 7. Recommended Integration Order

### Phase 1: MT5 (FXPesa) — FOREX ✅ EXISTING
**Priority:** Already have this  
**Effort:** Low (wrap existing code)  
**Assets:** Forex, metals, indices (via CFD)  
**Why first:** You already trade here, validates the unified connector pattern

**Action items:**
- [ ] Create `MT5Connector(BaseBrokerConnector)` class
- [ ] Implement reconnection logic
- [ ] Handle Windows/Linux Wine deployment
- [ ] Symbol mapping for FXPesa instruments

### Phase 2: CCXT (Binance) — CRYPTO
**Priority:** High  
**Effort:** Low-Medium (CCXT does most of the work)  
**Assets:** BTC, ETH, and all crypto pairs  
**Why second:** Free, easiest API, opens crypto market immediately

**Action items:**
- [ ] Create `CCXTConnector(BaseBrokerConnector)` class
- [ ] Binance testnet integration first
- [ ] Handle spot vs futures mode switching
- [ ] Rate limit awareness built-in via CCXT
- [ ] WebSocket support via CCXT Pro or native Binance WS

### Phase 3: OANDA — BETTER FOREX
**Priority:** Medium  
**Effort:** Medium  
**Assets:** Forex (better than MT5 API)  
**Why third:** Clean REST API, no terminal dependency, practice account for testing

**Action items:**
- [ ] Create `OANDAConnector(BaseBrokerConnector)` class
- [ ] Practice account setup and testing
- [ ] Streaming price integration
- [ ] Candle data normalization
- [ ] Consider replacing MT5 for forex if OANDA proves more reliable

### Phase 4: Interactive Brokers — INSTITUTIONAL
**Priority:** Medium-Low  
**Effort:** High (complex setup, TWS dependency)  
**Assets:** Everything (forex, stocks, options, futures, crypto)  
**Why last:**
- Most complex setup (requires TWS/IB Gateway running)
- Best for multi-asset portfolios
- Higher minimum requirements
- Worth it when you need stock/options access

**Action items:**
- [ ] Create `IBConnector(BaseBrokerConnector)` class
- [ ] TWS/IB Gateway headless deployment
- [ ] Contract resolution logic
- [ ] Paper trading first
- [ ] Handle IB's complex order types (bracket, OCA, etc.)

### Phase 5 (Optional): IG Markets
**Priority:** Low  
**Effort:** Low  
**When:** If you need UK/EU regulated broker access or guaranteed stops

---

## Quick Reference: Comparison Matrix

| Feature | MT5 | CCXT | OANDA | IB | IG |
|---|---|---|---|---|---|
| **Ease of setup** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
| **API quality** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| **Asset coverage** | Forex/CFD | Crypto | Forex/CFD | Everything | Forex/CFD/Stock |
| **Windows req.** | Yes | No | No | Yes (TWS) | No |
| **Paper trading** | ✅ | ✅ (exchange) | ✅ | ✅ | ✅ |
| **Real-time data** | ✅ (tick) | ✅ (WS) | ✅ (stream) | ✅ (stream) | ✅ (stream) |
| **Cost** | Free | Free (+ Pro) | Free | Free (data $) | Free |
| **Python lib** | metatrader5 | ccxt | oandapyV20 | ib_insync | ig-trading-api |
| **Community** | Medium | Large | Medium | Large | Small |

---

## Key Takeaways

1. **CCXT is the clear winner for crypto** — unified API across 100+ exchanges, one library, massive community
2. **MT5 works but has baggage** — Windows dependency, terminal required, but you already have it
3. **OANDA is the best pure forex API** — clean REST, no terminal, great for algo trading
4. **IB is the king of multi-asset** — but complex setup, worth it for stocks/options
5. **Unified connector pattern is essential** — swap brokers without changing strategy code

**Start with CCXT + MT5 (you have both), then add OANDA when ready for production forex.**
