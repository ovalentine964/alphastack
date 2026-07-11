# Alpha Stack — Final Scalability Verification Report

> **Author:** Scalability Verification Agent  
> **Date:** 2026-07-11  
> **Status:** Final Verification — Pre-Implementation  
> **Documents Reviewed:** `architecture_system.md`, `architecture_data_storage.md`, `architecture_trading_engine.md`, `fix_platform_consolidation.md`, `review_8_scalability.md`  
> **Severity Levels:** 🔴 CRITICAL | 🟠 HIGH | 🟡 MEDIUM | 🟢 LOW | ✅ PASS

---

## Executive Summary

**Overall Verdict: CONDITIONALLY SCALABLE — 6 remaining gaps after fixes.**

The Alpha Stack architecture demonstrates strong foundational scalability design across all layers — data, execution, deployment, and platform. The event-driven, modular approach with progressive complexity scaling is well-conceived. The data storage layer (`architecture_data_storage.md`) is particularly robust, with clean phase-gated storage tiers and well-defined retention policies. The platform consolidation fix (`fix_platform_consolidation.md`) correctly unifies the three platform silos into a single server with shared API.

However, the prior scalability review (`review_8_scalability.md`) identified 3 critical and 5 high-severity issues. This final verification confirms that **some issues have been partially addressed in the architecture docs** while **6 scalability gaps remain** that require action before deployment.

| Metric | Score | Status |
|--------|-------|--------|
| Phase 1 ($7) viability | 8/10 | ✅ Works with caveats |
| Phase 1→2 transition | 7/10 | 🟡 Minimal changes needed |
| Scaling triggers | 6/10 | 🟠 Incomplete definitions |
| Cost appropriateness | 8/10 | ✅ Well-gated |
| Bottlenecks addressed | 5/10 | 🟠 6 gaps remain |
| **Overall** | **7/10** | **Conditionally Scalable** |

---

## 1. Does the Phase 1 ($7) Architecture Actually Work?

### 1.1 Phase 1 Component Stack Assessment

| Component | Phase 1 Config | Viable? | Notes |
|-----------|---------------|---------|-------|
| **PostgreSQL 16 + TimescaleDB** | Docker, single instance | ✅ YES | Hypertables, compression, continuous aggregates all work on single node |
| **Redis 7** | Docker, single instance, 128MB | ✅ YES | Pub/Sub + Streams for event bus, AOF persistence |
| **VMPM 16-step pipeline** | Python asyncio on single machine | ✅ YES | Single pair (EUR/USD), ~50-200ms per pipeline run |
| **MT5 via Wine** | Local machine | 🟡 FRAGILE | Works but Wine on Linux is inherently unstable. Documented risk. |
| **Docker Compose** | Local machine | ✅ YES | All services co-located, environment variables for config |
| **Config files (JSON/YAML)** | No MongoDB | ✅ YES | Appropriate for 1 strategy, <10 config files |
| **Local disk backups** | pg_dump cron | ✅ YES | 7-day retention, sufficient for $7 scale |
| **Application-level encryption** | AES-256-GCM for credentials | ✅ YES | Broker credentials encrypted from day 1 |
| **Monitoring** | Prometheus + Grafana (Docker) | ✅ YES | Same machine, acceptable for dev |

### 1.2 Phase 1 Data Pipeline Viability

The data storage architecture defines a clean Phase 1 path:

| Data Store | Phase 1 Config | Storage Estimate | Verdict |
|-----------|---------------|-----------------|---------|
| TimescaleDB (ticks) | 1-day chunks, compress after 7d | ~5 GB/year for 3 pairs | ✅ Fits on 50GB SSD |
| TimescaleDB (candles) | 7-day chunks, compress after 30d | ~200 MB | ✅ Negligible |
| TimescaleDB (news) | 30-day chunks | ~500 MB | ✅ Negligible |
| Redis (hot state) | 128MB max, allkeys-lru | ~50 MB typical | ✅ Sufficient |
| Config files (JSON) | No MongoDB | <100 MB | ✅ Fine |
| **Total** | | **~6 GB** | **✅ Fits easily** |

