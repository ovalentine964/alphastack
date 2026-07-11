# Curriculum Mapping — Year 2: Economics & Statistics
## Valentine's Degree → Alpha Stack Institutional Trading System

*Generated: 2026-07-11 | Year 2 of 3*

---

## Summary Table

| Code | Unit Title | Grade | % | Alpha Stack Relevance |
|------|-----------|-------|---|----------------------|
| ECO 201 | Intermediate Microeconomics | C | 53 | ⭐⭐⭐ Market microstructure, game theory |
| ECO 202 | Introduction to Economic Statistics | D | 43 | ⭐⭐ Data analysis fundamentals |
| ECO 203 | Economic Statistics | C | 53 | ⭐⭐⭐ Statistical inference for trading |
| ECO 204 | Issues in African Development | C | 51 | ⭐⭐ Emerging market context |
| ECO 205 | Intermediate Macroeconomics | B | 67 | ⭐⭐⭐⭐ Macro regime detection |
| ECO 206 | Economics of Microfinance | C | 55 | ⭐⭐ Financial inclusion & mobile money |
| ECO 209 | Money and Banking | B | 65 | ⭐⭐⭐⭐⭐ Forex market mechanics |
| ECO 210 | Introduction to Quantitative Methods | B | 60 | ⭐⭐⭐⭐ Systematic trading methods |
| STA 241 | Probability and Distribution Models | A | 77 | ⭐⭐⭐⭐⭐ Risk modeling foundation |
| STA 244 | Time Series Analysis & Forecasting | D | 45 | ⭐⭐⭐⭐⭐ PRICE FORECASTING CORE |
| STA 245 | Social & Economic Statistics for National Planning | C | 51 | ⭐⭐⭐ Macro data analysis |
| STA 246 | Statistical Demography | B | 66 | ⭐⭐ Population-driven economic signals |

---

# UNIT 1: ECO 201 — Intermediate Microeconomics
**Grade: C (53%) | Alpha Stack Relevance: ⭐⭐⭐**

## Course Overview
Deepens the microeconomic toolkit from Year 1 — focuses on formal consumer/producer theory, general equilibrium, market failure, and information economics.

---

### Topic 1.1: Consumer Theory — Utility Maximization

#### Concept: Utility Functions
- **What it means:** Mathematical representation of consumer preferences — ordinal ranking of consumption bundles (e.g., U(x,y) = x^α · y^β for Cobb-Douglas)
- **Alpha Stack application:** Utility functions map directly to **objective functions** in portfolio optimization. A trader's "utility" is their risk-adjusted return — the system's optimization engine maximizes a utility function over portfolio weights
- **AI/future alignment:** Reinforcement learning agents learn implicit utility functions from reward signals — the RL reward IS the utility function. Multi-agent systems must model other agents' utility functions to anticipate their behavior
- **Research connection:** In multi-agent trading systems (Research 03), each agent has its own utility function. Nash equilibrium occurs when no agent can improve its utility given others' strategies — this is the equilibrium state the system should converge toward

#### Concept: Indifference Curves and Marginal Rate of Substitution (MRS)
- **What it means:** Combinations of goods giving equal utility; MRS = rate at which a consumer willingly trades one good for another while maintaining same utility
- **Alpha Stack application:** **Indifference curves in risk-return space** — an investor is indifferent between combinations of expected return and risk (standard deviation) along their indifference curve. The tangency with the efficient frontier gives the optimal portfolio
- **AI/future alignment:** AI portfolio managers implicitly construct indifference surfaces in multi-dimensional risk factor space — far beyond 2D textbook curves
- **Research connection:** Quantum portfolio optimization (Research 06) solves for the tangency point between risk-return indifference surfaces and the efficient frontier in higher dimensions — a problem exponentially hard for classical computers

#### Concept: Budget Constraints
- **What it means:** Limited income constrains consumption choices — the budget line shows all affordable bundles
- **Alpha Stack application:** **Capital constraints** are the trader's budget constraint. With $7 starting capital, every allocation decision is constrained. The system must optimize signal allocation subject to margin requirements and maximum position sizes
- **AI/future alignment:** Constrained optimization is fundamental to AI — LLMs are optimized subject to compute budgets, trading agents subject to capital limits
- **Research connection:** In the Alpha Stack multi-agent architecture (Research 03), each agent operates under a budget constraint (allocated capital). The meta-allocator distributes capital across agents subject to total portfolio constraints

#### Concept: Income and Substitution Effects
- **What it means:** When price changes, the total effect decomposes into: (1) substitution effect (change in relative price) and (2) income effect (change in purchasing power)
- **Alpha Stack application:** When the price of a currency pair moves, the effect on portfolio value decomposes similarly — the "substitution effect" is the change in relative attractiveness of that pair vs. others; the "income effect" is the change in portfolio equity affecting future position sizing
- **AI/future alignment:** Decomposing price effects into components helps AI models understand WHY prices move, not just THAT they move — more interpretable models
- **Research connection:** Decomposition reasoning is a key pattern in agentic loop systems (Research 03) — the ReAct loop naturally decomposes complex observations into constituent effects

---

### Topic 1.2: Producer Theory — Cost and Supply

#### Concept: Production Functions and Returns to Scale
- **What it means:** Relationship between inputs and outputs — increasing, constant, or decreasing returns to scale
- **Alpha Stack application:** **Strategy capacity** — a trading strategy has "returns to scale." Small strategies may have increasing returns (better fills, lower relative costs), but at some point, market impact causes decreasing returns. The system must identify optimal strategy capacity
- **AI/future alignment:** AI compute scaling laws (Chinchilla, etc.) mirror production functions — understanding diminishing returns helps allocate compute budget to model training vs. inference
- **Research connection:** Multi-agent systems face diminishing returns as more agents trade the same signals — alpha decay is decreasing returns to scale in agent count

#### Concept: Cost Curves (MC, AC, AVC)
- **What it means:** Marginal cost (MC) = cost of one more unit; Average cost (AC) = total cost / quantity; MC intersects AC at AC minimum
- **Alpha Stack application:** **Trading cost analysis** — marginal cost per trade (spread + commission + slippage), average cost across all trades, and the relationship between them. When marginal cost > average cost, trading frequency is too high
- **AI/future alignment:** AI inference costs follow similar curves — marginal cost per prediction decreases with batching, but infrastructure costs create step functions
- **Research connection:** The loop system cost analysis (Research 03) shows each ReAct loop iteration has a marginal token cost — the system should stop iterating when marginal information gain < marginal cost

#### Concept: Profit Maximization (MR = MC)
- **What it means:** Firms maximize profit where marginal revenue equals marginal cost
- **Alpha Stack application:** **Optimal trade frequency** — trade until the marginal expected profit from one more trade equals the marginal cost (spread + commission + slippage + risk). Overtrading occurs when you trade below this threshold
- **AI/future alignment:** AI systems can compute MR and MC in real-time, adjusting trade frequency dynamically — unlike human traders who have fixed habits
- **Research connection:** The deliberation loop (Research 03) implements MR=MC reasoning — the agent continues gathering information until marginal information value = marginal computation cost

---

### Topic 1.3: Market Structures

#### Concept: Perfect Competition vs. Monopoly vs. Oligopoly
- **What it means:** Market structures characterized by number of firms, barriers to entry, product differentiation, and price-setting power
- **Alpha Stack application:** **Market microstructure classification** — forex is an oligopoly (major banks as dealers), crypto is closer to perfect competition (many exchanges, low barriers). Different structures require different execution strategies
- **AI/future alignment:** AI market makers are becoming the dominant "firms" in financial markets — understanding market structure helps predict where AI will have the most impact
- **Research connection:** Multi-agent market simulations (Research 03) model different market structures — agents behave differently in competitive vs. monopolistic environments

#### Concept: Monopolistic Competition and Product Differentiation
- **What it means:** Many firms with differentiated products; each has some pricing power due to differentiation
- **Alpha Stack application:** **Strategy differentiation** — in a crowded quant space, your strategy must be differentiated (different signals, different timeframes, different risk profiles) to maintain alpha. Copying popular strategies leads to crowded trades and alpha decay
- **AI/future alignment:** AI enables rapid strategy differentiation — generative models can explore novel strategy spaces that humans wouldn't consider
- **Research connection:** In multi-agent systems, agents must differentiate their strategies to avoid collectively destroying alpha — this is a direct application of monopolistic competition theory

---

### Topic 1.4: Game Theory and Strategic Behavior

#### Concept: Nash Equilibrium
- **What it means:** A strategy profile where no player can improve their payoff by unilaterally changing their strategy, given others' strategies
- **Alpha Stack application:** **Market equilibrium detection** — when the market reaches Nash equilibrium, no trader can improve returns by changing strategy. The system should detect when equilibrium is disrupted (new information, regime change) and trade the transition
- **AI/future alignment:** Multi-agent AI systems must compute Nash equilibria to avoid being exploitable — this is a core challenge in AI safety and trading
- **Research connection:** Multi-agent trading systems (Research 03) explicitly model Nash equilibria — the system should identify when markets deviate from equilibrium and exploit the disequilibrium

#### Concept: Prisoner's Dilemma and Cooperation
- **What it means:** Two rational players may not cooperate even when cooperation would benefit both — dominant strategy leads to suboptimal outcome
- **Alpha Stack application:** **Market manipulation and cooperation** — traders face prisoner's dilemmas when deciding whether to cooperate (e.g., maintaining orderly markets) or defect (e.g., front-running, manipulation). The system must be robust to defection
- **AI/future alignment:** AI agents in multi-agent markets face iterated prisoner's dilemmas — tit-for-tat and other strategies from game theory inform agent design
- **Research connection:** In multi-agent loop systems (Research 03), agents must handle adversarial behavior from other agents — game theory provides the framework for robust agent design

#### Concept: Signaling and Screening
- **What it means:** Informed parties can signal their private information; uninformed parties design screening mechanisms to elicit information
- **Alpha Stack application:** **Order flow analysis** — large institutional orders "signal" information about future price direction. The system can use order flow as a signal (informed trading detection). Conversely, smart order routing "screens" market conditions to find the best execution
- **AI/future alignment:** AI systems can detect subtle signals in market data that humans miss — order flow toxicity, informed trading ratios, dark pool activity
- **Research connection:** Signal extraction is a core capability in multi-agent systems — agents must distinguish real signals from noise, and from adversarial signals designed to mislead

---

### Topic 1.5: Market Failure and Information Economics

#### Concept: Asymmetric Information
- **What it means:** One party has more or better information than another — leads to adverse selection and moral hazard
- **Alpha Stack application:** **Informed vs. uninformed trading** — the system must detect when it's trading against informed flow (adverse selection). The Bid-Ask Spread decomposition model (Glosten-Milgrom) separates informed and uninformed components
- **AI/future alignment:** AI can process information faster than humans, reducing (but not eliminating) information asymmetry — speed becomes the new information advantage
- **Research connection:** Multi-agent systems must model information asymmetry between agents — some agents have access to different data feeds, creating an information hierarchy

#### Concept: Externalities and Public Goods
- **What it means:** Costs or benefits that affect third parties not involved in the transaction; public goods are non-excludable and non-rival
- **Alpha Stack application:** **Market stability as a public good** — individual traders can free-ride on market stability without contributing to it. Systemic risk is a negative externality — individual position sizing doesn't account for system-wide risk
- **AI/future alignment:** AI trading systems that collectively destabilize markets create negative externalities — regulation (circuit breakers, position limits) addresses this
- **Research connection:** Multi-agent systems must model externalities — one agent's actions affect market conditions for all other agents. The loop architecture (Research 03) must include system-level risk constraints

---

# UNIT 2: ECO 202 — Introduction to Economic Statistics
**Grade: D (43%) | Alpha Stack Relevance: ⭐⭐**

## Course Overview
Foundational statistics applied to economic data — descriptive statistics, probability, estimation, hypothesis testing, and correlation analysis.

---

### Topic 2.1: Descriptive Statistics for Economic Data

#### Concept: Measures of Central Tendency (Mean, Median, Mode)
- **What it means:** Mean = average; Median = middle value; Mode = most frequent value. Each tells a different story about the "center" of a distribution
- **Alpha Stack application:** **Price analysis** — mean price over a period (simple moving average), median price (robust to outliers), mode (most traded price / point of control in volume profile). The system uses all three for different signals
- **AI/future alignment:** AI models can dynamically choose the best central tendency measure based on data characteristics — robust to regime changes where the "typical" return shifts
- **Research connection:** In multi-agent systems, different agents may use different central tendency measures — consensus mechanisms aggregate these diverse estimates

#### Concept: Measures of Dispersion (Variance, Standard Deviation, Range)
- **What it means:** How spread out data is — variance = average squared deviation from mean; SD = √variance; range = max - min
- **Alpha Stack application:** **Volatility measurement** — standard deviation of returns IS the classic volatility measure. Range-based volatility estimators (Parkinson, Garman-Klass) use the price range for more efficient estimation
- **AI/future alignment:** AI can estimate volatility from alternative data (order flow, news sentiment) beyond simple return standard deviation — richer volatility models
- **Research connection:** Quantum computing (Research 06) can accelerate Monte Carlo simulations for complex volatility models — computing option prices under stochastic volatility in real-time

