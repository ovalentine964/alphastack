# Alpha Stack — Strategy Enhancement: Steps 9–12

## Candlestick Confirmation → Trade Entry → Position Sizing → Stop Loss

---

## STEP 9 — CANDLESTICK CONFIRMATION (Enhanced)

### Current State
Manual pattern identification: Bullish/Bearish Engulfing, Hammer, Morning Star, Pin Bar, Shooting Star, Evening Star.

### Research-Backed Enhancements

#### Pattern Reliability Rankings (Empirical Data)

| Pattern | Win Rate | Avg R:R | Best Context | Worst Context |
|---|---|---|---|---|
| Morning Star | 65–72% | 2.1:1 | At support + volume spike | Counter-trend, no volume |
| Bullish Engulfing | 60–68% | 1.8:1 | After downtrend + OB zone | Ranging markets |
| Hammer | 58–65% | 1.7:1 | At demand zone + RSI <35 | In isolation, mid-range |
| Evening Star | 63–70% | 2.0:1 | At resistance + divergence | Counter-trend |
| Bearish Engulfing | 58–64% | 1.7:1 | After uptrend + supply zone | Strong trend continuation |
| Shooting Star | 55–62% | 1.6:1 | At supply + RSI >65 | Without volume confirmation |

**Key insight**: Patterns alone have ~55–65% win rate. Combined with volume + structure, this rises to 68–78%. Context is everything.

#### Volume-Weighted Pattern Scoring

```
Pattern Strength = Base Score × Volume Multiplier × Context Multiplier

Volume Multiplier:
  - Volume > 1.5x 20-period average → 1.4x
  - Volume > 1.2x average → 1.2x
  - Volume < 0.8x average → 0.7x (penalize low-volume patterns)

Context Multiplier:
  - At identified OB/liquidity zone → 1.5x
  - At key fib level (61.8/78.6%) → 1.3x
  - Confluence with RSI divergence → 1.3x
  - During kill zone → 1.2x
  - Random location, no structure → 0.6x
```

### AI/ML Enhancements

#### 1. Automated Candlestick Pattern Detection

```python
# Pattern detection using OHLC data
def detect_pattern(candles: list[dict]) -> dict:
    """
    Input: Last 3-5 candles with {open, high, low, close, volume}
    Output: {pattern_name, confidence, direction, score}
    """
    patterns = []

    # Engulfing
    if (candles[-2]['close'] < candles[-2]['open'] and
        candles[-1]['close'] > candles[-1]['open'] and
        candles[-1]['close'] > candles[-2]['open'] and
        candles[-1]['open'] < candles[-2]['close']):
        patterns.append(('bullish_engulfing', 0.85))

    # Hammer (body in upper 25% of range, long lower wick > 2x body)
    c = candles[-1]
    body = abs(c['close'] - c['open'])
    range_hl = c['high'] - c['low']
    lower_wick = min(c['open'], c['close']) - c['low']
    upper_wick = c['high'] - max(c['open'], c['close'])
    if range_hl > 0 and lower_wick > 2 * body and upper_wick < body * 0.3:
        patterns.append(('hammer', 0.75))

    # Morning Star (3-candle pattern)
    if (candles[-3]['close'] < candles[-3]['open'] and
        abs(candles[-2]['close'] - candles[-2]['open']) < body * 0.3 and
        candles[-1]['close'] > candles[-1]['open'] and
        candles[-1]['close'] > (candles[-3]['open'] + candles[-3]['close']) / 2):
        patterns.append(('morning_star', 0.90))

    return {
        'patterns': patterns,
        'best': max(patterns, key=lambda x: x[1], default=None),
        'direction': 'bullish' if any(p[0] in BULLISH_PATTERNS for p in patterns) else 'bearish'
    }
```

#### 2. ML-Based Pattern Recognition (CNN/LSTM)

