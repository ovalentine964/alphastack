# Alpha Stack — Performance Architecture Review

> **Reviewer:** Performance & Latency Agent  
> **Date:** 2026-07-11  
> **Scope:** Real-time trading performance, memory management, database optimization, WebSocket, connection pooling, bottleneck analysis  
> **Severity Scale:** 🔴 Critical · 🟠 High · 🟡 Medium · 🟢 Low · ⚪ Informational

---

## Executive Summary

The Alpha Stack architecture is **well-designed for progressive scaling** but contains several **critical performance gaps** that will prevent the <5s tick-to-order target from being reliably achieved, especially under load. The biggest risks are: (1) LLM inference latency in the AlphaStack pipeline, (2) missing memory management for 24/7 operation, (3) insufficient WebSocket performance specifications, and (4) absent connection pooling strategy for broker connectors.

**Overall Verdict:** The architecture is **achievable for Phase 1–2** (latency-tolerant, single-pair trading) but requires **significant performance hardening** for Phase 3+ real-time multi-pair operation.

---

## 1. Is the <5s Tick-to-Order Target Achievable?

### 1.1 Critical Path Analysis (From Architecture)

The system architecture states the critical path as:

```
Market Data → AlphaStack Pipeline (Steps 1-16) → Risk Agent → Execution Agent → Order Manager → Broker
  ~5ms           ~50-200ms (LLM steps)       ~5ms           ~5ms            ~10ms        ~50-200ms

Total: ~125-425ms (forex), ~200-600ms (crypto with exchange latency)
```

### 1.2 Verdict: 🟠 **Achievable but Fragile — Not Guaranteed**

| Factor | Estimated Latency | Risk Level | Notes |
|--------|-------------------|------------|-------|
| Tick ingestion (WS/MT5) | 1–5ms | 🟢 Low | Well-understood, fast |
| AlphaStack Steps 1–4 (Context) | 10–30ms | 🟢 Low | Mostly lookup/calculation |
| AlphaStack Steps 5–8 (Structure) | 20–80ms | 🟡 Medium | Indicator calculations, S/R detection |
| AlphaStack Steps 9–12 (Entry) | 20–50ms | 🟢 Low | Pattern matching, math |
| **AlphaStack Steps involving LLM** | **200–2000ms** | 🔴 **Critical** | DeepSeek/Qwen API calls are unpredictable |
| Risk Agent validation | 5–15ms | 🟢 Low | In-memory checks |
| Execution Agent | 5–10ms | 🟢 Low | Routing logic |
| Order Manager → Broker | 50–500ms | 🟠 High | Depends on broker; MT5 via ZMQ ~50ms, CCXT REST ~200-500ms |
| **Total (no LLM)** | **~115–675ms** | 🟢 Low | Achievable |
| **Total (with LLM)** | **~315–2675ms** | 🟠 High | Still <5s but with no margin |
| **Total (worst case, API timeout)** | **~10s+** | 🔴 **Critical** | LLM API timeouts can blow the target |

### 1.3 Specific Risks

**🔴 RISK 1: LLM Inference is the Uncontrollable Variable**
- Steps like "Fundamental Intelligence" (Step 1) and "News Sentiment" likely call LLM APIs (DeepSeek, Qwen).
- External API latency is **not deterministic** — p99 can be 2-10x the median.
- API rate limits (429s) and transient failures add seconds.
- **Mitigation:** The architecture mentions `temperature: 0.1` and `max_tokens: 4096` but does NOT specify:
  - Timeout budgets per step
  - Fallback behavior when LLM is slow
  - Whether LLM calls are on the critical path or pre-computed

**🟠 RISK 2: 16 Sequential Steps Create Cumulative Latency**
- The AlphaStack pipeline is strictly sequential (Step 1 → 2 → ... → 16).
- Even if each step averages 30ms, 16 steps = 480ms minimum.
- If any step calls an external service, the entire pipeline stalls.
- **Mitigation:** Steps 5–8 (Structure) could run in parallel since they analyze different aspects of the same data.

