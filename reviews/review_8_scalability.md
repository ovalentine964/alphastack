# Alpha Stack — Scalability Architecture Review

> **Reviewer:** Scalability Architecture Review Agent  
> **Date:** 2026-07-11  
> **Scope:** Validate scalability from $7 micro-account to institutional ($100K+) deployment  
> **Documents Reviewed:** `architecture_system.md`, `architecture_data_storage.md`, `architecture_trading_engine.md`, `architecture_risk.md`, `architecture_broker_routing.md`  
> **Severity Levels:** 🔴 CRITICAL | 🟠 HIGH | 🟡 MEDIUM | 🟢 LOW | ✅ PASS

---

## Executive Summary

The Alpha Stack architecture demonstrates **strong foundational scalability design**. The event-driven, modular approach with progressive complexity scaling is well-conceived. However, several concrete scalability risks exist in the transition from single-pair/$7 to multi-pair/institutional operation. This review identifies **3 critical issues**, **5 high-severity concerns**, and **8 medium/low observations**, with actionable recommendations for each.

**Overall Scalability Verdict: CONDITIONALLY SCALABLE** — the architecture *can* scale, but specific bottlenecks in the event bus, agent orchestration, and single-process assumptions must be addressed before crossing the ~$10K/10-pair threshold.

---

## 1. Pair Scalability: 1 Pair → 10+ Pairs

### 1.1 VMPM Pipeline Per-Pair Execution

| Aspect | Assessment | Verdict |
|--------|-----------|---------|
| Pipeline parallelism | Each pair runs an independent 16-step VMPM pipeline. Steps are async (`asyncio`). | ✅ PASS |
| Strategy context isolation | `StrategyContext` is per-pair, per-analysis. No cross-pair state leakage. | ✅ PASS |
| ML model sharing | FinBERT, regime classifier, S/R model are shared across pairs. Inference is stateless. | ✅ PASS |
| Resource contention | At 10+ pairs, concurrent ML inference + 16 pipeline steps × N pairs = significant CPU/memory. | 🟡 MEDIUM |

**Finding:** The VMPM pipeline is architecturally parallelizable (each pair gets its own `StrategyContext`), but the system document does not specify concurrency limits or backpressure mechanisms.

**Risk:** With 10 pairs × 16 steps × ~50-200ms per LLM-dependent step, a single Python `asyncio` event loop could saturate. The architecture uses `Python asyncio` for orchestration (L4), which is single-threaded.

**Recommendation:**
- Define explicit concurrency limits: `max_concurrent_pipelines = config.pairs * 1` with semaphore-based backpressure
- Profile the GIL-bound path: Steps 1-4 (context), 5-8 (structure) involve LLM calls (I/O-bound, fine for asyncio), but Steps 9-12 (entry confirmation, indicator calculation) are CPU-bound
- The Rust-backed indicators (`ta_core.rs` via PyO3) mitigate CPU-bound steps — **verify this is actually used for all CPU-intensive calculations**
- Consider `asyncio.TaskGroup` with `max_concurrent` for pipeline orchestration

### 1.2 Multi-Timeframe Analysis

| Aspect | Assessment | Verdict |
|--------|-----------|---------|
| Timeframe hierarchy | Architecture defines M1→D1 with continuous aggregates. Each timeframe is independent. | ✅ PASS |
| Data volume scaling | 10 pairs × 6 timeframes × continuous aggregates = 60 aggregate streams. TimescaleDB handles this natively. | ✅ PASS |
| Cross-timeframe confluence | Architecture mentions multi-TF analysis but doesn't specify how confluence scores aggregate across TFs at scale. | 🟡 MEDIUM |

### 1.3 Pair Correlation at Scale

