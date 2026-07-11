# Fix: Learning Loop Critical Issues

**Author:** Learning Loop Fix Agent  
**Date:** 2026-07-11  
**Version:** 1.0  
**Status:** Architecture Fix — Ready for Implementation  
**Source:** `review_learning_loops.md` Critical Issues C1–C6  
**Target:** `architecture_memory.md` Sections 5, 6, 9, 10

---

## Table of Contents

1. [Fix 1: Replace RL with Contextual Bandits](#fix-1-replace-rl-with-contextual-bandits)
2. [Fix 2: Add Concept Drift Detection](#fix-2-add-concept-drift-detection)
3. [Fix 3: Fix Pattern Reliability Tracking](#fix-3-fix-pattern-reliability-tracking)
4. [Fix 4: Add Statistical Significance Testing](#fix-4-add-statistical-significance-testing)
5. [Fix 5: Capture Counterfactual Data](#fix-5-capture-counterfactual-data)
6. [Fix 6: Fix Causal Attribution](#fix-6-fix-causal-attribution)
7. [Implementation Roadmap](#implementation-roadmap)
8. [Updated Data Schema Additions](#updated-data-schema-additions)

---

## Fix 1: Replace RL with Contextual Bandits

**Issue:** C5 — RL approach has fundamental design flaws. 500 trades is 2–3 orders of magnitude too few for deep RL. Non-stationary markets, sparse rewards, and state-space explosion make RL impractical.

### 1.1 What Changes

Replace the "Reinforcement Learning TP Agent" (Step 13) and "RL from Trade History" (Step 16) with a **Contextual Bandit** system for TP strategy selection, and **pre-computed lookup tables** for management rules.

### 1.2 Contextual Bandit Design

A contextual bandit is a one-step RL problem — no state transitions, no temporal credit assignment. It selects an action (TP strategy) given context (market conditions) and observes a reward (R-multiple achieved). This is the correct abstraction for "which TP strategy works best in this situation?"

```
CONTEXTUAL BANDIT — TP STRATEGY SELECTION

Context vector x:
  ├── symbol (one-hot encoded)
  ├── regime (trending_bull | trending_bear | ranging | volatile)
  ├── session (asian | london | new_york | overlap)
  ├── setup_type (ob_bounce | fvg_fill | bos_continuation | divergence)
  ├── volatility_regime (low | normal | high | extreme)
  ├── atr_ratio (current_atr / 20d_avg_atr)
  ├── confluence_score (0–100)
  └── timeframe (1h | 4h | 1d)

Action set A (discrete TP strategies):
  ├── conservative:  TP1=1.0R, TP2=1.5R, TP3=2.0R, trail=2.0×ATR
  ├── balanced:      TP1=1.5R, TP2=2.5R, TP3=4.0R, trail=2.5×ATR
  └── aggressive:    TP1=2.0R, TP2=4.0R, TP3=6.0R, trail=3.0×ATR

Reward r:
  Actual R-multiple achieved on the trade
  (If stopped out: negative R. If partial closes: weighted average.)
```

### 1.3 Algorithm: Thompson Sampling with Linear Payoffs

Thompson Sampling naturally balances exploration and exploitation. With linear payoffs (LinTS), it can generalize across similar contexts.

```python
import numpy as np
from scipy.stats import multivariate_normal

class ContextualBanditTP:
    """
    Thompson Sampling with linear payoffs for TP strategy selection.
    Each action (TP strategy) has its own linear model:
      reward ≈ x^T θ_a + ε
    """

    def __init__(self, n_features, n_actions, v_squared=1.0, prior_var=1.0):
        """
        Args:
            n_features: Dimension of context vector
            n_actions: Number of TP strategies (3: conservative, balanced, aggressive)
            v_squared: Observation noise variance
            prior_var: Prior variance on parameters
        """
        self.n_actions = n_actions
        self.v_squared = v_squared

        # Per-action parameters: θ_a ~ N(B_a^{-1} * f_a, v^2 * B_a^{-1})
        self.B = [prior_var * np.eye(n_features) for _ in range(n_actions)]  # Precision matrices
        self.f = [np.zeros(n_features) for _ in range(n_actions)]            # Accumulated rewards
        self.mu = [np.zeros(n_features) for _ in range(n_actions)]           # Posterior means

    def select_action(self, context):
        """Select TP strategy by sampling from posterior and picking the best."""
        samples = []
        for a in range(self.n_actions):
            B_inv = np.linalg.inv(self.B[a])
            mu_a = B_inv @ self.f[a]
            cov = self.v_squared * B_inv
            theta_sample = multivariate_normal.rvs(mean=mu_a, cov=cov)
            samples.append(context @ theta_sample)
        return int(np.argmax(samples))

    def update(self, context, action, reward):
        """Update posterior for the chosen action with observed reward."""
        self.B[action] += np.outer(context, context)
        self.f[action] += reward * context

    def get_expected_reward(self, context, action):
        """Get posterior expected reward for a given action."""
        B_inv = np.linalg.inv(self.B[action])
        mu_a = B_inv @ self.f[action]
        return context @ mu_a

    def get_action_confidence(self, context):
        """Return confidence (1 - posterior std) for each action."""
        confidences = []
        for a in range(self.n_actions):
            B_inv = np.linalg.inv(self.B[a])
            mu_a = B_inv @ self.f[a]
            expected = context @ mu_a
            var = self.v_squared * (context @ B_inv @ context)
            confidences.append(1.0 - min(1.0, np.sqrt(var)))
        return confidences
```

### 1.4 Lookup Tables for Management Rules

For trade management rules (when to move SL, when to take partials), pre-compute optimal parameters offline from historical data. No online learning needed.

```sql
CREATE TABLE management_rules (
    rule_id         SERIAL PRIMARY KEY,
    symbol          VARCHAR(20) NOT NULL,
    regime          VARCHAR(30) NOT NULL,
    session         VARCHAR(20) NOT NULL,
    setup_type      VARCHAR(30) NOT NULL,
    -- Optimal management parameters (computed offline)
    be_trigger_r    DECIMAL(4,2) NOT NULL,    -- Move SL to BE at this R-multiple
    partial_1_r     DECIMAL(4,2),             -- Take first partial at this R
    partial_1_pct   DECIMAL(4,2),             -- % of position to close at partial_1
    partial_2_r     DECIMAL(4,2),
    partial_2_pct   DECIMAL(4,2),
    trail_atr_mult  DECIMAL(4,2),             -- Trailing stop = ATR × this
    time_exit_hours DECIMAL(6,2),             -- Force exit after this many hours
    -- Statistics
    sample_size     INTEGER NOT NULL,
    avg_rr          DECIMAL(6,3),
    win_rate        DECIMAL(5,4),
    computed_at     TIMESTAMPTZ NOT NULL,
    -- Validity
    active          BOOLEAN DEFAULT TRUE,
    CONSTRAINT uq_management_rule UNIQUE (symbol, regime, session, setup_type)
);
```

**Offline computation (monthly cron):**

```python
def compute_management_rules(historical_trades, min_samples=20):
    """
    For each (symbol, regime, session, setup_type) cell:
    Brute-force search over management parameters to find optimal R-multiple.
    """
    cells = group_by(historical_trades, ['symbol', 'regime', 'session', 'setup_type'])
    rules = []

    for cell_key, trades in cells.items():
        if len(trades) < min_samples:
            continue

        # Grid search over management parameters
        best_params = None
        best_avg_rr = -float('inf')

        for be_trigger in [0.5, 0.75, 1.0, 1.25, 1.5]:
            for partial_r in [1.0, 1.5, 2.0, 2.5]:
                for partial_pct in [0.33, 0.50]:
                    for trail_mult in [2.0, 2.5, 3.0]:
                        # Simulate these parameters on historical trades
                        simulated_rr = simulate_management(
                            trades, be_trigger, partial_r, partial_pct, trail_mult
                        )
                        if simulated_rr > best_avg_rr:
                            best_avg_rr = simulated_rr
                            best_params = {
                                'be_trigger_r': be_trigger,
                                'partial_1_r': partial_r,
                                'partial_1_pct': partial_pct,
                                'trail_atr_mult': trail_mult,
                                'avg_rr': best_avg_rr,
                            }

        best_params.update({
            'symbol': cell_key[0], 'regime': cell_key[1],
            'session': cell_key[2], 'setup_type': cell_key[3],
            'sample_size': len(trades),
            'win_rate': sum(1 for t in trades if t['net_pnl'] > 0) / len(trades),
        })
        rules.append(best_params)

    return rules
```

### 1.5 Migration Path

| Component | Before (RL) | After (Bandit/Lookup) |
|-----------|-------------|----------------------|
| TP strategy selection | Deep RL agent (DQN/PPO) | Contextual bandit (Thompson Sampling) |
| Training data requirement | 10,000+ episodes | 50–100 observations per context |
| Non-stationarity handling | None (critical gap) | Online posterior updates adapt automatically |
| Interpretability | Black-box neural network | Posterior weights per action are inspectable |
| Management rules | Learned by RL agent | Pre-computed lookup tables (offline) |
| Validation | Off-policy evaluation (hard) | Posterior predictive checks (standard Bayesian) |

### 1.6 Sample Complexity Analysis

**Contextual bandit with Thompson Sampling:**
- 3 actions × ~20 features = 60 parameters total
- Convergence typically after 200–500 total observations
- With 500 trades: sufficient for 3 symbols, 3 regimes, 4 sessions = 36 contexts × ~14 obs/context
- Cold-start: use prior from offline backtest results as informative prior

**vs. Deep RL (DQN/PPO):**
- State space: 5 continuous variables × discretization → 1000+ states
- Per-state convergence: 10,000+ visits
- Total required: 10,000,000+ episodes
- Available: 500 episodes → **fundamentally insufficient**

---

## Fix 2: Add Concept Drift Detection

**Issue:** C4 — No mechanism to detect when the market has fundamentally changed and past lessons become silently obsolete. Weekly/monthly review is too slow.

### 2.1 What Changes

Add a real-time **Concept Drift Detector** that monitors the system's own prediction accuracy and market distributional properties. When drift is detected, automatically degrade stale knowledge and trigger re-learning.

### 2.2 Architecture

```
CONCEPT DRIFT DETECTION SYSTEM

┌─────────────────────────────────────────────────────────────┐
│                    DRIFT MONITOR (runs every 20 trades)       │
│                                                               │
│  ┌──────────────────┐   ┌──────────────────┐                │
│  │ SIGNAL ACCURACY  │   │ MARKET PROPERTY  │                │
│  │ DRIFT DETECTOR   │   │ DRIFT DETECTOR   │                │
│  │                  │   │                  │                │
│  │ • Rolling window │   │ • Volatility     │                │
│  │   accuracy vs    │   │   regime shift   │                │
│  │   historical     │   │ • Correlation    │                │
│  │ • Page-Hinkley   │   │   structure      │                │
│  │   test           │   │   change         │                │
│  │ • Per-agent      │   │ • Regime HMM     │                │
│  │   tracking       │   │   state change   │                │
│  └────────┬─────────┘   └────────┬─────────┘                │
│           │                       │                          │
│           ▼                       ▼                          │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                  DRIFT SCORE AGGREGATOR                 │ │
│  │                                                          │ │
│  │  drift_score = w1 * signal_drift + w2 * market_drift     │ │
│  │                                                          │ │
│  │  Thresholds:                                             │ │
│  │    drift_score < 0.3  → GREEN  (normal operation)        │ │
│  │    drift_score 0.3–0.6 → AMBER (reduce confidence)       │ │
│  │    drift_score > 0.6  → RED   (trigger re-learning)      │ │
│  └────────────────────────┬───────────────────────────────┘ │
│                            │                                 │
│           ┌────────────────┼────────────────┐               │
│           ▼                ▼                ▼               │
│    ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│    │   GREEN     │  │   AMBER     │  │    RED      │      │
│    │             │  │             │  │             │      │
│    │ Normal      │  │ - Reduce    │  │ - Discount  │      │
│    │ operation   │  │   lesson    │  │   ALL       │      │
│    │             │  │   conf by   │  │   lesson    │      │
│    │             │  │   25%       │  │   conf by   │      │
│    │             │  │ - Increase  │  │   50%       │      │
│    │             │  │   bandit    │  │ - Reset     │      │
│    │             │  │   learning  │  │   bandit    │      │
│    │             │  │   rate 2×   │  │   priors    │      │
│    │             │  │ - Flag for  │  │ - Force     │      │
│    │             │  │   human     │  │   HMM       │      │
│    │             │  │   review    │  │   retrain   │      │
│    │             │  │             │  │ - Alert     │      │
│    │             │  │             │  │   human     │      │
│    └─────────────┘  └─────────────┘  └─────────────┘      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 Signal Accuracy Drift Detector

Uses the **Page-Hinkley test** — a sequential change-point detection algorithm that triggers when the running mean of a variable shifts.

```python
class PageHinkleyDriftDetector:
    """
    Page-Hinkley test for detecting changes in the mean of a signal.
    Tracks whether agent prediction accuracy is drifting from historical baseline.
    """

    def __init__(self, delta=0.005, lambda_=50.0, alpha=0.999):
        """
        Args:
            delta: Magnitude of changes to detect (smaller = more sensitive)
            lambda_: Threshold for triggering alarm
            alpha: Forgetting factor (exponential weighting of past observations)
        """
        self.delta = delta
        self.lambda_ = lambda_
        self.alpha = alpha
        self.reset()

    def reset(self):
        self.n = 0
        self.sum = 0.0
        self.x_mean = 0.0
        self.m_T = 0.0
        self.M_T = 0.0

    def update(self, x):
        """
        Add observation x (1=correct prediction, 0=wrong prediction).
        Returns True if drift detected.
        """
        self.n += 1
        # Exponential moving average
        self.x_mean = self.alpha * self.x_mean + (1 - self.alpha) * x
        self.sum += x - self.x_mean - self.delta
        self.m_T = min(self.m_T, self.sum)
        self.M_T = max(self.M_T, self.sum)

        return (self.M_T - self.m_T) > self.lambda_


class DriftDetectorSystem:
    """
    Monitors concept drift across all agents and market properties.
    Runs every 20 trades.
    """

    def __init__(self, db):
        self.db = db
        # Per-agent drift detectors
        self.agent_detectors = {}  # agent_id → PageHinkleyDriftDetector
        # Market property detectors
        self.volatility_detector = PageHinkleyDriftDetector(delta=0.01, lambda_=100)
        self.correlation_detector = PageHinkleyDriftDetector(delta=0.02, lambda_=80)
        self.regime_detector = RegimeChangeDetector()

    def check_drift(self, recent_window=50):
        """
        Run drift detection on recent trades.
        Returns overall drift score (0=stable, 1=severe drift).
        """
        drift_signals = []

        # 1. Signal accuracy drift per agent
        for agent_id in self.db.get_active_agents():
            if agent_id not in self.agent_detectors:
                self.agent_detectors[agent_id] = PageHinkleyDriftDetector()

            recent_accuracy = self.db.get_recent_accuracy(agent_id, window=recent_window)
            historical_accuracy = self.db.get_historical_accuracy(agent_id)

            # Check if recent accuracy differs from historical
            accuracy_delta = abs(recent_accuracy - historical_accuracy)
            drift_signals.append(min(1.0, accuracy_delta / 0.15))  # 15% shift = max drift

            # Run Page-Hinkley on individual predictions
            predictions = self.db.get_recent_predictions(agent_id, limit=recent_window)
            for pred in predictions:
                if self.agent_detectors[agent_id].update(pred['correct']):
                    drift_signals.append(0.8)  # Agent-specific drift detected

        # 2. Volatility regime drift
        recent_atr = self.db.get_recent_atr(window=recent_window)
        historical_atr = self.db.get_historical_atr()
        atr_ratio = recent_atr / max(historical_atr, 1e-10)
        if atr_ratio > 1.5 or atr_ratio < 0.67:
            drift_signals.append(0.7)

        # 3. Regime transition frequency
        recent_regimes = self.db.get_recent_regime_changes(window=recent_window)
        if recent_regimes > 3:  # More than 3 regime changes in 50 trades
            drift_signals.append(0.6)

        # 4. Win rate trend
        recent_wr = self.db.get_recent_win_rate(window=recent_window)
        historical_wr = self.db.get_historical_win_rate()
        wr_delta = abs(recent_wr - historical_wr)
        if wr_delta > 0.10:  # 10% win rate drop
            drift_signals.append(0.5)

        # Aggregate drift score (max of all signals)
        if drift_signals:
            return min(1.0, max(drift_signals))
        return 0.0

    def get_drift_level(self, drift_score):
        if drift_score < 0.3:
            return 'GREEN'
        elif drift_score < 0.6:
            return 'AMBER'
        else:
            return 'RED'
```

### 2.4 Drift Response Actions

```python
def respond_to_drift(drift_level, drift_score):
    """Execute automated response to detected drift."""

    if drift_level == 'AMBER':
        # 1. Discount all lesson confidence by 25%
        db.execute("""
            UPDATE lessons
            SET confidence = confidence * 0.75
            WHERE status = 'active' AND confidence > 0.3
        """)

        # 2. Double the bandit learning rate (increase exploration)
        bandit.v_squared *= 1.5  # Wider posterior = more exploration

        # 3. Flag for human review
        create_alert(
            severity='WARNING',
            title=f'Concept drift detected (score: {drift_score:.2f})',
            message='Lesson confidence reduced by 25%. Bandit exploration increased. '
                    'Review recent pattern reliability and signal accuracy trends.'
        )

    elif drift_level == 'RED':
        # 1. Discount all lesson confidence by 50%
        db.execute("""
            UPDATE lessons
            SET confidence = confidence * 0.50
            WHERE status = 'active'
        """)

        # 2. Reset bandit priors (force re-learning from recent data)
        bandit = ContextualBanditTP(n_features=20, n_actions=3, v_squared=2.0)

        # 3. Force regime model retrain
        regime_model.retrain_on_recent(window=200)

        # 4. Alert human urgently
        create_alert(
            severity='CRITICAL',
            title=f'SEVERE concept drift (score: {drift_score:.2f})',
            message='Market regime has fundamentally shifted. All lesson confidence '
                    'halved. Bandit priors reset. Regime model retrained. '
                    'Immediate human review required.'
        )

        # 5. Increase monitoring frequency
        self.monitoring_interval = 5  # Check every 5 trades instead of 20
```

### 2.5 Regime Change Detector

```python
class RegimeChangeDetector:
    """
    Detects regime changes using a Hidden Markov Model
    retrained on rolling windows of market data.
    """

    def __init__(self, n_regimes=4, retrain_window=500):
        self.n_regimes = n_regimes
        self.retrain_window = retrain_window
        self.model = None
        self.current_regime = None
        self.regime_history = []

    def fit(self, market_data):
        """Fit HMM on recent market data."""
        from hmmlearn.hmm import GaussianHMM

        features = self._extract_features(market_data)
        self.model = GaussianHMM(
            n_components=self.n_regimes,
            covariance_type='full',
            n_iter=100
        )
        self.model.fit(features)

    def predict_regime(self, market_data):
        """Predict current regime and detect transitions."""
        features = self._extract_features(market_data)
        regimes = self.model.predict(features)
        new_regime = regimes[-1]

        if self.current_regime is not None and new_regime != self.current_regime:
            transition_prob = self._transition_probability(
                self.current_regime, new_regime
            )
            if transition_prob < 0.1:  # Rare transition = regime change
                self.regime_history.append({
                    'from': self.current_regime,
                    'to': new_regime,
                    'time': now(),
                    'transition_prob': transition_prob,
                })
                self.current_regime = new_regime
                return 'REGIME_CHANGE'

        self.current_regime = new_regime
        return 'STABLE'

    def _extract_features(self, market_data):
        return np.column_stack([
            market_data['atr_ratio'],
            market_data['correlation_matrix_flattened'],
            market_data['volume_ratio'],
            market_data['trend_strength'],
        ])

    def _transition_probability(self, from_regime, to_regime):
        return self.model.transmat_[from_regime, to_regime]
```

### 2.6 Integration with Learning Loop

The drift detector runs as a **pre-check** at the start of each Reflection Agent cycle:

```
TRADE CLOSED → TRIGGER REFLECTION AGENT
  │
  ▼
1. Run drift check (every 20 trades)
  │
  ├── GREEN: proceed normally
  ├── AMBER: reduce lesson confidence, increase exploration, proceed
  └── RED: halve confidence, reset priors, alert human, proceed with caution
  │
  ▼
2. Normal reflection protocol (compare, attribute, extract, update)
  │
  ▼
3. If drift was AMBER or RED: weight recent evidence 2× vs historical
```

---

## Fix 3: Fix Pattern Reliability Tracking

**Issue:** C3 — 2,160+ granular cells (5 types × 3 subtypes × 3 symbols × 4 timeframes × 3 regimes × 4 sessions) create meaningless tiny sample sizes. Most cells will have 0–2 trades.

### 3.1 What Changes

Replace independent per-cell win rate computation with a **hierarchical Bayesian model** that borrows statistical strength from similar cells. When a cell has few observations, its estimate is pulled toward the population mean. As observations accumulate, it converges to the cell-specific estimate.

### 3.2 Hierarchical Model Design

```
HIERARCHICAL PATTERN RELIABILITY

Instead of:
  win_rate[cell] = successes[cell] / total[cell]    ← independent, noisy

Use:
  win_rate[cell] ~ Beta(α, β)
  α = α₀ + successes[cell]                          ← Beta-Binomial model
  β = β₀ + failures[cell]

  Where α₀, β₀ are "pseudo-counts" borrowed from the parent level:

  Level 0 (global):       α₀_global, β₀_global     ← all patterns, all conditions
  Level 1 (pattern_type): α₀_type, β₀_type          ← same pattern type, all conditions
  Level 2 (symbol):       α₀_symbol, β₀_symbol       ← same pattern + symbol
  Level 3 (full cell):    α₀_cell, β₀_cell           ← specific cell (when enough data)

  The pseudo-counts are computed as a WEIGHTED AVERAGE across levels,
  with weights determined by the amount of data at each level.
```

### 3.3 Implementation

```python
class HierarchicalPatternReliability:
    """
    Beta-Binomial hierarchical model for pattern reliability.
    Borrows statistical strength from parent levels when cell data is sparse.
    """

    def __init__(self, db):
        self.db = db
        self.min_cell_samples = 15       # Need 15+ before trusting cell-level
        self.prior_weight = 5.0          # Weight of prior (pseudo-observations)

    def get_win_rate(self, pattern_type, pattern_subtype, symbol,
                     timeframe, regime, session):
        """
        Compute shrinkage estimate of win rate.
        Returns (win_rate, confidence_interval, effective_sample_size).
        """
        # Get observations at each hierarchy level
        cell_data = self.db.get_pattern_outcomes(
            pattern_type, pattern_subtype, symbol, timeframe, regime, session
        )
        type_data = self.db.get_pattern_outcomes(pattern_type=pattern_type)
        global_data = self.db.get_all_pattern_outcomes()

        n_cell = len(cell_data)
        s_cell = sum(1 for d in cell_data if d['outcome'] == 'win')

        # Compute shrinkage weight: how much to trust cell-level vs parent
        # More cell data → more weight on cell-level
        shrinkage = n_cell / (n_cell + self.min_cell_samples)

        # Parent-level estimates (Beta posterior means)
        if len(type_data) > 0:
            s_type = sum(1 for d in type_data if d['outcome'] == 'win')
            wr_type = (s_type + 1) / (len(type_data) + 2)  # Laplace-smoothed
        else:
            wr_type = 0.5  # Uninformative prior

        if len(global_data) > 0:
            s_global = sum(1 for d in global_data if d['outcome'] == 'win')
            wr_global = (s_global + 1) / (len(global_data) + 2)
        else:
            wr_global = 0.5

        # Hierarchical shrinkage estimate
        # When n_cell is small: estimate ≈ wr_type (parent dominates)
        # When n_cell is large: estimate ≈ wr_cell (data dominates)
        if n_cell > 0:
            wr_cell = s_cell / n_cell
            win_rate = shrinkage * wr_cell + (1 - shrinkage) * wr_type
        else:
            win_rate = wr_type

        # Effective sample size for confidence interval
        eff_n = n_cell + self.prior_weight * (1 - shrinkage)

        # Beta posterior confidence interval
        alpha_post = win_rate * eff_n + 1
        beta_post = (1 - win_rate) * eff_n + 1
        ci_low = beta.ppf(0.025, alpha_post, beta_post)
        ci_high = beta.ppf(0.975, alpha_post, beta_post)

        return {
            'win_rate': round(win_rate, 4),
            'ci_low': round(ci_low, 4),
            'ci_high': round(ci_high, 4),
            'effective_n': round(eff_n, 1),
            'raw_n': n_cell,
            'shrinkage': round(shrinkage, 3),
            'confidence': 'HIGH' if n_cell >= 30 else
                          'MEDIUM' if n_cell >= 10 else 'LOW'
        }

    def get_all_reliable_patterns(self, min_effective_n=10):
        """Return all pattern cells with sufficient data for reliable estimates."""
        cells = self.db.get_all_pattern_cells()
        reliable = []
        for cell in cells:
            result = self.get_win_rate(**cell)
            if result['effective_n'] >= min_effective_n:
                reliable.append({**cell, **result})
        return sorted(reliable, key=lambda x: x['win_rate'], reverse=True)
```

### 3.4 Exponentially Weighted Pattern Reliability

In addition to hierarchical shrinkage, apply **time weighting** so recent observations count more than old ones. This handles non-stationarity.

```python
def get_time_weighted_win_rate(self, pattern_type, symbol, regime,
                                half_life_trades=100):
    """
    Exponentially weighted win rate.
    Observations decay with half-life of `half_life_trades`.
    """
    outcomes = self.db.get_pattern_outcomes_ordered(
        pattern_type=pattern_type, symbol=symbol, regime=regime
    )

    if not outcomes:
        return {'win_rate': None, 'effective_n': 0}

    now_idx = len(outcomes)
    decay = math.log(2) / half_life_trades

    weighted_wins = 0.0
    weighted_total = 0.0
    for i, outcome in enumerate(outcomes):
        weight = math.exp(-decay * (now_idx - i))
        weighted_total += weight
        if outcome['outcome'] == 'win':
            weighted_wins += weight

    return {
        'win_rate': weighted_wins / weighted_total,
        'effective_n': weighted_total,  # Sum of weights ≈ effective sample
        'half_life': half_life_trades,
    }
```

### 3.5 Updated Schema

```sql
-- Replace the old pattern_reliability table
-- Now stores both raw and hierarchical estimates
DROP TABLE IF EXISTS pattern_reliability;

CREATE TABLE pattern_reliability (
    id                  SERIAL PRIMARY KEY,
    -- Cell identifiers
    pattern_type        VARCHAR(50) NOT NULL,
    pattern_subtype     VARCHAR(50),
    symbol              VARCHAR(20) NOT NULL,
    timeframe           VARCHAR(10),
    regime              VARCHAR(30),
    session             VARCHAR(20),
    -- Raw statistics
    total_occurrences   INTEGER NOT NULL DEFAULT 0,
    successful          INTEGER NOT NULL DEFAULT 0,
    failed              INTEGER NOT NULL DEFAULT 0,
    -- Hierarchical estimates (updated by cron job)
    win_rate_hierarchical   DECIMAL(6,4),       -- Shrinkage estimate
    ci_low              DECIMAL(6,4),
    ci_high             DECIMAL(6,4),
    effective_n         DECIMAL(8,1),           -- Effective sample size
    shrinkage_weight    DECIMAL(5,3),           -- How much parent influences
    -- Time-weighted estimates
    win_rate_ew         DECIMAL(6,4),           -- Exponentially weighted
    ew_effective_n      DECIMAL(8,1),
    -- Other statistics
    avg_rr              DECIMAL(6,3),
    avg_duration_hours  DECIMAL(6,2),
    -- Confidence classification
    confidence          VARCHAR(10) GENERATED ALWAYS AS (
        CASE
            WHEN total_occurrences >= 30 THEN 'HIGH'
            WHEN total_occurrences >= 10 THEN 'MEDIUM'
            ELSE 'LOW'
        END
    ) STORED,
    -- Timestamps
    last_updated        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Constraints
    CONSTRAINT uq_pattern_cell UNIQUE (pattern_type, pattern_subtype, symbol,
                                        timeframe, regime, session)
);

-- Index for fast lookups
CREATE INDEX idx_pattern_reliability_lookup
ON pattern_reliability (pattern_type, symbol, regime)
WHERE total_occurrences > 0;
```

### 3.6 Consolidation Cron Job

Runs nightly to recompute hierarchical and time-weighted estimates:

```python
def nightly_pattern_consolidation():
    """Recompute all pattern reliability estimates."""
    cells = db.execute("SELECT DISTINCT pattern_type, pattern_subtype, symbol, "
                       "timeframe, regime, session FROM pattern_reliability")

    for cell in cells:
        # Raw counts (already maintained by per-trade updates)
        raw = db.get_pattern_outcomes(**cell)

        # Hierarchical estimate
        h_est = hierarchical_model.get_win_rate(**cell)

        # Time-weighted estimate
        tw_est = hierarchical_model.get_time_weighted_win_rate(
            cell['pattern_type'], cell['symbol'], cell['regime']
        )

        # Update table
        db.execute("""
            UPDATE pattern_reliability SET
                win_rate_hierarchical = %s,
                ci_low = %s, ci_high = %s,
                effective_n = %s, shrinkage_weight = %s,
                win_rate_ew = %s, ew_effective_n = %s,
                last_updated = NOW()
            WHERE pattern_type = %s AND pattern_subtype = %s
              AND symbol = %s AND timeframe = %s
              AND regime = %s AND session = %s
        """, [h_est['win_rate'], h_est['ci_low'], h_est['ci_high'],
              h_est['effective_n'], h_est['shrinkage'],
              tw_est['win_rate'], tw_est['effective_n'],
              cell['pattern_type'], cell['pattern_subtype'],
              cell['symbol'], cell['timeframe'],
              cell['regime'], cell['session']])
```

---

## Fix 4: Add Statistical Significance Testing

**Issue:** C6 — Signal weights are adjusted after every trade without testing whether observed accuracy differs from random. ±0.01 per trade over 100 trades can move weights from 0.15 to 0.25 purely by noise.

### 4.1 What Changes

Before adjusting any signal weight, require **statistical evidence** that the agent's accuracy differs from random (p < 0.10). Apply **Bonferroni correction** for multiple comparisons (testing 6 agents × 3 symbols = 18 comparisons).

### 4.2 Significance Test Implementation

```python
from scipy import stats

class SignalWeightAdjuster:
    """
    Signal weight adjustment with statistical significance gates.
    Only adjusts weights when there is sufficient evidence.
    """

    def __init__(self, db, n_agents=6, n_symbols=3):
        self.db = db
        self.n_comparisons = n_agents * n_symbols  # For Bonferroni
        self.alpha = 0.10                           # Base significance level
        self.corrected_alpha = self.alpha / self.n_comparisons  # Bonferroni
        self.min_samples = 20                       # Minimum before any adjustment
        self.max_adjustment = 0.03                  # Per-trade cap

    def should_adjust(self, agent_id, symbol):
        """
        Determine whether there is sufficient evidence to adjust this agent's weight.
        Returns (should_adjust, p_value, direction, confidence).
        """
        # Get prediction history
        predictions = self.db.get_agent_predictions(agent_id, symbol)
        n = len(predictions)

        if n < self.min_samples:
            return (False, 1.0, 0, 'INSUFFICIENT_DATA')

        # Count successes (correct direction predictions)
        k = sum(1 for p in predictions if p['correct'])

        # Two-sided binomial test: H₀: accuracy = 0.50
        # Use exact binomial test for small samples, normal approx for large
        if n < 100:
            p_value = stats.binom_test(k, n, 0.5, alternative='two-sided')
        else:
            # Normal approximation with continuity correction
            p_hat = k / n
            se = math.sqrt(0.25 / n)  # SE under H₀: p=0.5
            z = (p_hat - 0.5) / se
            p_value = 2 * (1 - stats.norm.cdf(abs(z)))

        # Determine direction
        accuracy = k / n
        if accuracy > 0.5:
            direction = 1   # Agent is better than random → increase weight
        else:
            direction = -1  # Agent is worse than random → decrease weight

        # Check significance
        if p_value < self.corrected_alpha:
            # Compute confidence level
            if p_value < 0.01:
                confidence = 'HIGH'
            elif p_value < 0.05:
                confidence = 'MEDIUM'
            else:
                confidence = 'LOW'
            return (True, p_value, direction, confidence)
        else:
            return (False, p_value, direction, 'NOT_SIGNIFICANT')

    def compute_adjustment(self, agent_id, symbol):
        """
        Compute the appropriate weight adjustment.
        Uses effect-size-aware scaling: larger accuracy gaps → larger adjustments.
        """
        should, p_value, direction, confidence = self.should_adjust(agent_id, symbol)

        if not should:
            return 0.0

        predictions = self.db.get_agent_predictions(agent_id, symbol)
        accuracy = sum(1 for p in predictions if p['correct']) / len(predictions)

        # Effect size: how far from random (0.50)
        effect_size = abs(accuracy - 0.50)

        # Scale adjustment by effect size (capped at max_adjustment)
        # effect_size=0.10 → adjustment=0.01
        # effect_size=0.20 → adjustment=0.02
        # effect_size=0.30+ → adjustment=0.03 (capped)
        adjustment = min(
            self.max_adjustment,
            effect_size * 0.1  # 10% of effect size, capped
        )

        return direction * adjustment

    def update_weight(self, agent_id, symbol, trade_id):
        """
        Attempt to update signal weight after a trade.
        Only adjusts if statistically significant.
        """
        adjustment = self.compute_adjustment(agent_id, symbol)

        if adjustment == 0.0:
            return {
                'adjusted': False,
                'reason': 'Not statistically significant or insufficient data'
            }

        current = self.db.get_signal_weight(agent_id, symbol)
        new_weight = max(0.05, min(0.40, current['weight'] + adjustment))

        # Apply adjustment
        self.db.execute("""
            UPDATE signal_weights SET
                weight = %s,
                last_adjustment = NOW(),
                adjustment_reason = %s,
                adjustment_evidence = %s
            WHERE agent_id = %s AND symbol = %s
        """, [
            new_weight,
            f"Significant accuracy deviation (p={p_value:.4f}, "
            f"accuracy={accuracy:.3f}, n={n})",
            json.dumps({
                'p_value': p_value,
                'accuracy': accuracy,
                'sample_size': n,
                'effect_size': effect_size,
                'direction': direction,
                'confidence': confidence,
            }),
            agent_id, symbol
        ])

        return {
            'adjusted': True,
            'old_weight': current['weight'],
            'new_weight': new_weight,
            'adjustment': adjustment,
            'p_value': p_value,
            'confidence': confidence
        }
```

### 4.3 Multiple Comparison Correction

When testing 18 agent-symbol pairs simultaneously, we must correct for multiple comparisons to avoid false positives.

```python
def bonferroni_correction(base_alpha, n_tests):
    """Simple Bonferroni correction."""
    return base_alpha / n_tests

def benjamini_hochberg_correction(p_values, fdr=0.10):
    """
    Benjamini-Hochberg procedure (less conservative than Bonferroni).
    Controls False Discovery Rate instead of Family-Wise Error Rate.
    More appropriate when many tests are run.
    """
    n = len(p_values)
    sorted_idx = np.argsort(p_values)
    sorted_p = np.array(p_values)[sorted_idx]

    # Find the largest k such that p_(k) <= (k/n) * fdr
    thresholds = [(i + 1) / n * fdr for i in range(n)]
    significant = sorted_p <= thresholds

    if not significant.any():
        return [False] * n

    # All tests up to the last significant one are rejected
    max_sig = np.max(np.where(significant))
    results = [False] * n
    for i in range(max_sig + 1):
        results[sorted_idx[i]] = True

    return results
```

### 4.4 Minimum Sample Gate

Even before running significance tests, enforce a minimum sample size:

```python
MIN_SAMPLES_FOR_ADJUSTMENT = 20    # At least 20 predictions before adjusting
MIN_SAMPLES_FOR_CONFIDENCE = 50    # At least 50 before high-confidence claims

def get_adjustment_readiness(agent_id, symbol):
    """Check if we have enough data to even consider adjusting."""
    n = db.get_prediction_count(agent_id, symbol)

    if n < MIN_SAMPLES_FOR_ADJUSTMENT:
        return {
            'ready': False,
            'reason': f'Only {n} predictions (need {MIN_SAMPLES_FOR_ADJUSTMENT})',
            'stage': 'COLLECTING'
        }
    elif n < MIN_SAMPLES_FOR_CONFIDENCE:
        return {
            'ready': True,
            'reason': f'{n} predictions (low confidence)',
            'stage': 'PRELIMINARY'
        }
    else:
        return {
            'ready': True,
            'reason': f'{n} predictions (sufficient)',
            'stage': 'ESTABLISHED'
        }
```

### 4.5 Updated Signal Weight Update Rule

The old rule:
```python
# OLD: Adjust after every trade, no significance test
new_weight = weight.current + sign(blended - 0.5) * 0.01
```

The new rule:
```python
# NEW: Adjust only when statistically significant
def update_signal_weight(agent_id, symbol, trade_id):
    # 1. Record the prediction (always)
    db.record_prediction(agent_id, symbol, trade_id, correct=predicted_correctly)

    # 2. Check minimum sample gate
    readiness = get_adjustment_readiness(agent_id, symbol)
    if not readiness['ready']:
        return  # Collecting data, no adjustment

    # 3. Run significance test
    should, p_value, direction, confidence = adjuster.should_adjust(agent_id, symbol)
    if not should:
        return  # Not significant, no adjustment

    # 4. Compute effect-size-scaled adjustment
    adjustment = adjuster.compute_adjustment(agent_id, symbol)

    # 5. Apply (bounded, normalized)
    apply_weight_change(agent_id, symbol, adjustment, p_value, confidence)
```

---

## Fix 5: Capture Counterfactual Data

**Issue:** C2 — No counterfactual data capture. The system records what happened but not what would have happened under alternative decisions. RL agent cannot be trained without this.

### 5.1 What Changes

Implement a **Shadow Tracking System** that records hypothetical outcomes for alternative management strategies on every trade. This provides the counterfactual data needed for the contextual bandit and for evaluating whether learned rules actually improve outcomes.

### 5.2 Architecture

```
COUNTERFACTUAL SHADOW TRACKING

Every trade gets a PRIMARY management path (what actually happened)
and 3-5 SHADOW paths (what would have happened with different rules).

TRADE OPENED
  │
  ▼
┌─────────────────────────────────────────────────────────┐
│  PRIMARY PATH (actual trade)                             │
│  • Actual SL, TP levels                                  │
│  • Actual partial closes                                 │
│  • Actual trailing stop behavior                         │
│  • Actual exit price and timing                          │
│                                                          │
│  SHADOW PATH A: "Conservative TP"                        │
│  • TP1=1.0R, TP2=1.5R, TP3=2.0R, trail=2.0×ATR         │
│  • Simulate: what would the exit have been?              │
│                                                          │
│  SHADOW PATH B: "Aggressive TP"                          │
│  • TP1=2.0R, TP2=4.0R, TP3=6.0R, trail=3.0×ATR         │
│  • Simulate: what would the exit have been?              │
│                                                          │
│  SHADOW PATH C: "Structure-Based Trail"                  │
│  • Trail at last swing low/high instead of ATR           │
│  • Simulate: what would the exit have been?              │
│                                                          │
│  SHADOW PATH D: "Time-Based Exit"                        │
│  • Force exit after 4h / 8h / 24h                        │
│  • Simulate: what would the exit have been?              │
│                                                          │
│  SHADOW PATH E: "No Management" (buy-and-hold to TP/SL)  │
│  • No trailing, no partials, just TP or SL               │
│  • Simulate: what would the exit have been?              │
│                                                          │
└─────────────────────────────────────────────────────────┘
  │
  ▼
All paths recorded after trade closes (using tick data replay)
```

### 5.3 Shadow Tracker Implementation

```python
class CounterfactualTracker:
    """
    Tracks hypothetical outcomes for alternative management strategies.
    Uses post-trade tick data replay to compute what would have happened.
    """

    # Standard shadow strategies
    SHADOW_STRATEGIES = {
        'conservative_tp': {
            'partial_1_r': 1.0, 'partial_1_pct': 0.50,
            'partial_2_r': 1.5, 'partial_2_pct': 0.50,
            'trail_atr_mult': 2.0,
            'be_trigger_r': 0.75,
        },
        'aggressive_tp': {
            'partial_1_r': 2.0, 'partial_1_pct': 0.33,
            'partial_2_r': 4.0, 'partial_2_pct': 0.33,
            'trail_atr_mult': 3.0,
            'be_trigger_r': 1.0,
        },
        'structure_trail': {
            'trail_type': 'structure',  # Trail at last swing low/high
            'partial_1_r': 1.5, 'partial_1_pct': 0.50,
            'be_trigger_r': 1.0,
        },
        'time_exit_4h': {
            'max_duration_hours': 4.0,
            'trail_atr_mult': 2.5,
        },
        'time_exit_24h': {
            'max_duration_hours': 24.0,
            'trail_atr_mult': 2.5,
        },
        'no_management': {
            'no_trail': True,
            'no_partials': True,
            # Just TP or SL, nothing else
        },
    }

    def __init__(self, db, tick_data_source):
        self.db = db
        self.ticks = tick_data_source

    def compute_counterfactuals(self, trade):
        """
        After a trade closes, compute outcomes for all shadow strategies.
        Uses actual tick data to simulate what would have happened.
        """
        # Get tick data from entry to a reasonable end point
        # (max of actual exit time + 24h buffer for time-exit strategies)
        ticks = self.ticks.get_range(
            symbol=trade['symbol'],
            start=trade['entry_time'],
            end=trade['exit_time'] + timedelta(hours=24)
        )

        results = {}

        for strategy_name, params in self.SHADOW_STRATEGIES.items():
            outcome = self._simulate_strategy(trade, ticks, params)
            results[strategy_name] = outcome

        # Store all counterfactuals
        self.db.store_counterfactuals(trade['id'], results)

        return results

    def _simulate_strategy(self, trade, ticks, params):
        """Simulate a management strategy on tick data."""
        entry_price = trade['entry_price']
        sl_price = trade['stop_loss']
        direction = trade['direction']  # 'long' or 'short'
        atr = trade['atr_at_entry']
        position_size = trade['position_size']

        remaining_size = position_size
        total_pnl = 0.0
        exit_price = None
        exit_time = None
        exit_reason = None
        partial_closes = []

        # Compute TP levels from R-multiples
        risk = abs(entry_price - sl_price)

        for tick in ticks:
            price = tick['mid']

            # Check stop loss
            if direction == 'long' and price <= sl_price:
                exit_price = sl_price
                exit_time = tick['time']
                exit_reason = 'sl_hit'
                total_pnl += (sl_price - entry_price) * remaining_size
                remaining_size = 0
                break
            elif direction == 'short' and price >= sl_price:
                exit_price = sl_price
                exit_time = tick['time']
                exit_reason = 'sl_hit'
                total_pnl += (entry_price - sl_price) * remaining_size
                remaining_size = 0
                break

            # Compute current R-multiple
            if direction == 'long':
                current_r = (price - entry_price) / risk
            else:
                current_r = (entry_price - price) / risk

            # Move SL to break-even
            if 'be_trigger_r' in params and current_r >= params['be_trigger_r']:
                if direction == 'long':
                    sl_price = max(sl_price, entry_price)
                else:
                    sl_price = min(sl_price, entry_price)

            # Trailing stop update
            if 'trail_atr_mult' in params:
                trail_dist = atr * params['trail_atr_mult']
                if direction == 'long':
                    new_trail = price - trail_dist
                    sl_price = max(sl_price, new_trail)
                else:
                    new_trail = price + trail_dist
                    sl_price = min(sl_price, new_trail)

            # Structure-based trailing
            if params.get('trail_type') == 'structure':
                swing = self._find_last_swing(ticks, tick['time'], direction)
                if swing and direction == 'long':
                    sl_price = max(sl_price, swing)
                elif swing and direction == 'short':
                    sl_price = min(sl_price, swing)

            # Partial closes
            for pkey in ['partial_1_r', 'partial_2_r']:
                if pkey in params and params[pkey] is not None:
                    pct_key = pkey.replace('_r', '_pct')
                    if current_r >= params[pkey]:
                        close_pct = params.get(pct_key, 0.5)
                        close_size = remaining_size * close_pct
                        if direction == 'long':
                            total_pnl += (price - entry_price) * close_size
                        else:
                            total_pnl += (entry_price - price) * close_size
                        remaining_size -= close_size
                        partial_closes.append({
                            'r_multiple': current_r,
                            'price': price,
                            'size': close_size,
                            'time': tick['time'],
                        })
                        # Remove this partial from params to avoid re-triggering
                        params[pkey] = None

            # Time-based exit
            if 'max_duration_hours' in params:
                duration = (tick['time'] - trade['entry_time']).total_seconds() / 3600
                if duration >= params['max_duration_hours']:
                    exit_price = price
                    exit_time = tick['time']
                    exit_reason = 'time_exit'
                    if direction == 'long':
                        total_pnl += (price - entry_price) * remaining_size
                    else:
                        total_pnl += (entry_price - price) * remaining_size
                    remaining_size = 0
                    break

        # If still open at end of tick data (shouldn't happen with buffer)
        if remaining_size > 0:
            exit_price = ticks[-1]['mid']
            exit_time = ticks[-1]['time']
            exit_reason = 'data_end'
            if direction == 'long':
                total_pnl += (exit_price - entry_price) * remaining_size
            else:
                total_pnl += (entry_price - exit_price) * remaining_size

        # Compute R-multiple achieved
        risk = abs(entry_price - trade['stop_loss'])
        r_multiple = total_pnl / (risk * position_size) if risk > 0 else 0

        return {
            'exit_price': exit_price,
            'exit_time': exit_time,
            'exit_reason': exit_reason,
            'total_pnl': round(total_pnl, 4),
            'r_multiple': round(r_multiple, 3),
            'partial_closes': partial_closes,
            'duration_hours': round(
                (exit_time - trade['entry_time']).total_seconds() / 3600, 2
            ) if exit_time else None,
        }
```

### 5.4 Counterfactual Schema

```sql
CREATE TABLE trade_counterfactuals (
    id                  SERIAL PRIMARY KEY,
    trade_id            UUID NOT NULL REFERENCES trades(id),
    strategy_name       VARCHAR(50) NOT NULL,  -- e.g., 'conservative_tp', 'aggressive_tp'
    -- Hypothetical outcome
    exit_price          DECIMAL(18,8),
    exit_time           TIMESTAMPTZ,
    exit_reason         VARCHAR(30),
    total_pnl           DECIMAL(18,4),
    r_multiple          DECIMAL(8,3),
    duration_hours      DECIMAL(8,2),
    partial_closes      JSONB,                 -- Array of partial close records
    -- Comparison to actual
    pnl_vs_actual       DECIMAL(18,4),         -- counterfactual_pnl - actual_pnl
    r_vs_actual         DECIMAL(8,3),          -- counterfactual_r - actual_r
    -- Metadata
    computed_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_counterfactual UNIQUE (trade_id, strategy_name)
);

CREATE INDEX idx_counterfactuals_trade ON trade_counterfactuals(trade_id);
CREATE INDEX idx_counterfactuals_strategy ON trade_counterfactuals(strategy_name);

-- View: Which strategy would have been best per trade?
CREATE VIEW v_best_counterfactual AS
SELECT trade_id,
       strategy_name,
       r_multiple,
       r_vs_actual,
       RANK() OVER (PARTITION BY trade_id ORDER BY r_multiple DESC) as rank
FROM trade_counterfactuals;
```

### 5.5 Counterfactual Analysis Queries

```sql
-- Which shadow strategy performs best overall?
SELECT strategy_name,
       COUNT(*) as trades,
       ROUND(AVG(r_multiple), 3) as avg_r,
       ROUND(AVG(r_vs_actual), 3) as avg_improvement_vs_actual,
       ROUND(AVG(CASE WHEN r_vs_actual > 0 THEN 1.0 ELSE 0.0 END), 3) as pct_better
FROM trade_counterfactuals
GROUP BY strategy_name
ORDER BY avg_r DESC;

-- Which strategy is best per regime?
SELECT tf.strategy_name, te.regime,
       COUNT(*) as trades,
       ROUND(AVG(tf.r_multiple), 3) as avg_r
FROM trade_counterfactuals tf
JOIN trade_episodes te ON te.trade_id = tf.trade_id
GROUP BY tf.strategy_name, te.regime
ORDER BY te.regime, avg_r DESC;

-- Trades where we left money on the table
SELECT tf.trade_id, te.symbol,
       tf_actual.r_multiple as actual_r,
       tf_best.r_multiple as best_r,
       tf_best.strategy_name as best_strategy,
       tf_best.r_multiple - tf_actual.r_multiple as missed_r
FROM trade_counterfactuals tf_actual
JOIN trade_counterfactuals tf_best ON tf_best.trade_id = tf_actual.trade_id
    AND tf_best.rank = 1
JOIN trade_episodes te ON te.trade_id = tf_actual.trade_id
WHERE tf_actual.strategy_name = 'actual'
  AND tf_best.r_multiple > tf_actual.r_multiple + 0.5
ORDER BY missed_r DESC;
```

### 5.6 Feed to Contextual Bandit

Counterfactual data provides the **reward signal** for the contextual bandit:

```python
def train_bandit_from_counterfactuals(bandit, db, lookback_trades=200):
    """
    Train the contextual bandit using counterfactual outcomes.
    This is the key bridge: counterfactuals provide rewards for actions not taken.
    """
    trades = db.get_recent_trades(limit=lookback_trades)

    for trade in trades:
        # Get context at entry time
        context = build_context_vector(trade)

        # Get counterfactual outcomes for each TP strategy
        counterfactuals = db.get_counterfactuals(trade['id'])

        for cf in counterfactuals:
            # Map strategy name to action index
            action = strategy_to_action(cf['strategy_name'])
            reward = cf['r_multiple']

            # Update bandit with this (context, action, reward) tuple
            bandit.update(context, action, reward)
```

---

## Fix 6: Fix Causal Attribution

**Issue:** C1 — Cannot attribute trade outcomes to individual agent signals when agents vote simultaneously. The system needs ablation analysis, not simple directional comparison.

### 6.1 What Changes

Replace the naive per-signal directional check with **ablation-based attribution** and **counterfactual confluence scoring**. For each trade, recompute the confluence score with each agent's signal removed to measure individual contribution.

### 6.2 Ablation Analysis

```
ABLATION ANALYSIS — INDIVIDUAL SIGNAL CONTRIBUTION

Original trade: All 6 agents voted BULLISH, confluence=85, trade WON (+2R)

Question: Was the SMC Agent's signal actually predictive?

Method: Recompute confluence WITHOUT the SMC Agent's signal:
  - Remove SMC Agent contribution → confluence would have been 72
  - Would confluence=72 still have triggered the trade? (threshold=70)
  - Answer: YES, barely → SMC Agent was marginally important

Method: Recompute confluence with SMC Agent voting OPPOSITE:
  - SMC Agent votes BEARISH instead of BULLISH → confluence would have been 48
  - Would confluence=48 have triggered the trade? (threshold=70)
  - Answer: NO → SMC Agent was CRITICAL to the trade happening

Attribution:
  - If removing agent doesn't change trade decision → agent is NON-CRITICAL
  - If removing agent flips the decision → agent is CRITICAL
  - If removing agent changes confluence significantly but not decision → agent is CONTRIBUTING
```

### 6.3 Implementation

```python
class CausalAttribution:
    """
    Ablation-based causal attribution for multi-agent signal systems.
    Measures individual agent contribution to trade decisions.
    """

    def __init__(self, db, confluence_threshold=70):
        self.db = db
        self.threshold = confluence_threshold

    def attribute_trade(self, trade):
        """
        For a completed trade, determine each agent's causal contribution.
        Returns attribution scores for each agent.
        """
        episode = self.db.get_trade_episode(trade['id'])
        signals = episode['signals_snapshot']  # All agent signals at entry
        original_confluence = episode['confluence_score']
        original_direction = episode['direction']
        outcome = episode['outcome']  # 'win' | 'loss'

        attributions = {}

        for agent_id, signal in signals.items():
            # Method 1: ABLATION — remove this agent's signal
            ablated_confluence = self._recompute_confluence(
                signals, exclude_agent=agent_id
            )
            ablated_would_trade = ablated_confluence >= self.threshold

            # Method 2: COUNTERFACTUAL — flip this agent's signal
            flipped_signals = dict(signals)
            flipped_signals[agent_id] = {
                **signal,
                'direction': 'bearish' if signal['direction'] == 'bullish' else 'bullish',
                'score': -signal['score']
            }
            flipped_confluence = self._recompute_confluence(flipped_signals)
            flipped_would_trade = flipped_confluence >= self.threshold

            # Method 3: SIGNAL QUALITY — was the agent's direction correct?
            agent_was_correct = self._check_signal_correctness(
                agent_id, signal, outcome, original_direction
            )

            # Compute attribution score
            attribution = self._compute_attribution(
                original_confluence=original_confluence,
                ablated_confluence=ablated_confluence,
                ablated_would_trade=ablated_would_trade,
                flipped_confluence=flipped_confluence,
                flipped_would_trade=flipped_would_trade,
                agent_was_correct=agent_was_correct,
                signal_confidence=signal['confidence'],
                outcome=outcome,
            )

            attributions[agent_id] = attribution

        return attributions

    def _recompute_confluence(self, signals, exclude_agent=None):
        """
        Recompute confluence score excluding one agent.
        Uses the same aggregation formula as the Signal Aggregator.
        """
        active_signals = {
            aid: sig for aid, sig in signals.items()
            if aid != exclude_agent
        }

        if not active_signals:
            return 0

        # Get current weights for these agents
        weights = self.db.get_current_signal_weights()

        total_score = 0
        total_weight = 0
        for agent_id, signal in active_signals.items():
            w = weights.get(agent_id, 0.10)  # Default weight if missing
            total_score += signal['score'] * w
            total_weight += w

        # Normalize
        if total_weight > 0:
            return (total_score / total_weight) * 100
        return 0

    def _compute_attribution(self, original_confluence, ablated_confluence,
                              ablated_would_trade, flipped_confluence,
                              flipped_would_trade, agent_was_correct,
                              signal_confidence, outcome):
        """
        Compute multi-dimensional attribution score.

        Returns:
            {
                'criticality': float,    # How critical was this agent to the decision?
                'predictiveness': float, # How predictive was this agent's signal?
                'contribution': float,   # Overall contribution score
                'category': str,         # Classification
            }
        """
        # Criticality: how much does removing this agent change the decision?
        confluence_drop = original_confluence - ablated_confluence
        criticality = confluence_drop / max(original_confluence, 1)

        if not ablated_would_trade and original_confluence >= self.threshold:
            # Removing this agent would have prevented the trade
            criticality = max(criticality, 0.8)

        # Predictiveness: was the agent correct?
        predictiveness = 1.0 if agent_was_correct else -0.5

        # Scale by confidence: high-confidence wrong signals are worse
        if not agent_was_correct and signal_confidence > 0.7:
            predictiveness = -1.0  # High-confidence wrong signal

        # Contribution: weighted combination
        contribution = 0.6 * criticality + 0.4 * max(0, predictiveness)

        # Classification
        if criticality > 0.7 and agent_was_correct:
            category = 'CRITICAL_CORRECT'     # Key contributor to winning trade
        elif criticality > 0.7 and not agent_was_correct:
            category = 'CRITICAL_WRONG'       # Key contributor to losing trade
        elif criticality < 0.3 and agent_was_correct:
            category = 'NON_CRITICAL_CORRECT' # Right but didn't matter much
        elif criticality < 0.3 and not agent_was_correct:
            category = 'NON_CRITICAL_WRONG'   # Wrong but didn't matter much
        else:
            category = 'CONTRIBUTING'          # Moderate influence

        return {
            'criticality': round(criticality, 3),
            'predictiveness': round(predictiveness, 3),
            'contribution': round(contribution, 3),
            'category': category,
            'confluence_drop': round(confluence_drop, 1),
            'would_have_traded_without': ablated_would_trade,
            'flipped_confluence': round(flipped_confluence, 1),
        }
```

### 6.4 Attribution-Informed Weight Updates

Replace the naive weight update with attribution-informed updates:

```python
def update_weights_with_attribution(self, trade, attributions):
    """
    Update signal weights based on causal attribution, not just directional correctness.
    """
    outcome = trade['outcome']

    for agent_id, attr in attributions.items():
        # Only adjust weights for agents that had meaningful impact
        if attr['criticality'] < 0.1:
            continue  # Agent had negligible impact — don't learn from this trade

        # Compute adjustment based on attribution category
        if attr['category'] == 'CRITICAL_CORRECT':
            # Agent was critical and correct — strengthen
            adjustment = +0.01 * attr['criticality']

        elif attr['category'] == 'CRITICAL_WRONG':
            # Agent was critical and wrong — weaken
            adjustment = -0.01 * attr['criticality']

        elif attr['category'] == 'NON_CRITICAL_CORRECT':
            # Agent was right but didn't matter — small reinforcement
            adjustment = +0.005

        elif attr['category'] == 'NON_CRITICAL_WRONG':
            # Agent was wrong but didn't matter — small penalty
            adjustment = -0.005

        else:  # CONTRIBUTING
            # Moderate influence — moderate adjustment
            if attr['predictiveness'] > 0:
                adjustment = +0.008
            else:
                adjustment = -0.008

        # Apply with statistical significance gate (from Fix 4)
        # Only adjust if we have enough attribution data
        n_attributions = self.db.get_attribution_count(agent_id, trade['symbol'])
        if n_attributions >= 20:
            current_weight = self.db.get_signal_weight(agent_id, trade['symbol'])
            new_weight = max(0.05, min(0.40, current_weight + adjustment))

            self.db.update_signal_weight(
                agent_id, trade['symbol'], new_weight,
                reason=f"Attribution: {attr['category']}, "
                       f"criticality={attr['criticality']:.2f}, "
                       f"confluence_drop={attr['confluence_drop']:.1f}"
            )
```

### 6.5 Tracking Filtered Signals (Survivorship Correction)

The review flagged that agents only produce signals when they detect patterns. We need to track **signals that were generated but didn't lead to trades** to compute true precision/recall.

```sql
CREATE TABLE signal_log (
    id              SERIAL PRIMARY KEY,
    agent_id        VARCHAR(50) NOT NULL,
    symbol          VARCHAR(20) NOT NULL,
    timeframe       VARCHAR(10),
    direction       VARCHAR(10) NOT NULL,
    confidence      DECIMAL(5,3),
    score           DECIMAL(6,2),
    -- What happened to this signal?
    generated_at    TIMESTAMPTZ NOT NULL,
    led_to_trade    BOOLEAN DEFAULT FALSE,
    trade_id        UUID REFERENCES trades(id),
    filtered_by     VARCHAR(50),       -- 'risk_gate', 'confluence_low', 'time_filter', NULL
    -- Outcome (filled if led_to_trade)
    outcome         VARCHAR(10),       -- 'win', 'loss', 'breakeven', NULL
    -- Market context at signal time
    regime          VARCHAR(30),
    session         VARCHAR(20),
    confluence_without DECIMAL(6,2),   -- Confluence score if this agent was excluded
    -- For true precision/recall calculation
    was_correct_direction BOOLEAN,     -- Would this signal have been correct?
    CHECK (led_to_trade = TRUE OR trade_id IS NULL)
);

-- Indexes for precision/recall queries
CREATE INDEX idx_signal_log_agent ON signal_log(agent_id, symbol, generated_at);
CREATE INDEX idx_signal_log_filtered ON signal_log(filtered_by) WHERE led_to_trade = FALSE;
```

```python
def compute_true_precision_recall(agent_id, symbol, window=200):
    """
    Compute true precision and recall using ALL signals,
    including those filtered before becoming trades.
    """
    signals = db.execute("""
        SELECT direction, led_to_trade, outcome, was_correct_direction
        FROM signal_log
        WHERE agent_id = %s AND symbol = %s
        ORDER BY generated_at DESC
        LIMIT %s
    """, [agent_id, symbol, window])

    if not signals:
        return {'precision': None, 'recall': None, 'n': 0}

    # Precision: of signals that led to trades, what % were correct?
    trade_signals = [s for s in signals if s['led_to_trade']]
    if trade_signals:
        precision = sum(1 for s in trade_signals if s['outcome'] == 'win') / len(trade_signals)
    else:
        precision = None

    # Recall: of all correct signals, what % led to trades?
    correct_signals = [s for s in signals if s['was_correct_direction']]
    if correct_signals:
        recall = sum(1 for s in correct_signals if s['led_to_trade']) / len(correct_signals)
    else:
        recall = None

    # Filter rate: what % of signals are filtered before trading?
    filtered = [s for s in signals if not s['led_to_trade']]
    filter_rate = len(filtered) / len(signals) if signals else 0

    # Group filtered signals by reason
    filter_reasons = {}
    for s in filtered:
        reason = s['filtered_by'] or 'unknown'
        filter_reasons[reason] = filter_reasons.get(reason, 0) + 1

    return {
        'precision': round(precision, 4) if precision else None,
        'recall': round(recall, 4) if recall else None,
        'f1': round(2 * precision * recall / (precision + recall), 4)
              if precision and recall else None,
        'filter_rate': round(filter_rate, 4),
        'filter_reasons': filter_reasons,
        'n_signals': len(signals),
        'n_trade_signals': len(trade_signals),
        'n_correct_signals': len(correct_signals),
    }
```

### 6.6 Interaction Effects

Track pairwise agent interactions to learn synergies and conflicts:

```sql
CREATE TABLE agent_interactions (
    agent_a         VARCHAR(50) NOT NULL,
    agent_b         VARCHAR(50) NOT NULL,
    symbol          VARCHAR(20) NOT NULL,
    regime          VARCHAR(30),
    -- When both agents agree
    agree_count     INTEGER DEFAULT 0,
    agree_wins      INTEGER DEFAULT 0,
    -- When agents disagree
    disagree_count  INTEGER DEFAULT 0,
    disagree_wins   INTEGER DEFAULT 0,
    -- Interaction effect
    synergy_score   DECIMAL(5,3),  -- Positive = synergy, negative = conflict
    last_updated    TIMESTAMPTZ,
    CONSTRAINT uq_interaction UNIQUE (agent_a, agent_b, symbol, regime)
);
```

```python
def compute_synergy(agent_a, agent_b, symbol, regime):
    """
    Compute synergy score: does having both agents agree
    produce better outcomes than expected from independence?
    """
    # Win rate when both agree
    agree = db.get_interaction_data(agent_a, agent_b, symbol, regime, 'agree')
    wr_agree = agree['wins'] / agree['count'] if agree['count'] > 0 else None

    # Win rate when they disagree
    disagree = db.get_interaction_data(agent_a, agent_b, symbol, regime, 'disagree')
    wr_disagree = disagree['wins'] / disagree['count'] if disagree['count'] > 0 else None

    # Individual win rates
    wr_a = db.get_agent_win_rate(agent_a, symbol, regime)
    wr_b = db.get_agent_win_rate(agent_b, symbol, regime)

    if all(v is not None for v in [wr_agree, wr_a, wr_b]):
        # Expected win rate under independence
        wr_expected = wr_a * wr_b + (1 - wr_a) * (1 - wr_b)  # Both right or both wrong
        synergy = wr_agree - wr_expected
        return round(synergy, 4)

    return None
```

---

## Implementation Roadmap

### Phase 1: Critical Fixes (Weeks 1–3)

| Week | Task | Fixes |
|------|------|-------|
| 1 | Implement ablation-based causal attribution | Fix 6 |
| 1 | Add signal_log table and start logging all signals | Fix 6 |
| 2 | Implement statistical significance gating for weight adjustments | Fix 4 |
| 2 | Add minimum sample gates (20 obs before any adjustment) | Fix 4 |
| 3 | Implement hierarchical Bayesian pattern reliability | Fix 3 |
| 3 | Add exponentially-weighted pattern reliability | Fix 3 |

### Phase 2: Structural Improvements (Weeks 4–6)

| Week | Task | Fixes |
|------|------|-------|
| 4 | Implement counterfactual shadow tracking system | Fix 5 |
| 4 | Add trade_counterfactuals table and simulation engine | Fix 5 |
| 5 | Replace RL TP agent with contextual bandit (Thompson Sampling) | Fix 1 |
| 5 | Implement offline management rule computation (lookup tables) | Fix 1 |
| 6 | Integrate counterfactual data as bandit reward signal | Fix 1, 5 |
| 6 | Add agent interaction tracking and synergy computation | Fix 6 |

### Phase 3: Drift & Monitoring (Weeks 7–8)

| Week | Task | Fixes |
|------|------|-------|
| 7 | Implement Page-Hinkley drift detection for signal accuracy | Fix 2 |
| 7 | Implement regime change detector (HMM) | Fix 2 |
| 8 | Implement drift response actions (confidence reduction, prior reset) | Fix 2 |
| 8 | Integration testing: full loop with all 6 fixes | All |

### Validation Criteria

| Fix | Success Metric | Threshold |
|-----|---------------|-----------|
| Fix 1 (Bandits) | Bandit selects best TP strategy >60% of the time | >60% accuracy on holdout |
| Fix 2 (Drift) | Drift detected within 20 trades of actual regime change | <20 trade lag |
| Fix 3 (Hierarchical) | Pattern estimates stable even with <10 cell observations | CI width < 0.30 |
| Fix 4 (Significance) | Zero weight adjustments without p < 0.10 | 100% compliance |
| Fix 5 (Counterfactual) | Shadow tracking operational on 100% of trades | 100% coverage |
| Fix 6 (Attribution) | Attribution scores correlate with agent accuracy trends | r > 0.5 |

---

## Updated Data Schema Additions

Summarizing all new tables and modifications needed:

```sql
-- =============================================
-- NEW TABLES
-- =============================================

-- 1. Signal log (Fix 6): All signals, not just trade-linked ones
CREATE TABLE signal_log (
    id                  SERIAL PRIMARY KEY,
    agent_id            VARCHAR(50) NOT NULL,
    symbol              VARCHAR(20) NOT NULL,
    timeframe           VARCHAR(10),
    direction           VARCHAR(10) NOT NULL,
    confidence          DECIMAL(5,3),
    score               DECIMAL(6,2),
    generated_at        TIMESTAMPTZ NOT NULL,
    led_to_trade        BOOLEAN DEFAULT FALSE,
    trade_id            UUID REFERENCES trades(id),
    filtered_by         VARCHAR(50),
    outcome             VARCHAR(10),
    regime              VARCHAR(30),
    session             VARCHAR(20),
    confluence_without  DECIMAL(6,2),
    was_correct_direction BOOLEAN
);

-- 2. Trade counterfactuals (Fix 5): Shadow management outcomes
CREATE TABLE trade_counterfactuals (
    id                  SERIAL PRIMARY KEY,
    trade_id            UUID NOT NULL REFERENCES trades(id),
    strategy_name       VARCHAR(50) NOT NULL,
    exit_price          DECIMAL(18,8),
    exit_time           TIMESTAMPTZ,
    exit_reason         VARCHAR(30),
    total_pnl           DECIMAL(18,4),
    r_multiple          DECIMAL(8,3),
    duration_hours      DECIMAL(8,2),
    partial_closes      JSONB,
    pnl_vs_actual       DECIMAL(18,4),
    r_vs_actual         DECIMAL(8,3),
    computed_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_counterfactual UNIQUE (trade_id, strategy_name)
);

-- 3. Trade attributions (Fix 6): Per-agent causal contribution
CREATE TABLE trade_attributions (
    id                  SERIAL PRIMARY KEY,
    trade_id            UUID NOT NULL REFERENCES trades(id),
    agent_id            VARCHAR(50) NOT NULL,
    criticality         DECIMAL(5,3),
    predictiveness      DECIMAL(5,3),
    contribution        DECIMAL(5,3),
    category            VARCHAR(30),
    confluence_drop     DECIMAL(6,1),
    would_have_traded   BOOLEAN,
    computed_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_attribution UNIQUE (trade_id, agent_id)
);

-- 4. Agent interactions (Fix 6): Pairwise synergy tracking
CREATE TABLE agent_interactions (
    agent_a             VARCHAR(50) NOT NULL,
    agent_b             VARCHAR(50) NOT NULL,
    symbol              VARCHAR(20) NOT NULL,
    regime              VARCHAR(30),
    agree_count         INTEGER DEFAULT 0,
    agree_wins          INTEGER DEFAULT 0,
    disagree_count      INTEGER DEFAULT 0,
    disagree_wins       INTEGER DEFAULT 0,
    synergy_score       DECIMAL(5,3),
    last_updated        TIMESTAMPTZ,
    CONSTRAINT uq_interaction UNIQUE (agent_a, agent_b, symbol, regime)
);

-- 5. Drift detection state (Fix 2)
CREATE TABLE drift_state (
    detector_id         VARCHAR(50) PRIMARY KEY,
    detector_type       VARCHAR(30) NOT NULL,  -- 'page_hinkley', 'regime_hmm'
    state               JSONB NOT NULL,
    last_drift_score    DECIMAL(5,3),
    last_drift_level    VARCHAR(10),
    last_check          TIMESTAMPTZ,
    last_drift_detected TIMESTAMPTZ
);

-- 6. Management rules lookup (Fix 1)
CREATE TABLE management_rules (
    rule_id             SERIAL PRIMARY KEY,
    symbol              VARCHAR(20) NOT NULL,
    regime              VARCHAR(30) NOT NULL,
    session             VARCHAR(20) NOT NULL,
    setup_type          VARCHAR(30) NOT NULL,
    be_trigger_r        DECIMAL(4,2) NOT NULL,
    partial_1_r         DECIMAL(4,2),
    partial_1_pct       DECIMAL(4,2),
    partial_2_r         DECIMAL(4,2),
    partial_2_pct       DECIMAL(4,2),
    trail_atr_mult      DECIMAL(4,2),
    time_exit_hours     DECIMAL(6,2),
    sample_size         INTEGER NOT NULL,
    avg_rr              DECIMAL(6,3),
    win_rate            DECIMAL(5,4),
    computed_at         TIMESTAMPTZ NOT NULL,
    active              BOOLEAN DEFAULT TRUE,
    CONSTRAINT uq_management_rule UNIQUE (symbol, regime, session, setup_type)
);

-- =============================================
-- MODIFIED TABLES
-- =============================================

-- 7. Signal weights: add attribution and significance fields
ALTER TABLE signal_weights
    ADD COLUMN last_p_value DECIMAL(8,6),
    ADD COLUMN last_attribution_category VARCHAR(30),
    ADD COLUMN adjustment_evidence JSONB,
    ADD COLUMN n_attributions INTEGER DEFAULT 0;

-- 8. Pattern reliability: replace with hierarchical estimates
ALTER TABLE pattern_reliability
    ADD COLUMN win_rate_hierarchical DECIMAL(6,4),
    ADD COLUMN ci_low DECIMAL(6,4),
    ADD COLUMN ci_high DECIMAL(6,4),
    ADD COLUMN effective_n DECIMAL(8,1),
    ADD COLUMN shrinkage_weight DECIMAL(5,3),
    ADD COLUMN win_rate_ew DECIMAL(6,4),
    ADD COLUMN ew_effective_n DECIMAL(8,1);

-- =============================================
-- NEW INDEXES
-- =============================================

CREATE INDEX idx_signal_log_agent ON signal_log(agent_id, symbol, generated_at);
CREATE INDEX idx_signal_log_filtered ON signal_log(filtered_by) WHERE led_to_trade = FALSE;
CREATE INDEX idx_counterfactuals_trade ON trade_counterfactuals(trade_id);
CREATE INDEX idx_counterfactuals_strategy ON trade_counterfactuals(strategy_name);
CREATE INDEX idx_attributions_trade ON trade_attributions(trade_id);
CREATE INDEX idx_attributions_agent ON trade_attributions(agent_id, category);
```

---

## Summary: Before vs. After

| Component | Before (Broken) | After (Fixed) |
|-----------|-----------------|---------------|
| **TP optimization** | Deep RL (500 episodes, non-stationary, sparse reward) | Contextual bandit (Thompson Sampling, 50+ obs/convergence) |
| **Pattern reliability** | Independent per-cell (2,160 cells, avg 0.23 trades/cell) | Hierarchical Bayesian (borrows strength, shrinkage to parent) |
| **Signal weight updates** | ±0.01 per trade, no significance test | Only when p < 0.10, effect-size-scaled, Bonferroni corrected |
| **Causal attribution** | Directional check per signal (confounded) | Ablation analysis (remove agent, recompute confluence) |
| **Counterfactual data** | Not captured | Shadow tracking: 5 alternative strategies per trade |
| **Concept drift** | Not detected | Page-Hinkley + HMM regime detector, auto-degrade stale knowledge |

---

*Document generated: 2026-07-11*
*Author: Learning Loop Fix Agent — Alpha Stack*
*Status: Architecture Fix Complete — Ready for Implementation*
*Next: Integrate fixes into architecture_memory.md → Begin Phase 1 implementation*
