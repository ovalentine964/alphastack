# Alpha Stack — System Coherence Review

> **Review Type:** Architecture Design Review — System Coherence
> **Version:** 1.0 · **Date:** 2026-07-11 · **Reviewer:** Architecture Review Agent (Subagent)
> **Documents Reviewed:** `architecture_system.md`, `architecture_trading_engine.md`, `architecture_risk.md`, `architecture_broker_routing.md`, `architecture_data_storage.md`, `architecture_security.md`
> **Documents Missing:** `architecture_multi_agent.md`, `architecture_strategy_flow.md`, `architecture_agent_communication.md` — DO NOT EXIST

---

## Executive Summary

The Alpha Stack architecture is **ambitious, well-structured, and largely coherent** across the two core documents and supporting architecture files. The system design demonstrates strong engineering thinking — particularly in risk management, the VMPM pipeline abstraction, and the scaling roadmap. However, this review identifies **3 critical issues, 7 significant gaps, 4 redundancies, and 6 architectural risks** that should be addressed before implementation begins.

**Overall Coherence Score: 7.2 / 10** — Good foundation, needs targeted fixes.

| Category | Rating | Notes |
|----------|--------|-------|
| Module Connectivity | 8/10 | Well-defined interfaces, some ambiguity in agent↔module mapping |
| Data Flow Completeness | 7/10 | Primary flows complete, some dead ends in feedback loops |
| Missing Components | 6/10 | 3 requested docs don't exist; several cross-cutting concerns underspecified |
| Redundancy | 7/10 | Moderate overlap between system and trading engine docs |
| Deployability | 8/10 | Phased approach is practical; some Phase 1 gaps |
| Risk Profile | 6/10 | Several single points of failure and complexity risks |

---

## 1. Document Inventory & Coverage Analysis

### 1.1 Documents That Exist

| Document | Size | Coverage |
|----------|------|----------|
| `architecture_system.md` | 98KB | Full system architecture: layers, modules, data flow, deployment, scaling |
| `architecture_trading_engine.md` | 113KB | Deep dive: 16 VMPM steps, signal flow, broker integration, backtesting, live trading |
| `architecture_risk.md` | 126KB | Risk management: position sizing, drawdown, circuit breakers, black swan |
| `architecture_broker_routing.md` | 62KB | Smart order routing, broker scoring, failover, arbitrage detection |
| `architecture_data_storage.md` | 88KB | TimescaleDB, PostgreSQL, Redis, MongoDB, retention, backup |
| `architecture_security.md` | 76KB | Authentication, encryption, quantum-resistant crypto, audit |

### 1.2 Documents That DO NOT EXIST (Requested But Missing)

| Document | Expected Content | Impact |
|----------|-----------------|--------|
| `architecture_multi_agent.md` | Standalone multi-agent orchestration, LangGraph state machines, agent lifecycle | **HIGH** — Multi-agent details are scattered across system and trading engine docs. No single source of truth for agent orchestration. |
| `architecture_strategy_flow.md` | Standalone VMPM pipeline flow, step-to-step data contracts | **MEDIUM** — Strategy flow is well-covered in trading_engine.md. Redundant doc not strictly needed. |
| `architecture_agent_communication.md` | Standalone agent communication protocol, message schemas, routing | **MEDIUM** — Communication is covered in system.md §5 and trading_engine.md §5.2, but message schemas are inconsistent between the two. |

**Verdict:** The three missing docs are **not blockers** — their content is adequately (if not perfectly) covered in the existing documents. However, the inconsistency in agent communication schemas between system.md and trading_engine.md is a real issue that would have been caught if a dedicated communication doc existed.

---

## 2. Module Connectivity Validation

### 2.1 Dependency Matrix Cross-Check

The system architecture defines a clear 6-layer model (L0–L6). Cross-referencing module dependencies:

