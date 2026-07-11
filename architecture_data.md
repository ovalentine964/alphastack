# Alpha Stack — Data Pipeline Architecture

> **Author:** Data Architect  
> **Date:** 2026-07-11  
> **Status:** Architecture Design — Pre-Implementation  
> **Scope:** End-to-end data flow from raw sources to trading agent consumption

---

## 1. Design Principles

| Principle | Rationale |
|-----------|-----------|
| **Free-tier first** | $7 starting capital — every dollar of infrastructure cost must be justified |
| **Event-driven from day one** | Polling doesn't scale; push-based architecture is the foundation |
| **Single source of truth** | One canonical store per data type; consumers read, never duplicate |
| **Schema-on-write for market data, schema-on-read for alternative data** | Market data is structured and uniform; alt-data is heterogeneous and evolving |
| **Tiered storage** | Hot/warm/cold — keep recent data fast, historical data cheap |
| **Graceful degradation** | If one source dies, the pipeline continues; no single point of failure |
| **Replay-ability** | Every event is logged; any state can be reconstructed from the event log |

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DATA SOURCES (Ingestion Edge)                      │
├────────────┬────────────┬──────────────┬──────────────┬─────────────────────┤
│   MT5 /    │  CCXT      │  News &      │  On-Chain &  │  Alternative        │
│   Broker   │  Exchanges │  Sentiment   │  Derivatives │  Data               │
│   Feeds    │  (Binance, │  (RSS, API,  │  (DefiLlama, │  (Google Trends,    │
│            │  Bybit)    │  Reddit,     │  Glassnode,  │  GitHub, LunarCrush │
│            │            │  Telegram)   │  Coinglass)  │  Token Unlocks)     │
├────────────┴────────────┴──────────────┴──────────────┴─────────────────────┤
│                                                                             │
│                     ┌──────────────────────────┐                            │
│                     │   INGESTION LAYER        │                            │
│                     │   (Source Adapters)       │                            │
│                     └────────────┬─────────────┘                            │
│                                  │                                          │
│                     ┌────────────▼─────────────┐                            │
│                     │   NORMALIZATION &         │                            │
│                     │   VALIDATION LAYER        │                            │
│                     └────────────┬─────────────┘                            │
│                                  │                                          │
│          ┌───────────────────────┼───────────────────────┐                  │
│          ▼                       ▼                       ▼                  │
│  ┌──────────────┐   ┌───────────────────┐   ┌──────────────────┐           │
│  │  HOT PATH    │   │   WARM PATH       │   │   COLD PATH      │           │
│  │  (Real-Time) │   │   (Near Real-Time)│   │   (Batch)        │           │
│  │              │   │                   │   │                  │           │
│  │  Redis       │   │  Redis Streams    │   │  TimescaleDB     │           │
│  │  (ticks,     │   │  (events, signals,│   │  (historical     │           │
│  │   quotes,    │   │   alt-data)       │   │   OHLCV, ticks,  │           │
│  │   book)      │   │                   │   │   aggregates)    │           │
│  └──────┬───────┘   └────────┬──────────┘   └────────┬─────────┘           │
│         │                    │                       │                      │
│         ▼                    ▼                       ▼                      │
│  ┌──────────────────────────────────────────────────────────────────┐       │
│  │                    CONSUMPTION LAYER                              │       │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │       │
│  │  │ Signal   │ │ Execution│ │ Risk     │ │ Backtest │           │       │
│  │  │ Agents   │ │ Engine   │ │ Manager  │ │ Engine   │           │       │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │       │
│  └──────────────────────────────────────────────────────────────────┘       │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────┐       │
│  │                    ANALYTICS LAYER                                │       │
│  │  ClickHouse (OLAP) + Grafana Dashboards + Reporting              │       │
│  └──────────────────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Source Adapters — Ingestion Edge

Each data source gets a dedicated adapter. Adapters are isolated, independently restartable, and expose a uniform internal interface.

### 3.1 Adapter Contract

Every adapter implements:

```python
class SourceAdapter(ABC):
    """Base contract for all data source adapters."""

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def stream(self) -> AsyncIterator[RawEvent]: ...

    @abstractmethod
    async def health(self) -> SourceHealth: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    # Rate limit awareness
    rate_limit: RateLimitConfig
    # Retry policy
    retry: RetryPolicy
```

Each adapter emits `RawEvent` objects into the ingestion bus (Redis Streams), tagged with:
- `source` — identifier (e.g., `mt5`, `binance`, `defillama`)
- `asset_class` — `forex`, `crypto`, `macro`, `sentiment`, `onchain`
- `event_type` — `tick`, `ohlcv`, `orderbook`, `news`, `funding_rate`, etc.
- `symbol` — normalized symbol (e.g., `EUR/USD`, `BTC/USDT`)
- `timestamp` — UTC, microsecond precision
- `payload` — raw data as bytes/JSON

### 3.2 Source Adapter Inventory

