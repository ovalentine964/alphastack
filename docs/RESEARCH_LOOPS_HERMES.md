# Research: Loop Systems & Hermes Emerging Patterns for AlphaStack

> **Date:** 2026-07-16  
> **Author:** Loop Systems & Hermes Emerging Patterns Research Agent  
> **Scope:** Loop patterns, Hermes agent patterns, and their application to AlphaStack's trading system  
> **Status:** Research Complete — Ready for Architecture Integration  

---

## Table of Contents

- [PART 1: LOOP SYSTEMS](#part-1-loop-systems)
  - [1. Feedback Loops](#1-feedback-loops)
  - [2. Learning Loops](#2-learning-loops)
  - [3. Correction Loops](#3-correction-loops)
  - [4. Risk Feedback Loops](#4-risk-feedback-loops)
  - [5. Market Feedback Loops](#5-market-feedback-loops)
- [PART 2: HERMES EMERGING PATTERNS](#part-2-hermes-emerging-patterns)
  - [1. Skill Creation from Experience](#1-skill-creation-from-experience)
  - [2. Bounded Memory with Forced Prioritization](#2-bounded-memory-with-forced-prioritization)
  - [3. Self-Improving Agent Loops](#3-self-improving-agent-loops)
  - [4. Mixture of Experts](#4-mixture-of-experts)
  - [5. Recursive Self-Improvement](#5-recursive-self-improvement)
- [PART 3: PROBLEM-SOLUTION MAP](#part-3-problem-solution-map)
  - [Loop Systems Problem-Solution Matrix](#loop-systems-problem-solution-matrix)
  - [Hermes Patterns Problem-Solution Matrix](#hermes-patterns-problem-solution-matrix)
  - [Priority Implementation Order](#priority-implementation-order)
- [APPENDIX: References](#appendix-references)

---

# PART 1: LOOP SYSTEMS

## 1. Feedback Loops

### 1.1 What Are Feedback Loops?

A feedback loop is a cycle where the output of a process becomes input for the next iteration. In trading, every trade outcome should inform the next trade decision. The loop is: **Action → Outcome → Measurement → Adjustment → New Action**.

There are two types:
- **Positive feedback loops** amplify a signal (e.g., winning streak → increased confidence → larger positions → larger wins/losses)
- **Negative feedback loops** dampen a signal (e.g., losing streak → reduced position size → smaller losses → stabilization)

Trading systems need **negative feedback loops for risk** and **positive feedback loops for edge refinement**.

### 1.2 How Trade Outcome Feeds Back to Strategy Adjustment

```
TRADE CLOSED (EURUSD long, +2R, +$6.75)
    │
    ▼
REFLECTION AGENT (Step 16 — src/alphastack/agents/reflection/agent.py)
    │
    ├── Records: entry signals, confluence score, execution quality, outcome
    ├── Computes: R-multiple, MAE, MFE, slippage
    ├── Attributes: which signals were CRITICAL_CORRECT vs CRITICAL_WRONG
    │   (ablation analysis — see fix_learning_loops.md §6)
    │
    ▼
KNOWLEDGE UPDATE
    ├── Signal weights adjusted (statistically gated, p < 0.10)
    ├── Pattern reliability updated (hierarchical Bayesian)
    ├── Contextual bandit posterior updated (Thompson Sampling)
    ├── Management rules recomputed (offline, nightly)
    │
    ▼
NEXT TRADE
    ├── Memory-augmented pipeline loads updated weights
    ├── Pattern confidence scores reflect new evidence
    ├── TP strategy selected by bandit with updated posterior
    └── Management rules reflect optimal parameters
```

### 1.3 How Price Movement Feeds Back to Signal Confidence

```
PRICE TICK (EURUSD = 1.0850)
    │
    ▼
LIQUIDITY AGENT (Step 6 — src/alphastack/strategy/steps/s06_liquidity.py)
    ├── Detects price approaching H4 order block at 1.0835-1.0850
    ├── Signals: liquidity_pool_detected, proximity_score = 0.85
    │
    ▼
SIGNAL AGGREGATOR (Step 10 — src/alphastack/strategy/steps/s10_confluence.py)
    ├── Receives signals from S/R, Liquidity, SMC, Momentum, Candlestick
    ├── Computes confluence score with updated weights
    ├── Score = 78 → Grade A → Trade proposal generated
    │
    ▼
RISK GATE (Step 12 — src/alphastack/strategy/steps/s12_stop_loss.py)
    ├── Checks: position sizing uses latest drawdown state
    ├── Checks: correlation exposure uses current positions
    └── Approved → Execution
```

### 1.4 Where in AlphaStack This Helps

| Component | Current State | Feedback Loop Enhancement |
|-----------|--------------|--------------------------|
| `ReflectionAgent.execute()` | Computes performance, generates adjustments | Already implements the core feedback loop — outputs feed back to strategy parameters |
| `strategy/pipeline.py` | Sequential 16-step pipeline | Needs memory-augmented injection point where updated weights/lessons are loaded before Step 9 |
| `ConfluenceEngine` (Step 10) | Uses fixed weights from config | Should load `signal_weights` from PostgreSQL (L3 memory) — weights that reflect accumulated feedback |
| `PositionSizingStep` (Step 11) | Uses fixed `risk_per_trade` from config | Should adjust based on recent drawdown and win rate (feedback from recent performance) |
| `TradeManagementStep` (Step 14) | Uses static management rules | Should load `management_rules` from offline-computed lookup tables (feedback from counterfactual analysis) |

**Key feedback point:** The `MemoryAugmentedPipeline.get_memory_context()` call (described in `architecture_memory.md` §5.6) is the primary injection point where all accumulated feedback enters the next trade cycle.

---

## 2. Learning Loops

### 2.1 What Are Learning Loops?

A learning loop is a feedback loop specifically designed to improve system performance over time. The cycle is: **Experience → Reflection → Knowledge → Application → New Experience**. Unlike simple feedback loops, learning loops involve **knowledge distillation** — transforming raw experience into reusable rules.

### 2.2 How Win/Loss Analysis Drives Parameter Tuning

AlphaStack's learning loop has 6 stages (from `fix_learning_loops.md`):

```
STAGE 1: REFLECT (Post-Trade)
    ├── Ablation attribution: remove each agent's signal, recompute confluence
    │   ├── If removing SMC agent drops confluence from 85 → 52 → SMC was CRITICAL
    │   ├── If removing RSI agent drops confluence from 85 → 78 → RSI was NON-CRITICAL
    │   └── Result: per-agent criticality + predictiveness scores
    │
    ├── Counterfactual tracking: simulate 5 alternative management strategies
    │   ├── Conservative TP: what if TP1=1.0R instead of 1.5R?
    │   ├── Aggressive TP: what if TP1=2.0R?
    │   ├── Structure trail: what if trailed at swing low instead of ATR?
    │   ├── Time exit: what if exited after 4h regardless?
    │   └── No management: what if just held to TP or SL?
    │
    └── Concept drift check (every 20 trades):
        ├── Page-Hinkley test on agent prediction accuracy
        ├── Volatility regime comparison (recent ATR vs historical)
        └── Regime transition frequency

STAGE 2: EXTRACT (Knowledge Distillation)
    ├── Generate embedding for trade episode
    ├── Tag with structured metadata (symbol, regime, session, setup_type)
    ├── Compute hierarchical Bayesian pattern reliability
    │   ├── If cell has < 15 observations → borrow from parent level
    │   └── If cell has 30+ observations → trust cell-level estimate
    └── Create Lesson object with confidence + confidence interval

STAGE 3: UPDATE (Knowledge Base)
    ├── Signal weights: ONLY adjust if p < 0.10 (Bonferroni corrected)
    ├── Pattern reliability: update hierarchical estimates
    ├── Contextual bandit: update posterior with counterfactual rewards
    ├── Management rules: trigger offline recomputation (nightly cron)
    └── Lessons: store or reinforce existing lesson

STAGE 4: STORE (Persistence)
    ├── Episode → ClickHouse (L4) + pgvector embedding
    ├── Lesson → PostgreSQL (L3) with Bayesian confidence
    ├── Pattern → PostgreSQL (L3) with hierarchical estimates
    └── Signals → Redis (L2) with 24h TTL

STAGE 5: APPLY (Next Trade)
    ├── Memory context loader fetches relevant episodes + lessons
    ├── Signal weights reflect accumulated evidence
    ├── Pattern confidence reflects actual reliability
    └── Bandit selects TP strategy based on learned posterior

STAGE 6: COMPOUND (Long-Term)
    ├── After 100 trades: accurate pattern reliability per pair/session/regime
    ├── After 200 trades: calibrated signal weights reflecting actual predictive power
    ├── After 500 trades: robust management rules from counterfactual analysis
    └── Continuous: bandit posterior converges to optimal TP strategy selection
```

### 2.3 How Pattern Recognition Becomes Skill Creation

This is where Hermes' `/learn` pattern maps directly to AlphaStack:

```
PATTERN DETECTED (e.g., "H4 bullish OB at D1 support with RSI oversold in London session")
    │
    ├── Observed 15 times, 12 wins (80% win rate, CI: 0.56-0.94)
    │
    ▼
SKILL CREATION (analogous to Hermes /learn)
    ├── Encode as structured rule:
    │   "When [H4 OB at D1 support] AND [RSI < 30 on H1] AND [London session]:
    │    → Enter long at OB mid, SL below OB low + buffer, TP at 1.5R"
    │
    ├── Attach metadata:
    │   ├── confidence: 0.72 (Bayesian posterior)
    │   ├── sample_size: 15
    │   ├── regime: trending_bull
    │   ├── symbols: [EURUSD, GBPUSD]
    │   └── last_reinforced: 2026-07-15
    │
    └── Store as "trading skill" in lessons table (L3)
        └── Retrieved via semantic search when similar setup appears
```

### 2.4 Where in AlphaStack This Helps

| Component | Learning Loop Application |
|-----------|--------------------------|
| `src/alphastack/agi/memory.py` — `EpisodicMemory` | Already stores trade episodes with similarity scoring. Enhancement: add embedding-based semantic search and hierarchical consolidation. |
| `src/alphastack/agi/memory.py` — `consolidation()` | Moves short-term → long-term. Enhancement: add Bayesian confidence updates during consolidation. |
| `src/alphastack/agents/reflection/agent.py` | Currently computes win rate and profit factor. Enhancement: add ablation attribution (Fix 6) and counterfactual tracking (Fix 5). |
| `src/alphastack/strategy/steps/s07_smc.py` | SMC pattern detection. Enhancement: pattern reliability lookup when scoring OBs — weight by actual historical win rate, not fixed confidence. |
| `src/alphastack/strategy/steps/s10_confluence.py` | Confluence scoring. Enhancement: load adaptive signal weights from `signal_weights` table instead of hardcoded weights. |
| `src/alphastack/strategy/steps/s13_take_profit.py` | TP selection. Enhancement: use contextual bandit to select TP strategy (conservative/balanced/aggressive) based on learned posterior. |

**Critical gap identified:** The current `ReflectionAgent` (`src/alphastack/agents/reflection/agent.py`) generates adjustment recommendations but has no mechanism to **apply** them back to the pipeline. The `_generate_adjustments()` method returns recommendations like `"increase min_confluence_score by 0.1"` but these are never consumed by downstream steps. This is the **broken link** in the learning loop — the loop generates knowledge but doesn't inject it back.

**Fix:** Wire `strategy_adjustments` from ReflectionAgent output into a persistent store (PostgreSQL `signal_weights` / `management_rules` tables) that the pipeline reads at decision time.

---

## 3. Correction Loops

### 3.1 What Are Correction Loops?

A correction loop detects errors and systematically fixes them. In trading: **Wrong prediction → Identify root cause → Adjust parameters → Avoid same mistake**. Unlike learning loops (which improve general performance), correction loops target **specific failure modes**.

### 3.2 How Wrong Predictions Get Corrected

```
TRADE LOST (-1.5R, EURUSD long)
    │
    ▼
REFLECTION AGENT: Root Cause Analysis
    │
    ├── Was the SMC pattern real? → Check: was there actual institutional buying?
    │   └── Answer: OB was mitigated but price didn't hold → OB quality was poor
    │       CORRECTION: Increase OB validation requirements (volume + structure context)
    │
    ├── Was the RSI signal correct? → Check: RSI was 28 (oversold)
    │   └── Answer: RSI was correct but in a strong downtrend → RSI oversold ≠ reversal
    │       CORRECTION: In bearish regime, require RSI divergence (not just oversold)
    │
    ├── Was the session analysis correct? → Check: London session, high volatility
    │   └── Answer: Correct session but NFP was in 2 hours → event proximity risk
    │       CORRECTION: Enforce 30-min pre-news blackout (already in Risk Gate)
    │
    └── Was the regime detection correct? → Check: HMM said trending_bull
        └── Answer: HMM hadn't retrained since last week → stale regime model
            CORRECTION: Retrain HMM when drift detector triggers RED

    ▼
SPECIFIC CORRECTIONS APPLIED:
    ├── OB validation rule: add volume_ratio > 1.2 requirement
    ├── RSI signal: in bearish regime, require hidden bullish divergence, not just oversold
    ├── Regime model: force retrain when drift_score > 0.6
    └── Pattern reliability: H4 OB without volume confirmation → demote from 80% to 65% win rate
```

### 3.3 How the System Avoids Repeating the Same Mistake

The key mechanism is the **Lesson** object (from `architecture_memory.md` §5.3):

```python
Lesson(
    lesson_id="lesson_abc123",
    trade_id="trade_xyz789",
    instrument="EURUSD",
    regime="trending_bear",
    session="london",
    setup_type="ob_bounce",
    category="entry",
    description="H4 bullish OB failed in bearish regime — OB alone insufficient",
    rule="IF regime == bearish AND setup == ob_bounce THEN require_rsi_divergence = True",
    confidence=0.65,  # Starts moderate, reinforced/contradicted by future trades
    sample_size=1,
    supporting_trades=["trade_xyz789"],
    contradicting_trades=[],
    status="active"
)
```

On the **next** similar setup, the Memory Context Loader (`get_memory_context()`) retrieves this lesson and injects it into the pipeline. The entry logic checks: "Do I have a lesson about OB bounces in bearish regimes?" → Yes → Apply the rule: require RSI divergence.

### 3.4 Where in AlphaStack This Helps

| Component | Correction Loop Enhancement |
|-----------|---------------------------|
| `src/alphastack/agi/reasoning.py` — `ChainOfThoughtEngine` | Currently does basic bullish/bearish signal counting. Enhancement: incorporate lessons from past failures as constraints in the reasoning chain. "Before concluding bullish, check if there's a lesson about this pattern failing." |
| `src/alphastack/agi/planning.py` — `TradePlanner` | Currently creates bull/bear/sideways scenarios with equal probability. Enhancement: adjust scenario probabilities based on pattern reliability from past corrections. |
| `src/alphastack/strategy/steps/s07_smc.py` — `SmartMoneyConcepts` | OB/FVG detection. Enhancement: check `lessons` table for known failure modes of detected patterns before scoring. |
| `src/alphastack/strategy/steps/s09_candlestick.py` — `CandlestickConfirmation` | Pattern detection. Enhancement: flag patterns that have lessons attached (known failure conditions). |
| `src/alphastack/agents/reflection/agent.py` — `_extract_learnings()` | Currently generates generic text learnings. Enhancement: generate structured `Lesson` objects with actionable rules that can be machine-interpreted. |

**Key architectural gap:** The current `_extract_learnings()` method returns `list[str]` (human-readable strings). These are not machine-readable and cannot be applied by downstream agents. The fix is to return structured `Lesson` objects with conditions and actions that the pipeline can evaluate.

---

## 4. Risk Feedback Loops

### 4.1 What Are Risk Feedback Loops?

Risk feedback loops adjust risk exposure based on recent risk outcomes. The cycle is: **Risk event → Measure impact → Adjust exposure → New risk level**. These are **negative feedback loops** — they dampen risk-taking after losses and cautiously expand after wins.

### 4.2 How Drawdown Reduces Position Size

```
PORTFOLIO STATE: Current drawdown = 8% (approaching 10% alert threshold)
    │
    ▼
RISK GOVERNOR (src/alphastack/risk/governor.py)
    ├── drawdown_current = 8%
    ├── drawdown_alert = 10%
    ├── drawdown_halt = 15%
    │
    ├── CALCULATION:
    │   dd_ratio = 8% / 10% = 0.80
    │   position_multiplier = 1.0 - (0.80 * 0.5) = 0.60  # 40% reduction
    │
    └── RESULT: All new position sizes multiplied by 0.60
        ├── Normal trade: 0.02 lots → 0.012 lots
        ├── High-confluence trade: 0.03 lots → 0.018 lots
        └── Effect: smaller losses if drawdown continues

RECOVERY PATH:
    ├── Drawdown recovers to 5%
    │   dd_ratio = 5% / 10% = 0.50
    │   position_multiplier = 1.0 - (0.50 * 0.3) = 0.85  # 15% reduction
    │
    └── Drawdown recovers to 0%
        position_multiplier = 1.0  # Full size restored
```

### 4.3 How Winning Streaks Cautiously Increase Exposure

```
RECENT PERFORMANCE: 8 wins in last 10 trades (80% win rate)
    │
    ▼
REFLECTION AGENT: Performance analysis
    ├── Recent win rate: 80% (vs historical 55%)
    ├── Recent profit factor: 3.2 (vs historical 1.8)
    ├── Streak: 5 consecutive wins
    │
    ├── CHECK: Is this statistically significant?
    │   ├── n = 10, p-value = 0.055 (binomial test vs 0.50)
    │   ├── Bonferroni corrected alpha = 0.10 / 18 = 0.0056
    │   └── Result: NOT significant at corrected alpha → NO adjustment yet
    │
    ├── CHECK: Is this concept drift?
    │   ├── Page-Hinkley test: no drift detected
    │   └── Volatility: normal range
    │
    └── CONSERVATIVE ADJUSTMENT:
        ├── Win rate confidence: 0.72 (moderate)
        ├── Adjustment: +0.02 position size multiplier (1.00 → 1.02)
        ├── Cap: never exceed 1.2x base size regardless of streak
        └── Hysteresis: don't adjust by more than 0.03 per week
```

### 4.4 Where in AlphaStack This Helps

| Component | Current State | Risk Feedback Enhancement |
|-----------|--------------|--------------------------|
| `src/alphastack/risk/governor.py` | Has `RiskGovernor` class | Needs drawdown-based position size multiplier (currently not implemented) |
| `src/alphastack/risk/position_sizer.py` | Has `PositionSizer` | Needs to accept `drawdown_multiplier` parameter from governor |
| `src/alphastack/risk/circuit_breaker.py` | Has circuit breaker logic | Already implements the hard stop (15% flatten). Enhancement: add graduated response (10% reduce, 12.5% heavy reduce) |
| `src/alphastack/strategy/steps/s11_sizing.py` — `PositionSizingStep` | Position sizing step in pipeline | Should query current drawdown state from Redis (`state:portfolio`) and apply multiplier |
| `src/alphastack/agents/risk/agent.py` — `RiskAgent` | Evaluates trade proposals | Should inject drawdown-adjusted sizing into risk check |
| `src/alphastack/risk/drawdown.py` | Has drawdown tracking | Enhancement: expose `get_position_multiplier()` method that returns the current risk-adjusted multiplier |

**Critical integration point:** The `PositionSizingStep` (Step 11 in `pipeline.py`) currently computes position size from risk percentage and stop distance. It needs an additional input: the risk-adjusted multiplier from the risk governor. This multiplier should flow through the shared state (`AlphaStackState`).

---

## 5. Market Feedback Loops

### 5.1 What Are Market Feedback Loops?

Market feedback loops adjust strategy when market conditions change. The cycle is: **Market regime change → Detect change → Switch strategy → Adapt parameters**. These are **adaptive loops** — the system responds to the market rather than applying static rules.

### 5.2 How Volatility Regime Changes Trigger Strategy Switching

```
MARKET STATE: EURUSD volatility regime shifting
    │
    ▼
STRUCTURE AGENT (Steps 2-4) — src/alphastack/strategy/steps/s02_bias.py
    ├── HMM regime detection:
    │   ├── Previous state: TRENDING_BULL (posterior: 0.82)
    │   ├── Current state: RANGING (posterior: 0.68)
    │   ├── Transition probability: 0.12 (rare → regime change detected)
    │   └── Transition confidence: HIGH (posterior > 0.6)
    │
    ├── ATR regime analysis:
    │   ├── Current ATR(14): 0.0085
    │   ├── 20-day ATR: 0.0052
    │   ├── ATR ratio: 1.63 (current/avg)
    │   └── Classification: HIGH_VOLATILITY (ratio > 1.5)
    │
    └── Regime change event emitted:
        regime_change = {
            "from": "trending_bull",
            "to": "ranging",
            "confidence": 0.68,
            "volatility": "high",
            "trigger": "hmm_state_change"
        }

    ▼
PARAMETER ADAPTATION (across multiple steps):
    │
    ├── Step 8 — RSI Confirmation (src/alphastack/strategy/steps/s08_rsi.py):
    │   ├── Old thresholds (trending): RSI oversold = 40, overbought = 80
    │   ├── New thresholds (ranging): RSI oversold = 30, overbought = 70
    │   └── Reason: In ranging markets, RSI extremes are more meaningful
    │
    ├── Step 11 — Position Sizing (src/alphastack/strategy/steps/s11_sizing.py):
    │   ├── Old multiplier (trending): 1.2
    │   ├── New multiplier (ranging): 0.6
    │   └── Reason: Reduce size in ranging markets (lower edge, higher noise)
    │
    ├── Step 13 — Take Profit (src/alphastack/strategy/steps/s13_take_profit.py):
    │   ├── Old targets (trending): TP1=1.5R, TP2=2.5R, TP3=4.0R
    │   ├── New targets (ranging): TP1=1.0R, TP2=1.5R, TP3=2.0R
    │   └── Reason: Tighter targets in range-bound markets
    │
    └── Step 14 — Trade Management (src/alphastack/strategy/steps/s14_management.py):
        ├── Old trail (trending): ATR × 3.0
        ├── New trail (ranging): ATR × 2.0
        └── Reason: Tighter trailing in ranging markets to capture mean reversion
```

### 5.3 How Correlation Breakdown Adjusts Hedging

```
CORRELATION MONITOR (src/alphastack/risk/correlation.py):
    │
    ├── EURUSD-GBPUSD correlation: typically 0.85
    ├── Current 20-day correlation: 0.45 (breakdown detected)
    │
    ├── IMPACT ASSESSMENT:
    │   ├── If holding both EURUSD long and GBPUSD long:
    │   │   ├── Previously: counted as 1 correlated pair (effective exposure = 1.5x)
    │   │   └── Now: count as 2 independent positions (effective exposure = 2.0x)
    │   │
    │   └── Risk gate adjustment:
    │       ├── Old max correlated positions: 2
    │       ├── Now: these positions are no longer correlated
    │       └── Effect: can open another position in either pair
    │       BUT: total portfolio exposure increases → reduce individual sizes
    │
    └── STRATEGY ADJUSTMENT:
        ├── Hedging strategy: previously hedge EURUSD with GBPUSD
        ├── Now: hedge with USDCHF (which maintains correlation)
        └── Update correlation matrix in Redis (state:correlations)
```

### 5.4 Where in AlphaStack This Helps

| Component | Market Feedback Enhancement |
|-----------|---------------------------|
| `src/alphastack/strategy/steps/s02_bias.py` — `MarketBiasStep` | Already detects regime via HMM. Enhancement: emit `regime_change` event that triggers parameter adaptation across all downstream steps. |
| `src/alphastack/strategy/steps/s08_rsi.py` — `RSIConfirmation` | Has adaptive RSI thresholds. Enhancement: load thresholds from regime-specific config instead of hardcoded values. |
| `src/alphastack/strategy/steps/s13_take_profit.py` — `TakeProfitStep` | TP calculation. Enhancement: use regime-aware TP targets from contextual bandit or management rules lookup. |
| `src/alphastack/strategy/steps/s14_management.py` — `TradeManagementStep` | In-trade management. Enhancement: respond to mid-trade regime changes by adjusting trail distance and partial close levels. |
| `src/alphastack/risk/correlation.py` | Correlation tracking. Enhancement: real-time correlation updates that affect position sizing and hedging decisions. |
| `src/alphastack/strategy/steps/s04_structure.py` — `MarketStructure` | Multi-timeframe structure analysis. Enhancement: detect regime transitions and propagate parameter changes. |

**Key gap identified in review:** The `review_strategy_loops.md` (§4, issue R1) flagged that mid-trade regime transitions are not handled. When the regime shifts while a position is open, the management parameters should adapt. The fix is a regime-change decision matrix in `TradeManagementStep`.

---

# PART 2: HERMES EMERGING PATTERNS

## 1. Skill Creation from Experience

### 1.1 How Hermes Creates Reusable Skills

Hermes has a `/learn` command that turns experience into reusable skills. The pattern:

1. **Trigger:** Agent encounters a novel problem and solves it
2. **Capture:** Agent uses `skill_manage` tool to save the solution as a `SKILL.md` file
3. **Structure:** Skill follows standard format (name, description, when to use, procedure, pitfalls, verification)
4. **Storage:** Saved to `~/.hermes/skills/` directory
5. **Retrieval:** Available via progressive disclosure — Level 0 (name+description, ~3K tokens), Level 1 (full content), Level 2 (specific reference files)
6. **Maintenance:** Curator runs periodically to archive unused skills, consolidate duplicates, and patch drift

Key Hermes principle: **"Progressive disclosure"** — don't load full skill content unless needed. The agent sees skill names and descriptions first, only loads full content when it decides to use a skill.

### 1.2 How to Apply to AlphaStack: Trading Skills from Successful Patterns

```
ALPHASTACK TRADING SKILL CREATION

Trigger: Pattern detected with sufficient statistical backing
    │
    ▼
SKILL EXTRACTION (analogous to Hermes /learn):
    │
    ├── Pattern: "H4 bullish OB at D1 support with RSI divergence in London session"
    ├── Evidence: 15 trades, 12 wins (80%), avg R:R = 1.8
    ├── Conditions: regime=trending_bull, session=london, symbols=[EURUSD, GBPUSD]
    │
    ▼
SKILL OBJECT (analogous to SKILL.md):
    {
        "skill_id": "ob_bounce_london_trend",
        "name": "H4 Order Block Bounce — London Trending",
        "description": "Buy at H4 bullish OB aligned with D1 support during London session in trending bull regime",
        "version": "1.0",
        "when_to_use": {
            "regime": "trending_bull",
            "session": "london",
            "setup": "ob_bounce",
            "requirements": ["h4_ob_detected", "d1_support_aligned", "rsi_divergence"]
        },
        "procedure": {
            "entry": "Limit buy at OB mid-price",
            "stop_loss": "Below OB low + 0.5×ATR buffer",
            "take_profit": "TP1=1.5R, TP2=2.5R, trail=2.5×ATR",
            "position_size": "1.5% risk (standard)"
        },
        "confidence": 0.72,
        "sample_size": 15,
        "win_rate": 0.80,
        "avg_rr": 1.8,
        "last_reinforced": "2026-07-15",
        "pitfalls": [
            "Requires volume confirmation on OB formation candle",
            "Fails in high-impact news proximity (30-min blackout)",
            "Demote to 0.5% risk if regime confidence < 0.7"
        ]
    }

    ▼
STORAGE:
    ├── PostgreSQL `lessons` table (L3) — structured query
    ├── pgvector embedding — semantic search
    └── Progressive disclosure: only load full skill when setup matches

    ▼
RETRIEVAL (next similar setup):
    ├── Pipeline detects H4 bullish OB at D1 support → query lessons
    ├── Semantic search: "H4 OB bounce London trending" → finds this skill
    ├── Load skill → apply procedure with confidence-weighted parameters
    └── Higher confidence → standard size; lower confidence → reduced size
```

### 1.3 Specific Code Integration Points

| File | Integration |
|------|-------------|
| `src/alphastack/strategy/steps/s10_confluence.py` — `ConfluenceEngine` | When computing confluence, query `lessons` table for matching skills. If a matching skill has high confidence (>0.7), boost the confluence score by 5-10 points. |
| `src/alphastack/strategy/steps/s11_sizing.py` — `PositionSizingStep` | When sizing, check if there's a matching trading skill. Use the skill's recommended position size (confidence-weighted). |
| `src/alphastack/strategy/steps/s13_take_profit.py` — `TakeProfitStep` | Use the skill's TP procedure if available. If no skill, fall back to contextual bandit selection. |
| `src/alphastack/agi/memory.py` — `EpisodicMemory.get_lessons()` | Already retrieves lessons. Enhancement: add semantic search over embeddings for fuzzy matching (not just exact symbol/regime/session). |
| `src/alphastack/agents/reflection/agent.py` | Enhancement: when a pattern reaches statistical significance (n≥15, win rate significantly > 50%), automatically create a trading skill. |

---

## 2. Bounded Memory with Forced Prioritization

### 2.1 How Hermes Limits Memory to Force Quality

Hermes has strict character limits on memory:
- `MEMORY.md`: 2,200 chars (~800 tokens) — agent's personal notes
- `USER.md`: 1,375 chars (~500 tokens) — user profile

When memory is full and the agent tries to add an entry, it gets an error:
```json
{
    "success": false,
    "error": "Memory at 2,100/2,200 chars. Adding this entry (250 chars) would exceed the limit.",
    "current_entries": ["..."],
    "usage": "2,100/2,200"
}
```

The agent must then **prioritize**: consolidate overlapping entries, remove stale ones, or compress verbose entries. This forces the agent to keep only the most impactful information.

**Key principle:** "Character limits keep memory focused. Memory does not auto-compact — when a write would exceed the limit, the tool returns an error instead of silently dropping entries."

### 2.2 How to Apply to AlphaStack: Bounded Trade History with Forced Prioritization

```
ALPHASTACK BOUNDED MEMORY MODEL

PROBLEM: After 1,000 trades, the system has:
    ├── 1,000 trade episodes in episodic memory
    ├── 200+ lessons in long-term memory
    ├── 50+ pattern reliability entries
    └── Dozens of management rules

    Without bounds, the system:
    ├── Loads too many past episodes (token waste)
    ├── Retrieves irrelevant lessons (noise)
    ├── Can't distinguish high-quality from low-quality knowledge
    └── Semantic search returns too many mediocre matches

SOLUTION: Apply Hermes-style bounded memory with forced prioritization:

LAYER 1: ACTIVE LESSONS (Bounded: max 50)
    ├── Only lessons with confidence > 0.5 AND sample_size >= 10
    ├── When full: evict lowest-confidence lesson before adding new one
    ├── Consolidation: merge overlapping lessons (e.g., 3 OB lessons → 1 umbrella lesson)
    └── Character limit per lesson: 500 chars (forces concise, actionable rules)

LAYER 2: PATTERN RELIABILITY (Bounded: max 100 cells)
    ├── Only cells with effective_n >= 10 (hierarchical Bayesian)
    ├── When full: evict lowest-confidence cell
    ├── Consolidation: merge same-pattern-different-session cells when sessions have similar win rates
    └── Update frequency: nightly recomputation

LAYER 3: EPISODIC MEMORY (Bounded: max 200 episodes in hot tier)
    ├── Only episodes with |R-multiple| > 0.5 (significant trades)
    ├── When full: evict oldest low-impact episode
    ├── Archive: move evicted episodes to cold storage (ClickHouse with compression)
    └── Semantic search: only searches hot tier (200 episodes) for speed

LAYER 4: MANAGEMENT RULES (Bounded: max 36 cells)
    ├── 3 symbols × 3 regimes × 4 sessions = 36 maximum cells
    ├── When full: recompute, don't add (fixed schema)
    └── Recomputation: weekly offline cron

FORCED PRIORITIZATION (when memory pressure occurs):
    ├── Step 1: Remove lessons with confidence < 0.3 (stale knowledge)
    ├── Step 2: Consolidate lessons in same category (merge 3 entry lessons → 1)
    ├── Step 3: Archive episodes older than 90 days with |R| < 1.0
    ├── Step 4: If still full → alert human: "Memory capacity reached, review knowledge base"
    └── NEVER silently drop entries (Hermes principle)
```

### 2.3 Specific Code Integration Points

| File | Integration |
|------|-------------|
| `src/alphastack/agi/memory.py` — `EpisodicMemory` | Add hard cap on `_short_term` (max 50) and `_long_term` (max 200). Add error-on-full behavior (return error instead of silent eviction). |
| `src/alphastack/agi/memory.py` — `consolidation()` | Enhancement: add quality-based prioritization. Keep episodes with highest |R-multiple| and most lessons. Evict low-impact episodes first. |
| `architecture_memory.md` §5 — `KnowledgeUpdater` | Add memory pressure detection. When lessons table exceeds 50 active entries, trigger consolidation before adding new entries. |
| `architecture_memory.md` §9 — `SemanticSearchService` | Limit search to hot tier (200 episodes). Use structured filters first (PostgreSQL index), then semantic rank on small candidate set. |

---

## 3. Self-Improving Agent Loops

### 3.1 How Hermes Agents Get Better Over Time

Hermes has several self-improvement mechanisms:

1. **Skill creation from experience:** When the agent solves a novel problem, it saves the solution as a reusable skill. Over time, the skill library grows to cover more scenarios.

2. **Memory updates:** The agent proactively saves corrections, conventions, and lessons to MEMORY.md. These persist across sessions and improve future performance.

3. **Curator maintenance:** A background process periodically reviews skills, archives unused ones, consolidates duplicates, and patches drift. This prevents knowledge decay.

4. **Progressive disclosure:** The agent only loads full skill content when needed, keeping context windows efficient. This allows it to have many skills without overwhelming its context.

5. **Self-diagnosis via LSP:** The LSP (Language Server Protocol) integration provides semantic diagnostics — the agent can detect issues in its own output and correct them.

### 3.2 How to Apply to AlphaStack: Trading Agents That Learn from Performance

```
ALPHASTACK SELF-IMPROVING AGENT LOOP

LEVEL 1: PER-TRADE IMPROVEMENT (Immediate)
    │
    ├── Trade closes → Reflection Agent runs
    ├── Computes: which signals were predictive, which weren't
    ├── Updates: signal weights (statistically gated)
    ├── Effect: next trade uses refined weights
    │
    └── Example: SMC agent predicted correctly 12/15 times
        → SMC weight: 0.25 → 0.27 (after significance gate)

LEVEL 2: PER-PATTERN IMPROVEMENT (Weekly)
    │
    ├── Weekly consolidation cron runs
    ├── Recomputes: hierarchical Bayesian pattern reliability
    ├── Recomputes: management rules via offline grid search
    ├── Updates: contextual bandit posterior with week's counterfactuals
    │
    └── Example: H4 OB in trending regime → 80% win rate (n=15)
        → Create trading skill with full procedure

LEVEL 3: PER-REGIME IMPROVEMENT (Monthly)
    │
    ├── Monthly model retraining
    ├── HMM regime model: retrain on last 500 candles
    ├── Regime transition probabilities updated
    ├── Signal weight normalization: rebalance to sum to 1.0
    │
    └── Example: Regime transitions from ranging to trending detected faster
        → HMM retraining reduced detection lag from 5 candles to 2

LEVEL 4: META-IMPROVEMENT (Quarterly)
    │
    ├── Review: is the learning loop itself effective?
    ├── Metrics: has win rate improved over last 100 trades vs first 100?
    ├── Metrics: has the bandit converged? (action confidence > 0.8)
    ├── Metrics: are pattern reliability estimates stable? (CI width < 0.20)
    │
    └── Adjustments:
        ├── If learning loop not effective → review drift detection sensitivity
        ├── If bandit not converging → increase exploration (wider v_squared)
        ├── If patterns unstable → increase minimum sample threshold
        └── Document meta-lessons in MEMORY.md equivalent
```

### 3.3 Specific Code Integration Points

| File | Integration |
|------|-------------|
| `src/alphastack/agents/reflection/agent.py` | The core self-improvement engine. Currently only generates text recommendations. Enhancement: add structured parameter updates that flow to persistent storage. |
| `src/alphastack/agents/base.py` — `AlphaStackAgent.react_loop()` | The ReAct loop. Enhancement: add self-evaluation step — after generating output, critique it against known lessons before finalizing. |
| `src/alphastack/agi/reasoning.py` — `ChainOfThoughtEngine` | Enhancement: add memory-augmented reasoning — before concluding, check if any lessons contradict the conclusion. |
| `src/alphastack/strategy/pipeline.py` — `AlphaStackPipeline` | Enhancement: add `on_step` callback that checks lessons before each step executes. |
| `architecture_memory.md` §5 — `MemoryAugmentedPipeline` | The primary integration point. This is where self-improvement manifests: each pipeline run benefits from accumulated knowledge. |

---

## 4. Mixture of Experts

### 4.1 How Hermes Routes to Specialized Sub-Agents

Hermes' MoA (Mixture of Agents) pattern:

1. **Multiple reference models** analyze the same problem independently (e.g., GPT-5.5 + DeepSeek V4 Pro)
2. **An aggregator model** receives all reference outputs and synthesizes the final answer
3. **The aggregator has tool access** — it can call tools, execute code, etc.
4. **Reference models are cheap/fast** — they don't have tool access, just analysis
5. **The aggregator is high-quality** — it synthesizes perspectives into a coherent response

Key insight: "MoA beats its strongest component by ~6 points" — aggregating multiple perspectives lifts quality on hard tasks.

Configuration:
```yaml
moa:
  presets:
    default:
      reference_models:
        - provider: openai-codex
          model: gpt-5.5
        - provider: openrouter
          model: deepseek/deepseek-v4-pro
      aggregator:
        provider: openrouter
        model: anthropic/claude-opus-4.8
```

### 4.2 How to Apply to AlphaStack: Route to Different Strategies by Market Regime

```
ALPHASTACK MIXTURE OF STRATEGIES

CURRENT: Single pipeline for all market conditions
    ├── Same 16 steps regardless of regime
    ├── Same signal weights regardless of regime
    └── Same management rules regardless of regime

PROBLEM: Trending and ranging markets require fundamentally different approaches
    ├── Trending: momentum signals are predictive, mean-reversion fails
    ├── Ranging: mean-reversion is predictive, momentum fails
    └── One pipeline can't optimize for both simultaneously

SOLUTION: Regime-Routed Mixture of Strategies

┌─────────────────────────────────────────────────────────┐
│                  ORCHESTRATOR AGENT                       │
│          (Regime detection → Strategy routing)            │
└───────┬──────────────┬──────────────┬──────────────┬────┘
        │              │              │              │
  ┌─────▼─────┐  ┌─────▼─────┐  ┌─────▼─────┐  ┌───▼──────┐
  │ TRENDING  │  │  RANGING  │  │ VOLATILE  │  │TRANSITION│
  │ STRATEGY  │  │ STRATEGY  │  │ STRATEGY  │  │ STRATEGY │
  │           │  │           │  │           │  │          │
  │ Agents:   │  │ Agents:   │  │ Agents:   │  │ Agents:  │
  │ • SMC     │  │ • S/R     │  │ • News    │  │ • Light  │
  │ • Momentum│  │ • RSI     │  │ • Liquid. │  │   weight │
  │ • Struct. │  │ • Candle. │  │ • Struct. │  │ • All    │
  │           │  │           │  │           │  │  signals │
  │ Weights:  │  │ Weights:  │  │ Weights:  │  │ Weights: │
  │ SMC: 0.30 │  │ SR: 0.30  │  │ News: 0.25│  │ Equal   │
  │ Mom: 0.25 │  │ RSI: 0.25 │  │ Liq: 0.25 │  │ 0.125   │
  │ Str: 0.20 │  │ Can: 0.20 │  │ Str: 0.20 │  │ each    │
  │ Liq: 0.15 │  │ SMC: 0.15 │  │ SMC: 0.15 │  │          │
  │ Can: 0.10 │  │ Mom: 0.10 │  │ Mom: 0.15 │  │          │
  │           │  │           │  │           │  │          │
  │ TP: Wide  │  │ TP: Tight │  │ TP: Very  │  │ TP:      │
  │ Trail: 3× │  │ Trail: 2× │  │  tight    │  │ Moderate │
  │ ATR       │  │ ATR       │  │ Trail:1.5×│  │ 2.5×ATR  │
  │           │  │           │  │ ATR       │  │          │
  │ Size: 1.2×│  │ Size: 0.6×│  │ Size: 0.4×│  │ Size:    │
  │ base      │  │ base      │  │ base      │  │ 0.8×base │
  └───────────┘  └───────────┘  └───────────┘  └──────────┘
```

### 4.3 Implementation: Regime-Based Agent Routing

```python
class RegimeRouter:
    """
    Routes to specialized strategy configurations based on market regime.
    Analogous to Hermes MoA presets — different "expert" configurations
    for different market conditions.
    """

    REGIME_CONFIGS = {
        "trending_bull": {
            "signal_weights": {
                "smc": 0.30, "momentum": 0.25, "structure": 0.20,
                "liquidity": 0.15, "candlestick": 0.10
            },
            "tp_strategy": "aggressive",  # bandit action index 2
            "position_multiplier": 1.2,
            "trail_atr_mult": 3.0,
            "rsi_thresholds": {"oversold": 40, "overbought": 80},
            "preferred_setups": ["bos_continuation", "ob_bounce"],
        },
        "trending_bear": {
            "signal_weights": {
                "smc": 0.30, "momentum": 0.25, "structure": 0.20,
                "liquidity": 0.15, "candlestick": 0.10
            },
            "tp_strategy": "aggressive",
            "position_multiplier": 1.0,
            "trail_atr_mult": 3.0,
            "rsi_thresholds": {"oversold": 20, "overbought": 60},
            "preferred_setups": ["bos_continuation", "fvg_fill"],
        },
        "ranging": {
            "signal_weights": {
                "sr_level": 0.30, "rsi": 0.25, "candlestick": 0.20,
                "smc": 0.15, "momentum": 0.10
            },
            "tp_strategy": "conservative",  # bandit action index 0
            "position_multiplier": 0.6,
            "trail_atr_mult": 2.0,
            "rsi_thresholds": {"oversold": 30, "overbought": 70},
            "preferred_setups": ["sr_bounce", "range_fade"],
        },
        "volatile": {
            "signal_weights": {
                "news": 0.25, "liquidity": 0.25, "structure": 0.20,
                "smc": 0.15, "momentum": 0.15
            },
            "tp_strategy": "balanced",  # bandit action index 1
            "position_multiplier": 0.4,
            "trail_atr_mult": 1.5,
            "rsi_thresholds": {"oversold": 25, "overbought": 75},
            "preferred_setups": ["liquidity_sweep", "news_reaction"],
        },
    }

    def get_config(self, regime: str, regime_confidence: float) -> dict:
        """Get strategy configuration for current regime."""
        config = self.REGIME_CONFIGS.get(regime, self.REGIME_CONFIGS["ranging"])

        # Scale position multiplier by regime confidence
        if regime_confidence < 0.7:
            config = {**config, "position_multiplier": config["position_multiplier"] * 0.7}

        return config
```

### 4.4 Specific Code Integration Points

| File | Integration |
|------|-------------|
| `src/alphastack/agents/orchestrator/graph.py` — `AlphaStackOrchestrator` | Enhancement: after `news` node, add regime detection node that determines strategy routing. Pass regime config to `strategy` node. |
| `src/alphastack/strategy/steps/s02_bias.py` — `MarketBiasStep` | Enhancement: output regime config (weights, thresholds, preferred setups) alongside bias. |
| `src/alphastack/strategy/steps/s10_confluence.py` — `ConfluenceEngine` | Enhancement: load signal weights from regime config instead of hardcoded values. |
| `src/alphastack/strategy/steps/s08_rsi.py` — `RSIConfirmation` | Enhancement: load RSI thresholds from regime config. |
| `src/alphastack/strategy/steps/s13_take_profit.py` — `TakeProfitStep` | Enhancement: use regime-specific TP strategy (conservative/balanced/aggressive). |
| `src/alphastack/strategy/context.py` — `AlphaStackContext` | Enhancement: add `regime_config` field that carries the full regime-specific configuration. |

---

## 5. Recursive Self-Improvement

### 5.1 How Hermes Improves Its Own Improvement Process

Hermes has several meta-improvement mechanisms:

1. **Curator (meta-maintenance):** A background process that reviews the agent's skill library. It doesn't just maintain skills — it evaluates whether the skill creation process itself is producing quality skills. If skills are frequently unused or overlapping, the curator signals that the `/learn` process needs refinement.

2. **Memory character limits (meta-constraint):** By forcing the agent to fit knowledge into 2,200 chars, Hermes forces the agent to learn **how to distill** — not just what to remember. The constraint improves the quality of what gets remembered.

3. **Progressive disclosure (meta-efficiency):** By only loading skill content when needed, the agent learns to be efficient with context. This meta-pattern improves how the agent manages its own resources.

4. **Self-diagnosis via LSP (meta-evaluation):** The agent can evaluate its own output quality through semantic diagnostics. This is meta-improvement — the agent improves its ability to detect its own mistakes.

### 5.2 How to Apply to AlphaStack: Meta-Learning — Learning How to Learn from Trades

```
ALPHASTACK RECURSIVE SELF-IMPROVEMENT

LEVEL 0: TRADE → LESSON (Basic learning)
    └── "H4 OB bounce worked in London session" → store lesson

LEVEL 1: LEARNING PROCESS → EVALUATION (Meta-learning)
    ├── Evaluate: is the learning process producing useful lessons?
    │
    ├── Metric 1: Lesson Utilization Rate
    │   ├── How many stored lessons were actually retrieved and applied?
    │   ├── If < 30% → lessons are too specific or not retrievable
    │   └── Fix: improve semantic embeddings, consolidate overlapping lessons
    │
    ├── Metric 2: Lesson Accuracy
    │   ├── Of lessons applied, how often were they correct?
    │   ├── If < 60% → lessons are not predictive
    │   └── Fix: increase minimum sample size, tighten significance threshold
    │
    ├── Metric 3: Learning Rate
    │   ├── How quickly does the system improve?
    │   ├── Measure: rolling 100-trade win rate trend
    │   ├── If flat → learning loop is not effective
    │   └── Fix: check drift detection, review attribution accuracy
    │
    └── Metric 4: Knowledge Base Quality
        ├── Average lesson confidence (should increase over time)
        ├── Average pattern reliability CI width (should decrease over time)
        ├── Number of contradictions (should decrease over time)
        └── If degrading → concept drift not being detected

LEVEL 2: META-PARAMETER TUNING (Recursive improvement)
    │
    ├── The system adjusts its own learning parameters:
    │
    ├── Significance threshold (currently α = 0.10):
    │   ├── If too many false positives → tighten to α = 0.05
    │   ├── If too few adjustments → relax to α = 0.15
    │   └── Meta-rule: adjust α based on false discovery rate
    │
    ├── Minimum sample size (currently 20):
    │   ├── If pattern reliability unstable → increase to 30
    │   ├── If learning too slow → decrease to 15
    │   └── Meta-rule: adjust based on CI width of recent patterns
    │
    ├── Drift detection sensitivity (currently λ = 50):
    │   ├── If too many false alarms → increase λ to 80
    │   ├── If drift detected too late → decrease λ to 30
    │   └── Meta-rule: adjust based on false positive rate of drift alerts
    │
    ├── Memory bounds (currently 50 lessons, 200 episodes):
    │   ├── If retrieval quality high → can increase bounds
    │   ├── If retrieval quality low → decrease bounds (force more curation)
    │   └── Meta-rule: adjust based on retrieval precision
    │
    └── Contextual bandit exploration (currently v² = 1.0):
        ├── If bandit converged (all action confidences > 0.8) → decrease to 0.5
        ├── If bandit not converging after 200 trades → increase to 2.0
        └── Meta-rule: adjust based on action confidence variance

LEVEL 3: ARCHITECTURE IMPROVEMENT (Meta-meta)
    │
    ├── Quarterly review: is the overall loop architecture effective?
    │
    ├── Questions:
    │   ├── Are the right agents handling the right signals?
    │   │   → Review: agent interaction synergy scores
    │   │
    │   ├── Is the confluence scoring formula optimal?
    │   │   → Review: correlation between confluence score and R-multiple
    │   │
    │   ├── Is the pipeline order correct?
    │   │   → Review: would parallel signal detection improve latency?
    │   │
    │   └── Are there missing signals?
    │       → Review: trades that lost despite high confluence → what was missing?
    │
    └── Output: architecture change proposals (require human approval)
```

### 5.3 Specific Code Integration Points

| File | Integration |
|------|-------------|
| `architecture_memory.md` §5 — Learning Loop Engine | Enhancement: add meta-metrics tracking (lesson utilization, learning rate, knowledge quality). Store in `meta_metrics` table. |
| `architecture_memory.md` §5.2 — Drift Detection | Enhancement: self-tune drift detection parameters based on false positive/negative rates. |
| `fix_learning_loops.md` §4 — Statistical Significance | Enhancement: self-tune significance threshold based on observed false discovery rate. |
| `fix_learning_loops.md` §1 — Contextual Bandit | Enhancement: self-tune exploration parameter (v²) based on convergence rate. |
| `src/alphastack/agents/reflection/agent.py` | Enhancement: add meta-evaluation step — after computing adjustments, evaluate whether past adjustments actually improved performance. |
| New file: `src/alphastack/agi/meta_learning.py` | New module: Meta-learning engine that tracks learning loop effectiveness and tunes meta-parameters. |

---

# PART 3: PROBLEM-SOLUTION MAP

## Loop Systems Problem-Solution Matrix

| Loop Type | AlphaStack Problem | Where It Applies | Solution | Impact | Risk |
|-----------|-------------------|------------------|----------|--------|------|
| **Feedback** | Trade outcomes don't influence next trade parameters | `ReflectionAgent` → `pipeline.py` (broken link) | Wire reflection output to persistent stores that pipeline reads | Better signal weights, improved position sizing | Over-fitting to recent trades; mitigate with statistical gates |
| **Feedback** | Price movements don't dynamically adjust signal confidence | `LiquidityAgent` → `ConfluenceEngine` | Real-time confidence scoring based on price proximity to key levels | More responsive entry signals | Latency increase from real-time scoring; batch updates to 1s intervals |
| **Learning** | No mechanism to improve from experience | `EpisodicMemory` → all pipeline steps | Implement 6-stage learning loop (reflect → extract → update → store → apply → compound) | System compounds edge over time; each trade makes next one better | Cold-start problem (first 50 trades have no learned knowledge); mitigate with informative priors |
| **Learning** | Patterns not tracked by actual reliability | `SmartMoneyConcepts`, `CandlestickConfirmation` | Hierarchical Bayesian pattern reliability with shrinkage | Accurate win rate estimates even with few observations | Over-smoothing can hide genuine pattern differences; monitor shrinkage weights |
| **Correction** | Same mistakes repeated across trades | `ReflectionAgent` → lessons table → pipeline | Structured Lesson objects with conditions + actions | Avoid repeating known failure modes | Lessons can become stale; decay engine handles this |
| **Correction** | No counterfactual analysis | `TradeManagementStep` | Shadow tracking: simulate 5 alternative management strategies per trade | Learn optimal management from "what would have happened" | Computational cost of simulation; batch overnight |
| **Risk** | Drawdown doesn't reduce position size | `RiskGovernor` → `PositionSizingStep` | Drawdown-based position multiplier (graduated response) | Smaller losses during drawdowns, faster recovery | Over-conservatism after drawdown; hysteresis prevents oscillation |
| **Risk** | Winning streaks don't cautiously increase exposure | `ReflectionAgent` → signal weights | Statistically gated position size increase with hysteresis | Cautious scaling during genuine hot streaks | Over-confidence from small samples; Bonferroni correction mitigates |
| **Market** | Regime changes don't trigger parameter adaptation | `MarketBiasStep` → all downstream steps | Regime-based parameter routing (RSI thresholds, TP targets, position multipliers) | Strategy adapts to market conditions | Regime detection lag (2-5 candles); acceptable for non-scalping |
| **Market** | Correlation breakdown not detected | `correlation.py` → risk gate | Real-time correlation monitoring with hedging adjustment | Prevents over-concentration in correlated positions | Correlation estimation noisy with small windows; use 20-day minimum |

## Hermes Patterns Problem-Solution Map

| Pattern | AlphaStack Problem | Where It Applies | Solution | Impact | Risk |
|---------|-------------------|------------------|----------|--------|------|
| **Skill Creation** | Successful patterns not encoded as reusable rules | `ReflectionAgent` → lessons table → pipeline | Auto-create trading skills when patterns reach statistical significance | Patterns become actionable rules that persist and compound | Skill proliferation; curator/archiver prevents bloat |
| **Skill Creation** | Lessons are text strings, not machine-readable | `_extract_learnings()` in ReflectionAgent | Structured Lesson objects with conditions, actions, confidence, evidence | Pipeline can programmatically evaluate and apply lessons | Over-specification can make lessons brittle; keep conditions general |
| **Bounded Memory** | Unbounded trade history creates noise | `EpisodicMemory`, lessons table | Hard caps on active lessons (50), episodes (200), patterns (100) | Forces quality; most impactful knowledge surfaces first | Cap too low → loses useful knowledge; cap too high → noise; tune empirically |
| **Bounded Memory** | No forced prioritization when memory full | `EpisodicMemory.consolidation()` | Error-on-full with consolidation guidance (like Hermes MEMORY.md) | Agent must curate knowledge, not just accumulate | Requires consolidation logic; start simple (confidence-based eviction) |
| **Self-Improvement** | Agents don't improve from their own performance | All agents, especially `ReflectionAgent` | 4-level improvement loop (per-trade → per-pattern → per-regime → meta) | System compounds improvement at multiple timescales | Over-engineering; implement Level 1 first, add levels as data accumulates |
| **Self-Improvement** | No evaluation of learning loop effectiveness | Meta-learning layer | Track lesson utilization rate, learning rate, knowledge quality metrics | Detect when learning loop is broken before performance degrades | Meta-metrics add complexity; implement after Level 1 learning works |
| **Mixture of Experts** | Same pipeline for all market regimes | Orchestrator → strategy routing | Regime-specific signal weights, TP strategies, position multipliers | Right strategy for right market condition | Regime detection errors → wrong strategy; reduce position size when confidence low |
| **Mixture of Experts** | Single model for all analysis tasks | Agent architecture | Use fast models for time-critical decisions, slow models for research | Better latency/quality tradeoff | Model switching adds complexity; start with 2 tiers |
| **Recursive Self-Improvement** | Learning parameters are static | All learning loop components | Self-tune significance threshold, sample size, drift sensitivity | System adapts its own learning rate to data characteristics | Meta-parameter tuning can oscillate; use hysteresis and slow adaptation rates |
| **Recursive Self-Improvement** | No architecture-level self-evaluation | Quarterly review process | Track agent synergy scores, confluence-R correlation, pipeline latency | Identify architectural improvements before they become critical | Over-optimization risk; require human approval for architecture changes |

## Priority Implementation Order

### Phase 1: Foundation Loops (Weeks 1-4) — "Make It Learn"

| Priority | Pattern | Implementation | Effort | Impact |
|----------|---------|---------------|--------|--------|
| **P0** | Feedback Loop (broken link) | Wire `ReflectionAgent` output to PostgreSQL `signal_weights` table; pipeline reads at Step 10 | 2 days | **CRITICAL** — Without this, the system cannot learn from experience |
| **P0** | Learning Loop (basic) | Implement structured `Lesson` objects in ReflectionAgent; store in PostgreSQL | 3 days | **CRITICAL** — Enables all downstream learning |
| **P1** | Correction Loop (basic) | Add lesson retrieval in `ConfluenceEngine`; check for known failure modes | 2 days | **HIGH** — Prevents repeating known mistakes |
| **P1** | Risk Feedback (drawdown) | Add drawdown-based position multiplier in `PositionSizingStep` | 1 day | **HIGH** — Prevents catastrophic drawdowns |

### Phase 2: Adaptive Loops (Weeks 5-8) — "Make It Smart"

| Priority | Pattern | Implementation | Effort | Impact |
|----------|---------|---------------|--------|--------|
| **P2** | Market Feedback (regime routing) | Implement `RegimeRouter` with regime-specific configs | 3 days | **HIGH** — Right strategy for right market |
| **P2** | Mixture of Experts (regime weights) | Load signal weights from regime config instead of hardcoded values | 2 days | **HIGH** — Significant edge improvement |
| **P2** | Bounded Memory | Add hard caps to `EpisodicMemory` and lessons table; error-on-full | 2 days | **MEDIUM** — Prevents knowledge bloat |
| **P2** | Skill Creation | Auto-create trading skills when patterns reach significance | 3 days | **MEDIUM** — Compounds pattern knowledge |

### Phase 3: Meta-Improvement (Weeks 9-12) — "Make It Wise"

| Priority | Pattern | Implementation | Effort | Impact |
|----------|---------|---------------|--------|--------|
| **P3** | Self-Improvement (Level 2) | Track learning loop metrics; add weekly evaluation | 3 days | **MEDIUM** — Detects learning failures |
| **P3** | Recursive Self-Improvement | Self-tune significance threshold and drift sensitivity | 2 days | **MEDIUM** — Adapts learning rate to data |
| **P3** | Correction Loop (counterfactuals) | Implement shadow tracking for management strategies | 5 days | **MEDIUM** — Optimal management from "what if" analysis |
| **P3** | Risk Feedback (winning streaks) | Statistically gated exposure increase with hysteresis | 2 days | **LOW** — Cautious scaling, modest impact |

---

# APPENDIX: References

## AlphaStack Internal Documents
- `ANALYSIS_ARCHITECTURE.md` — Full system architecture review
- `architecture/architecture_multi_agent.md` — Multi-agent system design (16 agents, 5 loop types)
- `architecture/architecture_memory.md` — 4-layer memory architecture with Hermes-inspired learning loop
- `research/tech/research_03_loop_multiagent_systems.md` — Loop systems and multi-agent research
- `reviews/review_strategy_loops.md` — Strategy and loop system review (3 CRITICAL, 5 HIGH issues)
- `fixes/fix_learning_loops.md` — 6 critical fixes for learning loops (bandits, drift, hierarchy, significance, counterfactuals, attribution)
- `src/alphastack/agi/memory.py` — Episodic memory implementation
- `src/alphastack/agi/planning.py` — Trade planning with scenario analysis
- `src/alphastack/agi/reasoning.py` — Chain-of-thought reasoning engine
- `src/alphastack/agents/reflection/agent.py` — Reflection agent (post-trade analysis)
- `src/alphastack/agents/base.py` — Base agent with ReAct loop and memory
- `src/alphastack/agents/orchestrator/graph.py` — LangGraph orchestrator (5 agents)
- `src/alphastack/strategy/pipeline.py` — 16-step strategy pipeline
- `src/alphastack/risk/governor.py` — Risk governor
- `src/alphastack/risk/position_sizer.py` — Position sizer

## External Sources
- Hermes Agent Documentation — https://hermes-agent.nousresearch.com/docs/
  - Skills System: `/docs/user-guide/features/skills` — Progressive disclosure, `/learn`, SKILL.md format
  - Persistent Memory: `/docs/user-guide/features/memory` — Bounded memory (2,200 chars), forced prioritization
  - Mixture of Agents: `/docs/user-guide/features/mixture-of-agents` — Reference models + aggregator pattern
  - Curator: `/docs/user-guide/features/curator` — Background skill maintenance, archival, consolidation
- Anthropic. "Building Effective Agents." Dec 2024. https://www.anthropic.com/engineering/building-effective-agents
- Yao et al. "ReAct: Synergizing Reasoning and Acting in Language Models." ICLR 2023.
- LangGraph Documentation. https://docs.langchain.com/oss/python/langgraph/overview

---

*Document generated: 2026-07-16*  
*Author: Loop Systems & Hermes Emerging Patterns Research Agent*  
*Status: Research Complete*  
*Next: Integrate findings into architecture_memory.md and architecture_multi_agent.md*
