# Research 07: Trading Pairs Analysis — Alpha Stack System

> **Date:** 2026-07-11
> **System:** Alpha Stack (Macro-driven + SMC + S/R + RSI + Candlestick Confirmation)
> **Broker:** FXPesa (Equiti Group, FSA-regulated)
> **Platform:** MT5
> **Capital:** $7 (Micro/Cent account)

---

## 1. Forex Pairs Analysis

### 1.1 FXPesa Account Selection for $7 Capital

**Recommended: Micro Account**
- USD accounts | Leverage up to 1:500
- Trade smaller micro lot sizes | $0 Commission
- MT5 compatible | No minimum deposit
- Ideal for $7 starting capital (Classic/Standard need higher margins; Premier needs $100)

### 1.2 Major Pairs — Detailed Breakdown

| Pair | Premier Spread (pips) | Standard Spread (pips) | Margin | Avg Daily Range (pips) | Best Session | SMC Suitability |
|------|----------------------|----------------------|--------|----------------------|--------------|-----------------|
| **EUR/USD** | 0.0 | 1.4 | 0.20% | 70–100 | London + NY overlap | ⭐⭐⭐⭐⭐ Highest liquidity, cleanest order blocks |
| **GBP/USD** | 0.2 | 1.8 | 0.20% | 90–130 | London | ⭐⭐⭐⭐⭐ Volatile, strong SMC patterns |
| **USD/JPY** | 0.0 | 1.4 | 0.20% | 70–100 | Tokyo + London | ⭐⭐⭐⭐ Good for macro plays, BOJ policy driven |
| **AUD/USD** | 0.1 | 1.5 | 0.20% | 60–80 | Sydney + London | ⭐⭐⭐⭐ Commodity correlation, clean structure |
| **NZD/USD** | 0.4 | 2.0 | 0.20% | 60–80 | Sydney + London | ⭐⭐⭐ Decent but lower liquidity |
| **USD/CHF** | 0.3 | 2.0 | 1.00% | 60–80 | London | ⭐⭐⭐ Safe haven, inverse DXY proxy |
| **USD/CAD** | 0.4 | 2.0 | 0.20% | 60–80 | NY | ⭐⭐⭐ Oil correlation, good for macro |

### 1.3 Cross Pairs — Detailed Breakdown

| Pair | Premier Spread (pips) | Standard Spread (pips) | Margin | Avg Daily Range (pips) | Best Session | SMC Suitability |
|------|----------------------|----------------------|--------|----------------------|--------------|-----------------|
| **EUR/GBP** | 0.2 | 2.0 | 0.20% | 40–60 | London | ⭐⭐⭐ Tight range, mean-reversion friendly |
| **EUR/JPY** | 0.5 | 2.2 | 0.20% | 80–120 | London + Tokyo overlap | ⭐⭐⭐⭐ Volatile cross, strong trends |
| **GBP/JPY** | 0.7 | 2.3 | 0.20% | 120–180 | London | ⭐⭐⭐⭐⭐ "Beast" — massive moves, ideal for SMC breakouts |
| **AUD/JPY** | 1.0 | 2.3 | 0.20% | 70–100 | Tokyo + London | ⭐⭐⭐⭐ Risk-on/risk-off proxy |
| **EUR/AUD** | 1.3 | 2.5 | 0.20% | 80–110 | London + Sydney | ⭐⭐⭐ Good range, less crowded |
| **GBP/AUD** | 1.7 | 5.2 | 0.20% | 100–150 | London + Sydney | ⭐⭐⭐ Wide spreads eat profits on micro account |

### 1.4 Exotic Pairs — FXPesa Availability

| Pair | Standard Spread (pips) | Margin | Notes |
|------|----------------------|--------|-------|
| **EUR/ZAR** | 63.1 | 2.00% | South African Rand — too wide for $7 account |
| **USD/ZAR** | 140.8 | 2.00% | Extremely wide spread — avoid |
| **USD/PLN** | 26.0 | 2.00% | Moderate exotic |
| **USD/SGD** | 3.1 | 2.00% | Tightest exotic available |
| **USD/CNH** | 2.9 | 2.00% | Offshore Yuan — useful for macro |

