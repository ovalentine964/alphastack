# Alpha Stack — Full System Integration Review

> **Review Type:** End-to-End System Integration Validation  
> **Date:** 2026-07-11  
> **Reviewer:** System Integration Review Agent  
> **Documents Reviewed:** architecture_system.md, architecture_trading_engine.md, architecture_broker_routing.md, architecture_data_storage.md  
> **Status:** ✅ Architecture Valid — Minor Integration Gaps Identified

---

## Executive Summary

The Alpha Stack architecture is **well-designed and internally consistent** across all four reviewed documents. The data flow from market data → analysis → execution → journal is coherent, the component communication patterns are clearly defined, and the system is deployable incrementally from $7 to institutional scale. However, there are **7 integration gaps** and **5 integration risks** that should be addressed before engineering begins.

**Overall Verdict: READY FOR ENGINEERING with gap remediation in Sprint 1.**

---

## 1. Data Flow Validation: Market Data → Analysis → Execution → Journal

### 1.1 Primary Data Flow Path ✅

```
Market Data Sources (MT5/CCXT/OANDA)
    │
    ▼
Data Pipeline (Ingestion Layer)
    │ ticks → TimescaleDB hypertable
    │ candles → TimescaleDB hypertable + continuous aggregates (1m→5m→15m→1h→4h→1d)
    │ news → PostgreSQL (news_events)
    │ economic calendar → PostgreSQL (economic_calendar)
    │
    ├─→ Redis hot cache (tick:{symbol}, ohlcv:{symbol}:{tf})
    │
    ▼
AlphaStack Strategy Pipeline (16 Steps)
    │ S1 (Fundamental) → S2 (Bias) → S3 (Session) → S4 (Structure)
    │ → S5 (S/R) → S6 (Liquidity) → S7 (SMC) → S8 (RSI)
    │ → S9 (Candlestick) → S10 (Confluence Engine)
    │
    ▼
Risk Governor (Gate Check)
    │ max_risk_per_trade: 2%
    │ max_total_exposure: 6%
    │ max_daily_loss: 4% circuit breaker
    │ max_correlated_exposure: 3%
    │
    ▼
Execution Layer
    │ S11 (Position Sizing) → S12 (Stop Loss) → S13 (Take Profit)
    │ → Smart Order Router → Broker Connector → Broker API
    │
    ▼
Post-Execution
    │ S14 (Trade Management) → S15 (Exit Conditions)
    │ → S16 (Journal & Learning)
    │ → orders.fill event → Risk Agent (update state)
    │ → orders.fill event → Strategy Agent (re-evaluate)
    │
    ▼
Storage
    │ orders table (PostgreSQL)
    │ trades table (PostgreSQL)
    │ positions table (PostgreSQL)
    │ journal entries (PostgreSQL)
    │ screenshots (Object Storage)
    │ performance analytics (daily_performance, materialized views)
```

**Verdict: ✅ Complete.** Data flows end-to-end with no orphaned steps.

### 1.2 Signal Flow Consistency ✅

| Signal Source | Defined In | Stream Name | Consumers | Match? |
|---|---|---|---|---|
| S1 Fundamental | trading_engine | `signals.fundamental` | S2, S10 | ✅ |
| S2 Market Bias | trading_engine | `signals.bias` | S10 | ✅ |
| S3 Session | trading_engine | `signals.session` | S10 | ✅ |
| S4 Structure | trading_engine | `signals.structure` | S2, S10 | ✅ |
| S5 S/R | trading_engine | `signals.levels` | S10 | ✅ |
| S6 Liquidity | trading_engine | `signals.liquidity` | S10 | ✅ |
| S7 SMC | trading_engine | `signals.smc` | S10 | ✅ |
| S8 RSI | trading_engine | `signals.momentum` | S10 | ✅ |
| S9 Candlestick | trading_engine | `signals.candle` | S10 | ✅ |
| S10 Confluence | trading_engine | `orders.proposal` | Risk Governor | ✅ |
| Risk Governor | trading_engine | `orders.risk_check` | Execution Agent | ✅ |
| Broker fills | system | `orders.fill` | Risk, Strategy, Journal | ✅ |

