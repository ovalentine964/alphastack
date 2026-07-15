# AlphaStack Architecture Review

> **Date:** 2026-07-15  
> **Reviewer:** Architecture Review Agent  
> **Scope:** Full system architecture — 46 architecture docs, 15 source modules, Docker infra  
> **Verdict:** **Ambitious and well-documented, with significant gaps between design and implementation**

---

## 1. OVERALL ARCHITECTURE ASSESSMENT

### 1.1 Is the Architecture Sound?

**Partially.** The *design documents* are extensive, well-structured, and demonstrate deep domain knowledge. The *actual implementation* is a skeleton — a thin LangGraph orchestrator wiring 5 agents together, backed by Redis Streams and PostgreSQL. The gap between the 46 architecture documents (~3.3GB of design) and the implemented code is the single biggest risk.

**What's genuinely good:**
- **Event-first architecture** — All inter-module communication via events is the correct pattern for a trading system. Enables replay, audit, and horizontal scaling.
- **Risk as infrastructure, not prompt** — The Risk Agent enforces limits in code, not in LLM prompts. This is critical and correctly implemented.
- **Progressive autonomy (HITL)** — The 4-level autonomy system (supervised → conditional → notify → autonomous) is well-designed and properly implemented in `hitl_loop.py`.
- **Cognitive loops** — The 5 loop types (ReAct, Deliberation, Plan-and-Execute, Reflection, Event-driven) are well-chosen for their respective agent roles.
- **Rust fallback pattern** — `rust_bridge.py` gracefully degrades to Python when the native module isn't built. Good defensive programming.

**What's concerning:**
- **Architecture-first development anti-pattern** — 46 architecture docs before a working system. Many docs describe components that don't exist in code (ClickHouse, Kafka, gRPC, Kubernetes, FIX protocol, multi-broker routing, ML pipelines).
- **Over-specified for current stage** — The system has architecture for institutional-grade deployment ($100K+ capital) but the code is at prototype stage (in-memory trade stores, hardcoded demo data, no actual broker connections).
- **Single-process everything** — Despite describing a distributed multi-agent system, everything runs in a single Python process via LangGraph.

### 1.2 Does It Follow Best Practices?

| Practice | Status | Notes |
|----------|--------|-------|
| Event-driven architecture | ✅ Good | Redis Streams with consumer groups |
| Separation of concerns | ✅ Good | Agents have clear boundaries |
| Risk as code (not prompt) | ✅ Good | Infrastructure-level enforcement |
| Progressive autonomy | ✅ Good | 4-level HITL system |
| Audit trail | ⚠️ Partial | Events logged, but no persistent audit store |
| Schema-first design | ⚠️ Partial | Pydantic models exist but no schema registry |
| Circuit breakers | ⚠️ Partial | Defined in architecture, minimal in code |
| Graceful degradation | ⚠️ Partial | Fallback signals exist, but no real degradation logic |
| Infrastructure as code | ❌ Missing | Only a basic Dockerfile and compose file |
| CI/CD pipeline | ❌ Missing | No GitHub Actions, no test automation |
| Observability | ❌ Missing | No Prometheus metrics, no Grafana dashboards |

### 1.3 Is It Scalable?

**The architecture is designed to scale. The implementation is not.**

The architecture describes 5 scaling phases ($7 → $1M+) with clear triggers and infrastructure evolution. However, the current implementation has fundamental scalability blockers:

1. **In-memory trade stores** — `_TRADES` and `_SIGNALS` dicts in route files. Dies on restart, can't scale horizontally.
2. **Single Redis client** — No connection pooling configuration, no cluster support.
3. **Synchronous agent execution** — Agents run sequentially through the LangGraph pipeline. No parallel signal agent execution despite the architecture describing it.
4. **No backpressure** — The EventBus has no flow control. If consumers fall behind, messages accumulate silently.

### 1.4 Single Point of Failure Analysis