**🟠 RISK 3: Broker Latency is Phase-Dependent**
- Phase 1 (MT5 via ZeroMQ): ~50ms — acceptable
- Phase 2 (CCXT REST): ~200-500ms — borderline
- The architecture lists FIX at <10ms but that's Phase 5 ($1M+)
- **Mitigation:** For Phase 1-2, the 5s target is comfortable. For Phase 3+, need WebSocket-based execution or FIX.

### 1.4 Recommendations

| # | Recommendation | Priority | Effort |
|---|---------------|----------|--------|
| 1.1 | **Define per-step latency budgets** — e.g., Step 1 ≤ 100ms, total pipeline ≤ 1s | 🔴 Critical | Low |
| 1.2 | **Move LLM calls off the critical path** — Pre-compute fundamental bias and sentiment periodically (every 1h/4h), not per-tick | 🔴 Critical | Medium |
| 1.3 | **Add pipeline timeout circuit breaker** — If total pipeline exceeds 2s, abort and log | 🟠 High | Low |
| 1.4 | **Parallelize independent AlphaStack steps** — Steps 5-8 can run concurrently | 🟡 Medium | Medium |
| 1.5 | **Use streaming LLM responses** — Start processing partial results rather than waiting for full completion | 🟡 Medium | Medium |
| 1.6 | **Add warm-up / pre-warming** — Pre-load model weights, keep connections alive, cache common queries | 🟢 Low | Low |

---

## 2. Are Memory Management Practices Adequate for 24/7?

### 2.1 Verdict: 🔴 **No — Memory Management is Absent from the Architecture**

The architecture documents **do not address** memory management for long-running processes. This is a critical gap for a 24/7 trading system.

### 2.2 Identified Memory Risks

**🔴 RISK 1: Python Process Memory Growth (Unbounded)**
- The system runs as long-lived Python asyncio processes.
- Python's garbage collector does NOT guarantee timely collection of circular references.
- Each tick, signal, and order creates objects that may accumulate.
- **No mention of:** memory limits, GC tuning, object pools, or memory monitoring.

**🔴 RISK 2: Redis Memory is Hard-Limited to 256MB**
- `maxmemory 256mb` with `allkeys-lru` eviction.
- At 100 ticks/sec across 10 pairs, Redis stores ~86K ticks/day in `stream:ticks:*`.
- With JSON payloads of ~200 bytes each, that's ~17MB/day for ticks alone.
- Add candles, signals, orders, agent memory — 256MB fills in weeks.
- **Mitigation specified:** Stream trimming (`maxlen 10K`) — but no mention of monitoring actual memory usage.

**🟠 RISK 3: TimescaleDB Continuous Aggregates Can Stall**
- 6 continuous aggregates (1m → 5m → 15m → 1h → 4h → 1d) each refresh on schedule.
- If a refresh falls behind (e.g., after downtime), cascading refreshes can spike memory/CPU.
- No mention of refresh failure handling or backpressure.

**🟠 RISK 4: Agent Memory / Observation Lists Grow Without Bound**
- `agent:{id}:observations` (last 100) and `agent:{id}:decisions` (last 50) are bounded.
- But `patterns:{symbol}` and `indicators:{sym}:{tf}` hashes have no size limits.
- Over weeks, indicator hashes can accumulate stale entries.

**🟡 RISK 5: ML Model Memory (PyTorch)**
- FinBERT: ~440MB in GPU/CPU memory.
- If running multiple models (sentiment + regime + S/R + pattern), could be 2-4GB.
- No mention of model loading strategy (lazy vs eager), inference batching, or memory limits.

### 2.3 Recommendations

