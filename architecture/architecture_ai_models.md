# Alpha Stack — AI/ML Model Architecture

**Date:** 2026-07-11
**Version:** 1.0
**Status:** Architecture Design — Ready for Implementation Review
**Author:** AI Models Architect Agent

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Model Selection by Strategy Step](#2-model-selection-by-strategy-step)
3. [FinBERT — Sentiment Analysis Engine](#3-finbert--sentiment-analysis-engine)
4. [LSTM & Transformer — Price Prediction](#4-lstm--transformer--price-prediction)
5. [Hidden Markov Model — Regime Detection](#5-hidden-markov-model--regime-detection)
6. [Reinforcement Learning — Strategy Optimization](#6-reinforcement-learning--strategy-optimization)
7. [LLM Integration — Fundamental Analysis & Reasoning](#7-llm-integration--fundamental-analysis--reasoning)
8. [Model Serving Architecture](#8-model-serving-architecture)
9. [Model Versioning & A/B Testing](#9-model-versioning--ab-testing)
10. [Agent ↔ Model Integration](#10-agent--model-integration)
11. [Training Data Requirements](#11-training-data-requirements)
12. [Implementation Roadmap](#12-implementation-roadmap)

---

## 1. Executive Summary

Alpha Stack's AI/ML architecture deploys **8 specialized model families** across 16 strategy steps, orchestrated by a multi-agent system. Each model serves a distinct purpose — from understanding human language (FinBERT, LLMs) to detecting hidden market states (HMM) to optimizing execution through experience (RL). The architecture prioritizes **latency-awareness** (fast models for execution, slow models for research), **interpretability** (SHAP explanations for every trade), and **continuous learning** (closed feedback loops that improve models from trade outcomes).

### Model Family Overview

| # | Model Family | Primary Task | Inference Latency | Model Count |
|---|-------------|-------------|-------------------|-------------|
| 1 | **FinBERT** | Financial sentiment analysis | < 100ms | 1 (multi-tenant) |
| 2 | **XGBoost / LightGBM** | Signal classification, confluence scoring | < 10ms | 5–8 (per task) |
| 3 | **LSTM** | Sequential price/volatility prediction | < 50ms | 3–5 (per timeframe) |
| 4 | **Transformer** | Multi-timeframe, cross-asset analysis | < 200ms | 1–2 (per asset class) |
| 5 | **Hidden Markov Model** | Market regime detection | < 5ms | 2–3 (forex, crypto, ensemble) |
| 6 | **Reinforcement Learning** | Strategy optimization, TP management, execution | < 30ms | 3–5 (per strategy) |
| 7 | **LLM (DeepSeek/Qwen)** | Fundamental analysis, reasoning, report generation | 1–5s | 2 (reasoning + fast) |
| 8 | **CNN** | Chart pattern recognition (optional, Phase 2+) | < 100ms | 1–2 |

**Total active models at full deployment: 20–35**
**Estimated daily inference cost: $2–5 (excluding LLM API)**

---

## 2. Model Selection by Strategy Step

Each of the 16 Alpha Strategy steps maps to specific models. The selection is driven by **latency requirements**, **data type** (text, numerical, sequential), and **task type** (classification, regression, generation).

### 2.1 Complete Step → Model Mapping

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    ALPHA STRATEGY — MODEL PIPELINE                        │
│                                                                           │
│  STEP 1: Fundamental Intelligence                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────┐   │
│  │   FinBERT    │  │  LLM Reason  │  │  XGBoost Event Impact        │   │
│  │  (sentiment) │  │  (DeepSeek)  │  │  (surprise scoring)          │   │
│  └──────┬───────┘  └──────┬───────┘  └──────────────┬───────────────┘   │
│         └──────────────────┼─────────────────────────┘                    │
│                            ▼                                              │
│  STEP 2: Market Bias                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────┐   │
│  │     HMM      │  │   XGBoost    │  │  Linear Regression           │   │
│  │  (regime)    │  │  (bias clsf) │  │  (baseline, fast path)       │   │
│  └──────┬───────┘  └──────┬───────┘  └──────────────┬───────────────┘   │
│         └──────────────────┼─────────────────────────┘                    │
│                            ▼                                              │
│  STEP 3: Session Analysis                                                 │
│  ┌──────────────┐  ┌──────────────────────────────────────────────┐     │
│  │  Rules-Based │  │  XGBoost (session volatility classifier)     │     │
│  │  (session    │  │  LightGBM (Asian range breakout predictor)   │     │
│  │   state      │  └──────────────────────────────────────────────┘     │
│  │   machine)   │                                                        │
│  └──────┬───────┘                                                        │
│         ▼                                                                │
│  STEP 4: Market Structure                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────┐   │
│  │  Algorithmic │  │   XGBoost    │  │  LSTM (structure sequence)   │   │
│  │  (swing det, │  │  (BOS/CHoCH  │  │  (optional, for complex      │   │
│  │   BOS/CHoCH) │  │   classifier)│  │   multi-candle patterns)     │   │
│  └──────┬───────┘  └──────┬───────┘  └──────────────┬───────────────┘   │
│         └──────────────────┼─────────────────────────┘                    │
│                            ▼                                              │
│  STEP 5: Support & Resistance                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────┐   │
│  │  Algorithmic │  │   XGBoost    │  │  DBSCAN                      │   │
│  │  (fractal,   │  │  (level      │  │  (cluster nearby levels)     │   │
│  │   volume     │  │   quality    │  └──────────────────────────────┘   │
│  │   profile)   │  │   scorer)    │                                       │
│  └──────┬───────┘  └──────┬───────┘                                       │
│         └──────────────────┘                                              │
│                            ▼                                              │
│  STEP 6: Liquidity Detection                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────┐   │
│  │  Algorithmic │  │  Random      │  │  XGBoost                     │   │
│  │  (order book,│  │  Forest      │  │  (sweep classifier:          │   │
│  │   delta,     │  │  (institutional│ │   real vs fake)              │   │
│  │   flow)      │  │   flow det.) │  └──────────────────────────────┘   │
│  └──────┬───────┘  └──────┬───────┘                                       │
│         └──────────────────┘                                              │
│                            ▼                                              │
│  STEP 7: Smart Money Concepts                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────┐   │
│  │  Algorithmic │  │   XGBoost    │  │  LSTM/Transformer            │   │
│  │  (OB, FVG,   │  │  (pattern    │  │  (complex pattern            │   │
│  │   breaker)   │  │   success    │  │   recognition, optional)     │   │
│  │              │  │   predictor) │  └──────────────────────────────┘   │
│  └──────┬───────┘  └──────┬───────┘                                       │
│         └──────────────────┘                                              │
│                            ▼                                              │
│  STEP 8: RSI / Momentum                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────┐   │
│  │  Algorithmic │  │   XGBoost    │  │  HMM (regime-adaptive        │   │
│  │  (RSI,       │  │  (RSI signal │  │   RSI thresholds)            │   │
│  │   composite  │  │   predictor) │  └──────────────────────────────┘   │
│  │   momentum)  │  │              │                                       │
│  └──────┬───────┘  └──────┬───────┘                                       │
│         └──────────────────┘                                              │
│                            ▼                                              │
│  STEP 9: Candlestick                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────┐   │
│  │  Algorithmic │  │   CNN        │  │  XGBoost                     │   │
│  │  (rule-based │  │  (visual     │  │  (pattern outcome            │   │
│  │   patterns)  │  │   pattern    │  │   predictor)                 │   │
│  │              │  │   recog.)    │  └──────────────────────────────┘   │
│  └──────┬───────┘  └──────┬───────┘                                       │
│         └──────────────────┘                                              │
│                            ▼                                              │
│  STEP 10–12: Entry / Sizing / Stop Loss                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────┐   │
│  │  Algorithmic │  │  XGBoost     │  │  RL (DQN/PPO)               │   │
│  │  (confluence │  │  (entry      │  │  (position sizing            │   │
│  │   scoring)   │  │   timing)    │  │   optimization)              │   │
│  └──────┬───────┘  └──────┬───────┘  └──────────────┬───────────────┘   │
│         └──────────────────┼─────────────────────────┘                    │
│                            ▼                                              │
│  STEP 13–15: TP / Management / Exit                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────┐   │
│  │  RL (PPO)    │  │  LSTM        │  │  XGBoost                     │   │
│  │  (TP optim,  │  │  (exit       │  │  (early warning              │   │
│  │   trailing)  │  │   timing)    │  │   signal classifier)         │   │
│  └──────┬───────┘  └──────┬───────┘  └──────────────┬───────────────┘   │
│         └──────────────────┼─────────────────────────┘                    │
│                            ▼                                              │
│  STEP 16: Journal & Learning                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────┐   │
│  │  LLM         │  │  RL          │  │  Clustering                  │   │
│  │  (analysis,  │  │  (policy     │  │  (trade pattern              │   │
│  │   reports)   │  │   improve.)  │  │   recognition)               │   │
│  └──────────────┘  └──────────────┘  └──────────────────────────────┘   │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Model Selection Rationale

| Step | Primary Model | Why This Model | Alternative |
|------|--------------|----------------|-------------|
| **1: Fundamental** | FinBERT + LLM | Text understanding requires NLP models; FinBERT is domain-specific | GPT-4o for zero-shot analysis |
| **2: Market Bias** | HMM + XGBoost | HMM captures hidden states; XGBoost handles tabular features | Rules-based as fallback |
| **3: Session** | Rules + XGBoost | Session boundaries are deterministic; volatility prediction is ML | LightGBM for speed |
| **4: Structure** | Algorithmic + XGBoost | Swing detection is algorithmic; pattern quality is ML | LSTM for complex sequences |
| **5: S/R** | Algorithmic + XGBoost | Fractal detection is algorithmic; level quality is ML | — |
| **6: Liquidity** | Algorithmic + RF | Order flow is algorithmic; sweep classification is ML | — |
| **7: SMC** | Algorithmic + XGBoost | Pattern detection is algorithmic; success prediction is ML | LSTM for temporal patterns |
| **8: RSI/Momentum** | Algorithmic + XGBoost | Indicators are formulaic; signal quality is ML | — |
| **9: Candlestick** | Rules + CNN + XGBoost | Rules for known patterns; CNN for visual; XGBoost for outcome | — |
| **10–12: Entry/Size/SL** | XGBoost + RL | XGBoost for confluence; RL for optimal sizing | — |
| **13–15: TP/Mgmt/Exit** | RL + LSTM | RL for optimal policy; LSTM for exit timing | — |
| **16: Journal** | LLM + RL + Clustering | LLM for analysis; RL for policy improvement; clustering for patterns | — |

### 2.3 Latency Tiers

Models are organized by inference latency requirements:

```
TIER 1: ULTRA-FAST (< 5ms) — Real-time execution
├── Algorithmic detectors (swing, OB, FVG, S/R, RSI)
├── HMM regime classification (pre-computed transition matrix)
├── Rules-based session state machine
└── Linear regression baseline

TIER 2: FAST (< 50ms) — Per-candle analysis
├── XGBoost / LightGBM classifiers (signal, confluence, sweep)
├── Random Forest ensemble
├── DBSCAN clustering
└── LSTM (small, < 64 hidden units)

TIER 3: MEDIUM (< 500ms) — Per-session analysis
├── LSTM (large, 128+ hidden units)
├── Transformer (multi-timeframe)
├── CNN chart pattern recognition
├── RL policy inference (DQN/PPO)
└── FinBERT sentiment scoring

TIER 4: SLOW (1–10s) — Periodic / event-driven
├── LLM reasoning (DeepSeek/Qwen for fundamental analysis)
├── LLM report generation
├── Model retraining (background)
└── RL training episodes (background)
```

---

## 3. FinBERT — Sentiment Analysis Engine

### 3.1 Model Specification

| Property | Value |
|----------|-------|
| **Base Model** | `ProsusAI/finbert` (pre-trained on financial text) |
| **Fine-tuning** | Forex/crypto corpus (central bank language, macro terminology) |
| **Input** | Headline + first 2 sentences (max 512 tokens) |
| **Output** | `Bullish` / `Bearish` / `Neutral` + confidence [0, 1] |
| **Inference Latency** | < 100ms (CPU), < 20ms (GPU) |
| **Batch Size** | 16–32 articles per inference call |
| **Deployment** | ONNX Runtime on CPU (cost-efficient) |

### 3.2 Three-Layer Sentiment Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                 SENTIMENT ANALYSIS PIPELINE                       │
│                                                                   │
│  LAYER 1: FinBERT Classification (Fast, Always Running)          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Input: RSS headline + lead sentence                     │    │
│  │  Process: Tokenize → FinBERT → Softmax                  │    │
│  │  Output: {bullish: 0.72, bearish: 0.15, neutral: 0.13}  │    │
│  │  Latency: < 100ms                                       │    │
│  │  Use: All articles, continuous stream                    │    │
│  └────────────────────────┬────────────────────────────────┘    │
│                           │                                       │
│  LAYER 2: LLM Reasoning (Slow, Triggered for Complex Events)    │
│  ┌────────────────────────▼────────────────────────────────┐    │
│  │  Trigger: High-impact event OR FinBERT confidence < 0.6  │    │
│  │  Input: Full article + macro context + recent price data │    │
│  │  Process: Chain-of-thought reasoning                     │    │
│  │  Output: Direction + confidence + reasoning chain        │    │
│  │  Latency: 2–5s                                          │    │
│  │  Use: Central bank decisions, NFP, geopolitical events   │    │
│  └────────────────────────┬────────────────────────────────┘    │
│                           │                                       │
│  LAYER 3: Event Impact Scoring (Historical + Bayesian)           │
│  ┌────────────────────────▼────────────────────────────────┐    │
│  │  Input: Event type + actual vs forecast + current regime │    │
│  │  Process: Bayesian updating from historical impact DB    │    │
│  │  Output: Expected move (pips), direction probability,    │    │
│  │          impact window (hours)                           │    │
│  │  Latency: < 5ms (table lookup + calculation)            │    │
│  │  Use: All structured economic releases                   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│  AGGREGATION: Source-Weighted Sentiment Score                     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Bloomberg/Reuters:    weight = 1.0                      │    │
│  │  Central bank feeds:   weight = 1.5 (highest authority)  │    │
│  │  ForexFactory:         weight = 0.8                      │    │
│  │  Social media:         weight = 0.3                      │    │
│  │  Unknown sources:      weight = 0.1                      │    │
│  │                                                          │    │
│  │  Final = Σ(sentiment_i × source_weight_i × recency_i)   │    │
│  │  Sentiment Momentum = ΔSentiment / Δt (rate of change)   │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### 3.3 FinBERT Fine-Tuning Strategy

```python
# Fine-tuning pipeline for forex-specific sentiment

TRAINING_DATA_SOURCES:
  1. Financial PhraseBank (Malo et al., 2014) — 4,840 labeled sentences
  2. Forex Factory news threads (manually labeled, 5,000+ articles)
  3. Central bank statements (FOMC, ECB, BOJ, BOE — 500+ documents)
  4. Reuters forex headlines (labeled by price reaction within 1h)
  
FINE-TUNING_CONFIG:
  base_model: "ProsusAI/finbert"
  epochs: 3
  learning_rate: 2e-5
  batch_size: 16
  max_length: 512
  warmup_steps: 500
  weight_decay: 0.01
  
EVALUATION_METRICS:
  - Accuracy: > 85% on held-out forex test set
  - F1 (macro): > 0.83
  - Calibration: Brier score < 0.15 (confidence matches accuracy)
  
RETRAINING_SCHEDULE:
  - Weekly: Online learning on newly labeled articles (100-200 samples)
  - Monthly: Full retrain with expanded corpus
  - Quarterly: Architecture review (consider larger model if accuracy plateaus)
```

### 3.4 Sentiment → Trade Signal Integration

```python
class SentimentSignalGenerator:
    """Converts FinBERT output into trade-ready signals."""
    
    def generate_signal(self, sentiment_scores: dict, 
                        event_context: dict) -> SentimentSignal:
        
        # Aggregate sentiment across sources
        agg_score = self._weighted_aggregate(sentiment_scores)
        
        # Calculate sentiment momentum (rate of change)
        momentum = self._calc_momentum(agg_score, self.history)
        
        # Event proximity adjustment
        if event_context['high_impact_within_4h']:
            # Pre-event: sentiment is leading indicator
            confidence_mult = 1.3
        else:
            confidence_mult = 1.0
        
        # Generate signal
        return SentimentSignal(
            direction='BULLISH' if agg_score > 0.2 else 'BEARISH' if agg_score < -0.2 else 'NEUTRAL',
            strength=abs(agg_score),
            momentum=momentum,
            confidence=min(abs(agg_score) * confidence_mult, 1.0),
            event_risk=event_context['event_risk_score'],
            source_breakdown=sentiment_scores
        )
```

---

## 4. LSTM & Transformer — Price Prediction

### 4.1 LSTM for Sequential Price Prediction

#### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    LSTM PRICE PREDICTOR                       │
│                                                               │
│  Input Layer (50–200 time steps × 30+ features):             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  OHLCV (5) + Indicators (15) + Cross-asset (5)     │    │
│  │  + Session features (3) + Sentiment (2)              │    │
│  └──────────────────────────┬──────────────────────────┘    │
│                             ▼                                │
│  LSTM Layer 1: 128 units, return_sequences=True             │
│  BatchNorm → Dropout(0.3)                                   │
│                             ▼                                │
│  Attention Layer: Self-attention over time steps             │
│  (focuses on most informative bars)                          │
│                             ▼                                │
│  LSTM Layer 2: 64 units, return_sequences=False             │
│  BatchNorm → Dropout(0.2)                                   │
│                             ▼                                │
│  Dense Layer: 32 units, ReLU                                │
│  Dropout(0.2)                                                │
│                             ▼                                │
│  Output Heads:                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Direction   │  │  Return      │  │  Volatility  │     │
│  │  (3 classes) │  │  (regression)│  │  (regression)│     │
│  │  softmax     │  │  linear      │  │  softplus    │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│                                                               │
│  Loss: Multi-task = 0.4×CE(direction) + 0.3×MSE(return)    │
│        + 0.3×MSE(volatility)                                 │
│  Optimizer: AdamW (lr=1e-3, wd=1e-4)                        │
│  Scheduler: CosineAnnealingWarmRestarts                     │
└─────────────────────────────────────────────────────────────┘
```

#### LSTM Model Variants

| Variant | Sequence Length | Hidden Units | Timeframe | Purpose |
|---------|----------------|-------------|-----------|---------|
| **LSTM-Micro** | 50 bars | 64 | M15 | Scalping signals, < 1ms inference |
| **LSTM-Standard** | 100 bars | 128 | H1 | Intraday prediction |
| **LSTM-Swing** | 200 bars | 256 | H4/D1 | Swing trade signals |
| **LSTM-Vol** | 100 bars | 64 | All | Volatility forecasting (GARCH replacement) |

#### Training Protocol

```python
TRAINING_CONFIG:
  # Data preparation
  lookback: 100  # bars
  forecast: 10   # bars ahead
  features: 30   # OHLCV + indicators + cross-asset + session + sentiment
  train_split: 0.7
  val_split: 0.15
  test_split: 0.15
  
  # Walk-forward validation (respects temporal ordering)
  walk_forward:
    train_window: 252 days  # ~1 year
    test_window: 63 days    # ~3 months
    step: 21 days           # ~1 month
    min_train_samples: 50000
  
  # Hyperparameters
  batch_size: 256
  epochs: 100
  early_stopping_patience: 15
  learning_rate: 1e-3
  lr_scheduler: "cosine_annealing"
  
  # Regularization
  dropout: 0.3
  weight_decay: 1e-4
  gradient_clip: 1.0
  
  # Class weights (handle imbalanced up/down/flat)
  class_weights: {UP: 1.2, DOWN: 1.2, FLAT: 0.6}
```

### 4.2 Transformer for Multi-Timeframe Analysis

#### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                 MULTI-TIMEFRAME TRANSFORMER                          │
│                                                                       │
│  Input Embedding:                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Per-timeframe features (M15, H1, H4, D1):                 │    │
│  │    OHLCV (5) + Indicators (10) = 15 features per TF        │    │
│  │  Total: 15 × 4 = 60 features                               │    │
│  │  + Positional encoding (time-of-day, day-of-week)           │    │
│  │  + Asset embedding (EURUSD, GBPUSD, etc.)                   │    │
│  └──────────────────────────┬──────────────────────────────────┘    │
│                             ▼                                        │
│  Multi-Head Self-Attention (8 heads, d_model=256):                   │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Cross-timeframe attention: M15 attends to H1, H4, D1      │    │
│  │  Cross-asset attention: EURUSD attends to GBPUSD, DXY      │    │
│  │  Temporal attention: Recent bars attend to historical bars  │    │
│  └──────────────────────────┬──────────────────────────────────┘    │
│                             ▼                                        │
│  Feed-Forward Network (d_ff=1024, ReLU, Dropout=0.1):               │
│                             ▼                                        │
│  LayerNorm → Residual Connection                                     │
│                             ▼                                        │
│  (Repeat × 4 encoder layers)                                         │
│                             ▼                                        │
│  Classification Head:                                                │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Direction probability (Bullish / Bearish / Neutral)        │    │
│  │  + Confidence score                                         │    │
│  │  + Expected move magnitude (ATR multiples)                  │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  Efficient Attention: Linformer (O(n) instead of O(n²))             │
│  Context Window: 1024 time steps                                      │
│  Inference Latency: < 200ms (CPU)                                     │
└─────────────────────────────────────────────────────────────────────┘
```

#### Transformer vs LSTM Selection

| Criterion | LSTM | Transformer | Winner |
|-----------|------|-------------|--------|
| Sequential dependencies | Strong (inherent) | Learned (attention) | LSTM (slight) |
| Long-range dependencies | Weak (vanishing gradient) | Strong (direct attention) | Transformer |
| Parallelization | Poor (sequential) | Excellent | Transformer |
| Training speed | Slow | Fast | Transformer |
| Inference latency | Fast (small models) | Medium | LSTM |
| Cross-asset reasoning | Manual feature engineering | Built-in attention | Transformer |
| Data efficiency | Good with small data | Needs more data | LSTM |

**Decision:** Use LSTM for single-asset, single-timeframe prediction (Tier 2 latency). Use Transformer for multi-asset, multi-timeframe analysis (Tier 3 latency). Both serve different roles in the pipeline.

---

## 5. Hidden Markov Model — Regime Detection

### 5.1 HMM Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    HMM REGIME DETECTOR                            │
│                                                                   │
│  States (Hidden):                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  STATE 0:    │  │  STATE 1:    │  │  STATE 2:    │          │
│  │  BULL TREND  │  │  BEAR TREND  │  │  RANGE/CHOP  │          │
│  │              │  │              │  │              │          │
│  │  High returns│  │  Low returns │  │  Low vol,    │          │
│  │  Rising vol  │  │  Rising vol  │  │  mean-revert │          │
│  │  Strong ADX  │  │  Strong ADX  │  │  Weak ADX    │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                  │                  │                  │
│         └──────────────────┼──────────────────┘                  │
│                            ▼                                      │
│  Transition Matrix (learned from data):                          │
│              To Bull    To Bear    To Range                       │
│  From Bull   [0.85      0.05       0.10]                        │
│  From Bear   [0.08      0.82       0.10]                        │
│  From Range  [0.15      0.15       0.70]                        │
│                                                                   │
│  Observation Features (5 dimensions):                            │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  1. 20-period return (drift direction)                   │    │
│  │  2. Realized volatility (20d annualized)                 │    │
│  │  3. ATR ratio (fast/slow = 14/50)                        │    │
│  │  4. ADX (trend strength)                                 │    │
│  │  5. Volume ratio (20d/50d average)                       │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│  Output:                                                          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  regime: "BULL_TREND"                                    │    │
│  │  confidence: 0.82                                        │    │
│  │  state_probabilities: {bull: 0.82, bear: 0.08, range: 0.10}│   │
│  │  persistence_estimate: 12 days remaining                 │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Ensemble Regime Detection (Production)

```python
class EnsembleRegimeDetector:
    """
    Combines 4 methods for robust regime detection.
    Requires consensus for high-confidence regime classification.
    """
    
    def __init__(self):
        self.rules_engine = RulesBasedRegime()      # weight: 0.4
        self.hmm_detector = HMMRegime(n_states=3)   # weight: 0.3
        self.vol_filter = VolatilityRegime()         # weight: 0.2
        self.ml_classifier = XGBoostRegime()         # weight: 0.1
    
    def detect(self, market_data: DataFrame) -> RegimeState:
        # Run all detectors in parallel
        rules = self.rules_engine.classify(market_data)
        hmm = self.hmm_detector.predict(market_data)
        vol = self.vol_filter.classify(market_data)
        ml = self.ml_classifier.predict(market_data)
        
        # Weighted consensus
        regime_scores = {
            'BULL_TREND': (
                0.4 * rules['bull'] +
                0.3 * hmm['bull'] +
                0.2 * vol['bull'] +
                0.1 * ml['bull']
            ),
            'BEAR_TREND': (
                0.4 * rules['bear'] +
                0.3 * hmm['bear'] +
                0.2 * vol['bear'] +
                0.1 * ml['bear']
            ),
            'RANGE': (
                0.4 * rules['range'] +
                0.3 * hmm['range'] +
                0.2 * vol['range'] +
                0.1 * ml['range']
            )
        }
        
        # Consensus check
        best_regime = max(regime_scores, key=regime_scores.get)
        confidence = regime_scores[best_regime]
        
        # Agreement count
        detectors = [rules, hmm, vol, ml]
        agreements = sum(1 for d in detectors 
                        if max(d, key=d.get) == best_regime)
        
        return RegimeState(
            regime=best_regime,
            confidence=confidence,
            agreement_count=agreements,
            soft_weights=self._compute_soft_weights(regime_scores),
            persistence=self.hmm_detector.estimate_persistence(best_regime)
        )
    
    def _compute_soft_weights(self, scores: dict) -> dict:
        """Soft strategy weights based on regime probabilities."""
        # Crisis amplification: always overweight defensive
        weights = {
            'trend_weight': scores['BULL_TREND'] + scores['BEAR_TREND'],
            'mr_weight': scores['RANGE'],
            'defense_weight': scores.get('CRISIS', 0) * 2.0  # amplify crisis
        }
        # Normalize
        total = sum(weights.values())
        return {k: v/total for k, v in weights.items()}
```

### 5.3 HMM Retraining Schedule

| Frequency | Action | Trigger |
|-----------|--------|---------|
| **Daily** | Update observation features | New market data |
| **Weekly** | Recompute regime probabilities | Feature update |
| **Monthly** | Full HMM retrain | Calendar + performance degradation |
| **On-demand** | Emergency retrain | Log-likelihood drops > 20% from baseline |

### 5.4 Regime → Strategy Routing

```
REGIME DETECTED → STRATEGY ADAPTATION:

BULL_TREND (confidence > 0.7):
  ├── Trend following:     weight = 0.80
  ├── Mean reversion:      weight = 0.10
  ├── Defense:             weight = 0.10
  ├── RSI thresholds:      oversold=40, overbought=80
  ├── Stop loss:           wider (1.5× ATR buffer)
  ├── Take profit:         extended (trail with EMA21)
  └── Position sizing:     full Kelly × 1.2

BEAR_TREND (confidence > 0.7):
  ├── Trend following:     weight = 0.70 (short bias)
  ├── Mean reversion:      weight = 0.10
  ├── Defense:             weight = 0.20
  ├── RSI thresholds:      oversold=20, overbought=60
  ├── Stop loss:           tight (0.5× ATR buffer)
  ├── Take profit:         conservative (1.5R target)
  └── Position sizing:     0.7× Kelly

RANGE (confidence > 0.7):
  ├── Trend following:     weight = 0.10
  ├── Mean reversion:      weight = 0.80
  ├── Defense:             weight = 0.10
  ├── RSI thresholds:      oversold=30, overbought=70
  ├── Stop loss:           at range edges
  ├── Take profit:         opposite range edge
  └── Position sizing:     full Kelly × 1.0

UNCERTAIN (all < 0.5):
  ├── Trend following:     weight = 0.25
  ├── Mean reversion:      weight = 0.25
  ├── Defense:             weight = 0.50
  ├── Position sizing:     0.5× Kelly
  └── New entries:         RESTRICTED (high-conviction only)
```

---

## 6. Reinforcement Learning — Strategy Optimization

### 6.1 RL Agent Design

Alpha Stack uses three RL agents, each optimizing a different aspect of the trading pipeline:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    REINFORCEMENT LEARNING AGENTS                     │
│                                                                       │
│  AGENT 1: POSITION SIZING AGENT (PPO)                               │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  State: [confluence_score, regime, volatility, recent_wr,   │    │
│  │          session, correlation_exposure, drawdown, timeofday] │    │
│  │  Action: Position size multiplier [0.0, 2.0] (continuous)   │    │
│  │  Reward: Sharpe-adjusted return of individual trade          │    │
│  │  Policy: Gaussian (mean + std from neural network)           │    │
│  │  Training: PPO with GAE (λ=0.95, γ=0.99)                   │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  AGENT 2: TAKE-PROFIT AGENT (DQN)                                   │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  State: [current_R, time_in_trade, volatility_regime,       │    │
│  │          regime, atr, structure_alignment, session]          │    │
│  │  Actions:                                                     │    │
│  │    0: Hold (do nothing)                                      │    │
│  │    1: Close 25% at current price                             │    │
│  │    2: Close 50% at current price                             │    │
│  │    3: Close 100% at current price                            │    │
│  │    4: Move SL to breakeven                                   │    │
│  │    5: Move SL to 0.5R trail                                  │    │
│  │    6: Move SL to 1.0R trail                                  │    │
│  │  Reward: R-multiple achieved (normalized)                    │    │
│  │  Training: Double DQN with prioritized experience replay     │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  AGENT 3: EXECUTION AGENT (Q-Learning)                              │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  State: [order_book_imbalance, spread, volatility,           │    │
│  │          time_remaining, distance_to_level, urgency]         │    │
│  │  Actions:                                                     │    │
│  │    0: Market order (immediate)                               │    │
│  │    1: Limit order at current price                           │    │
│  │    2: Limit order at level + 0.1 ATR                         │    │
│  │    3: Limit order at level + 0.3 ATR                         │    │
│  │    4: Wait (do nothing this tick)                            │    │
│  │  Reward: Negative slippage (execution_price vs VWAP)         │    │
│  │  Training: Tabular Q-learning (discretized state space)      │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

### 6.2 PPO Training Configuration (Position Sizing)

```python
PPO_CONFIG:
  # Environment
  env: "AlphaTradingEnv"  # Custom Gym environment wrapping backtester
  observation_space: Box(low=-inf, high=inf, shape=(12,))  # 12 state features
  action_space: Box(low=0.0, high=2.0, shape=(1,))  # continuous multiplier
  
  # Hyperparameters
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
  
  # Network architecture
  policy_net: [64, 64]  # Two hidden layers, 64 units each
  value_net: [64, 64]
  activation: ReLU
  
  # Training schedule
  total_timesteps: 1_000_000
  eval_freq: 10_000
  n_eval_episodes: 100
  
  # Reward shaping
  reward_function: |
    def reward(trade_result):
      r_multiple = trade_result.r_multiple
      sharpe_component = trade_result.sharpe_contribution
      drawdown_penalty = -0.5 * max(0, trade_result.drawdown - 0.05)
      return r_multiple * 0.6 + sharpe_component * 0.3 + drawdown_penalty * 0.1
```

### 6.3 Training Data for RL

```
TRAINING PIPELINE:

Phase 1: Backtest-Based Training (Offline)
  ├── Run backtester on 3+ years of historical data
  ├── Record (state, action, reward, next_state) for every decision point
  ├── Store in replay buffer (1M+ transitions)
  └── Train RL agent on collected trajectories

Phase 2: Simulator-Based Training (Online)
  ├── GAN-generated synthetic market data (extends training distribution)
  ├── Stochastic simulation with realistic market microstructure
  ├── Inject rare events (flash crashes, liquidity gaps)
  └── Train agent on diverse scenarios

Phase 3: Live Fine-Tuning (Shadow Mode)
  ├── Agent observes live trades but doesn't execute
  ├── Records its recommended actions vs. actual actions
  ├── Evaluates: "Would the RL agent have done better?"
  └── Fine-tunes on live distribution shift

Phase 4: Live Deployment (Gradual)
  ├── Start with 10% of position sizing decisions
  ├── Monitor performance vs. rule-based baseline
  ├── Gradually increase authority as confidence grows
  └── Always maintain rule-based fallback
```

### 6.4 RL Safety Constraints

```python
class SafeRLWrapper:
    """Wraps RL agent with hard safety constraints that cannot be overridden."""
    
    def __init__(self, rl_agent, risk_config):
        self.agent = rl_agent
        self.risk = risk_config
    
    def get_action(self, state):
        # Get RL recommendation
        rl_action = self.agent.predict(state)
        
        # Apply hard constraints (NEVER overridden by RL)
        safe_action = rl_action
        
        # Constraint 1: Maximum position size
        safe_action = min(safe_action, self.risk.max_position_mult)
        
        # Constraint 2: Reduce after consecutive losses
        if state['consecutive_losses'] >= 3:
            safe_action = min(safe_action, 0.5)
        
        # Constraint 3: Reduce in high drawdown
        if state['current_drawdown'] > 0.10:
            safe_action = min(safe_action, 0.3)
        
        # Constraint 4: Reduce in uncertain regime
        if state['regime_confidence'] < 0.4:
            safe_action = min(safe_action, 0.5)
        
        # Constraint 5: Never go below minimum
        safe_action = max(safe_action, 0.1)
        
        return safe_action
```

---

## 7. LLM Integration — Fundamental Analysis & Reasoning

### 7.1 LLM Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    LLM INTEGRATION ARCHITECTURE                      │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    REASONING LLM (DeepSeek-R1 / QwQ)        │    │
│  │  Role: Complex fundamental analysis, macro synthesis         │    │
│  │  Trigger: Pre-session + on high-impact events                │    │
│  │  Latency: 3–10s                                              │    │
│  │  Context: RAG (financial knowledge base + real-time news)    │    │
│  │                                                              │    │
│  │  Tasks:                                                      │    │
│  │  • "Should I trade today?" fundamental assessment            │    │
│  │  • Central bank statement interpretation                     │    │
│  │  • Geopolitical risk assessment                              │    │
│  │  • Cross-asset correlation reasoning                         │    │
│  │  • Trade thesis generation and validation                    │    │
│  └──────────────────────────┬──────────────────────────────────┘    │
│                             │                                        │
│  ┌──────────────────────────▼──────────────────────────────────┐    │
│  │                    FAST LLM (Qwen-2.5-7B / DeepSeek-V3)    │    │
│  │  Role: Quick classification, structured extraction           │    │
│  │  Trigger: Every analysis cycle                               │    │
│  │  Latency: 0.5–2s                                             │    │
│  │                                                              │    │
│  │  Tasks:                                                      │    │
│  │  • News headline classification (event type)                 │    │
│  │  • Entity extraction (who, what, when, impact)               │    │
│  │  • Quick sentiment override for complex headlines            │    │
│  │  • Pattern description generation                            │    │
│  │  • Trade rationale summarization                             │    │
│  └──────────────────────────┬──────────────────────────────────┘    │
│                             │                                        │
│  ┌──────────────────────────▼──────────────────────────────────┐    │
│  │                    RAG PIPELINE                               │    │
│  │                                                              │    │
│  │  Knowledge Base:                                             │    │
│  │  • Financial encyclopedia (macro concepts, central bank)     │    │
│  │  • Historical event database (NFP surprises, rate decisions) │    │
│  │  • Strategy documentation (Alpha Stack strategy rules)       │    │
│  │  • Trade journal (past trades, lessons learned)              │    │
│  │  • Market structure notes (pair-specific observations)       │    │
│  │                                                              │    │
│  │  Retrieval: Vector search (SQLite + FTS5 or LanceDB)        │    │
│  │  Embedding: BGE-small-en-v1.5 (fast, 384-dim)               │    │
│  │  Chunk size: 512 tokens, overlap: 64 tokens                 │    │
│  │  Top-k: 5 most relevant chunks per query                     │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    GUARDRAILS                                 │    │
│  │                                                              │    │
│  │  • LLM output is NEVER the final decision — it's ONE input  │    │
│  │  • All LLM outputs include confidence + reasoning chain      │    │
│  │  • Low-confidence LLM outputs are flagged for human review   │    │
│  │  • LLM cannot override risk rules (infrastructure-level)     │    │
│  │  • Hallucination detection: cross-reference with structured  │    │
│  │    data; flag if LLM claims facts not in knowledge base      │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

### 7.2 LLM Prompt Templates

#### Fundamental Analysis Prompt

```
SYSTEM: You are a senior forex/crypto macro analyst. Analyze the current 
market environment and provide a structured assessment. Be precise with 
numbers. If uncertain, state your uncertainty explicitly.

CONTEXT:
- Current date: {date}
- Trading pair: {pair}
- Current regime: {regime} (confidence: {regime_confidence})
- Recent price action: {price_summary}
- Economic calendar today: {calendar_events}
- Recent news headlines: {news_headlines}
- Current sentiment score: {sentiment_score}

TASK: Provide a "Should I Trade Today?" assessment.

REQUIRED OUTPUT FORMAT:
{
  "fundamental_bias": "BULLISH|BEARISH|NEUTRAL",
  "confidence": 0.0-1.0,
  "event_risk_score": 0.0-1.0,
  "key_factors": ["factor1", "factor2", ...],
  "reasoning": "Chain-of-thought explanation",
  "recommendation": "TRADE|WAIT|AVOID",
  "risk_notes": "Specific risks to monitor"
}
```

#### News Interpretation Prompt

```
SYSTEM: You are a financial news analyst specializing in central bank 
policy and macroeconomic events. Interpret the following news in context.

NEWS: {headline}
FULL TEXT: {article_text}
CURRENT CONTEXT: {macro_context}

ANALYSIS REQUIRED:
1. What was expected vs. what actually happened?
2. What does this imply for future policy/market direction?
3. What is the expected market impact (direction, magnitude, timeframe)?
4. How does this interact with current market regime?

OUTPUT: Structured JSON with direction, confidence, impact_estimate, reasoning.
```

### 7.3 LLM Cost Management

| Scenario | Model | Estimated Tokens/Day | Cost/Day |
|----------|-------|---------------------|----------|
| Pre-session fundamental check | Reasoning LLM | 5K | $0.05 |
| News classification (continuous) | Fast LLM | 10K | $0.03 |
| High-impact event analysis | Reasoning LLM | 3K per event | $0.03 |
| Trade rationale generation | Fast LLM | 2K | $0.01 |
| Weekly performance review | Reasoning LLM | 10K | $0.10 |
| **Total daily** | | **~30K** | **~$0.22** |

---

## 8. Model Serving Architecture

### 8.1 Inference Pipeline

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    MODEL SERVING ARCHITECTURE                              │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    MODEL REGISTRY                                │    │
│  │  • Model artifacts stored in /models/ directory                  │    │
│  │  • Versioned: models/{model_name}/v{version}/                   │    │
│  │  • Formats: ONNX (XGBoost, LSTM), PyTorch (Transformer, FinBERT)│    │
│  │  • Metadata: training_date, metrics, feature_list, config       │    │
│  └──────────────────────────┬──────────────────────────────────────┘    │
│                             │                                            │
│  ┌──────────────────────────▼──────────────────────────────────────┐    │
│  │                    INFERENCE SERVER                               │    │
│  │                                                                   │    │
│  │  ┌─────────────────────────────────────────────────────────┐    │    │
│  │  │  ONNX Runtime (CPU)                                      │    │    │
│  │  │  • XGBoost/LightGBM classifiers (all signal models)      │    │    │
│  │  │  • LSTM models (small, < 64 units)                       │    │    │
│  │  │  • HMM regime detector                                    │    │    │
│  │  │  • Latency: < 10ms per inference                         │    │    │
│  │  └─────────────────────────────────────────────────────────┘    │    │
│  │                                                                   │    │
│  │  ┌─────────────────────────────────────────────────────────┐    │    │
│  │  │  PyTorch (CPU/GPU)                                       │    │    │
│  │  │  • FinBERT sentiment model                               │    │    │
│  │  │  • Transformer multi-TF model                            │    │    │
│  │  │  • CNN chart pattern model                               │    │    │
│  │  │  • Latency: 20–200ms per inference                       │    │    │
│  │  └─────────────────────────────────────────────────────────┘    │    │
│  │                                                                   │    │
│  │  ┌─────────────────────────────────────────────────────────┐    │    │
│  │  │  RL Policy Network (ONNX or PyTorch)                     │    │    │
│  │  │  • PPO position sizing policy                            │    │    │
│  │  │  • DQN take-profit policy                                │    │    │
│  │  │  • Q-table for execution (in-memory dict)                │    │    │
│  │  │  • Latency: < 5ms (policy forward pass)                  │    │    │
│  │  └─────────────────────────────────────────────────────────┘    │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    FEATURE STORE                                  │    │
│  │                                                                   │    │
│  │  • Pre-computed features stored in Redis                         │    │
│  │  • Updated on every new candle (M15 primary)                     │    │
│  │  • Features shared across all models (avoid redundant compute)   │    │
│  │  • Cache TTL: aligned with candle timeframe                      │    │
│  │                                                                   │    │
│  │  Feature groups:                                                  │    │
│  │  • raw_ohlcv: Latest 500 bars per instrument per timeframe      │    │
│  │  • indicators: RSI, MACD, ATR, ADX, BB, etc. (pre-computed)     │    │
│  │  • structure: Swing points, BOS/CHoCH, OB, FVG                  │    │
│  │  • sentiment: Latest aggregated sentiment scores                 │    │
│  │  • regime: Current regime state + probabilities                  │    │
│  │  • cross_asset: Correlation matrix, DXY, VIX, yields            │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    LLM CLIENT                                     │    │
│  │                                                                   │    │
│  │  • API client for DeepSeek/Qwen (cloud-hosted)                   │    │
│  │  • Local inference option: Ollama (self-hosted Qwen-2.5-7B)      │    │
│  │  • Retry logic with exponential backoff                          │    │
│  │  • Rate limiting: max 10 requests/minute                         │    │
│  │  • Response caching: identical queries cached for 1 hour         │    │
│  │  • Streaming for long responses                                  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────┘
```

### 8.2 Model Loading & Lifecycle

```python
class ModelManager:
    """
    Manages model loading, caching, and lifecycle.
    Models are loaded once at startup and cached in memory.
    """
    
    def __init__(self):
        self.models = {}
        self.feature_store = RedisFeatureStore()
    
    async def load_all_models(self):
        """Load all models at startup (parallel where possible)."""
        await asyncio.gather(
            self._load_onnx('xgboost_sr_scorer', 'models/sr_scorer/v2/model.onnx'),
            self._load_onnx('xgboost_sweep_classifier', 'models/sweep_cls/v1/model.onnx'),
            self._load_onnx('xgboost_smc_predictor', 'models/smc_pred/v1/model.onnx'),
            self._load_onnx('xgboost_confluence', 'models/confluence/v3/model.onnx'),
            self._load_onnx('lstm_price_standard', 'models/lstm_std/v2/model.onnx'),
            self._load_onnx('lstm_volatility', 'models/lstm_vol/v1/model.onnx'),
            self._load_pytorch('finbert', 'ProsusAI/finbert'),
            self._load_hmm('regime_hmm', 'models/regime_hmm/v2/model.pkl'),
            self._load_rl('ppo_sizing', 'models/ppo_sizing/v1/model.pkl'),
            self._load_rl('dqn_tp', 'models/dqn_tp/v1/model.pkl'),
        )
        logger.info(f"Loaded {len(self.models)} models")
    
    async def predict(self, model_name: str, features: dict) -> dict:
        """Run inference on a cached model."""
        model = self.models[model_name]
        
        # Check feature cache first
        cache_key = f"{model_name}:{hash(str(features))}"
        cached = await self.feature_store.get(cache_key)
        if cached:
            return cached
        
        # Run inference
        start = time.time()
        result = model.predict(features)
        latency_ms = (time.time() - start) * 1000
        
        # Cache result (TTL based on model type)
        ttl = self._get_cache_ttl(model_name)
        await self.feature_store.set(cache_key, result, ttl)
        
        # Log latency
        self._log_latency(model_name, latency_ms)
        
        return result
```

### 8.3 Performance Requirements

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

---

## 9. Model Versioning & A/B Testing

### 9.1 Versioning Schema

```
/models/
├── xgboost_confluence/
│   ├── v1/
│   │   ├── model.onnx              # Serialized model
│   │   ├── model.pkl               # Original Python model (for retraining)
│   │   ├── metadata.json           # Training date, metrics, config
│   │   ├── feature_list.json       # Ordered feature names
│   │   ├── training_config.yaml    # Full training configuration
│   │   └── evaluation_report.md    # Performance metrics, SHAP plots
│   ├── v2/
│   │   └── ...
│   └── production -> v2/           # Symlink to active version
│
├── lstm_price_standard/
│   ├── v1/
│   │   ├── model.onnx
│   │   ├── model.pt                # PyTorch checkpoint
│   │   ├── metadata.json
│   │   ├── scaler.pkl              # Feature scaler
│   │   └── evaluation_report.md
│   └── production -> v1/
│
├── regime_hmm/
│   ├── v1/
│   │   ├── model.pkl               # hmmlearn model
│   │   ├── scaler.pkl              # Feature scaler
│   │   ├── metadata.json
│   │   └── transition_matrix.json  # Human-readable transition probs
│   └── production -> v2/
│
└── ppo_sizing/
    ├── v1/
    │   ├── model.pkl               # Stable-baselines3 model
    │   ├── vec_normalize.pkl       # Observation normalization
    │   ├── metadata.json
    │   └── training_log.csv        # Training curve
    └── production -> v1/
```

### 9.2 Metadata Schema

```json
{
  "model_name": "xgboost_confluence",
  "version": 2,
  "training_date": "2026-07-10",
  "training_data_range": "2024-01-01 to 2026-06-30",
  "training_samples": 125000,
  "features": [
    "sr_score", "liquidity_sweep_strength", "ob_strength",
    "fvg_present", "bos_confirmed", "rsi_alignment",
    "candlestick_score", "volume_ratio", "session", "regime"
  ],
  "metrics": {
    "accuracy": 0.72,
    "precision": 0.70,
    "recall": 0.74,
    "f1": 0.72,
    "auc_roc": 0.78,
    "sharpe_ratio_backtest": 1.85,
    "max_drawdown_backtest": 0.12
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
  }
}
```

### 9.3 A/B Testing Framework

```
┌─────────────────────────────────────────────────────────────────────┐
│                    A/B TESTING FRAMEWORK                              │
│                                                                       │
│  PHASE 1: SHADOW MODE (1–2 weeks)                                   │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  • New model runs in parallel with production model          │    │
│  │  • New model predictions are LOGGED but NOT used             │    │
│  │  • Compare: accuracy, latency, edge cases                    │    │
│  │  • Gate: New model must match or exceed production metrics   │    │
│  │  • Human review: Analyze disagreements between models        │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  PHASE 2: CANARY (1–2 weeks)                                        │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  • New model handles 10% of traffic                          │    │
│  │  • Monitor: P&L impact, signal quality, latency              │    │
│  │  • Automatic rollback if: win rate drops > 5%,               │    │
│  │    latency P99 > threshold, or error rate > 1%               │    │
│  │  • Gradual ramp: 10% → 25% → 50% over 2 weeks              │    │
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
│  ROLLBACK TRIGGERS (automatic):                                      │
│  • Win rate drops > 5% from baseline                                 │
│  • P99 latency exceeds tier threshold for 5+ minutes                 │
│  • Error rate > 1% for 10+ minutes                                   │
│  • Max drawdown exceeds 8% in current regime                         │
│  • 3+ consecutive losing trades attributed to model                  │
└─────────────────────────────────────────────────────────────────────┘
```

### 9.4 Model Performance Monitoring

```python
class ModelMonitor:
    """Continuous monitoring of model performance in production."""
    
    def __init__(self):
        self.metrics_store = MetricsStore()
        self.alert_manager = AlertManager()
    
    async def log_prediction(self, model_name: str, prediction: dict, 
                             actual_outcome: dict = None):
        """Log prediction and compare to outcome when available."""
        
        await self.metrics_store.log({
            'model': model_name,
            'timestamp': datetime.utcnow(),
            'prediction': prediction,
            'actual': actual_outcome,
            'latency_ms': prediction.get('latency_ms'),
            'features_hash': prediction.get('features_hash')
        })
        
        # Check for degradation
        if actual_outcome:
            recent_accuracy = await self.metrics_store.get_accuracy(
                model_name, window=100
            )
            
            baseline = await self.metrics_store.get_baseline_accuracy(model_name)
            
            if recent_accuracy < baseline - 0.05:
                await self.alert_manager.send(
                    f"⚠️ Model {model_name} accuracy degraded: "
                    f"{recent_accuracy:.1%} vs baseline {baseline:.1%}",
                    priority="HIGH"
                )
    
    async def daily_report(self) -> dict:
        """Generate daily model performance report."""
        report = {}
        for model_name in self.models:
            report[model_name] = {
                'predictions_today': await self.metrics_store.count(model_name, 'today'),
                'accuracy_today': await self.metrics_store.get_accuracy(model_name, 'today'),
                'avg_latency_ms': await self.metrics_store.get_avg_latency(model_name, 'today'),
                'p99_latency_ms': await self.metrics_store.get_p99_latency(model_name, 'today'),
                'error_count': await self.metrics_store.get_errors(model_name, 'today'),
                'accuracy_trend_7d': await self.metrics_store.get_accuracy_trend(model_name, 7)
            }
        return report
```

---

## 10. Agent ↔ Model Integration

### 10.1 Agent-Model Binding Matrix

Each agent in the multi-agent system is bound to specific models. The binding defines which models an agent can call, with what frequency, and under what conditions.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    AGENT ↔ MODEL BINDING MATRIX                              │
│                                                                              │
│  Agent                  │ Models Used                    │ Call Pattern       │
│  ───────────────────────┼────────────────────────────────┼────────────────── │
│  Fundamental Agent      │ FinBERT, LLM (reasoning),      │ Pre-session +     │
│  (Step 1)               │ XGBoost (event impact)         │ on-event          │
│                         │                                │                    │
│  Structure Agent        │ HMM (regime), XGBoost          │ Every H4 candle   │
│  (Steps 2-4)            │ (bias classifier), LSTM        │ + session change   │
│                         │ (structure sequence)           │                    │
│                         │                                │                    │
│  S/R Agent              │ XGBoost (level quality),       │ Every D1 candle   │
│  (Step 5)               │ DBSCAN (clustering)            │                    │
│                         │                                │                    │
│  Liquidity Agent        │ Random Forest (flow),          │ Continuous +       │
│  (Step 6)               │ XGBoost (sweep classifier)     │ every M15          │
│                         │                                │                    │
│  SMC Agent              │ XGBoost (pattern success),     │ Every M15 candle   │
│  (Step 7)               │ LSTM (complex patterns)        │                    │
│                         │                                │                    │
│  Momentum Agent         │ XGBoost (RSI signal),          │ Every M15 candle   │
│  (Step 8)               │ HMM (adaptive thresholds)      │                    │
│                         │                                │                    │
│  Candlestick Agent      │ CNN (visual), XGBoost          │ Every candle close │
│  (Step 9)               │ (outcome predictor)            │                    │
│                         │                                │                    │
│  Entry Agent            │ XGBoost (confluence),          │ On signal          │
│  (Steps 10-11)          │ PPO (position sizing)          │ (score ≥ 60)       │
│                         │                                │                    │
│  Risk Gate Agent        │ NONE (pure code)               │ Every trade        │
│  (Step 12)              │                                │ proposal           │
│                         │                                │                    │
│  TP Agent               │ DQN (TP policy), LSTM          │ Every M15 candle   │
│  (Step 13)              │ (exit timing)                  │ (in-trade)         │
│                         │                                │                    │
│  Trade Mgmt Agent       │ LSTM (exit signal),            │ Continuous         │
│  (Steps 14-15)          │ XGBoost (early warning)        │ (in-trade)         │
│                         │                                │                    │
│  Execution Agent        │ Q-Table (execution),           │ On order           │
│  (Step 16 exec)         │ NONE (algorithmic)             │                    │
│                         │                                │                    │
│  Reflection Agent       │ LLM (reasoning), RL            │ Post-trade +       │
│  (Step 16 reflect)      │ (policy improvement)           │ daily/weekly       │
│                         │                                │                    │
│  Journal Agent          │ LLM (analysis), Clustering     │ Post-trade +       │
│  (Step 16 journal)      │ (pattern recognition)          │ daily/weekly       │
│                         │                                │                    │
│  Orchestrator Agent     │ ALL (via agent delegation)     │ Continuous         │
│  (Coordinator)          │                                │                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 10.2 Agent-Model Communication Protocol

```python
class AgentModelInterface:
    """
    Standardized interface for agents to call models.
    Handles caching, fallback, and monitoring.
    """
    
    def __init__(self, model_manager: ModelManager):
        self.mm = model_manager
        self.cache = PredictionCache()
        self.monitor = ModelMonitor()
    
    async def predict(self, agent_id: str, model_name: str, 
                      features: dict, context: dict = None) -> dict:
        """
        Agent calls model through this interface.
        Handles caching, fallback, and monitoring.
        """
        # 1. Check cache
        cache_key = self._build_cache_key(model_name, features)
        cached = await self.cache.get(cache_key)
        if cached and not self._is_stale(cached, model_name):
            return cached
        
        # 2. Run inference with timeout
        try:
            result = await asyncio.wait_for(
                self.mm.predict(model_name, features),
                timeout=self._get_timeout(model_name)
            )
        except asyncio.TimeoutError:
            # Fallback: use cached result or rule-based default
            result = await self._fallback(model_name, features)
            await self.monitor.log_timeout(agent_id, model_name)
        
        except Exception as e:
            result = await self._fallback(model_name, features)
            await self.monitor.log_error(agent_id, model_name, str(e))
        
        # 3. Cache result
        ttl = self._get_cache_ttl(model_name)
        await self.cache.set(cache_key, result, ttl)
        
        # 4. Log for monitoring
        await self.monitor.log_prediction(
            agent_id=agent_id,
            model_name=model_name,
            prediction=result,
            features=features
        )
        
        return result
    
    async def _fallback(self, model_name: str, features: dict) -> dict:
        """Fallback when model inference fails."""
        fallbacks = {
            'xgboost_confluence': {'score': 0, 'confidence': 0, 'fallback': True},
            'hmm_regime': {'regime': 'UNCERTAIN', 'confidence': 0, 'fallback': True},
            'finbert': {'sentiment': 'NEUTRAL', 'confidence': 0, 'fallback': True},
            'lstm_price': {'direction': 'NEUTRAL', 'confidence': 0, 'fallback': True},
        }
        return fallbacks.get(model_name, {'error': 'no_fallback', 'fallback': True})
```

### 10.3 Model → Agent Signal Flow

```
SIGNAL FLOW: How model outputs become agent decisions

Model Output                    Agent Processing              Action
─────────────                   ──────────────────            ──────
FinBERT: {bullish: 0.8}   →    Fundamental Agent:            fundamental_bias = "BULLISH"
                                Multiply by source weight     confidence = 0.8
                                Check against event risk      event_risk = 0.2

HMM: {bull: 0.82}         →    Structure Agent:              regime = "BULL_TREND"
                                Route to strategy weights     trend_weight = 0.80
                                Set RSI thresholds            rsi_oversold = 40

XGBoost: {score: 0.72}    →    Signal Aggregator:            confluence_score = 72
                                Compare to thresholds         → "STANDARD POSITION"
                                Generate trade proposal       risk = 1.0%

PPO: {size_mult: 1.3}    →    Entry Agent:                  position_size × 1.3
                                Apply safety constraints      capped at 2.0
                                Calculate lot size            lots = 0.026

DQN: {action: "close_50%"} →   TP Agent:                     Execute partial close
                                Send to Execution Agent       order = close 50%
                                Log to Journal Agent          record management

LLM: {recommendation:     →    Fundamental Agent:            If "AVOID" → no trade
     "AVOID", reason:...}       Pass reasoning to human       Alert with reasoning
                                Store in memory               Update RAG knowledge
```

---

## 11. Training Data Requirements

### 11.1 Data Sources & Volumes

| Data Type | Source | Volume | Storage | Update Frequency |
|-----------|--------|--------|---------|-----------------|
| **OHLCV (forex)** | MT5 API, Dukascopy | 28 pairs × 5 TFs × 10 years | TimescaleDB | Real-time tick, M15 aggregate |
| **OHLCV (crypto)** | CCXT (Binance, Bybit) | Top 50 × 4 TFs × 5 years | TimescaleDB | Real-time |
| **Economic calendar** | MT5, ForexFactory | ~500 events/year | PostgreSQL | Daily |
| **News articles** | Finnhub, RSS feeds | ~10,000 articles/day | Elasticsearch | Real-time |
| **Order book snapshots** | Exchange WebSocket | Top 5 levels, every 1s | Redis (hot), S3 (cold) | Real-time |
| **On-chain data** | Coinglass, Glassnode | Liquidation, whale moves | PostgreSQL | Hourly |
| **Sentiment labels** | Manual + automated | 50,000+ labeled sentences | PostgreSQL | Weekly batch |
| **Trade journal** | System-generated | Every trade, full context | PostgreSQL + Vector DB | Per-trade |
| **Synthetic data** | GAN-generated | 10× real data volume | TimescaleDB | Monthly regeneration |

### 11.2 Training Data Schemas

#### Supervised Learning Data (XGBoost, LSTM, CNN)

```python
# Feature matrix for signal classification models
FEATURE_SCHEMA = {
    # Price-derived features (OHLCV + indicators)
    'price_features': [
        'open', 'high', 'low', 'close', 'volume',
        'rsi_14', 'rsi_7', 'macd', 'macd_signal', 'macd_hist',
        'atr_14', 'atr_7', 'adx_14', 'bb_upper', 'bb_lower', 'bb_pct',
        'ema_21', 'ema_50', 'ema_200', 'sma_20',
        'stoch_k', 'stoch_d', 'cci_20', 'mfi_14', 'williams_r',
        'obv', 'vwap'
    ],
    
    # Structure features
    'structure_features': [
        'swing_high_distance', 'swing_low_distance',
        'bos_type', 'choch_type', 'bos_strength',
        'ob_type', 'ob_strength', 'ob_age',
        'fvg_present', 'fvg_size', 'fvg_filled_pct',
        'sr_score', 'sr_touch_count', 'sr_recency',
        'chop_score', 'adx', 'bb_width'
    ],
    
    # Context features
    'context_features': [
        'session', 'hour_of_day', 'day_of_week',
        'regime', 'regime_confidence',
        'sentiment_score', 'sentiment_momentum',
        'event_risk_score',
        'volume_ratio_20_50', 'volatility_ratio_14_50'
    ],
    
    # Cross-asset features
    'cross_asset_features': [
        'dxy_return_1h', 'dxy_return_4h',
        'vix_level', 'vix_change',
        'us10y_yield', 'us10y_change',
        'correlation_dxy', 'correlation_sp500'
    ],
    
    # Target
    'target': 'forward_return_class'  # UP / DOWN / FLAT (next 10 bars)
}

# Total features: ~50-60 per sample
# Minimum training samples: 50,000 (1 year of M15 data across pairs)
# Recommended: 200,000+ (3+ years)
```

#### RL Training Data

```python
RL_TRANSITION_SCHEMA = {
    'state': {
        'confluence_score': float,       # 0-100
        'regime': str,                    # BULL/BEAR/RANGE
        'regime_confidence': float,       # 0-1
        'volatility_regime': str,         # LOW/NORMAL/HIGH/EXTREME
        'session': str,                   # ASIAN/LONDON/NY/OVERLAP
        'recent_win_rate': float,         # Last 10 trades
        'consecutive_losses': int,        # Current streak
        'current_drawdown': float,        # % from peak
        'correlation_exposure': float,    # Effective correlated risk
        'time_of_day': float,             # 0-1 normalized
        'atr_percentile': float,          # Current ATR vs 1-year range
        'distance_to_level': float,       # ATR multiples to nearest S/R
    },
    'action': float,                      # Position size multiplier (0-2)
    'reward': float,                      # Sharpe-adjusted R-multiple
    'next_state': dict,                   # Same schema as state
    'done': bool                          # Trade completed?
}

# Minimum transitions: 100,000 (500+ trades × 200 decision points each)
# Recommended: 1,000,000+ (for stable PPO training)
```

### 11.3 Data Quality Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DATA QUALITY PIPELINE                              │
│                                                                       │
│  INGESTION LAYER:                                                    │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  • Validate OHLCV: H≥L, H≥max(O,C), L≤min(O,C)           │    │
│  │  • Detect gaps: Missing candles, exchange outages           │    │
│  │  • Deduplicate: Same tick from multiple sources             │    │
│  │  • Timestamp normalization: All to UTC                      │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  CLEANING LAYER:                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  • Outlier detection: Z-score > 4 on returns → flag         │    │
│  │  • Gap filling: Forward-fill small gaps (< 3 candles)       │    │
│  │  • Split/dividend adjustment (crypto: none needed)          │    │
│  │  • Session boundary alignment                               │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  FEATURE LAYER:                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  • Compute all technical indicators (vectorized)            │    │
│  │  • Compute cross-asset features                             │    │
│  │  • Compute rolling statistics                               │    │
│  │  • Normalize: Z-score per feature (rolling 1-year)          │    │
│  │  • Handle NaN: Forward-fill then drop remaining             │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  LABELING LAYER:                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  • Forward return classification: UP/DOWN/FLAT               │    │
│  │  • Label horizon: 10 bars (configurable per model)           │    │
│  │  • Threshold: ±0.5× ATR for UP/DOWN, else FLAT              │    │
│  │  • Purge: Remove labels within 5 bars of major events       │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  VALIDATION LAYER:                                                   │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  • Walk-forward split: Train (70%) → Val (15%) → Test (15%) │    │
│  │  • NO future data leakage (strict temporal ordering)         │    │
│  │  • Purged cross-validation (5-bar gap between train/test)   │    │
│  │  • Distribution shift detection: KS test between train/test  │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

### 11.4 Training Schedule

| Model | Initial Training | Retraining Trigger | Retrain Frequency |
|-------|-----------------|-------------------|-------------------|
| **FinBERT** | 50K labeled sentences | New labeled data (500+) | Weekly (online), Monthly (full) |
| **XGBoost (signals)** | 200K samples, 3yr data | Accuracy drops > 5% | Monthly |
| **LSTM (price)** | 500K samples, walk-forward | Performance degradation | Monthly |
| **Transformer** | 1M samples, multi-asset | Quarterly calendar | Quarterly |
| **HMM (regime)** | 5yr data, 3 states | Log-likelihood drop > 20% | Monthly |
| **PPO (sizing)** | 1M transitions | New market regime | Monthly |
| **DQN (TP)** | 500K transitions | Performance review | Monthly |
| **CNN (patterns)** | 50K labeled charts | New pattern types | Quarterly |

---

## 12. Implementation Roadmap

### Phase 1: Foundation Models (Weeks 1–4)

```
□ Set up model serving infrastructure (ONNX Runtime, PyTorch)
□ Implement feature store (Redis-based)
□ Implement model registry (/models/ directory structure)
□ Train and deploy HMM regime detector (3-state)
□ Train and deploy XGBoost confluence scorer
□ Train and deploy FinBERT sentiment model (fine-tuned on forex corpus)
□ Implement AgentModelInterface (caching, fallback, monitoring)
□ Implement ModelMonitor (latency, accuracy tracking)
□ Validate: All Tier 1-2 models running with < 50ms P99 latency
```

### Phase 2: Prediction Models (Weeks 5–8)

```
□ Train and deploy LSTM price predictor (Standard variant)
□ Train and deploy XGBoost sweep classifier
□ Train and deploy XGBoost SMC pattern predictor
□ Train and deploy XGBoost RSI signal model
□ Train and deploy XGBoost S/R level scorer
□ Implement walk-forward validation pipeline
□ Implement SHAP explainability for all XGBoost models
□ Validate: Prediction models achieving target accuracy metrics
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
□ Validate: RL agents matching or exceeding rule-based baseline
```

### Phase 4: LLM & Continuous Learning (Weeks 13–16)

```
□ Implement RAG pipeline (vector DB + knowledge base)
□ Deploy reasoning LLM for fundamental analysis
□ Deploy fast LLM for news classification
□ Implement A/B testing framework (shadow → canary → production)
□ Implement closed learning loop (trade outcomes → model updates)
□ Implement automated retraining pipeline
□ Implement model versioning and rollback
□ Validate: Full pipeline running end-to-end with all models
```

### Phase 5: Optimization & Scaling (Weeks 17+)

```
□ Optimize inference latency (ONNX optimization, quantization)
□ Implement CNN chart pattern recognition (optional)
□ Implement Transformer multi-timeframe model
□ Implement GAN synthetic data generation
□ Optimize model ensemble weights based on live performance
□ Scale to multi-instrument (crypto + forex)
□ Implement model performance attribution (which models add most value?)
□ Continuous monitoring and improvement
```

---

## Appendix A: Model Performance Targets

| Model | Metric | Target | Minimum Acceptable |
|-------|--------|--------|--------------------|
| **FinBERT** | Accuracy (forex test set) | > 85% | > 80% |
| **XGBoost (confluence)** | AUC-ROC | > 0.78 | > 0.72 |
| **XGBoost (sweep)** | Accuracy | > 75% | > 70% |
| **LSTM (price)** | Direction accuracy | > 58% | > 55% |
| **HMM (regime)** | State accuracy (labeled) | > 75% | > 70% |
| **PPO (sizing)** | Sharpe ratio vs rules | +15% | +5% |
| **DQN (TP)** | R-multiple improvement | +0.3R per trade | +0.1R |
| **LLM (fundamental)** | Human agreement | > 80% | > 70% |

## Appendix B: Cost Estimates

| Component | Monthly Cost | Notes |
|-----------|-------------|-------|
| **LLM API (DeepSeek/Qwen)** | $15–30 | ~30K tokens/day |
| **ONNX Runtime (CPU)** | $0 | Self-hosted |
| **PyTorch (CPU)** | $0 | Self-hosted |
| **Model storage** | $0 | Local disk |
| **Training compute** | $5–10 | Spot GPU instances for monthly retraining |
| **Data feeds** | $0–50 | Free tiers sufficient for start |
| **Total** | **$20–90/month** | Scales with account size |

## Appendix C: Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| XGBoost over deep learning for signals | XGBoost | Faster inference, better on tabular data, interpretable (SHAP) |
| HMM over ML for regime detection | HMM + ensemble | HMM captures temporal transitions; ensemble for robustness |
| PPO over other RL algorithms | PPO | Stable training, handles continuous actions, industry standard |
| ONNX over native PyTorch for inference | ONNX | 2-5× faster CPU inference, framework-agnostic |
| FinBERT over generic LLM for sentiment | FinBERT | Domain-specific, 100× faster, cheaper, sufficient accuracy |
| Local models over cloud APIs for inference | Local | Latency-critical path (< 50ms), no API dependency |
| Cloud LLM over local for reasoning | Cloud API | Reasoning quality matters more than latency for fundamental analysis |
| Soft regime switching over hard | Soft | 40-60% lower switching costs, smoother strategy transitions |

---

*Document generated: 2026-07-11*
*Author: AI Models Architect Agent — Alpha Stack*
*Status: Architecture Design Complete — Ready for Implementation Review*
*Next: Review with Multi-Agent Architecture team → Begin Phase 1 implementation*
