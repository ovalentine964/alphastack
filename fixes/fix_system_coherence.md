# Alpha Stack — System Coherence Fix

> **Fix Type:** Architecture Coherence Resolution
> **Version:** 1.0 · **Date:** 2026-07-11
> **Based On:** `review_6_system_coherence.md` (Architecture Review Agent)
> **Scope:** Fix the 3 critical issues identified in the system coherence review
> **Status:** Decision Document — Apply to all architecture docs after approval

---

## Executive Summary

This document resolves the 3 critical coherence issues found across Alpha Stack's architecture documents. For each issue, we define the **canonical resolution** and list the **exact changes** required in each affected document.

**Affected Documents:**
- `architecture_multi_agent.md` (primary — defines agent system)
- `architecture_strategy_flow.md` (defines pipeline flow)
- `architecture_agent_communication.md` (defines messaging protocol)
- `architecture_database.md` (defines data storage)
- `architecture_memory.md` (defines memory layers)

---

## Issue 1: Agent↔Module Mapping Ambiguity

### Problem

The review identified two competing agent taxonomies. After cross-referencing the actual documents, the real situation is:

- `architecture_multi_agent.md` defines **16 agents by function**: Orchestrator, Fundamental, Structure, Liquidity, SMC, Momentum, Candlestick, Signal Aggregator, Entry, Risk Gate, TP, Trade Mgmt, Execution, Monitor, Reflection, Journal
- `architecture_strategy_flow.md` defines **16 pipeline steps** that map to agents, but uses a **phase-based grouping** (Phase 1–6) rather than the multi_agent doc's **depth-based hierarchy** (Depth 0/1/2)
- `architecture_agent_communication.md` uses a **third grouping**: Analysis Agents, Decision Agents, Management Agents

These three groupings describe the same system but use different organizational axes, creating confusion about which is authoritative.

### Resolution: Unified Agent Taxonomy

**The `architecture_multi_agent.md` agent taxonomy is the single source of truth.** All other documents reference it.

The unified taxonomy has **three orthogonal classification axes** (all valid, all referencing the same agents):

#### Axis 1: Pipeline Step (What) — from strategy_flow.md

| Step | Name | Agent |
|------|------|-------|
| 1 | Fundamental Intelligence | Fundamental Agent |
| 2 | Market Bias | Structure Agent |
| 3 | Session Analysis | Structure Agent |
| 4 | Market Structure | Structure Agent |
| 5 | Support & Resistance | Structure Agent (S/R Module) |
| 6 | Liquidity Detection | Liquidity Agent |
| 7 | Smart Money Concepts | SMC Agent |
| 8 | RSI Confirmation | Momentum Agent |
| 9 | Candlestick Confirmation | Candlestick Agent |
| 10 | Trade Entry | Entry Agent |
| 11 | Position Sizing | Entry Agent |
| 12 | Risk Gate | Risk Gate Agent |
| 13 | Take Profit | TP Agent |
| 14 | Trade Management | Trade Mgmt Agent |
| 15 | Exit Conditions | Trade Mgmt Agent |
| 16 | Journal & Learning | Journal Agent + Reflection Agent |

#### Axis 2: Orchestration Depth (Who reports to whom) — from multi_agent.md

| Depth | Agents |
|-------|--------|
| **Depth 0** | Orchestrator Agent |
| **Depth 1** | Fundamental, Structure, Liquidity, SMC, Momentum, Candlestick, Signal Aggregator, Entry, Risk Gate, TP, Trade Mgmt, Execution, Monitor, Reflection, Journal |
| **Depth 2** | Workers spawned by Depth 1 agents (News Worker, Sentiment Worker, Regime Detector, etc.) |

#### Axis 3: Functional Category (How they behave) — from agent_communication.md

| Category | Agents | Behavior |
|----------|--------|----------|
| **Analysis** | Fundamental, Structure, Liquidity, SMC, Momentum, Candlestick | Produce signals from market data |
| **Decision** | Signal Aggregator, Entry, Risk Gate | Score, size, and gate trades |
| **Execution** | Execution | Submit orders to brokers |
| **Management** | TP, Trade Mgmt, Monitor | Manage open positions and system health |
| **Learning** | Reflection, Journal | Record, analyze, and improve |
| **Coordination** | Orchestrator | Route, gatekeep, and coordinate |

