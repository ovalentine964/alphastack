"""Model-agnostic AI client for AlphaStack.

Works with ANY OpenAI-compatible API provider:
  - Xiaomi MiMo, NVIDIA API, OpenAI, Anthropic, Google, Fable, Local Ollama
  - Any provider with an OpenAI-compatible /chat/completions endpoint

Provides cached, rate-limited, async access for:
  - Pre-trade reflection reasoning
  - Bull/Bear debate arguments
  - Post-trade analysis and learning
  - AGI planning and memory consolidation
  - Market analysis explanations
  - Telegram chat responses

Falls back to heuristic reasoning when the AI provider is unavailable.
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
# Provider registry
# ---------------------------------------------------------------------------

PROVIDERS: dict[str, dict[str, str]] = {
    "mimo": {
        "name": "Xiaomi MiMo 2.5 Pro",
        "default_base_url": "https://token-plan-sgp.xiaomimimo.com/v1",
        "default_model": "mimo-v2.5-pro",
    },
    "nvidia": {
        "name": "NVIDIA API (any model)",
        "default_base_url": "https://integrate.api.nvidia.com/v1",
        "default_model": "nvidia/llama-3.3-70b-instruct",
    },
    "openai": {
        "name": "OpenAI (GPT-5.6, GPT-4o, etc.)",
        "default_base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o",
    },
    "anthropic": {
        "name": "Anthropic (Claude 4, Claude 3.5)",
        "default_base_url": "https://api.anthropic.com/v1",
        "default_model": "claude-sonnet-4-20250514",
    },
    "fable": {
        "name": "Fable 5",
        "default_base_url": "https://api.fable.ai/v1",
        "default_model": "fable-5",
    },
    "google": {
        "name": "Google Gemini 2.5",
        "default_base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "default_model": "gemini-2.5-flash",
    },
    "local": {
        "name": "Local (Ollama / llama.cpp)",
        "default_base_url": "http://localhost:11434/v1",
        "default_model": "llama3.3:70b",
    },
}

# URL pattern → provider key (checked in order)
_URL_PROVIDER_MAP: list[tuple[str, str]] = [
    ("nvidia.com", "nvidia"),
    ("xiaomi.com", "mimo"),
    ("xiaomimimo.com", "mimo"),
    ("openai.com", "openai"),
    ("anthropic.com", "anthropic"),
    ("fable.ai", "fable"),
    ("googleapis.com", "google"),
    ("localhost", "local"),
    ("127.0.0.1", "local"),
]

# ---------------------------------------------------------------------------
# Configuration defaults
# ---------------------------------------------------------------------------

_DEFAULT_BASE_URL = PROVIDERS["mimo"]["default_base_url"]
_DEFAULT_MODEL = PROVIDERS["mimo"]["default_model"]
_CACHE_TTL_S = 300          # 5 minutes
_RATE_LIMIT_RPS = 10        # max requests per second
_MAX_RETRIES = 3            # increased from 2
_TIMEOUT_S = 30.0
_AVAILABLE_RESET_S = 300    # reset _available flag every 5 minutes


# ---------------------------------------------------------------------------
# Provider auto-detection
# ---------------------------------------------------------------------------

def detect_provider(base_url: str) -> str:
    """Auto-detect provider from base URL.

    Returns provider key (e.g. 'nvidia', 'mimo', 'openai') or 'openai'
    as the generic fallback (since most providers are OpenAI-compatible).

    Detection is < 10 lines of logic — simple substring matching.
    """
    url_lower = base_url.lower()
    for pattern, provider in _URL_PROVIDER_MAP:
        if pattern in url_lower:
            return provider
    return "openai"  # generic OpenAI-compatible fallback


def resolve_config(
    provider: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> tuple[str, str, str, str]:
    """Resolve provider config from args + env vars with backward compatibility.

    Priority order:
      1. Explicit arguments
      2. AI_* environment variables
      3. Legacy MIMO_* environment variables (backward compat)
      4. Provider defaults
      5. Global defaults (MiMo)

    Returns: (provider_key, api_key, base_url, model)
    """
    # --- API key ---
    resolved_key = (
        api_key
        or os.environ.get("AI_API_KEY")
        or os.environ.get("MIMO_API_KEY")  # backward compat
        or ""
    )

    # --- Base URL ---
    resolved_url = (
        base_url
        or os.environ.get("AI_BASE_URL")
        or os.environ.get("MIMO_BASE_URL")  # backward compat
        or ""
    )

    # --- Model ---
    resolved_model = (
        model
        or os.environ.get("AI_MODEL")
        or os.environ.get("MIMO_MODEL")  # backward compat
        or ""
    )

    # --- Provider (auto-detect if not explicit) ---
    resolved_provider = (
        provider
        or os.environ.get("AI_PROVIDER")
        or ""
    )

    if not resolved_provider and resolved_url:
        resolved_provider = detect_provider(resolved_url)
    elif not resolved_provider:
        # No URL, no provider — default to mimo for backward compat
        resolved_provider = "mimo"

    # Apply provider defaults for anything still empty
    prov_cfg = PROVIDERS.get(resolved_provider, PROVIDERS["openai"])
    if not resolved_url:
        resolved_url = prov_cfg["default_base_url"]
    if not resolved_model:
        resolved_model = prov_cfg["default_model"]

    return resolved_provider, resolved_key, resolved_url.rstrip("/"), resolved_model


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
# AlphaModel — model-agnostic AI client
# ---------------------------------------------------------------------------

class AlphaModel:
    """Model-agnostic AI client. Works with any OpenAI-compatible API.

    Auto-detects provider from API base URL or explicit ``AI_PROVIDER`` env.
    Supports: MiMo, NVIDIA, OpenAI, Anthropic, Fable, Google, Local Ollama,
    and any other OpenAI-compatible endpoint.

    Configuration (environment variables):
      - ``AI_PROVIDER``  — provider key (mimo|nvidia|openai|anthropic|fable|google|local)
      - ``AI_API_KEY``   — API key (required)
      - ``AI_BASE_URL``   — API base URL (auto-detected from provider if omitted)
      - ``AI_MODEL``      — model name (provider default if omitted)

    Legacy env vars still work: ``MIMO_API_KEY``, ``MIMO_BASE_URL``, ``MIMO_MODEL``.

    Features:
      - Response caching (5 min TTL)
      - Rate limiting (10 req/s)
      - Automatic retries with exponential backoff
      - Graceful fallback when provider is unavailable
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        provider: str | None = None,
    ) -> None:
        self._provider, self._api_key, self._base_url, self._model = resolve_config(
            provider=provider,
            api_key=api_key,
            base_url=base_url,
            model=model,
        )

        self._cache: dict[str, _CacheEntry] = {}
        self._limiter = _RateLimiter()
        self._client: httpx.AsyncClient | None = None
        self._available: bool | None = None  # tri-state: None = untested
        self._available_set_at: float = 0.0  # when _available was last set

        logger.info(
            "alphamodel.init",
            provider=self._provider,
            base_url=self._base_url,
            model=self._model,
            has_key=bool(self._api_key),
        )

    # -- properties --

    @property
    def provider(self) -> str:
        """Current provider key."""
        return self._provider

    @property
    def model(self) -> str:
        """Current model name."""
        return self._model

    @property
    def base_url(self) -> str:
        """Current API base URL."""
        return self._base_url

    # -- lifecycle --

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers: dict[str, str] = {
                "Content-Type": "application/json",
            }
            # Anthropic uses x-api-key instead of Bearer token
            if self._provider == "anthropic":
                headers["x-api-key"] = self._api_key
                headers["anthropic-version"] = "2023-06-01"
            else:
                headers["Authorization"] = f"Bearer {self._api_key}"

            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers=headers,
                timeout=_TIMEOUT_S,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # -- public API (same interface as MiMoClient) --

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

    async def chat(self, message: str, system: str | None = None) -> str:
        """General conversation (e.g. Telegram responses)."""
        if system is None:
            system = (
                "You are AlphaStack AI, a quantitative trading assistant. "
                "Be helpful, concise, and knowledgeable about markets and trading."
            )
        return await self._chat(system, message)

    async def is_available(self) -> bool:
        """Check if the AI provider is reachable and configured."""
        # Reset availability flag after cooldown period to retry
        if self._available is False and self._available_set_at > 0:
            if (time.time() - self._available_set_at) > _AVAILABLE_RESET_S:
                logger.info("alphamodel.resetting_availability", provider=self._provider)
                self._available = None
                self._available_set_at = 0.0

        if self._available is not None:
            return self._available
        if not self._api_key:
            self._available = False
            self._available_set_at = time.time()
            return False
        try:
            client = await self._get_client()
            # Try /models endpoint (works for most OpenAI-compatible APIs)
            resp = await client.get("/models", timeout=5.0)
            # Reject 401/403 as unavailable (bad key)
            self._available = 200 <= resp.status_code < 500
        except Exception:
            self._available = False
        self._available_set_at = time.time()
        return self._available

    # -- internals --

    async def _chat(self, system: str, user: str) -> str:
        """Send a chat completion request with caching and rate limiting."""
        cache_key = self._cache_key(system, user)

        # Check cache
        entry = self._cache.get(cache_key)
        if entry and not entry.expired:
            logger.debug("alphamodel.cache_hit", key=cache_key[:12])
            return entry.response

        # Check availability
        if not await self.is_available():
            logger.warning("alphamodel.unavailable", provider=self._provider, fallback=True)
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
        """Make the API call with exponential backoff retry."""
        # Anthropic uses a different request format
        if self._provider == "anthropic":
            return await self._request_anthropic(system, user)

        payload: dict[str, Any] = {
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
                    logger.warning("alphamodel.rate_limited", retry_after=retry_after)
                    await asyncio.sleep(retry_after)
                    continue

                resp.raise_for_status()
                data = resp.json()
                # Success — reset availability
                self._available = True
                self._available_set_at = time.time()
                return data["choices"][0]["message"]["content"]

            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                logger.warning(
                    "alphamodel.request_error",
                    provider=self._provider,
                    attempt=attempt,
                    error=str(exc),
                )
                if attempt < _MAX_RETRIES:
                    # Exponential backoff: 1s, 2s, 4s
                    await asyncio.sleep(1.0 * (2 ** attempt))
                else:
                    self._available = False
                    self._available_set_at = time.time()
                    return None

            except Exception as exc:
                logger.error("alphamodel.unexpected_error", error=str(exc))
                self._available = False
                self._available_set_at = time.time()
                return None

        return None

    async def _request_anthropic(self, system: str, user: str) -> str | None:
        """Anthropic Messages API (different format from OpenAI)."""
        payload: dict[str, Any] = {
            "model": self._model,
            "max_tokens": 2048,
            "system": system,
            "messages": [
                {"role": "user", "content": user},
            ],
        }

        for attempt in range(_MAX_RETRIES + 1):
            try:
                client = await self._get_client()
                resp = await client.post("/messages", json=payload)

                if resp.status_code == 429:
                    retry_after = float(resp.headers.get("Retry-After", "1"))
                    logger.warning("alphamodel.anthropic_rate_limited", retry_after=retry_after)
                    await asyncio.sleep(retry_after)
                    continue

                resp.raise_for_status()
                data = resp.json()
                # Success — reset availability
                self._available = True
                self._available_set_at = time.time()
                # Anthropic response: {"content": [{"type": "text", "text": "..."}]}
                return data["content"][0]["text"]

            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                logger.warning(
                    "alphamodel.anthropic_request_error",
                    attempt=attempt,
                    error=str(exc),
                )
                if attempt < _MAX_RETRIES:
                    # Exponential backoff: 1s, 2s, 4s
                    await asyncio.sleep(1.0 * (2 ** attempt))
                else:
                    self._available = False
                    self._available_set_at = time.time()
                    return None

            except Exception as exc:
                logger.error("alphamodel.anthropic_unexpected_error", error=str(exc))
                self._available = False
                self._available_set_at = time.time()
                return None

        return None

    @staticmethod
    def _fallback(system: str, user: str) -> str:
        """Heuristic fallback when AI provider is unavailable."""
        text = user.lower()
        if any(w in text for w in ("bull", "buy", "long", "uptrend")):
            return "[fallback] Bullish signal detected via keyword matching. Technical indicators suggest upward momentum. Consider long entry with tight stop-loss."
        if any(w in text for w in ("bear", "sell", "short", "downtrend")):
            return "[fallback] Bearish signal detected via keyword matching. Technical indicators suggest downward pressure. Consider short entry or reduce exposure."
        if any(w in text for w in ("risk", "stop", "loss")):
            return "[fallback] Risk management check: ensure position size ≤2% of portfolio, stop-loss at 2x ATR, and risk/reward ratio ≥1.5."
        return "[fallback] AI provider unavailable. Using basic heuristic analysis. Configure AI_API_KEY for full AI reasoning."

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
# ReasoningEngine — model-agnostic reasoning for AlphaStack
# ---------------------------------------------------------------------------

class ReasoningEngine:
    """Model-agnostic reasoning engine for AlphaStack.

    Wraps AlphaModel to generate structured reasoning chains for:
      - Pre-trade signal reflection
      - Bull/Bear debate arguments
      - Post-trade analysis and learning
      - Market analysis explanations

    Falls back to the built-in ChainOfThoughtEngine when AI is unavailable.
    """

    def __init__(self, model: AlphaModel | None = None) -> None:
        self._model = model or AlphaModel()
        self._fallback_engine = ChainOfThoughtEngine()

    @property
    def model(self) -> AlphaModel:
        """The underlying AlphaModel client."""
        return self._model

    @property
    def mimo(self) -> AlphaModel:
        """Backward-compatible alias for ``model``."""
        return self._model

    # -- Pre-trade reflection --

    async def pre_trade_reflect(
        self,
        signal: dict[str, Any],
        market_data: dict[str, Any],
        indicators: dict[str, float],
        recent_decisions: list[dict[str, Any]] | None = None,
    ) -> str:
        """Generate pre-trade reflection reasoning via AI model."""
        prompt = (
            f"Evaluate this trading signal for quality gate (APPROVE/REJECT/MODIFY):\n\n"
            f"Signal: {json.dumps(signal, default=str)}\n"
            f"Market Data: {json.dumps(market_data, default=str)}\n"
            f"Indicators: {json.dumps({k: round(v, 6) for k, v in indicators.items()})}\n"
            f"Recent Decisions: {json.dumps(recent_decisions[-5:] if recent_decisions else [], default=str)}\n\n"
            f"Assess: signal strength, confluence, market regime fit, conflict with recent trades.\n"
            f"Return verdict (APPROVE/REJECT/MODIFY), reasoning, and confidence (0-1)."
        )
        return await self._model.reasoning(prompt)

    # -- Bull/Bear debate --

    async def bull_argue(
        self,
        signal: dict[str, Any],
        market_data: dict[str, Any],
        indicators: dict[str, float],
        news_sentiment: float | None = None,
        bear_argument: str | None = None,
    ) -> str:
        """Generate bullish argument via AI model."""
        prompt = (
            f"Build the strongest BULLISH case for this trade:\n\n"
            f"Signal: {json.dumps(signal, default=str)}\n"
            f"Indicators: {json.dumps({k: round(v, 6) for k, v in indicators.items()})}\n"
            f"News Sentiment: {news_sentiment}\n"
        )
        if bear_argument:
            prompt += f"\nBear's argument to counter: {bear_argument}\n"
        prompt += "\nProvide specific technical evidence, risk/reward rationale, and a clear EXECUTE recommendation."
        return await self._model.reasoning(prompt)

    async def bear_argue(
        self,
        signal: dict[str, Any],
        market_data: dict[str, Any],
        indicators: dict[str, float],
        news_sentiment: float | None = None,
        bull_argument: str | None = None,
    ) -> str:
        """Generate bearish argument via AI model."""
        prompt = (
            f"Build the strongest BEARISH case against this trade:\n\n"
            f"Signal: {json.dumps(signal, default=str)}\n"
            f"Indicators: {json.dumps({k: round(v, 6) for k, v in indicators.items()})}\n"
            f"News Sentiment: {news_sentiment}\n"
        )
        if bull_argument:
            prompt += f"\nBull's argument to counter: {bull_argument}\n"
        prompt += "\nProvide specific risk evidence, overbought/overextended signals, and a clear REJECT recommendation."
        return await self._model.reasoning(prompt)

    # -- Post-trade analysis --

    async def post_trade_analyze(self, trade: dict[str, Any]) -> str:
        """Generate post-trade reflection and learning via AI model."""
        return await self._model.explain(trade)

    # -- Market analysis --

    async def market_analysis(self, data: dict[str, Any]) -> str:
        """Generate market analysis explanation via AI model."""
        return await self._model.analyze(data)

    # -- AGI planning --

    async def consolidate_memory(self, episodes: list[dict[str, Any]]) -> str:
        """Consolidate trade episodes into actionable memory via AI model."""
        prompt = (
            f"Review these {len(episodes)} recent trade episodes and extract:\n"
            f"1. Key patterns (wins and losses)\n"
            f"2. Actionable lessons\n"
            f"3. Parameter adjustments to consider\n\n"
            f"Episodes: {json.dumps(episodes[-10:], default=str)}"
        )
        return await self._model.reasoning(prompt)

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
        return await self._model.reasoning(prompt)

    # -- Telegram chat --

    async def chat(self, message: str) -> str:
        """Respond to Telegram chat messages."""
        return await self._model.chat(message)

    # -- Fallback bridge to existing ChainOfThoughtEngine --

    def fallback_chain(self, topic: str) -> ReasoningChain:
        """Create a reasoning chain using the built-in engine (no AI model)."""
        return self._fallback_engine.start_chain(topic)

    def fallback_analyze_signal(
        self,
        symbol: str,
        price_data: dict[str, Any],
        indicators: dict[str, float],
        news_sentiment: float | None = None,
    ) -> ReasoningChain:
        """Analyze a market signal using built-in heuristics (no AI model)."""
        return self._fallback_engine.analyze_market_signal(
            symbol, price_data, indicators, news_sentiment,
        )

    async def close(self) -> None:
        """Clean up resources."""
        await self._model.close()