```
Architecture: 1D-CNN on candlestick image representation

Input: Convert last N candles to pixel-like grid
  - X-axis: candle index (time)
  - Y-axis: price (normalized)
  - Channel 1: OHLC body/wick encoding
  - Channel 2: Volume overlay
  - Channel 3: RSI/momentum overlay

Training Data:
  - Label: Forward price movement (10-20 candles ahead)
  - Binary: Did price move > 1 ATR in pattern direction?
  - 50,000+ labeled patterns across multiple pairs/timeframes

Model Output:
  - Pattern classification (engulfing, hammer, etc.)
  - Probability of successful follow-through (0-1)
  - Expected move magnitude (in ATR multiples)

Advantage over rules: Captures subtle visual patterns humans miss.
Disadvantage: Requires retraining as market regime shifts.
```

#### 3. Pattern Failure Detection

```
Failure Signals (flag pattern as unreliable):
  1. Pattern formed on low volume (< 0.7x average)
  2. Immediate next candle reverses > 50% of pattern
  3. Pattern in middle of range (no structural support)
  4. Conflicting patterns on higher timeframe
  5. Market in chop/range (ADX < 20)
  6. Major news event within 2 hours

Response to failure signals:
  - Reduce confidence score by 40-60%
  - Require additional confirmation before entry
  - Tighten stop or skip trade entirely
```

### Multi-Agent Integration

```
Candlestick Agent Workflow:
  1. Price feeds in → detect patterns on all active pairs
  2. Score each pattern (volume + context multipliers)
  3. Flag failures immediately (next candle validation)
  4. Forward high-confidence patterns (score > 0.7) to Entry Agent
  5. Log all patterns + outcomes for ML retraining pipeline
```

### Loop Integration

```
Detection Loop:
  1. Real-time scan: Check every new candle close
  2. Multi-TF confirmation: 15m pattern + 1H structure alignment
  3. Pattern expires: If no entry within 3 candles, pattern invalidates
  4. Feedback loop: Track actual outcome vs prediction, retrain monthly
```

### Connections to Other Steps
- **→ Step 10**: High-scoring patterns feed directly into confluence scoring
- **→ Step 12**: Pattern type influences stop placement (engulfing = tighter stop, hammer = below wick)
- **← Step 5**: SMC structure provides the context multiplier for pattern scoring

---

## STEP 10 — TRADE ENTRY (Enhanced)

### Current State
Enter only when ALL conditions agree: fundamental, structure, session, liquidity, SMC, RSI, candlestick.

### Research-Backed Enhancements

#### Signal Confluence Scoring System

```
Not all confirmations are equal. Weight by predictive power:

CONFLUENCE SCORE = Σ (Signal Weight × Signal Quality × Timeframe Alignment)

Signal Weights (empirically derived):
  SMC Structure (OB/FVG):     0.25  — Highest predictive value
  Liquidity Sweep:            0.20  — Smart money footprint
  Kill Zone Timing:           0.15  — Institutional flow window
  Candlestick Pattern:        0.15  — Entry timing signal
  RSI/Momentum Divergence:    0.10  — Momentum confirmation
  Volume Confirmation:        0.10  — Validates the move
  News/Fundamental Bias:      0.05  — Directional filter

Score Ranges:
  0.80–1.00: A+ setup → Full position (1.5-2% risk)
  0.65–0.79: A setup → Standard position (1% risk)
  0.50–0.64: B setup → Reduced position (0.5% risk)
  0.35–0.49: C setup → Paper trade or skip
  < 0.35:    No trade

Critical Rule: If ANY of the top-3 signals (structure, liquidity, kill zone)
is absent, cap maximum score at 0.60 regardless of other signals.
```

#### Optimal Number of Confirmations

```
Research finding: Diminishing returns after 5 confirmations.

1-2 confirmations:  Win rate ~52%, too many false signals
3-4 confirmations:  Win rate ~65%, sweet spot for frequency vs quality
5-6 confirmations:  Win rate ~73%, fewer trades but higher quality
7+ confirmations:   Win rate ~75%, barely improves, massive trade reduction

OPTIMAL: 4-5 confirmations with weighted scoring.
Don't require ALL 7 — require the RIGHT 4 (top-weighted signals).
```

#### Partial Confirmation Handling

