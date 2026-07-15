"""MiMo 2.5 Pro integration — async AI reasoning engine for AlphaStack.

Provides cached, rate-limited, async access to Xiaomi's MiMo model for:
  - Pre-trade reflection reasoning
  - Bull/Bear debate arguments
  - Post-trade analysis and learning
  - AGI planning and memory consolidation
  - Market analysis explanations
  - Telegram chat responses

Falls back to heuristic reasoning when MiMo is unavailable.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from alphastack.agi.reasoning import (
    ChainOfThoughtEngine,
    ReasoningChain,
    ReasoningStepType,
)
from alphastack.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DEFAULT_BASE_URL = "https://api.xiaomi.com/v1"
_DEFAULT_MODEL = "mimo-v2.5-pro"
_CACHE_TTL_S = 300          # 5 minutes
_RATE_LIMIT_RPS = 10        # max requests per second
_MAX_RETRIES = 2
_TIMEOUT_S = 30.0


# ---------------------------------------------------------------------------
# Cache entry
# ---------------------------------------------------------------------------

@dataclass
class _CacheEntry:
    """A single cached response."""
    response: str
    created_at: float = field(default_factory=time.time)

    @property
    def expired(self) -> bool:
        return (time.time() - self.created_at) > _CACHE_TTL_S


# ---------------------------------------------------------------------------
# Rate limiter (token-bucket)
# ---------------------------------------------------------------------------

class _RateLimiter:
    """Simple async token-bucket rate limiter."""

    def __init__(self, rps: float = _RATE_LIMIT_RPS) -> None:
        self._rps = rps
        self._tokens = rps
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(self._rps, self._tokens + elapsed * self._rps)
            self._last_refill = now

            if self._tokens < 1:
                wait = (1 - self._tokens) / self._rps
                await asyncio.sleep(wait)
                self._tokens = 0
            else:
                self._tokens -= 1


# ---------------------------------------------------------------------------
# MiMoClient
# ---------------------------------------------------------------------------

class MiMoClient:
    """Async client for Xiaomi MiMo 2.5 Pro.

    Reads configuration from environment:
      - ``MIMO_API_KEY``   — required API key
      - ``MIMO_BASE_URL``  — optional, defaults to Xiaomi endpoint
      - ``MIMO_MODEL``     — optional model name override

    Features:
      - Response caching (5 min TTL, same prompt → cached result)
      - Rate limiting (10 req/s)
      - Graceful fallback when MiMo is unavailable
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("MIMO_API_KEY", "")
        self._base_url = (base_url or os.environ.get("MIMO_BASE_URL", _DEFAULT_BASE_URL)).rstrip("/")
        self._model = model or os.environ.get("MIMO_MODEL", _DEFAULT_MODEL)

        self._cache: dict[str, _CacheEntry] = {}
        self._limiter = _RateLimiter()
        self._client: httpx.AsyncClient | None = None

        self._available: bool | None = None  # tri-state: None = untested

    # -- lifecycle --

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                timeout=_TIMEOUT_S,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # -- public API --

    async def reasoning(self, prompt: str) -> str:
        """Chain-of-thought reasoning. Returns the model's response text."""
        system = (
            "You are a quantitative trading reasoning engine. "
            "Think step-by-step through observations, hypotheses, evidence, "
            "and inferences before concluding. Be precise and data-driven."
        )
        return await self._chat(system, prompt)

    async def analyze(self, data: dict[str, Any]) -> str:
        """Market analysis from structured data dict."""
        system = (
            "You are a market analysis engine. Given structured market data, "
            "provide a concise technical and sentiment analysis with actionable insights."
        )
        prompt = json.dumps(data, default=str, ensure_ascii=False)
        return await self._chat(system, prompt)

    async def explain(self, trade: dict[str, Any]) -> str:
        """Explain a trade outcome with lessons learned."""
        system = (
            "You are a trading coach. Explain this trade outcome clearly: "
            "what went right/wrong, root cause, and specific actionable improvements. "
            "Be direct — no filler."
        )
        prompt = json.dumps(trade, default=str, ensure_ascii=False)
        return await self._chat(system, prompt)

    async def chat(self, message: str) -> str:
        """General conversation (e.g. Telegram responses)."""
        system = (
            "You are AlphaStack AI, a quantitative trading assistant. "
            "Be helpful, concise, and knowledgeable about markets and trading."
        )
        return await self._chat(system, message)

    async def is_available(self) -> bool:
        """Check if MiMo API is reachable and configured."""
        if self._available is not None:
            return self._available
        if not self._api_key:
            self._available = False
            return False
        try:
            client = await self._get_client()
            resp = await client.get("/models", timeout=5.0)
            self._available = resp.status_code < 500
        except Exception:
            self._available = False
        return self._available

    # -- internals --

    async def _chat(self, system: str, user: str) -> str:
        """Send a chat completion request with caching and rate limiting."""
        cache_key = self._cache_key(system, user)

        # Check cache
        entry = self._cache.get(cache_key)
        if entry and not entry.expired:
            logger.debug("mimo.cache_hit", key=cache_key[:12])
            return entry.response

        # Check availability
        if not await self.is_available():
            logger.warning("mimo.unavailable", fallback=True)
            return self._fallback(system, user)

        # Rate limit
        await self._limiter.acquire()

        # Call API with retries
        response_text = await self._request_with_retry(system, user)
        if response_text is None:
            return self._fallback(system, user)

        # Cache result
        self._cache[cache_key] = _CacheEntry(response=response_text)
        self._evict_cache()
        return response_text

    async def _request_with_retry(self, system: str, user: str) -> str | None:
        """Make the API call with retry on transient failures."""
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.3,
            "max_tokens": 2048,
        }

        for attempt in range(_MAX_RETRIES + 1):
            try:
                client = await self._get_client()
                resp = await client.post("/chat/completions", json=payload)

                if resp.status_code == 429:
                    retry_after = float(resp.headers.get("Retry-After", "1"))
                    logger.warning("mimo.rate_limited", retry_after=retry_after)
                    await asyncio.sleep(retry_after)
                    continue

                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]

            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                logger.warning("mimo.request_error", attempt=attempt, error=str(exc))
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(1.0 * (attempt + 1))
                else:
                    self._available = False
                    return None

            except Exception as exc:
                logger.error("mimo.unexpected_error", error=str(exc))
                self._available = False
                return None

        return None

    @staticmethod
    def _fallback(system: str, user: str) -> str:
        """Heuristic fallback when MiMo is unavailable."""
        # Simple keyword-based heuristic
        text = user.lower()
        if any(w in text for w in ("bull", "buy", "long", "uptrend")):
            return "[fallback] Bullish signal detected via keyword matching. Technical indicators suggest upward momentum. Consider long entry with tight stop-loss."
        if any(w in text for w in ("bear", "sell", "short", "downtrend")):
            return "[fallback] Bearish signal detected via keyword matching. Technical indicators suggest downward pressure. Consider short entry or reduce exposure."
        if any(w in text for w in ("risk", "stop", "loss")):
            return "[fallback] Risk management check: ensure position size ≤2% of portfolio, stop-loss at 2x ATR, and risk/reward ratio ≥1.5."
        return "[fallback] MiMo unavailable. Using basic heuristic analysis. Enable MIMO_API_KEY for full AI reasoning."

    @staticmethod
    def _cache_key(system: str, user: str) -> str:
        """Deterministic cache key from system+user prompt."""
        raw = f"{system}|||{user}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def _evict_cache(self) -> None:
        """Remove expired cache entries (keeps cache bounded)."""
        if len(self._cache) > 500:
            expired = [k for k, v in self._cache.items() if v.expired]
            for k in expired:
                del self._cache[k]