| Adapter | Source | Protocol | Data Produced | Frequency | Priority |
|---------|--------|----------|---------------|-----------|----------|
| `Mt5Adapter` | MT5 (FXPesa) | Python `MetaTrader5` lib | Ticks, OHLCV, DOM, calendar, account state | Real-time (tick) | P0 |
| `CcxtAdapter` | Binance, Bybit | REST + WebSocket via `ccxt` | Ticks, OHLCV, order book, trades | Real-time (WS) | P0 |
| `FundingRateAdapter` | Binance/Bybit Futures | REST (`fapi/v1/fundingRate`) | Funding rates, open interest | Every 1 min | P1 |
| `CoinGeckoAdapter` | CoinGecko Demo API | REST | Market overview, prices, market cap | Every 5 min | P1 |
| `DefiLlamaAdapter` | DefiLlama | REST (`api.llama.fi`) | TVL, stablecoin supply, yields, DEX volume | Every 5 min | P1 |
| `CoinglassAdapter` | Coinglass | REST (scrape/API) | Liquidation maps, OI, long/short ratio | Every 1 min | P1 |
| `EconomicCalendarAdapter` | MQL5 Calendar (MT5) | MQL5 native | Economic events, impact levels | Daily fetch + intraday updates | P1 |
| `NewsRssAdapter` | CoinDesk, Reuters, BBC, FT | RSS parsing | Headlines, summaries | Every 15 min | P2 |
| `CryptoCompareNewsAdapter` | CryptoCompare | REST | Aggregated crypto news | Every 15 min | P2 |
| `RedditSentimentAdapter` | Reddit (PRAW) | Reddit API | Post/comment sentiment scores | Every 15 min | P2 |
| `TelegramMonitorAdapter` | Telegram (Telethon) | MTProto | Alpha group messages, sentiment | Real-time (event) | P2 |
| `GoogleTrendsAdapter` | Google Trends (`pytrends`) | REST | Search interest indices | Every 6 hours | P3 |
| `GitHubActivityAdapter` | GitHub API | REST | Commit frequency, contributor counts | Daily | P3 |
| `LunarCrushAdapter` | LunarCrush | REST | Social dominance, Galaxy Score | Every 15 min | P3 |
| `FearGreedAdapter` | alternative.me | REST | Fear & Greed Index | Every 1 hour | P3 |
| `TokenUnlockAdapter` | tokenunlocks.app | REST/scrape | Upcoming token unlock events | Daily | P3 |
| `GlassnodeAdapter` | Glassnode (when budget allows) | REST | Exchange flows, SOPR, MVRV, NVT | Every 5 min | P4 |
| `WhaleAlertAdapter` | Whale Alert / Arkham | REST/WebSocket | Large transaction alerts | Real-time (WS) | P4 |

### 3.3 MT5 Adapter — Deep Detail

The MT5 adapter is the most complex due to the MetaTrader5 Python library's synchronous nature and the variety of data it provides.

```
MT5 Adapter Internal Architecture:
┌─────────────────────────────────────────────┐
│              Mt5Adapter                      │
├─────────────────────────────────────────────┤
│                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │  Tick    │  │  OHLCV   │  │  DOM     │  │
│  │  Stream  │  │  Poller  │  │  Stream  │  │
│  │ (CopyTicks)│(CopyRates)│(BookGet)  │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  │
│       │              │              │        │
│       ▼              ▼              ▼        │
│  ┌─────────────────────────────────────┐    │
│  │    Internal Event Queue (asyncio)    │    │
│  └──────────────────┬──────────────────┘    │
│                     │                        │
│  ┌──────────────────▼──────────────────┐    │
│  │    MT5 Calendar Fetcher (daily)      │    │
│  └──────────────────────────────────────┘    │
│                                             │
│  ┌──────────────────────────────────────┐   │
│  │    Account State Monitor (positions,  │   │
│  │    balance, margin) — every 1s        │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

**Key implementation notes:**
- MT5 library is synchronous — wrap in `asyncio.to_thread()` for each call
- Tick data via `mt5.copy_ticks_from()` — stream in a dedicated thread
- OHLCV via `mt5.copy_rates_from_pos()` — poll on candle close events
- DOM via `mt5.market_book_get()` — subscribe with `market_book_add()`
- Calendar via `mt5.calendar_value()` — fetch once daily at 00:05 UTC
- Reconnection: detect `mt5.last_error()` and auto-reconnect with exponential backoff

### 3.4 CCXT Adapter — Deep Detail

```
CCXT Adapter Internal Architecture:
┌─────────────────────────────────────────────┐
│              CcxtAdapter                     │
├─────────────────────────────────────────────┤
│                                             │
│  ┌──────────────────────────────────────┐   │
│  │  WebSocket Manager                   │   │
│  │  - Per-exchange WS connections       │   │
│  │  - Heartbeat every 15s              │   │
│  │  - Auto-reconnect w/ backoff        │   │
│  │  - Message buffer during reconnect  │   │
│  └──────────────┬───────────────────────┘   │
│                 │                            │
│  ┌──────────────▼───────────────────────┐   │
│  │  Channel Subscriptions               │   │
│  │  - ticker:{symbol}                   │   │
│  │  - trades:{symbol}                   │   │
│  │  - orderbook:{symbol}                │   │
│  │  - OHLCV:{symbol}:{timeframe}        │   │
│  └──────────────┬───────────────────────┘   │
│                 │                            │
│  ┌──────────────▼───────────────────────┐   │
│  │  REST Fallback                       │   │
│  │  - Rate-limited polling              │   │
│  │  - Used for historical backfill      │   │
│  │  - Used when WS disconnects          │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

**Key implementation notes:**
- Use `ccxt.pro` (WebSocket-enabled) for real-time data
- Binance WS: 1024 stream limit per connection; use combined streams
- Bybit WS: 500 subscriptions per connection
- Rate limits: Binance 1200 req/min REST, Bybit 120 req/5s REST
- Historical backfill: use REST `fetchOHLCV()` with pagination, respect rate limits
- Symbol normalization: ccxt handles `BTC/USDT` → exchange-specific format

---

## 4. Normalization & Validation Layer

Raw events from adapters are heterogeneous. The normalization layer transforms them into a canonical format before storage.

### 4.1 Canonical Event Schema

```json
{
  "event_id": "uuid-v7",
  "source": "binance",
  "asset_class": "crypto",
  "event_type": "tick",
  "symbol": "BTC/USDT",
  "timestamp_utc": "2026-07-11T13:45:23.123456Z",
  "ingested_at": "2026-07-11T13:45:23.130000Z",
  "latency_ms": 6.5,
  "schema_version": 1,
  "payload": { ... },
  "metadata": {
    "adapter_version": "0.1.0",
    "checksum": "sha256:abc123..."
  }
}
```

