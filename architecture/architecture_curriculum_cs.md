# Architecture: Valentine's CS/IT Curriculum → Alpha Stack Module Wiring

> **Version:** 1.0 · **Date:** 2026-07-11 · **Author:** Architecture Team
> **Source Research:** [`research/curriculum/research_curriculum_ml_ai.md`](../research/curriculum/research_curriculum_ml_ai.md) — ML/AI curriculum — CS/IT module wiring
> **Status:** Architecture Complete

---

> **System:** Alpha Stack — Institutional-Grade AI Forex/Crypto Trading System
> **Role:** Computer Science Curriculum Architect
> **Date:** 2026-07-11
> **Purpose:** Define how every CS/IT concept from Valentine's coursework and additional CS courses maps to specific Alpha Stack modules, data flows, agent responsibilities, and system infrastructure.

---

## Table of Contents

1. [Curriculum Overview & Grade Analysis](#1-curriculum-overview--grade-analysis)
2. [BIT 113: Fundamentals of IT → Infrastructure Primitives](#2-bit-113-fundamentals-of-it--infrastructure-primitives)
3. [Machine Learning & AI → Prediction & Intelligence Layer](#3-machine-learning--ai--prediction--intelligence-layer)
4. [Data Structures & Algorithms → System Performance Layer](#4-data-structures--algorithms--system-performance-layer)
5. [Database Systems → Data Persistence & Retrieval Layer](#5-database-systems--data-persistence--retrieval-layer)
6. [Integration Wiring: How Everything Connects](#6-integration-wiring-how-everything-connects)
7. [Gap Analysis & Remediation Plan](#7-gap-analysis--remediation-plan)
8. [Agent Assignment Matrix](#8-agent-assignment-matrix)
9. [Cross-Cutting: Multi-Agent, Loop, Quantum, AGI](#9-cross-cutting-multi-agent-loop-quantum-agi)

---

## 1. Curriculum Overview & Grade Analysis

### Valentine's CS/IT Units & Additional Courses

| Unit | Title | Grade | Priority | Key Alpha Stack Role |
|------|-------|-------|----------|---------------------|
| **BIT 113** | Fundamentals of Information Technology | 71% (A-) | 🟡 Solid foundation | Networking, OS, hardware — infrastructure layer |
| **ML/AI** | Machine Learning & AI | Additional | 🔴 Critical | Prediction engine, signal generation, regime detection |
| **DSA** | Data Structures & Algorithms | Additional | 🔴 Critical | Performance, latency, data flow architecture |
| **Database** | Database Systems | Additional | 🔴 Critical | Persistence, retrieval, time-series, real-time state |

### Grade-to-Wiring Gap Map

```
Grade:  A-(71%)   Additional  Additional  Additional
        BIT113    ML/AI       DSA         Database
        ──────    ──────      ──────      ──────
Risk:   LOW       MEDIUM      MEDIUM      MEDIUM

→ BIT 113 provides solid IT foundations — wire immediately
→ Additional CS courses require structured learning before wiring
→ All three additional courses are CRITICAL for Alpha Stack operation
```

### CS → Alpha Stack Module Dependency Chain

```
BIT 113 (Infrastructure)
    │
    ├──→ Networking → Broker API connections, WebSocket feeds
    ├──→ Operating Systems → Process management, memory, threading
    ├──→ Hardware → Latency budgets, CPU/cache awareness
    └──→ Security → API key management, encryption, audit trails
         │
         ▼
DSA (Performance Layer)
    │
    ├──→ Arrays → Tick buffers, feature vectors, signal matrices
    ├──→ Trees → Order book, decision models, price indexing
    ├──→ Graphs → Correlation networks, arbitrage detection, agent topology
    ├──→ Sorting/Searching → Signal ranking, binary search on time-series
    ├──→ Dynamic Programming → RL Bellman equation, optimal execution
    └──→ Complexity Analysis → Latency budgets, scalability planning
         │
         ▼
Database (Persistence Layer)
    │
    ├──→ SQL (PostgreSQL) → Trade ledger, ACID orders, positions
    ├──→ NoSQL (Redis) → Real-time state, pub/sub, agent communication
    ├──→ Time-Series (TimescaleDB) → Market data, continuous aggregates
    ├──→ Data Modeling → Star schema, event sourcing, normalization
    └──→ Query Optimization → Indexing, connection pooling, caching
         │
         ▼
ML/AI (Intelligence Layer)
    │
    ├──→ Supervised Learning → Price prediction, signal classification
    ├──→ Unsupervised Learning → Regime detection, anomaly detection, PCA
    ├──→ Neural Networks → LSTM, Transformer, CNN pattern recognition
    ├──→ Reinforcement Learning → Position sizing, execution, strategy optimization
    ├──→ NLP → Sentiment analysis, news parsing, LLM integration
    └──→ Feature Engineering → Technical indicators, cross-asset, temporal features
```

---

## 2. BIT 113: Fundamentals of IT → Infrastructure Primitives

**Grade: A- (71%) | Priority: 🟡 Solid — Wire immediately with targeted reinforcement**

BIT 113 provides the infrastructure literacy upon which the entire Alpha Stack deployment depends. An A- grade indicates adequate understanding with room for reinforcement in specific areas.

### 2.1 Computer Networking → Data Feed & Broker Connectivity

**Concept:** OSI model, TCP/IP, HTTP/HTTPS, WebSocket, DNS, latency, bandwidth
**Alpha Stack Module:** `Network Layer` — Data Feed Adapters & Broker Gateway

```
┌─────────────────────────────────────────────────────────────────┐
│                  NETWORK LAYER — ALPHA STACK                      │
│                                                                   │
│  Data Feeds (Inbound):                                           │
│  ┌──────────┐  WebSocket (persistent)   ┌──────────────────┐   │
│  │ Binance  │◄──────────────────────────│  CcxtAdapter     │   │
│  │ Exchange │  TCP, low-latency         │  (ccxt.pro)      │   │
│  └──────────┘                           └──────────────────┘   │
│  ┌──────────┐  MT5 Protocol (sync)     ┌──────────────────┐   │
│  │ MT5      │◄──────────────────────────│  Mt5Adapter      │   │
│  │ Broker   │  Python MetaTrader5 lib   │  (asyncio wrap)  │   │
│  └──────────┘                           └──────────────────┘   │
│  ┌──────────┐  REST/HTTPS (polling)    ┌──────────────────┐   │
│  │ News RSS │◄──────────────────────────│  NewsRssAdapter  │   │
│  │ Feeds    │  HTTP GET, 15-min cycle   │  (feedparser)    │   │
│  └──────────┘                           └──────────────────┘   │
│                                                                   │
│  Order Routing (Outbound):                                       │
│  ┌──────────────────┐  MT5 API         ┌──────────┐           │
│  │ ExecutionEngine  │─────────────────→│  MT5     │           │
│  │                  │  TCP connection   │  Server  │           │
│  └──────────────────┘                   └──────────┘           │
│  ┌──────────────────┐  REST + WS       ┌──────────┐           │
│  │ ExecutionEngine  │─────────────────→│ Binance  │           │
│  │                  │  HTTPS + WSS      │ API      │           │
│  └──────────────────┘                   └──────────┘           │
│                                                                   │
│  Latency Budget:                                                  │
│  Network (broker → server):  1-5ms (forex), 10-50ms (crypto)   │
│  Internal (Redis → agent):   < 1ms                               │
│  Total tick → order:         < 25ms                              │
└─────────────────────────────────────────────────────────────────┘
```

**Wiring:**
- **TCP/UDP:** WebSocket connections for real-time tick data (persistent, full-duplex)
- **HTTP/HTTPS:** REST API for order placement, account queries, historical data backfill
- **DNS:** Resolve exchange/broker endpoints; DNS caching reduces lookup latency
- **WebSocket protocol:** Subscribe/unsubscribe to tick streams; heartbeat for connection health
- **Latency:** Every network hop adds microseconds — BIT 113's networking knowledge directly informs Alpha Stack's latency budget

**Remediation needed:** Minimal — A- is adequate. Reinforce WebSocket lifecycle management and TCP keepalive behavior for persistent connections.

### 2.2 Operating Systems → Process & Memory Management

**Concept:** Processes, threads, memory management, virtual memory, scheduling, file systems
**Alpha Stack Module:** `Runtime Environment` — Alpha Stack Process Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│              ALPHA STACK — PROCESS ARCHITECTURE                   │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Main Process (Python asyncio event loop)                │    │
│  │                                                          │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │    │
│  │  │ Ingestion│ │ Signal   │ │ Execution│ │ Risk     │   │    │
│  │  │ Task     │ │ Agent    │ │ Task     │ │ Monitor  │   │    │
│  │  │          │ │ Tasks    │ │          │ │ Task     │   │    │
│  │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘   │    │
│  │       │             │            │             │         │    │
│  │       └─────────────┼────────────┼─────────────┘         │    │
│  │                     │            │                        │    │
│  │  ┌──────────────────▼────────────▼────────────────────┐  │    │
│  │  │              Redis (shared state)                   │  │    │
│  │  └────────────────────────────────────────────────────┘  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Background Workers (separate processes)                  │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │    │
│  │  │ Model Trainer│  │ Backtest     │  │ Data         │   │    │
│  │  │ (GPU-bound)  │  │ Engine       │  │ Archiver     │   │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│  Memory Layout:                                                   │
│  L0: Process heap (feature vectors, model weights)     ~500MB    │
│  L1: Redis (hot state, agent communication)            ~256MB    │
│  L2: PostgreSQL/TimescaleDB (shared buffers)           ~1GB      │
│  L3: OS page cache (file-backed data)                  ~2GB      │
│  L4: Disk (cold storage, compressed)                   ~220GB    │
└─────────────────────────────────────────────────────────────────┘
```

**Wiring:**
- **Processes:** Each major component (ingestion, signal generation, execution, training) runs as a separate process for fault isolation
- **Threads:** MT5 adapter uses threads (synchronous library wrapped in asyncio)
- **Memory management:** Python's garbage collector + Redis for shared state; avoid memory leaks in long-running loops
- **Scheduling:** asyncio event loop handles cooperative multitasking; OS scheduler handles process-level parallelism
- **File systems:** TimescaleDB data files on SSD for fast random access; compressed archives on HDD for cold storage

**Remediation needed:** Reinforce understanding of asyncio vs threading for Python-based systems. Practice memory profiling for long-running services.

### 2.3 Hardware Awareness → Latency Optimization

**Concept:** CPU architecture, cache hierarchy, RAM, storage (SSD/HDD), GPU
**Alpha Stack Module:** `Performance Engineering` — Hardware-Aware Optimization

```
HARDWARE LATENCY AWARENESS IN ALPHA STACK:

  CPU L1 Cache:    ~1ns    → Feature vector should fit in L1 (64KB)
  CPU L2 Cache:    ~4ns    → Indicator arrays should fit in L2 (256KB)
  CPU L3 Cache:    ~12ns   → Recent candle buffer fits in L3 (8MB)
  RAM:             ~100ns  → Model weights, Redis database
  NVMe SSD:        ~10μs   → TimescaleDB queries (indexed)
  Network:         ~1ms    → Redis round-trip (localhost)
  Network:         ~10ms   → Exchange API round-trip

  Alpha Stack Optimization:
  ├── Feature vectors: 50 floats × 8 bytes = 400 bytes → fits in L1 ✅
  ├── Last 500 candles: 500 × 6 fields × 8 bytes = 24KB → fits in L2 ✅
  ├── Model weights (XGBoost): ~2MB → fits in L3 ✅
  ├── Full order book: 20 levels × 2 sides × 16 bytes = 640 bytes → L1 ✅
  └── Correlation matrix (50×50): 20KB → fits in L2 ✅
```

**Wiring:**
- **CPU cache awareness:** Keep hot data structures (feature vectors, order book) small enough for L1/L2 cache
- **SSD vs HDD:** TimescaleDB on NVMe SSD for fast random access; archives on HDD
- **GPU:** Reserved for model training (Phase 3+); inference on CPU is sufficient for <50ms targets
- **RAM budget:** 2-4GB total for Phase 1-2 (Python process + Redis + PostgreSQL shared buffers)

**Remediation needed:** Minimal for A- grade. Practice profiling tools (`cProfile`, `memory_profiler`) for identifying bottlenecks.

### 2.4 Information Security → Trading System Security

**Concept:** Encryption, authentication, authorization, secure protocols, threat modeling
**Alpha Stack Module:** `Security Layer` — Credential Management & Audit

```
┌─────────────────────────────────────────────────────────────────┐
│                    SECURITY ARCHITECTURE                          │
│                                                                   │
│  Layer 1: Credential Encryption                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Broker API keys → AES-256-GCM encrypted at rest        │    │
│  │  Database credentials → Environment variables only       │    │
│  │  Session tokens → Cryptographically random, hashed       │    │
│  │  Password hashing → Argon2id (>64MB memory cost)        │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│  Layer 2: Network Security                                       │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  All external APIs → HTTPS/WSS only                      │    │
│  │  Redis → localhost binding, requirepass enabled          │    │
│  │  PostgreSQL → localhost only, SSL required               │    │
│  │  No public ports exposed on production server            │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│  Layer 3: Authorization & Audit                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Role-based access: app (read/write), analytics (read)   │    │
│  │  All orders/signals → immutable append-only log          │    │
│  │  System events → severity-tagged audit trail             │    │
│  │  Backup encryption → AES-256 before external upload      │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│  Layer 4: Trading-Specific Security                              │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Circuit breakers → Auto-halt on anomalous behavior      │    │
│  │  Rate limiting → Prevent runaway order submission         │    │
│  │  Position limits → Hard caps enforced at DB level         │    │
│  │  Kill switch → Emergency halt via Redis pub/sub          │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

**Wiring:**
- **Encryption:** Broker credentials encrypted with AES-256-GCM; encryption key derived from user master key
- **Authentication:** Session tokens with 24h expiry; API keys with SHA-256 hashed storage
- **Authorization:** Database users with least-privilege roles; no admin access from application
- **Audit trail:** Every order, signal, and state change logged immutably to TimescaleDB

**Remediation needed:** Minimal. Reinforce understanding of encryption at rest vs in transit. Practice secure credential rotation procedures.

### 2.5 BIT 113 → Alpha Stack Module Summary

| BIT 113 Concept | Alpha Stack Module | Specific Application |
|----------------|-------------------|---------------------|
| **Networking (TCP/IP)** | Data Feed Adapters | WebSocket connections to exchanges, MT5 protocol |
| **Networking (HTTP)** | REST API Clients | Order placement, historical data, news feeds |
| **Networking (WebSocket)** | Real-time Streams | Tick data, order book updates, signal broadcast |
| **Operating Systems** | Process Architecture | asyncio event loop, thread pool for MT5, worker processes |
| **Memory Management** | Performance Engineering | Cache-aware data structures, Redis hot store |
| **File Systems** | Storage Architecture | TimescaleDB on SSD, compressed archives |
| **Hardware (CPU)** | Latency Optimization | L1/L2 cache-friendly feature vectors |
| **Security** | Credential Management | AES-256-GCM encryption, Argon2id hashing |
| **Security** | Network Security | localhost binding, SSL, no public ports |
| **Security** | Audit Trail | Immutable event log, system_events table |

---

## 3. Machine Learning & AI → Prediction & Intelligence Layer

**Source:** `research_curriculum_ml_ai.md` | `architecture_ai_models.md`
**Priority: 🔴 Critical — The brain of Alpha Stack**

ML/AI concepts map directly to Alpha Stack's 8 model families and 16 strategy steps. This section wires every concept to production modules.

### 3.1 Supervised Learning → Signal Generation Engine

**Concepts:** Linear/Logistic Regression, Decision Trees, Random Forest, XGBoost, SVM, Cross-Validation
**Alpha Stack Module:** `AlphaSignal` — Signal Generation & Classification

```
┌─────────────────────────────────────────────────────────────────┐
│              SUPERVISED LEARNING → SIGNAL ENGINE                  │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  XGBoost / LightGBM — Primary Signal Classifier         │    │
│  │                                                          │    │
│  │  Input Features (~50):                                   │    │
│  │    Technical: RSI, MACD, ATR, ADX, BB, EMA, SMA         │    │
│  │    Structure: S/R score, OB strength, FVG, BOS/CHoCH    │    │
│  │    Context: Session, regime, sentiment, event risk       │    │
│  │    Cross-asset: DXY, VIX, yields, correlations          │    │
│  │                                                          │    │
│  │  Output:                                                 │    │
│  │    Direction: UP / DOWN / FLAT                           │    │
│  │    Confidence: 0.0 – 1.0                                 │    │
│  │    Confluence Score: 0 – 100                             │    │
│  │                                                          │    │
│  │  SHAP Explainability:                                    │    │
│  │    "BUY signal driven by: RSI oversold (+12),           │    │
│  │     bullish MACD cross (+8), high volume (+6),          │    │
│  │     tempered by high VIX (-5)"                          │    │
│  │                                                          │    │
│  │  Latency: < 10ms (ONNX Runtime, CPU)                    │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│  Model Variants:                                                  │
│  ┌──────────────────┬──────────────┬──────────────────────┐     │
│  │ Model            │ Task         │ Retrain Frequency    │     │
│  ├──────────────────┼──────────────┼──────────────────────┤     │
│  │ xgboost_signal   │ Direction    │ Monthly              │     │
│  │ xgboost_confl    │ Confluence   │ Monthly              │     │
│  │ xgboost_sweep    │ Sweep detect │ Monthly              │     │
│  │ xgboost_smc      │ Pattern pred │ Monthly              │     │
│  │ xgboost_entry    │ Entry timing │ Monthly              │     │
│  │ lgbm_session     │ Session vol  │ Monthly              │     │
│  │ rf_liquidity     │ Flow detect  │ Monthly              │     │
│  │ svm_pattern      │ Chart class  │ Quarterly            │     │
│  └──────────────────┴──────────────┴──────────────────────┘     │
│                                                                   │
│  Cross-Validation: Walk-Forward (252d train, 63d test, 21d step)│
│  Validation: Purged CV with 5-bar gap to prevent leakage        │
└─────────────────────────────────────────────────────────────────┘
```

**Concept-to-Module Wiring:**

| ML Concept | Alpha Stack Application | Module |
|-----------|------------------------|--------|
| **Linear Regression** | Baseline price prediction, fast-path analyzer | `AlphaPredict` |
| **Logistic Regression** | Binary direction classification, calibrated probabilities | `AlphaSignal` |
| **Decision Trees** | Rule extraction: "IF RSI<30 AND MACD cross AND vol>2×avg THEN buy" | `AlphaSignal` |
| **Random Forest** | Ensemble voting, feature importance ranking, institutional flow detection | `AlphaEnsemble` |
| **XGBoost/LightGBM** | Primary signal classifier, confluence scoring, SHAP explainability | `AlphaCore` |
| **SVM** | Chart pattern classification, one-class anomaly detection | `AlphaPattern` |
| **Cross-Validation** | Walk-forward strategy validation, purged CV, CPCV | `AlphaBacktest` |
| **Feature Importance** | Dynamic feature leaderboard, automatic feature selection | `AlphaFeatures` |

### 3.2 Unsupervised Learning → Market Understanding Engine

**Concepts:** K-Means, PCA, DBSCAN, Hierarchical Clustering, Autoencoders
**Alpha Stack Module:** `AlphaRegime` — Regime Detection & Anomaly Detection

```
┌─────────────────────────────────────────────────────────────────┐
│           UNSUPERVISED LEARNING → MARKET UNDERSTANDING           │
│                                                                   │
│  K-Means → Market Regime Detection                               │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Features: [returns, volatility, volume, spread,         │    │
│  │             correlation, momentum, ADX]                   │    │
│  │  K = 3-7 regimes (validated by silhouette score)        │    │
│  │  Output: {trending_bull, trending_bear, range,           │    │
│  │           high_vol, low_vol, breakout, crisis}           │    │
│  │  Module: AlphaRegime                                     │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│  PCA → Dimensionality Reduction                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Input: 100+ correlated indicators                       │    │
│  │  Output: 10 uncorrelated principal components            │    │
│  │  PC1 = "Market factor" (~60% variance)                   │    │
│  │  PC2 = "Carry factor" (~15% variance)                    │    │
│  │  PC3 = "Volatility factor" (~10% variance)               │    │
│  │  Module: AlphaPortfolio                                  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│  DBSCAN → Anomaly Detection                                      │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Detect: Flash crashes, liquidity gaps, manipulation     │    │
│  │  Method: Density-based clustering in feature space       │    │
│  │  Noise points = anomalies → trigger risk protocols       │    │
│  │  Module: AlphaRisk                                       │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│  Hierarchical Clustering → Asset Correlation                     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Dendrogram of asset correlations                        │    │
│  │  Reveals: which assets move together at different scales │    │
│  │  Used for: Hierarchical Risk Parity (HRP) portfolio      │    │
│  │  Module: AlphaPortfolio                                  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│  Autoencoders → Compressed Market State                          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Encode 100+ features → 16-dim latent vector             │    │
│  │  High reconstruction error = anomalous market state      │    │
│  │  Latent vector = "market DNA" for similarity search      │    │
│  │  Module: AlphaLatent                                     │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### 3.3 Neural Networks → Pattern & Sequence Engine

**Concepts:** Feedforward, CNN, RNN/LSTM, Transformer, GAN
**Alpha Stack Module:** `AlphaDeep` — Deep Learning Inference

```
┌─────────────────────────────────────────────────────────────────┐
│              NEURAL NETWORKS → DEEP LEARNING ENGINE               │
│                                                                   │
│  LSTM → Sequential Price Prediction                              │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Architecture: 2-layer LSTM (128/64 units) + attention   │    │
│  │  Input: Last 100 bars × 30 features                      │    │
│  │  Output: Direction (3-class) + return + volatility       │    │
│  │  Variants:                                               │    │
│  │    LSTM-Micro:  50 bars, 64 units  (M15, <1ms)          │    │
│  │    LSTM-Std:   100 bars, 128 units (H1,  <5ms)          │    │
│  │    LSTM-Swing: 200 bars, 256 units (H4,  <10ms)         │    │
│  │    LSTM-Vol:   100 bars, 64 units  (vol forecast)        │    │
│  │  Format: ONNX Runtime (CPU)                              │    │
│  │  Module: AlphaSequence                                   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│  Transformer → Multi-Timeframe Analysis                          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Architecture: 4-layer, 8-head attention, d_model=256    │    │
│  │  Input: M15 + H1 + H4 + D1 features (60 total)          │    │
│  │  Cross-timeframe attention: which TF is most informative │    │
│  │  Cross-asset attention: EUR/USD attends to GBP/USD, DXY  │    │
│  │  Efficient: Linformer O(n) instead of O(n²)             │    │
│  │  Latency: < 200ms (CPU)                                  │    │
│  │  Module: AlphaAttention                                  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│  CNN → Chart Pattern Recognition                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  1D convolutions on OHLCV sequences                      │    │
│  │  Multi-scale filters: 3-5 bars (micro), 20-50 bars (macro)│   │
│  │  Classify: H&S, double top/bottom, triangles, flags      │    │
│  │  Transfer learning: ResNet fine-tuned on chart images    │    │
│  │  Latency: < 100ms (CPU)                                  │    │
│  │  Module: AlphaVision                                     │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│  GAN → Synthetic Data Generation                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Generate: Realistic price sequences for backtesting     │    │
│  │  Preserve: Fat tails, volatility clustering, jumps       │    │
│  │  Use: Extend backtesting data, stress test strategies    │    │
│  │  Module: AlphaSynth                                      │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### 3.4 Reinforcement Learning → Decision & Execution Engine

**Concepts:** Q-Learning, DQN, Policy Gradient, PPO, Multi-Agent RL
**Alpha Stack Module:** `AlphaRL` — Strategy Optimization & Execution

```
┌─────────────────────────────────────────────────────────────────┐
│           REINFORCEMENT LEARNING → DECISION ENGINE                │
│                                                                   │
│  PPO → Position Sizing Agent                                     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  State: [confluence, regime, vol, recent_WR, drawdown,   │    │
│  │          session, correlation_exposure, timeofday]        │    │
│  │  Action: Position size multiplier [0.0, 2.0] (continuous)│    │
│  │  Reward: Sharpe-adjusted R-multiple                       │    │
│  │  Safety: Hard caps, consecutive loss reduction, DD limits │    │
│  │  Latency: < 5ms (policy forward pass)                    │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│  DQN → Take-Profit Agent                                         │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  State: [current_R, time_in_trade, vol_regime, regime,   │    │
│  │          atr, structure_alignment, session]               │    │
│  │  Actions: Hold / Close 25% / 50% / 100% / Move SL       │    │
│  │  Reward: R-multiple achieved                              │    │
│  │  Training: Double DQN + prioritized experience replay    │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│  Q-Learning → Execution Agent                                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  State: [order_book_imbalance, spread, volatility,       │    │
│  │          time_remaining, distance_to_level, urgency]      │    │
│  │  Actions: Market / Limit@price / Limit+offset / Wait     │    │
│  │  Reward: Negative slippage (execution vs VWAP)           │    │
│  │  Implementation: Tabular Q-learning (discretized states) │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│  Multi-Agent RL → Agent Swarm Coordination                       │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Specialist agents: trend, mean-reversion, breakout, vol │    │
│  │  CTDE: Centralized training, decentralized execution     │    │
│  │  Communication: Shared embeddings of market observations │    │
│  │  Credit assignment: Shapley value-based contribution     │    │
│  │  Module: AlphaSwarm                                      │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### 3.5 NLP → Information Intelligence Engine

**Concepts:** Sentiment Analysis, NER, Text Classification, LLM Integration, Voice
**Alpha Stack Module:** `AlphaSentiment` / `AlphaLLM` — News & Language Intelligence

```
┌─────────────────────────────────────────────────────────────────┐
│                NLP → INFORMATION INTELLIGENCE                     │
│                                                                   │
│  FinBERT → Financial Sentiment (Tier 2, < 100ms)                │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Input: Headline + first 2 sentences (max 512 tokens)    │    │
│  │  Output: Bullish/Bearish/Neutral + confidence            │    │
│  │  Fine-tuned: Forex/crypto corpus, central bank language  │    │
│  │  Sources: Reuters, Bloomberg, ForexFactory, RSS          │    │
│  │  Aggregation: Source-weighted sentiment score             │    │
│  │  Module: AlphaSentiment                                  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│  NER → Entity Extraction                                         │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Extract: People (Powell), Orgs (Fed), Events (NFP),     │    │
│  │           Instruments (EUR/USD), Values ($50B)            │    │
│  │  Build: Entity-relationship knowledge graph               │    │
│  │  Feed: Structured events to trading agents                │    │
│  │  Module: AlphaNews                                       │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│  LLM → Fundamental Reasoning (Tier 4, 1-5s)                     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Reasoning LLM: DeepSeek-R1 / QwQ (complex analysis)    │    │
│  │  Fast LLM: Qwen-2.5-7B (classification, extraction)     │    │
│  │  RAG: Financial knowledge base + real-time news           │    │
│  │  Tasks: Market commentary, FOMC interpretation,          │    │
│  │         trade thesis generation, performance review       │    │
│  │  Cost: ~$0.22/day                                        │    │
│  │  Module: AlphaLLM                                        │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### 3.6 Feature Engineering → Perception Layer

**Concepts:** Technical indicators, lag features, rolling statistics, time features, cross-asset, feature selection
**Alpha Stack Module:** `AlphaFeatures` — Feature Engineering Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│              FEATURE ENGINEERING → PERCEPTION LAYER               │
│                                                                   │
│  Feature Groups (computed per symbol per timeframe):             │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Price Features (5): OHLCV                               │    │
│  │  Technical Indicators (15): RSI, MACD, ATR, ADX, BB,    │    │
│  │    EMA21/50/200, SMA20, Stoch, CCI, MFI, Williams, OBV  │    │
│  │  Structure Features (10): S/R score, OB strength, FVG,   │    │
│  │    BOS/CHoCH, swing distance, chop score                 │    │
│  │  Context Features (5): Session, hour, day, regime,       │    │
│  │    regime_confidence                                      │    │
│  │  Sentiment Features (3): score, momentum, event_risk     │    │
│  │  Cross-Asset Features (5): DXY return, VIX, yields,      │    │
│  │    correlation_SP500, funding_rate                        │    │
│  │  Temporal Features (5): lag_1-5, rolling_20/50 mean/std  │    │
│  │                                                          │    │
│  │  Total: ~48 features per sample                          │    │
│  │  Storage: Redis (hot), TimescaleDB (cold)                │    │
│  │  Update: On every new candle (M15 primary)               │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│  Feature Selection Pipeline:                                     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  1. Correlation filter: Remove >0.95 pairwise correlated │    │
│  │  2. Mutual information: Rank by MI with target            │    │
│  │  3. SHAP-based: Keep features with mean|SHAP| > threshold│    │
│  │  4. Boruta: Shadow feature comparison                     │    │
│  │  5. Time-varying: Track importance decay over time        │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### 3.7 ML/AI → Alpha Stack Module Summary

| ML Concept | Alpha Stack Module | Latency Tier | Retrain |
|-----------|-------------------|-------------|---------|
| Linear Regression | `AlphaPredict` (baseline) | Tier 1 (<5ms) | Monthly |
| Logistic Regression | `AlphaSignal` (direction) | Tier 2 (<50ms) | Monthly |
| Decision Trees | `AlphaSignal` (rules) | Tier 1 (<5ms) | Monthly |
| Random Forest | `AlphaEnsemble` | Tier 2 (<50ms) | Monthly |
| XGBoost/LightGBM | `AlphaCore` (primary) | Tier 2 (<50ms) | Monthly |
| SVM | `AlphaPattern` | Tier 2 (<50ms) | Quarterly |
| K-Means | `AlphaRegime` | Tier 1 (<5ms) | Monthly |
| PCA | `AlphaPortfolio` | Tier 2 (<50ms) | Monthly |
| DBSCAN | `AlphaRisk` (anomaly) | Tier 2 (<50ms) | Monthly |
| LSTM | `AlphaSequence` | Tier 2-3 (<50-200ms) | Monthly |
| Transformer | `AlphaAttention` | Tier 3 (<200ms) | Quarterly |
| CNN | `AlphaVision` | Tier 3 (<100ms) | Quarterly |
| GAN | `AlphaSynth` (offline) | N/A (offline) | Monthly |
| Q-Learning | `AlphaExec` | Tier 1 (<5ms) | Monthly |
| DQN | `AlphaRL` (TP) | Tier 2 (<30ms) | Monthly |
| PPO | `AlphaRL` (sizing) | Tier 2 (<30ms) | Monthly |
| MARL | `AlphaSwarm` | Tier 2 (<30ms) | Monthly |
| FinBERT | `AlphaSentiment` | Tier 3 (<100ms) | Weekly |
| NER | `AlphaNews` | Tier 3 (<100ms) | Quarterly |
| LLM | `AlphaLLM` | Tier 4 (1-5s) | N/A (API) |
| Feature Engineering | `AlphaFeatures` | Tier 1 (<5ms) | Continuous |

---

## 4. Data Structures & Algorithms → System Performance Layer

**Source:** `research_curriculum_dsa.md`
**Priority: 🔴 Critical — Determines system latency, scalability, and correctness**

DSA concepts are the invisible infrastructure that makes Alpha Stack fast, correct, and scalable. Every data structure maps to a specific performance-critical component.

### 4.1 Linear Data Structures → Data Flow Primitives

**Concepts:** Arrays, Linked Lists, Stacks, Queues
**Alpha Stack Module:** `Data Flow Layer` — Buffers, Pipelines, Event Processing

| DSA Concept | Alpha Stack Application | Module | Complexity |
|------------|------------------------|--------|-----------|
| **Arrays** | OHLCV storage (typed float64[]), tick ring buffers, feature vectors, signal matrices | `TickBuffer`, `FeatureStore` | O(1) access |
| **Linked Lists** | Order book price levels (doubly-linked), trade history chain, strategy pipeline steps | `OrderBook`, `AuditTrail` | O(1) insert/delete at head |
| **Stacks** | Strategy backtesting backtrack, undo operations for parameter tuning, nested order execution | `BacktestEngine`, `ParameterOptimizer` | O(1) push/pop |
| **Queues** | Signal queue (FIFO), order execution queue, tick processing queue, priority queue for signals | `SignalQueue`, `ExecutionQueue` | O(1) enqueue/dequeue |

**Priority Queue (Heap) — Signal Prioritization:**

```
Priority Queue for Signal Scheduling:

  Priority = conviction_score × urgency × liquidity / latency_requirement

  Signal A: score=85, urgency=high, liquidity=1.0  → priority=850
  Signal B: score=72, urgency=medium, liquidity=0.8 → priority=288
  Signal C: score=90, urgency=low, liquidity=1.0    → priority=90

  Execution order: A → B → C

  Implementation: Binary heap — O(log n) insert, O(1) peek, O(log n) extract
```

### 4.2 Trees → Indexing & Decision Structures

**Concepts:** BST, AVL, Red-Black, B-Trees, Tries
**Alpha Stack Module:** `Index Layer` — Order Book, Price Lookup, Symbol Resolution

| DSA Concept | Alpha Stack Application | Module | Complexity |
|------------|------------------------|--------|-----------|
| **BST** | Price level lookup (nearest S/R), strike/expiry indexing, historical price indexing | `PriceLevelIndex` | O(log n) search |
| **AVL Trees** | Real-time order book indexing (balanced under HFT cancellations), dynamic threshold management | `OrderBookIndex` | O(log n) worst-case |
| **Red-Black Trees** | Order book price level management (thousands of insertions/sec), rate limiting timestamp index | `LiveOrderBook` | O(log n) amortized |
| **B-Trees** | Historical data database indexing (TimescaleDB/PostgreSQL internal), backtest results indexing | `TimescaleDB` (internal) | O(log n) disk I/O |
| **Tries** | Symbol/pair lookup ("EUR" → EUR/USD, EUR/GBP, EUR/JPY), strategy name resolution, command parsing | `SymbolLookup`, `CommandParser` | O(m) lookup |

**Order Book as Red-Black Tree:**

```
BIDS (Red-Black Tree)          ASKS (Red-Black Tree)
┌──────────────────┐          ┌──────────────────┐
│  1.0850 [200K]   │◄──root──│  1.0853 [150K]   │
│  1.0849 [350K]   │          │  1.0854 [300K]   │
│  1.0848 [100K]   │          │  1.0855 [250K]   │
│  1.0847 [500K]   │          │  1.0856 [400K]   │
└──────────────────┘          └──────────────────┘

Best bid: 1.0850 (leftmost)    Best ask: 1.0853 (leftmost)
Spread: 0.0003 (3 pips)
Mid: 1.08515

Operations:
  New order at 1.0849 → RB-Tree insert: O(log n)
  Cancel order at 1.0848 → RB-Tree delete: O(log n)
  Best bid/ask → Leftmost node: O(1) (cached)
  Find nearest level to price → BST search: O(log n)
```

### 4.3 Graphs → Network Analysis & Pipeline Orchestration

**Concepts:** BFS, DFS, Shortest Path, MST, DAGs
**Alpha Stack Module:** `Network Layer` — Correlation Networks, Arbitrage, Agent Topology

| DSA Concept | Alpha Stack Application | Module | Complexity |
|------------|------------------------|--------|-----------|
| **BFS** | Correlation network traversal (find all pairs within 2 hops), connected component detection | `CorrelationAnalyzer` | O(V+E) |
| **DFS** | Cycle detection for arbitrage (EUR→GBP→EUR cycle), topological sort for pipeline ordering | `ArbitrageDetector`, `PipelineScheduler` | O(V+E) |
| **Dijkstra** | Optimal trade routing across exchanges, currency conversion chains, risk propagation path | `TradeRouter`, `RiskPropagator` | O((V+E)log V) |
| **MST** | Portfolio diversification graph (minimum correlation connections), feature selection (minimal independent set) | `PortfolioConstructor` | O(E log E) |
| **DAGs** | Multi-agent dependency resolution, strategy pipeline, backtest workflow, ML computational graph | `Orchestrator`, `PipelineEngine` | Topological sort O(V+E) |

**Currency Arbitrage Detection (Bellman-Ford):**

```
Graph: Currencies as nodes, exchange rates as edges

  USD ──1.0850──→ EUR
  EUR ──0.8520──→ GBP
  GBP ──1.2715──→ USD

  Log-transform weights: -ln(rate)
  Negative cycle = arbitrage opportunity

  If sum of -ln(rates) around cycle < 0:
    → Arbitrage exists → Execute triangular trade

  Alpha Stack runs this every tick for all currency triangles
  Complexity: O(V × E) — feasible for ~30 currency nodes
```

### 4.4 Sorting & Searching → Signal Ranking & Data Access

**Concepts:** QuickSort, MergeSort, Binary Search, Hash Tables
**Alpha Stack Module:** `Search Layer` — Ranking, Lookup, Caching

| DSA Concept | Alpha Stack Application | Module | Complexity |
|------------|------------------------|--------|-----------|
| **QuickSort** | Rank assets by signal strength (in-place, cache-friendly), leaderboard maintenance | `SignalRanker` | O(n log n) avg |
| **MergeSort** | Order book reconstruction (stable sort preserves FIFO priority), external sort for large backtest results | `OrderBookBuilder` | O(n log n) guaranteed |
| **Binary Search** | Price level lookup in sorted S/R arrays, historical data range queries (timestamp → position), implied volatility bisection | `PriceLookup`, `HistoricalQuery` | O(log n) |
| **Hash Tables** | Tick data cache (symbol → latest price), symbol mapping (normalized → exchange-specific), position tracking, deduplication | `TickCache`, `SymbolMap`, `PositionTracker` | O(1) avg |

**Hash Table — Tick Cache:**

```python
# O(1) access to latest price for any symbol
tick_cache = {
    "EUR/USD": {"bid": 1.08532, "ask": 1.08545, "time": "13:45:23.123"},
    "GBP/USD": {"bid": 1.27150, "ask": 1.27165, "time": "13:45:23.120"},
    "BTC/USDT": {"bid": 67450.00, "ask": 67452.50, "time": "13:45:23.118"},
    # ... 50+ symbols
}

# Every signal agent reads from this cache — O(1) per lookup
# Updated on every tick via Redis SET
```

### 4.5 Dynamic Programming → RL & Optimization Foundation

**Concepts:** Memoization, Optimal Substructure, Knapsack
**Alpha Stack Module:** `Optimization Layer` — RL Bellman Equation, Capital Allocation

| DSA Concept | Alpha Stack Application | Module | Complexity |
|------------|------------------------|--------|-----------|
| **Memoization** | Cache indicator computations (RSI, correlations), backtest intermediate results, model inference cache | `IndicatorCache`, `BacktestMemo` | Varies |
| **Optimal Substructure** | Bellman equation for RL: V(s) = max{r + γV(s')}, multi-timeframe signal aggregation | `RLAgent` | Bellman: O(|S|×|A|) |
| **Knapsack Problem** | Capital allocation across pairs (maximize return within margin constraints), strategy portfolio selection (maximize alpha within CPU budget) | `CapitalAllocator`, `StrategySelector` | O(nW) |

**Bellman Equation in Alpha Stack RL:**

```
V(state) = max_action {reward(state, action) + γ · V(next_state)}

Where:
  state = {confluence_score, regime, volatility, recent_WR, drawdown, session}
  action = position_size_multiplier ∈ [0.0, 2.0]
  reward = R-multiple × 0.6 + Sharpe_contribution × 0.3 - drawdown_penalty × 0.1
  γ = 0.99 (discount factor)

This IS dynamic programming — the optimal policy is built from
optimal sub-policies at each state. Alpha Stack's PPO agent
approximates this with neural networks.
```

### 4.6 Complexity Analysis → Latency Budgeting

**Concept:** Big O notation, time-space tradeoffs, amortized analysis
**Alpha Stack Module:** `Performance Engineering` — Latency Budget Allocation

```
ALPHA STACK LATENCY BUDGET (tick → order = 25ms total):

  Component                    Complexity    Latency    Budget
  ─────────────────────────    ──────────    ───────    ──────
  Tick ingestion (array)       O(1)          < 1ms      4%
  Feature computation (array)  O(n) n=50     < 2ms      8%
  Indicator update (memoized)  O(1) amort    < 1ms      4%
  Signal generation (XGBoost)  O(log n)      < 10ms     40%
  Risk check (hash lookup)     O(1)          < 1ms      4%
  Position sizing (PPO)        O(1) forward  < 5ms      20%
  Order routing (hash + API)   O(1) + net    < 5ms      20%
  ─────────────────────────    ──────────    ───────    ──────
  TOTAL                                       < 25ms     100%

  CRITICAL: If XGBoost inference exceeds 10ms, the entire
  pipeline breaks. O(log n) guarantees this doesn't happen
  as feature count grows.
```

### 4.7 DSA → Alpha Stack Module Summary

| DSA Layer | Concepts | Alpha Stack Module |
|-----------|---------|-------------------|
| **Data Ingestion** | Arrays, Queues, Hash Tables, Linked Lists | Tick buffers, event queues, symbol mapping |
| **Data Storage** | B-Trees, Arrays, Linked Lists | Historical database, candlestick storage, audit trail |
| **Data Indexing** | BST, AVL, Red-Black Trees, Tries | Order book, price level lookup, symbol resolution |
| **Signal Processing** | Stacks, Priority Queues, DP (Memoization) | Signal pipeline, backtracking optimization, indicator caching |
| **Risk Management** | Graphs (MST, Shortest Path), Knapsack | Portfolio diversification, capital allocation, risk routing |
| **Execution** | Queues, Priority Queues, Hash Tables | Order routing, execution queue, position tracking |
| **Agent Orchestration** | DAGs, Graphs (BFS/DFS), BST | Task scheduling, dependency resolution, agent registry |
| **ML Pipeline** | DAGs, Arrays (Tensors), DP | Computational graphs, feature vectors, model training |
| **System Monitoring** | Linked Lists, Stacks, Amortized Analysis | Event chains, undo history, capacity planning |

---

## 5. Database Systems → Data Persistence & Retrieval Layer

**Source:** `research_curriculum_database.md` | `architecture_database.md` | `architecture_data.md`
**Priority: 🔴 Critical — The memory and nervous system of Alpha Stack**

Database concepts map to Alpha Stack's multi-tier storage architecture: Redis (hot), TimescaleDB (warm), ClickHouse (cold), and the schema designs that make everything queryable.

### 5.1 Relational Databases (SQL) → Trade Ledger & Structured State

**Concepts:** Tables, Keys, JOINs, Indexes, ACID, Views, Stored Procedures
**Alpha Stack Module:** `Trade Ledger` — PostgreSQL Core

| SQL Concept | Alpha Stack Application | Table/Module |
|------------|------------------------|-------------|
| **Tables/Rows/Columns** | Trade records, signal logs, position state, account balances | `trades`, `signals`, `positions`, `accounts` |
| **Primary Keys** | UUID for every trade, order, signal (globally unique, immutable) | All tables use `UUID PRIMARY KEY` |
| **Foreign Keys** | Link trades→orders, signals→trades, positions→trades (full audit chain) | `trades.signal_id → signals.id` |
| **JOINs** | Combine trade data with market data: "Show losing trades during high-vol periods" | `SELECT * FROM trades t JOIN market_data m ON ...` |
| **Indexes** | Composite `(symbol, timestamp)` for time-series, partial index on open positions | 15+ indexes across tables |
| **ACID Transactions** | Atomic trade execution: insert trade + update position + update balance (all-or-nothing) | `BEGIN; INSERT trades; UPDATE positions; UPDATE accounts; COMMIT;` |
| **Views** | Pre-computed performance dashboards: `v_strategy_performance`, `v_agent_leaderboard` | Materialized views, refreshed periodically |
| **Stored Procedures** | `calculate_pnl()`, `check_risk_limits()`, `generate_eod_report()` | Server-side execution for speed |

**ACID Trade Execution:**

```sql
-- This entire transaction is ATOMIC — if any step fails, all roll back
BEGIN ISOLATION LEVEL SERIALIZABLE;

-- 1. Insert the trade record
INSERT INTO trades (id, symbol, direction, entry_price, size, strategy_id, agent_id, status)
VALUES (gen_random_uuid(), 'EUR/USD', 'buy', 1.08532, 100000, 'momentum_v3', 'trend_agent', 'open');

-- 2. Update position
INSERT INTO positions (trade_id, symbol, side, quantity, entry_price, broker_id, strategy_id, agent_id)
VALUES (...);

-- 3. Update account balance
UPDATE accounts SET margin_used = margin_used + 1085.32, margin_free = margin_free - 1085.32
WHERE broker_id = 'fxpesa_main';

-- 4. Log the signal that triggered this
UPDATE signals SET trade_id = ... WHERE signal_id = ...;

COMMIT;
```

### 5.2 NoSQL → Real-Time State & Flexible Storage

**Concepts:** Document Stores (MongoDB), Key-Value (Redis), Column-Family (Cassandra), Graph DB (Neo4j)
**Alpha Stack Module:** `Hot State Layer` — Redis + MongoDB

| NoSQL Concept | Alpha Stack Application | Technology | Latency |
|--------------|------------------------|-----------|---------|
| **Key-Value (Redis)** | Latest tick per symbol, current positions, signal state, agent health, session state | Redis Hash/String | < 1ms |
| **Redis Pub/Sub** | Tick broadcast to agents, signal distribution, regime change notifications, kill switch | Redis Pub/Sub | < 1ms |
| **Redis Streams** | Ordered event log: tick streams, signal streams, order lifecycle, system events | Redis Streams | < 1ms |
| **Document Store** | Strategy configs (heterogeneous parameters), research notes, backtest results (varying schemas) | MongoDB/SQLite | < 10ms |
| **Graph DB** | Asset correlation networks (nodes=assets, edges=correlations), agent communication topology | Neo4j (Phase 3+) | < 50ms |

**Redis — The Nervous System:**

```
Redis serves as Alpha Stack's real-time nervous system:

  Hot Data (< 1ms access):
  ├── tick:EUR/USD          → {bid, ask, spread, mid, time}
  ├── position:main:EUR/USD → {side, qty, entry, P&L, SL, TP}
  ├── account:main          → {balance, equity, margin, daily_pnl}
  ├── signal:trend_agent:EUR/USD → {direction, confidence, score}
  ├── regime:EUR/USD        → {regime, confidence, time}
  └── session_state         → {current_session, time_to_next}

  Pub/Sub Channels (real-time broadcast):
  ├── tick:{symbol}     → All signal agents subscribe
  ├── signal:{symbol}   → Execution + risk subscribe
  ├── regime:{symbol}   → All agents subscribe
  └── kill_switch       → ALL components subscribe

  Streams (durable event log):
  ├── stream:ticks:{symbol}  → 10K messages (~1 hour)
  ├── stream:signals         → 7 days retention
  └── stream:orders          → 30 days retention
```

### 5.3 Time-Series Databases → Market Data Store

**Concepts:** TimescaleDB, InfluxDB, Compression, Continuous Aggregates, Retention Policies
**Alpha Stack Module:** `Market Data Store` — TimescaleDB

| Time-Series Concept | Alpha Stack Application | Implementation |
|-------------------|------------------------|---------------|
| **Hypertables** | All market data tables auto-partitioned by time (ticks, candles, news, on-chain) | `SELECT create_hypertable('ticks', 'time')` |
| **Continuous Aggregates** | Auto-compute 1m→5m→15m→1h→4h→1d OHLCV from tick data | `CREATE MATERIALIZED VIEW candle_1m WITH (timescaledb.continuous)` |
| **Compression** | 95%+ reduction on data older than 7 days (ticks) / 30 days (candles) | `ALTER TABLE ticks SET (timescaledb.compress, ...)` |
| **Retention Policies** | Auto-drop raw ticks after 90 days; keep candles indefinitely (compressed) | `SELECT add_retention_policy('ticks', INTERVAL '90 days')` |
| **Chunk Isolation** | One agent's heavy query doesn't block another's real-time read | Automatic per hypertable |

**Continuous Aggregate Pipeline:**

```
Raw Ticks (millisecond) ──→ candle_1m ──→ candle_5m ──→ candle_15m ──→ candle_1h ──→ candle_4h ──→ candle_1d
  (every tick)            (every 1min)   (every 5min)   (every 15min)  (every 1h)    (every 4h)    (every 1d)

Each level auto-refreshes incrementally — only processes new data, not full re-scan.
All agents query the same continuous aggregates → guaranteed consistency.
```

### 5.4 Data Modeling → Schema Architecture

**Concepts:** Star Schema, Normalization vs Denormalization, Partitioning, Sharding
**Alpha Stack Module:** `Schema Layer` — Analytical & Operational Schemas

| Modeling Concept | Alpha Stack Application | Implementation |
|-----------------|------------------------|---------------|
| **Star Schema** | Analytical warehouse: `fact_trades` surrounded by `dim_strategy`, `dim_pair`, `dim_time`, `dim_agent` | ClickHouse (Phase 3+) |
| **Normalization** | Operational DB: trades, orders, positions normalized for consistency | PostgreSQL (Phase 1) |
| **Denormalization** | Analytics DB: `trade_analytics` pre-joins trades with strategy names, pair details | ClickHouse denormalized table |
| **Partitioning** | `market_data` range-partitioned by month; `trades` list-partitioned by asset class | TimescaleDB automatic |
| **Sharding** | Symbol-based: EUR pairs on shard 1, crypto on shard 2 (Phase 4+) | Future scaling |
| **Event Sourcing** | All state changes stored as append-only events; any state reconstructable from event log | Redis Streams + TimescaleDB |

**Star Schema for Trade Analytics:**

```
                    ┌──────────────┐
                    │  dim_strategy │
                    │──────────────│
                    │ strategy_key │
                    │ name         │
                    │ type         │
                    │ parameters   │
                    └──────┬───────┘
                           │
┌──────────────┐    ┌──────┴───────┐    ┌──────────────┐
│   dim_pair   │────│ fact_trades  │────│   dim_time   │
│──────────────│    │──────────────│    │──────────────│
│ pair_key     │    │ trade_id     │    │ time_key     │
│ symbol       │    │ strategy_key │    │ date         │
│ base/quote   │    │ pair_key     │    │ hour         │
│ asset_class  │    │ time_key     │    │ day_of_week  │
└──────────────┘    │ agent_key    │    │ session      │
                    │ pnl          │    └──────────────┘
                    │ volume       │
                    │ fees         │    ┌──────────────┐
                    └──────┬───────┘────│   dim_agent   │
                           │            │──────────────│
                           │            │ agent_key    │
                           │            │ name         │
                           │            │ type         │
                           │            └──────────────┘
```

### 5.5 Query Optimization → Performance Engineering

**Concepts:** EXPLAIN ANALYZE, Query Plans, Caching, Connection Pooling
**Alpha Stack Module:** `Query Performance Layer`

| Optimization | Alpha Stack Application | Implementation |
|-------------|------------------------|---------------|
| **EXPLAIN ANALYZE** | Diagnose slow queries in trading pipeline | Run on any query > 100ms |
| **Composite Indexes** | `(symbol, timeframe, time DESC)` for market data queries | 15+ indexes across tables |
| **Partial Indexes** | `WHERE status = 'open'` for positions (tiny index, instant lookup) | `CREATE INDEX ... WHERE status = 'open'` |
| **GIN Indexes** | Array containment queries on news symbols | `USING GIN (symbols)` |
| **Connection Pooling** | PgBouncer: 200 client connections → 20 DB connections | Transaction mode pooling |
| **Caching** | L0: process memory (<1μs), L1: Redis (<1ms), L2: TimescaleDB (<100ms) | Tiered cache |
| **Materialized Views** | `v_strategy_performance` pre-aggregates millions of trades | Refresh every 15 minutes |
| **Prepared Statements** | Repeated agent queries use cached query plans | `PREPARE stmt AS SELECT ...` |

### 5.6 Data Pipeline Design → ETL & Streaming

**Concepts:** ETL, CDC, Batch vs Stream, Data Warehousing
**Alpha Stack Module:** `Data Pipeline` — Ingestion to Consumption

```
┌─────────────────────────────────────────────────────────────────┐
│                    DATA PIPELINE ARCHITECTURE                     │
│                                                                   │
│  EXTRACTION (Source Adapters):                                   │
│  MT5, Binance, Bybit, RSS, Reddit, DefiLlama, Coinglass, ...   │
│         │                                                        │
│         ▼                                                        │
│  TRANSFORMATION (Normalization Layer):                           │
│  Validate → Enrich (spread, session, VWAP) → Canonical format   │
│         │                                                        │
│         ├──→ HOT PATH (Redis): < 1ms, real-time state           │
│         ├──→ WARM PATH (Redis Streams): < 100ms, event log      │
│         └──→ COLD PATH (TimescaleDB): < 100ms indexed, historical│
│                                                                   │
│  CDC (Change Data Capture):                                      │
│  TimescaleDB → logical replication → Kafka → ClickHouse          │
│  (Phase 3+ for analytics)                                        │
│                                                                   │
│  BATCH (Nightly):                                                │
│  Model retraining, backtest runs, compliance reports, archival   │
│                                                                   │
│  STREAM (Continuous):                                            │
│  Tick processing, signal generation, risk checks, order routing  │
└─────────────────────────────────────────────────────────────────┘
```

### 5.7 Database → Alpha Stack Module Summary

| DB Concept | Alpha Stack Module | Technology | Latency |
|-----------|-------------------|-----------|---------|
| Tables/Rows | Trade Ledger | PostgreSQL | < 10ms |
| ACID Transactions | Order Execution | PostgreSQL (SERIALIZABLE) | < 5ms |
| Indexes | Market Data Queries | B-tree, GIN, BRIN | < 5ms |
| Views | Performance Dashboards | Materialized views | < 10ms |
| Key-Value | Real-Time State | Redis | < 1ms |
| Pub/Sub | Agent Communication | Redis Pub/Sub | < 1ms |
| Streams | Event Log | Redis Streams | < 1ms |
| Document Store | Strategy Configs | MongoDB/SQLite | < 10ms |
| Hypertables | Market Data | TimescaleDB | < 100ms |
| Continuous Aggregates | OHLCV Computation | TimescaleDB | Auto |
| Compression | Tick Data (95% reduction) | TimescaleDB | Auto |
| Retention | Data Lifecycle | TimescaleDB | Auto |
| Star Schema | Analytics Warehouse | ClickHouse (Phase 3+) | < 5s |
| Connection Pooling | DB Access | PgBouncer | — |
| ETL | Data Pipeline | Custom Python | — |
| CDC | Real-Time Sync | Kafka (Phase 3+) | < 100ms |

---

## 6. Integration Wiring: How Everything Connects

### 6.1 The Complete CS Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    ALPHA STACK — CS CURRICULUM WIRING                    │
│                                                                         │
│  ┌──────────┐    ┌───────────┐    ┌───────────┐    ┌──────────┐       │
│  │ BIT 113  │    │    DSA    │    │ Database  │    │  ML/AI   │       │
│  │          │    │           │    │           │    │          │       │
│  │ Network  │───→│ Arrays    │───→│ Redis     │───→│ Feature  │       │
│  │ OS       │    │ Trees     │    │ Postgres  │    │ Engineer │       │
│  │ Security │    │ Graphs    │    │ TimeScale │    │ Models   │       │
│  │ Hardware │    │ DP        │    │ ClickHouse│    │ NLP      │       │
│  └──────────┘    └───────────┘    └───────────┘    └──────────┘       │
│       │               │               │               │               │
│       ▼               ▼               ▼               ▼               │
│  ┌──────────────────────────────────────────────────────────────┐     │
│  │              INFRASTRUCTURE LAYER                             │     │
│  │  BIT113: Network → Broker connections, WebSocket feeds       │     │
│  │  BIT113: OS → Process architecture, asyncio, threading       │     │
│  │  BIT113: Security → Credential encryption, audit trails      │     │
│  └──────────────────────────────────────────────────────────────┘     │
│       │               │               │               │               │
│       ▼               ▼               ▼               ▼               │
│  ┌──────────────────────────────────────────────────────────────┐     │
│  │              DATA LAYER                                      │     │
│  │  DSA: Arrays → Tick buffers, feature vectors                 │     │
│  │  DSA: Trees → Order book, price indexing                     │     │
│  │  DSA: Hash Tables → Symbol map, position cache              │     │
│  │  DB: Redis → Real-time state, pub/sub, streams              │     │
│  │  DB: TimescaleDB → Market data, continuous aggregates       │     │
│  │  DB: PostgreSQL → Trades, orders, positions (ACID)          │     │
│  └──────────────────────────────────────────────────────────────┘     │
│       │               │               │               │               │
│       ▼               ▼               ▼               ▼               │
│  ┌──────────────────────────────────────────────────────────────┐     │
│  │              INTELLIGENCE LAYER                               │     │
│  │  ML/AI: XGBoost → Signal classification (10ms)               │     │
│  │  ML/AI: LSTM → Price prediction (50ms)                       │     │
│  │  ML/AI: HMM → Regime detection (5ms)                         │     │
│  │  ML/AI: FinBERT → Sentiment (100ms)                          │     │
│  │  ML/AI: PPO → Position sizing (30ms)                         │     │
│  │  ML/AI: LLM → Fundamental reasoning (1-5s)                   │     │
│  └──────────────────────────────────────────────────────────────┘     │
│       │               │               │               │               │
│       ▼               ▼               ▼               ▼               │
│  ┌──────────────────────────────────────────────────────────────┐     │
│  │              EXECUTION LAYER                                  │     │
│  │  DSA: Priority Queue → Signal prioritization                 │     │
│  │  DSA: Queues → Order execution pipeline                      │     │
│  │  DB: ACID → Atomic trade execution                           │     │
│  │  BIT113: Network → Order routing to broker                   │     │
│  └──────────────────────────────────────────────────────────────┘     │
│       │                                                               │
│       ▼                                                               │
│  ┌──────────────────────────────────────────────────────────────┐     │
│  │              FEEDBACK LAYER                                   │     │
│  │  ML/AI: RL → Learn from trade outcomes                       │     │
│  │  DB: Event Sourcing → Replay and audit                       │     │
│  │  DSA: DAGs → Pipeline dependency resolution                  │     │
│  └──────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Cross-Course Concept Dependencies

| Concept | Requires From | Enables In |
|---------|-------------|------------|
| **Arrays** (DSA) | Hardware (BIT 113) | Feature vectors (ML/AI), tick buffers (DB) |
| **Trees** (DSA) | Complexity analysis (DSA) | Order book (DB), decision trees (ML/AI) |
| **Graphs** (DSA) | Arrays (DSA) | Correlation networks (ML/AI), pipeline DAGs (DB) |
| **Redis** (DB) | Networking (BIT 113), Hash tables (DSA) | Agent communication (ML/AI), real-time state |
| **TimescaleDB** (DB) | B-Trees (DSA), OS file systems (BIT 113) | Market data storage, continuous aggregates |
| **XGBoost** (ML/AI) | Decision trees (DSA), Feature engineering (ML/AI) | Signal generation, confluence scoring |
| **LSTM** (ML/AI) | Arrays (DSA), Neural networks (ML/AI) | Price prediction, volatility forecasting |
| **ACID** (DB) | Networking (BIT 113) | Atomic trade execution, position consistency |
| **PPO** (ML/AI) | DP/Bellman (DSA), Neural networks (ML/AI) | Position sizing, strategy optimization |
| **Walk-forward validation** (ML/AI) | Cross-validation (ML/AI), DB queries (DB) | Strategy validation, no-overfitting guarantee |
| **SHAP explainability** (ML/AI) | XGBoost (ML/AI), DB (trade records) | Trade rationale, regulatory compliance |
| **Connection pooling** (DB) | Networking (BIT 113) | Multi-agent concurrent DB access |
| **Compression** (DB) | Complexity analysis (DSA), File systems (BIT 113) | Years of tick data storage |

### 6.3 The Feedback Loops

```
Loop 1: Signal Generation Loop
  DSA (feature arrays) + ML/AI (XGBoost) + DB (Redis hot state)
  → Signal → Execution → P&L → Update models (gradient descent)

Loop 2: Risk Management Loop
  DB (positions via Redis) + DSA (graph traversal for correlation) + ML/AI (anomaly detection)
  → Risk check → Position adjustment → Re-evaluate risk

Loop 3: Data Pipeline Loop
  BIT 113 (network) + DSA (queues) + DB (TimescaleDB + Redis)
  → Tick ingestion → Normalize → Store → Feature compute → Signal generate

Loop 4: Model Retraining Loop
  ML/AI (gradient descent) + DB (historical data) + DSA (DAG pipeline)
  → Train on new data → Validate → Deploy → Monitor → Retrain

Loop 5: Strategy Evolution Loop
  ML/AI (genetic algorithms) + DSA (DP) + DB (backtest results)
  → Evolve strategies → Backtest → Select → Deploy → Monitor → Evolve
```

---

## 7. Gap Analysis & Remediation Plan

### 7.1 Critical Gaps

| Gap | Impact | Remediation |
|-----|--------|-------------|
| **BIT 113 (A-)** — Solid but not expert | Minor: may miss advanced networking optimizations | Practice WebSocket lifecycle, TCP tuning, latency profiling |
| **ML/AI** — Additional course, structured learning needed | HIGH: Core prediction engine depends on this | Follow research_curriculum_ml_ai.md as study guide |
| **DSA** — Additional course, structured learning needed | HIGH: Performance and correctness depend on this | Follow research_curriculum_dsa.md as study guide |
| **Database** — Additional course, structured learning needed | HIGH: Data persistence and retrieval depend on this | Follow research_curriculum_database.md as study guide |

### 7.2 Wiring Readiness Assessment

| Module | Required Courses | Valentine's Readiness | Action |
|--------|-----------------|----------------------|--------|
| **Broker Connections** | BIT 113 (networking) | ✅ A- — adequate | Wire immediately |
| **Process Architecture** | BIT 113 (OS) | ✅ A- — adequate | Wire immediately |
| **Credential Security** | BIT 113 (security) | ✅ A- — adequate | Wire immediately |
| **Tick Buffers** | DSA (arrays, queues) | ⚠️ Additional — learn first | Study arrays, then wire |
| **Order Book** | DSA (red-black trees) | ⚠️ Additional — learn first | Study trees, then wire |
| **Signal Ranking** | DSA (sorting, priority queues) | ⚠️ Additional — learn first | Study sorting, then wire |
| **Pipeline DAGs** | DSA (graphs, topological sort) | ⚠️ Additional — learn first | Study graphs, then wire |
| **Redis Hot Store** | DB (key-value), DSA (hash tables) | ⚠️ Additional — learn first | Study both, then wire |
| **TimescaleDB** | DB (time-series), DSA (B-trees) | ⚠️ Additional — learn first | Study both, then wire |
| **PostgreSQL ACID** | DB (transactions, SQL) | ⚠️ Additional — learn first | Study SQL, then wire |
| **XGBoost Signals** | ML/AI (supervised learning) | ⚠️ Additional — learn first | Study ML, then wire |
| **LSTM Prediction** | ML/AI (neural networks) | ⚠️ Additional — learn first | Study NN, then wire |
| **Regime Detection** | ML/AI (unsupervised learning) | ⚠️ Additional — learn first | Study unsupervised, then wire |
| **RL Agents** | ML/AI (RL), DSA (DP) | ⚠️ Additional — learn first | Study both, then wire |
| **NLP/Sentiment** | ML/AI (NLP) | ⚠️ Additional — learn first | Study NLP, then wire |
| **Feature Engineering** | ML/AI (feature eng) | ⚠️ Additional — learn first | Study feature eng, then wire |

### 7.3 Priority Wiring Order

```
Phase 1 (Immediate — leverage BIT 113 strengths):
  ✅ Broker network connections (BIT 113 networking)
  ✅ Process architecture setup (BIT 113 OS)
  ✅ Security layer (BIT 113 security)
  ✅ Basic Redis setup (key-value — minimal DSA needed)
  ✅ Basic PostgreSQL setup (SQL — minimal DB theory needed)

Phase 2 (After DSA study — performance layer):
  ⚠️ Tick buffer implementation (arrays, ring buffers)
  ⚠️ Order book data structure (red-black trees)
  ⚠️ Signal priority queue (heaps)
  ⚠️ Symbol lookup trie
  ⚠️ Pipeline DAG construction
  ⚠️ Complexity profiling of all modules

Phase 3 (After Database study — persistence layer):
  ⚠️ TimescaleDB hypertables and continuous aggregates
  ⚠️ Redis Streams for event bus
  ⚠️ ACID transaction implementation for trades
  ⚠️ Index optimization (EXPLAIN ANALYZE audit)
  ⚠️ Connection pooling (PgBouncer)
  ⚠️ Materialized views for performance dashboards

Phase 4 (After ML/AI study — intelligence layer):
  ⚠️ Feature engineering pipeline
  ⚠️ XGBoost signal classifier training and deployment
  ⚠️ HMM regime detector
  ⚠️ FinBERT sentiment model
  ⚠️ LSTM price predictor
  ⚠️ PPO position sizing agent
  ⚠️ Walk-forward validation pipeline
  ⚠️ SHAP explainability integration

Phase 5 (Integration — all courses combined):
  ⚠️ End-to-end pipeline: tick → feature → signal → order
  ⚠️ Multi-agent orchestration with all model families
  ⚠️ Closed learning loop (trade outcomes → model updates)
  ⚠️ A/B testing framework (shadow → canary → production)
  ⚠️ Full monitoring and alerting
```

---

## 8. Agent Assignment Matrix

### 8.1 Which CS Course Feeds Which Agent

| Alpha Stack Agent | Primary CS Sources | Secondary CS Sources |
|---|---|---|
| **Perception Agent** | DSA (arrays, feature vectors), DB (Redis hot store) | BIT 113 (network for data feeds) |
| **Prediction Agent** | ML/AI (XGBoost, LSTM, Transformer) | DSA (complexity for latency) |
| **Regime Agent** | ML/AI (HMM, K-Means, DBSCAN) | DB (historical regime data) |
| **Sentiment Agent** | ML/AI (FinBERT, NER, LLM) | BIT 113 (network for news feeds) |
| **Signal Aggregator** | DSA (priority queues, sorting) | ML/AI (ensemble methods) |
| **Entry Agent** | ML/AI (XGBoost confluence, PPO sizing) | DSA (hash tables for position lookup) |
| **Risk Gate Agent** | DSA (graph traversal for correlation) | DB (Redis positions, ACID constraints) |
| **Execution Agent** | DSA (queues, hash tables) | BIT 113 (network for order routing) |
| **TP/Management Agent** | ML/AI (DQN, LSTM) | DB (Redis for real-time position state) |
| **Journal Agent** | DB (PostgreSQL journal tables) | ML/AI (LLM for narrative generation) |
| **Reflection Agent** | ML/AI (RL policy improvement) | DB (trade episode embeddings) |
| **Meta Agent** | DSA (DAG orchestration), ML/AI (MARL) | DB (system_events monitoring) |
| **Data Pipeline** | BIT 113 (networking), DB (TimescaleDB, Redis) | DSA (queues for event processing) |

### 8.2 CS Concept → Agent Wiring Summary

```
BIT 113 (Infrastructure):
  → Broker Gateway: WebSocket connections, API authentication
  → Process Manager: asyncio event loop, thread pool
  → Security Layer: Credential encryption, audit trails

DSA (Performance):
  → Tick Buffer: Ring buffer (circular array) — O(1) append, O(1) access
  → Order Book: Red-black tree — O(log n) insert/delete/lookup
  → Signal Queue: Priority heap — O(log n) insert, O(1) peek
  → Symbol Map: Hash table — O(1) lookup
  → Pipeline: DAG — topological sort for execution order
  → Correlation Network: Graph — BFS/DFS for traversal
  → RL Agent: DP/Bellman — optimal substructure for value functions

Database (Persistence):
  → Redis: Real-time state (ticks, positions, signals) — O(1) access
  → Redis Pub/Sub: Agent communication — < 1ms broadcast
  → Redis Streams: Event log — ordered, durable
  → PostgreSQL: Trade ledger — ACID transactions
  → TimescaleDB: Market data — hypertables, continuous aggregates
  → ClickHouse: Analytics — star schema, denormalized

ML/AI (Intelligence):
  → XGBoost: Signal classification — < 10ms, SHAP explainable
  → LSTM: Price prediction — sequential pattern recognition
  → Transformer: Multi-timeframe analysis — cross-asset attention
  → HMM: Regime detection — hidden state transitions
  → FinBERT: Sentiment — financial text understanding
  → PPO: Position sizing — continuous action RL
  → DQN: Take-profit optimization — discrete action RL
  → LLM: Fundamental reasoning — chain-of-thought analysis
```

---

## 9. Cross-Cutting: Multi-Agent, Loop, Quantum, AGI

### 9.1 Multi-Agent System Integration

Every CS concept maps to Alpha Stack's multi-agent architecture:

| CS Concept | Agent Role | Coordination Mechanism |
|---|---|---|
| Arrays (DSA) | Feature vector provider | Shared Redis feature store |
| Hash Tables (DSA) | State cache | O(1) position/price lookup |
| Priority Queues (DSA) | Signal scheduler | Priority-based execution ordering |
| Graphs (DSA) | Correlation analyzer | Broadcast correlation regime changes |
| Redis (DB) | Nervous system | Pub/Sub for real-time coordination |
| TimescaleDB (DB) | Shared memory | All agents query same historical data |
| XGBoost (ML/AI) | Signal generator | Consensus voting with other models |
| LSTM (ML/AI) | Temporal predictor | Sequential context sharing |
| HMM (ML/AI) | Regime detector | Regime broadcast to all agents |
| FinBERT (ML/AI) | Sentiment provider | Sentiment score distribution |
| PPO (ML/AI) | Position sizer | Safety constraints from risk agent |
| ACID (DB) | Execution guarantor | Serialized order execution |

### 9.2 Loop System Integration

Every CS concept maps to the Sense → Analyze → Act → Reflect loop:

- **Sense**: BIT 113 (network feeds), DSA (feature arrays), DB (Redis hot store), ML/AI (feature engineering)
- **Analyze**: ML/AI (XGBoost, LSTM, Transformer, HMM), DSA (complexity-aware algorithms)
- **Act**: DSA (priority queues, execution queues), DB (ACID transactions), BIT 113 (order routing)
- **Reflect**: ML/AI (RL policy improvement, SHAP), DB (trade journal, agent memories), DSA (memoization)

### 9.3 Quantum Computing Connections

| Classical CS | Quantum Enhancement | Timeline |
|---|---|---|
| Arrays (DSA) | Quantum state vectors (qubit registers) | Near-term |
| Hash Tables (DSA) | Quantum hash functions | Medium-term |
| Graph Algorithms (DSA) | Quantum walk, Grover's search | Near-term |
| Binary Search (DSA) | Quantum search O(√n) | Near-term |
| DP (DSA) | Quantum dynamic programming | Medium-term |
| B-Trees (DB) | Quantum indexing | Medium-term |
| SQL Queries (DB) | Quantum query algorithms (Grover's) | Medium-term |
| XGBoost (ML/AI) | Quantum kernel methods | Near-term |
| SVM (ML/AI) | Quantum SVM (exponentially large feature spaces) | Near-term |
| PCA (ML/AI) | Quantum PCA (exponential speedup) | Near-term |
| Neural Networks (ML/AI) | Quantum neural networks | Medium-term |
| RL (ML/AI) | Quantum RL (superposition over actions) | Medium-term |

### 9.4 AGI Trajectory

Each CS course contributes building blocks toward AGI-capable trading:

| CS Course | AGI Contribution |
|-----------|-----------------|
| **BIT 113** (Infrastructure) | Physical substrate — networking, compute, security for AGI systems |
| **DSA** (Algorithms) | Efficient reasoning infrastructure — search, planning, optimization |
| **Database** (Persistence) | Memory systems — working memory (Redis), long-term memory (PostgreSQL), episodic memory (vector DB) |
| **ML/AI** (Intelligence) | Learning and adaptation — perception, prediction, decision-making, language understanding |

Together, they form the complete cognitive architecture:
- **Perception** (ML/AI: CNN, NLP, feature engineering) → Understanding the market environment
- **Memory** (DB: Redis + PostgreSQL + vector DB) → Working, short-term, and long-term memory
- **Reasoning** (ML/AI: SHAP, LLM; DSA: graphs, DP) → Explainable decision-making
- **Learning** (ML/AI: RL, online learning) → Continuous adaptation from experience
- **Planning** (ML/AI: RL, Transformers; DSA: DP, DAGs) → Multi-step strategy optimization
- **Communication** (ML/AI: LLM, NLP) → Natural language interaction
- **Infrastructure** (BIT 113: networking, OS, security) → Robust, secure, scalable substrate

---

## Appendix A: CS Concept Quick Reference

| Concept | Source | Alpha Stack Module | Key Formula/Pattern |
|---------|--------|-------------------|-------------------|
| Arrays | DSA | TickBuffer, FeatureStore | O(1) indexed access |
| Hash Tables | DSA | TickCache, SymbolMap | O(1) average lookup |
| Red-Black Trees | DSA | OrderBookIndex | O(log n) insert/delete |
| Priority Queues | DSA | SignalQueue | O(log n) insert, O(1) peek |
| BFS/DFS | DSA | CorrelationAnalyzer | O(V+E) traversal |
| Dijkstra | DSA | TradeRouter | O((V+E)log V) shortest path |
| DAGs | DSA | PipelineEngine | Topological sort O(V+E) |
| Bellman Equation | DSA/ML | RLAgent | V(s) = max{r + γV(s')} |
| ACID Transactions | DB | TradeLedger | BEGIN; ...; COMMIT; |
| Redis Pub/Sub | DB | AgentComms | < 1ms broadcast |
| TimescaleDB | DB | MarketDataStore | Hypertables + continuous aggs |
| Star Schema | DB | AnalyticsWarehouse | fact_trades + dimensions |
| Connection Pooling | DB | PgBouncer | 200 clients → 20 connections |
| XGBoost | ML/AI | AlphaCore | Gradient-boosted trees, SHAP |
| LSTM | ML/AI | AlphaSequence | Gated recurrent units |
| Transformer | ML/AI | AlphaAttention | Self-attention, multi-head |
| HMM | ML/AI | AlphaRegime | Transition matrix, Viterbi |
| FinBERT | ML/AI | AlphaSentiment | Fine-tuned BERT for finance |
| PPO | ML/AI | AlphaRL | Clipped surrogate objective |
| Feature Engineering | ML/AI | AlphaFeatures | 48 features per sample |
| Walk-Forward CV | ML/AI | AlphaBacktest | 252d train, 63d test, 21d step |
| WebSocket | BIT 113 | DataFeedAdapter | Persistent full-duplex connection |
| TCP/IP | BIT 113 | NetworkLayer | Low-latency data transport |
| AES-256-GCM | BIT 113 | SecurityLayer | Credential encryption |
| asyncio | BIT 113 | ProcessArchitecture | Cooperative multitasking |

---

## Appendix B: Wiring Checklist

- [ ] **Phase 1** — Wire BIT 113 infrastructure (networking, OS, security)
- [ ] **Phase 1** — Set up Redis (basic key-value + pub/sub)
- [ ] **Phase 1** — Set up PostgreSQL (core tables, ACID transactions)
- [ ] **Phase 2** — Study DSA: arrays, trees, graphs, sorting, DP
- [ ] **Phase 2** — Wire DSA: tick buffers, order book, signal queues, pipeline DAGs
- [ ] **Phase 3** — Study Database: SQL, NoSQL, time-series, indexing, data modeling
- [ ] **Phase 3** — Wire Database: TimescaleDB hypertables, continuous aggregates, indexes
- [ ] **Phase 3** — Wire Database: Redis Streams, connection pooling, materialized views
- [ ] **Phase 4** — Study ML/AI: supervised, unsupervised, neural nets, RL, NLP
- [ ] **Phase 4** — Wire ML/AI: feature engineering pipeline, XGBoost signals, HMM regime
- [ ] **Phase 4** — Wire ML/AI: LSTM prediction, FinBERT sentiment, PPO sizing
- [ ] **Phase 5** — Integration testing: tick → feature → signal → order pipeline
- [ ] **Phase 5** — Multi-agent orchestration with all model families
- [ ] **Phase 5** — Closed learning loop validation
- [ ] **Phase 6** — End-to-end performance profiling (latency budget audit)
- [ ] **Phase 6** — Quantum readiness assessment

---

*This architecture document defines the complete CS/IT wiring from Valentine's academic curriculum to Alpha Stack's production modules. BIT 113 provides the infrastructure foundation. DSA provides the performance layer. Database Systems provide the persistence layer. ML/AI provides the intelligence layer. Together, they form the complete computer science foundation for an institutional-grade AI trading system.*

*Every concept has a home. Every module has CS foundations. The gaps are identified. The plan is clear.*
