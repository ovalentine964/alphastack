"""Shared state definition for the AlphaStack multi-agent orchestrator."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field
from langgraph.graph import add_messages


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class Signal(BaseModel):
    """A trade signal produced by the strategy agent."""

    symbol: str
    side: Literal["long", "short", "flat"] = "flat"
    strength: float = 0.0  # -1.0 … 1.0
    confluence_score: float = 0.0  # 0.0 … 1.0
    timeframe: str = ""
    strategy: str = "alphastack"
    reasoning: str = ""
    stop_loss: float | None = None
    take_profit: float | None = None
    entry_price: float | None = None


class TradeDecision(BaseModel):
    """A trade decision awaiting approval or execution."""

    id: str = ""
    signal: Signal | None = None
    action: Literal["buy", "sell", "hold", "close"] = "hold"
    symbol: str = ""
    quantity: float = 0.0
    price: float = 0.0
    order_type: Literal["market", "limit", "stop"] = "market"
    status: Literal["pending", "approved", "rejected", "executed", "failed"] = "pending"
    approved_by: str = ""
    rejection_reason: str = ""
    broker: str = ""


class RiskStatus(BaseModel):
    """Snapshot of current portfolio risk."""

    drawdown_pct: float = 0.0
    daily_loss_pct: float = 0.0
    open_positions: int = 0
    max_positions: int = 10
    exposure_pct: float = 0.0
    correlation_risk: float = 0.0
    circuit_breaker_active: bool = False
    circuit_breaker_reason: str = ""
    risk_level: Literal["low", "medium", "high", "critical"] = "low"
    warnings: list[str] = Field(default_factory=list)


class NewsAlert(BaseModel):
    """A high-impact news event detected by the news agent."""

    id: str = ""
    headline: str = ""
    source: str = ""
    impact: Literal["low", "medium", "high", "critical"] = "medium"
    event_type: str = ""  # "NFP", "CPI", "FOMC", "earnings", etc.
    affected_symbols: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    recommendation: str = ""


class AgentMessage(BaseModel):
    """Inter-agent communication message."""

    from_agent: str
    to_agent: str = "all"
    content: str = ""
    message_type: Literal["info", "warning", "action", "question", "response"] = "info"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Main orchestrator state (LangGraph TypedDict)
# ---------------------------------------------------------------------------

class AlphaStackState(BaseModel):
    """Shared state across all agents in the orchestrator graph.

    This is the single source of truth that flows through every node
    in the LangGraph state machine.  Each agent reads from and writes
    to the fields relevant to its role.
    """

    # -- Messages (LangGraph convention) ------------------------------------
    messages: Annotated[list[Any], add_messages] = Field(default_factory=list)

    # -- Market data --------------------------------------------------------
    market_data: dict[str, Any] = Field(default_factory=dict)
    """Latest OHLCV, order book, tick data keyed by symbol/timeframe."""

    current_symbol: str = ""
    current_timeframe: str = "1h"

    # -- Pipeline context ---------------------------------------------------
    pipeline_context: dict[str, Any] = Field(default_factory=dict)
    """Output of the 16-step strategy pipeline."""

    # -- Signals & decisions ------------------------------------------------
    signals: list[Signal] = Field(default_factory=list)
    trade_decisions: list[TradeDecision] = Field(default_factory=list)

    # -- Risk ---------------------------------------------------------------
    risk_status: RiskStatus = Field(default_factory=RiskStatus)

    # -- News ---------------------------------------------------------------
    news_alerts: list[NewsAlert] = Field(default_factory=list)
    news_risk_adjustment: float = 0.0  # multiplier applied on high-impact news

    # -- Execution ----------------------------------------------------------
    execution_log: list[dict[str, Any]] = Field(default_factory=list)
    pending_orders: list[dict[str, Any]] = Field(default_factory=list)

    # -- Reflection ---------------------------------------------------------
    pre_trade_reflection: dict[str, Any] = Field(default_factory=dict)
    """Pre-trade signal reflection verdict.

    Keys: verdict (APPROVE/REJECT/MODIFY), reasoning, confidence,
    signal_verdicts (per-signal detail).
    """

    performance_summary: dict[str, Any] = Field(default_factory=dict)
    strategy_adjustments: list[dict[str, Any]] = Field(default_factory=list)

    # -- Inter-agent communication ------------------------------------------
    agent_messages: list[AgentMessage] = Field(default_factory=list)

    # -- Control flow -------------------------------------------------------
    should_continue: bool = True
    human_approval_required: bool = False
    human_feedback: str = ""
    error: str = ""

    # -- Metadata -----------------------------------------------------------
    run_id: str = ""
    started_at: datetime = Field(default_factory=datetime.utcnow)
    current_node: str = ""

    class Config:
        arbitrary_types_allowed = True

    def add_agent_message(
        self,
        from_agent: str,
        content: str,
        to_agent: str = "all",
        message_type: str = "info",
    ) -> None:
        """Convenience: append an inter-agent message."""
        self.agent_messages.append(
            AgentMessage(
                from_agent=from_agent,
                to_agent=to_agent,
                content=content,
                message_type=message_type,  # type: ignore[arg-type]
            )
        )

    def get_latest_signal(self) -> Signal | None:
        """Return the most recent signal, or None."""
        return self.signals[-1] if self.signals else None

    def is_circuit_breaker_active(self) -> bool:
        """Check if any circuit breaker is currently tripped."""
        return self.risk_status.circuit_breaker_active
