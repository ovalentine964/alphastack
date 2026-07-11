# Alpha Stack — Data Sources & Feeds Research

> **Last updated:** 2026-07-11  
> **Context:** Building a trading system with ~$7 starting capital. Prioritize free tiers, scale with revenue.

---

## 1. Economic Calendar Data

Economic events (NFP, CPI, FOMC, GDP) drive massive volatility. Having calendar awareness is critical for risk management and event-driven strategies.

| Source | Access | Cost | Data Quality | Programmatic Parsing |
|--------|--------|------|-------------|---------------------|
| **ForexFactory** | Web scraping (HTML) | Free | ⭐⭐⭐⭐⭐ Gold standard for retail | Parse HTML tables; JSON embedded in page |
| **Investing.com** | Web scraping | Free | ⭐⭐⭐⭐ Comprehensive, global | Heavier JS rendering; needs headless browser or careful parsing |
| **MQL5 Calendar** | Built into MT5 | Free (with MT5) | ⭐⭐⭐⭐ Integrated with terminal | Native MQL5 functions; Python via MetaTrader5 lib |
| **Trading Economics** | REST API | Free: limited; $20+/mo for API | ⭐⭐⭐⭐⭐ 20M+ indicators, 196 countries | Clean JSON API; best for programmatic use |
| **TradingView Calendar** | Web only | Free | ⭐⭐⭐⭐ Good UI, real-time | No official API; scraping possible but ToS-restricted |

### Recommended Approach
- **Primary:** MQL5 calendar (built into MT5, zero cost, structured data)
- **Supplement:** ForexFactory scraping for additional events and community sentiment
- **Upgrade path:** Trading Economics API ($20/mo) when capital allows — cleanest API access

### Key Considerations
- **Impact levels:** All sources classify events as Low/Medium/High impact — use this to filter
- **Parsing strategy:** ForexFactory embeds event data as JSON in the page HTML; can be parsed with `BeautifulSoup` + `json`
- **Latency:** Calendar data is scheduled (known in advance), so latency is not critical — fetch once daily

---

## 2. News & Sentiment Data

### Tier 1: Premium (Expensive)

| Source | Cost | Latency | Use Case |
|--------|------|---------|----------|
| **Reuters Eikon** | $1,000+/mo | Real-time | Institutional-grade; overkill for Alpha Stack |
| **Bloomberg Terminal** | $24,000/yr | Real-time | Same — not viable at current scale |
| **Refinitiv** | $500+/mo | Real-time | News + sentiment feeds; enterprise only |

### Tier 2: Affordable APIs

| Source | Free Tier | Paid | Latency | Notes |
|--------|-----------|------|---------|-------|
| **NewsAPI.org** | 100 req/day, 24h delay | $449/mo (Business) | Dev: delayed; Paid: real-time | ⚠️ Free tier is development-only (24h article delay). NOT for production trading signals |
| **GNews** | 100 req/day | ~$50/mo | Near real-time | Simpler than NewsAPI; good for basic news feeds |
| **NewsData.io** | 200 credits/day | $49/mo | Real-time | 10+ year archive; sentiment support on paid |
| **NewsCatcher API** | 1,000 req/month | $50/mo | Real-time | Open-source alternative; NER and sentiment |

### Tier 3: Crypto-Specific News

| Source | Access | Cost | Notes |
|--------|--------|------|-------|
| **CoinDesk RSS/Scraping** | RSS feeds | Free | Major crypto news; RSS is reliable |
| **The Block** | RSS + scraping | Free (basic) | Research-heavy; good for on-chain narratives |
| **CryptoCompare News** | API | Free: 100K calls/mo | Aggregated crypto news with social data |
| **Messari** | API | Free: 200 RPM | Governance, research reports; $30/mo for full API |

### Tier 4: Social Sentiment

| Source | Access | Cost | Notes |
|--------|--------|------|-------|
| **Reddit API** | PRAW (Python) | Free (with limits) | 100 req/min; r/wallstreetbets, r/cryptocurrency sentiment |
| **Twitter/X API** | API v2 | Free: 1,500 tweets/mo read; $100/mo Basic | ⚠️ Free tier extremely limited; Basic needed for useful volume |
| **Telegram Monitoring** | Telethon/Pyrogram | Free (user account) | Monitor crypto alpha groups; rate limits on user accounts |
| **StockTwits API** | REST | Free | Sentiment for stocks/crypto; limited but zero cost |

### Recommended Approach
- **Phase 1 (Free):** CoinDesk RSS + Reddit PRAW + CryptoCompare News API + StockTwits
- **Phase 2 ($50/mo):** Add NewsData.io or GNews for broader financial news
- **Phase 3 ($100+/mo):** Twitter/X Basic API for real-time social sentiment

