"""Risk Governor — central controller that coordinates all risk checks.

Hard limits, not guidelines. No ML model can override these.
Event-driven: publishes risk events for observability and audit.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from pydantic import BaseModel, Field

from alphastack.core.config import get_settings
from alphastack.risk.circuit_breaker import CircuitBreaker, CircuitBreakerState
from alphastack.risk.correlation import CorrelationMonitor
from alphastack.risk.drawdown import DrawdownManager
from alphastack.risk.exposure import ExposureManager
from alphastack.risk.position_sizer import PositionSizer, SizingRequest, SizingResult
from alphastack.risk.validators import TradeValidator, ValidationResult
from alphastack.utils.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Risk events (published by the governor)
# ---------------------------------------------------------------------------

class RiskEventType(str, Enum):
    """Observable risk events."""
    TRADE_APPROVED = "trade_approved"
    TRADE_REJECTED = "trade_rejected"
    CIRCUIT_BREAKER_TRIGGERED = "circuit_breaker_triggered"
    CIRCUIT_BREAKER_RESET = "circuit_breaker_reset"
    DRAWDOWN_WARNING = "drawdown_warning"
    DRAWDOWN_BREACH = "drawdown_breach"
    EXPOSURE_WARNING = "exposure_warning"
    CORRELATION_WARNING = "correlation_warning"
    POSITION_RESIZED = "position_resized"
    HALT_TRADING = "halt_trading"
    RESUME_TRADING = "resume_trading"


class RiskEvent(BaseModel):
    """Immutable risk event published to subscribers."""
    event_type: RiskEventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    symbol: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    severity: str = "info"  # info | warning | critical


# ---------------------------------------------------------------------------
# Trade request & result
# ---------------------------------------------------------------------------

class TradeRequest(BaseModel):
    """A proposed trade submitted for risk approval."""
    symbol: str
    direction: str  # "long" | "short"
    requested_size: float  # lots / units
    entry_price: float
    stop_loss: float
    take_profit: float = 0.0
    strategy_id: str = ""
    session: str = ""  # london | new_york | asian
    metadata: dict[str, Any] = Field(default_factory=dict)


class TradeApproval(BaseModel):
    """Risk governor's verdict on a proposed trade."""
    approved: bool
    adjusted_size: float = 0.0  # may differ from requested
    rejection_reason: str = ""
    warnings: list[str] = Field(default_factory=list)
    risk_score: float = 0.0  # 0 = minimal risk, 1 = extreme risk


# ---------------------------------------------------------------------------
# Risk Governor
# ---------------------------------------------------------------------------

RiskEventCallback = Callable[[RiskEvent], None]


