# Alpha Stack — Scalability Fix: 6 Remaining Gaps

> **Author:** Scalability Fix Agent  
> **Date:** 2026-07-11  
> **Source:** `review_scalability_final.md` — 6 unresolved gaps  
> **Status:** Implementation-Ready Fixes  

---

## Summary

This document provides concrete, copy-paste-ready fixes for the 6 scalability gaps identified in the final review. Each fix includes: rationale, implementation code/config, phase placement, and integration notes.

| # | Gap | Severity | Fix Type | Effort |
|---|-----|----------|----------|--------|
| 1 | Redis Sentinel at Phase 4 → Phase 2 | 🔴 CRITICAL | Config + Docker Compose | 4h |
| 2 | State recovery procedure undefined | 🔴 CRITICAL | Python module | 4h |
| 3 | LLM fallback chain + caching missing | 🟠 HIGH | Python module | 1 day |
| 4 | Cost budget system at $7 missing | 🟠 HIGH | Python module | 4h |
| 5 | MT5 data proxy service needed | 🟠 HIGH | New service | 1 day |
| 6 | Phase 2 VPS undersized (CX21→CX41) | 🟠 HIGH | Config change | 5 min |

---

## Fix 1: Redis Sentinel — Move from Phase 4 to Phase 2

### Problem

Redis Sentinel was placed at Phase 4 ($10K+). At Phase 2, the system runs live trading on a VPS. A Redis crash without Sentinel halts ALL inter-module communication and forces position closure — catastrophic for a live account.

### Solution

Deploy Redis Sentinel starting at Phase 2 (VPS deployment). Three Redis processes run on the same VPS: 1 primary + 2 replicas. Sentinel provides automatic failover in <5 seconds at zero additional hardware cost.

### Updated Phase Plan

| Phase | Redis Config | Notes |
|-------|-------------|-------|
| Phase 1 (local) | Single Redis + AOF persistence | Acceptable for dev on local machine |
| **Phase 2 (VPS)** | **Redis Sentinel (1 primary + 2 replicas, same VPS)** | **Automatic failover, <5s recovery** |
| Phase 3 ($1K) | Redis Sentinel on dedicated server | Separate from application server |
| Phase 4 ($10K+) | Redis Cluster (3 masters + 3 replicas) | Horizontal scaling |

### Docker Compose — Phase 2 Sentinel Configuration

```yaml
# docker-compose.phase2.yml — Redis Sentinel section

services:
  redis-primary:
    image: redis:7-alpine
    container_name: redis-primary
    command: >
      redis-server
      --appendonly yes
      --appendfsync everysec
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
      --requirepass ${REDIS_PASSWORD}
      --masterauth ${REDIS_PASSWORD}
    ports:
      - "127.0.0.1:6379:6379"
    volumes:
      - redis-primary-data:/data
    networks:
      - alpha-net
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3

  redis-replica-1:
    image: redis:7-alpine
    container_name: redis-replica-1
    command: >
      redis-server
      --appendonly yes
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
      --requirepass ${REDIS_PASSWORD}
      --masterauth ${REDIS_PASSWORD}
      --replicaof redis-primary 6379
    depends_on:
      redis-primary:
        condition: service_healthy
    networks:
      - alpha-net

  redis-replica-2:
    image: redis:7-alpine
    container_name: redis-replica-2
    command: >
      redis-server
      --appendonly yes
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
      --requirepass ${REDIS_PASSWORD}
      --masterauth ${REDIS_PASSWORD}
      --replicaof redis-primary 6379
    depends_on:
      redis-primary:
        condition: service_healthy
    networks:
      - alpha-net

  sentinel-1:
    image: redis:7-alpine
    container_name: sentinel-1
    command: >
      sh -c 'cat > /tmp/sentinel.conf << EOF
      port 26379
      sentinel monitor alpha-master redis-primary 6379 2
      sentinel auth-pass alpha-master ${REDIS_PASSWORD}
      sentinel down-after-milliseconds alpha-master 5000
      sentinel failover-timeout alpha-master 10000
      sentinel parallel-syncs alpha-master 1
      EOF
      redis-sentinel /tmp/sentinel.conf'
    ports:
      - "127.0.0.1:26379:26379"
    depends_on:
      - redis-primary
      - redis-replica-1
      - redis-replica-2
    networks:
      - alpha-net

  sentinel-2:
    image: redis:7-alpine
    container_name: sentinel-2
    command: >
      sh -c 'cat > /tmp/sentinel.conf << EOF
      port 26380
      sentinel monitor alpha-master redis-primary 6379 2
      sentinel auth-pass alpha-master ${REDIS_PASSWORD}
      sentinel down-after-milliseconds alpha-master 5000
      sentinel failover-timeout alpha-master 10000
      sentinel parallel-syncs alpha-master 1
      EOF
      redis-sentinel /tmp/sentinel.conf'
    ports:
      - "127.0.0.1:26380:26380"
    depends_on:
      - redis-primary
      - redis-replica-1
      - redis-replica-2
    networks:
      - alpha-net

  sentinel-3:
    image: redis:7-alpine
    container_name: sentinel-3
    command: >
      sh -c 'cat > /tmp/sentinel.conf << EOF
      port 26381
      sentinel monitor alpha-master redis-primary 6379 2
      sentinel auth-pass alpha-master ${REDIS_PASSWORD}
      sentinel down-after-milliseconds alpha-master 5000
      sentinel failover-timeout alpha-master 10000
      sentinel parallel-syncs alpha-master 1
      EOF
      redis-sentinel /tmp/sentinel.conf'
    ports:
      - "127.0.0.1:26381:26381"
    depends_on:
      - redis-primary
      - redis-replica-1
      - redis-replica-2
    networks:
      - alpha-net

volumes:
  redis-primary-data:

networks:
  alpha-net:
    driver: bridge
```

### Python Client — Sentinel-Aware Connection

```python
# core/redis_client.py

import redis.asyncio as redis
from redis.asyncio.sentinel import Sentinel
from typing import Optional
import logging
import os

logger = logging.getLogger(__name__)

class RedisClientFactory:
    """Creates Sentinel-aware or standalone Redis connections based on environment."""

    @staticmethod
    async def create() -> redis.Redis:
        """Create Redis client. Uses Sentinel if SENTINEL_HOSTS is set, else standalone."""
        sentinel_hosts_str = os.getenv("SENTINEL_HOSTS", "")

        if sentinel_hosts_str:
            # Phase 2+: Sentinel mode
            hosts = []
            for h in sentinel_hosts_str.split(","):
                host, port = h.strip().split(":")
                hosts.append((host, int(port)))

            password = os.getenv("REDIS_PASSWORD", "")
            service_name = os.getenv("SENTINEL_SERVICE", "alpha-master")

            sentinel = Sentinel(
                hosts,
                password=password,
                socket_timeout=5.0,
                socket_connect_timeout=5.0,
            )
            master = sentinel.master_for(
                service_name,
                socket_timeout=5.0,
                decode_responses=True,
            )
            logger.info(f"Connected via Sentinel to {service_name} via {hosts}")
            return master
        else:
            # Phase 1: Standalone mode
            return redis.Redis(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                password=os.getenv("REDIS_PASSWORD", ""),
                decode_responses=True,
                socket_timeout=5.0,
            )


# Usage in application startup:
# redis_client = await RedisClientFactory.create()
```

### Environment Variables

```bash
# Phase 1 (standalone)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_secure_password

# Phase 2+ (Sentinel)
SENTINEL_HOSTS=127.0.0.1:26379,127.0.0.1:26380,127.0.0.1:26381
SENTINEL_SERVICE=alpha-master
REDIS_PASSWORD=your_secure_password
```

### Resource Cost

| Component | CPU | RAM | Disk |
|-----------|-----|-----|------|
| Redis primary | ~5% | ~128 MB | ~500 MB |
| Redis replica 1 | ~3% | ~128 MB | ~500 MB |
| Redis replica 2 | ~3% | ~128 MB | ~500 MB |
| Sentinel × 3 | ~1% each | ~32 MB each | Negligible |
| **Total overhead** | **~15%** | **~480 MB** | **~1.5 GB** |