| Module | Declared Dependencies | Actually Connected? | Issues |
|--------|----------------------|---------------------|--------|
| **VMPM Pipeline (L3)** | Market data, ML models, all strategy steps | ✅ Yes | Well-defined StrategyContext flows through all 16 steps |
| **Strategy Agent (L4)** | VMPM Pipeline, Event Bus | ✅ Yes | Agent wraps pipeline, publishes to `signals.*` streams |
| **Risk Agent (L4)** | Risk Engine, Portfolio State | ✅ Yes | Risk Governor is well-defined with hard limits |
| **News Agent (L4)** | FinBERT, LLM, News APIs | ✅ Yes | S1 module handles this in trading_engine.md |
| **Execution Agent (L4)** | Order Manager, Brokers | ✅ Yes | UOM → BCA → Broker chain is clear |
| **Journal Agent (L4)** | Event Bus, Database | ⚠️ Partial | Journal records trades but connection to S16 RL learning agent is underspecified |
| **Auditor Agent (L4)** | Journal, ML models | ⚠️ Partial | "Weekly reflection" described but no clear trigger mechanism or state machine |
| **Order Manager (L2)** | Broker Connectors | ✅ Yes | UOM code is well-defined |
| **Risk Engine (L3)** | Portfolio State | ✅ Yes | Hard limits are code-defined |
| **Data Pipeline (L1)** | Brokers, News APIs | ✅ Yes | Ingestion → Processing → Storage chain is complete |
| **Event Bus (L4)** | Redis Streams | ✅ Yes | Stream definitions are comprehensive |
| **API Gateway (L5)** | All backend services | ⚠️ Partial | Routes defined but WebSocket push from strategy→client not fully specified |
| **Desktop App (L6)** | API Gateway | ⚠️ Partial | Tauri architecture referenced but detailed UI↔backend contract missing |

### 2.2 Critical Connectivity Issues

**ISSUE C-1: Agent ↔ Module Mapping Ambiguity**

The system architecture (system.md §3.4) defines 7 agents:
- Coordinator, Strategy, Risk, News, Execution, Journal, Auditor

The trading engine (trading_engine.md §5.1) defines a different agent taxonomy:
- Context Agents (S1, S2, S3), Analysis Agents (S4–S9), Decision Agents (S10, Risk Governor, Execution), Management Agents (S11–S15), Learning Agent (S16), Sentinel Agents (Black Swan, Correlation, Health)

**These two taxonomies don't align.** The system doc talks about a Coordinator Agent that delegates to specialists. The trading engine doc talks about layer-based agent grouping with no coordinator. This is the **most significant coherence gap** in the architecture.

**Recommendation:** Choose one taxonomy and make the other reference it. The trading engine's layer-based approach is more granular and practical. The system doc's coordinator pattern is higher-level orchestration. They can coexist if explicitly mapped.

**ISSUE C-2: Risk Governor vs Risk Agent**

- `architecture_system.md` defines a **Risk Agent** (ReAct loop, L4 orchestration layer)
- `architecture_trading_engine.md` defines a **Risk Governor** (hard-coded safety layer, L3)
- `architecture_risk.md` defines a **Risk Management System (RMS)** with its own Governor

Three different names/implementations for the same concept. The Risk Governor in trading_engine.md is the most concrete (actual Python code). The Risk Agent in system.md wraps it with an LLM-based ReAct loop. The RMS in risk.md is the most comprehensive.

**Recommendation:** Establish a clear layering: RMS (risk.md) is the authoritative risk system. Risk Governor is the code-level enforcement. Risk Agent is the LLM wrapper that adds reasoning. Document this hierarchy explicitly.

**ISSUE C-3: Shared State Location Conflict**

- `architecture_system.md`: "Shared State (Redis + PostgreSQL)" in multi-agent section
- `architecture_trading_engine.md`: Portfolio state in PostgreSQL, hot state in Redis
- `architecture_data_storage.md`: Adds MongoDB for document storage
- `architecture_risk.md`: Risk state in its own `risk.*` Redis streams

No single document defines the **canonical state store** for portfolio state, position state, and risk state. Which database is the source of truth for "current open positions"?

