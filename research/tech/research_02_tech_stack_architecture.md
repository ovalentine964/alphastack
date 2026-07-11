# Tech Stack & Architecture Report
## Institutional-Grade AI-Powered Forex/Crypto Trading System

**Date:** 2026-07-11  
**Target Environment:** FXPesa (East Africa) → MT5 | Starting Capital: $7 (micro/cent accounts)  
**Objective:** Design a production-grade, scalable architecture that starts within micro-account constraints but scales to institutional levels.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Core Languages](#2-core-languages)
3. [MT5 Integration Layer](#3-mt5-integration-layer)
4. [Data Pipeline Architecture](#4-data-pipeline-architecture)
5. [AI/ML Frameworks](#5-aiml-frameworks)
6. [Backtesting Frameworks](#6-backtesting-frameworks)
7. [Database & Storage](#7-database--storage)
8. [Message Queues & Streaming](#8-message-queues--streaming)
9. [API Architecture](#9-api-architecture)
10. [Cloud vs Local Deployment](#10-cloud-vs-local-deployment)
11. [Containerization & Orchestration](#11-containerization--orchestration)
12. [Monitoring & Logging](#12-monitoring--logging)
13. [Low-Latency Considerations](#13-low-latency-considerations)
14. [Recommended Stack Summary](#14-recommended-stack-summary)
15. [System Architecture Diagram](#15-system-architecture-diagram)
16. [Cost Analysis](#16-cost-analysis)
17. [Migration Path](#17-migration-path)

---

## 1. Executive Summary

Building an institutional-grade trading system on a $7 starting capital with FXPesa/MT5 requires a **pragmatic, layered approach**. The architecture must be:

- **Start small, scale big** — Begin with Python on a local VPS, evolve to distributed systems
- **MT5-native execution** — Use MT5 as the execution gateway; build intelligence around it
- **Event-driven from day one** — Design for real-time signal processing from the start
- **AI-first architecture** — ML models are not an afterthought; they drive signal generation

**Core Philosophy:** *Separate the research/ML layer (Python) from the execution layer (MQL5/Python MT5 API), connected by a message bus.*

---

## 2. Core Languages

### 2.1 Python — PRIMARY (Research, ML, Orchestration)

| Aspect | Rating | Notes |
|--------|--------|-------|
| ML/AI Ecosystem | ★★★★★ | PyTorch, TensorFlow, scikit-learn, Hugging Face |
| Rapid Prototyping | ★★★★★ | Fastest iteration cycle for strategy development |
| MT5 Integration | ★★★★☆ | `MetaTrader5` pip package; functional but has latency |
| Library Ecosystem | ★★★★★ | pandas, numpy, polars, ta-lib, ccxt |
| Performance | ★★★☆☆ | Slow raw compute; mitigated by C extensions |
| Concurrency | ★★★★☆ | asyncio for I/O-bound; multiprocessing for CPU |

**Verdict:** **Primary language for the entire system.** The ML/AI ecosystem is unmatched. Use NumPy/Polars for data crunching, PyTorch for models, and delegate hot paths to Cython/Rust extensions when needed.

### 2.2 Rust — SECONDARY (Performance-Critical Extensions)

| Aspect | Rating | Notes |
|--------|--------|-------|
| Performance | ★★★★★ | Zero-cost abstractions, no GC pauses |
| Safety | ★★★★★ | Memory safety without garbage collection |
| Python Interop | ★★★★☆ | PyO3/maturin — seamless Python↔Rust bindings |
| Learning Curve | ★★☆☆☆ | Steep; ownership model takes time |
| Ecosystem | ★★★☆☆ | Growing; `ta-rs`, `polars` (written in Rust) |

**Verdict:** **Use for performance-critical components** — tick data processing, real-time signal computation, order routing hot path. Wrap with PyO3 and call from Python.

**Key Libraries:**
- `PyO3` + `maturin` — Python-Rust bindings
- `tokio` — Async runtime for concurrent I/O
- `polars` — DataFrame engine (Rust-core, Python bindings)
- `ta-rs` — Technical indicators in Rust

### 2.3 C++ — NICHE (MT5 Native)

| Aspect | Rating | Notes |
|--------|--------|-------|
| Performance | ★★★★★ | Industry standard for HFT |
| MT5 Native | ★★★★★ | MQL5 is C++-like; native DLL imports |
| ML Ecosystem | ★★☆☆☆ | Limited; requires libtorch bindings |
| Development Speed | ★☆☆☆☆ | Slow, error-prone for rapid iteration |
| Deployment | ★★☆☆☆ | Complex cross-platform builds |

**Verdict:** **Only use if building MQL5 Expert Advisors or custom MT5 indicators.** For the broader system, Python + Rust covers everything C++ would, with faster development.

### 2.4 Julia — NOT RECOMMENDED

| Aspect | Rating | Notes |
|--------|--------|-------|
| Performance | ★★★★☆ | JIT compiled, near-C speed |
| ML Ecosystem | ★★☆☆☆ | Flux.jl exists but immature vs PyTorch |
| Library Ecosystem | ★★☆☆☆ | Small community, few trading libraries |
| Deployment | ★★☆☆☆ | Package compilation is still rough |
| MT5 Integration | ☆☆☆☆☆ | No native bindings |

**Verdict:** **Skip.** Julia's strengths (numerical computing) are well-covered by Python+NumPy/Polars, and its weaknesses (ecosystem, deployment) are dealbreakers for a production trading system.

### 2.5 Language Strategy Summary

```
┌─────────────────────────────────────────────────────┐
│                    LANGUAGE LAYERS                    │
├─────────────────────────────────────────────────────┤
│  Research & ML Layer    → Python (PyTorch, pandas)   │
│  Orchestration Layer    → Python (FastAPI, asyncio)  │
│  Data Processing Layer  → Python + Rust (Polars)     │
│  Execution Layer        → Python MT5 API + MQL5      │
│  Performance Extensions → Rust (PyO3 bindings)       │
│  MT5 Native Indicators  → MQL5 (C++-like)            │
└─────────────────────────────────────────────────────┘
```

---

## 3. MT5 Integration Layer

### 3.1 MetaTrader5 Python Package

The official `MetaTrader5` pip package is the **primary integration point** between our Python system and the FXPesa MT5 terminal.

```python
import MetaTrader5 as mt5

# Initialize connection
mt5.initialize(path=r"C:\Program Files\FXPesa MetaTrader 5\terminal64.exe")

# Login to FXPesa account
mt5.login(server="FXPesa-Demo", login=12345678, password="password")

# Get live tick data
tick = mt5.symbol_info_tick("EURUSD")

# Place order
request = {
    "action": mt5.TRADE_ACTION_DEAL,
    "symbol": "EURUSD",
    "volume": 0.01,        # Micro lot for $7 account
    "type": mt5.ORDER_TYPE_BUY,
    "price": mt5.symbol_info_tick("EURUSD").ask,
    "deviation": 20,
    "magic": 202607,
    "comment": "AI signal",
    "type_time": mt5.ORDER_TIME_GTC,
    "type_filling": mt5.ORDER_FILLING_IOC,
}
result = mt5.order_send(request)
```

**Key Capabilities:**
- ✅ Real-time tick/OHLCV data retrieval
- ✅ Order placement and management
- ✅ Account/position monitoring
- ✅ Symbol info and market data
- ⚠️ **Limitation:** Not suitable for tick-level scalping (latency ~50-200ms per call)
- ⚠️ **Limitation:** Single-threaded access; must serialize MT5 calls

### 3.2 MQL5 Expert Advisors (Hybrid Approach)

For latency-sensitive strategies, build a **thin MQL5 EA** that acts as a signal receiver:

```
MT5 Terminal (FXPesa)
├── MQL5 EA (Signal Receiver)
│   ├── Reads signals from file/pipe/zeroMQ
│   ├── Executes orders with <1ms latency
│   └── Reports fills back to Python
└── Python System (Signal Generator)
    ├── ML model inference
    ├── Signal generation
    └── Risk management
```

**MQL5 ↔ Python Bridge Options:**
1. **File-based** — Write signals to shared file; EA reads on timer (100ms latency)
2. **Named Pipes** — Windows IPC; ~1ms latency
3. **ZeroMQ** — Best option; cross-platform, <1ms latency (see SUM3API paper)
4. **Sockets** — TCP/UDP; flexible but more setup

**Recommended:** ZeroMQ bridge via the `SUM3API` pattern (Rust/ZMQ/MQL5) for production, with the Python MT5 API for research/backtesting.

### 3.3 MT5 Integration Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    MT5 INTEGRATION LAYER                   │
├──────────────────────────────────────────────────────────┤
│                                                            │
│  ┌─────────────┐    ZeroMQ     ┌──────────────────┐      │
│  │  MQL5 EA    │◄────────────►│  Signal Bridge    │      │
│  │  (Executor) │    <1ms       │  (Python/ZMQ)     │      │
│  └──────┬──────┘               └────────┬─────────┘      │
│         │                               │                  │
│    MT5 Terminal              ┌──────────▼──────────┐      │
│    (FXPesa)                  │  Trading Engine      │      │
│                              │  (Python)            │      │
│  ┌─────────────┐             │  - Risk Manager      │      │
│  │  Python MT5  │◄───────────│  - Position Manager  │      │
│  │  API (Data)  │  research   │  - Order Router      │      │
│  └─────────────┘  mode       └─────────────────────┘      │
│                                                            │
└──────────────────────────────────────────────────────────┘
```

### 3.4 FXPesa-Specific Considerations

- **Account Type:** Micro/cent accounts — minimum lot size 0.01 (1,000 units)
- **Leverage:** Up to 1:400 (confirm with FXPesa; high leverage = high risk on $7)
- **Spreads:** Variable; expect 1.5-3.0 pips on EURUSD during liquid hours
- **Server Location:** FXPesa servers likely in London/Equinix LD4 — latency from East Africa ~60-120ms
- **Symbol Suffix:** Check if FXPesa uses suffixes (e.g., `EURUSDm` for micro accounts)

---

## 4. Data Pipeline Architecture

### 4.1 Data Sources & Types

| Data Type | Source | Frequency | Storage |
|-----------|--------|-----------|---------|
| OHLCV (candles) | MT5 API | 1m, 5m, 15m, 1h, 4h, 1d | TimescaleDB |
| Tick Data | MT5 API | Real-time | TimescaleDB (compressed) |
| Order Book | MT5 Market Depth | Real-time | Redis (hot) / ClickHouse (cold) |
| Economic Calendar | Investing.com API / ForexFactory | Daily | PostgreSQL |
| Sentiment Data | Twitter/X API, Reddit, News APIs | Hourly | PostgreSQL |
| Crypto Order Book | CCXT (Binance, Bybit) | Real-time | Redis + ClickHouse |
| Alternative Data | Satellite, Web scraping | Varies | S3/MinIO |

### 4.2 Data Pipeline Design

```
┌────────────────────────────────────────────────────────────────┐
│                     DATA PIPELINE ARCHITECTURE                   │
├────────────────────────────────────────────────────────────────┤
│                                                                  │
│  DATA SOURCES                INGESTION              STORAGE      │
│  ──────────                  ─────────              ───────      │
│                                                                  │
│  MT5 Terminal ──┐                                                │
│                 ├──► Python Collector ──► TimescaleDB            │
│  CCXT Exchanges─┘    (asyncio)           (OHLCV + Ticks)        │
│                                                                  │
│  News/Sentiment──► NLP Pipeline ──► PostgreSQL                   │
│  (RSS, Twitter)    (HuggingFace)    (Features)                   │
│                                                                  │
│  Economic Data ──► Scheduler ──► PostgreSQL                      │
│  (APIs)             (APScheduler)  (Calendar)                    │
│                                                                  │
│  Tick Stream ───► ZeroMQ ──► Real-time Engine ──► Redis          │
│  (MT5/CCXT)        (PUB/SUB)    (Aggregation)    (Order Book)   │
│                                                                  │
└────────────────────────────────────────────────────────────────┘
```

### 4.3 Real-Time Data Ingestion (Python)

```python
# Async tick data collector
import asyncio
import MetaTrader5 as mt5
from datetime import datetime

class TickCollector:
    def __init__(self, symbols: list[str]):
        self.symbols = symbols
        self.running = False
    
    async def collect_ticks(self, symbol: str):
        """Collect ticks at maximum frequency."""
        last_tick_time = 0
        while self.running:
            tick = mt5.symbol_info_tick(symbol)
            if tick and tick.time_msc > last_tick_time:
                last_tick_time = tick.time_msc
                await self.publish_tick(symbol, tick)
            await asyncio.sleep(0.001)  # 1ms polling
    
    async def publish_tick(self, symbol: str, tick):
        """Publish to message bus."""
        await self.redis.xadd(f"ticks:{symbol}", {
            "bid": tick.bid,
            "ask": tick.ask,
            "last": tick.last,
            "volume": tick.volume,
            "timestamp": tick.time_msc
        })
    
    async def run(self):
        self.running = True
        tasks = [self.collect_ticks(s) for s in self.symbols]
        await asyncio.gather(*tasks)
```

### 4.4 Data Quality & Validation

- **Gap detection:** Monitor for missing candles/ticks; auto-fill from backup source
- **Outlier filtering:** Z-score based outlier detection on tick data
- **Timestamp alignment:** Normalize all timestamps to UTC milliseconds
- **Deduplication:** Redis-based dedup for tick streams
- **Validation pipeline:** Schema validation with Pydantic before storage

---

## 5. AI/ML Frameworks

### 5.1 Framework Comparison

| Framework | Use Case | GPU Support | Production Ready | Recommendation |
|-----------|----------|-------------|-----------------|----------------|
| **PyTorch** | Deep learning, custom architectures | ✅ CUDA/MPS | ✅ TorchServe, ONNX | ⭐ **PRIMARY** |
| **TensorFlow** | Production inference, TF Lite | ✅ CUDA | ✅ TF Serving | Secondary (inference) |
| **JAX** | Research, functional ML | ✅ CUDA | ⚠️ Maturing | Research only |
| **scikit-learn** | Classical ML, feature engineering | ❌ | ✅ | Feature models |
| **XGBoost/LightGBM** | Tabular data, gradient boosting | ✅ GPU | ✅ | **Signal classification** |
| **Hugging Face** | NLP, sentiment analysis | ✅ CUDA | ✅ | News/sentiment |

### 5.2 Recommended ML Stack

```python
# Core ML dependencies
requirements_ml = """
# Deep Learning
torch>=2.3.0
torchvision>=0.18.0
torchaudio>=2.3.0

# Classical ML
scikit-learn>=1.4.0
xgboost>=2.0.0
lightgbm>=4.3.0

# NLP / Sentiment
transformers>=4.40.0    # Hugging Face
datasets>=2.18.0
tokenizers>=0.19.0

# Feature Engineering
ta-lib>=0.4.28          # Technical indicators
pandas-ta>=0.3.14       # Additional indicators
featuretools>=1.31.0    # Automated feature engineering

# Experiment Tracking
mlflow>=2.12.0
wandb>=0.17.0           # Optional, for experiment tracking

# Model Serving
onnxruntime>=1.17.0     # Cross-platform inference
"""
```

### 5.3 ML Model Architecture for Trading

```
┌────────────────────────────────────────────────────────────┐
│                    ML MODEL PIPELINE                         │
├────────────────────────────────────────────────────────────┤
│                                                              │
│  Stage 1: FEATURE ENGINEERING                                │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Raw Data → Technical Indicators → Statistical       │    │
│  │  Features → Sentiment Scores → Market Microstructure │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  Stage 2: SIGNAL GENERATION (Ensemble)                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ LSTM/GRU │  │Transform.│  │ XGBoost  │  │Sentiment │    │
│  │ (Price)  │  │ (Multi-T)│  │ (Tabular)│  │ (BERT)   │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘    │
│       └──────────────┼──────────────┼──────────────┘          │
│                      ▼                                        │
│              ┌───────────────┐                                │
│              │ Meta-Learner  │  (Stacking ensemble)          │
│              │ (XGBoost)     │                                │
│              └───────┬───────┘                                │
│                      ▼                                        │
│  Stage 3: RISK-ADJUSTED SIGNAL                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Raw Signal → Position Sizing → Risk Filter →        │    │
│  │  Max Drawdown Check → Final Order                     │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
└────────────────────────────────────────────────────────────┘
```

### 5.4 Model Architectures by Strategy Type

| Strategy Type | Model | Input | Output |
|---------------|-------|-------|--------|
| **Trend Following** | LSTM + Attention | 100-bar OHLCV sequence | Direction + confidence |
| **Mean Reversion** | Transformer | Multi-timeframe features | Reversion probability |
| **Breakout** | CNN + LSTM | Price action patterns | Breakout probability |
| **Sentiment** | FinBERT | News headlines/tweets | Sentiment score |
| **Arbitrage** | XGBoost | Cross-exchange spread | Arb opportunity |
| **Scalping** | LightGBM | Order book imbalance | Micro-direction |

### 5.5 GPU Strategy

For $7 starting capital, **do NOT invest in GPU hardware**. Use:

1. **Google Colab (Free)** — T4 GPU for training; limited sessions
2. **Kaggle Notebooks** — 30h/week P100 GPU; free
3. **Vast.ai / RunPod** — Rent GPU instances for $0.20-0.50/hr when needed
4. **CPU Inference** — ONNX Runtime on CPU is sufficient for live inference (models are small)

**Training Strategy:** Train offline (Colab/Kaggle) → Export to ONNX → Deploy for CPU inference on VPS.

---

## 6. Backtesting Frameworks

### 6.1 Framework Comparison

| Framework | Type | Speed | MT5 Compatible | Crypto Support | Recommendation |
|-----------|------|-------|----------------|----------------|----------------|
| **VectorBT** | Vectorized | ★★★★★ | Via custom adapter | ✅ | ⭐ **PRIMARY** |
| **Backtrader** | Event-driven | ★★★☆☆ | Via MT5 store | ✅ | Secondary |
| **Freqtrade** | Event-driven | ★★★☆☆ | ❌ | ✅ (primary) | Crypto only |
| **Zipline** | Event-driven | ★★★☆☆ | ❌ | ❌ | Deprecated |
| **QuantConnect/Lean** | Event-driven | ★★★★☆ | ❌ | ✅ | Cloud-only |
| **NautilusTrader** | Event-driven | ★★★★★ | Via adapter | ✅ | Advanced users |
| **custom** | Any | ★★★★★ | Full control | Full control | Long-term |

### 6.2 Recommended: VectorBT (Primary) + Custom Engine (Long-term)

**VectorBT** is the recommended primary backtesting framework:

```python
import vectorbt as vbt
import pandas as pd

# Fetch data from MT5 or CCXT
data = vbt.YFData.download("EURUSD", start="2020-01-01")

# Define strategy with vectorized operations
fast_ma = vbt.MA.run(data.close, window=10)
slow_ma = vbt.MA.run(data.close, window=50)

entries = fast_ma.ma_crossed_above(slow_ma)
exits = fast_ma.ma_crossed_below(slow_ma)

# Run backtest
pf = vbt.Portfolio.from_signals(
    data.close, entries, exits,
    init_cash=7,           # Starting capital
    fees=0.0001,           # FXPesa typical spread cost
    freq="1min"
)

# Analyze results
print(pf.stats())
pf.plot().show()
```

**Why VectorBT:**
- **Blazing fast** — Vectorized operations; backtests years of minute data in seconds
- **Parameter optimization** — Built-in grid search across parameter space
- **Walk-forward analysis** — Built-in support for out-of-sample testing
- **Visualization** — Excellent plotting and reporting
- **Flexibility** — Works with any data source (MT5, CCXT, CSV)

**Long-term: Build Custom Event-Driven Engine**

For institutional-grade backtesting that matches live execution exactly:

```python
class BacktestEngine:
    """
    Custom event-driven backtester that mirrors live trading engine.
    Same code paths for backtest and live = no simulation bias.
    """
    def __init__(self, data_feed, strategy, risk_manager, broker_sim):
        self.data_feed = data_feed
        self.strategy = strategy
        self.risk_manager = risk_manager
        self.broker = broker_sim  # Simulates MT5 execution
    
    def run(self):
        for event in self.data_feed:
            if event.type == "TICK":
                self.strategy.on_tick(event)
            elif event.type == "BAR":
                signal = self.strategy.on_bar(event)
                if signal:
                    order = self.risk_manager.validate(signal)
                    if order:
                        self.broker.execute(order)
```

### 6.3 Backtesting Best Practices

1. **Walk-Forward Optimization** — Train on rolling windows, test on next period
2. **Monte Carlo Simulation** — Shuffle trades to estimate worst-case drawdown
3. **Slippage Modeling** — Add realistic slippage (0.1-0.5 pips for FX)
4. **Spread Modeling** — Use variable spreads matching FXPesa conditions
5. **Out-of-Sample Testing** — Always hold out 20-30% of data
6. **Transaction Costs** — Include commission + spread + swap rates
7. **Regime Detection** — Test across trending/ranging/volatile periods

---

## 7. Database & Storage

### 7.1 Database Comparison for Trading Systems

| Database | Type | Write Speed | Query Speed | Compression | SQL | Recommendation |
|----------|------|-------------|-------------|-------------|-----|----------------|
| **TimescaleDB** | Time-series (PostgreSQL) | ★★★★☆ | ★★★★☆ | ★★★★★ | ✅ Full | ⭐ **PRIMARY** |
| **InfluxDB** | Time-series | ★★★★★ | ★★★★☆ | ★★★★☆ | InfluxQL | Monitoring |
| **ClickHouse** | OLAP/Analytics | ★★★★★ | ★★★★★ | ★★★★★ | ✅ SQL-like | Analytics |
| **QuestDB** | Time-series | ★★★★★ | ★★★★★ | ★★★☆☆ | ✅ SQL | Alternative |
| **PostgreSQL** | Relational | ★★★☆☆ | ★★★☆☆ | ★★☆☆☆ | ✅ Full | Metadata |
| **Redis** | In-memory KV | ★★★★★ | ★★★★★ | ☆☆☆☆☆ | RedisQL | Hot cache |
| **SQLite** | Embedded | ★★☆☆☆ | ★★☆☆☆ | ☆☆☆☆☆ | ✅ Full | Local dev |

### 7.2 Recommended: TimescaleDB + Redis + PostgreSQL

**TimescaleDB** (primary time-series store):
```sql
-- Create hypertable for OHLCV data
CREATE TABLE ohlcv (
    time        TIMESTAMPTZ NOT NULL,
    symbol      TEXT NOT NULL,
    timeframe   TEXT NOT NULL,
    open        DOUBLE PRECISION,
    high        DOUBLE PRECISION,
    low         DOUBLE PRECISION,
    close       DOUBLE PRECISION,
    volume      DOUBLE PRECISION
);

SELECT create_hypertable('ohlcv', 'time');

-- Create compressed chunks (70-90% compression for old data)
ALTER TABLE ohlcv SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol, timeframe'
);
SELECT add_compression_policy('ohlcv', INTERVAL '7 days');

-- Continuous aggregate for daily rollups
CREATE MATERIALIZED VIEW ohlcv_daily
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time) AS bucket,\    symbol,
    first(open, time) AS open,
    max(high) AS high,
    min(low) AS low,
    last(close, time) AS close,
    sum(volume) AS volume
FROM ohlcv
WHERE timeframe = '1min'
GROUP BY bucket, symbol;
```

**Redis** (hot cache & real-time state):
```python
import redis.asyncio as redis

class TradingCache:
    def __init__(self):
        self.redis = redis.Redis(host='localhost', port=6379, decode_responses=True)
    
    async def set_position(self, symbol: str, position: dict):
        await self.redis.hset(f"positions:{symbol}", mapping=position)
    
    async def get_latest_signal(self, strategy: str) -> dict:
        return await self.redis.hgetall(f"signals:{strategy}")
    
    async def publish_signal(self, channel: str, signal: dict):
        await self.redis.publish(channel, json.dumps(signal))
    
    async def cache_ohlcv(self, symbol: str, timeframe: str, data: list):
        key = f"ohlcv:{symbol}:{timeframe}"
        await self.redis.rpush(key, *[json.dumps(d) for d in data])
        await self.redis.expire(key, 3600)  # 1h TTL
```

### 7.3 Schema Design

```sql
-- Metadata (PostgreSQL)
CREATE TABLE strategies (
    id          SERIAL PRIMARY KEY,
    name        TEXT UNIQUE NOT NULL,
    version     TEXT NOT NULL,
    config      JSONB NOT NULL,
    status      TEXT DEFAULT 'inactive',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE trades (
    id              SERIAL PRIMARY KEY,
    strategy_id     INTEGER REFERENCES strategies(id),
    symbol          TEXT NOT NULL,
    side            TEXT NOT NULL,  -- 'buy' / 'sell'
    entry_price     DOUBLE PRECISION,
    exit_price      DOUBLE PRECISION,
    volume          DOUBLE PRECISION,
    pnl             DOUBLE PRECISION,
    entry_time      TIMESTAMPTZ,
    exit_time       TIMESTAMPTZ,
    commission      DOUBLE PRECISION,
    slippage        DOUBLE PRECISION,
    metadata        JSONB
);

CREATE TABLE model_artifacts (
    id          SERIAL PRIMARY KEY,
    model_name  TEXT NOT NULL,
    version     TEXT NOT NULL,
    framework   TEXT NOT NULL,  -- 'pytorch', 'xgboost', 'onnx'
    artifact    BYTEA,          -- Serialized model
    metrics     JSONB,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 8. Message Queues & Streaming

### 8.1 Comparison

| System | Type | Latency | Throughput | Persistence | Recommendation |
|--------|------|---------|------------|-------------|----------------|
| **Redis Pub/Sub** | In-memory pub/sub | <1ms | ★★★★☆ | ❌ | ⭐ **Signal distribution** |
| **Redis Streams** | In-memory log | <1ms | ★★★★★ | ✅ | ⭐ **Tick data stream** |
| **ZeroMQ** | Socket library | <0.1ms | ★★★★★ | ❌ | ⭐ **MT5 bridge** |
| **Apache Kafka** | Distributed log | ~5ms | ★★★★★ | ✅ | Scale-out only |
| **RabbitMQ** | Message broker | ~2ms | ★★★☆☆ | ✅ | Task queues |
| **NATS** | Lightweight pub/sub | <1ms | ★★★★★ | ✅ JetStream | Alternative |

### 8.2 Recommended Architecture

```
┌──────────────────────────────────────────────────────────────┐
│               MESSAGE BUS ARCHITECTURE                        │
├──────────────────────────────────────────────────────────────┤
│                                                                │
│  Layer 1: MT5 Bridge (ZeroMQ)                                │
│  ┌─────────┐  ZMQ PUSH/PULL  ┌──────────────┐               │
│  │ MQL5 EA │◄───────────────►│ Signal Bridge │               │
│  └─────────┘  <0.1ms          └──────┬───────┘               │
│                                       │                        │
│  Layer 2: Internal Bus (Redis Streams)                        │
│                              ┌────────▼────────┐              │
│                              │  Event Router    │              │
│                              │  (Python asyncio)│              │
│                              └───┬────┬────┬───┘              │
│                                  │    │    │                    │
│  ┌──────────┐  ┌──────────┐  ┌───▼┐  ┌▼───┐  ┌──────────┐    │
│  │ Tick     │  │ Signal   │  │Risk│  │Pos │  │Execution │    │
│  │ Processor│  │ Generator│  │Mgr │  │Mgr │  │ Engine   │    │
│  └──────────┘  └──────────┘  └────┘  └────┘  └──────────┘    │
│                                                                │
│  Layer 3: Monitoring (Redis Pub/Sub)                          │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  Grafana ◄── Prometheus ◄── Redis Pub/Sub (metrics)   │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                                │
└──────────────────────────────────────────────────────────────┘
```

### 8.3 Implementation

```python
import zmq
import asyncio
import redis.asyncio as redis
from dataclasses import dataclass
import json

@dataclass
class TradingSignal:
    strategy: str
    symbol: str
    direction: str  # 'buy', 'sell', 'close'
    confidence: float
    price: float
    timestamp: int
    metadata: dict

class EventBus:
    def __init__(self):
        self.redis = redis.Redis(host='localhost', port=6379, decode_responses=True)
        self.ctx = zmq.Context()
    
    async def publish_signal(self, signal: TradingSignal):
        """Publish signal to internal bus."""
        await self.redis.xadd('signals:trading', {
            'data': json.dumps(signal.__dict__)
        }, maxlen=10000)
    
    async def consume_signals(self, consumer_group: str, consumer_name: str):
        """Consume signals from stream."""
        while True:
            messages = await self.redis.xreadgroup(
                consumer_group, consumer_name,
                {'signals:trading': '>'},
                count=10, block=1000
            )
            for stream, entries in messages:
                for entry_id, fields in entries:
                    yield json.loads(fields['data'])
                    await self.redis.xack('signals:trading', consumer_group, entry_id)

class MT5Bridge:
    """ZeroMQ bridge to MQL5 EA."""
    def __init__(self, port=5555):
        self.ctx = zmq.Context()
        self.socket = self.ctx.socket(zmq.PAIR)
        self.socket.bind(f'tcp://*:{port}')
    
    def send_order(self, order: dict) -> dict:
        self.socket.send_json(order)
        return self.socket.recv_json()  # Wait for confirmation
    
    def send_signal(self, signal: TradingSignal):
        """Non-blocking signal send."""
        self.socket.send_json(signal.__dict__, zmq.NOBLOCK)
```

---

## 9. API Architecture

### 9.1 FastAPI (Primary API Layer)

```python
from fastapi import FastAPI, WebSocket, Depends
from contextlib import asynccontextmanager
import asyncio

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize connections
    await db.connect()
    await redis.connect()
    yield
    # Shutdown: cleanup
    await db.disconnect()
    await redis.disconnect()

app = FastAPI(title="Trading System API", lifespan=lifespan)

# REST Endpoints
@app.get("/api/v1/portfolio")
async def get_portfolio():
    positions = await position_manager.get_all()
    return {"positions": positions, "equity": await account.equity()}

@app.get("/api/v1/signals")
async def get_signals(strategy: str = None, limit: int = 100):
    return await signal_store.get_recent(strategy, limit)

@app.post("/api/v1/strategy/{name}/toggle")
async def toggle_strategy(name: str, enabled: bool):
    await strategy_manager.toggle(name, enabled)
    return {"status": "ok", "strategy": name, "enabled": enabled}

@app.get("/api/v1/backtest")
async def run_backtest(strategy: str, start: str, end: str):
    result = await backtest_engine.run(strategy, start, end)
    return result

# WebSocket for real-time updates
@app.websocket("/ws/signals")
async def websocket_signals(websocket: WebSocket):
    await websocket.accept()
    pubsub = redis.pubsub()
    await pubsub.subscribe("signals:live")
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await websocket.send_text(message["data"])
    finally:
        await pubsub.unsubscribe()

@app.websocket("/ws/portfolio")
async def websocket_portfolio(websocket: WebSocket):
    await websocket.accept()
    while True:
        portfolio = await position_manager.get_all()
        await websocket.send_json(portfolio)
        await asyncio.sleep(1)
```

### 9.2 API Endpoints Summary

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/portfolio` | GET | Current positions and equity |
| `/api/v1/signals` | GET | Recent trading signals |
| `/api/v1/strategy/{name}/toggle` | POST | Enable/disable strategy |
| `/api/v1/backtest` | GET | Run backtest for strategy |
| `/api/v1/metrics` | GET | System performance metrics |
| `/api/v1/risk` | GET | Risk metrics and limits |
| `/ws/signals` | WS | Real-time signal stream |
| `/ws/portfolio` | WS | Real-time position updates |
| `/ws/ticks` | WS | Real-time tick data |

---

## 10. Cloud vs Local Deployment

### 10.1 Comparison

| Factor | Local VPS (Hetzner/Contabo) | AWS/GCP | Recommendation |
|--------|----------------------------|---------|----------------|
| **Cost** | $5-15/mo | $30-100+/mo | ⭐ VPS for $7 capital |
| **Latency to MT5** | Depends on location | Depends on region | Choose London/EU |
| **GPU** | ❌ Not available | ✅ Available | Train on cloud, infer on VPS |
| **Reliability** | ★★★☆☆ | ★★★★★ | Both acceptable |
| **Scalability** | Manual | Auto-scaling | VPS until proven |
| **Setup** | Simple | Complex | VPS for MVP |

### 10.2 Recommended Setup

**Phase 1 (MVP — $7 capital):**
```
Local Machine or Cheap VPS
├── Hetzner CX22 (2 vCPU, 4GB RAM) — €4.49/mo
├── Location: Falkenstein, Germany (close to MT5 servers)
├── Ubuntu 22.04 LTS
└── Docker Compose deployment
```

**Phase 2 (Growth — $100+ capital):**
```
VPS + Cloud Hybrid
├── Trading VPS: Hetzner CX32 (4 vCPU, 8GB RAM) — €8.49/mo
│   ├── Trading engine
│   ├── MT5 terminal (Wine or Windows VPS)
│   └── TimescaleDB
├── Cloud ML: Google Colab Pro — $10/mo
│   ├── Model training
│   └── Hyperparameter optimization
└── Monitoring: Grafana Cloud Free Tier
```

**Phase 3 (Scale — $1000+ capital):**
```
Full Cloud Infrastructure
├── AWS/GCP with auto-scaling
├── Dedicated GPU instances for training
├── Multi-region deployment
└── Managed databases (TimescaleDB Cloud)
```

### 10.3 MT5 on Linux (VPS)

MT5 runs natively on Windows. Options for Linux VPS:

1. **Wine** — Run MT5 terminal under Wine on Linux (works but fragile)
2. **Windows VPS** — Separate Windows VPS for MT5; Python connects remotely
3. **Docker + Wine** — Containerized MT5 via Wine (community images exist)
4. **MQL5 Cloud** — Use MQL5's built-in cloud for EA execution

**Recommended:** Windows VPS for MT5 (contabo.com ~$7/mo) + Linux VPS for Python system, connected via ZeroMQ.

---

## 11. Containerization & Orchestration

### 11.1 Docker Compose (MVP)

```yaml
# docker-compose.yml
version: '3.8'

services:
  trading-engine:
    build: ./trading-engine
    restart: always
    environment:
      - MT5_HOST=mt5-vps
      - REDIS_URL=redis://redis:6379
      - DATABASE_URL=postgresql://user:pass@timescaledb:5432/trading
    depends_on:
      - redis
      - timescaledb
    volumes:
      - ./config:/app/config
      - ./models:/app/models

  api:
    build: ./api
    ports:
      - "8000:8000"
    environment:
      - REDIS_URL=redis://redis:6379
      - DATABASE_URL=postgresql://user:pass@timescaledb:5432/trading
    depends_on:
      - redis
      - timescaledb

  timescaledb:
    image: timescale/timescaledb:latest-pg16
    volumes:
      - tsdb-data:/var/lib/postgresql/data
    environment:
      POSTGRES_DB: trading
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    volumes:
      - redis-data:/data
    ports:
      - "6379:6379"

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    volumes:
      - grafana-data:/var/lib/grafana

  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

volumes:
  tsdb-data:
  redis-data:
  grafana-data:
```

### 11.2 Kubernetes (Production)

For production scale, use Kubernetes with Helm charts:

```yaml
# Minimal Helm values for trading system
trading:
  engine:
    replicas: 1  # Single instance for stateful trading
    resources:
      requests: { memory: "512Mi", cpu: "500m" }
      limits: { memory: "2Gi", cpu: "2000m" }
  
  api:
    replicas: 2
    resources:
      requests: { memory: "256Mi", cpu: "250m" }

  redis:
    mode: standalone
    persistence: true

  timescaledb:
    persistence:
      size: 50Gi
      storageClass: ssd
```

**Note:** For $7 capital, Docker Compose on a single VPS is sufficient. Kubernetes only when managing multiple strategies across multiple servers.

---

## 12. Monitoring & Logging

### 12.1 Monitoring Stack

```
┌──────────────────────────────────────────────────────────┐
│                  MONITORING ARCHITECTURE                   │
├──────────────────────────────────────────────────────────┤
│                                                            │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐   │
│  │ Trading     │    │ System      │    │ Business    │   │
│  │ Metrics     │    │ Metrics     │    │ Metrics     │   │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘   │
│         │                   │                   │          │
│         └───────────────────┼───────────────────┘          │
│                             ▼                              │
│                    ┌─────────────┐                         │
│                    │ Prometheus  │                         │
│                    └──────┬──────┘                         │
│                           ▼                                │
│                    ┌─────────────┐                         │
│                    │  Grafana    │                         │
│                    │  Dashboards │                         │
│                    └──────┬──────┘                         │
│                           ▼                                │
│                    ┌─────────────┐                         │
│                    │  Alerting   │                         │
│                    │  (PagerDuty/│                         │
│                    │   Telegram) │                         │
│                    └─────────────┘                         │
│                                                            │
│  LOGGING:                                                  │
│  Application → Structured JSON → Loki → Grafana           │
│                                                            │
└──────────────────────────────────────────────────────────┘
```

### 12.2 Key Metrics to Track

```python
from prometheus_client import Counter, Gauge, Histogram

# Trading Metrics
trades_total = Counter('trades_total', 'Total trades', ['strategy', 'side', 'result'])
pnl_total = Gauge('pnl_total', 'Total P&L', ['strategy', 'currency'])
open_positions = Gauge('open_positions', 'Open positions', ['strategy', 'symbol'])
drawdown_current = Gauge('drawdown_current', 'Current drawdown %', ['strategy'])
sharpe_ratio = Gauge('sharpe_ratio', 'Rolling Sharpe ratio', ['strategy'])

# System Metrics
signal_latency = Histogram('signal_latency_seconds', 'Signal generation latency')
order_latency = Histogram('order_latency_seconds', 'Order execution latency')
model_inference_time = Histogram('model_inference_seconds', 'ML model inference time')
data_pipeline_lag = Gauge('data_pipeline_lag_seconds', 'Data pipeline lag')

# Risk Metrics
position_size = Gauge('position_size_lots', 'Position size', ['symbol'])
margin_usage = Gauge('margin_usage_pct', 'Margin usage percentage')
max_drawdown_hit = Gauge('max_drawdown_hit', 'Max drawdown limit breached', ['strategy'])
```

### 12.3 Alerting Rules

```yaml
# prometheus-alerts.yml
groups:
  - name: trading_alerts
    rules:
      - alert: HighDrawdown
        expr: drawdown_current > 15
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Drawdown exceeds 15%"

      - alert: SignalLatencyHigh
        expr: histogram_quantile(0.99, signal_latency_seconds) > 1.0
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Signal latency p99 > 1 second"

      - alert: DataPipelineStale
        expr: data_pipeline_lag_seconds > 60
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Data pipeline is stale"

      - alert: MarginWarning
        expr: margin_usage_pct > 80
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "Margin usage exceeds 80%"
```

### 12.4 Logging

```python
import structlog
import logging

# Structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ]
)

logger = structlog.get_logger()

# Usage
logger.info("order_executed",
    strategy="trend_following_v2",
    symbol="EURUSD",
    side="buy",
    volume=0.01,
    price=1.08542,
    latency_ms=45,
    signal_confidence=0.87
)
```

---

## 13. Low-Latency Considerations

### 13.1 Latency Budget for Retail Trading

```
Total Signal-to-Execution Latency Target: < 500ms

┌─────────────────────────────────────────────┐
│ Component              │ Target   │ Notes    │
├─────────────────────────────────────────────┤
│ Data ingestion         │ < 10ms   │ MT5 API  │
│ Feature computation    │ < 50ms   │ NumPy    │
│ ML inference           │ < 100ms  │ ONNX     │
│ Signal validation      │ < 5ms    │ Checks   │
│ Risk management        │ < 5ms    │ Rules    │
│ Order construction     │ < 1ms    │ Dict     │
│ Network to MT5         │ < 100ms  │ ZMQ      │
│ MT5 execution          │ < 200ms  │ Broker   │
│ Buffer                 │ < 30ms   │          │
└─────────────────────────────────────────────┘
```

### 13.2 Optimization Strategies

**For $7 account (not HFT, but still matters):**

1. **ONNX Runtime for inference** — 3-10x faster than raw PyTorch for inference
   ```python
   import onnxruntime as ort
   session = ort.InferenceSession("model.onnx", providers=['CPUExecutionProvider'])
   result = session.run(None, {"input": features})
   ```

2. **Precomputed features** — Calculate features on bar close, not on every tick
3. **Connection pooling** — Reuse MT5 connections; don't initialize per-trade
4. **Async I/O** — Use asyncio for all I/O-bound operations
5. **Memory-mapped files** — For large historical datasets
6. **Rust extensions** — For hot-path computations (feature engineering)

### 13.3 What NOT to Optimize

For a $7 retail account with FXPesa:
- ❌ Kernel bypass (DPDK/SPDK) — overkill
- ❌ FPGA acceleration — overkill
- ❌ Co-location — not available for retail MT5
- ❌ Custom network stack — not worth it
- ❌ Lock-free data structures — Python GIL prevents this anyway

**Focus on:** Reliable execution, correct risk management, and ML model quality. Latency optimization matters far less than signal quality at this scale.

---

## 14. Recommended Stack Summary

### 14.1 The Stack (MVP → Production)

```
┌────────────────────────────────────────────────────────────┐
│                    RECOMMENDED TECH STACK                    │
├────────────────────────────────────────────────────────────┤
│                                                              │
│  LANGUAGE:        Python 3.11+ (primary), Rust (extensions) │
│  ML FRAMEWORK:    PyTorch + XGBoost + HuggingFace           │
│  BACKTESTING:     VectorBT (primary) + Custom engine         │
│  DATABASE:        TimescaleDB + Redis + PostgreSQL           │
│  MESSAGE BUS:     Redis Streams + ZeroMQ (MT5 bridge)       │
│  API:             FastAPI + WebSocket                        │
│  MT5 INTEGRATION: MetaTrader5 Python API + MQL5 EA (ZMQ)   │
│  CONTAINERIZATION: Docker Compose (MVP) → Kubernetes        │
│  MONITORING:      Prometheus + Grafana + Structured Logging  │
│  DEPLOYMENT:      Hetzner VPS (€5-15/mo)                    │
│  VERSION CONTROL: Git + GitHub                               │
│  CI/CD:           GitHub Actions                             │
│  ML EXPERIMENT:   MLflow                                     │
│                                                              │
└────────────────────────────────────────────────────────────┘
```

### 14.2 Python Dependencies (requirements.txt)

```txt
# Core
MetaTrader5>=5.0.45
fastapi>=0.110.0
uvicorn>=0.29.0
websockets>=12.0
pydantic>=2.7.0

# Data & Analytics
pandas>=2.2.0
numpy>=1.26.0
polars>=0.20.0
scipy>=1.13.0

# ML/AI
torch>=2.3.0
scikit-learn>=1.4.0
xgboost>=2.0.0
lightgbm>=4.3.0
transformers>=4.40.0
onnxruntime>=1.17.0

# Backtesting
vectorbt>=0.26.0

# Technical Analysis
ta-lib>=0.4.28
pandas-ta>=0.3.14

# Database
psycopg2-binary>=2.9.9
redis>=5.0.0
sqlalchemy>=2.0.0
alembic>=1.13.0

# Monitoring
prometheus-client>=0.20.0
structlog>=24.1.0

# Messaging
pyzmq>=26.0.0

# Scheduling
apscheduler>=3.10.0

# ML Experiment Tracking
mlflow>=2.12.0

# Data Collection
ccxt>=4.2.0
requests>=2.31.0
feedparser>=6.0.0

# Development
pytest>=8.0.0
black>=24.0.0
ruff>=0.4.0
mypy>=1.9.0
pre-commit>=3.7.0
```

---

## 15. System Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    INSTITUTIONAL TRADING SYSTEM ARCHITECTURE              │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                      RESEARCH LAYER                              │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │    │
│  │  │ Jupyter  │  │ MLflow   │  │ VectorBT │  │ Feature  │       │    │
│  │  │ Notebook │  │ Tracking │  │ Backtest │  │ Store    │       │    │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                   │                                      │
│                              Model Artifacts                              │
│                                   ▼                                      │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                      ML INFERENCE LAYER                          │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │    │
│  │  │ PyTorch  │  │ XGBoost  │  │ FinBERT  │  │ ONNX RT  │       │    │
│  │  │ (LSTM)   │  │ (Signal) │  │(Sentimnt)│  │ (Deploy) │       │    │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                   │                                      │
│                              Signals                                     │
│                                   ▼                                      │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    TRADING ENGINE LAYER                           │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │    │
│  │  │ Signal   │  │ Risk     │  │ Position │  │ Order    │       │    │
│  │  │ Manager  │  │ Manager  │  │ Manager  │  │ Router   │       │    │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                   │                                      │
│                          Redis Streams + ZeroMQ                          │
│                                   ▼                                      │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    EXECUTION LAYER                                │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐                     │    │
│  │  │ MT5 API  │  │ MQL5 EA  │  │ CCXT     │                     │    │
│  │  │ (Data)   │  │ (ZMQ)    │  │ (Crypto) │                     │    │
│  │  └──────────┘  └──────────┘  └──────────┘                     │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                   │                                      │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    DATA LAYER                                    │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐                     │    │
│  │  │TimescaleDB│  │  Redis   │  │PostgreSQL│                     │    │
│  │  │(Time-srs) │  │ (Cache)  │  │(Metadata)│                     │    │
│  │  └──────────┘  └──────────┘  └──────────┘                     │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    OBSERVABILITY LAYER                            │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │    │
│  │  │Prometheus│  │ Grafana  │  │  Loki    │  │ Alerting │       │    │
│  │  │(Metrics) │  │(Dashboard│  │ (Logs)   │  │(Telegram)│       │    │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 16. Cost Analysis

### 16.1 Monthly Costs by Phase

| Component | Phase 1 (MVP) | Phase 2 (Growth) | Phase 3 (Scale) |
|-----------|---------------|------------------|------------------|
| VPS (Trading) | €4.49/mo (Hetzner CX22) | €8.49/mo (CX32) | €30/mo (CX52) |
| VPS (MT5) | €7/mo (Windows VPS) | €7/mo | €15/mo |
| Database | Self-hosted (free) | Self-hosted | Managed ($30/mo) |
| ML Training | Colab Free | Colab Pro ($10/mo) | GPU VPS ($50/mo) |
| Monitoring | Self-hosted (free) | Grafana Cloud Free | Grafana Cloud Pro |
| Domain + SSL | $0 (self-signed) | $12/year | $12/year |
| **Total** | **~€12/mo** | **~€26/mo** | **~$125/mo** |

### 16.2 ROI Requirements

| Phase | Monthly Cost | Required Monthly Return | Account Size Needed |
|-------|-------------|------------------------|--------------------|
| MVP | €12 (~$13) | 185% | $7 → impossibly high |
| Growth | €26 (~$28) | 28% | $100 |
| Scale | $125 | 12.5% | $1,000 |
| Production | $125 | 1.25% | $10,000 |

**Reality Check:** At $7 starting capital, the system cannot be profitable on infrastructure costs alone. The system must be built as an **investment in capability** — proving the strategy, growing the account, then scaling infrastructure with profits. The MVP VPS cost (~€12/mo) should be treated as education/development expense.

---

## 17. Migration Path

### 17.1 Phase 1: Foundation (Weeks 1-4)

```
□ Set up development environment
□ Install MetaTrader5 Python package
□ Connect to FXPesa demo account
□ Build basic data collection pipeline
□ Implement VectorBT backtesting
□ Create FastAPI skeleton
□ Set up TimescaleDB + Redis (Docker Compose)
□ Basic Prometheus/Grafana monitoring
□ Git repository + CI/CD pipeline
```

### 17.2 Phase 2: Intelligence (Weeks 5-8)

```
□ Feature engineering pipeline
□ Train first ML models (XGBoost baseline)
□ Implement LSTM/Transformer models
□ Walk-forward backtesting framework
□ Signal generation pipeline
□ Risk management module
□ Paper trading integration
□ Structured logging + alerting
```

### 17.3 Phase 3: Execution (Weeks 9-12)

```
□ MQL5 EA for order execution (ZeroMQ bridge)
□ Live trading on demo account
□ Performance monitoring dashboard
□ Position sizing for micro accounts
□ Drawdown protection
□ Telegram notifications
□ Performance attribution analysis
□ Walk-forward validation on live data
```

### 17.4 Phase 4: Production (Weeks 13+)

```
□ Live trading on FXPesa cent account ($7)
□ Continuous model retraining pipeline
□ A/B testing framework for strategies
□ Crypto integration via CCXT
□ Multi-strategy portfolio management
□ Advanced risk analytics
□ Performance reporting
□ Scale infrastructure with profits
```

---

## Appendix A: Key References

| Resource | URL | Description |
|----------|-----|-------------|
| MetaTrader5 Python Docs | `pip install MetaTrader5` | Official MT5 Python package |
| MQL5 Reference | https://www.mql5.com/en/docs | MQL5 language documentation |
| VectorBT | https://vectorbt.dev | Vectorized backtesting framework |
| NautilusTrader | https://nautilustrader.io | Python/Rust algo trading platform |
| SUM3API Paper | SSRN:6143486 | Rust+ZMQ+MQL5 architecture |
| TimescaleDB | https://www.timescale.com | Time-series database |
| FastAPI | https://fastapi.tiangolo.com | Modern Python API framework |
| PyTorch | https://pytorch.org | Deep learning framework |
| CCXT | https://ccxt.com | Crypto exchange connectivity |
| awesome-quant | https://github.com/wilsonfreitas/awesome-quant | Curated quant resources |
| ONNX Runtime | https://onnxruntime.ai | Cross-platform ML inference |
| Polars | https://pola.rs | Fast DataFrame library (Rust) |

---

## Appendix B: Decision Matrix

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Primary language | Python | ML ecosystem, rapid prototyping, MT5 API |
| Performance language | Rust | Safety + speed, PyO3 interop, Polars |
| ML framework | PyTorch | Flexibility, community, production tools |
| Classical ML | XGBoost + LightGBM | Best for tabular financial data |
| Backtesting | VectorBT | Speed, flexibility, parameter optimization |
| Time-series DB | TimescaleDB | PostgreSQL compatibility, compression, continuous aggregates |
| Cache/Streams | Redis | Speed, Pub/Sub, Streams, Lua scripting |
| MT5 bridge | ZeroMQ | Lowest latency, cross-platform, proven pattern |
| API framework | FastAPI | Async, auto-docs, type safety, WebSocket |
| Monitoring | Prometheus + Grafana | Industry standard, free, extensible |
| Containerization | Docker Compose → K8s | Start simple, scale when needed |
| Deployment | Hetzner VPS | Cheap, EU location, reliable |
| ML Training | Colab Free/Pro | Free GPU access for training |
| ML Inference | ONNX Runtime | Fast CPU inference, cross-platform |

---

*Report generated: 2026-07-11*  
*Author: Tech Stack & Architecture Research Agent*  
*Status: Complete*