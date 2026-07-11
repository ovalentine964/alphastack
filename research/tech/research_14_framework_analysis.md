# Research 14: Framework Analysis — OpenClaw, Hermes, & Multi-Agent Patterns for Alpha Stack

**Date:** 2026-07-11
**Purpose:** Deep analysis of OpenClaw and Hermes agent frameworks, comparison with CrewAI/AutoGen/LangGraph, and extraction of applicable patterns for Alpha Stack institutional-grade AI trading system.

---

## 1. OpenClaw Framework — Deep Architecture Analysis

### 1.1 What Is OpenClaw?

OpenClaw (v2026.5.27) is an **open-source, self-hosted, multi-channel AI gateway** with an embedded agent runtime. It is not just a chatbot wrapper — it is a full agent operating system that manages:

- **Multi-channel message routing** (Telegram, Discord, WhatsApp, Slack, Signal, iMessage, Matrix, IRC, Line, and 20+ more)
- **Session management** with daily/idle resets, compaction, and per-peer isolation
- **Cron/scheduling** for autonomous recurring tasks
- **Memory systems** (daily notes, long-term MEMORY.md, semantic search, dreaming/consolidation)
- **Skills system** (modular, gated, hot-reloadable capability modules)
- **Sub-agent spawning** with nested orchestration (up to depth 5)
- **Multi-agent routing** — multiple isolated agents in one gateway, each with own workspace, auth, sessions

**Architecture:** Single long-lived Gateway process owns all messaging surfaces. Control clients (macOS app, CLI, web UI) connect via WebSocket. Nodes (iOS/Android/macOS/headless) connect as devices with capabilities. Everything runs through a typed JSON WebSocket protocol.

**Key Insight:** OpenClaw is a **production-grade agent runtime**, not a research prototype. It handles the messy reality of multi-channel delivery, session persistence, tool execution, and autonomous scheduling — the exact infrastructure Alpha Stack needs.

### 1.2 Session Management

| Feature | OpenClaw Pattern | Alpha Stack Application |
|---------|-----------------|------------------------|
| **Session isolation** | Per-DM, per-group, per-channel-peer | Per-strategy, per-instrument, per-timeframe |
| **Daily reset** | 4:00 AM local time auto-rotate | Daily trading session boundaries (Asian/London/NY) |
| **Idle reset** | Configurable inactivity timeout | Auto-close dormant analysis sessions |
| **Compaction** | Auto-summarize old context to free tokens | Compress old market data context, keep signals |
| **Session transcripts** | JSONL persistence per session | Full trade journal with audit trail |
| **Session write lock** | Process-aware file-based locking | Prevent race conditions on order execution |

**Direct Adoption:** Alpha Stack should adopt OpenClaw's session model almost wholesale. Each trading strategy gets its own session. Market sessions (Asian/London/NY) map to daily resets. The compaction pattern is perfect for managing growing market context without losing signal.

### 1.3 Heartbeat System — The Proactive Monitoring Loop

OpenClaw's heartbeat is a **periodic agent turn** that runs in the main session on a configurable cadence (default 30m). Key features:

- **HEARTBEAT.md checklist** — agent reads a small task list each tick
- **tasks: blocks** — interval-based checks (e.g., inbox every 30m, calendar every 2h)
- **Active hours** — restrict to business hours to avoid spam
- **skipWhenBusy** — defer when sub-agents are running
- **Cost controls** — isolated sessions, light context, cheaper models for heartbeat
- **Alert vs OK** — only deliver when something needs attention; silent otherwise

**Alpha Stack Transformation:**
```
HEARTBEAT → MARKET_MONITOR.md

tasks:
- name: price-alerts
  interval: 1m
  prompt: "Check all active positions for stop-loss/take-profit triggers"
- name: news-scan  
  interval: 5m
  prompt: "Scan news feeds for high-impact events on tracked instruments"
- name: economic-calendar
  interval: 15m
  prompt: "Check upcoming economic releases in next 2 hours"
- name: correlation-check
  interval: 1h
  prompt: "Verify cross-pair correlations haven't shifted beyond thresholds"
- name: session-summary
  interval: 4h
  prompt: "Generate session P&L summary and strategy performance update"
```