### 4.2 Normalization Rules

| Transformation | Rule | Example |
|----------------|------|---------|
| **Timestamp** | All timestamps → UTC, microsecond precision | `1625139923123456` |
| **Symbol** | Normalize to `{BASE}/{QUOTE}` | `EURUSD` → `EUR/USD`, `BTCUSDT` → `BTC/USDT` |
| **Price** | Float64, no rounding at ingestion | `1.08532` (preserve all decimals from source) |
| **Volume** | Standardized units (base currency for crypto, lots for forex) | `0.01` lots, `1.5` BTC |
| **OHLCV** | Ensure `open ≤ high`, `low ≤ close ≤ high`, `volume ≥ 0` | Validate, flag violations |
| **Deduplication** | `event_id` (UUID v7 from source+timestamp+hash) prevents duplicates | Idempotent inserts |

### 4.3 Validation Pipeline

```
Raw Event → Schema Validation → Anomaly Detection → Enrichment → Canonical Event
                │                      │                  │
                ▼                      ▼                  ▼
          Reject & Log          Flag & Tag           Add derived fields
          (malformed)           (outlier, gap)       (spread, mid-price, session)
```

**Validation checks:**
1. **Schema compliance** — required fields present, correct types
2. **Timestamp sanity** — not in the future, not older than retention window
3. **Price sanity** — not zero, not negative, within ±20% of last known price (configurable)
4. **Volume sanity** — not negative
5. **Gap detection** — if tick stream has >5s gap, flag and alert
6. **Duplicate detection** — check `event_id` against recent ID set (bloom filter)

**Enrichment (added during normalization):**
- `spread` = ask - bid (for tick data)
- `mid_price` = (bid + ask) / 2
- `session` = `asian` | `london` | `new_york` | `overlap` (derived from timestamp)
- `is_news_window` = true if within ±30 min of a high-impact calendar event
- `vwap` = rolling volume-weighted average price (from tick data)

---

## 5. The Three Data Paths

Data flows through three paths based on latency requirements.

### 5.1 Hot Path — Real-Time (Sub-Millisecond)

**Purpose:** Current market state for live trading decisions.  
**Technology:** Redis (in-memory).  
**Latency target:** <1ms read, <5ms write.

```
Source Adapter → Normalization → Redis Key-Value / Pub/Sub → Trading Agents
```

**What lives in the Hot Path:**

| Key Pattern | Data | TTL | Update Frequency |
|-------------|------|-----|------------------|
| `tick:{symbol}` | Latest bid/ask/last/volume | 60s (auto-expire) | Every tick |
| `book:{symbol}` | Order book snapshot (top 20 levels) | 10s | Every book update |
| `ohlcv:{symbol}:{tf}` | Current (unclosed) candle per timeframe | Until close | Every tick |
| `signal:{agent_id}:{symbol}` | Latest signal from each agent | 5 min | On signal change |
| `position:{account_id}:{symbol}` | Current open positions | Until close | On change |
| `account:{account_id}` | Balance, equity, margin | 1s | Every 1s |
| `spread:{symbol}` | Current and average spread | 5 min | Every tick |
| `session_state` | Current session, time to next | 1 min | Every min |
| `calendar:today` | Today's economic events | 24h | Daily at 00:05 |
| `fear_greed` | Current Fear & Greed Index | 1h | Every 1h |
| `funding:{symbol}` | Current funding rate | 1 min | Every 1 min |

**Redis Pub/Sub channels:**

| Channel | Published By | Subscribed By |
|---------|-------------|---------------|
| `tick:{symbol}` | Ingestion layer | All active signal agents |
| `signal:{symbol}` | Signal agents | Execution engine, risk manager |
| `order:{account}` | Execution engine | Risk manager, portfolio manager |
| `alert:system` | Any component | Monitor agent, notification service |
| `regime` | Meta agent | All signal agents |

### 5.2 Warm Path — Event Stream (Seconds to Minutes)

**Purpose:** Ordered, durable event log for event-driven processing and signal generation.  
**Technology:** Redis Streams (Phase 1-3), Kafka (Phase 4+).  
**Latency target:** <100ms end-to-end.

```
Source Adapter → Normalization → Redis Stream (per topic) → Consumer Groups → Agents
```

**Stream topics:**

| Stream Key | Content | Consumer Groups | Retention |
|------------|---------|-----------------|-----------|
| `stream:ticks:{symbol}` | All ticks | signal-agents, risk-monitor | 1 hour (trim by maxlen) |
| `stream:ohlcv:{symbol}:{tf}` | Closed candles | signal-agents, backtest | 7 days |
| `stream:trades:{symbol}` | Exchange trade prints | delta-analyzer, volume-agent | 1 hour |
| `stream:news` | Parsed news headlines | sentiment-agent, news-filter | 24 hours |
| `stream:sentiment` | Social sentiment scores | sentiment-agent | 24 hours |
| `stream:onchain` | On-chain events (flows, whale txns) | onchain-agent | 24 hours |
| `stream:signals` | All generated signals | execution-engine, risk-manager | 7 days |
| `stream:orders` | Order lifecycle events | portfolio-manager, monitor | 30 days |
| `stream:system` | System events (errors, health, config) | monitor-agent | 7 days |

**Consumer group design:**
- Each agent type gets its own consumer group on relevant streams
- Consumer groups ensure exactly-once processing per agent type
- Failed messages are retried 3 times, then dead-lettered to `stream:dlq`
- Lag monitoring: alert if any consumer group falls behind by >1000 messages

### 5.3 Cold Path — Persistent Storage (Minutes to Forever)

