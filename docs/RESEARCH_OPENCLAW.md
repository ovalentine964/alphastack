# AlphaStack × OpenClaw: Multi-Agent Pattern Research

> **Date:** 2026-07-16
> **Source:** OpenClaw Framework v2026.x — `/usr/lib/node_modules/openclaw/docs/`
> **Purpose:** Identify transferable patterns for AlphaStack's multi-agent trading system

---

## Executive Summary

OpenClaw is a production-grade multi-agent orchestration framework with sophisticated session management, sub-agent spawning, task flow coordination, and memory systems. After analyzing 650+ documentation pages, the source code, and the skills system, I've identified **10 specific patterns** that map directly to AlphaStack's trading architecture needs.

The key insight: **OpenClaw treats agents as isolated, composable units with push-based communication and durable state** — exactly what a trading system needs for coordinating Swarm A (signal generation), Swarm B (execution), risk management, and portfolio optimization agents.

---

## Pattern 1: Sub-Agent Spawning (`sessions_spawn`)

### What It Is
Non-blocking spawning of isolated background agent runs that announce results back to the parent. Each sub-agent runs in its own session with its own context window.

### How It Works in OpenClaw
- Parent calls `sessions_spawn` with a task description → returns immediately with `{ runId, childSessionKey }`
- Child runs in isolation: `agent:<agentId>:subagent:<uuid>`
- On completion, result is **pushed** back to the parent via an announce mechanism
- Parent uses `sessions_yield` to wait for completions (not polling)
- Configurable depth: `maxSpawnDepth` allows orchestrator → worker hierarchies
- Concurrency control: `maxConcurrent` (default 8), `maxChildrenPerAgent` (default 5)

### Key Architecture Decisions
```json5
{
  agents: {
    defaults: {
      subagents: {
        maxSpawnDepth: 2,        // main → orchestrator → workers
        maxChildrenPerAgent: 5,  // fan-out limit per session
        maxConcurrent: 8,        // global concurrency lane
        runTimeoutSeconds: 900,  // default timeout
        model: "fast-model",     // cheaper model for sub-agents
      }
    }
  }
}
```

### How to Adapt for AlphaStack

**Spawn specialized trading sub-agents for parallel analysis:**

```typescript
// AlphaStack: Spawn parallel analysis agents
interface AlphaSpawnRequest {
  task: string;                    // "Analyze AAPL options flow for next 5 days"
  taskName?: string;               // "options_flow_aapl" — stable handle
  model?: string;                  // "alphastack/fast-sentiment" vs "alphastack/deep-fundamental"
  context?: "isolated" | "fork";   // isolated = clean slate; fork = inherit market context
  runTimeoutSeconds?: number;      // kill stale analysis after N seconds
}

// Main orchestrator spawns parallel analysts
async function runMorningScan(tickers: string[]) {
  const spawns = tickers.map(ticker =>
    alphastack.spawn({
      task: `Analyze ${ticker}: sentiment, options flow, technicals. Return structured signal.`,
      taskName: `scan_${ticker.toLowerCase()}`,
      model: "alphastack/fast-sentiment",
      context: "isolated",
      runTimeoutSeconds: 120,
    })
  );

  // Wait for all completions (push-based, not polling)
  const results = await alphastack.yield();
  return aggregateSignals(results);
}
```

**Depth hierarchy for trading:**
| Depth | Role | Example |
|-------|------|---------|
| 0 | Main Portfolio Agent | Orchestrates overall strategy |
| 1 | Strategy Orchestrator | Swarm A coordinator, Swarm B coordinator |
| 2 | Leaf Workers | Individual ticker analysts, execution agents |

---

## Pattern 2: Push-Based Completion (Announce Chain)

### What It Is
Sub-agents don't return values synchronously. Instead, they push results back to the parent when done. The parent yields and receives completions as the next message.

