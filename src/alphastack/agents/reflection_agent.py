"""Reflection Agent — real implementation with trade journal and performance analysis.

Production features:
- Structured trade journal generation with entry/exit reasoning
- Performance analysis with key metrics (win rate, profit factor, Sharpe, Sortino)
- **Strategy performance tracking by market regime** (learning #1)
- **Signal combination win-rate tracking** (learning #2)
- **Adaptive confidence thresholds** based on recent performance (learning #3)
- Strategy improvement suggestions based on pattern analysis
- Trace mining integration for systematic improvement
- Kelly stat updates pushed back to the Risk Agent
"""

from __future__ import annotations

import math
import statistics
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from alphastack.agents.base import AlphaStackAgent
from alphastack.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Trade Journal Entry
# ---------------------------------------------------------------------------

class TradeJournalEntry:
    """Structured journal entry for a single trade."""

    def __init__(
        self,
        trade_id: str,
        symbol: str,
        side: str,
        entry_price: float,
        exit_price: float,
        quantity: float,
        pnl: float,
        regime: str = "",
        strategy: str = "",
        signal_strength: float = 0.0,
        confluence_score: float = 0.0,
        hold_time_minutes: float = 0.0,
        slippage_bps: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.id = uuid.uuid4().hex[:12]
        self.trade_id = trade_id
        self.symbol = symbol
        self.side = side
        self.entry_price = entry_price
        self.exit_price = exit_price
        self.quantity = quantity
        self.pnl = pnl
        self.pnl_pct = ((exit_price - entry_price) / entry_price * 100) if entry_price > 0 else 0.0
        self.regime = regime
        self.strategy = strategy
        self.signal_strength = signal_strength
        self.confluence_score = confluence_score
        self.hold_time_minutes = hold_time_minutes
        self.slippage_bps = slippage_bps
        self.metadata = metadata or {}
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.tags: list[str] = []
        self.lessons: list[str] = []
        # Signal combination keys that produced this trade
        self.signal_combo: tuple[str, ...] = ()

    def add_tag(self, tag: str) -> None:
        self.tags.append(tag)

    def add_lesson(self, lesson: str) -> None:
        self.lessons.append(lesson)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "side": self.side,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "quantity": self.quantity,
            "pnl": round(self.pnl, 6),
            "pnl_pct": round(self.pnl_pct, 4),
            "regime": self.regime,
            "strategy": self.strategy,
            "signal_strength": self.signal_strength,
            "confluence_score": self.confluence_score,
            "hold_time_minutes": self.hold_time_minutes,
            "slippage_bps": self.slippage_bps,
            "timestamp": self.timestamp,
            "tags": self.tags,
            "lessons": self.lessons,
            "metadata": self.metadata,
            "signal_combo": list(self.signal_combo),
        }


# ---------------------------------------------------------------------------
# Performance Analyzer
# ---------------------------------------------------------------------------

class PerformanceAnalyzer:
    """Computes key trading performance metrics."""

    @staticmethod
    def compute_metrics(
        pnls: list[float],
        hold_times: list[float] | None = None,
        risk_free_rate: float = 0.05,
    ) -> dict[str, Any]:
        """Compute comprehensive performance metrics.

        Parameters
        ----------
        pnls : list[float]
            List of P&L values (positive = win, negative = loss).
        hold_times : list[float] | None
            Hold times in minutes.
        risk_free_rate : float
            Annualized risk-free rate for Sharpe/Sortino.

        Returns
        -------
        dict
            Performance metrics.
        """
        if not pnls:
            return {
                "trade_count": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "total_pnl": 0.0,
            }

        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        breakeven = [p for p in pnls if p == 0]

        win_rate = len(wins) / len(pnls) if pnls else 0.0
        avg_win = statistics.mean(wins) if wins else 0.0
        avg_loss = statistics.mean(losses) if losses else 0.0
        total_wins = sum(wins)
        total_losses = abs(sum(losses))
        profit_factor = total_wins / total_losses if total_losses > 0 else float("inf") if total_wins else 0.0
        avg_rr = abs(avg_win / avg_loss) if avg_loss != 0 else float("inf") if avg_win > 0 else 0.0

        # Expectancy (mathematical expectation per trade)
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * abs(avg_loss))

        # Sharpe ratio (annualized, assuming ~252 trading days)
        if len(pnls) > 1:
            pnl_std = statistics.stdev(pnls)
            mean_pnl = statistics.mean(pnls)
            # Daily risk-free (simplified)
            daily_rf = risk_free_rate / 252
            sharpe = ((mean_pnl - daily_rf) / pnl_std) * math.sqrt(252) if pnl_std > 0 else 0.0
        else:
            sharpe = 0.0
            pnl_std = 0.0

        # Sortino ratio (only penalizes downside volatility)
        downside_returns = [p for p in pnls if p < 0]
        if downside_returns and len(pnls) > 1:
            downside_std = statistics.stdev(downside_returns) if len(downside_returns) > 1 else abs(statistics.mean(downside_returns))
            mean_pnl = statistics.mean(pnls)
            daily_rf = risk_free_rate / 252
            sortino = ((mean_pnl - daily_rf) / downside_std) * math.sqrt(252) if downside_std > 0 else 0.0
        else:
            sortino = 0.0

        # Max consecutive losses
        max_consecutive_losses = 0
        current_streak = 0
        for p in pnls:
            if p < 0:
                current_streak += 1
                max_consecutive_losses = max(max_consecutive_losses, current_streak)
            else:
                current_streak = 0

        # Max drawdown from cumulative P&L
        cumulative = 0.0
        peak = 0.0
        max_drawdown = 0.0
        for p in pnls:
            cumulative += p
            peak = max(peak, cumulative)
            drawdown = peak - cumulative
            max_drawdown = max(max_drawdown, drawdown)

        metrics: dict[str, Any] = {
            "trade_count": len(pnls),
            "win_count": len(wins),
            "loss_count": len(losses),
            "breakeven_count": len(breakeven),
            "win_rate": round(win_rate, 4),
            "profit_factor": round(profit_factor, 4),
            "avg_win": round(avg_win, 6),
            "avg_loss": round(avg_loss, 6),
            "avg_rr_ratio": round(avg_rr, 4),
            "expectancy": round(expectancy, 6),
            "total_pnl": round(sum(pnls), 6),
            "total_wins": round(total_wins, 6),
            "total_losses": round(total_losses, 6),
            "max_consecutive_losses": max_consecutive_losses,
            "max_drawdown": round(max_drawdown, 6),
            "sharpe_ratio": round(sharpe, 4),
            "sortino_ratio": round(sortino, 4),
            "pnl_std": round(pnl_std, 6),
        }

        if hold_times:
            metrics["avg_hold_time_minutes"] = round(statistics.mean(hold_times), 1)
            metrics["median_hold_time_minutes"] = round(statistics.median(hold_times), 1)

        return metrics


