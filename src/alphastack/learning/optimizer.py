"""Strategy Optimizer — Bayesian optimization, A/B testing, and parameter tracking.

The self-improving core of AlphaStack's learning loop.

Components:
1. BayesianOptimizer     — GP-based optimization of strategy parameters
2. ABTest                — A/B test different signal weight configurations
3. ParameterPerformanceTracker — Track how each parameter set performs over time
4. StrategyOptimizer     — Orchestrates all optimization components

Design decisions:
- Pure Python implementation (no scipy dependency) using simple GP approximation
- Bounded parameter spaces with configurable min/max
- Thompson Sampling for A/B test allocation (explore/exploit)
- Exponential decay for recency weighting of performance data
"""

from __future__ import annotations

import math
import random
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

from alphastack.utils.logger import get_logger

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Parameter space definition
# ──────────────────────────────────────────────────────────────────────


@dataclass
class ParameterSpec:
    """Specification for a single optimizable parameter."""
    name: str
    min_value: float
    max_value: float
    step: float = 0.01  # minimum increment
    is_integer: bool = False
    default: float = 0.0

    def clip(self, value: float) -> float:
        """Clip value to valid range."""
        value = max(self.min_value, min(self.max_value, value))
        if self.is_integer:
            return round(value)
        # Snap to step grid
        steps = round((value - self.min_value) / self.step)
        return self.min_value + steps * self.step

    def random_sample(self) -> float:
        """Generate a random value within the parameter range."""
        value = random.uniform(self.min_value, self.max_value)
        return self.clip(value)


# ──────────────────────────────────────────────────────────────────────
# Observation record
# ──────────────────────────────────────────────────────────────────────


@dataclass
class Observation:
    """A single parameter configuration observation with its outcome."""
    obs_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    params: dict[str, float] = field(default_factory=dict)
    objective_value: float = 0.0  # e.g. Sharpe ratio, total PnL, win rate
    metrics: dict[str, float] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    regime: str = ""
    sample_count: int = 0  # number of trades in this observation

    def to_dict(self) -> dict[str, Any]:
        return {
            "obs_id": self.obs_id,
            "params": self.params,
            "objective_value": round(self.objective_value, 6),
            "metrics": {k: round(v, 6) for k, v in self.metrics.items()},
            "timestamp": self.timestamp,
            "regime": self.regime,
            "sample_count": self.sample_count,
        }


# ──────────────────────────────────────────────────────────────────────
# Simple Gaussian Process approximation (pure Python)
# ──────────────────────────────────────────────────────────────────────