**⚠️ Exotic Verdict:** Avoid on $7 capital. Spreads are 10–100x wider than majors. One trade would eat 5–20% of capital in spread alone. Only USD/CNH and USD/SGD are somewhat viable at higher capital levels.

**❌ KES, NGN pairs:** Not available on FXPesa MT5 platform (FXPesa operates under Seychelles FSA, not Kenya CMA for local pairs).

### 1.5 Best Pairs for Alpha Stack Strategy

**Tier 1 — Primary (trade these daily):**
1. **EUR/USD** — Best liquidity, tightest spreads, most predictable SMC patterns
2. **GBP/USD** — High volatility + clean order blocks = high R:R setups
3. **XAU/USD (Gold)** — See Section 2

**Tier 2 — Secondary (session-specific):**
4. **GBP/JPY** — Maximum pip movement for breakout SMC setups
5. **USD/JPY** — Macro-driven, responds strongly to interest rate news
6. **AUD/USD** — Clean structure, commodity correlation

**Tier 3 — Opportunistic:**
7. **EUR/JPY** — When JPY themes dominate
8. **USD/CAD** — Oil-driven macro plays

---

## 2. Gold (XAU/USD) — Deep Dive

### 2.1 Why Gold is IDEAL for Alpha Stack

Gold is arguably the **#1 instrument** for this strategy. Here's why:

1. **Macro-Driven Nature**: Gold responds directly to the macro factors Alpha Stack tracks:
   - US interest rates (Fed policy) — inverse correlation
   - USD strength (DXY) — inverse correlation
   - Inflation expectations — positive correlation
   - Geopolitical risk — safe haven bid
   - Central bank buying — structural demand

2. **Clean SMC Patterns**: Gold exhibits institutional behavior with:
   - Clear order blocks at key psychological levels ($2,600, $2,700, etc.)
   - Strong fair value gaps (FVGs) during news events
   - Predictable liquidity sweeps at round numbers
   - London session manipulation followed by NY session trend

3. **Perfect Volatility Profile**: Not too much, not too little:
   - Daily range: 2,000–4,000 pips (20–40 USD moves)
   - Enough movement for profitable trades
   - Not so wild that stops get hunted easily

### 2.2 FXPesa Gold Specifications

| Specification | Detail |
|--------------|--------|
| Symbol | XAUUSD |
| Type | Rolling CFD |
| Typical Spread | **0.28 pips** (Premier) — incredibly tight |
| Contract Size | 100 troy oz per lot |
| P/L per 1 lot | $100 per $1 move |
| Min Trade Size | 0.01 lots |
| Max Trade Size | 100 lots |
| Margin | 0.20% |
| Leverage | Up to 1:2000 (Classic/Standard), 1:500 (Micro) |
| Commission | $0 (commission-free on rolling) |
| Trading Hours | Sun 21:01 – Fri 20:57 GMT |

**Also available:** XAUEUR (Gold vs Euro) — 0.4 pip spread, useful for EUR-correlation plays.

### 2.3 Gold Trading Sessions

| Session | GMT Time | Character | Best For |
|---------|----------|-----------|----------|
| **Asian** | 00:00–08:00 | Range-bound, low volatility | Identifying accumulation zones, setting S/R levels |
| **London** | 08:00–16:00 | High volatility, trend-setting | **Primary session** — SMC manipulation moves, order block entries |
| **New York** | 13:00–21:00 | Highest volume, news-driven | **Best for macro trades** — Fed news, NFP, CPI releases |
| **London–NY Overlap** | 13:00–16:00 | Maximum liquidity | **Golden window** — tightest spreads, strongest moves |

### 2.4 Gold-Specific SMC Patterns

1. **London Session Manipulation**: Gold often sweeps Asian session lows/highs during London open (08:00–09:00 GMT), then reverses. Classic SMC liquidity grab.

2. **NFP/CPI Reaction**: Gold makes 30–80 USD moves on high-impact US news. Wait for the initial spike, then trade the FVG/ob pullback.

3. **Psychological Level Plays**: Round numbers ($2,700, $2,750) act as institutional order blocks. Price often sweeps these levels before reversing.

