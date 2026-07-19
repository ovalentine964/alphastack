"""Smart Order Router – best-execution routing with slippage estimation and fee calculation.

Sits between the strategy/execution layer and the BrokerRegistry, evaluating
each order against cost, fill quality, latency, and reliability metrics to
pick the optimal venue.  Supports:

- Multi-broker best execution
- Slippage estimation (realised + expected)
- Fee/commission calculation per broker
- Spread-adjusted entry/exit pricing
- Failover cascading
- Per-symbol broker affinity (stickiness)
"""

from __future__ import annotations

import asyncio
import datetime as dt
import math
import statistics
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog

from alphastack.brokers.base import BrokerConnector
from alphastack.brokers.forex_utils import FOREX_SYMBOLS, get_symbol, spread_in_pips as fx_spread_in_pips
from alphastack.brokers.models import (
    BrokerBalance,
    BrokerOrder,
    BrokerPosition,
    BrokerTick,
    OrderSide,
    OrderStatus,
    OrderType,
)
from alphastack.brokers.registry import BrokerRegistry

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RoutingStrategy(str, Enum):
    """How the router picks a broker for an order."""

    BEST_PRICE = "best_price"          # Lowest effective cost
    BEST_FILL = "best_fill"            # Highest historical fill rate
    LOWEST_LATENCY = "lowest_latency"  # Fastest execution
    BALANCED = "balanced"              # Weighted composite score
    ROUND_ROBIN = "round_robin"        # Rotate across brokers
    STICKY = "sticky"                  # Prefer the last-used broker per symbol


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class RouterConfig:
    """Tuning knobs for the smart router."""

    strategy: RoutingStrategy = RoutingStrategy.BALANCED

    # Weights for BALANCED strategy (must sum to ~1.0)
    cost_weight: float = 0.40
    fill_weight: float = 0.25
    latency_weight: float = 0.20
    reliability_weight: float = 0.15

    # Constraints
    max_spread_pips: float | None = None       # Reject if spread > N pips
    max_slippage_pct: float = 0.50             # Max acceptable slippage %
    max_latency_ms: float = 5000.0             # Max acceptable latency
    require_connected: bool = True

    # Sticky routing — remembers per-symbol broker affinity
    sticky_ttl_seconds: float = 300.0          # How long affinity lasts

    # Fee awareness
    include_swap_in_cost: bool = True          # Factor swap into cost for forex
    include_commission_in_cost: bool = True    # Factor commission into cost

    # Preferred / excluded brokers
    preferred: list[str] = field(default_factory=list)
    excluded: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Execution quality snapshot
# ---------------------------------------------------------------------------

@dataclass
class ExecutionQuality:
    """Snapshot of a broker's execution quality for a given symbol."""

    broker: str
    symbol: str
    spread: float = 0.0               # Current spread (price units)
    spread_pips: float = 0.0          # Spread in pips (forex)
    spread_pct: float = 0.0           # Spread as % of price
    bid: float = 0.0
    ask: float = 0.0
    mid: float = 0.0
    swap_long: float = 0.0            # Daily swap cost for long
    swap_short: float = 0.0           # Daily swap cost for short
    estimated_slippage: float = 0.0   # Expected slippage (price units)
    estimated_fee: float = 0.0        # Expected total fee (account currency)
    latency_ms: float = 0.0
    fill_rate: float = 0.8            # Historical fill rate (0-1)
    total_score: float = 0.0          # Composite routing score


# ---------------------------------------------------------------------------
# Slippage estimator
# ---------------------------------------------------------------------------

class SlippageEstimator:
    """Estimates expected slippage based on historical fill data and market conditions."""

    def __init__(self, window_size: int = 100) -> None:
        self._window_size = window_size
        # broker → list of (expected_price, actual_fill_price) tuples
        self._history: dict[str, list[tuple[float, float]]] = {}

    def record(self, broker: str, expected_price: float, actual_price: float) -> None:
        """Record an actual fill for slippage calibration."""
        history = self._history.setdefault(broker, [])
        history.append((expected_price, actual_price))
        if len(history) > self._window_size:
            self._history[broker] = history[-self._window_size:]

    def estimate(self, broker: str, price: float, side: OrderSide) -> float:
        """Estimate slippage in price units for the given broker and side.

        Returns the expected adverse price movement (always >= 0).
        For BUY orders slippage pushes price up; for SELL it pushes down.
        """
        history = self._history.get(broker, [])
        if len(history) < 5:
            # Not enough data — use a conservative default: 0.05% of price
            return price * 0.0005

        # Calculate average slippage from recent fills
        slippages: list[float] = []
        for expected, actual in history[-self._window_size:]:
            if expected > 0:
                slippages.append(abs(actual - expected) / expected)

        avg_slippage_pct = statistics.mean(slippages) if slippages else 0.0005
        # Add one standard deviation as safety margin
        if len(slippages) >= 10:
            std = statistics.stdev(slippages)
            avg_slippage_pct += std

        return price * avg_slippage_pct

    def estimate_pct(self, broker: str) -> float:
        """Return the average slippage as a percentage (0-1)."""
        history = self._history.get(broker, [])
        if len(history) < 3:
            return 0.0005  # 0.05% default

        slippages = [
            abs(actual - expected) / expected
            for expected, actual in history[-self._window_size:]
            if expected > 0
        ]
        return statistics.mean(slippages) if slippages else 0.0005


