"""ReAct (Reasoning + Acting) loop for AlphaStack agents.

Core cognitive loop: Think → Act → Observe → Repeat.

Forces agents to:
1. Reason about market conditions before acting
2. Gather information dynamically (tool use)
3. Observe results and update understanding
4. Iterate until a decision threshold is met

This is the primary decision loop used by all agents. Every trade
decision produces an auditable reasoning chain.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


class LoopStatus(Enum):
    """Status of a ReAct loop execution."""

    RUNNING = "running"
    DECISION_REACHED = "decision_reached"
    MAX_STEPS_REACHED = "max_steps_reached"
    TIMEOUT = "timeout"
    ERROR = "error"
    ABORTED = "aborted"


@dataclass
class ReActStep:
    """Single step in a ReAct loop.

    Attributes
    ----------
    step_number : int
        Sequential step number (1-indexed).
    thought : str
        Agent's reasoning about current state.
    action : str
        The action/tool the agent chose to use.
    action_input : dict
        Parameters for the action.
    observation : str
        Result of the action.
    duration_ms : float
        Time taken for this step.
    confidence : float
        Agent's confidence in current reasoning (0-1).
    """

    step_number: int = 0
    thought: str = ""
    action: str = ""
    action_input: dict[str, Any] = field(default_factory=dict)
    observation: str = ""
    duration_ms: float = 0.0
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step_number,
            "thought": self.thought,
            "action": self.action,
            "action_input": self.action_input,
            "observation": self.observation,
            "duration_ms": self.duration_ms,
            "confidence": self.confidence,
        }


@dataclass
class ReActResult:
    """Result of a complete ReAct loop execution."""

    steps: list[ReActStep] = field(default_factory=list)
    final_thought: str = ""
    decision: str = ""
    confidence: float = 0.0
    total_duration_ms: float = 0.0
    status: LoopStatus = LoopStatus.RUNNING
    reasoning_chain: list[str] = field(default_factory=list)

    @property
    def num_steps(self) -> int:
        return len(self.steps)

    def to_audit_log(self) -> dict[str, Any]:
        """Export as structured audit log entry."""
        return {
            "decision": self.decision,
            "confidence": self.confidence,
            "num_steps": self.num_steps,
            "total_duration_ms": self.total_duration_ms,
            "status": self.status.value,
            "reasoning_chain": self.reasoning_chain,
            "steps": [s.to_dict() for s in self.steps],
        }


# ---------------------------------------------------------------------------
# Tool interface
# ---------------------------------------------------------------------------


@dataclass
class Tool:
    """A tool available to the ReAct agent.

    Parameters
    ----------
    name : str
        Tool identifier (e.g., "fetch_price", "check_rsi").
    description : str
        What the tool does — used by the agent to decide when to use it.
    function : Callable
        Async function that executes the tool.
    returns_schema : str
        Description of the tool's return format.
    """

    name: str
    description: str
    function: Callable[..., Awaitable[str]]
    returns_schema: str = ""


# ---------------------------------------------------------------------------
# ReAct Loop
# ---------------------------------------------------------------------------


class ReActLoop:
    """ReAct (Reasoning + Acting) loop implementation.

    Implements the Think → Act → Observe cycle that drives all
    AlphaStack agent decisions.

    Usage: loop = ReActLoop(tools=[...], max_steps=10)
    result = await loop.run(context=..., reason_fn=..., decision_threshold=0.8)
    """

    def __init__(
        self,
        tools: list[Tool] | None = None,
        max_steps: int = 10,
        timeout_seconds: float = 30.0,
        decision_threshold: float = 0.8,
    ) -> None:
        self.tools = {t.name: t for t in (tools or [])}
        self.max_steps = max_steps
        self.timeout_seconds = timeout_seconds
        self.decision_threshold = decision_threshold

    async def run(
        self,
        context: str,
        reason_fn: Callable[..., Awaitable[tuple[str, str, dict[str, Any], float]]],
        decision_threshold: float | None = None,
        initial_observations: list[str] | None = None,
    ) -> ReActResult:
        """Execute the ReAct loop.

        Parameters
        ----------
        context : str
            The market context or problem statement.
        reason_fn : Callable
            Async function: (step_number, context, observations) →
            (thought, action, action_input, confidence)
        decision_threshold : float, optional
            Override the default decision confidence threshold.
        initial_observations : list[str], optional
            Pre-existing observations to seed the loop.

        Returns
        -------
        ReActResult
            Complete execution result with reasoning chain.
        """
        threshold = decision_threshold or self.decision_threshold
        result = ReActResult()
        observations = list(initial_observations or [])
        start_time = time.monotonic()

        for step_num in range(1, self.max_steps + 1):
            # Check timeout
            elapsed = (time.monotonic() - start_time)
            if elapsed > self.timeout_seconds:
                result.status = LoopStatus.TIMEOUT
                logger.warning("ReAct loop timed out after %.1fs", elapsed)
                break

            step_start = time.monotonic()

            try:
                # THINK: Get reasoning from the reason function
                thought, action, action_input, confidence = await reason_fn(
                    step_num, context, observations
                )
            except Exception as e:
                logger.error("ReAct step %d reason failed: %s", step_num, e)
                result.status = LoopStatus.ERROR
                break

            step = ReActStep(
                step_number=step_num,
                thought=thought,
                action=action,
                action_input=action_input,
                confidence=confidence,
            )

            # ACT: Execute the tool if available
            if action and action in self.tools:
                try:
                    observation = await self.tools[action].function(**action_input)
                    step.observation = observation
                    observations.append(observation)
                except Exception as e:
                    step.observation = f"Error: {e}"
                    observations.append(f"Error executing {action}: {e}")
            elif action:
                step.observation = f"Unknown tool: {action}"
            else:
                step.observation = "No action taken — reasoning only"

            step.duration_ms = (time.monotonic() - step_start) * 1000
            result.steps.append(step)
            result.reasoning_chain.append(
                f"[Step {step_num}] {thought}"
            )

            # Check if decision threshold reached
            if confidence >= threshold and action == "decide":
                result.status = LoopStatus.DECISION_REACHED
                result.final_thought = thought
                result.decision = step.observation
                result.confidence = confidence
                break

            # If no action and high confidence, treat as decision
            if confidence >= threshold and not action:
                result.status = LoopStatus.DECISION_REACHED
                result.final_thought = thought
                result.decision = thought
                result.confidence = confidence
                break
        else:
            result.status = LoopStatus.MAX_STEPS_REACHED
            if result.steps:
                last = result.steps[-1]
                result.final_thought = last.thought
                result.confidence = last.confidence

        result.total_duration_ms = (time.monotonic() - start_time) * 1000
        logger.info(
            "ReAct loop completed: status=%s, steps=%d, duration=%.0fms",
            result.status.value,
            result.num_steps,
            result.total_duration_ms,
        )
        return result

    def add_tool(self, tool: Tool) -> None:
        """Register a new tool with the loop."""
        self.tools[tool.name] = tool

    def get_tool_descriptions(self) -> str:
        """Get formatted tool descriptions for prompt injection."""
        lines = []
        for name, tool in self.tools.items():
            lines.append(f"- {name}: {tool.description}")
        return "\n".join(lines) if lines else "No tools available."

    def create_trading_reason_fn(
        self,
        llm_call: Callable[..., Awaitable[str]] | None = None,
    ) -> Callable[..., Awaitable[tuple[str, str, dict[str, Any], float]]]:
        """Create a default trading reason function.

        This provides the standard thought/action/confidence extraction
        pattern for trading agents. Override with custom LLM integration.
        """

        async def default_reason(
            step: int, context: str, observations: list[str]
        ) -> tuple[str, str, dict[str, Any], float]:
            obs_text = "\n".join(observations[-5:]) if observations else "No observations yet."
            prompt = (
                f"Step {step} | Context: {context}\n"
                f"Recent observations:\n{obs_text}\n\n"
                f"Available tools: {self.get_tool_descriptions()}\n\n"
                f"Think step by step. Then choose an action or make a decision."
            )

            if llm_call:
                response = await llm_call(prompt)
                return self._parse_response(response)

            # Fallback: structured reasoning template
            if step == 1:
                return (
                    f"Initial assessment: {context[:200]}",
                    "analyze_market",
                    {"context": context},
                    0.3,
                )
            elif step < self.max_steps:
                return (
                    f"Continuing analysis based on {len(observations)} observations",
                    "gather_data",
                    {"observations": observations[-3:]},
                    0.3 + (step * 0.1),
                )
            else:
                return (
                    "Sufficient information gathered for decision",
                    "",
                    {},
                    0.9,
                )

        return default_reason

    @staticmethod
    def _parse_response(
        response: str,
    ) -> tuple[str, str, dict[str, Any], float]:
        """Parse an LLM response into ReAct components.

        Expects format:
        Thought: ...
        Action: tool_name
        Action Input: {"key": "value"}
        Confidence: 0.X
        """
        thought = ""
        action = ""
        action_input: dict[str, Any] = {}
        confidence = 0.5

        for line in response.strip().split("\n"):
            line = line.strip()
            if line.startswith("Thought:"):
                thought = line[len("Thought:"):].strip()
            elif line.startswith("Action:"):
                action = line[len("Action:"):].strip()
            elif line.startswith("Action Input:"):
                import json
                try:
                    action_input = json.loads(line[len("Action Input:"):].strip())
                except json.JSONDecodeError:
                    action_input = {"raw": line[len("Action Input:"):].strip()}
            elif line.startswith("Confidence:"):
                try:
                    confidence = float(line[len("Confidence:"):].strip())
                except ValueError:
                    confidence = 0.5

        return thought, action, action_input, confidence
