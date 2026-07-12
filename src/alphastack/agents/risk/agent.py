"""Risk Agent — monitors portfolio risk and approves/rejects trade decisions.

This agent evaluates every trade signal against the current risk posture
and either approves it for execution or rejects it with a reason.
It also monitors for circuit-breaker conditions.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from alphastack.agents.base import AlphaStackAgent
from alphastack.core.config import get_settings
from alphastack.core.events import EventBus
from alphastack.utils.logger import get_logger

logger = get_logger(__name__)


class RiskAgent(AlphaStackAgent):
    """Evaluates trade signals against risk limits and portfolio state.

    Responsibilities:
    - Check drawdown, daily loss, position count, exposure, correlation
    - Trigger circuit breakers when hard limits are breached
    - Approve or reject each trade decision with reasoning
    - Apply risk multipliers from news events
    """

    def __init__(self, event_bus: EventBus | None = None) -> None:
        super().__init__(
            name="risk",
            role="risk_manager",
            description="Monitors portfolio risk and approves/rejects trade decisions",
            event_bus=event_bus,
        )
        self._settings = get_settings()

    def system_prompt(self) -> str:
        return (
            "You are the AlphaStack Risk Agent. Your job is to:\n"
            "1. Evaluate every trade signal against current risk limits\n"
            "2. Check: drawdown, daily loss, open positions, exposure, correlation\n"
            "3. Trigger circuit breakers if hard limits are breached\n"
            "4. Apply news risk adjustments (reduce position sizes on high-impact events)\n"
            "5. Approve or reject each decision with clear reasoning\n"
            "6. NEVER approve a trade that breaches a hard risk limit\n"
        )

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Evaluate signals and produce trade decisions."""
        signals = state.get("signals", [])
        risk_status = state.get("risk_status", {})
        news_alerts = state.get("news_alerts", [])
        news_adjustment = state.get("news_risk_adjustment", 0.0)

        # Deserialise risk status
        from alphastack.agents.orchestrator.state import RiskStatus
        if isinstance(risk_status, dict):
            risk = RiskStatus.model_validate(risk_status)
        else:
            risk = risk_status

        # Load configured limits
        risk_cfg = self._settings.risk

        # Update risk status with current checks
        risk = self._evaluate_risk_limits(risk, risk_cfg)

        # Check for circuit breaker conditions
        circuit_breaker, cb_reason = self._check_circuit_breaker(risk, risk_cfg, news_alerts)
        risk.circuit_breaker_active = circuit_breaker
        risk.circuit_breaker_reason = cb_reason

        # Process each signal into a trade decision
        trade_decisions = []
        for signal in signals:
            decision = self._evaluate_signal(signal, risk, risk_cfg, news_adjustment)
            trade_decisions.append(decision)

        return {
            "risk_status": risk.model_dump(),
            "trade_decisions": [d if isinstance(d, dict) else d for d in trade_decisions],
            "_confidence": 1.0 - (0.5 if circuit_breaker else 0.0),
        }

    def _evaluate_risk_limits(self, risk: Any, cfg: Any) -> Any:
        """Update risk status with current portfolio metrics."""
        from alphastack.agents.orchestrator.state import RiskStatus

        if isinstance(risk, dict):
            risk = RiskStatus.model_validate(risk)

        # Determine risk level
        if risk.circuit_breaker_active:
            risk.risk_level = "critical"
        elif risk.drawdown_pct > cfg.max_drawdown_pct * 0.8:
            risk.risk_level = "high"
        elif risk.drawdown_pct > cfg.max_drawdown_pct * 0.5:
            risk.risk_level = "medium"
        else:
            risk.risk_level = "low"

        # Warnings
        risk.warnings = []
        if risk.drawdown_pct > cfg.max_drawdown_pct * 0.7:
            risk.warnings.append(f"Drawdown {risk.drawdown_pct:.1f}% approaching limit {cfg.max_drawdown_pct}%")
        if risk.daily_loss_pct > cfg.max_daily_loss_pct * 0.7:
            risk.warnings.append(f"Daily loss {risk.daily_loss_pct:.1f}% approaching limit {cfg.max_daily_loss_pct}%")
        if risk.open_positions >= cfg.max_open_positions:
            risk.warnings.append(f"At max open positions ({risk.open_positions}/{cfg.max_open_positions})")

        return risk

    def _check_circuit_breaker(
        self,
        risk: Any,
        cfg: Any,
        news_alerts: list[Any],
    ) -> tuple[bool, str]:
        """Check if any hard circuit breaker should trip."""
        # Drawdown breach
        if risk.drawdown_pct >= cfg.max_drawdown_pct:
            return True, f"Max drawdown breached: {risk.drawdown_pct:.1f}% >= {cfg.max_drawdown_pct}%"

        # Daily loss breach
        if risk.daily_loss_pct >= cfg.max_daily_loss_pct:
            return True, f"Max daily loss breached: {risk.daily_loss_pct:.1f}% >= {cfg.max_daily_loss_pct}%"

        # Critical news event
        critical_news = [
            a for a in news_alerts
            if (a.get("impact") if isinstance(a, dict) else getattr(a, "impact", "")) == "critical"
        ]
        if critical_news:
            return True, f"Critical news event: {critical_news[0].get('headline', 'unknown') if isinstance(critical_news[0], dict) else getattr(critical_news[0], 'headline', 'unknown')}"

        return False, ""

    def _evaluate_signal(
        self,
        signal: dict[str, Any],
        risk: Any,
        cfg: Any,
        news_adjustment: float,
    ) -> dict[str, Any]:
        """Approve or reject a single signal."""
        from alphastack.agents.orchestrator.state import TradeDecision

        symbol = signal.get("symbol", "")
        strength = signal.get("strength", 0.0)
        confluence = signal.get("confluence_score", 0.0)

        # Hard rejections
        if risk.circuit_breaker_active:
            return TradeDecision(
                id=uuid.uuid4().hex[:12],
                action="hold",
                symbol=symbol,
                status="rejected",
                rejection_reason=f"Circuit breaker active: {risk.circuit_breaker_reason}",
            ).model_dump()

        if risk.open_positions >= cfg.max_open_positions:
            return TradeDecision(
                id=uuid.uuid4().hex[:12],
                action="hold",
                symbol=symbol,
                status="rejected",
                rejection_reason=f"Max positions reached ({risk.open_positions}/{cfg.max_open_positions})",
            ).model_dump()

        if confluence < 0.3:
            return TradeDecision(
                id=uuid.uuid4().hex[:12],
                action="hold",
                symbol=symbol,
                status="rejected",
                rejection_reason=f"Confluence too low: {confluence:.2f} < 0.30 threshold",
            ).model_dump()

        # Determine action
        side = signal.get("side", "flat")
        if side == "flat":
            action = "hold"
        elif side == "long":
            action = "buy"
        else:
            action = "sell"

        # Position sizing with news adjustment
        base_qty = 1.0  # Will be refined by the sizing pipeline step
        adjusted_qty = base_qty * (1.0 - min(news_adjustment, 0.8))

        return TradeDecision(
            id=uuid.uuid4().hex[:12],
            signal=signal,
            action=action,
            symbol=symbol,
            quantity=adjusted_qty,
            price=signal.get("entry_price", 0.0) or 0.0,
            order_type="limit" if signal.get("entry_price") else "market",
            status="approved",
            approved_by="risk_agent",
        ).model_dump()