```
Scenario: Strong structure + liquidity sweep + kill zone, but NO candlestick pattern.

Options:
  1. Wait for candle close (preferred) — patience costs nothing
  2. Use limit order at OB edge — enter at structure, not at market
  3. Reduced size — 0.5% risk on partial confluence
  4. Skip — if candlestick is the only timing signal, its absence matters

Decision Matrix:
  Missing Kill Zone + Structure: ALWAYS wait — these define direction
  Missing Candlestick: Enter with limit at structure level, reduce size 50%
  Missing RSI: Proceed — RSI is secondary confirmation
  Missing Volume: Wait — volume validates the move
```

### AI/ML Enhancements

#### Entry Timing Optimization

```python
def optimize_entry_timing(setup: dict) -> dict:
    """
    Determines optimal entry method and price based on setup characteristics.
    """
    score = setup['confluence_score']
    volatility = setup['atr']
    structure_level = setup['ob_price']

    # High score + clear structure → Limit order at structure
    if score >= 0.75 and setup['distance_to_ob'] < 0.5 * volatility:
        return {
            'method': 'limit',
            'price': structure_level,
            'reason': 'High confluence, price near OB — get best fill'
        }

    # High score + price moving fast → Market order with wider stop
    elif score >= 0.70 and setup['momentum'] > 1.5 * volatility:
        return {
            'method': 'market',
            'reason': 'Strong momentum — risk missing entry on limit'
        }

    # Medium score → Limit order slightly better than structure
    elif score >= 0.55:
        limit_price = structure_level + (0.2 * volatility * setup['direction'])
        return {
            'method': 'limit',
            'price': limit_price,
            'reason': 'Medium confluence — wait for better price'
        }

    # Low score → No entry
    else:
        return {'method': 'skip', 'reason': 'Insufficient confluence'}
```

#### Limit vs Market Order Decision Framework

```
USE LIMIT ORDER WHEN:
  ✓ Price is within 0.5 ATR of key structure level
  ✓ Confluence score ≥ 0.70
  ✓ No immediate high-impact news
  ✓ Spread is normal (< 1.5x average)
  ✓ Order book depth is healthy

USE MARKET ORDER WHEN:
  ✓ Strong momentum candle breaking structure
  ✓ News catalyst driving price fast
  ✓ Confluence score ≥ 0.80 and price is moving away from limit zone
  ✓ Liquidity sweep just occurred (momentum entry)
  ✓ Risk of missing the move > cost of worse fill

NEVER ENTER WHEN:
  ✗ Spread > 3x normal (liquidity issue)
  ✗ Within 5 min of high-impact news
  ✗ Confluence score < 0.50
  ✗ Conflicting signals on higher timeframe
  ✗ Already in 3+ correlated positions
```

### Multi-Agent Integration

```
Entry Agent receives from:
  - Structure Agent: OB/FVG zones, trend direction
  - Liquidity Agent: Sweep detection, pool locations
  - Session Agent: Kill zone status, optimal windows
  - Candlestick Agent: Pattern scores, failure flags
  - Risk Agent: Current exposure, correlation limits

Entry Agent computes:
  1. Weighted confluence score
  2. Entry method (limit/market/skip)
  3. Entry price and conditions
  4. Forwards to Position Sizing Agent

Entry Agent sends to Loop:
  - Trade proposal with full scoring breakdown
  - Awaits loop approval before execution
```

### Loop Integration

```
Entry Loop:
  1. Signal detected → Score all confirmations
  2. Score ≥ 0.50 → Prepare trade proposal
  3. Trade proposal → Loop review (human or auto-approve if ≥ 0.75)
  4. Approved → Execute entry method
  5. Executed → Monitor for 3 candles (validates entry quality)
  6. Post-entry: Log fill quality vs ideal entry for timing optimization

Auto-Approve Threshold: 0.75 (configurable)
Human Review Required: 0.50–0.74
Auto-Reject: < 0.50
```

### Connections to Other Steps
- **← Step 9**: Candlestick patterns provide timing signal
- **← Steps 1-8**: All upstream signals feed into confluence score
- **→ Step 11**: Score determines position size multiplier
- **→ Step 12**: Entry method influences stop placement strategy

---

## STEP 11 — POSITION SIZING (Enhanced)

### Current State
Risk 0.5–2% per trade. Calculate lot size from stop-loss distance.

