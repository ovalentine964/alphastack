# Review 7: Data Flow Architecture Assessment

> **Reviewer:** Data Flow Architecture Review Agent
> **Date:** 2026-07-11
> **Scope:** Data flow completeness, bottlenecks, storage design, missing sources, caching, and risk assessment
> **Documents Reviewed:** architecture_data_storage.md, architecture_system.md, architecture_trading_engine.md, architecture_trade_monitoring.md, architecture_broker_routing.md

---

## Executive Summary

The Alpha Stack data architecture is **impressively comprehensive** for a system designed to scale from $7 to institutional. The tiered storage model (Redis → TimescaleDB → Compressed → Archive) is well-designed, and the event-driven flow from market data through 16 strategy modules to broker execution is clearly articulated. However, several critical gaps exist in the data pipeline that could cause real-world failures.

**Overall Rating: 7.5/10** — Strong foundation with specific gaps that need addressing before live trading.

| Dimension | Score | Status |
|-----------|-------|--------|
| Data flow completeness | 7/10 | ⚠️ Gaps in reconciliation and failover paths |
| Bottleneck analysis | 8/10 | ✅ Well-identified with scaling triggers |
| Storage design appropriateness | 9/10 | ✅ Excellent tiered model |
| Missing data sources | 6/10 | ⚠️ Several critical sources absent |
| Caching strategy | 8/10 | ✅ Sound with minor gaps |
| Data risks | 6/10 | ⚠️ Significant risks unmitigated |

---

## 1. Data Flow Completeness: Market Data → Storage → Agents → Execution

### 1.1 End-to-End Flow Map

```
SOURCES          INGESTION       PROCESSING       DECISION        EXECUTION        FEEDBACK
─────────        ──────────      ──────────       ──────────      ──────────       ──────────
MT5 ticks   ──→  Tick Collector ──→ TimescaleDB ──→ S1-S9 Agents ──→ S10 Confluence ──→ S11-S13
CCXT feeds  ──→  WS Collector  ──→ Redis cache  ──→ AlphaStack Pipeline ──→ Risk Governor ──→ Broker
News APIs   ──→  News Aggregator──→ FinBERT     ──→ News Agent   ──→ Execution Agent──→ Fill
Econ Cal    ──→  Calendar Fetch ──→ PostgreSQL  ──→ S1 Fundamental──→ Order Manager ──→ S14-S16
On-chain    ──→  Chain Monitor ──→ TimescaleDB  ──→ S6 Liquidity ──→ TMS Monitor   ──→ Journal
```

### 1.2 Findings

| # | Finding | Severity | Detail |
|---|---------|----------|--------|
| F1.1 | **Continuous aggregate cascade is well-designed** | ✅ Positive | The 1m → 5m → 15m → 1h → 4h → 1d cascade in TimescaleDB is correct and ensures consistent aggregation. Each level uses the previous as source. |
| F1.2 | **candle_1m source mismatch** | 🔴 Critical | `candle_1m` aggregates from `ticks` table using `bid` price, but `market_data` table stores OHLCV from a different source. The 5m+ aggregates reference `market_data WHERE timeframe = '1m'`, but `candle_1m` writes to a *separate* materialized view, not `market_data`. **Data will diverge.** |
| F1.3 | **No explicit tick-to-candle write path** | 🟡 Medium | The `candle_1m` continuous aggregate computes OHLCV from ticks, but there's no documented mechanism to populate the `market_data` table from `candle_1m`. The 5m+ aggregates assume `market_data` has 1m rows. |
| F1.4 | **Redis Pub/Sub → Agent consumption is underspecified** | 🟡 Medium | The architecture specifies Redis Pub/Sub channels (e.g., `tick:{symbol}`, `signal:{symbol}`) but the agent consumption model (polling vs. blocking subscribe vs. Streams consumer group) is not defined. Pub/Sub is fire-and-forget — if an agent misses a message, it's gone. |
| F1.5 | **Signal-to-trade provenance chain is complete** | ✅ Positive | The `agent_signals` table with `contributed` and `trade_id` fields creates a complete provenance chain from signal generation through confluence scoring to trade execution. |
| F1.6 | **Execution feedback loop is well-defined** | ✅ Positive | S14 (Trade Management) and S15 (Exit) receive candle-close events and can modify positions. S16 (Journal) receives post-trade data. The loop from execution → learning → strategy adaptation is architecturally sound. |
| F1.7 | **Missing: Order book data → agent pipeline** | 🟡 Medium | `orderbook_snapshots` table exists with JSONB bids/asks, but no agent explicitly consumes order book data for decision-making. S6 (Liquidity) mentions order book depth but the data path from `orderbook_snapshots` → S6 is not wired. |