#### Concept: Skewness and Kurtosis
- **What it means:** Skewness = asymmetry of distribution; kurtosis = tail heaviness. Financial returns typically have negative skewness (more large losses) and excess kurtosis (fatter tails than normal)
- **Alpha Stack application:** **Risk modeling** — the system must account for non-normal return distributions. A strategy with negative skewness (many small wins, occasional large losses) requires different risk management than one with positive skewness
- **AI/future alignment:** AI models can learn the full return distribution shape, including skewness and kurtosis, enabling better tail risk management
- **Research connection:** Quantum Monte Carlo (Research 06) can sample from complex distributions with arbitrary skewness and kurtosis more efficiently than classical methods

---

### Topic 2.2: Correlation and Regression

#### Concept: Correlation Coefficient (Pearson's r)
- **What it measures:** Linear relationship between two variables, ranging from -1 to +1
- **Alpha Stack application:** **Pair correlation** — the system monitors correlations between currency pairs for pairs trading (correlated pairs diverge → trade the convergence) and portfolio diversification (low-correlation pairs reduce portfolio risk)
- **AI/future alignment:** AI can detect non-linear correlations that Pearson's r misses — mutual information, distance correlation, and neural network-based dependency measures
- **Research connection:** Multi-agent systems (Research 03) must track inter-agent correlation — if all agents are correlated, the portfolio has hidden concentration risk

#### Concept: Simple Linear Regression
- **What it means:** Modeling Y = α + βX + ε — finding the best-fit line through data points
- **Alpha Stack application:** **Beta estimation** — regressing asset returns against market returns gives beta (systematic risk). Also used for factor models — regressing currency returns against carry, momentum, and value factors
- **AI/future alignment:** AI extends regression to non-linear models (neural networks, gradient boosting) while maintaining the interpretability of linear models through attention mechanisms
- **Research connection:** Linear regression is the foundation of factor-based trading — multi-agent systems can each specialize in different factors and combine predictions

#### Concept: Coefficient of Determination (R²)
- **What it means:** Proportion of variance in Y explained by X — ranges from 0 to 1
- **Alpha Stack application:** **Signal quality measurement** — R² measures how much of price variance a signal explains. Low R² means the signal is noisy; high R² means it's predictive. The system uses R² to rank and filter signals
- **AI/future alignment:** AI models report R²-equivalent metrics (explained variance) for each prediction — transparent model evaluation
- **Research connection:** In multi-agent systems, each agent's R² contributes to the ensemble's overall predictive power — agent selection based on R² performance

---

### Topic 2.3: Probability in Economics

#### Concept: Random Variables and Distributions
- **What it means:** Random variables assign numbers to outcomes; distributions describe the probability of each value
- **Alpha Stack application:** **Return as a random variable** — each price change is a realization of a random variable. The system models returns using various distributions (normal, Student-t, skewed-t, generalized hyperbolic)
- **AI/future alignment:** AI can learn the distribution directly from data without assuming a parametric form — conditional density estimation
- **Research connection:** Quantum computers can sample from complex distributions more efficiently (Research 06) — enabling faster Monte Carlo risk simulations

#### Concept: Expected Value and Variance
- **What it means:** Expected value = probability-weighted average; variance = expected squared deviation from mean
- **Alpha Stack application:** **Trade expectation** — EV = P(win) × avg_win - P(loss) × avg_loss. The system only takes trades with positive expected value. Variance of trade outcomes determines position sizing (Kelly criterion)
- **AI/future alignment:** AI systems estimate EV and variance in real-time, adjusting for changing market conditions — adaptive position sizing
- **Research connection:** Kelly criterion (optimal bet sizing) requires accurate EV and variance estimates — multi-agent systems can pool estimates for more robust sizing

---

### Topic 2.4: Sampling and Data Collection

#### Concept: Sampling Methods and Sampling Error
- **What it means:** Using a subset of data to estimate population parameters — sampling error = difference between sample statistic and population parameter
- **Alpha Stack application:** **Backtesting sample size** — a strategy backtested on 100 trades has more sampling error than one tested on 1,000 trades. The system must assess statistical significance of backtest results
- **AI/future alignment:** AI models require large, representative training samples — data augmentation and synthetic data generation address sampling limitations
- **Research connection:** Multi-agent systems can use ensemble methods to reduce sampling error — each agent trained on different samples, predictions aggregated

#### Concept: Sampling Distributions
- **What it means:** The distribution of a statistic (e.g., sample mean) across all possible samples — central limit theorem ensures it's approximately normal for large samples
- **Alpha Stack application:** **Confidence intervals for strategy returns** — the sampling distribution of mean returns allows constructing confidence intervals. If the 95% CI includes zero, the strategy may not have real alpha
- **AI/future alignment:** Bayesian AI models naturally produce posterior distributions over parameters — full uncertainty quantification
- **Research connection:** Quantum speedup in Monte Carlo sampling (Research 06) enables faster computation of sampling distributions for complex statistics

---

# UNIT 3: ECO 203 — Economic Statistics
**Grade: C (53%) | Alpha Stack Relevance: ⭐⭐⭐**

## Course Overview
Advanced statistical methods for economic analysis — hypothesis testing, ANOVA, non-parametric methods, and multivariate analysis.

---

### Topic 3.1: Hypothesis Testing

#### Concept: Null and Alternative Hypotheses
- **What it means:** Null hypothesis (H₀) = default claim; alternative (H₁) = claim to test. Statistical test determines if evidence is strong enough to reject H₀
- **Alpha Stack application:** **Strategy validation** — H₀: "This strategy has no edge (mean return = 0)"; H₁: "This strategy has positive edge." Rejecting H₀ at 95% confidence means the strategy likely has real alpha
- **AI/future alignment:** AI models can run thousands of hypothesis tests simultaneously (multiple testing correction required) — automated strategy discovery with statistical rigor
- **Research connection:** Multi-agent systems (Research 03) can run parallel hypothesis tests — each agent tests different signal hypotheses, meta-agent aggregates results with proper multiple testing correction

#### Concept: Type I and Type II Errors
- **What it means:** Type I (false positive) = rejecting true H₀; Type II (false negative) = failing to reject false H₀. In trading: Type I = thinking a strategy works when it doesn't (overfitting); Type II = discarding a strategy that actually works
- **Alpha Stack application:** **Overfitting detection** — Type I error is the overfitting problem. The system must control false discovery rate when testing multiple strategies. Walk-forward analysis and out-of-sample testing reduce Type I errors
- **AI/future alignment:** AI can balance Type I and Type II errors using cost-sensitive learning — the cost of deploying a bad strategy (Type I) is typically higher than missing a good one (Type II)
- **Research connection:** In multi-agent systems, each agent has its own Type I/II error profile — the meta-agent must weight agents by their reliability (inverse of Type I error rate)

#### Concept: p-values and Significance Levels
- **What it means:** p-value = probability of observing data this extreme if H₀ is true; significance level (α) = threshold for rejection (typically 0.05)
- **Alpha Stack application:** **Signal significance** — only trade signals with p-value < 0.05 (or stricter). Multiple testing correction (Bonferroni, FDR) is essential when testing hundreds of potential signals
- **AI/future alignment:** AI can compute p-values for complex, non-standard test statistics using permutation tests and bootstrap methods — more flexible than traditional parametric tests
- **Research connection:** Quantum speedup (Research 06) enables permutation tests with all possible rearrangements rather than random subsets — exact p-values for complex statistics

#### Concept: t-tests and z-tests
- **What it means:** t-test compares means (one-sample, two-sample, paired); z-test for known variance. Both test if observed differences are statistically significant
- **Alpha Stack application:** **Strategy comparison** — two-sample t-test to determine if Strategy A's returns are significantly different from Strategy B's. Also used to test if mean returns are significantly different from zero
- **AI/future alignment:** AI extends these to non-parametric alternatives (Mann-Whitney U, Wilcoxon) that don't assume normality — more robust for financial data
- **Research connection:** Multi-agent systems use t-tests to compare agent performance — is Agent A significantly better than Agent B, or is the difference just noise?

---

### Topic 3.2: Analysis of Variance (ANOVA)

#### Concept: One-Way ANOVA
- **What it means:** Testing if the means of three or more groups are equal — extends the two-sample t-test to multiple groups
- **Alpha Stack application:** **Strategy performance across regimes** — ANOVA tests if strategy returns differ significantly across market regimes (trending, ranging, volatile). If they do, the strategy should be regime-conditional
- **AI/future alignment:** AI can use ANOVA-like decomposition to understand which factors drive model performance across different conditions
- **Research connection:** Multi-agent systems use ANOVA to determine if agent performance varies across market conditions — regime-specific agent allocation

#### Concept: Two-Way ANOVA and Interaction Effects
- **What it means:** Testing the effect of two factors simultaneously, including their interaction — does the effect of Factor A depend on the level of Factor B?
- **Alpha Stack application:** **Factor interaction analysis** — does the momentum signal work differently in high-volatility vs. low-volatility environments? Two-way ANOVA tests this. Interaction effects reveal when signals combine non-additively
- **AI/future alignment:** AI models naturally capture interaction effects through non-linear architectures (attention mechanisms, cross-features)
- **Research connection:** Multi-agent systems must model agent interactions — Agent A's performance may depend on Agent B's behavior (interaction effect)

---

### Topic 3.3: Non-Parametric Methods

#### Concept: Chi-Square Tests
- **What it means:** Testing independence or goodness-of-fit without assuming a specific distribution
- **Alpha Stack application:** **Signal independence testing** — chi-square test to verify that two trading signals are independent (if not, combining them adds less value). Also used to test if trade outcomes are independent of market conditions
- **AI/future alignment:** AI can use chi-square-like tests for feature selection — identifying which features are independent vs. redundant
- **Research connection:** Multi-agent systems require independence between agents — chi-square tests verify that agents aren't making correlated errors

#### Concept: Rank-Based Tests (Wilcoxon, Mann-Whitney)
- **What it means:** Tests based on data ranks rather than values — robust to outliers and non-normality
- **Alpha Stack application:** **Robust strategy comparison** — when return distributions are non-normal (as they always are in finance), rank-based tests provide more reliable comparisons than t-tests
- **AI/future alignment:** AI models can use rank-based loss functions (e.g., optimizing for median rather than mean performance) — more robust to outliers
- **Research connection:** Multi-agent systems can use rank-based aggregation (median of agent predictions) rather than mean — more robust to individual agent failures

---

### Topic 3.4: Multivariate Analysis

#### Concept: Multiple Regression
- **What it means:** Y = β₀ + β₁X₁ + β₂X₂ + ... + βₖXₖ + ε — modeling the relationship between a dependent variable and multiple independent variables
- **Alpha Stack application:** **Multi-factor models** — regressing currency returns on multiple factors (carry, momentum, value, volatility) simultaneously. Each βᵢ measures the sensitivity to that factor, holding others constant
- **AI/future alignment:** AI extends multiple regression to non-linear multi-factor models — gradient boosting, neural networks can capture complex factor interactions
- **Research connection:** Multi-agent systems (Research 03) can specialize in different factors — the meta-agent combines predictions using a multiple regression framework

#### Concept: Multicollinearity
- **What it means:** High correlation among independent variables — makes individual coefficient estimates unstable
- **Alpha Stack application:** **Feature redundancy** — if momentum and trend-following signals are highly correlated, including both in a model adds noise without information. The system must detect and handle multicollinearity (VIF analysis, PCA)
- **AI/future alignment:** AI models handle multicollinearity through regularization (L1/L2) — automatically down-weighting redundant features
- **Research connection:** Multi-agent systems face multicollinearity when agents use similar signals — regularization at the meta-agent level prevents over-concentration in correlated signals

---

# UNIT 4: ECO 204 — Issues in African Development
**Grade: C (51%) | Alpha Stack Relevance: ⭐⭐**

## Course Overview
Economic development challenges specific to Africa — structural adjustment, trade, governance, natural resources, and regional integration.

---

### Topic 4.1: Structural Adjustment and Economic Reform

#### Concept: IMF/World Bank Structural Adjustment Programs (SAPs)
- **What it means:** Policy packages (austerity, privatization, trade liberalization) attached to loans for developing countries
- **Alpha Stack application:** **Emerging market regime detection** — SAP implementation creates predictable currency dynamics: initial depreciation (austerity shock), then gradual stabilization (if reforms succeed). The system can model these macro regimes for African currency pairs
- **AI/future alignment:** AI can monitor IMF program compliance and reform progress as features for EM currency models — real-time structural adjustment tracking
- **Research connection:** Multi-agent systems can have dedicated agents for EM macro regime detection — monitoring policy reform signals alongside technical indicators

#### Concept: Debt Sustainability
- **What it means:** Whether a country can service its debt without extraordinary financing or default
- **Alpha Stack application:** **Sovereign risk scoring** — the system monitors debt-to-GDP ratios, debt service costs, and IMF assessments as features for currency risk. Countries approaching debt distress see currency depreciation and increased volatility
- **AI/future alignment:** AI can process IMF Article IV reports, debt sustainability analyses, and credit rating changes in real-time — automated sovereign risk assessment
- **Research connection:** Quantum computing (Research 06) can solve complex debt sustainability models with multiple interacting variables faster than classical methods

