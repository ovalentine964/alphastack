# Alpha Stack — ML Pipeline Architecture

> **Version:** 1.0 · **Date:** 2026-07-11 · **Author:** Architecture Team
> **Source Research:** [`research/curriculum/research_curriculum_ml_ai.md`](../research/curriculum/research_curriculum_ml_ai.md) — ML/AI curriculum — training pipeline and drift detection
> **Status:** Architecture Complete

---

**Date:** 2026-07-11
**Version:** 1.0
**Status:** Architecture Design — Ready for Implementation Review
**Author:** ML Pipeline Architect Agent
**Depends On:** `architecture_ai_models.md`, `architecture_data.md`, `architecture_multi_agent.md`

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Pipeline Overview](#2-pipeline-overview)
3. [Data Collection & Preprocessing Pipeline](#3-data-collection--preprocessing-pipeline)
4. [Feature Engineering Pipeline](#4-feature-engineering-pipeline)
5. [Model Training Pipeline](#5-model-training-pipeline)
6. [Model Validation Pipeline](#6-model-validation-pipeline)
7. [Model Serving Architecture](#7-model-serving-architecture)
8. [Model Versioning & A/B Testing](#8-model-versioning--ab-testing)
9. [Model Monitoring & Drift Detection](#9-model-monitoring--drift-detection)
10. [Retraining Triggers & Automation](#10-retraining-triggers--automation)
11. [Multi-Agent Integration](#11-multi-agent-integration)
12. [GPU/CPU Considerations](#12-gpucpu-considerations)
13. [Implementation Roadmap](#13-implementation-roadmap)

---

## 1. Executive Summary

Alpha Stack's ML pipeline is a **closed-loop, continuously-learning system** that takes raw market data from 17+ sources, engineers 60+ features per asset, trains and validates 8 model families (20–35 active models), serves predictions at four latency tiers, monitors for drift and degradation, and automatically retrains when performance decays. The pipeline is designed to start on a single CPU machine ($7 account) and scale to GPU-accelerated institutional infrastructure.

### Design Principles

| Principle | Rationale |
|-----------|-----------|
| **Walk-forward only** | Financial time series demands temporal validation; random splits leak future data |
| **Latency-stratified** | Fast models (< 5ms) for execution; slow models (1–10s) for research — never the reverse |
| **Graceful degradation** | If any model fails, rule-based fallbacks keep the system safe |
| **Explainability by default** | SHAP values for every XGBoost prediction; attention weights for transformers |
| **Cost-aware** | Target < $90/month total ML infrastructure cost through Phase 3 |
| **Reproducible** | Every training run is versioned with data snapshot, config, and metrics |

### Pipeline-at-a-Glance

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        ML PIPELINE — END TO END                          │
│                                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ COLLECT  │→ │ENGINEER  │→ │  TRAIN   │→ │ VALIDATE │→ │  DEPLOY  │  │
│  │ & CLEAN  │  │FEATURES  │  │  MODELS  │  │ (W-F/OOS)│  │  (Serve) │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └────┬─────┘  │
│                                                                 │        │
│  ┌──────────────────────────────────────────────────────────────┘        │
│  │                                                                      │
│  ▼                                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐    │
│  │ MONITOR  │→ │ DETECT   │→ │ RETRAIN  │→ │ VERSION & A/B TEST   │    │
│  │ (metrics)│  │  DRIFT   │  │ (auto)   │  │ (shadow→canary→prod) │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────────────┘    │
│       ▲                                                          │       │
│       └──────────────── CLOSED FEEDBACK LOOP ◄───────────────────┘       │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Pipeline Overview

### 2.1 Model Inventory

The pipeline manages **8 model families** across **4 latency tiers**:

| Model Family | Task | Inference Latency | Count | Retraining Cadence |
|-------------|------|-------------------|-------|---------------------|
| **FinBERT** | Sentiment classification | < 100ms (CPU) | 1 | Weekly (online), Monthly (full) |
| **XGBoost / LightGBM** | Signal classification, confluence | < 10ms | 5–8 | Monthly |
| **LSTM** | Sequential price/vol prediction | < 50ms | 3–5 | Monthly |
| **Transformer** | Multi-timeframe cross-asset | < 200ms | 1–2 | Quarterly |
| **HMM** | Regime detection | < 5ms | 2–3 | Monthly |
| **RL (PPO/DQN/Q-Learn)** | Sizing, TP, execution | < 30ms | 3–5 | Monthly |
| **LLM (DeepSeek/Qwen)** | Fundamental reasoning | 1–5s | 2 | N/A (API) |
| **CNN** | Chart pattern recognition | < 100ms | 1–2 | Quarterly |

### 2.2 Latency Tiers

```
TIER 1: ULTRA-FAST (< 5ms)     — Real-time execution path
  Algorithmic detectors · HMM regime · Rules-based session · Linear regression baseline

TIER 2: FAST (< 50ms)          — Per-candle analysis
  XGBoost/LightGBM · Random Forest · DBSCAN · Small LSTM (< 64 units)

TIER 3: MEDIUM (< 500ms)       — Per-session analysis
  Large LSTM · Transformer · CNN · RL policy inference · FinBERT

TIER 4: SLOW (1–10s)           — Periodic / event-driven
  LLM reasoning · Report generation · Model retraining · RL training episodes
```

### 2.3 Data Flow Summary

```
Sources (17+)          Ingestion          Feature Store         Model Serving
─────────────          ──────────         ─────────────         ─────────────
MT5/Broker     ─┐                      ┌→ Redis (hot)    ───→ Tier 1-2 models
CCXT/Exchange  ─┤→ Adapters → Normalize├→ Redis Streams  ───→ Tier 3 models
News/RSS       ─┤              & Enrich ├→ TimescaleDB    ───→ Tier 4 models
On-chain       ─┤                      └→ Feature Store  ───→ Training pipeline
Alt-data       ─┘                         (pre-computed)
```

---

## 3. Data Collection & Preprocessing Pipeline

### 3.1 Source Adapter Architecture

Every data source has a dedicated adapter implementing a uniform interface. Adapters are isolated, independently restartable, and emit canonical `RawEvent` objects.

```python
class SourceAdapter(ABC):
    """Uniform interface for all data sources."""

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def stream(self) -> AsyncIterator[RawEvent]: ...

    @abstractmethod
    async def health(self) -> SourceHealth: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    rate_limit: RateLimitConfig
    retry: RetryPolicy
```

### 3.2 Source Inventory

| Adapter | Source | Protocol | Data | Frequency | Priority |
|---------|--------|----------|------|-----------|----------|
| `Mt5Adapter` | MT5 (FXPesa) | Python lib | Ticks, OHLCV, DOM, calendar | Real-time tick | P0 |
| `CcxtAdapter` | Binance, Bybit | REST + WebSocket | Ticks, OHLCV, book, trades | Real-time WS | P0 |
| `FundingRateAdapter` | Binance/Bybit Futures | REST | Funding rates, OI | Every 1 min | P1 |
| `DefiLlamaAdapter` | DefiLlama | REST | TVL, stablecoins, yields | Every 5 min | P1 |
| `CoinglassAdapter` | Coinglass | REST/scrape | Liquidation maps, OI | Every 1 min | P1 |
| `EconomicCalendarAdapter` | MQL5 Calendar | MQL5 native | Events, impact levels | Daily + intraday | P1 |
| `NewsRssAdapter` | Reuters, BBC, FT, CoinDesk | RSS | Headlines | Every 15 min | P2 |
| `RedditSentimentAdapter` | Reddit (PRAW) | Reddit API | Post/comment sentiment | Every 15 min | P2 |
| `GoogleTrendsAdapter` | Google Trends | REST | Search interest | Every 6 hours | P3 |
| `LunarCrushAdapter` | LunarCrush | REST | Social dominance | Every 15 min | P3 |
| `FearGreedAdapter` | alternative.me | REST | Fear & Greed Index | Every 1 hour | P3 |
| `GlassnodeAdapter` | Glassnode | REST | Exchange flows, SOPR, MVRV | Every 5 min | P4 |
| `WhaleAlertAdapter` | Whale Alert | REST/WS | Large transaction alerts | Real-time WS | P4 |

### 3.3 Canonical Event Schema

```json
{
  "event_id": "uuid-v7",
  "source": "binance",
  "asset_class": "crypto",
  "event_type": "tick",
  "symbol": "BTC/USDT",
  "timestamp_utc": "2026-07-11T13:45:23.123456Z",
  "ingested_at": "2026-07-11T13:45:23.130000Z",
  "latency_ms": 6.5,
  "schema_version": 1,
  "payload": { ... },
  "metadata": {
    "adapter_version": "0.1.0",
    "checksum": "sha256:abc123..."
  }
}
```

### 3.4 Normalization & Validation Pipeline

```
Raw Event → Schema Validation → Anomaly Detection → Enrichment → Canonical Event
                │                      │                  │
                ▼                      ▼                  ▼
          Reject & Log          Flag & Tag           Add derived fields
          (malformed)           (outlier, gap)       (spread, mid, session)
```

**Normalization rules:**

| Transformation | Rule | Example |
|----------------|------|---------|
| Timestamp | All → UTC, microsecond precision | `1625139923123456` |
| Symbol | Normalize to `{BASE}/{QUOTE}` | `EURUSD` → `EUR/USD` |
| Price | Float64, no rounding at ingestion | `1.08532` |
| Volume | Standardized units (lots forex, base crypto) | `0.01` lots |
| OHLCV | Validate H≥L, H≥max(O,C), L≤min(O,C) | Flag violations |
| Deduplication | UUID v7 from source+timestamp+hash | Idempotent inserts |

**Enrichment fields added during normalization:**
- `spread` = ask - bid
- `mid_price` = (bid + ask) / 2
- `session` = asian | london | new_york | overlap (derived from timestamp)
- `is_news_window` = true if within ±30 min of high-impact event
- `vwap` = rolling volume-weighted average price

### 3.5 Three Data Paths

| Path | Purpose | Technology | Latency | Retention |
|------|---------|------------|---------|-----------|
| **Hot** | Current market state | Redis (in-memory) | < 1ms read | 60s–5min TTL |
| **Warm** | Ordered event log | Redis Streams | < 100ms | 1h–7 days |
| **Cold** | Historical + ML training | TimescaleDB | < 100ms indexed | 90 days–permanent |

### 3.6 Data Quality Pipeline for ML

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ML DATA QUALITY PIPELINE                           │
│                                                                       │
│  1. INGESTION VALIDATION                                             │
│     • OHLCV: H≥L, H≥max(O,C), L≤min(O,C)                          │
│     • Gap detection: Missing candles, exchange outages               │
│     • Timestamp normalization: All to UTC                            │
│     • Deduplication: event_id uniqueness                             │
│                                                                       │
│  2. CLEANING                                                         │
│     • Outlier detection: Z-score > 4 on returns → flag              │
│     • Gap filling: Forward-fill small gaps (< 3 candles)            │
│     • Session boundary alignment                                     │
│     • Split/dividend adjustment (crypto: none needed)               │
│                                                                       │
│  3. FEATURE COMPUTATION                                              │
│     • All technical indicators (vectorized, see §4)                  │
│     • Cross-asset features                                           │
│     • Rolling statistics                                             │
│     • Z-score normalization (rolling 1-year window)                  │
│     • Handle NaN: Forward-fill then drop remaining                  │
│                                                                       │
│  4. LABELING                                                         │
│     • Forward return classification: UP/DOWN/FLAT                    │
│     • Label horizon: 10 bars (configurable per model)               │
│     • Threshold: ±0.5× ATR for UP/DOWN, else FLAT                   │
│     • Purge: Remove labels within 5 bars of major events            │
│                                                                       │
│  5. SPLIT VALIDATION                                                 │
│     • Walk-forward: Train (70%) → Val (15%) → Test (15%)            │
│     • NO future data leakage (strict temporal ordering)              │
│     • Purged cross-validation (5-bar gap between train/test)        │
│     • Distribution shift: KS test between train/test distributions  │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.7 Storage Schema for ML Training Data

```sql
-- Feature store: pre-computed features for model training
CREATE TABLE ml_features (
    time         TIMESTAMPTZ NOT NULL,
    symbol       TEXT NOT NULL,
    timeframe    TEXT NOT NULL,
    feature_set  TEXT NOT NULL,        -- 'technical', 'structure', 'sentiment', 'cross_asset'
    features     JSONB NOT NULL,       -- Flexible key-value feature vector
    label        TEXT,                 -- 'UP', 'DOWN', 'FLAT' (null for inference-only rows)
    label_horizon INTEGER,             -- Bars ahead for label
    split_tag    TEXT                  -- 'train', 'val', 'test', 'purge'
);
SELECT create_hypertable('ml_features', 'time');

-- Training run registry
CREATE TABLE training_runs (
    run_id       UUID PRIMARY KEY,
    model_name   TEXT NOT NULL,
    version      INTEGER NOT NULL,
    started_at   TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    status       TEXT NOT NULL,         -- 'running', 'completed', 'failed'
    config       JSONB NOT NULL,        -- Full hyperparameter config
    data_range   TSTZRANGE NOT NULL,    -- Training data time range
    metrics      JSONB,                 -- Evaluation metrics
    artifact_path TEXT,                 -- Path to model artifacts
    git_commit   TEXT                   -- Code version
);

-- Prediction log (for monitoring)
CREATE TABLE prediction_log (
    time         TIMESTAMPTZ NOT NULL,
    model_name   TEXT NOT NULL,
    version      INTEGER NOT NULL,
    symbol       TEXT NOT NULL,
    prediction   JSONB NOT NULL,        -- Model output
    features     JSONB,                 -- Input features (sampled)
    latency_ms   DOUBLE PRECISION,
    actual       JSONB                  -- Filled in when outcome known
);
SELECT create_hypertable('prediction_log', 'time');
```

---

## 4. Feature Engineering Pipeline

### 4.1 Feature Architecture

Features are organized into **5 groups**, computed in a DAG (directed acyclic graph) to avoid redundant computation:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    FEATURE ENGINEERING DAG                            │
│                                                                       │
│  GROUP 1: RAW PRICE (input to all other groups)                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  OHLCV (5 features) × 4 timeframes (M15, H1, H4, D1)       │    │
│  │  = 20 raw price features per asset                          │    │
│  └──────────────────────────┬──────────────────────────────────┘    │
│                             │                                        │
│           ┌─────────────────┼─────────────────┐                     │
│           ▼                 ▼                 ▼                     │
│  GROUP 2: TECHNICAL    GROUP 3: STRUCTURE   GROUP 4: CONTEXT       │
│  INDICATORS            FEATURES             FEATURES                │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐       │
│  │ RSI (3)      │     │ Swing points │     │ Session      │       │
│  │ MACD (3)     │     │ BOS/CHoCH    │     │ Hour/Day     │       │
│  │ ATR (2)      │     │ OB strength  │     │ Regime       │       │
│  │ ADX (1)      │     │ FVG present  │     │ Event flags  │       │
│  │ Bollinger(3) │     │ S/R score    │     │ Sentiment    │       │
│  │ Stochastic(2)│     │ Liquidity    │     │ Funding rate │       │
│  │ CCI (1)      │     │ Volume ratio │     │ VIX level    │       │
│  │ MFI (1)      │     │              │     │              │       │
│  │ Williams(1)  │     │              │     │              │       │
│  │ OBV (1)      │     │              │     │              │       │
│  │ VWAP (1)     │     │              │     │              │       │
│  │ Ichimoku (5) │     │              │     │              │       │
│  │ Fibonacci (3)│     │              │     │              │       │
│  │ Pivot (3)    │     │              │     │              │       │
│  └──────┬───────┘     └──────┬───────┘     └──────┬───────┘       │
│         │                    │                    │                 │
│         └────────────────────┼────────────────────┘                 │
│                              ▼                                       │
│                     GROUP 5: CROSS-ASSET                             │
│                     ┌──────────────────┐                             │
│                     │ DXY returns      │                             │
│                     │ VIX level/change │                             │
│                     │ Bond yields      │                             │
│                     │ Correlation roll │                             │
│                     │ Lead-lag features│                             │
│                     │ Commodity prices │                             │
│                     └──────────────────┘                             │
│                                                                       │
│  OUTPUT: ~60 features per asset per timeframe                        │
│  TOTAL: ~240 features per asset (4 timeframes)                       │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 Group 2: Technical Indicators

| Category | Indicators | Parameters | Features |
|----------|-----------|------------|----------|
| **Trend** | SMA, EMA | 20, 50, 200 | 6 |
| **Trend** | MACD | 12/26/9 | 3 (line, signal, histogram) |
| **Trend** | ADX | 14 | 1 |
| **Trend** | Ichimoku | 9/26/52 | 5 (tenkan, kijun, senkou A/B, chikou) |
| **Momentum** | RSI | 7, 14, 21 | 3 |
| **Momentum** | Stochastic | 14/3 | 2 (K, D) |
| **Momentum** | CCI | 20 | 1 |
| **Momentum** | MFI | 14 | 1 |
| **Momentum** | Williams %R | 14 | 1 |
| **Volatility** | ATR | 7, 14 | 2 |
| **Volatility** | Bollinger Bands | 20/2 | 3 (upper, lower, %B) |
| **Volume** | OBV | — | 1 |
| **Volume** | VWAP | — | 1 |
| **Levels** | Fibonacci | Auto | 3 (38.2%, 50%, 61.8%) |
| **Levels** | Pivot Points | Daily | 3 (P, S1, R1) |
| **Derived** | MACD histogram, RSI-MACD divergence, BB width, ATR ratio | | 5 |

**Subtotal: ~40 technical indicator features per timeframe**

### 4.3 Group 3: Structure Features

```python
STRUCTURE_FEATURES = {
    # Swing detection
    'swing_high_distance': float,     # Bars since last swing high
    'swing_low_distance': float,      # Bars since last swing low
    'swing_high_value': float,        # Price of last swing high
    'swing_low_value': float,         # Price of last swing low

    # Market structure (BOS/CHoCH)
    'bos_type': int,                  # 0=none, 1=bullish, 2=bearish
    'bos_strength': float,            # 0-1 based on impulse size
    'choch_type': int,                # 0=none, 1=bullish, 2=bearish
    'choch_strength': float,          # 0-1

    # Order blocks
    'ob_type': int,                   # 0=none, 1=bullish, 2=bearish
    'ob_strength': float,             # 0-1
    'ob_age': int,                    # Bars since OB formed
    'ob_distance_atr': float,         # Distance to OB in ATR multiples

    # Fair value gaps
    'fvg_present': int,               # 0/1
    'fvg_size_atr': float,            # Gap size in ATR multiples
    'fvg_filled_pct': float,          # 0-1, how much filled

    # Support/Resistance
    'sr_score': float,                # 0-100 composite S/R quality
    'sr_touch_count': int,            # Number of touches
    'sr_recency': int,                # Bars since last touch
    'sr_distance_atr': float,         # Distance to nearest S/R

    # Liquidity
    'liquidity_above': float,         # Liquidity pool size above
    'liquidity_below': float,         # Liquidity pool size below
    'sweep_detected': int,            # 0/1 recent sweep
    'order_flow_delta': float,        # Buy/sell volume imbalance

    # Volume
    'volume_ratio_20_50': float,      # 20-period vol / 50-period vol
    'volume_spike': int,              # 0/1 if volume > 2x average
}
# ~25 structure features
```

### 4.4 Group 4: Context Features

```python
CONTEXT_FEATURES = {
    # Session
    'session': int,                   # 0=asian, 1=london, 2=ny, 3=overlap
    'hour_of_day_sin': float,         # Cyclical encoding
    'hour_of_day_cos': float,
    'day_of_week_sin': float,
    'day_of_week_cos': float,

    # Regime (from HMM)
    'regime': int,                    # 0=bull, 1=bear, 2=range
    'regime_confidence': float,       # 0-1
    'regime_persistence_days': float, # Expected days remaining

    # Sentiment
    'sentiment_score': float,         # -1 to +1 (FinBERT aggregated)
    'sentiment_momentum': float,      # Rate of change of sentiment

    # Events
    'event_risk_score': float,        # 0-1 (proximity + impact)
    'high_impact_event_4h': int,      # 0/1
    'nfp_today': int,                 # 0/1
    'fomc_today': int,                # 0/1

    # Volatility context
    'vix_level': float,               # Current VIX
    'vix_change_1d': float,           # VIX daily change
    'realized_vol_20d': float,        # 20-day realized volatility
    'atr_percentile': float,          # Current ATR vs 1-year range

    # On-chain (crypto only)
    'funding_rate': float,
    'open_interest_change': float,
    'long_short_ratio': float,
}
# ~25 context features
```

### 4.5 Group 5: Cross-Asset Features

```python
CROSS_ASSET_FEATURES = {
    # DXY (US Dollar Index)
    'dxy_return_1h': float,
    'dxy_return_4h': float,
    'dxy_rsi_14': float,

    # Bond yields
    'us10y_yield': float,
    'us10y_change_1d': float,
    'us2y_yield': float,
    'yield_curve_10y_2y': float,      # Spread

    # Equities
    'sp500_return_1d': float,
    'sp500_return_1h': float,

    # Commodities
    'gold_return_1d': float,          # AUD correlation
    'oil_return_1d': float,           # CAD correlation

    # Correlations (rolling)
    'corr_dxy_20d': float,            # 20-day correlation with DXY
    'corr_sp500_20d': float,          # 20-day correlation with S&P 500
    'corr_btc_20d': float,            # 20-day correlation with BTC

    # Lead-lag
    'dxy_lead_2_return': float,       # DXY return 2 bars ago (if DXY leads)
}
# ~15 cross-asset features
```

### 4.6 Feature Computation Pipeline

```python
class FeaturePipeline:
    """
    DAG-based feature computation. Computes features in dependency order,
    caching intermediate results to avoid redundant computation.
    """

    def __init__(self, feature_store: FeatureStore):
        self.store = feature_store
        self.dag = FeatureDAG()

        # Register feature groups with dependencies
        self.dag.register('raw_price', deps=[], compute=self._compute_raw)
        self.dag.register('technical', deps=['raw_price'], compute=self._compute_technical)
        self.dag.register('structure', deps=['raw_price'], compute=self._compute_structure)
        self.dag.register('context', deps=['raw_price'], compute=self._compute_context)
        self.dag.register('cross_asset', deps=['raw_price'], compute=self._compute_cross_asset)
        self.dag.register('lag_rolling', deps=['raw_price'], compute=self._compute_lag_rolling)

    async def compute_all(self, symbol: str, timeframe: str,
                          lookback: int = 500) -> FeatureVector:
        """Compute all features for a symbol/timeframe pair."""

        # Check cache first
        cache_key = f"features:{symbol}:{timeframe}"
        cached = await self.store.get(cache_key)
        if cached and not self._is_stale(cached, timeframe):
            return cached

        # Fetch raw data
        bars = await self.store.get_bars(symbol, timeframe, lookback)

        # Execute DAG
        results = {}
        for group_name in self.dag.topological_sort():
            results[group_name] = await self.dag.compute(
                group_name, bars=bars, results=results
            )

        # Flatten into single feature vector
        feature_vector = self._flatten(results)

        # Normalize (z-score with rolling 1-year window)
        normalized = self._normalize_rolling(feature_vector, window=252*24)

        # Cache
        ttl = self._timeframe_ttl(timeframe)
        await self.store.set(cache_key, normalized, ttl)

        return normalized

    def _compute_technical(self, bars: DataFrame, results: dict) -> dict:
        """Compute all technical indicators using vectorized operations."""
        close = bars['close']
        high = bars['high']
        low = bars['low']
        volume = bars['volume']

        features = {}

        # RSI (multiple periods)
        for period in [7, 14, 21]:
            features[f'rsi_{period}'] = ta.rsi(close, period)

        # MACD
        macd, signal, hist = ta.macd(close, 12, 26, 9)
        features['macd'] = macd
        features['macd_signal'] = signal
        features['macd_hist'] = hist

        # ATR
        for period in [7, 14]:
            features[f'atr_{period}'] = ta.atr(high, low, close, period)

        # ADX
        features['adx'] = ta.adx(high, low, close, 14)

        # Bollinger Bands
        upper, middle, lower = ta.bbands(close, 20, 2)
        features['bb_upper'] = upper
        features['bb_lower'] = lower
        features['bb_pct'] = (close - lower) / (upper - lower)

        # Stochastic
        k, d = ta.stoch(high, low, close, 14, 3)
        features['stoch_k'] = k
        features['stoch_d'] = d

        # Additional indicators...
        features['cci'] = ta.cci(high, low, close, 20)
        features['mfi'] = ta.mfi(high, low, close, volume, 14)
        features['williams_r'] = ta.williams_r(high, low, close, 14)
        features['obv'] = ta.obv(close, volume)
        features['vwap'] = ta.vwap(high, low, close, volume)
        features['adx'] = ta.adx(high, low, close, 14)

        return features
```

### 4.7 Feature Selection Pipeline

Features are evaluated monthly to remove noise and reduce dimensionality:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    FEATURE SELECTION PIPELINE                         │
│                                                                       │
│  STEP 1: Correlation Filter                                          │
│  • Remove features with > 0.95 pairwise correlation                 │
│  • Keep the one with higher mutual information with target          │
│  • Reduces ~240 features to ~120                                     │
│                                                                       │
│  STEP 2: Mutual Information Ranking                                  │
│  • Rank features by MI with forward return classification           │
│  • Keep top 80 features                                              │
│                                                                       │
│  STEP 3: SHAP-Based Selection (model-specific)                       │
│  • Train XGBoost on full feature set                                 │
│  • Compute mean |SHAP| per feature                                   │
│  • Keep features with mean |SHAP| > threshold (adaptive)            │
│  • Result: 40-60 features per model                                  │
│                                                                       │
│  STEP 4: Boruta Validation                                           │
│  • Create shadow features (shuffled copies)                          │
│  • Train Random Forest                                               │
│  • Keep features that beat their shadow significantly               │
│  • Final: 30-50 features per model                                   │
│                                                                       │
│  STEP 5: Time-Varying Importance Tracking                            │
│  • Track feature importance weekly                                   │
│  • Alert if any top-10 feature drops below threshold                │
│  • Triggers feature pipeline review                                  │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.8 Feature Store Design

```
┌─────────────────────────────────────────────────────────────────────┐
│                    FEATURE STORE                                       │
│                                                                       │
│  HOT (Redis):                                                         │
│  • Latest feature vector per symbol/timeframe                        │
│  • Updated on every new candle                                       │
│  • TTL: aligned with candle timeframe                                │
│  • Used by: All inference-time models                                │
│                                                                       │
│  WARM (Redis Streams):                                               │
│  • Feature vector history (last 7 days)                              │
│  • Ordered by time, replayable                                       │
│  • Used by: Training pipeline (recent data)                          │
│                                                                       │
│  COLD (TimescaleDB ml_features table):                               │
│  • Full historical feature vectors                                   │
│  • Compressed, partitioned by month                                  │
│  • Used by: Backtesting, full model retraining                       │
│                                                                       │
│  COMPUTED ARTIFACTS (local filesystem):                              │
│  • Scaler parameters (mean, std per feature)                         │
│  • Feature selection masks                                           │
│  • Correlation matrices                                              │
│  • Versioned with model artifacts                                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 5. Model Training Pipeline

### 5.1 Training Infrastructure

```
┌─────────────────────────────────────────────────────────────────────┐
│                    TRAINING INFRASTRUCTURE                             │
│                                                                       │
│  PHASE 1-3 (CPU only, single machine):                               │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  • scikit-learn for Random Forest, DBSCAN, Linear models    │    │
│  │  • XGBoost / LightGBM native for gradient boosted trees     │    │
│  │  • hmmlearn for Hidden Markov Models                         │    │
│  │  • PyTorch (CPU) for LSTM, Transformer, FinBERT             │    │
│  │  • Stable-Baselines3 for PPO, DQN                           │    │
│  │  • ONNX Runtime for inference optimization                  │    │
│  │  • All training runs on single 4-core machine               │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  PHASE 4+ (GPU optional, distributed):                               │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  • Spot GPU instances (T4/A10G) for neural network training  │    │
│  │  • Ray for distributed training of ensemble models           │    │
│  │  • Weights & Biases for experiment tracking                  │    │
│  │  • DVC for data versioning                                   │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.2 Training Data Preparation

```python
class TrainingDataBuilder:
    """
    Builds training datasets from the feature store.
    Handles temporal splitting, purging, and class balancing.
    """

    def build(self, model_name: str, symbol: str, timeframe: str,
              lookback_years: int = 3) -> TrainingDataset:
        """
        Build a training dataset with proper temporal splitting.

        Returns:
            TrainingDataset with train, val, test splits and metadata
        """
        # 1. Fetch historical features
        features = self.feature_store.get_historical(
            symbol, timeframe, lookback_years
        )

        # 2. Generate labels
        labels = self._generate_labels(
            features, horizon=10, threshold_atr=0.5
        )

        # 3. Remove purge buffer (5 bars around major events)
        features, labels = self._purge_events(
            features, labels, buffer=5
        )

        # 4. Walk-forward split
        splits = self._walk_forward_split(
            features, labels,
            train_ratio=0.70,
            val_ratio=0.15,
            test_ratio=0.15,
            gap=5  # Purge gap between splits
        )

        # 5. Class balancing (for classification models)
        if self._is_classification(model_name):
            splits.train = self._balance_classes(
                splits.train, method='smote'
            )

        # 6. Feature selection (model-specific)
        selected_features = self._select_features(
            model_name, splits.train
        )
        splits = splits.select_features(selected_features)

        # 7. Scaling (fit on train, transform all)
        scaler = self._fit_scaler(splits.train)
        splits = splits.apply_scaler(scaler)

        return TrainingDataset(
            splits=splits,
            scaler=scaler,
            feature_names=selected_features,
            label_config={'horizon': 10, 'threshold_atr': 0.5},
            metadata={
                'symbol': symbol,
                'timeframe': timeframe,
                'lookback_years': lookback_years,
                'total_samples': len(features),
                'class_distribution': self._class_counts(labels)
            }
        )
```

### 5.3 Walk-Forward Validation Strategy

```
┌─────────────────────────────────────────────────────────────────────┐
│                    WALK-FORWARD VALIDATION                            │
│                                                                       │
│  Timeline:                                                            │
│  ├───────────────┤ train (252 days)                                  │
│                   ├───┤ test (63 days)                                │
│                       ├───────────────┤ train (252 days)              │
│                                       ├───┤ test (63 days)           │
│                                           ├───────────────┤ train    │
│                                                           ├───┤ test │
│                                                                       │
│  Window: 252 trading days train, 63 trading days test               │
│  Step: 21 trading days (monthly retrain)                             │
│  Gap: 5 bars between train end and test start (purge)               │
│  Minimum train samples: 50,000                                       │
│                                                                       │
│  Result: Multiple (train, test) pairs                                │
│  Performance: Mean ± std across all test windows                     │
│  Stability: Variance of performance across windows                   │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.4 Model-Specific Training Configurations

#### XGBoost / LightGBM (Signal Classification)

```yaml
# XGBoost Confluence Scorer
model: xgboost
task: binary_classification  # profitable trade or not
target: forward_return_class  # UP/DOWN → binary after direction filter

hyperparameters:
  n_estimators: 500
  max_depth: 6
  learning_rate: 0.05
  subsample: 0.8
  colsample_bytree: 0.8
  min_child_weight: 5
  reg_alpha: 0.1           # L1 regularization
  reg_lambda: 1.0          # L2 regularization
  scale_pos_weight: auto   # Handle class imbalance

tuning:
  method: bayesian         # Optuna Bayesian optimization
  n_trials: 100
  metric: auc_pr           # Area under precision-recall curve
  cv: purged_kfold         # 5-fold with 5-bar purge gap

custom_objective: null      # Default logloss; switch to sharpe_ratio for direct optimization

evaluation:
  primary: auc_roc
  secondary: [precision, recall, f1, sharpe_ratio_backtest]
  minimum_auc: 0.72
```

#### LSTM (Sequential Price Prediction)

```yaml
# LSTM Standard (H1 timeframe)
model: lstm
task: multi_output  # direction (cls) + return (reg) + volatility (reg)

architecture:
  input_dim: 60            # 60 features
  sequence_length: 100     # 100 bars lookback
  hidden_units: [128, 64]  # Two LSTM layers
  attention: self_attention
  dropout: [0.3, 0.2]
  batch_norm: true

  output_heads:
    direction: {type: softmax, classes: 3, loss_weight: 0.4}
    return: {type: linear, loss_weight: 0.3}
    volatility: {type: softplus, loss_weight: 0.3}

training:
  optimizer: AdamW
  learning_rate: 1e-3
  weight_decay: 1e-4
  batch_size: 256
  epochs: 100
  early_stopping_patience: 15
  scheduler: CosineAnnealingWarmRestarts
  gradient_clip: 1.0

  class_weights: {UP: 1.2, DOWN: 1.2, FLAT: 0.6}

walk_forward:
  train_window: 252 days
  test_window: 63 days
  step: 21 days
```

#### FinBERT (Sentiment Analysis)

```yaml
# FinBERT fine-tuned for forex/crypto sentiment
model: finbert
base_model: "ProsusAI/finbert"
task: text_classification  # Bullish/Bearish/Neutral

training_data:
  - Financial PhraseBank: 4840 labeled sentences
  - Forex Factory headlines: 5000+ labeled articles
  - Central bank statements: 500+ documents
  - Reuters forex headlines: labeled by 1h price reaction

fine_tuning:
  epochs: 3
  learning_rate: 2e-5
  batch_size: 16
  max_length: 512
  warmup_steps: 500
  weight_decay: 0.01

evaluation:
  accuracy_target: 0.85
  f1_macro_target: 0.83
  calibration_target: brier_score < 0.15

retraining:
  weekly: online_learning(100-200_new_samples)
  monthly: full_retrain(expanded_corpus)
```

#### Hidden Markov Model (Regime Detection)

```yaml
# HMM Regime Detector
model: hmm
library: hmmlearn
task: sequence_labeling  # Regime classification

states: 3  # Bull Trend, Bear Trend, Range

observation_features:
  - return_20d           # 20-period return
  - realized_vol_20d     # 20-day realized volatility
  - atr_ratio_14_50      # ATR(14) / ATR(50)
  - adx_14               # Trend strength
  - volume_ratio_20_50   # Volume ratio

training:
  algorithm: Baum-Welch
  n_iter: 100
  tol: 1e-4
  init_params: kmeans     # Initialize with K-Means
  covariance_type: full

validation:
  metric: log_likelihood
  stability_check: transition_matrix_entropy
  regime_consistency: 70%+ agreement with rules-based detector

retraining:
  monthly: full_retrain
  trigger: log_likelihood_drop > 20%
```

#### PPO (Position Sizing)

```yaml
# PPO Position Sizing Agent
model: ppo
library: stable_baselines3
task: continuous_control

environment:
  observation_space: 12  # confluence_score, regime, vol, recent_wr, etc.
  action_space: [0.0, 2.0]  # Position size multiplier (continuous)
  reward: sharpe_adjusted_r_multiple

hyperparameters:
  learning_rate: 3e-4
  n_steps: 2048
  batch_size: 64
  n_epochs: 10
  gamma: 0.99
  gae_lambda: 0.95
  clip_range: 0.2
  ent_coef: 0.01
  vf_coef: 0.5
  max_grad_norm: 0.5
  policy_net: [64, 64]
  value_net: [64, 64]

training_phases:
  phase_1:
    name: offline_backtest
    timesteps: 1_000_000
    data: 3+ years historical
  phase_2:
    name: simulator
    timesteps: 500_000
    data: GAN-generated synthetic
  phase_3:
    name: shadow_live
    timesteps: 100_000
    data: live market (observe only)
  phase_4:
    name: gradual_live
    traffic_pct: [10, 25, 50, 100]
    monitoring: weekly
```

### 5.5 Hyperparameter Tuning Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                    HYPERPARAMETER TUNING                              │
│                                                                       │
│  METHOD: Bayesian Optimization (Optuna)                              │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Search Space Definition                                     │    │
│  │  • XGBoost: n_estimators [100,1000], max_depth [3,10],      │    │
│  │    learning_rate [0.01,0.3], subsample [0.5,1.0], etc.       │    │
│  │  • LSTM: hidden_units [32,256], layers [1,3], dropout        │    │
│  │    [0.1,0.5], lr [1e-4,1e-2]                                │    │
│  │  • HMM: n_states [2,7], covariance_type [full, diag]        │    │
│  └──────────────────────────┬──────────────────────────────────┘    │
│                             │                                        │
│  ┌──────────────────────────▼──────────────────────────────────┐    │
│  │  Optimization Loop                                           │    │
│  │  • n_trials: 100 (XGBoost), 50 (LSTM), 20 (HMM)            │    │
│  │  • Objective: Purged walk-forward CV metric                  │    │
│  │  • Pruning: MedianPruner (early stop bad trials)             │    │
│  │  • Parallelism: 4 trials concurrently (CPU)                  │    │
│  └──────────────────────────┬──────────────────────────────────┘    │
│                             │                                        │
│  ┌──────────────────────────▼──────────────────────────────────┐    │
│  │  Validation                                                  │    │
│  │  • Best params tested on held-out OOS data                   │    │
│  │  • Must beat default params by ≥ 2% on primary metric        │    │
│  │  • Stability check: performance variance across folds < 5%   │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  SCHEDULE:                                                            │
│  • Initial: Full hyperparameter search                               │
│  • Monthly: Fine-tune around current best (narrower search space)    │
│  • On demand: After significant data distribution shift              │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.6 Training Run Tracking

```python
class TrainingRunTracker:
    """
    Tracks every training run with full reproducibility.
    Stores: config, data snapshot, metrics, artifacts.
    """

    def start_run(self, model_name: str, config: dict) -> str:
        run_id = str(uuid.uuid4())
        self.db.insert('training_runs', {
            'run_id': run_id,
            'model_name': model_name,
            'version': self._next_version(model_name),
            'started_at': datetime.utcnow(),
            'status': 'running',
            'config': config,
            'data_range': config['data_range'],
            'git_commit': self._get_git_commit(),
        })
        return run_id

    def log_metrics(self, run_id: str, metrics: dict):
        self.db.update('training_runs', run_id, {
            'metrics': metrics
        })

    def complete_run(self, run_id: str, artifact_path: str):
        self.db.update('training_runs', run_id, {
            'status': 'completed',
            'completed_at': datetime.utcnow(),
            'artifact_path': artifact_path
        })

    def get_best_run(self, model_name: str, metric: str) -> dict:
        return self.db.query(
            "SELECT * FROM training_runs "
            "WHERE model_name = %s AND status = 'completed' "
            "ORDER BY metrics->>%s DESC LIMIT 1",
            (model_name, metric)
        )
```

---

## 6. Model Validation Pipeline

### 6.1 Validation Framework

```
┌─────────────────────────────────────────────────────────────────────┐
│                    MODEL VALIDATION PIPELINE                          │
│                                                                       │
│  STAGE 1: STATISTICAL VALIDATION                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Walk-Forward Cross-Validation                               │    │
│  │  • Multiple (train, test) pairs from temporal splits         │    │
│  │  • Report: mean ± std of metrics across folds                │    │
│  │  • Pass criteria: consistent performance across all folds    │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  STAGE 2: OUT-OF-SAMPLE TESTING                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Hold-Out OOS Test                                           │    │
│  │  • Most recent 15% of data, NEVER used in training           │    │
│  │  • Final "real world" test before deployment                 │    │
│  │  • Pass criteria: metrics within 10% of CV mean              │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  STAGE 3: BACKTEST VALIDATION                                        │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Strategy-Level Backtest                                     │    │
│  │  • Run model through full backtester with realistic costs    │    │
│  │  • Account for: spread, slippage, swap, commission           │    │
│  │  • Metrics: Sharpe, max DD, win rate, profit factor          │    │
│  │  • Pass criteria: Sharpe > 1.0, max DD < 20%                │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  STAGE 4: ROBUSTNESS TESTING                                         │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Stress Tests                                                │    │
│  │  • Test on synthetic crisis scenarios (GAN-generated)        │    │
│  │  • Test on different instruments (cross-pair generalization) │    │
│  │  • Test on different timeframes                              │    │
│  │  • Parameter sensitivity analysis (±10% on each param)       │    │
│  │  • Pass criteria: No catastrophic failure in any scenario    │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  STAGE 5: COMPARATOR TESTING                                         │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  A/B vs Current Production Model                             │    │
│  │  • Run new model in shadow mode alongside production         │    │
│  │  • Compare: accuracy, latency, edge cases                    │    │
│  │  • Pass criteria: Match or exceed production metrics         │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

### 6.2 Validation Metrics by Model Type

| Model Type | Primary Metrics | Secondary Metrics | Minimum Thresholds |
|-----------|----------------|-------------------|-------------------|
| **XGBoost (classification)** | AUC-ROC, AUC-PR | Precision, Recall, F1, Brier score | AUC-ROC > 0.72 |
| **LSTM (direction)** | Direction accuracy | Calibration error, confidence distribution | Accuracy > 55% |
| **LSTM (return)** | RMSE, MAE | Directional accuracy, R² | RMSE < baseline |
| **FinBERT** | Accuracy, F1 (macro) | Brier score, per-class F1 | Accuracy > 80% |
| **HMM** | Log-likelihood | State accuracy (labeled subset), transition entropy | Log-LL stable |
| **PPO** | Sharpe ratio vs rules | Max DD, win rate, avg R-multiple | Sharpe +5% vs rules |
| **DQN** | Avg R-multiple improvement | Win rate, partial close efficiency | +0.1R per trade |
| **Transformer** | Multi-task loss | Cross-asset generalization | Loss < LSTM baseline |

### 6.3 Purged Walk-Forward CV Implementation

```python
class PurgedWalkForwardCV:
    """
    Walk-forward cross-validation with purge gap.
    Prevents information leakage from autocorrelated financial data.
    """

    def __init__(self, train_window: int = 252*24,  # 252 days in H1 bars
                 test_window: int = 63*24,
                 step: int = 21*24,
                 purge_bars: int = 5):
        self.train_window = train_window
        self.test_window = test_window
        self.step = step
        self.purge_bars = purge_bars

    def split(self, X: np.ndarray, y: np.ndarray):
        """Generate (train_idx, test_idx) pairs."""
        n = len(X)
        start = 0

        while start + self.train_window + self.purge_bars + self.test_window <= n:
            train_end = start + self.train_window
            test_start = train_end + self.purge_bars  # Purge gap
            test_end = test_start + self.test_window

            train_idx = np.arange(start, train_end)
            test_idx = np.arange(test_start, test_end)

            yield train_idx, test_idx

            start += self.step

    def evaluate(self, model, X, y, metric_fn) -> dict:
        """Run full walk-forward evaluation."""
        scores = []

        for fold, (train_idx, test_idx) in enumerate(self.split(X, y)):
            X_train, y_train = X[train_idx], y[train_idx]
            X_test, y_test = X[test_idx], y[test_idx]

            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)
            score = metric_fn(y_test, y_pred)
            scores.append(score)

        return {
            'mean': np.mean(scores),
            'std': np.std(scores),
            'min': np.min(scores),
            'max': np.max(scores),
            'n_folds': len(scores),
            'scores': scores
        }
```

### 6.4 Combinatorial Purged CV (CPCV) for Strategy Validation

```python
class CombinatorialPurgedCV:
    """
    Marcos López de Prado's CPCV method.
    Generates multiple backtest paths to reveal strategy performance variance.
    """

    def __init__(self, n_groups: int = 10, n_test_groups: int = 2,
                 purge_bars: int = 5):
        self.n_groups = n_groups
        self.n_test_groups = n_test_groups
        self.purge_bars = purge_bars

    def split(self, X: np.ndarray):
        """Generate all C(n_groups, n_test_groups) combinations."""
        n = len(X)
        group_size = n // self.n_groups
        groups = [
            np.arange(i * group_size, (i + 1) * group_size)
            for i in range(self.n_groups)
        ]

        for test_group_ids in combinations(range(self.n_groups), self.n_test_groups):
            test_idx = np.concatenate([groups[i] for i in test_group_ids])
            train_idx = np.concatenate([
                groups[i] for i in range(self.n_groups)
                if i not in test_group_ids
            ])

            # Apply purge around test boundaries
            train_idx = self._apply_purge(train_idx, test_idx)

            yield train_idx, test_idx

    def backtest_paths(self, strategy, X, y) -> dict:
        """Generate multiple backtest paths and compute performance distribution."""
        returns_per_path = []

        for train_idx, test_idx in self.split(X):
            strategy.fit(X[train_idx], y[train_idx])
            returns = strategy.backtest(X[test_idx], y[test_idx])
            returns_per_path.append(returns)

        return {
            'mean_sharpe': np.mean([r.sharpe for r in returns_per_path]),
            'std_sharpe': np.std([r.sharpe for r in returns_per_path]),
            'mean_max_dd': np.mean([r.max_drawdown for r in returns_per_path]),
            'worst_path_sharpe': np.min([r.sharpe for r in returns_per_path]),
            'n_paths': len(returns_per_path)
        }
```

### 6.5 Out-of-Sample Testing Protocol

```
┌─────────────────────────────────────────────────────────────────────┐
│                    OUT-OF-SAMPLE PROTOCOL                             │
│                                                                       │
│  DATA ALLOCATION (strict, never violated):                           │
│                                                                       │
│  ├──────────────── 70% ────────────────┤── 15% ──┤── 15% ──┤       │
│  │         TRAINING (walk-forward)      │   VAL   │OOS TEST │       │
│  │                                      │(tuning) │(final)  │       │
│                                                                       │
│  • Training: Walk-forward CV (multiple folds with step)             │
│  • Validation: Hyperparameter tuning, model selection               │
│  • OOS Test: FINAL evaluation. Used ONCE. Never peeked.             │
│                                                                       │
│  OOS TEST PROTOCOL:                                                  │
│  1. Train final model on full training + validation data            │
│  2. Run predictions on OOS test set                                  │
│  3. Compute all metrics                                              │
│  4. Compare to CV metrics:                                           │
│     • OOS metric within 10% of CV mean → PASS                       │
│     • OOS metric 10-20% below CV mean → INVESTIGATE                 │
│     • OOS metric > 20% below CV mean → FAIL (overfitting)           │
│  5. Run backtest on OOS period with realistic costs                 │
│  6. Generate SHAP explanations for OOS predictions                  │
│  7. Human review of edge cases                                       │
│                                                                       │
│  RULE: OOS data is sacred. If we peek at it, we must hold out       │
│  a new OOS portion before deployment.                                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 7. Model Serving Architecture

### 7.1 Inference Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                    MODEL SERVING ARCHITECTURE                         │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  MODEL REGISTRY                                              │    │
│  │  /models/{model_name}/v{version}/                            │    │
│  │  ├── model.onnx          # Serialized model                  │    │
│  │  ├── model.pkl           # Original Python model             │    │
│  │  ├── metadata.json       # Training date, metrics, config    │    │
│  │  ├── feature_list.json   # Ordered feature names             │    │
│  │  ├── scaler.pkl          # Feature scaler                    │    │
│  │  └── evaluation.md       # Performance report                │    │
│  │  production -> vN/       # Symlink to active version         │    │
│  └──────────────────────────┬──────────────────────────────────┘    │
│                             │                                        │
│  ┌──────────────────────────▼──────────────────────────────────┐    │
│  │  INFERENCE RUNTIME                                           │    │
│  │                                                              │    │
│  │  ┌─────────────────────────────────────────────────────┐    │    │
│  │  │  ONNX Runtime (CPU) — Tier 1-2 models                │    │    │
│  │  │  • XGBoost/LightGBM classifiers                      │    │    │
│  │  │  • Small LSTM (< 64 units)                            │    │    │
│  │  │  • HMM regime detector                                │    │    │
│  │  │  • Latency: < 10ms per inference                     │    │    │
│  │  └─────────────────────────────────────────────────────┘    │    │
│  │                                                              │    │
│  │  ┌─────────────────────────────────────────────────────┐    │    │
│  │  │  PyTorch (CPU/GPU) — Tier 3 models                   │    │    │
│  │  │  • FinBERT sentiment model                            │    │    │
│  │  │  • Transformer multi-TF model                         │    │    │
│  │  │  • CNN chart pattern model                            │    │    │
│  │  │  • Latency: 20–200ms per inference                   │    │    │
│  │  └─────────────────────────────────────────────────────┘    │    │
│  │                                                              │    │
│  │  ┌─────────────────────────────────────────────────────┐    │    │
│  │  │  RL Policy Network — Tier 2-3 models                 │    │    │
│  │  │  • PPO position sizing policy                        │    │    │
│  │  │  • DQN take-profit policy                            │    │    │
│  │  │  • Q-table for execution (in-memory dict)            │    │    │
│  │  │  • Latency: < 5ms (policy forward pass)              │    │    │
│  │  └─────────────────────────────────────────────────────┘    │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  FEATURE CACHE (Redis)                                       │    │
│  │  • Pre-computed feature vectors per symbol/timeframe         │    │
│  │  • Updated on every new candle                               │    │
│  │  • All models read from cache (no redundant computation)     │    │
│  │  • TTL aligned with candle timeframe                         │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  LLM CLIENT                                                  │    │
│  │  • API client for DeepSeek/Qwen (cloud-hosted)               │    │
│  │  • Local fallback: Ollama (self-hosted Qwen-2.5-7B)          │    │
│  │  • Retry: exponential backoff, max 3 retries                 │    │
│  │  • Rate limiting: 10 requests/minute                         │    │
│  │  • Response caching: identical queries cached 1 hour         │    │
│  └──────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

### 7.2 Model Manager (Startup & Lifecycle)

```python
class ModelManager:
    """
    Manages model loading, caching, and lifecycle.
    Models loaded once at startup and cached in memory.
    """

    def __init__(self):
        self.models = {}
        self.feature_store = RedisFeatureStore()
        self.monitor = ModelMonitor()

    async def load_all_models(self):
        """Load all models at startup (parallel where possible)."""
        await asyncio.gather(
            self._load_onnx('xgboost_confluence', 'models/xgboost_confluence/production/model.onnx'),
            self._load_onnx('xgboost_sweep', 'models/xgboost_sweep/production/model.onnx'),
            self._load_onnx('xgboost_smc', 'models/xgboost_smc/production/model.onnx'),
            self._load_onnx('xgboost_rsi', 'models/xgboost_rsi/production/model.onnx'),
            self._load_onnx('xgboost_sr', 'models/xgboost_sr/production/model.onnx'),
            self._load_onnx('lstm_standard', 'models/lstm_standard/production/model.onnx'),
            self._load_onnx('lstm_vol', 'models/lstm_vol/production/model.onnx'),
            self._load_pytorch('finbert', 'ProsusAI/finbert'),
            self._load_hmm('regime_hmm', 'models/regime_hmm/production/model.pkl'),
            self._load_rl('ppo_sizing', 'models/ppo_sizing/production/model.pkl'),
            self._load_rl('dqn_tp', 'models/dqn_tp/production/model.pkl'),
        )
        logger.info(f"Loaded {len(self.models)} models")

    async def predict(self, model_name: str, features: dict) -> dict:
        """Run inference with caching, timeout, and monitoring."""
        model = self.models[model_name]

        # Check feature cache
        cache_key = f"{model_name}:{hash(str(features))}"
        cached = await self.feature_store.get(cache_key)
        if cached:
            return cached

        # Run inference with timeout
        start = time.time()
        try:
            result = await asyncio.wait_for(
                model.predict(features),
                timeout=self._get_timeout(model_name)
            )
        except asyncio.TimeoutError:
            result = self._fallback(model_name)
            await self.monitor.log_timeout(model_name)
            return result

        latency_ms = (time.time() - start) * 1000

        # Cache result
        ttl = self._get_cache_ttl(model_name)
        await self.feature_store.set(cache_key, result, ttl)

        # Log latency
        await self.monitor.log_latency(model_name, latency_ms)

        return result

    def _fallback(self, model_name: str) -> dict:
        """Rule-based fallback when model fails."""
        fallbacks = {
            'xgboost_confluence': {'score': 0, 'confidence': 0, 'fallback': True},
            'hmm_regime': {'regime': 'UNCERTAIN', 'confidence': 0, 'fallback': True},
            'finbert': {'sentiment': 'NEUTRAL', 'confidence': 0, 'fallback': True},
            'lstm_standard': {'direction': 'NEUTRAL', 'confidence': 0, 'fallback': True},
        }
        return fallbacks.get(model_name, {'error': 'no_fallback'})
```

### 7.3 Inference Optimization

```
┌─────────────────────────────────────────────────────────────────────┐
│                    INFERENCE OPTIMIZATION                             │
│                                                                       │
│  1. ONNX EXPORT                                                      │
│     • XGBoost → ONNX: 2-5× faster than native predict()             │
│     • LSTM → ONNX: 3-4× faster on CPU                               │
│     • Tool: skl2onnx (sklearn), torch.onnx.export (PyTorch)        │
│                                                                       │
│  2. QUANTIZATION (Phase 4+)                                          │
│     • FinBERT: Dynamic quantization (INT8) → 2× faster, < 1% acc loss│
│     • LSTM: FP16 inference on GPU → 2× throughput                   │
│     • XGBoost: Already optimized (histogram method)                  │
│                                                                       │
│  3. BATCHING                                                         │
│     • FinBERT: Batch 16-32 articles per inference call              │
│     • XGBoost: Vectorized predict on DataFrame (all rows at once)   │
│     • LSTM: Process all instruments in single batch                 │
│                                                                       │
│  4. CACHING STRATEGY                                                 │
│     • Feature vectors: Cache per candle close (invalidated on new bar)│
│     • Model predictions: Cache with model-specific TTL              │
│     • LLM responses: Cache identical queries for 1 hour             │
│     • Hit rate target: > 80% for Tier 1-2 models                   │
│                                                                       │
│  5. MODEL PRUNING                                                    │
│     • XGBoost: Limit to 200 trees (vs 500) if latency budget tight │
│     • LSTM: Reduce hidden units for Tier 2 variants                 │
│     • Decision: Latency-accuracy tradeoff per model                 │
└─────────────────────────────────────────────────────────────────────┘
```

### 7.4 Performance Requirements

| Metric | Target | Measurement |
|--------|--------|-------------|
| **P99 Latency (Tier 1)** | < 5ms | Algorithmic + HMM |
| **P99 Latency (Tier 2)** | < 50ms | XGBoost + small LSTM |
| **P99 Latency (Tier 3)** | < 500ms | FinBERT + Transformer + RL |
| **P99 Latency (Tier 4)** | < 10s | LLM reasoning |
| **Throughput** | 1000 predictions/sec | All models combined |
| **Availability** | 99.9% | During market hours |
| **Memory** | < 2GB total | All models loaded |
| **Cold start** | < 30s | Full model reload |
| **Cache hit rate** | > 80% | Tier 1-2 models |

---

## 8. Model Versioning & A/B Testing

### 8.1 Versioning Schema

```
/models/
├── xgboost_confluence/
│   ├── v1/
│   │   ├── model.onnx              # Serialized model
│   │   ├── model.pkl               # Original Python model (for retraining)
│   │   ├── metadata.json           # Training date, metrics, config
│   │   ├── feature_list.json       # Ordered feature names
│   │   ├── scaler.pkl              # Feature scaler
│   │   ├── training_config.yaml    # Full training configuration
│   │   └── evaluation_report.md    # Performance metrics, SHAP plots
│   ├── v2/
│   │   └── ...
│   └── production -> v2/           # Symlink to active version
│
├── lstm_standard/
│   ├── v1/
│   │   ├── model.onnx
│   │   ├── model.pt                # PyTorch checkpoint
│   │   ├── metadata.json
│   │   ├── scaler.pkl
│   │   └── evaluation_report.md
│   └── production -> v1/
│
├── regime_hmm/
│   ├── v1/
│   │   ├── model.pkl
│   │   ├── scaler.pkl
│   │   ├── metadata.json
│   │   └── transition_matrix.json
│   └── production -> v2/
│
└── ppo_sizing/
    ├── v1/
    │   ├── model.pkl
    │   ├── vec_normalize.pkl       # Observation normalization
    │   ├── metadata.json
    │   └── training_log.csv
    └── production -> v1/
```

### 8.2 Metadata Schema

```json
{
  "model_name": "xgboost_confluence",
  "version": 2,
  "training_date": "2026-07-10",
  "training_data_range": "2024-01-01 to 2026-06-30",
  "training_samples": 125000,
  "features": ["sr_score", "liquidity_sweep", "ob_strength", "..."],
  "feature_count": 45,
  "metrics": {
    "auc_roc": 0.78,
    "auc_pr": 0.72,
    "precision": 0.70,
    "recall": 0.74,
    "f1": 0.72,
    "brier_score": 0.18,
    "sharpe_ratio_backtest": 1.85,
    "max_drawdown_backtest": 0.12,
    "walk_forward_mean_auc": 0.76,
    "walk_forward_std_auc": 0.03,
    "oos_auc": 0.75
  },
  "hyperparameters": {
    "n_estimators": 500,
    "max_depth": 6,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8
  },
  "deployment": {
    "status": "shadow",
    "traffic_pct": 0,
    "promoted_to_production": null,
    "rollback_version": 1
  },
  "training_run_id": "abc-123-def",
  "git_commit": "a1b2c3d"
}
```

### 8.3 A/B Testing Framework

```
┌─────────────────────────────────────────────────────────────────────┐
│                    A/B TESTING PIPELINE                                │
│                                                                       │
│  PHASE 1: SHADOW MODE (1–2 weeks)                                   │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  • New model runs in parallel with production model          │    │
│  │  • Predictions LOGGED but NOT used for trading               │    │
│  │  • Compare: accuracy, latency, edge cases, disagreements     │    │
│  │  • Gate: Must match or exceed production metrics             │    │
│  │  • Human review: Analyze disagreements between models        │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  PHASE 2: CANARY (1–2 weeks)                                        │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  • New model handles 10% of traffic                          │    │
│  │  • Monitor: P&L impact, signal quality, latency              │    │
│  │  • Gradual ramp: 10% → 25% → 50% over 2 weeks              │    │
│  │  • Auto-rollback triggers:                                   │    │
│  │    - Win rate drops > 5% from baseline                       │    │
│  │    - P99 latency exceeds tier threshold for 5+ minutes       │    │
│  │    - Error rate > 1% for 10+ minutes                         │    │
│  │    - Max drawdown exceeds 8% in current regime               │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  PHASE 3: FULL DEPLOYMENT                                            │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  • New model handles 100% of traffic                         │    │
│  │  • Previous model kept as hot standby (instant rollback)     │    │
│  │  • Monitor for 1 additional week before retiring old model   │    │
│  │  • Archive old model with full performance report            │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  AUTOMATIC ROLLBACK TRIGGERS:                                        │
│  • Win rate drops > 5% from baseline                                 │
│  • P99 latency exceeds tier threshold for 5+ minutes                │
│  • Error rate > 1% for 10+ minutes                                   │
│  • Max drawdown exceeds 8% in current regime                        │
│  • 3+ consecutive losing trades attributed to model                 │
└─────────────────────────────────────────────────────────────────────┘
```

### 8.4 Promotion Gate Checklist

Before any model version is promoted to production:

```
□ Walk-forward CV metrics meet minimum thresholds
□ Out-of-sample test metrics within 10% of CV mean
□ Backtest Sharpe > 1.0, max drawdown < 20%
□ Shadow mode: 1 week of live predictions logged
□ Shadow mode: Accuracy matches or exceeds production
□ Shadow mode: Latency within tier budget
□ No critical edge case failures detected
□ SHAP explanations reviewed for sanity
□ Human review of model disagreements completed
□ Rollback plan documented and tested
□ Monitoring alerts configured
□ Feature dependencies verified (no missing features in production)
```

---

## 9. Model Monitoring & Drift Detection

### 9.1 Monitoring Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    MODEL MONITORING SYSTEM                             │
│                                                                       │
│  LAYER 1: INFRASTRUCTURE MONITORING (continuous)                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  • Latency per model (P50, P95, P99)                        │    │
│  │  • Throughput (predictions/second)                           │    │
│  │  • Error rate per model                                      │    │
│  │  • Memory usage per model                                    │    │
│  │  • Cache hit rate                                            │    │
│  │  • Model load time                                           │    │
│  │  Alert: P99 latency > tier threshold for 5 min               │    │
│  │  Alert: Error rate > 1% for 10 min                           │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  LAYER 2: PREDICTION QUALITY MONITORING (per-prediction)            │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  • Prediction distribution (is it still sensible?)           │    │
│  │  • Confidence calibration (does 70% confidence = 70% accuracy?)│   │
│  │  • Feature completeness (any missing/NaN features?)          │    │
│  │  • Prediction latency vs feature computation latency         │    │
│  │  Alert: Prediction distribution shift detected               │    │
│  │  Alert: Confidence calibration error > 10%                   │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  LAYER 3: PERFORMANCE MONITORING (per-outcome)                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  • Rolling accuracy (last 100 predictions)                   │    │
│  │  • Rolling win rate (last 50 trades)                         │    │
│  │  • Rolling Sharpe ratio (last 30 days)                       │    │
│  │  • Profit factor trend                                       │    │
│  │  • Per-signal-source accuracy (which signals are failing?)   │    │
│  │  Alert: Rolling accuracy drops > 5% from baseline            │    │
│  │  Alert: 3+ consecutive losing trades                         │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  LAYER 4: DATA DRIFT MONITORING (daily)                              │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  • Feature distribution shift (KS test, PSI)                 │    │
│  │  • Label distribution shift (class balance change)           │    │
│  │  • Correlation structure change (feature correlation matrix) │    │
│  │  • Concept drift (relationship between features and target)  │    │
│  │  Alert: PSI > 0.2 for any top-10 feature                     │    │
│  │  Alert: KS statistic > 0.1 with p < 0.01                    │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

### 9.2 Drift Detection Methods

```python
class DriftDetector:
    """
    Detects data drift and concept drift using multiple statistical methods.
    """

    def __init__(self, reference_data: DataFrame):
        self.reference = reference_data
        self.reference_distributions = self._compute_distributions(reference_data)

    def check_drift(self, current_data: DataFrame) -> DriftReport:
        """Run all drift checks and return comprehensive report."""

        report = DriftReport()

        # 1. Population Stability Index (PSI) per feature
        for col in self.reference.columns:
            psi = self._compute_psi(
                self.reference[col], current_data[col]
            )
            report.psi_scores[col] = psi
            if psi > 0.2:
                report.alerts.append(f"HIGH drift: {col} PSI={psi:.3f}")
            elif psi > 0.1:
                report.alerts.append(f"MODERATE drift: {col} PSI={psi:.3f}")

        # 2. Kolmogorov-Smirnov test per feature
        for col in self.reference.columns:
            stat, p_value = ks_2samp(
                self.reference[col].dropna(),
                current_data[col].dropna()
            )
            report.ks_scores[col] = {'statistic': stat, 'p_value': p_value}
            if stat > 0.1 and p_value < 0.01:
                report.alerts.append(
                    f"KS drift: {col} stat={stat:.3f} p={p_value:.4f}"
                )

        # 3. Correlation structure change
        ref_corr = self.reference.corr()
        cur_corr = current_data.corr()
        corr_diff = (ref_corr - cur_corr).abs().mean().mean()
        report.correlation_drift = corr_diff
        if corr_diff > 0.15:
            report.alerts.append(
                f"Correlation structure shift: mean diff={corr_diff:.3f}"
            )

        # 4. Label distribution shift (if labels available)
        if 'label' in current_data.columns:
            ref_dist = self.reference['label'].value_counts(normalize=True)
            cur_dist = current_data['label'].value_counts(normalize=True)
            label_psi = self._compute_categorical_psi(ref_dist, cur_dist)
            report.label_drift = label_psi
            if label_psi > 0.2:
                report.alerts.append(
                    f"Label distribution shift: PSI={label_psi:.3f}"
                )

        # 5. Multivariate drift (MMD - Maximum Mean Discrepancy)
        mmd = self._compute_mmd(
            self.reference.select_dtypes(include=[np.number]),
            current_data.select_dtypes(include=[np.number])
        )
        report.mmd_score = mmd

        return report

    def _compute_psi(self, reference: Series, current: Series,
                     bins: int = 10) -> float:
        """Population Stability Index."""
        # Create bins from reference distribution
        breakpoints = np.percentile(reference.dropna(), np.linspace(0, 100, bins + 1))
        breakpoints[0] = -np.inf
        breakpoints[-1] = np.inf

        ref_counts = np.histogram(reference.dropna(), bins=breakpoints)[0]
        cur_counts = np.histogram(current.dropna(), bins=breakpoints)[0]

        # Normalize to proportions (add small epsilon to avoid log(0))
        eps = 1e-4
        ref_pct = ref_counts / ref_counts.sum() + eps
        cur_pct = cur_counts / cur_counts.sum() + eps

        psi = np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct))
        return psi
```

### 9.3 Performance Degradation Detection

```python
class PerformanceMonitor:
    """
    Monitors model performance in production and triggers alerts/retraining.
    """

    def __init__(self, db, alert_manager):
        self.db = db
        self.alerts = alert_manager

    async def log_prediction(self, model_name: str, prediction: dict,
                             actual_outcome: dict = None):
        """Log prediction and check for degradation when outcome is known."""

        await self.db.insert('prediction_log', {
            'time': datetime.utcnow(),
            'model_name': model_name,
            'prediction': prediction,
            'actual': actual_outcome,
            'latency_ms': prediction.get('latency_ms')
        })

        if actual_outcome:
            # Check rolling accuracy
            rolling_acc = await self._rolling_accuracy(model_name, window=100)
            baseline_acc = await self._baseline_accuracy(model_name)

            if rolling_acc < baseline_acc - 0.05:
                await self.alerts.send(
                    f"⚠️ Model {model_name} accuracy degraded: "
                    f"{rolling_acc:.1%} vs baseline {baseline_acc:.1%}",
                    priority="HIGH"
                )

                # Check if retraining trigger is met
                if rolling_acc < baseline_acc - 0.10:
                    await self._trigger_retraining(model_name)

    async def daily_report(self) -> dict:
        """Generate daily model performance report."""
        report = {}
        for model_name in self._get_active_models():
            report[model_name] = {
                'predictions_today': await self._count_predictions(model_name, 'today'),
                'accuracy_today': await self._rolling_accuracy(model_name, 'today'),
                'accuracy_7d': await self._rolling_accuracy(model_name, '7d'),
                'accuracy_30d': await self._rolling_accuracy(model_name, '30d'),
                'avg_latency_ms': await self._avg_latency(model_name, 'today'),
                'p99_latency_ms': await self._p99_latency(model_name, 'today'),
                'error_count': await self._error_count(model_name, 'today'),
                'accuracy_trend': await self._accuracy_trend(model_name, 30)
            }
        return report
```

### 9.4 Monitoring Dashboard Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  MODEL MONITORING DASHBOARD                                          │
├────────────────┬────────────────┬───────────────────────────────────┤
│  Model Health  │  Accuracy      │  Latency                          │
│  [heatmap]     │  [line chart]  │  [line chart with thresholds]     │
│                │  7d / 30d      │  P50 / P95 / P99                  │
├────────────────┴────────────────┴───────────────────────────────────┤
│  Drift Detection                                                     │
│  PSI per feature [bar chart]  │  KS test results [table]            │
│  Correlation drift: 0.03 ✅   │  Label shift: 0.05 ✅               │
├──────────────────────────────────────────────────────────────────────┤
│  Per-Model Performance                                               │
│  ┌──────────────┬───────┬───────┬───────┬───────┬───────┐          │
│  │ Model        │ Acc   │ F1    │ Sharpe│ Lat   │ Status│          │
│  ├──────────────┼───────┼───────┼───────┼───────┼───────┤          │
│  │ xgboost_conf │ 72%   │ 0.71  │ 1.85  │ 8ms   │ 🟢    │          │
│  │ xgboost_sweep│ 75%   │ 0.73  │ —     │ 6ms   │ 🟢    │          │
│  │ lstm_std     │ 58%   │ 0.56  │ 1.42  │ 45ms  │ 🟢    │          │
│  │ finbert      │ 83%   │ 0.81  │ —     │ 85ms  │ 🟡    │          │
│  │ hmm_regime   │ 76%   │ —     │ —     │ 3ms   │ 🟢    │          │
│  │ ppo_sizing   │ —     │ —     │ 1.92  │ 4ms   │ 🟢    │          │
│  └──────────────┴───────┴───────┴───────┴───────┴───────┘          │
├──────────────────────────────────────────────────────────────────────┤
│  Recent Alerts                                                       │
│  [table: time, model, message, severity]                             │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 10. Retraining Triggers & Automation

### 10.1 Retraining Trigger System

```
┌─────────────────────────────────────────────────────────────────────┐
│                    RETRAINING TRIGGERS                                │
│                                                                       │
│  TRIGGER 1: PERFORMANCE DEGRADATION (automatic)                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Condition: Rolling accuracy (100 predictions) drops > 10%   │    │
│  │             from baseline accuracy                           │    │
│  │  Action: Queue retraining job                                │    │
│  │  Priority: HIGH                                              │    │
│  │  Human approval: Not required (retraining is safe)           │    │
│  │  Deployment: Automatic shadow → canary (human gates prod)    │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  TRIGGER 2: DATA DRIFT (automatic)                                   │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Condition: PSI > 0.2 for any top-10 feature                 │    │
│  │             OR KS statistic > 0.1 with p < 0.01             │    │
│  │             OR correlation structure shift > 0.15            │    │
│  │  Action: Queue retraining job                                │    │
│  │  Priority: MEDIUM                                            │    │
│  │  Human approval: Not required                                │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  TRIGGER 3: SCHEDULED (automatic)                                    │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  XGBoost: Monthly (1st of month, 02:00 UTC)                 │    │
│  │  LSTM: Monthly (1st of month, 03:00 UTC)                    │    │
│  │  HMM: Monthly (1st of month, 04:00 UTC)                     │    │
│  │  FinBERT: Weekly (Sunday, 02:00 UTC) online; Monthly full   │    │
│  │  PPO/DQN: Monthly (1st of month, 05:00 UTC)                 │    │
│  │  Transformer: Quarterly (1st of Jan/Apr/Jul/Oct)            │    │
│  │  Action: Queue retraining job                                │    │
│  │  Priority: LOW                                               │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  TRIGGER 4: NEW DATA (automatic)                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Condition: 500+ new labeled samples accumulated (FinBERT)   │    │
│  │             OR new market regime detected (HMM)              │    │
│  │             OR new instrument added to trading universe       │    │
│  │  Action: Queue incremental training                          │    │
│  │  Priority: LOW                                               │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  TRIGGER 5: MANUAL (human-initiated)                                 │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Human can trigger retraining via command at any time        │    │
│  │  Used for: Emergency market events, strategy changes,        │    │
│  │            parameter adjustments, investigation              │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

### 10.2 Automated Retraining Pipeline

```python
class AutoRetrainingPipeline:
    """
    Orchestrates the full retraining lifecycle:
    trigger → train → validate → deploy (shadow) → promote
    """

    def __init__(self, model_registry, training_pipeline, validation_pipeline,
                 deployment_pipeline, monitor, alert_manager):
        self.registry = model_registry
        self.training = training_pipeline
        self.validation = validation_pipeline
        self.deployment = deployment_pipeline
        self.monitor = monitor
        self.alerts = alert_manager

    async def handle_trigger(self, trigger: RetrainingTrigger):
        """Process a retraining trigger end-to-end."""

        model_name = trigger.model_name
        logger.info(f"Retraining triggered for {model_name}: {trigger.reason}")

        # 1. Build training dataset
        dataset = self.training.build_dataset(
            model_name=model_name,
            symbol=trigger.symbol,
            timeframe=trigger.timeframe,
            lookback_years=3
        )

        # 2. Run hyperparameter tuning (if not scheduled-only)
        if trigger.priority != 'LOW':
            best_params = await self.training.tune_hyperparameters(
                model_name, dataset
            )
        else:
            best_params = self.registry.get_current_params(model_name)

        # 3. Train model
        model, train_metrics = await self.training.train(
            model_name=model_name,
            dataset=dataset,
            params=best_params
        )

        # 4. Validate
        validation_result = await self.validation.full_validation(
            model=model,
            dataset=dataset,
            model_name=model_name
        )

        if not validation_result.passed:
            logger.warning(
                f"Validation failed for {model_name}: {validation_result.failures}"
            )
            await self.alerts.send(
                f"❌ Retraining failed validation for {model_name}: "
                f"{validation_result.failures}",
                priority="MEDIUM"
            )
            return

        # 5. Register new version
        version = self.registry.register(
            model_name=model_name,
            model=model,
            metrics=validation_result.metrics,
            config=best_params,
            trigger=trigger
        )

        # 6. Deploy to shadow mode
        await self.deployment.deploy_shadow(model_name, version)

        # 7. Alert
        await self.alerts.send(
            f"✅ New model {model_name} v{version} deployed to shadow mode. "
            f"AUC: {validation_result.metrics.get('auc_roc', 'N/A'):.3f}. "
            f"Will promote to canary after 1 week of shadow monitoring.",
            priority="MEDIUM"
        )

    async def check_and_promote(self):
        """Check shadow models for promotion eligibility."""

        for model_name, version in self.deployment.get_shadow_models():
            shadow_metrics = await self.monitor.get_shadow_metrics(
                model_name, version
            )
            prod_metrics = await self.monitor.get_production_metrics(model_name)

            if self._should_promote(shadow_metrics, prod_metrics):
                await self.deployment.promote_to_canary(model_name, version)
                await self.alerts.send(
                    f"🚀 {model_name} v{version} promoted to canary (10% traffic)",
                    priority="MEDIUM"
                )
```

### 10.3 Retraining Schedule

| Model | Scheduled Retrain | Trigger-Based | Estimated Duration |
|-------|------------------|---------------|-------------------|
| **FinBERT** | Weekly (online), Monthly (full) | 500+ new labeled samples | 30 min (online), 2h (full) |
| **XGBoost (5-8 models)** | Monthly | Accuracy drop > 10% | 1h per model |
| **LSTM (3-5 models)** | Monthly | Performance degradation | 2h per model |
| **HMM** | Monthly | Log-likelihood drop > 20% | 30 min |
| **PPO/DQN** | Monthly | New regime, performance drop | 4h per agent |
| **Transformer** | Quarterly | — | 8h |
| **CNN** | Quarterly | New pattern types | 4h |

### 10.4 Training Resource Budget

| Phase | Compute | Cost | Models Trained |
|-------|---------|------|----------------|
| **Phase 1-3** | CPU only (4 cores, 16GB RAM) | $0 (local) | XGBoost, HMM, small LSTM |
| **Phase 4** | Spot GPU (T4, 16GB VRAM) | $5-10/month | Full LSTM, Transformer, RL |
| **Phase 5** | Spot GPU (A10G, 24GB VRAM) | $15-25/month | All models, GAN training |

---

## 11. Multi-Agent Integration

### 11.1 Agent-Model Binding Matrix

Each agent in the multi-agent system is bound to specific models:

```
┌──────────────────────────────────────────────────────────────────────┐
│                    AGENT ↔ MODEL BINDING                               │
│                                                                        │
│  Agent                 │ Models Used                   │ Call Pattern  │
│  ──────────────────────┼───────────────────────────────┼────────────── │
│  Fundamental Agent     │ FinBERT, LLM (reasoning),     │ Pre-session   │
│  (Step 1)              │ XGBoost (event impact)        │ + on-event    │
│                        │                               │               │
│  Structure Agent       │ HMM (regime), XGBoost         │ Every H4      │
│  (Steps 2-4)           │ (bias), LSTM (structure)      │ + session     │
│                        │                               │               │
│  S/R Module            │ XGBoost (level quality),      │ Every D1      │
│  (Step 5)              │ DBSCAN (clustering)           │               │
│                        │                               │               │
│  Liquidity Agent       │ Random Forest (flow),         │ Continuous +  │
│  (Step 6)              │ XGBoost (sweep classifier)    │ every M15     │
│                        │                               │               │
│  SMC Agent             │ XGBoost (pattern success),    │ Every M15     │
│  (Step 7)              │ LSTM (complex patterns)       │               │
│                        │                               │               │
│  Momentum Agent        │ XGBoost (RSI signal),         │ Every M15     │
│  (Step 8)              │ HMM (adaptive thresholds)     │               │
│                        │                               │               │
│  Candlestick Agent     │ CNN (visual), XGBoost         │ Every candle  │
│  (Step 9)              │ (outcome predictor)           │ close         │
│                        │                               │               │
│  Entry Agent           │ XGBoost (confluence),         │ On signal     │
│  (Steps 10-11)         │ PPO (position sizing)         │ (score ≥ 60)  │
│                        │                               │               │
│  Risk Gate Agent       │ NONE (pure code)              │ Every trade   │
│  (Step 12)             │                               │ proposal      │
│                        │                               │               │
│  TP Agent              │ DQN (TP policy), LSTM         │ Every M15     │
│  (Step 13)             │ (exit timing)                 │ (in-trade)    │
│                        │                               │               │
│  Trade Mgmt Agent      │ LSTM (exit signal),           │ Continuous    │
│  (Steps 14-15)         │ XGBoost (early warning)       │ (in-trade)    │
│                        │                               │               │
│  Execution Agent       │ Q-Table (execution),          │ On order      │
│                        │ NONE (algorithmic)            │               │
│                        │                               │               │
│  Reflection Agent      │ LLM (reasoning), RL           │ Post-trade +  │
│                        │ (policy improvement)          │ daily/weekly  │
│                        │                               │               │
│  Journal Agent         │ LLM (analysis), Clustering    │ Post-trade +  │
│                        │ (pattern recognition)         │ daily/weekly  │
└──────────────────────────────────────────────────────────────────────┘
```

### 11.2 Agent-Model Communication Protocol

```python
class AgentModelInterface:
    """
    Standardized interface for agents to call models.
    Handles caching, fallback, timeout, and monitoring.
    """

    async def predict(self, agent_id: str, model_name: str,
                      features: dict, context: dict = None) -> dict:
        """
        Agent calls model through this interface.

        Flow:
        1. Check prediction cache (TTL-based)
        2. Run inference with timeout (per tier)
        3. On timeout/error: return rule-based fallback
        4. Cache result
        5. Log for monitoring
        """

        # 1. Check cache
        cache_key = self._build_cache_key(model_name, features)
        cached = await self.cache.get(cache_key)
        if cached and not self._is_stale(cached, model_name):
            return cached

        # 2. Run inference with timeout
        try:
            result = await asyncio.wait_for(
                self.model_manager.predict(model_name, features),
                timeout=self._get_timeout(model_name)
            )
        except asyncio.TimeoutError:
            result = self._fallback(model_name)
            await self.monitor.log_timeout(agent_id, model_name)

        except Exception as e:
            result = self._fallback(model_name)
            await self.monitor.log_error(agent_id, model_name, str(e))

        # 3. Cache
        ttl = self._get_cache_ttl(model_name)
        await self.cache.set(cache_key, result, ttl)

        # 4. Log
        await self.monitor.log_prediction(
            agent_id=agent_id,
            model_name=model_name,
            prediction=result,
            features=features
        )

        return result

    def _get_timeout(self, model_name: str) -> float:
        """Timeout per latency tier."""
        tier = self._get_tier(model_name)
        timeouts = {1: 0.005, 2: 0.050, 3: 0.500, 4: 10.0}
        return timeouts[tier]
```

### 11.3 Model → Agent Signal Flow

```
Model Output                    Agent Processing              Action
─────────────                   ──────────────────            ──────
FinBERT: {bullish: 0.8}   →    Fundamental Agent:            fundamental_bias = "BULLISH"
                                Multiply by source weight     confidence = 0.8

HMM: {bull: 0.82}         →    Structure Agent:              regime = "BULL_TREND"
                                Route to strategy weights     trend_weight = 0.80
                                                              rsi_oversold = 40

XGBoost: {score: 0.72}    →    Signal Aggregator:            confluence_score = 72
                                Compare to thresholds         → "STANDARD POSITION"
                                Generate trade proposal       risk = 1.0%

PPO: {size_mult: 1.3}    →    Entry Agent:                  position_size × 1.3
                                Apply safety constraints      capped at 2.0

DQN: {action: "close_50%"} →   TP Agent:                     Execute partial close
                                Send to Execution Agent       order = close 50%

LLM: {recommendation:     →    Fundamental Agent:            If "AVOID" → no trade
     "AVOID", reason:...}       Pass reasoning to human       Alert with reasoning
```

### 11.4 Shared Feature Store Access

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SHARED FEATURE STORE                                │
│                                                                       │
│  All agents and models read from a single Redis-backed feature store│
│  to avoid redundant computation:                                      │
│                                                                       │
│  Key Pattern                    │ TTL          │ Updated By          │
│  ───────────────────────────────┼──────────────┼─────────────────── │
│  features:{symbol}:technical    │ Until candle │ Feature Pipeline   │
│  features:{symbol}:structure    │ Until candle │ Structure Agent    │
│  features:{symbol}:sentiment    │ 1 hour       │ Fundamental Agent  │
│  features:{symbol}:regime       │ Until H4     │ Structure Agent    │
│  features:{symbol}:cross_asset  │ Until candle │ Feature Pipeline   │
│  prediction:{model}:{symbol}    │ Model-specific│ Model Manager      │
│  signal:{agent}:{symbol}        │ 5 min        │ Signal Agent       │
│                                                                       │
│  Invalidation:                                                        │
│  • On new candle: technical, structure, cross_asset features         │
│  • On news event: sentiment features                                  │
│  • On regime change: regime features                                  │
│  • On model retrain: prediction cache cleared                        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 12. GPU/CPU Considerations

### 12.1 Compute Requirements by Model

| Model | CPU Inference | GPU Inference | GPU Needed? | Memory |
|-------|--------------|---------------|-------------|--------|
| **XGBoost/LightGBM** | < 10ms ✅ | < 2ms (GPU) | No | 50-200MB per model |
| **LSTM (small)** | < 50ms ✅ | < 5ms | No | 10-50MB per model |
| **LSTM (large)** | 100-300ms | < 20ms | Optional | 100-500MB |
| **Transformer** | 200-500ms | < 50ms | Recommended | 500MB-2GB |
| **FinBERT** | < 100ms ✅ | < 20ms | No (ONNX optimized) | 400MB |
| **HMM** | < 5ms ✅ | N/A | No | 10-50MB |
| **CNN** | < 100ms ✅ | < 20ms | No | 50-200MB |
| **PPO/DQN (inference)** | < 5ms ✅ | < 1ms | No | 5-50MB |
| **PPO/DQN (training)** | Hours | Minutes | Recommended | 1-4GB |
| **LLM (local)** | 10-30s | 1-3s | Recommended | 4-14GB |
| **GAN (training)** | Days | Hours | Required | 2-8GB |

### 12.2 Phase-Based Compute Strategy

```
┌─────────────────────────────────────────────────────────────────────┐
│                    COMPUTE STRATEGY BY PHASE                          │
│                                                                       │
│  PHASE 1-3: CPU ONLY ($0 infrastructure)                             │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Machine: 4-core CPU, 16GB RAM, 500GB SSD                   │    │
│  │  Models: XGBoost, HMM, small LSTM, FinBERT (ONNX), Q-table │    │
│  │  Training: Overnight batch jobs (XGBoost ~1h, LSTM ~2h)     │    │
│  │  Inference: All models < 100ms on CPU with ONNX Runtime     │    │
│  │  Limitations: No Transformer, no large LSTM, no CNN          │    │
│  │  RL training: Slow but feasible (PPO ~4h on CPU)            │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  PHASE 4: GPU FOR TRAINING ($5-10/month spot instances)              │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Training: Spot T4 instance (16GB VRAM)                      │    │
│  │  • Upload training data to instance                          │    │
│  │  • Train LSTM, Transformer, RL agents                        │    │
│  │  • Export to ONNX, download to production CPU machine        │    │
│  │  • Training runs: 2-4 hours/month                            │    │
│  │  Inference: Still CPU-only in production                     │    │
│  │  New models: Large LSTM, Transformer, CNN                    │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  PHASE 5: GPU FOR INFERENCE ($15-25/month)                           │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Production: T4 GPU instance for inference                   │    │
│  │  • All PyTorch models run on GPU                             │    │
│  │  • FinBERT: < 20ms (vs 100ms CPU)                           │    │
│  │  • Transformer: < 50ms (vs 500ms CPU)                       │    │
│  │  • Batch inference: Process all instruments in parallel      │    │
│  │  Local LLM: Ollama on GPU (Qwen-2.5-7B, ~2s inference)     │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  PHASE 6+: SCALE ($50-200/month)                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Multi-GPU: A10G (24GB VRAM) for training                   │    │
│  │  Distributed: Ray cluster for parallel training              │    │
│  │  GPU inference: Dedicated inference server                   │    │
│  │  Model optimization: TensorRT for maximum throughput         │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

### 12.3 ONNX Optimization Strategy

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ONNX OPTIMIZATION PIPELINE                         │
│                                                                       │
│  WHY ONNX: 2-5× faster CPU inference vs native PyTorch/sklearn      │
│                                                                       │
│  EXPORT PIPELINE:                                                    │
│                                                                       │
│  XGBoost → skl2onnx → ONNX → ONNX Runtime (CPU)                    │
│  • Optimization: graph optimization, constant folding               │
│  • Result: < 10ms inference for 500-tree ensemble                   │
│                                                                       │
│  PyTorch LSTM → torch.onnx.export → ONNX → ONNX Runtime            │
│  • Optimization: operator fusion, memory planning                   │
│  • Dynamic axes: variable batch size and sequence length            │
│  • Result: 3-4× faster than PyTorch CPU inference                   │
│                                                                       │
│  FinBERT → optimum (Hugging Face) → ONNX → ONNX Runtime            │
│  • Optimization: quantization (INT8), operator fusion               │
│  • Result: 2-3× faster, < 1% accuracy loss                         │
│                                                                       │
│  PyTorch Transformer → torch.onnx.export → ONNX → ONNX Runtime     │
│  • Optimization: attention fusion, KV cache                         │
│  • Result: 2× faster on CPU                                         │
│                                                                       │
│  QUANTIZATION (Phase 5+):                                            │
│  • Dynamic quantization: INT8 weights, FP32 activations             │
│  • Static quantization: INT8 weights + activations (calibration)    │
│  • Result: Additional 2× speedup, < 1% accuracy loss for most models│
└─────────────────────────────────────────────────────────────────────┘
```

### 12.4 Inference Latency Budget

```
CRITICAL PATH: Tick → Signal → Order (target: < 25ms total)

  Tick received           →  0ms
  Feature update (Redis)  →  1ms
  HMM regime check        →  3ms  (Tier 1, cached)
  XGBoost signal score    →  8ms  (Tier 2, ONNX)
  Confluence aggregation  →  2ms
  Risk gate check         →  1ms  (pure code)
  Order submission        →  5ms
  ──────────────────────────────
  TOTAL                   → 20ms  ✅ (under 25ms budget)

NON-CRITICAL PATH: Analysis cycle (target: < 500ms)

  FinBERT sentiment       → 85ms  (Tier 3, ONNX)
  LSTM price prediction   → 45ms  (Tier 2, ONNX)
  RL policy inference     →  4ms  (Tier 2, ONNX)
  Transformer analysis    → 180ms (Tier 3, ONNX)
  ──────────────────────────────
  TOTAL (parallel)        → 180ms ✅ (under 500ms budget)

BACKGROUND PATH: LLM reasoning (target: < 10s)

  LLM fundamental analysis → 3-5s  (Tier 4, API)
  Report generation        → 2-5s  (Tier 4, API)
  ──────────────────────────────
  TOTAL                    → 5-10s ✅ (under 10s budget)
```

---

## 13. Implementation Roadmap

### Phase 1: Foundation (Weeks 1–4)

```
□ Set up data ingestion adapters (MT5, CCXT)
□ Implement normalization & validation pipeline
□ Set up TimescaleDB with feature store tables
□ Implement Redis feature cache
□ Build feature engineering pipeline (Groups 1-4)
□ Train and deploy HMM regime detector (3-state)
□ Train and deploy XGBoost confluence scorer
□ Train and deploy FinBERT sentiment model (fine-tuned)
□ Implement ModelManager with ONNX Runtime
□ Implement AgentModelInterface (caching, fallback, monitoring)
□ Validate: All Tier 1-2 models running with < 50ms P99 latency
```

### Phase 2: Prediction Models (Weeks 5–8)

```
□ Implement walk-forward validation pipeline
□ Implement hyperparameter tuning (Optuna)
□ Train and deploy LSTM price predictor (Standard variant)
□ Train and deploy XGBoost sweep classifier
□ Train and deploy XGBoost SMC pattern predictor
□ Train and deploy XGBoost RSI signal model
□ Train and deploy XGBoost S/R level scorer
□ Implement SHAP explainability for all XGBoost models
□ Implement feature selection pipeline (correlation, MI, SHAP)
□ Validate: Prediction models achieving target metrics
```

### Phase 3: RL & Advanced Models (Weeks 9–12)

```
□ Implement RL training environment (wraps backtester)
□ Train PPO position sizing agent (offline, 1M transitions)
□ Train DQN take-profit agent (offline, 500K transitions)
□ Implement Q-learning execution agent
□ Implement RL safety constraints (hard limits)
□ Deploy RL agents in shadow mode (observe only)
□ Train LSTM volatility predictor
□ Implement model versioning system
□ Implement A/B testing framework (shadow → canary → production)
□ Validate: RL agents matching or exceeding rule-based baseline
```

### Phase 4: Monitoring & Automation (Weeks 13–16)

```
□ Implement model monitoring system (all 4 layers)
□ Implement drift detection (PSI, KS, correlation)
□ Implement automated retraining pipeline
□ Implement retraining triggers (performance, drift, schedule)
□ Implement prediction logging and analysis
□ Set up monitoring dashboards (Grafana)
□ Implement CPCV for strategy-level validation
□ Implement closed learning loop (trade outcomes → model updates)
□ Validate: Full pipeline running end-to-end with monitoring
```

### Phase 5: Optimization & Scale (Weeks 17+)

```
□ Implement cross-asset feature pipeline (Group 5)
□ Implement Transformer multi-timeframe model (requires GPU training)
□ Implement CNN chart pattern recognition
□ Implement GAN synthetic data generation
□ Optimize inference latency (quantization, batching)
□ Scale to multi-instrument (crypto + forex)
□ Implement model performance attribution
□ Implement distributed training (Ray)
□ Continuous monitoring and improvement
```

### Cost Summary

| Phase | Infrastructure | Monthly Cost | Notes |
|-------|---------------|-------------|-------|
| **Phase 1-3** | CPU machine (local) | $0 | All models on CPU with ONNX |
| **Phase 4** | + Spot GPU for training | $5-10 | 2-4 hours/month GPU training |
| **Phase 5** | + GPU inference server | $15-25 | Dedicated inference |
| **Phase 6+** | + Multi-GPU, distributed | $50-200 | Institutional scale |
| **LLM API** | DeepSeek/Qwen | $15-30 | ~30K tokens/day |
| **Data feeds** | Free tiers | $0-50 | Scales with instruments |
| **Total (Phase 1-3)** | | **$15-30/month** | |
| **Total (Phase 4-5)** | | **$35-65/month** | |

---

## Appendix A: Key Design Decisions

| Decision | Choice | Rationale | Trade-off |
|----------|--------|-----------|-----------|
| ONNX for inference | ONNX Runtime | 2-5× faster CPU, framework-agnostic | Export complexity |
| XGBoost over deep learning for signals | XGBoost | Faster, better on tabular, interpretable (SHAP) | Less expressive |
| Walk-forward over random CV | Walk-forward | Respects temporal ordering, no future leakage | Fewer folds |
| Purged CV gap | 5 bars | Prevents autocorrelation leakage | Reduces training data |
| HMM + ensemble for regime | HMM + rules + vol + ML | HMM captures transitions; ensemble for robustness | More complex |
| PPO over other RL | PPO | Stable, handles continuous actions, industry standard | Slower than simpler methods |
| Shadow → canary → production | 3-phase deployment | Safety-first; catch issues before full rollout | Slower deployment |
| Redis feature store | Redis | Sub-ms reads, shared across all models | Memory cost |
| CPU-first strategy | CPU with ONNX | $0 infrastructure for Phase 1-3 | Some models limited |
| Separate training from serving | Offline training, online serving | Training doesn't affect inference latency | Stale models possible |

---

## Appendix B: Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **ML Framework** | scikit-learn, XGBoost, LightGBM | Classical ML models |
| **Deep Learning** | PyTorch | LSTM, Transformer, CNN, FinBERT |
| **Inference** | ONNX Runtime | Optimized CPU/GPU inference |
| **RL** | Stable-Baselines3 | PPO, DQN training and inference |
| **HMM** | hmmlearn | Regime detection |
| **Hyperparameter Tuning** | Optuna | Bayesian optimization |
| **Feature Store** | Redis | Hot feature cache |
| **Time-Series DB** | TimescaleDB | Historical features, training data |
| **Model Registry** | Filesystem + metadata DB | Versioned model artifacts |
| **Monitoring** | Custom + Prometheus + Grafana | Drift detection, performance tracking |
| **Experiment Tracking** | Weights & Biases (Phase 4+) | Training run comparison |
| **Data Versioning** | DVC (Phase 4+) | Reproducible training data |

---

## Appendix C: Glossary

| Term | Definition |
|------|-----------|
| **Walk-forward CV** | Time-series cross-validation that trains on past, tests on future, stepping forward |
| **Purged CV** | CV with a gap between train/test to prevent information leakage |
| **CPCV** | Combinatorial Purged CV — generates multiple backtest paths |
| **PSI** | Population Stability Index — measures distribution shift |
| **KS Test** | Kolmogorov-Smirnov test — non-parametric distribution comparison |
| **SHAP** | SHapley Additive exPlanations — model interpretability |
| **ONNX** | Open Neural Network Exchange — cross-platform model format |
| **Shadow mode** | Model runs in parallel but predictions not used for trading |
| **Canary mode** | Model handles small % of traffic for gradual rollout |
| **Concept drift** | Change in the relationship between features and target |
| **Data drift** | Change in the distribution of input features |
| **OOS** | Out-of-sample — data never seen during training/tuning |

---

*Document generated: 2026-07-11*
*Author: ML Pipeline Architect Agent — Alpha Stack*
*Status: Architecture Design Complete — Ready for Implementation Review*
*Dependencies: architecture_ai_models.md, architecture_data.md, architecture_multi_agent.md*
*Next: Review with team → Begin Phase 1 implementation*
