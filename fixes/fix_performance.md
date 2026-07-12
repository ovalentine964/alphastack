# Alpha Stack — Performance Fix Specification

> **Author:** Performance Fix Agent  
> **Date:** 2026-07-11  
> **Input:** `review_performance.md` — Critical findings #1 (LLM latency), #2 (memory management), #3 (WebSocket underspecified)  
> **Scope:** Detailed implementation specs, code patterns, configuration, and acceptance criteria for each fix

---

## Table of Contents

1. [Fix #1: Move LLM Calls Off the Critical Path](#fix-1-move-llm-calls-off-the-critical-path)
2. [Fix #2: Memory Management for 24/7 Operation](#fix-2-memory-management-for-247-operation)
3. [Fix #3: WebSocket Performance Specification](#fix-3-websocket-performance-specification)
4. [Integration & Testing](#integration--testing)

---

## Fix #1: Move LLM Calls Off the Critical Path

### Problem

LLM API calls (DeepSeek, Qwen) in AlphaStack Steps 1–2 add **200–2000ms** of non-deterministic latency directly on the tick-to-order critical path. API timeouts can blow the 5s target entirely.

### Architecture Change

**Before (current):**
```
Tick → Step 1 (LLM: Fundamental) → Step 2 (LLM: Sentiment) → Steps 3-16 → Order
         ~500-2000ms                  ~500-2000ms               ~100-200ms
Total: ~1100-4200ms (LLM-dominated)
```

**After (fixed):**
```
┌──────────────────────────────────────────────────────────┐
│  PRE-COMPUTE LAYER (async, off critical path)            │
│                                                          │
│  ┌─────────────────────┐  ┌─────────────────────────┐   │
│  │ Fundamental Worker   │  │ Sentiment Worker         │   │
│  │ (every 4h per pair)  │  │ (every 1h per pair)      │   │
│  │                      │  │                          │   │
│  │ LLM call → parse →   │  │ LLM call → parse →      │   │
│  │ cache in Redis        │  │ cache in Redis           │   │
│  │ TTL: 4h               │  │ TTL: 1h                  │   │
│  └──────────┬───────────┘  └──────────┬──────────────┘   │
│             │                         │                   │
│             └────────┬────────────────┘                   │
│                      ▼                                    │
│            Redis: cache:fundamental:{pair}                │
│            Redis: cache:sentiment:{pair}                  │
│            Redis: cache:bias:{pair}                       │
└──────────────────────────────────────────────────────────┘

Tick → Read cached values (≤1ms) → Steps 3-16 (computed) → Order
        ~100-200ms total
```

### 1.1 Pre-Compute Worker Specification

#### 1.1.1 Worker Architecture

```python
# alpha/workers/precompute.py

import asyncio
import json
import time
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Optional

import redis.asyncio as aioredis

class PrecomputeType(Enum):
    FUNDAMENTAL = "fundamental"
    SENTIMENT = "sentiment"
    BIAS = "bias"

@dataclass
class PrecomputeResult:
    pair: str
    compute_type: PrecomputeType
    value: dict              # LLM parsed output
    confidence: float        # 0.0 - 1.0
    computed_at: float       # epoch seconds
    ttl_seconds: int
    model: str               # which LLM model produced this
    latency_ms: float        # how long the LLM call took

    @property
    def is_expired(self) -> bool:
        return time.time() > (self.computed_at + self.ttl_seconds)

    @property
    def cache_key(self) -> str:
        return f"cache:{self.compute_type.value}:{self.pair}"

    def to_cache_value(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_cache(cls, raw: str) -> "PrecomputeResult":
        d = json.loads(raw)
        d["compute_type"] = PrecomputeType(d["compute_type"])
        return cls(**d)
```

#### 1.1.2 LLM Call Wrapper with Timeout + Fallback

```python
# alpha/workers/llm_client.py

import asyncio
import time
import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger("precompute.llm")

@dataclass
class LLMConfig:
    model: str
    base_url: str
    api_key: str
    timeout_seconds: float = 5.0       # hard timeout per call
    max_tokens: int = 1024             # keep responses small
    temperature: float = 0.1
    max_retries: int = 2               # 3 total attempts
    retry_delay_base: float = 1.0      # exponential backoff base

class LLMClient:
    """Async LLM client with strict timeouts and circuit breaking."""

    def __init__(self, config: LLMConfig):
        self.config = config
        self._consecutive_failures = 0
        self._circuit_open_until: float = 0

    async def call(self, prompt: str) -> tuple[Optional[str], float]:
        """
        Returns (response_text, latency_ms) or (None, latency_ms) on failure.
        Never raises — always returns gracefully.
        """
        # Circuit breaker: skip if too many consecutive failures
        if time.time() < self._circuit_open_until:
            logger.warning("LLM circuit open, skipping call")
            return None, 0.0

        latency_ms = 0.0
        for attempt in range(self.config.max_retries + 1):
            start = time.monotonic()
            try:
                response = await asyncio.wait_for(
                    self._raw_call(prompt),
                    timeout=self.config.timeout_seconds,
                )
                latency_ms = (time.monotonic() - start) * 1000
                self._consecutive_failures = 0
                return response, latency_ms
            except asyncio.TimeoutError:
                latency_ms = (time.monotonic() - start) * 1000
                logger.warning(f"LLM timeout (attempt {attempt+1}): {latency_ms:.0f}ms")
            except Exception as e:
                latency_ms = (time.monotonic() - start) * 1000
                logger.warning(f"LLM error (attempt {attempt+1}): {e}")

            self._consecutive_failures += 1
            if self._consecutive_failures >= 5:
                self._circuit_open_until = time.time() + 60  # open for 60s
                logger.error("LLM circuit breaker OPEN — 5 consecutive failures")
                break

            if attempt < self.config.max_retries:
                delay = self.config.retry_delay_base * (2 ** attempt)
                await asyncio.sleep(delay)

        return None, latency_ms

    async def _raw_call(self, prompt: str) -> str:
        """Actual HTTP call to LLM API — implement with httpx or openai SDK."""
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.config.base_url}/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.config.api_key}"},
                json={
                    "model": self.config.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": self.config.max_tokens,
                    "temperature": self.config.temperature,
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
```

#### 1.1.3 Pre-Compute Scheduler

```python
# alpha/workers/scheduler.py

import asyncio
import logging
import time
from typing import Callable, Awaitable

logger = logging.getLogger("precompute.scheduler")

class PrecomputeScheduler:
    """
    Schedules pre-computation jobs with jitter to avoid thundering herd.
    Each job runs at its configured interval with ±10% random jitter.
    """

    def __init__(self, redis: "aioredis.Redis"):
        self.redis = redis
        self._tasks: list[asyncio.Task] = []
        self._running = False

    def register(
        self,
        name: str,
        pairs: list[str],
        interval_seconds: int,
        compute_fn: Callable[[str], Awaitable[dict]],
    ):
        """Register a precompute job for all pairs."""
        task = asyncio.create_task(
            self._run_loop(name, pairs, interval_seconds, compute_fn)
        )
        self._tasks.append(task)

    async def _run_loop(
        self,
        name: str,
        pairs: list[str],
        interval: int,
        compute_fn: Callable[[str], Awaitable[dict]],
    ):
        import random
        while True:
            for pair in pairs:
                try:
                    result = await compute_fn(pair)
                    await self._store(name, pair, result)
                except Exception as e:
                    logger.error(f"Precompute {name}/{pair} failed: {e}")
                    # Record failure metric
                    await self._record_failure(name, pair, str(e))

            # Jitter: ±10% of interval
            jitter = interval * 0.1 * (2 * random.random() - 1)
            await asyncio.sleep(interval + jitter)

    async def _store(self, name: str, pair: str, result: dict):
        key = f"cache:{name}:{pair}"
        await self.redis.set(key, json.dumps(result), ex=result.get("ttl", 3600))

    async def _record_failure(self, name: str, pair: str, error: str):
        key = f"cache:failures:{name}:{pair}"
        await self.redis.lpush(key, json.dumps({
            "error": error,
            "timestamp": time.time(),
        }))
        await self.redis.ltrim(key, 0, 9)  # keep last 10 failures
```

#### 1.1.4 Cache Reader (Hot Path)

```python
# alpha/alphastack/cache_reader.py

import json
import time
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("alphastack.cache")

@dataclass
class CachedValue:
    value: dict
    confidence: float
    age_seconds: float
    is_stale: bool       # >80% of TTL elapsed
    is_expired: bool     # >100% of TTL elapsed

class PrecomputeCacheReader:
    """
    Reads pre-computed values on the hot path.
    Designed for ≤1ms latency — never blocks, never calls LLM.
    """

    def __init__(self, redis: "aioredis.Redis"):
        self.redis = redis
        self._local_cache: dict[str, tuple[float, dict]] = {}  # hot local cache
        self._local_ttl = 5.0  # seconds — avoids Redis roundtrip every tick

    async def get(self, compute_type: str, pair: str) -> Optional[CachedValue]:
        """
        Read cached pre-compute result. Returns None if missing/expired.
        Uses local cache to minimize Redis roundtrips.
        """
        cache_key = f"cache:{compute_type}:{pair}"

        # Check local cache first (in-process, ~0.01ms)
        if cache_key in self._local_cache:
            ts, raw = self._local_cache[cache_key]
            if time.time() - ts < self._local_ttl:
                return self._parse(raw)

        # Fallback to Redis (~0.5-1ms)
        try:
            raw = await self.redis.get(cache_key)
            if raw is None:
                return None
            if isinstance(raw, bytes):
                raw = raw.decode()
            self._local_cache[cache_key] = (time.time(), json.loads(raw))
            return self._parse(json.loads(raw))
        except Exception as e:
            logger.warning(f"Cache read failed for {cache_key}: {e}")
            return None

    def _parse(self, data: dict) -> CachedValue:
        age = time.time() - data.get("computed_at", 0)
        ttl = data.get("ttl_seconds", 3600)
        return CachedValue(
            value=data.get("value", {}),
            confidence=data.get("confidence", 0.0),
            age_seconds=age,
            is_stale=age > ttl * 0.8,
            is_expired=age > ttl,
        )

    def invalidate_local(self, compute_type: str, pair: str):
        """Force local cache miss — called when fresh data is pushed."""
        cache_key = f"cache:{compute_type}:{pair}"
        self._local_cache.pop(cache_key, None)
```

#### 1.1.5 TTL Configuration

| Precompute Type | TTL | Refresh Interval | Pairs (Phase 1) | LLM Calls/Day |
|----------------|-----|-----------------|-----------------|----------------|
| `fundamental` | 4h | 3h (refresh before expiry) | 1 | ~8 |
| `sentiment` | 1h | 45m | 1 | ~32 |
| `bias` | 1h | 45m | 1 | ~32 |
| **Total** | — | — | — | **~72/day** |

At Phase 3 (10 pairs): **~720 LLM calls/day** = ~0.5 calls/min average. Well within rate limits.

### 1.2 Pipeline Latency Budgets

#### Per-Step Budget Allocation

```yaml
# alpha/config/latency_budgets.yaml

pipeline:
  total_budget_ms: 2000        # hard cutoff — abort if exceeded
  warning_threshold_ms: 1000   # log warning if exceeded

  steps:
    # Steps 1-2: CACHE READ ONLY (pre-computed off critical path)
    - name: "fundamental_context"
      budget_ms: 5             # cache read only
      type: "cache_read"
      cache_key: "fundamental"

    - name: "market_bias"
      budget_ms: 5             # cache read only
      type: "cache_read"
      cache_key: "bias"

    # Steps 3-4: Context (parallel group)
    - name: "regime_detection"
      budget_ms: 20
      type: "compute"
      parallel_group: "context"

    - name: "volatility_analysis"
      budget_ms: 15
      type: "compute"
      parallel_group: "context"

    # Steps 5-8: Structure (parallel group)
    - name: "sr_detection"
      budget_ms: 30
      type: "compute"
      parallel_group: "structure"

    - name: "orderflow_analysis"
      budget_ms: 25
      type: "compute"
      parallel_group: "structure"

    - name: "indicator_suite"        # RSI, MACD, ATR, etc.
      budget_ms: 20
      type: "compute"
      parallel_group: "structure"

    - name: "candlestick_patterns"
      budget_ms: 15
      type: "compute"
      parallel_group: "structure"

    # Steps 9-12: Entry (sequential)
    - name: "liquidity_zones"
      budget_ms: 15
      type: "compute"

    - name: "entry_signal"
      budget_ms: 20
      type: "compute"

    - name: "confluence_score"
      budget_ms: 10
      type: "compute"

    - name: "entry_refinement"
      budget_ms: 15
      type: "compute"

    # Steps 13-16: Management (sequential)
    - name: "tp_calculation"
      budget_ms: 10
      type: "compute"

    - name: "sl_placement"
      budget_ms: 10
      type: "compute"

    - name: "position_sizing"
      budget_ms: 5
      type: "compute"

    - name: "final_signal"
      budget_ms: 5
      type: "compute"
```

**Budget totals:**
- Cache reads: 10ms
- Parallel context group: 20ms (max of parallel)
- Parallel structure group: 30ms (max of parallel)
- Sequential entry: 60ms
- Sequential management: 30ms
- **Total budget: ~130ms** (leaving 1870ms headroom for broker execution)

#### 1.2.1 Budget Enforcement (Circuit Breaker)

```python
# alpha/alphastack/budget_enforcer.py

import asyncio
import time
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("alphastack.budget")

@dataclass
class StepResult:
    name: str
    latency_ms: float
    budget_ms: float
    exceeded: bool
    output: Optional[dict] = None
    error: Optional[str] = None

@dataclass
class PipelineResult:
    pair: str
    total_latency_ms: float
    budget_ms: float
    aborted: bool
    steps: list[StepResult] = field(default_factory=list)
    signal: Optional[dict] = None

class PipelineBudgetEnforcer:
    """
    Enforces per-step and total pipeline latency budgets.
    Aborts pipeline if total budget is exceeded.
    """

    def __init__(self, config: dict):
        self.total_budget_ms = config["pipeline"]["total_budget_ms"]
        self.warning_ms = config["pipeline"]["warning_threshold_ms"]
        self.step_budgets = {
            s["name"]: s["budget_ms"]
            for s in config["pipeline"]["steps"]
        }

    async def run_step(
        self,
        step_name: str,
        fn,
        pipeline_start: float,
        *args, **kwargs,
    ) -> StepResult:
        """Run a single pipeline step with budget enforcement."""
        budget = self.step_budgets.get(step_name, 100)
        elapsed_total = (time.monotonic() - pipeline_start) * 1000

        # Check if we've already blown the total budget
        if elapsed_total > self.total_budget_ms:
            return StepResult(
                name=step_name,
                latency_ms=elapsed_total,
                budget_ms=budget,
                exceeded=True,
                error="Pipeline budget exceeded before step started",
            )

        start = time.monotonic()
        try:
            result = await asyncio.wait_for(fn(*args, **kwargs), timeout=budget / 1000)
            latency = (time.monotonic() - start) * 1000
            return StepResult(
                name=step_name,
                latency_ms=latency,
                budget_ms=budget,
                exceeded=latency > budget,
                output=result,
            )
        except asyncio.TimeoutError:
            latency = (time.monotonic() - start) * 1000
            logger.warning(
                f"Step {step_name} exceeded budget: {latency:.0f}ms > {budget}ms"
            )
            return StepResult(
                name=step_name,
                latency_ms=latency,
                budget_ms=budget,
                exceeded=True,
                error="Step timeout",
            )

    async def run_parallel_group(
        self,
        group_name: str,
        steps: list[tuple[str, callable]],
        pipeline_start: float,
    ) -> list[StepResult]:
        """Run a group of independent steps in parallel."""
        tasks = [
            self.run_step(name, fn, pipeline_start)
            for name, fn in steps
        ]
        return await asyncio.gather(*tasks)
```

### 1.3 Fallback Behavior

When pre-computed values are missing or stale:

```python
# alpha/alphastack/fallback.py

async def get_fundamental_context(
    cache: PrecomputeCacheReader,
    pair: str,
) -> dict:
    """
    Get fundamental context with graceful fallback.

    Priority:
    1. Fresh cache (age < 80% TTL)     → use directly
    2. Stale cache (age < 150% TTL)    → use with reduced confidence
    3. Default neutral context          → no signal bias
    """
    cached = await cache.get("fundamental", pair)

    if cached is None:
        # No data at all — return neutral
        return {
            "bias": "neutral",
            "confidence": 0.0,
            "source": "default",
            "warning": "no_fundamental_data",
        }

    if cached.is_expired:
        # Stale data — use with penalty
        result = cached.value.copy()
        result["confidence"] = cached.confidence * 0.5  # halve confidence
        result["source"] = "stale_cache"
        result["warning"] = f"stale_data_age_{cached.age_seconds:.0f}s"
        return result

    if cached.is_stale:
        # Getting old — slight penalty
        result = cached.value.copy()
        result["confidence"] = cached.confidence * 0.8
        result["source"] = "aging_cache"
        return result

    # Fresh data
    result = cached.value.copy()
    result["confidence"] = cached.confidence
    result["source"] = "cache"
    return result
```

### 1.4 Metrics

```python
# Expose via Prometheus

PRECOMPUTE_LATENCY = Histogram(
    "precompute_llm_latency_seconds",
    "LLM call latency for pre-computation",
    ["compute_type", "pair", "model"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0],
)

PRECOMPUTE_SUCCESS = Counter(
    "precompute_llm_success_total",
    "Successful pre-compute LLM calls",
    ["compute_type", "pair"],
)

PRECOMPUTE_FAILURE = Counter(
    "precompute_llm_failure_total",
    "Failed pre-compute LLM calls",
    ["compute_type", "pair", "reason"],
)

CACHE_HIT = Counter(
    "precompute_cache_hits_total",
    "Cache hits on pre-compute values",
    ["compute_type", "pair", "freshness"],  # fresh|stale|expired
)

PIPELINE_LATENCY = Histogram(
    "alphastack_pipeline_latency_seconds",
    "End-to-end AlphaStack pipeline latency",
    ["pair"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0],
)

PIPELINE_BUDGET_EXCEEDED = Counter(
    "alphastack_pipeline_budget_exceeded_total",
    "Pipeline steps that exceeded latency budget",
    ["pair", "step"],
)
```

### 1.5 Acceptance Criteria for Fix #1

| Metric | Target | Measurement |
|--------|--------|-------------|
| AlphaStack pipeline p50 (no LLM) | ≤150ms | Prometheus histogram |
| AlphaStack pipeline p99 (no LLM) | ≤300ms | Prometheus histogram |
| Pre-compute cache hit rate | ≥95% | Counter ratio |
| Stale cache usage rate | <5% | Counter ratio |
| LLM circuit breaker activations | <1/day | Counter |
| Tick-to-order total p50 | ≤500ms | Prometheus histogram |
| Tick-to-order total p99 | ≤2000ms | Prometheus histogram |

---

## Fix #2: Memory Management for 24/7 Operation

### Problem

No memory limits, no GC tuning, no object pooling, no monitoring. Python processes will grow unbounded over days/weeks of 24/7 operation.

### 2.1 Process Memory Limits

#### 2.1.1 Resource Limits (In-Process)

```python
# alpha/core/memory_guard.py

import os
import sys
import gc
import time
import signal
import logging
import resource
import threading
from dataclasses import dataclass
from typing import Optional, Callable

logger = logging.getLogger("memory_guard")

@dataclass
class MemoryConfig:
    # Process memory limits
    max_rss_mb: int = 1024              # hard limit — OOM kill at this point
    warning_rss_mb: int = 768           # alert threshold (75% of max)
    critical_rss_mb: int = 896          # trigger aggressive GC (87.5% of max)

    # GC tuning
    gc_threshold: tuple = (700, 10, 10) # Python default — tuned below
    gc_interval_seconds: int = 300      # forced GC every 5 min during low activity
    gc_aggressive_threshold_mb: int = 800  # trigger aggressive GC above this

    # Monitoring
    check_interval_seconds: int = 30    # how often to check RSS
    alert_cooldown_seconds: int = 300   # don't spam alerts

    # Graceful restart
    max_uptime_hours: int = 168         # 7 days — restart after this
    restart_window_start: int = 22      # UTC hour to allow restarts
    restart_window_end: int = 2         # UTC hour end


class MemoryGuard:
    """
    Monitors and manages process memory for 24/7 operation.
    Runs as a background task alongside the main event loop.
    """

    def __init__(self, config: MemoryConfig, on_critical: Optional[Callable] = None):
        self.config = config
        self.on_critical = on_critical
        self._start_time = time.time()
        self._last_alert: float = 0
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False

        # Apply GC tuning on init
        self._tune_gc()

    def _tune_gc(self):
        """
        Tune Python's garbage collector for trading workloads.

        Strategy:
        - Increase generation 0 threshold to reduce GC pauses during tick processing
        - Keep generation 1 and 2 thresholds moderate for cycle detection
        - Disable GC during critical path (re-enable after)
        """
        gc.set_threshold(*self.config.gc_threshold)
        gc.set_debug(0)  # disable debug output

        # Disable automatic GC — we'll control it manually
        # This prevents GC pauses during tick processing
        gc.disable()
        logger.info(
            f"GC tuned: thresholds={self.config.gc_threshold}, "
            f"automatic GC disabled (manual control)"
        )

    def start(self):
        """Start the memory monitoring background task."""
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())

    async def stop(self):
        """Stop monitoring."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

    async def _monitor_loop(self):
        """Main monitoring loop — runs every check_interval."""
        while self._running:
            try:
                await self._check_and_manage()
            except Exception as e:
                logger.error(f"Memory monitor error: {e}")
            await asyncio.sleep(self.config.check_interval_seconds)

    async def _check_and_manage(self):
        """Check memory state and take action if needed."""
        rss_mb = self._get_rss_mb()
        now = time.time()

        # Record metric
        MEMORY_RSS.labels(service=self._service_name).set(rss_mb * 1024 * 1024)

        # Hard limit — trigger graceful shutdown
        if rss_mb > self.config.max_rss_mb:
            logger.critical(
                f"HARD LIMIT EXCEEDED: RSS={rss_mb:.0f}MB > {self.config.max_rss_mb}MB. "
                f"Initiating graceful shutdown."
            )
            if self.on_critical:
                await self.on_critical("memory_limit_exceeded", rss_mb)
            return

        # Critical threshold — aggressive GC
        if rss_mb > self.config.critical_rss_mb:
            logger.warning(
                f"CRITICAL MEMORY: RSS={rss_mb:.0f}MB > {self.config.critical_rss_mb}MB. "
                f"Running aggressive GC."
            )
            self._aggressive_gc()
            if now - self._last_alert > self.config.alert_cooldown_seconds:
                self._last_alert = now
                # emit alert metric / notification
            return

        # Warning threshold
        if rss_mb > self.config.warning_rss_mb:
            if now - self._last_alert > self.config.alert_cooldown_seconds:
                logger.warning(f"HIGH MEMORY: RSS={rss_mb:.0f}MB")
                self._last_alert = now

        # Periodic gentle GC during low activity
        if self._is_low_activity():
            gc.collect(generation=0)  # fast, ~1ms

    def _get_rss_mb(self) -> float:
        """Get current process RSS in MB."""
        # Linux: /proc/self/status
        try:
            with open("/proc/self/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        return int(line.split()[1]) / 1024
        except FileNotFoundError:
            pass

        # Fallback: resource module (macOS, etc.)
        usage = resource.getrusage(resource.RUSAGE_SELF)
        return usage.ru_maxrss / 1024  # macOS reports bytes, Linux reports KB

    def _aggressive_gc(self):
        """Aggressive garbage collection — call during non-critical windows."""
        # Collect all generations
        collected = gc.collect()
        logger.info(f"Aggressive GC: collected {collected} objects")

        # Clear internal caches
        gc.collect(0)
        gc.collect(1)
        gc.collect(2)

    def _is_low_activity(self) -> bool:
        """Check if we're in a low-activity period (weekend, off-hours)."""
        import datetime
        now = datetime.datetime.utcnow()
        # Weekend or off-hours (22:00-06:00 UTC)
        return now.weekday() >= 5 or now.hour >= 22 or now.hour < 6

    def pause_gc(self):
        """Context manager to pause GC during critical path processing."""
        return _GCPause()

    def should_restart(self) -> bool:
        """Check if process should be gracefully restarted."""
        uptime_hours = (time.time() - self._start_time) / 3600
        if uptime_hours < self.config.max_uptime_hours:
            return False

        import datetime
        now = datetime.datetime.utcnow()
        return (
            self.config.restart_window_start
            <= now.hour
            or now.hour < self.config.restart_window_end
        )


class _GCPause:
    """Context manager to pause GC during critical sections."""
    def __enter__(self):
        gc.disable()
        return self

    def __exit__(self, *args):
        gc.enable()
```

#### 2.1.2 Container Memory Limits (Docker)

```yaml
# docker-compose.memory.yml

services:
  strategy-agent:
    deploy:
      resources:
        limits:
          memory: 1024M        # hard limit — OOM kill
        reservations:
          memory: 256M         # guaranteed minimum

  risk-agent:
    deploy:
      resources:
        limits:
          memory: 512M
        reservations:
          memory: 128M

  execution-agent:
    deploy:
      resources:
        limits:
          memory: 256M
        reservations:
          memory: 64M

  data-pipeline:
    deploy:
      resources:
        limits:
          memory: 1536M        # needs more for indicator calculations
        reservations:
          memory: 512M

  gateway:
    deploy:
      resources:
        limits:
          memory: 512M
        reservations:
          memory: 128M

  redis:
    deploy:
      resources:
        limits:
          memory: 256M         # matches redis.conf maxmemory
        reservations:
          memory: 128M
```

### 2.2 Object Pooling

#### 2.2.1 Tick Object Pool

```python
# alpha/core/object_pool.py

import asyncio
from collections import deque
from dataclasses import dataclass, field
from typing import TypeVar, Generic, Optional
import threading

T = TypeVar("T")

class ObjectPool(Generic[T]):
    """
    Thread-safe object pool for high-frequency objects (ticks, signals, orders).

    Avoids GC pressure from creating/destroying thousands of objects per second.
    Objects are recycled instead of garbage collected.
    """

    def __init__(self, factory: callable, max_size: int = 1000):
        self._factory = factory
        self._max_size = max_size
        self._pool: deque = deque(maxlen=max_size)
        self._lock = threading.Lock()
        self._created = 0
        self._reused = 0

    def acquire(self) -> T:
        """Get an object from the pool or create a new one."""
        with self._lock:
            if self._pool:
                self._reused += 1
                return self._pool.popleft()
            self._created += 1
            return self._factory()

    def release(self, obj: T):
        """Return an object to the pool for reuse."""
        with self._lock:
            if len(self._pool) < self._max_size:
                # Reset object state before returning to pool
                if hasattr(obj, "reset"):
                    obj.reset()
                self._pool.append(obj)

    @property
    def stats(self) -> dict:
        with self._lock:
            return {
                "pool_size": len(self._pool),
                "total_created": self._created,
                "total_reused": self._reused,
                "reuse_ratio": self._reused / max(1, self._created + self._reused),
            }


@dataclass
class Tick:
    """
    Recyclable tick object. Use pool.acquire() / pool.release().
    """
    symbol: str = ""
    bid: float = 0.0
    ask: float = 0.0
    volume: float = 0.0
    timestamp: float = 0.0
    source: str = ""

    def reset(self):
        """Reset all fields for pool reuse."""
        self.symbol = ""
        self.bid = 0.0
        self.ask = 0.0
        self.volume = 0.0
        self.timestamp = 0.0
        self.source = ""

    def populate(self, symbol: str, bid: float, ask: float,
                 volume: float, timestamp: float, source: str = ""):
        """Set all fields at once — avoids multiple attribute lookups."""
        self.symbol = symbol
        self.bid = bid
        self.ask = ask
        self.volume = volume
        self.timestamp = timestamp
        self.source = source


@dataclass
class Signal:
    """Recyclable signal object."""
    pair: str = ""
    direction: str = ""         # "long" | "short" | "flat"
    confidence: float = 0.0
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    timestamp: float = 0.0
    metadata: dict = field(default_factory=dict)

    def reset(self):
        self.pair = ""
        self.direction = ""
        self.confidence = 0.0
        self.entry_price = 0.0
        self.stop_loss = 0.0
        self.take_profit = 0.0
        self.timestamp = 0.0
        self.metadata.clear()


# Global pools — initialized at startup
tick_pool: ObjectPool[Tick] = ObjectPool(Tick, max_size=5000)
signal_pool: ObjectPool[Signal] = ObjectPool(Signal, max_size=500)
```

#### 2.2.2 Pool Usage Pattern

```python
# Usage in tick ingestion

async def process_tick(raw_data: dict):
    tick = tick_pool.acquire()
    try:
        tick.populate(
            symbol=raw_data["symbol"],
            bid=raw_data["bid"],
            ask=raw_data["ask"],
            volume=raw_data.get("volume", 0),
            timestamp=raw_data["timestamp"],
            source="websocket",
        )
        # Process tick through pipeline...
        await pipeline.process(tick)
    finally:
        tick_pool.release(tick)  # always return to pool
```

### 2.3 Memory Monitoring (Prometheus Metrics)

```python
# alpha/core/memory_metrics.py

from prometheus_client import Gauge, Counter, Histogram

# Process memory
PROCESS_RSS_BYTES = Gauge(
    "process_resident_memory_bytes",
    "Process RSS memory in bytes",
    ["service"],
)

PROCESS_VMS_BYTES = Gauge(
    "process_virtual_memory_bytes",
    "Process virtual memory in bytes",
    ["service"],
)

# Object pools
POOL_SIZE = Gauge(
    "object_pool_size",
    "Current number of objects in pool",
    ["pool_name"],
)

POOL_CREATED = Counter(
    "object_pool_created_total",
    "Total objects created by pool",
    ["pool_name"],
)

POOL_REUSED = Counter(
    "object_pool_reused_total",
    "Total objects reused from pool",
    ["pool_name"],
)

# GC stats
GC_COLLECTIONS = Counter(
    "python_gc_collections_total",
    "GC collection runs",
    ["generation"],
)

GC_COLLECTED = Counter(
    "python_gc_collected_objects_total",
    "Objects collected by GC",
    ["generation"],
)

GC_PAUSE_DURATION = Histogram(
    "python_gc_pause_duration_seconds",
    "GC pause duration",
    buckets=[0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1],
)

# Redis memory
REDIS_MEMORY_USED = Gauge(
    "redis_memory_used_bytes",
    "Redis memory usage",
)

REDIS_MEMORY_PEAK = Gauge(
    "redis_memory_peak_bytes",
    "Redis peak memory usage",
)

REDIS_EVICTIONS = Counter(
    "redis_evictions_total",
    "Redis key evictions",
)

# ML model memory
MODEL_MEMORY_BYTES = Gauge(
    "ml_model_memory_bytes",
    "Memory used by loaded ML models",
    ["model_name"],
)
```

### 2.4 GC Tuning Configuration

```python
# alpha/core/gc_config.py

# Recommended GC settings for trading workloads

GC_PROFILES = {
    "tick_processing": {
        # During tick processing: disable GC to avoid pauses
        "enabled": False,
        "description": "GC disabled during hot path tick processing",
    },
    "idle": {
        # During idle periods: gentle collection
        "enabled": True,
        "threshold": (700, 10, 10),
        "description": "Standard GC during idle periods",
    },
    "maintenance": {
        # During maintenance windows: aggressive collection
        "enabled": True,
        "threshold": (100, 5, 5),  # lower thresholds = more frequent collection
        "description": "Aggressive GC during maintenance",
    },
}
```

**Usage pattern:**
```python
async def process_tick_batch(ticks: list[Tick]):
    """Process a batch of ticks with GC paused."""
    with memory_guard.pause_gc():
        for tick in ticks:
            await process_single_tick(tick)
    # GC re-enabled automatically after context manager exits
```

### 2.5 Graceful Restart Strategy

```python
# alpha/core/restart_manager.py

import asyncio
import os
import signal
import logging
from datetime import datetime, timezone

logger = logging.getLogger("restart")

class GracefulRestartManager:
    """
    Manages periodic restarts to prevent memory leaks from accumulating.

    Strategy:
    - Check every hour if restart window is active
    - During restart window (Sunday 22:00-02:00 UTC), restart if uptime > threshold
    - Drain in-flight orders before restarting
    - Signal upstream (Docker/systemd) to restart
    """

    def __init__(self, memory_guard: MemoryGuard, order_manager):
        self.memory_guard = memory_guard
        self.order_manager = order_manager

    async def check_and_restart(self):
        """Called periodically — checks if restart is needed."""
        if not self.memory_guard.should_restart():
            return

        logger.info("Restart window active and uptime threshold met. Draining...")

        # 1. Stop accepting new signals
        await self.order_manager.stop_accepting()

        # 2. Wait for in-flight orders to complete (max 60s)
        try:
            await asyncio.wait_for(
                self.order_manager.drain(),
                timeout=60,
            )
        except asyncio.TimeoutError:
            logger.warning("Order drain timeout — forcing restart with pending orders")

        # 3. Save state to Redis for recovery
        await self._save_restart_state()

        # 4. Signal graceful shutdown
        logger.info("Initiating graceful restart")
        os.kill(os.getpid(), signal.SIGTERM)

    async def _save_restart_state(self):
        """Save in-flight state for post-restart recovery."""
        state = {
            "restart_time": datetime.now(timezone.utc).isoformat(),
            "reason": "scheduled_restart",
            "pending_orders": await self.order_manager.get_pending(),
        }
        await self.memory_guard.redis.set(
            "system:last_restart",
            json.dumps(state),
            ex=86400,  # keep for 24h
        )
```

### 2.6 Acceptance Criteria for Fix #2

| Metric | Target | Measurement |
|--------|--------|-------------|
| Process RSS after 24h | ≤1.5× initial | Prometheus gauge |
| Process RSS after 7d | ≤2.0× initial | Prometheus gauge |
| GC pause p99 | ≤5ms | Prometheus histogram |
| Object pool reuse ratio | ≥80% | Counter ratio |
| Memory-related restarts | 0/week | Log analysis |
| OOM kills | 0 | Container events |
| Scheduled restart success rate | 100% | Log analysis |

---

## Fix #3: WebSocket Performance Specification

### Problem

WebSocket architecture has no SLAs, no backpressure, no binary protocol, no fan-out spec, no reconnection strategy.

### 3.1 SLA Definitions

```yaml
# alpha/config/websocket_slas.yaml

websocket:
  # Connection SLAs
  connection:
    max_concurrent_clients: 100
    max_connections_per_ip: 5
    handshake_timeout_ms: 5000
    idle_timeout_seconds: 120        # disconnect if no data for 2min
    ping_interval_seconds: 30        # send ping every 30s
    pong_timeout_seconds: 10         # expect pong within 10s
    max_missed_pongs: 3              # disconnect after 3 missed pongs

  # Latency SLAs
  latency:
    tick_to_client_ms: 100           # p99 tick delivery to WS client
    fanout_latency_ms: 50            # p99 Redis → all WS clients
    message_serialize_ms: 5          # p99 message serialization
    total_e2e_ms: 150                # p99 tick source → client receive

  # Throughput SLAs
  throughput:
    max_messages_per_second: 10000   # aggregate across all clients
    max_messages_per_client: 1000    # per-client rate limit
    max_message_size_bytes: 65536    # 64KB per message

  # Reliability SLAs
  reliability:
    delivery_guarantee: "at-most-once"  # ticks are fire-and-forget
    reconnection_time_ms: 5000       # p99 full reconnection
    message_drop_threshold: 100      # drop if client buffer > 100 msgs
    buffer_size_per_client: 500      # max queued messages per client
```

### 3.2 Binary Protocol (MessagePack)

#### 3.2.1 Message Format

```
┌──────────────────────────────────────────────────────────┐
│ WebSocket Binary Frame                                    │
├──────────┬──────────┬──────────────────────────────────── │
│ Type (1B)│ Flags(1B)│ Payload (MessagePack)               │
│  0x01    │  0x01    │                                     │
│  tick    │  packed  │                                     │
│          │          │                                     │
│  0x02    │  0x01    │                                     │
│  signal  │  packed  │                                     │
│          │          │                                     │
│  0x03    │  0x01    │                                     │
│  order   │  packed  │                                     │
│          │          │                                     │
│  0x10    │  0x00    │                                     │
│  ping    │  plain   │                                     │
│          │          │                                     │
│  0x11    │  0x00    │                                     │
│  pong    │  plain   │                                     │
│          │          │                                     │
│  0xFE    │  0x00    │                                     │
│  error   │  plain   │                                     │
│          │          │                                     │
│  0xFF    │  0x00    │                                     │
│  auth    │  plain   │                                     │
└──────────┴──────────┴──────────────────────────────────── ┘

Type codes:
  0x01 = Tick data
  0x02 = Signal update
  0x03 = Order update
  0x10 = Ping (client → server)
  0x11 = Pong (server → client)
  0xFE = Error
  0xFF = Auth

Flags:
  bit 0: compressed (1 = zstd compressed payload)
  bit 1-7: reserved
```

#### 3.2.2 Tick Message Schema (MessagePack)

```python
# alpha/ws/protocol.py

import msgpack
from dataclasses import dataclass
from typing import Optional

# Message type constants
MSG_TICK = 0x01
MSG_SIGNAL = 0x02
MSG_ORDER = 0x03
MSG_PING = 0x10
MSG_PONG = 0x11
MSG_ERROR = 0xFE
MSG_AUTH = 0xFF

FLAG_COMPRESSED = 0x01

@dataclass
class TickMessage:
    """
    Binary tick message — optimized for minimal size and fast encoding.

    JSON format: ~200 bytes, ~50μs encode
    MessagePack format: ~50 bytes, ~10μs encode
    """
    symbol: str          # "EURUSD"
    bid: float           # 1.08542
    ask: float           # 1.08565
    volume: float        # 1000.0
    timestamp_ms: int    # 1720700000000

    def encode(self) -> bytes:
        """Encode to binary WebSocket frame."""
        payload = msgpack.packb(
            [self.symbol, self.bid, self.ask, self.volume, self.timestamp_ms],
            use_bin_type=True,
        )
        return bytes([MSG_TICK, 0x00]) + payload

    @classmethod
    def decode(cls, data: bytes) -> "TickMessage":
        """Decode from binary WebSocket frame."""
        _type, _flags = data[0], data[1]
        if _type != MSG_TICK:
            raise ValueError(f"Expected tick type, got {_type}")

        payload = data[2:]
        if _flags & FLAG_COMPRESSED:
            import zstd
            payload = zstd.decompress(payload)

        symbol, bid, ask, volume, ts = msgpack.unpackb(payload, raw=False)
        return cls(symbol=symbol, bid=bid, ask=ask, volume=volume, timestamp_ms=ts)


@dataclass
class SignalMessage:
    pair: str
    direction: str       # "long" | "short" | "flat"
    confidence: float
    entry: float
    stop_loss: float
    take_profit: float
    timestamp_ms: int
    source: str          # "smc" | "rsi" | "confluence"

    def encode(self) -> bytes:
        payload = msgpack.packb(
            [self.pair, self.direction, self.confidence,
             self.entry, self.stop_loss, self.take_profit,
             self.timestamp_ms, self.source],
            use_bin_type=True,
        )
        return bytes([MSG_SIGNAL, 0x00]) + payload

    @classmethod
    def decode(cls, data: bytes) -> "SignalMessage":
        _type = data[0]
        if _type != MSG_SIGNAL:
            raise ValueError(f"Expected signal type, got {_type}")
        vals = msgpack.unpackb(data[2:], raw=False)
        return cls(*vals)
```

### 3.3 Fan-Out Architecture

#### 3.3.1 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Tick Fan-Out Architecture                       │
│                                                                     │
│  ┌──────────┐    ┌──────────┐    ┌───────────────────────────────┐ │
│  │ MT5 /    │───▶│ Data     │───▶│ Redis Pub/Sub Channel         │ │
│  │ Exchange │    │ Pipeline │    │ "stream:ticks:{symbol}"       │ │
│  └──────────┘    └──────────┘    └───────────┬───────────────────┘ │
│                                              │                     │
│                    ┌──────────────────────────┼──────────────────┐ │
│                    │                          │                  │ │
│                    ▼                          ▼                  ▼ │
│           ┌──────────────┐         ┌──────────────┐    ┌────────┐ │
│           │ Strategy     │         │ Risk Agent   │    │ WS Fan │ │
│           │ Agents (N)   │         │              │    │ -Out   │ │
│           └──────────────┘         └──────────────┘    │ Server │ │
│                                                        └───┬────┘ │
│                                                           │      │
│                              ┌────────────────────────────┼──┐   │
│                              │              │              │  │   │
│                              ▼              ▼              ▼  │   │
│                         ┌────────┐    ┌────────┐    ┌────────┐   │
│                         │Client 1│    │Client 2│    │Client N│   │
│                         │(fast)  │    │(slow)  │    │        │   │
│                         └────────┘    └────────┘    └────────┘   │
│                                                                   │
│  Backpressure: Slow clients get messages DROPPED, not blocking   │
└───────────────────────────────────────────────────────────────────┘
```

#### 3.3.2 Fan-Out Server Implementation

```python
# alpha/ws/fanout.py

import asyncio
import time
import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, Set
from enum import Enum

import redis.asyncio as aioredis

logger = logging.getLogger("ws.fanout")


class ClientState(Enum):
    CONNECTED = "connected"
    SLOW = "slow"          # buffer growing
    DISCONNECTING = "disconnecting"


@dataclass
class WSClient:
    """Represents a connected WebSocket client with backpressure tracking."""
    client_id: str
    websocket: object       # starlette WebSocket
    subscriptions: Set[str] = field(default_factory=set)
    state: ClientState = ClientState.CONNECTED
    send_buffer: deque = field(default_factory=lambda: deque(maxlen=500))
    messages_sent: int = 0
    messages_dropped: int = 0
    last_activity: float = field(default_factory=time.time)
    last_ping: float = 0
    missed_pongs: int = 0

    @property
    def buffer_size(self) -> int:
        return len(self.send_buffer)


class WebSocketFanOut:
    """
    High-performance WebSocket fan-out server.

    Design principles:
    1. Never let a slow client block others (per-client buffers + drop policy)
    2. Use asyncio tasks per client for non-blocking sends
    3. Subscribe to Redis Pub/Sub once, fan out to all clients
    4. Binary MessagePack messages for minimal serialization overhead
    """

    def __init__(
        self,
        redis: aioredis.Redis,
        max_clients: int = 100,
        buffer_size: int = 500,
        drop_threshold: int = 100,
        ping_interval: int = 30,
        pong_timeout: int = 10,
        max_missed_pongs: int = 3,
    ):
        self.redis = redis
        self.max_clients = max_clients
        self.buffer_size = buffer_size
        self.drop_threshold = drop_threshold
        self.ping_interval = ping_interval
        self.pong_timeout = pong_timeout
        self.max_missed_pongs = max_missed_pongs

        self._clients: dict[str, WSClient] = {}
        self._send_tasks: dict[str, asyncio.Task] = {}
        self._pubsub_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._running = False

        # Metrics
        self._total_messages_fanout = 0
        self._total_messages_dropped = 0

    async def start(self):
        """Start the fan-out server."""
        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("WebSocket fan-out server started")

    async def stop(self):
        """Gracefully stop the fan-out server."""
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        for task in self._send_tasks.values():
            task.cancel()
        # Close all client connections
        for client in self._clients.values():
            try:
                await client.websocket.close()
            except Exception:
                pass
        self._clients.clear()

    async def handle_connection(self, websocket):
        """Handle a new WebSocket connection."""
        if len(self._clients) >= self.max_clients:
            await websocket.close(code=1013, reason="Max clients reached")
            return

        client_id = f"ws-{id(websocket)}"
        client = WSClient(
            client_id=client_id,
            websocket=websocket,
        )
        self._clients[client_id] = client

        # Start per-client send task
        self._send_tasks[client_id] = asyncio.create_task(
            self._client_send_loop(client)
        )

        try:
            async for message in websocket.iter_bytes():
                await self._handle_client_message(client, message)
        except Exception as e:
            logger.debug(f"Client {client_id} disconnected: {e}")
        finally:
            await self._disconnect_client(client_id)

    async def subscribe(self, channel: str):
        """Subscribe to a Redis Pub/Sub channel for tick data."""
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(channel)

        async for message in pubsub.listen():
            if message["type"] == "message":
                await self._fanout(message["data"])

    async def _fanout(self, data: bytes):
        """
        Fan out a message to all connected clients.
        This is the hot path — must be fast.
        """
        self._total_messages_fanout += 1

        for client_id, client in self._clients.items():
            if client.state == ClientState.DISCONNECTING:
                continue

            # Backpressure: drop if buffer is growing too large
            if client.buffer_size >= self.drop_threshold:
                client.messages_dropped += 1
                self._total_messages_dropped += 1
                WS_MESSAGES_DROPPED.labels(client_id=client_id).inc()

                # If buffer is critically full, mark for disconnection
                if client.buffer_size >= self.buffer_size:
                    client.state = ClientState.DISCONNECTING
                    logger.warning(
                        f"Client {client_id} buffer full ({client.buffer_size}), "
                        f"disconnecting"
                    )
                continue

            # Add to client's send buffer (non-blocking)
            client.send_buffer.append(data)

    async def _client_send_loop(self, client: WSClient):
        """
        Per-client send loop — drains the client's buffer.
        Runs as a separate asyncio task so one slow client doesn't block others.
        """
        while client.state != ClientState.DISCONNECTING:
            try:
                if client.send_buffer:
                    data = client.send_buffer.popleft()
                    await asyncio.wait_for(
                        client.websocket.send_bytes(data),
                        timeout=1.0,  # 1s max per send
                    )
                    client.messages_sent += 1
                    client.last_activity = time.time()
                    WS_MESSAGES_SENT.labels(client_id=client.client_id).inc()
                else:
                    # No data — sleep briefly to avoid busy-wait
                    await asyncio.sleep(0.001)  # 1ms
            except asyncio.TimeoutError:
                logger.warning(f"Client {client.client_id} send timeout")
                client.messages_dropped += 1
            except Exception as e:
                logger.warning(f"Client {client.client_id} send error: {e}")
                client.state = ClientState.DISCONNECTING
                break

    async def _heartbeat_loop(self):
        """Send pings and detect dead clients."""
        while self._running:
            await asyncio.sleep(self.ping_interval)

            now = time.time()
            to_disconnect = []

            for client_id, client in self._clients.items():
                # Check pong timeout
                if client.last_ping > 0 and now - client.last_ping > self.pong_timeout:
                    client.missed_pongs += 1
                    if client.missed_pongs >= self.max_missed_pongs:
                        logger.warning(
                            f"Client {client_id} missed {client.missed_pongs} pongs, "
                            f"disconnecting"
                        )
                        to_disconnect.append(client_id)
                        continue

                # Send ping
                try:
                    ping_frame = bytes([MSG_PING, 0x00])
                    await asyncio.wait_for(
                        client.websocket.send_bytes(ping_frame),
                        timeout=2.0,
                    )
                    client.last_ping = now
                except Exception:
                    to_disconnect.append(client_id)

            for client_id in to_disconnect:
                await self._disconnect_client(client_id)

    async def _disconnect_client(self, client_id: str):
        """Clean up a disconnected client."""
        client = self._clients.pop(client_id, None)
        if client:
            client.state = ClientState.DISCONNECTING
            try:
                await client.websocket.close()
            except Exception:
                pass
            task = self._send_tasks.pop(client_id, None)
            if task:
                task.cancel()
            logger.info(
                f"Client {client_id} disconnected. "
                f"Sent={client.messages_sent}, Dropped={client.messages_dropped}"
            )

    async def _handle_client_message(self, client: WSClient, data: bytes):
        """Handle incoming message from client."""
        if not data:
            return

        msg_type = data[0]

        if msg_type == MSG_PONG:
            client.missed_pongs = 0
            client.last_activity = time.time()

        elif msg_type == MSG_AUTH:
            # Handle authentication
            pass

        elif msg_type == MSG_SUBSCRIBE:
            # Handle channel subscription
            channel = data[2:].decode("utf-8")
            client.subscriptions.add(channel)

    @property
    def stats(self) -> dict:
        return {
            "connected_clients": len(self._clients),
            "total_messages_fanout": self._total_messages_fanout,
            "total_messages_dropped": self._total_messages_dropped,
            "clients": {
                cid: {
                    "state": c.state.value,
                    "buffer_size": c.buffer_size,
                    "messages_sent": c.messages_sent,
                    "messages_dropped": c.messages_dropped,
                }
                for cid, c in self._clients.items()
            },
        }
```

### 3.4 Reconnection Strategy

#### 3.4.1 Client-Side Reconnection

```python
# alpha/ws/reconnect.py

import asyncio
import random
import time
import logging
from typing import Optional, Callable, Awaitable

logger = logging.getLogger("ws.reconnect")


class ReconnectingWebSocketClient:
    """
    WebSocket client with exponential backoff reconnection.

    Strategy:
    - Initial delay: 1s
    - Max delay: 30s
    - Backoff factor: 2x
    - Jitter: ±25% (prevents thundering herd)
    - Max retries: unlimited (keeps trying for 24/7 operation)
    - Health check: ping every 30s
    """

    def __init__(
        self,
        url: str,
        on_message: Callable[[bytes], Awaitable[None]],
        on_connect: Optional[Callable[[], Awaitable[None]]] = None,
        on_disconnect: Optional[Callable[[], Awaitable[None]]] = None,
        initial_delay: float = 1.0,
        max_delay: float = 30.0,
        backoff_factor: float = 2.0,
        jitter: float = 0.25,
    ):
        self.url = url
        self.on_message = on_message
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter

        self._ws: Optional[object] = None
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._reconnect_count = 0
        self._last_connect: float = 0
        self._connected = False

    async def start(self):
        """Start the reconnection loop."""
        self._running = True
        self._task = asyncio.create_task(self._connect_loop())

    async def stop(self):
        """Stop reconnection."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._ws:
            await self._ws.close()

    async def _connect_loop(self):
        """Main reconnection loop with exponential backoff."""
        delay = self.initial_delay

        while self._running:
            try:
                await self._connect()
                delay = self.initial_delay  # reset on successful connect
                self._reconnect_count = 0

                # Listen for messages
                await self._listen()

            except Exception as e:
                logger.warning(f"WebSocket connection failed: {e}")

            finally:
                self._connected = False
                if self.on_disconnect:
                    await self.on_disconnect()

            if not self._running:
                break

            # Exponential backoff with jitter
            jitter_range = delay * self.jitter
            actual_delay = delay + random.uniform(-jitter_range, jitter_range)
            actual_delay = max(0.1, actual_delay)  # minimum 100ms

            logger.info(
                f"Reconnecting in {actual_delay:.1f}s "
                f"(attempt {self._reconnect_count + 1})"
            )
            await asyncio.sleep(actual_delay)

            delay = min(delay * self.backoff_factor, self.max_delay)
            self._reconnect_count += 1

            # Record metric
            WS_RECONNECT_TOTAL.labels(url=self.url).inc()

    async def _connect(self):
        """Establish WebSocket connection."""
        import websockets
        self._ws = await websockets.connect(
            self.url,
            ping_interval=30,
            ping_timeout=10,
            close_timeout=5,
            max_size=2**20,  # 1MB max message
        )
        self._connected = True
        self._last_connect = time.time()
        logger.info(f"WebSocket connected to {self.url}")

        if self.on_connect:
            await self.on_connect()

        WS_CONNECTED.labels(url=self.url).set(1)

    async def _listen(self):
        """Listen for messages until disconnected."""
        async for message in self._ws:
            if isinstance(message, bytes):
                await self.on_message(message)
            elif isinstance(message, str):
                await self.on_message(message.encode())

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def stats(self) -> dict:
        return {
            "connected": self._connected,
            "reconnect_count": self._reconnect_count,
            "last_connect": self._last_connect,
        }
```

#### 3.4.2 Server-Side Reconnection Support

```python
# During reconnection, the server should:

# 1. Accept the new connection immediately
# 2. Client re-authenticates
# 3. Client re-subscribes to channels
# 4. Server starts sending current data (no replay of missed ticks)
#    — Ticks are ephemeral; clients should not expect replay
#    — For signals/orders, client can request state via REST API

# The server does NOT buffer messages for disconnected clients.
# Rationale: tick data is real-time by nature; buffering creates stale data.
```

### 3.5 Backpressure Details

```python
# Backpressure policy — implemented in fan-out server

BACKPRESSURE_POLICY = {
    # Buffer size thresholds and actions
    "green": {
        "buffer_range": (0, 50),
        "action": "send_immediately",
        "description": "Normal operation — send as fast as possible",
    },
    "yellow": {
        "buffer_range": (50, 100),
        "action": "queue_with_priority",
        "description": "Buffer growing — prioritize newest messages",
    },
    "orange": {
        "buffer_range": (100, 200),
        "action": "drop_low_priority",
        "description": "Buffer concerning — drop tick data, keep signals/orders",
    },
    "red": {
        "buffer_range": (200, 500),
        "action": "drop_all_except_critical",
        "description": "Buffer critical — only keep order updates",
    },
    "disconnect": {
        "buffer_range": (500, float("inf")),
        "action": "disconnect_client",
        "description": "Buffer overflow — disconnect client",
    },
}
```

```python
def should_send(self, client: WSClient, msg_type: int) -> bool:
    """Decide whether to send a message based on backpressure state."""
    buf = client.buffer_size

    if buf < 50:
        return True  # green — always send

    if buf < 100:
        return True  # yellow — still send

    if buf < 200:
        # orange — only send signals and orders, drop ticks
        return msg_type in (MSG_SIGNAL, MSG_ORDER)

    if buf < 500:
        # red — only send order updates
        return msg_type == MSG_ORDER

    # disconnect — don't send anything
    return False
```

### 3.6 WebSocket Metrics

```python
# Prometheus metrics for WebSocket performance

WS_CONNECTIONS = Gauge(
    "ws_connections_active",
    "Active WebSocket connections",
)

WS_MESSAGES_SENT = Counter(
    "ws_messages_sent_total",
    "Total messages sent to WebSocket clients",
    ["client_id"],
)

WS_MESSAGES_DROPPED = Counter(
    "ws_messages_dropped_total",
    "Total messages dropped due to backpressure",
    ["client_id"],
)

WS_FANOUT_LATENCY = Histogram(
    "ws_fanout_latency_seconds",
    "Time to fan out a message to all clients",
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1],
)

WS_RECONNECT_TOTAL = Counter(
    "ws_reconnect_total",
    "Total reconnection attempts",
    ["url"],
)

WS_CONNECTED = Gauge(
    "ws_connected",
    "Whether WebSocket is currently connected",
    ["url"],
)

WS_BUFFER_SIZE = Gauge(
    "ws_client_buffer_size",
    "Per-client send buffer size",
    ["client_id"],
)

WS_MESSAGE_LATENCY = Histogram(
    "ws_message_latency_seconds",
    "End-to-end message latency (tick source → client receive)",
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5],
)
```

### 3.7 Acceptance Criteria for Fix #3

| Metric | Target | Measurement |
|--------|--------|-------------|
| Tick-to-client p50 | ≤50ms | Prometheus histogram |
| Tick-to-client p99 | ≤100ms | Prometheus histogram |
| Fan-out latency p99 | ≤50ms | Prometheus histogram |
| Max concurrent clients | 100 | Load test |
| Message throughput | 10,000 msg/s | Load test |
| Reconnection time p99 | ≤5s | Prometheus histogram |
| Messages dropped under load | <1% | Counter ratio |
| Client disconnections from backpressure | <5/hour | Log analysis |
| Heartbeat reliability | 99.9% | Pong response rate |

---

## Integration & Testing

### 4.1 Integration Checklist

- [ ] Pre-compute workers running and producing cache entries
- [ ] AlphaStack pipeline reads from cache, not LLM directly
- [ ] Pipeline budget enforcer aborts on timeout
- [ ] Memory guard starts with each agent process
- [ ] Object pools initialized at startup
- [ ] GC pauses disabled during tick processing
- [ ] WebSocket fan-out server running with backpressure
- [ ] Binary MessagePack protocol working end-to-end
- [ ] Reconnection client working with backoff
- [ ] All Prometheus metrics exposed and scraped

### 4.2 Load Testing Plan

```yaml
load_tests:
  - name: "tick_throughput"
    description: "Sustain 1000 ticks/sec for 1 hour"
    success_criteria:
      - p99 pipeline latency < 300ms
      - RSS growth < 10% over 1 hour
      - zero OOM kills
      - zero pipeline budget exceeded

  - name: "websocket_fanout"
    description: "100 concurrent clients, 1000 msgs/sec"
    success_criteria:
      - p99 delivery latency < 100ms
      - < 1% message drops
      - zero server crashes

  - name: "memory_72h"
    description: "Run system for 72 hours with synthetic load"
    success_criteria:
      - RSS at 72h < 2× initial
      - zero memory-related restarts
      - GC pause p99 < 5ms

  - name: "reconnection_storm"
    description: "50 clients disconnect and reconnect simultaneously"
    success_criteria:
      - all clients reconnected within 30s
      - no message delivery to other clients affected
      - server remains stable
```

### 4.3 Rollout Strategy

| Phase | Scope | Validation |
|-------|-------|------------|
| **Phase 1** | Pre-compute workers + cache reader | Verify cache hit rate >95%, pipeline latency <300ms |
| **Phase 2** | Memory guard + object pools | Run for 7 days, verify RSS stability |
| **Phase 3** | Binary protocol + fan-out | Load test with 100 clients, verify SLAs |
| **Phase 4** | Full integration | 72h soak test, all acceptance criteria green |

---

*This fix specification provides complete, production-ready implementations for all 3 critical performance issues. Each fix includes code, configuration, metrics, and acceptance criteria. The pre-compute architecture eliminates LLM latency from the critical path; memory management ensures 24/7 stability; WebSocket specification guarantees real-time data delivery under load.*
