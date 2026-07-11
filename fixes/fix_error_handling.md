# Alpha Stack — Error Handling Fixes (C1–C6)

> **Version:** 1.0 · **Date:** 2026-07-11 · **Author:** Error Handling Fix Agent  
> **Source:** `review_error_handling.md` — 6 critical gaps identified  
> **Scope:** Complete implementation specifications for all 6 critical error handling gaps  
> **Status:** Ready for implementation

---

## Table of Contents

1. [C1 — VMPM Pipeline Per-Step Error Handling](#c1--vmpm-pipeline-per-step-error-handling)
2. [C2 — LLM API Failure Handling](#c2--llm-api-failure-handling)
3. [C3 — Event Bus Grace Period](#c3--event-bus-grace-period)
4. [C4 — Circuit Breaker State Persistence](#c4--circuit-breaker-state-persistence)
5. [C5 — Data Pipeline Failure Recovery](#c5--data-pipeline-failure-recovery)
6. [C6 — Infrastructure Disaster Recovery](#c6--infrastructure-disaster-recovery)

---

## C1 — VMPM Pipeline Per-Step Error Handling

### Problem

The VMPM 16-step pipeline has no per-step error handling. A single LLM timeout or exception in any step stalls or crashes the entire pipeline. There is no timeout enforcement, no fallback strategy, and no partial-failure mechanism.

### Root Cause

The `VMPMStep` abstract base class defines only `analyze()` with no error contract, timeout, or failure strategy.

### Fix: StepErrorHandler System

#### 1. Define Failure Strategies

```python
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Any
import asyncio
import time

class FailureStrategy(Enum):
    """What to do when a pipeline step fails."""
    SKIP = "skip"                # Skip this step, continue pipeline
    USE_CACHED = "use_cached"    # Use the last successful result for this step
    USE_DEFAULT = "use_default"  # Use a hardcoded default result
    ABORT_PIPELINE = "abort"     # Abort the entire pipeline, return partial results
    RETRY_THEN_SKIP = "retry_then_skip"  # Retry N times, then skip

@dataclass
class StepConfig:
    """Configuration for a single pipeline step."""
    name: str
    timeout_seconds: float = 30.0       # Default 30s for LLM steps, 5s for indicator steps
    failure_strategy: FailureStrategy = FailureStrategy.SKIP
    max_retries: int = 2
    retry_delay_seconds: float = 1.0
    is_llm_step: bool = False
    is_critical: bool = False           # Critical steps abort pipeline on failure
    default_result: Optional[Any] = None
    cache_ttl_seconds: int = 300        # How long cached results are valid
```

#### 2. Define the Step Result Contract

```python
@dataclass
class StepResult:
    """Standardized result from every pipeline step."""
    step_name: str
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    from_cache: bool = False
    from_default: bool = False
    execution_time_ms: float = 0.0
    retry_count: int = 0

    @property
    def is_fallback(self) -> bool:
        return self.from_cache or self.from_default
```

#### 3. Implement StepErrorHandler

```python
class StepErrorHandler:
    """Handles errors for individual VMPM pipeline steps."""

    def __init__(self, cache_store):
        self.cache_store = cache_store  # Redis or in-memory cache
        self.step_results: dict[str, StepResult] = {}

    async def execute_step(
        self,
        step: 'VMPMStep',
        context: 'StrategyContext',
        config: StepConfig,
    ) -> StepResult:
        """Execute a single step with full error handling."""
        start_time = time.monotonic()

        for attempt in range(config.max_retries + 1):
            try:
                # Apply timeout
                result = await asyncio.wait_for(
                    step.analyze(context),
                    timeout=config.timeout_seconds,
                )

                # Validate result
                if not self._validate_result(result, step):
                    raise ValueError(f"Step {config.name} returned invalid result")

                execution_time = (time.monotonic() - start_time) * 1000
                step_result = StepResult(
                    step_name=config.name,
                    success=True,
                    data=result,
                    execution_time_ms=execution_time,
                    retry_count=attempt,
                )

                # Cache successful result
                self.cache_store.set(
                    f"vmpm_cache:{config.name}",
                    result,
                    ttl=config.cache_ttl_seconds,
                )
                self.step_results[config.name] = step_result
                return step_result

            except asyncio.TimeoutError:
                error_msg = f"Step {config.name} timed out after {config.timeout_seconds}s (attempt {attempt + 1})"
                if attempt < config.max_retries:
                    await asyncio.sleep(config.retry_delay_seconds * (attempt + 1))
                    continue
                return self._handle_failure(config, error_msg, start_time)

            except Exception as e:
                error_msg = f"Step {config.name} failed: {type(e).__name__}: {str(e)} (attempt {attempt + 1})"
                if attempt < config.max_retries and config.failure_strategy == FailureStrategy.RETRY_THEN_SKIP:
                    await asyncio.sleep(config.retry_delay_seconds * (attempt + 1))
                    continue
                return self._handle_failure(config, error_msg, start_time)

        # Should not reach here, but safety fallback
        return self._handle_failure(config, f"Step {config.name} exhausted all retries", start_time)

    def _handle_failure(self, config: StepConfig, error_msg: str, start_time: float) -> StepResult:
        """Apply the configured failure strategy."""
        execution_time = (time.monotonic() - start_time) * 1000

        if config.failure_strategy == FailureStrategy.USE_CACHED:
            cached = self.cache_store.get(f"vmpm_cache:{config.name}")
            if cached is not None:
                return StepResult(
                    step_name=config.name,
                    success=True,
                    data=cached,
                    from_cache=True,
                    error=error_msg,
                    execution_time_ms=execution_time,
                )

        if config.failure_strategy == FailureStrategy.USE_DEFAULT and config.default_result is not None:
            return StepResult(
                step_name=config.name,
                success=True,
                data=config.default_result,
                from_default=True,
                error=error_msg,
                execution_time_ms=execution_time,
            )

        # SKIP or fallback failure — mark as failed but non-fatal
        return StepResult(
            step_name=config.name,
            success=False,
            error=error_msg,
            execution_time_ms=execution_time,
        )

    def _validate_result(self, result, step) -> bool:
        """Validate that a step result is usable."""
        if result is None:
            return False
        # Steps can override this with custom validation
        if hasattr(step, 'validate_result'):
            return step.validate_result(result)
        return True
```

#### 4. Pipeline Orchestrator with Per-Step Error Handling

```python
class VMPMPipelineOrchestrator:
    """Orchestrates the 16-step VMPM pipeline with per-step error handling."""

    # Step configurations — each step defines its own error behavior
    STEP_CONFIGS = [
        StepConfig(name="market_regime", timeout_seconds=5, failure_strategy=FailureStrategy.USE_CACHED, is_llm_step=False),
        StepConfig(name="session_detection", timeout_seconds=3, failure_strategy=FailureStrategy.USE_DEFAULT, is_llm_step=False),
        StepConfig(name="data_validation", timeout_seconds=5, failure_strategy=FailureStrategy.ABORT_PIPELINE, is_critical=True),
        StepConfig(name="multi_tf_analysis", timeout_seconds=10, failure_strategy=FailureStrategy.SKIP, is_llm_step=False),
        StepConfig(name="sr_detection", timeout_seconds=10, failure_strategy=FailureStrategy.USE_CACHED, is_llm_step=False),
        StepConfig(name="order_flow", timeout_seconds=10, failure_strategy=FailureStrategy.SKIP, is_llm_step=False),
        StepConfig(name="smart_money", timeout_seconds=30, failure_strategy=FailureStrategy.SKIP, is_llm_step=True),
        StepConfig(name="confluence_scoring", timeout_seconds=15, failure_strategy=FailureStrategy.USE_CACHED, is_llm_step=False),
        StepConfig(name="regime_filter", timeout_seconds=5, failure_strategy=FailureStrategy.USE_CACHED, is_llm_step=False),
        StepConfig(name="news_filter", timeout_seconds=20, failure_strategy=FailureStrategy.SKIP, is_llm_step=True),
        StepConfig(name="risk_assessment", timeout_seconds=10, failure_strategy=FailureStrategy.ABORT_PIPELINE, is_critical=True),
        StepConfig(name="position_sizing", timeout_seconds=5, failure_strategy=FailureStrategy.ABORT_PIPELINE, is_critical=True),
        StepConfig(name="entry_timing", timeout_seconds=10, failure_strategy=FailureStrategy.SKIP, is_llm_step=False),
        StepConfig(name="exit_strategy", timeout_seconds=10, failure_strategy=FailureStrategy.USE_CACHED, is_llm_step=False),
        StepConfig(name="journal_logging", timeout_seconds=15, failure_strategy=FailureStrategy.SKIP, is_llm_step=True),
        StepConfig(name="final_signal", timeout_seconds=5, failure_strategy=FailureStrategy.ABORT_PIPELINE, is_critical=True),
    ]

    def __init__(self, steps: list['VMPMStep'], cache_store, logger):
        self.steps = {s.name: s for s in steps}
        self.handler = StepErrorHandler(cache_store)
        self.logger = logger

    async def run(self, context: 'StrategyContext') -> 'PipelineResult':
        """Run the full pipeline with per-step error handling."""
        results: list[StepResult] = []
        aborted = False

        for config in self.STEP_CONFIGS:
            if aborted:
                results.append(StepResult(
                    step_name=config.name,
                    success=False,
                    error="Pipeline aborted by earlier critical step failure",
                ))
                continue

            step = self.steps.get(config.name)
            if step is None:
                self.logger.warning(f"Step {config.name} not registered, skipping")
                continue

            result = await self.handler.execute_step(step, context, config)
            results.append(result)

            # Log all results (including fallbacks) to reasoning chain
            self._log_to_reasoning_chain(result, context)

            # Check if pipeline should abort
            if not result.success and config.is_critical:
                aborted = True
                self.logger.error(
                    f"Pipeline ABORTED: critical step '{config.name}' failed — {result.error}"
                )

            # Log fallback usage
            if result.is_fallback:
                self.logger.warning(
                    f"Step '{config.name}' used fallback "
                    f"(cache={result.from_cache}, default={result.from_default}): {result.error}"
                )

        return PipelineResult(
            steps=results,
            aborted=aborted,
            successful_steps=sum(1 for r in results if r.success),
            failed_steps=sum(1 for r in results if not r.success),
            fallback_steps=sum(1 for r in results if r.is_fallback),
        )

    def _log_to_reasoning_chain(self, result: StepResult, context: 'StrategyContext'):
        """Log step result to the reasoning chain for audit."""
        entry = {
            "step": result.step_name,
            "success": result.success,
            "from_fallback": result.is_fallback,
            "execution_ms": result.execution_time_ms,
            "retry_count": result.retry_count,
        }
        if result.error:
            entry["error"] = result.error
        context.reasoning_chain.append(entry)
```

#### 5. Updated VMPMStep Base Class

```python
class VMPMStep(ABC):
    """Updated abstract base class with error handling contract."""

    @abstractmethod
    async def analyze(self, context: StrategyContext) -> Any:
        """Execute the step analysis. Must raise on failure — never return None."""
        pass

    def validate_result(self, result: Any) -> bool:
        """Override to add custom result validation."""
        return result is not None

    @property
    @abstractmethod
    def step_name(self) -> str:
        """Unique name matching StepConfig."""
        pass
```

### Impact

- Pipeline continues with degraded (but valid) output when non-critical steps fail
- LLM timeouts no longer stall the entire pipeline
- Critical steps (data validation, risk assessment, position sizing) still abort on failure — safety preserved
- All fallbacks logged to reasoning chain for full auditability

---

## C2 — LLM API Failure Handling

### Problem

Agents using DeepSeek/Qwen/other LLMs have no error handling. API timeouts, rate limits, malformed responses, and provider outages all cause silent agent crashes or garbage signal propagation.

### Root Cause

No `LLMCallWrapper` exists. Each agent makes raw API calls with no retries, validation, or fallback.

### Fix: LLMCallWrapper with Retry, Validation, and Fallback

#### 1. Define LLM Error Types

```python
class LLMErrorCode(Enum):
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    MALFORMED_RESPONSE = "malformed_response"
    EMPTY_RESPONSE = "empty_response"
    INVALID_JSON = "invalid_json"
    AUTH_FAILURE = "auth_failure"
    PROVIDER_DOWN = "provider_down"
    UNKNOWN = "unknown"

@dataclass
class LLMResponse:
    """Standardized LLM response."""
    success: bool
    content: Optional[str] = None
    parsed_json: Optional[dict] = None
    error_code: Optional[LLMErrorCode] = None
    error_message: Optional[str] = None
    model_used: str = ""
    provider: str = ""
    latency_ms: float = 0.0
    retry_count: int = 0
    from_fallback: bool = False
```

#### 2. Implement LLMCallWrapper

```python
class LLMCallWrapper:
    """
    Wraps all LLM API calls with:
    - Exponential backoff with jitter
    - Response validation (JSON schema, relevance)
    - Fallback model chain (DeepSeek → Qwen → local)
    - Per-provider circuit breaker
    - Timeout enforcement
    """

    def __init__(self, config: LLMConfig, cache_store, metrics):
        self.config = config
        self.cache_store = cache_store
        self.metrics = metrics

        # Circuit breaker per provider
        self.circuit_breakers: dict[str, ProviderCircuitBreaker] = {}

        # Fallback chain: ordered list of (provider, model) pairs
        self.fallback_chain = [
            ("deepseek", "deepseek-chat"),
            ("qwen", "qwen-plus"),
            ("local", "local-model"),  # Last resort — local model or cached
        ]

    async def call(
        self,
        prompt: str,
        agent_name: str,
        expected_format: Optional[dict] = None,  # JSON schema for validation
        timeout_seconds: float = 30.0,
        temperature: float = 0.7,
        cache_key: Optional[str] = None,
        cache_ttl: int = 300,
    ) -> LLMResponse:
        """Execute an LLM call with full error handling."""

        # Check cache first
        if cache_key:
            cached = self.cache_store.get(f"llm_cache:{cache_key}")
            if cached:
                self.metrics.increment("llm.cache_hit", tags={"agent": agent_name})
                return LLMResponse(
                    success=True,
                    content=cached["content"],
                    parsed_json=cached.get("parsed_json"),
                    from_fallback=True,
                )

        last_error = None
        for provider, model in self.fallback_chain:
            # Check circuit breaker
            cb = self._get_circuit_breaker(provider)
            if cb.is_open():
                self.metrics.increment("llm.circuit_breaker_skip", tags={"provider": provider})
                continue

            # Try with retries
            for attempt in range(self.config.max_retries + 1):
                try:
                    start_time = time.monotonic()

                    response = await asyncio.wait_for(
                        self._raw_call(provider, model, prompt, temperature),
                        timeout=timeout_seconds,
                    )

                    latency_ms = (time.monotonic() - start_time) * 1000

                    # Validate response
                    validation_error = self._validate_response(response, expected_format)
                    if validation_error:
                        raise ValueError(f"Response validation failed: {validation_error}")

                    # Success — record and return
                    cb.record_success()
                    parsed = None
                    if expected_format:
                        parsed = json.loads(response)

                    result = LLMResponse(
                        success=True,
                        content=response,
                        parsed_json=parsed,
                        model_used=model,
                        provider=provider,
                        latency_ms=latency_ms,
                        retry_count=attempt,
                    )

                    # Cache if requested
                    if cache_key:
                        self.cache_store.set(
                            f"llm_cache:{cache_key}",
                            {"content": response, "parsed_json": parsed},
                            ttl=cache_ttl,
                        )

                    self.metrics.increment("llm.call_success", tags={
                        "agent": agent_name, "provider": provider, "model": model
                    })
                    return result

                except asyncio.TimeoutError:
                    last_error = LLMErrorCode.TIMEOUT
                    cb.record_failure()
                    self.metrics.increment("llm.timeout", tags={"provider": provider})

                except RateLimitError:
                    last_error = LLMErrorCode.RATE_LIMIT
                    # Don't count rate limits as circuit breaker failures
                    wait_time = self._get_retry_after(attempt)
                    await asyncio.sleep(wait_time)
                    continue

                except AuthError:
                    last_error = LLMErrorCode.AUTH_FAILURE
                    cb.record_failure()
                    break  # Don't retry auth failures on same provider

                except ValueError as e:
                    last_error = LLMErrorCode.MALFORMED_RESPONSE
                    cb.record_failure()

                except Exception as e:
                    last_error = LLMErrorCode.UNKNOWN
                    cb.record_failure()

                # Exponential backoff with jitter
                if attempt < self.config.max_retries:
                    delay = self._backoff_delay(attempt)
                    await asyncio.sleep(delay)

        # All providers exhausted
        self.metrics.increment("llm.all_providers_failed", tags={"agent": agent_name})

        # Last resort: return cached result even if expired
        if cache_key:
            stale = self.cache_store.get_stale(f"llm_cache:{cache_key}")
            if stale:
                self.logger.warning(f"LLM: Using stale cache for {agent_name}")
                return LLMResponse(
                    success=True,
                    content=stale["content"],
                    parsed_json=stale.get("parsed_json"),
                    from_fallback=True,
                )

        return LLMResponse(
            success=False,
            error_code=last_error or LLMErrorCode.UNKNOWN,
            error_message="All LLM providers exhausted",
        )

    def _backoff_delay(self, attempt: int) -> float:
        """Exponential backoff with jitter: 1s, 2s, 4s + random jitter."""
        base = self.config.base_retry_delay * (2 ** attempt)
        jitter = random.uniform(0, base * 0.5)
        return min(base + jitter, self.config.max_retry_delay)

    def _validate_response(self, response: str, expected_format: Optional[dict]) -> Optional[str]:
        """Validate LLM response against expected format."""
        if not response or not response.strip():
            return "Empty response"

        if expected_format:
            try:
                parsed = json.loads(response)
                # Validate against schema
                jsonschema.validate(parsed, expected_format)
            except json.JSONDecodeError:
                return "Response is not valid JSON"
            except jsonschema.ValidationError as e:
                return f"JSON schema validation failed: {e.message}"

        return None  # Valid

    def _get_circuit_breaker(self, provider: str) -> 'ProviderCircuitBreaker':
        if provider not in self.circuit_breakers:
            self.circuit_breakers[provider] = ProviderCircuitBreaker(
                failure_threshold=5,
                recovery_timeout_seconds=60,
            )
        return self.circuit_breakers[provider]


@dataclass
class LLMConfig:
    max_retries: int = 3
    base_retry_delay: float = 1.0
    max_retry_delay: float = 30.0
    default_timeout: float = 30.0


class ProviderCircuitBreaker:
    """Per-provider circuit breaker for LLM calls."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout_seconds: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout_seconds
        self.consecutive_failures = 0
        self.last_failure_time = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def is_open(self) -> bool:
        if self.state == "OPEN":
            if time.monotonic() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
                return False
            return True
        return False

    def record_success(self):
        self.consecutive_failures = 0
        self.state = "CLOSED"

    def record_failure(self):
        self.consecutive_failures += 1
        self.last_failure_time = time.monotonic()
        if self.consecutive_failures >= self.failure_threshold:
            self.state = "OPEN"
```

#### 3. Agent Integration Pattern

```python
class StrategyAgent:
    """Example agent showing LLMCallWrapper integration."""

    def __init__(self, llm_wrapper: LLMCallWrapper):
        self.llm = llm_wrapper

    async def analyze_smart_money(self, context: StrategyContext) -> Optional[SmartMoneyResult]:
        """Analyze smart money concepts with full LLM error handling."""
        prompt = self._build_smc_prompt(context)

        response = await self.llm.call(
            prompt=prompt,
            agent_name="strategy_smc",
            expected_format=SmartMoneyResult.schema(),
            timeout_seconds=30,
            cache_key=f"smc:{context.pair}:{context.timeframe}:{context.current_candle_time}",
            cache_ttl=300,
        )

        if not response.success:
            # LLMCallWrapper already tried all fallbacks
            # Log and return None — pipeline's FailureStrategy handles this
            self.logger.error(f"SMC analysis failed: {response.error_message}")
            return None

        if response.from_fallback:
            self.logger.warning("SMC analysis used cached/fallback result")

        return SmartMoneyResult(**response.parsed_json)
```

### Impact

- LLM timeouts retry 3× with exponential backoff before failing
- Rate limits handled with backoff, not treated as failures
- Malformed responses caught and retried
- Automatic fallback across providers (DeepSeek → Qwen → local)
- Per-provider circuit breaker prevents hammering a down provider
- Stale cache used as last resort before total failure

---

## C3 — Event Bus Grace Period

### Problem

A brief Redis blip (1-2 seconds) triggers the "close all positions, halt trading" response. This is too aggressive — unnecessary position closures on transient failures.

### Root Cause

The event bus failure handler has no reconnection logic, no local buffer, no grace period, and no degraded mode.

### Fix: Tiered Event Bus Failure Response

#### 1. Define Failure Tiers

```python
class EventBusFailureTier(Enum):
    """Tiered response to event bus failures."""
    HEALTHY = "healthy"           # Normal operation
    DEGRADED = "degraded"         # Brief outage, local buffering active
    CRITICAL = "critical"         # Extended outage, stop new trades
    EMERGENCY = "emergency"       # Prolonged outage, close positions

@dataclass
class EventBusHealthConfig:
    """Configuration for event bus health monitoring."""
    # Tier thresholds
    degraded_threshold_seconds: float = 5.0    # 5s without bus → degraded
    critical_threshold_seconds: float = 30.0   # 30s → critical (stop new trades)
    emergency_threshold_seconds: float = 60.0  # 60s → emergency (close all)

    # Recovery
    recovery_confirmation_seconds: float = 10.0  # Must be healthy for 10s to confirm recovery

    # Buffer
    max_buffered_events: int = 10000
    buffer_flush_timeout_seconds: float = 30.0

    # Reconnection
    reconnect_base_delay: float = 0.5
    reconnect_max_delay: float = 5.0
    reconnect_max_attempts: int = 100  # Keep trying for a long time
```

#### 2. Implement EventBusHealthMonitor

```python
class EventBusHealthMonitor:
    """
    Monitors event bus health with tiered response.
    
    Tiers:
    - HEALTHY → Normal operation
    - DEGRADED (5s) → Buffer events locally, continue processing
    - CRITICAL (30s) → Stop new trades, manage existing positions
    - EMERGENCY (60s) → Close all positions, full halt
    """

    def __init__(self, config: EventBusHealthConfig, event_bus, logger, metrics):
        self.config = config
        self.event_bus = event_bus
        self.logger = logger
        self.metrics = metrics

        self.current_tier = EventBusFailureTier.HEALTHY
        self.failure_start_time: Optional[float] = None
        self.last_successful_ping: float = time.monotonic()
        self.recovery_start_time: Optional[float] = None

        # Local event buffer for brief outages
        self.event_buffer: asyncio.Queue = asyncio.Queue(
            maxsize=config.max_buffered_events
        )
        self.buffer_overflow_count = 0

        # Reconnection state
        self.reconnect_attempts = 0
        self.is_reconnecting = False

    async def start_monitoring(self):
        """Start the health monitoring loop."""
        asyncio.create_task(self._monitor_loop())
        asyncio.create_task(self._reconnect_loop())

    async def _monitor_loop(self):
        """Main health check loop — runs every 1 second."""
        while True:
            try:
                await self._check_health()
            except Exception as e:
                self.logger.error(f"Health monitor error: {e}")
            await asyncio.sleep(1.0)

    async def _check_health(self):
        """Check event bus health and update tier."""
        try:
            # Ping Redis with short timeout
            await asyncio.wait_for(
                self.event_bus.ping(),
                timeout=2.0,
            )

            # Ping succeeded
            now = time.monotonic()

            if self.current_tier != EventBusFailureTier.HEALTHY:
                # Bus is back — start recovery confirmation
                if self.recovery_start_time is None:
                    self.recovery_start_time = now
                    self.logger.info("Event bus ping succeeded, starting recovery confirmation")

                elif now - self.recovery_start_time >= self.config.recovery_confirmation_seconds:
                    # Recovery confirmed
                    await self._on_recovery()
            else:
                # Already healthy, reset recovery timer
                self.recovery_start_time = None

            self.last_successful_ping = now
            self.failure_start_time = None
            self.reconnect_attempts = 0

        except (asyncio.TimeoutError, ConnectionError, RedisError):
            now = time.monotonic()

            if self.failure_start_time is None:
                self.failure_start_time = now
                self.recovery_start_time = None

            outage_duration = now - self.failure_start_time
            await self._update_tier(outage_duration)

    async def _update_tier(self, outage_duration: float):
        """Update failure tier based on outage duration."""
        old_tier = self.current_tier

        if outage_duration >= self.config.emergency_threshold_seconds:
            self.current_tier = EventBusFailureTier.EMERGENCY
        elif outage_duration >= self.config.critical_threshold_seconds:
            self.current_tier = EventBusFailureTier.CRITICAL
        elif outage_duration >= self.config.degraded_threshold_seconds:
            self.current_tier = EventBusFailureTier.DEGRADED

        if self.current_tier != old_tier:
            self.logger.warning(
                f"Event bus tier changed: {old_tier.value} → {self.current_tier.value} "
                f"(outage: {outage_duration:.1f}s)"
            )
            self.metrics.set("event_bus.tier", self.current_tier.value)
            await self._on_tier_change(old_tier, self.current_tier)

    async def _on_tier_change(self, old_tier: EventBusFailureTier, new_tier: EventBusFailureTier):
        """Execute actions when tier changes."""
        if new_tier == EventBusFailureTier.DEGRADED:
            # Start buffering events locally
            self.logger.warning("Event bus DEGRADED: buffering events locally")
            self.metrics.increment("event_bus.degraded")

        elif new_tier == EventBusFailureTier.CRITICAL:
            # Stop new trades, manage existing
            self.logger.error("Event bus CRITICAL: stopping new trades, managing existing positions")
            self.metrics.increment("event_bus.critical")
            await self._notify_agents_stop_trading()

        elif new_tier == EventBusFailureTier.EMERGENCY:
            # Close all positions
            self.logger.critical("Event bus EMERGENCY: initiating position close")
            self.metrics.increment("event_bus.emergency")
            await self._close_all_positions()

    async def _on_recovery(self):
        """Handle event bus recovery."""
        old_tier = self.current_tier
        self.current_tier = EventBusFailureTier.HEALTHY
        self.recovery_start_time = None

        self.logger.info(f"Event bus RECOVERED from {old_tier.value}")
        self.metrics.increment("event_bus.recovery")

        # Flush buffered events
        await self._flush_buffer()

        # Reconcile state with event bus
        await self._reconcile_after_recovery()

        # Notify agents they can resume
        await self._notify_agents_resume()

    async def _flush_buffer(self):
        """Flush locally buffered events to the event bus."""
        flushed = 0
        dropped = 0
        start_time = time.monotonic()

        while not self.event_buffer.empty():
            if time.monotonic() - start_time > self.config.buffer_flush_timeout_seconds:
                dropped = self.event_buffer.qsize()
                self.logger.warning(f"Buffer flush timeout, dropping {dropped} events")
                break

            try:
                event = self.event_buffer.get_nowait()
                await self.event_bus.publish(event)
                flushed += 1
            except asyncio.QueueEmpty:
                break
            except Exception as e:
                dropped += 1
                self.logger.error(f"Failed to flush event: {e}")

        self.logger.info(f"Buffer flushed: {flushed} events published, {dropped} dropped")
        self.metrics.set("event_bus.buffer_flushed", flushed)

    async def buffer_event(self, event: dict):
        """Buffer an event locally during bus outage."""
        try:
            self.event_buffer.put_nowait(event)
        except asyncio.QueueFull:
            self.buffer_overflow_count += 1
            if self.buffer_overflow_count % 100 == 0:
                self.logger.warning(f"Event buffer overflow: {self.buffer_overflow_count} events dropped")

    async def _reconnect_loop(self):
        """Attempt to reconnect to event bus."""
        while True:
            if (self.current_tier != EventBusFailureTier.HEALTHY and
                not self.is_reconnecting):

                self.is_reconnecting = True
                try:
                    delay = min(
                        self.config.reconnect_base_delay * (2 ** self.reconnect_attempts),
                        self.config.reconnect_max_delay,
                    )
                    jitter = random.uniform(0, delay * 0.3)
                    await asyncio.sleep(delay + jitter)

                    await self.event_bus.reconnect()
                    self.reconnect_attempts += 1

                except Exception as e:
                    self.reconnect_attempts += 1
                    self.logger.debug(f"Reconnect attempt {self.reconnect_attempts} failed: {e}")

                finally:
                    self.is_reconnecting = False

            await asyncio.sleep(1.0)

    async def _notify_agents_stop_trading(self):
        """Notify all agents to stop new trades."""
        await self.event_bus.publish_local({
            "type": "SYSTEM_COMMAND",
            "command": "STOP_NEW_TRADES",
            "reason": "Event bus critical failure",
        })

    async def _notify_agents_resume(self):
        """Notify all agents to resume trading."""
        await self.event_bus.publish_local({
            "type": "SYSTEM_COMMAND",
            "command": "RESUME_TRADING",
            "reason": "Event bus recovered",
        })

    async def _close_all_positions(self):
        """Close all positions — emergency only."""
        # This calls the existing broker close-all mechanism
        await self.event_bus.publish_local({
            "type": "SYSTEM_COMMAND",
            "command": "CLOSE_ALL_POSITIONS",
            "reason": "Event bus emergency — prolonged outage",
        })

    async def _reconcile_after_recovery(self):
        """Reconcile local state with event bus after recovery."""
        # Fetch any events missed during outage
        missed_events = await self.event_bus.get_missed_events(
            since=self.last_successful_ping
        )
        if missed_events:
            self.logger.info(f"Reconciling {len(missed_events)} missed events")
            for event in missed_events:
                await self.event_bus.replay_event(event)
```

#### 3. Agent-Side Graceful Degradation

```python
class EventBusClient:
    """Client that agents use to interact with the event bus."""

    def __init__(self, event_bus, health_monitor: EventBusHealthMonitor):
        self.event_bus = event_bus
        self.health = health_monitor

    async def publish(self, event: dict, critical: bool = False):
        """Publish event with graceful degradation."""
        if self.health.current_tier == EventBusFailureTier.HEALTHY:
            await self.event_bus.publish(event)
        elif self.health.current_tier == EventBusFailureTier.DEGRADED:
            # Buffer non-critical events, try to publish critical ones
            if critical:
                try:
                    await asyncio.wait_for(self.event_bus.publish(event), timeout=2.0)
                except (asyncio.TimeoutError, Exception):
                    await self.health.buffer_event(event)
            else:
                await self.health.buffer_event(event)
        else:
            # CRITICAL or EMERGENCY — buffer everything
            await self.health.buffer_event(event)

    async def subscribe(self, stream: str, handler: callable):
        """Subscribe with automatic reconnection."""
        # ... subscription with reconnect logic
```

### Impact

- 5-second grace period before entering degraded mode
- Local event buffering preserves events during brief outages
- 30-second threshold before stopping new trades (was: immediate)
- 60-second threshold before closing positions (was: immediate)
- Automatic recovery with event reconciliation
- Gradual recovery: buffer flush → state reconciliation → resume trading

---

## C4 — Circuit Breaker State Persistence

### Problem

Circuit breaker states are stored in memory. A system restart during a drawdown crisis loses all breaker state — the system restarts in GREEN stage and resumes full-size trading during an active drawdown.

### Root Cause

`CircuitBreakerSystem` uses `self.breaker_states = {}` with no persistence.

### Fix: Redis-Backed Circuit Breaker State

#### 1. Define Persistent State Schema

```python
@dataclass
class CircuitBreakerState:
    """Persistent circuit breaker state."""
    breaker_id: str
    layer: str                          # "position", "portfolio", "regime", "system"
    status: str                         # "GREEN", "YELLOW", "ORANGE", "RED"
    tripped_at: Optional[float] = None  # Unix timestamp
    trip_reason: Optional[str] = None
    trip_count: int = 0                 # Number of times tripped
    last_reset_at: Optional[float] = None
    recovery_conditions: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    version: int = 0                    # Optimistic locking

    def to_redis(self) -> dict:
        return {
            "breaker_id": self.breaker_id,
            "layer": self.layer,
            "status": self.status,
            "tripped_at": str(self.tripped_at) if self.tripped_at else "",
            "trip_reason": self.trip_reason or "",
            "trip_count": str(self.trip_count),
            "last_reset_at": str(self.last_reset_at) if self.last_reset_at else "",
            "recovery_conditions": json.dumps(self.recovery_conditions),
            "metadata": json.dumps(self.metadata),
            "version": str(self.version),
        }

    @classmethod
    def from_redis(cls, data: dict) -> 'CircuitBreakerState':
        return cls(
            breaker_id=data["breaker_id"],
            layer=data["layer"],
            status=data["status"],
            tripped_at=float(data["tripped_at"]) if data.get("tripped_at") else None,
            trip_reason=data.get("trip_reason") or None,
            trip_count=int(data.get("trip_count", 0)),
            last_reset_at=float(data["last_reset_at"]) if data.get("last_reset_at") else None,
            recovery_conditions=json.loads(data.get("recovery_conditions", "{}")),
            metadata=json.loads(data.get("metadata", "{}")),
            version=int(data.get("version", 0)),
        )
```

#### 2. Implement PersistentCircuitBreakerStore

```python
class PersistentCircuitBreakerStore:
    """
    Redis-backed circuit breaker state persistence.
    
    Key schema:
      cb:state:{breaker_id} → Hash with breaker state
      cb:active             → Set of currently tripped breaker IDs
      cb:history:{date}     → List of state changes for audit
    """

    REDIS_PREFIX = "cb"
    STATE_TTL = 86400 * 7  # 7 days — auto-cleanup old states

    def __init__(self, redis_client, logger):
        self.redis = redis_client
        self.logger = logger
        self._local_cache: dict[str, CircuitBreakerState] = {}

    async def save_state(self, state: CircuitBreakerState):
        """Save breaker state to Redis with optimistic locking."""
        key = f"{self.REDIS_PREFIX}:state:{state.breaker_id}"

        # Optimistic locking
        current = await self._load_state(state.breaker_id)
        if current and current.version != state.version:
            raise VersionConflictError(
                f"Breaker {state.breaker_id} version conflict: "
                f"expected {state.version}, found {current.version}"
            )

        state.version += 1

        async with self.redis.pipeline(transaction=True) as pipe:
            # Save state
            pipe.hset(key, mapping=state.to_redis())
            pipe.expire(key, self.STATE_TTL)

            # Update active set
            if state.status in ("ORANGE", "RED"):
                pipe.sadd(f"{self.REDIS_PREFIX}:active", state.breaker_id)
            else:
                pipe.srem(f"{self.REDIS_PREFIX}:active", state.breaker_id)

            # Append to history
            history_entry = json.dumps({
                "breaker_id": state.breaker_id,
                "status": state.status,
                "timestamp": time.time(),
                "reason": state.trip_reason,
                "version": state.version,
            })
            date_str = datetime.utcnow().strftime("%Y-%m-%d")
            pipe.rpush(f"{self.REDIS_PREFIX}:history:{date_str}", history_entry)
            pipe.expire(f"{self.REDIS_PREFIX}:history:{date_str}", 86400 * 30)

            await pipe.execute()

        # Update local cache
        self._local_cache[state.breaker_id] = state

        self.logger.info(
            f"Breaker {state.breaker_id} state saved: {state.status} (v{state.version})"
        )

    async def load_state(self, breaker_id: str) -> Optional[CircuitBreakerState]:
        """Load breaker state (with local cache)."""
        if breaker_id in self._local_cache:
            return self._local_cache[breaker_id]
        return await self._load_state(breaker_id)

    async def _load_state(self, breaker_id: str) -> Optional[CircuitBreakerState]:
        """Load breaker state from Redis."""
        key = f"{self.REDIS_PREFIX}:state:{breaker_id}"
        data = await self.redis.hgetall(key)
        if not data:
            return None
        state = CircuitBreakerState.from_redis(data)
        self._local_cache[breaker_id] = state
        return state

    async def load_all_active(self) -> list[CircuitBreakerState]:
        """Load all currently tripped breakers."""
        active_ids = await self.redis.smembers(f"{self.REDIS_PREFIX}:active")
        states = []
        for breaker_id in active_ids:
            state = await self._load_state(breaker_id)
            if state:
                states.append(state)
        return states

    async def load_history(self, date: str) -> list[dict]:
        """Load state change history for a given date."""
        entries = await self.redis.lrange(
            f"{self.REDIS_PREFIX}:history:{date}", 0, -1
        )
        return [json.loads(e) for e in entries]

    def invalidate_cache(self, breaker_id: str):
        """Invalidate local cache for a breaker."""
        self._local_cache.pop(breaker_id, None)
```

#### 3. Integrate with CircuitBreakerSystem

```python
class CircuitBreakerSystem:
    """Updated circuit breaker system with Redis persistence."""

    def __init__(self, redis_client, logger, metrics):
        self.store = PersistentCircuitBreakerStore(redis_client, logger)
        self.logger = logger
        self.metrics = metrics
        self.breakers: dict[str, CircuitBreaker] = {}
        self._loaded_from_persistence = False

    async def initialize(self):
        """Initialize breakers and restore persisted state."""
        # Register all breakers
        self._register_breakers()

        # Load persisted states
        active_states = await self.store.load_all_active()

        if active_states:
            self.logger.warning(
                f"Found {len(active_states)} persisted tripped breakers on startup"
            )
            for state in active_states:
                breaker = self.breakers.get(state.breaker_id)
                if breaker:
                    breaker.restore_state(state)
                    self.logger.warning(
                        f"Restored breaker {state.breaker_id}: {state.status} "
                        f"(tripped {state.trip_reason})"
                    )

        self._loaded_from_persistence = True
        self.logger.info(f"Circuit breaker system initialized with {len(self.breakers)} breakers")

    async def trip_breaker(
        self,
        breaker_id: str,
        reason: str,
        recovery_conditions: Optional[dict] = None,
    ):
        """Trip a breaker and persist the state."""
        breaker = self.breakers.get(breaker_id)
        if not breaker:
            raise ValueError(f"Unknown breaker: {breaker_id}")

        # Trip in memory
        breaker.trip(reason)

        # Persist to Redis
        state = CircuitBreakerState(
            breaker_id=breaker_id,
            layer=breaker.layer,
            status=breaker.status,
            tripped_at=time.time(),
            trip_reason=reason,
            trip_count=breaker.trip_count,
            recovery_conditions=recovery_conditions or {},
            metadata=breaker.metadata,
        )

        await self.store.save_state(state)

        self.metrics.increment("circuit_breaker.tripped", tags={
            "breaker": breaker_id, "layer": breaker.layer
        })

    async def reset_breaker(self, breaker_id: str, reason: str):
        """Reset a breaker and persist the cleared state."""
        breaker = self.breakers.get(breaker_id)
        if not breaker:
            raise ValueError(f"Unknown breaker: {breaker_id}")

        breaker.reset(reason)

        state = CircuitBreakerState(
            breaker_id=breaker_id,
            layer=breaker.layer,
            status="GREEN",
            last_reset_at=time.time(),
            trip_count=breaker.trip_count,
            metadata=breaker.metadata,
        )

        await self.store.save_state(state)

        self.metrics.increment("circuit_breaker.reset", tags={
            "breaker": breaker_id, "layer": breaker.layer
        })

    async def check_recovery(self, breaker_id: str) -> bool:
        """Check if a tripped breaker can be reset."""
        breaker = self.breakers.get(breaker_id)
        if not breaker or breaker.status == "GREEN":
            return True

        state = await self.store.load_state(breaker_id)
        if not state:
            return True

        # Check recovery conditions
        conditions = state.recovery_conditions

        if "min_time_seconds" in conditions:
            elapsed = time.time() - (state.tripped_at or 0)
            if elapsed < conditions["min_time_seconds"]:
                return False

        if "requires_human_approval" in conditions and conditions["requires_human_approval"]:
            if not breaker.human_approved:
                return False

        if "market_conditions" in conditions:
            if not await self._check_market_conditions(conditions["market_conditions"]):
                return False

        return True

    def _register_breakers(self):
        """Register all circuit breakers."""
        # Position-level (Layer 1)
        self.breakers["position_stop_loss"] = CircuitBreaker("position_stop_loss", "position")
        self.breakers["position_trailing_stop"] = CircuitBreaker("position_trailing_stop", "position")

        # Portfolio-level (Layer 2)
        self.breakers["daily_loss"] = CircuitBreaker("daily_loss", "portfolio")
        self.breakers["weekly_loss"] = CircuitBreaker("weekly_loss", "portfolio")
        self.breakers["monthly_loss"] = CircuitBreaker("monthly_loss", "portfolio")
        self.breakers["correlation_spike"] = CircuitBreaker("correlation_spike", "portfolio")

        # Regime-level (Layer 3)
        self.breakers["vix_spike"] = CircuitBreaker("vix_spike", "regime")
        self.breakers["spread_blowout"] = CircuitBreaker("spread_blowout", "regime")
        self.breakers["liquidity_crisis"] = CircuitBreaker("liquidity_crisis", "regime")

        # System-level (Layer 4)
        self.breakers["broker_disconnect"] = CircuitBreaker("broker_disconnect", "system")
        self.breakers["event_bus_failure"] = CircuitBreaker("event_bus_failure", "system")
        self.breakers["data_pipeline_failure"] = CircuitBreaker("data_pipeline_failure", "system")
        self.breakers["signal_quality"] = CircuitBreaker("signal_quality", "system")
```

#### 4. Coordinated Reset with Priority Ordering

```python
class CoordinatedBreakerReset:
    """Ensures breakers reset in the correct order."""

    RESET_PRIORITY = ["system", "regime", "portfolio", "position"]

    async def attempt_reset(self, breaker_system: CircuitBreakerSystem):
        """Attempt to reset all tripped breakers in priority order."""
        active = await breaker_system.store.load_all_active()

        # Group by layer
        by_layer = {}
        for state in active:
            by_layer.setdefault(state.layer, []).append(state)

        # Reset in priority order
        for layer in self.RESET_PRIORITY:
            states = by_layer.get(layer, [])
            for state in states:
                if await breaker_system.check_recovery(state.breaker_id):
                    await breaker_system.reset_breaker(
                        state.breaker_id,
                        reason="Coordinated reset — conditions met"
                    )
                    breaker_system.logger.info(
                        f"Breaker {state.breaker_id} reset (layer: {layer})"
                    )
                else:
                    # If a breaker in a higher-priority layer can't reset,
                    # don't reset lower layers
                    breaker_system.logger.info(
                        f"Breaker {state.breaker_id} cannot reset — blocking lower layers"
                    )
                    return  # Stop — don't reset lower-priority layers
```

### Impact

- Breaker states survive system restarts — crisis state is never forgotten
- Startup loads all active breakers and logs warnings for tripped breakers
- Optimistic locking prevents concurrent modification conflicts
- Full audit trail of all state changes (who tripped, when, why, when reset)
- Coordinated reset prevents premature trading resumption after multi-breaker trips

---

## C5 — Data Pipeline Failure Recovery

### Problem

When the data pipeline fails, the system has undefined behavior. "Fail to last known state" is specified but not implemented — what is "last known state"? How long can the system operate on stale data? When does it halt?

### Root Cause

No data freshness tracking, no stale data policy, no degraded mode definition, no catch-up procedure.

### Fix: Data Pipeline Degraded Mode

#### 1. Define Data Freshness States

```python
class DataFreshnessState(Enum):
    """Freshness state for each data stream."""
    FRESH = "fresh"               # Data is current (< 2× expected interval)
    STALE = "stale"               # Data is old but usable (2-10× expected interval)
    EXPIRED = "expired"           # Data is too old to trade on (10-60× expected interval)
    DEAD = "dead"                 # No data for extended period (> 60× expected interval)

@dataclass
class DataFreshnessConfig:
    """Configuration for data freshness monitoring per stream type."""
    stream_name: str
    expected_interval_seconds: float    # Expected time between updates
    fresh_multiplier: float = 2.0       # 2× expected = stale
    stale_multiplier: float = 10.0      # 10× expected = expired
    dead_multiplier: float = 60.0       # 60× expected = dead
    
    # What to do at each freshness level
    on_stale: str = "alert"             # alert, use_cached, halt
    on_expired: str = "halt_new_trades"  # halt_new_trades, close_positions, use_cached
    on_dead: str = "close_and_halt"     # close_and_halt, halt_all, use_last_known

# Default configurations for each data stream
DATA_FRESHNESS_CONFIGS = {
    "tick_data": DataFreshnessConfig(
        stream_name="tick_data",
        expected_interval_seconds=0.1,
        on_stale="use_cached",
        on_expired="halt_new_trades",
        on_dead="close_and_halt",
    ),
    "candle_1m": DataFreshnessConfig(
        stream_name="candle_1m",
        expected_interval_seconds=60,
        on_stale="use_cached",
        on_expired="halt_new_trades",
        on_dead="close_and_halt",
    ),
    "candle_5m": DataFreshnessConfig(
        stream_name="candle_5m",
        expected_interval_seconds=300,
        on_stale="use_cached",
        on_expired="use_cached",
        on_dead="halt_new_trades",
    ),
    "news_feed": DataFreshnessConfig(
        stream_name="news_feed",
        expected_interval_seconds=300,
        on_stale="alert",
        on_expired="alert",
        on_dead="alert",  # News is supplementary, not critical
    ),
    "economic_calendar": DataFreshnessConfig(
        stream_name="economic_calendar",
        expected_interval_seconds=3600,
        on_stale="alert",
        on_expired="halt_new_trades",
        on_dead="halt_new_trades",
    ),
}
```

#### 2. Implement DataFreshnessMonitor

```python
class DataFreshnessMonitor:
    """
    Monitors data pipeline freshness and triggers degraded mode.
    
    Behavior:
    - FRESH: Normal operation
    - STALE: Use last known data, alert operator
    - EXPIRED: Stop new trades, manage existing with cached data
    - DEAD: Close positions and halt (for critical streams)
    """

    def __init__(self, configs: dict, redis_client, logger, metrics):
        self.configs = configs
        self.redis = redis_client
        self.logger = logger
        self.metrics = metrics

        # Track last update time per stream per pair
        self.last_update: dict[str, dict[str, float]] = {}  # stream → pair → timestamp
        self.last_known_data: dict[str, dict[str, Any]] = {}  # stream → pair → data

        # Current freshness state per stream
        self.stream_states: dict[str, DataFreshnessState] = {}

        # Degraded mode flag
        self.degraded_mode = False
        self.degraded_streams: set[str] = set()

    async def start_monitoring(self):
        """Start the freshness monitoring loop."""
        asyncio.create_task(self._monitor_loop())

    async def _monitor_loop(self):
        """Check freshness every second."""
        while True:
            try:
                await self._check_all_streams()
            except Exception as e:
                self.logger.error(f"Freshness monitor error: {e}")
            await asyncio.sleep(1.0)

    async def record_update(self, stream: str, pair: str, data: Any):
        """Record that a stream received fresh data."""
        now = time.monotonic()

        if stream not in self.last_update:
            self.last_update[stream] = {}
            self.last_known_data[stream] = {}

        self.last_update[stream][pair] = now
        self.last_known_data[stream][pair] = data

        # If this stream was degraded, check if it's recovered
        if stream in self.degraded_streams:
            self.degraded_streams.discard(stream)
            if not self.degraded_streams:
                self.degraded_mode = False
                self.logger.info("Data pipeline: all streams FRESH — degraded mode ended")
                await self._on_recovery()

    async def _check_all_streams(self):
        """Check freshness of all configured streams."""
        now = time.monotonic()

        for stream_name, config in self.configs.items():
            updates = self.last_update.get(stream_name, {})
            if not updates:
                continue

            # Check the oldest update across all pairs
            oldest_update = min(updates.values())
            age_seconds = now - oldest_update
            expected = config.expected_interval_seconds

            # Determine freshness state
            if age_seconds < expected * config.fresh_multiplier:
                new_state = DataFreshnessState.FRESH
            elif age_seconds < expected * config.stale_multiplier:
                new_state = DataFreshnessState.STALE
            elif age_seconds < expected * config.dead_multiplier:
                new_state = DataFreshnessState.EXPIRED
            else:
                new_state = DataFreshnessState.DEAD

            old_state = self.stream_states.get(stream_name)
            self.stream_states[stream_name] = new_state

            if new_state != old_state:
                await self._on_state_change(stream_name, config, old_state, new_state, age_seconds)

    async def _on_state_change(
        self,
        stream: str,
        config: DataFreshnessConfig,
        old_state: Optional[DataFreshnessState],
        new_state: DataFreshnessState,
        age_seconds: float,
    ):
        """Handle freshness state change."""
        self.logger.warning(
            f"Data stream '{stream}' state: {old_state} → {new_state} "
            f"(age: {age_seconds:.1f}s, expected: {config.expected_interval_seconds}s)"
        )
        self.metrics.set(f"data_freshness.{stream}", new_state.value)

        if new_state == DataFreshnessState.STALE:
            action = config.on_stale
        elif new_state == DataFreshnessState.EXPIRED:
            action = config.on_expired
        elif new_state == DataFreshnessState.DEAD:
            action = config.on_dead
        else:
            action = "none"

        if action == "alert":
            self.logger.warning(f"Data stream '{stream}': {new_state.value} — alerting operator")

        elif action == "use_cached":
            self.logger.warning(f"Data stream '{stream}': using cached/last-known data")
            self.degraded_streams.add(stream)
            self.degraded_mode = True

        elif action == "halt_new_trades":
            self.logger.error(f"Data stream '{stream}': halting new trades")
            self.degraded_streams.add(stream)
            self.degraded_mode = True
            await self._command_halt_new_trades(stream)

        elif action == "close_and_halt":
            self.logger.critical(f"Data stream '{stream}': closing positions and halting")
            self.degraded_streams.add(stream)
            self.degraded_mode = True
            await self._command_close_and_halt(stream)

    def get_last_known(self, stream: str, pair: str) -> Optional[Any]:
        """Get the last known data for a stream/pair."""
        return self.last_known_data.get(stream, {}).get(pair)

    def get_freshness_age(self, stream: str, pair: str) -> Optional[float]:
        """Get how old the last known data is in seconds."""
        last = self.last_update.get(stream, {}).get(pair)
        if last is None:
            return None
        return time.monotonic() - last

    async def _on_recovery(self):
        """Handle recovery from degraded mode."""
        self.logger.info("Data pipeline recovered — resuming normal operation")
        self.metrics.increment("data_pipeline.recovery")

    async def _command_halt_new_trades(self, stream: str):
        """Command all agents to halt new trades due to data freshness."""
        self.logger.error(f"HALT NEW TRADES: data stream '{stream}' is stale/expired")

    async def _command_close_and_halt(self, stream: str):
        """Command position close and full halt due to data freshness."""
        self.logger.critical(f"CLOSE AND HALT: data stream '{stream}' is dead")
```

#### 3. Data Pipeline Catch-Up Procedure

```python
class DataPipelineCatchUp:
    """
    Automatic data gap filling after pipeline recovery.
    
    Procedure:
    1. Detect gap boundaries
    2. Fetch missing data from broker API
    3. Validate fetched data (outlier check, gap check)
    4. Fill gaps in TimescaleDB
    5. Recalculate affected indicators
    6. Optionally re-run VMPM pipeline for missed signals
    """

    def __init__(self, broker_client, db_client, indicator_engine, logger, metrics):
        self.broker = broker_client
        self.db = db_client
        self.indicators = indicator_engine
        self.logger = logger
        self.metrics = metrics

    async def catch_up(
        self,
        pair: str,
        timeframe: str,
        gap_start: datetime,
        gap_end: datetime,
        recalculate_signals: bool = False,
    ) -> 'CatchUpResult':
        """Fill a data gap."""
        self.logger.info(
            f"Catch-up started: {pair} {timeframe} from {gap_start} to {gap_end}"
        )

        # Step 1: Fetch missing candles from broker
        try:
            missing_candles = await self.broker.get_historical_candles(
                pair=pair,
                timeframe=timeframe,
                start=gap_start,
                end=gap_end,
            )
        except Exception as e:
            self.logger.error(f"Catch-up fetch failed: {e}")
            return CatchUpResult(success=False, error=str(e))

        if not missing_candles:
            self.logger.info("No missing candles found — gap may already be filled")
            return CatchUpResult(success=True, candles_filled=0)

        # Step 2: Validate fetched data
        validated = self._validate_candles(missing_candles, pair, timeframe)
        if len(validated) < len(missing_candles) * 0.8:
            self.logger.warning(
                f"Catch-up validation: {len(validated)}/{len(missing_candles)} candles valid"
            )

        # Step 3: Insert into TimescaleDB
        inserted = await self.db.insert_candles(pair, timeframe, validated)

        # Step 4: Recalculate indicators for the gap period
        await self.indicators.recalculate(
            pair=pair,
            timeframe=timeframe,
            start=gap_start,
            end=gap_end,
        )

        # Step 5: Optionally re-run VMPM for missed signals
        signals = []
        if recalculate_signals:
            # Only re-run for gaps < 1 hour to avoid expensive re-computation
            gap_duration = (gap_end - gap_start).total_seconds()
            if gap_duration < 3600:
                signals = await self._rerun_vmpm(pair, timeframe, gap_start, gap_end)
            else:
                self.logger.info(
                    f"Gap too large ({gap_duration}s) for signal recalculation"
                )

        result = CatchUpResult(
            success=True,
            candles_filled=inserted,
            candles_validated=len(validated),
            signals_recalculated=len(signals),
        )

        self.logger.info(f"Catch-up complete: {result}")
        self.metrics.increment("data_pipeline.catch_up", tags={"pair": pair})
        return result

    def _validate_candles(self, candles: list, pair: str, timeframe: str) -> list:
        """Validate fetched candles (outlier check, gap check)."""
        validated = []
        for candle in candles:
            # Basic sanity checks
            if candle.high < candle.low:
                continue
            if candle.open == 0 or candle.close == 0:
                continue
            # Additional outlier checks can be added here
            validated.append(candle)
        return validated

    async def _rerun_vmpm(self, pair, timeframe, start, end):
        """Re-run VMPM pipeline for a gap period."""
        # Implementation depends on VMPM pipeline interface
        pass


@dataclass
class CatchUpResult:
    success: bool
    candles_filled: int = 0
    candles_validated: int = 0
    signals_recalculated: int = 0
    error: Optional[str] = None
```

#### 4. Integration with VMPM Pipeline

```python
class DataAwareVMPMPipeline:
    """VMPM pipeline that checks data freshness before executing."""

    def __init__(self, pipeline: VMPMPipelineOrchestrator, freshness: DataFreshnessMonitor):
        self.pipeline = pipeline
        self.freshness = freshness

    async def run(self, context: StrategyContext) -> 'PipelineResult':
        """Run pipeline with data freshness awareness."""
        pair = context.pair

        # Check freshness of critical data streams
        critical_streams = ["candle_1m", "candle_5m", "tick_data"]
        degraded_streams = []

        for stream in critical_streams:
            age = self.freshness.get_freshness_age(stream, pair)
            if age is not None:
                config = self.freshness.configs.get(stream)
                if config and age > config.expected_interval_seconds * config.stale_multiplier:
                    degraded_streams.append(stream)

        if degraded_streams:
            context.add_warning(
                f"Data freshness degraded for: {', '.join(degraded_streams)}. "
                f"Using last known data where possible."
            )

        # Run pipeline (it handles its own per-step errors)
        result = await self.pipeline.run(context)

        # Annotate result with data quality info
        result.data_quality = {
            "degraded_streams": degraded_streams,
            "freshness_states": {
                stream: self.freshness.stream_states.get(stream, DataFreshnessState.FRESH).value
                for stream in critical_streams
            },
        }

        return result
```

### Impact

- Clear data freshness states (FRESH → STALE → EXPIRED → DEAD) with defined behaviors
- STALE data: use cached, alert operator
- EXPIRED data: halt new trades, manage existing
- DEAD data: close positions and halt (for critical streams only)
- Automatic catch-up procedure after recovery with data validation
- VMPM pipeline data-quality-aware — warns about degraded data in reasoning chain

---

## C6 — Infrastructure Disaster Recovery

### Problem

No documented DR for Redis or TimescaleDB. No backup schedule, no HA configuration, no recovery runbooks, no RTO/RPO definitions.

### Root Cause

DR was not addressed in the original architecture — infrastructure was treated as always-available.

### Fix: Complete Infrastructure DR Plan

#### 1. Component RTO/RPO Definitions

| Component | RTO (Recovery Time Objective) | RPO (Recovery Point Objective) | Priority |
|-----------|-------------------------------|--------------------------------|----------|
| **Redis (Event Bus)** | 30 seconds (auto-failover) | 0 (in-memory, accept loss) | P0 |
| **Redis (Breaker State)** | 5 minutes (manual restore) | Last checkpoint (< 1 min) | P0 |
| **TimescaleDB (Market Data)** | 15 minutes | 5 minutes (WAL archiving) | P1 |
| **TimescaleDB (Trade History)** | 15 minutes | 0 (WAL archiving, no loss) | P0 |
| **Application State** | 5 minutes (restart + restore from Redis) | Last checkpoint | P1 |
| **Configuration** | 1 minute (git restore) | 0 (version controlled) | P0 |

#### 2. Redis High Availability

```yaml
# redis-sentinel.conf — Redis Sentinel for automatic failover
# Deploy 3 Sentinel instances (odd number for quorum)

sentinel monitor alphastack-master 127.0.0.1 6379 2
sentinel down-after-milliseconds alphastack-master 5000
sentinel failover-timeout alphastack-master 30000
sentinel parallel-syncs alphastack-master 1

# Redis replication config (on replica)
# redis.conf (replica)
replicaof 192.168.1.10 6379
replica-read-only yes
replica-serve-stale-data yes
```

```python
class RedisHAManager:
    """
    Manages Redis HA with Sentinel.
    
    Architecture:
    - 1 Master (read/write)
    - 2 Replicas (read-only, automatic promotion)
    - 3 Sentinels (monitoring, failover coordination)
    """

    def __init__(self, sentinel_hosts: list[tuple[str, int]], service_name: str = "alphastack"):
        from redis.sentinel import Sentinel
        self.sentinel = Sentinel(sentinel_hosts, socket_timeout=0.5)
        self.service_name = service_name

    def get_master(self):
        """Get connection to current master (for writes)."""
        return self.sentinel.master_for(self.service_name, socket_timeout=0.5)

    def get_replica(self):
        """Get connection to a replica (for reads)."""
        return self.sentinel.slave_for(self.service_name, socket_timeout=0.5)

    async def health_check(self) -> dict:
        """Check health of all Redis nodes."""
        try:
            master = self.get_master()
            master_info = master.info("replication")

            replicas = self.sentinel.discover_slaves(self.service_name)

            return {
                "master": {
                    "host": master_info.get("master_host"),
                    "port": master_info.get("master_port"),
                    "status": "connected",
                },
                "replicas": [
                    {"host": r[0], "port": r[1], "status": "available"}
                    for r in replicas
                ],
                "sentinels": len(self.sentinel.sentinels),
                "overall": "healthy" if len(replicas) >= 1 else "degraded",
            }
        except Exception as e:
            return {"overall": "unhealthy", "error": str(e)}
```

#### 3. TimescaleDB Backup & Recovery

```bash
#!/bin/bash
# timescaledb_backup.sh — Daily backup with WAL archiving

# Configuration
BACKUP_DIR="/var/backups/timescaledb"
WAL_ARCHIVE_DIR="/var/backups/timescaledb/wal"
RETENTION_DAYS=30
DB_NAME="alphastack"
DB_HOST="localhost"
DB_PORT="5432"
DB_USER="alphastack_backup"

# Create backup directory
mkdir -p "$BACKUP_DIR" "$WAL_ARCHIVE_DIR"

# Daily full backup (pg_basebackup)
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_PATH="$BACKUP_DIR/full_$DATE"

echo "[$(date)] Starting full backup..."
pg_basebackup -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" \
    -D "$BACKUP_PATH" -Ft -z -P --wal-method=stream

if [ $? -eq 0 ]; then
    echo "[$(date)] Backup successful: $BACKUP_PATH"
    
    # Verify backup integrity
    pg_verifybackup "$BACKUP_PATH"
    
    # Clean old backups
    find "$BACKUP_DIR" -name "full_*" -mtime +$RETENTION_DAYS -exec rm -rf {} \;
    echo "[$(date)] Cleaned backups older than $RETENTION_DAYS days"
else
    echo "[$(date)] BACKUP FAILED" >&2
    # Send alert
    curl -X POST "$ALERT_WEBHOOK" -d '{"text": "TimescaleDB backup FAILED"}'
fi

# Continuous WAL archiving (configure in postgresql.conf)
# archive_mode = on
# archive_command = 'cp %p /var/backups/timescaledb/wal/%f'
# archive_timeout = 300  # Force WAL switch every 5 minutes
```

```sql
-- postgresql.conf additions for WAL archiving
-- Add these to your postgresql.conf

-- WAL Archiving
archive_mode = on
archive_command = 'test ! -f /var/backups/timescaledb/wal/%f && cp %p /var/backups/timescaledb/wal/%f'
archive_timeout = 300

-- Replication (for standby server)
max_wal_senders = 3
wal_level = replica

-- Recovery settings (on standby)
-- standby_mode = 'on'
-- primary_conninfo = 'host=192.168.1.10 port=5432 user=replicator'
-- restore_command = 'cp /var/backups/timescaledb/wal/%f %p'
```

```python
class TimescaleDBRecoveryManager:
    """Manages TimescaleDB backup verification and recovery."""

    def __init__(self, db_config, backup_dir: str, logger):
        self.config = db_config
        self.backup_dir = backup_dir
        self.logger = logger

    async def verify_backup(self, backup_path: str) -> bool:
        """Verify backup integrity."""
        try:
            result = subprocess.run(
                ["pg_verifybackup", backup_path],
                capture_output=True, text=True, timeout=300,
            )
            if result.returncode == 0:
                self.logger.info(f"Backup verified: {backup_path}")
                return True
            else:
                self.logger.error(f"Backup verification failed: {result.stderr}")
                return False
        except Exception as e:
            self.logger.error(f"Backup verification error: {e}")
            return False

    async def restore_point_in_time(
        self,
        target_time: datetime,
        backup_path: str,
        wal_archive_dir: str,
    ) -> bool:
        """Restore database to a specific point in time."""
        self.logger.info(f"Starting PITR restore to {target_time}")

        # Step 1: Stop the database
        await self._stop_database()

        # Step 2: Restore base backup
        await self._restore_base_backup(backup_path)

        # Step 3: Create recovery.signal and configure recovery
        recovery_conf = f"""
restore_command = 'cp {wal_archive_dir}/%f %p'
recovery_target_time = '{target_time.isoformat()}'
recovery_target_action = 'promote'
"""
        recovery_path = os.path.join(self.config.data_dir, "recovery.signal")
        with open(recovery_path, "w") as f:
            f.write("")

        postgres_conf = os.path.join(self.config.data_dir, "postgresql.auto.conf")
        with open(postgres_conf, "a") as f:
            f.write(recovery_conf)

        # Step 4: Start database
        await self._start_database()

        # Step 5: Verify recovery
        if await self._verify_recovery(target_time):
            self.logger.info(f"PITR restore successful to {target_time}")
            return True
        else:
            self.logger.error("PITR restore verification failed")
            return False

    async def _verify_recovery(self, target_time: datetime) -> bool:
        """Verify that recovery reached the target time."""
        try:
            async with self.config.get_connection() as conn:
                row = await conn.fetchrow("SELECT max(time) FROM candles")
                if row and row[0]:
                    recovered_time = row[0]
                    # Allow 1 minute tolerance
                    if abs((recovered_time - target_time).total_seconds()) < 60:
                        return True
            return False
        except Exception:
            return False

    async def _stop_database(self):
        """Stop PostgreSQL."""
        subprocess.run(["systemctl", "stop", "postgresql"], check=True)

    async def _start_database(self):
        """Start PostgreSQL."""
        subprocess.run(["systemctl", "start", "postgresql"], check=True)

    async def _restore_base_backup(self, backup_path: str):
        """Restore base backup."""
        data_dir = self.config.data_dir
        # Clear existing data
        shutil.rmtree(data_dir)
        # Extract backup
        subprocess.run(["tar", "-xzf", f"{backup_path}/base.tar.gz", "-C", data_dir], check=True)
        # Extract WAL
        subprocess.run(["tar", "-xzf", f"{backup_path}/pg_wal.tar.gz", "-C", f"{data_dir}/pg_wal"], check=True)
```

#### 4. Full System Restart Runbook

```python
class SystemRestartProcedure:
    """
    Documented and automated full system restart procedure.
    
    Cold Start Sequence:
    1. Verify infrastructure (Redis, DB, network)
    2. Load persisted circuit breaker states
    3. Check data pipeline freshness
    4. Reconcile positions with broker
    5. Run in paper-trade mode for 15 minutes
    6. Resume live trading (if all checks pass)
    """

    RESTART_PHASES = [
        "INFRASTRUCTURE_CHECK",
        "STATE_RECOVERY",
        "DATA_VALIDATION",
        "POSITION_RECONCILIATION",
        "PAPER_TRADE_VALIDATION",
        "LIVE_RESUME",
    ]

    def __init__(self, redis_ha, db_recovery, circuit_breaker_system,
                 data_freshness, broker_reconciliation, logger):
        self.redis = redis_ha
        self.db = db_recovery
        self.breakers = circuit_breaker_system
        self.data = data_freshness
        self.broker = broker_reconciliation
        self.logger = logger

    async def execute_restart(self) -> 'RestartResult':
        """Execute the full restart procedure."""
        self.logger.info("=== SYSTEM RESTART PROCEDURE STARTED ===")
        result = RestartResult()

        try:
            # Phase 1: Infrastructure Check
            result.phase = "INFRASTRUCTURE_CHECK"
            infra_ok = await self._check_infrastructure()
            if not infra_ok:
                result.success = False
                result.error = "Infrastructure check failed"
                return result

            # Phase 2: State Recovery
            result.phase = "STATE_RECOVERY"
            await self.breakers.initialize()
            tripped = await self.breakers.store.load_all_active()
            if tripped:
                result.warnings.append(
                    f"{len(tripped)} circuit breakers still tripped from previous session"
                )

            # Phase 3: Data Validation
            result.phase = "DATA_VALIDATION"
            data_ok = await self._validate_data()
            if not data_ok:
                result.warnings.append("Data pipeline has gaps — catch-up required")

            # Phase 4: Position Reconciliation
            result.phase = "POSITION_RECONCILIATION"
            recon_result = await self.broker.reconcile_all()
            if recon_result.discrepancies > 0:
                result.warnings.append(
                    f"{recon_result.discrepancies} position discrepancies found and corrected"
                )

            # Phase 5: Paper Trade Validation
            result.phase = "PAPER_TRADE_VALIDATION"
            self.logger.info("Entering paper-trade validation mode (15 minutes)")
            paper_ok = await self._paper_trade_validation(duration_minutes=15)
            if not paper_ok:
                result.success = False
                result.error = "Paper trade validation failed"
                return result

            # Phase 6: Live Resume
            result.phase = "LIVE_RESUME"
            self.logger.info("All checks passed — resuming live trading")
            result.success = True

        except Exception as e:
            result.success = False
            result.error = f"Restart failed at phase {result.phase}: {e}"
            self.logger.error(result.error)

        return result

    async def _check_infrastructure(self) -> bool:
        """Verify all infrastructure components."""
        checks = {
            "redis": await self.redis.health_check(),
            "database": await self.db.health_check(),
        }

        all_ok = True
        for component, health in checks.items():
            if health.get("overall") != "healthy":
                self.logger.error(f"Infrastructure check failed: {component} — {health}")
                all_ok = False

        return all_ok

    async def _validate_data(self) -> bool:
        """Validate data pipeline is healthy."""
        # Check freshness of all critical streams
        for stream in ["candle_1m", "candle_5m"]:
            state = self.data.stream_states.get(stream)
            if state in (DataFreshnessState.EXPIRED, DataFreshnessState.DEAD):
                return False
        return True

    async def _paper_trade_validation(self, duration_minutes: int) -> bool:
        """Run in paper-trade mode for validation."""
        start = time.monotonic()
        errors = 0

        while time.monotonic() - start < duration_minutes * 60:
            # Check that pipeline runs without errors
            # Check that broker connection is stable
            # Check that data is flowing
            await asyncio.sleep(60)

            # Check for any critical errors
            if self._has_critical_errors():
                errors += 1
                if errors >= 3:
                    return False

        return True

    def _has_critical_errors(self) -> bool:
        """Check for critical errors during paper trade."""
        # Implementation depends on error tracking system
        return False


@dataclass
class RestartResult:
    success: bool = False
    phase: str = ""
    warnings: list[str] = field(default_factory=list)
    error: Optional[str] = None
```

#### 5. Backup Verification Script

```bash
#!/bin/bash
# backup_verify.sh — Verify backup integrity and test restore

BACKUP_DIR="/var/backups/timescaledb"
TEST_RESTORE_DIR="/tmp/pg_restore_test"
DB_NAME="alphastack"

echo "=== Backup Verification $(date) ==="

# Find latest backup
LATEST_BACKUP=$(ls -t "$BACKUP_DIR"/full_* 2>/dev/null | head -1)
if [ -z "$LATEST_BACKUP" ]; then
    echo "ERROR: No backups found"
    exit 1
fi

echo "Latest backup: $LATEST_BACKUP"

# Verify backup integrity
echo "Verifying backup integrity..."
pg_verifybackup "$LATEST_BACKUP"
if [ $? -ne 0 ]; then
    echo "ERROR: Backup verification failed"
    exit 1
fi

# Test restore to temporary directory
echo "Testing restore to $TEST_RESTORE_DIR..."
mkdir -p "$TEST_RESTORE_DIR"
pg_basebackup -D "$TEST_RESTORE_DIR" --from-backup="$LATEST_BACKUP"

if [ $? -eq 0 ]; then
    echo "Restore test passed"
    
    # Start temporary instance and verify data
    pg_ctl -D "$TEST_RESTORE_DIR" start
    sleep 5
    
    # Check table counts
    CANDLE_COUNT=$(psql -h /tmp -d "$DB_NAME" -t -c "SELECT count(*) FROM candles")
    TRADE_COUNT=$(psql -h /tmp -d "$DB_NAME" -t -c "SELECT count(*) FROM trades")
    
    echo "Verification results:"
    echo "  Candles: $CANDLE_COUNT"
    echo "  Trades: $TRADE_COUNT"
    
    # Stop temporary instance
    pg_ctl -D "$TEST_RESTORE_DIR" stop
    rm -rf "$TEST_RESTORE_DIR"
    
    echo "=== Verification PASSED ==="
else
    echo "ERROR: Restore test failed"
    rm -rf "$TEST_RESTORE_DIR"
    exit 1
fi
```

#### 6. Network Partition Handling

```python
class NetworkPartitionHandler:
    """
    Handles network partition scenarios to prevent split-brain decisions.
    
    Strategy: Fencing
    - Only the agent that holds the "fencing token" can execute trades
    - Token is acquired from Redis (which is HA via Sentinel)
    - If you can't reach Redis, you can't trade
    """

    FENCING_KEY = "alphastack:fencing_token"
    FENCING_TTL = 30  # Must renew every 30 seconds

    def __init__(self, redis_client, agent_id: str, logger):
        self.redis = redis_client
        self.agent_id = agent_id
        self.logger = logger
        self.has_token = False

    async def acquire_fencing_token(self) -> bool:
        """Attempt to acquire the fencing token."""
        try:
            acquired = await self.redis.set(
                self.FENCING_KEY,
                self.agent_id,
                nx=True,  # Only if not exists
                ex=self.FENCING_TTL,
            )
            self.has_token = bool(acquired)
            if self.has_token:
                self.logger.info(f"Acquired fencing token: {self.agent_id}")
            return self.has_token
        except Exception as e:
            self.logger.error(f"Failed to acquire fencing token: {e}")
            self.has_token = False
            return False

    async def renew_fencing_token(self) -> bool:
        """Renew the fencing token (must be called periodically)."""
        if not self.has_token:
            return await self.acquire_fencing_token()

        try:
            # Use Lua script for atomic check-and-renew
            script = """
            if redis.call("GET", KEYS[1]) == ARGV[1] then
                return redis.call("EXPIRE", KEYS[1], ARGV[2])
            else
                return 0
            end
            """
            result = await self.redis.eval(
                script, 1, self.FENCING_KEY, self.agent_id, self.FENCING_TTL
            )
            if not result:
                self.has_token = False
                self.logger.warning("Lost fencing token — another instance may have taken over")
                return False
            return True
        except Exception as e:
            self.logger.error(f"Failed to renew fencing token: {e}")
            self.has_token = False
            return False

    async def can_trade(self) -> bool:
        """Check if this instance is allowed to trade."""
        if not self.has_token:
            return await self.acquire_fencing_token()
        return await self.renew_fencing_token()

    async def release_fencing_token(self):
        """Release the fencing token (graceful shutdown)."""
        try:
            script = """
            if redis.call("GET", KEYS[1]) == ARGV[1] then
                return redis.call("DEL", KEYS[1])
            else
                return 0
            end
            """
            await self.redis.eval(script, 1, self.FENCING_KEY, self.agent_id)
            self.has_token = False
            self.logger.info("Released fencing token")
        except Exception:
            pass
```

#### 7. Credential Rotation & Incident Response

```python
class CredentialRotationManager:
    """Manages credential rotation and incident response."""

    def __init__(self, secret_store, alert_manager, logger):
        self.secrets = secret_store
        self.alerts = alert_manager
        self.logger = logger

    async def rotate_broker_credentials(self, broker: str, new_credentials: dict):
        """Rotate broker API credentials."""
        self.logger.info(f"Rotating credentials for broker: {broker}")

        # 1. Store new credentials (but don't activate yet)
        await self.secrets.store(f"broker:{broker}:new", new_credentials)

        # 2. Test new credentials
        test_ok = await self._test_broker_credentials(broker, new_credentials)
        if not test_ok:
            await self.secrets.delete(f"broker:{broker}:new")
            raise CredentialTestFailed(f"New credentials for {broker} failed validation")

        # 3. Activate new credentials
        old_creds = await self.secrets.get(f"broker:{broker}:current")
        await self.secrets.rename(f"broker:{broker}:new", f"broker:{broker}:current")

        # 4. Reconnect broker with new credentials
        await self._reconnect_broker(broker)

        # 5. Verify connection
        await self._verify_broker_connection(broker)

        self.logger.info(f"Credentials rotated for broker: {broker}")

    async def emergency_credential_revoke(self, reason: str):
        """Emergency: revoke all API credentials immediately."""
        self.logger.critical(f"EMERGENCY CREDENTIAL REVOCATION: {reason}")

        # 1. Alert operator
        await self.alerts.send_critical(
            f"EMERGENCY: All API credentials revoked. Reason: {reason}"
        )

        # 2. Close all positions
        await self._emergency_close_all()

        # 3. Revoke all broker API keys
        brokers = await self.secrets.list_brokers()
        for broker in brokers:
            try:
                await self._revoke_broker_key(broker)
            except Exception as e:
                self.logger.error(f"Failed to revoke {broker} key: {e}")

        # 4. Rotate all internal secrets
        await self._rotate_internal_secrets()

        # 5. Enter safe mode
        self.logger.critical("System entered SAFE MODE — all trading halted")
```

### Impact

- Redis Sentinel provides automatic failover (30s RTO)
- TimescaleDB daily backups with WAL archiving for point-in-time recovery
- Automated backup verification with test restores
- Documented and automated cold-start procedure (6 phases)
- Network partition fencing prevents split-brain trading decisions
- Credential rotation and emergency revocation procedures

---

## Implementation Checklist

### C1 — VMPM Pipeline Error Handling
- [ ] Define `FailureStrategy` enum
- [ ] Define `StepConfig` dataclass with per-step configuration
- [ ] Implement `StepErrorHandler` with timeout, retry, and fallback
- [ ] Update `VMPMStep` base class with validation contract
- [ ] Implement `VMPMPipelineOrchestrator` with per-step error handling
- [ ] Define default `STEP_CONFIGS` for all 16 pipeline steps
- [ ] Add reasoning chain logging for all fallbacks
- [ ] Add signal quality circuit breaker (from review H4)

### C2 — LLM API Failure Handling
- [ ] Define `LLMErrorCode` and `LLMResponse` types
- [ ] Implement `LLMCallWrapper` with retry + backoff
- [ ] Implement `ProviderCircuitBreaker` per LLM provider
- [ ] Add JSON schema validation for structured responses
- [ ] Configure fallback chain (DeepSeek → Qwen → local)
- [ ] Add stale cache fallback as last resort
- [ ] Integrate with all LLM-using agents

### C3 — Event Bus Grace Period
- [ ] Define `EventBusFailureTier` enum (HEALTHY → DEGRADED → CRITICAL → EMERGENCY)
- [ ] Implement `EventBusHealthMonitor` with tiered response
- [ ] Add local event buffer for brief outages
- [ ] Implement reconnection loop with exponential backoff
- [ ] Add recovery confirmation (must be healthy for 10s)
- [ ] Implement buffer flush on recovery
- [ ] Add agent-side `EventBusClient` with graceful degradation

### C4 — Circuit Breaker Persistence
- [ ] Define `CircuitBreakerState` with Redis serialization
- [ ] Implement `PersistentCircuitBreakerStore` with optimistic locking
- [ ] Update `CircuitBreakerSystem` to load/save states on change
- [ ] Add startup state restoration with warning logging
- [ ] Implement `CoordinatedBreakerReset` with priority ordering
- [ ] Add audit trail (history per day)

### C5 — Data Pipeline Failure Recovery
- [ ] Define `DataFreshnessState` enum
- [ ] Define `DataFreshnessConfig` per stream type
- [ ] Implement `DataFreshnessMonitor` with state machine
- [ ] Define actions per freshness level (alert / use_cached / halt / close)
- [ ] Implement `DataPipelineCatchUp` with broker API fetch
- [ ] Add data validation during catch-up
- [ ] Integrate freshness awareness into VMPM pipeline

### C6 — Infrastructure DR
- [ ] Deploy Redis Sentinel (3 sentinels, 1 master, 2 replicas)
- [ ] Implement `RedisHAManager` with Sentinel integration
- [ ] Configure TimescaleDB WAL archiving
- [ ] Create daily backup script with verification
- [ ] Implement `TimescaleDBRecoveryManager` with PITR
- [ ] Create backup verification script
- [ ] Implement `SystemRestartProcedure` (6-phase cold start)
- [ ] Implement `NetworkPartitionHandler` with fencing
- [ ] Implement `CredentialRotationManager`
- [ ] Document RTO/RPO per component

---

## Risk Assessment Post-Fix

| Scenario | Before Fix | After Fix |
|----------|-----------|-----------|
| LLM timeout during NFP | Pipeline stalls indefinitely | Retries 3×, falls back to cache, continues pipeline |
| Redis blip | All positions closed | 5s degraded mode with buffering, auto-recovery |
| System restart during drawdown | Forgets crisis, resumes full trading | Loads persisted breaker states, warns operator |
| Data pipeline stops | Trades on stale/missing data | Freshness monitoring, halt new trades on expiry |
| LLM provider outage | All agents crash silently | Per-provider circuit breaker, fallback chain |
| Network partition | Split-brain trading decisions | Fencing token prevents unauthorized trading |

---

## Priority Order for Implementation

```
Phase 1 (Core Safety — implement first):
├── C4: Circuit breaker persistence (prevents restart-during-crisis bug)
├── C3: Event bus grace period (prevents unnecessary position closures)
└── C2: LLM API failure handling (prevents agent crashes)

Phase 2 (Pipeline Resilience):
├── C1: VMPM pipeline error handling (prevents pipeline stalls)
└── C5: Data pipeline failure recovery (prevents stale data trading)

Phase 3 (Infrastructure):
└── C6: Infrastructure DR (prevents total system loss)
```

---

*"Errors are inevitable. Catastrophic failure is not."*

---

> **Document maintained by:** Error Handling Fix Agent  
> **Source:** `review_error_handling.md` — Critical gaps C1–C6  
> **Next review:** After implementation, validate with chaos testing
