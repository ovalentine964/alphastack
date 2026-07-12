# Alpha Stack — Trading Pair Selection & Management Architecture

**Version:** 1.0
**Date:** 2026-07-13
**Status:** Architecture Design
**Dependencies:** Broker Abstraction Layer, TCA Engine, Market Regime Detection

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Design Philosophy](#2-design-philosophy)
3. [System Architecture](#3-system-architecture)
4. [Pair Evaluation Framework](#4-pair-evaluation-framework)
5. [Pair Tiers & Allocation](#5-pair-tiers--allocation)
6. [Correlation Management](#6-correlation-management)
7. [Session-Based Pair Rotation](#7-session-based-pair-rotation)
8. [Pair Lifecycle Management](#8-pair-lifecycle-management)
9. [Integration Points](#9-integration-points)
10. [Implementation Roadmap](#10-implementation-roadmap)

---

## 1. Executive Summary

### Problem

With $7 capital, you cannot trade everything. Over-monitoring leads to analysis paralysis, correlated exposure, and spreading capital too thin. FXPesa offers 60+ forex pairs, 50+ crypto CFDs, and numerous indices/commodities — most are unsuitable for micro-capital.

### Solution

A **tiered pair selection system** that evaluates pairs on spread cost, liquidity, volatility, SMC pattern quality, and macro sensitivity. Pairs are ranked into tiers, with strict allocation limits and session-based rotation. The system enforces a maximum of 5–7 active pairs at any time.

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Active pairs | 5–7 maximum | Focus > diversification at $7 |
| Tier 1 pairs | EURUSD, GBPUSD, XAUUSD | Lowest spreads, best SMC patterns |
| Crypto allocation | BTCUSD + ETHUSD only | Group 1 leverage (1:200) only |
| Exotic pairs | Banned at $7 | Spread eats 5–20% of capital per trade |
| Correlation rule | Never hold correlated pairs simultaneously | EURUSD + GBPUSD = same trade twice |

---

## 2. Design Philosophy

### P1: Focus Over Diversification
At $7, true diversification is impossible. One position at a time. Trade the best pair for the current session, not five mediocre ones.

### P2: Cost Is the Primary Filter
Before evaluating signal quality, check if the pair is even tradeable. Exotic pairs with 140-pip spreads are capital suicide at $7.

### P3: Gold Is #1
XAU/USD (Gold) is the best overall fit for macro + SMC strategy. Tight spreads, massive daily moves, institutional behavior, macro-driven. This is the primary money-maker.

### P4: Correlation Kills
Holding EURUSD long and GBPUSD long simultaneously is the same trade twice. Correlation management prevents doubling down on a single thesis.

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    PAIR MANAGEMENT SYSTEM                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     │
│  │  PAIR         │────▶│  TIER         │────▶│  SESSION      │     │
│  │  EVALUATOR    │     │  CLASSIFIER   │     │  ROUTER       │     │
│  └──────────────┘     └──────────────┘     └──────┬───────┘     │
│                              │                     │             │
│                              ▼                     ▼             │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │              CORRELATION GATE                             │     │
│  │  Reject if new position correlates > 0.7 with existing   │     │
│  └──────────────────────────┬──────────────────────────────┘     │
│                             │                                     │
│                             ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │              POSITION MANAGER                             │     │
│  │  • Max 1 position at $7 capital                          │     │
│  │  • Max 3 positions at $200+ capital                      │     │
│  │  • Risk per pair: 2% of capital                          │     │
│  └─────────────────────────────────────────────────────────┘     │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Pair Evaluation Framework

### Evaluation Criteria

| Criterion | Weight | Measurement | Threshold |
|-----------|--------|-------------|-----------|
| Spread cost | 30% | Pips × pip value at 0.01 lot | < 2.5 pips for majors |
| Liquidity | 25% | Daily volume, order book depth | > $1B/day for forex |
| Volatility | 20% | Average daily range (pips) | 60–180 pips/day |
| SMC quality | 15% | Clean order blocks, FVGs | Subjective scoring |
| Macro sensitivity | 10% | Responds to economic data | High for forex, very high for gold |

### Scoring Function

```python
def evaluate_pair(pair, account_balance):
    """Score a pair for tradeability at current capital level."""
    spread_cost = get_spread_cost(pair, 0.01)
    cost_pct = spread_cost / account_balance * 100
    
    # Hard reject: cost > 3% of capital
    if cost_pct > 3.0:
        return PairScore(pair, tier="REJECT", reason=f"Cost {cost_pct:.1f}% > 3%")
    
    # Score components
    spread_score = max(0, 100 - cost_pct * 20)  # Lower cost = higher score
    liquidity_score = min(100, get_daily_volume(pair) / 1e9 * 100)
    volatility_score = volatility_quality(get_daily_range(pair))
    smc_score = get_smc_quality(pair)  # 0–100 from backtesting
    
    total = (spread_score * 0.30 + liquidity_score * 0.25 +
             volatility_score * 0.20 + smc_score * 0.15 +
             get_macro_sensitivity(pair) * 0.10)
    
    tier = "T1" if total >= 80 else "T2" if total >= 60 else "T3" if total >= 40 else "REJECT"
    return PairScore(pair, tier=tier, score=total)
```

---

## 5. Pair Tiers & Allocation

### Tier 1 — Primary (Trade Daily)

| Pair | Spread | Daily Range | Why |
|------|--------|-------------|-----|
| **XAU/USD** | 0.28 pips | 2000–4000 pips | #1 money-maker. Macro + SMC perfect fit |
| **EUR/USD** | 1.4 pips | 70–100 pips | Most liquid, tightest spreads, cleanest patterns |
| **GBP/USD** | 1.8 pips | 90–130 pips | High volatility + clean order blocks |

### Tier 2 — Secondary (Session-Specific)

| Pair | Spread | Daily Range | Best Session |
|------|--------|-------------|-------------|
| **GBP/JPY** | 2.3 pips | 120–180 pips | London — "The Beast" |
| **USD/JPY** | 1.4 pips | 70–100 pips | Tokyo + London — macro-driven |
| **BTCUSD** | ~$5 | 2–5% daily | 24/6 — digital gold macro plays |
| **ETHUSD** | varies | 2–5% daily | 24/6 — DeFi ecosystem proxy |

### Tier 3 — Opportunistic

| Pair | Condition |
|------|-----------|
| AUD/USD | When commodity themes dominate |
| EUR/JPY | When JPY themes dominate |
| USD/CAD | Oil-driven macro plays |

### Excluded (Capital Suicide at $7)

| Pair | Reason |
|------|--------|
| EUR/MXN | 159-pip spread = 22.7% of capital per trade |
| USD/ZAR | 140-pip spread = 20.1% of capital |
| GBP/AUD | 5.2-pip spread on Standard account |
| All Group 2–4 crypto | Leverage too low, margin too high |

---

## 6. Correlation Management

### Correlation Matrix

```
              EUR/USD  GBP/USD  USD/JPY  GBP/JPY  XAU/USD  BTCUSD  ETHUSD
EUR/USD        1.00     0.90    -0.85     0.40     0.70    -0.55   -0.50
GBP/USD        0.90     1.00    -0.75     0.55     0.65    -0.50   -0.45
USD/JPY       -0.85    -0.75     1.00     0.60    -0.70     0.50    0.45
GBP/JPY        0.40     0.55     0.60     1.00     0.10     0.15    0.20
XAU/USD        0.70     0.65    -0.70     0.10     1.00    -0.30   -0.25
BTCUSD        -0.55    -0.50     0.50     0.15    -0.30     1.00    0.85
ETHUSD        -0.50    -0.45     0.45     0.20    -0.25     0.85    1.00
```

### Correlation Rules

```python
def check_correlation(new_pair, existing_positions):
    """Reject if new position correlates too highly with existing."""
    for pos in existing_positions:
        corr = get_correlation(new_pair, pos.pair, lookback=20)
        if abs(corr) > 0.70:
            return False, f"Correlation {corr:.2f} with {pos.pair} > 0.70 threshold"
    return True, "OK"
```

### Hard Rules
1. ❌ Never simultaneously long EUR/USD AND GBP/USD (0.90 correlated)
2. ❌ Never long BTCUSD AND ETHUSD (0.85 correlated)
3. ❌ Never long EUR/USD AND short USD/JPY (both USD weakness plays)
4. ✅ Long XAU/USD + Long GBP/JPY (0.10 correlation — diversified)

---

## 7. Session-Based Pair Rotation

### Session Schedule (EAT/GMT+3)

| Session | Time (EAT) | Active Pairs | Strategy Focus |
|---------|-----------|-------------|----------------|
| Asian | 03:00–12:00 | USD/JPY, AUD/USD, BTC | Range identification |
| London | 12:00–21:00 | EUR/USD, GBP/USD, GBP/JPY, XAU/USD | **Primary — SMC entries** |
| New York | 16:00–01:00 | EUR/USD, GBP/USD, XAU/USD, BTC | Macro news trades |
| Overlap | 16:00–21:00 | ALL pairs | **Maximum opportunity** |

### Session Router

```python
def get_active_pairs(session, regime):
    """Return pairs appropriate for current session and regime."""
    pairs = SESSION_PAIRS[session]
    
    if regime == "crisis":
        # In crisis, only trade most liquid
        pairs = [p for p in pairs if p in ["EURUSD", "XAUUSD"]]
    elif regime == "ranging":
        # In range, prefer mean-reversion friendly pairs
        pairs = [p for p in pairs if p in ["EURGBP", "EURUSD"]]
    
    return pairs
```

---

## 8. Pair Lifecycle Management

### Lifecycle States

```
CANDIDATE → EVALUATING → ACTIVE → MONITORING → RETIRED
```

| State | Criteria | Action |
|-------|----------|--------|
| CANDIDATE | New pair discovered | Queue for evaluation |
| EVALUATING | Backtesting in progress | Paper trade only |
| ACTIVE | Passed all checks, live trading | Full position sizing |
| MONITORING | Performance degrading | Reduce size, investigate |
| RETIRED | Consistent losses or conditions changed | Remove from watchlist |

### Retirement Triggers

```python
def should_retire_pair(pair, performance_history):
    """Check if pair should be retired from active trading."""
    recent = performance_history.last(30)  # Last 30 trades
    
    if recent.win_rate < 0.35:
        return True, f"Win rate {recent.win_rate:.0%} < 35% threshold"
    
    if recent.avg_rr < 1.0:
        return True, f"Avg R:R {recent.avg_rr:.1f} < 1.0 minimum"
    
    if recent.cost_pct > recent.profit_pct:
        return True, "Costs exceed profits"
    
    return False, "Performance acceptable"
```

---

## 9. Integration Points

### With TCA Engine
- Spread cost data for pair evaluation
- Cost thresholds gate pair admission
- Real-time cost tracking per pair

### With Market Regime
- Regime affects which pairs are active
- Crisis mode restricts to most liquid pairs
- Trending regime may expand pair universe

### With Risk Manager
- Correlation monitoring across positions
- Per-pair risk limits
- Portfolio-level exposure tracking

### With Execution Engine
- Session-based pair routing
- Order type selection per pair
- Slippage tracking per pair

---

## 10. Implementation Roadmap

### Phase 1: Core Pair Management (Week 1)
- [ ] Pair evaluation framework (spread + volume scoring)
- [ ] Tier classification system
- [ ] Hard-coded watchlist (Tier 1: XAU, EUR, GBP)
- [ ] Correlation gate for position entry

### Phase 2: Dynamic Management (Week 2–3)
- [ ] Session-based pair rotation
- [ ] Regime-aware pair selection
- [ ] Automated pair scoring from live data
- [ ] Performance tracking per pair

### Phase 3: Lifecycle Management (Week 4+)
- [ ] Pair retirement triggers
- [ ] Candidate evaluation pipeline
- [ ] Backtesting framework for new pairs
- [ ] Correlation matrix auto-update

### Phase 4: Optimization (Month 2+)
- [ ] Optimal pair combination search
- [ ] Cross-pair signal correlation
- [ ] Dynamic allocation based on regime
- [ ] Pair-specific strategy parameter tuning

---

*Architecture document for Alpha Stack Trading Pair Selection. Based on research findings: XAU/USD is the #1 instrument for macro + SMC strategy. Exotic pairs are capital suicide at $7 (20%+ per trade in spread). Maximum 5–7 active pairs recommended.*