### How It Works in OpenClaw
1. `sessions_spawn` returns immediately (non-blocking)
2. Child runs to completion
3. OpenClaw runs an "announce step" inside the child session
4. Announce is delivered to the parent via internal event injection
5. Parent sees the result as a structured message with status, runtime stats, and result text
6. For nested agents: depth-2 → depth-1 → depth-0 (cascading announces)

**Announce context includes:**
- Source (subagent/cron)
- Session IDs
- Status (success/error/timeout/unknown)
- Result content (latest visible assistant text)
- Runtime stats (tokens, cost, duration)

### How to Adapt for AlphaStack

```typescript
// AlphaStack: Push-based signal delivery
interface SignalAnnounce {
  source: "sentiment_agent" | "technical_agent" | "flow_agent";
  sessionKey: string;
  status: "success" | "error" | "timeout";
  signal: {
    ticker: string;
    direction: "long" | "short" | "neutral";
    confidence: number;  // 0-1
    timeframe: string;
    reasoning: string;
  };
  stats: {
    runtimeMs: number;
    tokensUsed: number;
    dataSourcesQueried: string[];
  };
}

// Parent aggregator receives pushes, not polls
async function handleSignalCompletion(announce: SignalAnnounce) {
  if (announce.status === "success") {
    await signalBuffer.add(announce.signal);
    // Check if all parallel analysts have reported
    if (signalBuffer.isComplete(morningScanId)) {
      const aggregated = aggregateSignals(signalBuffer.get(morningScanId));
      await riskGate.evaluate(aggregated);
    }
  }
}
```

**Critical trading insight:** Push-based completion means the orchestrator never wastes tokens polling. In trading, where latency matters, this is essential — the parent can process other work while waiting for slow fundamental analysis to complete.

---

## Pattern 3: Task Flow Orchestration (Durable Multi-Step Pipelines)

### What It Is
A durable orchestration layer above background tasks that manages multi-step flows with state, revision tracking, and resume semantics. Survives gateway restarts.

### How It Works in OpenClaw
- **Managed mode:** Task Flow owns the lifecycle — creates tasks as steps, waits for completion, advances state
- **Mirrored mode:** Observes externally created tasks, keeps flow state in sync
- Each flow has: `flowId`, `currentStep`, `stateJson`, `waitJson`, revision tracking
- State persists in SQLite with WAL for crash recovery
- Cancel intent is sticky — survives restarts

**Lifecycle:**
```
createManaged → runTask → setWaiting → resume → finish/fail
```

### How to Adapt for AlphaStack

```typescript
// AlphaStack: Trade execution flow with durable state
const tradeFlow = alphastack.taskFlow.createManaged({
  controllerId: "alphastack/trade-execution",
  goal: "Execute AAPL bull call spread",
  currentStep: "pre_trade_analysis",
  stateJson: {
    ticker: "AAPL",
    strategy: "bull_call_spread",
    legs: [],
    riskCheck: null,
    executionStatus: null,
  },
});

// Step 1: Pre-trade analysis
const analysis = taskFlow.runTask({
  flowId: tradeFlow.flowId,
  task: "Run pre-trade analysis: liquidity, spread width, IV rank",
  childSessionKey: "agent:analysis:subagent:pretrade",
});

// Step 2: Risk gate (wait for human approval if needed)
const riskGate = taskFlow.setWaiting({
  flowId: tradeFlow.flowId,
  currentStep: "risk_approval",
  waitJson: {
    kind: "approval",
    riskScore: analysis.riskScore,
    maxLoss: analysis.maxLoss,
    // Auto-approve if risk score < threshold
    autoApprove: analysis.riskScore < 0.3,
  },
});

// Step 3: Execute (after approval)
if (riskGate.waitJson.autoApprove || riskGate.approved) {
  taskFlow.resume({ flowId: tradeFlow.flowId, currentStep: "execute" });
  const execution = taskFlow.runTask({
    flowId: tradeFlow.flowId,
    task: `Execute ${tradeFlow.stateJson.strategy} on ${tradeFlow.stateJson.ticker}`,
  });
  taskFlow.finish({ flowId: tradeFlow.flowId });
}
```

