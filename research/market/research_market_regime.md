# Market Regime Analysis — Research Report for Alpha Stack

**Date:** 2026-07-11  
**Purpose:** How Alpha Stack should detect market regimes and adapt its trading strategy accordingly.

---

## 1. What Is a Market Regime?

A market regime is the prevailing "state" of the market at any given time. Markets don't behave uniformly — they alternate between distinct behavioral patterns. A strategy that prints money in one regime can bleed out in another.

### The Four Canonical Regimes

| Regime | Characteristics | Best Strategy Class | Typical Duration |
|--------|----------------|-------------------|-----------------|
| **Bull / Trending Up** | Persistent upward drift, rising volatility, high momentum | Trend following, momentum, long bias | Weeks to months |
| **Bear / Trending Down** | Persistent downward drift, rising volatility, fear-driven | Short bias, defensive, put spreads, cash | Weeks to months |
| **Sideways / Range-Bound** | Oscillation within a band, low directional movement | Mean reversion, grid trading, options selling (theta) | Weeks to months |
| **Crisis / High Volatility** | Violent swings, correlation spike → 1.0, liquidity evaporation | Risk-off, reduce exposure, cash, tail hedges | Days to weeks |

### Why This Matters for Alpha Stack

Running a fixed-strategy portfolio (e.g., 50% trend / 50% mean reversion) in all conditions guarantees that half your capital is fighting the market at any time. A regime-aware system routes capital to the strategy best suited for the current environment.

**Illustrative example:** A fund running trend + mean reversion at 50/50 returned ~0% for the year. A competitor with identical strategies but a regime-detection router returned 18% (Sharpe 1.6) — not by having better strategies, but by knowing *when* to use each one.

---

## 2. Regime Detection Methods

### 2.1 Rules-Based Detection (Most Practical, Recommended Starting Point)

Use combinations of indicator thresholds. Simple, interpretable, zero lag.

#### Core Indicators

| Indicator | What It Measures | Key Thresholds |
|-----------|-----------------|----------------|
| **ADX** (Average Directional Index) | Trend strength (not direction) | <20 = no trend; 20–25 = emerging; >25 = strong trend; >40 = extreme |
| **20-day Realized Volatility** | Market "temperature" | <15% ann. = calm; 15–25% = normal; 25–35% = elevated; >35% = crisis |
| **20-day Return** | Recent directional drift | >+5% = bullish; <-5% = bearish; ±2% = range |
| **Cross-asset Correlation** | "Risk-on / Risk-off" mode | <0.4 = normal diversification; >0.7 = correlated sell-off; >0.85 = crisis |
| **Price vs. 200-day MA** | Long-term trend | Above = bull regime; Below = bear regime |
| **VIX** (or equivalent) | Implied fear | <15 = complacent; 15–25 = normal; 25–35 = stressed; >35 = panic |

#### Decision Tree

```
1. IF volatility > 35% AND correlation > 0.8
     → CRISIS (priority override — nothing else matters)

2. ELSE IF ADX > 25 AND |return| > 5%
     → TRENDING (direction from sign of return)

3. ELSE IF ADX < 20 AND volatility < 15%
     → RANGE-BOUND / MEAN REVERTING

4. ELSE
     → TRANSITION / UNCERTAIN (reduce exposure, wait for clarity)
```

**Pros:** Zero lag, fully transparent, easy to debug.  
**Cons:** Hard thresholds are brittle; needs manual tuning per asset class.

---

### 2.2 Hidden Markov Model (HMM) — The Quant Standard

HMMs assume the market transitions between a small number of *hidden* states, and we observe only prices/returns. The model estimates:
- **State probabilities:** P(state = trending | observations) = 0.60
- **Transition matrix:** P(tomorrow = crisis | today = trending) = 0.05

#### Implementation Sketch

```python
import numpy as np
from hmmlearn import hmm

class RegimeDetector:
    def __init__(self, n_states=3):
        self.model = hmm.GaussianHMM(
            n_components=n_states,
            covariance_type="full",
            n_iter=100,
            random_state=42
        )

    def fit(self, features: np.ndarray):
        """features: [returns, volatility, ADX, ...] shape (T, n_features)"""
        self.model.fit(features)
        return self

    def predict_proba(self, features: np.ndarray) -> np.ndarray:
        """Returns posterior state probabilities for the latest time step."""
        return self.model.predict_proba(features)[-1]

    def get_regime(self, features, threshold=0.5):
        probs = self.predict_proba(features)
        if np.max(probs) < threshold:
            return "uncertain"
        return ["trending", "mean_reverting", "crisis"][np.argmax(probs)]
```

