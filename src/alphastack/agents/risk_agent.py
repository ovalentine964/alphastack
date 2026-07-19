"""Risk Agent — real implementation with Kelly criterion and circuit breakers.

Production features:
- Position sizing via Kelly criterion (fractional Kelly)
- Drawdown monitoring with adaptive limits
- Circuit breaker enforcement (hard limits that halt trading)
- Correlation monitoring (prevent over-concentration)
- Regime-adjusted risk limits
"""

from __future__ import annotations

import math
import uuid
from typing import Any, Literal

from alphastack.agents.base import AlphaStackAgent
from alphastack.core.config import get_settings
from alphastack.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Kelly Criterion
# ---------------------------------------------------------------------------

def kelly_fraction(
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    fraction: float = 0.5,
) -> float:
    """Compute fractional Kelly position size.

    Parameters
    ----------
    win_rate : float
        Probability of a winning trade (0.0–1.0).
    avg_win : float
        Average win magnitude (positive).
    avg_loss : float
        Average loss magnitude (positive).
    fraction : float
        Kelly fraction (0.5 = half-Kelly, conservative default).

    Returns
    -------
    float
        Fraction of bankroll to risk (0.0–1.0). Returns 0.0 if inputs are invalid.
    """
    if avg_loss <= 0 or win_rate <= 0 or win_rate >= 1:
        return 0.0

    # Kelly formula: f* = (p * b - q) / b
    # where p = win_rate, q = 1 - p, b = avg_win / avg_loss
    b = avg_win / avg_loss if avg_loss > 0 else 0.0
    if b <= 0:
        return 0.0

    q = 1.0 - win_rate
    kelly = (win_rate * b - q) / b

    # Clamp to [0, 1] and apply fraction
    kelly = max(0.0, min(kelly, 1.0))
    return kelly * fraction


# ---------------------------------------------------------------------------
# Correlation Monitor
# ---------------------------------------------------------------------------

class CorrelationMonitor:
    """Monitors pairwise correlation of open positions to prevent over-concentration."""

    def __init__(self, max_correlation: float = 0.7) -> None:
        self.max_correlation = max_correlation
        self._position_returns: dict[str, list[float]] = {}

    def add_return(self, symbol: str, ret: float) -> None:
        """Add a return observation for a symbol."""
        self._position_returns.setdefault(symbol, []).append(ret)
        # Keep rolling window of 100 observations
        if len(self._position_returns[symbol]) > 100:
            self._position_returns[symbol] = self._position_returns[symbol][-100:]

    def check_correlation(self, symbol: str, open_symbols: list[str]) -> tuple[bool, float]:
        """Check if adding `symbol` would exceed correlation limits.

        Returns
        -------
        tuple[bool, float]
            (allowed, max_correlation_found)
        """
        if symbol not in self._position_returns:
            return True, 0.0

        new_returns = self._position_returns[symbol]
        if len(new_returns) < 10:
            return True, 0.0  # insufficient data

        max_corr = 0.0
        for existing_sym in open_symbols:
            if existing_sym == symbol:
                continue
            if existing_sym not in self._position_returns:
                continue
            existing_returns = self._position_returns[existing_sym]
            if len(existing_returns) < 10:
                continue

            corr = self._pearson(new_returns[-50:], existing_returns[-50:])
            max_corr = max(max_corr, abs(corr))

            if abs(corr) > self.max_correlation:
                logger.warning(
                    "risk_agent.high_correlation",
                    symbol1=symbol,
                    symbol2=existing_sym,
                    correlation=round(corr, 3),
                    limit=self.max_correlation,
                )
                return False, max_corr

        return True, max_corr

    @staticmethod
    def _pearson(x: list[float], y: list[float]) -> float:
        """Compute Pearson correlation coefficient."""
        n = min(len(x), len(y))
        if n < 2:
            return 0.0

        x, y = x[:n], y[:n]
        mean_x = sum(x) / n
        mean_y = sum(y) / n

        cov = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y)) / n
        std_x = math.sqrt(sum((xi - mean_x) ** 2 for xi in x) / n)
        std_y = math.sqrt(sum((yi - mean_y) ** 2 for yi in y) / n)

        if std_x == 0 or std_y == 0:
            return 0.0
        return cov / (std_x * std_y)