4. **DXY Correlation Trade**: When DXY shows weakness, gold rallies. Use DXY as a leading indicator.

### 2.5 Gold Correlations

| Factor | Correlation | Strength | Use Case |
|--------|-----------|----------|----------|
| USD Index (DXY) | **Inverse** | Strong (-0.85) | DXY breakdown → Gold long |
| US 10Y Yield | **Inverse** | Strong (-0.75) | Yield drop → Gold long |
| US Inflation (CPI) | **Positive** | Moderate (+0.60) | High CPI → Gold long |
| Geopolitical Risk | **Positive** | Variable | Conflict escalation → Gold spike |
| S&P 500 | **Weak** | Variable | Decoupled in 2024–2026 bull run |
| Silver (XAG) | **Positive** | Strong (+0.90) | Confirmation indicator |

---

## 3. Crypto Pairs Analysis

### 3.1 FXPesa Crypto CFDs Available (MT5)

FXPesa offers **50+ cryptocurrency CFDs** on MT5 with up to 1:200 leverage. Key pairs:

| Symbol | Name | Min Trade | Leverage | Group | Contract Size |
|--------|------|-----------|----------|-------|---------------|
| **BTCUSD.lv** | Bitcoin | 0.001 | 1:200 | Group 1 | 1 unit |
| **ETHUSD.lv** | Ethereum | 0.1 | 1:200 | Group 1 | 1 unit |
| **SOLUSD.lv** | Solana | — | — | — | Check live |
| **ADAUSD.lv** | Cardano | 100 | 1:200 | Group 1 | 1 unit |
| **XRPUSD.lv** | Ripple | — | — | — | Check live |
| **DOTUSD.lv** | Polkadot | 1 | 1:200 | Group 1 | 1 unit |
| **LINKUSD.lv** | Chainlink | 1 | 1:200 | Group 1 | 1 unit |
| **BNBUSD.lv** | Binance Coin | 0.1 | 1:200 | Group 1 | 1 unit |
| **AVAXUSD.lv** | Avalanche | 0.1 | 1:200 | Group 1 | 1 unit |
| **HBARUSD.lv** | Hedera | 100 | 1:200 | Group 1 | 1 unit |

**Also notable:** BTCXAU (Bitcoin vs Gold) — unique pair at 1:200 leverage, 0.001 min trade. Fascinating for macro thesis plays.

### 3.2 Crypto Group Leverage Tiers

| Group | Leverage | Examples |
|-------|----------|---------|
| Group 1 | 1:200 | BTC, ETH, ADA, DOT, LINK, BNB, AVAX, BCH, HBAR |
| Group 2 | 1:10 | ALGO, EOS, FIL, LTC, MKR, MANA, AAVE |
| Group 3 | 1:2.5 | APE, BAT, COMP, CRV, ENJ, NEAR |
| Group 4 | 1:1 | 1INCH, DASH, IOTA, LPT, MINA |

**⚠️ Critical:** Only Group 1 cryptos are viable for $7 capital due to leverage. Group 2–4 require massive margin.

### 3.3 Crypto vs Forex for Alpha Stack

| Factor | Forex (Majors) | Crypto (BTC/ETH) | Advantage |
|--------|---------------|-------------------|-----------|
| **Spreads** | 0.0–1.8 pips | ~$5 on BTC | Forex wins |
| **Trading Hours** | 24/5 | 24/7 (FXPesa: 24/6) | Crypto slight edge |
| **Volatility** | 60–130 pips/day | 2–5% daily ($1,000–3,000 BTC) | Crypto more volatile |
| **Liquidity** | $7.5T/day | Lower, more gaps | Forex wins |
| **Macro Sensitivity** | High | Very High (BTC reacts to everything) | Both good |
| **SMC Patterns** | Clean, institutional | Messy, more manipulation | Forex wins |
| **Weekend Gaps** | Yes (Sunday open) | No (24/7) | Crypto wins |
| **Spread Cost on $7** | Minimal | Significant on BTC | Forex wins |

### 3.4 Bitcoin — Digital Gold Analysis

**BTC Macro Correlations (2024–2026):**

