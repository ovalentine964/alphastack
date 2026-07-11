# Backtesting Architecture Validation Review

**Date:** 2026-07-11
**Reviewer:** Backtesting Validation Agent
**Documents Reviewed:** `architecture_backtesting.md`, `strategy_enhancement_steps1to4.md` through `steps13to16.md`, `fix_confluence_scoring.md`
**Severity Legend:** 🔴 CRITICAL | 🟠 HIGH | 🟡 MEDIUM | 🟢 LOW | ✅ PASS

---

## Executive Summary

The backtesting architecture is **well-designed and institutional-grade in ambition**. The same-code abstraction, walk-forward framework, and overfitting defense layers are fundamentally sound. However, several **critical and high-severity issues** exist that would undermine the validity of backtest results if implemented as-is. The most significant gaps are around execution realism, data leakage risks in the ML pipeline, and insufficient Monte Carlo methodology.

**Overall Assessment: 7.2/10 — Strong foundation with fixable gaps**

| Category | Score | Status |
|----------|-------|--------|
| Same-code architecture | 9/10 | ✅ Excellent |
| Walk-forward analysis | 7/10 | 🟡 Good with gaps |
| Overfitting prevention | 6/10 | 🟠 Needs strengthening |
| Monte Carlo simulation | 5/10 | 🟠 Significant gaps |
| Performance metrics | 8/10 | ✅ Good |
| Execution realism | 5/10 | 🔴 Major gaps |
| Data integrity | 7/10 | 🟡 Adequate |

---

## 1. Same-Code Architecture (Backtest = Live)

### ✅ What's Correct

The `EventSource` abstraction is **architecturally excellent**. The pattern where `AlphaStrategyEngine` consumes `MarketEvent` objects from an abstract source — never knowing whether it's live or backtest — is the gold standard for eliminating backtest/live divergence.

Key strengths:
- **Steps 1-16 are shared** — confluence scoring, risk gate, position sizing, TP/SL management
- **Multi-timeframe replayer** correctly implements merge-sort by timestamp with proper priority (D1 > H4 > H1 > M15)
- **The critical invariant is well-documented** — what differs (event source, execution, clock, data feed) vs what's shared (all strategy logic)

### 🟠 Issue 1.1: Fundamental Agent Cannot Work in Backtest Mode

**Severity: HIGH**

The Fundamental Intelligence Agent (Step 1) depends on **real-time data sources** that cannot be replayed historically:
- FinBERT sentiment from live news feeds
- LLM reasoning on current economic conditions
- Real-time news RSS ingestion
- Live economic calendar events

**The backtesting architecture does not address how Step 1 produces output during historical replay.** The `BacktestEventSource` only replays candle/tick events — it doesn't replay news events, sentiment scores, or LLM reasoning.

**Impact:** Step 1's `fundamental_bias`, `sentiment_score`, and `event_risk_score` will be **missing or zero** during backtesting, which means:
- The confluence score will be artificially lower (news weight = 0.05 × 0 = 0)
- The "should I trade today?" filter won't function
- Walk-forward optimization will tune parameters without fundamental context

**Fix Required:**
```
Option A: Pre-compute and store historical sentiment scores in TimescaleDB
         (FinBERT on historical headlines, stored per-bar)
Option B: Create a HistoricalFundamentalAgent that reads pre-computed
         sentiment/calendar data from the database
Option C: Accept that backtests exclude fundamental signals and adjust
         confluence weights accordingly (document the limitation)
```

**Recommendation:** Option B — the `BacktestEventSource` should emit `news` and `sentiment` events from historical data, and the `FundamentalAgent` should have a `backtest_mode` that consumes these pre-computed values instead of calling live APIs.

### 🟡 Issue 1.2: HMM Regime Detection Retraining in Walk-Forward

**Severity: MEDIUM**

The HMM regime detector (Step 2) is retrained monthly in live trading. During walk-forward backtesting, the architecture shows parameter optimization per fold but does not explicitly address **when HMM models are retrained during the backtest**.

