# Alpha Stack — Transaction Cost Analysis (TCA) Architecture

> **Version:** 1.0 · **Date:** 2026-07-11 · **Author:** Architecture Team
> **Source Research:** [`research/research_tca.md`](../research/research_tca.md) — Transaction cost analysis research
> **Status:** Architecture Complete

---

**Version:** 1.0
**Date:** 2026-07-13
**Status:** Architecture Design
**Dependencies:** Broker Abstraction Layer, Execution Algorithms, Risk Management

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Design Philosophy](#2-design-philosophy)
3. [System Architecture](#3-system-architecture)
4. [Cost Model Components](#4-cost-model-components)
5. [Spread Cost Calculator](#5-spread-cost-calculator)
6. [Break-Even Analyzer](#6-break-even-analyzer)
7. [Cost-Aware Position Sizing](#7-cost-aware-position-sizing)
8. [Swap & Financing Cost Module](#8-swap--financing-cost-module)
9. [Slippage Estimator](#9-slippage-estimator)
10. [Integration Points](#10-integration-points)
11. [Implementation Roadmap](#11-implementation-roadmap)

---

## 1. Executive Summary

### Problem

At $7 capital on FXPesa Standard account, transaction costs consume 2–3.7% of capital per trade. A EURUSD round-trip costs $0.15 (2.1% of capital). Without rigorous cost analysis, the system will generate negative expectancy — profitable signals become losing trades after costs.

### Solution

A **real-time TCA engine** embedded in the execution pipeline that:
- Calculates total round-trip cost before every trade
- Rejects trades where cost exceeds a configurable threshold
- Adjusts position sizing to maintain positive expectancy after costs
- Tracks realized vs. estimated costs for continuous calibration

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Cost model | Per-trade, pre-execution | Must reject uneconomic trades before execution |
| Integration | Inline in execution pipeline | Not post-hoc analysis — blocks bad trades |
| Spread source | Real-time broker quotes | Static spread tables are stale within seconds |
| Swap model | Calendar-aware with triple Wednesday | Swap costs compound quickly on $7 accounts |
| Threshold | Dynamic, based on pair + session | EURUSD at London overlap ≠ GBPJPY at Asian session |

---

## 2. Design Philosophy

### P1: Cost Is the First Filter
Before any signal quality assessment, the TCA engine asks: "Can this trade be profitable after costs?" If not, reject immediately.

### P2: Conservative Estimation
When uncertain, overestimate costs. A trade that passes with overestimated costs will definitely pass with real costs. The reverse is catastrophic at $7.

### P3: Continuous Calibration
Every executed trade's actual costs are compared to estimates. The model self-calibrates over time, reducing estimation error.

### P4: Capital-Proportional Awareness
Cost thresholds scale with account size. At $7, a $0.15 cost is 2.1%. At $700, the same $0.15 is 0.02%. The system adapts.

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    TCA ENGINE ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     │
│  │  Signal       │     │  Spread      │     │  Swap        │     │
│  │  Generator    │────▶│  Calculator  │────▶│  Calculator  │     │
│  └──────┬───────┘     └──────┬───────┘     └──────┬───────┘     │
│         │                    │                     │              │
│         ▼                    ▼                     ▼              │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │              TOTAL COST ESTIMATOR                        │     │
│  │  cost = spread + commission + est_slippage + swap (if    │     │
│  │         held) + financing                                │     │
│  └──────────────────────┬──────────────────────────────────┘     │
│                         │                                         │
│                         ▼                                         │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │              BREAK-EVEN ANALYZER                         │     │
│  │  min_profit_pips = cost / pip_value                      │     │
│  │  min_rr_ratio = min_profit / stop_distance               │     │
│  └──────────────────────┬──────────────────────────────────┘     │
│                         │                                         │
│              ┌──────────┴──────────┐                              │
│              ▼                     ▼                              │
│  ┌──────────────────┐  ┌──────────────────┐                      │
│  │  REJECT TRADE    │  │  APPROVE TRADE   │                      │
│  │  (cost > max)    │  │  (pass to risk)  │                      │
│  └──────────────────┘  └──────────────────┘                      │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │              POST-TRADE COST TRACKER                     │     │
│  │  Compare estimated vs actual → calibrate model           │     │
│  └─────────────────────────────────────────────────────────┘     │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Cost Model Components

### Total Cost Formula

```
Total_Cost = Spread_Cost + Commission + Est_Slippage + Swap_Cost + Financing
```

### Component Breakdown for $7 Account (FXPesa Standard)

| Component | EURUSD | GBPUSD | XAUUSD | BTCUSD |
|-----------|--------|--------|--------|--------|
| Spread cost (0.01 lot) | $0.14 | $0.22 | $0.28 | ~$5.00 |
| Commission | $0.00 | $0.00 | $0.00 | $0.00 |
| Est. slippage | $0.01 | $0.01 | $0.02 | $0.50 |
| Swap (1 night, long) | -$0.08 | -$0.03 | varies | varies |
| **Day trade total** | **$0.15** | **$0.23** | **$0.30** | **$5.50** |
| **% of $7 capital** | **2.1%** | **3.3%** | **4.3%** | **78.6%** |

### Cost as % of Capital Threshold

```yaml
tca_thresholds:
  max_cost_pct_per_trade: 3.0      # Reject if cost > 3% of capital
  warn_cost_pct_per_trade: 2.0     # Warn if cost > 2% of capital
  max_daily_cost_pct: 6.0          # Max 6% of capital in daily costs
  max_daily_trades_at_7usd: 4      # 4 × $0.15 = $0.60 = 8.6% max
```

---

## 5. Spread Cost Calculator

### Real-Time Spread Calculation

```python
class SpreadCostCalculator:
    def calculate(self, pair: str, lot_size: float, current_spread_pips: float) -> float:
        """
        Calculate spread cost in account currency.
        
        Args:
            pair: Trading pair (e.g., "EURUSD")
            lot_size: Position size in lots (e.g., 0.01)
            current_spread_pips: Current bid-ask spread in pips
            
        Returns:
            Spread cost in USD
        """
        pip_value = self._get_pip_value(pair, lot_size)
        return current_spread_pips * pip_value
    
    def _get_pip_value(self, pair: str, lot_size: float) -> float:
        """For standard forex pairs, 1 pip = $0.10 per 0.01 lot."""
        if pair.endswith("USD"):
            return lot_size * 100_000 * 0.0001  # $1.00 per standard lot per pip
        # Cross pairs: convert pip value through USD
        return self._cross_pip_value(pair, lot_size)
```

### Spread Quality Assessment

| Spread Quality | EURUSD | Action |
|---------------|--------|--------|
| Excellent | < 1.0 pip | Full position size |
| Good | 1.0–1.5 pip | Normal position |
| Acceptable | 1.5–2.0 pip | Reduce size 25% |
| Poor | 2.0–3.0 pip | Reduce size 50% |
| Reject | > 3.0 pip | Skip trade |

### Session-Aware Spread Windows

```yaml
spread_windows:
  london_ny_overlap:  # 13:00-17:00 UTC
    eurusd_avg: 0.8
    gbpusd_avg: 1.2
    quality: excellent
  london_session:     # 08:00-16:00 UTC
    eurusd_avg: 1.2
    gbpusd_avg: 1.8
    quality: good
  asian_session:      # 00:00-08:00 UTC
    eurusd_avg: 2.0
    gbpusd_avg: 3.0
    quality: poor
  session_transition: # ±15 min of session open/close
    multiplier: 1.5   # Spread widens 50% at transitions
```

---

## 6. Break-Even Analyzer

### Break-Even Calculation

```
Break_Even_Pips = Total_Cost / Pip_Value
Minimum_R:R = Break_Even_Pips / Stop_Loss_Pips
```

### Break-Even Table (0.01 Lot, FXPesa Standard)

| Pair | Spread | Total Cost | Break-Even Pips | Min R:R (2-pip SL) | Min R:R (5-pip SL) |
|------|--------|-----------|-----------------|--------------------|--------------------|
| EURUSD | 1.4 | $0.15 | 1.5 | 0.75 | 0.30 |
| GBPUSD | 2.2 | $0.23 | 2.3 | 1.15 | 0.46 |
| USDJPY | 1.4 | $0.15 | 1.5 | 0.75 | 0.30 |
| XAUUSD | 0.28 | $0.30 | 3.0 | 1.50 | 0.60 |

### Minimum Profitable Target

```python
def min_profitable_target(pair, stop_pips, cost_usd, pip_value):
    """Calculate minimum take-profit to achieve desired R:R after costs."""
    be_pips = cost_usd / pip_value
    # For 1:2 R:R after costs:
    # TP = SL + 2 * (SL - be_pips)
    # Simplified: TP must be > be_pips + (2 * stop_pips)
    min_tp = be_pips + (2 * stop_pips)
    return min_tp
```

### Trade Viability Gate

```python
def is_trade_viable(signal, pair, lot_size, stop_pips, current_spread):
    """Gate: reject trades that can't be profitable after costs."""
    cost = tca_engine.estimate_total_cost(pair, lot_size, current_spread, hold_days=0)
    pip_value = get_pip_value(pair, lot_size)
    be_pips = cost / pip_value
    
    # Minimum: target must be 2x the break-even distance
    min_target_pips = be_pips * 2
    
    # Minimum R:R after costs must be >= 1:1.5
    net_rr = (signal.target_pips - be_pips) / stop_pips
    if net_rr < 1.5:
        return False, f"Net R:R {net_rr:.1f} after costs < 1.5 minimum"
    
    # Max cost as % of capital
    cost_pct = cost / get_account_balance() * 100
    if cost_pct > 3.0:
        return False, f"Cost {cost_pct:.1f}% of capital > 3% max"
    
    return True, "Approved"
```

---

## 7. Cost-Aware Position Sizing

### Integration with Kelly Criterion

Standard Kelly: `f = (bp - q) / b`

Cost-adjusted Kelly: `f = (b(p - cost_edge) - q) / b`

Where `cost_edge = cost_per_trade / potential_profit`

```python
def cost_adjusted_position_size(signal, pair, balance):
    """Position size that accounts for transaction costs."""
    # Estimate costs
    spread = get_current_spread(pair)
    cost = tca_engine.estimate_total_cost(pair, 0.01, spread)
    
    # Adjust win probability for cost drag
    raw_edge = signal.win_rate * signal.avg_win - (1 - signal.win_rate) * signal.avg_loss
    cost_drag = cost / signal.avg_win  # Cost as fraction of average win
    adjusted_edge = raw_edge - cost_drag
    
    if adjusted_edge <= 0:
        return 0  # No position — costs eat all edge
    
    # Kelly fraction with cost adjustment
    kelly_f = adjusted_edge / signal.avg_win
    conservative_f = kelly_f * 0.25  # Quarter-Kelly
    
    # Position size in lots
    risk_amount = balance * conservative_f
    pip_value_per_lot = get_pip_value(pair, 1.0)
    position_lots = risk_amount / (signal.stop_pips * pip_value_per_lot)
    
    # Enforce minimums
    return max(0.01, round(position_lots, 2))
```

### Capital-Phase Sizing Rules

| Capital Phase | Max Cost % | Max Daily Trades | Position Rule |
|--------------|-----------|-----------------|---------------|
| $7–$50 | 2.5% | 2–3 | 0.01 lots fixed, EURUSD/USDJPY only |
| $50–$200 | 2.0% | 4–5 | 0.01–0.02 lots, add GBPUSD |
| $200–$1K | 1.5% | 5–8 | % risk-based sizing (1–2%) |
| $1K+ | 1.0% | 10+ | Full Kelly with cost adjustment |

---

## 8. Swap & Financing Cost Module

### Swap Cost Calculation

```python
class SwapCalculator:
    def calculate(self, pair, direction, lots, hold_days, is_wednesday=False):
        """
        Calculate swap cost for holding a position.
        
        Triple swap on Wednesday (T+2 settlement for forex).
        """
        swap_rate = self._get_swap_rate(pair, direction)  # points per lot per day
        daily_swap = lots * 100_000 * swap_rate * self._point_size(pair)
        
        total = daily_swap * hold_days
        if is_wednesday:
            total += daily_swap * 2  # Triple swap
        
        return total  # Negative = cost, Positive = credit
```

### Swap Avoidance Rules

```yaml
swap_rules:
  $7_account:
    max_hold_days: 0           # Day trade only — never hold overnight
    close_before: "21:00 GMT"  # Before swap rollover
    reason: "Swap costs drain 1-5% of capital per night on losing positions"
  
  $50_plus_account:
    max_hold_days: 3           # Allow short swings
    swap_direction_filter: true  # Only hold in swap-positive direction
    min_swap_credit: 0.01      # Minimum daily credit to justify hold
```

---

## 9. Slippage Estimator

### Slippage Model

```python
class SlippageEstimator:
    def estimate(self, pair, lot_size, order_type, volatility_regime):
        """
        Estimate expected slippage based on:
        - Pair liquidity
        - Position size relative to normal
        - Current volatility
        - Order type (market vs limit)
        """
        base_slippage = self._base_slippage_pips(pair)  # 0.1–0.5 pips
        size_factor = max(1.0, lot_size / 0.01)         # Linear scaling
        vol_factor = {
            "low": 0.8, "normal": 1.0, "high": 1.5, "crisis": 3.0
        }[volatility_regime]
        
        est_pips = base_slippage * size_factor * vol_factor
        
        if order_type == "LIMIT":
            est_pips = 0  # Limit orders have zero slippage (or positive)
        
        return est_pips * self._pip_value(pair, lot_size)
```

### Slippage by Regime

| Regime | Base Slippage (EURUSD) | Multiplier | $7 Impact |
|--------|----------------------|-----------|----------|
| Low vol | 0.1 pips | 0.8× | $0.008 |
| Normal | 0.2 pips | 1.0× | $0.02 |
| High vol | 0.5 pips | 1.5× | $0.075 |
| Crisis/News | 2.0+ pips | 3.0× | $0.60+ |

---

## 10. Integration Points

### With Execution Engine
- Pre-trade cost check: TCA engine is called BEFORE order submission
- Reject threshold: Trades exceeding cost limits are blocked
- Order type selection: TCA recommends LIMIT vs MARKET based on cost

### With Risk Manager
- Cost-adjusted R:R: Risk manager uses net-of-cost returns
- Daily cost budget: Risk manager tracks cumulative daily costs
- Drawdown attribution: Distinguish cost-driven vs. strategy-driven drawdown

### With Position Sizer
- Cost-aware Kelly: Position sizer calls TCA for cost estimates
- Minimum viable size: TCA determines if a position size is economically viable

### With Market Regime
- Volatility regime input: TCA adjusts slippage estimates based on regime
- Session awareness: TCA knows which trading session is active

### With Portfolio Manager
- Multi-position cost: Total daily cost budget across all positions
- Correlation cost: Correlated positions amplify cost if both lose

---

## 11. Implementation Roadmap

### Phase 1: Core Cost Calculator (Week 1)
- [ ] Spread cost calculator with real-time broker quotes
- [ ] Break-even analyzer for all supported pairs
- [ ] Trade viability gate (reject if cost > 3% of capital)
- [ ] Basic slippage estimator (static per pair)

### Phase 2: Integration (Week 2)
- [ ] Inline integration with execution pipeline
- [ ] Cost-adjusted position sizing
- [ ] Session-aware spread windows
- [ ] Daily cost budget tracking

### Phase 3: Advanced (Week 3–4)
- [ ] Swap calculator with calendar awareness
- [ ] Dynamic slippage model (volatility-adjusted)
- [ ] Post-trade cost tracking (estimated vs actual)
- [ ] Cost model self-calibration

### Phase 4: Optimization (Month 2+)
- [ ] Cost-based pair ranking (trade cheapest pairs first)
- [ ] Cross-pair cost correlation (avoid doubling costs)
- [ ] Historical cost analytics dashboard
- [ ] Cost attribution reporting

---

*Architecture document for Alpha Stack TCA Engine. Based on research findings: FXPesa Standard account costs 2–3.7% per trade at $7 capital. Cost-aware execution is critical for survival at micro-capital levels.*
