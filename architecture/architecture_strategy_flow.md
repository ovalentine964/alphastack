# Alpha Stack — Strategy Flow Architecture
## Complete 16-Step Data Flow: Market Data → Signal → Execution → Journal

**Date:** 2026-07-11
**Version:** 1.0
**Status:** Architecture Design — Ready for Review

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Master Data Flow Diagram](#2-master-data-flow-diagram)
3. [Phase-by-Phase Flow Detail](#3-phase-by-phase-flow-detail)
4. [Step-by-Step Data Contracts](#4-step-by-step-data-contracts)
5. [Parallel vs Sequential Execution Map](#5-parallel-vs-sequential-execution-map)
6. [Human-in-the-Loop Checkpoints](#6-human-in-the-loop-checkpoints)
7. [Risk Gate Architecture](#7-risk-gate-architecture)
8. [Error Handling at Each Step](#8-error-handling-at-each-step)
9. [Loop System Improvement Map](#9-loop-system-improvement-map)
10. [Performance Requirements & Latency Budget](#10-performance-requirements--latency-budget)
11. [Signal-to-Execution Timing Diagram](#11-signal-to-execution-timing-diagram)
12. [Appendix: Agent-Step Mapping](#12-appendix-agent-step-mapping)

---

## 1. Executive Summary

The Alpha Strategy is a 16-step pipeline that transforms raw market data into executed trades and continuously improving intelligence. The flow operates in **6 phases**, with parallel execution where possible and strict sequential gates where safety demands it.

**Core Flow:**
```
Market Data → Context (Steps 1-4) → Signals (Steps 5-9) → Decision (Steps 10-12)
→ Execution → Management (Steps 13-15) → Learning (Step 16) → [Loop back to improve Steps 1-15]
```

**Key Design Principles:**
- **Parallel where possible, sequential where necessary** — Steps 5-9 run in parallel; Steps 10-12 are strictly sequential
- **Risk is infrastructure-level** — The Risk Gate (Step 12) is enforced in code, not by LLM prompts
- **Every trade is auditable** — Full reasoning chain from signal to execution to review
- **Self-improving** — Step 16 feeds back into every prior step via the closed learning loop
- **Latency-budgeted** — Each step has a hard latency limit; total signal-to-execution target: < 5 seconds for high-conviction setups

---

## 2. Master Data Flow Diagram

```
                                    ┌─────────────────────────────────────────┐
                                    │           EXTERNAL DATA SOURCES          │
                                    │                                         │
                                    │  MT5 API  Finnhub  RSS Feeds  CCXT     │
                                    │  ForexFactory  Central Banks  On-Chain  │
                                    │  Order Book  Dark Pool  COT Reports     │
                                    └──────────┬──────────────────────────────┘
                                               │
                                               ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          PHASE 1: CONTEXT BUILDING                              │
│                          (Steps 1-4, ~2-5 seconds)                              │
│                                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   STEP 1     │    │   STEP 2     │    │   STEP 3     │    │   STEP 4     │  │
│  │ Fundamental  │───▶│ Market Bias  │───▶│   Session    │───▶│   Market     │  │
│  │ Intelligence │    │              │    │   Analysis   │    │  Structure   │  │
│  └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘  │
│       │                    ▲                   │                   │            │
│       │                    │                   │                   │            │
│       │                    └───────────────────┴───────────────────┘            │
│       │                     (Steps 2-4 share data bidirectionally)              │
│       │                                                                        │
│  Outputs: fundamental_bias, market_regime, session_state, structure_map         │
└───────────────────────────────────────────┬─────────────────────────────────────┘
                                            │
                                            ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          PHASE 2: SIGNAL DETECTION                              │
│                          (Steps 5-9, PARALLEL, ~1-3 seconds)                    │
│                                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │  STEP 5  │  │  STEP 6  │  │  STEP 7  │  │  STEP 8  │  │  STEP 9  │        │
│  │   S/R    │  │Liquidity │  │   SMC    │  │   RSI    │  │Candle-   │        │
│  │Detection │  │Detection │  │ Patterns │  │ Momentum │  │ stick    │        │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘        │
│       │              │              │              │              │              │
│       └──────────────┴──────────────┴──────────────┴──────────────┘              │
│                              │                                                  │
│                              ▼                                                  │
│                   ┌─────────────────────┐                                       │
│                   │  CONFLUENCE SCORER  │                                       │
│                   │  (Signal Aggregator) │                                      │
│                   └──────────┬──────────┘                                       │
│                              │                                                  │
│  Outputs: confluence_score (0-100), trade_proposal, signal_breakdown            │
└───────────────────────────────────────────┬─────────────────────────────────────┘
                                            │
                              ┌──────────────┴──────────────┐
                              │                             │
                         Score < 40                   Score ≥ 40
                         NO TRADE                    CONTINUE
                         (log & stop)                     │
                                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          PHASE 3: TRADE DECISION                                │
│                          (Steps 10-12, SEQUENTIAL, ~1-2 seconds)                │
│                                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────────────────┐  │
│  │   STEP 10    │    │   STEP 11    │    │           STEP 12               │  │
│  │   Trade      │───▶│  Position    │───▶│          RISK GATE              │  │
│  │   Entry      │    │   Sizing     │    │  (Stop Loss + Risk Validation)  │  │
│  └──────────────┘    └──────────────┘    └──────────────┬───────────────────┘  │
│                                                         │                      │
│                                                   ┌─────┴─────┐                │
│                                                   │           │                │
│                                               REJECTED    APPROVED             │
│                                               (log &      (continue)           │
│                                                stop)          │                │
│                                                                │                │
│  Outputs: entry_order (type, price, size, SL, TP levels)       │               │
└───────────────────────────────────────────────────────────────┬─┘───────────────┘
                                                                │
                                                    ┌───────────┴───────────┐
                                                    │    HITL CHECKPOINT    │
                                                    │  (if risk > threshold)│
                                                    └───────────┬───────────┘
                                                                │
                                                                ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          PHASE 4: EXECUTION                                     │
│                          (~100ms - 1 second)                                    │
│                                                                                 │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │                        EXECUTION AGENT                                    │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │  │
│  │  │  Validate   │  │   Submit    │  │   Confirm   │  │    Set      │    │  │
│  │  │  Proposal   │──▶│   Order    │──▶│    Fill     │──▶│  SL/TP     │    │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘    │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
│  Outputs: fill_price, slippage, order_id, execution_time_ms                     │
└───────────────────────────────────────────┬─────────────────────────────────────┘
                                            │
                                            ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          PHASE 5: TRADE MANAGEMENT                              │
│                          (Steps 13-15, CONTINUOUS while position open)          │
│                                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                      │
│  │   STEP 13    │    │   STEP 14    │    │   STEP 15    │                      │
│  │   Take       │◄──▶│    Trade     │◄──▶│    Exit      │                      │
│  │   Profit     │    │  Management  │    │  Conditions  │                      │
│  └──────────────┘    └──────────────┘    └──────────────┘                      │
│       │                    │                    │                                │
│       └────────────────────┴────────────────────┘                               │
│                    (Continuous monitoring loop)                                  │
│                                                                                 │
│  Outputs: partial_closes, sl_adjustments, final_exit                            │
└───────────────────────────────────────────┬─────────────────────────────────────┘
                                            │
                                            ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          PHASE 6: LEARNING                                      │
│                          (Step 16, POST-TRADE + PERIODIC)                       │
│                                                                                 │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │                          STEP 16                                          │  │
│  │                    JOURNAL & LEARNING                                     │  │
│  │                                                                          │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │  │
│  │  │   Record    │  │   Analyze   │  │  Extract    │  │   Update    │    │  │
│  │  │   Trade     │──▶│   Outcome   │──▶│  Lessons    │──▶│  Strategy   │    │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘    │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                              │                                                  │
│                              ▼                                                  │
│                    ┌─────────────────────┐                                      │
│                    │   FEEDBACK LOOP     │                                      │
│                    │  → Adjust weights   │                                      │
│                    │  → Update thresholds│                                      │
│                    │  → Retrain models   │                                      │
│                    │  → Update playbook  │                                      │
│                    └─────────────────────┘                                      │
│                              │                                                  │
│                              └──────────────────────────────────────────────────│
│                              LOOP BACK to improve Steps 1-15                    │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Phase-by-Phase Flow Detail

### PHASE 1: Context Building (Steps 1-4)

**Purpose:** Establish the macro and technical context before looking for signals.

**Execution Order:** Steps 1 and 4 start in parallel; Step 2 requires both; Step 3 requires Step 2.

```
                    ┌──────────────┐
                    │  STEP 1      │ (parallel start)
                    │  Fundamental │
                    │  Intelligence│
                    └──────┬───────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
         ▼                 │                 ▼
  fundamental_bias         │          ┌──────────────┐
  sentiment_score          │          │  STEP 4      │ (parallel start)
  event_risk_score         │          │  Market      │
  volatility_forecast      │          │  Structure   │
         │                 │          └──────┬───────┘
         │                 │                 │
         │                 │          structure_map
         │                 │          key_levels
         │                 │          trend_direction
         │                 │                 │
         └────────┬────────┴────────┬────────┘
                  │                 │
                  ▼                 │
           ┌──────────────┐        │
           │  STEP 2      │        │
           │  Market Bias │        │
           │  (Fusion)    │        │
           └──────┬───────┘        │
                  │                │
           market_bias             │
           regime                  │
           confidence              │
                  │                │
                  ▼                │
           ┌──────────────┐        │
           │  STEP 3      │        │
           │  Session     │        │
           │  Analysis    │        │
           └──────┬───────┘        │
                  │                │
           session_state           │
           asian_range             │
           session_params          │
                  │                │
                  └────────┬───────┘
                           │
                           ▼
                    PHASE 2 TRIGGER
```

**Data Contracts:**

| Step | Receives | Produces | Latency Budget |
|------|----------|----------|---------------|
| Step 1 | News feeds, calendar, sentiment sources | `fundamental_bias`, `event_risk_score`, `volatility_forecast` | 2-5s (parallel with Step 4) |
| Step 2 | Step 1 output + Step 4 output | `market_bias`, `regime`, `regime_confidence`, `conflict_flag` | 500ms |
| Step 3 | Step 2 output + session clock | `current_session`, `session_volatility_state`, `asian_range`, `session_parameters` | 100ms |
| Step 4 | Multi-TF OHLCV data | `structure_map`, `key_levels`, `chop_score`, `multi_tf_alignment`, `trade_direction` | 1-3s (parallel with Step 1) |

---

### PHASE 2: Signal Detection (Steps 5-9) — PARALLEL

**Purpose:** All five signal agents run simultaneously, each looking for their specific setup type.

```
  Phase 1 Output (bias + regime + session + structure)
         │
         ├──────────────┬──────────────┬──────────────┬──────────────┐
         │              │              │              │              │
         ▼              ▼              ▼              ▼              ▼
   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
   │  STEP 5  │  │  STEP 6  │  │  STEP 7  │  │  STEP 8  │  │  STEP 9  │
   │   S/R    │  │Liquidity │  │   SMC    │  │   RSI    │  │Candle-   │
   │Detection │  │Detection │  │ Patterns │  │Confirm.  │  │ stick    │
   └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘
        │              │              │              │              │
        │  sr_levels   │  liquidity   │  ob_list     │  rsi_values  │  patterns
        │  sr_scores   │  _map        │  fvg_list    │  composite   │  pattern_
        │  flip_status │  sweep_      │  confluence  │  _momentum   │  score
        │              │  signals     │  _score      │  divergences │  failure
        │              │  order_flow  │  bos_choch   │  confirmation│  _flags
        │              │  _score      │              │              │
        └──────────────┴──────────────┴──────────────┴──────────────┘
                                     │
                                     ▼
                        ┌────────────────────────┐
                        │    CONFLUENCE SCORER   │
                        │    (Signal Aggregator)  │
                        │                        │
                        │  Score = Σ(weight ×    │
                        │    signal_quality ×     │
                        │    tf_alignment)        │
                        │                        │
                        │  + Confluence bonuses   │
                        └───────────┬────────────┘
                                    │
                              ┌─────┴─────┐
                              │           │
                         Score < 40  Score ≥ 40
                         LOG & STOP  GENERATE
                                     TRADE
                                     PROPOSAL
```

**Parallel Execution Details:**

| Step | Agent | Input Dependencies | Can Start When | Loop Type |
|------|-------|-------------------|----------------|-----------|
| Step 5 | S/R Module | Phase 1 output + OHLCV | Phase 1 complete | ReAct |
| Step 6 | Liquidity Agent | Phase 1 output + order book | Phase 1 complete | Event-driven |
| Step 7 | SMC Agent | Phase 1 output + OHLCV | Phase 1 complete | ReAct |
| Step 8 | Momentum Agent | OHLCV only | Immediately (no Phase 1 dependency) | Deliberation |
| Step 9 | Candlestick Agent | OHLCV only | Immediately | Event-driven |

**Note:** Steps 8 and 9 can start before Phase 1 completes since they only need price data, not fundamental/bias context. This saves ~2-3 seconds.

**Confluence Scoring Matrix:**

| Signal Source | Base Score | +S/R | +Liquidity | +SMC | +RSI | +Candlestick |
|--------------|-----------|------|------------|------|------|-------------|
| S/R Level | 20 | — | +15 | +20 | +10 | +10 |
| Liquidity Sweep | 25 | +15 | — | +25 | +10 | +10 |
| SMC Pattern | 30 | +20 | +25 | — | +15 | +15 |
| RSI Confirmation | 20 | +10 | +10 | +15 | — | +10 |
| Candlestick | 15 | +10 | +10 | +15 | +10 | — |

**Maximum possible score:** ~130 (all 5 signals with all confluence bonuses)
**Trade thresholds:**
- < 40: NO TRADE
- 40–60: ALERT ONLY (watchlist)
- 60–80: SMALL POSITION (0.5% risk)
- 80+: FULL POSITION (1-2% risk)

---

### PHASE 3: Trade Decision (Steps 10-12) — SEQUENTIAL

**Purpose:** Convert a scored signal into a validated, sized, risk-checked trade proposal.

```
  Confluence Score ≥ 40
         │
         ▼
  ┌──────────────┐
  │   STEP 10    │
  │   Trade      │──── Determines: entry type (limit/market/stop),
  │   Entry      │     entry price, entry conditions
  └──────┬───────┘
         │
         │  entry_plan
         ▼
  ┌──────────────┐
  │   STEP 11    │
  │   Position   │──── Calculates: lot size, risk amount,
  │   Sizing     │     correlation adjustment, multiplier stack
  └──────┬───────┘
         │
         │  sized_order
         ▼
  ┌──────────────────────────────────────────┐
  │              STEP 12                     │
  │         RISK GATE                        │
  │                                          │
  │  ┌────────────────────────────────────┐  │
  │  │ INFRASTRUCTURE-LEVEL CHECKS:      │  │
  │  │                                    │  │
  │  │ □ Max risk per trade (1-2%)       │  │
  │  │ □ Max daily loss (5%)             │  │
  │  │ □ Max open positions (3)          │  │
  │  │ □ Max correlation exposure (3%)   │  │
  │  │ □ Max drawdown halt (15%)         │  │
  │  │ □ Event proximity check           │  │
  │  │ □ Spread anomaly check            │  │
  │  │ □ Kill switch status              │  │
  │  └────────────────────────────────────┘  │
  │                                          │
  │  ┌────────────────────────────────────┐  │
  │  │ STOP LOSS PLACEMENT:              │  │
  │  │                                    │  │
  │  │ Structure level - ATR buffer       │  │
  │  │ × volatility factor                │  │
  │  │ × context adjustment               │  │
  │  │ + stop hunt protection             │  │
  │  └────────────────────────────────────┘  │
  │                                          │
  │  OUTPUT: APPROVED / REJECTED             │
  └──────────────┬───────────────────────────┘
                 │
           ┌─────┴─────┐
           │           │
       REJECTED    APPROVED
       → Log       → Continue
       → Stop      → HITL check
       → Alert     → Execute
```

**Why Sequential:**
- Step 10 (Entry) determines the price → Step 11 (Sizing) needs the price to calculate lot size → Step 12 (Risk Gate) needs both to validate
- The Risk Gate MUST be last — no trade can bypass it
- Each step's output is the next step's input; no parallelization possible

---

### PHASE 4: Execution (~100ms)

```
  APPROVED TRADE PROPOSAL
         │
         ▼
  ┌──────────────────────────────────────────────────────────┐
  │                    EXECUTION AGENT                        │
  │                                                          │
  │  Step 1: Validate proposal format (idempotency check)    │
  │  Step 2: Submit order to broker via ZeroMQ bridge        │
  │  Step 3: Confirm fill (wait for broker response)         │
  │  Step 4: Set stop loss order                             │
  │  Step 5: Set take profit orders (TP1, TP2)               │
  │  Step 6: Set trailing stop for TP3                       │
  │  Step 7: Log execution details                           │
  │                                                          │
  │  On failure: Retry once → Alert human → Halt pipeline    │
  └──────────────────────────────────────────────────────────┘
         │
         ▼
  POSITION OPEN → Trigger Phase 5 (Trade Management)
                → Trigger Phase 6 (Journal entry creation)
```

---

### PHASE 5: Trade Management (Steps 13-15) — CONTINUOUS

**Purpose:** Manage the open position from entry to exit.

```
  POSITION OPEN
         │
         ▼
  ┌──────────────────────────────────────────────────────────────┐
  │                TRADE MANAGEMENT LOOP                         │
  │              (Runs every M15 candle close)                    │
  │                                                              │
  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │
  │  │   STEP 13    │    │   STEP 14    │    │   STEP 15    │   │
  │  │              │    │              │    │              │   │
  │  │  Take Profit │◄──▶│    Trade     │◄──▶│    Exit      │   │
  │  │  Management  │    │  Management  │    │  Conditions  │   │
  │  │              │    │              │    │              │   │
  │  └──────────────┘    └──────────────┘    └──────────────┘   │
  │       │                    │                    │            │
  │       │                    │                    │            │
  │  TP hit?              SL move to BE?       Structure        │
  │  Partial close?       Partial close?       invalidation?    │
  │  Trail update?        News event?          Time stop?       │
  │                       Correlation?         Black swan?      │
  │                                              Session end?   │
  │                                                              │
  │  ┌────────────────────────────────────────────────────────┐  │
  │  │              MONITORING CHECK CYCLE                     │  │
  │  │                                                         │  │
  │  │  CHECK 1: TP level reached? → Execute partial close     │  │
  │  │  CHECK 2: SL needs adjustment? → Move SL                │  │
  │  │  CHECK 3: Volatility regime changed? → Adjust params    │  │
  │  │  CHECK 4: Upcoming news? → Apply pre-news protocol      │  │
  │  │  CHECK 5: Structure changed? → Reassess TP/SL           │  │
  │  │  CHECK 6: Correlation breach? → Reassess portfolio      │  │
  │  │  CHECK 7: Thesis invalidated? → Consider early exit     │  │
  │  │  CHECK 8: Black swan conditions? → Emergency protocol   │  │
  │  │  CHECK 9: Trade stale? → Time-based exit                │  │
  │  │  CHECK 10: EV turned negative? → Close                  │  │
  │  └────────────────────────────────────────────────────────┘  │
  │                                                              │
  │  EXIT TRIGGERED → Execute final close → Log to Journal       │
  └──────────────────────────────────────────────────────────────┘
         │
         ▼
  POSITION CLOSED → Trigger Phase 6 (Journal & Learning)
```

**Steps 13-15 Data Flow:**
```
  Step 13 (TP): Produces TP levels, partial close signals, trailing updates
       │
       ├──→ Step 14 (Management): Receives TP targets, applies dynamic rules
       │         │
       │         ├──→ Step 15 (Exit): Receives management state, checks exit conditions
       │         │
       │         └──← Step 15: Exit conditions can override management decisions
       │
       └──← Step 14: Management can adjust TP levels based on market conditions
```

---

### PHASE 6: Learning (Step 16) — POST-TRADE + PERIODIC

```
  POSITION CLOSED
         │
         ▼
  ┌──────────────────────────────────────────────────────────────┐
  │                    STEP 16: JOURNAL & LEARNING                │
  │                                                              │
  │  IMMEDIATE (within 1 hour of trade close):                   │
  │  ┌────────────────────────────────────────────────────────┐  │
  │  │  1. Record all trade data (entry, management, exit)    │  │
  │  │  2. Capture screenshots with annotations               │  │
  │  │  3. Compare predicted vs actual outcome                │  │
  │  │  4. Identify which signals were right/wrong            │  │
  │  │  5. Calculate R-multiple, MAE, MFE                     │  │
  │  └────────────────────────────────────────────────────────┘  │
  │                                                              │
  │  DAILY (end of trading day):                                 │
  │  ┌────────────────────────────────────────────────────────┐  │
  │  │  1. Compile all trades into daily summary              │  │
  │  │  2. Run performance analytics (win rate, expectancy)   │  │
  │  │  3. Update pattern reliability statistics              │  │
  │  │  4. Flag any rule deviations                           │  │
  │  └────────────────────────────────────────────────────────┘  │
  │                                                              │
  │  WEEKLY (Sunday):                                            │
  │  ┌────────────────────────────────────────────────────────┐  │
  │  │  1. Deep pattern recognition across all trades         │  │
  │  │  2. Agent weight adjustment (adaptive consensus)       │  │
  │  │  3. HMM regime model retraining                        │  │
  │  │  4. Signal weight updates (closed learning loop)       │  │
  │  │  5. Generate improvement plan                          │  │
  │  └────────────────────────────────────────────────────────┘  │
  │                                                              │
  │  MONTHLY:                                                    │
  │  ┌────────────────────────────────────────────────────────┐  │
  │  │  1. Full strategy parameter review                     │  │
  │  │  2. ML model retraining (XGBoost, LSTM)               │  │
  │  │  3. RL agent policy update                             │  │
  │  │  4. Performance attribution analysis                   │  │
  │  │  5. Trade playbook update (requires human approval)    │  │
  │  └────────────────────────────────────────────────────────┘  │
  │                                                              │
  │  FEEDBACK OUTPUTS:                                           │
  │  ┌────────────────────────────────────────────────────────┐  │
  │  │  → Step 1: Update sentiment source reliability         │  │
  │  │  → Step 2: Adjust HMM parameters, regime weights       │  │
  │  │  → Step 3: Update session volatility profiles          │  │
  │  │  → Step 4: Tune swing detection lookback               │  │
  │  │  → Step 5: Update S/R ML classifier                    │  │
  │  │  → Step 6: Retrain sweep classifier                    │  │
  │  │  → Step 7: Adjust pattern confluence weights           │  │
  │  │  → Step 8: Update adaptive RSI thresholds              │  │
  │  │  → Step 9: Update pattern reliability scores           │  │
  │  │  → Step 10: Optimize confluence scoring weights        │  │
  │  │  → Step 11: Update Kelly parameters, risk tiers        │  │
  │  │  → Step 12: Optimize stop placement model              │  │
  │  │  → Step 13: Retrain RL TP agent                        │  │
  │  │  → Step 14: Optimize trailing stop parameters          │  │
  │  │  → Step 15: Update early warning thresholds            │  │
  │  └────────────────────────────────────────────────────────┘  │
  └──────────────────────────────────────────────────────────────┘
```

---

## 4. Step-by-Step Data Contracts

Each step has a precise input/output contract. If a step fails to produce its output, downstream steps receive a degraded signal or halt entirely.

### Step 1 → Step 2

```json
{
  "step1_output": {
    "fundamental_bias": "BULLISH | BEARISH | NEUTRAL",
    "confidence": 0.0-1.0,
    "sentiment_score": -1.0 to +1.0,
    "event_risk_score": 0.0-1.0,
    "volatility_forecast": "LOW | NORMAL | HIGH | EXTREME",
    "upcoming_events": [{"time": "ISO8601", "impact": "HIGH|MEDIUM|LOW", "event": "string"}],
    "sentiment_momentum": {"direction": "+1|0|-1", "strength": 0.0-1.0}
  }
}
```

### Step 2 → Steps 3, 5-9

```json
{
  "step2_output": {
    "market_bias": "BULLISH | BEARISH | NEUTRAL",
    "bias_strength": 0.0-1.0,
    "regime": "TRENDING_BULL | TRENDING_BEAR | RANGE",
    "regime_confidence": 0.0-1.0,
    "conflict_flag": true|false,
    "timeframe_alignment": 0.0-1.0,
    "timeframe_biases": {"W1": {}, "D1": {}, "H4": {}, "H1": {}}
  }
}
```

### Step 3 → Steps 5-9

```json
{
  "step3_output": {
    "current_session": "ASIAN | LONDON | OVERLAP | NEW_YORK | WIND_DOWN | OFF_HOURS",
    "session_volatility_state": "EXPANDED | NORMAL | COMPRESSED",
    "asian_range": {"high": 1.0920, "low": 1.0850, "range_pips": 70, "classification": "TIGHT|NORMAL|WIDE"},
    "session_parameters": {
      "max_trades": 3,
      "position_size_mult": 1.0,
      "stop_mult": 1.2,
      "preferred_strategies": ["breakout", "trend_following"],
      "avoid_strategies": ["mean_reversion"]
    },
    "optimal_window": true|false
  }
}
```

### Step 4 → Steps 2, 5-9

```json
{
  "step4_output": {
    "structure_map": {
      "trend": "BULLISH | BEARISH | UNDEFINED",
      "latest_event": {"type": "BOS|CHoCH", "direction": "string", "price": 1.0850, "timeframe": "H4"},
      "bos_count": 3,
      "choch_count": 1,
      "structure_strength": 0.75
    },
    "key_levels": [{"price": 1.0850, "type": "SUPPORT|RESISTANCE", "strength": 0.85, "source": "SWING_HIGH"}],
    "chop_score": 0.0-1.0,
    "multi_tf_alignment": 0.0-1.0,
    "trade_direction": "BULLISH | BEARISH | NEUTRAL",
    "swing_highs": [],
    "swing_lows": []
  }
}
```

### Steps 5-9 → Confluence Scorer

Each of Steps 5-9 produces a standardized signal object:

```json
{
  "signal": {
    "step": 5,
    "agent_id": "sr_agent_01",
    "timestamp": "ISO8601",
    "instrument": "EURUSD",
    "signal_type": "LEVEL_APPROACH | SWEEP | ORDER_BLOCK | RSI_EXTREME | PATTERN",
    "direction": "BULLISH | BEARISH | NEUTRAL",
    "confidence": 0.0-1.0,
    "base_score": 20,
    "confluence_bonus": 15,
    "data": {},
    "reasoning": "string",
    "ttl_seconds": 3600
  }
}
```

### Confluence Scorer → Steps 10-12

```json
{
  "trade_proposal": {
    "confluence_score": 85,
    "grade": "A+ | A | B | C",
    "direction": "LONG | SHORT",
    "entry_zone": {"low": 1.0835, "high": 1.0850},
    "preferred_entry_price": 1.0842,
    "signal_breakdown": {
      "sr": {"present": true, "score": 78, "level": 1.0840},
      "liquidity": {"present": true, "score": 82, "sweep_detected": false},
      "smc": {"present": true, "score": 85, "ob_type": "bullish"},
      "rsi": {"present": true, "score": 70, "composite": 22},
      "candlestick": {"present": true, "score": 75, "pattern": "hammer"}
    },
    "reasoning": "string"
  }
}
```

### Step 12 (Risk Gate) → Execution Agent

```json
{
  "approved_trade": {
    "proposal_id": "uuid",
    "approved": true,
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
    "risk_breakdown": {
      "confluence_mult": 1.5,
      "regime_mult": 1.2,
      "performance_mult": 1.0,
      "session_mult": 1.2,
      "correlation_factor": 0.85
    },
    "hitl_required": false,
    "ttl_seconds": 300
  }
}
```

---

## 5. Parallel vs Sequential Execution Map

### Full Pipeline Timing

```
TIME (ms)   0    500   1000  1500  2000  2500  3000  3500  4000  4500  5000
            │     │     │     │     │     │     │     │     │     │     │
PHASE 1     ├─────────────────────────────┤
Step 1      ████████████████████░░░░░░░░░░  (2-3s, parallel)
Step 4      ████████████████████░░░░░░░░░░  (1-3s, parallel)
Step 2      ░░░░░░░░░░░░░░░░░░░████░░░░░░  (500ms, after Steps 1+4)
Step 3      ░░░░░░░░░░░░░░░░░░░░░░░██░░░░  (100ms, after Step 2)

PHASE 2     ░░░░░░░░░░░░░░░░░░░░░░░░████████┤  (parallel)
Step 5      ░░░░░░░░░░░░░░░░░░░░░░░░████░░░░  (1s)
Step 6      ░░░░░░░░░░░░░░░░░░░░░░░░███░░░░░  (800ms)
Step 7      ░░░░░░░░░░░░░░░░░░░░░░░░████░░░░  (1s)
Step 8      ░░░░░░░░░░░░░░░░░░░░░░░░██░░░░░░  (500ms)
Step 9      ░░░░░░░░░░░░░░░░░░░░░░░░█░░░░░░░  (200ms)
Confluence  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░████  (500ms)

PHASE 3     ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░█████┤  (sequential)
Step 10     ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░██░░░░  (500ms)
Step 11     ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░██░░  (300ms)
Step 12     ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░██  (200ms)

PHASE 4     ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░██┤  (execution)
Execute     ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░█  (100-500ms)

TOTAL: ~4.5-5.5 seconds from market data to order fill (high-conviction)
       ~3-4 seconds if Steps 8/9 start before Phase 1 completes
```

### Parallelization Rules

| Can Run in Parallel | Must Be Sequential | Reason |
|-------------------|-------------------|--------|
| Steps 1 and 4 | Steps 1 → 2 | Step 2 needs Step 1 output |
| Steps 5, 6, 7, 8, 9 | Steps 2 → 3 | Step 3 needs Step 2 output |
| Steps 8 and 9 (before Phase 1) | Steps 10 → 11 → 12 | Each depends on prior output |
| Phase 1 and Steps 8/9 | Step 12 → Execution | Risk Gate must pass first |
| Multiple instruments | Step 13 → 14 → 15 (per trade) | Management is per-position |

### Instrument Parallelism

When analyzing multiple instruments simultaneously:

```
INSTRUMENT PARALLEL EXECUTION:

  EURUSD:  [Phase1]──[Phase2]──[Phase3]──[Phase4]──[Phase5/6]
  GBPUSD:  [Phase1]──[Phase2]──[Phase3]──[Phase4]──[Phase5/6]
  USDJPY:  [Phase1]──[Phase2]──[Phase3]──[Phase4]──[Phase5/6]

  Shared agents (Orchestrator, Risk Gate, Monitor, Journal) handle all instruments.
  Signal agents (Steps 5-9) are instrument-specific but can run in parallel.
  Execution Agent serializes order submission (one order at a time).
```

---

## 6. Human-in-the-Loop Checkpoints

### HITL Decision Tree

```
TRADE PROPOSAL RECEIVED
         │
         ▼
  ┌──────────────────────────────┐
  │  Is confluence_score ≥ 75?   │
  │  AND risk_pct ≤ 1.0%?        │
  │  AND no conflict_flag?        │
  │  AND session is active?       │
  └──────────┬───────────────────┘
             │
        ┌────┴────┐
        │         │
       YES        NO
        │         │
        ▼         ▼
  ┌──────────┐  ┌──────────────────────────────┐
  │AUTO-     │  │  Is risk_pct > 1.5%?         │
  │EXECUTE   │  │  OR loss_streak ≥ 3?          │
  │          │  │  OR new_regime detected?       │
  │< 1 sec   │  │  OR unfamiliar_setup?          │
  └──────────┘  └──────────┬───────────────────┘
                           │
                      ┌────┴────┐
                      │         │
                     YES        NO
                      │         │
                      ▼         ▼
              ┌──────────┐  ┌──────────┐
              │ REQUIRE  │  │ ALERT +  │
              │ HUMAN    │  │ AUTO-    │
              │ APPROVAL │  │ APPROVE  │
              │          │  │ (5 min   │
              │ (no      │  │  timeout)│
              │  timeout)│  └──────────┘
              └──────────┘
```

### HITL Scenarios

| Scenario | Action | Timeout | Fallback |
|----------|--------|---------|----------|
| Standard trade (score ≥ 75, risk ≤ 1%) | Auto-execute | — | — |
| Good trade (score 60-75, risk ≤ 1.5%) | Alert + auto-approve | 5 min | Conservative: reduce size 50% |
| High risk (risk > 1.5%) | Require approval | 5 min | Skip trade |
| Loss streak ≥ 3 | Alert + halt strategy | 30 min | Flatten remaining, pause 24h |
| New regime detected | Alert + pause trading | 15 min | Continue with 50% reduced size |
| Max drawdown 10% | Alert + reduce all positions | 5 min | Auto-reduce to 50% exposure |
| Max drawdown 15% | Alert + flatten ALL | Immediate | — (auto-flatten) |
| Black swan detected | Alert + close all | Immediate | — (auto-close) |
| Strategy parameter change | Require approval | No auto | — |
| New instrument / unfamiliar | Require approval | No auto | — |

### HITL Delivery Channels

```
PRIMARY:    Telegram message with inline approval buttons
            [✅ APPROVE] [❌ REJECT] [⚙️ MODIFY]

SECONDARY:  Desktop notification (if desktop app running)

FALLBACK:   SMS alert (for critical: drawdown, black swan)

AUDIT:      All HITL decisions logged with timestamps and reasoning
```

---

## 7. Risk Gate Architecture

The Risk Gate (Step 12) is the **single most critical component** of the entire pipeline. It operates at the infrastructure level and cannot be bypassed by any agent.

### Risk Gate Check Sequence

```
TRADE PROPOSAL ARRIVES AT RISK GATE
         │
         ▼
  CHECK 1: Format Validation
  └─ Is the proposal structurally valid?
  └─ FAIL → REJECT (malformed proposal)

         │ PASS
         ▼
  CHECK 2: Idempotency
  └─ Is this a duplicate of an already-submitted order?
  └─ FAIL → REJECT (duplicate)

         │ PASS
         ▼
  CHECK 3: Kill Switch
  └─ Is the global kill switch active?
  └─ FAIL → REJECT (system halted)

         │ PASS
         ▼
  CHECK 4: Max Risk Per Trade
  └─ risk_pct ≤ max_risk_per_trade (2%)?
  └─ FAIL → REJECT or auto-reduce size

         │ PASS
         ▼
  CHECK 5: Max Daily Loss
  └─ cumulative_daily_loss + risk_pct ≤ max_daily_loss (5%)?
  └─ FAIL → REJECT (daily limit reached)

         │ PASS
         ▼
  CHECK 6: Max Open Positions
  └─ open_positions < max_open_positions (3)?
  └─ FAIL → REJECT (too many positions)

         │ PASS
         ▼
  CHECK 7: Correlation Exposure
  └─ effective_correlated_exposure + new_risk ≤ max_correlated (3%)?
  └─ FAIL → REJECT or reduce size

         │ PASS
         ▼
  CHECK 8: Max Drawdown
  └─ current_drawdown < max_drawdown_halt (15%)?
  └─ FAIL → FLATTEN ALL + HALT (emergency)

         │ PASS
         ▼
  CHECK 9: Event Proximity
  └─ high_impact_event within 30 minutes?
  └─ FAIL → REJECT (pre-event blackout)

         │ PASS
         ▼
  CHECK 10: Spread Anomaly
  └─ current_spread ≤ 3x normal_spread?
  └─ FAIL → REJECT (liquidity issue)

         │ PASS
         ▼
  CHECK 11: Stop Loss Validation
  └─ stop_loss_distance ≤ max_stop (2% of account)?
  └─ stop_loss is beyond structure level?
  └─ FAIL → Auto-adjust (reduce size to fit 2% cap)

         │ PASS
         ▼
  ┌──────────────────┐
  │    APPROVED      │
  │  Forward to      │
  │  Execution Agent │
  └──────────────────┘
```

### Risk Parameters (Configurable)

```json
{
  "risk_config": {
    "max_risk_per_trade_pct": 2.0,
    "max_daily_loss_pct": 5.0,
    "max_open_positions": 3,
    "max_correlated_positions": 2,
    "max_correlated_exposure_pct": 3.0,
    "max_drawdown_halt_pct": 15.0,
    "max_drawdown_reduce_pct": 10.0,
    "event_blackout_minutes": 30,
    "max_spread_multiplier": 3.0,
    "max_stop_loss_pct": 2.0,
    "consecutive_loss_halt": 3,
    "cooldown_after_halt_hours": 24
  }
}
```

---

## 8. Error Handling at Each Step

### Error Classification

| Severity | Description | Response | Recovery |
|----------|------------|----------|----------|
| **CRITICAL** | Risk breach, execution failure, data corruption | Halt pipeline, alert human | Manual intervention |
| **HIGH** | Agent timeout, model error, data source down | Restart agent, use fallback | Auto-recovery with fallback |
| **MEDIUM** | Stale data, slow inference, partial signal | Use cached data, degrade gracefully | Auto-recovery on next cycle |
| **LOW** | Minor warning, non-critical metric out of range | Log and continue | Self-correcting |

### Step-by-Step Error Handling

#### Step 1: Fundamental Intelligence

| Error | Detection | Response | Fallback |
|-------|-----------|----------|----------|
| News API down | HTTP timeout/error | Switch to RSS feeds | Use cached headlines (max 1h old) |
| FinBERT inference failure | Model error | Skip sentiment layer | Use neutral sentiment (0.5) |
| Calendar data stale | No events in 24h+ | Alert + use cached | Skip event risk scoring |
| All news sources down | All feeds fail | Set event_risk_score = 0.5 | Continue with reduced confidence |

**Degraded mode output:** `fundamental_bias: "NEUTRAL", confidence: 0.3, event_risk_score: 0.5`

#### Step 2: Market Bias

| Error | Detection | Response | Fallback |
|-------|-----------|----------|----------|
| HMM model fails | Inference error | Use simple trend detection (MA crossover) | Regime = "UNDEFINED" |
| Step 1 output missing | No fundamental data | Use technical-only bias | Reduce confidence by 20% |
| Step 4 output missing | No structure data | Use fundamental-only bias | Reduce confidence by 30% |
| Both inputs missing | Pipeline failure | Set bias = NEUTRAL | Halt signal detection |

**Degraded mode output:** `market_bias: "NEUTRAL", confidence: 0.2, regime: "UNDEFINED"`

#### Step 3: Session Analysis

| Error | Detection | Response | Fallback |
|-------|-----------|----------|----------|
| Session clock error | Invalid time | Use UTC hour directly | Manual session classification |
| Asian range data missing | No Asian session data | Skip Asian range analysis | Use previous day's range |

**Degraded mode output:** `current_session: inferred from UTC hour, session_parameters: conservative defaults`

#### Step 4: Market Structure

| Error | Detection | Response | Fallback |
|-------|-----------|----------|----------|
| OHLCV data missing | No candle data for timeframe | Use cached structure | Skip that timeframe |
| Swing detection fails | No swings found | Increase lookback | Use previous swing points |
| BOS/CHoCH unclear | Ambiguous structure | Set trend = UNDEFINED | Reduce alignment score |

**Degraded mode output:** `structure_map: cached, multi_tf_alignment: 0.0, trade_direction: "NEUTRAL"`

#### Steps 5-9: Signal Detection

| Error | Detection | Response | Fallback |
|-------|-----------|----------|----------|
| Agent timeout (>30s) | Orchestrator timeout | Kill agent, skip signal | Signal = absent (score 0) |
| Agent crash | Process exit | Restart once, then skip | Signal = absent |
| Invalid signal format | Validation error | Log + skip | Signal = absent |
| Data stale (>5 min) | Timestamp check | Use cached data | Reduce confidence by 50% |

**Critical rule:** If any signal agent fails, its contribution to the confluence score is 0. The remaining agents still vote. The system degrades gracefully — fewer signals means lower confluence score, which means smaller position or no trade.

#### Step 10: Trade Entry

| Error | Detection | Response | Fallback |
|-------|-----------|----------|----------|
| Entry price stale | Price moved > 1 ATR since proposal | Re-score confluence at new price | Skip if score drops below threshold |
| Limit order zone invalid | Price already beyond zone | Switch to market order or skip | Alert human |

#### Step 11: Position Sizing

| Error | Detection | Response | Fallback |
|-------|-----------|----------|----------|
| Account balance unavailable | API error | Use last known balance | Reduce size by 20% as safety margin |
| Correlation data stale | No recent correlation update | Use 30-day default correlations | Conservative sizing |
| Calculated size = 0 | Stop too wide for risk budget | Skip trade | Alert human |

#### Step 12: Risk Gate

| Error | Detection | Response | Fallback |
|-------|-----------|----------|----------|
| Risk check timeout | >10s | REJECT (conservative default) | Log error, alert human |
| Any check fails | Boolean check | REJECT with reason | No fallback — rejection is final |
| Risk Gate agent crash | Process failure | REJECT ALL trades until recovered | Emergency halt |

**The Risk Gate NEVER fails open.** If there's any doubt, the trade is rejected.

#### Phase 4: Execution

| Error | Detection | Response | Fallback |
|-------|-----------|----------|----------|
| Broker disconnect | Connection error | Retry once (1s delay) | Alert human, halt new entries |
| Order rejected by broker | Broker error code | Log + alert human | Skip trade, don't retry |
| Slippage > 2x expected | Fill price check | Log warning | Continue (slippage is normal) |
| No fill within 30s (limit) | Timeout | Cancel limit, switch to market | Or skip if price moved too far |
| ZeroMQ bridge failure | Connection error | Restart bridge | Alert human, manual execution |

#### Steps 13-15: Trade Management

| Error | Detection | Response | Fallback |
|-------|-----------|----------|----------|
| Price feed lost | No ticks for >30s | Use broker-side stops only | Alert human |
| Management agent crash | Process failure | Broker-side SL/TP still active | Restart agent |
| Partial close fails | Order error | Retry once | Full close if retry fails |
| Trailing stop calculation error | Invalid trail level | Keep current SL | Alert human |

**Critical safety net:** All positions always have broker-side stop losses set at order time. Even if the entire Alpha Stack system crashes, positions are protected by the broker's order management.

#### Step 16: Journal & Learning

| Error | Detection | Response | Fallback |
|-------|-----------|----------|----------|
| Trade data incomplete | Missing fields | Log what's available | Mark as "incomplete" |
| Database write failure | DB error | Retry with backoff | Write to local file as backup |
| Model retraining fails | Training error | Keep existing model | Alert human |

---

## 9. Loop System Improvement Map

### How Each Loop Improves Each Step

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    LOOP SYSTEM IMPROVEMENT CYCLE                             │
│                                                                             │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                   │
│  │   TICK      │     │   CANDLE    │     │   SESSION   │                   │
│  │   LOOP      │     │   LOOP      │     │   LOOP      │                   │
│  │  (1 sec)    │     │  (M15)      │     │  (4-8h)     │                   │
│  └──────┬──────┘     └──────┬──────┘     └──────┬──────┘                   │
│         │                   │                   │                           │
│  ┌──────▼──────┐     ┌──────▼──────┐     ┌──────▼──────┐                   │
│  │  Immediate  │     │  Tactical   │     │  Strategic  │                   │
│  │  adaptation │     │  tuning     │     │  review     │                   │
│  └─────────────┘     └─────────────┘     └─────────────┘                   │
│                                                                             │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                   │
│  │   DAILY     │     │   WEEKLY    │     │  MONTHLY    │                   │
│  │   LOOP      │     │   LOOP      │     │   LOOP      │                   │
│  │  (24h)      │     │  (7d)       │     │  (30d)      │                   │
│  └──────┬──────┘     └──────┬──────┘     └──────┬──────┘                   │
│         │                   │                   │                           │
│  ┌──────▼──────┐     ┌──────▼──────┐     ┌──────▼──────┐                   │
│  │  Pattern    │     │  Model      │     │  Strategy   │                   │
│  │  stats      │     │  retraining │     │  overhaul   │                   │
│  └─────────────┘     └─────────────┘     └─────────────┘                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Loop → Step Improvement Matrix

| Loop | Frequency | Steps Improved | What Changes | Human Approval? |
|------|-----------|---------------|--------------|-----------------|
| **Tick** | 1s | 6 (Liquidity) | Order book updates, delta recalculation | No |
| **Candle (M15)** | 15min | 5, 6, 7, 8, 9, 13, 14, 15 | S/R proximity alerts, SMC scan, RSI recalc, TP/trail updates | No |
| **Session** | 4-8h | 3, 5, 6 | Session transition rules, Asian range update, session-specific params | No |
| **Daily** | 24h | 1, 2, 3, 4, 5, 7, 16 | Sentiment weights, regime update, session vol profiles, S/R recalc, pattern stats | No |
| **Weekly** | 7d | 1, 2, 4, 7, 8, 10, 11, 16 | FinBERT retrain, HMM retrain, swing lookback, pattern weights, RSI thresholds, confluence weights, Kelly params | No (auto) |
| **Monthly** | 30d | ALL (1-16) | Full model recalibration, strategy parameter review, playbook update | **YES** (for strategy changes) |
| **Post-Trade** | Per trade | 7, 8, 9, 10, 13, 14, 15, 16 | Pattern outcome tracking, RSI accuracy, candlestick reliability, confluence calibration, TP optimization, management tuning | No |

### Closed Learning Loop Detail

```
TRADE OUTCOME
     │
     ▼
REFLECTION AGENT
     │
     ├──→ STEP 7 (SMC): "H4 bullish OB at D1 support had 80% win rate
     │                     across 15 trades. Increase OB weight: 0.30 → 0.32"
     │
     ├──→ STEP 8 (RSI): "RSI oversold + bullish divergence confirmed 12/15
     │                     winning entries. Increase divergence bonus: +25 → +30"
     │
     ├──→ STEP 10 (Entry): "Confluence score 85+ had 78% win rate.
     │                       Score 60-70 had only 52%. Raise threshold: 60 → 65"
     │
     ├──→ STEP 11 (Sizing): "Half-Kelly produced 15% better risk-adjusted
     │                        returns than fixed 1%. Maintain Half-Kelly default."
     │
     ├──→ STEP 12 (Stop): "0.5 ATR buffer was too tight for GBPJPY.
     │                      Increase to 0.75 ATR for high-vol pairs."
     │
     ├──→ STEP 13 (TP): "Trades that held 34% runner past 3R averaged
     │                     4.2R total. Wider trailing (ATR×3.0) captures more."
     │
     ├──→ STEP 14 (Management): "Moving SL to BE at 1R prevented 3 trades
     │                            from reaching 2R. Consider 1.5R for trending."
     │
     └──→ STEP 15 (Exit): "Early exit at warning_score=3 saved avg 0.6R
                            per losing trade. Maintain threshold."
```

### Adaptive Weight Update Mechanism

```python
# Weekly agent weight adjustment (Section 7.4 of Multi-Agent Architecture)
def update_agent_weights(agents, recent_trades):
    for agent in agents:
        # Calculate accuracy of agent's signals over last 50 trades
        correct = sum(1 for t in recent_trades 
                      if t.signals[agent.id].direction == t.outcome_direction)
        total = sum(1 for t in recent_trades if t.signals[agent.id].present)
        
        recent_accuracy = correct / total if total > 0 else agent.historical_accuracy
        
        # Blend: 70% recent, 30% historical
        blended = 0.7 * recent_accuracy + 0.3 * agent.historical_accuracy
        
        # Adjust weight (bounded 0.05 - 0.40)
        agent.weight = clip(blended * TOTAL_WEIGHT, 0.05, 0.40)
    
    # Normalize to sum to 1.0
    normalize_weights(agents)
    
    # Log changes
    for agent in agents:
        if abs(agent.weight - agent.previous_weight) > 0.02:
            journal.log(f"Agent {agent.id} weight: {agent.previous_weight} → {agent.weight}")
```

---

## 10. Performance Requirements & Latency Budget

### Latency Targets by Phase

| Phase | Steps | Target Latency | Hard Limit | Notes |
|-------|-------|---------------|------------|-------|
| Phase 1: Context | 1-4 | 2-3s | 5s | Steps 1+4 parallel |
| Phase 2: Signals | 5-9 | 1-2s | 3s | All parallel |
| Phase 2: Confluence | Aggregator | 200ms | 500ms | Simple scoring |
| Phase 3: Decision | 10-12 | 500ms-1s | 2s | Sequential |
| Phase 4: Execution | Execution | 100-500ms | 2s | Broker-dependent |
| **TOTAL** | **1-12** | **4-6s** | **12s** | **Signal to fill** |

### Latency Breakdown: Signal to Execution

```
MARKET EVENT (e.g., price hits S/R level)
     │
     │ 0ms ─── Event detected (tick processing)
     │
     ▼
PHASE 1: Context Building
     │  Step 1 (Fundamental): 2000ms ─── LLM inference + API calls
     │  Step 4 (Structure):   1500ms ─── OHLCV analysis + HMM (parallel)
     │  Step 2 (Bias):         500ms ─── Fusion calculation
     │  Step 3 (Session):      100ms ─── Clock check + params
     │
     │ ~3000ms elapsed
     ▼
PHASE 2: Signal Detection
     │  Step 5 (S/R):          800ms ─── Fractal + volume profile
     │  Step 6 (Liquidity):    600ms ─── Sweep detection
     │  Step 7 (SMC):         1000ms ─── OB/FVG/BOS scan
     │  Step 8 (RSI):          300ms ─── Indicator calc
     │  Step 9 (Candlestick):  100ms ─── Pattern match
     │  Confluence:            200ms ─── Score calculation
     │
     │ ~1200ms elapsed (parallel)
     ▼
PHASE 3: Trade Decision
     │  Step 10 (Entry):       300ms ─── Entry type selection
     │  Step 11 (Sizing):      200ms ─── Lot size calculation
     │  Step 12 (Risk Gate):   100ms ─── Rule validation
     │
     │ ~600ms elapsed
     ▼
PHASE 4: Execution
     │  Validate:               10ms ─── Format + idempotency
     │  Submit:                 50ms ─── ZeroMQ to MT5
     │  Fill confirmation:     200ms ─── Broker response
     │  Set SL/TP:             100ms ─── Management orders
     │
     │ ~360ms elapsed
     ▼
ORDER FILLED
     │
     TOTAL: ~5160ms (5.2 seconds)
```

### Performance Optimization Strategies

| Strategy | Applies To | Latency Savings | Trade-off |
|----------|-----------|----------------|-----------|
| **Pre-compute fundamentals** | Step 1 | 1.5s | Stale data risk (refresh hourly) |
| **Cache structure analysis** | Step 4 | 1s | Miss intra-candle structure changes |
| **Start Steps 8/9 early** | Steps 8, 9 | 1-2s | May analyze without bias context |
| **Use fast models for signals** | Steps 5-9 | 0.5-1s | Lower reasoning quality |
| **Pre-score S/R levels** | Step 5 | 0.5s | Needs periodic refresh |
| **Stream order book** | Step 6 | 0.3s | Higher data costs |
| **Batch confluence calc** | Aggregator | 0.1s | Minimal trade-off |

### Model Selection for Latency

| Agent | Model Tier | Expected Latency | Rationale |
|-------|-----------|-----------------|-----------|
| Fundamental (Step 1) | Reasoning-tier | 1-2s | Complex synthesis needs powerful model |
| Structure (Steps 2-4) | Fast model | 200-500ms | Pattern matching, not deep reasoning |
| S/R (Step 5) | Minimal/algo | 100-300ms | Primarily algorithmic |
| Liquidity (Step 6) | Minimal/algo | 100-200ms | XGBoost classifier, no LLM |
| SMC (Step 7) | Fast model | 300-800ms | Pattern classification |
| Momentum (Step 8) | Minimal/algo | 50-100ms | Pure calculation |
| Candlestick (Step 9) | Minimal/algo | 50-100ms | Pattern matching |
| Confluence | None (code) | 10-50ms | Simple arithmetic |
| Entry (Step 10) | Fast model | 200-400ms | Decision tree |
| Sizing (Step 11) | None (code) | 10-50ms | Formula-based |
| Risk Gate (Step 12) | None (code) | 10-50ms | Rule validation |
| Execution | None (code) | 100-500ms | Broker API latency |

---

## 11. Signal-to-Execution Timing Diagram

### High-Conviction Setup (Score 85+)

```
TIME    ACTION                                    LATENCY
─────   ─────────────────────────────────────     ───────
T+0     Price touches H4 Order Block              (market event)
T+50ms  Tick processed, event dispatched           50ms
T+100ms Steps 8,9 start (no Phase 1 dependency)   50ms
T+100ms Steps 1,4 start (parallel)                50ms
T+1.6s  Step 4 completes (structure analysis)     1500ms
T+2.1s  Step 1 completes (fundamental analysis)   2000ms
T+2.6s  Step 2 completes (bias fusion)            500ms
T+2.7s  Step 3 completes (session params)         100ms
T+2.7s  Phase 2 signal agents receive context
T+2.8s  Step 8 completes (RSI analysis)           300ms (started early)
T+2.9s  Step 9 completes (candlestick)            100ms (started early)
T+3.5s  Step 5 completes (S/R levels)             800ms
T+3.5s  Step 6 completes (liquidity)              600ms
T+3.7s  Step 7 completes (SMC patterns)           1000ms
T+3.9s  Confluence scored: 85 (A+)                200ms
T+4.2s  Step 10: Entry plan (limit at OB)         300ms
T+4.4s  Step 11: Position sized (0.02 lots)       200ms
T+4.5s  Step 12: Risk Gate APPROVED               100ms
T+4.5s  HITL check: Score 85, risk 1.2% → AUTO    10ms
T+4.6s  Order submitted to broker                 100ms
T+4.8s  Fill confirmed @ 1.0843 (1pip slip)       200ms
T+4.9s  SL/TP orders set                          100ms
T+5.0s  Journal entry created                     100ms
        ─────────────────────────────────────────
        TOTAL: ~5 seconds from event to fill
```

### Moderate Setup (Score 65, HITL Required)

```
TIME    ACTION                                    LATENCY
─────   ─────────────────────────────────────     ───────
T+0     RSI divergence detected on H1             (market event)
T+5s    Full pipeline completes, score 65
T+5.1s  HITL required (score < 75)                ALERT SENT
T+5.1s  Telegram notification with [APPROVE] button
T+5.1s  ... waiting for human ...
T+5.1s  + 47s Human approves                       47s human delay
T+5.2s  Order submitted
T+5.4s  Fill confirmed
        ─────────────────────────────────────────
        TOTAL: ~55 seconds (dominated by human response)
```

### Emergency Exit (Black Swan)

```
TIME    ACTION                                    LATENCY
─────   ─────────────────────────────────────     ───────
T+0     VIX spikes 45% in 1 minute                (anomaly detected)
T+100ms Black Swan Sentinel detects anomaly       100ms
T+100ms P0 alert dispatched to all agents
T+200ms All positions flagged for immediate close 100ms
T+250ms Market orders submitted for all positions 50ms
T+500ms All fills confirmed                       250ms
T+600ms Emergency halt activated                  100ms
T+700ms Human alerted via Telegram + SMS          100ms
        ─────────────────────────────────────────
        TOTAL: ~700ms from detection to all-flat
```

---

## 12. Appendix: Agent-Step Mapping

### Complete Mapping Table

| Step | Name | Agent | Loop Type | Trigger | Parallel Group | Latency Budget |
|------|------|-------|-----------|---------|---------------|---------------|
| 1 | Fundamental Intelligence | Fundamental Agent | ReAct | Pre-session + on-event | Phase 1 (with Step 4) | 2-3s |
| 2 | Market Bias | Structure Agent | Deliberation | After Steps 1+4 | Phase 1 (sequential) | 500ms |
| 3 | Session Analysis | Structure Agent | Event-driven | After Step 2 | Phase 1 (sequential) | 100ms |
| 4 | Market Structure | Structure Agent | Deliberation | H1/H4 candle close | Phase 1 (with Step 1) | 1-3s |
| 5 | Support & Resistance | Structure Agent (S/R Module) | ReAct | M15 candle close | Phase 2 (parallel) | 800ms |
| 6 | Liquidity Detection | Liquidity Agent | Event-driven | Continuous tick + M15 | Phase 2 (parallel) | 600ms |
| 7 | Smart Money Concepts | SMC Agent | ReAct | M15 candle close | Phase 2 (parallel) | 1s |
| 8 | RSI Confirmation | Momentum Agent | Deliberation | M15 candle close | Phase 2 (parallel) | 300ms |
| 9 | Candlestick Confirmation | Candlestick Agent | Event-driven | Candle close | Phase 2 (parallel) | 100ms |
| 10 | Trade Entry | Entry Agent | Plan-and-Execute | Confluence ≥ 40 | Phase 3 (sequential) | 300ms |
| 11 | Position Sizing | Entry Agent | Evaluation | After Step 10 | Phase 3 (sequential) | 200ms |
| 12 | Stop Loss / Risk Gate | Risk Gate Agent | Evaluation | Every trade proposal | Phase 3 (sequential) | 100ms |
| 13 | Take Profit | TP Agent | Plan-and-Execute | On entry + in-trade | Phase 5 (continuous) | 100ms |
| 14 | Trade Management | Trade Mgmt Agent | Event-driven | Continuous while open | Phase 5 (continuous) | 100ms |
| 15 | Exit Conditions | Trade Mgmt Agent | Event-driven | Continuous while open | Phase 5 (continuous) | 100ms |
| 16 | Journal & Learning | Journal Agent + Reflection Agent | Reflection | Post-trade + periodic | Phase 6 (post-trade) | N/A |

### Agent Communication Flow

```
                    ┌─────────────────┐
                    │   ORCHESTRATOR   │
                    │   (Depth 0)      │
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
    ┌────▼────┐        ┌────▼────┐        ┌────▼────┐
    │ANALYSIS │        │DECISION │        │MANAGEMENT│
    │ AGENTS  │        │ AGENTS  │        │ AGENTS   │
    │(Depth 1)│        │(Depth 1)│        │(Depth 1) │
    └────┬────┘        └────┬────┘        └────┬────┘
         │                   │                   │
    ┌────▼────┐        ┌────▼────┐        ┌────▼────┐
    │ WORKERS │        │ WORKERS │        │ WORKERS  │
    │(Depth 2)│        │(Depth 2)│        │(Depth 2) │
    └─────────┘        └─────────┘        └──────────┘

ANALYSIS AGENTS (Depth 1):
  Fundamental → News Worker, Sentiment Worker, Calendar Worker
  Structure → Regime Detector, Multi-TF Engine, Session Analyzer
  Liquidity → Order Book Worker, Sweep Classifier, On-Chain Worker
  SMC → OB Scanner, FVG Scanner, BOS/CHoCH Detector
  Momentum → RSI Engine, Divergence Detector, Composite Calculator
  Candlestick → Pattern Detector, Failure Monitor

DECISION AGENTS (Depth 1):
  Signal Aggregator → (no workers, pure scoring)
  Entry Agent → (no workers, pure logic)
  Risk Gate → (no workers, pure rules)

MANAGEMENT AGENTS (Depth 1):
  TP Agent → (no workers, event-driven)
  Trade Mgmt → Correlation Watcher, News Handler
  Execution → Broker Adapter (MT5/CCXT)
  Monitor → Black Swan Sentinel, Health Checker
  Reflection → (no workers, periodic)
  Journal → Performance Analytics, Pattern Recognition
```

---

## Summary

### Flow at a Glance

```
MARKET DATA
    │
    ▼
[STEP 1: Fundamental] ──────────────────────────────────────────────┐
[STEP 4: Structure]   ──────────────────────────────────────┐       │
                                                            │       │
[STEP 2: Market Bias] ◄────────────────────────────────────┘───────┘
[STEP 3: Session]     ◄──── Step 2
    │
    ▼
[STEP 5: S/R]         ──── PARALLEL ────┐
[STEP 6: Liquidity]   ──── PARALLEL ────┤
[STEP 7: SMC]         ──── PARALLEL ────┼──→ [CONFLUENCE SCORER]
[STEP 8: RSI]         ──── PARALLEL ────┤
[STEP 9: Candlestick] ──── PARALLEL ────┘
    │
    ▼ (if score ≥ 40)
[STEP 10: Entry] → [STEP 11: Sizing] → [STEP 12: RISK GATE]
    │
    ▼ (if approved)
[HITL CHECK] → [EXECUTION]
    │
    ▼
[STEP 13: TP] ↔ [STEP 14: Management] ↔ [STEP 15: Exit]
    │
    ▼ (on close)
[STEP 16: Journal & Learning]
    │
    └──→ FEEDBACK LOOP → Improve Steps 1-15 → Repeat
```

### Key Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Signal-to-execution latency | < 5s (high conviction) | End-to-end timing |
| Pipeline success rate | > 99% | Successful completions / attempts |
| Risk Gate rejection rate | 5-15% | Healthy filter rate |
| HITL response time | < 2 min average | Human approval latency |
| System uptime | > 99.5% | During market hours |
| Closed-loop improvement | Measurable monthly | Win rate, expectancy trends |
| Black swan response | < 1s | Detection to all-flat |

---

*Document generated by Alpha Stack Strategy Flow Architect*
*Version 1.0 — 2026-07-11*
*Status: Architecture Design Complete — Ready for Implementation Review*