---

### Topic 4.2: Trade and Regional Integration

#### Concept: Regional Trade Blocs (EAC, ECOWAS, SADC, AfCFTA)
- **What it means:** African regional trade agreements aimed at reducing barriers and increasing intra-African trade
- **Alpha Stack application:** **Regional currency dynamics** — trade bloc integration affects currency pairs within the bloc (e.g., EAC currency stability) and cross-bloc flows. AfCFTA implementation could shift trade patterns and currency correlations
- **AI/future alignment:** AI can track trade agreement implementation progress and model its impact on bilateral trade flows and exchange rates
- **Research connection:** Multi-agent systems can model regional economic integration as a multi-player game — countries as agents with trade policy strategies

#### Concept: Terms of Trade and Commodity Dependence
- **What it means:** Ratio of export prices to import prices; many African economies depend heavily on commodity exports
- **Alpha Stack application:** **Commodity-currency linkage** — African currencies (NGN, KES, ZAR, GHS) are heavily influenced by commodity prices. The system tracks commodity terms of trade as a leading indicator for currency moves
- **AI/future alignment:** AI can model complex commodity-currency linkages using multi-modal data (commodity futures, shipping data, production reports)
- **Research connection:** Multi-agent systems can have dedicated commodity-currency agents that specialize in these linkages

---

### Topic 4.3: Governance and Institutional Quality

#### Concept: Institutional Quality and Economic Performance
- **What it means:** Strong institutions (rule of law, property rights, low corruption) correlate with better economic outcomes
- **Alpha Stack application:** **Institutional quality as a currency filter** — countries with improving institutional quality (rising governance scores) tend to see currency appreciation; deteriorating institutions signal depreciation risk
- **AI/future alignment:** AI can track governance indicators (World Bank WGI, Mo Ibrahim Index) and news sentiment about institutional quality — real-time institutional risk scoring
- **Research connection:** Multi-agent systems can incorporate institutional quality as a slow-moving macro feature — affecting long-term currency allocation

---

### Topic 4.4: Natural Resource Management

#### Concept: Resource Curse (Dutch Disease)
- **What it means:** Resource-rich countries often experience currency overvaluation, manufacturing decline, and governance problems
- **Alpha Stack application:** **Resource currency dynamics** — the system models how oil price changes affect NGN (Nigeria), how mineral prices affect ZAR (South Africa), and how the "resource curse" creates predictable currency patterns
- **AI/future alignment:** AI can model the resource curse mechanism through multi-equation systems — tracking commodity prices, real exchange rates, manufacturing output, and governance simultaneously
- **Research connection:** Quantum computing (Research 06) can solve these multi-equation resource curse models with complex feedback loops

---

# UNIT 5: ECO 205 — Intermediate Macroeconomics
**Grade: B (67%) | Alpha Stack Relevance: ⭐⭐⭐⭐**

## Course Overview
Formal macroeconomic models — IS-LM, AD-AS, open economy macroeconomics, monetary/fiscal policy, and business cycle theory.

---

### Topic 5.1: The IS-LM Model

#### Concept: IS Curve (Investment-Saving)
- **What it means:** Combinations of interest rate and output where the goods market is in equilibrium — downward sloping (lower rates → more investment → more output)
- **Alpha Stack application:** **Interest rate-output dynamics** — the IS curve helps the system understand how interest rate changes affect economic activity and, through this, currency strength. A shift in the IS curve (fiscal policy change) changes the equilibrium interest rate and output
- **AI/future alignment:** AI models can estimate the IS curve parameters in real-time from economic data, detecting shifts as they happen — faster than human economists
- **Research connection:** Multi-agent systems (Research 03) can have a dedicated macro agent that models IS-LM dynamics — providing regime signals to the trading agents

#### Concept: LM Curve (Liquidity Preference-Money Supply)
- **What it means:** Combinations of interest rate and output where the money market is in equilibrium — upward sloping (higher output → more money demand → higher rates)
- **Alpha Stack application:** **Monetary policy transmission** — the LM curve shows how central bank money supply decisions affect interest rates and, through them, exchange rates. The system tracks money supply growth and central bank operations as features
- **AI/future alignment:** AI can process central bank communications (FOMC minutes, MPC statements) and estimate shifts in the LM curve — real-time monetary policy analysis
- **Research connection:** Multi-agent systems can have dedicated central bank watcher agents — parsing policy signals and updating LM curve estimates

#### Concept: IS-LM Equilibrium and Policy Effects
- **What it means:** The intersection of IS and LM determines equilibrium output and interest rate; fiscal policy shifts IS, monetary policy shifts LM
- **Alpha Stack application:** **Policy impact modeling** — when a fiscal stimulus is announced (IS shift right), the system predicts: higher output, higher interest rates, currency appreciation (if monetary policy is unchanged). This is a direct trading signal
- **AI/future alignment:** AI can simulate IS-LM equilibrium changes under different policy scenarios — automated scenario analysis for trading decisions
- **Research connection:** Quantum computing (Research 06) can solve IS-LM models with hundreds of interacting variables — multi-country, multi-sector extensions

---

### Topic 5.2: Aggregate Demand — Aggregate Supply (AD-AS)

#### Concept: Aggregate Demand Curve
- **What it means:** Relationship between price level and total output demanded — downward sloping (wealth effect, interest rate effect, exchange rate effect)
- **Alpha Stack application:** **Inflation-output tradeoff** — the AD curve helps the system understand how inflation expectations affect output and, through the exchange rate effect, currency values. A shift in AD (due to fiscal/monetary policy) changes both inflation and output
- **AI/future alignment:** AI can estimate the AD curve from high-frequency data (PMI, retail sales, industrial production) — real-time aggregate demand tracking
- **Research connection:** Multi-agent systems can have dedicated demand-tracking agents — monitoring consumption, investment, and government spending data

#### Concept: Short-Run and Long-Run Aggregate Supply
- **What it means:** SRAS is upward sloping (sticky prices); LRAS is vertical at potential output (full employment). The economy adjusts from SR to LR over time
- **Alpha Stack application:** **Output gap estimation** — the difference between actual and potential output (output gap) is a key macro signal. Positive gap → inflationary pressure → tighter monetary policy → currency appreciation. The system estimates the output gap using production function methods
- **AI/future alignment:** AI can estimate potential output and the output gap using multiple methods simultaneously (production function, statistical filters, survey data) — more robust estimates
- **Research connection:** Quantum computing (Research 06) can solve dynamic stochastic general equilibrium (DSGE) models that embed AD-AS dynamics — the frontier of macro modeling

#### Concept: Supply Shocks and Stagflation
- **What it means:** Negative supply shocks (oil price spikes, supply chain disruptions) shift SRAS left → higher prices AND lower output (stagflation)
- **Alpha Stack application:** **Stagflation trading** — stagflation is one of the hardest macro environments for traditional assets. The system must detect supply shocks early and position for: higher inflation (long commodities, short bonds), lower growth (short equities), and complex currency effects (commodity currencies up, others down)
- **AI/future alignment:** AI can detect supply shocks from alternative data (satellite imagery of ports, shipping data, commodity inventories) before they show up in official statistics
- **Research connection:** Multi-agent systems can have dedicated supply shock detection agents — monitoring global supply chain data for early warning signals

---

### Topic 5.3: Open Economy Macroeconomics

#### Concept: Mundell-Fleming Model (IS-LM-BP)
- **What it means:** Extends IS-LM to an open economy with a balance of payments (BP) curve — shows how fiscal and monetary policy work under different exchange rate regimes
- **Alpha Stack application:** **Exchange rate regime analysis** — the system must model policy effectiveness differently for fixed vs. floating exchange rate regimes. Under floating rates, monetary policy is powerful; under fixed rates, fiscal policy is powerful
- **AI/future alignment:** AI can classify countries' de facto exchange rate regimes (which often differ from declared regimes) and adjust policy impact models accordingly
- **Research connection:** Multi-agent systems can have regime-classification agents — determining the effective exchange rate regime and routing to appropriate policy models

#### Concept: Purchasing Power Parity (PPP)
- **What it means:** Exchange rates should equalize the price of identical goods across countries (law of one price extended to whole economies)
- **Alpha Stack application:** **Long-term mean reversion anchor** — PPP provides a fundamental fair value estimate for currency pairs. Pairs that deviate significantly from PPP may revert over long horizons. The system uses PPP deviation as a long-term signal
- **AI/future alignment:** AI can compute real-time PPP using big data (online prices, scanner data) rather than waiting for quarterly CPI releases — faster PPP deviation detection
- **Research connection:** Quantum computing (Research 06) can solve multi-country PPP models with hundreds of goods — high-dimensional price equilibrium computation

#### Concept: Interest Rate Parity (Covered and Uncovered)
- **What it means:** Covered interest rate parity: forward exchange rate reflects interest rate differential. Uncovered: expected exchange rate change equals interest rate differential
- **Alpha Stack application:** **Carry trade foundation** — the carry trade exploits deviations from uncovered interest rate parity. If the high-interest-rate currency doesn't depreciate as much as the interest differential suggests, the carry trade profits. The system monitors UIP deviations as carry trade signals
- **AI/future alignment:** AI can model time-varying risk premiums that cause UIP deviations — explaining why carry trades work (risk compensation, not market inefficiency)
- **Research connection:** Multi-agent systems (Research 03) can have dedicated carry trade agents that monitor UIP deviations across multiple currency pairs simultaneously

---

### Topic 5.4: Business Cycles

#### Concept: Business Cycle Phases (Expansion, Peak, Recession, Trough)
- **What it means:** Economies cycle through four phases — expansions (rising output), peaks (maximum output), recessions (falling output), troughs (minimum output)
- **Alpha Stack application:** **Regime-based trading** — the system classifies the current business cycle phase and adjusts strategy accordingly. Different currency factors (carry, momentum, value) perform differently at each phase
- **AI/future alignment:** AI can detect business cycle turning points from high-frequency data (PMI, jobless claims, credit growth) earlier than official recession dating — leading indicator construction
- **Research connection:** Multi-agent systems can have regime-detection agents that classify the business cycle phase and communicate it to all trading agents

#### Concept: Leading, Coincident, and Lagging Indicators
- **What it means:** Leading indicators predict future economic activity; coincident indicators move with the economy; lagging indicators confirm trends
- **Alpha Stack application:** **Economic indicator signals** — the system tracks leading indicators (yield curve, PMI, building permits, consumer confidence) for early economic cycle signals. These are features for macro-conditional trading models
- **AI/future alignment:** AI can construct composite leading indicators from hundreds of data sources — weighting indicators by their predictive power in real-time
- **Research connection:** Multi-agent systems can have indicator-specialist agents — each monitoring a different leading indicator, with the meta-agent combining their signals

#### Concept: Real Business Cycle (RBC) Theory
- **What it means:** Business cycles are driven by real shocks (technology, productivity) rather than monetary shocks — rational agents optimize in response to these shocks
- **Alpha Stack application:** **Productivity shock trading** — technology and productivity shocks affect currencies through terms of trade and competitiveness channels. The system can detect productivity shocks (TFP growth data) and trade the resulting currency adjustments
- **AI/future alignment:** AI can estimate total factor productivity (TFP) in real-time from multiple data sources — detecting productivity shifts before they're officially measured
- **Research connection:** Quantum computing (Research 06) can solve large-scale RBC models with heterogeneous agents — the frontier of quantitative macro

---

### Topic 5.5: Monetary and Fiscal Policy