class RiskGovernor:
    """Central risk controller — the immune system of AlphaStack.

    Coordinates all risk checks before any trade execution.
    All limits are hard; no strategy or model can override them.
    """

    def __init__(
        self,
        account_balance: float = 1000.0,
        on_event: RiskEventCallback | None = None,
    ) -> None:
        settings = get_settings().risk

        self._balance = account_balance
        self._halted = False
        self._halt_reason = ""
        self._event_subscribers: list[RiskEventCallback] = []
        if on_event:
            self._event_subscribers.append(on_event)

        # Sub-systems
        self.position_sizer = PositionSizer(
            account_balance=account_balance,
            max_position_pct=settings.max_position_size_pct,
        )
        self.drawdown_manager = DrawdownManager(
            account_balance=account_balance,
            max_daily_pct=settings.max_daily_loss_pct,
            max_total_pct=settings.max_drawdown_pct,
        )
        self.circuit_breaker = CircuitBreaker(
            max_daily_loss_pct=settings.max_daily_loss_pct,
            max_consecutive_losses=5,
        )
        self.correlation_monitor = CorrelationMonitor(
            max_correlation=settings.max_correlation,
        )
        self.exposure_manager = ExposureManager(
            max_open_positions=settings.max_open_positions,
            max_leverage=settings.max_leverage,
        )
        self.trade_validator = TradeValidator()

        log.info(
            "risk_governor_initialized",
            balance=account_balance,
            max_daily_loss_pct=settings.max_daily_loss_pct,
            max_drawdown_pct=settings.max_drawdown_pct,
            max_positions=settings.max_open_positions,
        )

    # -- Event system -------------------------------------------------------

    def subscribe(self, callback: RiskEventCallback) -> None:
        """Subscribe to risk events."""
        self._event_subscribers.append(callback)

    def _publish(self, event: RiskEvent) -> None:
        """Publish a risk event to all subscribers."""
        log.info(
            "risk_event",
            event_type=event.event_type.value,
            symbol=event.symbol,
            severity=event.severity,
            details=event.details,
        )
        for cb in self._event_subscribers:
            try:
                cb(event)
            except Exception:
                log.warning("event_subscriber_error", exc_info=True)

    # -- Account state ------------------------------------------------------

    @property
    def account_balance(self) -> float:
        return self._balance

    @property
    def is_halted(self) -> bool:
        return self._halted

    @property
    def halt_reason(self) -> str:
        return self._halt_reason

    def update_balance(self, new_balance: float) -> None:
        """Update account balance after a trade settles."""
        self._balance = new_balance
        self.position_sizer.update_balance(new_balance)
        self.drawdown_manager.update_balance(new_balance)

    def record_trade_result(self, pnl: float) -> None:
        """Record a completed trade's P&L across all risk sub-systems."""
        self.drawdown_manager.record_pnl(pnl)
        self.circuit_breaker.record_loss(pnl)
        self.update_balance(self._balance + pnl)

        # Check if circuit breakers tripped
        if self.circuit_breaker.is_tripped:
            self._halted = True
            self._halt_reason = self.circuit_breaker.trip_reason
            self._publish(RiskEvent(
                event_type=RiskEventType.CIRCUIT_BREAKER_TRIGGERED,
                severity="critical",
                details={
                    "reason": self._halt_reason,
                    "daily_pnl": self.circuit_breaker.daily_pnl,
                    "consecutive_losses": self.circuit_breaker.consecutive_losses,
                },
            ))

        # Check drawdown warnings
        dd_state = self.drawdown_manager.state
        if dd_state.total_pct > self.drawdown_manager.max_total_pct * 0.8:
            self._publish(RiskEvent(
                event_type=RiskEventType.DRAWDOWN_WARNING,
                severity="warning",
                details={
                    "daily_pct": dd_state.daily_pct,
                    "total_pct": dd_state.total_pct,
                },
            ))

    # -- Halt / resume ------------------------------------------------------

    def halt(self, reason: str) -> None:
        """Manually halt all trading."""
        self._halted = True
        self._halt_reason = reason
        self._publish(RiskEvent(
            event_type=RiskEventType.HALT_TRADING,
            severity="critical",
            details={"reason": reason},
        ))
        log.warning("trading_halted", reason=reason)

    def resume(self) -> None:
        """Resume trading after halt (circuit breakers must be reset first)."""
        if self.circuit_breaker.is_tripped:
            log.warning("cannot_resume_circuit_breaker_active")
            return
        self._halted = False
        self._halt_reason = ""
        self._publish(RiskEvent(
            event_type=RiskEventType.RESUME_TRADING,
            severity="info",
        ))
        log.info("trading_resumed")

    # -- Core approval flow -------------------------------------------------

    async def approve_trade(self, request: TradeRequest) -> TradeApproval:
        """Full risk approval pipeline. Returns adjusted or rejected trade.

        This is the single entry point for all trade proposals.
        Every check is a hard gate — failure means rejection, not a suggestion.
        """
        warnings: list[str] = []

        # Gate 0: Global halt
        if self._halted:
            return TradeApproval(
                approved=False,
                rejection_reason=f"Trading halted: {self._halt_reason}",
            )

        # Gate 1: Trade sanity validation
        validation = self.trade_validator.validate_pre_trade(request)
        if not validation.valid:
            return TradeApproval(
                approved=False,
                rejection_reason=f"Validation failed: {validation.errors}",
            )

        # Gate 2: Circuit breakers
        if self.circuit_breaker.is_tripped:
            return TradeApproval(
                approved=False,
                rejection_reason=f"Circuit breaker tripped: {self.circuit_breaker.trip_reason}",
            )

        # Gate 3: Drawdown limits
        if self.drawdown_manager.is_breach():
            return TradeApproval(
                approved=False,
                rejection_reason="Drawdown limit breached",
            )

        # Gate 4: Exposure limits
        exposure_ok, exposure_reason = self.exposure_manager.check_add_position(
            symbol=request.symbol,
            direction=request.direction,
            size=request.requested_size,
            price=request.entry_price,
            balance=self._balance,
        )
        if not exposure_ok:
            return TradeApproval(
                approved=False,
                rejection_reason=f"Exposure limit: {exposure_reason}",
            )

        # Gate 5: Correlation check
        corr_ok, corr_reason = self.correlation_monitor.check_correlation(
            symbol=request.symbol,
            direction=request.direction,
        )
        if not corr_ok:
            return TradeApproval(
                approved=False,
                rejection_reason=f"Correlation limit: {corr_reason}",
            )
        if corr_reason:  # warning but still allowed
            warnings.append(corr_reason)

        # Gate 6: Position sizing (may adjust size)
        sizing_result = self.position_sizer.size_position(SizingRequest(
            symbol=request.symbol,
            direction=request.direction,
            entry_price=request.entry_price,
            stop_loss=request.stop_loss,
            account_balance=self._balance,
            daily_drawdown_pct=self.drawdown_manager.state.daily_pct,
        ))
        adjusted_size = min(request.requested_size, sizing_result.max_size)

        if adjusted_size < request.requested_size:
            warnings.append(
                f"Size reduced from {request.requested_size} to {adjusted_size}"
            )
            self._publish(RiskEvent(
                event_type=RiskEventType.POSITION_RESIZED,
                symbol=request.symbol,
                severity="info",
                details={
                    "requested": request.requested_size,
                    "approved": adjusted_size,
                    "reason": "position_sizer_limit",
                },
            ))

        # Gate 7: Minimum viable size
        if adjusted_size < sizing_result.min_size:
            return TradeApproval(
                approved=False,
                rejection_reason=f"Size {adjusted_size} below minimum {sizing_result.min_size}",
            )

        # All gates passed
        risk_score = self._compute_risk_score(request, adjusted_size)
        self._publish(RiskEvent(
            event_type=RiskEventType.TRADE_APPROVED,
            symbol=request.symbol,
            severity="info",
            details={
                "requested_size": request.requested_size,
                "approved_size": adjusted_size,
                "risk_score": risk_score,
            },
        ))

        return TradeApproval(
            approved=True,
            adjusted_size=adjusted_size,
            warnings=warnings,
            risk_score=risk_score,
        )

    def _compute_risk_score(self, request: TradeRequest, size: float) -> float:
        """Compute composite risk score 0..1 for the approved trade."""
        scores: list[float] = []

        # Drawdown proximity
        dd = self.drawdown_manager.state
        dd_score = min(dd.total_pct / self.drawdown_manager.max_total_pct, 1.0)
        scores.append(dd_score)

        # Exposure fraction
        position_value = size * request.entry_price
        exp_score = min(position_value / (self._balance * 10), 1.0)
        scores.append(exp_score)

        # Distance to stop loss (tighter stop = higher risk)
        if request.entry_price > 0:
            sl_pct = abs(request.entry_price - request.stop_loss) / request.entry_price
            sl_score = max(0, 1.0 - sl_pct * 20)  # 5% stop = 0 risk, 0% stop = 1 risk
            scores.append(sl_score)

        return sum(scores) / len(scores) if scores else 0.0

    # -- Status -------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        """Return full risk system status."""
        return {
            "halted": self._halted,
            "halt_reason": self._halt_reason,
            "balance": self._balance,
            "drawdown": self.drawdown_manager.state.model_dump(),
            "circuit_breaker": {
                "tripped": self.circuit_breaker.is_tripped,
                "reason": self.circuit_breaker.trip_reason,
                "daily_pnl": self.circuit_breaker.daily_pnl,
                "consecutive_losses": self.circuit_breaker.consecutive_losses,
            },
            "exposure": self.exposure_manager.status(),
            "correlation": self.correlation_monitor.status(),
        }
