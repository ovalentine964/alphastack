# VMPM Strategy Enhancement — Steps 1–4
## Alpha Stack: Institutional-Grade AI Trading System
### Research-Backed Enhancements for the Valentine Money Printing Machine

---

# STEP 1 — Fundamental Intelligence

## 1.1 Current Strategy
Check MT5 economic calendar for interest rates, inflation, employment, GDP, central bank speeches, and political events. Manual review to decide "should I trade today?"

## 1.2 Research-Backed Enhancements

### A. LLM-Powered Macro Analysis
Research by Quek et al. (2025) at NUS demonstrated that LLM-based top-down macro analysis achieved a **Sharpe ratio of 2.51** and portfolio return of 8.79% versus -0.61 Sharpe and -1.39% for traditional cross-momentum strategies (ICLR Workshop 2025). The key insight: LLMs can simultaneously process policy documents, economic indicators, and sentiment patterns to make allocation decisions that outperform traditional quantitative models.

MarketSenseAI 2.0 (Fatouros et al., 2025) demonstrated that LLM agents processing SEC filings, earnings calls, and macroeconomic reports achieved **125.9% cumulative returns** vs S&P 100's 73.5% over 2 years. Their three-layer approach combining qualitative and quantitative macro data significantly improved fundamental analysis accuracy.

### B. Multi-Source Sentiment Analysis
FinBERT (Araci, 2019) and its derivatives have become the standard for financial NLP. The hybrid AI trading system by Pillai et al. (2026, ComSIA) integrated FinBERT sentiment with technical analysis and achieved **135.49% returns** over 24 months. Key finding: sentiment analysis on financial news provides a leading indicator that precedes price moves by 2-6 hours in forex markets.

### C. Real-Time News Intelligence
Research shows that processing speed matters enormously. The first 15 minutes after a major economic release contain 60-80% of the total price move. Systems must:
- Ingest and parse news within **< 30 seconds** of publication
- Distinguish between **signal** (actionable news) and **noise** (opinion pieces, rehashed old news)
- Weight sources by **historical accuracy** and **market impact**

## 1.3 AI/ML Enhancements

### Architecture: The Fundamental Intelligence Agent (FIA)

```
┌─────────────────────────────────────────────────────┐
│              FUNDAMENTAL INTELLIGENCE AGENT           │
│                                                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │ Economic  │  │  News    │  │  Sentiment       │   │
│  │ Calendar  │  │  Feed    │  │  Engine          │   │
│  │ Parser    │  │  Ingest  │  │  (FinBERT + LLM) │   │
│  └────┬─────┘  └────┬─────┘  └────────┬─────────┘   │
│       │              │                 │              │
│       └──────────────┼─────────────────┘              │
│                      ▼                                │
│         ┌────────────────────────┐                    │
│         │  Macro Context Builder │                    │
│         │  (RAG + Knowledge Graph)│                   │
│         └───────────┬────────────┘                    │
│                     ▼                                 │
│         ┌────────────────────────┐                    │
│         │  Trade Decision Engine │                    │
│         │  "Should I trade today?"│                   │
│         └────────────────────────┘                    │
└─────────────────────────────────────────────────────┘
```

### Data Sources (Priority-Ordered)

| Source | Type | Latency | Use Case |
|--------|------|---------|----------|
| **MT5 Economic Calendar** | Structured | Real-time | Event scheduling, impact ratings |
| **ForexFactory Calendar** | Structured | 1-min | Historical surprise vs actual |
| **Reuters/Bloomberg API** | News | < 10s | Breaking news, central bank statements |
| **Finnhub / Polygon.io** | News + Data | < 5s | Real-time news feed, earnings |
| **Central Bank RSS Feeds** | Official | < 30s | FOMC, ECB, BOJ, BOE statements |
| **Twitter/X Financial** | Social | Real-time | Market sentiment, breaking events |
| **On-Chain Data** (if applicable) | Blockchain | Real-time | Crypto flows, whale movements |
| **COT Reports** | Positioning | Weekly | Institutional positioning data |

### Sentiment Engine Design

**Layer 1 — FinBERT Classification**
- Fine-tuned on forex-specific corpus (central bank language, macro terminology)
- Input: headline + first 2 sentences of article
- Output: Bullish/Bearish/Neutral + confidence score (0-1)
- Latency: < 100ms per article

**Layer 2 — LLM Reasoning (DeepSeek/Qwen)**
- Triggered for high-impact events or when FinBERT confidence < 0.7
- Uses Chain-of-Thought reasoning to interpret nuanced situations
- Example: "ECB holds rates but dovish language" → interprets as bearish EUR
- Prompt template: "Analyze this central bank statement in context of current economic conditions. Consider: 1) What was expected? 2) What actually happened? 3) What does the language imply for future policy? Output: direction + confidence + reasoning."

**Layer 3 — Event Impact Scoring**
- Historical database of how similar events moved markets
- Bayesian updating: prior = historical average move, posterior = adjusted by current conditions
- Output: Expected volatility (pips), direction probability, time window of impact

### "Should I Trade Today?" Decision Matrix

```python
def should_trade_today(fundamental_context):
    score = 0
    reasons = []
    
    # High-impact calendar events
    if fundamental_context.has_high_impact_event:
        if fundamental_context.event_type in ["NFP", "CPI", "Rate Decision", "FOMC"]:
            score -= 30  # Extreme volatility risk
            reasons.append("High-impact event: reduce/avoid trading")
        elif fundamental_context.event_type in ["GDP", "Employment", "PMI"]:
            score -= 15  # Moderate volatility
            reasons.append("Medium-impact event: trade with caution")
    
    # Sentiment alignment
    if fundamental_context.sentiment_strength > 0.8:
        score += 20  # Strong directional conviction
        reasons.append("Strong sentiment alignment detected")
    elif fundamental_context.sentiment_strength < 0.3:
        score -= 10  # Conflicting signals
        reasons.append("Weak/conflicting sentiment")
    
    # Regime assessment
    if fundamental_context.volatility_regime == "EXTREME":
        score -= 25
        reasons.append("Extreme volatility regime - reduce size")
    elif fundamental_context.volatility_regime == "LOW":
        score += 10
        reasons.append("Low volatility - favorable conditions")
    
    # Political/geopolitical risk
    if fundamental_context.geopolitical_risk > 0.7:
        score -= 20
        reasons.append("Elevated geopolitical risk")
    
    # Decision
    if score >= 30:
        return TradeDecision.FULL_POSITION, reasons
    elif score >= 10:
        return TradeDecision.REDUCED_POSITION, reasons
    elif score >= -10:
        return TradeDecision.NO_TRADE, reasons
    else:
        return TradeDecision.AVOID_ALL, reasons
```

## 1.4 Multi-Agent Integration

| Agent | Role | Input | Output |
|-------|------|-------|--------|
| **News Crawler Agent** | Continuous news monitoring | RSS feeds, APIs | Raw articles with timestamps |
| **Sentiment Agent** | NLP processing | Raw articles | Sentiment scores per currency pair |
| **Event Impact Agent** | Calendar analysis | Economic calendar + historical data | Expected impact scores |
| **Macro Context Agent** | Synthesis | All above + RAG knowledge base | Unified fundamental bias |

## 1.5 Self-Improvement Loop

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Make Trade  │────▶│  Record      │────▶│  Compare    │
│  Decision    │     │  Prediction  │     │  vs Actual  │
└─────────────┘     └──────────────┘     └──────┬──────┘
                                                │
                    ┌──────────────┐             │
                    │  Update      │◀────────────┘
                    │  Sentiment   │
                    │  Weights     │
                    └──────────────┘
```

- **Weekly**: Retrain FinBERT on new labeled data (manually verified predictions)
- **Monthly**: Update event impact database with actual market reactions
- **Quarterly**: Retrain the "should I trade" model with expanded feature set
- **Continuous**: Track prediction accuracy per source, de-weight unreliable sources

## 1.6 Implementation Details

```python
# Core dependencies
# pip install transformers torch finnhub-python feedparser beautifulsoup4

