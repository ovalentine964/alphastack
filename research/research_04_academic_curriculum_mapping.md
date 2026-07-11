# Academic Curriculum Mapping — AI Forex/Crypto Trading System

*Generated: 2026-07-11*

---

## PART A — Completed Units Mapped to the Trading System

### 1. BCB 108 — Business Communication Skills (53%, C)

**Key Concepts:**
- Professional writing (reports, proposals, memos)
- Presentation skills and data storytelling
- Business correspondence and stakeholder communication
- Persuasive argumentation and logical structuring

**Application to Trading System:**
- **Strategy documentation:** Writing clear, structured trading strategy documents that explain logic, assumptions, and risk parameters to stakeholders or future collaborators
- **Backtest reporting:** Presenting backtest results in a way that's honest about drawdowns, overfitting risks, and limitations — not just cherry-picked equity curves
- **Investor communication:** If seeking funding, communicating strategy performance, risk metrics, and methodology in professional reports
- **Error logging & debugging narratives:** Maintaining clear logs of system failures, lessons learned, and post-mortems after losing trades

**Practical Example:** *"Writing a structured report explaining why a momentum strategy failed during a black swan event, with clear sections on what happened, why the model didn't anticipate it, and what changes were made."*

---

### 2. ECO 100 — Development Concepts and Application (56%, C)

**Key Concepts:**
- Economic development theories (Rostow, dependency theory)
- Institutional economics and governance
- Globalization and trade policy
- Poverty, inequality, and economic growth models

**Application to Trading System:**
- **Macro regime identification:** Understanding which phase of economic development a country is in helps predict currency strength — emerging market currencies behave differently from developed market currencies
- **Institutional quality as a signal:** Countries with weak institutions, corruption, or political instability tend to have more volatile currencies — this can be a filter in your system
- **Globalization flows:** Trade imbalances, capital flows, and FDI patterns directly affect exchange rates over medium-to-long timeframes
- **Development indicators as features:** GDP growth rates, HDI scores, and institutional quality indices can serve as fundamental features for a longer-horizon trading model

**Practical Example:** *"Using a country's GDP growth differential and institutional quality score as features in a carry trade model — currencies of high-growth, stable-institution countries tend to appreciate against low-growth, weak-institution currencies."*

---

### 3. ECO 101 — Introduction to Microeconomics (66%, B)

**Key Concepts:**
- Supply and demand analysis
- Price elasticity and market equilibrium
- Consumer and producer theory
- Market structures (perfect competition, monopoly, oligopoly)
- Game theory basics (Nash equilibrium)

**Application to Trading System:**
- **Order book dynamics:** The microeconomic supply-demand framework IS the limit order book — understanding how equilibrium prices form maps directly to understanding bid-ask spreads and price discovery
- **Liquidity and elasticity:** Highly liquid currency pairs (EUR/USD) have low price elasticity of large orders; exotic pairs move more per unit of order flow — this affects position sizing
- **Market microstructure:** Understanding that forex markets are OTC (decentralized, dealer-based) vs. crypto markets (exchange-based, order book) affects how your system interacts with each
- **Game theory for strategy:** Other traders are rational agents — understanding Nash equilibria helps in designing strategies that don't get arbitraged away when many participants use them

**Practical Example:** *"Modeling the EUR/USD order book as a supply-demand equilibrium — when large institutional orders shift the demand curve, price moves. Your system can detect this via volume spikes and order flow imbalance indicators."*

---

### 4. ECO 102 — Introduction to Macroeconomics (61%, B)

**Key Concepts:**
- GDP, inflation, unemployment, and their relationships
- Monetary and fiscal policy
- Interest rate theory and the IS-LM model
- Exchange rate determination (purchasing power parity, interest rate parity)
- Business cycles

