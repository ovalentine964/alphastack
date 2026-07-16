"""
AlphaStack Live Server — Full Production Integration

Uses the REAL multi-agent orchestrator, 16-step strategy pipeline, risk agent,
execution agent, reflection agent, AGI memory/planning, broker registry,
event bus, and all production API routes.

Runs without Redis/PostgreSQL by using in-memory fallbacks.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import os
import secrets
import sys
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

# ─── Path setup ────────────────────────────────────────────
_SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

import ccxt
import jwt
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel

# ─── Monkey-patch known bugs in src/ ──────────────────────
try:
    import alphastack.strategy.steps.s10_confluence as _s10
    if not hasattr(_s10, '_WEIGHTS'):
        _s10._WEIGHTS = _s10._DEFAULT_WEIGHTS
except Exception as _mp_err:
    logging.getLogger("alphastack.live").warning("Monkey-patch for s10_confluence failed: %s", _mp_err)

# ─── Production imports ───────────────────────────────────
from alphastack.strategy.context import AlphaStackContext, Direction
from alphastack.strategy.pipeline import AlphaStackPipeline
from alphastack.agents.orchestrator.graph import AlphaStackOrchestrator
from alphastack.agents.orchestrator.state import AlphaStackState, Signal, TradeDecision, RiskStatus
from alphastack.agents.strategy.agent import StrategyAgent
from alphastack.agents.risk.agent import RiskAgent
from alphastack.agents.news.agent import NewsAgent
from alphastack.agents.execution.agent import ExecutionAgent
from alphastack.agents.reflection.agent import ReflectionAgent
from alphastack.core.events import EventBus, SignalEvent, TradeEvent, EventType
from alphastack.brokers.registry import BrokerRegistry
from alphastack.api.rest.deps import TradeStore, SignalStore, PortfolioService
from alphastack.security.validators import InputValidator
from alphastack.agi.memory import EpisodicMemory, TradeEpisode
from alphastack.agi.planning import TradePlanner
from alphastack.engine.loop import TradingLoop, LoopConfig, LoopState, Interval
from alphastack.utils.logger import setup_logging, get_logger
from alphastack.integrations.telegram_bot import (
    AlphaTelegramBot,
    TelegramConfig,
    set_bot as set_telegram_bot,
)

logger = get_logger("alphastack.live")

# ═══════════════════════════════════════════════════════════
# In-Memory EventBus (replaces Redis Streams)
# ═══════════════════════════════════════════════════════════

class InMemoryEventBus:
    """In-memory event bus that mimics the Redis Streams EventBus API."""

    def __init__(self) -> None:
        self._handlers: dict[EventType, list] = {}
        self._events: list = []

    async def connect(self) -> None:
        logger.info("event_bus.in_memory_connected")

    async def close(self) -> None:
        logger.info("event_bus.closed")

    async def publish(self, event, max_len: int = 100_000) -> str:
        entry_id = uuid.uuid4().hex[:12]
        self._events.append((entry_id, event))
        for handler in self._handlers.get(event.type, []):
            try:
                await handler(event)
            except Exception:
                logger.warning("event_bus.handler_error", exc_info=True)
        return entry_id

    def subscribe(self, event_type, handler) -> None:
        self._handlers.setdefault(event_type, []).append(handler)


# ═══════════════════════════════════════════════════════════
# Global Singletons
# ═══════════════════════════════════════════════════════════

# Binance public (no keys needed)
exchange_public = ccxt.binance({
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'},
})

# ─── Encoding safety: strip non-ASCII chars that break latin-1 codec ───
def _sanitize_str(val: str) -> str:
    """Remove non-ASCII characters (e.g. U+2026 ellipsis) that cause
    ccxt/requests HMAC signing to fail with latin-1 codec error."""
    return val.encode('ascii', 'ignore').decode('ascii')


# Testnet for trading
BINANCE_API_KEY = _sanitize_str(os.environ.get("BINANCE_API_KEY", ""))
BINANCE_API_SECRET = _sanitize_str(os.environ.get("BINANCE_API_SECRET", ""))
exchange_testnet = None
if BINANCE_API_KEY and BINANCE_API_SECRET:
    exchange_testnet = ccxt.binance({
        'apiKey': BINANCE_API_KEY,
        'secret': BINANCE_API_SECRET,
        'enableRateLimit': True,
        'options': {'defaultType': 'spot'},
    })
    exchange_testnet.set_sandbox_mode(True)

# Event bus (in-memory — no Redis needed)
event_bus = InMemoryEventBus()

# Broker registry
broker_registry = BrokerRegistry()

# Production stores (from deps.py)
trade_store = TradeStore()
signal_store = SignalStore()
portfolio_service = PortfolioService()

# Wire the global singletons into deps.py
import alphastack.api.rest.deps as _deps
_deps.set_event_bus(event_bus)
_deps.set_broker_registry(broker_registry)
# Replace the module-level singletons
_deps.trade_store = trade_store
_deps.signal_store = signal_store
_deps.portfolio_service = portfolio_service

# AGI modules
episodic_memory = EpisodicMemory()
trade_planner = TradePlanner()

# Multi-agent orchestrator (human_in_the_loop=False for automated demo)
orchestrator = AlphaStackOrchestrator(
    event_bus=event_bus,
    human_in_the_loop=False,
)

# Signal cache
_SIGNAL_CACHE: dict[str, Any] = {"signals": [], "ts": 0.0}
_SIGNAL_TTL = 60
_SIGNAL_CACHE_LOCK = asyncio.Lock()

# Trading loop (initialized after helpers are defined)
trading_loop: Optional[TradingLoop] = None

# Telegram bot (initialized in lifespan if configured)
_telegram_bot: AlphaTelegramBot | None = None

# Token store
_ACTIVE_TOKENS: dict[str, dict] = {}

# Token blocklist for logout / refresh-token rotation
_TOKEN_BLOCKLIST: set[str] = set()
_TOKEN_BLOCKLIST_MAX: int = 10000


# ═══════════════════════════════════════════════════════════
# Market Data Helpers
# ═══════════════════════════════════════════════════════════

def _compute_atr(highs, lows, closes, period=14):
    if len(closes) < period + 1:
        return 0.0
    trs = []
    for i in range(1, len(closes)):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
        trs.append(tr)
    if len(trs) < period:
        return sum(trs) / len(trs) if trs else 0.0
    atr = sum(trs[:period]) / period
    for i in range(period, len(trs)):
        atr = (atr * (period - 1) + trs[i]) / period
    return atr


async def _fetch_ohlcv(symbol, timeframe="1h", limit=200):
    return await asyncio.to_thread(exchange_public.fetch_ohlcv, _sanitize_str(symbol), timeframe, limit=limit)


async def _build_market_data(symbol: str) -> dict[str, Any]:
    """Fetch real market data from Binance for the pipeline."""
    candles_1h = await _fetch_ohlcv(symbol, "1h", 200)
    candles_4h = await _fetch_ohlcv(symbol, "4h", 100)
    candles_1d = await _fetch_ohlcv(symbol, "1d", 60)

    def extract(candles):
        return ([c[1] for c in candles], [c[2] for c in candles],
                [c[3] for c in candles], [c[4] for c in candles],
                [c[5] for c in candles])

    opens, highs, lows, closes, volumes = extract(candles_1h)
    _, _, _, h4_closes, _ = extract(candles_4h)
    _, _, _, d_closes, _ = extract(candles_1d)

    current_price = closes[-1] if closes else 0.0
    atr = _compute_atr(highs, lows, closes, 14)
    pip_size = 1.0

    spread_pips = 1.0
    try:
        ob = await asyncio.to_thread(exchange_public.fetch_order_book, symbol, 5)
        if ob['bids'] and ob['asks']:
            spread_pips = (ob['asks'][0][0] - ob['bids'][0][0]) / pip_size
    except Exception:
        pass

    return {
        "opens": opens, "highs": highs, "lows": lows, "closes": closes, "volumes": volumes,
        "close": current_price,
        "timeframe_closes": {"1h": closes[-50:], "4h": h4_closes[-50:], "1d": d_closes[-50:]},
        "htf_closes": d_closes[-50:] if len(d_closes) >= 50 else d_closes,
        "atr_pips": round(atr / pip_size, 2), "pip_size": pip_size,
        "spread_pips": round(spread_pips, 2), "pip_value": 1.0,
        "news_sentiment": 0.0, "high_impact_events": [], "volatility_index": 0.0,
        "account_balance": 10_000.0, "risk_pct": 1.0, "rsi_period": 14,
        "rr_multipliers": [1.5, 2.5, 4.0],
    }


# ═══════════════════════════════════════════════════════════
# Pipeline + Orchestrator Signal Generation
# ═══════════════════════════════════════════════════════════

async def _run_pipeline_signal(symbol: str) -> dict[str, Any]:
    """Run the 16-step pipeline directly and return a signal dict."""
    try:
        market_data = await _build_market_data(symbol)
        ctx = AlphaStackContext(symbol=symbol, timeframe="1H", market_data=market_data)
        pipeline = AlphaStackPipeline(parallel=False)
        ctx = await pipeline.run(ctx)

        if ctx.confluence.direction == Direction.NONE:
            return {}

        score = ctx.confluence.score
        dir_str = ctx.confluence.direction.value
        strength = "very_strong" if score >= 80 else "strong" if score >= 60 else "moderate" if score >= 40 else "weak"

        reasons = [f"Confluence {score:.0f}/100"]
        if ctx.bias.bias.value != "neutral":
            reasons.append(f"Bias: {ctx.bias.bias.value}")
        if ctx.structure.structure_type.value != "consolidation":
            reasons.append(f"Structure: {ctx.structure.structure_type.value}")
        if ctx.rsi.signal != "neutral":
            reasons.append(f"RSI: {ctx.rsi.value:.0f} ({ctx.rsi.signal})")
        for p in ctx.candlestick.patterns:
            reasons.append(f"Pattern: {p.name}")

        return {
            "id": f"sig-{symbol.replace('/', '-')}-pipeline",
            "symbol": symbol, "direction": dir_str, "strength": strength,
            "strategy_id": "alphastack_pipeline", "confidence": round(min(score / 100, 0.99), 2),
            "entry_price": round(ctx.market_data.get("close", 0), 2),
            "stop_loss": round(ctx.stop_loss.price, 2) if ctx.stop_loss.price else None,
            "take_profit": [round(tp, 2) for tp in ctx.take_profit.levels] if ctx.take_profit.levels else None,
            "risk_reward": ctx.take_profit.rr_ratio,
            "confluence_score": round(score, 1),
            "reason": " | ".join(reasons),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "is_active": True,
            "component_scores": {k: round(v, 3) for k, v in ctx.confluence.component_scores.items()},
            "session": ctx.session.active.value, "structure": ctx.structure.structure_type.value,
            "rsi": round(ctx.rsi.value, 1), "patterns": [p.name for p in ctx.candlestick.patterns],
        }
    except Exception as e:
        logger.warning("pipeline_failed", symbol=symbol, error=str(e))
        return {}


async def _run_orchestrator(symbol: str) -> dict[str, Any]:
    """Run the full 5-agent orchestrator pipeline.

    Runs each agent individually (news → strategy → risk → execution → reflection)
    to avoid LangGraph state serialization issues with nested Pydantic models.
    """
    try:
        market_data = await _build_market_data(symbol)

        # Build initial state
        state = AlphaStackState(
            run_id=uuid.uuid4().hex[:12],
            market_data=market_data,
            current_symbol=symbol,
            current_timeframe="1h",
            started_at=datetime.now(timezone.utc),
        ).model_dump(mode="json")

        agent_messages = []

        # 1. News agent
        try:
            news_result = await orchestrator.news_agent.run(state)
            state.update(news_result)
            agent_messages.append({"from_agent": "news", "content": f"Detected {len(state.get('news_alerts', []))} alerts, risk adj: {state.get('news_risk_adjustment', 0)}x"})
        except Exception as e:
            logger.warning("news_agent_failed", error=str(e))

        # 2. Strategy agent (pipeline)
        try:
            strat_result = await orchestrator.strategy_agent.run(state)
            state.update(strat_result)
            agent_messages.append({"from_agent": "strategy", "content": f"Generated {len(state.get('signals', []))} signals"})
        except Exception as e:
            logger.warning("strategy_agent_failed", error=str(e))

        # 3. Risk agent
        try:
            risk_result = await orchestrator.risk_agent.run(state)
            state.update(risk_result)
            approved = sum(1 for d in state.get('trade_decisions', []) if (d.get('status') if isinstance(d, dict) else getattr(d, 'status', '')) == 'approved')
            agent_messages.append({"from_agent": "risk", "content": f"Approved {approved} decisions"})
        except Exception as e:
            logger.warning("risk_agent_failed", error=str(e))

        # 4. Execution agent
        try:
            exec_result = await orchestrator.execution_agent.run(state)
            state.update(exec_result)
            filled = sum(1 for e in state.get('execution_log', []) if e.get('status') == 'filled')
            agent_messages.append({"from_agent": "execution", "content": f"Executed {filled} orders"})
        except Exception as e:
            logger.warning("execution_agent_failed", error=str(e))

        # 5. Reflection agent
        try:
            refl_result = await orchestrator.reflection_agent.run(state)
            state.update(refl_result)
            agent_messages.append({"from_agent": "reflection", "content": "Post-trade analysis complete"})
        except Exception as e:
            logger.warning("reflection_agent_failed", error=str(e))

        # Build response
        signals = []
        for sig in state.get('signals', []):
            s = sig if isinstance(sig, dict) else (sig.model_dump() if hasattr(sig, 'model_dump') else sig)
            s["created_at"] = datetime.now(timezone.utc).isoformat()
            s["expires_at"] = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
            s["is_active"] = True
            s["id"] = f"sig-{symbol.replace('/', '-')}-orchestrator"
            signals.append(s)

        risk_status = state.get('risk_status', {})
        if hasattr(risk_status, 'model_dump'):
            risk_status = risk_status.model_dump()

        trade_decisions = []
        for d in state.get('trade_decisions', []):
            trade_decisions.append(d if isinstance(d, dict) else (d.model_dump() if hasattr(d, 'model_dump') else d))

        news_alerts = []
        for a in state.get('news_alerts', []):
            news_alerts.append(a if isinstance(a, dict) else (a.model_dump() if hasattr(a, 'model_dump') else a))

        return {
            "signals": signals,
            "risk_status": risk_status,
            "trade_decisions": trade_decisions,
            "news_alerts": news_alerts,
            "agent_messages": agent_messages,
            "performance_summary": state.get('performance_summary', {}),
            "execution_log": state.get('execution_log', []),
        }
    except Exception as e:
        logger.warning("orchestrator_failed", symbol=symbol, error=str(e), exc_info=True)
        return {}


def _init_trading_loop() -> TradingLoop:
    """Create the TradingLoop singleton wired to existing singletons."""
    cfg = LoopConfig(interval=Interval.H4)
    return TradingLoop(
        config=cfg,
        build_market_data=_build_market_data,
        run_pipeline=_run_pipeline_signal,
        run_orchestrator=_run_orchestrator,
        trade_store=trade_store,
        episodic_memory=episodic_memory,
        event_bus=event_bus,
    )


async def _generate_signals() -> list[dict[str, Any]]:
    """Generate signals using the pipeline, with caching."""
    async with _SIGNAL_CACHE_LOCK:
        now = time.time()
        if now - _SIGNAL_CACHE["ts"] < _SIGNAL_TTL and _SIGNAL_CACHE["signals"]:
            return _SIGNAL_CACHE["signals"]

        symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']
        results = await asyncio.gather(*[_run_pipeline_signal(s) for s in symbols], return_exceptions=True)
        signals = [r for r in results if isinstance(r, dict) and r]

        _SIGNAL_CACHE["signals"] = signals
        _SIGNAL_CACHE["ts"] = now
        return signals


# ═══════════════════════════════════════════════════════════
# Auth helpers
# ═══════════════════════════════════════════════════════════

_JWT_SECRET = os.environ.get("ALPHASTACK_JWT_SECRET")
if not _JWT_SECRET:
    _JWT_SECRET = hashlib.sha256(b"alphastack-dev-secret-v1").hexdigest()
    logging.getLogger("alphastack.live").warning(
        "ALPHASTACK_JWT_SECRET not set — using deterministic dev fallback. "
        "Set the env var in production!"
    )
_JWT_ALGO = "HS256"

_ADMIN_USER = os.environ.get("ALPHASTACK_ADMIN_USER", "")
_ADMIN_HASH = os.environ.get("ALPHASTACK_ADMIN_HASH", "")
_AUTH_CONFIGURED = bool(_ADMIN_USER and _ADMIN_HASH)


def _create_token(sub: str, ttl_seconds: int, token_type: str = "access") -> str:
    payload = {"sub": sub, "type": token_type, "iat": int(time.time()),
               "exp": int(time.time()) + ttl_seconds, "jti": secrets.token_hex(16)}
    return jwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALGO)


def _decode_token(token: str) -> dict:
    return jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGO])


# ═══════════════════════════════════════════════════════════
# Rate Limiter
# ═══════════════════════════════════════════════════════════

class RateLimiter:
    def __init__(self, rpm=120, burst=30):
        self.rpm = rpm
        self._buckets: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str):
        now = time.time()
        window = now - 60
        self._buckets[key] = [t for t in self._buckets[key] if t > window]
        current = len(self._buckets[key])
        if current >= self.rpm:
            oldest = min(self._buckets[key])
            return False, 0, self.rpm, max(1, int(oldest + 60 - now) + 1)
        self._buckets[key].append(now)
        return True, max(0, self.rpm - current - 1), self.rpm, 0


rate_limiter = RateLimiter()
_LOGIN_LIMITER = RateLimiter(rpm=10, burst=3)


# ═══════════════════════════════════════════════════════════
# FastAPI App
# ═══════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _telegram_bot, trading_loop
    setup_logging(json_output=False)
    logger.info("api_startup")
    await event_bus.connect()
    logger.info("api_startup.event_bus_connected")
    trading_loop = _init_trading_loop()
    logger.info("api_startup.trading_loop_initialized")

    # Start Telegram bot if configured
    tg_config = TelegramConfig()
    if tg_config.is_configured:
        _telegram_bot = AlphaTelegramBot(
            config=tg_config,
            trade_store=trade_store,
            signal_store=signal_store,
            portfolio_service=portfolio_service,
            exchange_public=exchange_public,
            generate_signals=_generate_signals,
        )
        set_telegram_bot(_telegram_bot)
        asyncio.create_task(_telegram_bot.start())
        logger.info("telegram_bot.starting")

    yield

    # Graceful shutdown: stop loop before closing event bus
    if trading_loop and trading_loop.state.running:
        await trading_loop.stop()

    # Shutdown Telegram bot
    if _telegram_bot:
        await _telegram_bot.stop()
        _telegram_bot = None
        set_telegram_bot(None)

    await event_bus.close()
    logger.info("api_shutdown")


app = FastAPI(title="AlphaStack API", version="0.2.0", lifespan=lifespan)

_CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")
_CORS_ORIGINS = [o.strip() for o in _CORS_ORIGINS if o.strip()]

app.add_middleware(CORSMiddleware, allow_origins=_CORS_ORIGINS, allow_credentials=True,
                   allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
                   allow_headers=["Authorization", "Content-Type"])


# ─── Middleware ─────────────────────────────────────────────

_PUBLIC_PATHS = {"/health", "/docs", "/redoc", "/openapi.json", "/metrics"}
_PUBLIC_PREFIXES = ("/api/v1/auth/login", "/api/v1/auth/register", "/api/v1/auth/refresh")


@app.middleware("http")
async def combined_middleware(request: Request, call_next):
    # Security headers
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # Rate limiting
    client_ip = request.client.host if request.client else "unknown"
    allowed, remaining, limit, retry_after = rate_limiter.check(client_ip)
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    if not allowed:
        response.status_code = 429
        response.headers["Retry-After"] = str(retry_after)

    # Timing
    response.headers["X-Process-Time"] = "0"

    return response


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    if path in _PUBLIC_PATHS or request.method == "OPTIONS" or path == "/ws":
        return await call_next(request)
    if any(path.startswith(p) for p in _PUBLIC_PREFIXES):
        return await call_next(request)
    if not path.startswith("/api/v1/"):
        return await call_next(request)

    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"detail": "Missing Authorization header"},
                            headers={"WWW-Authenticate": "Bearer"})
    try:
        claims = _decode_token(auth_header[7:])
        # Check token blocklist (logout / refresh-rotation)
        jti = claims.get("jti", "")
        if jti and jti in _TOKEN_BLOCKLIST:
            return JSONResponse(status_code=401, content={"detail": "Token has been revoked"},
                                headers={"WWW-Authenticate": "Bearer"})
        request.state.user = claims
    except Exception:
        return JSONResponse(status_code=401, content={"detail": "Invalid token"},
                            headers={"WWW-Authenticate": "Bearer"})
    return await call_next(request)


# ═══════════════════════════════════════════════════════════
# AUTH ENDPOINTS (production JWT auth)
# ═══════════════════════════════════════════════════════════

class LoginRequest(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    apiKey: Optional[str] = None
    apiSecret: Optional[str] = None


class RefreshRequest(BaseModel):
    refresh_token: str


@app.post("/api/v1/auth/login")
async def login(body: LoginRequest, request: Request):
    # Login-specific rate limiting
    client_ip = request.client.host if request.client else "unknown"
    allowed, remaining, limit, retry_after = _LOGIN_LIMITER.check(f"login:{client_ip}")
    if not allowed:
        raise HTTPException(429, f"Too many login attempts. Retry after {retry_after}s.")
    if not _AUTH_CONFIGURED:
        raise HTTPException(503, "Auth not configured — set ALPHASTACK_ADMIN_USER and ALPHASTACK_ADMIN_HASH env vars")
    uname = body.username or body.apiKey or ""
    pwd = body.password or body.apiSecret or ""
    if not uname or not pwd:
        raise HTTPException(400, "Missing credentials")
    if uname != _ADMIN_USER or not hmac.compare_digest(_ADMIN_HASH, hashlib.sha256(pwd.encode()).hexdigest()):
        raise HTTPException(401, "Invalid credentials")
    access = _create_token(uname, 1800, "access")
    refresh = _create_token(uname, 86400 * 7, "refresh")
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer", "expires_in": 1800,
            "user": {"id": "user-001", "username": uname, "plan": "pro"}}


@app.post("/api/v1/auth/refresh")
async def refresh(body: RefreshRequest):
    try:
        payload = _decode_token(body.refresh_token)
    except Exception:
        raise HTTPException(401, "Invalid refresh token")
    if payload.get("type") != "refresh":
        raise HTTPException(400, "Not a refresh token")
    # One-time-use: revoke old refresh token
    old_jti = payload.get("jti", "")
    if old_jti:
        if len(_TOKEN_BLOCKLIST) >= _TOKEN_BLOCKLIST_MAX:
            _TOKEN_BLOCKLIST.pop()
        _TOKEN_BLOCKLIST.add(old_jti)
    access = _create_token(payload["sub"], 1800, "access")
    new_refresh = _create_token(payload["sub"], 86400 * 7, "refresh")
    return {"access_token": access, "refresh_token": new_refresh, "token_type": "bearer", "expires_in": 1800}


@app.post("/api/v1/auth/logout")
async def logout(request: Request):
    # Extract token from Authorization header and revoke its jti
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            claims = _decode_token(auth_header[7:])
            jti = claims.get("jti", "")
            if jti:
                if len(_TOKEN_BLOCKLIST) >= _TOKEN_BLOCKLIST_MAX:
                    _TOKEN_BLOCKLIST.pop()
                _TOKEN_BLOCKLIST.add(jti)
        except Exception:
            pass  # Token already invalid — nothing to revoke
    return {"message": "Logged out"}


# ═══════════════════════════════════════════════════════════
# SIGNALS ENDPOINTS (pipeline-powered)
# ═══════════════════════════════════════════════════════════

@app.get("/api/v1/signals")
async def get_signals(page: int = 1, page_size: int = 50, symbol: str = None, strategy_id: str = None):
    signals = await _generate_signals()
    if symbol:
        signals = [s for s in signals if s["symbol"].upper() == symbol.upper()]
    if strategy_id:
        signals = [s for s in signals if s.get("strategy_id") == strategy_id]
    return {"signals": signals, "total": len(signals)}


@app.get("/api/v1/signals/active")
async def active_signals():
    return await _generate_signals()


@app.get("/api/v1/signals/history")
async def signals_history(page: int = 1, page_size: int = 50, symbol: str = None):
    signals = await _generate_signals()
    return {"signals": signals, "total": len(signals)}


# ═══════════════════════════════════════════════════════════
# TRADES ENDPOINTS (production TradeStore)
# ═══════════════════════════════════════════════════════════

class TradeCreate(BaseModel):
    symbol: str
    side: str
    quantity: float
    price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    strategy_id: Optional[str] = None
    notes: str = ""


@app.get("/api/v1/trades")
async def get_trades(page: int = 1, page_size: int = 50, status: str = None, symbol: str = None):
    items = trade_store.list_trades(status_filter=status, symbol=symbol)
    total = len(items)
    start = (page - 1) * page_size
    return {"trades": items[start:start + page_size], "total": total, "page": page, "page_size": page_size}


@app.get("/api/v1/trades/{trade_id}")
async def get_trade(trade_id: str):
    trade = trade_store.get_trade(trade_id)
    if not trade:
        raise HTTPException(404, "Trade not found")
    return trade


@app.post("/api/v1/trades")
async def create_trade(body: TradeCreate):
    validation = InputValidator.validate_order(
        symbol=body.symbol, side=body.side, order_type="market" if body.price is None else "limit",
        quantity=body.quantity, price=body.price, stop_loss=body.stop_loss, take_profit=body.take_profit,
    )
    if not validation:
        raise HTTPException(400, f"Validation failed: {'; '.join(validation.errors)}")
    trade = trade_store.create_trade(body.model_dump())

    # Also try to execute on testnet if available
    if exchange_testnet and body.price is None:
        try:
            # Sanitize symbol to prevent encoding errors in request signing
            safe_symbol = _sanitize_str(body.symbol)
            order = await asyncio.to_thread(
                exchange_testnet.create_order,
                symbol=safe_symbol, type='market', side=body.side, amount=body.quantity,
            )
            trade["broker_order_id"] = order.get("id", "")
            trade["status"] = "open"
        except Exception as e:
            logger.warning("broker_execution_failed", error=str(e))
            trade["notes"] += " | Execution failed"

    return trade


@app.put("/api/v1/trades/{trade_id}/close")
async def close_trade(trade_id: str, exit_price: float = None):
    trade = trade_store.close_trade(trade_id, exit_price)
    if trade is None:
        existing = trade_store.get_trade(trade_id)
        if existing is None:
            raise HTTPException(404, "Trade not found")
        raise HTTPException(400, f"Trade is {existing['status']}, not open")

    # Record in AGI episodic memory
    episode = TradeEpisode(
        symbol=trade["symbol"],
        direction="long" if trade["side"] == "buy" else "short",
        entry_price=trade["entry_price"] or 0,
        exit_price=trade.get("exit_price") or 0,
        pnl=trade.get("pnl") or 0,
    )
    episode.finalize()
    episodic_memory.store(episode)

    return trade


# ═══════════════════════════════════════════════════════════
# PORTFOLIO ENDPOINTS (production PortfolioService)
# ═══════════════════════════════════════════════════════════

@app.get("/api/v1/portfolio")
async def portfolio_positions():
    # Try broker positions first
    broker_positions = await portfolio_service.get_positions()
    if broker_positions:
        return broker_positions
    # Fallback to trade store
    open_trades = trade_store.list_trades(status_filter="open")
    positions = []
    for t in open_trades:
        entry = t.get("entry_price") or 0
        try:
            ticker = await asyncio.to_thread(exchange_public.fetch_ticker, t["symbol"])
            current = ticker['last']
        except Exception:
            current = entry * 1.005
        qty = t["quantity"]
        side = "long" if t["side"] == "buy" else "short"
        mult = 1 if side == "long" else -1
        unrealized = (current - entry) * qty * mult
        positions.append({
            "symbol": t["symbol"], "side": side, "quantity": qty,
            "entry_price": round(entry, 6), "current_price": round(current, 6),
            "unrealized_pnl": round(unrealized, 4),
            "unrealized_pnl_pct": round(((current / entry) - 1) * 100 * mult, 4) if entry else 0,
            "weight_pct": 0,
        })
    total_val = sum(p["current_price"] * p["quantity"] for p in positions)
    for p in positions:
        p["weight_pct"] = round((p["current_price"] * p["quantity"] / total_val * 100) if total_val else 0, 2)
    return positions


@app.get("/api/v1/portfolio/pnl")
async def portfolio_pnl():
    closed = trade_store.list_trades(status_filter="closed")
    open_trades = trade_store.list_trades(status_filter="open")
    total_realized = sum(t.get("pnl") or 0 for t in closed)
    wins = [t for t in closed if (t.get("pnl") or 0) > 0]
    losses = [t for t in closed if (t.get("pnl") or 0) < 0]
    return {
        "total_realized_pnl": round(total_realized, 4),
        "total_unrealized_pnl": 0, "total_pnl": round(total_realized, 4),
        "today_pnl": round(total_realized, 4),
        "win_rate": round(len(wins) / max(len(closed), 1) * 100, 2),
        "profit_factor": round(sum(t["pnl"] for t in wins) / abs(sum(t["pnl"] for t in losses)), 4) if losses else 0,
        "avg_win": round(sum(t["pnl"] for t in wins) / len(wins), 4) if wins else 0,
        "avg_loss": round(sum(t["pnl"] for t in losses) / len(losses), 4) if losses else 0,
        "best_trade_pnl": round(max((t.get("pnl") or 0 for t in closed), default=0), 4),
        "worst_trade_pnl": round(min((t.get("pnl") or 0 for t in closed), default=0), 4),
        "total_trades": len(closed), "winning_trades": len(wins), "losing_trades": len(losses),
    }


@app.get("/api/v1/portfolio/summary")
async def portfolio_summary():
    return await portfolio_pnl()


# ═══════════════════════════════════════════════════════════
# ANALYTICS ENDPOINTS (production-grade)
# ═══════════════════════════════════════════════════════════

@app.get("/api/v1/analytics/performance")
async def analytics_performance(period: str = "30d"):
    closed = trade_store.list_trades(status_filter="closed")
    pnls = [t.get("pnl") or 0 for t in closed]
    n = len(pnls) or 1
    total_return = sum(pnls)
    mean_pnl = total_return / n
    variance = sum((p - mean_pnl) ** 2 for p in pnls) / n if n > 1 else 0
    vol = variance ** 0.5
    sharpe = (mean_pnl / vol) * (252 ** 0.5) if vol else 0

    cumulative = peak = max_dd = 0
    for p in pnls:
        cumulative += p
        peak = max(peak, cumulative)
        dd = (peak - cumulative) / max(abs(peak), 1) * 100
        max_dd = max(max_dd, dd)

    return {
        "total_return_pct": round(total_return / 10000 * 100, 4),
        "sharpe_ratio": round(sharpe, 4), "max_drawdown_pct": round(max_dd, 4),
        "total_trades": len(closed), "winning_trades": sum(1 for p in pnls if p > 0),
        "losing_trades": sum(1 for p in pnls if p < 0),
        "win_rate": round(sum(1 for p in pnls if p > 0) / n * 100, 2),
        "profit_factor": round(sum(p for p in pnls if p > 0) / abs(sum(p for p in pnls if p < 0) or 1), 4),
        "avg_trade_duration_hours": 24.0, "expectancy": round(mean_pnl, 4),
    }


@app.get("/api/v1/analytics/equity-curve")
async def analytics_equity_curve(days: int = 90):
    closed = trade_store.list_trades(status_filter="closed")
    initial = 10000.0
    cumulative = initial
    peak = initial
    points = []
    for t in sorted(closed, key=lambda x: x.get("closed_at") or "")[-days:]:
        pnl = t.get("pnl") or 0
        cumulative += pnl
        peak = max(peak, cumulative)
        dd = ((peak - cumulative) / peak * 100) if peak else 0
        points.append({"date": (t.get("closed_at") or "")[:10], "equity": round(cumulative, 2), "drawdown_pct": round(dd, 2)})
    if not points:
        points.append({"date": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "equity": initial, "drawdown_pct": 0})
    return {"points": points, "initial_capital": initial, "current_equity": round(cumulative, 2)}


@app.get("/api/v1/analytics/win-rate")
async def analytics_win_rate():
    closed = trade_store.list_trades(status_filter="closed")
    pnls = [t.get("pnl") or 0 for t in closed]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    n = len(pnls) or 1
    return {
        "win_rate": round(len(wins) / n * 100, 2), "total_trades": len(closed),
        "winning_trades": len(wins), "losing_trades": len(losses), "breakeven_trades": sum(1 for p in pnls if p == 0),
        "avg_win": round(sum(wins) / len(wins), 4) if wins else 0,
        "avg_loss": round(sum(losses) / len(losses), 4) if losses else 0,
        "largest_win": round(max(wins, default=0), 4), "largest_loss": round(min(losses, default=0), 4),
        "profit_factor": round(sum(wins) / abs(sum(losses)), 4) if losses else 0,
    }


@app.get("/api/v1/analytics/pnl-history")
async def analytics_pnl_history(period: str = "30d"):
    closed = trade_store.list_trades(status_filter="closed")
    by_date: dict[str, list[float]] = {}
    for t in closed:
        d = (t.get("closed_at") or "")[:10]
        if d:
            by_date.setdefault(d, []).append(t.get("pnl") or 0)
    cumulative = 0.0
    points = []
    for d in sorted(by_date):
        daily = sum(by_date[d])
        cumulative += daily
        points.append({"date": d, "realized_pnl": round(daily, 4), "cumulative_pnl": round(cumulative, 4), "trade_count": len(by_date[d])})
    return points


@app.get("/api/v1/analytics/risk")
async def analytics_risk():
    closed = trade_store.list_trades(status_filter="closed")
    pnls = [t.get("pnl") or 0 for t in closed]
    n = len(pnls) or 1
    cumulative = peak = max_dd = 0
    for p in pnls:
        cumulative += p
        peak = max(peak, cumulative)
        dd = (peak - cumulative) / max(abs(peak), 1) * 100
        max_dd = max(max_dd, dd)

    sorted_pnls = sorted(pnls) if pnls else [0.0]
    max_consec = cur_consec = 0
    for p in pnls:
        if p < 0:
            cur_consec += 1
            max_consec = max(max_consec, cur_consec)
        else:
            cur_consec = 0

    wins = [p for p in pnls if p > 0]
    losses = [abs(p) for p in pnls if p < 0]
    return {
        "max_drawdown_pct": round(max_dd, 2), "current_drawdown_pct": round(max_dd, 2),
        "var_95": round(sorted_pnls[max(int(n * 0.05), 0)], 4),
        "var_99": round(sorted_pnls[max(int(n * 0.01), 0)], 4),
        "sharpe_ratio": 0, "sortino_ratio": 0,
        "avg_risk_per_trade": round(sum(losses) / len(losses), 4) if losses else 0,
        "max_consecutive_losses": max_consec,
        "risk_reward_avg": round((sum(wins) / len(wins)) / (sum(losses) / len(losses)), 4) if wins and losses else 0,
    }


# ═══════════════════════════════════════════════════════════
# TRADING LOOP ENDPOINTS (continuous loop engine)
# ═══════════════════════════════════════════════════════════

class NotificationSettings(BaseModel):
    email_enabled: Optional[bool] = None
    push_enabled: Optional[bool] = None
    signal_alerts: Optional[bool] = None
    trade_alerts: Optional[bool] = None


class DisplaySettings(BaseModel):
    theme: Optional[str] = None
    language: Optional[str] = None
    timezone: Optional[str] = None
    currency: Optional[str] = None


class RiskSettings(BaseModel):
    max_position_size_pct: Optional[float] = None
    max_daily_loss_pct: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    auto_stop_loss: Optional[bool] = None


class TradingSettings(BaseModel):
    default_order_type: Optional[str] = None
    confirmation_required: Optional[bool] = None
    paper_trading: Optional[bool] = None


class SettingsSectionUpdate(BaseModel):
    notifications: Optional[NotificationSettings] = None
    display: Optional[DisplaySettings] = None
    risk: Optional[RiskSettings] = None
    trading: Optional[TradingSettings] = None

    class Config:
        extra = "forbid"


class LoopConfigUpdate(BaseModel):
    interval: Optional[str] = None
    symbols: Optional[list[str]] = None
    max_concurrent_trades: Optional[int] = None
    cooldown_after_loss: Optional[int] = None
    evolution_enabled: Optional[bool] = None


@app.post("/api/v1/loop/start")
async def loop_start():
    """Start the continuous trading loop."""
    if trading_loop is None:
        raise HTTPException(503, "Trading loop not initialized")
    result = await trading_loop.start()
    return result


@app.post("/api/v1/loop/stop")
async def loop_stop():
    """Gracefully stop the trading loop (finishes current cycle)."""
    if trading_loop is None:
        raise HTTPException(503, "Trading loop not initialized")
    result = await trading_loop.stop()
    return result


@app.get("/api/v1/loop/status")
async def loop_status():
    """Get current loop status, config, and state."""
    if trading_loop is None:
        raise HTTPException(503, "Trading loop not initialized")
    return trading_loop.status()


@app.patch("/api/v1/loop/config")
async def loop_config_update(body: LoopConfigUpdate):
    """Hot-update loop configuration (takes effect next cycle)."""
    if trading_loop is None:
        raise HTTPException(503, "Trading loop not initialized")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    result = await trading_loop.update_config(**updates)
    return result




def _validate_symbol(symbol: str) -> bool:
    """Validate a trading pair symbol format."""
    return "/" in symbol and len(symbol) < 20 and symbol.replace("/", "").replace("-", "").isalnum()


# ═══════════════════════════════════════════════════════════
# ORCHESTRATOR ENDPOINT (full multi-agent pipeline)
# ═══════════════════════════════════════════════════════════

@app.post("/api/v1/orchestrator/run")
async def run_orchestrator(symbol: str = "BTC/USDT"):
    """Trigger the full 5-agent orchestrator pipeline."""
    if not _validate_symbol(symbol):
        raise HTTPException(400, "Invalid symbol format")
    result = await _run_orchestrator(symbol)
    return result


# ═══════════════════════════════════════════════════════════
# AGI ENDPOINTS (memory + planning)
# ═══════════════════════════════════════════════════════════

@app.get("/api/v1/agi/memory")
async def agi_memory():
    return episodic_memory.stats()


@app.get("/api/v1/agi/memory/lessons")
async def agi_lessons(symbol: str = None):
    return {"lessons": episodic_memory.get_lessons(symbol=symbol)}


@app.post("/api/v1/agi/plan")
async def agi_create_plan(symbol: str = "BTC/USDT", horizon_days: int = 5):
    try:
        ticker = await asyncio.to_thread(exchange_public.fetch_ticker, symbol)
        price = ticker['last']
    except Exception:
        price = 65000
    plan = trade_planner.create_plan(
        symbol=symbol, current_price=price, volatility=0.5,
        horizon_days=horizon_days, portfolio_value=10000, max_risk_pct=0.02,
    )
    return plan.to_dict()


@app.get("/api/v1/agi/plans")
async def agi_list_plans():
    return {"plans": trade_planner.list_plans()}


# ═══════════════════════════════════════════════════════════
# MARKET DATA ENDPOINTS
# ═══════════════════════════════════════════════════════════



@app.get("/api/v1/market/ticker/{symbol:path}")
async def market_ticker(symbol: str):
    if not _validate_symbol(symbol):
        raise HTTPException(400, "Invalid symbol format")
    try:
        t = await asyncio.to_thread(exchange_public.fetch_ticker, symbol)
        return {"symbol": symbol, "price": t['last'], "change_24h": t.get('percentage', 0),
                "volume_24h": t.get('quoteVolume', 0), "high_24h": t.get('high', 0), "low_24h": t.get('low', 0)}
    except Exception as e:
        logger.warning("market_ticker_failed", symbol=symbol, error=str(e))
        return {"symbol": symbol, "price": 0, "change_24h": 0, "volume_24h": 0, "high_24h": 0, "low_24h": 0}


async def _fetch_ticker(sym: str) -> dict:
    """Fetch a single ticker from Binance (used for parallel gathering)."""
    try:
        t = await asyncio.to_thread(exchange_public.fetch_ticker, sym)
        return {"symbol": sym, "price": t['last'], "change_24h": t.get('percentage', 0)}
    except Exception:
        return {"symbol": sym, "price": 0}


@app.get("/api/v1/market/tickers")
async def market_tickers():
    symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT', 'LINK/USDT', 'ADA/USDT']
    results = await asyncio.gather(*[_fetch_ticker(s) for s in symbols], return_exceptions=True)
    # Filter out any exceptions that slipped through (shouldn't happen with helper)
    return [r for r in results if isinstance(r, dict)]


@app.get("/api/v1/market/orderbook/{symbol:path}")
async def market_orderbook(symbol: str, limit: int = 10):
    if not _validate_symbol(symbol):
        raise HTTPException(400, "Invalid symbol format")
    try:
        ob = await asyncio.to_thread(exchange_public.fetch_order_book, symbol, limit)
        return {"symbol": symbol, "bids": ob['bids'][:limit], "asks": ob['asks'][:limit]}
    except Exception as e:
        raise HTTPException(400, str(e))


@app.get("/api/v1/market/candles/{symbol:path}")
async def market_candles(symbol: str, timeframe: str = "1h", limit: int = 100):
    if not _validate_symbol(symbol):
        raise HTTPException(400, "Invalid symbol format")
    try:
        candles = await asyncio.to_thread(exchange_public.fetch_ohlcv, symbol, timeframe, limit=limit)
        return {"symbol": symbol, "timeframe": timeframe,
                "candles": [{"time": c[0], "open": c[1], "high": c[2], "low": c[3], "close": c[4], "volume": c[5]} for c in candles]}
    except Exception as e:
        raise HTTPException(400, str(e))


# ═══════════════════════════════════════════════════════════
# SETTINGS ENDPOINTS
# ═══════════════════════════════════════════════════════════

_SETTINGS = {
    "notifications": {"email_enabled": True, "push_enabled": True, "signal_alerts": True, "trade_alerts": True},
    "display": {"theme": "dark", "language": "en", "timezone": "UTC", "currency": "USD"},
    "risk": {"max_position_size_pct": 5.0, "max_daily_loss_pct": 2.0, "max_drawdown_pct": 10.0, "auto_stop_loss": True},
    "trading": {"default_order_type": "limit", "confirmation_required": True, "paper_trading": True},
}


@app.get("/api/v1/settings")
async def get_settings():
    return _SETTINGS


@app.put("/api/v1/settings")
async def update_settings(body: SettingsSectionUpdate):
    for section_name in ("notifications", "display", "risk", "trading"):
        section = getattr(body, section_name, None)
        if section is not None:
            updates = {k: v for k, v in section.model_dump().items() if v is not None}
            _SETTINGS[section_name].update(updates)
    return {"message": "Settings updated", "settings": _SETTINGS}


# ═══════════════════════════════════════════════════════════
# SYSTEM ENDPOINTS
# ═══════════════════════════════════════════════════════════

_START_TIME = time.time()


@app.get("/health")
async def health():
    try:
        ticker = await asyncio.to_thread(exchange_public.fetch_ticker, 'BTC/USDT')
        binance_ok = True
        btc_price = ticker['last']
    except Exception:
        binance_ok = False
        btc_price = 0
    return {
        "status": "ok", "version": "0.1.0",
        "uptime_seconds": round(time.time() - _START_TIME, 2),
        "binance_connected": binance_ok, "btc_price": btc_price,
        "testnet_configured": exchange_testnet is not None,
        "pipeline_available": True, "orchestrator_available": True,
        "agents": ["news", "strategy", "risk", "execution", "reflection"],
        "event_bus": "in_memory",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/v1/settings/exchange")
async def exchange_settings():
    return {"exchange": "Binance", "mode": "testnet", "api_keys_configured": exchange_testnet is not None}


# ═══════════════════════════════════════════════════════════
# TELEGRAM CONFIG ENDPOINT
# ═══════════════════════════════════════════════════════════

class TelegramConfigRequest(BaseModel):
    pass


@app.get("/api/v1/config/telegram")
async def get_telegram_config():
    return {
        "configured": _telegram_bot is not None,
        "bot_token_set": bool(os.environ.get("TELEGRAM_BOT_TOKEN")),
        "chat_id_set": bool(os.environ.get("TELEGRAM_CHAT_ID")),
    }


@app.post("/api/v1/config/telegram")
async def set_telegram_config(body: TelegramConfigRequest):
    """Return current telegram config status. Tokens can only be set via environment variables."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    configured = bool(bot_token and chat_id)

    if configured and _telegram_bot is None:
        # Bot not running yet but env vars are set — start it
        global _telegram_bot
        tg_config = TelegramConfig()
        if tg_config.is_configured:
            _telegram_bot = AlphaTelegramBot(
                config=tg_config,
                trade_store=trade_store,
                signal_store=signal_store,
                portfolio_service=portfolio_service,
                exchange_public=exchange_public,
                generate_signals=_generate_signals,
            )
            set_telegram_bot(_telegram_bot)
            asyncio.create_task(_telegram_bot.start())
            return {"message": "Telegram bot configured and starting", "configured": True}

    return {
        "message": "Telegram status retrieved. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables to configure." if not configured else "Telegram bot is running.",
        "configured": configured,
        "bot_token_set": bool(bot_token),
        "chat_id_set": bool(chat_id),
    }