**Critical Design Choice:** For trading, heartbeat intervals need to be **much shorter** than OpenClaw's default 30m. Alpha Stack should implement a **tiered monitoring system**:
- **Tier 1 (1s-1m):** Price/order monitoring via direct exchange WebSocket (NOT through LLM)
- **Tier 2 (1m-5m):** Signal generation and anomaly detection through lightweight model calls
- **Tier 3 (15m-1h):** Strategy review, news analysis, macro context updates
- **Tier 4 (4h+):** Performance review, journal consolidation, strategy adaptation

### 1.4 Memory System — Three-Layer Architecture

OpenClaw implements a sophisticated memory system:

**Layer 1: Daily Notes** (`memory/YYYY-MM-DD.md`)
- Raw working context, automatically loaded for today + yesterday
- Indexed for semantic search
- The "working memory" layer

**Layer 2: Long-Term Memory** (`MEMORY.md`)
- Curated, distilled facts, preferences, decisions
- Loaded every DM session
- Manually/automatically maintained

**Layer 3: Dreaming (Optional)**
- Background consolidation pass
- Scores candidates from short-term signals
- Promotes qualified items into MEMORY.md
- Reviewable via DREAMS.md

**Memory Tools:**
- `memory_search` — semantic hybrid search (vector + keyword)
- `memory_get` — exact file/line range read
- Multiple backends: SQLite (default), QMD, Honcho, LanceDB

**Alpha Stack Memory Architecture:**

```
LAYER 1: RAW MARKET DATA (memory/YYYY-MM-DD.md equivalent)
├── tick_YYYY-MM-DD.md — raw price/volume data
├── signals_YYYY-MM-DD.md — generated signals with timestamps
├── orders_YYYY-MM-DD.md — all order actions
└── news_YYYY-MM-DD.md — news events and sentiment

LAYER 2: TRADE JOURNAL (MEMORY.md equivalent)  
├── STRATEGIES.md — active strategy parameters and performance
├── EDGE_NOTES.md — distilled market insights and patterns
├── LESSONS.md — mistakes, corrections, adapted rules
└── MARKET_STRUCTURE.md — current regime, correlations, volatility state

LAYER 3: CONSOLIDATION (Dreaming equivalent)
├── Weekly: auto-consolidate daily signals into strategy performance
├── Monthly: review and prune stale market assumptions
└── Quarterly: full strategy audit and parameter review
```

**Key Insight:** OpenClaw's "dreaming" pattern — where an agent periodically reviews its own short-term memories and promotes durable insights to long-term memory — is **exactly** what a trading system needs for continuous strategy improvement. The agent literally learns from its own trade history.

### 1.5 Skills System — Modular Capabilities

OpenClaw's skills are **directory-based capability modules** with:
- `SKILL.md` — instructions + YAML frontmatter (name, description, metadata)
- **Gating:** binary requirements, env vars, config checks, OS filtering
- **Precedence:** workspace > project-agent > personal-agent > managed > bundled
- **Hot reload:** file watcher triggers mid-session refresh
- **Per-agent allowlists:** different agents get different skills
- **ClawHub registry:** public skill marketplace at clawhub.ai

**Alpha Stack Skills Design:**

```
skills/
├── technical-analysis/
│   └── SKILL.md — "Analyze price action using TA indicators"
│       requires: { bins: ["ta-lib"], env: ["EXCHANGE_API_KEY"] }
├── order-execution/
│   └── SKILL.md — "Execute orders via exchange API"
│       requires: { config: ["trading.enabled"] }
├── news-analysis/
│   └── SKILL.md — "Parse and score news events for market impact"
│       requires: { env: ["NEWS_API_KEY"] }
├── risk-management/
│   └── SKILL.md — "Calculate position sizes, check limits, enforce rules"
├── macro-scanner/
│   └── SKILL.md — "Monitor economic calendar and central bank communications"
├── sentiment-analysis/
│   └── SKILL.md — "Analyze social media and COT data for positioning"
└── backtest-engine/
    └── SKILL.md — "Run strategy backtests on historical data"
        requires: { bins: ["python3"], env: ["DATA_API_KEY"] }
```