**Recommendation:** Define a single State Authority matrix: Portfolio state → PostgreSQL (source of truth) + Redis (hot cache). Risk state → Redis (source of truth, ephemeral). Market data → TimescaleDB (source of truth). This should be in system.md as a dedicated section.

---

## 3. Data Flow Completeness

### 3.1 Primary Data Flows — Traced End-to-End

| Flow | Start | End | Complete? | Dead Ends? |
|------|-------|-----|-----------|------------|
| **Market Data Ingestion** | MT5/CCXT/OANDA | TimescaleDB + Redis cache | ✅ Yes | None |
| **Signal Generation** | Market data → VMPM 1-16 | TradeProposal | ✅ Yes | None |
| **Risk Check** | TradeProposal → Risk Governor | Approved/Rejected | ✅ Yes | None |
| **Order Execution** | Approved order → UOM → BCA → Broker | Fill confirmation | ✅ Yes | None |
| **Trade Management** | Fill → S14/S15 monitoring | Exit/SL/TP adjustment | ✅ Yes | None |
| **Journal Recording** | Fill/Exit events → S16 | Journal entry in DB | ✅ Yes | None |
| **Feedback Loop** | Journal → RL Agent → Strategy Adaptation | ⚠️ Partial | **DEAD END** — RL agent recommendations have no clear path back to modify VMPM parameters |
| **News → Strategy** | News feed → FinBERT → Sentiment event | Strategy Agent consumes | ✅ Yes | None |
| **Client Data Push** | Strategy signals → WebSocket → Client | ⚠️ Partial | WebSocket server defined but client subscription model unclear |

### 3.2 Dead Ends and Broken Loops

**DEAD END D-1: RL Agent → Strategy Parameter Update**

The trading engine (S16) describes an RL agent that generates trade management recommendations and compares optimal vs actual decisions. However, there is **no defined mechanism** for these recommendations to actually modify VMPM strategy parameters.

The system.md says "Strategy as Data" (YAML config), but there's no:
- API endpoint to update strategy config
- Validation pipeline for RL-suggested parameter changes
- Approval workflow for parameter modifications
- Rollback mechanism if new parameters underperform

**Impact:** The learning loop is one-directional. The system learns but doesn't adapt. This undermines the "self-improving" narrative.

**Recommendation:** Add a `StrategyParameterManager` module that:
1. Receives parameter change proposals from the Auditor Agent
2. Validates them against safe bounds
3. Requires human approval (or auto-approves within safe bounds)
4. Applies changes with A/B testing (run old and new params in parallel)
5. Monitors performance delta and auto-reverts if degraded

**DEAD END D-2: Backtest → Live Parity Verification**

The trading engine (§7.1) claims "Same Pipeline, Different Data Source" for backtesting. This is architecturally sound, but there's no defined mechanism to **verify** that backtest results match live behavior. No:
- Drift detection between backtest and live fills
- Slippage model calibration from live data
- Periodic backtest-live reconciliation reports

**Recommendation:** Add a `BacktestLiveComparator` that runs the last N days of live data through the backtest engine and compares fills, signals, and P&L. Flag discrepancies > threshold.

**DEAD END D-3: Monitoring Alerts → Human Action → System Recovery**

Alerts go to Telegram/Grafana, but there's no defined:
- Alert acknowledgment workflow
- Escalation path (alert → PagerDuty → phone call)
- Human action → system state change protocol (e.g., human clicks "resume trading" after black swan)

**Recommendation:** Define an alert severity → response protocol matrix with escalation timers.

---

## 4. Missing Components

### 4.1 Critical Missing Components

