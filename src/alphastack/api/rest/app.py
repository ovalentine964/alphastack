"""FastAPI Application – middleware, CORS, auth, rate limiting, security headers.

Implements:
- Proper CORS with explicit methods/headers (not wildcards)
- Security headers (CSP, HSTS, X-Content-Type-Options, etc.)
- Per-IP rate limiting with retry-after headers
- Authentication dependency injection for protected routes
"""

from __future__ import annotations

import os
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from alphastack.core.config import get_settings
from alphastack.utils.logger import get_logger, setup_logging

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Rate limiter (in-memory token bucket with rate-limit headers)
# ---------------------------------------------------------------------------

class RateLimiter:
    """Per-IP token bucket rate limiter with rate-limit response headers."""

    def __init__(self, requests_per_minute: int = 120, burst: int = 30) -> None:
        self.rpm = requests_per_minute
        self.burst = burst
        self._buckets: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str) -> tuple[bool, int, int, int]:
        """Check rate limit. Returns (allowed, remaining, limit, retry_after)."""
        now = time.time()
        window = now - 60
        bucket = self._buckets[key]
        # Prune old entries
        self._buckets[key] = [t for t in bucket if t > window]
        current = len(self._buckets[key])
        remaining = max(0, self.rpm - current)

        if current >= self.rpm:
            # Calculate retry-after from oldest entry in window
            oldest = min(self._buckets[key]) if self._buckets[key] else now
            retry_after = max(1, int(oldest + 60 - now) + 1)
            return False, 0, self.rpm, retry_after

        self._buckets[key].append(now)
        return True, remaining - 1, self.rpm, 0


rate_limiter = RateLimiter()


# ---------------------------------------------------------------------------
# Protected paths (skip auth for these)
# ---------------------------------------------------------------------------

_PUBLIC_PATHS = {
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
}
_PUBLIC_PREFIXES = (
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/refresh",
)