class SimpleGP:
    """Lightweight Gaussian Process regression using RBF kernel.

    Pure Python — no numpy/scipy required.  Suitable for small datasets
    (< 500 observations) typical in strategy optimization.

    Uses the RBF kernel: k(x, x') = σ² * exp(-|x - x'|² / (2 * ℓ²))
    """

    def __init__(
        self,
        length_scale: float = 1.0,
        signal_variance: float = 1.0,
        noise_variance: float = 0.1,
    ) -> None:
        self.length_scale = length_scale
        self.signal_variance = signal_variance
        self.noise_variance = noise_variance
        self._X: list[list[float]] = []
        self._y: list[float] = []
        self._K_inv_y: list[float] = []  # cached (K + σI)^{-1} y

    def fit(self, X: list[list[float]], y: list[float]) -> None:
        """Fit the GP to training data."""
        self._X = [list(x) for x in X]
        self._y = list(y)
        n = len(X)
        if n == 0:
            self._K_inv_y = []
            return

        # Build kernel matrix K + σ²I
        K = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                K[i][j] = self._kernel(X[i], X[j])
                if i == j:
                    K[i][j] += self.noise_variance

        # Solve (K + σI)α = y via Cholesky decomposition
        try:
            L = self._cholesky(K)
            alpha = self._cholesky_solve(L, y)
            self._K_inv_y = alpha
        except (ValueError, ZeroDivisionError):
            # Fallback: use diagonal approximation
            self._K_inv_y = [y[i] / (K[i][i] + 1e-6) for i in range(n)]

    def predict(self, x: list[float]) -> tuple[float, float]:
        """Predict mean and variance at a point.

        Returns (mean, variance).
        """
        n = len(self._X)
        if n == 0:
            return 0.0, self.signal_variance

        # k_star = kernel between x and training points
        k_star = [self._kernel(x, xi) for xi in self._X]

        # Mean: k_star^T * alpha
        mean = sum(k * a for k, a in zip(k_star, self._K_inv_y))

        # Variance: k(x,x) - k_star^T * (K + σI)^{-1} * k_star
        # Simplified: approximate with k(x,x) - sum of squared k_star weights
        k_xx = self._kernel(x, x)
        variance_reduction = sum(k * a for k, a in zip(k_star, self._K_inv_y))
        variance = max(0.01, k_xx - abs(variance_reduction) * 0.1)

        return mean, variance

    def _kernel(self, x1: list[float], x2: list[float]) -> float:
        """RBF kernel."""
        dist_sq = sum((a - b) ** 2 for a, b in zip(x1, x2))
        return self.signal_variance * math.exp(-dist_sq / (2 * self.length_scale ** 2))

    @staticmethod
    def _cholesky(A: list[list[float]]) -> list[list[float]]:
        """Cholesky decomposition A = L * L^T."""
        n = len(A)
        L = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(i + 1):
                s = sum(L[i][k] * L[j][k] for k in range(j))
                if i == j:
                    val = A[i][i] - s
                    if val <= 0:
                        val = 1e-10
                    L[i][j] = math.sqrt(val)
                else:
                    L[i][j] = (A[i][j] - s) / L[j][j] if L[j][j] != 0 else 0
        return L

    @staticmethod
    def _cholesky_solve(L: list[list[float]], b: list[float]) -> list[float]:
        """Solve L * L^T * x = b via forward/backward substitution."""
        n = len(L)
        # Forward: L * y = b
        y = [0.0] * n
        for i in range(n):
            s = sum(L[i][k] * y[k] for k in range(i))
            y[i] = (b[i] - s) / L[i][i] if L[i][i] != 0 else 0

        # Backward: L^T * x = y
        x = [0.0] * n
        for i in range(n - 1, -1, -1):
            s = sum(L[k][i] * x[k] for k in range(i + 1, n))
            x[i] = (y[i] - s) / L[i][i] if L[i][i] != 0 else 0
        return x


# ──────────────────────────────────────────────────────────────────────
# Bayesian Optimizer
# # ──────────────────────────────────────────────────────────────────────