| # | Recommendation | Priority | Effort |
|---|---------------|----------|--------|
| 2.1 | **Set Python process memory limits** — Use `resource.setrlimit()` or container memory limits; alert at 80% | 🔴 Critical | Low |
| 2.2 | **Add memory monitoring** — Prometheus metrics for process RSS, Redis memory, PostgreSQL shared_buffers | 🔴 Critical | Low |
| 2.3 | **Implement object pooling** for tick/order objects — Reuse objects instead of creating new ones per tick | 🟠 High | Medium |
| 2.4 | **Tune Python GC** — `gc.set_threshold(700, 10, 10)` and periodic `gc.collect()` during low-activity periods | 🟠 High | Low |
| 2.5 | **Set Redis memory alerts** — Alert at 70% of maxmemory; tune TTLs before eviction kicks in | 🟡 Medium | Low |
| 2.6 | **Add ML model memory budgets** — Load models lazily, use ONNX runtime for inference (lower memory than PyTorch) | 🟡 Medium | Medium |
| 2.7 | **Implement graceful restart** — Weekly rolling restart during low-activity window (Sunday 22:00 UTC) | 🟢 Low | Low |

---

## 3. Is Database Query Optimization Sufficient?

### 3.1 Verdict: 🟡 **Mostly Adequate — But Missing Critical Optimizations**

The data storage architecture defines good indexes and hypertable designs, but several gaps exist for real-time trading queries.

### 3.2 Strengths

| Aspect | Assessment | Notes |
|--------|-----------|-------|
| Hypertable partitioning | ✅ Excellent | 1-day chunks for ticks, 7-day for candles |
| Compression policies | ✅ Excellent | 95%+ reduction after 7-30 days |
| Composite indexes | ✅ Good | `(symbol, timeframe, time DESC)` covers primary queries |
| Continuous aggregates | ✅ Good | Auto-computed candles from 1m → 1d |
| Retention policies | ✅ Good | Automated cleanup via TimescaleDB native policies |
| Query targets defined | ✅ Good | <5ms for last 500 candles, <50ms for ticks |

### 3.3 Gaps

**🟠 GAP 1: No Query Result Caching Layer**
- Every AlphaStack step that needs "last 500 candles" hits TimescaleDB.
- For 10 pairs × 5 timeframes × 16 steps = 800 potential DB calls per signal cycle.
- The architecture defines Redis as a cache (`ohlcv:{symbol}:{tf}` for current candle) but does NOT specify caching completed candle queries.
- **Impact:** Unnecessary DB load, especially during high-frequency signal generation.

**🟠 GAP 2: No Prepared Statements / Connection-Level Optimization**
- The data storage doc shows `pgbouncer.ini` (transaction mode) but:
  - No mention of prepared statements for hot queries.
  - No mention of `statement_timeout` to prevent runaway queries.
  - No mention of `idle_in_transaction_session_timeout`.

**🟡 GAP 3: Missing Indexes for Hot Queries**
- The `positions` table has `idx_positions_symbol WHERE status = 'open'` — good.
- But the `orders` table index `idx_orders_status WHERE status IN (...)` uses a multi-value partial index — PostgreSQL may not use it efficiently for single-status lookups.
- No index on `orders(broker_order_id)` for fill event lookups.

**🟡 GAP 4: No Materialized View Refresh Strategy Under Load**
- `v_strategy_performance` is a materialized view with `WITH NO DATA`.
- No mention of refresh frequency, CONCURRENTLY refresh, or impact on write performance.
- If refreshed during market hours, could cause lock contention.

**🟡 GAP 5: ClickHouse Not Integrated Yet**
- The architecture mentions ClickHouse for analytics but has zero schema definitions.
- No CDC pipeline defined between TimescaleDB and ClickHouse.
- Analytics queries will compete with trading queries on the same PostgreSQL instance until Phase 4.

### 3.4 Recommendations

| # | Recommendation | Priority | Effort |
|---|---------------|----------|--------|
| 3.1 | **Add Redis query cache for candle data** — Cache "last N candles" results with TTL = candle timeframe | 🔴 Critical | Low |
| 3.2 | **Use prepared statements** for hot queries (tick insert, candle lookup, position check) | 🟠 High | Low |
| 3.3 | **Set `statement_timeout = 500ms`** for trading-path queries; `5s` for analytics | 🟠 High | Low |
| 3.4 | **Add `idx_orders_broker_order_id`** index for fill event lookups | 🟡 Medium | Low |
| 3.5 | **Schedule materialized view refreshes** during off-hours only (Sunday night) | 🟡 Medium | Low |
| 3.6 | **Define ClickHouse schema and CDC pipeline** now, even if not deployed until Phase 3 | 🟢 Low | Medium |

