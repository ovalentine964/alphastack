# Alpha Strategy & Loop System — Review Report

**Date:** 2026-07-11
**Reviewer:** Strategy & Loops Review Agent
**Scope:** 16-step strategy, confluence scoring, loop systems, market regimes, edge cases, implementability
**Severity Scale:** CRITICAL / HIGH / MEDIUM / LOW

---

## Executive Summary

The Alpha Strategy is an ambitious, well-researched 16-step trading pipeline with a multi-agent architecture. The overall design is **sound in concept** but has **several correctness and implementability issues** that must be resolved before production deployment. The confluence scoring fix document resolves the most critical mathematical inconsistency. The loop systems are underdefined. Edge case handling is comprehensive in documentation but has execution gaps.

**Verdict: 3 CRITICAL, 5 HIGH, 8 MEDIUM issues found. Strategy is implementable after fixes.**

---

## 1. Logical Connectivity — Are the 16 Steps Connected?

### Result: PASS with MEDIUM gaps

The 16 steps form a coherent pipeline across 6 phases:

```
Phase 1 (Context):  Step 1 → Step 2 → Step 3 → Step 4
Phase 2 (Signals):  Steps 5-9 (parallel) → Confluence Scorer
Phase 3 (Decision): Step 10 → Step 11 → Step 12 (Risk Gate)
Phase 4 (Execution): Broker order
Phase 5 (Management): Steps 13-15 (continuous loop)
Phase 6 (Learning): Step 16 → feedback to Steps 1-15
```

**Connections verified:**
- ✅ Step 1 → Step 2: `fundamental_bias`, `sentiment_score`, `event_risk_score` feed into Market Bias
- ✅ Step 2 → Steps 3, 5-9: `market_bias`, `regime`, `conflict_flag` feed downstream
- ✅ Step 3 → Steps 5-9: `session_parameters`, `asian_range` inform signal detection
- ✅ Step 4 → Step 2: `structure_map`, `key_levels` feed back into bias construction (bidirectional)
- ✅ Steps 5-9 → Confluence Scorer: All produce standardized signal objects
- ✅ Confluence Scorer → Step 10: `confluence_score`, `grade`, `trade_proposal`
- ✅ Step 10 → Step 11 → Step 12: Sequential dependency chain (entry → sizing → risk gate)
- ✅ Step 12 → Execution: `approved_trade` with all parameters
- ✅ Steps 13-15: Bidirectional loop (TP ↔ Management ↔ Exit)
- ✅ Step 16: Feedback loop to all prior steps

**Gaps identified:**

| # | Gap | Severity | Description |
|---|-----|----------|-------------|
| G1 | Step 4 → Step 2 bidirectional dependency | MEDIUM | Architecture says Step 4 runs parallel with Step 1, but Step 2 needs both. If Step 4 is slow, Step 2 blocks. No fallback defined for partial input. |
| G2 | Step 9 → Step 10 implicit dependency | LOW | Step 9 (Candlestick) produces `pattern_score` but Step 10 (Entry) uses it via confluence. The direct causal link is through the scorer, not step-to-step. This is fine architecturally but the documentation implies direct feeding. |
| G3 | Step 16 → Steps 1-15 feedback loop timing | MEDIUM | The feedback loop is described conceptually but the actual update mechanism (how weights change, when models retrain) is only sketched. Weekly auto-updates are mentioned but the trigger logic is undefined. |

### Verdict: The 16 steps are logically connected. No missing links. Two timing gaps need resolution.

---

## 2. Confluence Scoring — Mathematical Correctness

### Result: PASS (after fix document) — Two issues remain

The `fix_confluence_scoring.md` document successfully resolves the original dual-system problem. The unified 3-layer system is mathematically correct.

**Layer 1 → Layer 2 → Layer 3 Pipeline:**
```
Raw Score (0-100 per step) → Normalize (÷100) → Weighted Sum (0.00-1.00)
```

**Weight verification:**
```
SMC:        0.25
Liquidity:  0.20
Kill Zone:  0.15
Candlestick:0.15
S/R:        0.10
RSI:        0.05
Volume:     0.05
News:       0.05
─────────────────
TOTAL:      1.00 ✅
```