### 1.3 Critical Fix Required

**F1.2 — candle_1m / market_data divergence:**

The continuous aggregate `candle_1m` creates a *separate* materialized view. The `market_data` hypertable is a *base table* that must be populated independently. The 5m+ aggregates (`candle_5m`, etc.) query `market_data WHERE timeframe = '1m'` — but if `candle_1m` data lives in a materialized view and not in `market_data`, the higher timeframes will have no data.

**Recommendation:** Either:
- (A) Make `candle_1m` write into `market_data` via a trigger or upsert policy, OR
- (B) Rewrite `candle_5m`+ to aggregate from `candle_1m` instead of `market_data`, OR
- (C) Eliminate `candle_1m` as a separate view and populate `market_data` (timeframe='1m') directly from ticks via a continuous aggregate.

Option (C) is cleanest: one source of truth (`market_data`) for all timeframes.

---

## 2. Data Bottlenecks

### 2.1 Identified Bottlenecks

| # | Bottleneck | Impact | Severity | Mitigation in Architecture |
|---|-----------|--------|----------|---------------------------|
| B2.1 | **Single Redis instance for all Pub/Sub + Streams + Cache** | At 100 ticks/sec across 28 pairs, Redis becomes the single contention point. Pub/Sub is single-threaded. | 🔴 High | Scaling path exists (Redis Cluster at Phase 4) but no intermediate sharding strategy. |
| B2.2 | **LLM inference in critical path (S1, S2, S7, S10)** | Steps requiring LLM reasoning (DeepSeek/Qwen) add 200-2000ms per call. With 4+ LLM calls in the signal chain, total latency can exceed 5 seconds. | 🔴 High | No async/pipeline optimization documented. Architecture says "50-200ms" for AlphaStack pipeline but LLM calls alone could be 10× that. |
| B2.3 | **TimescaleDB write amplification** | Every tick writes to `ticks` hypertable, then triggers continuous aggregate refresh for `candle_1m`. At 100 ticks/sec, that's 100 writes/sec + aggregate refresh overhead. | 🟡 Medium | Chunk interval (1 day) and compression (after 7 days) are appropriate. Batch writes could help. |
| B2.4 | **PostgreSQL SERIALIZABLE isolation on orders** | SERIALIZABLE isolation on `orders` table will cause serialization failures under concurrent agent writes. | 🟡 Medium | Architecture specifies SERIALIZABLE for ACID on money. This is correct for safety but will cause retries under load. |
| B2.5 | **MongoDB adds operational overhead with no clear Phase 1 value** | Architecture notes MongoDB is optional at Phase 1 (JSON files suffice) but includes it in the tech stack. Adds a third database to manage. | 🟢 Low | Correctly phase-gated. Not a bottleneck if deferred. |

### 2.2 Latency Budget Analysis

The architecture claims a critical path of ~125-425ms. Let's validate:

```
Component                    Claimed     Realistic    Source
─────────────────────────    ────────    ──────────   ──────
Tick ingestion               5ms         2-10ms       Redis write
S1 Fundamental (LLM)         ~100ms      500-2000ms   LLM API call
S2 Bias (HMM + fusion)       ~50ms       20-80ms      In-process
S3-S8 Analysis               ~500ms      100-500ms    Indicator calc
S9 Candlestick               ~50ms       10-50ms      Pattern match
S10 Confluence               ~100ms      20-100ms     Score calc
Risk Governor                ~10ms       5-20ms       Rule checks
S11-S13 Execution prep       ~50ms       10-50ms      Calc only
Broker execution             ~50-200ms   50-500ms     Network + broker
─────────────────────────────────────────────────────
TOTAL (no LLM)               ~775ms      215-860ms
TOTAL (with LLM)             ~1775ms     1215-4860ms  ← PROBLEM
```

**Critical Issue:** The "50-200ms" claim for the AlphaStack pipeline assumes all steps are in-process calculations. If S1, S2, or S10 use LLM inference, the actual latency is **5-25× higher than claimed**.

**Recommendation:**
1. Document which steps use LLM vs. pure computation
2. Implement LLM result caching (same news article → same sentiment for N minutes)
3. Run LLM-dependent steps asynchronously, not in the critical path
4. Pre-compute fundamental/sentiment bias on a schedule (every 15min), not per-tick

---

## 3. Storage Design Appropriateness

### 3.1 Assessment by Data Type

| Data Type | Storage Choice | Appropriateness | Notes |
|-----------|---------------|-----------------|-------|
| **Tick data** | TimescaleDB hypertable (1-day chunks) | ✅ Excellent | Auto-partitioning, compression after 7 days, 95%+ reduction. |
| **OHLCV candles** | TimescaleDB hypertable (7-day chunks) | ✅ Excellent | Continuous aggregates handle multi-timeframe. Compression after 30 days. |
| **Order book snapshots** | TimescaleDB with JSONB | ⚠️ Adequate | JSONB for bids/asks is flexible but harder to query analytically. For top-20 levels, this works. For full book, consider dedicated store. |
| **Orders/Trades** | PostgreSQL (append-only) | ✅ Excellent | ACID guarantees, referential integrity, immutable audit trail. |
| **Agent signals** | TimescaleDB hypertable | ✅ Excellent | Time-series nature, compression-friendly, GIN index on data column. |
| **Strategy configs** | MongoDB (Phase 2+) / JSON files (Phase 1) | ✅ Good | Schema-free for evolving strategy parameters. Correctly phase-gated. |
| **Agent memory** | PostgreSQL + pgvector (Phase 3+) | ✅ Good | Vector similarity search for trade episode matching. Schema-ready from Phase 1. |
| **Screenshots** | Object storage (S3/Backblaze) | ✅ Excellent | Correct separation of metadata (PostgreSQL) from files (S3). |
| **News events** | TimescaleDB hypertable | ⚠️ Adequate | GIN index on `symbols[]` array is correct. However, full-text search on `headline`/`summary` would benefit from Elasticsearch or PostgreSQL `tsvector`. |
| **Redis hot cache** | Redis KV + Pub/Sub + Streams | ✅ Good | Three usage patterns correctly separated. TTL-based expiry is appropriate. |

### 3.2 Storage Design Strengths

1. **Single database engine (PostgreSQL + TimescaleDB extension)** — Eliminates cross-database synchronization issues. This is the right call.
2. **Compression policies are aggressive and correct** — 95%+ reduction on ticks after 7 days, 90%+ on candles after 30 days.
3. **Retention matrix is comprehensive** — Every data type has explicit Hot/Warm/Cold/Archive tiers.
4. **Continuous aggregates are correctly cascaded** — 1m → 5m → 15m → 1h → 4h → 1d with proper offset policies.

### 3.3 Storage Design Gaps