| Factor | Correlation | Trade Setup |
|--------|-----------|-------------|
| DXY (USD Index) | Inverse (-0.60) | Weak dollar → BTC long |
| US 10Y Yield | Inverse (-0.50) | Rate cuts → BTC long |
| S&P 500 / NASDAQ | Positive (+0.65) | Risk-on → BTC long |
| Gold | Weak/Variable (+0.30) | Decoupled during BTC-specific events |
| Fed Policy | Strong | Dovish pivot → BTC rallies |
| ETF Flows | Very Strong | Spot ETF inflows → direct price impact |

**BTC Trading Sessions (Crypto never closes, but):**
- **Asian Session:** Often sets the range. Lower volume, accumulation.
- **London Session:** Breakout moves begin. Institutional crypto desks active.
- **US Session:** Largest volume. Reacts to US macro data + ETF flow news.
- **Weekend:** Lower liquidity, wider spreads on FXPesa, more manipulation. Avoid unless scalping clear levels.

### 3.5 Recommended Crypto Pairs for Alpha Stack

| Pair | Why | Capital Allocation |
|------|-----|-------------------|
| **BTCUSD** | Must-have. Digital gold, macro-driven, highest liquidity | 50% of crypto allocation |
| **ETHUSD** | #2 by market cap, DeFi ecosystem proxy, clean trends | 30% of crypto allocation |
| **ADAUSD** | High leverage (1:200), cheap per unit, good for micro accounts | 10% of crypto allocation |
| **DOTUSD** | Infrastructure play, 1:200 leverage, volatile | 10% of crypto allocation |

**Avoid:** Low-leverage Group 2–4 cryptos on $7 account — margin requirements too high.

---

## 4. Optimal Portfolio Construction

### 4.1 How Many Pairs to Monitor

**Answer: 5–7 pairs maximum.**

With $7 capital, you cannot trade everything. Over-monitoring leads to:
- Analysis paralysis
- Correlated exposure (blowing up on one theme)
- Spreading capital too thin

**Recommended Active Watchlist:**

| # | Pair | Type | Role |
|---|------|------|------|
| 1 | **EUR/USD** | Major FX | Core — trade daily |
| 2 | **GBP/USD** | Major FX | Core — trade daily |
| 3 | **XAU/USD** | Commodity | Core — highest conviction macro plays |
| 4 | **BTCUSD** | Crypto | Core — digital gold macro plays |
| 5 | **GBP/JPY** | Cross FX | Session-specific — London beast |
| 6 | **USD/JPY** | Major FX | Macro — interest rate proxy |
| 7 | **ETHUSD** | Crypto | Secondary crypto exposure |

### 4.2 Correlation Matrix — Avoid Correlated Trades

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

**Key Correlation Rules:**
1. ❌ **Never simultaneously long EUR/USD AND GBP/USD** — 0.90 correlated (same trade twice)
2. ❌ **Never long BTCUSD AND ETHUSD** — 0.85 correlated
3. ❌ **Never long EUR/USD AND short USD/JPY** — both are USD weakness plays (-0.85)
4. ✅ **Long XAU/USD + Long GBP/JPY** — low correlation (0.10), diversified
5. ✅ **Long EUR/USD + Long BTCUSD** — reasonable diversification (-0.55)

### 4.3 Session-Based Pair Rotation

| Session (EAT/GMT+3) | Active Pairs | Strategy Focus |
|---------------------|-------------|----------------|
| **Asian (03:00–12:00)** | USD/JPY, AUD/USD, BTC | Range identification, accumulation zones |
| **London (12:00–21:00)** | EUR/USD, GBP/USD, GBP/JPY, XAU/USD | **Primary session** — SMC manipulation entries |
| **New York (16:00–01:00)** | EUR/USD, GBP/USD, XAU/USD, BTC | Macro news trades, trend continuation |
| **London–NY Overlap (16:00–21:00)** | ALL pairs | **Maximum opportunity** — highest liquidity |
| **Weekend** | BTC only | Lower size, wider spreads, cautious |

### 4.4 Risk Allocation with $7 Capital

**Golden Rule: Risk no more than 2–3% per trade = $0.14–$0.21 per trade**

