# Alpha Stack — Scalability Architecture

> **Version:** 1.0 · **Date:** 2026-07-13 · **Author:** Architecture Team
> **Source Research:** [`research/research_scalability.md`](../research/research_scalability.md) — Scalability research covering technical, strategy, cost, and organizational scaling
> **Status:** Architecture Complete

---

> **Author:** Scalability Architect
> **Date:** 2026-07-13
> **Status:** Architecture Design — Ready for Implementation Review
> **Dependencies:** `architecture_system.md`, `architecture_deployment.md`, `architecture_database.md`, `architecture_data.md`, `architecture_risk.md`, `research_scalability.md`

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Design Philosophy](#2-design-philosophy)
3. [Technical Scaling Architecture](#3-technical-scaling-architecture)
4. [Data Layer Scaling](#4-data-layer-scaling)
5. [Message Infrastructure Scaling](#5-message-infrastructure-scaling)
6. [WebSocket & Connection Scaling](#6-websocket--connection-scaling)
7. [Strategy Scaling Framework](#7-strategy-scaling-framework)
8. [Position Sizing & Market Impact](#8-position-sizing--market-impact)
9. [Cost Scaling Model](#9-cost-scaling-model)
10. [Organizational Scaling](#10-organizational-scaling)
11. [Institutional-Grade Patterns](#11-institutional-grade-patterns)
12. [Event-Driven Architecture](#12-event-driven-architecture)
13. [Microservices Decomposition](#13-microservices-decomposition)
14. [CQRS & Read/Write Separation](#14-cqrs--readwrite-separation)
15. [Phase-Based Scaling Roadmap](#15-phase-based-scaling-roadmap)
16. [Scaling Decision Framework](#16-scaling-decision-framework)
17. [Anti-Patterns & Guardrails](#17-anti-patterns--guardrails)
18. [Implementation Roadmap](#18-implementation-roadmap)

---

## 1. Executive Summary

Alpha Stack must scale from **$7 micro accounts** to **institutional-level capital** without rewriting the core system. This architecture defines how every layer — data ingestion, signal generation, execution, risk management, and infrastructure — evolves incrementally as capital and complexity grow.

### The Golden Rule

> **Scale strategy first, infrastructure second.** A profitable strategy on a laptop beats an unprofitable strategy on a $10K server.

### Scaling Dimensions

| Dimension | From | To | Key Challenge |
|-----------|------|----|---------------|
| **Pairs** | 1 (EURUSD) | 28+ (all majors/crosses) | Rate limits, state sync, correlation |
| **Timeframes** | 1 (H1) | 5 (M1–D1) | Signal alignment, conflict resolution |
| **Strategies** | 1 (MA crossover) | 50+ (multi-family portfolio) | Correlation, capital allocation, decay |
| **Capital** | $7 | $1M+ | Market impact, execution quality, cost ratio |
| **Markets** | Forex | Forex + Crypto + Indices + Futures | API diversity, session management |
| **Team** | Solo + AI | Human team + AI agents | Communication, process, delegation |

---

## 2. Design Philosophy

### 2.1 Core Principles

**1. Incremental Scaling — Never Rewrite**
Each phase builds on the previous. SQLite → PostgreSQL is a migration, not a rewrite. Monolith → microservices is extraction, not replacement. Every upgrade preserves existing strategy logic.

**2. Infrastructure Scales with Capital**
At $7, run locally for $0/month. At $100K, pay $200/month for proper infrastructure. Infrastructure cost must never exceed 1% of monthly expected returns.

**3. Event-Driven from Day One**
Even at Phase 1, internal components communicate via events (function calls acting as events). This makes extraction into services trivial when scaling demands it.

**4. Latency Over Throughput for Execution**
For order execution, a single fast server beats a distributed slow cluster. Throughput matters for backtesting; latency matters for trading. Optimize accordingly.

**5. Strategy Capacity Drives Infrastructure**
Infrastructure decisions follow strategy requirements, not the other way around. If strategies don't need 100 pairs, don't build for 100 pairs.

### 2.2 Scaling Invariants

These properties must hold at every scale:

| Invariant | Description |
|-----------|-------------|
| **Single source of truth for positions** | One authoritative position state, regardless of how many services exist |
| **Atomic order execution** | Orders either fully succeed or fully fail — no partial states |
| **Deterministic signal generation** | Same input data → same signal, regardless of system scale |
| **Auditability** | Every decision is logged with full context, at every scale |
| **Graceful degradation** | System continues operating (with reduced capability) when components fail |

---

## 3. Technical Scaling Architecture

### 3.1 What Breaks: 1 Pair → 10 Pairs

| Dimension | 1 Pair | 10 Pairs | Failure Mode | Solution |
|-----------|--------|----------|-------------|----------|
| Data ingestion | 1 WebSocket stream | 10+ streams | Connection limits, rate limits | Connection pooling, multiplexing |
| State management | Single object | Concurrent state machines | Race conditions, stale reads | Per-pair event loops, message bus |
| Signal generation | Linear scan | N×N correlation checks | CPU spikes during volatility | Pre-computed batch correlations |
| Order management | Simple queue | Multi-pair correlation | Margin conflicts, hedging issues | Centralized position manager |
| Monitoring | Single dashboard | Aggregation needed | Alert fatigue, missed patterns | Cross-pair anomaly detection |

### 3.2 What Breaks: Single → Multi-Timeframe

| Aspect | Single TF | Multi-TF | Challenge | Architecture Solution |
|--------|-----------|----------|-----------|----------------------|
| Data storage | 1 candle series/pair | 3–5× series | Storage, indexing | TimescaleDB hypertables, partitioned by TF |
| Signal alignment | Trivial | Time sync problem | M15 and H4 close at different times | Event-driven candle-close triggers |
| Indicator computation | O(n) per bar | O(n × tf_count) | CPU cost | Incremental computation, cache intermediate state |
| Conflict resolution | N/A | M1 says buy, H4 says sell | Contradictory signals | Scoring system with TF hierarchy weighting |

### 3.3 Multi-Timeframe Signal Resolution

The timeframe alignment problem is the hardest scaling challenge. Architecture solution:

```
┌─────────────────────────────────────────────────────────┐
│              Multi-Timeframe Signal Resolution           │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  M1 candle close → Compute M1 indicators                │
│  M5 candle close → Compute M5 indicators                │
│  M15 candle close → Compute M15 indicators              │
│       │                                                 │
│       ▼                                                 │
│  ┌─────────────────────────────────┐                    │
│  │  Timeframe Hierarchy Engine     │                    │
│  │  D1 > H4 > H1 > M15 > M5 > M1  │                    │
│  │                                 │                    │
│  │  Scoring:                       │                    │
│  │  D1 signal:  weight = 0.30      │                    │
│  │  H4 signal:  weight = 0.25      │                    │
│  │  H1 signal:  weight = 0.20      │                    │
│  │  M15 signal: weight = 0.15      │                    │
│  │  M5 signal:  weight = 0.10      │                    │
│  │                                 │                    │
│  │  Threshold: ≥ 0.60 → Execute    │                    │
│  └─────────────────────────────────┘                    │
│       │                                                 │
│       ▼                                                 │
│  Consensus Signal (BUY/SELL/HOLD + confidence)          │
└─────────────────────────────────────────────────────────┘
```

**Key design decisions:**
- Higher timeframes always override lower (D1 bearish blocks M15 buy)
- Weighted scoring for nuanced alignment
- Configurable threshold per strategy
- Cached higher-TF state avoids recomputation on every lower-TF close

---

## 4. Data Layer Scaling

### 4.1 Database Scaling Phases

| Phase | Capital | Database | Rationale |
|-------|---------|----------|-----------|
| 1 | $7–$100 | SQLite | Zero config, single file, sufficient for 1–3 pairs |
| 2 | $100–$1K | PostgreSQL | Concurrent reads/writes, proper ACID, JSON support |
| 3 | $1K–$10K | TimescaleDB + Redis | Time-series hypertables for candles, Redis for hot cache |
| 4 | $10K–$100K | ClickHouse + PG + Redis | Analytics (backtesting) + OLTP + cache separation |
| 5 | $100K+ | Distributed (ClickHouse + PG + Redis + Kafka) | Full event sourcing, distributed analytics |

### 4.2 Data Volume Scaling

| Scale | Data Volume | Bottleneck | Solution |
|-------|-------------|------------|----------|
| 1 pair, 1 TF, 1 year | ~100K bars | Nothing | SQLite |
| 10 pairs, 3 TFs, 1 year | ~10M bars | Query speed | PostgreSQL + indexing |
| 28 pairs, 5 TFs, 5 years | ~500M bars | Storage + query | TimescaleDB hypertables |
| Full tick data, 28 pairs, 1 year | ~50B ticks | Everything | ClickHouse + aggregation |

### 4.3 Storage Tier Strategy

```
┌─────────────────────────────────────────────────────┐
│                  Storage Tier Model                   │
├─────────────────────────────────────────────────────┤
│                                                     │
│  HOT TIER (Redis)                                    │
│  ├── Last 1000 ticks per pair                       │
│  ├── Current indicator values                       │
│  ├── Active order state                             │
│  └── Latency: <1ms | Cost: RAM                     │
│                                                     │
│  WARM TIER (TimescaleDB / PostgreSQL)                │
│  ├── Historical candles (all timeframes)            │
│  ├── Completed trades                               │
│  ├── Signal history                                 │
│  └── Latency: 1-10ms | Cost: SSD                   │
│                                                     │
│  COLD TIER (Object Storage / Archive)                │
│  ├── Raw tick data (compressed)                     │
│  ├── Old backtest results                           │
│  ├── Audit logs                                     │
│  └── Latency: 100ms+ | Cost: pennies/GB            │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### 4.4 Migration Strategy

Each database migration is **additive, not destructive:**

1. Add new database alongside old
2. Dual-write to both databases
3. Migrate historical data in background
4. Switch reads to new database
5. Remove old database after validation period

**Never** do a big-bang migration. Always run both systems in parallel.

---

## 5. Message Infrastructure Scaling

### 5.1 Message Bus Evolution

| Phase | System | Throughput | Latency | Durability | Use Case |
|-------|--------|-----------|---------|------------|----------|
| 1 | None (function calls) | N/A | <1ms | N/A | Single-process monolith |
| 2 | In-process event emitter | 1M+ events/s | <1ms | None | Module-to-module in same process |
| 3 | Redis Streams | 500K msg/s | <1ms | Persistent | Inter-service events, consumer groups |
| 4 | Redis Streams + NATS | 10M+ msg/s | <1ms | At-least-once | High-throughput signal routing |
| 5 | Kafka + NATS + Redis | 1M+ msg/s | ~5ms | Durable, replayable | Full event sourcing + audit + analytics |

### 5.2 Message Type Classification

| Type | Priority | Durability | Example | System |
|------|----------|------------|---------|--------|
| **Signal** | Critical | Transient | BUY signal for EURUSD | NATS (speed) |
| **Order** | Critical | Durable | Execute order, fill confirmation | Redis Streams (reliable) |
| **Market Data** | High | Transient | Tick update, candle close | Redis Pub/Sub (fire-and-forget) |
| **Risk Alert** | Critical | Durable | Drawdown breach, position limit | Redis Streams |
| **Analytics** | Low | Durable | P&L calculation, performance report | Kafka (replayable) |
| **Audit** | Low | Durable | Decision log, state change | Kafka (immutable) |

### 5.3 Scaling Rule

> **Don't add Kafka until you're processing >100K events/second consistently.** A single Redis instance handles millions of messages per second. Over-engineering the message bus wastes time better spent on strategy.

---

## 6. WebSocket & Connection Scaling

### 6.1 Connection Scaling Phases

| Connections | Challenge | Architecture |
|-------------|-----------|-------------|
| 1–5 | Nothing | Direct connection, simple reconnection |
| 5–20 | Connection management | Pool with heartbeat monitoring, exponential backoff |
| 20–100 | Rate limits, memory | Connection pooling, multiplexing, message buffering |
| 100–1000 | Broker limits, OS limits | Proxy layer, load balancing across broker accounts |
| 1000+ | Infrastructure | Dedicated market data service, institutional feeds |

### 6.2 Connection Resilience Pattern

```
┌──────────────────────────────────────────────────────┐
│            WebSocket Resilience Architecture          │
├──────────────────────────────────────────────────────┤
│                                                      │
│  ┌─────────────┐    ┌──────────────┐                │
│  │  WebSocket   │───▶│  Message     │                │
│  │  Connection  │    │  Buffer      │                │
│  │  Manager     │    │  (Ring Buf)  │                │
│  └──────┬──────┘    └──────┬───────┘                │
│         │                  │                         │
│    ┌────▼────┐        ┌────▼────┐                    │
│    │ Heartbeat│        │ Reconnect│                   │
│    │ Monitor  │        │ w/ Backoff│                  │
│    │ (15-25s) │        │ + Jitter  │                  │
│    └─────────┘        └──────────┘                   │
│                                                      │
│  Failure cascade:                                    │
│  1. WebSocket dies → buffer messages                 │
│  2. Attempt reconnect (1s, 2s, 4s, 8s + jitter)     │
│  3. If reconnect fails 5× → fallback to REST poll    │
│  4. REST poll at 1s intervals until WS restored      │
│  5. Replay buffered messages on reconnect            │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### 6.3 Critical Implementation Details

| Detail | Specification |
|--------|--------------|
| Heartbeat interval | 15–25 seconds (below most broker 30–60s timeout) |
| Reconnect backoff | Exponential: 1s, 2s, 4s, 8s, 16s (cap at 30s) |
| Jitter | ±20% random to avoid thundering herd |
| Buffer size | 10,000 messages per connection (ring buffer) |
| Fallback threshold | 5 consecutive reconnect failures → REST polling |
| Health check | TCP keepalive + application-level ping |

---

## 7. Strategy Scaling Framework

### 7.1 Strategy Capacity Model

Every strategy has a capacity ceiling — the capital at which its edge degrades due to market impact.

**Square-root market impact model:**
```
Impact ≈ σ × √(Q / V)

Where:
  σ = asset volatility
  Q = order size
  V = average daily volume
```

### 7.2 Capacity by Capital Level

| Capital | Lot Size | Market Impact | Strategy Viability |
|---------|----------|---------------|-------------------|
| $7 | 0.001 | Zero | Any strategy works if edge exists |
| $700 | 0.1 | Negligible | Same strategies, slightly better fills |
| $7,000 | 1.0 | Minimal on majors | Some exotic pairs start slipping |
| $70,000 | 10.0 | Noticeable on minors | Split orders, avoid illiquid hours |
| $700,000 | 100.0 | Significant | TWAP/VWAP execution, multi-broker |
| $7,000,000 | 1,000.0 | Major | Institutional execution required |

### 7.3 Strategy Types and Scalability

| Strategy Type | Scales Well? | Capacity Ceiling | Notes |
|--------------|-------------|-----------------|-------|
| Trend following | ✅ Yes | Very high | Directional, doesn't need precise entry |
| Mean reversion (majors) | ✅ Yes | High | Liquid pairs absorb large orders |
| Momentum | ✅ Yes | High | Wide stops accommodate slippage |
| Scalping | ❌ No | Low (~$50K) | Tight spreads required, impact kills edge |
| Arbitrage | ❌ No | Very low (~$10K) | Disappears with latency and competition |
| News trading | ❌ No | Low (~$100K) | Requires institutional-grade execution |

### 7.4 Strategy Portfolio Scaling

| Strategies | Management Approach | Architecture |
|------------|-------------------|-------------|
| 1 | Manual monitoring | Single process |
| 2–5 | Automated alerts | Dashboard + notification service |
| 5–15 | Portfolio manager | Capital allocation engine, correlation monitor |
| 15–50 | Portfolio optimization | Risk parity, regime-based allocation |
| 50+ | Full portfolio system | Mean-variance optimization, strategy generation |

**Portfolio scaling principles:**
1. Diversify by strategy type (trend + mean reversion + breakout)
2. Diversify by timeframe (M15 + H1 + H4 + D1)
3. Diversify by pair group (majors + crosses + exotics)
4. Monitor correlation — "diversified" strategies may correlate in crashes
5. Risk parity allocation, not equal capital per strategy

---

## 8. Position Sizing & Market Impact

### 8.1 Slippage Scaling Model

| Capital | Position | Pair | Avg Slippage | Impact on 1:1 R:R |
|---------|----------|------|-------------|-------------------|
| $7 | 0.001 lot | EURUSD | 0 pips | 0% |
| $700 | 0.1 lot | EURUSD | 0 pips | 0% |
| $7,000 | 1 lot | EURUSD | 0–0.2 pips | 0–0.2% |
| $70,000 | 10 lots | EURUSD | 0.2–1 pip | 0.2–1% |
| $700,000 | 100 lots | EURUSD | 1–3 pips | 1–3% |
| $7,000,000 | 1,000 lots | EURUSD | 3–10 pips | 3–10% |

### 8.2 Execution Algorithm Progression

| Phase | Capital | Execution Method | Architecture |
|-------|---------|-----------------|-------------|
| 1 | $7–$1K | Direct market order | Single API call |
| 2 | $1K–$10K | Limit orders with retry | Order manager with fallback |
| 3 | $10K–$100K | TWAP for orders >1 lot | Time-split execution engine |
| 4 | $100K–$1M | TWAP + VWAP + multi-broker | Execution algorithm service |
| 5 | $1M+ | DMA / FIX protocol | Institutional execution stack |

### 8.3 Execution Algorithm Service

```
┌─────────────────────────────────────────────────────┐
│           Execution Algorithm Service                │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Input: {pair, side, total_size, urgency}           │
│                                                     │
│  ┌─────────────────────────────────┐                │
│  │  Algorithm Selector             │                │
│  │  size < 1 lot  → Market/Limit   │                │
│  │  size 1-10     → TWAP           │                │
│  │  size 10-100   → TWAP + VWAP    │                │
│  │  size > 100    → Iceberg + TWAP │                │
│  └───────────────┬─────────────────┘                │
│                  │                                  │
│  ┌───────────────▼─────────────────┐                │
│  │  Order Splitter                 │                │
│  │  Split into N child orders      │                │
│  │  Schedule across T time window  │                │
│  └───────────────┬─────────────────┘                │
│                  │                                  │
│  ┌───────────────▼─────────────────┐                │
│  │  Slippage Monitor               │                │
│  │  If slippage > threshold:       │                │
│  │    Pause, wait, retry           │                │
│  └───────────────┬─────────────────┘                │
│                  │                                  │
│  Output: Average fill price, total slippage, TCA    │
└─────────────────────────────────────────────────────┘
```

---

## 9. Cost Scaling Model

### 9.1 Infrastructure Cost by Phase

| Phase | Capital | Monthly Cost | Cost as % of Capital | Components |
|-------|---------|-------------|---------------------|------------|
| 1 | $7 | $0 | 0% | Local machine, free APIs |
| 2 | $100 | $5–10 | 5–10% | VPS, free data, basic monitoring |
| 3 | $1K | $10–20 | 1–2% | VPS, PostgreSQL, Redis, alerts |
| 4 | $10K | $30–60 | 0.3–0.6% | TimescaleDB, Redis Streams, backtest server |
| 5 | $100K | $200–500 | 0.2–0.5% | Microservices, Kafka, co-located execution |
| 6 | $1M+ | $1,000+ | <0.1% | Full stack, dedicated team, DMA |

### 9.2 The $7 Cost Paradox

At $7, infrastructure costs can exceed account value:
- VPS ($5/mo) = 71% of account per month
- Need 71% monthly return just to cover costs — unsustainable

**Solution:** Run locally until account >$500. Treat $7 as a learning investment, not a profit center.

### 9.3 Break-Even Analysis

| Capital | Monthly Cost | Trades to Break Even ($10/trade) | Feasibility |
|---------|-------------|--------------------------------|-------------|
| $7 | $5 | 0.5 | ❌ Need 71% monthly return |
| $70 | $5 | 0.5 | ⚠️ Need 7% monthly return |
| $700 | $10 | 1 | ✅ Very achievable |
| $7,000 | $20 | 2 | ✅ Easy |
| $70,000 | $50 | 5 | ✅ Trivial |

### 9.4 Cost Optimization Rules

1. **Never invest in infrastructure until account >$500**
2. **Infrastructure cost must be <1% of monthly expected returns**
3. **Use free tiers aggressively** (OANDA API, Redis open-source, PostgreSQL)
4. **Batch AI inference calls** — prompt caching and local models reduce costs 10×
5. **Backtest locally first**, only use cloud for distributed parameter sweeps

### 9.5 Data Feed Cost Tiers

| Data Type | Free Tier | Paid Tier | When to Upgrade |
|-----------|-----------|-----------|-----------------|
| OHLCV candles | Broker API (included) | $0 | Never — broker data sufficient for retail |
| Tick data | Dukascopy historical | $50–200/mo | When tick-level backtesting accuracy needed |
| Level 2 / Order book | Rarely free | $100–500/mo | When strategy depends on order flow |
| News/Sentiment | RSS, free APIs | $50–500/mo | When trading news events |
| Alternative data | Twitter API, Reddit | $100–10K/mo | When building sentiment strategies |

---

## 10. Organizational Scaling

### 10.1 Team Evolution

| Stage | Team | Roles | Communication |
|-------|------|-------|--------------|
| Solo | 1 human | Everything | None |
| Solo + AI | 1 + AI agents | Human: strategy, AI: execution/monitoring | Low |
| Duo | 2 humans | Strategy + Engineering | Minimal |
| Small team | 3–5 | Strategy, Engineering, Risk, Ops | Standups required |
| Department | 10–20 | Specialized per function | Process and tooling required |

### 10.2 AI-First Scaling Advantage

Modern trading systems scale with AI agents instead of headcount:

| Function | Traditional | AI-First |
|----------|------------|----------|
| Monitoring | 1–2 FTEs | AI agent, 24/7 |
| Alert triage | Manual review | AI filters and prioritizes |
| Report generation | Manual compilation | AI auto-generates |
| Strategy hypothesis | Human research | AI proposes, human validates |
| Backtesting | Manual parameter tuning | AI-driven optimization |

**Result:** 1-person operation manages what previously required 5 people.

### 10.3 Automation Maturity Model

| Level | Description | Risk | Minimum Capital |
|-------|-------------|------|----------------|
| 0 | Manual trading with alerts | Human error | Any |
| 1 | Semi-automated (signals auto, execution manual) | Missed signals | $100+ |
| 2 | Fully automated with manual oversight | System failure | $1K+ |
| 3 | Fully automated with automated risk management | Model failure | $10K+ |
| 4 | Self-adjusting parameters | Overfitting | $100K+ |
| 5 | AI-managed portfolio | Black swan | $1M+ |

**Automation priority order (highest ROI first):**
1. Data collection and storage
2. Signal generation
3. Order execution
4. Risk management (stops, position sizing)
5. Monitoring and alerting
6. Reporting
7. Strategy generation (last — highest risk)

### 10.4 Multi-Market Scaling

| Market Expansion | Infrastructure Change | Strategy Change | Cost Impact |
|-----------------|----------------------|-----------------|-------------|
| Forex → Crypto | New API, 24/7 monitoring | Similar TA, different microstructure | Low (free APIs) |
| Forex → Stocks | Market hours, order types | Different session patterns | Medium |
| Forex → Futures | Contract rollover, margin | Similar but need roll logic | Medium |
| Forex → Options | Greeks, vol surface | Completely different | High |

---

## 11. Institutional-Grade Patterns

### 11.1 Patterns from Renaissance, Citadel, Two Sigma

| Pattern | Description | Alpha Stack Application |
|---------|-------------|------------------------|
| Event-driven architecture | Everything is an event, nothing polled | Core design principle |
| Microservices | Independent deployability | Phase 4 extraction |
| Feature stores | Pre-computed features shared across strategies | Shared indicator cache |
| A/B testing | Test strategies with small capital in production | Shadow mode execution |
| Risk as a service | Centralized risk across all strategies | Risk Gate agent |
| Full audit trail | Every decision logged and traceable | Event sourcing via Kafka |

### 11.2 What Institutional Systems Do That We Don't (Yet)

| Capability | When to Add | Complexity |
|-----------|-------------|-----------|
| Custom FPGA hardware | $10M+ (HFT only) | Extreme |
| Petabytes of alternative data | $1M+ | High |
| 300+ researchers | $100M+ AUM | Organizational |
| Direct market access (DMA) | $100K+ | Medium |
| Prime brokerage | $500K+ | Medium |
| FIX protocol | $100K+ | Medium |

---

## 12. Event-Driven Architecture

### 12.1 Why Event-Driven

| Pattern | Polling (Bad) | Event-Driven (Good) |
|---------|--------------|-------------------|
| Data arrival | Check every 100ms | React when data arrives |
| Latency | 0–100ms (avg 50ms) | <1ms |
| CPU usage | Constant overhead | Idle until event |
| Scalability | Linear degradation | Near-constant per event |

### 12.2 Event Flow: Tick to Trade

```
Tick arrives → Market Data Service
  → Publishes: {pair: "EURUSD", bid: 1.0850, ask: 1.0851, time: ...}
  → Signal Generator subscribes, updates indicators
    → If signal: Publishes: {pair: "EURUSD", direction: "BUY", confidence: 0.8}
    → Risk Manager subscribes, checks limits
      → If approved: Publishes: {pair: "EURUSD", action: "EXECUTE_BUY", size: 0.1}
      → Execution Engine subscribes, places order
        → Publishes: {pair: "EURUSD", order_id: "...", status: "FILLED", price: 1.0851}
        → Portfolio Manager subscribes, updates positions
        → Monitor subscribes, checks for anomalies
        → Journal subscribes, logs trade
```

### 12.3 Event Schema

```json
{
  "event_id": "uuid-v4",
  "event_type": "signal.generated",
  "timestamp": "2026-07-13T03:22:00.000Z",
  "source": "signal-generator",
  "version": "1.0",
  "payload": {
    "pair": "EURUSD",
    "direction": "BUY",
    "confidence": 0.78,
    "timeframe": "H4",
    "strategy": "trend-momentum-v2",
    "indicators": { ... }
  },
  "metadata": {
    "correlation_id": "uuid-for-tracing",
    "causation_id": "event-id-that-caused-this"
  }
}
```

---

## 13. Microservices Decomposition

### 13.1 Service Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    TRADING SYSTEM ARCHITECTURE               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Market   │  │ Signal   │  │ Execution│  │ Risk     │   │
│  │ Data     │──│ Generator│──│ Engine   │──│ Manager  │   │
│  │ Service  │  │ Service  │  │ Service  │  │ Service  │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│       │              │              │              │        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Event Bus (Redis Streams / Kafka)       │   │
│  └─────────────────────────────────────────────────────┘   │
│       │              │              │              │        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Portfolio│  │ Backtest │  │ Monitor  │  │ Reporting│   │
│  │ Manager  │  │ Engine   │  │ & Alert  │  │ Service  │   │
│  │ Service  │  │ Service  │  │ Service  │  │          │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 13.2 Service Responsibilities

| Service | Responsibility | Scaling Strategy |
|---------|---------------|-----------------|
| **Market Data** | Ingest, normalize, distribute price data | Horizontal (one per data source) |
| **Signal Generator** | Compute indicators, generate signals | Horizontal (one per strategy) |
| **Execution Engine** | Place/modify/cancel orders | Vertical (latency-sensitive) |
| **Risk Manager** | Position limits, drawdown, correlation | Vertical (single source of truth) |
| **Portfolio Manager** | Capital allocation, rebalancing | Vertical |
| **Backtest Engine** | Historical strategy testing | Horizontal (embarrassingly parallel) |
| **Monitor & Alert** | System health, anomaly detection | Horizontal |
| **Reporting** | P&L, performance metrics, compliance | Horizontal |

### 13.3 Extraction Rules

When to extract a module into a service:

| Signal | Threshold | Action |
|--------|-----------|--------|
| Independent scaling need | Different CPU/memory profile | Extract |
| Independent deployment | Changes deployed separately | Extract |
| Team boundary | Different team owns it | Extract |
| Failure isolation | Must not crash other services | Extract |
| Technology diversity | Needs different language/runtime | Extract |

**When NOT to extract:**
- Shared in-memory state is critical (keep together)
- Network latency between services would hurt performance
- Fewer than 3 independent deployments needed per week
- The module is <500 lines of code

---

## 14. CQRS & Read/Write Separation

### 14.1 Architecture

```
WRITE SIDE (Commands)          READ SIDE (Queries)
┌─────────────────┐           ┌─────────────────┐
│ Order Placement  │           │ Portfolio View   │
│ Position Updates │           │ P&L Dashboard    │
│ Risk Checks      │    ───→   │ Performance Report│
│ Signal Generation│  Events   │ Historical Analysis│
└─────────────────┘           └─────────────────┘
        │                              │
   Write Database              Read Database
   (PostgreSQL)               (Optimized for queries)
```

### 14.2 Why CQRS for Trading

| Side | Needs | Database | Optimization |
|------|-------|----------|-------------|
| **Write** | ACID, consistency, low latency | PostgreSQL | B-tree indexes, row-level locking |
| **Read** | Fast queries, aggregation, analytics | ClickHouse / Redis | Columnar storage, materialized views |

**Separation benefits:**
- Write-heavy order execution doesn't slow dashboards
- Can scale reads and writes independently
- Read side can use purpose-built databases for analytics
- Eventually consistent for dashboards (acceptable), strongly consistent for execution (required)

---

## 15. Phase-Based Scaling Roadmap

### Phase 1: Foundation ($7–$100)

| Layer | Technology | Cost |
|-------|-----------|------|
| Runtime | Python single-script | $0 |
| Database | SQLite | $0 |
| Message bus | Function calls | $0 |
| Data source | Broker API (OANDA/ICMarkets) | $0 |
| Monitoring | print() + manual | $0 |
| Deployment | Local machine | $0 |
| **Total** | | **$0/month** |

**Strategy scope:** 3–5 major pairs, single timeframe, 1–2 simple strategies, fixed micro lots.

### Phase 2: Growth ($100–$1K)

| Layer | Technology | Cost |
|-------|-----------|------|
| Runtime | Python modules | $0 |
| Database | PostgreSQL | $0 (self-hosted) |
| Cache | Redis | $0 (self-hosted) |
| Message bus | In-process event emitter | $0 |
| Monitoring | Telegram alerts | $0 |
| Deployment | VPS (systemd) | $5–10/mo |
| **Total** | | **$5–10/month** |

**Strategy scope:** 10 pairs, multi-timeframe (H1+H4+D1), 3–5 strategies, proper position sizing.

### Phase 3: Professional ($1K–$10K)

| Layer | Technology | Cost |
|-------|-----------|------|
| Runtime | Python + Rust (hot paths) | $0 |
| Database | TimescaleDB + Redis | $0 (self-hosted) |
| Message bus | Redis Streams | $0 (self-hosted) |
| Monitoring | Prometheus + Grafana | $0 (self-hosted) |
| Deployment | Docker Compose on VPS | $20–40/mo |
| CI/CD | GitHub Actions | $0 |
| **Total** | | **$20–40/month** |

**Strategy scope:** 28 pairs, full multi-TF, 5–10 strategies, portfolio management, walk-forward optimization.

### Phase 4: Institutional-Grade ($10K–$100K)

| Layer | Technology | Cost |
|-------|-----------|------|
| Runtime | Python + Rust + Go | $0 |
| Database | ClickHouse + PG + Redis | $50–100/mo |
| Message bus | Kafka + NATS | $50–100/mo |
| Monitoring | Full observability (Prometheus, Grafana, Jaeger) | $20–50/mo |
| Deployment | Kubernetes | $50–100/mo |
| Execution | Co-located server | $50–100/mo |
| **Total** | | **$200–500/month** |

**Strategy scope:** 50+ strategies, ML-enhanced, multi-market, algorithmic execution, alternative data.

### Phase 5: Scale ($100K+)

| Layer | Technology | Cost |
|-------|-----------|------|
| Runtime | Polyglot (Python, Rust, Go, C++) | — |
| Database | Distributed (ClickHouse + PG + Redis + Kafka) | $500+/mo |
| Execution | DMA / FIX protocol, co-location | $500+/mo |
| Monitoring | Dedicated team/AI agents | — |
| **Total** | | **$1,000+/month (<0.1% AUM)** |

**Strategy scope:** 100+ strategies, all liquid markets, real-time portfolio optimization, proprietary feature stores.

---

## 16. Scaling Decision Framework

### 16.1 The Decision Tree

```
Should I upgrade infrastructure?

1. Is my current system limiting my returns?
   NO  → Don't upgrade
   YES → Continue

2. Is the bottleneck technical or strategic?
   STRATEGIC → Focus on strategy development, not infrastructure
   TECHNICAL → Continue

3. Will the upgrade cost <10% of monthly expected returns?
   NO  → Wait until account grows
   YES → Upgrade

4. Can I implement the upgrade in <1 week?
   NO  → Break into smaller upgrades
   YES → Do it
```

### 16.2 Scaling What Works vs What Doesn't

**Scales well (invest confidently):**
- Strategy logic — core edge doesn't change with size
- Risk management framework — same principles, different parameters
- Data infrastructure — add layers, don't rebuild
- Monitoring/alerting — more strategies = more monitoring
- Backtesting framework — invest once, use forever
- Event-driven architecture — design for it from day one

**Doesn't scale (plan to replace):**
- Single-script architecture — unmanageable beyond 2–3 strategies
- SQLite — concurrent access, query speed limits
- Manual monitoring — alert fatigue, missed issues
- Fixed position sizing — doesn't adapt to growth
- REST polling — rate limits, latency, wasted resources
- Monolithic application — one change risks everything

---

## 17. Anti-Patterns & Guardrails

### 17.1 Anti-Patterns to Avoid

| Anti-Pattern | Description | Consequence |
|-------------|-------------|-------------|
| **Over-engineering early** | $7 account with Kubernetes | Wasted time, complexity without benefit |
| **Under-engineering late** | $100K account with manual monitoring | Risk breaches, missed opportunities |
| **Premature optimization** | Building for 100 pairs when trading 3 | Unnecessary complexity, slower iteration |
| **Infrastructure worship** | Focusing on infra instead of strategy | No edge = no returns regardless of infra |
| **Ignoring costs** | VPS eating small account profits | Negative returns from overhead |
| **Scaling without edge** | Adding infra to a losing strategy | Amplified losses |

### 17.2 Guardrails

| Guardrail | Rule | Enforcement |
|-----------|------|-------------|
| Cost cap | Infrastructure <1% of monthly expected returns | Pre-purchase cost check |
| Complexity cap | Can explain system to new team member in <1 hour | Regular architecture review |
| Deployment frequency | Must deploy at least weekly | CI/CD pipeline metrics |
| Rollback capability | Any deployment rollback in <5 minutes | Automated rollback testing |
| Test coverage | >80% for execution path | CI gate |
| Latency budget | Order execution <100ms end-to-end | Continuous latency monitoring |

---

## 18. Implementation Roadmap

### Phase 1: Foundation (Current)

| Task | Deliverable |
|------|-------------|
| Event-driven core | Internal event emitter for module communication |
| SQLite data layer | Schema for candles, trades, signals |
| Single-pair pipeline | WebSocket → indicators → signal → execution |
| Basic monitoring | Console output + Telegram alerts |
| Local deployment | Run script on local machine |

### Phase 2: Growth

| Task | Deliverable |
|------|-------------|
| PostgreSQL migration | Migration scripts, dual-write period |
| Multi-pair support | Connection pool, per-pair event loops |
| Multi-timeframe engine | TF hierarchy, scoring system |
| VPS deployment | systemd service, auto-restart |
| Redis cache | Hot data cache, indicator state |

### Phase 3: Professional

| Task | Deliverable |
|------|-------------|
| TimescaleDB migration | Hypertables for candle data |
| Redis Streams | Event bus for inter-module communication |
| Portfolio manager | Capital allocation, risk parity |
| Strategy correlation monitor | Cross-strategy drawdown detection |
| Docker Compose deployment | Containerized services |
| Prometheus + Grafana | Metrics dashboards, alerting |

### Phase 4: Institutional-Grade

| Task | Deliverable |
|------|-------------|
| Service extraction | Market Data, Signal, Execution as separate services |
| Kafka event sourcing | Durable event log, replay capability |
| ClickHouse analytics | Fast backtesting queries, performance reports |
| Execution algorithms | TWAP, VWAP, iceberg order support |
| Kubernetes orchestration | Auto-scaling, rolling deployments |
| Co-located execution | Low-latency server near broker |

### Phase 5: Scale

| Task | Deliverable |
|------|-------------|
| Full microservices | All components independently deployable |
| DMA / FIX protocol | Direct market access |
| Multi-market expansion | Crypto, indices, futures |
| ML signal enhancement | Feature stores, model serving |
| Team scaling | AI agents for monitoring, humans for strategy |

---

*Architecture document for ALPHA STACK scalability. All scaling decisions should follow the decision framework in Section 16. Scale strategy first, infrastructure second.*
