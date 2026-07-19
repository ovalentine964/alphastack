"""Upgraded base agent class for AlphaStack v2.0.

Provides production-grade features per the architecture update:
- Per-node timeout enforcement (LangGraph 1.0)
- Retry logic with exponential backoff
- Circuit breaker per agent (OWASP-aligned)
- Health monitoring (heartbeat)
- Structured error handling with trace capture
"""

from __future__ import annotations

import abc
import asyncio
import enum
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from alphastack.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------

class CircuitState(str, enum.Enum):
    """Circuit breaker states."""
    CLOSED = "closed"       # Normal operation — requests flow through
    OPEN = "open"           # Tripped — all requests rejected immediately
    HALF_OPEN = "half_open" # Testing — one request allowed to check recovery


class CircuitBreaker:
    """Per-agent circuit breaker with configurable thresholds.

    Transitions:
        CLOSED → OPEN:  failure_count >= failure_threshold within window
        OPEN → HALF_OPEN: after recovery_timeout seconds
        HALF_OPEN → CLOSED: on success
        HALF_OPEN → OPEN: on failure
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        window_seconds: float = 300.0,
        name: str = "default",
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.window_seconds = window_seconds

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float = 0.0
        self._last_state_change: float = time.monotonic()
        self._failure_timestamps: list[float] = []

    @property
    def state(self) -> CircuitState:
        # Auto-transition OPEN → HALF_OPEN after recovery timeout
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                self._transition(CircuitState.HALF_OPEN)
        return self._state

    def allow_request(self) -> bool:
        """Check if a request should be allowed through."""
        state = self.state  # triggers auto-transition
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.HALF_OPEN:
            return True  # allow probe request
        return False  # OPEN

    def record_success(self) -> None:
        """Record a successful call."""
        self._success_count += 1
        if self._state == CircuitState.HALF_OPEN:
            self._transition(CircuitState.CLOSED)
            self._failure_count = 0
            self._failure_timestamps.clear()

    def record_failure(self) -> None:
        """Record a failed call."""
        now = time.monotonic()
        self._failure_count += 1
        self._last_failure_time = now
        self._failure_timestamps.append(now)

        # Prune old failures outside the window
        cutoff = now - self.window_seconds
        self._failure_timestamps = [t for t in self._failure_timestamps if t > cutoff]

        if self._state == CircuitState.HALF_OPEN:
            self._transition(CircuitState.OPEN)
        elif self._state == CircuitState.CLOSED:
            if len(self._failure_timestamps) >= self.failure_threshold:
                self._transition(CircuitState.OPEN)

    def _transition(self, new_state: CircuitState) -> None:
        old = self._state
        self._state = new_state
        self._last_state_change = time.monotonic()
        logger.warning(
            "circuit_breaker.transition",
            name=self.name,
            from_state=old.value,
            to_state=new_state.value,
            failure_count=self._failure_count,
        )

    def reset(self) -> None:
        """Manually reset the circuit breaker to closed state."""
        self._transition(CircuitState.CLOSED)
        self._failure_count = 0
        self._failure_timestamps.clear()

    def as_dict(self) -> dict[str, Any]:
        """Serialize state for monitoring."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "last_failure_age_s": round(time.monotonic() - self._last_failure_time, 1)
            if self._last_failure_time
            else None,
        }


# ---------------------------------------------------------------------------
# Retry Policy
# ---------------------------------------------------------------------------