### 1.3 Phase 1 Cost Problem

**🔴 UNRESOLVED: The $7 cost drain problem.**

The prior review identified that at $7 capital with 0.01 lot EUR/USD, spread cost is ~$0.10-0.15 per trade (1.4-2.1% of capital). This means ~46 trades before costs drain the account.

**Status in architecture docs:**
- `architecture_system.md`: Acknowledges the problem in scaling section
- `architecture_data_storage.md`: No cost mitigation
- `architecture_trading_engine.md`: Defines spread filter (`spread_filter_multiplier: 2.0`) but no cost budget

**Gap:** No "cost budget" system exists. The architecture filters by spread magnitude but doesn't track cumulative cost burden relative to account size.

**Verdict:** Phase 1 **works mechanically** but has a **viability risk at $7 capital** due to cost drain. The spread filter helps but doesn't solve the fundamental problem.

### 1.4 Phase 1 Verdict

**✅ YES — Phase 1 works** with two caveats:
1. MT5/Wine fragility is an accepted operational risk
2. Cost drain at $7 needs a mitigation strategy (cost budget + trade limits)

---

## 2. Does Scaling to Phase 2 ($100+) Require Minimal Changes?

### 2.1 Phase 1→2 Transition Analysis

| Change Required | Effort | Status |
|----------------|--------|--------|
| SQLite → PostgreSQL | Already in Phase 1 | ✅ No change needed |
| Add PgBouncer | Config addition | ✅ Minimal |
| Enable WAL archiving | Config change | ✅ Minimal |
| Add Backblaze B2 backup | Script addition | ✅ Minimal |
| Add MongoDB for configs | Optional, Docker container | ✅ Minimal |
| Add continuous aggregates | SQL migration (Alembic) | ✅ Minimal |
| Enable compression policies | SQL migration | ✅ Minimal |
| Add agent memory tables | SQL migration | ✅ Minimal |
| Upgrade VPS spec | Config change | ✅ Minimal |

### 2.2 What Actually Changes at Phase 2

The data storage architecture defines Phase 2 cleanly:

| Component | Phase 1 → Phase 2 | Migration Effort |
|-----------|-------------------|-----------------|
| **Database** | Same PostgreSQL + TimescaleDB | Zero (already there) |
| **Connection pooling** | Add PgBouncer | 1 hour |
| **Backup** | Add WAL archiving + external | 2 hours |
| **Continuous aggregates** | Enable candle_1m→1d pipeline | Alembic migration |
| **Compression** | Add policies for ticks, market_data | SQL one-liners |
| **Storage** | ~6 GB → ~57 GB | Still fits on single server |
| **Deployment** | Local Docker → VPS Docker | Docker Compose is environment-agnostic |
| **Cost** | $0/mo → ~$10-20/mo | Proportional to $100 capital |

### 2.3 Platform Consolidation Impact on Phase 2

The `fix_platform_consolidation.md` introduces the Alpha Stack Server as a unified backend. This affects Phase 2:

| Impact | Assessment |
|--------|-----------|
| Server runs on VPS (cloud mode) | ✅ All platforms connect to same API |
| Desktop becomes thin shell | ✅ Eliminates local-first complexity |
| Single API surface | ✅ No per-platform backend drift |
| JWT auth | ✅ Works across all platforms |
| Shared API client | ✅ TypeScript + Dart clients |

**The platform consolidation fix actually simplifies Phase 2** — instead of managing separate backend paths for desktop/web/mobile, there's one server with one API.

### 2.4 Phase 2 VPS Sizing Issue

**🟠 HIGH: Phase 2 VPS (Hetzner CX31: 4 CPU, 8GB RAM) is undersized.**

The prior review identified that 10 pairs × VMPM pipeline × LLM inference requires more resources:
- FinBERT inference: ~2GB RAM
- Redis + PostgreSQL + TimescaleDB + trading engine: ~4GB baseline
- 10 pairs × concurrent pipeline: significant CPU