### Sentiment Analysis Strategy
- Use lightweight NLP (VADER, TextBlob) for initial sentiment scoring
- LLM-based sentiment (your existing MIMO setup) for nuanced analysis of key headlines
- Aggregate sentiment scores across sources into a composite signal

---

## 3. Market Data Feeds

### Forex & Equities

| Source | Free Tier | Paid | Real-time? | Best For |
|--------|-----------|------|-----------|----------|
| **MT5 Built-in** | Full OHLCV + tick | Included with broker | Real-time (broker feed) | ⭐ Primary for forex/CFDs — use this first |
| **Yahoo Finance** | Via `yfinance` lib | Free | 15-min delayed (US equities) | Historical data, backtesting |
| **Alpha Vantage** | 25 calls/day | $49.99/mo | 1-min delay on free | ⚠️ Free tier severely limited (25 calls/day) |
| **Twelve Data** | 800 calls/day, 8/min | $29/mo | Real-time on paid | Better free tier than Alpha Vantage |
| **Polygon.io** | 5 calls/min | $199/mo | WebSocket real-time | Production-grade; expensive for Alpha Stack |
| **Financial Modeling Prep** | 250 calls/day | $19/mo | Real-time | Good for fundamentals data |

### Crypto Market Data

| Source | Free Tier | Paid | Assets | Best For |
|--------|-----------|------|--------|----------|
| **CoinGecko** | 10K calls/mo (Demo) | $29/mo | 17,400+ tokens, 1,700+ exchanges | ⭐ Best free tier for crypto |
| **CoinMarketCap** | 15K credits/mo | $29/mo | 48M+ assets | General-purpose; CMC ecosystem |
| **CryptoCompare** | 100K calls/mo | ~$80/mo | 7,000+ | Social analytics; research |
| **Messari** | 200 RPM | $30/mo | 40,000+ | Governance, research |
| **Binance API** | Unlimited (no key) | Free | All Binance pairs | ⭐ Direct exchange data; lowest latency for crypto |
| **Bybit API** | Unlimited | Free | All Bybit pairs | Good alternative; no key needed for market data |

### Real-time vs Delayed — Cost Analysis

| Data Type | Latency | Cost Range | Alpha Stack Viability |
|-----------|---------|------------|----------------------|
| Historical OHLCV | N/A (historical) | Free (most sources) | ✅ Use freely |
| 15-min delayed | 15 min | Free (Yahoo, etc.) | ✅ Fine for swing/position trading |
| 1-min bars | ~1 min | $20-50/mo | ⚠️ Add when needed |
| Real-time tick | <1 sec | $100-500/mo | ❌ Not needed at $7 capital |
| WebSocket streaming | Real-time | $200+/mo | ❌ Overkill for now |

### Recommended Approach
- **Forex/CFDs:** MT5 built-in feeds (zero additional cost)
- **Crypto:** Binance/Bybit free APIs (real-time, no cost) + CoinGecko for market overview
- **Equities (if needed):** Twelve Data free tier (800 calls/day) — best free option
- **Historical backtesting:** `yfinance` for equities, CoinGecko/Binance for crypto

---

## 4. On-Chain Data (Crypto)

On-chain data provides alpha that price data alone cannot — whale movements, exchange flows, network health.

### Major Providers

| Provider | Free Tier | Paid | Key Metrics | Latency |
|----------|-----------|------|-------------|---------|
| **Glassnode** | Limited metrics (1yr resolution) | $29/mo (Standard) | Exchange flow, whale tracking, SOPR, NVT | 10-min to 1hr |
| **Nansen** | Very limited | $150/mo (Lite) | Smart money tracking, wallet labels | Near real-time |
| **Dune Analytics** | Unlimited queries (community) | $349/mo (Plus) | Custom SQL queries on blockchain data | Depends on query |
| **Etherscan API** | 5 calls/sec (free) | $199/mo | Address tracking, tx history, gas | Real-time |
| **DefiLlama** | Fully free | N/A | TVL, yields, DeFi protocol data | Hourly updates |
| **Blockchain.com API** | Free (rate limited) | Custom | BTC address/tx data | Real-time |

### Key On-Chain Metrics for Trading

