# AGI Readiness Fix Plan — Alpha Stack

**Date:** 2026-07-11
**Status:** IMPLEMENTATION SPEC — Ready for Development
**Based on:** `review_agi_readiness.md` (4 Critical Gaps)
**Scope:** Strategy Monoculture, Learning Loop Poisoning, Model Architecture Lock-in, AI-vs-AI Blindness

---

## Overview

This document provides **concrete implementation specifications** for the 4 most dangerous AGI readiness gaps identified in the review. Each fix includes architecture design, code interface, data flow, integration points, and acceptance criteria.

| # | Gap | Fix | Effort | Priority |
|---|-----|-----|--------|----------|
| 1 | Strategy monoculture — no detection of AI crowd crowding | Alpha Decay Tracker + Strategy Diversification Engine | MEDIUM | P0 |
| 2 | Learning loop poisoning — adversarial manipulation vulnerability | Adversarial Robustness Layer for Reflection Agent | MEDIUM | P0 |
| 3 | Model architecture lock-in — hard-coded model-to-step mapping | Model Capability Abstraction Interface | HIGH | P0 |
| 4 | AI-vs-AI blindness — no opponent modeling | Opponent Strategy Estimator + Game-Theoretic Layer | HIGH | P0 |

---

## FIX 1: Alpha Decay Tracker + Strategy Diversification Engine

### Problem
The system runs a single strategy pipeline with fixed signal weights. When multiple AI agents converge on the same SMC/RSI/S/R strategies, alpha decays and the system has no mechanism to detect it or pivot. This is **strategy monoculture** — the #1 killer of quant strategies in crowded markets.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    ALPHA DECAY TRACKER                           │
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │ Strategy      │    │ Rolling      │    │ Decay        │      │
│  │ Performance   │───▶│ Sharpe/Alpha │───▶│ Detector     │      │
│  │ Logger        │    │ Calculator   │    │              │      │
│  └──────────────┘    └──────────────┘    └──────┬───────┘      │
│                                                  │               │
│                                    ┌─────────────▼────────────┐ │
│                                    │  Alpha Decay Signal      │ │
│                                    │  - decay_rate: float     │ │
│                                    │  - crowd_score: float    │ │
│                                    │  - uniqueness: float     │ │
│                                    │  - action: HOLD|ROTATE   │ │
│                                    └─────────────┬────────────┘ │
│                                                  │               │
│                                    ┌─────────────▼────────────┐ │
│                                    │  Strategy Diversification│ │
│                                    │  Engine                  │ │
│                                    │  - strategy_pool[]       │ │
│                                    │  - correlation_matrix    │ │
│                                    │  - rotation_schedule     │ │
│                                    └──────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Interface

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
import numpy as np
from collections import deque
import time


class DecayAction(Enum):
    HOLD = "hold"               # Alpha still healthy
    MONITOR = "monitor"         # Early warning, increase monitoring
    REDUCE = "reduce"           # Reduce position size on this strategy
    ROTATE = "rotate"           # Switch to uncorrelated alternative
    RETIRE = "retire"           # Strategy is dead, remove from active pool


@dataclass
class AlphaDecaySignal:
    strategy_id: str
    rolling_sharpe: float          # 30-day rolling Sharpe ratio
    rolling_alpha: float           # Alpha vs benchmark
    decay_rate: float              # Rate of alpha decline (slope)
    crowd_score: float             # 0-1, how crowded the strategy is
    uniqueness_score: float        # 0-1, how different from market consensus
    action: DecayAction
    confidence: float              # Confidence in the assessment
    timestamp: float
    details: Dict = field(default_factory=dict)


@dataclass
class StrategySnapshot:
    strategy_id: str
    returns: List[float]
    timestamps: List[float]
    signal_correlation: float      # Correlation with market aggregate
    metadata: Dict = field(default_factory=dict)