**Application to Trading System:**
- **Interest rate differentials:** The single most important driver of forex markets — carry trades exploit interest rate differentials between countries. Your system should track central bank policy expectations
- **Inflation data as signals:** CPI releases are among the highest-impact forex events. A model can incorporate inflation surprise (actual vs. forecast) as a feature
- **Purchasing Power Parity (PPP):** Long-term mean reversion anchor for currency pairs — currencies that deviate far from PPP may revert over months/years
- **Business cycle positioning:** Currencies behave differently at different cycle phases — early recovery (risk-on, commodity currencies up), late cycle (safe havens up)
- **Fiscal policy impact:** Government spending and debt levels affect sovereign risk premiums and currency valuations

**Practical Example:** *"Building a feature that tracks the US-UK interest rate differential (Fed Funds vs. Bank Rate) and combines it with inflation differential to predict GBP/USD directional bias over 1-3 month horizons."*

---

### 5. ECO 103 — Introduction to Mathematics for Economists (70%, A)

**Key Concepts:**
- Linear algebra basics (matrices, vectors)
- Systems of linear equations
- Set theory and logic
- Basic optimization (constrained and unconstrained)

**Application to Trading System:**
- **Portfolio representation:** Multiple currency positions are vectors in a multi-dimensional asset space — linear algebra is the language of portfolio math
- **Covariance matrices:** Calculating the covariance matrix of returns for multiple pairs requires matrix operations — this is foundational for portfolio risk management
- **Signal combination:** Combining multiple technical indicators into a single composite signal is a linear combination (weighted sum) — optimizing those weights is a linear algebra problem
- **Constrained optimization:** Position sizing under constraints (max exposure, max drawdown) is an optimization problem — the Lagrangian methods from this course apply directly

**Practical Example:** *"Using matrix multiplication to calculate the portfolio variance of a basket of 5 currency positions, where the covariance matrix is estimated from 252 days of returns — this tells you your portfolio's expected risk."*

---

### 6. ECO 104 — Mathematics for Economists (65%, B)

**Key Concepts:**
- Multivariable calculus
- Comparative statics
- Dynamic optimization (Euler equations)
- Difference and differential equations

**Application to Trading System:**
- **Partial derivatives for sensitivity analysis:** How much does your strategy P&L change when volatility changes by 1%? When correlation changes? Partial derivatives answer this
- **Dynamic programming:** Optimal position sizing over time can be framed as a dynamic programming problem — each period's decision depends on current state
- **Differential equations for price modeling:** Many quantitative models (Black-Scholes, Ornstein-Uhlenbeck for mean reversion) are differential equations
- **Comparative statics for scenario analysis:** "If the ECB raises rates by 25bp, what happens to EUR/USD?" — this is comparative statics applied to trading

**Practical Example:** *"Using partial derivatives to compute Greeks (delta, gamma, vega) for an options overlay on your forex positions — delta tells you how much your P&L changes per pip move in the underlying pair."*

---

### 7. ECO 106 — Emerging Public Health Issues (65%, B)

**Key Concepts:**
- Epidemiology and disease modeling (SIR models)
- Health economics and resource allocation
- Global health policy and institutional response
- Socioeconomic determinants of health

**Application to Trading System:**
- **Black swan event modeling:** Pandemics are the archetypal black swan — understanding how they unfold helps model tail risk in your system
- **Event-driven trading:** Health crises cause massive currency moves (COVID-19 caused USD to strengthen as a safe haven, then weaken on stimulus). Understanding the epidemiological timeline helps anticipate market phases
- **Cross-asset contagion:** Disease outbreaks affect commodities (oil demand collapse), equities, and currencies simultaneously — understanding the transmission mechanism helps build multi-asset models
- **SIR models as analogies:** The SIR (Susceptible-Infected-Recovered) compartmental model structure is analogous to market regime models (normal-volatile-recovered)

**Practical Example:** *"During COVID-19, building an event-detection system that monitors WHO alerts and epidemiological data, then triggers risk-off positioning (reduce exposure, increase hedging) before market consensus catches up."*

---

### 8. BIT 113 — Fundamentals of Information Technology (71%, A)

**Key Concepts:**
- Computer hardware and software fundamentals
- Networking and data communication
- Database concepts
- Programming basics and algorithms
- Information systems and security