def _is_public_path(path: str) -> bool:
    """Check if a path is publicly accessible (no auth required)."""
    if path in _PUBLIC_PATHS:
        return True
    for prefix in _PUBLIC_PREFIXES:
        if path.startswith(prefix):
            return True
    return False


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle — initialise event bus and broker registry."""
    setup_logging()
    logger.info("api_startup")

    # --- Wire up event bus (Redis Streams) ---
    try:
        from alphastack.api.rest.deps import set_event_bus
        from alphastack.core.events import EventBus
        settings = get_settings()
        bus = EventBus(redis_url=settings.redis.url)
        await bus.connect()
        set_event_bus(bus)
        logger.info("api_startup.event_bus_connected")
    except Exception as exc:
        logger.info("api_startup.event_bus_skipped", reason=str(exc))

    # --- Wire up broker registry ---
    registry = None
    try:
        from alphastack.api.rest.deps import get_broker_registry
        from alphastack.brokers.ccxt_connector import CCXTConnector
        settings = get_settings()
        registry = get_broker_registry()
        if settings.ccxt.api_key.get_secret_value():
            connector = CCXTConnector(
                exchange_id=settings.ccxt.exchange,
                api_key=settings.ccxt.api_key.get_secret_value(),
                secret=settings.ccxt.secret.get_secret_value(),
                sandbox=settings.ccxt.sandbox,
            )
            registry.register("ccxt", connector)
            await connector.connect()
            logger.info("api_startup.broker_connected", broker="ccxt")
    except Exception as exc:
        logger.info("api_startup.broker_skipped", reason=str(exc))

    # --- Wire up orchestrator ---
    try:
        from alphastack.agents.orchestrator.graph import AlphaStackOrchestrator
        from alphastack.api.rest.deps import set_orchestrator
        orch = AlphaStackOrchestrator(
            event_bus=bus if 'bus' in dir() else None,
            human_in_the_loop=False,
            broker_registry=registry,
        )
        set_orchestrator(orch)
        logger.info("api_startup.orchestrator_created")
    except Exception as exc:
        logger.info("api_startup.orchestrator_skipped", reason=str(exc))

    yield

    # --- Shutdown ---
    try:
        from alphastack.api.rest.deps import get_event_bus
        bus = get_event_bus()
        if bus:
            await bus.close()
    except Exception:
        pass
    try:
        from alphastack.api.rest.deps import get_broker_registry
        registry = get_broker_registry()
        await registry.disconnect_all()
    except Exception:
        pass
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

    # -- CORS (explicit methods/headers, not wildcards) -----------------------
    allowed_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    allowed_headers = [
        "Authorization",
        "Content-Type",
        "Accept",
        "Origin",
        "X-Requested-With",
        "X-Request-ID",
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.cors_origins,
        allow_credentials=True,
        allow_methods=allowed_methods,
        allow_headers=allowed_headers,
        expose_headers=["X-Process-Time", "X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
        max_age=600,
    )

    # -- Security headers middleware -----------------------------------------
    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        return response

    # -- Rate limit middleware with headers -----------------------------------
    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        allowed, remaining, limit, retry_after = rate_limiter.is_allowed(client_ip)
        if not allowed:
            resp = JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded"},
            )
            resp.headers["X-RateLimit-Limit"] = str(limit)
            resp.headers["X-RateLimit-Remaining"] = "0"
            resp.headers["Retry-After"] = str(retry_after)
            return resp

        response: Response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response

    # -- Auth middleware for protected REST endpoints -------------------------
    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        # Skip auth for public paths, WebSocket, and OPTIONS (CORS preflight)
        path = request.url.path
        if (
            _is_public_path(path)
            or request.method == "OPTIONS"
            or path == "/ws"
        ):
            return await call_next(request)

        # Only enforce auth on API routes
        if not path.startswith("/api/v1/"):
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Missing or invalid Authorization header"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = auth_header[7:]
        try:
            from alphastack.api.rest.routes.auth import get_auth_manager, blocklist
            auth = get_auth_manager()
            claims = auth.jwt.decode_token(token)

            # Check blocklist
            jti = claims.get("jti", "")
            if jti and blocklist.is_revoked(jti):
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Token has been revoked"},
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # Store claims in request state for route handlers
            request.state.user = claims
        except Exception as exc:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": f"Invalid token: {exc}"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        return await call_next(request)

    # -- Request timing + Prometheus metrics middleware ----------------------
    @app.middleware("http")
    async def timing_middleware(request: Request, call_next):
        # Skip metrics for the /metrics endpoint itself
        if request.url.path == "/metrics":
            return await call_next(request)
        start = time.perf_counter()
        response: Response = await call_next(request)
        elapsed = time.perf_counter() - start
        response.headers["X-Process-Time"] = f"{elapsed:.4f}"
        # Record Prometheus metrics
        try:
            from alphastack.utils.metrics import API_REQUESTS, API_LATENCY
            API_REQUESTS.labels(
                method=request.method,
                endpoint=request.url.path,
                status=str(response.status_code),
            ).inc()
            API_LATENCY.labels(
                method=request.method,
                endpoint=request.url.path,
            ).observe(elapsed)
        except Exception:
            pass  # Never fail a request because of metrics
        return response

    # -- Prometheus metrics endpoint ----------------------------------------
    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> PlainTextResponse:
        """Expose Prometheus metrics."""
        return PlainTextResponse(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST,
        )

    # -- Security middleware (IP allowlist, request signing, audit) -----------
    try:
        from alphastack.security.middleware import (
            IPAllowlistMiddleware,
            RequestSigningMiddleware,
            SecurityAuditMiddleware,
        )

        # IP allowlist (honours ALPHASTACK_IP_ALLOWLIST env var)
        app.add_middleware(IPAllowlistMiddleware)

        # Request signing validation (honours ALPHASTACK_REQUEST_SIGNING_KEY env var)
        app.add_middleware(RequestSigningMiddleware)

        # Comprehensive audit logging for all API requests
        app.add_middleware(SecurityAuditMiddleware)

        logger.info("api_startup.security_middleware_loaded")
    except Exception as exc:
        logger.warning("api_startup.security_middleware_skipped", reason=str(exc))

    # -- Register routes -----------------------------------------------------
    from alphastack.api.rest.routes.auth import router as auth_router
    from alphastack.api.rest.routes.brokers import router as brokers_router
    from alphastack.api.rest.routes.portfolio import router as portfolio_router
    from alphastack.api.rest.routes.signals import router as signals_router
    from alphastack.api.rest.routes.system import router as system_router
    from alphastack.api.rest.routes.trades import router as trades_router

    prefix = settings.api.api_prefix
    app.include_router(auth_router, prefix=prefix, tags=["auth"])
    app.include_router(trades_router, prefix=prefix, tags=["trades"])
    app.include_router(portfolio_router, prefix=prefix, tags=["portfolio"])
    app.include_router(signals_router, prefix=prefix, tags=["signals"])
    app.include_router(brokers_router, prefix=prefix, tags=["brokers"])
    app.include_router(system_router, tags=["system"])

    return app


# Module-level app instance for uvicorn
app = create_app()
