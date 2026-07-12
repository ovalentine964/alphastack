# Alpha Stack — MEXC Exchange Integration Architecture

**Version:** 1.0
**Date:** 2026-07-13
**Status:** Architecture Design
**Dependencies:** Broker Abstraction Layer, Execution Algorithms, Risk Management

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Design Philosophy](#2-design-philosophy)
3. [System Architecture](#3-system-architecture)
4. [MEXC API Integration](#4-mexc-api-integration)
5. [Grid Bot Integration](#5-grid-bot-integration)
6. [Token Risk Assessment](#6-token-risk-assessment)
7. [Safety Controls](#7-safety-controls)
8. [Integration Points](#8-integration-points)
9. [Implementation Roadmap](#9-implementation-roadmap)

---

## 1. Executive Summary

### Problem

MEXC is a Tier 2 crypto exchange with 800+ trading pairs, many of which are micro-cap tokens with extreme volatility and thin liquidity. Running grid bots on illiquid tokens (e.g., PEEPO with $4/day volume, DAO_DISB with no API data) is capital suicide. Alpha Stack needs a systematic approach to evaluate MEXC bot opportunities and reject dangerous ones.

### Solution

A **MEXC connector with embedded risk assessment** that integrates via CCXT, evaluates token viability before deploying capital, and enforces strict safety controls (minimum volume, maximum allocation, mandatory stop-losses).

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Integration | CCXT library | Unified API, handles MEXC quirks, maintained |
| Token screening | Automated risk scoring | 4 of 8 researched bots were on non-viable tokens |
| Min volume threshold | $50K/day | Below this, grid orders can't fill |
| Max per-token allocation | 10% of capital | Concentration risk control |
| Max total MEXC exposure | 30% of capital | Exchange risk control |

---

## 2. Design Philosophy

### P1: Screen Before Deploy
Never deploy capital to a token without automated viability assessment. Volume, liquidity depth, project credibility, and spread must all pass thresholds.

### P2: Assume MEXC Is Risky
MEXC is Tier 2 — lower liquidity, higher manipulation risk, less regulatory oversight than Binance. Allocate accordingly (max 30% of capital).

### P3: USDT Pairs Only
Avoid cross-pairs (e.g., CBK/ETH/USDT). ETH as intermediary adds noise and cost. Direct USDT pairs are cleaner.

### P4: Stop-Loss Is Mandatory
Every MEXC position must have a stop-loss. No exceptions. Meme tokens can drop 50% in hours.

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    MEXC INTEGRATION LAYER                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     │
│  │  MEXC API    │────▶│  TOKEN       │────▶│  GRID BOT    │     │
│  │  (CCXT)      │     │  SCREENER    │     │  MANAGER     │     │
│  └──────────────┘     └──────┬───────┘     └──────┬───────┘     │
│                              │                     │             │
│                              ▼                     ▼             │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │              RISK ASSESSMENT ENGINE                       │     │
│  │  • Volume check (min $50K/day)                           │     │
│  │  • Liquidity depth check (order book analysis)           │     │
│  │  • Spread check (max 0.5%)                               │     │
│  │  • Project credibility (CMC/CG listing, team, docs)      │     │
│  │  • Price manipulation detection                          │     │
│  └──────────────────────────┬──────────────────────────────┘     │
│                             │                                     │
│                             ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │              SAFETY CONTROLS                              │     │
│  │  • Max 10% per token                                     │     │
│  │  • Max 30% total MEXC exposure                           │     │
│  │  • Mandatory stop-loss (-15% to -25%)                    │     │
│  │  • Weekly performance review                             │     │
│  │  • Auto-shutdown on anomaly                              │     │
│  └─────────────────────────────────────────────────────────┘     │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. MEXC API Integration

### CCXT Configuration

```python
import ccxt

class MEXCConnector:
    def __init__(self, api_key, api_secret):
        self.exchange = ccxt.mexc({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
    
    def get_ticker(self, symbol):
        """Get 24h ticker data."""
        return self.exchange.fetch_ticker(symbol)
    
    def get_order_book(self, symbol, limit=20):
        """Get order book for liquidity analysis."""
        return self.exchange.fetch_order_book(symbol, limit)
    
    def get_ohlcv(self, symbol, timeframe='1h', limit=100):
        """Get candle data for analysis."""
        return self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    
    def create_grid_orders(self, symbol, side, prices, size_per_order):
        """Place grid orders at specified price levels."""
        orders = []
        for price in prices:
            order = self.exchange.create_order(
                symbol, 'limit', side, size_per_order, price
            )
            orders.append(order)
        return orders
```

### Rate Limit Management

```yaml
mexc_rate_limits:
  public_api:
    requests_per_second: 20
    weight_per_minute: 1200
  private_api:
    requests_per_second: 10
    orders_per_second: 5
  strategy: token_bucket_with_backoff
```

---

## 5. Grid Bot Integration

### Grid Bot Configuration

```python
class GridBotManager:
    def deploy_grid(self, token, config):
        """Deploy a grid bot with safety checks."""
        # Step 1: Risk assessment
        risk = self.assess_token(token)
        if not risk.passed:
            return f"REJECTED: {risk.reason}"
        
        # Step 2: Calculate grid parameters
        grid = self.calculate_grid(
            current_price=config.current_price,
            upper_bound=config.upper_bound,
            lower_bound=config.lower_bound,
            grid_count=config.grid_count
        )
        
        # Step 3: Place orders
        orders = self.mexc.create_grid_orders(
            symbol=config.symbol,
            side='both',
            prices=grid.levels,
            size_per_order=config.size_per_level
        )
        
        # Step 4: Set stop-loss
        self.mexc.create_stop_loss(
            symbol=config.symbol,
            stop_price=config.stop_loss_price,
            size=config.total_size
        )
        
        return GridDeployment(orders=orders, grid=grid, stop_loss=config.stop_loss_price)
```

### Grid Parameters by Token Risk

| Risk Level | Grid Spacing | Grid Count | Max Allocation | Stop-Loss |
|-----------|-------------|-----------|---------------|----------|
| Low (BROCCOLI) | 2–3% | 15–20 | 8% | -20% |
| Medium (SIREN) | 3–5% | 10–15 | 5% | -25% |
| High (CBK) | 1.5–2% | 10–15 | 5% | -15% |
| Reject (SURF, PEEPO) | N/A | N/A | 0% | N/A |

---

## 6. Token Risk Assessment

### Automated Screening

```python
class TokenScreener:
    def assess(self, symbol) -> RiskAssessment:
        """Comprehensive token viability check."""
        ticker = self.mexc.get_ticker(symbol)
        order_book = self.mexc.get_order_book(symbol)
        
        checks = {
            "volume": self._check_volume(ticker, min_daily=50_000),
            "spread": self._check_spread(order_book, max_pct=0.5),
            "depth": self._check_depth(order_book, min_usd=5_000),
            "listing": self._check_cmc_listing(symbol),
            "balance": self._check_book_balance(order_book),
        }
        
        passed = all(checks.values())
        return RiskAssessment(
            passed=passed,
            checks=checks,
            risk_level=self._calculate_risk_level(checks),
            rejection_reason=None if passed else self._first_failure(checks)
        )
    
    def _check_volume(self, ticker, min_daily):
        """Reject if daily volume < $50K."""
        return ticker['quoteVolume'] >= min_daily
    
    def _check_spread(self, order_book, max_pct):
        """Reject if spread > 0.5%."""
        bid = order_book['bids'][0][0]
        ask = order_book['a'][0][0]
        spread_pct = (ask - bid) / bid * 100
        return spread_pct <= max_pct
    
    def _check_depth(self, order_book, min_usd):
        """Reject if order book depth < $5K within 2%."""
        # Sum liquidity within 2% of mid-price
        mid = (order_book['bids'][0][0] + order_book['a'][0][0]) / 2
        bid_depth = sum(q * p for p, q in order_book['bids'] if p > mid * 0.98)
        ask_depth = sum(q * p for p, q in order_book['a'] if p < mid * 1.02)
        return min(bid_depth, ask_depth) >= min_usd
```

### Research Findings: Token Viability

| Token | Volume/Day | Spread | Verdict |
|-------|-----------|--------|---------|
| BROCCOLI | $70,900 | 0.15% | ✅ Viable |
| SIREN | $105,300 | 0.086% | ✅ Viable |
| CBK | $54,700 | 0.38% | ⚠️ Marginal |
| STOC | $38,000 | 0.048% | ⚠️ Thin depth |
| SURF | $2,000 | N/A | ❌ Reject |
| PEEPO | $4 | N/A | ❌ Reject |
| DAO_DISB | Unknown | N/A | ❌ Reject |
| GOGLIZZ | Unknown | N/A | ❌ Reject |

---

## 7. Safety Controls

### Exposure Limits

```yaml
mexc_safety_controls:
  max_per_token_pct: 10        # Max 10% of capital per token
  max_total_mexc_pct: 30       # Max 30% of capital on MEXC
  max_concurrent_bots: 3       # Max 3 grid bots simultaneously
  mandatory_stop_loss: true    # Every position must have stop-loss
  min_daily_volume_usd: 50000  # Minimum viable volume
  max_spread_pct: 0.5          # Maximum acceptable spread
  
  monitoring:
    check_interval: 5min       # Check bot health every 5 min
    anomaly_detection: true    # Detect unusual price/volume patterns
    auto_shutdown:
      drawdown_trigger: -15%   # Auto-close if bot loses 15%
      volume_drop_trigger: 50% # Auto-close if volume drops 50%
      spread_widen_trigger: 2x # Auto-close if spread doubles
```

### Weekly Review Protocol

```python
def weekly_review(bot_id):
    """Automated weekly performance review."""
    performance = get_bot_performance(bot_id, days=7)
    
    if performance.total_pnl < -0.10:  # Lost >10%
        return Action.REDUCE_SIZE
    
    if performance.fill_rate < 0.50:   # <50% orders filled
        return Action.WIDEN_GRID
    
    if performance.volume_trend < -0.30:  # Volume declining 30%+
        return Action.PREPARE_EXIT
    
    return Action.CONTINUE
```

---

## 8. Integration Points

### With Broker Abstraction Layer
- MEXC is a connector implementing `BrokerConnector` interface
- Unified order/position/balance model
- Smart routing between MEXC and other exchanges

### With Risk Manager
- MEXC exposure tracked in portfolio-level risk
- Correlation monitoring across MEXC positions
- Drawdown limits apply to MEXC bots

### With TCA Engine
- MEXC-specific cost model (0.05% maker/taker fees)
- Spread cost tracking per token
- Slippage monitoring on grid fills

### With Alternative Data
- On-chain signals for MEXC-listed tokens
- Social sentiment for meme tokens
- Whale tracking for relevant tokens

---

## 9. Implementation Roadmap

### Phase 1: Basic Integration (Week 1)
- [ ] CCXT MEXC connector
- [ ] Token risk screener (volume + spread checks)
- [ ] Basic grid bot deployment
- [ ] Stop-loss enforcement

### Phase 2: Enhanced Screening (Week 2–3)
- [ ] Order book depth analysis
- [ ] CMC/CG listing verification
- [ ] Automated grid parameter calculation
- [ ] Weekly review automation

### Phase 3: Production Hardening (Week 4+)
- [ ] Anomaly detection (price manipulation)
- [ ] Auto-shutdown triggers
- [ ] Performance analytics dashboard
- [ ] Multi-bot portfolio management

### Phase 4: Optimization (Month 2+)
- [ ] Backtested grid parameters per token type
- [ ] Dynamic grid adjustment based on volatility
- [ ] Cross-exchange arbitrage detection
- [ ] Token rotation strategy (replace underperformers)

---

*Architecture document for Alpha Stack MEXC Integration. Based on research findings: 4 of 8 researched MEXC bot tokens were non-viable ($4/day volume, unidentifiable tokens). Automated screening is essential to prevent capital destruction.*