class BayesianOptimizer:
    """Bayesian optimization using Gaussian Process surrogate.

    Uses Thompson Sampling for acquisition: sample from the GP posterior
    and pick the point that maximizes the sample.

    This is a pure-Python implementation suitable for optimizing 2-10
    strategy parameters with 10-200 observations.
    """

    def __init__(
        self,
        parameter_specs: list[ParameterSpec],
        objective: str = "sharpe_ratio",
        n_candidates: int = 100,
        exploration_weight: float = 0.3,
    ) -> None:
        self.specs = {s.name: s for s in parameter_specs}
        self.spec_list = parameter_specs
        self.objective = objective
        self.n_candidates = n_candidates
        self.exploration_weight = exploration_weight
        self._observations: list[Observation] = []
        self._gp = SimpleGP(
            length_scale=max(1.0, len(parameter_specs) * 0.5),
            signal_variance=1.0,
            noise_variance=0.1,
        )
        self._best_params: dict[str, float] = {}
        self._best_objective: float = float("-inf")

    def suggest(self) -> dict[str, float]:
        """Suggest the next parameter configuration to try.

        Uses Thompson Sampling: fit GP, sample from posterior,
        pick the candidate that maximizes the sample.

        Returns
        -------
        dict[str, float]
            Suggested parameter values.
        """
        if len(self._observations) < 3:
            # Random exploration for first few observations
            return self._random_params()

        # Fit GP to observations
        X = [self._params_to_vector(o.params) for o in self._observations]
        y = [o.objective_value for o in self._observations]
        self._gp.fit(X, y)

        # Generate candidates and score them
        best_candidate = None
        best_score = float("-inf")

        for _ in range(self.n_candidates):
            # Random candidate
            candidate = self._random_params()
            x_candidate = self._params_to_vector(candidate)

            # Thompson sample: mean + exploration_weight * sqrt(variance) * z
            mean, variance = self._gp.predict(x_candidate)
            std = math.sqrt(max(0, variance))
            sample = mean + self.exploration_weight * std * random.gauss(0, 1)

            if sample > best_score:
                best_score = sample
                best_candidate = candidate

        # Also try the current best with some noise (exploitation)
        if self._best_params:
            noisy_best = {}
            for name, value in self._best_params.items():
                spec = self.specs[name]
                noise = random.gauss(0, spec.step * 2)
                noisy_best[name] = spec.clip(value + noise)
            x_noisy = self._params_to_vector(noisy_best)
            mean, _ = self._gp.predict(x_noisy)
            if mean > best_score:
                best_candidate = noisy_best

        return best_candidate or self._random_params()

    def record(
        self,
        params: dict[str, float],
        objective_value: float,
        metrics: dict[str, float] | None = None,
        regime: str = "",
        sample_count: int = 0,
    ) -> None:
        """Record an observation (parameter config + outcome).

        Parameters
        ----------
        params : dict[str, float]
            The parameter configuration that was tested.
        objective_value : float
            The objective value achieved (e.g. Sharpe, PnL).
        metrics : dict[str, float] | None
            Additional metrics (win_rate, profit_factor, etc.).
        regime : str
            Market regime during this observation.
        sample_count : int
            Number of trades in this observation.
        """
        obs = Observation(
            params=dict(params),
            objective_value=objective_value,
            metrics=metrics or {},
            regime=regime,
            sample_count=sample_count,
        )
        self._observations.append(obs)

        # Track best
        if objective_value > self._best_objective:
            self._best_objective = objective_value
            self._best_params = dict(params)

        logger.info(
            "bayesian_optimizer.recorded",
            objective=objective_value,
            best_so_far=self._best_objective,
            n_observations=len(self._observations),
        )

    @property
    def best_params(self) -> dict[str, float]:
        """Return the best parameter configuration found so far."""
        return dict(self._best_params)

    @property
    def best_objective(self) -> float:
        return self._best_objective

    def get_history(self) -> list[dict[str, Any]]:
        """Return observation history."""
        return [o.to_dict() for o in self._observations]

    def get_convergence_data(self) -> list[float]:
        """Return running best objective over time (for plotting)."""
        running_best = float("-inf")
        convergence = []
        for obs in self._observations:
            running_best = max(running_best, obs.objective_value)
            convergence.append(running_best)
        return convergence

    def _random_params(self) -> dict[str, float]:
        """Generate random parameter configuration."""
        return {spec.name: spec.random_sample() for spec in self.spec_list}

    def _params_to_vector(self, params: dict[str, float]) -> list[float]:
        """Convert params dict to normalized vector for GP."""
        vector = []
        for spec in self.spec_list:
            value = params.get(spec.name, spec.default)
            # Normalize to [0, 1]
            range_size = spec.max_value - spec.min_value
            if range_size > 0:
                normalized = (value - spec.min_value) / range_size
            else:
                normalized = 0.5
            vector.append(normalized)
        return vector


# ──────────────────────────────────────────────────────────────────────
# A/B Test
# ──────────────────────────────────────────────────────────────────────


@dataclass
class ABVariant:
    """A single variant in an A/B test."""
    variant_id: str = ""
    name: str = ""
    params: dict[str, float] = field(default_factory=dict)
    # Running statistics
    trade_count: int = 0
    total_pnl: float = 0.0
    win_count: int = 0
    total_reward: float = 0.0  # for Thompson sampling

    @property
    def win_rate(self) -> float:
        return self.win_count / self.trade_count if self.trade_count > 0 else 0.0

    @property
    def avg_pnl(self) -> float:
        return self.total_pnl / self.trade_count if self.trade_count > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "name": self.name,
            "params": self.params,
            "trade_count": self.trade_count,
            "win_rate": round(self.win_rate, 4),
            "avg_pnl": round(self.avg_pnl, 6),
            "total_pnl": round(self.total_pnl, 6),
        }