| # | Gap | Recommendation |
|---|-----|----------------|
| G3.1 | No `trade_lifecycle_events` table in storage architecture | The monitoring architecture references this table but it's not in `architecture_data_storage.md`. Add it. |
| G3.2 | `equity_curve` table missing from storage architecture | Referenced in trade monitoring but not defined in data storage. This is a TimescaleDB hypertable that should be documented. |
| G3.3 | No schema for `performance_snapshots` in data storage | The monitoring doc defines it, but it should be in the canonical storage document. |
| G3.4 | `reconciliation_log` table not in storage architecture | Critical for broker reconciliation but only defined in monitoring doc. |

**Recommendation:** Consolidate all table definitions into `architecture_data_storage.md` as the single source of truth. The monitoring and trading engine documents should reference it, not duplicate definitions.

---

## 4. Missing Data Sources

### 4.1 Critical Missing Sources

| # | Missing Source | Impact | Severity |
|---|---------------|--------|----------|
| D4.1 | **Historical tick data backfill** | No mechanism to backfill tick data when the system starts or after downtime. The `candle_1m` aggregate needs historical ticks to work. | 🔴 High |
| D4.2 | **Cross-exchange price normalization** | MT5 and CCXT use different symbol formats, pip values, and price conventions. The `normalizer.py` module is mentioned but no normalization schema is defined. | 🔴 High |
| D4.3 | **Funding rate feed for crypto** | `funding_rates` table exists but no collector is documented. Funding rates are critical for crypto perpetual futures positioning. | 🟡 Medium |
| D4.4 | **Options/GEX data for S5 (S/R)** | S5 mentions "Options GEX levels, dark pool activity zones" but no data source or storage is defined for this. | 🟡 Medium |
| D4.5 | **Whale wallet monitoring for S6** | S6 mentions "whale wallet movements" and "on-chain liquidation levels" but no blockchain data collector is defined. | 🟡 Medium |
| D4.6 | **Social media sentiment** | S1 mentions "Reddit" as a sentiment source (sentiment_agent_v1 config in MongoDB) but no social media collector is documented. | 🟡 Medium |
| D4.7 | **Latency telemetry from broker routing** | The broker routing architecture tracks latency (p50/p99) but this data has no storage destination in the data architecture. | 🟢 Low |

### 4.2 Data Source Priority Matrix

| Source | Priority | Effort | Phase |
|--------|----------|--------|-------|
| Historical backfill | P0 | Medium | Phase 1 |
| Cross-source normalization | P0 | Medium | Phase 1 |
| Funding rate collector | P1 | Low | Phase 2 |
| Social media sentiment | P2 | Medium | Phase 2 |
| On-chain data (whale, liquidation) | P2 | High | Phase 2-3 |
| Options/GEX data | P3 | High | Phase 3 |
| Latency telemetry storage | P3 | Low | Phase 2 |

---

## 5. Caching Strategy Assessment

### 5.1 Cache Layer Design

The architecture defines a 3-layer cache:

```
L0: Process memory  → Current tick, current candle, agent state (overwritten on each update)
L1: Redis KV        → Hot market data with TTL-based expiry
L2: TimescaleDB     → Warm data, append-only, no invalidation needed
L3: ClickHouse      → Cold analytics, CDC from TimescaleDB (Phase 4)
```

### 5.2 Cache Assessment

| # | Aspect | Assessment | Detail |
|---|--------|------------|--------|
| C5.1 | **TTL-based expiry is correct for market data** | ✅ Sound | Market data is naturally time-bound. Stale data should expire. |
| C5.2 | **Redis Pub/Sub for real-time distribution** | ⚠️ Risky | Pub/Sub is fire-and-forget. If a consumer is temporarily disconnected, messages are lost. **Use Redis Streams with consumer groups for critical signals.** |
| C5.3 | **Redis Streams for durable event log** | ✅ Sound | `stream:signals`, `stream:orders`, `stream:system` with trim policies. This is the right pattern for event sourcing. |
| C5.4 | **Agent memory in Redis (short-term) + PostgreSQL (long-term)** | ✅ Sound | Dual-layer with decay mechanism. Redis for session-scoped observations, PostgreSQL for persistent memories. |
| C5.5 | **Missing: Cache warming strategy** | 🟡 Gap | When the system restarts, Redis is cold. No documented strategy for warming the cache from TimescaleDB before the system begins processing. |
| C5.6 | **Missing: Cache coherence for positions** | 🟡 Gap | Positions exist in Redis (`position:{acct}:{sym}`) AND PostgreSQL (`positions` table). No documented mechanism for keeping them in sync during writes. |