| Component | SPOF? | Impact | Mitigation in Code |
|-----------|-------|--------|-------------------|
| Redis | **YES** | All communication stops | None — single instance, no failover |
| PostgreSQL | **YES** | No persistence | Single instance, no replication |
| LangGraph orchestrator | **YES** | Pipeline halts | None — single process |
| LLM API (DeepSeek/Qwen) | **YES** | Agents can't reason | Fallback signals exist but no offline mode |
| Broker connection | Partial | Can't execute | Broker health check defined but not implemented |
| Event Bus | **YES** | All inter-agent comms stops | Architecture says "safe mode" but no implementation |

**Verdict:** Every critical component is a single point of failure. The architecture documents describe HA patterns (Redis Cluster, PostgreSQL replication, K8s multi-replica) but none are implemented.

---

## 2. MULTI-AGENT ORCHESTRATION

### 2.1 Is LangGraph the Right Choice?

**Yes, for the current stage.** LangGraph provides:
- State machine semantics (correct for a sequential pipeline)
- Built-in checkpointing (for HITL pause/resume)
- Conditional edges (for risk gate routing)
- Human-in-the-loop via `interrupt()`

**Concerns at scale:**
- LangGraph runs in a single process. The architecture describes 16+ agents running concurrently — LangGraph can't do this without significant custom work.
- The graph is rebuilt on every `AlphaStackOrchestrator` instantiation. No graph caching or reuse.
- State serialization/deserialization on every node transition (`_state_to_dict` / `_state_from_dict`) adds overhead. For a trading system where milliseconds matter, this is problematic.