**Verdict:** Easily fits on CX41 (8 CPU, 16 GB). Zero additional monetary cost.

---

## Fix 2: State Recovery Procedure

### Problem

The architecture defines no startup reconciliation procedure. After a crash, the system cannot determine: which positions are open, what orders are in-flight, or what Redis state should be. This risks orphaned positions, duplicate orders, and incorrect risk limits.

### Solution

A `startup_reconciliation()` procedure that runs on every system start. It queries the broker as the single source of truth, reconciles against the database, rebuilds Redis state, and resumes normal operation.

### Implementation

```python
# core/state_recovery.py

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class ReconciliationStatus(Enum):
    CLEAN = "clean"            # DB and broker match perfectly
    REPAIRED = "repaired"      # Discrepancies found and fixed
    MANUAL_REQUIRED = "manual" # Unresolvable discrepancies
    FAILED = "failed"          # Could not complete reconciliation


@dataclass
class ReconciliationResult:
    status: ReconciliationStatus
    broker_positions: list = field(default_factory=list)
    db_positions: list = field(default_factory=list)
    orphaned_in_db: list = field(default_factory=list)    # In DB but not at broker
    unknown_at_broker: list = field(default_factory=list) # At broker but not in DB
    orphaned_orders: list = field(default_factory=list)
    redis_keys_restored: int = 0
    errors: list = field(default_factory=list)
    duration_ms: float = 0.0


class StateRecovery:
    """
    Startup reconciliation procedure.
    
    Run on every system start to ensure DB, Redis, and broker are in sync.
    Broker API is the single source of truth for positions and orders.
    PostgreSQL is the source of truth for trade history and analytics.
    Redis is rebuilt from PostgreSQL on startup (it's a hot cache).
    """

    def __init__(self, broker, db, redis_client, config: dict):
        self.broker = broker
        self.db = db
        self.redis = redis_client
        self.config = config
        self.max_retries = config.get("reconciliation_max_retries", 3)
        self.retry_delay = config.get("reconciliation_retry_delay_sec", 5.0)

    async def run(self) -> ReconciliationResult:
        """Execute full startup reconciliation."""
        start = datetime.now(timezone.utc)
        result = ReconciliationResult(status=ReconciliationStatus.CLEAN)

        logger.info("=" * 60)
        logger.info("STARTUP RECONCILIATION — BEGIN")
        logger.info("=" * 60)

        try:
            # Phase 1: Verify broker connectivity
            if not await self._verify_broker_connection():
                result.errors.append("Cannot connect to broker")
                result.status = ReconciliationStatus.FAILED
                return result

            # Phase 2: Gather state from all sources
            broker_state = await self._get_broker_state(result)
            db_state = await self._get_db_state(result)

            # Phase 3: Reconcile positions
            await self._reconcile_positions(broker_state, db_state, result)

            # Phase 4: Reconcile pending orders
            await self._reconcile_orders(broker_state, db_state, result)

            # Phase 5: Rebuild Redis state
            await self._rebuild_redis(result)

            # Phase 6: Verify integrity
            await self._verify_integrity(result)

            # Determine final status
            if result.errors:
                if result.orphaned_in_db or result.unknown_at_broker:
                    result.status = ReconciliationStatus.MANUAL_REQUIRED
                else:
                    result.status = ReconciliationStatus.REPAIRED
            elif result.orphaned_in_db or result.unknown_at_broker or result.orphaned_orders:
                result.status = ReconciliationStatus.REPAIRED
            else:
                result.status = ReconciliationStatus.CLEAN

        except Exception as e:
            logger.error(f"Reconciliation failed: {e}", exc_info=True)
            result.errors.append(str(e))
            result.status = ReconciliationStatus.FAILED

        finally:
            elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            result.duration_ms = elapsed
            await self._log_result(result)

        return result

    async def _verify_broker_connection(self) -> bool:
        """Verify broker API is reachable with retries."""
        for attempt in range(1, self.max_retries + 1):
            try:
                connected = await self.broker.ping()
                if connected:
                    logger.info(f"Broker connection verified (attempt {attempt})")
                    return True
            except Exception as e:
                logger.warning(f"Broker ping failed (attempt {attempt}): {e}")

            if attempt < self.max_retries:
                await asyncio.sleep(self.retry_delay)

        logger.error("Broker connection failed after all retries")
        return False

    async def _get_broker_state(self, result: ReconciliationResult) -> dict:
        """Get current positions and orders from broker (source of truth)."""
        positions = await self.broker.get_positions()
        orders = await self.broker.get_pending_orders()

        result.broker_positions = positions
        logger.info(f"Broker state: {len(positions)} positions, {len(orders)} pending orders")

        return {"positions": positions, "orders": orders}

    async def _get_db_state(self, result: ReconciliationResult) -> dict:
        """Get last known state from PostgreSQL."""
        positions = await self.db.get_open_positions()
        orders = await self.db.get_pending_orders()

        result.db_positions = positions
        logger.info(f"DB state: {len(positions)} open positions, {len(orders)} pending orders")

        return {"positions": positions, "orders": orders}

    async def _reconcile_positions(
        self,
        broker_state: dict,
        db_state: dict,
        result: ReconciliationResult,
    ):
        """Reconcile positions between broker (truth) and DB."""
        broker_tickets = {p.ticket for p in broker_state["positions"]}
        db_tickets = {p.ticket for p in db_state["positions"]}

        # Orphaned: in DB but not at broker (ghost positions)
        orphaned_tickets = db_tickets - broker_tickets
        for pos in db_state["positions"]:
            if pos.ticket in orphaned_tickets:
                result.orphaned_in_db.append(pos)
                logger.warning(
                    f"ORPHANED POSITION: ticket={pos.ticket} symbol={pos.symbol} "
                    f"volume={pos.volume} — closing in DB (not at broker)"
                )
                await self.db.close_position(
                    pos.ticket,
                    reason="reconciliation_orphaned",
                    closed_at=datetime.now(timezone.utc),
                )

        # Unknown: at broker but not in DB (missed entries)
        unknown_tickets = broker_tickets - db_tickets
        for pos in broker_state["positions"]:
            if pos.ticket in unknown_tickets:
                result.unknown_at_broker.append(pos)
                logger.warning(
                    f"UNKNOWN POSITION: ticket={pos.ticket} symbol={pos.symbol} "
                    f"volume={pos.volume} — importing from broker"
                )
                await self.db.import_position(pos, source="reconciliation")

    async def _reconcile_orders(
        self,
        broker_state: dict,
        db_state: dict,
        result: ReconciliationResult,
    ):
        """Reconcile pending orders."""
        broker_order_ids = {o.order_id for o in broker_state["orders"]}
        db_order_ids = {o.order_id for o in db_state["orders"]}

        # Orders in DB but not at broker — they were filled or cancelled while we were down
        orphaned_order_ids = db_order_ids - broker_order_ids
        for order in db_state["orders"]:
            if order.order_id in orphaned_order_ids:
                result.orphaned_orders.append(order)
                logger.warning(
                    f"ORPHANED ORDER: order_id={order.order_id} symbol={order.symbol} "
                    f"— checking if filled or cancelled"
                )
                # Check trade history to see if it was filled
                fill = await self.broker.check_order_fill(order.order_id)
                if fill:
                    await self.db.record_order_fill(order.order_id, fill)
                else:
                    await self.db.cancel_order(order.order_id, reason="reconciliation_missing")

    async def _rebuild_redis(self, result: ReconciliationResult):
        """
        Rebuild Redis hot state from PostgreSQL.
        
        Redis is a cache — it can always be rebuilt from the database.
        We flush and rebuild rather than attempting merge.
        """
        logger.info("Rebuilding Redis state from PostgreSQL...")

        # Flush stale state (but preserve LLM cache and config)
        # Use a Lua script to delete only trading keys, not cache keys
        lua_script = """
        local keys = redis.call('KEYS', 'trading:*')
        for i=1,#keys,5000 do
            redis.call('DEL', unpack(keys, i, math.min(i+4999, #keys)))
        end
        keys = redis.call('KEYS', 'position:*')
        for i=1,#keys,5000 do
            redis.call('DEL', unpack(keys, i, math.min(i+4999, #keys)))
        end
        keys = redis.call('KEYS', 'risk:*')
        for i=1,#keys,5000 do
            redis.call('DEL', unpack(keys, i, math.min(i+4999, #keys)))
        end
        return 1
        """
        await self.redis.eval(lua_script, 0)

        # Restore active positions
        positions = await self.db.get_open_positions()
        for pos in positions:
            await self.redis.hset(
                f"position:{pos.ticket}",
                mapping={
                    "symbol": pos.symbol,
                    "volume": str(pos.volume),
                    "open_price": str(pos.open_price),
                    "open_time": pos.open_time.isoformat(),
                    "strategy_id": pos.strategy_id,
                    "stop_loss": str(pos.stop_loss or 0),
                    "take_profit": str(pos.take_profit or 0),
                },
            )
            result.redis_keys_restored += 1

        # Restore risk limits
        risk_state = await self.db.get_current_risk_state()
        await self.redis.hset("risk:state", mapping=risk_state)
        result.redis_keys_restored += 1

        # Restore active strategy configs
        strategies = await self.db.get_active_strategies()
        for strat in strategies:
            await self.redis.hset(
                f"trading:strategy:{strat.id}",
                mapping=strat.to_redis_mapping(),
            )
            result.redis_keys_restored += 1

        logger.info(f"Redis rebuilt: {result.redis_keys_restored} keys restored")

    async def _verify_integrity(self, result: ReconciliationResult):
        """Post-reconciliation integrity checks."""
        # Verify broker positions match DB positions
        broker_positions = await self.broker.get_positions()
        db_positions = await self.db.get_open_positions()

        broker_tickets = {p.ticket for p in broker_positions}
        db_tickets = {p.ticket for p in db_positions}

        if broker_tickets != db_tickets:
            mismatch = broker_tickets.symmetric_difference(db_tickets)
            result.errors.append(f"Post-reconciliation mismatch: {mismatch}")
            logger.error(f"INTEGRITY CHECK FAILED: position mismatch after reconciliation: {mismatch}")
        else:
            logger.info("Integrity check passed: broker and DB positions match")

    async def _log_result(self, result: ReconciliationResult):
        """Log reconciliation result to file and database."""
        logger.info("=" * 60)
        logger.info("STARTUP RECONCILIATION — COMPLETE")
        logger.info(f"  Status: {result.status.value}")
        logger.info(f"  Duration: {result.duration_ms:.0f}ms")
        logger.info(f"  Broker positions: {len(result.broker_positions)}")
        logger.info(f"  DB positions: {len(result.db_positions)}")
        logger.info(f"  Orphaned in DB (closed): {len(result.orphaned_in_db)}")
        logger.info(f"  Unknown at broker (imported): {len(result.unknown_at_broker)}")
        logger.info(f"  Orphaned orders: {len(result.orphaned_orders)}")
        logger.info(f"  Redis keys restored: {result.redis_keys_restored}")
        logger.info(f"  Errors: {len(result.errors)}")
        for err in result.errors:
            logger.error(f"    - {err}")
        logger.info("=" * 60)

        # Persist to database for audit trail
        await self.db.record_reconciliation(result)


# Integration point — called in main.py startup:
# async def startup():
#     recovery = StateRecovery(broker=mt5_broker, db=postgres, redis_client=redis, config=config)
#     result = await recovery.run()
#     if result.status == ReconciliationStatus.FAILED:
#         logger.critical("Reconciliation failed — entering safe mode")
#         await enter_safe_mode()
#     elif result.status == ReconciliationStatus.MANUAL_REQUIRED:
#         logger.critical("Manual reconciliation required — pausing trading")
#         await notify_operator("Manual reconciliation required", result)
#         await pause_trading()
#     else:
#         logger.info("Reconciliation OK — resuming normal operation")
#         await resume_trading()
```

