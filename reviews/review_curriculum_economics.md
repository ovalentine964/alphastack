# Curriculum Economics Verification Report

**Agent:** Economics Curriculum Verification Agent
**Date:** 2026-07-11
**Documents Reviewed:**
- `architecture_curriculum_economics.md` (Primary)
- `architecture_system.md` (System Architecture)
- `architecture_trading_engine.md` (Trading Engine)

---

## Executive Summary

| Criterion | Verdict | Score |
|-----------|---------|-------|
| All 14 ECO units mapped? | ✅ YES | 14/14 |
| Mappings accurate? | ⚠️ MOSTLY — 2 forced, 1 weak | 11/14 strong, 2 acceptable, 1 weak |
| Macro Signal Engine design? | ⚠️ GOOD but has redundancy | 7/10 |
| Forex Market Engine design? | ✅ SOLID | 8/10 |
| Curriculum drives code? | ⚠️ PARTIALLY — 8 modules exist, 16-step pipeline not curriculum-driven | 6/10 |
| Integration gaps? | ⚠️ SEVERAL — 6 critical gaps identified | See Section 6 |

**Overall Verdict:** The curriculum mapping is ambitious and largely well-done. All 14 ECO units are mapped, and most mappings are genuinely accurate. However, the curriculum architecture describes 8 modules that do NOT cleanly map to the actual 16-step VMPM trading pipeline. Several modules exist only as descriptions with no implementation in the trading engine. The curriculum is more of a theoretical overlay than a code-driving blueprint.

---

## 1. ECO Unit Mapping Completeness (14/14 ✅)

All 14 ECO units are mapped to specific Alpha Stack modules:

| # | ECO Unit | Module | Status |
|---|----------|--------|--------|
| 1 | ECO 101 (Micro) | Market Microstructure Engine | ✅ Mapped |
| 2 | ECO 102 (Macro) | Macro Signal Engine | ✅ Mapped |
| 3 | ECO 103 (Math I) | Portfolio Optimization Engine | ✅ Mapped |
| 4 | ECO 104 (Math II) | Dynamic Programming Engine (RL) | ✅ Mapped |
| 5 | ECO 201 (Int Micro) | Multi-Agent Coordinator | ✅ Mapped |
| 6 | ECO 205 (Int Macro) | Business Cycle / Regime Detection Engine | ✅ Mapped |
| 7 | ECO 209 (Money) | Forex Market Engine / Central Bank Watcher | ✅ Mapped |
| 8 | ECO 305/313 (Intl) | FX Model / Trade Flow Engine | ✅ Mapped |
| 9 | ECO 321 (Adv Micro) | General Equilibrium / Pricing Engine | ✅ Mapped |
| 10 | ECO 322 (Adv Macro) | DSGE / Policy Reaction Function Engine | ✅ Mapped |
| 11 | ECO 401 (Dev) | EM Sovereign Risk Module | ✅ Mapped |
| 12 | ECO 414/424 (Econometrics) | Signal Validation Engine | ✅ Mapped |
| 13 | ECO 421 (Pub Fin) | Fiscal Policy / Sovereign Credit Module | ✅ Mapped |
| 14 | ECO 422 (Industry) | Industry Analysis / Earnings Model Module | ✅ Mapped |

---

## 2. Mapping Accuracy Assessment (11/14 Strong)

### ✅ STRONG Mappings (Natural, non-contrived)