**What's missing for production:**
- No graph persistence (checkpointer is optional and no implementation provided)
- No graph versioning (can't A/B test different pipeline configurations)
- No graph visualization (the `graph` property exposes the compiled graph but no tooling to render it)

### 2.2 Agent Communication Patterns

The architecture describes three communication patterns:
1. **Shared State** (Redis Hashes) — For position/portfolio data
2. **Message Passing** (Redis Streams) — For signal handoff
3. **Event-Driven** (Redis Pub/Sub) — For market data distribution

**What's implemented:**
- `EventBus` in `events.py` — Redis Streams with consumer groups. Solid implementation with typed events (Signal, Trade, Risk, Data, Agent).
- `redis_client.py` — Basic cache and pub/sub helpers. No stream consumer group management.
- Agents communicate via the LangGraph shared state dict, not via Redis Streams. The EventBus is used for side-effect logging, not primary communication.

**Gap:** The architecture describes a rich inter-agent messaging protocol (priority levels, dead letter queues, deduplication, bloom filters, message signing) but the implementation uses LangGraph state passing. The EventBus is an append-only log, not a message broker.

### 2.3 Fault Tolerance Between Agents

**Architecture describes:** 5 circuit breaker levels, graceful degradation modes (normal → degraded → minimal → emergency), agent restart protocols, health monitoring heartbeats.

**Implementation has:**
- `base.py` — `publish_event()` with try/catch (won't crash on event bus failure)
- `orchestrator/graph.py` — `_route_after_risk()` checks `circuit_breaker_active` flag
- `risk/agent.py` — `_check_circuit_breaker()` checks drawdown, daily loss, and critical news

**Missing:**
- No agent health monitoring (heartbeats defined in architecture, not implemented)
- No agent restart mechanism (if an agent crashes, the pipeline hangs)
- No timeout enforcement on agent execution (an LLM call could hang forever)
- No fallback model switching (if DeepSeek is down, no automatic switch to Qwen)
- No dead letter handling for failed messages

### 2.4 How Agents Recover from Failures

**Short answer: They don't.** 

If an agent throws an exception during `execute()`, the `base.py` `run()` method catches it, publishes an error event, and re-raises. The LangGraph pipeline will fail at that node. There's no retry logic, no fallback, no circuit breaker at the agent level.

The architecture describes a 5-level circuit breaker system and graceful degradation modes. None of this is implemented in code.

---

## 3. DATA ARCHITECTURE

### 3.1 TimescaleDB + Redis + Kafka Choices

**TimescaleDB (PostgreSQL + TimescaleDB extension):**
- ✅ Correct choice for time-series market data. PostgreSQL-compatible, mature, auto-partitioning.
- ⚠️ The ORM models in `models.py` are well-designed (Account, Position, Order, Signal, Trade, MarketData, TickData, AgentDecision, RiskCheck) with proper indexes.
- ❌ The actual API routes use in-memory dicts (`_TRADES`, `_SIGNALS`), not the database. The ORM models exist but aren't wired up.

**Redis:**
- ✅ Correct for caching, pub/sub, and streams. The `redis_client.py` has clean cache helpers.
- ⚠️ The `EventBus` in `events.py` uses Redis Streams with consumer groups — good pattern.
- ❌ No Redis persistence configuration (data lost on restart)
- ❌ No connection pooling tuning (uses defaults)
- ❌ Redis is used for both caching AND messaging — these should have different configurations

**Kafka:**
- ❌ **Not implemented and not needed at current scale.** The architecture mentions Kafka for institutional deployment but Redis Streams is sufficient for 1-10 pairs. This is correct deferral.

**ClickHouse:**
- ❌ **Not implemented.** Architecture describes it for analytics/backtesting. Not needed until there's actual data to analyze.

### 3.2 Data Flow Bottlenecks

1. **Tick data ingestion** — No actual data pipeline exists. The architecture describes MT5 collectors, CCXT collectors, news aggregators, and economic calendar scrapers. None are implemented.

2. **Signal generation** — The StrategyAgent tries to import `AlphaStackPipeline` which doesn't exist. Falls back to a placeholder signal with 0.0 strength.

3. **State serialization** — Every LangGraph node transition serializes the entire state to JSON and back. For a state with market data, signals, trade decisions, and execution logs, this is expensive.

4. **LLM inference** — Every agent call potentially hits an external LLM API. No caching of LLM responses, no batching, no local model inference.

### 3.3 Real-time vs Batch Processing

**Architecture describes:**
- Real-time: Tick monitoring, stop loss/take profit triggers (1s)
- Near-real-time: Signal generation (M15 candle close)
- Batch: Journal compilation, performance review (daily/weekly)

**Implementation:** Everything is batch/synchronous. The LangGraph pipeline runs once per invocation. There's no continuous monitoring loop, no tick-level processing, no candle-close triggers.

### 3.4 Missing Data Components

| Component | Status | Priority |
|-----------|--------|----------|
| Market data collector | ❌ Missing | **Critical** — No data = No trading |
| Data normalization | ❌ Missing | High |
| Gap detection | ❌ Missing | Medium |
| Data quality checks | ❌ Missing | Medium |
| Historical data loader | ❌ Missing | High — needed for backtesting |
| News feed integration | ❌ Missing | Medium |
| Economic calendar | ❌ Missing | Medium |
| Tick-to-candle aggregation | ❌ Missing | High |

---

## 4. DEPLOYMENT ARCHITECTURE

### 4.1 Docker Setup Review

**Dockerfile:**
- ✅ Multi-stage build (builder + runtime) — good practice
- ✅ TA-Lib C library compilation — necessary for technical indicators
- ✅ Non-root user (`alphastack`) — security best practice
- ✅ Health check configured
- ⚠️ Uses `python:3.12-slim` but architecture references Python 3.11 — minor inconsistency
- ❌ No Rust compilation stage (despite `rust_bridge.py` expecting native module)
- ❌ No `.dockerignore` — will copy unnecessary files
- ❌ Hardcoded `CMD` for API server only — no support for worker/agent processes

**docker-compose.yml:**
- ✅ TimescaleDB and Redis with health checks
- ✅ Volume persistence for data
- ✅ Environment variable configuration via `x-common-env`
- ⚠️ Only 2 services (timescaledb, redis) + API server. Missing: trading engine, monitoring, nginx
- ❌ Hardcoded passwords (`alphastack`/`alphastack`) — acceptable for dev, dangerous if deployed
- ❌ No resource limits (memory/CPU constraints)
- ❌ No network isolation (all services on default network)
- ❌ `trading-engine` service uses `profiles: [engine]` — won't start by default
- ❌ No Prometheus, Grafana, Loki, or any monitoring stack

### 4.2 Scaling Strategy

**Architecture describes:** 5 deployment phases from local Docker Compose to multi-region Kubernetes.

**What exists:** A single `docker-compose.yml` with 3 services. No Kubernetes manifests, no Helm charts, no Terraform, no CI/CD pipeline.

**Gap:** The architecture is thorough about scaling (Phase 1-5 with specific VPS providers, costs, and configurations) but the implementation hasn't started on any of it.

### 4.3 Infrastructure Gaps

| Gap | Impact | Effort |
|-----|--------|--------|
| No CI/CD pipeline | Can't deploy reliably | Medium |
| No monitoring stack | Can't see what's happening | Medium |
| No logging aggregation | Can't debug production issues | Low |
| No secret management | Credentials in env vars | Medium |
| No backup automation | Data loss risk | Low |
| No SSL/TLS | Unencrypted API access | Low |
| No Kubernetes manifests | Can't scale horizontally | High |
| No disaster recovery | No recovery procedures | Medium |

### 4.4 Cloud Readiness

**Not cloud-ready.** The docker-compose.yml is a local development setup. For cloud deployment, you'd need:
- Managed database (RDS/Cloud SQL) instead of containerized PostgreSQL
- Managed Redis (ElastiCache/MemoryDB) instead of containerized Redis
- Load balancer instead of direct port exposure
- Secret management (Vault/AWS Secrets Manager) instead of env vars
- Container registry for images
- CI/CD pipeline for automated deployment

---

## 5. INTEGRATION PATTERNS

### 5.1 How Components Connect

```
┌─────────────┐     LangGraph      ┌──────────────┐
│  News       │ ──state dict──▶    │  Strategy    │
│  Agent      │                    │  Agent       │
└─────────────┘                    └──────┬───────┘
                                          │ state dict
                                          ▼
                                   ┌──────────────┐
                                   │  Risk        │
                                   │  Agent       │
                                   └──────┬───────┘
                                          │ state dict
                                          ▼
                                   ┌──────────────┐     Redis Streams
                                   │  Execution   │ ──────────────▶ EventBus
                                   │  Agent       │
                                   └──────┬───────┘
                                          │ state dict
                                          ▼
                                   ┌──────────────┐
                                   │  Reflection  │
                                   │  Agent       │
                                   └──────────────┘
```

**Pattern:** Sequential pipeline via LangGraph state passing. Each agent reads from and writes to a shared Pydantic model (`AlphaStackState`).

**Concerns:**
- **Tight coupling** — All agents share the same state model. Adding a field requires updating the model and potentially all agents.
- **No async parallelism** — Despite `async def execute()`, agents run sequentially in the graph. The architecture describes parallel Phase 3 execution (SMC + Momentum + Candlestick simultaneously) but the implementation doesn't support it.
- **State bloat** — The `AlphaStackState` contains everything: market data, signals, trade decisions, execution logs, news alerts, performance summaries. Every agent sees everything.

### 5.2 API Design Quality

**REST API (`rest/app.py`):**
- ✅ FastAPI with proper middleware (CORS, rate limiting, request timing)
- ✅ Clean route organization (auth, trades, portfolio, signals, system)
- ✅ Pydantic request/response models
- ⚠️ In-memory stores for trades and signals (not production-ready)
- ❌ No authentication middleware on protected routes (JWT is implemented but not enforced via `Depends`)
- ❌ No pagination on list endpoints (signals endpoint)
- ❌ No error response standardization

**WebSocket (`websocket/server.py`):**
- ✅ Clean channel-based subscription model
- ✅ Connection manager with proper cleanup
- ✅ Ping/pong for keepalive
- ⚠️ No authentication on WebSocket connections
- ❌ No message validation
- ❌ No backpressure handling
- ❌ No reconnection logic for server-side broadcasts

**Auth (`auth.py`):**
- ⚠️ Custom JWT implementation (no PyJWT dependency) — reinventing the wheel
- ❌ Secret generated at import time (`secrets.token_urlsafe(64)`) — changes on restart, invalidating all tokens
- ❌ Hardcoded demo user (`admin`/`alphastack`)
- ❌ No password hashing library (bcrypt/argon2) — uses raw SHA-256
- ❌ No token revocation (logout is a no-op)

### 5.3 Event-Driven vs Request-Response

**Architecture intent:** Event-driven for all inter-agent communication, request-response for API.

**Implementation reality:**
- Inter-agent: **Request-response via LangGraph state** (not event-driven)
- EventBus: **Append-only log** (not used for agent coordination)
- API: **Request-response** (correct)
- WebSocket: **Push-based** (correct for real-time data)

**The EventBus is underutilized.** It's well-implemented (typed events, consumer groups, stream management) but agents don't use it for communication. They use LangGraph state passing instead.

### 5.4 Coupling Analysis

| Coupling | Level | Concern |
|----------|------|---------|
| Agent ↔ Agent | **High** | All share `AlphaStackState` — adding an agent requires updating the state model |
| Agent ↔ LLM | **High** | No abstraction layer — agents directly depend on specific LLM APIs |
| Agent ↔ EventBus | **Low** | Good — agents publish events but don't depend on subscribers |
| Agent ↔ Broker | **Medium** | ExecutionAgent has broker registry but no formal connector interface |
| API ↔ Database | **None** | API uses in-memory stores, not the database |
| API ↔ Agents | **None** | No bridge between API requests and agent execution |

---

## 6. GAPS & RECOMMENDATIONS

### 6.1 What's Missing from the Architecture?

| Missing Component | Criticality | Notes |
|-------------------|------------|-------|
| **Actual data pipeline** | 🔴 Critical | No market data collection, no tick processing, no candle aggregation |
| **Broker connectors** | 🔴 Critical | MT5 and CCXT connectors described in architecture but not implemented |
| **Strategy pipeline (16 steps)** | 🔴 Critical | `AlphaStackPipeline` doesn't exist — StrategyAgent falls back to placeholder |
| **ML models** | 🟡 High | FinBERT, regime classifier, S/R ML — all described, none implemented |
| **Backtesting engine** | 🟡 High | Can't validate strategy without historical data and backtesting |
| **Monitoring stack** | 🟡 High | No Prometheus, Grafana, or alerting |
| **CI/CD pipeline** | 🟡 High | No automated testing or deployment |
| **Secret management** | 🟡 High | Credentials in env vars, JWT secret regenerated on restart |
| **Vector database** | 🟢 Medium | For semantic search over trade history — not needed until trades exist |
| **ClickHouse** | 🟢 Medium | Analytics DB — not needed until data volume justifies it |
| **Kubernetes** | 🟢 Medium | Not needed until multi-replica deployment |

### 6.2 What's Over-Engineered?

1. **The agent communication protocol** — 100+ pages on message envelopes, priority queues, bloom filters, dead letter handling, message signing, and distributed tracing. The actual communication is LangGraph state passing. This is 10x over-designed for the current need.

2. **The memory system** — 4-layer memory architecture (working → short-term → long-term → episodic) with semantic search, vector embeddings, and contextual bandits. The implementation is a basic `AgentMemory` class with append-only lists.

3. **The security architecture** — Quantum-resistant cryptography, HSM integration, 5-layer defense model. The actual auth is a hardcoded demo user with SHA-256 passwords.

4. **The curriculum documents** — 5 academic curriculum documents (CS, Economics, Math, Statistics, Integration) that have nothing to do with the trading system.

5. **The scalability architecture** — Microservices decomposition, CQRS, event sourcing, Kafka, Kubernetes — described in detail for a system that runs as a single process.

### 6.3 What Needs Simplification?

1. **Agent count** — 16+ agents is too many for a first implementation. Start with 4: Strategy, Risk, Execution, Journal. Add specialized agents (SMC, Momentum, Candlestick, etc.) as the system matures.

2. **Communication patterns** — Drop Redis Streams for inter-agent communication. Use LangGraph state passing (which already works). Use EventBus only for external event distribution (WebSocket, alerts).

3. **Database stack** — Start with PostgreSQL only. Add TimescaleDB extension for time-series. Drop ClickHouse and Kafka until data volume justifies them.

4. **Deployment** — Single docker-compose.yml with all services. No Kubernetes until you have 3+ replicas of something.

5. **Loop types** — 5 cognitive loop types is excessive. Start with ReAct (for analysis) and Event-driven (for execution). Add Deliberation and Reflection later.

### 6.4 Priority Fixes

**Phase 1: Make It Work (Weeks 1-4)**

| # | Fix | Effort | Impact |
|---|-----|--------|--------|
| 1 | Wire API routes to PostgreSQL (replace in-memory stores) | 2 days | Data persistence |
| 2 | Implement basic market data collector (CCXT for crypto) | 3 days | Actual data flow |
| 3 | Implement broker connector interface + CCXT adapter | 3 days | Can actually trade |
| 4 | Add timeout enforcement on agent execution | 1 day | Prevents hangs |
| 5 | Fix JWT secret (load from env, not generate at import) | 1 hour | Auth works across restarts |
| 6 | Add `Depends(get_current_user)` to protected routes | 1 day | API is actually secured |
| 7 | Add Alembic migrations | 1 day | Database schema management |
| 8 | Wire EventBus to WebSocket broadcasts | 1 day | Real-time data to clients |

**Phase 2: Make It Reliable (Weeks 5-8)**

| # | Fix | Effort | Impact |
|---|-----|--------|--------|
| 9 | Add agent execution timeouts and retry logic | 2 days | Fault tolerance |
| 10 | Implement Prometheus metrics in agents and API | 2 days | Observability |
| 11 | Add Grafana dashboards | 1 day | Visibility |
| 12 | Implement circuit breaker for LLM API calls | 1 day | Graceful degradation |
| 13 | Add proper password hashing (bcrypt) | 1 hour | Security |
| 14 | Implement basic backtesting with historical data | 5 days | Strategy validation |
| 15 | Add CI/CD pipeline (GitHub Actions) | 2 days | Reliable deployment |
| 16 | Add integration tests for the LangGraph pipeline | 3 days | Confidence in changes |

**Phase 3: Make It Scale (Weeks 9-16)**

| # | Fix | Effort | Impact |
|---|-----|--------|--------|
| 17 | Implement the 16-step strategy pipeline | 10 days | Actual strategy execution |
| 18 | Add FinBERT sentiment analysis | 3 days | News-aware trading |
| 19 | Implement parallel agent execution for Phase 3 signals | 3 days | Latency reduction |
| 20 | Add Redis persistence and connection pooling | 1 day | Data durability |
| 21 | Implement proper monitoring stack (Prometheus + Grafana + Loki) | 3 days | Production observability |
| 22 | Add Kubernetes manifests for multi-replica deployment | 5 days | Horizontal scaling |

### 6.5 Architecture Document Recommendations

1. **Stop writing architecture docs. Start writing code.** The ratio of documentation to implementation is ~100:1. This is unsustainable — the docs will diverge from reality.

2. **Mark documents as "Implemented" vs "Planned"** — Currently all 46 docs are marked "Architecture Complete" which implies they're built. They're not.

3. **Delete or archive the curriculum documents** — They're academic exercises, not system architecture.

4. **Consolidate overlapping documents** — `architecture_data.md`, `architecture_data_storage.md`, and `architecture_database.md` cover the same topic. `architecture_multi_agent.md` and `architecture_agent_communication.md` overlap significantly.

5. **Create a single "Implementation Status" document** — Track what's actually built vs what's designed. Update it with each sprint.

---

## Summary

| Category | Design Score | Implementation Score | Gap |
|----------|-------------|---------------------|-----|
| Multi-Agent Orchestration | 9/10 | 5/10 | Large |
| Data Architecture | 8/10 | 2/10 | Critical |
| Risk Management | 9/10 | 4/10 | Large |
| Deployment | 8/10 | 2/10 | Critical |
| Security | 9/10 | 2/10 | Critical |
| API Design | 7/10 | 4/10 | Medium |
| Cognitive Loops | 9/10 | 6/10 | Medium |
| Broker Integration | 8/10 | 1/10 | Critical |
| Monitoring | 8/10 | 1/10 | Critical |
| **Overall** | **8.4/10** | **3.0/10** | **Large** |

**Bottom line:** AlphaStack has an exceptionally well-thought-out architecture that demonstrates deep understanding of trading systems, multi-agent design, and production engineering. The problem is that almost none of it is implemented. The codebase is a working skeleton — a LangGraph orchestrator with 5 stub agents, an EventBus, ORM models, and a basic API. The path forward is clear: stop designing, start building. The architecture documents are a valuable reference, but they're not a trading system. The priority is to close the gap between design and reality, one working component at a time.
