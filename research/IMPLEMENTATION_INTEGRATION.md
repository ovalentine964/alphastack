# AlphaStack — Implementation & Integration Strategy

> **Version:** 1.0 · **Date:** 2026-07-19 · **Author:** Integration & OpenClaw Agent
> **Sources:** [`ai_week_openclaw.md`](./ai_week_openclaw.md), [`ai_week_multi_agent.md`](./ai_week_multi_agent.md), [`architecture/`](../architecture/) (36 docs)
> **Status:** Strategy Document — Ready for Architecture Review

---

## Purpose

This document answers one question: **What should AlphaStack build, buy, or borrow to reach first trade fastest?**

Every recommendation is filtered through the critical path. If it doesn't ship a live trade sooner, it's deferred.

---

## Table of Contents

1. [OpenClaw Evaluation](#1-openclaw-evaluation)
2. [Protocol Strategy — A2A, MCP, or Custom](#2-protocol-strategy--a2a-mcp-or-custom)
3. [Framework Migration Path — LangGraph → MAF or Stay](#3-framework-migration-path--langgraph--maf-or-stay)
4. [Third-Party Integrations](#4-third-party-integrations)
5. [API Design — REST vs WebSocket vs gRPC](#5-api-design--rest-vs-websocket-vs-grpc)
6. [Event Architecture — Redis Streams vs Kafka](#6-event-architecture--redis-streams-vs-kafka)
7. [Interoperability — Making Components Swappable](#7-interoperability--making-components-swappable)

---

## 1. OpenClaw Evaluation

### 1.1 What OpenClaw Actually Is

OpenClaw is a **self-hosted, multi-channel AI agent gateway** — not a trading framework, not an ML pipeline, not a broker connector. It's the "last mile" between AI agents and messaging surfaces (Telegram, Discord, WhatsApp, Signal, Slack, etc.). Its core value:

- **Gateway process** that bridges 20+ messaging channels to AI agents
- **Session management** with isolation per agent/workspace/sender
- **Model routing** with multi-provider failover (GPT-5.6, Claude, Ollama, Meta Muse, Tencent Hy3)
- **Plugin/skill system** (ClawHub marketplace, 70+ bundled skills)
- **Cron/automation** with wake-on-change scheduling
- **Mobile nodes** — iOS/Android devices as camera/location/notification endpoints
- **MIT licensed**, 532 contributors, weekly releases

### 1.2 Can OpenClaw Replace AlphaStack's Agent Layer?

**No. And it shouldn't try.**

| AlphaStack Requirement | OpenClaw Capability | Gap |
|------------------------|---------------------|-----|
| 16-step sequential pipeline (LangGraph state machine) | Generic agent routing, no graph execution | **Critical** — no typed state, no conditional edges, no checkpointing |
| Sub-second execution latency | Gateway overhead, model routing latency | **Critical** — OpenClaw adds 50-200ms per hop |
| TimescaleDB/ClickHouse/Redis data layer | SQLite for metadata only | **Critical** — no time-series, no analytics |
| Broker abstraction (MT5, CCXT, FIX) | No broker connectors | **Critical** — must build from scratch |
| Risk gates as infrastructure (not prompts) | Prompt-based guardrails only | **Critical** — risk must be deterministic |
| Backtesting with tick-level replay | No backtesting capability | **Critical** — core differentiator |
| ML pipeline (FinBERT, HMM, RL) | No ML infrastructure | **Critical** — no model training/serving |

**Verdict: OpenClaw cannot replace the agent orchestration layer.** LangGraph's typed state graphs, conditional branching, per-node timeouts, and checkpointing are non-negotiable for AlphaStack's 16-step pipeline.

### 1.3 Where OpenClaw Accelerates AlphaStack

OpenClaw is the **best fit for AlphaStack's Channel & Notification layer** — and this is on the critical path.

| Use Case | OpenClaw Feature | Time Saved |
|----------|-----------------|------------|
| **Telegram cockpit** (primary trader interface) | Native Telegram plugin with inline keyboards, media, topics, commands | **3-4 weeks** vs building from scratch |
| **Discord community** | Native Discord plugin with threads, embeds, voice | **2-3 weeks** |
| **WhatsApp alerts** | Native WhatsApp integration | **2 weeks** (vs Twilio API wiring) |
| **Signal encrypted channel** | Native Signal plugin | **2 weeks** |
| **Multi-channel notification routing** | Built-in priority routing, channel fallback | **1-2 weeks** |
| **Trader commands** (approve/pause/close) | Skill system for command handlers | **1 week** |
| **Scheduled reports** (daily P&L, weekly review) | Cron jobs with model selection | **3-5 days** |
| **Mobile push notifications** | iOS/Android native apps | **4-6 weeks** vs building native apps |

**Total time saved: 8-12 weeks** on the channel/notification layer alone.

### 1.4 Recommended Integration Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    ALPHA STACK CORE (LangGraph)                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │ Strategy │ │   Risk   │ │Execution │ │Reflection│          │
│  │  Agents  │ │  Engine  │ │  Engine  │ │  Agent   │          │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘          │
│       └────────────┴────────────┴─────────────┘                 │
│                          │                                       │
│                   ┌──────▼──────┐                                │
│                   │ Notification│                                │
│                   │   Bridge    │ ◄── Custom Python skill/       │
│                   │  (AlphaStack    │     plugin for OpenClaw        │
│                   │   skill)    │                                │
│                   └──────┬──────┘                                │
└──────────────────────────┼──────────────────────────────────────┘
                           │ HTTP/WebSocket
                   ┌───────▼───────┐
                   │   OpenClaw    │
                   │   Gateway     │
                   │  (v2026.7.1)  │
                   └───────┬───────┘
            ┌──────────────┼──────────────┐
            │              │              │
      ┌─────▼─────┐ ┌─────▼─────┐ ┌─────▼─────┐
      │ Telegram  │ │  Discord  │ │ WhatsApp  │
      │  (primary)│ │ (community)│ │  (alerts) │
      └───────────┘ └───────────┘ └───────────┘
```

### 1.5 Implementation Steps

| Step | Action | Effort | Priority |
|------|--------|--------|----------|
| 1 | Install OpenClaw 2026.7.1 in staging | 1 day | **P0** |
| 2 | Build `alphastack-notify` skill — HTTP bridge from AlphaStack event bus to OpenClaw | 1 week | **P0** |
| 3 | Configure Telegram bot with inline keyboards for trade approval | 3 days | **P0** |
| 4 | Add Discord channel for signal sharing | 2 days | **P1** |
| 5 | Add WhatsApp for critical alerts only | 2 days | **P1** |
| 6 | Build `alphastack-commands` skill — trader commands (approve, pause, close, status) | 1 week | **P1** |
| 7 | Configure cron for daily P&L reports | 1 day | **P2** |
| 8 | Evaluate mobile node integration for push notifications | 2 days | **P2** |

### 1.6 Risks

| Risk | Mitigation |
|------|-----------|
| OpenClaw breaking changes (beta releases every few days) | Pin to stable release (v2026.7.1), upgrade quarterly |
| Single maintainer (steipete) bus factor | OpenClaw is MIT-licensed; fork is always possible |
| Gateway adds latency to trader commands | Keep OpenClaw for notifications only; execution commands go direct via AlphaStack API |
| Security surface (647 tracked advisories) | Run OpenClaw in isolated container; no broker credentials in OpenClaw |

---

## 2. Protocol Strategy — A2A, MCP, or Custom

### 2.1 Protocol Landscape (July 2026)

| Protocol | Purpose | Adoption | Wire Format |
|----------|---------|----------|-------------|
| **MCP** | Agent ↔ Tool | 97M+ SDK downloads, all major providers | JSON-RPC 2.0 |
| **A2A** | Agent ↔ Agent | 150+ orgs, Linux Foundation, v1.0 stable | JSON-RPC 2.0 |
| **Custom** | AlphaStack internal | N/A | Redis Streams JSON |

### 2.2 Decision Matrix

| Communication Need | Current Design | Best Protocol | Reasoning |
|--------------------|---------------|---------------|-----------|
| Agent → Tool (market data, broker API) | Direct Python imports | **MCP** | Standardized tool interface; enables swapping data providers without agent code changes |
| Agent → Agent (pipeline handoffs) | Redis Streams | **Custom (keep Redis Streams)** | AlphaStack's sequential pipeline with typed state is simpler than A2A's discovery/delegation model. A2A adds overhead without benefit for a fixed pipeline. |
| AlphaStack → External agents (future) | N/A | **A2A** | When federating with third-party sentiment/analysis agents, A2A's Agent Card discovery is valuable |
| Agent → UI (dashboard) | REST + WebSocket | **AG-UI (emerging)** | Monitor for now; REST+WS is sufficient |
| Agent → Notification (OpenClaw) | Custom skill | **HTTP bridge** | Simplest path; OpenClaw doesn't speak A2A natively yet |

### 2.3 Recommended Adoption Timeline

**Phase 1 — First Trade (Weeks 1-8):**
- **MCP: Adopt for tool integrations.** Wrap market data APIs (Finnhub, CCXT, DefiLlama) as MCP servers. This makes data providers swappable.
- **A2A: Skip.** The pipeline is fixed and internal. A2A adds complexity without value at this stage.
- **Custom: Keep Redis Streams** for inter-agent communication. It works, it's fast, it's already designed.

**Phase 2 — Production Hardening (Months 3-6):**
- **MCP: Expand** to broker connectors. An MCP-wrapped CCXT connector means any MCP-compatible agent can execute trades.
- **A2A: Evaluate** for external agent integration (third-party research, alternative data providers).

**Phase 3 — Scale (Months 6-12):**
- **A2A: Adopt** if federating with external agents. Publish AlphaStack's Signal Aggregator as an A2A service — external agents could subscribe to AlphaStack signals.

### 2.4 MCP Implementation Sketch

```python
# Example: Wrapping CCXT as an MCP tool server
from mcp.server import Server
import ccxt

server = Server("alphastack-broker")

@server.tool("get_ticker", "Get current price for a trading pair")
async def get_ticker(symbol: str) -> dict:
    exchange = ccxt.binance()
    return exchange.fetch_ticker(symbol)

@server.tool("place_order", "Place a limit or market order")
async def place_order(symbol: str, side: str, amount: float, price: float = None) -> dict:
    exchange = ccxt.binance()
    order_type = "market" if price is None else "limit"
    return exchange.create_order(symbol, order_type, side, amount, price)
```

**Why MCP matters for AlphaStack:** When you swap from Binance to Bybit, you swap the MCP server — zero changes to agent code. When you add a new data provider, you add a new MCP server. The agent layer is decoupled from the tool layer.

---

## 3. Framework Migration Path — LangGraph → MAF or Stay

### 3.1 Framework Comparison for AlphaStack

| Criterion | LangGraph 1.0 | MAF 1.0 (Microsoft) | Claude Agent SDK |
|-----------|--------------|---------------------|-----------------|
| **State graphs** | ✅ First-class typed state, conditional edges | ✅ Magentic patterns | ⚠️ Scoped memory, no graph |
| **Per-node timeouts** | ✅ Shipped Q2 2026 | ✅ Built-in | ✅ Built-in |
| **Checkpointing** | ✅ Durable with recovery | ✅ Azure-integrated | ⚠️ Session-level |
| **Python native** | ✅ | ✅ | ✅ |
| **Production track** | ✅ Klarna, Uber | ⚠️ New, Azure-heavy | ⚠️ Anthropic-only |
| **MCP support** | ✅ Native | ✅ Native | ✅ Native |
| **A2A support** | Via adapters | ✅ Native | Via adapters |
| **Vendor lock-in** | Low (LangChain ecosystem) | High (Azure/Semantic Kernel) | High (Anthropic) |
| **Cost** | Free (OSS) | Free (OSS), Azure costs | API costs only |
| **Community** | Large, active | Microsoft-backed | Smaller |
| **Fit for 16-step pipeline** | ✅ Perfect | ⚠️ Over-engineered | ⚠️ No graph model |

### 3.2 Verdict: Stay with LangGraph

**LangGraph is the correct choice for AlphaStack.** Reasons:

1. **Typed state graphs are non-negotiable.** AlphaStack's 16-step pipeline with conditional branching (e.g., skip execution if risk gate fails) maps directly to LangGraph's graph model. MAF's Magentic patterns are designed for dynamic task decomposition, not fixed pipelines.

2. **Per-node timeouts are critical.** LangGraph Q2 2026 added exactly what AlphaStack needs — the News agent can have a 30s timeout (external API calls), the Execution agent a 2s timeout (time-critical), and the Reflection agent a 5min timeout (batch processing).

3. **DeltaChannel reduces event bus overhead.** Instead of pushing full state objects through Redis Streams, only changed fields transit between agents. For AlphaStack's pipeline where state grows at each step, this is a significant optimization.

4. **No vendor lock-in.** MAF ties AlphaStack to Azure. Claude SDK ties it to Anthropic. LangGraph is vendor-neutral — swap models freely.

5. **Industry consensus.** AutoGen is dead. MAF is too new. LangGraph is the production-proven choice at scale.

### 3.3 What to Borrow from Other Frameworks

| Pattern | Source | How to Apply |
|---------|--------|-------------|
| **Fallback model chains** | Claude Agent SDK | If primary model times out, retry with cheaper model (e.g., GPT-5.6 → Haiku for routine decisions) |
| **Hierarchical subagent spawning** | Claude Agent SDK | Future: Orchestrator spawns specialized sub-agents dynamically based on market conditions |
| **Policy engine interception** | Microsoft Agent Governance Toolkit | Insert sub-ms policy checks between agents — the Risk agent becomes a policy gate, not a prompt |
| **Pluggable backends** | CrewAI | Validate: separate agent logic from orchestration transport (Redis Streams today, Kafka tomorrow) |

### 3.4 Migration Path (If Ever Needed)

If AlphaStack outgrows LangGraph (unlikely within 12 months):

```
LangGraph 1.0 → LangGraph 2.0 (when available)
              → MAF 1.0 (only if Azure migration happens)
              → Custom framework (only at institutional scale)
```

**Do not plan for migration. Plan for LangGraph depth.** The per-node timeout, DeltaChannel, and checkpointing features are still underutilized in AlphaStack's current design.

---

## 4. Third-Party Integrations

### 4.1 Integration Priority Matrix

Ranked by impact on reaching first trade. Every integration below is evaluated on: **Does this unblock a pipeline step?**

#### Tier 1 — Unblocks First Trade (Weeks 1-4)

| Service | Purpose | Pipeline Step | Integration Method | Cost |
|---------|---------|---------------|-------------------|------|
| **CCXT** | Crypto exchange access (Binance, Bybit) | Execution, Market Data | Python library, wrap as MCP server | Free |
| **MetaTrader 5 (MT5)** | Forex broker (FXPesa) | Execution, Market Data | `MetaTrader5` Python package | Free (broker account) |
| **Finnhub** | Real-time news, earnings, economic calendar | Step 1 (Fundamental) | REST API, MCP server | Free tier: 60 calls/min |
| **TradingView (ta-lib)** | Technical indicators | Steps 2-9 (Signal agents) | Python `ta-lib` library | Free |
| **Telegram Bot API** | Primary trader interface | Notification layer | OpenClaw plugin | Free |

#### Tier 2 — Enhances Signal Quality (Weeks 4-8)

| Service | Purpose | Pipeline Step | Integration Method | Cost |
|---------|---------|---------------|-------------------|------|
| **DefiLlama** | On-chain TVL, DeFi metrics | Step 1 (Fundamental) | REST API, MCP server | Free |
| **Glassnode** | On-chain analytics (MVRV, SOPR, NVT) | Step 1 (Fundamental) | REST API | Free tier limited |
| **Coinglass** | Open interest, funding rates, liquidations | Step 6 (Liquidity) | REST API | Free tier |
| **CryptoCompare** | Historical OHLCV, social data | Data pipeline | REST/WebSocket API | Free tier: 100K calls/day |
| **LunarCrush** | Social sentiment, Galaxy Score | Step 1 (Sentiment) | REST API | Free tier |

#### Tier 3 — Production Hardening (Months 2-4)

| Service | Purpose | Pipeline Step | Integration Method | Cost |
|---------|---------|---------------|-------------------|------|
| **Polygon.io** | Institutional market data (stocks, forex, crypto) | Data pipeline | REST/WebSocket, MCP server | $29/mo starter |
| **Databento** | Tick-level market data | Backtesting, Data pipeline | Python SDK | Pay-per-use |
| **Elasticsearch** | Log aggregation, trade search | Monitoring | Self-hosted or Elastic Cloud | Free (self-hosted) |
| **Grafana + Prometheus** | Dashboards, alerting | Monitoring | Self-hosted | Free |
| **Sentry** | Error tracking | All agents | Python SDK | Free tier |

#### Tier 4 — Scale & Differentiation (Months 4+)

| Service | Purpose | Integration Method | Cost |
|---------|---------|-------------------|------|
| **Bloomberg API** | Institutional data | REST API | $$$$ (enterprise) |
| **Refinitiv (LSEG)** | Institutional data | REST/WebSocket | $$$ (enterprise) |
| **Unusual Whales** | Options flow, dark pool data | REST API | $33/mo |
| **Token Terminal** | Fundamental crypto analytics | REST API | $325/mo |
| **Messari** | Crypto research, metrics | REST API | $30/mo |

### 4.2 Integration Architecture: MCP as the Universal Adapter

```
┌─────────────────────────────────────────────────────────────┐
│                 ALPHA STACK AGENTS (LangGraph)                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ News     │ │ Strategy │ │ Risk     │ │Execution │       │
│  │ Agent    │ │ Agent    │ │ Agent    │ │Agent     │       │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘       │
│       │ MCP client  │ MCP client │ MCP client  │ MCP client  │
└───────┼─────────────┼───────────┼─────────────┼─────────────┘
        │             │           │             │
  ┌─────▼─────┐ ┌─────▼─────┐ ┌──▼──────┐ ┌───▼──────┐
  │ MCP Server│ │ MCP Server│ │MCP Server│ │MCP Server│
  │ "news"    │ │ "market"  │ │ "risk"   │ │ "broker" │
  │           │ │           │ │          │ │          │
  │ Finnhub   │ │ CCXT      │ │DefiLlama │ │ CCXT     │
  │ RSS feeds │ │ CryptoComp│ │Glassnode │ │ MT5      │
  │ LunarCrush│ │ ta-lib    │ │Coinglass │ │ FIX      │
  └───────────┘ └───────────┘ └──────────┘ └──────────┘
```

**Why this matters:** Each data provider is an MCP server. Agents are MCP clients. Swapping Binance for Bybit = swapping one MCP server config. Adding Messari = adding one MCP server. Agent code never changes.

### 4.3 Data Provider Redundancy

No single data source should be a point of failure:

| Data Type | Primary | Fallback | MCP Server |
|-----------|---------|----------|------------|
| Price feeds | CCXT (Binance) | CCXT (Bybit) | `market-data` |
| News | Finnhub | RSS feeds (free) | `news` |
| Sentiment | LunarCrush | CryptoCompare social | `sentiment` |
| On-chain | DefiLlama | Glassnode | `onchain` |
| Economic calendar | Finnhub | Investing.com scrape | `calendar` |
| Historical OHLCV | CryptoCompare | CCXT | `historical` |

---

## 5. API Design — REST vs WebSocket vs gRPC

### 5.1 Decision Matrix

| Use Case | Protocol | Latency | Complexity | Justification |
|----------|----------|---------|------------|---------------|
| **Trader commands** (approve/pause/close) | REST | <100ms | Low | Simple request-response; idempotent; cacheable |
| **Real-time price ticks** | WebSocket | <10ms | Medium | Persistent connection; high-frequency push |
| **Agent ↔ Agent pipeline handoffs** | Redis Streams | <1ms | Low | Already designed; ordered, persistent, replayable |
| **Dashboard data** (positions, P&L, signals) | WebSocket | <50ms | Medium | Push updates; don't poll |
| **Historical data queries** | REST | <500ms | Low | Request-response; pagination; caching |
| **Internal service ↔ service** | gRPC | <5ms | High | When AlphaStack splits into microservices (Phase 3+) |
| **OpenClaw ↔ AlphaStack bridge** | HTTP REST | <200ms | Low | OpenClaw skills use HTTP; simplest integration |
| **Mobile app ↔ Backend** | REST + WebSocket | <100ms | Medium | REST for commands; WS for live updates |

### 5.2 API Layer Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    EXTERNAL CLIENTS                           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ OpenClaw │ │ Tauri    │ │ Web App  │ │ Mobile   │       │
│  │ Gateway  │ │ Desktop  │ │ (React)  │ │ (Flutter)│       │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘       │
└───────┼─────────────┼───────────┼─────────────┼─────────────┘
        │ HTTP        │ WS+HTTP   │ WS+HTTP     │ REST+WS
        │             │           │             │
  ┌─────▼─────────────▼───────────▼─────────────▼─────────────┐
  │                    API GATEWAY (FastAPI)                     │
  │                                                              │
  │  /api/v1/signals/*      — Signal queries (REST)             │
  │  /api/v1/positions/*    — Position management (REST)        │
  │  /api/v1/trades/*       — Trade history (REST)              │
  │  /api/v1/config/*       — System configuration (REST)       │
  │  /api/v1/approve        — Trade approval (REST POST)        │
  │  /api/v1/pause          — System pause (REST POST)          │
  │  /ws/market             — Live price feed (WebSocket)       │
  │  /ws/portfolio          — Portfolio updates (WebSocket)     │
  │  /ws/signals            — Signal stream (WebSocket)         │
  │  /ws/events             — All events (WebSocket)            │
  │                                                              │
  │  Internal: gRPC on :50051 (future microservice split)       │
  └──────────────────────────┬──────────────────────────────────┘
                             │
  ┌──────────────────────────▼──────────────────────────────────┐
  │                    CORE ENGINE (LangGraph)                    │
  │  Agents communicate via Redis Streams (internal, not exposed)│
  └──────────────────────────────────────────────────────────────┘
```

### 5.3 API Design Principles

1. **REST for commands, WebSocket for streams.** Don't poll — push.
2. **Version everything.** `/api/v1/` from day one. Breaking changes get a new version.
3. **Idempotent POSTs.** Trade approval called twice = same result. Use idempotency keys.
4. **Rate limit external APIs.** 100 req/min per client. Internal APIs unlimited.
5. **Authenticate everything.** JWT tokens for REST. Token-based auth for WebSocket upgrade.
6. **gRPC is internal-only (Phase 3+).** Don't expose gRPC to clients. It's for service-to-service when AlphaStack splits into microservices.

### 5.4 What NOT to Build

- **GraphQL** — overkill for AlphaStack's data model. REST + WebSocket covers everything.
- **Server-Sent Events (SSE)** — WebSocket is strictly better for bidirectional needs.
- **Custom binary protocol** — premature optimization. JSON over WebSocket is fast enough until you hit 10K+ messages/sec.

---

## 6. Event Architecture — Redis Streams vs Kafka

### 6.1 Decision Matrix

| Criterion | Redis Streams | Kafka | Winner for AlphaStack |
|-----------|--------------|-------|----------------------|
| **Setup complexity** | Single binary, seconds | ZooKeeper/KRaft, minutes-hours | **Redis** |
| **Memory cost** | In-memory (bounded by RAM) | Disk-based (cheap storage) | **Kafka at scale** |
| **Throughput** | ~100K msg/sec single node | ~1M+ msg/sec per broker | **Kafka at scale** |
| **Latency** | Sub-millisecond | 2-10ms | **Redis** |
| **Persistence** | AOF/RDB snapshots | Disk-native, configurable retention | **Kafka** |
| **Consumer groups** | ✅ Built-in | ✅ Built-in (mature) | Tie |
| **Replay** | ✅ By offset/timestamp | ✅ By offset/timestamp | Tie |
| **Ordering** | Per-stream (partition key) | Per-partition | Tie |
| **Operational cost** | ~$0 (self-hosted) | ~$0 (self-hosted) to $$$ (Confluent Cloud) | **Redis** |
| **Python ecosystem** | `redis-py` (mature) | `confluent-kafka` / `aiokafka` (mature) | Tie |
| **Multi-tool integration** | Redis also serves as cache, state store, pub/sub | Kafka is single-purpose (messaging) | **Redis** (fewer moving parts) |

### 6.2 Recommendation: Redis Streams Now, Kafka Later

**Phase 1-2 (First Trade → Production): Redis Streams**

AlphaStack's current architecture already specifies Redis Streams. This is correct for the following reasons:

1. **AlphaStack is not a high-frequency trading system.** Signal generation happens on minute-to-hour timeframes. 100K msg/sec is 1000x more than needed.
2. **Redis serves triple duty:** event bus (Streams), shared state (Hashes), and cache (key-value). One process, three roles. Kafka would require a separate cache layer.
3. **Sub-millisecond latency matters for pipeline handoffs.** News agent → Strategy agent → Risk agent should complete in <10ms total. Redis delivers this. Kafka adds 5-10ms per hop.
4. **Simpler operations.** One Redis instance vs. a Kafka cluster. At $7 starting capital, operational simplicity is a feature.
5. **Already designed.** The `architecture_agent_communication.md` document has a complete Redis topology with 15+ streams, consumer groups, dead letter handling, and deduplication. Rewriting for Kafka costs 2-3 weeks with zero benefit.

**Phase 3 (Scale): Evaluate Kafka**

Migrate to Kafka when:
- Processing >50K messages/sec (unlikely until 28+ pairs × multiple timeframes × tick-level data)
- Need cross-datacenter replication for disaster recovery
- Need 30+ day message retention without memory pressure
- Multiple independent services consuming the same event stream

### 6.3 Redis Streams Topology (Already Designed — Confirm and Build)

```
PIPELINE STREAMS (ordered, persistent, at-least-once):
  pipeline.fundamental    ← Fundamental Agent output
  pipeline.structure      ← Structure Agent output
  pipeline.liquidity      ← Liquidity Agent output
  pipeline.smc            ← SMC Agent output
  pipeline.momentum       ← Momentum Agent output
  pipeline.candlestick    ← Candlestick Agent output
  pipeline.confluence     ← Signal Aggregator output
  pipeline.risk_gate      ← Risk Gate decisions
  pipeline.execution      ← Execution results
  pipeline.management     ← Trade management actions
  pipeline.journal        ← Journal entries

PUB/SUB CHANNELS (fire-and-forget, at-most-once):
  events.market_data      → Tick/bar distribution
  events.alerts           → Human-facing alerts
  events.system_health    → Agent health heartbeats
  events.kill_switch      → Emergency halt
  events.regime_change    → Market regime transitions

SHARED STATE (Redis Hashes, atomic read-modify-write):
  state:positions         → Current open positions
  state:portfolio         → Portfolio-level metrics
  state:regime            → Market regime per pair
  state:session           → Session state machine
  state:risk_limits       → Risk limit utilization
```

### 6.4 Kafka Migration Readiness

To avoid a rewrite if/when Kafka becomes necessary:

1. **Abstract the event bus.** Define an `EventBus` interface with `publish()`, `subscribe()`, `acknowledge()` methods. Implement with Redis Streams today, Kafka tomorrow.
2. **Use correlation IDs everywhere.** Kafka and Redis Streams both support partitioned ordering by key. Correlation IDs are your partition key.
3. **Keep messages self-contained.** Each message should have everything a consumer needs. Don't rely on Redis-specific features (e.g., XREAD blocking) in message design.

```python
# Abstract EventBus interface (implement with Redis or Kafka)
class EventBus(ABC):
    @abstractmethod
    async def publish(self, stream: str, message: dict, correlation_id: str) -> str: ...

    @abstractmethod
    async def subscribe(self, stream: str, group: str, consumer: str) -> AsyncIterator[Event]: ...

    @abstractmethod
    async def acknowledge(self, stream: str, group: str, message_id: str) -> None: ...
```

---

## 7. Interoperability — Making Components Swappable

### 7.1 The Swap Test

Every major component should pass the **swap test**: can you replace it with an alternative in <1 day with zero changes to other components?

| Component | Current | Alternative | Swap Difficulty | Interface |
|-----------|---------|------------|----------------|-----------|
| **LLM provider** | OpenAI GPT-5.6 | Claude, Ollama, Meta Muse | Easy (model routing) | OpenAI-compatible API |
| **Broker** | FXPesa (MT5) | Binance (CCXT) | Medium (new connector) | `BrokerConnector` ABC |
| **Data provider** | Finnhub | Polygon.io | Medium (new adapter) | `SourceAdapter` ABC |
| **Event bus** | Redis Streams | Kafka | Medium (new impl) | `EventBus` ABC |
| **Time-series DB** | TimescaleDB | QuestDB | Hard (migration) | SQL interface |
| **Cache/state** | Redis | DragonflyDB | Easy (drop-in) | Redis protocol |
| **Orchestration** | LangGraph | Custom | Hard (rewrite) | Graph API |
| **Notification** | OpenClaw | Custom bots | Medium (new impl) | HTTP bridge |
| **Sentiment model** | FinBERT | DistilBERT | Easy (same HF interface) | `transformers` API |
| **Regime model** | HMM (hmmlearn) | Custom LSTM | Medium (retrain) | `detect()` method |

### 7.2 Interface Contracts (Build These First)

These are the seams that make swapping possible. Build them before the implementations:

#### A. BrokerConnector (Already Designed)

```python
class BrokerConnector(ABC):
    """Core interface — all brokers implement this."""

    @abstractmethod
    async def connect(self) -> None: ...
    @abstractmethod
    async def place_order(self, order: Order) -> OrderResult: ...
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool: ...
    @abstractmethod
    async def get_positions(self) -> list[Position]: ...
    @abstractmethod
    async def get_balance(self) -> Balance: ...
    @abstractmethod
    async def stream_prices(self, symbols: list[str]) -> AsyncIterator[PriceTick]: ...
```

#### B. SourceAdapter (Data Providers)

```python
class SourceAdapter(ABC):
    """All data sources implement this. Wrap as MCP server for agent access."""

    @abstractmethod
    async def connect(self) -> None: ...
    @abstractmethod
    async def stream(self) -> AsyncIterator[RawEvent]: ...
    @abstractmethod
    async def fetch_historical(self, symbol: str, timeframe: str, start: datetime, end: datetime) -> list[Candle]: ...
    @abstractmethod
    async def health_check(self) -> bool: ...
```

#### C. EventBus (Message Transport)

```python
class EventBus(ABC):
    """Redis Streams today, Kafka tomorrow."""

    @abstractmethod
    async def publish(self, stream: str, message: dict, correlation_id: str) -> str: ...
    @abstractmethod
    async def subscribe(self, stream: str, group: str, consumer: str) -> AsyncIterator[Event]: ...
    @abstractmethod
    async def acknowledge(self, stream: str, group: str, message_id: str) -> None: ...
    @abstractmethod
    async def get_state(self, key: str) -> dict: ...
    @abstractmethod
    async def set_state(self, key: str, value: dict, ttl: int = None) -> None: ...
```

#### D. AgentContract (Agent Interface)

```python
class AgentContract(ABC):
    """Every agent in the pipeline implements this. Enables agent swapping."""

    @abstractmethod
    async def analyze(self, context: StrategyContext) -> AgentOutput: ...
    @abstractmethod
    async def validate_input(self, context: StrategyContext) -> bool: ...
    @abstractmethod
    async def get_confidence(self) -> float: ...
    @abstractmethod
    def get_timeout(self) -> float: ...
```

### 7.3 Configuration-Driven Composition

Use dependency injection to wire components at startup, not at code time:

```yaml
# config/alphastack.yaml
brokers:
  primary:
    type: ccxt
    exchange: binance
    config:
      api_key: ${BINANCE_API_KEY}
  secondary:
    type: mt5
    config:
      server: FXPesa-Demo

data:
  market_data:
    type: ccxt
    fallback: cryptocompare
  news:
    type: finnhub
    fallback: rss
  sentiment:
    type: lunarcrush
    fallback: cryptocompare_social

event_bus:
  type: redis_streams
  config:
    host: localhost
    port: 6379

agents:
  orchestrator:
    model: gpt-5.6
    timeout: 30s
  fundamental:
    model: gpt-5.6
    timeout: 60s
  risk:
    model: gpt-5.6
    timeout: 5s
    # Risk agent uses deterministic rules, LLM for explanation only
```

### 7.4 Interoperability Anti-Patterns

| Anti-Pattern | Why It's Bad | What to Do Instead |
|-------------|-------------|-------------------|
| Hardcoding broker API calls in agent code | Can't swap brokers without rewriting agents | Use `BrokerConnector` ABC |
| Direct Redis commands in agent logic | Can't swap event bus without rewriting agents | Use `EventBus` ABC |
| Importing specific LLM client (e.g., `openai`) in agents | Can't swap models without touching every agent | Use LangChain/LangGraph model abstraction |
| Embedding data parsing in strategy code | Can't swap data providers | Use `SourceAdapter` ABC |
| Configuration in code (magic numbers) | Can't tune without redeployment | YAML/TOML config files + environment variables |
| Monolithic single-process deployment | Can't scale individual components | Design for process isolation from day one (even if running in one process initially) |

---

## Summary: Critical Path to First Trade

| Week | Deliverable | Integration Decision |
|------|------------|---------------------|
| 1 | LangGraph pipeline skeleton with 5 core agents | Stay with LangGraph |
| 1 | Redis Streams event bus with 5 pipeline streams | Custom Redis (no Kafka) |
| 2 | CCXT connector for Binance (paper trading) | BrokerConnector ABC |
| 2 | Finnhub MCP server for news data | MCP for tools |
| 3 | FinBERT sentiment model integration | HuggingFace transformers |
| 3 | Risk gate with deterministic rules | Not prompt-based |
| 4 | OpenClaw Telegram integration for trade alerts | OpenClaw for notifications |
| 4-5 | Signal Aggregator with confluence scoring | LangGraph state graph |
| 5-6 | Execution agent with order management | BrokerConnector abstraction |
| 6-7 | Backtesting engine with historical replay | Same pipeline, different data source |
| 7-8 | First paper trade through full pipeline | End-to-end validation |

**The critical path does not include:** A2A protocol, Kafka, MAF migration, gRPC, GraphQL, Bloomberg API, or mobile apps. These are Phase 2-3 concerns.

**The critical path does include:** LangGraph + Redis Streams + CCXT + Finnhub + OpenClaw Telegram + deterministic risk gates. Build these. Ship a paper trade. Iterate.

---

*Document generated: 2026-07-19 16:21 GMT+8*
*Next review: After first paper trade (target: Week 8)*