**Each skill is self-contained, independently testable, and can be enabled/disabled per strategy agent.** This is the "modular strategy components" pattern Alpha Stack needs.

### 1.6 Sub-Agent Orchestration

OpenClaw supports **nested sub-agent spawning** with:
- **Depth control:** maxSpawnDepth 1-5 (default 1, recommended 2)
- **Context modes:** `isolated` (fresh) or `fork` (branched transcript)
- **Push-based completion:** children announce results back to parent
- **Concurrency limits:** maxConcurrent (default 8), maxChildrenPerAgent (default 5)
- **Cascade stop:** stopping parent stops all children
- **Auto-archive:** sessions cleaned up after configurable timeout
- **Thread bindings:** sub-agents can bind to Discord threads

**Alpha Stack Multi-Agent Architecture:**

```
DEPTH 0: COORDINATOR (main agent)
├── Receives user directives, market events
├── Decides which specialist to activate
└── Synthesizes results, delivers reports

DEPTH 1: SPECIALIST AGENTS (orchestrator tier)
├── market-scanner — "Scan all instruments, identify opportunities"
├── strategy-executor — "Execute strategy X on instrument Y"  
├── risk-manager — "Monitor portfolio risk, enforce limits"
├── news-analyst — "Process breaking news, score impact"
└── performance-auditor — "Review trades, update journal"

DEPTH 2: WORKERS (leaf tier, when needed)
├── data-fetcher — "Pull OHLCV for EUR/USD H4"
├── indicator-calc — "Run RSI/MACD/Bollinger on dataset"
└── order-placer — "Submit limit order to exchange"
```

**Key Design Principle:** OpenClaw's model where depth-2 workers **cannot spawn children** and **cannot access session tools** is critical for trading. Execution leaf nodes should be pure function calls with no autonomous decision-making.

### 1.7 Multi-Channel Communication

OpenClaw's channel system is production-hardened:
- **20+ channels** via plugins (Telegram, Discord, WhatsApp, Slack, Signal, Matrix, etc.)
- **Multi-account** support per channel
- **Deterministic routing** — bindings map (channel, account, peer) → agent
- **DM isolation** — per-channel-peer prevents context leakage
- **Broadcast groups** — one message to multiple targets

**Alpha Stack Delivery Matrix:**

| Channel | Purpose | Urgency |
|---------|---------|---------|
| **Desktop app** | Primary dashboard, charting, order management | Real-time |
| **Telegram** | Mobile alerts, quick commands, trade confirmations | High |
| **Discord** | Team collaboration, strategy discussion, logs | Medium |
| **Web dashboard** | Remote monitoring, reporting | Medium |
| **Email** | Daily/weekly reports, compliance records | Low |
| **SMS** | Emergency alerts (server down, max drawdown hit) | Critical |

### 1.8 Cron / Scheduling System

OpenClaw's cron is a **built-in Gateway scheduler** with:
- **Three schedule types:** `at` (one-shot), `every` (interval), `cron` (expression)
- **Execution styles:** main session, isolated, current session, custom session
- **Delivery modes:** announce (to channel), webhook, none
- **Retry with backoff:** exponential for transient errors
- **Webhook endpoints:** external triggers via HTTP POST
- **Model/thinking overrides** per job

**Alpha Stack Scheduled Tasks:**