**Purpose:** Historical data for backtesting, analytics, reporting, and ML training.  
**Technology:** TimescaleDB (time-series OLTP), ClickHouse (analytics OLAP).  
**Latency target:** <100ms for indexed queries, seconds for analytical scans.

```
Redis Stream → TimescaleDB Writer → TimescaleDB (hypertables)
                                    → ClickHouse (materialized views)
```

**TimescaleDB schema — Core tables:**

```sql
-- Market data: OHLCV candles (continuous aggregate from ticks)
CREATE TABLE market_data (
    time         TIMESTAMPTZ NOT NULL,
    symbol       TEXT NOT NULL,
    timeframe    TEXT NOT NULL,       -- '1m', '5m', '15m', '1h', '4h', '1d'
    open         DOUBLE PRECISION NOT NULL,
    high         DOUBLE PRECISION NOT NULL,
    low          DOUBLE PRECISION NOT NULL,
    close        DOUBLE PRECISION NOT NULL,
    volume       DOUBLE PRECISION NOT NULL,
    tick_count   INTEGER,             -- number of ticks in candle (forex)
    vwap         DOUBLE PRECISION,
    spread_avg   DOUBLE PRECISION
);
SELECT create_hypertable('market_data', 'time');

-- Tick data (raw, highest granularity)
CREATE TABLE ticks (
    time         TIMESTAMPTZ NOT NULL,
    symbol       TEXT NOT NULL,
    bid          DOUBLE PRECISION NOT NULL,
    ask          DOUBLE PRECISION NOT NULL,
    last         DOUBLE PRECISION,
    bid_volume   DOUBLE PRECISION,
    ask_volume   DOUBLE PRECISION,
    flags        INTEGER              -- tick flags from MT5
);
SELECT create_hypertable('ticks', 'time');

-- Trade executions
CREATE TABLE trades (
    trade_id     UUID PRIMARY KEY,
    time         TIMESTAMPTZ NOT NULL,
    symbol       TEXT NOT NULL,
    direction    TEXT NOT NULL,        -- 'BUY' | 'SELL'
    entry_price  DOUBLE PRECISION,
    exit_price   DOUBLE PRECISION,
    size         DOUBLE PRECISION,
    pnl          DOUBLE PRECISION,
    fees         DOUBLE PRECISION,
    strategy_id  TEXT NOT NULL,
    agent_id     TEXT NOT NULL,
    signal_id    UUID REFERENCES signals(signal_id),
    status       TEXT NOT NULL         -- 'OPEN' | 'CLOSED' | 'CANCELLED'
);
SELECT create_hypertable('trades', 'time');

-- Signals generated by agents
CREATE TABLE signals (
    signal_id    UUID PRIMARY KEY,
    time         TIMESTAMPTZ NOT NULL,
    symbol       TEXT NOT NULL,
    agent_id     TEXT NOT NULL,
    signal_type  TEXT NOT NULL,        -- 'BUY' | 'SELL' | 'HOLD'
    confidence   DOUBLE PRECISION,     -- 0.0 to 1.0
    timeframe    TEXT,
    features     JSONB,               -- feature values that triggered signal
    metadata     JSONB
);
SELECT create_hypertable('signals', 'time');

-- News and sentiment events
CREATE TABLE news_events (
    event_id     UUID PRIMARY KEY,
    time         TIMESTAMPTZ NOT NULL,
    source       TEXT NOT NULL,
    headline     TEXT NOT NULL,
    summary      TEXT,
    symbols      TEXT[],              -- related symbols
    sentiment    DOUBLE PRECISION,    -- -1.0 to +1.0
    impact       TEXT,                -- 'low' | 'medium' | 'high'
    metadata     JSONB
);
SELECT create_hypertable('news_events', 'time');

-- On-chain events
CREATE TABLE onchain_events (
    event_id     UUID PRIMARY KEY,
    time         TIMESTAMPTZ NOT NULL,
    chain        TEXT NOT NULL,        -- 'bitcoin', 'ethereum', etc.
    event_type   TEXT NOT NULL,        -- 'exchange_flow', 'whale_tx', 'tvl_change'
    metric       TEXT NOT NULL,
    value        DOUBLE PRECISION,
    metadata     JSONB
);
SELECT create_hypertable('onchain_events', 'time');

-- Alternative data snapshots
CREATE TABLE alt_data_snapshots (
    snapshot_id  UUID PRIMARY KEY,
    time         TIMESTAMPTZ NOT NULL,
    source       TEXT NOT NULL,        -- 'google_trends', 'github', 'lunarcrush', 'coinglass'
    symbol       TEXT,
    metrics      JSONB NOT NULL        -- flexible key-value metrics
);
SELECT create_hypertable('alt_data_snapshots', 'time');

-- System events (audit trail)
CREATE TABLE system_events (
    event_id     UUID PRIMARY KEY,
    time         TIMESTAMPTZ NOT NULL,
    component    TEXT NOT NULL,        -- 'ingestion', 'signal', 'execution', 'risk'
    event_type   TEXT NOT NULL,        -- 'error', 'warning', 'info', 'config_change'
    message      TEXT NOT NULL,
    metadata     JSONB
);
SELECT create_hypertable('system_events', 'time');
```

**TimescaleDB continuous aggregates:**

```sql
-- Auto-compute 1m OHLCV from tick data
CREATE MATERIALIZED VIEW candle_1m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', time) AS time,
    symbol,
    first(bid, time) AS open,
    max(bid) AS high,
    min(bid) AS low,
    last(bid, time) AS close,
    sum(bid_volume + ask_volume) AS volume,
    count(*) AS tick_count,
    avg((bid + ask) / 2) AS vwap,
    avg(ask - bid) AS spread_avg
FROM ticks
GROUP BY time_bucket('1 minute', time), symbol;

-- Auto-compute higher timeframes from 1m candles
-- (5m, 15m, 1h, 4h, 1d — each built from the previous)
-- Uses refresh policy to update incrementally
SELECT add_continuous_aggregate_policy('candle_1m',
    start_offset => INTERVAL '5 minutes',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute');
```