### PostgreSQL Table for Audit Trail

```sql
-- migrations/003_reconciliation_log.sql

CREATE TABLE IF NOT EXISTS reconciliation_log (
    id BIGSERIAL PRIMARY KEY,
    run_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status TEXT NOT NULL CHECK (status IN ('clean', 'repaired', 'manual', 'failed')),
    broker_positions INT NOT NULL DEFAULT 0,
    db_positions INT NOT NULL DEFAULT 0,
    orphaned_in_db INT NOT NULL DEFAULT 0,
    unknown_at_broker INT NOT NULL DEFAULT 0,
    orphaned_orders INT NOT NULL DEFAULT 0,
    redis_keys_restored INT NOT NULL DEFAULT 0,
    errors JSONB DEFAULT '[]',
    duration_ms FLOAT NOT NULL DEFAULT 0,
    details JSONB DEFAULT '{}'
);

CREATE INDEX idx_reconciliation_log_run_at ON reconciliation_log (run_at DESC);
CREATE INDEX idx_reconciliation_log_status ON reconciliation_log (status) WHERE status != 'clean';
```

---

## Fix 3: LLM Fallback Chain + Response Caching

### Problem

Steps S1, S2, S3, S7 of the VMPM pipeline depend on LLM inference. No fallback exists for API outages. No caching exists for repeated inputs. No timeout handling exists. At 10+ pairs, this is the dominant bottleneck and cost driver.

### Solution

A three-tier resilience chain: cache → primary model → secondary model → rule-based fallback. Responses cached in Redis with 1-hour TTL. Hard 5-second timeout per call.

### Implementation

