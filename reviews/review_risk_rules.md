# Risk Rules Review — Alpha Stack

**Date:** 2026-07-11
**Reviewer:** Risk Rules Review Agent
**Scope:** Validate risk management rules across architecture_risk.md, fix_confluence_scoring.md, strategy_enhancement_steps9to12.md, strategy_enhancement_steps13to16.md
**Status:** COMPLETE — 6 inconsistencies found, 10 gaps identified

---

## 1. Risk Limits Consistency: 2% per trade, 6% total, 4% daily

### Verdict: ⚠️ MOSTLY CONSISTENT — 2 inconsistencies

| Document | Per-Trade | Total Exposure | Daily Loss | Consistent? |
|----------|-----------|---------------|------------|-------------|
| architecture_risk.md (hard caps) | 2.0% | 6.0% | 4.0% | ✅ Baseline |
| architecture_risk.md (F1 multipliers) | A+ = 1.50× on base | — | — | ⚠️ See below |
| fix_confluence_scoring.md | A+ = 1.5%, A = 1.0%, B = 0.5% | 6.0% cap | — | ✅ |
| steps 9-12 (§10.1) | A+ = 1.5-2%, A = 1%, B = 0.5% | 6.0% cap | 4.0% | ⚠️ See below |
| steps 13-16 | References 2%/6%/4% | — | — | ✅ |

**Inconsistency #1: A+ risk cap ambiguity**

- `fix_confluence_scoring.md` §5.4 states: **A+ → 1.5% risk (max)**
- `steps 9-12` §10.1 states: **A+ → Full position (1.5-2% risk)**
- `architecture_risk.md` §2.1.3 hard cap: **Max risk per trade = 2.0%**
- `architecture_risk.md` F1 for A+ = 1.50× — on a 1% base this yields 1.5%, but with F2 (regime 1.2×) or F4 (vol 1.5×), it could hit the 2% cap.

**Resolution needed:** The confluence scoring doc should state "A+ → up to 2% risk (subject to 4-factor model and 2% hard cap)" rather than capping at 1.5%. The 1.5% is the F1 contribution, not the final risk.

**Inconsistency #2: Risk tier for $7–$1K accounts**

The architecture risk doc defines account tiers starting at $1K. The system is described as scaling from "$7 to $100K+" (§1.1 design philosophy: "$7 account has ~46 trades before costs drain capital"), but there is no tier for accounts under $1K. At $7, a 1% risk = $0.07, which is below any broker's minimum trade size.

**Resolution needed:** Add a micro-account tier ($0–$1K) with explicit guidance on minimum viable account size and TCA-adjusted minimum R:R requirements.

---

## 2. Five-Stage Drawdown System Cascade

### Verdict: ✅ PROPERLY CASCADED — 1 minor issue

**Stage thresholds are consistent across all documents:**

| Stage | Threshold | Size Multiplier | Max Positions | Consistent? |
|-------|-----------|----------------|---------------|-------------|
| GREEN | 0–3% | 1.00× | 5 | ✅ |
| YELLOW | 3–7% | 0.50× | 3 | ✅ |
| ORANGE | 7–12% | 0.25× | 2 | ✅ |
| RED | 12–18% | 0.10× | 1 | ✅ |
| BLACK | >18% | 0.00× | 0 | ✅ |

**Escalation cascade:** Automatic, no human intervention. ✅
**De-escalation cascade:** Requires sustained recovery with minimum wait times. ✅

**Minor issue: Recovery protocol comment vs. code mismatch**

In `architecture_risk.md` §3.4, the recovery protocol defines:
- BLACK → RED: Manual restart + 24h paper trading (wait 24h)
- RED → ORANGE: DD < 12% for 48h (wait 48h)
- ORANGE → YELLOW: DD < 7% for 24h (wait 24h)
- YELLOW → GREEN: DD < 3% for 12h (wait 12h)

The code's `_handle_stage_transition` method handles escalation but **does not implement de-escalation logic**. The recovery protocol is documented but not coded. This is a gap between design and implementation — the de-escalation logic with sustained-condition checks needs to be added to the `DrawdownLimitManager` class.

---

## 3. Four-Layer Circuit Breaker System

### Verdict: ✅ CORRECT — All 4 layers properly implemented

**Layer 1: Position Level (millisecond response)**

