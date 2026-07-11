# Alpha Stack — Broker Routing Architecture

> **Document Type:** System Architecture Design
> **Version:** 1.0
> **Date:** 2026-07-11
> **Author:** Broker Routing Architect (Subagent)
> **Status:** Design Complete

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Overview](#2-system-overview)
3. [Broker Scoring Algorithm](#3-broker-scoring-algorithm)
4. [Best Execution Routing](#4-best-execution-routing)
5. [Failover Routing](#5-failover-routing)
6. [Cross-Broker Arbitrage Detection](#6-cross-broker-arbitrage-detection)
7. [Order Splitting Across Brokers](#7-order-splitting-across-brokers)
8. [Latency-Based Routing](#8-latency-based-routing)
9. [Cost-Based Routing](#9-cost-based-routing)
10. [Load Balancing](#10-load-balancing)
11. [Route Logging & Analytics](#11-route-logging--analytics)
12. [Integration with Broker Connectors](#12-integration-with-broker-connectors)
13. [Data Flow & Sequence Diagrams](#13-data-flow--sequence-diagrams)
14. [Configuration Reference](#14-configuration-reference)

---

## 1. Executive Summary

The Broker Routing Engine (BRE) is the intelligent core of Alpha Stack's execution layer. It determines **which broker(s)** receive each order, **how orders are split**, and **when to failover** — all in real-time with sub-millisecond decision latency.

**Design Principles:**
- **Best execution first** — minimize total cost (spread + fees + slippage + market impact)
- **Resilience by default** — no single point of failure; every order has a fallback path
- **Observable by design** — every routing decision is logged with full context for TCA
- **Adaptive** — broker scores update continuously from live telemetry

---

## 2. System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ORDER ORCHESTRATOR                           │
│  (Strategy Layer → generates child orders)                          │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ OrderRequest{symbol, side, qty, algo, urgency}
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     SMART ORDER ROUTER (SOR)                        │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │   Broker      │  │   Route      │  │   Arb        │               │
│  │   Scoring     │  │   Selection  │  │   Detector   │               │
│  │   Engine      │  │   Engine     │  │              │               │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘               │
│         │                  │                  │                       │
│         ▼                  ▼                  ▼                       │
│  ┌──────────────────────────────────────────────────┐               │
│  │              ROUTE DECISION MATRIX                │               │
│  │  broker_id | rank | split_pct | route_type       │               │
│  └──────────────────────┬───────────────────────────┘               │
│                         │                                            │
└─────────────────────────┼──────────────────────────────────────────┘
                          │ RouteDecision[]
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    EXECUTION LAYER                                   │
│                                                                      │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐               │
│  │Binance  │  │OKX      │  │Bybit    │  │dYdX     │  ...           │
│  │Connector│  │Connector│  │Connector│  │Connector│               │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘               │
│       │            │            │            │                       │
│       ▼            ▼            ▼            ▼                       │
│  ┌──────────────────────────────────────────────────┐               │
│  │           EXECUTION REPORT AGGREGATOR             │               │
│  └──────────────────────┬───────────────────────────┘               │
│                         │                                            │
└─────────────────────────┼──────────────────────────────────────────┘
                          │ ExecutionReport[]
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    TCA & ANALYTICS ENGINE                            │
│  (Post-trade cost analysis, route performance, broker benchmarks)   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Broker Scoring Algorithm

### 3.1 Composite Score Formula

Each broker receives a **composite score** (0–100) computed every N seconds from live telemetry:

```
Score(broker, pair) = w₁·S_spread + w₂·S_liquidity + w₃·S_latency
                    + w₄·S_fees + w₅·S_reliability + w₆·S_fill_rate
```

**Default weights (configurable per strategy):**

| Factor | Weight | Description |
|--------|--------|-------------|
| `S_spread` | 0.25 | Effective spread quality (tighter = better) |
| `S_liquidity` | 0.25 | Available depth at top-of-book ± N levels |
| `S_latency` | 0.20 | Round-trip order latency (p50/p99) |
| `S_fees` | 0.15 | Net fee after rebates (maker/taker) |
| `S_reliability` | 0.10 | Uptime %, error rate, cancel-reject rate |
| `S_fill_rate` | 0.05 | Historical fill rate for this pair on this broker |

### 3.2 Individual Factor Scoring

#### 3.2.1 Spread Score

```python
def score_spread(broker: str, pair: str) -> float:
    """Lower effective spread = higher score. Normalized to [0, 1]."""
    broker_spread = get_effective_spread(broker, pair)       # in bps
    best_spread   = get_best_spread_across_brokers(pair)     # in bps
    worst_spread  = get_worst_spread_across_brokers(pair)    # in bps

    if worst_spread == best_spread:
        return 1.0

    # Inverted: best spread gets 1.0, worst gets 0.0
    return 1.0 - (broker_spread - best_spread) / (worst_spread - best_spread)
```

#### 3.2.2 Liquidity Score

```python
def score_liquidity(broker: str, pair: str, order_size: float) -> float:
    """How much of the order can be filled at top-of-book ± depth_levels."""
    book = get_order_book(broker, pair, depth=10)
    executable_qty = book.total_depth_within_bps(bps_threshold=10)

    # Ratio of order size coverable within acceptable slippage
    coverage = min(executable_qty / order_size, 1.0)
    return coverage
```

#### 3.2.3 Latency Score

```python
def score_latency(broker: str) -> float:
    """Lower latency = higher score. Uses exponential decay."""
    p50_ms = get_latency_p50(broker)  # median round-trip in ms
    p99_ms = get_latency_p99(broker)  # p99 round-trip in ms

    # Weighted blend: p50 matters more for typical, p99 for tail risk
    blended = 0.7 * p50_ms + 0.3 * p99_ms

    # Exponential decay: 1ms → ~1.0, 100ms → ~0.37, 500ms → ~0.007
    return math.exp(-blended / 100.0)
```

#### 3.2.4 Fee Score

```python
def score_fees(broker: str, pair: str, side: str, is_maker: bool) -> float:
    """Lower net fees = higher score. Includes rebates."""
    fee_schedule = get_fee_schedule(broker, pair, is_maker)
    net_fee_bps  = fee_schedule.taker_fee - fee_schedule.rebate  # can be negative

    # Normalize: 0 bps fee → 1.0, 10 bps → 0.0 (clamp negative to 1.0)
    return max(0.0, 1.0 - net_fee_bps / 10.0)
```

#### 3.2.5 Reliability Score

```python
def score_reliability(broker: str) -> float:
    """Rolling 24h uptime and error rate."""
    uptime_pct     = get_uptime_24h(broker)          # 0.0–1.0
    error_rate     = get_error_rate_24h(broker)       # 0.0–1.0
    reject_rate    = get_cancel_reject_rate(broker)   # 0.0–1.0

    # Weighted composite
    return 0.5 * uptime_pct + 0.3 * (1.0 - error_rate) + 0.2 * (1.0 - reject_rate)
```

#### 3.2.6 Fill Rate Score

```python
def score_fill_rate(broker: str, pair: str) -> float:
    """Historical fill rate for this pair over last 1000 orders."""
    stats = get_fill_stats(broker, pair, window=1000)
    return stats.fill_rate  # 0.0–1.0
```

### 3.3 Score Aggregation & Decay

```python
class BrokerScorer:
    def __init__(self, weights: dict, decay_half_life_min: int = 5):
        self.weights = weights
        self.decay_half_life = decay_half_life_min * 60  # seconds

    def compute_score(self, broker: str, pair: str, order_size: float,
                      side: str, is_maker: bool) -> float:
        factors = {
            'spread':     score_spread(broker, pair),
            'liquidity':  score_liquidity(broker, pair, order_size),
            'latency':    score_latency(broker),
            'fees':       score_fees(broker, pair, side, is_maker),
            'reliability': score_reliability(broker),
            'fill_rate':  score_fill_rate(broker, pair),
        }

        raw_score = sum(self.weights[k] * factors[k] for k in factors)

        # Apply exponential smoothing with historical score
        prev_score = self.get_previous_score(broker, pair)
        elapsed = time.time() - self.last_update[broker][pair]
        alpha = 1.0 - math.exp(-elapsed / self.decay_half_life)

        smoothed = alpha * raw_score + (1 - alpha) * prev_score
        self.update_score(broker, pair, smoothed)
        return smoothed
```

### 3.4 Penalty Modifiers

Certain events apply **penalty multipliers** to the composite score:

| Event | Penalty | Duration |
|-------|---------|----------|
| Order rejected by broker | ×0.5 | 60s |
| WebSocket disconnect | ×0.1 | until reconnect |
| Latency spike (>2× baseline) | ×0.7 | 120s |
| Partial fill rate < 50% | ×0.8 | 300s |
| API rate limit hit | ×0.3 | 120s |
| Maintenance window | ×0.0 | until clear |

---

## 4. Best Execution Routing

### 4.1 Routing Strategies

The SOR supports multiple routing strategies, selectable per order or per strategy:

| Strategy | Description | Use Case |
|----------|-------------|----------|
| `SINGLE_BEST` | Route entire order to highest-scoring broker | Small orders, low urgency |
| `SWEEP` | Fill across multiple brokers to get best aggregate price | Large orders, need immediate fill |
| `TWAP_SPLIT` | Split order over time, route each slice to best broker at that moment | TWAP/VWAP algos |
| `ICEBERG` | Route small visible portions, rotate brokers to hide footprint | Stealth execution |
| `ARBITRAGE` | Route to exploit cross-broker price differentials | Arb strategies |
| `COST_OPTIMAL` | Minimize total cost (fees + spread + impact) regardless of speed | Passive strategies |
| `LATENCY_OPTIMAL` | Minimize time-to-fill | HFT, momentum |

### 4.2 Routing Decision Engine

```python
class RouteDecisionEngine:
    def route_order(self, order: OrderRequest) -> list[RouteLeg]:
        """Main routing entry point."""

        # Step 1: Get ranked broker list
        ranked = self.scorer.rank_brokers(
            pair=order.pair,
            order_size=order.quantity,
            side=order.side,
            is_maker=(order.type == 'LIMIT')
        )

        # Step 2: Filter out blocked/unavailable brokers
        ranked = [b for b in ranked if self.is_broker_available(b.broker_id)]

        # Step 3: Apply strategy-specific routing
        strategy = order.routing_strategy or self.default_strategy

        if strategy == 'SINGLE_BEST':
            return self._route_single_best(ranked, order)
        elif strategy == 'SWEEP':
            return self._route_sweep(ranked, order)
        elif strategy == 'TWAP_SPLIT':
            return self._route_twap_split(ranked, order)
        elif strategy == 'COST_OPTIMAL':
            return self._route_cost_optimal(ranked, order)
        elif strategy == 'LATENCY_OPTIMAL':
            return self._route_latency_optimal(ranked, order)
        # ... additional strategies

    def _route_single_best(self, ranked, order):
        """Route entire order to the #1 ranked broker."""
        best = ranked[0]
        return [RouteLeg(
            broker_id=best.broker_id,
            quantity=order.quantity,
            price=order.price,
            order_type=order.type,
            time_in_force=order.tif,
            reason=f"Best composite score: {best.score:.2f}"
        )]

    def _route_sweep(self, ranked, order):
        """Sweep across brokers for best aggregate fill."""
        legs = []
        remaining = order.quantity

        for broker in ranked:
            if remaining <= 0:
                break

            # Calculate how much this broker can absorb
            available = self._get_available_depth(broker, order)
            take_qty = min(remaining, available)

            if take_qty > 0:
                legs.append(RouteLeg(
                    broker_id=broker.broker_id,
                    quantity=take_qty,
                    order_type='MARKET',
                    reason=f"Sweep fill, score: {broker.score:.2f}"
                ))
                remaining -= take_qty

        return legs
```

### 4.3 Pair-Specific Routing Rules

```yaml
routing_rules:
  # High-liquidity pairs: prefer lowest fees
  BTC/USDT:
    default_strategy: COST_OPTIMAL
    score_weights:
      fees: 0.30
      spread: 0.25
      liquidity: 0.20
      latency: 0.15
      reliability: 0.05
      fill_rate: 0.05
    preferred_brokers: [binance, okx, bybit]

  # Low-liquidity pairs: prefer reliability and fill rate
  ALT/USDT:
    default_strategy: SINGLE_BEST
    score_weights:
      reliability: 0.25
      fill_rate: 0.25
      liquidity: 0.25
      spread: 0.15
      fees: 0.05
      latency: 0.05
    min_broker_score: 60  # Don't route to low-scoring brokers

  # Stablecoins: minimize spread
  USDC/USDT:
    default_strategy: COST_OPTIMAL
    score_weights:
      spread: 0.40
      fees: 0.30
      liquidity: 0.20
      latency: 0.05
      reliability: 0.03
      fill_rate: 0.02
```

---

## 5. Failover Routing

### 5.1 Failover Architecture

```
                    ┌─────────────────┐
                    │   ORDER IN       │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  PRIMARY ROUTE   │──── Success ──→ Done
                    │  (highest score) │
                    └────────┬────────┘
                             │ Failure
                             ▼
                    ┌─────────────────┐
                    │  SECONDARY ROUTE  │──── Success ──→ Done
                    │  (2nd highest)   │
                    └────────┬────────┘
                             │ Failure
                             ▼
                    ┌─────────────────┐
                    │  TERTIARY ROUTE   │──── Success ──→ Done
                    │  (3rd highest)   │
                    └────────┬────────┘
                             │ Failure
                             ▼
                    ┌─────────────────┐
                    │  EMERGENCY FALLBACK│
                    │  (any available)  │
                    └────────┬────────┘
                             │ Failure
                             ▼
                    ┌─────────────────┐
                    │  ALERT + HOLD     │
                    │  (manual review)  │
                    └─────────────────┘
```

### 5.2 Failover Triggers

| Trigger | Detection Method | Failover Speed |
|---------|-----------------|----------------|
| **Connection lost** | WebSocket disconnect, TCP timeout | Immediate (< 100ms) |
| **Order rejected** | API error response | Immediate (next attempt) |
| **Timeout** | No ack within threshold (default 2s) | After timeout expires |
| **Rate limited** | HTTP 429 / API rate limit response | Immediate, route away for cooldown |
| **Stale prices** | Last price update > threshold (5s) | After staleness check |
| **Partial fill stall** | Partial fill with no further fills > 10s | After stall timeout |
| **Circuit breaker** | Error rate > threshold in sliding window | Immediate |

### 5.3 Failover State Machine

```python
class FailoverManager:
    BROKER_STATES = ['ACTIVE', 'DEGRADED', 'SUSPENDED', 'OFFLINE']

    def __init__(self):
        self.broker_state: dict[str, str] = {}
        self.failover_chain: dict[str, list[str]] = {}  # pair → ordered broker list

    def on_broker_failure(self, broker_id: str, failure_type: str, pair: str):
        """Handle broker failure and trigger failover."""

        # Record failure
        self.record_failure(broker_id, failure_type)

        # Update broker state
        current = self.broker_state.get(broker_id, 'ACTIVE')
        failure_count = self.get_failure_count(broker_id, window_sec=60)

        if failure_count >= 5:
            self.broker_state[broker_id] = 'OFFLINE'
            self.alert_ops(f"BROKER OFFLINE: {broker_id} ({failure_count} failures/min)")
        elif failure_count >= 2:
            self.broker_state[broker_id] = 'DEGRADED'
        else:
            self.broker_state[broker_id] = 'SUSPENDED'

        # Penalize score
        self.scorer.apply_penalty(broker_id, pair, duration_sec=120)

    def get_failover_broker(self, pair: str, exclude: list[str]) -> str | None:
        """Get next best broker for failover."""
        ranked = self.scorer.rank_brokers(pair=pair, order_size=0, side='BUY', is_maker=False)

        for broker in ranked:
            if broker.broker_id in exclude:
                continue
            if self.broker_state.get(broker.broker_id) == 'OFFLINE':
                continue
            if broker.score < 30:  # Minimum viable score
                continue
            return broker.broker_id

        return None  # No viable broker — alert!

    def recovery_probe(self, broker_id: str):
        """Periodically probe offline/degraded brokers to detect recovery."""
        # Send lightweight ping (e.g., GET /api/v3/ping)
        try:
            response = broker_connector[broker_id].ping(timeout=1)
            if response.ok:
                self.broker_state[broker_id] = 'ACTIVE'
                self.scorer.clear_penalties(broker_id)
                self.log.info(f"Broker {broker_id} recovered to ACTIVE")
        except Exception:
            pass  # Still down, will retry on next probe cycle
```

### 5.4 Failover Configuration

```yaml
failover:
  max_retries: 3
  retry_delay_ms: 100
  order_timeout_ms: 2000
  probe_interval_sec: 30       # Recovery probe frequency
  failure_window_sec: 60       # Rolling window for failure counting
  thresholds:
    degraded_after: 2          # Failures in window to mark DEGRADED
    offline_after: 5           # Failures in window to mark OFFLINE
    min_broker_score: 30       # Don't route to brokers below this
  alert_channels:
    - type: telegram
      severity: [offline, critical]
    - type: pagerduty
      severity: [critical]
```

---

## 6. Cross-Broker Arbitrage Detection

### 6.1 Arb Detection Engine

The arb detector runs as a continuous background process, scanning for price dislocations across brokers:

```python
class ArbitrageDetector:
    def __init__(self, min_profit_bps: float = 5.0, max_latency_ms: float = 500):
        self.min_profit_bps = min_profit_bps
        self.max_latency_ms = max_latency_ms
        self.price_cache: dict[str, dict[str, PriceLevel]] = {}  # pair → broker → price

    def on_price_update(self, pair: str, broker: str, bid: float, ask: float):
        """Called on every top-of-book update from any broker."""
        self.price_cache.setdefault(pair, {})[broker] = PriceLevel(bid, ask)

        # Check for arb opportunities
        opportunities = self._detect_arb(pair)
        for opp in opportunities:
            if opp.expected_profit_bps >= self.min_profit_bps:
                self._emit_arb_signal(opp)

    def _detect_arb(self, pair: str) -> list[ArbOpportunity]:
        """Find all viable arb opportunities for a pair across brokers."""
        prices = self.price_cache.get(pair, {})
        if len(prices) < 2:
            return []

        opportunities = []
        brokers = list(prices.keys())

        for i, buy_broker in enumerate(brokers):
            for j, sell_broker in enumerate(brokers):
                if i == j:
                    continue

                buy_price  = prices[buy_broker].ask   # Price to buy
                sell_price = prices[sell_broker].bid   # Price to sell

                if sell_price <= buy_price:
                    continue

                # Calculate net profit after fees and estimated slippage
                buy_fee  = self._get_fee(buy_broker, pair, 'taker')
                sell_fee = self._get_fee(sell_broker, pair, 'taker')
                slippage_bps = 1.0  # Estimated slippage buffer

                gross_profit_bps = (sell_price - buy_price) / buy_price * 10000
                net_profit_bps = gross_profit_bps - buy_fee - sell_fee - slippage_bps

                if net_profit_bps > 0:
                    # Estimate execution feasibility
                    buy_depth  = self._get_depth(buy_broker, pair, 'ask', levels=3)
                    sell_depth = self._get_depth(sell_broker, pair, 'bid', levels=3)
                    max_qty = min(buy_depth, sell_depth)

                    latency = self._estimate_cross_latency(buy_broker, sell_broker)

                    if latency <= self.max_latency_ms and max_qty > 0:
                        opportunities.append(ArbOpportunity(
                            pair=pair,
                            buy_broker=buy_broker,
                            sell_broker=sell_broker,
                            buy_price=buy_price,
                            sell_price=sell_price,
                            net_profit_bps=net_profit_bps,
                            max_quantity=max_qty,
                            estimated_latency_ms=latency,
                            timestamp=time.time_ns(),
                        ))

        return opportunities
```

### 6.2 Arb Execution Flow

```
Price Update → Arb Detector → Signal Emitted
                                  │
                                  ▼
                         ┌─────────────────┐
                         │  ARB EXECUTOR     │
                         │                   │
                         │  1. Validate still │
                         │     profitable     │
                         │  2. Check balances │
                         │  3. Atomic pair:   │
                         │     BUY  on broker_A│
                         │     SELL on broker_B│
                         │  4. Confirm fills  │
                         │  5. Log P&L        │
                         └─────────────────┘
```

### 6.3 Latency Arbitrage Window

```python
# Key timing constraints for cross-broker arb:
ARB_TIMING = {
    'price_staleness_ms': 100,      # Max age of price quote to act on
    'order_ack_timeout_ms': 500,     # Max wait for order acknowledgment
    'fill_confirm_timeout_ms': 2000, # Max wait for fill confirmation
    'max_leg_skew_ms': 50,           # Max time between legs (for atomicity)
    'min_profit_after_slippage_bps': 2.0,  # Floor after worst-case slippage
}
```

---

## 7. Order Splitting Across Brokers

### 7.1 Splitting Strategies

```python
class OrderSplitter:
    """Splits large orders across multiple brokers."""

    def split_order(self, order: OrderRequest, ranked_brokers: list[BrokerRank]
                    ) -> list[RouteLeg]:
        """Determine optimal split based on order characteristics."""

        if order.quantity <= self.small_order_threshold:
            # Small orders: don't split, use best broker
            return self._single_broker_split(order, ranked_brokers[0])

        strategy = self._select_split_strategy(order)

        if strategy == 'PROPORTIONAL':
            return self._proportional_split(order, ranked_brokers)
        elif strategy == 'LIQUIDITY_WEIGHTED':
            return self._liquidity_weighted_split(order, ranked_brokers)
        elif strategy == 'COST_OPTIMAL':
            return self._cost_optimal_split(order, ranked_brokers)
        elif strategy == 'ICEBERG_ROTATE':
            return self._iceberg_rotate_split(order, ranked_brokers)

    def _proportional_split(self, order, ranked):
        """Split proportional to broker scores."""
        total_score = sum(b.score for b in ranked[:self.max_split_brokers])
        legs = []
        remaining = order.quantity

        for i, broker in enumerate(ranked[:self.max_split_brokers]):
            if i == len(ranked[:self.max_split_brokers]) - 1:
                # Last broker gets remainder (handles rounding)
                qty = remaining
            else:
                pct = broker.score / total_score
                qty = round_qty(order.quantity * pct, order.pair)
                remaining -= qty

            if qty > 0:
                legs.append(RouteLeg(
                    broker_id=broker.broker_id,
                    quantity=qty,
                    split_pct=qty / order.quantity,
                    reason=f"Proportional split (score {broker.score:.1f})"
                ))

        return legs

    def _liquidity_weighted_split(self, order, ranked):
        """Split based on available liquidity at each broker."""
        depths = []
        for broker in ranked[:self.max_split_brokers]:
            depth = self._get_executable_depth(broker, order)
            depths.append((broker, depth))

        total_depth = sum(d for _, d in depths)
        if total_depth == 0:
            return self._proportional_split(order, ranked)

        legs = []
        remaining = order.quantity

        for i, (broker, depth) in enumerate(depths):
            if i == len(depths) - 1:
                qty = remaining
            else:
                pct = depth / total_depth
                qty = round_qty(order.quantity * pct, order.pair)
                remaining -= qty

            if qty > 0:
                legs.append(RouteLeg(
                    broker_id=broker.broker_id,
                    quantity=qty,
                    split_pct=qty / order.quantity,
                    reason=f"Liquidity-weighted (depth: {depth:.0f})"
                ))

        return legs

    def _cost_optimal_split(self, order, ranked):
        """Minimize total cost using linear programming."""
        # Objective: minimize sum(qty_i * (spread_i + fee_i + impact_i(qty_i)))
        # Subject to: sum(qty_i) = order.quantity, qty_i >= 0
        from scipy.optimize import minimize

        brokers = ranked[:self.max_split_brokers]
        n = len(brokers)

        def total_cost(qties):
            cost = 0
            for i, broker in enumerate(brokers):
                spread_cost = self._estimate_spread_cost(broker, order.pair, qties[i])
                fee_cost = self._estimate_fee_cost(broker, order.pair, qties[i])
                impact_cost = self._estimate_market_impact(broker, order.pair, qties[i])
                cost += qties[i] * (spread_cost + fee_cost + impact_cost)
            return cost

        constraints = {'type': 'eq', 'fun': lambda q: sum(q) - order.quantity}
        bounds = [(0, order.quantity)] * n
        x0 = [order.quantity / n] * n

        result = minimize(total_cost, x0, bounds=bounds, constraints=constraints)

        legs = []
        for i, broker in enumerate(brokers):
            qty = round_qty(result.x[i], order.pair)
            if qty > 0:
                legs.append(RouteLeg(
                    broker_id=broker.broker_id,
                    quantity=qty,
                    split_pct=qty / order.quantity,
                    reason=f"Cost-optimal (cost: {total_cost(result.x):.4f})"
                ))

        return legs
```

### 7.2 Split Configuration

```yaml
order_splitting:
  small_order_threshold: 0.01 BTC    # Don't split below this
  max_split_brokers: 5               # Max brokers per order
  min_split_quantity: 0.001 BTC      # Minimum quantity per broker
  rounding_precision: 8              # Decimal places for quantity

  strategies:
    default: PROPORTIONAL
    large_orders: COST_OPTIMAL       # Orders > 10× small_order_threshold
    stealth: ICEBERG_ROTATE          # When hiding intent is priority
```

---

## 8. Latency-Based Routing

### 8.1 Latency Measurement

```python
class LatencyMonitor:
    """Measures and tracks broker latency in real-time."""

    def __init__(self):
        self.latency_store: dict[str, LatencyStats] = {}

    def measure_latency(self, broker_id: str, operation: str) -> float:
        """Measure round-trip latency for a broker operation."""
        start = time.perf_counter_ns()

        # Perform lightweight operation (ping, ticker fetch, etc.)
        self._broker_ping(broker_id)

        elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000

        self._record(broker_id, operation, elapsed_ms)
        return elapsed_ms

    def get_latency_stats(self, broker_id: str) -> LatencyStats:
        """Get latency statistics for a broker."""
        samples = self._get_recent_samples(broker_id, window_sec=300)
        if not samples:
            return LatencyStats(p50=999, p95=999, p99=999, mean=999)

        return LatencyStats(
            p50=np.percentile(samples, 50),
            p95=np.percentile(samples, 95),
            p99=np.percentile(samples, 99),
            mean=np.mean(samples),
            stddev=np.std(samples),
            sample_count=len(samples),
        )

    def get_latency_ranking(self, pair: str) -> list[tuple[str, float]]:
        """Rank brokers by latency (lower = better)."""
        rankings = []
        for broker_id in self._get_active_brokers():
            stats = self.get_latency_stats(broker_id)
            # Use p95 for ranking (balances typical vs tail)
            rankings.append((broker_id, stats.p95))

        return sorted(rankings, key=lambda x: x[1])
```

### 8.2 Latency-Aware Routing Rules

```yaml
latency_routing:
  measurement:
    ping_interval_sec: 5
    window_sec: 300           # 5-minute rolling window
    min_samples: 10           # Minimum samples for reliable stats

  thresholds:
    excellent_ms: 10          # < 10ms = excellent
    good_ms: 50               # < 50ms = good
    acceptable_ms: 200        # < 200ms = acceptable
    degraded_ms: 500          # < 500ms = degraded
    unacceptable_ms: 2000     # > 2000ms = route away

  strategies:
    hft:
      max_latency_ms: 50
      score_weight_latency: 0.50
      failover_on_degraded: true

    swing:
      max_latency_ms: 2000
      score_weight_latency: 0.05
      failover_on_degraded: false
```

---

## 9. Cost-Based Routing

### 9.1 Total Cost Model

```python
class CostModel:
    """Calculates total trading cost for routing decisions."""

    def estimate_total_cost(self, broker: str, pair: str, side: str,
                            quantity: float, order_type: str) -> CostBreakdown:
        """Estimate all-in cost for executing on this broker."""

        # 1. Direct fees
        fee = self._get_fee(broker, pair, side, order_type)

        # 2. Spread cost (half-spread for marketable orders)
        spread_bps = self._get_effective_spread(broker, pair)
        spread_cost_bps = spread_bps / 2 if order_type == 'MARKET' else 0

        # 3. Market impact (estimated using square-root model)
        impact_bps = self._estimate_market_impact(broker, pair, quantity)

        # 4. Slippage (based on historical slippage for this pair/broker)
        slippage_bps = self._get_historical_slippage(broker, pair, quantity)

        # 5. Opportunity cost (for limit orders that may not fill)
        opp_cost_bps = 0
        if order_type == 'LIMIT':
            fill_prob = self._estimate_fill_probability(broker, pair, quantity)
            opp_cost_bps = (1 - fill_prob) * spread_bps  # Cost of not filling

        # 6. Financing cost (for leveraged/margin positions)
        financing_bps = self._get_financing_cost(broker, pair, quantity)

        total_bps = (fee + spread_cost_bps + impact_bps +
                     slippage_bps + opp_cost_bps + financing_bps)

        return CostBreakdown(
            broker=broker,
            pair=pair,
            quantity=quantity,
            fee_bps=fee,
            spread_cost_bps=spread_cost_bps,
            impact_bps=impact_bps,
            slippage_bps=slippage_bps,
            opportunity_cost_bps=opp_cost_bps,
            financing_bps=financing_bps,
            total_bps=total_bps,
            estimated_total_cost_usd=quantity * price * total_bps / 10000,
        )

    def _estimate_market_impact(self, broker: str, pair: str, qty: float) -> float:
        """Square-root market impact model: impact = σ * sqrt(qty / V) * γ"""
        volatility = self._get_volatility(pair)
        daily_volume = self._get_daily_volume(broker, pair)
        participation_rate = qty / daily_volume
        gamma = self._get_impact_coefficient(broker, pair)  # Calibrated per broker

        impact = volatility * math.sqrt(participation_rate) * gamma * 10000  # bps
        return impact
```

### 9.2 Cost Comparison Table

The router generates a cost comparison for each routing decision:

```
┌──────────┬────────┬────────┬────────┬────────┬────────┬─────────┐
│ Broker   │ Fee    │ Spread │ Impact │ Slipp. │ Opp.C  │ TOTAL   │
│          │ (bps)  │ (bps)  │ (bps)  │ (bps)  │ (bps)  │ (bps)   │
├──────────┼────────┼────────┼────────┼────────┼────────┼─────────┤
│ Binance  │  1.00  │  0.50  │  0.30  │  0.20  │  0.00  │  2.00   │
│ OKX      │  0.80  │  0.60  │  0.40  │  0.25  │  0.00  │  2.05   │
│ Bybit    │  1.00  │  0.70  │  0.50  │  0.30  │  0.00  │  2.50   │
│ Gate.io  │  1.20  │  1.00  │  0.80  │  0.50  │  0.00  │  3.50   │
└──────────┴────────┴────────┴────────┴────────┴────────┴─────────┘
→ Selected: Binance (lowest total cost: 2.00 bps)
```

---

## 10. Load Balancing

### 10.1 Load Balancing Objectives

1. **No single broker overload** — distribute volume to avoid rate limits
2. **Capacity-aware routing** — consider broker-specific limits
3. **Risk diversification** — avoid concentration risk on one broker
4. **Queue fairness** — prevent order starvation at any broker

### 10.2 Load Balancer Implementation

```python
class BrokerLoadBalancer:
    """Distributes orders across brokers considering load and capacity."""

    def __init__(self):
        self.broker_capacity: dict[str, BrokerCapacity] = {}
        self.active_orders: dict[str, int] = {}  # broker → active order count
        self.rate_counters: dict[str, RateCounter] = {}

    def get_available_capacity(self, broker_id: str) -> float:
        """Returns remaining capacity as a fraction [0, 1]."""
        cap = self.broker_capacity[broker_id]

        # Check multiple dimensions
        order_utilization = self.active_orders.get(broker_id, 0) / cap.max_concurrent_orders
        rate_utilization = self.rate_counters[broker_id].utilization()
        volume_utilization = self._get_volume_utilization(broker_id, window_sec=60)

        # Capacity is the most constrained dimension
        return 1.0 - max(order_utilization, rate_utilization, volume_utilization)

    def adjust_scores_for_load(self, ranked: list[BrokerRank]) -> list[BrokerRank]:
        """Adjust broker scores based on current load."""
        for broker in ranked:
            capacity = self.get_available_capacity(broker.broker_id)

            if capacity < 0.1:
                # Near capacity: heavy penalty
                broker.score *= 0.1
                broker.reason += " [LOAD: near capacity]"
            elif capacity < 0.3:
                # Moderate load: proportional penalty
                broker.score *= 0.5
                broker.reason += " [LOAD: moderate]"
            elif capacity < 0.7:
                # Normal load: slight penalty
                broker.score *= 0.9
                # No annotation needed

            # else: no penalty, plenty of capacity

        # Re-sort by adjusted scores
        ranked.sort(key=lambda b: b.score, reverse=True)
        return ranked

    def on_order_submitted(self, broker_id: str):
        self.active_orders[broker_id] = self.active_orders.get(broker_id, 0) + 1
        self.rate_counters[broker_id].increment()

    def on_order_completed(self, broker_id: str):
        self.active_orders[broker_id] = max(0, self.active_orders.get(broker_id, 0) - 1)
```

### 10.3 Load Balancing Configuration

```yaml
load_balancing:
  enabled: true
  check_interval_sec: 1

  broker_capacities:
    binance:
      max_concurrent_orders: 200
      max_orders_per_second: 50
      max_volume_per_minute_usd: 10000000
    okx:
      max_concurrent_orders: 150
      max_orders_per_second: 40
      max_volume_per_minute_usd: 8000000
    bybit:
      max_concurrent_orders: 100
      max_orders_per_second: 30
      max_volume_per_minute_usd: 5000000

  penalty_thresholds:
    near_capacity: 0.9     # > 90% utilization → score × 0.1
    moderate_load: 0.7     # > 70% utilization → score × 0.5
    light_load: 0.3        # > 30% utilization → score × 0.9
```

---

## 11. Route Logging & Analytics

### 11.1 Route Log Schema

Every routing decision is logged with full context:

```sql
CREATE TABLE route_decisions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp_ns        BIGINT NOT NULL,
    order_id            UUID NOT NULL,
    strategy            VARCHAR(32) NOT NULL,

    -- Input context
    pair                VARCHAR(20) NOT NULL,
    side                VARCHAR(4) NOT NULL,
    requested_qty       DECIMAL(20, 8) NOT NULL,
    order_type          VARCHAR(16) NOT NULL,
    urgency             VARCHAR(16),

    -- Routing output
    selected_broker     VARCHAR(32) NOT NULL,
    selected_score      DECIMAL(8, 4),
    route_legs          JSONB NOT NULL,        -- [{broker, qty, pct, reason}]
    routing_latency_us  INTEGER,               -- Decision time in microseconds

    -- Cost estimates
    estimated_cost_bps  DECIMAL(8, 4),
    estimated_slippage  DECIMAL(8, 4),

    -- Alternatives considered
    candidate_brokers   JSONB,                 -- [{broker, score, rank}]

    -- Outcome (filled post-execution)
    actual_fill_qty     DECIMAL(20, 8),
    actual_avg_price    DECIMAL(20, 8),
    actual_cost_bps     DECIMAL(8, 4),
    actual_slippage_bps DECIMAL(8, 4),
    fill_time_ms        INTEGER,

    -- TCA comparison
    arrival_price       DECIMAL(20, 8),        -- Price at decision time
    twap_price          DECIMAL(20, 8),        -- TWAP over execution window
    implementation_shortfall_bps DECIMAL(8, 4)
);

CREATE INDEX idx_route_decisions_order ON route_decisions(order_id);
CREATE INDEX idx_route_decisions_broker ON route_decisions(selected_broker, timestamp_ns);
CREATE INDEX idx_route_decisions_pair ON route_decisions(pair, timestamp_ns);
```

### 11.2 Real-Time Analytics Dashboard Metrics

```yaml
analytics:
  real_time:
    - metric: routing_latency_p99_us
      alert_threshold: 10000     # 10ms
    - metric: broker_score_variance
      description: "How spread out are broker scores? High = fragmented liquidity"
    - metric: failover_rate_per_hour
      alert_threshold: 5
    - metric: arb_opportunities_per_hour
    - metric: fill_rate_by_broker
    - metric: cost_savings_vs_single_broker_bps
      description: "How much SOR saves vs always using the default broker"

  daily_reports:
    - report: broker_scorecard
      content: "Per-broker: fill rate, avg cost, latency, uptime, score trend"
    - report: routing_effectiveness
      content: "Implementation shortfall, arrival cost, VWAP comparison"
    - report: split_analysis
      content: "How often splits were used, cost benefit of splitting"
    - report: failover_summary
      content: "Failover events, recovery times, impacted orders"
```

### 11.3 TCA Integration

```python
class RouteTCA:
    """Post-trade Transaction Cost Analysis for routing decisions."""

    def analyze_route(self, route_decision: dict, execution_reports: list) -> TCAReport:
        """Compare actual execution against alternatives."""

        arrival_price = route_decision['arrival_price']
        actual_avg = self._weighted_avg_price(execution_reports)

        # Implementation Shortfall
        side_sign = 1 if route_decision['side'] == 'BUY' else -1
        is_bps = side_sign * (actual_avg - arrival_price) / arrival_price * 10000

        # What if we used a single broker?
        single_broker_costs = []
        for broker in route_decision['candidate_brokers']:
            est = self.cost_model.estimate_total_cost(
                broker['broker_id'], route_decision['pair'],
                route_decision['side'], route_decision['requested_qty'],
                route_decision['order_type']
            )
            single_broker_costs.append((broker['broker_id'], est.total_bps))

        best_single = min(single_broker_costs, key=lambda x: x[1])
        savings_bps = best_single[1] - route_decision['actual_cost_bps']

        return TCAReport(
            order_id=route_decision['order_id'],
            implementation_shortfall_bps=is_bps,
            arrival_cost_bps=route_decision['actual_cost_bps'],
            savings_vs_best_single_broker_bps=savings_bps,
            routing_decision_correct=(savings_bps >= 0),
            fill_time_ms=route_decision['fill_time_ms'],
            broker_used=route_decision['selected_broker'],
            would_have_been_better_at=best_single[0] if savings_bps < 0 else None,
        )
```

---

## 12. Integration with Broker Connectors

### 12.1 Connector Interface

All broker connectors implement a unified interface:

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

class BrokerStatus(Enum):
    ACTIVE = "active"
    DEGRADED = "degraded"
    SUSPENDED = "suspended"
    OFFLINE = "offline"

@dataclass
class BrokerCapabilities:
    broker_id: str
    supported_pairs: list[str]
    supported_order_types: list[str]    # MARKET, LIMIT, STOP, ICEBERG, etc.
    supports_margin: bool
    supports_futures: bool
    max_order_size: dict[str, float]    # pair → max qty
    min_order_size: dict[str, float]    # pair → min qty
    tick_sizes: dict[str, float]        # pair → tick size
    lot_sizes: dict[str, float]         # pair → lot size

class BrokerConnector(ABC):
    """Unified interface for all broker integrations."""

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def ping(self) -> bool: ...

    @abstractmethod
    async def get_capabilities(self) -> BrokerCapabilities: ...

    @abstractmethod
    async def get_ticker(self, pair: str) -> Ticker: ...

    @abstractmethod
    async def get_order_book(self, pair: str, depth: int = 20) -> OrderBook: ...

    @abstractmethod
    async def submit_order(self, order: Order) -> OrderAck: ...

    @abstractmethod
    async def cancel_order(self, order_id: str) -> CancelAck: ...

    @abstractmethod
    async def amend_order(self, order_id: str, amendment: OrderAmendment) -> AmendAck: ...

    @abstractmethod
    async def get_order_status(self, order_id: str) -> OrderStatus: ...

    @abstractmethod
    async def get_open_orders(self, pair: str | None = None) -> list[OrderStatus]: ...

    @abstractmethod
    async def get_balances(self) -> dict[str, Balance]: ...

    @abstractmethod
    async def subscribe_ticker(self, pair: str, callback) -> None: ...

    @abstractmethod
    async def subscribe_order_book(self, pair: str, depth: int, callback) -> None: ...

    @abstractmethod
    async def subscribe_user_orders(self, callback) -> None: ...
```

### 12.2 Connector Registry

```python
class ConnectorRegistry:
    """Manages all broker connector instances."""

    def __init__(self):
        self.connectors: dict[str, BrokerConnector] = {}
        self.capabilities: dict[str, BrokerCapabilities] = {}
        self.status: dict[str, BrokerStatus] = {}

    async def register(self, broker_id: str, connector: BrokerConnector):
        """Register and initialize a broker connector."""
        self.connectors[broker_id] = connector
        await connector.connect()
        self.capabilities[broker_id] = await connector.get_capabilities()
        self.status[broker_id] = BrokerStatus.ACTIVE
        logger.info(f"Registered broker: {broker_id}")

    async def health_check_all(self):
        """Periodic health check for all registered brokers."""
        for broker_id, connector in self.connectors.items():
            try:
                ok = await asyncio.wait_for(connector.ping(), timeout=2.0)
                if ok and self.status[broker_id] != BrokerStatus.ACTIVE:
                    self.status[broker_id] = BrokerStatus.ACTIVE
                    logger.info(f"Broker {broker_id} recovered")
            except Exception as e:
                self.status[broker_id] = BrokerStatus.OFFLINE
                logger.warning(f"Broker {broker_id} health check failed: {e}")

    def get_active_brokers_for_pair(self, pair: str) -> list[str]:
        """Get all active brokers that support a given pair."""
        return [
            bid for bid, cap in self.capabilities.items()
            if pair in cap.supported_pairs and self.status[bid] == BrokerStatus.ACTIVE
        ]
```

### 12.3 Connector Adapter Pattern

```python
# Example: Binance connector adapter
class BinanceConnector(BrokerConnector):
    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        self.client = AsyncClient(api_key, api_secret, testnet=testnet)
        self.ws_manager = BinanceWebSocketManager()

    async def submit_order(self, order: Order) -> OrderAck:
        params = {
            'symbol': self._normalize_pair(order.pair),
            'side': order.side.upper(),
            'type': order.order_type.upper(),
            'quantity': str(order.quantity),
        }
        if order.order_type == 'LIMIT':
            params['price'] = str(order.price)
            params['timeInForce'] = order.tif or 'GTC'

        response = await self.client.create_order(**params)

        return OrderAck(
            broker_order_id=response['orderId'],
            status=response['status'],
            filled_qty=float(response.get('executedQty', 0)),
            avg_price=float(response.get('cummulativeQuoteQty', 0)) / max(float(response.get('executedQty', 1)), 1e-8),
            timestamp_ns=time.time_ns(),
            raw_response=response,
        )

    # ... implement all other abstract methods
```

### 12.4 Supported Brokers (Initial)

| Broker | Spot | Futures | Margin | WebSocket | Notes |
|--------|------|---------|--------|-----------|-------|
| Binance | ✅ | ✅ | ✅ | ✅ | Primary, highest liquidity |
| OKX | ✅ | ✅ | ✅ | ✅ | Strong alt-coin coverage |
| Bybit | ✅ | ✅ | ✅ | ✅ | Good derivatives |
| Gate.io | ✅ | ✅ | ❌ | ✅ | Wide pair coverage |
| dYdX | ✅ | ✅ | ❌ | ✅ | DEX, no KYC |
| Hyperliquid | ✅ | ✅ | ❌ | ✅ | DEX, low fees |

---

## 13. Data Flow & Sequence Diagrams

### 13.1 Order Routing Sequence

```
Strategy Layer          SOR                BrokerScorer        ConnectorRegistry       Broker API
     │                   │                      │                     │                    │
     │ OrderRequest      │                      │                     │                    │
     │──────────────────→│                      │                     │                    │
     │                   │ rank_brokers()       │                     │                    │
     │                   │─────────────────────→│                     │                    │
     │                   │                      │ get_scores()        │                    │
     │                   │                      │────────────────────→│                    │
     │                   │                      │                     │ get_ticker/book    │
     │                   │                      │                     │───────────────────→│
     │                   │                      │                     │    market data      │
     │                   │                      │                     │←───────────────────│
     │                   │                      │ scores[]            │                    │
     │                   │                      │←────────────────────│                    │
     │                   │ ranked_brokers[]     │                     │                    │
     │                   │←─────────────────────│                     │                    │
     │                   │                      │                     │                    │
     │                   │ route_order()        │                     │                    │
     │                   │──┐                   │                     │                    │
     │                   │  │ select strategy    │                     │                    │
     │                   │  │ apply failover     │                     │                    │
     │                   │  │ apply load balance │                     │                    │
     │                   │  │ generate legs      │                     │                    │
     │                   │←─┘                   │                     │                    │
     │                   │                      │                     │                    │
     │                   │ RouteDecision[]      │                     │                    │
     │                   │────────────────────────────────────────────→│                    │
     │                   │                      │                     │ submit_order()     │
     │                   │                      │                     │───────────────────→│
     │                   │                      │                     │    OrderAck        │
     │                   │                      │                     │←───────────────────│
     │                   │                      │                     │                    │
     │                   │ ExecutionReport[]    │                     │                    │
     │                   │←────────────────────────────────────────────│                    │
     │                   │                      │                     │                    │
     │ ExecutionReport   │                      │                     │                    │
     │←──────────────────│                      │                     │                    │
```

### 13.2 Failover Sequence

```
SOR                  FailoverMgr         Connector_A         Connector_B         Connector_C
 │                       │                    │                    │                    │
 │ submit_order(leg_1)   │                    │                    │                    │
 │──────────────────────────────────────────→│                    │                    │
 │                       │                    │                    │                    │
 │                       │                    │ ERROR / TIMEOUT    │                    │
 │←──────────────────────────────────────────│                    │                    │
 │                       │                    │                    │                    │
 │ on_failure(A, TIMEOUT)│                    │                    │                    │
 │──────────────────────→│                    │                    │                    │
 │                       │ mark DEGRADED(A)   │                    │                    │
 │                       │ penalize_score(A)  │                    │                    │
 │                       │                    │                    │                    │
 │                       │ get_failover(A)    │                    │                    │
 │                       │───────────────────→│ (returns B)        │                    │
 │                       │                    │                    │                    │
 │ submit_order(leg_1)   │                    │                    │                    │
 │───────────────────────────────────────────────────────────────→│                    │
 │                       │                    │                    │                    │
 │                       │                    │                    │ OrderAck           │
 │←───────────────────────────────────────────────────────────────│                    │
 │                       │                    │                    │                    │
 │ ExecutionReport       │                    │                    │                    │
 │ (routed to B)         │                    │                    │                    │
```

---

## 14. Configuration Reference

### 14.1 Master Configuration

```yaml
# broker_routing.yaml — Master configuration for the Broker Routing Engine

version: "1.0"
environment: production

# Global defaults
defaults:
  routing_strategy: COST_OPTIMAL
  max_split_brokers: 5
  small_order_threshold:
    BTC: 0.01
    ETH: 0.1
    default_usd: 10000
  order_timeout_ms: 2000
  max_retries: 3
  retry_delay_ms: 100

# Broker Scoring
scoring:
  update_interval_sec: 5
  decay_half_life_min: 5
  weights:
    spread: 0.25
    liquidity: 0.25
    latency: 0.20
    fees: 0.15
    reliability: 0.10
    fill_rate: 0.05
  min_viable_score: 30

# Failover
failover:
  enabled: true
  max_retries: 3
  retry_delay_ms: 100
  order_timeout_ms: 2000
  probe_interval_sec: 30
  failure_window_sec: 60
  thresholds:
    degraded_after: 2
    offline_after: 5
    min_broker_score: 30

# Arbitrage Detection
arbitrage:
  enabled: true
  min_profit_bps: 5.0
  max_latency_ms: 500
  max_position_usd: 50000
  cooldown_sec: 10

# Load Balancing
load_balancing:
  enabled: true
  check_interval_sec: 1
  penalty_thresholds:
    near_capacity: 0.9
    moderate_load: 0.7
    light_load: 0.3

# Latency Routing
latency:
  ping_interval_sec: 5
  window_sec: 300
  min_samples: 10
  thresholds:
    excellent_ms: 10
    good_ms: 50
    acceptable_ms: 200
    degraded_ms: 500

# Analytics
analytics:
  route_logging: true
  tca_enabled: true
  retention_days: 90
  dashboard_refresh_sec: 5

# Broker Definitions
brokers:
  binance:
    enabled: true
    priority: 1
    connector: binance
    api_env_var: BINANCE_API_KEY
    secret_env_var: BINANCE_API_SECRET
    rate_limits:
      orders_per_second: 50
      requests_per_minute: 1200

  okx:
    enabled: true
    priority: 2
    connector: okx
    api_env_var: OKX_API_KEY
    secret_env_var: OKX_API_SECRET
    passphrase_env_var: OKX_PASSPHRASE
    rate_limits:
      orders_per_second: 40
      requests_per_minute: 600

  bybit:
    enabled: true
    priority: 3
    connector: bybit
    api_env_var: BYBIT_API_KEY
    secret_env_var: BYBIT_API_SECRET
    rate_limits:
      orders_per_second: 30
      requests_per_minute: 600
```

---

## Appendix A: Glossary

| Term | Definition |
|------|-----------|
| **SOR** | Smart Order Router — automated system for optimal order routing |
| **TCA** | Transaction Cost Analysis — post-trade cost evaluation |
| **Implementation Shortfall** | Difference between decision price and actual execution price |
| **Effective Spread** | Actual cost of immediacy, including market impact |
| **BPS** | Basis Points (1 bps = 0.01%) |
| **Market Impact** | Price movement caused by the order itself |
| **Iceberg Order** | Order that shows only a small portion of total quantity |
| **TWAP** | Time-Weighted Average Price |
| **VWAP** | Volume-Weighted Average Price |
| **Fill Rate** | Percentage of submitted orders that get filled |
| **Latency** | Round-trip time from order submission to acknowledgment |

---

## Appendix B: Future Enhancements

1. **ML-based scoring** — Replace fixed weights with a trained model that learns optimal broker selection from historical TCA data
2. **Predictive routing** — Use order flow prediction to pre-position at the right broker before the order arrives
3. **Dark pool integration** — Route to dark pools for large block trades
4. **Cross-chain DEX routing** — Extend to on-chain liquidity sources (Uniswap, Curve, etc.)
5. **Reinforcement learning** — RL agent that optimizes routing policy by maximizing fill quality over time
6. **Colocation awareness** — Factor in physical server proximity to exchange matching engines
7. **Regulatory routing** — Ensure compliance with best execution obligations per jurisdiction

---

*End of document. Architecture designed for Alpha Stack Broker Routing Engine v1.0.*