**Trading use cases:**
- Multi-leg order execution with intermediate checks
- Signal → Analysis → Risk → Execution → Monitoring pipeline
- Rebalancing workflows that survive market interruptions

---

## Pattern 4: Multi-Agent Routing (Isolated Agents with Bindings)

### What It Is
Multiple fully isolated agents (each with own workspace, state, sessions, auth) in one gateway process. Inbound messages are routed via deterministic bindings.

### How It Works in OpenClaw
- Each `agentId` has: own workspace, `agentDir`, session store, auth profiles
- Bindings route by: channel → accountId → peer → guildId → default
- Most-specific binding wins
- Cross-agent messaging is opt-in (`tools.agentToAgent`)
- Per-agent sandbox and tool restrictions

```json5
{
  agents: {
    list: [
      { id: "signals", workspace: "~/.openclaw/workspace-signals", model: "fast-model" },
      { id: "execution", workspace: "~/.openclaw/workspace-execution", model: "precise-model" },
      { id: "risk", workspace: "~/.openclaw/workspace-risk", model: "analytical-model" },
    ],
  },
  bindings: [
    { agentId: "signals", match: { channel: "data-feed", accountId: "market-data" } },
    { agentId: "execution", match: { channel: "broker-api", accountId: "interactive-brokers" } },
    { agentId: "risk", match: { channel: "internal", accountId: "risk-monitor" } },
  ],
}
```

### How to Adapt for AlphaStack

```typescript
// AlphaStack: Trading agent topology
interface TradingAgentConfig {
  agents: {
    list: [
      {
        id: "swarm-a-coordinator",
        workspace: "./workspace-swarm-a",
        model: "alphastack/deep-analysis",
        subagents: { maxSpawnDepth: 2, maxChildrenPerAgent: 10 },
        tools: { allow: ["market_data", "sentiment", "technical", "sessions_spawn"] },
      },
      {
        id: "swarm-b-coordinator",
        workspace: "./workspace-swarm-b",
        model: "alphastack/execution-precise",
        subagents: { maxSpawnDepth: 1 },
        tools: { allow: ["broker_api", "order_management", "position_tracker"] },
      },
      {
        id: "risk-manager",
        workspace: "./workspace-risk",
        model: "alphastack/analytical",
        tools: { allow: ["portfolio_analysis", "var_calc", "correlation"] },
        // Risk agent has NO execution tools — defense in depth
        sandbox: { mode: "all" },
      },
    ],
  };
}
```

**Key insight:** Each swarm gets its own workspace with specialized `AGENTS.md` instructions, memory, and skills. The risk agent is sandboxed with no execution tools — defense in depth.

---

## Pattern 5: Workspace Bootstrap Files (Structured Agent Memory)

### What It Is
A structured workspace with injectable files that define agent behavior, persona, tools, and memory. Files are auto-injected into the system prompt every session.

### How It Works in OpenClaw
Standard files injected every session:
- `AGENTS.md` — operating instructions, memory protocol, red lines
- `SOUL.md` — persona, tone, boundaries
- `TOOLS.md` — local tool notes (camera names, SSH hosts, voice prefs)
- `IDENTITY.md` — name, vibe, emoji
- `USER.md` — who the user is
- `MEMORY.md` — curated long-term memory (main session only)
- `memory/YYYY-MM-DD.md` — daily memory logs
- `HEARTBEAT.md` — periodic check checklist

Large files are truncated per-file (default 12,000 chars) with total cap (60,000 chars).

### How to Adapt for AlphaStack