| ECO Unit | Why It's Strong |
|----------|----------------|
| **ECO 101** | Supply/demand → order book bid/ask is a direct, textbook mapping. Price elasticity → market impact (Almgren-Chriss) is quantitatively precise. Game theory bridge to ECO 201 is architecturally sound. |
| **ECO 102** | GDP/CPI/rates → macro factor model is the foundation of macro trading. Inflation surprise → forex signal is one of the highest-alpha trades in FX. Taylor Rule → rate expectation modeling is standard practice. |
| **ECO 103** | Matrix algebra → covariance matrix (σ²_p = w'Σw) is literally the same math. Lagrange multipliers → constrained portfolio optimization (cvxpy) is textbook. Eigenvalues → PCA for factor decomposition is canonical. |
| **ECO 205** | IS-LM → interest rate-output dynamics for currencies is standard macro-finance. Business cycle → regime-based trading (HMM) is well-established. Taylor Rule → policy prediction is direct. |
| **ECO 209** | Quantity theory (MV=PQ) → inflation forecasting for currencies is direct. Inflation targeting → CPI surprise trading is one of the most profitable FX strategies. Banking crises → systemic risk is real-world critical. |
| **ECO 305/313** | Exchange rate determination models (PPP, UIP, monetary model) → FX fair value engine is textbook. BOP → capital flow tracking is fundamental. Currency crisis models → early warning is directly applicable. |
| **ECO 322** | Stagflation detection → worst portfolio environment classifier is practical. Taylor Rule with time-varying parameters → Fed policy prediction is advanced but standard. Fiscal multiplier → currency impact model is real. |
| **ECO 414/424** | OLS → factor model estimation is THE core of quantitative finance. Cointegration → pairs trading engine is a direct, well-known application. Hypothesis testing → signal significance filter is essential. Bootstrap → backtest validation is best practice. Anti-data-mining (deflated Sharpe, FDR) → preventing false discoveries is critical. **This is the strongest mapping in the entire curriculum.** |
| **ECO 401** | Institutional quality → sovereign risk premium is directly measurable. Debt sustainability → sovereign credit model is standard (IMF DSA). Capital flight → crisis detection is real-world validated. |
| **ECO 421** | Public debt management → sovereign bond pricing is direct. Budget process → fiscal event trading is actionable. Tax revenue mobilization → fiscal capacity indicator is measurable. |
| **ECO 422** | Market concentration (HHI) → competitive moat scorer is quantitative. M&A → event-driven strategy is a real trading strategy. Barriers to entry → moat durability assessment is standard equity analysis. |

### ⚠️ ACCEPTABLE Mappings (Valid but somewhat stretched)

| ECO Unit | Concern |
|----------|---------|
| **ECO 201** | Intermediate micro concepts (utility maximization, budget constraints, indifference curves) are mapped to multi-agent coordination, but the connection is more conceptual than mechanical. The Nash Equilibrium → MARL bridge is strong, but the rest of ECO 201's content (income/substitution effects, production functions) feels like it's being fitted to the module rather than naturally flowing into it. The "Market structures → execution strategy classifier" mapping is valid but not uniquely tied to ECO 201 — any market practitioner would arrive at the same classification without studying intermediate micro. |
| **ECO 321** | Advanced micro concepts are mapped to general equilibrium pricing, which is correct in theory. However, "Walrasian general equilibrium → no-arbitrage conditions" is a conceptual analogy, not a computational one — the Alpha Stack doesn't actually solve a Walrasian equilibrium. The information asymmetry → PIN model mapping is strong, but quantum computing references (QAOA) are aspirational vapor. The welfare theorems → efficient frontier mapping is correct but already covered by ECO 103's portfolio optimization. |

### ❌ WEAK Mapping

| ECO Unit | Issue |
|----------|-------|
| **ECO 104** | Mathematics for Economists II is mapped to the "Dynamic Programming Engine (RL)," but the mapping is thin. The Bellman equation → RL (PPO/DQN) bridge is strong and genuine. However, the majority of ECO 104's content (difference equations, ODEs/SDEs, Black-Scholes PDE, convex sets, envelope theorem, implicit function theorem) does NOT drive Alpha Stack code. The Alpha Stack uses Black-Scholes as a pricing tool, not as a differential equation to solve. The convex optimization is already covered by ECO 103. The SDE/GBM connection to risk models is valid but not implemented in the described code. **Net: Only ~30% of ECO 104 content actually maps to code.** |

---

## 3. Macro Signal Engine Design Assessment (7/10 ⚠️)

### Strengths
- **Well-decomposed:** 6 sub-models (inflation, rate, cycle, fiscal, sovereign, FX) with clear inputs/outputs
- **Multi-ECO integration:** Correctly pulls from ECO 102, 205, 322, 401, 421
- **Data pipeline clarity:** Hot/warm/cold paths specified with concrete Redis keys
- **Signal aggregation:** Clear direction + confidence + regime output format

### Issues

**Issue 3.1: Redundancy with Forex Market Engine**
The Macro Signal Engine contains `self.fx_model = MultiModelFXForecaster()` fed by ECO 305/313. But the Forex Market Engine (Section 8.2) is a *separate* module also containing FX forecasting (PPP, UIP, monetary model). These two FX models overlap significantly:

```
MacroSignalEngine.fx_model      → MultiModelFXForecaster (ECO 305/313)
ForexMarketEngine.ppp_model     → PPPFairValue (ECO 305)
ForexMarketEngine.uip_model     → UIPDeviationTracker (ECO 209, 305)
```

**Recommendation:** Remove `fx_model` from Macro Signal Engine. The Macro Engine should produce macro *context* (inflation, rates, cycle phase, fiscal impulse, sovereign risk) that the Forex Engine consumes. The Forex Engine owns FX signal generation.

**Issue 3.2: Missing trade flow integration**
The Macro Signal Engine aggregates direction from inflation, rate expectations, cycle, fiscal, and sovereign — but does NOT incorporate capital flows or BOP data, which is one of the highest-alpha macro signals for FX (covered in ECO 305/313). This data should flow from the Forex Engine or be a direct input.

**Issue 3.3: Regime detection is split**
The `cycle_detector` (ECO 205) and `fx_model` regime classification (ECO 305) both do regime detection but use different models (HMM vs. de facto regime classifier). The system lacks a unified regime state that both engines reference.

### Verdict
The Macro Signal Engine is well-designed for its core purpose but has architectural redundancy with the Forex Market Engine. The two engines need clearer boundary definitions and a shared regime state.

---

## 4. Forex Market Engine Design Assessment (8/10 ✅)

### Strengths
- **Clean separation:** 7 components each owning a specific concept (PPP, UIP, CIP, regime, flows, CB, banking)
- **ECO 209 + 305/313 integration:** Correctly combines money/banking (ECO 209) with international econ (ECO 305/313)
- **Composite signal:** Weighted combination of 6 signals (PPP deviation, carry score, regime, flow direction, CB bias, systemic risk) is a robust approach
- **Central bank watcher:** FinBERT on Fed speak is the correct NLP application

### Issues

**Issue 4.1: No event-driven integration**
The Forex Market Engine's `generate_fx_signal()` is a pure function call. It doesn't subscribe to real-time events (CPI releases, rate decisions, BOP data). In the trading engine architecture, S1 (Fundamental Intelligence) handles event-driven macro, but the Forex Market Engine doesn't connect to S1's event pipeline.

**Issue 4.2: Missing microstructure layer**
The Forex Market Engine focuses on fundamental/flow signals but doesn't incorporate order book dynamics, spread analysis, or liquidity — which is where ECO 209's "Foreign Exchange Markets" concept (dealer networks, ECN/STP, bid-ask spreads) should map. This is currently handled by the separate Market Microstructure Engine (ECO 101), but the Forex Engine should consume microstructure signals.

**Issue 4.3: Carry trade implementation gap**
The UIP deviation tracker is described but the actual carry trade mechanics (funding rate monitoring, cost of carry calculation, risk-on/risk-off regime filtering) are not specified. ECO 209's "Interest Rate Channel" and "Exchange Rate Channel" concepts need more concrete implementation.

### Verdict
The Forex Market Engine is the best-designed module in the curriculum architecture. Its issues are integration-level, not design-level.

---

## 5. Does the Curriculum Drive the Code? (6/10 ⚠️)

### The Core Problem

The curriculum architecture describes **8 modules** (Macro Signal Engine, Forex Market Engine, Market Microstructure Engine, etc.), but the actual trading engine implements a **16-step VMPM pipeline** (S1-S16). These two structures do NOT align:

| Curriculum Module | VMPM Step(s) | Alignment |
|-------------------|--------------|-----------|
| Macro Signal Engine | S1 (Fundamental Intelligence) | ✅ Partial — S1 does macro analysis but isn't structured as the Macro Signal Engine |
| Forex Market Engine | No direct step | ❌ Not implemented in VMPM |
| Market Microstructure Engine | S6 (Liquidity) + S7 (SMC) | ⚠️ Partial — S6/S7 handle liquidity/SMC but not full microstructure |
| Portfolio Optimization Engine | S11 (Position Sizing) | ⚠️ Partial — S11 does sizing but not full MVO |
| Dynamic Programming Engine | S13 (Take Profit) RL agent | ⚠️ Partial — S13 has RL but not full DP engine |
| Multi-Agent Coordinator | Agent Orchestrator | ✅ Exists in system architecture |
| Regime Detection Engine | S2 (Market Bias) HMM | ⚠️ Partial — S2 has HMM but not full regime engine |
| Signal Validation Engine | S16 (Journal) analytics | ⚠️ Partial — S16 does some validation but not full econometric suite |

### What the Curriculum Adds That Isn't in the Trading Engine

| Curriculum Concept | In VMPM Pipeline? | Gap |
|-------------------|-------------------|-----|
| Inflation surprise trading (ECO 102) | S1 has sentiment but not explicit CPI surprise model | **Missing** |
| Taylor Rule calculator (ECO 205, 322) | Not implemented | **Missing** |
| PPP/UIP fair value (ECO 305/313) | Not implemented | **Missing** |
| Central bank communication parsing (ECO 209) | S1 has FinBERT but not CB-specific | **Missing** |
| Cointegration pairs trading (ECO 414/424) | Not implemented | **Missing** |
| OLS factor model estimation (ECO 414/424) | Not implemented | **Missing** |
| Bootstrap backtest validation (ECO 414/424) | Not implemented | **Missing** |
| DSGE-lite model (ECO 322) | Not implemented | **Missing** |
| EM sovereign risk scoring (ECO 401) | Not implemented | **Missing** |
| Fiscal policy impact model (ECO 421) | Not implemented | **Missing** |
| Industry concentration analysis (ECO 422) | Not implemented | **Missing** |
| General equilibrium pricer (ECO 321) | Not implemented | **Missing** |

### What the Trading Engine Has That Isn't in the Curriculum

| VMPM Step | ECO Coverage | Note |
|-----------|-------------|------|
| S4 (Market Structure) — BOS/CHoCH | None | Pure SMC/ICT methodology, no economics |
| S5 (S/R) — Fractal clustering, volume profile | None | Technical analysis, not economics-driven |
| S8 (RSI) — Adaptive momentum | None | Technical indicator |
| S9 (Candlestick) — Pattern recognition | None | Pattern recognition, not economics |
| S12 (Stop Loss) — ATR-based placement | None | Risk management technique |
| S14 (Trade Management) — Dynamic R-multiple | None | Position management technique |
| S15 (Exit Conditions) — Black swan protocol | None | Risk management technique |

### Verdict
The curriculum describes a theoretically sound mapping of economics → trading modules, but it does NOT describe how these modules integrate into the actual 16-step VMPM pipeline. The curriculum is an overlay, not a driver. The VMPM pipeline is driven by ICT/SMC trading methodology, not by economics coursework. The curriculum adds macro/fundamental depth that the VMPM pipeline currently lacks, but the wiring is incomplete.

---

## 6. Critical Integration Gaps

### Gap 1: Curriculum Modules Not Implemented in VMPM Pipeline 🔴 CRITICAL

**Problem:** The 8 curriculum modules exist as *descriptions* in `architecture_curriculum_economics.md` but have no corresponding implementation in `architecture_trading_engine.md`. The VMPM pipeline's S1 (Fundamental Intelligence) is the closest match but is a single step, not 8 separate engines.

**Impact:** The curriculum's value proposition — that economics knowledge drives trading decisions — is not realized in code.

**Recommendation:** Either:
- (A) Expand S1 into multiple sub-modules that implement the curriculum engines, OR
- (B) Add new VMPM steps (S1.1 through S1.8) for each curriculum engine, OR
- (C) Create a parallel "macro signal pipeline" that feeds into S10 (Confluence Engine) alongside the existing technical pipeline.

### Gap 2: No Econometric Validation Layer 🔴 CRITICAL

**Problem:** ECO 414/424 (Econometrics) is the highest-priority curriculum unit (marked CRITICAL), and the Signal Validation Engine is the most detailed module in the curriculum doc. But the trading engine has NO equivalent. S16 (Journal) does post-trade analytics but not pre-trade signal validation.

**Impact:** No OLS factor model estimation, no hypothesis testing, no cointegration testing, no bootstrap validation, no anti-data-mining framework. The system has no mathematical rigor for signal quality.

**Recommendation:** Implement the Signal Validation Engine as a gate between S10 (Confluence) and S11 (Position Sizing). Every proposed trade must pass econometric validation before execution.

### Gap 3: Forex Market Engine Has No Home in VMPM 🔴 CRITICAL

**Problem:** The Forex Market Engine (ECO 209 + 305/313) is described as a standalone module but doesn't correspond to any VMPM step. The VMPM pipeline is asset-class agnostic (it works on any pair), but the Forex Market Engine is FX-specific.

**Impact:** PPP fair value, UIP deviation, capital flow analysis, central bank parsing — none of these high-alpha signals are wired into the trading pipeline.

**Recommendation:** Create a "Macro Overlay" layer that sits between the data layer and S1, providing pair-specific macro signals that S1 consumes. For FX pairs, this would be the Forex Market Engine. For crypto, a different overlay.

### Gap 4: Regime Detection is Fragmented 🟡 HIGH

**Problem:** Regime detection appears in three places:
1. S2 (Market Bias) — HMM 3-state on returns/volatility
2. Macro Signal Engine — `cycle_detector` (HMM on PMI, yield curve, unemployment)
3. Forex Market Engine — `regime_classifier` (de facto FX regime: fixed/float/managed)

These are three separate models with three separate state spaces. There's no unified regime state.

**Impact:** The system could have conflicting regime signals (S2 says "bull trend" but macro engine says "contraction"). No resolution protocol exists.

**Recommendation:** Create a unified `RegimeState` object that aggregates all three regime signals with a conflict resolution protocol. Publish to Redis as `regime:unified:{symbol}`.

### Gap 5: Reflection Agent Not Wired to Trading Engine 🟡 HIGH

**Problem:** The curriculum maps ECO 414/424 to the Reflection Agent, which is described in `architecture_system.md` as the "Auditor Agent" (weekly reflection). But the trading engine's S16 (Journal) is a different agent with different responsibilities.

**Impact:** The econometric validation capabilities (OLS, diagnostics, hypothesis testing, bootstrap) described in the curriculum are not connected to any actual agent in the system.

**Recommendation:** Merge the Reflection Agent's econometric capabilities into S16 (Journal) or create a dedicated validation agent that runs between signal generation and trade execution.

### Gap 6: Aspirational vs. Implementable 🟡 MEDIUM

**Problem:** Several curriculum mappings reference technologies that don't exist or aren't practical:
- ECO 321: "Quantum (future QAOA)" — quantum computing for portfolio optimization is years away
- ECO 322: "DSGE Model (simplified)" — DSGE models require calibration that takes months of PhD-level work
- ECO 401: "Satellite + macro data" for development stage classification — satellite data pipelines are complex infrastructure

**Impact:** These aspirational references inflate the perceived completeness of the curriculum integration.

**Recommendation:** Separate "Phase 1: Implementable" from "Phase N: Aspirational" in the curriculum doc. Remove quantum computing references until there's a concrete implementation path.

---

## 7. Detailed Module-by-Module Verification

### 7.1 Market Microstructure Engine (ECO 101)

| Aspect | Verdict |
|--------|---------|
| Concept coverage | ✅ All 12 ECO 101 concepts mapped |
| Agent bindings | ✅ Liquidity Agent, SMC Agent, Execution Agent — all exist in system architecture |
| Data pipeline | ✅ Hot (tick/book), Warm (trades), Cold (snapshots) — matches system architecture |
| ML models | ✅ XGBoost sweep classifier, RF flow model — specified |
| Trading engine integration | ⚠️ S6 (Liquidity) + S7 (SMC) partially cover this, but the full "Market Microstructure Engine" isn't a single module in VMPM |

### 7.2 Macro Signal Engine (ECO 102)

| Aspect | Verdict |
|--------|---------|
| Concept coverage | ✅ All 9 ECO 102 concepts mapped |
| Agent bindings | ✅ Fundamental Agent — exists |
| Data pipeline | ✅ Calendar (warm), News (warm), Economic data (cold) — matches |
| ML models | ✅ FinBERT, LSTM, HMM — all specified |
| Trading engine integration | ⚠️ S1 (Fundamental Intelligence) partially implements this, but the full engine isn't in VMPM |
| Redundancy | ⚠️ FX model overlaps with Forex Market Engine |

### 7.3 Portfolio Optimization Engine (ECO 103)

| Aspect | Verdict |
|--------|---------|
| Concept coverage | ✅ All 8 ECO 103 concepts mapped |
| Agent bindings | ✅ Entry Agent, Portfolio Allocator — exist |
| Data pipeline | ✅ Cold (covariance matrix), Redis (indicators) |
| ML models | ⚠️ No ML — uses convex optimizer (cvxpy) and PCA, which is correct |
| Trading engine integration | ⚠️ S11 (Position Sizing) uses quarter-Kelly, not full MVO. The curriculum describes Markowitz optimization but S11 doesn't implement it. |

### 7.4 Dynamic Programming Engine (ECO 104)

| Aspect | Verdict |
|--------|---------|
| Concept coverage | ⚠️ Only Bellman → RL is genuinely mapped. ODE/SDE/convex sets are weakly connected. |
| Agent bindings | ✅ TP Agent, Execution Agent, Reflection Agent — exist |
| Data pipeline | ✅ Hot (positions), Warm (signals), Cold (trades) |
| ML models | ✅ PPO, DQN, Q-learning — all specified |
| Trading engine integration | ⚠️ S13 (Take Profit) has an RL agent, but it's one component of S13, not a standalone "Dynamic Programming Engine" |

### 7.5 Multi-Agent Coordinator (ECO 201)

| Aspect | Verdict |
|--------|---------|
| Concept coverage | ✅ Nash equilibrium, game theory, market structures — all mapped |
| Agent bindings | ✅ Orchestrator Agent — exists in system architecture |
| Data pipeline | ✅ Hot (shared state), Redis Streams (agent comms) |
| ML models | ✅ MARL for Nash equilibrium — specified |
| Trading engine integration | ✅ The multi-agent orchestrator exists in the system architecture and is implemented |

### 7.6 Regime Detection Engine (ECO 205)

| Aspect | Verdict |
|--------|---------|
| Concept coverage | ✅ IS-LM, AD-AS, Mundell-Fleming, Taylor Rule, business cycle — all mapped |
| Agent bindings | ✅ Structure Agent, Fundamental Agent — exist |
| Data pipeline | ✅ Warm (macro data), Cold (history) |
| ML models | ✅ HMM (3-state), XGBoost (cycle phase) — specified |
| Trading engine integration | ⚠️ S2 (Market Bias) has HMM but only 3 states on returns/volatility. The full IS-LM/AD-AS/Taylor Rule regime engine isn't implemented. |

### 7.7 Forex Market Engine (ECO 209)

| Aspect | Verdict |
|--------|---------|
| Concept coverage | ✅ All 16 ECO 209 concepts mapped — excellent coverage |
| Agent bindings | ✅ Fundamental Agent, Central Bank Watcher, Liquidity Agent — exist |
| Data pipeline | ✅ Hot (FX rates, funding), Warm (news, calendar), Cold (historical) |
| ML models | ✅ FinBERT (Fed speak), LSTM (rates) — specified |
| Trading engine integration | ❌ No corresponding VMPM step. This is a standalone module description with no pipeline integration. |

### 7.8 FX Model / Trade Flow Engine (ECO 305/313)

| Aspect | Verdict |
|--------|---------|
| Concept coverage | ✅ All 15 ECO 305/313 concepts mapped |
| Agent bindings | ✅ Fundamental Agent, Structure Agent — exist |
| Data pipeline | ✅ Hot (spot/FW), Warm (BOP data) |
| ML models | ✅ LSTM (FX), Transformer (multi-asset) — specified |
| Trading engine integration | ❌ Same issue as Forex Market Engine — no VMPM step |

### 7.9 General Equilibrium / Pricing Engine (ECO 321)

| Aspect | Verdict |
|--------|---------|
| Concept coverage | ✅ All 13 ECO 321 concepts mapped |
| Agent bindings | ✅ Signal Aggregator, Portfolio Allocator — exist |
| Data pipeline | ✅ Cold (factor matrix) |
| ML models | ⚠️ Convex optimizer is real; quantum QAOA is aspirational |
| Trading engine integration | ❌ No VMPM step. The "no-arbitrage checker" and "cross-asset pricer" don't exist in the trading engine. |

### 7.10 DSGE / Policy Reaction Function Engine (ECO 322)

| Aspect | Verdict |
|--------|---------|
| Concept coverage | ✅ All 14 ECO 322 concepts mapped |
| Agent bindings | ✅ Fundamental Agent, Structure Agent — exist |
| Data pipeline | ✅ Warm (IS-LM params), Cold (DSGE) |
| ML models | ⚠️ LLM for policy analysis is real; DSGE model requires PhD-level calibration |
| Trading engine integration | ❌ No VMPM step. Stagflation detector and policy reaction function don't exist in code. |

### 7.11 EM Sovereign Risk Module (ECO 401)

| Aspect | Verdict |
|--------|---------|
| Concept coverage | ✅ All 13 ECO 401 concepts mapped |
| Agent bindings | ✅ Fundamental Agent — exists |
| Data pipeline | ✅ Cold (development indicators) |
| ML models | ✅ XGBoost (country score), LLM (policy) — specified |
| Trading engine integration | ❌ No VMPM step. Sovereign risk scoring doesn't exist in code. |

### 7.12 Signal Validation Engine (ECO 414/424)

| Aspect | Verdict |
|--------|---------|
| Concept coverage | ✅ All 20+ ECO 414/424 concepts mapped — most thorough mapping |
| Agent bindings | ✅ Reflection Agent, Journal Agent — exist |
| Data pipeline | ✅ Cold (backtest DB, signals, market data) |
| ML models | ✅ OLS, MLE, Bootstrap, Bayesian — all specified with implementation details |
| Code specification | ✅ The `SignalValidationEngine` class is the most detailed code in the curriculum doc |
| Trading engine integration | ❌ No VMPM step. The most critical curriculum module has no trading engine implementation. |

### 7.13 Fiscal Policy Module (ECO 421)

| Aspect | Verdict |
|--------|---------|
| Concept coverage | ✅ All 14 ECO 421 concepts mapped |
| Agent bindings | ✅ Fundamental Agent — exists |
| Data pipeline | ✅ Warm (budget data), Cold (debt) |
| ML models | ✅ NLP (budget parsing), Monte Carlo (DSA) — specified |
| Trading engine integration | ❌ No VMPM step. Budget event calendar and sovereign bond pricing don't exist. |

### 7.14 Industry Analysis Module (ECO 422)

| Aspect | Verdict |
|--------|---------|
| Concept coverage | ✅ All 12 ECO 422 concepts mapped |
| Agent bindings | ✅ Fundamental Agent — exists |
| Data pipeline | ✅ Cold (financial statements) |
| ML models | ✅ NLP (earnings), XGBoost (SCP) — specified |
| Trading engine integration | ❌ No VMPM step. Industry analysis doesn't exist in code. |

---

## 8. Summary Scorecard

| Criterion | Score | Notes |
|-----------|-------|-------|
| **Completeness** (all 14 units mapped) | 10/10 | Every ECO unit has a module assignment |
| **Accuracy** (mappings are genuine) | 7/10 | 11 strong, 2 acceptable, 1 weak (ECO 104) |
| **Macro Signal Engine** | 7/10 | Well-designed but has redundancy with Forex Engine |
| **Forex Market Engine** | 8/10 | Best-designed module; minor integration gaps |
| **Curriculum drives code** | 4/10 | 8 described modules ≠ 16-step VMPM pipeline. 7 of 8 modules have no VMPM step. |
| **Integration completeness** | 3/10 | 6 critical gaps; most curriculum modules are descriptions, not implementations |

**Overall Architecture Quality: 6.5/10**

The curriculum mapping is a strong theoretical document. The concept-to-module mappings are mostly accurate and well-reasoned. However, the document exists as an overlay on top of the trading engine rather than a driver of it. The gap between "curriculum describes 8 modules" and "trading engine implements 16 steps" is the fundamental integration problem.

---

## 9. Recommendations (Priority Order)

### P0: Wire Curriculum Modules into VMPM Pipeline

The 8 curriculum modules need explicit integration points in the 16-step VMPM pipeline. Recommended approach:

```
NEW: Macro Overlay Layer (sits between Data Layer and VMPM)
├── Macro Signal Engine → produces macro_context consumed by S1
├── Forex Market Engine → produces fx_signals consumed by S1 (for FX pairs)
├── Regime Detection Engine → produces regime_state consumed by S2
└── Signal Validation Engine → validates S10 output before S11

Modified VMPM Steps:
S1 (Fundamental Intelligence) → now consumes Macro Signal Engine + Forex Market Engine
S2 (Market Bias) → now consumes unified Regime Detection Engine
S10 → S11 gate: Signal Validation Engine must approve before position sizing
```

### P1: Implement Signal Validation Engine

This is the highest-priority curriculum module (ECO 414/424, marked CRITICAL). Implement the `SignalValidationEngine` class from the curriculum doc as a gate between S10 and S11.

### P2: Resolve Macro/Forex Engine Redundancy

Remove `fx_model` from Macro Signal Engine. The Macro Engine produces context; the Forex Engine produces signals. Clear boundary.

### P3: Create Unified Regime State

Merge the three regime detection models into a single `RegimeState` object published to Redis.

### P4: Separate Implementable from Aspirational

Remove quantum computing references. Mark DSGE as "Phase 3+" (requires PhD-level calibration). Focus Phase 1 on implementable modules.

### P5: Map Curriculum to VMPM Steps Explicitly

Add a mapping table to the curriculum doc that shows exactly which VMPM step(s) each curriculum module feeds into, with data flow specifications.

---

## 10. Conclusion

Valentine's economics curriculum is well-mapped to Alpha Stack modules at the concept level. The 14 ECO units cover the full spectrum from microeconomic foundations to advanced econometrics, and the concept-to-module mappings are mostly genuine and well-reasoned. The strongest mapping is ECO 414/424 (Econometrics) → Signal Validation Engine, which has detailed implementation specifications.

However, the curriculum architecture exists as a theoretical overlay rather than a code-driving blueprint. The 8 described modules don't correspond to the 16-step VMPM pipeline that the trading engine actually implements. Seven of the eight curriculum modules have no corresponding VMPM step. The curriculum adds macro/fundamental depth that the VMPM pipeline currently lacks, but the wiring between curriculum concepts and trading code is incomplete.

The path forward is clear: wire the curriculum modules into the VMPM pipeline as a macro overlay layer, implement the Signal Validation Engine as the first priority, and create explicit integration points between curriculum concepts and trading steps.