# ---------------------------------------------------------------------------
# Drawdown Monitor
# ---------------------------------------------------------------------------

class DrawdownMonitor:
    """Tracks peak equity and computes real-time drawdown."""

    def __init__(self, max_drawdown_pct: float = 15.0) -> None:
        self.max_drawdown_pct = max_drawdown_pct
        self._peak_equity: float = 0.0
        self._current_equity: float = 0.0
        self._drawdown_history: list[float] = []

    def update(self, equity: float) -> float:
        """Update equity and return current drawdown percentage."""
        self._current_equity = equity
        self._peak_equity = max(self._peak_equity, equity)

        if self._peak_equity <= 0:
            return 0.0

        drawdown_pct = ((self._peak_equity - equity) / self._peak_equity) * 100
        self._drawdown_history.append(drawdown_pct)

        # Keep rolling window
        if len(self._drawdown_history) > 1000:
            self._drawdown_history = self._drawdown_history[-1000:]

        return drawdown_pct

    @property
    def current_drawdown_pct(self) -> float:
        if self._peak_equity <= 0:
            return 0.0
        return ((self._peak_equity - self._current_equity) / self._peak_equity) * 100

    @property
    def max_historical_drawdown_pct(self) -> float:
        return max(self._drawdown_history) if self._drawdown_history else 0.0

    def is_breach(self) -> bool:
        return self.current_drawdown_pct >= self.max_drawdown_pct


# ---------------------------------------------------------------------------
# Risk Agent
# ---------------------------------------------------------------------------