### 5.3 Specific Cache Concerns

**Redis Pub/Sub vs. Streams for signal distribution:**

The architecture uses Pub/Sub for `tick:{symbol}`, `signal:{symbol}`, `order:{account}` channels. Pub/Sub has a critical limitation: **if no consumer is subscribed when a message is published, the message is lost.**

For trading signals, this is unacceptable. If the Risk Agent briefly disconnects and reconnects, it could miss a signal that should have been rejected.

**Recommendation:** Use Redis Streams (which the architecture already defines) for all critical signal paths. Reserve Pub/Sub for truly ephemeral notifications (e.g., dashboard price updates).

**Cache warming on restart:**

After a system restart:
1. Redis is empty — no position state, no recent signals, no agent memory
2. The system needs to rebuild state from PostgreSQL + broker APIs
3. During this window, the system could make decisions with incomplete context

**Recommendation:** Implement a startup sequence:
1. Load positions from PostgreSQL
2. Sync with broker API to get current state
3. Replay last N messages from Redis Streams
4. Warm indicator caches from TimescaleDB
5. Only then begin processing live data

---

## 6. Data Risks

### 6.1 Risk Matrix

| # | Risk | Likelihood | Impact | Severity | Mitigation Status |
|---|------|-----------|--------|----------|-------------------|
| R6.1 | **Tick data loss during Redis Pub/Sub** | High | High (missed signals) | 🔴 Critical | **Not mitigated** — Pub/Sub is fire-and-forget |
| R6.2 | **Clock skew between components** | Medium | High (wrong candle boundaries) | 🔴 High | **Not addressed** — No NTP or clock sync strategy |
| R6.3 | **Data source disagreement** | High | Medium (conflicting signals) | 🟡 Medium | **Partially mitigated** — cross-source validation module exists but no consensus algorithm defined |
| R6.4 | **Continuous aggregate lag** | Medium | Medium (stale candles) | 🟡 Medium | **Mitigated** — offset policies ensure aggregates don't compute on incomplete data |
| R6.5 | **Redis memory exhaustion** | Low | High (system halt) | 🟡 Medium | **Mitigated** — `allkeys-lru` eviction policy + 256MB cap |
| R6.6 | **TimescaleDB chunk explosion** | Low | Medium (slow queries) | 🟡 Medium | **Mitigated** — appropriate chunk intervals (1d for ticks, 7d for candles) |
| R6.7 | **Credential compromise via data leak** | Low | Critical (account loss) | 🔴 High | **Well mitigated** — AES-256-GCM encryption, Argon2id hashing, LUKS disk encryption |
| R6.8 | **Silent data corruption in compressed chunks** | Very Low | High (wrong backtest results) | 🟡 Medium | **Not addressed** — No checksumming strategy for compressed TimescaleDB chunks |
| R6.9 | **Reconciliation gap between internal and broker state** | Medium | Critical (phantom positions) | 🔴 Critical | **Well mitigated** — TMS reconciliation engine runs every 5 minutes with full position comparison |
| R6.10 | **Single point of failure: Redis** | Medium (Phase 1-3) | Critical (full system halt) | 🔴 High | **Partially mitigated** — AOF + RDB persistence, but no HA until Phase 4 (Redis Cluster) |

### 6.2 Critical Risk Deep-Dives

#### R6.1 — Tick Data Loss via Pub/Sub