---

## 4. Is WebSocket Performance Adequate for Real-Time Data?

### 4.1 Verdict: 🔴 **WebSocket Architecture is Underspecified**

The architecture mentions WebSocket in the API Gateway layer (FastAPI + WebSocket server) but provides **virtually no performance specifications**.

### 4.2 Gaps

**🔴 GAP 1: No WebSocket Performance Targets**
- No defined metrics for:
  - Maximum concurrent connections
  - Message throughput (msgs/sec)
  - End-to-end latency (tick → client)
  - Reconnection time
  - Backpressure behavior

**🔴 GAP 2: No WebSocket Connection Management**
- No mention of:
  - Heartbeat/ping-pong intervals
  - Connection timeout configuration
  - Message queuing during reconnection
  - Client-side buffering strategy
  - Binary vs text message format (binary is 2-5x faster for tick data)

**🔴 GAP 3: No Fan-Out Architecture**
- When a tick arrives, it needs to reach: strategy agents, risk agent, dashboard clients, mobile clients.
- No mention of how Redis Pub/Sub → WebSocket fan-out works.
- If using Python asyncio for fan-out, a single slow client can block others.

**🟠 GAP 4: No Mention of WebSocket Library Choice**
- FastAPI uses `starlette.websockets` — adequate but not optimized for high-throughput.
- For production, should consider `uvicorn` with `uvloop` (not mentioned).
- For institutional scale, should consider `tokio-tungstenite` (Rust) for the tick ingestion path.

**🟡 GAP 5: No Binary Protocol for Tick Data**
- JSON serialization for tick data: ~200 bytes per tick, ~50μs serialize/deserialize.
- MessagePack or Protobuf: ~50 bytes, ~10μs — 4x less bandwidth, 5x less CPU.
- At 100 ticks/sec/pair × 10 pairs = 1000 ticks/sec, this matters.

### 4.3 Recommendations

| # | Recommendation | Priority | Effort |
|---|---------------|----------|--------|
| 4.1 | **Define WebSocket SLAs** — e.g., <100ms tick-to-client, 99.9% delivery, <5s reconnection | 🔴 Critical | Low |
| 4.2 | **Use `uvloop`** as the asyncio event loop (2-4x throughput improvement) | 🔴 Critical | Low |
| 4.3 | **Implement binary serialization** (MessagePack) for tick data over WebSocket | 🟠 High | Medium |
| 4.4 | **Add per-client backpressure** — Drop messages if client buffer > N, don't block other clients | 🟠 High | Medium |
| 4.5 | **Add WebSocket heartbeat** — 30s ping/pong, disconnect after 3 missed pongs | 🟡 Medium | Low |
| 4.6 | **Consider Rust WebSocket server** (tokio-tungstenite) for the tick ingestion hot path at Phase 3+ | 🟢 Low | High |

---

## 5. Are Connection Pooling Strategies Correct?

### 5.1 Verdict: 🟠 **Database Pooling is Defined, Broker Pooling is Missing**

### 5.2 Database Connection Pooling (PgBouncer)

The data storage architecture defines PgBouncer configuration:

```ini
pool_mode = transaction
max_client_conn = 200
default_pool_size = 20
min_pool_size = 5
reserve_pool_size = 5
```

**Assessment:**