If the HMM is trained on the full dataset (including test periods), this is **forward-looking bias**. The walk-forward fold training should include HMM retraining on training data only.

**Fix Required:** Explicitly document that the HMM must be retrained within each walk-forward training window, and the trained model applied to the test window without re-fitting.

### 🟡 Issue 1.3: RL Agent Training Creates Circular Dependency

**Severity: MEDIUM**

The PPO position sizing agent and DQN take-profit agent are trained on historical trade data. If these agents are used during backtesting, and the backtest results are used to train them, there's a **circular dependency**:
- Backtest generates trades → trains RL agent → RL agent influences backtest → ...

**Fix Required:** RL agents must be trained on a **separate training set** that is not used for backtest evaluation. The walk-forward framework should hold out RL training data from the test fold.

---

## 2. Walk-Forward Analysis

### ✅ What's Correct

- **252-day train / 63-day test / 21-day step** — standard institutional parameters
- **Purge gap of 5 bars** between train and test — prevents autocorrelation leakage
- **Parameter optimization within training folds only** using Optuna (Bayesian)
- **Acceptance criteria** are well-defined: mean Sharpe > 1.0, 70%+ folds profitable, worst-fold Sharpe > 0
- **Parameter stability check** — no parameter should drift > 50% of range across folds

### 🟠 Issue 2.1: Walk-Forward Window Sizes Are Too Rigid

**Severity: HIGH**

The 252/63/21 day configuration assumes daily-equivalent trading. But the strategy operates on **M15/H1/H4 timeframes**, not daily bars. The walk-forward windows should be specified in **trading bars**, not calendar days.

For H1 data:
- 252 days × 24 hours = 6,048 training bars
- 63 days × 24 hours = 1,512 test bars

For M15 data:
- 252 days × 96 bars = 24,192 training bars
- 63 days × 96 bars = 6,048 test bars

The current implementation uses `timedelta(days=self.train_days)` which is calendar-based, not bar-based. This means:
- Forex weekends create gaps (5 days/week, not 7)
- Different pairs may have different trading hours
- Crypto trades 24/7 but forex doesn't

**Fix Required:** Convert window sizes to bar counts based on the primary timeframe, accounting for forex weekends and holidays. The `_generate_windows` method should use trading-day logic, not calendar-day arithmetic.

### 🟠 Issue 2.2: Missing Walk-Forward for ML Models

**Severity: HIGH**

The walk-forward framework in `architecture_backtesting.md` focuses on **rule-based parameter optimization** (confluence threshold, RSI levels, ATR multipliers). But the ML pipeline (`architecture_ml_pipeline.md`) trains XGBoost, LSTM, and other models on **fixed 70/15/15 splits** with walk-forward CV for validation only.

**The backtesting walk-forward and ML walk-forward are not synchronized.** When the backtester runs fold N, it should use ML models trained only on fold N's training data. The current architecture doesn't enforce this.

**Impact:** If XGBoost is trained on 2021-2025 data and backtested on 2024-2026, the model has seen 2024-2025 data during training. This is **in-sample testing disguised as out-of-sample**.

**Fix Required:** The `WalkForwardAnalyzer` must coordinate with the ML pipeline:
1. For each fold, extract the training window
2. Train ML models on training window data only
3. Freeze ML model parameters
4. Run backtest on test window with frozen models
5. Report per-fold ML model performance

### 🟡 Issue 2.3: Minimum Trade Count Threshold

**Severity: MEDIUM**

The acceptance criteria require "minimum 30 trades per test fold" for statistical significance. With 63 test days and the strategy's selective nature (confluence ≥ 40, multiple filters), achieving 30 trades per fold may be unrealistic.

**Calculation:**
- 63 days × ~4 H1 candles/day (London+NY sessions) = ~252 potential entry points
- Confluence filter (score ≥ 40): ~15-25% pass → 38-63 potential trades
- Risk gate filter: ~85% pass → 32-53 trades
- Correlation filter: further reduction

This is **borderline feasible** for EUR/USD but may be insufficient for less liquid pairs.