```
alphastack-workspace/
├── AGENTS.md              # Trading rules, risk limits, execution protocols
├── SOUL.md                # Trading personality (aggressive/conservative/scalper)
├── TOOLS.md               # API endpoints, broker configs, data source notes
├── IDENTITY.md            # Agent name and role
├── STRATEGY.md            # Current active strategies and parameters
├── RISK_LIMITS.md         # Max position size, daily loss limit, correlation limits
├── memory/
│   ├── 2026-07-16.md      # Today's trades, signals, observations
│   ├── 2026-07-15.md      # Yesterday's summary
│   └── ...
├── MEMORY.md              # Curated: lessons learned, strategy adjustments, market regime notes
├── strategies/
│   ├── mean-reversion.md  # Strategy-specific instructions
│   ├── momentum.md
│   └── options-flow.md
└── skills/
    ├── technical-analysis/
    │   └── SKILL.md
    ├── sentiment-analysis/
    │   └── SKILL.md
    └── order-execution/
        └── SKILL.md
```

**Example `AGENTS.md` for a trading agent:**
```markdown
# Trading Agent Instructions

## Risk Rules (NEVER VIOLATE)
- Max single position: 5% of portfolio
- Max daily loss: 2% of portfolio
- Max correlation between positions: 0.7
- No trading in first/last 15 minutes of market open/close (unless pre-approved)
- Always check liquidity before entering

## Execution Protocol
1. Signal received → Validate with 2+ independent sources
2. Run pre-trade analysis (liquidity, spread, IV)
3. Risk gate check → Auto-approve if risk score < 0.3, else escalate
4. Execute with limit orders, never market orders for > 100 shares
5. Post-trade: log to memory, update portfolio state

## Memory Protocol
- Log every trade decision with reasoning
- Daily summary of P&L and lessons
- Weekly: review and update MEMORY.md with strategy adjustments
```

---

## Pattern 6: Skills System (Discoverable, Composable Capabilities)

### What It Is
A hierarchical skill loading system where each skill is a directory with a `SKILL.md` (YAML frontmatter + instructions). Skills are discovered, gated, and injected on demand.

### How It Works in OpenClaw
- Skills loaded from 6 precedence levels (workspace > project > personal > managed > bundled > extra)
- System prompt includes compact skill list (name + description + location)
- Model reads `SKILL.md` only when needed (lazy loading saves context)
- Skills can be gated per-agent via allowlists
- Skills can require specific binaries, configs, or environments

**Skill structure:**
```
skills/
└── technical-analysis/
    ├── SKILL.md           # YAML frontmatter + instructions
    ├── indicators.md      # Reference: RSI, MACD, Bollinger
    ├── patterns.md        # Reference: chart patterns
    └── scripts/
        └── scan.py        # Executable analysis script
```

**SKILL.md frontmatter:**
```yaml
---
name: technical-analysis
slug: technical-analysis
version: 1.0.0
description: "Analyze price action, indicators, and chart patterns for trading signals."
metadata:
  openclaw:
    requires:
      bins: ["python3", "ta-lib"]
      config: ["ALPHA_VANTAGE_API_KEY"]
---
```

### How to Adapt for AlphaStack

```typescript
// AlphaStack: Skill-based capability discovery
interface TradingSkill {
  name: string;
  slug: string;
  description: string;
  requires: {
    bins?: string[];           // ["python3", "node"]
    apis?: string[];           // ["polygon.io", "tradier"]
    dataFeeds?: string[];      // ["options_flow", "dark_pool"]
    permissions?: string[];    // ["read_positions", "submit_orders"]
  };
  // Skill is only loaded if all requirements are met
}

// Skills discovered at startup, injected into agent prompt as compact list
// Agent reads SKILL.md only when it needs that capability
const tradingSkills: TradingSkill[] = [
  { name: "options-flow-analysis", description: "Analyze unusual options activity..." },
  { name: "sentiment-scoring", description: "Score market sentiment from social/news..." },
  { name: "mean-reversion", description: "Identify mean reversion setups..." },
  { name: "order-execution", description: "Execute orders via broker API..." },
  { name: "portfolio-optimization", description: "Optimize portfolio allocation..." },
];
```