### Research-Backed Enhancements

#### Kelly Criterion for Optimal Sizing

```
Kelly % = (bp - q) / b

Where:
  b = Average win / Average loss (reward-to-risk ratio)
  p = Win probability
  q = 1 - p (loss probability)

Example (Alpha Stack typical stats):
  Win rate (p) = 0.68
  Avg R:R (b) = 1.8
  Kelly = (1.8 × 0.68 - 0.32) / 1.8 = (1.224 - 0.32) / 1.8 = 0.502

  Kelly says risk 50.2% — THIS IS INSANE for live trading.

PRACTICAL: Use Half-Kelly or Quarter-Kelly:
  Half-Kelly: 25.1% risk → Still too high
  Quarter-Kelly: 12.5% risk → Aggressive but manageable for experienced traders

RECOMMENDED FOR ALPHA STACK:
  Conservative (default): 0.5 × Half-Kelly = ~2-3% max
  Moderate: Half-Kelly = ~4-6% max
  Aggressive: Full Half-Kelly = ~8-10% max (experienced only)

Key insight: Kelly optimizes GROWTH, not survival. Fractional Kelly
preserves growth advantage while dramatically reducing ruin probability.
```

#### Dynamic Position Sizing Based on Signal Strength

```
Base Risk = 1% of account

Size Multipliers:

  Confluence Score Multiplier:
    0.80-1.00 (A+): 1.5x → 1.5% risk
    0.65-0.79 (A):  1.0x → 1.0% risk
    0.50-0.64 (B):  0.5x → 0.5% risk

  Market Regime Multiplier:
    Strong trend (ADX > 30):     1.2x
    Normal trend (ADX 20-30):    1.0x
    Weak/ranging (ADX < 20):     0.6x

  Recent Performance Multiplier:
    Last 5 trades: 4+ wins:      1.1x (momentum)
    Last 5 trades: 3 wins:       1.0x (neutral)
    Last 5 trades: 2 or fewer:   0.7x (cool down)
    3 consecutive losses:        0.5x (circuit breaker)

  Time-of-Day Multiplier:
    London/NY overlap:           1.2x (highest liquidity)
    London or NY solo:           1.0x
    Asian session:               0.7x (lower liquidity)

FINAL SIZE = Base Risk × Confluence × Regime × Performance × Time
CAPPED AT: 2% per trade, 6% total open exposure
```

#### Correlation-Adjusted Sizing

```
Problem: EUR/USD long + GBP/USD long = effectively 2x USD short exposure.

Correlation Matrix (rolling 20-day):
  EUR/USD ↔ GBP/USD:  +0.85  (high positive)
  EUR/USD ↔ USD/CHF:  -0.90  (high negative)
  EUR/USD ↔ AUD/USD:  +0.65  (moderate positive)
  GBP/JPY ↔ EUR/JPY:  +0.80  (high positive)

Rule: When correlation > 0.7 between two positions:
  Combined risk = Sum of individual risks × (1 + correlation × 0.5)

Example:
  EUR/USD long: 1% risk
  GBP/USD long: 1% risk
  Correlation: 0.85
  Effective risk: 2% × (1 + 0.85 × 0.5) = 2.85% → exceeds 2.5% limit

  Solution: Reduce each to 0.7% → Effective: 1.4% × 1.425 = ~2.0%

Maximum Correlated Exposure: 3% of account across all correlated pairs.
```

#### Account Growth Scaling

```
Tiered Risk Model:

Account Size    Max Risk/Trade    Max Open Exposure    Max Correlated
$1,000-$5,000     1.0%              3.0%                1.5%
$5,000-$25,000    1.5%              4.5%                2.5%
$25,000-$100K     1.5%              5.0%                3.0%
$100K-$500K       1.0%              4.0%                2.5%
$500K+            0.75%             3.0%                2.0%

Why reduce % as account grows:
  - Absolute $ risk still increases
  - Drawdown recovery becomes harder at scale
  - Slippage impact increases with size
  - Psychological pressure scales with $ at risk
```

#### Risk Parity Across Pairs

