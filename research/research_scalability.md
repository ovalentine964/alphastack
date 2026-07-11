# Trading System Scalability Research

**Date:** 2026-07-11  
**Scope:** From $7 micro accounts to institutional-level capital  

---

## Table of Contents

1. [Technical Scalability](#1-technical-scalability)
2. [Strategy Scalability](#2-strategy-scalability)
3. [Cost Scaling](#3-cost-scaling)
4. [Organizational Scaling](#4-organizational-scalization)
5. [What Institutional Systems Do for Scale](#5-what-institutional-systems-do-for-scale)
6. [Alpha Stack Scaling Roadmap](#6-alpha-stack-scaling-roadmap)
7. [Key Takeaways & Decision Matrix](#7-key-takeaways--decision-matrix)

---

## 1. Technical Scalability

### 1.1 What Breaks Going from 1 Pair to 10 Pairs

| Dimension | 1 Pair | 10 Pairs | What Breaks |
|-----------|--------|----------|-------------|
| Data ingestion | 1 WebSocket stream | 10+ streams | Connection management, reconnection logic, rate limits |
| State management | Single dict/object | Concurrent state machines | Race conditions, partial updates, inconsistent snapshots |
| Signal generation | Linear scan | N×N correlation checks | CPU spikes during volatile moments |
| Order management | Simple queue | Multi-pair position correlation | Margin calculation complexity, hedging conflicts |
| Monitoring | One dashboard | Need aggregation layer | Alert fatigue, missing cross-pair patterns |

**Critical failure modes:**

- **Rate limiting:** Most broker APIs (OANDA, IC Markets) rate-limit at 20-120 requests/minute. With 10 pairs × 5 timeframes × polling every tick = you hit limits fast.
- **State synchronization:** When EURUSD and GBPUSD both trigger signals simultaneously, execution order matters. Without proper locking, you get duplicate entries or missed exits.
- **Memory pressure:** Each pair's tick history, indicator state, and order book consumes ~10-50MB. At 10 pairs with multi-timeframe, you're at 500MB-2GB just for runtime state.

**Solutions:**
- Use WebSocket streams (push) instead of REST polling (pull)
- Implement per-pair event loops with shared state via message bus
- Pre-compute cross-pair correlations in batch, not real-time
- Use connection pooling with automatic reconnection and backoff

### 1.2 What Breaks Going from 1 Timeframe to Multi-Timeframe

| Aspect | Single TF | Multi-TF | Challenge |
|--------|-----------|----------|-----------|
| Data storage | 1 candle series per pair | 3-5× candle series | Storage and indexing |
| Signal alignment | Trivial | Time synchronization | M1 candle completes at different wall-clock times than H4 |
| Indicator computation | O(n) per bar | O(n × tf_count) | CPU cost scales linearly |
| Conflict resolution | N/A | M1 says buy, H4 says sell | Need hierarchy/weighting system |

**The alignment problem is the hardest part.** When M15 shows a buy signal but H4 is bearish, you need:
1. A clear timeframe hierarchy (higher TF overrides lower)
2. Or a scoring system (weighted consensus)
3. Or separate strategies per TF with portfolio-level risk management

**Implementation pattern:**
```
Event: M15 candle closes
  → Compute M15 indicators
  → Fetch cached H1/H4 state (pre-computed)
  → Run signal logic with multi-TF context
  → Emit trade signal if consensus threshold met
```

### 1.3 What Breaks When Data Volume Increases 100×

| Scale | Data Volume | Bottleneck | Solution |
|-------|-------------|------------|----------|
| 1 pair, 1 TF, 1 year | ~100K bars | Nothing | SQLite is fine |
| 10 pairs, 3 TFs, 1 year | ~10M bars | Query speed | PostgreSQL + indexing |
| 28 pairs, 5 TFs, 5 years | ~500M bars | Storage + query | TimescaleDB / ClickHouse |
| Full tick data, 28 pairs, 1 year | ~50B ticks | Everything | Distributed storage, aggregation |

**Database scaling strategies:**

| Strategy | When to Use | Trade-off |
|----------|-------------|-----------|
| **SQLite → PostgreSQL** | >1 pair, need concurrent reads | More setup, but proper ACID |
| **TimescaleDB hypertables** | Time-series dominant workload | Automatic partitioning by time, 10-100× faster than vanilla PG for range queries |
| **ClickHouse** | Analytics-heavy (backtesting) | Blazing fast reads, weaker writes, no ACID |
| **Redis** | Hot data (last N ticks, live indicators) | In-memory, volatile, perfect for cache layer |
| **Sharding by pair** | >50 pairs, independent data | Complexity of cross-pair queries |
| **Partitioning by time** | Historical data archival | Hot/warm/cold storage tiers |

**Recommended architecture by scale:**
```
Phase 1 (1-3 pairs):   SQLite + in-memory cache
Phase 2 (3-10 pairs):  PostgreSQL + Redis cache
Phase 3 (10-28 pairs): TimescaleDB + Redis Streams
Phase 4 (institutional): ClickHouse (analytics) + PostgreSQL (OLTP) + Redis (hot cache) + Kafka (event bus)
```

### 1.4 Horizontal vs Vertical Scaling

| Approach | Pros | Cons | Best For |
|----------|------|------|----------|
| **Vertical (bigger server)** | Simple, no distributed complexity | Hard ceiling, single point of failure | Phase 1-2, <$10K capital |
| **Horizontal (more servers)** | Near-unlimited scale, redundancy | Network latency, state sync, deployment complexity | Phase 3+, professional ops |

**Trading-specific considerations:**

- **Latency matters more than throughput** for execution. A single fast server beats a distributed slow cluster for order entry.
- **Throughput matters more than latency** for backtesting. Distributed backtesting across parameter ranges is embarrassingly parallel.
- **Hybrid approach:** Single execution server + distributed backtesting cluster.

**Vertical scaling limits:**
- CPU: ~128 cores (current max single-socket)
- RAM: ~2TB (current max single server)
- Network: ~100Gbps (current max NIC)
- For most retail trading, a single $50-200/month VPS handles everything through Phase 3.

### 1.5 Message Queue Scaling

| System | Throughput | Latency | Durability | Best For |
|--------|-----------|---------|------------|----------|
| **Redis Pub/Sub** | 1M+ msg/s | <1ms | None (fire-and-forget) | Real-time signals, ephemeral data |
| **Redis Streams** | 500K msg/s | <1ms | Persistent, consumer groups | Event sourcing, reliable delivery |
| **NATS JetStream** | 10M+ msg/s | <1ms | At-least-once | High-throughput event bus |
| **RabbitMQ** | 50K msg/s | ~5ms | Full ACK, routing | Complex routing, task queues |
| **Apache Kafka** | 1M+ msg/s | ~5ms | Durable, replayable | Event sourcing, audit trail, analytics |

**For trading systems:**

```
Phase 1-2: Redis Streams (simple, fast, good enough)
Phase 3:   Redis Streams + NATS for inter-service communication
Phase 4:   Kafka for event sourcing + audit + analytics pipeline
           NATS for real-time signal routing
           Redis for hot cache
```

**Key insight:** Most retail trading systems over-engineer their message infrastructure. A single Redis instance handles millions of messages per second. You don't need Kafka until you're processing >100K events/second consistently.

### 1.6 WebSocket Connection Scaling

| Connections | Challenge | Solution |
|-------------|-----------|----------|
| 1-5 | Nothing | Direct connection |
| 5-20 | Connection management | Reconnection logic, heartbeat monitoring |
| 20-100 | Rate limits, memory | Connection pooling, multiplexing |
| 100-1000 | Broker limits, OS limits | Proxy layer, load balancing across broker accounts |
| 1000+ | Infrastructure | Dedicated market data service, institutional feeds |

**Critical implementation details:**
- **Heartbeat/ping:** Most WebSocket connections die after 30-60s of inactivity. Implement ping every 15-25s.
- **Reconnection with backoff:** Exponential backoff (1s, 2s, 4s, 8s...) with jitter to avoid thundering herd.
- **Message buffering:** Buffer messages during reconnection, replay on reconnect.
- **Graceful degradation:** If WebSocket dies, fall back to REST polling temporarily.

---

## 2. Strategy Scalability

### 2.1 Do Strategies That Work at $7 Work at $700? At $70,000?

**The short answer: Most strategies have a "capacity ceiling."**

| Capital Level | Lot Size | Market Impact | Strategy Viability |
|---------------|----------|---------------|-------------------|
| $7 | 0.001 (micro) | Zero | Almost any strategy works if edge exists |
| $70 | 0.01 (mini) | Negligible | Same strategies, slightly better fills |
| $700 | 0.1 | Negligible | Still fine for major pairs |
| $7,000 | 1.0 (standard) | Minimal on majors | Some exotic pairs start slipping |
| $70,000 | 10.0 | Noticeable on minors | Need to split orders, avoid illiquid hours |
| $700,000 | 100.0 | Significant | Must use TWAP/VWAP execution, multi-broker |
| $7,000,000 | 1000.0 | Major | Institutional execution required |

**The $7 special case:**
- At $7, you're trading 0.001 lots (100 units of base currency)
- Spread costs are proportionally HUGE (1 pip on EURUSD = ~10% of a $7 account per standard lot equivalent)
- Minimum trade size constraints may force you into suboptimal position sizes
- The real challenge at $7 isn't strategy — it's surviving the cost structure

**What scales well from small to large:**
- Trend following (directional, doesn't need precise entry)
- Mean reversion on liquid pairs (EURUSD, USDJPY)
- Momentum strategies with wide stops

**What doesn't scale:**
- Scalping (tight spreads required, market impact kills it at scale)
- Arbitrage (disappears with latency and competition)
- News trading (requires institutional-grade execution speed)

### 2.2 Position Sizing Impact on Market Microstructure

**The square-root market impact model:**

```
Impact ≈ σ × √(Q / V)
```

Where:
- σ = volatility of the asset
- Q = order size
- V = average daily volume

**Practical implications:**

| Order Size (lots) | % of Typical EURUSD Volume | Expected Slippage |
|--------------------|---------------------------|-------------------|
| 0.01 | 0.000001% | 0 pips |
| 0.1 | 0.00001% | 0 pips |
| 1.0 | 0.0001% | 0-0.1 pips |
| 10.0 | 0.001% | 0.1-0.5 pips |
| 100.0 | 0.01% | 0.5-2 pips |
| 1,000.0 | 0.1% | 2-10 pips |
| 10,000.0 | 1% | 10-50 pips (requires algo execution) |

**Key insight:** For retail traders (up to ~$100K capital), market impact is negligible on major forex pairs. The real cost is the spread, not slippage.

### 2.3 Slippage Scaling with Position Size

**Real-world slippage data (approximate):**

| Capital | Position | Pair | Avg Slippage | Impact on 1:1 R:R Trade |
|---------|----------|------|-------------|------------------------|
| $7 | 0.001 lot | EURUSD | 0 pips | 0% |
| $700 | 0.1 lot | EURUSD | 0 pips | 0% |
| $7,000 | 1 lot | EURUSD | 0-0.2 pips | 0-0.2% |
| $70,000 | 10 lots | EURUSD | 0.2-1 pip | 0.2-1% |
| $700,000 | 100 lots | EURUSD | 1-3 pips | 1-3% |
| $7,000,000 | 1000 lots | EURUSD | 3-10 pips | 3-10% |

**Mitigation strategies as capital grows:**
1. **TWAP (Time-Weighted Average Price):** Split large orders into smaller chunks over time
2. **VWAP (Volume-Weighted Average Price):** Execute proportional to market volume
3. **Iceberg orders:** Show only small portions to the market
4. **Multi-broker execution:** Spread orders across brokers
5. **Dark pools / ECN:** Access deeper liquidity

### 2.4 How to Adapt Strategies as Capital Grows

**The adaptation playbook:**

| Phase | Capital | Strategy Adaptation |
|-------|---------|-------------------|
| 1 | $7-$100 | Focus on edge discovery, not execution. Use fixed micro lots. |
| 2 | $100-$1K | Introduce proper position sizing (% risk per trade). Start tracking slippage. |
| 3 | $1K-$10K | Multi-pair diversification. Start monitoring spread costs per pair. |
| 4 | $10K-$100K | Implement TWAP for orders >1 lot. Consider multiple broker accounts. |
| 5 | $100K-$1M | Algorithmic execution. Multi-broker routing. Strategy capacity analysis. |
| 6 | $1M+ | Institutional execution. Prime brokerage. Direct market access. |

### 2.5 Strategy Capacity Analysis

**How to calculate strategy capacity:**

```
Capacity = (Average Daily Volume × Acceptable Participation Rate) / Strategy's Average Daily Trades

Where Acceptable Participation Rate:
- Conservative: 1% of daily volume
- Moderate: 5% of daily volume  
- Aggressive: 10% of daily volume (significant market impact)
```

**Example: EURUSD scalping strategy**
- EURUSD average daily volume: ~$1.5 trillion
- Strategy makes 20 trades/day
- Acceptable participation: 1% = $15 billion/day
- Per trade capacity: $15B / 20 = $750M per trade
- At 100:1 leverage: $7.5M account capacity

**Example: Exotic pair strategy (USDTRY)**
- USDTRY average daily volume: ~$50 billion
- Strategy makes 10 trades/day
- Acceptable participation: 1% = $500M/day
- Per trade capacity: $500M / 10 = $50M per trade
- At 100:1 leverage: $500K account capacity

**Key insight:** Strategy capacity is pair-specific and strategy-type-specific. A strategy that works on EURUSD at $1M may hit capacity limits at $100K on exotic pairs.

---

## 3. Cost Scaling

### 3.1 VPS Costs at Different Scales

| Scale | Requirements | Monthly Cost | Recommended Providers |
|-------|-------------|-------------|----------------------|
| $7 account | 1 CPU, 1GB RAM, basic | $3-5/mo | Hetzner CX11, Vultr |
| $100 account | 2 CPU, 2GB RAM | $5-10/mo | Hetzner CX21, DigitalOcean |
| $1K account | 2 CPU, 4GB RAM | $10-20/mo | Hetzner CX31, AWS Lightsail |
| $10K account | 4 CPU, 8GB RAM | $20-40/mo | Hetzner CX41, AWS EC2 |
| $100K account | 8 CPU, 16GB RAM, low latency | $40-100/mo | AWS EC2 (near exchange), dedicated server |
| $1M+ account | Dedicated server, co-location | $200-1000/mo | Exchange co-location, bare metal |

**The cost paradox at $7:**
- VPS cost ($5/mo) = 71% of account value per month
- Need 71% monthly return just to cover infrastructure
- **Solution:** Run on local machine initially, or use free tier cloud credits

**Latency considerations:**
- For most retail strategies (holding time >1 minute), VPS location doesn't matter
- For scalping (<1 minute holds), co-locate near broker's server
- For HFT (<1 second), co-locate near exchange matching engine

### 3.2 Data Feed Costs

| Data Type | Free Tier | Paid Tier | When to Upgrade |
|-----------|-----------|-----------|-----------------|
| **OHLCV candles** | Broker API (OANDA, ICMarkets) | $0 (included) | Never — broker data is fine for retail |
| **Tick data** | Limited history | $50-200/mo (Tick Data Suite) | When backtesting requires tick-level accuracy |
| **Level 2 / Order book** | Rarely free | $100-500/mo | When strategies depend on order flow |
| **News/Sentiment** | RSS feeds, free APIs | $50-500/mo (Refinitiv, Bloomberg) | When trading news events |
| **Alternative data** | Free (Twitter API, Reddit) | $100-10K/mo | When building sentiment strategies |

**Free data sources that are actually good:**
- **OANDA API:** Real-time forex, no extra cost
- **Yahoo Finance:** Delayed but free for backtesting
- **Dukascopy:** Free tick data download (historical)
- **Binance API:** Free crypto tick data
- **FRED:** Free macroeconomic data

### 3.3 API Costs

| API Type | Free Tier | Paid Tier | Scaling Concern |
|----------|-----------|-----------|-----------------|
| **Broker API** | Usually free | Per-trade commission | Scales linearly with trades |
| **Market data** | Rate-limited free | $0-200/mo | Rate limits are the bottleneck |
| **AI inference (GPT-4, Claude)** | $5-20/mo (light use) | $50-500/mo | Prompt caching, batching reduces costs |
| **News API** | 100 req/day free | $50-200/mo | Cache aggressively |
| **Backtesting cloud** | Local is free | $50-200/mo (QuantConnect) | Parallelize locally first |

**AI model inference cost scaling:**

| Usage Level | Monthly Cost | Optimization |
|-------------|-------------|-------------|
| Signal analysis (10 calls/day) | $5-10 | Use smaller models (GPT-4-mini) |
| Continuous monitoring (100 calls/day) | $50-100 | Batch, cache, use local models |
| Full automation (1000+ calls/day) | $200-500 | Local LLM, rule-based pre-filtering |

### 3.4 How Costs Per Trade Decrease with Volume

**Commission structure (typical forex broker):**

| Monthly Volume | Commission per lot | Spread markup | Total cost per lot |
|---------------|-------------------|---------------|-------------------|
| <10 lots | $7.00 | 1.2 pips | ~$19 |
| 10-100 lots | $5.50 | 1.0 pips | ~$15.50 |
| 100-1000 lots | $4.00 | 0.8 pips | ~$12 |
| 1000+ lots | $3.00 | 0.5 pips | ~$8 |

**Break-even analysis at different capital levels:**

| Capital | Monthly Cost (VPS + data) | Trades/month needed to break even (at $10/trade profit) | Feasibility |
|---------|--------------------------|------------------------------------------------------|-------------|
| $7 | $5 | 0.5 trades | ❌ Need 71% monthly return |
| $70 | $5 | 0.5 trades | ⚠️ Need 7% monthly return |
| $700 | $10 | 1 trade | ✅ Very achievable |
| $7,000 | $20 | 2 trades | ✅ Easy |
| $70,000 | $50 | 5 trades | ✅ Trivial |
| $700,000 | $200 | 20 trades | ✅ Infrastructure pays for itself |

**The $7 reality check:**
At $7, the economics are brutal. You need:
1. A strategy with >70% monthly returns (unsustainable)
2. OR zero infrastructure costs (run locally, use free APIs)
3. OR treat it as a learning investment, not a profit center

**Practical advice:** Don't invest in infrastructure until your account is >$500. Before that, run everything locally.

---

## 4. Organizational Scaling

### 4.1 From Solo Trader to Team

| Stage | Team Size | Roles | Communication Overhead |
|-------|-----------|-------|----------------------|
| Solo | 1 | Everything | None |
| Solo + AI | 1 + AI agents | Human: strategy, AI: execution, monitoring | Low |
| Duo | 2 | Strategy + Execution/Engineering | Minimal |
| Small team | 3-5 | Strategy, Engineering, Risk, Operations | Moderate — need standups |
| Department | 10-20 | Specialized roles per function | Significant — need process |

**The AI-first scaling advantage:**
Modern trading systems can scale with AI agents instead of humans:
- AI handles monitoring, alerting, reporting
- AI generates and tests strategy hypotheses
- Human focuses on strategy design and risk oversight
- Result: 1-person operation can manage what previously required 5 people

### 4.2 From One Strategy to Strategy Portfolio

| Strategies | Management Approach | Risk Concern |
|------------|-------------------|-------------|
| 1 | Manual monitoring | Single point of failure |
| 2-3 | Spreadsheet tracking | Correlation risk |
| 5-10 | Dashboard + automated alerts | Drawdown correlation, capital allocation |
| 10-50 | Portfolio management system | Strategy decay detection, rebalancing |
| 50+ | Full portfolio optimization (mean-variance) | Model risk, overfitting to historical data |

**Portfolio scaling principles:**
1. **Diversify by strategy type:** Trend + mean reversion + breakout
2. **Diversify by timeframe:** M15 + H1 + H4 + D1
3. **Diversify by pair group:** Majors + crosses + exotics
4. **Monitor correlation:** Strategies that are "diversified" may correlate in crashes
5. **Capital allocation:** Risk parity across strategies, not equal allocation

### 4.3 From One Market to Multi-Market

| Market | Infrastructure Change | Strategy Change | Cost Impact |
|--------|----------------------|-----------------|-------------|
| Forex → Crypto | New API, 24/7 monitoring | Similar TA, different microstructure | Low (free APIs) |
| Forex → Stocks | Market hours, order types | Different session patterns | Medium (data costs) |
| Forex → Futures | Contract rollover, margin rules | Similar but need roll logic | Medium |
| Forex → Options | Greeks, vol surface | Completely different | High (education + data) |

**Multi-market scaling challenges:**
- **Time zone management:** Forex is 24/5, stocks are session-based
- **Correlation across markets:** USD strength affects forex AND stocks
- **Capital allocation:** How much to allocate to each market?
- **Infrastructure:** Different APIs, data formats, order types per market

### 4.4 From Manual to Fully Automated

**The automation maturity model:**

| Level | Description | Risk | Typical Capital |
|-------|-------------|------|----------------|
| 0 | Manual trading with alerts | Human error | Any |
| 1 | Semi-automated (signals auto-generated, manual execution) | Missed signals | $100+ |
| 2 | Fully automated with manual oversight | System failure | $1K+ |
| 3 | Fully automated with automated risk management | Model failure | $10K+ |
| 4 | Self-adjusting (strategy parameters adapt) | Overfitting | $100K+ |
| 5 | AI-managed portfolio (strategy generation + execution) | Black swan | $1M+ |

**What to automate first (highest ROI):**
1. **Data collection and storage** — Eliminate manual data gathering
2. **Signal generation** — Consistent, emotionless
3. **Order execution** — Speed and precision
4. **Risk management** — Stop-losses, position sizing
5. **Monitoring and alerting** — 24/7 oversight
6. **Reporting** — Performance tracking
7. **Strategy generation** — Last to automate, highest risk

---

## 5. What Institutional Systems Do for Scale

### 5.1 How Renaissance Technologies, Citadel, Two Sigma Scale

**Renaissance Technologies (Medallion Fund):**
- ~66% annual returns (before fees) for 30+ years
- Secret sauce: Signal-to-noise ratio, not HFT
- Infrastructure: Custom hardware, co-located servers
- Data: Petabytes of alternative data (satellite imagery, weather, shipping data)
- Team: 300+ researchers (mathematicians, physicists, CS PhDs)
- Key lesson: **Data advantage > algorithmic advantage at scale**

**Citadel Securities:**
- Market maker, not directional trader
- Processes ~25% of US equity volume
- Infrastructure: Sub-microsecond latency, custom FPGA hardware
- Key lesson: **Infrastructure IS the edge for market makers**

**Two Sigma:**
- Systematic, data-driven
- Heavy use of machine learning
- Open-source contributions (Zipline, etc.)
- Key lesson: **Engineering culture + ML at scale**

**Common patterns across all three:**
1. **Event-driven architecture** — Everything is an event, nothing is polled
2. **Microservices** — Each component is independently deployable and scalable
3. **Feature stores** — Pre-computed features shared across strategies
4. **A/B testing infrastructure** — Test strategies in production with small capital
5. **Risk management as a service** — Centralized risk across all strategies
6. **Audit trail** — Every decision is logged and traceable

### 5.2 Microservices Architecture for Trading

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

**Service breakdown:**

| Service | Responsibility | Scaling Strategy |
|---------|---------------|-----------------|
| **Market Data** | Ingest, normalize, distribute price data | Horizontal (one per data source) |
| **Signal Generator** | Compute indicators, generate signals | Horizontal (one per strategy) |
| **Execution Engine** | Place/modify/cancel orders | Vertical (latency-sensitive) |
| **Risk Manager** | Position limits, drawdown checks, correlation | Vertical (single source of truth) |
| **Portfolio Manager** | Capital allocation, rebalancing | Vertical |
| **Backtest Engine** | Historical strategy testing | Horizontal (embarrassingly parallel) |
| **Monitor & Alert** | System health, anomaly detection | Horizontal |
| **Reporting** | P&L, performance metrics, compliance | Horizontal |

### 5.3 Event-Driven Architecture

**Why event-driven for trading:**

| Pattern | Polling (Bad) | Event-Driven (Good) |
|---------|--------------|-------------------|
| Data arrival | Check every 100ms | React when data arrives |
| Latency | 0-100ms (average 50ms) | <1ms |
| CPU usage | Constant polling overhead | Idle until event |
| Scalability | Linear degradation | Near-constant per event |

**Event flow example:**
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
```

### 5.4 CQRS Pattern for Read/Write Separation

**Command Query Responsibility Segregation (CQRS):**

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

**Why CQRS matters for trading:**
- **Write side:** Needs ACID, consistency, low latency (order execution)
- **Read side:** Needs fast queries, aggregation, analytics (dashboards, reports)
- **Separation:** Write-heavy operations don't slow down read-heavy dashboards
- **Scalability:** Can scale reads and writes independently

**Implementation:**
- Write to PostgreSQL (ACID, consistency)
- Publish events to message bus
- Read side materializes views in optimized store (Redis for hot data, ClickHouse for analytics)
- Eventually consistent (acceptable for dashboards, not for execution)

---

## 6. Alpha Stack Scaling Roadmap

### Phase 1: Foundation ($7 - $100)

**Infrastructure:**
- Run locally (laptop/desktop) — save the $5/mo VPS cost
- SQLite for data storage
- Python single-script architecture
- Broker API for data (OANDA/ICMarkets free tier)

**Strategy:**
- 3-5 major pairs (EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD)
- Single timeframe (H1 or H4)
- 1-2 simple strategies (moving average crossover, RSI bounce)
- Fixed position size (0.01 lot minimum)

**What you learn:**
- API integration
- Basic strategy logic
- Order management
- The reality of spreads and commissions at micro scale

**Costs:** ~$0/month (run locally, free APIs)

**Key milestone:** Profitable for 3 consecutive months on demo, then live with $7-50.

---

### Phase 2: Growth ($100 - $1,000)

**Infrastructure upgrades:**
- VPS ($5-10/mo) for 24/5 operation
- PostgreSQL (replace SQLite for concurrent access)
- Redis for caching (hot data, indicator state)
- Basic monitoring (Telegram/Discord alerts)
- Automated daily reports

**Strategy upgrades:**
- 10 pairs (add crosses: EURGBP, EURJPY, GBPJPY, etc.)
- Multi-timeframe analysis (H1 + H4 + D1 alignment)
- 3-5 strategies with different logic
- Proper position sizing (1-2% risk per trade)
- Basic correlation awareness

**What changes:**
- Need proper error handling and reconnection logic
- Need logging and audit trail
- Need backtesting framework
- Strategy performance tracking becomes essential

**Costs:** ~$10-20/month

**Key milestone:** Consistent monthly returns, proper risk management, automated execution.

---

### Phase 3: Professional ($1,000 - $10,000)

**Infrastructure upgrades:**
- TimescaleDB for time-series data
- Redis Streams for event bus
- Dedicated backtesting server
- Multi-broker support (redundancy)
- Proper CI/CD pipeline
- Automated strategy health monitoring

**Strategy upgrades:**
- 28 pairs (all major + cross pairs)
- Multi-timeframe with scoring system
- 5-10 strategies in portfolio
- Strategy correlation monitoring
- Automated capital allocation (risk parity)
- Walk-forward optimization
- Regime detection (trending vs ranging)

**What changes:**
- Strategy capacity analysis becomes relevant
- Need to track slippage vs backtest expectations
- Need automated strategy decay detection
- Portfolio-level drawdown management

**Costs:** ~$30-60/month

**Key milestone:** Portfolio-level risk management, strategy diversification, automated rebalancing.

---

### Phase 4: Institutional-Grade ($10,000 - $100,000)

**Infrastructure upgrades:**
- Microservices architecture
- Kafka for event sourcing + audit trail
- ClickHouse for analytics
- Kubernetes for service orchestration
- Co-located execution server (near broker)
- Dedicated market data infrastructure
- Full observability (Prometheus, Grafana)

**Strategy upgrades:**
- 50+ strategies across multiple logic families
- Machine learning signal enhancement
- Alternative data integration (sentiment, order flow)
- Dynamic strategy allocation based on regime
- Multi-market (forex + crypto + indices)
- Execution algorithms (TWAP, VWAP)

**What changes:**
- Market impact becomes measurable
- Need algorithmic execution
- Need prime brokerage relationships
- Regulatory considerations emerge
- Tax optimization becomes important

**Costs:** ~$200-500/month

**Key milestone:** Institutional-grade execution, multi-market portfolio, ML-enhanced signals.

---

### Phase 5: Scale ($100,000+)

**Infrastructure:**
- Full event-driven microservices
- Custom hardware for latency-sensitive paths
- Direct market access (DMA)
- Co-location at exchange
- Dedicated team (or AI agents) for monitoring
- Full compliance and audit systems

**Strategy:**
- 100+ strategies across all liquid markets
- Real-time portfolio optimization
- Cross-asset correlation trading
- Volatility surface trading
- Custom execution algorithms
- Proprietary feature stores

**Costs:** $1,000+/month (but <0.1% of AUM)

---

## 7. Key Takeaways & Decision Matrix

### What Scales

| Component | Scales Well? | Notes |
|-----------|-------------|-------|
| Strategy logic | ✅ Yes | Core edge doesn't change with size |
| Risk management framework | ✅ Yes | Same principles, different parameters |
| Data infrastructure | ✅ Yes | Add layers as needed, don't rebuild |
| Monitoring/alerting | ✅ Yes | More strategies = more monitoring |
| Backtesting framework | ✅ Yes | Invest once, use forever |
| Event-driven architecture | ✅ Yes | Design for it from day 1 |

### What Doesn't Scale

| Component | Scales? | What Breaks |
|-----------|---------|-------------|
| Single-script architecture | ❌ | Unmanageable beyond 2-3 strategies |
| SQLite | ❌ | Concurrent access, query speed |
| Manual monitoring | ❌ | Alert fatigue, missed issues |
| Fixed position sizing | ❌ | Doesn't adapt to account growth |
| REST polling for data | ❌ | Rate limits, latency, wasted resources |
| Monolithic application | ❌ | Deploying one change risks everything |

### The Scaling Decision Matrix

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

### Anti-Patterns to Avoid

1. **Over-engineering early:** A $7 account doesn't need Kubernetes
2. **Under-engineering late:** A $100K account needs proper risk management
3. **Premature optimization:** Don't optimize for 1000 pairs when you trade 3
4. **Infrastructure worship:** The edge is in strategy, not infrastructure
5. **Ignoring costs:** Infrastructure costs can eat small account profits
6. **Scaling without edge:** No amount of infrastructure fixes a losing strategy

### The Golden Rule of Scaling

> **Scale your strategy first, infrastructure second.**
> 
> A profitable strategy on a laptop beats an unprofitable strategy on a $10K server.
> 
> Prove the edge → Automate it → Scale it → Optimize infrastructure.

---

## Appendix: Technology Stack Recommendations by Phase

| Component | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|-----------|---------|---------|---------|---------|
| **Language** | Python | Python | Python + Rust (hot paths) | Python + Rust + Go |
| **Database** | SQLite | PostgreSQL | TimescaleDB + Redis | ClickHouse + PG + Redis |
| **Message Bus** | None | None | Redis Streams | Kafka + NATS |
| **Cache** | In-memory dict | Redis | Redis | Redis Cluster |
| **Monitoring** | print() + Telegram | Telegram + basic metrics | Prometheus + Grafana | Full observability stack |
| **Deployment** | Local script | systemd on VPS | Docker Compose | Kubernetes |
| **CI/CD** | Manual | Git + manual deploy | GitHub Actions | Full pipeline |
| **Backtesting** | Pandas vectorized | Custom framework | Distributed backtest | Cloud-scale backtest |
| **Execution** | REST API | REST API | WebSocket + REST | DMA / FIX protocol |

---

*Document generated: 2026-07-11*  
*Next review: Update after Phase 2 completion*