**Mathematical issues found:**

| # | Issue | Severity | Description |
|---|-------|----------|-------------|
| M1 | SMC normalization denominator mismatch | HIGH | The fix document defines SMC theoretical max as 250 (sum of all possible points including bonuses). But the raw scoring in Steps 5-8 defines individual component maxes that sum to different values depending on which bonuses apply. The normalization `min(smc_raw / 250 * 100, 100)` is correct *only if* 250 is truly the theoretical max. Rechecking: 30+20+25+30+20+15+25+15+20+25+15+10 = 250 ✅. However, not all bonuses can simultaneously apply (e.g., "BOS/CHoCH + OB" and "Liquidity Sweep + OB" share the OB component). The *practical* max is closer to 200-220, making the normalization slightly conservative. This is acceptable — it means SMC rarely exceeds 0.50 normalized, which keeps the final score realistic. |
| M2 | Worked example arithmetic error | HIGH | In the fix document's worked example, SMC raw is stated as 80 (OB 30 + FVG overlap 15 + BOS 25 + volume 10). But the normalization shows `80/250×100 = 32`. This is correct. However, the example then says the SMC category score is 0.32, which is `32/100 = 0.32`. This is correct. **No error here upon recheck.** |
| M3 | Critical gate rule interaction with Kill Zone | MEDIUM | The gate rule states: "IF any of [SMC, Liquidity, Kill Zone] has category_score == 0: MAXIMUM confluence_score = 0.60." But Kill Zone is binary (0 or 1). If a trader operates outside kill zones (e.g., Asian session range trading), the score is permanently capped at 0.60, making it impossible to achieve A+ grade. This is by design but may be too restrictive for strategies that legitimately trade outside kill zones. |
| M4 | Step 1 news score double-counting | MEDIUM | Step 1 produces `fundamental_bias` which feeds into Step 2's `market_bias`. The confluence scorer also includes a separate `News/Fundamental` category at 0.05 weight. This means fundamental information is counted twice: once through the bias (which influences S/R, SMC, etc. scoring indirectly) and once directly. The 0.05 weight makes this negligible but it's architecturally impure. |

**Scoring thresholds verification:**
```
Grade A+ (≥0.80): Requires nearly all categories scoring >0.70 with kill zone active. Mathematically achievable but rare.
Grade A  (≥0.65): Achievable with 4-5 strong signals. Realistic.
Grade B  (≥0.50): Achievable with 3 moderate signals. Common.
Grade C  (≥0.35): Borderline — log only.
Grade F  (<0.35): No trade.
```

These thresholds are well-calibrated. The A+ threshold is intentionally high (only ~5-10% of setups should qualify).

### Verdict: Scoring system is mathematically correct after the fix. Two minor issues (double-counting, kill zone restrictiveness) are acceptable for v1.

---

## 3. Loop Systems — ReAct, Reflection, Deliberation

### Result: HIGH issues — Loop types are named but not defined

The architecture document references three loop types in the Agent-Step Mapping table (Section 12):
- **ReAct**: Steps 1, 5, 7
- **Deliberation**: Steps 2, 4, 8
- **Event-driven**: Steps 3, 6, 9, 14, 15
- **Plan-and-Execute**: Steps 10, 13
- **Reflection**: Step 16
- **Evaluation**: Steps 11, 12

**Issues:**

| # | Issue | Severity | Description |
|---|-------|----------|-------------|
| L1 | Loop types undefined | HIGH | The terms "ReAct," "Deliberation," and "Reflection" are used but never defined in any of the reviewed documents. ReAct (Reason + Act) is a known AI agent pattern (Yao et al., 2022), but its specific implementation here — what constitutes a "reason" step, what constitutes an "act" step, how many iterations, what the stopping condition is — is never specified. |
| L2 | No loop termination conditions | HIGH | For ReAct and Deliberation loops, there's no specification of: (a) maximum iterations, (b) convergence criteria, (c) timeout behavior. A ReAct loop that doesn't terminate could block the entire pipeline. |
| L3 | Deliberation vs. ReAct distinction unclear | MEDIUM | Steps 2 (Market Bias) and 4 (Structure) use "Deliberation" while Steps 5 (S/R) and 7 (SMC) use "ReAct." The distinction between these two loop types is never explained. In standard AI agent literature, Deliberation involves planning before acting, while ReAct interleaves reasoning and acting. For these trading steps, the practical difference is unclear. |
| L4 | Event-driven loop specification missing | MEDIUM | Steps 6, 9, 14, 15 are "event-driven" but the event system is only partially defined. The architecture mentions event types (ON_LEVEL_APPROACH, ON_LIQUIDITY_SWEEP, etc.) but doesn't specify the event bus, message format, or priority handling for concurrent events. |
| L5 | Reflection loop output undefined | MEDIUM | Step 16 uses "Reflection" but the reflection process — how the agent compares predicted vs. actual outcomes, what constitutes a "lesson," how lessons translate to parameter changes — is described conceptually but lacks algorithmic specification. |

