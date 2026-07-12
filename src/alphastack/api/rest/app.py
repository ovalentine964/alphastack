"""FastAPI Application – middleware, CORS, auth, rate limiting, health checks."""

from __future__ import annotations

import time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from alphastack.core.config import get_settings
from alphastack.utils.logger import get_logger, setup_logging

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Rate limiter (simple in-memory token bucket)
# ---------------------------------------------------------------------------

class RateLimiter:
    """Per-IP token bucket rate limiter."""

    def __init__(self, requests_per_minute: int = 120) -> None:
        self.rpm = requests_per_minute
        self._buckets: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        window = now - 60
        bucket = self._buckets[key]
        # Prune old entries
        self._buckets[key] = [t for t in bucket if t > window]
        if len(self._buckets[key]) >= self.rpm:
            return False
        self._buckets[key].append(now)
        return True


rate_limiter = RateLimiter()


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    setup_logging()
    logger.info("api_startup")
    yield
    logger.info("api_shutdown")


# ---------------------------------------------------------------------------
# FastAPI app factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="AlphaStack API",
        version="0.1.0",
        description="Multi-Agent AI Trading System – REST & WebSocket API",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # -- CORS ----------------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -- Rate limit middleware ------------------------------------------------
    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        if not rate_limiter.is_allowed(client_ip):
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded"},
            )
        return await call_next(request)

    # -- Request timing middleware --------------------------------------------
    @app.middleware("http")
    async def timing_middleware(request: Request, call_next):
        start = time.perf_counter()
        response: Response = await call_next(request)
        elapsed = time.perf_counter() - start
        response.headers["X-Process-Time"] = f"{elapsed:.4f}"
        return response

    # -- Register routes -----------------------------------------------------
    from alphastack.api.rest.routes.auth import router as auth_router
    from alphastack.api.rest.routes.portfolio import router as portfolio_router
    from alphastack.api.rest.routes.signals import router as signals_router
    from alphastack.api.rest.routes.system import router as system_router
    from alphastack.api.rest.routes.trades import router as trades_router

    prefix = settings.api.api_prefix
    app.include_router(auth_router, prefix=prefix, tags=["auth"])
    app.include_router(trades_router, prefix=prefix, tags=["trades"])
    app.include_router(portfolio_router, prefix=prefix, tags=["portfolio"])
    app.include_router(signals_router, prefix=prefix, tags=["signals"])
    app.include_router(system_router, tags=["system"])

    return app


# Module-level app instance for uvicorn
app = create_app()