**Fix Required:** Either reduce the minimum to 15 trades per fold (with appropriate confidence interval widening) or extend test windows to 126 days (6 months) for less liquid pairs.

---

## 3. Overfitting Prevention

### ✅ What's Correct

The 7-layer defense system is well-architected:
1. Walk-forward validation ✅
2. CPCV (López de Prado) ✅
3. Deflated Sharpe ratio ✅
4. Parameter stability analysis ✅
5. Cross-pair generalization ✅
6. Regime consistency ✅
7. Parsimony (AIC/BIC) ✅

The overfitting scorecard (70/100 threshold) provides an objective go/no-go decision.

### 🔴 Issue 3.1: CPCV Implementation Has Methodological Error

**Severity: CRITICAL**

The `CombinatorialPurgedCV` class generates paths by splitting data into N groups and selecting C(N, k) combinations of test groups. However, the implementation does **not properly account for the temporal ordering of financial data**.

```python
# Current implementation:
groups = [
    (i * group_size, (i + 1) * group_size)
    for i in range(self.n_groups)
]
```

This creates **equal-sized contiguous blocks**. When test groups are non-contiguous (e.g., groups 2 and 7), the training set has **gaps in the middle** — data from groups 3-6 is training data that temporally surrounds test group 2. This violates the temporal ordering principle because the model trains on data that comes **both before and after** the test period.

**López de Prado's CPCV specifically requires purging** around test boundaries to prevent this. The current `_apply_purge` method exists but only purges at boundaries — it doesn't address the fundamental issue of training on future data when test groups are non-contiguous.

**Fix Required:**
```
Option A: Only allow contiguous test group combinations
         (reduces C(10,2)=45 paths to 9 paths, but maintains temporal validity)
Option B: For non-contiguous test groups, split training into
         "before test" and "after test" segments, train only on "before"
Option C: Use the embargo approach — after each test group, add an
         embargo period before training data resumes
```

**Recommendation:** Option B — the implementation should ensure that for each path, the model only trains on data that temporally precedes the test period. This means non-contiguous test groups require training on only the data before the first test group.

### 🟠 Issue 3.2: Deflated Sharpe Ratio Formula May Be Incorrect

**Severity: HIGH**

The deflated Sharpe ratio calculation:

```python
deflated = observed_sharpe - expected_max_sharpe + adjustment
```

This formula appears to deviate from the Bailey & López de Prado (2014) paper. The standard formula is:

```
DSR = Prob(SR* > 0) where SR* is the deflated Sharpe
    = Φ((SR̂ - SR₀) × √(n-1) / √(1 - γ₃×SR̂ + (γ₄-1)/4 × SR̂²))
```

Where:
- SR̂ = observed maximum Sharpe across trials
- SR₀ = expected maximum Sharpe under null (no skill)
- γ₃ = skewness of Sharpe estimates
- γ₄ = kurtosis of Sharpe estimates

The current implementation uses a simplified approximation that may produce **incorrect confidence levels**.

**Fix Required:** Implement the full DSR formula from the paper, or use the `deflated_sharpe_ratio` package if available. The approximation may be acceptable for rough screening but should not be the sole overfitting gate.

### 🟡 Issue 3.3: Cross-Pair Generalization Test Is Insufficiently Defined

**Severity: MEDIUM**

The architecture states "Strategy trained on EUR/USD must work on GBP/USD, USD/JPY" but doesn't define:
- What constitutes "working" on another pair?
- How to handle pair-specific parameters (ATR multipliers, session times)?
- Whether the same confluence weights apply across all pairs?

**Fix Required:** Define explicit cross-pair acceptance criteria:
- Strategy must be profitable on ≥ 3 of 5 tested pairs
- Sharpe on cross-pair must be ≥ 0.5 × Sharpe on primary pair
- Parameter adaptation: allow pair-specific ATR/session parameters while keeping confluence weights universal

---

## 4. Monte Carlo Simulation

### ✅ What's Correct

Five simulation methods are well-chosen:
1. Trade resampling (bootstrap) ✅
2. Return shuffling ✅
3. Trade removal (leave-one-out) ✅
4. Worst-case insertion ✅
5. Parameter perturbation ✅