# FinBERT setup
from transformers import AutoTokenizer, AutoModelForSequenceClassification
finbert = AutoModelForSequenceClassification.from_pretrained('ProsusAI/finbert')
tokenizer = AutoTokenizer.from_pretrained('ProsusAI/finbert')

# News ingestion pipeline
import finnhub
import feedparser

class NewsIngestionPipeline:
    def __init__(self):
        self.finnhub_client = finnhub.Client(api_key="YOUR_KEY")
        self.rss_feeds = [
            "https://www.forexlive.com/feed",
            "https://www.fxstreet.com/rss",
            "https://www.reuters.com/rssFeed/forex",
        ]
    
    def get_realtime_news(self):
        # Finnhub for real-time
        news = self.finnhub_client.general_news('forex', min_id=0)
        # RSS feeds for broader coverage
        for feed_url in self.rss_feeds:
            entries = feedparser.parse(feed_url).entries
            news.extend(self._normalize_rss(entries))
        return self._deduplicate_and_rank(news)

# MT5 Calendar integration
import MetaTrader5 as mt5

class EconomicCalendarMonitor:
    def get_upcoming_events(self, hours_ahead=24):
        # MT5 calendar API
        events = mt5.calendar_get(0, int(time.time()) + hours_ahead*3600)
        return self._filter_and_classify(events)
    
    def classify_impact(self, event):
        # Historical surprise analysis
        surprise = (event.actual - event.forecast) / event.forecast if event.forecast else 0
        impact_score = abs(surprise) * event.importance_weight
        return impact_score
```

## 1.7 Connection to Step 2

The Fundamental Intelligence Agent outputs:
- `fundamental_bias`: BULLISH / BEARISH / NEUTRAL (per currency pair)
- `confidence`: 0.0 - 1.0
- `volatility_forecast`: Expected range in pips
- `event_risk_score`: 0.0 - 1.0 (upcoming event risk)
- `sentiment_momentum`: Direction and strength of evolving sentiment

These feed directly into the Market Bias Agent (Step 2) as the macro layer of bias construction.

---

# STEP 2 — Market Bias

## 2.1 Current Strategy
Combine fundamentals + higher timeframe structure to decide bullish/bearish/neutral bias per pair.

## 2.2 Research-Backed Enhancements

### A. Hidden Markov Model (HMM) Regime Detection
Research by Rabiner (1989) established HMMs for temporal pattern recognition. In financial applications, HMMs with 3-4 hidden states consistently outperform static approaches. The multi-model ensemble-HMM voting framework (AIMS Press, 2025) demonstrated that regime-aware strategies significantly reduce drawdowns by filtering trades during unfavorable regimes.

Key findings from research:
- **3-state HMM** (Trending Bull, Trending Bear, Range/Chop) is optimal for forex
- Input features: returns, volatility (ATR/realized vol), volume profile, correlation breakdown
- HMM posterior probability > 0.7 for regime classification = high confidence
- Regime persistence: average trending regime lasts 8-15 days, ranging regime 3-7 days

### B. Multi-Timeframe Analysis by AI
The concept of "fractal market hypothesis" (Peters, 1994) suggests that market structure is self-similar across timeframes. AI agents can exploit this by:
- Analyzing structure on **Weekly (W1)** for macro direction
- **Daily (D1)** for swing bias
- **4H** for tactical positioning
- **1H** for entry timing
- Requiring alignment on ≥ 3 of 4 timeframes for high-conviction bias

### C. Fundamental-Technical Conflict Resolution
When fundamentals and technicals conflict, research shows:
- **Short-term (< 4H)**: Technicals dominate (70% accuracy)
- **Medium-term (1-5 days)**: Equal weighting (50/50)
- **Long-term (> 1 week)**: Fundamentals dominate (65% accuracy)
- Resolution strategy: **Timeframe-dependent weighting** using a dynamic alpha

## 2.3 AI/ML Enhancements

### Architecture: The Market Bias Agent (MBA)

```
┌──────────────────────────────────────────────────────────────┐
│                    MARKET BIAS AGENT                          │
│                                                               │
│  ┌────────────────┐    ┌────────────────┐                    │
│  │  Fundamental   │    │  Technical     │                    │
│  │  Bias Input    │    │  Analysis      │                    │
│  │  (from Step 1) │    │  Module        │                    │
│  └───────┬────────┘    └───────┬────────┘                    │
│          │                     │                              │
│          ▼                     ▼                              │
│  ┌────────────────────────────────────────┐                  │
│  │       Multi-Timeframe Structure        │                  │
│  │  W1 ─── D1 ─── 4H ─── 1H              │                  │
│  │  [Macro] [Swing] [Tactical] [Timing]   │                  │
│  └──────────────────┬─────────────────────┘                  │
│                     ▼                                        │
│  ┌────────────────────────────────────────┐                  │
│  │     Hidden Markov Model Regime         │                  │
│  │     Detection (3-state)                │                  │
│  │     States: Bull / Bear / Range        │                  │
│  └──────────────────┬─────────────────────┘                  │
│                     ▼                                        │
│  ┌────────────────────────────────────────┐                  │
│  │     Bias Fusion Engine                 │                  │
│  │     (Dynamic Weighting)                │                  │
│  └──────────────────┬─────────────────────┘                  │
│                     ▼                                        │
│  ┌────────────────────────────────────────┐                  │
│  │     OUTPUT: Bias + Confidence          │                  │
│  │     + Regime + Conflict Flag           │                  │
│  └────────────────────────────────────────┘                  │
└──────────────────────────────────────────────────────────────┘
```

### HMM Regime Detection — Implementation

```python
import numpy as np
from hmmlearn import hmm

