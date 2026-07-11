# Alpha Stack — Data Storage Architecture

> **Author:** Data Storage Architect  
> **Date:** 2026-07-11  
> **Status:** Architecture Design — Pre-Implementation  
> **Dependencies:** `architecture_data.md`, `architecture_database.md`, `research_scalability.md`, `research_curriculum_database.md`, `research_data_sources.md`  
> **Scope:** Complete storage layer — from $7 single-node to institutional-grade distributed systems

---

## Table of Contents

1. [Time-Series Storage (TimescaleDB)](#1-time-series-storage-timescaledb)
2. [Relational Storage (PostgreSQL)](#2-relational-storage-postgresql)
3. [Cache Storage (Redis)](#3-cache-storage-redis)
4. [Document Storage (MongoDB)](#4-document-storage-mongodb)
5. [File Storage](#5-file-storage)
6. [Data Retention Policies (Hot/Warm/Cold Tiers)](#6-data-retention-policies-hotwarmcold-tiers)
7. [Backup and Recovery](#7-backup-and-recovery)
8. [Data Encryption at Rest](#8-data-encryption-at-rest)
9. [Data Migration Strategy](#9-data-migration-strategy)
10. [Storage Scaling from $7 to Institutional](#10-storage-scaling-from-7-to-institutional)

---

## 1. Time-Series Storage (TimescaleDB)

### 1.1 Why TimescaleDB

| Criterion | TimescaleDB | InfluxDB | ClickHouse | Vanilla PostgreSQL |
|-----------|-------------|----------|------------|-------------------|
| SQL compatibility | ✅ Full PostgreSQL | ❌ InfluxQL/Flux | ⚠️ ClickHouse SQL | ✅ Full |
| JOINs with relational data | ✅ Native | ❌ No | ⚠️ Limited | ✅ Native |
| Automatic time partitioning | ✅ Hypertables | ✅ TSM engine | ✅ MergeTree | ❌ Manual |
| Continuous aggregates | ✅ Native | ✅ Tasks | ✅ Materialized views | ❌ Manual |
| Native compression | ✅ 95%+ reduction | ✅ Good | ✅ Excellent | ❌ No |
| Retention policies | ✅ Built-in | ✅ Built-in | ✅ TTL | ❌ Manual |
| ACID transactions | ✅ Full | ❌ Limited | ❌ No | ✅ Full |
| Extension ecosystem | ✅ Full PostgreSQL | ❌ Limited | ⚠️ Growing | ✅ Full |
| Operational complexity | Low (PG extension) | Medium | High | Low |

**Decision: TimescaleDB** — It extends PostgreSQL, so we get time-series optimization AND relational capabilities in a single database. No separate system to manage, no data synchronization between stores.

### 1.2 Hypertable Design

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
    tick_count      INTEGER,
    vwap            DOUBLE PRECISION,
    spread_avg      DOUBLE PRECISION,
    CONSTRAINT ohlcv_valid CHECK (
        open <= high AND low <= close AND low <= high AND volume >= 0
    )
);
SELECT create_hypertable('market_data', 'time',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE
);

CREATE INDEX idx_market_data_sym_tf_time ON market_data (symbol, timeframe, time DESC);

ALTER TABLE market_data SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol, timeframe',
    timescaledb.compress_orderby = 'time DESC'
);
SELECT add_compression_policy('market_data', INTERVAL '30 days');


-- ============================================================
-- ORDER BOOK SNAPSHOTS — Depth of market (top N levels)
-- ============================================================
CREATE TABLE orderbook_snapshots (
    time            TIMESTAMPTZ     NOT NULL,
    symbol          TEXT            NOT NULL,
    source          TEXT            NOT NULL,
    bids            JSONB           NOT NULL,   -- [{price, volume}, ...] top 20
    asks            JSONB           NOT NULL,
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
    symbol          TEXT            NOT NULL,
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
    source          TEXT            NOT NULL,
    headline        TEXT            NOT NULL,
    summary         TEXT,
    url             TEXT,
    symbols         TEXT[],
    sentiment       DOUBLE PRECISION,           -- -1.0 to +1.0
    impact          TEXT,                       -- 'low', 'medium', 'high'
    category        TEXT,
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
    chain           TEXT            NOT NULL,
    event_type      TEXT            NOT NULL,
    metric          TEXT            NOT NULL,
    value           DOUBLE PRECISION NOT NULL,
    metadata        JSONB DEFAULT '{}'
);
SELECT create_hypertable('onchain_events', 'time',
    chunk_time_interval => INTERVAL '30 days',
    if_not_exists => TRUE
);

CREATE INDEX idx_onchain_chain_type_time ON onchain_events (chain, event_type, time DESC);


-- ============================================================
-- ALTERNATIVE DATA SNAPSHOTS
-- ============================================================
CREATE TABLE alt_data_snapshots (
    snapshot_id     UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    time            TIMESTAMPTZ     NOT NULL,
    source          TEXT            NOT NULL,
    symbol          TEXT,
    metrics         JSONB           NOT NULL
);
SELECT create_hypertable('alt_data_snapshots', 'time',
    chunk_time_interval => INTERVAL '30 days',
    if_not_exists => TRUE
);

CREATE INDEX idx_alt_source_sym_time ON alt_data_snapshots (source, symbol, time DESC);


-- ============================================================
-- SYSTEM EVENTS — Audit trail
-- ============================================================
CREATE TABLE system_events (
    event_id        UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    time            TIMESTAMPTZ     NOT NULL,
    component       TEXT            NOT NULL,
    severity        TEXT            NOT NULL,
    event_type      TEXT            NOT NULL,
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
-- ECONOMIC CALENDAR
-- ============================================================
CREATE TABLE economic_calendar (
    event_id        UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    time            TIMESTAMPTZ     NOT NULL,
    currency        TEXT            NOT NULL,
    event_name      TEXT            NOT NULL,
    impact          TEXT            NOT NULL,
    actual          DOUBLE PRECISION,
    forecast        DOUBLE PRECISION,
    previous        DOUBLE PRECISION,
    revised         DOUBLE PRECISION,
    source          TEXT            NOT NULL,
    metadata        JSONB DEFAULT '{}'
);
SELECT create_hypertable('economic_calendar', 'time',
    chunk_time_interval => INTERVAL '30 days',
    if_not_exists => TRUE
);

CREATE INDEX idx_calendar_impact_time ON economic_calendar (impact, time DESC);
CREATE INDEX idx_calendar_currency ON economic_calendar (currency, time DESC);
```

### 1.3 Continuous Aggregates — Auto-Computed Candles

```sql
-- 1-MINUTE OHLCV from tick data (foundation for all higher timeframes)
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

SELECT add_continuous_aggregate_policy('candle_1m',
    start_offset    => INTERVAL '5 minutes',
    end_offset      => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute'
);

-- Higher timeframes built incrementally from 1m → 5m → 15m → 1h → 4h → 1d
-- Each level uses the previous as source, ensuring consistent aggregation

CREATE MATERIALIZED VIEW candle_5m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('5 minutes', time) AS time,
    symbol, '5m' AS timeframe,
    first(open, time) AS open, max(high) AS high, min(low) AS low,
    last(close, time) AS close, sum(volume) AS volume,
    sum(tick_count) AS tick_count, avg(vwap) AS vwap, avg(spread_avg) AS spread_avg
FROM market_data WHERE timeframe = '1m'
GROUP BY time_bucket('5 minutes', time), symbol
WITH NO DATA;

CREATE MATERIALIZED VIEW candle_15m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('15 minutes', time) AS time,
    symbol, '15m' AS timeframe,
    first(open, time) AS open, max(high) AS high, min(low) AS low,
    last(close, time) AS close, sum(volume) AS volume,
    sum(tick_count) AS tick_count, avg(vwap) AS vwap, avg(spread_avg) AS spread_avg
FROM market_data WHERE timeframe = '5m'
GROUP BY time_bucket('15 minutes', time), symbol
WITH NO DATA;

CREATE MATERIALIZED VIEW candle_1h
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS time,
    symbol, '1h' AS timeframe,
    first(open, time) AS open, max(high) AS high, min(low) AS low,
    last(close, time) AS close, sum(volume) AS volume,
    sum(tick_count) AS tick_count, avg(vwap) AS vwap, avg(spread_avg) AS spread_avg
FROM market_data WHERE timeframe = '15m'
GROUP BY time_bucket('1 hour', time), symbol
WITH NO DATA;

CREATE MATERIALIZED VIEW candle_4h
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('4 hours', time) AS time,
    symbol, '4h' AS timeframe,
    first(open, time) AS open, max(high) AS high, min(low) AS low,
    last(close, time) AS close, sum(volume) AS volume,
    sum(tick_count) AS tick_count, avg(vwap) AS vwap, avg(spread_avg) AS spread_avg
FROM market_data WHERE timeframe = '1h'
GROUP BY time_bucket('4 hours', time), symbol
WITH NO DATA;

CREATE MATERIALIZED VIEW candle_1d
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time) AS time,
    symbol, '1d' AS timeframe,
    first(open, time) AS open, max(high) AS high, min(low) AS low,
    last(close, time) AS close, sum(volume) AS volume,
    sum(tick_count) AS tick_count, avg(vwap) AS vwap, avg(spread_avg) AS spread_avg
FROM market_data WHERE timeframe = '4h'
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

### 1.4 TimescaleDB Query Performance Targets

| Query | Table | Index | Target Latency |
|-------|-------|-------|----------------|
| Last 500 candles for BTC/USDT 1h | `market_data` | `(symbol, timeframe, time DESC)` | <5ms |
| All ticks for EUR/USD today | `ticks` | `(symbol, time DESC)` | <50ms |
| News mentioning BTC in last 24h | `news_events` | `GIN(symbols)` + `(time DESC)` | <10ms |
| Funding rates for ETH/USDT last 30d | `funding_rates` | `(symbol, time DESC)` | <20ms |
| Backtest: all EUR/USD 1h candles 2020–2026 | `market_data` | Sequential scan (compressed) | <2s |
| On-chain events by chain + type | `onchain_events` | `(chain, event_type, time DESC)` | <20ms |

---

## 2. Relational Storage (PostgreSQL)

### 2.1 Design Principles for Transactional Data

| Principle | Implementation |
|-----------|---------------|
| **ACID for money** | All order/position/balance tables use SERIALIZABLE isolation |
| **Single source of truth** | One canonical table per entity; no duplicates |
| **Immutable audit trail** | Orders and trades are append-only; status changes add new rows |
| **Schema-on-write** | Structured data (trades, users) uses strict schema |
| **Referential integrity** | Foreign keys link orders→trades→signals→agents |

### 2.2 Orders Table

```sql
CREATE TYPE order_side AS ENUM ('buy', 'sell');
CREATE TYPE order_type AS ENUM ('market', 'limit', 'stop', 'stop_limit', 'trailing_stop');
CREATE TYPE order_status AS ENUM (
    'pending', 'submitted', 'open', 'partially_filled',
    'filled', 'cancelled', 'rejected', 'expired'
);
CREATE TYPE time_in_force AS ENUM ('gtc', 'ioc', 'fok', 'day');

CREATE TABLE orders (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol              TEXT            NOT NULL,
    side                order_side      NOT NULL,
    order_type          order_type      NOT NULL,
    quantity            NUMERIC(20, 8)  NOT NULL CHECK (quantity > 0),
    price               NUMERIC(20, 8),
    stop_loss           NUMERIC(20, 8),
    take_profit         NUMERIC(20, 8),
    trailing_stop_pips  NUMERIC(10, 4),
    time_in_force       time_in_force   NOT NULL DEFAULT 'gtc',
    broker_id           TEXT,
    broker_order_id     TEXT,
    asset_class         TEXT,
    status              order_status    NOT NULL DEFAULT 'pending',
    fill_price          NUMERIC(20, 8),
    fill_quantity       NUMERIC(20, 8)  DEFAULT 0,
    commission          NUMERIC(20, 8)  DEFAULT 0,
    commission_currency TEXT,
    slippage_pips       NUMERIC(10, 4),
    spread_at_fill      NUMERIC(10, 6),
    strategy_id         TEXT,
    signal_id           UUID,
    proposal_id         UUID,
    confluence_score    NUMERIC(5, 2),
    metadata            JSONB           DEFAULT '{}',
    rejection_reason    TEXT,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    submitted_at        TIMESTAMPTZ,
    filled_at           TIMESTAMPTZ,
    cancelled_at        TIMESTAMPTZ
);

CREATE INDEX idx_orders_status ON orders (status) WHERE status IN ('pending', 'submitted', 'open', 'partially_filled');
CREATE INDEX idx_orders_symbol_time ON orders (symbol, created_at DESC);
CREATE INDEX idx_orders_strategy_time ON orders (strategy_id, created_at DESC);
CREATE INDEX idx_orders_broker ON orders (broker_id, status);
CREATE INDEX idx_orders_signal ON orders (signal_id);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_orders_updated_at
    BEFORE UPDATE ON orders
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
```

### 2.3 Trades Table (Completed)

```sql
CREATE TABLE trades (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol              TEXT            NOT NULL,
    direction           order_side      NOT NULL,
    asset_class         TEXT            NOT NULL,
    entry_order_id      UUID            REFERENCES orders(id),
    entry_price         NUMERIC(20, 8)  NOT NULL,
    entry_time          TIMESTAMPTZ     NOT NULL,
    entry_slippage      NUMERIC(10, 4)  DEFAULT 0,
    entry_spread        NUMERIC(10, 6),
    exit_order_id       UUID            REFERENCES orders(id),
    exit_price          NUMERIC(20, 8),
    exit_time           TIMESTAMPTZ,
    exit_slippage       NUMERIC(10, 4)  DEFAULT 0,
    size                NUMERIC(20, 8)  NOT NULL,
    size_usd            NUMERIC(20, 2),
    gross_pnl           NUMERIC(20, 8)  DEFAULT 0,
    fees                NUMERIC(20, 8)  DEFAULT 0,
    net_pnl             NUMERIC(20, 8)  DEFAULT 0,
    pnl_pct             NUMERIC(10, 4),
    stop_loss           NUMERIC(20, 8),
    take_profit         NUMERIC(20, 8),
    risk_amount         NUMERIC(20, 8),
    risk_reward_actual  NUMERIC(10, 4),
    max_drawdown        NUMERIC(20, 8)  DEFAULT 0,
    max_profit          NUMERIC(20, 8)  DEFAULT 0,
    duration_seconds    INTEGER,
    bars_held           INTEGER,
    strategy_id         TEXT            NOT NULL,
    agent_id            TEXT            NOT NULL,
    signal_id           UUID,
    confluence_score    NUMERIC(5, 2),
    regime              TEXT,
    session             TEXT,
    volatility_atr      NUMERIC(10, 6),
    status              TEXT            NOT NULL DEFAULT 'open',
    close_reason        TEXT,
    notes               TEXT,
    screenshot_urls     TEXT[],
    grade               TEXT,
    metadata            JSONB           DEFAULT '{}',
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_trades_symbol_time ON trades (symbol, entry_time DESC);
CREATE INDEX idx_trades_strategy_time ON trades (strategy_id, entry_time DESC);
CREATE INDEX idx_trades_agent_time ON trades (agent_id, entry_time DESC);
CREATE INDEX idx_trades_status ON trades (status) WHERE status = 'open';
CREATE INDEX idx_trades_pnl ON trades (net_pnl, entry_time DESC);
CREATE INDEX idx_trades_session ON trades (session, entry_time DESC);
```

### 2.4 Positions Table

```sql
CREATE TABLE positions (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    trade_id            UUID            REFERENCES trades(id),
    symbol              TEXT            NOT NULL,
    side                order_side      NOT NULL,
    quantity            NUMERIC(20, 8)  NOT NULL,
    entry_price         NUMERIC(20, 8)  NOT NULL,
    current_price       NUMERIC(20, 8),
    unrealized_pnl      NUMERIC(20, 8)  DEFAULT 0,
    margin_used         NUMERIC(20, 8)  DEFAULT 0,
    broker_id           TEXT            NOT NULL,
    broker_position_id  TEXT,
    asset_class         TEXT            NOT NULL,
    strategy_id         TEXT            NOT NULL,
    agent_id            TEXT            NOT NULL,
    stop_loss           NUMERIC(20, 8),
    take_profit         NUMERIC(20, 8),
    trailing_stop_active BOOLEAN        DEFAULT FALSE,
    trailing_stop_price NUMERIC(20, 8),
    status              TEXT            NOT NULL DEFAULT 'open',
    opened_at           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    closed_at           TIMESTAMPTZ,
    last_price_update   TIMESTAMPTZ,
    metadata            JSONB           DEFAULT '{}'
);

CREATE INDEX idx_positions_symbol ON positions (symbol) WHERE status = 'open';
CREATE INDEX idx_positions_broker ON positions (broker_id) WHERE status = 'open';
CREATE INDEX idx_positions_strategy ON positions (strategy_id) WHERE status = 'open';
CREATE INDEX idx_positions_open ON positions (status) WHERE status = 'open';

-- Position snapshots for drawdown analysis
CREATE TABLE position_snapshots (
    id              BIGSERIAL       PRIMARY KEY,
    position_id     UUID            NOT NULL REFERENCES positions(id),
    time            TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    current_price   NUMERIC(20, 8)  NOT NULL,
    unrealized_pnl  NUMERIC(20, 8)  NOT NULL,
    margin_used     NUMERIC(20, 8),
    drawdown_pct    NUMERIC(10, 4),
    metadata        JSONB           DEFAULT '{}'
);

CREATE INDEX idx_pos_snap_position_time ON position_snapshots (position_id, time DESC);
```

### 2.5 Account Balances

```sql
CREATE TABLE accounts (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    broker_id           TEXT            NOT NULL UNIQUE,
    label               TEXT,
    currency            TEXT            NOT NULL DEFAULT 'USD',
    balance             NUMERIC(20, 8)  NOT NULL DEFAULT 0,
    equity              NUMERIC(20, 8)  NOT NULL DEFAULT 0,
    margin_used         NUMERIC(20, 8)  NOT NULL DEFAULT 0,
    margin_free         NUMERIC(20, 8)  NOT NULL DEFAULT 0,
    unrealized_pnl      NUMERIC(20, 8)  NOT NULL DEFAULT 0,
    daily_pnl           NUMERIC(20, 8)  NOT NULL DEFAULT 0,
    daily_pnl_pct       NUMERIC(10, 4)  NOT NULL DEFAULT 0,
    max_drawdown        NUMERIC(20, 8)  NOT NULL DEFAULT 0,
    max_drawdown_pct    NUMERIC(10, 4)  NOT NULL DEFAULT 0,
    high_water_mark     NUMERIC(20, 8)  NOT NULL DEFAULT 0,
    status              TEXT            NOT NULL DEFAULT 'active',
    last_sync_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    metadata            JSONB           DEFAULT '{}'
);

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

### 2.6 User Accounts & Broker Connections

```sql
CREATE TABLE users (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    email               TEXT            UNIQUE NOT NULL,
    display_name        TEXT            NOT NULL,
    password_hash       TEXT            NOT NULL,       -- Argon2id
    timezone            TEXT            NOT NULL DEFAULT 'UTC',
    preferred_currency  TEXT            NOT NULL DEFAULT 'USD',
    risk_tolerance      TEXT            NOT NULL DEFAULT 'moderate',
    status              TEXT            NOT NULL DEFAULT 'active',
    email_verified      BOOLEAN         NOT NULL DEFAULT FALSE,
    mfa_enabled         BOOLEAN         NOT NULL DEFAULT FALSE,
    mfa_secret          TEXT,                           -- Encrypted TOTP secret
    plan                TEXT            NOT NULL DEFAULT 'free',
    plan_expires_at     TIMESTAMPTZ,
    last_login_at       TIMESTAMPTZ,
    login_count         INTEGER         NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE TABLE broker_connections (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID            NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    broker_type         TEXT            NOT NULL,
    label               TEXT            NOT NULL,
    endpoint            TEXT,
    encrypted_credentials TEXT          NOT NULL,       -- AES-256-GCM encrypted JSON
    credential_iv       TEXT            NOT NULL,
    credential_tag      TEXT            NOT NULL,
    asset_classes       TEXT[]          NOT NULL DEFAULT '{}',
    supported_symbols   JSONB,
    default_symbol_map  JSONB,
    status              TEXT            NOT NULL DEFAULT 'disconnected',
    last_connected_at   TIMESTAMPTZ,
    last_error          TEXT,
    consecutive_failures INTEGER        NOT NULL DEFAULT 0,
    rate_limit_config   JSONB,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    last_used_at        TIMESTAMPTZ
);

CREATE INDEX idx_broker_conn_user ON broker_connections (user_id);

CREATE TABLE user_sessions (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID            NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash          TEXT            NOT NULL UNIQUE,
    ip_address          INET,
    user_agent          TEXT,
    expires_at          TIMESTAMPTZ     NOT NULL,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE TABLE api_keys (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID            NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    label               TEXT            NOT NULL,
    key_hash            TEXT            NOT NULL UNIQUE,
    key_prefix          TEXT            NOT NULL,
    permissions         JSONB           NOT NULL DEFAULT '{"read": true, "write": false}',
    rate_limit          INTEGER         NOT NULL DEFAULT 100,
    last_used_at        TIMESTAMPTZ,
    expires_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
```

### 2.7 Performance Analytics

```sql
CREATE TABLE daily_performance (
    date                DATE            PRIMARY KEY,
    gross_pnl           NUMERIC(20, 8)  NOT NULL DEFAULT 0,
    fees                NUMERIC(20, 8)  NOT NULL DEFAULT 0,
    net_pnl             NUMERIC(20, 8)  NOT NULL DEFAULT 0,
    pnl_pct             NUMERIC(10, 4),
    total_trades        INTEGER         NOT NULL DEFAULT 0,
    winning_trades      INTEGER         NOT NULL DEFAULT 0,
    losing_trades       INTEGER         NOT NULL DEFAULT 0,
    breakeven_trades    INTEGER         NOT NULL DEFAULT 0,
    avg_win             NUMERIC(20, 8),
    avg_loss            NUMERIC(20, 8),
    largest_win         NUMERIC(20, 8),
    largest_loss        NUMERIC(20, 8),
    max_drawdown        NUMERIC(20, 8),
    max_drawdown_pct    NUMERIC(10, 4),
    risk_reward_avg     NUMERIC(10, 4),
    starting_equity     NUMERIC(20, 8),
    ending_equity       NUMERIC(20, 8),
    high_water_mark     NUMERIC(20, 8),
    strategy_breakdown  JSONB,
    regime              TEXT,
    volatility          TEXT,
    news_events         TEXT[],
    notes               TEXT,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- Materialized views for strategy and agent performance
CREATE MATERIALIZED VIEW v_strategy_performance AS
SELECT
    strategy_id,
    COUNT(*)                                    AS total_trades,
    COUNT(*) FILTER (WHERE net_pnl > 0)         AS winning_trades,
    COUNT(*) FILTER (WHERE net_pnl < 0)         AS losing_trades,
    ROUND(AVG(net_pnl)::numeric, 2)             AS avg_pnl,
    ROUND(SUM(net_pnl)::numeric, 2)             AS total_pnl,
    ROUND(STDDEV(net_pnl)::numeric, 2)          AS pnl_stddev,
    ROUND((COUNT(*) FILTER (WHERE net_pnl > 0)::float / NULLIF(COUNT(*), 0))::numeric, 4) AS win_rate,
    ROUND((AVG(net_pnl) FILTER (WHERE net_pnl > 0) /
        NULLIF(ABS(AVG(net_pnl) FILTER (WHERE net_pnl < 0)), 0))::numeric, 2) AS profit_factor,
    ROUND(AVG(risk_reward_actual)::numeric, 2)   AS avg_rr,
    MIN(entry_time) AS first_trade, MAX(entry_time) AS last_trade
FROM trades WHERE status = 'closed'
GROUP BY strategy_id
WITH NO DATA;

CREATE UNIQUE INDEX idx_v_strategy_perf_id ON v_strategy_performance (strategy_id);
```

---

## 3. Cache Storage (Redis)

### 3.1 Redis Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        REDIS INSTANCE                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  KEY-VALUE STORE (Hot State)                            │    │
│  │  tick:{symbol}          Latest bid/ask/last (TTL: 60s)  │    │
│  │  book:{symbol}          Order book top 20 (TTL: 10s)    │    │
│  │  ohlcv:{symbol}:{tf}    Current unclosed candle         │    │
│  │  signal:{agent}:{sym}   Latest signal (TTL: 5min)       │    │
│  │  position:{acct}:{sym}  Current position                │    │
│  │  account:{acct}         Balance/equity/margin            │    │
│  │  regime:{symbol}        Current market regime            │    │
│  │  session_state          Current session + volatility     │    │
│  │  calendar:today         Today's economic events (24h)    │    │
│  │  fear_greed             Current index (TTL: 1h)          │    │
│  │  funding:{symbol}       Current funding rate (TTL: 1m)   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  PUB/SUB CHANNELS (Real-Time Distribution)              │    │
│  │  tick:{symbol}          Price updates → signal agents    │    │
│  │  signal:{symbol}        Signals → execution + risk       │    │
│  │  order:{account}        Orders → risk + portfolio        │    │
│  │  alert:system           Alerts → monitor + notifications │    │
│  │  regime:{symbol}        Regime changes → all agents      │    │
│  │  kill_switch            Emergency halt → ALL components  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  STREAMS (Durable Event Log)                            │    │
│  │  stream:ticks:{sym}     Tick stream (trim: 10K msgs)    │    │
│  │  stream:ohlcv:{s}:{tf}  Closed candles (retain: 7d)     │    │
│  │  stream:signals         All signals (retain: 7d)         │    │
│  │  stream:orders          Order lifecycle (retain: 30d)    │    │
│  │  stream:news            News events (retain: 24h)        │    │
│  │  stream:system          System events (retain: 7d)       │    │
│  │  stream:dlq             Dead letter queue (retain: 30d)  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  AGENT MEMORY (Short-Term)                              │    │
│  │  agent:{id}:observations  Last 100 observations (List)  │    │
│  │  agent:{id}:decisions     Last 50 decisions (List)       │    │
│  │  patterns:{symbol}        Detected patterns (Hash)       │    │
│  │  indicators:{sym}:{tf}    Pre-computed indicators (Hash) │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Redis Configuration

```conf
# redis.conf — Alpha Stack configuration

# Network
bind 127.0.0.1
port 6379
protected-mode yes
requirepass <set-via-env>

# Memory
maxmemory 256mb
maxmemory_policy allkeys-lru

# Persistence (AOF + RDB for durability)
save 900 1
save 300 10
save 60 10000
appendonly yes
appendfsync everysec

# Performance
hz 10
dynamic-hz yes
tcp-backlog 511
timeout 0
tcp-keepalive 300
```

### 3.3 Cache Invalidation Strategy

| Layer | TTL / Invalidation | Rationale |
|-------|-------------------|-----------|
| L0: Process memory | Overwritten on each tick | Current tick, current candle, agent state |
| L1: Redis KV | TTL-based auto-expiry | Market data expires naturally when stale |
| L1: Redis Pub/Sub | Fire-and-forget (no persistence) | Ephemeral notifications |
| L1: Redis Streams | Trimmed by maxlen / time | Ordered event log, bounded size |
| L2: TimescaleDB | Append-only (no invalidation) | Immutable time-series data |
| L2: Materialized views | Refreshed on schedule | Periodic recomputation |
| L3: ClickHouse | CDC from TimescaleDB | Eventually consistent analytics |

### 3.4 Redis Scaling Path

| Phase | Redis Config | Max Memory | Connections | Notes |
|-------|-------------|------------|-------------|-------|
| Phase 1 ($7) | Single instance, localhost | 128MB | ~10 | All components on same machine |
| Phase 2 ($100) | Single instance, Docker | 256MB | ~20 | Docker Compose with app |
| Phase 3 ($1K) | Single instance, dedicated | 512MB | ~50 | Separate from DB server |
| Phase 4 ($10K+) | Redis Cluster (3 masters) | 2GB+ | ~200 | Sharded by key prefix |

---

## 4. Document Storage (MongoDB)

### 4.1 Why MongoDB for Flexible Data

MongoDB serves three categories of data that don't fit neatly into relational schema:

| Category | Examples | Why MongoDB |
|----------|----------|-------------|
| **Strategy configurations** | Parameters, hyperparameters, feature lists | Each strategy has different fields |
| **Research notes** | Backtest results, analysis, hypotheses | Schema evolves with each experiment |
| **Agent configurations** | Model settings, prompts, tool configs | Heterogeneous agent types |

### 4.2 Collections Schema

```javascript
// ============================================================
// STRATEGY CONFIGURATIONS
// Each strategy has unique parameters — no fixed schema
// ============================================================
db.createCollection("strategy_configs", {
    validator: {
        $jsonSchema: {
            required: ["strategy_id", "version", "active"],
            properties: {
                strategy_id: { bsonType: "string" },
                version: { bsonType: "int" },
                active: { bsonType: "bool" },
                parameters: { bsonType: "object" },  // Flexible per strategy
                risk_limits: { bsonType: "object" },
                symbols: { bsonType: "array" },
                timeframes: { bsonType: "array" },
                created_at: { bsonType: "date" },
                updated_at: { bsonType: "date" }
            }
        }
    }
});

// Example documents:
db.strategy_configs.insertOne({
    strategy_id: "sma_crossover_v3",
    version: 3,
    active: true,
    parameters: {
        fast_period: 20,
        slow_period: 50,
        signal_smoothing: 5,
        min_confidence: 0.7,
        entry_filters: {
            min_atr: 0.0005,
            max_spread: 0.0003,
            allowed_sessions: ["london", "new_york"]
        }
    },
    risk_limits: {
        max_risk_per_trade_pct: 2.0,
        max_daily_loss_pct: 5.0,
        max_concurrent_positions: 3
    },
    symbols: ["EUR/USD", "GBP/USD", "USD/JPY"],
    timeframes: ["1h", "4h"],
    created_at: ISODate("2026-07-01"),
    updated_at: ISODate("2026-07-11")
});

db.strategy_configs.insertOne({
    strategy_id: "transformer_sentiment_v1",
    version: 1,
    active: true,
    parameters: {
        model_name: "finbert-base",
        max_sequence_length: 512,
        attention_heads: 8,
        hidden_layers: 4,
        sentiment_threshold: 0.6,
        news_lookback_hours: 24,
        feature_weights: {
            price_momentum: 0.3,
            sentiment_score: 0.4,
            volume_anomaly: 0.2,
            onchain_signal: 0.1
        }
    },
    symbols: ["BTC/USDT", "ETH/USDT"],
    timeframes: ["4h"],
    created_at: ISODate("2026-07-10")
});


// ============================================================
// RESEARCH NOTES — Backtest results, analysis, hypotheses
// ============================================================
db.createCollection("research_notes");

// Example:
db.research_notes.insertOne({
    title: "Mean Reversion on EUR/USD During Asian Session",
    author: "reflection_agent",
    date: ISODate("2026-07-11"),
    type: "backtest_result",
    hypothesis: "EUR/USD mean reverts more strongly during Asian session when ATR is below average",
    methodology: {
        period: { start: ISODate("2023-01-01"), end: ISODate("2026-06-30") },
        pairs: ["EUR/USD"],
        timeframes: ["15m"],
        parameters: { bb_period: 20, bb_std: 2.0, min_atr_ratio: 0.7 }
    },
    results: {
        total_trades: 847,
        win_rate: 0.623,
        profit_factor: 1.41,
        sharpe_ratio: 1.82,
        max_drawdown_pct: -4.2,
        avg_rr: 1.35
    },
    conclusion: "Viable edge when ATR < 70% of 20-period average. Best during 00:00-06:00 UTC.",
    tags: ["mean_reversion", "eurusd", "asian_session", "atr_filter"],
    trade_ids: []  // Link to specific trades if applicable
});


// ============================================================
// AGENT CONFIGURATIONS — Heterogeneous agent settings
// ============================================================
db.createCollection("agent_configs");

// Example: Signal agent config
db.agent_configs.insertOne({
    agent_id: "smc_agent_v2",
    agent_type: "signal",
    version: 2,
    model: {
        name: "mimo-v2.5-pro",
        temperature: 0.1,
        max_tokens: 2048,
        system_prompt_path: "prompts/smc_agent_v2.md"
    },
    indicators: {
        ema_periods: [20, 50, 200],
        rsi_period: 14,
        atr_period: 14,
        custom: {
            order_block_lookback: 50,
            fvg_min_size_atr: 0.3,
            bos_confirmation_bars: 2
        }
    },
    signals: {
        min_confidence: 0.65,
        confluence_required: 3,
        cooldown_minutes: 30
    },
    data_access: {
        hot: ["tick:EUR/USD", "ohlcv:EUR/USD:1h", "regime:EUR/USD"],
        cold: ["market_data:EUR/USD:1h:500", "trade_episodes:similar:10"]
    }
});

// Example: Sentiment agent config
db.agent_configs.insertOne({
    agent_id: "sentiment_agent_v1",
    agent_type: "signal",
    version: 1,
    sources: {
        news: { enabled: true, weight: 0.4, lookback_hours: 24 },
        reddit: { enabled: true, weight: 0.2, subreddits: ["cryptocurrency", "forex"] },
        fear_greed: { enabled: true, weight: 0.2 },
        funding_rates: { enabled: true, weight: 0.2 }
    },
    nlp: {
        model: "vader",  // Phase 1; upgrade to FinBERT later
        min_sentiment_magnitude: 0.3
    }
});


// ============================================================
// BACKTEST RESULTS — Structured backtest output
// ============================================================
db.createCollection("backtest_results");

db.backtest_results.insertOne({
    backtest_id: "bt_20260711_001",
    strategy_id: "sma_crossover_v3",
    run_date: ISODate("2026-07-11"),
    period: { start: ISODate("2024-01-01"), end: ISODate("2026-06-30") },
    symbols: ["EUR/USD", "GBP/USD"],
    timeframe: "1h",
    parameters: { fast_period: 20, slow_period: 50 },
    results: {
        total_trades: 1247,
        win_rate: 0.58,
        profit_factor: 1.52,
        sharpe: 1.94,
        sortino: 2.41,
        max_drawdown_pct: -8.3,
        calmar: 2.34,
        avg_trade_pnl: 12.45,
        avg_winner: 45.20,
        avg_loser: -32.10,
        expectancy: 0.35
    },
    equity_curve: "backtest_results/bt_20260711_001_equity.csv",
    trade_log: "backtest_results/bt_20260711_001_trades.csv",
    notes: "Walk-forward validated. Robust across 2024-2026."
});
```

### 4.3 MongoDB Indexes

```javascript
// Strategy configs
db.strategy_configs.createIndex({ strategy_id: 1, version: -1 });
db.strategy_configs.createIndex({ active: 1 });

// Research notes
db.research_notes.createIndex({ date: -1 });
db.research_notes.createIndex({ tags: 1 });
db.research_notes.createIndex({ type: 1, date: -1 });

// Agent configs
db.agent_configs.createIndex({ agent_id: 1 });
db.agent_configs.createIndex({ agent_type: 1 });

// Backtest results
db.backtest_results.createIndex({ strategy_id: 1, run_date: -1 });
db.backtest_results.createIndex({ backtest_id: 1 });
```

### 4.4 MongoDB Scaling Path

| Phase | Deployment | Storage | Notes |
|-------|-----------|---------|-------|
| Phase 1 | Embedded (SQLite substitute) or skip | <100MB | Config files in JSON/YAML |
| Phase 2 | Single MongoDB instance | <1GB | Docker container |
| Phase 3 | Replica set (primary + 2 secondaries) | <10GB | High availability |
| Phase 4 | Sharded cluster | <100GB | Horizontal scaling |

> **Phase 1 Note:** At $7 capital, MongoDB is optional. Strategy configs and agent configs can live as JSON/YAML files. MongoDB adds value when you have 10+ strategies with evolving schemas.

---

## 5. File Storage

### 5.1 File Categories

| Category | Examples | Storage Location | Retention |
|----------|----------|-----------------|-----------|
| **Chart screenshots** | Entry/exit charts, analysis | Object storage (S3/Backblaze) | Forever |
| **Reports** | Daily P&L, strategy reports | Object storage + local | Forever |
| **Backups** | Database dumps, WAL archives | Object storage (encrypted) | Per retention policy |
| **Model artifacts** | Trained ML models, weights | Object storage + local cache | Until superseded |
| **Logs** | Application logs, audit trails | Local + rotated | 90 days local, 1 year archive |
| **Config exports** | Strategy configs, agent configs | Git repository | Version-controlled |
| **Data exports** | CSV/Parquet exports for analysis | Object storage | 1 year |

### 5.2 Storage Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     FILE STORAGE LAYER                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  LOCAL DISK (/home/work/.openclaw/workspace/alphastack/)     │
│  ├── backups/           Daily pg_dump snapshots              │
│  ├── logs/              Application logs (rotated daily)     │
│  ├── screenshots/       Temporary chart screenshots          │
│  ├── models/            Active ML model artifacts            │
│  └── exports/           Temporary data exports               │
│                                                              │
│  OBJECT STORAGE (S3 / Backblaze B2 / MinIO)                 │
│  ├── screenshots/       Permanent chart storage              │
│  │   ├── {trade_id}/                                        │
│  │   │   ├── entry_chart.png                                │
│  │   │   ├── exit_chart.png                                 │
│  │   │   └── context_chart.png                              │
│  │   └── {date}/                                            │
│  ├── reports/           Generated reports                    │
│  │   ├── daily/{date}/                                      │
│  │   ├── weekly/{week}/                                     │
│  │   └── monthly/{month}/                                   │
│  ├── backups/           Encrypted database backups           │
│  │   ├── daily/                                             │
│  │   └── weekly/                                            │
│  ├── models/            ML model versions                    │
│  │   └── {model_name}/{version}/                            │
│  └── exports/           Data exports for analysis            │
│                                                              │
│  GIT REPOSITORY                                              │
│  ├── configs/           Strategy & agent configs             │
│  ├── prompts/           LLM system prompts                  │
│  └── migrations/        Alembic migration files              │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 5.3 Screenshot Storage Schema (PostgreSQL References)

The `screenshots` table in PostgreSQL stores metadata and URLs:

```sql
CREATE TABLE screenshots (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    trade_id            UUID            REFERENCES trades(id),
    journal_entry_id    UUID            REFERENCES journal_entries(id),
    url                 TEXT            NOT NULL,       -- Object storage URL
    thumbnail_url       TEXT,
    file_size_bytes     INTEGER,
    mime_type           TEXT            NOT NULL DEFAULT 'image/png',
    symbol              TEXT,
    timeframe           TEXT,
    chart_type          TEXT,                           -- 'entry', 'exit', 'context'
    capture_time        TIMESTAMPTZ,
    price_at_capture    NUMERIC(20, 8),
    annotations         JSONB,
    description         TEXT,
    embedding           VECTOR(512),                    -- For visual similarity search
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_screenshots_trade ON screenshots (trade_id) WHERE trade_id IS NOT NULL;
```

### 5.4 File Naming Convention

```
screenshots/{trade_id}/{chart_type}_{timestamp}.png
reports/daily/{YYYY-MM-DD}_performance.pdf
backups/daily/{YYYYMMDD_HHmmss}.dump.gpg
models/{model_name}/{version}/model.pkl
exports/{YYYY-MM}/{symbol}_{data_type}_{date_range}.parquet
```

### 5.5 Phase-Gated File Storage

| Phase | Storage | Cost | Notes |
|-------|---------|------|-------|
| Phase 1 ($7) | Local disk only | $0 | 50GB SSD is plenty |
| Phase 2 ($100) | Local + Backblaze B2 | ~$1/mo | $0.005/GB/mo, $0.01/GB egress |
| Phase 3 ($1K) | S3 Standard + Glacier | ~$5/mo | Lifecycle rules for cold tier |
| Phase 4 ($10K+) | S3 + CloudFront CDN | ~$20/mo | Multi-region for low-latency access |

---

## 6. Data Retention Policies (Hot/Warm/Cold Tiers)

### 6.1 Tiered Storage Model

```
┌───────────────────────────────────────────────────────────────────────────┐
│                    DATA TEMPERATURE TIERS                                  │
├───────────┬───────────────┬──────────────────┬───────────────────────────┤
│   HOT     │    WARM       │     COLD         │     ARCHIVE               │
│ (Redis)   │ (TimescaleDB  │ (TimescaleDB     │ (Object Storage           │
│           │  Uncompressed)│  Compressed)     │  / S3 Glacier)            │
├───────────┼───────────────┼──────────────────┼───────────────────────────┤
│ <1ms      │ <100ms        │ <500ms           │ Seconds (retrieval)       │
│           │               │                  │                           │
│ Latest    │ Recent data   │ Historical data  │ Regulatory / backup       │
│ ticks     │ (days-weeks)  │ (months-years)   │ (years)                   │
│ positions │ Candles       │ Compressed       │ Encrypted dumps           │
│ signals   │ News          │ ticks/candles    │ Cold backups              │
│ account   │ Trades        │ Old trades       │ Compliance archives       │
└───────────┴───────────────┴──────────────────┴───────────────────────────┘
```

### 6.2 Retention Matrix

| Data Type | Hot (Redis) | Warm (PG/TSDB Uncompressed) | Cold (TSDB Compressed) | Archive |
|-----------|-------------|------------------------------|------------------------|---------|
| **Ticks** | 60 seconds | 7 days | 90 days | Delete |
| **1m candles** | Until next candle | 30 days | 2 years | Compress forever |
| **5m–15m candles** | Until next candle | 90 days | 5 years | Compress forever |
| **1h candles** | Until next candle | 1 year | 10 years | Compress forever |
| **4h–1d candles** | Until next candle | Forever | — | — |
| **Order book snapshots** | 10 seconds | 3 days | 30 days | Delete |
| **Signals** | 5 minutes | 90 days | 1 year | Delete |
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
| **Agent memories** | Session-scoped | Forever (active) | — | Prune inactive |
| **Lessons** | — | Forever | — | Archive superseded |
| **Screenshots** | — | References forever | — | Files in object storage |

### 6.3 Automated Retention Implementation

```sql
-- TimescaleDB native retention policies (Phase 2+)
SELECT add_retention_policy('ticks', INTERVAL '90 days');
SELECT add_retention_policy('orderbook_snapshots', INTERVAL '30 days');
SELECT add_retention_policy('system_events', INTERVAL '90 days');
SELECT add_retention_policy('news_events', INTERVAL '1 year');
SELECT add_retention_policy('onchain_events', INTERVAL '1 year');
SELECT add_retention_policy('alt_data_snapshots', INTERVAL '1 year');
SELECT add_retention_policy('funding_rates', INTERVAL '2 years');

-- TimescaleDB compression policies
ALTER TABLE ticks SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol, source',
    timescaledb.compress_orderby = 'time DESC'
);
SELECT add_compression_policy('ticks', INTERVAL '7 days');

ALTER TABLE market_data SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol, timeframe',
    timescaledb.compress_orderby = 'time DESC'
);
SELECT add_compression_policy('market_data', INTERVAL '30 days');

ALTER TABLE orderbook_snapshots SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol',
    timescaledb.compress_orderby = 'time DESC'
);
SELECT add_compression_policy('orderbook_snapshots', INTERVAL '3 days');

-- Manual retention for non-TimescaleDB tables (run via cron)
-- Prune expired sessions
-- DELETE FROM user_sessions WHERE expires_at < NOW();

-- Prune inactive agent memories with very low importance
-- UPDATE agent_memories SET active = FALSE
-- WHERE active = TRUE AND importance < 0.05 AND last_accessed_at < NOW() - INTERVAL '180 days';
```

### 6.4 Agent Memory Decay

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

### 6.5 Storage Estimates by Phase

| Phase | Pairs | Duration | Ticks | Candles | Signals/Orders | News/Alt-data | Agent Memory | **Total** |
|-------|-------|----------|-------|---------|----------------|---------------|--------------|-----------|
| 1 ($7) | 3 | 1 year | ~5 GB | ~200 MB | ~10 MB | ~500 MB | ~50 MB | **~6 GB** |
| 2 ($100) | 10 | 2 years | ~50 GB | ~1 GB | ~50 MB | ~5 GB | ~200 MB | **~57 GB** |
| 3 ($1K) | 28 | 5 years | ~200 GB | ~5 GB | ~200 MB | ~10 GB | ~500 MB | **~216 GB** |
| 4 ($10K+) | 50+ | 10 years | ~500 GB | ~15 GB | ~1 GB | ~30 GB | ~2 GB | **~548 GB** |

All fits on a single server with a 1TB SSD through Phase 3.

---

## 7. Backup and Recovery

### 7.1 Backup Strategy by Phase

| Phase | Method | Frequency | Retention | Storage | Encryption |
|-------|--------|-----------|-----------|---------|------------|
| **1** | `pg_dump` cron | Daily at 03:00 UTC | 7 days | Local + external | GPG |
| **2** | `pg_dump` + WAL archiving | Daily full + continuous WAL | 30 days | External (encrypted) | GPG + SSL |
| **3** | Barman / pgBackRest | Daily full + hourly incremental + continuous WAL | 90 days | Multi-region, encrypted | AES-256 |
| **4** | Streaming replication + Barman | Continuous + daily snapshots | 1 year | Multi-region, encrypted | AES-256 |

### 7.2 Phase 1 Backup Script

```bash
#!/bin/bash
# backup.sh — Daily PostgreSQL backup
# Cron: 0 3 * * * /path/to/backup.sh

set -euo pipefail

BACKUP_DIR="/home/work/.openclaw/workspace/alphastack/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DB_NAME="alphastack"
RETENTION_DAYS=7

mkdir -p "$BACKUP_DIR"

# Create compressed backup
pg_dump -Fc -Z9 "$DB_NAME" > "$BACKUP_DIR/alphastack_${TIMESTAMP}.dump"

# Verify integrity
pg_restore --list "$BACKUP_DIR/alphastack_${TIMESTAMP}.dump" > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "BACKUP VERIFICATION FAILED: ${TIMESTAMP}" >&2
    exit 1
fi

# Encrypt (optional — requires GPG key)
# gpg --symmetric --cipher-algo AES256 --output "$BACKUP_DIR/alphastack_${TIMESTAMP}.dump.gpg" \
#     "$BACKUP_DIR/alphastack_${TIMESTAMP}.dump"
# rm "$BACKUP_DIR/alphastack_${TIMESTAMP}.dump"

# Upload to external storage (optional)
# aws s3 cp "$BACKUP_DIR/alphastack_${TIMESTAMP}.dump" "s3://alphastack-backups/"

# Cleanup old backups
find "$BACKUP_DIR" -name "*.dump" -mtime +${RETENTION_DAYS} -delete

echo "Backup completed: alphastack_${TIMESTAMP}.dump ($(du -h "$BACKUP_DIR/alphastack_${TIMESTAMP}.dump" | cut -f1))"
```

### 7.3 WAL Archiving (Phase 2+)

```sql
-- postgresql.conf
-- wal_level = replica
-- archive_mode = on
-- archive_command = 'cp %p /archive/wal/%f'
-- max_wal_senders = 3

-- Base backup command:
-- pg_basebackup -D /backup/base -Ft -z -P

-- Recovery:
-- 1. Restore base backup
-- 2. Copy WAL files to pg_wal/
-- 3. Create recovery.signal
-- 4. Set restore_command in postgresql.conf
-- 5. Start PostgreSQL — replays WALs to consistent state
```

### 7.4 Recovery Procedures

| Scenario | RTO | RPO | Procedure |
|----------|-----|-----|-----------|
| Accidental DELETE | <1 hour | <24 hours | Restore from latest `pg_dump` |
| Data corruption | <2 hours | <1 hour (WAL) | Restore base backup + replay WALs |
| Disk failure | <4 hours | <24 hours | Restore from external encrypted backup |
| Complete server loss | <8 hours | <24 hours | Restore on new server from external backup |
| Redis data loss | <5 minutes | None (ephemeral) | Rebuild from PostgreSQL + market feeds |
| MongoDB data loss | <1 hour | <24 hours | Restore from replica or backup |

### 7.5 Redis Backup

```conf
# redis.conf — Persistence settings
save 900 1
save 300 10
save 60 10000
appendonly yes
appendfsync everysec
```

**Recovery:** Redis data is largely ephemeral. On restart:
1. Redis loads from RDB snapshot + AOF replay
2. Critical state (positions, account balances) re-fetched from broker APIs
3. Market data repopulated from live feeds within seconds

### 7.6 Backup Verification Schedule

| Task | Frequency | Method |
|------|-----------|--------|
| Backup integrity check | Every backup | `pg_restore --list` |
| Restore test (staging) | Monthly | Full restore to test database |
| WAL replay test | Quarterly | Full recovery simulation |
| Off-site retrieval test | Quarterly | Download + restore from S3/Backblaze |
| RTO validation | Quarterly | Time the full recovery process |

---

## 8. Data Encryption at Rest

### 8.1 Encryption Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                  ENCRYPTION AT REST — LAYERS                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  LAYER 1: DISK ENCRYPTION (Full Volume)                         │
│  ├── LUKS (Linux Unified Key Setup)                             │
│  ├── Encrypts entire volume: OS, databases, logs, temp files    │
│  ├── Transparent to applications — no code changes              │
│  ├── Performance impact: <5% on modern CPUs (AES-NI)            │
│  └── Key stored in TPM or passphrase at boot                    │
│                                                                  │
│  LAYER 2: APPLICATION-LEVEL ENCRYPTION (Sensitive Fields)       │
│  ├── Broker credentials: AES-256-GCM                            │
│  ├── API keys: SHA-256 hash (original shown once)               │
│  ├── Passwords: Argon2id (memory-hard)                          │
│  ├── MFA secrets: AES-256-GCM                                   │
│  └── Session tokens: SHA-256 hash (original not stored)         │
│                                                                  │
│  LAYER 3: DATABASE-LEVEL ENCRYPTION                             │
│  ├── PostgreSQL: pgcrypto extension for column encryption       │
│  ├── TimescaleDB: inherits PostgreSQL encryption                │
│  ├── Redis: TLS in transit, AOF encrypted at rest (Phase 3+)    │
│  └── MongoDB: WiredTiger encryption at rest (Phase 3+)          │
│                                                                  │
│  LAYER 4: BACKUP ENCRYPTION                                     │
│  ├── GPG symmetric encryption (AES-256) for pg_dump files       │
│  ├── S3 server-side encryption (SSE-S3 or SSE-KMS)              │
│  └── Key rotation: quarterly for backup encryption keys         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 8.2 Credential Encryption (Application Layer)

```python
# Broker credentials are encrypted before database storage
# Using AES-256-GCM with user-derived key

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os, json

def encrypt_credentials(credentials: dict, user_key: bytes) -> tuple[str, str, str]:
    """Encrypt broker credentials for storage.
    
    Returns: (ciphertext_b64, iv_b64, tag_b64)
    """
    aesgcm = AESGCM(user_key)
    iv = os.urandom(12)  # 96-bit nonce for GCM
    plaintext = json.dumps(credentials).encode()
    
    ciphertext = aesgcm.encrypt(iv, plaintext, None)
    # GCM appends tag to ciphertext
    
    import base64
    return (
        base64.b64encode(ciphertext).decode(),
        base64.b64encode(iv).decode(),
        ""  # Tag is appended to ciphertext in GCM
    )

def decrypt_credentials(ciphertext_b64: str, iv_b64: str, user_key: bytes) -> dict:
    """Decrypt broker credentials from storage."""
    import base64
    aesgcm = AESGCM(user_key)
    ciphertext = base64.b64decode(ciphertext_b64)
    iv = base64.b64decode(iv_b64)
    
    plaintext = aesgcm.decrypt(iv, ciphertext, None)
    return json.loads(plaintext.decode())
```

### 8.3 Password Hashing

```python
# Argon2id for password hashing — memory-hard, resistant to GPU/ASIC attacks
from argon2 import PasswordHasher

ph = PasswordHasher(
    time_cost=3,        # Number of iterations
    memory_cost=65536,  # 64MB memory usage
    parallelism=4,      # Parallel threads
    hash_len=32,        # 256-bit output
    salt_len=16         # 128-bit salt
)

# Hash password
hash = ph.hash("user_password")

# Verify password
try:
    ph.verify(hash, "user_password")
except Exception:
    # Invalid password
    pass
```

### 8.4 Encryption Key Management

| Key Type | Storage | Rotation | Backup |
|----------|---------|----------|--------|
| Disk encryption (LUKS) | TPM or secure boot | On compromise | Recovery key in safe |
| Credential encryption key | Environment variable + KMS | Quarterly | Encrypted in KMS |
| Password hashing salt | Per-password (in hash) | N/A (unique per password) | N/A |
| Backup encryption key | GPG keyring | Quarterly | Offline secure storage |
| Redis AUTH password | Environment variable | Quarterly | In secrets manager |
| TLS certificates | File system + cert manager | Annual | CA backup |

### 8.5 Phase-Gated Encryption

| Phase | Disk Encryption | App-Level | DB-Level | Backup Encryption |
|-------|----------------|-----------|----------|-------------------|
| 1 ($7) | Optional (LUKS if self-hosted) | AES-256-GCM for credentials | No | GPG symmetric |
| 2 ($100) | LUKS on VPS | AES-256-GCM | No | GPG + S3 SSE |
| 3 ($1K) | LUKS mandatory | AES-256-GCM | pgcrypto for sensitive columns | GPG + S3 SSE-KMS |
| 4 ($10K+) | LUKS + HSM | AES-256-GCM + KMS | Full column encryption | KMS-managed keys |

---

## 9. Data Migration Strategy

### 9.1 Migration Tool: Alembic

All PostgreSQL/TimescaleDB schema changes are managed through **Alembic** with version-controlled migrations.

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
| **Idempotent** | Use `IF NOT EXISTS`, `IF EXISTS` where possible |
| **Reversible** | Every migration has a `downgrade()` for rollback |
| **Zero-downtime** | No `ALTER TABLE` that locks >1s on large tables |
| **Tested** | Run against staging copy of production data |
| **Ordered** | Sequential numbering with timestamps for merge conflict resolution |

### 9.3 Migration Categories

```python
# Category 1: Schema additions (safe, additive)
def upgrade():
    op.add_column('trades', sa.Column('grade', sa.Text(), nullable=True))
    op.create_index('idx_trades_grade', 'trades', ['grade'])

def downgrade():
    op.drop_index('idx_trades_grade')
    op.drop_column('trades', 'grade')


# Category 2: TimescaleDB operations (idempotent by nature)
def upgrade():
    op.execute("SELECT create_hypertable('ticks', 'time', if_not_exists => TRUE)")
    op.execute("ALTER TABLE ticks SET (timescaledb.compress, ...)")
    op.execute("SELECT add_compression_policy('ticks', INTERVAL '7 days')")


# Category 3: Data migrations (batch to avoid long locks)
def upgrade():
    op.execute("""
        UPDATE trades t SET confluence_score = s.confluence_score
        FROM signals s WHERE t.signal_id = s.id AND t.confluence_score IS NULL
        LIMIT 10000
    """)


# Category 4: Index creation (CONCURRENTLY to avoid locks)
def upgrade():
    op.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_new ON trades (new_col)")

def downgrade():
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_new")
```

### 9.4 Phase-Gated Migration Sequence

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
| `015` | 3 | ClickHouse analytics tables |

### 9.5 Cross-Store Migration Scenarios

| Scenario | From | To | Method |
|----------|------|----|--------|
| Config files → MongoDB | JSON/YAML files | MongoDB | Custom import script |
| SQLite → PostgreSQL | SQLite | PostgreSQL | `pgloader` or custom ETL |
| Single PG → PG + TimescaleDB | Vanilla PG | PG + TSDB extension | `CREATE EXTENSION timescaledb;` then hypertable conversion |
| PG + Redis → + Kafka | Redis Streams | Kafka | Dual-write during migration, cutover when stable |
| PG → PG + ClickHouse | PostgreSQL | ClickHouse | CDC pipeline or batch ETL |
| Local disk → S3 | Local files | S3 | `aws s3 sync` with lifecycle rules |

### 9.6 Migration Workflow

```
1. Developer creates migration file
   $ alembic revision --autogenerate -m "add_trade_grade_column"

2. Review generated migration
   - Verify SQL correctness
   - Add CONCURRENTLY for index creation on large tables
   - Add batch operations for data migrations

3. Test against staging
   $ alembic upgrade head  # on staging DB

4. Verify application compatibility
   - Run test suite
   - Check new columns have defaults
   - Verify no breaking changes

5. Deploy to production
   $ alembic upgrade head  # on production DB

6. Monitor
   - Check for lock contention
   - Verify migration completed
   - Run smoke tests
```

---

## 10. Storage Scaling from $7 to Institutional

### 10.1 Scaling Roadmap Overview

```
$7 ──────────────────────────────────────────────────────── $10K+ INSTITUTIONAL

Phase 1: FOUNDATION          Phase 2: GROWTH           Phase 3: PROFESSIONAL       Phase 4: INSTITUTIONAL
├─ Local machine             ├─ VPS ($5-10/mo)          ├─ Dedicated server         ├─ Multi-server cluster
├─ PostgreSQL + TimescaleDB  ├─ + PgBouncer             ├─ + Read replica           ├─ + ClickHouse OLAP
├─ Redis (single)            ├─ + WAL archiving         ├─ + Redis Cluster          ├─ + Kafka event bus
├─ Config files (JSON)       ├─ + MongoDB               ├─ + pgvector               ├─ + Kubernetes
├─ Local disk backups        ├─ + Backblaze B2          ├─ + S3 + lifecycle         ├─ + Multi-region
├─ pg_dump cron              ├─ + continuous backup     ├─ + Barman/pgBackRest      ├─ + Streaming replication
│                            │                           │                            │
│ 3 pairs, <10 trades/day    │ 10 pairs, <50 trades/day │ 28 pairs, <200 trades/day  │ 50+ pairs, institutional
│ ~6 GB storage              │ ~57 GB storage           │ ~216 GB storage            │ ~548 GB+ storage
│ $0/mo infra                │ ~$10-20/mo               │ ~$30-60/mo                 │ ~$200-500/mo
```

### 10.2 Phase 1: Foundation ($7 Capital)

**Infrastructure:**
- **Database:** PostgreSQL 16 + TimescaleDB extension (Docker)
- **Cache:** Redis 7 (Docker)
- **Config:** JSON/YAML files (no MongoDB yet)
- **Backup:** `pg_dump` cron to local disk
- **Encryption:** Application-level AES-256-GCM for credentials only
- **File storage:** Local disk

**What you get:**
- Full OHLCV pipeline from tick → 1d candles
- Trade execution with ACID guarantees
- Real-time signal distribution via Redis Pub/Sub
- Agent memory in Redis (short-term) + PostgreSQL (long-term)
- 7-day backup retention

**Limits:**
- Single point of failure (one machine)
- No horizontal scaling
- No analytics layer
- Manual backup verification

**Monthly cost:** $0 (run locally)

### 10.3 Phase 2: Growth ($100 Capital)

**Infrastructure upgrades:**
- **VPS:** Hetzner CX21 (2 CPU, 4GB RAM) — $7/mo
- **Connection pool:** PgBouncer (transaction mode)
- **Backup:** WAL archiving for point-in-time recovery
- **External backup:** Backblaze B2 ($1/mo)
- **MongoDB:** Single instance for flexible configs
- **Monitoring:** Basic Prometheus + Telegram alerts

**What changes:**
- 24/5 operation (no dependency on local machine)
- Continuous aggregates auto-compute all timeframes
- Compression policies reduce storage by 95%
- Agent memory tables with pgvector-ready schema
- 30-day backup retention with point-in-time recovery

**Monthly cost:** ~$10-20

### 10.4 Phase 3: Professional ($1K Capital)

**Infrastructure upgrades:**
- **Server:** Hetzner CX41 (4 CPU, 16GB RAM) — $20/mo
- **Read replica:** Separate server for analytics queries
- **Redis:** Dedicated instance (512MB)
- **pgvector:** Semantic search for trade episodes and lessons
- **Backup:** pgBackRest with hourly incremental + continuous WAL
- **S3:** Lifecycle rules for tiered file storage
- **Monitoring:** Grafana dashboards for DB health

**What changes:**
- Read-heavy analytics don't compete with write-heavy trading
- Vector similarity search: "find trades similar to current setup"
- Materialized views for strategy/agent performance
- 90-day backup retention, multi-region encrypted storage
- Connection pool monitoring and query performance tracking

**Monthly cost:** ~$30-60

### 10.5 Phase 4: Institutional ($10K+ Capital)

**Infrastructure upgrades:**
- **PostgreSQL cluster:** Primary + 2 read replicas
- **ClickHouse:** OLAP analytics for backtesting and reporting
- **Kafka:** Durable event bus replacing Redis Streams
- **Redis Cluster:** 3-master sharded cache
- **Kubernetes:** Container orchestration for all services
- **Multi-region:** S3 cross-region replication for backups
- **HSM:** Hardware security module for encryption keys
- **Streaming replication:** Continuous replication across regions

**What changes:**
- CDC pipeline: TimescaleDB → Kafka → ClickHouse
- Feature store for ML model training
- Data warehouse with star schema (dbt models)
- Full observability (Prometheus, Grafana, alerting)
- Automated data quality monitoring
- 1-year backup retention, compliance-grade audit trail

**Monthly cost:** ~$200-500

### 10.6 Scaling Decision Matrix

| Metric | Threshold | Action |
|--------|-----------|--------|
| PostgreSQL CPU >70% sustained | Phase 2→3 | Add read replica |
| PostgreSQL disk >80% | Any phase | Enable compression, archive old data |
| Tick write latency >10ms p99 | Phase 3→4 | Move to dedicated ingestion service |
| Redis memory >80% | Phase 2→3 | Increase maxmemory, review TTLs |
| Query latency >500ms for dashboards | Phase 3→4 | Add ClickHouse for analytics |
| Connection count >80% of max | Phase 2→3 | Tune PgBouncer, add connection pooling |
| Backup time >1 hour | Phase 3→4 | Switch to pgBackRest with incremental |
| Storage >80% of disk | Any phase | Add compression, offload to object storage |
| Need >10 concurrent analytical queries | Phase 3→4 | Add ClickHouse for OLAP |

### 10.7 Technology Stack Summary

| Layer | Phase 1 ($7) | Phase 2 ($100) | Phase 3 ($1K) | Phase 4 ($10K+) |
|-------|-------------|----------------|----------------|------------------|
| **OLTP Database** | PostgreSQL 16 | PostgreSQL 16 | PostgreSQL 16 | PostgreSQL 16 cluster |
| **Time-Series** | TimescaleDB ext. | TimescaleDB | TimescaleDB | TimescaleDB |
| **Analytics OLAP** | — | — | — | ClickHouse |
| **Cache / Hot State** | Redis 7 | Redis 7 | Redis 7 | Redis Cluster |
| **Event Bus** | Redis Pub/Sub + Streams | Redis Streams | Redis Streams | Kafka + Redis |
| **Vector DB (memory)** | PostgreSQL (pgvector-ready) | PostgreSQL | pgvector | pgvector + LanceDB |
| **Config Store** | JSON/YAML files | MongoDB | MongoDB | MongoDB |
| **Connection Pool** | — | PgBouncer | PgBouncer | PgBouncer |
| **Schema Migrations** | Alembic | Alembic | Alembic | Alembic |
| **Backup** | pg_dump (cron) | pg_dump + WAL | pgBackRest | Barman + streaming |
| **File Storage** | Local disk | Local + Backblaze B2 | S3 + lifecycle | S3 + CloudFront |
| **Monitoring** | print() + Telegram | Prometheus + Telegram | Prometheus + Grafana | Full observability |
| **Deployment** | Docker Compose | Docker Compose | Docker Compose | Kubernetes |

### 10.8 What Scales vs What Doesn't

| Component | Scales? | Notes |
|-----------|---------|-------|
| PostgreSQL schema | ✅ Yes | Same tables through all phases; add columns via migrations |
| TimescaleDB hypertables | ✅ Yes | Automatic partitioning handles growth |
| Redis key patterns | ✅ Yes | Same patterns; scale Redis itself |
| Connection pooling | ✅ Yes | PgBouncer config adjusts; same architecture |
| Backup strategy | ✅ Yes | Same principle (pg_dump → WAL → Barman); just more automated |
| Agent memory schema | ✅ Yes | pgvector scales to millions of embeddings |
| Single Redis instance | ❌ Phase 4 | Replace with Redis Cluster |
| Redis Streams | ❌ Phase 4 | Replace with Kafka for durability |
| Config files | ❌ Phase 2 | Replace with MongoDB for schema flexibility |
| Local disk backups | ❌ Phase 2 | Move to external encrypted storage |
| Single server | ❌ Phase 3 | Add read replica; Phase 4: multi-server |

### 10.9 Anti-Patterns to Avoid

| Anti-Pattern | Why It's Bad | What to Do Instead |
|--------------|-------------|-------------------|
| Over-engineering at $7 | Kafka for 10 trades/day is absurd | Start with Redis Streams |
| Skipping compression at Phase 2 | Storage grows linearly; costs balloon | Enable TimescaleDB compression early |
| No backup verification | Backups you haven't tested are not backups | Monthly restore test to staging |
| Storing credentials in plaintext | Single breach exposes all accounts | AES-256-GCM from day 1 |
| Ignoring connection pooling | Each agent opens/closes connections; DB thrashes | Add PgBouncer at Phase 2 |
| Premature sharding | Sharding 3 pairs adds complexity for zero benefit | Shard only when single node can't handle it |
| No retention policies | Storage grows forever; queries slow down | Set retention from Phase 1 |
| Dual-write without CDC | Two databases diverge silently | Use CDC or single source of truth |

---

## Appendix A: Complete Entity Relationship Diagram

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
                     │ agent_id     │     │ context_     │
                     │ signal_type  │     │ embedding    │
                     │ confidence   │     │ signals_     │
                     │ ...          │     │ snapshot     │
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

MongoDB Collections:
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ strategy_configs │  │ research_notes   │  │ agent_configs    │
│                  │  │                  │  │                  │
│ strategy_id      │  │ title            │  │ agent_id         │
│ parameters{}     │  │ hypothesis       │  │ model{}          │
│ risk_limits{}    │  │ results{}        │  │ indicators{}     │
│ symbols[]        │  │ tags[]           │  │ signals{}        │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

## Appendix B: Connection Pool Configuration

```ini
# pgbouncer.ini
[databases]
alphastack = host=127.0.0.1 port=5432 dbname=alphastack

[pgbouncer]
listen_port = 6432
listen_addr = 127.0.0.1
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt

pool_mode = transaction
max_client_conn = 200
default_pool_size = 20
min_pool_size = 5
reserve_pool_size = 5
reserve_pool_timeout = 3
server_idle_timeout = 300
client_idle_timeout = 600
```

## Appendix C: Security Checklist

- [ ] PostgreSQL: `pg_hba.conf` restricts to localhost only
- [ ] PostgreSQL: SSL required for all connections
- [ ] PostgreSQL: Separate users for app (read/write) and analytics (read-only)
- [ ] Redis: `bind 127.0.0.1` (no external access)
- [ ] Redis: `requirepass` set
- [ ] Credentials: Encrypted at rest (AES-256-GCM) from Phase 1
- [ ] Credentials: Never in logs, config files, or environment variables in plaintext
- [ ] Backups: Encrypted before upload to external storage
- [ ] Audit: All schema changes logged to `system_events`
- [ ] Access: Principle of least privilege for all database users
- [ ] Monitoring: Alert on failed login attempts
- [ ] Rotation: API keys and encryption keys rotated quarterly
- [ ] Disk: LUKS encryption enabled on all production servers
- [ ] TLS: All internal service communication encrypted in transit

## Appendix D: Query Performance Monitoring

```sql
-- Enable pg_stat_statements
-- postgresql.conf:
-- shared_preload_libraries = 'pg_stat_statements'
-- pg_stat_statements.track = all

-- Find slow queries
SELECT query, calls,
    round(total_exec_time::numeric, 2) AS total_ms,
    round(mean_exec_time::numeric, 2) AS avg_ms,
    rows
FROM pg_stat_statements
WHERE mean_exec_time > 100
ORDER BY total_exec_time DESC LIMIT 20;

-- Find missing indexes
SELECT schemaname, relname, seq_scan, seq_tup_read, idx_scan, n_live_tup
FROM pg_stat_user_tables
WHERE seq_scan > 100 AND n_live_tup > 10000
ORDER BY seq_tup_read DESC;

-- Check index usage
SELECT indexrelname, idx_scan, idx_tup_read, idx_tup_fetch,
    pg_size_pretty(pg_relation_size(indexrelid)) AS size
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;
```

---

*This architecture defines the complete data storage layer for Alpha Stack. It starts at $0/month with a single-machine PostgreSQL + Redis setup, and scales to institutional-grade distributed storage without rewriting the foundation. Every table, index, policy, and procedure is designed to work at Phase 1 and still be correct at Phase 4.*

*The key insight: store data once, in the right store, with the right retention. Hot data in Redis for speed, warm data in TimescaleDB for queries, cold data compressed for cost, archived data in object storage for compliance. The tiered approach means you never pay for speed you don't need and never lose data you might.*
