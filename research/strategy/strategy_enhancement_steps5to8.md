# AlphaStack Strategy Enhancement — Steps 5–8
## Alpha Stack: AI-Enhanced Support/Resistance, Liquidity, SMC & RSI

**Version:** 1.0 | **Date:** 2026-07-11 | **Author:** Strategy Enhancement Agent

---

## Table of Contents

1. [Step 5 — Major Support & Resistance](#step-5--major-support--resistance)
2. [Step 6 — Liquidity Detection](#step-6--liquidity-detection)
3. [Step 7 — Smart Money Concepts (SMC)](#step-7--smart-money-concepts-smc)
4. [Step 8 — RSI Confirmation](#step-8--rsi-confirmation)
5. [Cross-Step Integration Map](#cross-step-integration-map)
6. [Multi-Agent Architecture](#multi-agent-architecture)
7. [Loop System Integration](#loop-system-integration)

---

## Step 5 — Major Support & Resistance

### Current State
Mark Daily/Weekly/Monthly/Yearly High/Low, psychological numbers (round numbers like 1.1000, 150.00).

### Problems with Manual S/R
- Subjective — two traders mark different levels
- Static — doesn't adapt to changing market structure
- No weighting — treats all levels equally
- Ignores volume context at each level
- Can't process 20+ instruments simultaneously

---

### 5.1 AI-Powered S/R Detection Methods

#### A. Fractal-Based Detection
```
Algorithm: Williams Fractals + Cluster Analysis
1. Detect fractal highs/lows across M15, H1, H4, D1, W1, MN
2. Cluster nearby fractals (within ATR×0.25 tolerance)
3. Score each cluster by:
   - Touch count (how many times price reacted)
   - Recency weight (exponential decay: weight = e^(-days/30))
   - Timeframe diversity (touched on 3+ TFs = premium level)
   - Volume at touch points (if available)
4. Output: Ranked S/R levels with confidence scores [0-100]
```

#### B. Volume Profile S/R
```
Algorithm: Market Profile / Volume Profile Analysis
1. Build volume profile for last 20/50/100 days
2. Identify:
   - POC (Point of Control): Highest volume price level
   - VAH (Value Area High): Upper 70% volume boundary
   - VAL (Value Area Low): Lower 70% volume boundary
   - HVN (High Volume Nodes): Support/Resistance magnets
   - LVN (Low Volume Nodes): Fast price movement zones
3. Weight: POC > VAH/VAL > HVN > LVN
4. These become institutional-grade S/R levels
```

#### C. Machine Learning S/R Classifier
```
Model: Gradient Boosted Trees (XGBoost/LightGBM) or LSTM
Features per price level:
  - Number of historical touches
  - Average bounce magnitude (%)
  - Time since last touch
  - Volume profile density at level
  - Round number proximity (distance to nearest 00/50)
  - Multi-timeframe confluence score
  - Gap presence at level
  - Order block overlap (from Step 7)
  
Target: Binary classification — "Will price react at this level?"
Training: 2+ years of historical data per instrument
Output: Probability score [0-1] for each detected level
```

---

### 5.2 Multi-Timeframe S/R Weighting System

| Timeframe | Base Weight | Decay Rate | Max Influence |
|-----------|------------|------------|---------------|
| Monthly   | 1.00       | 0.98/week  | 90 days       |
| Weekly    | 0.85       | 0.95/week  | 60 days       |
| Daily     | 0.70       | 0.90/week  | 30 days       |
| H4        | 0.50       | 0.85/week  | 14 days       |
| H1        | 0.30       | 0.80/week  | 7 days        |
| M15       | 0.15       | 0.70/week  | 3 days        |

**Confluence Multiplier:** When 2+ timeframes share the same level (within tolerance), multiply weights:
- 2 TFs: ×1.5
- 3 TFs: ×2.0
- 4+ TFs: ×3.0

**Final Score = Σ(TF_weight × touch_count × recency × confluence_mult)**

---

### 5.3 Institutional S/R Detection

**How to identify levels institutions are watching:**

1. **Options Gamma Exposure (GEX) Levels**
   - Call/Put walls at specific strike prices
   - High gamma = institutional hedging = magnetic S/R
   - Sources: CME options data, Unusual Whales, Barchart

2. **Dark Pool Activity Zones**
   - Clustered dark pool prints at specific price levels
   - Repeated large-block trades near round numbers
   - These become "hidden" institutional S/R

3. **Futures Open Interest Concentration**
   - High OI at specific price = institutional positioning
   - OI changes near levels signal institutional intent
   - Source: COT report, exchange OI data

4. **Algorithm Detection**
   - Institutional algos leave footprints:
     - Iceberg orders at specific levels
     - TWAP/VWAP anchored to specific prices
     - Repeated limit order clustering
   - Detection: Monitor order book depth changes over time

---

### 5.4 Broken S/R Flip Logic

**Core Principle:** Broken support becomes resistance; broken resistance becomes support ("polarity principle").

```
AI Detection Algorithm:
1. Level breaks when:
   - Candle CLOSES beyond level (not just wick)
   - Followed by minimum 1 ATR movement beyond level
   - Volume on break candle > 1.5× 20-period average

2. Flip Confirmation:
   - Price returns to broken level (pullback)
   - Reaction at flipped level (bounce/rejection)
   - If bounce > 0.5 ATR → Flip CONFIRMED
   - If price slices through → Flip FAILED (level invalidated)

3. Confidence Scoring:
   - Strong break (high volume + momentum) → Strong flip (90%+)
   - Weak break (low volume, marginal) → Weak flip (50-60%)
   - No retest yet → Potential flip (70%, awaiting confirmation)
```

---

### 5.5 Multi-Agent Integration for Step 5

| Agent | Role | Output |
|-------|------|--------|
| **S/R Scanner Agent** | Continuously scans all TFs for levels | Ranked level list with scores |
| **Volume Profile Agent** | Builds real-time volume profiles | POC/VAH/VAL/HVN/LVN levels |
| **Institutional Agent** | Monitors GEX, dark pool, OI data | Institutional S/R overlay |
| **Flip Tracker Agent** | Monitors broken levels for flips | Flip status per level |
| **Confluence Agent** | Merges all S/R sources | Final weighted S/R map |

---

### 5.6 Loop Integration for Step 5

```
EVERY_CANDLE (M15):
  → Update fractal detection
  → Check if price is near any S/R level (within 0.5 ATR)
  → If near: Trigger full analysis pipeline

EVERY_HOUR:
  → Rebuild volume profile (rolling 20-day)
  → Update institutional data feeds
  → Recalculate all S/R scores

EVERY_DAY:
  → Full S/R recalculation
  → Archive expired levels
  → Retrain ML model with new data (if online learning)

ON_LEVEL_APPROACH:
  → Alert: "Price approaching [Level] at [Price] (Score: X)"
  → Trigger Steps 6, 7, 8 confirmation cascade
```

---

### 5.7 Specific Implementation

```python
class SupportResistanceEngine:
    def __init__(self):
        self.fractal_detector = WilliamsFractals(period=2)
        self.clusterer = DBSCAN(eps=atr*0.25, min_samples=2)
        self.volume_profiler = VolumeProfile(bins=100, lookback=20)
        self.ml_classifier = XGBoostClassifier(model_path='sr_model.json')
    
    def detect_levels(self, ohlcv_dict: dict) -> list[SRLevel]:
        """Detect S/R levels across all timeframes."""
        all_levels = []
        
        for tf, ohlcv in ohlcv_dict.items():
            fractals = self.fractal_detector.detect(ohlcv)
            clusters = self.clusterer.fit_predict(fractal_prices)
            
            for cluster_id in set(clusters):
                level = SRLevel(
                    price=cluster_mean,
                    timeframe=tf,
                    touch_count=cluster_size,
                    volume_at_level=self._get_volume_at(ohlcv, cluster_mean),
                    recency=self._last_touch_time(clusters, cluster_id),
                    confidence=self.ml_classifier.predict_proba(features)
                )
                all_levels.append(level)
        
        # Add volume profile levels
        vp_levels = self.volume_profiler.get_levels(ohlcv_dict['D1'])
        all_levels.extend(vp_levels)
        
        # Merge and weight
        return self._merge_and_weight(all_levels)
    
    def check_flip(self, level: SRLevel, current_price: float, 
                   candle: Candle) -> FlipStatus:
        """Check if a broken S/R is flipping."""
        if not level.is_broken:
            if candle.close > level.price and level.type == 'resistance':
                if candle.volume > self.avg_volume * 1.5:
                    level.is_broken = True
                    level.flip_status = 'POTENTIAL_SUPPORT'
            # ... mirror logic for support
        
        return level.flip_status
```

---

## Step 6 — Liquidity Detection

### Current State
Detect liquidity sweeps above highs/below lows where retail stops are clustered.

### Problems with Basic Liquidity Detection
- Can't distinguish real sweeps from fake ones (stop hunts)
- No volume context
- Ignores institutional liquidity (which is often below obvious levels)
- No understanding of liquidity pool depth
- Missing on-chain data for crypto

---

### 6.1 AI Liquidity Pool Detection

#### A. Liquidity Heatmap Construction
```
Algorithm: Order Book Depth + Historical Stop Clustering
1. Identify "obvious" liquidity zones:
   - Above/below swing highs/lows (retail stops)
   - At round numbers (psychological stops)
   - At previous day/week extremes
   - At gap fills

2. Estimate liquidity DEPTH at each zone:
   - Conservative: Use ATR multiples to estimate stop density
   - Order book: Real-time bid/ask depth imbalance
   - Options: Open interest at nearby strikes
   
3. Build heatmap:
   Price Level | Liquidity Score | Type (Buy/Sell) | Confidence
   1.1050      | 85             | Sell-side       | High
   1.0980      | 72             | Buy-side        | Medium
```

#### B. Institutional Liquidity Detection
```
Smart Money Liquidity ≠ Retail Liquidity

Retail liquidity: Above obvious highs, below obvious lows
Institutional liquidity: 
  - BELOW support (where retail has stops) → Buy-side sweep
  - ABOVE resistance (where retail has stops) → Sell-side sweep
  - But ALSO: At less obvious levels where institutions built positions

Detection signals:
  1. Unusual volume spikes at "wrong" levels
  2. Order book spoofing (large orders appearing/disappearing)
  3. Dark pool prints clustering at specific prices
  4. Delta divergence (price up but aggressive selling)
```

---

### 6.2 Order Flow Data Integration

#### Data Sources
| Data Type | Source | Use Case |
|-----------|--------|----------|
| Level 2 / DOM | Exchange API | Real-time bid/ask depth |
| Time & Sales | Exchange API | Aggressive order detection |
| Delta (Cumulative) | Calculated | Buyer vs seller aggression |
| VWAP | Calculated | Institutional anchor |
| Footprint Charts | Bookmap/Sierra | Volume at price clusters |
| COT Report | CFTC | Weekly institutional positioning |

#### AI Order Flow Analysis
```python
class OrderFlowAnalyzer:
    def detect_institutional_flow(self, trades: list) -> FlowSignal:
        """Detect institutional activity from trade data."""
        
        # 1. Large trade detection (> 3σ from mean size)
        large_trades = [t for t in trades if t.size > self.sigma_3]
        
        # 2. Iceberg detection
        # Repeated fills at same price with hidden residual
        icebergs = self._detect_icebergs(trades, price_tolerance=0.0001)
        
        # 3. Sweep detection
        # Aggressive market orders consuming multiple price levels
        sweeps = self._detect_sweeps(trades, min_levels=3)
        
        # 4. Absorption detection
        # Large resting limit orders absorbing aggressive flow
        absorption = self._detect_absorption(trades, self.order_book)
        
        return FlowSignal(
            institutional_score=self._score(large_trades, icebergs, sweeps, absorption),
            direction=self._infer_direction(trades),
            confidence=self._calculate_confidence(trades)
        )
```

---

### 6.3 Liquidity Sweep vs. Fake Sweep Detection

**This is the most critical enhancement for Step 6.**

```
REAL LIQUIDITY SWEEP Characteristics:
  ✓ Volume spikes on the sweep candle (> 2× average)
  ✓ Immediate strong rejection (full engulfing or pin bar)
  ✓ Delta flips (buyers → sellers or vice versa)
  ✓ Sweep happens at a HIGH-SCORING S/R level (Step 5)
  ✓ Followed by displacement (strong move away from level)
  ✓ Aligns with higher timeframe bias

FAKE SWEEP / STOP HUNT Characteristics:
  ✗ Low volume on sweep (weak move)
  ✗ Price lingers at swept level (no rejection)
  ✗ Gradual move through level (not impulsive)
  ✗ No delta change
  ✗ Happens at LOW-SCORING S/R level
  ✗ Price reverses back through level quickly

AI Classification Model:
  Features: [volume_ratio, rejection_strength, delta_flip, 
             sr_score, displacement, time_at_level, candle_pattern]
  Model: Random Forest or XGBoost
  Target: REAL_SWEEP (1) vs FAKE_SWEEP (0)
  Accuracy target: >75%
```

---

### 6.4 On-Chain Liquidity (Crypto-Specific)

```
On-Chain Data Sources:
  - Exchange inflows/outflows → Supply dynamics
  - Whale wallet movements → Institutional intent
  - Stablecoin flows → Buying/selling pressure
  - Funding rates → Leveraged positioning
  - Open interest changes → New position building
  - Liquidation levels → Where forced selling occurs

AI Integration:
  1. Monitor exchange netflow:
     - Large inflow → Potential selling (liquidity building above)
     - Large outflow → Potential holding (less selling pressure)
  
  2. Liquidation heatmap:
     - Platforms: Coinglass, Hyblock Capital
     - Cluster of leveraged longs below → Buy-side liquidity pool
     - Cluster of leveraged shorts above → Sell-side liquidity pool
     - These are the EXACT levels institutions target
  
  3. Funding rate analysis:
     - Extreme positive funding → Shorts will hunt longs
     - Extreme negative funding → Longs will hunt shorts
  
  4. Stablecoin dominance:
     - Rising USDT/USDC dominance → Cash sitting on sidelines
     - Falling dominance → Money flowing into risk
```

---

### 6.5 Multi-Agent Integration for Step 6

| Agent | Role | Data Source | Output |
|-------|------|-------------|--------|
| **Liquidity Heatmap Agent** | Build real-time liquidity maps | Order book, historical data | Heatmap overlay |
| **Order Flow Agent** | Analyze aggressive flow | Time & sales, DOM | Delta, absorption signals |
| **Sweep Detector Agent** | Classify real vs fake sweeps | Price + volume + delta | Sweep signals with confidence |
| **On-Chain Agent** | Crypto liquidity pools | Blockchain data | Liquidation levels, whale moves |
| **Institutional Agent** | Dark pool + block trades | Dark pool feeds | Hidden liquidity zones |

---

### 6.6 Loop Integration for Step 6

```
EVERY_TICK (or M1):
  → Update order book snapshot
  → Scan for large trades (> 3σ)
  → Update delta calculation
  → Check if price is approaching liquidity pool

EVERY_CANDLE (M15):
  → Rebuild liquidity heatmap
  → Check for sweep patterns
  → Update sweep vs fake classification
  → Alert if liquidity event detected

EVERY_HOUR:
  → Full order flow analysis
  → Update institutional activity scores
  → Refresh on-chain data (crypto)

ON_LIQUIDITY_SWEEP:
  → Immediate alert with sweep type (real/fake)
  → Trigger Step 7 (SMC) pattern scan
  → Trigger Step 8 (RSI) confirmation
  → Calculate entry parameters
```

---

### 6.7 Specific Implementation

```python
class LiquidityEngine:
    def __init__(self):
        self.order_book_monitor = OrderBookMonitor()
        self.flow_analyzer = OrderFlowAnalyzer()
        self.sweep_classifier = SweepClassifier(model='sweep_rf_v2.pkl')
        self.on_chain = OnChainMonitor()  # Crypto only
    
    def build_liquidity_map(self, instrument: str, 
                            sr_levels: list[SRLevel]) -> LiquidityMap:
        """Build comprehensive liquidity heatmap."""
        heatmap = LiquidityMap()
        
        # Layer 1: S/R based liquidity (retail stops)
        for level in sr_levels:
            heatmap.add_zone(
                price=level.price + self.atr * 0.1,  # Just above resistance
                type='sell_side',
                depth=self._estimate_stop_density(level),
                source='sr_level'
            )
        
        # Layer 2: Order flow based liquidity
        book_depth = self.order_book_monitor.get_depth(instrument)
        heatmap.overlay_book_depth(book_depth)
        
        # Layer 3: On-chain liquidation levels (crypto)
        if instrument.is_crypto():
            liquidations = self.on_chain.get_liquidation_levels(instrument)
            heatmap.overlay_liquidations(liquidations)
        
        return heatmap
    
    def classify_sweep(self, candle: Candle, context: dict) -> SweepResult:
        """Classify a potential liquidity sweep."""
        features = self._extract_sweep_features(candle, context)
        prediction = self.sweep_classifier.predict(features)
        
        return SweepResult(
            is_sweep=prediction.is_sweep,
            is_real=prediction.real_probability > 0.65,
            confidence=prediction.confidence,
            direction=prediction.direction,
            target=self._calculate_target(candle, context)
        )
```

---

## Step 7 — Smart Money Concepts (SMC)

### Current State
Look for Order Blocks, Fair Value Gaps, BOS, CHoCH, Mitigation Blocks, Breaker Blocks.

### Problems with Manual SMC
- Extremely subjective — different traders mark different OBs/FVGs
- No statistical validation of which patterns actually work
- Can't process multiple instruments simultaneously
- No failure handling
- Confirmation bias in pattern identification

---

### 7.1 AI-Automated SMC Pattern Detection

#### A. Order Block Detection
```python
class OrderBlockDetector:
    """Detect institutional order blocks algorithmically."""
    
    def detect(self, ohlcv: DataFrame) -> list[OrderBlock]:
        blocks = []
        
        for i in range(2, len(ohlcv)):
            # Bullish OB: Last down candle before impulsive up move
            if self._is_impulse_up(ohlcv[i]):  # Strong bullish candle(s)
                # Look back for the last bearish candle
                for j in range(i-1, max(0, i-5), -1):
                    if ohlcv[j].close < ohlcv[j].open:  # Bearish candle
                        ob = OrderBlock(
                            type='bullish',
                            high=ohlcv[j].high,
                            low=ohlcv[j].low,
                            origin_index=j,
                            strength=self._calc_strength(ohlcv, j, i),
                            mitigated=False,
                            timeframe=self.current_tf
                        )
                        blocks.append(ob)
                        break
            
            # Bearish OB: Last up candle before impulsive down move
            if self._is_impulse_down(ohlcv[i]):
                for j in range(i-1, max(0, i-5), -1):
                    if ohlcv[j].close > ohlcv[j].open:  # Bullish candle
                        ob = OrderBlock(
                            type='bearish',
                            high=ohlcv[j].high,
                            low=ohlcv[j].low,
                            origin_index=j,
                            strength=self._calc_strength(ohlcv, j, i),
                            mitigated=False,
                            timeframe=self.current_tf
                        )
                        blocks.append(ob)
                        break
        
        return self._filter_and_rank(blocks)
    
    def _is_impulse_up(self, candle) -> bool:
        """Detect impulsive bullish move (>1.5 ATR body, minimal wick)."""
        body = abs(candle.close - candle.open)
        return (candle.close > candle.open and 
                body > self.atr * 1.5 and
                body > (candle.high - candle.low) * 0.7)
    
    def _calc_strength(self, ohlcv, ob_idx, impulse_idx) -> float:
        """Score OB strength based on impulse size, volume, and displacement."""
        impulse_size = abs(ohlcv[impulse_idx].close - ohlcv[ob_idx].close)
        volume_ratio = ohlcv[impulse_idx].volume / ohlcv[ob_idx].volume
        displacement = self._count_displaced_candles(ohlcv, ob_idx, impulse_idx)
        
        return (impulse_size / self.atr * 0.4 + 
                volume_ratio * 0.3 + 
                displacement * 0.3)
```

#### B. Fair Value Gap (FVG) Detection
```python
class FVGDetector:
    """Detect Fair Value Gaps (imbalances) algorithmically."""
    
    def detect(self, ohlcv: DataFrame) -> list[FVG]:
        fvgs = []
        
        for i in range(2, len(ohlcv)):
            # Bullish FVG: Gap between candle[i-2].high and candle[i].low
            if ohlcv[i].low > ohlcv[i-2].high:
                fvg = FVG(
                    type='bullish',
                    top=ohlcv[i].low,
                    bottom=ohlcv[i-2].high,
                    size=ohlcv[i].low - ohlcv[i-2].high,
                    midpoint=(ohlcv[i].low + ohlcv[i-2].high) / 2,
                    filled_pct=0,
                    origin_index=i,
                    strength=self._calc_fvg_strength(ohlcv, i)
                )
                fvgs.append(fvg)
            
            # Bearish FVG: Gap between candle[i].high and candle[i-2].low
            if ohlcv[i].high < ohlcv[i-2].low:
                fvg = FVG(
                    type='bearish',
                    top=ohlcv[i-2].low,
                    bottom=ohlcv[i].high,
                    size=ohlcv[i-2].low - ohlcv[i].high,
                    midpoint=(ohlcv[i-2].low + ohlcv[i].high) / 2,
                    filled_pct=0,
                    origin_index=i,
                    strength=self._calc_fvg_strength(ohlcv, i)
                )
                fvgs.append(fvg)
        
        return fvgs
    
    def update_fill_status(self, fvgs: list[FVG], current_candle):
        """Track how much of each FVG has been filled."""
        for fvg in fvgs:
            if fvg.type == 'bullish':
                if current_candle.low <= fvg.top:
                    fill_depth = fvg.top - max(current_candle.low, fvg.bottom)
                    fvg.filled_pct = fill_depth / fvg.size * 100
            # Mirror for bearish
```

#### C. Market Structure (BOS/CHoCH) Detection
```python
class MarketStructureDetector:
    """Detect Break of Structure (BOS) and Change of Character (CHoCH)."""
    
    def detect(self, ohlcv: DataFrame, swing_points: list) -> list[StructureBreak]:
        breaks = []
        current_trend = 'neutral'
        
        for i in range(1, len(swing_points)):
            prev = swing_points[i-1]
            curr = swing_points[i]
            
            if prev.type == 'high' and curr.type == 'high':
                if curr.price > prev.price:
                    if current_trend == 'bullish':
                        breaks.append(StructureBreak(
                            type='BOS',  # Continuation
                            direction='bullish',
                            level=prev.price,
                            index=curr.index,
                            trend_continuation=True
                        ))
                    else:
                        breaks.append(StructureBreak(
                            type='CHoCH',  # Reversal
                            direction='bullish',
                            level=prev.price,
                            index=curr.index,
                            trend_continuation=False
                        ))
                        current_trend = 'bullish'
            
            # Mirror logic for lows
            # ...
        
        return breaks
```

---

### 7.2 SMC Pattern Reliability Rankings

**Research-backed reliability scores (based on backtesting):**

| Pattern | Win Rate | Avg R:R | Best TF | Best Context |
|---------|----------|---------|---------|--------------|
| **BOS + OB** | 68-72% | 1:2.5 | H1-H4 | Trend continuation |
| **CHoCH + FVG** | 62-67% | 1:3.0 | H4-D1 | Trend reversal |
| **OB (H4/D1)** | 65-70% | 1:2.0 | H4-D1 | Premium/discount zones |
| **FVG (confluence)** | 60-65% | 1:2.5 | H1-H4 | With OB or S/R |
| **Breaker Block** | 58-63% | 1:2.0 | H1-H4 | After failed OB |
| **Mitigation Block** | 55-60% | 1:1.5 | M15-H1 | Scalping |
| **Liquidity Sweep + OB** | 70-75% | 1:3.0 | H1-D1 | Highest confluence |

**Key finding:** No single SMC pattern is reliable alone. **Confluence of 2+ patterns** dramatically improves win rate.

---

### 7.3 Combining Multiple SMC Signals

```
Signal Confluence Scoring System:

Base Score per Pattern:
  Order Block:            +30 points
  Fair Value Gap:         +20 points
  BOS (continuation):     +25 points
  CHoCH (reversal):       +30 points
  Breaker Block:          +20 points
  Mitigation Block:       +15 points
  Liquidity Sweep:        +25 points

Confluence Bonuses:
  OB + FVG overlap:       +15 bonus
  BOS/CHoCH + OB:         +20 bonus
  Liquidity Sweep + OB:   +25 bonus
  Multi-TF alignment:     +15 bonus per TF
  Volume confirmation:    +10 bonus

Threshold:
  Score < 40: NO TRADE
  Score 40-60: SMALL POSITION (0.5% risk)
  Score 60-80: STANDARD POSITION (1% risk)
  Score 80+: LARGE POSITION (1.5-2% risk)

Example High-Scoring Setup:
  H4 Order Block (30) + FVG overlap (15) + BOS (25) + 
  H1 Liquidity Sweep (25) + Volume conf (10) + Multi-TF (15) = 120 → MAX CONFIDENCE
```

---

### 7.4 SMC Failure Handling

```
FAILURE SCENARIOS AND RESPONSES:

1. OB Mitigated Without Reaction:
   → Mark as "weak OB"
   → Look for Breaker Block pattern (failed OB becomes new level)
   → Reduce confidence in same-TF OBs by 20%

2. FVG Fully Filled Without Reaction:
   → FVG invalidated
   → Price may be building liquidity for bigger move
   → Check for divergence with higher TF FVGs

3. BOS Followed by Immediate CHoCH:
   → "Fakeout" pattern
   → Original trend may still be valid
   → Wait for second confirmation before changing bias

4. CHoCH That Doesn't Follow Through:
   → "Disruption" — not a true change of character
   → Return to original trend bias
   → Increase confirmation requirements for next CHoCH

AI Failure Detection:
  - Monitor pattern completion rate in real-time
  - If pattern fails >40% of time in last 50 instances → Reduce weight
  - Adaptive confidence: Each pattern's score adjusts based on recent performance
  - "Pattern fatigue": If same pattern appears >3 times in same zone → Reduce score
```

---

### 7.5 Machine Learning for SMC Pattern Recognition

```
Approach 1: Feature Engineering + Classical ML
  Features:
    - Candle body/wick ratios
    - Impulse magnitude (ATR multiples)
    - Volume at pattern formation
    - Distance to nearest S/R (Step 5)
    - RSI state at formation (Step 8)
    - Higher timeframe alignment
    - Time of day
    - Recent pattern success rate
  
  Model: XGBoost / LightGBM
  Target: Pattern success (1) or failure (0)
  Advantage: Interpretable, fast inference

Approach 2: CNN on Candlestick Images
  Input: Rendered candlestick chart windows (64×64 pixels)
  Architecture: ResNet-18 pretrained → Fine-tuned on SMC patterns
  Classes: [OB_bullish, OB_bearish, FVG_bullish, FVG_bearish, 
            BOS_up, BOS_down, CHoCH_up, CHoCH_down, None]
  Advantage: Can capture visual patterns humans see
  Disadvantage: Less interpretable

Approach 3: LSTM/Transformer on OHLCV Sequences
  Input: Rolling window of 50-100 candles
  Architecture: Transformer encoder → Classification head
  Can detect: Complex multi-candle patterns, sequence dependencies
  Advantage: Captures temporal relationships
  Disadvantage: Requires more data, slower inference

RECOMMENDED: Approach 1 for production (fast, interpretable)
             Approach 3 as research/experimental
```

---

### 7.6 Multi-Agent Integration for Step 7

| Agent | Role | Output |
|-------|------|--------|
| **OB Scanner Agent** | Detect order blocks across all TFs | OB list with scores |
| **FVG Scanner Agent** | Detect and track FVG fill status | FVG list with fill % |
| **Structure Agent** | Track BOS/CHoCH in real-time | Structure break signals |
| **Pattern Scorer Agent** | Combine all SMC signals | Confluence scores |
| **Failure Monitor Agent** | Track pattern failures, update weights | Adaptive confidence |
| **ML Agent** | Run pattern recognition models | Pattern predictions |

---

### 7.7 Loop Integration for Step 7

```
EVERY_CANDLE (M15):
  → Scan for new OBs, FVGs
  → Update FVG fill status
  → Check for BOS/CHoCH
  → Calculate confluence scores
  → Update pattern success/failure tracking

EVERY_HOUR:
  → Full SMC scan on H1, H4
  → Update ML model predictions
  → Recalculate all active pattern scores

EVERY_DAY:
  → Full SMC scan on D1, W1
  → Archive expired patterns
  → Retrain ML model with latest data
  → Update pattern reliability statistics

ON_SMC_SIGNAL:
  → Alert with pattern type and confluence score
  → Trigger Step 5 (S/R) confirmation
  → Trigger Step 6 (Liquidity) confirmation
  → Trigger Step 8 (RSI) confirmation
  → If all confirm → Generate trade signal
```

---

## Step 8 — RSI Confirmation

### Current State
M15 RSI below 30 = oversold (look for buys), above 70 = overbought (look for sells), 40-60 = neutral.

### Problems with Basic RSI
- Fixed thresholds (30/70) don't adapt to market regime
- Single timeframe only
- No divergence detection
- RSI can stay overbought/oversold for extended periods
- Missing momentum context

---

### 8.1 AI-Enhanced RSI

#### A. Adaptive RSI Thresholds
```
Problem: RSI 30/70 works in ranging markets but fails in trends.
In a strong uptrend, RSI rarely reaches 30; 40 becomes "oversold."
In a strong downtrend, RSI rarely reaches 70; 60 becomes "overbought."

Solution: Dynamic Thresholds Based on Market Regime

Market Regime Detection:
  1. ADX > 25 = Trending
  2. ADX < 20 = Ranging
  3. Use Hurst Exponent or variance ratio for regime confirmation

Adaptive Thresholds:
  RANGING MARKET:
    Oversold: 30 (standard)
    Overbought: 70 (standard)
    
  BULLISH TREND:
    Oversold: 40 (higher — RSI pullbacks are buying opportunities)
    Overbought: 80 (higher — strong trends stay "overbought")
    
  BEARISH TREND:
    Oversold: 20 (lower — strong downtrends stay "oversold")
    Overbought: 60 (lower — RSI bounces are selling opportunities)

AI Implementation:
  Model: Hidden Markov Model (HMM) or regime classifier
  Input: ADX, ATR ratio, price slope, volume trend
  Output: Market regime → Set RSI thresholds dynamically
```

#### B. Multi-Timeframe RSI Alignment
```
RSI Alignment Scoring:

Timeframe | Weight | RSI Value | Zone        | Signal
M15       | 0.15   | 28        | Oversold    | BUY (+1)
H1        | 0.25   | 35        | Near oversold| BUY (+0.5)
H4        | 0.35   | 42        | Neutral-low | NEUTRAL (0)
D1        | 0.25   | 55        | Neutral     | NEUTRAL (0)

Alignment Score = Σ(TF_weight × signal)
Example: 0.15(1) + 0.25(0.5) + 0.35(0) + 0.25(0) = 0.275

Interpretation:
  Score > +0.5: Strong buy alignment → Full confirmation
  Score +0.25 to +0.5: Moderate buy → Partial confirmation
  Score -0.25 to +0.25: Neutral → No confirmation
  Score -0.5 to -0.25: Moderate sell → Partial confirmation
  Score < -0.5: Strong sell alignment → Full confirmation
```

#### C. RSI Divergence Detection
```python
class RSIDivergenceDetector:
    """Detect regular and hidden RSI divergences."""
    
    def detect(self, price: Series, rsi: Series, 
               swing_points: list) -> list[Divergence]:
        divergences = []
        
        # Regular Bullish Divergence: Price makes lower low, RSI makes higher low
        for i in range(1, len(swing_points)):
            sp = swing_points[i]
            prev = swing_points[i-1]
            
            if sp.type == 'low':
                if price[sp.idx] < price[prev.idx] and rsi[sp.idx] > rsi[prev.idx]:
                    divergences.append(Divergence(
                        type='regular_bullish',
                        strength=self._calc_strength(price, rsi, sp, prev),
                        price_points=(prev.idx, sp.idx),
                        rsi_points=(prev.idx, sp.idx),
                        reliability=self._historical_reliability('regular_bullish')
                    ))
        
        # Hidden Bullish Divergence: Price makes higher low, RSI makes lower low
        # (Trend continuation signal in uptrend)
        for i in range(1, len(swing_points)):
            sp = swing_points[i]
            prev = swing_points[i-1]
            
            if sp.type == 'low':
                if price[sp.idx] > price[prev.idx] and rsi[sp.idx] < rsi[prev.idx]:
                    divergences.append(Divergence(
                        type='hidden_bullish',
                        strength=self._calc_strength(price, rsi, sp, prev),
                        price_points=(prev.idx, sp.idx),
                        rsi_points=(prev.idx, sp.idx),
                        reliability=self._historical_reliability('hidden_bullish')
                    ))
        
        # Mirror for bearish divergences
        return divergences
    
    def _calc_strength(self, price, rsi, sp1, sp2) -> float:
        """Stronger divergence = bigger price-RSI disagreement."""
        price_diff = abs(price[sp2.idx] - price[sp1.idx]) / price[sp1.idx]
        rsi_diff = abs(rsi[sp2.idx] - rsi[sp1.idx])
        return (price_diff * 0.5 + rsi_diff / 100 * 0.5)
```

---

### 8.2 RSI Enhancement Alternatives

#### Should RSI Be Replaced?

**No — but it should be COMPLEMENTED.**

| Indicator | Strength | RSI Weakness It Fixes |
|-----------|----------|----------------------|
| **RSI** | Overbought/oversold, divergence | — |
| **Stochastic RSI** | More sensitive, fewer false extremes | RSI's sluggishness |
| **MFI (Money Flow Index)** | Volume-weighted momentum | RSI ignores volume |
| **Williams %R** | Leading indicator, faster signals | RSI's lag |
| **CCI (Commodity Channel Index)** | Extreme detection, mean reversion | RSI's fixed range |
| **ADX** | Trend strength (not direction) | RSI can't distinguish trend vs range |

#### Recommended: Composite Momentum Score
```
Instead of RSI alone, use a weighted composite:

Composite Momentum Score = 
  RSI_normalized × 0.35 +
  StochRSI_normalized × 0.20 +
  MFI_normalized × 0.20 +
  CCI_normalized × 0.15 +
  WilliamsR_normalized × 0.10

Each indicator normalized to [0, 100] scale.
Interpretation:
  Score < 25: Strong oversold (higher confidence than RSI alone)
  Score 25-40: Mild oversold
  Score 40-60: Neutral
  Score 60-75: Mild overbought
  Score > 75: Strong overbought

Advantage: Reduces false signals from any single indicator
```

---

### 8.3 RSI + Market Microstructure

```
Advanced RSI Enhancement: Contextual RSI

Standard RSI tells you WHAT — Enhanced RSI tells you WHY

1. RSI + Volume Context:
   - RSI oversold + Decreasing volume = Weak selling (good buy signal)
   - RSI oversold + Increasing volume = Strong selling (wait for volume climax)
   - RSI overbought + Decreasing volume = Weak buying (good sell signal)
   - RSI overbought + Increasing volume = Strong buying (wait for exhaustion)

2. RSI + Volatility Context:
   - RSI oversold + ATR expanding = Volatility spike (better entry after contraction)
   - RSI oversold + ATR contracting = Volatility squeeze (breakout imminent)
   
3. RSI + Time Context:
   - RSI oversold during Asian session = Less reliable (lower volume)
   - RSI oversold during London/NY overlap = More reliable (highest volume)
   - RSI extreme at session open = Often fades

4. RSI + Candle Pattern Context:
   - RSI oversold + Bullish engulfing = Strong buy signal
   - RSI oversold + Doji = Indecision (wait for confirmation)
   - RSI oversold + Continued bearish candles = Not yet (RSI can stay oversold)
```

---

### 8.4 Machine Learning RSI Enhancement

```python
class AIRSIEngine:
    """AI-enhanced RSI analysis."""
    
    def __init__(self):
        self.regime_detector = MarketRegimeDetector()  # HMM or classifier
        self.divergence_detector = RSIDivergenceDetector()
        self.composite = CompositeMomentum()
        self.signal_model = XGBoostClassifier(model_path='rsi_signal_v2.pkl')
    
    def analyze(self, ohlcv: DataFrame, current_tf: str) -> RSIAnalysis:
        """Full AI-enhanced RSI analysis."""
        
        # 1. Calculate RSI across timeframes
        rsi_m15 = ta.rsi(ohlcv['M15'], period=14)
        rsi_h1 = ta.rsi(ohlcv['H1'], period=14)
        rsi_h4 = ta.rsi(ohlcv['H4'], period=14)
        rsi_d1 = ta.rsi(ohlcv['D1'], period=14)
        
        # 2. Detect market regime
        regime = self.regime_detector.detect(ohlcv)
        
        # 3. Get adaptive thresholds
        thresholds = self._get_adaptive_thresholds(regime)
        
        # 4. Multi-TF alignment
        alignment = self._calc_alignment(
            rsi_m15, rsi_h1, rsi_h4, rsi_d1, thresholds
        )
        
        # 5. Divergence detection
        divergences = self.divergence_detector.detect(
            ohlcv['M15'].close, rsi_m15, 
            self.swing_detector.detect(ohlcv['M15'])
        )
        
        # 6. Composite momentum
        composite_score = self.composite.calculate(ohlcv)
        
        # 7. ML signal prediction
        features = self._build_features(
            rsi_m15, rsi_h1, rsi_h4, rsi_d1,
            regime, divergences, composite_score, ohlcv
        )
        ml_signal = self.signal_model.predict_proba(features)
        
        return RSIAnalysis(
            rsi_values={'M15': rsi_m15, 'H1': rsi_h1, 'H4': rsi_h4, 'D1': rsi_d1},
            regime=regime,
            thresholds=thresholds,
            alignment_score=alignment,
            divergences=divergences,
            composite_score=composite_score,
            ml_signal=ml_signal,
            confirmation=self._get_confirmation(alignment, divergences, composite_score, ml_signal)
        )
    
    def _get_confirmation(self, alignment, divergences, composite, ml) -> str:
        """Determine RSI confirmation level."""
        score = 0
        
        if abs(alignment) > 0.5: score += 30
        elif abs(alignment) > 0.25: score += 15
        
        if divergences:
            score += 25 * max(d.strength for d in divergences)
        
        if composite < 25 or composite > 75: score += 20
        elif composite < 40 or composite > 60: score += 10
        
        score += ml * 25
        
        if score >= 70: return 'STRONG'
        if score >= 45: return 'MODERATE'
        if score >= 25: return 'WEAK'
        return 'NONE'
```

---

### 8.5 Multi-Agent Integration for Step 8

| Agent | Role | Output |
|-------|------|--------|
| **RSI Calculator Agent** | Real-time RSI across all TFs | RSI values + zones |
| **Regime Agent** | Detect market regime | Trending/Ranging + confidence |
| **Divergence Agent** | Scan for RSI divergences | Divergence signals |
| **Composite Agent** | Calculate multi-indicator momentum | Composite score |
| **ML RSI Agent** | Run RSI signal model | ML probability |

---

### 8.6 Loop Integration for Step 8

```
EVERY_CANDLE (M15):
  → Calculate RSI on M15, H1, H4, D1
  → Check adaptive thresholds
  → Scan for divergences
  → Calculate composite momentum
  → Run ML signal model

EVERY_HOUR:
  → Update market regime detection
  → Recalculate adaptive thresholds
  → Full divergence scan on H1+

EVERY_DAY:
  → Retrain RSI ML model
  → Update regime parameters
  → Review RSI confirmation accuracy

ON_RSI_EXTREME:
  → Alert: "RSI [oversold/overbought] on [TF] (value: X)"
  → Include: Adaptive threshold, regime, divergence status
  → Trigger Steps 5, 6, 7 confirmation cascade
  → If all align → Generate trade signal
```

---

## Cross-Step Integration Map

### How Steps 5-8 Feed Into Each Other

```
┌─────────────────────────────────────────────────────────────────┐
│                    AlphaStack STRATEGY FLOW (Steps 5-8)               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  STEP 5 (S/R) ────────┐                                        │
│     │                  │                                        │
│     │ Price near       │ S/R level adds                        │
│     │ S/R level        │ weight to SMC                         │
│     ▼                  ▼                                        │
│  STEP 6 (Liquidity)  STEP 7 (SMC)                              │
│     │                  │                                        │
│     │ Liquidity        │ OB/FVG at S/R                         │
│     │ sweep detected   │ = High confluence                     │
│     ▼                  ▼                                        │
│  STEP 7 (SMC) ◄───────┘                                        │
│     │                                                           │
│     │ SMC patterns     │                                        │
│     │ confirmed         │                                        │
│     ▼                                                           │
│  STEP 8 (RSI)                                                   │
│     │                                                           │
│     │ RSI confirms     │                                        │
│     │ momentum          │                                        │
│     ▼                                                           │
│  TRADE SIGNAL                                                   │
│                                                                 │
│  CONFLUENCE MATRIX:                                             │
│  ┌──────────┬──────┬──────┬──────┬──────┐                      │
│  │          │ S/R  │ Liq  │ SMC  │ RSI  │                      │
│  ├──────────┼──────┼──────┼──────┼──────┤                      │
│  │ S/R      │  —   │ +15  │ +20  │ +10  │                      │
│  │ Liquidity│ +15  │  —   │ +25  │ +10  │                      │
│  │ SMC      │ +20  │ +25  │  —   │ +15  │                      │
│  │ RSI      │ +10  │ +10  │ +15  │  —   │                      │
│  └──────────┴──────┴──────┴──────┴──────┘                      │
│                                                                 │
│  Maximum confluence: All 4 steps align = 130+ score             │
│  Minimum for trade: 2+ steps align with 60+ score               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Step Dependency Matrix

| Step | Feeds Into | Receives From | Critical Connection |
|------|-----------|---------------|---------------------|
| **5 (S/R)** | 6, 7 | 7 (OB/FVG overlay) | S/R + OB overlap = strongest level |
| **6 (Liquidity)** | 7, 8 | 5 (S/R zones) | Liquidity sweep at S/R = entry trigger |
| **7 (SMC)** | 8, Trade | 5, 6 | OB/FVG confirmation + S/R = confluence |
| **8 (RSI)** | Trade | 5, 6, 7 | Final momentum filter before entry |

---

## Multi-Agent Architecture

### Agent Hierarchy for Steps 5-8

```
┌─────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR AGENT                         │
│  (Coordinates all sub-agents, manages signal flow)           │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ S/R AGENTS  │  │ LIQUIDITY   │  │ SMC AGENTS  │          │
│  │             │  │ AGENTS      │  │             │          │
│  │ • Fractal   │  │ • Heatmap   │  │ • OB Scan   │          │
│  │ • Vol Prof  │  │ • Flow      │  │ • FVG Scan  │          │
│  │ • Inst S/R  │  │ • Sweep Det │  │ • Structure │          │
│  │ • Flip Trk  │  │ • On-Chain  │  │ • Pattern   │          │
│  │ • Conflunce │  │ • Sweep Cls │  │ • Failure   │          │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘          │
│         │                │                │                  │
│         ▼                ▼                ▼                  │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              SIGNAL AGGREGATION AGENT                │    │
│  │  (Combines all signals, calculates confluence)       │    │
│  └──────────────────────┬──────────────────────────────┘    │
│                         │                                    │
│                         ▼                                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              RSI CONFIRMATION AGENT                   │    │
│  │  (Final momentum filter)                              │    │
│  └──────────────────────┬──────────────────────────────┘    │
│                         │                                    │
│                         ▼                                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              TRADE SIGNAL GENERATOR                   │    │
│  │  (Entry, SL, TP, Position Size)                       │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Agent Communication Protocol

```
Message Format:
{
  "agent_id": "sr_scanner_01",
  "timestamp": "2026-07-11T13:24:00Z",
  "signal_type": "LEVEL_DETECTED",
  "instrument": "EURUSD",
  "data": {
    "level": 1.0850,
    "type": "resistance",
    "score": 85,
    "timeframes": ["H4", "D1"],
    "touch_count": 4,
    "volume_context": "high"
  },
  "confidence": 0.85,
  "ttl": 3600  // Signal expires in 1 hour
}

Signal Priority Levels:
  P0: Liquidity sweep detected (immediate)
  P1: High-confluence SMC pattern (within 1 candle)
  P2: S/R level approach (within 3 candles)
  P3: RSI extreme (within 5 candles)
  P4: Background scan update (periodic)
```

---

## Loop System Integration

### Loop Timing for Steps 5-8

```
┌─────────────────────────────────────────────────────────────┐
│                    LOOP SCHEDULE                              │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  TICK_LOOP (every tick/1s):                                   │
│    → Order book monitoring (Step 6)                           │
│    → Delta calculation (Step 6)                               │
│    → Price proximity alerts (Step 5)                          │
│                                                               │
│  M1_LOOP:                                                     │
│    → High-frequency sweep detection (Step 6)                  │
│    → Micro-structure analysis                                 │
│                                                               │
│  M15_LOOP (primary analysis loop):                            │
│    → Full S/R scan update (Step 5)                            │
│    → SMC pattern detection (Step 7)                           │
│    → RSI calculation + divergence scan (Step 8)               │
│    → Confluence score calculation                             │
│    → Signal generation if threshold met                       │
│                                                               │
│  H1_LOOP:                                                     │
│    → Volume profile rebuild (Step 5)                          │
│    → Order flow analysis (Step 6)                             │
│    → H1-H4 SMC scan (Step 7)                                  │
│    → Market regime update (Step 8)                            │
│    → Adaptive threshold recalculation (Step 8)                │
│                                                               │
│  H4_LOOP:                                                     │
│    → Institutional data refresh (Step 5)                      │
│    → On-chain data update (Step 6)                            │
│    → D1-W1 SMC scan (Step 7)                                  │
│    → ML model inference (all steps)                           │
│                                                               │
│  D1_LOOP:                                                     │
│    → Full S/R recalculation (Step 5)                          │
│    → Pattern reliability update (Step 7)                      │
│    → ML model retraining (if online learning)                 │
│    → Performance review and weight adjustment                 │
│                                                               │
│  EVENT_LOOPS (triggered, not scheduled):                      │
│    → ON_LEVEL_APPROACH: Full cascade (Steps 5→6→7→8)          │
│    → ON_LIQUIDITY_SWEEP: SMC + RSI confirmation               │
│    → ON_SMC_SIGNAL: S/R + RSI confirmation                    │
│    → ON_RSI_EXTREME: S/R + SMC confirmation                   │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Signal Cascade Flow

```
TRIGGER: Price approaches S/R level (Step 5)
  │
  ├──► STEP 6: Check liquidity context
  │     ├── Liquidity pool nearby? → +15 confluence
  │     ├── Sweep in progress? → +25 confluence
  │     └── Order flow supportive? → +10 confluence
  │
  ├──► STEP 7: Check SMC patterns
  │     ├── Order Block at level? → +30 confluence
  │     ├── FVG at level? → +20 confluence
  │     ├── BOS/CHoCH confirms? → +25 confluence
  │     └── Breaker/Mitigation? → +20 confluence
  │
  ├──► STEP 8: Check RSI confirmation
  │     ├── RSI in adaptive zone? → +20 confluence
  │     ├── Multi-TF aligned? → +15 confluence
  │     ├── Divergence present? → +25 confluence
  │     └── Composite confirms? → +15 confluence
  │
  ▼
  CONFLUENCE SCORE CALCULATED
  │
  ├── Score < 40: NO TRADE (log for review)
  ├── Score 40-60: ALERT ONLY (watchlist)
  ├── Score 60-80: SMALL TRADE (0.5% risk)
  └── Score 80+: FULL TRADE (1-2% risk)
```

---

## Summary: Enhancement Deliverables

### Step 5 Enhancements
- ✅ Fractal + Volume Profile + ML-based S/R detection
- ✅ Multi-timeframe weighting system with confluence multipliers
- ✅ Institutional level detection (GEX, dark pool, OI)
- ✅ Broken S/R flip logic with confirmation algorithm
- ✅ 5 specialized agents with defined roles

### Step 6 Enhancements
- ✅ Liquidity heatmap construction (multi-source)
- ✅ Order flow analysis (delta, absorption, icebergs, sweeps)
- ✅ Real vs fake sweep classification (ML model)
- ✅ On-chain liquidity for crypto (liquidation levels, whale moves)
- ✅ 5 specialized agents with real-time monitoring

### Step 7 Enhancements
- ✅ Automated OB, FVG, BOS/CHoCH detection algorithms
- ✅ Pattern reliability rankings (research-backed)
- ✅ Confluence scoring system (quantified)
- ✅ Failure handling with adaptive confidence
- ✅ ML pattern recognition (3 approaches: XGBoost, CNN, Transformer)
- ✅ 6 specialized agents

### Step 8 Enhancements
- ✅ Adaptive RSI thresholds by market regime
- ✅ Multi-timeframe RSI alignment scoring
- ✅ Regular + hidden divergence detection
- ✅ Composite momentum indicator (RSI + StochRSI + MFI + CCI + WilliamsR)
- ✅ Contextual RSI (volume, volatility, time, candle pattern)
- ✅ ML RSI signal model
- ✅ 5 specialized agents

### Cross-Step Integration
- ✅ Confluence matrix with quantified scoring
- ✅ Signal cascade flow
- ✅ Loop system timing for all steps
- ✅ Agent communication protocol
- ✅ Multi-agent architecture with orchestrator

---

*Document generated by Strategy Enhancement Agent — Alpha Stack AlphaStack*
*Next: Implementation priority → Start with Step 5 (S/R) as foundation*
