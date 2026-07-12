# Alpha Stack — Execution Algorithms Architecture

**Version:** 1.0
**Date:** 2026-07-13
**Status:** Architecture Design
**Dependencies:** Broker Abstraction Layer, TCA Engine, Risk Management

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Design Philosophy](#2-design-philosophy)
3. [System Architecture](#3-system-architecture)
4. [Execution Rules for $7 Capital](#4-execution-rules-for-7-capital)
5. [Algorithm Catalog](#5-algorithm-catalog)
6. [Evolution Roadmap](#6-evolution-roadmap)
7. [MT5-Specific Configuration](#7-mt5-specific-configuration)
8. [Integration Points](#8-integration-points)
9. [Implementation Roadmap](#9-implementation-roadmap)

---

## 1. Executive Summary

### Problem

At $7 capital trading 0.01 lots, traditional execution algorithms (TWAP, VWAP, iceberg) are unnecessary and counterproductive. Order size is too small to move markets or suffer meaningful slippage. The real execution concerns are spread cost, entry/exit timing, and avoiding catastrophic mistakes during news events.

### Solution

A **tiered execution system** that starts with simple, high-impact rules at $7 and progressively adds algorithmic sophistication as capital grows. The architecture supports both paths — the execution engine decides which to use based on account size and order characteristics.

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| $7 execution | 3 simple rules (spread filter, session filter, news filter) | Over-engineering 0.01 lot execution wastes dev time |
| Order preference | Limit orders default, market only for breakouts | Limit orders may get mid-price fills; every cent matters |
| Algorithm activation | Capital-gated ($500+ for TWAP, $5K+ for VWAP) | Market impact only matters at scale |
| Slippage cap | 3 pips max deviation | At $7, 30-pip slippage = 43% capital loss |
| Session filter | London-NY overlap only (13:00–17:00 UTC) | Tightest spreads, 60–70% of daily volume |

---

## 2. Design Philosophy

### P1: Signal Quality > Execution Quality
At $7, getting the right trade matters 25× more than getting the perfect fill. A 2-pip slippage ($0.20) is noise compared to a 50-pip stop ($5.00). Optimize signals, not execution microstructure.

### P2: Simple Rules, Zero Ambiguity
Three hard rules that never require judgment: spread check, session check, news check. If any fail, skip the trade. No exceptions.

### P3: Progressive Complexity
Build the infrastructure for TWAP/VWAP/SOR from day one, but only activate algorithms when position sizes justify them. The execution engine routes through the appropriate complexity tier.

### P4: Log Everything
Record actual fill price vs. intended price for every trade. This data calibrates the slippage model and identifies execution quality trends.

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    EXECUTION ENGINE                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐                                                │
│  │  TRADE        │                                                │
│  │  SIGNAL       │                                                │
│  └──────┬───────┘                                                │
│         │                                                         │
│         ▼                                                         │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │              EXECUTION GATE                                │    │
│  │  □ Spread check: current_spread < 2× 1hr_avg?            │    │
│  │  □ Session check: in London-NY overlap?                   │    │
│  │  □ News check: no high-impact event ±30 min?             │    │
│  │  □ Slippage cap: max_deviation ≤ 3 pips?                 │    │
│  └──────────────────────┬───────────────────────────────────┘    │
│                         │                                         │
│              ┌──────────┴──────────┐                              │
│              ▼                     ▼                              │
│  ┌──────────────────┐  ┌──────────────────┐                      │
│  │  SIMPLE PATH     │  │  ALGO PATH       │                      │
│  │  ($7–$500)       │  │  ($500+)         │                      │
│  │                  │  │                  │                      │
│  │  • Market order  │  │  • TWAP          │                      │
│  │  • Limit order   │  │  • VWAP          │                      │
│  │  • Spread filter │  │  • Iceberg       │                      │
│  │  • Session filter│  │  • Smart routing │                      │
│  └────────┬─────────┘  └────────┬─────────┘                      │
│           │                     │                                 │
│           └──────────┬──────────┘                                 │
│                      ▼                                            │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │              ORDER MANAGER                                │    │
│  │  • Submit to broker                                       │    │
│  │  • Track fill status                                      │    │
│  │  • Record actual vs intended price                        │    │
│  │  • Handle rejections/retries                              │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Execution Rules for $7 Capital

### Rule 1: Spread Filter

```python
def spread_check(pair, current_spread, avg_spread_1h):
    """Reject entry if spread is abnormally wide."""
    if current_spread > avg_spread_1h * 2.0:
        return False, f"Spread {current_spread} > 2× avg {avg_spread_1h}"
    if current_spread > MAX_SPREAD.get(pair, 3.0):
        return False, f"Spread {current_spread} > max {MAX_SPREAD[pair]}"
    return True, "OK"

MAX_SPREAD = {
    "EURUSD": 2.0, "USDJPY": 2.0, "GBPUSD": 3.0,
    "XAUUSD": 0.5, "BTCUSD": 10.0
}
```

### Rule 2: Session Filter

```python
SESSIONS = {
    "london_ny_overlap": {"start": "13:00", "end": "17:00", "quality": "excellent"},
    "london": {"start": "08:00", "end": "16:00", "quality": "good"},
    "new_york": {"start": "13:00", "end": "21:00", "quality": "good"},
    "asian": {"start": "00:00", "end": "08:00", "quality": "poor"},
}

def session_check(pair, current_time_utc):
    """Only trade during liquid sessions."""
    session = get_current_session(current_time_utc)
    
    # Always allow during London-NY overlap
    if session == "london_ny_overlap":
        return True, "Golden window"
    
    # Allow London/NY for majors
    if session in ("london", "new_york") and is_major(pair):
        return True, f"{session} session"
    
    # Block Asian session for non-JPY pairs
    if session == "asian" and not pair.endswith("JPY"):
        return False, "Asian session — wide spreads on non-JPY"
    
    # Block session transitions (±15 min)
    if is_session_transition(current_time_utc):
        return False, "Session transition — spread spike risk"
    
    return True, "Acceptable"
```

### Rule 3: News Filter

```python
def news_check(current_time, calendar_events):
    """No positions through high-impact news events."""
    for event in calendar_events:
        if event.impact == "HIGH":
            time_to_event = (event.time - current_time).total_seconds() / 60
            if -30 <= time_to_event <= 30:
                return False, f"High-impact event: {event.name} in {time_to_event:.0f} min"
    return True, "No high-impact events"
```

### Rule 4: Order Type Selection

```python
def select_order_type(signal, market_conditions):
    """Default to limit orders; market only for confirmed breakouts."""
    if signal.type == "BREAKOUT_CONFIRMED":
        return "MARKET"  # Speed critical
    elif signal.type == "PULLBACK_ENTRY":
        return "LIMIT"   # Can wait for price
    elif signal.type == "ORDER_BLOCK":
        return "LIMIT"   # Place at OB level
    else:
        return "LIMIT"   # Default: maker, not taker
```

---

## 5. Algorithm Catalog

### 5.1 TWAP (Time-Weighted Average Price) — $500+ Capital

**Purpose:** Split large orders into equal time slices to achieve average price.

```python
class TWAPExecutor:
    def execute(self, pair, side, total_lots, duration_minutes, slices=5):
        """Split order into time-weighted slices."""
        lot_per_slice = total_lots / slices
        interval = duration_minutes / slices
        
        for i in range(slices):
            yield Order(
                pair=pair, side=side, lots=lot_per_slice,
                type="MARKET", delay=i * interval
            )
```

**Activation threshold:** Position > 0.1 lot or capital > $500.

### 5.2 VWAP (Volume-Weighted Average Price) — $5,000+ Capital

**Purpose:** Execute weighted toward high-volume periods.

**Activation threshold:** Position > 1.0 lot or capital > $5,000. Requires real-time volume feed.

### 5.3 Iceberg Orders — $10,000+ Capital

**Purpose:** Hide large order size by showing only small portions.

**Note:** Forex is OTC — no visible order book to hide from. Only relevant for equity/futures with visible order books.

### 5.4 Smart Order Routing (SOR) — $50,000+ Capital

**Purpose:** Route to venue with best price/liquidity across multiple brokers.

**Note:** FXPesa already aggregates liquidity internally. SOR only relevant with multiple broker accounts.

---

## 6. Evolution Roadmap

| Capital | Execution Enhancement | Why |
|---------|----------------------|-----|
| **$7–$50** | Spread filter + limit orders + session filter | Simple, high-impact |
| **$50–$500** | Partial fill handling, multi-pair correlation | Position management |
| **$500–$5K** | Basic TWAP for entries >0.1 lot, trailing stops | Market impact starts |
| **$5K–$50K** | VWAP benchmarking, slippage analytics | Execution cost measurable |
| **$50K+** | Full algo suite, multi-venue routing, latency opt | Institutional-grade |

---

## 7. MT5-Specific Configuration

### Recommended EA Settings

```mql5
// Slippage tolerance (points, not pips)
input int MaxSlippage = 30;  // 3.0 pips max deviation

// Fill policy: IOC or FOK preferred
// Avoid "Return" policy (leaves unfilled portions)

// Order type preference: LIMIT default, MARKET for breakouts
```

### FXPesa-Specific Notes

- **Account type:** Micro account for $7 start (0.01 lot minimum)
- **Execution model:** Market maker for standard accounts
- **Re-quote handling:** Set max deviation to avoid re-quote loops
- **Logging:** Record `OrderSend` result including actual fill price

---

## 8. Integration Points

### With TCA Engine
- Pre-trade cost check gates execution
- Spread filter uses real-time TCA spread calculator
- Slippage estimator informs max deviation setting

### With Risk Manager
- Position size from risk manager determines execution path
- Daily trade limit enforced before execution
- Drawdown triggers halt all execution

### With Market Regime
- Regime affects session preferences (crisis = tighter windows)
- Volatility regime adjusts slippage estimates
- Trending regime may extend holding periods (affects swap decisions)

### With Broker Abstraction Layer
- Execution engine submits orders through broker connector
- Fill confirmations flow back through event bus
- Multi-broker routing (Phase 3+) uses smart order router

---

## 9. Implementation Roadmap

### Phase 1: Simple Rules (Week 1)
- [ ] Spread filter with real-time broker quotes
- [ ] Session filter with UTC time windows
- [ ] News calendar integration (ForexFactory/Investing.com)
- [ ] Limit order default with market order fallback
- [ ] Execution logging (intended vs actual fill)

### Phase 2: Enhanced Simple Path (Week 2–3)
- [ ] Trailing stop implementation
- [ ] Partial fill handling
- [ ] Re-quote retry logic with backoff
- [ ] Slippage analytics dashboard

### Phase 3: Algorithm Activation (Month 2+, $500+ capital)
- [ ] TWAP executor for orders > 0.1 lot
- [ ] VWAP benchmarking (if volume data available)
- [ ] Multi-pair correlation-aware execution
- [ ] Execution quality scoring system

### Phase 4: Institutional Grade ($5K+ capital)
- [ ] Smart order routing across multiple brokers
- [ ] Iceberg order support (for equity/futures)
- [ ] Latency optimization (co-location assessment)
- [ ] Full algo suite with A/B testing

---

*Architecture document for Alpha Stack Execution Algorithms. Based on research findings: at $7, execution sophistication is the wrong optimization target. Focus on 3 simple rules. Add complexity only when position sizes justify it ($500+).*