| Metric | What It Signals | Source |
|--------|----------------|--------|
| **Exchange Net Flow** | Whale depositing → sell pressure; withdrawing → accumulation | Glassnode, CryptoQuant |
| **Active Addresses** | Network health, adoption trends | Glassnode, Dune |
| **Hash Rate** | Miner confidence (BTC) | Blockchain.com, Glassnode |
| **Stablecoin Supply Ratio** | Buying power on sidelines | Glassnode, CryptoQuant |
| **Funding Rates** | Leverage sentiment (perps) | Binance/Bybit API directly |
| **Liquidation Data** | Cascade risk | Coinglass (free tier available) |
| **Whale Wallet Tracking** | Large holder accumulation/distribution | Nansen (paid), Etherscan (manual) |

### Recommended Approach
- **Phase 1 (Free):** DefiLlama (DeFi metrics) + Binance/Bybit funding rates + Coinglass liquidations + Etherscan free API
- **Phase 2 ($29/mo):** Glassnode Standard — unlocks exchange flows, SOPR, NVT, whale metrics
- **Phase 3 ($150/mo):** Nansen for smart money tracking (if crypto becomes primary focus)

---

## 5. Alternative Data

Non-traditional data sources that can provide edge before price moves.

| Source | Access | Cost | Signal Type | Implementation |
|--------|--------|------|------------|----------------|
| **Google Trends** | `pytrends` lib | Free | Search interest spikes → narrative momentum | Python library; no API key needed |
| **GitHub Activity** | GitHub API | Free (5K req/hr) | Dev activity → project health signals | Track commits, stars, forks for crypto projects |
| **App Store Rankings** | App Annie / data.ai | $$$$ (enterprise) | App adoption trends | ❌ Too expensive; scrape Apple/Google store pages |
| **Web Traffic** | SimilarWeb API | $$$$ (enterprise) | Website traffic → user growth | ❌ Too expensive; use Alexa rank as proxy (free) |
| **Fear & Greed Index** | alternative.me API | Free | Market sentiment composite | Simple JSON API; good for crypto |
| **Crypto Social Volume** | LunarCrush | Free tier (limited) | Social mentions, influencer activity | Galaxy Score, Alt Rank metrics |
| **Funding Rate Arbitrage** | Exchange APIs | Free | Perpetual futures sentiment | Direct from Binance/Bybit APIs |

### Recommended Approach
- **Always on:** Google Trends (`pytrends`), Fear & Greed Index, GitHub activity tracking
- **Add when useful:** LunarCrush social data, funding rates from exchanges
- **Skip for now:** SimilarWeb, App Annie (too expensive, minimal edge vs. cost)

---

## 6. Data Quality & Costs Summary

### Free Tier Comparison

| Provider | Daily/Monthly Limit | Key Limitation | Quality |
|----------|-------------------|----------------|---------|
| CoinGecko Demo | 10K calls/mo | No WebSocket, basic endpoints | ⭐⭐⭐⭐ |
| CoinMarketCap | 15K credits/mo | Credit-based counting | ⭐⭐⭐⭐ |
| CryptoCompare | 100K calls/mo | Limited historical depth | ⭐⭐⭐⭐ |
| Twelve Data | 800 calls/day | 8 calls/min rate limit | ⭐⭐⭐⭐ |
| Alpha Vantage | 25 calls/day | Almost unusable free | ⭐⭐⭐ |
| NewsAPI.org | 100 req/day | 24h article delay (dev only) | ⭐⭐ |
| Reddit API | 100 req/min | PRAW library | ⭐⭐⭐⭐ |
| Etherscan | 5 calls/sec | Limited without paid key | ⭐⭐⭐⭐ |
| DefiLlama | Unlimited | DeFi only | ⭐⭐⭐⭐⭐ |
| Binance/Bybit | Unlimited | Crypto only | ⭐⭐⭐⭐⭐ |
| MT5 Built-in | Unlimited | Forex/CFDs only | ⭐⭐⭐⭐⭐ |

### Paid Tier Cost Tiers

| Budget | What You Get |
|--------|-------------|
| **$0** | MT5 (forex), Binance/Bybit (crypto), CoinGecko/CMC (overview), DefiLlama (DeFi), Reddit/GitHub (social) |
| **$50/mo** | + Glassnode Standard ($29), + Twelve Data Pro ($29) |
| **$100/mo** | + NewsData.io ($49), + CryptoCompare paid |
| **$200/mo** | + Polygon.io ($199) or Nansen ($150) |

### Reliability & Uptime Notes
- **Exchange APIs (Binance/Bybit):** 99.9%+ uptime; rate limits are generous
- **CoinGecko/CMC:** Occasional rate limit issues under heavy load
- **Free news APIs:** Unreliable for production; treat as supplementary
- **MT5:** Broker-dependent; varies by broker quality
- **Glassnode:** High quality but occasional data lag (10-60 min)

---

## 7. Recommended Data Stack by Capital Stage