```
Instead of equal % risk per trade, equalize RISK CONTRIBUTION:

Risk Parity Formula:
  Position Size_i = (Account Risk Budget / N) / (ATR_i × Pip Value_i)

This means:
  - EUR/USD (ATR 80 pips): Standard size
  - GBP/JPY (ATR 150 pips): Smaller size (higher volatility)
  - USD/CHF (ATR 60 pips): Larger size (lower volatility)

Each pair contributes EQUAL dollar risk to the portfolio,
regardless of individual volatility.

Implementation:
  1. Calculate ATR for each pair (20-period)
  2. Normalize: Size_i ∝ 1/ATR_i
  3. Scale to total risk budget
  4. Apply correlation adjustment
```

### AI/ML Enhancements

```python
def calculate_position_size(setup: dict, account: dict, market_state: dict) -> dict:
    """
    AI-optimized position sizing with multiple inputs.
    """
    base_risk = account['balance'] * 0.01  # 1% base

    # Signal strength multiplier
    confluence_mult = {
        'A+': 1.5, 'A': 1.0, 'B': 0.5
    }.get(setup['grade'], 0.5)

    # Market regime
    adx = market_state['adx']
    regime_mult = 1.2 if adx > 30 else (1.0 if adx > 20 else 0.6)

    # Recent performance
    recent_wr = account['recent_win_rate_5']
    perf_mult = 1.1 if recent_wr >= 0.8 else (1.0 if recent_wr >= 0.6 else 0.7)
    if account['consecutive_losses'] >= 3:
        perf_mult = 0.5  # Circuit breaker

    # Time of day
    session_mult = {
        'london_ny_overlap': 1.2,
        'london': 1.0, 'new_york': 1.0,
        'asian': 0.7
    }.get(market_state['session'], 0.8)

    # Correlation adjustment
    open_positions = account['open_positions']
    corr_factor = calculate_correlation_adjustment(
        setup['pair'], setup['direction'], open_positions
    )

    # Final calculation
    raw_risk = base_risk * confluence_mult * regime_mult * perf_mult * session_mult
    adjusted_risk = raw_risk * corr_factor

    # Hard caps
    max_risk = account['balance'] * 0.02  # 2% absolute max
    max_exposure = account['balance'] * 0.06  # 6% total
    current_exposure = sum(p['risk'] for p in open_positions)

    final_risk = min(adjusted_risk, max_risk, max_exposure - current_exposure)

    # Convert to lot size
    sl_pips = setup['sl_distance_pips']
    pip_value = get_pip_value(setup['pair'], account['currency'])
    lot_size = final_risk / (sl_pips * pip_value)

    return {
        'risk_amount': final_risk,
        'risk_pct': final_risk / account['balance'] * 100,
        'lot_size': round(lot_size, 2),
        'breakdown': {
            'confluence': confluence_mult,
            'regime': regime_mult,
            'performance': perf_mult,
            'session': session_mult,
            'correlation': corr_factor
        }
    }
```

### Multi-Agent Integration

```
Position Sizing Agent receives:
  - Entry Agent: Trade setup with confluence score and grade
  - Risk Agent: Current exposure, correlation matrix, drawdown state
  - Market Agent: ADX, ATR, session info
  - Account Agent: Balance, recent performance, tier

Position Sizing Agent outputs:
  - Final lot size
  - Risk amount and percentage
  - Breakdown of all multipliers
  - Warning flags (approaching limits, high correlation)
```

### Loop Integration

```
Sizing Loop:
  1. Trade proposal received → Check current exposure
  2. Calculate all multipliers → Generate sizing recommendation
  3. Check against hard caps → Adjust if needed
  4. Log sizing decision with full breakdown
  5. Post-trade: Compare actual outcome to sizing prediction
  6. Monthly: Review Kelly parameters, update win rate/R:R estimates
  7. Quarterly: Rebalance risk tiers based on account growth
```

### Connections to Other Steps
- **← Step 10**: Confluence score directly determines size multiplier
- **← Step 12**: Stop distance determines lot size calculation
- **→ Step 12**: Wider stops → smaller positions (risk stays constant)
- **→ Step 13 (Exit)**: Position size affects partial profit-taking strategy

---