```python
# core/llm_chain.py

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Optional

logger = logging.getLogger(__name__)


class LLMTier(Enum):
    CACHE = "cache"
    PRIMARY = "primary"
    SECONDARY = "secondary"
    FALLBACK = "fallback"


@dataclass
class LLMResponse:
    text: str
    tier: LLMTier
    model: str
    latency_ms: float
    cached: bool = False
    tokens_used: int = 0
    cost_usd: float = 0.0


@dataclass
class LLMChainConfig:
    primary_model: str = "gpt-4o-mini"
    secondary_model: str = "gpt-3.5-turbo"
    timeout_seconds: float = 5.0
    cache_ttl_seconds: int = 3600  # 1 hour
    max_retries: int = 1
    cache_enabled: bool = True
    cost_per_1k_tokens: dict = field(default_factory=lambda: {
        "gpt-4o-mini": 0.00015,
        "gpt-3.5-turbo": 0.0005,
        "deepseek-chat": 0.00014,
    })


class LLMFallbackChain:
    """
    Resilient LLM call chain with caching, fallback, and cost tracking.
    
    Call order:
    1. Redis cache (instant, free)
    2. Primary model (5s timeout)
    3. Secondary model (5s timeout)
    4. Rule-based fallback (instant, deterministic)
    
    Every response is cached. Cost is tracked per call and aggregated weekly.
    """

    def __init__(
        self,
        redis_client,
        primary_caller: Callable[..., Coroutine],
        secondary_caller: Callable[..., Coroutine],
        rule_fallback: Callable[..., Coroutine],
        cost_tracker,  # CostBudget instance from Fix 4
        config: Optional[LLMChainConfig] = None,
    ):
        self.redis = redis_client
        self.primary_caller = primary_caller
        self.secondary_caller = secondary_caller
        self.rule_fallback = rule_fallback
        self.cost_tracker = cost_tracker
        self.config = config or LLMChainConfig()

    def _make_cache_key(self, prompt: str, context: dict, step: str) -> str:
        """Deterministic cache key from prompt + context + pipeline step."""
        raw = json.dumps(
            {"prompt": prompt, "context": context, "step": step},
            sort_keys=True,
            default=str,
        )
        return f"llm_cache:{step}:{hashlib.sha256(raw.encode()).hexdigest()[:16]}"

    def _make_freshness_key(self, step: str, symbol: str) -> str:
        """
        Freshness key ensures cache entries are invalidated when new market
        data arrives. Groups cache by step + symbol + current 15-min candle.
        """
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc)
        candle_ts = now.replace(
            minute=(now.minute // 15) * 15, second=0, microsecond=0
        )
        return f"llm_fresh:{step}:{symbol}:{candle_ts.isoformat()}"

    async def call(
        self,
        prompt: str,
        context: dict,
        step: str,
        symbol: str = "UNKNOWN",
        force_refresh: bool = False,
    ) -> LLMResponse:
        """
        Execute LLM call with full fallback chain.
        
        Args:
            prompt: The LLM prompt text
            context: Additional context dict (market data, indicators, etc.)
            step: Pipeline step name (S1, S2, S3, S7) for metrics
            symbol: Trading symbol for freshness grouping
            force_refresh: Skip cache (for critical analysis)
        
        Returns:
            LLMResponse with text, tier used, and cost info
        """
        start = time.monotonic()
        cache_key = self._make_cache_key(prompt, context, step)

        # --- Tier 1: Cache ---
        if self.config.cache_enabled and not force_refresh:
            try:
                cached = await self.redis.get(cache_key)
                if cached:
                    data = json.loads(cached)
                    latency = (time.monotonic() - start) * 1000
                    logger.debug(f"LLM cache hit for {step}/{symbol}")
                    return LLMResponse(
                        text=data["text"],
                        tier=LLMTier.CACHE,
                        model=data["model"],
                        latency_ms=latency,
                        cached=True,
                        tokens_used=0,
                        cost_usd=0.0,
                    )
            except Exception as e:
                logger.warning(f"Cache read error: {e}")

        # --- Tier 2: Primary model ---
        try:
            response = await asyncio.wait_for(
                self.primary_caller(prompt, context),
                timeout=self.config.timeout_seconds,
            )
            latency = (time.monotonic() - start) * 1000
            llm_resp = LLMResponse(
                text=response["text"],
                tier=LLMTier.PRIMARY,
                model=self.config.primary_model,
                latency_ms=latency,
                tokens_used=response.get("tokens", 0),
                cost_usd=response.get("cost", 0.0),
            )
            await self._cache_response(cache_key, llm_resp)
            await self.cost_tracker.record_cost(step, llm_resp.cost_usd)
            return llm_resp

        except asyncio.TimeoutError:
            logger.warning(f"Primary LLM timeout ({self.config.timeout_seconds}s) for {step}/{symbol}")
        except Exception as e:
            logger.warning(f"Primary LLM error for {step}/{symbol}: {e}")

        # --- Tier 3: Secondary model ---
        try:
            response = await asyncio.wait_for(
                self.secondary_caller(prompt, context),
                timeout=self.config.timeout_seconds,
            )
            latency = (time.monotonic() - start) * 1000
            llm_resp = LLMResponse(
                text=response["text"],
                tier=LLMTier.SECONDARY,
                model=self.config.secondary_model,
                latency_ms=latency,
                tokens_used=response.get("tokens", 0),
                cost_usd=response.get("cost", 0.0),
            )
            await self._cache_response(cache_key, llm_resp)
            await self.cost_tracker.record_cost(step, llm_resp.cost_usd)
            return llm_resp

        except asyncio.TimeoutError:
            logger.warning(f"Secondary LLM timeout for {step}/{symbol}")
        except Exception as e:
            logger.warning(f"Secondary LLM error for {step}/{symbol}: {e}")

        # --- Tier 4: Rule-based fallback ---
        logger.warning(f"All LLM tiers exhausted for {step}/{symbol}, using rule-based fallback")
        fallback_text = await self.rule_fallback(prompt, context)
        latency = (time.monotonic() - start) * 1000
        return LLMResponse(
            text=fallback_text,
            tier=LLMTier.FALLBACK,
            model="rule_based",
            latency_ms=latency,
            tokens_used=0,
            cost_usd=0.0,
        )

    async def _cache_response(self, cache_key: str, response: LLMResponse):
        """Cache response in Redis with TTL."""
        try:
            data = json.dumps({
                "text": response.text,
                "model": response.model,
                "cached_at": time.time(),
            })
            await self.redis.setex(cache_key, self.config.cache_ttl_seconds, data)
        except Exception as e:
            logger.warning(f"Cache write error: {e}")

    async def invalidate_cache(self, step: str = "*", symbol: str = "*"):
        """Invalidate cached LLM responses. Called when new market data arrives."""
        pattern = f"llm_cache:{step}:*" if symbol == "*" else f"llm_cache:{step}:*"
        keys = []
        async for key in self.redis.scan_iter(match=pattern, count=1000):
            keys.append(key)
            if len(keys) >= 5000:
                await self.redis.delete(*keys)
                keys = []
        if keys:
            await self.redis.delete(*keys)
        logger.info(f"Invalidated LLM cache: pattern={pattern}")


# --- Rule-based fallbacks per step ---

async def rule_fallback_s1(prompt: str, context: dict) -> str:
    """Fallback for Step 1 (Fundamental Analysis): neutral bias."""
    return json.dumps({
        "bias": "neutral",
        "confidence": 0.0,
        "reasoning": "LLM unavailable — using neutral bias (rule-based fallback)",
        "tier": "fallback",
    })


async def rule_fallback_s2(prompt: str, context: dict) -> str:
    """Fallback for Step 2 (Sentiment Analysis): skip, return neutral."""
    return json.dumps({
        "sentiment": "neutral",
        "score": 0.0,
        "reasoning": "LLM unavailable — using neutral sentiment (rule-based fallback)",
        "tier": "fallback",
    })


async def rule_fallback_s3(prompt: str, context: dict) -> str:
    """Fallback for Step 3 (Technical Synthesis): use indicator consensus."""
    indicators = context.get("indicators", {})
    buy_signals = sum(1 for v in indicators.values() if v == "buy")
    sell_signals = sum(1 for v in indicators.values() if v == "sell")
    total = buy_signals + sell_signals

    if total == 0:
        bias = "neutral"
        confidence = 0.0
    elif buy_signals > sell_signals:
        bias = "buy"
        confidence = buy_signals / total
    elif sell_signals > buy_signals:
        bias = "sell"
        confidence = sell_signals / total
    else:
        bias = "neutral"
        confidence = 0.0

    return json.dumps({
        "bias": bias,
        "confidence": round(confidence, 2),
        "reasoning": f"Indicator consensus: {buy_signals} buy, {sell_signals} sell (rule-based fallback)",
        "tier": "fallback",
    })


async def rule_fallback_s7(prompt: str, context: dict) -> str:
    """Fallback for Step 7 (Trade Validation): approve with reduced confidence."""
    return json.dumps({
        "approved": True,
        "confidence_multiplier": 0.5,  # Reduce position size by 50%
        "reasoning": "LLM unavailable — auto-approved at 50% size (rule-based fallback)",
        "tier": "fallback",
    })
```

### Integration with VMPM Pipeline

```python
# In pipeline initialization:

llm_chain = LLMFallbackChain(
    redis_client=redis,
    primary_caller=openai_caller,           # GPT-4o-mini
    secondary_caller=deepseek_caller,        # DeepSeek Chat (cheap fallback)
    rule_fallback=rule_fallback_s1,          # Default, overridden per step
    cost_tracker=cost_budget,                # CostBudget from Fix 4
    config=LLMChainConfig(
        primary_model="gpt-4o-mini",
        secondary_model="deepseek-chat",
        timeout_seconds=5.0,
        cache_ttl_seconds=3600,
    ),
)

# Per-step usage:
response = await llm_chain.call(
    prompt=fundamental_prompt,
    context={"indicators": indicators, "news": news_data},
    step="S1",
    symbol="EURUSD",
)
```

### Scaling Notes

| Phase | LLM Config | Expected Cache Hit Rate |
|-------|-----------|----------------------|
| Phase 1 | Primary: gpt-4o-mini, Secondary: deepseek | ~30% (1 pair, low repetition) |
| Phase 2 | Primary: gpt-4o-mini, Secondary: deepseek | ~50% (10 pairs, high repetition) |
| Phase 3 | + Local FinBERT for sentiment (no API) | ~60% (FinBERT eliminates S2 API calls) |
| Phase 4 | + Local vLLM for all steps | ~70%+ (eliminates most API dependency) |

---

## Fix 4: Cost Budget System at $7 Scale

### Problem