| Breaker | Threshold | Action | Reset | Correct? |
|---------|-----------|--------|-------|----------|
| Hard stop | -2% per trade | Close position | Auto (next candle) | ✅ |
| Trailing stop | -3% from peak | Close position | Auto | ✅ |
| Slippage | >0.5% | Pause entries | Auto (5 min) | ✅ |
| Spread | >3x normal | Block orders | Auto (normalize <1.5x) | ✅ |
| Crisis time | >48h in crisis | Close position | Auto | ✅ |

**Layer 2: Portfolio Level (second-level response)**

| Breaker | Threshold | Action | Reset | Correct? |
|---------|-----------|--------|-------|----------|
| Daily loss | -4% | Pause 24h | Auto (next day) | ✅ |
| Weekly loss | -8% | Reduce 50% | Manual + 24h paper | ✅ |
| Monthly loss | -12% | Full de-risk | Manual + reassess | ✅ |
| Max drawdown | -18% | System halt | Manual restart | ✅ |
| Exposure | >6% | Block trades | Auto | ✅ |
| Margin | >30% | Block trades | Auto | ✅ |

**Layer 3: Regime Level (market-condition response)**

| Breaker | Threshold | Action | Reset | Correct? |
|---------|-----------|--------|-------|----------|
| VIX caution | >30 | Reduce 50% | Auto (VIX <30 for 4h) | ✅ |
| VIX high | >50 | Reduce 75% | Auto | ✅ |
| VIX extreme | >70 | Cash only | Auto | ✅ |
| Correlation spike | >0.80 | Hedging mode | Auto (<0.6 for 24h) | ✅ |
| Regime uncertain | >5 days | Defensive mode | Auto | ✅ |

**Layer 4: System Level (infrastructure response)**

| Breaker | Threshold | Action | Reset | Correct? |
|---------|-----------|--------|-------|----------|
| Connectivity | >30s disconnect | Close broker positions | Auto (reconnect + 60s) | ✅ |
| Order rejection | >10% rate | Pause trading | Manual review | ✅ |
| Latency | >10x normal | Cancel orders | Auto (5 min normal) | ✅ |
| Event bus failure | Failure | Safe mode, close all | Manual | ✅ |

**All layers are independent and can halt trading without consulting other layers.** ✅

**Note:** Layer 3 (VIX thresholds) and Black Swan detector (VIX spike) use different VIX metrics — static level vs. hourly change rate. This is intentional: Layer 3 responds to absolute VIX levels (regime), while Black Swan detects rapid VIX changes (crisis onset). They are complementary, not conflicting.

---

## 4. Position Sizing Formula Mathematical Correctness

### Verdict: ✅ FORMULAS CORRECT — 2 edge cases noted

**Kelly Criterion:**
```
Full Kelly: f* = (bp - q) / b
  b=1.8, p=0.68, q=0.32
  f* = (1.8 × 0.68 - 0.32) / 1.8 = (1.224 - 0.32) / 1.8 = 0.904 / 1.8 = 0.5022 ✅
Quarter Kelly: 0.5022 / 4 = 0.1256 ✅
```

**4-Factor Model:**
```
FINAL_RISK = Base_Risk × F1 × F2 × F3 × F4
  Base_Risk = Account × min(Kelly, 0.02)
  All factors bounded: F1 [0, 1.5], F2 [0.2, 1.2], F3 [0, 1.1], F4 [0.25, 1.5]
  Maximum theoretical: 2% × 1.5 × 1.2 × 1.1 × 1.5 = 5.94%
  Hard cap enforced: min(adjusted_risk, balance × 0.02) ✅
```

**Correlation-Adjusted Sizing:**
```
Combined_Risk = Σ(Individual_Risks) × (1 + max_correlation × 0.5)

Example from doc:
  EUR/USD: 1.0%, GBP/USD: 1.0%, Corr: 0.85
  Combined: 2.0% × (1 + 0.85 × 0.5) = 2.0% × 1.425 = 2.85% ✅
  Target: 2.5%, each reduced to 0.88%
  Check: 1.76% × 1.425 = 2.508% ≈ 2.5% ✅
```

**Edge Case #1: Correlated exposure limit mismatch**

The worked example in §2.1.4 uses **2.5%** as the correlated exposure limit, but §2.1.3 defines `MAX_CORRELATED_EXPOSURE = 0.03` (**3.0%**). The example should either use 3.0% as the limit, or the hard cap should be changed to 2.5%. This is a documentation inconsistency, not a math error.

**Edge Case #2: Volatility factor lower bound**

`_volatility_factor` is bounded `[0.25, 1.50]`, but the documentation in §2.1.2 Factor 4 only mentions the upper cap of 1.5. The lower bound of 0.25 is only in code. Should be documented explicitly.

---

