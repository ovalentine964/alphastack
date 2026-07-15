# AlphaStack Multi-Agent Swarm Architecture

## The Problem
Current system: 5 agents in a linear pipeline (news → strategy → risk → execution → reflection).
This is good, but it's **one opinion**. Real hedge funds use **competing teams**.

## The Solution: Two Specialized Swarms

### 🅰️ SWARM A: "OpenClaw" — Aggressive Alpha Hunter
**Goal:** Find high-conviction trades, maximize returns
**Framework borrowed from:** OpenClaw's multi-agent orchestration (sessions_spawn, subagents)

| Agent | Role |
|-------|------|
| Momentum Scout | Identifies trending assets with strong directional moves |
| Pattern Hunter | Recognizes chart patterns (head & shoulders, flags, wedges) |
| Sentiment Reader | Analyzes news, social media, on-chain data |
| Liquidity Mapper | Finds institutional order flow, whale movements |
| Aggregator | Combines all signals, scores conviction |

**Risk appetite:** Higher risk, higher reward. Targets 2-5% per trade.

### 🅱️ SWARM B: "Hermes" — Defensive Risk Guardian  
**Goal:** Protect capital, avoid drawdowns, find safe entries
**Framework borrowed from:** Hermes agent patterns (reflection, self-correction)

| Agent | Role |
|-------|------|
| Macro Analyst | Checks BTC dominance, DXY, rates, global macro |
| Volatility Guard | Monitors ATR, VIX-like metrics, adjusts position sizing |
| Correlation Checker | Ensures portfolio isn't overexposed to one asset |
| Drawdown Monitor | Tracks max drawdown, enforces circuit breakers |
| Risk Aggregator | Scores overall risk, approves/blocks trades |

**Risk appetite:** Conservative. Prioritizes capital preservation.

### ⚔️ HOW THE SWARMS INTERACT

```
                    ┌─────────────────┐
                    │   ORCHESTRATOR  │
                    │  (Arbitrator)   │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼                              ▼
    ┌─────────────────┐            ┌─────────────────┐
    │    SWARM A      │            │    SWARM B      │
    │  "OpenClaw"     │            │    "Hermes"     │
    │  (Aggressive)   │◄──────────►│  (Defensive)    │
    │                 │  Debate    │                 │
    └────────┬────────┘            └────────┬────────┘
             │                              │
             ▼                              ▼
    Signal: BUY BTC    ← Consensus →    Risk: APPROVED
             │                              │
             └──────────┬───────────────────┘
                        ▼
                ┌───────────────┐
                │  EXECUTION    │
                │  (If both     │
                │   agree)      │
                └───────────────┘
```

### 🧠 CONSENSUS MECHANISM

A trade only executes when:
1. **Swarm A** gives signal with conviction ≥ 70%
2. **Swarm B** risk score is APPROVED (drawdown < 5%, correlation OK)
3. **Arbitrator** resolves any disagreements (uses MiMo reasoning)

If Swarm A says BUY but Swarm B says TOO RISKY → **no trade**.
If both agree → **high-conviction trade with full position sizing**.

### 🔄 EVOLUTION: Self-Improving System

The Reflection Agent reviews every trade and:
- Updates Swarm A's strategy weights (what signals worked?)
- Updates Swarm B's risk thresholds (were we too conservative/aggressive?)
- Stores learnings in AGI Episodic Memory
- Over time, the swarms **evolve** based on real performance

### 🛠️ IMPLEMENTATION PLAN

1. **Phase 1** (Now): Current 5-agent pipeline works ✅
2. **Phase 2**: Split strategy agent into Swarm A sub-agents
3. **Phase 3**: Split risk agent into Swarm B sub-agents  
4. **Phase 4**: Add Arbitrator with MiMo reasoning for tie-breaking
5. **Phase 5**: Add self-evolution via Reflection → weight updates

### 📚 FRAMEWORKS TO BORROW

| Framework | What to borrow |
|-----------|---------------|
| **OpenClaw** | Multi-session orchestration, subagent spawning, task delegation |
| **Hermes** | Self-reflection loops, correction patterns, memory management |
| **LangGraph** | Already used! State machines for agent coordination |
| **AutoGen** | Multi-agent debate patterns (Swarm A vs Swarm B) |
| **CrewAI** | Role-based agent teams with delegation |