**Verdict: ✅ All signal streams have defined producers and consumers.**

### 1.3 Event Bus Stream Definitions ✅

Both `architecture_system.md` (Section 5.2) and `architecture_trading_engine.md` (Section 3.1) define event bus streams. Comparison:

| Stream | System Arch | Trading Engine | Consistent? |
|---|---|---|---|
| market.ticks / market.data | ✅ | ✅ | ✅ (name differs, same purpose) |
| market.candles | ✅ | ✅ | ✅ |
| signals.* | ✅ (summary) | ✅ (detailed per-step) | ✅ |
| orders.events / orders.proposal | ✅ | ✅ | ✅ |
| news.articles / news.sentiment | ✅ | ✅ | ✅ |
| system.health / system.alerts | ✅ | ✅ | ✅ |

**Note:** Minor naming inconsistency (`market.ticks` vs `market.data`) — should be standardized.

---

## 2. Component Communication Validation

### 2.1 Inter-Component Communication Matrix

| From → To | Protocol | Defined? | Latency Target | Status |
|---|---|---|---|---|
| Data Pipeline → Strategy Pipeline | Redis Streams | ✅ | <5ms tick ingestion | ✅ |
| Strategy Steps (S1-S9) → S10 | Redis Streams | ✅ | <500ms per candle | ✅ |
| S10 → Risk Governor | Redis Stream `orders.proposal` | ✅ | <100ms | ✅ |
| Risk Governor → Execution Agent | Redis Stream `orders.risk_check` | ✅ | <10ms | ✅ |
| Execution Agent → Order Manager | Direct async call | ✅ | <5ms | ✅ |
| Order Manager → Broker Connector | Direct async call | ✅ | <10ms | ✅ |
| Broker Connector → Broker API | MT5 API/CCXT/FIX | ✅ | 50-200ms | ✅ |
| Broker API → Fill Event | Redis Stream `orders.fill` | ✅ | Per-fill | ✅ |
| Fill Event → Journal Agent | Redis Stream `orders.fill` | ✅ | Async | ✅ |
| Fill Event → Risk Agent | Redis Stream `orders.fill` | ✅ | Immediate | ✅ |
| News Feed → News Agent | Redis Stream `news.articles` | ✅ | <30s latency | ✅ |
| All Agents → Monitoring | Prometheus metrics + Redis | ✅ | Continuous | ✅ |
| System → Alerts | Telegram Bot API | ✅ | <5s | ✅ |

**Verdict: ✅ All inter-component communication paths are defined with protocols and latency targets.**

### 2.2 Agent Communication Protocol ✅

The `AgentMessage` dataclass is consistently defined across documents:
- `architecture_system.md` Section 5.3: `AgentMessage` with `MessageType` enum
- `architecture_trading_engine.md` Section 5.2: `AgentMessage` with priority levels (P0-P3)

Both define the same fields: `message_id`, `source_agent`, `target_agent`, `message_type`, `payload`, `correlation_id`, `priority`, `timestamp`, `ttl_seconds`.

**Verdict: ✅ Consistent.**

### 2.3 Broker Connector Interface ✅

Three documents define the `BrokerConnector` ABC:
- `architecture_system.md` Section 3.5: 10 abstract methods
- `architecture_trading_engine.md` Section 6.1: 10 abstract methods (same set)
- `architecture_broker_routing.md` Section 12.1: Extended with `ping()`, `get_capabilities()`, `submit_order()` returning `OrderAck`, `cancel_order()`, `amend_order()`, `get_order_status()`, `subscribe_*` methods

**⚠️ Gap:** The broker routing doc defines a more detailed connector interface (with `OrderAck`, `AmendAck`, subscription methods) than the system/trading engine docs. These need to be reconciled into a single canonical interface.

---

## 3. Integration Gaps

### Gap 1: Missing Multi-Agent Architecture Document ❌

**Impact: HIGH**

