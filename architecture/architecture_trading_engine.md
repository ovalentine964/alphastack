# Alpha Stack — Trading Engine Architecture

## The Alpha Strategy: 16-Step Enhanced VMPM Trading System

**Version:** 1.0 | **Date:** 2026-07-11 | **Author:** Trading Engine Architect

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Module Design: 16 Steps](#2-module-design-16-steps)
3. [Signal Flow & Data Pipeline](#3-signal-flow--data-pipeline)
4. [Strategy Engine: Decision Making](#4-strategy-engine-decision-making)
5. [Multi-Agent System Integration](#5-multi-agent-system-integration)
6. [Broker Layer Integration](#6-broker-layer-integration)
7. [Backtesting Architecture](#7-backtesting-architecture)
8. [Live Trading Architecture](#8-live-trading-architecture)
9. [Technology Stack](#9-technology-stack)
10. [Deployment & Operations](#10-deployment--operations)

---

## 1. Architecture Overview

### 1.1 Design Philosophy

The Alpha Strategy engine is built on four principles:

1. **Event-driven from day one** — Every module communicates via events on a message bus. No polling, no cron-based hacks.
2. **Module isolation** — Each of the 16 steps is an independent, testable module with a defined interface. Modules can be upgraded, swapped, or disabled without affecting others.
3. **AI-first, rule-guarded** — ML models generate signals; hard rules enforce risk limits. No model can override a risk cap.
4. **Replay everything** — Every tick, every decision, every order is recorded. The backtesting engine replays the exact same pipeline as live trading.

### 1.2 High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         ALPHA STACK TRADING ENGINE                        │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │                        DATA LAYER                                    │ │
│  │  Market Data ── News/Sentiment ── Economic Calendar ── On-Chain     │ │
│  └──────────────────────────────┬──────────────────────────────────────┘ │
│                                 │                                         │
│  ┌──────────────────────────────▼──────────────────────────────────────┐ │
│  │                    SIGNAL GENERATION LAYER                           │ │
│  │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐│ │
│  │  │ S1  │ │ S2  │ │ S3  │ │ S4  │ │ S5  │ │ S6  │ │ S7  │ │ S8  ││ │
│  │  │Fund.│ │Bias │ │Sess.│ │Struc│ │S/R  │ │Liq. │ │SMC  │ │RSI  ││ │
│  │  └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘│ │
│  │     └───────┴───────┴───────┴───────┴───────┴───────┴───────┘     │ │
│  │                                 │                                   │ │
│  │  ┌──────────────────────────────▼────────────────────────────────┐ │ │
│  │  │              CONFLUENCE ENGINE (S9 + S10)                     │ │ │
│  │  └──────────────────────────────┬────────────────────────────────┘ │ │
│  └─────────────────────────────────┼──────────────────────────────────┘ │
│                                    │                                     │
│  ┌─────────────────────────────────▼──────────────────────────────────┐ │
│  │                    EXECUTION LAYER                                   │ │
│  │  ┌─────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                      │ │
│  │  │ S11 │ │ S12  │ │ S13  │ │ S14  │ │ S15  │                      │ │
│  │  │Size │ │SL    │ │TP    │ │Mgmt  │ │Exit  │                      │ │
│  │  └──┬──┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘                      │ │
│  │     └───────┴────────┴────────┴────────┘                            │ │
│  └─────────────────────────────────┬──────────────────────────────────┘ │
│                                    │                                     │
│  ┌─────────────────────────────────▼──────────────────────────────────┐ │
│  │                    BROKER ABSTRACTION LAYER                         │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐              │ │
│  │  │ MT5      │ │ CCXT     │ │ REST API │ │ FIX      │              │ │
│  │  │Connector │ │Connector │ │Connector │ │Connector │              │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘              │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                    LEARNING LAYER (S16)                             │ │
│  │  Journal ── Analytics ── RL Agent ── Pattern Recognition           │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                    RISK GOVERNOR (Oversees All)                     │ │
│  │  Position Limits ── Drawdown Circuit Breakers ── Correlation Caps  │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
```

### 1.3 Core Data Structures

All modules communicate through standardized event types on the message bus:

```python
@dataclass
class MarketEvent:
    timestamp: datetime
    pair: str
    event_type: EventType  # TICK, CANDLE, NEWS, CALENDAR, ORDER_BOOK
    data: dict
    source: str

@dataclass
class SignalEvent:
    timestamp: datetime
    pair: str
    source_module: str  # "S1_FUNDAMENTAL", "S7_SMC", etc.
    signal_type: SignalType  # BIAS, LEVEL, PATTERN, CONFIRMATION, WARNING
    direction: Direction  # BULLISH, BEARISH, NEUTRAL
    strength: float  # 0.0 - 1.0
    confidence: float  # 0.0 - 1.0
    data: dict  # Module-specific payload
    ttl_seconds: int  # Signal expiry

@dataclass
class TradeOrder:
    timestamp: datetime
    pair: str
    direction: Direction
    order_type: OrderType  # MARKET, LIMIT, STOP
    lot_size: float
    entry_price: float
    stop_loss: float
    take_profits: list[TakeProfitLevel]
    confluence_score: float
    setup_grade: str  # A+, A, B, C
    metadata: dict  # Full signal chain for journal

@dataclass
class RiskCheck:
    approved: bool
    reason: str
    adjusted_lot_size: float | None
    max_allowed_risk: float
    current_exposure: float
    correlation_factor: float
```

---

## 2. Module Design: 16 Steps

### Module Interface Contract

Every module implements the same interface:

```python
class StrategyModule(ABC):
    """Base interface for all 16 strategy modules."""
    
    @abstractmethod
    async def initialize(self, config: dict) -> None:
        """Load models, connect data sources, warm up."""
        pass
    
    @abstractmethod
    async def process(self, event: MarketEvent | SignalEvent) -> list[SignalEvent]:
        """Process an incoming event, return zero or more signals."""
        pass
    
    @abstractmethod
    async def get_state(self) -> dict:
        """Return current module state for monitoring/debugging."""
        pass
    
    @abstractmethod
    async def shutdown(self) -> None:
        """Clean shutdown — save state, close connections."""
        pass
```

---

### S1 — Fundamental Intelligence Module

**Purpose:** Macro-level directional bias from economic data, news, and sentiment.

**Internal Architecture:**
```
┌─────────────────────────────────────────────────────┐
│              FUNDAMENTAL INTELLIGENCE MODULE          │
│                                                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │ Economic  │  │  News    │  │  Sentiment       │   │
│  │ Calendar  │  │  Feed    │  │  Engine          │   │
│  │ Parser    │  │  Ingest  │  │  (FinBERT + LLM) │   │
│  └────┬─────┘  └────┬─────┘  └────────┬─────────┘   │
│       └──────────────┼─────────────────┘              │
│                      ▼                                │
│         ┌────────────────────────┐                    │
│         │  Macro Context Builder │                    │
│         │  (RAG + Knowledge Graph)│                   │
│         └───────────┬────────────┘                    │
│                     ▼                                 │
│         ┌────────────────────────┐                    │
│         │  "Should I Trade?"     │                    │
│         │  Decision Matrix       │                    │
│         └────────────────────────┘                    │
└─────────────────────────────────────────────────────┘
```

**Key Components:**
- **Economic Calendar Parser** — Ingests MT5 calendar + ForexFactory, classifies event impact (NFP/CPI/FOMC = high, PMI/retail sales = medium)
- **News Ingestion Pipeline** — Finnhub API + RSS feeds + central bank RSS, deduplication, <30s latency
- **Sentiment Engine** — Layer 1: FinBERT classification (<100ms). Layer 2: LLM reasoning (DeepSeek/Qwen) for nuanced events when FinBERT confidence <0.7. Layer 3: Event impact scoring with Bayesian updating against historical reactions
- **"Should I Trade?" Matrix** — Composite score from event risk, sentiment strength, volatility regime, geopolitical risk → outputs FULL_POSITION / REDUCED_POSITION / NO_TRADE / AVOID_ALL

**Output Signals:**
```python
SignalEvent(
    source_module="S1_FUNDAMENTAL",
    signal_type=SignalType.BIAS,
    direction=Direction.BULLISH,  # or BEARISH, NEUTRAL
    strength=0.75,  # sentiment strength
    confidence=0.82,
    data={
        "fundamental_bias": "BULLISH",
        "volatility_forecast_pips": 85,
        "event_risk_score": 0.3,
        "sentiment_momentum": +0.6,
        "trade_decision": "FULL_POSITION",
        "high_impact_events_next_24h": [],
        "reasoning": "Dovish ECB + strong USD sentiment + low event risk"
    }
)
```

**Dependencies:** News API keys, Finnhub, economic calendar feed, FinBERT model weights, LLM endpoint.

**Self-Improvement:** Weekly FinBERT retraining on verified predictions. Monthly event impact database update. Source reliability tracking (de-weight inaccurate sources).

---

### S2 — Market Bias Module

**Purpose:** Combine fundamental bias (S1) + multi-timeframe technical structure (S4) + HMM regime detection into a unified directional bias.

**Internal Architecture:**
```
┌──────────────────────────────────────────────────────┐
│                   MARKET BIAS MODULE                   │
│                                                        │
│  ┌────────────────┐    ┌────────────────┐             │
│  │  Fundamental   │    │  Technical     │             │
│  │  Bias (S1)     │    │  Structure (S4)│             │
│  └───────┬────────┘    └───────┬────────┘             │
│          └──────────┬──────────┘                       │
│                     ▼                                  │
│  ┌────────────────────────────────────────┐           │
│  │  HMM Regime Detection (3-state)        │           │
│  │  States: BULL_TREND / BEAR_TREND / RANGE│          │
│  └──────────────────┬─────────────────────┘           │
│                     ▼                                  │
│  ┌────────────────────────────────────────┐           │
│  │  Bias Fusion Engine                    │           │
│  │  Dynamic alpha: fundamental vs technical│           │
│  │  Conflict resolution protocol          │           │
│  └──────────────────┬─────────────────────┘           │
│                     ▼                                  │
│  OUTPUT: bias + regime + confidence + conflict_flag    │
└──────────────────────────────────────────────────────┘
```

**Key Components:**
- **HMM Regime Detector** — 3-state Gaussian HMM trained on returns, volatility, ATR ratio, ADX, volume ratio. Posterior probability >0.7 = high confidence. Retrained weekly.
- **Multi-Timeframe Bias Engine** — W1(0.35) + D1(0.30) + H4(0.20) + H1(0.15) weighted structure analysis. Alignment score 0-1.
- **Dynamic Alpha** — Fundamental weight ranges 0.2-0.7 based on volatility regime and technical alignment. High vol → more fundamental weight. Strong multi-TF alignment → more technical weight.
- **Conflict Resolution** — Pre-event (<4h): defer fundamentals. Range regime + conflict: neutral/reduce. Strong conflict on both sides: wait.

**Output Signals:**
```python
SignalEvent(
    source_module="S2_MARKET_BIAS",
    signal_type=SignalType.BIAS,
    direction=Direction.BULLISH,
    strength=0.72,
    confidence=0.68,
    data={
        "market_bias": "BULLISH",
        "regime": "BULL_TREND",
        "regime_confidence": 0.81,
        "timeframe_alignment": 0.75,
        "conflict_flag": False,
        "timeframe_biases": {"W1": +1, "D1": +1, "H4": +1, "H1": 0}
    }
)
```

---

### S3 — Session Analysis Module

**Purpose:** Classify current trading session, track Asian range, provide session-specific parameters.

**Key Components:**
- **Session State Machine** — States: OFF_HOURS → ASIAN → TRANSITION → LONDON → OVERLAP_NY → NEW_YORK → WIND_DOWN. Driven by UTC clock.
- **Asian Range Tracker** — Continuous H/L tracking during 00:00-08:00 UTC. Classifies range width (TIGHT/NORMAL/WIDE) and estimates breakout probability.
- **Volatility Analyzer** — Real-time ATR vs session historical average. Classifies as EXPANDED/NORMAL/COMPRESSED.
- **Session Parameter Provider** — Each session has different max_trades, position_size_mult, stop_mult, preferred strategies.

**Session-Specific Rules:**

| Session | Max Trades | Size Mult | Stop Mult | Preferred Strategies |
|---------|-----------|-----------|-----------|---------------------|
| Asian | 2 | 0.5× | 0.8× | Range, mean reversion |
| London | 3 | 1.0× | 1.2× | Breakout, trend, Asian range break |
| LDN/NY Overlap | 2 | 0.8× | 1.5× | Momentum, news reaction |
| New York | 2 | 0.8× | 1.0× | Continuation, reversal at levels |
| Wind Down | 1 | 0.5× | 0.8× | Management only |
| Off Hours | 0 | 0.0× | — | No trading |

**Output Signals:**
```python
SignalEvent(
    source_module="S3_SESSION",
    signal_type=SignalType.CONTEXT,
    data={
        "current_session": "LONDON",
        "session_volatility_state": "NORMAL",
        "asian_range": {"high": 1.0920, "low": 1.0870, "pips": 50, "classification": "TIGHT"},
        "session_parameters": {max_trades: 3, size_mult: 1.0, ...},
        "optimal_window": True,
        "spread_multiplier": 0.8
    }
)
```

---

### S4 — Market Structure Module

**Purpose:** Detect swing highs/lows, BOS/CHoCH, trend state, chop/range conditions across multiple timeframes.

**Internal Architecture:**
```
┌──────────────────────────────────────────────────────┐
│                  MARKET STRUCTURE MODULE                │
│                                                        │
│  ┌─────────────────────────────────────────────┐      │
│  │  Adaptive Swing Detector (ATR-based lookback)│      │
│  └──────────────────┬──────────────────────────┘      │
│                     ▼                                  │
│  ┌─────────────────────────────────────────────┐      │
│  │  BOS/CHoCH Classifier                       │      │
│  │  BOS = continuation, CHoCH = reversal        │      │
│  └──────────────────┬──────────────────────────┘      │
│                     ▼                                  │
│  ┌─────────────────────────────────────────────┐      │
│  │  Multi-TF Structure Engine                   │      │
│  │  W1 ← D1 ← H4 ← H1 alignment scoring       │      │
│  └──────────────────┬──────────────────────────┘      │
│                     ▼                                  │
│  ┌─────────────────────────────────────────────┐      │
│  │  Chop Detector (ADX + BB Width + MA crosses) │      │
│  └─────────────────────────────────────────────┘      │
└──────────────────────────────────────────────────────┘
```

**Key Algorithms:**
- **Adaptive Swing Detection** — Lookback period scales with ATR ratio (current ATR / median ATR). Higher volatility = wider lookback = fewer, more significant swings.
- **BOS Detection** — In uptrend: price breaks above previous swing high → BOS bullish (continuation). In downtrend: price breaks below previous swing low → BOS bearish.
- **CHoCH Detection** — In uptrend: price breaks below previous swing low → CHoCH bearish (reversal). In downtrend: price breaks above previous swing high → CHoCH bullish.
- **Chop Score** — Composite of ADX (<20 = +0.4), BB width percentile (<0.2 = +0.3), MA cross count (>8 in 20 bars = +0.3). Score >0.6 = choppy.

**Reliability:** BOS ~58% continuation when aligned with HTF trend. CHoCH ~52% reversal rate but larger average moves. Volume confirmation raises both to ~65%.

**Output Signals:**
```python
SignalEvent(
    source_module="S4_STRUCTURE",
    signal_type=SignalType.STRUCTURE,
    data={
        "trend": "BULLISH",
        "latest_event": {"type": "BOS", "direction": "BULLISH", "price": 1.0920, "timeframe": "H4"},
        "alignment_score": 0.78,
        "chop_score": 0.25,
        "key_levels": [{"price": 1.0870, "type": "SUPPORT"}, {"price": 1.0950, "type": "RESISTANCE"}],
        "swing_highs": [...],
        "swing_lows": [...]
    }
)
```

---

### S5 — Support & Resistance Module

**Purpose:** Detect, score, and track multi-timeframe S/R levels using fractal clustering, volume profiles, and institutional data.

**Key Components:**
- **Fractal Cluster Detector** — Williams Fractals across M15-D1, cluster nearby fractals (within ATR×0.25), score by touch count × recency × TF diversity.
- **Volume Profile Engine** — POC, VAH, VAL, HVN, LVN from rolling 20/50/100-day profiles.
- **Institutional Level Detector** — Options GEX levels, dark pool activity zones, futures OI concentration.
- **Flip Tracker** — Monitors broken S/R for polarity flip (broken support → resistance). Confirms flip when price reacts at flipped level with >0.5 ATR bounce.

**Multi-TF Weighting:**

| Timeframe | Base Weight | Decay Rate |
|-----------|------------|------------|
| Monthly | 1.00 | 0.98/week |
| Weekly | 0.85 | 0.95/week |
| Daily | 0.70 | 0.90/week |
| H4 | 0.50 | 0.85/week |
| H1 | 0.30 | 0.80/week |
| M15 | 0.15 | 0.70/week |

**Confluence Multiplier:** 2 TFs ×1.5, 3 TFs ×2.0, 4+ TFs ×3.0.

**Output:** Ranked S/R levels with confidence scores [0-100], flip status, institutional overlay.

---

### S6 — Liquidity Detection Module

**Purpose:** Map liquidity pools, detect sweeps, classify real vs. fake sweeps, integrate order flow and on-chain data.

**Key Components:**
- **Liquidity Heatmap Builder** — Layer 1: S/R-based (retail stops). Layer 2: Order book depth. Layer 3: On-chain liquidation levels (crypto).
- **Order Flow Analyzer** — Large trade detection (>3σ), iceberg detection, sweep detection (aggressive orders consuming 3+ levels), absorption detection.
- **Sweep Classifier (ML)** — Random Forest model. Features: volume_ratio, rejection_strength, delta_flip, sr_score, displacement, time_at_level, candle_pattern. Target: REAL_SWEEP vs FAKE_SWEEP. Target accuracy >75%.

**Real vs. Fake Sweep:**
- **Real sweep:** Volume spike >2× avg, immediate strong rejection, delta flip, at high-scoring S/R, followed by displacement, aligned with HTF bias.
- **Fake sweep:** Low volume, price lingers at level, gradual move, no delta change, at low-scoring S/R, reverses quickly.

**On-Chain (Crypto):** Exchange netflow, whale wallet movements, funding rates, liquidation heatmap (Coinglass/Hyblock), stablecoin dominance.

**Output:** Liquidity heatmap, sweep signals with real/fake classification, institutional activity score.

---

### S7 — Smart Money Concepts Module

**Purpose:** Detect Order Blocks, Fair Value Gaps, Breaker/Mitigation Blocks, and compute confluence scores.

**Key Components:**
- **Order Block Detector** — Bullish OB: last bearish candle before impulsive bullish move (>1.5 ATR body, >70% body ratio). Bearish OB: mirror. Score by impulse size, volume ratio, displacement count.
- **FVG Detector** — Bullish FVG: candle[i].low > candle[i-2].high. Bearish FVG: mirror. Track fill percentage in real-time.
- **Breaker/Mitigation Tracker** — Failed OB becomes breaker block. Mitigated OB tracked for potential re-entry.
- **Confluence Scorer** — Base scores: OB +30, FVG +20, BOS +25, CHoCH +30, Breaker +20, Mitigation +15, Liquidity Sweep +25. Bonuses: OB+FVG overlap +15, BOS+OB +20, Sweep+OB +25, multi-TF +15/TF, volume +10.

**Pattern Reliability:**

| Pattern | Win Rate | Avg R:R | Best Context |
|---------|----------|---------|--------------|
| Liquidity Sweep + OB | 70-75% | 1:3.0 | H1-D1 |
| BOS + OB | 68-72% | 1:2.5 | Trend continuation |
| CHoCH + FVG | 62-67% | 1:3.0 | Trend reversal |
| OB (H4/D1) | 65-70% | 1:2.0 | Premium/discount zones |

**Failure Handling:** OB mitigated without reaction → mark weak, look for breaker pattern. FVG fully filled → invalidate. BOS followed by immediate CHoCH → fakeout, wait for second confirmation.

**ML Enhancement:** XGBoost classifier on candle features, impulse magnitude, volume, distance to S/R, RSI state, HTF alignment, time of day → pattern success probability.

---

### S8 — RSI Confirmation Module

**Purpose:** Adaptive RSI analysis with regime-based thresholds, multi-TF alignment, divergence detection, and composite momentum scoring.

**Key Components:**
- **Adaptive Threshold Engine** — Ranging: 30/70 (standard). Bullish trend: 40/80. Bearish trend: 20/60. Regime from HMM (S2) or ADX.
- **Multi-TF RSI Alignment** — M15(0.15) + H1(0.25) + H4(0.35) + D1(0.25) weighted scoring. Score >+0.5 = strong buy alignment, <-0.5 = strong sell.
- **Divergence Detector** — Regular bullish: price lower low + RSI higher low. Hidden bullish: price higher low + RSI lower low (trend continuation). Reliability scored historically.
- **Composite Momentum** — RSI(0.35) + StochRSI(0.20) + MFI(0.20) + CCI(0.15) + WilliamsR(0.10), normalized to [0,100]. <25 = strong oversold, >75 = strong overbought.
- **Contextual Enhancement** — RSI + volume context, + volatility context, + session timing, + candle pattern context.

**Output:** Confirmation level (STRONG/MODERATE/WEAK/NONE) based on alignment + divergence + composite + ML signal.

---

### S9 — Candlestick Confirmation Module

**Purpose:** Automated pattern detection with volume-weighted scoring and failure detection.

**Key Components:**
- **Pattern Detector** — Engulfing, hammer, morning/evening star, pin bar, shooting star. Detection via OHLC rules with configurable sensitivity.
- **Volume-Weighted Scoring** — Pattern Strength = Base Score × Volume Multiplier × Context Multiplier. Volume >1.5× avg → 1.4×. At OB/liquidity zone → 1.5×. Random location → 0.6×.
- **ML Pattern Recognition** — 1D-CNN on candlestick image representation (OHLC body/wick encoding + volume overlay + RSI overlay). Output: pattern classification + success probability + expected move magnitude.
- **Failure Detector** — Flags: low volume pattern, immediate reversal >50%, mid-range no structure, conflicting HTF patterns, chop (ADX <20), news within 2h. Reduce confidence 40-60%.

**Pattern expires:** If no entry within 3 candles, pattern invalidates.

---

### S10 — Trade Entry Module (Confluence Engine)

**Purpose:** Aggregate all upstream signals into a confluence score, determine entry method, generate trade proposals.

**This is the critical decision point.**

**Confluence Scoring:**
```
CONFLUENCE SCORE = Σ(Signal Weight × Signal Quality × TF Alignment)

Signal Weights:
  SMC Structure (S7):        0.25  — Highest predictive value
  Liquidity Sweep (S6):      0.20  — Smart money footprint
  Kill Zone Timing (S3):     0.15  — Institutional flow window
  Candlestick Pattern (S9):  0.15  — Entry timing signal
  RSI/Momentum (S8):         0.10  — Momentum confirmation
  Volume Confirmation:        0.10  — Validates the move
  News/Fundamental (S1):     0.05  — Directional filter
```

**Critical Rule:** If ANY of the top-3 signals (structure, liquidity, kill zone) is absent, cap maximum score at 0.60.

**Optimal Confirmations:** 4-5 confirmations with weighted scoring. Don't require all 7 — require the RIGHT 4 (top-weighted signals). Diminishing returns after 5.

**Grading:**
- 0.80-1.00: A+ setup → Full position (1.5-2% risk)
- 0.65-0.79: A setup → Standard position (1% risk)
- 0.50-0.64: B setup → Reduced position (0.5% risk)
- 0.35-0.49: C setup → Paper trade or skip
- <0.35: No trade

**Entry Method Decision:**
- High score + price near OB → Limit order at structure
- High score + strong momentum → Market order with wider stop
- Medium score → Limit order slightly better than structure
- Low score → Skip

**Auto-Approve Threshold:** ≥0.75 (configurable). Human review: 0.50-0.74. Auto-reject: <0.50.

**Output:**
```python
TradeOrder(
    pair="EURUSD",
    direction=Direction.BULLISH,
    order_type=OrderType.LIMIT,
    lot_size=0.05,
    entry_price=1.0865,
    stop_loss=1.0835,
    take_profits=[
        TakeProfitLevel(price=1.0895, close_pct=33, r_multiple=1.0),
        TakeProfitLevel(price=1.0925, close_pct=33, r_multiple=2.0),
        TakeProfitLevel(price=None, close_pct=34, method="ATR_TRAIL", atr_mult=2.5)
    ],
    confluence_score=0.82,
    setup_grade="A+",
    metadata={
        "signal_chain": {"S1": ..., "S2": ..., "S3": ..., "S4": ..., "S5": ..., "S6": ..., "S7": ..., "S8": ..., "S9": ...},
        "entry_method": "limit",
        "entry_reason": "H4 OB touch + bullish engulfing + RSI divergence + London session"
    }
)
```

---

### S11 — Position Sizing Module

**Purpose:** Calculate optimal lot size using quarter-Kelly, dynamic multi-factor adjustment, correlation-aware sizing.

**Sizing Formula:**
```
FINAL_SIZE = Base_Risk × Confluence_Mult × Regime_Mult × Performance_Mult × Session_Mult × Correlation_Factor

Where:
  Base_Risk = Account_Balance × 1%
  Confluence_Mult: A+ = 1.5×, A = 1.0×, B = 0.5×
  Regime_Mult: ADX>30 = 1.2×, ADX 20-30 = 1.0×, ADX<20 = 0.6×
  Performance_Mult: Last 5 trades 4+ wins = 1.1×, 3 wins = 1.0×, ≤2 = 0.7×, 3 consec losses = 0.5× (circuit breaker)
  Session_Mult: LDN/NY overlap = 1.2×, London/NY = 1.0×, Asian = 0.7×
  Correlation_Factor: Adjusts for correlated open positions (see below)
```

**Hard Caps:**
- Max risk per trade: 2% of account
- Max total open exposure: 6% of account
- Max correlated exposure: 3% across all correlated pairs
- Max daily loss: 4% (circuit breaker — stop all new entries)

**Correlation Adjustment:**
```
When correlation > 0.7 between two positions:
  Combined risk = Sum of individual risks × (1 + correlation × 0.5)
If combined > 2.5%: reduce each position proportionally.
```

**Account Growth Scaling:**

| Account Size | Max Risk/Trade | Max Open Exposure |
|-------------|---------------|-------------------|
| $1K-$5K | 1.0% | 3.0% |
| $5K-$25K | 1.5% | 4.5% |
| $25K-$100K | 1.5% | 5.0% |
| $100K-$500K | 1.0% | 4.0% |
| $500K+ | 0.75% | 3.0% |

**Risk Parity:** Position size ∝ 1/ATR_i. Each pair contributes equal dollar risk regardless of volatility.

---

### S12 — Stop Loss Module

**Purpose:** Multi-factor stop placement with volatility adaptation, stop hunt protection, and trailing strategy selection.

**Stop Calculation:**
```
STOP = Structure_Level - (ATR_Buffer × Volatility_Factor × Context_Adjustment)

Structure Level Priority: OB edge > Swing H/L > FVG edge > Liquidity pool
ATR Buffer: Base 0.5× ATR(14), adjusted by volatility regime
Context: Strong structure → -0.1 ATR. Weak structure → +0.2 ATR. Counter-trend → +0.3 ATR
```

**Stop Hunt Protection:**
- Don't place stops at obvious levels (exact swing low, round numbers)
- Extend stop beyond visible liquidity pools
- Widen stops by 0.3 ATR during session opens and pre-news windows
- Layered stops: 60% at primary, 40% at extended (survives wicks)

**Trailing Stop Selection:**

| Market Condition | Trailing Method | Parameters |
|-----------------|----------------|------------|
| Trending (ADX>25) | ATR Trail | Highest High - 2× ATR |
| SMC Trade | Structure Trail | Trail to each new swing low |
| Strong Momentum | Chandelier Exit | Highest High - 3× ATR(22) |
| Ranging | Break-Even + Trail | BE at 1R, trail at 2R |
| Counter-trend | BE + Trail (conservative) | BE at 1R, tight trail |

**Time-Based Stops:** 15m TF: exit after 4h if no movement. 1H: after 24h. 4H: after 5 days. "Movement" = >0.5 ATR in favor.

**Hard Limits:** Max stop 2% of account. If calculated stop exceeds 2% → reduce position size, never move stop closer.

---

### S13 — Take Profit Module

**Purpose:** Partial profit-taking with session-based targets, volatility adaptation, and liquidity pool targeting.

**Partial TP Framework:**
```
Default (Balanced): 33% at 1R, 33% at 2R, trail 33% with ATR(14)×2.5
Conservative: 50% at 1R, 25% at 2R, trail 25% with structure
Aggressive: 25% at 1.5R, 25% at 3R, trail 50% until structure break
```

**Session-Based Targets:**
- Asian entry: TP1 at 0.8× Asian range, TP2 at 1.2× Asian range
- London entry: TP1 at 1.0× London opening range, TP2 at previous day H/L
- NY entry: TP1 at London H/L retest, TP2 at daily range completion
- LDN/NY overlap: Wider targets — highest momentum extensions

**Volatility Adjustments:**
- Low vol: target_mult 0.8×, take profit early
- Normal vol: target_mult 1.0×
- High vol: target_mult 1.3×, wider trailing
- Extreme vol: target_mult 1.5×, tighten initial TP

**Trending Override:** ADX >25 → runner strategy: close 20% at 1R, trail remainder with EMA(21) + ATR(14)×2.

**RL Agent:** Trained on 3+ years of historical data. State: volatility regime, session, structure, RSI, volume profile, time in trade. Action: close X% at various R-multiples. Reward: Sharpe ratio of individual trade.

---

### S14 — Trade Management Module

**Purpose:** Dynamic R-multiple management, pre-news handling, correlation monitoring, manual close decision framework.

**Dynamic R-Multiple Framework:**
```
Low vol + Asian:     BE at 0.7R, partial at 1.2R, trail 1.5× ATR
Normal vol + trend:  BE at 1.0R, partial at 2.0R, trail structure
High vol + trend:    BE at 1.5R, partial at 2.5R, trail 2× ATR or EMA(21)
Extreme vol:         BE at 2.0R, no partials, trail full with wide ATR OR close 50% immediately
```

**Pre-News Protocol:**
- T-60min: Flag positions with news exposure
- T-30min: If profit >1R → tighten SL. At BE → move SL to -0.5R. In loss >0.5R → consider closing
- T-5min (high impact): Close 50%, widen remaining SL to 2× ATR
- T+5min: Assess post-news. T+30min: Resume normal management

**Correlation Management:**
- Max effective portfolio exposure: 6R
- Correlation >0.8 and combined_R >4R → flag for review, consider closing weaker setup
- Correlation <-0.8 and net exposure →0 → flag as hedge, evaluate intent

**AI-Driven EV Monitoring:**
```
Every candle close:
  EV = (P_tp × Reward) - (P_sl × Risk) - (P_stagnate × Time_cost)
  If EV < 0.3R → signal to tighten SL or close
  If EV increases significantly → widen TP or add to position
```

**Smart Trailing Agent:** Pair-specific trailing "personality" learned from historical data. EURUSD: wider trailing with structure-based stops. GBPJPY: 3× ATR trailing. XAUUSD: EMA(8) trailing in trends.

---

### S15 — Exit Conditions Module

**Purpose:** Early exit detection, overnight/weekend management, black swan protocol.

**Early Warning System:**
```
WARNING SIGNALS:
1. Volume divergence (price → SL on increasing volume = bad)
2. Order flow shift (delta flipping against position)
3. Lower TF structure break (H1 breaks against H4 trade)
4. Momentum exhaustion (RSI failing to reach previous levels)
5. Liquidity sweep in wrong direction

WARNING SCORE ≥ 3 AND profit < 0.5R → EXIT EARLY
WARNING SCORE ≥ 3 AND in loss → EXIT EARLY (save 0.3-0.5R vs SL hit)
WARNING SCORE ≥ 2 AND profit > 1R → TIGHTEN SL to current price
```

**Weekend Management:**
- Friday 20:00 UTC check:
  - High-impact weekend event → close 100%
  - Profit >2R → close 50%, trail rest
  - Profit 1-2R → close 75%, trail rest
  - At BE or loss → close 100%

**Black Swan Protocol:**
```
DETECTION (any 2+):
- VIX spike >40% in 1 hour
- ATR(1) >5× ATR(14) on any open position
- Spread >10× normal
- Multiple correlated assets moving >3% simultaneously

RESPONSE:
1. IMMEDIATE: Close ALL positions at market
2. If execution impossible: set widest possible SL, contact broker
3. Post-event: Wait for VIX<30 and spreads normalizing
4. Portfolio protection: maintain max 30% margin utilization at all times
```

**Stale Trade Detection:** If time_in_trade >3× historical median AND profit <0.5R → exit (capital efficiency).

---

### S16 — Trade Journal & Learning Module

**Purpose:** Structured trade recording, AI-powered analytics, reinforcement learning from history, automated improvement recommendations.

**Journal Data Schema:**
```
TRADE RECORD:
├── Basic Data (pair, date, session, direction, timeframe, trade_type)
├── Pre-Trade Context (bias, structure, levels, liquidity, confluence_score, grade)
├── Entry Data (price, time, trigger, TF confirmation, slippage)
├── Management Data (SL adjustments, partial closes, all decisions)
├── Exit Data (price, time, condition, final R, MAE, MFE, slippage)
├── Psychological Data (confidence, emotions, rule adherence, deviations)
├── Analysis (why worked/failed, lessons, screenshots)
└── AI Analysis (pattern match, statistical edge, RL suggestions, optimal comparison)
```

**AI Analytics Engine:**
- **Weekly Analysis:** Pattern recognition across trades. "3 losing trades on GBP pairs during NY session." "A-grade setups 72% win rate but only 2 taken this week."
- **Correlation Analysis:** "Emotional state >7 correlates with 23% lower win rate." "Asian session trades have 15% higher expectancy."
- **Improvement Generation:** Priority-ranked actionable recommendations.

**Reinforcement Learning Agent:**
```
State: Market conditions at entry + all management decision points
Action: Entry/management/exit decisions
Reward: R-multiple achieved (normalized for volatility)

Training: Convert historical trades to state-action-reward trajectories.
Compare RL policy to actual human decisions.
Generate specific feedback: "At [time], you closed 50% at 1.2R. 
Optimal was to hold for 2.1R. Cost: 0.45R."

Retrain weekly. If RL outperforms → suggest adopting recommendations.
If human outperforms RL → investigate what human knows that RL doesn't.
```

**Performance Dashboard Metrics:**
- Return: Total R, win rate by setup/session/pair, avg R-multiple, profit factor, expectancy, Sharpe
- Risk: Max drawdown, avg MAE, max consecutive losses, risk of ruin, recovery factor
- Behavioral: Rule adherence %, deviation frequency, emotional correlation, time/day performance
- Pattern: Best/worst setups, optimal R targets, optimal holding time, confluence-P/L correlation

---

## 3. Signal Flow & Data Pipeline

### 3.1 Event Bus Architecture

All modules communicate through a central event bus (Redis Streams or NATS):

```
┌──────────────────────────────────────────────────────────────┐
│                        EVENT BUS (Redis Streams / NATS)       │
│                                                               │
│  Streams:                                                     │
│    market.data       → Raw ticks, candles, order book         │
│    market.news       → News articles, sentiment scores        │
│    market.calendar   → Economic events                        │
│    signals.fundamental → S1 outputs                           │
│    signals.bias      → S2 outputs                             │
│    signals.session   → S3 outputs                             │
│    signals.structure → S4 outputs                             │
│    signals.levels    → S5 outputs                             │
│    signals.liquidity → S6 outputs                             │
│    signals.smc       → S7 outputs                             │
│    signals.momentum  → S8 outputs                             │
│    signals.candle    → S9 outputs                             │
│    signals.confluence → S10 outputs                           │
│    orders.proposal   → Trade proposals from S10               │
│    orders.risk_check → Risk governor decisions                │
│    orders.execution  → Approved orders to broker              │
│    orders.fill       → Fill confirmations from broker         │
│    management.action → SL/TP adjustments from S12-S15         │
│    journal.trade     → Trade records for S16                  │
│    system.alert      → Risk alerts, black swan, errors        │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 Signal Flow Diagram

```
                    ┌─────────────┐
                    │  DATA FEEDS  │
                    │  (Market,    │
                    │   News,      │
                    │   Calendar)  │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │    S1    │ │    S3    │ │    S4    │
        │ Funda-   │ │ Session  │ │ Structure│
        │ mental   │ │ Analysis │ │          │
        └────┬─────┘ └────┬─────┘ └────┬─────┘
             │             │             │
             │    ┌────────┘             │
             │    │    ┌─────────────────┘
             ▼    ▼    ▼
        ┌──────────────────┐
        │       S2         │
        │  Market Bias     │◄──── S1 + S4
        │  (HMM + Fusion)  │
        └────────┬─────────┘
                 │
        ┌────────┼────────┬────────────┐
        ▼        ▼        ▼            ▼
   ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
   │   S5   │ │   S6   │ │   S7   │ │   S8   │
   │  S/R   │ │Liquidity│ │  SMC   │ │  RSI   │
   └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘
       │          │          │          │
       └──────────┴──────────┴──────────┘
                         │
                    ┌────▼────┐
                    │   S9    │
                    │Candle-  │
                    │stick    │
                    └────┬────┘
                         │
                    ┌────▼────────────┐
                    │      S10        │
                    │  CONFLUENCE     │
                    │  ENGINE         │
                    │  (Entry Decision)│
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  RISK GOVERNOR  │
                    │  (Gate check)   │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
        ┌──────────┐  ┌──────────┐  ┌──────────┐
        │    S11   │  │    S12   │  │    S13   │
        │Position  │  │Stop Loss │  │Take      │
        │Sizing    │  │          │  │Profit    │
        └────┬─────┘  └────┬─────┘  └────┬─────┘
             └──────────────┼──────────────┘
                            │
                    ┌───────▼───────┐
                    │  BROKER LAYER │
                    │  (Execution)  │
                    └───────┬───────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
        ┌──────────┐  ┌──────────┐  ┌──────────┐
        │    S14   │  │    S15   │  │    S16   │
        │  Trade   │  │   Exit   │  │ Journal  │
        │  Mgmt    │  │Conditions│  │& Learning│
        └──────────┘  └──────────┘  └──────────┘
```

### 3.3 Data Flow Timing

| Layer | Latency Target | Frequency |
|-------|---------------|-----------|
| Tick ingestion | <5ms | Every tick |
| S1-S3 (Context) | <2s | Per candle + events |
| S4-S8 (Analysis) | <500ms | Per candle (M15 primary) |
| S9 (Candlestick) | <50ms | Per candle close |
| S10 (Confluence) | <100ms | On signal from S4-S9 |
| Risk Governor | <10ms | On trade proposal |
| S11-S13 (Execution prep) | <50ms | On approved trade |
| Broker execution | <100ms | On order submission |
| S14-S15 (Management) | <1s | Per candle close |
| S16 (Journal) | Async | Post-trade |

---

## 4. Strategy Engine: Decision Making

### 4.1 The Decision Pipeline

The strategy engine makes final decisions through a strict pipeline:

```
1. CONTEXT GATHERING (S1 + S2 + S3)
   → Is the market safe to trade? What's the bias? What session are we in?

2. STRUCTURE ANALYSIS (S4 + S5)
   → What's the trend? Where are key levels?

3. SIGNAL DETECTION (S6 + S7 + S8 + S9)
   → Is there a setup forming? What confluences are present?

4. CONFLUENCE SCORING (S10)
   → How strong is the setup? What grade?

5. RISK GATE (Risk Governor)
   → Can we take this trade? Within limits?

6. EXECUTION PREP (S11 + S12 + S13)
   → How much? Where's the stop? Where are the targets?

7. ORDER SUBMISSION (Broker Layer)
   → Execute the trade.

8. POST-ENTRY MANAGEMENT (S14 + S15)
   → Manage the trade until exit.

9. RECORDING & LEARNING (S16)
   → Log everything, learn from it.
```

### 4.2 Gate System

Each stage acts as a gate. If a gate fails, the pipeline stops:

```python
class DecisionPipeline:
    async def evaluate(self, pair: str) -> TradeDecision:
        # Gate 1: Context
        context = await self.gather_context(pair)
        if context.trade_decision == "AVOID_ALL":
            return TradeDecision.SKIP("Fundamental avoidance")
        
        # Gate 2: Structure
        structure = await self.analyze_structure(pair)
        if structure.chop_score > 0.7:
            return TradeDecision.SKIP("Choppy market")
        if structure.alignment_score < 0.4:
            return TradeDecision.SKIP("Insufficient TF alignment")
        
        # Gate 3: Signals
        signals = await self.detect_signals(pair, context, structure)
        if not signals.has_actionable_setup:
            return TradeDecision.SKIP("No setup detected")
        
        # Gate 4: Confluence
        confluence = await self.score_confluence(signals, context, structure)
        if confluence.score < 0.50:
            return TradeDecision.SKIP(f"Low confluence: {confluence.score}")
        
        # Gate 5: Risk
        risk_check = await self.risk_governor.check(confluence, pair)
        if not risk_check.approved:
            return TradeDecision.SKIP(f"Risk rejected: {risk_check.reason}")
        
        # Gate 6: Execution Prep
        sizing = await self.position_sizing.calculate(confluence, risk_check)
        stop = await self.stop_loss.calculate(confluence, sizing)
        tp = await self.take_profit.calculate(confluence, sizing, stop)
        
        # Build trade order
        order = TradeOrder(
            pair=pair,
            direction=confluence.direction,
            lot_size=sizing.lot_size,
            entry_price=confluence.entry_price,
            stop_loss=stop.price,
            take_profits=tp.levels,
            confluence_score=confluence.score,
            setup_grade=confluence.grade,
            metadata=confluence.full_signal_chain
        )
        
        return TradeDecision.EXECUTE(order)
```

### 4.3 Confluence Scoring Engine (Detailed)

The confluence engine is the brain of the system. It aggregates signals from S1-S9:

```python
class ConfluenceEngine:
    WEIGHTS = {
        'smc_structure': 0.25,      # S7: OB/FVG/BOS/CHoCH
        'liquidity_sweep': 0.20,    # S6: Real sweep detection
        'kill_zone': 0.15,          # S3: Session timing
        'candlestick': 0.15,        # S9: Pattern confirmation
        'rsi_momentum': 0.10,       # S8: RSI alignment/divergence
        'volume': 0.10,             # Volume confirmation
        'fundamental': 0.05,        # S1: News/sentiment bias
    }
    
    def score(self, signals: dict, context: dict, structure: dict) -> ConfluenceResult:
        raw_scores = {}
        
        # Score each signal component
        raw_scores['smc_structure'] = self._score_smc(signals.get('smc'), structure)
        raw_scores['liquidity_sweep'] = self._score_liquidity(signals.get('liquidity'))
        raw_scores['kill_zone'] = self._score_session(context.get('session'))
        raw_scores['candlestick'] = self._score_candlestick(signals.get('candle'))
        raw_scores['rsi_momentum'] = self._score_rsi(signals.get('rsi'))
        raw_scores['volume'] = self._score_volume(signals.get('volume'))
        raw_scores['fundamental'] = self._score_fundamental(context.get('fundamental'))
        
        # Weighted sum
        total = sum(
            raw_scores[k] * self.WEIGHTS[k] 
            for k in self.WEIGHTS
        )
        
        # Critical rule: cap if top-3 signals missing
        top_3 = ['smc_structure', 'liquidity_sweep', 'kill_zone']
        missing_top = sum(1 for k in top_3 if raw_scores[k] < 0.3)
        if missing_top > 0:
            total = min(total, 0.60)
        
        # Grade
        grade = self._grade(total)
        
        # Direction consensus
        directions = [s.direction for s in signals.values() if s and s.direction]
        direction = self._majority_vote(directions)
        
        return ConfluenceResult(
            score=total,
            grade=grade,
            direction=direction,
            breakdown=raw_scores,
            entry_price=self._determine_entry(signals, structure),
            confirmation_count=sum(1 for v in raw_scores.values() if v > 0.5)
        )
    
    def _grade(self, score: float) -> str:
        if score >= 0.80: return "A+"
        if score >= 0.65: return "A"
        if score >= 0.50: return "B"
        if score >= 0.35: return "C"
        return "D"
```

### 4.4 Risk Governor

The Risk Governor is a hard-coded safety layer that NO module can override:

```python
class RiskGovernor:
    """Absolute risk limits. No ML model can bypass these."""
    
    MAX_RISK_PER_TRADE = 0.02       # 2% of account
    MAX_TOTAL_EXPOSURE = 0.06       # 6% of account
    MAX_CORRELATED_EXPOSURE = 0.03  # 3% across correlated pairs
    MAX_DAILY_LOSS = 0.04           # 4% daily circuit breaker
    MAX_CONCURRENT_POSITIONS = 5
    MAX_MARGIN_UTILIZATION = 0.30   # 30% max margin use
    
    async def check(self, proposal: TradeOrder, account: Account) -> RiskCheck:
        # Check 1: Per-trade risk
        trade_risk = self._calc_trade_risk(proposal)
        if trade_risk > self.MAX_RISK_PER_TRADE:
            return RiskCheck(approved=False, reason="Per-trade risk exceeded",
                           adjusted_lot_size=self._reduce_to_limit(proposal))
        
        # Check 2: Total exposure
        current_exposure = sum(p.risk for p in account.open_positions)
        if current_exposure + trade_risk > self.MAX_TOTAL_EXPOSURE:
            return RiskCheck(approved=False, reason="Total exposure exceeded")
        
        # Check 3: Correlation
        corr_risk = self._calc_correlation_risk(proposal, account.open_positions)
        if corr_risk > self.MAX_CORRELATED_EXPOSURE:
            return RiskCheck(approved=False, reason="Correlated exposure exceeded",
                           adjusted_lot_size=self._reduce_for_correlation(proposal, account))
        
        # Check 4: Daily loss circuit breaker
        if account.daily_pnl < -(self.MAX_DAILY_LOSS * account.balance):
            return RiskCheck(approved=False, reason="Daily loss circuit breaker triggered")
        
        # Check 5: Max positions
        if len(account.open_positions) >= self.MAX_CONCURRENT_POSITIONS:
            return RiskCheck(approved=False, reason="Max concurrent positions reached")
        
        # Check 6: Margin
        if account.margin_utilization > self.MAX_MARGIN_UTILIZATION:
            return RiskCheck(approved=False, reason="Margin utilization too high")
        
        return RiskCheck(approved=True, reason="All checks passed",
                        max_allowed_risk=self.MAX_RISK_PER_TRADE,
                        current_exposure=current_exposure,
                        correlation_factor=corr_risk)
```

---

## 5. Multi-Agent System Integration

### 5.1 Agent Architecture

The trading engine operates as a multi-agent system where each agent wraps one or more modules:

```
┌──────────────────────────────────────────────────────────────────┐
│                      AGENT ORCHESTRATOR                           │
│  (LangGraph / CrewAI / Custom)                                   │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  CONTEXT AGENTS (Low-frequency, high-level)                 │ │
│  │  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐     │ │
│  │  │ Fundamental   │ │ Market Bias   │ │ Session       │     │ │
│  │  │ Agent (S1)    │ │ Agent (S2)    │ │ Agent (S3)    │     │ │
│  │  └───────────────┘ └───────────────┘ └───────────────┘     │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  ANALYSIS AGENTS (Medium-frequency, per-candle)              │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │ │
│  │  │Structure │ │ S/R      │ │Liquidity │ │ SMC      │      │ │
│  │  │Agent(S4) │ │Agent(S5) │ │Agent(S6) │ │Agent(S7) │      │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘      │ │
│  │  ┌──────────┐ ┌──────────┐                                  │ │
│  │  │ RSI      │ │Candle    │                                  │ │
│  │  │Agent(S8) │ │Agent(S9) │                                  │ │
│  │  └──────────┘ └──────────┘                                  │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  DECISION AGENTS (Event-driven, on signal)                   │ │
│  │  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐     │ │
│  │  │ Confluence    │ │ Risk          │ │ Execution     │     │ │
│  │  │ Agent (S10)   │ │ Governor      │ │ Agent         │     │ │
│  │  └───────────────┘ └───────────────┘ └───────────────┘     │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  MANAGEMENT AGENTS (Continuous, per-candle)                  │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │ │
│  │  │Position  │ │Stop Loss │ │Take Profit│ │Trade Mgmt│      │ │
│  │  │Agent(S11)│ │Agent(S12)│ │Agent(S13)│ │Agent(S14)│      │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘      │ │
│  │  ┌───────────────┐                                          │ │
│  │  │ Exit Agent    │                                          │ │
│  │  │ (S15)         │                                          │ │
│  │  └───────────────┘                                          │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  LEARNING AGENT (Background, async)                          │ │
│  │  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐     │ │
│  │  │ Journal       │ │ Analytics     │ │ RL Agent      │     │ │
│  │  │ Agent (S16)   │ │ Agent         │ │               │     │ │
│  │  └───────────────┘ └───────────────┘ └───────────────┘     │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  SENTINEL AGENTS (Always-on, safety)                         │ │
│  │  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐     │ │
│  │  │ Black Swan    │ │ Correlation   │ │ Health        │     │ │
│  │  │ Sentinel      │ │ Watcher       │ │ Monitor       │     │ │
│  │  └───────────────┘ └───────────────┘ └───────────────┘     │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

### 5.2 Agent Communication Protocol

All agents communicate via structured messages on the event bus:

```python
@dataclass
class AgentMessage:
    from_agent: str
    to_agent: str  # "*" for broadcast
    timestamp: datetime
    message_type: MessageType  # SIGNAL, COMMAND, QUERY, RESPONSE, ALERT
    priority: Priority  # P0=CRITICAL, P1=HIGH, P2=MEDIUM, P3=LOW
    payload: dict
    ttl_seconds: int  # Message expiry
    correlation_id: str  # For request-response pairing
```

**Priority Levels:**
- **P0 (CRITICAL):** Black swan detected, risk limit breach, broker disconnection
- **P1 (HIGH):** Liquidity sweep detected, high-confluence trade signal, stop hit
- **P2 (MEDIUM):** S/R level approach, RSI extreme, session transition
- **P3 (LOW):** Background scan updates, journal entries, analytics

### 5.3 Loop Integration

The multi-agent system operates on multiple loop frequencies:

```
TICK LOOP (~100ms):
  → Black Swan Sentinel: anomaly detection
  → Correlation Watcher: portfolio risk update
  → Order Book Monitor: liquidity heatmap update

CANDLE LOOP (M15 primary, ~15min):
  → Structure Agent: swing detection, BOS/CHoCH
  → S/R Agent: level updates
  → Liquidity Agent: sweep detection
  → SMC Agent: OB/FVG scan
  → RSI Agent: calculation + divergence
  → Candlestick Agent: pattern detection
  → Confluence Agent: score calculation
  → Trade Management Agent: SL/TP adjustments
  → Exit Agent: exit condition checks

SESSION LOOP (every session open/close):
  → Session Agent: session transition, parameter update
  → Asian Range Agent: reset at 00:00 UTC
  → Fundamental Agent: session-specific news check

DAILY LOOP (end of day):
  → Journal Agent: daily compilation
  → Analytics Agent: daily performance
  → S/R Agent: full recalculation
  → HMM retrain trigger

WEEKLY LOOP (Sunday):
  → Full performance analysis
  → Pattern recognition across trades
  → RL agent retraining
  → Strategy parameter review
  → HMM retrain with latest data

MONTHLY LOOP:
  → Comprehensive strategy review
  → Model recalibration
  → Feature importance analysis
  → Trade playbook update
```

### 5.4 ReAct Loop for Complex Decisions

For complex or ambiguous situations, the system uses a ReAct (Reasoning + Acting) loop:

```python
class ReActDecisionLoop:
    """For high-stakes or ambiguous trade decisions."""
    
    async def evaluate(self, setup: dict, max_iterations: int = 5) -> Decision:
        thought = f"Analyzing setup: {setup.summary()}"
        
        for i in range(max_iterations):
            # Thought: Reason about current state
            thought = await self.llm.think(thought, self.get_current_context())
            
            # Action: Gather more information or make decision
            action = await self.llm.decide_action(thought, [
                "check_higher_timeframe",
                "check_order_flow",
                "check_correlation",
                "check_news_sentiment",
                "check_historical_similarity",
                "make_decision"
            ])
            
            if action == "make_decision":
                return await self.llm.make_decision(thought)
            
            # Observation: Get result of action
            observation = await self.execute_action(action, setup)
            thought = f"{thought}\nAction: {action}\nObservation: {observation}"
        
        # Max iterations reached — default to no trade
        return Decision.SKIP("ReAct loop max iterations — insufficient clarity")
```

---

## 6. Broker Layer Integration

### 6.1 Broker Abstraction Layer

The broker layer provides a unified interface regardless of the underlying broker:

```python
class BrokerConnector(ABC):
    """Abstract broker interface. Each broker implements this."""
    
    @abstractmethod
    async def connect(self, credentials: dict) -> bool:
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        pass
    
    @abstractmethod
    async def get_account_info(self) -> AccountInfo:
        pass
    
    @abstractmethod
    async def get_positions(self) -> list[Position]:
        pass
    
    @abstractmethod
    async def place_order(self, order: TradeOrder) -> OrderResult:
        pass
    
    @abstractmethod
    async def modify_order(self, ticket: int, modifications: dict) -> OrderResult:
        pass
    
    @abstractmethod
    async def close_position(self, ticket: int, volume: float = None) -> OrderResult:
        pass
    
    @abstractmethod
    async def get_market_data(self, pair: str, timeframe: str, count: int) -> DataFrame:
        pass
    
    @abstractmethod
    async def subscribe_ticks(self, pair: str, callback: Callable) -> None:
        pass
    
    @abstractmethod
    async def get_ohlcv(self, pair: str, timeframe: str, count: int) -> DataFrame:
        pass
```

### 6.2 MT5 Connector (Primary)

```python
class MT5Connector(BrokerConnector):
    """MetaTrader 5 connector via Python MT5 API."""
    
    async def connect(self, credentials: dict) -> bool:
        mt5.initialize(path=credentials['terminal_path'])
        mt5.login(
            server=credentials['server'],
            login=credentials['login'],
            password=credentials['password']
        )
        return mt5.account_info() is not None
    
    async def place_order(self, order: TradeOrder) -> OrderResult:
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": order.pair,
            "volume": order.lot_size,
            "type": mt5.ORDER_TYPE_BUY if order.direction == Direction.BULLISH else mt5.ORDER_TYPE_SELL,
            "price": mt5.symbol_info_tick(order.pair).ask if order.direction == Direction.BULLISH else mt5.symbol_info_tick(order.pair).bid,
            "sl": order.stop_loss,
            "tp": order.take_profits[0].price if order.take_profits else 0,
            "deviation": 20,
            "magic": 202607,
            "comment": f"Alpha:{order.setup_grade}:{order.confluence_score:.2f}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        return OrderResult(
            success=result.retcode == mt5.TRADE_RETCODE_DONE,
            ticket=result.order,
            price=result.price,
            error=result.comment
        )
    
    async def modify_order(self, ticket: int, modifications: dict) -> OrderResult:
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "sl": modifications.get('sl', 0),
            "tp": modifications.get('tp', 0),
        }
        result = mt5.order_send(request)
        return OrderResult(success=result.retcode == mt5.TRADE_RETCODE_DONE)
```

### 6.3 CCXT Connector (Crypto)

```python
class CCXTConnector(BrokerConnector):
    """Crypto exchange connector via CCXT library."""
    
    async def connect(self, credentials: dict) -> bool:
        exchange_class = getattr(ccxt, credentials['exchange'])
        self.exchange = exchange_class({
            'apiKey': credentials['api_key'],
            'secret': credentials['api_secret'],
            'sandbox': credentials.get('sandbox', False),
        })
        await self.exchange.load_markets()
        return True
    
    async def place_order(self, order: TradeOrder) -> OrderResult:
        side = 'buy' if order.direction == Direction.BULLISH else 'sell'
        result = await self.exchange.create_order(
            symbol=order.pair,
            type='limit' if order.order_type == OrderType.LIMIT else 'market',
            side=side,
            amount=order.lot_size,
            price=order.entry_price if order.order_type == OrderType.LIMIT else None,
            params={'stopLoss': order.stop_loss, 'takeProfit': order.take_profits[0].price}
        )
        return OrderResult(success=True, ticket=result['id'], price=result['price'])
```

### 6.4 Smart Order Router

```python
class SmartOrderRouter:
    """Routes orders to the best available broker."""
    
    def __init__(self, connectors: dict[str, BrokerConnector]):
        self.connectors = connectors
    
    async def route_order(self, order: TradeOrder) -> OrderResult:
        # Get best execution across all connected brokers
        quotes = {}
        for name, connector in self.connectors.items():
            try:
                quote = await connector.get_quote(order.pair)
                quotes[name] = quote
            except Exception:
                continue
        
        if not quotes:
            return OrderResult(success=False, error="No brokers available")
        
        # Select best price
        if order.direction == Direction.BULLISH:
            best_broker = min(quotes, key=lambda k: quotes[k].ask)
        else:
            best_broker = max(quotes, key=lambda k: quotes[k].bid)
        
        # Execute on best broker
        return await self.connectors[best_broker].place_order(order)
```

### 6.5 Unified Order Manager

```python
class UnifiedOrderManager:
    """Single source of truth for all orders across all brokers."""
    
    def __init__(self, router: SmartOrderRouter, risk_governor: RiskGovernor):
        self.router = router
        self.risk = risk_governor
        self.orders: dict[int, ManagedOrder] = {}
        self.event_bus = EventBus()
    
    async def submit_order(self, proposal: TradeOrder) -> OrderResult:
        # Risk gate
        account = await self.router.get_aggregated_account()
        risk_check = await self.risk.check(proposal, account)
        
        if not risk_check.approved:
            await self.event_bus.publish("orders.risk_check", {
                "approved": False, "reason": risk_check.reason
            })
            return OrderResult(success=False, error=risk_check.reason)
        
        # Adjust if needed
        if risk_check.adjusted_lot_size:
            proposal.lot_size = risk_check.adjusted_lot_size
        
        # Route and execute
        result = await self.router.route_order(proposal)
        
        if result.success:
            managed = ManagedOrder(
                ticket=result.ticket,
                proposal=proposal,
                fill_price=result.price,
                broker=result.broker,
                status=OrderStatus.OPEN,
                opened_at=datetime.utcnow()
            )
            self.orders[result.ticket] = managed
            
            # Notify all agents
            await self.event_bus.publish("orders.fill", {
                "ticket": result.ticket,
                "order": proposal,
                "fill_price": result.price
            })
        
        return result
    
    async def modify_sl(self, ticket: int, new_sl: float) -> OrderResult:
        order = self.orders[ticket]
        connector = self.router.connectors[order.broker]
        result = await connector.modify_order(ticket, {"sl": new_sl})
        
        if result.success:
            order.current_sl = new_sl
            await self.event_bus.publish("management.action", {
                "ticket": ticket, "action": "sl_modified", "new_sl": new_sl
            })
        
        return result
    
    async def partial_close(self, ticket: int, pct: float) -> OrderResult:
        order = self.orders[ticket]
        close_volume = order.proposal.lot_size * (pct / 100)
        connector = self.router.connectors[order.broker]
        result = await connector.close_position(ticket, close_volume)
        
        if result.success:
            order.closed_pct += pct
            await self.event_bus.publish("management.action", {
                "ticket": ticket, "action": "partial_close", "pct": pct
            })
        
        return result
```

---

## 7. Backtesting Architecture

### 7.1 Design Principle: Same Pipeline, Different Data Source

The backtesting engine reuses the EXACT same module code as live trading. The only difference is the data source — historical data instead of live feeds.

```
LIVE TRADING:                          BACKTESTING:
  Live tick feed ──┐                     Historical data ──┐
  News API ────────┤                     Historical news ──┤
  Calendar API ────┤                     Historical cal ───┤
                   ▼                                      ▼
  ┌──────────────────────┐              ┌──────────────────────┐
  │  SAME 16 MODULES     │              │  SAME 16 MODULES     │
  │  (identical code)    │              │  (identical code)    │
  └──────────┬───────────┘              └──────────┬───────────┘
             ▼                                      ▼
  Live broker ──► Real fills              Simulated fills ──► Analytics
```

### 7.2 Backtesting Engine Architecture

```python
class BacktestEngine:
    """Event-driven backtesting engine using the same modules as live."""
    
    def __init__(self, config: BacktestConfig):
        self.config = config
        self.modules = self._initialize_modules(config)
        self.simulator = FillSimulator(config.slippage_model, config.spread_model)
        self.portfolio = SimulatedPortfolio(config.initial_balance)
        self.analytics = BacktestAnalytics()
        self.event_bus = ReplayEventBus()  # Replays historical events in order
    
    async def run(self, start: datetime, end: datetime) -> BacktestResult:
        # Load historical data
        data = await self.load_historical_data(start, end)
        
        # Replay events in chronological order
        for event in self.event_bus.replay(data):
            # Process through same modules as live
            for module in self.modules:
                signals = await module.process(event)
                
                for signal in signals:
                    await self.event_bus.publish(signal.stream, signal)
            
            # Check for trade proposals
            proposals = self.event_bus.get_pending("orders.proposal")
            for proposal in proposals:
                # Risk gate (same as live)
                risk_check = await self.modules['risk_governor'].check(
                    proposal, self.portfolio.get_account()
                )
                
                if risk_check.approved:
                    # Simulate fill (instead of broker)
                    fill = self.simulator.simulate_fill(proposal, event)
                    self.portfolio.apply_fill(fill)
                    
                    # Track for analytics
                    self.analytics.record_trade(proposal, fill)
            
            # Management checks (same as live)
            for position in self.portfolio.open_positions:
                management_signals = await self.modules['trade_management'].process(event)
                for action in management_signals:
                    self.portfolio.apply_action(action)
        
        return self.analytics.generate_report()
```

### 7.3 Fill Simulator

```python
class FillSimulator:
    """Simulates realistic order fills with slippage and spread."""
    
    def __init__(self, slippage_model: str, spread_model: str):
        self.slippage_model = slippage_model  # 'fixed', 'proportional', 'volume_based'
        self.spread_model = spread_model      # 'fixed', 'session_based', 'historical'
    
    def simulate_fill(self, order: TradeOrder, market_event: MarketEvent) -> Fill:
        # Get current spread
        spread = self._get_spread(order.pair, market_event)
        
        # Calculate fill price
        if order.order_type == OrderType.MARKET:
            base_price = market_event.data['ask'] if order.direction == Direction.BULLISH else market_event.data['bid']
            slippage = self._calc_slippage(order, market_event)
            fill_price = base_price + slippage
        elif order.order_type == OrderType.LIMIT:
            if self._limit_filled(order, market_event):
                fill_price = order.entry_price
            else:
                return Fill(status=FillStatus.NOT_FILLED)
        
        # Check SL/TP hits
        high = market_event.data['high']
        low = market_event.data['low']
        
        sl_hit = (order.direction == Direction.BULLISH and low <= order.stop_loss) or \
                 (order.direction == Direction.BEARISH and high >= order.stop_loss)
        
        tp_hits = []
        for tp in order.take_profits:
            tp_price = tp.price
            if tp_price:
                tp_hit = (order.direction == Direction.BULLISH and high >= tp_price) or \
                         (order.direction == Direction.BEARISH and low <= tp_price)
                if tp_hit:
                    tp_hits.append(tp)
        
        return Fill(
            status=FillStatus.FILLED,
            price=fill_price,
            slippage=slippage,
            spread=spread,
            sl_hit=sl_hit,
            tp_hits=tp_hits,
            timestamp=market_event.timestamp
        )
    
    def _calc_slippage(self, order: TradeOrder, event: MarketEvent) -> float:
        if self.slippage_model == 'fixed':
            return 0.0001  # 1 pip fixed
        elif self.slippage_model == 'proportional':
            return event.data['spread'] * 0.5  # Half spread
        elif self.slippage_model == 'volume_based':
            # Higher volume = less slippage
            volume_factor = min(order.lot_size / 1.0, 2.0)
            return 0.0001 * volume_factor
```

### 7.4 Walk-Forward Optimization

```python
class WalkForwardOptimizer:
    """Walk-forward optimization to prevent overfitting."""
    
    def __init__(self, engine: BacktestEngine, n_splits: int = 5):
        self.engine = engine
        self.n_splits = n_splits
    
    async def optimize(self, data: HistoricalData, params: dict) -> OptimizedParams:
        # Split data into in-sample (IS) and out-of-sample (OOS) periods
        splits = self._create_splits(data, self.n_splits)
        
        results = []
        for is_data, oos_data in splits:
            # Optimize on in-sample
            best_params = await self._grid_search(is_data, params)
            
            # Validate on out-of-sample
            oos_result = await self.engine.run_with_params(oos_data, best_params)
            
            results.append({
                'is_sharpe': best_params['sharpe'],
                'oos_sharpe': oos_result.sharpe,
                'is_return': best_params['total_return'],
                'oos_return': oos_result.total_return,
                'params': best_params
            })
        
        # Select params with best OOS performance
        best = max(results, key=lambda r: r['oos_sharpe'])
        
        return OptimizedParams(
            params=best['params'],
            is_performance=np.mean([r['is_sharpe'] for r in results]),
            oos_performance=np.mean([r['oos_sharpe'] for r in results]),
            degradation_ratio=np.mean([r['oos_sharpe'] for r in results]) / np.mean([r['is_sharpe'] for r in results])
        )
```

### 7.5 Backtest Analytics

```python
class BacktestAnalytics:
    """Comprehensive backtest performance analysis."""
    
    def generate_report(self) -> BacktestResult:
        trades = self.trades
        
        return BacktestResult(
            # Return metrics
            total_return=self._total_return(),
            total_r=self._total_r(),
            sharpe_ratio=self._sharpe_ratio(),
            sortino_ratio=self._sortino_ratio(),
            calmar_ratio=self._calmar_ratio(),
            
            # Risk metrics
            max_drawdown=self._max_drawdown(),
            max_drawdown_duration=self._max_dd_duration(),
            avg_mae=self._avg_mae(),
            max_consecutive_losses=self._max_consec_losses(),
            risk_of_ruin=self._risk_of_ruin(),
            
            # Trade metrics
            total_trades=len(trades),
            win_rate=self._win_rate(),
            avg_win_r=self._avg_win_r(),
            avg_loss_r=self._avg_loss_r(),
            profit_factor=self._profit_factor(),
            expectancy=self._expectancy(),
            
            # Behavioral metrics
            avg_time_in_trade=self._avg_time_in_trade(),
            best_session=self._best_session(),
            worst_session=self._worst_session(),
            best_pair=self._best_pair(),
            best_setup_type=self._best_setup(),
            
            # Equity curve
            equity_curve=self._equity_curve(),
            monthly_returns=self._monthly_returns(),
            
            # Trade list
            trades=trades
        )
```

### 7.6 Monte Carlo Simulation

```python
class MonteCarloSimulator:
    """Monte Carlo simulation for risk assessment."""
    
    def simulate(self, trades: list[TradeResult], n_simulations: int = 10000) -> MonteCarloResult:
        results = []
        
        for _ in range(n_simulations):
            # Randomly shuffle trade order
            shuffled = np.random.permutation(trades)
            
            # Calculate equity curve
            equity = [self.initial_balance]
            for trade in shuffled:
                equity.append(equity[-1] + trade.pnl)
            
            results.append({
                'final_equity': equity[-1],
                'max_drawdown': self._calc_max_drawdown(equity),
                'sharpe': self._calc_sharpe(equity),
                'ruin': any(e <= 0 for e in equity)
            })
        
        return MonteCarloResult(
            median_final_equity=np.median([r['final_equity'] for r in results]),
            percentile_5=np.percentile([r['final_equity'] for r in results], 5),
            percentile_95=np.percentile([r['final_equity'] for r in results], 95),
            median_max_drawdown=np.median([r['max_drawdown'] for r in results]),
            ruin_probability=np.mean([r['ruin'] for r in results]),
            median_sharpe=np.median([r['sharpe'] for r in results])
        )
```

---

## 8. Live Trading Architecture

### 8.1 System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                     LIVE TRADING SYSTEM                           │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  INFRASTRUCTURE LAYER                                        │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │ │
│  │  │ VPS      │ │ Redis    │ │ PostgreSQL│ │ Grafana  │      │ │
│  │  │(Compute) │ │(Event Bus│ │(State)   │ │(Monitor) │      │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘      │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  DATA INGESTION LAYER                                        │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │ │
│  │  │ MT5      │ │ News     │ │ Calendar │ │ On-Chain │      │ │
│  │  │ Tick Feed│ │ Feed     │ │ Feed     │ │ Feed     │      │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘      │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  STRATEGY ENGINE (16 Modules)                                │ │
│  │  [S1] [S2] [S3] [S4] [S5] [S6] [S7] [S8] [S9] [S10]      │ │
│  │  [S11] [S12] [S13] [S14] [S15] [S16]                       │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  EXECUTION LAYER                                             │ │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │ │
│  │  │ Order Manager│ │ Risk Governor│ │ Broker Router│        │ │
│  │  └──────────────┘ └──────────────┘ └──────────────┘        │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  MONITORING & ALERTING                                       │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │ │
│  │  │ Telegram │ │ Grafana  │ │ PagerDuty│ │ Health   │      │ │
│  │  │ Alerts   │ │Dashboard │ │ On-call  │ │ Checks   │      │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘      │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

### 8.2 Deployment Topology

**Phase 1 — Single VPS ($7 account):**
```
Single Ubuntu VPS (2 vCPU, 4GB RAM)
├── Python process (strategy engine)
├── Redis (event bus + caching)
├── PostgreSQL (trade journal + state)
├── MT5 terminal (Wine or Windows VPS)
└── Grafana + Prometheus (monitoring)
```

**Phase 2 — Scaled ($25K+ account):**
```
Dedicated server or cloud VM (4 vCPU, 8GB RAM)
├── Strategy engine (Docker container)
├── Redis Cluster (event bus)
├── PostgreSQL (dedicated, with replication)
├── MT5 terminal (dedicated Windows VM)
├── Separate ML training instance
├── Grafana + Prometheus + AlertManager
└── Backup VPS (hot standby)
```

**Phase 3 — Institutional ($100K+):**
```
Kubernetes cluster
├── Strategy engine pods (horizontal scaling)
├── Redis Cluster (3+ nodes)
├── PostgreSQL (primary + replicas)
├── Multiple broker connections
├── Dedicated ML training GPU instance
├── Full observability stack
└── Multi-region failover
```

### 8.3 Process Lifecycle

```python
class AlphaStackEngine:
    """Main engine process — orchestrates all modules."""
    
    async def start(self):
        # 1. Initialize infrastructure
        self.event_bus = await RedisStreams.connect(self.config.redis)
        self.db = await PostgreSQL.connect(self.config.db)
        
        # 2. Initialize modules in dependency order
        await self._init_modules()
        
        # 3. Connect broker(s)
        self.broker = await self._connect_broker()
        
        # 4. Start data feeds
        await self._start_feeds()
        
        # 5. Start event processing loop
        await self._start_processing()
        
        # 6. Start monitoring
        await self._start_monitoring()
        
        # 7. Start management loops
        await self._start_management_loops()
        
        logger.info("Alpha Stack Engine started successfully")
    
    async def _init_modules(self):
        """Initialize all 16 modules in dependency order."""
        # Layer 1: Data processing (no dependencies)
        self.modules['S1'] = FundamentalModule()
        self.modules['S3'] = SessionModule()
        self.modules['S4'] = StructureModule()
        
        # Layer 2: Bias (depends on S1, S4)
        self.modules['S2'] = BiasModule(fundamental=self.modules['S1'], structure=self.modules['S4'])
        
        # Layer 3: Analysis (depends on S2, S4)
        self.modules['S5'] = SRModule()
        self.modules['S6'] = LiquidityModule()
        self.modules['S7'] = SMCModule()
        self.modules['S8'] = RSIModule()
        self.modules['S9'] = CandlestickModule()
        
        # Layer 4: Decision (depends on all above)
        self.modules['S10'] = ConfluenceModule(
            smc=self.modules['S7'], liquidity=self.modules['S6'],
            session=self.modules['S3'], candle=self.modules['S9'],
            rsi=self.modules['S8'], fundamental=self.modules['S1']
        )
        
        # Layer 5: Execution (depends on S10)
        self.modules['S11'] = PositionSizingModule()
        self.modules['S12'] = StopLossModule()
        self.modules['S13'] = TakeProfitModule()
        self.modules['S14'] = TradeManagementModule()
        self.modules['S15'] = ExitModule()
        
        # Layer 6: Learning (depends on all)
        self.modules['S16'] = JournalModule()
        
        # Risk Governor (oversees all)
        self.risk_governor = RiskGovernor()
        
        # Initialize all
        for name, module in self.modules.items():
            await module.initialize(self.config.modules.get(name, {}))
            logger.info(f"Module {name} initialized")
    
    async def _start_processing(self):
        """Main event processing loop."""
        async for event in self.event_bus.subscribe("market.*"):
            try:
                # Process through all modules
                all_signals = []
                for name, module in self.modules.items():
                    signals = await module.process(event)
                    all_signals.extend(signals)
                
                # Publish all signals
                for signal in all_signals:
                    await self.event_bus.publish(f"signals.{signal.source_module}", signal)
                
                # Check for trade proposals
                proposals = await self.event_bus.get_pending("orders.proposal")
                for proposal in proposals:
                    await self.unified_order_manager.submit_order(proposal)
                    
            except Exception as e:
                logger.error(f"Error processing event: {e}", exc_info=True)
                await self.event_bus.publish("system.alert", {
                    "level": "ERROR",
                    "message": str(e),
                    "module": "main_loop"
                })
    
    async def _start_management_loops(self):
        """Start periodic management tasks."""
        # Candle-close management loop
        asyncio.create_task(self._candle_management_loop())
        
        # Session transition loop
        asyncio.create_task(self._session_loop())
        
        # Daily journal loop
        asyncio.create_task(self._daily_journal_loop())
        
        # Weekly analytics loop
        asyncio.create_task(self._weekly_analytics_loop())
        
        # Black swan sentinel (always-on)
        asyncio.create_task(self._black_swan_sentinel())
    
    async def _candle_management_loop(self):
        """Runs on every candle close for the trade's timeframe."""
        async for candle in self.event_bus.subscribe("market.candle"):
            for position in self.unified_order_manager.open_positions:
                # Trade management checks (S14)
                actions = await self.modules['S14'].process(candle)
                for action in actions:
                    await self._execute_management_action(action)
                
                # Exit condition checks (S15)
                exits = await self.modules['S15'].process(candle)
                for exit_signal in exits:
                    await self._execute_exit(exit_signal)
                
                # Take profit checks (S13)
                tp_actions = await self.modules['S13'].process(candle)
                for tp in tp_actions:
                    await self._execute_partial_close(tp)
    
    async def _black_swan_sentinel(self):
        """Always-on black swan detection."""
        while True:
            try:
                market_state = await self._get_market_state()
                
                triggers = 0
                if market_state.vix_spike > 0.40: triggers += 1
                if market_state.atr_spike > 5.0: triggers += 1
                if market_state.spread_spike > 10.0: triggers += 1
                if market_state.correlation_convergence > 0.95: triggers += 1
                
                if triggers >= 2:
                    logger.critical(f"BLACK SWAN DETECTED: {triggers} triggers active")
                    await self._execute_black_swan_protocol()
                
                await asyncio.sleep(1)  # Check every second
                
            except Exception as e:
                logger.error(f"Black swan sentinel error: {e}")
                await asyncio.sleep(5)
    
    async def _execute_black_swan_protocol(self):
        """Emergency: close all positions immediately."""
        logger.critical("EXECUTING BLACK SWAN PROTOCOL: Closing all positions")
        
        for position in self.unified_order_manager.open_positions:
            try:
                await self.unified_order_manager.close_position(position.ticket)
                logger.info(f"Closed position {position.ticket}")
            except Exception as e:
                logger.error(f"Failed to close {position.ticket}: {e}")
        
        # Alert human
        await self._send_alert("🚨 BLACK SWAN: All positions closed", priority="CRITICAL")
        
        # Pause trading
        self.trading_paused = True
        self.pause_until = datetime.utcnow() + timedelta(hours=4)
```

### 8.4 Monitoring & Alerting

```python
class MonitoringStack:
    """Prometheus metrics + Grafana dashboards + Telegram alerts."""
    
    def __init__(self):
        # Prometheus metrics
        self.trade_counter = Counter('alpha_trades_total', 'Total trades', ['pair', 'direction', 'result'])
        self.confluence_histogram = Histogram('alpha_confluence_score', 'Confluence score distribution')
        self.risk_gauge = Gauge('alpha_current_risk', 'Current portfolio risk %')
        self.drawdown_gauge = Gauge('alpha_drawdown', 'Current drawdown %')
        self.pnl_gauge = Gauge('alpha_daily_pnl', 'Daily P&L in R')
        self.module_latency = Histogram('alpha_module_latency_seconds', 'Module processing latency', ['module'])
        self.broker_latency = Histogram('alpha_broker_latency_seconds', 'Broker order latency')
    
    async def send_alert(self, message: str, priority: str = "INFO"):
        """Send alert via Telegram."""
        emoji = {"CRITICAL": "🚨", "HIGH": "⚠️", "MEDIUM": "📊", "INFO": "ℹ️"}
        formatted = f"{emoji.get(priority, 'ℹ️')} {message}"
        await self.telegram_bot.send_message(self.alert_chat_id, formatted)
    
    def record_trade(self, trade: TradeResult):
        """Record trade metrics."""
        self.trade_counter.labels(
            pair=trade.pair,
            direction=trade.direction,
            result='win' if trade.r_multiple > 0 else 'loss'
        ).inc()
        self.confluence_histogram.observe(trade.confluence_score)
```

### 8.5 Health Checks

```python
class HealthChecker:
    """System health monitoring."""
    
    async def check_all(self) -> HealthStatus:
        checks = {
            'broker_connection': await self._check_broker(),
            'event_bus': await self._check_redis(),
            'database': await self._check_db(),
            'data_feeds': await self._check_feeds(),
            'module_health': await self._check_modules(),
            'disk_space': self._check_disk(),
            'memory_usage': self._check_memory(),
            'latency': await self._check_latency(),
        }
        
        all_ok = all(c.healthy for c in checks.values())
        
        if not all_ok:
            unhealthy = [k for k, v in checks.items() if not v.healthy]
            await self.alert(f"Health check failed: {unhealthy}", priority="HIGH")
        
        return HealthStatus(healthy=all_ok, checks=checks)
```

---

## 9. Technology Stack

### 9.1 Core Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Language** | Python 3.12+ | Primary (all modules, ML, orchestration) |
| **Performance** | Rust (PyO3) | Hot path: tick processing, signal computation |
| **ML/AI** | PyTorch, scikit-learn, XGBoost | Models: HMM, CNN, XGBoost classifiers |
| **NLP** | FinBERT, DeepSeek/Qwen (LLM) | Sentiment analysis, news processing |
| **Data** | Polars, pandas, NumPy | Data manipulation |
| **Event Bus** | Redis Streams | Inter-module communication |
| **Database** | PostgreSQL | Trade journal, state, analytics |
| **Cache** | Redis | Real-time state, session data |
| **Broker** | MetaTrader5 Python API, CCXT | Order execution |
| **API** | FastAPI | REST/WebSocket for monitoring |
| **Monitoring** | Prometheus + Grafana | Metrics and dashboards |
| **Alerting** | Telegram Bot API | Real-time alerts |
| **Container** | Docker + Docker Compose | Deployment |
| **Orchestration** | Kubernetes (Phase 3) | Scaling |
| **CI/CD** | GitHub Actions | Automated testing and deployment |
| **Backtesting** | Custom event-driven engine | Strategy validation |

### 9.2 ML Model Stack

| Model | Purpose | Technology | Training Frequency |
|-------|---------|------------|-------------------|
| HMM Regime | Market regime detection | hmmlearn | Weekly |
| FinBERT | News sentiment | Hugging Face | Monthly (fine-tune) |
| XGBoost S/R | S/R level classification | XGBoost | Monthly |
| XGBoost Sweep | Real vs fake sweep | XGBoost | Monthly |
| XGBoost SMC | Pattern success prediction | XGBoost | Monthly |
| CNN Candlestick | Pattern recognition | PyTorch | Quarterly |
| LSTM Exit | Exit timing prediction | PyTorch | Monthly |
| RL Agent | Trade management optimization | Stable-Baselines3 | Weekly |

### 9.3 Dependencies

```
# Core
python>=3.12
numpy>=1.26
pandas>=2.2
polars>=0.20
scipy>=1.12

# ML/AI
torch>=2.2
scikit-learn>=1.4
xgboost>=2.0
hmmlearn>=0.3
transformers>=4.38  # FinBERT
stable-baselines3>=2.2  # RL

# Trading
MetaTrader5>=5.0.45
ccxt>=4.2
ta-lib>=0.4.28
smart-money-concepts>=0.2

# Data
feedparser>=6.0
beautifulsoup4>=4.12
finnhub-python>=2.4
websocket-client>=1.7

# Infrastructure
redis>=5.0
asyncpg>=0.29
fastapi>=0.109
uvicorn>=0.27
prometheus-client>=0.20
python-telegram-bot>=21.0

# Backtesting
empyrical>=0.5.5
pyfolio>=0.9.2
```

---

## 10. Deployment & Operations

### 10.1 Deployment Pipeline

```
1. Code commit → GitHub
2. GitHub Actions: lint, type-check, unit tests
3. Docker build → push to registry
4. Deploy to staging → run integration tests
5. Deploy to production (blue-green)
6. Health checks pass → traffic routed to new version
7. Old version kept as hot standby for 24h
```

### 10.2 Operational Runbook

**Daily:**
- Check Grafana dashboards for anomalies
- Review Telegram alerts from past 24h
- Verify broker connection is healthy
- Check daily P&L and drawdown

**Weekly:**
- Review weekly analytics report (auto-generated)
- Check ML model performance metrics
- Verify backup integrity
- Review and act on improvement recommendations from S16

**Monthly:**
- Full model retraining cycle
- Strategy parameter review
- Infrastructure capacity review
- Security audit (credentials, access logs)

**Quarterly:**
- Deep strategy review — is the edge still valid?
- Full backtest with updated parameters
- Walk-forward optimization
- Infrastructure scaling assessment

### 10.3 Disaster Recovery

```
RPO (Recovery Point Objective): 1 minute (Redis AOF + PostgreSQL WAL)
RTO (Recovery Time Objective): 5 minutes (hot standby VPS)

Backup Strategy:
- PostgreSQL: Continuous WAL archiving + daily full backup
- Redis: AOF persistence + hourly RDB snapshots
- Trade state: Serialized to PostgreSQL every minute
- ML models: Versioned in model registry (MLflow or S3)
- Configuration: Git-versioned

Failover:
1. Primary VPS fails → health check detects (30s)
2. DNS/traffic routed to standby VPS (60s)
3. Standby connects to broker (30s)
4. State restored from PostgreSQL + Redis backup (60s)
5. Trading resumes (total: ~3-5 minutes)
```

---

## Appendix A: Module Dependency Graph

```
S1 (Fundamental) ──────────────────────────────────────────────┐
                                                                │
S3 (Session) ──────────────────────────────────────────────────┤
                                                                │
S4 (Structure) ────► S2 (Bias) ◄──── S1                       │
     │                   │                                      │
     │                   │                                      │
     ▼                   ▼                                      │
S5 (S/R) ─────────────────────────────────────────────────────┤
S6 (Liquidity) ───────────────────────────────────────────────┤
S7 (SMC) ─────────────────────────────────────────────────────┤
S8 (RSI) ─────────────────────────────────────────────────────┤
S9 (Candlestick) ─────────────────────────────────────────────┤
     │                                                        │
     └──────────────────► S10 (Confluence) ◄──────────────────┘
                              │
                    ┌─────────┼─────────┐
                    ▼         ▼         ▼
                S11 (Size) S12 (SL) S13 (TP)
                    │         │         │
                    └─────────┼─────────┘
                              │
                         BROKER LAYER
                              │
                    ┌─────────┼─────────┐
                    ▼         ▼         ▼
                S14 (Mgmt) S15 (Exit) S16 (Journal)
```

## Appendix B: Configuration Schema

```yaml
# alpha_stack_config.yaml
version: "1.0"
environment: "production"  # development | staging | production

broker:
  primary:
    type: "mt5"
    server: "FXPesa-Live"
    login: "${MT5_LOGIN}"
    password: "${MT5_PASSWORD}"
    terminal_path: "/path/to/terminal64.exe"
  crypto:
    type: "ccxt"
    exchange: "binance"
    api_key: "${BINANCE_API_KEY}"
    api_secret: "${BINANCE_API_SECRET}"

modules:
  S1_fundamental:
    news_sources: ["finnhub", "forexlive", "reuters"]
    sentiment_model: "ProsusAI/finbert"
    llm_endpoint: "${LLM_ENDPOINT}"
    llm_model: "deepseek-v3"
  
  S2_bias:
    hmm_states: 3
    hmm_retrain_frequency: "weekly"
    timeframes: ["W1", "D1", "H4", "H1"]
    tf_weights: {"W1": 0.35, "D1": 0.30, "H4": 0.20, "H1": 0.15}
  
  S3_session:
    timezone: "UTC"
    asian_range_hours: [0, 8]
    london_hours: [8, 16]
    new_york_hours: [13, 21]
  
  S4_structure:
    swing_lookback_base: 5
    atr_period: 14
    atr_multiplier: 1.5
    chop_adx_threshold: 20
  
  S5_sr:
    fractal_period: 2
    cluster_tolerance_atr: 0.25
    volume_profile_lookback: 20
  
  S6_liquidity:
    sweep_volume_threshold: 2.0
    sweep_classifier_model: "sweep_rf_v2.pkl"
    on_chain_enabled: true
  
  S7_smc:
    ob_impulse_atr_threshold: 1.5
    fvg_enabled: true
    confluence_threshold: 40
  
  S8_rsi:
    period: 14
    timeframes: ["M15", "H1", "H4", "D1"]
    tf_weights: {"M15": 0.15, "H1": 0.25, "H4": 0.35, "D1": 0.25}
    composite_indicators: ["rsi", "stoch_rsi", "mfi", "cci", "williams_r"]
  
  S10_confluence:
    auto_approve_threshold: 0.75
    human_review_range: [0.50, 0.74]
    min_confirmations: 4
  
  S11_sizing:
    base_risk_pct: 1.0
    max_risk_pct: 2.0
    max_total_exposure_pct: 6.0
    kelly_fraction: 0.25  # Quarter-Kelly
    circuit_breaker_consecutive_losses: 3
    circuit_breaker_daily_loss_pct: 4.0
  
  S12_stop_loss:
    base_atr_buffer: 0.5
    max_stop_pct: 2.0
    time_stops: {"M15": 4, "H1": 24, "H4": 120}  # hours
  
  S13_take_profit:
    default_strategy: "balanced"
    partial_levels: [
      {r_multiple: 1.0, close_pct: 33},
      {r_multiple: 2.0, close_pct: 33},
      {method: "trail", close_pct: 34, atr_mult: 2.5}
    ]
  
  S14_management:
    be_trigger_default: "1R"
    trailing_method: "structure"
    news_close_pct: 50
    correlation_max_r: 6
  
  S15_exit:
    early_exit_warning_threshold: 3
    black_swan_vix_spike_pct: 40
    black_swan_atr_multiplier: 5
    weekend_close_time: "Friday 20:00 UTC"

risk_governor:
  max_risk_per_trade_pct: 2.0
  max_total_exposure_pct: 6.0
  max_correlated_exposure_pct: 3.0
  max_daily_loss_pct: 4.0
  max_concurrent_positions: 5
  max_margin_utilization_pct: 30.0

monitoring:
  prometheus_port: 9090
  grafana_port: 3000
  telegram_alerts: true
  alert_chat_id: "${TELEGRAM_CHAT_ID}"

database:
  postgres_url: "${DATABASE_URL}"
  redis_url: "${REDIS_URL}"

backtesting:
  slippage_model: "proportional"
  spread_model: "session_based"
  monte_carlo_simulations: 10000
  walk_forward_splits: 5
```

---

*Document generated by Trading Engine Architect — Alpha Stack*
*This architecture supports the full 16-step Alpha Strategy from $7 micro accounts to institutional scale.*