class RetryPolicy:
    """Exponential backoff retry policy with jitter."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
    ) -> None:
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

    def delay_for_attempt(self, attempt: int) -> float:
        """Compute delay for a given retry attempt (0-indexed)."""
        import random
        delay = self.base_delay * (self.exponential_base ** attempt)
        delay = min(delay, self.max_delay)
        if self.jitter:
            delay *= 0.5 + random.random()  # 50-150% of computed delay
        return delay


# ---------------------------------------------------------------------------
# Agent Health (heartbeat)
# ---------------------------------------------------------------------------

class AgentHealth(BaseModel):
    """Health status for an agent instance."""

    agent_id: str = ""
    agent_name: str = ""
    status: str = "healthy"  # healthy | degraded | unhealthy | dead
    last_heartbeat: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_success: datetime | None = None
    last_failure: datetime | None = None
    consecutive_failures: int = 0
    total_calls: int = 0
    total_failures: int = 0
    avg_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    circuit_breaker_state: str = "closed"
    uptime_seconds: float = 0.0

    # Rolling window stats
    _latency_window: list[float] = []

    class Config:
        arbitrary_types_allowed = True


# ---------------------------------------------------------------------------
# Execution Trace (for trace mining pipeline)
# ---------------------------------------------------------------------------

class ExecutionTrace(BaseModel):
    """Structured trace of a single agent execution for the trace mining pipeline."""

    trace_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    agent_id: str = ""
    agent_name: str = ""
    run_id: str = ""
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    duration_ms: float = 0.0
    status: str = "pending"  # pending | success | failure | timeout | circuit_open
    error: str | None = None
    error_type: str | None = None
    retry_count: int = 0
    input_summary: dict[str, Any] = Field(default_factory=dict)
    output_summary: dict[str, Any] = Field(default_factory=dict)
    circuit_breaker_state: str = "closed"
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Base Agent ABC (upgraded v2.0)
# ---------------------------------------------------------------------------

class AlphaStackAgent(abc.ABC):
    """Abstract base class for all AlphaStack agents — v2.0.

    Production features:
    - Per-node timeout enforcement
    - Retry with exponential backoff
    - Circuit breaker per agent
    - Health monitoring (heartbeat)
    - Structured error handling
    - Execution trace capture for the trace mining pipeline

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
        event_bus: Any | None = None,
        # Per-node timeout (seconds) — LangGraph 1.0 enforcement
        timeout: float = 30.0,
        # Retry configuration
        max_retries: int = 3,
        retry_base_delay: float = 1.0,
        retry_max_delay: float = 30.0,
        # Circuit breaker configuration
        cb_failure_threshold: int = 5,
        cb_recovery_timeout: float = 60.0,
        cb_window_seconds: float = 300.0,
    ) -> None:
        self.agent_id = f"{name}_{uuid.uuid4().hex[:8]}"
        self.name = name
        self.role = role
        self.description = description
        self.tools = tools or []
        self._event_bus = event_bus

        # Timeout
        self.timeout = timeout

        # Retry
        self.retry_policy = RetryPolicy(
            max_retries=max_retries,
            base_delay=retry_base_delay,
            max_delay=retry_max_delay,
        )

        # Circuit breaker
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=cb_failure_threshold,
            recovery_timeout=cb_recovery_timeout,
            window_seconds=cb_window_seconds,
            name=name,
        )

        # Health
        self.health = AgentHealth(
            agent_id=self.agent_id,
            agent_name=name,
        )
        self._created_at = time.monotonic()

        # Trace buffer (most recent N)
        self._trace_buffer: list[ExecutionTrace] = []
        self._max_traces = 100

        # Latency tracking (rolling window)
        self._latencies: list[float] = []
        self._max_latency_window = 100

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
    # Per-node timeout enforcement (LangGraph 1.0)
    # ------------------------------------------------------------------

    async def _execute_with_timeout(self, state: dict[str, Any]) -> dict[str, Any]:
        """Execute with per-node timeout enforcement."""
        try:
            return await asyncio.wait_for(
                self.execute(state),
                timeout=self.timeout,
            )
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"Agent '{self.name}' exceeded timeout of {self.timeout}s"
            )

    # ------------------------------------------------------------------
    # Retry with exponential backoff
    # ------------------------------------------------------------------

    async def _execute_with_retry(self, state: dict[str, Any]) -> dict[str, Any]:
        """Execute with retry logic and exponential backoff."""
        last_exc: Exception | None = None

        for attempt in range(self.retry_policy.max_retries + 1):
            try:
                result = await self._execute_with_timeout(state)
                return result
            except Exception as exc:
                last_exc = exc
                if attempt < self.retry_policy.max_retries:
                    delay = self.retry_policy.delay_for_attempt(attempt)
                    logger.warning(
                        "agent.retry",
                        agent=self.name,
                        attempt=attempt + 1,
                        max_retries=self.retry_policy.max_retries,
                        delay_s=round(delay, 2),
                        error=str(exc),
                    )
                    await asyncio.sleep(delay)

        # All retries exhausted
        raise last_exc  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Circuit breaker + full execution
    # ------------------------------------------------------------------

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Main entry point — full production execution pipeline.

        Flow: circuit check → retry loop → timeout enforcement → execute
        Records health, traces, and publishes events.
        """
        # Check circuit breaker
        if not self.circuit_breaker.allow_request():
            logger.warning(
                "agent.circuit_open",
                agent=self.name,
                cb_state=self.circuit_breaker.state.value,
            )
            self.health.status = "unhealthy"
            self.health.circuit_breaker_state = self.circuit_breaker.state.value

            # Publish circuit open event
            await self._publish_event(
                action="circuit_open",
                reasoning=f"Circuit breaker is {self.circuit_breaker.state.value}",
                confidence=0.0,
            )

            # Return empty result — don't crash the pipeline
            return self._circuit_open_result(state)

        # Build execution trace
        trace = ExecutionTrace(
            agent_id=self.agent_id,
            agent_name=self.name,
            run_id=state.get("run_id", ""),
            input_summary=self._summarize_input(state),
        )

        start = time.monotonic()
        self.health.total_calls += 1
        self.health.last_heartbeat = datetime.now(timezone.utc)

        try:
            # Execute with retry + timeout
            result = await self._execute_with_retry(state)

            elapsed_ms = (time.monotonic() - start) * 1000

            # Update health
            self.health.status = "healthy"
            self.health.last_success = datetime.now(timezone.utc)
            self.health.consecutive_failures = 0
            self.health.circuit_breaker_state = self.circuit_breaker.state.value
            self._update_latency(elapsed_ms)

            # Record circuit breaker success
            self.circuit_breaker.record_success()

            # Complete trace
            trace.completed_at = datetime.now(timezone.utc)
            trace.duration_ms = elapsed_ms
            trace.status = "success"
            trace.output_summary = self._summarize_output(result)
            self._store_trace(trace)

            # Publish completion event
            await self._publish_event(
                action="complete",
                reasoning=f"{self.name} completed in {elapsed_ms:.0f}ms",
                confidence=result.get("_confidence", 0.0),
            )

            logger.info(
                "agent.complete",
                agent=self.name,
                elapsed_ms=round(elapsed_ms, 1),
            )
            return result

        except TimeoutError as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            self.health.consecutive_failures += 1
            self.health.last_failure = datetime.now(timezone.utc)
            self.health.total_failures += 1
            self.circuit_breaker.record_failure()

            trace.completed_at = datetime.now(timezone.utc)
            trace.duration_ms = elapsed_ms
            trace.status = "timeout"
            trace.error = str(exc)
            trace.error_type = "TimeoutError"
            self._store_trace(trace)

            logger.error(
                "agent.timeout",
                agent=self.name,
                timeout_s=self.timeout,
                elapsed_ms=round(elapsed_ms, 1),
            )

            await self._publish_event(
                action="timeout",
                reasoning=f"{self.name} timed out after {self.timeout}s",
                confidence=0.0,
            )

            self._update_health_status()
            return self._error_result(state, exc)

        except Exception as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            self.health.consecutive_failures += 1
            self.health.last_failure = datetime.now(timezone.utc)
            self.health.total_failures += 1
            self.circuit_breaker.record_failure()

            trace.completed_at = datetime.now(timezone.utc)
            trace.duration_ms = elapsed_ms
            trace.status = "failure"
            trace.error = str(exc)
            trace.error_type = type(exc).__name__
            self._store_trace(trace)

            logger.error(
                "agent.error",
                agent=self.name,
                elapsed_ms=round(elapsed_ms, 1),
                error=str(exc),
                exc_info=True,
            )

            await self._publish_event(
                action="error",
                reasoning=f"{self.name} failed: {exc}",
                confidence=0.0,
            )

            self._update_health_status()
            return self._error_result(state, exc)

    # ------------------------------------------------------------------
    # Health monitoring
    # ------------------------------------------------------------------

    def _update_latency(self, elapsed_ms: float) -> None:
        """Update rolling latency window and compute stats."""
        self._latencies.append(elapsed_ms)
        if len(self._latencies) > self._max_latency_window:
            self._latencies = self._latencies[-self._max_latency_window:]

        self.health.avg_latency_ms = sum(self._latencies) / len(self._latencies)
        sorted_lat = sorted(self._latencies)
        p99_idx = int(len(sorted_lat) * 0.99)
        self.health.p99_latency_ms = sorted_lat[min(p99_idx, len(sorted_lat) - 1)]

    def _update_health_status(self) -> None:
        """Derive health status from consecutive failures."""
        if self.health.consecutive_failures >= self.circuit_breaker.failure_threshold:
            self.health.status = "dead"
        elif self.health.consecutive_failures >= 3:
            self.health.status = "degraded"
        elif self.health.consecutive_failures >= 1:
            self.health.status = "degraded"
        self.health.circuit_breaker_state = self.circuit_breaker.state.value

    def get_health(self) -> dict[str, Any]:
        """Return current health status as dict."""
        self.health.uptime_seconds = time.monotonic() - self._created_at
        return self.health.model_dump()

    def heartbeat(self) -> dict[str, Any]:
        """Emit a heartbeat — call periodically for health monitoring."""
        self.health.last_heartbeat = datetime.now(timezone.utc)
        self.health.uptime_seconds = time.monotonic() - self._created_at
        self.health.circuit_breaker_state = self.circuit_breaker.state.value
        return self.get_health()

    # ------------------------------------------------------------------
    # Trace management
    # ------------------------------------------------------------------

    def _store_trace(self, trace: ExecutionTrace) -> None:
        """Store trace in buffer for the trace mining pipeline."""
        self._trace_buffer.append(trace)
        if len(self._trace_buffer) > self._max_traces:
            self._trace_buffer = self._trace_buffer[-self._max_traces:]

    def get_traces(self, n: int | None = None) -> list[dict[str, Any]]:
        """Return recent execution traces for the trace mining pipeline."""
        traces = self._trace_buffer[-n:] if n else self._trace_buffer
        return [t.model_dump() for t in traces]

    # ------------------------------------------------------------------
    # Event publishing
    # ------------------------------------------------------------------

    async def _publish_event(
        self,
        action: str,
        reasoning: str = "",
        confidence: float = 0.0,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Publish an AgentEvent to the event bus."""
        if self._event_bus is None:
            return
        try:
            from alphastack.core.events import AgentEvent
            event = AgentEvent(
                source=self.agent_id,
                agent_id=self.agent_id,
                action=action,
                reasoning=reasoning,
                confidence=confidence,
                payload=payload or {},
            )
            await self._event_bus.publish(event)
        except Exception:
            logger.warning("agent.event_publish_failed", agent=self.agent_id, exc_info=True)

    # ------------------------------------------------------------------
    # Result helpers
    # ------------------------------------------------------------------

    def _circuit_open_result(self, state: dict[str, Any]) -> dict[str, Any]:
        """Return a safe default result when circuit breaker is open."""
        return {
            "_confidence": 0.0,
            "_circuit_open": True,
            "_agent": self.name,
            "_error": f"Circuit breaker open for {self.name}",
        }

    def _error_result(self, state: dict[str, Any], exc: Exception) -> dict[str, Any]:
        """Return a safe default result when execution fails."""
        return {
            "_confidence": 0.0,
            "_error": str(exc),
            "_error_type": type(exc).__name__,
            "_agent": self.name,
        }

    @staticmethod
    def _summarize_input(state: dict[str, Any]) -> dict[str, Any]:
        """Create a lightweight input summary for traces (no full state dump)."""
        return {
            "keys": list(state.keys()),
            "symbol": state.get("current_symbol", ""),
            "timeframe": state.get("current_timeframe", ""),
            "has_market_data": bool(state.get("market_data")),
            "signal_count": len(state.get("signals", [])),
            "has_news_alerts": bool(state.get("news_alerts")),
        }

    @staticmethod
    def _summarize_output(result: dict[str, Any]) -> dict[str, Any]:
        """Create a lightweight output summary for traces."""
        return {
            "keys": list(result.keys()),
            "confidence": result.get("_confidence", 0.0),
            "has_error": "_error" in result,
        }