**Scenario:** Risk Agent subscribes to `tick:EUR/USD` Pub/Sub channel. Network blip causes 2-second disconnect. During that window, a tick with extreme spread (black swan indicator) is published. The agent misses it and doesn't trigger the black swan protocol.

**Impact:** Positions remain open during a black swan event. Potentially catastrophic loss.

**Mitigation:** Replace Pub/Sub with Redis Streams for all safety-critical channels:
```python
# Instead of:
await redis.publish(f"tick:{symbol}", tick_data)  # Fire and forget

# Use:
await redis.xadd(f"stream:tick:{symbol}", tick_data, maxlen=10000)  # Durable

# Consumer reads from last known position:
messages = redis.xread({f"stream:tick:{symbol}": last_id}, count=100, block=100)
```

#### R6.2 — Clock Skew

**Scenario:** The VPS clock drifts by 2 seconds. Candle boundaries shift. A signal that should align with the London open (08:00:00 UTC) is computed at 08:00:02 UTC. Session analysis (S3) classifies the session incorrectly.

**Impact:** Session-specific parameters (position size multipliers, stop distances) are wrong. Not catastrophic but introduces systematic error.

**Mitigation:** Add to infrastructure layer:
```bash
# NTP configuration
timedatectl set-ntp yes
chronyc tracking  # Verify sync
# Alert if offset > 100ms
```

#### R6.10 — Redis Single Point of Failure

**Scenario:** Redis crashes at 14:30 UTC (high-liquidity London session). All Pub/Sub channels stop. All Stream consumers halt. Position state in Redis is lost. The system cannot process signals, manage positions, or distribute events.

**Impact:** Open positions have no active management. Stops/TPs at the broker still execute, but the system cannot respond to market conditions.

**Mitigation (Phase 1-3):**
1. Redis AOF persistence (`appendfsync everysec`) limits data loss to ~1 second
2. Automatic Redis restart via systemd/Docker restart policy
3. On restart: replay AOF, rebuild state from PostgreSQL + broker API
4. **Critical addition:** Broker-side stops/TPs must always be active (not just system-side). Architecture correctly notes this — "Stops/TPs still active at broker."

---

## 7. Cross-Document Consistency Issues

| # | Issue | Documents | Severity |
|---|-------|-----------|----------|
| X7.1 | `trades` table defined differently in data_storage vs. trade_monitoring | `architecture_data_storage.md` (section 2.3) vs. `architecture_trade_monitoring.md` (section 1.4) | 🟡 Medium |
| X7.2 | `agent_signals` table only in monitoring doc, not in data storage | `architecture_trade_monitoring.md` defines it; `architecture_data_storage.md` does not | 🟡 Medium |
| X7.3 | `position_snapshots` in data_storage has different columns than monitoring | Data storage: `drawdown_pct`. Monitoring: `unrealized_pnl_r`, `mae_pips`, `mfe_pips` | 🟡 Medium |
| X7.4 | Redis stream definitions differ between system architecture and data storage | System arch: `stream:ticks:{sym}`. Data storage: `stream:ticks:{sym}` (consistent) but retention differs | 🟢 Low |
| X7.5 | `architecture_data.md` and `architecture_database.md` are referenced but don't exist | `architecture_data_storage.md` header lists them as dependencies | 🟡 Medium |

**Recommendation:** Establish `architecture_data_storage.md` as the canonical source for all table schemas. Other documents should reference it, not redefine schemas.

---

## 8. Recommendations Summary

### 8.1 Must-Fix Before Live Trading (P0)

| # | Issue | Action | Effort |
|---|-------|--------|--------|
| FIX-1 | candle_1m / market_data divergence | Consolidate into single `market_data` table as source of truth | 2 hours |
| FIX-2 | Replace Pub/Sub with Streams for critical signals | Use `XADD`/`XREAD` for tick, signal, order channels | 4 hours |
| FIX-3 | Document and implement cache warming on restart | Add startup sequence to load state from PostgreSQL + broker | 4 hours |
| FIX-4 | NTP configuration | Add clock sync to infrastructure checklist | 30 minutes |
| FIX-5 | Consolidate table schemas into single source of truth | Merge monitoring table defs into data_storage document | 2 hours |

