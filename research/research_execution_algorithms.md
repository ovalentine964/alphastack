# Execution Algorithms Research — Alpha Stack

> **Context:** Institutional-grade AI trading system, $7 starting capital, FXPesa broker, MT5 platform.
> **Date:** 2026-07-11

---

## 1. Executive Summary

At $7 capital trading micro lots (0.01), **traditional institutional execution algorithms (TWAP, VWAP, iceberg, smart order routing) are unnecessary and counterproductive.** Your order size is too small to move markets or suffer meaningful slippage. The real execution concerns at this scale are: spread cost, entry/exit timing relative to volatility, and avoiding amateur mistakes (market orders during news, trading illiquid sessions).

**Bottom line:** Focus on 3 simple execution rules, not algorithmic sophistication.

---

## 2. Algorithm-by-Algorithm Assessment

### 2.1 TWAP (Time-Weighted Average Price)

**What it does:** Splits a large order into equal time slices to achieve the average price over a period.

| Factor | Assessment |
|---|---|
| **Order size concern** | Only matters when your order is large enough to impact price. A 0.01 lot EUR/USD order (~1,000 units) is noise in a $7.5T/day market. |
| **Verdict** | **Not needed.** Your entire position is smaller than a single tick of institutional flow. |
| **When to add** | If position sizes ever exceed 1.0 lot consistently (~$100K notional). Unlikely with $7 capital. |

### 2.2 VWAP (Volume-Weighted Average Price)

**What it does:** Executes orders weighted toward high-volume periods to achieve a price near the day's volume-weighted average.

| Factor | Assessment |
|---|---|
| **Volume data** | Requires real-time volume feed. MT5 provides tick volume, not true volume for forex. |
| **Relevance** | Institutional benchmark for "did I get a fair fill?" — irrelevant when your fill cost is dominated by the spread, not market impact. |
| **Verdict** | **Not needed.** At 0.01 lot, your fill IS the market price ± spread. No impact to manage. |
| **When to add** | Position sizes >5 lots, or if managing multiple correlated positions simultaneously. |

### 2.3 Iceberg Orders

**What it does:** Hides large order size by only showing a small portion in the order book.

| Factor | Assessment |
|---|---|
| **Order book visibility** | Forex is OTC/decentralized — there is no visible order book to "hide" from in the way equity markets have. |
| **Size relevance** | 0.01 lot doesn't register on anyone's radar. |
| **Verdict** | **Completely irrelevant.** Forex ECN/STP brokers like FXPesa don't offer true iceberg functionality, and even if they did, your size doesn't warrant it. |
| **When to add** | Never for forex at retail scale. Only relevant for equity/futures with visible order books and sizes >0.5% of average daily volume. |

### 2.4 Smart Order Routing (SOR)

**What it does:** Routes orders to the venue offering the best price/liquidity across multiple exchanges or liquidity providers.

| Factor | Assessment |
|---|---|
| **FXPesa reality** | Your broker already does this internally. FXPesa aggregates liquidity from multiple LPs. You get their best bid/ask. |
| **MT5 limitation** | No multi-broker routing available from the platform. |
| **Verdict** | **Not applicable.** Your broker handles this. You cannot add a layer on top. |
| **When to add** | Only relevant if you ever build direct market access (DMA) with multiple prime broker relationships. Not a $7 concern. |

### 2.5 Slippage Management

**This one actually matters.**

| Slippage Source | Impact at $7 | Mitigation |
|---|---|---|
| **Spread widening** | HIGH — On a $7 account, a 3-pip spread on EUR/USD costs ~$0.30 per 0.01 lot = **4.3% of capital** per trade. | Trade during liquid sessions (London/NY overlap). Avoid exotic pairs. |
| **News slippage** | HIGH — NFP, CPI, FOMC can gap 20-50 pips. A 30-pip slippage on 0.01 lot = $3 = **43% of capital.** | Hard rule: no open positions through major news events. |
| **Low liquidity gaps** | MEDIUM — Sunday open, Asian session on non-JPY pairs. | Stick to major pairs during London/NY hours. |
| **Broker execution quality** | LOW-MEDIUM — FXPesa is a market maker for micro accounts. Expect some re-quotes. | Use "maximum deviation" settings in MT5. Consider ECN account type if available at minimum deposit. |

### 2.6 Execution Timing

**This is the most impactful execution "algorithm" for your scale.**

| Timing Rule | Rationale |
|---|---|
| **Trade London-NY overlap (13:00-17:00 UTC)** | Tightest spreads, highest liquidity. 60-70% of daily forex volume. |
| **Avoid Asian session for majors** | Wider spreads, lower volume, prone to false breakouts. |
| **Avoid first/last 15 min of sessions** | Spread spikes at session transitions. |
| **Never hold through NFP, CPI, FOMC** | Gap risk can wipe out a $7 account. Close or don't open. |
| **Avoid Friday afternoon (UTC)** | Weekend gap risk + reduced liquidity. |