| Component | Why It's Needed | Severity |
|-----------|----------------|----------|
| **Configuration Management Service** | System.md defines YAML config. Trading engine defines its own YAML. Risk.md defines its own. No single config schema, no config validation, no config versioning, no hot-reload mechanism. | **CRITICAL** |
| **Service Discovery / Health Registry** | Agents need to find each other. No service registry, no heartbeat protocol between agents, no "agent X is down" detection beyond health checks. | **HIGH** |
| **Distributed Tracing** | With 16+ modules and 7 agents, debugging a signal from market data to fill requires correlating events across Redis streams. No trace ID propagation, no OpenTelemetry. | **HIGH** |
| **Schema Registry for Event Bus** | Redis streams have defined formats in system.md, but no schema validation. A malformed event could crash downstream consumers. No schema evolution strategy. | **MEDIUM** |
| **Graceful Degradation Policies** | System.md mentions "fail-safe by default" but doesn't define what happens when specific modules are degraded. E.g., if S1 (Fundamental) is down, can the system trade with reduced confidence? | **MEDIUM** |
| **Testing Strategy** | `architecture_testing.md` exists (119KB) but wasn't in scope for this review. The system and trading engine docs don't reference it. Cross-referencing needed. | **LOW** |

### 4.2 Underspecified Components

| Component | Current State | What's Missing |
|-----------|--------------|----------------|
| **LangGraph State Machine** | Referenced in system.md as orchestration tool. Trading engine uses "Agent Orchestrator" generically. | No LangGraph graph definition, no state transitions, no conditional edges. This is the **core orchestration mechanism** and it's just a name drop. |
| **LLM Integration Layer** | Multiple agents use LLMs (DeepSeek, Qwen). Each step in VMPM that uses LLM has its own description. | No unified LLM client, no token budget management, no fallback when LLM is slow/down, no prompt template management. |
| **Model Registry** | ML models referenced (FinBERT, HMM, XGBoost, CNN, RL). Training frequency defined. | No model versioning, no A/B testing framework for model updates, no model performance monitoring, no rollback on degraded model. |
| **WebSocket Protocol** | WebSocket server defined in gateway. Trading engine pushes real-time data. | No WebSocket message protocol (what messages does the client receive?), no subscription model, no reconnection handling spec. |

---

## 5. Redundancy Analysis

### 5.1 Document-Level Redundancy

| Redundancy | Documents | Overlap | Resolution |
|-----------|-----------|---------|------------|
| **Broker Connector Interface** | system.md §3.5, trading_engine.md §6.1 | Both define `BrokerConnector` ABC with nearly identical methods | Keep trading_engine.md version (more complete). System.md should reference it. |
| **Multi-Agent Architecture** | system.md §3.4, trading_engine.md §5.1 | Two different agent taxonomies for the same system | Merge into single authoritative taxonomy |
| **Risk Governor** | system.md §3.2, trading_engine.md §4.4, risk.md §1 | Three definitions of the same component | Risk.md is authoritative. Others should reference it. |
| **Event Bus Streams** | system.md §5.2, trading_engine.md §3.1 | Different stream naming conventions (`market.ticks` vs `market.data`) | Standardize on one naming convention |

### 5.2 Component-Level Redundancy

| Redundancy | Components | Analysis |
|-----------|-----------|----------|
| **S1 (Fundamental) vs News Agent** | S1 in trading_engine.md does news ingestion + sentiment + macro analysis. News Agent in system.md does the same. | They're the same thing with different names. S1 is the module, News Agent is the agent wrapping it. Document this explicitly. |
| **Risk Engine vs Risk Governor vs RMS** | Three names for overlapping risk enforcement | Already covered in Issue C-2 |
| **Position Sizing** | S11 in trading_engine.md has detailed sizing formula. Risk.md has its own position sizing engine. | Risk.md version is more comprehensive. S11 should delegate to Risk.md's sizing engine. |
| **Black Swan Detection** | Defined in trading_engine.md §15, risk.md §8, and as a "Sentinel Agent" in trading_engine.md §5.1 | Three definitions. Consolidate into risk.md as authoritative, reference from others. |

---

## 6. Deployability Assessment

### 6.1 Phase 1: $7 Micro Account — Is It Deployable?

**Verdict: YES, with caveats.**

**What works:**
- Docker Compose stack (Python + Redis + TimescaleDB + Grafana) is standard and deployable
- MT5 via Wine on Linux is feasible (community-proven)
- Single-machine deployment with all components is realistic for Phase 1
- SQLite → PostgreSQL migration path is defined