| Aspect | Assessment | Verdict |
|--------|-----------|---------|
| Correlation monitoring | Risk architecture defines `max_correlation: 0.7` and correlation caps. | ✅ PASS |
| Computational cost | Correlation matrix for N pairs is O(N²). At 50 pairs, this is 1,225 pairwise calculations. | 🟡 MEDIUM |
| Real-time updates | Architecture doesn't specify correlation update frequency or computation method at scale. | 🟡 MEDIUM |

**Recommendation:** Use rolling Pearson correlation on 1h returns with 90-day window, computed as a materialized view refreshed every 15 minutes. For 50 pairs, a correlation matrix fits in Redis hash (~10KB) and is cheap to compute.

---

## 2. Capital Scalability: $7 → $100K+

### 2.1 Position Sizing Scaling

| Capital | Position Size | Execution Impact | Verdict |
|---------|--------------|-----------------|---------|
| $7 | 0.01 lot ($0.10/pip) | Negligible market impact, spread is dominant cost | ✅ PASS |
| $100 | 0.05-0.10 lot | Still micro-lot, no impact | ✅ PASS |
| $10K | 0.5-2.0 lots | Slippage becomes measurable (0.1-0.5 pips) | ✅ PASS |
| $100K | 5-20 lots | **Significant market impact on minors/exotics. TWAP required.** | 🟠 HIGH |
| $1M+ | 50-200 lots | **Requires SOR, dark pools, VWAP. Partial fills expected.** | 🔴 CRITICAL |

**Finding:** The architecture correctly identifies TWAP and SOR for larger sizes (Phase 4/5), but the **execution scaling path is underspecified**. The broker routing architecture defines a Smart Order Router (SOR) with multi-broker splitting, but:

1. **No minimum viable order size per broker is defined.** MT5 via FXPesa may have minimum lot sizes that make micro-management impossible at $100K+.
2. **Order splitting across brokers** is designed but the **reconciliation logic** for partial fills across multiple brokers is not detailed.
3. **The latency budget doesn't account for multi-broker coordination.** If Broker A fills in 50ms and Broker B takes 200ms, the system must handle the state inconsistency.

**Recommendation:**
- Define broker-specific minimum/maximum order sizes in the BCA configuration
- Implement a `SplitOrderCoordinator` that tracks child orders across brokers and reconciles fills
- Add a "settled" state to the order lifecycle for multi-broker fills
- At $100K+, implement pre-trade market impact estimation (Almgren-Chriss model or simplified)

### 2.2 Risk Scaling

| Aspect | Assessment | Verdict |
|--------|-----------|---------|
| % risk per trade | Scales linearly with capital. 2% of $7 = $0.14. 2% of $100K = $2,000. Math is sound. | ✅ PASS |
| Absolute drawdown limits | `max_drawdown: 0.15` (15%) = $1.05 at $7, $15,000 at $100K. Reasonable at all scales. | ✅ PASS |
| Circuit breakers | Defined with 4 stages. Scale-agnostic by design (%-based). | ✅ PASS |
| Correlation limits | `max_correlation: 0.7` — static threshold may be too permissive at institutional scale. | 🟡 MEDIUM |
| VaR / stress testing | Architecture mentions VaR for Phase 4+ but no implementation details. | 🟠 HIGH |

**Finding:** The risk architecture is **well-designed for scalability** — all limits are percentage-based, not absolute. However, institutional-grade risk requires:

1. **Value at Risk (VaR)** — mentioned but not designed. At $100K+, regulators and risk committees expect VaR reporting.
2. **Stress testing** — the architecture mentions "stress testing" in the risk governor but defines no scenarios (e.g., 2015 CHF depeg, 2020 COVID crash, 2022 LUNA collapse).
3. **Margin management** — at scale, margin utilization across multiple brokers needs centralized tracking. The `accounts` table tracks per-broker margin but no cross-broker margin aggregation exists.

**Recommendation:**
- Implement parametric VaR (95% and 99% confidence) as a continuous aggregate in the risk governor
- Define 10 canonical stress scenarios with historical price moves
- Add `cross_broker_margin` field to the risk governor's state, summing margin across all broker connections
- At $50K+, add intraday margin monitoring with automatic position reduction at 80% margin utilization