### 🟢 Stage 1: $7 Capital (Current) — $0 Data Cost

| Data Type | Source | Notes |
|-----------|--------|-------|
| **OHLCV (Forex)** | MT5 built-in | Broker feed; real-time |
| **OHLCV (Crypto)** | Binance/Bybit API | Real-time; no key needed |
| **Market Overview** | CoinGecko Demo API | 10K calls/mo; prices, market cap |
| **DeFi Metrics** | DefiLlama | TVL, yields — fully free |
| **Funding Rates** | Binance/Bybit API | Perpetual futures sentiment |
| **Liquidations** | Coinglass | Free tier; liquidation heatmaps |
| **Economic Calendar** | MQL5 Calendar (MT5) | Built into terminal |
| **News (Crypto)** | CoinDesk RSS + CryptoCompare API | 100K calls/mo free |
| **News (General)** | RSS aggregation (DIY) | Reuters, BBC, FT RSS feeds |
| **Social Sentiment** | Reddit PRAW + StockTwits | Free APIs |
| **Fear & Greed** | alternative.me API | Simple JSON endpoint |
| **Search Trends** | Google Trends (pytrends) | Free Python library |
| **Dev Activity** | GitHub API | Track crypto project commits |

**Total cost: $0** — Everything uses free tiers or built-in broker data.

### 🟡 Stage 2: ~$100 Capital — ~$30/mo Data Budget

Add:
- **Glassnode Standard ($29/mo):** Exchange flows, whale metrics, SOPR, NVT — huge edge for crypto
- **Twelve Data Pro ($29/mo):** Real-time stock data if expanding beyond crypto

### 🟠 Stage 3: ~$1,000 Capital — ~$100/mo Data Budget

Add:
- **NewsData.io ($49/mo):** Real-time financial news with sentiment
- **CryptoCompare paid (~$80/mo):** Deeper historical data, social analytics
- **Polygon.io Starter ($29/mo):** Real-time US equities if needed

### 🔴 Stage 4: ~$10,000+ Capital — ~$300/mo Data Budget

Add:
- **Nansen ($150/mo):** Smart money tracking, wallet labels
- **Polygon.io Pro ($199/mo):** WebSocket streaming, minute-level data
- **Twitter/X Basic ($100/mo):** Real-time social sentiment at scale

---

## 8. Implementation Priority Matrix

| Priority | Data Source | Effort | Impact | When to Build |
|----------|-----------|--------|--------|---------------|
| 🔴 P0 | MT5 OHLCV feed | Low | Critical | Day 1 |
| 🔴 P0 | Binance/Bybit API (crypto) | Low | Critical | Day 1 |
| 🟠 P1 | CoinGecko market overview | Low | High | Week 1 |
| 🟠 P1 | Economic calendar (MQL5) | Low | High | Week 1 |
| 🟠 P1 | Funding rates (exchange API) | Low | High | Week 1 |
| 🟡 P2 | News aggregation (RSS) | Medium | Medium | Week 2 |
| 🟡 P2 | Reddit sentiment (PRAW) | Medium | Medium | Week 2 |
| 🟡 P2 | Google Trends | Low | Medium | Week 2 |
| 🟢 P3 | DefiLlama integration | Low | Medium | Week 3 |
| 🟢 P3 | Fear & Greed Index | Low | Low | Week 3 |
| ⚪ P4 | Glassnode (when capital allows) | Medium | High | After profitability |
| ⚪ P4 | NewsAPI (when capital allows) | Medium | Medium | After profitability |

---

## 9. Key Warnings & Lessons

1. **⚠️ NewsAPI.org free tier is NOT for production** — 24h article delay makes it useless for trading signals. Only good for development/testing.

2. **⚠️ Alpha Vantage free tier is nearly useless** — 25 calls/day means you can't even do basic backtesting. Use Twelve Data instead (800 calls/day).

3. **⚠️ IEX Cloud shut down in Aug 2024** — Don't assume any data provider is permanent. Always have fallback sources.

4. **⚠️ Twitter/X API is expensive for meaningful volume** — Free tier (1,500 tweets/mo) is ~50/day. Not enough for sentiment analysis. Need $100/mo Basic plan.

5. **✅ Exchange APIs are the best free data source** — Binance/Bybit provide real-time data, unlimited calls, WebSocket streams. Use them as primary for crypto.

6. **✅ MT5 is underrated** — Built-in calendar, OHLCV, tick data, trade execution — all in one. Don't overlook it.

7. **✅ DefiLlama is a gem** — Completely free, no API key, comprehensive DeFi data. Use it.

---

*This research document should be revisited quarterly as pricing and availability change frequently.*