**What's problematic:**
- **ClickHouse in Phase 1?** System.md lists ClickHouse in L1 Data Foundation but Phase 1 deployment doesn't include it. When does it get added? No trigger defined.
- **6 databases for $7 account?** TimescaleDB, PostgreSQL, Redis, ClickHouse, Object Storage, SQLite — that's excessive for Phase 1. Should start with PostgreSQL + Redis only.
- **LLM costs not budgeted.** S1, S2, S10, S16 all use LLMs. At $7 capital, LLM API costs could exceed trading profits. Need a cost model.
- **MT5 on Linux via Wine** is fragile. The system.md mentions it casually but `architecture_testing.md` (not reviewed) likely addresses this.

**Recommendation:** Define a strict Phase 1 technology subset:
- Database: PostgreSQL only (TimescaleDB as extension)
- Cache: Redis
- Broker: MT5 only
- LLM: Local small model (e.g., Qwen-7B) or disable LLM-dependent steps
- ML: No ML in Phase 1 (rule-based only)
- Monitoring: Console logs + basic Grafana

### 6.2 Phase 2: Live Trading VPS — Is It Deployable?

**Verdict: YES.**

- Hetzner CX31 at $15/mo is realistic
- Docker Compose with all core services fits in 8GB RAM
- MT5 via Wine on VPS is proven in the retail trading community
- Nginx reverse proxy for API gateway is standard

**Gap:** No mention of MT5 terminal licensing. MT5 terminals require a broker-provided login. Running MT5 headlessly on a VPS requires specific broker support. FXPesa may or may not support this.

### 6.3 Phase 3-4: Cloud/Institutional — Is It Deployable?

**Verdict: PARTIALLY — needs more detail.**

- Kubernetes deployment is described at a high level but no Helm charts, no resource limits, no pod disruption budgets
- Multi-region DR is mentioned but failover mechanism is hand-wavy
- GPU nodes for ML inference — which ML models need GPU? FinBERT inference is CPU-feasible. CNN training needs GPU but is batch, not real-time.
- FIX protocol connector is listed but FIX is extremely complex to implement. No detail on FIX session management, sequence numbers, heartbeat handling.

### 6.4 Resource Estimation Gaps

| Resource | Phase 1 | Phase 2 | Issue |
|----------|---------|---------|-------|
| **RAM** | 8GB stated | 8GB stated | 16 Python modules + Redis + TimescaleDB + Grafana + Prometheus + MT5 (Wine) will likely exceed 8GB |
| **CPU** | 4 cores | 4 cores | LLM inference (even local 7B) needs more than 4 cores for acceptable latency |
| **Storage** | 50GB | 80GB | Tick data at 1-100 ticks/sec for multiple pairs will fill 80GB in weeks without compression |
| **Network** | Not specified | Not specified | MT5 + CCXT + News APIs + LLM API — need stable low-latency connection |

---

## 7. Architectural Risks

### Risk R-1: LLM Dependency in Critical Path (SEVERITY: HIGH)

**Description:** The VMPM pipeline uses LLMs in S1 (fundamental analysis), S2 (bias fusion), S10 (confluence reasoning), and S16 (journal analysis). LLMs have:
- Variable latency (100ms to 30s+)
- Cost that scales with usage
- Availability dependencies on external APIs
- Non-deterministic outputs

**Impact:** A slow LLM response during a fast-moving market could mean the difference between catching a setup and missing it. An LLM outage could halt the entire strategy pipeline.

**Mitigation:**
- Define hard timeout for LLM calls (e.g., 2s). If timeout, fall back to rule-based decision.
- Cache LLM responses for similar market conditions.
- Make LLM enhancement optional, not required. Core pipeline should work without LLMs.
- Budget LLM costs per trade and skip LLM calls when budget exceeded.

### Risk R-2: Event Bus as Single Point of Failure (SEVERITY: HIGH)

**Description:** All inter-module communication goes through Redis Streams. If Redis dies:
- No signals flow
- No orders can be submitted
- No risk checks can be performed
- System enters "safe mode" (close all positions)

