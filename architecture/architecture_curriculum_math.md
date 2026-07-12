# Architecture: Valentine's Mathematics Curriculum → Alpha Stack Module Wiring

> **Version:** 1.0 · **Date:** 2026-07-11 · **Author:** Architecture Team
> **Source Research:** [`research/curriculum/research_curriculum_ml_ai.md`](../research/curriculum/research_curriculum_ml_ai.md) — ML/AI curriculum — mathematics module wiring
> **Status:** Architecture Complete

---

> **System:** Alpha Stack — Institutional-Grade AI Forex/Crypto Trading System  
> **Role:** Mathematics Curriculum Architect  
> **Date:** 2026-07-11  
> **Purpose:** Define how every mathematical concept from Valentine's coursework maps to specific Alpha Stack modules, data flows, and agent responsibilities.

---

## Table of Contents

1. [Curriculum Overview & Grade Analysis](#1-curriculum-overview--grade-analysis)
2. [MAT 101: Foundation Mathematics → Core Primitives](#2-mat-101-foundation-mathematics--core-primitives)
3. [MAT 121: Differential Calculus → Rate & Sensitivity Layer](#3-mat-121-differential-calculus--rate--sensitivity-layer)
4. [MAT 124: Integral Calculus → Accumulation & Probability Layer](#4-mat-124-integral-calculus--accumulation--probability-layer)
5. [ECO 103: Mathematics for Economists → Portfolio Algebra Layer](#5-eco-103-mathematics-for-economists--portfolio-algebra-layer)
6. [ECO 104: Mathematics for Economists → Dynamic Optimization Layer](#6-eco-104-mathematics-for-economists--dynamic-optimization-layer)
7. [STA 443: Measure and Probability Theory → Risk Measure Layer](#7-sta-443-measure-and-probability-theory--risk-measure-layer)
8. [Financial Mathematics → Derivatives & Pricing Engine](#8-financial-mathematics--derivatives--pricing-engine)
9. [Stochastic Processes → Price Dynamics Engine](#9-stochastic-processes--price-dynamics-engine)
10. [Optimization Theory → Decision Engine](#10-optimization-theory--decision-engine)
11. [Integration Wiring: How Everything Connects](#11-integration-wiring-how-everything-connects)
12. [Gap Analysis & Remediation Plan](#12-gap-analysis--remediation-plan)
13. [Agent Assignment Matrix](#13-agent-assignment-matrix)

---

## 1. Curriculum Overview & Grade Analysis

### Valentine's Mathematics Units

| Unit | Title | Grade | Priority | Key Alpha Stack Role |
|------|-------|-------|----------|---------------------|
| **MAT 101** | Foundation Mathematics | 50% (D) | 🟡 Remediation needed | Set theory, logic, functions — system primitives |
| **MAT 121** | Differential Calculus | 66% (B) | 🔴 Critical | Momentum, Greeks, optimization, backpropagation |
| **MAT 124** | Integral Calculus | 56% (C) | 🔴 Critical | Cumulative volume, probability, option pricing |
| **ECO 103** | Mathematics for Economists | 70% (A) | 🔴 Critical | Matrix algebra, eigenvalues, portfolio construction |
| **ECO 104** | Mathematics for Economists | 65% (B) | 🔴 Critical | Dynamic programming, SDEs, differential equations |
| **STA 443** | Measure and Probability Theory | N/A | 🔴 Critical | Measure-theoretic foundations for risk and pricing |

### Grade-to-Wiring Gap Map

```
Grade:  D(50%)    B(66%)    C(56%)    A(70%)    B(65%)    N/A
        MAT101    MAT121    MAT124    ECO103    ECO104    STA443
        ──────    ──────    ──────    ──────    ──────    ──────
Risk:   HIGH      MEDIUM    HIGH      LOW       MEDIUM    UNKNOWN

→ MAT 101 foundations need strengthening before advanced wiring
→ MAT 124 integration skills need reinforcement for option pricing
→ STA 443 is the wild card — measure theory underpins everything
```

---

## 2. MAT 101: Foundation Mathematics → Core Primitives

**Grade: D (50%) | Priority: 🟡 Remediation Required**

MAT 101 provides the primitive data types and logical structures upon which all other mathematics is built. A D grade indicates gaps that will propagate errors upward.

### 2.1 Set Theory → Asset Universe Management

**Concept:** Sets, unions, intersections, complements, subsets  
**Alpha Stack Module:** `Universe Manager`

```
┌─────────────────────────────────────────────────────┐
│                  UNIVERSE MANAGER                     │
│                                                       │
│  All Assets (Ω) = {EUR/USD, GBP/USD, BTC, ETH, ...}  │
│                                                       │
│  Liquid = {pairs with avg daily vol > $1M}            │
│  Trending = {pairs with |Hurst| > 0.6}               │
│  Tradeable = Liquid ∩ ¬Blacklisted                    │
│  Signal Universe = Tradeable ∩ Trending               │
│                                                       │
│  Sector Partitions:                                   │
│    Majors = {EUR/USD, GBP/USD, USD/JPY, ...}         │
│    Crypto_L1 = {BTC, ETH, SOL, AVAX, ...}            │
│    Crypto_DeFi = {UNI, AAVE, MKR, ...}               │
└─────────────────────────────────────────────────────┘
```

**Wiring:**
- `∩` (intersection): Filter signals to only tradeable assets
- `∪` (union): Combine signal universes from multiple strategies
- `\` (set difference): Remove blacklisted or restricted assets
- Partitions: Define asset classes for portfolio diversification constraints

**Remediation needed:** Valentine's D in MAT 101 suggests potential weakness in formal set reasoning. This must be shored up because set operations are the foundation of every query, filter, and constraint in the system.

### 2.2 Propositional Logic → Trading Rule Engine

**Concept:** AND (∧), OR (∨), NOT (¬), implication (→), biconditional (↔)  
**Alpha Stack Module:** `Signal Rule Engine`

```
Signal Rules (Compound Propositions):

BUY  := (RSI < 30) ∧ (Volume > 2×Avg) ∧ (Trend = UP)
SELL := (RSI > 70) ∨ (StopLossHit) ∨ (Regime = CRISIS)
HOLD := ¬BUY ∧ ¬SELL

Strategy Activation:
  IF (Regime = Trending) → Deploy(MomentumAgent)
  IF (Regime = MeanReverting) → Deploy(PairsAgent)
  IF (Regime = HighVol) → Deploy(VolatilityAgent)
```

**Wiring:**
- Every signal is a compound logical proposition evaluated against market data
- Strategy routing uses implication (→) to map regimes to agents
- Negation (¬) defines exit conditions and contrarian signals
- Truth tables validate signal logic before deployment

### 2.3 Functions & Composition → Module Architecture

**Concept:** f(x), domain, range, composition f∘g  
**Alpha Stack Module:** `Pipeline Architecture`

```
Alpha Stack IS function composition:

MarketData ──→ FeatureEngine ──→ SignalGenerator ──→ RiskFilter ──→ Executor
   f(x)          g(f(x))          h(g(f(x)))        r(h(g(f(x))))  e(r(...))

Each module is a function:
  FeatureEngine: Data → Features
  SignalGenerator: Features → {BUY, SELL, HOLD}
  RiskFilter: Signal → ApprovedSignal
  Executor: ApprovedSignal → Order
```

**Wiring:**
- The entire Alpha Stack pipeline is a composition of functions
- Each module has a defined domain (inputs) and range (outputs)
- Type checking (set membership) prevents invalid data propagation
- Function composition order determines the data flow architecture

### 2.4 Sequences & Series → Moving Averages and Fibonacci

**Concept:** Arithmetic/geometric sequences, convergence, series sums  
**Alpha Stack Module:** `Indicator Library`

- **EMA** (Exponential Moving Average): Geometric series with ratio α → convergence guarantees stable smoothing
- **Fibonacci retracements**: Fibonacci sequence → 23.6%, 38.2%, 50%, 61.8%, 78.6% levels
- **Geometric series** for discount factors: Σ(1/(1+r)^t) = 1/r for perpetual instruments

---

## 3. MAT 121: Differential Calculus → Rate & Sensitivity Layer

**Grade: B (66%) | Priority: 🔴 Critical — Every derivative maps to a trading concept**

MAT 121 is the mathematical backbone of Alpha Stack. The derivative IS the rate of change, and rate of change IS momentum, sensitivity, and optimization.

### 3.1 First Derivative → Momentum Engine

**Concept:** f'(x) = lim[h→0] (f(x+h) - f(x))/h  
**Alpha Stack Module:** `Momentum Engine`

```
Price Derivative = Momentum:

  dP/dt ≈ (P_t - P_{t-1}) / Δt

  For EUR/USD on 15-min candles:
    Momentum_15m = (Close[now] - Close[15min ago]) / 15min

  Signal Logic:
    IF dP/dt > 0 AND d²P/dt² > 0  → Strong uptrend (BUY)
    IF dP/dt > 0 AND d²P/dt² < 0  → Weakening trend (TIGHTEN STOP)
    IF dP/dt < 0 AND d²P/dt² < 0  → Strong downtrend (SELL)
    IF dP/dt < 0 AND d²P/dt² > 0  → Reversing (WATCH)
```

**Module Dependencies:**
- Input: Price time series from `MarketDataStore`
- Output: Momentum signals to `SignalAggregator`
- Related: RSI, ROC, MACD are all derivative-based indicators

### 3.2 Higher-Order Derivatives → Gamma & Convexity

**Concept:** f''(x), f'''(x) — acceleration, jerk  
**Alpha Stack Module:** `Convexity Analyzer`

| Derivative | Financial Name | Alpha Stack Function |
|-----------|---------------|---------------------|
| f'(x) = dP/dt | Velocity (momentum) | Trend detection |
| f''(x) = d²P/dt² | Acceleration | Trend strength/weakness |
| ∂V/∂S | Delta | Option price sensitivity to underlying |
| ∂²V/∂S² | Gamma | Rate of change of delta — convexity |
| ∂V/∂σ | Vega | Sensitivity to volatility |
| ∂V/∂t | Theta | Time decay |
| ∂V/∂r | Rho | Sensitivity to interest rate |

**Wiring to Options:**
```
Greeks Calculator Module:
  Delta = ∂V/∂S  → Hedge ratio computation
  Gamma = ∂²V/∂S² → Convexity risk monitoring
  Theta = ∂V/∂t  → Time decay tracking
  Vega  = ∂V/∂σ  → Volatility exposure
  
Portfolio Greeks:
  Δ_portfolio = Σᵢ nᵢ · Δᵢ  (sum of position-weighted deltas)
  Γ_portfolio = Σᵢ nᵢ · Γᵢ
```

### 3.3 Chain Rule → Backpropagation & Cascade Analysis

**Concept:** d/dx f(g(x)) = f'(g(x)) · g'(x)  
**Alpha Stack Module:** `Neural Network Training Pipeline` + `Sensitivity Cascade Analyzer`

**Dual Application:**

1. **AI Training:** The chain rule IS backpropagation. Every gradient update in Alpha Stack's LSTM/Transformer models propagates through layers via the chain rule.

2. **Cascade Analysis:** How does a change in interest rates propagate through the system?
   ```
   Rate Change → Bond Price Change → Carry Trade P&L → Portfolio Value Change
   
   d(Portfolio)/d(Rate) = d(Portfolio)/d(Carry) × d(Carry)/d(Spread) × d(Spread)/d(Rate)
   ```

### 3.4 Optimization (f'(x) = 0) → Parameter Tuning

**Concept:** Critical points, first/second derivative tests  
**Alpha Stack Module:** `Parameter Optimizer`

- Finding optimal lookback periods: maximize Sharpe_ratio(period) → solve d/d(period) = 0
- Optimal stop-loss distance: minimize expected_loss(stop_distance) → derivative = 0
- Optimal position sizing: maximize Kelly_fraction → derivative = 0

### 3.5 Partial Derivatives → Multi-Factor Sensitivity

**Concept:** ∂f/∂x, ∂f/∂y — derivative with respect to one variable, others held constant  
**Alpha Stack Module:** `Sensitivity Matrix Engine`

```
Sensitivity Matrix (∂Portfolio/∂Factor):

              EUR/USD  GBP/USD  BTC    ETH    Rates   Vol
Portfolio Δ   0.85     0.72     1.2    0.95   -0.45   -0.32

→ Each entry is a partial derivative
→ The Jacobian matrix of portfolio sensitivities
→ Used for hedging: offset Delta with opposing positions
```

### 3.6 Gradient & Directional Derivative → Gradient Descent

**Concept:** ∇f = (∂f/∂x₁, ..., ∂f/∂xₙ), direction of steepest ascent  
**Alpha Stack Module:** `Optimization Engine`

- **Portfolio optimization:** Gradient of Sharpe ratio with respect to weights → move toward optimal allocation
- **Neural network training:** ∇Loss points toward steepest descent → parameter update direction
- **Adam optimizer:** Adaptive gradient descent using first and second moments

---

## 4. MAT 124: Integral Calculus → Accumulation & Probability Layer

**Grade: C (56%) | Priority: 🔴 Critical — Integration underpins volume, probability, and pricing**

MAT 124 provides the accumulation operator. If differentiation gives rates, integration gives totals. This maps to cumulative volume, probability calculations, and option pricing.

### 4.1 Definite Integral → Cumulative Volume & VWAP

**Concept:** ∫ₐᵇ f(x)dx = area under curve  
**Alpha Stack Module:** `Volume Profile Engine`

```
Cumulative Volume:
  V_total = ∫₀ᵀ v(t) dt  (integral of volume rate)

VWAP (Volume-Weighted Average Price):
  VWAP = ∫₀ᵀ P(t)·v(t)dt / ∫₀ᵀ v(t)dt

  Discrete approximation:
  VWAP = Σ(Pᵢ × Vᵢ) / Σ(Vᵢ)

Alpha Stack uses VWAP as:
  - Execution benchmark (are we buying above/below VWAP?)
  - Support/resistance level
  - Fair value estimate intraday
```

**Wiring:**
- Input: Tick-level price and volume data
- Computation: Running integral (summation) in the `Volume Accumulator`
- Output: VWAP line, volume profile, cumulative delta

### 4.2 Fundamental Theorem of Calculus → Return Aggregation

**Concept:** ∫ₐᵇ f(x)dx = F(b) - F(a), where F' = f  
**Alpha Stack Module:** `Return Calculator`

```
THE MOST IMPORTANT THEOREM IN TRADING MATH:

  Price Change (derivative) ←──FTC──→ Total Movement (integral)
  
  Return Rate: r_t = dP/P  (derivative)
  Cumulative Return: R = ∫₀ᵀ r_t dt = ln(P_T/P_0)  (integral)
  
  Log returns are additive:
    R_1week = r_Mon + r_Tue + r_Wed + r_Thu + r_Fri
    (This IS the FTC: sum of rates = total change)
```

### 4.3 Integration by Parts → Exotic Payoff Decomposition

**Concept:** ∫u dv = uv - ∫v du  
**Alpha Stack Module:** `Payoff Decomposer`

- Decompose complex DeFi payoffs into standard components (bond + option)
- Integration by parts in stochastic calculus (Itô integration by parts) underlies option pricing derivations

### 4.4 Probability Integrals → Signal Confidence

**Concept:** ∫f(x)dx where f is a PDF → probability  
**Alpha Stack Module:** `Bayesian Signal Updater`

```
Probability calculations (area under PDF):

  P(profit > 2%) = ∫₂^∞ f(r) dr   where f(r) is return PDF

  For normal returns: P = 1 - Φ((2% - μ) / σ)
  
  For fat-tailed: use Student-t or empirical distribution

  This feeds into:
    → Position sizing (higher probability → larger size)
    → Signal confidence scoring
    → Expected value calculation: EV = ∫ r·f(r)dr
```

### 4.5 Improper Integrals → Long-Horizon Risk

**Concept:** ∫₀^∞ f(x)dx  
**Alpha Stack Module:** `Perpetual Risk Model`

- Expected loss over infinite horizon for perpetual strategies
- Discounted value of perpetual cash flows: ∫₀^∞ e^(-rt) · CF dt = CF/r
- Used for long-term portfolio risk assessment and crypto staking valuation

---

## 5. ECO 103: Mathematics for Economists → Portfolio Algebra Layer

**Grade: A (70%) | Priority: 🔴 Critical — Valentine's strongest math unit**

ECO 103 provides the linear algebra that IS portfolio mathematics. This is Valentine's greatest strength and should be leveraged maximally.

### 5.1 Matrices → Covariance Matrix Engine

**Concept:** Matrix operations, multiplication, transpose  
**Alpha Stack Module:** `Covariance Matrix Engine`

```
The Covariance Matrix Σ IS the heart of portfolio math:

         EUR/USD  GBP/USD  USD/JPY  BTC    ETH
EUR/USD  [1.00    0.85    -0.45    0.32   0.28]
GBP/USD  [0.85    1.00    -0.40    0.30   0.25]
USD/JPY  [-0.45  -0.40     1.00   -0.15  -0.12]
BTC      [0.32    0.30    -0.15    1.00   0.88]
ETH      [0.28    0.25    -0.12    0.88   1.00]

Portfolio Variance: σ²_p = wᵀΣw  (matrix multiplication!)

  w = [0.2, 0.15, 0.1, 0.3, 0.25]  (portfolio weights)
  σ²_p = wᵀ × Σ × w = 0.00034      (daily variance)
```

**Wiring:**
- Input: Historical returns from all assets
- Update: Exponentially weighted moving average (EWMA) for regime-conditional correlations
- Output: Portfolio variance, risk decomposition, diversification ratio
- Consumers: `Portfolio Optimizer`, `Risk Engine`, `Position Sizer`

### 5.2 Determinants → Redundancy Detection

**Concept:** det(A) = 0 means singular  
**Alpha Stack Module:** `Redundancy Detector`

```
If det(Σ) ≈ 0:
  → Assets are nearly perfectly correlated
  → Covariance matrix is ill-conditioned
  → Portfolio optimization becomes unstable
  
Action: Remove redundant assets or apply shrinkage

Shrinkage Estimator:
  Σ_shrunk = α·Σ_sample + (1-α)·Σ_target
  where Σ_target = diagonal matrix of average variances
```

### 5.3 Matrix Inversion → Optimal Weight Solver

**Concept:** A⁻¹ such that AA⁻¹ = I  
**Alpha Stack Module:** `Markowitz Solver`

```
Minimum Variance Portfolio:
  w* = Σ⁻¹ · 1 / (1ᵀ · Σ⁻¹ · 1)

Maximum Sharpe Portfolio:
  w* = Σ⁻¹ · μ / (1ᵀ · Σ⁻¹ · μ)

Where:
  Σ⁻¹ = inverse of covariance matrix
  μ = expected return vector
  1 = vector of ones

Numerical stability:
  → Use Cholesky decomposition: Σ = LLᵀ, then Σ⁻¹ = (Lᵀ)⁻¹L⁻¹
  → Apply regularization if condition number is high
```

### 5.4 Eigenvalues & Eigenvectors → PCA Factor Engine

**Concept:** Av = λv  
**Alpha Stack Module:** `PCA Factor Decomposition Engine`

```
Eigendecomposition of covariance matrix:

  Σ = VΛVᵀ

  where:
    V = matrix of eigenvectors (principal components)
    Λ = diagonal matrix of eigenvalues (variance explained)

  PC1 (largest eigenvalue) → "Market Factor" (~60% of variance)
  PC2 → "Carry Factor" (~15%)
  PC3 → "Volatility Factor" (~10%)
  ...remaining PCs → noise

Alpha Stack uses PCA for:
  1. Dimensionality reduction: 50 assets → 5 factors
  2. Risk decomposition: which factors drive P&L?
  3. Signal orthogonalization: remove correlated signals
  4. Regime detection: eigenvalue ratios shift in crises
```

### 5.5 Linear Systems → Factor Model Calibration

**Concept:** Solve Ax = b  
**Alpha Stack Module:** `Factor Model Calibrator`

```
Multi-factor model:
  R_i = α + β₁·F₁ + β₂·F₂ + ... + βₖ·Fₖ + ε

In matrix form: R = Fβ + ε
Solve: β = (FᵀF)⁻¹FᵀR  (OLS solution — requires matrix inversion)

For each asset, we solve for factor exposures (betas):
  EUR/USD: β_carry = 0.4, β_momentum = 0.6, β_vol = -0.2
  BTC: β_carry = 0.1, β_momentum = 0.8, β_vol = 0.5
```

### 5.6 Linear Independence → Signal Orthogonality

**Concept:** Vectors are linearly independent if none is a linear combination of others  
**Alpha Stack Module:** `Signal Orthogonality Checker`

```
Trading signals must be independent for true diversification:

  Signal_1 = RSI-based
  Signal_2 = MACD-based  (potentially correlated with Signal_1!)
  Signal_3 = Sentiment-based  (likely independent)

Test: Check rank of signal correlation matrix
  If rank < number of signals → redundant signals exist
  Action: Remove or combine redundant signals

Gram-Schmidt orthogonalization:
  Transform correlated signals into orthogonal components
  → Each component captures unique information
  → Portfolio of orthogonal signals has maximum diversification
```

---

## 6. ECO 104: Mathematics for Economists → Dynamic Optimization Layer

**Grade: B (65%) | Priority: 🔴 Critical — Dynamic systems and optimization**

ECO 104 extends static optimization to dynamic settings — how systems evolve over time and how to optimize sequential decisions.

### 6.1 Difference Equations → AR Model Engine

**Concept:** yₜ = ayₜ₋₁ + b, characteristic equations  
**Alpha Stack Module:** `AR Model Engine`

```
First-order difference equation:
  Pₜ = α + β·Pₜ₋₁ + εₜ

  If |β| < 1 → stationary (mean-reverting)
  If β = 1 → random walk (unit root)
  If |β| > 1 → explosive (trending)

Alpha Stack classifies:
  |β| < 0.95 → Mean-reversion agent activates
  0.95 ≤ |β| ≤ 1.05 → Random walk (no trade)
  |β| > 1.05 → Momentum agent activates

Second-order (AR(2)):
  Pₜ = α + β₁Pₜ₋₁ + β₂Pₜ₋₂ + εₜ
  → Captures oscillatory dynamics
  → Characteristic equation: λ² - β₁λ - β₂ = 0
  → Complex roots → cyclical behavior
```

### 6.2 Differential Equations → Continuous-Time Models

**Concept:** dy/dt = f(y,t)  
**Alpha Stack Module:** `SDE Engine`

```
Ordinary Differential Equations in Finance:

  GBM: dS = μSdt + σSdW  (Geometric Brownian Motion)
  OU:  dX = θ(μ-X)dt + σdW  (Ornstein-Uhlenbeck for mean reversion)
  CIR: dr = θ(μ-r)dt + σ√r dW  (Cox-Ingersoll-Ross for rates)

Alpha Stack solves these:
  → Analytically when possible (GBM has closed-form solution)
  → Numerically (Euler-Maruyama discretization) for complex SDEs
  → Monte Carlo simulation for path-dependent quantities
```

### 6.3 Dynamic Programming (Bellman Equation) → RL Agent Core

**Concept:** V(x) = max{u(x,a) + βV(x')}  
**Alpha Stack Module:** `Reinforcement Learning Trading Agent`

```
THE MATHEMATICAL FOUNDATION OF RL:

Bellman Equation for trading:
  V(state) = max_action {reward(state, action) + γ · V(next_state)}

  Where:
    state = {price, position, P&L, volatility, regime}
    action = {BUY, SELL, HOLD, size}
    reward = realized P&L - transaction costs
    γ = discount factor (0.95 - 0.99)

Alpha Stack RL Agents:
  1. Execution Agent: Minimize slippage via optimal order splitting
  2. Position Sizing Agent: Learn Kelly-like sizing from experience
  3. Strategy Selector Agent: Choose which strategy to deploy per regime
```

### 6.4 Envelope Theorem → Sensitivity of Optimal Value

**Concept:** ∂V*/∂parameter = ∂L/∂parameter at optimum  
**Alpha Stack Module:** `Strategy Sensitivity Analyzer`

```
How sensitive is optimal performance to market parameters?

  ∂(Optimal Sharpe)/∂(correlation) = ?
  → If large: portfolio is fragile to correlation regime changes
  → If small: robust allocation

  ∂(Optimal Sharpe)/∂(volatility) = ?
  → Used to adjust allocation when vol regime shifts

This tells Alpha Stack:
  Which parameters matter most for performance
  Where to focus monitoring effort
  When to trigger re-optimization
```

### 6.5 Implicit Function Theorem → Implied Volatility Solver

**Concept:** If F(x,y) = 0, then dy/dx = -Fₓ/Fᵧ  
**Alpha Stack Module:** `Implied Volatility Solver`

```
Black-Scholes gives: V = BS(S, K, T, r, σ)

Given market price V_market, solve for σ:
  F(σ) = BS(S, K, T, r, σ) - V_market = 0

Using Newton-Raphson (root finding):
  σ_{n+1} = σ_n - F(σ_n)/F'(σ_n)
  
  where F'(σ) = Vega = ∂BS/∂σ  (from MAT 121 partial derivatives!)

This runs continuously for all traded options → builds IV surface
```

---

## 7. STA 443: Measure and Probability Theory → Risk Measure Layer

**Grade: N/A | Priority: 🔴 Critical — Measure theory underpins rigorous risk management**

STA 443 provides the rigorous mathematical foundations for probability, which underpins all risk modeling, derivatives pricing, and statistical inference.

### 7.1 σ-Algebras → Information Filtration

**Concept:** σ-algebra Fₜ represents information available at time t  
**Alpha Stack Module:** `Information State Manager`

```
Filtration: F₁ ⊆ F₂ ⊆ ... ⊆ Fₜ ⊆ ...

  Fₜ = σ(all market data up to time t)
    = σ(prices, volumes, news, order flow, ...)

Alpha Stack maintains explicit filtration:
  → Each agent's decision is Fₜ-measurable (uses only available info)
  → No look-ahead bias in backtesting (enforced by filtration structure)
  → Signal generators can only access Fₜ, not Fₜ₊₁
```

### 7.2 Measurable Functions → Random Variables

**Concept:** A function X: Ω → ℝ is F-measurable if {ω: X(ω) ≤ x} ∈ F for all x  
**Alpha Stack Module:** `Signal Validation Framework`

```
Every trading signal must be a measurable function of the information set:

  Signalₜ = f(Fₜ)  — must depend only on information available at time t

Validation:
  → Check that signal at time t doesn't use data from t+k
  → Ensure feature engineering respects temporal ordering
  → Measurability = no future information leakage
```

### 7.3 Lebesgue Integration → Expected Value Generalization

**Concept:** ∫X dP — integration with respect to a probability measure  
**Alpha Stack Module:** `Expected Value Engine`

```
Lebesgue integration generalizes Riemann integration:

  E[X] = ∫_Ω X(ω) dP(ω)

Why this matters for Alpha Stack:
  → Handles discrete + continuous distributions uniformly
  → Foundation for conditional expectation E[X|Fₜ]
  → Enables rigorous treatment of fat-tailed distributions
  → Required for change of measure (Girsanov's theorem in pricing)
```

### 7.4 Conditional Expectation → Bayesian Signal Updating

**Concept:** E[X|G] for sub-σ-algebra G ⊆ F  
**Alpha Stack Module:** `Bayesian Signal Updater`

```
Conditional expectation IS Bayesian updating:

  E[Return | Technical signals] = posterior expected return
  E[Return | Sentiment] = sentiment-adjusted expectation
  E[Return | Regime = HighVol] = regime-conditional expectation

Alpha Stack chains conditional expectations:
  Prior: E[Return] = historical mean
  Update with technical: E[Return | RSI < 30, MACD cross up]
  Update with sentiment: E[Return | RSI < 30, MACD cross up, Sentiment = Positive]
  → Each conditioning sharpens the estimate
```

### 7.5 Radon-Nikodym Derivative → Change of Measure

**Concept:** dQ/dP — density of measure Q with respect to P  
**Alpha Stack Module:** `Risk-Neutral Pricing Engine`

```
THE BRIDGE FROM REAL WORLD TO RISK-NEUTRAL WORLD:

  Under P (real-world measure): E_P[R] = expected return
  Under Q (risk-neutral measure): E_Q[R] = risk-free rate
  
  dQ/dP = Radon-Nikodym derivative = the "change of measure" density

Alpha Stack uses this for:
  → Derivatives pricing: price = E_Q[payoff] / (1+r)
  → Girsanov's theorem: how to change drift in SDEs
  → Risk premium decomposition: what the market charges for risk
```

### 7.6 Convergence Theorems → Model Validation

**Concept:** Dominated Convergence, Monotone Convergence, Fatou's Lemma  
**Alpha Stack Module:** `Backtesting Validation Framework`

```
These theorems guarantee that sample estimates converge to true values:

  Law of Large Numbers (from convergence theorems):
    (1/n) Σ Xᵢ → E[X] as n → ∞
    
  → Need sufficient sample size for reliable backtests
  → Alpha Stack enforces minimum trade counts per strategy
  
  Central Limit Theorem:
    √n(X̄ - μ)/σ → N(0,1)
    
  → Confidence intervals on strategy performance
  → Statistical significance testing of alpha
```

---

## 8. Financial Mathematics → Derivatives & Pricing Engine

These concepts come from dedicated financial mathematics study beyond Valentine's core units.

### 8.1 Black-Scholes → Options Pricing Agent

**Concept:** C = SN(d₁) - Ke^(-rT)N(d₂)  
**Alpha Stack Module:** `Options Pricing Agent`

```
Black-Scholes Pipeline:

  Inputs: S (spot), K (strike), T (time), r (rate), σ (vol)
  Output: Option price, Greeks

  d₁ = [ln(S/K) + (r + σ²/2)T] / (σ√T)
  d₂ = d₁ - σ√T

  C = S·N(d₁) - Ke^(-rT)·N(d₂)

Alpha Stack applies BS to:
  → Price BTC/ETH options on Deribit
  → Extract implied volatility from market prices
  → Compute Greeks for hedging
  → Detect mispriced options (BS price vs. market price)
```

### 8.2 Greeks → Hedging Agent Suite

**Concept:** Δ, Γ, Θ, ν, ρ  
**Alpha Stack Module:** `Hedging Agent Suite`

```
Five specialist agents, one per Greek:

  ┌─────────────┐
  │ Delta Agent  │ → Maintains delta-neutral portfolio
  │              │   Hedge ratio = -Δ_portfolio
  └─────────────┘
  ┌─────────────┐
  │ Gamma Agent  │ → Manages convexity risk
  │              │   Buy gamma before events, sell after
  └─────────────┘
  ┌─────────────┐
  │ Theta Agent  │ → Harvests time decay
  │              │   Sell options, collect daily Θ
  └─────────────┘
  ┌─────────────┐
  │ Vega Agent   │ → Trades volatility
  │              │   Buy ν before CPI, sell after
  └─────────────┘
  ┌─────────────┐
  │ Rho Agent    │ → Manages rate sensitivity
  │              │   Adjust around FOMC meetings
  └─────────────┘

Orchestrator resolves conflicts between agents
```

### 8.3 VaR & CVaR → Risk Engine

**Concept:** Maximum loss at confidence level; expected tail loss  
**Alpha Stack Module:** `Risk Engine`

```
VaR Calculation (three methods):

  1. Historical: VaR_99 = percentile(returns, 1%)
  2. Parametric: VaR_99 = μ - 2.326σ  (normal assumption)
  3. Monte Carlo: Simulate 100K paths, take 1st percentile

CVaR (Expected Shortfall):
  CVaR_99 = E[Loss | Loss > VaR_99]
  → Average loss in the worst 1% of scenarios

Risk Limits:
  IF VaR > threshold → reduce position sizes
  IF CVaR > threshold → aggressive de-risking
  IF MDD > threshold → halt all trading
```

### 8.4 Kelly Criterion → Optimal Position Sizer

**Concept:** f* = (bp - q)/b  
**Alpha Stack Module:** `Position Sizer`

```
Kelly Criterion for trading:
  f* = μ / σ²  (continuous version)
  
  where:
    μ = expected excess return
    σ² = return variance

Fractional Kelly (practical):
  f_actual = α · f*,  where α ∈ [0.25, 0.5]
  
  → Trades some growth for smoother equity curve
  → Accounts for estimation error in μ and σ

Multi-asset Kelly:
  f* = Σ⁻¹ · μ  (matrix form!)
  → This IS the maximum Sharpe portfolio weights
  → Connects Kelly to Markowitz (ECO 103 wiring)
```

---

## 9. Stochastic Processes → Price Dynamics Engine

### 9.1 Brownian Motion → Price Process Foundation

**Concept:** W(t) with independent N(0,t) increments  
**Alpha Stack Module:** `Price Process Engine`

```
Standard Brownian Motion → Foundation of all continuous-time models

  Properties:
    W(0) = 0
    Independent increments
    W(t) - W(s) ~ N(0, t-s)
    Continuous paths, nowhere differentiable

Alpha Stack uses BM as:
  → Building block for GBM, OU, and all SDE models
  → Monte Carlo path generation
  → Foundation for Black-Scholes derivation
```

### 9.2 Markov Chains → Regime Detection

**Concept:** P(Xₜ₊₁|Xₜ, Xₜ₋₁, ...) = P(Xₜ₊₁|Xₜ)  
**Alpha Stack Module:** `HMM Regime Detector`

```
Hidden Markov Model for market regimes:

  Hidden States: {Bull, Bear, Sideways, Crisis, Accumulation}
  Observations: {returns, volatility, volume, spread}

  Transition Matrix P:
         Bull   Bear   Side   Crisis Accum
  Bull  [0.70   0.10   0.15   0.02   0.03]
  Bear  [0.10   0.65   0.15   0.08   0.02]
  Side  [0.20   0.15   0.55   0.05   0.05]
  Crisis[0.05   0.30   0.10   0.50   0.05]
  Accum [0.25   0.05   0.20   0.02   0.48]

  Viterbi algorithm → decode most likely regime sequence
  Baum-Welch → learn transition matrix from data
```

### 9.3 Martingales → Fair Value & EMH Testing

**Concept:** E[Mₜ₊₁|Fₜ] = Mₜ  
**Alpha Stack Module:** `EMH Tester`

```
Martingale hypothesis = Efficient Market Hypothesis:

  If prices are martingales → no strategy can beat buy-and-hold
  
  Tests:
    → Variance ratio test: Var(rₜ + rₜ₋₁) = 2·Var(rₜ) if martingale
    → Autocorrelation test: Corr(rₜ, rₜ₋₁) = 0 if martingale
    → Hurst exponent: H = 0.5 for martingale, H > 0.5 for trending

  Alpha Stack only trades when martingale hypothesis is rejected
  → Deviations from martingale = exploitable inefficiency
```

### 9.4 Poisson Processes → Event Arrival Modeling

**Concept:** Events at rate λ, exponential inter-arrival times  
**Alpha Stack Module:** `Event Risk Engine`

```
Poisson Process for market events:

  λ = average rate of large moves (>2σ) per day
  
  P(k events in time t) = (λt)^k · e^(-λt) / k!

Alpha Stack uses this for:
  → Flash crash probability estimation
  → News event arrival modeling
  → Gap risk quantification (weekend jumps)
  → Order arrival modeling for execution optimization

Hawkes Process (self-exciting Poisson):
  λ(t) = μ + Σᵢ α·e^(-β(t-tᵢ))
  → Each event increases intensity temporarily
  → Models volatility clustering and crash contagion
```

### 9.5 Ornstein-Uhlenbeck → Mean Reversion Engine

**Concept:** dX = θ(μ - X)dt + σdW  
**Alpha Stack Module:** `Pairs Trading Engine`

```
OU Process for mean-reverting spreads:

  Spread_t = Price_A - β·Price_B  (cointegrated spread)
  dSpread = θ(μ - Spread)dt + σdW

  Parameters:
    θ = speed of mean reversion
    μ = long-run mean
    σ = volatility
    Half-life = ln(2)/θ

Trading rules:
  IF Spread < μ - 2σ → BUY spread (long A, short B)
  IF Spread > μ + 2σ → SELL spread (short A, long B)
  Exit when Spread → μ

Alpha Stack estimates OU parameters via:
  → Maximum likelihood on discrete observations
  → Kalman filter for time-varying parameters
```

### 9.6 Lévy Processes → Heavy-Tail Modeling

**Concept:** Stationary independent increments, general jumps  
**Alpha Stack Module:** `Tail Risk Engine`

```
Beyond Brownian Motion — Lévy processes capture:
  → Fat tails (kurtosis > 3)
  → Skewness (asymmetric returns)
  → Jumps (discontinuous price moves)

Models used in Alpha Stack:
  → Variance Gamma: VG(θ, σ, ν) — captures kurtosis
  → Normal Inverse Gaussian: NIG — flexible tail behavior
  → CGMY: controls fine jump structure
  
Application:
  → More accurate VaR/CVaR than Gaussian assumption
  → Better option pricing (volatility smile modeling)
  → Realistic Monte Carlo simulation
```

---

## 10. Optimization Theory → Decision Engine

### 10.1 Linear Programming → Allocation Engine

**Concept:** max cᵀx subject to Ax ≤ b, x ≥ 0  
**Alpha Stack Module:** `LP Allocation Engine`

```
Portfolio LP formulation:
  max Σᵢ rᵢ·wᵢ                    (maximize expected return)
  subject to:
    Σᵢ wᵢ = 1                      (fully invested)
    wᵢ ≤ 0.15                      (max 15% per asset)
    wᵢ ≥ 0                         (long only)
    Σᵢ βᵢ·wᵢ ≤ 1.2                (max portfolio beta)
    
  Shadow prices tell Alpha Stack:
    → Value of relaxing concentration limit
    → Cost of the long-only constraint
    → Opportunity cost of beta cap
```

### 10.2 Convex Optimization → Robust Portfolio Engine

**Concept:** min f(x) where f is convex, over convex set  
**Alpha Stack Module:** `Robust Portfolio Optimizer`

```
Convex formulations used in Alpha Stack:

  1. Mean-Variance (QP): min wᵀΣw  s.t. wᵀμ ≥ r_target
  2. Risk Parity: min Σᵢ(wᵢ(Σw)ᵢ - σ²_p/n)²  s.t. Σw = 1
  3. Robust (SOCP): max min_{μ∈U} wᵀμ  s.t. wᵀΣw ≤ σ²_max

  Convexity guarantees:
    → Global optimum found (no local optima traps)
    → Fast solving (polynomial time)
    → KKT conditions verify optimality
```

### 10.3 Gradient Descent (Adam) → Neural Network Training

**Concept:** θ ← θ - α·m̂/(√v̂ + ε)  
**Alpha Stack Module:** `Model Training Pipeline`

```
Adam optimizer for all Alpha Stack neural networks:

  Hyperparameters:
    α = 0.001 (learning rate, with cosine decay schedule)
    β₁ = 0.9 (momentum decay)
    β₂ = 0.999 (RMSprop decay)
    ε = 1e-8

  Training pipeline:
    → Warmup: 5% of steps, linear LR increase
    → Training: cosine decay to 10% of initial LR
    → Early stopping: validation Sharpe degradation
    → Gradient clipping: max norm = 1.0

  Models trained:
    → LSTM price predictor
    → Transformer cross-asset attention
    → Sentiment classifier
    → RL policy/value networks
```

### 10.4 Genetic Algorithms → Strategy Evolution Engine

**Concept:** Population, selection, crossover, mutation  
**Alpha Stack Module:** `Strategy Evolution Engine`

```
GA for trading strategy evolution:

  Chromosome = [entry_threshold, exit_threshold, stop_loss, 
                take_profit, lookback_period, indicator_weights, ...]
  
  Population size: 500 strategies
  Generations: 100
  
  Fitness = out-of-sample Sharpe ratio
  
  Selection: Tournament selection (k=5)
  Crossover: Uniform crossover (50% swap rate)
  Mutation: Gaussian perturbation (σ = 10% of parameter range)
  
  Runs nightly → produces next generation of strategies
  Top strategies promoted to live paper trading
```

### 10.5 Multi-Objective (NSGA-II) → Strategy Trade-Off Explorer

**Concept:** Pareto front of competing objectives  
**Alpha Stack Module:** `Pareto Strategy Explorer`

```
Multi-objective optimization:
  Maximize: Return, Sharpe Ratio
  Minimize: Max Drawdown, Transaction Costs, Correlation

NSGA-II produces Pareto front:
  → Strategy A: High return, high drawdown (aggressive)
  → Strategy B: Medium return, low drawdown (conservative)
  → Strategy C: High Sharpe, medium everything (balanced)

Portfolio manager selects from the front based on risk appetite
All points on the front are optimal — no objective can improve 
without worsening another
```

---

## 11. Integration Wiring: How Everything Connects

### 11.1 The Complete Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                     ALPHA STACK MATH PIPELINE                       │
│                                                                     │
│  ┌──────────┐    ┌───────────┐    ┌───────────┐    ┌──────────┐   │
│  │ MAT 101  │    │ MAT 121   │    │ MAT 124   │    │ ECO 103  │   │
│  │          │    │           │    │           │    │          │   │
│  │ Set Ops  │───→│ Derivatives│──→│ Integrals │───→│ Matrices │   │
│  │ Logic    │    │ Gradients │    │ Areas     │    │ Eigenvals│   │
│  │ Functions│    │ Chain Rule│    │ FTC       │    │ Solvers  │   │
│  └──────────┘    └───────────┘    └───────────┘    └──────────┘   │
│       │               │               │               │           │
│       ▼               ▼               ▼               ▼           │
│  ┌──────────────────────────────────────────────────────────┐     │
│  │              UNIFIED SIGNAL GENERATOR                     │     │
│  │  Momentum (MAT121) + Volume (MAT124) + Factor (ECO103)   │     │
│  └──────────────────────────────────────────────────────────┘     │
│       │               │               │               │           │
│       ▼               ▼               ▼               ▼           │
│  ┌──────────┐    ┌───────────┐    ┌───────────┐    ┌──────────┐   │
│  │ ECO 104  │    │ STA 443   │    │ Fin Math  │    │ Stoch    │   │
│  │          │    │           │    │           │    │ Processes│   │
│  │ DP/Bellman│──→│ Measures  │───→│ Black-Sch │──→│ BM, OU   │   │
│  │ ODE/SDE  │    │ Cond.Exp  │    │ Greeks    │    │ Markov   │   │
│  │ Env.Thm  │    │ R-N deriv │    │ VaR/Kelly │    │ Martingale│  │
│  └──────────┘    └───────────┘    └───────────┘    └──────────┘   │
│       │               │               │               │           │
│       ▼               ▼               ▼               ▼           │
│  ┌──────────────────────────────────────────────────────────┐     │
│  │              RISK & PORTFOLIO ENGINE                      │     │
│  │  Markowitz (ECO103) + Kelly (FinMath) + DP (ECO104)      │     │
│  └──────────────────────────────────────────────────────────┘     │
│       │                                                           │
│       ▼                                                           │
│  ┌──────────────────────────────────────────────────────────┐     │
│  │              EXECUTION LAYER                              │     │
│  │  Gradient descent (Optim) + Genetic Algo (Optim)          │     │
│  │  LP allocation (Optim) + RL agents (ECO104)               │     │
│  └──────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────┘
```

### 11.2 Cross-Unit Concept Dependencies

| Concept | Requires From | Enables In |
|---------|-------------|------------|
| Chain rule (MAT 121) | Functions (MAT 101) | Backpropagation, Greeks cascade |
| Partial derivatives (MAT 121) | Functions (MAT 101) | Greeks, sensitivity matrix, gradient |
| FTC (MAT 124) | Derivatives (MAT 121) | Return aggregation, VWAP |
| Probability integrals (MAT 124) | FTC (MAT 124) | VaR, expected value, signal confidence |
| Matrix inversion (ECO 103) | Matrix ops (ECO 103) | Markowitz solver, factor calibration |
| Eigenvalues (ECO 103) | Matrix ops (ECO 103) | PCA, factor decomposition, regime detection |
| Lagrange multipliers (ECO 103) | Derivatives (MAT 121) | Constrained portfolio optimization |
| ODEs (ECO 104) | Derivatives (MAT 121) | SDE engine, continuous-time models |
| Dynamic programming (ECO 104) | Optimization (MAT 121) | RL agents, Bellman equation |
| σ-algebra (STA 443) | Set theory (MAT 101) | Filtration, information state |
| Conditional expectation (STA 443) | Integration (MAT 124) | Bayesian updating, signal conditioning |
| Black-Scholes (Fin Math) | SDEs (ECO 104) + FTC (MAT 124) | Options pricing, implied vol |
| Greeks (Fin Math) | Partial derivatives (MAT 121) | Hedging agents |
| Markov chains (Stoch Proc) | Probability (STA 443) | Regime detection |
| Martingales (Stoch Proc) | Conditional expectation (STA 443) | EMH testing, fair pricing |
| Kelly Criterion (Fin Math) | Matrix inversion (ECO 103) + Expected value (MAT 124) | Position sizing |
| Adam optimizer (Optim) | Gradient (MAT 121) + Chain rule (MAT 121) | Neural network training |

### 11.3 The Feedback Loops

```
Loop 1: Signal Generation Loop
  MAT 121 (momentum) + MAT 124 (volume) + ECO 103 (factors)
  → Signal → Execution → P&L → Update parameters (gradient descent)

Loop 2: Risk Management Loop  
  STA 443 (VaR) + Fin Math (Greeks) + Stoch Proc (regime)
  → Risk check → Position adjustment → Re-evaluate risk

Loop 3: Portfolio Optimization Loop
  ECO 103 (Markowitz) + ECO 104 (dynamic rebalancing) + Optim (LP)
  → Optimize → Execute rebalance → Monitor drift → Re-optimize

Loop 4: Strategy Evolution Loop
  Optim (GA) + ECO 104 (DP) + MAT 121 (gradient)
  → Evolve strategies → Backtest → Select → Deploy → Monitor → Evolve

Loop 5: Model Retraining Loop
  Optim (Adam) + MAT 121 (backprop) + STA 443 (validation)
  → Train on new data → Validate out-of-sample → Deploy → Monitor → Retrain
```

---

## 12. Gap Analysis & Remediation Plan

### 12.1 Critical Gaps from Grade Analysis

| Gap | Impact | Remediation |
|-----|--------|-------------|
| **MAT 101 (D)** — Weak foundations | Errors propagate upward through all layers | Intensive review: sets, logic, functions, sequences. Practice until 90%+ confidence |
| **MAT 124 (C)** — Integration weakness | Impairs option pricing, probability calculations, VWAP | Focus on: FTC applications, integration techniques, probability integrals |
| **STA 443 (N/A)** — Unknown measure theory depth | Measure theory underpins all rigorous probability | Assess current level; if weak, prioritize σ-algebras, conditional expectation, convergence theorems |

### 12.2 Wiring Readiness Assessment

| Module | Required Concepts | Valentine's Readiness | Action |
|--------|------------------|----------------------|--------|
| Momentum Engine | Derivatives (MAT 121) | ✅ B grade — adequate | Wire immediately |
| Greeks Calculator | Partial derivatives (MAT 121) | ✅ B grade — adequate | Wire immediately |
| Covariance Engine | Matrix ops (ECO 103) | ✅ A grade — strong | Wire immediately, leverage strength |
| PCA Factor Engine | Eigenvalues (ECO 103) | ✅ A grade — strong | Wire immediately |
| Markowitz Solver | Matrix inversion (ECO 103) | ✅ A grade — strong | Wire immediately |
| Volume Profile | Integration (MAT 124) | ⚠️ C grade — needs reinforcement | Practice first, then wire |
| VWAP Engine | Integration (MAT 124) | ⚠️ C grade — needs reinforcement | Practice first, then wire |
| Bayesian Updater | Conditional probability (STA 443) | ❓ Unknown | Assess, then wire |
| Options Pricer | SDEs (ECO 104) + integration (MAT 124) | ⚠️ Mixed readiness | Strengthen integration, then wire |
| RL Agents | DP (ECO 104) | ✅ B grade — adequate | Wire with guidance |
| Regime Detector | Markov chains (STA 443) | ❓ Unknown | Assess, then wire |
| Neural Network Training | Chain rule (MAT 121) + gradient (MAT 121) | ✅ B grade — adequate | Wire immediately |

### 12.3 Priority Wiring Order

```
Phase 1 (Immediate — leverage strengths):
  ✅ Covariance Matrix Engine (ECO 103 — A grade)
  ✅ PCA Factor Engine (ECO 103 — A grade)
  ✅ Markowitz Solver (ECO 103 — A grade)
  ✅ Momentum Engine (MAT 121 — B grade)
  ✅ Greeks Calculator (MAT 121 — B grade)
  ✅ Neural Network Training Pipeline (MAT 121 — B grade)

Phase 2 (After MAT 124 remediation):
  ⚠️ Volume Profile Engine
  ⚠️ VWAP Engine
  ⚠️ Probability/Confidence Scorer
  ⚠️ Options Pricer (Black-Scholes)

Phase 3 (After STA 443 assessment):
  ❓ Bayesian Signal Updater
  ❓ HMM Regime Detector
  ❓ Risk-Neutral Pricing Engine
  ❓ EMH Tester (Martingale tests)
```

---

## 13. Agent Assignment Matrix

### 13.1 Which Math Feeds Which Agent

| Alpha Stack Agent | Primary Math Sources | Secondary Math Sources |
|---|---|---|
| **Trend Agent** | MAT 121 (derivatives, momentum) | ECO 104 (difference equations) |
| **Mean-Reversion Agent** | ECO 104 (OU process) | STA 443 (stationarity), MAT 124 (probability) |
| **Carry Agent** | ECO 104 (interest rate ODEs) | Fin Math (PV, yield curves) |
| **Volatility Agent** | Fin Math (Greeks, IV) | Stoch Proc (quadratic variation), MAT 121 (gamma) |
| **Options Agent** | Fin Math (Black-Scholes) | MAT 121 (Greeks), STA 443 (risk-neutral measure) |
| **Risk Agent** | STA 443 (VaR, CVaR) | Fin Math (Greeks), MAT 124 (tail integrals) |
| **Portfolio Agent** | ECO 103 (Markowitz, PCA) | Optim (LP, convex), ECO 104 (dynamic rebalancing) |
| **Execution Agent** | Optim (LP, Adam) | ECO 104 (DP), DSA (order book structures) |
| **Regime Agent** | Stoch Proc (Markov, HMM) | STA 443 (σ-algebras, filtration) |
| **NLP/Sentiment Agent** | Optim (Adam for training) | MAT 121 (backprop), STA 443 (Bayesian) |
| **Meta Agent** | ECO 104 (DP/Bellman) | Optim (GA, NSGA-II), Fin Math (Kelly) |

### 13.2 Math Concept → Agent Wiring Summary

```
MAT 101 (Set Theory, Logic, Functions)
  → Universe Manager (asset filtering)
  → Signal Rule Engine (compound logic)
  → Pipeline Architecture (function composition)

MAT 121 (Derivatives, Chain Rule, Optimization)
  → Momentum Engine (dP/dt)
  → Greeks Calculator (∂V/∂S, ∂²V/∂S²)
  → Neural Network Training (backpropagation)
  → Parameter Optimizer (f' = 0)
  → Sensitivity Cascade Analyzer (chain rule)

MAT 124 (Integration, FTC, Probability)
  → Volume Profile Engine (∫v(t)dt)
  → VWAP Engine (∫P·V / ∫V)
  → Return Calculator (FTC)
  → Probability Scorer (∫f(r)dr)
  → Perpetual Risk Model (∫₀^∞)

ECO 103 (Matrices, Eigenvalues, Systems)
  → Covariance Matrix Engine (wᵀΣw)
  → PCA Factor Engine (eigendecomposition)
  → Markowitz Solver (Σ⁻¹μ)
  → Redundancy Detector (det = 0)
  → Signal Orthogonality Checker (rank, independence)
  → Factor Model Calibrator (Ax = b)

ECO 104 (Diff Eq, DP, Comparative Statics)
  → AR Model Engine (difference equations)
  → SDE Engine (GBM, OU, CIR)
  → RL Trading Agent (Bellman equation)
  → Sensitivity Analyzer (envelope theorem)
  → Implied Vol Solver (implicit function theorem)

STA 443 (Measures, Conditional Expectation, R-N)
  → Information State Manager (filtration)
  → Signal Validation (measurability)
  → Bayesian Signal Updater (E[X|G])
  → Risk-Neutral Pricing Engine (dQ/dP)
  → Backtesting Validator (convergence theorems)

Financial Mathematics
  → Options Pricer (Black-Scholes)
  → Hedging Agents (Greeks)
  → Risk Engine (VaR, CVaR, Sharpe)
  → Position Sizer (Kelly Criterion)
  → Bond/Fixed Income Module (duration, convexity)

Stochastic Processes
  → Price Process Engine (Brownian Motion)
  → Regime Detector (Markov, HMM)
  → EMH Tester (Martingales)
  → Event Risk Engine (Poisson, Hawkes)
  → Pairs Trading Engine (OU process)
  → Tail Risk Engine (Lévy processes)

Optimization Theory
  → LP Allocation Engine (Simplex)
  → Robust Portfolio Optimizer (SOCP, convex)
  → Model Training Pipeline (Adam, SGD)
  → Strategy Evolution Engine (GA)
  → Pareto Strategy Explorer (NSGA-II)
```

---

## Appendix A: Mathematical Concept Quick Reference

| Concept | Symbol | Alpha Stack Module | Formula |
|---------|--------|-------------------|---------|
| Derivative | f'(x) | Momentum Engine | lim[f(x+h)-f(x)]/h |
| Partial Derivative | ∂f/∂x | Greeks Calculator | ∂V/∂S, ∂²V/∂S² |
| Gradient | ∇f | Optimization Engine | (∂f/∂x₁, ..., ∂f/∂xₙ) |
| Chain Rule | d/dx f(g(x)) | Backpropagation | f'(g(x))·g'(x) |
| Definite Integral | ∫ₐᵇ f(x)dx | Volume Profile | Σf(xᵢ)·Δx |
| FTC | ∫ₐᵇ f = F(b)-F(a) | Return Calculator | Σreturns = total return |
| Matrix Multiply | AB | Covariance Engine | wᵀΣw |
| Inverse | A⁻¹ | Markowitz Solver | Σ⁻¹μ |
| Eigenvalue | Av = λv | PCA Engine | Σ = VΛVᵀ |
| Lagrangian | L = f - λg | Portfolio Optimizer | max return - λ·risk |
| Bellman Equation | V(x) = max{r + γV(x')} | RL Agent | DP for trading |
| Black-Scholes | C = SN(d₁)-Ke⁻ʳᵀN(d₂) | Options Pricer | Derivative valuation |
| VaR | P(Loss > VaR) = α | Risk Engine | Percentile of losses |
| Kelly | f* = μ/σ² | Position Sizer | Optimal bet fraction |
| GBM | dS = μSdt + σSdW | Price Process | Asset dynamics |
| OU Process | dX = θ(μ-X)dt + σdW | Pairs Trading | Mean reversion |
| Transition Matrix | P = [pᵢⱼ] | Regime Detector | HMM parameters |
| Martingale | E[Mₜ₊₁\|Fₜ] = Mₜ | EMH Tester | Fair game test |

---

## Appendix B: Wiring Checklist

- [ ] **Phase 1** — Wire ECO 103 modules (covariance, PCA, Markowitz)
- [ ] **Phase 1** — Wire MAT 121 modules (momentum, Greeks, backprop)
- [ ] **Phase 2** — Remediate MAT 124 integration skills
- [ ] **Phase 2** — Wire MAT 124 modules (volume, VWAP, probability)
- [ ] **Phase 3** — Assess STA 443 measure theory depth
- [ ] **Phase 3** — Wire STA 443 modules (filtration, Bayesian, R-N)
- [ ] **Phase 4** — Wire Financial Mathematics modules (BS, Greeks, VaR)
- [ ] **Phase 4** — Wire Stochastic Process modules (BM, Markov, OU)
- [ ] **Phase 5** — Wire Optimization modules (LP, Adam, GA)
- [ ] **Phase 5** — Integration testing across all modules
- [ ] **Phase 6** — End-to-end pipeline validation
- [ ] **Phase 6** — Agent assignment and orchestration testing

---

*This architecture document defines the complete mathematical wiring from Valentine's academic curriculum to Alpha Stack's production modules. Every concept has a home. Every module has mathematical foundations. The gaps are identified. The plan is clear.*

*Mathematics is not just the foundation — it IS the system.*