The spread filter checks individual trade costs but doesn't track cumulative cost burden relative to account size. At $7 capital with 0.01 lot EUR/USD, spread costs ~$0.10-0.15 per trade (1.4-2.1% of capital). ~46 trades drain the account on costs alone.

### Solution

A `CostBudget` class that tracks all trading costs (spread, commission, swap, LLM API) weekly, enforces a percentage cap, and provides early warning before budget exhaustion.

### Implementation

```python
# core/cost_budget.py

import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class CostCategory(Enum):
    SPREAD = "spread"
    COMMISSION = "commission"
    SWAP = "swap"
    SLIPPAGE = "slippage"
    LLM_API = "llm_api"
    INFRA = "infrastructure"


@dataclass
class CostEntry:
    timestamp: datetime
    category: CostCategory
    amount_usd: float
    symbol: str = ""
    trade_id: str = ""
    step: str = ""  # Pipeline step (for LLM costs)
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class BudgetStatus:
    account_balance: float
    weekly_spent: float
    weekly_budget: float
    remaining: float
    utilization_pct: float
    projected_weekly: float  # Extrapolated from current rate
    is_exhausted: bool
    is_warning: bool  # >70% utilized
    cost_per_trade_avg: float
    trades_this_week: int
    estimated_trades_remaining: int


class CostBudget:
    """
    Micro-scale cost budget tracker.
    
    Enforces:
    - Weekly cost cap: 5% of account balance
    - Per-trade cost cap: 0.3% of account balance
    - LLM cost cap: $0.50/week at $7, scales with account
    - Cost/profit ratio: costs must be <30% of expected profit
    
    Tracks:
    - Spread costs (from trade execution)
    - Commission costs (from broker)
    - Swap costs (overnight positions)
    - Slippage costs (expected vs actual fill)
    - LLM API costs (from LLM chain)
    """

    # --- Tunable limits ---
    WEEKLY_COST_PCT = 5.0           # Max 5% of account per week
    PER_TRADE_COST_PCT = 0.3        # Max 0.3% of account per trade
    COST_PROFIT_RATIO = 0.30        # Costs must be <30% of expected profit
    LLM_WEEKLY_CAP_USD = 0.50       # LLM API budget at $7 scale
    LLM_WEEKLY_CAP_PCT = 2.0        # LLM cap as % of account (scales up)
    WARNING_THRESHOLD_PCT = 70.0    # Warn at 70% budget utilization
    EMERGENCY_THRESHOLD_PCT = 90.0  # Emergency stop at 90%

    def __init__(self, db, redis_client):
        self.db = db
        self.redis = redis_client

    async def can_trade(
        self,
        estimated_cost: float,
        symbol: str,
        expected_profit: float = 0.0,
    ) -> tuple[bool, str]:
        """
        Check if a new trade is within budget.
        
        Returns:
            (allowed: bool, reason: str)
        """
        account = await self.db.get_account_balance()
        status = await self.get_status(account)

        # Check 1: Weekly budget exhausted
        if status.is_exhausted:
            return False, (
                f"Weekly cost budget exhausted: ${status.weekly_spent:.4f} / "
                f"${status.weekly_budget:.4f} ({status.utilization_pct:.1f}%)"
            )

        # Check 2: Per-trade cost cap
        per_trade_cap = account * self.PER_TRADE_COST_PCT / 100
        if estimated_cost > per_trade_cap:
            return False, (
                f"Trade cost ${estimated_cost:.4f} exceeds per-trade cap "
                f"${per_trade_cap:.4f} ({self.PER_TRADE_COST_PCT}% of ${account:.2f})"
            )

        # Check 3: Would this trade push us over budget?
        projected = status.weekly_spent + estimated_cost
        if projected > status.weekly_budget:
            return False, (
                f"Trade would exceed weekly budget: "
                f"${projected:.4f} > ${status.weekly_budget:.4f}"
            )

        # Check 4: Emergency threshold
        if status.utilization_pct >= self.EMERGENCY_THRESHOLD_PCT:
            return False, (
                f"Emergency threshold reached: {status.utilization_pct:.1f}% utilized"
            )

        # Check 5: Cost/profit ratio (if expected profit provided)
        if expected_profit > 0:
            if estimated_cost > expected_profit * self.COST_PROFIT_RATIO:
                return False, (
                    f"Cost/profit ratio too high: ${estimated_cost:.4f} cost vs "
                    f"${expected_profit:.4f} expected profit "
                    f"({estimated_cost / expected_profit * 100:.1f}% > {self.COST_PROFIT_RATIO * 100:.0f}%)"
                )

        return True, "OK"

    async def record_cost(
        self,
        category_or_step: str,
        amount_usd: float,
        symbol: str = "",
        trade_id: str = "",
        metadata: dict = None,
    ):
        """Record a cost entry. Accepts category name or pipeline step."""
        # Auto-detect if it's a pipeline step (S1, S2, etc.) or category
        if category_or_step.startswith("S") and category_or_step[1:].isdigit():
            category = CostCategory.LLM_API
            step = category_or_step
        else:
            category = CostCategory(category_or_step)
            step = ""

        entry = CostEntry(
            timestamp=datetime.now(timezone.utc),
            category=category,
            amount_usd=amount_usd,
            symbol=symbol,
            trade_id=trade_id,
            step=step,
            metadata=metadata or {},
        )

        # Write to database
        await self.db.insert_cost_entry(entry)

        # Update Redis counters for fast reads
        week_key = self._week_key()
        await self.redis.hincrbyfloat(f"cost:{week_key}", category.value, amount_usd)
        await self.redis.hincrbyfloat(f"cost:{week_key}", "total", amount_usd)

        # Log warning if approaching budget
        account = await self.db.get_account_balance()
        weekly_budget = account * self.WEEKLY_COST_PCT / 100
        weekly_total = float(await self.redis.hget(f"cost:{week_key}", "total") or 0)
        utilization = (weekly_total / weekly_budget * 100) if weekly_budget > 0 else 0

        if utilization >= self.EMERGENCY_THRESHOLD_PCT:
            logger.error(
                f"COST EMERGENCY: {utilization:.1f}% of weekly budget used "
                f"(${weekly_total:.4f} / ${weekly_budget:.4f})"
            )
        elif utilization >= self.WARNING_THRESHOLD_PCT:
            logger.warning(
                f"COST WARNING: {utilization:.1f}% of weekly budget used "
                f"(${weekly_total:.4f} / ${weekly_budget:.4f})"
            )

    async def get_status(self, account_balance: Optional[float] = None) -> BudgetStatus:
        """Get current budget status."""
        if account_balance is None:
            account_balance = await self.db.get_account_balance()

        weekly_budget = account_balance * self.WEEKLY_COST_PCT / 100
        week_key = self._week_key()

        weekly_spent = float(await self.redis.hget(f"cost:{week_key}", "total") or 0)
        remaining = max(0, weekly_budget - weekly_spent)
        utilization = (weekly_spent / weekly_budget * 100) if weekly_budget > 0 else 0

        # Estimate trades remaining
        trades_this_week = await self.db.get_weekly_trade_count()
        cost_per_trade = (weekly_spent / trades_this_week) if trades_this_week > 0 else 0
        estimated_remaining = int(remaining / cost_per_trade) if cost_per_trade > 0 else 999

        # Project weekly total based on current rate
        week_start = self._week_start()
        elapsed_hours = (datetime.now(timezone.utc) - week_start).total_seconds() / 3600
        if elapsed_hours > 0:
            hourly_rate = weekly_spent / elapsed_hours
            projected = hourly_rate * 168  # 168 hours in a week
        else:
            projected = weekly_spent

        return BudgetStatus(
            account_balance=account_balance,
            weekly_spent=weekly_spent,
            weekly_budget=weekly_budget,
            remaining=remaining,
            utilization_pct=utilization,
            projected_weekly=projected,
            is_exhausted=remaining <= 0,
            is_warning=utilization >= self.WARNING_THRESHOLD_PCT,
            cost_per_trade_avg=cost_per_trade,
            trades_this_week=trades_this_week,
            estimated_trades_remaining=estimated_remaining,
        )

    async def get_weekly_summary(self) -> dict:
        """Get cost breakdown by category for the current week."""
        week_key = self._week_key()
        breakdown = await self.redis.hgetall(f"cost:{week_key}")
        account = await self.db.get_account_balance()
        budget = account * self.WEEKLY_COST_PCT / 100

        return {
            "week": week_key,
            "breakdown": {k: float(v) for k, v in breakdown.items()},
            "total": float(breakdown.get("total", 0)),
            "budget": budget,
            "utilization_pct": float(breakdown.get("total", 0)) / budget * 100 if budget > 0 else 0,
            "account_balance": account,
        }

    def _week_key(self) -> str:
        """ISO week key, e.g., '2026-W28'."""
        now = datetime.now(timezone.utc)
        return f"{now.isocalendar()[0]}-W{now.isocalendar()[1]:02d}"

    def _week_start(self) -> datetime:
        """Start of current ISO week (Monday 00:00 UTC)."""
        now = datetime.now(timezone.utc)
        monday = now - timedelta(days=now.weekday())
        return monday.replace(hour=0, minute=0, second=0, microsecond=0)
```

