# Architecture: Statistics Curriculum → Alpha Stack Module Wiring

> **Author:** Statistics Curriculum Architect Agent  
> **Date:** 2026-07-11  
> **Purpose:** Map every concept from Valentine's 13 statistics units (STA 142–STA 444) to specific Alpha Stack modules, agents, and code-level components. This is the implementation blueprint — not a research report, but an engineering specification.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Module Wiring Map](#2-module-wiring-map)
3. [Unit-by-Unit Architecture](#3-unit-by-unit-architecture)
4. [Data Flow: Statistics → Signal → Trade](#4-data-flow-statistics--signal--trade)
5. [Agent-Skill Matrix](#5-agent-skill-matrix)
6. [Implementation Priority](#6-implementation-priority)

---

## 1. Architecture Overview

Alpha Stack's 16-step Alpha Strategy pipeline consumes statistical methods at every stage. Valentine's statistics coursework provides the mathematical backbone for **7 core engine subsystems**:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ALPHA STACK ENGINE SUBSYSTEMS                     │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ DISTRIBUTION │  │ ESTIMATION   │  │ HYPOTHESIS   │              │
│  │   ENGINE     │  │   ENGINE     │  │  TESTING     │              │
│  │              │  │              │  │   ENGINE     │              │
│  │ STA 142      │  │ STA 341      │  │ STA 342      │              │
│  │ STA 241      │  │ STA 241      │  │ STA 444      │              │
│  │ STA 443      │  │ STA 347      │  │              │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
│         │                 │                  │                      │
│  ┌──────▼───────┐  ┌──────▼───────┐  ┌──────▼───────┐              │
│  │ TIME SERIES  │  │ MULTIVARIATE │  │ QUALITY      │              │
│  │   ENGINE     │  │   ENGINE     │  │  CONTROL     │              │
│  │              │  │              │  │   ENGINE     │              │
│  │ STA 244      │  │ STA 442      │  │ STA 346      │              │
│  │ STA 245      │  │ STA 343      │  │ STA 343      │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
│         │                 │                  │                      │
│         └─────────────────┼──────────────────┘                      │
│                           ▼                                          │
│              ┌──────────────────────┐                                │
│              │   COMPUTE LAYER      │                                │
│              │   (Statistical       │                                │
│              │    Computing Engine) │                                │
│              │   STA 347            │                                │
│              │   STA 443            │                                │
│              └──────────────────────┘                                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Module Wiring Map

### 2.1 STA 142 — Probability Theory (Grade: C, 54%)

| Concept | Alpha Stack Module | Agent | Code Component |
|---------|-------------------|-------|----------------|
| **Bayes' Theorem** | Signal Engine → Bayesian Updater | Fundamental Agent, Confluence Scorer | `signal/bayesian_updater.py` — Updates signal confidence as new data arrives. Prior = historical win rate; Likelihood = current market conditions; Posterior = updated signal strength. Runs for EVERY signal in REAL-TIME. |
| **Conditional Probability** | Signal Engine → Signal Conditioning | All signal agents | `signal/conditional.py` — "P(move UP \| RSI < 30 AND volume > 3x)" — the core of every trading signal. Each agent computes conditional probabilities for its signal type. |
| **Random Variables (PMF/PDF)** | Distribution Engine → Return Modeler | Distribution Agent | `risk/return_distribution.py` — Fits PDFs to asset returns using KDE and parametric distributions. Drives VaR, CVaR, and option pricing. |
| **Expected Value & Variance** | Signal Engine → Trade Evaluator | Signal Aggregator | `signal/trade_evaluator.py` — EV = P(win) × avg_win − P(loss) × avg_loss. Only positive-EV trades pass the confluence gate. Variance drives Kelly position sizing. |
| **Common Distributions** | Distribution Engine | Distribution Agent | `risk/distributions.py` — Binomial (win/loss modeling), Poisson (order arrival), Normal (baseline), Exponential (time-between-events). Each distribution maps to a specific modeling task. |
| **Joint Distributions** | Multi-Asset Engine → Correlation Matrix | Correlation Agent | `portfolio/correlation_matrix.py` — Joint distributions of EUR/USD and DXY, oil and CAD. Cross-asset correlation modeling for pairs trading and hedging. |
| **Covariance & Correlation** | Portfolio Engine → Covariance Matrix | Portfolio Optimizer | `portfolio/covariance.py` — Rolling correlation matrices across all assets. Regime-conditional correlation switching (correlations spike in crises). THE most important input to portfolio optimization. |
| **Law of Large Numbers** | Backtesting Engine → Sample Validator | Reflection Agent | `backtest/sample_validator.py` — Enforces minimum trade counts before deploying a strategy. Signal must be tested over sufficient sample sizes. |
| **Central Limit Theorem** | Risk Engine → Time Horizon Converter | Risk Manager | `risk/horizon_converter.py` — Daily returns (non-normal) aggregate toward normality over longer periods. Adjusts risk metrics across timeframes. |
| **Independence** | Portfolio Engine → Diversification Logic | Portfolio Optimizer | `portfolio/diversification.py` — Tests signal independence using correlation matrices. Independent signals achieve true diversification. |

### 2.2 STA 241 — Probability and Distribution Models (Grade: A, 77%)

| Concept | Alpha Stack Module | Agent | Code Component |
|---------|-------------------|-------|----------------|
| **PMF/PDF** | Distribution Engine → Return Modeler | Distribution Agent | `risk/return_distribution.py` — Kernel density estimation for non-parametric distributions. Fat-tail detection using kurtosis tests. |
| **CDF** | Risk Engine → VaR Calculator | Risk Manager | `risk/var_calculator.py` — VaR = inverse CDF at confidence level. VaR₉₅% = CDF⁻¹(0.05) for the loss distribution. |
| **Moment Generating Functions** | Distribution Engine → Distribution Characterizer | Distribution Agent | `risk/mgf.py` — Computes all moments from a single function. Used for complex distributions where direct moment computation is difficult. |
| **Bernoulli/Binomial** | Signal Engine → Trade Outcome Modeler | Signal Aggregator | `signal/trade_outcome.py` — Each trade is a Bernoulli trial. n trades follow binomial. Computes probability of k wins in n trades. Sets confidence intervals on win rates. |
| **Poisson Distribution** | Execution Engine → Order Arrival Modeler | Execution Agent | `execution/order_arrival.py` — Models trade signal frequency. Also models large price jump arrivals for jump-diffusion price models. |
| **Student's t-Distribution** | Distribution Engine → Fat-Tail Modeler | Distribution Agent | `risk/fat_tail.py` — Financial returns have heavier tails than normal. Student-t with 3-5 df is better for returns. Produces more realistic VaR estimates. |
| **Beta Distribution** | Signal Engine → Win Rate Estimator | Fundamental Agent | `signal/win_rate.py` — Beta(α wins + 1, β losses + 1). Bayesian updating with beta distribution tracks evolving win rates. |
| **Copulas** | Risk Engine → Dependency Modeler | Risk Manager | `risk/copulas.py` — Captures non-linear dependence (tail dependence) that correlation misses. During crises, assets become more correlated in the tails. |
| **Gamma/Chi-Square** | Distribution Engine | Distribution Agent | `risk/gamma_chisq.py` — Gamma for variance distribution modeling. Chi-square for independence testing of returns. |

### 2.3 STA 244 — Time Series Analysis & Forecasting (Grade: D, 45%)

| Concept | Alpha Stack Module | Agent | Code Component |
|---------|-------------------|-------|----------------|
| **Stationarity (ADF/KPSS)** | Data Pipeline → Preprocessing | Data Quality Agent | `data/stationarity_tests.py` — Tests every input series before modeling. Non-stationary series are differenced. Prevents spurious regression. |
| **ACF/PACF** | Time Series Engine → Model Identification | Time Series Agent | `signal/acf_pacf.py` — ACF/PACF patterns identify appropriate ARMA model order. Automated model selection for each currency pair. |
| **AR(p) Models** | Signal Engine → Mean Reversion | Mean-Reversion Agent | `signal/ar_model.py` — AR(1) coefficient < 1 → mean-reverting pair. Estimates AR coefficients for currency pairs. Candidates for mean-reversion strategies. |
| **MA(q) Models** | Signal Engine → Momentum | Momentum Agent | `signal/ma_model.py` — Captures how past shocks affect current prices. Significant MA terms indicate persistent shock effects. |
| **ARMA(p,q)** | Time Series Engine → Price Modeler | Time Series Agent | `signal/arma_model.py` — Full short-term price dynamics. Model selection via AIC/BIC. Baseline forecast for all time series. |
| **ARIMA(p,d,q)** | Time Series Engine → Multi-Horizon Forecaster | Time Series Agent | `signal/arima_model.py` — Captures trend (d), short-term dynamics (AR), and shock persistence (MA). Multi-horizon forecasting: 1-5 periods (short), 5-20 periods (medium). |
| **SARIMA** | Signal Engine → Intraday Patterns | Seasonality Agent | `signal/sarima_model.py` — London-New York overlap patterns, Asian session patterns, Monday direction-setting, Friday position squaring. |
| **Cointegration** | Pairs Trading Engine | Pairs Agent | `pairs/cointegration.py` — Engle-Granger and Johansen tests. Only trades pairs with confirmed cointegrating relationships. Error correction term = trading signal. |
| **VAR Models** | Multi-Asset Engine → Cross-Asset Forecaster | Macro Agent | `signal/var_model.py` — EUR/USD depends on its own past AND GBP/USD's past AND USD/JPY's past. Impulse response analysis for shock propagation. |
| **GARCH/ARCH** | Risk Engine → Volatility Forecaster | Volatility Agent | `risk/garch.py` — Predicts future volatility from current conditions. Dynamic position sizing, dynamic stop-losses, option pricing. EGARCH for asymmetric effects. |
| **Exponential Smoothing** | Signal Engine → Adaptive Forecaster | Time Series Agent | `signal/exp_smoothing.py` — Holt-Winters' for intraday price forecasting. Captures trend + time-of-day patterns. Recent data weighted more heavily. |
| **Forecast Accuracy (MAE/RMSE)** | Backtesting Engine → Model Evaluator | Reflection Agent | `backtest/forecast_metrics.py` — RMSE preferred for trading (large errors costly). Models with degrading accuracy are automatically flagged for re-estimation. |

### 2.4 STA 245 — Social & Economic Statistics (Grade: C, 51%)

| Concept | Alpha Stack Module | Agent | Code Component |
|---------|-------------------|-------|----------------|
| **Price Indices (Laspeyres, Paasche)** | Macro Engine → Inflation Monitor | Fundamental Agent | `macro/inflation_monitor.py` — CPI (Laspeyres, overstates), PCE (Paasche). System monitors both to assess true inflation. Different readings → different central bank responses → different currency impacts. |
| **National Income Accounting** | Macro Engine → GDP Module | Fundamental Agent | `macro/gdp_module.py` — GDP components: C → retail sales; I → PMI; G → budget data; NX → trade balance. Each drives different sector performance. |
| **Balance of Payments** | Macro Engine → BOP Tracker | Fundamental Agent | `macro/bop_tracker.py` — Current account deficits signal currency weakness. Capital flow monitoring. Adjustments through exchange rate, income, or prices. |
| **CPI & Inflation Measurement** | Signal Engine → Event Trader | Event Agent | `signal/cpi_event.py` — CPI releases are HIGH-IMPACT events. Models consensus forecast, trades the surprise (actual − forecast). CPI surprises cause immediate, large currency moves. |
| **Survey Methods & Data Quality** | Data Pipeline → Quality Engine | Data Quality Agent | `data/quality_checks.py` — Assesses quality of economic data. Identifies potential biases in CPI, employment, GDP data. Data revision tracking. |

### 2.5 STA 246 — Statistical Demography (Grade: B, 66%)

| Concept | Alpha Stack Module | Agent | Code Component |
|---------|-------------------|-------|----------------|
| **Population Growth Rate** | Macro Engine → Long-Term Signals | Macro Agent | `macro/demographic_signals.py` — Growing populations → growing labor forces → long-term currency potential. Declining populations → deflationary pressures. |
| **Age Structure & Dependency Ratios** | Macro Engine → Demographic Dividend | Macro Agent | `macro/demographic_dividend.py` — Low dependency ratios → higher savings, investment, growth → currency appreciation. Monitors demographic transitions as long-term signals. |
| **Urbanization** | Macro Engine → Development Proxy | Macro Agent | `macro/urbanization.py` — Rapid urbanization signals structural economic transformation → productivity growth → potential currency appreciation. Satellite-based tracking. |

### 2.6 STA 341 — Theory of Estimation (Grade: B, 66%)

| Concept | Alpha Stack Module | Agent | Code Component |
|---------|-------------------|-------|----------------|
| **Unbiasedness** | Estimation Engine → Model Calibration | All estimation agents | `estimation/bias_test.py` — Tests parameter estimates for bias using bootstrap and simulation. OLS alpha estimates must be unbiased for proper strategy evaluation. |
| **Efficiency (CRLB)** | Estimation Engine → Signal Extractor | Signal Agents | `estimation/crlb.py` — The Cramér-Rao lower bound tells the system the theoretical best precision for any signal estimate. If system's estimator is near CRLB, it's optimally using data. |
| **Consistency** | Backtesting Engine → Convergence Checker | Reflection Agent | `backtest/convergence.py` — As more data accumulates, estimates should converge to true values. Inconsistent estimators → strategies that never stabilize. |
| **Sufficiency** | Data Pipeline → Data Compressor | Data Quality Agent | `data/sufficient_stats.py` — For normally distributed returns, sample mean and variance are sufficient. All higher moments are noise. Compresses data without losing information. |
| **Method of Moments** | Estimation Engine → Quick Estimator | All estimation agents | `estimation/mom.py` — Rapid initial parameter estimates. GMM (Generalized Method of Moments) for financial models where exact likelihood is unavailable. |
| **Maximum Likelihood Estimation** | Estimation Engine → Core Estimator | All model agents | `estimation/mle.py` — GARCH parameters, HMM parameters, copula parameters, option pricing calibration. THE workhorse for any model with a well-specified likelihood. |
| **Bayesian Estimation** | Signal Engine → Adaptive Updater | Fundamental Agent | `estimation/bayesian.py` — Prior (historical base rate) + Likelihood (current conditions) = Posterior (updated probability). Runs for EVERY signal in REAL-TIME. |
| **Confidence Intervals** | Risk Engine → Performance Reporter | Risk Manager | `risk/confidence_intervals.py` — Reports strategy returns with CIs, not just point estimates. 10% ± 3% (95% CI) is very different from 10% ± 15%. |
| **Rao-Blackwell Theorem** | Estimation Engine → Signal Improver | Signal Agents | `estimation/rao_blackwell.py` — Conditioning on sufficient statistics improves estimates. If raw signal uses only price data, conditioning on volume improves it. |
| **Fisher Information** | Estimation Engine → Information Meter | Signal Agents | `estimation/fisher_info.py` — Determines optimal learning rate in online learning. Higher Fisher information → data is more informative → larger updates justified. Natural gradient descent uses Fisher information matrix. |

### 2.7 STA 342 — Test of Hypothesis (Grade: D, 41%)

| Concept | Alpha Stack Module | Agent | Code Component |
|---------|-------------------|-------|----------------|
| **Null/Alternative Hypotheses** | Backtesting Engine → Strategy Validator | Reflection Agent | `backtest/hypothesis_test.py` — Every new strategy enters with H₀: "no edge (alpha = 0)." Requires strong evidence to reject H₀. One-tailed for directional strategies, two-tailed for risk metrics. |
| **Type I/II Errors** | Backtesting Engine → Error Manager | Reflection Agent | `backtest/error_manager.py` — Type I = deploying a bad strategy (overfitting). Type II = missing a good strategy. Calibrates α and β based on costs. α should be low (don't deploy bad strategies). |
| **P-Values** | Signal Engine → Alpha Scorer | Signal Aggregator | `signal/pvalue_scorer.py` — Assigns p-values to every signal. p < 0.05 = "significant," p < 0.01 = "highly significant." Maintains ranked list. Also considers effect size and economic significance. |
| **t-Tests & z-Tests** | Backtesting Engine → Return Tester | Reflection Agent | `backtest/ttest.py` — One-sample: are returns ≠ 0? Two-sample: is Strategy A better than B? Paired: before/after model upgrade. Runs daily for all active strategies. |
| **Chi-Squared Tests** | Distribution Engine → Fit Tester | Distribution Agent | `distribution/chi_squared.py` — Goodness of fit: do returns follow assumed distributions? Independence: are trades independent (no serial correlation)? |
| **F-Test (ANOVA)** | Backtesting Engine → Model Comparator | Reflection Agent | `backtest/f_test.py` — Overall factor model significance. Does adding a new factor improve the model? ANOVA compares strategy performance across regimes. |
| **Non-Parametric Tests** | Backtesting Engine → Robust Tester | Reflection Agent | `backtest/nonparametric.py` — Wilcoxon, Mann-Whitney, Kruskal-Wallis. Used when return distributions are non-normal. More robust to outliers and heavy tails. If parametric and non-parametric tests disagree, non-parametric result is preferred. |
| **Likelihood Ratio Test** | Model Selection Engine | Model Selector | `model_selection/lrt.py` — Compares nested models. Is 5-factor model significantly better than 3-factor? Balances fit vs. complexity. Prevents overfitting. |
| **Multiple Testing Corrections** | Signal Engine → Anti-Data-Mining | Signal Aggregator | `signal/multiple_testing.py` — CRITICAL. Tests thousands of signals — without correction, many "significant" signals are false positives. Implements: (1) Bonferroni for conservative screening, (2) BH-FDR for signal discovery, (3) out-of-sample testing as ultimate correction. |
| **Bootstrap Tests** | Backtesting Engine → Robust Validator | Reflection Agent | `backtest/bootstrap_test.py` — Confidence intervals for Sharpe ratios without distributional assumptions. Permutation tests verify performance isn't due to luck. |

### 2.8 STA 343 — Experimental Designs (Grade: C, 58%)

| Concept | Alpha Stack Module | Agent | Code Component |
|---------|-------------------|-------|----------------|
| **Randomization** | Backtesting Engine → Test Design | Reflection Agent | `backtest/randomization.py` — Randomizes order/timing of signal generation to prevent order effects. Randomized cross-validation for backtesting. Prevents look-ahead bias. |
| **Replication** | Backtesting Engine → Multi-Period Test | Reflection Agent | `backtest/replication.py` — Replicates strategy tests across multiple time periods, market regimes, and geographies. A strategy that works in one period but not others lacks robustness. |
| **Blocking** | Backtesting Engine → Regime-Blocked Test | Reflection Agent | `backtest/blocking.py` — Blocks by market regime (high vol/low vol, bull/bear). Within each regime, strategies are compared fairly. Reduces noise from regime changes. |
| **Factorial Design** | Signal Engine → Multi-Factor Tester | Signal Aggregator | `signal/factorial_test.py` — Tests multiple signal factors simultaneously. Full factorial: all combinations. Interaction effects (momentum × value) often more important than main effects. |
| **Response Surface Methodology** | Parameter Optimizer | Optimization Agent | `optimization/rsm.py` — Sequential experiments to find optimal strategy parameters. Screen important parameters first, then model the response surface (Sharpe as function of parameters), then find optimum. More efficient than grid search. |
| **Latin Square Design** | Backtesting Engine → Balanced Test | Reflection Agent | `backtest/latin_square.py` — Controls for two sources of variation simultaneously: rows = time periods, columns = asset classes, treatments = strategies. Each strategy tested once in each period and asset class. |

### 2.9 STA 346 — Statistical Quality Control (Grade: C, 51%)

| Concept | Alpha Stack Module | Agent | Code Component |
|---------|-------------------|-------|----------------|
| **Control Charts (X̄, R, S)** | Monitoring Engine → Strategy Monitor | Monitor Agent | `monitoring/control_charts.py` — X̄ chart for rolling average returns (detects alpha drift). R/S chart for rolling volatility (detects risk changes). Points outside control limits trigger alerts. Non-random patterns signal regime change. |
| **Attribute Control Charts (p, np, c)** | Monitoring Engine → Trade Quality | Monitor Agent | `monitoring/trade_quality.py` — p chart: proportion of losing trades (is win rate stable?). c chart: defects per trade (slippage, partial fills, rejections). Detects execution quality deterioration. |
| **Process Capability (Cp, Cpk)** | Monitoring Engine → Strategy Capability | Monitor Agent | `monitoring/capability.py` — Cp: does strategy variability fit within acceptable bounds? Cpk: is strategy centered on target? High Cp but low Cpk → needs recalibration. |
| **Western Electric Rules** | Monitoring Engine → Early Warning | Monitor Agent | `monitoring/western_electric.py` — (1) One bad day beyond 3σ → investigate. (2) Consecutive underperformance → model degrading. (3) Persistent bias → systematic issue. Detects problems early. |
| **Acceptance Sampling** | Deployment Engine → Staged Deployment | Orchestrator Agent | `deployment/acceptance.py` — Paper trade (first sample). If clearly good → deploy. If clearly bad → reject. If ambiguous → extend paper trading. Balances speed with safety. |
| **Six Sigma (DMAIC)** | Strategy Development Pipeline | All Agents | `pipeline/dmaic.py` — Define (hypothesis), Measure (baseline), Analyze (alpha sources), Improve (optimize), Control (monitor). Structured approach prevents ad-hoc deployment. |
| **Fishbone/Pareto Analysis** | Failure Analysis Engine | Reflection Agent | `analysis/root_cause.py` — When strategy fails: Man (human error?), Machine (latency?), Method (flawed logic?), Material (bad data?), Measurement (wrong metrics?), Environment (unusual conditions?). Pareto focuses on top 20% of failure causes. |

### 2.10 STA 347 — Statistical Computing (Grade: B, 65%)

| Concept | Alpha Stack Module | Agent | Code Component |
|---------|-------------------|-------|----------------|
| **Newton-Raphson** | Estimation Engine → MLE Solver | All estimation agents | `compute/newton_raphson.py` — MLE computation for GARCH, copula, option pricing models. Real-time parameter estimation. |
| **Numerical Integration** | Risk Engine → Option Pricer | Risk Manager | `compute/numerical_integration.py` — Option pricing under non-standard distributions. VaR computation by integrating return distribution. Gaussian quadrature for high accuracy. |
| **Optimization (Gradient Descent, EM)** | Portfolio Engine → Optimizer | Portfolio Optimizer | `compute/optimizer.py` — Mean-variance portfolio optimization. Strategy parameter optimization. EM algorithm for HMM estimation (regime detection) and mixture model fitting. |
| **Matrix Computations (Eigenvalues, SVD)** | Factor Engine → PCA/Factor Extractor | Factor Agent | `compute/matrix_ops.py` — PCA/SVD for factor extraction. Covariance matrix estimation and regularization. Eigenvalue analysis for market regime detection. |
| **Monte Carlo Integration** | Risk Engine → Scenario Generator | Risk Manager | `compute/monte_carlo.py` — Complex derivative pricing. VaR/CVaR for large portfolios. Expected returns under complex scenarios. Variance reduction: antithetic variates, control variates, importance sampling. |
| **MCMC** | Estimation Engine → Bayesian Sampler | Estimation Agent | `compute/mcmc.py` — Bayesian parameter estimation. Posterior sampling. Gibbs sampling for hierarchical models. Metropolis-Hastings for non-standard posteriors. Hamiltonian Monte Carlo for continuous posteriors. |
| **Bootstrap Methods** | Backtesting Engine → Robust Inference | Reflection Agent | `compute/bootstrap.py` — Confidence intervals for any performance metric. Hypothesis testing without distributional assumptions. Model validation. Block bootstrap for time series. |
| **EM Algorithm / GMM** | Regime Engine → Mixture Modeler | Regime Agent | `compute/em_gmm.py` — Market regime detection (bull/bear/high-vol/low-vol as mixture components). Asset clustering. Strategy return decomposition. |
| **Kernel Density Estimation** | Distribution Engine → Non-Parametric Density | Distribution Agent | `compute/kde.py` — Return distribution estimation without assuming normality. VaR/CVaR from empirical distributions. Detects fat tails, skewness, multimodality. |
| **R Programming** | Research Environment | All Agents | `tools/r_integration.py` — Rapid prototyping of statistical models. Exploratory data analysis. Publication-quality analysis. Package ecosystem (rugarch, copula). |
| **Python (NumPy, Pandas, Scikit-learn)** | Production Pipeline | All Agents | Core codebase — NumPy/Pandas for data processing. Scikit-learn for classical ML. PyTorch for deep learning. FastAPI for model serving. |

### 2.11 STA 442 — Applied Multivariate Analysis

| Concept | Alpha Stack Module | Agent | Code Component |
|---------|-------------------|-------|----------------|
| **Multivariate Normal Distribution** | Portfolio Engine → Joint Return Model | Portfolio Optimizer | `portfolio/multivariate_normal.py` — Mean vector = expected returns; Covariance matrix = variances/covariances. Foundation of Markowitz optimization and Black-Scholes. |
| **Mahalanobis Distance** | Risk Engine → Outlier Detector | Risk Manager | `risk/mahalanobis.py` — Detects multivariate outliers — unusual conditions that aren't univariate outliers (e.g., high correlation + high volatility + negative returns simultaneously). |
| **Hotelling's T²** | Backtesting Engine → Multivariate Tester | Reflection Agent | `backtest/hotelling.py` — Tests whether portfolio's mean return vector is significantly different from zero across multiple assets simultaneously. Controls for multiple testing. |
| **Wishart Distribution** | Portfolio Engine → Covariance Inference | Portfolio Optimizer | `portfolio/wishart.py` — Sampling distribution of estimated covariance matrix. Confidence intervals for correlations. Shrinkage estimators (Ledoit-Wolf) when assets > observations. |
| **PCA** | Factor Engine → Risk Factor Extractor | Factor Agent | `factor/pca.py` — First PC = "market" factor, second = "slope," third = "curvature." Parsimonious factors explain most variance. Dimensionality reduction for large asset universes. |
| **Factor Analysis** | Factor Engine → Latent Factor Modeler | Factor Agent | `factor/factor_analysis.py` — Identifies latent risk factors (risk appetite, liquidity, inflation expectations). Exploratory FA discovers structure; Confirmatory FA tests hypotheses. |
| **LDA/QDA** | Regime Engine → Regime Classifier | Regime Agent | `regime/lda_qda.py` — LDA: linear regime boundaries (bull/bear/sideways). QDA: when regimes have different covariance structures (bear markets = higher vol + different correlations). |
| **Logistic Regression** | Signal Engine → Event Probability | Signal Agent | `signal/logistic.py` — Probability of default, probability of rating change, probability of recession. Output is probability → directly informs position sizing. |
| **Hierarchical Clustering** | Portfolio Engine → Asset Clustering | Portfolio Optimizer | `portfolio/hierarchical_clustering.py` — Groups assets by return correlation. Creates hierarchical risk budgeting framework. Assets in same cluster provide less diversification. |
| **K-Means Clustering** | Regime Engine → Regime Clustering | Regime Agent | `regime/kmeans.py` — Identifies market regimes from multi-dimensional indicators. Each cluster = distinct regime with optimal strategy. |
| **Gaussian Mixture Models** | Regime Engine → Soft Regime Classifier | Regime Agent | `regime/gmm.py` — Soft classification: 60% bull, 40% sideways. Informs strategy blending rather than binary switching. BIC for model selection. |
| **KDE** | Distribution Engine → Non-Parametric Density | Distribution Agent | `distribution/kde.py` — Full return distribution without parametric assumptions. Captures fat tails, skewness, multimodality. Critical for VaR and option pricing. |
| **MDS / t-SNE** | Visualization Engine → Correlation Map | Dashboard Agent | `visualization/mds.py` — Visualizes correlation structure. Assets close together = highly correlated. Reveals clusters and outliers. |
| **Correspondence Analysis** | Analysis Engine → Categorical Structure | Analysis Agent | `analysis/correspondence.py` — Relationships between categorical market variables (country × sector, rating × industry, regime × strategy). |

### 2.12 STA 443 — Measure and Probability Theory

| Concept | Alpha Stack Module | Agent | Code Component |
|---------|-------------------|-------|----------------|
| **σ-Algebras & Measurable Spaces** | Risk Engine → Event Space Definition | Risk Manager | `risk/event_space.py` — Defines event space for all possible market outcomes. Determines which events can have probabilities assigned. Prevents paradoxes in risk assessment. |
| **Lebesgue Integration** | Risk Engine → Expected Value Calculator | Risk Manager | `risk/lebesgue_integration.py` — All expected return calculations, option pricing (risk-neutral expectations), risk metrics (VaR, CVaR) are Lebesgue integrals. Handles fat-tailed, discontinuous payoffs. |
| **Convergence Theorems** | Estimation Engine → Asymptotic Guarantees | Estimation Agent | `estimation/convergence.py` — Dominated Convergence Theorem justifies sample averages converging to population expectations. Foundation of all statistical inference in the system. |
| **Fubini's Theorem** | Portfolio Engine → Joint Distribution | Portfolio Optimizer | `portfolio/fubini.py` — Multi-asset joint distribution computation. Justifies computing marginal distributions from joint. Essential for portfolio construction. |
| **Probability Spaces & Kolmogorov Axioms** | Risk Engine → Foundational Framework | Risk Manager | `risk/kolmogorov.py` — Every probability assessment must satisfy axioms. Violations (probabilities not summing to 1) indicate model errors. |
| **Conditional Probability & Bayes** | Signal Engine → Bayesian Updater | All Signal Agents | `signal/bayes.py` — Updates signal confidence as new data arrives. Prior + Likelihood = Posterior. Continuous learning and adaptation. |
| **Independence & Conditional Independence** | Factor Engine → Factor Orthogonality | Factor Agent | `factor/independence.py` — Multi-factor model assumes factors are independent. Conditional independence: assets independent given market factor. Decomposes risk into independent components. |
| **MGF & Characteristic Functions** | Pricing Engine → Fourier Pricer | Pricing Agent | `pricing/fourier.py` — Carr-Madan, COS method for option pricing. Knowing the characteristic function allows pricing any option payoff via numerical integration. Faster than Monte Carlo. |
| **Convergence Concepts** | Estimation Engine → Convergence Guarantees | Estimation Agent | `estimation/convergence_types.py` — OLS consistent (converges in probability). CLT gives convergence in distribution to Normal. Justifies finite-sample inference. |
| **Random Walks & Brownian Motion** | Price Engine → Baseline Price Model | Pricing Agent | `pricing/brownian.py` — GBM as baseline for all price modeling. Foundation of Black-Scholes, portfolio theory, risk modeling. Deviations from GBM (jumps, stochastic vol) are extensions. |
| **Markov Chains & Transition Matrices** | Regime Engine → Regime Detector | Regime Agent | `regime/markov.py` — Market regimes as Markov chains. Transition matrix estimated from historical data. Drives strategy allocation. |
| **Martingales** | Signal Engine → EMH Tester | Signal Agent | `signal/martingale_test.py` — Tests whether prices follow martingale property. Deviations = exploitable inefficiencies. Alpha signals are departures from martingale behavior. |

### 2.13 STA 444 — Non-Parametric Methods

| Concept | Alpha Stack Module | Agent | Code Component |
|---------|-------------------|-------|----------------|
| **Histogram & Frequency Polygon** | Visualization Engine → Distribution Viewer | Dashboard Agent | `visualization/histogram.py` — Return distribution visualization. Detects fat tails, skewness, multimodality. Reveals features summary statistics miss. |
| **KDE** | Distribution Engine → Density Estimator | Distribution Agent | `distribution/kde.py` — Non-parametric return distribution. Cross-validated bandwidth selection. Captures fat tails, skewness, multimodality. |
| **Kernel Regression (Nadaraya-Watson)** | Signal Engine → Non-Linear Signal | Signal Agent | `signal/kernel_regression.py` — Non-linear relationships between factors and returns. No functional form assumed. Each prediction based on nearby observations. |
| **LOESS/LOWESS** | Signal Engine → Trend Extractor | Signal Agent | `signal/loess.py` — Extracts trends from noisy market data. Adaptive smoothing captures non-linear trends. Used for detrending before signal estimation. |
| **Spline Smoothing** | Signal Engine → Flexible Factor Response | Signal Agent | `signal/splines.py` — Non-linear factor response functions. Relationship between volatility and returns may be convex for low vol, concave for high vol. |
| **Sign Test & Wilcoxon** | Backtesting Engine → Robust Return Test | Reflection Agent | `backtest/wilcoxon.py` — Tests median returns without normality assumption. Robust to outliers. More reliable evidence of positive returns for fat-tailed distributions. |
| **Mann-Whitney U** | Backtesting Engine → Strategy Comparator | Reflection Agent | `backtest/mann_whitney.py` — Compares two strategies without assuming normality. More robust than t-test for fat-tailed returns. |
| **Kruskal-Wallis** | Backtesting Engine → Multi-Strategy Comparison | Reflection Agent | `backtest/kruskal_wallis.py` — Compares performance across multiple strategies, time periods, or market conditions without normality assumption. |
| **K-S & Anderson-Darling Tests** | Distribution Engine → Fit Tester | Distribution Agent | `distribution/ks_test.py` — Verifies return distributions match assumed models. Catches distributional misspecification that affects risk models. |
| **Bootstrap** | Backtesting Engine → Robust Inference | Reflection Agent | `compute/bootstrap.py` — Confidence intervals for any metric. Hypothesis testing without distributional assumptions. Block bootstrap for time series. |
| **Spearman's Rank Correlation** | Portfolio Engine → Robust Correlation | Portfolio Optimizer | `portfolio/spearman.py` — Monotonic (not just linear) association. Robust to outliers. Used alongside Pearson for portfolio construction. |
| **Kendall's Tau** | Signal Engine → Signal Agreement | Signal Aggregator | `signal/kendall.py` — Measures agreement between multiple signals. High tau → signals reinforce. Low tau → signals provide diversification. |
| **Quantile Regression** | Risk Engine → Conditional VaR | Risk Manager | `risk/quantile_regression.py` — Estimates conditional VaR (5th percentile of tomorrow's return given today's conditions). More flexible than parametric VaR. Adapts to changing market conditions. |

---

## 3. Data Flow: Statistics → Signal → Trade

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STATISTICAL DATA FLOW IN ALPHA STACK                      │
│                                                                              │
│  RAW DATA                    STATISTICAL PROCESSING           TRADING OUTPUT │
│  ────────                    ──────────────────────           ────────────── │
│                                                                              │
│  ┌──────────┐    ┌─────────────────────┐    ┌──────────────┐                │
│  │ Price    │───→│ STA 244: Stationarity│───→│ ARIMA Model  │──┐            │
│  │ Tick Data│    │ Test (ADF/KPSS)      │    │ Selection    │  │            │
│  └──────────┘    └─────────────────────┘    └──────────────┘  │            │
│                                                                │            │
│  ┌──────────┐    ┌─────────────────────┐    ┌──────────────┐  │  ┌────────┐│
│  │ Volume   │───→│ STA 142: Distribution│───→│ KDE / GARCH  │──┼─→│SIGNAL  ││
│  │ Data     │    │ Fitting (PDF/CDF)    │    │ Volatility   │  │  │CONFLU- ││
│  └──────────┘    └─────────────────────┘    └──────────────┘  │  │ENCE    ││
│                                                                │  │SCORE   ││
│  ┌──────────┐    ┌─────────────────────┐    ┌──────────────┐  │  │        ││
│  │ Macro    │───→│ STA 245: Index       │───→│ Inflation    │──┤  │= Σ     ││
│  │ Data     │    │ Numbers, CPI         │    │ Surprise     │  │  │wᵢ·sᵢ  ││
│  └──────────┘    └─────────────────────┘    └──────────────┘  │  │        ││
│                                                                │  └───┬────┘│
│  ┌──────────┐    ┌─────────────────────┐    ┌──────────────┐  │      │     │
│  │ Multi-   │───→│ STA 442: PCA /       │───→│ Factor       │──┤      │     │
│  │ Asset    │    │ Factor Analysis      │    │ Exposures    │  │      │     │
│  │ Returns  │    └─────────────────────┘    └──────────────┘  │      │     │
│                                              ┌──────────────┐  │      │     │
│  ┌──────────┐    ┌─────────────────────┐    │ STA 342:     │  │      │     │
│  │ Backtest │───→│ STA 341: MLE /       │───→│ Hypothesis   │──┘      │     │
│  │ Results  │    │ Bayesian Estimation  │    │ Test (p-val) │         │     │
│  └──────────┘    └─────────────────────┘    └──────────────┘         │     │
│                                                                       │     │
│                                              ┌──────────────┐         │     │
│  ┌──────────┐    ┌─────────────────────┐    │ STA 346:     │         │     │
│  │ Live     │───→│ STA 347: Bootstrap /  │───→│ Control      │─────────▼─────│
│  │ Trade    │    │ Monte Carlo          │    │ Charts       │    ┌──────────┐│
│  │ Results  │    └─────────────────────┘    └──────────────┘    │ EXECUTION││
│  └──────────┘                                                    │ ENGINE   ││
│                                                                   └──────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Agent-Skill Matrix

Each multi-agent system agent draws on specific statistics skills:

| Agent | Primary Stats Units | Key Skills | Latency Requirement |
|-------|-------------------|------------|-------------------|
| **Fundamental Agent** | STA 142, STA 245, STA 246 | Bayesian updating, index numbers, demographic signals | Slow (1-5s) |
| **Time Series Agent** | STA 244, STA 347 | ARIMA, stationarity tests, exponential smoothing | Medium (50-200ms) |
| **Volatility Agent** | STA 241, STA 244, STA 341 | GARCH, distribution fitting, MLE | Medium (50-200ms) |
| **Regime Agent** | STA 241, STA 341, STA 347, STA 442, STA 443 | HMM, Markov chains, GMM, EM algorithm | Fast (<10ms) |
| **Pairs Agent** | STA 244, STA 444 | Cointegration, non-parametric correlation | Medium (50-200ms) |
| **Factor Agent** | STA 341, STA 442, STA 443 | PCA, factor analysis, MLE, eigenvalue decomposition | Medium (50-200ms) |
| **Risk Manager** | STA 142, STA 241, STA 341, STA 442, STA 443, STA 444 | VaR, CVaR, copulas, Mahalanobis distance, quantile regression, KDE | Fast (<10ms) |
| **Portfolio Optimizer** | STA 142, STA 341, STA 442, STA 444 | Covariance matrices, multivariate normal, clustering, rank correlation | Medium (50-200ms) |
| **Signal Aggregator** | STA 142, STA 241, STA 342, STA 444 | Expected value, hypothesis testing, multiple testing corrections, Kendall's tau | Fast (<10ms) |
| **Reflection Agent** | STA 342, STA 343, STA 346, STA 347, STA 444 | Hypothesis testing, experimental design, control charts, bootstrap, non-parametric tests | Slow (post-trade) |
| **Execution Agent** | STA 241 | Poisson order arrival, fill probability | Ultra-fast (<5ms) |
| **Monitor Agent** | STA 346 | Control charts, capability analysis, Western Electric rules | Continuous |
| **Data Quality Agent** | STA 244, STA 341, STA 347 | Stationarity tests, sufficiency, data cleaning | Background |
| **Pricing Agent** | STA 443, STA 347 | Lebesgue integration, characteristic functions, Monte Carlo | Fast (<10ms) |
| **Dashboard Agent** | STA 442, STA 444 | Visualization, histograms, MDS, correspondence analysis | Background |

---

## 5. Implementation Priority

### Phase 1: Foundation (Months 1-3) — CRITICAL

| Unit | Module | Why First |
|------|--------|-----------|
| **STA 142** | Distribution Engine, Signal Engine | Probability is the language of risk. Bayesian updating is the core of adaptive intelligence. |
| **STA 241** | Distribution Engine, Risk Engine | Valentine's strongest unit (A). Fat-tailed distributions, copulas, and MGFs are essential for realistic risk modeling. |
| **STA 341** | Estimation Engine | MLE and Bayesian estimation are used everywhere — GARCH, HMM, copulas, option pricing. |
| **STA 347** | Compute Layer | Python/R tools needed to implement everything else. Newton-Raphson, Monte Carlo, bootstrap. |

### Phase 2: Core Trading (Months 4-6) — HIGH PRIORITY

| Unit | Module | Why |
|------|--------|-----|
| **STA 244** | Time Series Engine | Valentine's weakest unit (D) but THE most directly relevant. ARIMA, GARCH, cointegration — the core forecasting toolkit. Must be prioritized for self-study. |
| **STA 342** | Hypothesis Testing Engine | Strategy validation, backtesting rigor. Multiple testing corrections prevent data mining. |
| **STA 443** | Measure Theory Foundation | Probability spaces, martingales, convergence theorems — the rigorous foundation for all probability-based components. |

### Phase 3: Advanced Analytics (Months 7-9) — MEDIUM PRIORITY

| Unit | Module | Why |
|------|--------|-----|
| **STA 442** | Multivariate Engine | PCA for factor extraction, clustering for regime detection, multivariate normal for portfolio optimization. |
| **STA 343** | Experimental Design | Factorial designs for multi-factor testing, RSM for parameter optimization, blocking for regime-fair evaluation. |
| **STA 346** | Quality Control Engine | Control charts for strategy monitoring, DMAIC for development process, acceptance sampling for deployment. |

### Phase 4: Specialization (Months 10-12) — LOWER PRIORITY

| Unit | Module | Why |
|------|--------|-----|
| **STA 444** | Non-Parametric Engine | Robust alternatives when parametric assumptions fail. KDE, quantile regression, rank-based methods. |
| **STA 245** | Macro Statistics | Index numbers, CPI analysis, BOP tracking — important for macro-driven signals but lower urgency than core statistical methods. |
| **STA 246** | Demographic Signals | Long-term demographic trends — useful for strategic allocation but not for active trading signals. |

---

## 6. Code Module Dependency Graph

```
┌─────────────────────────────────────────────────────────────────┐
│                    CODE MODULE DEPENDENCIES                       │
│                                                                   │
│  data/                                                            │
│  ├── stationarity_tests.py  (STA 244) ──→ signal/arima_model.py  │
│  ├── quality_checks.py      (STA 245) ──→ all signal modules     │
│  └── sufficient_stats.py    (STA 341) ──→ estimation/*           │
│                                                                   │
│  distribution/                                                    │
│  ├── return_distribution.py (STA 142, 241) ──→ risk/var_*.py     │
│  ├── fat_tail.py            (STA 241) ──→ risk/garch.py          │
│  ├── copulas.py             (STA 241) ──→ portfolio/covariance.py│
│  ├── kde.py                 (STA 347, 444) ──→ risk/var_*.py     │
│  └── ks_test.py             (STA 444) ──→ backtest/*             │
│                                                                   │
│  estimation/                                                      │
│  ├── mle.py                 (STA 341) ──→ risk/garch.py          │
│  ├── bayesian.py            (STA 142, 341) ──→ signal/bayes.py   │
│  ├── mom.py                 (STA 341) ──→ signal/arma_model.py   │
│  ├── fisher_info.py         (STA 341) ──→ compute/optimizer.py   │
│  └── convergence.py         (STA 443) ──→ backtest/*             │
│                                                                   │
│  signal/                                                          │
│  ├── bayesian_updater.py    (STA 142) ──→ signal/confluence.py   │
│  ├── arima_model.py         (STA 244) ──→ signal/confluence.py   │
│  ├── garch.py               (STA 244) ──→ risk/position_sizing.py│
│  ├── cointegration.py       (STA 244) ──→ pairs/trading.py       │
│  ├── var_model.py           (STA 244) ──→ macro/shock_model.py   │
│  ├── pvalue_scorer.py       (STA 342) ──→ signal/confluence.py   │
│  ├── multiple_testing.py    (STA 342) ──→ signal/confluence.py   │
│  ├── kernel_regression.py   (STA 444) ──→ signal/confluence.py   │
│  ├── loess.py               (STA 444) ──→ signal/arima_model.py  │
│  └── logistic.py            (STA 442) ──→ signal/confluence.py   │
│                                                                   │
│  risk/                                                            │
│  ├── var_calculator.py      (STA 241, 443) ──→ risk/position_*   │
│  ├── garch.py               (STA 244, 341) ──→ risk/position_*   │
│  ├── copulas.py             (STA 241) ──→ portfolio/covariance.py│
│  ├── confidence_intervals.py(STA 341) ──→ backtest/reporting.py  │
│  ├── mahalanobis.py         (STA 442) ──→ risk/outlier_alert.py  │
│  ├── quantile_regression.py (STA 444) ──→ risk/var_calculator.py │
│  └── lebesgue_integration.py(STA 443) ──→ pricing/fourier.py     │
│                                                                   │
│  portfolio/                                                       │
│  ├── covariance.py          (STA 142, 442) ──→ portfolio/optim.* │
│  ├── multivariate_normal.py (STA 442) ──→ portfolio/optimizer.py │
│  ├── hierarchical_clustering.py (STA 442) ──→ portfolio/risk_budget│
│  ├── spearman.py            (STA 444) ──→ portfolio/covariance.py│
│  └── diversification.py     (STA 142) ──→ portfolio/optimizer.py │
│                                                                   │
│  backtest/                                                        │
│  ├── hypothesis_test.py     (STA 342) ──→ deployment/gate.py     │
│  ├── bootstrap_test.py      (STA 347, 444) ──→ deployment/gate.py│
│  ├── ttest.py               (STA 342) ──→ backtest/reporting.py  │
│  ├── nonparametric.py       (STA 444) ──→ backtest/reporting.py  │
│  ├── hotelling.py           (STA 442) ──→ backtest/reporting.py  │
│  ├── blocking.py            (STA 343) ──→ backtest/test_design.py│
│  └── convergence.py         (STA 443) ──→ deployment/gate.py     │
│                                                                   │
│  monitoring/                                                      │
│  ├── control_charts.py      (STA 346) ──→ monitoring/alerts.py   │
│  ├── trade_quality.py       (STA 346) ──→ monitoring/alerts.py   │
│  ├── capability.py          (STA 346) ──→ monitoring/reports.py   │
│  └── western_electric.py    (STA 346) ──→ monitoring/alerts.py   │
│                                                                   │
│  compute/                                                         │
│  ├── newton_raphson.py      (STA 347) ──→ estimation/mle.py      │
│  ├── monte_carlo.py         (STA 347) ──→ risk/var_calculator.py │
│  ├── mcmc.py                (STA 347) ──→ estimation/bayesian.py │
│  ├── bootstrap.py           (STA 347, 444) ──→ backtest/*        │
│  ├── optimizer.py           (STA 347) ──→ portfolio/optimizer.py │
│  ├── em_gmm.py              (STA 347) ──→ regime/markov.py       │
│  └── matrix_ops.py          (STA 347) ──→ factor/pca.py          │
│                                                                   │
│  regime/                                                          │
│  ├── markov.py              (STA 443) ──→ regime/hmm.py          │
│  ├── hmm.py                 (STA 241, 341) ──→ orchestrator/route│
│  ├── lda_qda.py             (STA 442) ──→ regime/classifier.py   │
│  ├── kmeans.py              (STA 442) ──→ regime/classifier.py   │
│  └── gmm.py                 (STA 347, 442) ──→ regime/classifier │
│                                                                   │
│  factor/                                                          │
│  ├── pca.py                 (STA 442, 347) ──→ portfolio/optim.py│
│  ├── factor_analysis.py     (STA 442) ──→ signal/factor_model.py │
│  └── independence.py        (STA 443) ──→ signal/confluence.py   │
│                                                                   │
│  pricing/                                                         │
│  ├── brownian.py            (STA 443) ──→ pricing/options.py     │
│  └── fourier.py             (STA 443, 347) ──→ pricing/options.py│
│                                                                   │
│  pairs/                                                           │
│  └── cointegration.py       (STA 244) ──→ pairs/trading.py       │
│                                                                   │
│  optimization/                                                    │
│  └── rsm.py                 (STA 343) ──→ signal/param_optim.py  │
│                                                                   │
│  deployment/                                                      │
│  └── acceptance.py          (STA 346) ──→ deployment/gate.py     │
│                                                                   │
│  visualization/                                                   │
│  ├── histogram.py           (STA 444) ──→ dashboard/main.py      │
│  └── mds.py                 (STA 442) ──→ dashboard/correlation.py│
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. Valentine's Grade-to-Wiring Gap Analysis

| Unit | Grade | Wiring Completeness | Gap to Fill |
|------|-------|-------------------|-------------|
| **STA 142** | C (54%) | 🟡 Partial — Bayesian updating needs deepening | Probability axioms → risk engine; conditional probability → signal engine |
| **STA 241** | A (77%) | 🟢 Strong — best foundation | Extend to copulas, multivariate distributions for advanced risk modeling |
| **STA 244** | D (45%) | 🔴 Critical gap — most directly relevant unit | ARIMA, GARCH, cointegration must be self-studied urgently |
| **STA 245** | C (51%) | 🟡 Partial — index numbers and CPI analysis | Macro statistics for inflation signals and BOP tracking |
| **STA 246** | B (66%) | 🟢 Adequate — demographic signals | Long-term demographic trends for strategic allocation |
| **STA 341** | B (66%) | 🟢 Strong — estimation theory solid | MLE and Bayesian estimation are directly applicable |
| **STA 342** | D (41%) | 🔴 Critical gap — strategy validation core | Hypothesis testing, multiple testing corrections must be strengthened |
| **STA 343** | C (58%) | 🟡 Partial — experimental design | Factorial designs and RSM for strategy optimization |
| **STA 346** | C (51%) | 🟡 Partial — quality control | Control charts and DMAIC for operational excellence |
| **STA 347** | B (65%) | 🟢 Strong — computational tools | Python/R skills are directly transferable |
| **STA 442** | — | 🟡 Unknown — multivariate analysis | PCA, clustering, discriminant analysis for portfolio construction |
| **STA 443** | — | 🟡 Unknown — measure theory | Probability spaces, martingales, convergence theorems |
| **STA 444** | — | 🟡 Unknown — non-parametric methods | KDE, quantile regression, rank-based methods for robust inference |

---

## 8. Wiring Summary by Alpha Stack Layer

### Signal Layer (Steps 1-9)
- **STA 142**: Bayesian signal updating, conditional probability, expected value
- **STA 241**: Beta distribution for win rate, Poisson for signal frequency
- **STA 244**: ARIMA forecasting, cointegration for pairs, VAR for multi-asset
- **STA 245**: CPI surprise trading, inflation index analysis
- **STA 341**: MLE for model parameters, Bayesian estimation for adaptive signals
- **STA 443**: Martingale testing (EMH departures), random walk baseline
- **STA 444**: Kernel regression, LOESS trend extraction, spline factor responses

### Risk Layer (Steps 12-15)
- **STA 142**: Return distributions, VaR from CDF, Monte Carlo simulation
- **STA 241**: Fat-tailed distributions, copulas, MGF characterization
- **STA 244**: GARCH volatility forecasting, dynamic position sizing
- **STA 341**: Confidence intervals for risk metrics, Fisher information for learning rates
- **STA 442**: Mahalanobis distance for outlier detection, Hotelling's T² for portfolio testing
- **STA 443**: Lebesgue integration for VaR/CVaR, probability space foundations
- **STA 444**: Quantile regression for conditional VaR, KDE for empirical distributions

### Portfolio Layer
- **STA 142**: Covariance matrices, correlation modeling, diversification logic
- **STA 241**: Joint distributions, copulas for dependence
- **STA 341**: MLE for covariance estimation, shrinkage estimators
- **STA 442**: PCA for factor extraction, clustering for asset grouping, multivariate normal
- **STA 444**: Spearman/Kendall for robust correlation, hierarchical clustering

### Monitoring Layer
- **STA 342**: Hypothesis tests for strategy significance, multiple testing corrections
- **STA 343**: Experimental design for fair strategy evaluation
- **STA 346**: Control charts, capability analysis, Western Electric rules, DMAIC
- **STA 347**: Bootstrap for robust confidence intervals, Monte Carlo for stress testing

---

*Document generated: 2026-07-11*  
*Statistics units mapped: 13*  
*Alpha Stack modules referenced: 40+*  
*Code components specified: 80+*  
*Agent-skill mappings: 15 agents × 13 units*