**Status:** The `architecture_data_storage.md` Phase 2 specifies Hetzner CX21 (2 CPU, 4GB RAM) at $7/mo, which is even smaller than the CX31 in the system architecture.

**Recommendation:** Phase 2 VPS should be at minimum **8 CPU, 16GB RAM** (Hetzner CX41, ~$30/mo) or stay at 3-5 pairs max on CX31.

### 2.5 Phase 1→2 Verdict

**✅ YES — Phase 1→2 requires minimal changes.** The architecture is designed so the same PostgreSQL schema, same Redis patterns, and same Docker Compose config work at both phases. Key changes are config-level (PgBouncer, WAL archiving, compression policies), not architectural.

**One exception:** VPS sizing needs to be upgraded from the documented CX21 to at least CX31, preferably CX41.

---

## 3. Are All Scaling Triggers Properly Defined?

### 3.1 Scaling Triggers Assessment

The `architecture_system.md` defines scaling triggers in Section 8.3:

| Trigger | Definition | Verdict |
|---------|-----------|---------|
| **Pairs** | "Win rate > 55% over 100+ trades on current pair" | ✅ Clear, measurable |
| **Brokers** | "Capital > $5K OR need crypto exposure" | ✅ Clear |
| **Timeframes** | "Need finer entry precision OR holding time < 1 hour" | 🟡 Vague |
| **ML Models** | "1000+ labeled trade outcomes available" | ✅ Clear |
| **Database** | "SQLite queries > 100ms OR need concurrent access" | ✅ Clear (but SQLite is already replaced in Phase 1) |
| **Autonomy** | "Win rate > 60% over 200+ trades, max drawdown < 15%" | ✅ Clear |
| **Execution** | "Average position > 1.0 lot OR slippage > 1 pip" | ✅ Clear |
| **Infrastructure** | "Capital > $50K OR uptime < 99%" | ✅ Clear |

### 3.2 Data Storage Scaling Triggers

The `architecture_data_storage.md` defines triggers in Section 10.6:

| Trigger | Threshold | Action |
|---------|-----------|--------|
| PostgreSQL CPU >70% sustained | Phase 2→3 | Add read replica |
| PostgreSQL disk >80% | Any phase | Enable compression, archive old data |
| Tick write latency >10ms p99 | Phase 3→4 | Move to dedicated ingestion service |
| Redis memory >80% | Phase 2→3 | Increase maxmemory, review TTLs |
| Query latency >500ms for dashboards | Phase 3→4 | Add ClickHouse for analytics |
| Connection count >80% of max | Phase 2→3 | Tune PgBouncer, add connection pooling |
| Backup time >1 hour | Phase 3→4 | Switch to pgBackRest with incremental |
| Storage >80% of disk | Any phase | Add compression, offload to object storage |
| Need >10 concurrent analytical queries | Phase 3→4 | Add ClickHouse for OLAP |

### 3.3 Gaps in Scaling Triggers

| Gap | Severity | Issue |
|-----|----------|-------|
| **No cost-per-trade trigger** | 🟠 HIGH | No trigger for "total weekly trading costs > 5% of account" |
| **No LLM latency trigger** | 🟡 MEDIUM | No trigger for "LLM inference > 500ms p99" |
| **No memory pressure trigger** | 🟡 MEDIUM | No trigger for "process memory > 80% of available" |
| **No Redis latency trigger** | 🟡 MEDIUM | No trigger for "Redis command latency > 10ms p99" |
| **Timeframe trigger is vague** | 🟡 MEDIUM | "Need finer entry precision" isn't measurable |
| **Database trigger references SQLite** | 🟢 LOW | Phase 1 already uses PostgreSQL; trigger is stale |

### 3.4 Scaling Triggers Verdict

**🟡 MOSTLY DEFINED — 4 missing triggers.** The architecture defines 17 scaling triggers across two documents, covering infrastructure, data, execution, and strategy dimensions. However, cost-per-trade, LLM latency, memory pressure, and Redis latency triggers are missing.

---

## 4. Is Infrastructure Cost Appropriate at Each Phase?

### 4.1 Cost Breakdown by Phase