| Parameter | Value | Assessment | Notes |
|-----------|-------|-----------|-------|
| `pool_mode = transaction` | ✅ Correct | Best for short-lived queries |
| `max_client_conn = 200` | 🟡 Generous | 6 agents + gateway won't need 200; but safe |
| `default_pool_size = 20` | ✅ Good | Matches PostgreSQL default `max_connections = 100` |
| `min_pool_size = 5` | ✅ Good | Keeps connections warm |
| `reserve_pool_size = 5` | ✅ Good | Handles burst traffic |
| `server_idle_timeout = 300` | 🟡 Could be lower | 5 min idle is fine for Phase 1; reduce to 60s for Phase 3+ |
| `client_idle_timeout = 600` | 🟠 Too long | 10 min idle clients waste pool slots; should be 120s |

**🟡 Missing:** No mention of per-user or per-application pool limits. If the analytics dashboard hammers the DB, it could starve the trading engine.

### 5.3 Broker Connection Pooling — 🔴 **Completely Absent**

This is the most significant gap in the connection management strategy.

| Broker | Connection Model | Pooling Needed | Architecture Status |
|--------|-----------------|---------------|-------------------|
| MT5 (ZeroMQ) | Persistent socket | Yes — maintain N connections | ❌ Not specified |
| CCXT (REST) | HTTP per request | Yes — HTTP connection reuse | ❌ Not specified |
| CCXT (WebSocket) | Persistent WS | Yes — 1 WS per exchange | ❌ Not specified |
| OANDA (Streaming) | Persistent HTTP | Yes — 1 streaming conn per account | ❌ Not specified |

**Risks:**
- Without connection pooling, each order creates a new TCP connection (~50-100ms overhead).
- MT5 via ZeroMQ should maintain a persistent connection — but no reconnection strategy is defined.
- CCXT REST calls without `requests.Session()` reuse will re-establish TLS for each call.

### 5.4 Redis Connection Pooling — 🟡 **Not Specified**

- Redis is used for cache, Pub/Sub, and Streams.
- Each Python module likely creates its own `redis.Redis()` connection.
- No mention of connection pooling (`redis.ConnectionPool`), max connections, or socket timeout.
- At 6 agents + gateway + data pipeline = ~10+ Redis connections minimum.

### 5.5 Recommendations

| # | Recommendation | Priority | Effort |
|---|---------------|----------|--------|
| 5.1 | **Implement broker connection pooling** — Persistent connections with health checks and auto-reconnect | 🔴 Critical | Medium |
| 5.2 | **Define per-application PgBouncer pools** — Separate pool limits for trading vs analytics vs gateway | 🟠 High | Low |
| 5.3 | **Reduce `client_idle_timeout` to 120s** | 🟡 Medium | Low |
| 5.4 | **Use `redis.ConnectionPool`** with `max_connections=50` and `socket_timeout=5` | 🟡 Medium | Low |
| 5.5 | **Add connection health monitoring** — Prometheus metrics for pool size, active connections, wait time | 🟡 Medium | Low |
| 5.6 | **Implement circuit breaker** for broker connections — After N failures, pause attempts for M seconds | 🟡 Medium | Medium |

---

## 6. Performance Bottlenecks

### 6.1 Bottleneck Map

```
TICK ARRIVAL ────────────────────────────────────────────────── ORDER PLACEMENT
     │                                                              │
     ▼                                                              ▼
┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐
│ Ingestion│──▶│ AlphaStack    │──▶│  Risk   │──▶│Execution│──▶│ Broker  │
│ (5ms)   │   │Pipeline │   │  Agent  │   │  Agent  │   │  API    │
│         │   │(50-2000)│   │ (5ms)   │   │ (5ms)   │   │(50-500) │
└─────────┘   └────┬────┘   └─────────┘   └─────────┘   └─────────┘
                   │
         ┌─────────┴──────────┐
         │                    │
    BOTTLENECK 1         BOTTLENECK 2
    LLM API calls        Sequential pipeline
    (200-2000ms)         (no parallelism)
```

### 6.2 Bottleneck Inventory

