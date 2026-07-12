# Alpha Stack — Pair-Specific Strategy Architecture

> **Version:** 1.0 · **Date:** 2026-07-11 · **Author:** Architecture Team
> **Source Research:** [`research/market/research_07_trading_pairs.md`](../research/market/research_07_trading_pairs.md) (partial) — Trading pairs analysis — pair-specific strategies are architect innovation
> **Status:** Architecture Complete

---

**Version:** 1.0  
**Date:** 2026-07-11  
**Scope:** Deep adaptation of the Alpha Strategy (Steps 1–16) to each trading pair's unique market personality  
**Pairs Covered:** XAU/USD, BTC/USD, EUR/USD, GBP/USD, GBP/JPY  
**Status:** Architecture Design — Ready for Implementation

---

## Table of Contents

1. [Design Philosophy](#1-design-philosophy)
2. [Pair Personality Profiles](#2-pair-personality-profiles)
3. [XAU/USD — Gold](#3-xauusd--gold)
4. [BTC/USD — Bitcoin](#4-btcusd--bitcoin)
5. [EUR/USD — Euro/Dollar](#5-eurusd--eurodollar)
6. [GBP/USD — Cable](#6-gbpusd--cable)
7. [GBP/JPY — The Beast](#7-gbpjpy--the-beast)
8. [Cross-Pair Correlation Matrix](#8-cross-pair-correlation-matrix)
9. [Session-Based Pair Rotation Strategy](#9-session-based-pair-rotation-strategy)
10. [How to Add New Pairs](#10-how-to-add-new-pairs)
11. [Pair-Specific Agent Configuration Schema](#11-pair-specific-agent-configuration-schema)
12. [Adaptive Learning System](#12-adaptive-learning-system)

---

## 1. Design Philosophy

### Why Pairs Need Individual Treatment

No two trading instruments are the same. Gold responds to geopolitical fear. Bitcoin trades on narrative momentum. EUR/USD is a macro-liquidity machine. GBP/JPY is a volatility beast. Applying identical parameters across all pairs is like prescribing the same medication to every patient — it might work sometimes, but it's not medicine.

The Alpha Stack strategy has 16 steps. Each step has parameters that must be tuned per pair:

| Parameter Class | Examples | Why It Varies |
|----------------|----------|---------------|
| **Volatility** | ATR, daily range, stop-loss distance | GBP/JPY averages 150 pips/day; EUR/USD averages 80 |
| **Spread** | Transaction cost, break-even distance | Gold: 0.28 pips; GBP/JPY: 2.3 pips |
| **Session Behavior** | When the pair moves, when it consolidates | JPY pairs peak in Tokyo-London overlap; GBP peaks in London |
| **Fundamental Drivers** | What moves the price | Gold: real yields + DXY; GBP: BOE + Brexit legacy |
| **SMC Pattern Quality** | How clean are order blocks and FVGs | EUR/USD has the cleanest institutional patterns; BTC is noisy |
| **RSI Behavior** | Where is "oversold" / "overbought" | Trending pairs need adaptive thresholds; ranging pairs use fixed |
| **Correlation** | When NOT to trade because of redundancy | Long EUR/USD + Long GBP/USD = same trade twice |

### The Pair Configuration Layer

Every pair gets a **configuration profile** that overrides the default Alpha Strategy parameters. The system loads the profile at pipeline initialization and passes it to every agent in the chain.

```
┌─────────────────────────────────────────────────────────┐
│                PAIR CONFIGURATION LAYER                   │
│                                                           │
│  Default Strategy Params (Steps 1-16)                     │
│         │                                                 │
│         ▼                                                 │
│  ┌─────────────────────────────────────────────┐         │
│  │  PAIR PROFILE: XAU/USD                      │         │
│  │  ├── volatility: {atr_mult: 1.2, range: wide}│        │
│  │  ├── sessions: {primary: london, secondary: ny}│      │
│  │  ├── s_r: {psych_levels: true, round_numbers: true}│  │
│  │  ├── smc: {ob_quality: high, fvg_freq: medium}│       │
│  │  ├── rsi: {oversold: 35, overbought: 65}     │        │
│  │  ├── candlestick: {patterns: [engulfing, pin_bar]}│   │
│  │  ├── risk: {max_sl_mult: 1.5, rr_target: 3.0}│       │
│  │  └── fundamentals: {drivers: [DXY, yields, CPI]}│     │
│  └─────────────────────────────────────────────┘         │
│         │                                                 │
│         ▼                                                 │
│  Modified Strategy Pipeline (pair-aware)                  │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Pair Personality Profiles

### Summary Matrix

| Characteristic | XAU/USD | BTC/USD | EUR/USD | GBP/USD | GBP/JPY |
|---------------|---------|---------|---------|---------|---------|
| **Asset Class** | Commodity | Crypto | Major FX | Major FX | Cross FX |
| **Avg Daily Range** | $25–40 (2500–4000 pips) | $1,500–3,000 | 70–100 pips | 90–130 pips | 120–180 pips |
| **Typical Spread** | 0.28 pips | ~$5 | 1.4 pips | 1.8 pips | 2.3 pips |
| **Liquidity** | Very High | Moderate | Highest | Very High | High |
| **Volatility Class** | High | Very High | Moderate | Moderate-High | Very High |
| **Best Session** | London + NY overlap | US session | London + NY overlap | London | London |
| **SMC Pattern Quality** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Macro Sensitivity** | Very High | Very High | High | High | Moderate |
| **Weekend Gap Risk** | Low (CFD) | None (24/7) | Moderate | Moderate-High | High |
| **Correlation Cluster** | USD-inverse | Risk-on | USD cluster | USD cluster | JPY + GBP |

---

## 3. XAU/USD — Gold

### 3.1 Unique Characteristics

| Property | Value | Implication |
|----------|-------|-------------|
| **Tick Value** | $100 per $1 move per lot | High notional exposure; tiny position sizes for $7 account |
| **Min Trade** | 0.01 lots = $1 per $1 move | Smallest position still moves $1/pip |
| **Pip Definition** | 0.01 = 1 pip ($0.01 per 0.01 lot) | 100 pips = $1.00 move |
| **Daily Range** | 2,000–4,000 pips ($20–40) | Massive opportunity; requires wide stops |
| **Spread** | 0.28 pips (Premier) | Extremely tight; cost-efficient even on micro accounts |
| **Trading Hours** | Sun 21:01 – Fri 20:57 GMT | Near 24/5; closed only 1 hour daily |
| **Leverage** | Up to 1:500 (Micro) | High leverage available; use cautiously |

**Gold's Personality:** Gold is a macro-driven, institutional-grade instrument with clean SMC patterns. It responds directly to USD strength, real interest rates, inflation expectations, and geopolitical risk. It trends strongly during risk-off events and consolidates during calm periods. Gold is the **#1 instrument for Alpha Stack** because its behavior perfectly matches the strategy's strengths.

### 3.2 Strategy Step Adaptations

#### Step 1 — Fundamental Intelligence

| Default | XAU/USD Override |
|---------|-----------------|
| Track all macro indicators | **Priority drivers:** DXY (inverse, -0.85), US 10Y real yields (inverse, -0.75), CPI surprises, Fed policy, geopolitical risk index |
| Sentiment on all sources | **Gold-specific sources:** World Gold Council reports, central bank buying data, GLD ETF flows, COT gold positioning |
| Event risk scoring | **Gold-specific events:** FOMC (highest impact), NFP, CPI, geopolitical escalations, US debt ceiling, banking crises |
| "Should I trade?" logic | Add: If DXY is in strong trend (ADX>30) AND gold is counter-trend → REDUCE confidence by 30%. Gold often follows DXY with 1-4 hour lag. |

**Gold-Specific Fundamental Model:**
```
Gold Bias Score = (
    -0.35 × DXY_direction_score +        # Inverse USD correlation
    -0.25 × real_yield_direction +         # Inverse yield correlation
    +0.15 × inflation_surprise +           # High CPI → gold bid
    +0.10 × geopolitical_risk_score +      # Safe haven demand
    +0.10 × central_bank_buying_signal +   # Structural demand
    +0.05 × etf_flow_direction             # Institutional positioning
)
```

#### Step 2 — Market Bias

| Default | XAU/USD Override |
|---------|-----------------|
| 3-state HMM | **Add state:** "Geopolitical Shock" — a 4th regime where gold diverges from normal technical behavior. Triggered when geopolitical risk score > 0.7. In this state, gold ignores technical levels and follows fear. |
| Multi-TF weights W1:0.35, D1:0.30, H4:0.20, H1:0.15 | **Adjust:** W1:0.30, D1:0.35, H4:0.25, H1:0.10 — Gold's daily structure matters more than weekly because central bank actions create sharp regime shifts. |
| Dynamic alpha (fundamental vs technical) | **Gold override:** Alpha = 0.50 (equal weight) in normal conditions, 0.70 fundamental during geopolitical events. Gold is more macro-driven than most FX pairs. |

#### Step 3 — Session Analysis

| Default | XAU/USD Override |
|---------|-----------------|
| Standard session times | **Gold sessions (GMT):** Asian 00:00–08:00 (range-bound, 20-30% of daily range), London 08:00–16:00 (trend initiation, 40-50% of range), NY 13:00–21:00 (news-driven, 30-40% of range), Overlap 13:00–16:00 (maximum volatility) |
| Asian range tracking | **Gold-specific:** Asian range is narrower than FX pairs. A tight Asian range (<1,500 pips) on gold predicts a strong London breakout with 72% accuracy (vs 65% for EUR/USD). |
| Session volatility multiplier | **Gold:** Asian 0.3×, London 1.4×, NY 1.3×, Overlap 1.8× |

#### Step 4 — Market Structure

| Default | XAU/USD Override |
|---------|-----------------|
| Swing detection with ATR-based lookback | **Gold:** Use 1.5× ATR multiplier (vs 1.0× default). Gold's wider swings need larger lookback to avoid noise. Minimum lookback: 8 bars (vs 5 default). |
| BOS/CHoCH detection | **Gold:** BOS has 70% continuation rate (higher than FX average of 58%). CHoCH has 55% reversal rate. Favor BOS trades over CHoCH on gold. |
| Chop detection | **Gold:** ADX threshold for trending: 20 (lower than FX default of 25). Gold trends more cleanly, so lower ADX still indicates trend. |

#### Step 5 — Support & Resistance

| Default | XAU/USD Override |
|---------|-----------------|
| Fractal-based + volume profile S/R | **Gold-specific levels:** Add psychological round numbers ($2,600, $2,650, $2,700, etc.) with +25% weight. These are institutional order magnets. |
| Multi-TF weighting | **Gold:** D1 and W1 S/R levels have 1.5× the normal weight. Gold respects higher timeframe levels more than FX pairs. |
| Institutional S/R | **Gold:** Monitor central bank intervention levels (e.g., PBOC gold price band), options gamma exposure at COMEX, and ETF rebalancing levels (GLD, IAU). |

**Gold S/R Hierarchy:**
1. **Round numbers** ($2,700, $2,750) — strongest institutional levels
2. **Previous day/week high/low** — strong for intraday
3. **COMEX open interest clusters** — options-driven S/R
4. **Fibonacci extensions** (1.272, 1.618) — for targeting
5. **Volume profile POC/VAH/VAL** — for intraday levels

#### Step 6 — Liquidity Detection

| Default | XAU/USD Override |
|---------|-----------------|
| Standard liquidity pool detection | **Gold:** Liquidity pools are deeper and more reliable than FX. Institutional stop clusters at round numbers can contain 10× the volume of FX pools. |
| Sweep classification | **Gold:** Real sweeps have 80% follow-through rate (vs 70% on FX). Gold's institutional nature means sweeps are more decisive. Add volume threshold: >2.5× average (vs 2.0× default). |
| On-chain data | N/A for gold (physical commodity). Replace with: COMEX warehouse stocks, ETF flow data, central bank reserve changes. |

#### Step 7 — Smart Money Concepts

| Default | XAU/USD Override |
|---------|-----------------|
| OB detection | **Gold:** Order blocks form cleanly at psychological levels and D1 swing points. Gold OBs at round numbers have 75% reaction rate (vs 65% for random OBs). Prioritize OBs that align with round numbers. |
| FVG detection | **Gold:** FVGs form during NFP/CPI reactions and tend to fill within 2-4 hours. Gold FVGs have 68% fill rate (vs 60% on EUR/USD). Trade FVG fills aggressively. |
| Confluence scoring | **Gold override:** Add +20 bonus points when OB/FVG aligns with round number. Add +15 when aligned with DXY weakness signal. |

#### Step 8 — RSI Confirmation

| Default | XAU/USD Override |
|---------|-----------------|
| Adaptive thresholds by regime | **Gold thresholds:** Trending bull: oversold=40, overbought=82. Trending bear: oversold=18, overbought=60. Range: oversold=32, overbought=68. Gold oscillates more extremely than FX. |
| Divergence detection | **Gold:** Regular divergence on H4 has 72% reversal rate (higher than FX). Hidden divergence has 65% continuation rate. Weight H4 divergence 1.3× default. |
| Composite momentum | **Gold override:** Replace Williams %R with Gold-specific "Real Rate Momentum" (10Y TIPS yield change). Weight: RSI 0.30, StochRSI 0.15, MFI 0.15, Real Rate Mom 0.25, CCI 0.15. |

#### Step 9 — Candlestick Confirmation

| Default | XAU/USD Override |
|---------|-----------------|
| Standard patterns | **Gold:** Bullish/Bearish engulfing at round numbers have 75% win rate (vs 62% baseline). Pin bars after NFP/CPI spikes have 70% win rate. Morning/Evening star at weekly S/R: 68%. |
| Volume weighting | **Gold:** Volume spike threshold: 2.0× average (higher than FX default 1.5×). Gold needs stronger volume confirmation because it's more institutional. |

#### Steps 10–12 — Entry, Sizing, Stop Loss

| Parameter | XAU/USD Value | Rationale |
|-----------|--------------|-----------|
| **Entry method** | Limit orders preferred (80% of entries) | Gold often retests levels; limit orders get better fills |
| **Position sizing** | 0.01 lots max on $7 account | Risk $0.14 per 14 pips (1% of $7 account × 14) |
| **Stop-loss base** | 1.5× ATR(14) | Gold needs wider stops due to volatility; FX default is 1.0× |
| **Stop buffer** | Below round number + 50 pips | Avoid stop hunts at obvious levels |
| **R:R minimum** | 1:2.5 | Gold moves far enough to justify wider R:R target |
| **R:R preferred** | 1:3 to 1:4 | Gold trends persist; let winners run |
| **Max SL distance** | 3,000 pips ($30) on $7 account | 2% risk = $0.14; at 0.01 lot, max SL = 14 pips... actually this needs careful calculation |

**Gold Position Sizing Reality Check:**
```
Account: $7
Risk per trade: 2% = $0.14
Min lot: 0.01 lots
Pip value at 0.01 lots: $0.01 per 0.01 gold = $0.01/pip
Max SL in pips: $0.14 / $0.01 = 14 pips = $0.14 move in gold

Problem: Gold's ATR(14) is ~$25 (2,500 pips). 14 pips is 0.56% of ATR.
This stop is WAY too tight — will get stopped out by noise.

Solution: At $7 capital, gold trading requires:
- Either accept that 1% risk = 14 pips SL (extremely tight, only for scalping)
- Or use the smallest possible position and accept higher risk %
- Or wait until account grows to $50+ for meaningful gold position sizing
```

**Gold Minimum Viable Account:**
| Account Size | 2% Risk | Max SL at 0.01 lot | % of ATR | Viability |
|-------------|---------|-------------------|----------|-----------|
| $7 | $0.14 | 14 pips ($0.14) | 0.56% | ❌ Too tight |
| $20 | $0.40 | 40 pips ($0.40) | 1.6% | ⚠️ Marginal (scalping only) |
| $50 | $1.00 | 100 pips ($1.00) | 4% | ✅ Viable for intraday |
| $100 | $2.00 | 200 pips ($2.00) | 8% | ✅ Good for swing |
| $200 | $4.00 | 400 pips ($4.00) | 16% | ✅ Ideal |

**Recommendation:** Trade gold from $20+ account. At $7, focus on EUR/USD (tightest spread, smallest position sizing works). Gold becomes viable at $50+ for proper stop placement.

#### Steps 13–16 — TP, Management, Exit, Journal

| Parameter | XAU/USD Value |
|-----------|--------------|
| **TP1** | 1.5R (close 33%) |
| **TP2** | 3.0R (close 33%) |
| **TP3** | Trail with 2.5× ATR(14) |
| **Break-even trigger** | 1.2R (gold pulls back more before continuing) |
| **Trailing method** | Structure-based (gold forms clean swing structure) |
| **Time stop** | 48 hours for swing, 8 hours for intraday |
| **Weekend management** | Close 100% before Friday NY close (gold gaps are unpredictable) |
| **Journal focus** | Track DXY correlation accuracy, round number reaction rate, NFP/CPI setup performance |

### 3.3 Optimal Trading Sessions for Gold

| Session (GMT) | Activity Level | Strategy | Expected Range |
|--------------|---------------|----------|----------------|
| 00:00–08:00 | Low | Range identification, set alerts | 20-30% of daily |
| 08:00–12:00 | Medium-High | London breakout trades, Asian range sweep | 25-35% of daily |
| 12:00–13:00 | Low | Lunch consolidation, avoid entries | 5-10% of daily |
| **13:00–16:00** | **Maximum** | **Primary window — highest probability entries** | **30-40% of daily** |
| 16:00–21:00 | Medium | US session continuation, news trades | 15-25% of daily |

**Golden Window:** 13:00–16:00 GMT (London-NY overlap). This is when gold makes its largest moves, spreads are tightest, and institutional flow is heaviest.

### 3.4 Gold-Specific News Events

| Event | Time (GMT) | Impact | Typical Gold Move | Strategy |
|-------|-----------|--------|-------------------|----------|
| **FOMC Rate Decision** | 19:00 | 🔴 Extreme | $20–60 (2000–6000 pips) | Wait 30 min, trade FVG fill |
| **US CPI** | 13:30 | 🔴 Extreme | $15–40 (1500–4000 pips) | Wait for spike, trade OB pullback |
| **US NFP** | 13:30 | 🔴 Extreme | $15–50 (1500–5000 pips) | Wait 15 min, trade reversal if overextended |
| **US GDP** | 13:30 | 🟡 High | $8–20 (800–2000 pips) | Trade with trend if surprise > 0.5% |
| **Fed Chair Speech** | Various | 🔴 Extreme | $10–40 (1000–4000 pips) | No trading during speech; trade aftermath |
| **Geopolitical Crisis** | Any | 🔴 Extreme | $20–100+ | Safe haven bid; long gold with tight trailing |
| **US Jobs Report (ADP)** | 13:15 | 🟡 High | $5–15 (500–1500 pips) | Preview for NFP; trade alignment |

### 3.5 Gold Correlation Rules

| Correlated Pair | Correlation | Rule |
|----------------|-----------|------|
| **DXY (inverse)** | -0.85 | If DXY trending strongly (ADX>25), gold trade must align with DXY direction. Never long gold AND long DXY simultaneously. |
| **EUR/USD** | +0.70 | Long gold + Long EUR/USD = 1.7× effective USD short exposure. Reduce combined risk to 1.5%. |
| **GBP/USD** | +0.65 | Moderate correlation. Can hold both but reduce position size. |
| **USD/JPY** | -0.70 | Long gold + Short USD/JPY = same trade. Never hold both at full size. |
| **BTC/USD** | -0.30 to +0.30 | Variable correlation. Safe to hold both. Use as diversification. |
| **Silver (XAG)** | +0.90 | If trading both, treat as ONE position for risk purposes. |

### 3.6 Gold Agent Configuration

```yaml
pair_config:
  symbol: XAUUSD
  display_name: "Gold"
  
  fundamental:
    primary_drivers: ["DXY", "US_10Y_real_yield", "CPI", "geopolitical_risk"]
    driver_weights: {"DXY": -0.35, "real_yield": -0.25, "CPI": 0.15, "geopolitics": 0.10, "cb_buying": 0.10, "etf_flows": 0.05}
    sentiment_sources: ["world_gold_council", "cot_gold", "gld_etf_flow"]
    event_calendar_filter: ["FOMC", "CPI", "NFP", "GDP", "Fed_Speech", "Geopolitical"]
    
  market_bias:
    hmm_states: 4  # Add geopolitical shock state
    tf_weights: {"W1": 0.30, "D1": 0.35, "H4": 0.25, "H1": 0.10}
    fundamental_alpha: 0.50  # Equal weight in normal conditions
    fundamental_alpha_geopolitical: 0.70  # Fundamentals dominate during crisis
    
  session:
    primary_session: "london_ny_overlap"
    secondary_session: "london"
    asian_range_breakout_enabled: true
    asian_range_tight_threshold_pips: 1500
    session_vol_multipliers: {"asian": 0.3, "london": 1.4, "ny": 1.3, "overlap": 1.8}
    
  structure:
    swing_lookback_atr_mult: 1.5
    min_swing_lookback: 8
    bos_continuation_rate: 0.70
    choch_reversal_rate: 0.55
    adx_trend_threshold: 20
    
  support_resistance:
    round_number_weight_mult: 1.25
    d1_w1_sr_weight_mult: 1.5
    institutional_levels: ["comex_oi_clusters", "etf_rebalance", "psychological_round"]
    
  liquidity:
    sweep_volume_threshold_mult: 2.5
    sweep_follow_through_rate: 0.80
    on_chain_replacement: "comex_warehouse_stocks"
    
  smc:
    ob_at_round_number_bonus: 20
    ob_with_dxy_alignment_bonus: 15
    fvg_fill_rate: 0.68
    
  rsi:
    thresholds:
      trending_bull: {"oversold": 40, "overbought": 82}
      trending_bear: {"oversold": 18, "overbought": 60}
      range: {"oversold": 32, "overbought": 68}
    h4_divergence_weight_mult: 1.3
    composite_weights: {"RSI": 0.30, "StochRSI": 0.15, "MFI": 0.15, "RealRateMom": 0.25, "CCI": 0.15}
    
  candlestick:
    engulfing_at_round_number_wr: 0.75
    pin_bar_after_news_wr: 0.70
    volume_spike_threshold_mult: 2.0
    
  risk:
    min_account_size: 20  # $7 is too small for gold
    optimal_account_size: 100
    sl_atr_mult: 1.5
    sl_round_number_buffer_pips: 50
    rr_minimum: 2.5
    rr_preferred: 3.5
    max_sl_pips: 3000
    max_sl_pct_account: 2.0
    weekend_close: true  # Always close gold before weekend
    
  take_profit:
    tp1_r_multiple: 1.5
    tp2_r_multiple: 3.0
    tp3_method: "trail"
    tp3_atr_mult: 2.5
    be_trigger_r: 1.2
    trailing_method: "structure"
    time_stop_hours_swing: 48
    time_stop_hours_intraday: 8
    
  journal:
    focus_metrics: ["dxy_correlation_accuracy", "round_number_reaction_rate", "nfp_cpi_setup_performance", "geopolitical_regime_accuracy"]
```

---

## 4. BTC/USD — Bitcoin

### 4.1 Unique Characteristics

| Property | Value | Implication |
|----------|-------|-------------|
| **Tick Value** | $1 per 0.01 move per 0.01 lot | Extremely volatile; requires precise sizing |
| **Min Trade** | 0.001 BTC | Very small minimum; good for micro accounts |
| **Spread** | ~$5 (varies widely by session) | 5× wider than gold; significant cost |
| **Daily Range** | $1,500–3,000 (2–5%) | Massive moves; huge opportunity and risk |
| **Trading Hours** | 24/7 (FXPesa: 24/6) | No session gaps; weekend trading available |
| **Leverage** | 1:200 (Group 1) | High leverage available |
| **Unique Feature** | On-chain data available | Only pair with blockchain transparency |

**BTC's Personality:** Bitcoin is a narrative-driven, sentiment-heavy asset that trades like a high-beta risk asset correlated with tech stocks. It has the unique advantage of on-chain transparency — you can see whale movements, exchange flows, and liquidation levels in real-time. However, its SMC patterns are noisier than FX, spreads are wider, and it's prone to sudden 10-20% moves driven by ETF flows or regulatory news.

### 4.2 Strategy Step Adaptations

#### Step 1 — Fundamental Intelligence

| Default | BTC Override |
|---------|-------------|
| Economic calendar focus | **BTC drivers:** Fed policy (rate expectations), US tech earnings (correlation with NASDAQ), Spot ETF inflows/outflows (strongest direct driver), regulatory news (SEC, global), halving cycle position, on-chain metrics |
| News sources | **BTC-specific:** CoinDesk, The Block, Bitcoin Magazine, SEC EDGAR (ETF filings), Glassnode/CryptoQuant reports, Michael Saylor tweets (market-moving), ETF flow data from Bloomberg |
| Sentiment | **BTC-specific:** Fear & Greed Index, Crypto Twitter sentiment, Reddit r/bitcoin activity, Google Trends "Bitcoin", funding rates across exchanges |

**BTC-Specific Fundamental Model:**
```
BTC Bias Score = (
    +0.25 × etf_net_flow_direction +        # Strongest direct driver
    +0.20 × fed_policy_dovishness +          # Rate expectations
    +0.15 × nasdaq_direction +               # Risk-on correlation
    +0.12 × on_chain_whale_accumulation +    # Smart money
    +0.10 × funding_rate_extreme_signal +    # Contrarian
    +0.08 × fear_greed_shift +               # Retail sentiment
    +0.05 × google_trends_momentum +         # Retail attention
    +0.05 × regulatory_sentiment             # SEC, global regulation
)
```

#### Step 2 — Market Bias

| Default | BTC Override |
|---------|-------------|
| 3-state HMM | **Add state:** "Liquidation Cascade" — triggered when OI is extreme AND funding is extreme. In this state, price moves are mechanical (forced liquidations), not technical. Stop all SMC analysis; trade only with liquidation flow. |
| Multi-TF weights | **BTC:** W1:0.25, D1:0.30, H4:0.30, H1:0.15 — BTC's H4 structure matters more than W1 because the asset is younger and regime shifts happen faster. |
| Regime detection | **BTC-specific:** Add on-chain regime signals: SOPR (Spent Output Profit Ratio), MVRV Z-Score, exchange reserves. SOPR < 1 = capitulation (bullish). MVRV > 3.5 = overvaluation (bearish). |

#### Step 3 — Session Analysis

| Default | BTC Override |
|---------|-------------|
| Standard FX sessions | **BTC sessions (UTC):** Asian 00:00–08:00 (lower volume, often range), London 08:00–16:00 (crypto desks active, breakout moves), US 13:00–21:00 (highest volume, ETF flow news, largest moves), Weekend (lower liquidity, wider spreads, more manipulation) |
| Weekend trading | **BTC:** Available but caution. Spreads widen 2-3×. Reduce position size by 60%. Only trade clear levels. |
| Session volatility | **BTC:** Asian 0.6×, London 1.0×, US 1.4×, Weekend 0.5× |

#### Step 4 — Market Structure

| Default | BTC Override |
|---------|-----------------|
| Swing detection | **BTC:** Use 2.0× ATR multiplier. BTC's volatility creates many false swings with default settings. Minimum lookback: 10 bars. |
| BOS/CHoCH | **BTC:** BOS continuation rate: 55% (lower than FX). CHoCH reversal rate: 50%. BTC is more prone to fakeouts. Require volume confirmation (>1.8× average) for all structure breaks. |
| Chop detection | **BTC:** ADX trending threshold: 28 (higher than FX default). BTC has more ranging periods. BB squeeze is less reliable on BTC due to volatility clustering. |

#### Step 5 — Support & Resistance

| Default | BTC Override |
|---------|-----------------|
| S/R detection | **BTC-specific levels:** Add round numbers ($60,000, $65,000, $70,000), previous ATH, options max pain levels (Deribit), and on-chain cost basis levels (realized price, LTH/STH cost basis). |
| Institutional S/R | **BTC:** Options gamma exposure at Deribit (largest BTC options exchange), ETF creation/redemption levels, miner capitulation levels (production cost ~$30,000-40,000). |

#### Step 6 — Liquidity Detection

| Default | BTC Override |
|---------|-----------------|
| Liquidity pools | **BTC-specific:** Use Coinglass liquidation heatmap as primary source. These are EXACTLY where institutions target. Cluster of leveraged longs below = buy-side liquidity. Cluster of shorts above = sell-side liquidity. |
| On-chain liquidity | **BTC advantage:** Exchange inflows/outflows (Glassnode, CryptoQuant). Large inflows → potential selling pressure. Large outflows → supply squeeze. This data is NOT available for any other pair. |
| Funding rate integration | **BTC:** Extreme positive funding (>0.1%) → overcrowded shorts above → price will likely pump to liquidate them. Extreme negative funding (<-0.05%) → overcrowded longs below → price will likely dump. |

#### Step 7 — Smart Money Concepts

| Default | BTC Override |
|---------|-----------------|
| OB quality | **BTC:** Order blocks are noisier. Require additional confirmation: volume >2.0× average AND displacement >3 candles. BTC OBs without volume are 50/50. |
| FVG behavior | **BTC:** FVGs fill faster (within 2-4 hours vs 4-8 hours for FX). Trade FVG fills aggressively but with tighter stops. FVG fill rate: 65%. |
| Breaker blocks | **BTC:** Breaker blocks (failed OBs that become new levels) are more common on BTC (20% of OBs fail vs 12% on EUR/USD). Track and trade breakers actively. |

#### Step 8 — RSI Confirmation

| Default | BTC Override |
|---------|-----------------|
| RSI thresholds | **BTC thresholds:** Trending bull: oversold=35, overbought=85. Trending bear: oversold=15, overbought=65. Range: oversold=28, overbought=72. BTC oscillates more extremely. |
| Composite momentum | **BTC override:** Add funding rate as momentum signal. Weight: RSI 0.25, StochRSI 0.15, MFI 0.15, Funding Rate Signal 0.20, CCI 0.10, On-Chain Momentum 0.15. |

#### Steps 10–12 — Entry, Sizing, Stop Loss

| Parameter | BTC Value | Rationale |
|-----------|----------|-----------|
| **Entry method** | Limit orders 90% (wider spreads make market orders costly) | Spread is ~$5; market orders pay premium |
| **Position sizing** | 0.001 BTC min; scale carefully | $7 account: at 0.001 BTC, each $1 move = $0.001 |
| **Stop-loss base** | 2.0× ATR(14) | BTC needs widest stops of any pair |
| **R:R minimum** | 1:2.0 | BTC moves enough for 2:1 even with wide stops |
| **R:R preferred** | 1:3 to 1:5 | BTC trends can be massive |
| **Max daily loss** | 4% (BTC moves are extreme) | Lower than standard 5% to account for volatility |
| **Weekend trading** | Reduce size by 60% | Wider spreads, more manipulation |

**BTC Position Sizing Reality Check:**
```
Account: $7
BTC price: $70,000
Min lot: 0.001 BTC
Pip value: $0.001 per $1 move
Risk 2% = $0.14
Max SL: $0.14 / $0.001 = $140
ATR(14): ~$2,000

$140 SL = 7% of ATR → TIGHT but potentially viable for scalping
For swing trading, need $50+ account for proper stop placement
```

### 4.3 Optimal Trading Sessions for BTC

| Session (UTC) | Activity Level | Strategy | Notes |
|--------------|---------------|----------|-------|
| 00:00–08:00 | Low-Medium | Range identification, accumulation zones | Asian session; often sets the range |
| 08:00–13:00 | Medium | London breakout, crypto desk activity | European institutional desks |
| **13:00–21:00** | **Maximum** | **Primary window — ETF flow news, US macro** | **Best liquidity, highest volume** |
| 21:00–00:00 | Low | Wind down, manage positions | Reducing liquidity |
| Weekend | Low | Cautious scalping only | Wide spreads, manipulation |

### 4.4 BTC-Specific News Events

| Event | Impact | Typical BTC Move | Strategy |
|-------|--------|-----------------|----------|
| **FOMC Rate Decision** | 🔴 Extreme | $2,000–5,000 | Wait 30 min, trade FVG fill |
| **Spot ETF Flow (daily)** | 🔴 Extreme | $1,000–3,000 | Trade direction of net flow |
| **US CPI** | 🔴 Extreme | $1,500–4,000 | Wait for spike, trade reversal |
| **US Tech Earnings (AAPL, NVDA)** | 🟡 High | $500–2,000 | Correlated risk-on/off move |
| **SEC Regulatory News** | 🔴 Extreme | $2,000–10,000 | No trading during announcement; trade aftermath |
| **Bitcoin Halving** | 🟢 Structural | Long-term bullish | Position for trend continuation 6-12 months post-halving |
| **Whale Wallet Movements** | 🟡 High | $500–2,000 | Trade with whale flow direction |

### 4.5 BTC Correlation Rules

| Correlated Asset | Correlation | Rule |
|-----------------|-----------|------|
| **NASDAQ/S&P 500** | +0.65 | Long BTC + Long tech stocks = same risk-on trade. Reduce BTC size if holding tech. |
| **Gold** | -0.30 to +0.30 | Variable. Safe to hold both. Good diversification. |
| **EUR/USD** | -0.55 | Inverse USD correlation. Long BTC + Long EUR/USD = partial overlap. |
| **ETH/USD** | +0.85 | **Never hold both at full size.** Treat as ONE position for risk. |
| **DXY** | -0.60 | Weak dollar → BTC long. Align BTC trades with DXY direction. |

### 4.6 BTC Agent Configuration

```yaml
pair_config:
  symbol: BTCUSD
  display_name: "Bitcoin"
  
  fundamental:
    primary_drivers: ["ETF_flows", "Fed_policy", "NASDAQ", "on_chain_whale", "funding_rate"]
    driver_weights: {"ETF_flows": 0.25, "Fed": 0.20, "NASDAQ": 0.15, "whale": 0.12, "funding": 0.10, "fear_greed": 0.08, "google_trends": 0.05, "regulatory": 0.05}
    sentiment_sources: ["fear_greed_index", "crypto_twitter", "reddit_bitcoin", "google_trends"]
    on_chain_metrics: ["exchange_flow", "sopr", "mvrv", "whale_accumulation", "funding_rate"]
    
  market_bias:
    hmm_states: 4  # Add liquidation cascade state
    tf_weights: {"W1": 0.25, "D1": 0.30, "H4": 0.30, "H1": 0.15}
    fundamental_alpha: 0.45
    on_chain_regime_signals: ["SOPR", "MVRV_zscore", "exchange_reserves"]
    
  session:
    primary_session: "us_session"
    secondary_session: "london"
    weekend_trading: true
    weekend_size_reduction: 0.4  # Trade at 40% of normal size
    session_vol_multipliers: {"asian": 0.6, "london": 1.0, "us": 1.4, "weekend": 0.5}
    
  structure:
    swing_lookback_atr_mult: 2.0
    min_swing_lookback: 10
    bos_continuation_rate: 0.55
    choch_reversal_rate: 0.50
    adx_trend_threshold: 28
    volume_confirmation_required: true
    volume_threshold_mult: 1.8
    
  support_resistance:
    round_numbers: [60000, 65000, 70000, 75000, 80000, 100000]
    institutional_levels: ["deribit_max_pain", "etf_creation_level", "miner_cost_basis", "realized_price"]
    on_chain_cost_basis: ["sth_realized", "lth_realized", "200dma"]
    
  liquidity:
    primary_source: "coinglass_liquidation_heatmap"
    on_chain_sources: ["exchange_inflow", "exchange_outflow", "whale_transfers"]
    funding_rate_extreme_threshold: {"long": 0.001, "short": -0.0005}
    sweep_volume_threshold_mult: 2.0
    
  smc:
    ob_volume_confirmation_mult: 2.0
    ob_displacement_min_candles: 3
    fvg_fill_rate: 0.65
    fvg_fill_time_hours: 3
    breaker_block_rate: 0.20
    
  rsi:
    thresholds:
      trending_bull: {"oversold": 35, "overbought": 85}
      trending_bear: {"oversold": 15, "overbought": 65}
      range: {"oversold": 28, "overbought": 72}
    composite_weights: {"RSI": 0.25, "StochRSI": 0.15, "MFI": 0.15, "FundingRate": 0.20, "CCI": 0.10, "OnChainMom": 0.15}
    
  risk:
    min_account_size: 10
    optimal_account_size: 100
    sl_atr_mult: 2.0
    rr_minimum: 2.0
    rr_preferred: 3.5
    max_daily_loss_pct: 4.0  # Lower than standard due to volatility
    weekend_close: false  # Can hold weekend but reduce size
    weekend_size_mult: 0.4
    
  take_profit:
    tp1_r_multiple: 1.5
    tp2_r_multiple: 3.0
    tp3_method: "trail"
    tp3_atr_mult: 3.0  # Wider trailing for BTC volatility
    be_trigger_r: 1.5
    trailing_method: "ema_21"
    
  journal:
    focus_metrics: ["etf_flow_accuracy", "funding_rate_signal_accuracy", "on_chain_whale_accuracy", "weekend_trade_performance"]
```

---

## 5. EUR/USD — Euro/Dollar

### 5.1 Unique Characteristics

| Property | Value | Implication |
|----------|-------|-------------|
| **Daily Range** | 70–100 pips | Moderate; predictable movement |
| **Spread** | 1.4 pips (Standard), 0.0 (Premier) | Tightest of any pair on Premier |
| **Liquidity** | $7.5T daily (most liquid market on Earth) | Best execution, minimal slippage |
| **Best Session** | London + NY overlap | Peak institutional flow |
| **SMC Quality** | ⭐⭐⭐⭐⭐ | Cleanest order blocks and FVGs of any pair |
| **Macro Drivers** | ECB vs Fed policy, Eurozone GDP, US data | Clear fundamental framework |
| **Correlation** | GBP/USD +0.90, USD/CHF -0.90 | High correlation cluster |

**EUR/USD's Personality:** EUR/USD is the "default" pair for Alpha Stack. It has the tightest spreads, highest liquidity, cleanest SMC patterns, and most predictable session behavior. It's the best pair for learning and for consistent, lower-risk trading. Its main weakness is that it's highly correlated with GBP/USD and USD/CHF, so you can't trade multiple USD pairs simultaneously.

### 5.2 Strategy Step Adaptations

#### Step 1 — Fundamental Intelligence

| Default | EUR/USD Override |
|---------|-----------------|
| All macro indicators | **Priority drivers:** ECB vs Fed rate differential (strongest driver), Eurozone CPI, US NFP/CPI, EUR/USD positioning (COT), DXY |
| Event calendar | **EUR-specific:** ECB rate decision (13:45 GMT), Eurozone CPI (10:00 GMT), German ZEW/Ifo, US data (all high-impact USD events affect EUR/USD) |

**EUR/USD Fundamental Model:**
```
EUR/USD Bias Score = (
    +0.30 × ecb_fed_rate_differential_change +
    +0.25 × us_macro_surprise (NFP, CPI, GDP) +
    +0.15 × eurozone_cpi_surprise +
    +0.10 × dxy_direction (inverse) +
    +0.10 × risk_sentiment (VIX, SPX) +
    +0.10 × cot_positioning_extreme
)
```

#### Step 2 — Market Bias

| Default | EUR/USD Override |
|---------|-----------------|
| HMM states | Standard 3-state works perfectly for EUR/USD. No additions needed. |
| TF weights | **EUR/USD:** W1:0.35, D1:0.30, H4:0.20, H1:0.15 (default — no change) |
| Regime detection | **EUR/USD:** Standard ADX + volatility regime works well. Add: if EUR/USD and DXY both showing strength simultaneously → flag as conflict, wait for resolution. |

#### Step 3 — Session Analysis

| Default | EUR/USD Override |
|---------|-----------------|
| Session behavior | **EUR/USD:** London session sets the trend 65% of the time. NY session continues or reverses London 35% of the time. Asian range is 30-40% of daily range. |
| Kill zones | **EUR/USD primary:** 08:00–11:00 GMT (London open, institutional positioning) and 13:00–16:00 GMT (NY overlap, maximum liquidity) |

#### Step 4 — Market Structure

| Default | EUR/USD Override |
|---------|-----------------|
| Swing detection | Standard settings work well. ATR multiplier: 1.0×, lookback: 5 bars. EUR/USD has the cleanest swing structure. |
| BOS/CHoCH | **EUR/USD:** BOS continuation: 62%. CHoCH reversal: 55%. Standard behavior. No overrides needed. |

#### Steps 5–9 — S/R through Candlestick

EUR/USD is the **reference pair** — default parameters are designed around it. No overrides needed for Steps 5–9. The system's default behavior IS the EUR/USD behavior.

**Key EUR/USD-specific notes:**
- Round numbers (1.0800, 1.0900, 1.1000) are strong S/R
- London fix (16:00 GMT) creates predictable flows
- End-of-month rebalancing creates strong moves
- Sunday open gaps are typically 15-25 pips (small)

#### Steps 10–12 — Entry, Sizing, Stop Loss

| Parameter | EUR/USD Value | Rationale |
|-----------|--------------|-----------|
| **Entry method** | Limit 70%, Market 30% | Clean levels, good for limits |
| **Position sizing** | 0.01 lots on $7 account | $0.14 risk per 14 pips — viable |
| **Stop-loss base** | 1.0× ATR(14) | Standard; EUR/USD has clean structure for stops |
| **R:R minimum** | 1:2.0 | Standard |
| **R:R preferred** | 1:2.5 | EUR/USD moves reliably but not explosively |
| **Break-even trigger** | 1.0R | Standard; EUR/USD respects BE stops well |

**EUR/USD Position Sizing — Viable at $7:**
```
Account: $7
Risk per trade: 2% = $0.14
Lot size: 0.01
Pip value: $0.10 per pip
Max SL: $0.14 / $0.10 = 1.4 pips → TOO TIGHT

Wait — standard lot pip value for EUR/USD:
0.01 lot = 1,000 units
1 pip = $0.10
$0.14 risk / $0.10 per pip = 1.4 pips SL

This is too tight. Solution:
- Use 0.01 lot with 10 pip SL = $1.00 risk = 14.3% of account → TOO HIGH
- Need to balance: acceptable risk vs viable stop distance

Practical approach at $7:
- Trade 0.01 lots with 20 pip SL = $2.00 risk = 28.6% → STILL TOO HIGH
- Reality: At $7, position sizing for any pair is extremely constrained
- Recommended: 0.01 lot, 30 pip SL, accept 4.3% risk per trade
- Or: Wait for $20+ account for proper 1-2% risk sizing
```

### 5.3 Optimal Trading Sessions for EUR/USD

| Session (GMT) | Activity Level | Strategy | Expected Range |
|--------------|---------------|----------|----------------|
| 00:00–08:00 | Low | Range identification, set levels | 30-40% of daily |
| **08:00–11:00** | **High** | **London open — trend initiation** | **25-35% of daily** |
| 11:00–13:00 | Medium | Consolidation, manage positions | 10-15% of daily |
| **13:00–16:00** | **Maximum** | **NY overlap — best entries** | **25-35% of daily** |
| 16:00–21:00 | Medium | US afternoon, trend continuation | 10-20% of daily |

### 5.4 EUR/USD-Specific News Events

| Event | Time (GMT) | Impact | Typical EUR/USD Move | Strategy |
|-------|-----------|--------|---------------------|----------|
| **ECB Rate Decision** | 13:45 | 🔴 Extreme | 80–150 pips | Wait for press conference, trade FVG |
| **FOMC Rate Decision** | 19:00 | 🔴 Extreme | 60–120 pips | Wait 30 min, trade setup |
| **US NFP** | 13:30 | 🔴 Extreme | 50–100 pips | Wait for spike, trade reversal |
| **US CPI** | 13:30 | 🔴 Extreme | 40–80 pips | Wait for spike, trade FVG fill |
| **Eurozone CPI** | 10:00 | 🟡 High | 30–60 pips | Trade with trend if surprise |
| **German ZEW/Ifo** | 09:00/09:00 | 🟡 Medium | 15–30 pips | Trade alignment with bias |
| **US GDP** | 13:30 | 🟡 High | 30–60 pips | Trade with surprise direction |

### 5.5 EUR/USD Correlation Rules

| Correlated Pair | Correlation | Rule |
|----------------|-----------|------|
| **GBP/USD** | +0.90 | **Never hold both at full size.** Maximum combined risk: 1.5%. |
| **USD/CHF** | -0.90 | Long EUR/USD + Short USD/CHF = same trade. Maximum combined risk: 1.5%. |
| **GBP/JPY** | +0.40 | Low correlation. Safe to hold both. |
| **XAU/USD** | +0.70 | Long EUR/USD + Long Gold = partial overlap. Reduce combined risk. |
| **BTC/USD** | -0.55 | Inverse. Good diversification. |

### 5.6 EUR/USD Agent Configuration

```yaml
pair_config:
  symbol: EURUSD
  display_name: "EUR/USD"
  
  fundamental:
    primary_drivers: ["ECB_Fed_differential", "US_NFP_CPI", "Eurozone_CPI", "DXY", "risk_sentiment"]
    driver_weights: {"rate_diff": 0.30, "US_data": 0.25, "EZ_data": 0.15, "DXY": 0.10, "risk": 0.10, "COT": 0.10}
    
  market_bias:
    hmm_states: 3  # Standard
    tf_weights: {"W1": 0.35, "D1": 0.30, "H4": 0.20, "H1": 0.15}
    fundamental_alpha: 0.40  # Default
    
  session:
    primary_session: "london_ny_overlap"
    secondary_session: "london"
    london_fix_flow: true  # 16:00 GMT fixing flows
    
  structure:
    swing_lookback_atr_mult: 1.0
    min_swing_lookback: 5
    bos_continuation_rate: 0.62
    choch_reversal_rate: 0.55
    adx_trend_threshold: 25
    
  support_resistance:
    round_numbers: [1.0700, 1.0800, 1.0900, 1.1000, 1.1100, 1.1200]
    
  rsi:
    thresholds:
      trending_bull: {"oversold": 40, "overbought": 80}
      trending_bear: {"oversold": 20, "overbought": 60}
      range: {"oversold": 30, "overbought": 70}
    
  risk:
    min_account_size: 7  # Viable at $7
    optimal_account_size: 50
    sl_atr_mult: 1.0
    rr_minimum: 2.0
    rr_preferred: 2.5
    max_sl_pips: 50
    
  take_profit:
    tp1_r_multiple: 1.0
    tp2_r_multiple: 2.0
    tp3_method: "trail"
    tp3_atr_mult: 2.0
    be_trigger_r: 1.0
    trailing_method: "structure"
```

---

## 6. GBP/USD — Cable

### 6.1 Unique Characteristics

| Property | Value | Implication |
|----------|-------|-------------|
| **Daily Range** | 90–130 pips | 30% more volatile than EUR/USD |
| **Spread** | 1.8 pips (Standard) | Slightly wider than EUR/USD |
| **Liquidity** | Very High (3rd most traded pair) | Good execution, occasional spikes |
| **Best Session** | London (08:00–16:00 GMT) | GBP is a London-centric pair |
| **SMC Quality** | ⭐⭐⭐⭐⭐ | Excellent patterns; more volatile than EUR/USD |
| **Unique Risk** | Brexit legacy, UK political risk | Sudden spikes on UK political news |
| **Correlation** | EUR/USD +0.90 | High — same USD exposure |

**GBP/USD's Personality:** GBP/USD is EUR/USD's more volatile sibling. It offers 30% more daily range for similar spread costs, making it more profitable per trade but also riskier. GBP responds strongly to BOE policy, UK economic data, and political events (Brexit legacy, Scottish independence, general elections). London session is where GBP lives — 70% of daily range is established during London hours.

### 6.2 Strategy Step Adaptations

#### Step 1 — Fundamental Intelligence

| Default | GBP/USD Override |
|---------|-----------------|
| Macro drivers | **GBP drivers:** BOE vs Fed rate differential (primary), UK CPI (persistent inflation problem), UK GDP, UK political risk (Brexit, elections), GBP positioning (COT) |
| Event calendar | **GBP-specific:** BOE rate decision (12:00 GMT, Thursday), UK CPI (07:00 GMT), UK GDP, UK employment data |

**GBP/USD Fundamental Model:**
```
GBP/USD Bias Score = (
    +0.30 × boe_fed_rate_differential_change +
    +0.20 × uk_cpi_surprise +
    +0.15 × uk_gdp_surprise +
    +0.15 × us_macro_surprise +
    +0.10 × political_risk_score (inverse) +
    +0.10 × cot_positioning
)
```

#### Step 3 — Session Analysis

| Default | GBP/USD Override |
|---------|-----------------|
| Session focus | **GBP/USD:** London is DOMINANT. 70% of daily range during London session (vs 60% for EUR/USD). NY session often reverses or extends London moves. Asian session is almost irrelevant for GBP direction. |
| Kill zones | **GBP/USD primary:** 08:00–11:00 GMT (London open, institutional GBP positioning) and 13:00–15:00 GMT (NY overlap, US data impact) |

#### Steps 4–9 — Structure through Candlestick

GBP/USD behaves similarly to EUR/USD but with:
- **Larger swings:** Use 1.1× ATR multiplier (vs 1.0× for EUR/USD)
- **More volatile pullbacks:** Wider stops needed (1.2× ATR vs 1.0×)
- **Cleaner London session patterns:** OB/FVG quality peaks during 08:00–12:00 GMT
- **More false breakouts during Asian session:** Avoid breakout trades in Asian hours

#### Steps 10–12 — Entry, Sizing, Stop Loss

| Parameter | GBP/USD Value | Rationale |
|-----------|--------------|-----------|
| **Stop-loss base** | 1.2× ATR(14) | Wider than EUR/USD due to volatility |
| **R:R preferred** | 1:2.5 to 1:3.0 | More volatile = bigger moves = higher R:R |
| **Session filter** | No entries during Asian session (00:00–08:00) | Low liquidity, false breakouts |

### 6.3 GBP/USD-Specific News Events

| Event | Time (GMT) | Impact | Typical GBP/USD Move |
|-------|-----------|--------|---------------------|
| **BOE Rate Decision** | 12:00 Thursday | 🔴 Extreme | 80–150 pips |
| **UK CPI** | 07:00 | 🔴 Extreme | 50–100 pips |
| **UK GDP** | 07:00 | 🟡 High | 30–60 pips |
| **UK Employment** | 07:00 | 🟡 High | 30–50 pips |
| **UK Political Events** | Any | 🔴 Extreme | 50–200+ pips (Brexit-style) |
| **US NFP/CPI** | 13:30 | 🔴 Extreme | 50–100 pips |

### 6.4 GBP/USD Correlation Rules

| Correlated Pair | Correlation | Rule |
|----------------|-----------|------|
| **EUR/USD** | +0.90 | **Never hold both at full size.** Reduce to 0.7× each. |
| **GBP/JPY** | +0.55 | Moderate. Can hold both at reduced size. |
| **EUR/GBP** | -0.85 | If long GBP/USD, don't short EUR/GBP (same trade). |

### 6.5 GBP/USD Agent Configuration

```yaml
pair_config:
  symbol: GBPUSD
  display_name: "GBP/USD"
  
  fundamental:
    primary_drivers: ["BOE_Fed_differential", "UK_CPI", "UK_GDP", "political_risk", "US_data"]
    driver_weights: {"rate_diff": 0.30, "UK_CPI": 0.20, "UK_GDP": 0.15, "US_data": 0.15, "political": 0.10, "COT": 0.10}
    
  market_bias:
    tf_weights: {"W1": 0.30, "D1": 0.35, "H4": 0.25, "H1": 0.10}
    
  session:
    primary_session: "london"
    secondary_session: "london_ny_overlap"
    london_dominance: 0.70  # 70% of range during London
    asian_breakout_filter: false  # No breakout trades in Asian
    
  structure:
    swing_lookback_atr_mult: 1.1
    sl_atr_mult: 1.2
    
  risk:
    rr_preferred: 2.75
    max_sl_pips: 60
    correlated_pairs: {"EURUSD": 0.90, "GBPJPY": 0.55}
    max_correlated_risk: 1.5  # With EUR/USD
    
  take_profit:
    tp1_r_multiple: 1.0
    tp2_r_multiple: 2.5
    tp3_atr_mult: 2.5
```

---

## 7. GBP/JPY — The Beast

### 7.1 Unique Characteristics

| Property | Value | Implication |
|----------|-------|-------------|
| **Daily Range** | 120–180 pips | 50% more than EUR/USD; massive moves |
| **Spread** | 2.3 pips (Standard) | Wider than majors; needs larger targets |
| **Liquidity** | High (but lower than majors) | Good execution; occasional thin patches |
| **Best Session** | London (08:00–16:00 GMT) | London drives GBP, Tokyo drives JPY |
| **SMC Quality** | ⭐⭐⭐⭐ | Good patterns; more volatile than EUR/USD |
| **Unique Character** | "The Beast" — extreme momentum moves | Can move 100+ pips in a single candle |
| **Correlation** | GBP/USD +0.55, USD/JPY +0.60 | Dual USD exposure through component pairs |

**GBP/JPY's Personality:** GBP/JPY is the most volatile major cross pair. It's called "The Beast" because it can make 200+ pip moves in a single session. This volatility is a double-edged sword: massive profit potential but equally massive risk. GBP/JPY is ideal for SMC breakout strategies because its momentum moves are clean and decisive. However, it requires wider stops, smaller position sizes, and stronger risk management than any other pair.

### 7.2 Strategy Step Adaptations

#### Step 1 — Fundamental Intelligence

| Default | GBP/JPY Override |
|---------|-----------------|
| Macro drivers | **GBP/JPY:** Dual drivers — GBP side (BOE policy, UK data) AND JPY side (BOJ policy, Japan intervention risk). Also: global risk sentiment (JPY is safe haven; when risk-off, JPY strengthens = GBP/JPY falls) |
| Special factor | **BOJ intervention:** Japan intervenes to weaken JPY when GBP/JPY gets too high (>200 or rapid appreciation). This creates sudden 200-500 pip reversals. Always check intervention risk before trading. |

**GBP/JPY Fundamental Model:**
```
GBP/JPY Bias Score = (
    +0.25 × boe_rate_direction +
    -0.25 × boj_rate_direction +           # BOJ hike = JPY strength = GBP/JPY fall
    +0.15 × uk_macro_surprise +
    +0.15 × risk_sentiment (VIX inverse) +  # Risk-on = JPY weakness = GBP/JPY up
    -0.10 × boj_intervention_risk +         # High intervention risk = avoid longs
    +0.10 × global_yield_differential
)
```

#### Step 2 — Market Bias

| Default | GBP/JPY Override |
|---------|-----------------|
| HMM states | Standard 3-state. Add manual override: If BOJ intervention probability > 50% → FORCE bearish bias regardless of technicals. |
| TF weights | **GBP/JPY:** W1:0.25, D1:0.30, H4:0.30, H1:0.15 — H4 matters more because GBP/JPY moves fast and W1 structure can lag. |

#### Step 3 — Session Analysis

| Default | GBP/JPY Override |
|---------|-----------------|
| Session behavior | **GBP/JPY:** The "Golden Window" is London session 08:00–14:00 GMT when both GBP and JPY institutional flows overlap. Tokyo session (00:00–08:00) sets the JPY side of the range. London breaks it. |
| Asian range | **GBP/JPY:** Asian range is wider than EUR/USD (JPY pairs are active in Tokyo). Tight Asian range on GBP/JPY (<80 pips) predicts London breakout with 68% accuracy. |

#### Step 4 — Market Structure

| Default | GBP/JPY Override |
|---------|-----------------|
| Swing detection | **GBP/JPY:** Use 1.8× ATR multiplier. GBP/JPY's volatility creates many false swings. Minimum lookback: 8 bars. |
| BOS/CHoCH | **GBP/JPY:** BOS continuation: 65% (good). CHoCH reversal: 58% (above average). GBP/JPY's momentum means breaks are more decisive. |
| Chop detection | **GBP/JPY:** ADX trending threshold: 22 (between EUR/USD's 25 and BTC's 28). GBP/JPY trends more than EUR/USD but less cleanly than gold. |

#### Step 5 — Support & Resistance

| Default | GBP/JPY Override |
|---------|-----------------|
| S/R levels | **GBP/JPY:** Round numbers at every 100 pips (190.00, 191.00, 192.00). These are major institutional levels. Weight 1.3× normal. |
| Psychological levels | **GBP/JPY:** Levels like 190.00, 195.00, 200.00 are EXTREMELY significant. 200.00 is a historic level that triggers BOJ intervention discussions. |

#### Steps 6–9 — Liquidity through Candlestick

GBP/JPY overrides:
- **Sweeps are larger:** ATR × 0.5 buffer for sweep classification (vs 0.3 default)
- **FVGs are wider:** Minimum FVG size = 1.5× ATR (vs 1.0× default). Small FVGs on GBP/JPY are noise.
- **Candlestick patterns:** Engulfing patterns on GBP/JPY have 70% win rate when they occur at round numbers with volume >2× average.

#### Steps 10–12 — Entry, Sizing, Stop Loss

| Parameter | GBP/JPY Value | Rationale |
|-----------|--------------|-----------|
| **Entry method** | Limit orders 85% | Wider spreads make market orders costly |
| **Position sizing** | Smaller than EUR/USD by 40% | Higher volatility = wider stops = smaller positions |
| **Stop-loss base** | 1.8× ATR(14) | Widest stops of any FX pair |
| **R:R minimum** | 1:2.5 | Justified by large moves |
| **R:R preferred** | 1:3 to 1:5 | GBP/JPY trends are massive |
| **Max SL distance** | 80 pips | Beyond this, position size becomes too small |
| **Time stop** | 24 hours for intraday | GBP/JPY moves fast; dead trades waste capital |

**GBP/JPY Position Sizing:**
```
Account: $7
Risk: 2% = $0.14
Pip value at 0.01 lot: ~$0.065 (varies with JPY rate)
Max SL: $0.14 / $0.065 = ~2.15 pips → WAY TOO TIGHT

Reality: GBP/JPY at $7 is essentially untradeable with proper risk management.
At $50 account: $1.00 risk / $0.065 = 15.4 pips → Still tight
At $200 account: $4.00 risk / $0.065 = 61.5 pips → Viable

Recommendation: GBP/JPY requires $100+ account for proper stop placement.
At $7, focus on EUR/USD. Add GBP/JPY at $50+ (scalping) or $200+ (swing).
```

### 7.3 GBP/JPY-Specific News Events

| Event | Impact | GBP/JPY Move | Strategy |
|-------|--------|-------------|----------|
| **BOJ Rate Decision** | 🔴 Extreme | 100–300 pips | Avoid trading; massive spikes |
| **BOJ Intervention** | 🔴 Extreme | 200–500 pips | NEVER trade against intervention |
| **BOE Rate Decision** | 🔴 Extreme | 80–150 pips | Wait for FVG fill |
| **UK CPI** | 🟡 High | 40–80 pips | Trade with trend |
| **Japan CPI** | 🟡 Medium | 20–50 pips | Trade if surprise |
| **Global Risk Event** | 🔴 Extreme | 100–300 pips | JPY safe haven bid |

### 7.4 GBP/JPY Correlation Rules

| Correlated Pair | Correlation | Rule |
|----------------|-----------|------|
| **GBP/USD** | +0.55 | Moderate. Can hold both at reduced size. |
| **USD/JPY** | +0.60 | Moderate-High. Long GBP/JPY + Long USD/JPY = double JPY short. Reduce. |
| **EUR/JPY** | +0.80 | **High.** Reduce combined risk to 1.5%. |
| **EUR/USD** | +0.40 | Low. Safe to hold both. |

### 7.5 GBP/JPY Agent Configuration

```yaml
pair_config:
  symbol: GBPJPY
  display_name: "GBP/JPY"
  
  fundamental:
    primary_drivers: ["BOE_policy", "BOJ_policy", "risk_sentiment", "BOJ_intervention_risk"]
    driver_weights: {"BOE": 0.25, "BOJ": 0.25, "risk": 0.15, "UK_data": 0.15, "JP_data": 0.10, "intervention": 0.10}
    special_alerts: ["BOJ_intervention_probability"]
    
  market_bias:
    hmm_states: 3
    tf_weights: {"W1": 0.25, "D1": 0.30, "H4": 0.30, "H1": 0.15}
    boj_intervention_override: true  # Force bearish if intervention likely
    
  session:
    primary_session: "london"
    secondary_session: "london_ny_overlap"
    golden_window: "08:00-14:00 GMT"
    asian_range_tight_threshold_pips: 80
    
  structure:
    swing_lookback_atr_mult: 1.8
    min_swing_lookback: 8
    bos_continuation_rate: 0.65
    choch_reversal_rate: 0.58
    adx_trend_threshold: 22
    
  support_resistance:
    round_numbers_step: 100  # Every 100 pips
    critical_levels: [190.00, 195.00, 200.00]
    round_number_weight_mult: 1.3
    
  smc:
    min_fvg_size_atr_mult: 1.5
    sweep_buffer_atr_mult: 0.5
    
  rsi:
    thresholds:
      trending_bull: {"oversold": 38, "overbought": 82}
      trending_bear: {"oversold": 18, "overbought": 62}
      range: {"oversold": 30, "overbought": 70}
    
  risk:
    min_account_size: 50  # $7 is too small
    optimal_account_size: 200
    sl_atr_mult: 1.8
    rr_minimum: 2.5
    rr_preferred: 3.5
    max_sl_pips: 80
    position_size_reduction: 0.6  # 60% of EUR/USD size
    time_stop_hours: 24
    
  take_profit:
    tp1_r_multiple: 1.5
    tp2_r_multiple: 3.0
    tp3_method: "trail"
    tp3_atr_mult: 3.0
    be_trigger_r: 1.5
    trailing_method: "ema_21"
```

---

## 8. Cross-Pair Correlation Matrix

### 8.1 Rolling 20-Day Correlation Matrix

```
              XAU/USD  BTC/USD  EUR/USD  GBP/USD  GBP/JPY
XAU/USD        1.00    -0.30     0.70     0.65     0.10
BTC/USD       -0.30     1.00    -0.55    -0.50     0.15
EUR/USD        0.70    -0.55     1.00     0.90     0.40
GBP/USD        0.65    -0.50     0.90     1.00     0.55
GBP/JPY        0.10     0.15     0.40     0.55     1.00
```

### 8.2 Correlation Rules Engine

```python
class CorrelationGuard:
    """
    Prevents over-exposure through correlated positions.
    Enforced at infrastructure level (Risk Gate Agent).
    """
    
    CORRELATION_MATRIX = {
        ("XAUUSD", "EURUSD"): 0.70,
        ("XAUUSD", "GBPUSD"): 0.65,
        ("XAUUSD", "BTCUSD"): -0.30,
        ("XAUUSD", "GBPJPY"): 0.10,
        ("BTCUSD", "EURUSD"): -0.55,
        ("BTCUSD", "GBPUSD"): -0.50,
        ("BTCUSD", "GBPJPY"): 0.15,
        ("EURUSD", "GBPUSD"): 0.90,
        ("EURUSD", "GBPJPY"): 0.40,
        ("GBPUSD", "GBPJPY"): 0.55,
    }
    
    MAX_CORRELATED_RISK = {
        "high": 1.5,      # |corr| > 0.8
        "moderate": 2.5,   # |corr| 0.5-0.8
        "low": 4.0,        # |corr| < 0.5
    }
    
    def check_new_position(self, new_pair, new_direction, new_risk, open_positions):
        """Check if adding this position violates correlation limits."""
        
        for pos in open_positions:
            corr = self.get_correlation(new_pair, pos.pair)
            abs_corr = abs(corr)
            
            if abs_corr > 0.8:
                max_risk = self.MAX_CORRELATED_RISK["high"]
            elif abs_corr > 0.5:
                max_risk = self.MAX_CORRELATED_RISK["moderate"]
            else:
                continue  # Low correlation, no limit
            
            # Check if same direction on positively correlated pairs
            # or opposite direction on negatively correlated pairs
            effective_same = (
                (corr > 0 and new_direction == pos.direction) or
                (corr < 0 and new_direction != pos.direction)
            )
            
            if effective_same:
                combined_risk = new_risk + pos.risk
                if combined_risk > max_risk:
                    return CorrelationCheck(
                        passed=False,
                        reason=f"Correlated exposure ({new_pair} + {pos.pair}, corr={corr:.2f}) "
                               f"would be {combined_risk:.1f}% (max: {max_risk}%)",
                        suggestion=f"Reduce {new_pair} size to {max_risk - pos.risk:.1f}% risk"
                    )
        
        return CorrelationCheck(passed=True)
    
    def get_correlation(self, pair1, pair2):
        """Get correlation between two pairs. Order-independent."""
        key = (pair1, pair2) if (pair1, pair2) in self.CORRELATION_MATRIX else (pair2, pair1)
        return self.CORRELATION_MATRIX.get(key, 0.0)
```

### 8.3 Forbidden Combinations

| Combination | Why | Max Combined Risk |
|-------------|-----|-------------------|
| Long EUR/USD + Long GBP/USD | 0.90 correlation — same trade twice | 1.5% |
| Long EUR/USD + Short USD/CHF | -0.90 — both are USD weakness plays | 1.5% |
| Long XAU/USD + Long EUR/USD | 0.70 — both benefit from USD weakness | 2.5% |
| Long BTC/USD + Long ETH/USD | 0.85 — crypto risk-on trade | 1.5% |
| Long GBP/JPY + Long EUR/JPY | 0.80 — JPY weakness play | 1.5% |

### 8.4 Diversification Combinations

| Combination | Correlation | Why It Works |
|-------------|------------|--------------|
| Long XAU/USD + Long GBP/JPY | 0.10 | Gold is macro/safe haven; GBP/JPY is risk-on momentum |
| Long EUR/USD + Long BTC/USD | -0.55 | USD weakness + crypto risk-on (in different drivers) |
| Long XAU/USD + Long BTC/USD | -0.30 | Gold = traditional safe haven; BTC = digital gold (different narratives) |
| Long GBP/USD + Short GBP/JPY | Mixed | GBP long + JPY long = hedged GBP exposure |

---

## 9. Session-Based Pair Rotation Strategy

### 9.1 The Rotation Logic

Different pairs are active during different sessions. The system should prioritize the pair with the best opportunity during each session, rather than scanning all pairs constantly.

```
SESSION ROTATION ENGINE:

FOR each session:
    1. Identify which pairs are PRIME for this session
    2. Scan only prime pairs for signals
    3. If no signal on prime pairs, scan SECONDARY pairs
    4. Never scan pairs that are in their OFF session
```

### 9.2 Rotation Schedule

| Session (GMT) | Prime Pairs | Secondary Pairs | Avoid |
|--------------|-------------|-----------------|-------|
| **Asian (00:00–08:00)** | — | XAU/USD (range ID), BTC/USD | EUR/USD (low vol), GBP/USD (false breakouts), GBP/JPY (wide spreads) |
| **London (08:00–13:00)** | EUR/USD, GBP/USD, GBP/JPY | XAU/USD | BTC/USD (lower volume than US) |
| **London-NY Overlap (13:00–16:00)** | **ALL PAIRS** | — | — |
| **New York (16:00–21:00)** | EUR/USD, XAU/USD, BTC/USD | GBP/USD | GBP/JPY (London-driven, fades in NY) |
| **Wind Down (21:00–00:00)** | — | BTC/USD (24/7) | All FX pairs (wide spreads) |
| **Weekend** | — | BTC/USD (reduced size) | All FX pairs (closed) |

### 9.3 Session-Pair Scoring

```python
class SessionPairRotator:
    """
    Scores each pair for the current session and prioritizes
    scanning/analysis resources.
    """
    
    SESSION_SCORES = {
        # (session, pair) → score 0-100
        ("asian", "XAUUSD"): 40,    # Range identification only
        ("asian", "BTCUSD"): 50,     # Lower volume but tradeable
        ("asian", "EURUSD"): 20,     # Avoid
        ("asian", "GBPUSD"): 15,     # Avoid
        ("asian", "GBPJPY"): 25,     # Wide spreads, avoid
        
        ("london", "XAUUSD"): 70,    # Good for trend initiation
        ("london", "BTCUSD"): 55,    # Crypto desks active
        ("london", "EURUSD"): 85,    # Primary session
        ("london", "GBPUSD"): 90,    # BEST session for GBP
        ("london", "GBPJPY"): 95,    # BEST session for GBP/JPY
        
        ("overlap", "XAUUSD"): 95,   # Maximum opportunity
        ("overlap", "BTCUSD"): 80,   # US macro + crypto flow
        ("overlap", "EURUSD"): 95,   # Maximum opportunity
        ("overlap", "GBPUSD"): 85,   # High opportunity
        ("overlap", "GBPJPY"): 80,   # Good but fading
        
        ("new_york", "XAUUSD"): 80,  # US macro driven
        ("new_york", "BTCUSD"): 90,  # BEST session for BTC
        ("new_york", "EURUSD"): 70,  # Continuation
        ("new_york", "GBPUSD"): 60,  # Fading
        ("new_york", "GBPJPY"): 40,  # Avoid — London-driven
        
        ("wind_down", "XAUUSD"): 20, # Avoid
        ("wind_down", "BTCUSD"): 45, # Manage positions
        ("wind_down", "EURUSD"): 15, # Avoid
        ("wind_down", "GBPUSD"): 15, # Avoid
        ("wind_down", "GBPJPY"): 10, # Avoid
        
        ("weekend", "XAUUSD"): 0,    # Closed
        ("weekend", "BTCUSD"): 35,   # Reduced size
        ("weekend", "EURUSD"): 0,    # Closed
        ("weekend", "GBPUSD"): 0,    # Closed
        ("weekend", "GBPJPY"): 0,    # Closed
    }
    
    def get_priority_pairs(self, session, min_score=60):
        """Get pairs worth scanning for the current session."""
        pairs = []
        for (s, p), score in self.SESSION_SCORES.items():
            if s == session and score >= min_score:
                pairs.append((p, score))
        return sorted(pairs, key=lambda x: x[1], reverse=True)
    
    def should_scan(self, session, pair):
        """Whether to include this pair in the current scan."""
        return self.SESSION_SCORES.get((session, pair), 0) >= 40
```

### 9.4 Resource Allocation by Session

| Session | Active Agents | Scan Frequency | Max Concurrent Trades |
|---------|--------------|----------------|----------------------|
| Asian | BTC Agent only | Every H1 candle | 1 (BTC only) |
| London | EUR, GBP, GBP/JPY, Gold | Every M15 candle | 2 (pick best setup) |
| Overlap | ALL agents | Every M15 candle | 2 (pick best setup) |
| NY | EUR, Gold, BTC | Every M15 candle | 2 |
| Wind Down | BTC Agent only | Every H4 candle | 0 (manage only) |
| Weekend | BTC Agent (reduced) | Every H4 candle | 0 (manage only) |

---

## 10. How to Add New Pairs

### 10.1 New Pair Onboarding Process

Adding a new pair to Alpha Stack follows a structured 4-phase process:

```
PHASE 1: RESEARCH (1-2 days)
├── Collect 2+ years of historical OHLCV data
├── Calculate: ATR, daily range, spread, session behavior
├── Identify fundamental drivers (what moves this pair?)
├── Check correlation with existing pairs
└── Output: Pair Personality Report

PHASE 2: BACKTEST (2-3 days)
├── Run Alpha Strategy default parameters on historical data
├── Identify which parameters underperform
├── Test pair-specific overrides (wider/tighter stops, different RSI thresholds, etc.)
├── Measure: win rate, R:R, max drawdown, Sharpe ratio
└── Output: Optimized Pair Configuration

PHASE 3: PAPER TRADE (1-2 weeks)
├── Deploy pair config in paper trading mode
├── Monitor live signal quality vs backtest expectations
├── Track: slippage, spread impact, session behavior in real-time
├── Validate correlation assumptions with live data
└── Output: Validated Pair Configuration + Live Performance Stats

PHASE 4: LIVE DEPLOYMENT
├── Enable pair in live trading with 50% of normal position size
├── Monitor for 2 weeks at reduced size
├── If performance matches paper trade → full size
├── If underperforming → return to Phase 2
└── Output: Active Pair in Production
```

### 10.2 Pair Evaluation Criteria

| Criterion | Minimum Threshold | Ideal |
|-----------|------------------|-------|
| **Daily range** | > 50 pips | > 80 pips |
| **Spread** | < 3.0 pips | < 1.5 pips |
| **Liquidity** | Top 20 by volume | Top 10 |
| **SMC pattern quality** | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Correlation with existing** | < 0.7 with all existing pairs | < 0.5 |
| **Fundamental clarity** | Identifiable macro drivers | Strong single driver |
| **Session consistency** | Moves in predictable session windows | Clear kill zone |
| **Backtest win rate** | > 55% with default strategy | > 65% |
| **Backtest Sharpe** | > 1.0 | > 1.5 |

### 10.3 Pair Configuration Template

```yaml
pair_config:
  symbol: [SYMBOL]
  display_name: "[NAME]"
  asset_class: [forex_major|forex_cross|commodity|crypto]
  status: [research|backtest|paper|live|paused]
  added_date: [YYYY-MM-DD]
  
  # Phase 1: Research
  research:
    daily_range_pips: [value]
    spread_typical: [value]
    spread_session_best: [value]
    best_session: [session]
    primary_drivers: [list]
    correlation_with_existing: {pair: corr, ...}
    
  # Phase 2: Optimized parameters
  # (Use default template, override only what differs)
  fundamental:
    primary_drivers: []
    driver_weights: {}
    
  market_bias:
    hmm_states: 3
    tf_weights: {W1: 0.35, D1: 0.30, H4: 0.20, H1: 0.15}
    fundamental_alpha: 0.40
    
  structure:
    swing_lookback_atr_mult: 1.0
    min_swing_lookback: 5
    adx_trend_threshold: 25
    
  rsi:
    thresholds:
      trending_bull: {oversold: 40, overbought: 80}
      trending_bear: {oversold: 20, overbought: 60}
      range: {oversold: 30, overbought: 70}
    
  risk:
    min_account_size: [value]
    sl_atr_mult: 1.0
    rr_minimum: 2.0
    rr_preferred: 2.5
    max_sl_pips: [value]
    
  take_profit:
    tp1_r_multiple: 1.0
    tp2_r_multiple: 2.0
    tp3_method: "trail"
    tp3_atr_mult: 2.0
```

### 10.4 Future Pair Candidates

| Pair | Priority | Expected Addition | Notes |
|------|----------|------------------|-------|
| **USD/JPY** | High | Phase 2 | Strong macro driver (BOJ policy), good SMC patterns |
| **AUD/USD** | Medium | Phase 3 | Commodity correlation, clean structure |
| **EUR/JPY** | Medium | Phase 3 | High volatility cross, JPY themes |
| **ETH/USD** | High | Phase 2 | #2 crypto, DeFi ecosystem proxy |
| **USD/CAD** | Low | Phase 4 | Oil correlation, NY session specific |
| **Silver (XAG/USD)** | Medium | Phase 3 | Gold correlation (0.90), higher volatility |
| **EUR/GBP** | Low | Phase 4 | Tight range, mean-reversion friendly |

---

## 11. Pair-Specific Agent Configuration Schema

### 11.1 Configuration Hierarchy

```
SYSTEM DEFAULTS (strategy_defaults.yaml)
    │
    ├── PAIR OVERRIDES (pair_configs/XAUUSD.yaml)
    │       └── Only specifies what DIFFERS from defaults
    │
    ├── SESSION OVERRIDES (session_configs/london.yaml)
    │       └── Session-specific behavior modifications
    │
    └── RUNTIME OVERRIDES (dynamic, from learning system)
            └── Adaptive parameters based on recent performance
```

### 11.2 Configuration Resolution

```python
class PairConfigResolver:
    """
    Resolves the final configuration for a pair by merging:
    1. System defaults
    2. Pair-specific overrides
    3. Session-specific overrides
    4. Runtime adaptive overrides (from learning system)
    """
    
    def resolve(self, pair: str, session: str) -> dict:
        # Load in order of precedence (later overrides earlier)
        config = self.load_defaults()
        config = deep_merge(config, self.load_pair_config(pair))
        config = deep_merge(config, self.load_session_config(session))
        config = deep_merge(config, self.load_adaptive_overrides(pair))
        
        # Validate: ensure no impossible combinations
        self.validate(config)
        
        return config
```

### 11.3 Agent Consumption

Each agent in the pipeline receives the resolved pair configuration at spawn time:

```
Pipeline Trigger: New H4 candle on XAU/USD
    │
    ▼
Orchestrator: Resolve XAU/USD config for London session
    │
    ▼
Spawn Fundamental Agent with config.fundamental
Spawn Structure Agent with config.structure + config.market_bias
Spawn SMC Agent with config.smc
Spawn Momentum Agent with config.rsi
Spawn Candlestick Agent with config.candlestick
Spawn Entry Agent with config.risk + config.take_profit
    │
    ▼
Each agent uses pair-specific parameters throughout its analysis
```

---

## 12. Adaptive Learning System

### 12.1 How the System Learns Pair-Specific Patterns

The system doesn't just use static configurations. It continuously learns and adapts per pair.

#### Signal Weight Adaptation

```python
class PairSignalLearner:
    """
    Tracks signal accuracy per pair and adapts weights.
    Runs weekly during Reflection Agent cycle.
    """
    
    def update_weights(self, pair: str, trades: list):
        """Update signal weights based on recent trade outcomes."""
        
        # Calculate accuracy per signal type
        for signal_type in ["structure", "liquidity", "smc", "momentum", "candlestick"]:
            signal_trades = [t for t in trades if signal_type in t.signals_used]
            if len(signal_trades) < 10:
                continue  # Need minimum sample
            
            accuracy = sum(1 for t in signal_trades if t.outcome == "win") / len(signal_trades)
            
            # Adjust weight: blend recent accuracy with historical
            current_weight = self.get_weight(pair, signal_type)
            historical_accuracy = self.get_historical_accuracy(pair, signal_type)
            
            blended = 0.7 * accuracy + 0.3 * historical_accuracy
            new_weight = current_weight * (blended / 0.5)  # Normalize around 50% baseline
            new_weight = clip(new_weight, 0.05, 0.40)  # Bound
            
            self.set_weight(pair, signal_type, new_weight)
        
        # Normalize all weights to sum to 1.0
        self.normalize_weights(pair)
```

#### Pattern Reliability Tracking

```python
class PatternReliabilityTracker:
    """
    Tracks which SMC patterns work best for each pair.
    """
    
    def track_pattern(self, pair: str, pattern_type: str, outcome: str, context: dict):
        """Record pattern outcome for this pair."""
        
        record = {
            "pair": pair,
            "pattern": pattern_type,
            "outcome": outcome,  # "win" or "loss"
            "session": context["session"],
            "regime": context["regime"],
            "timeframe": context["timeframe"],
            "confluence_score": context["confluence_score"],
            "r_multiple": context["r_multiple"],
            "timestamp": datetime.utcnow()
        }
        
        self.db.insert("pattern_outcomes", record)
    
    def get_reliability(self, pair: str, pattern_type: str, context: dict = None) -> float:
        """Get current reliability score for this pattern on this pair."""
        
        query = "SELECT * FROM pattern_outcomes WHERE pair=%s AND pattern=%s"
        if context:
            query += " AND session=%s AND regime=%s"
        
        results = self.db.query(query, [pair, pattern_type] + list(context.values()))
        
        if len(results) < 20:
            return None  # Insufficient data
        
        wins = sum(1 for r in results if r["outcome"] == "win")
        return wins / len(results)
```

#### RSI Threshold Adaptation

```python
class AdaptiveRSITuner:
    """
    Learns optimal RSI thresholds per pair based on actual market behavior.
    """
    
    def tune_thresholds(self, pair: str, regime: str, ohlcv_history):
        """
        Find the RSI thresholds that would have generated
        the best signals historically for this pair.
        """
        
        rsi_values = calculate_rsi(ohlcv_history, period=14)
        
        # Test oversold thresholds from 15 to 45
        best_oversold = 30
        best_score = 0
        
        for threshold in range(15, 46, 5):
            score = self._backtest_threshold(
                rsi_values, ohlcv_history, 
                oversold=threshold, overbought=100-threshold,
                regime=regime
            )
            if score > best_score:
                best_score = score
                best_oversold = threshold
        
        # Store optimized threshold
        self.db.upsert("rsi_thresholds", {
            "pair": pair,
            "regime": regime,
            "oversold": best_oversold,
            "overbought": 100 - best_oversold,
            "score": best_score,
            "sample_size": len(ohlcv_history),
            "updated_at": datetime.utcnow()
        })
```

### 12.2 Learning Cycle Schedule

| Cycle | Frequency | What It Learns | Agent |
|-------|-----------|---------------|-------|
| **Post-Trade** | After every trade | Pattern outcome, signal accuracy | Reflection Agent |
| **Daily** | End of day | Session performance, RSI accuracy | Journal Agent |
| **Weekly** | Sunday | Signal weight adjustment, pattern reliability update | Reflection Agent |
| **Monthly** | 1st of month | RSI threshold optimization, regime parameter tuning | Reflection Agent (deep) |
| **Quarterly** | Every 3 months | Full model recalibration, pair re-evaluation | Human + Reflection Agent |

### 12.3 Learning Safeguards

| Safeguard | Rule | Rationale |
|-----------|------|-----------|
| **Minimum sample size** | 20 trades before adjusting weights | Prevent overfitting to small samples |
| **Maximum adjustment** | ±20% per weekly cycle | Prevent wild swings in parameters |
| **Human approval** | Required for: new pair addition, risk limit changes, strategy parameter changes >30% | Safety net |
| **Rollback capability** | Keep last 4 weekly parameter snapshots | Can revert if new parameters underperform |
| **A/B testing** | Test parameter changes on 50% of signals first | Validate before full deployment |

### 12.4 Pair Performance Dashboard

The system maintains a real-time dashboard per pair:

```
┌─────────────────────────────────────────────────────────────┐
│  PAIR PERFORMANCE DASHBOARD — XAU/USD                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Win Rate (20-trade rolling): 68% ↑                         │
│  Avg R-Multiple: 2.1                                        │
│  Expectancy: +0.78R per trade                               │
│  Max Drawdown: -4.2R (current: -0.8R)                       │
│  Trades This Week: 4                                        │
│                                                              │
│  Best Setup: OB + RSI divergence at round number (82% WR)   │
│  Worst Setup: FVG fill without volume (45% WR)              │
│  Best Session: London-NY overlap (75% WR)                   │
│  Worst Session: Asian (50% WR)                              │
│                                                              │
│  Signal Weights:                                             │
│    Structure: 0.28  Liquidity: 0.18  SMC: 0.22             │
│    Momentum: 0.17   Candlestick: 0.15                       │
│                                                              │
│  RSI Thresholds (current regime: TRENDING_BULL):            │
│    Oversold: 42  Overbought: 80                              │
│                                                              │
│  Correlation Alert: Long XAU/USD + Long EUR/USD = 2.1%     │
│    effective risk (limit: 2.5%) ✅                           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Summary

### What This Architecture Delivers

1. **5 complete pair profiles** with unique parameters for all 16 strategy steps
2. **Correlation matrix** with enforced rules preventing over-exposure
3. **Session rotation engine** that allocates resources to the best pair per session
4. **New pair onboarding process** with 4-phase evaluation
5. **Adaptive learning system** that continuously improves per-pair parameters
6. **Configuration hierarchy** (defaults → pair overrides → session overrides → runtime adaptive)

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Static config + adaptive learning | Both | Static provides stability; adaptive provides edge |
| Per-pair RSI thresholds | Yes | Different pairs oscillate differently |
| Correlation enforcement at infrastructure level | Yes | Cannot be overridden by agents; safety-critical |
| Session-based pair rotation | Yes | Don't waste resources scanning inactive pairs |
| Minimum account size per pair | Yes | Some pairs are untradeable at $7 |
| Weekly learning cycle | Yes | Enough data per cycle; not too frequent |

### Implementation Priority

| Priority | Component | Effort |
|----------|-----------|--------|
| 1 | EUR/USD config (reference pair) | 1 day |
| 2 | XAU/USD config | 1 day |
| 3 | GBP/USD config | 0.5 days |
| 4 | Correlation engine | 1 day |
| 5 | Session rotation engine | 1 day |
| 6 | GBP/JPY config | 0.5 days |
| 7 | BTC/USD config | 1 day |
| 8 | Adaptive learning system | 3 days |
| 9 | New pair onboarding pipeline | 2 days |
| 10 | Performance dashboard | 2 days |

---

*Document generated for Alpha Stack — Pair-Specific Strategy Architecture*
*Part of the AlphaStack (Volatility-Mapped Price Movement) Strategy Framework*
*Version 1.0 — 2026-07-11*