The acceptance criteria (probability of profit > 70%, ruin < 5%) are reasonable.

### 🔴 Issue 4.1: Monte Carlo Operates on Trade Returns, Not Price Paths

**Severity: CRITICAL**

The current Monte Carlo implementation resamples **trade-level returns** (P&L per trade). This is fundamentally limited because:

1. **It assumes trades are independent** — but they're not. Consecutive trades in a trending market are correlated.
2. **It ignores autocorrelation** in returns — winning streaks and losing streaks in real markets have structure.
3. **It can't test "what if the market moved differently"** — only "what if trades happened in a different order."
4. **It doesn't account for path-dependent risk** — drawdown depends on the sequence of wins and losses, not just their distribution.

**The correct approach for a trading strategy** is to simulate **price paths** and re-run the strategy on each simulated path. This captures:
- Autocorrelation in returns
- Regime persistence
- Path-dependent drawdown dynamics
- The strategy's behavior under different market conditions

**Fix Required:**
```
Add Method 6: Price Path Simulation
- Fit a GARCH(1,1) model to historical returns
- Simulate 10,000 synthetic price paths preserving:
  - Volatility clustering (GARCH effects)
  - Fat tails (Student-t innovations)
  - Regime persistence (regime-switching model)
- Run the FULL STRATEGY on each synthetic path
- This produces realistic distributions of Sharpe, drawdown, etc.
```

### 🟠 Issue 4.2: Trade Resampling Doesn't Preserve Strategy Logic

**Severity: HIGH**

When resampling trades with replacement, the Monte Carlo creates synthetic equity curves by concatenating random trades. But this ignores:

1. **Position sizing depends on prior trades** — the performance multiplier (last 5 trades win rate) changes based on sequence
2. **Correlation exposure depends on what's currently open** — random trade sequences may violate correlation limits
3. **Session/time-of-day effects** — a trade taken during Asian session behaves differently than London