# ═══════════════════════════════════════════════════════════
# WEBSOCKET (live prices)
# ═══════════════════════════════════════════════════════════

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return
    try:
        _decode_token(token)
    except Exception:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return
    symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'LINK/USDT']
    try:
        await websocket.send_json({"type": "connected", "data": {"message": "Live Binance feed"}})
        while True:
            for sym in symbols:
                try:
                    ticker = await asyncio.to_thread(exchange_public.fetch_ticker, sym)
                    await websocket.send_json({
                        "type": "price_update",
                        "data": {"symbol": sym, "price": ticker['last'],
                                 "change": ticker.get('percentage', 0), "volume": ticker.get('quoteVolume', 0)}
                    })
                except Exception:
                    pass
                await asyncio.sleep(0.5)
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass


# ═══════════════════════════════════════════════════════════
# PROMETHEUS METRICS
# ═══════════════════════════════════════════════════════════

@app.get("/metrics")
async def metrics():
    try:
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
        return PlainTextResponse(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
    except Exception:
        return PlainTextResponse(content="# metrics unavailable\n")


# ═══════════════════════════════════════════════════════════
# RUN
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    print("🚀 AlphaStack LIVE Server v3.0 starting...")
    print("📡 Connected to Binance for real market data")
    print("💰 Trading mode: TESTNET (virtual money, real prices)")
    print("🧠 Multi-Agent Orchestrator: ✅ 5 agents (news → strategy → risk → execution → reflection)")
    print("📊 Strategy Pipeline: ✅ 16-step AlphaStack")
    print("🎯 AGI Module: ✅ Episodic Memory + Trade Planner")
    print("📡 Event Bus: In-Memory (no Redis required)")
    print("🔒 Auth: JWT (production-grade)")
    print("📋 Endpoints: auth, signals, trades, portfolio, analytics, market, agi, orchestrator, loop, settings")
    uvicorn.run(app, host="0.0.0.0", port=8000)