**TimescaleDB compression:**

```sql
-- Compress chunks older than 7 days (ticks) / 30 days (candles)
ALTER TABLE ticks SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol',
    timescaledb.compress_orderby = 'time DESC'
);
SELECT add_compression_policy('ticks', INTERVAL '7 days');

ALTER TABLE market_data SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol, timeframe',
    timescaledb.compress_orderby = 'time DESC'
);
SELECT add_compression_policy('market_data', INTERVAL '30 days');
```

**TimescaleDB retention:**

```sql
-- Raw ticks: keep 90 days
SELECT add_retention_policy('ticks', INTERVAL '90 days');

-- 1m candles: keep 2 years
-- (handled by continuous aggregate refresh policy + manual archival)

-- System events: keep 90 days
SELECT add_retention_policy('system_events', INTERVAL '90 days');
```

**ClickHouse — Analytics layer (Phase 3+):**

ClickHouse serves the OLAP workload — backtesting, strategy analysis, reporting.

```sql
-- Denormalized trade analytics table (star schema fact table)
CREATE TABLE analytics.fact_trades (
    trade_id     UUID,
    time         DateTime64(6),
    symbol       LowCardinality(String),
    direction    Enum8('BUY'=1, 'SELL'=2),
    entry_price  Float64,
    exit_price   Float64,
    size         Float64,
    pnl          Float64,
    fees         Float64,
    strategy_id  LowCardinality(String),
    agent_id     LowCardinality(String),
    session      LowCardinality(String),
    regime       LowCardinality(String),
    -- Pre-joined dimension fields for fast analytics
    pair_base    LowCardinality(String),
    pair_quote   LowCardinality(String),
    asset_class  LowCardinality(String)
) ENGINE = MergeTree()
ORDER BY (symbol, time)
PARTITION BY toYYYYMM(time);
```

**Data flow to ClickHouse:**
- TimescaleDB → CDC (logical replication) → Kafka connector → ClickHouse
- OR: Application-level dual-write for critical tables
- Batch sync nightly for analytical tables that don't need real-time freshness

---

## 6. Indexes & Query Optimization

### 6.1 TimescaleDB Indexes

```sql
-- Market data: most common query = "get N candles for symbol X, timeframe Y"
CREATE INDEX idx_market_data_symbol_tf_time
    ON market_data (symbol, timeframe, time DESC);

-- Ticks: most common query = "get recent ticks for symbol X"
CREATE INDEX idx_ticks_symbol_time
    ON ticks (symbol, time DESC);

-- Trades: query by strategy, by symbol, by time
CREATE INDEX idx_trades_strategy_time
    ON trades (strategy_id, time DESC);
CREATE INDEX idx_trades_symbol_time
    ON trades (symbol, time DESC);

-- Signals: query by agent, by symbol
CREATE INDEX idx_signals_agent_time
    ON signals (agent_id, time DESC);
CREATE INDEX idx_signals_symbol_time
    ON signals (symbol, time DESC);

-- News: query by time, filter by symbols
CREATE INDEX idx_news_time
    ON news_events (time DESC);
CREATE INDEX idx_news_symbols
    ON news_events USING GIN (symbols);

-- On-chain: query by chain + event type + time
CREATE INDEX idx_onchain_chain_type_time
    ON onchain_events (chain, event_type, time DESC);
```

### 6.2 Query Patterns & Expected Performance

| Query | Target Table | Index Used | Expected Latency |
|-------|-------------|------------|-----------------|
| Last 500 candles for BTC/USDT 1h | `market_data` | `idx_market_data_symbol_tf_time` | <5ms |
| All ticks for EUR/USD today | `ticks` | `idx_ticks_symbol_time` | <50ms |
| P&L by strategy last 30 days | `trades` | `idx_trades_strategy_time` | <100ms |
| Signals from agent X this week | `signals` | `idx_signals_agent_time` | <20ms |
| News mentioning BTC in last 24h | `news_events` | `idx_news_time` + GIN | <30ms |
| Backtest: all EUR/USD 1h candles 2020-2026 | `market_data` | sequential scan (compressed) | <2s |

---

## 7. Data Flow — End-to-End Scenarios

### 7.1 Scenario: EUR/USD Tick → Trading Signal → Order

```
1. MT5 receives tick: EUR/USD bid=1.08532 ask=1.08545
2. Mt5Adapter emits RawEvent to Redis Stream `stream:ticks:EUR/USD`
3. Normalization: validate, enrich (spread=0.00013, session=london, mid=1.085385)
4. Write to Redis HOT: `tick:EUR/USD` = {bid, ask, spread, mid, time}
5. Publish to Redis Pub/Sub channel `tick:EUR/USD`
6. TimescaleDB writer consumes from stream → inserts into `ticks` hypertable

7. Signal Agent (MA Crossover) receives Pub/Sub notification
8. Agent reads HOT: `ohlcv:EUR/USD:1h` (current unclosed candle)
9. Agent reads COLD: last 200 × 1h candles from TimescaleDB (cached in process)
10. Agent computes: fast MA (20) > slow MA (50) → BUY signal
11. Agent publishes signal to Redis `signal:ma_crossover:EUR/USD`
12. Agent writes to Redis Stream `stream:signals`

13. Risk Manager consumes from `stream:signals`
14. Risk Manager checks HOT: `account:main` (balance, margin, open positions)
15. Risk Manager checks limits: max position size, max drawdown, correlation
16. Risk Manager approves → publishes to Redis Stream `stream:orders`

17. Execution Engine consumes from `stream:orders`
18. Execution Engine sends order to MT5 via MetaTrader5 Python API
19. Execution Engine receives fill confirmation
20. Execution Engine updates HOT: `position:main:EUR/USD`
21. Execution Engine writes to Redis Stream `stream:orders` (fill event)
22. TimescaleDB writer: inserts into `trades` table
23. Portfolio Manager updates position state
24. Monitor Agent checks for anomalies
```