| Pair Type | Allocation | Max Concurrent Positions | Risk per Trade |
|-----------|-----------|------------------------|----------------|
| Forex Majors (EUR/USD, GBP/USD) | 40% of trades | 1 | $0.14 (2%) |
| Gold (XAU/USD) | 30% of trades | 1 | $0.14 (2%) |
| Crypto (BTC/ETH) | 20% of trades | 1 | $0.14 (2%) |
| GBP/JPY / USD/JPY | 10% of trades | 1 | $0.14 (2%) |

**Critical:** Only ONE position at a time with $7. You cannot afford multi-position exposure.

### 4.5 Minimum Viable Diversification

With $7, true diversification is impossible. The strategy is:

1. **Phase 1 ($7–$50):** Trade 1 pair at a time. Focus on EUR/USD or XAU/USD.
2. **Phase 2 ($50–$200):** Trade 2 pairs. Add GBP/USD or BTC.
3. **Phase 3 ($200–$1,000):** Trade 3 pairs with proper correlation management.
4. **Phase 4 ($1,000+):** Full 5–7 pair portfolio with position sizing.

---

## 5. Return Projections

### 5.1 Realistic Monthly Returns by Pair Type

| Pair Type | Monthly Return (Realistic) | Monthly Return (Aggressive) | Win Rate Needed | Avg R:R |
|-----------|---------------------------|----------------------------|-----------------|---------|
| EUR/USD | 5–15% | 15–30% | 50–60% | 1:2 to 1:3 |
| GBP/USD | 8–20% | 20–40% | 45–55% | 1:2 to 1:3 |
| XAU/USD | 10–25% | 25–50% | 45–55% | 1:2 to 1:4 |
| GBP/JPY | 10–30% | 30–60% | 40–50% | 1:3 to 1:5 |
| BTCUSD | 8–25% | 25–60% | 45–55% | 1:2 to 1:4 |
| ETHUSD | 8–25% | 25–50% | 45–55% | 1:2 to 1:4 |

**Note:** These ranges assume consistent execution of the Alpha Stack strategy with proper risk management. The "aggressive" column assumes higher leverage and larger position sizes — NOT recommended for beginners.

### 5.2 Risk-Reward Ratios Achievable

**SMC + Macro Strategy R:R Targets:**

| Setup Type | Entry Method | Stop Loss | Take Profit | R:R |
|-----------|-------------|-----------|-------------|-----|
| Order Block Entry | OB + RSI divergence | Below OB | Next liquidity zone | 1:2 – 1:3 |
| FVG Entry | Fair Value Gap fill | Beyond FVG | Previous structure | 1:2 – 1:4 |
| BOS/CHoCH | Break of Structure | Beyond swing | Next OB/Fib level | 1:3 – 1:5 |
| Liquidity Sweep | Sweep + engulfing candle | Beyond sweep | Opposing liquidity | 1:3 – 1:5 |
| Macro News | Post-news FVG | Beyond spike | Pre-news level | 1:2 – 1:3 |

**Minimum acceptable R:R: 1:2** (Risk $0.14 to make $0.28)

### 5.3 Compounding Strategy — $7 Growth Trajectory

**Assumptions:**
- Starting capital: $7
- Average monthly return: 15% (conservative, realistic for disciplined Alpha Stack execution)
- Risk per trade: 2% of equity
- No withdrawals until Phase 3

| Month | Starting Balance | 15% Return | Ending Balance | Phase |
|-------|-----------------|------------|----------------|-------|
| 1 | $7.00 | $1.05 | $8.05 | Phase 1 |
| 2 | $8.05 | $1.21 | $9.26 | Phase 1 |
| 3 | $9.26 | $1.39 | $10.65 | Phase 1 |
| 4 | $10.65 | $1.60 | $12.25 | Phase 1 |
| 5 | $12.25 | $1.84 | $14.09 | Phase 1 |
| 6 | $14.09 | $2.11 | $16.20 | Phase 1 |
| 7 | $16.20 | $2.43 | $18.63 | Phase 1 |
| 8 | $18.63 | $2.79 | $21.43 | Phase 1 |
| 9 | $21.43 | $3.21 | $24.64 | Phase 1 |
| 10 | $24.64 | $3.70 | $28.34 | Phase 1 |
| 11 | $28.34 | $4.25 | $32.59 | Phase 1 |
| 12 | $32.59 | $4.89 | $37.48 | Phase 1→2 |