```bash
# Pre-market analysis
openclaw cron add --name "Pre-Market Scan" \
  --cron "30 7 * * 1-5" --tz "America/New_York" \
  --session isolated --model "anthropic/claude-sonnet-4-6" \
  --message "Run pre-market analysis: overnight price action, economic calendar, key levels" \
  --announce --channel telegram

# Economic calendar check
openclaw cron add --name "Econ Calendar" \
  --cron "0 */4 * * * --tz UTC" \
  --session isolated \
  --message "Check economic calendar for high-impact releases in next 4 hours"

# End-of-day journal
openclaw cron add --name "Daily Journal" \
  --cron "0 17 * * 1-5" --tz "America/New_York" \
  --session isolated \
  --message "Compile daily trade journal: P&L, signals generated, lessons learned"

# Weekly strategy review
openclaw cron add --name "Weekly Review" \
  --cron "0 10 * * 6" --tz "America/New_York" \
  --session isolated --model "opus" --thinking high \
  --message "Deep weekly strategy review: performance metrics, parameter optimization suggestions"
```

### 1.9 Delegate Architecture

OpenClaw's delegate pattern enables agents with their own identity:
- **Own credentials** (email, calendar, API keys)
- **Acts on behalf of** humans, never impersonates
- **Standing orders** — rules for autonomous vs approved actions
- **Capability tiers:** Read-Only → Send-on-Behalf → Proactive
- **Hard blocks** enforced at Gateway level, not just prompt level

**Alpha Stack Application:** Each trading strategy can be a "delegate" with:
- Its own exchange API credentials (isolated)
- Standing orders (strategy parameters, risk limits)
- Capability tier (read-only analysis → paper trading → live execution)

---

## 2. Hermes Agent Framework Analysis

### 2.1 What Is Hermes?

