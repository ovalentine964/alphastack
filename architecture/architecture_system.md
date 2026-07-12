# Alpha Stack — System Architecture Document

> **Version:** 1.0 · **Date:** 2026-07-11 · **Author:** Architecture Team
> **Source Research:** [`research/research_02_tech_stack_architecture.md`](../research/research_02_tech_stack_architecture.md), [`research/research_01_crypto_forex_trading_bot_landscape.md`](../research/research_01_crypto_forex_trading_bot_landscape.md) — Tech stack architecture and crypto/forex trading bot landscape
> **Status:** Architecture Complete

---

> **Version:** 1.0 · **Date:** 2026-07-11 · **Author:** System Architect Agent
> **Scope:** Complete system architecture for institutional-grade AI forex/crypto trading platform
> **Design Philosophy:** Start at $7, scale to institutional — every module is designed for both extremes

---

## Table of Contents

1. [Architecture Philosophy](#1-architecture-philosophy)
2. [High-Level System Architecture](#2-high-level-system-architecture)
3. [Module Breakdown & Responsibilities](#3-module-breakdown--responsibilities)
4. [Data Flow Architecture](#4-data-flow-architecture)
5. [Communication Protocols](#5-communication-protocols)
6. [Dependency Graph](#6-dependency-graph)
7. [Deployment Topology](#7-deployment-topology)
8. [Scaling Architecture: $7 → Institutional](#8-scaling-architecture-7--institutional)
9. [Security Architecture](#9-security-architecture)
10. [Technology Stack Summary](#10-technology-stack-summary)

---

## 1. Architecture Philosophy

### 1.1 Core Principles

| Principle | Description | Rationale |
|-----------|-------------|-----------|
| **Event-First** | Every module communicates via events, not direct calls | Decouples modules, enables replay/audit, scales horizontally |
| **Strategy as Data** | AlphaStack strategy steps are configuration, not code | Swap strategies without re-deployment |
| **Fail-Safe by Default** | Every module assumes the module below it will fail | Graceful degradation, no cascading failures |
| **Audit Everything** | Every decision, every order, every signal is logged with full reasoning chain | Institutional compliance, strategy improvement |
| **Human Override Always** | Any automated decision can be overridden by a human at any stage | Safety, trust-building, regulatory compliance |
| **Progressive Autonomy** | Start with human approval for everything, gradually increase automation as trust builds | Risk management during learning phase |

### 1.2 Architectural Style

**Hybrid Event-Driven + Multi-Agent + Pipeline Architecture**

```
┌─────────────────────────────────────────────────────────────────────┐
│                     ARCHITECTURAL PATTERN                            │
│                                                                      │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐      │
│  │ Pipeline │    │  Event   │    │  Multi-  │    │  Layered │      │
│  │ (AlphaStack    │ +  │  Driven  │ +  │  Agent   │ +  │  (Tiered │      │
│  │  16-step)│    │  (Async) │    │  (Roles) │    │  Access) │      │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘      │
│                                                                      │
│  Pipeline: Sequential strategy steps with conditional branching      │
│  Event-Driven: All inter-module communication via message bus        │
│  Multi-Agent: Specialized agents for each domain (risk, news, etc.)  │
│  Layered: Clear separation between data → logic → execution → UI    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. High-Level System Architecture

### 2.1 System Overview Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ALPHA STACK — FULL SYSTEM                           │
│                                                                              │
│  ═══════════════════════════════════════════════════════════════════════════  │
│  LAYER 6: PRESENTATION                                                      │
│  ═══════════════════════════════════════════════════════════════════════════  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │  Tauri       │  │  Web App     │  │  Flutter     │  │  CLI / API   │    │
│  │  Desktop     │  │  (React)     │  │  Mobile      │  │  (Headless)  │    │
│  │  (Primary)   │  │  (Companion) │  │  (Alerts)    │  │  (Bot)       │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘    │
│         │                 │                 │                 │              │
│  ═══════╪═════════════════╪═════════════════╪═════════════════╪══════════    │
│  LAYER 5: API GATEWAY     │                 │                 │              │
│  ═══════╪═════════════════╪═════════════════╪═════════════════╪══════════    │
│         └────────┬────────┴────────┬────────┘                 │              │
│            ┌─────┴─────┐    ┌──────┴──────┐           ┌──────┴──────┐      │
│            │  REST API │    │  WebSocket  │           │  gRPC/IPC   │      │
│            │  (FastAPI)│    │  Server     │           │  (Internal) │      │
│            └─────┬─────┘    └──────┬──────┘           └──────┬──────┘      │
│                  │                 │                          │              │
│  ════════════════╪═════════════════╪══════════════════════════╪══════════    │
│  LAYER 4: ORCHESTRATION           │                          │              │
│  ════════════════╪═════════════════╪══════════════════════════╪══════════    │
│            ┌─────┴─────────────────┴──────────────────────────┴─────┐       │
│            │              MULTI-AGENT ORCHESTRATOR                   │       │
│            │  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐  │       │
│            │  │Strategy │ │  Risk    │ │  News    │ │Execution  │  │       │
│            │  │Agent    │ │  Agent   │ │  Agent   │ │Agent      │  │       │
│            │  │(AlphaStack)   │ │          │ │          │ │           │  │       │
│            │  └────┬────┘ └────┬─────┘ └────┬─────┘ └─────┬─────┘  │       │
│            │       │          │             │             │         │       │
│            │  ┌────┴──────────┴─────────────┴─────────────┴─────┐   │       │
│            │  │           EVENT BUS (Redis Streams)             │   │       │
│            │  └────┬──────────┬─────────────┬─────────────┬─────┘   │       │
│            └───────┼──────────┼─────────────┼─────────────┼─────────┘       │
│                    │          │             │             │                  │
│  ══════════════════╪══════════╪═════════════╪═════════════╪══════════════    │
│  LAYER 3: STRATEGY & ANALYSIS  │             │             │                  │
│  ══════════════════╪══════════╪═════════════╪═════════════╪══════════════    │
│            ┌───────┴──────────┴─────────────┴─────────────┴─────────┐       │
│            │              AlphaStack STRATEGY PIPELINE                     │       │
│            │  ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐    │       │
│            │  │ 1 │→│ 2 │→│ 3 │→│ 4 │→│ 5 │→│ 6 │→│ 7 │→│ 8 │    │       │
│            │  └───┘ └───┘ └───┘ └───┘ └───┘ └───┘ └───┘ └───┘    │       │
│            │  ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐    │       │
│            │  │ 9 │→│10 │→│11 │→│12 │→│13 │→│14 │→│15 │→│16 │    │       │
│            │  └───┘ └───┘ └───┘ └───┘ └───┘ └───┘ └───┘ └───┘    │       │
│            └───────────────────────────────────────────────────────┘       │
│                    │          │             │             │                  │
│  ══════════════════╪══════════╪═════════════╪═════════════╪══════════════    │
│  LAYER 2: EXECUTION & BROKER  │             │             │                  │
│  ══════════════════╪══════════╪═════════════╪═════════════╪══════════════    │
│            ┌───────┴──────────┴─────────────┴─────────────┴─────────┐       │
│            │            UNIFIED ORDER MANAGER (UOM)                  │       │
│            └───────────────────────┬─────────────────────────────────┘       │
│                                    │                                         │
│            ┌───────────────────────┴─────────────────────────────────┐       │
│            │            BROKER CONNECTOR ABSTRACTION (BCA)           │       │
│            │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │       │
│            │  │MT5       │ │CCXT      │ │REST API  │ │FIX       │  │       │
│            │  │Connector │ │Connector │ │Connector │ │Connector │  │       │
│            │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘  │       │
│            └───────┼────────────┼────────────┼────────────┼─────────┘       │
│                    │            │            │            │                  │
│  ══════════════════╪════════════╪════════════╪════════════╪══════════════    │
│  LAYER 1: DATA FOUNDATION      │            │            │                  │
│  ══════════════════╪════════════╪════════════╪════════════╪══════════════    │
│            ┌───────┴────────────┴────────────┴────────────┴─────────┐       │
│            │              DATA PIPELINE & STORAGE                    │       │
│            │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │       │
│            │  │TimescaleDB│ │Redis    │ │ClickHouse│ │Object    │  │       │
│            │  │(Time-     │ │(Hot     │ │(Analytics│ │Storage   │  │       │
│            │  │ Series)   │ │ Cache)  │ │ + Audit) │ │(S3/MinIO)│  │       │
│            │  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │       │
│            └───────────────────────────────────────────────────────┘       │
│                                                                             │
│  ═══════════════════════════════════════════════════════════════════════     │
│  LAYER 0: INFRASTRUCTURE                                                    │
│  ═══════════════════════════════════════════════════════════════════════     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │  Docker      │  │  Monitoring  │  │  Logging     │  │  Secrets     │    │
│  │  Compose /   │  │  Prometheus  │  │  ELK / Loki  │  │  Vault /     │    │
│  │  K8s         │  │  + Grafana   │  │              │  │  SOPS        │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Layer Definitions

| Layer | Name | Responsibility | Key Technologies |
|-------|------|---------------|------------------|
| **L6** | Presentation | User interfaces, visualization, alerts | Tauri 2.x, React 19, Flutter 3.x |
| **L5** | API Gateway | Authentication, rate limiting, request routing | FastAPI, WebSocket, gRPC |
| **L4** | Orchestration | Multi-agent coordination, strategy execution, risk enforcement | LangGraph, Redis Streams, Python asyncio |
| **L3** | Strategy & Analysis | AlphaStack 16-step pipeline, signal generation, ML inference | PyTorch, TA-Lib, Polars, Custom Rust |
| **L2** | Execution & Broker | Order management, broker abstraction, fill tracking | Python MT5 API, CCXT, ZeroMQ |
| **L1** | Data Foundation | Market data storage, caching, analytics | TimescaleDB, Redis, ClickHouse |
| **L0** | Infrastructure | Container orchestration, monitoring, logging, secrets | Docker, Prometheus, Grafana, Loki |

---

## 3. Module Breakdown & Responsibilities

### 3.1 Module Registry

```
alpha-stack/
├── core/                          # L3: Strategy & Analysis Engine
│   ├── alphastack/                      # AlphaStack 16-step strategy pipeline
│   │   ├── steps/                 # Individual strategy steps (1-16)
│   │   ├── pipeline.py            # Pipeline orchestrator
│   │   └── config/                # Strategy parameters (YAML)
│   ├── agents/                    # Multi-agent definitions
│   │   ├── strategy_agent.py      # AlphaStack execution agent
│   │   ├── risk_agent.py          # Risk management agent
│   │   ├── news_agent.py          # News/sentiment agent
│   │   ├── execution_agent.py     # Order execution agent
│   │   ├── journal_agent.py       # Trade journaling agent
│   │   └── auditor_agent.py       # Performance audit agent
│   ├── ml/                        # Machine learning models
│   │   ├── sentiment/             # FinBERT, LLM sentiment
│   │   ├── regime/                # Market regime classifier
│   │   ├── sr_detection/          # S/R level ML model
│   │   ├── pattern_recognition/   # Candlestick pattern CNN
│   │   └── tp_optimizer/          # RL-based TP optimization
│   └── indicators/                # Technical indicators (Rust-backed)
│       ├── ta_core.rs             # Rust implementations
│       └── ta_python.py           # Python bindings via PyO3
│
├── execution/                     # L2: Execution & Broker Layer
│   ├── order_manager.py           # Unified Order Manager (UOM)
│   ├── risk_engine.py             # Pre-trade risk checks
│   ├── connectors/                # Broker Connector Abstraction
│   │   ├── base.py                # Abstract BrokerConnector interface
│   │   ├── mt5_connector.py       # MetaTrader 5 (FXPesa)
│   │   ├── ccxt_connector.py      # Crypto exchanges (CCXT)
│   │   ├── oanda_connector.py     # OANDA REST API
│   │   ├── ibkr_connector.py      # Interactive Brokers
│   │   └── fix_connector.py       # FIX protocol (institutional)
│   ├── execution_algos/           # Execution algorithms
│   │   ├── market_order.py        # Simple market order
│   │   ├── limit_order.py         # Limit order with expiry
│   │   ├── twap.py                # TWAP (for larger sizes)
│   │   └── smart_router.py        # Multi-broker SOR
│   └── bridge/                    # MT5-specific bridge
│       ├── mql5_ea/               # MQL5 Expert Advisor (signal receiver)
│       └── zmq_bridge.py          # ZeroMQ Python↔MQL5 bridge
│
├── data/                          # L1: Data Foundation
│   ├── ingestion/                 # Data collection
│   │   ├── mt5_collector.py       # MT5 tick/candle collector
│   │   ├── ccxt_collector.py      # Crypto data collector
│   │   ├── news_collector.py      # News feed aggregator
│   │   └── economic_calendar.py   # Economic event scraper
│   ├── storage/                   # Database adapters
│   │   ├── timescale.py           # TimescaleDB adapter
│   │   ├── redis_cache.py         # Redis hot cache
│   │   ├── clickhouse.py          # ClickHouse analytics
│   │   └── object_store.py        # S3/MinIO for model artifacts
│   ├── quality/                   # Data quality
│   │   ├── gap_detector.py        # Missing data detection
│   │   ├── outlier_filter.py      # Z-score outlier filtering
│   │   └── normalizer.py          # Cross-source normalization
│   └── models/                    # Data models (Pydantic)
│       ├── market.py              # OHLCV, Tick, OrderBook
│       ├── order.py               # Order, Position, Fill
│       └── signal.py              # Signal, TradeProposal
│
├── gateway/                       # L5: API Gateway
│   ├── rest/                      # REST API (FastAPI)
│   │   ├── routes/                # API routes
│   │   ├── auth.py                # JWT + API key auth
│   │   └── middleware.py          # Rate limiting, CORS
│   ├── websocket/                 # WebSocket server
│   │   ├── server.py              # WS server for real-time data
│   │   └── handlers.py            # Event handlers
│   └── grpc/                      # gRPC for internal services
│       └── proto/                 # Protobuf definitions
│
├── apps/                          # L6: Presentation Layer
│   ├── desktop/                   # Tauri 2.x desktop app
│   │   ├── src-tauri/             # Rust backend (Tauri commands)
│   │   └── src/                   # React frontend
│   ├── web/                       # Web companion (React)
│   ├── mobile/                    # Flutter mobile app
│   └── cli/                       # CLI interface
│
├── infra/                         # L0: Infrastructure
│   ├── docker/                    # Dockerfiles
│   ├── compose/                   # Docker Compose configs
│   ├── k8s/                       # Kubernetes manifests
│   ├── monitoring/                # Prometheus + Grafana configs
│   └── scripts/                   # Deployment scripts
│
└── tests/                         # Test suites
    ├── unit/                      # Unit tests
    ├── integration/               # Integration tests
    ├── backtest/                  # Strategy backtests
    └── paper/                     # Paper trading tests
```

---

### 3.2 Module Responsibility Matrix

| Module | Primary Responsibility | Input | Output | Dependencies |
|--------|----------------------|-------|--------|--------------|
| **AlphaStack Pipeline** | Execute 16-step strategy analysis | Market data, signals | Trade proposals | All strategy steps, ML models |
| **Strategy Agent** | Orchestrate AlphaStack pipeline per instrument | Market events | Signal events | AlphaStack Pipeline, Event Bus |
| **Risk Agent** | Enforce risk limits, position sizing | Trade proposals | Approved/rejected proposals | Risk Engine, Portfolio State |
| **News Agent** | Monitor news, score sentiment | News feeds | Sentiment events | FinBERT, LLM, News APIs |
| **Execution Agent** | Execute approved orders | Approved orders | Fill confirmations | Order Manager, Brokers |
| **Journal Agent** | Record and analyze all trades | Trade events | Journal entries, performance stats | Event Bus, Database |
| **Auditor Agent** | Periodic strategy performance review | Trade history | Strategy recommendations | Journal, ML models |
| **Order Manager** | Single source of truth for all orders | Order requests | Order state updates | Broker Connectors |
| **Risk Engine** | Pre-trade risk calculations | Order requests, portfolio | Risk metrics, limits | Portfolio State |
| **Broker Connectors** | Abstract broker-specific APIs | Unified orders | Fill events, market data | Broker APIs |
| **Data Pipeline** | Ingest, clean, store market data | Raw market data | Normalized data | Brokers, News APIs |
| **Event Bus** | Route all inter-module events | Events from all modules | Events to subscribers | Redis Streams |

---

### 3.3 AlphaStack Strategy Pipeline — Detailed Module Design

The AlphaStack (Valentine Money Printing Machine) is a 16-step sequential pipeline. Each step is an independent module that receives context from previous steps and enriches it for downstream steps.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    AlphaStack 16-STEP STRATEGY PIPELINE                    │
│                                                                      │
│  PHASE A: CONTEXT (Steps 1-4)                                       │
│  ┌───────┐   ┌───────┐   ┌───────┐   ┌───────┐                    │
│  │Step 1 │──▶│Step 2 │──▶│Step 3 │──▶│Step 4 │                    │
│  │Funda- │   │Market │   │Session│   │Market │                    │
│  │mental │   │ Bias  │   │Analy- │   │Struc- │                    │
│  │Intel  │   │       │   │sis    │   │ture   │                    │
│  └───────┘   └───────┘   └───────┘   └───────┘                    │
│  "What's      "Bull or    "Which      "What's the                  │
│   happening?"  bear?"     session?"    structure?"                  │
│                                                                      │
│  PHASE B: STRUCTURE (Steps 5-8)                                     │
│  ┌───────┐   ┌───────┐   ┌───────┐   ┌───────┐                    │
│  │Step 5 │──▶│Step 6 │──▶│Step 7 │──▶│Step 8 │                    │
│  │Support│   │Liquid-│   │Smart  │   │RSI   │                    │
│  │/Resist│   │ity    │   │Money  │   │Confir-│                    │
│  │ance   │   │Detect │   │Concept│   │mation │                    │
│  └───────┘   └───────┘   └───────┘   └───────┘                    │
│  "Where are   "Where's    "Where's    "Momentum                    │
│   levels?"    liquidity?"  smart $?"   aligned?"                    │
│                                                                      │
│  PHASE C: ENTRY (Steps 9-12)                                        │
│  ┌───────┐   ┌───────┐   ┌───────┐   ┌───────┐                    │
│  │Step 9 │──▶│Step 10│──▶│Step 11│──▶│Step 12│                    │
│  │Candle-│   │Trade  │   │Posi-  │   │Stop  │                    │
│  │stick  │   │Entry  │   │tion   │   │Loss  │                    │
│  │Confir-│   │Signal │   │Sizing │   │Place-│                    │
│  │mation │   │       │   │       │   │ment  │                    │
│  └───────┘   └───────┘   └───────┘   └───────┘                    │
│  "Pattern     "Where to   "How big?"  "Where's                     │
│   confirms?"  enter?"                   the stop?"                  │
│                                                                      │
│  PHASE D: MANAGEMENT (Steps 13-16)                                  │
│  ┌───────┐   ┌───────┐   ┌───────┐   ┌───────┐                    │
│  │Step 13│──▶│Step 14│──▶│Step 15│──▶│Step 16│                    │
│  │Take   │   │Trade  │   │Exit   │   │Trade │                    │
│  │Profit │   │Manage-│   │Condi- │   │Journal│                    │
│  │       │   │ment   │   │tions  │   │& Learn│                    │
│  └───────┘   └───────┘   └───────┘   └───────┘                    │
│  "Where to    "How to     "When to    "What did                     │
│   profit?"    manage?"    exit?"      we learn?"                    │
└─────────────────────────────────────────────────────────────────────┘
```

**Each Step Module implements:**

```python
class AlphaStackStep(ABC):
    """Base class for all AlphaStack strategy steps."""
    
    @abstractmethod
    async def analyze(self, context: StrategyContext) -> StepResult:
        """Execute this step's analysis."""
        pass
    
    @abstractmethod
    def get_confidence(self) -> float:
        """Return confidence score [0.0 - 1.0]."""
        pass
    
    @abstractmethod
    def get_reasoning(self) -> str:
        """Return human-readable reasoning chain."""
        pass
    
    def should_skip(self, context: StrategyContext) -> bool:
        """Check if this step should be skipped (conditional execution)."""
        return False
```

**StrategyContext** is a progressively enriched data object that flows through all 16 steps:

```python
@dataclass
class StrategyContext:
    # Input
    instrument: str                    # e.g., "EUR/USD"
    timestamp: datetime
    timeframe: str                     # Primary analysis timeframe
    
    # Phase A: Context
    fundamental_bias: FundamentalBias  # From Step 1
    market_bias: MarketBias            # From Step 2 (bullish/bearish/neutral)
    session_info: SessionInfo          # From Step 3 (Asian/London/NY/Overlap)
    market_structure: MarketStructure  # From Step 4 (trending/ranging/transitional)
    
    # Phase B: Structure
    sr_levels: list[SRLevel]           # From Step 5
    liquidity_zones: list[LiquidityZone]  # From Step 6
    order_blocks: list[OrderBlock]     # From Step 7 (SMC)
    rsi_state: RSIState                # From Step 8
    
    # Phase C: Entry
    candlestick_signal: CandleSignal   # From Step 9
    entry_plan: EntryPlan              # From Step 10
    position_size: PositionSize        # From Step 11
    stop_loss: StopLoss                # From Step 12
    
    # Phase D: Management
    take_profit: TakeProfitPlan        # From Step 13
    management_rules: ManagementRules  # From Step 14
    exit_conditions: ExitConditions    # From Step 15
    journal_entry: TradeJournal        # From Step 16
    
    # Metadata
    confidence_score: float            # Aggregate confidence [0-1]
    reasoning_chain: list[str]         # Full audit trail
    step_results: dict[str, StepResult]  # Per-step detailed results
```

---

### 3.4 Multi-Agent System — Detailed Design

```
┌─────────────────────────────────────────────────────────────────────┐
│                    MULTI-AGENT ARCHITECTURE                          │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    COORDINATOR AGENT (Depth 0)               │    │
│  │  Role: Receive market events, delegate to specialists,       │    │
│  │        synthesize results, enforce global policies            │    │
│  │  Loop: Orchestrator-Workers (Anthropic pattern)              │    │
│  └─────────────────────────┬───────────────────────────────────┘    │
│                            │                                         │
│         ┌──────────────────┼──────────────────┐                     │
│         │                  │                  │                     │
│  ┌──────┴──────┐  ┌───────┴───────┐  ┌───────┴───────┐            │
│  │ STRATEGY    │  │ RISK          │  │ NEWS          │            │
│  │ AGENT       │  │ AGENT         │  │ AGENT         │            │
│  │ (Depth 1)   │  │ (Depth 1)     │  │ (Depth 1)     │            │
│  │             │  │               │  │               │            │
│  │ Loop:       │  │ Loop:         │  │ Loop:         │            │
│  │ Plan-Execute│  │ ReAct         │  │ ReAct         │            │
│  │             │  │               │  │               │            │
│  │ Delegates:  │  │ Monitors:     │  │ Monitors:     │            │
│  │ - Data fetch│  │ - Drawdown    │  │ - News feeds  │            │
│  │ - Indicator │  │ - Exposure    │  │ - Sentiment   │            │
│  │   calc      │  │ - Correlation │  │ - Events      │            │
│  │ - Signal    │  │ - Limits      │  │ - Impact      │            │
│  │   generation│  │               │  │   scoring     │            │
│  └──────┬──────┘  └───────┬───────┘  └───────┬───────┘            │
│         │                  │                  │                     │
│  ┌──────┴──────┐  ┌───────┴───────┐  ┌───────┴───────┐            │
│  │ EXECUTION   │  │ JOURNAL       │  │ AUDITOR       │            │
│  │ AGENT       │  │ AGENT         │  │ AGENT         │            │
│  │ (Depth 1)   │  │ (Depth 1)     │  │ (Depth 1)     │            │
│  │             │  │               │  │               │            │
│  │ Loop:       │  │ Loop:         │  │ Loop:         │            │
│  │ ReAct       │  │ Event-driven  │  │ Reflection    │            │
│  │             │  │               │  │               │            │
│  │ Actions:    │  │ Actions:      │  │ Actions:      │            │
│  │ - Order     │  │ - Record      │  │ - Review      │            │
│  │   placement │  │ - Categorize  │  │ - Score       │            │
│  │ - Fill      │  │ - Annotate    │  │ - Recommend   │            │
│  │   tracking  │  │ - Report      │  │ - Adapt       │            │
│  └─────────────┘  └───────────────┘  └───────────────┘            │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │              SHARED STATE (Redis + PostgreSQL)               │    │
│  │  - Portfolio state (positions, P&L, margin)                 │    │
│  │  - Active signals and proposals                              │    │
│  │  - Risk metrics and limits                                   │    │
│  │  - Market context cache                                      │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

**Agent Loop Patterns:**

| Agent | Loop Pattern | Rationale |
|-------|-------------|-----------|
| **Coordinator** | Orchestrator-Workers | Dynamically delegates to specialists based on market conditions |
| **Strategy** | Plan-and-Execute | Plans analysis strategy, then executes AlphaStack steps |
| **Risk** | ReAct | Continuously reasons about risk state, takes protective actions |
| **News** | ReAct | Monitors feeds, reasons about impact, triggers alerts |
| **Execution** | ReAct | Reasons about execution quality, adapts order strategy |
| **Journal** | Event-Driven | Reacts to trade events, records with context |
| **Auditor** | Reflection | Periodically reviews performance, critiques strategies, recommends changes |

---

### 3.5 Broker Connector Abstraction — Detailed Design

```python
# Unified Broker Connector Interface

class BrokerConnector(ABC):
    """Abstract base class for all broker connectors."""
    
    @abstractmethod
    async def connect(self, credentials: BrokerCredentials) -> bool:
        """Establish connection to broker."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Gracefully disconnect."""
        pass
    
    @abstractmethod
    async def get_account_info(self) -> AccountInfo:
        """Get account balance, equity, margin."""
        pass
    
    @abstractmethod
    async def get_positions(self) -> list[Position]:
        """Get all open positions."""
        pass
    
    @abstractmethod
    async def place_order(self, order: UnifiedOrder) -> OrderResult:
        """Place a new order."""
        pass
    
    @abstractmethod
    async def modify_order(self, order_id: str, modifications: dict) -> OrderResult:
        """Modify an existing order."""
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        pass
    
    @abstractmethod
    async def get_market_data(self, symbol: str, timeframe: str, 
                               count: int) -> list[Candle]:
        """Get OHLCV data."""
        pass
    
    @abstractmethod
    async def subscribe_ticks(self, symbol: str, 
                               callback: Callable) -> None:
        """Subscribe to real-time tick data."""
        pass
    
    @abstractmethod
    async def get_spread(self, symbol: str) -> float:
        """Get current spread in pips."""
        pass
```

**Connector Implementations:**

| Connector | Protocol | Assets | Latency | Phase |
|-----------|----------|--------|---------|-------|
| **MT5Connector** | Python MT5 API + ZeroMQ | Forex, CFDs | 50-200ms | Phase 1 |
| **CCXTConnector** | CCXT (REST + WS) | Crypto Spot/Futures | 100-500ms | Phase 2 |
| **OANDAConnector** | REST API v20 + Streaming | Forex, CFDs | 20-80ms | Phase 3 |
| **IBKRConnector** | TWS API / Client Portal | All asset classes | 10-50ms | Phase 4 |
| **FIXConnector** | FIX 4.4 / 5.0 | Institutional | <10ms | Phase 5 |

---

### 3.6 Data Pipeline — Detailed Design

```
┌─────────────────────────────────────────────────────────────────────┐
│                      DATA PIPELINE ARCHITECTURE                      │
│                                                                      │
│  SOURCES                    PROCESSING                STORAGE        │
│  ───────                    ──────────                ───────        │
│                                                                      │
│  ┌──────────┐                                                    │
│  │MT5       │──┐                                                  │
│  │Terminal   │  │  ┌──────────────┐   ┌──────────────┐            │
│  └──────────┘  ├─▶│ Tick Stream  │──▶│ Aggregator   │──┐         │
│  ┌──────────┐  │  │ Collector    │   │ (OHLCV from  │  │         │
│  │CCXT      │──┤  │ (asyncio)    │   │  ticks)      │  │         │
│  │Exchanges │  │  └──────────────┘   └──────────────┘  │         │
│  └──────────┘  │                                        │         │
│  ┌──────────┐  │  ┌──────────────┐   ┌──────────────┐  ▼         │
│  │OANDA     │──┤  │ REST Poller  │──▶│ Gap Detector │──▶ TimescaleDB│
│  │API       │  │  │ (periodic)   │   │ + Filler     │  │ (OHLCV)  │
│  └──────────┘  │  └──────────────┘   └──────────────┘  │         │
│                │                                        │         │
│  ┌──────────┐  │  ┌──────────────┐   ┌──────────────┐  │         │
│  │News APIs │──┤  │ News Feed    │──▶│ FinBERT +    │──▶ Redis    │
│  │RSS, Finnh│  │  │ Aggregator   │   │ LLM Pipeline │  │ (Hot)    │
│  │ub, Reuters│  │  └──────────────┘   └──────────────┘  │         │
│  └──────────┘  │                                        │         │
│                │  ┌──────────────┐   ┌──────────────┐  │         │
│  ┌──────────┐  │  │ Economic     │──▶│ Event        │──▶ ClickHouse│
│  │Economic  │──┘  │ Calendar     │   │ Scheduler    │  │ (Audit)  │
│  │Calendar  │     │ Fetcher      │   │              │  │         │
│  └──────────┘     └──────────────┘   └──────────────┘  └──────────┘
│                                                                      │
│  QUALITY GATES:                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ Outlier      │  │ Missing Data │  │ Cross-Source │              │
│  │ Filter       │  │ Detection    │  │ Validation   │              │
│  │ (Z-score)    │  │ (gap scan)   │  │ (consensus)  │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
└─────────────────────────────────────────────────────────────────────┘
```

**Data Flow Rates:**

| Data Type | Ingestion Rate | Storage | Hot Cache | Retention |
|-----------|---------------|---------|-----------|-----------|
| Tick data | 1-100 ticks/sec/pair | TimescaleDB compressed | Redis (last 10K ticks) | 1 year raw, 5 years aggregated |
| OHLCV candles | 1 candle per timeframe close | TimescaleDB hypertables | Redis (last 1000 candles per TF) | Indefinite |
| News articles | 10-100/hour | PostgreSQL | Redis (last 24h) | 5 years |
| Sentiment scores | Per-article + hourly aggregate | PostgreSQL | Redis (current scores) | 2 years |
| Economic events | 1-10/day | PostgreSQL | Redis (next 7 days) | Indefinite |
| Order/trade data | Per-event | PostgreSQL + ClickHouse | Redis (active orders) | Indefinite |
| Signal data | Per-signal | ClickHouse | Redis (active signals) | 5 years |

---

## 4. Data Flow Architecture

### 4.1 Inbound Data Flow (Market → System)

```
External Sources          Ingestion Layer         Processing Layer        Storage Layer
───────────────          ───────────────         ────────────────        ─────────────

MT5 Terminal ──────┐
                   ├──▶ Tick Collector ────▶ Aggregator ────▶ TimescaleDB
CCXT Exchanges ────┘     (asyncio, WS)       (OHLCV build)    (hypertables)
                                                           │
                                                           ├──▶ Redis (hot cache)
                                                           │
OANDA API ────────────▶ REST Poller ──────▶ Normalizer ────┘
                         (periodic)          (cross-source)
                                                           │
News Feeds ────────────▶ News Aggregator ──▶ FinBERT ──────▶ PostgreSQL
(RSS, Finnhub,          (async HTTP)        (sentiment)      (features)
 Reuters)
                                                           │
Economic Calendar ─────▶ Calendar Fetcher ─▶ Event ─────────▶ PostgreSQL
(ForexFactory,           (daily cron)        Scheduler         (calendar)
 Investing.com)                             (impact score)
```

### 4.2 Signal Generation Flow (Strategy → Decision)

```
Market Data              AlphaStack Pipeline            Decision Layer
───────────              ─────────────            ──────────────

OHLCV + Ticks ──────┐
                    ├──▶ Step 1: Fundamental ──▶ FundamentalBias
                    │         Intelligence         │
                    ├──▶ Step 2: Market Bias ────▶ MarketBias
                    │         (sentiment + macro)   │
                    ├──▶ Step 3: Session ────────▶ SessionInfo
                    │         Analysis              │
                    ├──▶ Step 4: Market ─────────▶ MarketStructure
                    │         Structure             │
                    │                              │
                    │    PHASE B: STRUCTURE        │
                    ├──▶ Step 5: S/R Detection ──▶ SRLevels[]
                    ├──▶ Step 6: Liquidity ──────▶ LiquidityZones[]
                    ├──▶ Step 7: SMC ────────────▶ OrderBlocks[]
                    ├──▶ Step 8: RSI ────────────▶ RSIState
                    │                              │
                    │    PHASE C: ENTRY            │
                    ├──▶ Step 9: Candlestick ────▶ CandleSignal
                    ├──▶ Step 10: Entry ─────────▶ EntryPlan ────┐
                    ├──▶ Step 11: Position ──────▶ PositionSize   │
                    ├──▶ Step 12: Stop Loss ─────▶ StopLoss       │
                    │                                              │
                    │    PHASE D: MANAGEMENT       ┌──────────────┘
                    ├──▶ Step 13: Take Profit ───▶ TakeProfitPlan ├──▶ TradeProposal
                    ├──▶ Step 14: Management ────▶ ManagementRules│    │
                    ├──▶ Step 15: Exit ──────────▶ ExitConditions │    │
                    └──▶ Step 16: Journal ───────▶ TradeJournal   │    │
                                                                  │    │
                         ┌────────────────────────────────────────┘    │
                         ▼                                              ▼
                    Risk Agent ────────────────────────────────▶ Execution Agent
                    (validate, size, limit check)                (place order)
```

### 4.3 Execution Flow (Decision → Broker → Confirmation)

```
TradeProposal          Risk Layer              Execution Layer         Broker Layer
─────────────          ──────────              ───────────────         ────────────

TradeProposal ──────▶ Risk Agent ──────────▶ Execution Agent ──────▶ Order Manager
                       │                       │                       │
                       ├─ Check max drawdown   ├─ Select broker        ├─ Route to connector
                       ├─ Check exposure limit  ├─ Choose order type   ├─ Place order
                       ├─ Check correlation     ├─ Set deviation       ├─ Track fill
                       ├─ Check daily loss      │                       │
                       │                       │                       │
                       ▼                       ▼                       ▼
                    APPROVED/REJECTED      Order Request ──────────▶ Broker API
                                            │                       (MT5/CCXT/OANDA)
                                            │                           │
                                            │                           ▼
                                            │                       Fill Confirmation
                                            │                           │
                                            ▼                           ▼
                                        Fill Event ◀────────────── Fill Event
                                            │
                                            ├──▶ Journal Agent (record)
                                            ├──▶ Risk Agent (update state)
                                            └──▶ Strategy Agent (re-evaluate)
```

### 4.4 Feedback Loop Flow (Trade → Learning → Improvement)

```
Trade Closed           Analysis Layer          Learning Layer
────────────           ──────────────          ──────────────

Fill Event ──────────▶ Journal Agent ────────▶ Trade Journal Entry
                       │                       │
                       ├─ Record entry/exit    ├─ Entry reasoning
                       ├─ Calculate P&L        ├─ Market context at entry
                       ├─ Record slippage      ├─ Actual vs expected
                       ├─ Tag strategy step    ├─ Screenshot (chart state)
                       │                       │
                       ▼                       ▼
                    Post-Trade ──────────────▶ Performance Metrics
                    Analysis                   │
                       │                       ├─ Win rate by step
                       ├─ What went right?     ├─ Average R:R by session
                       ├─ What went wrong?     ├─ Sentiment accuracy
                       ├─ Model accuracy       ├─ S/R hit rate
                       │                       │
                       ▼                       ▼
                    Auditor Agent ───────────▶ Strategy Adaptation
                    (weekly reflection)        │
                       │                       ├─ Adjust step weights
                       ├─ Review all trades    ├─ Update ML training data
                       ├─ Identify patterns    ├─ Retrain models (monthly)
                       ├─ Score strategy       └─ Parameter optimization
                       │
                       ▼
                    Recommendations ──────────▶ Human Review
                    (auto or HITL)              (approve/reject)
```

---

## 5. Communication Protocols

### 5.1 Protocol Stack

```
┌─────────────────────────────────────────────────────────────────────┐
│                    COMMUNICATION PROTOCOL STACK                       │
│                                                                      │
│  LAYER 4: APPLICATION PROTOCOLS                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ REST API     │  │ WebSocket    │  │ gRPC         │              │
│  │ (Client-     │  │ (Real-time   │  │ (Internal    │              │
│  │  facing)     │  │  streams)    │  │  service-    │              │
│  │              │  │              │  │  to-service) │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
│         │                 │                 │                        │
│  LAYER 3: MESSAGE PATTERNS                                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ Pub/Sub      │  │ Request/     │  │ Event        │              │
│  │ (Broadcast)  │  │ Response     │  │ Sourcing     │              │
│  │              │  │ (RPC)        │  │ (Replay)     │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
│         │                 │                 │                        │
│  LAYER 2: MESSAGE BUS                                                 │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │                    Redis Streams                               │    │
│  │  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │    │
│  │  │ market  │  │ signals  │  │ orders   │  │ system       │  │    │
│  │  │ .data   │  │ .active  │  │ .events  │  │ .health      │  │    │
│  │  └─────────┘  └──────────┘  └──────────┘  └──────────────┘  │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  LAYER 1: TRANSPORT                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ TCP/TLS      │  │ WebSocket    │  │ Unix Socket  │              │
│  │ (Broker      │  │ (Client      │  │ (Local IPC)  │              │
│  │  connections)│  │  connections)│  │              │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.2 Event Bus — Stream Definitions

```yaml
# Redis Streams Configuration
streams:
  market.ticks:
    description: "Real-time tick data per instrument"
    format: { symbol, bid, ask, last, volume, timestamp }
    retention: 24h
    consumers: [strategy-agent, data-pipeline]
    
  market.candles:
    description: "Closed candle events per timeframe"
    format: { symbol, timeframe, open, high, low, close, volume, timestamp }
    retention: 7d
    consumers: [strategy-agent, ml-pipeline]
    
  signals.generated:
    description: "Raw signals from strategy pipeline"
    format: { signal_id, instrument, direction, confidence, reasoning, steps }
    retention: 30d
    consumers: [risk-agent, execution-agent, journal-agent]
    
  signals.approved:
    description: "Risk-approved trade proposals"
    format: { signal_id, instrument, direction, size, entry, sl, tp, risk_score }
    retention: 30d
    consumers: [execution-agent, journal-agent]
    
  orders.events:
    description: "Order lifecycle events"
    format: { order_id, event_type, broker, symbol, status, fill_price, fill_qty }
    retention: indefinite
    consumers: [risk-agent, journal-agent, strategy-agent]
    
  news.articles:
    description: "Ingested news articles"
    format: { article_id, source, headline, content, symbols, timestamp }
    retention: 7d
    consumers: [news-agent]
    
  news.sentiment:
    description: "Processed sentiment scores"
    format: { symbol, sentiment, confidence, source, reasoning, timestamp }
    retention: 30d
    consumers: [strategy-agent, risk-agent]
    
  system.health:
    description: "System health and status events"
    format: { component, status, metrics, timestamp }
    retention: 24h
    consumers: [monitoring, coordinator-agent]
    
  system.alerts:
    description: "Human-attention-required alerts"
    format: { alert_id, severity, category, message, action_required }
    retention: 30d
    consumers: [notification-service, coordinator-agent]
```

### 5.3 Inter-Agent Communication Protocol

```python
# Agent Message Protocol
@dataclass
class AgentMessage:
    """Standard message format for inter-agent communication."""
    message_id: str              # UUID
    source_agent: str            # e.g., "strategy-agent"
    target_agent: str            # e.g., "risk-agent" or "broadcast"
    message_type: MessageType    # REQUEST, RESPONSE, EVENT, COMMAND
    payload: dict                # Message-specific data
    correlation_id: str          # Links request/response pairs
    priority: Priority           # LOW, NORMAL, HIGH, CRITICAL
    timestamp: datetime
    ttl_seconds: int             # Time-to-live (0 = no expiry)
    
class MessageType(Enum):
    REQUEST = "request"          # Needs a response
    RESPONSE = "response"        # Reply to a request
    EVENT = "event"              # Fire-and-forget notification
    COMMAND = "command"          # Direct action instruction
    HEARTBEAT = "heartbeat"      # Health check
```

### 5.4 External API Protocols

| Connection | Protocol | Auth | Format | Rate Limit Strategy |
|------------|----------|------|--------|---------------------|
| MT5 Python API | Local function calls | Login credentials | Python objects | Serialized access (single-threaded) |
| MT5 ZeroMQ | TCP + ZeroMQ | Shared secret | Protobuf | Connection pooling |
| CCXT | HTTPS REST + WSS | API Key + HMAC | JSON | Exponential backoff, 429 respect |
| OANDA | HTTPS REST + Streaming | Bearer token | JSON | 120 req/min, connection limit |
| News APIs | HTTPS REST | API Key | JSON | Per-source rate limits |
| Web/Mobile Client | WSS + REST | JWT | JSON | Per-user rate limiting |

---

## 6. Dependency Graph

### 6.1 Module Dependency Matrix

```
                    INFRA  DATA  BROKER  EXEC  STRAT  RISK  NEWS  JOURNAL  AUDIT  GATEWAY  APP
                    ─────  ────  ──────  ────  ─────  ────  ────  ───────  ─────  ───────  ───
INFRA (L0)           ·
DATA (L1)           ───▶    ·
BROKER (L2)                ───▶     ·
EXEC (L3:Exec)             ───▶   ───▶    ·
STRATEGY (L3:Strat)        ───▶          ───▶    ·
RISK (L4)                  ───▶          ───▶  ───▶    ·
NEWS (L3:News)             ───▶                       ───▶    ·
JOURNAL (L4)               ───▶          ───▶  ───▶  ───▶  ───▶     ·
AUDITOR (L4)               ───▶                ───▶        ───▶   ───▶     ·
GATEWAY (L5)                         ───▶  ───▶  ───▶              ───▶     ·
APPS (L6)                                  ───▶                           ───▶    ·
MONITORING (L0)      ───▶  ───▶   ───▶  ───▶  ───▶  ───▶  ───▶   ───▶  ───▶   ───▶  ───▶
```

### 6.2 Critical Path Analysis

**Critical Path (signal → execution):**
```
Market Data → AlphaStack Pipeline (Steps 1-16) → Risk Agent → Execution Agent → Order Manager → Broker
  ~5ms           ~50-200ms (LLM steps)       ~5ms           ~5ms            ~10ms        ~50-200ms
  
Total: ~125-425ms (forex), ~200-600ms (crypto with exchange latency)
```

**Non-critical paths (can run in parallel):**
- News Agent: continuous, independent
- Journal Agent: event-driven, async
- Auditor Agent: periodic (weekly), batch
- Data Pipeline: continuous, independent

### 6.3 Failure Impact Analysis

| Module Failure | Impact | Mitigation |
|----------------|--------|------------|
| **Data Pipeline down** | No new signals, existing positions unmanaged | Fail to last known state, alert human, continue managing open positions |
| **Strategy Agent down** | No new trades | Existing positions continue with stops/TPs managed by Execution Agent |
| **Risk Agent down** | **CRITICAL** — No risk checks | HALT ALL NEW TRADES. Existing positions maintain stops. Alert human. |
| **Execution Agent down** | Cannot execute new trades | Queue orders, alert human. Stops/TPs still active at broker. |
| **Broker connection down** | Cannot execute or get data | Failover to backup broker if available. Alert human. |
| **News Agent down** | No sentiment updates | Continue with stale sentiment. Not critical for execution. |
| **Journal Agent down** | No trade recording | Buffer events in Redis. Replay on recovery. |
| **Event Bus down** | **CRITICAL** — All communication stops | System enters safe mode: close all positions, halt trading. |

---

## 7. Deployment Topology

### 7.1 Phase 1: Development & Paper Trading ($7 Micro Account)

```
┌─────────────────────────────────────────────────────────────┐
│                    LOCAL DEVELOPMENT MACHINE                  │
│                      (Pop!_OS 24.04)                         │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                  Docker Compose Stack                   │  │
│  │                                                        │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐            │  │
│  │  │ Python   │  │ Redis    │  │TimescaleDB│            │  │
│  │  │ Trading  │  │ (Event   │  │(Market    │            │  │
│  │  │ Engine   │  │  Bus)    │  │ Data)     │            │  │
│  │  └──────────┘  └──────────┘  └──────────┘            │  │
│  │                                                        │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐            │  │
│  │  │ FastAPI  │  │Prometheus│  │ Grafana  │            │  │
│  │  │ Gateway  │  │          │  │          │            │  │
│  │  └──────────┘  └──────────┘  └──────────┘            │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────┐  ┌──────────┐                                 │
│  │ MT5      │  │ Tauri    │                                 │
│  │ Terminal │  │ Desktop  │                                 │
│  │ (Wine)   │  │ App      │                                 │
│  └──────────┘  └──────────┘                                 │
│                                                              │
│  Resources: 4 CPU, 8GB RAM, 50GB SSD                        │
│  Cost: $0 (local machine)                                    │
└─────────────────────────────────────────────────────────────┘
```

### 7.2 Phase 2: Live Trading VPS ($100 - $10K Capital)

```
┌─────────────────────────────────────────────────────────────┐
│                    VPS (Hetzner CX31)                        │
│                    $15/month                                  │
│                    4 CPU, 8GB RAM, 80GB SSD                  │
│                    Location: Frankfurt (close to MT5 servers) │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                  Docker Compose Stack                   │  │
│  │                                                        │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐            │  │
│  │  │ Python   │  │ Redis    │  │TimescaleDB│            │  │
│  │  │ Trading  │  │          │  │          │            │  │
│  │  │ Engine   │  │          │  │          │            │  │
│  │  └──────────┘  └──────────┘  └──────────┘            │  │
│  │                                                        │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐            │  │
│  │  │ FastAPI  │  │Prometheus│  │ Grafana  │            │  │
│  │  │ Gateway  │  │ + Loki   │  │          │            │  │
│  │  └──────────┘  └──────────┘  └──────────┘            │  │
│  │                                                        │  │
│  │  ┌──────────┐  ┌──────────┐                           │  │
│  │  │ MT5      │  │ Nginx    │                           │  │
│  │  │ (Wine)   │  │ (Reverse │                           │  │
│  │  │          │  │  Proxy)  │                           │  │
│  │  └──────────┘  └──────────┘                           │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │ Tauri    │  │ Web App  │  │ Flutter  │                  │
│  │ Desktop  │  │ (Remote) │  │ Mobile   │                  │
│  │ (Local)  │  │          │  │          │                  │
│  └──────────┘  └──────────┘  └──────────┘                  │
└─────────────────────────────────────────────────────────────┘
```

### 7.3 Phase 3: Multi-Broker Production ($10K - $100K Capital)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    CLOUD INFRASTRUCTURE (AWS / Hetzner Cloud)            │
│                    ~$80-150/month                                        │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    KUBERNETES CLUSTER                             │    │
│  │                                                                  │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │    │
│  │  │ Trading      │  │ Data         │  │ API          │          │    │
│  │  │ Engine Pod   │  │ Pipeline Pod │  │ Gateway Pod  │          │    │
│  │  │ (2 replicas) │  │ (2 replicas) │  │ (2 replicas) │          │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘          │    │
│  │                                                                  │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │    │
│  │  │ Agent        │  │ News         │  │ ML           │          │    │
│  │  │ Orchestrator │  │ Service      │  │ Inference    │          │    │
│  │  │ Pod          │  │ Pod          │  │ Pod (GPU)    │          │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘          │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │Managed   │  │ Managed  │  │ S3       │  │ CloudFlare│              │
│  │PostgreSQL│  │ Redis    │  │ (Models) │  │ (CDN/DDoS)│              │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘              │
└─────────────────────────────────────────────────────────────────────────┘
```

### 7.4 Phase 4: Institutional ($100K+ Capital)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    INSTITUTIONAL DEPLOYMENT                              │
│                    ~$500-2000/month                                      │
│                                                                          │
│  ┌────────────────────────────┐  ┌────────────────────────────┐        │
│  │  PRIMARY REGION            │  │  DR REGION                 │        │
│  │  (London / Equinix LD4)    │  │  (Frankfurt)               │        │
│  │                            │  │                            │        │
│  │  ┌──────┐ ┌──────┐        │  │  ┌──────┐ ┌──────┐        │        │
│  │  │K8s   │ │GPU   │        │  │  │K8s   │ │GPU   │        │        │
│  │  │Nodes │ │Nodes │        │  │  │Nodes │ │Nodes │        │        │
│  │  └──────┘ └──────┘        │  │  └──────┘ └──────┘        │        │
│  │                            │  │                            │        │
│  │  ┌──────┐ ┌──────┐        │  │  ┌──────┐                 │        │
│  │  │Times-│ │Click-│        │  │  │Times-│                 │        │
│  │  │caleDB│ │House │        │  │  │caleDB│                 │        │
│  │  └──────┘ └──────┘        │  │  └──────┘                 │        │
│  └────────────────────────────┘  └────────────────────────────┘        │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │  BROKER COLOCATION                                              │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │    │
│  │  │MT5 Server│  │CCXT      │  │IBKR      │  │FIX       │      │    │
│  │  │(FXPesa)  │  │(Binance) │  │Gateway   │  │Gateway   │      │    │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘      │    │
│  └────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 8. Scaling Architecture: $7 → Institutional

### 8.1 Scaling Phases Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    SCALING ROADMAP                                       │
│                                                                          │
│  PHASE 1         PHASE 2         PHASE 3         PHASE 4         PHASE 5│
│  $7              $100            $10K            $100K           $1M+   │
│  Paper/Live      Live Trading    Multi-Broker    Institutional   Prime  │
│  ────────────    ────────────    ────────────    ────────────    ────── │
│                                                                          │
│  1 pair          3-5 pairs       10-20 pairs     20+ pairs       50+    │
│  1 broker        1 broker        2-3 brokers     5+ brokers      DMA    │
│  1 timeframe     3 timeframes    5 timeframes    5+ TFs          Full   │
│  SQLite          PostgreSQL      TimescaleDB     + ClickHouse    + Kafka│
│  Local machine   VPS ($15/mo)    Cloud K8s       Multi-region    Colo   │
│  Manual review   Semi-auto       Mostly auto     Fully auto      Auto   │
│  Basic ML        FinBERT         + LLM           + RL models     Custom │
│  No news         News feeds      + Sentiment     + Alt data      + DMA  │
│                                                                          │
│  ◀─────── Progressive Autonomy ────────▶                                │
│  HITL everything → HITL risk → HITL large → Audit only → Full auto     │
└─────────────────────────────────────────────────────────────────────────┘
```

### 8.2 Scaling Dimensions

| Dimension | Phase 1 ($7) | Phase 2 ($100) | Phase 3 ($10K) | Phase 4 ($100K) | Phase 5 ($1M+) |
|-----------|-------------|----------------|-----------------|------------------|-----------------|
| **Pairs** | EUR/USD only | EUR/USD, GBP/USD, USD/JPY | 10-20 majors + crosses | 20+ forex + crypto | 50+ all asset classes |
| **Brokers** | FXPesa MT5 | FXPesa MT5 | + CCXT (Binance/Bybit) | + OANDA, IBKR | + Prime brokerage, DMA |
| **Timeframes** | H1, H4 | M15, H1, H4, D1 | M5, M15, H1, H4, D1 | M1, M5, M15, H1, H4, D1 | Full multi-TF |
| **Strategies** | AlphaStack only | AlphaStack + basic news filter | AlphaStack + sentiment + regime | Multiple strategies | Strategy portfolio |
| **ML Models** | None → basic | FinBERT sentiment | + regime classifier, S/R ML | + RL TP optimizer, CNN patterns | + custom transformers |
| **Database** | SQLite | PostgreSQL | TimescaleDB + Redis | + ClickHouse | + Kafka + distributed |
| **Execution** | Market orders | + Limit orders | + Partial TPs | + TWAP (for >1 lot) | + SOR, dark pools |
| **Risk** | Fixed % risk | + Max drawdown | + Correlation limits | + VaR, stress testing | + Full risk analytics |
| **News** | None | Economic calendar | + RSS + FinBERT | + Reuters API | + Alt data feeds |
| **Monitoring** | Console logs | + Grafana | + Prometheus + Loki | + PagerDuty | + 24/7 ops |
| **Autonomy** | HITL all trades | HITL >2% risk | HITL >5% risk | HITL black swan only | Audit only |
| **Latency** | Doesn't matter | <500ms preferred | <200ms preferred | <50ms preferred | <10ms required |
| **Uptime** | Best effort | 95% | 99% | 99.9% | 99.99% |

### 8.3 Scaling Triggers

```python
# When to scale each dimension

SCALING_TRIGGERS = {
    "pairs": {
        "trigger": "Win rate > 55% over 100+ trades on current pair",
        "action": "Add next correlated pair, run paper trading for 50 trades",
    },
    "brokers": {
        "trigger": "Capital > $5K OR need crypto exposure",
        "action": "Add CCXT connector for crypto, keep MT5 for forex",
    },
    "timeframes": {
        "trigger": "Need finer entry precision OR holding time < 1 hour",
        "action": "Add lower timeframes with hierarchy rules",
    },
    "ml_models": {
        "trigger": "1000+ labeled trade outcomes available",
        "action": "Train first ML model (sentiment or regime)",
    },
    "database": {
        "trigger": "SQLite queries > 100ms OR need concurrent access",
        "action": "Migrate to PostgreSQL + Redis cache",
    },
    "autonomy": {
        "trigger": "Win rate > 60% over 200+ trades, max drawdown < 15%",
        "action": "Reduce HITL threshold by 50%",
    },
    "execution": {
        "trigger": "Average position > 1.0 lot OR slippage > 1 pip",
        "action": "Implement TWAP, consider multi-broker routing",
    },
    "infrastructure": {
        "trigger": "Capital > $50K OR uptime < 99%",
        "action": "Move to Kubernetes, add monitoring, DR",
    },
}
```

### 8.4 Data Scaling Strategy

```
$7 → $100:      SQLite (single file, <1GB)
                 In-memory cache (Python dict)
                 
$100 → $10K:    PostgreSQL (single instance)
                 Redis cache (hot data: last 1000 candles per pair)
                 ~10GB storage
                 
$10K → $100K:   TimescaleDB (auto-partitioned time-series)
                 Redis Streams (event bus + cache)
                 ClickHouse (analytics, backtesting)
                 ~100GB storage
                 
$100K → $1M:    TimescaleDB cluster (multi-node)
                 Redis cluster (HA)
                 ClickHouse cluster (analytics)
                 S3/MinIO (model artifacts, backups)
                 ~1TB storage
                 
$1M+:           Distributed TimescaleDB
                 Kafka (event sourcing, audit trail)
                 ClickHouse cluster (analytics)
                 Object storage (data lake)
                 ~10TB+ storage
```

### 8.5 Execution Scaling Strategy

```
$7:              Fixed micro lot (0.01)
                 Market orders only
                 1 broker (FXPesa MT5)
                 Manual spread checking
                 
$100:            % risk per trade (1-2%)
                 Market + limit orders
                 1 broker, session-aware execution
                 Spread filter (skip if > 2x average)
                 
$10K:            Kelly criterion position sizing
                 + Partial take profits (3 levels)
                 2-3 brokers (MT5 + CCXT)
                 Basic execution algos
                 
$100K:           Optimal f sizing
                 + TWAP for orders > 1 lot
                 + Multi-broker smart routing
                 + Slippage tracking per broker
                 
$1M+:            Full institutional execution
                 + VWAP, iceberg orders
                 + Dark pool access
                 + FIX protocol
                 + Co-location near matching engines
```

---

## 9. Security Architecture

### 9.1 Security Layers

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SECURITY ARCHITECTURE                              │
│                                                                      │
│  LAYER 1: NETWORK                                                    │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ TLS 1.3 everywhere · VPN for admin access · DDoS protection │   │
│  │ Firewall rules (allowlist only) · Network segmentation       │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  LAYER 2: AUTHENTICATION & AUTHORIZATION                             │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ JWT tokens (short-lived) · API keys (scoped) · RBAC          │   │
│  │ Broker credentials encrypted at rest (AES-256-GCM)           │   │
│  │ Hardware security module (HSM) for institutional             │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  LAYER 3: APPLICATION                                                │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ Input validation · SQL injection prevention · XSS protection │   │
│  │ Rate limiting per user/API key · Request signing              │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  LAYER 4: DATA                                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ Encryption at rest (AES-256) · Encryption in transit (TLS)   │   │
│  │ Secrets in Vault/SOPS · No credentials in code/config        │   │
│  │ PII data masking in logs · Audit trail for all access        │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  LAYER 5: OPERATIONAL                                                │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ Automated security scanning · Dependency vulnerability checks│   │
│  │ Incident response playbook · Regular credential rotation     │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### 9.2 Credential Management

| Credential Type | Storage | Rotation | Access |
|----------------|---------|----------|--------|
| Broker API keys | Encrypted vault (SOPS/env) | Quarterly | Only Execution Agent |
| Database passwords | Docker secrets / K8s secrets | Monthly | Only backend services |
| JWT signing keys | HSM / K8s secrets | Quarterly | API Gateway only |
| News API keys | Environment variables | Annually | Only News Agent |
| TLS certificates | Auto-renewed (Let's Encrypt) | Auto (90 days) | Nginx / Traefik |

---

## 10. Technology Stack Summary

### 10.1 Complete Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Language (Primary)** | Python 3.12+ | Strategy, ML, orchestration, API |
| **Language (Performance)** | Rust (PyO3) | Tick processing, indicators, hot paths |
| **Language (MT5)** | MQL5 | Signal receiver EA, native indicators |
| **Framework (API)** | FastAPI | REST + WebSocket API gateway |
| **Framework (Desktop)** | Tauri 2.x | Desktop application shell |
| **Framework (Web)** | React 19 + TypeScript | Web companion + Desktop frontend |
| **Framework (Mobile)** | Flutter 3.x | Mobile companion app |
| **Orchestration** | LangGraph | Multi-agent workflow orchestration |
| **Event Bus** | Redis Streams | Inter-module event routing |
| **Cache** | Redis | Hot market data, session state |
| **Database (Time-Series)** | TimescaleDB | OHLCV, tick data, time-series |
| **Database (OLTP)** | PostgreSQL | Orders, accounts, config, journal |
| **Database (Analytics)** | ClickHouse | Backtesting, audit, analytics |
| **Object Storage** | S3 / MinIO | Model artifacts, backups, charts |
| **ML Framework** | PyTorch | Model training and inference |
| **ML Models** | FinBERT, custom LSTMs, XGBoost | Sentiment, regime, pattern recognition |
| **LLM Integration** | DeepSeek / Qwen (via API) | News reasoning, trade analysis |
| **Technical Indicators** | TA-Lib + Custom Rust | Indicator calculations |
| **Broker (Forex)** | MetaTrader5 Python API | FXPesa integration |
| **Broker (Crypto)** | CCXT | Multi-exchange crypto access |
| **Broker (Institutional)** | FIX Protocol | Direct market access |
| **IPC (MT5 Bridge)** | ZeroMQ | Low-latency Python↔MQL5 |
| **Charts** | Lightweight Charts (TradingView) | Real-time charting |
| **Monitoring** | Prometheus + Grafana | Metrics and dashboards |
| **Logging** | Loki + Promtail | Centralized logging |
| **Containerization** | Docker + Docker Compose | Development and small deployments |
| **Orchestration** | Kubernetes (K8s) | Production deployment |
| **CI/CD** | GitHub Actions | Automated testing and deployment |
| **Secrets** | SOPS + age | Encrypted configuration |

### 10.2 Technology Decision Rationale

| Decision | Chosen | Over | Why |
|----------|--------|------|-----|
| Primary language | Python | Rust, C++ | ML ecosystem, rapid iteration, community |
| Performance | Rust (PyO3) | C++, Cython | Safety, speed, Python interop |
| Desktop | Tauri 2.x | Electron | 5MB vs 200MB, Rust security, native perf |
| Mobile | Flutter | React Native | True single codebase, 95% code sharing |
| Event bus | Redis Streams | Kafka, NATS | Simple, fast, sufficient for scale, built-in cache |
| Time-series DB | TimescaleDB | InfluxDB, QuestDB | PostgreSQL compatible, mature, auto-partitioning |
| Analytics DB | ClickHouse | Druid, Pinot | Blazing fast reads, simple operations |
| ML framework | PyTorch | TensorFlow | Pythonic, research-friendly, ONNX export |
| Orchestration | LangGraph | CrewAI, AutoGen | Graph-based control, persistent state, HITL support |
| Broker (forex) | MT5 Python API | OANDA (Phase 1) | FXPesa is MT5-native, best for $7 start |
| Broker (crypto) | CCXT | Custom | Unified API for 100+ exchanges |

---

## Appendix A: Glossary

| Term | Definition |
|------|-----------|
| **AlphaStack** | Valentine Money Printing Machine — the core 16-step trading strategy |
| **UOM** | Unified Order Manager — single source of truth for all orders across brokers |
| **BCA** | Broker Connector Abstraction — plugin interface for broker integrations |
| **HITL** | Human-in-the-Loop — checkpoints requiring human approval |
| **SOR** | Smart Order Routing — routing orders to the best venue |
| **TWAP** | Time-Weighted Average Price — execution algorithm splitting orders over time |
| **VWAP** | Volume-Weighted Average Price — execution algorithm weighted by volume |
| **SMC** | Smart Money Concepts — institutional order flow analysis |
| **S/R** | Support and Resistance — key price levels |
| **OB** | Order Block — institutional supply/demand zone |
| **FVG** | Fair Value Gap — imbalance in price delivery |
| **R:R** | Risk-to-Reward ratio |
| **VaR** | Value at Risk — statistical measure of potential loss |
| **ADX** | Average Directional Index — trend strength indicator |
| **ATR** | Average True Range — volatility indicator |
| **RSI** | Relative Strength Index — momentum oscillator |
| **FinBERT** | Financial BERT — NLP model fine-tuned for financial text |
| **DMA** | Direct Market Access — bypassing broker for exchange access |
| **ECN** | Electronic Communication Network — electronic order matching |
| **STP** | Straight-Through Processing — orders passed directly to liquidity providers |

---

## Appendix B: Configuration Schema

```yaml
# alpha-stack config.yaml (simplified)

system:
  mode: "paper"  # paper | live
  log_level: "INFO"
  timezone: "Africa/Nairobi"  # EAT for FXPesa
  
strategy:
  name: "alphastack"
  version: "1.0"
  instruments: ["EUR/USD"]
  timeframes: ["H1", "H4", "D1"]
  min_confidence: 0.65  # Minimum aggregate confidence to trade
  
risk:
  max_risk_per_trade: 0.02  # 2% of account
  max_daily_loss: 0.05      # 5% of account
  max_drawdown: 0.15        # 15% max drawdown
  max_open_positions: 3
  max_correlation: 0.7      # Skip trade if correlated > 0.7
  
execution:
  mode: "market"  # market | limit | smart
  max_slippage_pips: 3
  spread_filter_multiplier: 2.0  # Skip if spread > 2x average
  kill_zones: ["London", "NY_Overlap"]
  avoid_news_minutes: 30  # Don't trade 30min before/after high-impact news
  
brokers:
  - id: "fxpesa"
    type: "mt5"
    enabled: true
    server: "FXPesa-Demo"
    login: "${MT5_LOGIN}"
    password: "${MT5_PASSWORD}"
    
  - id: "binance"
    type: "ccxt"
    enabled: false
    exchange: "binance"
    api_key: "${BINANCE_API_KEY}"
    api_secret: "${BINANCE_API_SECRET}"
    
database:
  timescale:
    host: "localhost"
    port: 5432
    database: "alpha_stack"
  redis:
    host: "localhost"
    port: 6379
    
agents:
  strategy:
    model: "deepseek-v3"
    temperature: 0.1
    max_tokens: 4096
  risk:
    model: "qwen-2.5-72b"
    temperature: 0.0
  news:
    model: "deepseek-v3"
    finbert_enabled: true
  journal:
    model: "qwen-2.5-7b"  # Lightweight for journaling
    
autonomy:
  level: "semi_auto"  # full_hitl | semi_auto | full_auto
  auto_approve_below_risk: 0.01  # Auto-approve if risk < 1%
  require_approval_above_risk: 0.03
  halt_on_loss_streak: 5
  halt_on_drawdown: 0.10
```

---

*This architecture document is the foundation for all subsequent implementation. Every module, every interface, every data flow described here will be built, tested, and iterated upon. The system is designed to work at $7 and scale to $7M+ — because the architecture doesn't change, only the parameters do.*
