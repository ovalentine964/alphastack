# Self-Improvement Wiring: Connecting Fixes to Architecture

**Author:** Self-Improvement Wiring Agent
**Date:** 2026-07-11
**Version:** 1.0
**Status:** Wiring Specification — Ready for Implementation
**Source:**
- `fix_learning_loops.md` — 6 architectural fixes (C1–C6)
- `review_self_improvement.md` — Verification report (0/14 issues resolved)
- `alphastack/architecture_memory.md` — 4-layer memory architecture

**Purpose:** The fixes exist as standalone designs. This document wires them into the actual memory architecture — specifying exactly where each fix plugs in, what it replaces, what calls it, and what calls it back.

---

## Table of Contents

1. [Wiring Overview](#1-wiring-overview)
2. [Wire 1: Contextual Bandit → Trade Management System](#2-wire-1-contextual-bandit--trade-management-system)
3. [Wire 2: Concept Drift Detection → Signal Weight System](#3-wire-2-concept-drift-detection--signal-weight-system)
4. [Wire 3: Hierarchical Bayesian Model → Pattern Reliability Tracking](#4-wire-3-hierarchical-bayesian-model--pattern-reliability-tracking)
5. [Wire 4: Statistical Significance → Weight Adjustment Triggers](#5-wire-4-statistical-significance--weight-adjustment-triggers)
6. [Wire 5: Counterfactual Data Capture → Journal System](#6-wire-5-counterfactual-data-capture--journal-system)
7. [Wire 6: Ablation Analysis → Agent Performance Tracking](#7-wire-6-ablation-analysis--agent-performance-tracking)
8. [Integration Map: All Wires Together](#8-integration-map-all-wires-together)
9. [Modified Architecture Sections](#9-modified-architecture-sections)
10. [Implementation Checklist](#10-implementation-checklist)

---

## 1. Wiring Overview

### 1.1 What "Wiring" Means

Each fix from `fix_learning_loops.md` is a self-contained algorithm. But the architecture in `architecture_memory.md` has specific entry points, data flows, and agent responsibilities. Wiring means:

1. **Inbound:** What triggers the fix? Which agent, which event, which memory layer?
2. **Outbound:** What does the fix produce? Where does output go? Which consumers read it?
3. **Replacement:** What existing component does it replace or augment?
4. **Side effects:** What other parts of the architecture change as a consequence?

### 1.2 The Six Wires at a Glance

| Wire | Fix | Plugs Into | Replaces | Primary Agent |
|------|-----|-----------|----------|---------------|
| 1 | Contextual Bandit | Step 13 (TP Agent) + Step 16 (RL) | Deep RL TP selection | TP Agent → `ContextualBanditTP` |
| 2 | Concept Drift Detection | Section 9 (Learning Loop) + Signal Weights | Nothing (new component) | New: `DriftMonitor` (cron) |
| 3 | Hierarchical Bayesian | Section 5.4.3 (Pattern Reliability) | Independent per-cell win rates | Reflection Agent → `HierarchicalPatternReliability` |
| 4 | Statistical Significance | Section 5.4.2 (Signal Weights) + Section 9.2 Phase 4 | Per-trade weight adjustments | Reflection Agent → `SignalWeightAdjuster` |
| 5 | Counterfactual Capture | Section 6 (Episodic Memory) + Journal Agent | Nothing (new component) | Journal Agent → `CounterfactualTracker` |
| 6 | Ablation Analysis | Section 9.2 Phase 2 (Reflect) + Section 5.4.2 | Simple directional attribution | Reflection Agent → `CausalAttribution` |

### 1.3 Dependency Graph

```
Wire 5 (Counterfactuals) ──feeds──▶ Wire 1 (Bandit rewards)
         │
Wire 6 (Ablation) ──feeds──▶ Wire 4 (Significance gate)
         │
Wire 4 (Significance) ──gates──▶ Wire 3 (Pattern updates)
         │
Wire 2 (Drift) ──overrides──▶ ALL wires (discounts stale knowledge)
```

**Critical path:** Wire 5 and Wire 6 are foundational — they produce data that other wires consume. Implement them first.

---

## 2. Wire 1: Contextual Bandit → Trade Management System

### 2.1 What It Replaces

In `architecture_memory.md`, the TP Agent (Section 7.1 access matrix row) currently has no specified intelligence — it's a placeholder for "RL-based TP selection." The fix in `fix_learning_loops.md` Section 1 replaces this with Thompson Sampling.

**Before:** TP Agent reads strategy parameters, applies fixed TP levels.
**After:** TP Agent queries `ContextualBanditTP` with market context, receives optimal TP strategy.

### 2.2 Inbound Wiring

```
TRIGGER: Entry Agent produces a trade proposal (confluence ≥ threshold)
  │
  ▼
TP Agent receives:
  ├── From Working Memory (Redis):
  │   ├── regime:{symbol}          → regime classification
  │   ├── confluence:{symbol}      → confluence_score
  │   └── indicators:{symbol}:{tf} → atr_ratio, volatility metrics
  │
  ├── From Short-Term Memory (PostgreSQL):
  │   ├── session state            → asian/london/new_york/overlap
  │   └── today's volatility       → current_atr vs 20d_avg_atr
  │
  └── From Long-Term Memory (PostgreSQL):
      ├── signal_weights           → setup_type from dominant signals
      └── pattern_reliability      → pattern classification
```

**Context vector construction** (wired into TP Agent's prompt injection, Section 7.4):

```python
def build_bandit_context(symbol, working_memory, short_term, long_term):
    """
    Constructs the context vector for the contextual bandit.
    Called by TP Agent before strategy selection.
    """
    regime = working_memory.get(f'regime:{symbol}')['regime']
    session = short_term.get_current_session()
    setup_type = classify_setup(working_memory.get(f'confluence:{symbol}'))
    atr_data = working_memory.get(f'indicators:{symbol}:4h')

    return {
        'symbol': one_hot_encode(symbol, ['EUR/USD', 'BTC/USDT', 'GBP/USD']),
        'regime': one_hot_encode(regime, ['trending_bull', 'trending_bear', 'ranging', 'volatile']),
        'session': one_hot_encode(session, ['asian', 'london', 'new_york', 'overlap']),
        'setup_type': one_hot_encode(setup_type, ['ob_bounce', 'fvg_fill', 'bos_continuation', 'divergence']),
        'volatility_regime': classify_volatility(atr_data['atr_ratio']),
        'atr_ratio': atr_data['atr_ratio'],
        'confluence_score': working_memory.get(f'confluence:{symbol}')['score'] / 100,
        'timeframe': one_hot_encode('4h', ['1h', '4h', '1d']),
    }
```

### 2.3 Outbound Wiring

```
ContextualBanditTP.select_action(context) returns:
  │
  ▼
action_index → maps to TP strategy:
  0 = conservative:  TP1=1.0R, TP2=1.5R, TP3=2.0R, trail=2.0×ATR
  1 = balanced:      TP1=1.5R, TP2=2.5R, TP3=4.0R, trail=2.5×ATR
  2 = aggressive:    TP1=2.0R, TP2=4.0R, TP3=6.0R, trail=3.0×ATR
  │
  ▼
TP Agent writes to Working Memory:
  └── tp_strategy:{trade_id} → {strategy_name, tp1_r, tp2_r, tp3_r, trail_mult}
  │
  ▼
Trade Management Agent reads tp_strategy:{trade_id}
  └── Applies partial close and trailing rules from the selected strategy
```

### 2.4 Reward Feedback Loop

After trade closes, the bandit needs the reward signal. This is where Wire 5 (Counterfactuals) feeds Wire 1:

```
TRADE CLOSED
  │
  ▼
Journal Agent computes counterfactuals (Wire 5)
  │
  ▼
CounterfactualTracker returns r_multiple for each strategy
  │
  ▼
Reflection Agent calls:
  bandit.update(context_vector, actual_action, actual_r_multiple)
  │
  ▼
For counterfactual strategies (actions not taken):
  bandit.update(context_vector, alt_action, counterfactual_r_multiple)
  │
  ▼
Posterior updated → next trade uses updated posteriors
```

### 2.5 Lookup Table Integration

Management rules (when to move SL, partial sizes) come from offline-computed lookup tables. Wire into the existing `strategy_parameters` table:

```sql
-- Extend existing strategy_parameters to include management rules
-- The existing table stores version-controlled configs (Section 5.4.1)
-- Add management_rules as a new parameter set within the JSONB parameters column

-- Or, if management_rules is a separate table (fix_learning_loops.md Section 1.4):
-- Wire it into the TP Agent's read path:

-- TP Agent reads:
SELECT * FROM management_rules
WHERE symbol = %s AND regime = %s AND session = %s AND setup_type = %s
  AND active = TRUE;

-- If no specific rule found, fall back to bandit selection
```

### 2.6 Architecture Memory Section Changes

**Section 7.1 (Access Matrix):** TP Agent row now reads from `management_rules` table and `ContextualBanditTP` model (stored in PostgreSQL or serialized file).

**Section 9.2 (Phase 4 — Update Knowledge):** Add bandit posterior update as part of "Signal Weights" priority level — it's auto-approved within bounds.

**Section 10.1 (Improvement Pipeline):** Add row:
```
contextual_bandit_posterior  →  TP Agent selects optimal strategy  →  Higher R-multiple per trade
```

---

## 3. Wire 2: Concept Drift Detection → Signal Weight System

### 3.1 What It Adds

The architecture has **no drift detection in the learning loop** (confirmed by review Section 2.1). The ML pipeline has drift detection for model features, but lessons, weights, and patterns are unmonitored. This wire adds a `DriftMonitor` that runs as a cron job and can override the entire learning system.

### 3.2 Inbound Wiring

```
TRIGGER: Cron job, runs every 20 closed trades
  │
  ▼
DriftMonitor.check_drift() reads:
  │
  ├── From Long-Term Memory (PostgreSQL):
  │   ├── signal_weights          → accuracy_50 per agent/symbol
  │   ├── pattern_reliability     → win_rate trends per pattern
  │   ├── lessons                 → success_when_applied / times_applied
  │   └── trades (recent 50)      → outcomes for rolling accuracy
  │
  ├── From Short-Term Memory (PostgreSQL):
  │   ├── daily_performance       → recent win rate trend
  │   └── regime_history          → regime transition frequency
  │
  └── From ML Pipeline (shared state):
      └── drift_state:{model_id}  → existing PSI/KS drift scores
```

### 3.3 Outbound Wiring

```
DriftMonitor.check_drift() returns drift_level: GREEN | AMBER | RED
  │
  ▼
GREEN: No action (normal operation)
  │
  ▼
AMBER:
  ├── UPDATE signal_weights SET confidence = confidence * 0.75
  ├── UPDATE lessons SET confidence = confidence * 0.75 WHERE status = 'active'
  ├── bandit.v_squared *= 1.5  (increase exploration)
  ├── WRITE drift_state table: {level: 'AMBER', score, timestamp}
  ├── EMIT to Redis Stream: stream:alerts → {severity: 'WARNING', message}
  └── WRITE to memory/YYYY-MM-DD.md: "Concept drift detected (AMBER)"
  │
  ▼
RED:
  ├── UPDATE signal_weights SET confidence = confidence * 0.50
  ├── UPDATE lessons SET confidence = confidence * 0.50 WHERE status = 'active'
  ├── RESET ContextualBanditTP priors (v_squared = 2.0)
  ├── TRIGGER regime_model.retrain_on_recent(window=200)
  ├── WRITE drift_state table: {level: 'RED', score, timestamp}
  ├── EMIT to Redis Stream: stream:alerts → {severity: 'CRITICAL', message}
  ├── WRITE to memory/YYYY-MM-DD.md: "SEVERE concept drift (RED)"
  └── SET monitoring_interval = 5  (check every 5 trades instead of 20)
```

### 3.4 Consumer Integration

Every component that reads signal weights or lessons must check drift state first:

```python
# In Signal Aggregator (reads signal_weights):
def get_adjusted_weight(agent_id, symbol):
    weight = db.get_signal_weight(agent_id, symbol)
    drift = db.get_latest_drift_state()

    if drift['level'] == 'AMBER':
        return weight * 0.75  # Discount by 25%
    elif drift['level'] == 'RED':
        return weight * 0.50  # Discount by 50%
    return weight

# In Reflection Agent (reads lessons):
def get_applicable_lessons(symbol, regime):
    lessons = db.search_lessons(symbol, regime)
    drift = db.get_latest_drift_state()

    if drift['level'] in ('AMBER', 'RED'):
        # Only return high-confidence lessons during drift
        return [l for l in lessons if l['confidence'] > 0.6]
    return lessons
```

### 3.5 Architecture Memory Section Changes

**Section 3 (Working Memory):** Add `drift_state:{symbol}` to Redis Hash, updated by DriftMonitor cron.

**Section 5 (Long-Term Memory):** Add `drift_state` table (see fix_learning_loops.md Section 2.6 schema).

**Section 9 (Closed Learning Loop):** Insert drift check as **pre-check step** before Phase 2 (Reflect). The loop becomes:

```
TRADE CLOSED
  │
  ▼
0. [NEW] Drift check (every 20 trades)
  │   ├── GREEN → proceed
  │   ├── AMBER → discount confidence, increase exploration, proceed
  │   └── RED → halve confidence, reset priors, alert human, proceed with caution
  │
  ▼
1. Reflect on trade (existing)
  ▼
2. Extract lessons (existing)
  ▼
3. Update knowledge (existing, but with drift-adjusted confidence)
  ▼
4. Apply knowledge (existing)
```

**Section 12.2 (Cleanup Schedule):** Add to WEEKLY:
```
□ Run drift detection on all agents (full window analysis)
□ Validate drift_state table consistency
□ If RED drift sustained > 1 week: escalate to human review
```

---

## 4. Wire 3: Hierarchical Bayesian Model → Pattern Reliability Tracking

### 4.1 What It Replaces

In `architecture_memory.md` Section 5.4.3, `pattern_reliability` stores independent per-cell win rates. With 2,160 possible cells and ~500 trades, most cells have 0–2 observations. The fix replaces the raw `win_rate` computation with a hierarchical shrinkage estimator.

### 4.2 Inbound Wiring

```
TRIGGER: Reflection Agent, during Phase 3 (Extract Lessons)
  │
  ▼
For each pattern used in the trade:
  │
  ├── Read from Long-Term Memory (PostgreSQL):
  │   ├── pattern_reliability (cell-level data)
  │   ├── pattern_reliability (parent-level aggregation)
  │   └── pattern_reliability (global aggregation)
  │
  └── Compute hierarchical estimate:
      HierarchicalPatternReliability.get_win_rate(
          pattern_type, pattern_subtype, symbol, timeframe, regime, session
      )
```

### 4.3 Outbound Wiring

```
HierarchicalPatternReliability returns:
  {
    'win_rate': 0.72,          # Shrinkage estimate
    'ci_low': 0.58,            # 95% CI lower
    'ci_high': 0.84,           # 95% CI upper
    'effective_n': 23.5,       # Effective sample size
    'shrinkage': 0.45,         # How much parent influences
    'confidence': 'MEDIUM'     # HIGH/MEDIUM/LOW
  }
  │
  ▼
Written to pattern_reliability table:
  UPDATE pattern_reliability SET
    win_rate_hierarchical = 0.72,
    ci_low = 0.58, ci_high = 0.84,
    effective_n = 23.5,
    shrinkage_weight = 0.45,
    last_updated = NOW()
  WHERE pattern_type = %s AND symbol = %s AND ...
  │
  ▼
Consumers:
  ├── Signal Aggregator: uses win_rate_hierarchical for confluence bonus/penalty
  ├── Entry Agent: uses win_rate_hierarchical for position sizing
  ├── Reflection Agent: uses confidence level to decide lesson extraction strength
  └── TP Agent: uses win_rate_hierarchical to calibrate TP targets
```

### 4.4 Nightly Consolidation Cron

The hierarchical estimates need periodic recomputation (not per-trade, too expensive). Wire into the existing daily consolidation:

```
EXISTING: End of day (Section 4.5) — Journal Agent compiles daily performance
  │
  ▼
[NEW] After Journal Agent completes, trigger pattern consolidation:
  │
  ▼
nightly_pattern_consolidation():
  ├── For each unique (pattern_type, pattern_subtype, symbol, timeframe, regime, session):
  │   ├── Compute hierarchical estimate
  │   ├── Compute exponentially-weighted estimate (half_life=100 trades)
  │   └── UPDATE pattern_reliability
  │
  └── WRITE to memory/YYYY-MM-DD.md: "Pattern reliability consolidated: N cells updated"
```

### 4.5 Read Path Changes

Every agent that reads `pattern_reliability` must use the hierarchical estimate:

```python
# BEFORE (Section 5.4.3 example query):
# SELECT win_rate FROM pattern_reliability WHERE ...

# AFTER:
SELECT win_rate_hierarchical AS win_rate,
       ci_low, ci_high, effective_n, confidence
FROM pattern_reliability
WHERE ...

# If win_rate_hierarchical IS NULL (first run, no consolidation yet):
# Fall back to raw win_rate with LOW confidence flag
```

### 4.6 Architecture Memory Section Changes

**Section 5.4.3 (Pattern Reliability):** Replace the example query. Add explanation of hierarchical shrinkage. Add `effective_n` and `shrinkage_weight` columns to the schema.

**Section 9.2 (Phase 3 — Extract Lessons):** Pattern reliability updates now call `HierarchicalPatternReliability.get_win_rate()` instead of raw computation.

**Section 12.2 (Cleanup Schedule):** Add to DAILY:
```
□ Run nightly_pattern_consolidation() — recompute hierarchical and EW estimates
```

**Section 10.2 (Example 2 — Pattern Reliability Refinement):** Update the example to show shrinkage behavior:
```
TRADE 1-5: Bullish OBs on EUR/USD H4 — 4 wins, 1 loss
  Raw win_rate: 80% (but CI: [28%, 99%] — meaningless)
  Hierarchical win_rate: 62% (shrunk toward population mean of 55%)
  Effective n: 8.5 (raw 5 + 3.5 from parent)
  Confidence: LOW

TRADE 11-30: 14 wins, 6 losses (70% stable)
  Hierarchical win_rate: 68% (less shrinkage as cell data grows)
  Effective n: 25.2
  Confidence: MEDIUM

TRADE 31-50: 16 wins, 4 losses (80%)
  Hierarchical win_rate: 76% (minimal shrinkage — cell has enough data)
  Effective n: 42.1
  Confidence: HIGH
```

---

## 5. Wire 4: Statistical Significance → Weight Adjustment Triggers

### 5.1 What It Replaces

In `architecture_memory.md` Section 5.4.2, the `update_signal_weight` function adjusts weights after **every trade** with no significance test. The fix gates all adjustments behind a binomial test with Bonferroni correction.

### 5.2 Inbound Wiring

```
TRIGGER: Reflection Agent, during Phase 4 (Update Knowledge)
  │
  ▼
For each agent signal in the trade:
  │
  ├── Read from Long-Term Memory (PostgreSQL):
  │   ├── signal_weights (current weight, accuracy_50, accuracy_total)
  │   └── signal_log (all predictions for this agent/symbol — Wire 6)
  │
  └── Call SignalWeightAdjuster.update_weight(agent_id, symbol, trade_id)
```

### 5.3 The Gated Update Flow

Replace the existing `update_signal_weight` function (Section 5.4.2) entirely:

```python
# ============================================================
# REPLACES: architecture_memory.md Section 5.4.2 update rule
# ============================================================

# OLD (architecture_memory.md):
# new_weight = clip(weight.current + sign(blended - 0.5) * 0.01, 0.05, 0.40)
# new_weight = clip(new_weight, weight.current - 0.03, weight.current + 0.03)

# NEW (wired with significance gate):
def update_signal_weight(agent_id, symbol, trade_id):
    """
    Wired replacement for Section 5.4.2 update rule.
    Only adjusts when statistically significant evidence exists.
    """
    # Step 1: Always record the prediction (Wire 6 feeds this)
    prediction = db.get_prediction(agent_id, symbol, trade_id)
    db.record_prediction_outcome(prediction['id'], correct=prediction['correct'])

    # Step 2: Check minimum sample gate
    n = db.get_prediction_count(agent_id, symbol)
    if n < 20:
        return {'adjusted': False, 'reason': f'Collecting data ({n}/20)'}

    # Step 3: Run significance test (Wire 4 core)
    should, p_value, direction, confidence = adjuster.should_adjust(agent_id, symbol)
    if not should:
        return {'adjusted': False, 'reason': f'Not significant (p={p_value:.4f})'}

    # Step 4: Compute effect-size-scaled adjustment
    adjustment = adjuster.compute_adjustment(agent_id, symbol)

    # Step 5: Apply bounded adjustment (preserves existing bounds from Section 5.4.2)
    current = db.get_signal_weight(agent_id, symbol)
    new_weight = max(0.05, min(0.40, current['weight'] + adjustment))
    new_weight = max(new_weight, current['weight'] - 0.03)  # Preserve ±0.03 cap
    new_weight = min(new_weight, current['weight'] + 0.03)

    # Step 6: Write with evidence
    db.update_signal_weight(
        agent_id, symbol, new_weight,
        reason=f"Significant: p={p_value:.4f}, accuracy={accuracy:.3f}, n={n}",
        evidence={'p_value': p_value, 'accuracy': accuracy, 'n': n,
                  'effect_size': effect_size, 'confidence': confidence}
    )

    # Step 7: Normalize all weights to sum to 1.0 (preserves existing normalization)
    normalize_signal_weights(strategy_id)

    return {'adjusted': True, 'old': current['weight'], 'new': new_weight,
            'p_value': p_value, 'confidence': confidence}
```

### 5.4 Outbound Wiring

```
SignalWeightAdjuster.update_weight() returns:
  │
  ▼
If adjusted:
  ├── UPDATE signal_weights SET weight = new_weight, last_p_value = p_value, ...
  ├── WRITE to memory/YYYY-MM-DD.md: "Weight adjusted: {agent} {symbol} ±{adj}"
  └── EMIT to Redis Stream: stream:weight_changes → {agent, symbol, old, new, reason}

If not adjusted:
  ├── No database change
  └── WRITE to signal_weights.adjustment_evidence: {reason: 'not significant'}
```

### 5.5 Consumer Impact

**Signal Aggregator** reads weights as before — no change to read path. The change is that weights are now only adjusted when there's statistical evidence, so they're more stable.

**Reflection Agent** must be updated to call the gated function instead of the old per-trade adjustment:

```
EXISTING (Section 9.2 Phase 4):
  "3. Propose signal weight adjustments"
  └── Old: ±0.01 per trade, no gate

NEW:
  "3. Propose signal weight adjustments"
  └── Call SignalWeightAdjuster.update_weight()
      └── Only adjusts if p < 0.10 (Bonferroni-corrected)
```

### 5.6 Architecture Memory Section Changes

**Section 5.4.2 (Signal Weights):** Replace the entire `update_signal_weight` Python function with the gated version above. Add `last_p_value` and `adjustment_evidence` columns to the schema.

**Section 9.2 (Phase 4 — Update Knowledge):** Update priority 2 (Signal Weights) description:
```
2. SIGNAL WEIGHTS (auto-approved within bounds, gated by significance)
   - Only adjusted when binomial test p < 0.10 (Bonferroni-corrected)
   - Minimum 20 predictions before any adjustment
   - Effect-size-scaled: larger accuracy gaps → larger adjustments
   - Max ±0.03 per trade (preserved)
   - Min 0.05, Max 0.40 (preserved)
   - Normalized to sum = 1.0 (preserved)
```

**Section 9.4 (Preventing Overfitting):** Update the safeguards table:
```
| Minimum sample size | Lessons require 5+ supporting trades before confidence > 0.6 |
| [NEW] Significance gate | Signal weights require p < 0.10 before adjustment |
| [NEW] Bonferroni correction | Multiple comparison correction for 18 agent-symbol pairs |
```

---

## 6. Wire 5: Counterfactual Data Capture → Journal System

### 6.1 What It Adds

The Journal Agent (Section 6.4) currently creates episodes with actual outcomes only. This wire adds `CounterfactualTracker` as a sub-component that runs immediately after episode creation, computing hypothetical outcomes for 3–5 alternative management strategies using tick data replay.

### 6.2 Inbound Wiring

```
TRIGGER: Journal Agent, during episode creation (Section 6.4 Step 3)
  │
  ▼
After trade_episodes record is written:
  │
  ├── Read from Short-Term Memory (PostgreSQL):
  │   ├── trades table → entry_price, exit_price, stop_loss, direction, atr_at_entry
  │   └── orders table → fill timestamps, partial close records
  │
  ├── Read from Market Data (PostgreSQL):
  │   └── market_data (tick/candle data from entry to exit + 24h buffer)
  │
  └── Call CounterfactualTracker.compute_counterfactuals(trade)
```

### 6.3 Outbound Wiring

```
CounterfactualTracker.compute_counterfactuals() returns:
  {
    'conservative_tp': {exit_price, exit_time, r_multiple, duration_hours, ...},
    'aggressive_tp':   {exit_price, exit_time, r_multiple, duration_hours, ...},
    'structure_trail': {exit_price, exit_time, r_multiple, duration_hours, ...},
    'time_exit_4h':    {exit_price, exit_time, r_multiple, duration_hours, ...},
    'time_exit_24h':   {exit_price, exit_time, r_multiple, duration_hours, ...},
    'no_management':   {exit_price, exit_time, r_multiple, duration_hours, ...},
  }
  │
  ▼
Written to trade_counterfactuals table (new table, fix_learning_loops.md Section 5.4)
  │
  ▼
Also compute vs_actual:
  pnl_vs_actual = counterfactual_pnl - actual_pnl
  r_vs_actual = counterfactual_r - actual_r
  │
  ▼
Consumers:
  ├── Contextual Bandit (Wire 1): uses counterfactual r_multiple as reward for actions not taken
  ├── Reflection Agent: compares actual vs counterfactual for lesson extraction
  ├── TP Agent: reads best_counterfactual view to validate strategy selection
  └── Weekly review: aggregates counterfactual analysis across all trades
```

### 6.4 Integration with Episode Creation

The existing episode creation flow (Section 6.4) gets one additional step:

```
EXISTING (Section 6.4):
  1. Gather all context
  2. Compute embeddings
  3. Write trade_episodes record
  4. Trigger Reflection Agent
  5. Update trade record with episode_id

NEW (with counterfactuals):
  1. Gather all context
  2. Compute embeddings
  3. Write trade_episodes record
  3a. [NEW] Compute counterfactuals → write to trade_counterfactuals
  4. Trigger Reflection Agent (now has counterfactual data available)
  5. Update trade record with episode_id
```

### 6.5 Tick Data Requirement

Counterfactual simulation requires tick-level data from entry to exit + buffer. Wire into the existing market data ingestion:

```
EXISTING: market_data table stores OHLCV candles (Section 3.5)

REQUIRED: Tick-level data or 1m candles for counterfactual simulation

OPTIONS:
  A. Store 1m candles in market_data (adds ~1440 rows/day/symbol)
  B. Use existing tick stream data (Redis Streams, 7-day retention per Section 12.3)
  C. Store only at management action timestamps (partial close, SL move)

RECOMMENDED: Option A (1m candles) — sufficient precision for simulation,
  manageable storage, survives Redis TTL expiry.
```

### 6.6 Architecture Memory Section Changes

**Section 4.5 (Short-Term → Long-Term Promotion):** Add counterfactual computation between steps 3 and 4:
```
3. For each closed trade:
   a. Create/update trade_episodes record with full context
   b. [NEW] Compute counterfactual outcomes → trade_counterfactuals
   c. Update pattern_reliability for patterns used
   d. Feed trade to Reflection Agent for lesson extraction
```

**Section 6.2 (What Makes an Episode):** Add to the episode structure:
```
├── Counterfactual Outcomes (NEW)
│   ├── conservative_tp → {r_multiple, exit_price, exit_time}
│   ├── aggressive_tp → {r_multiple, exit_price, exit_time}
│   ├── structure_trail → {r_multiple, exit_price, exit_time}
│   ├── time_exit_4h → {r_multiple, exit_price, exit_time}
│   ├── time_exit_24h → {r_multiple, exit_price, exit_time}
│   ├── no_management → {r_multiple, exit_price, exit_time}
│   └── best_counterfactual → {strategy_name, r_vs_actual}
```

**Section 6.5 (Why Episodes Matter):** Update the counterfactual bullet:
```
- Counterfactual analysis: [NOW IMPLEMENTED] For every trade, 6 alternative management
  strategies are simulated. The system learns which strategies work best in which conditions
  by comparing actual vs counterfactual outcomes across hundreds of trades.
```

---

## 7. Wire 6: Ablation Analysis → Agent Performance Tracking

### 7.1 What It Replaces

The Reflection Agent (Section 9.2 Phase 2) currently attributes outcomes to individual agents using "simple directional comparison" — checking if an agent's predicted direction matched the outcome. This is confounded because multiple agents vote simultaneously. The fix replaces this with ablation-based causal attribution.

### 7.2 Inbound Wiring

```
TRIGGER: Reflection Agent, during Phase 2 (Reflect on Trade)
  │
  ▼
For each completed trade:
  │
  ├── Read from Episodic Memory (PostgreSQL):
  │   ├── trade_episodes.signals_snapshot → all agent signals at entry
  │   ├── trade_episodes.confluence_score → original confluence
  │   └── trades.outcome → win/loss/breakeven
  │
  ├── Read from Long-Term Memory (PostgreSQL):
  │   └── signal_weights → current weights for confluence recompute
  │
  └── Call CausalAttribution.attribute_trade(trade)
```

### 7.3 Outbound Wiring

```
CausalAttribution.attribute_trade() returns per agent:
  {
    'agent_id': 'smc_agent',
    'criticality': 0.82,           # How much removing this agent changes the decision
    'predictiveness': 1.0,         # Was the agent correct?
    'contribution': 0.89,          # Overall contribution score
    'category': 'CRITICAL_CORRECT', # Classification
    'confluence_drop': 13.0,       # Confluence without this agent
    'would_have_traded_without': True,
    'flipped_confluence': 48.0,    # Confluence if agent voted opposite
  }
  │
  ▼
Written to trade_attributions table (new table, fix_learning_loops.md Section 6.4)
  │
  ▼
Consumers:
  ├── Signal Weight Adjuster (Wire 4): uses attribution category to weight adjustments
  ├── Reflection Agent: uses attribution for lesson extraction (which agent caused the outcome?)
  ├── Weekly review: aggregates attribution across trades to identify systematic biases
  └── Agent health monitoring: tracks criticality trends per agent
```

### 7.4 Signal Log Integration

Ablation analysis needs to know about **all signals**, not just those that led to trades. Wire `signal_log` into the existing signal flow:

```
EXISTING (Section 3.5 Working Memory Lifecycle):
  4. Signal agents write signal:{agent_id}:{symbol}
  5. Signal Aggregator reads all signals → writes confluence:{symbol}
  6. If confluence ≥ threshold → spawn Entry Agent

NEW (with signal logging):
  4. Signal agents write signal:{agent_id}:{symbol}
  4a. [NEW] Log ALL signals to signal_log table (not just trade-linked ones)
      ├── led_to_trade = TRUE if confluence ≥ threshold
      ├── led_to_trade = FALSE if filtered
      ├── filtered_by = 'confluence_low' | 'risk_gate' | 'time_filter' | NULL
      └── confluence_without = confluence score recomputed without this agent
  5. Signal Aggregator reads all signals → writes confluence:{symbol}
  6. If confluence ≥ threshold → spawn Entry Agent
```

### 7.5 Attribution-Informed Weight Updates

Wire 6 feeds into Wire 4. The weight adjustment is no longer just "was the agent correct?" but "was the agent's signal causally important?":

```python
# Wired into Reflection Agent Phase 4 (Update Knowledge):
# REPLACE: "Propose signal weight adjustments" (Section 9.2 Phase 4, item 3)
# WITH:

def update_weights_with_attribution(trade, attributions):
    """
    Attribution-informed weight updates.
    Called by Reflection Agent after CausalAttribution.attribute_trade().
    """
    for agent_id, attr in attributions.items():
        # Skip agents with negligible impact
        if attr['criticality'] < 0.1:
            continue

        # Compute adjustment based on attribution category
        adjustment = ATTRIBUTION_ADJUSTMENTS[attr['category']]

        # Apply through significance gate (Wire 4)
        # This ensures we don't adjust on noise
        n_attributions = db.get_attribution_count(agent_id, trade['symbol'])
        if n_attributions >= 20:
            current = db.get_signal_weight(agent_id, trade['symbol'])
            new_weight = max(0.05, min(0.40, current + adjustment))
            db.update_signal_weight(agent_id, trade['symbol'], new_weight,
                                    reason=f"Attribution: {attr['category']}")

ATTRIBUTION_ADJUSTMENTS = {
    'CRITICAL_CORRECT':     +0.01,
    'CRITICAL_WRONG':       -0.01,
    'NON_CRITICAL_CORRECT': +0.005,
    'NON_CRITICAL_WRONG':   -0.005,
    'CONTRIBUTING':         +0.008,  # or -0.008 based on predictiveness
}
```

### 7.6 Agent Interaction Tracking

Track pairwise synergies (Section 6.6 of fix_learning_loops.md). Wire into the weekly consolidation:

```
EXISTING (Section 12.2 WEEKLY):
  □ Normalize signal_weights (ensure sum = 1.0)

NEW (add to WEEKLY):
  □ Compute agent_interactions: pairwise synergy scores
    ├── For each (agent_a, agent_b, symbol, regime):
    │   ├── Count agree/disagree outcomes
    │   ├── Compute synergy_score = wr_agree - wr_expected
    │   └── UPDATE agent_interactions
    └── Flag pairs with |synergy| > 0.15 for human review
```

### 7.7 Architecture Memory Section Changes

**Section 7.1 (Access Matrix):** Add `signal_log` table as write target for all signal agents (not just trade-linked).

**Section 9.2 (Phase 2 — Reflect on Trade):** Replace the "ATTRIBUTE" section:
```
2. ATTRIBUTE: Which signals were causally important?
   [OLD] Simple directional comparison
   [NEW] Ablation analysis:
   ├── For each agent: recompute confluence without this agent
   ├── For each agent: recompute confluence with this agent flipped
   ├── Classify: CRITICAL_CORRECT, CRITICAL_WRONG, NON_CRITICAL_*, CONTRIBUTING
   └── Write to trade_attributions table
```

**Section 9.2 (Phase 4 — Update Knowledge):** Update priority 2:
```
2. SIGNAL WEIGHTS (attribution-informed, significance-gated)
   - Adjustment magnitude based on attribution category
   - CRITICAL agents get larger adjustments than NON-CRITICAL
   - Only adjusted when p < 0.10 (Wire 4)
   - Minimum 20 attributions before any adjustment
```

**Section 10.2 (Example 1 — Signal Weight Adaptation):** Update to show attribution-informed learning:
```
TRADE 50: SMC Agent detected bullish OB, trade won (+1.5R)
  Attribution: CRITICAL_CORRECT (confluence dropped 15 without SMC)
  → SMC weight for EUR/USD: 0.15 → 0.16 (+0.01, full adjustment)

TRADE 51: Momentum Agent divergence signal was wrong, but trade won anyway
  Attribution: NON_CRITICAL_WRONG (confluence still above threshold without Momentum)
  → Momentum weight for EUR/USD: 0.10 → 0.095 (-0.005, small penalty)
```

---

## 8. Integration Map: All Wires Together

### 8.1 Complete Data Flow with All Wires

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    WIRED SELF-IMPROVEMENT SYSTEM                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  TRADE CLOSED                                                            │
│     │                                                                    │
│     ▼                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐       │
│  │ JOURNAL AGENT (existing + Wire 5)                            │       │
│  │  1. Gather context (existing)                                │       │
│  │  2. Compute embeddings (existing)                            │       │
│  │  3. Write trade_episodes (existing)                          │       │
│  │  3a. [WIRE 5] Compute counterfactuals → trade_counterfactuals│       │
│  │  4. Trigger Reflection Agent                                 │       │
│  └──────────────────────────┬───────────────────────────────────┘       │
│                             │                                            │
│                             ▼                                            │
│  ┌──────────────────────────────────────────────────────────────┐       │
│  │ REFLECTION AGENT (existing + Wires 2,3,4,6)                  │       │
│  │                                                              │       │
│  │  0. [WIRE 2] Drift check (every 20 trades)                   │       │
│  │     ├── GREEN → proceed normally                             │       │
│  │     ├── AMBER → discount confidence 25%, increase exploration│       │
│  │     └── RED → halve confidence, reset priors, alert human    │       │
│  │                                                              │       │
│  │  1. Compare predicted vs actual (existing)                   │       │
│  │                                                              │       │
│  │  2. [WIRE 6] Ablation-based attribution (replaces directional│       │
│  │     comparison) → trade_attributions                         │       │
│  │                                                              │       │
│  │  3. [WIRE 3] Hierarchical pattern reliability (replaces      │       │
│  │     independent per-cell) → pattern_reliability              │       │
│  │                                                              │       │
│  │  4. [WIRE 4] Significance-gated weight adjustment            │       │
│  │     (replaces per-trade adjustment) → signal_weights         │       │
│  │                                                              │       │
│  │  5. Extract lessons (existing, but with attribution-informed │       │
│  │     confidence and drift-adjusted thresholds)                │       │
│  │                                                              │       │
│  │  6. [WIRE 1] Update bandit posterior with actual +           │       │
│  │     counterfactual rewards                                   │       │
│  └──────────────────────────┬───────────────────────────────────┘       │
│                             │                                            │
│                             ▼                                            │
│  ┌──────────────────────────────────────────────────────────────┐       │
│  │ DRIFT MONITOR (Wire 2 — cron, every 20 trades)               │       │
│  │  • Per-agent signal accuracy drift (Page-Hinkley)            │       │
│  │  • Volatility regime drift                                   │       │
│  │  • Regime transition frequency                               │       │
│  │  • Win rate trend                                            │       │
│  │  → Updates drift_state table + Redis working memory          │       │
│  └──────────────────────────────────────────────────────────────┘       │
│                                                                          │
│  NEXT TRADE CYCLE                                                        │
│     │                                                                    │
│     ▼                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐       │
│  │ TP AGENT (Wire 1)                                            │       │
│  │  1. Build context vector from working memory                 │       │
│  │  2. Query ContextualBanditTP → select TP strategy            │       │
│  │  3. Or: lookup management_rules table for pre-computed rules  │       │
│  │  4. Write tp_strategy:{trade_id} to working memory           │       │
│  └──────────────────────────────────────────────────────────────┘       │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────┐       │
│  │ SIGNAL AGGREGATOR (Wires 2, 3, 4)                            │       │
│  │  1. Read signal weights (drift-adjusted if AMBER/RED)        │       │
│  │  2. Read pattern reliability (hierarchical estimates)        │       │
│  │  3. Compute confluence score                                 │       │
│  │  4. [WIRE 6] Log ALL signals to signal_log (not just trades) │       │
│  └──────────────────────────────────────────────────────────────┘       │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────┐       │
│  │ ALL SIGNAL AGENTS (Wire 6)                                   │       │
│  │  1. Generate signal (existing)                               │       │
│  │  2. [WIRE 6] Log signal to signal_log table                  │       │
│  │     ├── led_to_trade: determined after confluence check      │       │
│  │     ├── filtered_by: set by Risk Gate if filtered            │       │
│  │     └── confluence_without: computed by ablation             │       │
│  └──────────────────────────────────────────────────────────────┘       │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 8.2 New Tables Summary

| Table | Wire | Written By | Read By |
|-------|------|-----------|---------|
| `trade_counterfactuals` | 5 | Journal Agent | Bandit, Reflection, TP Agent |
| `trade_attributions` | 6 | Reflection Agent | Weight Adjuster, Weekly Review |
| `signal_log` | 6 | Signal Agents + Aggregator | Attribution, Precision/Recall |
| `agent_interactions` | 6 | Weekly Cron | Reflection Agent, Review |
| `drift_state` | 2 | DriftMonitor Cron | All agents (via signal weight discount) |
| `management_rules` | 1 | Monthly Cron (offline) | TP Agent |

### 8.3 Modified Tables Summary

| Table | Wire | Changes |
|-------|------|---------|
| `signal_weights` | 4, 6 | Add `last_p_value`, `last_attribution_category`, `adjustment_evidence`, `n_attributions` |
| `pattern_reliability` | 3 | Add `win_rate_hierarchical`, `ci_low`, `ci_high`, `effective_n`, `shrinkage_weight`, `win_rate_ew`, `ew_effective_n` |
| `trade_episodes` | 5 | Add counterfactual references (link to trade_counterfactuals) |

### 8.4 New Cron Jobs

| Cron | Wire | Frequency | Purpose |
|------|------|-----------|---------|
| `drift_monitor` | 2 | Every 20 trades | Check for concept drift |
| `pattern_consolidation` | 3 | Daily (end of session) | Recompute hierarchical + EW estimates |
| `agent_interactions` | 6 | Weekly (Sunday) | Compute pairwise synergy scores |
| `management_rules_compute` | 1 | Monthly | Offline optimal management parameter search |

---

## 9. Modified Architecture Sections

### 9.1 Section 5.4.2 — Signal Weights (Modified)

**Replace the update rule with:**

```python
def update_signal_weight(agent_id, symbol, trade_id):
    """
    [WIRED] Significance-gated, attribution-informed weight adjustment.
    Replaces the old per-trade ±0.01 adjustment.

    Gates:
    1. Minimum 20 predictions (Wire 4)
    2. Binomial test p < 0.10, Bonferroni-corrected (Wire 4)
    3. Attribution-based adjustment magnitude (Wire 6)
    4. Drift-adjusted if AMBER/RED (Wire 2)
    """
    # Record prediction (always)
    record_prediction(agent_id, symbol, trade_id)

    # Minimum sample gate
    n = get_prediction_count(agent_id, symbol)
    if n < 20:
        return  # Collecting

    # Significance test
    should, p_value, direction, confidence = significance_test(agent_id, symbol)
    if not should:
        return  # Not significant

    # Attribution-informed adjustment (if available)
    attribution = get_latest_attribution(agent_id, trade_id)
    if attribution and attribution['criticality'] >= 0.1:
        adjustment = ATTRIBUTION_ADJUSTMENTS[attribution['category']]
    else:
        adjustment = direction * min(0.03, abs(accuracy - 0.50) * 0.1)

    # Drift discount
    drift = get_drift_state()
    if drift['level'] == 'AMBER':
        adjustment *= 0.75
    elif drift['level'] == 'RED':
        adjustment *= 0.50

    # Apply bounded
    current = get_weight(agent_id, symbol)
    new_weight = max(0.05, min(0.40, current + adjustment))
    new_weight = clip(new_weight, current - 0.03, current + 0.03)
    update_weight(agent_id, symbol, new_weight, p_value=p_value)
    normalize_weights()
```

### 9.2 Section 5.4.3 — Pattern Reliability (Modified)

**Replace the win rate computation with:**

```python
def get_pattern_win_rate(pattern_type, symbol, regime, session):
    """
    [WIRED] Hierarchical Bayesian estimate with time weighting.
    Replaces independent per-cell win_rate = successes / total.

    When cell has < 15 observations, estimate is shrunk toward
    parent-level (pattern_type) mean. As observations accumulate,
    converges to cell-specific estimate.
    """
    result = hierarchical_model.get_win_rate(
        pattern_type=pattern_type, symbol=symbol,
        regime=regime, session=session
    )

    # Blend hierarchical with exponentially-weighted
    ew_result = hierarchical_model.get_time_weighted_win_rate(
        pattern_type=pattern_type, symbol=symbol, regime=regime,
        half_life_trades=100
    )

    # Use EW if we have enough data, otherwise hierarchical
    if ew_result['effective_n'] >= 10:
        return ew_result['win_rate']
    return result['win_rate']
```

### 9.3 Section 9.2 — Reflection Agent Phases (Modified)

**Phase 2 (Reflect) — Replace attribution:**

```
EXISTING:
  2. ATTRIBUTE: Which signals were predictive?
     → Simple directional check

NEW [WIRE 6]:
  2. ATTRIBUTE: Which signals were causally important?
     → CausalAttribution.attribute_trade(trade)
     → Ablation: remove each agent, recompute confluence
     → Counterfactual: flip each agent's signal
     → Classification: CRITICAL_CORRECT, CRITICAL_WRONG, etc.
     → Write to trade_attributions table
```

**Phase 3 (Extract Lessons) — Add hierarchical pattern stats:**

```
EXISTING:
  3. Update pattern_reliability for patterns used
     → Raw win_rate = successes / total

NEW [WIRE 3]:
  3. Update pattern_reliability for patterns used
     → HierarchicalPatternReliability.get_win_rate()
     → Shrinkage estimate with confidence interval
     → Time-weighted estimate (half-life = 100 trades)
```

**Phase 4 (Update Knowledge) — Gate weight adjustments:**

```
EXISTING:
  4. Propose signal weight adjustments
     → ±0.01 per trade, no gate

NEW [WIRE 4]:
  4. Propose signal weight adjustments (significance-gated)
     → SignalWeightAdjuster.update_weight()
     → Only if p < 0.10 (Bonferroni-corrected)
     → Attribution-informed magnitude (Wire 6)
     → Drift-adjusted (Wire 2)
```

**Add Phase 0 — Drift pre-check:**

```
NEW [WIRE 2]:
  0. Drift pre-check (every 20 trades)
     → DriftMonitor.check_drift()
     → GREEN/AMBER/RED response
     → Affects all subsequent phases
```

### 9.4 Section 6.4 — Episode Creation (Modified)

```
EXISTING:
  1. Gather all context
  2. Compute embeddings
  3. Write trade_episodes record
  4. Trigger Reflection Agent
  5. Update trade record with episode_id

NEW [WIRE 5]:
  1. Gather all context
  2. Compute embeddings
  3. Write trade_episodes record
  3a. [NEW] CounterfactualTracker.compute_counterfactuals(trade)
      → Simulate 6 alternative management strategies
      → Write to trade_counterfactuals table
      → Compute pnl_vs_actual, r_vs_actual
  4. Trigger Reflection Agent (now has counterfactual data)
  5. Update trade record with episode_id
```

### 9.5 Section 12.2 — Cleanup Schedule (Modified)

**Add to DAILY:**
```
□ Run nightly_pattern_consolidation()
  └── Recompute hierarchical + EW estimates for all pattern cells
□ Run drift_monitor check
  └── Update drift_state, trigger responses if AMBER/RED
```

**Add to WEEKLY:**
```
□ Compute agent_interactions (pairwise synergy scores)
□ Validate signal_log completeness (all signals logged, not just trade-linked)
□ Run true_precision_recall per agent (using signal_log)
```

**Add to MONTHLY:**
```
□ Compute management_rules (offline optimization over historical trades)
□ Full drift analysis (all agents, all symbols, full window)
□ Counterfactual analysis report (which strategies would have been best?)
```

---

## 10. Implementation Checklist

### Phase 1: Foundation (Weeks 1–3)

```
□ WIRE 6 — Signal logging
  □ Create signal_log table
  □ Modify Signal Aggregator to log ALL signals (not just trade-linked)
  □ Add confluence_without computation to signal logging
  □ Test: verify all signals appear in signal_log

□ WIRE 6 — Ablation attribution
  □ Create trade_attributions table
  □ Implement CausalAttribution class
  □ Wire into Reflection Agent Phase 2
  □ Test: verify attribution scores on 10+ paper trades

□ WIRE 4 — Significance gating
  □ Implement SignalWeightAdjuster with binomial test
  □ Add Bonferroni correction
  □ Replace old update_signal_weight in Reflection Agent
  □ Test: verify no weight adjustments when p > 0.10
```

### Phase 2: Structural (Weeks 4–6)

```
□ WIRE 5 — Counterfactual capture
  □ Create trade_counterfactuals table
  □ Implement CounterfactualTracker class
  □ Ensure 1m candle data available for simulation
  □ Wire into Journal Agent episode creation flow
  □ Test: verify counterfactuals computed on 10+ paper trades

□ WIRE 1 — Contextual bandit
  □ Implement ContextualBanditTP class
  □ Create management_rules table
  □ Wire into TP Agent (replace fixed TP logic)
  □ Wire counterfactual rewards into bandit update
  □ Test: verify bandit selects strategies and updates posteriors

□ WIRE 3 — Hierarchical Bayesian
  □ Implement HierarchicalPatternReliability class
  □ Add hierarchical columns to pattern_reliability table
  □ Implement nightly_pattern_consolidation cron
  □ Update Signal Aggregator read path to use hierarchical estimates
  □ Test: verify shrinkage behavior with sparse cells
```

### Phase 3: Drift & Monitoring (Weeks 7–8)

```
□ WIRE 2 — Concept drift detection
  □ Implement DriftMonitor with Page-Hinkley test
  □ Create drift_state table
  □ Wire drift check into Reflection Agent Phase 0
  □ Wire drift responses (confidence discount, prior reset)
  □ Wire drift-adjusted weights into Signal Aggregator
  □ Test: verify drift detection triggers on synthetic regime change

□ WIRE 6 — Agent interactions
  □ Create agent_interactions table
  □ Implement weekly synergy computation cron
  □ Test: verify synergy scores on accumulated data

□ Integration testing
  □ Run 50+ paper trades with all 6 wires active
  □ Verify data flows: counterfactuals → bandit → TP selection
  □ Verify drift detection → confidence discount → weight stability
  □ Verify ablation → attribution → significance-gated weight updates
  □ Verify hierarchical patterns → stable estimates with sparse data
```

---

## Appendix: Wire Compatibility with Existing Architecture

| Architecture Component | Status | Wire Impact |
|----------------------|--------|-------------|
| Working Memory (Redis) | Unchanged | Wire 2 adds `drift_state:{symbol}` key |
| Short-Term Memory (PG) | Unchanged | No schema changes |
| Long-Term Memory (PG) | Modified | 3 tables modified, 6 tables added |
| Episodic Memory (PG + pgvector) | Modified | Episode structure extended with counterfactual refs |
| Signal Aggregator | Modified | Reads drift-adjusted weights, hierarchical patterns |
| TP Agent | Replaced | Now uses ContextualBanditTP + management_rules |
| Reflection Agent | Modified | All 4 phases updated (drift, attribution, hierarchical, significance) |
| Journal Agent | Modified | Step 3a added (counterfactual computation) |
| Signal Agents | Modified | Now log all signals to signal_log |
| Redis Streams | Unchanged | Existing streams still used for pipeline routing |
| Memory Decay | Unchanged | Existing decay algorithm still applies |
| Semantic Search | Unchanged | Embedding generation unchanged |
| Memory Consolidation | Extended | Daily + weekly + monthly jobs added |

**Bottom line:** The four-layer memory architecture is preserved. Working memory and short-term memory are unchanged. Long-term memory gets new tables and modified computation. Episodic memory gets counterfactual data. The learning loop phases are updated but the loop structure itself (trade → reflect → extract → update → apply) is preserved.

---

*Document generated: 2026-07-11*
*Author: Self-Improvement Wiring Agent — Alpha Stack*
*Status: Wiring Specification Complete — Ready for Implementation*
*Next: Begin Phase 1 implementation (signal logging + ablation attribution + significance gating)*