**Total latency budget (tick → order sent):**
| Step | Latency |
|------|---------|
| MT5 tick → adapter | <1ms |
| Normalization | <1ms |
| Redis write + pub | <1ms |
| Signal computation | <10ms |
| Risk check | <5ms |
| Order routing | <5ms |
| **Total** | **<25ms** |

### 7.2 Scenario: On-Chain Event → Sentiment Signal

```
1. DefiLlama adapter polls: stablecoin supply on Ethereum dropped 2% in 1h
2. Adapter emits RawEvent to Redis Stream `stream:onchain`
3. Normalization: validate, enrich (classify as `stablecoin_outflow`, severity=medium)
4. Write to TimescaleDB `onchain_events`
5. Write to Redis HOT: `onchain:stablecoin:ethereum`

6. On-Chain Agent (consumer of `stream:onchain`) processes event
7. Agent reads related context: funding rates from HOT, recent price action from COLD
8. Agent generates signal: "stablecoin outflow + negative funding + price support = BUY"
9. Agent publishes signal → enters same signal → execution pipeline as above
```

### 7.3 Scenario: News Event → Trading Pause

```
1. Economic Calendar adapter fetches: NFP release at 13:30 GMT (high impact)
2. Calendar written to Redis HOT: `calendar:today`
3. At 13:00 GMT: Meta Agent detects "high-impact event in 30 minutes"
4. Meta Agent publishes to `alert:system`: "pause_trading:EUR/USD,USD/JPY"
5. Risk Manager receives alert → sets circuit breaker for affected pairs
6. Signal Agents for affected pairs → stop generating signals
7. At 14:00 GMT (30 min after event): Meta Agent lifts pause
8. Circuit breaker removed → normal operation resumes
```

---

## 8. Consumer Architecture — Agent Data Access Patterns

### 8.1 Agent Data Access Matrix

| Agent Type | Hot (Redis) | Warm (Streams) | Cold (TimescaleDB) | Typical Queries |
|------------|-------------|----------------|---------------------|-----------------|
| **Signal Agent** | Current tick, current candle, indicators | Closed candles, tick history | Historical candles for backtest context | `GET tick:EUR/USD`, `XRANGE stream:ohlcv:EUR/USD:1h - + COUNT 200` |
| **Execution Agent** | Current price, positions, account state | Order events | Historical fills | `GET position:main:EUR/USD`, `GET account:main` |
| **Risk Manager** | All positions, account state, spreads | Signal events, order events | Historical drawdown, correlation data | `GET account:main`, `MGET position:*` |
| **Sentiment Agent** | Fear & Greed, latest news headline | News stream, social stream | Historical sentiment scores | `GET fear_greed`, `XRANGE stream:news - + COUNT 50` |
| **On-Chain Agent** | Latest funding rate, stablecoin supply | On-chain event stream | Historical on-chain metrics | `GET funding:BTC/USDT`, `GET onchain:stablecoin:*` |
| **Backtest Engine** | None (operates offline) | None | Full historical data (all tables) | `SELECT * FROM market_data WHERE symbol='EUR/USD' AND timeframe='1h'` |
| **Meta Agent** | System health, regime state | System events | Strategy performance history | `GET session_state`, `XRANGE stream:system - + COUNT 100` |
| **Monitor** | All alerts | System events | Historical errors | `SUBSCRIBE alert:system` |

### 8.2 Caching Strategy

```
L0: Process memory     — current tick, current candle, agent state     (< 1μs)
L1: Redis              — market state, positions, signals              (< 1ms)
L2: TimescaleDB        — historical data, compressed                   (< 100ms)
L3: ClickHouse         — analytical queries, backtesting               (< 5s)
```

**Cache invalidation:**
- L0 (process): invalidated by Redis Pub/Sub notifications
- L1 (Redis): TTL-based auto-expiry for market data; explicit invalidation for positions
- L2 (TimescaleDB): append-only for time-series; updates only for trade status
- L3 (ClickHouse): refreshed from TimescaleDB CDC; eventual consistency acceptable

---

## 9. Data Lifecycle & Retention

| Data Type | Hot (Redis) | Warm (Streams) | Warm (TimescaleDB uncompressed) | Cold (TimescaleDB compressed) | Archive |
|-----------|-------------|----------------|---------------------------------|-------------------------------|---------|
| Ticks | 60s | 1 hour | 7 days | 90 days | Delete |
| 1m candles | Until next candle | 7 days | 30 days | 2 years | Compress forever |
| 1h+ candles | Until next candle | 30 days | 1 year | 10 years | Compress forever |
| Daily candles | Current | 90 days | Forever | — | — |
| Signals | 5 min | 7 days | 90 days | 1 year | Compress forever |
| Orders | Current | 30 days | 1 year | 7 years (regulatory) | Compress forever |
| News | 1 hour | 24 hours | 90 days | 1 year | Delete |
| On-chain | 1 hour | 24 hours | 90 days | 2 years | Delete |
| Alt-data | 1 hour | 24 hours | 90 days | 1 year | Delete |
| System events | — | 7 days | 90 days | 1 year | Delete |

**Storage estimates (Phase 1 — 3 pairs, 1 year):**

| Data Type | Rows/Day | Rows/Year | Compressed Size |
|-----------|----------|-----------|-----------------|
| Ticks (3 pairs) | ~500K | ~180M | ~5 GB |
| 1m candles | ~4,320 | ~1.6M | ~200 MB |
| 1h candles | ~72 | ~26K | ~5 MB |
| Signals | ~100 | ~36K | ~10 MB |
| Orders | ~10 | ~3.6K | ~2 MB |
| **Total** | | | **~5.5 GB** |

