# Memory Systems Review — Alpha Stack

> **Date:** 2026-07-11
> **Reviewer:** Memory Systems Review Agent
> **Scope:** 4-layer memory architecture, Hermes closed learning loop, memory-driven decision-making, 24/7 operational risks, semantic search feasibility
> **Input Documents:** architecture_system.md, research_14_framework_analysis.md
> **Critical Finding:** `architecture_memory.md` does not exist. The memory system is referenced conceptually but never formally designed. This is the single biggest gap in the architecture.

---

## Executive Summary

The Alpha Stack memory architecture exists as **scattered patterns** across system architecture and research documents, but lacks a dedicated, coherent design. The 4-layer model (Working → Short-Term → Long-Term → Episodic) is implied but never specified. The Hermes closed learning loop is cited as a goal but has no implementation plan. This review identifies **12 critical risks**, **8 design gaps**, and provides a concrete remediation path.

**Overall Assessment: 🔴 HIGH RISK — Memory system needs dedicated architecture before implementation.**

---

## 1. Is the 4-Layer Memory Correctly Designed?

### 1.1 Current State: NOT DESIGNED

The 4-layer model (Working → Short-Term → Long-Term → Episodic) is referenced conceptually across documents but **no formal specification exists**. Here's what's scattered:

| Layer | What Exists | What's Missing |
|-------|------------|----------------|
| **Working** | StrategyContext dataclass (VMPM pipeline) with progressively enriched fields | No definition of working memory size limits, eviction policy, or serialization format |
| **Short-Term** | Redis hot cache (last 10K ticks, last 1000 candles per TF), active signals in Redis | No definition of what qualifies for promotion to long-term, no retention policy beyond TTL |
| **Long-Term** | PostgreSQL (orders, journal), TimescaleDB (OHLCV), ClickHouse (analytics) | No unified query interface, no semantic indexing, no consolidation process defined |
| **Episodic** | Trade journal entries (Step 16 of VMPM), Auditor Agent weekly review | No episodic retrieval mechanism, no similarity search, no context injection for future decisions |

### 1.2 Design Gaps

**Gap 1: No Memory Manager Module**
The system architecture defines agents (Strategy, Risk, News, Execution, Journal, Auditor) but **no Memory Agent or Memory Manager**. There is no component responsible for:
- Deciding what to remember vs. forget
- Promoting short-term observations to long-term knowledge
- Consolidating episodic memories into actionable patterns
- Providing relevant historical context to current decisions

**Gap 2: No Memory Schema**
The `StrategyContext` dataclass is a good working memory structure, but there's no equivalent schema for:
- Trade outcome memories (what happened, why, what was learned)
- Market regime memories (how did price behave in similar conditions)
- Strategy performance memories (which steps work best in which conditions)
- Error memories (what went wrong and what was corrected)

**Gap 3: No Cross-Layer References**
When the Risk Agent evaluates a new trade proposal, how does it recall:
- "Last time we traded EUR/USD during London session with similar RSI, it hit stop loss"?
- "This S/R level has been tested 3 times in the last month and held each time"?
- "The News Agent was wrong about NFP impact last 2 out of 3 times"?

There's no mechanism for linking current decisions to relevant past episodes.

**Gap 4: No Memory Lifecycle**
No definition of:
- When memories are created
- When they're accessed/reinforced
- When they decay or get archived
- When they're permanently deleted
- How conflicting memories are resolved

### 1.3 Recommended 4-Layer Design