@dataclass
class ABTestResult:
    """Result of an A/B test analysis."""
    test_id: str = ""
    winner: str = ""  # variant_id of the winner
    confidence: float = 0.0  # statistical confidence in winner
    variants: list[dict[str, Any]] = field(default_factory=list)
    is_significant: bool = False
    recommendation: str = ""
    trades_per_variant: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_id": self.test_id,
            "winner": self.winner,
            "confidence": round(self.confidence, 4),
            "is_significant": self.is_significant,
            "recommendation": self.recommendation,
            "trades_per_variant": self.trades_per_variant,
            "variants": self.variants,
        }


class ABTest:
    """A/B test for comparing signal weight configurations.

    Uses Thompson Sampling (Beta-Bernoulli) for adaptive allocation:
    variants that perform well get more traffic automatically.

    This lets us test whether "RSI weight=0.3, MACD weight=0.4" beats
    "RSI weight=0.5, MACD weight=0.2" in live trading.
    """

    def __init__(
        self,
        test_id: str = "",
        min_samples: int = 20,
        significance_threshold: float = 0.90,
    ) -> None:
        self.test_id = test_id or uuid.uuid4().hex[:12]
        self.min_samples = min_samples
        self.significance_threshold = significance_threshold
        self._variants: dict[str, ABVariant] = {}
        self._alpha: dict[str, float] = {}  # Beta distribution alpha (successes)
        self._beta: dict[str, float] = {}   # Beta distribution beta (failures)

    def add_variant(self, name: str, params: dict[str, float]) -> str:
        """Add a variant to the A/B test.

        Returns the variant_id.
        """
        variant_id = f"v{len(self._variants)}"
        variant = ABVariant(
            variant_id=variant_id,
            name=name,
            params=dict(params),
        )
        self._variants[variant_id] = variant
        # Initialize Beta(1, 1) = Uniform prior
        self._alpha[variant_id] = 1.0
        self._beta[variant_id] = 1.0
        return variant_id

    def select_variant(self) -> str:
        """Select which variant to use for the next trade.

        Uses Thompson Sampling: sample from each variant's Beta
        distribution and pick the highest.

        Returns
        -------
        str
            variant_id of the selected variant.
        """
        if not self._variants:
            return ""

        best_id = ""
        best_sample = float("-inf")

        for vid in self._variants:
            # Sample from Beta(alpha, beta)
            sample = random.betavariate(self._alpha[vid], self._beta[vid])
            if sample > best_sample:
                best_sample = sample
                best_id = vid

        return best_id

    def record_outcome(self, variant_id: str, pnl: float) -> None:
        """Record a trade outcome for a variant.

        Parameters
        ----------
        variant_id : str
            Which variant was used.
        pnl : float
            Trade P&L (positive = win, negative = loss).
        """
        if variant_id not in self._variants:
            return

        variant = self._variants[variant_id]
        variant.trade_count += 1
        variant.total_pnl += pnl

        if pnl > 0:
            variant.win_count += 1
            self._alpha[variant_id] += 1.0  # Success
        else:
            self._beta[variant_id] += 1.0  # Failure

    def get_result(self) -> ABTestResult:
        """Analyze the A/B test and determine if there's a winner.

        Uses the Beta distributions to compute the probability that
        each variant is the best.
        """
        result = ABTestResult(test_id=self.test_id)

        if not self._variants:
            result.recommendation = "No variants configured"
            return result

        # Compute P(variant is best) via Monte Carlo
        n_samples = 10000
        win_counts: dict[str, int] = {vid: 0 for vid in self._variants}

        for _ in range(n_samples):
            best_vid = ""
            best_val = float("-inf")
            for vid in self._variants:
                val = random.betavariate(self._alpha[vid], self._beta[vid])
                if val > best_val:
                    best_val = val
                    best_vid = vid
            if best_vid:
                win_counts[best_vid] += 1

        # Find winner
        total_trades = sum(v.trade_count for v in self._variants.values())
        max_prob = 0.0
        winner_id = ""

        variants_data = []
        for vid, variant in self._variants.items():
            prob_best = win_counts[vid] / n_samples
            variants_data.append({
                **variant.to_dict(),
                "prob_best": round(prob_best, 4),
            })
            if prob_best > max_prob:
                max_prob = prob_best
                winner_id = vid

        result.variants = variants_data
        result.winner = winner_id
        result.confidence = max_prob
        result.is_significant = max_prob >= self.significance_threshold
        result.trades_per_variant = total_trades // len(self._variants) if self._variants else 0

        if result.is_significant:
            winner = self._variants[winner_id]
            result.recommendation = (
                f"Variant '{winner.name}' is the winner with {max_prob:.1%} confidence. "
                f"Win rate: {winner.win_rate:.1%}, Avg PnL: {winner.avg_pnl:.4f}"
            )
        else:
            result.recommendation = (
                f"Not yet significant (best confidence: {max_prob:.1%}, "
                f"need {self.significance_threshold:.0%}). Continue testing."
            )

        return result

    def get_variants(self) -> list[dict[str, Any]]:
        """Return all variant data."""
        return [v.to_dict() for v in self._variants.values()]


