"""Human-in-the-Loop (HITL) system for AlphaStack.

Implements progressive autonomy — the system earns more independence
as it demonstrates reliability.

Approval levels:
1. All trades require human approval
2. High-confidence trades auto-execute, others require approval
3. All trades auto-execute, human notified
4. Full autonomy with circuit-breaker safety nets

Escalation rules:
- Unusual market conditions → escalate
- Position size exceeds threshold → escalate
- Multiple consecutive losses → escalate
- New market/instrument → escalate
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums & data classes
# ---------------------------------------------------------------------------


class AutonomyLevel(Enum):
    """Progressive autonomy levels.

    Level 1: Full human oversight — every trade approved
    Level 2: Conditional autonomy — high-confidence auto-execute
    Level 3: Notification only — auto-execute with alerts
    Level 4: Full autonomy — circuit-breaker safety only
    """

    LEVEL_1_SUPERVISED = 1
    LEVEL_2_CONDITIONAL = 2
    LEVEL_3_NOTIFY = 3
    LEVEL_4_AUTONOMOUS = 4


class ApprovalStatus(Enum):
    """Status of an approval request."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMED_OUT = "timed_out"
    AUTO_APPROVED = "auto_approved"
    ESCALATED = "escalated"


class EscalationReason(Enum):
    """Reasons for escalating to human oversight."""

    LOW_CONFIDENCE = "low_confidence"
    LARGE_POSITION = "large_position"
    CONSECUTIVE_LOSSES = "consecutive_losses"
    NEW_INSTRUMENT = "new_instrument"
    UNUSUAL_CONDITIONS = "unusual_conditions"
    RISK_LIMIT = "risk_limit"
    MANUAL_OVERRIDE = "manual_override"
    SYSTEM_ERROR = "system_error"


@dataclass
class ApprovalRequest:
    """A request for human approval of a trade action.

    Attributes
    ----------
    request_id : str
        Unique request identifier.
    trade_action : dict
        The proposed trade action (symbol, direction, size, etc.).
    reasoning : str
        Agent's reasoning for this trade.
    confidence : float
        Agent's confidence in this trade (0-1).
    escalation_reason : EscalationReason | None
        If escalated, why.
    autonomy_level : AutonomyLevel
        Current autonomy level.
    timeout_seconds : float
        How long to wait for approval.
    auto_approve_eligible : bool
        Whether this can be auto-approved at current autonomy level.
    """

    request_id: str
    trade_action: dict[str, Any]
    reasoning: str
    confidence: float
    escalation_reason: EscalationReason | None = None
    autonomy_level: AutonomyLevel = AutonomyLevel.LEVEL_1_SUPERVISED
    timeout_seconds: float = 300.0
    auto_approve_eligible: bool = False
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: float = 0.0
    resolved_at: float = 0.0
    human_response: str = ""


@dataclass
class EscalationRule:
    """Rule for when to escalate to human oversight.

    Attributes
    ----------
    name : str
        Rule name.
    condition : str
        Description of when this rule triggers.
    reason : EscalationReason
        Why this triggers escalation.
    min_autonomy_level : AutonomyLevel
        Minimum autonomy level where this rule still applies.
    """

    name: str
    condition: str
    reason: EscalationReason
    min_autonomy_level: AutonomyLevel = AutonomyLevel.LEVEL_4_AUTONOMOUS


@dataclass
class HITLState:
    """Current state of the HITL system."""

    autonomy_level: AutonomyLevel = AutonomyLevel.LEVEL_1_SUPERVISED
    total_requests: int = 0
    approved: int = 0
    rejected: int = 0
    auto_approved: int = 0
    timed_out: int = 0
    consecutive_losses: int = 0
    consecutive_wins: int = 0
    total_trades_at_level: int = 0
    approval_rate_at_level: float = 0.0
    pending_requests: list[ApprovalRequest] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Human-in-the-Loop
# ---------------------------------------------------------------------------