**What the loop definitions should contain:**

For each loop type, the implementation needs:
```
LOOP_TYPE:
  - Trigger: What starts the loop
  - Max iterations: Hard cap
  - Convergence: When to stop (e.g., confidence > 0.8, no new information)
  - Timeout: Maximum wall-clock time
  - On timeout: What to do (use last result, default, abort)
  - State: What persists between iterations
  - Output: What the loop produces
```

### Verdict: Loop types are named but lack implementation specifications. This is the most significant architectural gap. Without defined termination conditions and iteration limits, the system cannot be implemented deterministically.

---

## 4. Market Regime Handling

### Result: PASS — Comprehensive regime coverage

The strategy handles four market regimes explicitly:

| Regime | Detection | Strategy Adjustment | Source |
|--------|-----------|-------------------|--------|
| **Trending Bull** | HMM state 0, ADX > 25, HH/HL structure | Wider TPs, trail with structure, RSI oversold at 40 | Steps 2, 4, 8 |
| **Trending Bear** | HMM state 1, ADX > 25, LH/LL structure | Wider TPs, trail with structure, RSI overbought at 60 | Steps 2, 4, 8 |
| **Ranging/Chop** | HMM state 2, ADX < 20, chop_score > 0.6 | Mean reversion, tight TPs, reduce size 0.6x | Steps 2, 4, 8 |
| **Transitional** | ADX 20-25, regime_confidence < 0.7 | Standard parameters, higher confirmation required | Steps 2, 4 |

**Regime-dependent adjustments verified:**
- ✅ Position sizing: `regime_mult` = 1.2 (trending), 1.0 (normal), 0.6 (ranging) — Step 11
- ✅ RSI thresholds: Adaptive by regime (30/70 ranging, 40/80 bull trend, 20/60 bear trend) — Step 8
- ✅ Stop loss: Volatility-adaptive buffer (0.35-0.75 × ATR) — Step 12
- ✅ Take profit: Session × volatility × regime matrix — Step 13
- ✅ Trade management: Dynamic R-multiple triggers by regime — Step 14
- ✅ Conflict resolution: Fundamentals vs. technicals weighting by regime — Step 2

**Gap:**

| # | Gap | Severity | Description |
|---|-----|----------|-------------|
| R1 | Regime transition handling | MEDIUM | When the HMM detects a regime change mid-trade, the management loop (Step 14) should adjust parameters. The document mentions "reassess TP/SL levels" in the monitoring cycle but doesn't specify the transition logic — e.g., if a trade was entered in a trending regime and the regime shifts to ranging, should the TP be tightened immediately? The decision matrix for in-trade regime shifts is missing. |

### Verdict: Market regime handling is comprehensive. One gap in mid-trade regime transition logic.

---

## 5. Edge Cases

### Result: PASS with HIGH issues in two areas

**Edge cases covered:**

