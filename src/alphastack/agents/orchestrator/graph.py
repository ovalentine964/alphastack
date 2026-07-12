"""LangGraph-based multi-agent orchestrator for AlphaStack.

The orchestrator builds a StateGraph with five specialised agent nodes
(strategy, risk, news, execution, reflection) wired together with
conditional edges and human-in-the-loop checkpoints.

Flow
----
    ┌──────────┐
    │  START   │
    └────┬─────┘
         ▼
    ┌──────────┐
    │  news    │  ← detect high-impact events first
    └────┬─────┘
         ▼
    ┌──────────┐
    │ strategy │  ← run the 16-step pipeline
    └────┬─────┘
         ▼
    ┌──────────┐
    │   risk   │  ← approve / reject signals
    └────┬─────┘
         │
         ├── signals approved ──▶ ┌───────────┐
         │                        │ execution │
         │                        └─────┬─────┘
         │                              ▼
         │                        ┌───────────┐
         │                        │ reflection│
         │                        └─────┬─────┘
         │                              │
         └── signals rejected ──────────┴──▶ END
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from alphastack.agents.execution.agent import ExecutionAgent
from alphastack.agents.news.agent import NewsAgent
from alphastack.agents.orchestrator.state import AlphaStackState
from alphastack.agents.reflection.agent import ReflectionAgent
from alphastack.agents.risk.agent import RiskAgent
from alphastack.agents.strategy.agent import StrategyAgent
from alphastack.core.events import EventBus
from alphastack.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# State type alias — LangGraph works with dicts; we serialise through Pydantic
# ---------------------------------------------------------------------------

def _state_to_dict(state: AlphaStackState) -> dict[str, Any]:
    """Convert Pydantic state to a plain dict for LangGraph."""
    return state.model_dump(mode="json")


def _state_from_dict(d: dict[str, Any]) -> AlphaStackState:
    """Reconstruct Pydantic state from a LangGraph dict."""
    return AlphaStackState.model_validate(d)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class AlphaStackOrchestrator:
    """Builds and runs the LangGraph state machine.

    Parameters
    ----------
    event_bus : EventBus | None
        Shared event bus for publishing agent events.
    checkpointer : BaseCheckpointSaver | None
        LangGraph checkpointer for state persistence (e.g. Redis).
    human_in_the_loop : bool
        If True, inserts a human approval checkpoint before execution.
    """

    def __init__(
        self,
        event_bus: EventBus | None = None,
        checkpointer: BaseCheckpointSaver | None = None,
        human_in_the_loop: bool = True,
    ) -> None:
        self.event_bus = event_bus
        self.checkpointer = checkpointer
        self.human_in_the_loop = human_in_the_loop

        # Instantiate agents
        self.strategy_agent = StrategyAgent(event_bus=event_bus)
        self.risk_agent = RiskAgent(event_bus=event_bus)
        self.news_agent = NewsAgent(event_bus=event_bus)
        self.execution_agent = ExecutionAgent(event_bus=event_bus)
        self.reflection_agent = ReflectionAgent(event_bus=event_bus)

        # Build the graph
        self._graph = self._build_graph()

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------

    def _build_graph(self) -> Any:
        """Construct the LangGraph StateGraph."""
        graph = StateGraph(AlphaStackState)

        # Register nodes
        graph.add_node("news", self._news_node)
        graph.add_node("strategy", self._strategy_node)
        graph.add_node("risk", self._risk_node)
        graph.add_node("execution", self._execution_node)
        graph.add_node("reflection", self._reflection_node)
        graph.add_node("human_review", self._human_review_node)

        # Entry point: news first (detect events before analysing)
        graph.set_entry_point("news")

        # news → strategy
        graph.add_edge("news", "strategy")

        # strategy → risk
        graph.add_edge("strategy", "risk")

        # risk → conditional: approve → execution, reject → end
        graph.add_conditional_edges(
            "risk",
            self._route_after_risk,
            {
                "execute": "human_review" if self.human_in_the_loop else "execution",
                "end": END,
            },
        )

        # human review → conditional: approve → execution, reject → end
        graph.add_conditional_edges(
            "human_review",
            self._route_after_human,
            {
                "execute": "execution",
                "reject": END,
            },
        )

        # execution → reflection → end
        graph.add_edge("execution", "reflection")
        graph.add_edge("reflection", END)

        # Compile
        compile_kwargs: dict[str, Any] = {}
        if self.checkpointer:
            compile_kwargs["checkpointer"] = self.checkpointer

        return graph.compile(**compile_kwargs)

    # ------------------------------------------------------------------
    # Node implementations
    # ------------------------------------------------------------------

    async def _news_node(self, state: dict[str, Any]) -> dict[str, Any]:
        """News agent: detect high-impact events and adjust risk."""
        logger.info("orchestrator.node", node="news")
        s = _state_from_dict(state)
        s.current_node = "news"

        result = await self.news_agent.run(s.model_dump())

        # Merge news agent output back
        s.news_alerts = result.get("news_alerts", s.news_alerts)
        s.news_risk_adjustment = result.get("news_risk_adjustment", s.news_risk_adjustment)
        s.add_agent_message("news", f"Detected {len(s.news_alerts)} alerts, risk adj: {s.news_risk_adjustment}x")

        out = _state_to_dict(s)
        out["current_node"] = "news"
        return out

    async def _strategy_node(self, state: dict[str, Any]) -> dict[str, Any]:
        """Strategy agent: run the 16-step pipeline and generate signals."""
        logger.info("orchestrator.node", node="strategy")
        s = _state_from_dict(state)
        s.current_node = "strategy"

        result = await self.strategy_agent.run(s.model_dump())

        s.signals = result.get("signals", s.signals)
        s.pipeline_context = result.get("pipeline_context", s.pipeline_context)
        s.add_agent_message(
            "strategy",
            f"Generated {len(s.signals)} signals",
        )

        out = _state_to_dict(s)
        out["current_node"] = "strategy"
        return out

    async def _risk_node(self, state: dict[str, Any]) -> dict[str, Any]:
        """Risk agent: evaluate signals and approve/reject trades."""
        logger.info("orchestrator.node", node="risk")
        s = _state_from_dict(state)
        s.current_node = "risk"

        result = await self.risk_agent.run(s.model_dump())

        s.risk_status = result.get("risk_status", s.risk_status)
        s.trade_decisions = result.get("trade_decisions", s.trade_decisions)

        approved = sum(1 for d in s.trade_decisions if d.status == "approved")
        rejected = sum(1 for d in s.trade_decisions if d.status == "rejected")
        s.add_agent_message(
            "risk",
            f"Approved {approved}, rejected {rejected} decisions. "
            f"Risk level: {s.risk_status.risk_level}",
        )

        out = _state_to_dict(s)
        out["current_node"] = "risk"
        return out

    async def _execution_node(self, state: dict[str, Any]) -> dict[str, Any]:
        """Execution agent: route approved decisions to brokers."""
        logger.info("orchestrator.node", node="execution")
        s = _state_from_dict(state)
        s.current_node = "execution"

        result = await self.execution_agent.run(s.model_dump())

        s.execution_log = result.get("execution_log", s.execution_log)
        s.pending_orders = result.get("pending_orders", s.pending_orders)

        executed = len([e for e in s.execution_log if e.get("status") == "filled"])
        s.add_agent_message("execution", f"Executed {executed} orders")

        out = _state_to_dict(s)
        out["current_node"] = "execution"
        return out

    async def _reflection_node(self, state: dict[str, Any]) -> dict[str, Any]:
        """Reflection agent: post-trade analysis and learning."""
        logger.info("orchestrator.node", node="reflection")
        s = _state_from_dict(state)
        s.current_node = "reflection"

        result = await self.reflection_agent.run(s.model_dump())

        s.performance_summary = result.get("performance_summary", s.performance_summary)
        s.strategy_adjustments = result.get("strategy_adjustments", s.strategy_adjustments)
        s.add_agent_message("reflection", "Post-trade analysis complete")

        out = _state_to_dict(s)
        out["current_node"] = "reflection"
        return out

    async def _human_review_node(self, state: dict[str, Any]) -> dict[str, Any]:
        """Human-in-the-loop checkpoint: pause and wait for approval."""
        logger.info("orchestrator.node", node="human_review")
        s = _state_from_dict(state)
        s.current_node = "human_review"

        # Build a summary for the human
        summary_lines = ["## Trade Review Required\n"]
        for i, decision in enumerate(s.trade_decisions, 1):
            if decision.status == "approved":
                summary_lines.append(
                    f"{i}. **{decision.action.upper()} {decision.symbol}** "
                    f"— qty={decision.quantity}, price={decision.price}, "
                    f"type={decision.order_type}"
                )
        summary_lines.append(f"\nRisk level: {s.risk_status.risk_level}")
        if s.news_alerts:
            summary_lines.append(f"Active news alerts: {len(s.news_alerts)}")

        summary = "\n".join(summary_lines)

        # Use LangGraph interrupt to pause for human input
        human_response = interrupt(summary)

        # Process human feedback
        if isinstance(human_response, str):
            feedback_lower = human_response.strip().lower()
            if feedback_lower in ("approve", "yes", "ok", "go", "proceed"):
                s.human_feedback = "approved"
                s.add_agent_message("human", "Human approved trade decisions")
            else:
                # Reject all pending decisions
                for decision in s.trade_decisions:
                    if decision.status == "approved":
                        decision.status = "rejected"
                        decision.rejection_reason = f"Human rejected: {human_response}"
                s.human_feedback = "rejected"
                s.add_agent_message("human", f"Human rejected: {human_response}")
        else:
            s.human_feedback = "approved"

        out = _state_to_dict(s)
        out["current_node"] = "human_review"
        return out

    # ------------------------------------------------------------------
    # Routing functions
    # ------------------------------------------------------------------

    def _route_after_risk(self, state: dict[str, Any]) -> Literal["execute", "end"]:
        """Decide whether to proceed to execution or end."""
        s = _state_from_dict(state)

        # Check circuit breaker
        if s.risk_status.circuit_breaker_active:
            logger.warning("orchestrator.circuit_breaker", reason=s.risk_status.circuit_breaker_reason)
            return "end"

        # Check if any decisions were approved
        has_approved = any(d.status == "approved" for d in s.trade_decisions)
        if not has_approved:
            logger.info("orchestrator.no_approved_decisions")
            return "end"

        return "execute"

    def _route_after_human(self, state: dict[str, Any]) -> Literal["execute", "reject"]:
        """Route based on human feedback."""
        s = _state_from_dict(state)
        if s.human_feedback == "approved":
            return "execute"
        return "reject"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(
        self,
        market_data: dict[str, Any],
        symbol: str = "BTC/USDT",
        timeframe: str = "1h",
        thread_id: str | None = None,
    ) -> AlphaStackState:
        """Execute the full orchestrator pipeline.

        Parameters
        ----------
        market_data : dict
            Market data to feed into the pipeline.
        symbol : str
            Primary symbol to analyse.
        timeframe : str
            Analysis timeframe.
        thread_id : str | None
            Thread ID for checkpoint persistence. Auto-generated if None.

        Returns
        -------
        AlphaStackState
            The final state after all agents have run.
        """
        run_id = uuid.uuid4().hex[:12]
        thread_id = thread_id or run_id

        initial_state = AlphaStackState(
            run_id=run_id,
            market_data=market_data,
            current_symbol=symbol,
            current_timeframe=timeframe,
            started_at=datetime.utcnow(),
        )

        logger.info(
            "orchestrator.run.start",
            run_id=run_id,
            symbol=symbol,
            timeframe=timeframe,
        )

        config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}

        # Invoke the graph
        final_state_dict = await self._graph.ainvoke(
            _state_to_dict(initial_state),
            config=config,
        )

        final_state = _state_from_dict(final_state_dict)
        logger.info("orchestrator.run.complete", run_id=run_id)
        return final_state

    async def stream(
        self,
        market_data: dict[str, Any],
        symbol: str = "BTC/USDT",
        timeframe: str = "1h",
        thread_id: str | None = None,
    ):
        """Stream node-by-node execution for real-time updates.

        Yields ``(node_name, state_dict)`` tuples as each node completes.
        """
        run_id = uuid.uuid4().hex[:12]
        thread_id = thread_id or run_id

        initial_state = AlphaStackState(
            run_id=run_id,
            market_data=market_data,
            current_symbol=symbol,
            current_timeframe=timeframe,
            started_at=datetime.utcnow(),
        )

        config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}

        async for event in self._graph.astream(
            _state_to_dict(initial_state),
            config=config,
        ):
            for node_name, node_output in event.items():
                yield node_name, node_output

    @property
    def graph(self):
        """Expose the compiled graph for visualisation / debugging."""
        return self._graph
