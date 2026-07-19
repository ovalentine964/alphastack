"""
Health check endpoints for AlphaStack.

Provides:
- Liveness probe: Is the process alive?
- Readiness probe: Are all dependencies healthy?
- Dependency health: Redis, PostgreSQL, brokers, LLM API

Usage:
    from alphastack.monitoring.health import health_registry

    # Register dependencies at startup
    health_registry.register("redis", check_redis)
    health_registry.register("postgres", check_postgres)

    # In your FastAPI app:
    @app.get("/health")
    async def liveness():
        return health_registry.liveness()

    @app.get("/health/ready")
    async def readiness():
        result = health_registry.readiness()
        status_code = 200 if result["status"] == "healthy" else 503
        return JSONResponse(content=result, status_code=status_code)

    @app.get("/health/deps")
    async def dependencies():
        return health_registry.check_all()
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class DependencyHealth:
    """Health status of a single dependency."""
    name: str
    status: HealthStatus
    latency_ms: float = 0.0
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemHealth:
    """Overall system health."""
    status: HealthStatus
    timestamp: float
    uptime_seconds: float
    version: str = "0.1.0"
    dependencies: list[DependencyHealth] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "timestamp": self.timestamp,
            "uptime_seconds": round(self.uptime_seconds, 2),
            "version": self.version,
            "dependencies": [
                {
                    "name": d.name,
                    "status": d.status.value,
                    "latency_ms": round(d.latency_ms, 2),
                    "message": d.message,
                    **d.metadata,
                }
                for d in self.dependencies
            ],
        }


# Type for dependency check functions
DependencyCheckFn = Callable[[], Awaitable[DependencyHealth]]


class HealthRegistry:
    """
    Registry for health check functions.

    Each dependency registers an async callable that returns DependencyHealth.
    The registry provides liveness, readiness, and detailed dependency checks.
    """

    def __init__(self, version: str = "0.1.0") -> None:
        self._checks: dict[str, DependencyCheckFn] = {}
        self._start_time: float = time.time()
        self._version: str = version
        self._cache: dict[str, DependencyHealth] = {}
        self._cache_ttl: float = 5.0  # seconds
        self._cache_time: float = 0.0

    def register(self, name: str, check_fn: DependencyCheckFn) -> None:
        """Register a dependency health check function."""
        self._checks[name] = check_fn

    def unregister(self, name: str) -> None:
        """Remove a dependency health check."""
        self._checks.pop(name, None)
        self._cache.pop(name, None)

    async def check_one(self, name: str) -> DependencyHealth:
        """Run a single dependency check."""
        if name not in self._checks:
            return DependencyHealth(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=f"Unknown dependency: {name}",
            )

        start = time.perf_counter()
        try:
            result = await self._checks[name]()
            result.latency_ms = (time.perf_counter() - start) * 1000
            return result
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            return DependencyHealth(
                name=name,
                status=HealthStatus.UNHEALTHY,
                latency_ms=latency_ms,
                message=f"Check failed: {exc}",
            )

    async def check_all(self, use_cache: bool = True) -> list[DependencyHealth]:
        """Run all dependency checks in parallel."""
        now = time.time()

        if use_cache and (now - self._cache_time) < self._cache_ttl and self._cache:
            return list(self._cache.values())

        if not self._checks:
            return []

        tasks = {name: asyncio.create_task(self.check_one(name)) for name in self._checks}
        results: list[DependencyHealth] = []

        for name, task in tasks.items():
            try:
                result = await task
            except Exception as exc:
                result = DependencyHealth(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Task failed: {exc}",
                )
            results.append(result)
            self._cache[name] = result

        self._cache_time = now
        return results

    def liveness(self) -> dict[str, Any]:
        """
        Liveness probe: Is the process alive?

        Always returns 200 if the process is running.
        Used by Kubernetes livenessProbe.
        """
        return {
            "status": "alive",
            "uptime_seconds": round(time.time() - self._start_time, 2),
            "version": self._version,
        }

    async def readiness(self) -> dict[str, Any]:
        """
        Readiness probe: Can the system serve traffic?

        Returns healthy only if ALL critical dependencies are healthy.
        Used by Kubernetes readinessProbe.
        """
        deps = await self.check_all(use_cache=False)

        # Determine overall status
        statuses = [d.status for d in deps]

        if not deps:
            overall = HealthStatus.HEALTHY
        elif all(s == HealthStatus.HEALTHY for s in statuses):
            overall = HealthStatus.HEALTHY
        elif any(s == HealthStatus.UNHEALTHY for s in statuses):
            overall = HealthStatus.UNHEALTHY
        else:
            overall = HealthStatus.DEGRADED

        health = SystemHealth(
            status=overall,
            timestamp=time.time(),
            uptime_seconds=time.time() - self._start_time,
            version=self._version,
            dependencies=deps,
        )
        return health.to_dict()

    async def detailed(self) -> dict[str, Any]:
        """
        Detailed health check with all dependency information.

        Returns full status of every registered dependency.
        """
        deps = await self.check_all(use_cache=False)

        statuses = [d.status for d in deps]
        if not deps:
            overall = HealthStatus.HEALTHY
        elif all(s == HealthStatus.HEALTHY for s in statuses):
            overall = HealthStatus.HEALTHY
        elif any(s == HealthStatus.UNHEALTHY for s in statuses):
            overall = HealthStatus.UNHEALTHY
        else:
            overall = HealthStatus.DEGRADED

        health = SystemHealth(
            status=overall,
            timestamp=time.time(),
            uptime_seconds=time.time() - self._start_time,
            version=self._version,
            dependencies=deps,
        )
        return health.to_dict()


# ─── Default health check implementations ─────────────────────────


async def check_redis(redis_client: Any = None) -> DependencyHealth:
    """Check Redis connectivity."""
    try:
        if redis_client is None:
            # Try to import and create a client
            import os
            import redis.asyncio as aioredis

            url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
            redis_client = aioredis.from_url(url)

        start = time.perf_counter()
        pong = await redis_client.ping()
        latency_ms = (time.perf_counter() - start) * 1000

        if pong:
            info = await redis_client.info("memory")
            used_memory = info.get("used_memory", 0)
            return DependencyHealth(
                name="redis",
                status=HealthStatus.HEALTHY,
                latency_ms=latency_ms,
                message="Connected",
                metadata={"used_memory_bytes": used_memory},
            )
        else:
            return DependencyHealth(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                message="Ping returned False",
            )
    except Exception as exc:
        return DependencyHealth(
            name="redis",
            status=HealthStatus.UNHEALTHY,
            message=f"Connection failed: {exc}",
        )


async def check_postgres(db_engine: Any = None) -> DependencyHealth:
    """Check PostgreSQL / TimescaleDB connectivity."""
    try:
        if db_engine is None:
            import os
            from sqlalchemy.ext.asyncio import create_async_engine

            url = os.environ.get("DATABASE_URL", "postgresql+asyncpg://alphastack:password@localhost:5432/alphastack")
            # Convert sync URL to async if needed
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            db_engine = create_async_engine(url, pool_size=1)

        start = time.perf_counter()
        async with db_engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        latency_ms = (time.perf_counter() - start) * 1000

        return DependencyHealth(
            name="postgres",
            status=HealthStatus.HEALTHY,
            latency_ms=latency_ms,
            message="Connected",
        )
    except Exception as exc:
        return DependencyHealth(
            name="postgres",
            status=HealthStatus.UNHEALTHY,
            message=f"Connection failed: {exc}",
        )


async def check_broker(broker_name: str, broker_client: Any = None) -> DependencyHealth:
    """Check broker connectivity."""
    try:
        if broker_client is None:
            return DependencyHealth(
                name=f"broker:{broker_name}",
                status=HealthStatus.DEGRADED,
                message="No broker client configured",
            )

        start = time.perf_counter()
        is_connected = await broker_client.is_connected()
        latency_ms = (time.perf_counter() - start) * 1000

        if is_connected:
            return DependencyHealth(
                name=f"broker:{broker_name}",
                status=HealthStatus.HEALTHY,
                latency_ms=latency_ms,
                message="Connected",
            )
        else:
            return DependencyHealth(
                name=f"broker:{broker_name}",
                status=HealthStatus.UNHEALTHY,
                message="Disconnected",
            )
    except Exception as exc:
        return DependencyHealth(
            name=f"broker:{broker_name}",
            status=HealthStatus.UNHEALTHY,
            message=f"Check failed: {exc}",
        )


# ─── Global registry instance ────────────────────────────────────

health_registry = HealthRegistry()