### 2.3 Cost Scaling

| Capital | Spread Cost (EUR/USD) | As % of Capital | Impact | Verdict |
|---------|----------------------|-----------------|--------|---------|
| $7, 0.01 lot | ~$0.10-0.15 | 1.4-2.1% per trade | **Survival risk** — 46 trades before costs drain capital | 🟠 HIGH |
| $100, 0.05 lot | ~$0.50-0.75 | 0.5-0.75% per trade | Significant but manageable | 🟡 MEDIUM |
| $10K, 1.0 lot | ~$10-15 | 0.1-0.15% per trade | Normal trading costs | ✅ PASS |
| $100K, 10 lots | ~$100-150 | 0.1-0.15% per trade | Normal, but slippage adds | ✅ PASS |

**Finding:** The architecture acknowledges the $7 cost problem in the risk document ("$7 account has ~46 trades before costs drain capital") but **no specific cost mitigation strategy is implemented**. The spread filter (`spread_filter_multiplier: 2.0`) helps but doesn't solve the fundamental problem of high relative costs at micro scale.

**Recommendation:**
- At $7-$100: Implement a "cost budget" — limit total weekly trading costs to <5% of account
- Track cost-per-trade in the `trades` table (already has `commission` and `slippage_pips` fields — use them)
- Add a cost-aware signal filter: reject trades where estimated total cost (spread + commission + expected slippage) > 30% of expected profit

---

## 3. Single Points of Failure (SPOF) Analysis

### 3.1 Critical SPOFs

| Component | SPOF? | Impact | Current Mitigation | Gap | Severity |
|-----------|-------|--------|-------------------|-----|----------|
| **Redis (Event Bus)** | 🔴 YES | All inter-module communication stops. System enters safe mode. | Single instance. AOF + RDB persistence. | **No Redis Sentinel or Cluster until Phase 4.** | 🔴 CRITICAL |
| **PostgreSQL** | 🔴 YES | No order/trade recording. No risk state. | WAL archiving from Phase 2. | **No read replica until Phase 3. No HA until Phase 4.** | 🔴 CRITICAL |
| **MT5 Terminal** | 🟠 YES | No forex data, no order execution. Wine-based MT5 is inherently fragile. | Failover to backup broker if available. | **No automated MT5 restart. No health check for Wine process.** | 🟠 HIGH |
| **Python Trading Engine** | 🟠 YES | All processing stops. | Docker restart policy. | **No hot standby. No state recovery on restart.** | 🟠 HIGH |
| **LLM API (DeepSeek/Qwen)** | 🟠 YES | Steps relying on LLM inference fail. Strategy pipeline stalls. | Unknown (not documented). | **No fallback model. No cached responses. No timeout handling.** | 🟠 HIGH |
| **Internet Connection** | 🟠 YES | No market data, no execution. | N/A (hosting-dependent). | **No offline mode. No data buffer for brief disconnections.** | 🟠 HIGH |

### 3.2 SPOF Mitigation Recommendations

**Redis (Event Bus) — HIGHEST PRIORITY:**
```
Phase 1-2: Single Redis with AOF (acceptable for $7-$1K)
Phase 3: Redis Sentinel (3 nodes: 1 primary + 2 replicas) — automatic failover
Phase 4: Redis Cluster (3 masters + 3 replicas) — sharded + HA
```

**Immediate action:** Add Redis Sentinel at Phase 2 ($100), not Phase 4. The cost is minimal (2 additional Redis processes on same VPS) and the risk reduction is massive.

**PostgreSQL:**
```
Phase 1-2: Single instance with WAL archiving (acceptable)
Phase 3: Streaming replication (1 primary + 1 read replica)
Phase 4: Patroni-based HA cluster
```