**Storage estimates (Phase 3 — 28 pairs, 5 years):**

| Data Type | Compressed Size |
|-----------|-----------------|
| Ticks | ~200 GB |
| Candles (all TFs) | ~5 GB |
| Signals + Orders | ~500 MB |
| News + Alt-data | ~10 GB |
| **Total** | **~220 GB** |

This fits comfortably on a single server with a 500GB SSD through Phase 3.

---

## 10. Phase-Gated Implementation Plan

### Phase 1: Foundation ($0 infrastructure, $7 capital)

**Goal:** Working data pipeline for 3 forex pairs + BTC/USDT.

| Component | Implementation | Effort |
|-----------|---------------|--------|
| MT5 Adapter | Python script using `MetaTrader5` lib | 1 day |
| CCXT Adapter | `ccxt.pro` WebSocket for Binance | 1 day |
| Redis Hot Store | Local Redis instance, key-value + Pub/Sub | 30 min |
| TimescaleDB | Docker container, hypertable setup | 2 hours |
| Basic Normalization | Python module: symbol normalization, validation | 1 day |
| Stream Writer | Redis Stream → TimescaleDB batch writer | 1 day |
| Economic Calendar | MQL5 calendar fetcher → Redis | 2 hours |
| DefiLlama Adapter | REST poller for TVL, stablecoins | 2 hours |
| Funding Rate Adapter | Binance Futures API poller | 1 hour |
| **Total Phase 1** | | **~5 days** |

**Phase 1 stack:** Python + Redis + TimescaleDB (Docker) + SQLite (config/state)

### Phase 2: Enrichment (~$100 capital, ~$10/mo infra)

| Component | Implementation | Effort |
|-----------|---------------|--------|
| News RSS Adapter | Feedparser + sentiment scoring (VADER) | 1 day |
| Reddit Sentiment | PRAW + VADER for r/cryptocurrency | 1 day |
| Google Trends | pytrends integration | 2 hours |
| Coinglass Adapter | Liquidation/OI scraper | 1 day |
| Fear & Greed | alternative.me API | 1 hour |
| Continuous Aggregates | TimescaleDB 1m→5m→15m→1h→4h→1d | 2 hours |
| Compression Policies | TimescaleDB native compression | 30 min |
| Telegram Alerts | Alert publisher for trade events | 2 hours |
| **Total Phase 2** | | **~4 days** |

### Phase 3: Professional (~$1K capital, ~$30/mo infra)

| Component | Implementation | Effort |
|-----------|---------------|--------|
| ClickHouse Analytics | Deploy ClickHouse, ETL from TimescaleDB | 2 days |
| Star Schema | fact_trades + dimension tables in ClickHouse | 1 day |
| GitHub Activity | API integration for dev metrics | 2 hours |
| LunarCrush | Social dominance API | 2 hours |
| Token Unlocks | Calendar integration | 2 hours |
| Glassnode (if budget) | Exchange flow metrics | 1 day |
| Backtest Data Access | Query optimization for historical scans | 1 day |
| CDC Pipeline | TimescaleDB → Kafka → ClickHouse | 2 days |
| Grafana Dashboards | Data pipeline monitoring | 1 day |
| **Total Phase 3** | | **~9 days** |

### Phase 4: Institutional (~$10K+ capital, ~$200/mo infra)

| Component | Implementation | Effort |
|-----------|---------------|--------|
| Kafka Event Bus | Replace Redis Streams for durability | 3 days |
| Microservices | Each adapter as independent service | 1 week |
| Nansen Integration | Smart money wallet tracking | 2 days |
| WebSocket Multiplexing | Connection pool for 50+ symbols | 2 days |
| Data Warehouse ETL | dbt models for analytical layer | 1 week |
| ML Feature Store | Pre-computed features for model training | 1 week |
| Data Quality Monitoring | Automated anomaly detection on ingestion | 3 days |
| Multi-Broker Data | Aggregate feeds from multiple brokers | 1 week |
| **Total Phase 4** | | **~5 weeks** |

---

## 11. Technology Stack Summary

| Layer | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|-------|---------|---------|---------|---------|
| **Hot Store** | Redis | Redis | Redis | Redis Cluster |
| **Event Bus** | Redis Streams | Redis Streams | Redis Streams | Kafka + NATS |
| **Time-Series DB** | TimescaleDB | TimescaleDB | TimescaleDB | TimescaleDB |
| **Analytics DB** | — | — | ClickHouse | ClickHouse |
| **Config Store** | SQLite | SQLite | PostgreSQL | PostgreSQL |
| **Cache** | In-process dict | Redis | Redis | Redis Cluster |
| **Monitoring** | print() + Telegram | Telegram + basic | Prometheus + Grafana | Full observability |
| **Deployment** | Local | Docker Compose | Docker Compose | Kubernetes |
| **Language** | Python | Python | Python + SQL | Python + Rust + Go |

---

## 12. Failure Modes & Recovery

| Failure | Detection | Impact | Recovery |
|---------|-----------|--------|----------|
| MT5 disconnect | `mt5.last_error()` ≠ 0 | No forex data | Auto-reconnect (3 retries, exponential backoff); alert after 3 failures |
| Binance WS drops | Heartbeat timeout | No crypto ticks | ccxt auto-reconnect; REST fallback polling; alert |
| Redis down | Connection refused | No hot data | Agents degrade to direct DB reads; alert; auto-restart Redis |
| TimescaleDB down | Connection refused | No historical data | Agents continue on hot data only; queue writes in memory; alert |
| Source API rate limited | HTTP 429 | Staggered data | Exponential backoff; reduce poll frequency; use cached data |
| Data gap detected | Gap detector in normalization | Missing candles | Backfill from REST API (OHLCV) or mark gap in DB |
| Stale data | Timestamp age check | Outdated signals | Alert if tick age > 5s; switch to REST fallback |
| Disk full | OS-level monitoring | Pipeline halt | Retention policies should prevent this; alert at 80% usage |
| Network partition | Health check failures | Split brain | Each adapter operates independently; reconciliation on reconnect |