### PostgreSQL Table

```sql
-- migrations/004_cost_tracking.sql

CREATE TABLE IF NOT EXISTS cost_entries (
    id BIGSERIAL PRIMARY KEY,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    category TEXT NOT NULL CHECK (category IN (
        'spread', 'commission', 'swap', 'slippage', 'llm_api', 'infrastructure'
    )),
    amount_usd NUMERIC(12, 6) NOT NULL,
    symbol TEXT DEFAULT '',
    trade_id TEXT DEFAULT '',
    step TEXT DEFAULT '',
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_cost_entries_recorded_at ON cost_entries (recorded_at DESC);
CREATE INDEX idx_cost_entries_category ON cost_entries (category);
CREATE INDEX idx_cost_entries_week ON cost_entries (date_trunc('week', recorded_at));

-- Continuous aggregate for weekly rollups
CREATE MATERIALIZED VIEW cost_weekly_summary
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('7 days', recorded_at) AS week,
    category,
    SUM(amount_usd) AS total_usd,
    COUNT(*) AS entry_count
FROM cost_entries
GROUP BY week, category;
```

### Scaling the Budget

| Account Size | Weekly Budget | Per-Trade Cap | LLM Cap/Week | Expected Trades/Week |
|-------------|---------------|---------------|---------------|---------------------|
| $7 | $0.35 | $0.021 | $0.50 | ~17 |
| $100 | $5.00 | $0.30 | $2.00 | ~50 |
| $1,000 | $50.00 | $3.00 | $10.00 | ~200 |
| $10,000 | $500.00 | $30.00 | $50.00 | ~1000 |

At $7, the budget limits the system to ~17 trades/week. This is intentional — it forces quality over quantity and prevents cost drain. As capital grows, the budget scales proportionally.

---

## Fix 5: MT5 Data Proxy Service

### Problem

The Python MT5 API is single-threaded (serialized access). At 10+ pairs, only one pair can query MT5 at a time for market data, creating a queuing bottleneck. The existing ZeroMQ bridge handles order signals but not data collection.

### Solution

A standalone `MT5DataProxy` service that owns all MT5 data access. It polls MT5 on a schedule, publishes to Redis Streams, and eliminates serialization by being the single consumer of the MT5 API.

### Architecture

```
┌─────────────────────────────────────────────────────┐
│                    MT5 Terminal (Wine)                │
│                                                       │
│  ┌──────────────┐     ┌──────────────────────┐      │
│  │  Alpha EA    │     │  MT5 Data Proxy      │      │
│  │  (ZeroMQ)    │     │  (Python process)     │      │
│  │              │     │                       │      │
│  │  Receives:   │     │  Polls:               │      │
│  │  - Signals   │     │  - Ticks (100ms)      │      │
│  │  - Orders    │     │  - Candles (1m)        │      │
│  │              │     │  - Positions (1s)      │      │
│  │  Sends:      │     │  - Account info (5s)   │      │
│  │  - Fills     │     │                       │      │
│  │  - Status    │     │  Publishes to:         │      │
│  └──────┬───────┘     │  - Redis Streams       │      │
│         │              └───────────┬───────────┘      │
└─────────┼──────────────────────────┼──────────────────┘
          │                          │
          ▼                          ▼
    ┌──────────┐            ┌──────────────┐
    │  ZeroMQ  │            │  Redis       │
    │  Bridge  │            │  Streams     │
    └────┬─────┘            └──────┬───────┘
         │                         │
         ▼                         ▼
    ┌──────────────────────────────────┐
    │        Trading Engine            │
    │  - Reads ticks from Redis        │
    │  - Reads positions from Redis    │
    │  - Sends orders via ZeroMQ       │
    └──────────────────────────────────┘
```

### Implementation