## 5. Risk Management Scaling: $7 to $100K+

### Verdict: ⚠️ PARTIAL — Scaling documented for $1K+ but not for micro-accounts

**Account Tier Scaling (from architecture_risk.md §2.1.5):**

| Account Size | Max Risk/Trade | Max Exposure | Kelly | Viable? |
|-------------|---------------|-------------|-------|---------|
| $1K–$5K | 1.0% | 3.0% | 1/5 Kelly | ✅ Documented |
| $5K–$25K | 1.5% | 4.5% | Quarter Kelly | ✅ Documented |
| $25K–$100K | 1.5% | 5.0% | Quarter Kelly | ✅ Documented |
| $100K–$500K | 1.0% | 4.0% | 1/5 Kelly | ✅ Documented |
| $500K+ | 0.75% | 3.0% | Conservative | ✅ Documented |
| **$0–$1K** | **???** | **???** | **???** | ❌ **NOT DOCUMENTED** |

**Scaling strengths:**
- Percentage risk decreases as account grows (absolute $ risk still increases). ✅
- TCA-aware sizing blocks trades when costs exceed thresholds. ✅
- Minimum R:R increases as cost-to-account ratio rises. ✅

**Scaling weakness:**
The system references "$7 accounts" in the design philosophy but provides no guidance for accounts below $1K. At $7:
- 1% risk = $0.07 (below any broker minimum)
- Spread costs on EUR/USD (~1 pip = $0.10 on 0.01 lot) exceed the account's viable trade size
- The TCA section warns at >1.5% and blocks at >3.0%, but doesn't define what the minimum viable account size is

**Recommendation:** Add explicit minimum viable account guidance:
```
$0–$500:  NOT VIABLE — costs dominate, recommend paper trading
$500–$1K: MARGINAL — only micro-lots (0.01), max 1 position, min R:R 5:1
$1K–$5K:  VIABLE — reduced sizing per tier table
```

---

## 6. Risk Management Gaps

### Gap 1: Correlated Exposure Limit — Documentation Conflict
**Severity:** Medium
**Location:** architecture_risk.md §2.1.3 vs §2.1.4
**Issue:** Hard cap says 3.0% correlated exposure, worked example uses 2.5%
**Fix:** Unify to one value. Recommend 2.5% (more conservative) or update the example to use 3.0%.

### Gap 2: A+ Risk Cap Ambiguity
**Severity:** Medium
**Location:** fix_confluence_scoring.md §5.4 vs architecture_risk.md §2.1.2
**Issue:** Confluence doc caps A+ at 1.5%, but architecture allows up to 2% with multipliers
**Fix:** Update confluence doc to state "A+ → up to 2% (subject to 4-factor model and hard cap)".

### Gap 3: Drawdown De-escalation Not Coded
**Severity:** High
**Location:** architecture_risk.md §3.3 (code) vs §3.4 (recovery protocol)
**Issue:** Recovery protocol is documented but the `DrawdownLimitManager` class only implements escalation, not de-escalation. The `update()` method never transitions back to a lower stage.
**Fix:** Add de-escalation logic to `update()` that checks sustained recovery conditions before allowing stage transitions.

### Gap 4: Micro-Account Tier Missing
**Severity:** Medium
**Location:** architecture_risk.md §2.1.5
**Issue:** No tier for accounts under $1K despite "$7 account" design philosophy
**Fix:** Add explicit $0–$1K tier with minimum viable account guidance.

### Gap 5: Kelly Minimum Data Requirement — Inconsistency
**Severity:** Low
**Location:** architecture_risk.md §2.1.1 vs §2.2 code
**Issue:** Documentation says "minimum 100-trade sample" but code uses `len(recent_trades) < 30` as the threshold, returning a conservative 1% default.
**Fix:** Unify — either change doc to say 30 or change code to 100. Recommend 30 (more practical for new systems).

### Gap 6: Crypto-Specific Risk Framework Incomplete
**Severity:** Medium
**Location:** architecture_risk.md (throughout)
**Issue:** The system is designed for forex+crypto but crypto-specific risks are underdeveloped:
- Max exchange exposure (5%) is mentioned but no framework for exchange failure cascades
- No stablecoin depeg risk management beyond black swan detection
- No gas fee / network congestion impact on execution
- Max 3 crypto positions mentioned but not enforced in code's `MAX_CONCURRENT_POSITIONS = 5`
**Fix:** Add dedicated crypto risk parameters section with exchange diversification rules, stablecoin exposure limits, and network-aware execution logic.

