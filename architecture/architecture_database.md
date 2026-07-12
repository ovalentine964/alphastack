# Alpha Stack — Database Architecture

> **Version:** 1.0 · **Date:** 2026-07-11 · **Author:** Architecture Team
> **Source Research:** [`research/research_data_sources.md`](../research/research_data_sources.md), [`research/research_02_tech_stack_architecture.md`](../research/research_02_tech_stack_architecture.md) — Data sources and tech stack research — database design
> **Status:** Architecture Complete

---

**Author:** Database Architect
**Date:** 2026-07-11
**Status:** Architecture Design — Pre-Implementation
**Dependencies:** `architecture_data.md`, `architecture_broker.md`, `architecture_multi_agent.md`, `research_scalability.md`, `research_curriculum_database.md`

---

## Table of Contents

1. [Design Principles](#1-design-principles)
2. [Technology Stack](#2-technology-stack)
3. [TimescaleDB Schema — Market Data](#3-timescaledb-schema--market-data)
4. [PostgreSQL Schema — Trades, Positions, Orders](#4-postgresql-schema--trades-positions-orders)
5. [Redis Schema — Real-Time State](#5-redis-schema--real-time-state)
6. [Trade Journal Schema](#6-trade-journal-schema)
7. [User Accounts & Broker Connections](#7-user-accounts--broker-connections)
8. [Agent Memory Schema](#8-agent-memory-schema)
9. [Migration Strategy](#9-migration-strategy)
10. [Backup & Recovery](#10-backup--recovery)
11. [Data Retention Policies](#11-data-retention-policies)
12. [Query Optimization](#12-query-optimization)
13. [Storage Estimates & Scaling](#13-storage-estimates--scaling)
14. [Implementation Roadmap](#14-implementation-roadmap)

---

## 1. Design Principles

| Principle | Rationale |
|-----------|-----------|
| **Single source of truth** | One canonical table per entity; consumers read, never duplicate |
| **ACID for money, eventual for analytics** | Orders/positions use SERIALIZABLE isolation; dashboards tolerate stale reads |
| **Time-series native** | Market data lives in hypertables; automatic partitioning by time |
| **Schema-on-write for structured data, JSONB for evolving data** | Signals/orders are rigid; strategy configs/alt-data are fluid |
| **Tiered storage** | Hot (Redis) → Warm (TimescaleDB uncompressed) → Cold (compressed) → Archive |
| **Audit everything** | Every order, signal, and state change is an immutable append-only record |
| **Phase-gated complexity** | Start with PostgreSQL + Redis; add TimescaleDB/ClickHouse as data volume justifies |
| **Replay-ability** | Event sourcing for orders/signals; any state reconstructable from event log |

---

## 2. Technology Stack

| Component | Phase 1 ($7) | Phase 2 ($100) | Phase 3 ($1K) | Phase 4 ($10K+) |
|-----------|-------------|----------------|----------------|------------------|
| **OLTP Database** | PostgreSQL 16 | PostgreSQL 16 | PostgreSQL 16 | PostgreSQL 16 |
| **Time-Series** | PostgreSQL (native) | TimescaleDB ext. | TimescaleDB | TimescaleDB |
| **Analytics OLAP** | — | — | — | ClickHouse |
| **Cache / Hot State** | Redis 7 | Redis 7 | Redis 7 | Redis Cluster |
| **Event Bus** | Redis Pub/Sub | Redis Streams | Redis Streams | Kafka + Redis |
| **Vector DB (memory)** | SQLite FTS5 | SQLite FTS5 | pgvector ext. | pgvector + LanceDB |
| **Config Store** | SQLite | SQLite | PostgreSQL | PostgreSQL |
| **Connection Pool** | — | PgBouncer | PgBouncer | PgBouncer |
| **Schema Migrations** | Alembic | Alembic | Alembic | Alembic |
| **Backups** | pg_dump (cron) | pg_dump + WAL | pg_dump + WAL + offsite | Barman + WAL archiving |

---

## 3. TimescaleDB Schema — Market Data

### 3.1 Core Hypertables

```sql
-- ============================================================
-- TICK DATA — Raw tick stream from all sources
-- Highest granularity, shortest retention
-- ============================================================
CREATE TABLE ticks (
    time            TIMESTAMPTZ     NOT NULL,
    symbol          TEXT            NOT NULL,   -- Normalized: 'EUR/USD', 'BTC/USDT'
    source          TEXT            NOT NULL,   -- 'mt5', 'binance', 'bybit'
    bid             DOUBLE PRECISION NOT NULL,
    ask             DOUBLE PRECISION NOT NULL,
    last            DOUBLE PRECISION,
    bid_volume      DOUBLE PRECISION,
    ask_volume      DOUBLE PRECISION,
    flags           INTEGER,                    -- Source-specific tick flags
    -- Derived fields (computed during normalization)
    spread          DOUBLE PRECISION GENERATED ALWAYS AS (ask - bid) STORED,
    mid_price       DOUBLE PRECISION GENERATED ALWAYS AS ((bid + ask) / 2) STORED
);
SELECT create_hypertable('ticks', 'time',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Composite index: most queries are "ticks for symbol X in time range"
CREATE INDEX idx_ticks_symbol_time ON ticks (symbol, time DESC);

-- Compression: 95%+ reduction after 7 days
ALTER TABLE ticks SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol, source',
    timescaledb.compress_orderby = 'time DESC'
);
SELECT add_compression_policy('ticks', INTERVAL '7 days');


-- ============================================================
-- OHLCV CANDLES — Pre-computed from ticks via continuous aggregates
-- Primary data source for signal agents and backtesting
-- ============================================================
CREATE TABLE market_data (
    time            TIMESTAMPTZ     NOT NULL,
    symbol          TEXT            NOT NULL,
    timeframe       TEXT            NOT NULL,   -- '1m', '5m', '15m', '1h', '4h', '1d'
    open            DOUBLE PRECISION NOT NULL,
    high            DOUBLE PRECISION NOT NULL,
    low             DOUBLE PRECISION NOT NULL,
    close           DOUBLE PRECISION NOT NULL,
    volume          DOUBLE PRECISION NOT NULL,
    tick_count      INTEGER,                    -- Ticks aggregated into candle
    vwap            DOUBLE PRECISION,           -- Volume-weighted average price
    spread_avg      DOUBLE PRECISION,           -- Average spread during candle
    -- Constraint: OHLC validity
    CONSTRAINT ohlcv_valid CHECK (
        open <= high AND low <= close AND low <= high AND volume >= 0
    )
);
SELECT create_hypertable('market_data', 'time',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE
);

-- Primary query pattern: "last N candles for symbol X, timeframe Y"
CREATE INDEX idx_market_data_sym_tf_time ON market_data (symbol, timeframe, time DESC);

-- Compression after 30 days
ALTER TABLE market_data SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol, timeframe',
    timescaledb.compress_orderby = 'time DESC'
);
SELECT add_compression_policy('market_data', INTERVAL '30 days');


-- ============================================================
-- ORDER BOOK SNAPSHOTS — Depth of market (top N levels)
-- Used by Liquidity Agent for sweep detection
-- ============================================================
CREATE TABLE orderbook_snapshots (
    time            TIMESTAMPTZ     NOT NULL,
    symbol          TEXT            NOT NULL,
    source          TEXT            NOT NULL,
    bids            JSONB           NOT NULL,   -- [{price, volume}, ...] top 20
    asks            JSONB           NOT NULL,   -- [{price, volume}, ...] top 20
    spread          DOUBLE PRECISION,
    mid_price       DOUBLE PRECISION
);
SELECT create_hypertable('orderbook_snapshots', 'time',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

CREATE INDEX idx_orderbook_sym_time ON orderbook_snapshots (symbol, time DESC);

ALTER TABLE orderbook_snapshots SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol',
    timescaledb.compress_orderby = 'time DESC'
);
SELECT add_compression_policy('orderbook_snapshots', INTERVAL '3 days');


-- ============================================================
-- FUNDING RATES — Crypto perpetual futures
-- ============================================================
CREATE TABLE funding_rates (
    time            TIMESTAMPTZ     NOT NULL,
    symbol          TEXT            NOT NULL,   -- 'BTC/USDT', 'ETH/USDT'
    exchange        TEXT            NOT NULL,
    funding_rate    DOUBLE PRECISION NOT NULL,
    predicted_rate  DOUBLE PRECISION,
    open_interest   DOUBLE PRECISION
);
SELECT create_hypertable('funding_rates', 'time',
    chunk_time_interval => INTERVAL '30 days',
    if_not_exists => TRUE
);

CREATE INDEX idx_funding_sym_time ON funding_rates (symbol, time DESC);


-- ============================================================
-- NEWS & SENTIMENT EVENTS
-- ============================================================
CREATE TABLE news_events (
    event_id        UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    time            TIMESTAMPTZ     NOT NULL,
    source          TEXT            NOT NULL,   -- 'rss', 'cryptocompare', 'finnhub'
    headline        TEXT            NOT NULL,
    summary         TEXT,
    url             TEXT,
    symbols         TEXT[],                     -- Related symbols: {'EUR/USD', 'GBP/USD'}
    sentiment       DOUBLE PRECISION,           -- -1.0 to +1.0 (FinBERT or VADER)
    impact          TEXT,                       -- 'low', 'medium', 'high'
    category        TEXT,                       -- 'macro', 'crypto', 'earnings', 'central_bank'
    metadata        JSONB DEFAULT '{}'
);
SELECT create_hypertable('news_events', 'time',
    chunk_time_interval => INTERVAL '30 days',
    if_not_exists => TRUE
);

CREATE INDEX idx_news_time ON news_events (time DESC);
CREATE INDEX idx_news_symbols ON news_events USING GIN (symbols);
CREATE INDEX idx_news_impact ON news_events (impact, time DESC) WHERE impact = 'high';


-- ============================================================
-- ON-CHAIN EVENTS — DeFi, whale transactions, TVL changes
-- ============================================================
CREATE TABLE onchain_events (
    event_id        UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    time            TIMESTAMPTZ     NOT NULL,
    chain           TEXT            NOT NULL,   -- 'bitcoin', 'ethereum', 'solana'
    event_type      TEXT            NOT NULL,   -- 'exchange_flow', 'whale_tx', 'tvl_change', 'liquidation'
    metric          TEXT            NOT NULL,   -- 'net_flow', 'large_tx_count', 'tvl_usd'
    value           DOUBLE PRECISION NOT NULL,
    metadata        JSONB DEFAULT '{}'
);
SELECT create_hypertable('onchain_events', 'time',
    chunk_time_interval => INTERVAL '30 days',
    if_not_exists => TRUE
);

CREATE INDEX idx_onchain_chain_type_time ON onchain_events (chain, event_type, time DESC);


-- ============================================================
-- ALTERNATIVE DATA SNAPSHOTS — Google Trends, GitHub, LunarCrush, Fear&Greed
-- ============================================================
CREATE TABLE alt_data_snapshots (
    snapshot_id     UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    time            TIMESTAMPTZ     NOT NULL,
    source          TEXT            NOT NULL,   -- 'google_trends', 'github', 'lunarcrush', 'coinglass', 'fear_greed'
    symbol          TEXT,                       -- NULL for global metrics (e.g., Fear & Greed)
    metrics         JSONB           NOT NULL    -- Flexible: each source has different fields
);
SELECT create_hypertable('alt_data_snapshots', 'time',
    chunk_time_interval => INTERVAL '30 days',
    if_not_exists => TRUE
);

CREATE INDEX idx_alt_source_sym_time ON alt_data_snapshots (source, symbol, time DESC);


-- ============================================================
-- SYSTEM EVENTS — Audit trail for all infrastructure events
-- ============================================================
CREATE TABLE system_events (
    event_id        UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    time            TIMESTAMPTZ     NOT NULL,
    component       TEXT            NOT NULL,   -- 'ingestion', 'signal', 'execution', 'risk', 'broker'
    severity        TEXT            NOT NULL,   -- 'debug', 'info', 'warning', 'error', 'critical'
    event_type      TEXT            NOT NULL,   -- 'error', 'reconnect', 'config_change', 'circuit_break'
    message         TEXT            NOT NULL,
    metadata        JSONB DEFAULT '{}'
);
SELECT create_hypertable('system_events', 'time',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE
);

CREATE INDEX idx_system_severity_time ON system_events (severity, time DESC);
CREATE INDEX idx_system_component_time ON system_events (component, time DESC);


-- ============================================================
-- ECONOMIC CALENDAR — Scheduled high-impact events
-- ============================================================
CREATE TABLE economic_calendar (
    event_id        UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    time            TIMESTAMPTZ     NOT NULL,
    currency        TEXT            NOT NULL,   -- 'USD', 'EUR', 'GBP'
    event_name      TEXT            NOT NULL,   -- 'Non-Farm Payrolls', 'CPI', 'Rate Decision'
    impact          TEXT            NOT NULL,   -- 'low', 'medium', 'high'
    actual          DOUBLE PRECISION,
    forecast        DOUBLE PRECISION,
    previous        DOUBLE PRECISION,
    revised         DOUBLE PRECISION,
    source          TEXT            NOT NULL,   -- 'mt5_calendar', 'forexfactory'
    metadata        JSONB DEFAULT '{}'
);
SELECT create_hypertable('economic_calendar', 'time',
    chunk_time_interval => INTERVAL '30 days',
    if_not_exists => TRUE
);

CREATE INDEX idx_calendar_impact_time ON economic_calendar (impact, time DESC);
CREATE INDEX idx_calendar_currency ON economic_calendar (currency, time DESC);
```

### 3.2 Continuous Aggregates — Auto-Computed Candles

```sql
-- ============================================================
-- 1-MINUTE OHLCV from tick data
-- Foundation for all higher timeframes
-- ============================================================
CREATE MATERIALIZED VIEW candle_1m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', time)  AS time,
    symbol,
    first(bid, time)               AS open,
    max(bid)                       AS high,
    min(bid)                       AS low,
    last(bid, time)                AS close,
    sum(bid_volume + ask_volume)   AS volume,
    count(*)                       AS tick_count,
    avg((bid + ask) / 2)           AS vwap,
    avg(ask - bid)                 AS spread_avg
FROM ticks
GROUP BY time_bucket('1 minute', time), symbol
WITH NO DATA;

-- Refresh policy: update every minute, covering last 5 minutes
SELECT add_continuous_aggregate_policy('candle_1m',
    start_offset    => INTERVAL '5 minutes',
    end_offset      => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute'
);


-- ============================================================
-- HIGHER TIMEFRAMES — Built from market_data (1m candles)
-- 5m, 15m, 1h, 4h, 1d — each built from the previous level
-- ============================================================

-- 5-minute from 1m
CREATE MATERIALIZED VIEW candle_5m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('5 minutes', time) AS time,
    symbol,
    '5m'                           AS timeframe,
    first(open, time)              AS open,
    max(high)                      AS high,
    min(low)                       AS low,
    last(close, time)              AS close,
    sum(volume)                    AS volume,
    sum(tick_count)                AS tick_count,
    avg(vwap)                      AS vwap,
    avg(spread_avg)                AS spread_avg
FROM market_data
WHERE timeframe = '1m'
GROUP BY time_bucket('5 minutes', time), symbol
WITH NO DATA;

-- 15-minute from 5m
CREATE MATERIALIZED VIEW candle_15m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('15 minutes', time) AS time,
    symbol,
    '15m'                           AS timeframe,
    first(open, time)               AS open,
    max(high)                       AS high,
    min(low)                        AS low,
    last(close, time)               AS close,
    sum(volume)                     AS volume,
    sum(tick_count)                 AS tick_count,
    avg(vwap)                       AS vwap,
    avg(spread_avg)                 AS spread_avg
FROM market_data
WHERE timeframe = '5m'
GROUP BY time_bucket('15 minutes', time), symbol
WITH NO DATA;

-- 1-hour from 15m
CREATE MATERIALIZED VIEW candle_1h
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time)     AS time,
    symbol,
    '1h'                            AS timeframe,
    first(open, time)               AS open,
    max(high)                       AS high,
    min(low)                        AS low,
    last(close, time)               AS close,
    sum(volume)                     AS volume,
    sum(tick_count)                 AS tick_count,
    avg(vwap)                       AS vwap,
    avg(spread_avg)                 AS spread_avg
FROM market_data
WHERE timeframe = '15m'
GROUP BY time_bucket('1 hour', time), symbol
WITH NO DATA;

-- 4-hour from 1h
CREATE MATERIALIZED VIEW candle_4h
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('4 hours', time)    AS time,
    symbol,
    '4h'                            AS timeframe,
    first(open, time)               AS open,
    max(high)                       AS high,
    min(low)                        AS low,
    last(close, time)               AS close,
    sum(volume)                     AS volume,
    sum(tick_count)                 AS tick_count,
    avg(vwap)                       AS vwap,
    avg(spread_avg)                 AS spread_avg
FROM market_data
WHERE timeframe = '1h'
GROUP BY time_bucket('4 hours', time), symbol
WITH NO DATA;

-- 1-day from 4h
CREATE MATERIALIZED VIEW candle_1d
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time)      AS time,
    symbol,
    '1d'                            AS timeframe,
    first(open, time)               AS open,
    max(high)                       AS high,
    min(low)                        AS low,
    last(close, time)               AS close,
    sum(volume)                     AS volume,
    sum(tick_count)                 AS tick_count,
    avg(vwap)                       AS vwap,
    avg(spread_avg)                 AS spread_avg
FROM market_data
WHERE timeframe = '4h'
GROUP BY time_bucket('1 day', time), symbol
WITH NO DATA;

-- Refresh policies for each level
SELECT add_continuous_aggregate_policy('candle_5m',
    start_offset => INTERVAL '15 minutes', end_offset => INTERVAL '5 minutes',
    schedule_interval => INTERVAL '5 minutes');
SELECT add_continuous_aggregate_policy('candle_15m',
    start_offset => INTERVAL '1 hour', end_offset => INTERVAL '15 minutes',
    schedule_interval => INTERVAL '15 minutes');
SELECT add_continuous_aggregate_policy('candle_1h',
    start_offset => INTERVAL '4 hours', end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour');
SELECT add_continuous_aggregate_policy('candle_4h',
    start_offset => INTERVAL '1 day', end_offset => INTERVAL '4 hours',
    schedule_interval => INTERVAL '4 hours');
SELECT add_continuous_aggregate_policy('candle_1d',
    start_offset => INTERVAL '3 days', end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day');
```

### 3.3 Retention Policies

```sql
-- Raw ticks: keep 90 days, then drop
SELECT add_retention_policy('ticks', INTERVAL '90 days');

-- Order book snapshots: keep 30 days
SELECT add_retention_policy('orderbook_snapshots', INTERVAL '30 days');

-- System events: keep 90 days
SELECT add_retention_policy('system_events', INTERVAL '90 days');

-- News/onchain/alt-data: keep 1 year
SELECT add_retention_policy('news_events', INTERVAL '1 year');
SELECT add_retention_policy('onchain_events', INTERVAL '1 year');
SELECT add_retention_policy('alt_data_snapshots', INTERVAL '1 year');

-- OHLCV candles: kept indefinitely (compressed after 30 days)
-- Daily candles: never compressed, never dropped

-- Funding rates: keep 2 years
SELECT add_retention_policy('funding_rates', INTERVAL '2 years');

-- Economic calendar: keep 3 years (useful for backtesting surprise impacts)
SELECT add_retention_policy('economic_calendar', INTERVAL '3 years');
```

---

## 4. PostgreSQL Schema — Trades, Positions, Orders

All transactional (money-related) tables use **standard PostgreSQL** (not TimescaleDB hypertables) to ensure full ACID guarantees with SERIALIZABLE isolation where needed.

### 4.1 Orders

```sql
-- ============================================================
-- ORDERS — The single source of truth for all order lifecycle
-- ============================================================
CREATE TYPE order_side AS ENUM ('buy', 'sell');
CREATE TYPE order_type AS ENUM ('market', 'limit', 'stop', 'stop_limit', 'trailing_stop');
CREATE TYPE order_status AS ENUM (
    'pending',          -- Created, not yet sent to broker
    'submitted',        -- Sent to broker, awaiting ack
    'open',             -- Acknowledged by broker, working
    'partially_filled', -- Some quantity filled
    'filled',           -- Fully filled
    'cancelled',        -- Cancelled by user or system
    'rejected',         -- Rejected by broker or risk engine
    'expired'           -- Time-in-force expired
);
CREATE TYPE time_in_force AS ENUM ('gtc', 'ioc', 'fok', 'day');

CREATE TABLE orders (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Order specification
    symbol              TEXT            NOT NULL,           -- Normalized: 'EUR/USD'
    side                order_side      NOT NULL,
    order_type          order_type      NOT NULL,
    quantity            NUMERIC(20, 8)  NOT NULL CHECK (quantity > 0),
    price               NUMERIC(20, 8),                     -- Limit/stop price (NULL for market)
    stop_loss           NUMERIC(20, 8),
    take_profit         NUMERIC(20, 8),
    trailing_stop_pips  NUMERIC(10, 4),
    time_in_force       time_in_force   NOT NULL DEFAULT 'gtc',

    -- Routing
    broker_id           TEXT,                               -- Which broker connection
    broker_order_id     TEXT,                               -- Broker's native order ID
    asset_class         TEXT,                               -- 'forex', 'crypto', 'cfd'

    -- Execution results
    status              order_status    NOT NULL DEFAULT 'pending',
    fill_price          NUMERIC(20, 8),                     -- Average fill price
    fill_quantity       NUMERIC(20, 8)  DEFAULT 0,
    commission          NUMERIC(20, 8)  DEFAULT 0,
    commission_currency TEXT,
    slippage_pips       NUMERIC(10, 4),                     -- Measured slippage
    spread_at_fill      NUMERIC(10, 6),                     -- Spread when filled

    -- Strategy context
    strategy_id         TEXT,                               -- Which strategy generated this
    signal_id           UUID,                               -- Link to originating signal
    proposal_id         UUID,                               -- Link to trade proposal
    confluence_score    NUMERIC(5, 2),                      -- Signal aggregator score

    -- Audit
    metadata            JSONB           DEFAULT '{}',       -- Strategy tags, reasoning
    rejection_reason    TEXT,                               -- Why rejected (if applicable)
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    submitted_at        TIMESTAMPTZ,
    filled_at           TIMESTAMPTZ,
    cancelled_at        TIMESTAMPTZ
);

-- Indexes for common query patterns
CREATE INDEX idx_orders_status ON orders (status) WHERE status IN ('pending', 'submitted', 'open', 'partially_filled');
CREATE INDEX idx_orders_symbol_time ON orders (symbol, created_at DESC);
CREATE INDEX idx_orders_strategy_time ON orders (strategy_id, created_at DESC);
CREATE INDEX idx_orders_broker ON orders (broker_id, status);
CREATE INDEX idx_orders_signal ON orders (signal_id);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_orders_updated_at
    BEFORE UPDATE ON orders
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
```

### 4.2 Trades (Completed)

```sql
-- ============================================================
-- TRADES — Completed trade records (entry + exit = one trade)
-- This is the fact table for the analytical star schema
-- ============================================================
CREATE TABLE trades (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Identity
    symbol              TEXT            NOT NULL,
    direction           order_side      NOT NULL,
    asset_class         TEXT            NOT NULL,           -- 'forex', 'crypto', 'cfd'

    -- Entry
    entry_order_id      UUID            REFERENCES orders(id),
    entry_price         NUMERIC(20, 8)  NOT NULL,
    entry_time          TIMESTAMPTZ     NOT NULL,
    entry_slippage      NUMERIC(10, 4)  DEFAULT 0,
    entry_spread        NUMERIC(10, 6),

    -- Exit
    exit_order_id       UUID            REFERENCES orders(id),
    exit_price          NUMERIC(20, 8),
    exit_time           TIMESTAMPTZ,
    exit_slippage       NUMERIC(10, 4)  DEFAULT 0,

    -- Sizing
    size                NUMERIC(20, 8)  NOT NULL,           -- Lots or coins
    size_usd            NUMERIC(20, 2),                     -- USD equivalent at entry

    -- P&L
    gross_pnl           NUMERIC(20, 8)  DEFAULT 0,          -- Before fees
    fees                NUMERIC(20, 8)  DEFAULT 0,          -- Total commissions + swap
    net_pnl             NUMERIC(20, 8)  DEFAULT 0,          -- After fees
    pnl_pct             NUMERIC(10, 4),                     -- % return on risked capital

    -- Risk metrics
    stop_loss           NUMERIC(20, 8),                     -- Initial SL
    take_profit         NUMERIC(20, 8),                     -- Initial TP
    risk_amount         NUMERIC(20, 8),                     -- $ amount risked
    risk_reward_actual  NUMERIC(10, 4),                     -- Actual R:R achieved
    max_drawdown        NUMERIC(20, 8)  DEFAULT 0,          -- Max adverse excursion
    max_profit          NUMERIC(20, 8)  DEFAULT 0,          -- Max favorable excursion

    -- Duration
    duration_seconds    INTEGER,                            -- How long the trade was open
    bars_held           INTEGER,                            -- Candles the trade spanned

    -- Strategy attribution
    strategy_id         TEXT            NOT NULL,
    agent_id            TEXT            NOT NULL,           -- Primary signal agent
    signal_id           UUID,
    confluence_score    NUMERIC(5, 2),

    -- Context
    regime              TEXT,                               -- Market regime at entry
    session             TEXT,                               -- 'asian', 'london', 'new_york', 'overlap'
    volatility_atr      NUMERIC(10, 6),                     -- ATR at entry

    -- Status
    status              TEXT            NOT NULL DEFAULT 'open',  -- 'open', 'closed', 'partial'
    close_reason        TEXT,                               -- 'tp_hit', 'sl_hit', 'manual', 'trailing', 'time_exit'

    -- Journal
    notes               TEXT,                               -- Trader's notes
    screenshot_urls     TEXT[],                             -- Chart screenshot URLs
    grade               TEXT,                               -- 'A+', 'A', 'B', 'C', 'D', 'F'

    -- Audit
    metadata            JSONB           DEFAULT '{}',
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- Analytical indexes
CREATE INDEX idx_trades_symbol_time ON trades (symbol, entry_time DESC);
CREATE INDEX idx_trades_strategy_time ON trades (strategy_id, entry_time DESC);
CREATE INDEX idx_trades_agent_time ON trades (agent_id, entry_time DESC);
CREATE INDEX idx_trades_status ON trades (status) WHERE status = 'open';
CREATE INDEX idx_trades_pnl ON trades (net_pnl, entry_time DESC);
CREATE INDEX idx_trades_session ON trades (session, entry_time DESC);

-- Materialized view for strategy performance (refreshed periodically)
CREATE MATERIALIZED VIEW v_strategy_performance AS
SELECT
    strategy_id,
    COUNT(*)                                    AS total_trades,
    COUNT(*) FILTER (WHERE net_pnl > 0)         AS winning_trades,
    COUNT(*) FILTER (WHERE net_pnl < 0)         AS losing_trades,
    ROUND(AVG(net_pnl)::numeric, 2)             AS avg_pnl,
    ROUND(AVG(net_pnl) FILTER (WHERE net_pnl > 0)::numeric, 2) AS avg_win,
    ROUND(AVG(net_pnl) FILTER (WHERE net_pnl < 0)::numeric, 2) AS avg_loss,
    ROUND(SUM(net_pnl)::numeric, 2)             AS total_pnl,
    ROUND(STDDEV(net_pnl)::numeric, 2)          AS pnl_stddev,
    ROUND(
        (COUNT(*) FILTER (WHERE net_pnl > 0)::float / NULLIF(COUNT(*), 0))::numeric, 4
    )                                            AS win_rate,
    ROUND(
        (AVG(net_pnl) FILTER (WHERE net_pnl > 0) /
         NULLIF(ABS(AVG(net_pnl) FILTER (WHERE net_pnl < 0)), 0))::numeric, 2
    )                                            AS profit_factor,
    ROUND(AVG(risk_reward_actual)::numeric, 2)   AS avg_rr,
    ROUND(MAX(net_pnl)::numeric, 2)              AS best_trade,
    ROUND(MIN(net_pnl)::numeric, 2)              AS worst_trade,
    ROUND(AVG(confluence_score)::numeric, 1)     AS avg_confluence,
    MIN(entry_time)                              AS first_trade,
    MAX(entry_time)                              AS last_trade
FROM trades
WHERE status = 'closed'
GROUP BY strategy_id
WITH NO DATA;

CREATE UNIQUE INDEX idx_v_strategy_perf_id ON v_strategy_performance (strategy_id);

-- Agent performance view
CREATE MATERIALIZED VIEW v_agent_performance AS
SELECT
    agent_id,
    strategy_id,
    COUNT(*)                                    AS total_signals,
    COUNT(*) FILTER (WHERE t.net_pnl > 0)       AS profitable_signals,
    ROUND(AVG(t.confluence_score)::numeric, 1)  AS avg_confluence,
    ROUND(SUM(t.net_pnl)::numeric, 2)           AS total_pnl,
    ROUND(
        (COUNT(*) FILTER (WHERE t.net_pnl > 0)::float / NULLIF(COUNT(*), 0))::numeric, 4
    )                                            AS signal_accuracy
FROM trades t
WHERE t.status = 'closed'
GROUP BY agent_id, strategy_id
WITH NO DATA;

CREATE UNIQUE INDEX idx_v_agent_perf_id ON v_agent_performance (agent_id, strategy_id);
```

### 4.3 Positions

```sql
-- ============================================================
-- POSITIONS — Current open positions (cross-broker)
-- ============================================================
CREATE TABLE positions (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    trade_id            UUID            REFERENCES trades(id),  -- Link to originating trade
    symbol              TEXT            NOT NULL,
    side                order_side      NOT NULL,
    quantity            NUMERIC(20, 8)  NOT NULL,
    entry_price         NUMERIC(20, 8)  NOT NULL,
    current_price       NUMERIC(20, 8),
    unrealized_pnl      NUMERIC(20, 8)  DEFAULT 0,
    margin_used         NUMERIC(20, 8)  DEFAULT 0,
    broker_id           TEXT            NOT NULL,
    broker_position_id  TEXT,                               -- Broker's native position ID
    asset_class         TEXT            NOT NULL,
    strategy_id         TEXT            NOT NULL,
    agent_id            TEXT            NOT NULL,

    -- Risk
    stop_loss           NUMERIC(20, 8),
    take_profit         NUMERIC(20, 8),
    trailing_stop_active BOOLEAN        DEFAULT FALSE,
    trailing_stop_price NUMERIC(20, 8),

    -- State
    status              TEXT            NOT NULL DEFAULT 'open',  -- 'open', 'closing', 'closed'
    opened_at           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    closed_at           TIMESTAMPTZ,
    last_price_update   TIMESTAMPTZ,

    metadata            JSONB           DEFAULT '{}'
);

CREATE INDEX idx_positions_symbol ON positions (symbol) WHERE status = 'open';
CREATE INDEX idx_positions_broker ON positions (broker_id) WHERE status = 'open';
CREATE INDEX idx_positions_strategy ON positions (strategy_id) WHERE status = 'open';

-- Composite index for risk engine: "all open positions"
CREATE INDEX idx_positions_open ON positions (status) WHERE status = 'open';


-- ============================================================
-- POSITION HISTORY — Snapshots of position state over time
-- Used for drawdown analysis and trade management review
-- ============================================================
CREATE TABLE position_snapshots (
    id              BIGSERIAL       PRIMARY KEY,
    position_id     UUID            NOT NULL REFERENCES positions(id),
    time            TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    current_price   NUMERIC(20, 8)  NOT NULL,
    unrealized_pnl  NUMERIC(20, 8)  NOT NULL,
    margin_used     NUMERIC(20, 8),
    drawdown_pct    NUMERIC(10, 4),                     -- Current drawdown from peak
    metadata        JSONB           DEFAULT '{}'
);

CREATE INDEX idx_pos_snap_position_time ON position_snapshots (position_id, time DESC);
```

### 4.4 Account Balances

```sql
-- ============================================================
-- ACCOUNT BALANCES — Per-broker account state
-- ============================================================
CREATE TABLE accounts (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    broker_id           TEXT            NOT NULL UNIQUE,
    label               TEXT,                               -- 'FXPesa Main', 'Binance Spot'
    currency            TEXT            NOT NULL DEFAULT 'USD',
    balance             NUMERIC(20, 8)  NOT NULL DEFAULT 0,
    equity              NUMERIC(20, 8)  NOT NULL DEFAULT 0,
    margin_used         NUMERIC(20, 8)  NOT NULL DEFAULT 0,
    margin_free         NUMERIC(20, 8)  NOT NULL DEFAULT 0,
    unrealized_pnl      NUMERIC(20, 8)  NOT NULL DEFAULT 0,
    -- Risk tracking
    daily_pnl           NUMERIC(20, 8)  NOT NULL DEFAULT 0,
    daily_pnl_pct       NUMERIC(10, 4)  NOT NULL DEFAULT 0,
    max_drawdown        NUMERIC(20, 8)  NOT NULL DEFAULT 0,
    max_drawdown_pct    NUMERIC(10, 4)  NOT NULL DEFAULT 0,
    high_water_mark     NUMERIC(20, 8)  NOT NULL DEFAULT 0,
    -- Status
    status              TEXT            NOT NULL DEFAULT 'active',  -- 'active', 'suspended', 'closed'
    last_sync_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    metadata            JSONB           DEFAULT '{}'
);

-- Balance history for equity curve tracking
CREATE TABLE account_balance_history (
    id              BIGSERIAL       PRIMARY KEY,
    account_id      UUID            NOT NULL REFERENCES accounts(id),
    time            TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    balance         NUMERIC(20, 8)  NOT NULL,
    equity          NUMERIC(20, 8)  NOT NULL,
    margin_used     NUMERIC(20, 8),
    daily_pnl       NUMERIC(20, 8),
    open_positions  INTEGER         DEFAULT 0
);

CREATE INDEX idx_balance_history_account ON account_balance_history (account_id, time DESC);
```

---

## 5. Redis Schema — Real-Time State

Redis serves as the **hot path** — sub-millisecond access for live trading decisions.

### 5.1 Key Patterns

```
# ============================================================
# MARKET DATA — Latest prices, candles, order books
# ============================================================

# Latest tick per symbol (TTL: 60s, auto-expire on stale data)
tick:{symbol}                   → Hash {bid, ask, last, spread, mid, bid_vol, ask_vol, time, source}

# Current (unclosed) candle per symbol/timeframe
ohlcv:{symbol}:{timeframe}      → Hash {open, high, low, close, volume, tick_count, vwap, time}

# Latest order book top-20
book:{symbol}                   → Hash {bids_json, asks_json, spread, mid, time}  (TTL: 10s)

# Current and average spread
spread:{symbol}                 → Hash {current, avg_1h, avg_4h, avg_1d}

# ============================================================
# AGENT STATE — Signal state, agent health
# ============================================================

# Latest signal from each agent per symbol
signal:{agent_id}:{symbol}      → Hash {direction, confidence, timeframe, score, time, reasoning}
                                (TTL: 5 min, expires if agent stops producing)

# Aggregated confluence score per symbol
confluence:{symbol}             → Hash {score, direction, agents_voted, timestamp}

# Current market regime per symbol (set by Meta Agent)
regime:{symbol}                 → Hash {regime, confidence, time}
                                # regime: 'trending_bull', 'trending_bear', 'range', 'volatile'

# Session state
session_state                   → Hash {current_session, time_to_next, volatility_profile}
                                # current_session: 'asian', 'london', 'new_york', 'overlap', 'closed'

# Agent health status
agent:{agent_id}:health         → Hash {status, uptime_s, signals_produced, avg_inference_ms,
                                        errors_1h, memory_mb, last_heartbeat}
                                (TTL: 60s, refreshed by heartbeat)

# ============================================================
# RISK STATE — Positions, account, limits
# ============================================================

# Current positions per account/symbol
position:{account_id}:{symbol}  → Hash {side, quantity, entry_price, current_price,
                                        unrealized_pnl, stop_loss, take_profit, strategy_id}

# Account summary (refreshed every 1s from broker)
account:{account_id}            → Hash {balance, equity, margin_used, margin_free,
                                        daily_pnl, daily_pnl_pct, open_positions, max_drawdown_pct}

# Risk limit utilization
risk:{account_id}               → Hash {max_risk_per_trade, max_daily_loss, max_positions,
                                        max_drawdown, current_daily_loss, current_positions,
                                        current_drawdown_pct, circuit_breaker_state}

# ============================================================
# ECONOMIC CALENDAR — Today's events
# ============================================================

calendar:today                  → JSON (list of events with time, currency, impact, name)
                                (TTL: 24h, refreshed daily at 00:05 UTC)

# ============================================================
# SENTIMENT / ALTERNATIVE DATA
# ============================================================

fear_greed                      → Hash {value, classification, time}
                                (TTL: 1h)

funding:{symbol}                → Hash {rate, predicted_rate, open_interest, time}
                                (TTL: 1 min)

# ============================================================
# SYSTEM STATE
# ============================================================

system:status                   → Hash {uptime, active_agents, active_symbols, active_orders,
                                        circuit_breaker, last_error_time}
circuit_breaker:{broker_id}     → String 'closed' | 'open' | 'half_open'
                                (TTL: set dynamically based on state)
```

### 5.2 Redis Pub/Sub Channels

```
# Real-time price distribution
tick:{symbol}                   → Published by ingestion, subscribed by all active signal agents

# Signal broadcast
signal:{symbol}                 → Published by signal agents, subscribed by execution + risk

# Order lifecycle events
order:{account_id}              → Published by execution engine, subscribed by risk + portfolio

# System alerts
alert:system                    → Published by any component, subscribed by monitor + notifications

# Regime changes
regime:{symbol}                 → Published by meta agent, subscribed by all signal agents

# Kill switch (emergency halt)
kill_switch                     → Published by risk engine or human, subscribed by ALL components
```

### 5.3 Redis Streams (Durable Event Log)

```
# Per-symbol tick stream (consumer groups: signal-agents, risk-monitor)
stream:ticks:{symbol}           → Trimmed to maxlen 10000 (~1 hour of ticks)

# Closed candle stream (consumer groups: signal-agents, backtest)
stream:ohlcv:{symbol}:{tf}     → Retained 7 days

# All generated signals (consumer groups: execution-engine, risk-manager, journal)
stream:signals                  → Retained 7 days

# Order lifecycle events (consumer groups: portfolio-manager, monitor, journal)
stream:orders                   → Retained 30 days

# News and sentiment events
stream:news                     → Retained 24 hours

# System events (errors, health, config changes)
stream:system                   → Retained 7 days

# Dead letter queue for failed message processing
stream:dlq                      → Retained 30 days
```

### 5.4 Redis Data Structures for Agent Memory

```
# ============================================================
# SHORT-TERM AGENT MEMORY (per-session)
# ============================================================

# Agent's recent observations (capped list, last 100)
agent:{agent_id}:observations   → List (LPUSH, LTRIM 0 99)

# Agent's recent decisions (capped list, last 50)
agent:{agent_id}:decisions      → List (LPUSH, LTRIM 0 49)

# Pattern detection cache (symbol → detected patterns)
patterns:{symbol}               → Hash {ob_high, ob_low, fvg_high, fvg_low, bos_direction, ...}
                                (TTL: until next candle close)

# Indicators cache (pre-computed, shared across agents)
indicators:{symbol}:{timeframe} → Hash {rsi, atr, macd, ema_20, ema_50, sma_200, ...}
                                (TTL: until next candle close)
```

---

## 6. Trade Journal Schema

The trade journal combines structured data (PostgreSQL) with narrative and analytical content.

### 6.1 Journal Entries

```sql
-- ============================================================
-- JOURNAL ENTRIES — Post-trade analysis and daily journals
-- ============================================================
CREATE TABLE journal_entries (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    entry_type          TEXT            NOT NULL,   -- 'trade', 'daily', 'weekly', 'monthly', 'insight'

    -- For trade entries
    trade_id            UUID            REFERENCES trades(id),

    -- Time context
    entry_date          DATE            NOT NULL,
    period_start        TIMESTAMPTZ,
    period_end          TIMESTAMPTZ,

    -- Content
    title               TEXT            NOT NULL,
    summary             TEXT,                       -- 1-2 sentence summary
    body_markdown       TEXT,                       -- Full journal entry in markdown

    -- Pre-trade analysis (for trade entries)
    pre_trade_thesis    TEXT,                       -- Why I took this trade
    expected_outcome    TEXT,                       -- What I expected to happen
    actual_outcome      TEXT,                       -- What actually happened

    -- Post-trade reflection (for trade entries)
    what_worked         TEXT[],                     -- List of things that went well
    what_failed         TEXT[],                     -- List of things that went wrong
    missing_signals     TEXT[],                     -- Signals I should have noticed
    lessons_learned     TEXT[],                     -- Distilled lessons

    -- Rating
    execution_grade     TEXT,                       -- 'A+', 'A', 'B', 'C', 'D', 'F'
    setup_quality       NUMERIC(3, 1),              -- 1-10 scale
    discipline_score    NUMERIC(3, 1),              -- 1-10 scale (did I follow the plan?)

    -- Analytics
    emotional_state     TEXT,                       -- 'calm', 'anxious', 'fomo', 'revenge', 'confident'
    market_conditions   TEXT,                       -- 'trending', 'ranging', 'volatile', 'low_vol'

    -- Media
    chart_urls          TEXT[],                     -- Screenshot URLs (entry, exit, context)
    annotations         JSONB,                      -- Chart annotations (key levels, patterns drawn)

    -- Tags for search
    tags                TEXT[],                     -- ['breakout', 'london_session', 'eurusd', 'lesson']

    -- Agent attribution
    generated_by        TEXT,                       -- 'journal_agent', 'reflection_agent', 'human'
    agent_reasoning     JSONB,                      -- Agent's ReAct trace for this entry

    -- Version control
    version             INTEGER         NOT NULL DEFAULT 1,
    previous_version_id UUID,

    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_journal_date ON journal_entries (entry_date DESC);
CREATE INDEX idx_journal_trade ON journal_entries (trade_id) WHERE trade_id IS NOT NULL;
CREATE INDEX idx_journal_type ON journal_entries (entry_type, entry_date DESC);
CREATE INDEX idx_journal_tags ON journal_entries USING GIN (tags);
CREATE INDEX idx_journal_grade ON journal_entries (execution_grade) WHERE execution_grade IS NOT NULL;


-- ============================================================
-- SCREENSHOTS — Chart screenshots and annotations
-- ============================================================
CREATE TABLE screenshots (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    trade_id            UUID            REFERENCES trades(id),
    journal_entry_id    UUID            REFERENCES journal_entries(id),

    -- File info
    url                 TEXT            NOT NULL,       -- Storage URL (S3, local, etc.)
    thumbnail_url       TEXT,
    file_size_bytes     INTEGER,
    mime_type           TEXT            NOT NULL DEFAULT 'image/png',

    -- Context
    symbol              TEXT,
    timeframe           TEXT,                           -- Timeframe of the chart
    chart_type          TEXT,                           -- 'entry', 'exit', 'context', 'analysis'
    capture_time        TIMESTAMPTZ,                    -- When the chart was captured
    price_at_capture    NUMERIC(20, 8),

    -- Annotations
    annotations         JSONB,                          -- [{type: 'line', x1, y1, x2, y2, color}, ...]
    description         TEXT,                           -- Human or AI description of what's shown

    -- ML embeddings for visual similarity search
    embedding           VECTOR(512),                    -- If pgvector enabled

    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_screenshots_trade ON screenshots (trade_id) WHERE trade_id IS NOT NULL;
CREATE INDEX idx_screenshots_journal ON screenshots (journal_entry_id) WHERE journal_entry_id IS NOT NULL;
```

### 6.2 Performance Analytics Tables

```sql
-- ============================================================
-- DAILY PERFORMANCE SUMMARY
-- ============================================================
CREATE TABLE daily_performance (
    date                DATE            PRIMARY KEY,
    -- P&L
    gross_pnl           NUMERIC(20, 8)  NOT NULL DEFAULT 0,
    fees                NUMERIC(20, 8)  NOT NULL DEFAULT 0,
    net_pnl             NUMERIC(20, 8)  NOT NULL DEFAULT 0,
    pnl_pct             NUMERIC(10, 4),
    -- Trade stats
    total_trades        INTEGER         NOT NULL DEFAULT 0,
    winning_trades      INTEGER         NOT NULL DEFAULT 0,
    losing_trades       INTEGER         NOT NULL DEFAULT 0,
    breakeven_trades    INTEGER         NOT NULL DEFAULT 0,
    -- Win/loss
    avg_win             NUMERIC(20, 8),
    avg_loss            NUMERIC(20, 8),
    largest_win         NUMERIC(20, 8),
    largest_loss        NUMERIC(20, 8),
    -- Risk
    max_drawdown        NUMERIC(20, 8),
    max_drawdown_pct    NUMERIC(10, 4),
    risk_reward_avg     NUMERIC(10, 4),
    -- Equity
    starting_equity     NUMERIC(20, 8),
    ending_equity       NUMERIC(20, 8),
    high_water_mark     NUMERIC(20, 8),
    -- Strategy attribution
    strategy_breakdown  JSONB,          -- {strategy_id: {trades, pnl, win_rate}, ...}
    -- Context
    regime              TEXT,
    volatility          TEXT,
    news_events         TEXT[],         -- High-impact events that day
    notes               TEXT,

    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);


-- ============================================================
-- STRATEGY PARAMETERS — Version-controlled strategy configs
-- ============================================================
CREATE TABLE strategy_parameters (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id         TEXT            NOT NULL,
    version             INTEGER         NOT NULL,
    parameters          JSONB           NOT NULL,       -- All configurable parameters
    change_reason       TEXT,                           -- Why parameters changed
    approved_by         TEXT,                           -- 'human', 'reflection_agent', 'auto'
    performance_before  JSONB,                          -- Performance metrics before change
    active              BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    UNIQUE (strategy_id, version)
);

CREATE INDEX idx_strategy_params_active ON strategy_parameters (strategy_id) WHERE active = TRUE;


-- ============================================================
-- SIGNAL WEIGHTS — Adaptive signal scoring weights
-- ============================================================
CREATE TABLE signal_weights (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id         TEXT            NOT NULL,
    agent_id            TEXT            NOT NULL,
    symbol              TEXT,                           -- NULL = global weight
    weight              NUMERIC(5, 4)   NOT NULL,       -- Current weight (0.0 - 1.0)
    base_weight         NUMERIC(5, 4)   NOT NULL,       -- Original weight before adaptation
    accuracy_50         NUMERIC(5, 4),                  -- Win rate over last 50 signals
    accuracy_total      NUMERIC(5, 4),                  -- All-time win rate
    total_signals       INTEGER         NOT NULL DEFAULT 0,
    last_adjustment     TIMESTAMPTZ,
    adjustment_reason   TEXT,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    UNIQUE (strategy_id, agent_id, symbol)
);


-- ============================================================
-- PATTERN RELIABILITY — Historical pattern win rates
-- ============================================================
CREATE TABLE pattern_reliability (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    pattern_type        TEXT            NOT NULL,       -- 'order_block', 'fvg', 'bos', 'divergence', 'hammer'
    pattern_subtype     TEXT,                           -- 'bullish_ob', 'bearish_ob', 'bullish_fvg', etc.
    symbol              TEXT,                           -- NULL = all symbols
    timeframe           TEXT,                           -- NULL = all timeframes
    regime              TEXT,                           -- NULL = all regimes
    session             TEXT,                           -- NULL = all sessions
    -- Stats
    total_occurrences   INTEGER         NOT NULL DEFAULT 0,
    successful          INTEGER         NOT NULL DEFAULT 0,
    failed              INTEGER         NOT NULL DEFAULT 0,
    win_rate            NUMERIC(5, 4)   GENERATED ALWAYS AS (
                            CASE WHEN total_occurrences > 0
                            THEN successful::numeric / total_occurrences
                            ELSE 0 END
                        ) STORED,
    avg_rr              NUMERIC(10, 4),                 -- Average R:R when successful
    avg_duration_hours  NUMERIC(10, 2),                 -- Average trade duration
    confidence_interval NUMERIC(5, 4),                  -- Statistical confidence in win_rate
    last_updated        TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    UNIQUE (pattern_type, pattern_subtype, symbol, timeframe, regime, session)
);

CREATE INDEX idx_pattern_reliability_type ON pattern_reliability (pattern_type, win_rate DESC);
```

---

## 7. User Accounts & Broker Connections

### 7.1 User Schema

```sql
-- ============================================================
-- USERS — Platform user accounts
-- ============================================================
CREATE TABLE users (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    email               TEXT            UNIQUE NOT NULL,
    display_name        TEXT            NOT NULL,
    password_hash       TEXT            NOT NULL,       -- bcrypt/argon2 hash

    -- Profile
    timezone            TEXT            NOT NULL DEFAULT 'UTC',
    preferred_currency  TEXT            NOT NULL DEFAULT 'USD',
    risk_tolerance      TEXT            NOT NULL DEFAULT 'moderate',  -- 'conservative', 'moderate', 'aggressive'

    -- Status
    status              TEXT            NOT NULL DEFAULT 'active',    -- 'active', 'suspended', 'deleted'
    email_verified      BOOLEAN         NOT NULL DEFAULT FALSE,
    mfa_enabled         BOOLEAN         NOT NULL DEFAULT FALSE,
    mfa_secret          TEXT,                               -- TOTP secret (encrypted)

    -- Subscription
    plan                TEXT            NOT NULL DEFAULT 'free',     -- 'free', 'pro', 'institutional'
    plan_expires_at     TIMESTAMPTZ,

    -- Audit
    last_login_at       TIMESTAMPTZ,
    login_count         INTEGER         NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);


-- ============================================================
-- BROKER CONNECTIONS — Encrypted broker credentials
-- Credentials are encrypted at the application layer before storage
-- ============================================================
CREATE TABLE broker_connections (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID            NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Connection info
    broker_type         TEXT            NOT NULL,       -- 'mt5', 'ccxt', 'oanda', 'ibkr'
    label               TEXT            NOT NULL,       -- 'FXPesa Main', 'Binance Spot'
    endpoint            TEXT,                           -- Server URL / exchange name

    -- Encrypted credentials (AES-256-GCM, encrypted at app layer)
    encrypted_credentials TEXT          NOT NULL,       -- JSON blob, encrypted
    credential_iv       TEXT            NOT NULL,       -- Initialization vector
    credential_tag      TEXT            NOT NULL,       -- Auth tag for GCM

    -- Capabilities
    asset_classes       TEXT[]          NOT NULL DEFAULT '{}',  -- ['forex', 'crypto']
    supported_symbols   JSONB,                          -- {normalized: native_format}
    default_symbol_map  JSONB,                          -- Bidirectional symbol mappings

    -- Status
    status              TEXT            NOT NULL DEFAULT 'disconnected',
    last_connected_at   TIMESTAMPTZ,
    last_error          TEXT,
    consecutive_failures INTEGER        NOT NULL DEFAULT 0,

    -- Rate limiting
    rate_limit_config   JSONB,                          -- {max_requests, window_seconds}

    -- Audit
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    last_used_at        TIMESTAMPTZ
);

CREATE INDEX idx_broker_conn_user ON broker_connections (user_id);
CREATE INDEX idx_broker_conn_status ON broker_connections (status) WHERE status = 'connected';


-- ============================================================
-- USER SESSIONS — Active sessions for auth
-- ============================================================
CREATE TABLE user_sessions (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID            NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash          TEXT            NOT NULL UNIQUE,    -- SHA-256 of session token
    ip_address          INET,
    user_agent          TEXT,
    expires_at          TIMESTAMPTZ     NOT NULL,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sessions_user ON user_sessions (user_id);
CREATE INDEX idx_sessions_expires ON user_sessions (expires_at);

-- Cleanup expired sessions
CREATE OR REPLACE FUNCTION cleanup_expired_sessions()
RETURNS void AS $$
BEGIN
    DELETE FROM user_sessions WHERE expires_at < NOW();
END;
$$ LANGUAGE plpgsql;


-- ============================================================
-- API KEYS — For programmatic access
-- ============================================================
CREATE TABLE api_keys (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID            NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    label               TEXT            NOT NULL,
    key_hash            TEXT            NOT NULL UNIQUE,    -- SHA-256 of API key
    key_prefix          TEXT            NOT NULL,           -- First 8 chars for identification
    permissions         JSONB           NOT NULL DEFAULT '{"read": true, "write": false}',
    rate_limit          INTEGER         NOT NULL DEFAULT 100,  -- Requests per minute
    last_used_at        TIMESTAMPTZ,
    expires_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_api_keys_user ON api_keys (user_id);
```

### 7.2 Security Notes

- **Credentials never stored in plaintext.** Encrypted with AES-256-GCM at the application layer using a user-derived master key.
- **Password hashing:** Argon2id with high memory cost (>64MB).
- **Session tokens:** Cryptographically random, hashed before storage, short-lived (24h).
- **API keys:** Only hash stored; plain key shown once at creation.
- **Audit log:** All credential access logged to `system_events`.

---

## 8. Agent Memory Schema

### 8.1 Memory Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                    AGENT MEMORY SYSTEM                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  LAYER 1: WORKING MEMORY (Redis)                                    │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  Current market state, active positions, latest signals,      │  │
│  │  in-progress pipeline state, agent observations               │  │
│  │  TTL: Session-scoped (minutes to hours)                       │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  LAYER 2: SHORT-TERM MEMORY (Redis + PostgreSQL)                    │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  Today's signals, trades, news, session observations.         │  │
│  │  Recent pattern detections, indicator caches.                 │  │
│  │  TTL: 1-7 days                                                │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  LAYER 3: LONG-TERM MEMORY (PostgreSQL + pgvector)                  │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  Strategy parameters, signal weights, pattern reliability,    │  │
│  │  market regime history, distilled lessons (EDGE_NOTES).       │  │
│  │  TTL: Permanent (with periodic pruning)                       │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  LAYER 4: EPISODIC MEMORY (PostgreSQL + pgvector)                   │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  Complete trade records with full context, reasoning traces,  │  │
│  │  embeddings for semantic similarity search.                   │  │
│  │  TTL: Permanent                                               │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 8.2 Database Tables for Memory

```sql
-- ============================================================
-- EPISODIC MEMORY — Complete trade episodes with embeddings
-- Enables: "Find trades similar to current conditions"
-- ============================================================
CREATE TABLE trade_episodes (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    trade_id            UUID            NOT NULL REFERENCES trades(id),

    -- Context at time of trade
    symbol              TEXT            NOT NULL,
    timeframe           TEXT            NOT NULL,
    session             TEXT,
    regime              TEXT,
    volatility_regime   TEXT,                       -- 'low', 'normal', 'high', 'extreme'

    -- Multi-agent signals at entry
    signals_snapshot    JSONB           NOT NULL,   -- All agent signals at decision time
    confluence_score    NUMERIC(5, 2),
    entry_reasoning     TEXT,                       -- Natural language explanation

    -- Outcome
    outcome             TEXT            NOT NULL,   -- 'win', 'loss', 'breakeven'
    net_pnl             NUMERIC(20, 8),
    risk_reward_actual  NUMERIC(10, 4),
    duration_hours      NUMERIC(10, 2),

    -- Lessons
    lessons             TEXT[],                     -- Distilled lessons from this trade
    what_worked         TEXT[],
    what_failed         TEXT[],

    -- Embedding for semantic search (requires pgvector)
    -- Embedding encodes: symbol + regime + signals + conditions + outcome
    context_embedding   VECTOR(1536),               -- OpenAI/text-embedding-3-small dimension
    reasoning_embedding VECTOR(1536),               -- Embedding of the reasoning text

    -- Tags
    tags                TEXT[],

    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- Index for similarity search (requires pgvector)
-- CREATE INDEX idx_episode_context_embedding ON trade_episodes
--     USING ivfflat (context_embedding vector_cosine_ops) WITH (lists = 100);
-- CREATE INDEX idx_episode_reasoning_embedding ON trade_episodes
--     USING ivfflat (reasoning_embedding vector_cosine_ops) WITH (lists = 100);

CREATE INDEX idx_episodes_symbol ON trade_episodes (symbol, created_at DESC);
CREATE INDEX idx_episodes_outcome ON trade_episodes (outcome, symbol);
CREATE INDEX idx_episodes_regime ON trade_episodes (regime, outcome);
CREATE INDEX idx_episodes_tags ON trade_episodes USING GIN (tags);


-- ============================================================
-- AGENT MEMORY ENTRIES — Distilled knowledge per agent
-- Each agent can store and retrieve its own memories
-- ============================================================
CREATE TABLE agent_memories (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id            TEXT            NOT NULL,
    memory_type         TEXT            NOT NULL,   -- 'lesson', 'observation', 'pattern', 'rule', 'insight'

    -- Content
    title               TEXT            NOT NULL,
    content             TEXT            NOT NULL,   -- The memory content
    content_structured  JSONB,                      -- Structured version if applicable

    -- Context
    symbol              TEXT,                       -- NULL = general
    timeframe           TEXT,
    regime              TEXT,
    strategy_id         TEXT,

    -- Importance and decay
    importance          NUMERIC(3, 2)   NOT NULL DEFAULT 0.5,  -- 0.0 to 1.0
    access_count        INTEGER         NOT NULL DEFAULT 0,    -- How often accessed
    last_accessed_at    TIMESTAMPTZ,
    decay_rate          NUMERIC(5, 4)   NOT NULL DEFAULT 0.01, -- How fast importance decays

    -- Source
    source_trade_ids    UUID[],                     -- Which trades generated this memory
    source_type         TEXT            NOT NULL,   -- 'reflection', 'human', 'auto'

    -- Embedding for semantic retrieval
    embedding           VECTOR(1536),

    -- Lifecycle
    active              BOOLEAN         NOT NULL DEFAULT TRUE,
    superseded_by       UUID,                       -- If this memory was replaced
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_agent_mem_agent ON agent_memories (agent_id, memory_type, active) WHERE active = TRUE;
CREATE INDEX idx_agent_mem_symbol ON agent_memories (symbol, agent_id) WHERE active = TRUE;
CREATE INDEX idx_agent_mem_importance ON agent_memories (importance DESC) WHERE active = TRUE;
-- CREATE INDEX idx_agent_mem_embedding ON agent_memories
--     USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);


-- ============================================================
-- LESSON LOG — Distilled lessons promoted to long-term memory
-- This is the "curated wisdom" from the reflection loop
-- ============================================================
CREATE TABLE lessons (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    lesson_type         TEXT            NOT NULL,   -- 'strategy', 'risk', 'execution', 'market', 'psychology'

    -- Content
    title               TEXT            NOT NULL,
    description         TEXT            NOT NULL,
    rule                TEXT            NOT NULL,   -- Actionable rule: "When X, do Y because Z"

    -- Context
    symbol              TEXT,
    strategy_id         TEXT,
    regime              TEXT,
    timeframe           TEXT,

    -- Evidence
    supporting_trades   UUID[],                     -- Trade IDs that support this lesson
    contradicting_trades UUID[],                    -- Trade IDs that contradict this lesson
    confidence          NUMERIC(3, 2)   NOT NULL DEFAULT 0.5,  -- Based on evidence quality

    -- Impact
    times_applied       INTEGER         NOT NULL DEFAULT 0,
    success_when_applied INTEGER        NOT NULL DEFAULT 0,
    estimated_impact    NUMERIC(10, 2),             -- Estimated $ impact if followed

    -- Status
    status              TEXT            NOT NULL DEFAULT 'active',  -- 'active', 'superseded', 'archived'
    superseded_by       UUID            REFERENCES lessons(id),

    -- Embedding
    embedding           VECTOR(1536),

    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_lessons_type ON lessons (lesson_type, confidence DESC) WHERE status = 'active';
CREATE INDEX idx_lessons_strategy ON lessons (strategy_id) WHERE status = 'active';
CREATE INDEX idx_lessons_symbol ON lessons (symbol) WHERE status = 'active';
-- CREATE INDEX idx_lessons_embedding ON lessons
--     USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);


-- ============================================================
-- REGIME HISTORY — Market regime state transitions
-- Used by agents to understand "what happened before"
-- ============================================================
CREATE TABLE regime_history (
    id                  BIGSERIAL       PRIMARY KEY,
    symbol              TEXT            NOT NULL,
    time                TIMESTAMPTZ     NOT NULL,
    previous_regime     TEXT,
    new_regime          TEXT            NOT NULL,
    confidence          NUMERIC(3, 2)   NOT NULL,
    trigger             TEXT,                       -- 'hmm_transition', 'volatility_spike', 'structure_break'
    duration_hours      NUMERIC(10, 2),             -- How long in previous regime
    metadata            JSONB           DEFAULT '{}'
);

CREATE INDEX idx_regime_symbol_time ON regime_history (symbol, time DESC);
CREATE INDEX idx_regime_transition ON regime_history (symbol, new_regime, time DESC);
```

### 8.3 Memory Access Patterns

| Query | Table | Index | Latency Target |
|-------|-------|-------|----------------|
| "Last 50 observations from SMC agent" | Redis List | Direct key | <1ms |
| "Current regime for EUR/USD" | Redis Hash | Direct key | <1ms |
| "Find trades similar to current setup" | `trade_episodes` | Vector index (IVFFlat) | <50ms |
| "All lessons for Strategy X in trending regime" | `lessons` | Composite | <10ms |
| "Pattern reliability for bullish OB on EUR/USD H4" | `pattern_reliability` | Unique constraint | <5ms |
| "Agent memories for momentum agent about RSI" | `agent_memories` | Agent + type | <10ms |
| "Regime transitions for BTC/USDT in last 30 days" | `regime_history` | Symbol + time | <20ms |

### 8.4 Memory Lifecycle & Decay

```sql
-- Periodically decay unused memories (run weekly)
UPDATE agent_memories
SET importance = GREATEST(0.01, importance - decay_rate)
WHERE active = TRUE
  AND last_accessed_at < NOW() - INTERVAL '30 days'
  AND importance > 0.01;

-- Archive memories with very low importance
UPDATE agent_memories
SET active = FALSE
WHERE active = TRUE
  AND importance < 0.05
  AND last_accessed_at < NOW() - INTERVAL '90 days';

-- Promote frequently-accessed memories
UPDATE agent_memories
SET importance = LEAST(1.0, importance + 0.05)
WHERE active = TRUE
  AND access_count > 20
  AND last_accessed_at > NOW() - INTERVAL '7 days';
```

---

## 9. Migration Strategy

### 9.1 Tool: Alembic (Python)

All schema changes are managed through **Alembic** with version-controlled migrations.

```
alphastack/
├── alembic/
│   ├── alembic.ini
│   ├── env.py
│   └── versions/
│       ├── 001_initial_schema.py
│       ├── 002_add_timescaledb_hypertables.py
│       ├── 003_add_continuous_aggregates.py
│       └── ...
```

### 9.2 Migration Principles

| Principle | Rule |
|-----------|------|
| **Forward-only** | Never modify a deployed migration; always add a new one |
| **Idempotent** | Migrations use `IF NOT EXISTS`, `IF EXISTS` where possible |
| **Reversible** | Every migration has a `downgrade()` for rollback |
| **Zero-downtime** | No `ALTER TABLE` that locks the table for >1s on large tables |
| **Tested** | Migrations run against a staging copy of production data |
| **Ordered** | Sequential numbering with timestamps for merge conflict resolution |

### 9.3 Migration Categories

```python
# Category 1: Schema additions (safe, additive)
# - New tables, new columns (with defaults), new indexes
# Example:
def upgrade():
    op.add_column('trades', sa.Column('grade', sa.Text(), nullable=True))
    op.create_index('idx_trades_grade', 'trades', ['grade'])

def downgrade():
    op.drop_index('idx_trades_grade')
    op.drop_column('trades', 'grade')


# Category 2: TimescaleDB operations (hypertable creation, compression, retention)
# These are idempotent by nature
def upgrade():
    op.execute("SELECT create_hypertable('ticks', 'time', if_not_exists => TRUE)")
    op.execute("ALTER TABLE ticks SET (timescaledb.compress, ...)")
    op.execute("SELECT add_compression_policy('ticks', INTERVAL '7 days')")

def downgrade():
    op.execute("SELECT remove_compression_policy('ticks', if_exists => TRUE)")
    # Note: Can't un-hypertable a table; downgrade is limited


# Category 3: Data migrations (transform existing data)
# Run in batches to avoid long locks
def upgrade():
    # Example: Backfill confluence_score from signal data
    op.execute("""
        UPDATE trades t
        SET confluence_score = s.confluence_score
        FROM signals s
        WHERE t.signal_id = s.id AND t.confluence_score IS NULL
        LIMIT 10000
    """)
    # Run repeatedly until no more rows to update


# Category 4: Index creation (CONCURRENTLY to avoid locks)
def upgrade():
    op.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_new ON trades (new_col)")

def downgrade():
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_new")
```

### 9.4 Migration Workflow

```
1. Developer creates migration file
   $ alembic revision --autogenerate -m "add_trade_grade_column"

2. Review generated migration (Alembic auto-detect is imperfect)
   - Verify SQL is correct
   - Add CONCURRENTLY for index creation on large tables
   - Add batch operations for data migrations

3. Test against staging
   $ alembic upgrade head  # on staging DB with prod-like data

4. Verify application compatibility
   - Run test suite
   - Check that new columns have defaults
   - Verify no breaking changes to queries

5. Deploy to production
   $ alembic upgrade head  # on production DB

6. Monitor
   - Check for lock contention
   - Verify migration completed
   - Run application smoke tests
```

### 9.5 Phase-Gated Migration Sequence

| Migration | Phase | Description |
|-----------|-------|-------------|
| `001` | 1 | Core PostgreSQL tables (orders, trades, positions, accounts) |
| `002` | 1 | User accounts and broker connections |
| `003` | 1 | TimescaleDB hypertables (ticks, market_data, news_events) |
| `004` | 1 | Basic indexes |
| `005` | 1 | Journal entries and screenshots |
| `006` | 2 | Continuous aggregates (candle_1m through candle_1d) |
| `007` | 2 | Compression and retention policies |
| `008` | 2 | Agent memory tables (trade_episodes, agent_memories, lessons) |
| `009` | 2 | Pattern reliability and signal weights |
| `010` | 2 | Performance analytics (daily_performance, strategy_parameters) |
| `011` | 3 | pgvector extension for embeddings |
| `012` | 3 | Vector indexes on memory tables |
| `013` | 3 | Materialized views (v_strategy_performance, v_agent_performance) |
| `014` | 3 | Regime history table |
| `015` | 3 | ClickHouse analytics tables (if applicable) |

---

## 10. Backup & Recovery

### 10.1 Backup Strategy by Phase

| Phase | Method | Frequency | Retention | Storage |
|-------|--------|-----------|-----------|---------|
| **Phase 1** | `pg_dump` cron job | Daily at 03:00 UTC | 7 days | Local + external (S3/Backblaze) |
| **Phase 2** | `pg_dump` + WAL archiving | Daily full + continuous WAL | 30 days | External (encrypted) |
| **Phase 3** | Barman / pgBackRest | Daily full + hourly incremental + continuous WAL | 90 days | External (encrypted, multi-region) |
| **Phase 4** | Streaming replication + Barman | Continuous + daily snapshots | 1 year | Multi-region, encrypted |

### 10.2 Phase 1 Implementation

```bash
#!/bin/bash
# backup.sh — Daily PostgreSQL backup (Phase 1)
# Runs via cron: 0 3 * * * /path/to/backup.sh

set -euo pipefail

BACKUP_DIR="/home/work/.openclaw/workspace/alphastack/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DB_NAME="alphastack"
RETENTION_DAYS=7

# Create backup
pg_dump -Fc -Z9 "$DB_NAME" > "$BACKUP_DIR/alphastack_${TIMESTAMP}.dump"

# Verify backup integrity
pg_restore --list "$BACKUP_DIR/alphastack_${TIMESTAMP}.dump" > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "BACKUP VERIFICATION FAILED: ${TIMESTAMP}" | mail -s "Alpha Stack Backup Alert" admin@example.com
    exit 1
fi

# Upload to external storage (encrypted)
# gpg --symmetric --cipher-algo AES256 "$BACKUP_DIR/alphastack_${TIMESTAMP}.dump" | \
#     aws s3 cp - "s3://alphastack-backups/alphastack_${TIMESTAMP}.dump.gpg"

# Clean up old backups
find "$BACKUP_DIR" -name "*.dump" -mtime +${RETENTION_DAYS} -delete

echo "Backup completed: alphastack_${TIMESTAMP}.dump ($(du -h "$BACKUP_DIR/alphastack_${TIMESTAMP}.dump" | cut -f1))"
```

### 10.3 Phase 2: WAL Archiving

```sql
-- PostgreSQL configuration for continuous archiving
-- postgresql.conf:
-- wal_level = replica
-- archive_mode = on
-- archive_command = 'cp %p /archive/wal/%f'
-- max_wal_senders = 3

-- Create base backup
-- $ pg_basebackup -D /backup/base -Ft -z -P

-- Recovery procedure:
-- 1. Restore base backup
-- 2. Copy WAL files to pg_wal/
-- 3. Create recovery.signal
-- 4. Set restore_command in postgresql.conf
-- 5. Start PostgreSQL — it replays WALs to reach consistent state
```

### 10.4 Recovery Procedures

| Scenario | RTO | RPO | Procedure |
|----------|-----|-----|-----------|
| **Accidental DELETE** | < 1 hour | < 24 hours | Restore from latest `pg_dump` |
| **Corruption** | < 2 hours | < 1 hour (WAL) | Restore base backup + replay WALs |
| **Disk failure** | < 4 hours | < 24 hours | Restore from external backup |
| **Complete server loss** | < 8 hours | < 24 hours | Restore on new server from external backup |
| **Redis data loss** | < 5 minutes | None (ephemeral) | Rebuild from PostgreSQL + market feeds |

### 10.5 Redis Backup

Redis data is largely ephemeral (hot cache), but some state needs persistence:

```bash
# redis.conf
save 900 1      # Snapshot if at least 1 key changed in 900 seconds
save 300 10     # Snapshot if at least 10 keys changed in 300 seconds
save 60 10000   # Snapshot if at least 10000 keys changed in 60 seconds

appendonly yes
appendfsync everysec
```

**Recovery:** Redis rebuilds from PostgreSQL on startup. Critical state (positions, account balances) is re-fetched from broker APIs.

---

## 11. Data Retention Policies

### 11.1 Retention Matrix

| Data Type | Redis (Hot) | TimescaleDB (Uncompressed) | TimescaleDB (Compressed) | Archive |
|-----------|-------------|---------------------------|-------------------------|---------|
| **Ticks** | 60 seconds | 7 days | 90 days | Delete |
| **1m candles** | Until next candle | 30 days | 2 years | Compress forever |
| **5m–15m candles** | Until next candle | 90 days | 5 years | Compress forever |
| **1h candles** | Until next candle | 1 year | 10 years | Compress forever |
| **4h–1d candles** | Until next candle | Forever | — | — |
| **Order book snapshots** | 10 seconds | 3 days | 30 days | Delete |
| **Signals** | 5 minutes | 7 days (stream) | 90 days | 1 year, then delete |
| **Orders** | Current open only | Forever | — | — |
| **Trades** | — | Forever | — | — |
| **Positions** | Current open only | Forever (closed) | — | — |
| **News events** | 1 hour | 90 days | 1 year | Delete |
| **On-chain events** | 1 hour | 90 days | 2 years | Delete |
| **Alt-data snapshots** | 1 hour | 90 days | 1 year | Delete |
| **System events** | — | 90 days | 1 year | Delete |
| **Funding rates** | 1 minute | 90 days | 2 years | Delete |
| **Economic calendar** | 24 hours | Forever | — | — |
| **Journal entries** | — | Forever | — | — |
| **Agent memories** | — | Forever (active) | — | Prune inactive |
| **Lessons** | — | Forever | — | Archive superseded |
| **Trade episodes** | — | Forever | — | — |
| **Screenshots** | — | References forever | — | Files in object storage |

### 11.2 Automated Retention Implementation

```sql
-- TimescaleDB native retention (Phase 2+)
SELECT add_retention_policy('ticks', INTERVAL '90 days');
SELECT add_retention_policy('orderbook_snapshots', INTERVAL '30 days');
SELECT add_retention_policy('system_events', INTERVAL '90 days');
SELECT add_retention_policy('news_events', INTERVAL '1 year');
SELECT add_retention_policy('onchain_events', INTERVAL '1 year');
SELECT add_retention_policy('alt_data_snapshots', INTERVAL '1 year');
SELECT add_retention_policy('funding_rates', INTERVAL '2 years');

-- Manual retention for non-TimescaleDB tables (run via cron)
-- Archive old daily performance data
DELETE FROM daily_performance WHERE date < CURRENT_DATE - INTERVAL '10 years';

-- Prune expired sessions
DELETE FROM user_sessions WHERE expires_at < NOW();

-- Prune inactive agent memories with very low importance
UPDATE agent_memories SET active = FALSE
WHERE active = TRUE AND importance < 0.05 AND last_accessed_at < NOW() - INTERVAL '180 days';
```

### 11.3 Storage Estimates

| Scale | Ticks | Candles (all TFs) | Signals/Orders | News/Alt-data | Agent Memory | **Total** |
|-------|-------|-------------------|----------------|---------------|--------------|-----------|
| Phase 1 (3 pairs, 1 year) | ~5 GB | ~200 MB | ~10 MB | ~500 MB | ~50 MB | **~6 GB** |
| Phase 2 (10 pairs, 2 years) | ~50 GB | ~1 GB | ~50 MB | ~5 GB | ~200 MB | **~57 GB** |
| Phase 3 (28 pairs, 5 years) | ~200 GB | ~5 GB | ~200 MB | ~10 GB | ~500 MB | **~216 GB** |
| Phase 4 (50+ pairs, 10 years) | ~500 GB | ~15 GB | ~1 GB | ~30 GB | ~2 GB | **~548 GB** |

All fits comfortably on a single server with a 1TB SSD through Phase 3.

---

## 12. Query Optimization

### 12.1 Common Query Patterns & Index Strategy

| Query | Table | Index | Expected Latency |
|-------|-------|-------|-----------------|
| Last 500 candles for BTC/USDT 1h | `market_data` | `(symbol, timeframe, time DESC)` | <5ms |
| All ticks for EUR/USD today | `ticks` | `(symbol, time DESC)` | <50ms |
| Open positions for risk check | `positions` | `(status) WHERE status='open'` | <1ms |
| P&L by strategy last 30 days | `trades` | `(strategy_id, entry_time DESC)` | <20ms |
| Signals from agent X this week | `signals` (stream) | Redis `XRANGE` | <1ms |
| News mentioning BTC in last 24h | `news_events` | `GIN(symbols)` | <10ms |
| Trades similar to current setup | `trade_episodes` | Vector index (IVFFlat) | <50ms |
| Pattern reliability for bullish OB | `pattern_reliability` | Unique constraint | <5ms |
| Daily P&L equity curve | `daily_performance` | `(date)` | <5ms |
| Agent memory for SMC about EUR/USD | `agent_memories` | `(agent_id, symbol)` | <10ms |

### 12.2 Index Design Rules

```sql
-- RULE 1: Composite indexes follow query column order
-- Query: WHERE symbol = 'X' AND timeframe = 'Y' AND time > Z
-- Index: (symbol, timeframe, time DESC)

-- RULE 2: Partial indexes for filtered queries
-- Query: SELECT * FROM positions WHERE status = 'open'
-- Index: (status) WHERE status = 'open'  →  Tiny index, instant lookup

-- RULE 3: GIN indexes for array/JSONB containment queries
-- Query: WHERE symbols @> ARRAY['BTC/USDT']
-- Index: USING GIN (symbols)

-- RULE 4: CONCURRENTLY for index creation on large tables
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_new_index ON large_table (col);

-- RULE 5: Covering indexes for read-heavy queries
-- Include all columns needed to satisfy the query from the index alone
CREATE INDEX idx_trades_strategy_covering ON trades (strategy_id, entry_time DESC)
    INCLUDE (net_pnl, symbol, confluence_score);

-- RULE 6: BRIN indexes for naturally ordered data (timestamps)
-- Much smaller than B-tree for append-only time-series
CREATE INDEX idx_ticks_brin ON ticks USING BRIN (time);
```

### 12.3 Query Optimization Checklist

| Technique | When to Use | Example |
|-----------|-------------|---------|
| **EXPLAIN ANALYZE** | Any query >100ms | `EXPLAIN ANALYZE SELECT ...` |
| **Prepared statements** | Repeated queries from agents | `PREPARE stmt AS SELECT ...` |
| **Connection pooling** | >10 concurrent queries | PgBouncer (transaction mode) |
| **Materialized views** | Expensive aggregations queried frequently | `v_strategy_performance` |
| **Continuous aggregates** | Time-series rollups | `candle_1m` → `candle_1d` |
| **Batch inserts** | High-throughput ingestion | `INSERT INTO ticks VALUES (...),(...),(...)` |
| **Partition pruning** | Queries touching subset of time range | TimescaleDB does this automatically |
| **Cursor pagination** | Large result sets | `FETCH NEXT 100 ROWS ONLY` |
| **Denormalization** | Analytics queries needing many JOINs | Star schema in ClickHouse |
| **Read replicas** | Read-heavy analytical workloads | Streaming replication (Phase 3+) |

### 12.4 Connection Pool Configuration

```ini
# pgbouncer.ini
[databases]
alphastack = host=127.0.0.1 port=5432 dbname=alphastack

[pgbouncer]
listen_port = 6432
listen_addr = 127.0.0.1
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt

pool_mode = transaction          # Release connection after each transaction
max_client_conn = 200            # Max application connections
default_pool_size = 20           # Connections per user/database pair
min_pool_size = 5                # Keep warm connections
reserve_pool_size = 5            # Extra connections for spikes
reserve_pool_timeout = 3         # Seconds before using reserve pool
server_idle_timeout = 300        # Close idle server connections
client_idle_timeout = 600        # Close idle client connections
```

### 12.5 Query Performance Monitoring

```sql
-- Enable pg_stat_statements for query performance tracking
-- postgresql.conf:
-- shared_preload_libraries = 'pg_stat_statements'
-- pg_stat_statements.track = all
-- pg_stat_statements.max = 10000

-- Find slow queries
SELECT
    query,
    calls,
    round(total_exec_time::numeric, 2) AS total_ms,
    round(mean_exec_time::numeric, 2) AS avg_ms,
    round(stddev_exec_time::numeric, 2) AS stddev_ms,
    rows
FROM pg_stat_statements
WHERE mean_exec_time > 100  -- Queries averaging >100ms
ORDER BY total_exec_time DESC
LIMIT 20;

-- Find missing indexes (sequential scans on large tables)
SELECT
    schemaname,
    relname,
    seq_scan,
    seq_tup_read,
    idx_scan,
    n_live_tup
FROM pg_stat_user_tables
WHERE seq_scan > 100 AND n_live_tup > 10000
ORDER BY seq_tup_read DESC;

-- Check index usage
SELECT
    indexrelname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch,
    pg_size_pretty(pg_relation_size(indexrelid)) AS size
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;
```

---

## 13. Storage Estimates & Scaling

### 13.1 Write Volume Estimates

| Data Type | Writes/Day (Phase 1) | Writes/Day (Phase 3) | Writes/Day (Phase 4) |
|-----------|----------------------|----------------------|----------------------|
| Ticks (3 pairs → 28 pairs → 50+) | ~500K | ~5M | ~10M |
| Candles (computed from ticks) | ~4.5K | ~42K | ~75K |
| Order book snapshots | ~8.6K | ~80K | ~150K |
| Signals | ~100 | ~500 | ~2,000 |
| Orders | ~10 | ~50 | ~200 |
| News events | ~500 | ~2,000 | ~5,000 |
| System events | ~1,000 | ~10,000 | ~50,000 |

### 13.2 Scaling Decision Matrix

| Metric | Threshold | Action |
|--------|-----------|--------|
| PostgreSQL CPU >70% sustained | Phase 2→3 | Add read replica |
| PostgreSQL disk >80% | Any phase | Enable compression, archive old data |
| Tick write latency >10ms p99 | Phase 3→4 | Move to dedicated ingestion service |
| Redis memory >80% | Phase 2→3 | Increase maxmemory, review TTLs |
| Query latency >500ms for dashboards | Phase 3→4 | Add ClickHouse for analytics |
| Connection count >80% of max | Phase 2→3 | Tune PgBouncer, add connection pooling |
| Backup time >1 hour | Phase 3→4 | Switch to pgBackRest with incremental |

### 13.3 Horizontal Scaling Path

```
Phase 1: Single PostgreSQL + Redis
    └── Handles: 3 pairs, <100 trades/day

Phase 2: Single PostgreSQL + TimescaleDB extension + Redis
    └── Handles: 10 pairs, <500 trades/day

Phase 3: PostgreSQL primary + replica + Redis
    └── Handles: 28 pairs, <2000 trades/day
    └── Replica serves: analytics, backtesting, reporting

Phase 4: PostgreSQL cluster + ClickHouse + Redis Cluster + Kafka
    └── Handles: 50+ pairs, institutional volume
    └── ClickHouse: OLAP analytics
    └── Kafka: durable event bus
    └── Redis Cluster: distributed hot cache
```

---

## 14. Implementation Roadmap

### Phase 1: Foundation (Week 1-2)

```
□ Install PostgreSQL 16 + Redis 7 (Docker Compose)
□ Create database and user with proper permissions
□ Run migration 001: Core tables (orders, trades, positions, accounts)
□ Run migration 002: User accounts and broker connections
□ Run migration 003: TimescaleDB hypertables
□ Run migration 004: Basic indexes
□ Run migration 005: Journal entries
□ Set up PgBouncer for connection pooling
□ Write backup script (pg_dump cron job)
□ Write Redis key management module
□ Test: Insert sample data, verify queries <50ms
□ Document: Connection strings, credentials (in secrets manager)
```

### Phase 2: Enrichment (Week 3-4)

```
□ Run migration 006: Continuous aggregates
□ Run migration 007: Compression and retention policies
□ Run migration 008: Agent memory tables
□ Run migration 009: Pattern reliability + signal weights
□ Run migration 010: Performance analytics
□ Implement Redis Streams for event bus
□ Set up WAL archiving for continuous backup
□ Build materialized view refresh jobs
□ Test: Agent memory read/write, pattern reliability queries
□ Test: Backup and recovery procedure
```

### Phase 3: Professional (Week 5-8)

```
□ Run migration 011: pgvector extension
□ Run migration 012: Vector indexes
□ Run migration 013: Materialized views
□ Run migration 014: Regime history
□ Implement semantic search for trade episodes
□ Set up read replica for analytics
□ Implement pg_stat_statements monitoring
□ Build Grafana dashboards for DB health
□ Optimize slow queries (EXPLAIN ANALYZE audit)
□ Test: Full backup/restore cycle with WAL replay
```

### Phase 4: Institutional (Week 9+)

```
□ Evaluate ClickHouse for OLAP workload
□ Set up streaming replication
□ Implement Barman/pgBackRest for backup management
□ Evaluate Kafka for durable event bus
□ Build data pipeline: TimescaleDB → ClickHouse
□ Implement connection pool monitoring
□ Set up automated alerting (disk, CPU, slow queries)
□ Load testing: simulate 50+ pairs × full pipeline
□ Document runbooks for common operational tasks
```

---

## Appendix A: Entity Relationship Diagram

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│    users      │────▶│   accounts   │────▶│  positions   │
│              │     │              │     │              │
│ id           │     │ broker_id    │     │ trade_id ────┼──┐
│ email        │     │ balance      │     │ symbol       │  │
│ ...          │     │ equity       │     │ side         │  │
└──────────────┘     │ ...          │     │ ...          │  │
       │             └──────────────┘     └──────────────┘  │
       │                                                    │
       ▼                                                    │
┌──────────────┐     ┌──────────────┐     ┌──────────────┐  │
│  broker_     │     │    orders    │     │    trades     │◀─┘
│  connections │     │              │     │              │
│              │     │ symbol       │     │ strategy_id  │
│ broker_type  │     │ side         │     │ agent_id     │
│ encrypted_   │     │ status       │     │ entry_price  │
│ credentials  │     │ fill_price   │     │ exit_price   │
│ ...          │     │ signal_id ───┼─┐   │ net_pnl      │
└──────────────┘     │ ...          │ │   │ ...          │
                     └──────────────┘ │   └──────┬───────┘
                                      │          │
                                      ▼          ▼
                     ┌──────────────┐  │  ┌──────────────┐
                     │   signals    │  │  │  trade_      │
                     │   (stream)   │◀─┘  │  episodes    │
                     │              │     │              │
                     │ agent_id     │     │ signals_     │
                     │ signal_type  │     │ snapshot     │
                     │ confidence   │     │ context_     │
                     │ ...          │     │ embedding    │
                     └──────────────┘     └──────────────┘

┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  market_data │     │   journal_   │     │   agent_     │
│  (TimescaleDB)│    │   entries    │     │   memories   │
│              │     │              │     │              │
│ symbol       │     │ trade_id     │     │ agent_id     │
│ timeframe    │     │ body_markdown│     │ memory_type  │
│ OHLCV        │     │ lessons      │     │ content      │
│ ...          │     │ ...          │     │ embedding    │
└──────────────┘     └──────────────┘     └──────────────┘

┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│    ticks     │     │  news_events │     │   lessons    │
│  (TimescaleDB)│    │              │     │              │
│ symbol       │     │ headline     │     │ rule         │
│ bid/ask      │     │ sentiment    │     │ confidence   │
│ ...          │     │ symbols[]    │     │ evidence     │
└──────────────┘     └──────────────┘     └──────────────┘
```

---

## Appendix B: Configuration Reference

```yaml
# config/database.yaml
database:
  host: 127.0.0.1
  port: 5432
  name: alphastack
  user: alphastack
  # Password from environment variable: DATABASE_PASSWORD

  pool:
    min_size: 5
    max_size: 20
    timeout: 30

  pgbouncer:
    host: 127.0.0.1
    port: 6432
    pool_mode: transaction

  timescaledb:
    enabled: true
    compression:
      ticks: 7d
      market_data: 30d
      orderbook_snapshots: 3d
    retention:
      ticks: 90d
      orderbook_snapshots: 30d
      system_events: 90d

  backup:
    method: pg_dump  # or pgbackrest
    schedule: "0 3 * * *"  # Daily at 03:00 UTC
    retention_days: 7
    external_storage: s3://alphastack-backups/

redis:
  host: 127.0.0.1
  port: 6379
  db: 0
  maxmemory: 256mb
  maxmemory_policy: allkeys-lru
  persistence:
    save: ["900 1", "300 10", "60 10000"]
    appendonly: true
    appendfsync: everysec
```

---

## Appendix C: Security Checklist

- [ ] PostgreSQL: `pg_hba.conf` restricts to localhost only
- [ ] PostgreSQL: SSL required for all connections
- [ ] PostgreSQL: Separate users for app (read/write) and analytics (read-only)
- [ ] Redis: `bind 127.0.0.1` (no external access)
- [ ] Redis: `requirepass` set
- [ ] Credentials: Encrypted at rest (AES-256-GCM)
- [ ] Credentials: Never in logs, config files, or environment variables in plaintext
- [ ] Backups: Encrypted before upload to external storage
- [ ] Audit: All schema changes logged to `system_events`
- [ ] Access: Principle of least privilege for all database users
- [ ] Monitoring: Alert on failed login attempts
- [ ] Rotation: API keys rotated quarterly

---

*This architecture document is the blueprint for Alpha Stack's database layer. It defines every table, index, policy, and procedure needed to build an institutional-grade trading data platform. Start with Phase 1, validate the schema works for 3 pairs, then layer in complexity as data volume and capital grow.*

*Next: `architecture_execution.md` — Order routing, execution algorithms, and broker integration.*