**LLM API Resilience:**
- Implement a `LLMFallbackChain`: primary model → secondary model → cached response → skip step
- Cache recent LLM responses in Redis with 1-hour TTL for identical inputs
- Set hard timeouts (5s for LLM calls) with graceful degradation to rule-based fallback

**MT5 Terminal:**
- Implement a health check process that monitors the Wine/MT5 process
- Auto-restart MT5 on crash with exponential backoff
- Log MT5 connection state to Redis for cross-module awareness

### 3.3 State Recovery on Restart

**Finding:** The architecture does not describe **state recovery procedures** after a crash. Key questions:
1. How does the system know which positions are open after a restart?
2. How does it rebuild the event bus state?
3. How does it reconcile in-flight orders?

**Recommendation:**
- On startup, query broker APIs for current positions and orders (source of truth)
- Rebuild Redis state from PostgreSQL (positions, account balances)
- Skip any signals/orders that were in-flight during crash (broker orders remain active with stops/TPs)
- Implement a `startup_reconciliation()` procedure in the Execution Agent

---

## 4. Deployment Architecture Scalability

### 4.1 Phase 1: Local Development ($7)

| Aspect | Assessment | Verdict |
|--------|-----------|---------|
| Docker Compose on local machine | Appropriate for development. All services co-located. | ✅ PASS |
| Resource requirements | 4 CPU, 8GB RAM, 50GB SSD — sufficient for 1-3 pairs. | ✅ PASS |
| MT5 via Wine | Fragile but functional. Not scalable. | 🟡 MEDIUM |
| Monitoring | Prometheus + Grafana on same machine — acceptable for dev. | ✅ PASS |

### 4.2 Phase 2: VPS ($100-$10K)

| Aspect | Assessment | Verdict |
|--------|-----------|---------|
| Hetzner CX31 (4 CPU, 8GB RAM) | **Insufficient for 10+ pairs with ML inference.** | 🟠 HIGH |
| Single VPS | Single point of failure. No redundancy. | 🟡 MEDIUM |
| MT5 on VPS via Wine | Wine on headless VPS requires Xvfb. Known stability issues. | 🟠 HIGH |
| Cost | $15/mo — reasonable for the capital level. | ✅ PASS |

**Finding:** The Phase 2 VPS specification (4 CPU, 8GB RAM) is undersized for the described workload:
- 10 pairs × VMPM pipeline × LLM inference = significant CPU
- FinBERT inference requires ~2GB RAM
- Redis + PostgreSQL + TimescaleDB + trading engine = ~4GB baseline
- Total: ~6-7GB baseline, leaving <1GB headroom

**Recommendation:**
- Phase 2 VPS should be at least **8 CPU, 16GB RAM** (Hetzner CX41, ~$30/mo)
- Or: separate database server from application server at the 5+ pair mark
- Monitor memory usage with alerts at 80% utilization

### 4.3 Phase 3: Cloud Kubernetes ($10K-$100K)

| Aspect | Assessment | Verdict |
|--------|-----------|---------|
| K8s with 2 replicas per service | Appropriate for HA. | ✅ PASS |
| Managed PostgreSQL + Redis | Reduces operational burden. | ✅ PASS |
| GPU node for ML inference | Required for FinBERT at scale. | ✅ PASS |
| Cost estimate ($80-150/mo) | Reasonable. | ✅ PASS |
| Multi-broker orchestration | Requires careful state management in K8s (pods are ephemeral). | 🟡 MEDIUM |

**Finding:** The transition from Docker Compose to Kubernetes is a **significant operational complexity jump**. The architecture shows K8s at Phase 3 ($10K) but:
1. Stateful services (PostgreSQL, TimescaleDB, Redis) in K8s require StatefulSets, PVCs, and careful storage class selection
2. The MT5 Wine bridge does not containerize well
3. Network latency between pods adds to the critical path (~125-425ms already)

