# Curriculum Gap Remediation Plan

**Generated:** 2026-07-11  
**Source:** `review_curriculum_integration.md` — 7 critical gaps + 2 sequencing fixes  
**Goal:** Define concrete self-study plans, learning paths, and wiring corrections for every identified gap

---

## Table of Contents

1. [Gap 1: STA 244 — Time Series Analysis (D Grade)](#gap-1-sta-244--time-series-analysis-d-grade)
2. [Gap 2: STA 342 — Hypothesis Testing (D Grade)](#gap-2-sta-342--hypothesis-testing-d-grade)
3. [Gap 3: ECO 305/313 — International Economics (D Grades)](#gap-3-eco-305313--international-economics-d-grades)
4. [Gap 4: Systems Programming (Rust/Tauri)](#gap-4-systems-programming)
5. [Gap 5: Real-Time Systems & Concurrency](#gap-5-real-time-systems--concurrency)
6. [Gap 6: Market Microstructure Theory](#gap-6-market-microstructure-theory)
7. [Gap 7: Production Econometrics](#gap-7-production-econometrics)
8. [Fix A: STA 244 Self-Study → Phase 1](#fix-a-sta-244-self-study--phase-1)
9. [Fix B: ECO 414/424 Wiring Order](#fix-b-eco-414424-wiring-order)
10. [Revised Phase Plan](#revised-phase-plan)
11. [Dependencies Between Gaps](#dependencies-between-gaps)
12. [Weekly Schedule Template](#weekly-schedule-template)

---

## Gap 1: STA 244 — Time Series Analysis (D Grade)

**Severity:** 🔴 CRITICAL  
**Why critical:** ARIMA, GARCH, and cointegration are THE core forecasting toolkit. Every signal agent depends on time series competence. A D grade (45%) means foundational concepts are shaky.

### Root Cause Analysis

STA 244 covers: stationarity, AR/MA/ARIMA models, GARCH volatility modeling, cointegration, Granger causality, unit root tests, VAR/VECM. At 45%, the likely gaps are:
- ARIMA model identification (ACF/PACF interpretation)
- GARCH parameter estimation and interpretation
- Cointegration testing (Engle-Granger, Johansen)
- Stationarity testing (ADF, KPSS, Phillips-Perron)

### Self-Study Plan

#### Phase 1A: Foundations (Weeks 1–3)

| Topic | Resource | Hours | Deliverable |
|-------|----------|-------|-------------|
| Stationarity & Unit Root Tests | Hamilton Ch. 15–16; `statsmodels.tsa.stattools` | 8 | Implement ADF, KPSS, PP tests on forex data |
| AR/MA/ARMA Identification | Hamilton Ch. 3–5; Hyndman & Athanasopoulos Ch. 8 | 12 | ACF/PACF analysis notebook for 5 major pairs |
| ARIMA Estimation & Forecasting | `statsmodels.tsa.arima.model.ARIMA` | 8 | Rolling 1-step forecast pipeline |

**Milestone:** Can identify, estimate, and forecast ARIMA models for any stationary time series.

#### Phase 2A: Volatility Modeling (Weeks 4–5)

| Topic | Resource | Hours | Deliverable |
|-------|----------|-------|-------------|
| ARCH/GARCH Theory | Hamilton Ch. 21; Tsay Ch. 3 | 8 | Implement GARCH(1,1) from scratch |
| GARCH Extensions (EGARCH, GJR-GARCH) | `arch` library docs; Engle & Ng (1993) | 6 | Asymmetric volatility model for BTCUSD |
| Volatility Forecasting & Backtesting | Patton & Sheppard (2015) | 6 | Volatility forecast evaluation (MCS test) |

**Milestone:** Can model and forecast volatility for any asset with appropriate GARCH variant.

#### Phase 3A: Multivariate & Cointegration (Weeks 6–8)

| Topic | Resource | Hours | Deliverable |
|-------|----------|-------|-------------|
| VAR Models | Hamilton Ch. 11; Lütkepohl | 8 | Implement VAR for macro indicators → FX |
| Cointegration (Engle-Granger) | Hamilton Ch. 19; `statsmodels.tsa.vector_ar` | 8 | Pairs trading signal on cointegrated FX pairs |
| Johansen Test & VECM | Johansen (1991); `statsmodels` | 8 | Multi-cointegration system for currency basket |
| Granger Causality | Granger (1969); `statsmodels.tsa.stattools` | 4 | Causality network for macro→FX transmission |

**Milestone:** Can build multivariate time series models and identify cointegrated relationships.

### Assessment Criteria

- [ ] Pass: Can implement ARIMA, GARCH, and cointegration tests in Python with < 5% error vs reference implementations
- [ ] Pass: Can correctly identify model order via ACF/PACF for 8/10 synthetic test series
- [ ] Pass: Can detect cointegration in known pairs (e.g., EUR/USD vs GBP/USD) at 95% confidence

### Alpha Stack Wiring

| STA 244 Concept | Alpha Stack Module | Agent |
|----------------|-------------------|-------|
| ARIMA Forecasting | `engines/time_series/arima.py` | Mean-Reversion, Momentum |
| GARCH Volatility | `engines/time_series/garch.py` | Volatility Agent |
| Cointegration | `engines/time_series/cointegration.py` | Mean-Reversion Agent |
| Granger Causality | `engines/validation/granger.py` | Signal Validation Engine |
| VAR/VECM | `engines/time_series/var.py` | Fundamental Agent, Carry Agent |

---

## Gap 2: STA 342 — Hypothesis Testing (D Grade)

**Severity:** 🔴 CRITICAL  
**Why critical:** Backtesting validation is hypothesis testing. Every strategy claim ("this strategy beats the market") is a hypothesis. A D grade (41%) means the statistical foundation for claiming "this works" is broken.

### Root Cause Analysis

STA 342 covers: t-tests, chi-square tests, ANOVA, multiple testing corrections (Bonferroni, FDR), power analysis, effect sizes, non-parametric tests. At 41%, likely gaps:
- When to use which test
- Multiple testing problem (testing 1000 strategies → many false positives)
- Power analysis and sample size requirements
- p-value interpretation and limitations

### Self-Study Plan

#### Phase 1B: Core Testing (Weeks 1–3)

| Topic | Resource | Hours | Deliverable |
|-------|----------|-------|-------------|
| Hypothesis Testing Framework | Casella & Berger Ch. 8–9; Wasserman Ch. 10 | 8 | Decision tree: which test for which data |
| t-tests, z-tests, chi-square | Khan Academy + `scipy.stats` | 6 | Implement all common tests from scratch |
| ANOVA & Post-hoc Tests | `scipy.stats.f_oneway`, Tukey HSD | 6 | Compare strategy returns across regimes |

#### Phase 2B: Multiple Testing & Backtest Validation (Weeks 4–6)

| Topic | Resource | Hours | Deliverable |
|-------|----------|-------|-------------|
| Multiple Testing Problem | Harvey et al. (2016) "…and the Cross-Section of Expected Returns" | 8 | Implement Bonferroni, Holm, BH corrections |
| FDR Control (Benjamini-Hochberg) | BH (1995); Storey (2002) | 6 | FDR-controlled strategy selection pipeline |
| Power Analysis & Sample Size | Cohen (1988); `statsmodels.stats.power` | 6 | Minimum sample size calculator for backtests |
| Effect Size (Cohen's d, η²) | Lakens (2013) | 4 | Effect size reporting for all strategy tests |

#### Phase 3B: Backtest-Specific Testing (Weeks 7–8)

| Topic | Resource | Hours | Deliverable |
|-------|----------|-------|-------------|
| Bootstrap & Permutation Tests | Efron & Tibshirani; `arch.bootstrap` | 8 | Bootstrap confidence intervals for Sharpe ratios |
| Reality Check (White, 2000) | White's SPA test; `arch` library | 6 | Data-snooping-aware strategy comparison |
| Deflated Sharpe Ratio | Bailey & López de Prado (2014) | 4 | Implement DSR for strategy selection |

**Total: ~76 hours over 8 weeks (9.5 hrs/week)**

### Assessment Criteria

- [ ] Can correctly select and apply the appropriate test for any backtest scenario
- [ ] Can implement multiple testing corrections that control FDR at 5%
- [ ] Can compute deflated Sharpe ratio and bootstrap CIs for strategy returns
- [ ] Can design a backtest validation protocol that avoids data snooping

### Alpha Stack Wiring

| STA 342 Concept | Alpha Stack Module | Purpose |
|----------------|-------------------|---------|
| Hypothesis Tests | `engines/validation/hypothesis_tests.py` | Validate strategy significance |
| Multiple Testing | `engines/validation/multiple_testing.py` | Control false discoveries across strategies |
| Power Analysis | `engines/validation/power_analysis.py` | Determine minimum backtest length |
| Bootstrap CI | `engines/validation/bootstrap.py` | Confidence intervals for Sharpe, alpha |
| Deflated Sharpe | `engines/validation/deflated_sharpe.py` | Strategy selection with data-snooping correction |
| Reality Check | `engines/validation/reality_check.py` | White's SPA test for model comparison |

---

## Gap 3: ECO 305/313 — International Economics (D Grades)

**Severity:** 🔴 CRITICAL  
**Why critical:** The Alpha Stack trades forex. ECO 305 covers international trade theory, BOP, and exchange rate determination. ECO 313 covers advanced international monetary economics. D grades in both (40–45%) mean the economic foundation for understanding WHY currencies move is weak.

### Root Cause Analysis

ECO 305 covers: comparative advantage, trade models (Heckscher-Ohlin, Ricardian), BOP accounting, exchange rate determination, monetary/fiscal policy in open economy (Mundell-Fleming).  
ECO 313 covers: optimal currency areas, international monetary systems, capital flows, currency crises, sovereign debt.

At D grades, likely gaps:
- Mundell-Fleming model mechanics
- BOP identity and its components
- Exchange rate regime classification
- Currency crisis models (first, second, third generation)
- Optimal currency area theory

### Self-Study Plan

#### Phase 1C: Core International Economics (Weeks 1–4)

| Topic | Resource | Hours | Deliverable |
|-------|----------|-------|-------------|
| Trade Theory Refresher | Krugman et al. Ch. 3–7 | 8 | Notes + trade model comparison table |
| BOP Accounting | Krugman Ch. 12–13; IMF BPM6 | 6 | BOP analysis pipeline for 10 countries |
| Mundell-Fleming Model | Krugman Ch. 16–17; Blanchard Ch. 19 | 10 | Policy response simulator (monetary/fiscal under fixed/floating) |
| Exchange Rate Regimes | IMF AREAER database; Klein & Shambaugh (2010) | 6 | Regime classification database |

#### Phase 2C: Advanced FX Economics (Weeks 5–8)

| Topic | Resource | Hours | Deliverable |
|-------|----------|-------|-------------|
| Currency Crisis Models | Krugman (1979), Obstfeld (1996), Chang & Velasco (2001) | 10 | Crisis probability model (logistic regression) |
| Optimal Currency Areas | Mundell (1961), McKinnon (1963), Kenen (1969) | 6 | OCA index calculator for currency blocs |
| Capital Flows & Sudden Stops | Calvo (1998), Rey (2015) | 6 | Capital flow regime detector |
| International Monetary Systems | Eichengreen; Bordo & MacDonald | 8 | Historical regime analysis for context |

#### Phase 3C: FX Trading Applications (Weeks 9–10)

| Topic | Resource | Hours | Deliverable |
|-------|----------|-------|-------------|
| PPP & Real Exchange Rate | Rogoff (1996); IMF WEO data | 6 | PPP deviation signal for long-horizon FX |
| Interest Rate Parity (UIP/CIP) | Chinn & Meredith (2004) | 6 | Carry trade signal with UIP deviation |
| Taylor Rule for FX | Taylor (1993); Engel et al. (2015) | 6 | Fair value model using Taylor rule implied rate |

**Total: ~84 hours over 10 weeks (8.4 hrs/week)**

### Assessment Criteria

- [ ] Can derive Mundell-Fleming predictions for any policy/ regime combination
- [ ] Can classify exchange rate regimes and predict regime shifts
- [ ] Can implement PPP, UIP, and Taylor-rule-based FX fair value models
- [ ] Can model currency crisis probability using fundamentals

### Alpha Stack Wiring

| ECO 305/313 Concept | Alpha Stack Module | Agent |
|--------------------|-------------------|-------|
| Mundell-Fleming | `engines/macro/mundell_fleming.py` | Fundamental Agent |
| BOP Analysis | `engines/macro/bop.py` | Fundamental Agent |
| Currency Crisis | `engines/macro/crisis_model.py` | Risk Agent, Regime Agent |
| PPP / REER | `engines/macro/ppp_fair_value.py` | Carry Agent |
| UIP/CIP Deviation | `engines/macro/interest_parity.py` | Carry Agent |
| Taylor Rule FX | `engines/macro/taylor_rule_fx.py` | Fundamental Agent |
| OCA Index | `engines/macro/oca.py` | Regime Agent |
| Capital Flows | `engines/macro/capital_flows.py` | Fundamental Agent |

---

## Gap 4: Systems Programming

**Severity:** 🔴 CRITICAL  
**Why critical:** Rust/Tauri is the chosen tech stack for the desktop application. The execution layer requires low-latency, memory-safe code. No curriculum covers systems programming.

### Learning Path

#### Phase 1: Rust Fundamentals (Weeks 1–4)

| Topic | Resource | Hours | Deliverable |
|-------|----------|-------|-------------|
| Ownership & Borrowing | "The Rust Book" Ch. 4; Rustlings exercises | 16 | Complete all Rustlings exercises |
| Structs, Enums, Pattern Matching | "The Rust Book" Ch. 5–6, 18 | 12 | Implement order types (Market, Limit, Stop) as enums |
| Error Handling | "The Rust Book" Ch. 9; `thiserror`, `anyhow` | 6 | Error type hierarchy for trading system |
| Traits & Generics | "The Rust Book" Ch. 10 | 8 | Trait-based strategy interface |
| Iterators & Closures | "The Rust Book" Ch. 13 | 6 | Streaming data processor |
| Cargo, Crates, Project Structure | "The Rust Book" Ch. 14; Cargo book | 4 | Workspace layout for trading system |

#### Phase 2: Async & Concurrency (Weeks 5–8)

| Topic | Resource | Hours | Deliverable |
|-------|----------|-------|-------------|
| `tokio` Runtime | tokio tutorial; "Asynchronous Programming in Rust" | 12 | Async order book updater |
| Channels (`mpsc`, `broadcast`) | tokio docs | 8 | Multi-agent message passing system |
| `select!` and concurrent tasks | tokio docs | 6 | Race conditions handler for multiple data feeds |
| Shared State (`Arc<Mutex>`, `RwLock`) | "Rust Atomics and Locks" (Mara Bos) | 8 | Thread-safe position manager |

#### Phase 3: Tauri & FFI (Weeks 9–12)

| Topic | Resource | Hours | Deliverable |
|-------|----------|-------|-------------|
| Tauri Architecture | Tauri docs + examples | 12 | Basic Tauri app with Rust backend |
| Tauri Commands & Events | Tauri docs | 8 | Command interface for trading engine |
| FFI to Python (PyO3) | PyO3 docs | 8 | Call Python ML models from Rust |
| Serialization (serde) | serde docs; `serde_json` | 4 | Config/state serialization |

#### Phase 4: Production Patterns (Weeks 13–16)

| Topic | Resource | Hours | Deliverable |
|-------|----------|-------|-------------|
| Memory Management & Profiling | `cargo flamegraph`, `dhat` | 8 | Profile and optimize hot paths |
| Testing & Property-Based Testing | `proptest`, `quickcheck` | 6 | Property tests for order matching |
| Logging & Observability | `tracing` crate | 4 | Structured logging for all subsystems |
| Error Recovery & Graceful Degradation | Patterns from "Zero To Production In Rust" | 6 | Circuit breaker pattern for exchange feeds |

**Total: ~138 hours over 16 weeks (8.6 hrs/week)**

### Assessment Criteria

- [ ] Can build a concurrent, async Rust application with `tokio`
- [ ] Can implement a Tauri desktop app with Rust backend and web frontend
- [ ] Can use PyO3 to bridge Rust ↔ Python for ML model inference
- [ ] Can profile and optimize Rust code for latency-sensitive paths

### Alpha Stack Wiring

| Rust/Tauri Component | Alpha Stack Module |
|---------------------|-------------------|
| Order Matching Engine | `execution/engine/matching.rs` |
| Async Data Feed Handler | `data/feeds/async_handler.rs` |
| Position Manager | `execution/position/manager.rs` |
| Tauri Frontend | `frontend/tauri/` (dashboard) |
| PyO3 ML Bridge | `ml/pyo3_bridge.rs` (call Python models) |
| Risk Check (low-latency) | `risk/realtime/check.rs` |

---

## Gap 5: Real-Time Systems & Concurrency

**Severity:** 🔴 CRITICAL  
**Why critical:** 24/7 forex trading requires systems that never sleep: concurrent data feeds, async order processing, event-driven architecture, message queues, fault tolerance. No curriculum covers this.

### Learning Path

#### Phase 1: Concurrency Fundamentals (Weeks 1–3)

| Topic | Resource | Hours | Deliverable |
|-------|----------|-------|-------------|
| Async/Await in Python | `asyncio` docs; Beazley "Python Concurrency" | 10 | Async data fetcher for 5 FX pairs |
| Event Loop & Task Scheduling | `asyncio` internals | 6 | Custom event loop for trading system |
| Thread Safety & Locks | `threading`, `multiprocessing` docs | 6 | Thread-safe order queue |

#### Phase 2: Message Queues & Event-Driven Architecture (Weeks 4–6)

| Topic | Resource | Hours | Deliverable |
|-------|----------|-------|-------------|
| Redis Pub/Sub | Redis docs | 8 | Inter-agent communication bus |
| Message Queue Patterns | Kleppmann Ch. 11; Redis Streams | 8 | Reliable order flow with dead letter queue |
| Event Sourcing | Young "Versioning in an Event Sourced System" | 6 | Event-sourced position tracker |
| CQRS Pattern | Vernon "Implementing DDD" | 6 | Separate read/write models for trading |

#### Phase 3: Fault Tolerance & 24/7 Operations (Weeks 7–10)

| Topic | Resource | Hours | Deliverable |
|-------|----------|-------|-------------|
| Circuit Breaker Pattern | Nygaard "Release It!" | 6 | Exchange feed circuit breaker |
| Health Checks & Heartbeats | Implement liveness/readiness probes | 4 | Agent health monitoring system |
| Graceful Shutdown & Restart | Signal handling, state persistence | 6 | Zero-downtime restart capability |
| State Recovery & Replay | Event log replay pattern | 8 | Recover positions from event log after crash |
| Rate Limiting & Backpressure | Token bucket algorithm | 4 | Exchange API rate limiter |

#### Phase 4: Deployment & Monitoring (Weeks 11–12)

| Topic | Resource | Hours | Deliverable |
|-------|----------|-------|-------------|
| Docker Containerization | Docker docs | 8 | Dockerize all system components |
| Health Monitoring Dashboard | Grafana + Prometheus basics | 6 | Real-time system health dashboard |
| Alerting & Escalation | PagerDuty model; on-call patterns | 4 | Alert pipeline for P&L drawdown, system failures |
| Log Aggregation | ELK basics; structured logging | 4 | Centralized logging for debugging |

**Total: ~104 hours over 12 weeks (8.7 hrs/week)**

### Assessment Criteria

- [ ] Can build an async, event-driven system with multiple concurrent data feeds
- [ ] Can implement message queue communication between agents
- [ ] Can design fault-tolerant systems with circuit breakers and graceful degradation
- [ ] Can containerize and deploy a multi-component system

### Alpha Stack Wiring

| Concurrency Concept | Alpha Stack Module |
|-------------------|-------------------|
| Async Data Feeds | `data/feeds/async_feed.py` |
| Redis Pub/Sub Bus | `core/messaging/redis_bus.py` |
| Event Sourcing | `core/events/event_store.py` |
| Circuit Breaker | `core/resilience/circuit_breaker.py` |
| Health Checks | `core/health/liveness.py` |
| Docker Deployment | `deployment/docker/` |
| Monitoring | `deployment/monitoring/` |

---

## Gap 6: Market Microstructure Theory

**Severity:** 🔴 CRITICAL  
**Why critical:** SMC (Smart Money Concepts) implementation requires understanding HOW markets actually work at the order level: bid-ask dynamics, informed trading, market impact, order flow toxicity. ECO 201 touches microstructure but at C grade.

### Learning Path

#### Phase 1: Core Microstructure Theory (Weeks 1–4)

| Topic | Resource | Hours | Deliverable |
|-------|----------|-------|-------------|
| Kyle (1985) Model | Kyle "Continuous Auctions and Insider Trading" | 8 | Implement Kyle lambda estimator |
| Glosten-Milgrom (1985) | Glosten & Milgrom "Bid, Ask, and Transaction Prices" | 6 | Adverse selection component of spread |
| Market Maker Models | Harris "Trading and Exchanges" Ch. 9–12 | 10 | Spread decomposition (adverse selection + inventory + processing) |
| Order Book Dynamics | Cont, Stoikov & Talreja (2010) | 8 | Order book simulation engine |

#### Phase 2: Order Flow Analysis (Weeks 5–7)

| Topic | Resource | Hours | Deliverable |
|-------|----------|-------|-------------|
| VPIN (Volume-Synchronized PIN) | Easley, López de Prado & O'Hara (2012) | 8 | VPIN toxicity indicator |
| Kyle's Lambda Estimation | Brennan & Subrahmanyam (1996) | 6 | Realized lambda from tick data |
| Order Flow Imbalance | Cont et al. (2014) | 6 | OFI predictor for short-horizon returns |
| Trade Classification (Lee-Ready) | Lee & Ready (1991) | 4 | Tick rule classifier |

#### Phase 3: SMC Implementation (Weeks 8–10)

| Topic | Resource | Hours | Deliverable |
|-------|----------|-------|-------------|
| Institutional Order Detection | Cont & Kukanov (2017) | 8 | Large order detection algorithm |
| Iceberg Order Detection | Hautsch & Huang (2012) | 6 | Hidden liquidity estimator |
| Liquidity Zones & Imbalances | Practical SMC literature | 8 | Order block and fair value gap detector |
| Smart Money vs Retail Flow | Barber & Odean (2000); Hvidkjaer (2008) | 6 | Flow classification model |

#### Phase 4: Market Impact & Execution (Weeks 11–12)

| Topic | Resource | Hours | Deliverable |
|-------|----------|-------|-------------|
| Temporary & Permanent Impact | Almgren & Chriss (2001) | 8 | Impact cost model |
| Optimal Execution (Almgren-Chriss) | Almgren & Chriss (2000) | 8 | Optimal execution trajectory |
| TWAP/VWAP Algorithms | Kissell "The Science of Algorithmic Trading" | 6 | Basic execution algorithms |

**Total: ~108 hours over 12 weeks (9 hrs/week)**

### Assessment Criteria

- [ ] Can derive Kyle and Glosten-Milgrom models from first principles
- [ ] Can estimate VPIN, Kyle's lambda, and order flow imbalance from tick data
- [ ] Can detect institutional orders and hidden liquidity patterns
- [ ] Can implement market impact models and basic execution algorithms

### Alpha Stack Wiring

| Microstructure Concept | Alpha Stack Module | Agent |
|-----------------------|-------------------|-------|
| Kyle Lambda | `engines/microstructure/kyle_lambda.py` | Execution Agent |
| VPIN | `engines/microstructure/vpin.py` | Risk Agent |
| Order Flow Imbalance | `engines/microstructure/ofi.py` | Momentum Agent |
| Order Book Simulation | `engines/microstructure/orderbook_sim.py` | Execution Agent |
| SMC Detection | `engines/microstructure/smc_detector.py` | Momentum Agent, Execution Agent |
| Market Impact | `engines/microstructure/impact_model.py` | Execution Agent |
| Optimal Execution | `engines/execution/almgren_chriss.py` | Execution Agent |

---

## Gap 7: Production Econometrics

**Severity:** 🔴 CRITICAL  
**Why critical:** ECO 414/424 covers econometrics but is a NEW course (not yet graded). Even with a strong grade, production econometrics for trading requires going beyond textbook: robust inference with financial data, regime-robust estimation, high-frequency methods.

### Learning Path

#### Phase 1: Econometrics Foundations (Weeks 1–4)

| Topic | Resource | Hours | Deliverable |
|-------|----------|-------|-------------|
| OLS & Assumptions | Wooldridge Ch. 1–4; Stock & Watson Ch. 4–6 | 10 | Diagnostic test suite for regression models |
| Heteroskedasticity & Robust SE | White (1980); Newey-West (1987) | 8 | HAC-robust inference for financial regressions |
| Instrumental Variables & 2SLS | Wooldridge Ch. 15; Angrist & Pischke Ch. 4 | 8 | IV regression for causal FX effects |
| Panel Data Methods | Wooldridge Ch. 10, 13 | 8 | Fixed effects model for multi-country FX analysis |

#### Phase 2: Time Series Econometrics (Weeks 5–8)

| Topic | Resource | Hours | Deliverable |
|-------|----------|-------|-------------|
| Robust Inference for Time Series | Newey-West; HAC estimators | 6 | HAC standard errors for all strategy regressions |
| Structural Breaks | Bai & Perron (2003); `strucchange` R / Python equivalent | 8 | Break date detection for macro relationships |
| Threshold & Regime Models | Hansen (1999); Markov-switching | 8 | Regime-dependent regression for FX |
| Local Projections | Jordà (2005) | 6 | Impulse response estimation for macro shocks |

#### Phase 3: Financial Econometrics (Weeks 9–12)

| Topic | Resource | Hours | Deliverable |
|-------|----------|-------|-------------|
| High-Frequency Methods | Aït-Sahalia & Jacod "High-Frequency Financial Econometrics" | 8 | Realized volatility estimation |
| Realized Variance & Covariance | Barndorff-Nielsen & Shephard (2004) | 6 | High-frequency covariance estimator |
| Jumps & Microstructure Noise | Aït-Sahalia (2009) | 6 | Jump-robust volatility estimator |
| Factor Models & PCA | Fama-French; Bai & Ng (2002) | 8 | Dynamic factor model for cross-country returns |

#### Phase 4: Strategy Validation Econometrics (Weeks 13–16)

| Topic | Resource | Hours | Deliverable |
|-------|----------|-------|-------------|
| Predictability Tests | Goyal & Welch (2008); Clark & West (2007) | 8 | Out-of-sample predictability test for FX |
| Cross-Validation for Time Series | Blocked CV; purged CV (de Prado) | 6 | Time-series-aware cross-validation |
| Model Comparison (AIC, BIC, Bayes Factor) | Burnham & Anderson (2002) | 4 | Model selection framework |
| Granger Causality in Production | Granger (1969); Toda-Yamamoto (1995) | 6 | Robust Granger causality with lag selection |

**Total: ~126 hours over 16 weeks (7.9 hrs/week)**

### Assessment Criteria

- [ ] Can apply HAC-robust inference to any financial regression
- [ ] Can detect structural breaks and regime changes in economic relationships
- [ ] Can estimate high-frequency realized volatility and covariance
- [ ] Can run out-of-sample predictability tests with proper time-series cross-validation

### Alpha Stack Wiring

| Econometrics Concept | Alpha Stack Module | Purpose |
|--------------------|-------------------|---------|
| OLS + Robust SE | `engines/econometrics/regression.py` | Strategy regression analysis |
| IV/2SLS | `engines/econometrics/iv.py` | Causal inference for macro→FX |
| Panel Data | `engines/econometrics/panel.py` | Multi-country analysis |
| Structural Breaks | `engines/econometrics/breaks.py` | Detect regime shifts in relationships |
| Local Projections | `engines/econometrics/local_projections.py` | Impulse response analysis |
| Realized Volatility | `engines/econometrics/realized_vol.py` | High-frequency vol estimation |
| Factor Models | `engines/econometrics/factors.py` | Cross-country return factors |
| Predictability Tests | `engines/validation/predictability.py` | OOS strategy validation |

---

## Fix A: STA 244 Self-Study → Phase 1

**Problem:** The original wiring order places STA 244 self-study in Phase 2 (weeks 5–8). This is too late — time series is foundational for signal generation.

**Fix:** STA 244 self-study **must start in Phase 1, week 1.** It runs as a parallel track alongside the strengths-based foundation work.

### Justification

1. **Every signal agent depends on time series.** Momentum needs ARIMA forecasts. Mean-reversion needs cointegration. Volatility needs GARCH. You can't wire any signal engine without time series competence.
2. **Phase 2 currently has too much to do.** It tries to wire time series engines AND do the self-study. Split the learning (Phase 1) from the wiring (Phase 2).
3. **Compounding benefit.** Starting time series study in week 1 means by week 5 you have 4 weeks of practice, not 0.

### Revised Placement

```
Phase 1 (Weeks 1–4):
  ├── [Strength] Wire ECO 103, STA 241, MAT 121 modules
  ├── [GAP 1] STA 244 self-study: Weeks 1–3 (foundations) + Week 4 (volatility intro)
  ├── [GAP 2] STA 342 self-study: Weeks 1–3 (core testing) + Week 4 (multiple testing intro)
  ├── [GAP 3] ECO 305/313 self-study: Weeks 1–4 (core international economics)
  ├── [GAP 7] ECO 414/424 self-study: Weeks 1–4 (econometrics foundations)
  └── [Infrastructure] Basic setup (Redis, PostgreSQL, WebSocket)

Phase 2 (Weeks 5–8):
  ├── [GAP 1] STA 244: Weeks 5–6 (GARCH) + Weeks 7–8 (VAR/cointegration)
  ├── [GAP 2] STA 342: Weeks 5–6 (backtest validation) + Weeks 7–8 (deflated Sharpe)
  ├── [GAP 3] ECO 305/313: Weeks 5–8 (advanced FX economics)
  ├── [GAP 7] ECO 414/424: Weeks 5–8 (time series econometrics)
  └── Wire ARIMA, GARCH, cointegration engines (using Phase 1 knowledge)
```

---

## Fix B: ECO 414/424 Wiring Order

**Problem:** ECO 414/424 (Econometrics) is described as CRITICAL in the integration doc but does NOT appear in the 6-phase wiring order. The Signal Validation Engine depends entirely on econometrics.

**Fix:** Add ECO 414/424 to Phase 1 (start) and Phase 2 (complete).

### Justification

1. **Econometrics = validation backbone.** Without econometrics, you can't run regressions, test hypotheses, or validate strategies. STA 342 (hypothesis testing) and ECO 414/424 (econometrics) are complementary — you need both.
2. **No dependency conflict.** ECO 414/424 depends on basic statistics (STA 142/241, both solid) and basic economics (ECO 101/102, both adequate). It can start in week 1.
3. **Wiring order gap.** The integration doc's Section 9.2 dependency chain lists `STA 142/241 + ECO 104 → Signal Engine` but skips ECO 414/424. This is a gap.

### Revised Wiring

```
Dependency Chain (corrected):

MAT 101 → MAT 121/124 + ECO 103
                              ↓
STA 142/241 + ECO 104 + ECO 414/424  ← ADDED
                              ↓
                    Signal Engine (Time Series + Validation)
                              ↓
                    Risk Engine + Portfolio Engine
                              ↓
                    Macro Engine + Execution Engine
                              ↓
                    Orchestration
```

### Phase Placement

| Phase | ECO 414/424 Activity |
|-------|---------------------|
| Phase 1 (Weeks 1–4) | OLS, robust SE, IV/2SLS, panel data foundations |
| Phase 2 (Weeks 5–8) | Time series econometrics, structural breaks, regime models |
| Phase 3 (Weeks 9–12) | Wire Signal Validation Engine using econometrics knowledge |
| Phase 4 (Weeks 13–16) | Production patterns: HAC inference, model selection, OOS tests |

---

## Revised Phase Plan

### Phase 1 — Foundation + Gap Remediation Start (Weeks 1–4)

| Track | Content | Hours/Week |
|-------|---------|------------|
| **Strength: ECO 103** | Wire covariance, PCA, Markowitz modules | 3 |
| **Strength: STA 241** | Wire distributions, VaR basics modules | 3 |
| **Strength: MAT 121** | Wire momentum, Greeks modules | 2 |
| **Gap 1: STA 244** | Stationarity, AR/MA/ARIMA identification | 8 |
| **Gap 2: STA 342** | Core hypothesis tests, t/z/chi/ANOVA | 6 |
| **Gap 3: ECO 305/313** | Trade theory, BOP, Mundell-Fleming | 6 |
| **Gap 7: ECO 414/424** | OLS, robust SE, IV, panel data | 6 |
| **Infrastructure** | Redis, PostgreSQL, WebSocket setup | 4 |
| **Total** | | **38 hrs/wk** |

### Phase 2 — Signal Engine + Gap Remediation (Weeks 5–8)

| Track | Content | Hours/Week |
|-------|---------|------------|
| **Gap 1: STA 244** | GARCH, VAR, cointegration, Granger | 8 |
| **Gap 2: STA 342** | Multiple testing, bootstrap, deflated Sharpe | 6 |
| **Gap 3: ECO 305/313** | Currency crises, OCA, capital flows, FX models | 6 |
| **Gap 7: ECO 414/424** | Time series econometrics, structural breaks | 6 |
| **Wiring** | Wire ARIMA, GARCH, cointegration engines | 6 |
| **Total** | | **32 hrs/wk** |

### Phase 3 — ML/AI + Systems (Weeks 9–16)

| Track | Content | Hours/Week |
|-------|---------|------------|
| **Gap 4: Rust** | Rust fundamentals + async (Weeks 9–12) | 8 |
| **Gap 5: Real-Time** | Async Python, Redis pub/sub, event-driven (Weeks 9–12) | 6 |
| **Gap 6: Microstructure** | Kyle, Glosten-Milgrom, order flow (Weeks 9–12) | 8 |
| **ML/AI Wiring** | XGBoost, LSTM, HMM, FinBERT | 6 |
| **Wiring** | Wire signal engines, validation framework | 4 |
| **Total** | | **32 hrs/wk** |

### Phase 4 — Risk + Production (Weeks 17–24)

| Track | Content | Hours/Week |
|-------|---------|------------|
| **Gap 4: Rust (cont.)** | Tauri, PyO3, production patterns (Weeks 17–20) | 6 |
| **Gap 5: Real-Time (cont.)** | Fault tolerance, Docker, monitoring (Weeks 17–20) | 6 |
| **Gap 6: Microstructure (cont.)** | SMC, market impact, execution (Weeks 17–20) | 6 |
| **Wiring** | Wire risk engine, portfolio optimizer, execution | 8 |
| **Integration** | End-to-end testing, paper trading | 4 |
| **Total** | | **30 hrs/wk** |

### Phase 5 — Production & Deployment (Weeks 25–32)

| Track | Content | Hours/Week |
|-------|---------|------------|
| **Production Hardening** | Circuit breakers, health checks, alerting | 6 |
| **Multi-Agent** | MARL orchestrator, agent coordination | 6 |
| **Deployment** | Docker, monitoring, CI/CD | 4 |
| **Paper Trading** | Live paper trading with real data | 8 |
| **Iteration** | Fix bugs, tune parameters, add strategies | 6 |
| **Total** | | **30 hrs/wk** |

---

## Dependencies Between Gaps

```
                    ┌─────────────────┐
                    │   STA 244       │ ← Must start Week 1
                    │ (Time Series)   │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  ECO 414/424    │ ← Must start Week 1 (parallel)
                    │ (Econometrics)  │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
     ┌────────▼───────┐ ┌───▼────┐ ┌───────▼────────┐
     │   STA 342      │ │ GAP 3  │ │   GAP 7        │
     │ (Hypothesis    │ │ ECO    │ │ (Production     │
     │  Testing)      │ │ 305/313│ │  Econometrics)  │
     └────────┬───────┘ └───┬────┘ └───────┬────────┘
              │             │              │
              └──────────────┼──────────────┘
                             │
                    ┌────────▼────────┐
                    │  Signal Engine  │ ← Wired in Phase 2
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
     ┌────────▼───────┐ ┌───▼────┐ ┌───────▼────────┐
     │   GAP 4        │ │ GAP 5  │ │   GAP 6        │
     │ (Rust/Systems) │ │(Real-  │ │ (Microstructure)│
     │                │ │ Time)  │ │                 │
     └────────┬───────┘ └───┬────┘ └───────┬────────┘
              │             │              │
              └──────────────┼──────────────┘
                             │
                    ┌────────▼────────┐
                    │  Execution      │ ← Wired in Phase 4
                    │  Engine         │
                    └─────────────────┘
```

**Key dependency insight:** Gaps 1, 2, 3, 7 (academic gaps) are mostly independent and can be studied in parallel. Gaps 4, 5, 6 (systems gaps) depend on the signal engine being designed (Phase 2) but can start learning fundamentals in Phase 3.

---

## Weekly Schedule Template

### Phase 1 Typical Week (38 hrs)

| Day | Morning (3h) | Afternoon (3h) | Evening (2h) |
|-----|-------------|----------------|---------------|
| Mon | STA 244: Stationarity theory + ADF tests | STA 244: ACF/PACF practice | Wire ECO 103 modules |
| Tue | STA 342: t-tests, z-tests | STA 342: Practice problems | Wire STA 241 modules |
| Wed | ECO 305/313: Mundell-Fleming | ECO 305/313: BOP analysis | Infrastructure setup |
| Thu | ECO 414/424: OLS theory | ECO 414/424: Python implementation | Wire MAT 121 modules |
| Fri | STA 244: ARIMA estimation | STA 342: ANOVA | Infrastructure setup |
| Sat | ECO 305/313: Exchange rate regimes | ECO 414/424: Robust SE | Review & practice |
| Sun | Rest / light review | | |

### Progress Tracking

| Gap | Week 1 | Week 2 | Week 3 | Week 4 | Week 5 | Week 6 | Week 7 | Week 8 |
|-----|--------|--------|--------|--------|--------|--------|--------|--------|
| STA 244 | Stationarity | AR/MA | ARIMA | Vol intro | GARCH | GARCH ext | VAR | Coint |
| STA 342 | Core tests | Practice | ANOVA | Multi-test intro | FDR | Bootstrap | Deflated SR | Reality check |
| ECO 305/313 | Trade theory | BOP | M-F model | Regimes | Crises | OCA | Capital flows | FX models |
| ECO 414/424 | OLS | Diagnostics | IV/2SLS | Panel | HAC | Breaks | Regime models | Local proj |
| Rust | — | — | — | — | — | — | — | — |
| Real-Time | — | — | — | — | — | — | — | — |
| Microstructure | — | — | — | — | — | — | — | — |

---

## Summary: Total Remediation Effort

| Gap | Weeks | Total Hours | Priority |
|-----|-------|-------------|----------|
| STA 244 (Time Series) | 1–8 | ~76 hrs | 🔴 P0 — Start Week 1 |
| STA 342 (Hypothesis Testing) | 1–8 | ~76 hrs | 🔴 P0 — Start Week 1 |
| ECO 305/313 (International Econ) | 1–8 | ~84 hrs | 🔴 P0 — Start Week 1 |
| ECO 414/424 (Econometrics) | 1–8 | ~84 hrs | 🔴 P0 — Start Week 1 |
| Systems Programming (Rust) | 9–24 | ~138 hrs | 🔴 P1 — Start Phase 3 |
| Real-Time Systems | 9–24 | ~104 hrs | 🔴 P1 — Start Phase 3 |
| Microstructure Theory | 9–24 | ~108 hrs | 🔴 P1 — Start Phase 3 |
| **TOTAL** | **24 weeks** | **~670 hrs** | |

**Weekly commitment:** 28–38 hours/week (adjustable based on availability)

**Key insight:** The 4 academic gaps (STA 244, STA 342, ECO 305/313, ECO 414/424) total ~320 hours and can be studied in parallel during Phases 1–2 (8 weeks). The 3 systems gaps (Rust, Real-Time, Microstructure) total ~350 hours and fill Phases 3–4 (16 weeks). This is aggressive but achievable at 30–38 hours/week.

---

*Document generated: 2026-07-11*  
*Source: review_curriculum_integration.md*  
*All 7 critical gaps addressed with specific self-study plans, resources, assessment criteria, and Alpha Stack wiring*  
*Both sequencing fixes (STA 244 → Phase 1, ECO 414/424 added to wiring order) implemented*