**Circuit breakers:**
- If any critical source (MT5, Binance) is down for >5 minutes → halt all trading
- If Redis is down → halt execution (signals can still be generated from DB)
- If TimescaleDB is down → continue trading but disable backtesting
- If disk >90% → stop ingesting ticks (keep candles + signals only)

---

## 13. Key Design Decisions & Trade-offs

| Decision | Choice | Rationale | Trade-off |
|----------|--------|-----------|-----------|
| Redis Streams over Kafka (Phase 1-3) | Redis | Simpler ops, lower resource usage, sufficient throughput | No durability guarantees; can't replay across restarts |
| TimescaleDB over InfluxDB | TimescaleDB | SQL-compatible, JOINs with trades table, continuous aggregates | Slightly higher memory usage than InfluxDB for pure metrics |
| Single Redis instance over Cluster | Single | $7 account doesn't need HA | Single point of failure; risk acceptable at this scale |
| Python over Rust for adapters | Python | Faster development, ccxt/MT5 libraries available | Higher latency (~1ms overhead per event); acceptable for retail |
| Append-only ticks over upsert | Append | Simpler ingestion, no conflict resolution | Slightly more storage; acceptable with compression |
| Denormalized ClickHouse for analytics | Denormalized | Query speed for backtesting | Update complexity; acceptable because analytics is read-heavy |

---

## 14. Security & Access Control

| Concern | Mitigation |
|---------|-----------|
| API keys in source adapters | Environment variables only; never in code or logs; rotate quarterly |
| Database credentials | Docker secrets or environment variables; no plaintext config files |
| Redis access | Bind to localhost only (Phase 1-3); require auth for remote access |
| Trade data at rest | Disk encryption (LUKS/BitLocker) on the server |
| Network exposure | No public ports; all services on internal Docker network |
| Audit trail | All orders and signals logged to TimescaleDB with timestamps; immutable |
| Backup | Daily pg_dump of TimescaleDB to encrypted off-site storage |

---

## 15. Monitoring & Observability

### 15.1 Data Pipeline Health Metrics

| Metric | Source | Alert Threshold |
|--------|--------|-----------------|
| Tick ingestion latency (p99) | Ingestion layer | >100ms |
| Stream consumer lag (messages) | Redis Streams | >1000 messages |
| Source adapter health | Each adapter | Any adapter unhealthy for >60s |
| Data gap count (per hour) | Normalization | >5 gaps/hour |
| TimescaleDB write throughput | Database metrics | <10 writes/sec (expected 100+) |
| Redis memory usage | Redis INFO | >80% of maxmemory |
| Disk usage | OS metrics | >80% |
| Error rate (per component) | Application logs | >10 errors/min |
| Stale data age (per symbol) | Ingestion layer | >5s for any active symbol |

### 15.2 Grafana Dashboard Layout

```
┌─────────────────────────────────────────────────────┐
│  DATA PIPELINE DASHBOARD                             │
├────────────────┬────────────────┬───────────────────┤
│  Ingestion     │  Storage       │  Consumers        │
│  Rate          │  Size          │  Lag              │
│  [graph]       │  [gauge]       │  [graph]          │
├────────────────┴────────────────┴───────────────────┤
│  Source Adapter Health                               │
│  MT5: 🟢  Binance: 🟢  DefiLlama: 🟢  News: 🟢    │
├─────────────────────────────────────────────────────┤
│  Recent Errors                                       │
│  [table: time, component, message, count]            │
├─────────────────────────────────────────────────────┤
│  Data Freshness (per symbol)                         │
│  EUR/USD: 0.3s  BTC/USDT: 0.1s  GBP/USD: 0.4s     │
└─────────────────────────────────────────────────────┘
```

---

## 16. Summary — Data Pipeline at a Glance

```
SOURCES                    INGESTION           STORAGE              CONSUMERS
─────────────              ──────────          ──────────           ──────────
MT5 (forex)     ─┐                            ┌→ Redis (hot)  ───→ Signal Agents
Binance (crypto) ─┤                            │                    Execution
Bybit (crypto)   ─┤→ Adapter → Normalize → ──→├→ Redis Streams ──→ Risk Manager
DefiLlama        ─┤    (per     (validate,     │   (warm)           Portfolio
Coinglass        ─┤    source)  enrich)        │                    Meta Agent
RSS News         ─┤                            ├→ TimescaleDB  ───→ Backtest
Reddit           ─┤                            │   (cold)           Analytics
Google Trends    ─┤                            │
GitHub           ─┤                            └→ ClickHouse  ───→ Reports
LunarCrush       ─┘                                (analytics)     ML Training
```

**Key numbers:**
- **17 source adapters** covering forex, crypto, news, sentiment, on-chain, and alternative data
- **3 data paths:** hot (<1ms), warm (<100ms), cold (<100ms indexed)
- **$0 infrastructure cost** in Phase 1 (run locally with Docker)
- **<25ms tick-to-order latency** for the critical trading path
- **~5.5 GB storage** for 3 pairs × 1 year of tick data
- **Graceful degradation** — no single source failure halts the system

---

*This architecture is designed to be built incrementally. Phase 1 delivers a working trading data pipeline in under a week. Each subsequent phase adds capability without rewriting the foundation.*

*Next: `architecture_execution.md` — Order routing, execution algorithms, and broker integration.*