Hermes Agent is an **open-source autonomous AI agent framework** built by [Nous Research](https://nousresearch.com), MIT-licensed. It runs as a long-running process on a server and can be interacted with via Telegram, Discord, Slack, WhatsApp, Signal, or CLI — all from a single gateway process.

**Key Differentiator:** Hermes's core innovation is the **closed learning loop** — the agent creates skills from experience, improves them during use, and nudges itself to persist knowledge.

### 2.2 Hermes Architecture

From the GitHub repo and documentation:

| Component | Description |
|-----------|-------------|
| **Gateway** | Multi-channel message routing (similar to OpenClaw) |
| **Agent** | Core agent runtime with tool execution |
| **Cron** | Built-in scheduler for autonomous tasks |
| **ACP Adapter** | Agent Communication Protocol integration |
| **ACP Registry** | Registry for external agent services |
| **Memory** | Three-layer memory: session → skills → long-term |
| **Skills** | Agent-created, self-improving skill files |
| **TUI** | Full terminal interface with multiline editing |
| **Apps** | Application layer for specialized workflows |

### 2.3 Hermes Memory System — The Closed Learning Loop

Hermes's memory is its killer feature for trading:

1. **Session Memory:** Current conversation context
2. **Skill Memory:** After complex tasks, Hermes writes work as reusable **skill files in plain markdown** on disk
3. **Long-Term Memory:** Agent-curated with periodic nudges to persist knowledge
4. **FTS5 Session Search:** Full-text search across all past conversations with LLM summarization
5. **Honcho Integration:** Dialectic user modeling for deepening understanding over time

**The Compounding Effect:** "Next time a similar task arrives, it loads the skill automatically and gets faster. The agent compounds."

**Alpha Stack Application:** This is exactly what a trading system needs. After processing a Fed rate decision, the agent creates a skill: "How to analyze Fed rate decisions." Next time, it loads that skill and processes faster with better context. After 10 similar events, the skill is highly refined.

### 2.4 Hermes vs OpenClaw — Key Differences

| Dimension | OpenClaw | Hermes |
|-----------|----------|--------|
| **Origin** | Messaging gateway evolved into agent OS | Purpose-built autonomous agent from scratch |
| **Language** | Node.js (TypeScript) | Python |
| **Memory** | File-based (MEMORY.md, daily notes) + plugins | Three-layer with auto-skill-creation |
| **Learning Loop** | Manual/heartbeat-driven memory maintenance | Autonomous skill creation from experience |
| **Skills** | External (ClawHub registry, user-created) | Self-generated from task completion |
| **Multi-agent** | Native multi-agent routing, sub-agents | Subagent spawning, ACP protocol |
| **Channels** | 20+ channels, production-hardened | Telegram, Discord, Slack, WhatsApp, Signal, CLI |
| **Maturity** | More mature, larger community (370k+ GitHub stars) | Newer, rapidly growing |
| **Deployment** | Self-hosted, KiloClaw managed option | Self-hosted, Docker, serverless (Modal/Daytona) |
| **Model Support** | Any provider via config | Any provider, Nous Portal, OpenRouter |
| **Terminal** | CLI + WebChat | Full TUI with autocomplete |

### 2.5 KiloClaw — Hosted OpenClaw

KiloClaw (by Kilo Code) is a **managed OpenClaw hosting service**:
- Deploys, hosts, and secures OpenClaw agents
- 500+ AI models via Kilo Gateway at 0% markup
- Web-based setup for integrations
- Auto-restart, monitoring, security updates
- Backed by independent security audit

**Relevance:** For Alpha Stack, the self-hosted path is preferred (exchange API keys, trading infrastructure), but KiloClaw validates that OpenClaw is production-viable for institutional use.

---

## 3. Comparison with Other Agent Frameworks

### 3.1 CrewAI

**What it is:** Open-source Python framework for orchestrating role-playing, autonomous AI agents. High-level abstractions for agent collaboration.

**Key patterns:**
- Role-based agent design (each agent has a role, goal, backstory)
- Task-driven execution with sequential/hierarchical processes
- Tool integration via function decorators
- Built-in delegation between agents

**vs OpenClaw for Alpha Stack:**
- CrewAI is a **library**; OpenClaw is a **runtime**. CrewAI gives you building blocks; OpenClaw gives you a production system.
- CrewAI lacks persistent sessions, memory systems, channel delivery, cron scheduling.
- CrewAI's role-playing model is conceptually useful but doesn't solve the infrastructure problem.
- **Verdict:** CrewAI patterns (role-based agents, task delegation) are useful as **internal design patterns** within Alpha Stack, but it cannot replace the infrastructure layer.

### 3.2 AutoGen / Microsoft Agent Framework (MAF)

**What it is:** Microsoft's multi-agent framework. AutoGen is now in **maintenance mode**; its successor is **Microsoft Agent Framework (MAF)**, released as production-ready v1.0 in April 2026.

**Key patterns:**
- Multi-agent conversations with configurable agent topologies
- Code execution in sandboxed environments
- Human-in-the-loop workflows
- Cross-runtime interoperability via A2A and MCP protocols

**vs OpenClaw for Alpha Stack:**
- MAF is enterprise-grade with Microsoft backing, but focused on general agent orchestration.
- Lacks the channel delivery, memory, and scheduling infrastructure OpenClaw provides.
- A2A protocol support could enable Alpha Stack to interoperate with other agent systems.
- **Verdict:** MAF's A2A protocol is worth adopting for inter-agent communication. The orchestration patterns are useful but don't replace OpenClaw's infrastructure.

### 3.3 LangGraph

**What it is:** Low-level orchestration framework by LangChain for building stateful, long-running agents. Focus on durable execution and graph-based workflows.

**Key patterns:**
- Graph-based agent flows (nodes + edges)
- Durable execution — persists through failures, resumes from checkpoints
- Stateful workflows with checkpointing
- Human-in-the-loop breakpoints
- Subagent support via Deep Agents package

**vs OpenClaw for Alpha Stack:**
- LangGraph's **durable execution** and **checkpointing** are highly relevant for trading (resume after crash, audit trail).
- Graph-based flows map well to trading decision trees (analyze → decide → execute → log).
- But LangGraph is a framework, not a runtime — you still need infrastructure.
- **Verdict:** LangGraph's graph-based workflow model and durable execution are worth integrating into Alpha Stack's strategy execution engine, potentially as the internal decision-making framework within OpenClaw skills.

### 3.4 Summary Comparison

| Feature | OpenClaw | Hermes | CrewAI | MAF | LangGraph |
|---------|----------|--------|--------|-----|-----------|
| **Type** | Agent Runtime | Agent Runtime | Framework | Framework | Framework |
| **Sessions** | ✅ Full | ✅ Full | ❌ | ❌ | ✅ Checkpoint |
| **Memory** | ✅ 3-layer + plugins | ✅ 3-layer + auto-skills | ❌ | ❌ | ✅ State |
| **Channels** | ✅ 20+ | ✅ 6+ | ❌ | ❌ | ❌ |
| **Cron/Schedule** | ✅ Built-in | ✅ Built-in | ❌ | ❌ | ❌ |
| **Sub-agents** | ✅ Nested 5-deep | ✅ Nested | ✅ Delegation | ✅ Multi-agent | ✅ Graph |
| **Skills** | ✅ Registry | ✅ Self-generated | ✅ Tools | ✅ Plugins | ✅ Tools |
| **Self-improvement** | ⚠️ Manual/heartbeat | ✅ Closed loop | ❌ | ❌ | ❌ |
| **Production-ready** | ✅ Yes | ✅ Yes | ⚠️ Moderate | ✅ Yes | ✅ Yes |
| **Trading fit** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ |

---

## 4. Alpha Stack Architecture Recommendations

### 4.1 Patterns to Adopt Directly from OpenClaw

These require minimal modification:

| Pattern | OpenClaw Implementation | Alpha Stack Usage |
|---------|------------------------|-------------------|
| **Gateway architecture** | Single process owns all channels | Single process owns desktop, web, mobile, exchange connections |
| **Session management** | Per-peer isolation, daily/idle reset, compaction | Per-strategy isolation, session-boundary resets, context compression |
| **Multi-channel delivery** | Bindings route (channel, account, peer) → agent | Route alerts to Telegram, reports to email, orders to exchange |
| **Cron scheduling** | Built-in scheduler with retry, delivery, webhook | Market scans, economic calendar, journal compilation |
| **Tool policy** | Per-agent allow/deny lists, profiles | Per-strategy tool permissions (some read-only, some execute) |
| **Sub-agent spawning** | sessions_spawn, sessions_yield, nested depth | Coordinator → Specialist → Worker architecture |
| **Workspace files** | AGENTS.md, SOUL.md, TOOLS.md, MEMORY.md | STRATEGY.md, RISK_RULES.md, TOOLS.md, TRADE_JOURNAL.md |
| **Skills system** | Directory-based, gated, hot-reloadable | Modular strategy components (TA, execution, risk, news) |
| **Bootstrap files** | Injected into system prompt every session | Strategy parameters, risk limits, market context every session |

### 4.2 Patterns to Adopt from Hermes

| Pattern | Hermes Implementation | Alpha Stack Adaptation |
|---------|----------------------|----------------------|
| **Closed learning loop** | Auto-create skills from complex tasks | Auto-create analysis patterns from successful trades |
| **Self-improving skills** | Skills refined during use | Strategy parameters refined based on backtest results |
| **FTS5 session search** | Full-text search across all conversations | Search across all trade history, signal logs, news events |
| **Honcho user modeling** | Dialectic model of user preferences | Model of market regime, strategy behavior patterns |
| **Skill compounding** | Skills load faster over time | Strategies become more refined and context-aware over time |

### 4.3 Patterns to Modify for Trading Context

| Pattern | Original | Trading Modification |
|---------|----------|---------------------|
| **Heartbeat (30m)** | Periodic agent check-in | **Tiered monitoring:** 1s exchange WS → 1m signal → 15m analysis → 4h review |
| **HEARTBEAT.md** | Static checklist | **Dynamic MARKET_MONITOR.md** that updates based on active positions and market hours |
| **Dreaming/memory consolidation** | Periodic background pass | **Trade journal consolidation** with performance attribution |
| **Session reset (daily)** | 4:00 AM local | **Market session boundaries** (Asian open, London open, NY open) |
| **Compaction** | Summarize old messages | **Compress old market data**, keep signal/decision context |
| **Tool execution** | Any tool, any time | **Gated execution:** analysis anytime, orders only with risk check |
| **Sub-agent autonomy** | Can use all allowed tools | **Execution leaf nodes are pure functions** — no autonomous trading |

### 4.4 Patterns to Build Differently

These are trading-specific and have no direct framework equivalent:

| Component | Why Different | Design |
|-----------|--------------|--------|
| **Exchange connectivity** | Needs persistent WebSocket, not HTTP polling | Dedicated exchange connector process feeding into gateway |
| **Order execution engine** | Needs atomic operations, idempotency, circuit breakers | Separate service with kill switch, not an LLM tool |
| **Risk management** | Must be enforced at infrastructure level, not prompt level | Gateway-level middleware that blocks orders exceeding limits |
| **Market data pipeline** | High-frequency data doesn't belong in LLM context | Separate data store (TimescaleDB/QuestDB), LLM queries on demand |
| **Backtesting engine** | Needs deterministic replay, not agent-based | Separate Python service with OHLCV data, called as tool |
| **Compliance/audit** | Regulatory requirements for trade records | Append-only audit log, separate from session transcripts |
| **Latency-sensitive execution** | LLM inference adds seconds, trading needs milliseconds | Hot path bypasses LLM entirely; LLM only for strategy decisions |

### 4.5 Recommended Alpha Stack Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    ALPHA STACK GATEWAY                    │
│              (Based on OpenClaw Architecture)              │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │ Desktop  │  │ Telegram │  │ Web App  │  │  Email  │ │
│  │  Client  │  │   Bot    │  │ Dashboard│  │ Reports │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬────┘ │
│       │              │              │              │      │
│  ┌────┴──────────────┴──────────────┴──────────────┴───┐ │
│  │              Channel Routing / Bindings              │ │
│  └────┬──────────────┬──────────────┬──────────────┬───┘ │
│       │              │              │              │      │
│  ┌────┴────┐   ┌─────┴────┐   ┌────┴────┐   ┌────┴───┐ │
│  │Trading  │   │ Analysis │   │  Risk   │   │Journal │ │
│  │Coordinator│ │  Agent   │   │ Manager │   │ Agent  │ │
│  │(Agent)  │   │ (Agent)  │   │ (Agent) │   │(Agent) │ │
│  └────┬────┘   └─────┬────┘   └────┬────┘   └────┬───┘ │
│       │              │              │              │      │
│  ┌────┴──────────────┴──────────────┴──────────────┴───┐ │
│  │              Sub-Agent Workers (Depth 2)             │ │
│  │  ┌─────┐ ┌──────┐ ┌──────┐ ┌─────┐ ┌──────────┐   │ │
│  │  │Fetch│ │Calc  │ │Parse │ │Order│ │Backtest  │   │ │
│  │  │Data │ │Indic.│ │News  │ │Place│ │Engine    │   │ │
│  │  └─────┘ └──────┘ └──────┘ └─────┘ └──────────┘   │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌─────────────────────────────────────────────────────┐ │
│  │                  SKILLS LAYER                        │ │
│  │  technical-analysis/  order-execution/  risk-mgmt/  │ │
│  │  news-analysis/  macro-scanner/  sentiment/          │ │
│  │  backtest-engine/  portfolio-optimizer/               │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌─────────────────────────────────────────────────────┐ │
│  │                 MEMORY LAYER                         │ │
│  │  L1: Daily market data, signals, orders              │ │
│  │  L2: Trade journal, strategy memory, lessons         │ │
│  │  L3: Consolidation (weekly/monthly/quarterly)        │ │
│  │  Search: FTS5 + vector semantic search               │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌─────────────────────────────────────────────────────┐ │
│  │              INFRASTRUCTURE LAYER                    │ │
│  │  Exchange WS │ Market Data DB │ Order Engine │ Cron  │ │
│  │  (persistent)│ (TimescaleDB)  │ (atomic,    │(built │ │
│  │              │                │  gated)      │ -in)  │ │
│  └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### 4.6 Implementation Priority

**Phase 1 — Foundation (Weeks 1-4):**
1. Set up OpenClaw gateway with Telegram + Desktop channels
2. Create workspace with STRATEGY.md, RISK_RULES.md, TOOLS.md
3. Implement basic skills: technical-analysis, order-execution, risk-management
4. Set up cron for economic calendar and daily journal

**Phase 2 — Multi-Agent (Weeks 5-8):**
1. Implement coordinator → specialist → worker architecture
2. Add market-scanner, news-analyst, performance-auditor agents
3. Configure per-agent tool policies and sandboxing
4. Implement sub-agent spawning with proper depth limits

**Phase 3 — Memory & Learning (Weeks 9-12):**
1. Implement three-layer memory system
2. Add semantic search across trade history
3. Implement trade journal consolidation (Hermes-style learning loop)
4. Add strategy skill auto-generation from successful patterns

**Phase 4 — Production Hardening (Weeks 13-16):**
1. Implement tiered monitoring (exchange WS → signal → analysis → review)
2. Add circuit breakers and kill switches at gateway level
3. Implement compliance audit trail
4. Add multi-channel delivery matrix with priority routing

---

## 5. Key Takeaways

### 5.1 The Big Insight

**OpenClaw solves 80% of Alpha Stack's infrastructure problems.** The session management, memory systems, channel delivery, cron scheduling, skills system, and sub-agent orchestration are exactly what a trading system needs — they just need to be pointed at financial data instead of email and calendars.

### 5.2 The Hermes Edge

Hermes's **closed learning loop** — where the agent automatically creates reusable skills from complex tasks — is the most important pattern for trading. A system that gets better at analyzing Fed decisions after each one, that compounds its knowledge of market microstructure over time, that learns from its own mistakes without manual intervention — that's the institutional edge.

### 5.3 The Critical Difference

**Neither OpenClaw nor Hermes was built for trading.** The patterns are right, but the execution layer needs to be custom:
- Exchange connectivity must be persistent WebSocket, not HTTP
- Order execution must be atomic with circuit breakers, not an LLM tool call
- Risk management must be enforced at infrastructure level, not prompt level
- Market data must flow through a dedicated pipeline, not through the LLM context

### 5.4 What NOT to Do

- ❌ Don't use CrewAI/MAF as your infrastructure — they're frameworks, not runtimes
- ❌ Don't let the LLM execute orders directly — use a gateway-level middleware
- ❌ Don't put tick data in LLM context — use a dedicated time-series database
- ❌ Don't rely on prompt-level risk management — enforce at infrastructure level
- ❌ Don't use 30-minute heartbeats for market monitoring — implement tiered monitoring

### 5.5 What TO Do

- ✅ Use OpenClaw as the gateway/runtime foundation
- ✅ Adopt Hermes's closed learning loop for strategy improvement
- ✅ Implement the three-layer memory system for trade journaling
- ✅ Use the skills system for modular strategy components
- ✅ Use sub-agents for parallel market analysis
- ✅ Use cron for scheduled market operations
- ✅ Use multi-channel delivery for alerts and reports
- ✅ Build custom infrastructure for exchange connectivity and order execution

---

## Sources

- OpenClaw documentation: `/usr/lib/node_modules/openclaw/docs/` (v2026.5.27)
- OpenClaw GitHub: https://github.com/openclaw/openclaw (370k+ stars)
- Hermes Agent GitHub: https://github.com/NousResearch/hermes-agent
- Hermes Agent docs: https://hermes-agent.nousresearch.com/docs/
- KiloClaw: https://kilo.ai/kiloclaw
- CrewAI: https://github.com/crewAIInc/crewAI
- AutoGen/MAF: https://github.com/microsoft/autogen
- LangGraph: https://github.com/langchain-ai/langgraph
- "I Switched from OpenClaw to Hermes Agent" — Medium, Apr 2026
- "I run my AI trading research engine from a Telegram chat now" — BitFinance, May 2026
- OpenClaw vs Hermes 2026 analysis — Kilo.ai (1,300 Reddit comments analyzed)