---

## 3. What Actually Matters at $7 — The Simple Execution Rules

### Rule 1: Spread Awareness (Cost Minimization)

```
Trade EUR/USD during London-NY overlap → spread typically 0.6-1.2 pips
Trade EUR/USD during Asian session → spread typically 1.5-3.0 pips

Cost difference per 0.01 lot trade:
  1.0 pip spread = $0.10 = 1.4% of $7 capital
  2.5 pip spread = $0.25 = 3.6% of $7 capital
```

**Implementation:** Add spread check to entry logic. If current spread > 1.5x the 1-hour average spread, delay entry or skip trade.

### Rule 2: Limit Orders Over Market Orders

```
Market order: Taker — pays the spread
Limit order:  Maker — may get filled at mid-price or better, sometimes earns rebate

At $7, every cent matters. Use limit orders for entries where possible.
```

**Implementation:** Use pending orders (Buy Limit / Sell Limit) for planned entries. Only use market orders when speed is critical (breakout confirmation).

### Rule 3: Position Sizing = Execution Quality

At $7, a single 0.01 lot trade on EUR/USD has ~$100 notional with 1:500 leverage. Your margin is tiny, but your pip value is $0.10.

```
A 50-pip stop loss on 0.01 lot = $5.00 loss = 71% of capital

This means your execution precision matters LESS than your
risk management precision. A 2-pip slippage ($0.20) is noise
compared to a 50-pip stop ($5.00).
```

**Key insight:** At $7, getting the right trade matters 25x more than getting the perfect fill. Optimize signal quality, not execution microstructure.

---

## 4. MT5-Specific Execution Settings

### Recommended MT5 EA Settings

```mql5
// Slippage tolerance (in points, not pips)
// For EUR/USD: 3 points = 0.3 pips = acceptable
input int MaxSlippage = 30;  // 3.0 pips max deviation

// Fill policy
// Use IOC (Immediate or Cancel) or FOK (Fill or Kill)
// Avoid "Return" policy which can leave unfilled portions

// Order type preference
// Prefer LIMIT orders; fall back to MARKET only on confirmed breakouts
```

### FXPesa-Specific Notes

- **Account type:** If available, ECN/RAW spread account dramatically reduces spread cost
- **Minimum trade:** 0.01 lots (1 micro lot) — this is your base unit
- **Execution model:** Market maker for standard accounts, STP/ECN for professional accounts
- **Re-quote handling:** Set max deviation to avoid re-quote loops

---

## 5. Evolution Roadmap — When to Add Sophistication

| Capital Level | Execution Enhancement | Why |
|---|---|---|
| **$7-$50** | Spread check + limit orders + session filtering | Simple, high-impact |
| **$50-$500** | Add partial fill handling, multi-pair correlation awareness | Position management becomes relevant |
| **$500-$5,000** | Add basic TWAP for entries >0.1 lot, trailing stop algorithms | Market impact starts to register |
| **$5,000-$50,000** | VWAP benchmarking, slippage analytics dashboard, smart execution routing | Execution cost becomes a measurable P&L factor |
| **$50,000+** | Full algo suite (TWAP/VWAP/ICEBERG), multi-venue routing, latency optimization | Institutional-grade execution justified |

---

## 6. Anti-Patterns to Avoid

| Anti-Pattern | Why It's Bad at $7 |
|---|---|
| Over-engineering execution for 0.01 lot | Development time > saved slippage by 100x |
| Using market orders during news | One bad fill can lose 30-50% of capital |
| Trading exotic pairs for "diversification" | Spread cost eats capital faster than alpha generates it |
| Chasing fills (re-entering after slippage) | Compounds losses, emotional execution |
| Ignoring spread because "it's small" | 1.4% per trade × 10 trades/day × 250 days = 3,500% annual spread cost |

---

## 7. Practical Implementation Checklist

```
□  Spread filter: Reject entry if spread > 2x 1-hour average
□  Session filter: Only trade during London-NY overlap (13:00-17:00 UTC)
□  News filter: Close/no-open 30 min before/after high-impact events
□  Order type: Default to LIMIT orders, MARKET only for confirmed breakouts
□  Slippage cap: Max 3 pips deviation on any order
□  Logging: Record actual fill price vs. intended price for every trade
□  Review: Weekly analysis of execution quality (avg slippage per trade)
```

---

## 8. Key Takeaway

> **At $7, execution sophistication is the wrong optimization target.**
>
> Your edge comes from: (1) signal quality, (2) risk management, (3) avoiding catastrophic slippage during news. A perfectly executed bad trade still loses money. A slightly imperfect good trade still makes money.
>
> Build the simple execution rules above. Log everything. Add complexity only when position sizes justify it ($500+ capital). The algorithms aren't going anywhere — but your $7 will be if you spend it on slippage during NFP.