# ──────────────────────────────────────────────────────────────────────
# Parameter Performance Tracker
# ──────────────────────────────────────────────────────────────────────


class ParameterPerformanceTracker:
    """Tracks how each parameter configuration performs over time.

    Maintains a time-series of (params → outcome) so we can:
    - See which parameters are currently best
    - Detect parameter regime-dependence (different best params per regime)
    - Track parameter drift (are we over-fitting to recent data?)
    """

    def __init__(self, decay_halflife: float = 50.0) -> None:
        self._decay_halflife = decay_halflife
        # regime -> list of (timestamp, params, outcome)
        self._history: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._global_history: list[dict[str, Any]] = []

    def record(
        self,
        params: dict[str, float],
        outcome: float,
        regime: str = "unknown",
        metrics: dict[str, float] | None = None,
    ) -> None:
        """Record a parameter configuration and its outcome."""
        entry = {
            "timestamp": time.time(),
            "params": dict(params),
            "outcome": outcome,
            "metrics": metrics or {},
        }
        self._history[regime].append(entry)
        self._global_history.append({**entry, "regime": regime})

        # Keep bounded
        if len(self._global_history) > 2000:
            self._global_history = self._global_history[-1000:]
        for regime_key in self._history:
            if len(self._history[regime_key]) > 500:
                self._history[regime_key] = self._history[regime_key][-250:]

    def get_best_params(
        self,
        regime: str | None = None,
        top_k: int = 1,
    ) -> list[dict[str, Any]]:
        """Return the best-performing parameter configurations.

        Parameters
        ----------
        regime : str | None
            If specified, only consider trades from this regime.
        top_k : int
            Number of top configurations to return.

        Returns
        -------
        list[dict]
            Top configurations with their performance metrics.
        """
        history = self._history.get(regime, self._global_history) if regime else self._global_history
        if not history:
            return []

        # Group by parameter configuration (discretized)
        config_outcomes: dict[str, list[float]] = defaultdict(list)
        config_params: dict[str, dict[str, float]] = {}

        for entry in history:
            key = self._params_key(entry["params"])
            config_outcomes[key].append(entry["outcome"])
            config_params[key] = entry["params"]

        # Score each configuration (recency-weighted average)
        configs = []
        for key, outcomes in config_outcomes.items():
            # Simple average (could use recency weighting)
            avg_outcome = sum(outcomes) / len(outcomes)
            configs.append({
                "params": config_params[key],
                "avg_outcome": round(avg_outcome, 6),
                "sample_count": len(outcomes),
                "std": round(self._std(outcomes), 6) if len(outcomes) > 1 else 0,
            })

        configs.sort(key=lambda c: c["avg_outcome"], reverse=True)
        return configs[:top_k]

    def get_regime_analysis(self) -> dict[str, dict[str, Any]]:
        """Analyze which parameters work best in each regime.

        Returns
        -------
        dict
            Regime → {best_params, avg_outcome, sample_count}
        """
        analysis = {}
        for regime, history in self._history.items():
            if len(history) < 5:
                continue
            best = self.get_best_params(regime=regime, top_k=1)
            if best:
                analysis[regime] = {
                    "best_params": best[0]["params"],
                    "avg_outcome": best[0]["avg_outcome"],
                    "sample_count": best[0]["sample_count"],
                    "total_trades": len(history),
                }
        return analysis

    def detect_drift(self, window: int = 30) -> dict[str, Any]:
        """Detect if optimal parameters are drifting over time.

        Compares recent best params vs historical best params.
        """
        if len(self._global_history) < window * 2:
            return {"drift_detected": False, "reason": "Insufficient data"}

        recent = self._global_history[-window:]
        historical = self._global_history[:-window]

        # Get best params for each period
        recent_best = self._best_from_entries(recent)
        hist_best = self._best_from_entries(historical)

        if not recent_best or not hist_best:
            return {"drift_detected": False, "reason": "Insufficient data"}

        # Compute param distance
        distance = self._param_distance(recent_best, hist_best)

        drift_detected = distance > 0.3  # threshold
        return {
            "drift_detected": drift_detected,
            "param_distance": round(distance, 4),
            "recent_best": recent_best,
            "historical_best": hist_best,
            "recent_avg_outcome": round(
                sum(e["outcome"] for e in recent) / len(recent), 6
            ),
            "historical_avg_outcome": round(
                sum(e["outcome"] for e in historical) / len(historical), 6
            ),
        }

    @staticmethod
    def _params_key(params: dict[str, float]) -> str:
        """Create a deterministic key from parameter values."""
        return "|".join(f"{k}={v:.4f}" for k, v in sorted(params.items()))

    @staticmethod
    def _std(values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
        return math.sqrt(variance)

    @staticmethod
    def _best_from_entries(entries: list[dict[str, Any]]) -> dict[str, float] | None:
        if not entries:
            return None
        best = max(entries, key=lambda e: e["outcome"])
        return best["params"]

    @staticmethod
    def _param_distance(p1: dict[str, float], p2: dict[str, float]) -> float:
        """Euclidean distance between two param configs (normalized)."""
        common = set(p1.keys()) & set(p2.keys())
        if not common:
            return 0.0
        dist_sq = sum((p1[k] - p2[k]) ** 2 for k in common)
        return math.sqrt(dist_sq / len(common))


# ──────────────────────────────────────────────────────────────────────
# Strategy Optimizer (orchestrator)
# ──────────────────────────────────────────────────────────────────────


class StrategyOptimizer:
    """Orchestrates all optimization components.

    The main entry point for the self-improving loop. Combines:
    - Bayesian optimization for parameter tuning
    - A/B testing for signal weight comparison
    - Parameter performance tracking for regime-dependent tuning
    - Adaptation signal generation

    Usage
    -----
    ```python
    optimizer = StrategyOptimizer(parameter_specs=[...])

    # Get next params to try
    params = optimizer.suggest()

    # After trades with those params
    optimizer.record(params, pnl=0.5, regime="trending_up")

    # Check if we should adapt
    signals = optimizer.get_adaptation_signals()
    ```
    """

    def __init__(
        self,
        parameter_specs: list[ParameterSpec] | None = None,
        objective: str = "sharpe_ratio",
    ) -> None:
        self.specs = parameter_specs or self._default_specs()
        self.objective = objective

        self._bayesian = BayesianOptimizer(
            parameter_specs=self.specs,
            objective=objective,
            n_candidates=100,
        )
        self._param_tracker = ParameterPerformanceTracker()
        self._active_ab_tests: dict[str, ABTest] = {}
        self._completed_ab_tests: list[ABTestResult] = []

        # Trade buffer for computing objective
        self._recent_outcomes: deque[float] = deque(maxlen=100)
        self._recent_params: deque[dict[str, float]] = deque(maxlen=100)

    def suggest(self, regime: str = "") -> dict[str, float]:
        """Suggest the next parameter configuration to try.

        If we have regime-specific data, uses that. Otherwise falls
        back to Bayesian optimization.

        Parameters
        ----------
        regime : str
            Current market regime.

        Returns
        -------
        dict[str, float]
            Suggested parameter values.
        """
        # Check regime-specific best params
        if regime:
            regime_analysis = self._param_tracker.get_regime_analysis()
            if regime in regime_analysis:
                best = regime_analysis[regime]
                # Use regime best with some noise for exploration
                params = {}
                for name, value in best["best_params"].items():
                    spec = self.specs[name] if name in self.specs else None
                    if spec:
                        noise = random.gauss(0, spec.step * 3)
                        params[name] = spec.clip(value + noise)
                    else:
                        params[name] = value
                return params

        # Fall back to Bayesian optimization
        return self._bayesian.suggest()

    def record(
        self,
        params: dict[str, float],
        pnl: float = 0.0,
        regime: str = "unknown",
        metrics: dict[str, float] | None = None,
    ) -> None:
        """Record a trade outcome for the given parameters.

        Computes the objective value from recent trades and feeds
        it to both the Bayesian optimizer and parameter tracker.
        """
        self._recent_outcomes.append(pnl)
        self._recent_params.append(dict(params))

        # Track in parameter tracker
        self._param_tracker.record(
            params=params,
            outcome=pnl,
            regime=regime,
            metrics=metrics,
        )

        # Update active A/B tests
        for test in self._active_ab_tests.values():
            # Find which variant matches these params (closest)
            variant_id = self._find_matching_variant(test, params)
            if variant_id:
                test.record_outcome(variant_id, pnl)

        # Periodically feed to Bayesian optimizer (every 10 trades)
        if len(self._recent_outcomes) % 10 == 0 and len(self._recent_outcomes) >= 10:
            objective = self._compute_objective()
            self._bayesian.record(
                params=params,
                objective_value=objective,
                metrics=metrics,
                regime=regime,
                sample_count=10,
            )

    def create_ab_test(
        self,
        name: str,
        variants: list[dict[str, Any]],
    ) -> str:
        """Create a new A/B test for signal weight configurations.

        Parameters
        ----------
        name : str
            Test name.
        variants : list[dict]
            Each dict must have 'name' and 'params' keys.

        Returns
        -------
        str
            Test ID.
        """
        test = ABTest(min_samples=20, significance_threshold=0.90)
        for v in variants:
            test.add_variant(v["name"], v["params"])

        test_id = test.test_id
        self._active_ab_tests[test_id] = test
        return test_id

    def get_ab_test_result(self, test_id: str) -> ABTestResult | None:
        """Get the result of an A/B test."""
        test = self._active_ab_tests.get(test_id)
        if test:
            return test.get_result()
        return None

    def get_adaptation_signals(self) -> list[dict[str, Any]]:
        """Generate adaptation signals from all optimization data.

        Returns a list of actionable recommendations.
        """
        signals: list[dict[str, Any]] = []

        # 1. Check parameter drift
        drift = self._param_tracker.detect_drift()
        if drift.get("drift_detected"):
            signals.append({
                "type": "parameter_drift",
                "severity": "medium",
                "message": (
                    f"Parameter drift detected (distance={drift['param_distance']:.3f}). "
                    f"Recent best differs from historical best."
                ),
                "recent_best": drift.get("recent_best"),
                "historical_best": drift.get("historical_best"),
            })

        # 2. Check regime-specific recommendations
        regime_analysis = self._param_tracker.get_regime_analysis()
        for regime, analysis in regime_analysis.items():
            if analysis["sample_count"] >= 10:
                signals.append({
                    "type": "regime_optimization",
                    "severity": "low",
                    "message": (
                        f"Regime '{regime}': best params achieve "
                        f"{analysis['avg_outcome']:.4f} avg outcome "
                        f"({analysis['total_trades']} trades)"
                    ),
                    "regime": regime,
                    "best_params": analysis["best_params"],
                })

        # 3. Check A/B test results
        for test_id, test in self._active_ab_tests.items():
            result = test.get_result()
            if result.is_significant:
                signals.append({
                    "type": "ab_test_winner",
                    "severity": "high",
                    "message": result.recommendation,
                    "test_id": test_id,
                    "winner": result.winner,
                    "confidence": result.confidence,
                })

        # 4. Bayesian optimization convergence
        if len(self._bayesian._observations) >= 10:
            convergence = self._bayesian.get_convergence_data()
            if len(convergence) >= 10:
                recent_improvement = convergence[-1] - convergence[-5] if len(convergence) >= 5 else 0
                if recent_improvement < 0.001:
                    signals.append({
                        "type": "optimization_converged",
                        "severity": "info",
                        "message": (
                            f"Bayesian optimization converged. Best objective: "
                            f"{self._bayesian.best_objective:.4f}"
                        ),
                        "best_params": self._bayesian.best_params,
                    })

        return signals

    def get_summary(self) -> dict[str, Any]:
        """Return a complete optimization summary."""
        return {
            "bayesian": {
                "observations": len(self._bayesian._observations),
                "best_objective": self._bayesian.best_objective,
                "best_params": self._bayesian.best_params,
                "convergence": self._bayesian.get_convergence_data()[-10:],
            },
            "active_ab_tests": {
                tid: test.get_result().to_dict()
                for tid, test in self._active_ab_tests.items()
            },
            "regime_analysis": self._param_tracker.get_regime_analysis(),
            "drift_detection": self._param_tracker.detect_drift(),
            "adaptation_signals": self.get_adaptation_signals(),
        }

    # -- internals --

    def _compute_objective(self) -> float:
        """Compute objective value from recent outcomes."""
        if not self._recent_outcomes:
            return 0.0

        outcomes = list(self._recent_outcomes)

        if self.objective == "sharpe_ratio":
            if len(outcomes) < 2:
                return 0.0
            mean = sum(outcomes) / len(outcomes)
            variance = sum((o - mean) ** 2 for o in outcomes) / (len(outcomes) - 1)
            std = math.sqrt(variance) if variance > 0 else 1e-10
            return mean / std
        elif self.objective == "total_pnl":
            return sum(outcomes)
        elif self.objective == "win_rate":
            wins = sum(1 for o in outcomes if o > 0)
            return wins / len(outcomes)
        elif self.objective == "expectancy":
            wins = [o for o in outcomes if o > 0]
            losses = [o for o in outcomes if o < 0]
            wr = len(wins) / len(outcomes) if outcomes else 0
            avg_win = sum(wins) / len(wins) if wins else 0
            avg_loss = abs(sum(losses) / len(losses)) if losses else 0
            return (wr * avg_win) - ((1 - wr) * avg_loss)
        else:
            return sum(outcomes)

    @staticmethod
    def _find_matching_variant(test: ABTest, params: dict[str, float]) -> str | None:
        """Find the variant whose params are closest to the given params."""
        best_id = None
        best_dist = float("inf")

        for vid, variant in test._variants.items():
            dist = 0.0
            count = 0
            for k, v in params.items():
                if k in variant.params:
                    dist += (v - variant.params[k]) ** 2
                    count += 1
            if count > 0:
                dist = math.sqrt(dist / count)
                if dist < best_dist:
                    best_dist = dist
                    best_id = vid

        return best_id

    @staticmethod
    def _default_specs() -> list[ParameterSpec]:
        """Default parameter specifications for strategy optimization."""
        return [
            ParameterSpec("min_confluence_score", 0.1, 0.9, step=0.05, default=0.3),
            ParameterSpec("position_size_pct", 0.001, 0.1, step=0.005, default=0.02),
            ParameterSpec("stop_loss_atr_mult", 0.5, 5.0, step=0.1, default=2.0),
            ParameterSpec("take_profit_atr_mult", 1.0, 8.0, step=0.2, default=3.0),
            ParameterSpec("rsi_weight", 0.0, 1.0, step=0.1, default=0.3),
            ParameterSpec("macd_weight", 0.0, 1.0, step=0.1, default=0.3),
            ParameterSpec("volume_weight", 0.0, 1.0, step=0.1, default=0.2),
            ParameterSpec("momentum_weight", 0.0, 1.0, step=0.1, default=0.2),
        ]