This is acknowledged in system.md but the mitigation ("close all positions") is nuclear. A Redis failure shouldn't require liquidating positions.

**Mitigation:**
- Redis Sentinel or Redis Cluster for HA
- Direct function calls as fallback for critical paths (risk check, order submission)
- In-memory event queue as last-resort fallback
- Broker-side stops/TPs remain active regardless of system state

### Risk R-3: Complexity at $7 Scale (SEVERITY: MEDIUM)

**Description:** The architecture describes 16 strategy modules, 7 agents, 6 databases, 4+ broker connectors, multiple ML models, and a full monitoring stack. At $7 capital, the operational complexity cost (time, debugging, maintenance) vastly exceeds the potential trading returns.

**Impact:** Developer burnout, abandoned project, or perpetual "building" phase with no live trading.

**Mitigation:**
- Define an explicit "MVP" that's 20% of the architecture delivering 80% of the value
- Phase 1 should be: 1 pair, 1 broker, rule-based (no ML, no LLM), 5 core VMPM steps (S3, S4, S5, S8, S10), PostgreSQL + Redis
- Add complexity only after profitability is proven

### Risk R-4: Strategy-as-Data Without Validation (SEVERITY: MEDIUM)

**Description:** System.md declares "Strategy as Data" (YAML config), but there's no:
- Schema validation for strategy configs
- Constraint checking (e.g., "max_risk_per_trade can't exceed max_total_exposure")
- Version control integration for strategy changes
- Testing framework for strategy parameter changes

**Impact:** A misconfigured YAML could allow 100% risk per trade. No guardrails.

**Mitigation:** JSON Schema or Pydantic model for all strategy configs. Validation at load time. Diff-based review for strategy changes.

### Risk R-5: Backtest-Live Divergence (SEVERITY: MEDIUM)

**Description:** The backtesting engine claims "same pipeline, different data source," but:
- Historical data quality differs from live data (gaps, revisions)
- Slippage models are approximations
- Spread models don't capture real-time liquidity
- News sentiment is only available in real-time, not historically

**Impact:** Backtested strategies may perform significantly differently in live trading.

**Mitigation:**
- Paper trading phase with live data but simulated execution
- Continuous backtest-live reconciliation
- Conservative slippage/spread assumptions in backtests
- Out-of-sample validation as standard practice

### Risk R-6: Security of Broker Credentials (SEVERITY: HIGH)

**Description:** `architecture_security.md` defines a comprehensive security model, but:
- Phase 1 deployment stores credentials in environment variables
- MT5 credentials give direct access to real money
- No mention of credential rotation for MT5 (which typically requires broker portal access)
- The gap between security architecture (institutional-grade) and Phase 1 reality (Docker env vars) is enormous

**Impact:** Credential theft = direct fund loss.

**Mitigation:**
- Phase 1: Use MT5 demo accounts only until security infrastructure is built
- Implement credential encryption at rest from day one (even if simplified)
- Never store live broker credentials in plaintext, even in Phase 1

---

## 8. Consistency Issues

### 8.1 Naming Inconsistencies

| Concept | Name in System.md | Name in Trading Engine.md | Name in Risk.md | Resolution Needed |
|---------|-------------------|--------------------------|-----------------|-------------------|
| Risk enforcement | Risk Agent | Risk Governor | Risk Governor / RMS | Standardize |
| Position sizing | Position sizing (S11) | S11 Position Sizing Module | Position Sizing Engine | OK — same thing |
| Event streams | `market.ticks`, `signals.active` | `market.data`, `signals.fundamental` | `risk.drawdown`, `risk.exposure` | Align stream naming |
| Order types | UnifiedOrder | TradeOrder | TradeOrder (from trading engine) | Standardize on one |
| Agent messages | AgentMessage (system.md) | AgentMessage (trading_engine.md) | RiskEvent (risk.md) | Unify message protocol |

### 8.2 Interface Inconsistencies