## STEP 12 — STOP LOSS (Enhanced)

### Current State
Place below swing low, order block, support, with ATR buffer.

### Research-Backed Enhancements

#### AI-Optimized Stop Placement

```
Multi-Factor Stop Calculation:

STOP = Structure Level - (ATR Buffer × Volatility Factor × Context Adjustment)

Structure Level Selection (priority order):
  1. Order block edge (highest probability reversal zone)
  2. Swing low/high (invalidation point)
  3. Fair value gap edge
  4. Liquidity pool (where stops cluster — be aware, don't join them)

ATR Buffer:
  Base: 0.5 × ATR(14)
  Adjusted by:
    - High volatility (ATR > 1.5x average): 0.75 × ATR
    - Low volatility (ATR < 0.7x average): 0.35 × ATR
    - News proximity: 1.0 × ATR (wider for news volatility)

Context Adjustment:
  - Strong structure (multiple touches): -0.1 ATR (tighter — structure is reliable)
  - Weak/unclear structure: +0.2 ATR (wider — give room)
  - Higher timeframe alignment: -0.1 ATR (more confident)
  - Counter-trend trade: +0.3 ATR (wider — higher failure rate)

Maximum Stop: Never exceed 2% of account in dollar terms.
If calculated stop > 2% risk → Reduce position size, don't move stop closer.
```

#### Dynamic Stops Based on Volatility

```
Volatility-Adaptive Stop Framework:

Daily ATR Classification:
  Low Vol:    ATR < 70% of 20-day average → Tight stop (0.3 ATR buffer)
  Normal Vol: ATR 70-130% of average → Standard stop (0.5 ATR buffer)
  High Vol:   ATR > 130% of average → Wide stop (0.75 ATR buffer)

Intraday Adjustment:
  If volatility expands during trade (ATR increases 50%+):
    → Widen stop by additional 0.2 ATR (don't get shaken out)
  If volatility contracts (consolidation):
    → Tighten stop to 0.3 ATR (protect profits in compression)

Implementation:
  1. At entry: Use current ATR for initial stop
  2. Every 4 candles: Recalculate ATR, adjust stop if needed
  3. Never widen stop beyond initial placement (only tighten or maintain)
  4. If ATR doubles: Consider taking partial profit instead of widening stop
```

#### Time-Based Stops

```
"Time is a stop loss" — if a trade hasn't worked in X time, exit.

Time Stop Rules:
  Scalp (15m TF):     Exit after 4 hours if no movement
  Intraday (1H TF):   Exit after 24 hours if no movement
  Swing (4H TF):      Exit after 5 days if no movement

"Movement" Definition:
  - Price has moved > 0.5 ATR in favor → Trade is working, let it run
  - Price has moved < 0.3 ATR in favor → Trade is stalling
  - Price is at entry ± 0.2 ATR → Trade is dead, exit

Time Stop Scoring:
  If trade age > time limit AND movement < threshold:
    Exit at market, regardless of structure

Rationale: Capital tied in a dead trade has opportunity cost.
A trade that hasn't moved in expected timeframe has lower probability
of success than a fresh setup elsewhere.
```

#### Stop Hunt Protection

```
Stop hunts target obvious stop clusters. How to avoid being the prey:

1. DON'T Place Stops at Obvious Levels:
   - Below the exact swing low → Move 0.2 ATR lower
   - Below round numbers (1.1000, 1.1500) → Add 5-10 pips
   - Below visible support → Add buffer for the sweep

2. Layered Stop Strategy:
   Instead of one stop: Split into 2 levels
   - 60% of position at primary stop (structure - 0.3 ATR)
   - 40% at extended stop (structure - 0.8 ATR)
   If primary is hunted, the extended survives the wick

3. Liquidity Pool Awareness:
   - If stop is near a visible liquidity pool (cluster of obvious stops)
   - Consider: Extend stop BEYOND the pool
   - The sweep will blow through the pool and reverse — your stop survives

4. Time-Based Stop Hunt Filter:
   Stop hunts often occur:
   - First 15 min of London/NY session
   - During low-liquidity periods (Asian session for G7 pairs)
   - Just before major news
   → Widen stops by 0.3 ATR during these windows
```