#### Using HMM Output for Strategy Weights

**Naive approach** (risky): Use state probabilities directly as strategy weights.  
**Better approach:** Apply risk-adjusted amplification:

```
trend_weight    = P(trending) * 1.0
mr_weight       = P(mean_revert) * 1.0
crisis_weight   = P(crisis) * 2.0   # amplify crisis signal — asymmetric risk
```

Then normalize to sum to 1.0.

**Key insight:** Don't use HMM probabilities as raw weights. Crisis states are rare but catastrophic — always overweight the defensive allocation.

**Pros:** Captures non-linear state transitions, provides probabilistic output.  
**Cons:** Assumes Gaussian emissions (often violated), sensitive to number of states chosen, can be slow to detect regime changes in real-time.

---

### 2.3 Volatility Clustering — The Pragmatic Shortcut

Volatility clusters: high-vol periods follow high-vol periods, and vice versa. Since volatility is more predictable than returns, a volatility-only regime filter is surprisingly effective.

| Realized Vol (20d annualized) | Regime | Action |
|-------------------------------|--------|--------|
| < 15% | Low Vol / Range | Mean reversion ON, sell options, full size |
| 15–25% | Normal | Standard operations |
| 25–35% | High Vol / Trending | Trend following ON, reduce MR, cut size 30% |
| > 35% | Crisis | Risk-off, reduce all positions 50–80%, buy tail hedges |

**Why volatility works as a single feature:**
- It's the market's "heartbeat" — fast to compute, no estimation lag
- Strong clustering effect (GARCH-family models formalize this)
- Correlates with regime shifts more reliably than returns alone

---

### 2.4 Machine Learning Classification

Train a classifier (Random Forest, XGBoost, LightGBM) on labeled historical regimes.

**Features:** Returns at multiple horizons, volatility (realized + implied), ADX, RSI, breadth indicators, credit spreads, term structure.  
**Labels:** Manually annotated or HMM-derived regime labels.

**Risk:** Overfitting to historical regime patterns that don't repeat. Use walk-forward validation, never train on future data.

---

### 2.5 Hybrid / Ensemble Approach (Recommended for Production)

Combine multiple methods and require consensus:

```
regime_score = (
    0.4 * rules_based_signal +
    0.3 * hmm_state +
    0.2 * vol_clustering_signal +
    0.1 * ml_classifier
)
```

If ≥3 out of 4 methods agree → high confidence, act immediately.  
If 2/4 agree → medium confidence, gradual position adjustment.  
If no consensus → stay in "uncertain" mode, reduce exposure.

---

## 3. Strategy Adaptation by Regime

### 3.1 Bull / Trending Up

| Parameter | Setting |
|-----------|---------|
| Strategy bias | Trend following, momentum, breakout |
| Direction | Long bias (can be 100% long) |
| Position sizing | Full or increased (Kelly fraction) |
| Stop losses | Trailing stops, wider stops (trends need room) |
| Mean reversion | Reduced weight (20% max) — counter-trend trades bleed |
| Options | Buy calls, sell puts (collect premium on dips) |
| Holding period | Longer (let winners run) |

### 3.2 Bear / Trending Down

| Parameter | Setting |
|-----------|---------|
| Strategy bias | Short-term shorts, put spreads, defensive |
| Direction | Short bias or hedged |
| Position sizing | Reduced (50–70% of normal) |
| Stop losses | Tighter stops (bear markets are violent) |
| Mean reversion | Can work for short-covering bounces, but careful |
| Options | Buy puts, sell calls (premium on rips) |
| Cash allocation | 30–50% — capital preservation is priority |

### 3.3 Sideways / Range-Bound

| Parameter | Setting |
|-----------|---------|
| Strategy bias | Mean reversion, grid trading, pairs trading |
| Direction | Neutral (long and short) |
| Position sizing | Normal, but within defined ranges |
| Stop losses | Tight (range edges are natural stops) |
| Trend following | OFF or minimal — it bleeds in chop |
| Options | Sell strangles/iron condors (theta harvest) |
| Holding period | Shorter (trade the range, not the breakout) |

### 3.4 Crisis / High Volatility