```
┌─────────────────────────────────────────────────────────────────────┐
│                    MEMORY ARCHITECTURE (Proposed)                     │
│                                                                      │
│  LAYER 1: WORKING MEMORY (Hot, In-Memory, Ephemeral)                │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ Contents: Current market state, active analysis context,      │   │
│  │           open position state, pending orders, live signals   │   │
│  │ Storage:  Python objects in agent process memory              │   │
│  │ Size:     Bounded (max 100 active contexts)                   │   │
│  │ TTL:      Current analysis cycle (seconds to minutes)         │   │
│  │ Eviction: LRU when capacity exceeded                          │   │
│  │ Access:   Direct object reference (zero latency)              │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                            │                                         │
│                            ▼ (event triggers)                        │
│  LAYER 2: SHORT-TERM MEMORY (Warm, Redis, Session-Scoped)           │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ Contents: Today's signals, recent trade outcomes, current     │   │
│  │           session performance, active market conditions       │   │
│  │ Storage:  Redis hashes + sorted sets                          │   │
│  │ Size:     ~10K entries per instrument                         │   │
│  │ TTL:      Current trading session (4-24 hours)                │   │
│  │ Eviction: Session boundary reset + selective promotion        │   │
│  │ Access:   Key lookup + range queries (sub-ms)                 │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                            │                                         │
│                            ▼ (session end / consolidation)           │
│  LAYER 3: LONG-TERM MEMORY (Cold, PostgreSQL + Vector DB)           │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ Contents: Trade journal, strategy performance metrics,        │   │
│  │           distilled lessons, market regime patterns,          │   │
│  │           S/R level history, correlation matrices             │   │
│  │ Storage:  PostgreSQL (structured) + pgvector (embeddings)     │   │
│  │ Size:     Unbounded (grows ~1MB/day at $7 scale)              │   │
│  │ TTL:      Indefinite (with periodic relevance review)         │   │
│  │ Eviction: Relevance scoring + manual/archival pruning         │   │
│  │ Access:   SQL queries + semantic search (10-50ms)             │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                            │                                         │
│                            ▼ (periodic consolidation)                │
│  LAYER 4: EPISODIC MEMORY (Structured, ClickHouse + Embeddings)     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ Contents: Complete trade episodes (entry → management → exit  │   │
│  │           → outcome → reflection), market event episodes      │   │
│  │           (news → reaction → resolution), strategy adaptation │   │
│  │           episodes (problem → diagnosis → fix → result)       │   │
│  │ Storage:  ClickHouse (event sequences) + vector embeddings    │   │
│  │ Size:     Unbounded, compressed after 90 days                 │   │
│  │ TTL:      Indefinite (institutional-grade retention)          │   │
│  │ Eviction: Archive to cold storage after 2 years               │   │
│  │ Access:   Semantic similarity search (50-200ms)               │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  CROSS-LAYER SEARCH: Unified semantic search across all layers       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ Query: "What happened last time EUR/USD broke above 1.0950    │   │
│  │         during London session with bullish sentiment?"        │   │
│  │ Method: Vector embedding of query → similarity search across  │   │
│  │         episodic memories → rank by recency + relevance       │   │
│  │ Result: Top-5 matching episodes with full context             │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Is the Hermes Closed Learning Loop Correctly Implemented?

### 2.1 Current State: NOT IMPLEMENTED

The research document (Section 2.3) describes Hermes's closed learning loop as a key pattern to adopt:

> *"After processing a Fed rate decision, the agent creates a skill: 'How to analyze Fed rate decisions.' Next time, it loads that skill and processes faster with better context."*

However, **no implementation plan exists** in any architecture document. The closest components are:

| Hermes Pattern | Alpha Stack Component | Status |
|---------------|----------------------|--------|
| Auto-skill creation from tasks | Step 16: Trade Journal & Learn | ⚠️ Only records, doesn't create reusable skills |
| Self-improving skills | Auditor Agent weekly review | ⚠️ Recommends changes, doesn't auto-apply |
| FTS5 session search | Not designed | ❌ No full-text search over trade history |
| Skill compounding | Not designed | ❌ No mechanism for loading past learnings into current context |
| Honcho user modeling | Not designed | ❌ No market regime modeling from experience |

### 2.2 What the Closed Learning Loop Should Look Like

```
TRADE EPISODE                          LEARNING LOOP
─────────────                          ─────────────

1. Signal generated                    ┌─ 5. POST-TRADE ANALYSIS
   (VMPM Steps 1-16)                  │     - What worked?