| Edge Case | Handling | Quality |
|-----------|----------|---------|
| **High-impact news (NFP, FOMC)** | Event proximity check in Risk Gate, pre-news management protocol, 30-min blackout | ✅ Comprehensive |
| **Black swan events** | Dedicated sentinel agent, VIX spike detection, auto-close protocol, <1s response | ✅ Excellent |
| **Session transitions** | Session state machine with 7 states, transition rules defined | ✅ Good |
| **Weekend gaps** | Friday close protocol, Monday gap assessment | ✅ Good |
| **Correlation blowup** | Correlation watcher agent, max effective exposure 6R, auto-reduce alerts | ✅ Good |
| **Broker disconnect** | Retry once, alert human, broker-side stops as safety net | ✅ Good |
| **Stale data** | Timestamp checks, cached fallback, confidence reduction | ✅ Good |
| **Loss streaks** | Circuit breaker at 3 consecutive losses, 50% size reduction | ✅ Good |
| **Max drawdown** | 10% alert + reduce, 15% flatten all | ✅ Good |
| **Spread anomalies** | 3x spread = reject trade | ✅ Good |

**Issues:**

| # | Issue | Severity | Description |
|---|-------|----------|-------------|
| E1 | Black swan auto-close execution risk | HIGH | The document says "auto-execute if configured for black swan protocol" — closing all positions via market orders during a liquidity crisis can result in catastrophic slippage. The 2015 CHF flash crash saw fills 2000+ pips from pre-crash levels. The protocol should include: (a) attempt close, (b) if slippage > 5x normal, switch to hedge (open opposite positions) rather than market close, (c) contact broker immediately. |
| E2 | Session transition atomicity | HIGH | The session state machine has overlapping sessions (e.g., London 08:00-16:00 and London-NY Overlap 13:00-16:00). The `get_current_session()` function returns a single session based on UTC hour, but at 13:00 UTC, both London and Overlap are active. The function returns OVERLAP, which has different parameters than London. If a trade was entered during "pure London" (09:00-13:00) with London parameters, and the session shifts to Overlap at 13:00, the management parameters change mid-trade. This transition is not handled. |
| E3 | Holiday/DST handling | MEDIUM | Session times are hardcoded in UTC. DST transitions shift the effective market hours (e.g., US DST changes NY open from 13:00 to 12:00 UTC). No mechanism exists to detect or adjust for DST. Similarly, bank holidays reduce liquidity but the system doesn't account for them. |
| E4 | Multiple simultaneous signals | MEDIUM | What happens when Steps 5-9 produce conflicting signals simultaneously (e.g., S/R says bullish, RSI says bearish, SMC is neutral)? The confluence scorer handles this mathematically (lower score = lower grade) but the *decision logic* for when signals explicitly contradict is not defined beyond the score. |
| E5 | On-chain data availability | LOW | Step 6 includes on-chain data for crypto, but the primary strategy targets forex (MT5). The on-chain agent should gracefully handle "not applicable" without scoring 0 and penalizing the liquidity score. |

### Verdict: Edge case coverage is strong. Two HIGH issues (black swan execution, session transition atomicity) need resolution before production.

---

## 6. Implementability as a Deterministic System

### Result: HIGH issues — Partially deterministic

The strategy mixes deterministic and non-deterministic components:

**Deterministic components (implementable now):**
- ✅ Confluence scoring (Layer 1→2→3 pipeline) — pure arithmetic
- ✅ Position sizing (multiplier stack) — formula-based
- ✅ Risk Gate (11 boolean checks) — rule-based
- ✅ Session detection (UTC hour mapping) — lookup table
- ✅ Stop loss calculation (ATR buffer formula) — arithmetic
- ✅ RSI calculation, ATR, ADX — standard indicators
- ✅ Swing detection (adaptive lookback algorithm) — deterministic
- ✅ BOS/CHoCH detection — rule-based state machine
- ✅ Order block detection — algorithmic (impulse + lookback)
- ✅ FVG detection — gap comparison (candle[i].low > candle[i-2].high)
- ✅ Trailing stop logic — rule-based state transitions
- ✅ Time-based stops — clock comparison
- ✅ Correlation adjustment — matrix multiplication

**Non-deterministic components (need specification):**
- ❌ HMM regime detection — depends on training data, random_state, and retraining schedule
- ❌ FinBERT sentiment — model inference is deterministic per-input but model updates change outputs
- ❌ LLM reasoning (DeepSeek/Qwen in Step 1) — inherently non-deterministic
- ❌ XGBoost/LightGBM classifiers (S/R, sweep, pattern) — deterministic per-model but retraining changes behavior
- ❌ RL agents (TP optimization, management) — non-deterministic by design
- ❌ CNN pattern recognition — deterministic per-model but retraining changes behavior
- ❌ "Adaptive consensus" weight updates — algorithm specified but convergence behavior depends on data