**Recommendation:**
- Use managed database services (RDS, Cloud SQL) instead of self-hosted in K8s
- Keep MT5 on a dedicated VM outside K8s, connected via gRPC/ZeroMQ
- Consider Docker Compose on a dedicated server as an intermediate step between Phase 2 and K8s
- Implement pod disruption budgets and anti-affinity rules for trading engine pods

### 4.4 Phase 4: Institutional ($100K+)

| Aspect | Assessment | Verdict |
|--------|-----------|---------|
| Multi-region deployment | London primary + Frankfurt DR. Appropriate for forex. | ✅ PASS |
| Broker colocation | Required for <10ms latency. | ✅ PASS |
| Cost estimate ($500-2000/mo) | Proportional to capital. | ✅ PASS |
| FIX protocol | Institutional standard. Well-defined connector interface. | ✅ PASS |
| DR region | Architecture shows DR but no RPO/RTO targets for failover. | 🟡 MEDIUM |

---

## 5. Performance Bottlenecks

### 5.1 Critical Path Latency Analysis

```
Market Data → VMPM Pipeline (Steps 1-16) → Risk Agent → Execution Agent → Order Manager → Broker
  ~5ms           ~50-200ms (LLM steps)       ~5ms           ~5ms            ~10ms        ~50-200ms
  
Total: ~125-425ms (forex), ~200-600ms (crypto with exchange latency)
```

| Bottleneck | Latency | Scalability Impact | Severity |
|-----------|---------|-------------------|----------|
| **LLM inference (Steps 1-4, 7)** | 50-200ms per call | **Does not scale with pairs.** 10 pairs × 4 LLM steps = 40 sequential calls or massive parallelism. | 🟠 HIGH |
| **Redis Streams fan-out** | <1ms | Scales well. Redis handles 100K+ msgs/sec easily. | ✅ PASS |
| **TimescaleDB queries** | 5-50ms | Scales with proper indexing. Compression helps. | ✅ PASS |
| **MT5 via ZeroMQ** | 50-200ms | Single-threaded MT5 API. **Serialized access is a bottleneck at 10+ pairs.** | 🟠 HIGH |
| **Broker API rate limits** | Variable | CCXT: 10-20 req/s per exchange. OANDA: 120 req/min. Can throttle at scale. | 🟡 MEDIUM |

### 5.2 LLM Inference Bottleneck (CRITICAL PATH)

**Finding:** The VMPM pipeline has **at least 4 LLM-dependent steps** (Steps 1, 2, 3, 7 per the trading engine architecture). Each LLM call takes 50-200ms. For a single pair, this is manageable. For 10 pairs running concurrently:

- Sequential: 10 pairs × 4 steps × 150ms = **6 seconds** (unacceptable)
- Parallel (asyncio): 4 steps × 150ms = **600ms** (acceptable, but GIL contention on model loading)
- Parallel (multiprocess): **150ms** (ideal, but requires process pool management)

**Recommendation:**
- Implement LLM call batching: group similar prompts across pairs into a single batch inference request
- Use a local inference server (vLLM, TGI) for FinBERT and smaller models to eliminate API latency
- Cache LLM responses for identical market conditions (same fundamental data + same session = same bias assessment)
- Set per-pipeline LLM timeout budget: max 500ms total for all LLM calls in a pipeline run

### 5.3 MT5 Serialization Bottleneck

**Finding:** The architecture notes "MT5 Python API" uses "Serialized access (single-threaded)" — this means only one pair can query MT5 at a time. At 10 pairs, this creates a queuing bottleneck.

**Current mitigation:** ZeroMQ bridge (`zmq_bridge.py`) for signal passing.

**Gap:** The ZeroMQ bridge handles signal delivery to the EA, but market data collection and position queries still go through the Python MT5 API, which is serialized.