# ---------------------------------------------------------------------------
# Fee calculator
# ---------------------------------------------------------------------------

class FeeCalculator:
    """Calculate total trading cost including spread, commission, and swap."""

    @staticmethod
    def spread_cost(
        spread: float,
        quantity: float,
        contract_size: float = 1.0,
    ) -> float:
        """Cost of crossing the spread.

        For forex: spread × lots × contract_size
        For crypto: spread × quantity
        """
        return spread * quantity * contract_size

    @staticmethod
    def commission_cost(
        commission_per_lot: float,
        quantity: float,
        contract_size: float = 1.0,
    ) -> float:
        """Broker commission cost."""
        if commission_per_lot <= 0:
            return 0.0
        lots = quantity if contract_size <= 1.0 else quantity
        return commission_per_lot * lots

    @staticmethod
    def swap_cost(
        swap_rate: float,
        quantity: float,
        days: int = 1,
        contract_size: float = 1.0,
    ) -> float:
        """Daily swap/rollover cost (negative = cost, positive = credit)."""
        return swap_rate * quantity * days

    @staticmethod
    def total_cost(
        spread: float,
        quantity: float,
        contract_size: float = 1.0,
        commission_per_lot: float = 0.0,
        swap_rate: float = 0.0,
        hold_days: int = 0,
    ) -> float:
        """Total round-trip cost estimate."""
        spread_c = FeeCalculator.spread_cost(spread, quantity, contract_size)
        comm_c = FeeCalculator.commission_cost(commission_per_lot, quantity, contract_size)
        swap_c = FeeCalculator.swap_cost(swap_rate, quantity, hold_days, contract_size)
        return spread_c + comm_c + abs(swap_c)

    @staticmethod
    def effective_entry_price(
        side: OrderSide,
        ask: float,
        bid: float,
        estimated_slippage: float = 0.0,
    ) -> float:
        """Calculate the effective entry price after spread and slippage.

        BUY  → enters at ask + slippage
        SELL → enters at bid - slippage
        """
        if side == OrderSide.BUY:
            return ask + estimated_slippage
        return bid - estimated_slippage

    @staticmethod
    def breakeven_price(
        side: OrderSide,
        entry_price: float,
        spread: float,
        commission_per_unit: float = 0.0,
    ) -> float:
        """Price at which the trade breaks even after costs.

        BUY  → breakeven = entry + spread + commission
        SELL → breakeven = entry - spread - commission
        """
        total_cost = spread + commission_per_unit
        if side == OrderSide.BUY:
            return entry_price + total_cost
        return entry_price - total_cost


# ---------------------------------------------------------------------------
# Smart Order Router
# ---------------------------------------------------------------------------

