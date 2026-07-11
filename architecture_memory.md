# Alpha Stack — Memory Architecture

**Author:** Memory Systems Architect
**Date:** 2026-07-11
**Version:** 1.0
**Status:** Architecture Design — Ready for Implementation Review
**Dependencies:** `architecture_multi_agent.md`, `architecture_database.md`, `research_03_loop_multiagent_systems.md`, `research_14_framework_analysis.md`

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Design Principles](#2-design-principles)
3. [Memory Layer 1: Working Memory](#3-memory-layer-1-working-memory)
4. [Memory Layer 2: Short-Term Memory](#4-memory-layer-2-short-term-memory)
5. [Memory Layer 3: Long-Term Memory](#5-memory-layer-3-long-term-memory)
6. [Memory Layer 4: Episodic Memory](#6-memory-layer-4-episodic-memory)
7. [Agent Memory Access & Update Protocol](#7-agent-memory-access--update-protocol)
8. [Memory Sharing Between Agents](#8-memory-sharing-between-agents)
9. [Closed Learning Loop (Hermes-Inspired)](#9-closed-learning-loop-hermes-inspired)
10. [How Memory Drives Strategy Improvement](#10-how-memory-drives-strategy-improvement)
11. [Semantic Search Over Trade History](#11-semantic-search-over-trade-history)
12. [Memory Cleanup & Archival](#12-memory-cleanup--archival)
13. [Memory Observability & Debugging](#13-memory-observability--debugging)
14. [Implementation Roadmap](#14-implementation-roadmap)

---

## 1. Executive Summary

Alpha Stack's memory system is a **four-layer architecture** modeled on how human traders develop expertise: raw perception fades, recent context persists, durable knowledge accumulates, and vivid trade episodes remain retrievable indefinitely. The system draws on three sources:

- **OpenClaw's memory model** — daily notes, long-term MEMORY.md, dreaming/consolidation
- **Hermes's closed learning loop** — auto-created skills from experience that compound over time
- **Cognitive science** — working memory (Baddeley), episodic memory (Tulving), memory consolidation (sleep/wake cycles)

The memory system serves a dual purpose: **runtime context** (what agents need to make decisions right now) and **learning substrate** (what the system needs to improve over time). Every trade generates a memory trace. The Reflection Agent periodically consolidates those traces into durable knowledge. Over hundreds of trades, the system develops instrument-specific expertise that no static strategy can match.

**Key innovation:** Memory is not passive storage. It is an **active participant in decision-making** — agents query past episodes before entering trades, the Signal Aggregator weights signals by historical reliability, and the Reflection Agent autonomously updates strategy parameters based on accumulated evidence.

---

## 2. Design Principles

| Principle | Rationale |
|-----------|-----------|
| **Memory is architecture, not an afterthought** | Every agent interaction produces a memory trace; the memory system defines what the system learns |
| **Four layers, clear ownership** | Each layer has a defined owner (who writes), TTL (how long it lives), and access policy (who reads) |
| **Write-heavy, read-critical** | Agents write frequently (every signal, every tick observation); reads must be sub-millisecond for hot paths |
| **Semantic over syntactic** | Agents don't search by exact key — they search by meaning ("trades similar to this setup") |
| **Decay mimics human forgetting** | Unused memories lose importance; frequently-accessed memories strengthen (spaced repetition) |
| **Episodes are the learning unit** | A single trade episode contains everything needed to learn: context, signals, reasoning, outcome |
| **Consolidation is scheduled, not ad-hoc** | Memory consolidation runs on a defined cadence (post-trade, daily, weekly) — never left to chance |
| **Audit everything** | Every memory write is timestamped, attributed to an agent, and traceable to its source |

---

## 3. Memory Layer 1: Working Memory

### 3.1 Purpose

Working memory holds **what is happening right now** — the current tick, active positions, in-progress pipeline state, and the latest signals from each agent. It is the sensory register of the trading system: volatile, fast, and replaced on every new input.

### 3.2 Contents

```
WORKING MEMORY
├── Market State
│   ├── Latest tick per symbol: {bid, ask, spread, time}
│   ├── Current (unclosed) candle per symbol/timeframe
│   ├── Latest order book snapshot (top 20 levels)
│   └── Current session state: {asian|london|new_york|overlap|closed}
│
├── Agent State
│   ├── Latest signal from each agent per symbol
│   ├── Current confluence score per symbol
│   ├── Pipeline progress: which agents have reported for current cycle
│   └── Agent health heartbeats (last seen, inference latency)
│
├── Position State
│   ├── All open positions with live P&L
│   ├── Current margin utilization
│   ├── Active stop-loss and take-profit levels
│   └── Trailing stop state
│
├── Risk State
│   ├── Daily P&L (realized + unrealized)
│   ├── Current drawdown from high-water mark
│   ├── Position count vs limit
│   └── Circuit breaker state: closed | open | half_open
│
└── Pipeline State
    ├── Current analysis cycle: instrument, phase, start time
    ├── Pending trade proposals awaiting Risk Gate
    └── HITL checkpoints awaiting human response
```

### 3.3 Storage & Performance

| Property | Value |
|----------|-------|
| **Storage** | Redis 7 (in-memory) |
| **TTL** | Session-scoped; tick data expires in 60s, signals in 5m, positions persist until closed |
| **Write latency** | <0.1ms (Redis SET) |
| **Read latency** | <0.1ms (Redis GET) |
| **Write frequency** | Every tick (~100-500ms per symbol), every signal, every order event |
| **Read frequency** | Every agent invocation, every risk check |
| **Persistence** | AOF + RDB snapshots; rebuilds from PostgreSQL + broker API on restart |

### 3.4 Key Patterns

```
# Latest tick — expires if stale
tick:{symbol}                   → Hash {bid, ask, last, spread, mid, time, source}
                                  TTL: 60s

# Current candle — replaced on each tick within the candle
ohlcv:{symbol}:{timeframe}      → Hash {open, high, low, close, volume, time}

# Latest signal per agent — expires if agent stops producing
signal:{agent_id}:{symbol}      → Hash {direction, confidence, score, time, reasoning}
                                  TTL: 5m

# Aggregated confluence — updated by Signal Aggregator
confluence:{symbol}             → Hash {score, direction, agents_voted, timestamp}

# Current regime — set by Structure Agent
regime:{symbol}                 → Hash {regime, confidence, time}

# Agent observations — capped rolling list (last 100)
agent:{agent_id}:observations   → List (LPUSH, LTRIM 0 99)

# Pattern cache — rebuilt every candle close
patterns:{symbol}               → Hash {ob_high, ob_low, fvg_high, fvg_low, bos_direction, ...}

# Indicator cache — shared across agents
indicators:{symbol}:{timeframe} → Hash {rsi, atr, macd, ema_20, ema_50, sma_200, ...}
```

### 3.5 Working Memory Lifecycle

```
TICK ARRIVES
  │
  ▼
1. Ingestion writes tick:{symbol} (TTL 60s)
  │
  ▼
2. Updates ohlcv:{symbol}:{timeframe} (current candle)
  │
  ▼
3. If candle closes:
   a. Finalize candle → write to PostgreSQL market_data
   b. Trigger signal agents (SMC, Momentum, Candlestick)
   c. Rebuild patterns:{symbol} and indicators:{symbol}:{tf}
  │
  ▼
4. Signal agents write signal:{agent_id}:{symbol}
  │
  ▼
5. Signal Aggregator reads all signals → writes confluence:{symbol}
  │
  ▼
6. If confluence ≥ threshold → spawn Entry Agent with working memory snapshot
  │
  ▼
7. Working memory state is snapshot into the trade episode (Layer 4)
```

---

## 4. Memory Layer 2: Short-Term Memory

### 4.1 Purpose

Short-term memory holds **today's context** — what happened in this trading session, recent trades, news events, and session-level observations. It bridges the gap between ephemeral working memory and permanent long-term memory. It answers: "What has the market done today, and what has the system done about it?"

### 4.2 Contents

```
SHORT-TERM MEMORY (Today + Yesterday)
├── Market Context
│   ├── Today's OHLCV candles (all timeframes, all symbols)
│   ├── Session high/low/range for each symbol
│   ├── Key levels tested today (S/R, order blocks, FVGs)
│   ├── Volatility profile (ATR today vs 20-day average)
│   └── Regime changes detected today
│
├── News & Events
│   ├── Today's economic calendar events + outcomes
│   ├── Breaking news events with sentiment scores
│   ├── Central bank communications
│   └── Social sentiment shifts
│
├── Trade Activity
│   ├── Today's signals generated (all agents, all symbols)
│   ├── Today's trades: entries, exits, P&L
│   ├── Pending orders and their status
│   ├── Today's daily P&L running total
│   └── HITL decisions made today
│
├── Agent Observations
│   ├── Lessons from today's Reflection Agent runs
│   ├── Pattern detections and their outcomes
│   ├── Signal quality notes ("SMC agent detected 3 OBs, 2 were valid")
│   └── Anomaly observations ("Unusual volume spike at London open")
│
└── System State
    ├── Agent restarts or failures today
    ├── Data source switches or outages
    ├── Circuit breaker events
    └── Configuration changes
```

### 4.3 Storage & Performance

| Property | Value |
|----------|-------|
| **Storage** | PostgreSQL (structured) + File-based (narrative, `memory/YYYY-MM-DD.md`) |
| **TTL** | 30 days in hot storage; archived to cold storage after |
| **Write latency** | <5ms (PostgreSQL INSERT) |
| **Read latency** | <10ms (indexed queries) |
| **Write frequency** | Every signal, every trade, every news event, every session observation |
| **Read frequency** | Every agent invocation loads today's context; Reflection Agent reads recent days |
| **Persistence** | Full ACID; survives restarts |

### 4.4 Daily Memory File Structure

```markdown
# memory/2026-07-11.md — Daily Trading Notes

## Session Context
- **Date:** Friday, July 11, 2026
- **Regime:** EUR/USD trending bull (confidence 0.82), BTC/USDT ranging
- **Volatility:** EUR/USD ATR(14) at 85 pips (above 20-day avg of 72)
- **Key Events:** US CPI at 13:30 UTC (actual 2.9% vs 3.1% expected — beat)

## Signals Generated (12 total)
- 08:15 UTC — SMC Agent: Bullish OB on EUR/USD H4 at 1.0835-1.0850 (strength 0.82)
- 08:15 UTC — Momentum Agent: RSI oversold on EUR/USD H1 (RSI=28)
- 08:16 UTC — Confluence: EUR/USD score 85 (STRONG BUY)
- 08:17 UTC — Entry Agent: Limit buy 1.0842, SL 1.0810, TP1 1.0887
- 08:18 UTC — Risk Gate: APPROVED (risk 1.5%, within limits)
- ... (more signals)

## Trades (2 executed)
### Trade 1: EUR/USD Long
- Entry: 1.0843 (limit at 1.0842, 1 pip slippage)
- Exit: 1.0888 (TP1 hit, +45 pips, +$6.75)
- Duration: 3h 42m
- Grade: A-
- Notes: Perfect OB bounce. London session timing optimal.

### Trade 2: BTC/USDT Short
- Entry: 67,450 (market order)
- Exit: 67,100 (trailing stop, +$3.50)
- Duration: 1h 15m
- Grade: B
- Notes: Good entry but exited too early on H1 noise.

## Daily Summary
- Gross P&L: +$10.25
- Win rate: 2/2 (100%)
- Lessons: Wider trailing stops in trending regimes.
```

### 4.5 Short-Term → Long-Term Promotion

At the end of each trading day, the **Journal Agent** compiles short-term memory into structured records:

```
END OF DAY (triggered by cron at session close)
  │
  ▼
1. Compile daily_performance record:
   - Total trades, win rate, P&L, max drawdown
   - Strategy breakdown
   - News events that impacted trading
  │
  ▼
2. Update v_strategy_performance materialized view
  │
  ▼
3. For each closed trade:
   a. Create/update trade_episodes record with full context
   b. Update pattern_reliability for patterns used
   c. Feed trade to Reflection Agent for lesson extraction
  │
  ▼
4. Archive memory/YYYY-MM-DD.md (remains accessible for 30 days)
  │
  ▼
5. Reflection Agent runs post-day review:
   - Compare predicted vs actual outcomes
   - Extract durable lessons → write to lessons table
   - Update signal_weights if evidence warrants
   - Promote insights to EDGE_NOTES.md
```

---

## 5. Memory Layer 3: Long-Term Memory

### 5.1 Purpose

Long-term memory holds **what the system has learned** — distilled knowledge that persists across sessions, instruments, and market conditions. It is the system's expertise: strategy parameters calibrated by experience, pattern reliability statistics, market insights, and actionable rules. This is the Hermes-inspired "compounding" layer — the system gets smarter over time.

### 5.2 Contents

```
LONG-TERM MEMORY (Permanent)
├── Strategy Knowledge
│   ├── strategy_parameters — Version-controlled strategy configs
│   ├── signal_weights — Adaptive weights per agent/symbol/strategy
│   └── v_strategy_performance — Aggregated performance metrics
│
├── Pattern Knowledge
│   ├── pattern_reliability — Win rates by pattern type, symbol, regime, session
│   └── pattern_evolution — How pattern reliability changes over time
│
├── Market Knowledge
│   ├── regime_history — Regime transitions and their triggers
│   ├── correlation_matrix — Cross-pair correlations (updated weekly)
│   └── volatility_profiles — Volatility characteristics per symbol/session
│
├── Distilled Wisdom
│   ├── lessons — Actionable rules from reflection ("When X, do Y because Z")
│   ├── agent_memories — Per-agent observations, patterns, and insights
│   └── EDGE_NOTES.md — Curated market insights (human-readable)
│
└── Performance Archive
    ├── daily_performance — Daily P&L and stats (permanent)
    ├── trades — All completed trades (permanent)
    └── journal_entries — Trade journals and daily summaries (permanent)
```

### 5.3 Storage & Performance

| Property | Value |
|----------|-------|
| **Storage** | PostgreSQL + pgvector (for embeddings) |
| **TTL** | Permanent (with periodic pruning of stale entries) |
| **Write latency** | <10ms (PostgreSQL INSERT/UPDATE) |
| **Read latency** | <10ms (indexed), <50ms (vector similarity) |
| **Write frequency** | Post-trade (Reflection Agent), daily (Journal Agent), weekly (deep review) |
| **Read frequency** | Every trade decision (pattern lookup, lesson check), every agent invocation (weight lookup) |
| **Persistence** | Full ACID; backed up daily |

### 5.4 The Five Knowledge Stores

#### 5.4.1 Strategy Parameters

Version-controlled strategy configurations. Every parameter change is recorded with its reason and the performance before/after.

```sql
-- Every change creates a new version; old versions are preserved
strategy_parameters (
    strategy_id, version, parameters (JSONB),
    change_reason, approved_by, performance_before (JSONB),
    active BOOLEAN
)
```

**Access pattern:** Agents read `active = TRUE` for their strategy. Reflection Agent proposes changes; human approves for parameter changes, auto-approved for signal weight adjustments within bounds.

#### 5.4.2 Signal Weights

Adaptive weights that reflect each agent's actual predictive power per symbol, per strategy. Updated by the Reflection Agent after every trade.

```sql
signal_weights (
    strategy_id, agent_id, symbol,
    weight (current), base_weight (original),
    accuracy_50 (last 50 signals), accuracy_total,
    total_signals, last_adjustment, adjustment_reason
)
```

**Update rule:**
```python
def update_signal_weight(agent_id, symbol, trade_outcome):
    weight = get_current_weight(agent_id, symbol)
    accuracy = get_recent_accuracy(agent_id, symbol, window=50)

    # Blend recent and historical (70/30)
    blended = 0.7 * accuracy + 0.3 * weight.accuracy_total

    # Adjust weight (bounded 0.05–0.40, max change ±0.03 per trade)
    new_weight = clip(weight.current + sign(blended - 0.5) * 0.01, 0.05, 0.40)

    # Never change more than ±0.03 per trade to prevent oscillation
    new_weight = clip(new_weight, weight.current - 0.03, weight.current + 0.03)

    update_weight(agent_id, symbol, new_weight, reason=f"Trade {trade_id}: {'win' if trade_outcome else 'loss'}")
```

#### 5.4.3 Pattern Reliability

Historical win rates for every pattern type, broken down by symbol, timeframe, regime, and session. This is the statistical backbone of confluence scoring.

```sql
pattern_reliability (
    pattern_type, pattern_subtype, symbol, timeframe,
    regime, session,
    total_occurrences, successful, failed,
    win_rate (computed), avg_rr, avg_duration_hours,
    confidence_interval
)
```

**Example query:** "What is the win rate of bullish order blocks on EUR/USD H4 during London session in trending markets?"

```sql
SELECT win_rate, avg_rr, total_occurrences, confidence_interval
FROM pattern_reliability
WHERE pattern_type = 'order_block'
  AND pattern_subtype = 'bullish_ob'
  AND symbol = 'EUR/USD'
  AND timeframe = '4h'
  AND session = 'london'
  AND regime = 'trending_bull';
-- Result: win_rate=0.80, avg_rr=2.1, total_occurrences=15, confidence_interval=0.72
```

#### 5.4.4 Lessons

Actionable rules distilled from trade experience. Each lesson has supporting evidence (trade IDs), a confidence score, and tracking of how often it's been applied successfully.

```sql
lessons (
    lesson_type, title, description,
    rule (TEXT), -- "When X, do Y because Z"
    symbol, strategy_id, regime, timeframe,
    supporting_trades (UUID[]), contradicting_trades (UUID[]),
    confidence, times_applied, success_when_applied,
    estimated_impact, status, embedding (VECTOR)
)
```

**Lesson lifecycle:**
```
TRADE COMPLETED
  │
  ▼
Reflection Agent extracts lesson candidate
  │
  ▼
If similar lesson exists (semantic search > 0.85):
  → Strengthen existing lesson (add trade to supporting_trades, increase confidence)
  │
  ▼
If new lesson:
  → Create with confidence=0.5, status='active'
  → After 5+ supporting trades: confidence increases
  → After contradicting trades: confidence decreases
  → If confidence < 0.2: status='archived'
```

#### 5.4.5 Agent Memories

Per-agent distilled knowledge — observations, patterns, and insights that don't fit neatly into structured tables. This is the Hermes "skill memory" pattern applied to trading.

```sql
agent_memories (
    agent_id, memory_type ('lesson'|'observation'|'pattern'|'rule'|'insight'),
    title, content, content_structured (JSONB),
    symbol, timeframe, regime, strategy_id,
    importance (0-1), access_count, decay_rate,
    source_trade_ids, source_type,
    embedding (VECTOR), active BOOLEAN
)
```

**Memory types:**
- **lesson:** "H4 order blocks in trending markets have 80% win rate"
- **observation:** "EUR/USD tends to sweep Asian range before London open"
- **pattern:** "When RSI divergence coincides with FVG, probability increases by 15%"
- **rule:** "Never trade 30 minutes before NFP"
- **insight:** "The SMC agent's BOS detection is most reliable on H4 timeframe"

### 5.5 Long-Term Memory File System

```
workspace/
├── STRATEGY.md          # Active strategy parameters (human-readable)
├── EDGE_NOTES.md        # Curated market insights (auto-maintained by Reflection Agent)
├── LESSONS.md           # Top lessons by confidence (auto-maintained)
├── MARKET_STRUCTURE.md  # Current regime, correlations, volatility state
└── memory/
    └── strategy/
        ├── STRATEGIES.md      # Strategy parameter history
        ├── EDGE_NOTES.md      # Distilled market insights
        ├── LESSONS.md         # Mistakes and corrections
        └── MARKET_STRUCTURE.md # Current regime state
```

**EDGE_NOTES.md example:**
```markdown
# Edge Notes — Distilled Market Insights

## EUR/USD
- H4 order blocks during London session in trending markets: 80% win rate (15 trades)
- Asian range sweep before London open occurs 65% of the time
- CPI surprises >0.2% cause 40-60 pip moves in 30 minutes
- When multi-TF alignment score >0.75 and regime confidence >0.8: use 1.5x TP targets

## BTC/USDT
- Funding rate >0.05% correlates with local tops (72% accuracy)
- Weekend liquidity gaps cause 2x normal slippage on market orders
- Whale exchange inflows >1000 BTC precede 5%+ drops within 48h (68% accuracy)

## General
- London-NY overlap has highest win rate across all pairs (62% vs 54% average)
- Trades with confluence score >80 have 3x better R:R than score 60-80 trades
- Trailing stops with ATR×3.0 outperform ATR×2.5 in trending regimes by 0.3R avg
```

---

## 6. Memory Layer 4: Episodic Memory

### 6.1 Purpose

Episodic memory stores **complete trade episodes** — the full context of a trade from signal generation through outcome and reflection. Each episode is a self-contained learning unit: it captures what the system saw, what it decided, why, and what happened. This is the raw material for the closed learning loop.

### 6.2 What Makes an Episode

An episode is not just an order record. It is the **entire decision context** frozen at the moment of the trade:

```
TRADE EPISODE
├── Identity
│   ├── episode_id (UUID)
│   ├── trade_id (FK → trades)
│   └── created_at
│
├── Market Context (at entry)
│   ├── symbol, timeframe, session, regime
│   ├── volatility_regime (low|normal|high|extreme)
│   ├── key_levels (S/R, order blocks, FVGs active at entry)
│   └── news_context (recent events, sentiment)
│
├── Multi-Agent Signals (at entry)
│   ├── signals_snapshot (JSONB) — complete output from every agent
│   ├── confluence_score
│   ├── entry_reasoning (natural language)
│   └── agent_votes (who voted what, with confidence)
│
├── Trade Details
│   ├── entry_price, exit_price, size
│   ├── stop_loss, take_profit_levels
│   ├── duration, bars_held
│   └── gross_pnl, net_pnl, risk_reward_actual
│
├── Outcome Analysis
│   ├── outcome (win|loss|breakeven)
│   ├── max_drawdown, max_profit (intra-trade)
│   ├── close_reason (tp_hit|sl_hit|manual|trailing|time_exit)
│   └── grade (A+|A|B|C|D|F)
│
├── Reflection
│   ├── what_worked (TEXT[])
│   ├── what_failed (TEXT[])
│   ├── missing_signals (TEXT[])
│   ├── lessons_learned (TEXT[])
│   └── discipline_score (1-10)
│
├── Embeddings (for semantic search)
│   ├── context_embedding (VECTOR 1536) — encodes market conditions
│   ├── reasoning_embedding (VECTOR 1536) — encodes decision reasoning
│   └── tags (TEXT[]) — for filtered search
│
└── Cross-References
    ├── similar_episodes (computed periodically)
    ├── lessons_generated (FK → lessons)
    └── strategy_changes_triggered
```

### 6.3 Storage

| Property | Value |
|----------|-------|
| **Primary store** | `trade_episodes` table (PostgreSQL) |
| **Embedding store** | pgvector columns on `trade_episodes` |
| **Linked data** | `trades`, `orders`, `journal_entries`, `screenshots` |
| **TTL** | Permanent |
| **Size** | ~2-5 KB per episode (excluding embeddings); ~8 KB with embeddings |

### 6.4 Episode Creation Flow

```
TRADE CLOSED
  │
  ▼
Journal Agent (within 1 hour):
  │
  ├── 1. Gather all context:
  │      - Read signals_snapshot from Redis Streams (stream:signals, XRANGE by trade_id)
  │      - Read confluence:{symbol} at time of entry
  │      - Read regime:{symbol} at time of entry
  │      - Read news_events near entry time
  │      - Read orderbook state at entry
  │
  ├── 2. Compute embeddings:
  │      - context_embedding = embed(symbol + regime + signals + conditions)
  │      - reasoning_embedding = embed(entry_reasoning + agent_votes)
  │
  ├── 3. Write trade_episodes record
  │
  ├── 4. Trigger Reflection Agent
  │
  └── 5. Update trade record with episode_id
```

### 6.5 Why Episodes Matter

Episodes are the **atom of learning**. Without complete episodes, the system can only learn from aggregate statistics ("win rate is 60%"). With episodes, it can learn from **specific contexts** ("in this exact type of setup, with these signals, during this session, the win rate is 85%").

This enables:
- **Semantic search:** "Find trades similar to the current setup" → retrieve episodes with similar context embeddings
- **Pattern discovery:** Cluster episodes by outcome to find hidden patterns
- **Strategy attribution:** Which agent's signals were most predictive in which conditions?
- **Counterfactual analysis:** "What would have happened if we had used wider stops?"

---

## 7. Agent Memory Access & Update Protocol

### 7.1 Access Matrix

Every agent has a defined memory access profile. This is not just documentation — it is enforced at the infrastructure level (Redis ACLs, PostgreSQL row-level security, API middleware).

| Agent | Working Memory | Short-Term | Long-Term | Episodic | Writes To |
|-------|---------------|------------|-----------|----------|-----------|
| **Orchestrator** | R/W | R | R | R | Working (pipeline state) |
| **Fundamental** | R | R/W | R | R | Short-term (news observations) |
| **Structure** | R/W | R/W | R | R | Working (regime, structure), Short-term (session notes) |
| **Liquidity** | R | R | R | — | Working (liquidity map) |
| **SMC** | R | R | R | R | Working (patterns) |
| **Momentum** | R | R | R | — | Working (indicators) |
| **Candlestick** | R | R | R | — | Working (patterns) |
| **Signal Aggregator** | R/W | R | R | R | Working (confluence score) |
| **Entry** | R/W | R | R | R | Working (entry order) |
| **Risk Gate** | R/W | R | R | R | Working (risk decision) |
| **TP** | R/W | R | R | R | Working (TP levels) |
| **Trade Mgmt** | R/W | R | R | R | Working (management actions) |
| **Execution** | R/W | R | — | — | Working (order result) |
| **Monitor** | R/W | R | R | — | Working (health, alerts) |
| **Reflection** | R | R/W | R/W | R/W | Long-term (lessons, weights), Short-term (review notes) |
| **Journal** | R | R/W | R/W | R/W | Short-term (daily notes), Long-term (journal entries), Episodic (episodes) |

### 7.2 Read Protocol

When an agent starts its work, it loads context in a defined order:

```
AGENT SPAWN
  │
  ▼
1. Load BOOTSTRAP.md (strategy parameters, risk rules, tool config)
  │
  ▼
2. Load working memory snapshot:
   - Current regime:{symbol}
   - Current confluence:{symbol}
   - Current positions (if relevant)
   - Latest signals from upstream agents
  │
  ▼
3. Load short-term context:
   - Today's session state and key levels
   - Recent trades on this symbol
   - Today's news events
  │
  ▼
4. Load long-term context (if decision-making agent):
   - Pattern reliability for current setup type
   - Signal weight for this agent/symbol
   - Relevant lessons (by symbol + regime match)
   - Similar past episodes (semantic search)
  │
  ▼
5. Execute analysis with full context
```

**Critical:** Steps 2-4 happen in <50ms total (Redis for working memory, PostgreSQL indexed queries for short/long-term). Agents never block on memory reads.

### 7.3 Write Protocol

Memory writes follow a strict protocol to prevent corruption and ensure consistency:

```
AGENT PRODUCES OUTPUT
  │
  ▼
1. Write to working memory (Redis):
   - signal:{agent_id}:{symbol} with TTL
   - Update any relevant caches
   │
   ├── CRITICAL PATH: <1ms, synchronous
   │
   ▼
2. Emit to Redis Stream (durable):
   - stream:signals (for pipeline routing and audit)
   - stream:orders (for execution events)
   │
   ├── NEAR-REAL-TIME: <5ms, asynchronous
   │
   ▼
3. Write to short-term memory (PostgreSQL):
   - journal_entries, news_events, signals
   │
   ├── BACKGROUND: <50ms, async batch
   │
   ▼
4. If trade completed → trigger episode creation (Journal Agent)
   │
   ├── DEFERRED: runs within 1 hour
   │
   ▼
5. If episode created → trigger Reflection Agent
   │
   ├── DEFERRED: runs within 1 hour
   │
   ▼
6. Reflection Agent writes to long-term memory:
   - lessons, agent_memories, signal_weights, pattern_reliability
   │
   ├── DEFERRED: runs within 1 hour
```

### 7.4 Memory Injection into Agent Prompts

Every agent receives memory context as part of its system prompt. This is not optional — it is how agents "remember."

```python
def build_agent_prompt(agent_id, symbol, context):
    prompt = []

    # 1. Strategy parameters (from BOOTSTRAP.md / strategy_parameters)
    prompt.append(load_strategy_config(agent_id))

    # 2. Working memory snapshot
    prompt.append(f"""
## Current Market State
- Regime: {context.regime} (confidence: {context.regime_confidence})
- Session: {context.session}
- Confluence Score: {context.confluence_score}/100
- Active Positions: {context.open_positions}
- Daily P&L: {context.daily_pnl}
""")

    # 3. Short-term context
    prompt.append(f"""
## Today's Context
- Key levels tested: {context.levels_tested_today}
- Recent signals: {context.recent_signals}
- News events: {context.today_news}
""")

    # 4. Long-term knowledge (compressed)
    relevant_lessons = search_lessons(symbol, context.regime, max_results=3)
    pattern_stats = get_pattern_reliability(context.current_pattern, symbol)
    similar_trades = search_similar_episodes(context, max_results=3)

    prompt.append(f"""
## Relevant Knowledge
### Lessons
{format_lessons(relevant_lessons)}

### Pattern Statistics
{format_pattern_stats(pattern_stats)}

### Similar Past Trades
{format_similar_trades(similar_trades)}
""")

    return "\n".join(prompt)
```

---

## 8. Memory Sharing Between Agents

### 8.1 Sharing Patterns

Agents share memory through three mechanisms, each suited to different needs:

```
┌─────────────────────────────────────────────────────────────────┐
│                    MEMORY SHARING PATTERNS                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  PATTERN 1: SHARED STATE (Redis)                                │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Multiple agents read the same key simultaneously         │  │
│  │  Example: regime:{symbol} read by all signal agents       │  │
│  │  Example: position:{id} read by Risk Gate + Trade Mgmt    │  │
│  │  Latency: <0.1ms                                          │  │
│  │  Consistency: Last-write-wins (acceptable for signals)    │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  PATTERN 2: MESSAGE PASSING (Redis Streams)                     │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Agent produces → Stream → Consumer reads                 │  │
│  │  Example: SMC Agent writes OB detection → Signal Agg      │  │
│  │  Example: Execution writes fill → Journal Agent           │  │
│  │  Latency: <5ms                                            │  │
│  │  Consistency: Ordered, durable, replayable                │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  PATTERN 3: SHARED KNOWLEDGE (PostgreSQL)                       │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  All agents read from the same long-term tables           │  │
│  │  Example: pattern_reliability read by all signal agents   │  │
│  │  Example: signal_weights read by Signal Aggregator        │  │
│  │  Example: lessons read by all decision-making agents      │  │
│  │  Latency: <10ms                                           │  │
│  │  Consistency: ACID (read-committed)                       │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 8.2 What Agents Share (and What They Don't)

| Shared By | Shared With | What | Mechanism |
|-----------|------------|------|-----------|
| Structure Agent | All signal agents | Market regime, session state | Redis Hash (shared state) |
| Fundamental Agent | All signal agents | Event risk score, sentiment | Redis Hash (shared state) |
| Signal agents | Signal Aggregator | Individual signals | Redis Stream (message passing) |
| Signal Aggregator | Entry Agent, Risk Gate | Confluence score, trade proposal | Redis Stream (message passing) |
| Risk Gate | Execution Agent | Approval/rejection decision | Redis Stream (message passing) |
| Execution Agent | Journal, Monitor, Trade Mgmt | Fill result, slippage | Redis Stream (message passing) |
| Reflection Agent | All agents | Updated signal weights, lessons | PostgreSQL (shared knowledge) |
| Journal Agent | All agents | Trade episodes, pattern stats | PostgreSQL (shared knowledge) |
| **Human** | All agents | Strategy parameters, risk rules | Workspace files (BOOTSTRAP.md) |

### 8.3 What Is NOT Shared

Certain memory is agent-private to prevent information leakage and maintain analytical independence:

| Agent | Private Memory | Why |
|-------|---------------|-----|
| Each signal agent | Its own reasoning trace | Prevents anchoring bias — agents should reach independent conclusions |
| Risk Gate | Internal risk calculations | Prevents gaming — agents shouldn't optimize around risk rules |
| Fundamental | Raw news processing | Prevents information cascades — other agents shouldn't front-run news analysis |

**Exception:** After a trade closes, all reasoning traces are shared (via the episode) for reflection and learning. Privacy is only during the decision process, not after.

### 8.4 Memory Synchronization

When multiple agents write to shared state, conflicts are resolved by priority:

```
CONFLICT RESOLUTION:
  1. Position state: Only Execution Agent and Trade Mgmt Agent write
     → Execution Agent has priority for order events
     → Trade Mgmt Agent has priority for management actions
     → Risk Gate can force-write (flatten all) — highest priority

  2. Regime state: Only Structure Agent writes
     → No conflict possible (single writer)

  3. Signal weights: Only Reflection Agent writes
     → No conflict possible (single writer)

  4. Confluence score: Only Signal Aggregator writes
     → No conflict possible (single writer)
```

### 8.5 Cross-Session Memory

When an agent session ends (daily reset, task completion), its working memory is preserved:

```
SESSION END
  │
  ▼
1. Agent observations → agent:{agent_id}:observations (Redis, survives session)
  │
  ▼
2. Agent decisions → agent:{agent_id}:decisions (Redis, survives session)
  │
  ▼
3. Any pending insights → agent_memories table (PostgreSQL, permanent)
  │
  ▼
4. Session transcript → archived (OpenClaw session persistence)
  │
  ▼
5. Next session loads: recent observations + relevant memories
```

---

## 9. Closed Learning Loop (Hermes-Inspired)

### 9.1 The Core Loop

The closed learning loop is Alpha Stack's mechanism for **autonomous strategy improvement**. Inspired by Hermes's pattern where agents create reusable skills from experience, Alpha Stack's Reflection Agent automatically extracts lessons from trade outcomes and feeds them back into the decision-making process.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CLOSED LEARNING LOOP                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    │
│   │  TRADE   │───▶│ REFLECT  │───▶│  EXTRACT │───▶│  UPDATE  │    │
│   │ EXECUTED │    │ ON TRADE │    │  LESSONS │    │ KNOWLEDGE│    │
│   └──────────┘    └──────────┘    └──────────┘    └─────┬────┘    │
│        ▲                                                 │         │
│        │                                                 │         │
│        │              ┌──────────┐    ┌──────────┐       │         │
│        └──────────────│  APPLY   │◀───│  STORE   │◀──────┘         │
│                       │ KNOWLEDGE│    │ LONG-TERM│                  │
│                       └──────────┘    └──────────┘                  │
│                                                                      │
│   This loop runs for EVERY closed trade.                             │
│   Over 100 trades, the system develops calibrated expertise.        │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 9.2 Loop Phases in Detail

#### Phase 1: TRADE EXECUTED

Every trade produces a memory trace in working memory. The Journal Agent captures:
- All signals that contributed to the trade
- The confluence score and reasoning
- The execution details (fill price, slippage, timing)
- The market context (regime, session, volatility)

#### Phase 2: REFLECT ON TRADE

The Reflection Agent (triggered within 1 hour of trade close) performs a structured comparison:

```
REFLECTION PROTOCOL:

1. COMPARE: Predicted vs Actual
   ┌────────────────────────────────────────────────────┐
   │ PREDICTED: "Price will bounce from H4 OB at       │
   │ 1.0835-1.0850, targeting previous high at 1.0900"  │
   │                                                     │
   │ ACTUAL: "Price bounced from 1.0838 (3 pips above  │
   │ OB low), reached 1.0888 (TP1), pulled back, then   │
   │ continued to 1.0910 (above original TP2 target)"    │
   │                                                     │
   │ GAP: TP2 was set too conservatively for trending    │
   │ market. Missed +22 pips of profit.                  │
   └────────────────────────────────────────────────────┘

2. ATTRIBUTE: Which signals were predictive?
   ┌────────────────────────────────────────────────────┐
   │ ✓ SMC Agent: OB detection was accurate (price      │
   │   bounced from exact level) — CONFIRMED             │
   │ ✓ Structure Agent: Bullish bias correct — CONFIRMED │
   │ ✓ Momentum Agent: RSI oversold signal confirmed —   │
   │   price did bounce from oversold territory          │
   │ ⚠ TP Agent: Targets too conservative for trending   │
   │   regime — NEEDS ADJUSTMENT                         │
   │ ✓ Risk Gate: 1.5% risk was appropriate — CONFIRMED  │
   └────────────────────────────────────────────────────┘

3. IDENTIFY: What was missing?
   ┌────────────────────────────────────────────────────┐
   │ Missing: Regime confidence was 0.82 (trending).    │
   │ In high-confidence trending regimes, TP targets    │
   │ should be extended by 1.5x. This rule doesn't      │
   │ exist yet in the knowledge base.                    │
   └────────────────────────────────────────────────────┘
```

#### Phase 3: EXTRACT LESSONS

The Reflection Agent generates structured lessons from the analysis:

```python
# Lesson extraction algorithm
def extract_lessons(trade_episode, reflection_output):
    lessons = []

    # 1. Check if a similar lesson already exists
    existing = search_similar_lessons(
        query=reflection_output.key_insight,
        symbol=trade_episode.symbol,
        regime=trade_episode.regime,
        threshold=0.85
    )

    if existing:
        # Strengthen existing lesson
        existing.supporting_trades.append(trade_episode.trade_id)
        existing.confidence = min(1.0, existing.confidence + 0.05)
        existing.times_applied += 1
        update_lesson(existing)
    else:
        # Create new lesson
        lesson = Lesson(
            type='strategy',
            title=reflection_output.key_insight,
            description=reflection_output.detailed_analysis,
            rule=reflection_output.actionable_rule,
            symbol=trade_episode.symbol,
            regime=trade_episode.regime,
            supporting_trades=[trade_episode.trade_id],
            confidence=0.5,  # Starts at 0.5, grows with evidence
            source_type='reflection'
        )
        create_lesson(lesson)

    # 2. Update pattern reliability
    for pattern in trade_episode.patterns_used:
        update_pattern_reliability(
            pattern_type=pattern.type,
            symbol=trade_episode.symbol,
            outcome=trade_episode.outcome
        )

    # 3. Propose signal weight adjustments
    for agent_signal in trade_episode.signals:
        if agent_signal.was_predictive != agent_signal.predicted_direction:
            propose_weight_adjustment(
                agent_id=agent_signal.agent_id,
                symbol=trade_episode.symbol,
                adjustment=-0.01  # Decrease weight for wrong signal
            )
        elif agent_signal.confidence > 0.7 and trade_episode.outcome == 'win':
            propose_weight_adjustment(
                agent_id=agent_signal.agent_id,
                symbol=trade_episode.symbol,
                adjustment=+0.01  # Increase weight for correct high-confidence signal
            )

    return lessons
```

#### Phase 4: UPDATE KNOWLEDGE

Updates happen in a defined priority order:

```
UPDATE PRIORITY (highest first):

1. SAFETY RULES (immediate, auto-approved)
   - If trade hit max drawdown → tighten risk limit
   - If pattern failed catastrophically → add warning to pattern_reliability
   - If agent produced consistently wrong signals → reduce weight to floor

2. SIGNAL WEIGHTS (auto-approved within bounds)
   - Max ±0.03 adjustment per trade
   - Min weight: 0.05, Max weight: 0.40
   - Normalized to sum to 1.0 after all adjustments
   - Logged to signal_weights table with reason

3. PATTERN RELIABILITY (auto-approved)
   - Update win rate, avg_rr, avg_duration
   - Recompute confidence_interval
   - If sample size < 10: flag as "low confidence"

4. STRATEGY PARAMETERS (requires human approval)
   - TP multiplier adjustments
   - Session-specific rules
   - New entry/exit conditions
   - Proposed by Reflection Agent, approved via HITL

5. NEW LESSONS (auto-created, human-reviewable)
   - Stored in lessons table with status='active'
   - Visible in EDGE_NOTES.md for human review
   - If contradicting evidence accumulates → flagged for review
```

#### Phase 5: STORE LONG-TERM

All updates are persisted to PostgreSQL with full audit trail:

```
EVERY UPDATE RECORDS:
- What changed (before/after values)
- Why it changed (trade_id, lesson_id, reasoning)
- When it changed (timestamp)
- Who changed it (agent_id or 'human')
- Confidence level (0-1)
```

#### Phase 6: APPLY KNOWLEDGE

On the next trade, the updated knowledge is injected into agent prompts:

```
NEXT TRADE CYCLE
  │
  ▼
Agent loads:
  - Updated signal weights (from signal_weights table)
  - Updated pattern reliability (from pattern_reliability table)
  - New lessons matching current conditions (from lessons table)
  - Similar past episodes (from trade_episodes, semantic search)
  │
  ▼
Agent makes decision with enriched context
  │
  ▼
Cycle repeats → system gets smarter with each trade
```

### 9.3 The Compounding Effect

After N trades, the system has:

| Trades | What the System Knows |
|--------|----------------------|
| 10 | Basic pattern win rates for traded instruments |
| 50 | Calibrated signal weights per agent, per symbol |
| 100 | Reliable pattern statistics by regime and session |
| 200 | Instrument-specific edge notes, session-specific rules |
| 500 | Deep expertise: knows which signals work in which conditions, with what confidence |
| 1000+ | Institutional-grade knowledge base that rivals years of human trading experience |

**Key insight:** The system doesn't just accumulate data — it **distills** data into actionable knowledge. A human trader with 1000 trades might have intuition. The system has **structured, queryable, evidence-backed rules**.

### 9.4 Preventing Overfitting

The closed learning loop includes safeguards against learning from noise:

| Safeguard | Mechanism |
|-----------|-----------|
| **Minimum sample size** | Lessons require 5+ supporting trades before confidence > 0.6 |
| **Confidence intervals** | Pattern reliability includes statistical confidence; low-sample patterns flagged |
| **Bounded adjustments** | Signal weights change max ±0.03 per trade; no wild swings |
| **Contradicting evidence** | Lessons with contradicting trades have confidence reduced |
| **Human review** | Strategy parameter changes require human approval |
| **Walk-forward validation** | Weekly review tests if learned rules hold on out-of-sample data |
| **Decay** | Unused lessons lose importance over time; stale knowledge is archived |

---

## 10. How Memory Drives Strategy Improvement

### 10.1 The Improvement Pipeline

Memory doesn't just store information — it actively drives improvement through a defined pipeline:

```
MEMORY CONTENT          →    IMPROVEMENT ACTION         →    EFFECT
─────────────────────────────────────────────────────────────────────
pattern_reliability     →    Signal Aggregator adjusts   →    Better confluence
                            confluence scoring weights       scores over time

signal_weights          →    Signal Aggregator weighs    →    More accurate
                            agent votes differently          consensus decisions

lessons                 →    Injected into agent prompts →    Agents avoid known
                                                               mistakes, follow
                                                               proven rules

similar_episodes        →    Entry Agent calibrates      →    Position sizing
                            position size based on           matches historical
                            historical R:R for similar       success rate
                            setups

regime_history          →    Structure Agent improves    →    Better regime
                            regime detection model           classification

daily_performance       →    Reflection Agent identifies →    Systematic
                            systematic biases                debiasing
```

### 10.2 Concrete Examples

#### Example 1: Signal Weight Adaptation

```
TRADE 50: SMC Agent detected bullish OB, trade won (+1.5R)
  → SMC weight for EUR/USD: 0.15 → 0.16

TRADE 51: SMC Agent detected bearish OB, trade lost (-1R)
  → SMC weight for EUR/USD: 0.16 → 0.15

TRADE 52-60: SMC Agent 7/9 correct on EUR/USD OBs
  → SMC weight for EUR/USD: 0.15 → 0.19

TRADE 61: Momentum Agent divergence signal was wrong
  → Momentum weight for EUR/USD: 0.10 → 0.09

AFTER 100 TRADES:
  EUR/USD weights: SMC=0.22, Structure=0.25, Momentum=0.08, ...
  BTC/USDT weights: SMC=0.12, Momentum=0.18, Liquidity=0.15, ...
  
  Different instruments have different optimal weight distributions!
```

#### Example 2: Pattern Reliability Refinement

```
TRADE 1-10: Bullish OBs on EUR/USD H4 — 7 wins, 3 losses (70%)
  → confidence_interval: wide (small sample)

TRADE 11-30: 14 wins, 6 losses (70% stable)
  → confidence_interval: narrowing
  → avg_rr: 1.8 (good)

TRADE 31-50: 16 wins, 4 losses (80% improving!)
  → Pattern proven reliable for this symbol/timeframe
  → Confluence score for H4 OB on EUR/USD gets +5 bonus

INSIGHT: After 50 trades, the system "knows" that H4 OBs on EUR/USD
are reliable (80% win rate, 1.8 avg R:R). This knowledge is
automatically applied to future trade decisions.
```

#### Example 3: Lesson-Driven Rule Creation

```
TRADE 75: Entered EUR/USD long 30 minutes before NFP. Lost -2R on spike.
  → Reflection: "High-impact events cause unpredictable volatility"
  → New lesson: "Do not enter trades within 30 minutes of high-impact news"
  → Confidence: 0.5 (single incident)

TRADE 89: Entered GBP/USD long 20 minutes before BOE decision. Lost -1.5R.
  → Existing lesson strengthened: confidence 0.65
  → Rule generalized: "No entries within 30 min of any high-impact central bank event"

TRADE 112: Waited for post-CPI, entered EUR/USD. Won +2R.
  → Rule applied successfully: confidence 0.75

AFTER 200 TRADES:
  Rule confidence: 0.85 (strong evidence)
  Rule is now automatically enforced by Risk Gate Agent
  (Risk Gate rejects proposals within 30 min of high-impact events)
```

### 10.3 Improvement Metrics

The system tracks its own improvement over time:

```sql
-- Monthly improvement metrics
SELECT
    date_trunc('month', entry_time) AS month,
    COUNT(*) AS trades,
    ROUND(AVG(net_pnl)::numeric, 2) AS avg_pnl,
    ROUND((COUNT(*) FILTER (WHERE net_pnl > 0)::float / COUNT(*))::numeric, 4) AS win_rate,
    ROUND(AVG(risk_reward_actual)::numeric, 2) AS avg_rr,
    ROUND(AVG(confluence_score)::numeric, 1) AS avg_confluence,
    -- Signal accuracy improvement
    (SELECT ROUND(AVG(accuracy_50)::numeric, 4)
     FROM signal_weights
     WHERE last_adjustment >= date_trunc('month', t.entry_time)) AS avg_signal_accuracy
FROM trades t
WHERE status = 'closed'
GROUP BY date_trunc('month', entry_time)
ORDER BY month;
```

---

## 11. Semantic Search Over Trade History

### 11.1 Why Semantic Search Matters

Traditional SQL queries search by exact criteria: "Find all EUR/USD trades in July 2026." Semantic search finds trades by **meaning**: "Find trades similar to the current setup — a bullish order block at H4 support with RSI oversold during London session."

This is critical because:
- Market conditions are **continuous**, not categorical — two "similar" setups may have different exact values
- Trading knowledge is **contextual** — the same pattern behaves differently in different regimes
- Agents need **analogical reasoning** — "What happened last time conditions looked like this?"

### 11.2 Embedding Strategy

Each trade episode gets two embeddings:

| Embedding | What It Encodes | Dimension | Use |
|-----------|----------------|-----------|-----|
| `context_embedding` | Market conditions: symbol, regime, session, volatility, key levels, indicators | 1536 | "Find similar market conditions" |
| `reasoning_embedding` | Decision reasoning: agent signals, confluence analysis, entry thesis | 1536 | "Find similar trade rationale" |

**Embedding generation:**

```python
def generate_context_embedding(episode):
    """Generate embedding from structured market context."""
    text = f"""
    Symbol: {episode.symbol}
    Regime: {episode.regime} (confidence: {episode.regime_confidence})
    Session: {episode.session}
    Volatility: {episode.volatility_regime}
    ATR: {episode.volatility_atr}
    Key levels: {format_levels(episode.key_levels)}
    Indicators: RSI={episode.rsi}, MACD={episode.macd_signal}
    Patterns: {format_patterns(episode.patterns_detected)}
    News context: {episode.news_summary}
    """
    return embedding_model.encode(text)


def generate_reasoning_embedding(episode):
    """Generate embedding from the decision reasoning."""
    text = f"""
    Entry thesis: {episode.entry_reasoning}
    Confluence score: {episode.confluence_score}
    Agent votes: {format_agent_votes(episode.signals_snapshot)}
    Risk assessment: {episode.risk_reasoning}
    Expected outcome: {episode.expected_outcome}
    """
    return embedding_model.encode(text)
```

### 11.3 Search Queries

#### Query 1: Find Similar Setups

```python
def find_similar_setups(current_context, max_results=10, min_score=0.7):
    """Find past trades with similar market conditions."""
    query_embedding = generate_context_embedding(current_context)

    results = db.execute("""
        SELECT
            te.id, te.trade_id, te.symbol, te.outcome,
            te.net_pnl, te.risk_reward_actual,
            te.confluence_score, te.entry_reasoning,
            te.lessons, te.what_worked, te.what_failed,
            1 - (te.context_embedding <=> %s::vector) AS similarity
        FROM trade_episodes te
        WHERE te.context_embedding IS NOT NULL
        ORDER BY te.context_embedding <=> %s::vector
        LIMIT %s
    """, [query_embedding, query_embedding, max_results])

    return [r for r in results if r['similarity'] >= min_score]
```

#### Query 2: Find Trades with Similar Reasoning

```python
def find_similar_reasoning(entry_reasoning, max_results=10):
    """Find past trades with similar decision rationale."""
    query_embedding = embedding_model.encode(entry_reasoning)

    return db.execute("""
        SELECT
            te.id, te.outcome, te.net_pnl, te.lessons,
            1 - (te.reasoning_embedding <=> %s::vector) AS similarity
        FROM trade_episodes te
        WHERE te.reasoning_embedding IS NOT NULL
        ORDER BY te.reasoning_embedding <=> %s::vector
        LIMIT %s
    """, [query_embedding, query_embedding, max_results])
```

#### Query 3: Cluster by Outcome

```python
def discover_winning_patterns(symbol, regime, min_cluster_size=5):
    """Discover what distinguishes winning trades from losing ones."""
    episodes = db.execute("""
        SELECT * FROM trade_episodes
        WHERE symbol = %s AND regime = %s
    """, [symbol, regime])

    winners = [e for e in episodes if e['outcome'] == 'win']
    losers = [e for e in episodes if e['outcome'] == 'loss']

    # Compute centroid embeddings for winners and losers
    winner_centroid = np.mean([e['context_embedding'] for e in winners], axis=0)
    loser_centroid = np.mean([e['context_embedding'] for e in losers], axis=0)

    # Find features that differentiate winners from losers
    # (Agent signals, patterns, session, volatility — which correlate with outcome?)
    return analyze_feature_importance(winners, losers)
```

### 11.4 Search Performance

| Query Type | Index | Latency | Notes |
|-----------|-------|---------|-------|
| Similar context (top 10) | IVFFlat on context_embedding | <50ms | 1536-dim cosine similarity |
| Similar reasoning (top 10) | IVFFlat on reasoning_embedding | <50ms | 1536-dim cosine similarity |
| Filtered by symbol + regime | Composite B-tree + vector | <30ms | Pre-filter reduces search space |
| Full-text over reasoning | GIN on tsvector | <10ms | For keyword-based search fallback |
| Pattern-based | B-tree on tags | <5ms | For exact tag matches |

### 11.5 Fallback: FTS5 for Phase 1

Before pgvector is available (Phase 1), use SQLite FTS5 for text search:

```python
# SQLite FTS5 fallback (Phase 1)
def search_trade_history_fts(query_text, max_results=10):
    """Full-text search over trade reasoning and lessons."""
    return sqlite_db.execute("""
        SELECT trade_id, entry_reasoning, outcome, net_pnl,
               rank
        FROM trade_episodes_fts
        WHERE trade_episodes_fts MATCH ?
        ORDER BY rank
        LIMIT ?
    """, [query_text, max_results])
```

---

## 12. Memory Cleanup & Archival

### 12.1 Cleanup Philosophy

Memory cleanup follows the **human forgetting curve** (Ebbinghaus): unused memories decay, frequently-accessed memories strengthen. The goal is to keep the knowledge base relevant and performant without losing valuable accumulated expertise.

### 12.2 Cleanup Schedule

```
CONTINUOUS (automated):
  ├── Redis TTL expiry: tick data (60s), signals (5m), orderbook (10s)
  ├── Working memory: replaced on every new input
  └── Stale agent health: expires after 60s without heartbeat

DAILY (end of session):
  ├── Compile daily_performance from today's trades
  ├── Archive memory/YYYY-MM-DD.md (keep 30 days)
  ├── Compact agent observations (keep last 100 per agent)
  ├── Refresh materialized views (v_strategy_performance, v_agent_performance)
  └── Run Reflection Agent on today's closed trades

WEEKLY (Sunday maintenance):
  ├── Decay unused agent_memories (importance -= decay_rate)
  ├── Archive agent_memories with importance < 0.05 and unused for 90+ days
  ├── Recompute pattern_reliability confidence intervals
  ├── Normalize signal_weights (ensure sum = 1.0)
  ├── Validate lessons: check if recent trades support or contradict
  ├── Consolidate weekly digest (memory/consolidated/weekly_YYYY-WNN.md)
  └── Run deep strategy review (Reflection Agent, reasoning-tier model)

MONTHLY:
  ├── Archive daily_performance older than 1 year to cold storage
  ├── Audit lessons: archive lessons with confidence < 0.2
  ├── Audit signal weights: flag agents with accuracy < 40% for review
  ├── Regime model retraining (HMM on last 6 months)
  ├── Consolidate monthly digest (memory/consolidated/monthly_YYYY-MM.md)
  ├── Review EDGE_NOTES.md: remove stale insights
  └── Full strategy parameter review (requires human approval)

QUARTERLY:
  ├── Archive compressed market data older than 1 year
  ├── Full pattern reliability audit
  ├── Strategy parameter recalibration
  ├── Embedding index rebuild (for pgvector IVFFlat)
  └── Storage usage report and capacity planning
```

### 12.3 Retention Matrix

| Data | Hot (Redis) | Warm (PostgreSQL) | Cold (Compressed) | Archive | Delete |
|------|------------|-------------------|-------------------|---------|--------|
| **Ticks** | 60s | 7 days | 90 days | — | ✓ |
| **1m candles** | Until next | 30 days | 2 years | Forever | — |
| **4h/1d candles** | Until next | Forever | — | — | — |
| **Order book** | 10s | 3 days | 30 days | — | ✓ |
| **Signals** | 5m | 7 days (stream) | 90 days | 1 year | ✓ |
| **Orders** | Open only | Forever | — | — | — |
| **Trades** | — | Forever | — | — | — |
| **Trade episodes** | — | Forever | — | — | — |
| **Agent memories** | — | Active: forever | Inactive: 90 days | — | Prune |
| **Lessons** | — | Active: forever | Superseded: archive | — | — |
| **Pattern reliability** | — | Forever | — | — | — |
| **Signal weights** | — | Forever | — | — | — |
| **News events** | 1h | 90 days | 1 year | — | ✓ |
| **Daily performance** | — | Forever | — | — | — |
| **Journal entries** | — | Forever | — | — | — |

### 12.4 Memory Decay Algorithm

```python
def decay_agent_memories():
    """Weekly decay of unused agent memories."""
    memories = db.execute("""
        SELECT id, importance, decay_rate, access_count, last_accessed_at
        FROM agent_memories
        WHERE active = TRUE
    """)

    for mem in memories:
        days_since_access = (now() - mem['last_accessed_at']).days

        if days_since_access > 90 and mem['importance'] < 0.05:
            # Archive: too old, too low importance
            db.execute("UPDATE agent_memories SET active = FALSE WHERE id = %s", [mem['id']])

        elif days_since_access > 30:
            # Decay: reduce importance
            new_importance = max(0.01, mem['importance'] - mem['decay_rate'])
            db.execute("UPDATE agent_memories SET importance = %s WHERE id = %s",
                      [new_importance, mem['id']])

        elif mem['access_count'] > 20 and days_since_access < 7:
            # Strengthen: frequently accessed, recently used
            new_importance = min(1.0, mem['importance'] + 0.05)
            db.execute("UPDATE agent_memories SET importance = %s WHERE id = %s",
                      [new_importance, mem['id']])
```

### 12.5 Lesson Lifecycle

```
LESSON LIFECYCLE:

Created (confidence: 0.5)
  │
  ├── Supporting trade → confidence += 0.05
  ├── Contradicting trade → confidence -= 0.10
  │
  ▼
Confidence > 0.7 → "Established" (auto-applied to decisions)
  │
  ├── If contradicting evidence increases:
  │   confidence -= 0.10 per contradicting trade
  │
  ▼
Confidence < 0.3 → "Questioned" (flagged for human review)
  │
  ├── Human confirms → confidence restored to 0.5
  ├── Human rejects → status = 'archived'
  │
  ▼
Confidence < 0.2 → Auto-archived (status = 'archived')
```

---

## 13. Memory Observability & Debugging

### 13.1 Memory Health Dashboard

The system exposes memory health metrics for monitoring:

```
MEMORY HEALTH METRICS:

Working Memory:
  ├── Redis memory usage: 45MB / 256MB (17.6%)
  ├── Keys by prefix: tick=3, signal=15, regime=3, confluence=3
  ├── Hit rate: 99.2%
  └── Evictions (24h): 0

Short-Term Memory:
  ├── Today's signals: 47
  ├── Today's trades: 3
  ├── Today's news events: 12
  └── Journal entries pending: 1

Long-Term Memory:
  ├── Total lessons: 127 (active), 23 (archived)
  ├── Agent memories: 342 (active), 89 (archived)
  ├── Pattern reliability entries: 156
  ├── Signal weight entries: 21
  └── Avg lesson confidence: 0.68

Episodic Memory:
  ├── Total episodes: 234
  ├── With embeddings: 234 (100%)
  ├── Avg embedding generation time: 45ms
  └── Index size: 12MB

Semantic Search:
  ├── Queries (24h): 89
  ├── Avg latency: 38ms
  ├── Avg results returned: 7.2
  └── Cache hit rate: 0% (no cache — direct vector search)
```

### 13.2 Memory Debugging Tools

```python
class MemoryDebugger:
    """Tools for inspecting and debugging the memory system."""

    def explain_episode(self, trade_id):
        """Show the complete memory trace for a trade."""
        episode = db.get_trade_episode(trade_id)
        signals = db.get_signals_for_trade(trade_id)
        lessons = db.get_lessons_from_trade(trade_id)
        weights = db.get_signal_weights_at_time(trade_id)

        return {
            "episode": episode,
            "signals_at_entry": signals,
            "weights_at_entry": weights,
            "lessons_generated": lessons,
            "similar_episodes": search_similar(episode, max=5)
        }

    def trace_learning(self, lesson_id):
        """Show how a lesson evolved over time."""
        lesson = db.get_lesson(lesson_id)
        supporting = db.get_trades(lesson.supporting_trades)
        contradicting = db.get_trades(lesson.contradicting_trades)

        return {
            "lesson": lesson,
            "confidence_history": get_confidence_timeline(lesson_id),
            "supporting_trades": supporting,
            "contradicting_trades": contradicting,
            "current_status": lesson.status
        }

    def agent_memory_report(self, agent_id):
        """Show all memories for an agent."""
        memories = db.execute("""
            SELECT memory_type, title, importance, access_count,
                   last_accessed_at, created_at
            FROM agent_memories
            WHERE agent_id = %s AND active = TRUE
            ORDER BY importance DESC
        """, [agent_id])

        return {
            "total_memories": len(memories),
            "by_type": group_by_type(memories),
            "most_accessed": memories[:10],
            "least_recent": memories[-10:],
            "high_importance": [m for m in memories if m['importance'] > 0.8]
        }
```

### 13.3 Memory Audit Queries

```sql
-- Find lessons that might be wrong (high contradicting evidence)
SELECT id, title, rule, confidence,
       array_length(supporting_trades, 1) AS supporting,
       array_length(contradicting_trades, 1) AS contradicting
FROM lessons
WHERE status = 'active'
  AND array_length(contradicting_trades, 1) > array_length(supporting_trades, 1)
ORDER BY confidence ASC;

-- Find agents with declining accuracy
SELECT agent_id, symbol, weight, accuracy_50, accuracy_total,
       (accuracy_50 - accuracy_total) AS trend
FROM signal_weights
WHERE accuracy_50 < accuracy_total - 0.1  -- More than 10% decline
ORDER BY trend ASC;

-- Find patterns with insufficient data
SELECT pattern_type, pattern_subtype, symbol, timeframe,
       total_occurrences, win_rate, confidence_interval
FROM pattern_reliability
WHERE total_occurrences < 10
  AND confidence_interval > 0.3  -- Wide confidence = unreliable
ORDER BY confidence_interval DESC;

-- Memory growth over time
SELECT date_trunc('week', created_at) AS week,
       COUNT(*) AS new_episodes,
       (SELECT COUNT(*) FROM lessons WHERE created_at >= date_trunc('week', e.created_at)
        AND created_at < date_trunc('week', e.created_at) + INTERVAL '1 week') AS new_lessons
FROM trade_episodes e
GROUP BY date_trunc('week', e.created_at)
ORDER BY week;
```

---

## 14. Implementation Roadmap

### Phase 1: Foundation (Weeks 1–4)

```
□ Set up Redis with memory key patterns (tick, signal, regime, confluence)
□ Implement working memory read/write for all agents
□ Implement short-term memory (daily notes file + PostgreSQL signals/orders)
□ Create trade_episodes table (without embeddings initially)
□ Create lessons table
□ Create agent_memories table
□ Implement basic Reflection Agent (post-trade review, lesson extraction)
□ Implement basic Journal Agent (daily compilation, episode creation)
□ Implement FTS5 search over trade history (SQLite fallback)
□ Test: Agent prompt injection with memory context
□ Test: Closed learning loop on 10 paper trades
```

### Phase 2: Enrichment (Weeks 5–8)

```
□ Implement pattern_reliability table and update logic
□ Implement signal_weights table and adaptive adjustment
□ Implement regime_history table
□ Implement memory decay algorithm (weekly cron)
□ Implement lesson lifecycle (creation → strengthening → archival)
□ Implement EDGE_NOTES.md auto-maintenance
□ Implement memory debugging tools
□ Implement memory health dashboard metrics
□ Test: Signal weight adaptation over 50 paper trades
□ Test: Pattern reliability statistics accuracy
```

### Phase 3: Semantic Search (Weeks 9–12)

```
□ Install pgvector extension
□ Implement embedding generation for trade episodes
□ Implement context_embedding and reasoning_embedding columns
□ Create IVFFlat indexes for vector similarity search
□ Implement semantic search queries (similar setups, similar reasoning)
□ Implement cluster analysis (winning vs losing pattern discovery)
□ Replace FTS5 fallback with pgvector primary
□ Optimize embedding generation latency (<50ms target)
□ Test: Semantic search relevance on 100+ paper trades
□ Test: "Find similar setups" query quality
```

### Phase 4: Advanced Learning (Weeks 13–16)

```
□ Implement walk-forward validation for learned rules
□ Implement counterfactual analysis ("what if we used wider stops?")
□ Implement automated strategy parameter proposals (Reflection Agent → HITL)
□ Implement cross-instrument knowledge transfer (lessons that apply to multiple pairs)
□ Implement memory consolidation (daily → weekly → monthly digests)
□ Implement overfitting detection (confidence interval monitoring)
□ Implement memory audit queries and alerting
□ Full integration test: 200 paper trades with closed learning loop
□ Performance benchmark: memory read/write latency under load
□ Document: Memory system operations runbook
```

---

## Appendix A: Memory System Data Flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    COMPLETE MEMORY DATA FLOW                              │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  MARKET DATA ──────────────────────────────────────────────────────┐    │
│  (ticks, candles, order book, news)                                │    │
│                                                                     │    │
│  ┌─────────────────────────────────────────────────────────────┐   │    │
│  │                    WORKING MEMORY (Redis)                     │   │    │
│  │  tick:{symbol} ← Ingestion                                  │   │    │
│  │  signal:{agent}:{symbol} ← Signal Agents                    │   │◀───┘
│  │  confluence:{symbol} ← Signal Aggregator                    │   │
│  │  regime:{symbol} ← Structure Agent                          │   │
│  │  position:{id} ← Trade Mgmt Agent                          │   │
│  └─────────────────────────┬───────────────────────────────────┘   │
│                             │                                       │
│          ┌──────────────────┼──────────────────┐                   │
│          │                  │                  │                   │
│          ▼                  ▼                  ▼                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│  │   SIGNAL     │  │    ENTRY     │  │    RISK      │            │
│  │  AGGREGATOR  │  │    AGENT     │  │    GATE      │            │
│  │ (reads all   │  │ (reads conf- │  │ (reads pos-  │            │
│  │  signals)    │  │  luence +    │  │  itions +    │            │
│  │              │  │  lessons)    │  │  risk state) │            │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘            │
│         │                  │                  │                    │
│         └──────────────────┼──────────────────┘                   │
│                            ▼                                       │
│                   ┌──────────────┐                                 │
│                   │  EXECUTION   │                                 │
│                   │    AGENT     │                                 │
│                   └──────┬───────┘                                 │
│                          │                                         │
│                          ▼                                         │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │              SHORT-TERM MEMORY (PostgreSQL)                   │ │
│  │  orders ← Execution Agent                                    │ │
│  │  trades ← Journal Agent                                      │ │
│  │  daily_performance ← Journal Agent (end of day)              │ │
│  │  memory/YYYY-MM-DD.md ← Journal Agent (narrative)            │ │
│  └─────────────────────────┬────────────────────────────────────┘ │
│                            │                                       │
│                            ▼                                       │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │              EPISODIC MEMORY (PostgreSQL + pgvector)          │ │
│  │  trade_episodes ← Journal Agent (within 1h of trade close)   │ │
│  │  journal_entries ← Journal Agent                             │ │
│  └─────────────────────────┬────────────────────────────────────┘ │
│                            │                                       │
│                            ▼                                       │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │              REFLECTION AGENT (triggered by episode)          │ │
│  │  1. Compare predicted vs actual                              │ │
│  │  2. Extract lessons                                          │ │
│  │  3. Update signal_weights                                    │ │
│  │  4. Update pattern_reliability                               │ │
│  │  5. Update agent_memories                                    │ │
│  └─────────────────────────┬────────────────────────────────────┘ │
│                            │                                       │
│                            ▼                                       │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │              LONG-TERM MEMORY (PostgreSQL)                    │ │
│  │  lessons ← Reflection Agent                                  │ │
│  │  signal_weights ← Reflection Agent                           │ │
│  │  pattern_reliability ← Reflection Agent                      │ │
│  │  agent_memories ← Reflection Agent                           │ │
│  │  strategy_parameters ← Reflection Agent (proposal) → Human   │ │
│  │  EDGE_NOTES.md ← Reflection Agent (auto-maintained)          │ │
│  └─────────────────────────┬────────────────────────────────────┘ │
│                            │                                       │
│                            ▼                                       │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │              NEXT TRADE CYCLE                                 │ │
│  │  Agents load: working memory + short-term + long-term        │ │
│  │  + semantic search for similar episodes                      │ │
│  │  → Decisions made with accumulated knowledge                 │ │
│  │  → Loop repeats                                              │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

---

## Appendix B: Configuration Reference

```yaml
# config/memory.yaml

memory:
  working:
    redis_db: 0
    maxmemory: 256mb
    maxmemory_policy: allkeys-lru
    ttl:
      tick: 60s
      signal: 300s
      orderbook: 10s
      regime: 3600s
      confluence: 300s
      indicators: until_next_candle
      patterns: until_next_candle

  short_term:
    daily_notes_dir: memory/
    retention_days: 30
    max_daily_signals: 1000
    max_daily_trades: 100

  long_term:
    min_lesson_confidence: 0.3
    max_signal_weight_change_per_trade: 0.03
    min_signal_weight: 0.05
    max_signal_weight: 0.40
    pattern_min_sample_size: 10
    memory_decay_rate_default: 0.01
    memory_archive_threshold: 0.05
    memory_archive_days: 90

  episodic:
    embedding_model: text-embedding-3-small
    embedding_dimension: 1536
    ivfflat_lists: 100
    min_similarity_score: 0.7
    max_search_results: 10

  consolidation:
    daily_time: "23:00 UTC"
    weekly_day: "Sunday"
    weekly_time: "10:00 UTC"
    monthly_day: 1
    monthly_time: "10:00 UTC"

  cleanup:
    redis_tick_ttl: 60s
    redis_signal_ttl: 300s
    redis_orderbook_ttl: 10s
    daily_notes_retention: 30d
    news_events_retention: 90d
    system_events_retention: 90d
```

---

## Appendix C: Glossary

| Term | Definition |
|------|-----------|
| **Working Memory** | Ephemeral, sub-millisecond state in Redis — what's happening right now |
| **Short-Term Memory** | Today's context in PostgreSQL + files — what happened today |
| **Long-Term Memory** | Permanent distilled knowledge in PostgreSQL — what the system has learned |
| **Episodic Memory** | Complete trade episodes with embeddings — specific past experiences |
| **Closed Learning Loop** | The cycle: trade → reflect → extract → update → apply → trade |
| **Signal Weight** | Adaptive multiplier reflecting an agent's predictive accuracy |
| **Pattern Reliability** | Statistical win rate for a pattern type in specific conditions |
| **Lesson** | Actionable rule distilled from trade experience ("When X, do Y because Z") |
| **Memory Decay** | Gradual reduction in importance of unused memories |
| **Semantic Search** | Finding similar trades by meaning (vector embeddings) rather than exact match |
| **Consolidation** | Periodic process of distilling short-term memories into long-term knowledge |
| **Episode** | A complete trade record including context, signals, reasoning, and outcome |

---

*Document generated: 2026-07-11*
*Author: Memory Systems Architect — Alpha Stack*
*Status: Architecture Design Complete — Ready for Implementation Review*
*Next: Review with team → Begin Phase 1 implementation (Redis memory patterns + Reflection Agent)*