# ---------------------------------------------------------------------------
# ReasoningEngine — MiMo-powered replacement for ChainOfThoughtEngine
# ---------------------------------------------------------------------------

class ReasoningEngine:
    """MiMo-powered reasoning engine for AlphaStack.

    Wraps MiMoClient to generate structured reasoning chains for:
      - Pre-trade signal reflection
      - Bull/Bear debate arguments
      - Post-trade analysis and learning
      - Market analysis explanations

    Falls back to the built-in ChainOfThoughtEngine when MiMo is unavailable.
    """

    def __init__(self, mimo: MiMoClient | None = None) -> None:
        self._mimo = mimo or MiMoClient()
        self._fallback_engine = ChainOfThoughtEngine()

    @property
    def mimo(self) -> MiMoClient:
        return self._mimo

    # -- Pre-trade reflection --

    async def pre_trade_reflect(
        self,
        signal: dict[str, Any],
        market_data: dict[str, Any],
        indicators: dict[str, float],
        recent_decisions: list[dict[str, Any]] | None = None,
    ) -> str:
        """Generate pre-trade reflection reasoning via MiMo."""
        prompt = (
            f"Evaluate this trading signal for quality gate (APPROVE/REJECT/MODIFY):\n\n"
            f"Signal: {json.dumps(signal, default=str)}\n"
            f"Market Data: {json.dumps(market_data, default=str)}\n"
            f"Indicators: {json.dumps({k: round(v, 6) for k, v in indicators.items()})}\n"
            f"Recent Decisions: {json.dumps(recent_decisions[-5:] if recent_decisions else [], default=str)}\n\n"
            f"Assess: signal strength, confluence, market regime fit, conflict with recent trades.\n"
            f"Return verdict (APPROVE/REJECT/MODIFY), reasoning, and confidence (0-1)."
        )
        return await self._mimo.reasoning(prompt)

    # -- Bull/Bear debate --

    async def bull_argue(
        self,
        signal: dict[str, Any],
        market_data: dict[str, Any],
        indicators: dict[str, float],
        news_sentiment: float | None = None,
        bear_argument: str | None = None,
    ) -> str:
        """Generate bullish argument via MiMo."""
        prompt = (
            f"Build the strongest BULLISH case for this trade:\n\n"
            f"Signal: {json.dumps(signal, default=str)}\n"
            f"Indicators: {json.dumps({k: round(v, 6) for k, v in indicators.items()})}\n"
            f"News Sentiment: {news_sentiment}\n"
        )
        if bear_argument:
            prompt += f"\nBear's argument to counter: {bear_argument}\n"
        prompt += "\nProvide specific technical evidence, risk/reward rationale, and a clear EXECUTE recommendation."
        return await self._mimo.reasoning(prompt)

    async def bear_argue(
        self,
        signal: dict[str, Any],
        market_data: dict[str, Any],
        indicators: dict[str, float],
        news_sentiment: float | None = None,
        bull_argument: str | None = None,
    ) -> str:
        """Generate bearish argument via MiMo."""
        prompt = (
            f"Build the strongest BEARISH case against this trade:\n\n"
            f"Signal: {json.dumps(signal, default=str)}\n"
            f"Indicators: {json.dumps({k: round(v, 6) for k, v in indicators.items()})}\n"
            f"News Sentiment: {news_sentiment}\n"
        )
        if bull_argument:
            prompt += f"\nBull's argument to counter: {bull_argument}\n"
        prompt += "\nProvide specific risk evidence, overbought/overextended signals, and a clear REJECT recommendation."
        return await self._mimo.reasoning(prompt)

    # -- Post-trade analysis --

    async def post_trade_analyze(self, trade: dict[str, Any]) -> str:
        """Generate post-trade reflection and learning via MiMo."""
        return await self._mimo.explain(trade)

    # -- Market analysis --

    async def market_analysis(self, data: dict[str, Any]) -> str:
        """Generate market analysis explanation via MiMo."""
        return await self._mimo.analyze(data)

    # -- AGI planning --

    async def consolidate_memory(self, episodes: list[dict[str, Any]]) -> str:
        """Consolidate trade episodes into actionable memory via MiMo."""
        prompt = (
            f"Review these {len(episodes)} recent trade episodes and extract:\n"
            f"1. Key patterns (wins and losses)\n"
            f"2. Actionable lessons\n"
            f"3. Parameter adjustments to consider\n\n"
            f"Episodes: {json.dumps(episodes[-10:], default=str)}"
        )
        return await self._mimo.reasoning(prompt)

    async def plan_next_actions(
        self,
        portfolio: dict[str, Any],
        market_state: dict[str, Any],
        recent_reflections: list[str],
    ) -> str:
        """AGI planning — determine next strategic actions."""
        prompt = (
            f"Given current portfolio state and market conditions, plan next actions:\n\n"
            f"Portfolio: {json.dumps(portfolio, default=str)}\n"
            f"Market State: {json.dumps(market_state, default=str)}\n"
            f"Recent Reflections: {json.dumps(recent_reflections[-5:])}\n\n"
            f"Provide: prioritized action items, risk adjustments, and strategic rationale."
        )
        return await self._mimo.reasoning(prompt)

    # -- Telegram chat --

    async def chat(self, message: str) -> str:
        """Respond to Telegram chat messages."""
        return await self._mimo.chat(message)

    # -- Fallback bridge to existing ChainOfThoughtEngine --

    def fallback_chain(self, topic: str) -> ReasoningChain:
        """Create a reasoning chain using the built-in engine (no MiMo)."""
        return self._fallback_engine.start_chain(topic)

    def fallback_analyze_signal(
        self,
        symbol: str,
        price_data: dict[str, Any],
        indicators: dict[str, float],
        news_sentiment: float | None = None,
    ) -> ReasoningChain:
        """Analyze a market signal using built-in heuristics (no MiMo)."""
        return self._fallback_engine.analyze_market_signal(
            symbol, price_data, indicators, news_sentiment,
        )

    async def close(self) -> None:
        """Clean up resources."""
        await self._mimo.close()
