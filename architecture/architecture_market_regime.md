# Alpha Stack — Market Regime Detection Architecture

**Version:** 1.0
**Date:** 2026-07-13
**Status:** Architecture Design
**Dependencies:** Strategy Engine, Risk Management, Alternative Data

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Design Philosophy](#2-design-philosophy)
3. [System Architecture](#3-system-architecture)
4. [Detection Methods](#4-detection-methods)
5. [Regime Definitions](#5-regime-definitions)
6. [Strategy Adaptation Rules](#6-strategy-adaptation-rules)
7. [Soft Switching Protocol](#7-soft-switching-protocol)
8. [Integration Points](#8-integration-points)
9. [Implementation Roadmap](#9-implementation-roadmap)

---

## 1. Executive Summary

### Problem

A fixed-strategy portfolio (e.g., 50% trend / 50% mean reversion) guarantees that half your capital fights the market at any time. A trend-following strategy bleeds in sideways markets; mean reversion catches falling knives in crashes. Without regime awareness, strategy selection is random.

### Solution

A **regime detection router** that identifies the current market state (trending, ranging, crisis, uncertain) using an ensemble of methods, then dynamically allocates capital to the strategy best suited for that environment. The router doesn't generate alpha — it routes capital to the strategy that generates alpha in the current regime.

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Detection method | Ensemble (rules + HMM + volatility) | No single method is reliable alone |
| Regime count | 3 primary + 1 meta (uncertain) | 5+ states = overfitting; 3 is the sweet spot |
| Switching protocol | Soft (gradual weight transitions) | Hard switching costs 40–60% more in transition losses |
| Crisis detection | Asymmetric (overweight crisis signals) | Missing a bull trend costs gains; missing a crisis costs capital |
| Update frequency | Hourly | Regimes don't change minute-to-minute |

---

## 2. Design Philosophy

### P1: The Uncertain Regime Is the Most Important
Most of the market's time is in transition — not clearly trending, not clearly ranging. This is where most strategies lose money. Explicit "sit out" rules are a feature, not a bug.

### P2: Volatility Is the Single Most Useful Feature
If you can only track one thing, track realized volatility. It clusters, it's fast to compute, and it correlates with regime shifts more reliably than returns alone.

### P3: Soft Switching Over Hard Switching
Instead of flipping strategies on/off, gradually shift weights over 3–5 days. This smooths false signals and reduces switching costs by 40–60%.

### P4: Crisis Detection Must Be Asymmetric
Missing a bull trend costs you gains. Missing a crisis costs you capital. Always overweight crisis signals with a 2× multiplier.

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    REGIME DETECTION ROUTER                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │  RULES-BASED │  │    HMM       │  │  VOLATILITY  │           │
│  │  ENGINE      │  │  DETECTOR    │  │  CLUSTERING  │           │
│  │              │  │              │  │              │           │
│  │ ADX + Vol +  │  │ 3-state      │  │ Realized vol │           │
│  │ Return +     │  │ Gaussian     │  │ percentiles  │           │
│  │ Correlation  │  │ model        │  │              │           │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘           │
│         │                  │                  │                   │
│         └──────────────────┼──────────────────┘                   │
│                            ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │              ENSEMBLE SCORER                              │     │
│  │  regime = 0.4×rules + 0.3×hmm + 0.2×vol + 0.1×ml       │     │
│  │  confidence = agreement_level (2/3, 3/3 methods agree)   │     │
│  └──────────────────────────┬──────────────────────────────┘     │
│                             │                                     │
│              ┌──────────────┼──────────────┐                      │
│              ▼              ▼              ▼                      │
│  ┌─────────────────┐ ┌────────────┐ ┌────────────┐              │
│  │  TRENDING        │ │  RANGING   │ │  CRISIS    │              │
│  │                  │ │            │ │            │              │
│  │  Trend: 80%     │ │  MR: 80%   │ │  Defense:  │              │
│  │  MR: 10%        │ │  Trend: 10%│ │  90%       │              │
│  │  Defense: 10%   │ │  Def: 10%  │ │  Trend: 5% │              │
│  └─────────────────┘ └────────────┘ └────────────┘              │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │  UNCERTAIN (confidence < 0.5)                             │     │
│  │  Trend: 25% | MR: 25% | Defense: 50%                     │     │
│  │  "Sitting out IS the strategy"                            │     │
│  └─────────────────────────────────────────────────────────┘     │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Detection Methods

### 4.1 Rules-Based Engine (Weight: 0.4)

**Zero lag, fully transparent, easy to debug.** The primary detection method.

#### Core Indicators

| Indicator | Measures | Thresholds |
|-----------|----------|------------|
| ADX (14-period) | Trend strength | <20 = no trend; 20–25 = emerging; >25 = strong; >40 = extreme |
| 20-day Realized Volatility | Market "temperature" | <15% = calm; 15–25% = normal; 25–35% = elevated; >35% = crisis |
| 20-day Return | Directional drift | >+5% = bullish; <-5% = bearish; ±2% = range |
| Cross-asset Correlation | Risk-on/off mode | <0.4 = normal; >0.7 = correlated selloff; >0.85 = crisis |
| Price vs 200-day MA | Long-term trend | Above = bull; Below = bear |

#### Decision Tree

```python
def rules_based_regime(adx, vol_20d, return_20d, correlation):
    """Rules-based regime detection with zero lag."""
    # Priority 1: Crisis (override everything)
    if vol_20d > 0.35 and correlation > 0.8:
        return "crisis", 0.9
    
    # Priority 2: Trending
    if adx > 25 and abs(return_20d) > 0.05:
        direction = "bull" if return_20d > 0 else "bear"
        return f"trending_{direction}", 0.7
    
    # Priority 3: Range-bound
    if adx < 20 and vol_20d < 0.15:
        return "ranging", 0.7
    
    # Default: Uncertain
    return "uncertain", 0.4
```

### 4.2 Hidden Markov Model (Weight: 0.3)

**Probabilistic, captures non-linear transitions.** Refines rules-based detection.

```python
class HMMRegimeDetector:
    def __init__(self, n_states=3):
        self.model = hmm.GaussianHMM(
            n_components=n_states,
            covariance_type="full",
            n_iter=100,
            random_state=42
        )
    
    def fit(self, features):
        """features: [returns_20d, volatility_20d, adx, correlation]"""
        self.model.fit(features)
    
    def predict(self, features):
        """Returns state probabilities for latest observation."""
        probs = self.model.predict_proba(features)[-1]
        states = ["trending", "mean_reverting", "crisis"]
        return dict(zip(states, probs))
```

**HMM Output Processing:**
```python
def hmm_to_regime(probs, threshold=0.5):
    """Convert HMM probabilities to regime with crisis amplification."""
    # Amplify crisis signal (asymmetric risk)
    probs["crisis"] *= 2.0
    
    # Normalize
    total = sum(probs.values())
    probs = {k: v/total for k, v in probs.items()}
    
    if max(probs.values()) < threshold:
        return "uncertain", max(probs.values())
    
    regime = max(probs, key=probs.get)
    return regime, probs[regime]
```

### 4.3 Volatility Clustering (Weight: 0.2)

**The pragmatic shortcut.** Volatility clusters: high-vol follows high-vol.

```python
def volatility_regime(realized_vol_20d):
    """Single-feature regime detection via volatility percentiles."""
    if realized_vol_20d < 0.15:
        return "ranging", 0.8      # Low vol = range-bound
    elif realized_vol_20d < 0.25:
        return "normal", 0.6       # Normal operations
    elif realized_vol_20d < 0.35:
        return "trending", 0.7     # High vol = trending
    else:
        return "crisis", 0.9       # Crisis
```

### 4.4 Ensemble Scoring

```python
class EnsembleRegimeScorer:
    WEIGHTS = {
        "rules": 0.4,
        "hmm": 0.3,
        "volatility": 0.2,
        "ml_classifier": 0.1  # Optional, Phase 2
    }
    
    def score(self, rules_result, hmm_result, vol_result):
        """Combine methods. Agreement = high confidence."""
        methods = [rules_result, hmm_result, vol_result]
        regimes = [r[0] for r in methods]
        
        # Count agreement
        from collections import Counter
        counts = Counter(regimes)
        most_common = counts.most_common(1)[0]
        
        if most_common[1] >= 2:  # 2/3 or 3/3 agree
            return most_common[0], most_common[1] / len(methods)
        else:
            return "uncertain", 0.3
```

---

## 5. Regime Definitions

### 5.1 Bull / Trending Up

| Attribute | Value |
|-----------|-------|
| Characteristics | Persistent upward drift, rising volatility, high momentum |
| Best strategies | Trend following, momentum, breakout |
| Direction bias | Long (can be 100%) |
| Position sizing | Full or increased (Kelly fraction × 1.2) |
| Stop losses | Trailing stops, wider stops (trends need room) |
| Holding period | Longer (let winners run) |

### 5.2 Bear / Trending Down

| Attribute | Value |
|-----------|-------|
| Characteristics | Persistent downward drift, fear-driven, volatility spikes |
| Best strategies | Short bias, defensive, put spreads |
| Direction bias | Short or hedged |
| Position sizing | Reduced (50–70% of normal) |
| Stop losses | Tighter (bear markets are violent) |
| Cash allocation | 30–50% |

### 5.3 Sideways / Range-Bound

| Attribute | Value |
|-----------|-------|
| Characteristics | Oscillation within band, low directional movement |
| Best strategies | Mean reversion, grid trading, options selling |
| Direction bias | Neutral (long and short) |
| Position sizing | Normal, within defined ranges |
| Stop losses | Tight (range edges are natural stops) |
| Trend following | OFF — it bleeds in chop |

### 5.4 Crisis / High Volatility

| Attribute | Value |
|-----------|-------|
| Characteristics | Violent swings, correlation → 1.0, liquidity evaporation |
| Best strategies | Capital preservation, tail hedging |
| Direction bias | Flat or short |
| Position sizing | Minimal (10–30% of normal) |
| Cash allocation | 70–90% |
| **Rule #1** | **Don't lose money. Rule #2: Don't forget Rule #1.** |

---

## 6. Strategy Adaptation Rules

### Strategy Allocation by Regime

```yaml
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
```

### Position Sizing by Regime

```yaml
position_sizing:
  base_kelly_fraction: 0.25  # Quarter-Kelly for safety
  regime_multiplier:
    trending: 1.2
    ranging: 1.0
    crisis: 0.3
    uncertain: 0.5
  max_portfolio_leverage: 1.5
```

### Red Lines — Always Sit Out

1. **Volatility > 40% annualized** — market is broken
2. **Correlation > 0.9 across all assets** — no diversification exists
3. **HMM "uncertain" for > 5 consecutive days** — model has no idea
4. **3 consecutive losing trades in same direction** — regime may have shifted

---

## 7. Soft Switching Protocol

### Gradual Weight Transitions

Instead of hard regime switches, transition weights over 3–5 days:

```
Day 0: Regime detected as "trending" with 60% confidence
  → Trend weight: 60% → 70%, MR weight: 40% → 30%

Day 3: Confidence rises to 80%
  → Trend weight: 70% → 85%, MR weight: 30% → 15%

Day 7: Confidence at 90%, sustained
  → Trend weight: 85% → 95%, MR weight: 15% → 5%
```

### Implementation

```python
class SoftSwitcher:
    def __init__(self, transition_days=3):
        self.transition_days = transition_days
        self.current_weights = None
        self.target_weights = None
        self.transition_start = None
    
    def update_target(self, new_regime, confidence):
        """Set new target weights based on detected regime."""
        self.target_weights = REGIME_ALLOCATIONS[new_regime]
        self.transition_start = datetime.now()
        self.starting_weights = self.current_weights.copy()
    
    def get_current_weights(self):
        """Interpolate between starting and target weights."""
        if not self.transition_start:
            return self.current_weights
        
        elapsed = (datetime.now() - self.transition_start).days
        progress = min(1.0, elapsed / self.transition_days)
        
        # Smooth interpolation (ease-in-out)
        progress = self._ease_in_out(progress)
        
        weights = {}
        for key in self.target_weights:
            start = self.starting_weights.get(key, 0)
            target = self.target_weights[key]
            weights[key] = start + (target - start) * progress
        
        return weights
    
    def _ease_in_out(self, t):
        """Smooth acceleration/deceleration."""
        return t * t * (3 - 2 * t)
```

---

## 8. Integration Points

### With Strategy Engine
- Strategy weights adjusted by regime
- Signal filtering: trend signals suppressed in ranging regime
- Entry/exit timing aligned with regime confidence

### With Risk Manager
- Position limits scaled by regime multiplier
- Drawdown triggers regime reassessment
- Crisis mode activates maximum risk reduction

### With Alternative Data
- Funding rate extremes confirm crisis detection
- Social sentiment extremes as regime validation
- On-chain flows as trend confirmation

### With Portfolio Manager
- Asset allocation adjusted by regime
- Correlation monitoring for crisis detection
- Cash allocation management per regime

### With TCA Engine
- Spread estimates adjusted by volatility regime
- Slippage multipliers by regime (crisis = 3× normal)
- Cost thresholds adapt to regime

---

## 9. Implementation Roadmap

### Phase 1: Rules-Based Foundation (Week 1)
- [ ] Implement ADX + volatility + return decision tree
- [ ] Basic 3-regime classification (trending/ranging/crisis)
- [ ] Regime-to-strategy-weight mapping
- [ ] Logging and monitoring

### Phase 2: Ensemble Enhancement (Week 2–3)
- [ ] HMM detector with 3-state model
- [ ] Volatility clustering filter
- [ ] Ensemble scorer with agreement-based confidence
- [ ] Soft switching protocol

### Phase 3: Adaptive Thresholds (Week 4+)
- [ ] Rolling percentile thresholds (replace fixed values)
- [ ] Regime duration tracking (transition matrix)
- [ ] Model drift detection and automatic retraining
- [ ] Performance attribution by regime

### Phase 4: ML Enhancement (Month 2+)
- [ ] Train classifier on labeled historical regimes
- [ ] Walk-forward validation (never train on future data)
- [ ] Feature importance analysis
- [ ] A/B testing: ensemble vs rules-only performance

---

*Architecture document for Alpha Stack Market Regime Detection. Based on research findings: regime-aware routing returned 18% (Sharpe 1.6) vs 0% for fixed-strategy portfolios using identical strategies. Volatility is the single most useful regime feature.*