# ---------------------------------------------------------------------------
# Regime Performance Tracker (Learning #1)
# ---------------------------------------------------------------------------

class RegimePerformanceTracker:
    """Tracks strategy performance broken down by market regime.

    Maintains rolling statistics per regime so the system can learn:
    - Which regimes are profitable vs which are not
    - Which strategies work best in each regime
    - How to adjust sizing and thresholds per regime
    """

    def __init__(self, window_size: int = 50) -> None:
        self._window_size = window_size
        # regime -> list of (pnl, strategy, timestamp, signal_strength)
        self._regime_trades: dict[str, list[dict[str, Any]]] = defaultdict(list)
        # regime -> strategy -> list of pnl
        self._regime_strategy_pnl: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))

    def record(
        self,
        regime: str,
        pnl: float,
        strategy: str = "",
        signal_strength: float = 0.0,
    ) -> None:
        """Record a trade outcome for a regime."""
        entry = {
            "pnl": pnl,
            "strategy": strategy,
            "signal_strength": signal_strength,
            "timestamp": time.time(),
        }
        self._regime_trades[regime].append(entry)
        # Keep window bounded
        if len(self._regime_trades[regime]) > self._window_size * 2:
            self._regime_trades[regime] = self._regime_trades[regime][-self._window_size:]
        self._regime_strategy_pnl[regime][strategy].append(pnl)

    def get_regime_stats(self, regime: str) -> dict[str, Any]:
        """Get performance stats for a specific regime."""
        trades = self._regime_trades.get(regime, [])
        if not trades:
            return {"regime": regime, "trade_count": 0}

        pnls = [t["pnl"] for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]

        return {
            "regime": regime,
            "trade_count": len(pnls),
            "win_rate": round(len(wins) / len(pnls), 4) if pnls else 0,
            "total_pnl": round(sum(pnls), 6),
            "avg_pnl": round(statistics.mean(pnls), 6) if pnls else 0,
            "avg_win": round(statistics.mean(wins), 6) if wins else 0,
            "avg_loss": round(statistics.mean(losses), 6) if losses else 0,
            "profit_factor": round(
                sum(wins) / abs(sum(losses)), 4
            ) if losses and sum(losses) != 0 else (float("inf") if wins else 0),
        }

    def get_all_regime_stats(self) -> dict[str, dict[str, Any]]:
        """Get performance stats for all tracked regimes."""
        return {regime: self.get_regime_stats(regime) for regime in self._regime_trades}

    def get_best_regime(self) -> str | None:
        """Return the regime with highest expectancy, or None."""
        best_regime = None
        best_expectancy = float("-inf")
        for regime in self._regime_trades:
            stats = self.get_regime_stats(regime)
            if stats["trade_count"] < 3:
                continue
            if stats["avg_pnl"] > best_expectancy:
                best_expectancy = stats["avg_pnl"]
                best_regime = regime
        return best_regime

    def get_worst_regime(self) -> str | None:
        """Return the regime with lowest expectancy, or None."""
        worst_regime = None
        worst_expectancy = float("inf")
        for regime in self._regime_trades:
            stats = self.get_regime_stats(regime)
            if stats["trade_count"] < 3:
                continue
            if stats["avg_pnl"] < worst_expectancy:
                worst_expectancy = stats["avg_pnl"]
                worst_regime = regime
        return worst_regime

    def get_regime_strategy_matrix(self) -> dict[str, dict[str, dict[str, Any]]]:
        """Return regime × strategy performance matrix.

        Returns: {regime: {strategy: {win_rate, total_pnl, trade_count}}}
        """
        matrix: dict[str, dict[str, dict[str, Any]]] = {}
        for regime, strat_map in self._regime_strategy_pnl.items():
            matrix[regime] = {}
            for strategy, pnls in strat_map.items():
                if not pnls:
                    continue
                wins = [p for p in pnls if p > 0]
                matrix[regime][strategy] = {
                    "trade_count": len(pnls),
                    "win_rate": round(len(wins) / len(pnls), 4),
                    "total_pnl": round(sum(pnls), 6),
                    "avg_pnl": round(statistics.mean(pnls), 6),
                }
        return matrix