**Application to Trading System:**
- **Networking for API connections:** Understanding TCP/IP, latency, and data transmission is critical when connecting to broker APIs and exchange WebSocket feeds
- **Database design:** Storing tick data, trade logs, and historical prices requires database knowledge — relational (PostgreSQL) for structured data, time-series databases (InfluxDB) for market data
- **Security fundamentals:** Protecting API keys, encrypting credentials, and securing your trading server against unauthorized access
- **System architecture:** Understanding client-server architecture helps design the trading system (data feed → strategy engine → execution engine → risk management)

**Practical Example:** *"Designing a trading system architecture where market data arrives via WebSocket → gets stored in a time-series database → triggers strategy calculations → sends orders via REST API to the broker — all running on a secure VPS."*

---

### 9. MAT 101 — Foundation Mathematics (50%, D)

**Key Concepts:**
- Algebra fundamentals (polynomials, factorization)
- Trigonometry basics
- Coordinate geometry
- Sequences and series

**Application to Trading System:**
- **Polynomial regression for trend fitting:** Fitting polynomial curves to price data to identify trend direction and curvature (acceleration/deceleration)
- **Sequences for Fibonacci analysis:** Fibonacci retracement and extension levels are derived from the Fibonacci sequence — understanding the math behind it
- **Coordinate geometry for charting:** Price charts are Cartesian coordinate systems — understanding slope, intercepts, and curve shapes translates directly to technical analysis interpretation
- **Series convergence for moving averages:** Exponential moving averages are geometric series — understanding convergence helps tune decay parameters

**Practical Example:** *"Using the Fibonacci sequence to generate retracement levels (23.6%, 38.2%, 50%, 61.8%, 78.6%) for support/resistance detection in your automated chart pattern recognition module."*

---

### 10. MAT 121 — Differential Calculus (66%, B)

**Key Concepts:**
- Limits and continuity
- Derivatives and differentiation rules
- Chain rule, product rule, quotient rule
- Applications: rate of change, optimization, related rates

**Application to Trading System:**
- **Rate of change = Momentum:** The first derivative of price with respect to time IS momentum — `dP/dt`. This is literally what momentum indicators (ROC, RSI) attempt to measure
- **Acceleration = Second derivative:** The second derivative `d²P/dt²` tells you if momentum is increasing or decreasing — divergence between price and momentum is a powerful signal
- **Optimization of parameters:** Finding the optimal lookback period, threshold, or position size requires taking the derivative of a performance metric and setting it to zero
- **Taylor series approximation:** Used in options pricing (expanding the price function around a point) and in approximating non-linear strategy payoffs
- **Gradient descent:** The foundation of all machine learning optimization — `∂Loss/∂weight` is computed via differentiation

**Practical Example:** *"Computing `dP/dt` on 15-minute EUR/USD candles to generate a momentum signal. When momentum is positive AND accelerating (d²P/dt² > 0), enter long. When momentum is positive but decelerating (d²P/dt² < 0), tighten stops."*

---

### 11. MAT 124 — Integral Calculus (56%, C)

**Key Concepts:**
- Definite and indefinite integrals
- Integration techniques (substitution, parts, partial fractions)
- Applications: area under curves, volumes
- Fundamental theorem of calculus

**Application to Trading System:**
- **Area under the curve for cumulative volume:** Integrating volume over time gives cumulative volume — used in VWAP (Volume Weighted Average Price) calculations
- **Expected value calculations:** Computing the expected return of a strategy requires integrating the return distribution's PDF — `E[R] = ∫ R·f(R)dR`
- **Probability from distributions:** Calculating the probability of a trade hitting a take-profit level requires integrating the price distribution from entry to TP
- **Signal smoothing:** Integration acts as a low-pass filter — integrating noisy signals produces smoother output, useful for reducing false signals

**Practical Example:** *"Integrating the normal distribution to calculate the probability that EUR/USD moves 50+ pips in the next hour given current volatility — if probability > 60%, your system places a breakout trade."*

---