| # | Bottleneck | Severity | Location | Impact |
|---|-----------|----------|----------|--------|
| **B1** | LLM API latency (DeepSeek/Qwen) | 🔴 Critical | AlphaStack Steps 1, possibly others | 200-2000ms, non-deterministic |
| **B2** | Sequential AlphaStack pipeline | 🟠 High | AlphaStack Steps 1→16 | No parallelism, cumulative latency |
| **B3** | MT5 terminal (Wine on Linux) | 🟠 High | Broker connector | Wine adds ~10-50ms overhead; stability risk |
| **B4** | Python GIL for CPU-bound work | 🟡 Medium | Indicator calculations | Limits true parallelism |
| **B5** | Redis Pub/Sub fan-out | 🟡 Medium | Signal distribution | Single-threaded; slow consumers block |
| **B6** | TimescaleDB write contention | 🟡 Medium | Tick ingestion | Hypertable chunk creation can briefly stall writes |
| **B7** | Docker overhead | 🟢 Low | All components | ~2-5% CPU overhead, acceptable |
| **B8** | JSON serialization | 🟢 Low | Event bus messages | ~50μs per message, acceptable at current scale |

### 6.3 Bottleneck Deep-Dives

#### B1: LLM API Latency — The #1 Performance Risk

**Current state:** The architecture specifies LLM models (DeepSeek, Qwen) for strategy reasoning but does NOT specify:
- Whether LLM calls are synchronous on the critical path
- Timeout configuration
- Retry strategy
- Fallback behavior
- Response caching

**What happens under load:**
- 10 pairs × 1 signal cycle/min = 10 LLM calls/min
- If each call takes 500ms median, that's 5s/min of LLM time
- If LLM API has a 5% failure rate, that's 1 failed call every 2 minutes
- With retry (3 attempts × 500ms), a single failure costs 1.5s

**Mitigation architecture (recommended):**
```
Instead of:
  Tick → AlphaStack Step 1 (LLM call) → Step 2 → ... → Step 16 → Order

Implement:
  ┌─ Pre-compute Layer (every 1-4h) ─────────────────────────┐
  │  Step 1 (Fundamental) → LLM call → Cache result (4h TTL) │
  │  Step 2 (Market Bias) → LLM call → Cache result (1h TTL) │
  └───────────────────────────────────────────────────────────┘
  
  Tick → Steps 3-16 (all cached/computed, no LLM) → Order
         (~100-200ms total)
```

#### B2: Sequential Pipeline Parallelism

**Current:** Steps 1→2→3→...→16 execute sequentially.

**Optimization opportunity:**
```
Steps 1-4 (Context):  Independent → can run in parallel
Steps 5-8 (Structure): Independent → can run in parallel
Steps 9-12 (Entry):  Mostly sequential (entry depends on S/R, liquidity)
Steps 13-16 (Management): Sequential (TP depends on entry, etc.)

Optimized:
  ┌─ Steps 1-4 (parallel, ~30ms) ──┐
  └─ Steps 5-8 (parallel, ~50ms) ──┤──▶ Steps 9-12 (sequential, ~40ms) ──▶ Steps 13-16 (sequential, ~30ms)
                                    │
Total: ~150ms (vs ~480ms sequential)
```

#### B3: MT5 on Linux via Wine

**Risk:** MetaTrader 5 does not run natively on Linux. Running via Wine adds:
- 10-50ms latency per API call (IPC overhead)
- Stability risk (Wine crashes, MT5 freezes)
- Memory overhead (~200-500MB for Wine + MT5)
- No native watchdog — need external process monitoring

**Mitigation:** The ZeroMQ bridge helps (direct socket vs Wine API calls), but the MT5 terminal itself still runs under Wine.

---

## 7. Additional Performance Concerns

### 7.1 No Performance Testing Strategy

The architecture mentions test suites (`tests/unit/`, `tests/integration/`, `tests/backtest/`, `tests/paper/`) but does NOT define:
- Load testing methodology
- Latency benchmarking approach
- Performance regression tests
- Stress testing scenarios

**Recommendation:** Define performance acceptance criteria and automated benchmarks.

### 7.2 No Observability for Performance

The architecture mentions Prometheus + Grafana but provides:
- No specific metrics to collect
- No alerting thresholds
- No SLO definitions
- No distributed tracing