2. Trade executed                      │     - What failed?
3. Trade managed                       │     - What was unexpected?
4. Trade closed                        │     - P&L attribution
                                       │
                                       ▼
                                 6. EPISODE RECORDED
                                    Full context saved:
                                    - Market state at entry
                                    - Reasoning chain
                                    - Outcome (P&L, duration)
                                    - What was learned
                                       │
                                       ▼
                                 7. PATTERN DETECTION
                                    After N similar episodes:
                                    - "London session RSI divergences
                                       on EUR/USD have 68% win rate"
                                    - "NFP releases cause 2x spread
                                       widening on all USD pairs"
                                       │
                                       ▼
                                 8. SKILL/KNOWLEDGE UPDATE
                                    - Update strategy parameters
                                    - Create reusable analysis template
                                    - Adjust risk limits for conditions
                                    - Feed back into VMPM pipeline
                                       │
                                       ▼
                                 9. NEXT SIMILAR SCENARIO
                                    - Load relevant past episodes
                                    - Apply refined parameters
                                    - Faster, better-informed decision
                                    └──────────────────────────┘
```

### 2.3 Implementation Requirements

To implement the Hermes closed loop, Alpha Stack needs:

1. **Episode Recorder** — Captures complete trade episodes (not just journal entries) with full market context, reasoning chain, and outcome
2. **Pattern Detector** — Runs periodically (daily/weekly) to identify recurring patterns across episodes
3. **Knowledge Updater** — Translates detected patterns into strategy parameter adjustments or new analysis templates
4. **Context Loader** — When facing a new decision, retrieves relevant past episodes and loads them into working memory
5. **Skill Generator** — Creates reusable markdown skill files from successful patterns (Hermes-style)

---

## 3. Does Memory Actually Drive Decision-Making?

### 3.1 Current State: PARTIALLY, BUT NOT DESIGNED TO

The VMPM pipeline (Steps 1-16) produces decisions based on **current market data only**. The `StrategyContext` dataclass has no fields for:
- Historical context ("what happened last time in similar conditions")
- Past trade outcomes on this instrument
- Learned patterns or adjusted parameters
- Memory-retrieved insights

**The decision pipeline is memory-blind.** It processes the current state without referencing the past.

### 3.2 Where Memory Should Drive Decisions

| Decision Point | Current Input | Missing Memory Input | Impact |
|---------------|--------------|---------------------|--------|
| **Step 2: Market Bias** | Current sentiment + macro | Past bias accuracy (was sentiment right last 5 times?) | Over-trusting unreliable signals |
| **Step 5: S/R Detection** | Current price levels | Historical S/R strength (how many times tested, held/broken) | No confidence weighting on levels |
| **Step 8: RSI Confirmation** | Current RSI value | Past RSI signal accuracy in this regime | False signals from range-bound RSI in trending market |
| **Step 10: Entry Signal** | Current candlestick pattern | Pattern success rate in similar conditions | No Bayesian updating on pattern reliability |
| **Step 11: Position Sizing** | Account risk % | Recent win/loss streak, strategy drawdown state | Could over-size after losses (tilting) |
| **Step 14: Trade Management** | Current P&L | How similar trades behaved historically | No learned management rules |
| **Risk Agent** | Current limits | Historical limit breaches, false alarms | Static limits don't adapt to market conditions |
| **News Agent** | Current sentiment | Past sentiment accuracy for this source/indicator | Equal weight to reliable and unreliable sources |

### 3.3 Memory-Augmented Decision Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│              MEMORY-AUGMENTED VMPM PIPELINE                          │
│                                                                      │
│  Current Market Data ─────────────────────────────────┐             │
│                                                       │             │
│  ┌─────────────────────┐                              ▼             │
│  │   MEMORY RETRIEVER  │──▶ Past episodes       ┌─────────┐        │
│  │                     │    for similar          │ CONTEXT │        │
│  │  Query: instrument  │    conditions           │ BUILDER │        │
│  │  + regime + session │──▶ Learned patterns    │         │        │
│  │  + conditions       │    for this setup      │ Merges  │        │
│  │                     │──▶ Strategy adjustments│ current │        │
│  │  Semantic search    │    from past reviews   │ + past  │        │
│  │  across episodic    │                        │ context │        │
│  │  memory             │                        └────┬────┘        │
│  └─────────────────────┘                              │             │
│                                                       ▼             │
│                                              ┌─────────────┐       │
│                                              │ VMPM Steps  │       │
│                                              │ 1-16 with   │       │
│                                              │ augmented   │       │
│                                              │ context     │       │
│                                              └──────┬──────┘       │
│                                                     │              │
│                                                     ▼              │
│                                              Trade Decision        │
│                                              (memory-informed)     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. Memory Leak Risks in 24/7 Operation

### 4.1 Identified Leak Risks

| Risk | Severity | Description | Mitigation |
|------|----------|-------------|------------|
| **Working memory accumulation** | 🔴 HIGH | StrategyContext objects accumulate if not explicitly freed after analysis cycles. Each context holds market data snapshots, indicator states, ML model outputs. | Implement explicit `context.release()` at pipeline completion. Set max concurrent contexts (e.g., 50). Monitor via Prometheus `process_resident_memory_bytes`. |
| **Redis key proliferation** | 🔴 HIGH | Every tick, signal, order creates Redis keys. Without TTL, Redis grows unbounded. At 100 ticks/sec/pair × 5 pairs = 500 keys/sec = 43M keys/day. | Enforce TTL on ALL Redis keys. Use Redis Streams with MAXLEN. Implement daily key audit. |
| **Event bus backlog** | 🟡 MEDIUM | If consumers fall behind producers, Redis Streams grow. Journal Agent processing delays → stream grows unbounded. | Set MAXLEN on all streams. Implement consumer lag monitoring. Alert if lag > 1000 entries. |
| **Log volume explosion** | 🟡 MEDIUM | "Audit everything" principle → every decision, every tick logged. At scale, this generates GB/day. | Structured logging with severity levels. Auto-rotate logs. Archive to S3 after 7 days. ClickHouse for long-term audit (compressed). |
| **ML model memory** | 🟡 MEDIUM | PyTorch models loaded in memory. Multiple models (FinBERT, regime classifier, S/R detector, pattern CNN) × multiple instruments = significant memory. | Lazy model loading. Model sharing across instruments. Quantized inference. Memory-mapped model weights. |
| **Session transcript growth** | 🟠 LOW-MED | Agent session transcripts (JSONL) grow with every interaction. Over months, these become large. | Implement compaction (summarize old transcripts). Archive raw transcripts to S3. Keep only recent + summarized. |
| **TimescaleDB hypertable bloat** | 🟠 LOW-MED | Tick data at 100/sec = 8.6M rows/day. Without compression, storage explodes. | TimescaleDB native compression (90%+ reduction). Retention policies (drop raw ticks after 1 year). |
| **Embedding vector accumulation** | 🟠 LOW | Vector embeddings for semantic search grow with every trade episode. After 10K trades, this is non-trivial. | Use dimensionality reduction (768→128). Cluster old embeddings. Archive embeddings > 1 year old. |
| **Connection pool leaks** | 🟠 LOW | Database, Redis, broker connections not properly released. Common in long-running async Python. | Connection pool monitoring. Health check endpoints. Automatic connection recycling. |
| **Garbage collection pauses** | 🟠 LOW | Python GC pauses during high-frequency processing. Can cause missed ticks or delayed signals. | Use `gc.disable()` during critical paths. Periodic GC in controlled windows. Consider Rust for hot paths (already planned). |

### 4.2 24/7 Memory Monitoring Requirements

```python
MEMORY_MONITORING = {
    "metrics": {
        "process_resident_memory_bytes": {"alert": "> 2GB", "critical": "> 4GB"},
        "redis_used_memory_bytes": {"alert": "> 1GB", "critical": "> 2GB"},
        "redis_connected_clients": {"alert": "> 100", "critical": "> 200"},
        "timescale_disk_usage_bytes": {"alert": "> 50GB", "critical": "> 100GB"},
        "event_bus_consumer_lag": {"alert": "> 1000", "critical": "> 10000"},
        "active_contexts_count": {"alert": "> 50", "critical": "> 100"},
        "gc_pause_duration_seconds": {"alert": "> 0.1", "critical": "> 0.5"},
    },
    "scheduled_tasks": {
        "hourly": "Check Redis key count, memory usage, connection pools",
        "daily": "Audit log volume, TimescaleDB size, embedding count",
        "weekly": "Full memory audit, identify leaks, prune stale data",
    },
    "auto_remediation": {
        "redis_memory_critical": "Flush expired keys, compress streams",
        "process_memory_critical": "Restart worker processes (graceful)",
        "disk_critical": "Archive old data to S3, compress hypertables",
    }
}
```

---

## 5. Is Semantic Search Over Trade History Feasible?

### 5.1 Feasibility Assessment: ✅ YES, WITH CAVEATS

| Factor | Assessment | Details |
|--------|-----------|---------|
| **Data volume** | ✅ Manageable | At $7 scale: ~10 trades/day × 365 days = 3,650 episodes/year. At institutional scale: ~1000 trades/day × 365 = 365K episodes/year. Both are within pgvector capabilities. |
| **Embedding quality** | ⚠️ Needs validation | Financial text embeddings (trade reasoning, market context) need domain-specific fine-tuning. Generic sentence transformers may not capture trading nuances (e.g., "bullish engulfing at support" vs "bearish engulfing at resistance"). |
| **Query latency** | ✅ Acceptable | pgvector with IVFFlat index: <50ms for 100K vectors. HNSW index: <10ms for 1M vectors. Well within decision-making timeframes. |
| **Storage cost** | ✅ Minimal | 768-dim float32 embedding = 3KB. 100K episodes = 300MB. Negligible. |
| **Retrieval relevance** | ⚠️ Critical challenge | "Similar" trades need multi-dimensional similarity: instrument, timeframe, market regime, session, technical setup, fundamental context. Pure text embedding won't capture all dimensions. |

### 5.2 Recommended Semantic Search Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│              TRADE HISTORY SEMANTIC SEARCH                            │
│                                                                      │
│  TRADE EPISODE                                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ {                                                             │   │
│  │   "trade_id": "uuid",                                        │   │
│  │   "instrument": "EUR/USD",                                   │   │
│  │   "timestamp": "2026-07-11T14:30:00Z",                       │   │
│  │   "direction": "LONG",                                       │   │
│  │   "entry_price": 1.0950,                                     │   │
│  │   "exit_price": 1.0985,                                      │   │
│  │   "pnl_pips": 35,                                            │   │
│  │   "duration_minutes": 120,                                   │   │
│  │   "session": "London",                                       │   │
│  │   "regime": "trending_bullish",                              │   │
│  │   "reasoning_text": "Strong bullish bias from D1 structure,  │   │
│  │     H4 order block at 1.0945 held, RSI divergence on H1...", │   │
│  │   "embedding": [0.023, -0.156, ...],  // 768-dim             │   │
│  │   "structured_tags": {                                       │   │
│  │     "pattern": "order_block_bounce",                         │   │
│  │     "timeframe": "H1",                                       │   │
│  │     "session": "london",                                     │   │
│  │     "regime": "trending",                                    │   │
│  │     "confidence": 0.78,                                      │   │
│  │     "outcome": "win"                                         │   │
│  │   }                                                          │   │
│  │ }                                                             │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  SEARCH STRATEGY: Hybrid (Structured + Semantic)                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ 1. STRUCTURED FILTER (fast, exact)                           │   │
│  │    WHERE instrument = 'EUR/USD'                              │   │
│  │      AND session = 'london'                                  │   │
│  │      AND regime = 'trending'                                 │   │
│  │      AND outcome = 'win'                                     │   │
│  │                                                              │   │
│  │ 2. SEMANTIC RANK (on filtered set)                           │   │
│  │    SELECT *, embedding <=> query_embedding AS similarity     │   │
│  │    FROM filtered_set                                         │   │
│  │    ORDER BY similarity                                       │   │
│  │    LIMIT 5                                                   │   │
│  │                                                              │   │
│  │ 3. RECENCY BOOST                                             │   │
│  │    final_score = similarity * 0.7 + recency_weight * 0.3     │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  PERFORMANCE TARGETS                                                 │
│  - Query latency: <50ms (structured) + <50ms (semantic) = <100ms    │
│  - Relevance: Top-5 results should include ≥3 genuinely similar     │
│    trades (validated by human review during paper trading)           │
│  - Scale: Handles up to 1M episodes without degradation              │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.3 Key Challenge: Embedding Quality

Generic sentence transformers (all-MiniLM-L6-v2, etc.) may not adequately represent trading-specific semantics. Options:

| Approach | Effort | Quality | Recommendation |
|----------|--------|---------|----------------|
| Generic embeddings (sentence-transformers) | Low | Medium | Start here for Phase 1 |
| Financial-domain embeddings (FinBERT, Bloomberg BERT) | Medium | Good | Adopt for Phase 2 |
| Custom fine-tuned embeddings on trade history | High | Best | Phase 3+ after accumulating 1000+ labeled episodes |
| Hybrid: structured tags + generic embeddings | Low | Good | **Recommended for initial deployment** |

The hybrid approach (structured tags for exact filtering + embeddings for semantic ranking within filtered results) provides the best cost/quality ratio.

---

## 6. Memory System Risks

### 6.1 Critical Risks

| # | Risk | Probability | Impact | Mitigation |
|---|------|------------|--------|------------|
| **R1** | **No memory architecture exists** — system will be built without coherent memory design, leading to fragmented, inconsistent memory across agents | HIGH | CRITICAL | Create `architecture_memory.md` immediately. This review provides the foundation. |
| **R2** | **Memory-blind decisions** — VMPM pipeline makes decisions without referencing historical context, repeating known mistakes | HIGH | HIGH | Implement Memory Retriever that injects relevant past episodes into StrategyContext before VMPM Steps 9-14. |
| **R3** | **Redis unbounded growth** — 24/7 operation with tick data, signals, and events filling Redis without proper TTL/MAXLEN | MEDIUM | HIGH | Enforce TTL on all keys. Use Redis Streams with MAXLEN. Monitor memory usage hourly. |
| **R4** | **No learning loop** — system generates trades but doesn't systematically learn from outcomes | HIGH | HIGH | Implement the Hermes-inspired closed loop: Episode Recorder → Pattern Detector → Knowledge Updater → Context Loader. |
| **R5** | **Semantic search hallucination** — LLM interprets retrieved episodes incorrectly, making decisions based on misremembered history | MEDIUM | HIGH | Always pass raw episode data alongside LLM summary. Implement confidence scoring on retrieved memories. Log which memories influenced each decision. |
| **R6** | **Memory poisoning** — Bad trade outcomes create false patterns that mislead future decisions | MEDIUM | HIGH | Implement minimum sample size for pattern detection (N≥10). Confidence intervals on all learned patterns. Human review gate for strategy parameter changes. |
| **R7** | **Cross-agent memory inconsistency** — Strategy Agent, Risk Agent, and Journal Agent each maintain separate memory views, leading to conflicting assessments | MEDIUM | MEDIUM | Implement shared memory store (PostgreSQL) with agent-specific views. Single source of truth for trade outcomes. |
| **R8** | **Cold start problem** — New deployment has zero episodic memory, decisions are memory-blind for weeks | HIGH | MEDIUM | Backfill with historical trade data. Import backtest results as synthetic episodes. Start with conservative (memory-agnostic) parameters and gradually trust memory-informed decisions. |
| **R9** | **Memory retrieval latency** — Semantic search adds 50-200ms to decision pipeline, potentially missing entry windows | LOW | MEDIUM | Pre-compute common queries. Cache frequently accessed episodes. Async memory retrieval (fetch while VMPM Steps 1-8 run). |
| **R10** | **Overfitting to history** — System becomes too conservative, avoiding trades that resemble past losses even when conditions have changed | MEDIUM | MEDIUM | Implement memory decay (older episodes weighted less). Include regime change detection. Set minimum novelty threshold. |
| **R11** | **GDPR/compliance data retention** — Trade history contains PII (account IDs, broker credentials in logs). Indefinite retention may violate regulations | LOW | MEDIUM | Implement data anonymization in episodic memory. Separate PII from trade data. Configurable retention policies. |
| **R12** | **Disaster recovery** — Memory loss (Redis crash, PostgreSQL corruption) means losing all learned knowledge | LOW | CRITICAL | Daily backups of PostgreSQL. Redis AOF persistence. Episodic memory exported to S3 weekly. Document recovery procedures. |

### 6.2 Risk Heat Map

```
                    LOW IMPACT    MEDIUM IMPACT    HIGH IMPACT    CRITICAL IMPACT