**Key insight:** Skills are lazy-loaded. The agent sees "options-flow-analysis exists" in its prompt but only reads the full instructions when it actually needs to analyze options flow. This saves context window space for market data.

---

## Pattern 7: Active Memory (Blocking Memory Sub-Agent)

### What It Is
A plugin-owned blocking sub-agent that runs **before** the main reply to surface relevant memory. It searches long-term memory and injects a hidden context prefix into the prompt.

### How It Works in OpenClaw
```
User Message → Build Memory Query → Active Memory Sub-Agent → (NONE | relevant summary) → Main Reply
```

- Runs as a blocking sub-agent with its own timeout (default 15s)
- Three query modes: `message` (fastest), `recent` (balanced), `full` (best recall)
- Returns `NONE` if nothing relevant found
- Summary is injected as hidden `<active_memory_plugin>` system context
- Has its own circuit breaker (skips after repeated timeouts)

### How to Adapt for AlphaStack

```typescript
// AlphaStack: Market context memory injection
async function injectMarketMemory(currentQuery: MarketQuery): Promise<MarketMemory> {
  // Search historical context before generating signals
  const memory = await alphastack.memorySearch({
    query: buildMemoryQuery(currentQuery),
    // "What happened last time AAPL had similar IV crush pattern?"
    // "How did the portfolio perform during similar rate hike environments?"
    mode: "recent",  // balanced speed/quality
    timeoutMs: 5000, // tighter timeout for trading
    promptStyle: "precision-heavy", // only inject clearly relevant context
  });

  if (memory.status === "none") return null;

  // Inject as hidden context for the main analysis agent
  return {
    hiddenContext: `
      <market_memory>
        Historical context (do not treat as current data):
        ${memory.summary}
        Retrieved at: ${memory.timestamp}
        Confidence: ${memory.relevanceScore}
      </market_memory>
    `,
  };
}
```

**Trading-specific memory queries:**
- "Last time TSLA dropped 5% in a day, what was the recovery pattern?"
- "How did the portfolio perform during the last 3 FOMC meetings?"
- "What strategies worked best in high-VIX environments?"

---

## Pattern 8: Session Management (Isolation and Lifecycle)

### What It Is
Sessions organize conversations with automatic routing, isolation, lifecycle management (daily/idle resets), and maintenance (pruning, compaction).

### How It Works in OpenClaw
- Sessions keyed as `agent:<agentId>:<sessionKey>`
- DM scope options: `main`, `per-peer`, `per-channel-peer`, `per-account-channel-peer`
- Daily reset at 4 AM, idle reset after inactivity
- Transcript stored as JSONL per session
- Compaction summarizes older history to free context window
- Session pruning with configurable retention

### How to Adapt for AlphaStack

```typescript
// AlphaStack: Trading session isolation
interface TradingSessionConfig {
  // Each strategy gets its own session (isolated context)
  sessionScopes: {
    "momentum-strategy": "isolated";     // Clean context, no cross-contamination
    "mean-reversion-strategy": "isolated";
    "portfolio-overview": "persistent";  // Long-running, benefits from history
  };

  // Trade-specific sessions
  tradeSessions: {
    // Fresh session per trade execution (audit trail)
    scope: "per-trade-id";
    // Keep transcript for compliance
    retention: "730d"; // 2 years
    // Compact after 1 hour to save storage
    compaction: { trigger: "idle-60m" };
  };

  // Market regime sessions
  regimeSessions: {
    // Reset when market regime changes (not time-based)
    scope: "per-regime";
    reset: "on-regime-change"; // Custom trigger
  };
}
```

**Key insight for trading:** Use `per-trade-id` sessions for execution audit trails. Each trade gets its own isolated session with full transcript — perfect for compliance and post-trade analysis.