# ---------------------------------------------------------------------------
# Signal Combination Tracker (Learning #2)
# ---------------------------------------------------------------------------

class SignalCombinationTracker:
    """Tracks which signal combinations produce the highest win rates.

    Signal combinations are represented as sorted tuples of signal names.
    Example: ("MACD_bullish", "RSI_oversold", "volume_spike")

    This lets the system learn that "RSI + MACD + volume" works 65% of
    the time while "RSI alone" only works 42%.
    """

    def __init__(self, min_samples: int = 5) -> None:
        self._min_samples = min_samples
        # combo_key -> list of (pnl, timestamp)
        self._combo_outcomes: dict[str, list[dict[str, Any]]] = defaultdict(list)
        # Individual signal -> list of pnl
        self._individual_outcomes: dict[str, list[float]] = defaultdict(list)

    def record(self, signal_combo: tuple[str, ...], pnl: float) -> None:
        """Record a trade outcome for a signal combination."""
        key = self._combo_key(signal_combo)
        self._combo_outcomes[key].append({"pnl": pnl, "timestamp": time.time()})
        # Also track individual signals
        for sig in signal_combo:
            self._individual_outcomes[sig].append(pnl)

    def get_combo_stats(self, signal_combo: tuple[str, ...]) -> dict[str, Any]:
        """Get stats for a specific signal combination."""
        key = self._combo_key(signal_combo)
        outcomes = self._combo_outcomes.get(key, [])
        if not outcomes:
            return {"combo": list(signal_combo), "trade_count": 0}

        pnls = [o["pnl"] for o in outcomes]
        wins = [p for p in pnls if p > 0]

        return {
            "combo": list(signal_combo),
            "trade_count": len(pnls),
            "win_rate": round(len(wins) / len(pnls), 4) if pnls else 0,
            "total_pnl": round(sum(pnls), 6),
            "avg_pnl": round(statistics.mean(pnls), 6) if pnls else 0,
            "expectancy": round(statistics.mean(pnls), 6) if pnls else 0,
        }

    def get_top_combos(self, top_k: int = 10) -> list[dict[str, Any]]:
        """Return top-K signal combinations by win rate (with min samples)."""
        combos = []
        for key, outcomes in self._combo_outcomes.items():
            if len(outcomes) < self._min_samples:
                continue
            pnls = [o["pnl"] for o in outcomes]
            wins = [p for p in pnls if p > 0]
            combo = key.split("|")
            combos.append({
                "combo": combo,
                "trade_count": len(pnls),
                "win_rate": round(len(wins) / len(pnls), 4),
                "total_pnl": round(sum(pnls), 6),
                "avg_pnl": round(statistics.mean(pnls), 6),
                "expectancy": round(statistics.mean(pnls), 6),
            })
        combos.sort(key=lambda c: c["win_rate"], reverse=True)
        return combos[:top_k]

    def get_worst_combos(self, top_k: int = 5) -> list[dict[str, Any]]:
        """Return worst signal combinations by win rate."""
        combos = []
        for key, outcomes in self._combo_outcomes.items():
            if len(outcomes) < self._min_samples:
                continue
            pnls = [o["pnl"] for o in outcomes]
            wins = [p for p in pnls if p > 0]
            combo = key.split("|")
            combos.append({
                "combo": combo,
                "trade_count": len(pnls),
                "win_rate": round(len(wins) / len(pnls), 4),
                "total_pnl": round(sum(pnls), 6),
            })
        combos.sort(key=lambda c: c["win_rate"])
        return combos[:top_k]

    def get_individual_signal_stats(self) -> dict[str, dict[str, Any]]:
        """Get win rate for each individual signal type."""
        stats = {}
        for signal, pnls in self._individual_outcomes.items():
            if len(pnls) < 3:
                continue
            wins = [p for p in pnls if p > 0]
            stats[signal] = {
                "trade_count": len(pnls),
                "win_rate": round(len(wins) / len(pnls), 4),
                "total_pnl": round(sum(pnls), 6),
                "avg_pnl": round(statistics.mean(pnls), 6),
            }
        return stats

    @staticmethod
    def _combo_key(signals: tuple[str, ...]) -> str:
        """Create a deterministic key from signal names."""
        return "|".join(sorted(signals))


# ---------------------------------------------------------------------------
# Adaptive Confidence Thresholds (Learning #3)
# ---------------------------------------------------------------------------

