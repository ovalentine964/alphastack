# AlphaStack — Comprehensive Strategy Build Plan

**Version:** 1.0  
**Date:** 2026-07-15  
**Status:** Strategy Architecture — Ready for Implementation  
**Scope:** Complete trading strategy design for the multi-agent system  

---

## Table of Contents

1. [Current Strategy Analysis](#1-current-strategy-analysis)
2. [Strategy Architecture](#2-strategy-architecture)
3. [AI/ML Strategy Components](#3-aiml-strategy-components)
4. [Broker-Specific Strategy (Binance)](#4-broker-specific-strategy-binance)
5. [Implementation Roadmap](#5-implementation-roadmap)
6. [Risk-Adjusted Strategy](#6-risk-adjusted-strategy)

---

## 1. Current Strategy Analysis

### 1.1 What Exists in the Code

The AlphaStack codebase contains a **fully scaffolded 16-step pipeline** with Pydantic immutable context, an abstract step base class, a parallel-capable pipeline orchestrator, a LangGraph multi-agent orchestrator, and an ONNX inference engine. Here's the status of each component:

#### Strategy Pipeline (`src/alphastack/strategy/`)

| Step | File | Status | What It Does | What's Missing |
|------|------|--------|-------------|----------------|
| **01** | `s01_fundamental.py` | ✅ Implemented | VIX-proxy macro regime, news sentiment, high-impact event dampening | No FinBERT integration, no real calendar feed, no LLM reasoning |
| **02** | `s02_bias.py` | ✅ Implemented | Multi-TF MA crossover bias (5/20), HTF bias | No HMM regime detection, no dynamic alpha weighting, no conflict resolution |
| **03** | `s03_session.py` | ✅ Implemented | UTC-based session detection (Asian/London/NY), volatility multiplier | No Asian range tracking, no session-specific trading rules, no overlap detection |
| **04** | `s04_structure.py` | ✅ Implemented | Swing H/L detection (lookback method), HH/HL/LH/LL classification, BOS/CHoCH | No adaptive lookback (ATR-based), no multi-TF structure alignment, no chop detection |
| **05** | `s05_support_resistance.py` | ✅ Implemented | Price bucketing to 50-pip zones, touch counting, swing-based S/R | No volume profile, no multi-TF weighting, no institutional levels, no flip logic |
| **06** | `s06_liquidity.py` | ✅ Implemented | Equal highs/lows detection, stop cluster from S/R, deduplication | No order book depth, no sweep vs fake classification, no on-chain data |
| **07** | `s07_smc.py` | ✅ Implemented | Order block detection (bearish→bullish impulse), FVG detection (3-candle gap), breaker blocks (stub) | Breaker blocks are a stub returning `[]`. No confluence scoring, no failure tracking |
| **08** | `s08_rsi.py` | ✅ Implemented | RSI(14) with Wilder smoothing, overbought/oversold, divergence detection | No adaptive thresholds, no multi-TF RSI, no composite momentum |
| **09** | `s09_candlestick.py` | ✅ Implemented | Engulfing, hammer, shooting star, doji, morning/evening star detection | No volume weighting, no context multipliers, no ML pattern recognition |
| **10** | `s10_confluence.py` | ✅ Implemented | Weighted scoring (9 components), direction decision at 40+ threshold | Weights are hardcoded, no regime-adaptive weights, no ML confluence scorer |
| **11** | `s11_sizing.py` | ✅ Implemented | Fixed fractional (risk_pct from market_data), ATR-based stop distance | No Kelly criterion, no correlation adjustment, no regime multiplier, no performance multiplier |
| **12** | `s12_stop_loss.py` | ✅ Implemented | Structure-based (swing H/L) + ATR-based, takes wider (conservative) | No volatility-adaptive buffers, no stop hunt protection, no liquidity pool awareness |
| **13** | `s13_take_profit.py` | ✅ Implemented | R:R multipliers [1.5, 2.5, 4.0], S/R override for TP1 | No partial TP logic, no session-based targets, no trailing TP |
| **14** | `s14_management.py` | ✅ Implemented | Break-even at 1R, ATR trail at 1.5R, 50% partial at TP1 | No dynamic R-multiple targets, no news event handling, no correlation management |
| **15** | `s15_exit.py` | ✅ Implemented | Time-based exit (48h), structure flip, RSI reversal warning, confluence drop, stop hit | No early warning detection, no weekend management, no black swan protocol |
| **16** | `s16_journal.py` | ✅ Structured logging | Tag generation, notes summary, JSON log emission | No persistent storage, no performance analytics, no RL feedback loop |

#### Multi-Agent System (`src/alphastack/agents/`)

| Component | Status | What It Does | What's Missing |
|-----------|--------|-------------|----------------|
| **Strategy Agent** | ✅ Implemented | Wraps pipeline, generates signals, applies news adjustment | No fallback signal quality, no multi-symbol scanning |
| **Orchestrator** | ✅ Implemented | LangGraph state machine: news→strategy→risk→execution→reflection | No streaming, no checkpointing to Redis, no parallel symbol processing |
| **Orchestrator State** | ✅ Implemented | Pydantic state with signals, decisions, risk, news, execution | Missing: regime state, correlation matrix, portfolio context |
| **Risk Agent** | Referenced but not read | Approves/rejects signals | Needs: circuit breaker, drawdown management, correlation limits |
| **News Agent** | Referenced but not read | Detects high-impact events | Needs: FinBERT integration, real feed connection |
| **Execution Agent** | Referenced but not read | Routes to brokers | Needs: Binance CCXT integration, order management |
| **Reflection Agent** | Referenced but not read | Post-trade analysis | Needs: RL training loop, performance attribution |

#### Data Layer (`src/alphastack/data/`)

| Component | Status | What It Does | What's Missing |
|-----------|--------|-------------|----------------|
| **Market Data** | ✅ Implemented | Tick normalization, candle aggregation (M1/M5/M15/H1/H4/D1), event bus | No Binance connector, no MT5 connector (only interfaces) |
| **News Feed** | ✅ Implemented | Polygon.io news fetch, keyword-based sentiment scoring, macro event detection | No FinBERT, no RSS feeds, no central bank feeds |
| **Alternative Data** | ✅ Stub | Funding rates (Binance/Bybit API), whale alerts (stub), social sentiment (stub), Google Trends (stub) | All social/whale/trends are stubs |
| **Feature Engineering** | ✅ Implemented | SMA, EMA, RSI, MACD, BB, ATR, Stochastic, VWAP, ADX — all vectorized. Feature store. Normalizer. | No structure features, no cross-asset features, no regime features |
| **TimescaleDB** | Schema defined | Hypertables for OHLCV, features, predictions | Needs: actual database setup, migration scripts |

#### Models (`src/alphastack/models/`)

| Component | Status | What It Does | What's Missing |
|-----------|--------|-------------|----------------|
| **Inference Engine** | ✅ Implemented | ONNX Runtime with model caching, latency tracking (p50/p95/p99), warm-up, batch prediction | No model registry integration, no fallback chain |
| **Model Trainer** | ✅ Implemented | Walk-forward validation, hyperparameter grid search, ONNX export, early stopping | No Optuna integration, no SHAP explainability, no drift detection |
| **Model Registry** | Interface defined | Versioned model storage | Needs: actual file structure, metadata schema |

#### Reasoning (`src/alphastack/reasoning/`)

| Component | Status | What It Does | What's Missing |
|-----------|--------|-------------|----------------|
| **Chain of Thought** | ✅ Implemented | 6-step reasoning (observe→collect→weigh→hypothesize→validate→conclude), confidence scoring | Not connected to pipeline steps |
| **Causal Inference** | ✅ Implemented | Temporal precedence, correlation vs causation, counterfactual reasoning, news impact scoring | Not connected to trade decisions |
| **Explainability** | ✅ Implemented | Factor contribution breakdown, risk/benefit analysis, audit trail generation | Not connected to trade journal |

### 1.2 What's Working vs Needs Building

#### ✅ Working (Can Use Today)
1. **Pipeline architecture** — The 16-step immutable context pattern is solid and production-ready
2. **Step implementations** — All 16 steps have working logic (albeit simplified)
3. **Confluence engine** — Weighted scoring with component breakdown works
4. **Risk management skeleton** — Position sizing, stop loss, take profit, exit conditions all exist
5. **Agent orchestrator** — LangGraph state machine with human-in-the-loop works
6. **Inference engine** — ONNX Runtime with caching and latency tracking is production-grade
7. **Feature engineering** — 20+ technical indicators computed vectorized
8. **Reasoning engines** — Chain of thought, causal inference, explainability all implemented

#### ⚠️ Needs Enhancement (Works But Simplified)
1. **Fundamental intelligence** — Keyword sentiment → needs FinBERT
2. **Market bias** — Simple MA crossover → needs HMM regime detection
3. **Session analysis** — Basic UTC detection → needs Asian range tracking, session rules
4. **Structure detection** — Fixed lookback → needs ATR-adaptive, multi-TF alignment
5. **S/R detection** — Price bucketing → needs volume profile, institutional levels
6. **Liquidity detection** — Equal highs/lows → needs order flow, sweep classification
7. **SMC detection** — Basic OB/FVG → needs confluence scoring, failure tracking
8. **RSI** — Fixed thresholds → needs adaptive thresholds, composite momentum
9. **Candlestick** — Rule-based patterns → needs volume weighting, context scoring
10. **Position sizing** — Fixed fractional → needs Kelly, correlation, regime adjustment
11. **Stop loss** — Structure + ATR → needs volatility-adaptive, stop hunt protection
12. **Take profit** — Fixed R:R → needs partial TPs, session targets, trailing

#### 🔴 Needs Building From Scratch
1. **HMM regime detector** — 3-state model with ensemble scoring
2. **FinBERT sentiment pipeline** — Fine-tuned forex/crypto sentiment
3. **Multi-timeframe analysis engine** — W1→D1→H4→H1 alignment
4. **Correlation engine** — Rolling correlation matrix with enforcement
5. **Binance connector** — CCXT integration for live trading
6. **Backtesting engine** — Walk-forward with realistic costs
7. **RL training environment** — PPO/DQN for sizing and TP optimization
8. **Model monitoring** — Drift detection, performance tracking
9. **Portfolio manager** — Multi-position management, exposure tracking
10. **Journal database** — Persistent trade storage with analytics

---

## 2. Strategy Architecture

### 2.1 Multi-Timeframe Analysis

The system must analyze price action across 6 timeframes simultaneously, with each serving a distinct role:

```
┌─────────────────────────────────────────────────────────────────┐
│                MULTI-TIMEFRAME ANALYSIS ENGINE                    │
│                                                                   │
│  WEEKLY (W1) ─── MACRO DIRECTION                                │
│  ├── Institutional positioning, major S/R                        │
│  ├── Weight: 0.30 (bias foundation)                              │
│  └── Update: Every Monday open                                   │
│       │                                                          │
│       ▼                                                          │
│  DAILY (D1) ─── SWING BIAS                                       │
│  ├── Swing structure, OB/FVG zones, key levels                  │
│  ├── Weight: 0.30 (primary reference)                            │
│  └── Update: Every D1 candle close (00:00 UTC for crypto)       │
│       │                                                          │
│       ▼                                                          │
│  4-HOUR (H4) ─── TACTICAL POSITION                               │
│  ├── BOS/CHoCH detection, trend confirmation                    │
│  ├── Weight: 0.25 (trade direction)                              │
│  └── Update: Every H4 candle close                               │
│       │                                                          │
│       ▼                                                          │
│  1-HOUR (H1) ─── ENTRY TIMING                                    │
│  ├── OB/FVG entry zones, RSI confirmation                       │
│  ├── Weight: 0.10 (timing refinement)                            │
│  └── Update: Every H1 candle close                               │
│       │                                                          │
│       ▼                                                          │
│  15-MINUTE (M15) ─── PRECISION ENTRY                              │
│  ├── Candlestick patterns, exact entry price                    │
│  ├── Weight: 0.05 (execution timing)                             │
│  └── Update: Every M15 candle close                              │
│       │                                                          │
│       ▼                                                          │
│  5-MINUTE (M5) ─── SCALING & MANAGEMENT                          │
│  ├── Trailing stop adjustments, partial close timing            │
│  ├── Used only during active trades                              │
│  └── Update: Every M5 candle close                               │
└─────────────────────────────────────────────────────────────────┘
```

**Alignment Rule:** A trade is only taken when the **directional bias aligns across at least 3 of 4 primary timeframes** (W1, D1, H4, H1). The confluence score gets a multiplier:
- 4/4 aligned: 1.3× confluence bonus
- 3/4 aligned: 1.1× confluence bonus
- 2/4 aligned: 0.8× (reduced conviction)
- 1/4 aligned: No trade

### 2.2 Entry Signal Logic

A trade entry requires the following cascade of confirmations:

```
ENTRY CASCADE (must pass top-to-bottom):

GATE 1: REGIME CHECK
├── HMM regime != CRISIS (confidence > 0.7)
├── If UNCERTAIN → reduce size by 50%
└── If CRISIS → NO TRADE

GATE 2: SESSION CHECK
├── Current session allows trading (per pair config)
├── Not within 30 min of high-impact news
├── Spread < 2× average
└── Asian session: reduced size, no breakouts

GATE 3: DIRECTIONAL BIAS
├── Multi-TF alignment score > 0.6
├── Fundamental bias + Technical bias not in conflict
└── If conflict → WAIT (don't trade opposing forces)

GATE 4: STRUCTURE CONFIRMATION
├── BOS confirmed in trade direction (continuation)
├── OR CHoCH confirmed (reversal — higher conviction required)
├── Price at or near OB/FVG zone
└── Chop score < 0.6 (not in ranging chop)

GATE 5: CONFLUENCE SCORING
├── S/R proximity score > 0.3
├── Liquidity pool alignment
├── SMC pattern score > 0.3
├── RSI confirmation (adaptive threshold)
├── Candlestick pattern confirmation
└── TOTAL CONFLUENCE SCORE > 60/100

GATE 6: RISK CHECK
├── Current exposure < 6% of account
├── No correlated position at limit
├── Daily loss < 4% of account
├── Circuit breaker not active
└── Position size calculated and validated

→ IF ALL GATES PASS → GENERATE ENTRY SIGNAL
```

**Entry Types:**

| Entry Type | When | Order Type | Slippage Tolerance |
|-----------|------|-----------|-------------------|
| **Limit at OB** | Price approaching OB zone, high confluence | Limit order at OB edge | 0 pips (wait for fill) |
| **Limit at FVG** | FVG present, price approaching | Limit order at FVG midpoint | 0 pips |
| **Market on BOS** | Strong BOS with volume confirmation | Market order | 2 pips max |
| **Market on Sweep** | Liquidity sweep detected, reversal confirmed | Market order | 3 pips max |
| **Limit at S/R** | Price at key S/R level with pattern | Limit order at level + buffer | 0 pips |

### 2.3 Exit Signal Logic

```
EXIT HIERARCHY (checked in order, first match wins):

1. STOP LOSS HIT
   └── Automatic exit at stop price (handled by exchange/broker)

2. BLACK SWAN DETECTION (overrides everything)
   ├── VIX spike > 40% in 1 hour
   ├── ATR(1) > 5× ATR(14)
   ├── Spread > 10× normal
   └── Response: CLOSE ALL IMMEDIATELY

3. STRUCTURE INVALIDATION
   ├── Trade direction: LONG, but structure flipped to BEARISH (CHoCH)
   ├── Trade direction: SHORT, but structure flipped to BULLISH (CHoCH)
   └── Response: Close at market

4. CONFLUENCE COLLAPSE
   ├── Confluence score drops below 25/100
   └── Response: Close at market

5. NEWS EVENT INVALIDATION
   ├── High-impact event changes fundamental thesis
   ├── Central bank surprise (unexpected rate change)
   └── Response: Close or tighten stop per news protocol

6. TIME-BASED EXIT
   ├── Intraday: > 8 hours without 0.5 ATR movement
   ├── Swing: > 48 hours without 1R movement
   └── Response: Close at market (capital efficiency)

7. TAKE PROFIT LEVELS
   ├── TP1: 1.5R → Close 33%, move SL to break-even
   ├── TP2: 2.5R → Close 33%, trail remaining with ATR
   ├── TP3: 4.0R → Trail with structure (let it run)
   └── S/R override: If nearest S/R is closer than TP1, use S/R

8. TRAILING STOP
   ├── Activate at 1.5R profit
   ├── Trail distance: 1.5× ATR(14)
   ├── Method: Structure-based (trail to swing H/L)
   └── Never moves backward (only tightens)
```

### 2.4 Position Sizing Logic

The position sizing system uses a **multi-factor approach** that adapts to signal quality, market regime, and account state:

```
POSITION SIZE CALCULATION:

Base Risk = Account Balance × 1.0%

Multipliers:
  Confluence Score Multiplier:
    Score 80-100 (A+):  1.5× → 1.5% risk
    Score 65-79  (A):   1.0× → 1.0% risk
    Score 50-64  (B):   0.5× → 0.5% risk
    Score < 50:          NO TRADE

  Regime Multiplier:
    BULL_TREND (conf > 0.7):   1.2×
    BEAR_TREND (conf > 0.7):   0.7× (reduced — counter-trend risk)
    RANGE (conf > 0.7):        1.0×
    UNCERTAIN:                 0.5×
    CRISIS:                    0.0× (no trading)

  Recent Performance Multiplier:
    Last 5 trades: 4+ wins:     1.1× (momentum)
    Last 5 trades: 3 wins:      1.0× (neutral)
    Last 5 trades: ≤2 wins:     0.7× (cool down)
    3 consecutive losses:        0.5× (circuit breaker)
    5 consecutive losses:        0.0× (stop trading)

  Session Multiplier:
    London-NY Overlap:          1.2× (highest liquidity)
    London or NY solo:          1.0×
    Asian:                      0.7×
    Off-hours:                  0.0×

  Correlation Adjustment:
    If new position correlates > 0.7 with existing:
      Combined risk cap = 2.5%
      Reduce new position to fit within cap

FINAL RISK = Base Risk × Confluence × Regime × Performance × Session × Correlation

HARD CAPS:
  Max risk per trade:     2.0% of account
  Max open exposure:      6.0% of account
  Max correlated (|ρ|>0.7): 2.5% of account
  Max daily loss:         4.0% of account

POSITION SIZE (lots) = Final Risk Amount / (Stop Distance × Pip Value)
```

### 2.5 Portfolio Management

```
PORTFOLIO CONSTRAINTS:

Maximum Concurrent Positions: 5
  ├── Max per pair: 1
  ├── Max per correlation cluster: 2
  │   ├── USD cluster: EUR/USD, GBP/USD, USD/CHF (pick max 2)
  │   ├── JPY cluster: GBP/JPY, EUR/JPY, USD/JPY (pick max 2)
  │   └── Crypto cluster: BTC/USD, ETH/USD (pick max 1)
  └── Max same direction: 3 (prevent one-sided bet)

Correlation Matrix (rolling 20-day):
              XAU/USD  BTC/USD  EUR/USD  GBP/USD  GBP/JPY
  XAU/USD      1.00    -0.30     0.70     0.65     0.10
  BTC/USD     -0.30     1.00    -0.55    -0.50     0.15
  EUR/USD      0.70    -0.55     1.00     0.90     0.40
  GBP/USD      0.65    -0.50     0.90     1.00     0.55
  GBP/JPY      0.10     0.15     0.40     0.55     1.00

Effective Exposure Calculation:
  For each pair of positions (i, j):
    effective_risk_i = risk_i × (1 + |correlation_ij| × risk_j / total_risk)
  
  Total effective exposure = Σ effective_risk_i
  Must be < 6% of account

Position Priority (when slots are full):
  1. Highest confluence score gets priority
  2. Least correlated with existing positions
  3. Best session alignment
  4. Replace lowest-performing existing position if new signal is stronger
```

---

## 3. AI/ML Strategy Components

### 3.1 ML Models to Train

The strategy requires **8 model families** organized by latency tier:

#### Tier 1: Ultra-Fast (< 5ms) — Real-time Execution

| Model | Purpose | Features | Training Data | Target Accuracy |
|-------|---------|----------|--------------|----------------|
| **HMM Regime** | 3-state regime detection (Bull/Bear/Range) | Returns, volatility, ATR ratio, ADX, volume ratio (5 features) | 5 years OHLCV, labeled by rules engine | State accuracy > 75% |
| **Rules Engine** | Zero-lag regime classification | ADX, 20d realized vol, 20d return, cross-asset correlation | N/A (deterministic) | N/A |

#### Tier 2: Fast (< 50ms) — Per-Candle Analysis

| Model | Purpose | Features | Training Data | Target Accuracy |
|-------|---------|----------|--------------|----------------|
| **XGBoost Confluence** | Signal quality scoring (profitable trade probability) | 45 features: S/R score, liquidity sweep, OB strength, FVG, BOS, RSI alignment, candlestick score, volume, session, regime | 200K samples, 3yr walk-forward | AUC-ROC > 0.72 |
| **XGBoost Sweep** | Real vs fake liquidity sweep classification | Volume ratio, rejection strength, delta flip, S/R score, displacement, time at level | 50K labeled sweeps | Accuracy > 75% |
| **XGBoost SMC** | SMC pattern success prediction | Pattern type, impulse magnitude, volume, distance to S/R, RSI state, HTF alignment, session | 100K labeled patterns | AUC-ROC > 0.70 |
| **XGBoost RSI** | RSI signal quality (will the signal work?) | RSI value, regime, divergence, composite momentum, volume context, session | 150K labeled signals | AUC-ROC > 0.68 |
| **XGBoost S/R** | S/R level quality scoring | Touch count, recency, timeframe diversity, volume at level, round number proximity | 100K labeled levels | AUC-ROC > 0.72 |

#### Tier 3: Medium (< 500ms) — Per-Session Analysis

| Model | Purpose | Features | Training Data | Target Accuracy |
|-------|---------|----------|--------------|----------------|
| **LSTM Price** | Direction + return + volatility prediction | 60 features × 100 bars lookback: OHLCV + indicators + cross-asset + session + sentiment | 500K sequences, walk-forward | Direction accuracy > 58% |
| **FinBERT** | Financial sentiment classification | Headline + first 2 sentences (max 512 tokens) | 50K labeled sentences (forex-specific) | Accuracy > 85% |
| **PPO Sizing** | Position size optimization | 12 state features: confluence, regime, vol, recent WR, session, correlation, drawdown | 1M RL transitions | Sharpe +15% vs rules |
| **DQN TP** | Take-profit optimization | Current R, time in trade, vol regime, structure, session | 500K transitions | +0.3R per trade |

#### Tier 4: Slow (1-10s) — Periodic/Event-Driven

| Model | Purpose | Trigger | Target |
|-------|---------|---------|--------|
| **LLM Reasoning** | Fundamental analysis, macro synthesis | Pre-session + high-impact events | Human agreement > 80% |
| **LLM Fast** | News classification, entity extraction | Every news article | Latency < 2s |

### 3.2 Feature Engineering

The feature engineering pipeline computes **~60 features per asset per timeframe**, organized into 5 groups:

#### Group 1: Price-Derived (20 features per TF × 4 TFs = 80 raw)

```
OHLCV (5) + SMA(20,50) + EMA(12,26) + RSI(7,14,21) + MACD(3) + 
ATR(7,14) + Bollinger(3) + Stochastic(2) + ADX(1) + VWAP(1) + Volume Ratio(1)
```

#### Group 2: Structure Features (25 features)

```
swing_high/low_distance, swing_high/low_value,
bos_type, bos_strength, choch_type, choch_strength,
ob_type, ob_strength, ob_age, ob_distance_atr,
fvg_present, fvg_size_atr, fvg_filled_pct,
sr_score, sr_touch_count, sr_recency, sr_distance_atr,
liquidity_above, liquidity_below, sweep_detected, order_flow_delta,
volume_ratio_20_50, volume_spike, chop_score, adx
```

#### Group 3: Context Features (20 features)

```
session (encoded), hour_of_day_sin/cos, day_of_week_sin/cos,
regime, regime_confidence, regime_persistence_days,
sentiment_score, sentiment_momentum,
event_risk_score, high_impact_event_4h, nfp_today, fomc_today,
vix_level, vix_change_1d, realized_vol_20d, atr_percentile,
funding_rate (crypto), open_interest_change, long_short_ratio
```

#### Group 4: Cross-Asset Features (15 features)

```
dxy_return_1h/4h, dxy_rsi_14,
us10y_yield, us10y_change_1d, yield_curve_10y_2y,
sp500_return_1d/1h,
gold_return_1d, oil_return_1d,
corr_dxy_20d, corr_sp500_20d, corr_btc_20d,
dxy_lead_2_return
```

**Feature Selection Pipeline (monthly):**
1. Correlation filter: Remove features with > 0.95 pairwise correlation
2. Mutual information ranking: Keep top 80
3. SHAP-based selection: Keep features with mean |SHAP| > threshold
4. Boruta validation: Keep features that beat shuffled shadows
5. Result: 30-50 features per model

### 3.3 Regime Detection

The regime detection system uses an **ensemble of 4 methods** with weighted consensus:

```
┌─────────────────────────────────────────────────────────────────┐
│                ENSEMBLE REGIME DETECTION                          │
│                                                                   │
│  Method 1: Rules-Based (Weight: 0.4)                            │
│  ├── ADX(14): <20=no trend, 20-25=emerging, >25=strong          │
│  ├── 20d Realized Vol: <15%=calm, 15-25%=normal, >35%=crisis    │
│  ├── 20d Return: >+5%=bull, <-5%=bear, ±2%=range                │
│  └── Cross-asset Correlation: >0.8=crisis                        │
│                                                                   │
│  Method 2: HMM 3-State (Weight: 0.3)                            │
│  ├── States: BULL_TREND, BEAR_TREND, RANGE                       │
│  ├── Features: returns, vol, ATR ratio, ADX, volume ratio        │
│  └── Transition matrix learned from data                         │
│                                                                   │
│  Method 3: Volatility Clustering (Weight: 0.2)                   │
│  ├── Realized vol percentile determines regime                   │
│  └── Simple but effective single-feature detector                │
│                                                                   │
│  Method 4: ML Classifier (Weight: 0.1, Phase 2+)                 │
│  ├── XGBoost trained on labeled regime history                   │
│  └── Captures non-linear patterns the others miss                │
│                                                                   │
│  Ensemble Rule:                                                   │
│  ├── 2/3 methods agree → regime with 0.6-0.7 confidence         │
│  ├── 3/3 methods agree → regime with 0.8+ confidence             │
│  └── No agreement → UNCERTAIN (0.3 confidence)                   │
│                                                                   │
│  Crisis Amplification: Crisis signals get 2× weight              │
│  (Missing a bull trend costs gains; missing a crisis costs capital)│
└─────────────────────────────────────────────────────────────────┘
```

**Regime → Strategy Routing:**

| Regime | Trend Weight | Mean Reversion Weight | Defense Weight | Position Size Mult | RSI Oversold/Overbought |
|--------|-------------|----------------------|----------------|-------------------|------------------------|
| BULL_TREND | 0.80 | 0.10 | 0.10 | 1.2× | 40 / 80 |
| BEAR_TREND | 0.70 (short) | 0.10 | 0.20 | 0.7× | 20 / 60 |
| RANGE | 0.10 | 0.80 | 0.10 | 1.0× | 30 / 70 |
| CRISIS | 0.05 | 0.05 | 0.90 | 0.3× | — (no new trades) |
| UNCERTAIN | 0.25 | 0.25 | 0.50 | 0.5× | 30 / 70 |

**Soft Switching:** Regime transitions happen gradually over 3-5 days using ease-in-out interpolation, not hard flips. This reduces switching costs by 40-60%.

### 3.4 LLM Integration for Reasoning

The Xiaomi MiMo model (running as the system's base LLM) can be leveraged for:

#### Pre-Session Fundamental Analysis

```
Trigger: 30 minutes before each major session open (London, NY)
Input: Economic calendar, recent news headlines, current regime, price action summary
Task: "Should I trade this session? Assess fundamental environment."
Output: {recommendation: TRADE|WAIT|AVOID, bias: BULLISH|BEARISH|NEUTRAL, 
         confidence: 0-1, key_factors: [...], reasoning: "chain of thought"}
Latency: 3-10s (acceptable for pre-session)
```

#### High-Impact Event Interpretation

```
Trigger: High-impact event detected (NFP, CPI, FOMC, etc.)
Input: Event details, actual vs forecast, current market conditions, historical similar events
Task: "Interpret this event. What does it mean for [pair]? Expected impact?"
Output: {direction, magnitude_pips, timeframe_hours, confidence, reasoning}
Latency: 2-5s
```

#### Trade Rationale Generation

```
Trigger: After each trade signal generation
Input: All 16 step outputs, confluence breakdown, market context
Task: "Explain this trade signal in plain language. Why should we take this trade?"
Output: Human-readable rationale for journal and audit
Latency: 1-3s
```

#### Weekly Performance Review

```
Trigger: Sunday evening
Input: All trades from the week, performance metrics, regime changes
Task: "Analyze this week's trading. What worked? What didn't? What should change?"
Output: Structured review with specific recommendations
Latency: 5-10s
```

### 3.5 Sentiment Analysis Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                SENTIMENT ANALYSIS PIPELINE                        │
│                                                                   │
│  Layer 1: FinBERT Classification (Always Running)               │
│  ├── Input: Headline + first 2 sentences                        │
│  ├── Output: Bullish/Bearish/Neutral + confidence               │
│  ├── Latency: < 100ms                                           │
│  └── Use: All articles                                          │
│                                                                   │
│  Layer 2: LLM Reasoning (Triggered for Complex Events)          │
│  ├── Trigger: High-impact event OR FinBERT confidence < 0.6     │
│  ├── Input: Full article + macro context                        │
│  ├── Output: Direction + confidence + reasoning                 │
│  └── Latency: 2-5s                                              │
│                                                                   │
│  Layer 3: Event Impact Scoring (Historical + Bayesian)          │
│  ├── Input: Event type + actual vs forecast + regime            │
│  ├── Output: Expected move, direction probability, impact window│
│  └── Latency: < 5ms (table lookup)                              │
│                                                                   │
│  Source Weighting:                                                │
│  ├── Central bank feeds:   1.5× (highest authority)             │
│  ├── Bloomberg/Reuters:    1.0×                                  │
│  ├── ForexFactory:         0.8×                                  │
│  ├── Social media:         0.3×                                  │
│  └── Unknown sources:      0.1×                                  │
│                                                                   │
│  Final Score = Σ(sentiment_i × source_weight_i × recency_i)     │
│  Sentiment Momentum = ΔSentiment / Δt (rate of change)          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Broker-Specific Strategy (Binance)

### 4.1 Trading Pairs (Priority Order)

| Priority | Pair | Why | Min Account | Session Focus |
|---------|------|-----|-------------|---------------|
| 1 | **BTC/USDT** | Highest liquidity, most data, ETF flows | $10 | US session (13:00-21:00 UTC) |
| 2 | **ETH/USDT** | #2 crypto, DeFi proxy, good SMC patterns | $10 | US session |
| 3 | **BNB/USDT** | Exchange token, Binance-specific advantages | $20 | US session |
| 4 | **SOL/USDT** | High volatility, narrative-driven | $20 | US session |
| 5 | **XRP/USDT** | Regulatory-driven, news-sensitive | $10 | Any session |

**Avoid:** Low-liquidity altcoins, meme coins, newly listed tokens (< 6 months)

### 4.2 Optimal Trading Sessions (UTC)

```
SESSION SCHEDULE FOR CRYPTO:

00:00–08:00 UTC (Asian Session)
├── Activity: LOW-MEDIUM
├── Strategy: Range identification, accumulation zones
├── Position size: 60% of normal
├── Preferred: Mean reversion at range edges
└── Avoid: Breakout trades (low volume = false breakouts)

08:00–13:00 UTC (London Session)
├── Activity: MEDIUM
├── Strategy: European institutional desk activity
├── Position size: 80% of normal
├── Preferred: Trend continuation from Asian range
└── Note: Crypto desks open, increasing volume

13:00–21:00 UTC (US Session — PRIMARY)
├── Activity: MAXIMUM
├── Strategy: ETF flow news, US macro data, largest moves
├── Position size: 100% (full allocation)
├── Preferred: ALL strategies viable
├── Note: FOMC, CPI, NFP all hit during this window
└── This is when 60-70% of daily range is established

21:00–00:00 UTC (Wind Down)
├── Activity: LOW
├── Strategy: Manage existing positions only
├── Position size: 0% (no new entries)
└── Note: Reducing liquidity, wider spreads

WEEKEND (Saturday-Sunday)
├── Activity: LOW (crypto trades 24/7 but reduced)
├── Strategy: Cautious scalping only
├── Position size: 40% of normal
├── Note: Wider spreads, more manipulation potential
└── Close swing positions before Friday 21:00 UTC
```

### 4.3 Order Types

| Situation | Order Type | Rationale |
|-----------|-----------|-----------|
| **Entry at OB/FVG** | Limit | Get best fill at structure level, no slippage |
| **Entry on BOS** | Market | Momentum entry, don't miss the move |
| **Entry on sweep** | Market | Fast-moving, need immediate execution |
| **Stop loss** | Stop-Market | Guaranteed execution, no partial fills |
| **Take profit** | Limit | Get exact price, no slippage |
| **Trailing stop** | Stop-Market (exchange-side) | Let exchange manage the trail |

**Order Execution Rules:**
1. **Never use market orders when spread > 3× average** — wait for spread normalization
2. **Always use limit orders for entries at known levels** — save 1-3 pips per trade
3. **Set stop-loss immediately after entry fill** — no exceptions
4. **Use OCO (One-Cancels-Other) orders** for SL + TP — automate management
5. **Check order book depth before large orders** — avoid moving the market

### 4.4 Slippage Management

```
SLIPPAGE CONTROL:

Expected Slippage by Market Condition:
  Normal market:     0.5-1.0 pips (acceptable)
  High volatility:   2-5 pips (budget for it)
  News event:        5-20 pips (avoid market orders)
  Low liquidity:     3-10 pips (use limit orders only)

Slippage Budget Per Trade:
  Include 2× expected slippage in risk calculation
  If actual slippage > 3× expected → log anomaly, alert

Fill Quality Tracking:
  Track: expected_price vs actual_fill_price for every order
  Report: average slippage per pair per session
  Alert: if slippage > 5 pips on any single order
  Action: switch to limit-only mode if slippage exceeds budget

Binance-Specific:
  Use "Post-Only" flag for limit orders (ensures maker fee)
  Use "IOC" (Immediate or Cancel) for urgent entries
  Monitor Binance's "Mark Price" for stop triggers (not last price)
  Use "Reduce-Only" flag on stop-loss orders (prevent accidental position increase)
```

---

## 5. Implementation Roadmap

### Phase 1: MVP Strategy (Weeks 1-4) — "Walk"

**Goal:** Get the existing pipeline producing real signals on Binance paper trading.

| Week | Tasks | Deliverable |
|------|-------|-------------|
| **1** | Wire Binance CCXT connector to MarketDataPipeline. Connect BTC/USDT and ETH/USDT real-time data. Set up TimescaleDB for OHLCV storage. | Live market data flowing into pipeline |
| **2** | Run the 16-step pipeline on live BTC/USDT data. Log all step outputs. Identify which steps produce useful vs garbage signals. | Pipeline running on live data with logging |
| **3** | Implement confluence score threshold tuning. Backtest confluence thresholds on 1 year of BTC/USDT data. Find optimal threshold (likely 55-65). | Optimized confluence threshold |
| **4** | Connect paper trading via Binance testnet. Run pipeline → risk gate → paper execution. Track signals vs outcomes. | Paper trading producing P&L data |

**Success Criteria:**
- Pipeline runs without errors on live data
- Confluence score distribution is reasonable (not all 0 or all 100)
- Paper trades execute with realistic fills
- At least 20 paper trades completed for initial analysis

### Phase 2: Regime + Sentiment (Weeks 5-8) — "Jog"

**Goal:** Add regime detection and sentiment to filter signals.

| Week | Tasks | Deliverable |
|------|-------|-------------|
| **5** | Implement rules-based regime detector (ADX + vol + return + correlation). Wire into Step 2 (Market Bias). | Regime detection working |
| **6** | Train HMM regime detector on 3 years of BTC/USDT data. Deploy as ensemble with rules-based. | Ensemble regime detection |
| **7** | Integrate FinBERT for sentiment scoring. Fine-tune on crypto news corpus. Wire into Step 1 (Fundamental). | Sentiment pipeline active |
| **8** | Implement adaptive RSI thresholds per regime. Implement session-specific trading rules. | Regime-adaptive parameters |

**Success Criteria:**
- Regime detection accuracy > 70% on labeled historical data
- FinBERT accuracy > 82% on crypto test set
- Signal quality improves (higher win rate in trending regimes)
- False signals reduce in ranging/crisis regimes

### Phase 3: ML Models (Weeks 9-12) — "Run"

**Goal:** Deploy XGBoost models for confluence scoring and pattern prediction.

| Week | Tasks | Deliverable |
|------|-------|-------------|
| **9** | Build feature engineering pipeline (60+ features). Implement walk-forward validation. Prepare training datasets. | Feature pipeline + training data |
| **10** | Train XGBoost confluence scorer. Train XGBoost sweep classifier. Deploy via ONNX inference engine. | 2 XGBoost models in production |
| **11** | Train XGBoost SMC pattern predictor. Train XGBoost RSI signal model. Implement SHAP explainability. | 4 XGBoost models total |
| **12** | Implement model monitoring (latency, accuracy, drift). Set up A/B testing framework (shadow mode). | Model monitoring + A/B framework |

**Success Criteria:**
- XGBoost confluence AUC-ROC > 0.72 on OOS data
- Models serve predictions in < 50ms
- SHAP explanations available for every prediction
- Shadow mode running, comparing ML vs rules-based signals

### Phase 4: RL + Advanced (Weeks 13-16) — "Sprint"

**Goal:** Add reinforcement learning for position sizing and take-profit optimization.

| Week | Tasks | Deliverable |
|------|-------|-------------|
| **13** | Build RL training environment (wraps backtester). Train PPO position sizing agent (1M transitions offline). | PPO sizing agent trained |
| **14** | Train DQN take-profit agent. Implement RL safety constraints (hard limits). Deploy RL in shadow mode. | DQN TP agent trained |
| **15** | Implement correlation engine with enforcement. Implement portfolio manager (multi-position). Implement circuit breaker. | Portfolio management active |
| **16** | Connect LLM for fundamental reasoning. Implement trade journal database. Implement performance analytics dashboard. | Full system integration |

**Success Criteria:**
- PPO sizing improves Sharpe by > 10% vs rules-based
- DQN TP improves average R-multiple by > 0.2R
- Correlation engine prevents over-exposure
- LLM generates useful trade rationale
- Journal stores all trade data with analytics

### Phase 5: Live Trading (Weeks 17+) — "Fly"

**Goal:** Transition from paper to live with graduated capital allocation.

| Week | Tasks | Deliverable |
|------|-------|-------------|
| **17-18** | Live trading with 10% of intended capital. Monitor all systems. Compare live vs paper performance. | Live trading at 10% size |
| **19-20** | Increase to 25% if performance matches paper. Implement automated retraining pipeline. | Live at 25% size |
| **21-24** | Increase to 50% → 100% over 4 weeks. Implement model versioning and rollback. | Full capital deployment |
| **25+** | Continuous monitoring, monthly model retraining, quarterly strategy review. | Production operations |

### Backtesting Strategy

Each component must be backtested before deployment:

```
BACKTESTING PROTOCOL:

1. DATA PREPARATION
   ├── Collect 3+ years of OHLCV data (M15 granularity)
   ├── Include spread, swap, commission costs
   ├── Include slippage model (0.5-2 pips depending on volatility)
   └── Split: 70% train, 15% validation, 15% OOS test

2. WALK-FORWARD VALIDATION
   ├── Train window: 252 days (1 year)
   ├── Test window: 63 days (3 months)
   ├── Step: 21 days (1 month)
   ├── Gap: 5 bars between train and test (prevent leakage)
   └── Report: mean ± std of metrics across all folds

3. STRATEGY-LEVEL BACKTEST
   ├── Run full 16-step pipeline on historical data
   ├── Include ALL transaction costs
   ├── Track: Sharpe, max DD, win rate, profit factor, avg R
   └── Pass criteria: Sharpe > 1.0, max DD < 20%, win rate > 55%

4. STRESS TESTING
   ├── Test on synthetic crisis scenarios (GAN-generated)
   ├── Test on different instruments (cross-pair generalization)
   ├── Parameter sensitivity: ±10% on each parameter
   └── Pass criteria: No catastrophic failure in any scenario

5. FORWARD DEMO VALIDATION
   ├── Run live signals in paper trading for 4+ weeks
   ├── Compare: paper performance vs backtest expectations
   ├── Track: slippage, spread impact, fill quality
   └── Pass criteria: Paper Sharpe within 20% of backtest Sharpe
```

---

## 6. Risk-Adjusted Strategy

### 6.1 Maximum Positions Per Strategy

| Strategy Type | Max Concurrent | Max Per Pair | Max Per Session |
|--------------|---------------|-------------|-----------------|
| **Trend Following** | 3 | 1 | 2 |
| **Mean Reversion** | 2 | 1 | 1 |
| **Breakout** | 2 | 1 | 1 |
| **Total (all strategies)** | **5** | **1** | **3** |

### 6.2 Correlation Limits

```
CORRELATION ENFORCEMENT (Infrastructure-Level, Cannot Be Overridden):

High Correlation (|ρ| > 0.8):
├── EUR/USD ↔ GBP/USD: 0.90 → Max combined risk: 1.5%
├── EUR/USD ↔ USD/CHF: -0.90 → Max combined risk: 1.5%
├── BTC/USDT ↔ ETH/USDT: 0.85 → Max combined risk: 1.5%
└── XAU/USD ↔ XAG/USD: 0.90 → Max combined risk: 1.5%

Moderate Correlation (|ρ| 0.5-0.8):
├── XAU/USD ↔ EUR/USD: 0.70 → Max combined risk: 2.5%
├── GBP/USD ↔ GBP/JPY: 0.55 → Max combined risk: 2.5%
└── BTC/USDT ↔ SOL/USDT: 0.75 → Max combined risk: 2.5%

Low Correlation (|ρ| < 0.5):
├── XAU/USD ↔ BTC/USDT: -0.30 → No special limit
├── EUR/USD ↔ GBP/JPY: 0.40 → No special limit
└── BTC/USDT ↔ EUR/USD: -0.55 → No special limit

FORBIDDEN COMBINATIONS (never hold simultaneously at full size):
├── Long EUR/USD + Long GBP/USD (same trade)
├── Long BTC/USDT + Long ETH/USDT (same trade)
└── Long XAU/USD + Long XAG/USD (same trade)
```

### 6.3 Drawdown-Based Position Reduction

```
DRAWDOWN RESPONSE PROTOCOL:

Current Drawdown    Action                    Position Size Multiplier
────────────────    ──────                    ────────────────────────
0-3%                Normal operations         1.0×
3-5%                Caution mode              0.7×
5-8%                Defensive mode            0.5×
8-10%               Critical mode             0.3× (high-conviction only)
10-15%              Survival mode             0.1× (manage existing only)
>15%                STOP ALL TRADING          0.0×

Recovery Protocol:
├── After 3 consecutive winning trades → upgrade one level
├── After reaching new equity high → reset to normal
├── Never increase size faster than drawdown reduction
└── Minimum 5 trades at each level before upgrading

Daily Loss Limits:
├── Soft limit: 2% of account → warning alert
├── Hard limit: 4% of account → stop all new entries for the day
├── Emergency: 6% of account → close all positions, stop trading for 48h
└── Monthly limit: 10% of account → full system review required
```

### 6.4 Circuit Breaker Integration

```
CIRCUIT BREAKER CONDITIONS (any 2+ triggers = halt):

TRIGGER 1: Volatility Spike
├── VIX > 40 (or crypto equivalent: BTC 1h ATR > 5× 14d average)
├── Spread > 10× normal on any open position
└── Action: Close all positions immediately

TRIGGER 2: Correlation Collapse
├── Cross-asset correlation > 0.9 across all monitored pairs
├── "Everything moving together" = no diversification exists
└── Action: Reduce all positions to 25% size

TRIGGER 3: Consecutive Losses
├── 5 consecutive losing trades
├── 3 consecutive losses on same pair
└── Action: Stop trading that pair for 24h, reduce global size by 50%

TRIGGER 4: Model Degradation
├── XGBoost confluence accuracy drops > 10% from baseline (rolling 100)
├── HMM regime detection disagrees with rules engine for > 5 days
└── Action: Switch to rules-only mode, alert for model retraining

TRIGGER 5: Infrastructure Failure
├── Data feed interruption > 30 seconds
├── Model inference timeout > 5 seconds (3 consecutive)
├── Order execution failure rate > 5%
└── Action: Close all positions, halt trading until resolved

RECOVERY FROM CIRCUIT BREAKER:
├── Minimum cooldown: 1 hour (volatility spike)
├── Medium cooldown: 24 hours (consecutive losses)
├── Long cooldown: 1 week (model degradation)
└── All recovery requires human approval
```

### 6.5 Risk Budget Allocation

```
RISK BUDGET PER ACCOUNT SIZE:

Account $50-$200 (Micro):
├── Max risk per trade: 2.0%
├── Max open positions: 2
├── Max daily loss: 4.0%
├── Max correlated risk: 2.5%
├── Preferred pairs: BTC/USDT, ETH/USDT (smallest position sizes)
└── Strategy: Conservative, A-grade setups only

Account $200-$1,000 (Small):
├── Max risk per trade: 1.5%
├── Max open positions: 3
├── Max daily loss: 4.0%
├── Max correlated risk: 2.5%
├── Preferred pairs: BTC/USDT, ETH/USDT, SOL/USDT
└── Strategy: Standard, A and B grade setups

Account $1,000-$10,000 (Medium):
├── Max risk per trade: 1.0%
├── Max open positions: 5
├── Max daily loss: 3.0%
├── Max correlated risk: 2.0%
├── Preferred pairs: All viable pairs
└── Strategy: Full strategy deployment

Account $10,000+ (Large):
├── Max risk per trade: 0.75%
├── Max open positions: 5
├── Max daily loss: 2.5%
├── Max correlated risk: 1.5%
├── Preferred pairs: All pairs, consider adding forex via MT5
└── Strategy: Institutional-grade, full ML deployment
```

---

## Appendix A: Confluence Weight Tuning

The default confluence weights (from `s10_confluence.py`) should be tuned per pair and per regime. Here's the starting point and tuning methodology:

**Default Weights (current code):**
```python
_WEIGHTS = {
    "fundamental": 0.05,
    "market_bias": 0.15,
    "session": 0.05,
    "structure": 0.20,
    "sr_levels": 0.10,
    "liquidity": 0.10,
    "smc": 0.15,
    "rsi": 0.10,
    "candlestick": 0.10,
}
```

**Research-Backed Weights (from strategy enhancement docs):**
```python
_WEIGHTS_RESEARCH = {
    "smc_structure": 0.25,    # Highest predictive value
    "liquidity_sweep": 0.20,  # Smart money footprint
    "session_timing": 0.15,   # Institutional flow window
    "candlestick": 0.15,      # Entry timing signal
    "momentum_rsi": 0.10,     # Momentum confirmation
    "volume": 0.10,           # Validates the move
    "fundamental": 0.05,      # Directional filter
}
```

**Tuning Process:**
1. Run backtest with default weights on 1 year of data
2. Use SHAP analysis on XGBoost confluence model to find actual feature importance
3. Adjust weights to match empirical importance
4. Validate on OOS data
5. Re-tune monthly as market conditions change

## Appendix B: Entry Signal Quality Grades

| Grade | Confluence Score | Win Rate Target | R:R Target | Position Size | Frequency |
|-------|-----------------|----------------|------------|---------------|-----------|
| **A+** | 80-100 | > 70% | 1:3+ | 1.5× base | 5-10% of signals |
| **A** | 65-79 | > 60% | 1:2.5 | 1.0× base | 20-30% of signals |
| **B** | 50-64 | > 52% | 1:2.0 | 0.5× base | 30-40% of signals |
| **C** | 40-49 | > 45% | 1:1.5 | Paper trade only | 20-30% of signals |
| **F** | < 40 | — | — | No trade | — |

## Appendix C: Key Performance Indicators

Track these metrics continuously:

**Return Metrics:**
- Total R gained/lost (normalized by risk)
- Win rate by setup type, session, pair
- Average R-multiple (winners vs losers)
- Profit factor (gross profit / gross loss)
- Expectancy = (win_rate × avg_win) - (loss_rate × avg_loss)
- Sharpe ratio (risk-adjusted return)

**Risk Metrics:**
- Max drawdown (R and %)
- Average MAE (Maximum Adverse Excursion)
- Max consecutive losses
- Risk of ruin probability
- Recovery factor (total profit / max drawdown)

**Operational Metrics:**
- Signal generation rate (signals per day)
- Signal-to-trade conversion rate
- Average slippage per trade
- Model inference latency (p50/p95/p99)
- Data feed uptime percentage

---

*This document serves as the complete strategy specification for the AlphaStack trading system. It should be reviewed and updated quarterly as the system evolves from paper trading through live deployment.*