**Recommendation:**
- Implement a `MT5DataProxy` service that runs in its own process, polls MT5 on a schedule, and publishes to Redis Streams
- Use ZeroMQ for all MT5 communication (bidirectional): data requests go out, responses come back asynchronously
- At Phase 3+, consider switching to OANDA REST API for forex data (HTTP-based, no serialization)

### 5.4 Database Write Contention

| Table | Write Rate (10 pairs) | Concern | Severity |
|-------|----------------------|---------|----------|
| `ticks` | 10-100 ticks/sec × 10 = 100-1000/sec | TimescaleDB hypertables handle this easily. | ✅ PASS |
| `market_data` | 10 pairs × 6 TFs = 60 writes/min | Negligible. | ✅ PASS |
| `orders` | Bursty: 1-10 orders/min | Low volume. | ✅ PASS |
| `trades` | 1-10/day | Negligible. | ✅ PASS |
| `system_events` | 100-1000/min | **High volume for audit trail.** Consider batching. | 🟡 MEDIUM |

**Recommendation:** Batch `system_events` writes (buffer in Redis, flush to PostgreSQL every 5 seconds). TimescaleDB handles high write volume, but reducing write frequency reduces WAL pressure.

### 5.5 Memory Pressure at Scale

| Component | Phase 1 (1 pair) | Phase 3 (10 pairs) | Phase 4 (50 pairs) |
|-----------|------------------|--------------------|--------------------|
| Redis | ~50MB | ~256MB | ~2GB |
| PostgreSQL | ~200MB | ~2GB | ~8GB |
| Trading Engine | ~500MB | ~2GB | ~4GB |
| ML Models (FinBERT) | ~1GB | ~1GB (shared) | ~1GB (shared) + GPU |
| **Total** | ~1.75GB | ~5.25GB | ~15GB |

**Verdict:** Memory is not a bottleneck through Phase 3 on a 16GB machine. Phase 4 requires 32GB+ or distributed deployment. ✅ PASS

---

## 6. Scaling Risks

### 6.1 Risk Matrix

| Risk | Likelihood | Impact | Mitigation | Residual Risk | Severity |
|------|-----------|--------|-----------|--------------|----------|
| **Redis failure causes total system halt** | Medium | Critical | Add Sentinel at Phase 2 | Low | 🔴 CRITICAL |
| **LLM API outage stalls strategy pipeline** | Medium | High | Fallback chain + cache | Medium | 🟠 HIGH |
| **MT5 Wine process crashes on VPS** | High | High | Health check + auto-restart | Medium | 🟠 HIGH |
| **Cost drain at $7 scale (46-trade limit)** | High | High | Cost budget + trade limits | Medium | 🟠 HIGH |
| **Single VPS failure loses all services** | Low | Critical | External backups + quick recovery procedure | Medium | 🟠 HIGH |
| **Correlation risk at 10+ pairs** | Medium | Medium | Rolling correlation monitor | Low | 🟡 MEDIUM |
| **Python GIL limits parallel pipeline execution** | Medium | Medium | Rust-backed hot paths + process pool | Low | 🟡 MEDIUM |
| **Database migration SQLite→PostgreSQL breaks something** | Low | Medium | Alembic versioned migrations | Low | 🟡 MEDIUM |
| **K8s adds operational complexity at Phase 3** | Medium | Medium | Managed K8s or stay on Docker Compose longer | Low | 🟡 MEDIUM |
| **Multi-broker order reconciliation errors** | Medium | High | Dedicated reconciliation service | Medium | 🟡 MEDIUM |
| **Latency exceeds acceptable thresholds at scale** | Low | Medium | Profile and optimize critical path | Low | 🟢 LOW |
| **Storage exceeds disk at Phase 3+** | Low | Low | Compression + retention policies | Minimal | 🟢 LOW |

### 6.2 Scaling Transition Risks

**Phase 1 → Phase 2 ($7 → $100):**
- Risk: Migration from local Docker to VPS Docker may expose environment differences
- Mitigation: Docker Compose configs should be environment-agnostic. Test deployment script.