class AdaptiveThresholds:
    """Dynamically adjusts confidence thresholds based on recent performance.

    When the system is winning → slightly relax thresholds (take more trades).
    When the system is losing  → tighten thresholds (be more selective).

    Uses exponential moving average of recent win rate to smoothly adapt.
    """

    def __init__(
        self,
        base_confidence: float = 0.45,
        base_confluence: float = 0.30,
        adaptation_rate: float = 0.05,
        lookback: int = 20,
    ) -> None:
        self._base_confidence = base_confidence
        self._base_confluence = base_confluence
        self._adaptation_rate = adaptation_rate
        self._lookback = lookback
        self._recent_outcomes: list[float] = []  # 1.0 for win, 0.0 for loss
        self._current_confidence = base_confidence
        self._current_confluence = base_confluence
        self._adjustment_history: list[dict[str, Any]] = []

    def record_outcome(self, pnl: float) -> None:
        """Record a trade outcome for threshold adaptation."""
        outcome = 1.0 if pnl > 0 else 0.0
        self._recent_outcomes.append(outcome)
        if len(self._recent_outcomes) > self._lookback * 2:
            self._recent_outcomes = self._recent_outcomes[-self._lookback:]

        # Recompute thresholds
        self._adapt()

    def _adapt(self) -> None:
        """Adjust thresholds based on recent win rate."""
        if len(self._recent_outcomes) < self._lookback:
            return

        recent = self._recent_outcomes[-self._lookback:]
        recent_wr = sum(recent) / len(recent)

        # Target win rate is 0.55 — if above, relax; if below, tighten
        deviation = recent_wr - 0.55

        # Adjust confidence threshold: lower = take more trades, higher = more selective
        old_conf = self._current_confidence
        self._current_confidence = self._base_confidence - (deviation * self._adaptation_rate * 10)
        # Clamp to [0.2, 0.8]
        self._current_confidence = max(0.2, min(0.8, self._current_confidence))

        old_confluence = self._current_confluence
        self._current_confluence = self._base_confluence - (deviation * self._adaptation_rate * 8)
        # Clamp to [0.1, 0.7]
        self._current_confluence = max(0.1, min(0.7, self._current_confluence))

        if abs(old_conf - self._current_confidence) > 0.001:
            self._adjustment_history.append({
                "timestamp": time.time(),
                "recent_win_rate": round(recent_wr, 4),
                "old_confidence": round(old_conf, 4),
                "new_confidence": round(self._current_confidence, 4),
                "old_confluence": round(old_confluence, 4),
                "new_confluence": round(self._current_confluence, 4),
                "deviation": round(deviation, 4),
            })

    @property
    def confidence_threshold(self) -> float:
        return round(self._current_confidence, 4)

    @property
    def confluence_threshold(self) -> float:
        return round(self._current_confluence, 4)

    def get_state(self) -> dict[str, Any]:
        """Return current threshold state."""
        recent_wr = 0.0
        if self._recent_outcomes:
            recent = self._recent_outcomes[-self._lookback:]
            recent_wr = sum(recent) / len(recent) if recent else 0.0

        return {
            "confidence_threshold": self.confidence_threshold,
            "confluence_threshold": self.confluence_threshold,
            "base_confidence": self._base_confidence,
            "base_confluence": self._base_confluence,
            "recent_win_rate": round(recent_wr, 4),
            "samples": len(self._recent_outcomes),
            "adjustments_made": len(self._adjustment_history),
            "last_adjustment": self._adjustment_history[-1] if self._adjustment_history else None,
        }


# ---------------------------------------------------------------------------
# Strategy Improvement Engine
# ---------------------------------------------------------------------------

