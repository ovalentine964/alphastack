"""LangGraph-based multi-agent orchestrator for AlphaStack.

The orchestrator builds a StateGraph with six specialised agent nodes
(strategy, debate, risk, news, execution, reflection) wired together
with conditional edges and human-in-the-loop checkpoints.

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
    │  debate  │  ← bull/bear/risk-arbiter consensus
    └────┬─────┘
         │
         ├── REJECT ──────────────────────────▶ END
         ├── MODIFY ──▶ modified signal
         │                    │
         └── EXECUTE ─────────┴──▶ ┌──────────┐
                                   │   risk   │  ← approve / reject
                                   └────┬─────┘
                                        │
                                        ├── approved ──▶ ┌───────────┐
                                        │                │ execution │
                                        │                └─────┬─────┘
                                        │                      ▼
                                        │                ┌───────────┐
                                        │                │ reflection│
                                        │                └─────┬─────┘
                                        │                      │
                                        └── rejected ──────────┴──▶ END
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from alphastack.agents.debate.debate_engine import DebateEngine
from alphastack.agents.debate.risk_arbiter import DebateVerdict
from alphastack.agents.execution.agent import ExecutionAgent
from alphastack.agents.news.agent import NewsAgent
from alphastack.agents.orchestrator.state import AlphaStackState
from alphastack.agents.reflection.agent import ReflectionAgent
from alphastack.agents.reflection.post_trade import (
    CorrectionEngine,
    PostTradeReflection,
    SkillCreator,
)
from alphastack.agents.risk.agent import RiskAgent
from alphastack.agi.memory import EpisodicMemory
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
        self.debate_engine = DebateEngine()
        self.risk_agent = RiskAgent(event_bus=event_bus)
        self.news_agent = NewsAgent(event_bus=event_bus)
        self.execution_agent = ExecutionAgent(event_bus=event_bus)
        self.reflection_agent = ReflectionAgent(event_bus=event_bus)

        # Post-trade self-correction loop
        self.post_reflection = PostTradeReflection()
        self.correction_engine = CorrectionEngine()
        self.skill_creator = SkillCreator()
        self.episodic_memory = EpisodicMemory()

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
        graph.add_node("debate", self._debate_node)
        graph.add_node("risk", self._risk_node)
        graph.add_node("execution", self._execution_node)
        graph.add_node("reflection", self._reflection_node)
        graph.add_node("human_review", self._human_review_node)

        # Entry point: news first (detect events before analysing)
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

    async def _debate_node(self, state: dict[str, Any]) -> dict[str, Any]:
        """Debate node: bull/bear/risk-arbiter consensus on each signal."""
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
            sig_dict = signal.model_dump()
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
                    f"REJECTED {signal.side} {signal.symbol}: {result.reasoning}",
                    message_type="warning",
                )
            elif result.verdict == DebateVerdict.MODIFY:
                # Apply modified signal parameters
                if result.modified_signal:
                    if result.modified_signal.get("quantity") is not None:
                        signal.quantity = result.modified_signal["quantity"]
                    s.add_agent_message(
                        "debate",
                        f"MODIFIED {signal.side} {signal.symbol}: {result.reasoning}",
                    )
                surviving_signals.append(signal)
            else:
                s.add_agent_message(
                    "debate",
                    f"APPROVED {signal.side} {signal.symbol}: {result.reasoning}",
                )
                surviving_signals.append(signal)

        s.signals = surviving_signals
        s.pipeline_context["debate_results"] = debate_results

        approved = sum(1 for r in debate_results if r["verdict"] == "execute")
        rejected = sum(1 for r in debate_results if r["verdict"] == "reject")
        modified = sum(1 for r in debate_results if r["verdict"] == "modify")
        s.add_agent_message(
            "debate",
            f"Debate complete: {approved} approved, {rejected} rejected, {modified} modified",
        )

        out = _state_to_dict(s)
        out["current_node"] = "debate"
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
        """Reflection agent: post-trade analysis, self-correction, and skill extraction."""
        logger.info("orchestrator.node", node="reflection")
        s = _state_from_dict(state)
        s.current_node = "reflection"

        # 1. Aggregate performance analysis (existing)
        result = await self.reflection_agent.run(s.model_dump())
        s.performance_summary = result.get("performance_summary", s.performance_summary)
        s.strategy_adjustments = result.get("strategy_adjustments", s.strategy_adjustments)

        # 2. Per-trade self-correction loop
        filled_trades = [e for e in s.execution_log if e.get("status") == "filled"]
        corrections_generated = 0
        skills_created = 0

        for trade_entry in filled_trades:
            trade_data = self._enrich_trade(trade_entry, s)

            # Reflect on individual trade
            chain = self.post_reflection.reflect(trade_data)

            # Generate correction
            correction = self.correction_engine.generate(
                chain, trade_data, current_params=s.pipeline_context,
            )
            if correction:
                corrections_generated += 1

            # Store episode and check for skill creation
            from alphastack.agi.memory import TradeEpisode
            episode = TradeEpisode(
                symbol=trade_data.get("symbol", ""),
                direction=trade_data.get("direction", ""),
                entry_price=trade_data.get("entry_price", 0.0),
                exit_price=trade_data.get("exit_price", 0.0),
                pnl=trade_data.get("pnl", 0.0),
                indicators=trade_data.get("indicators", {}),
                market_context=trade_data.get("market_context", {}),
            )
            episode.finalize()
            episode.lessons.append(f"reflection_chain={chain.chain_id}")
            self.correction_engine.store_lessons(self.episodic_memory, episode)
            self.episodic_memory.store(episode)

            skill = self.skill_creator.record_trade(trade_data, self.episodic_memory)
            if skill and skill.win_count == 5:
                skills_created += 1

        # 3. Apply corrections to pipeline context for next cycle
        if corrections_generated > 0:
            s.pipeline_context = self.correction_engine.apply_corrections(s.pipeline_context)

        s.add_agent_message(
            "reflection",
            f"Post-trade analysis complete. "
            f"Corrections: {corrections_generated}, Skills: {skills_created}, "
            f"Active skills: {sum(1 for sk in self.skill_creator._skills.values() if sk.active)}",
        )

        out = _state_to_dict(s)
        out["current_node"] = "reflection"
        return out

    @staticmethod
    def _enrich_trade(entry: dict[str, Any], state: AlphaStackState) -> dict[str, Any]:
        """Combine execution entry with signal context for reflection."""
        signal = {}
        for sig in state.signals:
            sig_sym = sig.get("symbol", "") if isinstance(sig, dict) else getattr(sig, "symbol", "")
            if sig_sym == entry.get("symbol", ""):
                signal = sig if isinstance(sig, dict) else {
                    "symbol": getattr(sig, "symbol", ""),
                    "side": getattr(sig, "side", "flat"),
                    "strength": getattr(sig, "strength", 0.0),
                    "confluence_score": getattr(sig, "confluence_score", 0.0),
                    "strategy": getattr(sig, "strategy", ""),
                    "reasoning": getattr(sig, "reasoning", ""),
                    "stop_loss": getattr(sig, "stop_loss", None),
                    "take_profit": getattr(sig, "take_profit", None),
                    "entry_price": getattr(sig, "entry_price", None),
                }
                break

        return {
            **entry,
            "signal": signal,
            "direction": entry.get("action", "long"),
            "indicators": state.pipeline_context.get("indicators", {}),
            "market_context": {
                "timeframe": state.current_timeframe,
                "news_risk_adjustment": state.news_risk_adjustment,
            },
        }

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

        # Include debate summary
        debate_results = s.pipeline_context.get("debate_results", [])
        if debate_results:
            summary_lines.append(f"\nDebate: {len(debate_results)} signals debated")
            for dr in debate_results:
                summary_lines.append(
                    f"  - {dr.get('verdict', '?').upper()} "
                    f"(bull={dr.get('bull_confidence', 0):.2f}, "
                    f"bear={dr.get('bear_confidence', 0):.2f})"
                )

        summary = "\n".join(summary_lines)

        # Use LangGraph interrupt to pause for human input (30s timeout)
        try:
            human_response = interrupt(summary)
        except Exception:
            logger.warning("orchestrator.human_review.timeout_or_error", exc_info=True)
            s.human_feedback = "rejected"
            for decision in s.trade_decisions:
                if decision.status == "approved":
                    decision.status = "rejected"
                    decision.rejection_reason = "Human review timed out or failed"
            s.add_agent_message("human", "Human review timed out — rejecting all trades")
            out = _state_to_dict(s)
            out["current_node"] = "human_review"
            return out

        # Process human feedback — REJECT on non-string input (fail-closed)
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
            # Fail-closed: non-string input (None, dict, etc.) → REJECT
            logger.warning("orchestrator.human_review.non_string_input", type=type(human_response).__name__)
            for decision in s.trade_decisions:
                if decision.status == "approved":
                    decision.status = "rejected"
                    decision.rejection_reason = f"Invalid human review response type: {type(human_response).__name__}"
            s.human_feedback = "rejected"
            s.add_agent_message("human", "Human review received invalid response — rejecting all trades")

        out = _state_to_dict(s)
        out["current_node"] = "human_review"
        return out

    # ------------------------------------------------------------------
    # Routing functions
    # ------------------------------------------------------------------

    def _route_after_debate(self, state: dict[str, Any]) -> Literal["proceed", "end"]:
        """Route after debate: proceed to risk if any signals survived, else end."""
        s = _state_from_dict(state)

        if not s.signals:
            logger.info("orchestrator.debate.all_rejected")
            return "end"

        return "proceed"

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