### Required Changes

| Document | Section | Change |
|----------|---------|--------|
| `architecture_multi_agent.md` | §2.1 | Add "Canonical Agent List" header. Add cross-reference note: "This is the authoritative agent taxonomy. See strategy_flow.md §12 for step mapping, agent_communication.md §5 for category mapping." |
| `architecture_strategy_flow.md` | §12 (Appendix) | Add header: "Agent definitions are in architecture_multi_agent.md §2. This section maps pipeline steps to those agents." |
| `architecture_agent_communication.md` | §5.1 | Add header: "Agent definitions are in architecture_multi_agent.md §2. This section classifies agents by communication pattern." |

---

## Issue 2: Risk Governor vs Risk Agent vs Risk Gate Naming Conflict

### Problem

The review identified three different names for the risk enforcement component:

1. **"Risk Agent"** — referenced in the review as being in a "system.md" (document does not exist in current set)
2. **"Risk Governor"** — referenced in the review as being in a "trading_engine.md" (document does not exist in current set)
3. **"Risk Gate Agent"** — used in `architecture_multi_agent.md` and `architecture_strategy_flow.md`
4. **"RiskValidator"** — Python class in `architecture_multi_agent.md` §10.4
5. **"Risk Gate"** — pipeline Step 12 in `architecture_strategy_flow.md`

After reviewing all existing documents, the **actual** naming in the current doc set is:

| Document | Term Used | Context |
|----------|-----------|---------|
| `architecture_multi_agent.md` | **Risk Gate Agent** | Agent name (§2.2.J) |
| `architecture_multi_agent.md` | **RiskValidator** | Python class (§10.4) |
| `architecture_strategy_flow.md` | **Risk Gate** | Pipeline Step 12 (§7) |
| `architecture_agent_communication.md` | **Risk Gate Agent** | Agent ID: `risk_gate_agent` |
| `architecture_database.md` | **risk engine** | Referenced in Redis schema |

The review's references to "Risk Agent", "Risk Governor", and "RMS" come from documents that don't exist in the current set (`architecture_system.md`, `architecture_trading_engine.md`, `architecture_risk.md`). However, the naming is still inconsistent within the existing documents.

### Resolution: Standardized Risk Naming

**Canonical name: `Risk Gate Agent`**

This is the only name used for the risk enforcement component. The layered architecture is:

```
┌─────────────────────────────────────────────────────────┐
│                    RISK ENFORCEMENT STACK                 │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  LAYER 3: RISK GATE AGENT (Agent — L4 Orchestration)    │
│  ┌────────────────────────────────────────────────────┐  │
│  │  • LLM-based reasoning about risk context          │  │
│  │  • Evaluates: regime, session, correlation, news   │  │
│  │  • Can MODIFY trade params (reduce size, delay)    │  │
│  │  • Spans: Multi-Agent Orchestrator as Depth 1      │  │
│  │  • Loop type: Evaluation                           │  │
│  └────────────────────────────────────────────────────┘  │
│                         │ wraps                          │
│                         ▼                                │
│  LAYER 2: RISK VALIDATOR (Code — Infrastructure)         │
│  ┌────────────────────────────────────────────────────┐  │
│  │  • Hard-coded rule enforcement (Python class)      │  │
│  │  • Cannot be overridden by LLM or prompts          │  │
│  │  • Checks: max risk, daily loss, positions, DD     │  │
│  │  • Class: `RiskValidator` in TradingEngine          │  │
│  │  • Runs: BEFORE order submission                   │  │
│  └────────────────────────────────────────────────────┘  │
│                         │ uses                           │
│                         ▼                                │
│  LAYER 1: RISK CONFIG (Configuration)                    │
│  ┌────────────────────────────────────────────────────┐  │
│  │  • YAML/JSON risk parameters                       │  │
│  │  • max_risk_per_trade, max_daily_loss, etc.        │  │
│  │  • Loaded at startup, hot-reloadable               │  │
│  │  • Validated by Pydantic schema                    │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

**Naming rules:**

| Context | Use This Name | NOT This |
|---------|--------------|----------|
| Agent name (multi-agent system) | **Risk Gate Agent** | Risk Agent, Risk Governor |
| Pipeline step | **Risk Gate (Step 12)** | Risk Governor, RMS |
| Python class | **RiskValidator** | RiskGovernor, RiskAgent |
| Redis stream | **pipeline.risk_gate** | pipeline.risk, pipeline.rms |
| Consumer group | **cg:risk_gate** | cg:risk_agent, cg:risk_governor |
| Agent ID | **risk_gate_agent** | risk_agent, risk_governor |
| Discussion/ docs | **Risk Gate** | Risk Governor, RMS |

### Required Changes

| Document | Section | Change |
|----------|---------|--------|
| `architecture_multi_agent.md` | §2.2.J | Add note: "This is the canonical risk enforcement agent. Do not use 'Risk Governor' or 'RMS' — use 'Risk Gate Agent'." |
| `architecture_multi_agent.md` | §10.4 | Add note: "`RiskValidator` is the code-layer component wrapped by the Risk Gate Agent." |
| `architecture_strategy_flow.md` | §7 | Add note: "The Risk Gate (Step 12) is implemented by the Risk Gate Agent (see architecture_multi_agent.md §2.2.J) wrapping the RiskValidator class." |
| `architecture_agent_communication.md` | §5.1 | Standardize all references to `risk_gate_agent` / `pipeline.risk_gate`. Already consistent — no changes needed. |
| `architecture_database.md` | §5.1 | Change `risk engine` references to `Risk Gate Agent` or `RiskValidator` as appropriate. |

---

## Issue 3: Shared State Location Conflict

### Problem

Different documents describe shared state storage differently:

| Document | What It Says | Implication |
|----------|-------------|-------------|
| `architecture_multi_agent.md` §3.1 | "Shared State (Redis Hashes)" — positions, portfolio, regime, session, risk limits, system health all in Redis | Redis is the source of truth for all live state |
| `architecture_database.md` §4 | PostgreSQL is "single source of truth" for orders, positions, trades (ACID, SERIALIZABLE) | PostgreSQL is the source of truth for positions |
| `architecture_database.md` §5 | Redis is "hot path" — sub-ms access for live decisions | Redis is a cache, not source of truth |
| `architecture_database.md` §10.4 | "Redis rebuilds from PostgreSQL on startup" | PostgreSQL is authoritative; Redis is ephemeral |
| `architecture_memory.md` §3 | Working memory in Redis, short-term in Redis+PostgreSQL, long-term in PostgreSQL+pgvector | Layered model with different authorities per layer |

The conflict: **multi_agent.md says Redis is the source of truth for positions. database.md says PostgreSQL is. memory.md says it depends on the layer.**

### Resolution: State Authority Matrix

**One canonical source of truth per data type. Redis is always the hot cache; PostgreSQL/TimescaleDB is always the durable store.**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    STATE AUTHORITY MATRIX                                │
├─────────────────────┬──────────────────┬────────────────┬───────────────┤
│ Data Type           │ Source of Truth   │ Hot Cache      │ Written By    │
├─────────────────────┼──────────────────┼────────────────┼───────────────┤
│ Open Positions      │ PostgreSQL       │ Redis Hash     │ Execution     │
│                     │ (positions table)│ (state:pos*)   │ Agent         │
├─────────────────────┼──────────────────┼────────────────┼───────────────┤
│ Orders (all states) │ PostgreSQL       │ Redis Hash     │ Execution     │
│                     │ (orders table)   │ (open only)    │ Agent         │
├─────────────────────┼──────────────────┼────────────────┼───────────────┤
│ Portfolio Metrics   │ PostgreSQL       │ Redis Hash     │ Portfolio     │
│ (equity, P&L)       │ (computed)       │ (state:port*)  │ Aggregator    │
├─────────────────────┼──────────────────┼────────────────┼───────────────┤
│ Market Regime       │ Redis Hash       │ (is the source)│ Structure     │
│                     │ (state:regime*)  │                │ Agent         │
├─────────────────────┼──────────────────┼────────────────┼───────────────┤
│ Session State       │ Redis Hash       │ (is the source)│ Orchestrator  │
│                     │ (state:session*) │                │               │
├─────────────────────┼──────────────────┼────────────────┼───────────────┤
│ Risk Limit Usage    │ Redis Hash       │ (is the source)│ Risk Gate     │
│                     │ (state:risk*)    │                │ Agent         │
├─────────────────────┼──────────────────┼────────────────┼───────────────┤
│ Agent Health        │ Redis Hash       │ (is the source)│ Each Agent    │
│                     │ (state:system*)  │                │ (heartbeat)   │
├─────────────────────┼──────────────────┼────────────────┼───────────────┤
│ Signal Cache        │ Redis Hash       │ (is the source)│ Each Signal   │
│ (latest per agent)  │ (state:sig*)     │                │ Agent         │
├─────────────────────┼──────────────────┼────────────────┼───────────────┤
│ Market Data (ticks) │ TimescaleDB      │ Redis (60s TTL)│ Data Pipeline │
│                     │ (ticks table)    │ (tick:{sym})   │               │
├─────────────────────┼──────────────────┼────────────────┼───────────────┤
│ Market Data (candles│ TimescaleDB      │ Redis (until   │ Data Pipeline │
│                     │ (market_data)    │  next candle)  │               │
├─────────────────────┼──────────────────┼────────────────┼───────────────┤
│ Trade History       │ PostgreSQL       │ None           │ Journal       │
│                     │ (trades table)   │                │ Agent         │
├─────────────────────┼──────────────────┼────────────────┼───────────────┤
│ Trade Episodes      │ PostgreSQL       │ None           │ Reflection    │
│ (with embeddings)   │ (trade_episodes) │                │ Agent         │
├─────────────────────┼──────────────────┼────────────────┼───────────────┤
│ Strategy Config     │ PostgreSQL/      │ Redis (on      │ Human /       │
│                     │ YAML files       │  startup)      │ Orchestrator  │
├─────────────────────┼──────────────────┼────────────────┼───────────────┤
│ Signal Weights      │ PostgreSQL       │ Redis (loaded  │ Reflection    │
│                     │ (patterns table) │  at startup)   │ Agent         │
└─────────────────────┴──────────────────┴────────────────┴───────────────┘
```