### 8.2 Should-Fix Before Scaling (P1)

| # | Issue | Action | Effort |
|---|-------|--------|--------|
| FIX-6 | LLM latency in critical path | Move LLM-dependent steps to async pre-computation | 1 week |
| FIX-7 | Historical tick backfill mechanism | Implement MT5/CCXT historical data downloader | 3 days |
| FIX-8 | Cross-source symbol normalization | Define canonical symbol format and normalization rules | 2 days |
| FIX-9 | Funding rate collector | Implement CCXT-based funding rate ingestion | 1 day |
| FIX-10 | Cache coherence for positions | Implement write-through pattern (write Redis + PostgreSQL atomically) | 2 days |

### 8.3 Nice-to-Have (P2)

| # | Issue | Action | Effort |
|---|-------|--------|--------|
| FIX-11 | Full-text search on news headlines | Add PostgreSQL `tsvector` index or Elasticsearch | 1 day |
| FIX-12 | Compressed chunk checksumming | Enable TimescaleDB integrity checks | 1 hour |
| FIX-13 | Social media data collector | Implement Reddit/Twitter sentiment ingestion | 1 week |
| FIX-14 | On-chain data pipeline | Implement blockchain event monitoring for crypto | 2 weeks |

---

## 9. Architecture Strengths (What's Done Well)

1. **Tiered storage model is excellent** — Hot (Redis) → Warm (TimescaleDB uncompressed) → Cold (compressed) → Archive (S3) with explicit retention policies for every data type.

2. **Continuous aggregate cascade is correct** — 1m → 5m → 15m → 1h → 4h → 1d with proper offset policies prevents computing on incomplete data.

3. **Compression strategy is aggressive and appropriate** — 95%+ reduction on ticks after 7 days. This means 1 year of tick data fits in ~5GB instead of ~100GB.

4. **Event-driven architecture is sound** — Redis Streams for durable event sourcing, Pub/Sub for ephemeral notifications. The distinction is correct (though Pub/Sub should be replaced for critical paths).

5. **Trade provenance chain is complete** — From signal generation (agent_signals) through confluence scoring to execution (trades) to journal (S16), every step is recorded with full context.

6. **Encryption at rest is comprehensive** — 4 layers: disk (LUKS), application (AES-256-GCM), database (pgcrypto), backup (GPG). Credentials are never stored in plaintext.

7. **Phase-gated scaling is practical** — The $7 → $100 → $1K → $10K+ progression avoids premature complexity while maintaining architectural consistency.

8. **Backup strategy includes verification** — Monthly restore tests, quarterly WAL replay tests, quarterly RTO validation. "Backups you haven't tested are not backups."

9. **Reconciliation engine is robust** — 5-minute reconciliation cycle comparing internal positions with broker records, detecting phantom trades, missed fills, and equity drift.

10. **Agent memory decay model is sophisticated** — Importance-based decay with access-count promotion. Memories that aren't accessed lose importance; frequently-accessed memories gain it.

---

## 10. Conclusion

The Alpha Stack data architecture is **well above average** for a system at this stage of design. The storage layer is production-grade, the tiered model is correct, and the event-driven flow is architecturally sound.

The primary risks are:
1. **Pub/Sub message loss** for safety-critical signals (must fix before live trading)
2. **candle_1m / market_data data divergence** (must fix before backtesting)
3. **LLM latency in the critical path** (must address before expecting sub-second signal generation)
4. **Cross-document schema inconsistency** (should consolidate before team scaling)

The system is **ready for paper trading** after addressing the P0 fixes. It is **ready for live trading** after addressing P0 + P1 fixes and validating the end-to-end latency budget with real broker connections.

---

*Review completed by Data Flow Architecture Review Agent — 2026-07-11*