**Phase 2 → Phase 3 ($100 → $10K):**
- Risk: Adding brokers (CCXT) introduces new failure modes (exchange API instability, rate limits)
- Mitigation: Broker routing architecture already defines failover. Test with paper trading first.

**Phase 3 → Phase 4 ($10K → $100K):**
- Risk: The jump from Docker Compose to Kubernetes is the **highest-risk transition**
- Mitigation: Consider an intermediate step: Docker Compose on a beefy dedicated server with managed DB

**Phase 4 → Phase 5 ($100K → $1M+):**
- Risk: Institutional requirements (FIX protocol, colocation, compliance) are fundamentally different
- Mitigation: This is a separate project, not a scaling step. Budget 6-12 months for institutional readiness.

### 6.3 Technical Debt Scaling Risks

| Debt Item | Current State | Scaling Impact | Priority |
|-----------|--------------|----------------|----------|
| MT5 via Wine | Fragile, hard to containerize | Blocks K8s migration | 🟠 HIGH |
| No state recovery on restart | Undefined | Crashes at scale lose more state | 🟠 HIGH |
| LLM responses not cached | Every inference is fresh | Wastes money and adds latency at scale | 🟡 MEDIUM |
| No connection pooling documented | Single connections assumed | Connection exhaustion at 10+ pairs | 🟡 MEDIUM |
| Event bus has no dead letter queue | Failed events are lost | Silent failures at scale | 🟡 MEDIUM |

---

## 7. Scalability Validation Checklist

### 7.1 Can the system scale from 1 pair to 10+ pairs?

**YES, with caveats.**

| Requirement | Status | Notes |
|------------|--------|-------|
| Independent per-pair pipeline execution | ✅ Designed | `StrategyContext` is per-pair |
| Parallel data collection | ✅ Designed | Async collectors per source |
| Shared ML models | ✅ Designed | Stateless inference |
| Resource management | ⚠️ Gap | No concurrency limits or backpressure defined |
| MT5 serialization | ⚠️ Gap | Single-threaded MT5 API is a bottleneck |
| Memory management | ✅ Adequate | 16GB handles 10 pairs easily |

### 7.2 Can it scale from $7 to $100K+?

**YES, with caveats.**

| Requirement | Status | Notes |
|------------|--------|-------|
| Position sizing scales | ✅ Designed | % -based, scales with capital |
| Risk limits scale | ✅ Designed | All limits are % -based |
| Execution scales | ⚠️ Gap | TWAP/SOR designed but not implemented; reconciliation untested |
| Cost management | ⚠️ Gap | No cost budget system at $7 scale |
| Broker diversity | ✅ Designed | BCA abstraction supports 5+ brokers |
| Compliance/audit | ✅ Designed | Full audit trail in ClickHouse |

### 7.3 Are there single points of failure?

**YES — 2 critical, 4 high-severity.** See Section 3.

### 7.4 Is the deployment architecture scalable?

**YES, progressively.** The 5-phase deployment roadmap is well-structured. Key gap: the Phase 2→3 jump (Docker Compose → K8s) is too large; an intermediate step is recommended.

### 7.5 Are there performance bottlenecks?

**YES — 2 significant:** LLM inference latency on the critical path, and MT5 serialization. Both are addressable with the recommendations in Section 5.

### 7.6 What scaling risks exist?

**12 risks identified.** 2 critical (Redis SPOF, LLM outage), 4 high (MT5 fragility, cost drain at $7, VPS SPOF, state recovery), 5 medium, 1 low. See Section 6.1.

---

## 8. Recommendations Summary

### Immediate (Before Phase 1 Deployment)