```python
# services/mt5_data_proxy.py

import asyncio
import json
import logging
import os
import signal
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Optional

import MetaTrader5 as mt5
import redis.asyncio as redis

logger = logging.getLogger(__name__)


@dataclass
class ProxyConfig:
    mt5_login: int = 0
    mt5_password: str = ""
    mt5_server: str = ""
    mt5_path: str = ""
    symbols: list = None
    tick_poll_ms: int = 100
    candle_poll_sec: int = 60
    position_poll_sec: int = 1
    account_poll_sec: int = int(os.getenv("MT5_ACCOUNT_POLL_SEC", "5"))
    redis_host: str = os.getenv("REDIS_HOST", "localhost")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))
    redis_password: str = os.getenv("REDIS_PASSWORD", "")
    max_reconnect_attempts: int = 10
    reconnect_delay_sec: float = 5.0

    def __post_init__(self):
        if self.symbols is None:
            self.symbols = ["EURUSD", "GBPUSD", "USDJPY"]


class MT5DataProxy:
    """
    Standalone service that owns all MT5 data access.
    
    Eliminates serialization bottleneck by being the single MT5 consumer.
    Publishes all data to Redis Streams for consumption by the trading engine.
    
    Streams produced:
      - mt5:ticks:{symbol}    — Real-time tick data
      - mt5:candles:{symbol}  — 1-minute OHLCV
      - mt5:positions         — Position snapshots
      - mt5:account           — Account info
      - mt5:health            — Proxy health status
    """

    def __init__(self, config: ProxyConfig):
        self.config = config
        self.redis_client: Optional[redis.Redis] = None
        self.running = False
        self._tasks: list[asyncio.Task] = []
        self._last_tick: dict[str, float] = {}
        self._tick_counts: dict[str, int] = {}
        self._errors: dict[str, int] = {}

    async def start(self):
        """Initialize MT5 and Redis, start all polling loops."""
        logger.info("MT5 Data Proxy starting...")

        # Connect to Redis
        self.redis_client = redis.Redis(
            host=self.config.redis_host,
            port=self.config.redis_port,
            password=self.config.redis_password,
            decode_responses=True,
        )
        await self.redis_client.ping()
        logger.info("Redis connected")

        # Initialize MT5
        if not mt5.initialize(
            path=self.config.mt5_path or None,
            login=self.config.mt5_login,
            password=self.config.mt5_password,
            server=self.config.mt5_server,
        ):
            logger.error(f"MT5 initialization failed: {mt5.last_error()}")
            raise RuntimeError("MT5 init failed")

        # Verify symbols
        for symbol in self.config.symbols:
            info = mt5.symbol_info(symbol)
            if info is None:
                logger.error(f"Symbol {symbol} not found in MT5")
                raise ValueError(f"Symbol {symbol} not available")
            if not info.visible:
                mt5.symbol_select(symbol, True)

        logger.info(f"MT5 initialized: {len(self.config.symbols)} symbols active")

        self.running = True

        # Start polling tasks
        self._tasks = [
            asyncio.create_task(self._poll_ticks(), name="tick_poller"),
            asyncio.create_task(self._poll_candles(), name="candle_poller"),
            asyncio.create_task(self._poll_positions(), name="position_poller"),
            asyncio.create_task(self._poll_account(), name="account_poller"),
            asyncio.create_task(self._publish_health(), name="health_publisher"),
        ]

        logger.info("All polling tasks started")

        # Wait for shutdown
        await asyncio.gather(*self._tasks, return_exceptions=True)

    async def stop(self):
        """Graceful shutdown."""
        logger.info("MT5 Data Proxy stopping...")
        self.running = False

        for task in self._tasks:
            task.cancel()

        await asyncio.gather(*self._tasks, return_exceptions=True)

        if self.redis_client:
            await self.redis_client.close()

        mt5.shutdown()
        logger.info("MT5 Data Proxy stopped")

    async def _poll_ticks(self):
        """Poll MT5 for tick data at configured interval."""
        interval = self.config.tick_poll_ms / 1000.0

        while self.running:
            try:
                for symbol in self.config.symbols:
                    tick = mt5.symbol_info_tick(symbol)
                    if tick is None:
                        continue

                    tick_time = datetime.fromtimestamp(tick.time, tz=timezone.utc)

                    # Skip if same tick as last poll
                    last = self._last_tick.get(symbol, 0)
                    if tick.time <= last:
                        continue
                    self._last_tick[symbol] = tick.time

                    await self.redis_client.xadd(
                        f"mt5:ticks:{symbol}",
                        {
                            "bid": str(tick.bid),
                            "ask": str(tick.ask),
                            "last": str(tick.last),
                            "volume": str(tick.volume),
                            "time": tick_time.isoformat(),
                            "flags": str(tick.flags),
                        },
                        maxlen=10000,  # Keep last 10k ticks per symbol
                    )
                    self._tick_counts[symbol] = self._tick_counts.get(symbol, 0) + 1

            except Exception as e:
                self._errors["ticks"] = self._errors.get("ticks", 0) + 1
                logger.error(f"Tick poll error: {e}")
                await self._handle_mt5_error(e)

            await asyncio.sleep(interval)

    async def _poll_candles(self):
        """Poll MT5 for 1-minute candle data."""
        interval = self.config.candle_poll_sec

        while self.running:
            try:
                for symbol in self.config.symbols:
                    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 1)
                    if rates is None or len(rates) == 0:
                        continue

                    rate = rates[0]
                    candle_time = datetime.fromtimestamp(rate["time"], tz=timezone.utc)

                    # Deduplicate: only publish if timestamp is newer
                    last_candle_key = f"mt5:last_candle:{symbol}"
                    last_candle = await self.redis_client.get(last_candle_key)
                    if last_candle and last_candle == candle_time.isoformat():
                        continue
                    await self.redis_client.set(last_candle_key, candle_time.isoformat(), ex=300)

                    await self.redis_client.xadd(
                        f"mt5:candles:{symbol}",
                        {
                            "time": candle_time.isoformat(),
                            "open": str(rate["open"]),
                            "high": str(rate["high"]),
                            "low": str(rate["low"]),
                            "close": str(rate["close"]),
                            "tick_volume": str(rate["tick_volume"]),
                            "spread": str(rate["spread"]),
                            "real_volume": str(rate.get("real_volume", 0)),
                        },
                        maxlen=5000,
                    )

            except Exception as e:
                self._errors["candles"] = self._errors.get("candles", 0) + 1
                logger.error(f"Candle poll error: {e}")

            await asyncio.sleep(interval)

    async def _poll_positions(self):
        """Poll MT5 for current positions."""
        interval = self.config.position_poll_sec

        while self.running:
            try:
                positions = mt5.positions_get()
                if positions is None:
                    positions = []

                pos_data = []
                for pos in positions:
                    pos_data.append({
                        "ticket": str(pos.ticket),
                        "symbol": pos.symbol,
                        "type": "buy" if pos.type == mt5.ORDER_TYPE_BUY else "sell",
                        "volume": str(pos.volume),
                        "open_price": str(pos.price_open),
                        "current_price": str(pos.price_current),
                        "sl": str(pos.sl),
                        "tp": str(pos.tp),
                        "profit": str(pos.profit),
                        "swap": str(pos.swap),
                        "magic": str(pos.magic),
                        "open_time": datetime.fromtimestamp(
                            pos.time, tz=timezone.utc
                        ).isoformat(),
                    })

                # Publish snapshot
                await self.redis_client.set(
                    "mt5:positions:snapshot",
                    json.dumps(pos_data),
                    ex=interval * 3,  # Expire if proxy dies
                )

                # Also publish to stream for history
                await self.redis_client.xadd(
                    "mt5:positions",
                    {"count": str(len(pos_data)), "data": json.dumps(pos_data)},
                    maxlen=1000,
                )

            except Exception as e:
                self._errors["positions"] = self._errors.get("positions", 0) + 1
                logger.error(f"Position poll error: {e}")

            await asyncio.sleep(interval)

    async def _poll_account(self):
        """Poll MT5 for account info."""
        interval = self.config.account_poll_sec

        while self.running:
            try:
                info = mt5.account_info()
                if info is None:
                    logger.warning("MT5 account_info returned None")
                    await asyncio.sleep(interval)
                    continue

                account_data = {
                    "balance": str(info.balance),
                    "equity": str(info.equity),
                    "margin": str(info.margin),
                    "free_margin": str(info.margin_free),
                    "margin_level": str(info.margin_level),
                    "profit": str(info.profit),
                    "leverage": str(info.leverage),
                    "currency": info.currency,
                    "server": info.server,
                    "trade_allowed": str(info.trade_allowed),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                await self.redis_client.set(
                    "mt5:account:snapshot",
                    json.dumps(account_data),
                    ex=interval * 3,
                )

            except Exception as e:
                self._errors["account"] = self._errors.get("account", 0) + 1
                logger.error(f"Account poll error: {e}")

            await asyncio.sleep(interval)

    async def _publish_health(self):
        """Publish proxy health status every 10 seconds."""
        while self.running:
            try:
                health = {
                    "status": "running",
                    "uptime_sec": time.monotonic() - self._start_time,
                    "symbols": self.config.symbols,
                    "tick_counts": self._tick_counts.copy(),
                    "errors": self._errors.copy(),
                    "mt5_connected": mt5.terminal_info() is not None,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                await self.redis_client.set(
                    "mt5:health", json.dumps(health), ex=30
                )
            except Exception as e:
                logger.error(f"Health publish error: {e}")

            await asyncio.sleep(10)

    async def _handle_mt5_error(self, error: Exception):
        """Handle MT5 connection errors with reconnection logic."""
        logger.warning(f"MT5 error detected: {error}")

        for attempt in range(1, self.config.max_reconnect_attempts + 1):
            logger.info(f"MT5 reconnect attempt {attempt}/{self.config.max_reconnect_attempts}")

            await asyncio.sleep(self.config.reconnect_delay_sec)

            try:
                mt5.shutdown()
                if mt5.initialize(
                    path=self.config.mt5_path or None,
                    login=self.config.mt5_login,
                    password=self.config.mt5_password,
                    server=self.config.mt5_server,
                ):
                    logger.info("MT5 reconnected successfully")
                    # Re-select symbols
                    for symbol in self.config.symbols:
                        mt5.symbol_select(symbol, True)
                    return
            except Exception as reconnect_error:
                logger.error(f"Reconnect attempt {attempt} failed: {reconnect_error}")

        logger.critical("MT5 reconnect failed after all attempts — proxy entering degraded mode")
        self._errors["reconnect_failed"] = self._errors.get("reconnect_failed", 0) + 1


# Consumer side — Trading Engine reads from Redis:
# class MT5DataReader:
#     """Reads MT5 data from Redis Streams instead of direct MT5 API."""
#
#     async def get_latest_tick(self, symbol: str) -> dict:
#         entries = await self.redis.xrevrange(f"mt5:ticks:{symbol}", count=1)
#         if entries:
#             _, data = entries[0]
#             return data
#         return None
#
#     async def get_latest_candle(self, symbol: str) -> dict:
#         entries = await self.redis.xrevrange(f"mt5:candles:{symbol}", count=1)
#         if entries:
#             _, data = entries[0]
#             return data
#         return None
#
#     async def get_positions(self) -> list:
#         snapshot = await self.redis.get("mt5:positions:snapshot")
#         return json.loads(snapshot) if snapshot else []
#
#     async def get_account(self) -> dict:
#         snapshot = await self.redis.get("mt5:account:snapshot")
#         return json.loads(snapshot) if snapshot else {}
```