class AlphaDecayTracker:
    """
    Tracks alpha decay per strategy and detects strategy crowding.
    
    Core idea: In AI-dominated markets, alpha decays when multiple
    agents converge on the same strategy. This tracker measures decay
    rate and crowding to trigger strategy rotation BEFORE P&L impact.
    """
    
    def __init__(self, config: Dict):
        self.rolling_window = config.get("rolling_window_days", 30)
        self.short_window = config.get("short_window_days", 7)
        self.decay_threshold = config.get("decay_threshold", -0.5)  # Sharpe slope
        self.crowd_threshold = config.get("crowd_threshold", 0.7)
        self.min_observations = config.get("min_observations", 20)
        
        # Per-strategy rolling returns
        self.strategy_returns: Dict[str, deque] = {}
        # Strategy correlation matrix
        self.correlation_matrix: Dict[str, Dict[str, float]] = {}
        # Alpha decay history for trend detection
        self.decay_history: Dict[str, List[AlphaDecaySignal]] = {}
    
    def record_return(self, strategy_id: str, ret: float, timestamp: float):
        """Record a strategy return observation."""
        if strategy_id not in self.strategy_returns:
            self.strategy_returns[strategy_id] = deque(
                maxlen=self.rolling_window * 24  # hourly observations
            )
        self.strategy_returns[strategy_id].append((timestamp, ret))
    
    def update_correlation_matrix(
        self, strategy_returns: Dict[str, List[float]]
    ):
        """
        Update cross-strategy correlation matrix.
        High correlation = strategies are crowded (trading same signals).
        """
        strategy_ids = list(strategy_returns.keys())
        n = len(strategy_ids)
        
        # Build returns matrix
        returns_matrix = np.array([
            strategy_returns[sid] for sid in strategy_ids
        ])
        
        # Compute correlation matrix
        corr = np.corrcoef(returns_matrix)
        
        # Store
        for i, sid_i in enumerate(strategy_ids):
            if sid_i not in self.correlation_matrix:
                self.correlation_matrix[sid_i] = {}
            for j, sid_j in enumerate(strategy_ids):
                if i != j:
                    self.correlation_matrix[sid_i][sid_j] = corr[i, j]
    
    def compute_crowd_score(self, strategy_id: str) -> float:
        """
        Compute how crowded a strategy is.
        
        Signals of crowding:
        1. High correlation with other active strategies
        2. High correlation with market aggregate
        3. Accelerating alpha decay (more agents entering)
        4. Decreasing signal-to-noise ratio
        
        Returns: 0.0 (unique) to 1.0 (extremely crowded)
        """
        if strategy_id not in self.correlation_matrix:
            return 0.0
        
        # Average correlation with all other strategies
        correlations = list(
            self.correlation_matrix[strategy_id].values()
        )
        if not correlations:
            return 0.0
        
        avg_correlation = np.mean(np.abs(correlations))
        
        # Weight by recent trend (accelerating correlation = more crowded)
        recent_corr = np.mean(np.abs(correlations[-5:])) if len(correlations) >= 5 else avg_correlation
        trend_factor = max(0, recent_corr - avg_correlation)  # Positive = increasing crowding
        
        crowd_score = min(1.0, avg_correlation + trend_factor)
        return float(crowd_score)
    
    def compute_decay_rate(self, strategy_id: str) -> float:
        """
        Compute the rate of alpha decay using linear regression
        on rolling Sharpe ratios.
        
        Negative slope = alpha is decaying (bad)
        Accelerating negative slope = AI crowd is entering (very bad)
        """
        returns = self.strategy_returns.get(strategy_id)
        if not returns or len(returns) < self.min_observations:
            return 0.0
        
        # Compute rolling Sharpe at different time points
        timestamps = [t for t, _ in returns]
        values = [r for _, r in returns]
        
        # Sliding window Sharpe computation
        window_size = min(self.short_window * 24, len(values) // 3)
        if window_size < 10:
            return 0.0
        
        sharpe_series = []
        for i in range(window_size, len(values)):
            window = values[i - window_size:i]
            mean_r = np.mean(window)
            std_r = np.std(window)
            if std_r > 0:
                sharpe_series.append(mean_r / std_r * np.sqrt(252))
            else:
                sharpe_series.append(0.0)
        
        if len(sharpe_series) < 5:
            return 0.0
        
        # Linear regression slope on Sharpe series
        x = np.arange(len(sharpe_series))
        slope, _ = np.polyfit(x, sharpe_series, 1)
        
        return float(slope)
    
    def compute_uniqueness_score(self, strategy_id: str) -> float:
        """
        Compute how unique a strategy is vs. market consensus.
        
        Low uniqueness = running same strategy as everyone else
        High uniqueness = differentiated alpha source
        
        Returns: 0.0 (herd) to 1.0 (unique)
        """
        crowd = self.compute_crowd_score(strategy_id)
        return 1.0 - crowd
    
    def evaluate(self, strategy_id: str) -> AlphaDecaySignal:
        """
        Main evaluation: assess alpha decay and recommend action.
        """
        decay_rate = self.compute_decay_rate(strategy_id)
        crowd_score = self.compute_crowd_score(strategy_id)
        uniqueness = self.compute_uniqueness_score(strategy_id)
        
        # Compute rolling Sharpe for reporting
        returns = self.strategy_returns.get(strategy_id, [])
        if returns:
            values = [r for _, r in returns]
            mean_r = np.mean(values[-self.short_window * 24:])
            std_r = np.std(values[-self.short_window * 24:])
            rolling_sharpe = (mean_r / std_r * np.sqrt(252)) if std_r > 0 else 0.0
        else:
            rolling_sharpe = 0.0
        
        # Decision logic
        action = self._determine_action(
            decay_rate, crowd_score, uniqueness, rolling_sharpe
        )
        
        # Confidence based on data availability
        data_points = len(returns)
        confidence = min(1.0, data_points / (self.min_observations * 3))
        
        signal = AlphaDecaySignal(
            strategy_id=strategy_id,
            rolling_sharpe=rolling_sharpe,
            rolling_alpha=rolling_sharpe * 0.8,  # Simplified
            decay_rate=decay_rate,
            crowd_score=crowd_score,
            uniqueness_score=uniqueness,
            action=action,
            confidence=confidence,
            timestamp=time.time(),
            details={
                "data_points": data_points,
                "window_days": self.rolling_window,
            }
        )
        
        # Store history for trend analysis
        if strategy_id not in self.decay_history:
            self.decay_history[strategy_id] = []
        self.decay_history[strategy_id].append(signal)
        
        return signal
    
    def _determine_action(
        self,
        decay_rate: float,
        crowd_score: float,
        uniqueness: float,
        rolling_sharpe: float,
    ) -> DecayAction:
        """
        Determine action based on multi-factor assessment.
        
        Priority: Retire > Rotate > Reduce > Monitor > Hold
        """
        # Immediate retirement: alpha is deeply negative and decaying
        if rolling_sharpe < -1.0 and decay_rate < self.decay_threshold:
            return DecayAction.RETIRE
        
        # Rotation: strategy is crowded AND alpha is decaying
        if crowd_score > self.crowd_threshold and decay_rate < self.decay_threshold * 0.5:
            return DecayAction.ROTATE
        
        # Reduction: moderate crowding or moderate decay
        if crowd_score > 0.5 or decay_rate < self.decay_threshold * 0.3:
            return DecayAction.REDUCE
        
        # Monitoring: early signs of decay
        if decay_rate < 0 or crowd_score > 0.3:
            return DecayAction.MONITOR
        
        return DecayAction.HOLD


class StrategyDiversificationEngine:
    """
    Maintains a pool of uncorrelated strategies and auto-rotates
    when alpha decay is detected.
    
    Core principle: In AI-dominated markets, the winning strategy
    is the one that's DIFFERENT from the crowd.
    """
    
    def __init__(self, alpha_tracker: AlphaDecayTracker, config: Dict):
        self.alpha_tracker = alpha_tracker
        self.max_correlation = config.get("max_correlation", 0.6)
        self.min_strategies = config.get("min_active_strategies", 3)
        self.max_strategies = config.get("max_active_strategies", 8)
        self.rotation_cooldown_hours = config.get("rotation_cooldown_hours", 24)
        
        # Strategy pool: active, standby, retired
        self.active_strategies: Dict[str, float] = {}   # id → weight
        self.standby_strategies: List[str] = []
        self.retired_strategies: List[str] = []
        self.last_rotation: Dict[str, float] = {}       # strategy_id → timestamp
    
    def register_strategy(
        self, strategy_id: str, initial_weight: float = 0.0
    ):
        """Register a new strategy in the standby pool."""
        if strategy_id not in self.active_strategies:
            if strategy_id not in self.standby_strategies:
                self.standby_strategies.append(strategy_id)
    
    def evaluate_rotation(self) -> Dict[str, str]:
        """
        Evaluate all active strategies for rotation.
        Returns dict of strategy_id → recommended action.
        """
        recommendations = {}
        
        for strategy_id in list(self.active_strategies.keys()):
            signal = self.alpha_tracker.evaluate(strategy_id)
            
            if signal.action in (DecayAction.ROTATE, DecayAction.RETIRE):
                # Find best uncorrelated replacement
                replacement = self._find_replacement(strategy_id)
                if replacement:
                    recommendations[strategy_id] = (
                        f"ROTATE_TO:{replacement}"
                    )
                else:
                    recommendations[strategy_id] = "REDUCE_ONLY"
            elif signal.action == DecayAction.REDUCE:
                recommendations[strategy_id] = "REDUCE"
            else:
                recommendations[strategy_id] = "HOLD"
        
        return recommendations
    
    def _find_replacement(self, retiring_id: str) -> Optional[str]:
        """
        Find the best uncorrelated replacement strategy from standby pool.
        
        Selection criteria:
        1. Low correlation with remaining active strategies
        2. Highest recent alpha (from standby pool)
        3. Not recently retired (cooldown check)
        """
        now = time.time()
        candidates = []
        
        for candidate_id in self.standby_strategies:
            # Skip if recently retired
            if candidate_id in self.last_rotation:
                hours_since = (now - self.last_rotation[candidate_id]) / 3600
                if hours_since < self.rotation_cooldown_hours:
                    continue
            
            # Check correlation with all active strategies
            max_corr = 0.0
            for active_id in self.active_strategies:
                if active_id == retiring_id:
                    continue
                corr = self._get_correlation(candidate_id, active_id)
                max_corr = max(max_corr, abs(corr))
            
            if max_corr < self.max_correlation:
                # Get candidate's alpha
                signal = self.alpha_tracker.evaluate(candidate_id)
                candidates.append((candidate_id, signal.rolling_alpha, max_corr))
        
        if not candidates:
            return None
        
        # Sort by: lowest correlation first, then highest alpha
        candidates.sort(key=lambda x: (-x[2], x[1]), reverse=False)
        candidates.sort(key=lambda x: x[2])  # Lowest correlation first
        
        return candidates[0][0]
    
    def _get_correlation(self, strat_a: str, strat_b: str) -> float:
        """Get correlation between two strategies from tracker."""
        if strat_a in self.alpha_tracker.correlation_matrix:
            return self.alpha_tracker.correlation_matrix[strat_a].get(
                strat_b, 0.0
            )
        return 0.0
    
    def execute_rotation(
        self, retiring_id: str, replacement_id: str
    ):
        """Execute a strategy rotation."""
        weight = self.active_strategies.pop(retiring_id, 0.0)
        self.retired_strategies.append(retiring_id)
        self.last_rotation[retiring_id] = time.time()
        
        if replacement_id in self.standby_strategies:
            self.standby_strategies.remove(replacement_id)
        
        self.active_strategies[replacement_id] = weight
        self.last_rotation[replacement_id] = time.time()
    
    def get_portfolio_uniqueness(self) -> float:
        """
        Compute overall portfolio uniqueness score.
        
        A diversified portfolio of uncorrelated strategies
        has high uniqueness and is harder for AI adversaries
        to exploit.
        """
        if not self.active_strategies:
            return 0.0
        
        uniqueness_scores = []
        for strategy_id in self.active_strategies:
            signal = self.alpha_tracker.evaluate(strategy_id)
            uniqueness_scores.append(signal.uniqueness_score)
        
        return float(np.mean(uniqueness_scores))
```

### Integration Points

```python
# In TradingEngine or StrategyManager:

class StrategyManager:
    def __init__(self):
        self.alpha_tracker = AlphaDecayTracker(config={
            "rolling_window_days": 30,
            "short_window_days": 7,
            "decay_threshold": -0.5,
            "crowd_threshold": 0.7,
        })
        self.diversification = StrategyDiversificationEngine(
            self.alpha_tracker, config={
                "max_correlation": 0.6,
                "min_active_strategies": 3,
                "max_active_strategies": 8,
                "rotation_cooldown_hours": 24,
            }
        )
    
    def on_trade_closed(self, strategy_id: str, return_pct: float):
        """Called after each trade closes."""
        self.alpha_tracker.record_return(
            strategy_id, return_pct, time.time()
        )
    
    def on_periodic_evaluation(self):
        """Called by scheduler every N hours."""
        # Update correlation matrix
        returns_data = self._collect_strategy_returns()
        self.alpha_tracker.update_correlation_matrix(returns_data)
        
        # Evaluate rotations
        recommendations = self.diversification.evaluate_rotation()
        
        for strategy_id, action in recommendations.items():
            if action.startswith("ROTATE_TO:"):
                replacement = action.split(":")[1]
                self.diversification.execute_rotation(
                    strategy_id, replacement
                )
                self._log_rotation(strategy_id, replacement)
            elif action == "REDUCE":
                self._reduce_strategy_weight(strategy_id, factor=0.5)
```

### Acceptance Criteria

- [ ] Alpha decay rate computed per strategy with rolling 30-day window
- [ ] Crowd score detects correlation spikes across strategies
- [ ] Uniqueness score measures strategy differentiation from market
- [ ] Automatic rotation triggers when decay_rate < threshold AND crowd_score > threshold
- [ ] Replacement strategy selected by lowest correlation with active portfolio
- [ ] Portfolio uniqueness score > 0.5 maintained at all times
- [ ] Rotation cooldown prevents oscillation (24h minimum between rotations per strategy)
- [ ] All signals logged for post-hoc analysis

---

## FIX 2: Adversarial Robustness Layer for Reflection Agent

### Problem
The Reflection Agent's closed learning loop updates signal weights from trade outcomes. An AGI adversary can engineer market conditions that systematically corrupt this loop — creating losing patterns that teach the system wrong lessons, or winning patterns that lure the system into crowded strategies. This is **learning loop poisoning**.

### Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│              ADVERSARIAL ROBUSTNESS LAYER                         │
│                                                                   │
│  Trade Outcome                                                    │
│       │                                                           │
│       ▼                                                           │
│  ┌──────────────────┐                                             │
│  │ Input Validation  │ ← Reject anomalous/outlier outcomes        │
│  │ & Sanitization    │                                            │
│  └────────┬─────────┘                                             │
│           │                                                       │
│           ▼                                                       │
│  ┌──────────────────┐                                             │
│  │ Adversarial       │ ← Detect patterns designed to poison       │
│  │ Pattern Detector  │   the learning loop                        │
│  └────────┬─────────┘                                             │
│           │                                                       │
│           ▼                                                       │
│  ┌──────────────────┐                                             │
│  │ Update Rate       │ ← Limit how fast the system can change     │
│  │ Limiter           │   its beliefs (prevent rapid poisoning)    │
│  └────────┬─────────┘                                             │
│           │                                                       │
│           ▼                                                       │
│  ┌──────────────────┐                                             │
│  │ Ensemble          │ ← Only update if multiple independent      │
│  │ Agreement Gate    │   signals agree on the lesson               │
│  └────────┬─────────┘                                             │
│           │                                                       │
│           ▼                                                       │
│  ┌──────────────────┐                                             │
│  │ Bounded Update    │ ← Clamp max change per update cycle        │
│  │ Application       │                                            │
│  └────────┬─────────┘                                             │
│           │                                                       │
│           ▼                                                       │
│  Reflection Agent (Original)                                      │
└──────────────────────────────────────────────────────────────────┘
```

### Interface

```python
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from enum import Enum
import numpy as np
from collections import deque
import hashlib
import time


class PoisoningVerdict(Enum):
    CLEAN = "clean"                # Normal trade outcome
    SUSPICIOUS = "suspicious"      # Potential manipulation, reduce weight
    POISONED = "poisoned"          # Likely adversarial, discard entirely
    OUTLIER = "outlier"            # Statistical outlier, downweight


@dataclass
class TradeOutcome:
    trade_id: str
    strategy_id: str
    entry_time: float
    exit_time: float
    return_pct: float
    holding_period_hours: float
    signal_strengths: Dict[str, float]  # signal_name → strength at entry
    market_context: Dict                 # regime, volatility, etc.
    metadata: Dict


@dataclass
class AdversarialAssessment:
    trade_id: str
    verdict: PoisoningVerdict
    confidence: float
    reasons: List[str]
    recommended_weight: float  # 0.0 to 1.0, how much to trust this outcome
    details: Dict


class AdversarialRobustnessLayer:
    """
    Sits between trade outcomes and the Reflection Agent's learning loop.
    
    Defense mechanisms:
    1. Statistical outlier detection (basic hygiene)
    2. Adversarial pattern detection (manipulation attempts)
    3. Update rate limiting (prevent rapid belief changes)
    4. Ensemble agreement (multiple signals must agree)
    5. Bounded updates (max change per cycle)
    """
    
    def __init__(self, config: Dict):
        # Outlier detection
        self.outlier_z_threshold = config.get("outlier_z_threshold", 3.0)
        self.min_outlier_sample = config.get("min_outlier_sample", 30)
        
        # Adversarial detection
        self.pattern_window = config.get("pattern_window", 100)
        self.min_pattern_confidence = config.get("min_pattern_confidence", 0.7)
        
        # Update rate limiting
        self.max_update_magnitude = config.get("max_update_magnitude", 0.1)  # 10% max change per cycle
        self.update_cooldown_seconds = config.get("update_cooldown_seconds", 3600)
        self.max_updates_per_day = config.get("max_updates_per_day", 10)
        
        # Ensemble agreement
        self.min_agreement_sources = config.get("min_agreement_sources", 3)
        
        # State
        self.outcome_history: Dict[str, deque] = {}  # strategy_id → outcomes
        self.recent_updates: deque = deque(maxlen=1000)
        self.update_count_today: int = 0
        self.last_update_time: float = 0.0
        self.signal_correlations: Dict[str, deque] = {}
    
    def assess_trade_outcome(
        self, outcome: TradeOutcome
    ) -> AdversarialAssessment:
        """
        Assess whether a trade outcome is safe to feed into the learning loop.
        
        Returns assessment with recommended weight for the learning update.
        """
        reasons = []
        verdict = PoisoningVerdict.CLEAN
        recommended_weight = 1.0
        
        # Layer 1: Statistical outlier detection
        outlier_result = self._check_outlier(outcome)
        if outlier_result:
            verdict = PoisoningVerdict.OUTLIER
            reasons.append(outlier_result)
            recommended_weight *= 0.3  # Heavily downweight outliers
        
        # Layer 2: Adversarial pattern detection
        adversarial_result = self._check_adversarial_pattern(outcome)
        if adversarial_result:
            verdict = PoisoningVerdict.POISONED
            reasons.append(adversarial_result)
            recommended_weight = 0.0  # Completely discard
        
        # Layer 3: Correlation manipulation detection
        correlation_result = self._check_correlation_manipulation(outcome)
        if correlation_result:
            if verdict == PoisoningVerdict.CLEAN:
                verdict = PoisoningVerdict.SUSPICIOUS
            reasons.append(correlation_result)
            recommended_weight *= 0.5
        
        # Layer 4: Update rate check
        rate_result = self._check_update_rate()
        if rate_result:
            reasons.append(rate_result)
            recommended_weight *= 0.2  # Heavily dampen if rate limited
        
        # Compute confidence
        confidence = self._compute_confidence(outcome, len(reasons))
        
        # Record outcome for future pattern detection
        self._record_outcome(outcome)
        
        return AdversarialAssessment(
            trade_id=outcome.trade_id,
            verdict=verdict,
            confidence=confidence,
            reasons=reasons,
            recommended_weight=recommended_weight,
            details={
                "outlier_check": outlier_result,
                "adversarial_check": adversarial_result,
                "correlation_check": correlation_result,
                "rate_check": rate_result,
            }
        )
    
    def _check_outlier(self, outcome: TradeOutcome) -> Optional[str]:
        """
        Detect statistical outliers that may be adversarial.
        
        An adversary might engineer extreme wins to lure the system
        into a trap, or extreme losses to corrupt signal weights.
        Both are suspicious.
        """
        history = self.outcome_history.get(outcome.strategy_id)
        if not history or len(history) < self.min_outlier_sample:
            return None
        
        returns = [o.return_pct for o in history]
        mean_r = np.mean(returns)
        std_r = np.std(returns)
        
        if std_r == 0:
            return None
        
        z_score = abs(outcome.return_pct - mean_r) / std_r
        
        if z_score > self.outlier_z_threshold:
            direction = "gain" if outcome.return_pct > mean_r else "loss"
            return (
                f"OUTLIER: {direction} of {outcome.return_pct:.2%} is "
                f"{z_score:.1f}σ from mean ({mean_r:.2%} ± {std_r:.2%})"
            )
        
        return None
    
    def _check_adversarial_pattern(
        self, outcome: TradeOutcome
    ) -> Optional[str]:
        """
        Detect patterns designed to manipulate the learning loop.
        
        Adversarial patterns:
        1. Alternating win/loss designed to create false signal correlations
        2. Clustered losses after specific signal combinations (targeted poisoning)
        3. Wins that correlate with noise signals (teaching false patterns)
        4. Timing patterns that don't match natural market dynamics
        """
        history = self.outcome_history.get(outcome.strategy_id)
        if not history or len(history) < 20:
            return None
        
        recent = list(history)[-20:]
        
        # Check for alternating pattern (win-loss-win-loss)
        signs = [1 if o.return_pct > 0 else -1 for o in recent]
        alternating_count = sum(
            1 for i in range(1, len(signs))
            if signs[i] != signs[i-1]
        )
        alternating_ratio = alternating_count / (len(signs) - 1)
        
        if alternating_ratio > 0.85:  # Very high alternation is suspicious
            return (
                f"ADVERSARIAL: Suspicious win/loss alternation "
                f"({alternating_ratio:.0%}) — possible pattern injection"
            )
        
        # Check for targeted signal poisoning
        # If a specific signal combination consistently produces losses,
        # it may be adversarial targeting
        signal_patterns = {}
        for o in recent:
            sig_key = tuple(sorted(o.signal_strengths.items()))
            if sig_key not in signal_patterns:
                signal_patterns[sig_key] = []
            signal_patterns[sig_key].append(o.return_pct)
        
        for pattern, returns in signal_patterns.items():
            if len(returns) >= 5:
                # Suspiciously consistent losses on a specific signal combo
                if all(r < 0 for returns in [returns] for r in returns):
                    mean_loss = np.mean(returns)
                    if mean_loss < -0.02:  # >2% average loss
                        return (
                            f"ADVERSARIAL: Signal pattern {pattern[:3]}... "
                            f"consistently loses ({mean_loss:.2%} avg) — "
                            f"possible targeted poisoning"
                        )
        
        # Check for timing manipulation
        holding_periods = [o.holding_period_hours for o in recent]
        if len(holding_periods) >= 10:
            # Unnaturally consistent holding periods suggest algo manipulation
            cv = np.std(holding_periods) / np.mean(holding_periods) if np.mean(holding_periods) > 0 else 0
            if cv < 0.1:  # Coefficient of variation < 10%
                return (
                    f"ADVERSARIAL: Holding periods unnaturally consistent "
                    f"(CV={cv:.2%}) — possible adversarial timing"
                )
        
        return None
    
    def _check_correlation_manipulation(
        self, outcome: TradeOutcome
    ) -> Optional[str]:
        """
        Detect attempts to create false correlations between signals.
        
        An adversary who can influence market data might engineer
        conditions where noise signals appear predictive, poisoning
        the signal weight updates.
        """
        if not outcome.signal_strengths:
            return None
        
        # Track signal-return correlations over time
        for signal_name, strength in outcome.signal_strengths.items():
            key = f"{outcome.strategy_id}:{signal_name}"
            if key not in self.signal_correlations:
                self.signal_correlations[key] = deque(maxlen=200)
            
            self.signal_correlations[key].append(
                (strength, outcome.return_pct)
            )
            
            # Check for sudden correlation shifts
            history = self.signal_correlations[key]
            if len(history) >= 50:
                recent = list(history)[-20:]
                older = list(history)[-50:-20]
                
                recent_corr = self._compute_correlation(recent)
                older_corr = self._compute_correlation(older)
                
                # Sudden correlation appearance is suspicious
                if older_corr is not None and recent_corr is not None:
                    if abs(older_corr) < 0.1 and abs(recent_corr) > 0.5:
                        return (
                            f"SUSPICIOUS: Signal '{signal_name}' suddenly "
                            f"correlated ({older_corr:.2f} → {recent_corr:.2f}) "
                            f"— possible data manipulation"
                        )
        
        return None
    
    def _compute_correlation(
        self, pairs: List[Tuple[float, float]]
    ) -> Optional[float]:
        """Compute Pearson correlation for (signal, return) pairs."""
        if len(pairs) < 10:
            return None
        x = np.array([p[0] for p in pairs])
        y = np.array([p[1] for p in pairs])
        if np.std(x) == 0 or np.std(y) == 0:
            return 0.0
        return float(np.corrcoef(x, y)[0, 1])
    
    def _check_update_rate(self) -> Optional[str]:
        """Enforce rate limits on learning loop updates."""
        now = time.time()
        
        # Cooldown check
        if now - self.last_update_time < self.update_cooldown_seconds:
            remaining = self.update_cooldown_seconds - (now - self.last_update_time)
            return (
                f"RATE_LIMITED: Update cooldown active "
                f"({remaining:.0f}s remaining)"
            )
        
        # Daily limit check
        if self.update_count_today >= self.max_updates_per_day:
            return (
                f"RATE_LIMITED: Daily update limit reached "
                f"({self.update_count_today}/{self.max_updates_per_day})"
            )
        
        return None
    
    def _compute_confidence(
        self, outcome: TradeOutcome, num_flags: int
    ) -> float:
        """Compute confidence in the assessment."""
        # Base confidence from data quality
        base = 0.9 if outcome.metadata.get("verified") else 0.7
        
        # Reduce confidence for each flag raised
        penalty = num_flags * 0.15
        
        return max(0.1, base - penalty)
    
    def _record_outcome(self, outcome: TradeOutcome):
        """Record outcome for pattern detection."""
        if outcome.strategy_id not in self.outcome_history:
            self.outcome_history[outcome.strategy_id] = deque(
                maxlen=self.pattern_window
            )
        self.outcome_history[outcome.strategy_id].append(outcome)
    
    def apply_bounded_update(
        self, current_weights: Dict[str, float],
        proposed_updates: Dict[str, float],
        assessment: AdversarialAssessment
    ) -> Dict[str, float]:
        """
        Apply learning updates with bounds and adversarial filtering.
        
        This is the final gate before updates reach the Reflection Agent.
        """
        now = time.time()
        bounded_updates = {}
        
        for signal_name, proposed_delta in proposed_updates.items():
            current = current_weights.get(signal_name, 0.5)
            
            # Apply adversarial weight (0.0 = ignore, 1.0 = full trust)
            trusted_delta = proposed_delta * assessment.recommended_weight
            
            # Clamp to max update magnitude
            max_delta = self.max_update_magnitude
            clamped_delta = max(-max_delta, min(max_delta, trusted_delta))
            
            # Apply and bound to [0, 1]
            new_weight = max(0.0, min(1.0, current + clamped_delta))
            bounded_updates[signal_name] = new_weight
        
        # Record update
        self.last_update_time = now
        self.update_count_today += 1
        self.recent_updates.append({
            "timestamp": now,
            "assessment": assessment.verdict.value,
            "weight_applied": assessment.recommended_weight,
            "updates": bounded_updates,
        })
        
        return bounded_updates


class ProtectedReflectionAgent:
    """
    Wrapper around the Reflection Agent that adds adversarial robustness.
    
    The original Reflection Agent remains unchanged — this layer sits
    between trade outcomes and the learning loop.
    """
    
    def __init__(self, reflection_agent, config: Dict):
        self.reflection_agent = reflection_agent
        self.robustness_layer = AdversarialRobustnessLayer(config)
        self.quarantine: List[TradeOutcome] = []  # Outcomes pending review
    
    def on_trade_closed(self, outcome: TradeOutcome) -> Dict[str, float]:
        """
        Process a trade outcome through adversarial robustness checks
        before feeding to the Reflection Agent.
        """
        # Assess outcome
        assessment = self.robustness_layer.assess_trade_outcome(outcome)
        
        if assessment.verdict == PoisoningVerdict.POISONED:
            # Quarantine for human review
            self.quarantine.append(outcome)
            self._alert_poisoning_detected(outcome, assessment)
            return {}  # No update applied
        
        if assessment.verdict == PoisoningVerdict.SUSPICIOUS:
            # Log but allow with reduced weight
            self._log_suspicious(outcome, assessment)
        
        # Get proposed updates from Reflection Agent
        current_weights = self.reflection_agent.get_signal_weights()
        proposed_updates = self.reflection_agent.compute_weight_deltas(
            outcome
        )
        
        # Apply through robustness layer
        bounded_updates = self.robustness_layer.apply_bounded_update(
            current_weights, proposed_updates, assessment
        )
        
        return bounded_updates
    
    def _alert_poisoning_detected(
        self, outcome: TradeOutcome, assessment: AdversarialAssessment
    ):
        """Alert on detected poisoning attempt."""
        # Integration point: send alert to monitoring/dashboard
        pass
    
    def _log_suspicious(
        self, outcome: TradeOutcome, assessment: AdversarialAssessment
    ):
        """Log suspicious outcome for analysis."""
        pass
```

### Integration Points

```python
# Replace direct Reflection Agent calls:

# BEFORE (vulnerable):
reflection_agent.on_trade_closed(outcome)
reflection_agent.update_signal_weights()

# AFTER (protected):
protected_reflection = ProtectedReflectionAgent(
    reflection_agent, 
    config={
        "outlier_z_threshold": 3.0,
        "max_update_magnitude": 0.1,
        "max_updates_per_day": 10,
        "update_cooldown_seconds": 3600,
    }
)
protected_reflection.on_trade_closed(outcome)
```

### Acceptance Criteria

- [ ] Statistical outliers detected and downweighted (z-score > 3.0)
- [ ] Alternating win/loss patterns flagged as adversarial
- [ ] Targeted signal poisoning detected (consistent losses on specific patterns)
- [ ] Sudden signal correlation shifts flagged
- [ ] Update rate limited to max 10 per day with 1h cooldown
- [ ] Max weight change per update bounded to 10%
- [ ] Poisoned outcomes quarantined for human review
- [ ] Reflection Agent code remains unchanged (wrapper pattern)
- [ ] Alerting on detected poisoning attempts

---

## FIX 3: Model Capability Abstraction Interface

### Problem
Models are hard-coded to strategy steps. Swapping XGBoost for a new library requires rewriting agent code. When a single AGI model can replace all 8 families, the entire pipeline must be rewritten. This is **model architecture lock-in**.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                 MODEL CAPABILITY ABSTRACTION LAYER                    │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    CAPABILITY REGISTRY                       │    │
│  │                                                              │    │
│  │  Capabilities:                                               │    │
│  │    sentiment_analysis → [FinBERT_v3, Qwen_v2, AGI_Unified]  │    │
│  │    regime_detection   → [HMM_v2, XGBoost_Regime, AGI_Unified]│    │
│  │    price_direction    → [XGBoost_v4, LSTM_v2, AGI_Unified]  │    │
│  │    position_sizing    → [RL_PPO_v1, XGBoost_Sizing]         │    │
│  │    confluence_scoring → [XGBoost_v3, Ensemble_v1]           │    │
│  │    ...                                                       │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    MODEL ROUTER                              │    │
│  │                                                              │    │
│  │  get_best(capability) → Model                               │    │
│  │    1. Check performance leaderboard                          │    │
│  │    2. Apply A/B traffic split                                │    │
│  │    3. Route to winner or canary                              │    │
│  │                                                              │    │
│  │  register(model, capabilities[]) → None                     │    │
│  │  swap(capability, old_model, new_model) → MigrationPlan     │    │
│  │  get_leaderboard(capability) → List[ModelPerformance]       │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    UNIFIED MODEL ADAPTER                     │    │
│  │                                                              │    │
│  │  Wraps ANY model (XGBoost, LSTM, HMM, RL, AGI API) into    │    │
│  │  a uniform capability interface.                             │    │
│  │                                                              │    │
│  │  class UnifiedModelAdapter(ModelInterface):                  │    │
│  │      def predict_sentiment(text) → SentimentResult          │    │
│  │      def predict_direction(features) → DirectionResult      │    │
│  │      def detect_regime(market_state) → RegimeResult         │    │
│  │      def score_confluence(signals) → ConfluenceResult       │    │
│  │      def size_position(context) → PositionSizeResult        │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

### Interface

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Type
import time
import threading


# ─────────────────────────────────────────────────────────────
# Capability Definitions
# ─────────────────────────────────────────────────────────────

class Capability(str, Enum):
    """All model capabilities in the trading system."""
    SENTIMENT_ANALYSIS = "sentiment_analysis"
    REGIME_DETECTION = "regime_detection"
    PRICE_DIRECTION = "price_direction"
    CONFLUENCE_SCORING = "confluence_scoring"
    POSITION_SIZING = "position_sizing"
    RISK_SCORING = "risk_scoring"
    NEWS_SUMMARIZATION = "news_summarization"
    PATTERN_RECOGNITION = "pattern_recognition"
    ORDER_FLOW_ANALYSIS = "order_flow_analysis"
    MACRO_ANALYSIS = "macro_analysis"
    # AGI unified capability (replaces all above)
    UNIFIED_ANALYSIS = "unified_analysis"


@dataclass
class PredictionResult:
    """Universal result wrapper for any model prediction."""
    value: Any                          # The prediction itself
    confidence: float                   # 0.0 to 1.0
    latency_ms: float                   # Inference time
    model_id: str                       # Which model produced this
    capability: Capability              # Which capability was used
    metadata: Dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class ModelPerformance:
    """Track record for a model on a specific capability."""
    model_id: str
    capability: Capability
    total_predictions: int = 0
    correct_predictions: int = 0
    avg_confidence: float = 0.0
    avg_latency_ms: float = 0.0
    sharpe_contribution: float = 0.0    # Contribution to strategy Sharpe
    last_evaluated: float = 0.0
    recent_accuracy: List[float] = field(default_factory=list)  # Rolling
    error_count: int = 0
    is_active: bool = True


@dataclass
class MigrationPlan:
    """Plan for migrating from one model to another."""
    capability: Capability
    old_model_id: str
    new_model_id: str
    phases: List[Dict]                  # Shadow → Canary → Full
    current_phase: int = 0
    started_at: float = 0.0
    estimated_completion: float = 0.0
    rollback_triggered: bool = False


# ─────────────────────────────────────────────────────────────
# Base Model Interface (ALL models implement this)
# ─────────────────────────────────────────────────────────────

class ModelInterface(ABC):
    """
    Base interface that every model must implement.
    
    This is the ONLY contract between models and the rest of the system.
    Agents never import model-specific classes — they use this interface.
    """
    
    @abstractmethod
    def get_model_id(self) -> str:
        """Unique identifier for this model instance."""
        ...
    
    @abstractmethod
    def get_capabilities(self) -> Set[Capability]:
        """What this model can do."""
        ...
    
    @abstractmethod
    def predict(self, capability: Capability, inputs: Dict) -> PredictionResult:
        """
        Make a prediction for a specific capability.
        
        The model routes internally based on capability.
        A unified AGI model would handle ALL capabilities here.
        A specialized model only handles its specific capability.
        """
        ...
    
    @abstractmethod
    def get_supported_input_schema(self, capability: Capability) -> Dict:
        """Describe what inputs this model expects for a capability."""
        ...
    
    def get_health(self) -> Dict:
        """Health check. Override for custom health monitoring."""
        return {"status": "healthy", "model_id": self.get_model_id()}
    
    def warmup(self) -> bool:
        """Optional warmup call (load weights, etc). Returns True if ready."""
        return True
    
    def shutdown(self):
        """Cleanup when model is being replaced."""
        pass


# ─────────────────────────────────────────────────────────────
# Specialized Model Implementations (examples)
# ─────────────────────────────────────────────────────────────

class SpecializedModelAdapter(ModelInterface):
    """
    Adapter for existing specialized models (XGBoost, LSTM, HMM, etc.).
    Wraps them into the ModelInterface without changing their code.
    """
    
    def __init__(
        self,
        model_id: str,
        capabilities: Set[Capability],
        underlying_model: Any,
        predict_fn: Any  # Callable that maps (capability, inputs) → result
    ):
        self._model_id = model_id
        self._capabilities = capabilities
        self._underlying = underlying_model
        self._predict_fn = predict_fn
    
    def get_model_id(self) -> str:
        return self._model_id
    
    def get_capabilities(self) -> Set[Capability]:
        return self._capabilities
    
    def predict(self, capability: Capability, inputs: Dict) -> PredictionResult:
        if capability not in self._capabilities:
            raise ValueError(
                f"Model {self._model_id} does not support {capability}"
            )
        
        start = time.time()
        result = self._predict_fn(self._underlying, capability, inputs)
        latency = (time.time() - start) * 1000
        
        return PredictionResult(
            value=result,
            confidence=result.get("confidence", 0.5) if isinstance(result, dict) else 0.5,
            latency_ms=latency,
            model_id=self._model_id,
            capability=capability,
        )
    
    def get_supported_input_schema(self, capability: Capability) -> Dict:
        # Delegate to underlying model's schema
        return {"type": "specialized", "model": self._model_id}


class AGIUnifiedModel(ModelInterface):
    """
    Adapter for a single AGI model that replaces ALL specialized models.
    
    This is the future: one model handles everything.
    The capability abstraction layer means this is a drop-in replacement.
    """
    
    def __init__(self, model_id: str, api_endpoint: str, api_key: str):
        self._model_id = model_id
        self._endpoint = api_endpoint
        self._key = api_key
        self._capabilities = set(Capability)  # Supports everything
    
    def get_model_id(self) -> str:
        return self._model_id
    
    def get_capabilities(self) -> Set[Capability]:
        return self._capabilities
    
    def predict(self, capability: Capability, inputs: Dict) -> PredictionResult:
        """
        Route to AGI model with capability-specific prompting.
        
        The AGI model receives the capability context and raw inputs,
        then returns a structured prediction.
        """
        start = time.time()
        
        # Construct capability-specific prompt/context
        prompt = self._build_capability_prompt(capability, inputs)
        
        # Call AGI model
        result = self._call_agi(prompt)
        
        latency = (time.time() - start) * 1000
        
        return PredictionResult(
            value=result,
            confidence=result.get("confidence", 0.8),
            latency_ms=latency,
            model_id=self._model_id,
            capability=capability,
            metadata={"agi_model": True, "unified": True},
        )
    
    def _build_capability_prompt(
        self, capability: Capability, inputs: Dict
    ) -> str:
        """Build a prompt tailored to the capability."""
        capability_prompts = {
            Capability.SENTIMENT_ANALYSIS: (
                "Analyze the sentiment of the following financial text. "
                "Return: {sentiment: float[-1,1], confidence: float, key_phrases: list}"
            ),
            Capability.REGIME_DETECTION: (
                "Given the following market state data, identify the current "
                "market regime. Return: {regime: str, confidence: float, "
                "transition_probability: float}"
            ),
            Capability.PRICE_DIRECTION: (
                "Based on the following features, predict price direction. "
                "Return: {direction: up/down/flat, magnitude: float, "
                "confidence: float, timeframe: str}"
            ),
            # ... other capabilities
        }
        
        prompt = capability_prompts.get(
            capability,
            f"Analyze the following data for {capability.value}. "
            f"Return a structured JSON result with confidence."
        )
        
        return f"{prompt}\n\nInput data: {inputs}"
    
    def _call_agi(self, prompt: str) -> Dict:
        """Call the AGI model API."""
        # Implementation: HTTP call to AGI endpoint
        # This is where you'd integrate GPT-5, Claude, Gemini, etc.
        # when they reach AGI-level capabilities
        raise NotImplementedError("AGI model integration pending")
    
    def get_supported_input_schema(self, capability: Capability) -> Dict:
        return {
            "type": "flexible",
            "model": self._model_id,
            "note": "AGI model accepts any structured input",
        }


# ─────────────────────────────────────────────────────────────
# Capability Registry + Model Router
# ─────────────────────────────────────────────────────────────

class CapabilityRegistry:
    """
    Central registry that maps capabilities to available models.
    
    Agents request capabilities, not models. The registry routes
    to the best available model for each capability.
    """
    
    def __init__(self):
        self._models: Dict[str, ModelInterface] = {}
        self._capability_map: Dict[Capability, List[str]] = {
            cap: [] for cap in Capability
        }
        self._performance: Dict[str, ModelPerformance] = {}
        self._lock = threading.Lock()
    
    def register(self, model: ModelInterface):
        """Register a model and its capabilities."""
        with self._lock:
            model_id = model.get_model_id()
            self._models[model_id] = model
            
            for cap in model.get_capabilities():
                if model_id not in self._capability_map[cap]:
                    self._capability_map[cap].append(model_id)
                
                perf_key = f"{model_id}:{cap.value}"
                if perf_key not in self._performance:
                    self._performance[perf_key] = ModelPerformance(
                        model_id=model_id,
                        capability=cap,
                    )
    
    def unregister(self, model_id: str):
        """Remove a model from the registry."""
        with self._lock:
            model = self._models.pop(model_id, None)
            if model:
                for cap in model.get_capabilities():
                    if model_id in self._capability_map[cap]:
                        self._capability_map[cap].remove(model_id)
    
    def get_best(
        self, capability: Capability, strategy: str = "performance"
    ) -> Optional[ModelInterface]:
        """
        Get the best model for a capability.
        
        Strategies:
        - "performance": Route to highest accuracy model
        - "latency": Route to fastest model
        - "balanced": Weighted score of accuracy + latency
        - "canary": Route to the canary model for A/B testing
        """
        with self._lock:
            candidates = self._capability_map.get(capability, [])
            if not candidates:
                # Check if any model supports UNIFIED_ANALYSIS
                candidates = self._capability_map.get(
                    Capability.UNIFIED_ANALYSIS, []
                )
            
            if not candidates:
                return None
            
            if strategy == "canary":
                # Return the last registered (newest) model
                return self._models.get(candidates[-1])
            
            # Score each candidate
            best_id = None
            best_score = float("-inf")
            
            for model_id in candidates:
                perf_key = f"{model_id}:{capability.value}"
                perf = self._performance.get(perf_key)
                
                if not perf or not perf.is_active:
                    continue
                
                if strategy == "performance":
                    score = self._accuracy_score(perf)
                elif strategy == "latency":
                    score = -perf.avg_latency_ms  # Lower is better
                else:  # balanced
                    score = (
                        0.7 * self._accuracy_score(perf)
                        + 0.3 * (-perf.avg_latency_ms / 100)
                    )
                
                if score > best_score:
                    best_score = score
                    best_id = model_id
            
            return self._models.get(best_id) if best_id else None
    
    def predict(
        self, capability: Capability, inputs: Dict, strategy: str = "performance"
    ) -> PredictionResult:
        """
        High-level: get best model and make prediction.
        This is what agents call.
        """
        model = self.get_best(capability, strategy)
        if not model:
            raise RuntimeError(f"No model available for {capability}")
        
        return model.predict(capability, inputs)
    
    def record_prediction_result(
        self,
        model_id: str,
        capability: Capability,
        correct: bool,
        latency_ms: float
    ):
        """Record a prediction result for performance tracking."""
        perf_key = f"{model_id}:{capability.value}"
        with self._lock:
            perf = self._performance.get(perf_key)
            if perf:
                perf.total_predictions += 1
                if correct:
                    perf.correct_predictions += 1
                perf.recent_accuracy.append(1.0 if correct else 0.0)
                if len(perf.recent_accuracy) > 100:
                    perf.recent_accuracy = perf.recent_accuracy[-100:]
                # Update rolling average latency
                perf.avg_latency_ms = (
                    perf.avg_latency_ms * 0.95 + latency_ms * 0.05
                )
                perf.last_evaluated = time.time()
    
    def swap(
        self,
        capability: Capability,
        old_model_id: str,
        new_model_id: str
    ) -> MigrationPlan:
        """
        Initiate a model swap with gradual migration.
        
        Phases:
        1. Shadow: New model runs in parallel, results logged but not used
        2. Canary: 10% traffic to new model
        3. Full: 100% traffic to new model
        4. Cleanup: Old model removed
        """
        plan = MigrationPlan(
            capability=capability,
            old_model_id=old_model_id,
            new_model_id=new_model_id,
            phases=[
                {"name": "shadow", "traffic_pct": 0, "duration_hours": 168},
                {"name": "canary", "traffic_pct": 10, "duration_hours": 72},
                {"name": "full", "traffic_pct": 100, "duration_hours": 48},
                {"name": "cleanup", "traffic_pct": 100, "duration_hours": 0},
            ],
            started_at=time.time(),
        )
        
        return plan
    
    def _accuracy_score(self, perf: ModelPerformance) -> float:
        """Compute accuracy score with recency weighting."""
        if not perf.recent_accuracy:
            return 0.5  # No data, assume average
        
        # Exponentially weighted recent accuracy
        weights = np.exp(np.linspace(-1, 0, len(perf.recent_accuracy)))
        weights /= weights.sum()
        return float(np.dot(perf.recent_accuracy, weights))
    
    def get_leaderboard(
        self, capability: Capability
    ) -> List[ModelPerformance]:
        """Get performance leaderboard for a capability."""
        candidates = self._capability_map.get(capability, [])
        perfs = []
        for model_id in candidates:
            perf_key = f"{model_id}:{capability.value}"
            perf = self._performance.get(perf_key)
            if perf:
                perfs.append(perf)
        
        perfs.sort(
            key=lambda p: self._accuracy_score(p), reverse=True
        )
        return perfs


# ─────────────────────────────────────────────────────────────
# Migration from current architecture
# ─────────────────────────────────────────────────────────────

class ModelMigrationHelper:
    """
    Helper to migrate from current hardcoded model-to-step mapping
    to capability-based routing.
    
    Maps current step definitions to capabilities.
    """
    
    # Current step → Capability mapping
    STEP_TO_CAPABILITY = {
        "step1_sentiment": Capability.SENTIMENT_ANALYSIS,
        "step2_regime": Capability.REGIME_DETECTION,
        "step3_session_analysis": Capability.PATTERN_RECOGNITION,
        "step4_confluence": Capability.CONFLUENCE_SCORING,
        "step5_direction": Capability.PRICE_DIRECTION,
        "step6_sizing": Capability.POSITION_SIZING,
        "step7_risk": Capability.RISK_SCORING,
        "step8_execution": Capability.ORDER_FLOW_ANALYSIS,
    }
    
    @classmethod
    def wrap_existing_models(
        cls, model_manager: Any
    ) -> CapabilityRegistry:
        """
        Wrap all existing models from ModelManager into the
        capability registry.
        
        This enables incremental migration — existing models
        work unchanged, but are now accessed via capabilities.
        """
        registry = CapabilityRegistry()
        
        # Example: wrap XGBoost models
        for model_name, model_obj in model_manager.models.items():
            # Determine capabilities from model name/type
            capabilities = cls._infer_capabilities(model_name)
            
            adapter = SpecializedModelAdapter(
                model_id=model_name,
                capabilities=capabilities,
                underlying_model=model_obj,
                predict_fn=cls._default_predict_fn,
            )
            
            registry.register(adapter)
        
        return registry
    
    @classmethod
    def _infer_capabilities(
        cls, model_name: str
    ) -> Set[Capability]:
        """Infer capabilities from model name."""
        name_lower = model_name.lower()
        
        caps = set()
        if "sentiment" in name_lower or "finbert" in name_lower:
            caps.add(Capability.SENTIMENT_ANALYSIS)
        if "regime" in name_lower or "hmm" in name_lower:
            caps.add(Capability.REGIME_DETECTION)
        if "direction" in name_lower or "xgboost" in name_lower:
            caps.add(Capability.PRICE_DIRECTION)
        if "confluence" in name_lower:
            caps.add(Capability.CONFLUENCE_SCORING)
        if "sizing" in name_lower or "rl" in name_lower:
            caps.add(Capability.POSITION_SIZING)
        if "risk" in name_lower:
            caps.add(Capability.RISK_SCORING)
        
        return caps if caps else {Capability.PRICE_DIRECTION}  # Default
    
    @classmethod
    def _default_predict_fn(
        cls, model: Any, capability: Capability, inputs: Dict
    ) -> Dict:
        """Default prediction function for wrapped models."""
        # Call model's predict method with appropriate inputs
        if hasattr(model, "predict"):
            return model.predict(inputs)
        elif hasattr(model, "predict_proba"):
            return {"probability": model.predict_proba(inputs)}
        else:
            raise RuntimeError(f"Model {model} has no predict method")
```

### Integration Points

```python
# Step 1: Create registry from existing models
registry = ModelMigrationHelper.wrap_existing_models(model_manager)

# Step 2: Replace hardcoded model calls in agents
# BEFORE:
#   sentiment = finbert_model.predict(text)
#   regime = hmm_model.detect(market_state)
#   direction = xgboost_direction.predict(features)

# AFTER:
#   sentiment = registry.predict(Capability.SENTIMENT_ANALYSIS, {"text": text})
#   regime = registry.predict(Capability.REGIME_DETECTION, {"state": market_state})
#   direction = registry.predict(Capability.PRICE_DIRECTION, {"features": features})

# Step 3: When AGI model arrives, register it:
agi_model = AGIUnifiedModel(
    model_id="agi_v1",
    api_endpoint="https://api.agi.example.com/v1",
    api_key="..."
)
registry.register(agi_model)

# Step 4: Gradually migrate each capability
plan = registry.swap(
    Capability.SENTIMENT_ANALYSIS,
    old_model_id="finbert_v3",
    new_model_id="agi_v1"
)
```

### Acceptance Criteria

- [ ] All models wrapped in `ModelInterface` without code changes
- [ ] Capability registry routes to best model per capability
- [ ] Performance leaderboard tracks accuracy per model per capability
- [ ] Model swap with shadow → canary → full migration phases
- [ ] AGI unified model integrates as single drop-in replacement
- [ ] Agents use `registry.predict(capability, inputs)` — never import model classes
- [ ] Hot-swap supported (register/unregister without restart)
- [ ] Rollback triggers on performance degradation

---

## FIX 4: Opponent Strategy Estimator + Game-Theoretic Layer

### Problem
The system optimizes against historical patterns as if markets are natural phenomena. In AGI-era markets, patterns are created and destroyed by competing AI agents. The system is playing a game while unaware of the other players. This is **AI-vs-AI blindness**.

### Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                OPPONENT STRATEGY ESTIMATOR                            │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  MARKET MICROSTRUCTURE OBSERVER                                 │  │
│  │  - Order book pattern analysis                                  │  │
│  │  - Trade flow fingerprinting                                    │  │
│  │  - Latency distribution analysis                                │  │
│  │  - Correlated action detection                                  │  │
│  └──────────────────────────┬─────────────────────────────────────┘  │
│                              │                                        │
│                              ▼                                        │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  AGENT FINGERPRINT CLASSIFIER                                   │  │
│  │                                                                  │  │
│  │  Known agent archetypes:                                        │  │
│  │    TREND_FOLLOWER  — Momentum-based, trailing stops              │  │
│  │    MEAN_REVERTER   — RSI/BB-based, counter-trend                 │  │
│  │    SMC_TRADER      — Smart Money Concepts, order blocks          │  │
│  │    ARBITRAGEUR     — Cross-exchange, latency-sensitive            │  │
│  │    MARKET_MAKER    — Spread capture, inventory management        │  │
│  │    MOMENTUM_IGNITION — Adversarial, triggers then fades           │  │
│  │    UNKNOWN         — New/unclassified agent type                  │  │
│  └──────────────────────────┬─────────────────────────────────────┘  │
│                              │                                        │
│                              ▼                                        │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  CROWDING ESTIMATOR                                             │  │
│  │  - What % of market is running similar strategy?                │  │
│  │  - Is the crowd growing or shrinking?                           │  │
│  │  - What's the crowd's likely next move?                         │  │
│  └──────────────────────────┬─────────────────────────────────────┘  │
│                              │                                        │
│                              ▼                                        │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  GAME-THEORETIC ADVISOR                                         │  │
│  │                                                                  │  │
│  │  Given: Our strategy + Estimated opponent strategies             │  │
│  │  Compute:                                                        │  │
│  │    - Nash equilibrium position sizing                            │  │
│  │    - Optimal mixed strategy (randomization)                      │  │
│  │    - Counter-exploitation moves                                  │  │
│  │    - Anti-correlated strategy selection                          │  │
│  └──────────────────────────┬─────────────────────────────────────┘  │
│                              │                                        │
│                              ▼                                        │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  STRATEGY ADAPTATION ENGINE                                     │  │
│  │                                                                  │  │
│  │  Actions:                                                        │  │
│  │    SHIFT_TIMING  — Offset entry/exit from detected crowd         │  │
│  │    ADD_NOISE     — Randomize parameters to avoid fingerprinting  │  │
│  │    CONTRARIAN    — Fade the crowd when crowd is wrong             │  │
│  │    DECOY         — Place decoy orders to mislead opponents        │  │
│  │    EXIT_CROWD    — Exit when crowd is too large                   │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

### Interface

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple
import numpy as np
from collections import defaultdict, deque
import time


class AgentArchetype(Enum):
    """Known types of AI trading agents in the market."""
    TREND_FOLLOWER = "trend_follower"
    MEAN_REVERTER = "mean_reverter"
    SMC_TRADER = "smc_trader"
    ARBITRAGEUR = "arbitrageur"
    MARKET_MAKER = "market_maker"
    MOMENTUM_IGNITION = "momentum_ignition"
    STAT_ARB = "statistical_arbitrage"
    NEWS_REACTOR = "news_reactor"
    UNKNOWN = "unknown"


class AdaptationAction(Enum):
    """Actions to take in response to opponent modeling."""
    HOLD = "hold"                         # No change needed
    SHIFT_TIMING = "shift_timing"         # Offset from crowd timing
    ADD_NOISE = "add_noise"               # Randomize parameters
    CONTRARIAN = "contrarian"             # Fade the crowd
    EXIT_CROWD = "exit_crowd"             # Exit crowded positions
    REDUCE_SIZE = "reduce_size"           # Reduce position size
    SWITCH_STRATEGY = "switch_strategy"   # Switch to uncorrelated strategy
    TIGHTEN_STOPS = "tighten_stops"       # Tighten stop losses


@dataclass
class OrderBookSnapshot:
    """Point-in-time order book state."""
    timestamp: float
    bids: List[Tuple[float, float]]       # (price, size)
    asks: List[Tuple[float, float]]
    trade_flow: List[Dict]                # Recent trades
    metadata: Dict = field(default_factory=dict)


@dataclass
class AgentFingerprint:
    """Detected characteristics of a market participant."""
    agent_id: str                          # Anonymized identifier
    archetype: AgentArchetype
    confidence: float                      # 0.0 to 1.0
    characteristics: Dict                  # Detected behavior patterns
    first_seen: float
    last_seen: float
    trade_count: int = 0
    estimated_strategy: str = ""
    risk_to_us: float = 0.0               # How much they threaten our alpha


@dataclass
class CrowdingAssessment:
    """Assessment of strategy crowding in the market."""
    our_strategy_id: str
    crowd_percentage: float               # 0-1, % of market running similar strategy
    crowd_trend: float                    # Growing (>0) or shrinking (<0)
    crowd_archetypes: Dict[str, float]    # archetype → estimated %
    dominant_archetype: AgentArchetype
    estimated_crowd_next_move: str
    confidence: float
    timestamp: float


@dataclass
class GameTheoreticAdvice:
    """Advice from the game-theoretic layer."""
    action: AdaptationAction
    parameters: Dict                       # Action-specific parameters
    reasoning: str
    expected_impact: float                 # Expected P&L impact
    confidence: float
    alternatives: List[Dict]               # Other options considered


class MarketMicrostructureObserver:
    """
    Observes order book and trade flow to detect AI agent behavior.
    
    Key signals:
    1. Order placement patterns (latency, size, cancellation rate)
    2. Trade flow correlation (multiple agents acting in concert)
    3. Spread dynamics (market maker presence and behavior)
    4. Flash crash amplification (cascade detection)
    """
    
    def __init__(self, config: Dict):
        self.lookback_seconds = config.get("lookback_seconds", 300)
        self.min_trades_for_pattern = config.get("min_trades_for_pattern", 50)
        
        # Trade history for pattern detection
        self.trade_history: deque = deque(maxlen=10000)
        self.order_book_history: deque = deque(maxlen=1000)
        
        # Detected agent profiles
        self.detected_agents: Dict[str, AgentFingerprint] = {}
        self._agent_counter = 0
    
    def observe(self, snapshot: OrderBookSnapshot):
        """Process a new order book observation."""
        self.order_book_history.append(snapshot)
        self.trade_history.extend(snapshot.trade_flow)
        
        # Run detection algorithms
        self._detect_agent_clusters(snapshot)
        self._detect_correlated_actions()
        self._detect_spoofing_patterns(snapshot)
    
    def _detect_agent_clusters(self, snapshot: OrderBookSnapshot):
        """
        Cluster trades by behavior to identify distinct agents.
        
        Clustering features:
        - Trade size distribution
        - Timing patterns (regularity, burstiness)
        - Order-to-trade ratio
        - Cancellation patterns
        - Price level preferences
        """
        recent_trades = list(self.trade_history)[-200:]
        if len(recent_trades) < self.min_trades_for_pattern:
            return
        
        # Extract features per trade cluster
        # (Simplified — real implementation would use DBSCAN or similar)
        size_clusters = self._cluster_by_size(recent_trades)
        timing_clusters = self._cluster_by_timing(recent_trades)
        
        # Merge clusters into agent fingerprints
        for cluster_id, trades in size_clusters.items():
            if cluster_id not in self.detected_agents:
                self._agent_counter += 1
                agent_id = f"agent_{self._agent_counter}"
                
                archetype = self._classify_archetype(trades)
                
                self.detected_agents[agent_id] = AgentFingerprint(
                    agent_id=agent_id,
                    archetype=archetype,
                    confidence=0.5,  # Initial, increases with more data
                    characteristics=self._extract_characteristics(trades),
                    first_seen=time.time(),
                    last_seen=time.time(),
                    trade_count=len(trades),
                )
    
    def _cluster_by_size(
        self, trades: List[Dict]
    ) -> Dict[str, List[Dict]]:
        """Cluster trades by size distribution."""
        clusters = defaultdict(list)
        for trade in trades:
            size = trade.get("size", 0)
            # Bucket by order of magnitude
            if size < 0.01:
                clusters["micro"].append(trade)
            elif size < 0.1:
                clusters["small"].append(trade)
            elif size < 1.0:
                clusters["medium"].append(trade)
            elif size < 10.0:
                clusters["large"].append(trade)
            else:
                clusters["whale"].append(trade)
        return dict(clusters)
    
    def _cluster_by_timing(
        self, trades: List[Dict]
    ) -> Dict[str, List[Dict]]:
        """Cluster trades by timing patterns."""
        clusters = defaultdict(list)
        for trade in trades:
            # Classify by regularity
            interval = trade.get("interval_since_last", 0)
            if interval < 0.01:  # <10ms — HFT
                clusters["hft"].append(trade)
            elif interval < 1.0:  # <1s — fast algo
                clusters["fast_algo"].append(trade)
            elif interval < 60:  # <1min — algo
                clusters["algo"].append(trade)
            else:
                clusters["slow"].append(trade)
        return dict(clusters)
    
    def _classify_archetype(
        self, trades: List[Dict]
    ) -> AgentArchetype:
        """Classify a cluster of trades into an agent archetype."""
        if not trades:
            return AgentArchetype.UNKNOWN
        
        # Analyze trade direction consistency
        directions = [t.get("side", "unknown") for t in trades]
        buy_ratio = directions.count("buy") / len(directions) if directions else 0.5
        
        # Analyze timing regularity
        intervals = [t.get("interval_since_last", 0) for t in trades if t.get("interval_since_last")]
        timing_cv = np.std(intervals) / np.mean(intervals) if intervals and np.mean(intervals) > 0 else 1.0
        
        # Analyze size consistency
        sizes = [t.get("size", 0) for t in trades]
        size_cv = np.std(sizes) / np.mean(sizes) if sizes and np.mean(sizes) > 0 else 1.0
        
        # Classification heuristics
        if timing_cv < 0.1 and size_cv < 0.1:
            return AgentArchetype.MARKET_MAKER  # Very regular
        if timing_cv < 0.2 and buy_ratio > 0.8:
            return AgentArchetype.TREND_FOLLOWER  # Consistent direction
        if timing_cv < 0.2 and 0.3 < buy_ratio < 0.7:
            return AgentArchetype.MEAN_REVERTER  # Both sides
        if np.mean(intervals) < 0.01 if intervals else False:
            return AgentArchetype.ARBITRAGEUR  # Ultra-fast
        
        return AgentArchetype.UNKNOWN
    
    def _extract_characteristics(
        self, trades: List[Dict]
    ) -> Dict:
        """Extract behavioral characteristics from trades."""
        sizes = [t.get("size", 0) for t in trades]
        intervals = [t.get("interval_since_last", 0) for t in trades if t.get("interval_since_last")]
        
        return {
            "avg_trade_size": float(np.mean(sizes)) if sizes else 0,
            "avg_interval": float(np.mean(intervals)) if intervals else 0,
            "trade_count": len(trades),
            "size_consistency": 1.0 - (np.std(sizes) / np.mean(sizes) if sizes and np.mean(sizes) > 0 else 1.0),
            "timing_consistency": 1.0 - (np.std(intervals) / np.mean(intervals) if intervals and np.mean(intervals) > 0 else 1.0),
        }
    
    def _detect_correlated_actions(self):
        """
        Detect multiple agents acting in concert.
        
        Correlated actions indicate:
        1. Multiple agents running the same strategy (crowding)
        2. Coordinated manipulation (adversarial)
        3. Herd behavior (cascade risk)
        """
        recent_trades = list(self.trade_history)[-100:]
        if len(recent_trades) < 20:
            return
        
        # Check for correlated direction changes
        # If many agents switch from buy to sell within a short window
        # that's a cascade risk
        timestamps = [t.get("timestamp", 0) for t in recent_trades]
        sides = [1 if t.get("side") == "buy" else -1 for t in recent_trades]
        
        # Rolling correlation of trade directions
        window = 20
        for i in range(window, len(sides)):
            window_sides = sides[i-window:i]
            # High autocorrelation = correlated agents
            autocorr = np.corrcoef(
                window_sides[:-1], window_sides[1:]
            )[0, 1] if len(window_sides) > 1 else 0
            
            if abs(autocorr) > 0.7:
                # High correlation detected — potential cascade
                pass  # Log and alert
    
    def _detect_spoofing_patterns(self, snapshot: OrderBookSnapshot):
        """
        Detect spoofing patterns (large orders placed and quickly cancelled).
        
        Spoofing is a common adversarial tactic:
        1. Place large order to create false impression
        2. Other agents react to the apparent liquidity
        3. Cancel the large order
        4. Profit from the reaction
        """
        # Compare current order book with recent history
        if len(self.order_book_history) < 2:
            return
        
        prev = self.order_book_history[-2]
        
        # Check for sudden large order appearances/disappearances
        for side in ["bids", "asks"]:
            current_levels = {p: s for p, s in getattr(snapshot, side, [])}
            prev_levels = {p: s for p, s in getattr(prev, side, [])}
            
            # Find orders that appeared and disappeared quickly
            for price, size in prev_levels.items():
                if price in current_levels:
                    if prev_levels[price] > current_levels.get(price, 0) * 3:
                        # Large order reduced significantly — potential spoof
                        pass  # Log and flag


class CrowdingEstimator:
    """
    Estimates what percentage of the market is running similar strategies.
    
    Core question: "Are we trading against humans or against copies of ourselves?"
    """
    
    def __init__(self, microstructure_observer: MarketMicrostructureObserver):
        self.observer = microstructure_observer
        self.crowding_history: deque = deque(maxlen=1000)
    
    def estimate_crowding(
        self, our_strategy_signals: Dict[str, float]
    ) -> CrowdingAssessment:
        """
        Estimate how crowded our strategy is.
        
        Method:
        1. Compare our signal patterns with detected agent behaviors
        2. Estimate % of market following similar patterns
        3. Track trend (growing or shrinking crowd)
        """
        # Count agents by archetype
        archetype_counts = defaultdict(int)
        total_agents = len(self.observer.detected_agents)
        
        for agent in self.observer.detected_agents.values():
            archetype_counts[agent.archetype] += 1
        
        # Estimate crowd percentage
        # (How many agents are likely running strategies similar to ours?)
        similar_archetypes = self._get_similar_archetypes(our_strategy_signals)
        crowd_count = sum(
            archetype_counts.get(a, 0) for a in similar_archetypes
        )
        crowd_pct = crowd_count / max(total_agents, 1)
        
        # Compute trend
        crowd_trend = self._compute_crowd_trend(crowd_pct)
        
        # Determine dominant archetype
        if archetype_counts:
            dominant = max(archetype_counts, key=archetype_counts.get)
        else:
            dominant = AgentArchetype.UNKNOWN
        
        assessment = CrowdingAssessment(
            our_strategy_id="current",
            crowd_percentage=crowd_pct,
            crowd_trend=crowd_trend,
            crowd_archetypes={
                a.value: count / max(total_agents, 1)
                for a, count in archetype_counts.items()
            },
            dominant_archetype=dominant,
            estimated_crowd_next_move=self._estimate_crowd_action(
                dominant, our_strategy_signals
            ),
            confidence=min(1.0, total_agents / 20),  # More agents = more confidence
            timestamp=time.time(),
        )
        
        self.crowding_history.append(assessment)
        return assessment
    
    def _get_similar_archetypes(
        self, our_signals: Dict[str, float]
    ) -> List[AgentArchetype]:
        """
        Determine which archetypes are similar to our strategy.
        
        Our strategy uses SMC + RSI + S/R → likely overlaps with:
        - SMC_TRADER (same patterns)
        - TREND_FOLLOWER (similar entries)
        - MEAN_REVERTER (similar RSI usage)
        """
        similar = []
        
        # Check if we use momentum signals
        if our_signals.get("rsi_signal", 0) != 0:
            similar.append(AgentArchetype.MEAN_REVERTER)
            similar.append(AgentArchetype.TREND_FOLLOWER)
        
        # Check if we use SMC patterns
        if our_signals.get("smc_signal", 0) != 0:
            similar.append(AgentArchetype.SMC_TRADER)
        
        # Check if we use order flow
        if our_signals.get("order_flow_signal", 0) != 0:
            similar.append(AgentArchetype.ARBITRAGEUR)
        
        return similar
    
    def _compute_crowd_trend(self, current_crowd_pct: float) -> float:
        """Compute whether the crowd is growing or shrinking."""
        if len(self.crowding_history) < 5:
            return 0.0
        
        recent = [c.crowd_percentage for c in list(self.crowding_history)[-10:]]
        older = [c.crowd_percentage for c in list(self.crowding_history)[-20:-10]]
        
        if not older:
            return 0.0
        
        return float(np.mean(recent) - np.mean(older))
    
    def _estimate_crowd_action(
        self,
        dominant: AgentArchetype,
        our_signals: Dict[str, float]
    ) -> str:
        """Estimate what the crowd will do next."""
        # If most agents are trend followers and we're in an uptrend
        # they'll likely keep buying (until reversal)
        if dominant == AgentArchetype.TREND_FOLLOWER:
            if our_signals.get("trend_direction", 0) > 0:
                return "CONTINUE_BUYING"
            else:
                return "START_SELLING"
        
        if dominant == AgentArchetype.MEAN_REVERTER:
            if our_signals.get("rsi_signal", 50) > 70:
                return "START_SELLING"
            elif our_signals.get("rsi_signal", 50) < 30:
                return "START_BUYING"
        
        return "UNCERTAIN"


class GameTheoreticAdvisor:
    """
    Computes optimal strategy given our position and estimated opponents.
    
    Core principle: In adversarial markets, the optimal strategy depends
    on what other players are doing. This is game theory, not statistics.
    """
    
    def __init__(
        self,
        crowding_estimator: CrowdingEstimator,
        config: Dict
    ):
        self.crowding = crowding_estimator
        self.min_confidence = config.get("min_confidence", 0.5)
        self.noise_level = config.get("noise_level", 0.1)  # Randomization
    
    def advise(
        self,
        our_strategy_signals: Dict[str, float],
        our_position: Dict,
        market_state: Dict,
    ) -> GameTheoreticAdvice:
        """
        Compute game-theoretic advice given current state.
        
        This is the core intelligence: given what we know about
        our opponents, what should we do differently?
        """
        # Get crowding assessment
        crowding = self.crowding.estimate_crowding(our_strategy_signals)
        
        if crowding.confidence < self.min_confidence:
            return GameTheoreticAdvice(
                action=AdaptationAction.HOLD,
                parameters={},
                reasoning="Insufficient data on market participants",
                expected_impact=0.0,
                confidence=crowding.confidence,
                alternatives=[],
            )
        
        # Decision tree based on crowding
        if crowding.crowd_percentage > 0.7:
            # EXTREME CROWDING — our strategy is known
            if crowding.crowd_trend > 0:
                # Crowd is growing — exit before the stampede
                return self._advise_exit_crowd(crowding, our_position)
            else:
                # Crowd is shrinking — might be safe to stay
                return self._advise_reduce_and_noise(crowding, our_position)
        
        elif crowding.crowd_percentage > 0.4:
            # MODERATE CROWDING — need differentiation
            return self._advise_differentiate(crowding, our_strategy_signals)
        
        elif crowding.crowd_percentage < 0.2:
            # LOW CROWDING — we're unique, maintain edge
            return GameTheoreticAdvice(
                action=AdaptationAction.HOLD,
                parameters={"noise_level": 0.05},
                reasoning=f"Strategy uniqueness is high ({1-crowding.crowd_percentage:.0%}). Maintain current approach with minimal randomization.",
                expected_impact=0.0,
                confidence=crowding.confidence,
                alternatives=[],
            )
        
        else:
            # MODERATE — add noise to avoid fingerprinting
            return self._advise_add_noise(crowding)
    
    def _advise_exit_crowd(
        self, crowding: CrowdingAssessment, position: Dict
    ) -> GameTheoreticAdvice:
        """Advice: exit crowded positions."""
        return GameTheoreticAdvice(
            action=AdaptationAction.EXIT_CROWD,
            parameters={
                "urgency": "high",
                "exit_method": "twap",  # Time-weighted average price
                "duration_minutes": 30,
            },
            reasoning=(
                f"CROWDING ALERT: {crowding.crowd_percentage:.0%} of detected agents "
                f"appear to follow similar strategies. Crowd trend: "
                f"{'GROWING' if crowding.crowd_trend > 0 else 'SHRINKING'}. "
                f"Dominant archetype: {crowding.dominant_archetype.value}. "
                f"Recommendation: Exit before crowd unwinds."
            ),
            expected_impact=-0.02,  # Small loss from early exit
            confidence=crowding.confidence,
            alternatives=[
                {"action": "reduce_size", "params": {"factor": 0.5}},
                {"action": "tighten_stops", "params": {"atr_multiplier": 1.0}},
            ],
        )
    
    def _advise_reduce_and_noise(
        self, crowding: CrowdingAssessment, position: Dict
    ) -> GameTheoreticAdvice:
        """Advice: reduce size and add parameter noise."""
        return GameTheoreticAdvice(
            action=AdaptationAction.REDUCE_SIZE,
            parameters={
                "size_factor": 0.6,
                "noise_level": 0.15,
                "timing_offset_seconds": np.random.uniform(-30, 30),
            },
            reasoning=(
                f"High crowding ({crowding.crowd_percentage:.0%}) but crowd is "
                f"{'shrinking' if crowding.crowd_trend < 0 else 'growing'}. "
                f"Reduce exposure and add timing noise to avoid detection."
            ),
            expected_impact=-0.01,
            confidence=crowding.confidence,
            alternatives=[
                {"action": "switch_strategy", "params": {}},
                {"action": "contrarian", "params": {}},
            ],
        )
    
    def _advise_differentiate(
        self, crowding: CrowdingAssessment, signals: Dict[str, float]
    ) -> GameTheoreticAdvice:
        """Advice: differentiate from the crowd."""
        # Determine what the crowd is likely doing
        crowd_action = crowding.estimated_crowd_next_move
        
        if crowd_action in ("START_BUYING", "CONTINUE_BUYING"):
            # Crowd is buying — consider fading if we think they're wrong
            contrarian_advice = GameTheoreticAdvice(
                action=AdaptationAction.CONTRARIAN,
                parameters={
                    "direction": "sell",
                    "confidence_threshold": 0.6,
                    "size_factor": 0.3,
                },
                reasoning=(
                    f"Crowd ({crowding.crowd_percentage:.0%}) appears to be {crowd_action}. "
                    f"Consider contrarian position if fundamentals disagree."
                ),
                expected_impact=0.01,
                confidence=crowding.confidence * 0.7,  # Lower confidence for contrarian
                alternatives=[
                    {"action": "hold", "params": {}},
                    {"action": "shift_timing", "params": {"offset_minutes": 15}},
                ],
            )
            return contrarian_advice
        
        return GameTheoreticAdvice(
            action=AdaptationAction.SHIFT_TIMING,
            parameters={
                "offset_seconds": np.random.uniform(-60, 60),
                "noise_level": 0.1,
            },
            reasoning=f"Moderate crowding. Shift timing to avoid clustering with crowd.",
            expected_impact=0.0,
            confidence=crowding.confidence,
            alternatives=[],
        )
    
    def _advise_add_noise(
        self, crowding: CrowdingAssessment
    ) -> GameTheoreticAdvice:
        """Advice: add randomization to avoid fingerprinting."""
        return GameTheoreticAdvice(
            action=AdaptationAction.ADD_NOISE,
            parameters={
                "entry_noise_seconds": np.random.uniform(-20, 20),
                "size_noise_pct": np.random.uniform(-0.1, 0.1),
                "parameter_noise_pct": np.random.uniform(-0.05, 0.05),
            },
            reasoning=(
                f"Crowding at {crowding.crowd_percentage:.0%}. Adding randomization "
                f"to entry timing, position size, and strategy parameters "
                f"to avoid pattern detection by opponents."
            ),
            expected_impact=0.0,
            confidence=crowding.confidence,
            alternatives=[],
        )


class OpponentModelingSystem:
    """
    Top-level system that integrates all opponent modeling components.
    
    This is what the Trading Engine interacts with.
    """
    
    def __init__(self, config: Dict):
        self.observer = MarketMicrostructureObserver(config)
        self.crowding_estimator = CrowdingEstimator(self.observer)
        self.game_advisor = GameTheoreticAdvisor(
            self.crowding_estimator, config
        )
        self.enabled = True
    
    def on_order_book_update(self, snapshot: OrderBookSnapshot):
        """Feed order book data into the observer."""
        if self.enabled:
            self.observer.observe(snapshot)
    
    def get_adaptation_advice(
        self,
        our_signals: Dict[str, float],
        our_position: Dict,
        market_state: Dict,
    ) -> Optional[GameTheoreticAdvice]:
        """
        Get game-theoretic advice for the current situation.
        
        Call this before executing any trade decision.
        Returns None if opponent modeling is disabled or insufficient data.
        """
        if not self.enabled:
            return None
        
        return self.game_advisor.advise(
            our_signals, our_position, market_state
        )
    
    def get_crowding_report(self) -> Dict:
        """Get current crowding assessment for dashboards."""
        assessment = self.crowding_estimator.estimate_crowding({})
        return {
            "crowd_percentage": assessment.crowd_percentage,
            "crowd_trend": assessment.crowd_trend,
            "dominant_archetype": assessment.dominant_archetype.value,
            "archetype_distribution": assessment.crowd_archetypes,
            "detected_agents": len(self.observer.detected_agents),
            "confidence": assessment.confidence,
        }
    
    def get_detected_agents(self) -> List[AgentFingerprint]:
        """Get all detected market participants."""
        return list(self.observer.detected_agents.values())
```

### Integration Points

```python
# In Trading Engine:

class TradingEngine:
    def __init__(self):
        self.opponent_system = OpponentModelingSystem(config={
            "lookback_seconds": 300,
            "min_confidence": 0.5,
            "noise_level": 0.1,
        })
    
    def on_market_data(self, data):
        """Feed market data to opponent modeling."""
        snapshot = OrderBookSnapshot(
            timestamp=data["timestamp"],
            bids=data["bids"],
            asks=data["asks"],
            trade_flow=data["recent_trades"],
        )
        self.opponent_system.on_order_book_update(snapshot)
    
    def on_signal_generated(self, signals: Dict[str, float]):
        """Check game-theoretic advice before executing."""
        advice = self.opponent_system.get_adaptation_advice(
            our_signals=signals,
            our_position=self.get_current_position(),
            market_state=self.get_market_state(),
        )
        
        if advice:
            if advice.action == AdaptationAction.EXIT_CROWD:
                self.reduce_all_positions(
                    method=advice.parameters.get("exit_method", "market")
                )
            elif advice.action == AdaptationAction.REDUCE_SIZE:
                self.scale_positions(advice.parameters["size_factor"])
            elif advice.action == AdaptationAction.ADD_NOISE:
                self.inject_noise(advice.parameters)
            elif advice.action == AdaptationAction.SHIFT_TIMING:
                self.delay_execution(advice.parameters["offset_seconds"])
            elif advice.action == AdaptationAction.CONTRARIAN:
                self.consider_contrarian(advice.parameters)
```

### Acceptance Criteria

- [ ] Order book patterns analyzed for agent behavior detection
- [ ] Agent archetypes classified (trend follower, mean reverter, SMC trader, etc.)
- [ ] Crowding percentage computed per strategy
- [ ] Crowd trend tracked (growing vs shrinking)
- [ ] Game-theoretic advice generated before trade execution
- [ ] Parameter noise injection to avoid fingerprinting
- [ ] Timing offset applied to avoid clustering with crowd
- [ ] Contrarian signals considered when crowd is detected
- [ ] Exit triggers when crowding exceeds threshold (70%)
- [ ] Dashboard reports on detected agents and crowding levels

---

## Integration Summary

All 4 fixes integrate into the existing architecture as **additive layers** — no existing code needs to be rewritten.

```
┌─────────────────────────────────────────────────────────────────┐
│                    TRADING ENGINE (existing)                      │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  FIX 3: Capability Registry                                │   │
│  │  (replaces hardcoded model-to-step mapping)                │   │
│  │  registry.predict(Capability.X, inputs)                    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  FIX 1: Alpha Decay Tracker                                │   │
│  │  (detects strategy crowding, triggers rotation)            │   │
│  │  tracker.evaluate(strategy_id) → AlphaDecaySignal          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  FIX 2: Adversarial Robustness Layer                       │   │
│  │  (protects Reflection Agent from poisoning)                │   │
│  │  protected_reflection.on_trade_closed(outcome)             │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  FIX 4: Opponent Modeling System                           │   │
│  │  (game-theoretic advice before trade execution)            │   │
│  │  opponent.get_adaptation_advice(signals, position, state)  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Implementation Priority

| Order | Fix | Why First |
|-------|-----|-----------|
| 1 | FIX 3: Model Capability Abstraction | Foundation — all other fixes benefit from swappable models |
| 2 | FIX 1: Alpha Decay Tracker | Quick win — immediate visibility into strategy crowding |
| 3 | FIX 2: Adversarial Robustness | Security — protects the learning loop before it's exploited |
| 4 | FIX 4: Opponent Modeling | Most complex — but most critical for AGI-era markets |

## Estimated Total Effort

| Fix | Effort | Team |
|-----|--------|------|
| FIX 1 | 2-3 weeks | 1 ML engineer |
| FIX 2 | 2 weeks | 1 ML security engineer |
| FIX 3 | 3-4 weeks | 1 platform engineer |
| FIX 4 | 4-6 weeks | 1 quant + 1 ML engineer |
| **Total** | **11-15 weeks** | **3-4 engineers** |

---

*Fix plan completed: 2026-07-11*
*Based on: AGI Readiness Review (review_agi_readiness.md)*
*Next: Architecture review → Sprint planning → Implementation*