---

## Pattern 9: Standing Orders (Autonomous Operating Authority)

### What It Is
Permanent operating authority defined in workspace files. Instead of per-task prompting, define programs with scope, triggers, approval gates, and escalation rules. Agent executes autonomously within boundaries.

### How It Works in OpenClaw
- Defined in `AGENTS.md` (auto-injected every session)
- Each program specifies: scope, triggers, approval gates, escalation rules
- Combined with cron jobs for time-based enforcement
- Follows Execute-Verify-Report pattern

### How to Adapt for AlphaStack

```markdown
## Program: Morning Market Scan

**Authority:** Scan pre-market data, identify setups, generate watchlist
**Trigger:** Every trading day at 8:00 AM ET (cron enforced)
**Approval gate:** None for watchlist generation. Alert owner for high-conviction setups.
**Escalation:** If data feeds are stale (>5 min), if VIX > 30, if overnight gaps > 3%

### Execution steps
1. Pull overnight futures, pre-market movers, economic calendar
2. Run technical scan on watchlist tickers
3. Check options flow for unusual activity
4. Generate prioritized watchlist with entry/exit levels
5. If high-conviction setup found → alert owner immediately
6. Log results to memory/YYYY-MM-DD.md

### What NOT to do
- Do not enter positions without explicit approval
- Do not scan tickers not on the approved list
- Do not trade during first 15 minutes of market open
- Never override risk limits

## Program: Continuous Risk Monitoring

**Authority:** Monitor portfolio risk metrics, alert on threshold breaches
**Trigger:** Every 5 minutes during market hours
**Approval gate:** Auto-hedge if VaR breach. Escalate if hedge fails.
**Escalation:** If any position exceeds 5% of portfolio, if daily P&L < -1.5%

### Response matrix
| Condition | Action | Escalate? |
|-----------|--------|-----------|
| VaR breach | Auto-hedge with puts | Only if hedge fails |
| Position > 5% | Reduce to 3% | Yes, with explanation |
| Daily P&L < -1.5% | Close all new positions | Yes, immediately |
| Correlation > 0.7 | Flag pair, reduce exposure | Report in daily summary |
```

---

## Pattern 10: Context Engine (Pluggable Context Assembly)

### What It Is
A pluggable system that controls how the model's context is built each run: which messages to include, how to summarize older history, and how to manage context across sub-agent boundaries.

### How It Works in OpenClaw
Four lifecycle hooks:
1. **Ingest** — store/index new messages
2. **Assemble** — build context within token budget
3. **Compact** — summarize when window is full
4. **After turn** — persist state, trigger background work

Plugin engines can implement custom assembly, compaction, and cross-session recall.

### How to Adapt for AlphaStack

```typescript
// AlphaStack: Trading-optimized context engine
class TradingContextEngine implements ContextEngine {
  async assemble({ sessionId, messages, tokenBudget }) {
    // Prioritize recent market data over older messages
    const prioritized = this.prioritizeByRelevance(messages, {
      // Weight factors for trading context
      recency: 0.3,           // Recent data matters more
      signalStrength: 0.3,    // Strong signals get priority
      assetRelevance: 0.2,    // Current ticker context
      outcomeCorrelation: 0.2, // Similar past setups
    });

    // Always include: current positions, risk limits, active orders
    const mandatory = await this.getMandatoryContext(sessionId);

    // Fit within budget
    return {
      messages: this.fitToBudget([...mandatory, ...prioritized], tokenBudget),
      estimatedTokens: this.countTokens([...mandatory, ...prioritized]),
      systemPromptAddition: this.buildMarketContext(sessionId),
    };
  }

  async compact({ sessionId }) {
    // Don't compact active trade context — only historical
    const activeTrades = await this.getActiveTrades(sessionId);
    const historical = await this.getHistoricalMessages(sessionId);

    // Summarize historical, keep active trade context intact
    const summary = await this.summarizeHistorical(historical);
    return { compacted: true, summary };
  }
}
```