### Key Rules

1. **Financial data (positions, orders, trades) → PostgreSQL is ALWAYS the source of truth.** Redis is a hot cache that can be rebuilt from PostgreSQL + broker APIs.

2. **Ephemeral operational state (regime, session, risk limits, agent health, signal cache) → Redis is the source of truth.** These are transient and don't survive restarts. Reconstructed from live data on startup.

3. **Market data → TimescaleDB is the source of truth.** Redis holds the latest tick/candle for sub-ms access; TimescaleDB holds the full history.

4. **Learning artifacts (trade episodes, signal weights, lessons) → PostgreSQL is the source of truth.** Redis may cache for performance but is never authoritative.

5. **On Redis failure:** All financial state rebuilds from PostgreSQL + broker APIs. Operational state reconstructs from agent restart. No data loss.

6. **On PostgreSQL failure:** System halts all trading immediately. No new orders until PostgreSQL recovers. Existing positions protected by broker-side stops.

### Redis Key Naming Convention (Canonical)

To eliminate ambiguity, all Redis keys follow this pattern:

```
{namespace}:{entity}[:{identifier}]

Namespaces:
  state:*       → Shared operational state (ephemeral, source of truth in Redis)
  cache:*       → Cached data (source of truth elsewhere, rebuildable)
  pipeline:*    → Agent communication streams
  events:*      → Broadcast pub/sub channels
  request:*     → Direct agent request inbox
  response:*    → Direct agent response
  dedup:*       → Deduplication keys
  trace:*       → Pipeline execution traces
  processed:*   → Consumer dedup keys

Examples:
  state:positions:{account_id}:{symbol}  → Current position (hot, from Execution Agent)
  state:portfolio:{account_id}           → Portfolio metrics (hot, from Portfolio Aggregator)
  state:regime:{symbol}                  → Current regime (source of truth, from Structure Agent)
  state:session                         → Session state (source of truth, from Orchestrator)
  state:risk:{account_id}               → Risk limit usage (source of truth, from Risk Gate)
  state:system                          → System health (source of truth, from Monitor)
  cache:ohlcv:{symbol}:{timeframe}      → Latest candle (cached from TimescaleDB)
  cache:tick:{symbol}                   → Latest tick (cached from TimescaleDB)
  cache:book:{symbol}                   → Latest order book (cached)
```

