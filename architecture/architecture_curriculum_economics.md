# Alpha Stack — Economics Curriculum Architecture

**Author:** Economics Curriculum Architect
**Date:** 2026-07-11
**Status:** Architecture Design
**Scope:** Valentine's 14 Economics Units → Alpha Stack Module Mapping
**Dependencies:** `architecture_data.md`, `architecture_database.md`, `architecture_multi_agent.md`, `architecture_ai_models.md`, `architecture_broker.md`, All `research_curriculum_*.md`

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Curriculum-to-Module Mapping Matrix](#2-curriculum-to-module-mapping-matrix)
3. [Year 1 Foundations: ECO 101–104](#3-year-1-foundations-eco-101104)
4. [Year 2 Core: ECO 201–210](#4-year-2-core-eco-201210)
5. [Year 3 Advanced: ECO 305–322](#5-year-3-advanced-eco-305322)
6. [Year 4 Specialized: ECO 401–424](#6-year-4-specialized-eco-401424)
7. [Concept Dependency Graph](#7-concept-dependency-graph)
8. [Alpha Stack Module Specifications](#8-alpha-stack-module-specifications)
9. [Multi-Agent System Integration](#9-multi-agent-system-integration)
10. [AI/ML Model Bindings](#10-aiml-model-bindings)
11. [Implementation Roadmap](#11-implementation-roadmap)

---

## 1. Executive Summary

This document maps every economics concept from Valentine's 14 ECO units to specific Alpha Stack modules, agents, and data pipelines. Each concept is classified by:
- **Alpha Stack Module** — which system component consumes or produces the concept
- **Agent Binding** — which multi-agent system agent operationalizes it
- **Data Pipeline** — where the concept enters the system (hot/warm/cold path)
- **AI/ML Model** — which model type processes the concept
- **Priority** — CRITICAL (blockers), HIGH (core alpha), MEDIUM (enhancement), LOW (context)

### Grade-Weighted Priority Classification

| Priority | Units | Grade Range | Rationale |
|----------|-------|-------------|-----------|
| 🔴 CRITICAL | ECO 209, ECO 305/313, ECO 414/424 | 44–65% | Weakest grades on highest-impact modules. Must close gaps. |
| 🟡 HIGH | ECO 101, ECO 102, ECO 201, ECO 205, ECO 321, ECO 322 | 51–67% | Core trading theory. Solid foundation, needs deepening. |
| 🟢 MEDIUM | ECO 103, ECO 104, ECO 401, ECO 421, ECO 422 | 60–70% | Supporting modules. Good grades, apply to specialized areas. |

### Coverage Summary

```
14 Economics Units → 8 Alpha Stack Modules → 16 Multi-Agent System Agents

┌──────────────────────────────────────────────────────────────────────┐
│                    ECO → ALPHA STACK PIPELINE                         │
│                                                                      │
│  ECO 101 (Micro)     ──→ Market Microstructure Engine                │
│  ECO 102 (Macro)     ──→ Macro Signal Engine                        │
│  ECO 103 (Math 1)    ──→ Portfolio Optimization Engine               │
│  ECO 104 (Math 2)    ──→ Dynamic Programming Engine (RL)            │
│  ECO 201 (Int Micro) ──→ Game Theory / Multi-Agent Coordinator      │
│  ECO 205 (Int Macro) ──→ Business Cycle / Regime Detection Engine   │
│  ECO 209 (Money)     ──→ Forex Market Engine / Central Bank Watcher │
│  ECO 305/313 (Intl)  ──→ FX Model / Trade Flow Engine               │
│  ECO 321 (Adv Micro) ──→ General Equilibrium / Pricing Engine        │
│  ECO 322 (Adv Macro) ──→ DSGE / Policy Reaction Function Engine     │
│  ECO 401 (Dev)       ──→ Emerging Market Sovereign Risk Module       │
│  ECO 414/424 (Econ)  ──→ Factor Model / Signal Validation Engine    │
│  ECO 421 (Pub Fin)   ──→ Fiscal Policy / Sovereign Credit Module    │
│  ECO 422 (Industry)  ──→ Industry Analysis / Earnings Model Module  │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 2. Curriculum-to-Module Mapping Matrix

### 2.1 Primary Module Assignments

| ECO Unit | Alpha Stack Module | Agent(s) | Data Pipeline | AI/ML Model | Priority |
|----------|-------------------|----------|---------------|-------------|----------|
| **ECO 101** | Market Microstructure | Liquidity Agent, SMC Agent | Hot (order book), Warm (trades) | XGBoost (sweep classifier), RF (flow) | 🟡 HIGH |
| **ECO 102** | Macro Signal Engine | Fundamental Agent | Warm (calendar), Cold (GDP/CPI) | FinBERT, LLM (reasoning), HMM (regime) | 🟡 HIGH |
| **ECO 103** | Portfolio Optimization | Entry Agent, Risk Gate | Cold (covariance matrix) | Convex optimizer, PCA (eigenvalues) | 🟢 MEDIUM |
| **ECO 104** | Dynamic Programming | TP Agent, Execution Agent | Hot (positions), Warm (signals) | PPO (sizing), DQN (TP), Q-table (exec) | 🟢 MEDIUM |
| **ECO 201** | Multi-Agent Coordinator | Orchestrator Agent | Hot (shared state) | MARL (Nash eq.), XGBoost (strategy) | 🟡 HIGH |
| **ECO 205** | Regime Detection | Structure Agent | Warm (macro data), Cold (history) | HMM (regime), XGBoost (cycle phase) | 🟡 HIGH |
| **ECO 209** | Forex Market Engine | Fundamental Agent, Central Bank Watcher | Hot (FX rates), Warm (policy) | FinBERT (Fed speak), LSTM (rates) | 🔴 CRITICAL |
| **ECO 305/313** | FX Model / Trade Flow | Fundamental Agent, Structure Agent | Hot (spot/FW), Warm (BOP data) | LSTM (FX), Transformer (multi-asset) | 🔴 CRITICAL |
| **ECO 321** | General Equilibrium | Signal Aggregator, Portfolio Allocator | Cold (factor matrix) | Convex opt., Quantum (future QAOA) | 🟡 HIGH |
| **ECO 322** | Policy Reaction Function | Fundamental Agent, Structure Agent | Warm (IS-LM params), Cold (DSGE) | LLM (policy analysis), HMM (regime) | 🟡 HIGH |
| **ECO 401** | EM Sovereign Risk | Fundamental Agent | Cold (development indicators) | XGBoost (country score), LLM (policy) | 🟢 MEDIUM |
| **ECO 414/424** | Signal Validation Engine | Reflection Agent, Journal Agent | Cold (backtest DB) | OLS, MLE, Bootstrap, Bayesian | 🔴 CRITICAL |
| **ECO 421** | Fiscal Policy Module | Fundamental Agent | Warm (budget data), Cold (debt) | NLP (budget parsing), Monte Carlo | 🟢 MEDIUM |
| **ECO 422** | Industry Analysis | Fundamental Agent | Cold (financial statements) | NLP (earnings), XGBoost (SCP) | 🟢 MEDIUM |

### 2.2 Cross-Module Concept Flow

```
ECO 101 (Supply/Demand) ─────────────────────────────────────┐
  │                                                           │
  ├──→ Order Book Model (bid = demand, ask = supply)          │
  ├──→ Fair Value Engine (equilibrium price)                  │
  ├──→ Market Impact Model (elasticity)                       │
  └──→ Game Theory (Nash equilibrium) ──→ ECO 201             │
                                                              │
ECO 102 (GDP, CPI, Rates) ───────────────────────────────────┤
  │                                                           │
  ├──→ Macro Factor Model (GDP components as factors)         │
  ├──→ Inflation Monitor (CPI/PPI surprise trading)           ▼
  ├──→ Interest Rate Model (rate expectations)      ┌─────────────────────┐
  └──→ Business Cycle Engine ──→ ECO 205            │  ALPHA STACK CORE   │
                                                    │                     │
ECO 209 (Money & Banking) ──────────────────────────┤  Signal Engine      │
  │                                                 │  Risk Engine        │
  ├──→ FX Market Engine (spot, forward, swap)       │  Execution Engine   │
  ├──→ Central Bank Watcher (policy parsing)        │  Portfolio Engine   │
  ├──→ Monetary Policy Transmission Model           │  Macro Engine       │
  └──→ Banking Sector Health Monitor                │  Regime Engine      │
                                                    │  Validation Engine  │
ECO 414/424 (Econometrics) ─────────────────────────┤  EM Module          │
  │                                                 │  Industry Module    │
  ├──→ Factor Model Estimation (OLS, MLE)           └─────────────────────┘
  ├──→ Signal Validation (hypothesis testing)
  ├──→ Cointegration Engine (pairs trading)
  └──→ Diagnostic Pipeline (Gauss-Markov, heteroscedasticity)
```

---

## 3. Year 1 Foundations: ECO 101–104

### 3.1 ECO 101 — Introduction to Microeconomics (66%, B)
**Module:** Market Microstructure Engine
**Agents:** Liquidity Agent, SMC Agent, Signal Aggregator

#### Concept → Module Mapping

| Concept | Alpha Stack Application | Agent | Model | Priority |
|---------|------------------------|-------|-------|----------|
| **Law of Demand** | Bid side of limit order book = demand curve. As price drops, more buyers willing to buy. | Liquidity Agent | Algorithmic (order book analysis) | HIGH |
| **Law of Supply** | Ask side of order book = supply curve. As price rises, more sellers willing to sell. | Liquidity Agent | Algorithmic | HIGH |
| **Market Equilibrium** | Fair value estimation. Deviations from equilibrium create mean-reversion signals. | Signal Aggregator | XGBoost (fair value scorer) | HIGH |
| **Price Elasticity** | Market impact estimation. Elasticity of demand for an asset determines slippage per unit of order size. | Execution Agent | Almgren-Chriss model | HIGH |
| **Consumer Utility** | Risk preference modeling. Utility functions (CRRA, CARA) determine optimal position sizing. | Entry Agent | RL (PPO — learns implicit utility) | MEDIUM |
| **Budget Constraint** | Capital allocation constraint. Σ(position_value) ≤ total_capital. Margin adds constraints. | Risk Gate Agent | Constraint solver (KKT) | HIGH |
| **Optimal Choice (Tangency)** | Tangency of indifference curve with efficient frontier = optimal portfolio. | Portfolio Allocator | Convex optimizer (Lagrangian) | HIGH |
| **Production Functions** | Alpha production function: Alpha = f(Data, Compute, Strategy, Capital). Diminishing returns apply. | Orchestrator Agent | Resource allocation optimizer | MEDIUM |
| **Cost Curves** | Trading cost modeling: fixed (infrastructure), variable (commissions), marginal (one more trade). | Execution Agent | Cost model (MC = MR optimization) | HIGH |
| **Perfect Competition** | Benchmark model. EMH = perfect competition. Deviations create alpha. | Meta Agent | Market efficiency tests (variance ratio) | MEDIUM |
| **Monopoly/Market Power** | Dominant market maker detection. When one participant controls enough flow to influence prices. | Liquidity Agent | Concentration index (HHI) | MEDIUM |
| **Game Theory (Oligopoly)** | **CORE MULTI-AGENT BRIDGE.** Cournot (quantity/position size), Bertrand (price/spread), Nash Equilibrium. | Orchestrator Agent | MARL (multi-agent RL for Nash eq.) | CRITICAL |

**Data Pipeline Integration:**
- **Hot Path (Redis):** `tick:{symbol}`, `book:{symbol}`, `spread:{symbol}` — real-time order book for supply/demand analysis
- **Warm Path (Streams):** `stream:trades:{symbol}` — trade flow for elasticity estimation
- **Cold Path (TimescaleDB):** `orderbook_snapshots` — historical order book for equilibrium modeling

---

### 3.2 ECO 102 — Introduction to Macroeconomics (61%, B)
**Module:** Macro Signal Engine
**Agent:** Fundamental Agent

#### Concept → Module Mapping

| Concept | Alpha Stack Application | Agent | Model | Priority |
|---------|------------------------|-------|-------|----------|
| **GDP Components (C+I+G+NX)** | Macro factor model. Each component drives different sectors/asset classes. C→consumer, I→industrial, G→defense, NX→forex. | Fundamental Agent | Factor regression (OLS) | HIGH |
| **Inflation (CPI, PPI, Core)** | **PRIMARY MACRO SIGNAL.** Surprise vs. consensus drives rate expectations → forex. Core vs. headline divergence signals transitory vs. persistent. | Fundamental Agent | FinBERT (inflation sentiment), XGBoost (surprise scorer) | CRITICAL |
| **Unemployment** | NFP = highest-impact monthly forex event. Labor market tightness → Fed policy → rates → forex. | Fundamental Agent | NLP (Fed communication parsing) | HIGH |
| **Money Supply (M0, M1, M2)** | Liquidity analysis. M2 growth drives asset prices. QE (expanding M0) is primary risk-asset driver. | Fundamental Agent | Time series (M2 growth tracking) | HIGH |
| **Interest Rate Determination** | **THE MOST IMPORTANT PRICE IN FINANCE.** Drives bonds, equities, forex, commodities. | Fundamental Agent + Structure Agent | LSTM (rate prediction), HMM (regime) | CRITICAL |
| **Monetary Policy (OMO, QE)** | Policy regime detection. Tightening/easing/neutral. QE announcements = binary signals with massive impact. | Fundamental Agent | FinBERT (Fed speak), Regime HMM | CRITICAL |
| **Exchange Rate Determination** | **CORE FOREX DOMAIN.** Interest rate parity, PPP, portfolio balance models. Alpha signals from deviations. | Structure Agent | LSTM (FX forecast), Multi-factor model | CRITICAL |
| **Balance of Payments** | Capital flow tracking. Current account deficits → currency depreciation pressure. Capital flows drive FX. | Fundamental Agent | Flow analysis (BIS, IIF data) | HIGH |
| **Business Cycles** | **MACRO REGIME MODEL.** Early expansion→overweight equities. Contraction→overweight bonds. Trough→add risk. | Structure Agent | HMM (3-state regime), XGBoost (cycle phase) | CRITICAL |

**Data Pipeline Integration:**
- **Hot Path:** `calendar:today` — economic events for today (TTL: 24h, refreshed daily at 00:05 UTC)
- **Warm Path:** `stream:news` — RSS news for sentiment analysis (FinBERT processing)
- **Cold Path:** `economic_calendar` table — historical events with actual/forecast/previous for surprise scoring
- **Cold Path:** `alt_data_snapshots` — GDP proxies, PMI, industrial production from alternative sources

---

### 3.3 ECO 103 — Mathematics for Economists I (70%, A)
**Module:** Portfolio Optimization Engine
**Agent:** Entry Agent, Portfolio Allocator

#### Concept → Module Mapping

| Concept | Alpha Stack Application | Agent | Model | Priority |
|---------|------------------------|-------|-------|----------|
| **Matrix Operations** | Correlation/covariance matrix = foundation of MPT. σ²_p = w'Σw. Matrix multiplication computes portfolio risk. | Portfolio Allocator | Matrix algebra (NumPy/BLAS) | CRITICAL |
| **Determinants** | Portfolio singularity check. det(Σ)=0 means perfect correlation (redundant assets). | Portfolio Allocator | Determinant computation | HIGH |
| **Matrix Inversion** | Markowitz optimization: w* = Σ⁻¹μ. Matrix inversion for optimal portfolio weights. | Portfolio Allocator | Cholesky decomposition (numerically stable) | CRITICAL |
| **Eigenvalues/Eigenvectors** | **PCA — most important dimension reduction in finance.** Eigenvectors of covariance matrix = principal risk factors (PC1=market, PC2=yield curve, PC3=credit). | Structure Agent | Eigenvalue decomposition (scipy.linalg) | CRITICAL |
| **Gaussian Elimination** | Factor model calibration. Solving for factor exposures (betas) in multi-factor model. | Structure Agent | QR decomposition (stable) | HIGH |
| **Linear Independence** | Factor independence testing. Redundant factors (linearly dependent) should be removed to avoid overfitting. | Reflection Agent | Gram-Schmidt orthogonalization | HIGH |
| **Lagrange Multipliers** | **CONSTRAINED PORTFOLIO OPTIMIZATION.** Maximize return subject to risk constraint. λ = price of risk = shadow price. | Portfolio Allocator | Lagrangian optimizer (cvxpy) | CRITICAL |
| **Kuhn-Tucker Conditions** | Position limit optimization. Non-negativity (long-only) or bounded (position limits) constraints. | Risk Gate Agent | KKT solver | HIGH |

**Data Pipeline Integration:**
- **Cold Path:** Covariance matrix computed from `market_data` hypertable (rolling window)
- **Redis Hot:** `indicators:{symbol}:{timeframe}` — pre-computed indicators for factor inputs
- **PostgreSQL:** `strategy_parameters` — version-controlled portfolio weights

---

### 3.4 ECO 104 — Mathematics for Economists II (65%, B)
**Module:** Dynamic Programming Engine
**Agent:** TP Agent, Execution Agent, Reflection Agent

#### Concept → Module Mapping

| Concept | Alpha Stack Application | Agent | Model | Priority |
|---------|------------------------|-------|-------|----------|
| **Difference Equations** | AR(p) models ARE difference equations. yₜ = ayₜ₋₁ + b. Mean reversion if |a|<1. | Structure Agent | ARIMA model (statsmodels) | HIGH |
| **Differential Equations (ODEs)** | Black-Scholes IS a PDE. dS = μSdt + σSdW (geometric Brownian motion). Continuous-time finance models. | Risk Engine | SDE solver, Black-Scholes calculator | HIGH |
| **Dynamic Programming (Bellman)** | **FOUNDATION OF REINFORCEMENT LEARNING.** V(x) = max{u(x,a) + βV(x')}. Optimal trade execution, portfolio rebalancing, optimal stopping. | TP Agent, Execution Agent | PPO (position sizing), DQN (TP), Q-learning (execution) | CRITICAL |
| **Envelope Theorem** | Sensitivity of optimal portfolio to parameter changes. How much does Sharpe ratio change when market conditions shift? | Reflection Agent | Sensitivity analyzer | MEDIUM |
| **Implicit Function Theorem** | Implied volatility computation. Inverting Black-Scholes to find σ from observed option price. | Risk Engine | Newton-Raphson IV solver | HIGH |
| **Convex Sets and Functions** | Portfolio optimization is convex (mean-variance). Convexity guarantees global optimum. Non-convex extensions (transaction costs) need specialized solvers. | Portfolio Allocator | Convex optimizer (cvxpy, scipy.optimize) | HIGH |

**Data Pipeline Integration:**
- **Hot Path:** `position:{account_id}:{symbol}` — current positions for RL state
- **Warm Path:** `stream:signals` — signal history for RL reward computation
- **Cold Path:** `trades` table — completed trades for RL training episodes

---

## 4. Year 2 Core: ECO 201–210

### 4.1 ECO 201 — Intermediate Microeconomics (53%, C)
**Module:** Multi-Agent Coordinator
**Agent:** Orchestrator Agent, all agents

#### Concept → Module Mapping

| Concept | Alpha Stack Application | Agent | Model | Priority |
|---------|------------------------|-------|-------|----------|
| **Utility Maximization** | Objective function design. Different "preferences" (risk aversion) produce different optimal portfolios. Inverse RL infers utility from expert behavior. | Entry Agent | PPO (learns utility from reward) | HIGH |
| **Indifference Curves / MRS** | Risk-return indifference surfaces. Tangency with efficient frontier = optimal portfolio. Multi-dimensional beyond textbook 2D. | Portfolio Allocator | Multi-objective optimizer | HIGH |
| **Budget Constraints** | Capital constraints. With $7 starting capital, every allocation is constrained. Margin requirements add constraints. | Risk Gate Agent | Constraint solver | HIGH |
| **Income/Substitution Effects** | Price impact decomposition. When system executes large order, price change decomposes into substitution (other traders substitute away) and income (remaining capital changes). | Execution Agent | Almgren-Chriss impact model | MEDIUM |
| **Production Functions / Returns to Scale** | Strategy capacity. Small strategies may have increasing returns (better fills), but market impact causes decreasing returns at scale. | Orchestrator Agent | Capacity model | HIGH |
| **Cost Curves (MC, AC)** | Trading cost analysis. Marginal cost per trade (spread + commission + slippage). When MC > AC, trading frequency is too high. | Execution Agent | Cost model | HIGH |
| **Profit Maximization (MR=MC)** | Optimal trade frequency. Trade until marginal expected profit = marginal cost. Overtrading occurs below this threshold. | Orchestrator Agent | MR=MC optimizer | HIGH |
| **Market Structures** | Market microstructure classification. Forex = oligopoly (major banks as dealers). Crypto = closer to perfect competition. Different structures require different execution strategies. | Execution Agent | Structure classifier | HIGH |
| **Nash Equilibrium** | **MARKET EQUILIBRIUM DETECTION.** When market reaches Nash equilibrium, no trader can improve by changing strategy. System detects when equilibrium is disrupted and trades the transition. | Orchestrator Agent | MARL (Nash finder) | CRITICAL |
| **Prisoner's Dilemma** | Market manipulation and cooperation. Traders face prisoner's dilemmas (cooperate = orderly markets vs. defect = front-running). System must be robust to defection. | Risk Gate Agent | Game-theoretic robustness | HIGH |
| **Signaling and Screening** | Order flow analysis. Large institutional orders "signal" information. Smart order routing "screens" market conditions. Informed vs. uninformed trading detection. | Liquidity Agent | Informed trading ratio (PIN model) | HIGH |
| **Asymmetric Information** | Adverse selection in market-making. System must detect when trading against informed flow. Glosten-Milgrom spread decomposition. | Liquidity Agent | Spread decomposition model | HIGH |

**Data Pipeline Integration:**
- **Hot Path:** `state:positions`, `state:portfolio`, `state:risk_limits` — shared state for multi-agent coordination
- **Redis Streams:** `pipeline.*` — agent communication channels
- **PostgreSQL:** `agent_memories`, `trade_episodes` — episodic memory for learning

---

### 4.2 ECO 205 — Intermediate Macroeconomics (67%, B)
**Module:** Business Cycle / Regime Detection Engine
**Agent:** Structure Agent, Fundamental Agent

#### Concept → Module Mapping

| Concept | Alpha Stack Application | Agent | Model | Priority |
|---------|------------------------|-------|-------|----------|
| **IS Curve** | Interest rate-output dynamics. How rate changes affect economic activity and currency strength. Steep IS = economy sensitive to rates. | Structure Agent | IS curve estimator (rolling regression) | HIGH |
| **LM Curve** | Monetary policy transmission. Money supply decisions → interest rates → exchange rates. LM shifts = Fed policy changes. | Fundamental Agent | LM curve tracker (M2, reserves, SOFR) | HIGH |
| **IS-LM Equilibrium** | Policy impact modeling. Fiscal stimulus (IS shift right) → higher output, higher rates, currency appreciation. Direct trading signal. | Fundamental Agent | Policy impact model | HIGH |
| **AD-AS Model** | Inflation-output tradeoff. AD shifts (fiscal/monetary) change both inflation and output. Supply shocks → stagflation. | Structure Agent | AD-AS framework (regime classifier) | HIGH |
| **Short-Run / Long-Run AS** | Output gap estimation. Positive gap → inflationary pressure → tighter policy → currency appreciation. | Structure Agent | Output gap estimator (HP filter, production function) | HIGH |
| **Supply Shocks / Stagflation** | Stagflation detection. Worst environment for traditional portfolios. System shifts to inflation-hedging assets. | Structure Agent | Supply shock detector (commodity prices, shipping data) | CRITICAL |
| **Mundell-Fleming Model** | Exchange rate regime analysis. Policy effectiveness differs for fixed vs. floating regimes. Under floating: monetary policy powerful. Under fixed: fiscal policy powerful. | Structure Agent | Regime classifier (de facto exchange rate regime) | HIGH |
| **PPP** | Long-term mean reversion anchor. Fundamental fair value estimate for currency pairs. Pairs deviating significantly from PPP may revert. | Structure Agent | PPP deviation tracker | MEDIUM |
| **Interest Rate Parity** | **CARRY TRADE FOUNDATION.** Carry exploits UIP deviations. If high-interest currency doesn't depreciate as much as differential suggests, carry profits. | Structure Agent | UIP deviation monitor | CRITICAL |
| **Business Cycle Phases** | **REGIME-BASED TRADING.** Different currency factors (carry, momentum, value) perform differently at each phase. | Structure Agent | HMM (4-phase cycle detector) | CRITICAL |
| **Leading/Coincident/Lagging Indicators** | Economic indicator signals. Yield curve, PMI, building permits, consumer confidence for early cycle signals. | Fundamental Agent | Composite leading indicator (weighted index) | HIGH |
| **Taylor Rule** | **RATE EXPECTATION MODELING.** i = r* + π + 0.5(π - π*) + 0.5(y - y*). Deviations between Taylor Rule rate and actual rate signal future rate moves. | Fundamental Agent | Taylor Rule calculator, Fed policy predictor | CRITICAL |
| **Fiscal Multiplier** | Fiscal policy impact on currencies. High multiplier → stronger equity impact. Adjusts for monetary accommodation and economic slack. | Fundamental Agent | Multiplier estimator (country-specific) | HIGH |
| **QE and Unconventional Policy** | QE impact modeling. QE announcements cause predictable currency effects (typically depreciation of QE currency). Monitor central bank balance sheets. | Fundamental Agent | QE impact model, balance sheet tracker | HIGH |

**Data Pipeline Integration:**
- **Hot Path:** `regime:{symbol}` — current regime state (set by Meta Agent)
- **Warm Path:** `stream:news` — central bank communications for policy parsing
- **Cold Path:** `economic_calendar` — historical events for Taylor Rule estimation
- **Cold Path:** `alt_data_snapshots` — PMI, yield curve, consumer confidence

---

### 4.3 ECO 209 — Money and Banking (65%, B) 🔴 CRITICAL
**Module:** Forex Market Engine / Central Bank Watcher
**Agent:** Fundamental Agent, Structure Agent

#### Concept → Module Mapping

| Concept | Alpha Stack Application | Agent | Model | Priority |
|---------|------------------------|-------|-------|----------|
| **Functions of Money** | Currency strength assessment. A currency failing any function (medium of exchange, unit of account, store of value) depreciates. Monitor inflation expectations, currency substitution, black market premiums. | Fundamental Agent | Currency health score (composite) | HIGH |
| **Money Supply Measures** | Money supply growth as currency signal. Rapid M2 growth relative to GDP → future inflation → currency depreciation. Track M2 growth rates across countries. | Fundamental Agent | M2 growth tracker, inflation forecaster | CRITICAL |
| **Quantity Theory (MV=PQ)** | Inflation forecasting model. If money supply grows faster than real output, inflation follows → currency depreciation. Velocity estimation is key. | Fundamental Agent | MV=PQ model with velocity estimator | HIGH |
| **Fractional Reserve Banking** | Credit creation cycle. Expansion (banks lending freely) and contraction (banks tightening). Monitor bank lending standards and credit growth. | Fundamental Agent | Credit cycle tracker (lending surveys, NPL ratios) | HIGH |
| **Bank Balance Sheets / Capital Adequacy** | Banking sector health as systemic risk indicator. Weak banking (low capital adequacy, high NPLs) → currency risk. | Fundamental Agent | Banking health index (capital ratio, NPL, ROA) | HIGH |
| **NPL Ratios** | Crisis predictor. Rising NPLs predict banking stress and potential currency crises. Monitor NPL ratios for EM countries. | Fundamental Agent | NPL trend monitor, crisis early warning | CRITICAL |
| **Central Bank Functions** | Central bank credibility as currency anchor. Independent banks with clear mandates → stable currencies. Monitor independence indicators and policy credibility. | Fundamental Agent | Central bank credibility score | HIGH |
| **Monetary Policy Tools** | Policy tool impact on currencies. OMOs most common and predictable. Track open market operations and market impact. | Fundamental Agent | OMO tracker, policy impact model | HIGH |
| **Inflation Targeting** | **INFLATION SURPRISE TRADING.** When inflation deviates from target, predict central bank response (rate change) and trade resulting currency move. CPI surprises = high-impact events. | Fundamental Agent | CPI forecaster, surprise scorer | CRITICAL |
| **Interest Rate Channel** | **RATE DECISION TRADING.** Most direct channel. Higher rates → currency appreciation. Second-order effects (slower growth → eventual weakness). | Fundamental Agent + Structure Agent | Rate impact model (immediate + lagged) | CRITICAL |
| **Exchange Rate Channel** | **DIRECT FOREX SIGNAL.** Interest rate differential → capital flows → exchange rate. Monitor rate differentials, capital flow data, trade balances. | Structure Agent | FX channel model (rate diff → flow → FX) | CRITICAL |
| **Credit Channel** | Credit growth signals. Often more powerful than interest rate channel in developing economies. Monitor bank lending surveys and credit growth. | Fundamental Agent | Credit impulse indicator | HIGH |
| **Money Markets / Capital Markets** | Yield curve analysis. Short end = current policy. Long end = growth/inflation expectations. Curve shape (normal, flat, inverted) = powerful economic signal. | Structure Agent | Yield curve shape classifier (HMM) | HIGH |
| **Foreign Exchange Markets** | **CORE ALPHA STACK DOMAIN.** Understanding forex microstructure (dealer networks, ECN/STP, bid-ask spreads, liquidity pools) is fundamental to execution quality. | Liquidity Agent, Execution Agent | Order book analysis, execution algorithms | CRITICAL |
| **Derivatives Markets** | Hedging and leverage tools. FX forwards for hedging, options for tail risk, swaps for carry trade execution. | Risk Engine | Derivatives pricing (Black-Scholes, Garman-Kohlhagen) | HIGH |
| **Bank Runs / Systemic Risk** | Crisis detection and trading. Monitor interbank rates, CDS spreads, deposit outflows for early crisis detection. Safe-haven flows during crises. | Monitor Agent | Crisis indicator composite (CDS, interbank spread) | HIGH |

**Data Pipeline Integration:**
- **Hot Path:** `tick:{symbol}` — real-time FX rates, `funding:{symbol}` — funding rates for carry
- **Warm Path:** `stream:news` — central bank communications, `calendar:today` — rate decisions
- **Cold Path:** `market_data` — historical FX rates for PPP/UIP estimation
- **Cold Path:** `onchain_events` — for crypto monetary analysis (stablecoin supply, DeFi yields)

---

## 5. Year 3 Advanced: ECO 305–322

### 5.1 ECO 305/313 — International Economics (44%/47%, D) 🔴 CRITICAL
**Module:** FX Model / Trade Flow Engine
**Agent:** Fundamental Agent, Structure Agent

#### Concept → Module Mapping

| Concept | Alpha Stack Application | Agent | Model | Priority |
|---------|------------------------|-------|-------|----------|
| **Comparative Advantage** | Portfolio specialization. Each strategy has "comparative advantage" — some excel at momentum, others at mean-reversion. Orchestrator allocates capital based on relative edge. | Orchestrator Agent | Strategy allocator (comparative advantage scoring) | HIGH |
| **Opportunity Cost / PPF** | Capital allocation frontier. Efficient frontier of portfolio allocations. Allocating to Strategy A means less for Strategy B. | Portfolio Allocator | Efficient frontier solver (MVO) | HIGH |
| **Gains from Trade / Terms of Trade** | Bid-ask spread analysis. "Terms of trade" between buyer and seller = bid-ask spread. Cross-asset "terms of trade" drives relative value strategies. | Execution Agent | Spread analyzer, relative value model | MEDIUM |
| **Tariffs** | Transaction cost modeling. Tariffs = transaction costs, commissions, exchange fees. All "tariffs" on execution must be modeled to calculate net alpha. | Execution Agent | Transaction cost analyzer (TCA) | HIGH |
| **Quotas / VERs** | Position limits and risk caps. Quotas = position size limits. VERs = self-imposed exposure limits. Risk Engine enforces both. | Risk Gate Agent | Position limit enforcer | HIGH |
| **Exchange Rate Determination** | **FX MODULE CORE.** Multiple theories: PPP, interest rate parity, monetary model. Alpha signals from deviations from these models. | Structure Agent | Multi-model FX forecaster (ensemble) | CRITICAL |
| **Spot and Forward Rates** | Derivatives pricing. Forward rates = inputs to FX forwards, futures, options. Covered interest rate parity for mispriced forwards. | Risk Engine | Forward rate calculator, CIP arb detector | HIGH |
| **Exchange Rate Regimes** | Regime detection. Fixed → mean-reversion opportunities. Floating → trend-following. Managed float → detect intervention patterns. | Structure Agent | Regime classifier (de facto regime HMM) | CRITICAL |
| **Current Account** | Macro data pipeline. Persistent deficits → currency weakness. Trade balance data feeds commodity demand models. | Fundamental Agent | BOP tracker, trade balance monitor | HIGH |
| **Capital/Financial Account** | Capital flow tracker. FPI, FDI as leading indicators. Large portfolio inflows → bullish EM. Capital flight → defensive. | Fundamental Agent | Capital flow model (EPFR, BIS data) | CRITICAL |
| **BOP Equilibrium/Disequilibrium** | Global imbalances monitor. Large surpluses → reserve accumulation → SWF flows → asset price effects. | Fundamental Agent | Imbalance monitor, adjustment mechanism predictor | HIGH |
| **Heckscher-Ohlin Theory** | Factor model framework. System "exports" strategies that exploit its "abundant factors" (superior data, faster execution). | Orchestrator Agent | Factor endowment analyzer | MEDIUM |
| **Stolper-Samuelson** | Winner/loser analysis in regime changes. When market structure changes, identify which strategies benefit and which are hurt. | Reflection Agent | Regime impact analyzer | MEDIUM |
| **Optimal Tariff Theory** | Optimal spread strategy. Market-makers face analogous problem: setting optimal spread that maximizes revenue while maintaining flow. | Execution Agent | Optimal spread calculator (RL) | HIGH |
| **Currency Crises** | Crisis detection. Third-generation crisis models. Monitor reserve coverage, current account, capital flight indicators. | Monitor Agent | Crisis early warning system (composite index) | HIGH |

**Data Pipeline Integration:**
- **Hot Path:** `tick:{symbol}` — spot FX, `funding:{symbol}` — carry trade signals
- **Warm Path:** `stream:news` — trade policy news, BOP data releases
- **Cold Path:** `market_data` — historical FX for PPP/UIP/cointegration analysis
- **Cold Path:** `economic_calendar` — BOP releases, trade balance data

---

### 5.2 ECO 321 — Advanced Microeconomics (51%, C)
**Module:** General Equilibrium / Pricing Engine
**Agent:** Signal Aggregator, Portfolio Allocator

#### Concept → Module Mapping

| Concept | Alpha Stack Application | Agent | Model | Priority |
|---------|------------------------|-------|-------|----------|
| **Utility Functions (Advanced)** | Objective function design. Sharpe ratio, risk-adjusted return, or custom metric. Different risk aversion levels → different optimal portfolios. | Entry Agent | Utility function designer (CRRA, CARA, mean-variance) | HIGH |
| **Utility Maximization / Demand** | Portfolio optimization (MVO). Maximize expected utility subject to budget and risk constraints. Lagrangian optimization. | Portfolio Allocator | Mean-variance optimizer (cvxpy) | CRITICAL |
| **Slutsky Equation** | Price impact decomposition. Decompose execution price change into substitution and income effects. | Execution Agent | Almgren-Chriss decomposition | HIGH |
| **Duality (Indirect Utility, Expenditure)** | Cost-minimization for target return. Minimum-risk portfolio for target return = dual problem. Efficient frontier traced by solving dual for different targets. | Portfolio Allocator | Dual optimizer | HIGH |
| **Production Functions (Advanced)** | Strategy production functions. Map inputs (data, compute, research) to outputs (alpha). Returns to scale analysis. | Orchestrator Agent | Production function estimator | MEDIUM |
| **Cost Minimization** | Infrastructure cost optimization. Fixed (infrastructure) + variable (compute) costs. Cloud vs. on-premise = long-run vs. short-run. | Orchestrator Agent | Cost optimizer | MEDIUM |
| **Profit Maximization / Supply** | Strategy capacity and optimal sizing. MR = MC for optimal trade frequency. Market-making supply (ask) and demand (bid) curves. | Execution Agent | MR=MC optimizer, market-making model | HIGH |
| **Perfect Competition** | EMH benchmark. Alpha exists only to the extent markets are NOT perfectly competitive. Monitor market efficiency metrics. | Meta Agent | Efficiency tests (autocorrelation, variance ratio) | MEDIUM |
| **Monopoly / Price Discrimination** | Information monopoly. Unique data sources or analytical capabilities. Price discrimination = dynamic execution pricing. | Execution Agent | Dynamic pricing model | MEDIUM |
| **Oligopoly / Game Theory** | Competitive strategy. Trading industry is oligopoly (Citadel, Jane Street, Two Sigma). Model competitor behavior. | Orchestrator Agent | Competitor behavior model (Cournot/Bertrand/Stackelberg) | HIGH |
| **Walrasian General Equilibrium** | Cross-asset equilibrium pricing. No-arbitrage conditions = financial equivalent of Walrasian equilibrium. Detect disequilibria for arbitrage. | Signal Aggregator | No-arbitrage checker, cross-asset pricer | HIGH |
| **Pareto Efficiency / Welfare Theorems** | Portfolio Pareto efficiency. Efficient frontier = Pareto efficient portfolios. Can't improve return without increasing risk. | Portfolio Allocator | Efficient frontier computer | HIGH |
| **Market Failures (Info Asymmetry)** | **INFORMATION ASYMMETRY TRADING.** System profits by identifying and exploiting information asymmetries before they're resolved. Adverse selection in market-making. | Liquidity Agent | Informed trading detector (PIN, VPIN) | CRITICAL |

---

### 5.3 ECO 322 — Advanced Macroeconomics (62%, B)
**Module:** DSGE / Policy Reaction Function Engine
**Agent:** Fundamental Agent, Structure Agent

#### Concept → Module Mapping

| Concept | Alpha Stack Application | Agent | Model | Priority |
|---------|------------------------|-------|-------|----------|
| **GDP Components (Advanced)** | Macro data pipeline. Each component tracked independently. C→retail sales, I→capex/PMI, G→budget data, NX→trade balance. | Fundamental Agent | GDP nowcaster (high-frequency data) | HIGH |
| **Inflation Measurement (Advanced)** | Inflation signal engine. CPI-PPI divergence = margin pressure. Core vs. headline = transitory vs. persistent. TIPS breakevens = market-implied. | Fundamental Agent | Multi-measure inflation tracker | CRITICAL |
| **Unemployment / Phillips Curve** | Labor market signal module. Initial claims, ADP, JOLTS, wage growth. Modified Phillips Curve helps forecast inflation. | Fundamental Agent | Labor market composite, Phillips Curve estimator | HIGH |
| **IS-LM (Advanced)** | Interest rate sensitivity. IS curve slope = economy's rate sensitivity. Steep IS → position for rate moves. Flat IS → rate-insensitive sectors outperform. | Structure Agent | IS curve real-time estimator | HIGH |
| **LM Curve / Liquidity** | Liquidity signal engine. M2, reserve balances, money market rates. LM shifts = Fed policy changes. SOFR, repo rates = real-time LM indicators. | Fundamental Agent | Liquidity condition monitor | HIGH |
| **Policy Mix** | Fiscal-monetary policy tracker. Crowding out effects matter for bond positioning. Track fiscal deficits, Treasury issuance, Fed purchases. | Fundamental Agent | Policy impulse model (fiscal + monetary) | HIGH |
| **AD-AS (Advanced)** | Demand/supply macro signals. Demand shocks → equity bullish, bonds bearish. Supply shocks → stagflation (both fall). | Structure Agent | Demand/supply shock classifier | HIGH |
| **Stagflation Detection** | Regime classification. Stagflation = worst environment for traditional portfolios. Shift to commodities, TIPS, gold, real assets. | Structure Agent | Stagflation detector (HMM with supply shock features) | CRITICAL |
| **Business Cycle Theory (RBC, NK)** | Cycle positioning engine. RBC technology shocks → growth stocks. NK demand shocks → value stocks. Both frameworks for robust identification. | Structure Agent | Dual-framework cycle classifier | HIGH |
| **Solow Growth Model** | Long-term return forecasting. Long-run equity returns = dividend yield + earnings growth (driven by TFP). Countries with higher TFP growth → higher expected returns. | Fundamental Agent | TFP growth estimator, long-term return model | MEDIUM |
| **Endogenous Growth (Romer, Lucas)** | R&D alpha measurement. Knowledge spillovers between strategies create increasing returns. Track R&D productivity. | Reflection Agent | Innovation productivity tracker | MEDIUM |
| **Taylor Rule (Advanced)** | Fed policy prediction. Compare Taylor Rule-implied rate vs. actual rate. Deviations = policy stance (hawkish/dovish). Drives rates and equity positioning. | Fundamental Agent | Taylor Rule calculator with time-varying parameters | CRITICAL |
| **Fiscal Multiplier (Advanced)** | Fiscal impact model. Estimate multipliers for different spending types. High multiplier spending → stronger equity impact. Adjust for monetary accommodation. | Fundamental Agent | Country-specific multiplier estimator | HIGH |
| **Ricardian Equivalence** | Debt sustainability monitor. If Ricardian equivalence holds → deficits don't stimulate → bond yields rise. If not → deficits stimulate → equity bullish. | Fundamental Agent | Ricardian equivalence tester | MEDIUM |

---

## 6. Year 4 Specialized: ECO 401–424

### 6.1 ECO 401 — Economics of Development
**Module:** Emerging Market Sovereign Risk Module
**Agent:** Fundamental Agent

#### Concept → Module Mapping

| Concept | Alpha Stack Application | Agent | Model | Priority |
|---------|------------------------|-------|-------|----------|
| **Classical Growth Models** | Macro regime detection. Classify economies into growth regimes (frontier, emerging, developing, developed) to adjust sovereign risk premia. | Fundamental Agent | Development stage classifier (satellite + macro data) | MEDIUM |
| **Structural Change (Lewis)** | Sector rotation engine. Track structural transformation (agriculture→manufacturing→services) to position sector-tilted equity baskets. Lewis turning point = wage inflation signal. | Fundamental Agent | Structural shift detector (labor data, GDP composition) | MEDIUM |
| **Endogenous Growth** | Innovation alpha signal. Score countries on R&D intensity, patent filings, STEM workforce. High endogenous growth → overweight equities. | Fundamental Agent | Innovation score (patents, R&D, education data) | MEDIUM |
| **Dependency Theory** | Geopolitical risk & trade dependency. Map core-periphery trade dependencies for supply chain shock vulnerability. | Fundamental Agent | Trade dependency graph (network analysis) | LOW |
| **Poverty / Inequality** | Consumer demand forecasting. Poverty metrics feed consumer demand models. Kuznets curve = social stability risk score. | Fundamental Agent | Consumer demand model (poverty-adjusted) | LOW |
| **HDI / Capabilities** | Country quality score. HDI and capability metrics as supplementary country risk/quality scores. High HDI → lower risk premium. | Fundamental Agent | Country quality composite score | MEDIUM |
| **Trade Liberalization** | Trade flow alpha signal. Model comparative advantage shifts in real-time. Export basket composition = fundamental currency signal. | Fundamental Agent | Trade flow model (export composition tracker) | MEDIUM |
| **Terms of Trade / Prebisch-Singer** | Commodity currency model. Terms of trade movements as primary drivers of commodity currency pairs. Structural headwinds for commodity EM currencies. | Structure Agent | Terms of trade tracker (commodity price indices) | HIGH |
| **Financial Liberalization** | Financial regime signal. Countries moving from repressed to liberalized → structural shifts in capital flows, banking profitability. Multi-year alpha signal. | Fundamental Agent | Financial liberalization score (regulatory tracker) | MEDIUM |
| **Capital Flight / Debt Sustainability** | Sovereign credit risk module. Continuous DSA using IMF frameworks. Capital flight indicators (errors & omissions, parallel FX premium). | Fundamental Agent | DSA model (Monte Carlo), capital flight detector | HIGH |
| **Microfinance / Financial Inclusion** | Fintech alpha. Rapid financial inclusion (mobile money adoption) = early-stage investment opportunity. | Fundamental Agent | Financial inclusion tracker (mobile money volumes) | LOW |
| **Aid Effectiveness** | Aid flow tracking. Large aid inflows affect exchange rates (Dutch disease risk), fiscal space. | Fundamental Agent | Aid flow monitor | LOW |
| **Institutional Quality** | Institutional quality premium. World Governance Indicators, Ease of Doing Business. Improving institutions → structural currency appreciation. | Fundamental Agent | Institutional quality score (WGI, EoDB) | HIGH |

---

### 6.2 ECO 414/424 — Econometrics 🔴 CRITICAL
**Module:** Signal Validation Engine
**Agent:** Reflection Agent, Journal Agent

#### Concept → Module Mapping

| Concept | Alpha Stack Application | Agent | Model | Priority |
|---------|------------------------|-------|-------|----------|
| **OLS Estimation** | **CORE SIGNAL ESTIMATION.** Regressing returns on risk factors to decompose into alpha and beta. Every signal starts as an OLS regression. | Reflection Agent | OLS (statsmodels, scipy) | CRITICAL |
| **Gauss-Markov / BLUE** | Signal quality assessment. Test whether factor regressions satisfy assumptions. Apply robust standard errors (Newey-West, White) when violated. | Reflection Agent | Diagnostic test suite | CRITICAL |
| **Hypothesis Testing** | **SIGNAL SIGNIFICANCE FILTER.** Every alpha signal must pass t-test (t-stat > 2.0) before inclusion. Multiple testing corrections (Bonferroni, FDR). | Reflection Agent | Hypothesis testing framework | CRITICAL |
| **R² / Adjusted R²** | Signal power metric. Distinguish in-sample R² (optimistic) from out-of-sample R² (realistic). Track information ratio as investment-relevant metric. | Reflection Agent | R² tracker (in-sample vs. OOS) | HIGH |
| **Multiple Regression** | Multi-factor model framework. Rᵢ = αᵢ + β₁(Market) + β₂(Size) + β₃(Value) + β₄(Momentum) + εᵢ. Each β isolates pure factor exposure. | Reflection Agent | Multi-factor regression engine | CRITICAL |
| **Multicollinearity** | Factor orthogonalization. Handle correlated factors using Gram-Schmidt or PCA. VIF analysis to detect redundancy. | Reflection Agent | Orthogonalization module (PCA, Gram-Schmidt) | HIGH |
| **Dummy Variables / Structural Breaks** | Regime-switching models. Capture regime effects (bull/bear, risk-on/off). Chow test, CUSUM for structural break detection. | Structure Agent | Structural break detector (Chow, CUSUM) | HIGH |
| **Omitted Variable Bias** | Signal specification testing. Run horseraces between competing specs. AIC/BIC for model selection. | Reflection Agent | Model selection framework (AIC, BIC, cross-validation) | HIGH |
| **Heteroscedasticity** | Volatility-weighted signal estimation. GARCH for time-varying variance. WLS or Feasible GLS to weight observations by precision. | Reflection Agent | GARCH model, WLS estimator | CRITICAL |
| **Autocorrelation** | Time series signal correction. Newey-West standard errors for all time series regressions. Cochrane-Orcutt or GLS for efficient estimation. | Reflection Agent | Newey-West SE calculator, GLS estimator | CRITICAL |
| **Endogeneity / IV / 2SLS** | Causal inference module. Establish causal relationships using instruments. Prevent trading on spurious correlations. | Reflection Agent | 2SLS estimator, instrument validity tests | HIGH |
| **Simultaneity** | Market microstructure model. Order flow ↔ price impact = simultaneous relationship. 2SLS identifies causal direction. | Liquidity Agent | Structural estimation (2SLS) | HIGH |
| **Stationarity / Unit Roots** | Data preprocessing pipeline. Test every input for stationarity (ADF, Phillips-Perron). Non-stationary → difference or detrend. Prevent spurious regression. | Reflection Agent | ADF test, KPSS test | CRITICAL |
| **Cointegration** | **PAIRS TRADING ENGINE.** Test all candidate pairs for cointegration (Engle-Granger, Johansen). Only trade confirmed cointegrated pairs. Error correction term = mean-reversion speed. | Structure Agent | Cointegration test suite (Engle-Granger, Johansen), ECM | CRITICAL |
| **Granger Causality** | Lead-lag signal discovery. Find lead-lag relationships across markets (copper→AUD/USD, VIX→S&P). Tradeable signals from leading market. | Structure Agent | Granger causality test, transfer entropy | HIGH |
| **ARIMA Models** | Baseline forecasting engine. ARIMA as baseline for all time series. More complex models must beat ARIMA out-of-sample. | Structure Agent | ARIMA model (auto.arima), forecast evaluator | HIGH |
| **Logit / Probit** | Binary event prediction. Will central bank hike? Will currency devalue? Probability estimates for binary events. | Fundamental Agent | Logit/Probit models (sklearn, statsmodels) | HIGH |
| **Tobit / Truncated Regression** | Censored return modeling. Portfolio returns with stop-losses/take-profits are censored. Estimate true underlying return distribution. | Reflection Agent | Tobit model (for censored returns) | MEDIUM |
| **MLE** | Core model estimation. GARCH parameters, HMM parameters, copula parameters, option pricing calibration. | Reflection Agent | MLE optimizer (scipy.optimize, statsmodels) | CRITICAL |
| **Bootstrap / Permutation Tests** | Robust backtest validation. Confidence intervals without distributional assumptions. Test whether Sharpe ratios are significantly different from zero. | Reflection Agent | Bootstrap engine (resampling framework) | CRITICAL |
| **Multiple Testing Corrections** | Anti-data-mining framework. Bonferroni for screening, BH-FDR for discovery. Deflated Sharpe ratios (Bailey & López de Prado). | Reflection Agent | FDR controller, deflated Sharpe calculator | CRITICAL |

**Data Pipeline Integration:**
- **Cold Path (TimescaleDB):** `trades` table — all completed trades for backtest validation
- **Cold Path:** `signals` table — signal history for factor model estimation
- **Cold Path:** `market_data` — historical OHLCV for time series analysis
- **PostgreSQL:** `pattern_reliability`, `signal_weights` — updated by Reflection Agent after validation

---

### 6.3 ECO 421 — Public Finance and Fiscal Policy
**Module:** Fiscal Policy / Sovereign Credit Module
**Agent:** Fundamental Agent

#### Concept → Module Mapping

| Concept | Alpha Stack Application | Agent | Model | Priority |
|---------|------------------------|-------|-------|----------|
| **Public Goods / Market Failure** | Government spending classification. Infrastructure spending has multiplier effects; defense may not. Classification improves fiscal impact modeling. | Fundamental Agent | Spending classifier (NLP on budget documents) | MEDIUM |
| **Externalities / Pigouvian Tax** | Carbon tax / ESG signal. Track carbon tax implementation globally. Directly affects energy companies, manufacturing costs, trade competitiveness. | Fundamental Agent | Carbon tax impact model | MEDIUM |
| **Taxation Theory (Laffer, Incidence)** | Tax policy impact model. Model impact of tax changes on corporate earnings, consumer spending, investment. Tax incidence analysis. | Fundamental Agent | Tax impact model (sector-specific) | MEDIUM |
| **Cost-Benefit Analysis** | Infrastructure investment signal. Monitor government CBA of major projects. Approved projects with positive NPV → future economic activity in related sectors. | Fundamental Agent | Project approval tracker (NLP on government documents) | LOW |
| **Tax Types** | Tax regime classifier. Classify countries by tax structure. Affects corporate profitability, consumer spending, investment decisions. | Fundamental Agent | Tax regime database (country-level) | MEDIUM |
| **Tax Revenue Mobilization** | Fiscal capacity indicator. Tax-to-GDP ratios as sovereign credit indicator. Improving mobilization → improving fiscal sustainability. | Fundamental Agent | Tax-to-GDP tracker | HIGH |
| **Tax Evasion / Avoidance** | Profit shifting risk score. Estimate tax risk of multinationals with significant operations in tax havens. OECD BEPS risk. | Fundamental Agent | Profit shifting detector (subsidiary profitability analysis) | LOW |
| **Budget Process** | Fiscal calendar trading. Track budget cycles globally. Budget announcements move markets. Trade around fiscal events. | Fundamental Agent | Budget event calendar, NLP budget parser | HIGH |
| **Fiscal Multiplier (Advanced)** | Fiscal stimulus impact model. Estimate multipliers for different spending types and conditions. During recessions, infrastructure spending has high multipliers. | Fundamental Agent | Real-time multiplier estimator | HIGH |
| **Public Debt Management** | Sovereign bond pricing model. Continuous DSA. Track debt-to-GDP, primary balance, r-g differential, contingent liabilities. | Fundamental Agent | DSA model (Monte Carlo simulation) | CRITICAL |
| **Fiscal Federalism** | Sub-national risk assessment. Track provincial/state fiscal health. In federal systems, sub-national distress can affect sovereign. | Fundamental Agent | Sub-national fiscal health monitor | LOW |
| **Fiscal Rules** | Fiscal rule compliance monitor. Track compliance globally. Countries approaching limits face policy constraint. | Fundamental Agent | Fiscal rule compliance tracker | HIGH |
| **Crisis Fiscal Response** | Crisis fiscal response tracker. Size of stimulus, composition, financing method. Drives recovery speed, inflation, sovereign credit expectations. | Fundamental Agent | Crisis response analyzer (size, composition, financing) | HIGH |
| **Sovereign Debt Restructuring** | Distressed debt trading module. Identify sovereigns approaching default. Price distressed debt using recovery rate models. | Fundamental Agent | Default probability model (early warning indicators) | HIGH |

---

### 6.4 ECO 422 — Economics of Industry
**Module:** Industry Analysis / Earnings Model Module
**Agent:** Fundamental Agent

#### Concept → Module Mapping

| Concept | Alpha Stack Application | Agent | Model | Priority |
|---------|------------------------|-------|-------|----------|
| **Perfect Competition** | Commodity market model. Commodity markets ≈ perfectly competitive. Alpha from predicting supply/demand shifts, not firm-level analysis. | Fundamental Agent | Supply/demand model (satellite + futures data) | MEDIUM |
| **Monopoly / Market Power** | Monopoly premium signal. Identify companies with market power (high margins, low elasticity, network effects). Persistent profits → premium valuation. | Fundamental Agent | Market power scorer (HHI, margin analysis) | HIGH |
| **Oligopoly / Game Theory** | Industry博弈 model. Predict competitive responses in oligopolistic industries (airlines, telecoms, banking, semiconductors). | Fundamental Agent | Game-theoretic earnings model | HIGH |
| **Monopolistic Competition** | Brand value / differentiation signal. Track durability of product differentiation. How long until competition erodes advantage. | Fundamental Agent | Differentiation durability scorer | MEDIUM |
| **Antitrust / Competition Policy** | Antitrust risk module. Monitor enforcement globally. Antitrust action can break up companies or block mergers. | Fundamental Agent | Antitrust risk monitor (NLP on regulatory filings) | MEDIUM |
| **Natural Monopoly Regulation** | Regulated utility valuation. Model returns under different regulatory regimes. Changes in framework → structural shifts in profitability. | Fundamental Agent | Regulatory regime model (utility-specific) | LOW |
| **Privatization / Deregulation** | Privatization event tracking. IPOs of state companies, regulatory liberalization, market opening. | Fundamental Agent | Privatization event calendar | LOW |
| **Barriers to Entry** | Competitive moat assessment. Quantify barriers: capital intensity, patent strength, switching costs, network effects, regulatory licenses. | Fundamental Agent | Moat durability scorer (multi-factor) | HIGH |
| **Price Discrimination** | Revenue optimization signal. Companies with strong price discrimination earn higher margins. Airlines, hotels, tech platforms. | Fundamental Agent | Pricing power scorer | MEDIUM |
| **M&A** | M&A event-driven strategy. Deal spreads (merger arbitrage), sector consolidation, breakup value analysis. | Fundamental Agent | M&A target predictor (ML), deal completion probability | HIGH |
| **Innovation / R&D (Schumpeterian)** | Innovation alpha signal. Track R&D spending, patent filings, innovation output. Accelerating R&D productivity → outperformance. | Fundamental Agent | Innovation productivity tracker (patent NLP) | HIGH |
| **Market Concentration (SCP)** | Concentration-performance signal. Monitor HHI trends. Rising concentration → increasing market power (positive for incumbents) but also regulatory risk. | Fundamental Agent | HHI tracker, concentration trend analyzer | HIGH |

---

## 7. Concept Dependency Graph

```
YEAR 1 FOUNDATIONS
══════════════════

ECO 101 (Micro) ──────────┬──→ Order Book Model (S&D)
                           ├──→ Fair Value Engine (Equilibrium)
                           ├──→ Market Impact (Elasticity)
                           └──→ Game Theory ──→ ECO 201

ECO 102 (Macro) ──────────┬──→ Macro Factor Model (GDP)
                           ├──→ Inflation Monitor (CPI)
                           ├──→ Interest Rate Model
                           ├──→ FX Model ──→ ECO 305/313
                           └──→ Business Cycle ──→ ECO 205

ECO 103 (Math I) ─────────┬──→ Covariance Matrix Engine
                           ├──→ PCA / Factor Decomposition
                           ├──→ Portfolio Optimizer (Lagrange)
                           └──→ Constrained Optimization ──→ ECO 321

ECO 104 (Math II) ────────┬──→ ARIMA Models ──→ STA 244
                           ├──→ SDE / Black-Scholes
                           └──→ Dynamic Programming ──→ RL Agents

YEAR 2 CORE
═══════════

ECO 201 (Int Micro) ──────┬──→ Multi-Agent Coordinator
                           ├──→ Nash Equilibrium Engine
                           ├──→ Market Microstructure Classifier
                           └──→ Information Asymmetry Detector

ECO 205 (Int Macro) ──────┬──→ IS-LM Model
                           ├──→ AD-AS Regime Classifier
                           ├──→ Mundell-Fleming (FX Regime)
                           ├──→ Taylor Rule ──→ ECO 322
                           └──→ Business Cycle Positioning

ECO 209 (Money) ──────────┬──→ FX Market Engine (CORE)
                           ├──→ Central Bank Watcher
                           ├──→ Monetary Policy Transmission
                           ├──→ Banking Sector Health Monitor
                           └──→ Yield Curve Analyzer

YEAR 3 ADVANCED
═══════════════

ECO 305/313 (Intl) ───────┬──→ FX Model (PPP, UIP, Portfolio Balance)
                           ├──→ Trade Flow Engine (BOP, Capital Flows)
                           ├──→ Regime Classifier (Fixed/Float/Managed)
                           └──→ Currency Crisis Detector

ECO 321 (Adv Micro) ──────┬──→ General Equilibrium Pricer
                           ├──→ Pareto Efficient Frontier
                           ├──→ Information Asymmetry Trading
                           └──→ Market Failure Exploitation

ECO 322 (Adv Macro) ──────┬──→ DSGE Model (simplified)
                           ├──→ Stagflation Detector
                           ├──→ Policy Reaction Function
                           ├──→ Fiscal Multiplier Model
                           └──→ Long-Term Return Forecaster (Solow)

YEAR 4 SPECIALIZED
══════════════════

ECO 401 (Dev) ────────────┬──→ EM Sovereign Risk Module
                           ├──→ Development Stage Classifier
                           ├──→ Structural Transformation Tracker
                           └──→ Institutional Quality Score

ECO 414/424 (Econometrics)┬──→ Signal Validation Engine (CRITICAL)
                           ├──→ Factor Model Estimation (OLS, MLE)
                           ├──→ Cointegration Engine (Pairs Trading)
                           ├──→ Hypothesis Testing Framework
                           └──→ Anti-Data-Mining Framework

ECO 421 (Public Finance) ─┬──→ Fiscal Policy Module
                           ├──→ Sovereign Bond Pricing (DSA)
                           ├──→ Tax Policy Impact Model
                           └──→ Budget Event Trading

ECO 422 (Industry) ───────┬──→ Industry Analysis Module
                           ├──→ Market Power / Moat Scorer
                           ├──→ M&A Event Strategy
                           └──→ Innovation Alpha Signal
```

---

## 8. Alpha Stack Module Specifications

### 8.1 Module: Macro Signal Engine
**Inputs:** ECO 102, ECO 205, ECO 322, ECO 401, ECO 421

```python
class MacroSignalEngine:
    """
    Processes macroeconomic data into tradeable signals.
    Consumes concepts from ECO 102, 205, 322, 401, 421.
    """

    def __init__(self):
        self.inflation_monitor = InflationMonitor()        # ECO 102: CPI, PPI, Core
        self.rate_model = InterestRateModel()              # ECO 102, 209: Rate expectations
        self.cycle_detector = BusinessCycleDetector()      # ECO 205, 322: HMM regime
        self.taylor_rule = TaylorRuleCalculator()          # ECO 205, 322: Policy prediction
        self.fiscal_tracker = FiscalPolicyTracker()        # ECO 322, 421: Fiscal impact
        self.sovereign_risk = SovereignRiskScorer()        # ECO 401, 421: EM credit risk
        self.fx_model = MultiModelFXForecaster()           # ECO 305/313: FX signals

    def generate_macro_signal(self, symbol: str, context: dict) -> MacroSignal:
        # 1. Inflation signal (ECO 102)
        inflation = self.inflation_monitor.assess(
            cpi_surprise=context['cpi_surprise'],
            core_vs_headline=context['core_headline_div'],
            ppi_trend=context['ppi_trend']
        )

        # 2. Rate expectation (ECO 209, 322)
        rate_expectation = self.rate_model.predict(
            taylor_rule_rate=self.taylor_rule.calculate(
                inflation=inflation.current,
                output_gap=context['output_gap']
            ),
            actual_rate=context['current_rate'],
            fed_communication=context['fed_speak_sentiment']  # FinBERT output
        )

        # 3. Business cycle phase (ECO 205)
        cycle = self.cycle_detector.detect(
            pmi=context['pmi'],
            yield_curve=context['yield_curve_slope'],
            unemployment=context['unemployment_trend'],
            credit_growth=context['credit_growth']
        )

        # 4. Fiscal impulse (ECO 322, 421)
        fiscal = self.fiscal_tracker.assess(
            deficit_gdp=context['fiscal_deficit'],
            spending_composition=context['spending_breakdown'],
            monetary_accommodation=context['rate_stance']
        )

        # 5. Sovereign risk (ECO 401)
        sovereign = self.sovereign_risk.score(
            debt_gdp=context['debt_to_gdp'],
            institutional_quality=context['wgi_score'],
            capital_flight_indicators=context['capital_flow_data']
        )

        # 6. Aggregate macro signal
        return MacroSignal(
            direction=self._aggregate_direction(inflation, rate_expectation, cycle, fiscal),
            confidence=self._aggregate_confidence(all_signals),
            regime=cycle.regime,
            event_risk=inflation.event_risk,
            sovereign_premium=sovereign.risk_premium
        )
```

### 8.2 Module: Forex Market Engine
**Inputs:** ECO 209, ECO 305/313

```python
class ForexMarketEngine:
    """
    Core forex trading engine.
    Consumes concepts from ECO 209 (Money & Banking) and ECO 305/313 (International Economics).
    """

    def __init__(self):
        self.ppp_model = PPPFairValue()                    # ECO 305: Long-run anchor
        self.uip_model = UIPDeviationTracker()             # ECO 209, 305: Carry signals
        self.interest_rate_parity = CoveredIRP()           # ECO 209: Forward pricing
        self.regime_classifier = FXRegimeClassifier()      # ECO 305: Fixed/Float/Managed
        self.capital_flow_tracker = CapitalFlowModel()     # ECO 305: BOP analysis
        self.central_bank_watcher = CentralBankWatcher()   # ECO 209: Policy parsing
        self.banking_health = BankingSectorMonitor()       # ECO 209: Systemic risk

    def generate_fx_signal(self, pair: str) -> FXSignal:
        # 1. Fair value anchor (ECO 305: PPP)
        ppp_fair = self.ppp_model.estimate(pair)

        # 2. Carry signal (ECO 209: Interest Rate Parity)
        uip_deviation = self.uip_model.deviation(pair)

        # 3. Regime (ECO 305: Exchange Rate Regimes)
        regime = self.regime_classifier.classify(pair)

        # 4. Capital flows (ECO 305: BOP)
        flows = self.capital_flow_tracker.current(pair)

        # 5. Central bank stance (ECO 209: Monetary Policy)
        cb_stance = self.central_bank_watcher.assess(pair)

        # 6. Banking sector risk (ECO 209: Banking Crises)
        banking_risk = self.banking_health.score(pair)

        return FXSignal(
            pair=pair,
            ppp_deviation=ppp_fair.deviation_from_spot,
            carry_score=uip_deviation.score,
            regime=regime.type,
            flow_direction=flows.net_direction,
            cb_bias=cb_stance.hawkish_dovish,
            systemic_risk=banking_risk.score,
            composite_score=self._weighted_composite(all_signals)
        )
```

### 8.3 Module: Signal Validation Engine
**Inputs:** ECO 414/424

```python
class SignalValidationEngine:
    """
    Validates trading signals using econometric methods.
    Consumes ALL concepts from ECO 414/424 (Econometrics).
    """

    def __init__(self):
        self.ols_engine = OLSEstimator()                   # ECO 414: OLS, Gauss-Markov
        self.diagnostic_suite = DiagnosticTestSuite()      # ECO 414/424: All diagnostic tests
        self.hypothesis_tester = HypothesisTester()        # ECO 414/424: t-test, F-test, p-value
        self.time_series_validator = TimeSeriesValidator()  # ECO 424: Stationarity, cointegration
        self.multi_testing = MultipleTestingController()   # ECO 424: Bonferroni, FDR
        self.bootstrap_engine = BootstrapValidator()       # ECO 424: Bootstrap, permutation tests

    def validate_signal(self, signal: SignalCandidate, data: DataFrame) -> ValidationResult:
        # 1. Estimate factor model (ECO 414: OLS)
        model = self.ols_engine.estimate(
            y=data['returns'],
            X=data[signal.features],
            robust_errors=True  # Newey-West for time series
        )

        # 2. Run diagnostics (ECO 414/424: Full diagnostic suite)
        diagnostics = self.diagnostic_suite.run_all(
            model=model,
            tests=[
                'ramsey_reset',         # Functional form
                'breusch_pagan',        # Heteroscedasticity
                'durbin_watson',        # Autocorrelation
                'jarque_bera',          # Normality
                'vif',                  # Multicollinearity
                'chow',                 # Structural breaks
                'adf',                  # Stationarity
            ]
        )

        # 3. Hypothesis test (ECO 414: t-test, F-test)
        significance = self.hypothesis_tester.test(
            model=model,
            null_hypothesis="alpha = 0",
            alternative="alpha > 0",
            correction='bonferroni'  # Multiple testing correction
        )

        # 4. Time series validation (ECO 424: Cointegration, Granger)
        if signal.type == 'pairs':
            ts_valid = self.time_series_validator.test_cointegration(
                series1=data[signal.pair[0]],
                series2=data[signal.pair[1]],
                method='johansen'
            )
        else:
            ts_valid = self.time_series_validator.test_stationarity(
                series=data['returns'],
                method='adf'
            )

        # 5. Bootstrap validation (ECO 424: Bootstrap)
        bootstrap_ci = self.bootstrap_engine.confidence_interval(
            statistic='sharpe_ratio',
            data=data['returns'],
            n_bootstrap=10000,
            confidence=0.95
        )

        # 6. Anti-data-mining check (ECO 424: Deflated Sharpe)
        deflated_sharpe = self.multi_testing.deflated_sharpe_ratio(
            observed_sharpe=model.sharpe,
            n_trials=signal.n_hypotheses_tested,
            n_observations=len(data)
        )

        return ValidationResult(
            approved=(
                significance.p_value < 0.05
                and diagnostics.all_passed
                and ts_valid.is_valid
                and bootstrap_ci.lower > 0
                and deflated_sharpe > 0
            ),
            factor_model=model,
            diagnostics=diagnostics,
            significance=significance,
            bootstrap_ci=bootstrap_ci,
            deflated_sharpe=deflated_sharpe,
            rejection_reasons=self._compile_rejections(all_tests)
        )
```

---

## 9. Multi-Agent System Integration

### 9.1 Agent ↔ ECO Unit Binding Matrix

| Agent | ECO Units | Responsibilities |
|-------|-----------|-----------------|
| **Orchestrator** | ECO 201 | Multi-agent coordination, Nash equilibrium detection, strategy allocation |
| **Fundamental Agent** | ECO 102, 205, 209, 305/313, 322, 401, 421, 422 | Macro analysis, central bank watching, fiscal policy, EM risk, industry analysis |
| **Structure Agent** | ECO 102, 205, 209, 305/313, 322 | Regime detection, IS-LM, AD-AS, business cycle, FX regime, cointegration |
| **Liquidity Agent** | ECO 101 | Order book dynamics, supply/demand, elasticity, informed trading detection |
| **SMC Agent** | ECO 101 | Smart money concepts (extends microstructure) |
| **Signal Aggregator** | ECO 321 | General equilibrium pricing, confluence scoring, Pareto efficiency |
| **Entry Agent** | ECO 103, 104, 201 | Portfolio optimization (Lagrange), position sizing (RL), budget constraints |
| **Risk Gate Agent** | ECO 103, 201 | Constraint enforcement (KKT), position limits, game-theoretic robustness |
| **TP Agent** | ECO 104 | Dynamic programming (Bellman), optimal stopping, partial close optimization |
| **Execution Agent** | ECO 101, 104, 201 | Market impact (elasticity), execution algorithms, spread optimization |
| **Reflection Agent** | ECO 414/424 | **ALL ECONOMETRICS.** Signal validation, hypothesis testing, diagnostics, bootstrap |
| **Journal Agent** | ECO 414/424 | Performance attribution, factor model documentation, research reports |
| **Monitor Agent** | ECO 209, 305/313 | Banking crisis detection, currency crisis early warning, systemic risk |
| **Portfolio Allocator** | ECO 103, 321 | Matrix algebra, eigenvalues, constrained optimization, efficient frontier |

### 9.2 Concept → Agent Communication Flow

```
ECO 209 (Money & Banking):
  Fundamental Agent ──[macro signal]──→ Signal Aggregator
  Structure Agent ──[regime signal]──→ Orchestrator
  Monitor Agent ──[crisis alert]──→ Risk Gate Agent (P0 CRITICAL)

ECO 305/313 (International Economics):
  Fundamental Agent ──[FX signal]──→ Signal Aggregator
  Structure Agent ──[regime/classification]──→ Orchestrator
  Capital Flow Data ──[flow direction]──→ Entry Agent (position sizing)

ECO 414/424 (Econometrics):
  Reflection Agent ──[validation result]──→ Orchestrator (approve/reject signal)
  Reflection Agent ──[diagnostic alert]──→ Journal Agent (log issue)
  Bootstrap CI ──[confidence interval]──→ Risk Gate Agent (adjust limits)
```

---

## 10. AI/ML Model Bindings

### 10.1 Model ↔ ECO Concept Mapping

| Model | ECO Concepts | Application | Latency Tier |
|-------|-------------|-------------|-------------|
| **FinBERT** | ECO 102 (inflation), ECO 209 (Fed speak), ECO 322 (policy) | Sentiment analysis of central bank communications, economic commentary | Tier 3 (<500ms) |
| **XGBoost** | ECO 101 (sweep classifier), ECO 201 (strategy), ECO 401 (country score) | Signal classification, confluence scoring, regime detection | Tier 2 (<50ms) |
| **HMM** | ECO 102 (regime), ECO 205 (cycle), ECO 305 (FX regime) | Market regime detection, business cycle classification, FX regime detection | Tier 1 (<5ms) |
| **LSTM** | ECO 102 (rates), ECO 209 (FX), ECO 305/313 (FX forecast) | Price/rate forecasting, sequential pattern recognition | Tier 2 (<50ms) |
| **Transformer** | ECO 305/313 (multi-asset), ECO 322 (policy analysis) | Multi-timeframe, cross-asset analysis, policy document understanding | Tier 3 (<500ms) |
| **PPO (RL)** | ECO 104 (Bellman), ECO 201 (game theory) | Position sizing optimization, multi-agent strategy optimization | Tier 2 (<50ms) |
| **DQN (RL)** | ECO 104 (optimal stopping) | Take-profit optimization, partial close decisions | Tier 2 (<50ms) |
| **LLM (DeepSeek/Qwen)** | ECO 209 (central bank), ECO 322 (policy), ECO 421 (budget), ECO 422 (earnings) | Fundamental analysis, policy interpretation, budget parsing, earnings analysis | Tier 4 (1-10s) |
| **OLS/MLE** | ECO 414/424 (ALL econometrics) | Factor model estimation, signal validation, hypothesis testing | Tier 1 (<5ms) |
| **Bootstrap** | ECO 424 (robust inference) | Confidence intervals, Sharpe ratio validation, model comparison | Tier 3 (<500ms) |

---

## 11. Implementation Roadmap

### Phase 1: Foundation (Weeks 1–4)

```
□ Implement Macro Signal Engine (ECO 102 concepts)
  ├── Inflation monitor (CPI/PPI surprise scoring)
  ├── Interest rate model (Taylor Rule calculator)
  └── Business cycle detector (HMM 3-state)

□ Implement Forex Market Engine (ECO 209 concepts)
  ├── PPP fair value model
  ├── UIP deviation tracker
  ├── Central bank communication parser (FinBERT)
  └── Banking sector health monitor

□ Implement Signal Validation Engine (ECO 414 concepts)
  ├── OLS factor model estimator
  ├── Diagnostic test suite (heteroscedasticity, autocorrelation, normality)
  ├── Hypothesis testing framework (t-test, F-test, p-value)
  └── Multiple testing controller (Bonferroni, FDR)
```

### Phase 2: Core Trading (Weeks 5–8)

```
□ Implement Market Microstructure Engine (ECO 101 concepts)
  ├── Order book supply/demand model
  ├── Market impact estimator (elasticity)
  ├── Informed trading detector (PIN model)
  └── Fair value equilibrium calculator

□ Implement Regime Detection Engine (ECO 205 concepts)
  ├── IS-LM model (interest rate-output dynamics)
  ├── AD-AS regime classifier (Goldilocks, reflation, stagflation, deflation)
  ├── Mundell-Fleming FX regime classifier
  └── Leading indicator composite

□ Implement Portfolio Optimization Engine (ECO 103 concepts)
  ├── Covariance matrix engine (PCA, eigenvalue decomposition)
  ├── Mean-variance optimizer (Lagrangian, KKT)
  └── Efficient frontier computer
```

### Phase 3: Advanced Analytics (Weeks 9–12)

```
□ Implement FX Model (ECO 305/313 concepts)
  ├── Multi-model FX forecaster (PPP + UIP + monetary model + portfolio balance)
  ├── Capital flow tracker (BOP, FDI, FPI)
  ├── Currency crisis early warning system
  └── Exchange rate regime classifier (de facto)

□ Implement Policy Reaction Function (ECO 322 concepts)
  ├── Taylor Rule with time-varying parameters
  ├── Fiscal multiplier estimator (country-specific)
  ├── Stagflation detector (supply shock features)
  └── DSGE-lite model (simplified, real-time)

□ Implement Time Series Validation (ECO 424 concepts)
  ├── Cointegration test suite (Engle-Granger, Johansen)
  ├── Granger causality engine
  ├── ARIMA baseline forecaster
  └── Bootstrap validation engine
```

### Phase 4: Specialized Modules (Weeks 13–16)

```
□ Implement EM Sovereign Risk Module (ECO 401 concepts)
  ├── Development stage classifier
  ├── Institutional quality scorer (WGI, EoDB)
  ├── Debt sustainability analyzer (Monte Carlo DSA)
  └── Financial inclusion tracker

□ Implement Fiscal Policy Module (ECO 421 concepts)
  ├── Budget event calendar and parser (NLP)
  ├── Sovereign bond pricing model
  ├── Fiscal rule compliance monitor
  └── Crisis fiscal response tracker

□ Implement Industry Analysis Module (ECO 422 concepts)
  ├── Market power / competitive moat scorer
  ├── M&A target predictor and deal completion model
  ├── Innovation productivity tracker (patent NLP)
  └── Industry concentration (HHI) tracker

□ Implement Dynamic Programming Engine (ECO 104 concepts)
  ├── PPO position sizing agent (offline training)
  ├── DQN take-profit agent (offline training)
  ├── Q-learning execution agent
  └── RL safety constraints (hard limits)
```

### Phase 5: Integration & Hardening (Weeks 17+)

```
□ Full pipeline integration test (all 14 ECO units → 8 modules → 16 agents)
□ Cross-module signal flow validation
□ Performance attribution by ECO concept source
□ Quantum computing preparation (QAOA for portfolio, quantum Monte Carlo for risk)
□ Continuous learning loop (Reflection Agent updates from trade outcomes)
□ Model versioning and A/B testing framework
□ Load testing and failure injection
```

---

## Appendix A: Grade Gap Analysis

| ECO Unit | Grade | Alpha Stack Priority | Gap Severity | Remediation |
|----------|-------|---------------------|--------------|-------------|
| ECO 101 | 66% | HIGH | Low | Solid foundation. Deepen game theory (MARL). |
| ECO 102 | 61% | HIGH | Medium | Strengthen monetary policy transmission, exchange rate models. |
| ECO 103 | 70% | MEDIUM | Low | Strong. Apply to portfolio optimization implementation. |
| ECO 104 | 65% | MEDIUM | Low | Solid. Focus on Bellman equation → RL implementation. |
| ECO 201 | 53% | HIGH | **High** | Weak on game theory. Critical for multi-agent architecture. Self-study: Fudenberg & Tirole. |
| ECO 205 | 67% | HIGH | Low | Good macro framework. Deepen IS-LM → real-time estimation. |
| ECO 209 | 65% | **CRITICAL** | **High** | Core forex knowledge. Must strengthen monetary transmission, banking crises. |
| ECO 305 | 44% | **CRITICAL** | **Severe** | Weakest unit. Must self-study: trade theory, FX regimes, BOP analysis. |
| ECO 313 | 47% | **CRITICAL** | **Severe** | Advanced international econ. Gap in Heckscher-Ohlin, optimal currency areas. |
| ECO 321 | 51% | HIGH | **High** | Advanced micro. Gap in general equilibrium, welfare theorems. |
| ECO 322 | 62% | HIGH | Medium | Solid macro. Deepen DSGE, fiscal multiplier estimation. |
| ECO 401 | N/A | MEDIUM | — | New course. Apply development economics to EM sovereign risk. |
| ECO 414 | N/A | **CRITICAL** | — | New course. Core econometrics for signal validation. Master immediately. |
| ECO 424 | N/A | **CRITICAL** | — | New course. Advanced econometrics. Critical for anti-data-mining framework. |
| ECO 421 | N/A | MEDIUM | — | New course. Apply to fiscal policy module. |
| ECO 422 | N/A | MEDIUM | — | New course. Apply to industry analysis module. |

### Priority Self-Study Plan

1. **ECO 414/424 (Econometrics)** — IMMEDIATE. This is the validation backbone. Master OLS, diagnostics, hypothesis testing, cointegration.
2. **ECO 305/313 (International Economics)** — URGENT. Weakest grades on highest-impact modules. Self-study: Krugman & Obstfeld "International Economics."
3. **ECO 209 (Money & Banking)** — HIGH. Core forex knowledge. Self-study: Mishkin "Economics of Money, Banking, and Financial Markets."
4. **ECO 201 (Intermediate Micro)** — HIGH. Game theory gap. Self-study: Fudenberg & Tirole "Game Theory" (Chapters 1-6).
5. **ECO 321 (Advanced Micro)** — MEDIUM. General equilibrium. Self-study: Mas-Colell "Microeconomic Theory" (Chapters 10, 15, 22).

---

## Appendix B: Technology Stack for Economics Modules

| Component | Technology | ECO Units Served |
|-----------|-----------|-----------------|
| **OLS/MLE Estimation** | statsmodels, scipy.optimize | ECO 414, 424 |
| **Time Series (ARIMA, GARCH)** | statsmodels, arch | ECO 104, 424 |
| **HMM Regime Detection** | hmmlearn | ECO 102, 205, 305 |
| **FinBERT Sentiment** | HuggingFace Transformers, ONNX | ECO 102, 209, 322 |
| **Portfolio Optimization** | cvxpy, scipy.optimize | ECO 103, 321 |
| **RL Agents** | Stable-Baselines3 (PPO, DQN) | ECO 104, 201 |
| **LLM Policy Analysis** | DeepSeek/Qwen API, Ollama | ECO 209, 322, 421, 422 |
| **Bootstrap Engine** | Custom (numpy resampling) | ECO 424 |
| **Cointegration Tests** | statsmodels (Johansen, Engle-Granger) | ECO 424 |
| **Factor Model Database** | PostgreSQL (factor_exposures table) | ECO 414, 424 |
| **Macro Data Pipeline** | Redis (hot), TimescaleDB (cold) | ECO 102, 205, 209, 322 |
| **NLP Budget/Earnings Parser** | LLM + structured extraction | ECO 421, 422 |

---

*This architecture document is the blueprint for wiring Valentine's economics coursework into Alpha Stack. Every concept from 14 ECO units maps to a specific module, agent, data pipeline, and AI/ML model. The highest-priority gaps (ECO 305/313 at 44%/47%, ECO 414/424 as new courses) require immediate attention. The system is designed to be built incrementally — Phase 1 delivers the macro and validation engines that underpin all trading decisions.*

*Next: Cross-reference with `architecture_multi_agent.md` for agent communication protocol details.*