### 12. STA 142 — Probability Theory (54%, C)

**Key Concepts:**
- Probability axioms and rules (conditional, Bayes' theorem)
- Random variables (discrete and continuous)
- Probability distributions (normal, binomial, Poisson, exponential)
- Expected value, variance, standard deviation
- Law of large numbers, central limit theorem

**Application to Trading System:**
- **Bayesian updating:** As new market data arrives, update the probability of your hypothesis (e.g., "trend is bullish") using Bayes' theorem — this is the foundation of adaptive trading systems
- **Return distributions:** Financial returns are NOT normally distributed (fat tails) — understanding normal distribution helps you model the baseline, then adjust for kurtosis
- **Expected value for trade decisions:** Every trade has a probability-weighted expected value: `EV = P(win) × avg_win - P(loss) × avg_loss`. Only take trades with positive EV
- **Monte Carlo simulation:** Simulating thousands of possible price paths using random sampling from historical return distributions to stress-test strategies
- **Law of large numbers:** Your edge only materializes over many trades — understanding this prevents quitting a good strategy after a losing streak

**Practical Example:** *"Running 10,000 Monte Carlo simulations of your strategy's equity curve using historical return distributions to estimate the 5th percentile drawdown — this gives you your Value at Risk (VaR) and helps set position sizes that survive worst-case scenarios."*

---

## PART B — Additional Courses That Would Help

### 1. Time Series Analysis

**Typical Code:** STA 3XX / ECO 3XX / STA 441

**Topics:**
- Stationarity and differencing (ADF test)
- Autocorrelation (ACF) and Partial Autocorrelation (PACF)
- AR, MA, ARMA, ARIMA models
- GARCH models for volatility clustering
- Seasonal decomposition (STL, X-13)
- Vector Autoregression (VAR)
- Cointegration and error correction models
- Spectral analysis (Fourier transforms)

**Application to Trading System:**
- **ARIMA for price forecasting:** Model price changes as autoregressive processes — past returns contain information about future returns at certain lags
- **GARCH for volatility prediction:** Volatility clusters (high vol follows high vol) — GARCH models this explicitly, enabling dynamic position sizing (smaller positions in high-vol regimes)
- **Cointegration for pairs trading:** Two cointegrated assets maintain a spread that mean-reverts — detect this statistically and trade the spread
- **Spectral analysis:** Decompose price series into frequency components to identify dominant cycles (e.g., weekly, monthly patterns)

---

### 2. Econometrics

**Typical Code:** ECO 201 / ECO 301 / ECO 401

**Topics:**
- Simple and multiple linear regression
- OLS assumptions and violations (heteroscedasticity, autocorrelation, multicollinearity)
- Instrumental variables and 2SLS
- Panel data methods
- Logit/probit models (discrete choice)
- Maximum likelihood estimation
- Hypothesis testing and confidence intervals
- Model specification and diagnostic testing

**Application to Trading System:**
- **Regression-based signals:** Regress currency returns on macro variables (interest rate differentials, inflation, trade balance) to generate fundamental-based predictions
- **Feature importance:** Use regression coefficients to determine which macro factors actually move markets, and drop irrelevant features
- **Heteroscedasticity-robust standard errors:** Financial data is heteroscedastic — using robust standard errors prevents false confidence in model parameters
- **Logit for binary outcomes:** Model "will this trade be profitable? (yes/no)" as a logistic regression using entry-time features
- **Maximum likelihood for distribution fitting:** Fit custom return distributions (Student-t, skewed normal) using MLE for better risk modeling

---

### 3. Financial Mathematics

**Typical Code:** MAT 3XX / MTH 401 / FIN 301

**Topics:**
- Time value of money and compounding
- Bond pricing and yield curves
- Options pricing (Black-Scholes, binomial models)
- Greeks (delta, gamma, theta, vega)
- Stochastic calculus basics (Itô's lemma)
- Risk-neutral pricing
- Forward and futures pricing

**Application to Trading System:**
- **Options as hedging tools:** Use options to hedge forex exposure — buying EUR/USD puts to protect long positions
- **Black-Scholes for implied volatility:** Implied volatility from options prices tells you the market's expectation of future vol — this is a feature for your model
- **Itô's lemma for stochastic modeling:** Price processes are stochastic — Itô's lemma is the chain rule for stochastic calculus, essential for deriving any pricing formula
- **Carry calculation:** Understanding the time value of money and interest rate differentials is fundamental to carry trade strategies
- **Yield curve analysis:** The shape of the yield curve (normal, inverted, flat) signals economic conditions and affects currency strength

---

### 4. Machine Learning

**Typical Code:** CS 229 / CSC 401 / CS 4XX

**Topics:**
- Supervised learning (linear/logistic regression, SVM, decision trees, random forests, gradient boosting)
- Unsupervised learning (k-means, PCA, DBSCAN)
- Neural networks and deep learning (CNN, RNN, LSTM, Transformer)
- Bias-variance tradeoff
- Cross-validation and hyperparameter tuning
- Ensemble methods
- Reinforcement learning fundamentals

**Application to Trading System:**
- **LSTM for sequence prediction:** LSTMs can learn temporal patterns in price data — train on sequences of OHLCV data to predict next-period returns
- **Random Forests for feature selection:** Use random forest feature importance to identify which technical indicators actually predict returns
- **Gradient Boosting (XGBoost/LightGBM):** State-of-the-art for tabular data — combine hundreds of technical and fundamental features into a single prediction model
- **Reinforcement learning for execution:** Train an RL agent to optimize order execution (minimize slippage) or to learn optimal position sizing
- **PCA for dimensionality reduction:** Reduce 50+ correlated technical indicators to 5-10 orthogonal components, preventing overfitting
- **Ensemble methods:** Combine multiple models (technical, fundamental, sentiment) into a meta-model for more robust predictions

---

### 5. Data Structures and Algorithms

**Typical Code:** CS 201 / CSC 201 / CS 102

**Topics:**
- Arrays, linked lists, stacks, queues
- Hash tables and trees (BST, AVL, B-trees)
- Graph algorithms (BFS, DFS, shortest path)
- Sorting and searching algorithms
- Algorithm complexity (Big-O notation)
- Recursion and dynamic programming

**Application to Trading System:**
- **Hash tables for order book:** O(1) lookup for price levels in the order book — critical for high-frequency strategies
- **Trees for hierarchical data:** Decision trees for trade signals, or B-trees for indexing time-series data in a database
- **Graph algorithms for correlation networks:** Model currency pairs as a graph where edges are correlations — find clusters of correlated pairs for diversification
- **Dynamic programming for optimal execution:** Break a large order into smaller pieces optimally using DP (similar to the Almgren-Chriss model)
- **Big-O for performance:** Your trading system must process ticks in microseconds — choosing the right data structure (hash table vs. binary search) matters enormously

---

### 6. Database Systems

**Typical Code:** CS 340 / CSC 305 / CS 4XX

**Topics:**
- Relational database design (normalization, ER diagrams)
- SQL (queries, joins, aggregations, window functions)
- Indexing and query optimization
- Transaction management (ACID properties)
- NoSQL databases (document, key-value, column-family, graph)
- Time-series databases
- Data warehousing concepts

**Application to Trading System:**
- **Tick data storage:** Millions of price ticks per day require efficient storage — time-series databases (InfluxDB, TimescaleDB) are purpose-built for this
- **SQL for backtesting queries:** "Give me all candles where RSI < 30 AND MACD crossed up AND volume > 2× average" — this is a SQL query on your historical data
- **Window functions for rolling calculations:** SQL window functions can compute rolling averages, ranks, and cumulative sums directly in the database — faster than pulling data to Python
- **ACID for trade logging:** Trade records must be atomic and consistent — a partial fill that gets recorded incorrectly corrupts your P&L calculations
- **Indexing for speed:** Proper indexing on (symbol, timestamp) makes your backtesting queries 100× faster

---

### 7. Stochastic Processes

**Typical Code:** STA 4XX / MAT 4XX / STA 303

**Topics:**
- Markov chains and transition matrices
- Random walks
- Brownian motion and Wiener processes
- Poisson processes
- Martingales
- Ornstein-Uhlenbeck process (mean-reverting)
- Itô calculus

**Application to Trading System:**
- **Random walk hypothesis:** The null hypothesis in finance is that prices follow a random walk — your strategy must prove it can beat this baseline
- **Ornstein-Uhlenbeck for mean reversion:** Model mean-reverting spreads (pairs trades) using OU process: `dX = θ(μ - X)dt + σdW`. Estimate θ (speed of reversion), μ (mean), σ (volatility) from data
- **Brownian motion for price simulation:** Generate realistic synthetic price data for Monte Carlo testing using geometric Brownian motion
- **Markov chains for regime detection:** Model market regimes (bull/bear/sideways) as a Markov chain — estimate transition probabilities from historical data
- **Poisson processes for event modeling:** Model the arrival of large price jumps (news events, flash crashes) as a Poisson process with intensity λ

---

### 8. Numerical Methods

**Typical Code:** MAT 3XX / CSC 3XX / MAT 301

**Topics:**
- Root-finding methods (Newton-Raphson, bisection)
- Numerical integration (Simpson's rule, Gaussian quadrature)
- Numerical differentiation
- Iterative methods for linear systems
- Interpolation and curve fitting
- Finite difference methods
- Error analysis and convergence

**Application to Trading System:**
- **Newton-Raphson for implied volatility:** Given an options price, solve for implied volatility iteratively — this is a root-finding problem
- **Numerical integration for expected values:** When analytical solutions don't exist, numerically integrate return distributions to compute expected shortfall, VaR, etc.
- **Curve fitting for yield curves:** Fit smooth curves to discrete yield data points using spline interpolation
- **Finite differences for PDEs:** The Black-Scholes PDE can be solved numerically using finite difference methods for exotic options pricing
- **Optimization without gradients:** Nelder-Mead and other derivative-free methods for optimizing strategy parameters when the objective function is noisy

---

### 9. Optimization Theory

**Typical Code:** MAT 4XX / OR 3XX / MAT 350

**Topics:**
- Linear programming (Simplex method)
- Quadratic programming
- Convex optimization
- Lagrangian duality
- Integer programming
- Nonlinear optimization
- Multi-objective optimization

**Application to Trading System:**
- **Mean-variance portfolio optimization:** Markowitz's framework is a quadratic programming problem — minimize portfolio variance for a target return
- **Linear programming for position sizing:** Maximize expected return subject to linear constraints (max exposure per pair, max total exposure, min diversification)
- **Convex optimization for robust portfolios:** Robust optimization accounts for estimation uncertainty in expected returns — produces portfolios that perform well across scenarios
- **Multi-objective optimization:** Balance return vs. risk vs. drawdown vs. trade frequency — Pareto-optimal solutions give you the efficient frontier of strategies
- **Integer programming for discrete decisions:** "How many contracts to trade?" is an integer problem — rounding LP solutions can be suboptimal

---

### 10. Financial Markets and Instruments

**Typical Code:** FIN 201 / FIN 301 / ECO 3XX

**Topics:**
- Market microstructure (order types, market makers, bid-ask spread)
- Forex markets (spot, forward, swaps, options)
- Fixed income (bonds, yield curves, duration, convexity)
- Derivatives (options, futures, swaps)
- Cryptocurrency markets and DeFi
- Market efficiency hypothesis (EMH)
- Technical and fundamental analysis frameworks

**Application to Trading System:**
- **Order types and execution:** Understanding market orders, limit orders, stop orders, iceberg orders, and TWAP/VWAP execution algorithms
- **Forex market structure:** The forex market is decentralized, OTC, with different liquidity tiers — your system needs to understand how prices are quoted and executed
- **Crypto market structure:** Crypto trades on centralized exchanges (Binance, Coinbase) with different fee structures, maker/taker models, and funding rates for perpetual futures
- **Efficiency hypothesis testing:** Test whether markets are weak-form efficient (technical analysis works), semi-strong (fundamental analysis works), or strong-form (nothing works consistently)

---

### 11. Risk Management

**Typical Code:** FIN 401 / RMI 3XX / FIN 3XX

**Topics:**
- Value at Risk (VaR) and Expected Shortfall (CVaR)
- Stress testing and scenario analysis
- Maximum drawdown analysis
- Position sizing methods (Kelly Criterion, fixed fractional)
- Correlation and diversification
- Tail risk and fat-tailed distributions
- Risk-adjusted performance metrics (Sharpe, Sortino, Calmar)

**Application to Trading System:**
- **VaR for daily risk limits:** Calculate the maximum expected loss at 99% confidence — if VaR exceeds your threshold, reduce position sizes
- **Kelly Criterion for optimal sizing:** `f* = (bp - q) / b` where b=odds, p=win probability, q=1-p. This maximizes long-term growth rate but is aggressive — use fractional Kelly (half or quarter Kelly)
- **Maximum drawdown as a circuit breaker:** If your system's drawdown exceeds a threshold (e.g., 15%), automatically stop trading and alert for manual review
- **Sharpe ratio for strategy evaluation:** `(mean_return - risk_free_rate) / std_return` — only deploy strategies with Sharpe > 1.5 (ideally > 2)
- **Fat tails in crypto:** Crypto returns have extreme kurtosis — standard VaR underestimates tail risk. Use Student-t or empirical distributions instead

---

### 12. Portfolio Theory

**Typical Code:** FIN 401 / FIN 3XX / ECO 4XX

**Topics:**
- Modern Portfolio Theory (Markowitz)
- Efficient frontier and capital market line
- Capital Asset Pricing Model (CAPM)
- Arbitrage Pricing Theory (APT)
- Factor models (Fama-French)
- Black-Litterman model
- Risk parity

**Application to Trading System:**
- **Multi-pair portfolio construction:** Instead of trading single pairs, construct an optimal portfolio of 10-20 pairs that maximizes return for a given risk level
- **Efficient frontier for strategy selection:** Plot your different strategies on a risk-return plane and select those on the efficient frontier
- **Factor models for alpha generation:** Decompose currency returns into factors (carry, momentum, value, volatility) — trade the factors, not individual pairs
- **Risk parity:** Allocate risk equally across pairs rather than capital equally — this prevents a single volatile pair from dominating portfolio risk
- **Black-Litterman for combining views:** Combine your model's predictions (views) with market equilibrium (prior) to get a more robust portfolio allocation

---

## PART C — Skill Gap Analysis

### Critical Gaps (Must Fill for a Functional System)

| Gap | Why It's Critical | How to Fill |
|-----|-------------------|-------------|
| **Python Programming** | Everything runs on Python — data ingestion, model training, backtesting, execution | Complete: Python basics → pandas → NumPy → scikit-learn. Build projects: price data downloader, backtester, live paper trader |
| **Software Engineering Practices** | Your system will run 24/5 (forex) or 24/7 (crypto) — it needs to be robust, tested, and maintainable | Learn: Git, unit testing (pytest), logging, error handling, virtual environments, Docker basics |
| **API Integration** | Connecting to broker/exchange APIs (OANDA, Binance, Interactive Brokers) is the execution layer | Learn: REST APIs, WebSocket connections, authentication (OAuth, API keys), rate limiting, error handling |
| **Data Engineering** | Collecting, cleaning, storing, and accessing market data at scale | Learn: pandas for data manipulation, SQL for storage, data pipelines, handling missing data, timezone conversions |
| **Statistical Testing** | Knowing if your backtest results are statistically significant or just noise | Learn: hypothesis testing, p-values, multiple testing correction (Bonferroni, FDR), out-of-sample testing |

### Important Gaps (Fill to Build a Competitive System)

| Gap | Why It Matters | How to Fill |
|-----|----------------|-------------|
| **Machine Learning in Practice** | Theory from courses ≠ practical ML engineering | Learn: scikit-learn, XGBoost, PyTorch. Practice: feature engineering, hyperparameter tuning, preventing data leakage in time series |
| **Linux and Server Administration** | Trading systems run on VPS/cloud servers | Learn: Linux command line, SSH, cron jobs, systemd services, basic networking |
| **Version Control (Git)** | Track changes to strategies, models, and code | Learn: git init, commit, branch, merge, GitHub/GitLab workflows |
| **Cloud Computing** | Scalability, reliability, and 24/7 uptime | Learn: AWS/GCP basics, EC2/GCE instances, S3 storage, basic serverless |
| **Visualization and Dashboards** | Monitoring system performance in real-time | Learn: matplotlib, plotly, Streamlit or Dash for live dashboards |

### Advanced Gaps (Fill for an Institutional-Grade System)

| Gap | Why It Matters | How to Fill |
|-----|----------------|-------------|
| **Natural Language Processing (NLP)** | Sentiment analysis from news, social media, and central bank statements | Learn: transformers (BERT, GPT), sentiment analysis, text preprocessing |
| **Reinforcement Learning** | Learn optimal trading policies without explicit rules | Learn: Q-learning, PPO, A2C. Libraries: Stable Baselines3, RLlib |
| **High-Performance Computing** | Backtesting millions of parameter combinations requires speed | Learn: Cython, Numba, vectorized NumPy, parallel processing |
| **Market Microstructure** | Understanding order flow, market impact, and execution quality at a deep level | Read: "Trading and Exchanges" by Larry Harris, "Algorithmic Trading" by Ernest Chan |
| **Behavioral Finance** | Understanding why markets aren't rational — and exploiting it | Read: "Misbehaving" by Thaler, "Irrational Exuberance" by Shiller |

### Recommended Learning Path (Priority Order)

1. **Month 1-2:** Python programming + pandas + NumPy + basic SQL
2. **Month 2-3:** Statistics refresher + probability + hypothesis testing
3. **Month 3-4:** Machine learning basics (scikit-learn, XGBoost) + Git
4. **Month 4-5:** Build a backtesting framework from scratch (this teaches you everything)
5. **Month 5-6:** API integration + connect to a broker/exchange for paper trading
6. **Month 6-8:** Deep learning (LSTM, Transformers) + time series analysis
7. **Month 8-10:** Risk management implementation + portfolio optimization
8. **Month 10-12:** Live paper trading, debugging, stress testing, iteration

### Key Resources

- **Books:** "Advances in Financial Machine Learning" (Marcos López de Prado), "Quantitative Trading" (Ernest Chan), "Python for Finance" (Yves Hilpisch)
- **Courses:** Andrew Ng's ML course (Coursera), QuantConnect tutorials, Kaggle time series competitions
- **Practice:** Build real projects — a crypto price tracker, a backtest engine, a paper trading bot. Projects > certificates.

---

## Summary: Your Current Strengths and Weaknesses

### Strengths (from completed coursework)
- ✅ Solid mathematical foundations (calculus, linear algebra)
- ✅ Basic probability and statistics
- ✅ Macroeconomic understanding (interest rates, inflation, exchange rates)
- ✅ IT fundamentals (networking, databases, basic programming concepts)

### Weaknesses (to address)
- ❌ No programming experience (Python is non-negotiable)
- ❌ No financial markets or instruments knowledge
- ❌ Weak statistical modeling (regression, time series, hypothesis testing)
- ❌ No machine learning knowledge
- ❌ No software engineering practices (testing, version control, deployment)
- ❌ Weak in advanced calculus (integral calculus was a C)

### Verdict
Your Year 1 economics and mathematics units provide a **theoretical foundation** that many self-taught traders lack — you understand *why* markets work (supply/demand, interest rates, macro policy) and you have the math to formalize it. The gap is in **practical implementation**: programming, data science, and engineering skills. The good news: these are highly learnable through online resources and practice, and your math background means the transition to ML and quantitative finance will be smoother than for someone starting from scratch.