class SmartOrderRouter:
    """High-level order router with best-execution, slippage estimation, and fee calculation.

    Usage::

        router = SmartOrderRouter(registry)
        await router.start()

        order = BrokerOrder(symbol="BTC/USDT", side=OrderSide.BUY,
                            order_type=OrderType.MARKET, quantity=0.01)
        result = await router.route(order)

        # Check routing quality
        quality = router.last_execution_quality
        print(f"Routed to {quality.broker}, spread={quality.spread_pct:.4%}")

        await router.stop()
    """

    def __init__(
        self,
        registry: BrokerRegistry,
        config: RouterConfig | None = None,
    ) -> None:
        self._registry = registry
        self._config = config or RouterConfig()

        self._slippage = SlippageEstimator()
        self._fees = FeeCalculator()

        # Per-broker metrics (updated after each order)
        self._fill_rates: dict[str, float] = {}    # broker → 0-1
        self._latencies: dict[str, float] = {}     # broker → avg ms
        self._error_counts: dict[str, int] = {}    # broker → cumulative errors
        self._order_counts: dict[str, int] = {}    # broker → cumulative orders

        # Sticky routing state
        self._symbol_affinity: dict[str, str] = {}  # symbol → broker name
        self._affinity_ts: dict[str, float] = {}    # symbol → last used timestamp

        # Round-robin state
        self._rr_index: int = 0

        # Last execution quality (set after each route())
        self.last_execution_quality: ExecutionQuality | None = None

        # Fee schedules per broker (commission per standard lot)
        self._commission_schedule: dict[str, float] = {}

    # -- lifecycle ----------------------------------------------------------

    async def start(self) -> None:
        """Connect all registered brokers."""
        await self._registry.connect_all()

    async def stop(self) -> None:
        """Disconnect all registered brokers."""
        await self._registry.disconnect_all()

    # -- public API ---------------------------------------------------------

    async def route(self, order: BrokerOrder) -> BrokerOrder:
        """Route *order* to the best broker using the configured strategy.

        Returns the order with broker-assigned ID and fill details.
        Raises RuntimeError if no broker can execute the order.
        """
        candidates = await self._score_brokers(order)
        if not candidates:
            raise RuntimeError(
                f"No eligible brokers for {order.symbol} "
                f"(connected: {self._registry.connected_brokers()})"
            )

        last_error: Exception | None = None
        for eq in candidates:
            connector = self._registry.get(eq.broker)
            if connector is None:
                continue

            # Pre-execution slippage check
            if eq.estimated_slippage > 0:
                slippage_pct = eq.estimated_slippage / (order.price or eq.mid or 1.0) * 100
                if slippage_pct > self._config.max_slippage_pct:
                    logger.warning(
                        "router_slippage_exceeded",
                        broker=eq.broker,
                        slippage_pct=slippage_pct,
                        max=self._config.max_slippage_pct,
                    )
                    continue

            # Execute
            t0 = asyncio.get_event_loop().time()
            try:
                order.broker = eq.broker
                result = await connector.place_order(order)
                latency_ms = (asyncio.get_event_loop().time() - t0) * 1000

                # Record metrics
                self._record_success(eq.broker, latency_ms)
                self._slippage.record(
                    eq.broker,
                    order.price or eq.mid,
                    result.avg_fill_price or order.price or eq.mid,
                )
                self._update_symbol_affinity(order.symbol, eq.broker)

                # Compute execution quality
                eq.latency_ms = latency_ms
                eq.estimated_fee = self._fees.total_cost(
                    spread=eq.spread,
                    quantity=order.quantity,
                    commission_per_lot=self._commission_schedule.get(eq.broker, 0.0),
                )
                self.last_execution_quality = eq

                logger.info(
                    "router_order_placed",
                    order_id=order.id,
                    broker=eq.broker,
                    total_score=eq.total_score,
                    spread_pct=eq.spread_pct,
                    latency_ms=round(latency_ms, 1),
                    slippage_est=round(eq.estimated_slippage, 6),
                )
                return result

            except Exception as exc:
                last_error = exc
                self._record_error(eq.broker)
                logger.warning("router_broker_failed", broker=eq.broker, error=str(exc))
                continue

        raise RuntimeError(f"All routing candidates failed: {last_error}")

    async def estimate_cost(
        self,
        order: BrokerOrder,
        broker: str | None = None,
    ) -> ExecutionQuality:
        """Estimate execution cost without placing an order.

        If *broker* is specified, returns the estimate for that broker only.
        Otherwise returns the estimate for the best broker.
        """
        if broker:
            connector = self._registry.get(broker)
            if connector is None or not connector.is_connected:
                raise ValueError(f"Broker {broker} is not available")
            tick = await connector.get_tick(order.symbol)
            return self._build_quality(broker, tick, order)

        candidates = await self._score_brokers(order)
        if not candidates:
            raise RuntimeError("No eligible brokers for cost estimation")
        return candidates[0]

    async def get_all_quotes(self, symbol: str) -> dict[str, BrokerTick]:
        """Fetch current quotes from all connected brokers for *symbol*."""
        quotes: dict[str, BrokerTick] = {}
        tasks: dict[str, asyncio.Task[BrokerTick]] = {}

        for name in self._registry.names:
            connector = self._registry.get(name)
            if connector and connector.is_connected:
                tasks[name] = asyncio.create_task(connector.get_tick(symbol))

        for name, task in tasks.items():
            try:
                quotes[name] = await asyncio.wait_for(task, timeout=5.0)
            except Exception:
                pass

        return quotes

    def set_commission(self, broker: str, per_lot: float) -> None:
        """Set the commission schedule for a broker (per standard lot round-trip)."""
        self._commission_schedule[broker] = per_lot

    # -- scoring internals --------------------------------------------------

    async def _score_brokers(self, order: BrokerOrder) -> list[ExecutionQuality]:
        """Score and rank all eligible brokers for *order*."""
        cfg = self._config
        symbol = order.symbol

        # Strategy-specific short-circuits
        if cfg.strategy == RoutingStrategy.STICKY:
            sticky = self._get_sticky_broker(symbol)
            if sticky:
                connector = self._registry.get(sticky)
                if connector and connector.is_connected:
                    tick = await connector.get_tick(symbol)
                    eq = self._build_quality(sticky, tick, order)
                    return [eq]

        if cfg.strategy == RoutingStrategy.ROUND_ROBIN:
            broker = self._round_robin_next()
            if broker:
                connector = self._registry.get(broker)
                if connector and connector.is_connected:
                    tick = await connector.get_tick(symbol)
                    eq = self._build_quality(broker, tick, order)
                    return [eq]

        # Gather quotes from all connected brokers in parallel
        tick_tasks: dict[str, asyncio.Task[BrokerTick]] = {}
        for name in self._registry.names:
            if cfg.require_connected:
                connector = self._registry.get(name)
                if not connector or not connector.is_connected:
                    continue
            if name in cfg.excluded:
                continue

            connector = self._registry.get(name)
            if connector:
                try:
                    tick_tasks[name] = asyncio.create_task(connector.get_tick(symbol))
                except Exception:
                    pass

        # Collect results with timeout
        ticks: dict[str, BrokerTick] = {}
        for name, task in tick_tasks.items():
            try:
                ticks[name] = await asyncio.wait_for(task, timeout=5.0)
            except Exception:
                pass

        if not ticks:
            return []

        # Build quality scores
        qualities: list[ExecutionQuality] = []
        for name, tick in ticks.items():
            eq = self._build_quality(name, tick, order)
            qualities.append(eq)

        # Normalize and score
        self._normalize_scores(qualities)

        # Apply strategy-specific sorting
        if cfg.strategy == RoutingStrategy.BEST_PRICE:
            qualities.sort(key=lambda q: q.estimated_fee)
        elif cfg.strategy == RoutingStrategy.BEST_FILL:
            qualities.sort(key=lambda q: q.fill_rate, reverse=True)
        elif cfg.strategy == RoutingStrategy.LOWEST_LATENCY:
            qualities.sort(key=lambda q: q.latency_ms)
        else:  # BALANCED
            qualities.sort(key=lambda q: q.total_score, reverse=True)

        # Filter by constraints
        result: list[ExecutionQuality] = []
        for eq in qualities:
            if cfg.max_spread_pips is not None and eq.spread_pips > cfg.max_spread_pips:
                logger.debug(
                    "router_spread_rejected",
                    broker=eq.broker,
                    spread_pips=eq.spread_pips,
                    max=cfg.max_spread_pips,
                )
                continue
            if cfg.max_latency_ms < float("inf") and eq.latency_ms > cfg.max_latency_ms:
                continue
            result.append(eq)

        return result

    def _build_quality(
        self,
        broker: str,
        tick: BrokerTick,
        order: BrokerOrder,
    ) -> ExecutionQuality:
        """Build an ExecutionQuality snapshot for a single broker."""
        mid = tick.mid if tick.mid > 0 else tick.last
        spread_pct = (tick.spread / mid * 100) if mid > 0 else 0.0

        # Estimate slippage
        est_slippage = self._slippage.estimate(broker, mid, order.side)

        # Estimate total fee
        commission = self._commission_schedule.get(broker, 0.0)
        est_fee = self._fees.total_cost(
            spread=tick.spread,
            quantity=order.quantity,
            commission_per_lot=commission,
        )

        # Swap (for forex)
        swap = 0.0
        if self._config.include_swap_in_cost:
            swap_rate = tick.swap_long if order.side == OrderSide.BUY else tick.swap_short
            swap = abs(swap_rate * order.quantity)

        # Compute spread in pips for forex symbols
        spread_pips = 0.0
        if order.symbol in FOREX_SYMBOLS:
            try:
                fx = get_symbol(order.symbol)
                spread_pips = fx_spread_in_pips(tick.spread, fx.pip_size)
            except KeyError:
                spread_pips = 0.0

        # Build quality
        eq = ExecutionQuality(
            broker=broker,
            symbol=order.symbol,
            spread=tick.spread,
            spread_pips=spread_pips,
            spread_pct=spread_pct,
            bid=tick.bid,
            ask=tick.ask,
            mid=mid,
            swap_long=tick.swap_long,
            swap_short=tick.swap_short,
            estimated_slippage=est_slippage,
            estimated_fee=est_fee + swap,
            latency_ms=self._latencies.get(broker, 100.0),
            fill_rate=self._fill_rates.get(broker, 0.8),
        )

        # Composite score (0-1, higher is better)
        cost_score = 1.0 - min(spread_pct / 0.1, 1.0)  # 0.1% spread = score 0
        latency_score = 1.0 - min(eq.latency_ms / 2000.0, 1.0)
        reliability_score = eq.fill_rate

        eq.total_score = (
            self._config.cost_weight * cost_score
            + self._config.fill_weight * eq.fill_rate
            + self._config.latency_weight * latency_score
            + self._config.reliability_weight * reliability_score
        )

        # Preference bonus
        if broker in self._config.preferred:
            eq.total_score = min(1.0, eq.total_score + 0.1)

        return eq

    def _normalize_scores(self, qualities: list[ExecutionQuality]) -> None:
        """Normalize scores relative to the best in each dimension."""
        if len(qualities) <= 1:
            return

        # Normalize cost: lower fee = higher score
        fees = [q.estimated_fee for q in qualities]
        max_fee = max(fees) if fees else 1.0
        for q in qualities:
            if max_fee > 0:
                cost_norm = 1.0 - (q.estimated_fee / max_fee)
            else:
                cost_norm = 1.0
            q.total_score = (
                self._config.cost_weight * cost_norm
                + self._config.fill_weight * q.fill_rate
                + self._config.latency_weight * (1.0 - min(q.latency_ms / 2000.0, 1.0))
                + self._config.reliability_weight * q.fill_rate
            )

    # -- sticky routing -----------------------------------------------------

    def _get_sticky_broker(self, symbol: str) -> str | None:
        """Return the sticky broker for *symbol* if still valid."""
        broker = self._symbol_affinity.get(symbol)
        if not broker:
            return None
        ts = self._affinity_ts.get(symbol, 0.0)
        now = asyncio.get_event_loop().time()
        if now - ts > self._config.sticky_ttl_seconds:
            return None
        return broker

    def _update_symbol_affinity(self, symbol: str, broker: str) -> None:
        """Record that *broker* was used for *symbol*."""
        self._symbol_affinity[symbol] = broker
        self._affinity_ts[symbol] = asyncio.get_event_loop().time()

    # -- round-robin --------------------------------------------------------

    def _round_robin_next(self) -> str | None:
        """Return the next broker in round-robin order."""
        connected = self._registry.connected_brokers()
        if not connected:
            return None
        broker = connected[self._rr_index % len(connected)]
        self._rr_index += 1
        return broker

    # -- metrics tracking ---------------------------------------------------

    def _record_success(self, broker: str, latency_ms: float) -> None:
        self._order_counts[broker] = self._order_counts.get(broker, 0) + 1
        prev_rate = self._fill_rates.get(broker, 0.8)
        self._fill_rates[broker] = prev_rate * 0.9 + 1.0 * 0.1
        prev_lat = self._latencies.get(broker, latency_ms)
        self._latencies[broker] = prev_lat * 0.8 + latency_ms * 0.2

    def _record_error(self, broker: str) -> None:
        self._error_counts[broker] = self._error_counts.get(broker, 0) + 1
        self._order_counts[broker] = self._order_counts.get(broker, 0) + 1
        prev_rate = self._fill_rates.get(broker, 0.8)
        self._fill_rates[broker] = prev_rate * 0.9 + 0.0 * 0.1

    # -- diagnostics --------------------------------------------------------

    def metrics(self) -> dict[str, Any]:
        """Return current routing metrics for diagnostics."""
        result: dict[str, Any] = {}
        for name in self._registry.names:
            result[name] = {
                "fill_rate": round(self._fill_rates.get(name, 0.0), 3),
                "avg_latency_ms": round(self._latencies.get(name, 0.0), 1),
                "error_count": self._error_counts.get(name, 0),
                "order_count": self._order_counts.get(name, 0),
                "slippage_pct": round(self._slippage.estimate_pct(name) * 100, 4),
                "commission_per_lot": self._commission_schedule.get(name, 0.0),
            }
        return result

    def symbol_affinity(self) -> dict[str, str]:
        """Return current per-symbol broker affinity."""
        return dict(self._symbol_affinity)