### Gap 7: Time-of-Day Multiplier Missing from Architecture
**Severity:** Low
**Location:** architecture_risk.md §2.1.2 vs steps 9-12 §11
**Issue:** Steps 9-12 defines a Time-of-Day multiplier (London/NY overlap 1.2×, Asian 0.7×) but architecture_risk.md's 4-factor model does not include it. The architecture has 4 factors (Confluence, Regime, Performance, Volatility) — time-of-day is a 5th factor in steps 9-12.
**Fix:** Either add as a 5th factor in the architecture or explicitly state it's absorbed into the Regime factor.

### Gap 8: Weekend Gap Risk Not in Circuit Breakers
**Severity:** Low
**Location:** architecture_risk.md §4 vs steps 13-16 §15
**Issue:** Steps 13-16 has detailed weekend gap management rules, but the circuit breaker system has no weekend-specific breaker. Friday close logic is only in the exit conditions doc.
**Fix:** Add a weekend-risk check to Layer 2 (portfolio level) circuit breakers.

### Gap 9: Opposite-Direction Correlated Positions
**Severity:** Low
**Location:** architecture_risk.md §2.1.4
**Issue:** Correlation adjustment only considers same-direction positions. Opposite-direction correlated positions (e.g., EUR/USD long + USD/CHF long, correlation -0.90) are natural hedges but the system doesn't recognize or credit them.
**Fix:** Add net exposure calculation that accounts for opposing correlations as hedges, potentially allowing slightly larger positions when natural hedges exist.

### Gap 10: Stress Test Scenarios Don't Cover All Asset Classes
**Severity:** Low
**Location:** architecture_risk.md §6.2
**Issue:** Historical scenarios cover forex (CHF 2015, Asian 1997) and crypto (LUNA 2022) but hypothetical scenarios are light on crypto-specific risks (e.g., DeFi protocol failure, Layer-1 outage, regulatory ban).
**Fix:** Add hypothetical scenarios for crypto-native risks alongside the existing forex/equity scenarios.

---

## Summary Table

| # | Check | Verdict | Issues |
|---|-------|---------|--------|
| 1 | Risk limits consistency (2%/6%/4%) | ⚠️ Mostly consistent | A+ cap ambiguity, micro-account tier missing |
| 2 | 5-stage drawdown cascade | ✅ Properly cascaded | De-escalation not coded |
| 3 | 4-layer circuit breaker system | ✅ Correct | All layers independent and complete |
| 4 | Position sizing math | ✅ Correct | Correlated limit mismatch (2.5% vs 3.0%) |
| 5 | Scaling $7–$100K+ | ⚠️ Partial | No tier for <$1K accounts |
| 6 | Risk management gaps | 10 gaps found | 1 high, 4 medium, 5 low severity |

---

## Priority Action Items

| Priority | Action | Effort |
|----------|--------|--------|
| **P0** | Implement drawdown de-escalation logic in `DrawdownLimitManager` | Medium |
| **P1** | Unify correlated exposure limit (2.5% or 3.0%) across all docs | Low |
| **P1** | Clarify A+ risk cap — update confluence scoring doc | Low |
| **P1** | Add micro-account tier ($0–$1K) with minimum viable guidance | Low |
| **P2** | Add crypto-specific risk parameters section | Medium |
| **P2** | Unify Kelly minimum data requirement (30 vs 100 trades) | Low |
| **P2** | Add time-of-day factor to architecture (or document absorption into regime) | Low |
| **P3** | Add weekend risk breaker to Layer 2 | Low |
| **P3** | Add opposite-direction correlation hedging logic | Medium |
| **P3** | Expand hypothetical stress test scenarios for crypto | Low |

---

## Overall Assessment

The Alpha Stack risk management architecture is **institutional-grade and well-designed**. The layered defense model (position → portfolio → regime → system) is robust. The 2%/6%/4% limits are consistently applied across documents. The math is correct.

The primary issues are **documentation inconsistencies** (not design flaws) and one **implementation gap** (drawdown de-escalation). The system handles the critical path correctly — trades that should be blocked will be blocked. The gaps identified are edge cases and completeness improvements, not structural weaknesses.

**Risk of the risk system failing: LOW.** The hard caps are truly hard. The circuit breakers are independent. The black swan detector runs on its own loop. The design philosophy of "survive first, profit second" is consistently implemented.

---

*Review completed by: Risk Rules Review Agent — Alpha Stack*
*Files reviewed: architecture_risk.md, fix_confluence_scoring.md, strategy_enhancement_steps9to12.md, strategy_enhancement_steps13to16.md*