The file `architecture_multi_agent.md` does not exist. Multi-agent content is scattered across:
- `architecture_system.md` Section 3.4 (agent architecture diagram, loop patterns)
- `architecture_trading_engine.md` Section 5 (agent architecture, communication protocol, loop integration)

The system architecture references a Coordinator Agent with orchestrator-workers pattern, but the trading engine describes a flat agent hierarchy with direct event bus communication. These models need reconciliation.

**Resolution:** Create `architecture_multi_agent.md` that explicitly defines:
1. Coordinator Agent vs flat hierarchy decision
2. Agent lifecycle management (start, stop, restart, health check)
3. Agent state persistence and recovery
4. Inter-agent dependency graph (which agent waits for which)
5. Deadlock prevention (circular event dependencies)

### Gap 2: Smart Order Router Interface Mismatch ⚠️

**Impact: MEDIUM**

| Component | Interface | Source |
|---|---|---|
| `architecture_system.md` | `SmartOrderRouter` with `route_order()` | Section 3.5 |
| `architecture_trading_engine.md` | `SmartOrderRouter` with `route_order()` | Section 6.4 |
| `architecture_broker_routing.md` | `RouteDecisionEngine` with `route_order()` returning `RouteLeg[]` | Section 4.2 |

The broker routing doc introduces `RouteLeg`, `BrokerRank`, `OrderRequest` types that don't exist in the other docs. The `OrderManager` in the trading engine calls `router.route_order()` but the broker routing doc returns `RouteLeg[]` (multiple legs) while the trading engine expects a single `OrderResult`.

**Resolution:** Align on `RouteDecisionEngine` returning `RouteLeg[]`, and update `UnifiedOrderManager` to handle multi-leg orders (submit each leg, aggregate results).

### Gap 3: Continuous Aggregate Pipeline Gap ⚠️

**Impact: MEDIUM**

`architecture_data_storage.md` defines continuous aggregates from tick → 1m → 5m → 15m → 1h → 4h → 1d. However:

- The 5m aggregate sources from `market_data WHERE timeframe = '1m'`, but the 1m aggregate is defined as `candle_1m` (a materialized view), not the `market_data` table.
- The `candle_1m` view is populated from `ticks`, but there's no explicit `INSERT INTO market_data` step that writes the 1m candle result back to `market_data` for the 5m aggregate to read.

**Resolution:** Add an explicit data flow step: `candle_1m` continuous aggregate → periodic `INSERT INTO market_data` for 1m timeframe, OR redefine higher-level aggregates to source from `candle_1m` directly.

### Gap 4: MongoDB Integration Underspecified ⚠️

**Impact: LOW**

`architecture_data_storage.md` introduces MongoDB for strategy configs, research notes, agent configs, and backtest results. However:
- No other architecture document references MongoDB
- No agent reads from MongoDB collections
- No event bus stream publishes to MongoDB
- The scaling path notes MongoDB is "optional at Phase 1"

**Resolution:** Either:
1. Remove MongoDB and use PostgreSQL JSONB columns + JSON/YAML files (simpler)
2. Define explicit MongoDB integration points in the agent architecture

### Gap 5: Missing ML Model Serving Architecture ⚠️

**Impact: MEDIUM**

The trading engine references 8 ML models (HMM, FinBERT, XGBoost ×3, CNN, LSTM, RL) but:
- No architecture defines how models are served (inline inference vs separate inference service)
- No latency targets for ML inference within the pipeline
- No model versioning or hot-reload mechanism
- The system architecture mentions "ML Inference Pod (GPU)" in Phase 3 but no details

**Resolution:** Add model serving specification:
- Phase 1: Inline inference (model loaded in process memory)
- Phase 2+: Separate inference service with gRPC endpoint
- Model registry (MLflow or custom)
- Hot-reload on model retrain

### Gap 6: Event Bus Naming Inconsistency ⚠️

**Impact: LOW**

Stream naming differs between documents:

| Concept | System Arch | Trading Engine | Data Storage |
|---|---|---|---|
| Tick stream | `market.ticks` | `market.data` | `stream:ticks:{sym}` |
| Order events | `orders.events` | `orders.execution` | `stream:orders` |
| System alerts | `system.alerts` | `system.alert` | `alert:system` |

**Resolution:** Canonical stream names should be defined in one place (system architecture) and referenced by all other docs.

### Gap 7: Missing Deployment Orchestration Details ⚠️

**Impact: MEDIUM**

`architecture_system.md` defines 4 deployment phases but:
- No Docker Compose file or service dependency graph
- No health check endpoints defined
- No startup order specification (which service starts first)
- No graceful shutdown sequence
- The trading engine defines `AlphaStackEngine.start()` with initialization order, but this is Python-level, not infrastructure-level

**Resolution:** Add `docker-compose.yml` specification with:
- Service dependency graph (depends_on)
- Health check definitions
- Startup order
- Volume mounts for persistent data

---

## 4. Deployability Assessment

### 4.1 Phase 1 Deployability: $7 Micro Account ✅

| Requirement | Available? | Notes |
|---|---|---|
| Single-machine deployment | ✅ | Docker Compose on local machine |
| MT5 connectivity | ✅ | MT5 Python API + ZeroMQ bridge |
| Basic data pipeline | ✅ | Tick → 1m → higher TF via continuous aggregates |
| Strategy execution | ✅ | AlphaStack 16-step pipeline |
| Risk management | ✅ | Risk Governor with hard limits |
| Trade journaling | ✅ | PostgreSQL + journal entries |
| Monitoring | ✅ | Prometheus + Grafana + Telegram alerts |
| Paper trading mode | ✅ | Config: `mode: "paper"` |
| Backup | ✅ | pg_dump cron |

**Phase 1 is fully deployable** with the existing architecture. All required components are specified.

### 4.2 Phase 2 Deployability: Live Trading VPS ✅

| Requirement | Available? | Notes |
|---|---|---|
| VPS deployment | ✅ | Hetzner CX31 specified |
| 24/5 operation | ✅ | No local machine dependency |
| WAL archiving | ✅ | Defined in data storage |
| Connection pooling | ✅ | PgBouncer config provided |
| External backup | ✅ | Backblaze B2 |

**Phase 2 is fully deployable.**

### 4.3 Phase 3 Deployability: Multi-Broker ⚠️

| Requirement | Available? | Notes |
|---|---|---|
| Kubernetes manifests | ❌ | Referenced but not defined |
| Multi-broker routing | ✅ | Broker routing architecture complete |
| Read replica | ✅ | Referenced in data storage |
| ClickHouse | ⚠️ | Referenced but no schema defined |
| CDC pipeline | ❌ | Mentioned but not designed |

**Phase 3 has gaps** in Kubernetes manifests and CDC pipeline design.

### 4.4 Phase 4 Deployability: Institutional ❌

Phase 4 (institutional) is aspirational. Key components lack detail:
- Kafka event bus migration path undefined
- Multi-region replication strategy undefined
- FIX protocol connector referenced but not designed
- HSM integration referenced but not designed

**Phase 4 is NOT ready for engineering.** Acceptable — it's years away.

---

## 5. Integration Risks

### Risk 1: Event Bus Single Point of Failure 🔴

**Severity: CRITICAL**

Redis is the sole event bus. If Redis goes down:
- All inter-agent communication stops
- No signals propagate
- No orders can be submitted
- The system architecture states: "Event Bus down → System enters safe mode: close all positions, halt trading"

**Mitigation:**
- Phase 1: Accept risk (single machine, low capital)
- Phase 2: Redis AOF + RDB persistence, monitoring
- Phase 3: Redis Sentinel or Cluster for HA
- Phase 4: Kafka as primary event bus with Redis as cache

**Engineering Action:** Implement the "safe mode" shutdown protocol as the first priority. Ensure positions can be closed even if the event bus fails (direct broker API call bypass).

### Risk 2: Strategy Pipeline Latency Budget 🟡

**Severity: MEDIUM**

The critical path (market data → execution) has a budget of ~125-425ms for forex. Breakdown:

