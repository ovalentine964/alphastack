"""Model routing layer — tiered LLM routing for AlphaStack agents.

Routes agent requests to the optimal model based on:
  - Task complexity (simple classification vs deep reasoning)
  - Latency requirement (<500ms vs <10s acceptable)
  - Cache hit probability (system prompts, repeated context)
  - Stakes (execution vs journaling)
  - Language requirements (African languages → Qwen3)

Cost tracking per agent per call with latency monitoring.
Fallback chain: primary → secondary → local.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from alphastack.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Model tiers
# ---------------------------------------------------------------------------

class ModelTier(str, Enum):
    """Model quality tiers ordered by capability (ascending)."""
    FLASH = "flash"          # DeepSeek V4-Flash — cheap, fast, cache-optimized
    STANDARD = "standard"    # GPT-5.6 Terra / Gemini 3.5 Flash — balanced
    REASONING = "reasoning"  # Claude Sonnet 5 — complex reasoning, high-stakes
    LOCAL = "local"          # Qwen3 self-hosted / Bonsai 27B — zero cost


class TaskComplexity(str, Enum):
    """Estimated task complexity for routing decisions."""
    TRIVIAL = "trivial"      # simple classification, keyword extraction
    SIMPLE = "simple"        # sentiment scoring, indicator interpretation
    MODERATE = "moderate"    # multi-factor analysis, confluence scoring
    COMPLEX = "complex"      # fundamental reasoning, multi-step planning
    CRITICAL = "critical"    # execution decisions, risk assessment


class LatencyRequirement(str, Enum):
    """Latency SLA for the request."""
    REALTIME = "realtime"    # <500ms — execution, risk checks
    FAST = "fast"            # <2s   — signal generation, classification
    NORMAL = "normal"        # <10s  — analysis, planning
    RELAXED = "relaxed"      # <30s  — journaling, reflection


# ---------------------------------------------------------------------------
# Model config
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ModelConfig:
    """Configuration for a single model endpoint."""
    tier: ModelTier
    name: str
    provider: str
    base_url: str
    model_id: str
    cost_per_mtok_input: float    # $/MTok (standard)
    cost_per_mtok_output: float   # $/MTok
    cost_per_mtok_cached: float   # $/MTok (cache hit)
    avg_latency_ms: float         # observed average latency
    max_concurrency: int          # max parallel requests
    supports_cache: bool = True   # provider supports context caching
    languages: list[str] = field(default_factory=lambda: ["en"])


# Default model registry — matches IMPLEMENTATION_TECH_STACK.md
DEFAULT_MODELS: dict[ModelTier, ModelConfig] = {
    ModelTier.FLASH: ModelConfig(
        tier=ModelTier.FLASH,
        name="DeepSeek V4-Flash",
        provider="deepseek",
        base_url="https://api.deepseek.com/v1",
        model_id="deepseek-v4-flash",
        cost_per_mtok_input=0.14,
        cost_per_mtok_output=0.28,
        cost_per_mtok_cached=0.0028,
        avg_latency_ms=800,
        max_concurrency=2500,
        supports_cache=True,
        languages=["en", "zh", "sw", "ha", "yo", "am"],
    ),
    ModelTier.STANDARD: ModelConfig(
        tier=ModelTier.STANDARD,
        name="GPT-5.6 Terra",
        provider="openai",
        base_url="https://api.openai.com/v1",
        model_id="gpt-5.6-terra",
        cost_per_mtok_input=0.50,
        cost_per_mtok_output=1.50,
        cost_per_mtok_cached=0.50,
        avg_latency_ms=1500,
        max_concurrency=500,
        supports_cache=False,
        languages=["en", "zh", "sw", "ha"],
    ),
    ModelTier.REASONING: ModelConfig(
        tier=ModelTier.REASONING,
        name="Claude Sonnet 5",
        provider="anthropic",
        base_url="https://api.anthropic.com/v1",
        model_id="claude-sonnet-5-20260715",
        cost_per_mtok_input=2.00,
        cost_per_mtok_output=10.00,
        cost_per_mtok_cached=2.00,
        avg_latency_ms=2000,
        max_concurrency=200,
        supports_cache=False,
        languages=["en", "zh", "fr", "sw", "ha", "yo", "am"],
    ),
    ModelTier.LOCAL: ModelConfig(
        tier=ModelTier.LOCAL,
        name="Qwen3 (self-hosted)",
        provider="local",
        base_url="http://localhost:11434/v1",
        model_id="qwen3-72b",
        cost_per_mtok_input=0.0,
        cost_per_mtok_output=0.0,
        cost_per_mtok_cached=0.0,
        avg_latency_ms=1500,
        max_concurrency=4,
        supports_cache=False,
        languages=[],  # supports 119 languages
    ),
}


# ---------------------------------------------------------------------------
# Agent routing profiles
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AgentRoutingProfile:
    """Defines routing preferences for a specific agent role."""
    agent_name: str
    primary_tier: ModelTier
    fallback_tier: ModelTier
    default_complexity: TaskComplexity
    default_latency: LatencyRequirement
    budget_per_call_usd: float = 0.05  # max cost per single call
    prefer_cache: bool = True
    african_language_override: bool = False  # route to Qwen3 for African langs


# Default agent profiles — matches IMPLEMENTATION_TECH_STACK.md Section 1.1
DEFAULT_AGENT_PROFILES: dict[str, AgentRoutingProfile] = {
    "news": AgentRoutingProfile(
        agent_name="news",
        primary_tier=ModelTier.FLASH,
        fallback_tier=ModelTier.REASONING,
        default_complexity=TaskComplexity.SIMPLE,
        default_latency=LatencyRequirement.FAST,
        budget_per_call_usd=0.02,
        prefer_cache=True,
    ),
    "strategy": AgentRoutingProfile(
        agent_name="strategy",
        primary_tier=ModelTier.REASONING,
        fallback_tier=ModelTier.STANDARD,
        default_complexity=TaskComplexity.COMPLEX,
        default_latency=LatencyRequirement.NORMAL,
        budget_per_call_usd=0.15,
        prefer_cache=False,
    ),
    "risk": AgentRoutingProfile(
        agent_name="risk",
        primary_tier=ModelTier.FLASH,
        fallback_tier=ModelTier.LOCAL,
        default_complexity=TaskComplexity.MODERATE,
        default_latency=LatencyRequirement.REALTIME,
        budget_per_call_usd=0.01,
        prefer_cache=True,
    ),
    "execution": AgentRoutingProfile(
        agent_name="execution",
        primary_tier=ModelTier.FLASH,
        fallback_tier=ModelTier.FLASH,  # deterministic fallback
        default_complexity=TaskComplexity.TRIVIAL,
        default_latency=LatencyRequirement.REALTIME,
        budget_per_call_usd=0.005,
        prefer_cache=True,
    ),
    "journal": AgentRoutingProfile(
        agent_name="journal",
        primary_tier=ModelTier.FLASH,
        fallback_tier=ModelTier.LOCAL,
        default_complexity=TaskComplexity.TRIVIAL,
        default_latency=LatencyRequirement.RELAXED,
        budget_per_call_usd=0.01,
        prefer_cache=True,
    ),
    "auditor": AgentRoutingProfile(
        agent_name="auditor",
        primary_tier=ModelTier.REASONING,
        fallback_tier=ModelTier.STANDARD,
        default_complexity=TaskComplexity.COMPLEX,
        default_latency=LatencyRequirement.RELAXED,
        budget_per_call_usd=0.20,
        prefer_cache=False,
    ),
    "fundamental": AgentRoutingProfile(
        agent_name="fundamental",
        primary_tier=ModelTier.REASONING,
        fallback_tier=ModelTier.FLASH,
        default_complexity=TaskComplexity.COMPLEX,
        default_latency=LatencyRequirement.NORMAL,
        budget_per_call_usd=0.10,
        prefer_cache=False,
    ),
}


# ---------------------------------------------------------------------------
# Cost tracking
# ---------------------------------------------------------------------------

@dataclass
class CostRecord:
    """A single cost event from an LLM call."""
    agent_name: str
    model_tier: ModelTier
    model_name: str
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    cost_usd: float
    latency_ms: float
    timestamp: float = field(default_factory=time.time)
    cache_hit: bool = False
    fallback_used: bool = False


class CostTracker:
    """Tracks per-agent, per-model cost and latency metrics.

    Thread-safe for concurrent agent usage.
    """

    def __init__(self) -> None:
        self._records: list[CostRecord] = []
        self._lock = asyncio.Lock()
        # Running aggregates for fast lookups
        self._total_cost_by_agent: dict[str, float] = defaultdict(float)
        self._total_cost_by_tier: dict[ModelTier, float] = defaultdict(float)
        self._call_count_by_agent: dict[str, int] = defaultdict(int)
        self._latency_sum_by_tier: dict[ModelTier, float] = defaultdict(float)
        self._latency_count_by_tier: dict[ModelTier, int] = defaultdict(int)
        self._cache_hit_count: int = 0
        self._total_calls: int = 0

    async def record(self, rec: CostRecord) -> None:
        """Record a cost event."""
        async with self._lock:
            self._records.append(rec)
            self._total_cost_by_agent[rec.agent_name] += rec.cost_usd
            self._total_cost_by_tier[rec.model_tier] += rec.cost_usd
            self._call_count_by_agent[rec.agent_name] += 1
            self._latency_sum_by_tier[rec.model_tier] += rec.latency_ms
            self._latency_count_by_tier[rec.model_tier] += 1
            if rec.cache_hit:
                self._cache_hit_count += 1
            self._total_calls += 1

    def get_agent_cost(self, agent_name: str) -> float:
        """Total USD spent by an agent."""
        return self._total_cost_by_agent.get(agent_name, 0.0)

    def get_agent_calls(self, agent_name: str) -> int:
        """Total calls made by an agent."""
        return self._call_count_by_agent.get(agent_name, 0)

    def get_tier_cost(self, tier: ModelTier) -> float:
        """Total USD spent on a model tier."""
        return self._total_cost_by_tier.get(tier, 0.0)

    def get_avg_latency(self, tier: ModelTier) -> float:
        """Average latency (ms) for a model tier."""
        count = self._latency_count_by_tier.get(tier, 0)
        if count == 0:
            return 0.0
        return self._latency_sum_by_tier[tier] / count

    def get_cache_hit_rate(self) -> float:
        """Overall cache hit rate (0.0–1.0)."""
        if self._total_calls == 0:
            return 0.0
        return self._cache_hit_count / self._total_calls

    def get_total_cost(self) -> float:
        """Total USD spent across all agents."""
        return sum(self._total_cost_by_agent.values())

    def get_summary(self) -> dict[str, Any]:
        """Full cost/latency summary."""
        return {
            "total_cost_usd": round(self.get_total_cost(), 6),
            "total_calls": self._total_calls,
            "cache_hit_rate": round(self.get_cache_hit_rate(), 4),
            "cost_by_agent": {k: round(v, 6) for k, v in self._total_cost_by_agent.items()},
            "cost_by_tier": {k.value: round(v, 6) for k, v in self._total_cost_by_tier.items()},
            "avg_latency_by_tier_ms": {
                k.value: round(self.get_avg_latency(k), 1)
                for k in ModelTier
                if self._latency_count_by_tier.get(k, 0) > 0
            },
        }

    def get_records(
        self,
        agent_name: str | None = None,
        since: float | None = None,
        limit: int = 100,
    ) -> list[CostRecord]:
        """Retrieve cost records with optional filters."""
        records = self._records
        if agent_name:
            records = [r for r in records if r.agent_name == agent_name]
        if since:
            records = [r for r in records if r.timestamp >= since]
        return records[-limit:]


# ---------------------------------------------------------------------------
# Token budget manager
# ---------------------------------------------------------------------------

class TokenBudgetManager:
    """Per-agent token budget management.

    Enforces daily and per-call token limits to prevent cost overruns.
    """

    def __init__(
        self,
        daily_budget_usd: float = 5.0,
        per_call_budget_usd: float = 0.20,
    ) -> None:
        self._daily_budget = daily_budget_usd
        self._per_call_budget = per_call_budget_usd
        self._daily_spent: dict[str, float] = defaultdict(float)  # agent → USD
        self._day_start: float = time.time()

    def check_budget(self, agent_name: str, estimated_cost: float) -> bool:
        """Return True if the call is within budget."""
        self._maybe_reset_day()
        if estimated_cost > self._per_call_budget:
            logger.warning(
                "budget.per_call_exceeded",
                agent=agent_name,
                estimated=estimated_cost,
                limit=self._per_call_budget,
            )
            return False
        if self._daily_spent[agent_name] + estimated_cost > self._daily_budget:
            logger.warning(
                "budget.daily_exceeded",
                agent=agent_name,
                spent=self._daily_spent[agent_name],
                estimated=estimated_cost,
                limit=self._daily_budget,
            )
            return False
        return True

    def record_spend(self, agent_name: str, cost_usd: float) -> None:
        """Record actual spend against the budget."""
        self._maybe_reset_day()
        self._daily_spent[agent_name] += cost_usd

    def get_remaining(self, agent_name: str) -> float:
        """Remaining daily budget for an agent."""
        self._maybe_reset_day()
        return max(0.0, self._daily_budget - self._daily_spent[agent_name])

    def _maybe_reset_day(self) -> None:
        """Reset daily counters if a new day has started."""
        now = time.time()
        if now - self._day_start > 86400:
            self._daily_spent.clear()
            self._day_start = now


# ---------------------------------------------------------------------------
# Model Router
# ---------------------------------------------------------------------------

class ModelRouter:
    """Intelligent model routing for AlphaStack agents.

    Routes requests to the optimal LLM based on task complexity, latency,
    cost budget, and cache dynamics. Tracks costs per agent per call.

    Usage::

        router = ModelRouter()
        config = router.route("strategy", complexity=TaskComplexity.COMPLEX)
        # → ModelConfig for Claude Sonnet 5

        # After the call:
        router.record_cost("strategy", config, input_tokens=1200, output_tokens=800, ...)
    """

    def __init__(
        self,
        models: dict[ModelTier, ModelConfig] | None = None,
        agent_profiles: dict[str, AgentRoutingProfile] | None = None,
        cost_tracker: CostTracker | None = None,
        budget_manager: TokenBudgetManager | None = None,
    ) -> None:
        self._models = models or DEFAULT_MODELS
        self._profiles = agent_profiles or DEFAULT_AGENT_PROFILES
        self._cost_tracker = cost_tracker or CostTracker()
        self._budget = budget_manager or TokenBudgetManager()

        # Latency observations for adaptive routing
        self._latency_samples: dict[ModelTier, list[float]] = defaultdict(list)
        self._max_samples = 100

        logger.info(
            "model_router.init",
            models=list(self._models.keys()),
            agents=list(self._profiles.keys()),
        )

    # -- public API --

    def route(
        self,
        agent_name: str,
        complexity: TaskComplexity | None = None,
        latency: LatencyRequirement | None = None,
        language: str | None = None,
        estimated_input_tokens: int = 0,
        force_tier: ModelTier | None = None,
    ) -> ModelConfig:
        """Select the optimal model for an agent's request.

        Args:
            agent_name: Agent role (news, strategy, risk, etc.)
            complexity: Task complexity override (uses profile default if None)
            latency: Latency requirement override
            language: Target language code (triggers African language override)
            estimated_input_tokens: For cost estimation
            force_tier: Bypass routing and use a specific tier

        Returns:
            ModelConfig for the selected model.

        Raises:
            ValueError: If agent_name has no registered profile.
        """
        if force_tier:
            return self._models[force_tier]

        profile = self._profiles.get(agent_name)
        if profile is None:
            # Unknown agent — use flash tier as safe default
            logger.warning("model_router.unknown_agent", agent=agent_name)
            return self._models[ModelTier.FLASH]

        complexity = complexity or profile.default_complexity
        latency = latency or profile.default_latency

        # African language override → route to local Qwen3
        if profile.african_language_override and language:
            african_langs = {"sw", "ha", "yo", "am", "zu", "ig", "sn"}
            if language.lower() in african_langs:
                logger.info(
                    "model_router.african_language_override",
                    agent=agent_name,
                    language=language,
                )
                return self._models[ModelTier.LOCAL]

        # Estimate cost for budget check
        if estimated_input_tokens > 0:
            primary = self._models[profile.primary_tier]
            est_cost = self._estimate_cost(primary, estimated_input_tokens)
            if not self._budget.check_budget(agent_name, est_cost):
                # Try cheaper tier
                cheaper = self._find_cheaper_tier(profile.primary_tier)
                if cheaper:
                    logger.info(
                        "model_router.budget_downgrade",
                        agent=agent_name,
                        from_tier=profile.primary_tier.value,
                        to_tier=cheaper.value,
                    )
                    return self._models[cheaper]

        # Select tier based on complexity + latency
        selected_tier = self._select_tier(profile, complexity, latency)
        return self._models[selected_tier]

    def route_with_fallback(
        self,
        agent_name: str,
        **kwargs: Any,
    ) -> list[ModelConfig]:
        """Return ordered list of models to try (primary → fallback → local).

        The caller should try each model in order until one succeeds.
        """
        primary = self.route(agent_name, **kwargs)
        profile = self._profiles.get(agent_name)

        chain = [primary]

        if profile:
            # Add fallback if different from primary
            fallback = self._models.get(profile.fallback_tier)
            if fallback and fallback.tier != primary.tier:
                chain.append(fallback)

        # Always add local as last resort (if not already in chain)
        local = self._models.get(ModelTier.LOCAL)
        if local and local.tier not in {m.tier for m in chain}:
            chain.append(local)

        return chain

    async def record_cost(
        self,
        agent_name: str,
        model: ModelConfig,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int = 0,
        latency_ms: float = 0.0,
        cache_hit: bool = False,
        fallback_used: bool = False,
    ) -> CostRecord:
        """Record the cost and latency of a completed LLM call."""
        cost = self._compute_cost(model, input_tokens, output_tokens, cached_tokens)

        rec = CostRecord(
            agent_name=agent_name,
            model_tier=model.tier,
            model_name=model.name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            cost_usd=cost,
            latency_ms=latency_ms,
            cache_hit=cache_hit,
            fallback_used=fallback_used,
        )

        await self._cost_tracker.record(rec)
        self._budget.record_spend(agent_name, cost)

        # Track latency for adaptive routing
        self._record_latency(model.tier, latency_ms)

        logger.debug(
            "model_router.cost_recorded",
            agent=agent_name,
            model=model.name,
            cost_usd=round(cost, 6),
            latency_ms=round(latency_ms, 1),
            cache_hit=cache_hit,
        )

        return rec

    def estimate_cost(
        self,
        agent_name: str,
        input_tokens: int,
        output_tokens: int = 500,
        cached_tokens: int = 0,
    ) -> float:
        """Estimate the cost of a call in USD."""
        config = self.route(agent_name, estimated_input_tokens=input_tokens)
        return self._estimate_cost(config, input_tokens, output_tokens, cached_tokens)

    # -- accessors --

    @property
    def cost_tracker(self) -> CostTracker:
        """Access the cost tracker for reporting."""
        return self._cost_tracker

    @property
    def budget(self) -> TokenBudgetManager:
        """Access the budget manager."""
        return self._budget

    def get_cost_summary(self) -> dict[str, Any]:
        """Get full cost/latency summary."""
        return self._cost_tracker.get_summary()

    # -- internal routing logic --

    def _select_tier(
        self,
        profile: AgentRoutingProfile,
        complexity: TaskComplexity,
        latency: LatencyRequirement,
    ) -> ModelTier:
        """Select the best tier given complexity, latency, and profile."""

        # Real-time latency → must use fast model
        if latency == LatencyRequirement.REALTIME:
            if complexity in (TaskComplexity.TRIVIAL, TaskComplexity.SIMPLE):
                return ModelTier.FLASH
            # Moderate+ complexity with realtime SLA → flash (best effort)
            return ModelTier.FLASH

        # Fast latency → flash or standard
        if latency == LatencyRequirement.FAST:
            if complexity in (TaskComplexity.TRIVIAL, TaskComplexity.SIMPLE):
                return ModelTier.FLASH
            return ModelTier.STANDARD

        # Complexity-driven routing for normal/relaxed latency
        complexity_tier_map = {
            TaskComplexity.TRIVIAL: ModelTier.FLASH,
            TaskComplexity.SIMPLE: ModelTier.FLASH,
            TaskComplexity.MODERATE: ModelTier.STANDARD,
            TaskComplexity.COMPLEX: ModelTier.REASONING,
            TaskComplexity.CRITICAL: ModelTier.REASONING,
        }

        selected = complexity_tier_map.get(complexity, profile.primary_tier)

        # Respect profile's primary tier if it's higher than complexity suggests
        tier_order = [ModelTier.FLASH, ModelTier.STANDARD, ModelTier.REASONING]
        if profile.primary_tier in tier_order and selected in tier_order:
            profile_idx = tier_order.index(profile.primary_tier)
            selected_idx = tier_order.index(selected)
            # Don't downgrade below profile's primary for non-trivial tasks
            if complexity not in (TaskComplexity.TRIVIAL, TaskComplexity.SIMPLE):
                selected = tier_order[max(profile_idx, selected_idx)]

        return selected

    def _find_cheaper_tier(self, current: ModelTier) -> ModelTier | None:
        """Find a cheaper tier than the current one."""
        cost_order = [ModelTier.LOCAL, ModelTier.FLASH, ModelTier.STANDARD, ModelTier.REASONING]
        try:
            idx = cost_order.index(current)
            if idx > 0:
                return cost_order[idx - 1]
        except ValueError:
            pass
        return None

    def _record_latency(self, tier: ModelTier, latency_ms: float) -> None:
        """Record latency sample for adaptive routing."""
        samples = self._latency_samples[tier]
        samples.append(latency_ms)
        if len(samples) > self._max_samples:
            self._latency_samples[tier] = samples[-self._max_samples:]

    @staticmethod
    def _compute_cost(
        model: ModelConfig,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int = 0,
    ) -> float:
        """Compute actual USD cost for a call."""
        # Cached tokens use the discounted rate
        uncached_input = max(0, input_tokens - cached_tokens)
        cost = (
            (uncached_input / 1_000_000) * model.cost_per_mtok_input
            + (cached_tokens / 1_000_000) * model.cost_per_mtok_cached
            + (output_tokens / 1_000_000) * model.cost_per_mtok_output
        )
        return cost

    def _estimate_cost(
        self,
        model: ModelConfig,
        input_tokens: int,
        output_tokens: int = 500,
        cached_tokens: int = 0,
    ) -> float:
        """Estimate cost for budget checking."""
        return self._compute_cost(model, input_tokens, output_tokens, cached_tokens)