| # | Issue | Severity | Description |
|---|-------|----------|-------------|
| I1 | LLM in the critical path | HIGH | Step 1 uses LLM (DeepSeek/Qwen) for "Chain-of-Thought reasoning" on central bank statements. LLM inference is non-deterministic (different outputs for same input across runs), has variable latency (1-30s), and can hallucinate. For a trading system where Step 1 feeds into all downstream steps, this is a reliability risk. **Recommendation:** Use LLM for analysis but cache results. Re-run only on new data. Add a deterministic fallback (FinBERT + rule-based interpretation) if LLM is slow or fails. |
| I2 | Retraining schedule ambiguity | MEDIUM | Multiple components have "retrain weekly/monthly" but no specification of: (a) what triggers retraining, (b) how to validate the new model is better than the old, (c) rollback mechanism if new model underperforms. A bad retrain could silently degrade performance. |
| I3 | "Adaptive consensus" weight updates | MEDIUM | The `update_agent_weights()` function in the architecture document blends 70% recent accuracy with 30% historical. But the update frequency, minimum sample size for "recent" accuracy, and bounds (0.05-0.40) need to be tuned. If weights oscillate, the system becomes unstable. |
| I4 | Order execution non-determinism | LOW | Market orders may fill at different prices depending on liquidity, spread, and latency. Limit orders may not fill at all. The system accounts for slippage but the execution path is inherently non-deterministic. This is acceptable — it's a feature of markets, not a system flaw. |

### Verdict: The core pipeline (scoring, sizing, risk gate, execution) is deterministic. The AI/ML components introduce non-determinism that must be managed with caching, fallbacks, and validation gates.

---

## 7. Summary of All Issues

### CRITICAL (3)

| # | Issue | Location | Fix Required |
|---|-------|----------|--------------|
| C1 | Loop types (ReAct, Deliberation, Reflection) undefined — no termination conditions, iteration limits, or timeout behavior | Architecture §12, all step documents | Define each loop type with trigger, max iterations, convergence, timeout, fallback |
| C2 | LLM in critical path of Step 1 with no deterministic fallback | Step 1 §1.2/1.3 | Add FinBERT + rule-based fallback; cache LLM results; set hard timeout (5s) |
| C3 | Black swan auto-close during liquidity crisis can cause catastrophic slippage | Step 15 §15 | Add hedge fallback, slippage circuit breaker, broker contact protocol |

### HIGH (5)

| # | Issue | Location | Fix Required |
|---|-------|----------|--------------|
| H1 | Session transition atomicity — overlapping sessions change management parameters mid-trade | Step 3 §3.3 | Define session transition rules for in-trade positions; lock parameters at entry |
| H2 | SMC normalization denominator is theoretical max (250) not practical max (~200-220) | fix_confluence_scoring.md §3.3 | Accept as conservative bias OR adjust denominator to 220 |
| H3 | No model retraining validation or rollback mechanism | Steps 1, 2, 4, 5, 6, 7, 8, 9, 16 | Add A/B testing: run old + new model in parallel, compare, then switch |
| H4 | Deliberation vs. ReAct loop distinction unexplained | Architecture §12 | Define specific behavioral differences or consolidate to one type |
| H5 | Event-driven loop event bus unspecified | Steps 6, 9, 14, 15 | Define message queue (ZeroMQ/Redis), priority levels, concurrency handling |

### MEDIUM (8)