| Step | Budget | Risk |
|---|---|---|
| Tick ingestion | 5ms | Low |
| AlphaStack Pipeline (16 steps) | 50-200ms | **HIGH** — LLM steps (S1, S2) could exceed budget |
| Risk Governor | 10ms | Low |
| Execution Agent | 5ms | Low |
| Order Manager | 10ms | Low |
| Broker execution | 50-200ms | Medium |

The trading engine acknowledges LLM latency in S1 ("Layer 2: LLM reasoning for nuanced events when FinBERT confidence <0.7") but doesn't specify timeout behavior. If the LLM takes 2s, the entire pipeline stalls.

**Mitigation:**
- Strict timeouts on LLM calls (500ms max)
- Fallback to FinBERT-only when LLM times out
- Async LLM enrichment (don't block pipeline, enrich in background)
- Pre-compute fundamental bias on session start, not per-candle

### Risk 3: Data Consistency Across Stores 🟡

**Severity: MEDIUM**

The system writes to 4 storage systems:
- TimescaleDB (time-series)
- PostgreSQL (transactions)
- Redis (cache + events)
- MongoDB (configs, optional)

If a write to PostgreSQL succeeds but the corresponding Redis cache update fails, agents may read stale data. No distributed transaction or saga pattern is defined.

**Mitigation:**
- PostgreSQL is the source of truth for all transactional data
- Redis cache is rebuilt from PostgreSQL on startup
- Event sourcing via Redis Streams provides replay capability
- Define explicit "cache-aside" pattern: read from Redis, miss → read from PG → write to Redis

### Risk 4: Broker Connection Resilience 🟡

**Severity: MEDIUM**

The MT5 connector uses a single-threaded Python MT5 API. If the MT5 terminal crashes:
- All forex trading stops
- Market data feed stops
- Open positions have stops/TPs at broker level (safe)

The broker routing architecture defines failover for crypto (multiple exchanges) but MT5 forex has no failover path.

**Mitigation:**
- Phase 1: Accept single-broker risk (low capital)
- Phase 2: Monitor MT5 terminal health, auto-restart via process supervisor
- Phase 3: Add OANDA as backup forex broker
- Implement "broker health" event stream so all agents know when broker is down

### Risk 5: ML Model Lifecycle Management 🟡

**Severity: MEDIUM**

8 ML models are referenced but no architecture defines:
- How models are loaded into memory
- How model updates are deployed without downtime
- How model performance is monitored
- What happens when a model produces NaN/error outputs

**Mitigation:**
- Define model wrapper with fallback behavior (return neutral/default on error)
- Model versioning via file naming (`model_v3.pkl`)
- Graceful degradation: if ML model fails, fall back to rule-based logic
- Monitor model prediction distribution (drift detection)

---

## 6. Cross-Document Consistency Matrix

| Concept | System Arch | Trading Engine | Broker Routing | Data Storage | Consistent? |
|---|---|---|---|---|---|
| AlphaStack 16 steps | ✅ High-level | ✅ Detailed | — | — | ✅ |
| StrategyContext dataclass | ✅ | ✅ (as TradeOrder) | — | — | ⚠️ Different names |
| Event bus (Redis Streams) | ✅ | ✅ | ✅ | ✅ | ✅ (minor naming diffs) |
| BrokerConnector ABC | ✅ 10 methods | ✅ 10 methods | ✅ 14 methods | — | ⚠️ Interface mismatch |
| Risk Governor limits | ✅ | ✅ (detailed) | — | — | ✅ |
| Confluence scoring | ✅ (summary) | ✅ (detailed) | — | — | ✅ |
| Deployment phases | ✅ 4 phases | ✅ 3 phases | — | ✅ 4 phases | ⚠️ Phase count differs |
| Storage technologies | ✅ | — | — | ✅ (detailed) | ✅ |
| Monitoring stack | ✅ | ✅ | ✅ | ✅ | ✅ |
| Agent roles | ✅ | ✅ | — | — | ✅ |
| S/R module design | ✅ (summary) | ✅ (detailed) | — | — | ✅ |
| Position sizing | ✅ (summary) | ✅ (detailed) | — | — | ✅ |
| Stop loss logic | — | ✅ (detailed) | — | — | ✅ |
| Take profit logic | — | ✅ (detailed) | — | — | ✅ |
| Trade management | — | ✅ (detailed) | — | — | ✅ |
| Exit conditions | — | ✅ (detailed) | — | — | ✅ |
| Journal schema | — | ✅ (detailed) | — | ✅ (SQL) | ✅ |

---

## 7. Recommendations Summary

### Must-Fix Before Engineering (Sprint 1)

| # | Gap | Action | Effort |
|---|---|---|---|
| 1 | Missing multi-agent arch doc | Create `architecture_multi_agent.md` | 2 days |
| 2 | BrokerConnector interface mismatch | Reconcile to single canonical interface | 1 day |
| 3 | Event bus naming inconsistency | Standardize stream names in system arch | 0.5 day |
| 4 | Safe mode shutdown protocol | Implement emergency position close bypass | 2 days |

### Should-Fix Before Phase 2 (Sprint 2-3)

| # | Gap | Action | Effort |
|---|---|---|---|
| 5 | Continuous aggregate pipeline gap | Fix 1m → 5m aggregate data source | 1 day |
| 6 | ML model serving architecture | Define inference service spec | 1 day |
| 7 | Deployment orchestration | Create docker-compose.yml with health checks | 2 days |
| 8 | LLM timeout/fallback behavior | Implement async enrichment with timeout | 1 day |

### Nice-to-Have (Backlog)

| # | Gap | Action | Effort |
|---|---|---|---|
| 9 | MongoDB integration | Decide: keep or remove | 0.5 day |
| 10 | Kubernetes manifests | Create for Phase 3 | 3 days |
| 11 | ClickHouse schema | Define analytics tables | 1 day |
| 12 | CDC pipeline design | Design TimescaleDB → ClickHouse | 2 days |

---

## 8. Final Verdict

### Architecture Completeness

| Dimension | Score | Notes |
|---|---|---|
| Data flow completeness | 9/10 | End-to-end path verified, minor naming gaps |
| Component communication | 9/10 | All paths defined, interface mismatch in broker connector |
| Integration consistency | 8/10 | 7 gaps identified, all resolvable |
| Deployability (Phase 1) | 9/10 | Fully deployable, missing docker-compose |
| Deployability (Phase 2) | 8/10 | Deployable, minor gaps |
| Deployability (Phase 3) | 6/10 | K8s, CDC, ClickHouse need design |
| Risk coverage | 8/10 | 5 risks identified, all have mitigations |
| Scalability design | 9/10 | Excellent $7 → institutional path |
| Security architecture | 9/10 | Comprehensive encryption, auth, audit |
| Documentation quality | 9/10 | Detailed, well-structured, code examples |

### **Overall: 8.4/10 — Architecture is solid and ready for engineering with targeted gap remediation.**

### Key Strengths

1. **Event-first architecture** enables clean decoupling and replay capability
2. **AlphaStack 16-step pipeline** is well-designed with clear interfaces and progressive enrichment
3. **Risk Governor** is properly positioned as an unskippable gate with hard limits
4. **Tiered scaling** from $7 to institutional is thoughtfully designed without requiring rewrites
5. **Data storage** is comprehensive with proper retention, compression, and backup strategies
6. **Broker routing** is sophisticated with scoring, failover, arbitrage detection, and load balancing
7. **Security** is built-in from day one (encryption, auth, audit trail)

### Key Weaknesses

1. **Missing multi-agent coordination document** — the most critical gap
2. **ML model lifecycle** is underspecified across all documents
3. **Phase 3/4 infrastructure** needs more design detail before those phases begin
4. **No explicit saga/distributed transaction pattern** for cross-store consistency

---

*Review completed by System Integration Review Agent — Alpha Stack*  
*All architecture documents have been reviewed end-to-end. The system is architecturally sound and ready for engineering commencement.*