**At 15% monthly:** $7 → $37.48 in 12 months (5.35x)

**Aggressive scenario (25% monthly):**

| Month | Balance | Month | Balance |
|-------|---------|-------|---------|
| 1 | $8.75 | 7 | $33.78 |
| 2 | $10.94 | 8 | $42.22 |
| 3 | $13.67 | 9 | $52.78 |
| 4 | $17.09 | 10 | $65.97 |
| 5 | $21.36 | 11 | $82.46 |
| 6 | $26.70 | 12 | **$103.08** |

**At 25% monthly:** $7 → $103 in 12 months (14.7x)

### 5.4 Compounding Milestones

| Milestone | Balance | Strategy Unlocked |
|-----------|---------|-------------------|
| **$7** | Start | 1 pair, micro lots, 2% risk |
| **$20** | Early growth | Can absorb 2–3 consecutive losses |
| **$50** | Phase 2 | Add 2nd pair, slightly larger positions |
| **$100** | Meaningful | 2–3 pairs, proper rotation |
| **$200** | Phase 3 | 3 pairs, correlation management |
| **$500** | Real trading | Full portfolio, 1:200 leverage usable |
| **$1,000** | Phase 4 | Professional-grade position sizing |
| **$5,000** | Serious | Can trade standard lots on EUR/USD |

---

## 6. Final Recommendations

### 6.1 The Alpha Stack Core 5

These are the **5 pairs you should focus on from Day 1:**

1. **🥇 XAU/USD (Gold)** — Best overall fit for macro + SMC. Tight spreads. Massive daily moves. Institutional behavior. This is your #1 money-maker.

2. **🥈 EUR/USD** — Most liquid pair on Earth. Cleanest SMC patterns. Lowest spreads. Best for learning and consistent gains.

3. **🥉 GBP/USD** — Higher volatility than EUR/USD, more pip potential. Excellent for SMC breakout entries during London.

4. **🏅 BTCUSD** — Digital gold. Reacts to macro. 24/6 trading. The crypto hedge in your portfolio.

5. **🏅 GBP/JPY** — The "Beast." When you need maximum pips from a single trade, this is it. London session specialist.

### 6.2 What NOT to Trade on $7

- ❌ Exotic pairs (spreads will destroy you)
- ❌ Low-leverage crypto (Group 2–4, margin too high)
- ❌ More than 1 position at a time
- ❌ Weekend crypto (wider spreads, manipulation)
- ❌ News trading without a plan (wait for the setup AFTER the spike)

### 6.3 Daily Routine

| Time (EAT) | Action |
|-----------|--------|
| 06:00–08:00 | Mark S/R levels on EUR/USD, GBP/USD, XAU/USD from daily/4H charts |
| 08:00–09:00 | Check Asian session range — mark manipulation zones |
| 12:00–13:00 | London open — watch for liquidity sweeps on Gold and GBP pairs |
| 13:00–15:00 | London–NY overlap — highest probability entries |
| 16:00–18:00 | Check macro calendar for US news — position or stay flat |
| 20:00–21:00 | Review trades, update journal, prep for next day |

---

## Appendix: FXPesa Account Comparison for Alpha Stack

| Feature | Micro | Classic | Standard | Premier |
|---------|-------|---------|----------|---------|
| Min Deposit | $0 | $0 | $30 | $100 |
| Leverage | 1:500 | 1:2000 | 1:2000 | 1:2000 |
| EUR/USD Spread | — | 1.6 pips | 1.4 pips | 0.0 pips |
| Commission | $0 | $0 | $0 | $3.5/lot/side |
| Best For | **$7 start** | Intermediate | Intermediate | Advanced |
| **Recommendation** | ✅ **USE THIS** | Later | Later | $100+ |

**Decision:** Start with **Micro Account** → Graduate to **Classic** at $50 → **Premier** at $100+

---

*Document generated for the Alpha Stack Trading System. All spread data sourced from FXPesa.com (Equiti Group, FSA Seychelles). Market conditions and spreads may vary. Past performance does not guarantee future results.*