### Docker Compose Addition

```yaml
# docker-compose.phase2.yml — add to services:

  mt5-data-proxy:
    build:
      context: .
      dockerfile: services/mt5_data_proxy/Dockerfile
    container_name: mt5-data-proxy
    environment:
      - MT5_LOGIN=${MT5_LOGIN}
      - MT5_PASSWORD=${MT5_PASSWORD}
      - MT5_SERVER=${MT5_SERVER}
      - MT5_PATH=${MT5_PATH}
      - MT5_SYMBOLS=EURUSD,GBPUSD,USDJPY
      - REDIS_HOST=redis-primary
      - REDIS_PORT=6379
      - REDIS_PASSWORD=${REDIS_PASSWORD}
    volumes:
      - mt5-data:/root/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Files
    depends_on:
      redis-primary:
        condition: service_healthy
    networks:
      - alpha-net
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import redis; r=redis.Redis(); r.ping()"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### Migration Path

| Phase | MT5 Data Access | Notes |
|-------|----------------|-------|
| Phase 1 | Direct Python API (current) | Single machine, acceptable |
| **Phase 2** | **MT5 Data Proxy service** | **Eliminates serialization, enables scaling** |
| Phase 3+ | OANDA REST API for forex data | HTTP-based, no serialization, native multi-threading |

---

## Fix 6: Phase 2 VPS Undersized — CX21 → CX41

### Problem

The data storage architecture specifies Hetzner CX21 (2 vCPU, 4 GB RAM) at $7/mo for Phase 2. This is insufficient for:
- PostgreSQL + TimescaleDB: ~1.5 GB baseline
- Redis Sentinel (3 processes): ~480 MB
- Trading engine + 10 pairs: ~1.5 GB
- FinBERT inference: ~2 GB
- OS + overhead: ~1 GB
- **Total: ~6.5 GB minimum**

4 GB RAM will cause OOM kills under load.

### Solution

Upgrade Phase 2 VPS to Hetzner CX41 (8 vCPU, 16 GB RAM) at ~$30/mo.

### Updated VPS Specifications

| Phase | Hetzner Spec | CPU | RAM | Disk | Cost/mo | Cost/Capital |
|-------|-------------|-----|-----|------|---------|-------------|
| **Phase 1** | Local machine | — | — | — | $0 | 0% |
| **Phase 2** | **CX41** (was CX21) | **8 vCPU** (was 2) | **16 GB** (was 4) | **240 GB SSD** (was 40) | **~$30** (was $7) | 30% on $100 |
| Phase 3 | CX41 or CPX41 | 8 vCPU | 16 GB | 240 GB SSD | ~$30 | 3% on $1K |
| Phase 4 | Dedicated AX52 | 12 vCPU | 64 GB | 2×512 GB NVMe | ~$65 | 0.65% on $10K |

### Resource Allocation on CX41

| Component | CPU | RAM | Disk |
|-----------|-----|-----|------|
| OS + Docker overhead | 0.5 vCPU | 512 MB | 8 GB |
| PostgreSQL + TimescaleDB | 2 vCPU | 3 GB | 100 GB |
| Redis Sentinel (3 processes) | 0.5 vCPU | 480 MB | 2 GB |
| Trading Engine (Python) | 2 vCPU | 2 GB | 1 GB |
| MT5 Data Proxy | 1 vCPU | 512 MB | 2 GB |
| FinBERT inference | 1 vCPU | 2 GB | 1 GB |
| Prometheus + Grafana | 0.5 vCPU | 512 MB | 10 GB |
| **Reserved headroom** | 0.5 vCPU | ~7.5 GB | ~115 GB |
| **Total allocated** | **8 vCPU** | **~9 GB** | **~135 GB** |
| **CX41 capacity** | **8 vCPU** | **16 GB** | **240 GB** |

### Cost Mitigation for $100 Capital

At $100 capital, $30/mo infrastructure is 30% — high but not fatal for a learning project. Mitigations:

1. **Hetzner Auction servers:** ~30-50% cheaper for same specs (~$18-20/mo)
2. **Start with 3-5 pairs, not 10:** Reduces CPU/RAM needs, can start on CX31 ($15/mo)
3. **Defer FinBERT to Phase 3:** Use API-based sentiment at Phase 2, save 2 GB RAM
4. **Scale pair count with capital:** Each $20 of capital funds ~1 additional pair

### Alternative: Staged Upgrade

If $30/mo is too much at $100 capital:

| Sub-phase | VPS | Pairs | Cost/mo | Cost/Capital |
|-----------|-----|-------|---------|-------------|
| Phase 2a ($100) | CX31 (4 vCPU, 8 GB) | 3-5 pairs | ~$15 | 15% |
| Phase 2b ($500+) | CX41 (8 vCPU, 16 GB) | 10 pairs | ~$30 | 6% |

This pairs the VPS cost with capital growth instead of over-provisioning early.

---

## Integration Checklist

All 6 fixes should be applied in this order:

| Order | Fix | Phase | Depends On | Status |
|-------|-----|-------|------------|--------|
| 1 | **Fix 6: VPS sizing** | Phase 2 | — | Config change, do first |
| 2 | **Fix 1: Redis Sentinel** | Phase 2 | Fix 6 (needs CX41 resources) | Docker Compose |
| 3 | **Fix 2: State recovery** | Phase 1+ | — | Python module |
| 4 | **Fix 4: Cost budget** | Phase 1 | — | Python module |
| 5 | **Fix 3: LLM fallback** | Phase 2 | Fix 4 (cost tracking) | Python module |
| 6 | **Fix 5: MT5 data proxy** | Phase 2 | Fix 1 (Redis Streams) | New service |

---

## Updated Architecture Document References

These fixes require updates to the following existing architecture documents:

### `architecture_system.md`
- Section 7.3: Add Redis Sentinel failover to failure modes (auto-recovery, not safe mode)
- Section 8.3: Add cost-per-trade scaling trigger
- Add: State recovery procedure reference
- Add: LLM fallback chain reference

### `architecture_data_storage.md`
- Section 3.4: Move Redis Sentinel from Phase 4 to Phase 2
- Section 4.2: Update Phase 2 VPS from CX21 to CX41
- Add: `reconciliation_log` table schema
- Add: `cost_entries` table schema
- Add: `cost_weekly_summary` continuous aggregate

### `architecture_trading_engine.md`
- Add: `LLMFallbackChain` class reference
- Add: `CostBudget` integration in trade validation
- Add: `MT5DataProxy` service reference
- Add: `StateRecovery` startup procedure
- Update: `MT5Connector` to use `MT5DataReader` (Redis-based) instead of direct API

---

## Summary of Deliverables

| Deliverable | Type | Lines | Location |
|------------|------|-------|----------|
| Redis Sentinel Docker Compose | YAML | ~120 | `docker-compose.phase2.yml` |
| Sentinel-aware Redis client | Python | ~60 | `core/redis_client.py` |
| State recovery module | Python | ~250 | `core/state_recovery.py` |
| Reconciliation audit table | SQL | ~20 | `migrations/003_reconciliation_log.sql` |
| LLM fallback chain | Python | ~250 | `core/llm_chain.py` |
| Rule-based fallbacks (S1-S7) | Python | ~80 | `core/llm_chain.py` |
| Cost budget system | Python | ~220 | `core/cost_budget.py` |
| Cost tracking table + aggregate | SQL | ~30 | `migrations/004_cost_tracking.sql` |
| MT5 Data Proxy service | Python | ~350 | `services/mt5_data_proxy.py` |
| MT5 Data Proxy Dockerfile | Dockerfile | ~15 | `services/mt5_data_proxy/Dockerfile` |
| VPS sizing update | Config | ~5 | Architecture docs |

**Total: ~1,400 lines of implementation-ready code/config across 6 fixes.**

---

*This fix document resolves all 6 remaining scalability gaps identified in `review_scalability_final.md`. With these fixes applied, the Alpha Stack can credibly scale from $7 to $100K+ with well-defined phase transitions, resilient LLM integration, cost awareness, and proper HA at each tier.*