### Required Changes

| Document | Section | Change |
|----------|---------|--------|
| `architecture_multi_agent.md` | §3.1 | Replace "Shared State (Redis + PostgreSQL)" with: "Shared State follows the State Authority Matrix. Redis holds ephemeral operational state (source of truth). PostgreSQL holds financial state (source of truth, cached in Redis). See architecture_database.md §5 for Redis schema." |
| `architecture_multi_agent.md` | §3.4 (Channel Topology) | Update `state:*` keys to use canonical naming. Add note: "Financial state in Redis is a hot cache; PostgreSQL is source of truth. Operational state in Redis is source of truth." |
| `architecture_database.md` | §5.1 | Add header: "Redis serves as hot cache for financial data (source of truth: PostgreSQL) and as source of truth for ephemeral operational state. See State Authority Matrix above." |
| `architecture_database.md` | §10.4 | Clarify: "Redis rebuilds from PostgreSQL on startup. Operational state (regime, session, risk limits) reconstructs from live agent data." |
| `architecture_memory.md` | §3 | Align with State Authority Matrix. Working memory (Redis) = operational state (source of truth) + financial cache (not source of truth). |

---

## Summary of All Changes

### Change Count by Document

| Document | Changes Required | Priority |
|----------|-----------------|----------|
| `architecture_multi_agent.md` | 5 changes | Critical |
| `architecture_strategy_flow.md` | 2 changes | Critical |
| `architecture_agent_communication.md` | 1 change | Important |
| `architecture_database.md` | 4 changes | Critical |
| `architecture_memory.md` | 2 changes | Important |

### Implementation Order

1. **`architecture_multi_agent.md`** — This is the primary architecture doc. Apply all 5 changes first.
2. **`architecture_database.md`** — Apply State Authority Matrix and Redis naming convention.
3. **`architecture_strategy_flow.md`** — Add cross-references to multi_agent.md.
4. **`architecture_agent_communication.md`** — Add cross-reference (already mostly consistent).
5. **`architecture_memory.md`** — Align memory layers with State Authority Matrix.

### What This Does NOT Fix

These issues are noted in the review but are **out of scope** for this coherence fix:

- Missing LLM fallback paths (Risk R-1)
- Event Bus single point of failure (Risk R-2)
- Complexity at $7 scale (Risk R-3)
- Strategy-as-Data validation (Risk R-4)
- Backtest-Live divergence (Risk R-5)
- Broker credential security (Risk R-6)
- RL feedback loop closure (Dead End D-1)
- Configuration management service
- Distributed tracing
- Schema registry for event bus

These should be addressed as separate tasks.

---

## Appendix: Terminology Glossary

| Term | Definition | Canonical Document |
|------|-----------|-------------------|
| **Orchestrator Agent** | Depth 0 coordinator that routes signals, enforces pipeline order, manages HITL | multi_agent.md §2.2.A |
| **Risk Gate Agent** | Depth 1 agent that validates trade proposals against risk rules | multi_agent.md §2.2.J |
| **RiskValidator** | Python class implementing infrastructure-level risk checks | multi_agent.md §10.4 |
| **Risk Gate** | Pipeline Step 12 — the risk validation phase | strategy_flow.md §7 |
| **Signal Aggregator** | Depth 1 agent that scores confluence from all signal agents | multi_agent.md §2.2.H |
| **Trading Engine** | Code layer that separates decision-making from execution safety | multi_agent.md §10.3 |
| **State Authority Matrix** | Canonical mapping of data type → source of truth database | This document (Issue 3) |
| **Pipeline** | The 16-step data flow from market data to journal | strategy_flow.md |
| **Working Memory** | Redis-backed ephemeral state for current session | memory.md §3 |
| **Shared State** | Redis Hashes holding operational state readable by all agents | multi_agent.md §3.1, agent_communication.md §5.1 |

---

*Fix document generated: 2026-07-11*
*Apply changes to architecture docs, then delete this fix document.*