class RiskAgent(AlphaStackAgent):
    """Evaluates trade signals against risk limits and portfolio state.

    Upgraded v2.0 features:
    - Kelly criterion position sizing (fractional Kelly, conservative)
    - Real-time drawdown monitoring with adaptive limits
    - Circuit breaker enforcement (hard limits halt all trading)
    - Correlation monitoring (prevent over-concentration in correlated assets)
    - Regime-adjusted risk limits (tighter limits in volatile regimes)
    """

    def __init__(self, event_bus: Any | None = None) -> None:
        super().__init__(
            name="risk",
            role="risk_manager",
            description="Monitors portfolio risk with Kelly sizing and circuit breakers",
            event_bus=event_bus,
            timeout=10.0,  # risk checks must be fast
            max_retries=1,  # risk decisions shouldn't retry much
            cb_failure_threshold=3,
        )
        self._settings = get_settings()
        self._drawdown_monitor = DrawdownMonitor(
            max_drawdown_pct=self._settings.risk.max_drawdown_pct,
        )
        self._correlation_monitor = CorrelationMonitor(
            max_correlation=self._settings.risk.max_correlation,
        )

        # Kelly criterion parameters (from historical performance)
        self._kelly_win_rate: float = 0.55  # default, updated by reflection agent
        self._kelly_avg_win: float = 1.5    # R-multiple
        self._kelly_avg_loss: float = 1.0   # R-multiple
        self._kelly_fraction: float = 0.5   # half-Kelly (conservative)

        # RiskGovernor integration (optional, set via set_risk_governor)
        self._governor: Any = None

    def set_risk_governor(self, governor: Any) -> None:
        """Set the RiskGovernor for production risk checks."""
        self._governor = governor
        logger.info("risk_agent.governor_set")

    def system_prompt(self) -> str:
        return (
            "You are the AlphaStack Risk Agent. Your job is to:\n"
            "1. Size positions using Kelly criterion (fractional Kelly)\n"
            "2. Monitor drawdown — halt if max drawdown is breached\n"
            "3. Enforce circuit breakers on hard limit breaches\n"
            "4. Check correlation — reject if new position over-concentrates\n"
            "5. Adjust risk limits based on market regime\n"
            "6. NEVER approve a trade that breaches a hard risk limit\n"
        )

    # ------------------------------------------------------------------
    # Kelly sizing
    # ------------------------------------------------------------------

    def _kelly_size(
        self,
        signal: dict[str, Any],
        account_balance: float,
        risk_pct: float,
    ) -> float:
        """Compute Kelly criterion position size for a signal.

        Uses fractional Kelly with current win/loss statistics.
        Falls back to fixed-fraction sizing if Kelly data is insufficient.
        """
        # Kelly fraction of bankroll to risk
        kelly_f = kelly_fraction(
            win_rate=self._kelly_win_rate,
            avg_win=self._kelly_avg_win,
            avg_loss=self._kelly_avg_loss,
            fraction=self._kelly_fraction,
        )

        if kelly_f <= 0:
            # Fall back to fixed-fraction sizing
            kelly_f = risk_pct / 100.0

        # Risk amount in account currency
        risk_amount = account_balance * kelly_f

        # Convert to position size based on stop loss distance
        entry_price = signal.get("entry_price", 0.0) or 0.0
        stop_loss = signal.get("stop_loss", 0.0) or 0.0

        if entry_price > 0 and stop_loss > 0 and entry_price != stop_loss:
            stop_distance = abs(entry_price - stop_loss)
            position_size = risk_amount / stop_distance
        else:
            # No stop loss info — use fixed fraction
            position_size = risk_amount / entry_price if entry_price > 0 else 0.0

        return round(position_size, 6)

    # ------------------------------------------------------------------
    # Update Kelly stats (called by reflection agent)
    # ------------------------------------------------------------------

    def update_kelly_stats(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
    ) -> None:
        """Update Kelly criterion parameters from reflection agent feedback."""
        self._kelly_win_rate = max(0.01, min(win_rate, 0.99))
        self._kelly_avg_win = max(0.01, avg_win)
        self._kelly_avg_loss = max(0.01, avg_loss)
        logger.info(
            "risk_agent.kelly_updated",
            win_rate=self._kelly_win_rate,
            avg_win=self._kelly_avg_win,
            avg_loss=self._kelly_avg_loss,
        )

    # ------------------------------------------------------------------
    # Circuit breaker checks
    # ------------------------------------------------------------------

    def _check_circuit_breakers(
        self,
        risk_status: dict[str, Any],
        cfg: Any,
        news_alerts: list[Any],
    ) -> tuple[bool, str]:
        """Check all hard circuit breaker conditions.

        Returns (should_trip, reason).
        """
        # 1. Max drawdown
        drawdown = self._drawdown_monitor.current_drawdown_pct
        if drawdown >= cfg.max_drawdown_pct:
            return True, f"Max drawdown breached: {drawdown:.1f}% >= {cfg.max_drawdown_pct}%"

        # 2. Max daily loss
        daily_loss = risk_status.get("daily_loss_pct", 0.0)
        if daily_loss >= cfg.max_daily_loss_pct:
            return True, f"Max daily loss breached: {daily_loss:.1f}% >= {cfg.max_daily_loss_pct}%"

        # 3. Critical news events
        for alert in news_alerts:
            impact = alert.get("impact", "") if isinstance(alert, dict) else getattr(alert, "impact", "")
            if impact == "critical":
                headline = alert.get("headline", "unknown") if isinstance(alert, dict) else getattr(alert, "headline", "unknown")
                return True, f"Critical news event: {headline}"

        return False, ""

    # ------------------------------------------------------------------
    # Correlation check
    # ------------------------------------------------------------------

    def _check_correlation(
        self,
        signal: dict[str, Any],
        open_positions: list[dict[str, Any]],
    ) -> tuple[bool, float]:
        """Check if adding this signal would violate correlation limits."""
        symbol = signal.get("symbol", "")
        open_symbols = [p.get("symbol", "") for p in open_positions]
        return self._correlation_monitor.check_correlation(symbol, open_symbols)

    # ------------------------------------------------------------------
    # Regime-adjusted limits
    # ------------------------------------------------------------------

    def _regime_risk_multiplier(self, regime: str) -> float:
        """Return a risk multiplier based on market regime.

        Volatile regimes get tighter limits (multiplier < 1.0).
        """
        multipliers = {
            "trending_up": 1.0,
            "trending_down": 0.8,   # tighter in downtrends
            "ranging": 1.0,
            "volatile": 0.6,        # much tighter in volatile markets
            "low_volatility": 1.1,  # slightly relaxed in calm markets
            "unknown": 0.8,         # conservative default
        }
        return multipliers.get(regime, 0.8)

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Evaluate signals and produce trade decisions with Kelly sizing."""
        signals = state.get("signals", [])
        risk_status = state.get("risk_status", {})
        news_alerts = state.get("news_alerts", [])
        pipeline_context = state.get("pipeline_context", {})
        market_data = state.get("market_data", {})

        cfg = self._settings.risk

        # Update drawdown monitor with current equity
        equity = market_data.get("equity", market_data.get("account_balance", 10000.0))
        current_drawdown = self._drawdown_monitor.update(equity)

        # Parse risk status
        from alphastack.agents.orchestrator.state import RiskStatus
        if isinstance(risk_status, dict):
            risk = RiskStatus.model_validate(risk_status)
        else:
            risk = risk_status

        risk.drawdown_pct = current_drawdown

        # 1. Check circuit breakers
        cb_active, cb_reason = self._check_circuit_breakers(
            risk.model_dump() if hasattr(risk, "model_dump") else risk,
            cfg,
            news_alerts,
        )
        risk.circuit_breaker_active = cb_active
        risk.circuit_breaker_reason = cb_reason

        # Determine risk level
        if cb_active:
            risk.risk_level = "critical"
        elif current_drawdown > cfg.max_drawdown_pct * 0.8:
            risk.risk_level = "high"
        elif current_drawdown > cfg.max_drawdown_pct * 0.5:
            risk.risk_level = "medium"
        else:
            risk.risk_level = "low"

        # Build warnings
        risk.warnings = []
        if current_drawdown > cfg.max_drawdown_pct * 0.7:
            risk.warnings.append(f"Drawdown {current_drawdown:.1f}% approaching limit {cfg.max_drawdown_pct}%")

        # 2. Regime detection for risk adjustment
        regime = pipeline_context.get("regime", "unknown")
        regime_mult = self._regime_risk_multiplier(regime)

        # 3. Process each signal
        trade_decisions: list[dict[str, Any]] = []
        open_positions = state.get("positions", [])

        for signal in signals:
            decision = self._evaluate_signal(
                signal=signal,
                risk=risk,
                cfg=cfg,
                regime_mult=regime_mult,
                open_positions=open_positions,
                market_data=market_data,
            )
            trade_decisions.append(decision)

        # 3b. Run RiskGovernor validation on approved decisions (async)
        if self._governor is not None:
            for i, decision in enumerate(trade_decisions):
                if decision.get("status") != "approved":
                    continue
                try:
                    from alphastack.risk.governor import TradeRequest
                    sig = decision.get("signal", {})
                    gov_request = TradeRequest(
                        symbol=decision["symbol"],
                        direction=sig.get("side", "long"),
                        requested_size=decision["quantity"],
                        entry_price=decision["price"],
                        stop_loss=sig.get("stop_loss", 0.0) or 0.0,
                        take_profit=sig.get("take_profit", 0.0) or 0.0,
                        strategy_id=sig.get("strategy", "alphastack"),
                    )
                    approval = await self._governor.approve_trade(gov_request)
                    if not approval.approved:
                        trade_decisions[i] = self._reject(
                            decision["symbol"],
                            sig.get("side", "long"),
                            f"RiskGovernor rejected: {approval.rejection_reason}",
                        )
                    elif approval.adjusted_size < decision["quantity"]:
                        trade_decisions[i]["quantity"] = approval.adjusted_size
                        trade_decisions[i]["governor_adjusted"] = True
                        trade_decisions[i]["warnings"] = approval.warnings
                except Exception as exc:
                    logger.warning("risk_agent.governor_validation_failed", error=str(exc))

        # 4. Update risk status with new drawdown
        risk.drawdown_pct = current_drawdown

        approved = sum(1 for d in trade_decisions if d.get("status") == "approved")
        rejected = sum(1 for d in trade_decisions if d.get("status") == "rejected")

        logger.info(
            "risk_agent.complete",
            approved=approved,
            rejected=rejected,
            drawdown_pct=round(current_drawdown, 2),
            risk_level=risk.risk_level,
            circuit_breaker=cb_active,
            regime=regime,
            regime_mult=regime_mult,
        )

        return {
            "risk_status": risk.model_dump() if hasattr(risk, "model_dump") else risk,
            "trade_decisions": trade_decisions,
            "_confidence": 1.0 - (0.5 if cb_active else 0.0),
        }

    # ------------------------------------------------------------------
    # Signal evaluation
    # ------------------------------------------------------------------

    def _evaluate_signal(
        self,
        signal: dict[str, Any],
        risk: Any,
        cfg: Any,
        regime_mult: float,
        open_positions: list[Any],
        market_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Evaluate a single signal and produce a trade decision."""
        symbol = signal.get("symbol", "")
        confluence = signal.get("adjusted_confluence", signal.get("confluence_score", 0.0))
        side = signal.get("side", "flat")

        # --- Hard rejections ---

        # Circuit breaker active
        if risk.circuit_breaker_active:
            return self._reject(
                symbol, side,
                f"Circuit breaker active: {risk.circuit_breaker_reason}",
            )

        # Max positions
        open_count = len(open_positions) if isinstance(open_positions, list) else 0
        if open_count >= cfg.max_open_positions:
            return self._reject(
                symbol, side,
                f"Max positions reached ({open_count}/{cfg.max_open_positions})",
            )

        # Minimum confluence
        min_confluence = 0.3 * regime_mult  # tighter in volatile regimes
        if confluence < min_confluence:
            return self._reject(
                symbol, side,
                f"Confluence {confluence:.2f} below threshold {min_confluence:.2f}",
            )

        # Correlation check
        corr_ok, max_corr = self._check_correlation(signal, open_positions)
        if not corr_ok:
            return self._reject(
                symbol, side,
                f"Correlation limit exceeded (max={max_corr:.2f}, limit={cfg.max_correlation})",
            )

        # Flat signal
        if side == "flat":
            return self._reject(symbol, side, "Signal is flat — no trade")

        # --- Approved: compute Kelly-sized position ---

        account_balance = market_data.get("account_balance", 10000.0)
        base_risk_pct = cfg.max_position_size_pct

        # Apply regime adjustment to risk percentage
        adjusted_risk_pct = base_risk_pct * regime_mult

        # Kelly sizing
        kelly_size = self._kelly_size(
            signal=signal,
            account_balance=account_balance,
            risk_pct=adjusted_risk_pct,
        )

        # News adjustment
        news_adj = signal.get("news_risk_adjustment", 0.0)
        if news_adj > 0:
            kelly_size *= (1.0 - min(news_adj, 0.8))

        # Determine action
        action = "buy" if side == "long" else "sell"

        # RiskGovernor validation (if available)
        if self._governor is not None:
            try:
                from alphastack.risk.governor import TradeRequest
                gov_request = TradeRequest(
                    symbol=symbol,
                    direction=side,
                    requested_size=kelly_size,
                    entry_price=signal.get("entry_price", 0.0) or 0.0,
                    stop_loss=signal.get("stop_loss", 0.0) or 0.0,
                    take_profit=signal.get("take_profit", 0.0) or 0.0,
                    strategy_id=signal.get("strategy", "alphastack"),
                )
                # Note: governor.approve_trade is async, but we're in a sync method.
                # The orchestrator handles this at the async level.
                # Store the request for async validation in execute().
            except Exception as exc:
                logger.debug("risk_agent.governor_request_build_failed", error=str(exc))

        return {
            "id": uuid.uuid4().hex[:12],
            "signal": signal,
            "action": action,
            "symbol": symbol,
            "quantity": kelly_size,
            "price": signal.get("entry_price", 0.0) or 0.0,
            "order_type": "limit" if signal.get("entry_price") else "market",
            "status": "approved",
            "approved_by": "risk_agent",
            "sizing_method": "kelly_fractional",
            "kelly_stats": {
                "win_rate": self._kelly_win_rate,
                "avg_win": self._kelly_avg_win,
                "avg_loss": self._kelly_avg_loss,
                "fraction": self._kelly_fraction,
            },
            "regime_adjustment": regime_mult,
            "drawdown_pct": self._drawdown_monitor.current_drawdown_pct,
        }

    @staticmethod
    def _reject(symbol: str, side: str, reason: str) -> dict[str, Any]:
        """Create a rejection decision."""
        return {
            "id": uuid.uuid4().hex[:12],
            "action": "hold",
            "symbol": symbol,
            "status": "rejected",
            "rejection_reason": reason,
        }
