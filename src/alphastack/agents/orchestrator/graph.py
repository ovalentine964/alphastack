"""LangGraph-based multi-agent orchestrator for AlphaStack — v2.0.

Upgraded architecture:
- Parallel execution where possible (fan-out/fan-in)
- Conditional routing with regime awareness
- HITL (Human-in-the-Loop) gates for high-risk decisions
- Per-node timeout enforcement via base agent
- Circuit breaker integration
- Health monitoring and trace capture

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
    ┌──────────┐         ┌──────────┐
    │ strategy │────────▶│  debate  │  (can run in parallel with risk prep)
    └────┬─────┘         └────┬─────┘
         │                    │
         └────────┬───────────┘
                  ▼
            ┌──────────┐
            │   risk   │  ← Kelly sizing, circuit breakers, correlation
            └────┬─────┘
                 │
                 ├── REJECT ──────────────────────────▶ END
                 │
                 ▼
            ┌──────────┐
            │   HITL   │  ← human approval (conditional)
            └────┬─────┘
                 │
                 ├── REJECT ──────────────────────────▶ END
                 │
                 ▼
            ┌──────────┐
            │execution │  ← TWAP/VWAP, slippage tracking
            └────┬─────┘
                 ▼
            ┌──────────┐
            │reflection│  ← journal, performance, Kelly update
            └────┬─────┘
                 ▼
               END
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

try:
    from langgraph.graph import END, StateGraph
    from langgraph.types import interrupt
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    class _Stub:
        def __getattr__(self, name: str) -> Any:
            raise ImportError(f"langgraph not available: {name}")
    StateGraph = _Stub()  # type: ignore[assignment,misc]
    END = "__end__"  # type: ignore[assignment,misc]
    interrupt = None  # type: ignore[assignment,misc]

from alphastack.agents.debate.debate_engine import DebateEngine
from alphastack.agents.debate.risk_arbiter import DebateVerdict
from alphastack.agents.execution.agent import ExecutionAgent
from alphastack.agents.news.agent import NewsAgent
from alphastack.agents.orchestrator.state import AlphaStackState
from alphastack.agents.reflection.agent import ReflectionAgent
from alphastack.agents.risk.agent import RiskAgent
from alphastack.agents.strategy.agent import StrategyAgent
from alphastack.agents.base import CircuitBreaker
from alphastack.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# State helpers
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
    """Builds and runs the LangGraph state machine — v2.0.

    Parameters
    ----------
    event_bus : EventBus | None
        Shared event bus for publishing agent events.
    checkpointer : BaseCheckpointSaver | None
        LangGraph checkpointer for state persistence.
    human_in_the_loop : bool
        If True, inserts a human approval checkpoint before execution.
    hitl_threshold : float
        Minimum confluence score to require HITL approval.
        Signals below this threshold are auto-approved (still risk-checked).
    """

    def __init__(
        self,
        event_bus: Any | None = None,
        checkpointer: Any | None = None,
        human_in_the_loop: bool = True,
        hitl_threshold: float = 0.6,
    ) -> None:
        self.event_bus = event_bus
        self.checkpointer = checkpointer
        self.human_in_the_loop = human_in_the_loop
        self.hitl_threshold = hitl_threshold

        # Instantiate agents (with production features from v2.0 base)
        self.strategy_agent = StrategyAgent(event_bus=event_bus)
        self.debate_engine = DebateEngine()
        self.risk_agent = RiskAgent(event_bus=event_bus)
        self.news_agent = NewsAgent(event_bus=event_bus)
        self.execution_agent = ExecutionAgent(event_bus=event_bus)
        self.reflection_agent = ReflectionAgent(event_bus=event_bus)

        # Orchestrator-level circuit breaker
        self.orchestrator_cb = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=120.0,
            name="orchestrator",
        )

        # Build the graph
        self._graph = self._build_graph()

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------

    def _build_graph(self) -> Any:
        """Construct the LangGraph StateGraph with parallel and conditional edges."""
        graph = StateGraph(AlphaStackState)

        # Register nodes
        graph.add_node("news", self._news_node)
        graph.add_node("strategy", self._strategy_node)
        graph.add_node("debate", self._debate_node)
        graph.add_node("risk", self._risk_node)
        graph.add_node("execution", self._execution_node)
        graph.add_node("reflection", self._reflection_node)

        # Conditional HITL node (only added if human_in_the_loop is True)
        if self.human_in_the_loop:
            graph.add_node("human_review", self._human_review_node)

        # Entry point: news first
        graph.set_entry_point("news")

        # news → strategy
        graph.add_edge("news", "strategy")

        # strategy → debate
        graph.add_edge("strategy", "debate")

        # debate → conditional: proceed to risk or end
        graph.add_conditional_edges(
            "debate",
            self._route_after_debate,
            {
                "proceed": "risk",
                "end": END,
            },
        )

        # risk → conditional: approve → HITL (or execution), reject → end
        if self.human_in_the_loop:
            graph.add_conditional_edges(
                "risk",
                self._route_after_risk,
                {
                    "execute": "human_review",
                    "end": END,
                },
            )
            # human review → conditional
            graph.add_conditional_edges(
                "human_review",
                self._route_after_human,
                {
                    "execute": "execution",
                    "reject": END,
                },
            )
        else:
            graph.add_conditional_edges(
                "risk",
                self._route_after_risk,
                {
                    "execute": "execution",
                    "end": END,
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
        """News agent: detect high-impact events."""
        logger.info("orchestrator.node", node="news")
        s = _state_from_dict(state)
        s.current_node = "news"

        result = await self.news_agent.run(s.model_dump())

        s.news_alerts = result.get("news_alerts", s.news_alerts)
        s.news_risk_adjustment = result.get("news_risk_adjustment", s.news_risk_adjustment)
        s.add_agent_message("news", f"Detected {len(s.news_alerts)} alerts, risk adj: {s.news_risk_adjustment}x")

        out = _state_to_dict(s)
        out["current_node"] = "news"
        return out

    async def _strategy_node(self, state: dict[str, Any]) -> dict[str, Any]:
        """Strategy agent: run pipeline with regime-aware signal generation."""
        logger.info("orchestrator.node", node="strategy")
        s = _state_from_dict(state)
        s.current_node = "strategy"

        result = await self.strategy_agent.run(s.model_dump())

        s.signals = result.get("signals", s.signals)
        s.pipeline_context = result.get("pipeline_context", s.pipeline_context)
        regime = s.pipeline_context.get("regime", "unknown")
        s.add_agent_message(
            "strategy",
            f"Generated {len(s.signals)} signals (regime: {regime})",
        )

        out = _state_to_dict(s)
        out["current_node"] = "strategy"
        return out

    async def _debate_node(self, state: dict[str, Any]) -> dict[str, Any]:
        """Debate node: bull/bear/risk-arbiter consensus."""
        logger.info("orchestrator.node", node="debate")
        s = _state_from_dict(state)
        s.current_node = "debate"

        if not s.signals:
            s.add_agent_message("debate", "No signals to debate — skipping")
            out = _state_to_dict(s)
            out["current_node"] = "debate"
            return out

        debate_results: list[dict[str, Any]] = []
        surviving_signals = []

        for signal in s.signals:
            sig_dict = signal if isinstance(signal, dict) else signal.model_dump()
            indicators = s.pipeline_context.get("indicators", {})
            news_sentiment = s.pipeline_context.get("news_sentiment")
            risk_context = {
                "drawdown_pct": s.risk_status.drawdown_pct,
                "daily_loss_pct": s.risk_status.daily_loss_pct,
                "open_positions": s.risk_status.open_positions,
                "max_positions": s.risk_status.max_positions,
            }

            result = self.debate_engine.debate(
                signal=sig_dict,
                market_data=s.market_data,
                indicators=indicators,
                news_sentiment=news_sentiment,
                risk_context=risk_context,
            )

            debate_results.append(result.to_dict())

            if result.verdict == DebateVerdict.REJECT:
                s.add_agent_message(
                    "debate",
                    f"REJECTED {sig_dict.get('side', '?')} {sig_dict.get('symbol', '?')}: {result.reasoning}",
                    message_type="warning",
                )
            elif result.verdict == DebateVerdict.MODIFY:
                if result.modified_signal:
                    if result.modified_signal.get("quantity") is not None:
                        if isinstance(signal, dict):
                            signal["quantity"] = result.modified_signal["quantity"]
                        else:
                            signal.quantity = result.modified_signal["quantity"]
                surviving_signals.append(signal)
            else:
                surviving_signals.append(signal)

        s.signals = surviving_signals
        s.pipeline_context["debate_results"] = debate_results

        approved = sum(1 for r in debate_results if r["verdict"] == "execute")
        rejected = sum(1 for r in debate_results if r["verdict"] == "reject")
        modified = sum(1 for r in debate_results if r["verdict"] == "modify")
        s.add_agent_message(
            "debate",
            f"Debate: {approved} approved, {rejected} rejected, {modified} modified",
        )

        out = _state_to_dict(s)
        out["current_node"] = "debate"
        return out

    async def _risk_node(self, state: dict[str, Any]) -> dict[str, Any]:
        """Risk agent: Kelly sizing, circuit breakers, correlation checks."""
        logger.info("orchestrator.node", node="risk")
        s = _state_from_dict(state)
        s.current_node = "risk"

        result = await self.risk_agent.run(s.model_dump())

        s.risk_status = result.get("risk_status", s.risk_status)
        s.trade_decisions = result.get("trade_decisions", s.trade_decisions)

        approved = sum(
            1 for d in s.trade_decisions
            if (d.get("status") if isinstance(d, dict) else getattr(d, "status", "")) == "approved"
        )
        rejected = sum(
            1 for d in s.trade_decisions
            if (d.get("status") if isinstance(d, dict) else getattr(d, "status", "")) == "rejected"
        )

        # Extract regime info
        regime = s.pipeline_context.get("regime", "unknown")
        s.add_agent_message(
            "risk",
            f"Approved {approved}, rejected {rejected}. Risk: {s.risk_status.risk_level}, Regime: {regime}",
        )

        out = _state_to_dict(s)
        out["current_node"] = "risk"
        return out

    async def _execution_node(self, state: dict[str, Any]) -> dict[str, Any]:
        """Execution agent: TWAP/VWAP, slippage tracking."""
        logger.info("orchestrator.node", node="execution")
        s = _state_from_dict(state)
        s.current_node = "execution"

        result = await self.execution_agent.run(s.model_dump())

        s.execution_log = result.get("execution_log", s.execution_log)
        s.pending_orders = result.get("pending_orders", s.pending_orders)

        slippage_stats = result.get("slippage_stats", {})
        executed = len([e for e in s.execution_log if e.get("status") == "filled"])
        s.add_agent_message(
            "execution",
            f"Executed {executed} orders. Slippage: {slippage_stats.get('mean_bps', 0):.1f} bps avg",
        )

        out = _state_to_dict(s)
        out["current_node"] = "execution"
        return out

    async def _reflection_node(self, state: dict[str, Any]) -> dict[str, Any]:
        """Reflection agent: journal, performance, Kelly update, suggestions."""
        logger.info("orchestrator.node", node="reflection")
        s = _state_from_dict(state)
        s.current_node = "reflection"

        result = await self.reflection_agent.run(s.model_dump())

        s.performance_summary = result.get("performance_summary", s.performance_summary)
        s.strategy_adjustments = result.get("strategy_adjustments", s.strategy_adjustments)

        # Push Kelly stats back to Risk Agent for next cycle
        kelly_update = s.performance_summary.get("kelly_update", {})
        if kelly_update:
            self.risk_agent.update_kelly_stats(
                win_rate=kelly_update.get("win_rate", 0.55),
                avg_win=kelly_update.get("avg_win", 1.5),
                avg_loss=kelly_update.get("avg_loss", 1.0),
            )

        learnings = s.performance_summary.get("learnings", [])
        suggestions = len(s.strategy_adjustments)
        s.add_agent_message(
            "reflection",
            f"Analysis complete. {len(learnings)} learnings, {suggestions} suggestions. "
            f"Win rate: {s.performance_summary.get('win_rate', 0):.1%}",
        )

        out = _state_to_dict(s)
        out["current_node"] = "reflection"
        return out

    async def _human_review_node(self, state: dict[str, Any]) -> dict[str, Any]:
        """Human-in-the-loop checkpoint: pause and wait for approval."""
        logger.info("orchestrator.node", node="human_review")
        s = _state_from_dict(state)
        s.current_node = "human_review"

        # Check if any signal exceeds HITL threshold
        needs_hitl = any(
            (d.get("status") if isinstance(d, dict) else getattr(d, "status", "")) == "approved"
            and (
                (d.get("signal", {}) or {}).get("adjusted_confluence", 0) >= self.hitl_threshold
                if isinstance(d, dict)
                else getattr(d, "signal", None) is not None
            )
            for d in s.trade_decisions
        )

        if not needs_hitl:
            # Low-risk trades — auto-approve
            s.human_feedback = "auto_approved"
            s.add_agent_message("human", "Auto-approved (below HITL threshold)")
            out = _state_to_dict(s)
            out["current_node"] = "human_review"
            return out

        # Build summary for human review
        summary_lines = ["## Trade Review Required\n"]
        for i, decision in enumerate(s.trade_decisions, 1):
            status = decision.get("status") if isinstance(decision, dict) else getattr(decision, "status", "")
            if status == "approved":
                sym = decision.get("symbol", "") if isinstance(decision, dict) else getattr(decision, "symbol", "")
                act = decision.get("action", "") if isinstance(decision, dict) else getattr(decision, "action", "")
                qty = decision.get("quantity", 0) if isinstance(decision, dict) else getattr(decision, "quantity", 0)
                px = decision.get("price", 0) if isinstance(decision, dict) else getattr(decision, "price", 0)
                summary_lines.append(f"{i}. **{act.upper()} {sym}** — qty={qty}, price={px}")

        summary_lines.append(f"\nRisk level: {s.risk_status.risk_level}")
        summary_lines.append(f"Regime: {s.pipeline_context.get('regime', 'unknown')}")
        if s.news_alerts:
            summary_lines.append(f"Active news alerts: {len(s.news_alerts)}")

        summary = "\n".join(summary_lines)

        # Use LangGraph interrupt
        try:
            if interrupt is not None:
                human_response = interrupt(summary)
            else:
                human_response = None
        except Exception:
            logger.warning("orchestrator.human_review.error", exc_info=True)
            human_response = None

        # Process response (fail-closed)
        if isinstance(human_response, str):
            feedback_lower = human_response.strip().lower()
            if feedback_lower in ("approve", "yes", "ok", "go", "proceed"):
                s.human_feedback = "approved"
                s.add_agent_message("human", "Human approved trade decisions")
            else:
                for d in s.trade_decisions:
                    status = d.get("status") if isinstance(d, dict) else getattr(d, "status", "")
                    if status == "approved":
                        if isinstance(d, dict):
                            d["status"] = "rejected"
                            d["rejection_reason"] = f"Human rejected: {human_response}"
                        else:
                            d.status = "rejected"
                            d.rejection_reason = f"Human rejected: {human_response}"
                s.human_feedback = "rejected"
                s.add_agent_message("human", f"Human rejected: {human_response}")
        else:
            # Fail-closed
            for d in s.trade_decisions:
                status = d.get("status") if isinstance(d, dict) else getattr(d, "status", "")
                if status == "approved":
                    if isinstance(d, dict):
                        d["status"] = "rejected"
                        d["rejection_reason"] = "Human review timed out or invalid response"
                    else:
                        d.status = "rejected"
                        d.rejection_reason = "Human review timed out or invalid response"
            s.human_feedback = "rejected"
            s.add_agent_message("human", "Human review timeout/invalid — rejecting all trades")

        out = _state_to_dict(s)
        out["current_node"] = "human_review"
        return out

    # ------------------------------------------------------------------
    # Routing functions
    # ------------------------------------------------------------------

    def _route_after_debate(self, state: dict[str, Any]) -> Literal["proceed", "end"]:
        """Route after debate: proceed if any signals survived."""
        s = _state_from_dict(state)
        if not s.signals:
            logger.info("orchestrator.debate.all_rejected")
            return "end"
        return "proceed"

    def _route_after_risk(self, state: dict[str, Any]) -> Literal["execute", "end"]:
        """Route after risk: execute if any approved decisions."""
        s = _state_from_dict(state)

        # Circuit breaker check
        if s.risk_status.circuit_breaker_active:
            logger.warning("orchestrator.circuit_breaker", reason=s.risk_status.circuit_breaker_reason)
            return "end"

        # Check for approved decisions
        has_approved = any(
            (d.get("status") if isinstance(d, dict) else getattr(d, "status", "")) == "approved"
            for d in s.trade_decisions
        )
        if not has_approved:
            logger.info("orchestrator.no_approved_decisions")
            return "end"

        return "execute"

    def _route_after_human(self, state: dict[str, Any]) -> Literal["execute", "reject"]:
        """Route based on human feedback."""
        s = _state_from_dict(state)
        if s.human_feedback in ("approved", "auto_approved"):
            return "execute"
        return "reject"

    # ------------------------------------------------------------------
    # Health monitoring
    # ------------------------------------------------------------------

    def get_health(self) -> dict[str, Any]:
        """Return health status of all agents."""
        return {
            "orchestrator": {
                "circuit_breaker": self.orchestrator_cb.as_dict(),
                "human_in_the_loop": self.human_in_the_loop,
                "hitl_threshold": self.hitl_threshold,
            },
            "news": self.news_agent.get_health(),
            "strategy": self.strategy_agent.get_health(),
            "risk": self.risk_agent.get_health(),
            "execution": self.execution_agent.get_health(),
            "reflection": self.reflection_agent.get_health(),
        }

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
            Thread ID for checkpoint persistence.

        Returns
        -------
        AlphaStackState
            The final state after all agents have run.
        """
        # Check orchestrator-level circuit breaker
        if not self.orchestrator_cb.allow_request():
            logger.error("orchestrator.circuit_breaker_open")
            state = AlphaStackState(
                run_id=uuid.uuid4().hex[:12],
                market_data=market_data,
                current_symbol=symbol,
                current_timeframe=timeframe,
                started_at=datetime.now(timezone.utc),
                error="Orchestrator circuit breaker is open",
            )
            return state

        run_id = uuid.uuid4().hex[:12]
        thread_id = thread_id or run_id

        initial_state = AlphaStackState(
            run_id=run_id,
            market_data=market_data,
            current_symbol=symbol,
            current_timeframe=timeframe,
            started_at=datetime.now(timezone.utc),
        )

        logger.info(
            "orchestrator.run.start",
            run_id=run_id,
            symbol=symbol,
            timeframe=timeframe,
            human_in_the_loop=self.human_in_the_loop,
        )

        config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}

        try:
            final_state_dict = await self._graph.ainvoke(
                _state_to_dict(initial_state),
                config=config,
            )
            final_state = _state_from_dict(final_state_dict)
            self.orchestrator_cb.record_success()
            logger.info("orchestrator.run.complete", run_id=run_id)
            return final_state

        except Exception as exc:
            self.orchestrator_cb.record_failure()
            logger.error("orchestrator.run.failed", run_id=run_id, error=str(exc), exc_info=True)
            initial_state.error = str(exc)
            return initial_state

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
            started_at=datetime.now(timezone.utc),
        )

        config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}

        async for event in self._graph.astream(
            _state_to_dict(initial_state),
            config=config,
        ):
            for node_name, node_output in event.items():
                yield node_name, node_output

    @property
    def graph(self) -> Any:
        """Expose the compiled graph for visualisation / debugging."""
        return self._graph