| Parameter | Setting |
|-----------|---------|
| Strategy bias | Capital preservation, tail hedging |
| Direction | Flat or short |
| Position sizing | Minimal (10–30% of normal) |
| Stop losses | Very tight or no new positions |
| Mean reversion | Dangerous — "catching a falling knife" |
| Trend following | Can work (crises trend hard), but size small |
| Cash allocation | 70–90% |
| **Rule #1** | **Don't lose money. Rule #2: Don't forget Rule #1.** |

---

## 4. When to Trade vs. When to Sit Out

### The "Uncertain" Regime Is the Most Important

Most of the market's time is spent in transition zones — not clearly trending, not clearly ranging. This is where most strategies lose money.

**Decision framework:**

```
IF regime_confidence > 0.7:
    → Full strategy deployment for detected regime

ELIF regime_confidence 0.4 – 0.7:
    → Half size, use blended strategy weights

ELIF regime_confidence < 0.4:
    → "SIT OUT" mode:
      - Reduce all positions to 25% of normal
      - Tighten all stops
      - No new entries unless high-conviction setup
      - This is a feature, not a bug — preserving capital IS the strategy
```

### Red Lines — Always Sit Out

1. **Volatility > 40% annualized** — market is broken, wait for normalization
2. **Correlation across all assets > 0.9** — no diversification exists, everything moves together
3. **HMM says "uncertain" for > 5 consecutive days** — the model has no idea, neither should you
4. **Three consecutive losing trades in the same direction** — regime may have shifted, stop and reassess

---

## 5. Regime Transition Dynamics

### Regimes Don't Switch Instantly

Real regime transitions are messy. The transition period itself is a regime — one characterized by:
- Conflicting signals (trend indicators say one thing, volatility another)
- False breakouts (the market fakes a trend, then reverses)
- Increased whipsaw rate

### Transition Costs

| Lag (days to detect) | Cost in Trending Market | Cost in Crisis Market |
|----------------------|------------------------|-----------------------|
| 1 day | ~5% of the move missed | ~3% additional loss |
| 3 days | ~15% of the move missed | ~10% additional loss |
| 5 days | ~25% of the move missed | ~20% additional loss |

### Soft Switching Protocol (Recommended)

Instead of hard regime switches (trend ON → OFF), use gradual transitions:

```
Day 0: Regime detected as "trending" with 60% confidence
  → Trend weight: 60% → 70%, MR weight: 40% → 30%

Day 3: Confidence rises to 80%
  → Trend weight: 70% → 85%, MR weight: 30% → 15%

Day 7: Confidence at 90%, sustained
  → Trend weight: 85% → 95%, MR weight: 15% → 5%
```

This smooths out false signals and reduces switching costs by 40–60% vs. hard switching.

---

## 6. Practical Implementation for Alpha Stack

### Architecture

```
┌─────────────────────────────────────────────────┐
│                 REGIME ROUTER                     │
│                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │  Rules   │  │   HMM    │  │ Vol Clustering│   │
│  │  Engine  │  │ Detector │  │   Filter      │   │
│  └────┬─────┘  └────┬─────┘  └──────┬────────┘   │
│       └──────────────┼───────────────┘            │
│                      ▼                            │
│              Ensemble Scorer                      │
│                      │                            │
│              Regime + Confidence                  │
│                      │                            │
│        ┌─────────────┼─────────────┐             │
│        ▼             ▼             ▼             │
│   ┌─────────┐ ┌──────────┐ ┌──────────┐        │
│   │ Trend   │ │  Mean    │ │ Defense  │        │
│   │ Strategy│ │ Reversion│ │ Strategy │        │
│   │ (w=0.X) │ │ (w=0.X)  │ │ (w=0.X)  │        │
│   └─────────┘ └──────────┘ └──────────┘        │
└─────────────────────────────────────────────────┘
```

### Configuration Parameters