#### Concept: Taylor Rule
- **What it means:** Central bank interest rate rule: i = r* + π + 0.5(π - π*) + 0.5(y - y*) — rate responds to inflation gap and output gap
- **Alpha Stack application:** **Rate expectation modeling** — the system uses the Taylor Rule to estimate the "appropriate" interest rate given current inflation and output gaps. Deviations between the Taylor Rule rate and the actual rate signal future rate moves — a direct trading signal
- **AI/future alignment:** AI can estimate Taylor Rule parameters that vary over time (the Fed's reaction function has changed over decades) — adaptive policy rule estimation
- **Research connection:** Multi-agent systems can have a dedicated Taylor Rule agent — monitoring inflation and output data to predict central bank decisions

#### Concept: Fiscal Multiplier
- **What it means:** The change in output resulting from a change in government spending — multiplier > 1 means spending generates more than $1 of output per $1 spent
- **Alpha Stack application:** **Fiscal policy impact on currencies** — fiscal stimulus (high multiplier) → higher growth → higher rates → currency appreciation. The system estimates fiscal multipliers for different countries to assess the currency impact of fiscal announcements
- **AI/future alignment:** AI can estimate country-specific, time-varying fiscal multipliers from historical data — more nuanced than one-size-fits-all assumptions
- **Research connection:** Multi-agent systems can model fiscal policy as an exogenous shock to the economy — agents adjust their predictions based on estimated multiplier effects

#### Concept: Quantitative Easing (QE) and Unconventional Monetary Policy
- **What it means:** Central bank purchasing long-term assets when short-term rates hit zero — expands money supply and lowers long-term rates
- **Alpha Stack application:** **QE impact modeling** — QE announcements cause predictable currency effects (typically depreciation of the QE currency). The system monitors central bank balance sheets and QE schedules as trading signals
- **AI/future alignment:** AI can process central bank communications to detect QE policy shifts before official announcements — parsing language changes in FOMC/MPC statements
- **Research connection:** Multi-agent systems can have central bank communication analysis agents — using NLP to extract policy signals from central bank texts

---

# UNIT 6: ECO 206 — Economics of Microfinance
**Grade: C (55%) | Alpha Stack Relevance: ⭐⭐**

## Course Overview
Microfinance institutions, financial inclusion, mobile money, and their role in developing economies.

---

### Topic 6.1: Financial Inclusion and Access

#### Concept: Financial Inclusion Metrics
- **What it means:** Measures of access to financial services — account ownership, savings rates, credit access, insurance coverage
- **Alpha Stack application:** **Mobile money adoption as economic indicator** — M-Pesa penetration in Kenya, mobile money usage in Nigeria/Ghana — these are real-time economic activity indicators. The system can use mobile money transaction volumes as a proxy for economic activity
- **AI/future alignment:** AI can process mobile money transaction data (anonymized, aggregated) to construct real-time economic activity indices — faster than GDP data
- **Research connection:** Multi-agent systems can have mobile money monitoring agents — tracking transaction volumes as leading indicators for currency activity

#### Concept: Agency Banking and Digital Financial Services
- **What it means:** Using retail agents (shops, kiosks) to provide banking services — extends financial access beyond bank branches
- **Alpha Stack application:** **Financial infrastructure as development signal** — countries expanding digital financial infrastructure see improved monetary transmission and economic efficiency — medium-term positive for the currency
- **AI/future alignment:** AI can track digital financial infrastructure expansion from satellite data (agent locations, mobile network coverage) — development tracking at scale
- **Research connection:** Multi-agent systems can integrate development data into long-term currency allocation models

---

### Topic 6.2: Microfinance Institutions (MFIs)

#### Concept: Group Lending and Joint Liability
- **What it means:** Grameen model — groups of borrowers are jointly liable for each other's loans, using social pressure as collateral
- **Alpha Stack application:** **Social collateral as risk model analogy** — the group lending model is analogous to portfolio diversification — joint liability reduces individual default risk, just as diversification reduces individual asset risk
- **AI/future alignment:** AI can model social network effects in financial markets — herding behavior, information cascades, and contagion follow similar dynamics to group lending
- **Research connection:** Multi-agent systems model agent interactions analogous to group dynamics — agents can "co-sign" each other's positions (correlated risk management)

#### Concept: Interest Rate Sustainability
- **What it means:** MFIs must charge high interest rates to cover costs — debate about whether high rates exploit the poor or reflect true costs
- **Alpha Stack application:** **Cost of capital in emerging markets** — the high cost of microfinance reflects the true risk and operating costs in EM. This informs the system's cost-of-capital assumptions for EM currency carry trades
- **AI/future alignment:** AI can model the relationship between financial inclusion costs and economic development — how reducing transaction costs affects growth and currency stability
- **Research connection:** Multi-agent systems can model market friction costs — each transaction has a cost that affects optimal strategy

---

### Topic 6.3: Mobile Money and Digital Currencies

#### Concept: Mobile Money Ecosystems (M-Pesa, etc.)
- **What it means:** Mobile phone-based money transfer and payment systems — dominant in East Africa
- **Alpha Stack application:** **Mobile money as economic pulse** — M-Pesa transaction data provides real-time economic activity signals for Kenya. The system can monitor aggregated, anonymized transaction volumes as a leading indicator for KES
- **AI/future alignment:** AI can build real-time economic activity indices from mobile money data — complementing traditional indicators (GDP, CPI) that are published with lags
- **Research connection:** Multi-agent systems can process alternative data sources (mobile money, satellite, social media) alongside traditional market data

#### Concept: Central Bank Digital Currencies (CBDCs)
- **What it means:** Digital versions of national currencies issued by central banks — Nigeria's eNaira, Ghana's eCedi
- **Alpha Stack application:** **CBDC impact on monetary transmission** — CBDCs change how monetary policy transmits to the economy. If CBDCs increase velocity of money, inflation dynamics change. The system must model CBDC effects on currency value
- **AI/future alignment:** AI can monitor CBDC adoption rates and model their macroeconomic effects — a new dimension of monetary policy analysis
- **Research connection:** Quantum computing (Research 06) can model complex monetary systems with CBDCs — agent-based simulations of digital currency ecosystems

---

# UNIT 7: ECO 209 — Money and Banking
**Grade: B (65%) | Alpha Stack Relevance: ⭐⭐⭐⭐⭐**

## Course Overview
The financial system — money creation, banking operations, central banking, monetary policy transmission, and financial markets.

---

### Topic 7.1: The Nature and Functions of Money

#### Concept: Functions of Money (Medium of Exchange, Unit of Account, Store of Value)
- **What it means:** Money serves three functions — facilitates transactions (medium of exchange), provides a common measure of value (unit of account), and preserves purchasing power over time (store of value)
- **Alpha Stack application:** **Currency strength assessment** — a currency that fails any of these functions depreciates. Hyperinflation destroys the store of value function. The system monitors inflation expectations, currency substitution, and black market premiums as indicators of monetary dysfunction
- **AI/future alignment:** AI can monitor cryptocurrency adoption as an indicator of fiat currency dysfunction — when people flee to crypto, it signals loss of confidence in the local currency
- **Research connection:** Multi-agent systems can model the competition between fiat currencies, crypto, and CBDCs as a medium of exchange — evolutionary dynamics

#### Concept: Money Supply Measures (M0, M1, M2, M3)
- **What it means:** Different measures of money — M0 (base money/reserves), M1 (cash + demand deposits), M2 (M1 + savings + time deposits), M3 (M2 + large deposits + money market funds)
- **Alpha Stack application:** **Money supply growth as currency signal** — rapid money supply growth relative to GDP growth signals future inflation → currency depreciation. The system tracks M2 growth rates across countries as a medium-term currency signal
- **AI/future alignment:** AI can process money supply data in real-time and model its lagged effect on inflation and exchange rates — dynamic monetary models
- **Research connection:** Multi-agent systems can have dedicated money supply monitoring agents — tracking central bank balance sheets and banking system credit creation

#### Concept: Quantity Theory of Money (MV = PQ)
- **What it means:** Money supply × Velocity of money = Price level × Real output — if V and Q are stable, money supply growth causes proportional inflation
- **Alpha Stack application:** **Inflation forecasting model** — the system uses MV=PQ to forecast inflation: if money supply grows faster than real output, inflation will follow → currency depreciation. Velocity estimation is key
- **AI/future alignment:** AI can estimate velocity of money from high-frequency transaction data — solving the key weakness of the quantity theory (unstable velocity)
- **Research connection:** Quantum computing (Research 06) can solve dynamic versions of MV=PQ with endogenous velocity — more realistic monetary models

---

### Topic 7.2: Banking Operations and Money Creation

#### Concept: Fractional Reserve Banking and Money Multiplier
- **What it means:** Banks hold only a fraction of deposits as reserves and lend the rest — creating money through the money multiplier (1/reserve ratio)
- **Alpha Stack application:** **Credit creation cycle** — the money multiplier drives the credit cycle — expansion (banks lending freely, money supply growing) and contraction (banks tightening, money supply shrinking). The system monitors bank lending standards and credit growth as leading indicators
- **AI/future alignment:** AI can model the money multiplier in real-time using central bank reserve data and bank lending surveys — credit cycle tracking
- **Research connection:** Multi-agent systems can model the banking sector as a multi-agent system — banks as agents with lending decisions that collectively determine money supply

#### Concept: Bank Balance Sheets and Capital Adequacy
- **What it means:** Assets (loans, reserves) = Liabilities (deposits) + Equity (capital). Capital adequacy ratio = capital / risk-weighted assets
- **Alpha Stack application:** **Banking sector health as systemic risk indicator** — weak banking sector (low capital adequacy, high NPLs) signals systemic risk → currency risk. The system monitors banking sector health indicators for countries in the portfolio
- **AI/future alignment:** AI can process bank financial statements and regulatory filings to construct real-time banking sector health indices — early warning for banking crises
- **Research connection:** Multi-agent systems can model banking sector contagion — one bank's failure affecting others through interbank lending networks

#### Concept: Non-Performing Loans (NPLs)
- **What it means:** Loans where borrowers have stopped making payments — indicator of banking sector stress
- **Alpha Stack application:** **NPL ratio as crisis predictor** — rising NPLs predict banking stress and potential currency crises. The system monitors NPL ratios for EM countries as a risk indicator
- **AI/future alignment:** AI can predict NPL formation from borrower-level data (where available) and macro conditions — early warning for credit deterioration
- **Research connection:** Multi-agent systems can model credit risk propagation — NPL formation in one sector affecting others through supply chain linkages

---

### Topic 7.3: Central Banking

#### Concept: Central Bank Functions and Independence
- **What it means:** Central banks conduct monetary policy, regulate banks, and act as lender of last resort. Independence from political pressure is crucial for credibility
- **Alpha Stack application:** **Central bank credibility as currency anchor** — independent central banks with clear mandates (inflation targeting) anchor inflation expectations → stable currencies. The system monitors central bank independence indicators and policy credibility
- **AI/future alignment:** AI can score central bank credibility from policy consistency, communication clarity, and inflation target adherence — quantitative credibility metrics
- **Research connection:** Multi-agent systems can have dedicated central bank analysis agents — monitoring policy decisions and communication for credibility signals

#### Concept: Monetary Policy Tools (Open Market Operations, Discount Rate, Reserve Requirements)
- **What it means:** OMOs (buying/selling government bonds), discount rate (rate at which banks borrow from central bank), reserve requirements (minimum reserves banks must hold)
- **Alpha Stack application:** **Policy tool impact on currencies** — each tool affects the economy and currencies differently. OMOs are the most common and predictable — the system tracks open market operations and their market impact
- **AI/future alignment:** AI can process central bank operation data in real-time — detecting policy shifts from operation patterns before they're explicitly communicated
- **Research connection:** Multi-agent systems can model the monetary policy transmission mechanism — from policy tool → money market rates → bank lending → economic activity → exchange rates

#### Concept: Inflation Targeting Framework
- **What it means:** Central bank commits to achieving a specific inflation target (typically 2%) — uses interest rate adjustments to keep inflation on target
- **Alpha Stack application:** **Inflation surprise trading** — when inflation deviates from target, the system predicts the central bank's response (rate change) and trades the resulting currency move. Inflation surprises (actual vs. forecast) are high-impact events
- **AI/future alignment:** AI can model the central bank's reaction function — predicting not just IF they'll change rates, but by how much, based on the inflation deviation from target
- **Research connection:** Multi-agent systems can have inflation forecasting agents — predicting CPI releases and the central bank's response

---

### Topic 7.4: Monetary Policy Transmission

#### Concept: Interest Rate Channel
- **What it means:** Central bank rate changes → market rates → investment/consumption decisions → economic activity
- **Alpha Stack application:** **Rate decision trading** — the most direct channel. When central banks change rates, the system trades the immediate currency impact (higher rates → currency appreciation) and the second-order effects (slower growth → eventual currency weakness)
- **AI/future alignment:** AI can model the transmission lag from rate changes to economic activity — the system can predict when rate changes will start affecting the real economy
- **Research connection:** Multi-agent systems can model the interest rate channel as a causal chain — each link in the chain monitored by a specialized agent

#### Concept: Exchange Rate Channel
- **What it means:** Monetary policy → interest rate differential → capital flows → exchange rate → net exports → economic activity
- **Alpha Stack application:** **Direct forex signal** — this is THE channel for forex trading. Interest rate differentials drive capital flows, which drive exchange rates. The system monitors rate differentials, capital flow data, and trade balances
- **AI/future alignment:** AI can model the exchange rate channel with real-time capital flow data (bank settlements, portfolio flows) — faster than quarterly balance of payments data
- **Research connection:** Multi-agent systems can have dedicated capital flow monitoring agents — tracking institutional investor positioning and cross-border flows

#### Concept: Credit Channel and Bank Lending Channel
- **What it means:** Monetary policy → bank reserves → bank lending capacity → credit availability → economic activity
- **Alpha Stack application:** **Credit growth signals** — the credit channel is often more powerful than the interest rate channel in developing economies. The system monitors bank lending surveys and credit growth data as leading economic indicators
- **AI/future alignment:** AI can process bank lending data and credit conditions surveys in real-time — constructing credit impulse indicators for each economy
- **Research connection:** Multi-agent systems can model the credit channel as a network — banks as nodes, interbank lending as edges, with policy changes propagating through the network

---

### Topic 7.5: Financial Markets and Instruments

#### Concept: Money Markets and Capital Markets
- **What it means:** Money markets trade short-term instruments (T-bills, repos, commercial paper); capital markets trade long-term instruments (bonds, equities)
- **Alpha Stack application:** **Yield curve analysis** — the money market (short end) reflects current monetary policy; the capital market (long end) reflects growth and inflation expectations. The yield curve shape (normal, flat, inverted) is a powerful economic signal
- **AI/future alignment:** AI can model the entire yield curve as a dynamic system — predicting curve shape changes from macro data and central bank signals
- **Research connection:** Multi-agent systems can have yield curve agents — specializing in different maturities and combining signals for curve trades

#### Concept: Foreign Exchange Markets
- **What it means:** The market for trading currencies — largest financial market in the world ($7.5T+ daily volume). Includes spot, forward, swap, and options markets
- **Alpha Stack application:** **CORE ALPHA STACK DOMAIN** — this IS the system's market. Understanding forex market microstructure (dealer networks, ECN/STP execution, bid-ask spreads, liquidity pools) is fundamental to the system's execution quality
- **AI/future alignment:** AI is transforming forex markets — algorithmic trading now accounts for 70%+ of forex volume. AI-powered execution (smart order routing, optimal execution algorithms) is the frontier
- **Research connection:** Multi-agent systems (Research 03) are the natural architecture for forex trading — multiple specialized agents (technical, fundamental, sentiment, flow) collaborating in real-time

#### Concept: Derivatives Markets (Forwards, Futures, Options, Swaps)
- **What it means:** Financial contracts whose value derives from an underlying asset — used for hedging and speculation
- **Alpha Stack application:** **Hedging and leverage tools** — the system uses forex forwards for hedging currency risk, options for tail risk protection, and swaps for carry trade execution. Understanding derivatives pricing is essential
- **AI/future alignment:** AI can price complex derivatives in real-time — enabling dynamic hedging strategies that adjust continuously rather than at fixed intervals
- **Research connection:** Quantum computing (Research 06) offers quadratic speedup for Monte Carlo option pricing — the first practical quantum advantage in finance (expected 2028-2030)

---

### Topic 7.6: Banking Crises and Financial Stability

#### Concept: Bank Runs and Systemic Risk
- **What it means:** Self-fulfilling crisis — depositors withdraw because they fear others will withdraw. Systemic risk = risk that the failure of one institution triggers failures across the system
- **Alpha Stack application:** **Crisis detection and trading** — the system monitors indicators of banking stress (interbank rates, CDS spreads, deposit outflows) for early crisis detection. During crises, safe-haven flows (to USD, CHF, JPY) create trading opportunities
- **AI/future alignment:** AI can detect early signs of banking stress from network analysis of interbank lending patterns — crisis prediction before it becomes obvious
- **Research connection:** Multi-agent systems can model bank runs as coordination games — agents (depositors) deciding whether to withdraw based on their beliefs about others' actions

#### Concept: Moral Hazard and Too Big to Fail
- **What it means:** Banks take excessive risks because they expect to be bailed out. "Too big to fail" institutions have implicit government guarantees
- **Alpha Stack application:** **Implicit guarantee pricing** — TBTF banks have lower funding costs due to implicit guarantees. The system can trade the spread between TBTF and non-TBTF bank bonds as a measure of moral hazard pricing
- **AI/future alignment:** AI can identify TBTF institutions from network centrality measures — mapping the financial network to identify systemically important nodes
- **Research connection:** Multi-agent systems model moral hazard as a principal-agent problem — regulators (principals) trying to incentivize prudent behavior from banks (agents)

---

# UNIT 8: ECO 210 — Introduction to Quantitative Methods
**Grade: B (60%) | Alpha Stack Relevance: ⭐⭐⭐⭐**

## Course Overview
Mathematical and statistical tools for economic analysis — matrix algebra, optimization, difference equations, and basic econometrics.

---

### Topic 8.1: Matrix Algebra for Economics

#### Concept: Matrix Operations (Addition, Multiplication, Inversion)
- **What it means:** Matrices are rectangular arrays of numbers — matrix multiplication combines rows and columns; inversion finds the matrix equivalent of division
- **Alpha Stack application:** **Portfolio mathematics** — the covariance matrix of asset returns is the foundation of portfolio optimization. Matrix inversion is required for computing optimal portfolio weights (Markowitz: w = Σ⁻¹μ)
- **AI/future alignment:** AI frameworks (PyTorch, TensorFlow) are built on matrix operations — GPU-accelerated matrix multiplication is the computational backbone of deep learning
- **Research connection:** Quantum computing (Research 06) offers exponential speedup for certain matrix operations — quantum linear algebra algorithms (HHL) for large covariance matrices

#### Concept: Eigenvalues and Eigenvectors
- **What it means:** For a matrix A, if Av = λv, then λ is an eigenvalue and v is an eigenvector — they reveal the "natural directions" of a linear transformation
- **Alpha Stack application:** **Principal Component Analysis (PCA)** — eigenvalue decomposition of the covariance matrix identifies the principal components of return variation. The first PC often captures "market risk," subsequent PCs capture sector/style factors
- **AI/future alignment:** AI uses eigendecomposition for dimensionality reduction — compressing high-dimensional market data into its most informative components
- **Research connection:** Quantum eigendecomposition (quantum phase estimation) can find eigenvalues exponentially faster — applicable to large-scale covariance matrix analysis

#### Concept: Determinants
- **What it means:** A scalar value computed from a square matrix — indicates whether the matrix is invertible and the scaling factor of the linear transformation
- **Alpha Stack application:** **Portfolio diversification measure** — the determinant of the correlation matrix measures overall diversification. A determinant near 1 means assets are uncorrelated (good diversification); near 0 means highly correlated (poor diversification)
- **AI/future alignment:** AI can compute determinants of large matrices efficiently — enabling real-time diversification monitoring for large portfolios
- **Research connection:** Quantum computing can compute determinants of large matrices faster than classical methods — enabling portfolio diversification analysis at scale

---

### Topic 8.2: Optimization Methods

#### Concept: Unconstrained Optimization (First and Second Order Conditions)
- **What it means:** Finding maximum or minimum of a function — first order: f'(x) = 0; second order: f''(x) determines if it's a max (negative) or min (positive)
- **Alpha Stack application:** **Strategy parameter optimization** — finding the optimal lookback period, threshold, or position size by maximizing a performance metric (Sharpe ratio, total return). First order conditions find candidates; second order confirms they're maxima
- **AI/future alignment:** AI training IS optimization — gradient descent is the workhorse. Understanding first/second order conditions helps diagnose training issues (saddle points, local minima)
- **Research connection:** Quantum annealing (Research 06) solves optimization problems by finding the global minimum of complex objective functions — avoiding local minima that trap classical optimizers

#### Concept: Constrained Optimization (Lagrange Multipliers)
- **What it means:** Optimizing a function subject to constraints — Lagrange multipliers measure how much the optimal value would improve if the constraint were relaxed by one unit
- **Alpha Stack application:** **Portfolio optimization with constraints** — maximizing expected return subject to: (1) budget constraint (weights sum to 1), (2) no short-selling constraint, (3) sector exposure limits, (4) maximum position size. Lagrange multipliers show the "shadow price" of each constraint
- **AI/future alignment:** AI uses constrained optimization for fair ML, safe RL, and policy compliance — ensuring AI systems respect operational constraints
- **Research connection:** Quantum computing (Research 06) can solve constrained optimization problems with many constraints more efficiently — QAOA (Quantum Approximate Optimization Algorithm) for combinatorial portfolio selection

#### Concept: Linear Programming
- **What it means:** Optimizing a linear objective function subject to linear constraints — solved by the simplex method or interior point methods
- **Alpha Stack application:** **Trade allocation optimization** — allocating capital across strategies subject to linear constraints (max exposure per pair, max total leverage, min diversification). LP finds the optimal allocation
- **AI/future alignment:** AI can solve large-scale LPs in real-time — enabling dynamic trade allocation that adjusts to changing market conditions
- **Research connection:** Quantum computing offers potential speedup for LP through quantum interior point methods — larger problems solvable in real-time

---

### Topic 8.3: Difference Equations

#### Concept: First-Order Linear Difference Equations
- **What it means:** Equations of the form yₜ = a·yₜ₋₁ + b — describes how a variable evolves over discrete time periods
- **Alpha Stack application:** **Mean reversion modeling** — if a = |value| < 1, the series is mean-reverting (converges to b/(1-a)). This models mean-reverting price behavior — the system detects mean-reverting pairs and trades the reversion
- **AI/future alignment:** AI can estimate the reversion speed (parameter a) and equilibrium level (b/(1-a)) from data — adaptive mean reversion models
- **Research connection:** Multi-agent systems can model price dynamics as difference equations — each agent's trading affecting the price evolution

#### Concept: Second-Order Linear Difference Equations
- **What it means:** Equations of the form yₜ = a·yₜ₋₁ + b·yₜ₋₂ + c — can generate oscillatory behavior (cycles)
- **Alpha Stack application:** **Business cycle modeling** — economic cycles can be modeled as second-order difference equations. The system can detect cycle phase and amplitude from the estimated parameters
- **AI/future alignment:** AI can fit higher-order difference equations to capture complex cyclical dynamics in economic and market data
- **Research connection:** Quantum computing can solve systems of difference equations with many interacting variables — multi-country business cycle models

#### Concept: Systems of Difference Equations
- **What it means:** Multiple interrelated difference equations — e.g., two variables each evolving based on both variables' past values
- **Alpha Stack application:** **Multi-asset dynamics** — modeling the joint evolution of multiple currency pairs as a system of difference equations. Cross-pair interactions (e.g., EUR/USD and GBP/USD) are captured by off-diagonal terms
- **AI/future alignment:** AI can learn systems of difference equations from data — vector autoregression (VAR) and its non-linear extensions
- **Research connection:** Multi-agent systems naturally produce systems of equations — each agent's behavior is an equation, market dynamics are the system

---

### Topic 8.4: Basic Econometrics

#### Concept: Ordinary Least Squares (OLS) Estimation
- **What it means:** Estimating regression coefficients by minimizing the sum of squared residuals — the workhorse of empirical economics
- **Alpha Stack application:** **Factor model estimation** — OLS estimates factor exposures (betas) and factor premiums (alpha). The system uses OLS to estimate how much of a currency's return is explained by carry, momentum, and value factors
- **AI/future alignment:** AI extends OLS to non-linear models while maintaining interpretability — generalized additive models, attention-based factor models
- **Research connection:** Multi-agent systems can use OLS for agent performance attribution — decomposing returns into factor contributions

#### Concept: Gauss-Markov Assumptions and OLS Properties
- **What it means:** OLS is BLUE (Best Linear Unbiased Estimator) when: (1) linear in parameters, (2) random sampling, (3) no perfect multicollinearity, (4) zero conditional mean (E[ε|X] = 0), (5) homoskedasticity
- **Alpha Stack application:** **Model diagnostics** — the system must verify Gauss-Markov assumptions when estimating factor models. Violations (heteroskedasticity, autocorrelation, endogeneity) bias coefficient estimates and invalidate statistical tests
- **AI/future alignment:** AI can detect assumption violations automatically — using residual tests, heteroskedasticity tests, and autocorrelation tests as part of the model validation pipeline
- **Research connection:** Multi-agent systems can have dedicated model validation agents — testing assumptions and flagging models that violate them

#### Concept: Hypothesis Testing in Regression (t-tests, F-tests)
- **What it means:** Testing whether individual coefficients are significant (t-test) or whether the model as a whole is significant (F-test)
- **Alpha Stack application:** **Factor significance testing** — the system tests whether each factor (carry, momentum, value) has a statistically significant premium. Insignificant factors are dropped from the model
- **AI/future alignment:** AI can run thousands of factor tests with proper multiple testing correction — automated factor discovery with statistical rigor
- **Research connection:** Multi-agent systems can have factor research agents — each testing different factor hypotheses, with a meta-agent aggregating results

---

# UNIT 9: STA 241 — Probability and Distribution Models
**Grade: A (77%) | Alpha Stack Relevance: ⭐⭐⭐⭐⭐**

## Course Overview
Rigorous probability theory — random variables, distribution families, moment generating functions, joint distributions, and limit theorems. **This is Valentine's strongest unit — direct foundation for risk modeling.**

---

### Topic 9.1: Random Variables and Their Distributions

#### Concept: Probability Mass Functions (PMF) and Probability Density Functions (PDF)
- **What it means:** PMF gives probabilities for discrete random variables; PDF gives probability densities for continuous random variables (probability = area under curve)
- **Alpha Stack application:** **Return distribution modeling** — the system models returns as continuous random variables with a PDF. The shape of the return PDF determines risk measures (VaR, CVaR) and option prices. Non-normal PDFs (fat-tailed, skewed) require specialized distributions
- **AI/future alignment:** AI can learn the return PDF directly from data using normalizing flows or diffusion models — no parametric assumptions needed
- **Research connection:** Quantum computing (Research 06) can sample from complex PDFs more efficiently — quantum Monte Carlo for risk calculations

#### Concept: Cumulative Distribution Function (CDF)
- **What it means:** P(X ≤ x) — the probability that a random variable is less than or equal to a value
- **Alpha Stack application:** **Value at Risk (VaR)** — VaR is literally the inverse CDF at a given confidence level. VaR₉₅% = CDF⁻¹(0.05) for the loss distribution. The system computes VaR from the estimated return CDF
- **AI/future alignment:** AI can estimate the CDF non-parametrically using empirical distribution functions or kernel density estimation — more accurate VaR estimates
- **Research connection:** Quantum computing can compute CDFs of complex distributions faster — quantum amplitude estimation for risk measures

#### Concept: Expected Value E[X] and Variance Var(X)
- **What it means:** E[X] = Σx·P(x) or ∫x·f(x)dx (probability-weighted average); Var(X) = E[(X - E[X])²] (spread around mean)
- **Alpha Stack application:** **Trade evaluation** — every trade has an expected value (probability-weighted P&L) and variance (uncertainty). The system only takes trades with positive EV and sizes positions based on the EV/variance ratio (Kelly criterion)
- **AI/future alignment:** AI can estimate EV and variance conditional on market state — dynamic trade evaluation that adapts to changing conditions
- **Research connection:** Multi-agent systems aggregate agent EV estimates — consensus estimates are more robust than individual agent estimates

#### Concept: Moment Generating Functions (MGF)
- **What it means:** M(t) = E[e^(tX)] — uniquely determines the distribution and generates moments (mean, variance, skewness, kurtosis) by differentiation
- **Alpha Stack application:** **Distribution characterization** — MGFs allow the system to compute all moments of the return distribution from a single function. This is useful for complex distributions where direct moment computation is difficult
- **AI/future alignment:** AI can learn the MGF from data — characterizing the full distribution from its generating function
- **Research connection:** Quantum computing can compute MGFs for quantum states — enabling quantum advantage in distribution characterization

---

### Topic 9.2: Important Distribution Families

#### Concept: Bernoulli and Binomial Distributions
- **What it means:** Bernoulli: single trial with success probability p; Binomial: number of successes in n independent Bernoulli trials
- **Alpha Stack application:** **Trade outcome modeling** — each trade is a Bernoulli trial (win/loss). n trades follow a binomial distribution. The system uses the binomial to compute the probability of k wins in n trades and to set confidence intervals on win rates
- **AI/future alignment:** AI can model non-stationary Bernoulli processes — where the win probability changes over time (regime-dependent)
- **Research connection:** Multi-agent systems model each agent's trades as Bernoulli trials — the meta-agent evaluates agent reliability using binomial tests

#### Concept: Poisson Distribution
- **What it means:** Models the number of events in a fixed interval — parameter λ = average rate. Used for rare events
- **Alpha Stack application:** **Trade signal frequency modeling** — the number of trading signals per day may follow a Poisson distribution. Also models the arrival of large price jumps (rare events) — essential for jump-diffusion price models
- **AI/future alignment:** AI can model time-varying Poisson rates — the signal arrival rate changes with market volatility (more signals in volatile markets)
- **Research connection:** Multi-agent systems can model agent signal generation as Poisson processes — coordinating agent activity to avoid signal congestion

#### Concept: Normal (Gaussian) Distribution
- **What it means:** The bell curve — characterized by mean μ and variance σ². Central limit theorem makes it ubiquitous
- **Alpha Stack application:** **Baseline return model** — the normal distribution is the starting point for return modeling. While real returns have fat tails, the normal provides a baseline that can be adjusted. Many risk models (VaR, portfolio optimization) assume normality
- **AI/future alignment:** AI models can test for normality automatically and switch to more appropriate distributions (Student-t, skewed-t) when normality is rejected — adaptive distribution selection
- **Research connection:** Quantum computing (Research 06) can generate normal random numbers more efficiently — quantum random number generators provide true randomness

#### Concept: Exponential Distribution
- **What it means:** Models time between events in a Poisson process — memoryless property (future doesn't depend on past)
- **Alpha Stack application:** **Time between trades/signals** — the exponential distribution models the waiting time between trading signals or between large price moves. The memoryless property means each moment is equally likely to see a signal, regardless of how long you've waited
- **AI/future alignment:** AI can model non-exponential waiting times — recognizing that market events cluster (volatility clustering violates the memoryless property)
- **Research connection:** Multi-agent systems can model inter-agent communication timing as exponential processes — network latency and message arrival

#### Concept: Gamma and Chi-Square Distributions
- **What it means:** Gamma generalizes the exponential (sum of exponentials); chi-square is a special case (sum of squared normals). Both model waiting times and variance
- **Alpha Stack application:** **Volatility modeling** — the gamma distribution models the distribution of variance estimates. Chi-square distribution is used in hypothesis testing (chi-square test for independence of returns)
- **AI/future alignment:** AI uses chi-square tests for feature selection — identifying which features are independent of the target variable
- **Research connection:** Quantum computing can sample from gamma and chi-square distributions efficiently — quantum Monte Carlo for variance-based risk measures

#### Concept: Student's t-Distribution
- **What it means:** Like the normal but with heavier tails — parameterized by degrees of freedom (ν). As ν → ∞, converges to normal
- **Alpha Stack application:** **Fat-tailed return modeling** — financial returns have heavier tails than the normal distribution. The Student-t with 3-5 degrees of freedom is a better model for returns, producing more realistic VaR estimates
- **AI/future alignment:** AI can estimate the optimal degrees of freedom from data — adaptive tail thickness modeling. Bayesian AI models use the t-distribution as a robust likelihood function
- **Research connection:** Quantum computing can sample from Student-t distributions efficiently — quantum Monte Carlo for fat-tailed risk models

#### Concept: Beta Distribution
- **What it means:** Distribution on [0,1] — models probabilities and proportions. Parameterized by α and β
- **Alpha Stack application:** **Win rate estimation** — the beta distribution is the conjugate prior for the Bernoulli/binomial. It models uncertainty in the win rate: Beta(α wins + 1, β losses + 1). The system uses Bayesian updating with the beta distribution to track evolving win rates
- **AI/future alignment:** AI uses the beta distribution in Bayesian optimization — for hyperparameter tuning of trading strategies
- **Research connection:** Multi-agent systems can use beta distributions to model agent reliability — updating beliefs about each agent's competence as new trade results arrive

---

### Topic 9.3: Joint Distributions and Dependence

#### Concept: Joint Probability Distributions
- **What it means:** Distribution of two or more random variables simultaneously — f(x,y) describes the probability of X=x AND Y=y together
- **Alpha Stack application:** **Multi-asset return modeling** — the joint distribution of EUR/USD and GBP/USD returns captures their dependence structure. Joint distributions enable computing conditional probabilities (probability of GBP/USD decline given EUR/USD decline)
- **AI/future alignment:** AI can learn complex joint distributions using copulas, normalizing flows, or generative adversarial networks — capturing non-linear dependencies between assets
- **Research connection:** Quantum computing can represent joint distributions of many variables using quantum states — exponential compression of high-dimensional distributions

#### Concept: Marginal and Conditional Distributions
- **What it means:** Marginal: distribution of one variable ignoring others. Conditional: distribution of one variable given specific values of others
- **Alpha Stack application:** **Conditional risk modeling** — the conditional distribution of returns given volatility regime (high/low) provides more accurate risk estimates than the unconditional distribution. The system conditions on market state for better predictions
- **AI/future alignment:** AI naturally computes conditional distributions — P(return | features) is the fundamental prediction. Transformer attention mechanisms weight different conditions dynamically
- **Research connection:** Multi-agent systems use conditional distributions for agent communication — Agent A's prediction is conditioned on Agent B's signal

#### Concept: Covariance and Correlation
- **What it means:** Covariance = E[(X-μₓ)(Y-μᵧ)] (linear dependence); Correlation = standardized covariance (dimensionless, -1 to +1)
- **Alpha Stack application:** **Portfolio construction** — the covariance matrix of returns is the input to portfolio optimization. The system tracks time-varying correlations (correlations increase during crises — "correlation breakdown")
- **AI/future alignment:** AI can model time-varying correlations using DCC-GARCH or neural network-based dynamic correlation models — adaptive portfolio construction
- **Research connection:** Quantum computing can compute covariance matrices for large portfolios efficiently — quantum linear algebra for portfolio optimization

#### Concept: Copulas
- **What it means:** Functions that couple marginal distributions to form a joint distribution — separate the dependence structure from the marginal distributions
- **Alpha Stack application:** **Advanced dependence modeling** — copulas capture non-linear dependence (tail dependence) that correlation misses. During crises, assets become more correlated in the tails — copulas model this explicitly. The system uses copulas for more accurate portfolio risk assessment
- **AI/future alignment:** AI can learn copula structures from data — neural copulas that adapt to changing dependence patterns
- **Research connection:** Quantum computing can sample from complex copula distributions efficiently — quantum Monte Carlo for copula-based risk models

---

### Topic 9.4: Limit Theorems

#### Concept: Law of Large Numbers (LLN)
- **What it means:** As sample size increases, the sample mean converges to the population mean. Weak LLN: convergence in probability. Strong LLN: convergence with probability 1
- **Alpha Stack application:** **Backtest reliability** — LLN guarantees that with enough trades, the sample win rate converges to the true win rate. This is why the system requires minimum trade counts before deploying a strategy
- **AI/future alignment:** AI models benefit from LLN — more training data leads to better estimates of true model performance
- **Research connection:** Multi-agent systems benefit from LLN — aggregating predictions from many agents converges to the true expected value

#### Concept: Central Limit Theorem (CLT)
- **What it means:** The sum (or average) of many independent random variables is approximately normally distributed, regardless of the original distribution
- **Alpha Stack application:** **Return aggregation** — daily returns are the sum of many intraday returns → approximately normal by CLT. Monthly returns are the sum of daily returns → even more normal. This justifies normal-based risk models at longer horizons
- **AI/future alignment:** AI exploits CLT for ensemble methods — averaging predictions from many models produces normally distributed errors, enabling confidence intervals
- **Research connection:** Quantum computing can verify CLT convergence for complex, dependent variables — quantum central limit theorems

#### Concept: Convergence in Distribution, Probability, and Almost Surely
- **What it means:** Three modes of convergence — distribution (CDF converges), probability (probability of large deviations goes to zero), almost surely (convergence happens with probability 1)
- **Alpha Stack application:** **Model convergence guarantees** — understanding convergence modes helps assess whether a strategy's performance metrics will stabilize with more data. Almost sure convergence provides the strongest guarantee
- **AI/future alignment:** AI training convergence analysis — understanding whether model parameters converge in probability (SGD guarantees) vs. distribution (Bayesian posterior convergence)
- **Research connection:** Quantum algorithms have different convergence properties than classical — understanding quantum convergence is essential for quantum-enhanced trading systems

---

# UNIT 10: STA 244 — Introduction to Time Series Analysis & Forecasting
**Grade: D (45%) | Alpha Stack Relevance: ⭐⭐⭐⭐⭐**

## Course Overview
**THE MOST DIRECTLY RELEVANT UNIT** — modeling and forecasting time-ordered data. Covers stationarity, ARMA models, seasonal models, and forecasting methods. **This is the mathematical foundation of price prediction.**

---

### Topic 10.1: Time Series Fundamentals

#### Concept: Components of Time Series (Trend, Seasonality, Cyclical, Irregular)
- **What it means:** Any time series can be decomposed into: trend (long-term direction), seasonal (repeating patterns), cyclical (irregular cycles), and irregular (random noise)
- **Alpha Stack application:** **Price decomposition** — the system decomposes price movements into trend (the directional component to trade), seasonal (time-of-day, day-of-week patterns in forex), cyclical (business cycle effects), and noise (to filter out). Trading the trend component while filtering noise is the core strategy
- **AI/future alignment:** AI can perform decomposition using neural network-based methods (STL-NET, transformer decomposition) — more flexible than classical seasonal decomposition
- **Research connection:** Multi-agent systems can have specialized agents for each component — trend agent, seasonality agent, cycle agent — with a meta-agent combining their signals

#### Concept: Stationarity (Strict and Weak)
- **What it means:** A time series is stationary if its statistical properties (mean, variance, autocorrelation) don't change over time. Weak stationarity: constant mean, constant variance, autocorrelation depends only on lag
- **Alpha Stack application:** **Model applicability test** — most time series models (ARMA, ARIMA) require stationarity. The system must test for stationarity (ADF test, KPSS test) and difference the series if non-stationary. Non-stationary returns imply a changing data-generating process
- **AI/future alignment:** AI can detect non-stationarity automatically and adapt — online learning algorithms that track changing distributions
- **Research connection:** Multi-agent systems must handle non-stationarity — agents that detect regime changes (distribution shifts) and signal other agents to adapt

#### Concept: Autocorrelation Function (ACF) and Partial Autocorrelation Function (PACF)
- **What it means:** ACF: correlation between a series and its lagged values. PACF: correlation between a series and its lagged values, controlling for intermediate lags
- **Alpha Stack application:** **Model identification** — ACF and PACF patterns identify the appropriate ARMA model order. ACF decay + PACF cutoff at lag p → AR(p). ACF cutoff at lag q + PACF decay → MA(q). The system uses ACF/PACF to select model specifications
- **AI/future alignment:** AI can compute ACF/PACF for multiple time series simultaneously — automated model identification for hundreds of currency pairs
- **Research connection:** Multi-agent systems can have model identification agents — automatically selecting the best ARMA specification for each currency pair

#### Concept: White Noise and Random Walks
- **What it means:** White noise: uncorrelated, zero-mean, constant variance. Random walk: Pₜ = Pₜ₋₁ + εₜ (today's price = yesterday's price + random shock)
- **Alpha Stack application:** **Efficient market test** — if prices follow a random walk, no trading strategy can consistently profit. The system tests for random walk behavior (variance ratio test, runs test) — rejecting the random walk hypothesis justifies active trading
- **AI/future alignment:** AI can detect subtle departures from random walk behavior that traditional tests miss — non-linear dependencies, regime-specific predictability
- **Research connection:** Multi-agent systems can test for market efficiency in real-time — if the market becomes more efficient (closer to random walk), agents reduce trading frequency

---

### Topic 10.2: ARMA Models

#### Concept: Autoregressive Models AR(p)
- **What it means:** Yₜ = c + φ₁Yₜ₋₁ + φ₂Yₜ₋₂ + ... + φₚYₜ₋ₚ + εₜ — current value depends on p past values plus noise
- **Alpha Stack application:** **Mean reversion signals** — if an AR(1) coefficient φ₁ < 1, the series is mean-reverting. The system estimates AR coefficients for currency pairs — pairs with significant, stable AR(1) coefficients are candidates for mean reversion strategies
- **AI/future alignment:** AI extends AR models to non-linear AR (NAR) using neural networks — capturing complex patterns in price dynamics that linear AR models miss
- **Research connection:** Multi-agent systems can have AR-specialist agents — each estimating AR models for different currency pairs and timeframes

#### Concept: Moving Average Models MA(q)
- **What it means:** Yₜ = c + εₜ + θ₁εₜ₋₁ + θ₂εₜ₋₂ + ... + θqεₜ₋q — current value depends on q past forecast errors plus current noise
- **Alpha Stack application:** **Momentum and correction signals** — MA models capture how past shocks (surprises) affect current prices. Significant MA terms indicate that price shocks have persistent effects — the system trades this persistence
- **AI/future alignment:** AI can estimate non-linear MA models — capturing asymmetric responses to positive vs. negative shocks (leverage effect)
- **Research connection:** Multi-agent systems can model market dynamics as MA processes — each agent's trading creates a "shock" that affects future prices

#### Concept: ARMA(p,q) Models
- **What it means:** Combines AR and MA: Yₜ = c + ΣφᵢYₜ₋ᵢ + εₜ + Σθⱼεₜ₋ⱼ — captures both autoregressive and moving average dynamics
- **Alpha Stack application:** **Comprehensive price modeling** — ARMA models capture the full short-term dynamics of price movements. The system fits ARMA models to returns and uses them for short-term forecasting. Model selection (AIC, BIC) determines optimal p and q
- **AI/future alignment:** AI extends ARMA to ARIMA (with differencing for non-stationary data), SARIMA (seasonal), and ARIMAX (with exogenous variables) — building comprehensive forecasting models
- **Research connection:** Multi-agent systems can have ARMA-modeling agents — each fitting ARMA models to different pairs/timeframes, with the meta-agent combining forecasts

#### Concept: Model Selection (AIC, BIC)
- **What it means:** AIC (Akaike Information Criterion) and BIC (Bayesian Information Criterion) balance model fit vs. complexity — lower is better. BIC penalizes complexity more heavily
- **Alpha Stack application:** **Avoiding overfitting** — the system uses AIC/BIC to select model complexity. A model that fits training data perfectly but has many parameters (low AIC, high BIC) is likely overfit. BIC's stronger penalty favors simpler, more generalizable models
- **AI/future alignment:** AI uses information criteria for model selection in automated machine learning (AutoML) — balancing model complexity and predictive accuracy
- **Research connection:** Multi-agent systems use information criteria for agent selection — simpler agents (fewer parameters) are preferred when their predictive accuracy is similar to complex agents

---

### Topic 10.3: ARIMA Models

#### Concept: Differencing for Stationarity
- **What it means:** If a series is non-stationary (has a trend), differencing (Yₜ - Yₜ₋₁) can make it stationary. First differencing removes linear trends; second differencing removes quadratic trends
- **Alpha Stack application:** **Return calculation** — differencing prices gives returns (the stationary series). The system works with returns (differenced prices) rather than raw prices for all modeling. This is the foundation of quantitative finance
- **AI/future alignment:** AI can automatically determine the order of differencing needed — testing for unit roots and applying the minimum necessary differencing
- **Research connection:** Multi-agent systems standardize on returns (differenced prices) as the common data format — enabling agents to share and compare signals

#### Concept: ARIMA(p,d,q) Models
- **What it means:** ARIMA = AR + I (Integrated/differencing) + MA. Apply ARMA to the d-times differenced series. Handles both non-stationary and stationary data
- **Alpha Stack application:** **Full-cycle price modeling** — ARIMA captures trend (d component), short-term dynamics (AR component), and shock persistence (MA component). The system fits ARIMA models for multi-horizon forecasting — short-term (1-5 periods), medium-term (5-20 periods)
- **AI/future alignment:** AI extends ARIMA to neural ARIMA (combining ARIMA with neural network residuals) — capturing both linear and non-linear patterns
- **Research connection:** Multi-agent systems can have ARIMA-specialist agents — each tuned for different forecasting horizons

#### Concept: Diagnostic Checking (Residual Analysis)
- **What it means:** After fitting an ARIMA model, check if residuals are white noise (no remaining patterns). If not, the model is inadequate
- **Alpha Stack application:** **Model validation** — the system performs Ljung-Box tests on residuals to ensure no remaining autocorrelation. Non-white-noise residuals indicate the model missed patterns — the system iterates on model specification
- **AI/future alignment:** AI can perform comprehensive residual diagnostics automatically — testing for autocorrelation, heteroskedasticity, non-normality, and structural breaks
- **Research connection:** Multi-agent systems have dedicated diagnostic agents — continuously validating model residuals and alerting when models become inadequate

---

### Topic 10.4: Seasonal Models

#### Concept: Seasonal ARIMA (SARIMA)
- **What it means:** ARIMA extended with seasonal terms — captures repeating patterns at fixed intervals (daily, weekly, monthly). Notation: ARIMA(p,d,q)(P,D,Q)ₛ where s is the seasonal period
- **Alpha Stack application:** **Intraday and weekly patterns** — forex markets have strong seasonal patterns: London-New York overlap (highest volume), Asian session (lowest volume), Monday (direction-setting), Friday (position squaring). SARIMA captures these patterns for intraday trading
- **AI/future alignment:** AI can detect multiple seasonal patterns simultaneously (hourly, daily, weekly, monthly) using multi-seasonal decomposition — more comprehensive than single-season SARIMA
- **Research connection:** Multi-agent systems can have seasonality-specialist agents — trading time-of-day and day-of-week patterns while other agents focus on trend and momentum

#### Concept: Seasonal Decomposition (STL, X-13)
- **What it means:** Separating a time series into trend, seasonal, and remainder components. STL (Seasonal and Trend decomposition using Loess) is flexible; X-13 is the US Census Bureau's official method
- **Alpha Stack application:** **Signal extraction** — the system decomposes price data to extract the trend component (tradeable) from the seasonal component (predictable but small) and noise (untradeable). This improves signal quality
- **AI/future alignment:** AI can perform decomposition using attention mechanisms — learning which components are most predictive for each market condition
- **Research connection:** Multi-agent systems can decompose market data and distribute components to specialized agents — parallel processing of trend, seasonal, and residual signals

---

### Topic 10.5: Forecasting Methods

#### Concept: Point Forecasts and Prediction Intervals
- **What it means:** Point forecast = single best estimate of future value. Prediction interval = range within which the future value will fall with a given probability
- **Alpha Stack application:** **Trade setup** — the system generates point forecasts for entry/exit targets and prediction intervals for stop-loss and take-profit levels. A 95% prediction interval gives the range of likely price outcomes — wider intervals mean more uncertainty and smaller position sizes
- **AI/future alignment:** AI naturally produces prediction intervals through Bayesian methods or quantile regression — uncertainty-aware forecasting
- **Research connection:** Multi-agent systems aggregate agent forecasts into consensus prediction intervals — combining individual uncertainty estimates for more robust intervals

#### Concept: Forecast Accuracy Metrics (MAE, RMSE, MAPE)
- **What it means:** MAE = mean absolute error; RMSE = root mean squared error (penalizes large errors); MAPE = mean absolute percentage error (scale-independent)
- **Alpha Stack application:** **Model evaluation** — the system tracks forecast accuracy using these metrics. RMSE is preferred for trading (large errors are costly). Models with degrading accuracy are automatically flagged for re-estimation
- **AI/future alignment:** AI uses custom loss functions that weight errors by their trading cost — not all forecast errors are equally expensive
- **Research connection:** Multi-agent systems rank agents by forecast accuracy — higher-accuracy agents receive more capital allocation

#### Concept: Exponential Smoothing Methods (SES, Holt's, Holt-Winters')
- **What it means:** SES (Simple Exponential Smoothing) for no-trend data; Holt's for trend data; Holt-Winters' for trend + seasonality. Weighted averages with exponentially decreasing weights
- **Alpha Stack application:** **Adaptive forecasting** — exponential smoothing adapts to changing conditions (recent data weighted more heavily). The system uses Holt-Winters' for intraday price forecasting — capturing both trend and time-of-day patterns
- **AI/future alignment:** AI extends exponential smoothing through attention mechanisms — learning optimal weighting patterns rather than assuming exponential decay
- **Research connection:** Multi-agent systems can use exponential smoothing for agent performance tracking — more recent performance weighted more heavily in agent selection

---

### Topic 10.6: Advanced Topics

#### Concept: Cointegration
- **What it means:** Two non-stationary series are cointegrated if a linear combination of them is stationary — they move together in the long run even if they diverge in the short run
- **Alpha Stack application:** **Pairs trading** — cointegrated currency pairs (e.g., EUR/USD and GBP/USD) have a stable long-run relationship. When they diverge, the system trades the convergence (long the underperformer, short the outperformer). This is one of the most robust trading strategies
- **AI/future alignment:** AI can detect cointegration in high-dimensional settings (many assets) using machine learning methods — more pairs to trade
- **Research connection:** Multi-agent systems can have dedicated pairs trading agents — monitoring cointegrated relationships across hundreds of currency pairs

#### Concept: Vector Autoregression (VAR)
- **What it means:** Multiple time series modeled as a system — each variable depends on its own past AND the past of other variables
- **Alpha Stack application:** **Multi-asset forecasting** — VAR models capture cross-currency dynamics. EUR/USD depends on its own past AND on GBP/USD's past, AND on USD/JPY's past. The system uses VAR for multi-pair forecasting and impulse response analysis
- **AI/future alignment:** AI extends VAR to non-linear VAR (using neural networks) — capturing complex cross-asset dynamics
- **Research connection:** Multi-agent systems can use VAR for agent communication — each agent's forecast incorporates signals from other agents

#### Concept: Volatility Clustering and ARCH/GARCH
- **What it means:** Volatility clusters — high-volatility periods follow high-volatility periods. ARCH models this as variance depending on past squared returns; GARCH adds past variance
- **Alpha Stack application:** **Dynamic risk management** — GARCH models predict future volatility from current conditions. The system uses GARCH forecasts to: (1) adjust position sizes (smaller in high-vol periods), (2) set dynamic stop-losses, (3) price options on currency pairs
- **AI/future alignment:** AI extends GARCH to neural GARCH — capturing non-linear volatility dynamics. Deep learning models can incorporate alternative data (news, sentiment) into volatility forecasts
- **Research connection:** Multi-agent systems can have volatility-specialist agents — providing real-time volatility forecasts to all other agents for risk management

---

# UNIT 11: STA 245 — Social & Economic Statistics for National Planning
**Grade: C (51%) | Alpha Stack Relevance: ⭐⭐⭐**

## Course Overview
Statistical methods for national planning — index numbers, demographic statistics, economic indicators, and data collection for policy.

---

### Topic 11.1: Index Numbers

#### Concept: Price Indices (Laspeyres, Paasche, Fisher)
- **What it means:** Laspeyres: base-period weights; Paasche: current-period weights; Fisher: geometric mean of both (ideal index)
- **Alpha Stack application:** **Inflation measurement** — CPI is a Laspeyres index (overstates inflation), PCE is closer to Paasche. The system monitors both to assess true inflation — different inflation readings lead to different central bank responses and currency impacts
- **AI/future alignment:** AI can construct real-time price indices from online price data — faster than official CPI releases
- **Research connection:** Multi-agent systems can have inflation-monitoring agents — tracking multiple price indices and constructing consensus inflation estimates

#### Concept: Quantity and Value Indices
- **What it means:** Quantity indices measure physical output changes; value indices measure nominal value changes. Real = Value / Price index
- **Alpha Stack application:** **Real vs. nominal analysis** — the system decomposes economic data into real (volume) and price components. Real GDP growth is more informative than nominal for currency analysis — adjusting for inflation reveals true economic momentum
- **AI/future alignment:** AI can decompose economic indicators into real and price components in real-time — more timely than official statistics
- **Research connection:** Multi-agent systems can have real/nominal decomposition agents — providing cleaner economic signals to trading agents

---

### Topic 11.2: Economic Indicators for Planning

#### Concept: National Income Accounting (GDP, GNP, NNP)
- **What it means:** GDP = total value of goods and services produced within a country. GNP = GDP + net income from abroad. NNP = GNP - depreciation
- **Alpha Stack application:** **GDP as currency anchor** — GDP growth is the ultimate measure of economic health. The system monitors GDP releases and GDP proxies (PMI, industrial production) as medium-term currency signals
- **AI/future alignment:** AI can estimate GDP in real-time from alternative data (satellite imagery, electricity consumption, mobile phone activity) — "nowcasting" GDP before official releases
- **Research connection:** Multi-agent systems can have GDP nowcasting agents — providing real-time economic activity estimates to trading agents

#### Concept: Balance of Payments (Current Account, Capital Account, Financial Account)
- **What it means:** Current account = trade balance + income flows. Capital account = capital transfers. Financial account = investment flows. They must sum to zero (with errors and omissions)
- **Alpha Stack application:** **External balance assessment** — current account deficits must be financed by capital inflows. If capital flows dry up, the currency must depreciate to restore balance. The system monitors BOP components as medium-term currency signals
- **AI/future alignment:** AI can process high-frequency trade and capital flow data to estimate BOP in real-time — faster than quarterly official data
- **Research connection:** Multi-agent systems can have BOP monitoring agents — tracking trade flows, portfolio flows, and FDI for each country

#### Concept: Consumer Price Index (CPI) and Inflation Measurement
- **What it means:** CPI measures the average change in prices paid by consumers. Inflation rate = percentage change in CPI
- **Alpha Stack application:** **HIGH-IMPACT EVENT** — CPI releases are among the most market-moving events. The system models CPI expectations (consensus forecast) and trades the surprise (actual - forecast). CPI surprises cause immediate, large currency moves
- **AI/future alignment:** AI can construct real-time CPI estimates from online price data, scanner data, and alternative sources — predicting CPI releases with higher accuracy than economist surveys
- **Research connection:** Multi-agent systems can have CPI forecasting agents — combining multiple data sources and methods for consensus CPI predictions

---

### Topic 11.3: Data Collection and Survey Methods

#### Concept: Survey Design and Sampling
- **What it means:** Designing data collection to be representative, unbiased, and efficient — stratified sampling, cluster sampling, systematic sampling
- **Alpha Stack application:** **Data quality assessment** — the system must assess the quality of economic data it uses. Understanding survey methods helps identify potential biases in CPI, employment, and GDP data
- **AI/future alignment:** AI can design optimal data collection strategies — identifying which data sources provide the most information per unit cost
- **Research connection:** Multi-agent systems can have data quality agents — monitoring incoming data for quality issues and alerting other agents

#### Concept: Non-Sampling Errors and Bias
- **What it means:** Errors not related to sampling — response bias, non-response bias, measurement error, processing errors
- **Alpha Stack application:** **Data revision awareness** — economic data is often revised significantly. The system must account for data revisions and not overreact to initial releases. Understanding non-sampling errors helps assess data reliability
- **AI/future alignment:** AI can track data revisions and learn the revision pattern — adjusting initial estimates based on historical revision behavior
- **Research connection:** Multi-agent systems can have data revision tracking agents — monitoring how initial estimates are revised and updating trading signals accordingly

---

# UNIT 12: STA 246 — Statistical Demography
**Grade: B (66%) | Alpha Stack Relevance: ⭐⭐**

## Course Overview
Population statistics — life tables, fertility, mortality, migration, and population projections. Demographic factors drive long-term economic trends.

---

### Topic 12.1: Population Measurement

#### Concept: Population Growth Rate and Doubling Time
- **What it means:** Growth rate = (births - deaths + net migration) / population. Doubling time ≈ 70 / growth rate (%)
- **Alpha Stack application:** **Long-term economic potential** — countries with growing populations (most of Africa) have growing labor forces and consumer markets → long-term currency potential. Declining populations (Japan, Europe) face deflationary pressures
- **AI/future alignment:** AI can track population dynamics from satellite data (urban expansion), mobile phone data (migration patterns), and social media (demographic sentiment)
- **Research connection:** Multi-agent systems can have demographic trend agents — providing long-term population signals for strategic currency allocation

#### Concept: Age Structure and Dependency Ratios
- **What it means:** Proportion of population in different age groups. Dependency ratio = (youth + elderly) / working-age population
- **Alpha Stack application:** **Demographic dividend trading** — countries with low dependency ratios (large working-age population) have a "demographic dividend" → higher savings, investment, and growth → currency appreciation. The system monitors demographic transitions as long-term signals
- **AI/future alignment:** AI can model the economic impact of demographic transitions — predicting when countries will enter/exit their demographic dividend period
- **Research connection:** Multi-agent systems can model demographic-economic interactions — population structure as a slow-moving macro feature

---

### Topic 12.2: Fertility and Mortality

#### Concept: Total Fertility Rate (TFR) and Life Expectancy
- **What it means:** TFR = average number of children per woman. Life expectancy = average years a person is expected to live
- **Alpha Stack application:** **Development trajectory indicator** — declining TFR and rising life expectancy signal demographic transition → economic development → potential currency appreciation. The system monitors these as long-term development signals
- **AI/future alignment:** AI can track demographic indicators from health data, education data, and satellite imagery — real-time demographic monitoring
- **Research connection:** Multi-agent systems can integrate demographic data into long-term macro models — population as a fundamental economic driver

#### Concept: Life Tables and Survival Functions
- **What it means:** Life tables show the probability of surviving from one age to the next. Survival functions describe the probability of surviving beyond a given age
- **Alpha Stack application:** **Pension and insurance market implications** — countries with aging populations face pension funding challenges → fiscal pressure → currency risk. The system monitors pension system sustainability as a long-term currency risk factor
- **AI/future alignment:** AI can model pension system dynamics under different demographic scenarios — stress-testing fiscal sustainability
- **Research connection:** Quantum computing (Research 06) can solve complex demographic-economic models with many interacting variables — multi-generational fiscal sustainability analysis

---

### Topic 12.3: Migration

#### Concept: Net Migration and Push-Pull Factors
- **What it means:** Net migration = immigration - emigration. Push factors drive people out (poverty, conflict); pull factors attract people in (jobs, safety)
- **Alpha Stack application:** **Migration as economic signal** — net migration patterns signal economic conditions. Brain drain (skilled emigration) is negative for the source country's currency; remittance inflows are positive. The system monitors migration data as a labor market signal
- **AI/future alignment:** AI can track migration patterns from mobile phone data, airline bookings, and social media — real-time migration monitoring
- **Research connection:** Multi-agent systems can have migration-monitoring agents — tracking labor mobility as an economic adjustment mechanism

#### Concept: Urbanization
- **What it means:** Population shift from rural to urban areas — associated with economic development, productivity growth, and structural transformation
- **Alpha Stack application:** **Urbanization as development proxy** — rapid urbanization (common in Africa) signals structural economic transformation → productivity growth → potential currency appreciation. The system monitors urbanization rates as a development indicator
- **AI/future alignment:** AI can track urbanization from satellite data (nighttime lights, building footprints, road networks) — real-time urbanization monitoring
- **Research connection:** Multi-agent systems can integrate satellite-based urbanization data into long-term currency models — development trajectory signals

---

# CROSS-UNIT SYNTHESIS: Alpha Stack Module Mapping

## Direct Module Mappings

| Alpha Stack Module | Primary Units | Key Concepts |
|-------------------|---------------|--------------|
| **Signal Generation Engine** | STA 244, ECO 210, STA 241 | ARIMA forecasting, optimization, probability models |
| **Risk Management Module** | STA 241, ECO 203, STA 244 | Distributions, hypothesis testing, volatility (GARCH) |
| **Portfolio Optimization** | ECO 210, ECO 201, STA 241 | Matrix algebra, utility theory, covariance matrices |
| **Macro Regime Detection** | ECO 205, ECO 209, STA 245 | IS-LM, monetary policy, economic indicators |
| **Execution Engine** | ECO 201, ECO 209 | Market microstructure, forex markets |
| **Pairs Trading Module** | STA 244, ECO 203 | Cointegration, correlation, regression |
| **Emerging Market Module** | ECO 204, ECO 206, STA 246 | African development, microfinance, demography |
| **Central Bank Watcher** | ECO 209, ECO 205 | Monetary policy, Taylor Rule, inflation targeting |
| **Multi-Agent Coordinator** | ECO 201, STA 241, STA 244 | Game theory, probability, time series models |

## Multi-Agent System Alignment

| Year 2 Concept | Multi-Agent Role | Loop System Pattern |
|----------------|-----------------|---------------------|
| ARMA/ARIMA (STA 244) | Time Series Agent | ReAct loop (estimate → forecast → trade → observe) |
| Hypothesis Testing (ECO 203) | Validation Agent | Reflection loop (test → critique → revise) |
| Game Theory (ECO 201) | Strategy Agent | Deliberation loop (analyze → weigh → decide) |
| Monetary Policy (ECO 209) | Macro Agent | ReAct loop (observe → reason → act) |
| GARCH (STA 244) | Volatility Agent | Observation loop (measure → predict → adjust) |
| Cointegration (STA 244) | Pairs Agent | ReAct loop (monitor → diverge → trade → converge) |
| Portfolio Optimization (ECO 210) | Allocation Agent | Optimization loop (estimate → constrain → allocate) |
| Demography (STA 246) | Long-term Agent | Slow observation loop (track → project → allocate) |

## Quantum Computing Alignment

| Year 2 Concept | Quantum Application | Timeline |
|----------------|---------------------|----------|
| Matrix Algebra (ECO 210) | Quantum linear algebra for portfolio optimization | 2026-2028 |
| Probability Distributions (STA 241) | Quantum Monte Carlo for risk simulation | 2028-2030 |
| Optimization (ECO 210) | Quantum annealing for constrained optimization | 2026-2027 |
| Eigenvalues (ECO 210) | Quantum phase estimation for PCA | 2028-2030 |
| Copulas (STA 241) | Quantum sampling from complex distributions | 2030-2035 |
| DSGE Models (ECO 205) | Quantum simulation of macro models | 2030-2035 |
| ARIMA Forecasting (STA 244) | Quantum time series analysis | 2028-2030 |

---

# VALENTINE'S YEAR 2 STRENGTH-WEAKNESS ANALYSIS

## Strengths (Alpha Stack Relevant)
- **STA 241 (Probability & Distributions) — A (77%):** Excellent foundation for risk modeling. This is the highest-impact unit for the trading system
- **ECO 205 (Intermediate Macro) — B (67%):** Strong macro understanding for regime detection
- **ECO 209 (Money & Banking) — B (65%):** Direct forex market knowledge — essential for the core product
- **ECO 210 (Quantitative Methods) — B (60%):** Solid quantitative foundation for systematic trading

## Weaknesses (Need Improvement for Alpha Stack)
- **STA 244 (Time Series) — D (45%):** CRITICAL GAP — this is the most directly relevant unit for price forecasting. Must be prioritized for self-study
- **ECO 202 (Intro Economic Statistics) — D (43%):** Foundational statistics weakness — affects all downstream statistical work
- **ECO 203 (Economic Statistics) — C (53%):** Hypothesis testing and regression skills need strengthening

## Priority Self-Study Plan
1. **STA 244 (Time Series)** — ARIMA, GARCH, cointegration — THE core forecasting toolkit
2. **ECO 202 (Economic Statistics)** — Solidify foundations: correlation, regression, hypothesis testing
3. **ECO 203 (Economic Statistics)** — Advanced: multiple regression, ANOVA, non-parametric methods
4. **STA 241 (Probability)** — Already strong (A), but extend to copulas and multivariate distributions for advanced risk modeling

---

# RESEARCH INTEGRATION SUMMARY

## How Year 2 Connects to the Full Research Stack

| Research Area | Year 2 Foundation | Gap to Fill |
|--------------|-------------------|-------------|
| **Multi-Agent Systems (R03)** | Game theory (ECO 201), probability (STA 241) | Agent communication protocols, consensus mechanisms |
| **Quantum Computing (R06)** | Matrix algebra (ECO 210), optimization (ECO 210) | Quantum algorithms, QAOA, quantum Monte Carlo |
| **Loop Systems (R03)** | Hypothesis testing (ECO 203), time series (STA 244) | ReAct/Reflection/Deliberation loop implementation |
| **AGI Integration (R06)** | Macro models (ECO 205), monetary policy (ECO 209) | LLM integration, tool use, agentic reasoning |
| **Tech Architecture (R02)** | Quantitative methods (ECO 210), statistics (ECO 203) | Python/Rust implementation, API integration |

---

*End of Year 2 Curriculum Mapping*
*Next: Year 3 — Advanced Economics & Statistics*