**Fix Required:** The trade resampling should:
- Preserve the temporal clustering of trades (don't mix Asian and London trades randomly)
- Recalculate position sizing based on the resampled sequence
- Enforce portfolio constraints on each simulation

### 🟡 Issue 4.3: Monte Carlo Doesn't Test Regime Transitions

**Severity: MEDIUM**

The worst-case stress test inserts the worst historical losing streak at random points. But it doesn't test:
- **What if a regime transition happens at the worst possible time?**
- **What if the strategy is fully positioned when a black swan hits?**
- **What if correlation converges to 1.0 during a crisis?**

**Fix Required:** Add scenario-based Monte Carlo:
- Scenario 1: Trending bull → sudden crash (Swiss Franc 2015 style)
- Scenario 2: Low volatility range → breakout (COVID March 2020 style)
- Scenario 3: Correlation breakdown (carry trade unwind)
- For each scenario, test with maximum portfolio exposure

---

## 5. Performance Metrics

### ✅ What's Correct

The metrics suite is comprehensive and well-defined:

| Metric | Implementation | Status |
|--------|---------------|--------|
| Sharpe Ratio | Annualized, √252 scaling | ✅ Correct |
| Sortino Ratio | Downside deviation only | ✅ Correct |
| Calmar Ratio | Annualized return / max DD | ✅ Correct |
| Omega Ratio | Threshold-based | ✅ Correct |
| Max Drawdown | Peak-to-trough percentage | ✅ Correct |
| Profit Factor | Gross profit / gross loss | ✅ Correct |
| R-Multiple | P&L / initial risk | ✅ Correct |
| Win Rate | Wins / total trades | ✅ Correct |
| Expectancy | (WR × avg_win) - (LR × avg_loss) | ✅ Correct |

### 🟡 Issue 5.1: Sharpe Ratio Uses Trade Returns, Not Daily Returns

**Severity: MEDIUM**

The Sharpe ratio implementation:
```python
returns_arr = np.array(returns)  # These are per-trade returns
excess_returns = returns_arr - risk_free_rate / periods_per_year
mean_excess = np.mean(excess_returns)
std_returns = np.std(excess_returns, ddof=1)
return (mean_excess / std_returns) * np.sqrt(periods_per_year)
```

The `returns` list contains **per-trade P&L percentages**, not daily returns. Annualizing by `√252` assumes daily returns with 252 trading days per year. If the strategy takes ~200 trades/year, the correct annualization factor is `√200`, not `√252`.

**Impact:** Overestimates Sharpe ratio by ~12% (252/200 ≈ 1.12, √1.12 ≈ 1.06, so 6% overestimate).

**Fix Required:** Calculate Sharpe on **daily equity returns** (resample equity curve to daily frequency) rather than per-trade returns. This is the standard approach and correctly handles varying trade frequency.

### 🟡 Issue 5.2: Missing Information Ratio

**Severity: LOW**

The metrics suite lacks an **Information Ratio** (excess return vs benchmark / tracking error). For a forex strategy, the benchmark could be:
- Buy-and-hold DXY
- Risk-free rate (T-bills)
- Another strategy (the rule-based version before AI enhancements)

This is useful for measuring the **value added** by the AI/ML components.

**Fix Required:** Add Information Ratio with configurable benchmark. Low priority.

### 🟡 Issue 5.3: Drawdown Duration Not Used in Walk-Forward Criteria

**Severity: MEDIUM**

The acceptance criteria check max drawdown percentage but not **drawdown duration**. A strategy with 15% max drawdown that takes 8 months to recover is psychologically and financially different from one that recovers in 2 weeks.

**Fix Required:** Add to walk-forward acceptance criteria:
- Mean max drawdown duration < 30 trading days
- Worst-fold max drawdown duration < 60 trading days

---

## 6. Execution Realism

### ✅ What's Correct

The `ExecutionSimulator` includes:
- Dynamic spread modeling ✅
- Volume-based slippage ✅
- Commission per lot ✅
- Swap/rollover costs ✅
- Execution latency simulation (200ms) ✅
- Limit order fill probability (85%) ✅
- Partial fill modeling ✅

### 🔴 Issue 6.1: Spread Model Doesn't Capture Session-Dependent Spreads

**Severity: CRITICAL**

The strategy document (Step 3) explicitly states:
> Asian session: Spreads 1.5-2x normal (lower liquidity)
> London session: Spreads at minimum (peak liquidity)
> Off-hours: Spreads 2-3x normal

But the `ExecutionConfig` uses a single `fixed_spread_pips` or `spread_multiplier` that doesn't vary by session. This means:
- Asian session trades are **under-penalized** (real spreads are wider)
- London session trades are **over-penalized** (real spreads are tighter)
- Off-hours trades are **significantly under-penalized**

**Impact:** The backtest will show profitable Asian/off-hours trades that would be **unprofitable with real spreads**. This is a classic source of backtest/live divergence.

**Fix Required:**
```python
@dataclass
class SessionSpreadModel:
    """Session-dependent spread modeling."""
    asian_multiplier: float = 1.75      # 1.5-2x normal
    london_multiplier: float = 0.85     # Below normal (peak liquidity)
    ny_multiplier: float = 1.0          # Normal
    overlap_multiplier: float = 0.75    # Lowest (peak volume)
    off_hours_multiplier: float = 2.5   # 2-3x normal
    
    def get_spread(self, base_spread: float, session: Session) -> float:
        multiplier = {
            Session.ASIAN: self.asian_multiplier,
            Session.LONDON: self.london_multiplier,
            Session.NEW_YORK: self.ny_multiplier,
            Session.LONDON_NY_OVERLAP: self.overlap_multiplier,
            Session.OFF_HOURS: self.off_hours_multiplier,
        }.get(session, 1.0)
        return base_spread * multiplier
```

### 🟠 Issue 6.2: Slippage Model Doesn't Account for Volatility Spikes

**Severity: HIGH**

The volatility-based slippage model:
```python
slippage = market.atr_14 * 0.05 * (order.size / 0.01)
```

Uses ATR(14) as the volatility measure. But during **news events and session transitions**, instantaneous volatility can be 5-10× the 14-period average. The slippage model should use **realized volatility at the time of execution**, not the smoothed ATR.

**Fix Required:** Use ATR(1) or tick-level realized volatility for slippage calculation during high-impact events. Add a news proximity multiplier:
```python
if event_risk_score > 0.7:
    slippage *= 3.0  # 3x slippage near high-impact events
```

### 🟠 Issue 6.3: No Modeling of Requotes and Partial Fills in Forex

**Severity: HIGH**

MT5/forex brokers frequently:
- **Requote** during volatile periods (order rejected, need to resubmit at new price)
- **Partially fill** large orders (especially during low liquidity)
- **Reject orders** during extreme volatility (circuit breakers)

The `ExecutionSimulator` models partial fills but doesn't model **rejection and requotes**. In live trading, a requoted order at a worse price is a real cost.

**Fix Required:** Add requote probability model:
- Normal conditions: 1% requote probability
- High volatility (ATR > 1.5x average): 5% requote probability
- News events: 15% requote probability
- On requote: re-attempt at new price with additional slippage

### 🟡 Issue 6.4: Limit Order Fill Model Is Too Optimistic

**Severity: MEDIUM**

The `limit_fill_probability: float = 0.85` means 85% of limit orders fill when price touches the level. In reality:
- If price **wick-touched** (high/low reached the level but close didn't): ~60-70% fill rate
- If price **closed through** the level: ~95% fill rate
- During high volatility: fill rate drops further

**Fix Required:** Make fill probability conditional on candle type:
```python
if candle_type == 'wick_touch':
    fill_probability = 0.65
elif candle_type == 'close_through':
    fill_probability = 0.95
# Adjust for volatility
fill_probability *= max(0.5, 1.0 - (atr_ratio - 1.0) * 0.3)
```

---

## 7. Data Integrity

### ✅ What's Correct

- **Data snapshot system** with SHA-256 checksums for reproducibility ✅
- **Gap detection** with classification (minor/moderate/major/critical) ✅
- **OHLC integrity validation** (H ≥ L, H ≥ max(O,C), etc.) ✅
- **Data quality scoring** (quality_score threshold at 0.95) ✅

### 🟡 Issue 7.1: Forward-Fill Creates Artificial Data

**Severity: MEDIUM**

For minor gaps (1-2 bars), the architecture forward-fills: `Open=Close, Volume=0`. This creates **artificial candles** that:
- Have zero volume (which the strategy uses for volume confirmation)
- Have identical OHLC (which candlestick pattern detection may misinterpret)
- Don't reflect actual market conditions during the gap

**Fix Required:** For gaps < 3 bars, use **higher-timeframe interpolation** (synthesize H1 candles from H4 data) rather than forward-fill. If higher-TF data is unavailable, mark the gap as `filled=False` and exclude from signal generation during that period.

### 🟡 Issue 7.2: No Survivorship Bias Check

**Severity: MEDIUM**

The architecture doesn't address **survivorship bias** in the data:
- Forex: Major pairs have existed for decades, but crosses may have been delisted
- Crypto: Altcoins frequently get delisted. Backtesting on only currently-listed coins introduces survivorship bias (you're only testing coins that survived)

**Fix Required:** For crypto, maintain a list of all coins that were ever listed on the exchange during the backtest period, including delisted ones. For forex, this is less of an issue but should be documented.

---

## 8. Additional Gaps

### 🟠 Issue 8.1: No Transaction Cost Sensitivity Analysis

**Severity: HIGH**

The architecture uses fixed commission ($7/lot) and spread assumptions. But real costs vary:
- Different brokers have different commission structures
- Spreads vary by broker and liquidity provider
- Swap rates change daily

**A strategy that's profitable at 1.5 pip spread but unprofitable at 2.0 pip spread has a fragile edge.**

**Fix Required:** Run backtests at multiple cost levels:
- Optimistic: 0.8x base costs
- Base: 1.0x base costs
- Conservative: 1.5x base costs
- Worst case: 2.0x base costs
- Strategy must be profitable at conservative level to pass

### 🟠 Issue 8.2: No Look-Ahead Bias Check for Confluence Scoring

**Severity: HIGH**

The confluence scoring system (`fix_confluence_scoring.md`) combines signals from Steps 5-9. During backtesting, all 5 signals are computed from the **same candle's data**. But in live trading:
- S/R levels are computed from **historical** data (no look-ahead) ✅
- Liquidity detection uses **real-time order flow** (no look-ahead) ✅
- SMC patterns use the **current candle's OHLC** — but the candle is already closed ✅
- RSI uses the **current close** — same as live ✅
- Candlestick patterns use the **current candle** — same as live ✅

**However**, the confluence scorer combines all signals at the same timestamp. In live trading, there may be **latency between signal detection** (e.g., SMC pattern detected at T+100ms, RSI computed at T+300ms). If price moves during this latency window, the backtest may show a confluence that wouldn't exist live.

**Fix Required:** Add a **signal staleness check** — if signals were generated more than 500ms apart, re-score the confluence with the latest price. This is a minor issue for H1+ timeframes but could matter for M15 entries.

### 🟡 Issue 8.3: No Slippage Correlation with Drawdown

**Severity: MEDIUM**

During drawdowns, traders often experience:
- **Worse slippage** (emotional trading, market orders at bad prices)
- **Wider spreads** (broker risk management)
- **Requotes** (broker liquidity issues)

The backtest simulator doesn't model the correlation between portfolio drawdown and execution quality degradation.

**Fix Required:** Add a drawdown-dependent slippage multiplier:
```python
drawdown_pct = (peak_equity - current_equity) / peak_equity
if drawdown_pct > 0.10:  # > 10% drawdown
    slippage_multiplier = 1.0 + (drawdown_pct - 0.10) * 5  # Up to 2.5x at 40% DD
```

### 🟡 Issue 8.4: Missing Benchmark Comparison

**Severity: MEDIUM**

The backtest report structure doesn't include **benchmark comparison**. A Sharpe of 1.5 means nothing if a simple moving average crossover achieves 1.8 on the same data.

**Fix Required:** Always compare against:
- Buy-and-hold (for the instrument)
- Simple trend-following (e.g., 20/50 EMA crossover)
- Random entry with same risk management (Monte Carlo baseline)

### 🟢 Issue 8.5: No Transaction Log for Audit

**Severity: LOW**

The architecture logs trades to the journal but doesn't produce a **machine-readable transaction log** that can be independently verified. For regulatory and debugging purposes, every backtest should produce a CSV/JSONL file with:
- Every order submitted (timestamp, symbol, side, size, type)
- Every fill (timestamp, price, slippage, commission)
- Every position update (SL/TP changes, partial closes)
- Account state at each step (balance, equity, margin)

**Fix Required:** Add `BacktestTransactionLog` that writes every event to a file during backtest execution.

---

## 9. Summary of Issues by Severity

### 🔴 CRITICAL (3 issues)

| # | Issue | Impact | Fix Effort |
|---|-------|--------|------------|
| 3.1 | CPCV temporal ordering violation | Overfitting detection may be invalid | 2 days |
| 4.1 | MC on trade returns, not price paths | Unrealistic confidence intervals | 3 days |
| 6.1 | No session-dependent spread modeling | Asian/off-hours trades look profitable but aren't | 1 day |

### 🟠 HIGH (6 issues)

| # | Issue | Impact | Fix Effort |
|---|-------|--------|------------|
| 1.1 | Fundamental agent can't backtest | Missing ~5% of confluence signal | 2 days |
| 2.1 | Walk-forward windows are calendar-based | Bar-count mismatch across timeframes | 1 day |
| 2.2 | Walk-forward doesn't coordinate with ML training | In-sample ML testing | 3 days |
| 3.2 | Deflated Sharpe formula may be incorrect | Overfitting gate unreliable | 1 day |
| 6.2 | Slippage doesn't spike during volatility | Under-estimated execution costs | 0.5 days |
| 6.3 | No requote/rejection modeling | Missing real execution friction | 1 day |
| 8.1 | No transaction cost sensitivity analysis | Fragile edge undetected | 1 day |
| 8.2 | No look-ahead bias check for confluence | Minor in-sample leakage possible | 0.5 days |

### 🟡 MEDIUM (9 issues)

| # | Issue | Impact | Fix Effort |
|---|-------|--------|------------|
| 1.2 | HMM retraining not coordinated with WF | Forward-looking regime labels | 0.5 days |
| 1.3 | RL agent circular dependency | In-sample RL testing | 1 day |
| 2.3 | Minimum trade count too high | Borderline statistical significance | 0.5 days |
| 3.3 | Cross-pair generalization undefined | No clear pass/fail criteria | 0.5 days |
| 4.2 | MC doesn't preserve strategy logic | Unrealistic resampled equity curves | 1 day |
| 4.3 | MC doesn't test regime transitions | Missing crisis scenarios | 1 day |
| 5.1 | Sharpe uses trade returns, not daily | ~6% Sharpe overestimate | 0.5 days |
| 5.3 | No drawdown duration in WF criteria | Missing psychological risk metric | 0.5 days |
| 6.4 | Limit fill model too optimistic | Over-estimated fill rates | 0.5 days |
| 7.1 | Forward-fill creates artificial data | False volume/candlestick signals | 0.5 days |
| 7.2 | No survivorship bias check (crypto) | Only testing surviving coins | 0.5 days |
| 8.3 | No slippage-DD correlation | Under-estimated costs during drawdowns | 0.5 days |
| 8.4 | No benchmark comparison | Contextless performance metrics | 0.5 days |

### 🟢 LOW (1 issue)

| # | Issue | Impact | Fix Effort |
|---|-------|--------|------------|
| 8.5 | No machine-readable transaction log | Audit difficulty | 0.5 days |

---

## 10. Recommended Implementation Priority

### Phase 1: Fix Critical Issues (Week 1)
1. Fix CPCV temporal ordering (Issue 3.1)
2. Add session-dependent spread model (Issue 6.1)
3. Implement price-path Monte Carlo (Issue 4.1)

### Phase 2: Fix High Issues (Week 2)
4. Add historical fundamental data for backtesting (Issue 1.1)
5. Coordinate walk-forward with ML training (Issue 2.2)
6. Add transaction cost sensitivity analysis (Issue 8.1)
7. Add requote/rejection modeling (Issue 6.3)
8. Fix walk-forward window to use trading bars (Issue 2.1)
9. Verify deflated Sharpe formula (Issue 3.2)

### Phase 3: Fix Medium Issues (Week 3)
10. All medium issues listed above

### Phase 4: Enhancements (Week 4+)
11. Transaction log (Issue 8.5)
12. Benchmark comparison (Issue 8.4)
13. Additional Monte Carlo scenarios

---

## 11. Positive Assessment

Despite the issues identified, the backtesting architecture has several **institutional-quality strengths** that many retail and even professional systems lack:

1. **The same-code abstraction is excellent** — this alone eliminates the most common source of backtest/live divergence
2. **The overfitting defense is multi-layered** — walk-forward + CPCV + deflated Sharpe + parameter stability + cross-pair + regime + parsimony
3. **The execution simulator is comprehensive** — spread, slippage, commission, swap, partial fills, latency
4. **The reporting structure is thorough** — 11 sections covering every aspect of strategy evaluation
5. **The phased implementation is pragmatic** — start simple, add complexity as capital justifies
6. **The data snapshot system ensures reproducibility** — checksummed data with gap tracking
7. **The regime-specific analysis is forward-thinking** — most backtesting systems ignore regime effects

**With the critical and high issues fixed, this would be a top-decile backtesting system for retail algorithmic trading.**

---

*Review completed by Backtesting Validation Agent*
*Total issues found: 19 (3 critical, 6 high, 9 medium, 1 low)*
*Estimated total fix effort: ~20 engineering days*