| # | Issue | Location | Fix Required |
|---|-------|----------|--------------|
| M1 | Step 16 feedback loop timing and trigger logic underspecified | Step 16, Architecture §9 | Define exact triggers (trade count? time? performance threshold?) |
| M2 | News/Fundamental score double-counted (direct 0.05 weight + indirect via bias) | fix_confluence_scoring.md §5.1 | Accept as negligible (0.05) or remove direct news weight |
| M3 | Kill Zone binary cap too restrictive for Asian session strategies | fix_confluence_scoring.md §5.3 | Add session-specific kill zone logic (Asian range trading = valid) |
| M4 | Regime transition mid-trade management rules missing | Step 14 | Add regime-change decision matrix for open positions |
| M5 | DST/holiday handling absent | Step 3 | Add calendar service with DST transitions and bank holidays |
| M6 | Conflicting simultaneous signals — decision logic beyond scoring | Steps 5-9, Confluence | Define explicit conflict resolution (e.g., higher-TF signal wins) |
| M7 | On-chain data scoring penalty for forex instruments | Step 6 | Make on-chain category conditional (skip for forex, score for crypto) |
| M8 | Adaptive weight oscillation risk in closed learning loop | Architecture §9 | Add hysteresis (don't change weight by more than 0.02 per week) |

### LOW (2)

| # | Issue | Location | Fix Required |
|---|-------|----------|--------------|
| L1 | Step 9 → Step 10 direct link implied but connection is via confluence scorer | Step 9 §9.5 | Clarify in documentation |
| L2 | Architecture file references non-existent agent communication protocol details | Architecture §12 | Document ZeroMQ message format and routing |

---

## 8. Loop System Detailed Review

### Loop Timing Matrix (Verified)

| Loop | Frequency | Steps Affected | Trigger | Termination |
|------|-----------|---------------|---------|-------------|
| **Tick** | ~1s | 6 | New tick | Continuous (no termination) |
| **Candle (M15)** | 15min | 5,6,7,8,9,13,14,15 | Candle close | Single pass |
| **Session** | 4-8h | 3,5,6 | Session boundary | Single pass |
| **Daily** | 24h | 1,2,3,4,5,7,16 | End of day | Single pass |
| **Weekly** | 7d | 1,2,4,7,8,10,11,16 | Sunday | Single pass |
| **Monthly** | 30d | ALL | Month end | Single pass |
| **Post-Trade** | Per trade | 7,8,9,10,13,14,15,16 | Position close | Single pass |

**Issue:** Most loops are "single pass" (execute once per trigger), which is deterministic. But the tick loop and candle loop can overlap — if a tick event triggers Step 6 processing while the M15 candle close triggers Step 7, and both try to update the confluence scorer simultaneously, there's a race condition.

**Recommendation:** Use a message queue with sequential processing for the confluence scorer. Signal agents can compute in parallel, but the scorer processes signals sequentially.

### Reflection Loop (Step 16) — Detailed Analysis

The reflection loop is the most complex and least defined:

```
CURRENT (Vague):
  Trade closes → Record data → "Analyze" → "Extract lessons" → "Update strategy"

NEEDS (Specific):
  Trade closes → 
    1. Record trade data to database (deterministic)
    2. Calculate R-multiple, MAE, MFE (deterministic)
    3. Compare to similar historical trades (query DB, deterministic)
    4. If trade_count_since_last_review >= 20: (deterministic trigger)
       a. Calculate rolling win rate, expectancy per setup type (deterministic)
       b. Compare to previous period (deterministic)
       c. If expectancy dropped > 15%: flag for review (deterministic)
       d. Generate weight adjustment proposals (deterministic formula)
       e. Apply adjustments IF auto-approved OR queue for human review
    5. If weekly: retrain ML models with validation gate (semi-deterministic)
```

### Verdict: Loop timing is well-structured. The reflection loop needs algorithmic specification. Race conditions in parallel signal processing need addressing.

---

## 9. Recommendations — Priority Order

### Immediate (Before Implementation)

1. **Define all loop types** with trigger, max iterations, convergence, timeout, and fallback. This is the #1 blocker.
2. **Add LLM timeout + deterministic fallback** for Step 1. Cache results. Don't let LLM latency block the pipeline.
3. **Define session transition rules** for in-trade positions. Lock management parameters at entry or explicitly define how they change.
4. **Add black swan hedge fallback** — don't just market-close during liquidity crisis.

### Before Production

5. **Add model retraining validation** — A/B test, rollback mechanism, minimum sample size.
6. **Specify the event bus** — ZeroMQ or Redis, message format, priority, concurrency.
7. **Handle DST/holidays** — calendar service.
8. **Add hysteresis to adaptive weights** — max 0.02 change per week.

### Post-Launch Improvements

9. **Refine SMC normalization** — consider practical max (220) vs theoretical (250).
10. **Add session-specific kill zone logic** — Asian range trading should not be penalized.
11. **Implement regime transition management** — decision matrix for mid-trade regime shifts.

---

## 10. Implementation Readiness Score

| Component | Readiness | Notes |
|-----------|-----------|-------|
| Step 1 (Fundamental) | 70% | Needs LLM fallback, caching |
| Step 2 (Market Bias) | 85% | HMM implementation clear, needs retraining spec |
| Step 3 (Session) | 80% | Needs DST/holiday handling, transition rules |
| Step 4 (Structure) | 90% | Well-defined algorithms |
| Step 5 (S/R) | 85% | ML model needs training data pipeline |
| Step 6 (Liquidity) | 75% | Order flow data availability varies by broker |
| Step 7 (SMC) | 90% | Algorithmic detection well-specified |
| Step 8 (RSI) | 90% | Standard indicators + adaptive logic clear |
| Step 9 (Candlestick) | 85% | Pattern detection clear, ML optional |
| Step 10 (Entry) | 80% | Confluence scorer ready, entry logic needs spec |
| Step 11 (Sizing) | 95% | Formula-based, well-defined |
| Step 12 (Risk Gate) | 95% | 11 boolean checks, infrastructure-level |
| Step 13 (TP) | 80% | Partial close framework clear, RL agent is future work |
| Step 14 (Management) | 75% | Dynamic rules defined, regime transitions missing |
| Step 15 (Exit) | 85% | Comprehensive conditions, black swan needs hedge fallback |
| Step 16 (Journal) | 70% | Schema defined, reflection algorithm underspecified |
| Confluence Scoring | 95% | Fixed, verified, implementation-ready |
| Loop System | 60% | Timing defined, loop types undefined |
| Agent Architecture | 75% | Hierarchy clear, communication protocol incomplete |

**Overall Readiness: 82%** — Implementable for core pipeline (Steps 4-12), needs work for AI/ML components and loop systems.

---

## Appendix A: Confluence Scoring Verification

Re-deriving the worked example from fix_confluence_scoring.md:

```
Input:
  SR_raw=72, Liq_raw=68, SMC_raw=80, RSI_raw=33, Candle_raw=70
  KZ=true, Vol_raw=70, News_raw=85, SMC_max=250

Layer 2 (Normalize):
  SR    = 72/100 = 0.72
  Liq   = 68/100 = 0.68
  SMC   = min(80/250*100, 100)/100 = min(32, 100)/100 = 0.32
  RSI   = 33/100 = 0.33
  Candle= 70/100 = 0.70
  KZ    = 1.0
  Vol   = 70/100 = 0.70
  News  = 85/100 = 0.85

Layer 3 (Weighted):
  Score = 0.32×0.25 + 0.68×0.20 + 1.00×0.15 + 0.70×0.15
        + 0.72×0.10 + 0.33×0.05 + 0.70×0.05 + 0.85×0.05
  
  = 0.080 + 0.136 + 0.150 + 0.105 + 0.072 + 0.017 + 0.035 + 0.043
  = 0.638

Gate check: SMC=0.32≠0, Liq=0.68≠0, KZ=1.0≠0 → No cap applied

Grade: 0.638 → B (0.50-0.64) → Reduced trade at 0.5% risk ✅
```

**Verification: PASSED.** Arithmetic is correct.

---

## Appendix B: Data Contract Completeness

| Contract | Fields Verified | Missing Fields |
|----------|----------------|----------------|
| Step 1 → Step 2 | All 7 fields defined | None |
| Step 2 → Steps 3, 5-9 | All 7 fields defined | None |
| Step 3 → Steps 5-9 | All 5 fields defined | `optimal_window` logic unspecified |
| Step 4 → Steps 2, 5-9 | All 7 fields defined | None |
| Steps 5-9 → Scorer | All 8 fields defined | `ttl_seconds` handling on expiry unspecified |
| Scorer → Steps 10-12 | All 5 fields defined | None |
| Step 12 → Execution | All 10 fields defined | `ttl_seconds` handling on expiry unspecified |

---

*Review completed by Strategy & Loops Review Agent — 2026-07-11*
