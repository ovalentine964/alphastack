"""Learning loop for continuous model and strategy improvement in AlphaStack.

Core concept: Continuous feedback-driven adaptation where the system
learns from every trade outcome and market observation.

Tracks:
- Feature importance shifts (what signals matter NOW)
- Strategy performance decay (alpha erosion detection)
- Model confidence calibration (are we overconfident?)
- Parameter adaptation (auto-tuning based on regime changes)
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


class AdaptationType(Enum):
    """Types of adaptation signals."""

    PARAMETER_UPDATE = "parameter_update"  # Tune a specific parameter
    FEATURE_REWEIGHT = "feature_reweight"  # Change feature importance
    STRATEGY_ROTATE = "strategy_rotate"  # Switch active strategy
    MODEL_RECALIBRATE = "model_recalibrate"  # Recalibrate confidence
    REGIME_SHIFT = "regime_shift"  # Market regime changed
    ALPHA_DECAY = "alpha_decay"  # Strategy alpha is decaying


class RegimeType(Enum):
    """Market regime classification."""

    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGE_BOUND = "range_bound"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    CRISIS = "crisis"
    RECOVERY = "recovery"


@dataclass
class AdaptationSignal:
    """A signal suggesting how the system should adapt.

    Attributes
    ----------
    adaptation_type : AdaptationType
        Type of adaptation needed.
    target : str
        What to adapt (e.g., "stop_loss_pct", "rsi_period", "strategy_name").
    current_value : Any
        Current value of the parameter/feature.
    recommended_value : Any
        Recommended new value.
    confidence : float
        How confident we are in this recommendation (0-1).
    reason : str
        Why this adaptation is recommended.
    urgency : int
        1 (low) to 5 (critical).
    """

    adaptation_type: AdaptationType
    target: str
    current_value: Any
    recommended_value: Any
    confidence: float
    reason: str
    urgency: int = 3


@dataclass
class TradeOutcome:
    """Record of a completed trade for learning."""

    trade_id: str
    symbol: str
    strategy: str
    features_used: dict[str, float]
    predicted_confidence: float
    actual_outcome: float  # P&L
    regime: RegimeType
    timestamp: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class FeatureImportance:
    """Tracking feature importance over time."""

    feature_name: str
    current_weight: float
    rolling_correlation: float = 0.0
    predictive_power: float = 0.0  # How well this feature predicted outcomes
    decay_rate: float = 0.0  # How fast this feature's predictive power is declining
    last_updated: float = 0.0


@dataclass
class LearningState:
    """Current state of the learning system."""

    trade_history: deque[TradeOutcome] = field(default_factory=lambda: deque(maxlen=1000))
    feature_importances: dict[str, FeatureImportance] = field(default_factory=dict)
    current_regime: RegimeType = RegimeType.RANGE_BOUND
    regime_confidence: float = 0.5
    calibration_error: float = 0.0  # How well-calibrated are predictions
    adaptation_history: list[AdaptationSignal] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Learning Loop
# ---------------------------------------------------------------------------


class LearningLoop:
    """Continuous learning loop for strategy adaptation.

    Monitors trade outcomes, tracks feature importance, detects regime
    shifts, and generates adaptation signals.

    Usage
    -----
    ```python
    loop = LearningLoop(window_size=100)

    # After each trade
    loop.record_trade(trade_outcome)

    # Periodically check for adaptation signals
    signals = loop.analyze()
    for signal in signals:
        apply_adaptation(signal)
    ```
    """

    def __init__(
        self,
        window_size: int = 100,
        alpha_decay_threshold: float = 0.3,
        calibration_threshold: float = 0.15,
        regime_lookback: int = 50,
    ) -> None:
        self.state = LearningState()
        self.window_size = window_size
        self.alpha_decay_threshold = alpha_decay_threshold
        self.calibration_threshold = calibration_threshold
        self.regime_lookback = regime_lookback

    def record_trade(self, outcome: TradeOutcome) -> None:
        """Record a completed trade for learning.

        Parameters
        ----------
        outcome : TradeOutcome
            The completed trade with actual results.
        """
        outcome.timestamp = outcome.timestamp or time.time()
        self.state.trade_history.append(outcome)

        # Update feature importances
        self._update_feature_importances(outcome)

        # Update calibration
        self._update_calibration(outcome)

        logger.info(
            "Recorded trade %s: strategy=%s, outcome=%.2f, confidence=%.2f",
            outcome.trade_id,
            outcome.strategy,
            outcome.actual_outcome,
            outcome.predicted_confidence,
        )

    def analyze(self) -> list[AdaptationSignal]:
        """Analyze recent trades and generate adaptation signals.

        Returns
        -------
        list[AdaptationSignal]
            Recommended adaptations, sorted by urgency.
        """
        signals: list[AdaptationSignal] = []

        if len(self.state.trade_history) < 10:
            logger.info("Insufficient trade history for analysis (%d trades)", len(self.state.trade_history))
            return signals

        # Check alpha decay
        signals.extend(self._check_alpha_decay())

        # Check feature importance shifts
        signals.extend(self._check_feature_drift())

        # Check calibration
        signals.extend(self._check_calibration())

        # Check regime
        signals.extend(self._detect_regime_shift())

        # Sort by urgency
        signals.sort(key=lambda s: s.urgency, reverse=True)

        # Store in history
        self.state.adaptation_history.extend(signals)

        return signals

    def get_strategy_performance(self, strategy: str | None = None) -> dict[str, Any]:
        """Get performance metrics for a strategy.

        Parameters
        ----------
        strategy : str, optional
            Strategy name. If None, returns aggregate metrics.
        """
        trades = list(self.state.trade_history)
        if strategy:
            trades = [t for t in trades if t.strategy == strategy]

        if not trades:
            return {"n_trades": 0}

        outcomes = [t.actual_outcome for t in trades]
        wins = [o for o in outcomes if o > 0]
        losses = [o for o in outcomes if o < 0]

        return {
            "n_trades": len(trades),
            "win_rate": len(wins) / len(trades) if trades else 0,
            "avg_win": float(np.mean(wins)) if wins else 0,
            "avg_loss": float(np.mean(losses)) if losses else 0,
            "total_pnl": float(sum(outcomes)),
            "sharpe_proxy": (
                float(np.mean(outcomes) / (np.std(outcomes) + 1e-10))
                if len(outcomes) > 1 else 0
            ),
            "max_drawdown": float(self._compute_max_drawdown(outcomes)),
            "avg_confidence": float(np.mean([t.predicted_confidence for t in trades])),
        }

    def get_feature_report(self) -> list[dict[str, Any]]:
        """Get current feature importance report."""
        return [
            {
                "feature": fi.feature_name,
                "weight": fi.current_weight,
                "correlation": fi.rolling_correlation,
                "predictive_power": fi.predictive_power,
                "decay_rate": fi.decay_rate,
            }
            for fi in sorted(
                self.state.feature_importances.values(),
                key=lambda f: f.predictive_power,
                reverse=True,
            )
        ]

    # ------------------------------------------------------------------
    # Internal analysis methods
    # ------------------------------------------------------------------

    def _update_feature_importances(self, outcome: TradeOutcome) -> None:
        """Update feature importance based on trade outcome."""
        for feature_name, feature_value in outcome.features_used.items():
            if feature_name not in self.state.feature_importances:
                self.state.feature_importances[feature_name] = FeatureImportance(
                    feature_name=feature_name,
                    current_weight=1.0,
                )

            fi = self.state.feature_importances[feature_name]

            # Update rolling correlation between feature and outcome
            # Simple exponential moving average
            alpha = 0.1
            correlation_signal = 1.0 if (
                (feature_value > 0 and outcome.actual_outcome > 0) or
                (feature_value < 0 and outcome.actual_outcome < 0)
            ) else -1.0

            fi.rolling_correlation = (
                (1 - alpha) * fi.rolling_correlation + alpha * correlation_signal
            )

            # Update predictive power
            correct = abs(outcome.predicted_confidence - (1.0 if outcome.actual_outcome > 0 else 0.0))
            fi.predictive_power = (1 - alpha) * fi.predictive_power + alpha * (1.0 - correct)

            fi.last_updated = time.time()

    def _update_calibration(self, outcome: TradeOutcome) -> None:
        """Update prediction calibration tracking."""
        # Expected: confidence should match win rate at that confidence level
        actual_win = 1.0 if outcome.actual_outcome > 0 else 0.0
        error = abs(outcome.predicted_confidence - actual_win)

        alpha = 0.05
        self.state.calibration_error = (
            (1 - alpha) * self.state.calibration_error + alpha * error
        )

    def _check_alpha_decay(self) -> list[AdaptationSignal]:
        """Check if any strategy's alpha is decaying."""
        signals = []
        strategies = set(t.strategy for t in self.state.trade_history)

        for strategy in strategies:
            trades = [t for t in self.state.trade_history if t.strategy == strategy]
            if len(trades) < 20:
                continue

            # Compare recent performance vs historical
            recent = trades[-self.window_size // 2:]
            historical = trades[:self.window_size // 2]

            recent_sharpe = self._compute_sharpe([t.actual_outcome for t in recent])
            hist_sharpe = self._compute_sharpe([t.actual_outcome for t in historical])

            if hist_sharpe > 0 and recent_sharpe < hist_sharpe * (1 - self.alpha_decay_threshold):
                signals.append(AdaptationSignal(
                    adaptation_type=AdaptationType.ALPHA_DECAY,
                    target=strategy,
                    current_value=hist_sharpe,
                    recommended_value=recent_sharpe,
                    confidence=0.8,
                    reason=(
                        f"Strategy '{strategy}' Sharpe declined from {hist_sharpe:.2f} "
                        f"to {recent_sharpe:.2f} — possible alpha decay"
                    ),
                    urgency=4,
                ))

        return signals

    def _check_feature_drift(self) -> list[AdaptationSignal]:
        """Check if feature importance has shifted."""
        signals = []
        for name, fi in self.state.feature_importances.items():
            if fi.decay_rate > 0.5:
                signals.append(AdaptationSignal(
                    adaptation_type=AdaptationType.FEATURE_REWEIGHT,
                    target=name,
                    current_value=fi.current_weight,
                    recommended_value=fi.current_weight * 0.5,
                    confidence=0.6,
                    reason=f"Feature '{name}' predictive power declining (decay: {fi.decay_rate:.2f})",
                    urgency=2,
                ))
        return signals

    def _check_calibration(self) -> list[AdaptationSignal]:
        """Check if predictions are well-calibrated."""
        signals = []
        if self.state.calibration_error > self.calibration_threshold:
            signals.append(AdaptationSignal(
                adaptation_type=AdaptationType.MODEL_RECALIBRATE,
                target="confidence_predictions",
                current_value=self.state.calibration_error,
                recommended_value=self.calibration_threshold,
                confidence=0.7,
                reason=(
                    f"Prediction calibration error ({self.state.calibration_error:.3f}) "
                    f"exceeds threshold ({self.calibration_threshold:.3f})"
                ),
                urgency=3,
            ))
        return signals

    def _detect_regime_shift(self) -> list[AdaptationSignal]:
        """Detect if market regime has shifted."""
        signals = []
        recent = list(self.state.trade_history)[-self.regime_lookback:]
        if len(recent) < self.regime_lookback:
            return signals

        outcomes = [t.actual_outcome for t in recent]
        volatility = float(np.std(outcomes))
        mean_return = float(np.mean(outcomes))

        # Classify regime
        new_regime = self._classify_regime(mean_return, volatility)

        if new_regime != self.state.current_regime:
            signals.append(AdaptationSignal(
                adaptation_type=AdaptationType.REGIME_SHIFT,
                target="market_regime",
                current_value=self.state.current_regime.value,
                recommended_value=new_regime.value,
                confidence=0.6,
                reason=(
                    f"Regime shift detected: {self.state.current_regime.value} → {new_regime.value} "
                    f"(vol={volatility:.4f}, mean={mean_return:.4f})"
                ),
                urgency=4,
            ))
            self.state.current_regime = new_regime

        return signals

    @staticmethod
    def _classify_regime(mean_return: float, volatility: float) -> RegimeType:
        """Classify market regime from return statistics."""
        if volatility > 0.03:
            if abs(mean_return) > 0.01:
                return RegimeType.CRISIS
            return RegimeType.HIGH_VOLATILITY
        if volatility < 0.005:
            return RegimeType.LOW_VOLATILITY
        if mean_return > 0.005:
            return RegimeType.TRENDING_UP
        if mean_return < -0.005:
            return RegimeType.TRENDING_DOWN
        return RegimeType.RANGE_BOUND

    @staticmethod
    def _compute_sharpe(returns: list[float]) -> float:
        if len(returns) < 2:
            return 0.0
        arr = np.array(returns)
        return float(np.mean(arr) / (np.std(arr) + 1e-10))

    @staticmethod
    def _compute_max_drawdown(returns: list[float]) -> float:
        if not returns:
            return 0.0
        cumulative = np.cumsum(returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = running_max - cumulative
        return float(np.max(drawdown)) if len(drawdown) > 0 else 0.0