class HumanInTheLoop:
    """Human-in-the-Loop approval and escalation system.

    Manages progressive autonomy — the system earns more independence
    as it demonstrates reliability.

    Usage
    -----
    ```python
    hitl = HumanInTheLoop(initial_level=AutonomyLevel.LEVEL_2_CONDITIONAL)

    # Before executing a trade
    request = hitl.create_request(trade_action, reasoning, confidence)

    if request.status == ApprovalStatus.AUTO_APPROVED:
        execute_trade(trade_action)
    else:
        notify_human(request)
        wait_for_approval(request)
    ```
    """

    # Default escalation rules
    DEFAULT_RULES = [
        EscalationRule(
            name="low_confidence",
            condition="Trade confidence below 0.6",
            reason=EscalationReason.LOW_CONFIDENCE,
            min_autonomy_level=AutonomyLevel.LEVEL_3_NOTIFY,
        ),
        EscalationRule(
            name="large_position",
            condition="Position size exceeds 5% of portfolio",
            reason=EscalationReason.LARGE_POSITION,
            min_autonomy_level=AutonomyLevel.LEVEL_4_AUTONOMOUS,
        ),
        EscalationRule(
            name="consecutive_losses",
            condition="3 or more consecutive losing trades",
            reason=EscalationReason.CONSECUTIVE_LOSSES,
            min_autonomy_level=AutonomyLevel.LEVEL_3_NOTIFY,
        ),
        EscalationRule(
            name="new_instrument",
            condition="Trading an instrument not traded in last 30 days",
            reason=EscalationReason.NEW_INSTRUMENT,
            min_autonomy_level=AutonomyLevel.LEVEL_2_CONDITIONAL,
        ),
        EscalationRule(
            name="unusual_conditions",
            condition="VIX > 30 or spread > 3x normal",
            reason=EscalationReason.UNUSUAL_CONDITIONS,
            min_autonomy_level=AutonomyLevel.LEVEL_2_CONDITIONAL,
        ),
    ]

    # Autonomy promotion thresholds
    PROMOTION_THRESHOLDS = {
        AutonomyLevel.LEVEL_1_SUPERVISED: {
            "min_trades": 50,
            "min_approval_rate": 0.9,
            "max_consecutive_losses": 5,
        },
        AutonomyLevel.LEVEL_2_CONDITIONAL: {
            "min_trades": 200,
            "min_approval_rate": 0.85,
            "max_consecutive_losses": 4,
        },
        AutonomyLevel.LEVEL_3_NOTIFY: {
            "min_trades": 500,
            "min_approval_rate": 0.8,
            "max_consecutive_losses": 3,
        },
    }

    def __init__(
        self,
        initial_level: AutonomyLevel = AutonomyLevel.LEVEL_1_SUPERVISED,
        confidence_auto_approve: float = 0.8,
        position_size_auto_approve: float = 0.02,
        escalation_rules: list[EscalationRule] | None = None,
        approval_callback: Callable[..., Awaitable[ApprovalStatus]] | None = None,
    ) -> None:
        self.state = HITLState(autonomy_level=initial_level)
        self.confidence_auto_approve = confidence_auto_approve
        self.position_size_auto_approve = position_size_auto_approve
        self.rules = escalation_rules or list(self.DEFAULT_RULES)
        self.approval_callback = approval_callback

    def create_request(
        self,
        trade_action: dict[str, Any],
        reasoning: str,
        confidence: float,
        timeout_seconds: float = 300.0,
    ) -> ApprovalRequest:
        """Create an approval request for a trade.

        Parameters
        ----------
        trade_action : dict
            The proposed trade (symbol, direction, size, etc.).
        reasoning : str
            Why this trade should be executed.
        confidence : float
            Agent's confidence (0-1).
        timeout_seconds : float
            How long to wait for human approval.

        Returns
        -------
        ApprovalRequest
            The request with its current status.
        """
        request_id = f"req_{int(time.time() * 1000)}"
        self.state.total_requests += 1

        # Check escalation rules
        escalation = self._check_escalation_rules(trade_action, confidence)

        # Determine auto-approve eligibility
        auto_eligible = self._is_auto_approve_eligible(
            trade_action, confidence, escalation
        )

        request = ApprovalRequest(
            request_id=request_id,
            trade_action=trade_action,
            reasoning=reasoning,
            confidence=confidence,
            escalation_reason=escalation,
            autonomy_level=self.state.autonomy_level,
            timeout_seconds=timeout_seconds,
            auto_approve_eligible=auto_eligible,
            created_at=time.time(),
        )

        # Auto-approve if eligible
        if auto_eligible:
            request.status = ApprovalStatus.AUTO_APPROVED
            request.resolved_at = time.time()
            self.state.auto_approved += 1
            self.state.approved += 1
            logger.info("Auto-approved trade %s (confidence=%.2f)", request_id, confidence)
        elif escalation:
            request.status = ApprovalStatus.ESCALATED
            self.state.pending_requests.append(request)
            logger.info(
                "Escalated trade %s: %s", request_id, escalation.value
            )
        else:
            self.state.pending_requests.append(request)
            logger.info("Approval request %s pending human review", request_id)

        return request

    async def resolve_request(
        self,
        request_id: str,
        approved: bool,
        human_response: str = "",
    ) -> ApprovalRequest | None:
        """Resolve a pending approval request.

        Parameters
        ----------
        request_id : str
            The request to resolve.
        approved : bool
            Whether the human approved the trade.
        human_response : str
            Optional human feedback.

        Returns
        -------
        ApprovalRequest | None
            The resolved request, or None if not found.
        """
        for req in self.state.pending_requests:
            if req.request_id == request_id:
                req.status = (
                    ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
                )
                req.resolved_at = time.time()
                req.human_response = human_response
                self.state.pending_requests.remove(req)

                if approved:
                    self.state.approved += 1
                else:
                    self.state.rejected += 1

                self.state.total_trades_at_level += 1
                self._update_approval_rate()
                self._check_promotion()

                logger.info(
                    "Request %s %s by human",
                    request_id,
                    "approved" if approved else "rejected",
                )
                return req

        logger.warning("Request %s not found in pending queue", request_id)
        return None

    def record_trade_outcome(self, pnl: float) -> None:
        """Record a trade outcome for autonomy tracking.

        Parameters
        ----------
        pnl : float
            Realized P&L.
        """
        if pnl > 0:
            self.state.consecutive_wins += 1
            self.state.consecutive_losses = 0
        elif pnl < 0:
            self.state.consecutive_losses += 1
            self.state.consecutive_wins = 0

        # Check if demotion is needed
        self._check_demotion()

    def get_status(self) -> dict[str, Any]:
        """Get current HITL system status."""
        return {
            "autonomy_level": self.state.autonomy_level.value,
            "autonomy_name": self.state.autonomy_level.name,
            "total_requests": self.state.total_requests,
            "approved": self.state.approved,
            "rejected": self.state.rejected,
            "auto_approved": self.state.auto_approved,
            "pending": len(self.state.pending_requests),
            "consecutive_losses": self.state.consecutive_losses,
            "approval_rate": self.state.approval_rate_at_level,
            "trades_at_level": self.state.total_trades_at_level,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _check_escalation_rules(
        self,
        trade_action: dict[str, Any],
        confidence: float,
    ) -> EscalationReason | None:
        """Check if any escalation rules are triggered."""
        level = self.state.autonomy_level

        for rule in self.rules:
            # Skip rules that don't apply at current autonomy level
            if level.value >= rule.min_autonomy_level.value:
                continue

            # Check conditions
            if rule.reason == EscalationReason.LOW_CONFIDENCE:
                if confidence < 0.6:
                    return rule.reason

            elif rule.reason == EscalationReason.LARGE_POSITION:
                size = trade_action.get("position_size", 0)
                if size > self.position_size_auto_approve * 2.5:
                    return rule.reason

            elif rule.reason == EscalationReason.CONSECUTIVE_LOSSES:
                if self.state.consecutive_losses >= 3:
                    return rule.reason

            elif rule.reason == EscalationReason.UNUSUAL_CONDITIONS:
                if trade_action.get("vix", 0) > 30:
                    return rule.reason

        return None

    def _is_auto_approve_eligible(
        self,
        trade_action: dict[str, Any],
        confidence: float,
        escalation: EscalationReason | None,
    ) -> bool:
        """Check if a trade can be auto-approved."""
        if escalation:
            return False

        level = self.state.autonomy_level

        if level == AutonomyLevel.LEVEL_1_SUPERVISED:
            return False

        if level == AutonomyLevel.LEVEL_2_CONDITIONAL:
            size = trade_action.get("position_size", 0)
            return (
                confidence >= self.confidence_auto_approve
                and size <= self.position_size_auto_approve
            )

        if level in (AutonomyLevel.LEVEL_3_NOTIFY, AutonomyLevel.LEVEL_4_AUTONOMOUS):
            return True

        return False

    def _update_approval_rate(self) -> None:
        """Update approval rate at current level."""
        total = self.state.total_trades_at_level
        if total > 0:
            self.state.approval_rate_at_level = self.state.approved / total

    def _check_promotion(self) -> None:
        """Check if the system should be promoted to a higher autonomy level."""
        level = self.state.autonomy_level
        thresholds = self.PROMOTION_THRESHOLDS.get(level)

        if not thresholds:
            return  # Already at max level

        trades = self.state.total_trades_at_level
        rate = self.state.approval_rate_at_level

        if (
            trades >= thresholds["min_trades"]
            and rate >= thresholds["min_approval_rate"]
            and self.state.consecutive_losses <= thresholds["max_consecutive_losses"]
        ):
            new_level = AutonomyLevel(level.value + 1)
            logger.info(
                "Promoting autonomy: %s → %s (trades=%d, rate=%.2f)",
                level.name,
                new_level.name,
                trades,
                rate,
            )
            self.state.autonomy_level = new_level
            self.state.total_trades_at_level = 0
            self.state.approval_rate_at_level = 0.0

    def _check_demotion(self) -> None:
        """Check if the system should be demoted due to poor performance."""
        level = self.state.autonomy_level

        if level == AutonomyLevel.LEVEL_1_SUPERVISED:
            return  # Already at minimum

        # Demote on excessive consecutive losses
        loss_thresholds = {
            AutonomyLevel.LEVEL_2_CONDITIONAL: 5,
            AutonomyLevel.LEVEL_3_NOTIFY: 4,
            AutonomyLevel.LEVEL_4_AUTONOMOUS: 3,
        }

        threshold = loss_thresholds.get(level, 3)
        if self.state.consecutive_losses >= threshold:
            new_level = AutonomyLevel(level.value - 1)
            logger.warning(
                "Demoting autonomy: %s → %s (consecutive_losses=%d)",
                level.name,
                new_level.name,
                self.state.consecutive_losses,
            )
            self.state.autonomy_level = new_level
            self.state.total_trades_at_level = 0
            self.state.approval_rate_at_level = 0.0