| Phase | Capital | Infrastructure Cost | Cost as % of Capital | Verdict |
|-------|---------|-------------------|---------------------|---------|
| **1** | $7 | $0/mo (local) | 0% | ✅ Appropriate |
| **2** | $100 | $10-20/mo | 10-20%/mo | 🟡 High but acceptable for learning |
| **3** | $1K | $30-60/mo | 3-6%/mo | ✅ Appropriate |
| **4** | $10K+ | $80-150/mo | 0.8-1.5%/mo | ✅ Appropriate |
| **5** | $100K+ | $500-2000/mo | 0.5-2%/mo | ✅ Appropriate |

### 4.2 Cost Scaling Appropriateness

**✅ PASS — Costs scale proportionally with capital.**

Key observations:
- Phase 1 at $0/mo is essential — no infrastructure cost on $7 capital
- Phase 2 at $10-20/mo on $100 capital is high (10-20%) but the VPS provides 24/5 operation, which is necessary for live trading
- Phase 3+ costs become negligible as percentages
- The architecture correctly avoids over-engineering at low phases (no Kafka at $7, no K8s at $100)

### 4.3 Cost Optimization Opportunities

| Opportunity | Phase | Impact |
|------------|-------|--------|
| Use Hetzner auction servers | 2-3 | 30-50% cheaper than listed prices |
| Use Backblaze B2 instead of S3 | 2-3 | 10× cheaper for backup storage |
| Self-hosted Prometheus instead of managed | 2-3 | Save $10-20/mo |
| TimescaleDB compression enables smaller disks | 2+ | 95% storage reduction after compression |

### 4.4 Cost Verdict

**✅ APPROPRIATE at every phase.** The phase-gated spending model is well-designed. Infrastructure costs never exceed 20% of capital and drop to <2% at institutional scale.

---

## 5. Are There Scaling Bottlenecks Not Addressed?

### 5.1 Bottleneck Assessment Matrix

| Bottleneck | Severity | Addressed? | Status |
|-----------|----------|-----------|--------|
| **Redis SPOF** | 🔴 CRITICAL | Partially | Arch defines AOF persistence but Redis Sentinel is Phase 4, should be Phase 2 |
| **LLM inference latency** | 🟠 HIGH | Partially | Mentioned in prior review, no implementation in architecture docs |
| **MT5 serialization** | 🟠 HIGH | Partially | ZeroMQ bridge exists but market data still goes through serialized Python API |
| **Cost drain at $7** | 🟠 HIGH | Partially | Spread filter exists but no cost budget system |
| **State recovery on restart** | 🟠 HIGH | ❌ NOT ADDRESSED | No startup reconciliation procedure defined |
| **Python GIL** | 🟡 MEDIUM | Partially | Rust-backed indicators (ta_core.rs) mitigate CPU-bound paths |
| **Multi-broker order reconciliation** | 🟡 MEDIUM | ❌ NOT ADDRESSED | SOR designed but reconciliation logic for partial fills undefined |
| **LLM fallback chain** | 🟡 MEDIUM | ❌ NOT ADDRESSED | No fallback model, no cached responses, no timeout handling |
| **Dead letter queue** | 🟡 MEDIUM | Partially | Redis Streams defined with DLQ stream but no consumer implementation |
| **Connection pooling** | 🟡 MEDIUM | ✅ ADDRESSED | PgBouncer config defined in data storage architecture |

### 5.2 Unaddressed Bottlenecks (Details)

#### 🔴 Bottleneck 1: Redis SPOF — Sentinel Too Late

**Problem:** The data storage architecture puts Redis Sentinel at Phase 4 ($10K+). Until then, Redis is a single point of failure. If Redis crashes, ALL inter-module communication stops — the system enters safe mode and closes all positions.

**Evidence from architecture:**
- `architecture_data_storage.md` Section 3.4: "Phase 4: Redis Cluster (3 masters)"
- `architecture_system.md` Section 7.3: Event Bus failure → "System enters safe mode: close all positions, halt trading"

