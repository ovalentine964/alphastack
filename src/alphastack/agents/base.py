"""Base agent class for all AlphaStack agents."""

from __future__ import annotations

import abc
import time
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from langchain_core.messages import AIMessage, BaseMessage

from alphastack.core.events import AgentEvent, EventBus, EventType
from alphastack.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Agent memory
# ---------------------------------------------------------------------------

class AgentMemory(BaseModel):
    """Short-term working memory for an agent."""

    observations: list[dict[str, Any]] = Field(default_factory=list)
    decisions: list[dict[str, Any]] = Field(default_factory=list)
    reflections: list[str] = Field(default_factory=list)

    def add_observation(self, content: str, metadata: dict[str, Any] | None = None) -> None:
        self.observations.append({
            "content": content,
            "metadata": metadata or {},
            "timestamp": datetime.utcnow().isoformat(),
        })

    def add_decision(self, action: str, reasoning: str, confidence: float) -> None:
        self.decisions.append({
            "action": action,
            "reasoning": reasoning,
            "confidence": confidence,
            "timestamp": datetime.utcnow().isoformat(),
        })

    def add_reflection(self, reflection: str) -> None:
        self.reflections.append(reflection)

    def recent_observations(self, n: int = 10) -> list[dict[str, Any]]:
        return self.observations[-n:]

    def recent_decisions(self, n: int = 5) -> list[dict[str, Any]]:
        return self.decisions[-n:]


# ---------------------------------------------------------------------------
# ReAct step
# ---------------------------------------------------------------------------

class ReActStep(BaseModel):
    """Single step in a ReAct (Reason → Act → Observe) loop."""

    thought: str = ""
    action: str = ""
    action_input: dict[str, Any] = Field(default_factory=dict)
    observation: str = ""
    step_number: int = 0
    duration_ms: int = 0


# ---------------------------------------------------------------------------
# Base agent ABC
# ---------------------------------------------------------------------------

class AlphaStackAgent(abc.ABC):
    """Abstract base class for all AlphaStack agents.

    Provides:
    - Identity (name, role, description)
    - ReAct loop pattern
    - Working memory
    - Event publishing via the shared EventBus
    - Common ``run()`` entry point with timing & error handling

    Subclasses must implement:
    - :meth:`system_prompt` — the agent's system prompt
    - :meth:`execute` — the core agent logic
    """

    def __init__(
        self,
        name: str,
        role: str,
        description: str = "",
        tools: list[Any] | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self.agent_id = f"{name}_{uuid.uuid4().hex[:8]}"
        self.name = name
        self.role = role
        self.description = description
        self.tools = tools or []
        self.memory = AgentMemory()
        self._event_bus = event_bus

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abc.abstractmethod
    def system_prompt(self) -> str:
        """Return the system prompt that defines this agent's behaviour."""

    @abc.abstractmethod
    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Run the agent's core logic and return state updates.

        Parameters
        ----------
        state : dict
            The current shared orchestrator state.

        Returns
        -------
        dict
            A partial state dict with the fields this agent wants to update.
        """

    # ------------------------------------------------------------------
    # ReAct loop
    # ------------------------------------------------------------------

    async def react_loop(
        self,
        query: str,
        max_steps: int = 5,
    ) -> list[ReActStep]:
        """Execute a ReAct (Reason → Act → Observe) loop.

        Override in subclasses that need tool-calling loops.
        The default implementation is a single-step "think only" pass.
        """
        steps: list[ReActStep] = []
        start = time.monotonic()

        step = ReActStep(
            thought=query,
            action="respond",
            action_input={"query": query},
            observation="(base agent – no tools configured)",
            step_number=1,
            duration_ms=int((time.monotonic() - start) * 1000),
        )
        steps.append(step)
        return steps

    # ------------------------------------------------------------------
    # Event publishing
    # ------------------------------------------------------------------

    async def publish_event(
        self,
        action: str,
        reasoning: str = "",
        confidence: float = 0.0,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Publish an AgentEvent to the event bus."""
        if self._event_bus is None:
            return
        event = AgentEvent(
            source=self.agent_id,
            agent_id=self.agent_id,
            action=action,
            reasoning=reasoning,
            confidence=confidence,
            payload=payload or {},
        )
        try:
            await self._event_bus.publish(event)
        except Exception:
            logger.warning("agent.event_publish_failed", agent=self.agent_id, exc_info=True)

    # ------------------------------------------------------------------
    # Run entry point
    # ------------------------------------------------------------------

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Main entry point — wraps execute with timing, logging, events."""
        logger.info("agent.start", agent=self.name, role=self.role)
        start = time.monotonic()

        try:
            result = await self.execute(state)
            elapsed_ms = int((time.monotonic() - start) * 1000)

            # Record in memory
            self.memory.add_observation(
                f"Executed in {elapsed_ms}ms",
                metadata={"result_keys": list(result.keys())},
            )

            # Publish completion event
            await self.publish_event(
                action="complete",
                reasoning=f"{self.name} completed in {elapsed_ms}ms",
                confidence=result.get("_confidence", 0.0),
            )

            logger.info("agent.complete", agent=self.name, elapsed_ms=elapsed_ms)
            return result

        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.error("agent.error", agent=self.name, elapsed_ms=elapsed_ms, exc_info=True)

            await self.publish_event(
                action="error",
                reasoning=f"{self.name} failed: {exc}",
                confidence=0.0,
            )
            raise
