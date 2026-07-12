"""Smart Order Router – route orders to the best available broker.

Evaluates cost, fill quality, latency, and reliability to pick the optimal
venue for each order.  Supports failover and (future) arbitrage detection.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from dataclasses import dataclass, field
from typing import Any

import structlog

from alphastack.brokers.base import BrokerConnector
from alphastack.brokers.models import BrokerBalance, BrokerOrder, BrokerTick, OrderSide, OrderType
from alphastack.brokers.order_manager import OrderManager
from alphastack.brokers.registry import BrokerRegistry

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Routing criteria
# ---------------------------------------------------------------------------

@dataclass
class RoutingCriteria:
    """Weights and constraints for smart routing decisions."""

    # Weights (0-1, higher = more important)
    cost_weight: float = 0.4          # Spread / commission
    fill_quality_weight: float = 0.3  # Historical fill rate
    latency_weight: float = 0.2       # Response time
    reliability_weight: float = 0.1   # Uptime / error rate

    # Constraints
    max_spread: float | None = None
    max_slippage_pct: float = 0.5
    require_connected: bool = True
    preferred_brokers: list[str] = field(default_factory=list)
    excluded_brokers: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Broker scorecard
# ---------------------------------------------------------------------------

@dataclass
class BrokerScore:
    """Per-broker scoring for a routing decision."""

    broker: str
    cost_score: float = 0.0       # 0-1, lower spread = higher score
    fill_score: float = 0.0       # 0-1, historical fill rate
    latency_score: float = 0.0    # 0-1, lower latency = higher score
    reliability_score: float = 0.0  # 0-1, uptime
    total_score: float = 0.0
    spread: float = 0.0
    available: bool = True


# ---------------------------------------------------------------------------
# Smart Router
# ---------------------------------------------------------------------------

class SmartRouter:
    """Intelligent order routing across multiple brokers.

    The router sits between the strategy layer and the broker registry,
    evaluating each order against routing criteria to pick the best venue.
    """

    def __init__(
        self,
        registry: BrokerRegistry,
        order_manager: OrderManager,
        criteria: RoutingCriteria | None = None,
    ) -> None:
        self._registry = registry
        self._order_manager = order_manager
        self._criteria = criteria or RoutingCriteria()

        # Per-broker metrics (updated after each order)
        self._fill_rates: dict[str, float] = {}  # broker → 0-1
        self._latencies: dict[str, float] = {}   # broker → avg ms
        self._error_counts: dict[str, int] = {}  # broker → error count
        self._order_counts: dict[str, int] = {}  # broker → total orders

    # -- public API ---------------------------------------------------------

    async def route(self, order: BrokerOrder) -> BrokerOrder:
        """Route *order* to the best broker based on current criteria.

        If the best broker fails, falls back to the next-best.
        """
        candidates = await self._rank_brokers(order)
        if not candidates:
            raise RuntimeError("No eligible brokers for routing")

        last_error: Exception | None = None
        for score in candidates:
            connector = self._registry.get(score.broker)
            if connector is None:
                continue
            try:
                logger.info(
                    "smart_routing",
                    order_id=order.id,
                    broker=score.broker,
                    total_score=score.total_score,
                    spread=score.spread,
                )
                order.broker = score.broker
                result = await connector.place_order(order)
                self._order_manager.register(result)
                self._record_success(score.broker)
                return result
            except Exception as exc:
                last_error = exc
                self._record_error(score.broker)
                logger.warning(
                    "smart_route_failed",
                    broker=score.broker,
                    error=str(exc),
                )
                continue

        raise RuntimeError(f"All routing candidates failed: {last_error}")

    async def route_with_criteria(
        self, order: BrokerOrder, criteria: RoutingCriteria
    ) -> BrokerOrder:
        """Route with ad-hoc criteria (overrides instance defaults)."""
        old = self._criteria
        self._criteria = criteria
        try:
            return await self.route(order)
        finally:
            self._criteria = old

    # -- scoring ------------------------------------------------------------

    async def _rank_brokers(self, order: BrokerOrder) -> list[BrokerScore]:
        """Score and rank all eligible brokers for *order*."""
        scores: list[BrokerScore] = []
        criteria = self._criteria

        # Gather spreads in parallel
        spread_tasks: dict[str, asyncio.Task[BrokerTick]] = {}
        for name in self._registry.names:
            connector = self._registry.get(name)
            if connector is None:
                continue
            if criteria.require_connected and not connector.is_connected:
                continue
            if name in criteria.excluded_brokers:
                continue
            try:
                spread_tasks[name] = asyncio.create_task(connector.get_tick(order.symbol))
            except Exception:
                continue

        # Wait for all tick data (with timeout)
        tick_data: dict[str, BrokerTick] = {}
        for name, task in spread_tasks.items():
            try:
                tick_data[name] = await asyncio.wait_for(task, timeout=5.0)
            except Exception:
                continue

        # Score each broker
        for name, tick in tick_data.items():
            score = BrokerScore(broker=name, spread=tick.spread)

            # Cost score (inverse of spread – lower spread = higher score)
            max_spread = max(t.spread for t in tick_data.values()) or 1.0
            score.cost_score = 1.0 - (tick.spread / max_spread) if max_spread > 0 else 1.0

            # Fill quality score
            score.fill_score = self._fill_rates.get(name, 0.8)  # Default 80%

            # Latency score
            avg_latency = self._latencies.get(name, 100.0)
            max_latency = max(self._latencies.values()) or 200.0
            score.latency_score = 1.0 - (avg_latency / max_latency) if max_latency > 0 else 1.0

            # Reliability score
            total = self._order_counts.get(name, 0)
            errors = self._error_counts.get(name, 0)
            score.reliability_score = 1.0 - (errors / total) if total > 0 else 0.9

            # Preference bonus
            if name in criteria.preferred_brokers:
                score.reliability_score = min(1.0, score.reliability_score + 0.1)

            # Weighted total
            score.total_score = (
                criteria.cost_weight * score.cost_score
                + criteria.fill_quality_weight * score.fill_score
                + criteria.latency_weight * score.latency_score
                + criteria.reliability_weight * score.reliability_score
            )

            # Apply constraints
            if criteria.max_spread and tick.spread > criteria.max_spread:
                score.available = False
                score.total_score = 0.0

            scores.append(score)

        # Sort descending
        scores.sort(key=lambda s: s.total_score, reverse=True)
        return [s for s in scores if s.available]

    # -- metrics tracking ---------------------------------------------------

    def _record_success(self, broker: str) -> None:
        self._order_counts[broker] = self._order_counts.get(broker, 0) + 1
        count = self._order_counts[broker]
        prev_rate = self._fill_rates.get(broker, 0.8)
        # Exponential moving average
        self._fill_rates[broker] = prev_rate * 0.9 + 1.0 * 0.1

    def _record_error(self, broker: str) -> None:
        self._error_counts[broker] = self._error_counts.get(broker, 0) + 1
        self._order_counts[broker] = self._order_counts.get(broker, 0) + 1
        prev_rate = self._fill_rates.get(broker, 0.8)
        self._fill_rates[broker] = prev_rate * 0.9 + 0.0 * 0.1

    def record_latency(self, broker: str, latency_ms: float) -> None:
        """Record a latency measurement for *broker*."""
        prev = self._latencies.get(broker, latency_ms)
        self._latencies[broker] = prev * 0.8 + latency_ms * 0.2

    # -- diagnostics --------------------------------------------------------

    def scores(self, order: BrokerOrder | None = None) -> dict[str, Any]:
        """Return current broker metrics for diagnostics."""
        result: dict[str, Any] = {}
        for name in self._registry.names:
            result[name] = {
                "fill_rate": round(self._fill_rates.get(name, 0.0), 3),
                "avg_latency_ms": round(self._latencies.get(name, 0.0), 1),
                "error_count": self._error_counts.get(name, 0),
                "order_count": self._order_counts.get(name, 0),
                "connected": (self._registry.get(name) or BrokerConnector).__class__.__name__,
            }
        return result
