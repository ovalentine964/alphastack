# Alpha Stack — Multi-Agent System Architecture

**Date:** 2026-07-11
**Version:** 1.0
**Status:** Architecture Design — Ready for Implementation Review

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Agent Roles & Responsibilities](#2-agent-roles--responsibilities)
3. [Agent Communication Protocol](#3-agent-communication-protocol)
4. [Orchestration Pattern](#4-orchestration-pattern)
5. [Memory Systems](#5-memory-systems)
6. [Loop Systems](#6-loop-systems)
7. [Consensus Mechanism for Trade Decisions](#7-consensus-mechanism-for-trade-decisions)
8. [Agent Lifecycle](#8-agent-lifecycle)
9. [Failure Handling](#9-failure-handling)
10. [Trading Engine Integration](#10-trading-engine-integration)
11. [Broker Layer Integration](#11-broker-layer-integration)
12. [Implementation Roadmap](#12-implementation-roadmap)

---

## 1. Executive Summary

Alpha Stack uses a **hierarchical multi-agent system** where specialized AI agents each own one responsibility of the Alpha Strategy pipeline (16 steps). A central **Orchestrator Agent** coordinates agents, manages state, and enforces risk gates. Agents communicate via structured messages over an event bus, with shared state for position/portfolio data and message passing for deliberation.

**Core Design Principles:**

1. **One agent, one job** — each agent is a specialist, not a generalist
2. **Risk is infrastructure-level** — enforced by gateway middleware, not prompts
3. **Every trade has an auditable reasoning chain** — ReAct traces stored permanently
4. **Self-improvement is built in** — reflection and deliberation loops run continuously
5. **Latency-aware** — fast models for execution-time decisions, slow models for research
6. **Graceful degradation** — if any agent fails, the system pauses trading rather than guessing

**Framework Foundation:** Built on OpenClaw's gateway/session/sub-agent infrastructure, with LangGraph-style graph-based workflow execution for the decision pipeline, and Hermes-inspired closed learning loops for strategy improvement.

---

## 2. Agent Roles & Responsibilities

### 2.1 Agent Hierarchy Map

```
┌──────────────────────────────────────────────────────────────────────┐
│                          DEPTH 0: COORDINATOR                        │
│                    (Orchestrator Agent — Main Session)                │
│  Receives market events, user directives, and cron triggers.         │
│  Routes to specialist agents, synthesizes results, enforces gates.   │
└──────┬──────────┬──────────┬──────────┬──────────┬──────────┬───────┘
       │          │          │          │          │          │
┌──────▼───┐┌─────▼────┐┌───▼────┐┌────▼─────┐┌──▼─────┐┌──▼──────┐
│FUNDAMENTAL││ STRUCTURE││ LIQUIDITY││  SMC    ││ MOMENTUM││ CANDLESTICK│
│ AGENT    ││  AGENT   ││  AGENT  ││  AGENT  ││  AGENT  ││   AGENT    │
│(Step 1)  ││(Steps 2-4)││(Step 6) ││(Step 7) ││(Step 8) ││  (Step 9)  │
└──────────┘└──────────┘└─────────┘└─────────┘└─────────┘└────────────┘
       │          │          │          │          │          │
       └──────────┴──────────┴──────────┴──────────┴──────────┘
                              │
                    ┌─────────▼──────────┐
                    │  SIGNAL AGGREGATOR  │
                    │  (Confluence Score) │
                    └─────────┬──────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
       ┌──────▼──────┐ ┌─────▼─────┐ ┌───────▼───────┐
       │  RISK GATE  │ │   ENTRY   │ │   TAKE-PROFIT  │
       │  (Step 12)  │ │ (Steps    │ │   (Steps 13-15)│
       │             │ │  10-11)   │ │                │
       └──────┬──────┘ └─────┬─────┘ └───────┬───────┘
              │               │               │
       ┌──────▼───────────────▼───────────────▼───────┐
       │              EXECUTION AGENT                   │
       │         (Order routing + broker bridge)         │
       └───────────────────┬───────────────────────────┘
                           │
       ┌───────────────────┼───────────────────┐
       │                   │                   │
┌──────▼──────┐    ┌──────▼──────┐    ┌───────▼──────┐
│   MONITOR   │    │  REFLECTION │    │   JOURNAL    │
│   AGENT     │    │   AGENT     │    │    AGENT     │
│(Continuous) │    │(Daily/Weekly)│   │(Post-trade)  │
└─────────────┘    └─────────────┘    └──────────────┘
```

### 2.2 Agent Definitions

#### A. Orchestrator Agent (Depth 0)

| Property | Value |
|----------|-------|
| **Role** | Central coordinator, router, gatekeeper |
| **Session** | Main session (persistent, daily reset at market close) |
| **Loop Type** | Plan-and-Execute (strategic) + Event-driven (tactical) |
| **LLM Model** | High-capability model (reasoning-tier) |
| **Responsibilities** | Route signals, enforce pipeline order, manage HITL checkpoints, synthesize reports |
| **Tools** | All agent spawn tools, shared state read/write, cron trigger, notification delivery |
| **Max Concurrency** | Processes one instrument analysis at a time (sequential pipeline per pair) |

**Behavioral Rules:**
- Never skips the Risk Gate
- If any upstream agent fails, halts the pipeline for that instrument
- Escalates to human when confidence < threshold or risk > limit
- Runs the "should I trade today?" check (Step 1 output) before any analysis

---

#### B. Fundamental Intelligence Agent (Step 1)

| Property | Value |
|----------|-------|
| **Role** | Macro analysis, sentiment, event risk |
| **Loop Type** | ReAct (iterative search → read → synthesize) |
| **LLM Model** | Reasoning-tier for macro synthesis; FinBERT for sentiment classification |
| **Frequency** | On-demand (pre-session) + on-event (breaking news) |
| **Output** | `fundamental_bias`, `sentiment_score`, `event_risk_score`, `volatility_forecast` |

**Sub-Agents (Depth 2, spawned as needed):**
- **News Crawler Worker** — fetches from RSS, Finnhub, central bank feeds
- **Sentiment Worker** — runs FinBERT on headlines, LLM reasoning on complex events
- **Calendar Worker** — parses economic calendar, computes surprise scores

---

#### C. Market Structure Agent (Steps 2–4)

| Property | Value |
|----------|-------|
| **Role** | Regime detection, multi-TF structure, session analysis |
| **Loop Type** | Deliberation (weigh multiple analytical frameworks) |
| **LLM Model** | Fast model for structure classification; HMM model for regime |
| **Frequency** | Every new H1/H4 candle + on session transition |
| **Output** | `market_bias`, `regime`, `timeframe_alignment`, `session_state`, `asian_range`, `structure_map` |

**Internal Modules:**
- **Regime Detector** — 3-state HMM (Bull Trend / Bear Trend / Range)
- **Multi-TF Structure Engine** — Swing detection + BOS/CHoCH classification on W1→D1→4H→H1
- **Session Analyzer** — Session state machine, Asian range tracker, volatility profiles
- **Conflict Resolver** — Mediates fundamental vs technical disagreements

---

#### D. Liquidity Agent (Step 6)

| Property | Value |
|----------|-------|
| **Role** | Detect liquidity pools, classify sweeps, order flow analysis |
| **Loop Type** | Event-driven (on price approach to liquidity zone) |
| **LLM Model** | Minimal LLM use; primarily algorithmic (XGBoost sweep classifier) |
| **Frequency** | Continuous tick monitoring; full heatmap rebuild every M15 |
| **Output** | `liquidity_map`, `sweep_signals`, `order_flow_score`, `delta` |

**Sub-Agents:**
- **Order Book Worker** — real-time bid/ask depth monitoring
- **Sweep Classifier Worker** — ML model: real vs fake sweep detection
- **On-Chain Worker** (crypto only) — liquidation levels, whale movements

---

#### E. Smart Money Concepts Agent (Step 7)

| Property | Value |
|----------|-------|
| **Role** | Detect order blocks, FVGs, breaker/mitigation blocks |
| **Loop Type** | ReAct (scan → classify → score → validate) |
| **LLM Model** | Fast model for pattern classification; XGBoost for confluence scoring |
| **Frequency** | Every new M15 candle; full scan on H1/H4/D1/W1 |
| **Output** | `ob_list`, `fvg_list`, `structure_breaks`, `confluence_score` |

**Internal Modules:**
- **OB Scanner** — Algorithmic detection of order blocks (impulse + last counter candle)
- **FVG Scanner** — Gap detection + fill tracking
- **BOS/CHoCH Detector** — Structure break classification
- **Pattern Scorer** — Confluence scoring with volume + context multipliers
- **Failure Monitor** — Tracks pattern outcomes, adjusts confidence weights

---

#### F. Momentum Agent (Step 8)

| Property | Value |
|----------|-------|
| **Role** | RSI analysis, divergence detection, composite momentum |
| **Loop Type** | Deliberation (weigh multiple momentum indicators) |
| **LLM Model** | Minimal LLM; algorithmic (adaptive thresholds, composite scoring) |
| **Frequency** | Every new M15 candle |
| **Output** | `rsi_values`, `adaptive_thresholds`, `divergences`, `composite_momentum`, `confirmation_level` |

**Internal Modules:**
- **Adaptive RSI Engine** — Dynamic thresholds by regime (trending: 40/80, ranging: 30/70)
- **Multi-TF RSI Aligner** — Weighted alignment score across M15→H1→H4→D1
- **Divergence Detector** — Regular + hidden bullish/bearish divergences
- **Composite Momentum** — Weighted blend: RSI×0.35 + StochRSI×0.20 + MFI×0.20 + CCI×0.15 + WilliamsR×0.10

---

#### G. Candlestick Agent (Step 9)

| Property | Value |
|----------|-------|
| **Role** | Pattern detection, volume-weighted scoring, failure flagging |
| **Loop Type** | Event-driven (on candle close) |
| **LLM Model** | Minimal; CNN model for visual pattern recognition (optional) |
| **Frequency** | Every candle close on M15+ |
| **Output** | `patterns`, `best_pattern`, `pattern_score`, `failure_flags` |

---

#### H. Signal Aggregator Agent

| Property | Value |
|----------|-------|
| **Role** | Combine all signals into confluence score, generate trade proposal |
| **Loop Type** | Evaluation (accept/modify/reject based on threshold) |
| **Frequency** | Triggered when any signal agent produces output |
| **Output** | `confluence_score`, `trade_proposal` (direction, entry zone, confidence) |

**Confluence Scoring Matrix:**

| Signal Source | Base Score | With S/R | With Liquidity | With SMC | With RSI |
|--------------|-----------|----------|----------------|----------|----------|
| S/R Level | 20 | — | +15 | +20 | +10 |
| Liquidity Sweep | 25 | +15 | — | +25 | +10 |
| SMC Pattern | 30 | +20 | +25 | — | +15 |
| RSI Confirmation | 20 | +10 | +10 | +15 | — |
| Candlestick | 15 | +10 | +10 | +15 | +10 |

**Thresholds:**
- Score < 40: NO TRADE
- Score 40–60: ALERT ONLY (watchlist)
- Score 60–80: SMALL POSITION (0.5% risk)
- Score 80+: FULL POSITION (1–2% risk)

---

#### I. Entry Agent (Steps 10–11)

| Property | Value |
|----------|-------|
| **Role** | Determine exact entry type, price, and position sizing |
| **Loop Type** | Plan-and-Execute |
| **Frequency** | Triggered by Signal Aggregator when score ≥ 60 |
| **Output** | `entry_order` (type, price, size, SL, TP levels) |

**Entry Decision Tree:**
1. Market order (immediate, high conviction)
2. Limit order (better price, at S/R or OB)
3. Stop order (breakout confirmation)
4. Wait (signals conflict or session unfavorable)

---

#### J. Risk Gate Agent (Step 12)

| Property | Value |
|----------|-------|
| **Role** | Final gatekeeper — enforce all risk rules before execution |
| **Loop Type** | Evaluation (hard accept/reject, no modification) |
| **Frequency** | Triggered on every trade proposal |
| **Output** | `approved` (bool), `rejection_reason`, `modified_params` |
| **Authority** | **CANNOT BE OVERRIDDEN** by any other agent |

**Risk Rules (enforced at infrastructure level, not prompt level):**
- Max risk per trade: 1–2% of equity
- Max daily loss: 5% of equity
- Max open positions: 3 (configurable)
- Max correlation exposure: no more than 2 positions in correlated pairs
- Max drawdown halt: 15% → flatten all, pause trading, alert human
- Event proximity: reject if high-impact event within 30 minutes
- Kill switch: human can halt all trading instantly

---

#### K. Take-Profit Agent (Step 13)

| Property | Value |
|----------|-------|
| **Role** | Dynamic TP management, partial closes, trailing stops |
| **Loop Type** | Plan-and-Execute (pre-trade plan) + Event-driven (in-trade adjustments) |
| **Frequency** | Pre-trade: on entry. In-trade: every M15 candle |
| **Output** | `tp_levels`, `partial_close_signals`, `trailing_stop_updates` |

**Partial TP Framework:**
- 33% at 1R (lock in base case)
- 33% at 2R (optimistic case)
- 34% trailing with ATR(14)×2.5 (runner)

**Session Adjustments:**
- Asian entry: targets × 0.7
- London entry: targets × 1.0
- NY entry: targets × 1.1
- Overlap entry: targets × 1.3

---

#### L. Trade Management Agent (Steps 14–15)

| Property | Value |
|----------|-------|
| **Role** | In-trade monitoring, breakeven moves, partial closes, exit conditions |
| **Loop Type** | Event-driven (on price movement, structure change, news) |
| **Frequency** | Continuous monitoring while position is open |
| **Output** | `management_actions` (move SL, partial close, full close) |

**Exit Conditions:**
- Stop loss hit
- All TP levels reached
- Structure reversal (CHoCH against position)
- Time-based exit (position open > X hours without progress)
- Volatility regime change (extreme VIX spike)
- Correlation breach (new position creates excess correlation)

---

#### M. Execution Agent

| Property | Value |
|----------|-------|
| **Role** | Translate approved trade proposals into broker orders |
| **Loop Type** | Plan-and-Execute (plan execution strategy, execute step by step) |
| **Frequency** | On approved trade or management action |
| **Output** | `order_result` (fill price, slippage, execution time) |

**Execution Strategies:**
- Market order: immediate fill for urgent entries
- Limit order: price improvement for patient entries
- TWAP: split large orders over time (future scaling)
- Smart routing: select best execution venue (multi-broker)

---

#### N. Monitor Agent (Continuous)

| Property | Value |
|----------|-------|
| **Role** | System health, position monitoring, alert generation |
| **Loop Type** | Tiered event-driven monitoring |
| **Frequency** | See monitoring tiers below |
| **Output** | `alerts`, `system_health`, `position_status` |

**Monitoring Tiers:**

| Tier | Interval | Scope | Method |
|------|----------|-------|--------|
| T1 | 1s | Price/order monitoring | Direct exchange WebSocket (NOT through LLM) |
| T2 | 1m | Signal generation, anomaly detection | Lightweight model calls |
| T3 | 15m | Strategy review, news analysis, macro context | Full LLM analysis |
| T4 | 4h+ | Performance review, journal consolidation | Deep analysis |

---

#### O. Reflection Agent (Post-Trade / Periodic)

| Property | Value |
|----------|-------|
| **Role** | Review trades, extract lessons, update strategy parameters |
| **Loop Type** | Reflection (generate → critique → revise) |
| **Frequency** | Post-trade (within 1 hour of close) + daily summary + weekly deep review |
| **Output** | `lessons_learned`, `strategy_adjustments`, `parameter_updates` |

**Reflection Loop:**
1. **Record** — Log entry thesis, all signals, confluence score, risk params
2. **Compare** — What actually happened vs what was predicted
3. **Analyze** — Which signals were right/wrong, which were missing
4. **Update** — Adjust pattern weights, signal thresholds, risk parameters
5. **Store** — Promote durable lessons to long-term memory

---

#### P. Journal Agent (Step 16)

| Property | Value |
|----------|-------|
| **Role** | Maintain comprehensive trade journal, performance analytics |
| **Loop Type** | Post-trade compilation + periodic reporting |
| **Frequency** | Per-trade + daily + weekly + monthly |
| **Output** | `trade_journal`, `performance_report`, `attribution_analysis` |

---

### 2.3 Strategy Step → Agent Mapping

| Strategy Step | Agent | Loop Type | Trigger |
|--------------|-------|-----------|---------|
| Step 1: Fundamental Intelligence | Fundamental Agent | ReAct | Pre-session + on-event |
| Step 2: Market Bias | Structure Agent | Deliberation | On fundamental output + H4 candle |
| Step 3: Session Analysis | Structure Agent | Event-driven | Session transitions |
| Step 4: Market Structure | Structure Agent | Deliberation | H1/H4 candle close |
| Step 5: Support & Resistance | Structure Agent (S/R module) | ReAct | M15 candle close |
| Step 6: Liquidity Detection | Liquidity Agent | Event-driven | Continuous tick + M15 |
| Step 7: Smart Money Concepts | SMC Agent | ReAct | M15 candle close |
| Step 8: RSI Confirmation | Momentum Agent | Deliberation | M15 candle close |
| Step 9: Candlestick Confirmation | Candlestick Agent | Event-driven | Candle close |
| Step 10: Trade Entry | Entry Agent | Plan-and-Execute | Signal Aggregator output |
| Step 11: Position Sizing | Entry Agent | Evaluation | Entry decision |
| Step 12: Stop Loss | Risk Gate Agent | Evaluation | Every trade proposal |
| Step 13: Take Profit | TP Agent | Plan-and-Execute | On entry + in-trade |
| Step 14: Trade Management | Trade Mgmt Agent | Event-driven | Continuous while in trade |
| Step 15: Exit Conditions | Trade Mgmt Agent | Event-driven | Continuous while in trade |
| Step 16: Journal & Learning | Journal Agent + Reflection Agent | Reflection | Post-trade + periodic |

---

## 3. Agent Communication Protocol

### 3.1 Communication Patterns

Alpha Stack uses a **hybrid communication model** combining three patterns:

| Pattern | Use Case | Implementation |
|---------|----------|---------------|
| **Shared State** | Position/portfolio data, current regime, session state | Redis-backed state store (consistency-critical) |
| **Message Passing** | Agent-to-agent signal handoff, deliberation | Redis Streams (ordered, persistent, replayable) |
| **Event-Driven** | Market data distribution, alert broadcasting | Redis Pub/Sub (fire-and-forget, low latency) |

**Why hybrid:**
- Shared state ensures all agents see the same position/risk data (no race conditions on orders)
- Message passing provides ordered, auditable signal flow (replay for debugging)
- Event-driven enables reactive responses to market events (lowest latency)

### 3.2 Message Format

All inter-agent messages follow a standardized envelope:

```json
{
  "message_id": "uuid-v4",
  "timestamp": "2026-07-11T13:24:00.123Z",
  "source_agent": "smc_agent_01",
  "target_agent": "signal_aggregator",
  "channel": "signals.smc",
  "priority": "P1",
  "message_type": "SIGNAL",
  "ttl_seconds": 3600,
  "correlation_id": "trade_pipeline_EURUSD_20260711_132400",
  "payload": {
    "instrument": "EURUSD",
    "signal_type": "ORDER_BLOCK_DETECTED",
    "direction": "bullish",
    "data": {
      "ob_high": 1.0850,
      "ob_low": 1.0835,
      "timeframe": "H4",
      "strength": 0.82,
      "mitigated": false
    },
    "confidence": 0.82,
    "reasoning": "H4 bullish OB formed after impulsive move from 1.0820. OB at 1.0835-1.0850 aligns with D1 support and H1 FVG. Volume on impulse candle was 1.8x average."
  },
  "metadata": {
    "model_used": "qwen-2.5-72b",
    "inference_ms": 340,
    "loop_type": "react",
    "loop_iterations": 3
  }
}
```

### 3.3 Priority Levels

| Priority | Name | Latency Target | Use Case |
|----------|------|---------------|----------|
| **P0** | CRITICAL | < 1s | Liquidity sweep detected, risk breach, kill switch |
| **P1** | HIGH | < 5s | High-confluence signal, entry trigger, stop loss hit |
| **P2** | MEDIUM | < 30s | S/R level approach, SMC pattern, RSI extreme |
| **P3** | LOW | < 5m | Background scan update, session transition |
| **P4** | BACKGROUND | < 30m | Performance review, journal consolidation |

### 3.4 Channel Topology

```
Redis Streams (ordered, persistent):
├── pipeline.fundamental     → Fundamental Agent output
├── pipeline.structure       → Structure Agent output (bias, regime, S/R)
├── pipeline.liquidity       → Liquidity Agent output
├── pipeline.smc             → SMC Agent output
├── pipeline.momentum        → Momentum Agent output
├── pipeline.candlestick     → Candlestick Agent output
├── pipeline.confluence      → Signal Aggregator output
├── pipeline.risk_gate       → Risk Gate decisions
├── pipeline.execution       → Execution results
├── pipeline.management      → Trade management actions
└── pipeline.journal         → Journal entries

Redis Pub/Sub (fire-and-forget):
├── events.market_data       → Tick/bar data distribution
├── events.alerts            → Human-facing alerts
├── events.system_health     → Agent health heartbeats
└── events.kill_switch       → Emergency halt

Shared State (Redis Hashes):
├── state:positions          → Current open positions
├── state:portfolio          → Portfolio-level metrics
├── state:regime             → Current market regime per pair
├── state:session            → Current session state
├── state:risk_limits        → Current risk limit utilization
└── state:system             → Agent health status
```

### 3.5 Signal Handoff Protocol

When one agent completes its work and passes to the next:

```
1. Agent writes result to its output stream (pipeline.{agent_name})
2. Orchestrator reads from stream, validates message format
3. Orchestrator updates shared state if needed
4. Orchestrator routes to next agent in pipeline (or skips if not needed)
5. Next agent reads context from shared state + message payload
6. Agent acknowledges receipt by writing ACK to stream
7. If no ACK within timeout → Orchestrator retries or escalates
```

### 3.6 Agent Identity & Authentication

Each agent has a unique identity with scoped permissions:

```json
{
  "agent_id": "smc_agent_01",
  "agent_type": "smc",
  "depth": 1,
  "permissions": {
    "read": ["state:regime", "state:session", "pipeline.structure", "pipeline.liquidity"],
    "write": ["pipeline.smc"],
    "tools": ["fetch_ohlcv", "calculate_indicators"],
    "spawn_children": true,
    "max_children": 3,
    "execute_orders": false
  },
  "model_override": null,
  "sandbox": true
}
```

**Critical rule:** Only the Execution Agent has `execute_orders: true`. No analysis agent can place orders directly.

---

## 4. Orchestration Pattern

### 4.1 Hybrid Orchestration Model

Alpha Stack uses a **hierarchical orchestrator with event-driven specialist agents**:

- **Hierarchical:** Orchestrator Agent (Depth 0) controls the pipeline sequence, enforces gates, and manages HITL checkpoints
- **Event-Driven:** Specialist agents (Depth 1) react to events/messages rather than polling
- **Worker Delegation:** Specialist agents can spawn Depth 2 workers for parallel sub-tasks

```
                    ┌─────────────────────┐
                    │    ORCHESTRATOR      │
                    │   (Hierarchical)     │
                    │   Controls pipeline  │
                    │   sequence & gates   │
                    └──────────┬──────────┘
                               │
            ┌──────────────────┼──────────────────┐
            │                  │                  │
   ┌────────▼────────┐ ┌──────▼──────┐ ┌────────▼────────┐
   │  EVENT-DRIVEN   │ │ EVENT-DRIVEN│ │  EVENT-DRIVEN   │
   │  ANALYSIS       │ │ EXECUTION   │ │  MONITORING     │
   │  AGENTS         │ │ AGENTS      │ │  AGENTS         │
   │  (Depth 1)      │ │ (Depth 1)   │ │  (Depth 1)      │
   └────────┬────────┘ └──────┬──────┘ └────────┬────────┘
            │                  │                  │
   ┌────────▼────────┐ ┌──────▼──────┐ ┌────────▼────────┐
   │  WORKER         │ │  WORKER     │ │  WORKER         │
   │  DELEGATION     │ │  DELEGATION │ │  DELEGATION     │
   │  (Depth 2)      │ │  (Depth 2)  │ │  (Depth 2)      │
   └─────────────────┘ └─────────────┘ └─────────────────┘
```

### 4.2 Pipeline Execution Flow

For each instrument analysis cycle:

```
TRIGGER: New H4 candle close OR session transition OR breaking news
  │
  ▼
┌─────────────────────────────────────────────────────────────┐
│ PHASE 1: CONTEXT GATHERING (parallel)                        │
│                                                              │
│  Fundamental Agent ◄─── News/Calendar events                 │
│  Structure Agent   ◄─── OHLCV data across timeframes        │
│                                                              │
│  Both run in parallel. Structure Agent doesn't wait for      │
│  Fundamental Agent (they're independent data sources).       │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ PHASE 2: BIAS CONSTRUCTION (sequential)                      │
│                                                              │
│  Structure Agent combines:                                   │
│    - Fundamental bias (from Phase 1)                         │
│    - Technical structure (from Phase 1)                      │
│    - HMM regime detection                                    │
│    - Session context                                         │
│  → Outputs: market_bias, regime, session_state               │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ PHASE 3: SIGNAL DETECTION (parallel)                         │
│                                                              │
│  S/R Module       ◄─── Bias + OHLCV → Key levels            │
│  Liquidity Agent  ◄─── Bias + Order book → Liquidity map    │
│  SMC Agent        ◄─── Bias + OHLCV → OB/FVG/BOS/CHoCH     │
│  Momentum Agent   ◄─── OHLCV → RSI/Composite momentum       │
│  Candlestick Agent◄─── OHLCV → Candle patterns              │
│                                                              │
│  All 5 agents run in parallel. Each only needs bias + data. │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ PHASE 4: CONFLUENCE SCORING (sequential)                     │
│                                                              │
│  Signal Aggregator collects all Phase 3 outputs:             │
│    - Calculates confluence score                             │
│    - If score < 40 → NO TRADE (log and stop)                 │
│    - If score ≥ 40 → Generate trade proposal                 │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ PHASE 5: TRADE PREPARATION (sequential)                      │
│                                                              │
│  Entry Agent: Determine entry type, price, size              │
│  Risk Gate Agent: Validate against all risk rules            │
│    - REJECTED → Log reason, stop                             │
│    - APPROVED → Proceed to execution                         │
│  HITL Check: If risk > threshold → Pause for human approval  │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ PHASE 6: EXECUTION (sequential)                              │
│                                                              │
│  Execution Agent: Submit order to broker                     │
│  Monitor Agent: Track fill, slippage, latency                │
│  TP Agent: Set take-profit levels and trailing stops         │
│  Journal Agent: Log trade entry with full context            │
└─────────────────────────────────────────────────────────────┘
```

### 4.3 Pipeline Optimization

**Parallelization:** Phases 1 and 3 are fully parallel — agents don't depend on each other within these phases.

**Conditional Execution:** Not all phases run for every cycle:
- If fundamental bias says "AVOID_ALL" → Skip Phases 3–6
- If session is OFF_HOURS → Skip all analysis
- If no new candle on any timeframe → Skip signal detection (use cached results)
- If position already open on instrument → Skip to Phase 6 (trade management)

**Caching:** Each agent caches its last result in shared state with a TTL:
- Fundamental: 1 hour (or on breaking news)
- Structure: until next H4 candle
- S/R: until next D1 candle
- SMC: until next M15 candle
- Momentum: until next M15 candle

### 4.4 HITL (Human-in-the-Loop) Checkpoints

| Scenario | Action | Timeout |
|----------|--------|---------|
| Standard trade within risk params | Auto-execute | — |
| Trade exceeds 1.5% risk | Alert + require approval | 5 min → conservative action |
| New market regime detected | Alert + pause trading | 15 min → continue with caution |
| Loss streak > 3 trades | Alert + halt strategy | 30 min → flatten remaining |
| Max drawdown 10% reached | Alert + reduce all positions | 5 min → auto-reduce |
| Max drawdown 15% reached | Alert + flatten ALL | Immediate (no timeout) |
| Strategy parameter change | Require approval | No auto-action |
| New instrument / unfamiliar setup | Require approval | No auto-action |

**Dead Man's Switch:** If human doesn't respond within timeout, the system takes the conservative action (reduce size, move to breakeven, or close position).

---

## 5. Memory Systems

### 5.1 Three-Layer Memory Architecture

Adapted from OpenClaw's memory model, specialized for trading:

```
┌─────────────────────────────────────────────────────────────┐
│                    MEMORY ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  LAYER 1: WORKING MEMORY (Session-Scoped)                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Current market state, active positions,             │    │
│  │  latest signals, in-progress pipeline state          │    │
│  │                                                      │    │
│  │  Storage: Redis (in-memory, fast read/write)         │    │
│  │  TTL: Session-scoped (cleared on session reset)      │    │
│  │  Access: All agents (read), Orchestrator (write)     │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  LAYER 2: SHORT-TERM MEMORY (Daily)                          │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Today's signals, trades, news events,               │    │
│  │  session-level observations                          │    │
│  │                                                      │    │
│  │  Storage: File-based (memory/YYYY-MM-DD.md)          │    │
│  │  Format: Structured markdown with timestamps         │    │
│  │  Retention: 30 days (archived after)                 │    │
│  │  Access: All agents (read), Journal Agent (write)    │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  LAYER 3: LONG-TERM MEMORY (Persistent)                      │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Trade journal, strategy parameters, lessons,        │    │
│  │  pattern reliability stats, market regime history    │    │
│  │                                                      │    │
│  │  Storage: Vector DB (semantic search) + TimescaleDB  │    │
│  │  Format: Structured records + embeddings             │    │
│  │  Retention: Permanent (with periodic pruning)        │    │
│  │  Access: All agents (read), Reflection Agent (write) │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  LAYER 4: EPISODIC MEMORY (Trade History)                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Complete trade records with entry thesis,           │    │
│  │  all signals, execution details, outcome, lessons    │    │
│  │                                                      │    │
│  │  Storage: TimescaleDB (structured) + Vector DB       │    │
│  │  Format: JSONB records with embeddings               │    │
│  │  Retention: Permanent                                │    │
│  │  Query: "Find similar setups to current conditions"  │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 Memory File Structure

```
memory/
├── YYYY-MM-DD.md              # Daily notes (raw logs)
├── heartbeat-state.json       # Last-check timestamps
│
├── trade_journal/
│   ├── trades_YYYY-MM.jsonl   # Trade records (append-only)
│   └── daily_summary_YYYY-MM-DD.md
│
├── strategy/
│   ├── STRATEGIES.md          # Active strategy parameters
│   ├── EDGE_NOTES.md          # Distilled market insights
│   ├── LESSONS.md             # Mistakes and corrections
│   └── MARKET_STRUCTURE.md    # Current regime, correlations
│
├── patterns/
│   ├── pattern_reliability.json  # Win rates by pattern type
│   └── signal_weights.json       # Current signal scoring weights
│
└── consolidated/
    ├── weekly_YYYY-WNN.md     # Weekly performance digest
    └── monthly_YYYY-MM.md     # Monthly strategy review
```

### 5.3 Memory Access Patterns

| Agent | Working Memory | Short-Term | Long-Term | Episodic |
|-------|---------------|------------|-----------|----------|
| Orchestrator | Read/Write | Read | Read | Read |
| Fundamental | Read | Read/Write | Read | Read |
| Structure | Read/Write | Read/Write | Read | Read |
| Liquidity | Read | Read | Read | Read |
| SMC | Read | Read | Read | Read |
| Momentum | Read | Read | Read | Read |
| Candlestick | Read | Read | Read | — |
| Signal Aggregator | Read/Write | Read | Read | Read |
| Entry | Read/Write | Read | Read | Read |
| Risk Gate | Read/Write | Read | Read | Read |
| TP | Read/Write | Read | Read | Read |
| Trade Mgmt | Read/Write | Read | Read | Read |
| Execution | Read/Write | Read | — | — |
| Monitor | Read/Write | Read | Read | — |
| Reflection | Read | Read/Write | Read/Write | Read |
| Journal | Read | Read/Write | Read/Write | Read/Write |

### 5.4 Closed Learning Loop (Hermes-Inspired)

The Reflection Agent implements a **closed learning loop** where the system automatically creates reusable knowledge from experience:

```
TRADE COMPLETED
  │
  ▼
REFLECTION AGENT:
  1. Record full trade context (entry signals, confluence score, execution)
  2. Compare predicted outcome vs actual outcome
  3. Identify which signals were correct / incorrect / missing
  4. Generate lesson: "In [conditions], [signal] predicted [outcome] 
     but [reality]. Adjust [parameter] by [amount]."
  5. Update signal weights in patterns/signal_weights.json
  6. If lesson is durable → Promote to EDGE_NOTES.md
  7. If pattern reliability changed → Update patterns/pattern_reliability.json
  8. If strategy parameter needs change → Propose to human for approval
```

**Compounding Effect:** After 100 trades, the system has:
- Accurate pattern reliability statistics per pair, session, regime
- Calibrated signal weights that reflect actual predictive power
- A library of market insights (EDGE_NOTES.md) specific to traded instruments
- Adaptive RSI thresholds that match current market conditions

### 5.5 Semantic Search for Trade History

When a new setup appears, the system searches for similar past trades:

```python
# Query: "Find trades similar to current EURUSD setup"
similar_trades = memory_search(
    query="EURUSD bullish order block at H4 support with RSI oversold during London session",
    corpus="episodic",
    max_results=10,
    min_score=0.7
)

# Returns: Past trades with similar conditions, their outcomes, and lessons learned
# The Entry Agent uses this to calibrate position size and confidence
```

---

## 6. Loop Systems

### 6.1 Loop Type Assignments

Each agent uses the loop pattern best suited to its task:

| Loop Type | Agents | When Used | Why |
|-----------|--------|-----------|-----|
| **ReAct** | Fundamental, SMC, S/R Module | Information gathering + reasoning | Forces auditable reasoning chain; dynamic data fetching |
| **Deliberation** | Structure, Momentum | Weighing multiple signals | Explicitly evaluates options before committing |
| **Plan-and-Execute** | Entry, TP, Execution | Action planning + step-by-step execution | Separates strategy from tactics |
| **Reflection** | Journal, Reflection | Post-trade review | Self-correction and learning |
| **Event-Driven** | Liquidity, Monitor, Trade Mgmt | Reactive responses | Lowest latency for time-sensitive events |
| **Evaluation** | Signal Aggregator, Risk Gate | Accept/reject decisions | Binary gate with clear criteria |

### 6.2 ReAct Loop — Fundamental Agent Example

```
TRIGGER: Pre-session scan requested

Thought: "It's London session open. Let me check the economic calendar first."
Action: fetch_economic_calendar(hours_ahead=8)
Observation: "US CPI at 13:30 UTC today. Expected 3.1% YoY. Previous 3.3%."

Thought: "High-impact event. Let me check recent CPI surprises and market reaction."
Action: search_trade_history("US CPI surprise EURUSD reaction")
Observation: "Last 3 CPI beats → EURUSD dropped 40-60 pips in 30 min. Last miss → +35 pips."

Thought: "Let me check current sentiment positioning."
Action: fetch_sentiment("EURUSD")
Observation: "FinBERT: Neutral (0.52). Social sentiment: Slightly bearish. COT: Net long EUR increasing."

Thought: "High-impact event today with asymmetric risk. Recommend reduced position sizing 
          or wait until post-CPI. Event risk score: 0.85 (HIGH)."
Action: emit_signal({
  fundamental_bias: "NEUTRAL",
  event_risk_score: 0.85,
  recommendation: "WAIT_UNTIL_POST_CPI",
  reasoning: "CPI release at 13:30. Historical pattern shows 40-60 pip moves. 
              Avoid pre-CPI entries. Monitor for post-release setup."
})
```

### 6.3 Deliberation Loop — Structure Agent Example

```
TRIGGER: H4 candle close on EURUSD

Step 1: GENERATE OPTIONS
  Option A: Bullish bias (W1 HH/HL, D1 trending up, H4 BOS bullish)
  Option B: Bearish bias (H4 showing potential LH, RSI overbought on H1)
  Option C: Neutral (conflicting signals across timeframes)

Step 2: EVALUATE EACH OPTION
  Option A:
    - W1: Bullish HH/HL confirmed. Weight: 0.35. Score: 0.35 × 0.9 = 0.315
    - D1: Bullish BOS on last swing. Weight: 0.30. Score: 0.30 × 0.8 = 0.240
    - H4: Bullish BOS. Weight: 0.20. Score: 0.20 × 0.85 = 0.170
    - H1: Neutral (consolidating). Weight: 0.15. Score: 0.15 × 0.3 = 0.045
    - Total: 0.770. Regime: TRENDING_BULL (HMM posterior: 0.82)
  
  Option B:
    - H1 RSI at 72 (overbought) → potential pullback
    - But H4 structure still bullish, no CHoCH yet
    - Score: 0.350 (weak bearish case)
  
  Option C:
    - No strong conflict — most timeframes aligned bullish
    - Score: 0.200

Step 3: SELECT AND JUSTIFY
  "Selecting Option A (Bullish bias) with confidence 0.77.
   Multi-TF alignment score: 0.77 (above 0.75 threshold for high conviction).
   Regime: Trending Bull (0.82 confidence).
   H1 overbought RSI noted but not sufficient to override HTF structure.
   Recommendation: Look for buy setups at H4 OB or S/R pullback."
```

### 6.4 Plan-and-Execute Loop — Entry Agent Example

```
TRIGGER: Confluence score 85 (HIGH) for EURUSD long

PLANNING PHASE:
  "Trade proposal: EURUSD Long
   Entry zone: 1.0835-1.0850 (H4 Order Block)
   Entry type: Limit order at 1.0842 (mid-OB)
   Stop loss: 1.0810 (below OB low + 5 pip buffer = 32 pips)
   Position size: 0.02 lots (1.5% risk on $500 account = $7.50 risk)
   TP1: 1.0887 (1.5R = 45 pips) — close 33%
   TP2: 1.0932 (3R = 90 pips) — close 33%
   TP3: Trail with ATR(14)×2.5 — close remaining 34%
   
   Execution plan:
   1. Submit limit buy at 1.0842
   2. Set stop loss at 1.0810
   3. Set TP1 at 1.0887
   4. Monitor for fill
   5. On fill: Set trailing stop for TP3"

EXECUTION PHASE:
  Step 1: submit_order(type=LIMIT, side=BUY, price=1.0842, size=0.02)
  Step 2: set_stop_loss(price=1.0810)
  Step 3: set_take_profit(price=1.0887, size=0.0066)  # 33% of 0.02
  Step 4: monitor_order(order_id)
  → Filled at 1.0843 (1 pip slippage)
  Step 5: set_trailing_stop(method=ATR, multiplier=2.5, timeframe=H4)
```

### 6.5 Reflection Loop — Post-Trade Review

```
TRIGGER: Trade closed (EURUSD long, +45 pips, +$6.75)

Phase 1: RECORD
  Entry thesis: "H4 OB at S/R level, bullish BOS, RSI oversold on H1, 
                 London session, confluence score 85"
  Actual outcome: +1.5R (+$6.75)
  Execution: Filled 1 pip from limit, 0 slippage on exit

Phase 2: COMPARE
  Predicted: Price would bounce from H4 OB and target previous high
  Actual: Price bounced exactly from OB low, reached TP1, pulled back, 
          then continued to TP2 level (but TP2 wasn't set aggressively enough)
  Missed opportunity: Could have held for 2.5R instead of 1.5R partial

Phase 3: ANALYZE
  What worked:
    ✓ H4 OB detection was accurate (price bounced from exact level)
    ✓ Multi-TF alignment correctly identified bullish bias
    ✓ London session timing was optimal for this entry
  What could improve:
    ⚠ TP1 was too conservative for trending market regime
    ⚠ Could have used wider TP targets when regime confidence > 0.8
    ⚠ Trailing stop was triggered prematurely by H1 noise

Phase 4: UPDATE
  - patterns/signal_weights.json: Increase H4 OB weight by 0.02 (was 0.30, now 0.32)
  - patterns/pattern_reliability.json: H4 OB win rate updated (12/15 = 80%)
  - EDGE_NOTES.md: "When regime confidence > 0.8 in trending market, 
     use 1.5x normal TP targets. The trend continuation probability is high."
  - signal_weights.json: Trailing stop ATR multiplier: 2.5 → 3.0 for trending regimes

Phase 5: STORE
  - Trade recorded in trade_journal/trades_2026-07.jsonl
  - Lesson promoted to LESSONS.md: "H4 OBs in trending markets with 
     multi-TF alignment have 80% win rate. Use wider TPs."
```

### 6.6 Loop Scheduling Summary

```
CONTINUOUS (event-driven, no fixed interval):
  → Order book monitoring (Liquidity Agent)
  → Position monitoring (Trade Mgmt Agent)
  → System health checks (Monitor Agent)
  → Kill switch monitoring

EVERY TICK / 1 SECOND:
  → Price proximity to S/R levels
  → Stop loss / take profit trigger checks
  → Delta calculation

EVERY MINUTE:
  → Sweep detection (Liquidity Agent)
  → Anomaly detection (Monitor Agent)

EVERY M15 CANDLE:
  → S/R scan update
  → SMC pattern detection (OB, FVG, BOS/CHoCH)
  → RSI calculation + divergence scan
  → Confluence score calculation
  → TP level adjustment (in-trade)

EVERY H1 CANDLE:
  → Volume profile rebuild
  → Order flow analysis
  → H1-H4 SMC scan
  → Market regime update
  → Adaptive RSI threshold recalculation

EVERY H4 CANDLE:
  → Full pipeline cycle (Phases 1-6)
  → Institutional data refresh
  → ML model inference
  → On-chain data update (crypto)

EVERY D1 (session reset):
  → Full S/R recalculation
  → Pattern reliability update
  → Daily journal compilation
  → Signal weight review

POST-TRADE:
  → Reflection loop (within 1 hour)
  → Journal entry compilation
  → Signal weight updates

WEEKLY:
  → Deep strategy review (Reflection Agent, high-capability model)
  → HMM retraining
  → Performance attribution analysis
  → Memory consolidation (promote lessons to MEMORY.md)

MONTHLY:
  → Full model recalibration
  → Pattern reliability audit
  → Strategy parameter review (requires human approval for changes)
```

---

## 7. Consensus Mechanism for Trade Decisions

### 7.1 Voting Architecture

Trade decisions are not made by a single agent. They emerge from a **weighted consensus** across multiple specialist agents:

```
┌──────────────────────────────────────────────────────────┐
│                 CONSENSUS MECHANISM                        │
├──────────────────────────────────────────────────────────┤
│                                                           │
│  AGENT VOTES:                                             │
│  ┌──────────────┬────────┬────────┬──────────────────┐   │
│  │ Agent        │ Weight │ Vote   │ Confidence       │   │
│  ├──────────────┼────────┼────────┼──────────────────┤   │
│  │ Fundamental  │ 0.15   │ +0.8   │ 0.70             │   │
│  │ Structure    │ 0.25   │ +0.9   │ 0.82             │   │
│  │ S/R Module   │ 0.15   │ +0.7   │ 0.75             │   │
│  │ Liquidity    │ 0.10   │ +0.6   │ 0.65             │   │
│  │ SMC          │ 0.15   │ +0.85  │ 0.80             │   │
│  │ Momentum     │ 0.10   │ +0.5   │ 0.60             │   │
│  │ Candlestick  │ 0.10   │ +0.7   │ 0.70             │   │
│  └──────────────┴────────┴────────┴──────────────────┘   │
│                                                           │
│  WEIGHTED CONSENSUS:                                      │
│  Σ(weight × vote × confidence) / Σ(weight × confidence)  │
│                                                           │
│  = (0.15×0.8×0.7 + 0.25×0.9×0.82 + 0.15×0.7×0.75 +     │
│     0.10×0.6×0.65 + 0.15×0.85×0.8 + 0.10×0.5×0.6 +     │
│     0.10×0.7×0.7) /                                      │
│    (0.15×0.7 + 0.25×0.82 + 0.15×0.75 + 0.10×0.65 +      │
│     0.15×0.8 + 0.10×0.6 + 0.10×0.7)                     │
│                                                           │
│  = 0.73 / 0.74 = 0.987 (normalized to 0-1 scale)         │
│                                                           │
│  DECISION: STRONG BUY (consensus > 0.7)                   │
│  CONFLUENCE SCORE: 85/100                                  │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

### 7.2 Voting Rules

| Rule | Description |
|------|-------------|
| **Minimum Voters** | At least 4 of 7 agents must vote |
| **Veto Power** | Risk Gate Agent has absolute veto (overrides all consensus) |
| **Fundamental Veto** | If event_risk_score > 0.8 → automatic NO TRADE regardless of consensus |
| **Regime Filter** | If regime confidence < 0.6 → reduce position size by 50% |
| **Conflict Penalty** | If fundamental and technical votes disagree by > 0.5 → reduce score by 30% |
| **Minimum Confidence** | Any agent with confidence < 0.4 is excluded from voting |
| **Recency Weight** | More recent signals weighted 1.2x vs older cached signals |

### 7.3 Conflict Resolution

When agents disagree:

```
CONFLICT DETECTED: Fundamental says BEARISH, Structure says BULLISH

RESOLUTION PROTOCOL:
  1. Check event proximity
     → If high-impact event < 4h: Defer to Fundamental
     → Otherwise: Continue resolution

  2. Check signal strength
     → If one side has confidence > 0.8 and other < 0.5: Follow strong signal
     → If both > 0.7: WAIT (don't trade in conflict)

  3. Check regime
     → If trending: Weight Structure higher (technicals dominate in trends)
     → If ranging: Weight Fundamental higher (events dominate in ranges)

  4. Check timeframe
     → Short-term trade (< 4H): Technicals 70%, Fundamentals 30%
     → Medium-term trade (1-5 days): 50/50
     → Long-term trade (> 1 week): Fundamentals 65%, Technicals 35%

  5. Default: If still unresolved → NO TRADE (conservative)
```

### 7.4 Adaptive Weight Adjustment

Agent weights are not static. They adapt based on recent performance:

```python
# Weekly weight adjustment
for agent in agents:
    recent_accuracy = calculate_accuracy(agent.last_50_signals)
    historical_accuracy = agent.historical_accuracy
    
    # Blend recent and historical (70/30)
    blended = 0.7 * recent_accuracy + 0.3 * historical_accuracy
    
    # Adjust weight (bounded between 0.05 and 0.40)
    agent.weight = clip(blended * total_weight, 0.05, 0.40)

# Normalize weights to sum to 1.0
normalize_weights(agents)
```

**Example:** If the SMC Agent's win rate drops from 70% to 50% over the last 50 signals, its weight decreases from 0.15 to ~0.11, while more accurate agents gain weight.

---

## 8. Agent Lifecycle

### 8.1 Lifecycle States

```
┌─────────┐    ┌─────────┐    ┌──────────┐    ┌─────────┐
│  SPAWN  │───▶│  READY  │───▶│ RUNNING  │───▶│COMPLETE │
└─────────┘    └─────────┘    └──────────┘    └─────────┘
                    │              │    │
                    │              │    ▼
                    │              │  ┌─────────┐
                    │              │  │ PAUSED  │ (HITL checkpoint)
                    │              │  └─────────┘
                    │              │       │
                    │              ▼       ▼
                    │         ┌──────────┐
                    │         │  FAILED  │
                    │         └──────────┘
                    │              │
                    ▼              ▼
               ┌─────────┐   ┌──────────┐
               │ RETIRED │   │ RESTART  │
               └─────────┘   └──────────┘
```

### 8.2 Spawn Rules

| Agent | Spawn Trigger | Context Mode | Max Children | Timeout |
|-------|--------------|--------------|--------------|---------|
| Orchestrator | System start | Main session | 8 | Persistent |
| Fundamental | Pre-session / on-event | Isolated | 3 (workers) | 5 min |
| Structure | H4 candle / session transition | Isolated | 2 (workers) | 2 min |
| Liquidity | Continuous (always running) | Main session | 2 (workers) | Persistent |
| SMC | M15 candle close | Isolated | 2 (workers) | 1 min |
| Momentum | M15 candle close | Isolated | 0 | 30s |
| Candlestick | Candle close | Isolated | 0 | 15s |
| Signal Aggregator | On signal from any agent | Isolated | 0 | 30s |
| Entry | Confluence score ≥ 60 | Isolated | 0 | 1 min |
| Risk Gate | On trade proposal | Isolated | 0 | 10s |
| TP | On entry confirmation | Fork | 0 | Persistent (while position open) |
| Trade Mgmt | On entry confirmation | Fork | 0 | Persistent (while position open) |
| Execution | On approved trade | Isolated | 0 | 30s |
| Monitor | System start | Main session | 0 | Persistent |
| Reflection | Post-trade / daily cron | Isolated | 0 | 10 min |
| Journal | Post-trade / daily cron | Isolated | 0 | 5 min |

### 8.3 Health Monitoring

Each agent reports health via heartbeat:

```json
{
  "agent_id": "smc_agent_01",
  "status": "running",
  "uptime_seconds": 3600,
  "last_signal_time": "2026-07-11T13:24:00Z",
  "signals_produced": 47,
  "avg_inference_ms": 340,
  "errors_last_hour": 0,
  "memory_usage_mb": 256,
  "model": "qwen-2.5-72b"
}
```

**Monitor Agent checks every 30 seconds:**
- If agent hasn't reported in 2 minutes → WARN
- If agent hasn't reported in 5 minutes → RESTART
- If agent restarts 3 times in 10 minutes → ESCALATE to human
- If agent memory > 1GB → RESTART (memory leak detection)

### 8.4 Restart Protocol

```
AGENT FAILURE DETECTED
  │
  ▼
1. Log failure reason (last error, stack trace, context)
  │
  ▼
2. Check if failure is recoverable
   ├── Timeout → Restart with fresh context
   ├── Model error → Restart with fallback model
   ├── Data error → Restart with cached data
   └── Unknown → Escalate to human
  │
  ▼
3. Spawn replacement agent
   - Same agent type, fresh session
   - Load last known good state from shared memory
   - Resume from last checkpoint
  │
  ▼
4. If replacement also fails within 5 minutes
   → Pause pipeline for affected instrument
   → Alert human
   → Continue monitoring other instruments
```

### 8.5 Agent Retirement

Agents are retired when:
- **Task complete:** Analysis agent finishes its cycle → session archived after 1 hour
- **Position closed:** Trade management agent → session archived after journal compilation
- **Superseded:** New version of agent deployed → old version drains and retires
- **Manual:** Human explicitly stops agent via command

---

## 9. Failure Handling

### 9.1 Failure Categories

| Category | Examples | Response | Recovery |
|----------|---------|----------|----------|
| **Agent Timeout** | LLM inference too slow, API hang | Kill agent, restart | Cached data fallback |
| **Model Error** | LLM returns garbage, rate limited | Retry with backoff, fallback model | Switch to lighter model |
| **Data Error** | Missing candle, stale price feed | Use cached data, alert | Switch data source |
| **Execution Error** | Order rejected, broker disconnect | Retry order, alert human | Manual intervention |
| **Risk Breach** | Position exceeds limits | Immediate flatten | Human review required |
| **Cascade Failure** | Multiple agents fail simultaneously | Halt ALL trading | Full system restart |

### 9.2 Circuit Breakers

```
LEVEL 1 — SINGLE AGENT FAILURE
  Action: Restart agent, use cached data
  Impact: Pipeline delayed by < 30 seconds
  Auto-recovery: Yes

LEVEL 2 — MULTIPLE AGENT FAILURES (2+ in same pipeline)
  Action: Halt pipeline for affected instrument
  Impact: Instrument offline until recovery
  Auto-recovery: Yes, after all agents healthy for 5 minutes

LEVEL 3 — EXECUTION FAILURE
  Action: Halt all new entries, manage existing positions only
  Impact: No new trades until execution restored
  Auto-recovery: Requires human confirmation

LEVEL 4 — RISK BREACH
  Action: Flatten all positions, halt all trading
  Impact: Full stop
  Auto-recovery: NO — requires human review and manual restart

LEVEL 5 — CASCADE FAILURE
  Action: Emergency shutdown of all agents
  Impact: System offline
  Auto-recovery: NO — requires human intervention
  Emergency: Existing positions remain open with broker-side stops
```

### 9.3 Graceful Degradation

When resources are constrained (model API down, high latency):

```
NORMAL OPERATION:
  All 7 signal agents active → Full consensus → Full position sizing

DEGRADED MODE (3+ agents unavailable):
  Only Structure + SMC + Momentum active → Reduced consensus
  → Position size reduced by 50%
  → Alert: "Operating in degraded mode. Reduced confidence."

MINIMAL MODE (only 1-2 agents available):
  Only Monitor Agent active → No new analysis
  → Manage existing positions only
  → Alert: "Minimal mode. No new trades."

EMERGENCY MODE (all agents down):
  Broker-side stops still active (set at order time)
  → Positions protected by stop losses
  → Alert: "System offline. Positions protected by broker stops."
```

### 9.4 Data Source Failover

| Primary Source | Failover 1 | Failover 2 | Failover 3 |
|---------------|------------|------------|------------|
| MT5 API | CCXT (crypto) | Cached data | Stale data + alert |
| Finnhub news | RSS feeds | Cached headlines | Skip news analysis |
| Economic calendar | ForexFactory | Cached calendar | Skip event check |
| Order book | Exchange WebSocket | Snapshot cache | Skip liquidity analysis |
| On-chain data | Coinglass API | Cached data | Skip on-chain layer |

---

## 10. Trading Engine Integration

### 10.1 Architecture Boundary

**Critical Design Decision:** The multi-agent system does NOT execute orders directly. It generates **trade proposals** that are validated by a separate **Trading Engine** before reaching the broker.

```
MULTI-AGENT SYSTEM                    TRADING ENGINE              BROKER
(Decision Making)                     (Execution Safety)          (Market)
                                     
┌──────────────┐                     ┌──────────────┐           ┌─────────┐
│ Signal       │    Trade Proposal   │ Risk         │  Order    │ MT5 /   │
│ Aggregator   │────────────────────▶│ Validator    │──────────▶│ Exchange│
└──────────────┘                     │              │           └─────────┘
                                     │ • Idempotency│
┌──────────────┐                     │ • Dedup      │           ┌─────────┐
│ Risk Gate    │    Approved Trade   │ • Circuit    │  Fill     │ Order   │
│ Agent        │────────────────────▶│ • Logging    │◀──────────│ Result  │
└──────────────┘                     │ • Atomicity  │           └─────────┘
                                     └──────────────┘
```

### 10.2 Trade Proposal Format

```json
{
  "proposal_id": "uuid-v4",
  "timestamp": "2026-07-11T13:24:00Z",
  "instrument": "EURUSD",
  "action": "BUY",
  "order_type": "LIMIT",
  "entry_price": 1.0842,
  "stop_loss": 1.0810,
  "take_profits": [
    {"price": 1.0887, "size_pct": 33, "label": "TP1"},
    {"price": 1.0932, "size_pct": 33, "label": "TP2"},
    {"method": "trailing", "atr_multiple": 2.5, "size_pct": 34, "label": "TP3"}
  ],
  "position_size_lots": 0.02,
  "risk_pct": 1.5,
  "confluence_score": 85,
  "reasoning": "H4 OB at D1 support, bullish BOS, RSI oversold H1, London session",
  "signals": {
    "fundamental": {"bias": "NEUTRAL", "confidence": 0.70},
    "structure": {"bias": "BULLISH", "confidence": 0.82},
    "sr_level": {"price": 1.0840, "score": 78},
    "liquidity": {"sweep_detected": false, "pool_below": true},
    "smc": {"ob_type": "bullish", "ob_strength": 0.82, "fvg_present": true},
    "momentum": {"rsi_m15": 28, "composite": 22, "confirmation": "STRONG"},
    "candlestick": {"pattern": "hammer", "score": 0.75}
  },
  "approved_by": "risk_gate_agent",
  "hitl_required": false,
  "ttl_seconds": 300
}
```

### 10.3 Trading Engine Components

```python
class TradingEngine:
    """
    Separates decision-making (agents) from execution (engine).
    All safety checks happen here, independent of LLM agents.
    """
    
    def __init__(self, broker_adapter, risk_config):
        self.broker = broker_adapter
        self.risk = RiskValidator(risk_config)
        self.orders = OrderManager()
        self.positions = PositionManager()
        self.audit = AuditLog()
    
    def process_proposal(self, proposal: TradeProposal) -> ExecutionResult:
        # 1. Validate proposal format
        if not self._validate_format(proposal):
            return ExecutionResult(status="REJECTED", reason="Invalid format")
        
        # 2. Check idempotency (prevent duplicate orders)
        if self.orders.is_duplicate(proposal):
            return ExecutionResult(status="DUPLICATE", reason="Order already submitted")
        
        # 3. Risk validation (INFRASTRUCTURE-LEVEL, not prompt-level)
        risk_check = self.risk.validate(proposal, self.positions.get_all())
        if not risk_check.passed:
            self.audit.log_rejection(proposal, risk_check)
            return ExecutionResult(status="REJECTED", reason=risk_check.reason)
        
        # 4. Circuit breaker check
        if self.circuit_breaker.is_open():
            return ExecutionResult(status="HALTED", reason="Circuit breaker open")
        
        # 5. Submit to broker
        try:
            order = self.broker.submit_order(
                symbol=proposal.instrument,
                side=proposal.action,
                order_type=proposal.order_type,
                price=proposal.entry_price,
                size=proposal.position_size_lots,
                stop_loss=proposal.stop_loss,
                take_profit=proposal.take_profits[0]["price"]
            )
            
            # 6. Set remaining TP levels and trailing stop
            self._setup_management_orders(order, proposal)
            
            # 7. Audit log
            self.audit.log_execution(proposal, order)
            
            return ExecutionResult(
                status="FILLED",
                fill_price=order.fill_price,
                slippage=order.slippage,
                order_id=order.id
            )
            
        except BrokerError as e:
            self.audit.log_error(proposal, e)
            return ExecutionResult(status="ERROR", reason=str(e))
```

### 10.4 Risk Validator (Infrastructure-Level)

```python
class RiskValidator:
    """
    Risk rules enforced at INFRASTRUCTURE level.
    Cannot be overridden by LLM agents or prompts.
    """
    
    def validate(self, proposal, open_positions) -> RiskCheck:
        checks = []
        
        # Max risk per trade
        if proposal.risk_pct > self.config.max_risk_per_trade:
            checks.append(f"Risk {proposal.risk_pct}% exceeds max {self.config.max_risk_per_trade}%")
        
        # Max daily loss
        daily_loss = self._calculate_daily_loss(open_positions)
        if daily_loss + proposal.risk_pct > self.config.max_daily_loss:
            checks.append(f"Daily loss would reach {daily_loss + proposal.risk_pct}% (max: {self.config.max_daily_loss}%)")
        
        # Max open positions
        if len(open_positions) >= self.config.max_open_positions:
            checks.append(f"Already at max positions ({self.config.max_open_positions})")
        
        # Correlation check
        correlated = self._check_correlation(proposal.instrument, open_positions)
        if correlated > self.config.max_correlated_positions:
            checks.append(f"Too many correlated positions ({correlated})")
        
        # Max drawdown check
        current_dd = self._calculate_drawdown()
        if current_dd > self.config.max_drawdown_halt:
            checks.append(f"Max drawdown reached ({current_dd}%) — TRADING HALTED")
        
        return RiskCheck(
            passed=len(checks) == 0,
            reason="; ".join(checks) if checks else "All checks passed"
        )
```

---

## 11. Broker Layer Integration

### 11.1 Broker Abstraction Layer

The system uses a **Broker Adapter** pattern to support multiple brokers/exchanges:

```
┌─────────────────────────────────────────────────────────────┐
│                    BROKER ADAPTER INTERFACE                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────┐                                   │
│  │   BrokerAdapter      │ (Abstract Interface)              │
│  │   ───────────────    │                                   │
│  │   submit_order()     │                                   │
│  │   cancel_order()     │                                   │
│  │   modify_order()     │                                   │
│  │   get_positions()    │                                   │
│  │   get_balance()      │                                   │
│  │   get_tick()         │                                   │
│  │   subscribe_ticks()  │                                   │
│  └──────────┬───────────┘                                   │
│             │                                                │
│     ┌───────┼───────┬───────────┬──────────┐                │
│     │       │       │           │          │                │
│  ┌──▼──┐ ┌──▼──┐ ┌──▼────┐ ┌───▼───┐ ┌───▼────┐           │
│  │ MT5 │ │CCXT │ │ IBKR  │ │OANDA  │ │DEX     │           │
│  │Adapter│ │Adapt│ │Adapter│ │Adapter│ │Adapter │           │
│  └─────┘ └─────┘ └───────┘ └───────┘ └────────┘           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 11.2 MT5 Adapter (Primary — FXPesa)

```python
class MT5Adapter(BrokerAdapter):
    """
    MetaTrader 5 adapter for FXPesa (forex) via ZeroMQ bridge.
    """
    
    def __init__(self, config):
        self.zmq_bridge = ZMQBridge(config.zmq_port)
        self.data_api = MetaTrader5DataAPI(config.mt5_path)
    
    def submit_order(self, symbol, side, order_type, price, size, 
                     stop_loss, take_profit) -> OrderResult:
        """Submit order via ZeroMQ to MQL5 EA."""
        request = {
            "action": "TRADE_ACTION_DEAL" if order_type == "MARKET" else "TRADE_ACTION_PENDING",
            "symbol": symbol,
            "volume": size,
            "type": "ORDER_TYPE_BUY" if side == "BUY" else "ORDER_TYPE_SELL",
            "price": price,
            "sl": stop_loss,
            "tp": take_profit,
            "deviation": 20,
            "magic": 202607,
            "comment": "AlphaStack"
        }
        
        result = self.zmq_bridge.send_order(request)
        
        return OrderResult(
            order_id=result.get("order"),
            fill_price=result.get("price", price),
            slippage=abs(result.get("price", price) - price),
            status="FILLED" if result.get("retcode") == 10009 else "REJECTED"
        )
    
    def subscribe_ticks(self, symbols, callback):
        """Subscribe to real-time tick data via MT5 API."""
        for symbol in symbols:
            self.data_api.subscribe(symbol, callback)
```

### 11.3 CCXT Adapter (Crypto)

```python
class CCXTAdapter(BrokerAdapter):
    """
    CCXT adapter for crypto exchanges (Binance, Bybit, MEXC).
    """
    
    def __init__(self, config):
        self.exchange = ccxt.binance({
            'apiKey': config.api_key,
            'secret': config.api_secret,
            'sandbox': config.sandbox
        })
    
    def submit_order(self, symbol, side, order_type, price, size, 
                     stop_loss, take_profit) -> OrderResult:
        """Submit order via CCXT."""
        params = {
            'stopLoss': {'triggerPrice': stop_loss},
            'takeProfit': {'triggerPrice': take_profit}
        }
        
        order = self.exchange.create_order(
            symbol=symbol,
            type=order_type.lower(),
            side=side.lower(),
            amount=size,
            price=price if order_type == "LIMIT" else None,
            params=params
        )
        
        return OrderResult(
            order_id=order['id'],
            fill_price=order.get('average', price),
            slippage=abs(order.get('average', price) - price) if order.get('average') else 0,
            status="FILLED" if order['status'] == 'closed' else "PENDING"
        )
```

### 11.4 Multi-Broker Routing

When the system scales to multiple brokers:

```python
class SmartOrderRouter:
    """
    Route orders to the best execution venue.
    """
    
    def route(self, proposal: TradeProposal) -> BrokerAdapter:
        """Select broker based on instrument, cost, and reliability."""
        
        candidates = []
        
        for broker in self.brokers:
            if proposal.instrument in broker.supported_instruments:
                cost = broker.estimate_cost(proposal)
                latency = broker.avg_latency_ms
                reliability = broker.uptime_pct
                
                score = (reliability * 0.5) - (cost * 0.3) - (latency * 0.2)
                candidates.append((broker, score))
        
        return max(candidates, key=lambda x: x[1])[0]
```

### 11.5 Connection Health Monitoring

```python
class BrokerHealthMonitor:
    """
    Monitor broker connectivity and failover if needed.
    """
    
    def check_health(self, broker: BrokerAdapter) -> HealthStatus:
        try:
            # Ping test
            start = time.time()
            broker.get_balance()
            latency = (time.time() - start) * 1000
            
            return HealthStatus(
                connected=True,
                latency_ms=latency,
                last_check=datetime.utcnow(),
                status="HEALTHY" if latency < 500 else "DEGRADED"
            )
        except Exception as e:
            return HealthStatus(
                connected=False,
                error=str(e),
                status="DOWN"
            )
    
    def failover(self, failed_broker, proposal):
        """Switch to backup broker."""
        backup = self.get_backup_broker(failed_broker, proposal.instrument)
        if backup:
            logger.warning(f"Failing over from {failed_broker.name} to {backup.name}")
            return backup
        else:
            logger.error("No backup broker available. Halting execution.")
            return None
```

---

## 12. Implementation Roadmap

### Phase 1: Foundation (Weeks 1–4)

```
□ Set up OpenClaw gateway with Telegram + Desktop channels
□ Create workspace: STRATEGY.md, RISK_RULES.md, TOOLS.md, MEMORY.md
□ Implement Orchestrator Agent with basic pipeline routing
□ Implement Structure Agent (Steps 2–4): regime detection, multi-TF structure
□ Implement basic Risk Gate Agent (hard-coded risk rules)
□ Set up Redis for shared state + message passing
□ Set up TimescaleDB for trade journal
□ Basic MT5 connectivity via Python API
□ Paper trading mode only
```

### Phase 2: Signal Agents (Weeks 5–8)

```
□ Implement Fundamental Agent (Step 1): news + sentiment + calendar
□ Implement SMC Agent (Step 7): OB, FVG, BOS/CHoCH detection
□ Implement Momentum Agent (Step 8): adaptive RSI, composite momentum
□ Implement S/R Module (Step 5): fractal + volume profile detection
□ Implement Liquidity Agent (Step 6): sweep detection, order flow
□ Implement Candlestick Agent (Step 9): pattern detection
□ Implement Signal Aggregator with confluence scoring
□ Agent-to-agent communication via Redis Streams
□ Validate consensus mechanism on historical data
```

### Phase 3: Execution Pipeline (Weeks 9–12)

```
□ Implement Entry Agent (Steps 10–11): entry logic, position sizing
□ Implement TP Agent (Step 13): partial closes, trailing stops
□ Implement Trade Management Agent (Steps 14–15): in-trade monitoring
□ Implement Execution Agent with MT5 ZeroMQ bridge
□ Implement Trading Engine with infrastructure-level risk validation
□ HITL checkpoints via Telegram approval buttons
□ Live demo account trading
□ Implement Monitor Agent with tiered monitoring
```

### Phase 4: Learning & Hardening (Weeks 13–16)

```
□ Implement Reflection Agent with post-trade review loop
□ Implement Journal Agent with comprehensive trade logging
□ Implement closed learning loop (signal weight adaptation)
□ Implement circuit breakers and graceful degradation
□ Implement broker failover (CCXT as backup)
□ Implement memory consolidation (daily → weekly → monthly)
□ Performance dashboard (Grafana + custom web UI)
□ Load testing and failure injection testing
□ Transition to live FXPesa cent account ($7 starting capital)
```

### Phase 5: Scale & Optimize (Weeks 17+)

```
□ Add crypto instruments via CCXT adapter
□ Implement ML models for pattern recognition (XGBoost, LSTM)
□ Implement RL agent for TP optimization
□ Add multi-broker routing
□ Implement backtesting engine that mirrors live pipeline
□ A/B testing framework for strategy variants
□ Performance attribution analysis
□ Scale infrastructure with account growth
```

---

## Appendix A: Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Orchestration | Hierarchical + Event-driven | Trading needs strict pipeline order (risk gate last) but reactive agents for speed |
| Framework | OpenClaw gateway + custom agents | Production-ready infrastructure for sessions, memory, cron, channels |
| State Management | Redis (shared state) + Redis Streams (messages) | Consistency for positions, ordered signals for audit |
| Risk Enforcement | Infrastructure-level (Trading Engine), not prompt-level | LLMs can hallucinate; risk must be enforced in code |
| Order Execution | Via ZeroMQ bridge to MQL5 EA | <1ms latency from Python to MT5 terminal |
| LLM Usage | Fast models for execution, slow models for research | Latency vs quality tradeoff |
| Memory | 3-layer (working → daily → long-term) + episodic | Mirrors human memory; enables learning from experience |
| Consensus | Weighted voting with adaptive weights | No single agent has absolute authority; weights adapt to performance |
| Failure Handling | Circuit breakers + graceful degradation | Safety-first; degrade rather than guess |
| HITL | Tiered approval (auto → alert → require) | Build trust gradually; start conservative |

---

## Appendix B: Agent Count & Resource Estimates

| Agent Type | Count | Model | Est. Tokens/Day | Est. Cost/Day |
|-----------|-------|-------|-----------------|---------------|
| Orchestrator | 1 | Reasoning-tier | 50K | $0.50 |
| Fundamental | 1 | Reasoning-tier | 30K | $0.30 |
| Structure | 1 | Fast model | 20K | $0.10 |
| Liquidity | 1 | Minimal (algo) | 5K | $0.02 |
| SMC | 1 | Fast model | 15K | $0.08 |
| Momentum | 1 | Minimal (algo) | 5K | $0.02 |
| Candlestick | 1 | Minimal (algo) | 3K | $0.01 |
| Signal Aggregator | 1 | Fast model | 10K | $0.05 |
| Entry | 1 | Fast model | 5K | $0.03 |
| Risk Gate | 1 | None (pure code) | 0 | $0.00 |
| TP | 1 | Fast model | 8K | $0.04 |
| Trade Mgmt | 1–3 | Fast model | 10K | $0.05 |
| Execution | 1 | None (pure code) | 0 | $0.00 |
| Monitor | 1 | Minimal | 5K | $0.02 |
| Reflection | 1 | Reasoning-tier | 20K | $0.20 |
| Journal | 1 | Fast model | 10K | $0.05 |
| **TOTAL** | **16–18** | | **~196K** | **~$1.47** |

**Note:** These are estimates for a single instrument running the full pipeline. Multi-instrument scaling multiplies the signal agents but shares the Orchestrator, Risk Gate, Monitor, and Journal agents.

---

## Appendix C: Technology Stack Summary

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Gateway | OpenClaw | Agent runtime, sessions, channels, cron |
| Orchestration | Custom Python (asyncio) | Pipeline routing, consensus |
| Agent Framework | OpenClaw sub-agents + custom | Agent lifecycle, tools, memory |
| State Store | Redis | Working memory, shared state |
| Message Bus | Redis Streams + Pub/Sub | Agent communication |
| Time-Series DB | TimescaleDB | Market data, trade journal |
| Vector DB | SQLite + FTS5 (or LanceDB) | Semantic search over trade history |
| MT5 Bridge | ZeroMQ (Python ↔ MQL5) | Order execution, tick data |
| Crypto Bridge | CCXT | Multi-exchange connectivity |
| ML Inference | ONNX Runtime | Fast CPU inference for models |
| Monitoring | Prometheus + Grafana | System and trading metrics |
| Delivery | Telegram, Desktop, Web | Alerts, reports, HITL approval |

---

*Document generated: 2026-07-11*
*Author: Multi-Agent Architecture Agent — Alpha Stack*
*Status: Architecture Design Complete — Ready for Implementation Review*
*Next: Review with team → Begin Phase 1 implementation*
