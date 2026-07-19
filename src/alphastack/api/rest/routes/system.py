"""System Routes – health check, system status, current config, readiness probes."""

from __future__ import annotations

import platform
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from alphastack.core.config import get_settings
from alphastack.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()

_START_TIME = time.time()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    version: str
    uptime_seconds: float
    timestamp: datetime
    checks: dict[str, str]


class SystemStatus(BaseModel):
    platform: str
    python_version: str
    environment: str
    uptime_seconds: float
    components: dict[str, str]


class ConfigResponse(BaseModel):
    environment: str
    api_prefix: str
    api_host: str
    api_port: int
    debug: bool
    db_host: str
    db_port: int
    db_name: str
    redis_host: str
    redis_port: int
    risk_max_drawdown_pct: float
    risk_max_position_size_pct: float
    risk_max_daily_loss_pct: float
    risk_max_open_positions: int


# ---------------------------------------------------------------------------
# Health check helpers
# ---------------------------------------------------------------------------

async def _check_database() -> str:
    """Ping the database via SQLAlchemy."""
    try:
        from alphastack.core.database import get_engine
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        return "healthy"
    except Exception as exc:
        logger.warning("healthcheck.db_failed", error=str(exc))
        return f"unhealthy: {exc}"


async def _check_redis() -> str:
    """Ping Redis."""
    try:
        from alphastack.core.redis_client import get_redis
        r = get_redis()
        await r.ping()
        return "healthy"
    except Exception as exc:
        logger.warning("healthcheck.redis_failed", error=str(exc))
        return f"unhealthy: {exc}"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Liveness probe — returns 200 if the process is alive."""
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        uptime_seconds=round(time.time() - _START_TIME, 2),
        timestamp=datetime.now(timezone.utc),
        checks={"process": "healthy"},
    )


@router.get("/health/ready")
async def readiness_check():
    """Readiness probe — checks database and Redis connectivity."""
    db_status = await _check_database()
    redis_status = await _check_redis()

    checks = {
        "database": db_status,
        "redis": redis_status,
    }

    all_healthy = all(v == "healthy" or v == "not_configured" for v in checks.values())
    resp = HealthResponse(
        status="ready" if all_healthy else "not_ready",
        version="0.1.0",
        uptime_seconds=round(time.time() - _START_TIME, 2),
        timestamp=datetime.now(timezone.utc),
        checks=checks,
    )

    if all_healthy:
        return resp
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=resp.model_dump(mode="json"),
    )


@router.get("/status", response_model=SystemStatus)
async def system_status() -> SystemStatus:
    """Detailed system status."""
    settings = get_settings()
    db_status = await _check_database()
    redis_status = await _check_redis()

    return SystemStatus(
        platform=f"{platform.system()} {platform.release()}",
        python_version=platform.python_version(),
        environment=settings.env.value,
        uptime_seconds=round(time.time() - _START_TIME, 2),
        components={
            "api": "healthy",
            "database": db_status,
            "redis": redis_status,
        },
    )


@router.get("/config", response_model=ConfigResponse)
async def get_config() -> ConfigResponse:
    """Current non-sensitive configuration."""
    settings = get_settings()
    return ConfigResponse(
        environment=settings.env.value,
        api_prefix=settings.api.api_prefix,
        api_host=settings.api.host,
        api_port=settings.api.port,
        debug=settings.api.debug,
        db_host=settings.db.host,
        db_port=settings.db.port,
        db_name=settings.db.name,
        redis_host=settings.redis.host,
        redis_port=settings.redis.port,
        risk_max_drawdown_pct=settings.risk.max_drawdown_pct,
        risk_max_position_size_pct=settings.risk.max_position_size_pct,
        risk_max_daily_loss_pct=settings.risk.max_daily_loss_pct,
        risk_max_open_positions=settings.risk.max_open_positions,
    )


@router.get("/orchestrator/health")
async def orchestrator_health():
    """Orchestrator and agent health status."""
    try:
        from alphastack.api.rest.deps import get_orchestrator
        orch = get_orchestrator()
        if orch is None:
            return {"status": "not_initialized"}
        return orch.get_health()
    except Exception as exc:
        logger.warning("orchestrator_health_failed", error=str(exc))
        return {"status": "error", "error": str(exc)}


@router.post("/orchestrator/run")
async def orchestrator_run(body: dict[str, Any]):
    """Trigger an orchestrator pipeline run."""
    try:
        from alphastack.api.rest.deps import get_orchestrator
        orch = get_orchestrator()
        if orch is None:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"detail": "Orchestrator not initialized"},
            )
        symbol = body.get("symbol", "BTC/USDT")
        timeframe = body.get("timeframe", "1h")
        market_data = body.get("market_data", {})
        result = await orch.run(
            market_data=market_data,
            symbol=symbol,
            timeframe=timeframe,
        )
        return result.model_dump(mode="json") if hasattr(result, "model_dump") else result
    except Exception as exc:
        logger.error("orchestrator_run_failed", error=str(exc), exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(exc)},
        )