| # | Recommendation | Effort | Impact |
|---|---------------|--------|--------|
| 1 | Define concurrency limits for parallel pipeline execution | 2 hours | Prevents resource exhaustion |
| 2 | Implement LLM call timeout (5s hard limit) with graceful fallback | 4 hours | Prevents pipeline stalls |
| 3 | Document state recovery procedure for crash scenarios | 4 hours | Enables reliable restarts |
| 4 | Add Redis AOF persistence (already in config — verify it's enabled) | 30 minutes | Prevents data loss on Redis crash |
| 5 | Implement cost budget tracking at $7 scale | 4 hours | Prevents cost drain |

### Short-Term (Before Phase 2)

| # | Recommendation | Effort | Impact |
|---|---------------|--------|--------|
| 6 | Add Redis Sentinel (3 nodes) at Phase 2 | 4 hours | Eliminates Redis SPOF |
| 7 | Implement MT5 health check + auto-restart | 4 hours | Reduces MT5 downtime |
| 8 | Cache LLM responses in Redis (1h TTL) | 4 hours | Reduces latency and API costs |
| 9 | Add MT5 data proxy service (separate process) | 1 day | Eliminates MT5 serialization bottleneck |
| 10 | Upgrade Phase 2 VPS spec to 8 CPU, 16GB RAM | 0 (config change) | Provides headroom for 10 pairs |

### Medium-Term (Before Phase 3)

| # | Recommendation | Effort | Impact |
|---|---------------|--------|--------|
| 11 | Implement `SplitOrderCoordinator` for multi-broker orders | 1 week | Enables safe multi-broker execution |
| 12 | Add streaming PostgreSQL replication | 1 day | Eliminates database SPOF |
| 13 | Implement VaR calculation in risk governor | 3 days | Required for institutional risk reporting |
| 14 | Define 10 canonical stress test scenarios | 2 days | Validates risk under extreme conditions |
| 15 | Add dead letter queue for failed event processing | 4 hours | Prevents silent event loss |

### Long-Term (Before Phase 4)

| # | Recommendation | Effort | Impact |
|---|---------------|--------|--------|
| 16 | Replace Redis Streams with Kafka for event sourcing | 2 weeks | Durable, replayable event log |
| 17 | Implement FIX protocol connector | 2 weeks | Institutional execution |
| 18 | Add cross-broker margin aggregation | 3 days | Required for multi-broker risk management |
| 19 | Implement Almgren-Chriss market impact model | 1 week | Required for large order execution |
| 20 | Add compliance-grade audit reporting | 1 week | Required for institutional clients |

---

## 9. Scalability Score Card

| Dimension | Score (1-10) | Notes |
|-----------|-------------|-------|
| **Pair Scalability** | 7/10 | Well-designed parallelism, but MT5 serialization and LLM latency are gaps |
| **Capital Scalability** | 8/10 | Excellent %-based design. Execution scaling path needs more detail. |
| **Failure Resilience** | 5/10 | Redis and PostgreSQL are critical SPOFs until Phase 3-4 |
| **Deployment Flexibility** | 8/10 | 5-phase roadmap is thoughtful. K8s transition risk is the main concern. |
| **Performance at Scale** | 6/10 | Critical path is acceptable for 1-3 pairs but needs optimization for 10+ |
| **Data Scalability** | 9/10 | TimescaleDB + Redis + tiered storage is excellent. Compression and retention are well-designed. |
| **Cost Efficiency** | 7/10 | Good phase-gated spending. $7 cost problem acknowledged but not mitigated. |
| **Operational Complexity** | 6/10 | Starts simple (Docker Compose), but K8s jump is large. MT5/Wine is operationally fragile. |
| **Overall** | **7/10** | **Conditionally scalable. Address SPOFs and LLM bottleneck before 10+ pairs.** |

---

*This review validates that the Alpha Stack architecture has a solid scalability foundation. The event-driven, modular design with progressive complexity is the right approach. The critical actions are: (1) add Redis HA early, (2) implement LLM resilience, and (3) define state recovery procedures. With these addressed, the system can credibly scale from $7 to $100K+.*
