# Alpha Stack — Performance Optimization Architecture

> **Author:** Performance Architect
> **Date:** 2026-07-11
> **Status:** Architecture Design — Pre-Implementation
> **Dependencies:** `architecture_data.md`, `architecture_database.md`, `architecture_deployment.md`, `architecture_multi_agent.md`, `architecture_agent_communication.md`, `research_scalability.md`, `research_02_tech_stack_architecture.md`

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Latency Optimization — Tick-to-Order <5s Target](#2-latency-optimization--tick-to-order-5s-target)
3. [Memory Management — 24/7 Operation](#3-memory-management--247-operation)
4. [CPU Optimization — Parallel Agent Execution](#4-cpu-optimization--parallel-agent-execution)
5. [Database Query Optimization](#5-database-query-optimization)
6. [WebSocket Performance — Real-Time Data Streaming](#6-websocket-performance--real-time-data-streaming)
7. [Caching Strategy — Redis Hot Path](#7-caching-strategy--redis-hot-path)
8. [Connection Pooling — Broker, Database, API](#8-connection-pooling--broker-database-api)
9. [Profiling and Benchmarking Methodology](#9-profiling-and-benchmarking-methodology)
10. [Performance Regression Testing](#10-performance-regression-testing)
11. [Resource Scaling Triggers](#11-resource-scaling-triggers)
12. [Implementation Roadmap](#12-implementation-roadmap)

---

## 1. Executive Summary

Alpha Stack is a 24/7 multi-agent trading system where **latency directly impacts profitability** and **memory stability determines uptime**. This document defines the performance optimization architecture across the full stack — from tick ingestion to order execution, from memory management to CPU parallelization.

### Performance Targets

| Metric | Target | Measurement Point | Priority |
|--------|--------|-------------------|----------|
| **Tick-to-Order Latency** | <5s (retail), <500ms (hot path) | Tick received → order sent to broker | P0 |
| **Signal Agent Inference** | <100ms per agent | Input features → signal output | P0 |
| **Redis Read Latency** | <1ms p99 | GET/HGET operation | P0 |
| **Database Query (hot)** | <5ms p95 | Indexed read on hot data | P1 |
| **Database Query (cold)** | <100ms p95 | Historical candle retrieval | P1 |
| **WebSocket Tick Delivery** | <10ms p99 | Broker tick → Redis write | P0 |
| **Memory Growth Rate** | <1MB/hour steady-state | RSS after warm-up | P1 |
| **CPU Utilization (idle)** | <15% | No active pipeline cycles | P1 |
| **CPU Utilization (active)** | <70% | Full pipeline with 10 pairs | P1 |
| **Agent Startup Time** | <3s cold, <500ms warm | Spawn → first signal produced | P2 |
| **Pipeline End-to-End** | <30s for full 7-phase cycle | Trigger → trade decision | P1 |

### Design Principles

| Principle | Rationale |
|-----------|-----------|
| **Measure before optimizing** | Profile first, optimize hot paths only |
| **Latency over throughput** | Trading favors fast single operations over batch throughput |
| **Predictable over fast** | Consistent 5ms beats variable 1-50ms |
| **Fail fast, fail loud** | Timeout > hang; circuit breaker > retry storm |
| **Zero-copy where possible** | Avoid serialization/deserialization in hot paths |
| **Pre-compute over compute-on-demand** | Cache indicators, features, regime state |
| **Vertical first, horizontal later** | Single-machine optimization before distribution |

---

## 2. Latency Optimization — Tick-to-Order <5s Target

### 2.1 Latency Budget Breakdown

The full tick-to-order path traverses 7 components. Each has a strict budget:

```
TICK ARRIVES FROM BROKER
  │
  ├─ [1] Broker WebSocket → Adapter          < 1ms      (P0)
  ├─ [2] Adapter → Normalization              < 1ms      (P0)
  ├─ [3] Redis Write + Pub/Sub Publish        < 1ms      (P0)
  ├─ [4] Agent Inference (signal generation)  < 100ms    (P0)
  ├─ [5] Risk Gate Validation                 < 5ms      (P0)
  ├─ [6] Order Construction + Routing         < 5ms      (P0)
  ├─ [7] ZeroMQ → MQL5 EA → Broker           < 200ms    (P0)
  │
  └─ TOTAL HOT PATH:                         < 313ms    (P0)

ADDITIONAL OVERHEAD (full pipeline with multi-agent consensus):
  ├─ Multi-agent parallel inference           < 500ms    (P1)
  ├─ Signal aggregation + confluence scoring  < 50ms     (P1)
  ├─ Entry type determination                 < 20ms     (P1)
  ├─ HITL approval (if needed)                0-300s     (P2)
  │
  └─ TOTAL FULL PIPELINE (no HITL):          < 883ms    (P1)
  └─ TOTAL WITH HITL TIMEOUT:                < 5s       (P0)
```

### 2.2 Hot Path vs Cold Path Separation

```
HOT PATH (latency-critical, <1s total):
  Tick → Redis Pub/Sub → Signal Agent → Risk Gate → Order → Broker
  │
  Design: Zero-copy, pre-computed features, in-memory state, no DB writes
  Technology: Redis Pub/Sub, Python asyncio, ONNX Runtime, ZeroMQ

COLD PATH (latency-tolerant, seconds to minutes):
  Tick → TimescaleDB, Signal → Journal, Order → Audit Log
  │
  Design: Async writes, batch inserts, non-blocking
  Technology: Redis Streams, TimescaleDB COPY, background tasks
```

### 2.3 Tick Ingestion Optimization

```python
# HOT PATH: Tick ingestion — zero-copy design
class OptimizedTickIngester:
    """
    Minimal-overhead tick ingestion.
    Target: <1ms from broker tick to Redis publish.
    """

    __slots__ = ('_redis', '_pub_pipe', '_symbol_channels', '_buffer')

    def __init__(self, redis_client, symbols: list[str]):
        self._redis = redis_client
        # Pre-compute channel names (avoid string formatting per tick)
        self._symbol_channels = {
            sym: f"tick:{sym}".encode() for sym in symbols
        }
        # Use pipeline for batched Redis operations
        self._pub_pipe = redis_client.pipeline(transaction=False)
        # Pre-allocated buffer for batch writes
        self._buffer = bytearray()

    async def on_tick(self, symbol: str, bid: float, ask: float,
                      timestamp: int, volume: float = 0.0):
        """
        Process a single tick with minimal allocations.
        Uses pre-computed channel names and pipelined Redis operations.
        """
        # Pre-computed key lookup (O(1) dict access)
        channel = self._symbol_channels.get(symbol)
        if channel is None:
            return  # Unknown symbol, skip

        # Direct hash update + publish in single pipeline
        # Avoid intermediate dict creation
        key = f"tick:{symbol}"
        self._pub_pipe.hset(key, mapping={
            'bid': bid,
            'ask': ask,
            'spread': ask - bid,
            'mid': (bid + ask) / 2.0,
            'time': timestamp,
            'vol': volume,
        })
        self._pub_pipe.expire(key, 60)  # Auto-expire stale ticks
        self._pub_pipe.publish(channel, f"{bid},{ask},{timestamp}")

        # Execute pipeline (batched, single round-trip)
        await self._pub_pipe.execute()

    async def on_tick_batch(self, ticks: list[tuple]):
        """
        Batch tick processing for high-throughput periods.
        Multiple ticks in single Redis pipeline = fewer round-trips.
        """
        for symbol, bid, ask, ts, vol in ticks:
            key = f"tick:{symbol}"
            self._pub_pipe.hset(key, mapping={
                'bid': bid, 'ask': ask,
                'spread': ask - bid, 'mid': (bid + ask) / 2.0,
                'time': ts, 'vol': vol,
            })
            channel = self._symbol_channels.get(symbol)
            if channel:
                self._pub_pipe.publish(channel, f"{bid},{ask},{ts}")

        await self._pub_pipe.execute()
```

### 2.4 Signal Inference Optimization

The ML inference step is the largest single latency contributor. Optimization targets:

```python
# ONNX Runtime — 3-10x faster than PyTorch for inference
import onnxruntime as ort
import numpy as np

class OptimizedSignalEngine:
    """
    Pre-loaded ONNX models with optimized inference.
    Target: <10ms per model inference.
    """

    def __init__(self, model_paths: dict[str, str]):
        # Configure ONNX Runtime for minimum latency
        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        sess_options.intra_op_num_threads = 2        # Limit threads per model
        sess_options.inter_op_num_threads = 1
        sess_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        sess_options.enable_mem_pattern = True
        sess_options.enable_cpu_mem_arena = True

        # Pre-load all models at startup (avoid cold-start latency)
        self.sessions = {}
        for name, path in model_paths.items():
            self.sessions[name] = ort.InferenceSession(
                path,
                sess_options=sess_options,
                providers=['CPUExecutionProvider'],
            )

        # Pre-allocate numpy arrays for input (avoid allocation per inference)
        self._input_buffers = {}

    def infer(self, model_name: str, features: np.ndarray) -> np.ndarray:
        """
        Run inference with pre-allocated buffers.
        features shape must match model input shape.
        """
        session = self.sessions[model_name]
        input_name = session.get_inputs()[0].name

        # Reuse buffer if shape matches (avoid allocation)
        buf_key = (model_name, features.shape)
        if buf_key not in self._input_buffers:
            self._input_buffers[buf_key] = np.empty(
                features.shape, dtype=np.float32
            )
        buf = self._input_buffers[buf_key]
        np.copyto(buf, features)

        return session.run(None, {input_name: buf})[0]
```

### 2.5 Order Execution Optimization

```python
class ZeroCopyOrderRouter:
    """
    Minimal-latency order routing via ZeroMQ.
    Target: <5ms from decision to broker submission.
    """

    def __init__(self, zmq_port: int = 5555):
        import zmq
        self.ctx = zmq.Context()

        # Use PAIR socket for lowest latency (no routing overhead)
        self.socket = self.ctx.socket(zmq.PAIR)
        self.socket.setsockopt(zmq.SNDHWM, 10)     # Send high-water mark
        self.socket.setsockopt(zmq.RCVHWM, 10)     # Receive high-water mark
        self.socket.setsockopt(zmq.LINGER, 0)       # Don't wait on close
        self.socket.setsockopt(zmq.TCP_NODELAY, 1)  # Disable Nagle's algorithm
        self.socket.connect(f"tcp://localhost:{zmq_port}")

        # Pre-allocated order template
        self._order_template = {
            "action": None, "symbol": None, "volume": None,
            "type": None, "price": None, "sl": None, "tp": None,
            "deviation": 20, "magic": 202607, "comment": "AS"
        }

    async def submit_order(self, symbol: str, side: str, volume: float,
                           price: float, sl: float, tp: float) -> dict:
        """
        Submit order with minimal serialization overhead.
        Uses pre-allocated template and compact JSON.
        """
        import json

        # Fill template (reuse dict, avoid new allocation)
        self._order_template.update({
            "action": "TRADE_ACTION_DEAL",
            "symbol": symbol,
            "volume": volume,
            "type": "ORDER_TYPE_BUY" if side == "BUY" else "ORDER_TYPE_SELL",
            "price": price,
            "sl": sl,
            "tp": tp,
        })

        # Compact JSON (no whitespace)
        msg = json.dumps(self._order_template, separators=(',', ':'))

        # Non-blocking send
        self.socket.send_string(msg, zmq.NOBLOCK)

        # Blocking receive with timeout
        if self.socket.poll(5000):  # 5s timeout
            return json.loads(self.socket.recv_string())
        else:
            raise TimeoutError("Broker did not respond within 5s")
```

### 2.6 Latency Measurement Instrumentation

```python
import time
from contextlib import contextmanager
from prometheus_client import Histogram

# Latency histograms for every hot-path stage
LATENCY_BUCKETS = (0.0005, 0.001, 0.002, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0)

tick_ingest_latency = Histogram('tick_ingest_seconds', 'Tick ingestion latency', buckets=LATENCY_BUCKETS)
signal_inference_latency = Histogram('signal_inference_seconds', 'Signal inference latency', ['agent', 'model'], buckets=LATENCY_BUCKETS)
risk_check_latency = Histogram('risk_check_seconds', 'Risk gate validation latency', buckets=LATENCY_BUCKETS)
order_routing_latency = Histogram('order_routing_seconds', 'Order routing latency', buckets=LATENCY_BUCKETS)
end_to_end_latency = Histogram('tick_to_order_seconds', 'Tick-to-order end-to-end latency', buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0))

@contextmanager
def measure_latency(histogram, **labels):
    """Context manager for latency measurement."""
    start = time.perf_counter_ns()
    yield
    elapsed = (time.perf_counter_ns() - start) / 1e9
    histogram.labels(**labels).observe(elapsed) if histogram._labelnames else histogram.observe(elapsed)

# Usage in hot path:
async def process_tick(tick):
    with measure_latency(tick_ingest_latency):
        await ingester.on_tick(tick.symbol, tick.bid, tick.ask, tick.timestamp)

    with measure_latency(signal_inference_latency, agent='smc', model='xgboost'):
        signal = smc_agent.infer(features)

    with measure_latency(risk_check_latency):
        approved = risk_gate.validate(signal)

    if approved:
        with measure_latency(order_routing_latency):
            result = router.submit_order(...)
```

---

## 3. Memory Management — 24/7 Operation

### 3.1 Memory Leak Prevention Strategy

Alpha Stack must run 24/7 without restarts. The primary memory risks:

| Source | Risk | Mitigation |
|--------|------|------------|
| **Python object accumulation** | Unbounded growth in lists/dicts | Bounded collections, explicit cleanup |
| **Redis connection pools** | Connection leak on errors | Context managers, pool health checks |
| **ONNX Runtime sessions** | Model memory not freed | Reuse sessions, never re-create |
| **Logging buffers** | Unbounded log queues | Async handler with bounded queue |
| **Pandas DataFrames** | Copy-on-write creates copies | In-place operations, explicit del |
| **Agent observation history** | Growing lists without bounds | Capped collections (deque maxlen) |
| **Redis Stream consumers** | Pending entries accumulate | Regular XACK, monitor pending count |
| **Circular references** | Python GC misses cycles | weakref for back-references |

### 3.2 Bounded Collection Patterns

```python
from collections import deque
from typing import Any
import gc
import psutil
import os

class BoundedCache:
    """
    Memory-bounded cache with LRU eviction.
    Prevents unbounded memory growth in long-running processes.
    """

    def __init__(self, max_size: int = 10000, max_memory_mb: int = 256):
        self._cache: dict[str, Any] = {}
        self._access_order: deque = deque(maxlen=max_size)
        self._max_size = max_size
        self._max_memory_bytes = max_memory_mb * 1024 * 1024

    def get(self, key: str) -> Any | None:
        if key in self._cache:
            self._access_order.append(key)
            return self._cache[key]
        return None

    def set(self, key: str, value: Any) -> None:
        self._cache[key] = value
        self._access_order.append(key)

        # Evict if over size limit
        while len(self._cache) > self._max_size:
            oldest = self._access_order.popleft()
            self._cache.pop(oldest, None)

        # Evict if over memory limit
        if self._estimate_memory() > self._max_memory_bytes:
            self._evict_to_target(self._max_memory_bytes * 0.8)

    def _estimate_memory(self) -> int:
        """Approximate memory usage in bytes."""
        import sys
        return sum(sys.getsizeof(v) for v in self._cache.values())

    def _evict_to_target(self, target_bytes: int) -> None:
        """Evict oldest entries until memory is under target."""
        while self._estimate_memory() > target_bytes and self._cache:
            oldest = self._access_order.popleft()
            self._cache.pop(oldest, None)


class CappedObservationBuffer:
    """
    Agent observation buffer with fixed capacity.
    Prevents observation history from growing unbounded.
    """

    def __init__(self, maxlen: int = 100):
        self._observations = deque(maxlen=maxlen)
        self._maxlen = maxlen

    def add(self, observation: dict) -> None:
        self._observations.append(observation)

    def get_recent(self, n: int = 10) -> list[dict]:
        return list(self._observations)[-n:]

    def clear(self) -> None:
        self._observations.clear()

    @property
    def size(self) -> int:
        return len(self._observations)
```

### 3.3 Memory Monitoring and Alerting

```python
import psutil
import asyncio
import structlog
from prometheus_client import Gauge

logger = structlog.get_logger()

# Prometheus metrics
memory_rss_mb = Gauge('process_memory_rss_mb', 'Process RSS memory in MB')
memory_vms_mb = Gauge('process_memory_vms_mb', 'Process VMS memory in MB')
memory_percent = Gauge('process_memory_percent', 'Process memory as % of system')
gc_collections = Gauge('gc_collections_total', 'GC collection counts', ['generation'])

class MemoryWatchdog:
    """
    Monitors memory usage and triggers cleanup/alerts.
    Runs as a background task in every long-running process.
    """

    def __init__(self, alert_callback=None,
                 warn_mb: int = 512, critical_mb: int = 1024,
                 growth_rate_warn_mb_per_hour: float = 10.0):
        self.alert_callback = alert_callback
        self.warn_mb = warn_mb
        self.critical_mb = critical_mb
        self.growth_rate_warn = growth_rate_warn_mb_per_hour
        self._process = psutil.Process(os.getpid())
        self._history: deque = deque(maxlen=60)  # Last 60 measurements
        self._last_rss = 0

    async def start(self, interval_seconds: int = 60):
        """Start memory monitoring loop."""
        while True:
            await self._check()
            await asyncio.sleep(interval_seconds)

    async def _check(self):
        """Perform memory check."""
        mem = self._process.memory_info()
        rss_mb = mem.rss / (1024 * 1024)
        vms_mb = mem.vms / (1024 * 1024)
        pct = self._process.memory_percent()

        # Update Prometheus
        memory_rss_mb.set(rss_mb)
        memory_vms_mb.set(vms_mb)
        memory_percent.set(pct)

        # Track history
        now = asyncio.get_event_loop().time()
        self._history.append((now, rss_mb))

        # Check growth rate
        if len(self._history) >= 10:
            old_time, old_rss = self._history[-10]
            elapsed_hours = (now - old_time) / 3600
            if elapsed_hours > 0:
                growth_rate = (rss_mb - old_rss) / elapsed_hours
                if growth_rate > self.growth_rate_warn:
                    logger.warning("memory_growth_rate_high",
                                   growth_mb_per_hour=round(growth_rate, 2),
                                   rss_mb=round(rss_mb, 1))
                    await self._trigger_cleanup("growth_rate")

        # Check absolute thresholds
        if rss_mb > self.critical_mb:
            logger.error("memory_critical", rss_mb=round(rss_mb, 1),
                         threshold_mb=self.critical_mb)
            await self._trigger_cleanup("critical")
            if self.alert_callback:
                await self.alert_callback("CRITICAL",
                    f"Memory critical: {rss_mb:.0f}MB > {self.critical_mb}MB")
        elif rss_mb > self.warn_mb:
            logger.warning("memory_warn", rss_mb=round(rss_mb, 1))
            await self._trigger_cleanup("warn")

        self._last_rss = rss_mb

    async def _trigger_cleanup(self, severity: str):
        """Trigger garbage collection and cache eviction."""
        # Force GC
        collected = gc.collect()
        logger.info("gc_triggered", severity=severity, collected=collected)

        # Log GC stats
        for i, stats in enumerate(gc.get_stats()):
            gc_collections.labels(generation=str(i)).set(stats['collections'])
```

### 3.4 Process-Level Memory Configuration

```python
# Python runtime tuning for long-running processes
import gc
import sys

def configure_python_memory():
    """
    Configure Python runtime for stable 24/7 operation.
    Call once at process startup.
    """

    # GC tuning: less frequent full collections, more incremental
    gc.set_threshold(50000, 10, 10)  # Default: (700, 10, 10)

    # Disable GC during critical sections (re-enable after)
    # gc.disable()  # Only in extreme latency-sensitive paths

    # Limit string intern pool
    sys.set_int_max_str_digits(0)  # No limit on int→str conversion

    # Increase recursion limit for deep agent chains
    sys.setrecursionlimit(500)

    # Track object creation for leak detection
    if __debug__:
        import tracemalloc
        tracemalloc.start(10)  # Track 10 frames deep
```

### 3.5 Docker Memory Limits

```yaml
# docker-compose.prod.yml — Memory limits per service
services:
  trading-engine:
    deploy:
      resources:
        limits:
          memory: 1G        # Hard limit — OOM kill if exceeded
        reservations:
          memory: 256M      # Guaranteed minimum

  ai-inference:
    deploy:
      resources:
        limits:
          memory: 2G        # Models need more headroom
        reservations:
          memory: 512M

  redis:
    command: >
      redis-server
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
    deploy:
      resources:
        limits:
          memory: 300M      # 256MB Redis + 44MB overhead

  postgres:
    shm_size: 512mb         # Shared memory for PostgreSQL
    deploy:
      resources:
        limits:
          memory: 2G
```

---

## 4. CPU Optimization — Parallel Agent Execution

### 4.1 Python GIL Mitigation Strategy

Python's Global Interpreter Lock (GIL) prevents true parallel execution of Python code. Alpha Stack uses multiple strategies:

| Strategy | Use Case | Implementation |
|----------|----------|----------------|
| **asyncio** | I/O-bound agent operations | Single event loop, cooperative multitasking |
| **multiprocessing** | CPU-bound model inference | Separate process per model |
| **Rust extensions** | Hot-path computations | PyO3 bindings, true parallelism |
| **ONNX intra-op threads** | Per-model parallelism | Configured per session |
| **Process pools** | Backtesting, batch analysis | `ProcessPoolExecutor` |

### 4.2 Agent Parallelization Architecture

```
                    ┌─────────────────────────────┐
                    │     ORCHESTRATOR PROCESS      │
                    │     (asyncio event loop)      │
                    │                               │
                    │  Phase 1: ┌────────┐ ┌──────┐│
                    │  parallel │Fundam. │ │Struct││
                    │           └────────┘ └──────┘│
                    │                               │
                    │  Phase 3: ┌────┐ ┌────┐ ┌──┐ │
                    │  parallel │SMC │ │Mom.│ │CS│ │
                    │           └────┘ └────┘ └──┘ │
                    └───────────┬───────────────────┘
                                │
           ┌────────────────────┼────────────────────┐
           ▼                    ▼                    ▼
  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
  │  INFERENCE       │ │  DATA PROCESS   │ │  EXECUTION      │
  │  PROCESS POOL    │ │  PROCESS POOL   │ │  PROCESS        │
  │                  │ │                 │ │                 │
  │  Model A (ONNX)  │ │  Feature Eng.   │ │  ZMQ Bridge     │
  │  Model B (ONNX)  │ │  Indicator Calc │ │  Order Router   │
  │  Model C (XGB)   │ │  Pattern Scan   │ │                 │
  └─────────────────┘ └─────────────────┘ └─────────────────┘
```

### 4.3 Concurrent Agent Execution

```python
import asyncio
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

class ParallelPipelineExecutor:
    """
    Executes pipeline phases with optimal parallelization.
    Phase 1 and Phase 3 are fully parallel within themselves.
    """

    def __init__(self):
        # Process pool for CPU-bound inference (bypasses GIL)
        self._inference_pool = ProcessPoolExecutor(
            max_workers=4,
            mp_context=None,  # Use default multiprocessing
        )
        # Thread pool for I/O-bound operations
        self._io_pool = ThreadPoolExecutor(max_workers=8)

    async def execute_phase_1(self, symbol: str, context: dict) -> dict:
        """
        Phase 1: Context Gathering — runs Fundamental + Structure in parallel.
        Both are independent data sources.
        """
        fundamental_task = asyncio.create_task(
            self._run_agent('fundamental', symbol, context)
        )
        structure_task = asyncio.create_task(
            self._run_agent('structure', symbol, context)
        )

        # Await both; if one fails, cancel the other
        done, pending = await asyncio.wait(
            [fundamental_task, structure_task],
            return_when=asyncio.ALL_COMPLETED,
        )

        results = {}
        for task in done:
            if task.exception():
                logger.error("phase_1_agent_failed", error=str(task.exception()))
                # Cancel pending
                for p in pending:
                    p.cancel()
                raise task.exception()
            results.update(task.result())

        return results

    async def execute_phase_3(self, symbol: str, bias: dict) -> dict:
        """
        Phase 3: Signal Detection — runs 5 agents in parallel.
        SMC, Momentum, Candlestick, Liquidity, S/R all independent.
        """
        agents = ['smc', 'momentum', 'candlestick', 'liquidity', 'sr']
        tasks = {
            agent: asyncio.create_task(
                self._run_agent(agent, symbol, {'bias': bias})
            )
            for agent in agents
        }

        results = {}
        done, _ = await asyncio.wait(
            tasks.values(),
            return_when=asyncio.ALL_COMPLETED,
            timeout=30,  # 30s timeout for all signal agents
        )

        for task in done:
            if task.exception():
                agent_name = [k for k, v in tasks.items() if v is not task][0]
                logger.warning("signal_agent_failed", agent=agent_name,
                               error=str(task.exception()))
                continue  # Skip failed agent, use remaining signals
            results.update(task.result())

        return results

    async def _run_agent(self, agent_name: str, symbol: str, context: dict) -> dict:
        """Run a single agent (I/O-bound via asyncio)."""
        agent = self._get_agent(agent_name)
        return await agent.analyze(symbol, context)

    def run_inference_offloaded(self, model_name: str, features) -> any:
        """
        Offload CPU-bound inference to separate process.
        Bypasses GIL for true parallelism.
        """
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(
            self._inference_pool,
            _inference_worker,
            model_name,
            features,
        )


def _inference_worker(model_name: str, features):
    """Worker function for process pool inference."""
    # Each process loads its own model copy
    session = _get_or_create_session(model_name)
    return session.run(None, {'input': features})[0]
```

### 4.4 Rust Extensions for Hot-Path Computation

```rust
// src/indicators.rs — Rust extension for indicator computation
use pyo3::prelude::*;
use numpy::PyReadonlyArray1;

#[pyfunction]
fn compute_rsi(prices: PyReadonlyArray1<f64>, period: usize) -> PyResult<f64> {
    let prices = prices.as_slice()?;
    if prices.len() < period + 1 {
        return Err(pyo3::exceptions::PyValueError::new_err("Insufficient data"));
    }

    let mut gains = 0.0;
    let mut losses = 0.0;

    for i in (prices.len() - period)..prices.len() {
        let change = prices[i] - prices[i - 1];
        if change > 0.0 {
            gains += change;
        } else {
            losses -= change;
        }
    }

    let avg_gain = gains / period as f64;
    let avg_loss = losses / period as f64;

    if avg_loss == 0.0 {
        return Ok(100.0);
    }

    let rs = avg_gain / avg_loss;
    Ok(100.0 - (100.0 / (1.0 + rs)))
}

#[pyfunction]
fn detect_order_blocks(
    highs: PyReadonlyArray1<f64>,
    lows: PyReadonlyArray1<f64>,
    closes: PyReadonlyArray1<f64>,
    volumes: PyReadonlyArray1<f64>,
    lookback: usize,
) -> PyResult<Vec<(usize, f64, f64, bool)>> {
    // ... OB detection algorithm
    // Returns: (index, ob_high, ob_low, is_bullish)
    Ok(vec![])
}

#[pymodule]
fn alphastack_native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(compute_rsi, m)?)?;
    m.add_function(wrap_pyfunction!(detect_order_blocks, m)?)?;
    Ok(())
}
```

### 4.5 CPU Affinity and Thread Pinning

```python
import os
import multiprocessing

def pin_process_to_cores(start_core: int, num_cores: int):
    """
    Pin process to specific CPU cores.
    Prevents context switching overhead for latency-sensitive processes.
    """
    if hasattr(os, 'sched_setaffinity'):
        cores = set(range(start_core, start_core + num_cores))
        os.sched_setaffinity(0, cores)
        logger.info("cpu_pinned", pid=os.getpid(), cores=list(cores))

# Usage:
# Trading engine on cores 0-1 (dedicated to execution)
# Signal agents on cores 2-5 (parallel inference)
# Data ingestion on core 6 (dedicated I/O)
# Monitoring on core 7 (background tasks)
```

---

## 5. Database Query Optimization

### 5.1 Query Performance Targets

| Query Category | Target p95 | Target p99 | Index Strategy |
|---------------|-----------|-----------|----------------|
| Latest tick per symbol | <1ms | <2ms | Redis hash (not DB) |
| Last 500 candles (1h) | <5ms | <10ms | Composite (symbol, timeframe, time DESC) |
| Open positions | <1ms | <2ms | Partial index WHERE status='open' |
| P&L by strategy (30d) | <20ms | <50ms | Composite (strategy_id, entry_time DESC) |
| Trades similar to setup | <50ms | <100ms | Vector index (IVFFlat) |
| Agent memory lookup | <10ms | <20ms | Composite (agent_id, symbol) |
| Pattern reliability | <5ms | <10ms | Unique constraint |
| Full backtest scan | <2s | <5s | BRIN index on time |

### 5.2 Index Optimization Catalog

```sql
-- ============================================================
-- COMPOSITE INDEXES — Match query column order exactly
-- ============================================================

-- Pattern: "Last N candles for symbol X, timeframe Y"
CREATE INDEX idx_market_data_sym_tf_time
    ON market_data (symbol, timeframe, time DESC);

-- Pattern: "All ticks for symbol X today"
CREATE INDEX idx_ticks_symbol_time
    ON ticks (symbol, time DESC);

-- Pattern: "Trades by strategy, ordered by time"
CREATE INDEX idx_trades_strategy_time
    ON trades (strategy_id, entry_time DESC);

-- Pattern: "Signals by agent, ordered by time"
CREATE INDEX idx_signals_agent_time
    ON signals (agent_id, time DESC);


-- ============================================================
-- PARTIAL INDEXES — Tiny, instant lookups for filtered queries
-- ============================================================

-- Pattern: "All open positions" (very few rows match)
CREATE INDEX idx_positions_open
    ON positions (symbol, strategy_id)
    WHERE status = 'open';

-- Pattern: "Active orders" (pending + submitted + open)
CREATE INDEX idx_orders_active
    ON orders (symbol, created_at DESC)
    WHERE status IN ('pending', 'submitted', 'open', 'partially_filled');

-- Pattern: "Active agent memories"
CREATE INDEX idx_agent_mem_active
    ON agent_memories (agent_id, symbol, importance DESC)
    WHERE active = TRUE;


-- ============================================================
-- COVERING INDEXES — Satisfy query from index alone (no table lookup)
-- ============================================================

-- Pattern: "Strategy performance summary" — needs net_pnl, symbol, confluence
CREATE INDEX idx_trades_strategy_covering
    ON trades (strategy_id, entry_time DESC)
    INCLUDE (net_pnl, symbol, confluence_score, agent_id);

-- Pattern: "Position risk check" — needs side, quantity, entry_price, sl, tp
CREATE INDEX idx_positions_risk_covering
    ON positions (symbol, strategy_id)
    INCLUDE (side, quantity, entry_price, stop_loss, take_profit, unrealized_pnl)
    WHERE status = 'open';


-- ============================================================
-- BRIN INDEXES — Tiny, efficient for naturally ordered data
-- ============================================================

-- Tick data is append-only, naturally ordered by time
CREATE INDEX idx_ticks_brin ON ticks USING BRIN (time);

-- System events are append-only
CREATE INDEX idx_system_events_brin ON system_events USING BRIN (time);


-- ============================================================
-- GIN INDEXES — For array/JSONB containment queries
-- ============================================================

-- Pattern: "News mentioning EUR/USD"
CREATE INDEX idx_news_symbols ON news_events USING GIN (symbols);

-- Pattern: "Journal entries tagged with 'breakout'"
CREATE INDEX idx_journal_tags ON journal_entries USING GIN (tags);


-- ============================================================
-- VECTOR INDEXES — For semantic similarity search
-- ============================================================

-- Pattern: "Find trades similar to current setup"
-- CREATE INDEX idx_episode_embedding ON trade_episodes
--     USING ivfflat (context_embedding vector_cosine_ops) WITH (lists = 100);
```

### 5.3 Query Optimization Patterns

```python
# ============================================================
-- PATTERN 1: Prepared statements for repeated queries
-- ============================================================

class PreparedQueryCache:
    """
    Cache prepared statements for hot queries.
    Avoids query planning overhead on repeated executions.
    """

    def __init__(self, pool):
        self._pool = pool
        self._prepared: dict[str, str] = {}

    async def execute_prepared(self, name: str, query: str, *args):
        """Execute a prepared statement."""
        async with self._pool.acquire() as conn:
            if name not in self._prepared:
                await conn.execute(f"PREPARE {name} AS {query}")
                self._prepared[name] = query
            return await conn.fetch(f"EXECUTE {name}", *args)


# ============================================================
-- PATTERN 2: Cursor-based pagination for large result sets
-- ============================================================

async def get_trades_paginated(pool, strategy_id: str, cursor=None, limit=100):
    """
    Cursor-based pagination — consistent performance regardless of offset.
    Uses the index on (strategy_id, entry_time DESC) efficiently.
    """
    async with pool.acquire() as conn:
        if cursor:
            return await conn.fetch("""
                SELECT * FROM trades
                WHERE strategy_id = $1 AND entry_time < $2
                ORDER BY entry_time DESC
                LIMIT $3
            """, strategy_id, cursor, limit)
        else:
            return await conn.fetch("""
                SELECT * FROM trades
                WHERE strategy_id = $1
                ORDER BY entry_time DESC
                LIMIT $2
            """, strategy_id, limit)


# ============================================================
-- PATTERN 3: Materialized view refresh for expensive aggregations
-- ============================================================

async def refresh_performance_views(pool):
    """
    Refresh materialized views periodically (every 5 minutes).
    Keeps dashboard queries fast without real-time computation.
    """
    async with pool.acquire() as conn:
        await conn.execute("""
            REFRESH MATERIALIZED VIEW CONCURRENTLY v_strategy_performance;
            REFRESH MATERIALIZED VIEW CONCURRENTLY v_agent_performance;
        """)
```

### 5.4 Connection Pool Tuning

```ini
# pgbouncer.ini — Optimized for trading workloads
[pgbouncer]
pool_mode = transaction          # Release connection after each transaction
max_client_conn = 200            # Max application connections
default_pool_size = 20           # Connections per user/database pair
min_pool_size = 5                # Keep warm connections
reserve_pool_size = 5            # Extra connections for spikes
reserve_pool_timeout = 3         # Seconds before using reserve pool
server_idle_timeout = 300        # Close idle server connections
client_idle_timeout = 600        # Close idle client connections
server_lifetime = 3600           # Recycle connections hourly
query_timeout = 30               # Kill queries running >30s
query_wait_timeout = 10          # Wait max 10s for a connection
```

### 5.5 TimescaleDB-Specific Optimizations

```sql
-- ============================================================
-- CHUNK TIME INTERVAL tuning
-- Smaller chunks = faster queries on recent data, more chunks to manage
-- ============================================================

-- Ticks: 1-day chunks (high write volume, short retention)
SELECT create_hypertable('ticks', 'time',
    chunk_time_interval => INTERVAL '1 day');

-- OHLCV: 7-day chunks (moderate write volume, long retention)
SELECT create_hypertable('market_data', 'time',
    chunk_time_interval => INTERVAL '7 days');

-- System events: 7-day chunks
SELECT create_hypertable('system_events', 'time',
    chunk_time_interval => INTERVAL '7 days');


-- ============================================================
-- COMPRESSION — Aggressive for old data
-- ============================================================

-- Ticks: compress after 7 days (95%+ reduction)
ALTER TABLE ticks SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol, source',
    timescaledb.compress_orderby = 'time DESC'
);
SELECT add_compression_policy('ticks', INTERVAL '7 days');

-- OHLCV: compress after 30 days
ALTER TABLE market_data SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol, timeframe',
    timescaledb.compress_orderby = 'time DESC'
);
SELECT add_compression_policy('market_data', INTERVAL '30 days');


-- ============================================================
-- CONTINUOUS AGGREGATES — Pre-computed rollups
-- ============================================================

-- Ensure refresh policies are tuned for near-real-time availability
SELECT add_continuous_aggregate_policy('candle_1m',
    start_offset => INTERVAL '5 minutes',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute');

-- Materialized views for dashboard queries
-- Refreshed every 5 minutes via application cron
CREATE MATERIALIZED VIEW v_strategy_performance AS
SELECT strategy_id, COUNT(*), SUM(net_pnl), AVG(net_pnl), ...
FROM trades WHERE status = 'closed'
GROUP BY strategy_id;
```

---

## 6. WebSocket Performance — Real-Time Data Streaming

### 6.1 WebSocket Connection Architecture

```
                    ┌─────────────────────────────────────┐
                    │         CONNECTION MANAGER            │
                    │                                       │
                    │  ┌─────────┐    ┌──────────────────┐ │
                    │  │ MT5 WS  │    │  Binance WS      │ │
                    │  │ (tick)  │    │  (combined stream)│ │
                    │  └────┬────┘    └────────┬─────────┘ │
                    │       │                  │           │
                    │  ┌────▼──────────────────▼─────────┐ │
                    │  │     MESSAGE DISPATCHER           │ │
                    │  │  (zero-copy, asyncio callback)   │ │
                    │  └────┬──────────────────┬─────────┘ │
                    │       │                  │           │
                    │  ┌────▼─────┐    ┌───────▼────────┐ │
                    │  │ Redis    │    │  Signal Agent   │ │
                    │  │ Writer   │    │  Notification   │ │
                    │  └──────────┘    └────────────────┘ │
                    └─────────────────────────────────────┘
```

### 6.2 WebSocket Optimization Techniques

```python
import asyncio
import websockets
from collections import deque

class OptimizedWebSocketManager:
    """
    High-performance WebSocket manager with:
    - Connection pooling with health monitoring
    - Message batching for high-throughput periods
    - Zero-copy message dispatch
    - Automatic reconnection with exponential backoff
    """

    def __init__(self, max_connections: int = 10):
        self._connections: dict[str, websockets.WebSocketClientProtocol] = {}
        self._health: dict[str, bool] = {}
        self._reconnect_backoff: dict[str, float] = {}
        self._message_buffer: deque = deque(maxlen=10000)
        self._handlers: dict[str, list] = {}  # channel → [handler, ...]
        self._batch_size = 50
        self._batch_interval_ms = 10  # Flush every 10ms

    async def connect(self, url: str, channel: str,
                      ping_interval: int = 15, ping_timeout: int = 10):
        """
        Establish WebSocket connection with optimized settings.
        """
        extra_headers = {}

        ws = await websockets.connect(
            url,
            ping_interval=ping_interval,
            ping_timeout=ping_timeout,
            max_size=2**20,           # 1MB max message size
            max_queue=100,             # Limit incoming queue
            close_timeout=5,
            additional_headers=extra_headers,
            # Compression can add latency; disable for tick data
            compression=None,
        )

        self._connections[channel] = ws
        self._health[channel] = True
        self._reconnect_backoff[channel] = 1.0

        # Start receive loop
        asyncio.create_task(self._receive_loop(channel, ws))

    async def _receive_loop(self, channel: str, ws):
        """
        Optimized receive loop with batching.
        """
        batch = []
        last_flush = asyncio.get_event_loop().time()

        try:
            async for message in ws:
                # Parse and dispatch immediately (zero-copy path)
                if self._handlers.get(channel):
                    for handler in self._handlers[channel]:
                        # Non-blocking dispatch
                        asyncio.create_task(handler(message))

                # Also buffer for batch consumers
                batch.append(message)

                # Flush batch if full or interval elapsed
                now = asyncio.get_event_loop().time()
                if len(batch) >= self._batch_size or \
                   (now - last_flush) * 1000 >= self._batch_interval_ms:
                    await self._flush_batch(channel, batch)
                    batch.clear()
                    last_flush = now

        except websockets.ConnectionClosed:
            self._health[channel] = False
            await self._schedule_reconnect(channel)

    async def _flush_batch(self, channel: str, batch: list):
        """Flush message batch to Redis in single pipeline."""
        if not batch:
            return
        # Batch write to Redis Stream
        async with self._redis.pipeline(transaction=False) as pipe:
            for msg in batch:
                pipe.xadd(f"stream:ticks:{channel}", {'data': msg},
                          maxlen=10000, approximate=True)
            await pipe.execute()

    async def _schedule_reconnect(self, channel: str):
        """Reconnect with exponential backoff and jitter."""
        import random
        backoff = self._reconnect_backoff.get(channel, 1.0)
        jitter = random.uniform(0, backoff * 0.5)
        delay = min(backoff + jitter, 60.0)  # Cap at 60s

        logger.warning("ws_reconnecting", channel=channel, delay_s=round(delay, 1))
        await asyncio.sleep(delay)

        url = self._get_url(channel)
        await self.connect(url, channel)

        # Increase backoff for next attempt
        self._reconnect_backoff[channel] = min(backoff * 2, 60.0)

    def on_message(self, channel: str, handler):
        """Register message handler for a channel."""
        self._handlers.setdefault(channel, []).append(handler)
```

### 6.3 MT5 Tick Streaming Optimization

```python
class MT5TickStreamer:
    """
    Optimized MT5 tick streaming.
    MT5 Python API is synchronous — must be wrapped carefully.
    """

    def __init__(self, symbols: list[str], redis_client):
        self.symbols = symbols
        self._redis = redis_client
        self._running = False
        self._last_timestamp: dict[str, int] = {}

    async def start(self):
        """Start tick streaming in background thread."""
        import MetaTrader5 as mt5

        self._running = True

        # Run MT5 polling in thread pool (avoid blocking event loop)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._stream_loop)

    def _stream_loop(self):
        """
        Blocking tick stream loop.
        Runs in thread pool to avoid blocking asyncio.
        """
        import MetaTrader5 as mt5

        while self._running:
            for symbol in self.symbols:
                tick = mt5.symbol_info_tick(symbol)
                if tick is None:
                    continue

                # Skip if same timestamp (no new tick)
                if tick.time_msc <= self._last_timestamp.get(symbol, 0):
                    continue
                self._last_timestamp[symbol] = tick.time_msc

                # Publish directly to Redis (synchronous in thread)
                self._redis.hset(f"tick:{symbol}", mapping={
                    'bid': tick.bid,
                    'ask': tick.ask,
                    'spread': tick.ask - tick.bid,
                    'mid': (tick.bid + tick.ask) / 2,
                    'time': tick.time_msc,
                    'vol': tick.volume,
                })
                self._redis.expire(f"tick:{symbol}", 60)
                self._redis.publish(f"tick:{symbol}",
                    f"{tick.bid},{tick.ask},{tick.time_msc}")

            # Minimal sleep to prevent CPU spin
            # 1ms = ~1000 checks/sec, sufficient for retail trading
            import time
            time.sleep(0.001)
```

---

## 7. Caching Strategy — Redis Hot Path

### 7.1 Cache Hierarchy

```
L0: Python process memory    (< 1μs)    Current tick, indicator state, model weights
L1: Redis                    (< 1ms)    Market state, positions, signals, session
L2: TimescaleDB (indexed)    (< 10ms)   Recent candles, open orders
L3: TimescaleDB (compressed) (< 100ms)  Historical data
L4: ClickHouse               (< 5s)     Analytical queries, backtesting
```

### 7.2 Redis Key Design

```python
# ============================================================
-- KEY PATTERNS — Designed for minimal serialization overhead
-- ============================================================

# All keys use consistent naming: {type}:{identifier}[:{subtype}]

TICK_KEY = "tick:{symbol}"                    # Hash, TTL 60s
CANDLE_KEY = "ohlcv:{symbol}:{timeframe}"     # Hash, TTL until close
BOOK_KEY = "book:{symbol}"                    # Hash, TTL 10s
SIGNAL_KEY = "signal:{agent_id}:{symbol}"     # Hash, TTL 5min
POSITION_KEY = "position:{account}:{symbol}"  # Hash, no TTL
ACCOUNT_KEY = "account:{account_id}"          # Hash, no TTL
REGIME_KEY = "regime:{symbol}"                # Hash, no TTL
SESSION_KEY = "session_state"                 # Hash, TTL 1min
INDICATOR_KEY = "ind:{symbol}:{tf}"           # Hash, TTL until candle close
PATTERN_KEY = "pat:{symbol}"                  # Hash, TTL until candle close
CALENDAR_KEY = "calendar:today"               # String (JSON), TTL 24h
CONFLUENCE_KEY = "confluence:{symbol}"        # Hash, TTL 5min


# ============================================================
-- REDIS CONFIGURATION — Optimized for trading workloads
-- ============================================================

REDIS_CONFIG = {
    'maxmemory': '256mb',
    'maxmemory-policy': 'allkeys-lru',      # Evict least recently used
    'save': '900 1 300 10 60 10000',         # RDB snapshots
    'appendonly': 'yes',
    'appendfsync': 'everysec',               # AOF with 1s sync
    'hz': 100,                               # Server tick rate
    'tcp-keepalive': 300,
    'timeout': 0,                            # No client timeout
    'tcp-backlog': 511,
}
```

### 7.3 Redis Pipeline Optimization

```python
class OptimizedRedisClient:
    """
    Redis client optimized for trading workloads.
    Uses pipelining, connection pooling, and Lua scripts.
    """

    def __init__(self, url: str):
        import redis.asyncio as redis
        self._pool = redis.ConnectionPool.from_url(
            url,
            max_connections=50,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30,
        )
        self._client = redis.Redis(connection_pool=self._pool)

        # Pre-compiled Lua scripts
        self._lua_scripts = {}

    async def update_tick(self, symbol: str, bid: float, ask: float,
                          timestamp: int, volume: float = 0.0):
        """
        Atomic tick update + publish in single round-trip.
        Uses Lua script for atomicity.
        """
        script = """
        local key = KEYS[1]
        local channel = KEYS[2]
        redis.call('HSET', key,
            'bid', ARGV[1],
            'ask', ARGV[2],
            'spread', ARGV[3],
            'mid', ARGV[4],
            'time', ARGV[5],
            'vol', ARGV[6])
        redis.call('EXPIRE', key, 60)
        redis.call('PUBLISH', channel, ARGV[7])
        return 1
        """
        await self._client.eval(
            script, 2,
            f"tick:{symbol}", f"tick:{symbol}",
            bid, ask, ask - bid, (bid + ask) / 2,
            timestamp, volume,
            f"{bid},{ask},{timestamp}",
        )

    async def batch_update_indicators(self, symbol: str, timeframe: str,
                                       indicators: dict[str, float]):
        """
        Batch update multiple indicator values in single HSET.
        """
        key = f"ind:{symbol}:{timeframe}"
        mapping = {k: str(v) for k, v in indicators.items()}
        await self._client.hset(key, mapping=mapping)
        # Expire at next candle close (approximate)
        ttl = self._ttl_for_timeframe(timeframe)
        await self._client.expire(key, ttl)

    async def get_pipeline_state(self, symbol: str) -> dict:
        """
        Get all pipeline state for a symbol in single MGET.
        Reduces round-trips from 6 to 1.
        """
        keys = [
            f"tick:{symbol}",
            f"regime:{symbol}",
            f"confluence:{symbol}",
            f"signal:smc:{symbol}",
            f"signal:momentum:{symbol}",
            f"pat:{symbol}",
        ]
        results = await self._client.mget(keys)
        return {
            'tick': results[0],
            'regime': results[1],
            'confluence': results[2],
            'signal_smc': results[3],
            'signal_momentum': results[4],
            'patterns': results[5],
        }

    @staticmethod
    def _ttl_for_timeframe(timeframe: str) -> int:
        """Get TTL in seconds for next candle close."""
        tf_seconds = {
            '1m': 60, '5m': 300, '15m': 900,
            '1h': 3600, '4h': 14400, '1d': 86400,
        }
        return tf_seconds.get(timeframe, 3600)
```

### 7.4 Cache Warming Strategy

```python
class CacheWarmer:
    """
    Pre-populate Redis cache on startup and session transitions.
    Avoids cold-start latency for first trades.
    """

    def __init__(self, redis_client, db_pool):
        self._redis = redis_client
        self._db = db_pool

    async def warm_on_startup(self):
        """
        Warm critical caches on process startup.
        """
        # 1. Load current session state
        await self._warm_session_state()

        # 2. Load today's economic calendar
        await self._warm_calendar()

        # 3. Load current regime for all active symbols
        await self._warm_regimes()

        # 4. Load latest indicators for active symbols
        await self._warm_indicators()

        # 5. Load current positions from DB
        await self._warm_positions()

        logger.info("cache_warming_complete")

    async def warm_on_session_change(self, new_session: str):
        """
        Re-warm caches on trading session transition.
        Different sessions have different active symbols.
        """
        await self._warm_session_state()
        await self._warm_indicators()

    async def _warm_indicators(self):
        """Pre-compute and cache indicators for all active symbols."""
        symbols = await self._redis.smembers("active_symbols")
        for symbol in symbols:
            for tf in ['15m', '1h', '4h']:
                candles = await self._db.fetch("""
                    SELECT * FROM market_data
                    WHERE symbol = $1 AND timeframe = $2
                    ORDER BY time DESC LIMIT 200
                """, symbol, tf)

                if candles:
                    indicators = compute_indicators(candles)
                    await self._redis.hset(
                        f"ind:{symbol}:{tf}",
                        mapping={k: str(v) for k, v in indicators.items()}
                    )
```

---

## 8. Connection Pooling — Broker, Database, API

### 8.1 Connection Pool Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    CONNECTION POOLS                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │  PostgreSQL Pool  │  │  Redis Pool      │                │
│  │  (via PgBouncer)  │  │  (direct)        │                │
│  │                   │  │                  │                │
│  │  min: 5           │  │  max: 50         │                │
│  │  max: 20          │  │  health_check: 30s│               │
│  │  mode: transaction│  │  retry: on_timeout│               │
│  └──────────────────┘  └──────────────────┘                │
│                                                              │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │  MT5 ZeroMQ Pool │  │  HTTP Client Pool│                │
│  │  (PAIR sockets)  │  │  (aiohttp)       │                │
│  │                   │  │                  │                │
│  │  connections: 1   │  │  max_per_host: 10│                │
│  │  (single bridge)  │  │  keepalive: True │                │
│  └──────────────────┘  │  timeout: 30s    │                │
│                         └──────────────────┘                │
└─────────────────────────────────────────────────────────────┘
```

### 8.2 PostgreSQL Connection Pool

```python
import asyncpg
from asyncpg import Pool

class DatabasePool:
    """
    Optimized PostgreSQL connection pool.
    Uses asyncpg for maximum async performance.
    """

    def __init__(self, dsn: str):
        self._pool: Pool | None = None
        self._dsn = dsn

    async def initialize(self):
        """Create connection pool with optimized settings."""
        self._pool = await asyncpg.create_pool(
            self._dsn,
            min_size=5,                # Keep 5 warm connections
            max_size=20,               # Max 20 connections
            max_inactive_connection_lifetime=300,  # Recycle after 5min idle
            timeout=30,                # Connection timeout
            command_timeout=30,        # Query timeout
            statement_cache_size=100,  # Cache 100 prepared statements
            max_cached_statement_lifetime=3600,
        )

    async def fetch_latest_candles(self, symbol: str, timeframe: str,
                                    limit: int = 200) -> list[dict]:
        """
        Hot query — uses prepared statement cache.
        Expected latency: <5ms with proper index.
        """
        async with self._pool.acquire() as conn:
            return await conn.fetch("""
                SELECT time, open, high, low, close, volume, vwap
                FROM market_data
                WHERE symbol = $1 AND timeframe = $2
                ORDER BY time DESC
                LIMIT $3
            """, symbol, timeframe, limit)

    async def get_open_positions(self) -> list[dict]:
        """
        Risk-critical query — partial index on (status='open').
        Expected latency: <1ms.
        """
        async with self._pool.acquire() as conn:
            return await conn.fetch("""
                SELECT id, symbol, side, quantity, entry_price,
                       current_price, unrealized_pnl, stop_loss,
                       take_profit, strategy_id, broker_id
                FROM positions
                WHERE status = 'open'
                ORDER BY opened_at
            """)

    async def bulk_insert_ticks(self, ticks: list[tuple]):
        """
        High-throughput tick insertion using COPY.
        10-100x faster than individual INSERTs.
        """
        async with self._pool.acquire() as conn:
            await conn.copy_records_to_table(
                'ticks',
                records=ticks,
                columns=['time', 'symbol', 'source', 'bid', 'ask',
                         'last', 'bid_volume', 'ask_volume'],
            )

    async def health_check(self) -> bool:
        """Check pool health."""
        try:
            async with self._pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return True
        except Exception:
            return False

    @property
    def pool_stats(self) -> dict:
        """Get pool statistics for monitoring."""
        if not self._pool:
            return {}
        return {
            'size': self._pool.get_size(),
            'free_size': self._pool.get_idle_size(),
            'min_size': self._pool.get_min_size(),
            'max_size': self._pool.get_max_size(),
        }
```

### 8.3 HTTP Client Pool (External APIs)

```python
import aiohttp
from aiohttp import TCPConnector

class HTTPClientPool:
    """
    Shared HTTP client pool for external API calls.
    Reuses TCP connections, reduces latency for repeated calls.
    """

    def __init__(self):
        self._session: aiohttp.ClientSession | None = None

    async def initialize(self):
        connector = TCPConnector(
            limit=100,                  # Total connections
            limit_per_host=10,          # Per-host limit
            ttl_dns_cache=300,          # DNS cache TTL
            enable_cleanup_closed=True,
            force_close=False,          # Keep-alive
            keepalive_timeout=30,
        )
        timeout = aiohttp.ClientTimeout(
            total=30,
            connect=10,
            sock_read=20,
        )
        self._session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
        )

    async def get(self, url: str, **kwargs) -> dict:
        """Make GET request using pooled connection."""
        async with self._session.get(url, **kwargs) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def close(self):
        if self._session:
            await self._session.close()
```

---

## 9. Profiling and Benchmarking Methodology

### 9.1 Profiling Strategy

| Tool | Use Case | When to Run | Output |
|------|----------|-------------|--------|
| **cProfile** | CPU profiling, function hotspots | Development, pre-release | Call counts, cumulative time |
| **py-spy** | Production sampling profiler | On-demand in production | Flame graphs, thread analysis |
| **memory_profiler** | Memory allocation tracking | Memory leak investigation | Line-by-line memory usage |
| **tracemalloc** | Python object tracking | Leak detection | Object allocation traces |
| **perf_counter_ns** | Micro-benchmarks | Every hot-path function | Latency histograms |
| **locust** | Load testing | Pre-release, scaling validation | Throughput, latency under load |

### 9.2 Continuous Performance Monitoring

```python
# ============================================================
-- PRODUCTION PROFILING — Always-on lightweight profiling
-- ============================================================

import cProfile
import pstats
import io

class ProductionProfiler:
    """
    Lightweight production profiler.
    Profiles hot-path functions with minimal overhead.
    """

    def __init__(self, enabled: bool = False, sample_rate: int = 100):
        self._enabled = enabled
        self._sample_rate = sample_rate
        self._counter = 0
        self._profiler = None

    def start_sample(self):
        """Start profiling a sample (called every Nth invocation)."""
        if not self._enabled:
            return

        self._counter += 1
        if self._counter % self._sample_rate != 0:
            return

        self._profiler = cProfile.Profile()
        self._profiler.enable()

    def end_sample(self) -> str | None:
        """End profiling and return stats summary."""
        if not self._profiler:
            return None

        self._profiler.disable()
        s = io.StringIO()
        ps = pstats.Stats(self._profiler, stream=s).sort_stats('cumulative')
        ps.print_stats(20)  # Top 20 functions
        self._profiler = None
        return s.getvalue()


# ============================================================
-- FLAME GRAPH GENERATION — For visual analysis
-- ============================================================

# Install: pip install py-spy
# Generate flame graph:
#   py-spy record -o flame.svg --pid <PID> --duration 30
# Generate speedscope format:
#   py-spy record -o speedscope.json --format speedscope --pid <PID> --duration 30
```

### 9.3 Benchmark Suite

```python
import time
import asyncio
import statistics

class BenchmarkSuite:
    """
    Automated benchmark suite for Alpha Stack components.
    Run before each release to detect performance regressions.
    """

    def __init__(self):
        self.results: dict[str, list[float]] = {}

    async def benchmark_tick_ingestion(self, iterations: int = 10000):
        """Benchmark tick ingestion throughput."""
        redis_client = await get_redis()
        ingester = OptimizedTickIngester(redis_client, ['EUR/USD', 'BTC/USDT'])

        latencies = []
        for i in range(iterations):
            start = time.perf_counter_ns()
            await ingester.on_tick('EUR/USD', 1.0850 + i * 0.0001,
                                    1.0851 + i * 0.0001, int(time.time()))
            elapsed = (time.perf_counter_ns() - start) / 1e6  # ms
            latencies.append(elapsed)

        self.results['tick_ingestion'] = {
            'p50': statistics.median(latencies),
            'p95': sorted(latencies)[int(0.95 * len(latencies))],
            'p99': sorted(latencies)[int(0.99 * len(latencies))],
            'mean': statistics.mean(latencies),
            'throughput_per_sec': 1000 / statistics.mean(latencies),
        }

    async def benchmark_signal_inference(self, iterations: int = 1000):
        """Benchmark signal inference latency."""
        engine = OptimizedSignalEngine({
            'smc': 'models/smc_model.onnx',
            'momentum': 'models/momentum_model.onnx',
        })

        import numpy as np
        features = np.random.randn(1, 50).astype(np.float32)

        latencies = []
        for _ in range(iterations):
            start = time.perf_counter_ns()
            engine.infer('smc', features)
            elapsed = (time.perf_counter_ns() - start) / 1e6
            latencies.append(elapsed)

        self.results['signal_inference_smc'] = {
            'p50': statistics.median(latencies),
            'p95': sorted(latencies)[int(0.95 * len(latencies))],
            'p99': sorted(latencies)[int(0.99 * len(latencies))],
        }

    async def benchmark_redis_operations(self, iterations: int = 10000):
        """Benchmark Redis hot-path operations."""
        redis = await get_redis()

        # Benchmark HSET (tick update)
        latencies = []
        for i in range(iterations):
            start = time.perf_counter_ns()
            await redis.hset(f"tick:BENCHMARK", mapping={
                'bid': 1.0850, 'ask': 1.0851, 'time': i
            })
            elapsed = (time.perf_counter_ns() - start) / 1e6
            latencies.append(elapsed)

        self.results['redis_hset'] = {
            'p50': statistics.median(latencies),
            'p95': sorted(latencies)[int(0.95 * len(latencies))],
            'p99': sorted(latencies)[int(0.99 * len(latencies))],
        }

        # Benchmark pipeline (batch tick updates)
        latencies = []
        for i in range(iterations // 100):
            pipe = redis.pipeline(transaction=False)
            start = time.perf_counter_ns()
            for j in range(100):
                pipe.hset(f"tick:BENCHMARK", mapping={
                    'bid': 1.0850 + j * 0.0001, 'ask': 1.0851, 'time': i * 100 + j
                })
            await pipe.execute()
            elapsed = (time.perf_counter_ns() - start) / 1e6
            latencies.append(elapsed / 100)  # Per-operation

        self.results['redis_pipeline_100'] = {
            'p50': statistics.median(latencies),
            'p95': sorted(latencies)[int(0.95 * len(latencies))],
        }

    async def benchmark_database_queries(self, iterations: int = 1000):
        """Benchmark database query latency."""
        db = await get_db_pool()

        # Benchmark: latest 500 candles
        latencies = []
        for _ in range(iterations):
            start = time.perf_counter_ns()
            await db.fetch_latest_candles('EUR/USD', '1h', 500)
            elapsed = (time.perf_counter_ns() - start) / 1e6
            latencies.append(elapsed)

        self.results['db_candles_500'] = {
            'p50': statistics.median(latencies),
            'p95': sorted(latencies)[int(0.95 * len(latencies))],
            'p99': sorted(latencies)[int(0.99 * len(latencies))],
        }

    def report(self) -> str:
        """Generate benchmark report."""
        lines = ["=" * 60, "ALPHA STACK BENCHMARK REPORT", "=" * 60, ""]
        for name, stats in self.results.items():
            lines.append(f"--- {name} ---")
            for metric, value in stats.items():
                if 'per_sec' in metric:
                    lines.append(f"  {metric}: {value:.0f}")
                else:
                    lines.append(f"  {metric}: {value:.3f}ms")
            lines.append("")
        return "\n".join(lines)
```

---

## 10. Performance Regression Testing

### 10.1 Regression Detection Framework

```python
import json
from pathlib import Path
from dataclasses import dataclass

@dataclass
class PerformanceBaseline:
    """Performance baseline for a specific benchmark."""
    name: str
    p50_ms: float
    p95_ms: float
    p99_ms: float
    throughput_per_sec: float | None = None

    # Acceptable regression thresholds
    p50_threshold_pct: float = 20.0   # 20% regression = fail
    p95_threshold_pct: float = 30.0   # 30% regression = fail
    p99_threshold_pct: float = 50.0   # 50% regression = fail


class RegressionDetector:
    """
    Detects performance regressions by comparing current benchmarks
    against stored baselines.
    """

    BASELINES_FILE = "benchmarks/baselines.json"

    def __init__(self):
        self.baselines: dict[str, PerformanceBaseline] = {}
        self._load_baselines()

    def _load_baselines(self):
        path = Path(self.BASELINES_FILE)
        if path.exists():
            data = json.loads(path.read_text())
            for name, stats in data.items():
                self.baselines[name] = PerformanceBaseline(name=name, **stats)

    def save_baselines(self, results: dict[str, dict]):
        """Save current results as new baselines."""
        data = {}
        for name, stats in results.items():
            data[name] = {
                'p50_ms': stats['p50'],
                'p95_ms': stats['p95'],
                'p99_ms': stats.get('p99', stats['p95']),
                'throughput_per_sec': stats.get('throughput_per_sec'),
            }
        Path(self.BASELINES_FILE).write_text(json.dumps(data, indent=2))

    def check_regressions(self, current: dict[str, dict]) -> list[str]:
        """
        Check current results against baselines.
        Returns list of regression warnings.
        """
        warnings = []

        for name, stats in current.items():
            baseline = self.baselines.get(name)
            if not baseline:
                continue

            # Check p50
            if stats['p50'] > baseline.p50_ms * (1 + baseline.p50_threshold_pct / 100):
                pct = ((stats['p50'] - baseline.p50_ms) / baseline.p50_ms) * 100
                warnings.append(
                    f"REGRESSION: {name} p50 {stats['p50']:.2f}ms "
                    f"({pct:+.1f}% vs baseline {baseline.p50_ms:.2f}ms)"
                )

            # Check p95
            if stats['p95'] > baseline.p95_ms * (1 + baseline.p95_threshold_pct / 100):
                pct = ((stats['p95'] - baseline.p95_ms) / baseline.p95_ms) * 100
                warnings.append(
                    f"REGRESSION: {name} p95 {stats['p95']:.2f}ms "
                    f"({pct:+.1f}% vs baseline {baseline.p95_ms:.2f}ms)"
                )

        return warnings
```

### 10.2 CI Integration

```yaml
# .github/workflows/performance.yml
name: Performance Tests

on:
  pull_request:
    branches: [main]
  schedule:
    - cron: "0 6 * * 1"  # Weekly on Monday at 06:00 UTC

jobs:
  benchmark:
    runs-on: ubuntu-latest
    services:
      redis:
        image: redis:7-alpine
        ports: ["6379:6379"]
      postgres:
        image: timescale/timescaledb:latest-pg16
        env:
          POSTGRES_DB: alphastack_bench
          POSTGRES_USER: bench
          POSTGRES_PASSWORD: bench
        ports: ["5432:5432"]

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip

      - name: Install dependencies
        run: pip install -r requirements-dev.txt

      - name: Run benchmarks
        run: python -m benchmarks.run_all --output results.json

      - name: Check regressions
        run: python -m benchmarks.check_regressions --results results.json

      - name: Upload results
        uses: actions/upload-artifact@v4
        with:
          name: benchmark-results
          path: results.json

      - name: Comment on PR
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const results = JSON.parse(fs.readFileSync('results.json', 'utf8'));
            let body = '## 🏎️ Performance Benchmark Results\n\n';
            body += '| Metric | p50 | p95 | p99 | Status |\n';
            body += '|--------|-----|-----|-----|--------|\n';
            for (const [name, stats] of Object.entries(results)) {
              body += `| ${name} | ${stats.p50.toFixed(2)}ms | ${stats.p95.toFixed(2)}ms | ${(stats.p99||0).toFixed(2)}ms | ✅ |\n`;
            }
            github.rest.issues.createComment({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: context.issue.number,
              body: body
            });
```

### 10.3 Performance Budget (CI Gate)

```python
# benchmarks/performance_budget.py
"""
Hard performance budget — CI fails if any metric exceeds threshold.
"""

PERFORMANCE_BUDGET = {
    'tick_ingestion': {
        'p95_max_ms': 2.0,        # Must be < 2ms at p95
        'throughput_min_per_sec': 5000,  # Must handle 5000 ticks/sec
    },
    'signal_inference_smc': {
        'p95_max_ms': 50.0,       # Must be < 50ms at p95
    },
    'redis_hset': {
        'p95_max_ms': 1.0,        # Must be < 1ms at p95
    },
    'redis_pipeline_100': {
        'p95_max_ms': 0.5,        # Per-op < 0.5ms at p95
    },
    'db_candles_500': {
        'p95_max_ms': 10.0,       # Must be < 10ms at p95
    },
    'db_open_positions': {
        'p95_max_ms': 2.0,        # Must be < 2ms at p95
    },
}

def check_budget(results: dict[str, dict]) -> list[str]:
    """Return list of budget violations."""
    violations = []
    for metric, budget in PERFORMANCE_BUDGET.items():
        if metric not in results:
            continue
        stats = results[metric]
        for key, max_val in budget.items():
            actual_key = key.replace('_max_ms', '').replace('_min_per_sec', '')
            actual = stats.get(actual_key, 0)
            if 'max' in key and actual > max_val:
                violations.append(
                    f"BUDGET VIOLATION: {metric}.{actual_key} = {actual:.2f} "
                    f"(budget: {max_val})"
                )
            elif 'min' in key and actual < max_val:
                violations.append(
                    f"BUDGET VIOLATION: {metric}.{actual_key} = {actual:.0f} "
                    f"(budget: {max_val})"
                )
    return violations
```

---

## 11. Resource Scaling Triggers

### 11.1 Scaling Decision Matrix

| Metric | Warning Threshold | Critical Threshold | Action |
|--------|------------------|-------------------|--------|
| **CPU (trading-engine)** | >60% sustained 5min | >80% sustained 2min | Add core affinity, reduce inference frequency |
| **CPU (ai-inference)** | >70% sustained 5min | >85% sustained 2min | Add process pool workers, offload to separate VPS |
| **Memory (any process)** | >512MB RSS | >1GB RSS | Trigger GC, evict caches, restart process |
| **Memory (Redis)** | >200MB | >240MB | Trim streams, reduce TTLs, increase maxmemory |
| **Disk (data volume)** | >80% used | >90% used | Enable compression, archive old data, expand volume |
| **DB Connections** | >80% of pool | >95% of pool | Increase pool size, add PgBouncer, add read replica |
| **Redis Connections** | >40 of 50 | >48 of 50 | Increase pool, optimize pipeline usage |
| **Stream Consumer Lag** | >1000 messages | >10000 messages | Add consumer instances, optimize processing |
| **Tick Ingestion Latency** | >5ms p95 | >20ms p95 | Check broker connection, reduce polling interval |
| **Signal Inference Latency** | >100ms p95 | >500ms p95 | Switch to lighter model, increase process pool |
| **DB Query Latency** | >50ms p95 | >200ms p95 | Add indexes, increase cache, add read replica |
| **WebSocket Reconnects** | >3/hour | >10/hour | Check broker status, add connection redundancy |
| **Error Rate** | >1% of operations | >5% of operations | Halt new trades, investigate, alert human |

### 11.2 Auto-Scaling Actions

```python
class ResourceScaler:
    """
    Automatic resource scaling based on metrics.
    Conservative: prefers optimization over scaling.
    """

    def __init__(self, config: dict):
        self.config = config
        self._last_scale_action: dict[str, float] = {}

    async def evaluate_and_scale(self, metrics: dict):
        """
        Evaluate current metrics and take scaling actions.
        Minimum 5-minute cooldown between scaling actions.
        """
        now = time.time()

        # CPU scaling
        if metrics.get('cpu_pct', 0) > 80:
            if self._can_scale('cpu', now):
                await self._scale_cpu(metrics)
                self._last_scale_action['cpu'] = now

        # Memory scaling
        if metrics.get('memory_rss_mb', 0) > 512:
            if self._can_scale('memory', now):
                await self._scale_memory(metrics)
                self._last_scale_action['memory'] = now

        # Connection pool scaling
        if metrics.get('db_pool_usage_pct', 0) > 80:
            if self._can_scale('db_pool', now):
                await self._scale_db_pool(metrics)
                self._last_scale_action['db_pool'] = now

        # Stream consumer lag
        if metrics.get('stream_lag', 0) > 1000:
            if self._can_scale('consumers', now):
                await self._scale_consumers(metrics)
                self._last_scale_action['consumers'] = now

    def _can_scale(self, resource: str, now: float) -> bool:
        """Check cooldown period."""
        last = self._last_scale_action.get(resource, 0)
        return (now - last) > 300  # 5-minute cooldown

    async def _scale_cpu(self, metrics: dict):
        """
        CPU scaling strategy:
        1. First: reduce inference frequency (cheap)
        2. Second: switch to lighter model (medium)
        3. Third: add process pool workers (medium)
        4. Fourth: offload to separate VPS (expensive)
        """
        current_workers = metrics.get('inference_pool_workers', 2)
        if current_workers < 4:
            logger.info("scaling_cpu", action="add_inference_worker",
                       workers=current_workers + 1)
            # Signal to process pool to add a worker
            await self._signal('inference_pool', 'add_worker')

    async def _scale_memory(self, metrics: dict):
        """
        Memory scaling strategy:
        1. First: force GC (free)
        2. Second: evict LRU caches (free)
        3. Third: reduce Redis TTLs (free)
        4. Fourth: restart process (brief downtime)
        """
        import gc
        collected = gc.collect()
        logger.info("memory_gc", collected=collected, rss_mb=metrics.get('memory_rss_mb'))

        # If still high after GC, reduce caches
        if metrics.get('memory_rss_mb', 0) > 512:
            await self._signal('cache', 'evict_lru')

    async def _scale_db_pool(self, metrics: dict):
        """Increase DB connection pool size."""
        current = metrics.get('db_pool_size', 20)
        new_size = min(current + 5, 50)  # Cap at 50
        logger.info("scaling_db_pool", old=current, new=new_size)
        await self._signal('db_pool', f'resize:{new_size}')

    async def _scale_consumers(self, metrics: dict):
        """Add stream consumer instances for lagging consumers."""
        logger.info("scaling_consumers", lag=metrics.get('stream_lag'))
        # This would trigger spawning additional consumer instances
        # In Phase 1-3, this is limited by single-process architecture
```

### 11.3 Infrastructure Scaling Phases

```
PHASE 1 ($7 capital): Single VPS (2 vCPU, 4GB RAM)
├── All services in single Docker Compose
├── Max: 3 pairs, 1 strategy, ~10 trades/day
├── Bottleneck: CPU (AI inference)
└── Scale trigger: CPU >70% sustained → Phase 2

PHASE 2 ($100 capital): Upgraded VPS (4 vCPU, 8GB RAM)
├── Same Docker Compose, more resources
├── Max: 10 pairs, 3 strategies, ~50 trades/day
├── Bottleneck: Memory (model loading)
└── Scale trigger: Memory >80% OR CPU >70% → Phase 3

PHASE 3 ($1K capital): Split VPS (App: 4vCPU/8GB + DB: 2vCPU/4GB)
├── Application and database on separate VPS
├── WireGuard tunnel between VPS
├── Max: 28 pairs, 5 strategies, ~200 trades/day
├── Bottleneck: DB query latency (cross-VPS)
└── Scale trigger: DB latency >50ms p95 → Phase 4

PHASE 4 ($10K capital): Professional (3+ VPS + managed services)
├── K3s cluster, managed PostgreSQL, Redis Cluster
├── Max: 50+ pairs, 10+ strategies, ~1000 trades/day
├── Bottleneck: Inter-service communication
└── Scale trigger: Multi-region latency requirements → Phase 5

PHASE 5 ($100K capital): Multi-region cluster
├── Kubernetes across regions
├── Co-located execution near broker
├── Max: Institutional volume
└── Bottleneck: Market impact (not infrastructure)
```

---

## 12. Implementation Roadmap

### Phase 1: Foundation (Week 1-2)

```
□ Implement tick ingestion with Redis pipeline batching
□ Configure ONNX Runtime for signal inference
□ Set up asyncpg connection pool with PgBouncer
□ Implement bounded cache collections
□ Add latency instrumentation to all hot-path functions
□ Configure Python GC for long-running processes
□ Set up Prometheus metrics for latency/memory/CPU
□ Write benchmark suite for core operations
□ Run baseline benchmarks and store results
□ Verify: tick-to-order <500ms in local testing
```

### Phase 2: Optimization (Week 3-4)

```
□ Implement Rust extensions for indicator computation
□ Implement cache warming on startup and session change
□ Optimize Redis Lua scripts for atomic operations
□ Set up memory watchdog with alerting
□ Implement WebSocket connection manager with batching
□ Add CPU affinity pinning for trading engine
□ Optimize database indexes (EXPLAIN ANALYZE audit)
□ Set up performance regression CI pipeline
□ Implement auto-scaling triggers (CPU, memory, connections)
□ Verify: signal inference <50ms p95, DB queries <10ms p95
```

### Phase 3: Hardening (Week 5-8)

```
□ Implement parallel agent execution with process pools
□ Add production profiler (py-spy integration)
□ Implement connection pool health monitoring
□ Set up load testing with locust (100+ concurrent signals)
□ Implement stream consumer lag monitoring and auto-scaling
□ Add circuit breakers for all external connections
□ Implement graceful degradation (reduced functionality on overload)
□ Performance budget enforcement in CI
□ Memory leak detection (24h soak test)
□ Verify: 24h stable operation, <1MB/hour memory growth
```

### Phase 4: Scale (Week 9+)

```
□ Evaluate and implement ClickHouse for analytical queries
□ Implement Kafka for event bus (if Redis Streams insufficient)
□ Add read replicas for database
□ Implement Redis Cluster for distributed caching
□ Multi-region latency testing
□ Capacity planning for 50+ pairs
□ Performance review with production traffic data
□ Document: Performance tuning playbook
```

---

## Appendix A: Performance Checklist

### Pre-Launch Checklist

- [ ] All hot-path functions instrumented with latency metrics
- [ ] ONNX models loaded at startup (no cold-start inference)
- [ ] Redis pipelining used for all batch operations
- [ ] Database queries use prepared statements
- [ ] All indexes match query patterns (EXPLAIN ANALYZE verified)
- [ ] Connection pools configured with min/max limits
- [ ] Memory watchdog running in every long-lived process
- [ ] Bounded collections used for all growing data structures
- [ ] GC thresholds tuned for trading workload
- [ ] CPU affinity set for trading engine process
- [ ] WebSocket ping/pong configured (15s interval)
- [ ] Circuit breakers on all external connections
- [ ] Performance budget defined and enforced in CI
- [ ] Benchmark suite runs on every PR
- [ ] 24h soak test passed (<1MB/hour memory growth)
- [ ] Load test passed (100 concurrent signal evaluations)
- [ ] Redis maxmemory and eviction policy configured
- [ ] TimescaleDB compression policies active
- [ ] PgBouncer configured for transaction pooling
- [ ] All timeouts set (no infinite waits)

### Daily Operations Checklist

- [ ] Check Grafana: latency dashboards within budget
- [ ] Check Prometheus: no firing alerts
- [ ] Check Redis: memory usage <80%
- [ ] Check PostgreSQL: connection pool usage <80%
- [ ] Check disk: usage <80%
- [ ] Check error rate: <1% of operations
- [ ] Check stream consumer lag: <100 messages

---

## Appendix B: Technology-Specific Tuning

### Python 3.11+ Tuning

```python
# Start Python with optimized flags
# python -X utf8 -X faulthandler -O src/main.py

# Or in code:
import sys
sys.set_int_max_str_digits(0)    # No int-to-str limit
sys.setrecursionlimit(500)       # Limit recursion depth
```

### Redis 7 Tuning

```conf
# redis.conf
maxmemory 256mb
maxmemory-policy allkeys-lru
hz 100
tcp-keepalive 300
tcp-backlog 511
timeout 0
save 900 1
save 300 10
save 60 10000
appendonly yes
appendfsync everysec
no-appendfsync-on-rewrite yes
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb
```

### PostgreSQL 16 + TimescaleDB Tuning

```conf
# postgresql.conf
shared_buffers = 512MB           # 25% of RAM
effective_cache_size = 1536MB    # 75% of RAM
work_mem = 16MB                  # Per-operation sort memory
maintenance_work_mem = 256MB     # VACUUM, CREATE INDEX
max_connections = 100            # Via PgBouncer
max_parallel_workers_per_gather = 2
max_parallel_workers = 4
wal_buffers = 64MB
checkpoint_completion_target = 0.9
random_page_cost = 1.1           # SSD
effective_io_concurrency = 200   # SSD
shared_preload_libraries = 'timescaledb,pg_stat_statements'
```

### Docker Tuning

```yaml
# docker-compose.yml — Performance-oriented settings
services:
  trading-engine:
    cgroup: host
    ulimits:
      nofile:
        soft: 65536
        hard: 65536
    sysctls:
      net.core.somaxconn: 65535
      net.ipv4.tcp_max_syn_backlog: 65535
```

---

*This performance architecture is designed to be implemented incrementally. Phase 1 delivers <500ms tick-to-order latency on a €5 VPS. Each subsequent phase optimizes further while maintaining the safety-first design of the trading system. Measure first, optimize the hot paths, and never sacrifice correctness for speed.*

*Generated: 2026-07-11*
*Next review: After Phase 2 benchmark results*