**Key insight:** Trading context has different priority rules than chat. Current positions, risk limits, and active orders must always be in context. Historical analysis can be summarized. Market data freshness matters more than conversation recency.

---

## Architecture Summary: AlphaStack Agent Topology

Based on OpenClaw patterns, here's the recommended AlphaStack architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                    Main Portfolio Agent (Depth 0)            │
│  - Orchestrates overall strategy                            │
│  - Manages risk gates and human escalation                  │
│  - Workspace: portfolio-level AGENTS.md, MEMORY.md          │
├──────────────┬──────────────────┬───────────────────────────┤
│   Swarm A    │     Swarm B      │     Risk Manager          │
│  (Signals)   │   (Execution)    │     (Independent)         │
│  Depth 1     │     Depth 1      │     Depth 1               │
│  Orchestrator│     Orchestrator  │     Sandboxed             │
├──────┬───────┼──────┬───────────┼───────────────────────────┤
│Sent. │Tech.  │Order │Position   │  VaR Monitor              │
│Agent │Agent  │Exec  │Manager    │  Correlation Checker      │
│Depth2│Depth2 │Depth2│Depth2     │  Drawdown Tracker         │
└──────┴───────┴──────┴───────────┴───────────────────────────┘
```

### Communication Patterns
- **Swarm A → Main:** Push-based signal announces
- **Main → Swarm B:** Task Flow for execution pipelines
- **Risk → Main:** Real-time alerts via `sessions_send`
- **All agents:** Shared market context via workspace files + active memory

### State Management
- **Per-strategy sessions:** Isolated context, no cross-contamination
- **Per-trade sessions:** Full audit trail, compliance-ready
- **Daily memory logs:** `memory/YYYY-MM-DD.md` for all trading activity
- **Long-term memory:** `MEMORY.md` for strategy lessons, regime observations

### Safety Patterns
- Risk agent is sandboxed with no execution tools
- Standing orders define hard limits (never violated)
- Approval gates for high-risk operations
- Execute-Verify-Report for all trades

---

## Implementation Priority

| Priority | Pattern | Effort | Impact |
|----------|---------|--------|--------|
| P0 | Sub-Agent Spawning | Medium | Core — enables parallel analysis |
| P0 | Push-Based Completion | Low | Core — efficient coordination |
| P0 | Workspace Bootstrap | Low | Core — structured agent behavior |
| P1 | Multi-Agent Routing | Medium | High — swarm isolation |
| P1 | Session Management | Medium | High — audit trails, context isolation |
| P1 | Standing Orders | Low | High — autonomous operation |
| P2 | Task Flow | High | Medium — complex trade pipelines |
| P2 | Active Memory | Medium | Medium — historical context |
| P2 | Skills System | Medium | Medium — composable capabilities |
| P3 | Context Engine | High | Medium — optimized token usage |

---

## References

- OpenClaw Docs: `/usr/lib/node_modules/openclaw/docs/`
- Key files analyzed:
  - `concepts/agent.md` — Agent runtime and workspace contract
  - `concepts/agent-loop.md` — Full agent execution lifecycle
  - `tools/subagents.md` — Sub-agent spawning and orchestration
  - `concepts/session-tool.md` — Cross-session tools
  - `concepts/multi-agent.md` — Multi-agent routing
  - `automation/taskflow.md` — Durable flow orchestration
  - `automation/tasks.md` — Background task tracking
  - `automation/standing-orders.md` — Autonomous operating authority
  - `concepts/active-memory.md` — Memory sub-agent
  - `concepts/context-engine.md` — Pluggable context assembly
  - `concepts/session.md` — Session management
  - `concepts/agent-workspace.md` — Workspace structure
  - `tools/skills.md` — Skills system
  - `skills/taskflow/SKILL.md` — TaskFlow implementation patterns