**Recommended metrics:**

```
# Trading path latency
trading_tick_to_order_seconds{pair, broker} — histogram
trading_alphastack_pipeline_seconds{pair, step} — histogram
trading_risk_check_seconds — histogram
trading_broker_latency_seconds{broker, order_type} — histogram

# System health
process_resident_memory_bytes{service} — gauge
redis_memory_used_bytes — gauge
redis_connected_clients — gauge
pg_connections_active{database} — gauge
pg_query_duration_seconds{query_type} — histogram

# WebSocket
ws_connections_active — gauge
ws_messages_sent_total — counter
ws_messages_dropped_total — counter
ws_fanout_latency_seconds — histogram
```

### 7.3 No Backpressure Mechanism

If market data arrives faster than the system can process:
- Tick stream grows unbounded in Redis
- AlphaStack pipeline queue grows
- Orders may be placed on stale signals

**No backpressure strategy is defined.** The system should:
- Drop old ticks if processing falls behind
- Skip signal generation for pairs that are too far behind
- Alert when processing lag exceeds threshold

---

## 8. Summary — Performance Readiness Matrix

| Dimension | Phase 1 ($7) | Phase 2 ($100) | Phase 3 ($10K) | Phase 4 ($100K+) |
|-----------|-------------|----------------|-----------------|-------------------|
| **Tick-to-Order Latency** | 🟢 Achievable | 🟢 Achievable | 🟠 Needs work | 🔴 Needs redesign |
| **Memory Management** | 🟡 Basic | 🟡 Basic | 🔴 Insufficient | 🔴 Insufficient |
| **DB Query Optimization** | 🟢 Adequate | 🟢 Adequate | 🟡 Needs tuning | 🟠 Needs ClickHouse |
| **WebSocket Performance** | 🟡 Functional | 🟡 Functional | 🔴 Underspecified | 🔴 Underspecified |
| **Connection Pooling** | 🟢 Basic OK | 🟡 Needs PgBouncer | 🟠 Needs broker pool | 🔴 Needs full strategy |
| **Observability** | 🟡 Console logs | 🟡 Prometheus | 🟠 Needs dashboards | 🔴 Needs full stack |

---

## 9. Top 10 Action Items (Priority Order)

| # | Action | Priority | Phase | Effort | Impact |
|---|--------|----------|-------|--------|--------|
| 1 | Move LLM calls off critical path (pre-compute + cache) | 🔴 Critical | 1 | Medium | Eliminates biggest latency variable |
| 2 | Define per-step latency budgets and pipeline timeout | 🔴 Critical | 1 | Low | Enables performance regression detection |
| 3 | Add process memory limits and monitoring | 🔴 Critical | 1 | Low | Prevents OOM crashes in 24/7 operation |
| 4 | Implement broker connection pooling with health checks | 🔴 Critical | 2 | Medium | Eliminates connection setup latency |
| 5 | Add Redis query cache for candle data | 🟠 High | 1 | Low | Reduces DB load by 80%+ |
| 6 | Define WebSocket SLAs and add backpressure | 🟠 High | 2 | Medium | Ensures real-time data reliability |
| 7 | Use `uvloop` and binary serialization (MessagePack) | 🟠 High | 2 | Low | 2-5x throughput improvement |
| 8 | Parallelize independent AlphaStack steps (1-4, 5-8) | 🟡 Medium | 2 | Medium | ~300ms latency reduction |
| 9 | Set `statement_timeout` and use prepared statements | 🟡 Medium | 1 | Low | Prevents runaway queries |
| 10 | Define performance SLOs and Prometheus metrics | 🟡 Medium | 2 | Medium | Enables proactive performance management |

---

*This review identifies that the Alpha Stack architecture has a solid foundation but needs targeted performance hardening. The biggest risk is LLM API latency on the critical path — removing that single dependency would transform the <5s target from "fragile" to "comfortable." The other gaps (memory management, WebSocket, connection pooling) are addressable with focused effort in Phase 1-2.*