```yaml
regime_detection:
  update_frequency: "1h"          # How often to recalculate regime
  lookback_window: 20             # Days for feature calculation
  min_confidence_to_act: 0.5      # Below this, go to "uncertain"
  soft_switch_days: 3             # Days over which to transition weights

  rules_engine:
    adx_trend_threshold: 25
    adx_range_threshold: 20
    vol_crisis_threshold: 0.35
    vol_calm_threshold: 0.15
    return_trend_threshold: 0.05
    correlation_crisis_threshold: 0.8

  hmm:
    n_states: 3                   # trending, mean_reverting, crisis
    retrain_frequency: "monthly"
    features: ["returns_20d", "volatility_20d", "adx", "correlation"]

  vol_clustering:
    vol_percentiles:
      low: 25th
      normal: [25th, 75th]
      high: [75th, 90th]
      crisis: 90th

strategy_allocation:
  trending:
    trend_following: 0.80
    mean_reversion: 0.10
    defense: 0.10
  ranging:
    trend_following: 0.10
    mean_reversion: 0.80
    defense: 0.10
  crisis:
    trend_following: 0.05
    mean_reversion: 0.05
    defense: 0.90
  uncertain:
    trend_following: 0.25
    mean_reversion: 0.25
    defense: 0.50

position_sizing:
  base_kelly_fraction: 0.25       # Quarter-Kelly for safety
  regime_multiplier:
    trending: 1.2
    ranging: 1.0
    crisis: 0.3
    uncertain: 0.5
  max_portfolio_leverage: 1.5
```

### Monitoring & Alerts

| Alert | Condition | Action |
|-------|-----------|--------|
| Regime flip | State changes with >0.6 confidence | Notify, begin soft switch |
| High uncertainty | All states <0.45 probability for 3+ days | Enter "uncertain" mode |
| Crisis detected | Crisis probability >0.3 | Immediate risk reduction |
| Model drift | HMM log-likelihood drops >20% from baseline | Retrain model |
| Drawdown trigger | Portfolio DD > 8% in current regime | Reduce to 50% regardless of regime |

---

## 7. Common Pitfalls

1. **Over-optimizing regime thresholds on historical data.** The market evolves. Use adaptive thresholds (rolling percentiles) rather than fixed numbers.

2. **Too many regimes.** 3 states (trend / range / crisis) is the sweet spot. 5+ states = overfitting. Each state needs enough data to be statistically meaningful.

3. **Ignoring regime duration.** A regime that just started is more likely to persist than one that's been running for months. Use the transition matrix.

4. **Switching too frequently.** If you're switching strategies every week, you're paying too much in transaction costs and slippage. Enforce a minimum regime duration (e.g., 5 trading days).

5. **Fighting the regime.** The most common failure mode: a trend-following system that keeps trying to pick tops in a bull market, or a mean-reversion system that keeps buying dips in a crash. The regime router exists to prevent this.

6. **Hindsight bias in backtesting.** Regime labels are clear in retrospect. In real-time, there's always a gray zone. Backtest with realistic detection lag (at least 1 day).

---

## 8. Key Takeaways for Alpha Stack

1. **Start with rules-based detection.** It's the simplest, most interpretable, and has zero detection lag. Add HMM later for probabilistic refinement.

2. **Volatility is the single most useful regime feature.** If you can only track one thing, track realized volatility.

3. **The "uncertain" regime is where you make or lose money.** Design explicit rules for when to sit out. Sitting out IS a strategy.

4. **Soft switching > hard switching.** Gradual weight transitions reduce switching costs by 40–60%.

5. **Crisis detection must be asymmetric.** Missing a bull trend costs you gains. Missing a crisis costs you capital. Always overweight crisis signals.

6. **Evaluate regime detection by strategy P&L improvement**, not by classification accuracy. A regime detector that's 80% accurate but generates so many switches that costs exceed gains is worthless.

7. **Regime detection is a router, not a strategy.** It doesn't generate alpha — it routes capital to the strategy that generates alpha in the current environment.

---

## References

- Hamilton, J.D. (1989). "A New Approach to the Economic Analysis of Nonstationary Time Series and the Business Cycle." *Econometrica*, 57(2), 357–384.
- Ang, A., & Bekaert, G. (2002). "Regime Switches in Interest Rates." *Journal of Business & Economic Statistics*, 20(2), 163–182.
- Rydén, T., Teräsvirta, T., & Åsbrink, S. (1998). "Stylized Facts of Daily Return Series and the Hidden Markov Model." *Journal of Applied Econometrics*, 13(3), 217–244.
- Two Sigma (2021). "A Machine Learning Approach to Regime Modeling."
- Waylandz (2026). "AI Quantitative Trading: From Zero to One" — Lesson 12: Regime Detection.
- Ang, A. (2014). *Asset Management: A Systematic Approach to Factor Investing.* Oxford University Press.