class StrategyImprover:
    """Analyzes trade patterns and generates improvement suggestions."""

    def analyze_and_suggest(
        self,
        journal_entries: list[dict[str, Any]],
        metrics: dict[str, Any],
        pipeline_context: dict[str, Any],
        regime_stats: dict[str, dict[str, Any]] | None = None,
        signal_combo_stats: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Generate improvement suggestions based on trade patterns.

        Returns list of suggestion dicts with parameter, current value,
        recommended value, reason, and priority.
        """
        suggestions: list[dict[str, Any]] = []

        win_rate = metrics.get("win_rate", 0.0)
        profit_factor = metrics.get("profit_factor", 0.0)
        avg_rr = metrics.get("avg_rr_ratio", 0.0)
        trade_count = metrics.get("trade_count", 0)
        expectancy = metrics.get("expectancy", 0.0)
        max_consec_losses = metrics.get("max_consecutive_losses", 0)

        if trade_count < 3:
            return [{"parameter": "data", "reason": "Insufficient trades for analysis (need ≥3)", "priority": "info"}]

        # 1. Low win rate → tighten entry filters
        if win_rate < 0.4:
            current_threshold = pipeline_context.get("confluence_threshold", 0.3)
            suggestions.append({
                "parameter": "min_confluence_score",
                "current": current_threshold,
                "recommended": min(current_threshold + 0.1, 0.8),
                "reason": f"Win rate {win_rate:.1%} below 40% — tighten entry filter to reduce false signals",
                "priority": "high",
                "category": "entry",
            })

        # 2. Poor R:R → widen TP or tighten SL
        if avg_rr < 1.0:
            suggestions.append({
                "parameter": "risk_reward_minimum",
                "current": pipeline_context.get("min_rr", 1.5),
                "recommended": max(1.5, pipeline_context.get("min_rr", 1.5)),
                "reason": f"Average R:R {avg_rr:.2f} below 1.0 — winners too small relative to losers",
                "priority": "high",
                "category": "exit",
            })

        # 3. Profit factor below 1.0 → system is losing money
        if profit_factor < 1.0:
            suggestions.append({
                "parameter": "pause_and_review",
                "current": "active",
                "recommended": "paused",
                "reason": f"Profit factor {profit_factor:.2f} below 1.0 — system losing money overall",
                "priority": "critical",
                "category": "system",
            })

        # 4. High consecutive losses → add drawdown circuit breaker
        if max_consec_losses >= 5:
            suggestions.append({
                "parameter": "consecutive_loss_limit",
                "current": pipeline_context.get("consecutive_loss_limit", "none"),
                "recommended": max_consec_losses - 1,
                "reason": f"Max {max_consec_losses} consecutive losses detected — add circuit breaker",
                "priority": "high",
                "category": "risk",
            })

        # 5. Regime-specific analysis (enhanced with tracker data)
        if regime_stats:
            for regime, stats in regime_stats.items():
                if stats.get("trade_count", 0) < 3:
                    continue
                regime_wr = stats.get("win_rate", 0)
                regime_pf = stats.get("profit_factor", 0)

                if regime_wr < 0.3:
                    suggestions.append({
                        "parameter": f"regime_{regime}_filter",
                        "current": "active",
                        "recommended": "reduced_size",
                        "reason": (
                            f"Win rate {regime_wr:.1%} in {regime} regime "
                            f"({stats['trade_count']} trades, PF={regime_pf:.1f}) — reduce exposure"
                        ),
                        "priority": "medium",
                        "category": "regime",
                    })
                elif regime_wr > 0.65 and stats.get("trade_count", 0) >= 10:
                    suggestions.append({
                        "parameter": f"regime_{regime}_boost",
                        "current": "standard_size",
                        "recommended": "increased_size",
                        "reason": (
                            f"Win rate {regime_wr:.1%} in {regime} regime "
                            f"({stats['trade_count']} trades) — consider increasing exposure"
                        ),
                        "priority": "low",
                        "category": "regime",
                    })
        else:
            # Fallback: inline regime analysis
            regime_trades: dict[str, list[dict[str, Any]]] = {}
            for entry in journal_entries:
                regime = entry.get("regime", "unknown")
                regime_trades.setdefault(regime, []).append(entry)

            for regime, trades in regime_trades.items():
                regime_pnls = [t.get("pnl", 0) for t in trades]
                regime_wr = sum(1 for p in regime_pnls if p > 0) / len(regime_pnls) if regime_pnls else 0
                regime_pf = (
                    sum(p for p in regime_pnls if p > 0) / abs(sum(p for p in regime_pnls if p < 0))
                    if any(p < 0 for p in regime_pnls) and sum(p for p in regime_pnls if p < 0) != 0
                    else float("inf") if any(p > 0 for p in regime_pnls) else 0
                )

                if regime_wr < 0.3 and len(trades) >= 3:
                    suggestions.append({
                        "parameter": f"regime_{regime}_filter",
                        "current": "active",
                        "recommended": "reduced_size",
                        "reason": f"Win rate {regime_wr:.1%} in {regime} regime ({len(trades)} trades, PF={regime_pf:.1f}) — reduce exposure",
                        "priority": "medium",
                        "category": "regime",
                    })

        # 6. Signal combination analysis
        if signal_combo_stats:
            for combo_stat in signal_combo_stats[:3]:  # top 3
                if combo_stat.get("win_rate", 0) > 0.65 and combo_stat.get("trade_count", 0) >= 5:
                    suggestions.append({
                        "parameter": "signal_combo_boost",
                        "current": "standard",
                        "recommended": "prioritize",
                        "reason": (
                            f"Signal combo {combo_stat['combo']} has {combo_stat['win_rate']:.0%} win rate "
                            f"({combo_stat['trade_count']} trades) — prioritize this combination"
                        ),
                        "priority": "medium",
                        "category": "signals",
                    })

        # 7. Symbol-specific analysis
        symbol_trades: dict[str, list[dict[str, Any]]] = {}
        for entry in journal_entries:
            sym = entry.get("symbol", "")
            symbol_trades.setdefault(sym, []).append(entry)

        for sym, trades in symbol_trades.items():
            sym_pnls = [t.get("pnl", 0) for t in trades]
            sym_wr = sum(1 for p in sym_pnls if p > 0) / len(sym_pnls) if sym_pnls else 0

            if sym_wr < 0.25 and len(trades) >= 3:
                suggestions.append({
                    "parameter": f"symbol_{sym}_filter",
                    "current": "active",
                    "recommended": "review_or_remove",
                    "reason": f"Win rate {sym_wr:.1%} on {sym} ({len(trades)} trades) — review or remove from universe",
                    "priority": "medium",
                    "category": "universe",
                })

        # 8. Good performance → suggest scaling
        if win_rate > 0.6 and profit_factor > 2.0 and trade_count >= 10:
            suggestions.append({
                "parameter": "kelly_fraction",
                "current": 0.5,
                "recommended": 0.6,
                "reason": f"Strong performance (WR={win_rate:.1%}, PF={profit_factor:.1f}) — consider increasing Kelly fraction",
                "priority": "low",
                "category": "sizing",
            })

        # 9. Expectancy per trade
        if expectancy < 0:
            suggestions.append({
                "parameter": "expectancy",
                "current": round(expectancy, 6),
                "recommended": "positive",
                "reason": f"Negative expectancy ({expectancy:.4f}) — system expected to lose per trade",
                "priority": "critical",
                "category": "system",
            })

        return suggestions


# ---------------------------------------------------------------------------
# Reflection Agent
# ---------------------------------------------------------------------------

class ReflectionAgent(AlphaStackAgent):
    """Post-trade analysis, performance review, and strategy adjustment.

    Upgraded v3.0 features (self-improving loop):
    - Structured trade journal generation
    - Performance analysis (Sharpe, Sortino, expectancy, consecutive losses)
    - **RegimePerformanceTracker** — tracks win rate per market regime
    - **SignalCombinationTracker** — identifies highest win-rate signal combos
    - **AdaptiveThresholds** — auto-tunes confidence/confluence thresholds
    - Strategy improvement suggestions (regime-aware, signal-aware, symbol-aware)
    - Trace mining integration
    - Kelly stat updates for the Risk Agent
    """

    def __init__(self, event_bus: Any | None = None) -> None:
        super().__init__(
            name="reflection",
            role="analyst",
            description="Post-trade analysis with journal, performance metrics, and adaptive learning",
            event_bus=event_bus,
            timeout=300.0,  # reflection can be thorough
            max_retries=1,
            cb_failure_threshold=3,
        )
        self._analyzer = PerformanceAnalyzer()
        self._improver = StrategyImprover()
        self._journal: list[TradeJournalEntry] = []
        self._max_journal = 1000

        # --- Learning components ---
        self._regime_tracker = RegimePerformanceTracker(window_size=50)
        self._signal_tracker = SignalCombinationTracker(min_samples=5)
        self._adaptive_thresholds = AdaptiveThresholds(
            base_confidence=0.45,
            base_confluence=0.30,
            adaptation_rate=0.05,
            lookback=20,
        )

    def system_prompt(self) -> str:
        return (
            "You are the AlphaStack Reflection Agent. Your job is to:\n"
            "1. Generate structured trade journal entries for every execution\n"
            "2. Compute performance metrics: win rate, PF, Sharpe, Sortino, expectancy\n"
            "3. Track strategy performance by market regime\n"
            "4. Identify which signal combinations have highest win rate\n"
            "5. Adjust confidence thresholds based on recent performance\n"
            "6. Generate concrete improvement suggestions with priority\n"
            "7. Update Kelly statistics for the Risk Agent\n"
            "8. Feed learnings back to improve the strategy pipeline\n"
        )

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Run post-trade reflection, generate journal, and suggest improvements."""
        execution_log = state.get("execution_log", [])
        trade_decisions = state.get("trade_decisions", [])
        pipeline_context = state.get("pipeline_context", {})
        signals = state.get("signals", [])

        logger.info(
            "reflection_agent.start",
            executions=len(execution_log),
            decisions=len(trade_decisions),
        )

        # 1. Generate trade journal entries
        journal_entries = self._generate_journal(execution_log, signals, pipeline_context)

        # 2. Feed outcomes into learning trackers
        for entry in journal_entries:
            # Regime tracker
            self._regime_tracker.record(
                regime=entry.regime,
                pnl=entry.pnl,
                strategy=entry.strategy,
                signal_strength=entry.signal_strength,
            )
            # Signal combination tracker
            if entry.signal_combo:
                self._signal_tracker.record(entry.signal_combo, entry.pnl)
            # Adaptive thresholds
            self._adaptive_thresholds.record_outcome(entry.pnl)

        # 3. Compute performance metrics
        pnls = [j.pnl for j in journal_entries]
        hold_times = [j.hold_time_minutes for j in journal_entries if j.hold_time_minutes > 0]
        metrics = self._analyzer.compute_metrics(pnls, hold_times or None)

        # 4. Get learning data
        regime_stats = self._regime_tracker.get_all_regime_stats()
        top_combos = self._signal_tracker.get_top_combos(top_k=10)
        threshold_state = self._adaptive_thresholds.get_state()

        # 5. Generate improvement suggestions (now with learning data)
        journal_dicts = [j.to_dict() for j in journal_entries]
        suggestions = self._improver.analyze_and_suggest(
            journal_dicts, metrics, pipeline_context,
            regime_stats=regime_stats,
            signal_combo_stats=top_combos,
        )

        # 6. Compute Kelly stats for Risk Agent
        kelly_update = self._compute_kelly_update(metrics)

        # 7. Extract learnings
        learnings = self._extract_learnings(metrics, journal_dicts, regime_stats, top_combos)

        # 8. Store journal entries
        self._journal.extend(journal_entries)
        if len(self._journal) > self._max_journal:
            self._journal = self._journal[-self._max_journal:]

        # 9. Build performance summary
        performance: dict[str, Any] = {
            **metrics,
            "learnings": learnings,
            "kelly_update": kelly_update,
            "reflection_timestamp": datetime.now(timezone.utc).isoformat(),
            # --- Learning data ---
            "regime_performance": regime_stats,
            "top_signal_combos": top_combos[:5],
            "worst_signal_combos": self._signal_tracker.get_worst_combos(3),
            "individual_signal_stats": self._signal_tracker.get_individual_signal_stats(),
            "adaptive_thresholds": threshold_state,
            "regime_strategy_matrix": self._regime_tracker.get_regime_strategy_matrix(),
        }

        logger.info(
            "reflection_agent.complete",
            journal_entries=len(journal_entries),
            trade_count=metrics.get("trade_count", 0),
            win_rate=metrics.get("win_rate", 0),
            suggestions=len(suggestions),
            regimes_tracked=len(regime_stats),
            signal_combos_tracked=len(top_combos),
        )

        return {
            "performance_summary": performance,
            "strategy_adjustments": suggestions,
            "trade_journal": [j.to_dict() for j in journal_entries[-10:]],  # last 10
            "adaptive_thresholds": {
                "confidence": self._adaptive_thresholds.confidence_threshold,
                "confluence": self._adaptive_thresholds.confluence_threshold,
            },
            "_confidence": 0.85,
        }

    # ------------------------------------------------------------------
    # Journal generation
    # ------------------------------------------------------------------

    def _generate_journal(
        self,
        execution_log: list[dict[str, Any]],
        signals: list[Any],
        pipeline_context: dict[str, Any],
    ) -> list[TradeJournalEntry]:
        """Generate structured journal entries from execution log."""
        entries: list[TradeJournalEntry] = []
        regime = pipeline_context.get("regime", "unknown")

        # Build signal lookup
        signal_map: dict[str, dict[str, Any]] = {}
        for sig in signals:
            sym = sig.get("symbol", "") if isinstance(sig, dict) else getattr(sig, "symbol", "")
            if sym:
                signal_map[sym] = sig if isinstance(sig, dict) else {
                    "symbol": getattr(sig, "symbol", ""),
                    "strength": getattr(sig, "strength", 0.0),
                    "confluence_score": getattr(sig, "confluence_score", 0.0),
                    "strategy": getattr(sig, "strategy", ""),
                }

        for entry in execution_log:
            if entry.get("status") != "filled":
                continue

            symbol = entry.get("symbol", "")
            signal = signal_map.get(symbol, {})

            # Compute P&L
            fill_price = entry.get("fill_price", 0.0)
            entry_price = entry.get("price", 0.0)
            action = entry.get("action", "")
            quantity = entry.get("quantity", 0.0)

            if fill_price and entry_price and action in ("buy", "sell"):
                if action == "buy":
                    pnl = (fill_price - entry_price) * quantity
                else:
                    pnl = (entry_price - fill_price) * quantity
            else:
                pnl = 0.0

            # Slippage
            slippage = entry.get("slippage", {})
            slippage_bps = slippage.get("slippage_bps", 0.0) if isinstance(slippage, dict) else 0.0

            journal_entry = TradeJournalEntry(
                trade_id=entry.get("id", ""),
                symbol=symbol,
                side=action,
                entry_price=entry_price,
                exit_price=fill_price,
                quantity=quantity,
                pnl=pnl,
                regime=regime,
                strategy=signal.get("strategy", "alphastack"),
                signal_strength=signal.get("strength", 0.0),
                confluence_score=signal.get("confluence_score", 0.0),
                slippage_bps=slippage_bps,
                metadata={
                    "algorithm": entry.get("algorithm", "market"),
                    "broker": entry.get("broker", ""),
                    "decision_id": entry.get("decision_id", ""),
                },
            )

            # Build signal combination from metadata
            active_signals = entry.get("active_signals", signal.get("active_signals", []))
            if isinstance(active_signals, list) and active_signals:
                journal_entry.signal_combo = tuple(sorted(str(s) for s in active_signals))
            elif signal.get("strategy"):
                journal_entry.signal_combo = (signal["strategy"],)

            # Auto-tag
            if pnl > 0:
                journal_entry.add_tag("winner")
            elif pnl < 0:
                journal_entry.add_tag("loser")
            else:
                journal_entry.add_tag("breakeven")

            if regime:
                journal_entry.add_tag(f"regime:{regime}")

            if slippage_bps > 5:
                journal_entry.add_tag("high_slippage")

            entries.append(journal_entry)

        return entries

    # ------------------------------------------------------------------
    # Kelly update computation
    # ------------------------------------------------------------------

    def _compute_kelly_update(self, metrics: dict[str, Any]) -> dict[str, float]:
        """Compute Kelly criterion parameters from recent performance."""
        win_rate = metrics.get("win_rate", 0.55)
        avg_win = metrics.get("avg_win", 0.0)
        avg_loss = metrics.get("avg_loss", 0.0)

        # Convert to R-multiples for Kelly
        if avg_loss != 0:
            avg_rr = abs(avg_win / avg_loss)
        else:
            avg_rr = 1.5  # default

        return {
            "win_rate": win_rate,
            "avg_win": avg_rr,  # in R-multiples
            "avg_loss": 1.0,    # normalized to 1R
            "recommended_fraction": 0.5 if win_rate < 0.55 else 0.6,
        }

    # ------------------------------------------------------------------
    # Learnings extraction (enhanced with learning data)
    # ------------------------------------------------------------------

    def _extract_learnings(
        self,
        metrics: dict[str, Any],
        journal: list[dict[str, Any]],
        regime_stats: dict[str, dict[str, Any]] | None = None,
        top_combos: list[dict[str, Any]] | None = None,
    ) -> list[str]:
        """Extract human-readable learnings from all data sources."""
        learnings: list[str] = []
        trade_count = metrics.get("trade_count", 0)

        if trade_count == 0:
            learnings.append("No trades executed this cycle — review signal generation thresholds")
            return learnings

        win_rate = metrics.get("win_rate", 0)
        pf = metrics.get("profit_factor", 0)
        sharpe = metrics.get("sharpe_ratio", 0)
        expectancy = metrics.get("expectancy", 0)
        max_dd = metrics.get("max_drawdown", 0)

        # Win rate
        if win_rate > 0.6:
            learnings.append(f"Strong win rate ({win_rate:.1%}) — strategy is performing well")
        elif win_rate > 0.4:
            learnings.append(f"Moderate win rate ({win_rate:.1%}) — room for improvement in entry timing")
        else:
            learnings.append(f"Low win rate ({win_rate:.1%}) — tighten confluence requirements")

        # Profit factor
        if pf > 2.0:
            learnings.append(f"Excellent profit factor ({pf:.1f}) — winners significantly outweigh losers")
        elif pf > 1.0:
            learnings.append(f"Profitable profit factor ({pf:.1f}) — system is net positive")
        elif pf > 0:
            learnings.append(f"Profit factor below 1.0 ({pf:.1f}) — losing money overall")

        # Expectancy
        if expectancy > 0:
            learnings.append(f"Positive expectancy ({expectancy:.4f}) — system has a mathematical edge")
        else:
            learnings.append(f"Negative expectancy ({expectancy:.4f}) — system expected to lose per trade")

        # Sharpe
        if sharpe > 1.5:
            learnings.append(f"Strong risk-adjusted returns (Sharpe={sharpe:.2f})")
        elif sharpe > 0:
            learnings.append(f"Positive Sharpe ({sharpe:.2f}) — but could improve risk-adjusted returns")

        # Max drawdown
        if max_dd > 0:
            learnings.append(f"Max drawdown this cycle: {max_dd:.4f}")

        # Slippage
        high_slippage = [j for j in journal if j.get("slippage_bps", 0) > 5]
        if high_slippage:
            avg_slip = statistics.mean(j["slippage_bps"] for j in high_slippage)
            learnings.append(f"{len(high_slippage)} trades with high slippage (avg {avg_slip:.1f} bps)")

        # --- Regime learnings ---
        if regime_stats:
            best = self._regime_tracker.get_best_regime()
            worst = self._regime_tracker.get_worst_regime()
            if best:
                stats = regime_stats[best]
                learnings.append(
                    f"Best regime: {best} (WR={stats['win_rate']:.1%}, "
                    f"{stats['trade_count']} trades, avg PnL={stats['avg_pnl']:.4f})"
                )
            if worst and worst != best:
                stats = regime_stats[worst]
                learnings.append(
                    f"Worst regime: {worst} (WR={stats['win_rate']:.1%}, "
                    f"{stats['trade_count']} trades, avg PnL={stats['avg_pnl']:.4f})"
                )

        # --- Signal combination learnings ---
        if top_combos:
            best_combo = top_combos[0]
            if best_combo.get("win_rate", 0) > 0.6:
                learnings.append(
                    f"Top signal combo: {best_combo['combo']} — "
                    f"{best_combo['win_rate']:.0%} WR over {best_combo['trade_count']} trades"
                )

        # --- Adaptive threshold status ---
        threshold_state = self._adaptive_thresholds.get_state()
        if threshold_state["adjustments_made"] > 0:
            learnings.append(
                f"Adaptive thresholds: confidence={threshold_state['confidence_threshold']:.3f}, "
                f"confluence={threshold_state['confluence_threshold']:.3f} "
                f"(adjusted {threshold_state['adjustments_made']} times)"
            )

        return learnings

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_journal(self, n: int | None = None) -> list[dict[str, Any]]:
        """Return recent journal entries."""
        entries = self._journal[-n:] if n else self._journal
        return [e.to_dict() for e in entries]

    def get_regime_performance(self) -> dict[str, dict[str, Any]]:
        """Return performance stats by regime."""
        return self._regime_tracker.get_all_regime_stats()

    def get_top_signal_combos(self, top_k: int = 10) -> list[dict[str, Any]]:
        """Return top signal combinations by win rate."""
        return self._signal_tracker.get_top_combos(top_k)

    def get_adaptive_thresholds(self) -> dict[str, Any]:
        """Return current adaptive threshold state."""
        return self._adaptive_thresholds.get_state()

    def get_learning_summary(self) -> dict[str, Any]:
        """Return a complete learning summary for monitoring."""
        return {
            "regime_performance": self._regime_tracker.get_all_regime_stats(),
            "regime_strategy_matrix": self._regime_tracker.get_regime_strategy_matrix(),
            "top_signal_combos": self._signal_tracker.get_top_combos(10),
            "worst_signal_combos": self._signal_tracker.get_worst_combos(5),
            "individual_signal_stats": self._signal_tracker.get_individual_signal_stats(),
            "adaptive_thresholds": self._adaptive_thresholds.get_state(),
            "journal_size": len(self._journal),
        }