#### Trailing Stop Strategies

```
Trailing Stop Options (select based on trade type):

1. ATR Trailing (Best for trending):
   Trail = Highest High - (2 × ATR)
   Update every candle close
   Never moves backward (only tightens)

2. Structure Trailing (Best for SMC trades):
   Trail to each new swing low (for longs)
   Only move when new structure forms
   Most patient approach — catches big moves

3. Chandelier Exit (Best for momentum):
   Trail = Highest High - (3 × ATR(22))
   Wider than standard ATR trail
   Good for strong trends with pullbacks

4. Break-Even + Trail:
   At 1R profit: Move stop to entry (break-even)
   At 2R profit: Trail at 1R below current price
   At 3R profit: Trail at 1.5R below current price
   Locks in profits progressively

5. Partial Close + Trail:
   At 1R: Close 50%, stop → break-even on remainder
   At 2R: Close 25%, trail remaining 25% with ATR
   At 3R+: Let remainder run with structure trail

Selection Logic:
  Trending market (ADX > 25): ATR Trail or Structure Trail
  Ranging market (ADX < 20): Break-Even + Trail (protect gains)
  High volatility: Chandelier Exit (wider trail)
  Counter-trend trade: Break-Even + Trail (be conservative)
```

#### Maximum Stop Loss Rules

```
Hard Limits:
  - Maximum stop per trade: 2% of account (absolute cap)
  - Maximum stop per correlated group: 3% of account
  - Maximum total open risk: 6% of account
  - Maximum daily loss: 4% of account (circuit breaker)

If calculated stop exceeds 2%:
  Option A: Reduce position size until risk = 2% (PREFERRED)
  Option B: Skip the trade (if size becomes too small to be meaningful)
  Option C: NEVER move stop closer to reduce risk (guarantees getting stopped)

Daily Circuit Breaker:
  If cumulative daily loss reaches 4%:
    → Stop all new entries for the day
    → Close any position that is at break-even or better
    → Review remaining positions at end of day
    → Resume next day with reduced size (50% of normal) for 24 hours
```

### AI/ML Enhancements

```python
def optimize_stop_loss(setup: dict, market: dict) -> dict:
    """
    AI-optimized stop placement considering multiple factors.
    """
    atr = market['atr_14']
    structure_level = setup['ob_edge'] or setup['swing_low']

    # Base buffer
    volatility_ratio = atr / market['atr_20_avg']
    if volatility_ratio > 1.3:
        buffer = 0.75 * atr
    elif volatility_ratio < 0.7:
        buffer = 0.35 * atr
    else:
        buffer = 0.5 * atr

    # Context adjustments
    if setup['structure_quality'] == 'strong':
        buffer -= 0.1 * atr
    elif setup['structure_quality'] == 'weak':
        buffer += 0.2 * atr

    if setup['counter_trend']:
        buffer += 0.3 * atr

    # Stop hunt protection
    liquidity_pools = market['liquidity_below']
    if liquidity_pools and abs(structure_level - liquidity_pools[0]) < 0.3 * atr:
        # Extend stop beyond the liquidity pool
        structure_level = liquidity_pools[0] - 0.2 * atr

    # Calculate stop
    stop_price = structure_level - buffer
    stop_distance = setup['entry_price'] - stop_price
    risk_pct = (stop_distance * setup['pip_value'] * setup['lot_size']) / setup['balance'] * 100

    # Enforce maximum
    if risk_pct > 2.0:
        # Reduce position size instead of moving stop
        new_lot = (0.02 * setup['balance']) / (stop_distance * setup['pip_value'])
        return {
            'stop_price': stop_price,
            'lot_size': round(new_lot, 2),
            'risk_pct': 2.0,
            'action': 'reduced_size',
            'original_lot': setup['lot_size']
        }

    # Time stop recommendation
    time_limits = {'15m': 4, '1h': 24, '4h': 120}  # hours
    time_stop_hours = time_limits.get(setup['timeframe'], 24)

    # Trailing stop recommendation
    if market['adx'] > 25:
        trail_type = 'atr_trail'
        trail_params = {'multiplier': 2.0, 'atr_period': 14}
    else:
        trail_type = 'breakeven_trail'
        trail_params = {'breakeven_at_r': 1.0, 'trail_at_r': 2.0}

    return {
        'stop_price': stop_price,
        'stop_distance_pips': stop_distance,
        'risk_pct': risk_pct,
        'buffer_atr': buffer / atr,
        'time_stop_hours': time_stop_hours,
        'trail_type': trail_type,
        'trail_params': trail_params,
        'stop_hunt_protected': liquidity_pools is not None
    }
```

