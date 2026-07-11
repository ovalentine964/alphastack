# Transaction Cost Analysis (TCA): Alpha Stack — FXPesa / MT5 / $7 Capital

**Date:** 2026-07-11
**Broker:** FXPesa (EGM Securities Ltd, regulated by Kenya CMA #107)
**Platform:** MetaTrader 5
**Capital:** $7 USD
**Account Type:** Standard (Premier requires $100 min deposit — not available)

---

## 1. EXECUTIVE SUMMARY

Trading with $7 on FXPesa Standard account is **extremely constrained**. The minimum tradeable unit (0.01 lots) on major forex pairs costs **$0.14 round-trip in spread alone** — that's **2% of your capital per trade**. Break-even requires at minimum a 1.4-pip move in your favor on EURUSD. With swaps, slippage, and the need to survive drawdowns, this account is operating at the razor's edge of viability.

**⚠️ CRITICAL: FXPesa does NOT offer crypto CFDs.** Their product range covers forex, indices, commodities, shares, ETFs, and futures only. "Crypto" is not available on this broker.

---

## 2. ACCOUNT STRUCTURE

### Standard Account (the only option at $7)
| Parameter | Value |
|---|---|
| Minimum deposit | $0 (no minimum) |
| Commission | $0 |
| Spread type | Variable |
| Leverage | Up to 1:400 |
| Min lot size | 0.01 lots (1,000 units) |
| Platform | MT4, MT5, MQ WebTrader, Equiti Trader |
| Swap/Islamic | Swap charges apply (see §5) |

### Premier Account (NOT available — $100 min deposit)
| Parameter | Value |
|---|---|
| Commission | $3.50/lot per side = **$7.00/lot round-trip** |
| Spreads | From 0.0 pips |

---

## 3. SPREAD COSTS (THE PRIMARY COST)

### How Spread Cost Works
```
Spread Cost = Spread (pips) × Pip Value × Lot Size
```

For a **0.01 micro lot**:
- **EUR/USD:** pip value = $0.10 per pip
- **GBP/USD:** pip value = $0.10 per pip
- **USD/JPY:** pip value = $0.10 per pip (approx)

### Detailed Spread Costs per Trade (0.01 lot, Standard Account)

| Pair | Typical Spread | Round-Trip Cost | % of $7 Capital |
|------|---------------|----------------|-----------------|
| **EURUSD** | 1.4 pips | **$0.14** | **2.0%** |
| **USDJPY** | 1.4 pips | **$0.14** | **2.0%** |
| **GBPUSD** | 2.2 pips | **$0.22** | **3.1%** |
| **AUDUSD** | 1.5 pips | **$0.15** | **2.1%** |
| **USDCAD** | 2.0 pips | **$0.20** | **2.9%** |
| **USDCHF** | 2.0 pips | **$0.20** | **2.9%** |
| **NZDUSD** | 2.0 pips | **$0.20** | **2.9%** |
| **EURGBP** | 2.0 pips | **$0.20** | **2.9%** |
| **EURJPY** | 2.2 pips | **$0.22** | **3.1%** |
| **GBPJPY** | 2.5 pips | **$0.25** | **3.6%** |

### Worst Offenders (Exotic Pairs — AVOID on $7)
| Pair | Spread | Cost (0.01 lot) | % of Capital |
|------|--------|-----------------|--------------|
| EURMXN | 159.2 pips | ~$1.59 | 22.7% |
| EURNOK | 145.3 pips | ~$1.45 | 20.7% |
| GBPNOK | 148.4 pips | ~$1.48 | 21.2% |
| USDZAR | 140.8 pips | ~$1.41 | 20.1% |

**Verdict: Exotics are capital suicide at $7. Stick to majors only.**

---

## 4. COMMISSION

**Standard Account: $0 commission.** This is the only viable account type at $7.

The cost is embedded in the wider spreads (1.4+ pips vs 0.0 pips on Premier).

**Effective "hidden" commission equivalent:**
- EURUSD: 1.4 pips × $0.10 = $0.14 per 0.01 lot round-trip
- This is comparable to or better than many commission-based accounts at micro-lot level

---

## 5. SWAP / FINANCING FEES (Overnight Holding Costs)

Swap rates are charged/recredited daily when positions roll past 21:00 GMT (T+2 settlement). **Triple swap on Wednesdays.**

### Selected Swap Rates (points per day, 1 standard lot)
| Pair | Long Swap | Short Swap | Direction Favor |
|------|-----------|------------|-----------------|
| EURUSD | -7.768 | +1.119 | Short earns |
| GBPUSD | -3.184 | -3.156 | Both pay |
| USDJPY | +16.896 | -32.934 | Long earns |
| AUDUSD | -0.901 | +2.968 | Short earns |
| USDCAD | +3.899 | -7.343 | Long earns |

**At 0.01 lots, swap = value ÷ 100:**
- EURUSD long: -$0.078/day | short: +$0.011/day
- USDJPY long: +$0.169/day | short: -$0.329/day

**Impact at $7 capital:**
- Holding a losing EURUSD long for 3 days: ~$0.24 in swap = **3.4% of capital drained**
- Swap costs are small per day but compound quickly on a tiny account

### Swap Formula (FXPesa)
```
Lots × Contract Size × Long/Short Swap × Point Size
0.01 × 100,000 × -7.768 × 0.0001 = -$0.0777 per day (EURUSD long)
```

---

## 6. SLIPPAGE & EXECUTION

FXPesa is a market maker / STP broker. Slippage factors:

| Factor | Impact |
|---|---|
| Normal market conditions | 0-0.5 pips slippage |
| High volatility (news) | 1-5+ pips slippage |
| Stop-loss execution | Can gap past your stop |
| Micro lot execution | Generally good (less liquidity concern) |

**Estimated slippage cost per trade: $0.00–$0.05 (normal conditions)**

At $7 capital, even 0.5 pips slippage = $0.005 = 0.07% — manageable in normal conditions. During news events, slippage can exceed the spread itself.

---

## 7. DEPOSIT & WITHDRAWAL FEES

### Deposit Methods (Kenya-focused)
| Method | Fee | Processing |
|---|---|---|
| M-Pesa | **Free** (FXPesa charges $0) | Instant |
| Bank Transfer | Bank fees may apply | 1-3 days |
| Credit/Debit Card | **Free** | Instant |

### Withdrawal
| Method | Fee | Processing |
|---|---|---|
| M-Pesa | **Free** (FXPesa charges $0) | 1-24 hours |
| Bank Transfer | Bank fees may apply | 1-3 days |

**Note:** Currency conversion fees may apply if depositing KES to a USD account.

### Welcome Bonus
- 100% bonus on first deposit (min $10)
- **CANNOT be used to cover losses**
- **CANNOT be withdrawn**
- Removed if equity falls to ≤5% of total
- With $7 deposit, bonus = $7 credit (but min deposit for bonus is $10, so $7 doesn't qualify)

---

## 8. TOTAL COST PER TRADE: THE REAL NUMBERS

### Round-Trip Cost Breakdown (0.01 lot, Standard Account)

| Cost Component | EURUSD | GBPUSD | USDJPY |
|---|---|---|---|
| Spread | $0.14 | $0.22 | $0.14 |
| Commission | $0.00 | $0.00 | $0.00 |
| Slippage (est.) | $0.01 | $0.01 | $0.01 |
| **Total (day trade)** | **$0.15** | **$0.23** | **$0.15** |
| Swap (1 night) | ±$0.08 | ~$0.03 | ±$0.33 |
| **Total (swing, 1 night)** | **$0.07–$0.23** | **$0.20–$0.26** | **-$0.18 to $0.48** |

### As Percentage of $7 Capital

| Pair | Day Trade Cost | % of Capital |
|---|---|---|
| EURUSD | $0.15 | **2.1%** |
| GBPUSD | $0.23 | **3.3%** |
| USDJPY | $0.15 | **2.1%** |
| GBPJPY | $0.26 | **3.7%** |

---

## 9. BREAK-EVEN ANALYSIS

### How Many Pips to Break Even?

| Pair | Spread (pips) | Min Profit Move | Risk:Reward Implication |
|---|---|---|---|
| EURUSD | 1.4 | 1.4 pips | Need R:R > 1:1 to profit after costs |
| GBPUSD | 2.2 | 2.2 pips | Need R:R > 1:1.5 |
| USDJPY | 1.4 | 1.4 pips | Need R:R > 1:1 |

### Dollar Break-Even per Trade
- **EURUSD:** Need $0.15 profit to break even → 1.5 pips move at 0.01 lot
- **Daily cost budget:** At $7 capital, spending $0.15/trade means you can make ~46 trades before going broke (from costs alone)
- **Realistic daily trades:** 2-4 trades max to preserve capital

### Risk of Ruin Calculation
- At $0.15 cost per trade with $7 capital
- 46 trades = $6.90 in costs alone
- With 50% win rate and 1:1 R:R, expected value per trade: $0.00 (pre-costs)
- **After costs: negative expectancy** → account will drain to zero

---

## 10. COST MINIMIZATION STRATEGIES

### ✅ DO
1. **Trade only EURUSD and USDJPY** — lowest spread (1.4 pips)
2. **Day trade only** — avoid swap costs entirely
3. **Trade during London/NY overlap** (13:00-17:00 GMT) — tightest spreads, best liquidity
4. **Use limit orders** — avoid slippage on entry
5. **Set stop-losses during liquid hours** — reduce gap/slippage risk
6. **Aim for 3-5 pip targets minimum** — 2× spread as minimum target
7. **Deposit more if possible** — even $10-20 dramatically improves viability
8. **Use the 1:400 leverage wisely** — don't over-leverage, but don't under-use it either

### ❌ DON'T
1. **Don't trade exotics** — spread eats 20%+ of capital per trade
2. **Don't hold overnight** — swap costs compound on losing positions
3. **Don't scalp 1-pip targets** — spread alone exceeds profit target
4. **Don't trade during news** — slippage can be catastrophic at $7
5. **Don't trade crypto** — FXPesa doesn't offer it
6. **Don't trade indices/commodities** — wider spreads, larger contract sizes

---

## 11. CRYPTO: NOT AVAILABLE ON FXPESA

FXPesa's product lineup:
- ✅ Forex (60+ pairs)
- ✅ Indices (US30, NAS100, etc.)
- ✅ Commodities (Gold, Silver, Oil)
- ✅ Shares (US, UK, EU stocks)
- ✅ ETFs
- ✅ Futures
- ❌ **NO Cryptocurrency CFDs**

If crypto trading is required, you'll need a different broker (e.g., Exness, XM, IC Markets, or a dedicated crypto exchange like Binance).

---

## 12. VIABILITY ASSESSMENT

### Can You Trade Profitably with $7?

| Factor | Rating | Notes |
|---|---|---|
| Spread costs | ⚠️ High | 2-3.7% per trade |
| Commission | ✅ Zero | Standard account advantage |
| Swap costs | ⚠️ Variable | Avoidable by day trading |
| Slippage | ✅ Low | Normal conditions only |
| Deposit/withdrawal | ✅ Free | M-Pesa is free |
| Break-even difficulty | 🔴 Hard | Need 1.5-2.2 pip edge |
| Account survival | 🔴 Risky | ~46 trades before costs drain capital |

### The Math Reality
- **Cost per trade:** ~$0.15 (best case, EURUSD)
- **Trades to break even from costs alone:** 46 trades
- **Need per trade to profit:** >1.5 pips consistently
- **With 50% win rate at 1:2 R:R:** Expected profit = $0.25/trade, net = $0.10/trade after costs
- **With 50% win rate at 1:1 R:R:** Expected profit = $0.00, net = -$0.15/trade (guaranteed loss)

### Recommendation
$7 is **below the practical minimum** for sustainable forex trading. The cost structure alone makes it extremely difficult to generate positive expectancy. Options:

1. **Increase capital to $20-50** — drops cost-to-capital ratio to manageable levels
2. **Use demo account** to prove strategy before risking real money
3. **Focus exclusively on EURUSD/USDJPY day trades** with strict 1:2+ R:R targets
4. **Accept this as a learning account** — the $7 buys experience, not income

---

## 13. OPTIMAL TRADE PARAMETERS FOR $7

```
Pair:         EURUSD or USDJPY ONLY
Lot size:     0.01 (minimum)
Strategy:     Day trade only (close before 21:00 GMT)
Target:       3-5 pips minimum (1:2 R:R minimum)
Stop-loss:    1.5-2.5 pips
Max trades:   2-3 per day
Session:      London-NY overlap (13:00-17:00 GMT)
Max daily cost budget: $0.30 (4.3% of capital)
```

---

*Sources: FXPesa official website (fxpesa.com), FastBull broker review, swap rates from FXPesa financing fees page. Data as of July 2026.*