**BrokerConnector interface** is defined in both system.md and trading_engine.md with slightly different method signatures:

- system.md: `place_order(order: UnifiedOrder) -> OrderResult`
- trading_engine.md: `place_order(order: TradeOrder) -> OrderResult`
- system.md has `get_spread()`, trading_engine.md doesn't
- trading_engine.md has `get_ohlcv()`, system.md doesn't

**Recommendation:** Define BrokerConnector in exactly one place and reference it everywhere else.

### 8.3 Configuration Inconsistencies

- system.md config: `risk.max_risk_per_trade: 0.02`
- trading_engine.md config: `risk_governor.max_risk_per_trade_pct: 2.0`
- risk.md: Uses percentages differently

The same parameter is represented as a decimal (0.02) in one place and a percentage (2.0) in another. This is a bug-prone pattern.

**Recommendation:** Standardize on decimal (0.02) everywhere. Add a Pydantic config model with validators.

---

## 9. Recommendations Summary

### 9.1 Critical (Do Before Implementation)

| # | Recommendation | Effort |
|---|---------------|--------|
| 1 | **Unify agent taxonomy** — Choose one agent model (system.md's coordinator pattern or trading_engine.md's layer-based pattern) and make the other reference it | 1 day |
| 2 | **Single source of truth for interfaces** — BrokerConnector, AgentMessage, RiskCheck, TradeOrder defined in exactly one location | 1 day |
| 3 | **Define Phase 1 MVP explicitly** — List exactly which modules, databases, and features are in scope for the $7 deployment | 1 day |
| 4 | **Add LLM fallback paths** — Every LLM-dependent step must have a rule-based fallback with defined timeout | 2 days |

### 9.2 Important (Do Before Live Trading)

| # | Recommendation | Effort |
|---|---------------|--------|
| 5 | **Configuration management** — Single Pydantic config schema, validation, versioning | 3 days |
| 6 | **Distributed tracing** — Add trace IDs to all events, OpenTelemetry integration | 2 days |
| 7 | **Schema registry for event bus** — Validate event formats at publish time | 2 days |
| 8 | **Feedback loop closure** — Define how RL/auditor recommendations modify strategy parameters | 3 days |
| 9 | **Alert escalation protocol** — Define severity → response → escalation matrix | 1 day |
| 10 | **State authority matrix** — Define which database is source of truth for each state type | 1 day |

### 9.3 Nice to Have (Do Before Scaling)

| # | Recommendation | Effort |
|---|---------------|--------|
| 11 | LangGraph state machine definition | 3 days |
| 12 | Model registry with versioning | 2 days |
| 13 | WebSocket protocol specification | 1 day |
| 14 | Graceful degradation policies per module | 2 days |
| 15 | Backtest-live reconciliation framework | 3 days |

---

## 10. Conclusion

The Alpha Stack architecture is a **well-researched, ambitious design** that demonstrates strong domain knowledge in both trading systems and software architecture. The VMPM 16-step pipeline is a clever abstraction that makes the strategy auditable and modifiable. The risk management architecture is particularly strong — the layered defense model with hard limits is exactly right for a trading system.

The primary weaknesses are:
1. **Documentation fragmentation** — Key concepts (agents, risk, events) are defined differently across documents
2. **LLM dependency risk** — Too many critical-path dependencies on non-deterministic, variable-latency LLM calls
3. **Complexity vs. capital mismatch** — The full architecture is designed for institutional scale but the starting point is $7
4. **Incomplete feedback loops** — The system can learn but can't automatically improve

**Bottom line:** The architecture is sound enough to begin implementation. Start with the Phase 1 MVP (recommendation #3), unify the interfaces (#2), and add LLM fallbacks (#4). The rest can be addressed iteratively as the system matures and capital grows.

---

*Review completed by Architecture Review Agent — System Coherence*
*All findings based on cross-referencing the 6 architecture documents that exist. 3 requested documents (multi_agent, strategy_flow, agent_communication) do not exist and were not needed — their content is covered in the existing documents, albeit with some inconsistencies.*