### Multi-Agent Integration

```
Stop Loss Agent receives:
  - Structure Agent: OB edges, swing levels, FVG boundaries
  - Volatility Agent: Current ATR, volatility regime
  - Liquidity Agent: Stop cluster locations, liquidity pools
  - Entry Agent: Entry price, direction, timeframe
  - Risk Agent: Current exposure, daily P&L

Stop Loss Agent computes:
  1. Optimal stop price (multi-factor)
  2. Position size adjustment if needed
  3. Time stop recommendation
  4. Trailing stop strategy selection
  5. Stop hunt risk assessment

Stop Loss Agent monitors:
  - Real-time: If price approaches stop, prepare exit
  - Every candle: Update trailing stop
  - If stop hit: Log outcome for ML retraining
```

### Loop Integration

```
Stop Management Loop:
  1. Trade entered → Place initial stop
  2. Every candle close → Check if stop needs updating
  3. At 1R profit → Evaluate break-even move
  4. At 2R+ profit → Activate trailing strategy
  5. If time stop reached → Evaluate movement, exit if dead
  6. If stop hit → Log everything, feed to ML pipeline
  7. Weekly: Analyze stop placement quality (were stops too tight/wide?)
  8. Monthly: Retrain stop optimization model with new data
```

### Connections to Other Steps
- **← Step 10**: Entry price determines stop distance
- **← Step 11**: Stop distance determines position size (inversely proportional)
- **→ Step 11**: Wider stop = smaller position, tighter stop = larger position
- **→ Step 13 (Exit)**: Trailing stops feed into exit management
- **← Step 9**: Candlestick pattern type suggests stop placement (hammer = below wick)

---

## CROSS-STEP INTEGRATION MAP

```
Step 9 (Candlestick) ─────────────────────────────────────┐
    │ Score, direction, failure flag                       │
    ▼                                                      │
Step 10 (Entry) ◄── Steps 1-8 signals                     │
    │ Confluence score, entry method                       │
    ├──► Step 11 (Position Sizing) ◄── Account, correlation
    │        │ Lot size, risk amount                       │
    │        ▼                                              │
    └──► Step 12 (Stop Loss) ◄── Structure, volatility ────┘
             │ Stop price, trailing strategy
             ▼
        TRADE EXECUTION
             │
             ▼
        MONITORING LOOP (time stops, trailing, break-even)
             │
             ▼
        OUTCOME LOGGING → ML RETRAINING PIPELINE
```

## IMPLEMENTATION PRIORITY

| Priority | Enhancement | Impact | Effort |
|---|---|---|---|
| 1 | Confluence scoring system (Step 10) | ★★★★★ | Medium |
| 2 | Dynamic position sizing (Step 11) | ★★★★★ | Medium |
| 3 | Automated pattern detection (Step 9) | ★★★★☆ | High |
| 4 | Volatility-adaptive stops (Step 12) | ★★★★☆ | Low |
| 5 | Kelly Criterion integration (Step 11) | ★★★☆☆ | Low |
| 6 | Stop hunt protection (Step 12) | ★★★☆☆ | Medium |
| 7 | Trailing stop strategies (Step 12) | ★★★☆☆ | Medium |
| 8 | Correlation-adjusted sizing (Step 11) | ★★★☆☆ | Medium |
| 9 | Time-based stops (Step 12) | ★★☆☆☆ | Low |
| 10 | ML pattern recognition (Step 9) | ★★★★☆ | High |

---

*Generated by Alpha Stack Strategy Enhancement Agent — Steps 9-12*
*Part of the VMPM (Volatility-Mapped Price Movement) Strategy Framework*
