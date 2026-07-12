"""System Routes – health check, system status, current config."""

from __future__ import annotations

import platform
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter
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


class SystemStatus(BaseModel):
    platform: str
    python_version: str
    environment: str
    uptime_seconds: float
    components: dict[str, str]  # component → status


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
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Basic health check."""
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        uptime_seconds=round(time.time() - _START_TIME, 2),
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/status", response_model=SystemStatus)
async def system_status() -> SystemStatus:
    """Detailed system status."""
    settings = get_settings()
    return SystemStatus(
        platform=f"{platform.system()} {platform.release()}",
        python_version=platform.python_version(),
        environment=settings.env.value,
        uptime_seconds=round(time.time() - _START_TIME, 2),
        components={
            "api": "healthy",
            "database": "unknown",  # ping DB in production
            "redis": "unknown",
            "timescaledb": "unknown",
            "trading_engine": "unknown",
            "data_pipeline": "unknown",
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
