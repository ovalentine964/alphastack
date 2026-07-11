# Research Report: Loop Systems & Multi-Agent Architectures for AI Trading

**Date:** 2026-07-11
**Focus:** Loop patterns, multi-agent frameworks, and agentic trading architecture design

---

## Table of Contents

1. [Loop Systems for Trading](#1-loop-systems-for-trading)
2. [Multi-Agent Frameworks Comparison](#2-multi-agent-frameworks-comparison)
3. [Agentic Trading Architecture Design](#3-agentic-trading-architecture-design)
4. [Real-World Examples & Open Source Projects](#4-real-world-examples--open-source-projects)
5. [Recommended Architecture for Our System](#5-recommended-architecture-for-our-system)

---

## 1. Loop Systems for Trading

### 1.1 ReAct (Reasoning + Acting) Loop

**Core Concept:** Interleaves reasoning traces with tool-use actions in a cycle: `Thought → Action → Observation → Thought → ...`

**How it applies to trading:**
- Agent reasons about market conditions ("BTC is testing the 200-day MA with declining volume...")
- Takes an action (queries price API, reads news, calculates RSI)
- Observes the result
- Reasons again with new information
- Repeats until a trade decision threshold is reached

**Trading-specific ReAct loop:**
```
Thought: "SPY is showing a bearish divergence on RSI. Let me check volume profile."
Action: fetch_volume_profile("SPY", period="5d")
Observation: "Volume concentrated at 452-455, price at 458. Low volume node above."
Thought: "Price is above a low-volume node with bearish divergence. Probability of rejection is high."
Action: check_market_regime()
Observation: "VIX at 18.5, trending up. Risk-off environment."
Thought: "Multiple bearish signals align. Initiating short position with tight stop."
Action: execute_trade("SPY", "SHORT", size=0.5, stop=462, target=450)
```

**Why it works for trading:**
- Forces the model to "show its work" — every trade has an auditable reasoning chain
- Prevents impulsive single-step decisions
- Allows dynamic information gathering (the agent decides what data to fetch next)
- Natural fit for the iterative nature of market analysis

**Limitations:**
- Can be slow for time-sensitive scalping (each loop adds latency)
- May over-reason and miss fast-moving opportunities
- Token cost scales with loop iterations

---

### 1.2 Reflection Loop

**Core Concept:** Agent generates an output, then critiques and revises it in a self-correction cycle.

**Trading application — Strategy Self-Correction:**
```
Phase 1: INITIAL ANALYSIS
  "Based on technicals, I recommend going long ETH at $3,200."

Phase 2: SELF-CRITIQUE
  "Wait — I didn't consider the upcoming FOMC meeting in 2 days.
   Historical data shows ETH drops 3-5% on average before rate decisions.
   My stop-loss at $3,100 might get triggered by event-driven volatility."

Phase 3: REVISED ANALYSIS
  "Revised recommendation: Wait until post-FOMC. If rate holds and
   ETH maintains above $3,150 post-announcement, enter long with
   wider stop at $3,050. Reduced position size to account for event risk."
```

**Key patterns:**
- **Pre-trade reflection:** Before executing, the agent reviews its own analysis for blind spots
- **Post-trade reflection:** After a trade closes, analyze what went right/wrong
- **Periodic strategy reflection:** Weekly review of all trades to update strategy parameters

**Implementation approach:**
```python
def reflection_loop(trade_thesis, max_reflections=3):
    for i in range(max_reflections):
        critique = llm.generate(f"Critically evaluate this trade thesis: {trade_thesis}")
        if "no_issues_found" in critique.lower():
            return trade_thesis
        trade_thesis = llm.generate(f"Revise this trade thesis based on critique:\n"
                                     f"Thesis: {trade_thesis}\nCritique: {critique}")
    return trade_thesis
```

---

### 1.3 Deliberation Loop

**Core Concept:** Multi-step reasoning where the agent explicitly weighs multiple options before committing.

**Trading application — Trade Deliberation:**
```
Step 1: GENERATE OPTIONS
  Option A: Go long BTC at current price ($67,500)
  Option B: Set limit buy at $66,000 (support level)
  Option C: Buy a call option (defined risk)
  Option D: Do nothing, wait for clearer signal

Step 2: EVALUATE EACH OPTION
  Option A: R/R ratio 1:2, but entering at resistance. Score: 6/10
  Option B: Better entry, but may not fill. Score: 7/10
  Option C: Defined risk, but theta decay in low-vol environment. Score: 5/10
  Option D: No risk, but may miss move. Score: 7/10

Step 3: SELECT AND JUSTIFY
  "Selecting Option B (limit buy at $66,000) with Option D as fallback.
   If price doesn't reach $66,000 within 48 hours, reassess."
```

**When to use:** High-conviction trades, large position sizes, unfamiliar market conditions.

---

### 1.4 Plan-and-Execute Loop

**Core Concept:** Separates strategic planning (high-level) from tactical execution (step-by-step).

**Trading application:**
```
PLANNER AGENT:
  "Market is in a range-bound regime. Strategy:
   1. Identify range boundaries (support/resistance)
   2. Fade extremes with mean-reversion entries
   3. Use tight stops at range boundaries
   4. Take profit at opposite end of range
   5. Reassess if range breaks"

EXECUTOR AGENT (runs per-tick):
  "Current price: SPY $455.50. Upper range: $458. Lower range: $452.
   Distance to upper: 0.55%. Distance to lower: 0.77%.
   RSI(14): 72 (overbought near upper range).
   EXECUTING: Short entry at $455.50, stop $458.50, target $452.50."
```

**Why it works:**
- Planner thinks slowly and strategically (low frequency, high quality)
- Executor acts quickly and tactically (high frequency, plan-guided)
- Clear separation of concerns
- Plan can be updated periodically without changing execution logic

**2026 evolution:** LangGraph's `Plan-and-Execute` pattern and CrewAI's `Flow` system both natively support this pattern with state management between planner and executor nodes.

---

### 1.5 Human-in-the-Loop (HITL)

**Core Concept:** Strategic checkpoints where the system escalates to a human for approval or override.

**When to alert vs auto-execute:**

| Scenario | Action |
|---|---|
| Standard trade within risk parameters | Auto-execute |
| Trade exceeds 2% portfolio risk | Alert + require approval |
| New market regime detected | Alert + pause trading |
| Loss streak > 5 trades | Alert + halt strategy |
| Black swan event detected | Alert + flatten all positions |
| Strategy parameter change | Require approval |
| New asset class / unfamiliar territory | Require approval |

**HITL implementation pattern:**
```python
class HITLCheckpoint:
    def __init__(self, risk_threshold, auto_approve_below):
        self.risk_threshold = risk_threshold
        self.auto_approve_below = auto_approve_below

    def evaluate(self, trade_proposal):
        if trade_proposal.risk_pct < self.auto_approve_below:
            return "AUTO_APPROVE"
        elif trade_proposal.risk_pct < self.risk_threshold:
            return "ALERT_AND_WAIT"  # Send notification, wait for human
        else:
            return "REJECT"  # Too risky, reject automatically
```

**2026 best practices (from Anthropic's guidance):**
- Start with HITL for all trades, gradually increase autonomy as trust builds
- Use "approval tiers": small trades auto-approve, large trades require confirmation
- Implement "dead man's switch": if human doesn't respond within X minutes, take conservative action
- Log all HITL decisions for training data

---

### 1.6 Emerging Loop Patterns (2026)

**a) Orchestrator-Workers Loop (Anthropic pattern)**
- Central orchestrator agent dynamically delegates to specialized worker agents
- Unlike fixed pipelines, the orchestrator decides which workers to invoke based on market conditions
- Example: Orchestrator sees high volatility → invokes volatility specialist agent instead of trend-following agent

**b) Evaluator-Optimizer Loop**
- One agent generates trade signals, another evaluates them against historical performance
- Signals that score below threshold get sent back for revision
- Creates a natural quality filter before execution

**c) Swarm Loops (OpenAI Swarm pattern)**
- Agents hand off to each other based on context
- "BTC analysis agent" hands off to "risk management agent" hands off to "execution agent"
- Each agent handles its domain then transfers control

**d) Magentic-One Loop (Microsoft AutoGen)**
- Orchestrator dynamically plans, delegates, and tracks progress across specialized agents
- Built-in error recovery and replanning
- Well-suited for complex multi-step trading workflows

---

## 2. Multi-Agent Frameworks Comparison

### 2.1 Framework Overview (as of mid-2026)

| Feature | **LangGraph** | **CrewAI** | **AutoGen** | **OpenAI Swarm** |
|---|---|---|---|---|
| **Type** | Low-level orchestration | High-level crew framework | Multi-agent conversation | Lightweight handoff |
| **Control Flow** | Graph-based (nodes + edges) | Role-based crews + flows | Conversation patterns | Function-based handoffs |
| **State Management** | Built-in persistent state | Flow state with decorators | Session state | Minimal (context vars) |
| **Human-in-the-Loop** | Native interrupts | Via callbacks | Built-in tutorial | Manual implementation |
| **Memory** | Built-in store | Agent memory + crew memory | Memory + RAG module | Manual |
| **Streaming** | First-class support | Basic | Supported | Manual |
| **Best For** | Complex workflows needing fine control | Role-based team simulations | Research & conversation-heavy tasks | Simple agent handoffs |
| **Learning Curve** | Medium-High | Low-Medium | Medium | Low |
| **Production Ready** | Yes (used by many companies) | Yes (v1.15+) | Yes (v0.4+) | Prototype/concept |

### 2.2 Deep Dive: LangGraph

**Why it's the strongest fit for trading systems:**

1. **Graph-based control flow** — Perfect for defining trading pipelines as directed graphs
   - Nodes = processing steps (fetch data, analyze, decide, execute)
   - Edges = conditional routing (if high volatility → go to risk node, else → go to signal node)
   - Cycles = natural for ReAct/reflection loops

2. **Persistent state** — Critical for trading
   - Position state, P&L tracking, trade history all persist across steps
   - Built-in checkpointing allows recovery from failures

3. **Human-in-the-loop interrupts** — Native support for pausing and waiting for human approval

4. **Multi-agent support** — Can define multiple agents as nodes in the same graph

**Example trading graph in LangGraph:**
```
[MarketData] → [TechnicalAnalysis] → [FundamentalAnalysis] → [SignalAggregation]
                                                                    ↓
[HITLCheckpoint] ← [RiskAssessment] ← [PositionSizer]
       ↓
  [OrderExecution] → [TradeLogger] → [PostTradeAnalysis]
```

### 2.3 Deep Dive: CrewAI

**Strengths for trading:**
- **Role-based design** naturally maps to trading desk roles
- **CrewAI Flows** (v1.15+) provide event-driven workflow control
- Built-in delegation, memory, and tool assignment per agent
- Lower boilerplate than LangGraph

**Example trading crew:**
```python
researcher = Agent(role="Market Researcher", goal="Find alpha-generating signals",
                   tools=[news_api, sec_filings, social_sentiment])
analyst = Agent(role="Technical Analyst", goal="Identify entry/exit points",
                tools=[charting_api, indicator_calculator])
risk_manager = Agent(role="Risk Manager", goal="Ensure portfolio stays within risk limits",
                     tools=[var_calculator, correlation_analyzer])
executor = Agent(role="Trade Executor", goal="Execute trades at best prices",
                 tools=[broker_api, order_router])

crew = Crew(agents=[researcher, analyst, risk_manager, executor],
            process=Process.sequential)  # or Process.hierarchical
```

### 2.4 Deep Dive: AutoGen (Microsoft)

**Strengths for trading:**
- **Magentic-One** — Advanced orchestrator pattern for complex multi-step tasks
- **GraphFlow** — Directed graph workflows similar to LangGraph
- **Selector Group Chat** — Agents discuss and reach consensus (good for trade committee decisions)
- Strong research backing and enterprise adoption

**Trading-relevant patterns:**
- **Selector Group Chat** for trade committee: Multiple analyst agents debate a trade, a selector agent picks the best argument
- **Swarm** for execution handoffs: Market analyst → Risk checker → Order executor
- **GraphFlow** for deterministic pipelines

### 2.5 Deep Dive: OpenAI Swarm

**Minimal framework for agent handoffs:**
- Not a production framework — more of a pattern/concept
- Agents are simple functions that can hand off to other agents
- Good for prototyping, not recommended for production trading
- Useful as inspiration for lightweight handoff patterns

---

## 3. Agentic Trading Architecture Design

### 3.1 Recommended Multi-Agent Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR AGENT                         │
│  (Plan-and-Execute loop, routes to specialist agents)        │
└────────────┬────────────┬────────────┬────────────┬─────────┘
             │            │            │            │
     ┌───────▼──┐  ┌──────▼───┐  ┌────▼─────┐  ┌──▼────────┐
     │ RESEARCH │  │ ANALYSIS │  │   RISK   │  │ EXECUTION │
     │  AGENTS  │  │  AGENTS  │  │  AGENT   │  │   AGENT   │
     └──────────┘  └──────────┘  └──────────┘  └───────────┘
     │ News       │ Technical    │ VaR calc    │ Order routing
     │ Sentiment  │ Fundamental  │ Correlation │ Smart routing
     │ On-chain   │ Macro        │ Position    │ Slippage mgmt
     │ Alt data   │ Quant models │ sizing      │ Execution algo
```

### 3.2 Agent Roles Defined

#### Research Agent(s)
- **Purpose:** Gather and synthesize market information
- **Tools:** News APIs, social media scrapers, SEC filing parsers, on-chain analytics
- **Loop pattern:** ReAct — iteratively search, read, synthesize until sufficient info gathered
- **Output:** Structured research brief with sentiment score, key events, catalysts

#### Analysis Agent(s)
- **Purpose:** Transform raw data into tradeable signals
- **Sub-agents:**
  - Technical Analyst: Chart patterns, indicators, price action
  - Fundamental Analyst: Earnings, valuation, sector analysis
  - Macro Analyst: Interest rates, GDP, geopolitical risk
- **Loop pattern:** Deliberation — weigh multiple analytical frameworks before signal generation
- **Output:** Trade signals with confidence scores and reasoning

#### Risk Management Agent
- **Purpose:** Gate-keep all trades through risk checks
- **Checks:** Position sizing, portfolio correlation, max drawdown, exposure limits, volatility regime
- **Loop pattern:** Evaluation — accepts, modifies, or rejects trade proposals
- **Output:** Approved/modified trade with risk parameters

#### Execution Agent
- **Purpose:** Execute approved trades optimally
- **Tools:** Broker APIs, smart order routers, execution algorithms (TWAP, VWAP)
- **Loop pattern:** Plan-and-Execute — plan execution strategy, then execute step by step
- **Output:** Filled orders with execution quality metrics

#### Monitor Agent
- **Purpose:** Continuously watch positions, market conditions, and system health
- **Loop pattern:** Event-driven — triggers alerts on threshold breaches
- **Actions:** Alert human, adjust stops, flatten positions in emergencies

#### Reflection Agent
- **Purpose:** Periodic review of all trading activity
- **Loop pattern:** Reflection — reviews past trades, identifies patterns in wins/losses
- **Output:** Strategy adjustments, lessons learned, parameter tuning recommendations

### 3.3 Signal Flow Architecture

```
Phase 1: DATA INGESTION (Continuous)
  Market Data Feeds ──┐
  News/Social ────────┤──→ [Data Lake / Event Stream]
  On-chain Data ──────┤
  Alt Data ───────────┘

Phase 2: ANALYSIS (Event-driven, on new data)
  [Data Lake] ──→ Research Agent ──→ Analysis Agent(s) ──→ [Signal Queue]

Phase 3: DECISION (Per-signal)
  [Signal Queue] ──→ Orchestrator ──→ Deliberation Loop ──→ Risk Agent ──→ [Trade Proposal]

Phase 4: EXECUTION (Per-trade-proposal)
  [Trade Proposal] ──→ HITL Check ──→ Execution Agent ──→ [Order Flow]

Phase 5: REVIEW (Periodic + Post-trade)
  [Trade Log] ──→ Reflection Agent ──→ [Strategy Updates]
  [Position State] ──→ Monitor Agent ──→ [Alerts / Adjustments]
```

### 3.4 Memory Systems for Trading Agents

| Memory Type | Purpose | Implementation | Retention |
|---|---|---|---|
| **Working Memory** | Current market state, active positions | In-process state dict | Session-scoped |
| **Short-term Memory** | Recent price action, intraday patterns | Rolling window (e.g., last 100 ticks) | Hours |
| **Episodic Memory** | Past trade records, what happened and why | Vector DB (trade thesis + outcome) | Permanent |
| **Semantic Memory** | Market rules, strategy parameters, learned patterns | Structured knowledge base | Permanent, periodically updated |
| **Procedural Memory** | How to execute specific strategies | Code + prompt templates | Version-controlled |

**Implementation with LangGraph:**
```python
from langgraph.store import InMemoryStore

# Trading-specific memory store
trade_memory = InMemoryStore()

# Store trade episode
trade_memory.put(("trades", "2026-07-11"), "trade_001", {
    "entry": 67500,
    "exit": 68200,
    "thesis": "Breakout above resistance with volume confirmation",
    "outcome": "WIN",
    "pnl": 700,
    "lessons": "Volume confirmation was key. Without it, would have been a false breakout."
})

# Retrieve similar past trades for reflection
similar_trades = trade_memory.search(("trades",), query="breakout resistance volume")
```

### 3.5 Communication Protocols Between Agents

**Option A: Shared State (LangGraph approach)**
- All agents read/write to a shared state object
- Simple, but can cause conflicts with concurrent writes
- Best for sequential pipelines

**Option B: Message Passing (AutoGen approach)**
- Agents send structured messages to each other
- More flexible, supports parallel execution
- Best for deliberation/debate patterns

**Option C: Event-Driven (CrewAI Flows approach)**
- Agents emit events, other agents listen and react
- Loose coupling, easy to add/remove agents
- Best for reactive systems

**Recommended for trading:** Hybrid approach
- Shared state for position/portfolio data (needs consistency)
- Message passing for agent-to-agent deliberation
- Event-driven for market data distribution

---

## 4. Real-World Examples & Open Source Projects

### 4.1 Industry Adoption

**Hedge Funds & Prop Firms (2025-2026 trends):**
- **Citadel, Two Sigma, DE Shaw** — Multi-agent systems for research aggregation, where different agents specialize in different data sources (fundamental, technical, alternative data) and a meta-agent synthesizes signals
- **Point72** — Known to use AI agents for idea generation, with human portfolio managers making final decisions (HITL pattern)
- **Renaissance Technologies** — While not publicly disclosed, their Medallion fund's approach aligns with multi-model ensemble + systematic execution patterns
- **Jump Trading, Jane Street** — AI-assisted execution optimization, using agents to dynamically select execution algorithms based on market microstructure

**Key industry patterns:**
- Most firms use AI as augmentation, not full automation (HITL remains dominant)
- Multi-agent architectures for research/synthesis are more common than for execution
- Reflection/review loops are standard for strategy improvement
- Risk management agents are always human-supervised

### 4.2 Open Source Multi-Agent Trading Projects

| Project | Description | Stars | Relevance |
|---|---|---|---|
| **[FinGPT](https://github.com/AI4Finance-Foundation/FinGPT)** | Open-source financial LLM | 14k+ | Foundation model for financial agents |
| **[FinRL](https://github.com/AI4Finance-Foundation/FinRL)** | Deep RL for quantitative finance | 10k+ | RL-based trading agents |
| **[AI4Finance](https://github.com/AI4Finance-Foundation)** | Suite of financial AI tools | Multiple repos | Comprehensive ecosystem |
| **[Qlib (Microsoft)](https://github.com/microsoft/qlim)** | Quant investment platform | 16k+ | Data + model infrastructure |
| **[OpenBB](https://github.com/OpenBB-finance/OpenBB)** | Open data platform for quants & AI agents | 35k+ | Data layer for agents |
| **[FinRL-Meta](https://github.com/AI4Finance-Foundation/FinRL-Meta)** | Market environments for financial RL | 2k+ | Training environments |
| **[LLM Trading Agent](https://github.com/topics/llm-trading)** | Various LLM-based trading experiments | Multiple | Experimental patterns |
| **[LangChain Financial Agents](https://github.com/langchain-ai)** | Templates for financial agents | Part of LangChain | Framework integration |

### 4.3 Notable Open Source Multi-Agent Trading Architectures

**a) AI4Finance Agent Framework**
- Multi-agent system with separate agents for data collection, feature engineering, model training, and execution
- Uses FinRL for RL-based strategy optimization
- Supports multiple asset classes

**b) OpenBB + LangChain Integration**
- OpenBB provides the data layer (MCP server for AI agents)
- LangGraph orchestrates analysis agents
- Pattern: Data Agent → Analysis Agent → Signal Agent → Execution Agent

**c) GPT-Trader / LLM-Trader Projects**
- Community projects using LLMs as trading agents
- Common pattern: News agent + Technical agent + Risk agent → Consensus → Trade
- Most use simple ReAct or chain-of-thought patterns

---

## 5. Recommended Architecture for Our System

### 5.1 Framework Choice: **LangGraph**

**Rationale:**
- Graph-based control flow maps perfectly to trading pipelines
- Native state management for positions, P&L, and trade history
- Built-in HITL interrupts for risk management
- Production-proven at scale
- Fine-grained control over agent behavior (critical for trading)
- Strong memory/persistence support

### 5.2 Architecture Blueprint

```
┌──────────────────────────────────────────────────────────────┐
│                      LANGGRAPH STATE GRAPH                    │
│                                                                │
│  ┌─────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐ │
│  │  Data    │───→│ Research │───→│ Analysis │───→│ Signal   │ │
│  │  Ingest  │    │  Agent   │    │  Agents  │    │ Aggregator│ │
│  └─────────┘    └──────────┘    └──────────┘    └─────┬────┘ │
│                                                       │      │
│  ┌─────────┐    ┌──────────┐    ┌──────────┐         │      │
│  │ Monitor  │←───│ Execution│←───│   Risk   │←────────┘      │
│  │  Agent   │    │  Agent   │    │  Agent   │                │
│  └────┬────┘    └──────────┘    └──────────┘                │
│       │                                                      │
│  ┌────▼────┐    ┌──────────┐                                │
│  │Reflection│───→│ Strategy │   ← Periodic batch job         │
│  │  Agent   │    │ Updater  │                                │
│  └─────────┘    └──────────┘                                │
└──────────────────────────────────────────────────────────────┘
```

### 5.3 Loop Assignments per Agent

| Agent | Loop Type | Frequency |
|---|---|---|
| Data Ingest | Event-driven (continuous) | Real-time |
| Research Agent | ReAct (search → read → synthesize) | On new events |
| Analysis Agent | Deliberation (weigh multiple signals) | Per signal |
| Signal Aggregator | Voting/Consensus | Per signal batch |
| Risk Agent | Evaluation (accept/modify/reject) | Per trade |
| Execution Agent | Plan-and-Execute | Per trade |
| Monitor Agent | Event-driven polling | Continuous |
| Reflection Agent | Reflection loop | Daily/Weekly |

### 5.4 Implementation Priority

1. **Phase 1:** Single ReAct agent with basic trading tools (data fetch, indicator calc, paper trading)
2. **Phase 2:** Add Risk Agent with HITL checkpoint
3. **Phase 3:** Add Research + Analysis agents as separate nodes in LangGraph
4. **Phase 4:** Add Reflection agent for strategy improvement
5. **Phase 5:** Add Monitor agent and production execution

### 5.5 Key Design Principles

1. **Start simple, add complexity only when needed** (Anthropic's advice)
2. **Every trade must have an auditable reasoning chain** (ReAct traces)
3. **Risk agent is always the last gate before execution** (non-negotiable)
4. **Human-in-the-loop for anything above threshold** (gradually increase autonomy)
5. **Reflection is not optional** — continuous improvement is the edge
6. **Memory is critical** — agents that forget past mistakes will repeat them
7. **Latency matters** — use fast models for execution-time decisions, slow models for research

---

## Sources & References

- Anthropic. "Building Effective Agents." Dec 2024. https://www.anthropic.com/engineering/building-effective-agents
- LangGraph Documentation. https://docs.langchain.com/oss/python/langgraph/overview
- CrewAI Documentation. https://docs.crewai.com/concepts/agents
- AutoGen Documentation. https://microsoft.github.io/autogen/
- Yao et al. "ReAct: Synergizing Reasoning and Acting in Language Models." ICLR 2023. https://arxiv.org/abs/2210.03629
- OpenBB Finance. https://github.com/OpenBB-finance/OpenBB
- AI4Finance Foundation. https://github.com/AI4Finance-Foundation
