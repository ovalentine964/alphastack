# Architecture: Memory System — Alpha Stack

> **Version:** 1.0  
> **Date:** 2026-07-11  
> **Status:** Architecture Design — Ready for Implementation  
> **Related:** `architecture_system.md`, `research_14_framework_analysis.md`, `fix_learning_loops.md`, `review_memory_systems.md`

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Design Principles](#2-design-principles)
3. [4-Layer Memory Architecture](#3-4-layer-memory-architecture)
4. [Memory Manager Component](#4-memory-manager-component)
5. [Hermes-Inspired Closed Learning Loop](#5-hermes-inspired-closed-learning-loop)
6. [Schemas](#6-schemas)
7. [Lifecycle Policies](#7-lifecycle-policies)
8. [Redis Unbounded Growth Prevention](#8-redis-unbounded-growth-prevention)
9. [Semantic Search Over Trade History](#9-semantic-search-over-trade-history)
10. [Disaster Recovery Procedures](#10-disaster-recovery-procedures)
11. [Integration with Agents and Trading Engine](#11-integration-with-agents-and-trading-engine)
12. [24/7 Operation Memory Leak Prevention](#12-247-operation-memory-leak-prevention)
13. [Implementation Roadmap](#13-implementation-roadmap)

---

## 1. Executive Summary

The Alpha Stack memory system is a **4-layer architecture** (Working → Short-Term → Long-Term → Episodic) that enables the trading system to learn from its own experience. Inspired by OpenClaw's layered memory and Hermes's closed learning loop, it transforms raw trade data into actionable knowledge through a structured pipeline: **Trade → Reflect → Extract → Update → Store → Apply**.

**Key design decisions:**
- **Working Memory**: In-process Python objects, LRU-evicted, bounded at 100 contexts
- **Short-Term Memory**: Redis with mandatory TTL on every key, MAXLEN on every stream
- **Long-Term Memory**: PostgreSQL (structured) + pgvector (semantic search)
- **Episodic Memory**: ClickHouse (event sequences) + vector embeddings for similarity search
- **Learning Loop**: Contextual bandits (not deep RL) for TP strategy selection, hierarchical Bayesian pattern reliability, ablation-based causal attribution, concept drift detection
- **Safety**: Statistical significance gates on all weight changes, counterfactual shadow tracking, minimum sample requirements

---

## 2. Design Principles

| # | Principle | Rationale |
|---|-----------|-----------|
| **P1** | **Every memory has a lifecycle** | No data lives forever without review. TTL, decay, archival, and deletion are first-class concepts. |
| **P2** | **Bounded by default** | Every data structure has a maximum size. Unbounded growth is a bug, not a feature. |
| **P3** | **Memory drives decisions** | The AlphaStack pipeline must reference historical context. Memory-blind decisions repeat known mistakes. |
| **P4** | **Statistical rigor** | No weight adjustment without significance testing. No pattern claim without minimum sample size. |
| **P5** | **Closed learning loop** | Every trade feeds back into knowledge. The system compounds experience over time. |
| **P6** | **Graceful degradation** | Memory loss (Redis crash, DB corruption) must not stop trading. The system operates conservatively without memory. |
| **P7** | **Single source of truth** | PostgreSQL is the canonical store. Redis is a cache. ClickHouse is an analytics mirror. No conflicting views. |
| **P8** | **Observable** | Every memory operation is logged and metriced. Memory leaks are detected within hours, not weeks. |

---

## 3. 4-Layer Memory Architecture

```
┌───────────────────────────────────────────────────────────────────────────┐
│                        ALPHA STACK MEMORY ARCHITECTURE                     │
│                                                                            │
│  LAYER 1: WORKING MEMORY (Hot, In-Process, Ephemeral)                     │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │  Storage:   Python objects in agent process memory                 │   │
│  │  Contents:  Current market state, active analysis context,         │   │
│  │             open position state, pending orders, live signals      │   │
│  │  Size:      Bounded — max 100 concurrent StrategyContext objects   │   │
│  │  TTL:       Current analysis cycle (seconds to minutes)            │   │
│  │  Eviction:  LRU when capacity exceeded                             │   │
│  │  Access:    Direct object reference (zero latency, <1ms)           │   │
│  │  Schema:    StrategyContext dataclass (see §6.1)                   │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│                              │                                             │
│                              ▼ (event triggers: trade close, signal gen)   │
│                                                                            │
│  LAYER 2: SHORT-TERM MEMORY (Warm, Redis, Session-Scoped)                 │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │  Storage:   Redis hashes, sorted sets, streams                     │   │
│  │  Contents:  Today's signals, recent trade outcomes, current        │   │
│  │             session performance, active market conditions,          │   │
│  │             last 10K ticks, last 1000 candles per TF               │   │
│  │  Size:      ~10K entries per instrument, capped per key pattern    │   │
│  │  TTL:       Current trading session (4–24 hours)                   │   │
│  │  Eviction:  Session boundary reset + selective promotion           │   │
│  │  Access:    Key lookup + range queries (sub-millisecond)           │   │
│  │  Schema:    Redis key schemas (see §6.2)                           │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│                              │                                             │
│                              ▼ (session end / consolidation cron)          │
│                                                                            │
│  LAYER 3: LONG-TERM MEMORY (Cold, PostgreSQL + pgvector)                  │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │  Storage:   PostgreSQL (structured) + pgvector (embeddings)        │   │
│  │  Contents:  Trade journal, strategy performance metrics,           │   │
│  │             distilled lessons, market regime patterns,              │   │
│  │             S/R level history, correlation matrices,                │   │
│  │             learned management rules, signal weights               │   │
│  │  Size:      Unbounded (grows ~1MB/day at retail scale)             │   │
│  │  TTL:       Indefinite with periodic relevance review              │   │
│  │  Eviction:  Relevance scoring + archival after 2 years             │   │
│  │  Access:    SQL queries + semantic search (10–50ms)                │   │
│  │  Schema:    PostgreSQL tables (see §6.3)                           │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│                              │                                             │
│                              ▼ (periodic consolidation: weekly/monthly)    │
│                                                                            │
│  LAYER 4: EPISODIC MEMORY (Structured Sequences, ClickHouse + Embeddings) │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │  Storage:   ClickHouse (event sequences) + vector embeddings       │   │
│  │  Contents:  Complete trade episodes (entry → management → exit     │   │
│  │             → outcome → reflection), market event episodes          │   │
│  │             (news → reaction → resolution), strategy adaptation     │   │
│  │             episodes (problem → diagnosis → fix → result)           │   │
│  │  Size:      Unbounded, compressed after 90 days                    │   │
│  │  TTL:       Indefinite (institutional-grade retention)             │   │
│  │  Eviction:  Archive to cold storage (S3) after 2 years             │   │
│  │  Access:    Semantic similarity search (50–200ms)                  │   │
│  │  Schema:    ClickHouse tables + embeddings (see §6.4)              │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│                                                                            │
│  CROSS-LAYER: UNIFIED SEMANTIC SEARCH                                      │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │  Query:  "What happened last time EUR/USD broke above 1.0950       │   │
│  │           during London session with bullish sentiment?"            │   │
│  │  Method: Vector embedding → hybrid search (structured + semantic)  │   │
│  │          across all layers → rank by recency + relevance           │   │
│  │  Result: Top-5 matching episodes with full context                 │   │
│  └────────────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Layer Promotion Rules

| From | To | Trigger | What Gets Promoted |
|------|----|---------|-------------------|
| Working → Short-Term | Analysis cycle complete | Market state snapshot, signal decisions, context summary |
| Short-Term → Long-Term | Trade closes | Trade journal entry, outcome metrics, lesson extracted |
| Short-Term → Long-Term | Session ends | Session performance summary, aggregated signals |
| Long-Term → Episodic | Pattern detected (N≥10) | Distilled pattern with confidence interval |
| Long-Term → Episodic | Weekly consolidation | Week's trade episodes with full reasoning chains |
| Any → Decay | Relevance review fails | Confidence reduced, eventually archived |

### 3.2 Data Flow Diagram

```
                    ┌──────────────┐
                    │   Exchange    │
                    │  WebSocket    │
                    └──────┬───────┘
                           │ tick data
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    WORKING MEMORY                                 │
│  StrategyContext ──── current market state + analysis pipeline    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │ Price Stream  │  │  Indicator   │  │   Signal     │           │
│  │   (live)      │  │   State      │  │  Generator   │           │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘           │
│         └──────────────────┴──────────────────┘                   │
│                            │                                      │
│                            ▼                                      │
│                    AlphaStack Pipeline (Steps 1-16)                     │
│                    with Memory Augmentation                       │
└────────────────────────────┬────────────────────────────────────┘
                             │
                ┌────────────┼────────────┐
                ▼            ▼            ▼
┌──────────────────┐ ┌──────────────┐ ┌──────────────────┐
│  Signal Generated │ │ Trade Opened │ │ Trade Closed     │
│  → Log to Redis  │ │ → Log to Redis│ │ → Record Episode │
│  (L2, TTL: 24h) │ │ (L2, TTL: ∞) │ │ → Extract Lesson │
└──────────────────┘ └──────────────┘ │ → Update Patterns │
                                      │ → Store (L3/L4)  │
                                      └────────┬─────────┘
                                               │
                                               ▼
                                      ┌──────────────────┐
                                      │  LEARNING LOOP    │
                                      │  (see §5)         │
                                      │                   │
                                      │  Trade            │
                                      │    → Reflect      │
                                      │    → Extract      │
                                      │    → Update       │
                                      │    → Store        │
                                      │    → Apply        │
                                      └──────────────────┘
                                               │
                                               ▼
                                      Next trade benefits
                                      from accumulated
                                      knowledge
```

---

## 4. Memory Manager Component

The Memory Manager is a **dedicated service** responsible for all memory operations across all layers. It is not an "agent" in the LLM sense — it is a deterministic service with well-defined APIs.

### 4.1 Responsibilities

| Responsibility | Description |
|---------------|-------------|
| **Store** | Persist data to the appropriate layer with correct TTL and schema |
| **Retrieve** | Fetch relevant memories given a query context (structured + semantic) |
| **Promote** | Move data between layers based on lifecycle rules |
| **Decay** | Reduce confidence/relevance of stale memories |
| **Archive** | Move old data to cold storage (S3) |
| **Consolidate** | Run periodic consolidation passes (daily, weekly, monthly) |
| **Monitor** | Track memory usage, detect leaks, enforce bounds |
| **Recover** | Handle disaster recovery (restore from backups) |

### 4.2 Interface

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from datetime import datetime
import uuid


class MemoryManager:
    """
    Central memory service for Alpha Stack.
    Manages all 4 memory layers and the closed learning loop.
    """

    # ── Layer 1: Working Memory ──

    @abstractmethod
    def create_context(self, instrument: str, timeframe: str) -> 'StrategyContext':
        """Create a new working memory context for an analysis cycle."""

    @abstractmethod
    def get_context(self, context_id: str) -> Optional['StrategyContext']:
        """Retrieve a working memory context by ID."""

    @abstractmethod
    def release_context(self, context_id: str) -> None:
        """Release a working memory context (free resources)."""

    @abstractmethod
    def get_active_context_count(self) -> int:
        """Return number of active working memory contexts."""

    # ── Layer 2: Short-Term Memory ──

    @abstractmethod
    def store_signal(self, signal: 'TradeSignal') -> None:
        """Store a generated signal in short-term memory."""

    @abstractmethod
    def store_tick(self, instrument: str, tick: dict) -> None:
        """Store a tick in the hot cache (Redis)."""

    @abstractmethod
    def get_recent_signals(self, instrument: str, limit: int = 100) -> list:
        """Retrieve recent signals for an instrument."""

    @abstractmethod
    def get_recent_candles(self, instrument: str, timeframe: str, limit: int = 1000) -> list:
        """Retrieve recent candles from short-term cache."""

    @abstractmethod
    def session_reset(self, session_type: str) -> None:
        """Reset session-scoped data at session boundary."""

    # ── Layer 3: Long-Term Memory ──

    @abstractmethod
    def store_trade(self, trade: 'TradeRecord') -> str:
        """Store a completed trade in long-term memory."""

    @abstractmethod
    def store_lesson(self, lesson: 'Lesson') -> str:
        """Store a learned lesson."""

    @abstractmethod
    def store_pattern(self, pattern: 'PatternRecord') -> None:
        """Store or update a detected pattern with reliability metrics."""

    @abstractmethod
    def query_lessons(self, instrument: str, regime: str, session: str,
                      limit: int = 10) -> list:
        """Retrieve relevant lessons for current conditions."""

    @abstractmethod
    def query_management_rules(self, instrument: str, regime: str,
                               session: str, setup_type: str) -> Optional[dict]:
        """Retrieve optimal management rules for conditions."""

    @abstractmethod
    def update_signal_weight(self, agent_id: str, symbol: str,
                             adjustment: float, evidence: dict) -> bool:
        """Update signal weight with statistical significance gate."""

    # ── Layer 4: Episodic Memory ──

    @abstractmethod
    def store_episode(self, episode: 'TradeEpisode') -> str:
        """Store a complete trade episode with embedding."""

    @abstractmethod
    def search_similar_episodes(self, query: str, filters: dict,
                                limit: int = 5) -> list:
        """Semantic search over trade episodes."""

    @abstractmethod
    def search_by_embedding(self, embedding: list[float], filters: dict,
                            limit: int = 5) -> list:
        """Direct vector similarity search."""

    # ── Cross-Layer ──

    @abstractmethod
    def get_memory_context(self, instrument: str, regime: str,
                           session: str, setup_type: str) -> 'MemoryContext':
        """
        Retrieve a unified memory context for decision-making.
        Combines relevant data from all 4 layers.
        """

    # ── Learning Loop ──

    @abstractmethod
    def run_reflection(self, trade_id: str) -> 'ReflectionResult':
        """Run post-trade reflection: compare, attribute, extract lessons."""

    @abstractmethod
    def run_consolidation(self, scope: str) -> None:
        """Run periodic consolidation (daily/weekly/monthly)."""

    @abstractmethod
    def run_drift_check(self) -> 'DriftResult':
        """Run concept drift detection across all agents."""

    # ── Monitoring ──

    @abstractmethod
    def get_memory_stats(self) -> dict:
        """Return memory usage statistics across all layers."""

    @abstractmethod
    def audit_keys(self) -> dict:
        """Audit Redis keys for TTL compliance and count."""
```

### 4.3 Component Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      MEMORY MANAGER                              │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Working Mem  │  │ Short-Term   │  │ Long-Term    │          │
│  │ Store        │  │ Store        │  │ Store        │          │
│  │ (Python)     │  │ (Redis)      │  │ (PostgreSQL) │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                  │                  │                  │
│  ┌──────┴──────────────────┴──────────────────┴───────┐         │
│  │              Memory Router / Policy Engine           │         │
│  │  - Routes writes to correct layer                   │         │
│  │  - Enforces TTL policies                            │         │
│  │  - Manages promotion/decay rules                    │         │
│  └──────────────────────┬─────────────────────────────┘         │
│                          │                                       │
│  ┌──────────────────────┴─────────────────────────────┐         │
│  │              Learning Loop Engine                    │         │
│  │  - Episode Recorder                                 │         │
│  │  - Reflection Agent (ablation attribution)          │         │
│  │  - Pattern Detector (hierarchical Bayesian)         │         │
│  │  - Knowledge Updater (contextual bandit)            │         │
│  │  - Drift Detector (Page-Hinkley + HMM)              │         │
│  │  - Context Loader (retrieval-augmented decisions)   │         │
│  └──────────────────────┬─────────────────────────────┘         │
│                          │                                       │
│  ┌──────────────────────┴─────────────────────────────┐         │
│  │              Monitoring & Recovery                   │         │
│  │  - Prometheus metrics exporter                      │         │
│  │  - Redis key auditor                                │         │
│  │  - Memory leak detector                             │         │
│  │  - Backup orchestrator                              │         │
│  └─────────────────────────────────────────────────────┘         │
│                                                                  │
│  ┌─────────────────────────────────────────────────────┐         │
│  │              Episodic Memory Store                   │         │
│  │  (ClickHouse + pgvector embeddings)                  │         │
│  └─────────────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────────┘
```

### 4.4 Deployment Model

The Memory Manager runs as a **dedicated microservice** within the Alpha Stack infrastructure:

- **Process**: Single long-lived Python process (async/await)
- **API**: gRPC for internal calls (low latency), REST for monitoring/debugging
- **Scaling**: Single instance at retail scale; sharded by instrument at institutional scale
- **Health**: Exposes `/health` and `/metrics` endpoints for Prometheus scraping
- **Dependencies**: Redis, PostgreSQL (with pgvector), ClickHouse, S3

---

## 5. Hermes-Inspired Closed Learning Loop

The closed learning loop is the core mechanism by which the system improves over time. Every completed trade feeds back into accumulated knowledge, which influences future decisions.

### 5.1 Loop Architecture

```
TRADE EPISODE                                    CLOSED LEARNING LOOP
──────────────                                   ────────────────────

1. Signal generated (AlphaStack Steps 1-16)
2. Trade executed
3. Trade managed (partials, trailing)
4. Trade closed
         │
         ▼
┌────────────────────────────────────┐
│  STEP 1: REFLECT                   │◄─────────────────────────────┐
│                                    │                              │
│  Post-trade analysis:              │                              │
│  • Compare predicted vs actual     │                              │
│  • Run ablation attribution        │                              │
│  • Compute counterfactuals         │                              │
│  • Identify what worked/failed     │                              │
└────────────────┬───────────────────┘                              │
                 │                                                  │
                 ▼                                                  │
┌────────────────────────────────────┐                              │
│  STEP 2: EXTRACT                   │                              │
│                                    │                              │
│  Distill knowledge:                │                              │
│  • Record full episode             │                              │
│  • Generate embedding              │                              │
│  • Tag with structured metadata    │                              │
│  • Compute pattern reliability     │                              │
│    (hierarchical Bayesian)         │                              │
└────────────────┬───────────────────┘                              │
                 │                                                  │
                 ▼                                                  │
┌────────────────────────────────────┐                              │
│  STEP 3: UPDATE                    │                              │
│                                    │                              │
│  Update knowledge base:            │                              │
│  • Adjust signal weights           │                              │
│    (statistically gated)           │                              │
│  • Update management rules         │                              │
│    (offline computation)           │                              │
│  • Retrain bandit posterior        │                              │
│  • Update pattern reliability      │                              │
│  • Check for concept drift         │                              │
└────────────────┬───────────────────┘                              │
                 │                                                  │
                 ▼                                                  │
┌────────────────────────────────────┐                              │
│  STEP 4: STORE                     │                              │
│                                    │                              │
│  Persist to appropriate layer:     │                              │
│  • Episode → Episodic (L4)         │                              │
│  • Lesson → Long-Term (L3)         │                              │
│  • Pattern → Long-Term (L3)        │                              │
│  • Signals → Short-Term (L2)       │                              │
└────────────────┬───────────────────┘                              │
                 │                                                  │
                 ▼                                                  │
┌────────────────────────────────────┐                              │
│  STEP 5: APPLY                     │                              │
│                                    │                              │
│  Next trade benefits:              │                              │
│  • Memory-augmented AlphaStack pipeline  │                              │
│  • Relevant episodes loaded        │                              │
│  • Refined parameters applied      │                              │
│  • Patterns with confidence scores │                              │
└────────────────┬───────────────────┘                              │
                 │                                                  │
                 ▼                                                  │
         Next Similar Scenario ─────────────────────────────────────┘
```

### 5.2 Step 1: Reflect — Post-Trade Analysis

After every trade closes, the Reflection Agent runs automatically:

```python
class ReflectionAgent:
    """
    Post-trade reflection with ablation-based causal attribution
    and counterfactual analysis.
    """

    def reflect(self, trade_id: str) -> ReflectionResult:
        # 1. Load trade episode
        episode = self.memory.get_trade_episode(trade_id)

        # 2. Run ablation attribution (Fix 6)
        attributions = self.causal_attribution.attribute_trade(episode)

        # 3. Compute counterfactuals (Fix 5)
        counterfactuals = self.counterfactual_tracker.compute_counterfactuals(episode)

        # 4. Identify key learnings
        learnings = self.extract_learnings(episode, attributions, counterfactuals)

        # 5. Check for concept drift (every 20 trades)
        if self.trade_counter % 20 == 0:
            drift = self.drift_detector.check_drift()
            if drift.level in ('AMBER', 'RED'):
                learnings.append(drift.to_learning())

        return ReflectionResult(
            trade_id=trade_id,
            attributions=attributions,
            counterfactuals=counterfactuals,
            learnings=learnings,
            episode=episode,
        )
```

### 5.3 Step 2: Extract — Knowledge Distillation

Lessons are extracted with structured metadata and confidence scores:

```python
@dataclass
class Lesson:
    lesson_id: str
    trade_id: str
    instrument: str
    regime: str
    session: str
    setup_type: str
    # What was learned
    category: str          # 'entry', 'exit', 'management', 'risk', 'timing'
    description: str       # Human-readable lesson
    rule: str              # Actionable rule ("If X, then Y")
    # Confidence
    confidence: float      # 0.0–1.0 (starts at 0.5, updated by evidence)
    sample_size: int       # Number of supporting observations
    confidence_interval: tuple[float, float]  # Beta posterior CI
    # Evidence
    supporting_trades: list[str]   # Trade IDs that support this lesson
    contradicting_trades: list[str] # Trade IDs that contradict this lesson
    # Metadata
    created_at: datetime
    last_reinforced: datetime
    last_contradicted: Optional[datetime]
    status: str            # 'active', 'decayed', 'archived', 'contradicted'
```

### 5.4 Step 3: Update — Knowledge Base Updates

All updates are **statistically gated**:

```python
class KnowledgeUpdater:
    """
    Updates knowledge base with statistical rigor.
    No update without evidence.
    """

    def update_from_reflection(self, reflection: ReflectionResult):
        # 1. Signal weights — only if p < 0.10 (Fix 4)
        for agent_id, attr in reflection.attributions.items():
            if attr.criticality > 0.1:  # Only meaningful attributions
                self.memory.update_signal_weight(
                    agent_id=agent_id,
                    symbol=reflection.episode.symbol,
                    adjustment=self.compute_adjustment(attr),
                    evidence=attr.to_dict()
                )

        # 2. Pattern reliability — hierarchical Bayesian (Fix 3)
        self.update_pattern_reliability(reflection)

        # 3. Contextual bandit — update posterior (Fix 1)
        context = self.build_context_vector(reflection.episode)
        for cf in reflection.counterfactuals:
            action = strategy_to_action(cf.strategy_name)
            self.bandit.update(context, action, cf.r_multiple)

        # 4. Management rules — offline recomputation (Fix 1)
        # Triggered nightly, not per-trade
        if self.should_recompute_rules():
            self.recompute_management_rules()

        # 5. Lessons — store or reinforce
        for learning in reflection.learnings:
            self.store_or_reinforce_lesson(learning)
```

### 5.5 Step 4: Store — Persistence

Data is stored to the appropriate layer:

| Data Type | Layer | Storage | TTL |
|-----------|-------|---------|-----|
| Trade episode (full) | Episodic (L4) | ClickHouse + pgvector | Indefinite (compress after 90d) |
| Trade journal entry | Long-Term (L3) | PostgreSQL | Indefinite |
| Lesson | Long-Term (L3) | PostgreSQL | Until decayed/archived |
| Pattern reliability | Long-Term (L3) | PostgreSQL | Until contradicted |
| Signal weights | Long-Term (L3) | PostgreSQL | Until reset by drift |
| Management rules | Long-Term (L3) | PostgreSQL | Until recomputed |
| Embedding vectors | Long-Term (L3) | pgvector | Same as parent record |
| Session signals | Short-Term (L2) | Redis | 24 hours |
| Tick data | Short-Term (L2) | Redis | 4 hours |
| Analysis context | Working (L1) | Python objects | Analysis cycle |

### 5.6 Step 5: Apply — Memory-Augmented Decisions

The AlphaStack pipeline is augmented with memory retrieval:

```python
class MemoryAugmentedPipeline:
    """
    AlphaStack pipeline with memory-augmented decision points.
    """

    def run_analysis(self, instrument: str, timeframe: str) -> StrategyContext:
        # Create working memory context
        ctx = self.memory.create_context(instrument, timeframe)

        # Steps 1-8: Standard AlphaStack pipeline
        ctx = self.step1_market_structure(ctx)
        ctx = self.step2_market_bias(ctx)
        # ... steps 3-8 ...

        # === MEMORY AUGMENTATION POINT ===
        # Load relevant past episodes and lessons
        memory_context = self.memory.get_memory_context(
            instrument=instrument,
            regime=ctx.regime,
            session=ctx.session,
            setup_type=ctx.setup_type,
        )
        ctx.past_episodes = memory_context.episodes        # Top-5 similar episodes
        ctx.lessons = memory_context.lessons                # Relevant lessons
        ctx.pattern_confidence = memory_context.pattern_win_rate  # Pattern reliability
        ctx.management_rules = memory_context.management_rules    # Optimal management
        ctx.signal_weights = memory_context.signal_weights        # Current weights

        # Steps 9-14: Decision steps with augmented context
        ctx = self.step9_rsi_confirmation(ctx)       # Now uses past RSI accuracy
        ctx = self.step10_entry_signal(ctx)          # Now uses pattern confidence
        ctx = self.step11_position_sizing(ctx)       # Now uses recent drawdown state
        ctx = self.step12_risk_check(ctx)            # Now uses historical limit breaches
        ctx = self.step13_take_profit(ctx)           # Now uses bandit-selected strategy
        ctx = self.step14_trade_management(ctx)      # Now uses learned management rules

        # Steps 15-16: Execution and journaling
        ctx = self.step15_execution(ctx)
        ctx = self.step16_journaling(ctx)

        return ctx
```

---

## 6. Schemas

### 6.1 Working Memory Schema (Layer 1)

```python
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
import uuid


@dataclass
class StrategyContext:
    """Working memory context for a single analysis cycle."""

    # Identity
    context_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.utcnow)

    # Instrument
    instrument: str = ""
    timeframe: str = ""

    # Market State (populated by Steps 1-8)
    market_structure: Optional[dict] = None
    bias: Optional[str] = None           # 'bullish', 'bearish', 'neutral'
    regime: Optional[str] = None         # 'trending', 'ranging', 'volatile'
    session: Optional[str] = None        # 'asian', 'london', 'new_york', 'overlap'
    volatility_state: Optional[str] = None

    # Technical Data
    candles: list = field(default_factory=list)
    indicators: dict = field(default_factory=dict)
    support_resistance: list = field(default_factory=list)
    order_blocks: list = field(default_factory=list)
    fvg_zones: list = field(default_factory=list)

    # Memory-Augmented Fields (populated by Memory Context Loader)
    past_episodes: list = field(default_factory=list)       # Similar past episodes
    lessons: list = field(default_factory=list)              # Relevant lessons
    pattern_confidence: Optional[dict] = None                # Pattern reliability stats
    management_rules: Optional[dict] = None                  # Optimal management params
    signal_weights: dict = field(default_factory=dict)       # Current signal weights

    # Decision Outputs (populated by Steps 9-16)
    entry_signal: Optional[dict] = None
    position_size: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit_strategy: Optional[str] = None  # Selected by contextual bandit
    risk_check_passed: bool = False
    order: Optional[dict] = None
    journal_entry: Optional[str] = None

    # State
    step_completed: int = 0
    is_valid: bool = True
    rejection_reason: Optional[str] = None

    def release(self):
        """Free resources held by this context."""
        self.candles.clear()
        self.indicators.clear()
        self.past_episodes.clear()
        self.lessons.clear()
        # Context is now eligible for garbage collection
```

### 6.2 Short-Term Memory Schemas (Layer 2 — Redis)

```yaml
# Redis Key Schemas

# ── Tick Cache ──
# Key: tick:{instrument}:{timestamp_ms}
# Type: Hash
# TTL: 4 hours (14400s)
# Fields: bid, ask, mid, volume, timestamp
# MAXLEN: 10000 per instrument (enforced by sorted set)
tick:EUR/USD:1720700000000:
  bid: 1.09501
  ask: 1.09503
  mid: 1.09502
  volume: 1250
  timestamp: "2026-07-11T14:30:00Z"

# ── Candle Cache ──
# Key: candle:{instrument}:{timeframe}:{timestamp_ms}
# Type: Hash
# TTL: 24 hours (86400s)
# MAXLEN: 1000 per instrument-timeframe combination
candle:EUR/USD:H1:1720700000000:
  open: 1.09450
  high: 1.09520
  low: 1.09430
  close: 1.09500
  volume: 15000
  timestamp: "2026-07-11T14:00:00Z"

# ── Signal Log ──
# Key: signal:{instrument}:{timestamp_ms}
# Type: Hash
# TTL: 24 hours (86400s)
# MAXLEN: 1000 per instrument
signal:EUR/USD:1720700000000:
  agent_id: "technical_analysis"
  direction: "bullish"
  confidence: 0.78
  score: 82.5
  timeframe: "H1"
  setup_type: "ob_bounce"
  generated_at: "2026-07-11T14:30:00Z"

# ── Active Position ──
# Key: position:{trade_id}
# Type: Hash
# TTL: None (deleted when trade closes)
# No MAXLEN (bounded by max concurrent positions, e.g., 10)
position:abc-123-def:
  instrument: "EUR/USD"
  direction: "long"
  entry_price: 1.09500
  stop_loss: 1.09350
  take_profit: 1.09800
  position_size: 0.10
  entry_time: "2026-07-11T14:30:00Z"
  status: "open"

# ── Session Performance ──
# Key: session:{session_type}:{date}
# Type: Hash
# TTL: 7 days (604800s)
session:london:2026-07-11:
  trades: 5
  wins: 3
  losses: 2
  total_pnl: 1.25
  total_r: 2.5

# ── Event Stream (Redis Streams) ──
# Key: events:{instrument}
# Type: Stream
# MAXLEN: 10000 (approximate trimming)
# TTL: 24 hours (86400s) via EXPIRE
events:EUR/USD:
  - type: "signal"
    data: '{"agent_id": "ta", "direction": "bullish"}'
    timestamp: "2026-07-11T14:30:00Z"
  - type: "trade_opened"
    data: '{"trade_id": "abc-123", "direction": "long"}'
    timestamp: "2026-07-11T14:31:00Z"

# ── Market Condition Cache ──
# Key: market:{instrument}
# Type: Hash
# TTL: 1 hour (3600s)
market:EUR/USD:
  regime: "trending_bullish"
  atr_14: 0.0045
  atr_ratio: 1.2
  volatility_state: "normal"
  correlation_usd_chf: 0.85
  last_updated: "2026-07-11T14:30:00Z"
```

### 6.3 Long-Term Memory Schemas (Layer 3 — PostgreSQL)

```sql
-- =============================================
-- TRADE JOURNAL
-- =============================================

CREATE TABLE trades (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instrument          VARCHAR(20) NOT NULL,
    direction           VARCHAR(10) NOT NULL,   -- 'long', 'short'
    entry_price         DECIMAL(18,8) NOT NULL,
    exit_price          DECIMAL(18,8),
    stop_loss           DECIMAL(18,8) NOT NULL,
    take_profit         DECIMAL(18,8),
    position_size       DECIMAL(18,8) NOT NULL,
    -- Outcome
    pnl_absolute        DECIMAL(18,4),
    pnl_pips            DECIMAL(10,2),
    r_multiple          DECIMAL(8,3),
    outcome             VARCHAR(10),            -- 'win', 'loss', 'breakeven'
    -- Context at entry
    regime              VARCHAR(30),
    session             VARCHAR(20),
    setup_type          VARCHAR(30),
    confluence_score    DECIMAL(6,2),
    -- Signals snapshot (all agent signals at entry)
    signals_snapshot    JSONB NOT NULL,
    -- Management
    management_path     VARCHAR(50),            -- 'conservative', 'balanced', 'aggressive'
    partial_closes      JSONB,
    trailing_stops      JSONB,
    -- Timing
    entry_time          TIMESTAMPTZ NOT NULL,
    exit_time           TIMESTAMPTZ,
    duration_minutes    DECIMAL(10,2),
    -- Audit
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_trades_instrument ON trades(instrument, entry_time DESC);
CREATE INDEX idx_trades_outcome ON trades(outcome, entry_time DESC);
CREATE INDEX idx_trades_regime ON trades(regime, instrument);

-- =============================================
-- SIGNAL LOG (all signals, not just trade-linked)
-- =============================================

CREATE TABLE signal_log (
    id                      SERIAL PRIMARY KEY,
    agent_id                VARCHAR(50) NOT NULL,
    symbol                  VARCHAR(20) NOT NULL,
    timeframe               VARCHAR(10),
    direction               VARCHAR(10) NOT NULL,
    confidence              DECIMAL(5,3),
    score                   DECIMAL(6,2),
    generated_at            TIMESTAMPTZ NOT NULL,
    led_to_trade            BOOLEAN DEFAULT FALSE,
    trade_id                UUID REFERENCES trades(id),
    filtered_by             VARCHAR(50),        -- 'risk_gate', 'confluence_low', NULL
    outcome                 VARCHAR(10),        -- 'win', 'loss', NULL
    regime                  VARCHAR(30),
    session                 VARCHAR(20),
    confluence_without      DECIMAL(6,2),
    was_correct_direction   BOOLEAN
);

CREATE INDEX idx_signal_log_agent ON signal_log(agent_id, symbol, generated_at);
CREATE INDEX idx_signal_log_filtered ON signal_log(filtered_by) WHERE led_to_trade = FALSE;

-- =============================================
-- SIGNAL WEIGHTS
-- =============================================

CREATE TABLE signal_weights (
    id                      SERIAL PRIMARY KEY,
    agent_id                VARCHAR(50) NOT NULL,
    symbol                  VARCHAR(20) NOT NULL,
    weight                  DECIMAL(5,4) NOT NULL DEFAULT 0.1000,
    -- Statistical tracking
    last_p_value            DECIMAL(8,6),
    last_attribution_category VARCHAR(30),
    adjustment_evidence     JSONB,
    n_attributions          INTEGER DEFAULT 0,
    n_predictions           INTEGER DEFAULT 0,
    accuracy                DECIMAL(5,4),
    -- Lifecycle
    last_adjustment         TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_signal_weight UNIQUE (agent_id, symbol),
    CONSTRAINT chk_weight_range CHECK (weight >= 0.05 AND weight <= 0.40)
);

-- =============================================
-- LESSONS
-- =============================================

CREATE TABLE lessons (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trade_id                UUID REFERENCES trades(id),
    instrument              VARCHAR(20) NOT NULL,
    regime                  VARCHAR(30),
    session                 VARCHAR(20),
    setup_type              VARCHAR(30),
    -- Lesson content
    category                VARCHAR(30) NOT NULL,   -- 'entry', 'exit', 'management', 'risk'
    description             TEXT NOT NULL,
    rule                    TEXT NOT NULL,
    -- Confidence (Bayesian)
    confidence              DECIMAL(5,4) NOT NULL DEFAULT 0.5000,
    sample_size             INTEGER NOT NULL DEFAULT 1,
    confidence_interval     DECIMAL(5,4)[],         -- [ci_low, ci_high]
    -- Evidence
    supporting_trades       UUID[] DEFAULT '{}',
    contradicting_trades    UUID[] DEFAULT '{}',
    -- Lifecycle
    status                  VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_reinforced         TIMESTAMPTZ,
    last_contradicted       TIMESTAMPTZ,
    -- Semantic search
    embedding               vector(768)             -- pgvector embedding
);

CREATE INDEX idx_lessons_instrument ON lessons(instrument, regime, session);
CREATE INDEX idx_lessons_category ON lessons(category, status);
CREATE INDEX idx_lessons_embedding ON lessons USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- =============================================
-- PATTERN RELIABILITY (Hierarchical Bayesian)
-- =============================================

CREATE TABLE pattern_reliability (
    id                      SERIAL PRIMARY KEY,
    -- Cell identifiers
    pattern_type            VARCHAR(50) NOT NULL,
    pattern_subtype         VARCHAR(50),
    symbol                  VARCHAR(20) NOT NULL,
    timeframe               VARCHAR(10),
    regime                  VARCHAR(30),
    session                 VARCHAR(20),
    -- Raw statistics
    total_occurrences       INTEGER NOT NULL DEFAULT 0,
    successful              INTEGER NOT NULL DEFAULT 0,
    failed                  INTEGER NOT NULL DEFAULT 0,
    -- Hierarchical estimates (recomputed nightly)
    win_rate_hierarchical   DECIMAL(6,4),
    ci_low                  DECIMAL(6,4),
    ci_high                 DECIMAL(6,4),
    effective_n             DECIMAL(8,1),
    shrinkage_weight        DECIMAL(5,3),
    -- Time-weighted estimates
    win_rate_ew             DECIMAL(6,4),
    ew_effective_n          DECIMAL(8,1),
    -- Other statistics
    avg_rr                  DECIMAL(6,3),
    avg_duration_hours      DECIMAL(6,2),
    -- Confidence classification (computed)
    confidence              VARCHAR(10) GENERATED ALWAYS AS (
        CASE
            WHEN total_occurrences >= 30 THEN 'HIGH'
            WHEN total_occurrences >= 10 THEN 'MEDIUM'
            ELSE 'LOW'
        END
    ) STORED,
    -- Timestamps
    last_updated            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_pattern_cell UNIQUE (pattern_type, pattern_subtype, symbol,
                                        timeframe, regime, session)
);

CREATE INDEX idx_pattern_reliability_lookup
ON pattern_reliability (pattern_type, symbol, regime)
WHERE total_occurrences > 0;

-- =============================================
-- MANAGEMENT RULES (offline-computed lookup)
-- =============================================

CREATE TABLE management_rules (
    rule_id             SERIAL PRIMARY KEY,
    symbol              VARCHAR(20) NOT NULL,
    regime              VARCHAR(30) NOT NULL,
    session             VARCHAR(20) NOT NULL,
    setup_type          VARCHAR(30) NOT NULL,
    -- Optimal parameters
    be_trigger_r        DECIMAL(4,2) NOT NULL,
    partial_1_r         DECIMAL(4,2),
    partial_1_pct       DECIMAL(4,2),
    partial_2_r         DECIMAL(4,2),
    partial_2_pct       DECIMAL(4,2),
    trail_atr_mult      DECIMAL(4,2),
    time_exit_hours     DECIMAL(6,2),
    -- Statistics
    sample_size         INTEGER NOT NULL,
    avg_rr              DECIMAL(6,3),
    win_rate            DECIMAL(5,4),
    computed_at         TIMESTAMPTZ NOT NULL,
    -- Validity
    active              BOOLEAN DEFAULT TRUE,
    CONSTRAINT uq_management_rule UNIQUE (symbol, regime, session, setup_type)
);

-- =============================================
-- TRADE COUNTERFACTUALS (shadow tracking)
-- =============================================

CREATE TABLE trade_counterfactuals (
    id                  SERIAL PRIMARY KEY,
    trade_id            UUID NOT NULL REFERENCES trades(id),
    strategy_name       VARCHAR(50) NOT NULL,
    -- Hypothetical outcome
    exit_price          DECIMAL(18,8),
    exit_time           TIMESTAMPTZ,
    exit_reason         VARCHAR(30),
    total_pnl           DECIMAL(18,4),
    r_multiple          DECIMAL(8,3),
    duration_hours      DECIMAL(8,2),
    partial_closes      JSONB,
    -- Comparison to actual
    pnl_vs_actual       DECIMAL(18,4),
    r_vs_actual         DECIMAL(8,3),
    -- Metadata
    computed_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_counterfactual UNIQUE (trade_id, strategy_name)
);

CREATE INDEX idx_counterfactuals_trade ON trade_counterfactuals(trade_id);
CREATE INDEX idx_counterfactuals_strategy ON trade_counterfactuals(strategy_name);

-- =============================================
-- TRADE ATTRIBUTIONS (ablation-based)
-- =============================================

CREATE TABLE trade_attributions (
    id                  SERIAL PRIMARY KEY,
    trade_id            UUID NOT NULL REFERENCES trades(id),
    agent_id            VARCHAR(50) NOT NULL,
    -- Attribution scores
    criticality         DECIMAL(5,3),
    predictiveness      DECIMAL(5,3),
    contribution        DECIMAL(5,3),
    category            VARCHAR(30),        -- 'CRITICAL_CORRECT', 'CRITICAL_WRONG', etc.
    confluence_drop     DECIMAL(6,1),
    would_have_traded   BOOLEAN,
    flipped_confluence  DECIMAL(6,1),
    -- Metadata
    computed_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_attribution UNIQUE (trade_id, agent_id)
);

CREATE INDEX idx_attributions_trade ON trade_attributions(trade_id);
CREATE INDEX idx_attributions_agent ON trade_attributions(agent_id, category);

-- =============================================
-- AGENT INTERACTIONS (synergy tracking)
-- =============================================

CREATE TABLE agent_interactions (
    agent_a             VARCHAR(50) NOT NULL,
    agent_b             VARCHAR(50) NOT NULL,
    symbol              VARCHAR(20) NOT NULL,
    regime              VARCHAR(30),
    -- Statistics
    agree_count         INTEGER DEFAULT 0,
    agree_wins          INTEGER DEFAULT 0,
    disagree_count      INTEGER DEFAULT 0,
    disagree_wins       INTEGER DEFAULT 0,
    synergy_score       DECIMAL(5,3),
    last_updated        TIMESTAMPTZ,
    CONSTRAINT uq_interaction UNIQUE (agent_a, agent_b, symbol, regime)
);

-- =============================================
-- DRIFT DETECTION STATE
-- =============================================

CREATE TABLE drift_state (
    detector_id         VARCHAR(50) PRIMARY KEY,
    detector_type       VARCHAR(30) NOT NULL,   -- 'page_hinkley', 'regime_hmm'
    state               JSONB NOT NULL,
    last_drift_score    DECIMAL(5,3),
    last_drift_level    VARCHAR(10),
    last_check          TIMESTAMPTZ,
    last_drift_detected TIMESTAMPTZ
);
```

### 6.4 Episodic Memory Schemas (Layer 4 — ClickHouse + pgvector)

```sql
-- =============================================
-- TRADE EPISODES (ClickHouse)
-- =============================================

CREATE TABLE trade_episodes (
    -- Identity
    trade_id            UUID,
    instrument          String,
    direction           String,

    -- Timing
    entry_time          DateTime64(3),
    exit_time           DateTime64(3),
    duration_minutes    Float64,

    -- Context at entry
    regime              String,
    session             String,
    setup_type          String,
    confluence_score    Float32,
    volatility_state    String,

    -- Outcome
    outcome             String,             -- 'win', 'loss', 'breakeven'
    pnl_absolute        Float64,
    pnl_pips            Float64,
    r_multiple          Float64,

    -- Full reasoning chain (compressed JSON)
    reasoning_chain     String CODEC(ZSTD(3)),

    -- Signals snapshot
    signals_snapshot    String CODEC(ZSTD(3)),

    -- Market data summary (compressed)
    market_context      String CODEC(ZSTD(3)),

    -- Embedding (for vector similarity)
    -- Stored in pgvector, linked by trade_id

    -- Metadata
    created_at          DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(entry_time)
ORDER BY (instrument, entry_time)
TTL entry_time + INTERVAL 90 DAY RECOMPRESS CODEC(ZSTD(9)),
    entry_time + INTERVAL 730 DAY DELETE
SETTINGS index_granularity = 8192;

-- =============================================
-- EPISODE EMBEDDINGS (pgvector in PostgreSQL)
-- =============================================

CREATE TABLE episode_embeddings (
    trade_id            UUID PRIMARY KEY REFERENCES trades(id),
    -- Text embedding of reasoning chain + context
    embedding           vector(768) NOT NULL,
    -- Structured tags for hybrid search
    instrument          VARCHAR(20) NOT NULL,
    regime              VARCHAR(30),
    session             VARCHAR(20),
    setup_type          VARCHAR(30),
    outcome             VARCHAR(10),
    direction           VARCHAR(10),
    r_multiple          DECIMAL(8,3),
    -- Metadata
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_episode_embedding ON episode_embeddings
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE INDEX idx_episode_structured ON episode_embeddings(instrument, regime, session, outcome);
```

---

## 7. Lifecycle Policies

### 7.1 Data Lifecycle State Machine

```
                    ┌─────────┐
          create    │  ACTIVE │
         ──────────▶│         │
                    └────┬────┘
                         │
              ┌──────────┼──────────┐
              ▼          ▼          ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │REINFORCED│ │ DECAYING │ │CONTRADICTED│
        │(accessed │ │(no access│ │(counter-  │
        │ recently)│ │ > TTL)   │ │ evidence) │
        └────┬─────┘ └────┬─────┘ └────┬─────┘
             │            │             │
             └────────────┼─────────────┘
                          ▼
                    ┌──────────┐
                    │ ARCHIVED │
                    │(cold     │
                    │ storage) │
                    └────┬─────┘
                         │
                         ▼
                    ┌──────────┐
                    │ DELETED  │
                    └──────────┘
```

### 7.2 TTL Policies by Layer

| Layer | Data Type | TTL | Trigger | Action |
|-------|-----------|-----|---------|--------|
| **L1 Working** | StrategyContext | Analysis cycle (~5min) | Pipeline complete | Release + GC |
| **L2 Short-Term** | Tick data | 4 hours | TTL expiry | Auto-delete |
| **L2 Short-Term** | Candle data | 24 hours | TTL expiry | Auto-delete |
| **L2 Short-Term** | Signal log | 24 hours | TTL expiry | Promote to L3 if trade-linked |
| **L2 Short-Term** | Active position | Trade lifetime | Trade closes | Promote to L3 |
| **L2 Short-Term** | Session stats | 7 days | TTL expiry | Promote summary to L3 |
| **L2 Short-Term** | Event streams | 24 hours | TTL + MAXLEN | Auto-trim |
| **L2 Short-Term** | Market condition cache | 1 hour | TTL expiry | Auto-delete |
| **L3 Long-Term** | Trade journal | Indefinite | — | Archive after 2 years |
| **L3 Long-Term** | Lessons (active) | Indefinite | Relevance review | Decay or archive |
| **L3 Long-Term** | Lessons (decayed) | 90 days after decay | TTL expiry | Archive to S3 |
| **L3 Long-Term** | Pattern reliability | Indefinite | Weekly recompute | Update or deactivate |
| **L3 Long-Term** | Signal weights | Indefinite | Drift reset | Reset to uniform |
| **L3 Long-Term** | Management rules | Until recomputed | Monthly cron | Overwrite |
| **L3 Long-Term** | Counterfactuals | 1 year | TTL expiry | Archive to S3 |
| **L3 Long-Term** | Attributions | 1 year | TTL expiry | Archive to S3 |
| **L4 Episodic** | Trade episodes (raw) | 90 days | TTL | Recompress (ZSTD 9) |
| **L4 Episodic** | Trade episodes (compressed) | 2 years | TTL | Archive to S3, delete from CH |
| **L4 Episodic** | Embeddings | Same as parent | Parent TTL | Delete with parent |

### 7.3 Decay Rules

Memories decay when they lose relevance. Decay is **gradual**, not binary:

```python
class MemoryDecayEngine:
    """
    Applies gradual confidence decay to stale memories.
    """

    # Decay rates (confidence loss per day of inaccess)
    DECAY_RATES = {
        'lesson': 0.002,           # 0.2% per day → half-life ~347 days
        'pattern': 0.005,          # 0.5% per day → half-life ~139 days
        'signal_weight': 0.001,    # 0.1% per day → half-life ~693 days
    }

    # Minimum confidence before auto-archive
    ARCHIVE_THRESHOLDS = {
        'lesson': 0.10,
        'pattern': 0.15,
        'signal_weight': 0.05,
    }

    def apply_decay(self):
        """Run daily decay pass on all active memories."""
        # Lessons
        lessons = db.execute("""
            SELECT id, confidence, last_reinforced
            FROM lessons
            WHERE status = 'active'
              AND last_reinforced < NOW() - INTERVAL '7 days'
        """)
        for lesson in lessons:
            days_since = (now() - lesson['last_reinforced']).days
            decay = self.DECAY_RATES['lesson'] * days_since
            new_conf = max(0, lesson['confidence'] - decay)

            if new_conf < self.ARCHIVE_THRESHOLDS['lesson']:
                db.execute("""
                    UPDATE lessons SET status = 'archived', confidence = %s
                    WHERE id = %s
                """, [new_conf, lesson['id']])
            else:
                db.execute("""
                    UPDATE lessons SET confidence = %s WHERE id = %s
                """, [new_conf, lesson['id']])

        # Patterns — similar logic
        # Signal weights — similar logic (but reset to uniform instead of archive)
```

### 7.4 Consolidation Schedule

| Task | Frequency | Scope | Duration |
|------|-----------|-------|----------|
| Session reset | Every session boundary (4h/8h) | L2 short-term data | ~1s |
| Daily consolidation | 00:00 UTC daily | Promote L2 → L3, run decay | ~30s |
| Pattern recomputation | 02:00 UTC daily | Hierarchical Bayesian update | ~2min |
| Management rule recompute | 03:00 UTC weekly (Sunday) | Grid search over parameters | ~10min |
| Episode embedding | After each trade close | Generate + store embedding | ~500ms |
| Drift check | Every 20 trades | Page-Hinkley + HMM | ~2s |
| Memory audit | 04:00 UTC daily | Redis key count, memory usage | ~5s |
| Full memory review | Monthly (1st of month) | Review all active lessons/patterns | ~5min |
| S3 archival | Weekly (Sunday 05:00 UTC) | Archive data > 2 years | ~30min |
| Backup | Daily (03:30 UTC) | PostgreSQL pg_dump + Redis BGSAVE | ~5min |

---

## 8. Redis Unbounded Growth Prevention

Redis is the highest-risk component for memory leaks in 24/7 operation. Every strategy below is **mandatory**, not optional.

### 8.1 TTL Enforcement

**Rule: Every Redis key MUST have a TTL. No exceptions.**

```python
# Enforced at write time
class RedisShortTermStore:
    """Short-term memory store with mandatory TTL enforcement."""

    # TTLs by key pattern
    TTL_CONFIG = {
        'tick:*':       14400,      # 4 hours
        'candle:*':     86400,      # 24 hours
        'signal:*':     86400,      # 24 hours
        'position:*':   None,       # No TTL (deleted on trade close)
        'session:*':    604800,     # 7 days
        'market:*':     3600,       # 1 hour
        'events:*':     86400,      # 24 hours
    }

    # Maximum keys per pattern
    MAXLEN_CONFIG = {
        'tick:*':       10000,      # Per instrument
        'candle:*':     1000,       # Per instrument-timeframe
        'signal:*':     1000,       # Per instrument
        'position:*':   10,         # Global max concurrent positions
        'events:*':     10000,      # Per instrument (stream MAXLEN)
    }

    def set_with_ttl(self, key: str, value: dict, ttl_override: int = None):
        """Set a key with mandatory TTL."""
        ttl = ttl_override or self._get_ttl_for_key(key)
        if ttl is None:
            # Only allowed for position:* keys
            if not key.startswith('position:'):
                raise ValueError(f"No TTL configured for key pattern: {key}")

        pipe = self.redis.pipeline()
        pipe.hset(key, mapping=value)
        if ttl is not None:
            pipe.expire(key, ttl)
        pipe.execute()

    def xadd_with_maxlen(self, stream: str, data: dict, maxlen: int = 10000):
        """Add to stream with MAXLEN trimming."""
        self.redis.xadd(stream, data, maxlen=maxlen, approximate=True)

    def _get_ttl_for_key(self, key: str) -> Optional[int]:
        """Get TTL for a key based on pattern matching."""
        for pattern, ttl in self.TTL_CONFIG.items():
            if self._matches_pattern(key, pattern):
                return ttl
        raise ValueError(f"Unknown key pattern: {key}")
```

### 8.2 MAXLEN Enforcement on Streams

```python
# All Redis Streams use MAXLEN to prevent unbounded growth
STREAM_CONFIGS = {
    'events:EUR/USD': {'maxlen': 10000},
    'events:GBP/USD': {'maxlen': 10000},
    'events:USD/JPY': {'maxlen': 10000},
    'audit:orders':    {'maxlen': 50000},
    'audit:signals':   {'maxlen': 50000},
}
```

### 8.3 Daily Key Audit

```python
class RedisKeyAuditor:
    """
    Daily audit of Redis keys for TTL compliance and count limits.
    Runs at 04:00 UTC daily.
    """

    def audit(self) -> AuditResult:
        result = AuditResult()

        # 1. Find keys without TTL
        all_keys = self.redis.keys('*')
        no_ttl_keys = []
        for key in all_keys:
            ttl = self.redis.ttl(key)
            if ttl == -1:  # No TTL set
                no_ttl_keys.append(key)

        if no_ttl_keys:
            result.violations['no_ttl'] = no_ttl_keys
            # Auto-fix: apply default TTL
            for key in no_ttl_keys:
                default_ttl = self._get_default_ttl(key)
                if default_ttl:
                    self.redis.expire(key, default_ttl)

        # 2. Count keys by pattern
        for pattern in self.TTL_CONFIG:
            count = len(self.redis.keys(pattern))
            result.key_counts[pattern] = count
            max_count = self.MAXLEN_CONFIG.get(pattern, 100000)
            if count > max_count:
                result.violations[f'exceeds_maxlen:{pattern}'] = count

        # 3. Memory usage
        info = self.redis.info('memory')
        result.used_memory_bytes = info['used_memory']
        result.used_memory_peak = info['used_memory_peak']

        if info['used_memory'] > 2 * 1024**3:  # > 2GB
            result.alerts.append('CRITICAL: Redis memory > 2GB')

        return result
```

### 8.4 Memory Monitoring Alerts

```yaml
redis_monitoring:
  metrics:
    used_memory_bytes:
      alert: "> 1GB"
      critical: "> 2GB"
      action: "Flush expired keys, compress streams"
    used_memory_peak:
      alert: "> 1.5GB"
      action: "Review peak usage patterns"
    connected_clients:
      alert: "> 100"
      critical: "> 200"
      action: "Check for connection leaks"
    keyspace_hits_ratio:
      alert: "< 0.80"
      action: "Review key patterns and access patterns"
    evicted_keys:
      alert: "> 1000/hour"
      action: "Review TTL settings, consider maxmemory-policy"
    fragmented_memory:
      alert: "frag_ratio > 1.5"
      action: "Run MEMORY PURGE or restart Redis"
```

---

## 9. Semantic Search Over Trade History

### 9.1 Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│              TRADE HISTORY SEMANTIC SEARCH                            │
│                                                                      │
│  QUERY: "EUR/USD London session bullish order block bounce"          │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  STEP 1: STRUCTURED FILTER (PostgreSQL, fast)                │   │
│  │                                                              │   │
│  │  SELECT trade_id FROM episode_embeddings                     │   │
│  │  WHERE instrument = 'EUR/USD'                                │   │
│  │    AND session = 'london'                                    │   │
│  │    AND regime = 'trending_bullish'                           │   │
│  │    AND outcome = 'win'                                       │   │
│  │                                                              │   │
│  │  Result: ~50 candidate trade_ids (fast index scan)           │   │
│  └──────────────────────────────┬───────────────────────────────┘   │
│                                 │                                    │
│                                 ▼                                    │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  STEP 2: SEMANTIC RANK (pgvector, <50ms)                     │   │
│  │                                                              │   │
│  │  SELECT trade_id,                                           │   │
│  │         embedding <=> $query_embedding AS similarity         │   │
│  │  FROM episode_embeddings                                     │   │
│  │  WHERE trade_id = ANY($candidates)                           │   │
│  │  ORDER BY similarity                                         │   │
│  │  LIMIT 5                                                     │   │
│  │                                                              │   │
│  │  Result: Top-5 most similar episodes by embedding distance   │   │
│  └──────────────────────────────┬───────────────────────────────┘   │
│                                 │                                    │
│                                 ▼                                    │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  STEP 3: RECENCY BOOST + FINAL RANKING                       │   │
│  │                                                              │   │
│  │  final_score = similarity * 0.7 + recency_weight * 0.3       │   │
│  │  recency_weight = exp(-0.01 * days_ago)                      │   │
│  │                                                              │   │
│  │  Result: Re-ranked by relevance × recency                    │   │
│  └──────────────────────────────┬───────────────────────────────┘   │
│                                 │                                    │
│                                 ▼                                    │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  STEP 4: CONTEXT ENRICHMENT                                  │   │
│  │                                                              │   │
│  │  For each top-5 episode:                                     │   │
│  │  - Load full episode from ClickHouse                         │   │
│  │  - Include reasoning chain, signals, outcome                 │   │
│  │  - Include counterfactual data                               │   │
│  │  - Include attribution scores                                │   │
│  │                                                              │   │
│  │  Result: Full context for each similar past episode          │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  PERFORMANCE TARGETS                                                 │
│  - Structured filter: <5ms (PostgreSQL index scan)                   │
│  - Semantic rank: <50ms (pgvector IVFFlat, 100K vectors)            │
│  - Context enrichment: <50ms (ClickHouse point query × 5)           │
│  - Total: <105ms end-to-end                                         │
└─────────────────────────────────────────────────────────────────────┘
```

### 9.2 Embedding Strategy

**Phase 1**: Hybrid approach — structured tags for exact filtering + generic embeddings for semantic ranking.

```python
from sentence_transformers import SentenceTransformer

class EpisodeEmbedder:
    """
    Generates embeddings for trade episodes.
    Phase 1: Generic sentence transformer
    Phase 2: Financial-domain embeddings (FinBERT)
    Phase 3: Custom fine-tuned on trade history
    """

    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        self.model = SentenceTransformer(model_name)
        self.embedding_dim = 384  # all-MiniLM-L6-v2 dimension

    def embed_episode(self, episode: dict) -> list[float]:
        """
        Generate embedding from episode reasoning chain + context.
        Combines multiple text fields into a single embedding.
        """
        # Build text representation
        text_parts = [
            f"Instrument: {episode['instrument']}",
            f"Direction: {episode['direction']}",
            f"Setup: {episode['setup_type']}",
            f"Regime: {episode['regime']}",
            f"Session: {episode['session']}",
            f"Reasoning: {episode['reasoning_chain']}",
            f"Outcome: {episode['outcome']} ({episode['r_multiple']}R)",
        ]
        text = " | ".join(text_parts)

        # Generate embedding
        embedding = self.model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    def embed_query(self, query: str) -> list[float]:
        """Generate embedding for a search query."""
        embedding = self.model.encode(query, normalize_embeddings=True)
        return embedding.tolist()
```

### 9.3 Query Interface

```python
class SemanticSearchService:
    """
    Hybrid semantic + structured search over trade history.
    """

    def search(self, query: str, filters: dict, limit: int = 5,
               recency_weight: float = 0.3) -> list[SearchResult]:
        """
        Search for similar trade episodes.

        Args:
            query: Natural language query (e.g., "EUR/USD London session bullish OB bounce")
            filters: Structured filters (e.g., {'instrument': 'EUR/USD', 'outcome': 'win'})
            limit: Number of results to return
            recency_weight: Weight of recency in final ranking (0-1)

        Returns:
            List of SearchResult with episode data and similarity scores
        """
        # Step 1: Structured filter
        candidates = self._structured_filter(filters)

        if not candidates:
            return []

        # Step 2: Semantic rank
        query_embedding = self.embedder.embed_query(query)
        ranked = self._semantic_rank(query_embedding, candidates, limit=limit * 2)

        # Step 3: Recency boost
        final_ranked = self._apply_recency_boost(ranked, recency_weight)

        # Step 4: Context enrichment
        results = []
        for item in final_ranked[:limit]:
            episode = self._load_episode(item['trade_id'])
            results.append(SearchResult(
                trade_id=item['trade_id'],
                similarity=item['similarity'],
                recency_weight=item['recency_weight'],
                final_score=item['final_score'],
                episode=episode,
            ))

        return results

    def _structured_filter(self, filters: dict) -> list[str]:
        """Fast structured filter using PostgreSQL indexes."""
        conditions = []
        params = []
        for key, value in filters.items():
            conditions.append(f"{key} = %s")
            params.append(value)

        where_clause = " AND ".join(conditions) if conditions else "TRUE"

        rows = self.db.execute(f"""
            SELECT trade_id FROM episode_embeddings
            WHERE {where_clause}
        """, params)

        return [row['trade_id'] for row in rows]

    def _semantic_rank(self, query_embedding: list[float],
                       candidates: list[str], limit: int) -> list[dict]:
        """Rank candidates by vector similarity using pgvector."""
        rows = self.db.execute("""
            SELECT trade_id,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM episode_embeddings
            WHERE trade_id = ANY(%s)
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """, [query_embedding, candidates, query_embedding, limit])

        return [{'trade_id': row['trade_id'], 'similarity': row['similarity']}
                for row in rows]

    def _apply_recency_boost(self, ranked: list[dict],
                              recency_weight: float) -> list[dict]:
        """Apply recency weighting to similarity scores."""
        import math
        from datetime import datetime, timezone

        for item in ranked:
            episode = self.db.execute("""
                SELECT entry_time FROM trades WHERE id = %s
            """, [item['trade_id']])[0]

            days_ago = (datetime.now(timezone.utc) - episode['entry_time']).days
            recency = math.exp(-0.01 * days_ago)

            similarity_weight = 1.0 - recency_weight
            item['recency_weight'] = recency
            item['final_score'] = (
                item['similarity'] * similarity_weight +
                recency * recency_weight
            )

        return sorted(ranked, key=lambda x: x['final_score'], reverse=True)
```

---

## 10. Disaster Recovery Procedures

### 10.1 Failure Scenarios

| Scenario | Impact | Recovery Time | Data Loss |
|----------|--------|---------------|-----------|
| **Redis crash** | Short-term data lost (ticks, signals, active positions) | <1 min (auto-restart) | Last tick/signal data (acceptable) |
| **PostgreSQL corruption** | All long-term memory lost | Hours (restore from backup) | Up to 24 hours of trades |
| **ClickHouse failure** | Episodic data inaccessible | Hours (restore from backup) | Up to 24 hours of episodes |
| **Full disk** | All writes fail | Minutes (clear space) | None if handled gracefully |
| **Network partition** | Agents can't reach memory | Minutes (auto-reconnect) | None (queues buffer) |
| **Embedding model failure** | Semantic search unavailable | Minutes (restart service) | None (structured search still works) |
| **Memory Manager crash** | All memory operations stop | <1 min (auto-restart) | In-flight operations may be lost |

### 10.2 Backup Strategy

```yaml
backup_strategy:
  postgresql:
    method: "pg_dump + WAL archiving"
    schedule:
      full_backup: "daily at 03:30 UTC"
      wal_archiving: "continuous (archive_command)"
    retention:
      daily_backups: 7 days
      weekly_backups: 4 weeks
      monthly_backups: 12 months
    storage: "S3 (encrypted, versioned)"
    restore_test: "monthly (automated)"

  redis:
    method: "BGSAVE + AOF"
    schedule:
      bgsave: "every 6 hours"
      aof_rewrite: "auto (when AOF > 64MB)"
    persistence:
      aof_fsync: "everysec"  # Balance between safety and performance
      rdb_save: "900 1 300 10 60 10000"  # Save if 1 key in 15min, 10 in 5min, 10000 in 1min
    retention:
      rdb_files: 3 most recent
    storage: "local + S3 (daily upload)"
    restore_test: "monthly"

  clickhouse:
    method: "clickhouse-backup"
    schedule:
      full_backup: "weekly (Sunday 04:00 UTC)"
      incremental: "daily at 04:00 UTC"
    retention:
      daily_backups: 7 days
      weekly_backups: 4 weeks
    storage: "S3 (encrypted)"
    restore_test: "monthly"

  s3_archive:
    method: "S3 lifecycle policies"
    schedule: "weekly archival of data > 2 years"
    retention:
      standard: "2 years"
      glacier: "5 years"
      deep_archive: "10 years"
    encryption: "AES-256 (SSE-S3)"
```

### 10.3 Recovery Procedures

```python
class DisasterRecovery:
    """
    Disaster recovery procedures for the memory system.
    """

    # ── Redis Recovery ──

    def recover_redis(self):
        """
        Recovery procedure for Redis crash/restart.

        1. Redis auto-restarts (systemd/supervisor)
        2. AOF replay restores recent data (up to last fsync)
        3. If AOF corrupted: restore from latest RDB snapshot
        4. If RDB also corrupted: start fresh (short-term data loss acceptable)
        5. Rebuild hot cache from PostgreSQL (recent candles, active positions)
        """
        # Step 1: Check if Redis is up
        if not self.redis.ping():
            logger.error("Redis is down. Waiting for auto-restart...")
            self.wait_for_redis(timeout=60)

        # Step 2: Check data integrity
        key_count = self.redis.dbsize()
        if key_count == 0:
            logger.warning("Redis is empty. Rebuilding from PostgreSQL...")
            self._rebuild_redis_from_pg()

        # Step 3: Verify active positions
        self._verify_active_positions()

    def _rebuild_redis_from_pg(self):
        """Rebuild Redis hot cache from PostgreSQL."""
        # Reload active positions
        positions = self.db.execute("""
            SELECT * FROM trades WHERE exit_time IS NULL
        """)
        for pos in positions:
            self.redis.hset(f"position:{pos['id']}", mapping=pos)
            # No TTL on positions (deleted when trade closes)

        # Reload recent candles (last 24 hours)
        for instrument in self.instruments:
            candles = self.db.execute("""
                SELECT * FROM candle_data
                WHERE instrument = %s AND time > NOW() - INTERVAL '24 hours'
                ORDER BY time DESC LIMIT 1000
            """, [instrument])
            for candle in candles:
                self.redis.hset(
                    f"candle:{instrument}:{candle['timeframe']}:{int(candle['time'].timestamp() * 1000)}",
                    mapping=candle
                )
                self.redis.expire(
                    f"candle:{instrument}:{candle['timeframe']}:{int(candle['time'].timestamp() * 1000)}",
                    86400
                )

        logger.info(f"Redis rebuilt: {self.redis.dbsize()} keys")

    # ── PostgreSQL Recovery ──

    def recover_postgresql(self):
        """
        Recovery procedure for PostgreSQL failure.

        1. Check if PostgreSQL is accessible
        2. If corrupted: restore from latest backup
        3. Replay WAL logs to minimize data loss
        4. Verify data integrity (checksums)
        5. Restart Memory Manager
        """
        # Step 1: Check connectivity
        if not self.db.ping():
            logger.error("PostgreSQL is down. Initiating recovery...")
            self._start_pg_recovery()

        # Step 2: Verify integrity
        result = self.db.execute("SELECT pg_catalog.pg_stat_get_db_xact_commit(oid) FROM pg_database WHERE datname = current_database()")
        if not result:
            logger.error("PostgreSQL integrity check failed. Restoring from backup...")
            self._restore_from_backup('postgresql')

        # Step 3: Verify critical tables
        for table in ['trades', 'lessons', 'signal_weights', 'pattern_reliability']:
            count = self.db.execute(f"SELECT COUNT(*) FROM {table}")[0]
            logger.info(f"Table {table}: {count} rows")

    def _restore_from_backup(self, component: str):
        """Restore a component from latest S3 backup."""
        # Download latest backup
        backup_key = self.s3.list_objects(
            Bucket='alpha-stack-backups',
            Prefix=f'{component}/latest'
        )[0]['Key']

        local_path = f'/tmp/restore_{component}'
        self.s3.download_file('alpha-stack-backups', backup_key, local_path)

        # Restore
        if component == 'postgresql':
            subprocess.run(['pg_restore', '-d', 'alpha_stack', local_path], check=True)
        elif component == 'clickhouse':
            subprocess.run(['clickhouse-backup', 'restore', 'latest'], check=True)

        logger.info(f"Restored {component} from {backup_key}")

    # ── Graceful Degradation ──

    def operate_without_memory(self):
        """
        When memory is unavailable, operate in conservative mode.

        - No memory-augmented decisions (skip Step 9-14 memory injection)
        - Use default signal weights (uniform 0.10)
        - Use default management rules (conservative TP)
        - Log all decisions as "memory-blind" for later review
        - Reduce position sizes by 50%
        - Alert human operator
        """
        logger.warning("Operating in MEMORY-BLIND mode. Reduced position sizes.")
        self.alert(
            severity='CRITICAL',
            title='Memory system offline — operating conservatively',
            message='Memory Manager is unreachable. Trading with default parameters '
                    'and 50% position sizes. Review all trades manually.'
        )

        # Set global flag
        self.config['memory_available'] = False
        self.config['position_size_multiplier'] = 0.5
        self.config['default_signal_weight'] = 0.10
```

### 10.4 Recovery Time Objectives

| Component | RTO | RPO | Method |
|-----------|-----|-----|--------|
| Redis | <1 min | 1 sec (AOF) | Auto-restart + AOF replay |
| PostgreSQL | <30 min | 15 min (WAL) | pg_restore + WAL replay |
| ClickHouse | <1 hour | 24 hours | clickhouse-backup restore |
| Memory Manager | <1 min | 0 (stateless) | Process restart |
| Full system | <2 hours | 24 hours | Sequential restore |

---

## 11. Integration with Agents and Trading Engine

### 11.1 Agent Integration Points

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    AGENT-MEMORY INTEGRATION MAP                          │
│                                                                          │
│  STRATEGY AGENT ─────────────────────────────────────────────────────┐  │
│  │ • Writes: StrategyContext (L1), signals (L2)                      │  │
│  │ • Reads:  Past episodes (L4), lessons (L3), patterns (L3)        │  │
│  │ • Trigger: Every analysis cycle                                   │  │
│  │ • API: memory.get_memory_context() → MemoryContext                │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  RISK AGENT ─────────────────────────────────────────────────────────┐  │
│  │ • Writes: Risk limit breaches (L2), risk lessons (L3)             │  │
│  │ • Reads:  Historical limit breaches (L3), drawdown state (L2)    │  │
│  │ • Trigger: Every trade proposal (Step 12)                         │  │
│  │ • API: memory.query_lessons(category='risk', instrument=X)        │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  NEWS AGENT ─────────────────────────────────────────────────────────┐  │
│  │ • Writes: News events (L2), sentiment scores (L2)                 │  │
│  │ • Reads:  Past event reactions (L4), source reliability (L3)      │  │
│  │ • Trigger: News event detected                                    │  │
│  │ • API: memory.search_similar_episodes("Fed rate decision")        │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  JOURNAL AGENT ──────────────────────────────────────────────────────┐  │
│  │ • Writes: Trade journal entries (L3), episodes (L4)               │  │
│  │ • Reads:  Raw trade data (L2), signals (L2)                      │  │
│  │ • Trigger: Trade closes                                           │  │
│  │ • API: memory.store_trade(), memory.store_episode()               │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  REFLECTION AGENT ───────────────────────────────────────────────────┐  │
│  │ • Writes: Lessons (L3), attributions (L3), patterns (L3)          │  │
│  │ • Reads:  Trade episodes (L4), counterfactuals (L3)               │  │
│  │ • Trigger: After Journal Agent completes (async, background)       │  │
│  │ • API: memory.run_reflection(trade_id) → ReflectionResult          │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  AUDITOR AGENT ──────────────────────────────────────────────────────┐  │
│  │ • Reads:  All layers (audit queries)                              │  │
│  │ • Writes: Audit reports (L3)                                      │  │
│  │ • Trigger: Weekly cron (Sunday 10:00 UTC)                         │  │
│  │ • API: memory.get_memory_stats(), memory.audit_keys()             │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  CONTEXTUAL BANDIT ──────────────────────────────────────────────────┐  │
│  │ • Writes: Bandit posterior (in-memory, persisted to Redis)        │  │
│  │ • Reads:  Counterfactual outcomes (L3), context vectors           │  │
│  │ • Trigger: Every trade close (update), every TP decision (select) │  │
│  │ • API: bandit.select_action(context) → action                     │  │
│  │        bandit.update(context, action, reward)                     │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 11.2 Trading Engine Integration

```python
class TradingEngineMemoryBridge:
    """
    Bridge between the trading engine and the memory system.
    Ensures all trading events are captured and memory is consulted.
    """

    # ── Event Handlers ──

    def on_signal_generated(self, signal: TradeSignal):
        """Called when any agent generates a signal."""
        # Store in short-term memory
        self.memory.store_signal(signal)
        # Log to signal_log table (for precision/recall tracking)
        self.db.execute("""
            INSERT INTO signal_log (agent_id, symbol, timeframe, direction,
                                    confidence, score, generated_at, regime, session)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, [signal.agent_id, signal.symbol, signal.timeframe,
              signal.direction, signal.confidence, signal.score,
              signal.generated_at, signal.regime, signal.session])

    def on_trade_proposed(self, proposal: TradeProposal) -> TradeProposal:
        """
        Called before a trade is executed.
        Augments the proposal with memory context.
        """
        # Get memory-augmented context
        memory_ctx = self.memory.get_memory_context(
            instrument=proposal.instrument,
            regime=proposal.regime,
            session=proposal.session,
            setup_type=proposal.setup_type,
        )

        # Inject past episodes
        proposal.past_episodes = memory_ctx.episodes

        # Inject lessons
        proposal.relevant_lessons = memory_ctx.lessons

        # Inject pattern confidence
        proposal.pattern_confidence = memory_ctx.pattern_win_rate

        # Select TP strategy via contextual bandit
        context_vector = self.build_context_vector(proposal)
        proposal.tp_strategy = self.bandit.select_action(context_vector)

        # Inject management rules
        proposal.management_rules = self.memory.query_management_rules(
            proposal.instrument, proposal.regime,
            proposal.session, proposal.setup_type
        )

        return proposal

    def on_trade_opened(self, trade: TradeRecord):
        """Called when a trade is executed."""
        # Store in Redis (active position)
        self.redis.hset(f"position:{trade.id}", mapping=trade.to_dict())
        # No TTL on positions — deleted when trade closes

        # Update signal_log: mark signals that led to this trade
        for agent_id, signal in trade.signals_snapshot.items():
            self.db.execute("""
                UPDATE signal_log SET led_to_trade = TRUE, trade_id = %s
                WHERE agent_id = %s AND symbol = %s
                  AND generated_at = (
                      SELECT MAX(generated_at) FROM signal_log
                      WHERE agent_id = %s AND symbol = %s
                        AND generated_at <= %s
                  )
            """, [trade.id, agent_id, trade.instrument,
                  agent_id, trade.instrument, trade.entry_time])

    def on_trade_closed(self, trade: TradeRecord):
        """Called when a trade closes."""
        # Remove from Redis
        self.redis.delete(f"position:{trade.id}")

        # Store in PostgreSQL (long-term)
        self.memory.store_trade(trade)

        # Generate episode embedding
        embedding = self.embedder.embed_episode(trade.to_episode_dict())
        self.db.execute("""
            INSERT INTO episode_embeddings
                (trade_id, embedding, instrument, regime, session,
                 setup_type, outcome, direction, r_multiple)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, [trade.id, embedding, trade.instrument, trade.regime,
              trade.session, trade.setup_type, trade.outcome,
              trade.direction, trade.r_multiple])

        # Store in ClickHouse (episodic)
        self.clickhouse.execute("""
            INSERT INTO trade_episodes VALUES (...)
        """, trade.to_episode_dict())

        # Trigger reflection (async, non-blocking)
        self.reflection_queue.put(trade.id)

        # Update signal_log: mark outcomes
        self.db.execute("""
            UPDATE signal_log SET outcome = %s, was_correct_direction = %s
            WHERE trade_id = %s
        """, [trade.outcome, trade.direction == trade.predicted_direction, trade.id])

    def on_session_boundary(self, session_type: str):
        """Called at session boundaries (Asian/London/NY open)."""
        # Reset session-scoped Redis data
        self.memory.session_reset(session_type)

        # Generate session summary
        summary = self.compute_session_summary(session_type)
        self.memory.store_session_summary(summary)
```

### 11.3 Memory-Augmented Decision Flow

```
NEW TRADE DECISION REQUEST
          │
          ▼
┌──────────────────────────────────────┐
│  1. Load Working Memory Context      │
│     (StrategyContext for instrument)  │
└─────────────────┬────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────┐
│  2. Run AlphaStack Steps 1-8              │
│     (Standard analysis pipeline)     │
└─────────────────┬────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────┐
│  3. MEMORY RETRIEVAL                 │◄── Memory Manager
│     • Query past episodes (L4)       │
│     • Load relevant lessons (L3)     │
│     • Get pattern confidence (L3)    │
│     • Get management rules (L3)      │
│     • Get signal weights (L3)        │
│     Latency budget: <100ms           │
└─────────────────┬────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────┐
│  4. CONTEXT BUILDING                 │
│     • Merge current state + memory   │
│     • Weight signals by reliability  │
│     • Flag relevant past episodes    │
│     • Highlight active lessons       │
└─────────────────┬────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────┐
│  5. Run AlphaStack Steps 9-14             │
│     (Memory-augmented decisions)     │
│     • Step 10: Use pattern confidence│
│     • Step 11: Use drawdown state    │
│     • Step 13: Bandit-selected TP    │
│     • Step 14: Learned mgmt rules    │
└─────────────────┬────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────┐
│  6. Execute + Record                 │
│     • Execute trade                  │
│     • Log to all memory layers       │
│     • Queue for reflection           │
└──────────────────────────────────────┘
```

---

## 12. 24/7 Operation Memory Leak Prevention

### 12.1 Risk Matrix

| Risk | Severity | Component | Detection | Mitigation |
|------|----------|-----------|-----------|------------|
| **Working memory accumulation** | 🔴 HIGH | Python process | `process_resident_memory_bytes > 2GB` | Explicit `context.release()`, max 100 contexts, GC tuning |
| **Redis key proliferation** | 🔴 HIGH | Redis | `key_count > 100K` | Mandatory TTL, MAXLEN, daily audit |
| **Event stream backlog** | 🟡 MEDIUM | Redis Streams | `consumer_lag > 1000` | MAXLEN on all streams, lag monitoring |
| **Log volume explosion** | 🟡 MEDIUM | Filesystem | `log_dir_size > 10GB` | Severity filtering, rotation, S3 archival |
| **ML model memory** | 🟡 MEDIUM | Python process | `model_memory > 500MB` | Lazy loading, model sharing, quantization |
| **Session transcript growth** | 🟠 LOW-MED | Filesystem | `transcript_size > 1GB` | Compaction, S3 archival |
| **TimescaleDB hypertable bloat** | 🟠 LOW-MED | PostgreSQL | `disk_usage > 50GB` | Compression, retention policies |
| **Embedding accumulation** | 🟠 LOW | pgvector | `embedding_count > 1M` | Dimensionality reduction, clustering |
| **Connection pool leaks** | 🟠 LOW | All DBs | `active_connections > 100` | Health checks, recycling |
| **GC pauses** | 🟠 LOW | Python process | `gc_pause > 100ms` | Disable GC during hot paths, periodic GC windows |

### 12.2 Monitoring Configuration

```python
MEMORY_MONITORING = {
    "process": {
        "resident_memory_bytes": {
            "alert": "> 2GB",
            "critical": "> 4GB",
            "action": "restart_worker",
            "check_interval": "1m"
        },
        "gc_pause_duration_seconds": {
            "alert": "> 0.1",
            "critical": "> 0.5",
            "action": "enable_gc_control",
            "check_interval": "5m"
        },
        "active_contexts_count": {
            "alert": "> 50",
            "critical": "> 100",
            "action": "force_release_old_contexts",
            "check_interval": "30s"
        }
    },
    "redis": {
        "used_memory_bytes": {
            "alert": "> 1GB",
            "critical": "> 2GB",
            "action": "flush_expired_and_audit",
            "check_interval": "5m"
        },
        "connected_clients": {
            "alert": "> 100",
            "critical": "> 200",
            "action": "kill_idle_connections",
            "check_interval": "1m"
        },
        "key_count": {
            "alert": "> 100K",
            "critical": "> 500K",
            "action": "run_key_audit",
            "check_interval": "15m"
        },
        "evicted_keys_per_minute": {
            "alert": "> 100",
            "action": "review_ttl_settings",
            "check_interval": "5m"
        }
    },
    "postgresql": {
        "disk_usage_bytes": {
            "alert": "> 50GB",
            "critical": "> 100GB",
            "action": "archive_old_data",
            "check_interval": "1h"
        },
        "active_connections": {
            "alert": "> 50",
            "critical": "> 100",
            "action": "kill_idle_connections",
            "check_interval": "1m"
        },
        "table_sizes": {
            "alert": "any_table > 10GB",
            "action": "review_retention_policy",
            "check_interval": "6h"
        }
    },
    "clickhouse": {
        "disk_usage_bytes": {
            "alert": "> 20GB",
            "critical": "> 50GB",
            "action": "run_compression_and_archive",
            "check_interval": "1h"
        },
        "active_queries": {
            "alert": "> 20",
            "action": "review_query_patterns",
            "check_interval": "5m"
        }
    },
    "event_bus": {
        "consumer_lag": {
            "alert": "> 1000",
            "critical": "> 10000",
            "action": "scale_consumers_or_trim_stream",
            "check_interval": "1m"
        }
    }
}
```

### 12.3 Auto-Remediation

```python
class MemoryLeakRemediation:
    """
    Automated remediation for memory leak scenarios.
    """

    def remediate_redis_memory_critical(self):
        """Redis memory exceeded 2GB."""
        # 1. Delete expired keys (should be automatic, but force it)
        self.redis.execute_command('MEMORY', 'PURGE')

        # 2. Trim oversized streams
        for stream_key in self.redis.scan_iter('events:*'):
            self.redis.xtrim(stream_key, maxlen=5000)

        # 3. Audit all keys for missing TTL
        auditor = RedisKeyAuditor(self.redis)
        result = auditor.audit()
        if result.violations['no_ttl']:
            for key in result.violations['no_ttl']:
                self.redis.expire(key, 86400)  # Apply 24h default

        # 4. Alert
        self.alert('CRITICAL', f'Redis memory remediated. {result.key_counts}')

    def remediate_process_memory_critical(self):
        """Python process memory exceeded 4GB."""
        # 1. Force release all working memory contexts
        released = 0
        for ctx_id in list(self.active_contexts.keys()):
            self.active_contexts[ctx_id].release()
            del self.active_contexts[ctx_id]
            released += 1

        # 2. Force garbage collection
        import gc
        gc.collect()

        # 3. If still critical, restart gracefully
        if self.get_process_memory() > 3 * 1024**3:  # Still > 3GB
            logger.critical("Memory still critical after cleanup. Initiating graceful restart.")
            self.graceful_restart()

        self.alert('WARNING', f'Released {released} contexts. Memory: {self.get_process_memory_mb()}MB')

    def remediate_disk_critical(self, component: str):
        """Disk usage critical for a component."""
        if component == 'postgresql':
            # Archive old data to S3
            self.archive_to_s3('trades', older_than='2 years')
            self.archive_to_s3('signal_log', older_than='1 year')
            self.archive_to_s3('trade_counterfactuals', older_than='1 year')

            # Run VACUUM
            self.db.execute("VACUUM ANALYZE")

        elif component == 'clickhouse':
            # Force merge and compression
            self.clickhouse.execute("OPTIMIZE TABLE trade_episodes FINAL")

            # Archive old partitions to S3
            self.archive_ch_partitions('trade_episodes', older_than='2 years')

        elif component == 'logs':
            # Rotate and archive logs
            self.rotate_logs()
            self.archive_logs_to_s3(older_than='7 days')
```

### 12.4 GC Tuning for Trading

```python
import gc

class GCTuner:
    """
    Tune Python GC for low-latency trading paths.
    """

    def __init__(self):
        # Disable automatic GC during initialization
        gc.disable()

        # Track allocation count for manual GC
        self.alloc_count = 0
        self.gc_interval = 1000  # Run GC every N allocations

    def on_analysis_start(self):
        """Called at the start of a critical analysis path."""
        # Disable GC during critical section
        gc.disable()

    def on_analysis_end(self):
        """Called at the end of a critical analysis path."""
        # Re-enable and run GC in controlled window
        gc.enable()
        gc.collect(generation=0)  # Only collect youngest generation (fastest)
        gc.disable()

    def on_idle(self):
        """Called during idle periods (no active analysis)."""
        # Run full GC during idle time
        gc.enable()
        gc.collect()  # Full collection
        gc.disable()

    def periodic_gc(self):
        """Run periodically (every 30 seconds) during non-critical periods."""
        if not self.is_critical_path_active:
            gc.enable()
            collected = gc.collect()
            gc.disable()
            if collected > 0:
                logger.debug(f"GC collected {collected} objects")
```

### 12.5 Scheduled Maintenance Tasks

```yaml
maintenance_schedule:
  # Every minute
  - name: "Check process memory"
    command: "python -c 'import psutil; print(psutil.Process().memory_info().rss)'"
    alert_threshold: "2GB"

  # Every 5 minutes
  - name: "Redis memory check"
    command: "redis-cli info memory | grep used_memory_human"
    alert_threshold: "1GB"

  # Every 15 minutes
  - name: "Redis key count audit"
    command: "redis-cli dbsize"
    alert_threshold: "100000"

  # Every hour
  - name: "PostgreSQL disk usage"
    command: "psql -c \"SELECT pg_database_size('alpha_stack')\""
    alert_threshold: "50GB"

  # Every 6 hours
  - name: "ClickHouse table sizes"
    command: "clickhouse-client -q \"SELECT table, formatReadableSize(sum(bytes)) FROM system.parts GROUP BY table\""

  # Daily at 04:00 UTC
  - name: "Full memory audit"
    command: "python scripts/memory_audit.py"
    actions:
      - "Check all Redis keys for TTL"
      - "Verify PostgreSQL table sizes"
      - "Check connection pool health"
      - "Verify backup integrity"
      - "Report memory trends"

  # Weekly (Sunday 05:00 UTC)
  - name: "Memory compaction"
    command: "python scripts/memory_compact.py"
    actions:
      - "Archive data > 2 years to S3"
      - "Compress ClickHouse partitions"
      - "Run PostgreSQL VACUUM ANALYZE"
      - "Defragment Redis"
```

---

## 13. Implementation Roadmap

### Phase 1: Foundation (Weeks 1–4)

| Week | Task | Deliverable |
|------|------|-------------|
| 1 | Implement Working Memory (StrategyContext with bounded size) | `StrategyContext` dataclass, LRU eviction |
| 1 | Set up Redis with mandatory TTL enforcement | `RedisShortTermStore` with TTL config |
| 2 | Implement basic trade journal (PostgreSQL) | `trades` table, `store_trade()` API |
| 2 | Implement Short-Term Memory store | Signal/candle/position storage in Redis |
| 3 | Implement Long-Term Memory store | Lessons, signal weights, patterns tables |
| 3 | Basic session management (reset at boundaries) | `session_reset()` implementation |
| 4 | Memory Manager service skeleton | gRPC API, health endpoint, basic routing |
| 4 | Prometheus monitoring for memory metrics | Grafana dashboards, alert rules |

### Phase 2: Learning Loop (Weeks 5–8)

| Week | Task | Deliverable |
|------|------|-------------|
| 5 | Implement signal logging (all signals, not just trade-linked) | `signal_log` table, logging in engine |
| 5 | Implement ablation-based causal attribution | `CausalAttribution` class, `trade_attributions` table |
| 6 | Implement statistical significance gating | `SignalWeightAdjuster`, Bonferroni correction |
| 6 | Implement hierarchical Bayesian pattern reliability | `HierarchicalPatternReliability` class |
| 7 | Implement counterfactual shadow tracking | `CounterfactualTracker`, `trade_counterfactuals` table |
| 7 | Replace RL with contextual bandit (Thompson Sampling) | `ContextualBanditTP` class |
| 8 | Implement management rule computation (offline) | Nightly cron, `management_rules` table |
| 8 | Integrate counterfactual data as bandit reward signal | Bandit training pipeline |

### Phase 3: Episodic Memory & Search (Weeks 9–12)

| Week | Task | Deliverable |
|------|------|-------------|
| 9 | Implement ClickHouse episodic storage | `trade_episodes` table, compression policies |
| 9 | Implement episode embedding generation | `EpisodeEmbedder`, `episode_embeddings` table |
| 10 | Implement hybrid semantic search | `SemanticSearchService`, pgvector indexes |
| 10 | Implement Memory Context Loader | `get_memory_context()` API, context injection |
| 11 | Memory-augmented AlphaStack pipeline (Steps 9-14) | Pipeline integration with memory retrieval |
| 11 | Implement concept drift detection | `DriftDetectorSystem`, Page-Hinkley, HMM |
| 12 | Implement drift response actions | Confidence reduction, prior reset, alerts |
| 12 | End-to-end integration testing | Full loop: trade → reflect → store → retrieve → decide |

### Phase 4: Production Hardening (Weeks 13–16)

| Week | Task | Deliverable |
|------|------|-------------|
| 13 | Implement disaster recovery procedures | Redis/PG/CH recovery scripts, S3 backups |
| 13 | Implement memory lifecycle management | Decay engine, archival cron, TTL enforcement |
| 14 | Implement auto-remediation for memory leaks | `MemoryLeakRemediation` class |
| 14 | GC tuning for trading paths | `GCTuner` class, critical path GC control |
| 15 | Load testing and performance optimization | Stress test at 2× expected load |
| 15 | Security review (PII in memory, access control) | Anonymization, access logging |
| 16 | Documentation and runbook completion | Ops runbook, architecture review |
| 16 | Production deployment and monitoring validation | Go-live checklist, 24h burn-in |

### Success Criteria

| Phase | Metric | Target |
|-------|--------|--------|
| Phase 1 | Redis TTL compliance | 100% of keys have TTL |
| Phase 1 | Working memory bounded | Max 100 concurrent contexts, never exceeds |
| Phase 2 | Weight adjustments gated | Zero adjustments without p < 0.10 |
| Phase 2 | Counterfactual coverage | 100% of trades have shadow tracking |
| Phase 3 | Semantic search latency | <100ms end-to-end |
| Phase 3 | Search relevance | ≥3/5 top results genuinely similar (human-validated) |
| Phase 4 | Memory leak detection | Leaks detected within 1 hour |
| Phase 4 | Recovery time | Redis <1min, PG <30min, full system <2 hours |
| Phase 4 | 24/7 stability | Zero OOM kills, zero unbounded growth, 7-day burn-in |

---

## Appendix A: Configuration Reference

```yaml
# memory_config.yaml

# Working Memory (Layer 1)
working_memory:
  max_contexts: 100
  context_ttl_seconds: 300       # 5 minutes max lifetime
  gc_generation: 0               # Collect youngest generation only during active trading

# Short-Term Memory (Layer 2)
short_term:
  redis:
    host: "localhost"
    port: 6379
    db: 0
    max_memory: "1gb"
    maxmemory_policy: "volatile-lru"   # Evict keys with TTL first
  ttl:
    tick_seconds: 14400          # 4 hours
    candle_seconds: 86400        # 24 hours
    signal_seconds: 86400        # 24 hours
    session_seconds: 604800      # 7 days
    market_seconds: 3600         # 1 hour
    event_stream_seconds: 86400  # 24 hours
  maxlen:
    ticks_per_instrument: 10000
    candles_per_instrument_tf: 1000
    signals_per_instrument: 1000
    events_per_instrument: 10000
    max_concurrent_positions: 10

# Long-Term Memory (Layer 3)
long_term:
  postgresql:
    host: "localhost"
    port: 5432
    database: "alpha_stack"
    pool_size: 20
    max_overflow: 10
  pgvector:
    embedding_model: "all-MiniLM-L6-v2"    # Phase 1
    embedding_dimension: 384
    index_type: "ivfflat"
    lists: 100
  lifecycle:
    lesson_decay_rate: 0.002              # Per day of inaccess
    pattern_decay_rate: 0.005
    signal_weight_decay_rate: 0.001
    lesson_archive_threshold: 0.10
    pattern_archive_threshold: 0.15
    counterfactual_retention_days: 365
    attribution_retention_days: 365
    trade_archive_years: 2

# Episodic Memory (Layer 4)
episodic:
  clickhouse:
    host: "localhost"
    port: 9000
    database: "alpha_stack"
  compression:
    raw_days: 90                 # Keep raw for 90 days
    compressed_codec: "ZSTD(9)"  # After 90 days
    archive_years: 2             # Archive to S3 after 2 years

# Learning Loop
learning_loop:
  reflection:
    trigger: "trade_close"
    counterfactual_strategies: 5
    attribution_method: "ablation"
  pattern_detection:
    min_samples: 10
    hierarchical_levels: 3
    time_weight_half_life: 100   # trades
  signal_weights:
    min_samples_for_adjustment: 20
    significance_alpha: 0.10
    bonferroni_correction: true
    max_adjustment_per_trade: 0.03
    weight_bounds: [0.05, 0.40]
  bandit:
    algorithm: "thompson_sampling_linear"
    n_features: 20
    n_actions: 3                 # conservative, balanced, aggressive
    v_squared: 1.0
    prior_variance: 1.0
  drift_detection:
    check_interval: 20           # Every 20 trades
    page_hinkley_delta: 0.005
    page_hinkley_lambda: 50.0
    amber_threshold: 0.3
    red_threshold: 0.6
    regime_hmm_n_states: 4
    regime_hmm_retrain_window: 500

# Monitoring
monitoring:
  prometheus:
    port: 9090
    scrape_interval: "15s"
  alerts:
    process_memory_critical_gb: 4
    redis_memory_critical_gb: 2
    redis_keys_critical: 500000
    pg_disk_critical_gb: 100
    ch_disk_critical_gb: 50
    consumer_lag_critical: 10000
  auto_remediation:
    enabled: true
    redis_memory_critical: "flush_expired_and_audit"
    process_memory_critical: "graceful_restart"
    disk_critical: "archive_and_compress"
```

---

## Appendix B: Glossary

| Term | Definition |
|------|-----------|
| **Working Memory** | In-process Python objects for current analysis. Ephemeral, LRU-evicted. |
| **Short-Term Memory** | Redis-based hot cache for session-scoped data. TTL-enforced. |
| **Long-Term Memory** | PostgreSQL-based durable store for trade journal, lessons, patterns. |
| **Episodic Memory** | ClickHouse-based structured episodes with vector embeddings for semantic search. |
| **Closed Learning Loop** | Trade → Reflect → Extract → Update → Store → Apply cycle. |
| **Contextual Bandit** | Thompson Sampling with linear payoffs for TP strategy selection. |
| **Hierarchical Bayesian** | Beta-Binomial model that borrows statistical strength from parent levels. |
| **Ablation Attribution** | Measuring agent contribution by removing its signal and recomputing confluence. |
| **Counterfactual Tracking** | Recording hypothetical outcomes for alternative management strategies. |
| **Concept Drift** | When market conditions change enough that past lessons become unreliable. |
| **Page-Hinkley Test** | Sequential change-point detection algorithm for drift monitoring. |
| **Memory Context** | Unified retrieval result combining data from all 4 memory layers. |

---

*Document created: 2026-07-11*  
*Status: Architecture Design Complete — Ready for Phase 1 Implementation*  
*Next: Create `implementation_memory.md` with detailed implementation tasks*
