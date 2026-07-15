# Implementation: Self-Reflection & Correction Loop (P1)

**Status:** ✅ Complete  
**Date:** 2026-07-16  
**Priority:** P1 (Decision Council)  
**Files changed:**

| File | Change |
|------|--------|
| `src/alphastack/agents/reflection/post_trade.py` | **NEW** — PostTradeReflection, CorrectionEngine, SkillCreator |
| `src/alphastack/agents/reflection/__init__.py` | Added exports for new classes |
| `src/alphastack/agents/orchestrator/graph.py` | Integrated self-correction loop into reflection node |

---

## Architecture

```
execution node fills trade
        │
        ▼
┌─ reflection node ─────────────────────────────┐
│                                                │
│  1. ReflectionAgent (existing)                 │
│     └─ aggregate performance metrics           │
│                                                │
│  2. PostTradeReflection (NEW)                  │
│     └─ chain-of-thought per trade              │
│        "What went right? Wrong? Differently?"  │
│                                                │
│  3. CorrectionEngine (NEW)                     │
│     └─ generates parameter corrections         │
│     └─ stores lessons in EpisodicMemory        │
│     └─ applies corrections to pipeline_context │
│                                                │
│  4. SkillCreator (NEW)                         │
│     └─ 5+ similar wins → create skill          │
│     └─ skills promoted/demoted by win rate     │
│     └─ max 20 active skills (bounded)          │
│                                                │
└────────────────────────────────────────────────┘
        │
        ▼
   END (corrections applied for next cycle)
```

---

## Components

### 1. `PostTradeReflection`

Uses `ChainOfThoughtEngine` (existing) to run structured reasoning on each completed trade.

**Chain steps:**
1. **Observation** — record trade outcome (symbol, direction, P&L)
2. **Observation** — note triggering signal type and confidence
3. **Hypothesis** — diagnose root cause category
4. **Evidence** — support diagnosis with concrete data points
5. **Inference** — assign category: `signal | execution | timing | risk`
6. **Conclusion** — recommendation for correction

**Root cause diagnosis logic:**
- Signal confidence < 0.4 + loss → `signal` (bad signal)
- Slippage > 0.5% → `execution` (poor fill quality)
- Price capture ratio < 30% of expected move → `timing` (suboptimal entry/exit)
- Max adverse excursion exceeds stop distance by 1.5x → `risk` (stop too tight)

**Performance target:** < 1 second per trade (no I/O, pure computation).

### 2. `CorrectionEngine`

Translates reflection diagnoses into concrete parameter adjustments.

**Correction categories:**

| Category + Outcome | Parameter Adjusted | Delta |
|--------------------|--------------------|-------|
| signal + loss | `min_confluence_score` | +0.05 (tighten) |
| execution + loss | `position_size_pct` | -0.02 (reduce size) |
| timing + loss | `entry_patience_bars` | +1 (wait longer) |
| risk + loss | `stop_loss_atr_mult` | +0.2 (widen stop) |
| signal + win | `min_confluence_score` | -0.02 (slightly relax) |

**Features:**
- Corrections have an `impact_score` (0–1) weighted by P&L magnitude
- `apply_corrections()` merges active corrections into `pipeline_context`
- `store_lessons()` writes correction reasons as lessons on `TradeEpisode`
- Active corrections expire after 24 hours

### 3. `SkillCreator`

Extracts reusable trade templates from repeated winning patterns.

**Skill lifecycle:**
1. **Pattern extraction** — `symbol:direction:strategy:timeframe:confluence_bucket`
2. **Counting** — similar wins counted via `EpisodicMemory.find_similar()`
3. **Creation** — after 5+ similar wins with same pattern key
4. **Promotion** — skills with high win rate stay active
5. **Demotion** — skills drop below 40% win rate → `active = False`
6. **Pruning** — over 20 active skills → lowest performers removed

**`get_applicable_skills(trade)`** — returns active skills matching a trade's pattern, sorted by win rate. Next trade cycle can consult these for position sizing and entry rules.

---

## Orchestrator Integration

The `_reflection_node` in `AlphaStackOrchestrator` now runs three phases:

```python
# Phase 1: Aggregate analysis (existing ReflectionAgent)
result = await self.reflection_agent.run(...)

# Phase 2: Per-trade self-correction (new loop)
for trade in filled_trades:
    chain = self.post_reflection.reflect(trade)
    correction = self.correction_engine.generate(chain, trade)
    episode = create_episode(trade, chain)
    self.correction_engine.store_lessons(memory, episode)
    self.episodic_memory.store(episode)
    self.skill_creator.record_trade(trade, memory)

# Phase 3: Apply corrections to pipeline_context
if corrections_generated:
    s.pipeline_context = self.correction_engine.apply_corrections(...)
```

New helper `_enrich_trade()` combines execution entries with their triggering signal context for reflection.

---

## Design Decisions

1. **Synchronous within reflection node** — reflection is fast (< 1s) and happens after execution, so no blocking of trade flow.
2. **Existing ReasoningChain** — reuses the chain-of-thought engine for consistency with other agents.
3. **Bounded memory** — `EpisodicMemory` auto-consolidates short-term to long-term; skills capped at 20.
4. **Correction expiry** — 24-hour TTL prevents stale corrections from compounding.
5. **Pattern fuzzy matching** — skills match on symbol/direction/strategy/timeframe but not exact confluence bucket, allowing slight variation.

---

## Usage

```python
from alphastack.agents.reflection.post_trade import (
    PostTradeReflection, CorrectionEngine, SkillCreator
)
from alphastack.agi.memory import EpisodicMemory

reflection = PostTradeReflection()
corrections = CorrectionEngine()
skills = SkillCreator()
memory = EpisodicMemory()

# After a trade completes:
chain = reflection.reflect(trade_data)
correction = corrections.generate(chain, trade_data)
if correction:
    adjusted_params = corrections.apply_corrections(current_params)

# Check for applicable skills:
applicable = skills.get_applicable_skills(trade_data)
```
