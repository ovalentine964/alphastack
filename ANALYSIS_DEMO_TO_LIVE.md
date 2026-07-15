# AlphaStack — Demo-to-Live Trading Plan

> **Version:** 1.0 · **Date:** 2026-07-15 · **Status:** Implementation Guide
> **Scope:** Complete phased transition from paper/demo trading to live capital deployment
> **Prerequisites:** AlphaStack backend running, broker accounts created

---

## Table of Contents

1. [Overview & Safety Philosophy](#1-overview--safety-philosophy)
2. [PHASE 1: Demo/Paper Trading](#2-phase-1-demopaper-trading)
3. [PHASE 2: Forward Testing (Live Data, Tiny Positions)](#3-phase-2-forward-testing)
4. [PHASE 3: Live Trading (Real Money)](#4-phase-3-live-trading)
5. [Binance Testnet vs Production Reference](#5-binance-testnet-vs-production-reference)
6. [CCXT Sandbox Mode Deep Dive](#6-ccxt-sandbox-mode-deep-dive)
7. [Monitoring & Alerting Setup](#7-monitoring--alerting-setup)
8. [Risk Parameter Evolution Table](#8-risk-parameter-evolution-table)
9. [Troubleshooting & Common Issues](#9-troubleshooting--common-issues)

---

## 1. Overview & Safety Philosophy

### 1.1 The Transition Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DEMO → LIVE TRANSITION PIPELINE                    │
│                                                                       │
│  PHASE 1: PAPER TRADING (0$ at risk)                                │
│  ├── Binance Testnet / MT5 Demo                                     │
│  ├── Validate signal chain end-to-end                               │
│  ├── Measure execution latency, fill quality                        │
│  ├── Duration: 2-4 weeks minimum                                    │
│  └── Gate: All metrics within tolerance                             │
│                                                                       │
│  PHASE 2: FORWARD TESTING ($50-200 at risk)                         │
│  ├── Live Binance account, minimum position sizes                   │
│  ├── Real slippage, real fees, real fills                           │
│  ├── Validate risk governor under live conditions                   │
│  ├── Duration: 2-4 weeks minimum                                    │
│  └── Gate: Positive expectancy, risk limits respected               │
│                                                                       │
│  PHASE 3: LIVE TRADING (scaled capital)                             │
│  ├── Gradual position size increases                                │
│  ├── Full monitoring, alerting, circuit breakers                    │
│  ├── Continuous validation against backtest expectations            │
│  └── Ongoing: never stop validating                                 │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 Safety Principles

| # | Principle | Rationale |
|---|-----------|-----------|
| 1 | **Never skip phases** | Each phase catches different failure modes |
| 2 | **Same code paths** | Paper and live use identical `BrokerConnector` implementations |
| 3 | **Hard risk limits** | The `RiskGovernor` cannot be overridden by any strategy or model |
| 4 | **Manual kill switch** | Always have a way to halt trading in <5 seconds |
| 5 | **Assume bugs exist** | Treat every phase as a bug-finding exercise, not a profit exercise |
| 6 | **Capital you can lose** | Phase 2 capital should be money you're willing to lose entirely |

---

## 2. Phase 1: Demo/Paper Trading

### 2.1 Goal

Validate the complete AlphaStack signal → risk → execution → journal pipeline without any real money at risk. Confirm that the multi-agent orchestrator (news → strategy → risk → execution → reflection) produces sensible trade decisions.

### 2.2 Option A: Binance Testnet (Recommended for Crypto)

#### 2.2.1 Get Testnet API Keys

1. Go to **https://testnet.binance.vision/**
2. Sign in with GitHub
3. Click **"API Key"** to generate testnet credentials
4. Save the API Key and Secret Key

> **Note:** Binance testnet uses **separate credentials** from production. Testnet funds are free and unlimited (you can reset balance).

#### 2.2.2 Configuration

**Option 1: Environment Variables (`.env` file)**

Create or edit `.env` in the project root:

```bash
# .env — Phase 1: Binance Testnet
ALPHASTACK_ENV=dev

# CCXT Broker — Binance Testnet
CCXT_EXCHANGE=binance
CCXT_API_KEY=<your_testnet_api_key>
CCXT_SECRET=<your_testnet_secret_key>
CCXT_SANDBOX=true                    # ← CRITICAL: enables testnet mode

# Risk (conservative for testing)
RISK_MAX_DRAWDOWN_PCT=10.0
RISK_MAX_POSITION_SIZE_PCT=2.0
RISK_MAX_DAILY_LOSS_PCT=2.0
RISK_MAX_OPEN_POSITIONS=3
RISK_MAX_LEVERAGE=1.0

# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=alphastack
DB_USER=alphastack
DB_PASSWORD=alphastack

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# API
API_HOST=0.0.0.0
API_PORT=8000
API_DEBUG=true

# Logging
LOGGING_LEVEL=DEBUG
```

**Option 2: YAML config override**

```yaml
# config/alphastack.local.yaml
env: dev

ccxt:
  exchange: binance
  sandbox: true                      # ← Enables testnet
  # api_key and secret loaded from env vars CCXT_API_KEY / CCXT_SECRET

risk:
  max_drawdown_pct: 10.0
  max_position_size_pct: 2.0
  max_daily_loss_pct: 2.0
  max_open_positions: 3
  max_leverage: 1.0

trading:
  symbols:
    - BTC/USDT
    - ETH/USDT
  timeframes:
    - 1h
    - 4h
  default_timeframe: 1h
```

#### 2.2.3 How Sandbox Mode Works in Code

Looking at `src/alphastack/brokers/ccxt_connector.py`, the sandbox mode is activated via:

```python
# In CCXTConnector.__init__():
self._sandbox = sandbox if sandbox is not None else cfg.sandbox

# In CCXTConnector.connect():
if self._sandbox:
    self._exchange.set_sandbox_mode(True)
    logger.info("ccxt_sandbox_enabled", exchange=self._exchange_id)
```

When `sandbox=True`, CCXT's `set_sandbox_mode(True)` redirects API calls to the exchange's testnet endpoints:
- **Binance:** `testnet.binance.vision` (instead of `api.binance.com`)
- **Bybit:** `api-testnet.bybit.com`
- **OKX:** Uses testnet flag in headers

This is a **zero-code-change** switch — the same `CCXTConnector` class handles both modes.

#### 2.2.4 Docker Compose for Phase 1

```yaml
# docker-compose.phase1.yml — Paper trading on Binance testnet
version: "3.9"

x-common-env: &common-env
  ALPHASTACK_ENV: dev
  DB_HOST: timescaledb
  DB_PORT: 5432
  DB_NAME: alphastack
  DB_USER: alphastack
  DB_PASSWORD: alphastack
  REDIS_HOST: redis
  REDIS_PORT: 6379
  API_HOST: "0.0.0.0"
  API_PORT: 8000
  API_DEBUG: "true"
  # Broker — Binance Testnet
  CCXT_EXCHANGE: binance
  CCXT_SANDBOX: "true"               # ← Testnet mode
  CCXT_API_KEY: "${CCXT_API_KEY}"
  CCXT_SECRET: "${CCXT_SECRET}"
  # Conservative risk for paper trading
  RISK_MAX_DRAWDOWN_PCT: "10.0"
  RISK_MAX_POSITION_SIZE_PCT: "2.0"
  RISK_MAX_DAILY_LOSS_PCT: "2.0"
  RISK_MAX_OPEN_POSITIONS: "3"
  LOGGING_LEVEL: DEBUG

services:
  timescaledb:
    image: timescale/timescaledb:latest-pg16
    container_name: alphastack-timescaledb
    restart: unless-stopped
    ports: ["5432:5432"]
    environment:
      POSTGRES_DB: alphastack
      POSTGRES_USER: alphastack
      POSTGRES_PASSWORD: alphastack
    volumes: [timescaledb_data:/var/lib/postgresql/data]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U alphastack"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: alphastack-redis
    restart: unless-stopped
    ports: ["6379:6379"]
    volumes: [redis_data:/data]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  api:
    build:
      context: .
      dockerfile: infra/docker/Dockerfile
    container_name: alphastack-api
    restart: unless-stopped
    command: ["uvicorn", "alphastack.api.rest.app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
    ports: ["8000:8000"]
    environment: *common-env
    depends_on:
      timescaledb: { condition: service_healthy }
      redis: { condition: service_healthy }
    volumes:
      - ./src:/app/src
      - ./logs:/app/logs

  trading-engine:
    build:
      context: .
      dockerfile: infra/docker/Dockerfile
    container_name: alphastack-engine
    restart: unless-stopped
    command: ["python", "-m", "alphastack.engine"]
    environment: *common-env
    depends_on:
      timescaledb: { condition: service_healthy }
      redis: { condition: service_healthy }
    volumes:
      - ./src:/app/src
      - ./logs:/app/logs

volumes:
  timescaledb_data:
  redis_data:
```

#### 2.2.5 Commands to Run

```bash
# 1. Set testnet credentials
export CCXT_API_KEY="your_testnet_api_key"
export CCXT_SECRET="your_testnet_secret_key"

# 2. Start infrastructure
docker compose -f infra/docker/docker-compose.yml up -d timescaledb redis

# 3. Wait for DB to be healthy
docker compose -f infra/docker/docker-compose.yml exec timescaledb pg_isready -U alphastack

# 4. Start the API server
docker compose -f infra/docker/docker-compose.yml up -d api

# 5. Verify health
curl http://localhost:8000/health

# 6. Verify testnet connection
curl http://localhost:8000/api/v1/system/status | python3 -m json.tool

# 7. Check API docs
open http://localhost:8000/docs

# 8. Start the trading engine (when ready)
docker compose -f infra/docker/docker-compose.yml --profile engine up -d trading-engine

# 9. View logs
docker compose -f infra/docker/docker-compose.yml logs -f trading-engine
```

### 2.3 Option B: MT5 Demo Account (For Forex)

#### 2.3.1 Get Demo Account

1. Download MetaTrader 5 from your broker (e.g., FXPesa, Exness, ICMarkets)
2. Open a **Demo Account** (not live) in the MT5 terminal
3. Note the login number, password, and server name

#### 2.3.2 Configuration

```bash
# .env — Phase 1: MT5 Demo
MT5_LOGIN=12345678
MT5_PASSWORD=your_demo_password
MT5_SERVER=FXPesa-Demo                # or "MetaQuotes-Demo"
MT5_PATH=/path/to/terminal64.exe      # auto-detect if empty
```

> **Important:** MT5 requires Windows or Wine. For Linux servers, use the `MQL5Bridge` component (WebSocket bridge running on a Windows VM).

#### 2.3.3 MT5 Testnet Differences

Unlike crypto exchanges, MT5 "demo" accounts are:
- Connected to **live market data** (real prices)
- Using **demo money** (virtual funds, typically $10,000)
- Subject to the **same execution conditions** as live (same spread, same latency)

This makes MT5 demo accounts excellent for realistic paper trading.

### 2.4 Verification Steps for Phase 1

#### 2.4.1 Connection Verification

```bash
# Check broker connection status
curl -s http://localhost:8000/api/v1/system/status | python3 -m json.tool

# Expected output should show:
# {
#   "broker_status": {
#     "ccxt:binance": "connected"    ← or "mt5:fxpesa": "connected"
#   },
#   "risk_status": { ... },
#   "uptime_seconds": ...
# }
```

#### 2.4.2 Market Data Verification

```bash
# Fetch a test tick
curl -s http://localhost:8000/api/v1/signals/ticker?symbol=BTC/USDT | python3 -m json.tool

# Fetch OHLCV bars
curl -s "http://localhost:8000/api/v1/signals/bars?symbol=BTC/USDT&timeframe=1h&count=10" | python3 -m json.tool
```

#### 2.4.3 Signal Chain Verification

Run the orchestrator manually and verify each agent produces output:

```bash
# The orchestrator runs: news → strategy → risk → [human_review] → execution → reflection
# Check logs for each node:
docker compose logs trading-engine | grep "orchestrator.node"

# Expected log sequence:
# orchestrator.node node=news
# orchestrator.node node=strategy
# orchestrator.node node=risk
# orchestrator.node node=execution     (if approved)
# orchestrator.node node=reflection
```

#### 2.4.4 Order Execution Verification (Testnet)

Place a small test order through the API:

```bash
# Create a test trade via API
curl -X POST http://localhost:8000/api/v1/trades \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC/USDT",
    "side": "buy",
    "quantity": 0.001,
    "price": null,
    "stop_loss": 0,
    "take_profit": 0,
    "notes": "Phase 1 test order"
  }'
```

### 2.5 Metrics to Track During Phase 1

| Metric | How to Measure | Target |
|--------|---------------|--------|
| **Connection uptime** | % of time broker shows "connected" | >99% |
| **Signal generation rate** | Signals per day from strategy agent | 1-5/day |
| **Risk approval rate** | % of signals passing risk governor | 30-70% |
| **Execution latency** | Time from signal to order fill | <500ms (crypto), <200ms (MT5) |
| **Fill rate** | % of orders successfully filled | >95% |
| **Slippage** | Fill price vs expected price | <0.1% (crypto), <1 pip (forex) |
| **Data gap rate** | Missing candles / total candles | <1% |
| **Agent error rate** | Exceptions per agent per day | 0 |
| **Circuit breaker trips** | False positive breaker trips | 0 |
| **Daily P&L tracking** | Paper P&L vs backtest expectation | Within 2σ |

### 2.6 Phase 1 Exit Criteria

All of the following must be true for **at least 14 consecutive days**:

- [ ] Broker connection uptime >99%
- [ ] Zero unhandled exceptions in logs
- [ ] Execution latency P95 <500ms
- [ ] Fill rate >95%
- [ ] Risk governor correctly rejects >90% of invalid proposals
- [ ] Circuit breaker has zero false positive trips
- [ ] Paper P&L is positive or within expected drawdown range
- [ ] All 5 agents (news, strategy, risk, execution, reflection) produce output
- [ ] Human-in-the-loop approval flow works correctly
- [ ] WebSocket ticker streaming is stable (no disconnections >5min)

---

## 3. Phase 2: Forward Testing

### 3.1 Goal

Validate the system with **real money at minimum risk**. This phase catches issues that testnet/demo cannot: real slippage, real fee structures, real network conditions, and psychological factors.

### 3.2 Switching from Testnet to Live

#### 3.2.1 Get Live API Keys

**Binance:**
1. Log into **https://www.binance.com**
2. Go to **API Management** → **Create API**
3. Enable **Spot Trading** (disable Withdrawals for safety)
4. Set IP restrictions if possible
5. Save API Key and Secret

**MT5:**
1. Open a **live account** with your broker
2. Fund the minimum deposit
3. Note the live server name (e.g., "FXPesa-Live" vs "FXPesa-Demo")

#### 3.2.2 Configuration Changes

**The only change needed:** flip `sandbox` from `true` to `false`.

```bash
# .env — Phase 2: Live (tiny positions)
# CHANGE THESE:
CCXT_API_KEY=<your_LIVE_api_key>      # ← Production key
CCXT_SECRET=<your_LIVE_secret_key>    # ← Production secret
CCXT_SANDBOX=false                     # ← CRITICAL: disable sandbox

# Risk — very conservative for Phase 2
RISK_MAX_DRAWDOWN_PCT=5.0             # ← Tighter than Phase 1
RISK_MAX_POSITION_SIZE_PCT=1.0        # ← Much smaller positions
RISK_MAX_DAILY_LOSS_PCT=1.5           # ← Tighter daily limit
RISK_MAX_OPEN_POSITIONS=2             # ← Fewer concurrent positions
RISK_MAX_LEVERAGE=1.0                  # ← No leverage initially

# Trading — limit to most liquid pairs
# (edit alphastack.yaml or override via env)
```

**YAML override:**

```yaml
# config/alphastack.local.yaml — Phase 2
env: dev

ccxt:
  exchange: binance
  sandbox: false                       # ← LIVE mode
  # Credentials from env vars

risk:
  max_drawdown_pct: 5.0
  max_position_size_pct: 1.0
  max_daily_loss_pct: 1.5
  max_open_positions: 2
  max_leverage: 1.0
  stop_loss_atr_multiplier: 2.0

trading:
  symbols:
    - BTC/USDT                         # Start with ONE pair only
  timeframes:
    - 1h
    - 4h
  default_timeframe: 1h
```

#### 3.2.3 Code Changes Required

**None.** The `CCXTConnector` handles both testnet and live identically. The only difference is:

```python
# ccxt_connector.py line ~75
if self._sandbox:
    self._exchange.set_sandbox_mode(True)  # Testnet URLs
# else: uses production URLs automatically
```

#### 3.2.4 Minimum Viable Position Sizes

| Exchange | Asset | Minimum Order | Approx USD Value |
|----------|-------|---------------|------------------|
| Binance Spot | BTC/USDT | 0.00001 BTC | ~$0.67 |
| Binance Spot | ETH/USDT | 0.001 ETH | ~$3.50 |
| Binance Spot | BNB/USDT | 0.001 BNB | ~$0.60 |
| MT5 (Forex) | EUR/USD | 0.01 lots (1,000 units) | ~$10 margin |

**Recommended Phase 2 starting sizes:**
- Crypto: **$5-10 per position** (smallest possible above exchange minimum)
- Forex: **0.01 lots** (micro lot, ~$10 margin with 1:100 leverage)

#### 3.2.5 Commands to Switch

```bash
# 1. Stop the trading engine
docker compose stop trading-engine

# 2. Update credentials (create a new .env or update existing)
export CCXT_API_KEY="your_LIVE_api_key"
export CCXT_SECRET="your_LIVE_secret_key"
export CCXT_SANDBOX="false"

# 3. Verify connection WITHOUT placing orders first
docker compose up -d api
curl http://localhost:8000/api/v1/system/status | python3 -m json.tool

# 4. Verify balance is correct
curl -s http://localhost:8000/api/v1/portfolio/balance | python3 -m json.tool

# 5. Restart engine
docker compose --profile engine up -d trading-engine

# 6. Monitor closely
docker compose logs -f trading-engine
```

### 3.3 Risk Parameters for Phase 2

```python
# These values are set in config and enforced by RiskGovernor
# The governor runs 7 sequential gates (see risk/governor.py):

PHASE_2_RISK_PARAMS = {
    "max_drawdown_pct": 5.0,          # Total equity drawdown halt
    "max_daily_loss_pct": 1.5,        # Daily loss circuit breaker
    "max_position_size_pct": 1.0,     # Max single position as % of equity
    "max_open_positions": 2,           # Concurrent position limit
    "max_correlation": 0.7,            # Cross-position correlation cap
    "max_leverage": 1.0,               # No leverage
    "stop_loss_atr_multiplier": 2.0,   # SL = 2x ATR from entry
    "risk_free_rate": 0.05,            # For Sharpe calculations
}
```

### 3.4 Monitoring During Phase 2

#### 3.4.1 What to Watch

| Monitor | How | Alert Threshold |
|---------|-----|----------------|
| **Equity curve** | Portfolio API / Grafana | Any single day > -1.5% |
| **Open positions** | `GET /api/v1/portfolio/positions` | More than 2 positions |
| **Order fills** | Logs + trade API | Any rejected order |
| **Circuit breaker** | `GET /api/v1/system/status` | Any trip |
| **Spread** | Tick data logging | Spread > 2x average |
| **Slippage** | Compare fill vs expected | Slippage > 0.2% |
| **Connection** | Health endpoint | Any disconnection >1min |

#### 3.4.2 Quick Monitoring Commands

```bash
# Watch equity in real-time
watch -n 5 'curl -s http://localhost:8000/api/v1/portfolio/balance | python3 -m json.tool'

# Watch for new trades
watch -n 10 'curl -s "http://localhost:8000/api/v1/trades?status=open" | python3 -m json.tool'

# Watch risk status
watch -n 5 'curl -s http://localhost:8000/api/v1/system/status | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d.get(\"risk_status\",{}), indent=2))"'

# Tail engine logs with error filtering
docker compose logs -f trading-engine | grep -E "(ERROR|WARNING|circuit_breaker|trade_approved|trade_rejected)"
```

### 3.5 Phase 2 Exit Criteria

All of the following must be true for **at least 14 consecutive days**:

- [ ] Real money P&L is positive or within expected backtest drawdown range
- [ ] Zero circuit breaker false positives
- [ ] Risk governor correctly sized/rejected all trades
- [ ] Slippage matches Phase 1 observations (±50%)
- [ ] Fee impact is accounted for in P&L calculations
- [ ] No manual interventions were needed
- [ ] Fill rate >98% (live markets are more liquid than testnet)
- [ ] The system survived at least one "volatile day" without breaking
- [ ] At least 20 trades executed (for statistical significance)

---

## 4. Phase 3: Live Trading

### 4.1 Goal

Scale up position sizes and capital deployment with full monitoring, alerting, and circuit breaker protection.

### 4.2 Scaling Up Position Sizes

#### 4.2.1 The Escalation Ladder

```
Week 1-2:  $50-100 total capital, 1% risk per trade
Week 3-4:  $200-500 total capital, 1% risk per trade
Week 5-8:  $500-2000 total capital, 1.5% risk per trade
Week 9-12: $2000-5000 total capital, 1.5% risk per trade
Month 4+:  Scale based on proven track record, max 2% risk per trade
```

#### 4.2.2 Configuration for Phase 3

```bash
# .env — Phase 3: Full live trading
CCXT_SANDBOX=false

# Risk — production values (from architecture_broker.md)
RISK_MAX_DRAWDOWN_PCT=15.0
RISK_MAX_POSITION_SIZE_PCT=5.0
RISK_MAX_DAILY_LOSS_PCT=3.0
RISK_MAX_OPEN_POSITIONS=10
RISK_MAX_CORRELATION=0.7
RISK_MAX_LEVERAGE=2.0
RISK_STOP_LOSS_ATR_MULTIPLIER=2.0

# Trading — full symbol list
# (symbols defined in alphastack.yaml trading.symbols)
```

**YAML config:**

```yaml
# config/alphastack.local.yaml — Phase 3
env: prod

ccxt:
  exchange: binance
  sandbox: false

risk:
  max_drawdown_pct: 15.0
  max_position_size_pct: 5.0
  max_daily_loss_pct: 3.0
  max_open_positions: 10
  max_correlation: 0.7
  max_leverage: 2.0
  stop_loss_atr_multiplier: 2.0

trading:
  symbols:
    - BTC/USDT
    - ETH/USDT
    - EUR/USD
    - AAPL
    - SPY
  timeframes:
    - 1m
    - 5m
    - 15m
    - 1h
    - 4h
    - 1d
  default_timeframe: 1h
```

### 4.3 Risk Management Escalation

#### 4.3.1 The RiskGovernor Pipeline

The `RiskGovernor` (in `src/alphastack/risk/governor.py`) runs **7 sequential gates** on every trade:

```
Gate 0: Global halt check          → Is trading manually halted?
Gate 1: Trade sanity validation     → Are SL/TP/size values valid?
Gate 2: Circuit breaker check       → Has daily loss / consecutive loss tripped?
Gate 3: Drawdown limit check        → Has total drawdown breached limit?
Gate 4: Exposure limit check        → Would this exceed max positions / leverage?
Gate 5: Correlation check           → Is this correlated with existing positions?
Gate 6: Position sizing             → Adjust size down if needed
Gate 7: Minimum viable size         → Is adjusted size above exchange minimum?
```

Every gate is a **hard stop** — failure means rejection, not a suggestion.

#### 4.3.2 Circuit Breaker System

The `CircuitBreaker` (in `src/alphastack/risk/circuit_breaker.py`) has **4 independent breakers**:

| Breaker | Trigger | Action |
|---------|---------|--------|
| **Daily Loss** | Daily P&L < -3% of balance | Halt trading, 30min cooldown |
| **Consecutive Loss** | 5 losing trades in a row | Halt trading, 30min cooldown |
| **Volatility** | Return z-score ≥ 3.0 | Halt trading, 30min cooldown |
| **Black Swan** | Return z-score ≥ 5.0 | Emergency halt, manual reset required |

**To manually halt trading:**

```bash
# Via API
curl -X POST http://localhost:8000/api/v1/system/halt \
  -H "Content-Type: application/json" \
  -d '{"reason": "Manual halt - investigating issue"}'

# Or just stop the engine
docker compose stop trading-engine
```

**To resume after cooldown:**

```bash
# Via API (respects 30-min cooldown)
curl -X POST http://localhost:8000/api/v1/system/resume

# Force reset (bypasses cooldown — use with caution)
curl -X POST http://localhost:8000/api/v1/system/force-resume
```

### 4.4 Monitoring & Alerting Setup

#### 4.4.1 Essential Monitoring Stack

```
┌──────────────────────────────────────────────────────────────┐
│                    MONITORING ARCHITECTURE                     │
│                                                                │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐               │
│  │ AlphaStack│───▶│Prometheus│───▶│ Grafana  │               │
│  │  (metrics)│    │ (scrape) │    │(dashbrd) │               │
│  └──────────┘    └──────────┘    └──────────┘               │
│                                                                │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐               │
│  │ structlog│───▶│  Loki    │───▶│ Grafana  │               │
│  │  (logs)  │    │ (aggr.)  │    │ (logs)   │               │
│  └──────────┘    └──────────┘    └──────────┘               │
│                                                                │
│  ┌──────────┐    ┌──────────┐                                │
│  │ RiskGov. │───▶│ Telegram │  ← Critical alerts             │
│  │ events   │    │ /Email   │                                │
│  └──────────┘    └──────────┘                                │
└──────────────────────────────────────────────────────────────┘
```

#### 4.4.2 Key Metrics to Export

```python
# Add to your monitoring setup (prometheus_client is already in dependencies)

from prometheus_client import Gauge, Counter, Histogram

# Trading metrics
equity_gauge = Gauge('alphastack_equity_usd', 'Current account equity')
daily_pnl_gauge = Gauge('alphastack_daily_pnl_pct', 'Daily P&L percentage')
drawdown_gauge = Gauge('alphastack_drawdown_pct', 'Current drawdown percentage')
open_positions_gauge = Gauge('alphastack_open_positions', 'Number of open positions')

# Execution metrics
orders_total = Counter('alphastack_orders_total', 'Total orders', ['status', 'broker'])
order_latency = Histogram('alphastack_order_latency_seconds', 'Order execution latency')
slippage_histogram = Histogram('alphastack_slippage_pct', 'Order slippage percentage')

# Risk metrics
circuit_breaker_state = Gauge('alphastack_circuit_breaker', 'Circuit breaker state (0=ok, 1=tripped)')
risk_rejections = Counter('alphastack_risk_rejections_total', 'Risk rejections', ['reason'])

# Connection metrics
broker_connection = Gauge('alphastack_broker_connected', 'Broker connection state', ['broker'])
```

#### 4.4.3 Grafana Dashboard Panels

Essential panels for your Grafana dashboard:

1. **Equity Curve** — Real-time equity over time
2. **Daily P&L** — Bar chart of daily returns
3. **Drawdown** — Current drawdown from peak
4. **Open Positions** — Table with symbol, side, size, P&L
5. **Order Activity** — Recent fills, rejections, cancellations
6. **Risk Governor** — Current risk score, breaker states
7. **Execution Latency** — P50/P95/P99 order latency
8. **Connection Status** — Green/red for each broker

### 4.5 Kill Switches

#### 4.5.1 Software Kill Switches

```bash
# Method 1: API halt (preferred)
curl -X POST http://localhost:8000/api/v1/system/halt \
  -H "Content-Type: application/json" \
  -d '{"reason": "Emergency stop"}'

# Method 2: Stop the engine container
docker compose stop trading-engine

# Method 3: Revoke API keys (nuclear option)
# Log into Binance → API Management → Delete API Key
# This instantly prevents any order from being placed
```

#### 4.5.2 Hardware Kill Switches

For production deployments, consider:
- A physical button/script that SSHs into the server and stops the container
- A Telegram bot command `/halt` that triggers the API halt endpoint
- Binance API key with **Spot Trading only** (no withdrawal permissions)

#### 4.5.3 Automated Emergency Close

The `RiskGovernor` can trigger emergency position closure:

```python
# In your monitoring/alerting code:
from alphastack.risk.governor import RiskGovernor, RiskEventType

def on_risk_event(event):
    if event.event_type == RiskEventType.CIRCUIT_BREAKER_TRIGGERED:
        # Close all positions immediately
        # Send alert
        send_telegram_alert(f"🚨 Circuit breaker tripped: {event.details}")
    elif event.event_type == RiskEventType.DRAWDOWN_BREACH:
        # Emergency close all
        send_telegram_alert(f"🔴 Drawdown breach: {event.details}")
```

---

## 5. Binance Testnet vs Production Reference

### 5.1 Key Differences

| Feature | Testnet (`testnet.binance.vision`) | Production (`api.binance.com`) |
|---------|-----------------------------------|-------------------------------|
| **Base URL** | `https://testnet.binance.vision` | `https://api.binance.com` |
| **API Keys** | Separate keys (generate at testnet site) | Real Binance API keys |
| **Funds** | Virtual (unlimited, resettable) | Real money |
| **Market Data** | Delayed/synthetic (not real-time) | Real-time |
| **Liquidity** | Very low (few users) | Deep, real market |
| **Order Book** | Thin, unrealistic | Real supply/demand |
| **Slippage** | Minimal (thin book) | Realistic |
| **Fees** | Charged but virtual | Real fees (0.1% spot) |
| **Rate Limits** | Same as production | 1200 req/min (weight) |
| **WebSocket** | Supported but less stable | Production-grade |
| **Symbols** | Limited subset | All listed pairs |
| **Precision** | Same as production | Exchange-specific |

### 5.2 Testnet Limitations to Be Aware Of

1. **Unrealistic fills**: Testnet orders fill instantly at the displayed price. Real markets have slippage.
2. **No real news impact**: Testnet prices don't react to real-world events.
3. **Limited symbols**: Not all trading pairs are available on testnet.
4. **WebSocket instability**: Testnet WebSocket connections drop more frequently.
5. **Reset potential**: Testnet can be reset by Binance without notice.

### 5.3 What Testnet Validates vs What It Doesn't

| Validated by Testnet ✅ | NOT Validated by Testnet ❌ |
|------------------------|---------------------------|
| API connectivity | Real slippage |
| Order structure (valid requests) | Real fee impact |
| Authentication flow | Real market liquidity |
| Basic execution flow | Real network latency |
| Risk governor logic | Psychological pressure |
| Position tracking | Exchange-specific quirks under load |
| WebSocket connectivity | Partial fill handling |

---

## 6. CCXT Sandbox Mode Deep Dive

### 6.1 How CCXT Sandbox Works

When you call `exchange.set_sandbox_mode(True)`, CCXT internally changes the exchange's base URL:

```python
# Inside ccxt library (simplified):
class binance(Exchange):
    def set_sandbox_mode(self, enabled):
        if enabled:
            self.urls['api'] = {
                'public': 'https://testnet.binance.vision/api/v3',
                'private': 'https://testnet.binance.vision/api/v3',
                # ... etc
            }
        else:
            self.urls['api'] = {
                'public': 'https://api.binance.com/api/v3',
                'private': 'https://api.binance.com/api/v3',
                # ... etc
            }
```

### 6.2 Exchange-by-Exchange Sandbox URLs

| Exchange | Sandbox URL | Notes |
|----------|-------------|-------|
| Binance | `testnet.binance.vision` | Separate key generation |
| Bybit | `api-testnet.bybit.com` | Unified testnet |
| OKX | Same URL, testnet flag | Uses `x-simulated-trading: 1` header |
| Kraken | No official sandbox | Use paper trading mode |
| Coinbase | `api-public.sandbox.exchange.coinbase.com` | Sandbox keys |

### 6.3 AlphaStack CCXT Connector Flow

```
User sets CCXT_SANDBOX=true
         │
         ▼
CCXTConnector.__init__()
  └─ self._sandbox = True (from config)
         │
         ▼
CCXTConnector.connect()
  ├─ exchange_class = ccxt_async.binance
  ├─ self._exchange = exchange_class({apiKey, secret, ...})
  ├─ if self._sandbox:
  │     self._exchange.set_sandbox_mode(True)  ← URL swap
  └─ await self._exchange.load_markets()
         │
         ▼
All subsequent API calls use testnet URLs
  - place_order() → testnet.binance.vision/api/v3/order
  - get_balance() → testnet.binance.vision/api/v3/account
  - etc.
```

---

## 7. Monitoring & Alerting Setup

### 7.1 Structured Logging

AlphaStack uses `structlog` for JSON-structured logs. Key log events to monitor:

```bash
# Trade events
docker compose logs trading-engine | grep -E "trade_approved|trade_rejected|order_placed|order_filled"

# Risk events
docker compose logs trading-engine | grep -E "circuit_breaker|drawdown|exposure|correlation"

# Connection events
docker compose logs trading-engine | grep -E "ccxt_connected|ccxt_disconnected|connection_state"

# Errors
docker compose logs trading-engine | grep -E "ERROR|CRITICAL|exception"
```

### 7.2 Telegram Alert Bot (Example)

```python
# scripts/alert_bot.py
import httpx
import asyncio
from alphastack.risk.governor import RiskEvent, RiskEventType

TELEGRAM_BOT_TOKEN = "your_bot_token"
TELEGRAM_CHAT_ID = "your_chat_id"

async def send_alert(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    await httpx.AsyncClient().post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
    })

def risk_event_handler(event: RiskEvent):
    severity_emoji = {
        "info": "ℹ️",
        "warning": "⚠️",
        "critical": "🚨",
    }
    emoji = severity_emoji.get(event.severity, "📢")

    message = (
        f"{emoji} *AlphaStack Risk Alert*\n"
        f"Type: `{event.event_type.value}`\n"
        f"Symbol: {event.symbol}\n"
        f"Details: {event.details}"
    )

    asyncio.create_task(send_alert(message))
```

### 7.3 Health Check Endpoint

The FastAPI app exposes health at `GET /health`:

```bash
# Basic health check
curl http://localhost:8000/health

# Detailed system status
curl http://localhost:8000/api/v1/system/status
```

---

## 8. Risk Parameter Evolution Table

| Parameter | Phase 1 (Paper) | Phase 2 (Forward) | Phase 3 (Live Start) | Phase 3 (Scaled) |
|-----------|-----------------|--------------------|-----------------------|-------------------|
| `max_drawdown_pct` | 10.0 | 5.0 | 15.0 | 15.0 |
| `max_position_size_pct` | 2.0 | 1.0 | 5.0 | 5.0 |
| `max_daily_loss_pct` | 2.0 | 1.5 | 3.0 | 3.0 |
| `max_open_positions` | 3 | 2 | 10 | 10 |
| `max_correlation` | 0.7 | 0.7 | 0.7 | 0.7 |
| `max_leverage` | 1.0 | 1.0 | 2.0 | 2.0 |
| `stop_loss_atr_multiplier` | 2.0 | 2.0 | 2.0 | 2.0 |
| `CCXT_SANDBOX` | `true` | `false` | `false` | `false` |
| Symbols | BTC/USDT, ETH/USDT | BTC/USDT only | All configured | All configured |
| Capital at risk | $0 | $50-200 | $200-500 | $500+ |

---

## 9. Troubleshooting & Common Issues

### 9.1 Connection Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| `ccxt_exchange_not_available` | Wrong exchange ID | Check `CCXT_EXCHANGE` value (lowercase) |
| `AuthenticationError` | Bad API key/secret | Regenerate keys, check for whitespace |
| `ccxt_sandbox_enabled but orders fail` | Testnet keys used on live (or vice versa) | Verify key source matches sandbox setting |
| `Rate limit exceeded` | Too many API calls | Reduce polling frequency, check `rate_limit` param |

### 9.2 Order Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| `InsufficientFunds` | Balance too low for minimum order | Check minimum order sizes, reduce quantity |
| `InvalidOrder` | Price/size precision wrong | CCXT handles this, but check exchange filters |
| `Order immediately filled on testnet` | Testnet has no real order book | Expected behavior — move to Phase 2 for realistic fills |

### 9.3 Risk Governor Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| All trades rejected | Risk params too tight | Temporarily loosen limits, investigate which gate fails |
| Circuit breaker trips on first trade | Daily loss calculation bug | Check `record_trade_result()` is called correctly |
| Position size always 0 | `max_position_size_pct` too low | Increase or check account balance is set correctly |

### 9.4 Docker Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| `timescaledb` not healthy | Port conflict or disk full | Check `docker compose logs timescaledb` |
| `api` container restarts | Missing env vars | Verify `.env` file or `environment` in compose |
| `trading-engine` won't start | Missing dependencies | Rebuild: `docker compose build --no-cache` |

---

## Appendix A: Quick Reference Commands

```bash
# === PHASE 1: Paper Trading ===
export CCXT_SANDBOX=true
docker compose up -d
curl http://localhost:8000/health

# === PHASE 2: Forward Testing ===
export CCXT_SANDBOX=false
export CCXT_API_KEY="live_key"
export CCXT_SECRET="live_secret"
docker compose restart api trading-engine

# === PHASE 3: Live Trading ===
# Same as Phase 2, adjust risk params in config

# === Emergency Stop ===
curl -X POST http://localhost:8000/api/v1/system/halt \
  -d '{"reason": "Emergency"}'

# === View Logs ===
docker compose logs -f trading-engine

# === Check Status ===
curl http://localhost:8000/api/v1/system/status
```

## Appendix B: Environment Variable Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `ALPHASTACK_ENV` | `dev` | Environment: `dev`, `staging`, `prod` |
| `CCXT_EXCHANGE` | `binance` | Exchange ID (lowercase) |
| `CCXT_API_KEY` | `""` | Exchange API key |
| `CCXT_SECRET` | `""` | Exchange API secret |
| `CCXT_SANDBOX` | `false` | Use exchange testnet |
| `MT5_LOGIN` | `0` | MT5 account login |
| `MT5_PASSWORD` | `""` | MT5 password |
| `MT5_SERVER` | `""` | MT5 server name |
| `DB_HOST` | `localhost` | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_NAME` | `alphastack` | Database name |
| `REDIS_HOST` | `localhost` | Redis host |
| `REDIS_PORT` | `6379` | Redis port |
| `RISK_MAX_DRAWDOWN_PCT` | `15.0` | Max total drawdown % |
| `RISK_MAX_POSITION_SIZE_PCT` | `5.0` | Max position size % |
| `RISK_MAX_DAILY_LOSS_PCT` | `3.0` | Max daily loss % |
| `RISK_MAX_OPEN_POSITIONS` | `10` | Max concurrent positions |
| `RISK_MAX_LEVERAGE` | `2.0` | Max leverage |
| `API_HOST` | `0.0.0.0` | API server host |
| `API_PORT` | `8000` | API server port |
| `LOGGING_LEVEL` | `INFO` | Log level |

---

*This document is the operational guide for transitioning AlphaStack from paper trading to live capital deployment. Every phase is a gate — do not skip phases, and do not proceed until all exit criteria are met. The risk governor is your safety net; trust it over any strategy's conviction.*
