# AlphaStack — Comprehensive System Architecture Analysis

> **Analysis Date:** 2026-07-15
> **Scope:** Full codebase analysis of `src/alphastack/` and `architecture/` docs
> **Analyst:** Automated deep analysis

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Tech Stack Details](#2-tech-stack-details)
3. [Multi-Agent Orchestration](#3-multi-agent-orchestration)
4. [Trading Strategy Pipeline](#4-trading-strategy-pipeline)
5. [Risk Management System](#5-risk-management-system)
6. [Broker Integration](#6-broker-integration)
7. [Data Pipeline](#7-data-pipeline)
8. [AI/ML Models](#8-aiml-models)
9. [Reasoning & Explainability](#9-reasoning--explainability)
10. [Security Architecture](#10-security-architecture)
11. [API Layer](#11-api-layer)
12. [Cognitive Loops](#12-cognitive-loops)
13. [Implementation Status Assessment](#13-implementation-status-assessment)
14. [Key Design Decisions & Trade-offs](#14-key-design-decisions--trade-offs)
15. [Risks & Recommendations](#15-risks--recommendations)

---

## 1. Architecture Overview

AlphaStack is a **multi-agent AI-powered trading system** built around a 16-step strategy pipeline, orchestrated via LangGraph, with institutional-grade risk management. The system targets both forex (via MetaTrader 5) and crypto (via CCXT-compatible exchanges).

### High-Level Data Flow

```
Market Data Feeds ──▶ Data Pipeline (ingestion/aggregation)
                            │
                            ▼
              ┌─────────────────────────────┐
              │   LangGraph Orchestrator     │
              │                              │
              │  news ──▶ strategy ──▶ risk  │
              │                    │         │
              │         ┌──────────┤         │
              │         ▼          ▼         │
              │   human_review  execution    │
              │         │          │         │
              │         └────┬─────┘         │
              │              ▼               │
              │         reflection           │
              └─────────────────────────────┘
                            │
                            ▼
              Broker Connectors (MT5/CCXT) ──▶ Exchanges
```

### Core Design Principles

1. **One agent, one job** — each agent is a specialist (strategy, risk, execution, news, reflection)
2. **Risk is infrastructure-level** — enforced by code gates, not prompts or LLM decisions
3. **Every trade has an auditable reasoning chain** — ReAct traces stored permanently
4. **Self-improvement built in** — reflection and learning loops run continuously
5. **Graceful degradation** — agent failure pauses trading rather than guessing

---

## 2. Tech Stack Details

### Python Dependencies (from code imports)

| Category | Libraries | Purpose |
|----------|-----------|---------|
| **Orchestration** | `langchain_core`, `langgraph` | Multi-agent graph execution, state management |
| **Web Framework** | `fastapi`, `uvicorn` | REST API, WebSocket server |
| **Database** | `sqlalchemy` (async), `asyncpg`, `psycopg2` | PostgreSQL/TimescaleDB ORM |
| **Cache/Events** | `redis` (async), `redis.asyncio` | Event bus (Streams), caching, pub/sub |
| **Broker - Crypto** | `ccxt`, `ccxt.async_support`, `ccxt.pro` | 104+ crypto exchange connectivity |
| **Broker - Forex** | `MetaTrader5` (optional, Windows-only) | MT5 terminal integration |
| **Messaging** | `pyzmq` (ZeroMQ) | MQL5 bridge for MT5 Expert Advisor |
| **ML/AI** | `torch`, `numpy`, `pandas`, `onnxruntime` | Model training, inference, feature engineering |
| **Security** | `cryptography`, `argon2-cffi`, `pyjwt`, `pyotp` | AES-256-GCM encryption, Argon2id hashing, JWT, TOTP 2FA |
| **HTTP Client** | `httpx` | Async HTTP for data feeds, news APIs |
| **Config** | `pydantic`, `pydantic-settings` | Type-safe configuration with env vars |
| **Logging** | `structlog`, `prometheus_client` | Structured JSON logging, Prometheus metrics |
| **Data Feeds** | Polygon.io, Alpha Vantage, Finnhub APIs | Market data, news feeds |

### Rust Integration

The system includes a **PyO3 Rust bridge** (`alphastack_rust_core`) for performance-critical paths:

- **TickProcessor** — real-time tick aggregation into candles with volume profile
- **Indicators** — RSI, VWAP (native speed)
- **SignalEngine** — confluence score computation
- **OrderBookAnalyzer** — order book snapshot analysis
- **RiskCalculator** — Kelly fraction, position sizing, Sharpe ratio
- **BacktestEngine** — backtesting with fees/slippage

**Fallback**: Full pure-Python implementations exist for every Rust class, so the system runs without the native module (with degraded performance). The `RUST_AVAILABLE` flag controls which path is taken.

### Infrastructure

- **Database**: PostgreSQL + TimescaleDB (hypertables for time-series OHLCV/tick data)
- **Cache/Streams**: Redis (Streams for event bus, key-value for caching, pub/sub for alerts)
- **Monitoring**: Prometheus metrics, structured JSON logging to files

---

## 3. Multi-Agent Orchestration

### Agent Architecture

The orchestrator is built on **LangGraph StateGraph** with 5 specialized agents:

| Agent | Role | Runs |
|-------|------|------|
| **NewsAgent** | Detect high-impact events, compute risk adjustment multiplier | First (entry point) |
| **StrategyAgent** | Run 16-step pipeline, generate trade signals | Second |
| **RiskAgent** | Evaluate signals against risk limits, approve/reject | Third |
| **ExecutionAgent** | Route approved orders to broker connectors | Fourth (if approved) |
| **ReflectionAgent** | Post-trade analysis, performance metrics, learning | Fifth (after execution) |

### Graph Flow

```
START → news → strategy → risk → [conditional]
                                    ├── approved → human_review → [conditional]
                                    │                                ├── approved → execution → reflection → END
                                    │                                └── rejected → END
                                    └── rejected (circuit breaker / no signals) → END
```

### Shared State (`AlphaStackState`)

A Pydantic model flows through all nodes containing:
- `market_data` — OHLCV, order book, tick data
- `signals` — trade signals from strategy agent
- `trade_decisions` — approved/rejected decisions from risk agent
- `risk_status` — drawdown, exposure, circuit breaker state
- `news_alerts` — detected high-impact events
- `execution_log` — order fill records
- `performance_summary` — post-trade metrics
- `agent_messages` — inter-agent communication log

### Agent Base Class (`AlphaStackAgent`)

All agents inherit from an abstract base providing:
- **Identity**: name, role, description, agent_id
- **ReAct loop pattern**: Think → Act → Observe cycle
- **Working memory**: observations, decisions, reflections (in-memory)
- **Event publishing**: publishes `AgentEvent` to the Redis event bus
- **Timing & error handling**: automatic elapsed_ms tracking, error event publishing

### Human-in-the-Loop

The orchestrator supports an optional `human_review` node using LangGraph's `interrupt()` mechanism. When enabled:
- Risk-approved trades pause for human review
- Human can approve ("approve", "yes", "go") or reject with feedback
- Rejection changes all approved decisions to rejected status

---

## 4. Trading Strategy Pipeline

### 16-Step Pipeline Architecture

The `AlphaStackPipeline` runs 16 sequential steps, with steps 5-9 parallelizable:

| Step | Name | Description | Status |
|------|------|-------------|--------|
| 1 | **Fundamental Intelligence** | Economic calendar, news sentiment, macro regime detection (risk_on/risk_off/mixed) | ✅ Implemented |
| 2 | **Market Bias** | Multi-timeframe trend analysis, higher-timeframe bias via MA crossovers | ✅ Implemented |
| 3 | **Session Analysis** | London/NY/Asian session detection, session-specific volatility profiles | ✅ Implemented |
| 4 | **Market Structure** | HH/HL/LH/LL swing detection, Break of Structure (BOS), Change of Character (CHoCH) | ✅ Implemented |
| 5 | **Support & Resistance** | Price bucketing to round numbers, swing-based S/R, strength scoring | ✅ Implemented |
| 6 | **Liquidity Detection** | Equal highs/lows, stop clusters, liquidity pool mapping with deduplication | ✅ Implemented |
| 7 | **Smart Money Concepts** | Order blocks (bullish/bearish), Fair Value Gaps (3-candle imbalance), breaker blocks | ✅ Implemented |
| 8 | **RSI Confirmation** | RSI with Wilder smoothing, overbought/oversold zones, divergence detection | ✅ Implemented |
| 9 | **Candlestick Confirmation** | Engulfing, pin bar, hammer, shooting star, doji, morning/evening star patterns | ✅ Implemented |
| 10 | **Confluence Engine** | Weighted scoring of steps 1-9 (9 component weights summing to 1.0), direction decision | ✅ Implemented |
| 11 | **Position Sizing** | Risk-based sizing with ATR stop distance, spread cost awareness | ✅ Implemented |
| 12 | **Stop Loss** | Structure-based (swing points) and ATR-based stops, takes wider/conservative | ✅ Implemented |
| 13 | **Take Profit** | R:R multipliers (1.5x, 2.5x, 4.0x), partial TP levels, S/R override | ✅ Implemented |
| 14 | **Trade Management** | Breakeven at 1R, ATR trailing stop at 1.5R, partial close at TP1 | ✅ Implemented |
| 15 | **Exit Conditions** | Time-based exit (48h max), structure flip, RSI reversal, confluence drop, SL hit | ✅ Implemented |
| 16 | **Trade Journal** | Structured logging, tag generation, JSON-line output for aggregation | ✅ Implemented |

### Confluence Weights

```python
_WEIGHTS = {
    "fundamental": 0.05,   # News/sentiment
    "market_bias": 0.15,   # Multi-TF trend
    "session": 0.05,       # Session volatility
    "structure": 0.20,     # HH/HL/LH/LL (highest weight)
    "sr_levels": 0.10,     # Key levels
    "liquidity": 0.10,     # Liquidity pools
    "smc": 0.15,           # Order blocks/FVGs
    "rsi": 0.10,           # Momentum
    "candlestick": 0.10,   # Pattern confirmation
}
```

### Pipeline Context (`AlphaStackContext`)

An **immutable** Pydantic model (frozen=True) that flows through all 16 steps. Each step returns a new copy via `context.update()`. Contains typed sub-models for every step's output: `FundamentalData`, `MarketBias`, `SessionData`, `StructureData`, `SRLevels`, `LiquidityPool`, `SMCData`, `RSIData`, `CandlestickData`, `ConfluenceResult`, `PositionSizing`, `StopLoss`, `TakeProfit`, `TradeManagement`, `ExitSignal`, `JournalEntry`.

---

## 5. Risk Management System

### Architecture: 7 Independent Risk Sub-Systems

The risk system is the **immune system** of AlphaStack — hard limits, not guidelines.

#### 5.1 Risk Governor (`RiskGovernor`)

Central controller coordinating all risk checks. Single entry point: `approve_trade(request) → TradeApproval`.

**7-gate approval pipeline:**
1. **Global halt** — is trading halted?
2. **Trade validation** — price/size/direction sanity checks
3. **Circuit breakers** — any breaker tripped?
4. **Drawdown limits** — daily/weekly/total breach?
5. **Exposure limits** — max positions, per-pair, per-session, leverage
6. **Correlation check** — correlated double-up prevention
7. **Position sizing** — risk-adjusted size (may reduce)

#### 5.2 Position Sizer (`PositionSizer`)

- **Fixed-risk sizing**: risk X% of account per trade
- **Kelly criterion**: half-Kelly for safety (W - (1-W)/R, halved)
- **Spread-cost aware**: reduces size if spread > 30% of risk budget (critical for small accounts)
- **Progressive de-escalation**: risk reduces as drawdown increases:
  - 0-2% drawdown: full risk
  - 2-5%: 50% risk
  - 5-10%: 25% risk
  - >10%: 10% risk

#### 5.3 Drawdown Manager (`DrawdownManager`)

Tracks daily, weekly, and total drawdown from peak equity:
- **Hard limits**: 3% daily, 7% weekly, 15% total (configurable)
- **Risk multiplier**: progressive reduction as drawdown approaches limits
- **Auto-reset**: daily/weekly counters reset at period boundaries

#### 5.4 Circuit Breaker (`CircuitBreaker`)

Four independent breakers, any single trip halts all trading:
- **Daily loss breaker**: daily P&L exceeds threshold
- **Consecutive loss breaker**: 5+ consecutive losses
- **Volatility breaker**: z-score ≥ 3.0 on recent returns
- **Black swan detector**: z-score ≥ 5.0

Features 30-minute cooldown after trip (manual reset or force_reset for admin override).

#### 5.5 Correlation Monitor (`CorrelationMonitor`)

- Pre-loaded correlation matrix for major forex pairs (EUR/USD↔GBP/USD: 0.85, EUR/USD↔USD/CHF: -0.90, etc.)
- Prevents correlated double-ups (same-direction highly-correlated pairs)
- Limits same-direction exposure count (max 3)
- Live correlation update support

#### 5.6 Exposure Manager (`ExposureManager`)

- Max open positions (default: 10)
- Max per-pair exposure (20% of account)
- Max per-session exposure (40% of account)
- Max leverage (2.0x)

#### 5.7 Tail Risk Manager (`TailRiskManager`)

- **CVaR calculation**: Historical, Parametric (normal), and Cornish-Fisher (skew/kurtosis-adjusted) methods
- **Stress testing**: 7 historical crisis scenarios (GFC 2008, Flash Crash 2010, CHF Unpeg 2015, Brexit 2016, COVID 2020, LUNA 2022, SVB 2023)
- **Reverse stress testing**: "What would it take to lose X%?"
- **Limits**: max CVaR 95% = 5%, max CVaR 99% = 10%, max stress loss = 25%

#### 5.8 Trade Validator (`TradeValidator`)

Pre-trade checks:
- Price sanity (not NaN, not zero, not absurd)
- Size sanity (positive, within broker limits)
- Direction validity
- Stop loss logic (correct side of entry, not too tight/wide)
- Take profit logic

Post-trade checks:
- Fill price vs expected (slippage analysis)
- Size reconciliation
- Unfavorable fill detection

#### 5.9 News Event Handler (`NewsEventHandler`)

Three-phase protocol:
- **Pre-event** (30min before): reduce exposure by 50%, widen stops
- **During**: halt new trading entirely
- **After** (15min cooldown): gradual resume at 75% exposure

Knows 10 high-impact event types (NFP, CPI, FOMC, ECB, BOE, BOJ, GDP, PMI, Retail Sales, Unemployment).

---

## 6. Broker Integration

### Supported Brokers

| Broker | Connector | Status | Use Case |
|--------|-----------|--------|----------|
| **MetaTrader 5** | `MT5Connector` | ✅ Implemented | Forex (EUR/USD, GBP/USD, etc.) |
| **CCXT (104+ exchanges)** | `CCXTConnector` | ✅ Implemented | Crypto (Binance, Bybit, MEXC, OKX, etc.) |
| **MQL5 Bridge** | `MQL5Bridge` | ✅ Implemented | ZeroMQ bridge to MT5 Expert Advisor |

### Broker Abstraction Layer

All connectors implement `BrokerConnector` ABC:
- **Lifecycle**: `connect()`, `disconnect()`, `reconnect()` with state machine (DISCONNECTED→CONNECTING→CONNECTED→RECONNECTING→ERROR)
- **Orders**: `place_order()`, `cancel_order()`, `modify_order()`
- **Account**: `get_positions()`, `get_balance()`
- **Market Data**: `get_tick()`, `get_bars()`
- **Retry**: exponential backoff (3 retries, 1-30s delay)

### Unified Domain Models

All broker responses map to broker-agnostic models:
- `BrokerOrder` — unified order with status lifecycle tracking
- `BrokerPosition` — position with P&L, leverage, margin
- `BrokerBalance` — account balance with margin details
- `BrokerTick` — bid/ask/last/volume/spread
- `BrokerBar` — OHLCV bar

### Smart Order Router (`SmartRouter`)

Evaluates brokers on 4 weighted criteria:
- **Cost** (40%): spread/commission
- **Fill quality** (30%): historical fill rate
- **Latency** (20%): response time
- **Reliability** (10%): uptime/error rate

Supports failover: tries primary broker, falls back to next-best on failure.

### Order Manager (`OrderManager`)

In-memory order registry with:
- Full lifecycle tracking (pending→open→partially_filled→filled/cancelled/rejected)
- Partial fill recording with weighted average price
- Persistence callbacks (fire-and-forget to DB)
- Snapshot/restore for crash recovery

### MQL5 Bridge

ZeroMQ-based bridge between Python and MT5 Expert Advisor:
- Bidirectional JSON messaging
- Heartbeat management (5s interval, 15s timeout)
- Trade signal sending (BUY, SELL, CLOSE, MODIFY, CLOSE_ALL)
- Account info and position tracking
- Background receive and heartbeat loops

### Broker Selection Heuristic

The `ExecutionAgent` selects brokers by symbol:
- Crypto pairs (contain `/`, `USDT`, `BTC`, `ETH`, etc.) → `ccxt`
- Everything else → `mt5`

---

## 7. Data Pipeline

### Market Data Ingestion (`MarketDataPipeline`)

Three-layer architecture:

1. **Ingestion Layer** — broker connectors stream raw ticks
2. **Aggregation Layer** — `CandleAggregator` builds OHLCV candles at multiple timeframes (M1, M5, M15, M30, H1, H4, D1, W1)
3. **Event Layer** — publishes `tick` and `candle_closed` events to in-process event bus

### Data Sources

| Source | Type | Status |
|--------|------|--------|
| **MT5** | Forex ticks, OHLCV bars | ✅ Implemented |
| **CCXT** | Crypto ticks, OHLCV bars, WebSocket streaming | ✅ Implemented |
| **Polygon.io** | News articles, market data | ✅ Implemented (API integration) |
| **Alpha Vantage** | Market data | Config key exists, connector placeholder |
| **Finnhub** | Market data | Config key exists, connector placeholder |

### Alternative Data (`AlternativeDataPipeline`)

- **On-chain**: Funding rates from Binance/Bybit APIs (live), whale alerts (placeholder)
- **Social sentiment**: Twitter/Reddit sentiment (placeholder — ready for API integration)
- **Google Trends**: Interest over time for financial keywords (placeholder)

### Feature Engineering (`FeatureEngineeringPipeline`)

Computes 20+ technical indicators on OHLCV DataFrames:
- **Moving Averages**: SMA(20,50), EMA(12,26)
- **Momentum**: RSI(14), MACD(12,26,9), Stochastic(14,3)
- **Volatility**: Bollinger Bands(20,2), ATR(14)
- **Trend**: ADX(14)
- **Volume**: VWAP
- **Derived**: price_change_pct, bb_width

Includes `FeatureNormalizer` (z-score or min-max) and `FeatureStore` (in-memory, Redis-backed).

### Storage (TimescaleDB)

- **OHLCV hypertable**: 1-day chunks, 7-day compression policy
- **Tick hypertable**: 1-hour chunks, 1-day compression policy
- Optimized queries for backtesting with time-range filters

### News Feed (`NewsFeed`)

- Fetches from Polygon.io `/v2/reference/news`
- Sentiment scoring via keyword-based `SentimentScorer` (FinBERT-ready — swap `score()` method)
- Macro event detection (NFP, CPI, FOMC, GDP, PMI, etc.) via pattern matching

---

## 8. AI/ML Models

### Current State: Architecture Complete, Implementation Partial

The architecture defines 8 model families across 16 strategy steps. Current code status:

| Model Family | Architecture Status | Code Status |
|-------------|-------------------|-------------|
| **FinBERT** (sentiment) | Designed | Placeholder (keyword scorer implemented) |
| **XGBoost/LightGBM** (signal classification) | Designed | Not implemented |
| **LSTM** (price prediction) | Designed | Not implemented |
| **Transformer** (multi-TF analysis) | Designed | Not implemented |
| **HMM** (regime detection) | Designed | Not implemented |
| **RL** (strategy optimization) | Designed | Not implemented |
| **LLM** (reasoning) | Designed | Config exists (OpenAI/Anthropic keys), not wired |
| **CNN** (chart patterns) | Designed (Phase 2+) | Not implemented |

### Model Infrastructure (Implemented)

- **Model Registry** (`models/registry/`): Version management with lifecycle stages (staging→canary→production→archived), metadata tracking, A/B testing support
- **Inference Engine** (`models/serving/`): ONNX Runtime integration with batching, caching, latency tracking (p50/p95/p99)
- **Model Trainer** (`models/training/`): Walk-forward validation, hyperparameter tuning, PyTorch→ONNX export

### Current "Intelligence" Sources

The system currently derives its "intelligence" from:
1. **Rule-based technical analysis** — all 16 pipeline steps are deterministic algorithms
2. **Weighted confluence scoring** — 9 component weights (not ML-learned)
3. **Keyword-based sentiment** — simple bearish/bullish word counting
4. **LLM integration ready** — config keys for OpenAI/Anthropic, not yet wired into agents

---

## 9. Reasoning & Explainability

### Chain of Thought (`ChainOfThought`)

Step-by-step market analysis with 6 thought step types:
1. **Observe** — record market observations (weight: 0.15)
2. **Collect Evidence** — gather indicator data (weight: 0.20)
3. **Weigh Evidence** — assess bullish/bearish signal count (weight: 0.25)
4. **Hypothesize** — form direction hypothesis (weight: 0.15)
5. **Validate** — check with volume/sentiment (weight: 0.15)
6. **Conclude** — final signal with confidence (weight: 0.10)

Final confidence = weighted average of all step confidences.

### Causal Inference (`CausalInference`)

Distinguishes true causation from correlation using:
- Temporal precedence (+0.3)
- High correlation (+0.2)
- No confound (+0.2)
- Repeated observation (+0.2)
- Dose-response (+0.1)

Score ≥ 0.6 = causal. Supports counterfactual reasoning ("Without X, Y would have been Z% different").

### Trade Explainer (`TradeExplainer`)

Generates human-readable explanations for every trade:
- **Factor contribution breakdown** — each factor's value, weight, contribution, direction
- **Risk/benefit analysis** — risk per share, reward per share, R:R ratio, max loss/gain %
- **Rationale** — natural language summary of top 3 factors
- **Audit trail** — timestamped decision log for compliance

---

## 10. Security Architecture

### Authentication (3-Layer)

1. **Identity**: email + password via Argon2id (64MB memory, 3 iterations)
2. **Second Factor**: TOTP RFC 6238 (Google Authenticator compatible)
3. **Session**: JWT access (15min) + refresh (7day) tokens with device binding

### Encryption

- **At rest**: AES-256-GCM with field-level encryption, versioned DEKs, 90-day key rotation
- **In transit**: TLS 1.3 enforcement
- **Credentials**: OS keyring storage (or encrypted file fallback), per-broker isolation

### Audit Logging

- Tamper-proof, append-only event trail with hash-chain integrity
- 7-year retention for trading events, 2-year for auth events
- Categories: authentication, authorization, trading, credential, system, security, data_access, agent

### Input Validation

- SQL injection prevention (11 regex patterns)
- XSS prevention (8 regex patterns)
- Symbol validation (regex: `^[A-Z0-9]{1,10}(/[A-Z0-9]{1,10})?$`)
- Order parameter validation

### Compliance

- Kenya CMA regulatory requirements
- GDPR/Kenya DPA data protection
- Risk disclosure generation
- Geo-blocking (US, KP, IR, SY, CU)

### Quantum Readiness

- Threat assessment module (RSA/ECDSA vulnerable, AES/SHA safe)
- 4 readiness levels (none → aware → hybrid → post-quantum)
- Migration path planning (estimated threat year: 2035)

---

## 11. API Layer

### REST API (FastAPI)

| Route Group | Endpoints | Purpose |
|------------|-----------|---------|
| `/auth` | login, refresh, logout | JWT authentication |
| `/trades` | list, create, get, close | Trade CRUD |
| `/portfolio` | positions, pnl, performance | Portfolio analytics |
| `/signals` | list active, history | Signal management |
| `/system` | health, status, config | System monitoring |

**Middleware**: CORS, per-IP rate limiting (120 req/min), request timing headers.

**Note**: Trade and signal stores are currently **in-memory** (demo data seeded on startup). Production requires DB-backed stores.

### WebSocket Server

Channel-based pub/sub:
- **prices** — real-time price updates
- **trades** — trade execution notifications
- **signals** — new signal alerts
- **system** — system messages

Protocol: JSON messages with subscribe/unsubscribe/ping actions.

---

## 12. Cognitive Loops

### 5 Loop Systems

| Loop | Purpose | Pattern |
|------|---------|---------|
| **ReAct Loop** | Primary decision loop for all agents | Think → Act → Observe → Repeat |
| **Reflection Loop** | Self-correcting analysis | Generate → Critique → Revise |
| **Deliberation Loop** | Multi-agent consensus | Propose → Evaluate → Vote → Consensus |
| **Learning Loop** | Continuous adaptation | Record → Analyze → Adapt |
| **HITL Loop** | Progressive autonomy | Approve → Track → Promote/Demote |

### ReAct Loop

Forces agents to reason before acting with auditable traces. Supports tool registration, configurable max steps/timeout/decision threshold. Can integrate LLM for thought generation.

### Deliberation Loop

5 consensus methods: majority vote, weighted vote, unanimous, threshold, delegation. 5 conflict resolution strategies: escalate to human, defer to risk, defer to expert, no action, average positions.

### Learning Loop

Tracks:
- **Feature importance shifts** — what signals matter NOW
- **Strategy performance decay** — alpha erosion detection via Sharpe comparison
- **Model confidence calibration** — are predictions well-calibrated?
- **Regime detection** — trending/range-bound/high-vol/crisis classification

### HITL Loop (Progressive Autonomy)

4 autonomy levels:
1. **Supervised** — every trade requires human approval
2. **Conditional** — high-confidence auto-execute, others require approval
3. **Notify** — auto-execute with alerts
4. **Autonomous** — full autonomy with circuit-breaker safety

Promotion thresholds: 50→200→500 trades at 90%→85%→80% approval rate. Demotion on consecutive losses (5→4→3).

---

## 13. Implementation Status Assessment

### ✅ Fully Implemented (Production-Ready Code)

| Component | Files | Lines (est.) | Notes |
|-----------|-------|-------------|-------|
| **Orchestrator** | `agents/orchestrator/graph.py`, `state.py` | ~500 | LangGraph StateGraph with 5 agent nodes + HITL |
| **All 5 Agents** | `agents/*/agent.py` | ~800 | Strategy, Risk, Execution, News, Reflection |
| **16-Step Pipeline** | `strategy/pipeline.py`, `steps/s01-s16.py` | ~1500 | All 16 steps fully implemented |
| **Pipeline Context** | `strategy/context.py` | ~300 | Immutable Pydantic model with 16 sub-models |
| **Risk Governor** | `risk/governor.py` | ~400 | 7-gate approval pipeline |
| **Risk Sub-systems** | `risk/circuit_breaker.py`, `drawdown.py`, etc. | ~2000 | Circuit breaker, drawdown, correlation, exposure, tail risk, validators |
| **Broker Connectors** | `brokers/mt5_connector.py`, `ccxt_connector.py` | ~1200 | Full MT5 and CCXT implementations |
| **Smart Router** | `brokers/smart_router.py` | ~300 | Weighted scoring, failover |
| **Order Manager** | `brokers/order_manager.py` | ~250 | Lifecycle tracking, partial fills |
| **Data Pipeline** | `data/ingestion/market_data.py` | ~400 | Tick ingestion, multi-TF candle aggregation |
| **Feature Engineering** | `data/features/engineering.py` | ~400 | 20+ indicators, normalization, feature store |
| **Event Bus** | `core/events.py` | ~300 | Redis Streams with consumer groups |
| **Database** | `core/database.py`, `core/models.py` | ~600 | SQLAlchemy async, 10 ORM models |
| **Config** | `core/config.py` | ~200 | Pydantic Settings with 8 sub-configs |
| **Rust Bridge** | `core/rust_bridge.py` | ~500 | PyO3 imports + full Python fallbacks |
| **REST API** | `api/rest/` | ~600 | FastAPI with 5 route groups |
| **WebSocket** | `api/websocket/server.py` | ~300 | Channel-based pub/sub |
| **Security** | `security/` | ~1500 | Auth, encryption, audit, compliance, validation |
| **Reasoning** | `reasoning/` | ~600 | Chain-of-thought, causal inference, explainability |
| **Cognitive Loops** | `loops/` | ~1500 | ReAct, reflection, deliberation, learning, HITL |
| **News Handler** | `risk/news_handler.py` | ~300 | Three-phase news protocol |
| **Alternative Data** | `data/ingestion/alternative_data.py` | ~300 | On-chain, social, trends (providers implemented, some endpoints placeholder) |
| **MQL5 Bridge** | `brokers/mql5_bridge.py` | ~300 | ZeroMQ bridge to MT5 EA |
| **Prometheus Metrics** | `utils/metrics.py` | ~100 | Trade, position, risk, system metrics |
| **Structured Logging** | `utils/logger.py` | ~100 | structlog with JSON output |

### ⚠️ Partially Implemented / Placeholder

| Component | Status | What's Missing |
|-----------|--------|----------------|
| **ML Models** | Infrastructure only | No trained models; registry, inference engine, trainer exist but no actual models |
| **LLM Integration** | Config only | OpenAI/Anthropic API keys configured but not wired into agents |
| **Alternative Data** | Providers stubbed | Funding rates work (Binance/Bybit API), but whale alerts, Twitter, Reddit, Google Trends return empty |
| **News Sentiment** | Keyword-based | Simple word-count scorer; FinBERT integration planned but not implemented |
| **API Data Stores** | In-memory | Trade and signal endpoints use in-memory dicts with demo data |
| **Backtesting** | Rust engine defined | `BacktestEngine` class exists in Rust bridge but no backtesting harness |

### 📋 Architecture Only (No Code)

| Component | Notes |
|-----------|-------|
| **XGBoost/LightGBM classifiers** | Designed for signal classification, confluence scoring |
| **LSTM/Transformer models** | Designed for price prediction |
| **HMM regime detection** | Designed for market regime classification |
| **RL strategy optimization** | Designed for TP management, execution optimization |
| **CNN chart patterns** | Phase 2+ |
| **Quantum-resistant crypto** | Assessment module exists, no actual PQC implementation |

---

## 14. Key Design Decisions & Trade-offs

### Strengths

1. **Risk-first architecture** — 7 independent risk sub-systems with hard limits. The `RiskGovernor` 7-gate pipeline is genuinely institutional-grade.

2. **Immutable pipeline context** — `frozen=True` Pydantic model prevents accidental state mutation between steps. Clean functional-style data flow.

3. **Full Python fallbacks for Rust** — system degrades gracefully without native module. Every Rust class has a pure-Python equivalent.

4. **Plugin-based broker abstraction** — adding a new broker = one new class. Zero changes to core. CCXT gives access to 104+ exchanges for free.

5. **Comprehensive audit trail** — every agent decision, every risk check, every trade produces structured logs. Hash-chain tamper detection in audit logger.

6. **Progressive autonomy (HITL)** — system earns independence over time. Smart design that starts conservative and relaxes based on demonstrated reliability.

### Trade-offs / Concerns

1. **No trained ML models** — the architecture calls for 20-35 models, but the system currently runs entirely on rule-based heuristics. The "intelligence" is in the confluence weight tuning, not learned patterns.

2. **LLM not integrated** — agents have system prompts but don't actually call LLMs. The `react_loop` and `reason_fn` are designed for LLM integration but use fallback templates.

3. **In-memory API stores** — trade and signal endpoints use Python dicts. Server restart loses all data. Needs DB-backed stores.

4. **MT5 is Windows-only** — the connector works but requires Wine or a remote Windows VPS on Linux. The MQL5 Bridge via ZeroMQ is the recommended approach.

5. **Simplified sentiment** — keyword counting instead of FinBERT. Will miss context, sarcasm, domain-specific language.

---

## 15. Risks & Recommendations

### Critical Path to Production

1. **Wire LLM into agents** — the `system_prompt()` methods exist but are never used. Connect OpenAI/Anthropic to make agents actually reason.

2. **Train at least one ML model** — XGBoost for confluence scoring or HMM for regime detection. The infrastructure (registry, trainer, inference engine) is ready.

3. **DB-backed API stores** — replace in-memory dicts with PostgreSQL queries using the existing ORM models.

4. **Integration tests** — no test files found in the codebase. The risk system especially needs comprehensive test coverage.

5. **FinBERT integration** — replace keyword scorer with actual NLP model for sentiment analysis.

### Architecture Strengths to Preserve

- The 7-gate risk pipeline is excellent — don't shortcut it
- The immutable context pattern prevents entire classes of bugs
- The broker abstraction layer is well-designed for multi-asset expansion
- The HITL progressive autonomy is a genuinely novel approach to trading system governance

### Scale Considerations

- Redis Streams event bus scales horizontally with consumer groups
- TimescaleDB hypertables handle billions of tick rows
- CCXT connector supports rate limiting per exchange
- Prometheus metrics enable Grafana dashboards for monitoring

---

*End of analysis. This report covers every Python file in `src/alphastack/` and the 4 specified architecture documents.*