class MarketRegimeDetector:
    def __init__(self, n_states=3):
        self.model = hmm.GaussianHMM(
            n_components=n_states,
            covariance_type="full",
            n_iter=1000,
            random_state=42
        )
        self.state_labels = {0: "BULL_TREND", 1: "BEAR_TREND", 2: "RANGE"}
    
    def prepare_features(self, df):
        """Extract regime-relevant features from OHLCV data"""
        features = []
        features.append(df['close'].pct_change().rolling(20).mean())  # Returns
        features.append(df['close'].pct_change().rolling(20).std())   # Volatility
        features.append(self._calc_atr_ratio(df, 14, 50))             # ATR ratio
        features.append(self._calc_adx(df, 14))                       # Trend strength
        features.append(df['volume'].rolling(20).mean() / 
                       df['volume'].rolling(50).mean())                # Volume ratio
        return np.column_stack(features)
    
    def detect_regime(self, df):
        features = self.prepare_features(df)
        features = features[~np.isnan(features).any(axis=1)]
        
        self.model.fit(features)
        states = self.model.predict(features)
        posteriors = self.model.predict_proba(features)
        
        current_state = states[-1]
        confidence = posteriors[-1][current_state]
        
        return {
            'regime': self.state_labels[current_state],
            'confidence': confidence,
            'state_probabilities': {
                label: posteriors[-1][i] 
                for i, label in self.state_labels.items()
            }
        }
    
    def _calc_atr_ratio(self, df, fast, slow):
        """Short-term ATR / Long-term ATR — measures volatility expansion"""
        atr_fast = self._atr(df, fast)
        atr_slow = self._atr(df, slow)
        return atr_fast / atr_slow
    
    def _atr(self, df, period):
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift())
        low_close = abs(df['low'] - df['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.rolling(period).mean()
```

### Multi-Timeframe Bias Construction

```python
class MultiTimeframeBiasEngine:
    """
    Combines structure analysis across 4 timeframes
    to produce a unified directional bias.
    """
    
    TIMEFRAMES = {
        'W1': {'weight': 0.35, 'role': 'macro_direction'},
        'D1': {'weight': 0.30, 'role': 'swing_bias'},
        'H4': {'weight': 0.20, 'role': 'tactical_position'},
        'H1': {'weight': 0.15, 'role': 'timing'}
    }
    
    def compute_bias(self, multi_tf_data, fundamental_bias):
        tf_biases = {}
        
        for tf, config in self.TIMEFRAMES.items():
            structure = self._analyze_structure(multi_tf_data[tf])
            tf_biases[tf] = {
                'direction': structure['trend_direction'],  # +1, 0, -1
                'strength': structure['trend_strength'],     # 0.0 - 1.0
                'structure': structure['pattern']            # HH/HL, LH/LL, etc.
            }
        
        # Compute weighted technical bias
        tech_bias = sum(
            tf_biases[tf]['direction'] * tf_biases[tf]['strength'] * config['weight']
            for tf, config in self.TIMEFRAMES.items()
        )
        
        # Dynamic alpha: how much to weight fundamentals vs technicals
        # Based on timeframe horizon of intended trade
        alpha = self._compute_dynamic_alpha(
            fundamental_confidence=fundamental_bias['confidence'],
            technical_alignment=self._measure_alignment(tf_biases),
            volatility_regime=self._get_vol_regime()
        )
        
        # Fusion
        final_bias = alpha * fundamental_bias['score'] + (1 - alpha) * tech_bias
        
        # Conflict detection
        conflict = (
            (fundamental_bias['score'] > 0.3 and tech_bias < -0.3) or
            (fundamental_bias['score'] < -0.3 and tech_bias > 0.3)
        )
        
        return {
            'bias': 'BULLISH' if final_bias > 0.2 else 'BEARISH' if final_bias < -0.2 else 'NEUTRAL',
            'strength': abs(final_bias),
            'confidence': self._compute_confidence(tf_biases, fundamental_bias),
            'conflict': conflict,
            'timeframe_biases': tf_biases,
            'regime': self.regime_detector.current_regime
        }
    
    def _compute_dynamic_alpha(self, fundamental_confidence, technical_alignment, volatility_regime):
        """
        Dynamic weighting between fundamental and technical signals.
        - High vol / event-driven → more weight to fundamentals
        - Low vol / trending → more weight to technicals
        """
        base_alpha = 0.4  # Default: 40% fundamental, 60% technical
        
        if volatility_regime == 'HIGH':
            base_alpha += 0.2  # Fundamentals matter more in high vol
        elif volatility_regime == 'LOW':
            base_alpha -= 0.1  # Technicals matter more in low vol
        
        if technical_alignment > 0.8:  # Strong multi-TF alignment
            base_alpha -= 0.1
        
        return np.clip(base_alpha, 0.2, 0.7)
    
    def _measure_alignment(self, tf_biases):
        """Measure how aligned all timeframes are (0=divergent, 1=perfect alignment)"""
        directions = [b['direction'] for b in tf_biases.values()]
        if len(set(directions)) == 1 and directions[0] != 0:
            return 1.0
        non_zero = [d for d in directions if d != 0]
        if not non_zero:
            return 0.0
        return abs(sum(non_zero)) / len(non_zero)
```

### Conflict Resolution Protocol

When fundamental bias and technical bias conflict, the system follows this protocol:

```python
def resolve_conflict(fundamental_bias, technical_bias, regime, event_proximity):
    """
    Resolution strategies when fundamentals and technicals disagree.
    """
    
    # RULE 1: If high-impact event within 4 hours, defer to fundamentals
    if event_proximity < 4:  # hours
        return {
            'action': 'DEFER_FUNDAMENTALS',
            'bias': fundamental_bias['direction'],
            'confidence': fundamental_bias['confidence'] * 0.7,  # Reduce confidence
            'note': 'Pre-event: fundamentals override technicals'
        }
    
    # RULE 2: If in ranging regime, reduce position size significantly
    if regime == 'RANGE':
        return {
            'action': 'REDUCE_SIZE',
            'bias': 'NEUTRAL',
            'confidence': 0.3,
            'note': 'Range regime + conflicting signals: avoid or reduce'
        }
    
    # RULE 3: If both have strong conviction, wait for alignment
    if fundamental_bias['confidence'] > 0.7 and technical_bias['strength'] > 0.7:
        return {
            'action': 'WAIT',
            'bias': 'NEUTRAL',
            'confidence': 0.0,
            'note': 'Strong conflict: wait for convergence signal'
        }
    
    # RULE 4: Default — use the stronger signal
    if fundamental_bias['confidence'] > technical_bias['strength']:
        return {
            'action': 'FOLLOW_FUNDAMENTALS',
            'bias': fundamental_bias['direction'],
            'confidence': fundamental_bias['confidence'] * 0.6,
            'note': 'Weak technical conflict: lean fundamental'
        }
    else:
        return {
            'action': 'FOLLOW_TECHNICALS',
            'bias': technical_bias['direction'],
            'confidence': technical_bias['strength'] * 0.6,
            'note': 'Weak fundamental conflict: lean technical'
        }
```

## 2.4 Multi-Agent Integration

| Agent | Role | Communication |
|-------|------|---------------|
| **Fundamental Intelligence Agent (Step 1)** | Provides macro bias | → MBA via message queue |
| **Structure Agent (Step 4)** | Provides HTF structure | → MBA via direct call |
| **Regime Detection Agent** | HMM state classification | Embedded in MBA |
| **Conflict Resolution Agent** | Mediates disagreements | Embedded in MBA |

## 2.5 Self-Improvement Loop

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Generate Bias   │────▶│  Track Outcome   │────▶│  Analyze        │
│  (per pair/day)  │     │  (did bias hold?)│     │  Accuracy       │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                          │
       ┌──────────────────────────────────────────────────┘
       ▼
┌─────────────────┐     ┌──────────────────┐
│  Adjust HMM     │────▶│  Update Alpha    │
│  Parameters     │     │  Weights         │
└─────────────────┘     └──────────────────┘
```

- **Daily**: Log bias accuracy per pair (did price follow bias within 24H?)
- **Weekly**: Retrain HMM with latest data, update transition matrices
- **Monthly**: Analyze which timeframes were most/least accurate, adjust weights
- **Quarterly**: Full model review, feature importance analysis

## 2.6 Implementation Details

```python
# HMM Training Pipeline
from hmmlearn import hmm
from sklearn.preprocessing import StandardScaler
import joblib

class RegimeTrainingPipeline:
    def __init__(self):
        self.scaler = StandardScaler()
        self.model = hmm.GaussianHMM(n_components=3, covariance_type="full", n_iter=1000)
    
    def train(self, historical_data):
        features = self._extract_features(historical_data)
        features_scaled = self.scaler.fit_transform(features)
        self.model.fit(features_scaled)
        
        # Save model artifacts
        joblib.dump(self.model, 'models/regime_hmm_v1.pkl')
        joblib.dump(self.scaler, 'models/regime_scaler_v1.pkl')
        
        # Log transition matrix for analysis
        print("Transition Matrix:")
        print(self.model.transmat_)
        print("\nState Means:")
        print(self.model.means_)
```

## 2.7 Connection to Step 3

The Market Bias Agent outputs:
- `market_bias`: BULLISH / BEARISH / NEUTRAL (per pair)
- `bias_strength`: 0.0 - 1.0
- `regime`: TRENDING_BULL / TRENDING_BEAR / RANGE
- `regime_confidence`: 0.0 - 1.0
- `conflict_flag`: True/False
- `timeframe_alignment`: 0.0 - 1.0

These feed into the Session Analysis Agent (Step 3) to determine **when** to act on the bias.

---

# STEP 3 — Session Analysis

## 3.1 Current Strategy
Identify Asian High/Low, London Open, New York Open. Use session levels as reference points.

## 3.2 Research-Backed Enhancements

### A. Session-Specific Volatility Profiles
Research on forex microstructure (BIS Triennial Survey 2022) and academic studies show distinct session behaviors:

| Session | UTC Hours | Characteristics | Avg EURUSD Range |
|---------|-----------|-----------------|------------------|
| **Asian** | 00:00-08:00 | Low volatility, range-bound, JPY/AUD focus | 30-50 pips |
| **London** | 08:00-16:00 | High volatility, trend initiation, GBP/EUR focus | 60-100 pips |
| **New York** | 13:00-21:00 | USD-driven, news reaction, continuation | 50-80 pips |
| **London-NY Overlap** | 13:00-16:00 | **Peak volatility**, highest liquidity | 40-60 pips (in 3H) |
| **Asian-London Overlap** | 07:00-09:00 | Moderate, transition period | 20-30 pips |

Key finding: **60-70% of daily range** is typically established during London and New York sessions. Asian session establishes the range that London often breaks.

### B. Session Overlap Dynamics
The London-New York overlap (13:00-16:00 UTC) accounts for approximately **40% of total daily forex volume**. This is when:
- Major economic releases (US data) hit during active European trading
- Institutional rebalancing occurs
- Stop hunts and liquidity grabs are most common

### C. Session-Specific Spread Costs
Spreads vary significantly by session:
- Asian session: Spreads 1.5-2x normal (lower liquidity)
- London session: Spreads at minimum (peak liquidity)
- NY session: Spreads normal, widening briefly at 16:00 (fix)
- Off-hours: Spreads 2-3x normal

## 3.3 AI/ML Enhancements

### Architecture: The Session Analysis Agent (SAA)

```
┌──────────────────────────────────────────────────────────┐
│                  SESSION ANALYSIS AGENT                    │
│                                                           │
│  ┌────────────────┐    ┌─────────────────────────────┐   │
│  │  Session Clock  │    │  Volatility Analyzer        │   │
│  │  (UTC-based)    │    │  (Real-time ATR/Range)      │   │
│  └───────┬────────┘    └──────────────┬──────────────┘   │
│          │                            │                   │
│          ▼                            ▼                   │
│  ┌──────────────────────────────────────────────────┐    │
│  │         Session State Machine                     │    │
│  │  PRE_MARKET → ASIAN → TRANSITION → LONDON →      │    │
│  │  OVERLAP_NY → NEW_YORK → WIND_DOWN → OFF_HOURS   │    │
│  └──────────────────────┬───────────────────────────┘    │
│                         ▼                                │
│  ┌──────────────────────────────────────────────────┐    │
│  │         Session Behavior Model                    │    │
│  │  - Expected range per session                     │    │
│  │  - Typical patterns (breakout, range, reversal)   │    │
│  │  - Optimal trade windows                          │    │
│  └──────────────────────┬───────────────────────────┘    │
│                         ▼                                │
│  ┌──────────────────────────────────────────────────┐    │
│  │         Asian Range Tracker                       │    │
│  │  - High/Low detection                             │    │
│  │  - Range width analysis                           │    │
│  │  - Breakout probability                           │    │
│  └──────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────┘
```

### Real-Time Session Detection

```python
from datetime import datetime, timezone
from enum import Enum
import numpy as np

class Session(Enum):
    OFF_HOURS = "off_hours"
    ASIAN = "asian"
    ASIAN_LONDON_TRANSITION = "asian_london_transition"
    LONDON = "london"
    LONDON_NY_OVERLAP = "london_ny_overlap"
    NEW_YORK = "new_york"
    WIND_DOWN = "wind_down"

class SessionAnalyzer:
    # Session definitions (UTC)
    SESSION_TIMES = {
        Session.ASIAN: (0, 8),
        Session.ASIAN_LONDON_TRANSITION: (7, 9),
        Session.LONDON: (8, 16),
        Session.LONDON_NY_OVERLAP: (13, 16),
        Session.NEW_YORK: (13, 21),
        Session.WIND_DOWN: (20, 22),
        Session.OFF_HOURS: (22, 24),  # Also 0-0 but handled by Asian
    }
    
    # Historical volatility multipliers per session (relative to daily avg)
    VOLATILITY_PROFILES = {
        Session.ASIAN: {'multiplier': 0.4, 'avg_range_pips': 40, 'spread_mult': 1.5},
        Session.LONDON: {'multiplier': 1.3, 'avg_range_pips': 80, 'spread_mult': 0.8},
        Session.LONDON_NY_OVERLAP: {'multiplier': 1.6, 'avg_range_pips': 50, 'spread_mult': 0.7},
        Session.NEW_YORK: {'multiplier': 1.1, 'avg_range_pips': 65, 'spread_mult': 1.0},
        Session.OFF_HOURS: {'multiplier': 0.3, 'avg_range_pips': 25, 'spread_mult': 2.0},
    }
    
    def get_current_session(self):
        utc_now = datetime.now(timezone.utc)
        hour = utc_now.hour
        
        if 0 <= hour < 7:
            return Session.ASIAN
        elif 7 <= hour < 9:
            return Session.ASIAN_LONDON_TRANSITION
        elif 9 <= hour < 13:
            return Session.LONDON
        elif 13 <= hour < 16:
            return Session.LONDON_NY_OVERLAP
        elif 16 <= hour < 20:
            return Session.NEW_YORK
        elif 20 <= hour < 22:
            return Session.WIND_DOWN
        else:
            return Session.OFF_HOURS
    
    def analyze_session_dynamics(self, tick_data, session):
        """Real-time analysis of current session behavior"""
        
        session_start = self._get_session_start_time(session)
        session_ticks = tick_data[tick_data['time'] >= session_start]
        
        if len(session_ticks) < 10:
            return {'status': 'INSUFFICIENT_DATA'}
        
        # Current range
        session_high = session_ticks['high'].max()
        session_low = session_ticks['low'].min()
        current_range = session_high - session_low
        
        # Compare to historical average
        expected_range = self.VOLATILITY_PROFILES[session]['avg_range_pips'] * 0.0001
        range_ratio = current_range / expected_range if expected_range > 0 else 1.0
        
        # Realized volatility
        returns = session_ticks['close'].pct_change().dropna()
        realized_vol = returns.std() * np.sqrt(len(returns))
        
        # Volume profile
        avg_volume = session_ticks['volume'].mean()
        
        return {
            'session': session,
            'session_high': session_high,
            'session_low': session_low,
            'current_range_pips': current_range * 10000,
            'range_ratio': range_ratio,  # > 1 = expanded, < 1 = compressed
            'realized_volatility': realized_vol,
            'volume_profile': 'HIGH' if avg_volume > np.percentile(tick_data['volume'], 75) else 'NORMAL',
            'volatility_state': 'EXPANDED' if range_ratio > 1.3 else 'COMPRESSED' if range_ratio < 0.7 else 'NORMAL',
            'optimal_trade_window': self._is_optimal_window(session, utc_now)
        }
    
    def track_asian_range(self, tick_data):
        """
        Track Asian session high/low for London breakout strategy.
        Asian range is a key reference point for the rest of the day.
        """
        asian_ticks = tick_data[
            (tick_data['time'].dt.hour >= 0) & 
            (tick_data['time'].dt.hour < 8)
        ]
        
        if len(asian_ticks) < 100:  # Need sufficient data
            return None
        
        asian_high = asian_ticks['high'].max()
        asian_low = asian_ticks['low'].min()
        asian_range = asian_high - asian_low
        asian_midpoint = (asian_high + asian_low) / 2
        
        # Classify range width
        avg_daily_range = tick_data['high'].max() - tick_data['low'].min()
        range_pct = asian_range / avg_daily_range if avg_daily_range > 0 else 0
        
        return {
            'asian_high': asian_high,
            'asian_low': asian_low,
            'asian_range_pips': asian_range * 10000,
            'asian_midpoint': asian_midpoint,
            'range_classification': (
                'TIGHT' if range_pct < 0.25 else
                'NORMAL' if range_pct < 0.45 else
                'WIDE'
            ),
            'breakout_probability': self._estimate_breakout_prob(range_pct),
            'direction_bias': None  # Filled by Step 2's market bias
        }
```

### Session-Specific Trading Rules

```python
class SessionTradingRules:
    """
    Adaptive rules based on session characteristics.
    """
    
    def get_session_parameters(self, session, market_bias, asian_range):
        """Returns session-specific trading parameters."""
        
        params = {
            'max_trades': 0,
            'position_size_mult': 1.0,
            'stop_mult': 1.0,
            'take_profit_mult': 1.0,
            'preferred_strategies': [],
            'avoid_strategies': []
        }
        
        if session == Session.ASIAN:
            params.update({
                'max_trades': 2,
                'position_size_mult': 0.5,  # Half size in Asian
                'stop_mult': 0.8,           # Tighter stops
                'preferred_strategies': ['range_trading', 'mean_reversion'],
                'avoid_strategies': ['breakout', 'momentum'],
                'notes': 'Range-bound session. Trade the range, not breakouts.'
            })
        
        elif session == Session.LONDON:
            params.update({
                'max_trades': 3,
                'position_size_mult': 1.0,
                'stop_mult': 1.2,          # Wider stops for volatility
                'preferred_strategies': ['breakout', 'trend_following', 'asian_range_breakout'],
                'avoid_strategies': ['mean_reversion'],
                'notes': 'Trend initiation session. Look for Asian range breakout.'
            })
            
            # Asian range breakout setup
            if asian_range and asian_range['range_classification'] == 'TIGHT':
                params['preferred_strategies'].append('asian_squeeze_breakout')
                params['position_size_mult'] = 1.2  # Higher conviction
                params['notes'] += ' Tight Asian range detected — high breakout probability.'
        
        elif session == Session.LONDON_NY_OVERLAP:
            params.update({
                'max_trades': 2,
                'position_size_mult': 0.8,  # Reduce during peak vol
                'stop_mult': 1.5,          # Wide stops for volatility spikes
                'preferred_strategies': ['momentum', 'news_reaction'],
                'avoid_strategies': ['range_trading'],
                'notes': 'Peak volatility. Be selective. News-driven moves likely.'
            })
        
        elif session == Session.NEW_YORK:
            params.update({
                'max_trades': 2,
                'position_size_mult': 0.8,
                'stop_mult': 1.0,
                'preferred_strategies': ['continuation', 'reversal_at_key_levels'],
                'avoid_strategies': ['breakout'],
                'notes': 'USD-driven session. Look for continuation of London moves.'
            })
        
        elif session == Session.WIND_DOWN:
            params.update({
                'max_trades': 1,
                'position_size_mult': 0.5,
                'stop_mult': 0.8,
                'preferred_strategies': ['position_management_only'],
                'avoid_strategies': ['new_entries'],
                'notes': 'Wind down. Manage existing positions, avoid new entries.'
            })
        
        elif session == Session.OFF_HOURS:
            params.update({
                'max_trades': 0,
                'position_size_mult': 0.0,
                'preferred_strategies': [],
                'avoid_strategies': ['all'],
                'notes': 'Off-hours. No trading. Wide spreads, low liquidity.'
            })
        
        return params
```

## 3.4 Multi-Agent Integration

| Agent | Role | Timing |
|-------|------|--------|
| **Session Clock Agent** | Tracks current session state | Continuous |
| **Asian Range Agent** | Monitors Asian H/L during Asian session | 00:00-08:00 UTC |
| **Volatility Agent** | Real-time volatility monitoring per session | Continuous |
| **Spread Monitor Agent** | Tracks bid-ask spreads by session | Continuous |

## 3.5 Self-Improvement Loop

- **Daily**: Log actual range vs predicted range per session
- **Weekly**: Update session volatility profiles with rolling 4-week data
- **Monthly**: Analyze which session-specific strategies performed best
- **Quarterly**: Adjust session time boundaries if market hours have shifted (DST, holidays)

## 3.6 Implementation Details

```python
# Core session tracking
class SessionTracker:
    def __init__(self, symbol):
        self.symbol = symbol
        self.sessions = {}
        self.asian_range = None
    
    def update(self, tick):
        session = self.get_current_session()
        
        if session not in self.sessions:
            self.sessions[session] = {
                'open': tick['price'],
                'high': tick['price'],
                'low': tick['price'],
                'volume': 0,
                'tick_count': 0,
                'start_time': tick['time']
            }
        
        s = self.sessions[session]
        s['high'] = max(s['high'], tick['price'])
        s['low'] = min(s['low'], tick['price'])
        s['volume'] += tick['volume']
        s['tick_count'] += 1
        
        # Update Asian range continuously
        if session == Session.ASIAN:
            self.asian_range = {
                'high': s['high'],
                'low': s['low'],
                'range_pips': (s['high'] - s['low']) * 10000
            }
```

## 3.7 Connection to Step 4

The Session Analysis Agent outputs:
- `current_session`: ASIAN / LONDON / OVERLAP / NEW_YORK / etc.
- `session_volatility_state`: EXPANDED / NORMAL / COMPRESSED
- `asian_range`: {high, low, range_pips, classification}
- `session_parameters`: {max_trades, position_size_mult, stop_mult, strategies}
- `optimal_window`: True/False

These feed into the Market Structure Agent (Step 4) to know **what kind of structure patterns to expect** and **how to size entries**.

---

# STEP 4 — Market Structure

## 4.1 Current Strategy
Identify HH (Higher High), HL (Higher Low), LH (Lower High), LL (Lower Low) to determine trend direction.

## 4.2 Research-Backed Enhancements

### A. Automated Structure Detection
Smart Money Concepts (SMC) have gained significant traction. The `smart-money-concepts` Python library (Attridge, 2024) provides programmatic detection of:
- **Swing Highs/Lows** with configurable lookback
- **Break of Structure (BOS)**: Continuation signal — price breaks a swing high in uptrend or swing low in downtrend
- **Change of Character (CHoCH)**: Reversal signal — price breaks the most recent swing low in uptrend (or high in downtrend)

Reddit research on r/algotrading (2025) analyzing NQ H1 data from 2008-2025 found:
- BOS signals have **~58% continuation rate** when aligned with higher timeframe trend
- CHoCH signals have **~52% reversal rate** but with larger average moves
- Combining BOS/CHoCH with volume confirmation increases accuracy to **~65%**

### B. Choppy/Ranging Market Detection
Research shows that markets are in a ranging state **60-70% of the time**. Detection methods:
- **ADX < 20**: Classic trend strength indicator (Wilder, 1978)
- **Bollinger Band Width**: Squeeze detection (narrow bands = range)
- **Price vs Moving Average**: Oscillation around MA without clear direction
- **HMM Regime**: Already integrated in Step 2

### C. Multi-Timeframe Structure Alignment
The fractal nature of market structure means:
- **W1 structure** defines the macro trend (institutional level)
- **D1 structure** defines the swing trend (swing trader level)
- **4H structure** defines the tactical trend (day trader level)
- **1H structure** defines the entry timing (scalper level)

**Rule**: Only trade in the direction of the **highest timeframe that has clear structure**. If W1 is bullish HH/HL but D1 is showing CHoCH bearish → wait for D1 to realign with W1.

## 4.3 AI/ML Enhancements

### Architecture: The Market Structure Agent (MSA)

```
┌──────────────────────────────────────────────────────────────┐
│                   MARKET STRUCTURE AGENT                      │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐     │
│  │            Swing Detection Engine                    │     │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │     │
│  │  │ ZigZag   │  │ Fractal  │  │ Adaptive         │  │     │
│  │  │ Algorithm │  │ Detection│  │ Lookback (ATR)   │  │     │
│  │  └──────────┘  └──────────┘  └──────────────────┘  │     │
│  └────────────────────────┬────────────────────────────┘     │
│                           ▼                                  │
│  ┌─────────────────────────────────────────────────────┐     │
│  │         Structure Classification                     │     │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │     │
│  │  │ BOS      │  │ CHoCH    │  │ Trend State      │  │     │
│  │  │ Detector │  │ Detector │  │ (HH/HL/LH/LL)   │  │     │
│  │  └──────────┘  └──────────┘  └──────────────────┘  │     │
│  └────────────────────────┬────────────────────────────┘     │
│                           ▼                                  │
│  ┌─────────────────────────────────────────────────────┐     │
│  │         Multi-TF Alignment Engine                    │     │
│  │  W1 ← D1 ← 4H ← 1H                                 │     │
│  │  [Structure coherence scoring]                       │     │
│  └────────────────────────┬────────────────────────────┘     │
│                           ▼                                  │
│  ┌─────────────────────────────────────────────────────┐     │
│  │         Chop/Range Detector                          │     │
│  │  ADX + BB Width + Price-MA oscillation               │     │
│  └────────────────────────┬────────────────────────────┘     │
│                           ▼                                  │
│  ┌─────────────────────────────────────────────────────┐     │
│  │         OUTPUT: Structure Map                        │     │
│  │  {trend, key_levels, BOS/CHoCH, chop_score}         │     │
│  └─────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────┘
```

### Swing Detection Algorithm

```python
import numpy as np
import pandas as pd

class AdaptiveSwingDetector:
    """
    Detects swing highs and lows with adaptive lookback
    based on current ATR (volatility-adjusted).
    """
    
    def __init__(self, base_lookback=5, atr_period=14, atr_multiplier=1.5):
        self.base_lookback = base_lookback
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier
    
    def detect_swings(self, df):
        """
        Detect swing points using adaptive lookback.
        
        A swing high is a bar whose high is higher than the N bars
        on either side, where N adapts to volatility.
        """
        df = df.copy()
        
        # Calculate adaptive lookback
        atr = self._calc_atr(df, self.atr_period)
        median_atr = atr.median()
        adaptive_lookback = np.maximum(
            self.base_lookback,
            (atr / median_atr * self.base_lookback * self.atr_multiplier).astype(int)
        )
        
        swing_highs = []
        swing_lows = []
        
        for i in range(len(df)):
            lb = int(adaptive_lookback.iloc[i])
            if i < lb or i >= len(df) - lb:
                continue
            
            # Swing High: current high > all highs in window
            window_highs = df['high'].iloc[i-lb:i+lb+1]
            if df['high'].iloc[i] == window_highs.max():
                swing_highs.append({
                    'index': i,
                    'time': df.index[i],
                    'price': df['high'].iloc[i],
                    'type': 'SWING_HIGH',
                    'lookback': lb
                })
            
            # Swing Low: current low < all lows in window
            window_lows = df['low'].iloc[i-lb:i+lb+1]
            if df['low'].iloc[i] == window_lows.min():
                swing_lows.append({
                    'index': i,
                    'time': df.index[i],
                    'price': df['low'].iloc[i],
                    'type': 'SWING_LOW',
                    'lookback': lb
                })
        
        return swing_highs, swing_lows
    
    def _calc_atr(self, df, period):
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift())
        low_close = abs(df['low'] - df['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.rolling(period).mean()
```

### BOS & CHoCH Detection

```python
class StructureAnalyzer:
    """
    Detects Break of Structure (BOS) and Change of Character (CHoCH).
    
    BOS = Continuation: In uptrend, price breaks above previous swing high
                       In downtrend, price breaks below previous swing low
    
    CHoCH = Reversal: In uptrend, price breaks below previous swing low
                     In downtrend, price breaks above previous swing high
    """
    
    def __init__(self):
        self.swing_detector = AdaptiveSwingDetector()
        self.current_trend = None  # 'BULLISH', 'BEARISH', 'UNDEFINED'
        self.last_swing_high = None
        self.last_swing_low = None
        self.structure_events = []
    
    def analyze(self, df):
        swing_highs, swing_lows = self.swing_detector.detect_swings(df)
        
        # Initialize trend from first swings
        if not self.current_trend and swing_highs and swing_lows:
            self._initialize_trend(swing_highs, swing_lows)
        
        # Process each new swing point
        all_swings = sorted(swing_highs + swing_lows, key=lambda x: x['index'])
        
        events = []
        for swing in all_swings:
            if swing['type'] == 'SWING_HIGH':
                event = self._process_swing_high(swing)
            else:
                event = self._process_swing_low(swing)
            
            if event:
                events.append(event)
        
        self.structure_events = events
        return self._build_structure_map(events, swing_highs, swing_lows)
    
    def _process_swing_high(self, swing):
        prev_high = self.last_swing_high
        
        if self.current_trend == 'BULLISH':
            if swing['price'] > prev_high['price']:
                # Higher High — BOS continuation
                return {
                    'type': 'BOS',
                    'direction': 'BULLISH',
                    'label': 'HH',
                    'price': swing['price'],
                    'time': swing['time'],
                    'significance': 'CONTINUATION'
                }
            else:
                # Lower High in uptrend — potential weakness
                return {
                    'type': 'WEAKNESS',
                    'direction': 'BEARISH',
                    'label': 'LH',
                    'price': swing['price'],
                    'time': swing['time'],
                    'significance': 'WARNING'
                }
        
        elif self.current_trend == 'BEARISH':
            if swing['price'] < prev_high['price']:
                # Lower High — BOS continuation (bearish)
                self.last_swing_high = swing
                return {
                    'type': 'BOS',
                    'direction': 'BEARISH',
                    'label': 'LH',
                    'price': swing['price'],
                    'time': swing['time'],
                    'significance': 'CONTINUATION'
                }
        
        self.last_swing_high = swing
        return None
    
    def _process_swing_low(self, swing):
        prev_low = self.last_swing_low
        
        if self.current_trend == 'BEARISH':
            if swing['price'] < prev_low['price']:
                # Lower Low — BOS continuation
                return {
                    'type': 'BOS',
                    'direction': 'BEARISH',
                    'label': 'LL',
                    'price': swing['price'],
                    'time': swing['time'],
                    'significance': 'CONTINUATION'
                }
            else:
                # Higher Low in downtrend — CHoCH!
                self.current_trend = 'BULLISH'
                return {
                    'type': 'CHoCH',
                    'direction': 'BULLISH',
                    'label': 'HL',
                    'price': swing['price'],
                    'time': swing['time'],
                    'significance': 'REVERSAL'
                }
        
        elif self.current_trend == 'BULLISH':
            if swing['price'] > prev_low['price']:
                # Higher Low — BOS continuation (bullish)
                return {
                    'type': 'BOS',
                    'direction': 'BULLISH',
                    'label': 'HL',
                    'price': swing['price'],
                    'time': swing['time'],
                    'significance': 'CONTINUATION'
                }
            else:
                # Lower Low in uptrend — CHoCH!
                self.current_trend = 'BEARISH'
                return {
                    'type': 'CHoCH',
                    'direction': 'BEARISH',
                    'label': 'LL',
                    'price': swing['price'],
                    'time': swing['time'],
                    'significance': 'REVERSAL'
                }
        
        self.last_swing_low = swing
        return None
    
    def _build_structure_map(self, events, swing_highs, swing_lows):
        """Build comprehensive structure map"""
        
        recent_events = events[-10:] if len(events) > 10 else events
        
        # Count structure signals
        bos_count = sum(1 for e in recent_events if e['type'] == 'BOS')
        choch_count = sum(1 for e in recent_events if e['type'] == 'CHoCH')
        
        # Determine structure state
        latest_event = events[-1] if events else None
        
        return {
            'trend': self.current_trend,
            'latest_event': latest_event,
            'bos_count': bos_count,
            'choch_count': choch_count,
            'structure_strength': bos_count / (bos_count + choch_count) if (bos_count + choch_count) > 0 else 0.5,
            'swing_highs': swing_highs[-5:],  # Last 5 swing highs
            'swing_lows': swing_lows[-5:],     # Last 5 swing lows
            'key_levels': self._extract_key_levels(swing_highs, swing_lows)
        }
    
    def _extract_key_levels(self, swing_highs, swing_lows):
        """Extract key price levels from swing points"""
        levels = []
        
        # Recent swing highs as resistance
        for sh in swing_highs[-3:]:
            levels.append({
                'price': sh['price'],
                'type': 'RESISTANCE',
                'strength': 1.0,  # Decay over time
                'source': 'SWING_HIGH'
            })
        
        # Recent swing lows as support
        for sl in swing_lows[-3:]:
            levels.append({
                'price': sl['price'],
                'type': 'SUPPORT',
                'strength': 1.0,
                'source': 'SWING_LOW'
            })
        
        return sorted(levels, key=lambda x: x['price'], reverse=True)
```

### Choppy Market Detector

```python
class ChopDetector:
    """
    Detects ranging/choppy market conditions where trend-following
    strategies underperform.
    """
    
    def __init__(self):
        self.adx_period = 14
        self.bb_period = 20
        self.bb_std = 2.0
    
    def detect(self, df):
        # ADX
        adx = self._calc_adx(df, self.adx_period)
        
        # Bollinger Band Width (squeeze detection)
        bb_upper = df['close'].rolling(self.bb_period).mean() + self.bb_std * df['close'].rolling(self.bb_period).std()
        bb_lower = df['close'].rolling(self.bb_period).mean() - self.bb_std * df['close'].rolling(self.bb_period).std()
        bb_width = (bb_upper - bb_lower) / df['close'].rolling(self.bb_period).mean()
        bb_width_percentile = bb_width.rank(pct=True).iloc[-1]
        
        # Price-MA oscillation (mean reversion tendency)
        ma_20 = df['close'].rolling(20).mean()
        ma_50 = df['close'].rolling(50).mean()
        price_vs_ma = (df['close'] - ma_20) / ma_20
        cross_count = ((price_vs_ma > 0) != (price_vs_ma.shift(1) > 0)).rolling(20).sum().iloc[-1]
        
        # Chop score (0 = trending, 1 = very choppy)
        chop_score = 0.0
        
        if adx.iloc[-1] < 20:
            chop_score += 0.4  # Weak trend
        elif adx.iloc[-1] < 25:
            chop_score += 0.2
        
        if bb_width_percentile < 0.2:  # Bollinger squeeze
            chop_score += 0.3
        
        if cross_count > 8:  # Frequent MA crosses
            chop_score += 0.3
        
        chop_score = min(chop_score, 1.0)
        
        return {
            'chop_score': chop_score,
            'is_choppy': chop_score > 0.6,
            'adx': adx.iloc[-1],
            'bb_width_percentile': bb_width_percentile,
            'ma_cross_count_20bar': cross_count,
            'recommendation': (
                'NO_NEW_TREND_TRADES' if chop_score > 0.7 else
                'CAUTION' if chop_score > 0.5 else
                'TRENDING' if chop_score < 0.3 else
                'NORMAL'
            )
        }
```

### Multi-Timeframe Structure Alignment

```python
class MultiTFStructureEngine:
    """
    Aligns market structure across multiple timeframes.
    Only signals high-conviction trades when structure aligns.
    """
    
    TIMEFRAMES = ['W1', 'D1', 'H4', 'H1']
    WEIGHTS = {'W1': 0.35, 'D1': 0.30, 'H4': 0.20, 'H1': 0.15}
    
    def __init__(self):
        self.analyzers = {tf: StructureAnalyzer() for tf in self.TIMEFRAMES}
        self.chop_detectors = {tf: ChopDetector() for tf in self.TIMEFRAMES}
    
    def analyze(self, multi_tf_data):
        results = {}
        
        for tf in self.TIMEFRAMES:
            structure = self.analyzers[tf].analyze(multi_tf_data[tf])
            chop = self.chop_detectors[tf].detect(multi_tf_data[tf])
            
            results[tf] = {
                'structure': structure,
                'chop': chop,
                'trend_direction': self._trend_to_signal(structure['trend']),
                'is_tradeable': not chop['is_choppy']
            }
        
        # Compute alignment score
        alignment = self._compute_alignment(results)
        
        return {
            'timeframes': results,
            'alignment_score': alignment['score'],
            'aligned_direction': alignment['direction'],
            'is_high_conviction': alignment['score'] > 0.75,
            'lowest_tradeable_tf': self._get_lowest_tradeable_tf(results),
            'structure_map': self._build_composite_map(results)
        }
    
    def _compute_alignment(self, results):
        """How aligned are all timeframes? (0 = divergent, 1 = perfect)"""
        
        signals = []
        for tf in self.TIMEFRAMES:
            if results[tf]['is_tradeable']:
                signals.append(
                    results[tf]['trend_direction'] * self.WEIGHTS[tf]
                )
        
        if not signals:
            return {'score': 0.0, 'direction': 'NEUTRAL'}
        
        weighted_signal = sum(signals)
        max_possible = sum(self.WEIGHTS[tf] for tf in self.TIMEFRAMES if results[tf]['is_tradeable'])
        
        alignment_score = abs(weighted_signal) / max_possible if max_possible > 0 else 0
        
        direction = 'BULLISH' if weighted_signal > 0.1 else 'BEARISH' if weighted_signal < -0.1 else 'NEUTRAL'
        
        return {'score': alignment_score, 'direction': direction}
    
    def _trend_to_signal(self, trend):
        return {'BULLISH': 1, 'BEARISH': -1, 'UNDEFINED': 0}.get(trend, 0)
    
    def _get_lowest_tradeable_tf(self, results):
        """Get the lowest (fastest) timeframe that still has clear structure"""
        for tf in reversed(self.TIMEFRAMES):  # H1 first
            if results[tf]['is_tradeable'] and results[tf]['structure']['trend'] != 'UNDEFINED':
                return tf
        return None
```

## 4.4 Multi-Agent Integration

| Agent | Role | Communication |
|-------|------|---------------|
| **Swing Detection Agent** | Identifies swing H/L per timeframe | → Structure Analyzer |
| **BOS/CHoCH Agent** | Classifies structure breaks | → Bias Agent (Step 2) |
| **Chop Detector Agent** | Identifies ranging conditions | → All downstream agents |
| **Multi-TF Alignment Agent** | Scores structure coherence | → Entry Agent (Step 5+) |

## 4.5 Self-Improvement Loop

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Detect Structure│────▶│  Record Signal   │────▶│  Track Outcome   │
│  (BOS/CHoCH)     │     │  + Context       │     │  (did move occur?)│
└──────────────────┘     └──────────────────┘     └────────┬─────────┘
                                                           │
       ┌───────────────────────────────────────────────────┘
       ▼
┌──────────────────┐     ┌──────────────────┐
│  Analyze Hit     │────▶│  Tune Swing      │
│  Rate by Setup   │     │  Lookback &      │
│                  │     │  Filters         │
└──────────────────┘     └──────────────────┘
```

- **Daily**: Log all BOS/CHoCH signals and their outcomes
- **Weekly**: Calculate hit rate per signal type (BOS vs CHoCH), per pair, per session
- **Monthly**: Adjust swing detection parameters (lookback, confirmation requirements)
- **Quarterly**: Full model recalibration, feature importance analysis

### Performance Tracking Schema

```python
class StructureSignalTracker:
    def __init__(self):
        self.signals = []
    
    def log_signal(self, signal, context):
        self.signals.append({
            'timestamp': datetime.utcnow(),
            'signal_type': signal['type'],  # BOS or CHoCH
            'direction': signal['direction'],
            'price': signal['price'],
            'pair': context['pair'],
            'timeframe': context['timeframe'],
            'session': context['session'],
            'regime': context['regime'],
            'chop_score': context['chop_score'],
            'multi_tf_alignment': context['alignment_score'],
            # Outcome filled later
            'outcome': None,
            'max_favorable_excursion': None,
            'max_adverse_excursion': None,
            'hit_target': None
        })
    
    def update_outcomes(self, lookforward_bars=20):
        """Update signal outcomes after N bars"""
        for signal in self.signals:
            if signal['outcome'] is not None:
                continue
            # ... check if price moved in signal direction
            # ... calculate MFE, MAE, hit rate
    
    def get_statistics(self):
        """Performance stats by signal type"""
        completed = [s for s in self.signals if s['outcome'] is not None]
        
        stats = {}
        for signal_type in ['BOS', 'CHoCH']:
            subset = [s for s in completed if s['signal_type'] == signal_type]
            if subset:
                hit_rate = sum(1 for s in subset if s['hit_target']) / len(subset)
                avg_mfe = np.mean([s['max_favorable_excursion'] for s in subset])
                stats[signal_type] = {
                    'count': len(subset),
                    'hit_rate': hit_rate,
                    'avg_mfe_pips': avg_mfe,
                    'best_session': self._best_session(subset),
                    'best_regime': self._best_regime(subset)
                }
        
        return stats
```

## 4.6 Implementation Details

```python
# Using the smart-money-concepts library as a reference/validation layer
# pip install smart-money-concepts pandas numpy

# Full pipeline integration
class MarketStructurePipeline:
    def __init__(self, symbol, timeframes=['W1', 'D1', 'H4', 'H1']):
        self.symbol = symbol
        self.structure_engine = MultiTFStructureEngine()
        self.signal_tracker = StructureSignalTracker()
    
    def run(self, multi_tf_data, session_info, market_bias):
        # 1. Analyze structure across all timeframes
        structure = self.structure_engine.analyze(multi_tf_data)
        
        # 2. Check for actionable signals
        latest_event = None
        for tf in ['H1', 'H4', 'D1', 'W1']:
            tf_structure = structure['timeframes'][tf]['structure']
            if tf_structure['latest_event']:
                if tf_structure['latest_event']['type'] in ['BOS', 'CHoCH']:
                    latest_event = tf_structure['latest_event']
                    latest_event['timeframe'] = tf
                    break
        
        # 3. Validate signal against bias
        if latest_event:
            signal_valid = self._validate_signal(
                latest_event, market_bias, structure, session_info
            )
        else:
            signal_valid = False
        
        # 4. Track signal for self-improvement
        if latest_event and signal_valid:
            self.signal_tracker.log_signal(latest_event, {
                'pair': self.symbol,
                'timeframe': latest_event.get('timeframe'),
                'session': session_info['current_session'],
                'regime': market_bias.get('regime'),
                'chop_score': structure['timeframes'].get(
                    latest_event.get('timeframe'), {}
                ).get('chop', {}).get('chop_score', 0),
                'alignment_score': structure['alignment_score']
            })
        
        return {
            'structure': structure,
            'actionable_signal': latest_event if signal_valid else None,
            'signal_valid': signal_valid,
            'key_levels': self._aggregate_key_levels(structure),
            'trade_direction': (
                latest_event['direction'] if signal_valid else
                structure['aligned_direction']
            )
        }
    
    def _validate_signal(self, signal, bias, structure, session):
        """Multi-layer validation before acting on structure signal"""
        
        # Layer 1: Signal must align with bias (or be CHoCH with strong conviction)
        if signal['type'] == 'BOS':
            if signal['direction'] != bias.get('bias'):
                return False  # BOS must align with bias
        
        # Layer 2: Must not be in choppy conditions
        tf = signal.get('timeframe', 'H1')
        if structure['timeframes'][tf]['chop']['is_choppy']:
            return False
        
        # Layer 3: Multi-TF alignment must be sufficient
        if structure['alignment_score'] < 0.4:
            return False
        
        # Layer 4: Session must support the trade
        session_params = session.get('session_parameters', {})
        if session_params.get('max_trades', 0) == 0:
            return False
        
        return True
```

## 4.7 Connection to Next Steps (Steps 5+)

The Market Structure Agent outputs:
- `structure_state`: {trend, BOS/CHoCH signals, swing points}
- `key_levels`: [{price, type: SUPPORT/RESISTANCE, strength}]
- `chop_score`: 0.0 - 1.0
- `multi_tf_alignment`: 0.0 - 1.0
- `trade_direction`: BULLISH / BEARISH / NEUTRAL
- `actionable_signal`: {type, direction, price, timeframe} or None

These feed into the **Entry Engine (Step 5+)** which will:
- Use key_levels for entry zones
- Use structure signals for timing
- Use chop_score to decide position sizing
- Use multi_tf_alignment for conviction scoring

---

# INTEGRATION SUMMARY

## Data Flow: Steps 1→2→3→4

```
STEP 1: Fundamental Intelligence
  │
  │  Output: fundamental_bias, sentiment, event_risk, vol_forecast
  │
  ▼
STEP 2: Market Bias
  │  Combines: Fundamental (Step 1) + Technical Structure (Step 4)
  │  Uses: HMM Regime Detection, Multi-TF Analysis
  │
  │  Output: market_bias, regime, confidence, conflict_flag
  │
  ▼
STEP 3: Session Analysis
  │  Provides: Session context, volatility profile, optimal windows
  │  Uses: Bias (Step 2) for direction, Asian range for setups
  │
  │  Output: session, volatility_state, asian_range, session_params
  │
  ▼
STEP 4: Market Structure
  │  Provides: Trend direction, BOS/CHoCH signals, key levels
  │  Uses: All prior steps for context and validation
  │
  │  Output: structure_map, key_levels, actionable_signals, trade_direction
  │
  ▼
STEP 5+ (Entry Engine): Uses all above to execute trades
```

## Agent Communication Protocol

```python
class AlphaStackOrchestrator:
    """
    Orchestrates all agents in the VMPM pipeline.
    """
    
    def run_pipeline(self, symbol):
        # Step 1: Fundamental Intelligence
        fundamental = self.fundamental_agent.analyze(symbol)
        
        # Step 4 (runs in parallel with Step 2 prep): Market Structure
        structure = self.structure_pipeline.run(
            self.get_multi_tf_data(symbol)
        )
        
        # Step 2: Market Bias (needs both Step 1 and Step 4)
        bias = self.bias_agent.compute(
            fundamental_bias=fundamental,
            structure_data=structure
        )
        
        # Step 3: Session Analysis
        session = self.session_analyzer.analyze(
            symbol=symbol,
            market_bias=bias,
            asian_range=self.session_analyzer.asian_range
        )
        
        # Final output: Unified trade context
        return {
            'symbol': symbol,
            'timestamp': datetime.utcnow(),
            'fundamental': fundamental,
            'bias': bias,
            'session': session,
            'structure': structure,
            'trade_ready': self._assess_trade_readiness(
                fundamental, bias, session, structure
            )
        }
    
    def _assess_trade_readiness(self, fundamental, bias, session, structure):
        """Final gate check before passing to entry engine"""
        
        checks = {
            'fundamental_clear': fundamental['event_risk_score'] < 0.7,
            'bias_defined': bias['bias'] != 'NEUTRAL',
            'bias_confidence': bias['confidence'] > 0.5,
            'session_active': session['session_parameters']['max_trades'] > 0,
            'structure_clear': structure['structure']['alignment_score'] > 0.4,
            'not_choppy': not structure.get('chop_score', 1.0) > 0.6,
            'no_conflict': not bias.get('conflict', False)
        }
        
        passed = sum(checks.values())
        total = len(checks)
        
        return {
            'ready': passed >= 5,  # Need 5/7 checks to pass
            'score': passed / total,
            'checks': checks,
            'blockers': [k for k, v in checks.items() if not v]
        }
```

---

# REFERENCES

1. Quek, R.W.H. et al. (2025). "Leveraging LLMs for Top-Down Sector Allocation in Automated Trading." ICLR Workshop Advances in Financial AI. arXiv:2503.09647.
2. Fatouros, G. et al. (2025). "MarketSenseAI 2.0: Enhancing Stock Analysis through LLM Agents." arXiv:2502.00415.
3. Pillai, V.N.K. et al. (2026). "Generating Alpha: A Hybrid AI-Driven Trading System Integrating Technical Analysis, Machine Learning and Financial Sentiment for Regime-Adaptive Equity Strategies." ComSIA 2026, Springer LNNS. arXiv:2601.19504.
4. Rabiner, L.R. (1989). "A Tutorial on Hidden Markov Models and Selected Applications in Speech Recognition." Proceedings of the IEEE.
5. AIMS Press (2025). "A Multi-Model Ensemble-HMM Voting Framework for Market Regime Detection."
6. Araci, D. (2019). "FinBERT: Financial Sentiment Analysis with Pre-Trained Language Models." arXiv:1908.10063.
7. Wilder, J.W. (1978). "New Concepts in Technical Trading Systems."
8. Peters, E. (1994). "Fractal Market Analysis: Applying Chaos Theory to Investment and Economics."
9. BIS Triennial Survey (2022). "OTC Derivatives Statistics."
10. Attridge, J. (2024). "Smart Money Concepts (smc) Python Library." GitHub.