HIGH PROB.                    ┌──────────────┐   ┌──────────────┐
                              │ R8 Cold Start│   │ R1 No Design │
                              │              │   │ R2 Blind Dec │
                              │              │   │ R4 No Loop   │
                              └──────────────┘   └──────────────┘
MEDIUM PROB.   ┌────────────┐ ┌──────────────┐   ┌──────────────┐
               │ R11 GDPR   │ │ R7 Inconsist │   │ R3 Redis Grow│
               │            │ │ R10 Overfit  │   │ R5 Hallucin. │
               │            │ │              │   │ R6 Poisoning │
               └────────────┘ └──────────────┘   └──────────────┘
LOW PROB.      ┌────────────┐ ┌──────────────┐   ┌──────────────┐
               │            │ │ R9 Latency   │   │ R12 Disaster │
               │            │ │              │   │              │
               └────────────┘ └──────────────┘   └──────────────┘
```

---

## 7. Recommendations

### 7.1 Immediate Actions (Before Implementation)

1. **Create `architecture_memory.md`** — Formalize the 4-layer memory architecture with schemas, interfaces, lifecycle policies, and component responsibilities
2. **Design Memory Manager module** — A dedicated component (or agent) responsible for memory operations across all layers
3. **Define memory schemas** — Pydantic models for trade episodes, market memories, learned patterns, and strategy adjustments
4. **Specify semantic search interface** — How agents query memory, what gets returned, latency budgets

### 7.2 Phase 1 Memory Implementation (Weeks 1-4)

- Implement Working Memory (StrategyContext with bounded size)
- Implement Short-Term Memory (Redis with enforced TTL)
- Basic trade journal (PostgreSQL, structured only)
- No semantic search yet — structured queries only

### 7.3 Phase 2 Memory Implementation (Weeks 5-8)

- Implement Long-Term Memory (PostgreSQL + pgvector)
- Add episode recording with embeddings
- Basic semantic search (hybrid structured + vector)
- Memory-augmented VMPM pipeline (Steps 9-14 reference history)

### 7.4 Phase 3 Closed Learning Loop (Weeks 9-12)

- Implement Pattern Detector (weekly analysis of episodes)
- Implement Knowledge Updater (strategy parameter adjustments)
- Implement Context Loader (retrieval-augmented decisions)
- Begin Hermes-style skill generation from successful patterns

### 7.5 Phase 4 Production Hardening (Weeks 13-16)

- Memory monitoring (Prometheus metrics, alerting)
- Memory lifecycle management (decay, archival, pruning)
- Disaster recovery (backups, restore procedures)
- Memory performance optimization (caching, pre-computation)

---

## 8. Conclusion

The Alpha Stack has a strong system architecture and well-researched framework patterns, but the **memory system is the largest unaddressed gap**. Without a coherent memory architecture:

- The system cannot learn from its own trades
- Decisions are made without historical context
- The Hermes closed learning loop remains aspirational
- 24/7 operation risks unbounded memory growth
- Semantic search over trade history has no foundation

The 4-layer model (Working → Short-Term → Long-Term → Episodic) is the correct pattern, informed by both OpenClaw and Hermes. The hybrid semantic search approach (structured filters + vector ranking) is feasible and practical. The closed learning loop is implementable but requires dedicated components that don't yet exist.

**Priority: Create `architecture_memory.md` as a first-class architecture document, on par with `architecture_system.md`.**

---

*This review was generated by the Memory Systems Review Agent. All assessments are based on the available architecture and research documents. Implementation-specific validation will require the formal memory architecture document.*
