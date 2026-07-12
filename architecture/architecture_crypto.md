# Alpha Stack — Crypto-Specific Trading Architecture

> **Version:** 1.0 · **Date:** 2026-07-11 · **Author:** Architecture Team
> **Source Research:** [`research/market/research_07_trading_pairs.md`](../research/market/research_07_trading_pairs.md), [`research/market/research_market_microstructure.md`](../research/market/research_market_microstructure.md) — Trading pairs analysis and market microstructure
> **Status:** Architecture Complete

---

**Version:** 1.0  
**Date:** 2026-07-11  
**Author:** Crypto Integration Architect  
**Scope:** On-chain data, DeFi integration, crypto-specific risk management, and the full crypto trading stack  
**Status:** Architecture Design — Ready for Implementation

---

## Table of Contents

1. [Design Philosophy](#1-design-philosophy)
2. [Crypto Exchange Integration](#2-crypto-exchange-integration)
3. [On-Chain Data Pipeline](#3-on-chain-data-pipeline)
4. [Crypto-Specific Indicators](#4-crypto-specific-indicators)
5. [DeFi Integration](#5-defi-integration)
6. [Crypto-Specific Risk Management](#6-crypto-specific-risk-management)
7. [Crypto Portfolio Construction](#7-crypto-portfolio-construction)
8. [Crypto News and Sentiment](#8-crypto-news-and-sentiment)
9. [Staking and Yield Opportunities](#9-staking-and-yield-opportunities)
10. [Crypto Tax Considerations](#10-crypto-tax-considerations)
11. [Future: Tokenized RWA, CBDCs, Cross-Chain](#11-future-tokenized-rwa-cbdcs-cross-chain)
12. [Integration with Alpha Stack Engine](#12-integration-with-alpha-stack-engine)
13. [Implementation Roadmap](#13-implementation-roadmap)

---

## 1. Design Philosophy

### Why Crypto Needs Its Own Architecture

Crypto is not "forex with more volatility." It is a fundamentally different market microstructure:

| Dimension | Forex | Crypto | Implication |
|-----------|-------|--------|-------------|
| **Operating Hours** | 24/5 | 24/7/365 | No downtime. No weekend gaps. But also no rest. |
| **Circuit Breakers** | Exchange-level LULD | **None** | BTC can drop 50% overnight with no halt. |
| **Settlement** | T+2 (CLS) | Block-time (seconds) | Instant finality but also instant liquidation. |
| **Counterparty** | Regulated broker | Exchange (often unregulated) | FTX proved exchange risk is existential. |
| **Data Sources** | Price + macro | Price + on-chain + social + DeFi + derivatives | Orders of magnitude more data dimensions. |
| **Market Manipulation** | Moderate (central banks) | Severe (whales, wash trading, MEV) | Can't trust order flow naively. |
| **Asset Lifecycle** | Decades-old pairs | Tokens launch and die in weeks | Survivorship bias is extreme. |
| **Leverage** | 30:1–50:1 (regulated) | Up to 125:1 (unregulated) | Liquidation cascades are the #1 short-term driver. |
| **Correlation Structure** | Stable macro relationships | Regime-dependent (BTC-beta dominates) | Altcoins are leveraged BTC bets most of the time. |

**Core Design Principle:** The crypto architecture must treat on-chain data, derivatives data, and social sentiment as **first-class inputs** — not optional overlays. In forex, price + macro is 90% of the edge. In crypto, on-chain + derivatives + sentiment is 60% of the edge.

---

## 2. Crypto Exchange Integration

### 2.1 CCXT Unified Layer

All exchange interaction flows through **CCXT** — the de facto standard library supporting 100+ crypto exchanges with a single API.

```python
# Architecture: Exchange Abstraction via CCXT
class CryptoExchangeRouter:
    """
    Unified exchange interface. Routes orders to optimal venue.
    Supports: Binance, Bybit, OKX, Coinbase, Kraken, dYdX, Hyperliquid
    """
    
    EXCHANGES = {
        "binance": {
            "class": ccxt.binance,
            "type": "cex",
            "tier": 1,
            "maker_fee": 0.0002,    # 0.02% (with BNB discount)
            "taker_fee": 0.0004,    # 0.04%
            "max_leverage": 125,
            "perpetuals": True,
            "spot": True,
            "api_rate_limit": 1200,  # requests/min
            "websocket": True,
            "testnet": True,
        },
        "bybit": {
            "class": ccxt.bybit,
            "type": "cex",
            "tier": 1,
            "maker_fee": 0.0002,
            "taker_fee": 0.00055,
            "max_leverage": 100,
            "perpetuals": True,
            "spot": True,
            "api_rate_limit": 600,
            "websocket": True,
            "testnet": True,
        },
        "okx": {
            "class": ccxt.okx,
            "type": "cex",
            "tier": 1,
            "maker_fee": 0.0002,
            "taker_fee": 0.0005,
            "max_leverage": 100,
            "perpetuals": True,
            "spot": True,
            "api_rate_limit": 600,
            "websocket": True,
            "testnet": True,
        },
        "dydx": {
            "class": ccxt.dydx,
            "type": "dex",
            "tier": 1,
            "maker_fee": 0.0002,
            "taker_fee": 0.0005,
            "max_leverage": 20,
            "perpetuals": True,
            "spot": False,
            "api_rate_limit": 300,
            "websocket": True,
            "testnet": True,
        },
        "hyperliquid": {
            "class": None,  # Custom SDK — not in CCXT yet
            "type": "dex",
            "tier": 1,
            "maker_fee": 0.0002,
            "taker_fee": 0.0005,
            "max_leverage": 50,
            "perpetuals": True,
            "spot": True,
            "api_rate_limit": 200,
            "websocket": True,
            "testnet": True,
        },
    }
    
    def __init__(self, config: dict):
        self.exchanges = {}
        for name, params in self.EXCHANGES.items():
            if config.get(name, {}).get("enabled"):
                self.exchanges[name] = params["class"]({
                    "apiKey": config[name]["api_key"],
                    "secret": config[name]["secret"],
                    "sandbox": config[name].get("testnet", False),
                    "enableRateLimit": True,
                    "options": {"defaultType": "swap"},  # Perpetuals by default
                })
    
    def get_best_venue(self, symbol: str, side: str, size: float) -> str:
        """Route order to exchange with best effective price."""
        quotes = {}
        for name, ex in self.exchanges.items():
            try:
                book = ex.fetch_order_book(symbol, limit=20)
                effective_price = self._calculate_effective_price(
                    book, side, size
                )
                fee = (self.EXCHANGES[name]["maker_fee"] 
                       if side == "limit" 
                       else self.EXCHANGES[name]["taker_fee"])
                quotes[name] = {
                    "effective_price": effective_price,
                    "fee": fee,
                    "net_price": effective_price * (1 + fee if side == "buy" else 1 - fee),
                }
            except Exception:
                continue
        return min(quotes, key=lambda x: quotes[x]["net_price"])
```

### 2.2 Exchange-Specific Considerations

| Exchange | Strengths | Weaknesses | Best For |
|----------|-----------|------------|----------|
| **Binance** | Deepest liquidity, most pairs, lowest fees | Regulatory risk in some jurisdictions | Primary execution venue |
| **Bybit** | Excellent perpetuals, copy trading data | Smaller spot market | Perps trading, sentiment data |
| **OKX** | Best altcoin perps, structured products | Complex API | Altcoin derivatives |
| **dYdX** | Fully decentralized, transparent orderbook | Lower leverage, smaller books | DEX execution, MEV-resistant |
| **Hyperliquid** | CEX-speed on-chain, tokenized stocks | Newer, less battle-tested | On-chain perps, RWA trading |
| **Coinbase** | US-regulated, fiat on-ramp | Higher fees, fewer pairs | Fiat conversion, compliance |

### 2.3 Multi-Exchange Data Normalization

```python
class CryptoDataNormalizer:
    """
    Normalizes data across exchanges into a unified schema.
    Handles different timestamp formats, price precisions,
    volume units, and funding rate schedules.
    """
    
    def normalize_ohlcv(self, exchange: str, raw_candles: list) -> pd.DataFrame:
        df = pd.DataFrame(raw_candles, columns=[
            "timestamp", "open", "high", "low", "close", "volume"
        ])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df["exchange"] = exchange
        df["vwap"] = (df["volume"] * (df["high"] + df["low"]) / 2).cumsum() / df["volume"].cumsum()
        return df
    
    def normalize_funding_rate(self, exchange: str, raw: dict) -> dict:
        """Funding rates: Binance/Bybit = 8h, dYdX = hourly, Hyperliquid = variable."""
        INTERVAL_MAP = {
            "binance": 8, "bybit": 8, "okx": 8,
            "dydx": 1, "hyperliquid": 1,
        }
        return {
            "exchange": exchange,
            "symbol": raw["symbol"],
            "rate": float(raw["fundingRate"]),
            "annualized": float(raw["fundingRate"]) * (365 * 24 / INTERVAL_MAP[exchange]),
            "next_funding_time": raw.get("fundingTimestamp"),
            "interval_hours": INTERVAL_MAP[exchange],
        }
    
    def normalize_order_book(self, exchange: str, raw_book: dict, depth: int = 20) -> dict:
        """Unified order book with bid/ask imbalance, spread, and depth metrics."""
        bids = raw_book["bids"][:depth]
        asks = raw_book["asks"][:depth]
        bid_vol = sum(b[1] for b in bids)
        ask_vol = sum(a[1] for a in asks)
        return {
            "exchange": exchange,
            "best_bid": bids[0][0],
            "best_ask": asks[0][0],
            "spread_pct": (asks[0][0] - bids[0][0]) / bids[0][0] * 100,
            "bid_ask_imbalance": (bid_vol - ask_vol) / (bid_vol + ask_vol),
            "bid_depth_usd": sum(b[0] * b[1] for b in bids),
            "ask_depth_usd": sum(a[0] * a[1] for a in asks),
            "mid_price": (bids[0][0] + asks[0][0]) / 2,
        }
```

### 2.4 WebSocket Real-Time Feed

```python
class CryptoWebSocketManager:
    """
    Manages real-time WebSocket connections to multiple exchanges.
    Provides unified tick, trade, orderbook, and funding rate streams.
    """
    
    STREAMS = {
        "binance": {
            "tick": "{symbol}@ticker",
            "trade": "{symbol}@trade",
            "book": "{symbol}@depth20@100ms",
            "funding": "{symbol}@markPrice@1s",
            "liquidation": "{symbol}@forceOrder",
        },
        "bybit": {
            "tick": "tickers.{symbol}",
            "trade": "publicTrade.{symbol}",
            "book": "orderbook.25.{symbol}",
            "funding": "publicTickers.{symbol}",
        },
    }
    
    async def start_streams(self, symbols: list, streams: list):
        """Start all configured streams. Auto-reconnect on disconnect."""
        tasks = []
        for exchange in self.exchanges:
            for symbol in symbols:
                for stream_type in streams:
                    tasks.append(self._stream_loop(exchange, symbol, stream_type))
        await asyncio.gather(*tasks)
    
    async def _stream_loop(self, exchange, symbol, stream_type):
        """Reconnecting stream with exponential backoff."""
        while True:
            try:
                async for msg in self._connect(exchange, symbol, stream_type):
                    normalized = self._normalize(exchange, stream_type, msg)
                    await self._publish(normalized)  # Redis pub/sub
            except Exception as e:
                logger.warning(f"Stream {exchange}/{symbol}/{stream_type} dropped: {e}")
                await asyncio.sleep(min(60, 2 ** self._retry_count))
```

### 2.5 Exchange Health Monitoring

```python
EXCHANGE_HEALTH_METRICS = {
    "api_latency_ms": {"warn": 500, "critical": 2000},
    "order_rejection_rate": {"warn": 0.05, "critical": 0.15},
    "websocket_disconnects_per_hour": {"warn": 3, "critical": 10},
    "funding_rate_deviation_from_peers": {"warn": 0.0005, "critical": 0.002},
    "orderbook_depth_ratio_vs_baseline": {"warn": 0.5, "critical": 0.2},
    "withdrawal_processing_time_min": {"warn": 30, "critical": 120},
}
```

---

## 3. On-Chain Data Pipeline

On-chain data is the **single most unique advantage** crypto offers over traditional markets. It's the equivalent of being able to see every institutional order flow, every fund transfer, and every insider transaction in real-time.

### 3.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ON-CHAIN DATA PIPELINE                             │
│                                                                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │ Ethereum  │  │ Solana   │  │ Bitcoin  │  │ L2s      │            │
│  │ RPC/Node  │  │ RPC/Node │  │ RPC/Node │  │ (Base,   │            │
│  │           │  │          │  │          │  │  Arb,OP) │            │
│  └─────┬────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘            │
│        │             │             │              │                    │
│        └─────────────┴─────────────┴──────────────┘                   │
│                              │                                        │
│                    ┌─────────▼──────────┐                             │
│                    │   BLOCK INDEXER     │                             │
│                    │   (real-time sync)  │                             │
│                    └─────────┬──────────┘                             │
│                              │                                        │
│        ┌─────────────────────┼─────────────────────┐                 │
│        │                     │                     │                  │
│  ┌─────▼──────┐  ┌──────────▼──────────┐  ┌──────▼───────┐         │
│  │   WHALE    │  │   EXCHANGE FLOW     │  │   DeFi       │         │
│  │   TRACKER  │  │   ANALYZER          │  │   ACTIVITY   │         │
│  │            │  │                     │  │              │         │
│  │ Labeled    │  │ Exchange wallets    │  │ DEX volume   │         │
│  │ wallets    │  │ Inflow/outflow     │  │ TVL changes  │         │
│  │ Tx size    │  │ Stablecoin flows   │  │ Yield shifts │         │
│  │ Clustering │  │ OTC detection      │  │ Liquidations │         │
│  └─────┬──────┘  └──────────┬──────────┘  └──────┬───────┘         │
│        │                     │                     │                  │
│        └─────────────────────┼─────────────────────┘                 │
│                              │                                        │
│                    ┌─────────▼──────────┐                             │
│                    │  COMPOSITE ON-CHAIN │                             │
│                    │  SIGNAL AGGREGATOR  │                             │
│                    └────────────────────┘                             │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 Data Sources

| Source | API | Cost | Update Freq | Key Metrics |
|--------|-----|------|-------------|-------------|
| **DefiLlama** | `api.llama.fi` | Free, no auth | 5 min | TVL, yields, stablecoin supply, DEX volume |
| **CryptoQuant** | REST API | Free tier | 1 hour | Exchange reserves, miner flows, SOPR, MVRV |
| **Glassnode** | REST API | Free tier | 1 day | MVRV Z-Score, NUPL, RHODL, dormancy |
| **Dune Analytics** | GraphQL | Free (limited) | 1 hour | Custom queries: whale tracking, protocol metrics |
| **Arkham Intelligence** | API | Free tier | Real-time | Labeled wallets, entity tracking, fund flows |
| **Etherscan/Solscan** | REST API | Free (5 req/s) | Real-time | Wallet balances, token transfers, contract events |
| **Whale Alert** | Twitter + API | Free tier | Real-time | Large transaction alerts (> $100K) |
| **Coinglass** | REST API | Free (limited) | 1 min | Funding rates, OI, liquidation maps, L/S ratios |
| **Binance Futures** | REST API | Free, no key | 1 min | Funding, OI, mark price, liquidation stream |

### 3.3 Whale Tracking System

```python
class WhaleTracker:
    """
    Tracks whale wallets across multiple chains.
    Generates signals based on accumulation/distribution patterns.
    """
    
    # Known whale categories (labeled via Arkham/Dune)
    WHALE_CATEGORIES = {
        "exchange_hot_wallet": {"weight": -0.3, "desc": "Incoming = sell pressure"},
        "exchange_cold_wallet": {"weight": -0.1, "desc": "Long-term storage"},
        "defi_protocol_treasury": {"weight": 0.0, "desc": "Operational, not signal"},
        "known_fund": {"weight": 0.5, "desc": "Smart money accumulation"},
        "whale_cluster": {"weight": 0.4, "desc": "Unlabeled but high-value"},
        "miner": {"weight": -0.2, "desc": "Selling to cover costs"},
        "government": {"weight": -0.5, "desc": "Seized asset liquidation"},
    }
    
    # Minimum USD value to track
    THRESHOLD_USD = 100_000
    
    async def process_transaction(self, tx: dict) -> Optional[WhaleSignal]:
        """Process a whale transaction and generate signal."""
        if tx["value_usd"] < self.THRESHOLD_USD:
            return None
        
        from_cat = self._classify_wallet(tx["from"])
        to_cat = self._classify_wallet(tx["to"])
        
        # Key signal: whale accumulation (unknown → known fund)
        if to_cat == "known_fund" and from_cat not in ["exchange_hot_wallet"]:
            return WhaleSignal(
                type="accumulation",
                asset=tx["token"],
                value_usd=tx["value_usd"],
                confidence=0.7,
                lead_time_hours=4,  # Historical average
            )
        
        # Key signal: whale sending to exchange (potential sell)
        if to_cat == "exchange_hot_wallet" and from_cat == "whale_cluster":
            return WhaleSignal(
                type="distribution",
                asset=tx["token"],
                value_usd=tx["value_usd"],
                confidence=0.6,
                lead_time_hours=2,
            )
        
        # Key signal: large stablecoin move to exchange (buying power)
        if (tx["token"] in ["USDT", "USDC", "DAI"] and 
            to_cat == "exchange_hot_wallet" and 
            tx["value_usd"] > 1_000_000):
            return WhaleSignal(
                type="buying_power",
                asset="STABLECOIN",
                value_usd=tx["value_usd"],
                confidence=0.5,
                lead_time_hours=6,
            )
        
        return None
```

### 3.4 Exchange Flow Analyzer

```python
class ExchangeFlowAnalyzer:
    """
    Tracks net flow of assets to/from exchanges.
    The single strongest on-chain signal for crypto.
    """
    
    async def compute_net_flows(self, asset: str, window_hours: int = 24) -> dict:
        """
        Negative net flow = coins leaving exchanges = bullish (supply squeeze)
        Positive net flow = coins entering exchanges = bearish (sell pressure)
        """
        inflows = await self._get_exchange_inflows(asset, window_hours)
        outflows = await self._get_exchange_outflows(asset, window_hours)
        net_flow = outflows - inflows  # Positive = net outflow (bullish)
        
        # Z-score vs 30-day baseline
        baseline = await self._get_baseline(asset, days=30)
        z_score = (net_flow - baseline["mean"]) / baseline["std"]
        
        return {
            "asset": asset,
            "net_flow_usd": net_flow,
            "net_flow_zscore": z_score,
            "inflow_usd": inflows,
            "outflow_usd": outflows,
            "signal": "bullish" if z_score > 1.5 else "bearish" if z_score < -1.5 else "neutral",
            "strength": min(abs(z_score) / 3, 1.0),  # Normalize to 0-1
        }
    
    async def compute_stablecoin_flows(self, window_hours: int = 24) -> dict:
        """
        Stablecoin supply changes = dry powder indicator.
        Rising stablecoin supply on exchanges = potential buying.
        """
        usdt_change = await self._get_supply_change("USDT", window_hours)
        usdc_change = await self._get_supply_change("USDC", window_hours)
        total_change = usdt_change + usdc_change
        
        exchange_stablecoin_balance = await self._get_exchange_balance("STABLECOIN")
        
        return {
            "total_stablecoin_change_24h": total_change,
            "exchange_stablecoin_balance": exchange_stablecoin_balance,
            "buying_power_signal": "increasing" if total_change > 0 else "decreasing",
            "dry_powder_ratio": exchange_stablecoin_balance / await self._get_total_market_cap(),
        }
```

### 3.5 Polling Schedule

| Data Source | Frequency | Method | Latency |
|-------------|-----------|--------|---------|
| Exchange funding rates | **1 min** | REST API (batched) | ~100ms |
| Exchange OI | **1 min** | REST API | ~100ms |
| Exchange liquidations | **Real-time** | WebSocket stream | <1s |
| On-chain whale txs | **Real-time** | WebSocket / Dune | <5s |
| Exchange net flows | **5 min** | CryptoQuant API | ~1s |
| Stablecoin supply | **15 min** | DefiLlama API | ~1s |
| DeFi TVL changes | **15 min** | DefiLlama API | ~1s |
| DEX volume | **15 min** | Dune query | ~5s |
| MVRV / SOPR | **1 hour** | Glassnode API | ~1s |
| Whale accumulation patterns | **1 hour** | Dune custom query | ~10s |
| Google Trends | **6 hours** | pytrends | ~5s |
| GitHub dev activity | **24 hours** | GitHub API | ~1s |

---

## 4. Crypto-Specific Indicators

These indicators exist **only in crypto** and provide signals that have no equivalent in traditional markets.

### 4.1 Network Value to Transactions (NVT) Ratio

```
NVT = Market Cap / Daily On-Chain Transaction Volume (USD)

Interpretation:
- NVT > 150: Network overvalued relative to usage (bearish)
- NVT < 30: Network undervalued relative to usage (bullish)
- NVT trend: Rising NVT + rising price = speculative bubble forming
```

```python
class NVTCalculator:
    async def compute(self, asset: str, window: int = 90) -> dict:
        market_cap = await self._get_market_cap(asset)
        # Use adjusted transaction volume (remove self-sends, change outputs)
        tx_volume = await self._get_adjusted_tx_volume(asset, window)
        
        nvt = market_cap / tx_volume if tx_volume > 0 else float("inf")
        
        # Signal generation
        percentile = await self._get_historical_percentile(nvt, asset, lookback_days=365)
        
        return {
            "nvt": nvt,
            "nvt_percentile": percentile,  # 0-100
            "signal": "bearish" if percentile > 85 else "bullish" if percentile < 15 else "neutral",
            "divergence": self._check_price_nvt_divergence(asset),
        }
    
    def _check_price_nvt_divergence(self, asset) -> str:
        """
        Price making new highs while NVT declining = bullish (increasing utility)
        Price flat while NVT rising = bearish (speculation outpacing usage)
        """
        # Compare 30-day trends of price vs NVT
        price_slope = self._trend_slope("price", asset, 30)
        nvt_slope = self._trend_slope("nvt", asset, 30)
        
        if price_slope > 0 and nvt_slope < 0:
            return "bullish_divergence"  # Price up, NVT down = healthy
        elif price_slope < 0 and nvt_slope > 0:
            return "bearish_divergence"  # Price down, NVT up = unhealthy
        return "aligned"
```

### 4.2 Market Value to Realized Value (MVRV) Z-Score

```
MVRV = Market Cap / Realized Cap

Where Realized Cap = Sum of (each UTXO × price when last moved)

MVRV Z-Score = (Market Cap - Realized Cap) / StdDev(Market Cap)

Interpretation:
- Z-Score > 7: Extreme overvaluation (cycle top signal — sell)
- Z-Score > 3.5: Overvalued (reduce exposure)
- Z-Score < 0: Undervalued (accumulate)
- Z-Score < -0.5: Extreme undervaluation (cycle bottom — buy aggressively)
```

### 4.3 Spent Output Profit Ratio (SOPR)

```
SOPR = Value of spent outputs at current price / Value when created

Interpretation:
- SOPR > 1: Coins being sold at profit (bullish if trending up, bearish if extreme)
- SOPR < 1: Coins being sold at loss (capitulation — potential bottom)
- SOPR = 1: Breakeven selling (support/resistance level)

Key signal: SOPR < 1 for extended period then crosses back above 1 = strong buy
```

### 4.4 Funding Rate Analysis

```
Funding Rate = Premium/discount of perpetual futures vs spot index

Binance/Bybit: Paid every 8 hours (00:00, 08:00, 16:00 UTC)
dYdX/Hyperliquid: Paid every hour

Interpretation:
- Funding > 0.1% per 8h (45% annualized): Overcrowded longs → pullback likely
- Funding > 0.3% per 8h (135% annualized): Extreme greed → strong sell signal
- Funding < -0.05% per 8h: Overcrowded shorts → bounce likely
- Funding < -0.1% per 8h: Extreme fear → strong buy signal

Funding rate arbitrage:
- Long perp + short spot (or vice versa) to collect funding
- At 0.1%/8h = 0.3%/day = ~110% APR (market-neutral)
```

```python
class FundingRateAnalyzer:
    def analyze(self, symbol: str) -> dict:
        """Multi-exchange funding rate analysis."""
        rates = {}
        for exchange in ["binance", "bybit", "okx", "dydx"]:
            rates[exchange] = self._fetch_funding(exchange, symbol)
        
        avg_rate = np.mean([r["rate"] for r in rates.values()])
        rate_spread = max(r["rate"] for r in rates.values()) - min(r["rate"] for r in rates.values())
        
        return {
            "avg_funding_rate": avg_rate,
            "avg_annualized": avg_rate * 3 * 365,  # 8h funding → annual
            "cross_exchange_spread": rate_spread,
            "signal": self._generate_signal(avg_rate),
            "arb_opportunity": rate_spread > 0.0005,  # >0.05% spread = arb
            "rates_by_exchange": rates,
        }
    
    def _generate_signal(self, rate: float) -> str:
        if rate > 0.003:    # 0.3%/8h
            return "extreme_long_crowding_STRONG_SELL"
        elif rate > 0.001:  # 0.1%/8h
            return "long_crowding_SELL_BIAS"
        elif rate < -0.001: # -0.1%/8h
            return "short_crowding_BUY_BIAS"
        elif rate < -0.003: # -0.3%/8h
            return "extreme_short_crowding_STRONG_BUY"
        return "neutral"
```

### 4.5 Open Interest (OI) Analysis

```
Open Interest = Total outstanding notional value of futures contracts

Key signals:
- OI rising + price rising = Strong trend (new money entering)
- OI rising + price falling = Bearish (new shorts entering)
- OI falling + price rising = Weak rally (short covering, not new longs)
- OI falling + price falling = Capitulation (long liquidation)
- OI spike + price flat = Breakout imminent (direction unknown)
```

### 4.6 Liquidation Cascade Map

```
Leveraged position liquidation levels create "magnets" for price.

When price approaches a cluster of liquidation levels:
1. Forced market orders hit the book
2. Price moves further, triggering more liquidations
3. Cascade amplifies the move

Use Coinglass liquidation heatmaps to identify:
- Long liquidation clusters below current price (price targets these)
- Short liquidation clusters above current price (short squeeze targets)
```

### 4.7 Composite Crypto Indicator Score

```python
class CryptoIndicatorComposite:
    """
    Combines all crypto-specific indicators into a single score.
    """
    
    WEIGHTS = {
        "funding_rate":        0.20,  # Derivatives positioning
        "exchange_net_flow":   0.18,  # On-chain supply dynamics
        "mvrv_zscore":         0.15,  # Cycle position
        "sopr":                0.12,  # Profit/loss sentiment
        "nvt":                 0.10,  # Network valuation
        "oi_divergence":       0.10,  # Trend conviction
        "stablecoin_flows":    0.08,  # Dry powder
        "liquidation_map":     0.07,  # Short-term cascade risk
    }
    
    def compute_composite_score(self, asset: str) -> dict:
        scores = {}
        for indicator, weight in self.WEIGHTS.items():
            raw = self._compute_indicator(indicator, asset)
            normalized = self._normalize_to_neg1_pos1(raw)
            scores[indicator] = normalized * weight
        
        composite = sum(scores.values())
        
        return {
            "composite_score": composite,  # -1.0 to +1.0
            "signal": "strong_buy" if composite > 0.5 else 
                      "buy" if composite > 0.2 else
                      "strong_sell" if composite < -0.5 else
                      "sell" if composite < -0.2 else "neutral",
            "component_scores": scores,
            "conviction": abs(composite),  # How strong the signal is
            "agreement": self._compute_agreement(scores),  # Do indicators agree?
        }
    
    def _compute_agreement(self, scores: dict) -> float:
        """Percentage of indicators pointing in same direction."""
        directions = [1 if v > 0 else -1 if v < 0 else 0 for v in scores.values()]
        if not directions:
            return 0.0
        majority = max(set(directions), key=directions.count)
        return directions.count(majority) / len(directions)
```

---

## 5. DeFi Integration

### 5.1 DEX Data Pipeline

```
┌───────────────────────────────────────────────────────────────┐
│                    DeFi DATA PIPELINE                           │
│                                                                 │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐  │
│  │ Uniswap   │  │ Curve     │  │ Jupiter   │  │ Raydium   │  │
│  │ (Ethereum │  │ (Stable   │  │ (Solana   │  │ (Solana   │  │
│  │  + L2s)   │  │  swaps)   │  │  aggregator│ │  AMM)     │  │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘  │
│        └───────────────┼───────────────┼──────────────┘        │
│                        │               │                        │
│              ┌─────────▼───────────────▼─────────┐              │
│              │       DEX AGGREGATOR               │              │
│              │  (Volume, TVL, Price Impact,       │              │
│              │   Liquidity Depth, Impermanent Loss)│             │
│              └────────────────┬──────────────────┘              │
│                               │                                 │
│              ┌────────────────▼──────────────────┐              │
│              │     DeFi SIGNAL GENERATOR          │              │
│              │  - DEX volume spikes → momentum    │              │
│              │  - TVL changes → capital rotation  │              │
│              │  - Yield curve shifts → risk repricing│           │
│              │  - LP concentration → liquidity risk│             │
│              └───────────────────────────────────┘              │
└───────────────────────────────────────────────────────────────┘
```

### 5.2 DEX Metrics

| Metric | Source | Signal | Lead Time |
|--------|--------|--------|-----------|
| **DEX Volume** | Dune/DefiLlama | Volume spike → price momentum 4-12h ahead | 4-12h |
| **DEX/CEX Volume Ratio** | Dune | Rising = decentralization trend, bullish for DeFi tokens | Days |
| **TVL Changes** | DefiLlama | Sudden TVL drop → de-risking / exploit | 1-6h |
| **Liquidity Depth** | On-chain | Thin liquidity → large price impact → volatility | Real-time |
| **Impermanent Loss** | On-chain | High IL → LP withdrawals → liquidity crisis | Hours |
| **Stableswap Pool Imbalance** | Curve | Pool imbalance → market directional bias | Hours |
| **New Pair Launch Volume** | Dune | Volume on new pairs → narrative rotation | Hours |

### 5.3 Yield Farming Integration

```python
class DeFiYieldMonitor:
    """
    Monitors DeFi yield opportunities across protocols and chains.
    Integrates with DefiLlama yields API.
    """
    
    RISK_TIERS = {
        "low": {
            "protocols": ["aave", "compound", "maker"],
            "chains": ["ethereum"],
            "max_apy": 15,
            "tvl_minimum": 1_000_000_000,  # $1B+
        },
        "medium": {
            "protocols": ["curve", "convex", "yearn", "lido"],
            "chains": ["ethereum", "arbitrum", "base"],
            "max_apy": 30,
            "tvl_minimum": 100_000_000,
        },
        "high": {
            "protocols": ["pendle", "eigenlayer", "ether.fi"],
            "chains": ["ethereum", "arbitrum", "base", "solana"],
            "max_apy": 100,
            "tvl_minimum": 10_000_000,
        },
        "degen": {
            "protocols": ["*"],  # Any protocol
            "chains": ["*"],
            "max_apy": float("inf"),
            "tvl_minimum": 0,
        },
    }
    
    async def find_opportunities(self, risk_tier: str = "low") -> list:
        """Fetch and rank yield opportunities from DefiLlama."""
        url = "https://yields.llama.fi/pools"
        resp = await self.http.get(url)
        pools = resp.json()["data"]
        
        filtered = []
        tier = self.RISK_TIERS[risk_tier]
        
        for pool in pools:
            if (pool["tvlUsd"] >= tier["tvl_minimum"] and
                pool["apy"] <= tier["max_apy"] and
                (tier["protocols"] == ["*"] or pool["project"] in tier["protocols"]) and
                (tier["chains"] == ["*"] or pool["chain"] in tier["chains"])):
                
                # Risk-adjusted yield score
                il_risk = self._estimate_il_risk(pool)
                smart_contract_risk = self._estimate_sc_risk(pool["project"])
                
                filtered.append({
                    "pool": pool["pool"],
                    "project": pool["project"],
                    "chain": pool["chain"],
                    "symbol": pool["symbol"],
                    "apy": pool["apy"],
                    "tvl": pool["tvlUsd"],
                    "il_risk": il_risk,
                    "sc_risk": smart_contract_risk,
                    "risk_adjusted_apy": pool["apy"] * (1 - il_risk) * (1 - smart_contract_risk),
                    "impermanent_loss_7d": pool.get("il7d", 0),
                })
        
        return sorted(filtered, key=lambda x: x["risk_adjusted_apy"], reverse=True)
```

### 5.4 Liquidity Pool Monitoring

```python
class LiquidityPoolMonitor:
    """
    Monitors key liquidity pools for signals and risk.
    """
    
    KEY_POOLS = {
        "ETH/USDC_uniswap_v3": "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640",
        "WBTC/ETH_uniswap_v3": "0xcbcdf9626bc03e24f779434178a73a0b4bad62ed",
        "stETH/ETH_curve": "0xdc24316b9ae028f1497c275eb9192a3ea0f67022",
        "USDC/USDT_curve_3pool": "0xbebc44782c7db0a1a60cb6fe97d0b483032ff1c7",
    }
    
    async def check_pool_health(self, pool_id: str) -> dict:
        pool = await self._fetch_pool_state(pool_id)
        
        return {
            "pool_id": pool_id,
            "tvl_usd": pool["tvl"],
            "volume_24h": pool["volume_24h"],
            "fees_24h": pool["fees_24h"],
            "fee_apr": pool["fees_24h"] * 365 / pool["tvl"] * 100,
            "utilization": pool["volume_24h"] / pool["tvl"],
            "imbalance": self._compute_imbalance(pool),
            "liquidity_concentration": self._compute_concentration(pool),
            "whale_lp_share": self._compute_whale_lp_share(pool),
        }
```

### 5.5 Liquidation Monitoring (DeFi)

```python
class DeFiLiquidationMonitor:
    """
    Monitors DeFi lending protocols for liquidation events.
    Large liquidations cascade similar to futures liquidations.
    """
    
    PROTOCOLS = {
        "aave_v3": {
            "chains": ["ethereum", "arbitrum", "base", "polygon"],
            "health_factor_threshold": 1.0,
        },
        "compound_v3": {
            "chains": ["ethereum", "base", "arbitrum"],
            "health_factor_threshold": 1.0,
        },
        "maker": {
            "chains": ["ethereum"],
            "collateral_ratio_threshold": 1.5,
        },
        "morpho": {
            "chains": ["ethereum", "base"],
            "health_factor_threshold": 1.0,
        },
    }
    
    async def find_at_risk_positions(self, threshold: float = 1.2) -> list:
        """Find positions near liquidation threshold."""
        at_risk = []
        for protocol, config in self.PROTOCOLS.items():
            positions = await self._fetch_positions(protocol)
            for pos in positions:
                if pos["health_factor"] < threshold:
                    at_risk.append({
                        "protocol": protocol,
                        "chain": pos["chain"],
                        "user": pos["user"],
                        "health_factor": pos["health_factor"],
                        "collateral_value": pos["collateral_usd"],
                        "debt_value": pos["debt_usd"],
                        "liquidation_price": pos["liquidation_price"],
                        "collateral_asset": pos["collateral_asset"],
                    })
        
        # Aggregate: which assets have the most liquidation risk?
        asset_risk = self._aggregate_by_asset(at_risk)
        
        return {
            "positions_at_risk": at_risk,
            "asset_risk_summary": asset_risk,
            "total_at_risk_usd": sum(p["collateral_value"] for p in at_risk),
            "cascade_risk": self._estimate_cascade_risk(at_risk),
        }
```

---

## 6. Crypto-Specific Risk Management

### 6.1 The 24/7 Problem

Crypto never closes. This creates unique risks:

| Risk | Description | Mitigation |
|------|-------------|------------|
| **Weekend liquidity drain** | Market makers pull back on weekends, spreads widen | Reduce position sizes 50% on weekends |
| **Asia session manipulation** | Low-liquidity windows exploited for stop hunts | Widen stops during 00:00–06:00 UTC |
| **Holiday gaps** | Not applicable (no gaps), but volume drops | Monitor volume; reduce exposure when <50% of average |
| **No sleep** | System must run 24/7/365 | Full automation, no manual intervention needed |
| **Exchange maintenance** | Exchanges do maintenance during "quiet" periods | Multi-exchange failover |

### 6.2 No Circuit Breakers

Unlike equities (LULD halts), crypto has **zero circuit breakers**. A flash crash can liquidate everything in seconds.

```python
class CryptoCircuitBreaker:
    """
    Alpha Stack's own circuit breakers since exchanges provide none.
    """
    
    BREAKER_RULES = {
        # Price-based breakers
        "flash_crash_1m": {
            "trigger": "price_drop_pct_1min > 5",
            "action": "cancel_all_orders + reduce_position_50%",
            "cooldown_min": 15,
        },
        "flash_crash_5m": {
            "trigger": "price_drop_pct_5min > 10",
            "action": "cancel_all_orders + close_all_positions",
            "cooldown_min": 60,
        },
        "flash_crash_15m": {
            "trigger": "price_drop_pct_15min > 20",
            "action": "system_halt + alert_human",
            "cooldown_min": 240,
        },
        
        # Drawdown breakers
        "daily_loss": {
            "trigger": "daily_pnl_pct < -3",
            "action": "no_new_positions_24h",
            "cooldown_min": 1440,
        },
        "weekly_loss": {
            "trigger": "weekly_pnl_pct < -7",
            "action": "reduce_all_positions_50%",
            "cooldown_min": 10080,
        },
        "max_drawdown": {
            "trigger": "drawdown_from_peak_pct > 15",
            "action": "close_all + system_halt + alert_human",
            "cooldown_min": 0,  # Manual reset required
        },
        
        # Liquidity breakers
        "spread_spike": {
            "trigger": "spread_pct > 5x_baseline",
            "action": "cancel_all_orders + no_new_orders",
            "cooldown_min": 30,
        },
        "orderbook_depth_collapse": {
            "trigger": "depth_usd < 20%_of_baseline",
            "action": "reduce_position_sizes_50%",
            "cooldown_min": 60,
        },
        
        # Exchange-specific breakers
        "exchange_api_down": {
            "trigger": "api_failures > 5 in 5min",
            "action": "migrate_orders_to_backup_exchange",
            "cooldown_min": 15,
        },
        "exchange_withdrawal_halt": {
            "trigger": "withdrawal_pending > 2_hours",
            "action": "reduce_exposure_on_that_exchange",
            "cooldown_min": 60,
        },
        
        # On-chain breakers
        "stablecoin_depeg": {
            "trigger": "stablecoin_price < 0.98 or > 1.02",
            "action": "convert_to_alternate_stablecoin",
            "cooldown_min": 60,
        },
        "smart_contract_exploit_alert": {
            "trigger": "protocol_in_portfolio_has_exploit_alert",
            "action": "emergency_withdrawal_from_protocol",
            "cooldown_min": 0,
        },
    }
```

### 6.3 Exchange Counterparty Risk Management

The FTX collapse taught us that exchange risk is the **#1 existential risk** in crypto.

```python
class ExchangeRiskManager:
    """
    Manages counterparty exposure across exchanges.
    No single exchange should hold enough to cause catastrophic loss.
    """
    
    LIMITS = {
        "max_exposure_per_exchange_pct": 20,     # Max 20% of total capital
        "max_exposure_per_exchange_type_pct": 40, # Max 40% on CEX combined
        "min_exchanges_used": 3,                   # Always spread across 3+
        "max_fiat_on_exchange_hours": 24,          # Don't park fiat on exchange
        "proof_of_reserves_check_interval_hours": 24,
    }
    
    # Red flags that trigger immediate withdrawal
    RED_FLAGS = [
        "exchange_native_token_declining_30d",     # FTT-style signal
        "proof_of_reserves_merkle_tree_incomplete", # Can't verify solvency
        "withdrawal_delays_reported",                # Bank run signal
        "regulatory_action_announced",               # Legal risk
        "executive_departures",                      # Internal problems
        "exchange_token_is_large_pct_of_reserves",  # Circular value (FTX)
    ]
    
    async def check_exchange_health(self, exchange: str) -> dict:
        """Daily health check on each exchange we use."""
        health = {
            "exchange": exchange,
            "our_exposure_usd": await self._get_our_balance(exchange),
            "our_exposure_pct": await self._get_exposure_pct(exchange),
            "proof_of_reserves": await self._check_por(exchange),
            "withdrawal_test": await self._test_withdrawal(exchange, amount=10),
            "api_health": await self._check_api_health(exchange),
            "red_flags_detected": [],
            "risk_score": 0.0,  # 0-1, higher = riskier
        }
        
        # Check red flags
        for flag in self.RED_FLAGS:
            if await self._check_flag(exchange, flag):
                health["red_flags_detected"].append(flag)
                health["risk_score"] += 0.2
        
        # Overexposure check
        if health["our_exposure_pct"] > self.LIMITS["max_exposure_per_exchange_pct"]:
            health["red_flags_detected"].append("overexposed")
            health["risk_score"] += 0.3
        
        return health
    
    async def rebalance_exchange_exposure(self):
        """Move funds to maintain exposure limits."""
        exposures = {}
        for exchange in self.active_exchanges:
            exposures[exchange] = await self._get_exposure_pct(exchange)
        
        # Find overexposed exchanges
        overexposed = {k: v for k, v in exposures.items() 
                       if v > self.LIMITS["max_exposure_per_exchange_pct"]}
        
        for exchange, pct in overexposed.items():
            excess_pct = pct - self.LIMITS["max_exposure_per_exchange_pct"]
            target_exchange = min(exposures, key=exposures.get)
            
            # Withdraw excess from overexposed, deposit to underexposed
            amount_usd = excess_pct / 100 * await self._get_total_capital()
            await self._withdraw(exchange, amount_usd)
            await self._deposit(target_exchange, amount_usd)
```

### 6.4 Leverage Management

```python
class CryptoLeverageManager:
    """
    Crypto leverage is extreme (125x on Binance).
    Alpha Stack enforces conservative limits.
    """
    
    MAX_LEVERAGE_BY_REGIME = {
        "low_volatility": 3.0,     # BTC 30-day vol < 40%
        "normal": 2.0,              # BTC 30-day vol 40-80%
        "high_volatility": 1.0,     # BTC 30-day vol 80-120%
        "extreme_volatility": 0.0,  # BTC 30-day vol > 120% — no leverage
    }
    
    MAX_LEVERAGE_BY_ASSET = {
        "BTC": 3.0,
        "ETH": 2.5,
        "large_cap_alt": 2.0,      # SOL, ADA, DOT, etc.
        "mid_cap_alt": 1.0,        # Top 50-100
        "small_cap_alt": 0.0,      # Top 100+ — no leverage
        "meme_coin": 0.0,          # Never leverage meme coins
    }
    
    def get_max_leverage(self, asset: str, regime: str) -> float:
        asset_class = self._classify_asset(asset)
        return min(
            self.MAX_LEVERAGE_BY_REGIME[regime],
            self.MAX_LEVERAGE_BY_ASSET[asset_class]
        )
    
    def compute_liquidation_buffer(self, entry_price: float, leverage: float, 
                                     side: str) -> dict:
        """How far price can move before liquidation."""
        if side == "long":
            liq_price = entry_price * (1 - 1/leverage * 0.95)  # 95% of maintenance margin
            distance_pct = (entry_price - liq_price) / entry_price * 100
        else:
            liq_price = entry_price * (1 + 1/leverage * 0.95)
            distance_pct = (liq_price - entry_price) / entry_price * 100
        
        return {
            "entry_price": entry_price,
            "leverage": leverage,
            "liquidation_price": liq_price,
            "distance_to_liquidation_pct": distance_pct,
            "safe": distance_pct > 15,  # Need >15% buffer
            "recommendation": "safe" if distance_pct > 15 else 
                            "caution" if distance_pct > 8 else "too_risky",
        }
```

### 6.5 Smart Contract Risk Framework

```python
class SmartContractRiskManager:
    """
    DeFi interactions carry smart contract risk that has no traditional equivalent.
    """
    
    RISK_FACTORS = {
        "audit_count": {"weight": 0.20, "good": ">= 2 reputable audits"},
        "audit_recency": {"weight": 0.10, "good": "< 6 months since last audit"},
        "tvl_age": {"weight": 0.15, "good": "TVL > $100M for > 6 months"},
        "bug_bounty": {"weight": 0.10, "good": "Active bug bounty > $100K"},
        "upgrade_mechanism": {"weight": 0.15, "good": "Timelock + multisig governance"},
        "code_complexity": {"weight": 0.10, "good": "Simple, well-documented contracts"},
        "insurance_available": {"weight": 0.10, "good": "Nexus Mutual or similar coverage"},
        "incident_history": {"weight": 0.10, "good": "No exploits in 12+ months"},
    }
    
    def assess_protocol(self, protocol: str) -> dict:
        score = 0.0
        details = {}
        for factor, config in self.RISK_FACTORS.items():
            value = self._evaluate_factor(protocol, factor)
            score += value * config["weight"]
            details[factor] = {"value": value, "weight": config["weight"]}
        
        return {
            "protocol": protocol,
            "risk_score": 1 - score,  # 0 = safe, 1 = highest risk
            "risk_tier": "safe" if score > 0.8 else "moderate" if score > 0.6 else 
                        "elevated" if score > 0.4 else "high" if score > 0.2 else "extreme",
            "max_allocation_pct": score * 20,  # Max 20% even for safest protocols
            "details": details,
        }
```

### 6.6 Crypto Crisis Response Matrix

Derived from historical crypto crises:

| Crisis Type | Historical Example | Detection Signal | Response |
|-------------|-------------------|------------------|----------|
| **Exchange collapse** | FTX (Nov 2022) | Withdrawal delays, FTT-style token decline | Emergency withdrawal to self-custody |
| **Stablecoin depeg** | UST (May 2022) | Depeg > 2%, backing ratio declining | Exit to fiat or overcollateralized stables |
| **Leverage cascade** | Mar 2020 COVID crash | Funding extreme, OI spike, liquidation cascade | Reduce leverage, widen stops, add hedges |
| **DeFi exploit** | Wormhole, Ronin | Unusual contract activity, TVL sudden drop | Emergency withdrawal from protocol |
| **Regulatory shock** | China ban (May 2021) | News sentiment spike, exchange-specific outflows | Reduce exposure to affected jurisdictions |
| **Contagion** | 3AC/Celsius (Jun 2022) | Multiple entities showing stress, credit spreads widening | Systematic de-risk, avoid affected tokens |
| **Whale manipulation** | Elon tweets (2021) | Social mention spike, unusual whale activity | Tighten stops, reduce position size |

---

## 7. Crypto Portfolio Construction

### 7.1 Crypto Asset Classification

```python
CRYPTO_ASSET_CLASSES = {
    "store_of_value": {
        "assets": ["BTC"],
        "role": "Digital gold, inflation hedge, macro-driven",
        "correlation_to_btc": 1.0,
        "expected_vol_annual": 0.60,
        "max_allocation_pct": 40,
        "behavior": "Responds to macro (rates, DXY, ETF flows). Least volatile crypto.",
    },
    "smart_contract_platform": {
        "assets": ["ETH", "SOL", "ADA", "AVAX", "DOT", "NEAR"],
        "role": "Infrastructure layer, DeFi backbone",
        "correlation_to_btc": 0.75,
        "expected_vol_annual": 0.85,
        "max_allocation_pct": 30,
        "behavior": "BTC-beta. Outperforms in risk-on, underperforms in risk-off.",
    },
    "defi_token": {
        "assets": ["UNI", "AAVE", "MKR", "LDO", "PENDLE", "CRV"],
        "role": "Protocol governance, fee capture",
        "correlation_to_btc": 0.70,
        "expected_vol_annual": 1.00,
        "max_allocation_pct": 15,
        "behavior": "Revenue-driven. Sensitive to DeFi TVL and yield environment.",
    },
    "stablecoin": {
        "assets": ["USDT", "USDC", "DAI", "USDS"],
        "role": "Cash equivalent, dry powder, yield",
        "correlation_to_btc": 0.0,
        "expected_vol_annual": 0.01,
        "max_allocation_pct": 100,  # Can be 100% in defensive mode
        "behavior": "Pegged to USD. Use as safe haven during drawdowns.",
    },
    "meme_coin": {
        "assets": ["DOGE", "SHIB", "PEPE", "WIF", "BONK"],
        "role": "Pure speculation, narrative trading",
        "correlation_to_btc": 0.50,
        "expected_vol_annual": 2.00,
        "max_allocation_pct": 5,
        "behavior": "Sentiment-driven, extreme volatility, no fundamentals.",
    },
    "rwa_token": {
        "assets": ["ONDO", "MPL", "CFG", "TRU"],
        "role": "Real-world asset tokenization exposure",
        "correlation_to_btc": 0.40,
        "expected_vol_annual": 0.80,
        "max_allocation_pct": 10,
        "behavior": "New asset class. Growth driven by institutional adoption.",
    },
}
```

### 7.2 Correlation Dynamics

Crypto correlation is **regime-dependent**, not static:

| Regime | BTC-ALT Correlation | BTC-SPX Correlation | Strategy |
|--------|--------------------|--------------------|----------|
| **BTC Bull** | 0.50–0.70 (altcoins lag then catch up) | 0.30–0.50 | Long BTC + selective altcoins |
| **BTC Bear** | 0.85–0.95 (everything falls together) | 0.60–0.80 | Short or cash. No diversification benefit. |
| **BTC Choppy** | 0.40–0.60 (narrative-driven alt rotation) | 0.20–0.40 | Altcoin rotation, sector plays |
| **DeFi Summer** | 0.30–0.50 (DeFi decouples from BTC) | 0.10–0.30 | DeFi-focused, yield farming |
| **Macro Crisis** | 0.90+ (crypto = risk asset, all sold) | 0.90+ | Cash only. Everything correlates to 1. |

```python
class CryptoRegimeDetector:
    """
    Detects current crypto market regime to adjust portfolio.
    """
    
    REGIMES = {
        "btc_bull": {
            "conditions": ["btc_above_200dma", "funding_positive", "etf_inflows_positive"],
            "portfolio": {"BTC": 0.40, "ETH": 0.20, "L1s": 0.15, "DeFi": 0.10, "stable": 0.15},
        },
        "btc_bear": {
            "conditions": ["btc_below_200dma", "funding_negative", "exchange_inflows_rising"],
            "portfolio": {"BTC": 0.15, "ETH": 0.05, "L1s": 0.00, "DeFi": 0.00, "stable": 0.80},
        },
        "alt_season": {
            "conditions": ["btc_dominance_declining", "eth_btc_rising", "alt_volume_surge"],
            "portfolio": {"BTC": 0.25, "ETH": 0.25, "L1s": 0.25, "DeFi": 0.15, "stable": 0.10},
        },
        "defi_growth": {
            "conditions": ["tvl_rising", "dex_volume_rising", "yield_spreads_widening"],
            "portfolio": {"BTC": 0.25, "ETH": 0.20, "L1s": 0.10, "DeFi": 0.30, "stable": 0.15},
        },
        "risk_off": {
            "conditions": ["correlation_spike", "vix_rising", "funding_extreme_negative"],
            "portfolio": {"BTC": 0.10, "ETH": 0.00, "L1s": 0.00, "DeFi": 0.00, "stable": 0.90},
        },
    }
    
    def detect_regime(self) -> str:
        scores = {}
        for regime, config in self.REGIMES.items():
            conditions_met = sum(
                1 for c in config["conditions"] if self._check_condition(c)
            )
            scores[regime] = conditions_met / len(config["conditions"])
        
        return max(scores, key=scores.get)
```

### 7.3 Portfolio Rebalancing Rules

| Trigger | Action | Rationale |
|---------|--------|-----------|
| **Single asset > 40%** | Trim to 35% | Concentration risk |
| **Single asset < 5% of target** | Rebalance to target | Opportunity cost |
| **Total altcoin exposure > 50%** | Trim to 40% | BTC-beta risk |
| **Stablecoin < 10% in bear regime** | Raise to 30% | Defensive posture |
| **Meme coin > 5%** | Trim to 3% | Speculative cap |
| **30-day drift > 10%** | Rebalance | Maintain target allocation |
| **Regime change detected** | Full rebalance | Portfolio must match regime |

---

## 8. Crypto News and Sentiment

### 8.1 Sentiment Data Sources

```
┌───────────────────────────────────────────────────────────────────┐
│                 CRYPTO SENTIMENT PIPELINE                          │
│                                                                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐         │
│  │ Twitter/X│  │ Reddit   │  │ Telegram │  │ Discord  │         │
│  │ Mentions │  │ Sentiment│  │ Alpha    │  │ Community│         │
│  │ Velocity │  │ Analysis │  │ Groups   │  │ Signals  │         │
│  └─────┬────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘         │
│        └────────────┼─────────────┼──────────────┘                │
│                     │             │                                 │
│           ┌─────────▼─────────────▼─────────┐                     │
│           │     NLP PROCESSING ENGINE        │                     │
│           │  - Sentiment scoring (BERT/GPT)  │                     │
│           │  - Entity extraction             │                     │
│           │  - Narrative classification       │                     │
│           │  - Bot detection                 │                     │
│           └────────────────┬─────────────────┘                     │
│                            │                                       │
│           ┌────────────────▼─────────────────┐                     │
│           │     SENTIMENT COMPOSITE SCORE     │                     │
│           │  Social Volume + Sentiment +      │                     │
│           │  Influencer Signal + Fear/Greed   │                     │
│           └──────────────────────────────────┘                     │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────┐     │
│  │ ADDITIONAL SIGNALS                                        │     │
│  │  - Fear & Greed Index (alternative.me)                   │     │
│  │  - Google Trends (pytrends)                               │     │
│  │  - GitHub commit activity                                 │     │
│  │  - Token unlock schedules (tokenunlocks.app)              │     │
│  │  - Exchange listing announcements                         │     │
│  │  - Regulatory news feeds                                  │     │
│  └──────────────────────────────────────────────────────────┘     │
└───────────────────────────────────────────────────────────────────┘
```

### 8.2 Sentiment Scoring System

```python
class CryptoSentimentEngine:
    """
    Multi-source sentiment analysis for crypto assets.
    """
    
    COMPONENT_WEIGHTS = {
        "twitter_mention_velocity": 0.20,   # How fast mentions spike
        "twitter_sentiment_shift": 0.15,    # Sentiment direction change
        "reddit_sentiment": 0.15,           # r/cc, r/bitcoin, r/ethtrader
        "fear_greed_index": 0.12,           # Alternative.me index
        "google_trends": 0.10,              # Search interest
        "telegram_signal": 0.08,            # Alpha group activity
        "github_activity": 0.05,            # Dev health
        "token_unlock_pressure": 0.05,      # Supply catalyst
        "news_sentiment": 0.10,             # Major news outlets
    }
    
    async def compute_sentiment(self, asset: str) -> dict:
        scores = {}
        
        # Twitter/X mention velocity
        mentions_1h = await self._get_twitter_mentions(asset, hours=1)
        mentions_24h_avg = await self._get_twitter_mentions(asset, hours=24) / 24
        velocity_ratio = mentions_1h / max(mentions_24h_avg, 1)
        scores["twitter_mention_velocity"] = min(velocity_ratio / 5, 1.0) * 2 - 1  # -1 to 1
        
        # Reddit sentiment (VADER + transformer)
        reddit = await self._analyze_reddit(asset)
        scores["reddit_sentiment"] = reddit["compound_score"]  # -1 to 1
        
        # Fear & Greed Index
        fgi = await self._get_fear_greed()
        scores["fear_greed_index"] = (fgi["value"] - 50) / 50  # -1 to 1
        
        # Google Trends
        trends = await self._get_google_trends(asset)
        trend_acceleration = trends["ma7"] / max(trends["ma30"], 1) - 1
        scores["google_trends"] = max(min(trend_acceleration * 10, 1), -1)
        
        # Token unlock schedule
        unlocks = await self._get_upcoming_unlocks(asset)
        if unlocks and unlocks[0]["days_until"] < 7:
            supply_pct = unlocks[0]["supply_pct"]
            scores["token_unlock_pressure"] = -min(supply_pct / 5, 1.0)  # Bearish
        else:
            scores["token_unlock_pressure"] = 0.0
        
        # Composite
        composite = sum(
            scores.get(k, 0) * v for k, v in self.COMPONENT_WEIGHTS.items()
        )
        
        return {
            "asset": asset,
            "composite_sentiment": composite,  # -1 to 1
            "signal": "extreme_greed" if composite > 0.6 else
                     "greed" if composite > 0.3 else
                     "extreme_fear" if composite < -0.6 else
                     "fear" if composite < -0.3 else "neutral",
            "contrarian_signal": "sell" if composite > 0.6 else "buy" if composite < -0.6 else None,
            "components": scores,
            "velocity_alert": velocity_ratio > 3.0,  # 3x normal = attention spike
        }
```

### 8.3 Narrative Detection

```python
class NarrativeDetector:
    """
    Detects emerging narratives that drive altcoin rotation.
    
    Crypto narratives cycle: L1s → DeFi → NFTs → AI → RWA → Memes → ...
    Early narrative detection = 10-50x returns on the right tokens.
    """
    
    NARRATIVE_KEYWORDS = {
        "ai_crypto": ["AI", "artificial intelligence", "machine learning", "GPT", "agent"],
        "rwa": ["real world asset", "tokenization", "BlackRock", "BUIDL", "T-bill"],
        "layer2": ["L2", "rollup", "Base", "Arbitrum", "Optimism", "zkSync"],
        "defi_2_0": ["restaking", "Eigenlayer", "points", "airdrop", "yield"],
        "memecoin": ["meme", "dog", "cat", "pepe", "moon", "pump"],
        "depin": ["DePIN", "physical infrastructure", "Helium", "render"],
        "gaming": ["gaming", "metaverse", "play to earn", "NFT game"],
        "privacy": ["privacy", "Monero", "Zcash", "zero knowledge"],
    }
    
    async def detect_emerging_narratives(self) -> list:
        """Identify which narratives are gaining momentum."""
        narratives = []
        
        for narrative, keywords in self.NARRATIVE_KEYWORDS.items():
            # Social volume for narrative keywords
            social_vol = await self._aggregate_social_volume(keywords)
            social_vol_7d_change = await self._get_volume_change(keywords, days=7)
            
            # Performance of narrative basket
            basket_perf = await self._get_narrative_basket_performance(narrative)
            
            # Dev activity
            dev_trend = await self._get_narrative_dev_trend(narrative)
            
            score = (
                0.35 * social_vol_7d_change +  # Social momentum
                0.30 * basket_perf["7d_return"] +  # Price momentum
                0.20 * dev_trend +  # Fundamental health
                0.15 * (social_vol / self.baseline_social_vol)  # Relative attention
            )
            
            narratives.append({
                "narrative": narrative,
                "momentum_score": score,
                "social_volume_change_7d": social_vol_7d_change,
                "basket_return_7d": basket_perf["7d_return"],
                "top_tokens": basket_perf["top_tokens"],
                "stage": "emerging" if score > 0.5 and social_vol < self.baseline_social_vol * 2 
                        else "trending" if score > 0.3 else "mature" if score > 0 else "fading",
            })
        
        return sorted(narratives, key=lambda x: x["momentum_score"], reverse=True)
```

### 8.4 Fear & Greed Integration

```
Fear & Greed Index (alternative.me) → Crypto-specific behavior:

Extreme Fear (0-25):   Contrarian BUY signal. Capitulation.
Fear (25-45):          Cautious accumulation. Wider stops.
Neutral (45-55):       Normal operations.
Greed (55-75):         Tighten stops, reduce leverage.
Extreme Greed (75-100): Contrarian SELL signal. Take profits.

Key divergence: Price making new highs while F&G declining = distribution phase.
Key divergence: Price declining while F&G stabilizing = accumulation phase.
```

---

## 9. Staking and Yield Opportunities

### 9.1 Staking Architecture

```python
class StakingManager:
    """
    Manages staking positions across multiple protocols and chains.
    """
    
    STAKING_OPTIONS = {
        "ETH": {
            "native_staking": {
                "protocol": "ethereum_beacon_chain",
                "apy": 3.5,
                "lock_period": "variable (withdrawal queue)",
                "risk": "low",
                "min_stake": 32,  # For solo validator
            },
            "liquid_staking": {
                "protocol": "lido",
                "apy": 3.2,
                "token": "stETH",
                "lock_period": "none (liquid)",
                "risk": "low-medium",
                "smart_contract_risk": 0.15,
            },
            "restaking": {
                "protocol": "eigenlayer",
                "apy": 5.0,  # Base ETH staking + restaking rewards
                "token": "eETH",
                "lock_period": "variable",
                "risk": "medium",
                "smart_contract_risk": 0.25,
            },
        },
        "SOL": {
            "native_staking": {
                "protocol": "solana",
                "apy": 7.0,
                "lock_period": "~2-3 days (unstake)",
                "risk": "low",
            },
            "liquid_staking": {
                "protocol": "marinade",
                "apy": 6.8,
                "token": "mSOL",
                "lock_period": "none",
                "risk": "low-medium",
            },
        },
        "AVAX": {
            "native_staking": {
                "protocol": "avalanche",
                "apy": 8.0,
                "lock_period": "14 days minimum",
                "risk": "low",
            },
        },
    }
    
    def compute_risk_adjusted_yield(self, asset: str, method: str) -> dict:
        option = self.STAKING_OPTIONS[asset][method]
        sc_risk = option.get("smart_contract_risk", 0.05)
        slashing_risk = 0.02 if "native" in method else 0.01
        illiquidity_discount = 0.5 if option.get("lock_period") not in ["none", None] else 0
        
        risk_adjusted_apy = option["apy"] * (1 - sc_risk) * (1 - slashing_risk) - illiquidity_discount
        
        return {
            "asset": asset,
            "method": method,
            "nominal_apy": option["apy"],
            "risk_adjusted_apy": risk_adjusted_apy,
            "smart_contract_risk": sc_risk,
            "slashing_risk": slashing_risk,
            "liquidity": "liquid" if option.get("lock_period") in ["none", None] else "illiquid",
        }
```

### 9.2 Yield Strategy Matrix

| Strategy | APY Range | Risk Level | Capital Efficiency | Best For |
|----------|-----------|------------|-------------------|----------|
| **ETH liquid staking (stETH)** | 3-4% | Low | High (can use as collateral) | Core holdings |
| **SOL native staking** | 6-8% | Low | Medium | SOL positions |
| **Stablecoin lending (Aave)** | 3-8% | Low-Medium | High | Cash reserves |
| **Curve LP (stable pools)** | 5-15% | Medium | Medium | Stablecoin yield |
| **Pendle yield trading** | 10-30% | Medium-High | Medium | Yield speculation |
| **Eigenlayer restaking** | 5-10% | Medium | High | ETH holders |
| **Funding rate arbitrage** | 15-50% | Low-Medium | High | Market-neutral |
| **LP in volatile pairs** | 20-100%+ | High | Low (IL risk) | Yield farming |

### 9.3 Funding Rate Arbitrage (Deep Dive)

```python
class FundingArbitrageStrategy:
    """
    Market-neutral strategy: collect funding payments.
    
    When funding is positive (longs pay shorts):
    - Short perp (collect funding)
    - Long spot (delta neutral)
    
    Risk: Funding rate can flip. Liquidation if perp moves sharply.
    """
    
    async def find_opportunities(self, min_annualized_apy: float = 15) -> list:
        opportunities = []
        
        symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"]
        
        for symbol in symbols:
            funding = await self._get_avg_funding(symbol, hours=24)
            annualized = funding * 3 * 365  # 8h funding → annual
            
            if abs(annualized) < min_annualized_apy:
                continue
            
            if funding > 0:
                # Longs paying shorts → short perp + long spot
                strategy = "short_perp_long_spot"
            else:
                # Shorts paying longs → long perp + short spot (harder, needs margin)
                strategy = "long_perp_short_spot"
            
            opportunities.append({
                "symbol": symbol,
                "funding_rate_8h": funding,
                "annualized_apy": annualized * 100,
                "strategy": strategy,
                "estimated_daily_yield": abs(funding) * 3,  # 3 funding periods/day
                "risk_factors": {
                    "funding_flip_risk": funding < 0.0005,  # Close to neutral
                    "liquidation_risk": "low" if abs(annualized) < 30 else "medium",
                    "exchange_risk": "counterparty exposure",
                },
            })
        
        return sorted(opportunities, key=lambda x: x["annualized_apy"], reverse=True)
```

---

## 10. Crypto Tax Considerations

### 10.1 Tax Event Classification

| Event | Taxable? | Type | Notes |
|-------|----------|------|-------|
| **Buy crypto with fiat** | No | Acquisition | Cost basis established |
| **Sell crypto for fiat** | Yes | Capital gain/loss | (Sale price - cost basis) |
| **Trade crypto-to-crypto** | Yes | Capital gain/loss | Each trade is a taxable event |
| **Receive staking rewards** | Yes | Ordinary income | Taxed at FMV when received |
| **Receive airdrop** | Yes | Ordinary income | Taxed at FMV when received |
| **DeFi yield farming** | Yes | Ordinary income | Rewards taxed as income |
| **LP token minting** | Complex | Varies | Some jurisdictions treat as disposal |
| **LP token burning** | Complex | Varies | May trigger capital gains |
| **Borrowing against crypto** | No (usually) | Loan | Not a disposal, but collateral liquidation is |
| **Funding rate payments** | Yes | Income/expense | Depends on jurisdiction |
| **Futures P&L** | Yes | Capital gain/loss | May get favorable 60/40 treatment in US |
| **NFT purchase** | No | Acquisition | Cost basis established |
| **NFT sale** | Yes | Capital gain/loss | May be collectible rate (28% in US) |

### 10.2 Tax-Loss Harvesting Integration

```python
class CryptoTaxOptimizer:
    """
    Integrates tax considerations into trading decisions.
    Note: No wash-sale rule for crypto in the US (as of 2026),
    but this may change. Always verify current law.
    """
    
    def __init__(self, jurisdiction: str = "US"):
        self.jurisdiction = jurisdiction
        self.tax_lots = []  # FIFO, LIFO, or specific identification
    
    def should_harvest_loss(self, position: dict, current_price: float) -> dict:
        """Check if closing position would generate a tax-loss benefit."""
        unrealized_loss = (current_price - position["cost_basis"]) * position["quantity"]
        
        if unrealized_loss >= 0:
            return {"harvest": False, "reason": "no_loss"}
        
        # Estimate tax benefit
        marginal_rate = self._get_marginal_rate()
        tax_benefit = abs(unrealized_loss) * marginal_rate
        
        # Consider transaction costs
        tx_cost = position["quantity"] * current_price * 0.001  # 0.1% fee
        
        net_benefit = tax_benefit - tx_cost
        
        return {
            "harvest": net_benefit > 0,
            "unrealized_loss": unrealized_loss,
            "tax_benefit": tax_benefit,
            "transaction_cost": tx_cost,
            "net_benefit": net_benefit,
            "can_repurchase_immediately": self.jurisdiction == "US",  # No wash-sale for crypto (check current law)
        }
    
    def optimize_lot_selection(self, sell_quantity: float, lots: list) -> list:
        """Choose which tax lots to sell for optimal tax treatment."""
        if self.jurisdiction == "US":
            # Specific identification: sell highest cost basis first (minimize gains)
            sorted_lots = sorted(lots, key=lambda x: x["cost_basis"], reverse=True)
        else:
            # FIFO: sell oldest first
            sorted_lots = sorted(lots, key=lambda x: x["acquisition_date"])
        
        selected = []
        remaining = sell_quantity
        for lot in sorted_lots:
            if remaining <= 0:
                break
            qty = min(lot["quantity"], remaining)
            selected.append({**lot, "sell_quantity": qty})
            remaining -= qty
        
        return selected
```

### 10.3 Jurisdiction-Specific Notes

| Jurisdiction | Key Rules | Crypto-to-Crypto | Staking Income | Loss Offset |
|-------------|-----------|-------------------|----------------|-------------|
| **US** | Capital gains + income | Taxable event | Ordinary income | Up to $3K/year + unlimited against gains |
| **UK** | Capital gains tax | Taxable event | Income tax | Against capital gains |
| **EU (varies)** | Varies by country | Usually taxable | Usually income | Varies |
| **Germany** | Tax-free after 1yr hold | Taxable (resets clock) | Income tax | Against crypto gains |
| **Singapore** | No capital gains | N/A | N/A | N/A |
| **UAE** | No income/capital gains | N/A | N/A | N/A |

**Important:** Always consult a tax professional. Laws change frequently.

---

## 11. Future: Tokenized RWA, CBDCs, Cross-Chain

### 11.1 Tokenized Real-World Assets (RWA)

The RWA market is **$35.7B** as of July 2026 and accelerating. Alpha Stack must be positioned to trade these assets.

```
Current RWA Landscape:
┌─────────────────────────────────────────────────────┐
│                 TOKENIZED ASSETS                      │
│                                                       │
│  Government Securities ($10B+)                        │
│  ├── BlackRock BUIDL: $2.9B (+28% monthly growth)   │
│  ├── Hashnote USYC: $3.1B                            │
│  ├── Ondo USDY: $2.2B                                │
│  └── Franklin BENJI: $1.6B                           │
│                                                       │
│  Tokenized Stocks (exploding)                         │
│  ├── FIGon (Robinhood): $1.2B (+2,051%)              │
│  ├── LLYon (Eli Lilly): $119M                        │
│  └── Dozens on Hyperliquid + Robinhood               │
│                                                       │
│  Tokenized Commodities                                │
│  ├── Tether Gold (XAUT): $2.5B                       │
│  └── PAX Gold (PAXG): $1.8B                          │
│                                                       │
│  Tokenized Credit                                     │
│  ├── Janus Henderson JAAA: $689M                     │
│  └── Multiple strategies emerging ($500M+)           │
│                                                       │
│  Total: $35.7B → Projected $2-16T by 2030           │
└─────────────────────────────────────────────────────┘
```

**Integration Plan:**

```python
class RWATokenManager:
    """
    Manages tokenized real-world asset positions.
    """
    
    SUPPORTED_RWA = {
        "BUIDL": {
            "issuer": "BlackRock (via Securitize)",
            "asset": "US Treasury Bills",
            "chain": ["ethereum"],
            "apy": 4.5,
            "liquidity": "medium",
            "min_investment": 1,
            "settlement": "T+0 (on-chain)",
        },
        "USDY": {
            "issuer": "Ondo Finance",
            "asset": "US Treasury + Bank Deposit",
            "chain": ["ethereum", "solana", "mantle"],
            "apy": 5.0,
            "liquidity": "medium",
            "min_investment": 500,
        },
        "XAUT": {
            "issuer": "Tether",
            "asset": "Physical Gold",
            "chain": ["ethereum"],
            "apy": 0,  # No yield, just price appreciation
            "liquidity": "high",
            "min_investment": 1,
        },
        "FIGon": {
            "issuer": "Robinhood (tokenized)",
            "asset": "Robinhood stock (HOOD)",
            "chain": ["arbitrum"],
            "apy": 0,
            "liquidity": "high (Hyperliquid)",
            "min_investment": 1,
        },
    }
    
    async def get_rwa_opportunities(self) -> list:
        """Fetch and rank RWA trading opportunities."""
        opportunities = []
        for token, config in self.SUPPORTED_RWA.items():
            price = await self._get_price(token)
            volume = await self._get_volume_24h(token)
            premium_to_nav = await self._compute_premium(token)
            
            opportunities.append({
                "token": token,
                "price": price,
                "volume_24h": volume,
                "premium_to_nav": premium_to_nav,
                "apy": config["apy"],
                "liquidity": config["liquidity"],
                "discount_signal": premium_to_nav < -0.02,  # Trading below NAV
            })
        
        return opportunities
```

### 11.2 CBDC Integration Readiness

CBDCs will rewire forex and create new trading opportunities:

| CBDC | Status (2026) | Alpha Stack Integration |
|------|--------------|------------------------|
| **e-CNY (Digital Yuan)** | Live, 260M+ wallets | Monitor cross-border flows via mBridge |
| **Digital Euro** | Expected 2028-2029 | Design architecture for EUR-CBDC settlement |
| **Digital Rupee** | Pilot (wholesale + retail) | Watch for INR crypto pair impact |
| **Drex (Digital Real)** | Advanced pilot | Smart contract integration potential |

**CBDC Impact on Crypto Trading:**
- Instant settlement → reduced counterparty risk
- 24/7 forex markets → eliminates weekend gaps
- Programmable money → conditional execution
- Cross-border CBDC corridors → new arbitrage opportunities

### 11.3 Cross-Chain Architecture

```python
class CrossChainRouter:
    """
    Routes trades across multiple blockchains.
    Critical for accessing liquidity wherever it exists.
    """
    
    SUPPORTED_CHAINS = {
        "ethereum": {"finality_seconds": 12, "gas_model": "EIP-1559"},
        "arbitrum": {"finality_seconds": 1, "gas_model": "L2"},
        "base": {"finality_seconds": 2, "gas_model": "L2"},
        "optimism": {"finality_seconds": 2, "gas_model": "L2"},
        "solana": {"finality_seconds": 0.4, "gas_model": "priority_fee"},
        "avalanche": {"finality_seconds": 1, "gas_model": "dynamic"},
        "polygon": {"finality_seconds": 2, "gas_model": "EIP-1559"},
    }
    
    INTENT_PROTOCOLS = {
        "across": {"chains": ["ethereum", "arbitrum", "base", "optimism", "polygon"]},
        "jupiter": {"chains": ["solana"]},
        "li_fi": {"chains": ["ethereum", "arbitrum", "base", "optimism", "polygon", "avalanche"]},
        "socket": {"chains": ["most_evm"]},
    }
    
    async def route_swap(self, from_token, to_token, amount, from_chain=None) -> dict:
        """Find best execution across chains and DEXs."""
        routes = []
        
        # Check same-chain DEX options
        for dex in self._get_dexs_on_chain(from_chain):
            quote = await self._get_quote(dex, from_token, to_token, amount)
            routes.append({**quote, "chain": from_chain, "type": "same_chain"})
        
        # Check cross-chain options
        for bridge, config in self.INTENT_PROTOCOLS.items():
            if from_chain in config["chains"]:
                for target_chain in config["chains"]:
                    if target_chain != from_chain:
                        quote = await self._get_bridge_quote(
                            bridge, from_token, to_token, amount, from_chain, target_chain
                        )
                        routes.append({**quote, "type": "cross_chain", "bridge": bridge})
        
        # Rank by effective output (after fees, slippage, bridge costs)
        return sorted(routes, key=lambda x: x["output_amount"], reverse=True)[0]
```

### 11.4 MEV Protection

```python
class MEVProtection:
    """
    Protects against Maximal Extractable Value (MEV) attacks.
    MEV = profit block producers extract by reordering/inserting transactions.
    """
    
    PROTECTION_METHODS = {
        "flashbots_protect": {
            "chain": "ethereum",
            "description": "Private mempool, no front-running",
            "endpoint": "https://rpc.flashbots.net",
        },
        "mev_blocker": {
            "chain": "ethereum",
            "description": "Encrypted mempool via MEV Blocker",
            "endpoint": "https://rpc.mevblocker.io",
        },
        "jupiter_validator": {
            "chain": "solana",
            "description": "Jupiter's MEV protection on swaps",
            "integrated": True,
        },
    }
    
    async def send_protected_transaction(self, tx: dict, chain: str) -> dict:
        """Route transaction through MEV-protected channel."""
        method = self.PROTECTION_METHODS.get(chain)
        if not method:
            # Fall back to standard submission with higher gas
            return await self._send_with_priority_fee(tx, chain)
        
        return await self._send_via_protected_rpc(tx, method["endpoint"])
```

---

## 12. Integration with Alpha Stack Engine

### 12.1 Signal Flow Integration

The crypto-specific signals feed into the Alpha Stack 16-step pipeline at specific points:

```
ALPHA STACK 16-STEP PIPELINE — CRYPTO INTEGRATION POINTS

Step 1 (Fundamental Analysis):
  ├── Traditional: Economic data, central bank policy
  └── CRYPTO ADD: On-chain metrics (MVRV, NVT, SOPR)
                   Exchange flows (net inflow/outflow)
                   Whale accumulation patterns
                   Token unlock schedule

Step 2 (Bias Determination):
  ├── Traditional: Macro bias from DXY, yields
  └── CRYPTO ADD: Funding rate bias (long/short crowding)
                   Crypto regime detection (bull/bear/alt_season)
                   Fear & Greed index

Step 3 (Session Analysis):
  ├── Traditional: London/NY/Asian session characteristics
  └── CRYPTO ADD: 24/7 session mapping
                   Weekend liquidity profile
                   Exchange-specific activity windows

Step 4 (Market Structure):
  ├── Traditional: SMC, order blocks, FVGs
  └── CRYPTO ADD: Liquidation cascade levels
                   OI-weighted support/resistance
                   Funding rate equilibrium zones

Step 9 (Confluence):
  ├── Traditional: Multi-factor confluence scoring
  └── CRYPTO ADD: On-chain signal composite (weight: 30%)
                   Derivatives signal composite (weight: 25%)
                   Sentiment signal composite (weight: 20%)
                   DeFi activity signals (weight: 15%)
                   Technical signals (weight: 10%)

Step 11 (Position Sizing):
  ├── Traditional: Kelly criterion, fixed risk %
  └── CRYPTO ADD: Leverage limits per asset class
                   Exchange exposure limits
                   Smart contract exposure limits

Step 12 (Stop Loss):
  ├── Traditional: ATR-based, structure-based
  └── CRYPTO ADD: Liquidation distance buffer
                   Funding rate change stops
                   Stablecoin depeg stops
```

### 12.2 Crypto Data Schema for Alpha Stack

```python
# Unified crypto signal object that feeds into Alpha Stack
@dataclass
class CryptoSignal:
    # Standard Alpha Stack fields
    pair: str                    # e.g., "BTC/USDT"
    direction: str               # "long" | "short"
    timeframe: str               # "1h" | "4h" | "1d"
    confluence_score: float      # 0-1
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_reward: float
    
    # Crypto-specific fields
    on_chain_score: float        # -1 to +1 (composite on-chain)
    funding_rate: float          # Current funding rate
    funding_rate_signal: str     # "overcrowded_long" | "neutral" | etc.
    open_interest_change: float  # % change in OI
    liquidation_risk: str        # "low" | "medium" | "high"
    sentiment_score: float       # -1 to +1 (composite sentiment)
    fear_greed: int              # 0-100
    whale_activity: str          # "accumulating" | "distributing" | "neutral"
    exchange_flow: str           # "net_inflow" | "net_outflow" | "neutral"
    defi_signal: str             # "tvl_growing" | "tvl_declining" | "neutral"
    regime: str                  # "btc_bull" | "btc_bear" | "alt_season" | "risk_off"
    exchange: str                # Execution venue
    leverage: float              # Recommended leverage for this trade
    tax_lot_impact: dict         # Tax implications of this trade
```

---

## 13. Implementation Roadmap

### Phase 1: Foundation (Weeks 1-4)

- [ ] CCXT integration for Binance + Bybit (testnet)
- [ ] WebSocket real-time data feeds
- [ ] Basic on-chain data pipeline (DefiLlama + CryptoQuant free tier)
- [ ] Funding rate and OI data collection
- [ ] Crypto circuit breaker implementation
- [ ] Exchange risk manager (basic exposure limits)
- [ ] Database schema for crypto-specific data

### Phase 2: Indicators & Signals (Weeks 5-8)

- [ ] MVRV, NVT, SOPR calculators
- [ ] Funding rate analyzer (multi-exchange)
- [ ] Liquidation cascade mapper
- [ ] On-chain signal composite engine
- [ ] Social sentiment pipeline (Twitter + Reddit)
- [ ] Fear & Greed integration
- [ ] Crypto indicator composite scoring

### Phase 3: DeFi Integration (Weeks 9-12)

- [ ] DEX data pipeline (Uniswap, Curve, Jupiter)
- [ ] Yield farming opportunity scanner
- [ ] Smart contract risk framework
- [ ] LP monitoring system
- [ ] DeFi liquidation monitor
- [ ] Cross-chain router (basic: Ethereum + Solana)

### Phase 4: Advanced Features (Weeks 13-16)

- [ ] Narrative detection engine
- [ ] Token unlock schedule integration
- [ ] Staking manager
- [ ] Funding rate arbitrage strategy
- [ ] Tax optimization module
- [ ] Portfolio regime-based rebalancing
- [ ] MEV protection integration

### Phase 5: RWA & Future-Proofing (Weeks 17-20)

- [ ] Tokenized asset data feeds (RWA.xyz)
- [ ] RWA trading integration (BUIDL, USDY, XAUT)
- [ ] Cross-chain execution routing
- [ ] CBDC readiness (architecture only — no live CBDCs to connect yet)
- [ ] Hyperliquid integration for tokenized stocks
- [ ] Agent-friendly API endpoints

---

## Appendix A: Free API Endpoints

| Service | Endpoint | Auth | Rate Limit |
|---------|----------|------|------------|
| DefiLlama | `https://api.llama.fi/` | None | Generous |
| Binance Futures | `https://fapi.binance.com/fapi/v1/` | None (market data) | 1200/min |
| Bybit | `https://api.bybit.com/v5/market/` | None (market data) | 600/min |
| CryptoQuant | `https://api.cryptoquant.com/v1/` | Free API key | 100/day |
| Glassnode | `https://api.glassnode.com/v1/metrics/` | Free API key | Limited |
| Dune Analytics | `https://api.dune.com/api/v1/` | Free API key | Limited queries |
| Etherscan | `https://api.etherscan.io/api` | Free API key | 5/sec |
| GitHub | `https://api.github.com/` | Free token | 5000/hr |
| Google Trends | `pytrends` library | None | Unofficial |
| Alternative.me | `https://api.alternative.me/fng/` | None | Generous |
| CoinGecko | `https://api.coingecko.com/api/v3/` | None (free) | 10-50/min |

## Appendix B: Key Metrics Quick Reference

```
ON-CHAIN:
  MVRV Z-Score > 7     → CYCLE TOP (sell)
  MVRV Z-Score < 0     → CYCLE BOTTOM (buy)
  SOPR < 1 (extended)  → CAPITULATION (buy)
  Exchange net outflow  → BULLISH (supply squeeze)
  Exchange net inflow   → BEARISH (sell pressure)

DERIVATIVES:
  Funding > 0.1%/8h    → OVERCROWDED LONGS (caution)
  Funding > 0.3%/8h    → EXTREME GREED (sell signal)
  Funding < -0.1%/8h   → OVERCROWDED SHORTS (bounce)
  OI rising + price flat → BREAKOUT IMMINENT
  Liquidation cascade   → PRICE MAGNET

SENTIMENT:
  Fear & Greed < 20    → EXTREME FEAR (contrarian buy)
  Fear & Greed > 80    → EXTREME GREED (contrarian sell)
  Social velocity 3x+  → ATTENTION SPIKE (early momentum)
  Narrative emerging    → ROTATION OPPORTUNITY

VALUATION:
  NVT > 150            → OVERVALUED relative to usage
  NVT < 30             → UNDERVALUED relative to usage
  Stock-to-Flow target → Long-term fair value estimate
```

---

*Document maintained by: Alpha Stack Crypto Integration Division*  
*Review cadence: Monthly, or after major market events*  
*Next review: 2026-08-11*  
*Dependencies: architecture_trading_engine.md, architecture_pair_strategy.md*