**Why this is critical:** At Phase 2 ($100), the system is doing live trading on a VPS. A Redis crash means:
1. All agent communication stops
2. No new signals processed
3. Open positions lose management (S14/S15 can't run)
4. System closes all positions (catastrophic at scale)

**Fix:** Add Redis Sentinel at Phase 2, not Phase 4. The cost is minimal (2 additional Redis processes on same VPS) and the risk reduction is massive. Sentinel provides automatic failover with <5 second recovery.

#### 🟠 Bottleneck 2: LLM Inference Latency — No Fallback

**Problem:** The VMPM pipeline has 4+ LLM-dependent steps (S1, S2, S3, S7). Each call takes 50-200ms. For 10 pairs running concurrently, this creates a 6-second sequential bottleneck or significant parallel resource contention.

**Evidence from architecture:**
- `architecture_system.md`: LLM calls are on the critical path
- `architecture_trading_engine.md`: Steps 1, 2, 3, 7 all depend on LLM inference
- No fallback model defined
- No response caching defined
- No timeout handling defined

**Impact:** At 10+ pairs, LLM latency becomes the dominant bottleneck. An API outage stalls the entire strategy pipeline.

**Fix:**
1. Implement LLM response caching in Redis (1h TTL for identical market conditions)
2. Set hard timeout (5s per call) with graceful degradation to rule-based fallback
3. Define fallback model chain: primary → secondary → cached → skip step
4. At Phase 3+, use local inference server (vLLM) for FinBERT to eliminate API latency

#### 🟠 Bottleneck 3: State Recovery — Undefined

**Problem:** The architecture does not describe what happens when the system restarts after a crash. Key questions unanswered:
1. How does the system know which positions are open?
2. How does it rebuild Redis state?
3. How does it reconcile in-flight orders?

**Evidence:** Neither `architecture_system.md`, `architecture_trading_engine.md`, nor `architecture_data_storage.md` define a startup reconciliation procedure.

**Impact:** At scale, a crash without state recovery means:
- Open positions may be orphaned (no management)
- Risk limits may be incorrectly calculated
- Duplicate orders may be submitted

**Fix:** Define `startup_reconciliation()` procedure:
1. Query broker APIs for current positions and orders (source of truth)
2. Rebuild Redis state from PostgreSQL
3. Reconcile in-flight orders with broker state
4. Resume normal operation with verified state

#### 🟠 Bottleneck 4: MT5 Serialization — Data Collection Bottleneck

**Problem:** The Python MT5 API is single-threaded (serialized access). While the ZeroMQ bridge handles signal delivery to the EA, market data collection and position queries still go through the serialized Python API.

**Evidence:**
- `architecture_system.md`: "Serialized access (single-threaded)" for MT5
- `architecture_trading_engine.md`: MT5Connector uses `mt5.symbol_info_tick()` which is serialized

**Impact:** At 10+ pairs, only one pair can query MT5 at a time. This creates a queuing bottleneck for market data collection.

**Fix:** Implement `MT5DataProxy` service:
1. Separate process that polls MT5 on a schedule
2. Publishes to Redis Streams
3. Use ZeroMQ for ALL MT5 communication (bidirectional)
4. At Phase 3+, switch to OANDA REST API for forex data (HTTP-based, no serialization)

#### 🟡 Bottleneck 5: Multi-Broker Order Reconciliation

**Problem:** The architecture defines a Smart Order Router (SOR) with multi-broker splitting, but the reconciliation logic for partial fills across multiple brokers is not detailed.

**Evidence:**
- `architecture_system.md`: SOR routes to best broker
- `architecture_trading_engine.md`: `SmartOrderRouter` selects best price but doesn't handle split orders

**Impact:** At $100K+ with orders split across brokers, partial fills create inconsistent state.

**Fix:** Implement `SplitOrderCoordinator`:
1. Track child orders across brokers
2. Reconcile partial fills into unified position state
3. Add "settled" state to order lifecycle
4. Implement pre-trade market impact estimation at $100K+

#### 🟡 Bottleneck 6: LLM Response Caching

**Problem:** Every LLM inference call is fresh. For identical market conditions (same fundamental data + same session), the same analysis is re-computed every time.

**Impact:** Wastes money and adds latency. At 10 pairs × 4 LLM steps × 1 call/15min = ~27 LLM calls/hour. Many will have identical inputs.

**Fix:** Cache LLM responses in Redis with 1-hour TTL. Hash the input context and return cached response if hit.

### 5.3 Bottleneck Verdict

**🟠 6 BOTTLENECKS REMAIN.** Two critical (Redis SPOF, state recovery), three high (LLM latency, MT5 serialization, cost drain), and one medium (multi-broker reconciliation). All have defined fixes; none have implementation.

---

## 6. What Scalability Gaps Remain After Fixes?

### 6.1 Gap Summary

| # | Gap | Severity | Phase Impact | Fix Effort |
|---|-----|----------|-------------|------------|
| 1 | **Redis Sentinel at Phase 2, not Phase 4** | 🔴 CRITICAL | Phase 2+ | 4 hours |
| 2 | **State recovery procedure undefined** | 🔴 CRITICAL | Phase 1+ | 4 hours |
| 3 | **LLM fallback chain + caching** | 🟠 HIGH | Phase 2+ | 1 day |
| 4 | **Cost budget system at $7 scale** | 🟠 HIGH | Phase 1 | 4 hours |
| 5 | **MT5 data proxy service** | 🟠 HIGH | Phase 2+ | 1 day |
| 6 | **Phase 2 VPS undersized** | 🟠 HIGH | Phase 2 | Config change |

### 6.2 Gap Details & Recommended Fixes

#### Gap 1: Redis Sentinel at Phase 2

**Current:** Redis Sentinel defined at Phase 4 ($10K+)  
**Should be:** Phase 2 ($100)

**Implementation:**
```
Phase 1-2: Single Redis with AOF (acceptable for local dev)
Phase 2 (VPS): Redis Sentinel (3 processes on same VPS)
  - 1 primary + 2 replicas on same machine
  - Automatic failover in <5 seconds
  - Zero additional cost (same VPS)
Phase 3: Redis Sentinel on separate server
Phase 4: Redis Cluster (3 masters + 3 replicas)
```

**Why this matters:** At Phase 2, the system is doing live trading. A Redis crash without Sentinel means the system closes all positions and halts. With Sentinel, failover is automatic and transparent.

#### Gap 2: State Recovery Procedure

**Current:** Undefined  
**Should be:** Documented startup procedure

**Implementation:**
```python
async def startup_reconciliation():
    """Run on every system start."""
    
    # 1. Query broker for ground truth
    broker_positions = await broker.get_positions()
    broker_orders = await broker.get_pending_orders()
    
    # 2. Query database for last known state
    db_positions = await db.get_open_positions()
    db_orders = await db.get_pending_orders()
    
    # 3. Reconcile
    orphaned = set(db_positions) - set(broker_positions)
    unknown = set(broker_positions) - set(db_positions)
    
    if orphaned:
        logger.warning(f"Orphaned positions (in DB but not at broker): {orphaned}")
        await db.close_positions(orphaned, reason="reconciliation_orphaned")
    
    if unknown:
        logger.warning(f"Unknown positions (at broker but not in DB): {unknown}")
        await db.import_positions(unknown, source="reconciliation")
    
    # 4. Rebuild Redis state from DB
    await redis.flushdb()
    await rebuild_redis_from_db()
    
    # 5. Resume normal operation
    logger.info("Startup reconciliation complete")
```

#### Gap 3: LLM Fallback Chain

**Current:** No fallback, no caching, no timeout  
**Should be:** Resilient LLM pipeline

**Implementation:**
```python
class LLMFallbackChain:
    async def call(self, prompt: str, context: dict) -> LLMResponse:
        # 1. Check cache
        cache_key = hash(prompt + json.dumps(context, sort_keys=True))
        cached = await redis.get(f"llm_cache:{cache_key}")
        if cached:
            return LLMResponse.from_cache(cached)
        
        # 2. Try primary model
        try:
            response = await asyncio.wait_for(
                self.primary.call(prompt), timeout=5.0
            )
            await redis.setex(f"llm_cache:{cache_key}", 3600, response.serialize())
            return response
        except (asyncio.TimeoutError, APIError):
            pass
        
        # 3. Try secondary model
        try:
            response = await asyncio.wait_for(
                self.secondary.call(prompt), timeout=5.0
            )
            await redis.setex(f"llm_cache:{cache_key}", 3600, response.serialize())
            return response
        except (asyncio.TimeoutError, APIError):
            pass
        
        # 4. Return rule-based fallback
        return self.rule_based_fallback(context)
```

#### Gap 4: Cost Budget System

**Current:** Spread filter only  
**Should be:** Cumulative cost tracking

**Implementation:**
```python
class CostBudget:
    MAX_WEEKLY_COST_PCT = 5.0  # Max 5% of account per week on trading costs
    
    async def can_trade(self, estimated_cost: float, account: Account) -> bool:
        weekly_costs = await self.get_weekly_costs(account.id)
        remaining_budget = (account.balance * self.MAX_WEEKLY_COST_PCT / 100) - weekly_costs
        
        if estimated_cost > remaining_budget:
            return False  # Budget exhausted
        
        # Also check: estimated cost < 30% of expected profit
        expected_profit = self.estimate_expected_profit(...)
        if estimated_cost > expected_profit * 0.30:
            return False  # Cost too high relative to expected return
        
        return True
```

#### Gap 5: MT5 Data Proxy

**Current:** Market data goes through serialized Python MT5 API  
**Should be:** Separate data proxy service

**Implementation:**
```
Architecture:
  MT5DataProxy (separate process)
    ├── Polls MT5 every 100ms for tick data
    ├── Polls MT5 every 1m for candle data
    ├── Publishes to Redis Streams
    └── Handles all MT5 serialization in one place

  Trading Engine
    ├── Reads from Redis Streams (not directly from MT5)
    └── Sends orders through ZeroMQ bridge (already exists)
```

#### Gap 6: Phase 2 VPS Sizing

**Current:** Hetzner CX21 (2 CPU, 4GB RAM) at $7/mo  
**Should be:** Hetzner CX41 (8 CPU, 16GB RAM) at ~$30/mo

**Rationale:**
- FinBERT inference: ~2GB RAM
- Redis + PostgreSQL + TimescaleDB: ~2GB baseline
- Trading engine + 10 pairs: ~2GB
- Headroom for spikes: ~4GB
- **Total: ~10GB minimum, 16GB recommended**

**Cost impact:** $7/mo → $30/mo. On $100 capital, this is 30%/mo which is high. Alternative: limit to 3-5 pairs on CX21 until capital grows to $500+.

---

## 7. Comprehensive Scalability Scorecard

### 7.1 Dimension Scores

| Dimension | Score (1-10) | Notes |
|-----------|-------------|-------|
| **Pair Scalability** | 7/10 | Well-designed parallelism, but MT5 serialization and LLM latency are gaps |
| **Capital Scalability** | 8/10 | Excellent %-based design. Execution scaling path needs more detail. |
| **Failure Resilience** | 5/10 | Redis and PostgreSQL are critical SPOFs until Phase 3-4 |
| **Deployment Flexibility** | 8/10 | 5-phase roadmap is thoughtful. K8s transition risk is the main concern. |
| **Performance at Scale** | 6/10 | Critical path acceptable for 1-3 pairs, needs optimization for 10+ |
| **Data Scalability** | 9/10 | TimescaleDB + Redis + tiered storage is excellent |
| **Cost Efficiency** | 8/10 | Good phase-gated spending. $7 cost problem acknowledged but not mitigated. |
| **Operational Complexity** | 6/10 | Starts simple, but K8s jump is large. MT5/Wine is operationally fragile. |
| **Platform Scalability** | 8/10 | Unified server + shared API + design tokens = clean scaling |
| **Overall** | **7/10** | **Conditionally scalable. Address SPOFs and LLM bottleneck before 10+ pairs.** |

### 7.2 Phase-by-Phase Readiness

| Phase | Ready? | Blockers |
|-------|--------|----------|
| **Phase 1 ($7)** | ✅ YES | Cost drain mitigation needed |
| **Phase 2 ($100)** | 🟡 MOSTLY | Redis Sentinel, VPS sizing, state recovery |
| **Phase 3 ($10K)** | 🟡 MOSTLY | Multi-broker reconciliation, VaR implementation |
| **Phase 4 ($100K)** | 🟡 MOSTLY | FIX protocol, compliance reporting, stress testing |
| **Phase 5 ($1M+)** | 🟡 PLANNED | Institutional requirements are a separate project |

---

## 8. Final Recommendations

### 8.1 Before Phase 1 Deployment (Immediate)

| # | Recommendation | Effort | Impact |
|---|---------------|--------|--------|
| 1 | Define and implement `startup_reconciliation()` procedure | 4 hours | 🔴 Prevents state loss on crash |
| 2 | Implement cost budget tracking at $7 scale | 4 hours | 🟠 Prevents cost drain |
| 3 | Add Redis AOF persistence (verify it's enabled) | 30 min | 🔴 Prevents data loss |
| 4 | Document LLM timeout handling (5s hard limit) | 2 hours | 🟠 Prevents pipeline stalls |
| 5 | Define concurrency limits for parallel pipeline execution | 2 hours | 🟡 Prevents resource exhaustion |

### 8.2 Before Phase 2 (Short-Term)

| # | Recommendation | Effort | Impact |
|---|---------------|--------|--------|
| 6 | Add Redis Sentinel at Phase 2 (not Phase 4) | 4 hours | 🔴 Eliminates Redis SPOF |
| 7 | Upgrade Phase 2 VPS to CX41 (8 CPU, 16GB RAM) | Config change | 🟠 Provides headroom |
| 8 | Implement LLM response caching in Redis | 4 hours | 🟠 Reduces latency and cost |
| 9 | Implement MT5 data proxy service | 1 day | 🟠 Eliminates serialization bottleneck |
| 10 | Implement MT5 health check + auto-restart | 4 hours | 🟠 Reduces MT5 downtime |

### 8.3 Before Phase 3 (Medium-Term)

| # | Recommendation | Effort | Impact |
|---|---------------|--------|--------|
| 11 | Implement `SplitOrderCoordinator` for multi-broker orders | 1 week | 🟡 Enables safe multi-broker execution |
| 12 | Add streaming PostgreSQL replication | 1 day | 🔴 Eliminates database SPOF |
| 13 | Implement VaR calculation in risk governor | 3 days | 🟠 Required for institutional risk |
| 14 | Define 10 canonical stress test scenarios | 2 days | 🟠 Validates risk under extremes |
| 15 | Add dead letter queue consumer for failed events | 4 hours | 🟡 Prevents silent event loss |

---

## 9. Conclusion

The Alpha Stack architecture has a **solid scalability foundation**. The event-driven, modular design with progressive complexity is the right approach. The data storage layer is particularly well-designed — TimescaleDB hypertables, Redis hot cache, tiered retention, and compression policies scale cleanly from $7 to institutional.

The platform consolidation fix (`fix_platform_consolidation.md`) correctly unifies the three platform silos, which actually **simplifies** scaling by eliminating backend drift.

**The 6 remaining gaps are all addressable with well-defined fixes.** None require architectural changes — they're implementation-level additions (Redis Sentinel, state recovery, LLM caching, cost budget, MT5 proxy, VPS sizing).

**With these 6 gaps addressed, the system can credibly scale from $7 to $100K+.**

The scaling path is: same PostgreSQL schema, same Redis patterns, same API surface, same Docker Compose config — just more pairs, more brokers, more resources, and more automation at each phase. The architecture doesn't change, only the parameters do.

---

*This verification report confirms the Alpha Stack architecture's scalability from $7 micro-accounts to institutional deployment. The critical actions are: (1) add Redis HA early, (2) implement state recovery, (3) add LLM resilience, and (4) implement cost budget tracking. With these addressed, the system is ready for progressive scaling.*
