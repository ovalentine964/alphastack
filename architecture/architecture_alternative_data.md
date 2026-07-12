# Alpha Stack — Alternative Data Architecture

> **Version:** 1.0 · **Date:** 2026-07-11 · **Author:** Architecture Team
> **Source Research:** [`research/research_alternative_data.md`](../research/research_alternative_data.md) — Alternative data sources research
> **Status:** Architecture Complete

---

**Version:** 1.0
**Date:** 2026-07-13
**Status:** Architecture Design
**Dependencies:** Signal Aggregation, Market Regime Detection, Risk Management

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Design Philosophy](#2-design-philosophy)
3. [System Architecture](#3-system-architecture)
4. [Data Source Modules](#4-data-source-modules)
5. [Signal Normalization Layer](#5-signal-normalization-layer)
6. [Composite Alpha Score](#6-composite-alpha-score)
7. [Polling & Caching Strategy](#7-polling--caching-strategy)
8. [Integration Points](#8-integration-points)
9. [Implementation Roadmap](#9-implementation-roadmap)

---

## 1. Executive Summary

### Problem

Traditional technical analysis (price + volume + indicators) is the only edge available on most retail platforms. But institutional players use on-chain analytics, social sentiment, whale tracking, and derivatives data — sources that provide 1–24 hour lead times on price moves. Without alternative data, Alpha Stack competes with one arm tied behind its back.

### Solution

A **multi-source alternative data aggregator** that ingests free-tier data from on-chain analytics, social sentiment, exchange derivatives, and whale tracking, normalizes signals into a unified [-1.0, +1.0] alpha score, and feeds it into the strategy engine as a conviction multiplier.

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Data sources | Free tiers only | $0 budget at $7 capital; DefiLlama, Binance API, LunarCrush |
| Signal model | Weighted composite score | 2–3 deep signals beat 10 shallow ones |
| Update frequency | Source-dependent (1min–6hr) | Funding rates need 1min; Google Trends needs 6hr |
| Alpha quality | 15–25% win rate boost (combined) | Research-validated improvement over price-only |
| Cost | $0/month | All free APIs with aggressive caching |

---

## 2. Design Philosophy

### P1: Free Data, Maximum Edge
Every data source must have a free tier. At $7 capital, paid data is unjustifiable. The edge comes from combining uncorrelated free signals, not from paying for premium feeds.

### P2: 2–3 Deep Beats 10 Shallow
Master funding rates + exchange flows + social velocity. Don't spread effort across 10 mediocre signals. Depth > breadth.

### P3: Signal Independence
Only combine signals that are genuinely uncorrelated. Funding rates and open interest are correlated — count them as one. Social sentiment and on-chain flows are independent — combine them.

### P4: Lead Time Matters
Signals with 1–8 hour lead times (funding, social) are actionable for day trading. Signals with 1–4 week lead times (Google Trends, dev activity) are for portfolio allocation, not trade timing.

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                ALTERNATIVE DATA AGGREGATOR                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │  ON-CHAIN     │  │  SOCIAL      │  │  EXCHANGE    │               │
│  │  ANALYTICS    │  │  SENTIMENT   │  │  DERIVATIVES │               │
│  │              │  │              │  │              │               │
│  │ • DefiLlama  │  │ • Twitter/X  │  │ • Funding    │               │
│  │ • CryptoQuant│  │ • Reddit     │  │ • Open Int.  │               │
│  │ • Dune       │  │ • LunarCrush │  │ • Liq Maps   │               │
│  │ • Etherscan  │  │ • Telegram   │  │ • L/S Ratio  │               │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘               │
│         │                  │                  │                       │
│         ▼                  ▼                  ▼                       │
│  ┌─────────────────────────────────────────────────────────────┐     │
│  │              SIGNAL NORMALIZER                                │     │
│  │  • Z-score normalization                                     │     │
│  │  • Time alignment (resample to common clock)                 │     │
│  │  • Confidence weighting                                      │     │
│  └──────────────────────────┬──────────────────────────────────┘     │
│                             │                                         │
│                             ▼                                         │
│  ┌─────────────────────────────────────────────────────────────┐     │
│  │              COMPOSITE ALPHA SCORE                            │     │
│  │  Score = Σ(weight_i × signal_i)                              │     │
│  │  Range: -1.0 (strong sell) to +1.0 (strong buy)              │     │
│  └──────────────────────────┬──────────────────────────────────┘     │
│                             │                                         │
│                             ▼                                         │
│  ┌─────────────────────────────────────────────────────────────┐     │
│  │              STRATEGY ENGINE                                  │     │
│  │  Alpha score as conviction multiplier for trade signals       │     │
│  └─────────────────────────────────────────────────────────────┘     │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. Data Source Modules

### 4.1 On-Chain Analytics (Priority #1 — Weight: 0.35)

**Strongest short-term signal.** On-chain data shows what smart money does before price moves.

| Source | Endpoint | Frequency | Signal |
|--------|----------|-----------|--------|
| DefiLlama | `api.llama.fi/` | 5 min | Stablecoin flows, TVL changes |
| CryptoQuant | Free tier API | 15 min | Exchange reserves, SOPR, MVRV |
| Dune Analytics | GraphQL | 1 hour | Whale accumulation, DEX volumes |
| Etherscan | REST API (5/sec) | 5 min | Whale wallet monitoring |

```python
class OnChainModule:
    def get_exchange_flows(self, asset="BTC"):
        """Net flow to/from exchanges. Negative = bullish (coins leaving)."""
        data = self.cryptoquant.get_exchange_reserves(asset)
        net_flow = data.current - data.previous
        return self.normalize(-net_flow, lookback=30)  # Negative flow = positive score
    
    def get_stablecoin_flows(self):
        """Stablecoin supply changes = dry powder indicator."""
        data = self.defillama.get_stablecoin_flows()
        inflow = data.exchange_inflow_24h
        return self.normalize(inflow, lookback=30)
    
    def get_whale_accumulation(self, token):
        """Track top 100 wallets for target tokens."""
        data = self.dune.query_whale_activity(token)
        net_buying = data.whale_buys - data.whale_sells
        return self.normalize(net_buying, lookback=30)
```

### 4.2 Social Sentiment (Priority #2 — Weight: 0.25)

**2–12 hour lead time.** Crypto is sentiment-driven. Social signals predict retail FOMO/FUD before orders hit.

| Source | Method | Frequency | Signal |
|--------|--------|-----------|--------|
| Twitter/X | snscrape library | 15 min | Mention velocity, sentiment shift |
| Reddit | API (100 req/min) | 15 min | Post sentiment (VADER), comment volume |
| LunarCrush | Free API (30/min) | 15 min | Social dominance, Galaxy Score |
| Telegram | Bot monitoring | 5 min | Alpha group calls, panic signals |

```python
class SocialModule:
    def get_mention_velocity(self, token):
        """Spike detection: 1h mentions / (24h avg per hour)."""
        mentions_1h = self.twitter.count(token, hours=1)
        avg_hourly = self.twitter.count(token, hours=24) / 24
        ratio = mentions_1h / max(avg_hourly, 1)
        # ratio > 3.0 = significant spike
        return self.normalize(ratio - 1.0, lookback=30)  # Center around 0
    
    def get_sentiment_shift(self, token):
        """Sentiment change from negative to positive = reversal signal."""
        current = self.lunarcrush.sentiment(token)
        prev_24h = self.lunarcrush.sentiment(token, hours=24)
        shift = current - prev_24h
        return self.normalize(shift, lookback=30)
```

### 4.3 Exchange Derivatives (Priority #3 — Weight: 0.20)

**1–8 hour lead time.** Funding rates and OI are the most predictive short-term signals in crypto.

| Source | Endpoint | Frequency | Signal |
|--------|----------|-----------|--------|
| Binance Futures | `fapi/v1/fundingRate` | 1 min | Funding rate extremes |
| Binance Futures | `fapi/v1/openInterest` | 1 min | OI divergence from price |
| Coinglass | Web + limited API | 5 min | Liquidation heatmaps |
| Bybit/OKX | REST API | 5 min | Cross-exchange validation |

```python
class DerivativesModule:
    def get_funding_signal(self, pair="BTCUSDT"):
        """Extreme funding = overcrowded positioning."""
        rate = self.binance.get_funding_rate(pair)
        # > 0.1% = overcrowded longs (bearish)
        # < -0.05% = overcrowded shorts (bullish)
        if rate > 0.001:
            return -self.normalize(rate, lookback=30)  # Inverted: high funding = sell
        elif rate < -0.0005:
            return self.normalize(abs(rate), lookback=30)  # Low funding = buy
        return 0.0
    
    def get_oi_divergence(self, pair="BTCUSDT"):
        """OI rising + price flat = breakout brewing."""
        oi_change = self.binance.get_oi_change(pair, hours=4)
        price_change = self.binance.get_price_change(pair, hours=4)
        divergence = oi_change - price_change
        return self.normalize(divergence, lookback=30)
```

### 4.4 Whale Tracking (Weight: 0.12)

**4–24 hour lead time.** Whales move markets. Tracking their on-chain activity provides early signals.

| Source | Method | Signal |
|--------|--------|--------|
| Etherscan API | Wallet monitoring | Large transfers to/from exchanges |
| Whale Alert | Twitter bot + API | Real-time large transaction alerts |
| Arkham Intelligence | Free tier | Entity-labeled wallet tracking |

### 4.5 Supporting Signals (Weight: 0.08)

| Source | Frequency | Lead Time | Signal |
|--------|-----------|-----------|--------|
| Google Trends | 6 hours | 1–4 weeks | Retail attention (leading indicator) |
| GitHub API | Daily | Weeks | Developer activity (fundamental health) |
| Token Unlocks | Daily | Calendar | Supply catalysts (sell pressure) |

---

## 5. Signal Normalization Layer

### Normalization Pipeline

```python
class SignalNormalizer:
    def normalize(self, raw_value, lookback=30):
        """
        Normalize raw signal to [-1.0, +1.0] using z-score.
        
        1. Compute z-score over lookback window
        2. Clip to [-3, +3] (outliers)
        3. Map to [-1.0, +1.0]
        """
        history = self.get_history(lookback)
        mean = np.mean(history)
        std = np.std(history)
        if std == 0:
            return 0.0
        z = (raw_value - mean) / std
        z = np.clip(z, -3, 3)
        return z / 3.0  # Map to [-1, +1]
    
    def time_align(self, signals, target_freq="5min"):
        """
        Align signals to common time grid.
        - 1-min signals: resample to 5-min (take latest)
        - Hourly signals: forward-fill to 5-min
        - Daily signals: forward-fill to 5-min
        """
        aligned = {}
        for name, signal in signals.items():
            aligned[name] = signal.resample(target_freq).last().ffill()
        return aligned
```

### Confidence Weighting

Each signal has a confidence score based on:
- Data freshness (stale data = lower confidence)
- Sample size (fewer data points = lower confidence)
- Historical accuracy (backtested reliability)

```python
def weighted_signal(signal_value, confidence, base_weight):
    """Apply confidence weighting to signal."""
    effective_weight = base_weight * confidence
    return signal_value * effective_weight
```

---

## 6. Composite Alpha Score

### Weight Configuration

```yaml
alpha_weights:
  # Primary signals (uncorrelated, high alpha)
  on_chain_exchange_flows: 0.20
  funding_rate: 0.18
  social_mention_velocity: 0.15
  
  # Secondary signals
  whale_accumulation: 0.12
  stablecoin_flows: 0.10
  
  # Supporting signals
  google_trends: 0.08
  dev_activity: 0.07
  token_unlocks: 0.05
  reddit_sentiment: 0.05
```

### Score Computation

```python
class CompositeAlphaScore:
    def compute(self, signals: Dict[str, float]) -> float:
        """
        Compute weighted composite alpha score.
        
        Returns: float in [-1.0, +1.0]
          -1.0 = strong sell signal
           0.0 = neutral
          +1.0 = strong buy signal
        """
        total = 0.0
        total_weight = 0.0
        
        for name, value in signals.items():
            weight = ALPHA_WEIGHTS.get(name, 0.0)
            confidence = self.get_confidence(name)
            total += value * weight * confidence
            total_weight += weight * confidence
        
        if total_weight == 0:
            return 0.0
        
        score = total / total_weight
        return np.clip(score, -1.0, +1.0)
    
    def get_actionable_signal(self, score):
        """Map score to action recommendation."""
        if abs(score) < 0.15:
            return "NEUTRAL"  # No clear signal
        elif score > 0.5:
            return "STRONG_BUY"
        elif score > 0.25:
            return "BUY"
        elif score < -0.5:
            return "STRONG_SELL"
        elif score < -0.25:
            return "SELL"
        return "NEUTRAL"
```

### Integration with Price-Based Signals

```python
def combine_with_technical(alt_score, technical_signal):
    """
    Alternative data acts as conviction multiplier, not replacement.
    
    - Strong alt data + technical signal = high conviction trade
    - Strong alt data + no technical signal = wait
    - Weak alt data + technical signal = reduce size
    - Conflicting signals = skip
    """
    if abs(alt_score) < 0.15:
        return technical_signal * 0.5  # Reduce conviction
    
    if np.sign(alt_score) == np.sign(technical_signal.direction):
        return technical_signal * (1.0 + abs(alt_score) * 0.5)  # Boost
    
    if np.sign(alt_score) != np.sign(technical_signal.direction):
        return None  # Conflicting — skip trade
```

---

## 7. Polling & Caching Strategy

### Polling Schedule

| Source | Frequency | TTL | Reason |
|--------|-----------|-----|--------|
| Exchange funding/OI | 1 min | 30 sec | Fast-moving, high alpha |
| On-chain flows | 5 min | 3 min | Block time dependent |
| Social mentions | 15 min | 10 min | Slower propagation |
| Whale alerts | 5 min | 3 min | Time-sensitive |
| Google Trends | 6 hours | 4 hours | Very slow updating |
| GitHub activity | Daily | 12 hours | Fundamental, not timing |
| Token unlocks | Daily | 24 hours | Calendar-based |

### Caching Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  API Source   │────▶│  Redis Cache  │────▶│  Signal      │
│  (rate-limited)│     │  (TTL-based) │     │  Normalizer  │
└──────────────┘     └──────────────┘     └──────────────┘
                            │
                     ┌──────┴──────┐
                     │  PostgreSQL  │
                     │  (historical)│
                     └─────────────┘
```

### Rate Limit Management

```yaml
rate_limits:
  etherscan:
    requests_per_second: 5
    burst: 10
    strategy: token_bucket
  defillama:
    requests_per_minute: 300  # No auth, generous
    strategy: sliding_window
  lunarcrush:
    requests_per_minute: 30
    strategy: sliding_window
  binance_futures:
    requests_per_minute: 1200
    strategy: sliding_window
  github:
    requests_per_hour: 5000  # With free token
    strategy: sliding_window
```

---

## 8. Integration Points

### With Strategy Engine
- Alpha score as conviction multiplier for trade signals
- Threshold gating: skip trades when alpha score conflicts
- Position size adjustment based on alpha strength

### With Market Regime Detection
- Social sentiment extremes as regime confirmation
- Funding rate extremes as crisis indicators
- On-chain flows as trend validation

### With Risk Manager
- Alternative data drawdown warnings (whale selling detected)
- Correlation spike detection across data sources
- Signal degradation alerts (all sources turning negative)

### With Portfolio Manager
- Sector rotation signals (whale movement between protocols)
- Asset selection based on on-chain fundamentals
- Risk-on/risk-off signals from derivatives data

---

## 9. Implementation Roadmap

### Phase 1: Quick Wins (Day 1–3)
- [ ] DefiLlama API integration (stablecoin flows, TVL)
- [ ] Binance Futures API (funding rates, OI)
- [ ] Google Trends via pytrends
- [ ] Basic composite score calculator

### Phase 2: Social Layer (Day 4–7)
- [ ] Twitter/X mention velocity tracking
- [ ] LunarCrush API integration
- [ ] Reddit sentiment (VADER analysis)
- [ ] Signal normalization pipeline

### Phase 3: On-Chain Depth (Week 2)
- [ ] Dune Analytics queries (whale tracking, DEX flows)
- [ ] Etherscan API whale monitoring
- [ ] CryptoQuant free tier integration
- [ ] Cross-source signal validation

### Phase 4: Production Hardening (Week 3+)
- [ ] Redis caching layer with TTL management
- [ ] Rate limit enforcement across all sources
- [ ] Historical signal storage for backtesting
- [ ] Signal quality monitoring and degradation alerts
- [ ] Weight tuning based on backtested alpha contribution

---

*Architecture document for Alpha Stack Alternative Data System. Based on research findings: combined multi-signal approach delivers 15–25% win rate improvement vs price-only strategies, at $0/month cost using free API tiers.*
