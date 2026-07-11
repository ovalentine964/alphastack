# Market Microstructure Research — Alpha Stack

> Institutional-level understanding of order books, spreads, market impact, and order flow.

---

## 1. Order Book Mechanics

### 1.1 How Order Books Work

An **order book** (also called Depth of Market / DOM) is a real-time, continuously updated list of buy and sell orders for a financial instrument organized by price level.

**Core Structure:**
- **Bids (Buy side):** Orders to purchase, sorted descending by price (highest bid at top)
- **Asks/Offers (Sell side):** Orders to sell, sorted ascending by price (lowest ask at top)
- **Best Bid / Best Ask:** The highest bid and lowest ask — their difference is the spread
- **Depth:** The total volume of orders at each price level away from the best price
- **Mid-price:** (Best Bid + Best Ask) / 2 — the "fair value" estimate

```
ASKS (Sell Orders)
─────────────────────────────────
1.0855  │  500K  │  ██████
1.0854  │  300K  │  ████
1.0853  │  200K  │  ███
1.0852  │  800K  │  ██████████  ← Heavy resistance
─────────────────────────────────
1.0851  │  BEST ASK
═════════ SPREAD: 1.0 pips ═════
1.0850  │  BEST BID
─────────────────────────────────
1.0849  │  400K  │  █████
1.0848  │  250K  │  ███
1.0847  │  600K  │  ████████   ← Strong support
1.0846  │  150K  │  ██
─────────────────────────────────
BIDS (Buy Orders)
```

**Order Types in the Book:**
| Order Type | Behavior | Book Impact |
|---|---|---|
| **Limit Order** | Rests in book at specified price | Adds liquidity |
| **Market Order** | Executes immediately at best available | Removes liquidity |
| **Stop Order** | Becomes market order when triggered | Removes liquidity on trigger |
| **Iceberg/Hidden** | Partially visible; most of size hidden | Masks true depth |

### 1.2 Level 1 vs Level 2 vs Level 3 Data

| Level | What You See | Who Uses It | Access Cost |
|---|---|---|---|
| **Level 1** | Best bid/ask price & size, last trade | All retail traders | Free via most platforms |
| **Level 2** | Full order book (multiple price levels, aggregated size) | Active day traders, prop firms | $5–50/month per exchange |
| **Level 3** | Every individual order with ID, size, time, modification | Market makers, HFT firms, exchanges | Institutional only |

**What each reveals:**

- **Level 1:** The surface. Tells you the price but not the story.
- **Level 2:** Shows where liquidity clusters, where gaps exist, how thick/thin the book is. Reveals support/resistance beyond price action alone.
- **Level 3:** Shows order additions, cancellations, modifications in real-time. This is where spoofing detection, order flow toxicity measurement, and true institutional analysis happens.

**Key insight for retail:** You never get Level 3. But Level 2 (DOM) is available on MT5 for ECN accounts and provides significant edge if you know how to read it.

### 1.3 Order Book Imbalance as Signal

**Order Book Imbalance (OBI)** measures the ratio of buy vs. sell volume at or near the best prices.

```
OBI = (Bid Volume - Ask Volume) / (Bid Volume + Ask Volume)
```

**Interpretation:**
- OBI > +0.5 → Strong buy pressure (more resting bids than asks)
- OBI < -0.5 → Strong sell pressure
- OBI near 0 → Balanced market

**Trading signals from OBI:**

1. **Directional bias:** Persistent imbalance signals institutional accumulation/distribution
2. **Liquidity gaps:** Thin levels on one side suggest price will move through them quickly
3. **Spoofing detection:** Large orders that appear and vanish (especially at Level 3) indicate manipulation
4. **Absorption:** When large resting orders absorb aggressive market orders without moving — signals strong institutional interest

**Research finding:** A 2025 arXiv paper on order book imbalance found that imbalance slope is inversely proportional to market depth — meaning when the book is thin, imbalances are more predictive of short-term price movement.

**Limitations for forex:** Forex is a decentralized OTC market. There is no single unified order book. What you see on MT5 DOM is only your broker's liquidity aggregator's view — a fraction of global order flow.

### 1.4 How Institutional Traders Read Order Books

Institutional traders use order book data differently than retail:

1. **Liquidity mapping:** Identify where large resting orders sit (potential support/resistance)
2. **Execution planning:** Split large orders across price levels and time to minimize impact
3. **Toxicity measurement:** Use VPIN (Volume-Synchronized Probability of Informed Trading) to assess adverse selection risk
4. **Iceberg hunting:** Detect hidden orders by watching for replenishment patterns at specific levels
5. **Queue position:** In electronic markets, being first in queue at a price level matters for fill probability

**Key institutional strategies involving order books:**
- **Market making:** Posting bids and asks to capture the spread
- **Liquidity detection:** Sending small "ping" orders to gauge hidden depth
- **Layering/Spoofing:** Placing and canceling orders to manipulate perception (illegal but prevalent)
- **Sniping:** Detecting large resting orders and front-running them

### 1.5 Order Book Data on MT5

**What MT5 provides:**

MT5 has a built-in **Depth of Market (DOM)** feature accessible via:
- MQL5 API: `MarketBookGet()` / `MarketBookAdd()`
- Python: `mt5.market_book_get(symbol)`
- GUI: Right-click symbol → "Depth of Market"

**MQL5 BookEvent handler:**
```mql5
void OnBookEvent(const string &symbol) {
    MqlBookInfo book[];
    MarketBookGet(symbol, book);
    // book[] contains price, type (BID/ASK/BUY/SELL), volume
}
```

**What you can get:**
- Multiple price levels (typically 10–20 levels each side)
- Volume at each level
- Real-time updates on book changes

**What you CANNOT get on MT5:**
- Individual order IDs (no Level 3)
- Historical order book snapshots (no built-in storage)
- Cross-broker aggregated book
- True forex volume (only tick volume)
- Hidden/iceberg order detection

**Practical for Alpha Stack:** Use MT5 DOM for short-term execution timing (enter when book is favorable), not for deep institutional-style analysis. Pair with tick volume and price action for better signals.

---

## 2. Bid-Ask Spread

### 2.1 What Determines Spread Width

The spread is the primary transaction cost in forex. Multiple factors determine its width:

**Structural factors:**
| Factor | Effect on Spread | Example |
|---|---|---|
| **Currency pair liquidity** | More liquid = tighter | EUR/USD: 0.1–1.0 pips vs. USD/TRY: 5–25 pips |
| **Time of day** | Overlap sessions = tighter | London-NY overlap: tightest spreads |
| **Volatility** | Higher vol = wider spreads | NFP release: spreads blow out 5–10x |
| **Broker type** | ECN vs. market maker | ECN: raw spread + commission; MM: fixed spread |
| **Order size** | Larger size = wider effective spread | 0.01 lot vs. 10 lots |
| **Market depth** | Thin book = wider spreads | Asian session exotic pairs |

**Academic insight (Determinants of Bid-Ask Spreads in FX, SMU 1999):**
The key determinants of forex spreads are:
1. **Inventory costs** — risk market makers bear holding positions
2. **Adverse selection costs** — risk of trading against informed traders
3. **Order processing costs** — technology, infrastructure
4. **Competition** — more LPs = tighter spreads

### 2.2 Spread as Transaction Cost

**For a $7 account trading 0.01 lot EUR/USD:**

```
Position size: 0.01 lot = 1,000 units
Spread: 1.2 pips (typical for EUR/USD on FXPesa)
Pip value: $0.10 per pip for 0.01 lot
Spread cost: 1.2 × $0.10 = $0.12 per trade
Round trip (open + close): $0.12 × 2 = $0.24

As % of account: $0.24 / $7 = 3.43% per round trip
```

**This is devastating.** A 3.43% cost per trade means you need 3.43% profit just to break even. For context, professional traders aim for costs below 0.5% of account per trade.

**Break-even calculation:**
```
Required pips to break even = Spread (pips) × 2
For 1.2 pip spread: Need 2.4 pips profit just to cover costs
For 0.6 pip spread (ECN): Need 1.2 pips profit
```

### 2.3 How to Minimize Spread Impact

1. **Trade during liquid sessions** — London-NY overlap (13:00–17:00 GMT) has tightest spreads
2. **Choose liquid pairs** — EUR/USD, USD/JPY, GBP/USD have lowest spreads
3. **Use limit orders** — Provide liquidity instead of consuming it (some brokers offer rebates)
4. **Avoid news events** — Spreads widen 5–10x during NFP, FOMC, CPI
5. **Size appropriately** — Smaller positions have proportionally higher spread costs
6. **Choose ECN broker** — Raw spreads (0.0–0.5 pips) + small commission vs. fixed spreads
7. **Trade higher timeframes** — If target is 100 pips, 1.2 pip spread = 1.2% cost; if target is 10 pips, it's 12%
8. **Avoid end-of-day/week** — Spreads widen as liquidity providers pull quotes

### 2.4 Spread Patterns During Different Sessions

```
Typical EUR/USD Spread by Session (pips):

Asian Session (00:00–08:00 GMT):     1.0 – 2.5 pips
London Session (08:00–16:00 GMT):    0.5 – 1.2 pips
London-NY Overlap (13:00–17:00):     0.3 – 0.8 pips  ← TIGHTEST
New York Session (13:00–22:00 GMT):  0.5 – 1.5 pips
Late NY / Pre-Asian (22:00–00:00):   1.5 – 3.0+ pips ← WIDEST

Friday Close (20:00–22:00 GMT):      2.0 – 5.0+ pips
Sunday Open (22:00 GMT):             3.0 – 10+ pips  ← GAP RISK
```

### 2.5 FXPesa Typical Spreads

FXPesa (Kenya-based broker, part of EGM Securities) offers:

**Standard Account (STP):**
| Pair | Typical Spread | Commission |
|---|---|---|
| EUR/USD | 1.2 – 1.6 pips | None |
| GBP/USD | 1.5 – 2.0 pips | None |
| USD/JPY | 1.2 – 1.5 pips | None |
| AUD/USD | 1.5 – 2.0 pips | None |
| EUR/GBP | 1.8 – 2.5 pips | None |
| USD/CHF | 1.5 – 2.0 pips | None |

**Executive Account (ECN):**
| Pair | Typical Spread | Commission |
|---|---|---|
| EUR/USD | 0.1 – 0.5 pips | $3.50 per lot per side |
| GBP/USD | 0.3 – 0.8 pips | $3.50 per lot per side |
| USD/JPY | 0.1 – 0.5 pips | $3.50 per lot per side |

**For a $7 account:**
- Standard: $0.12 round trip cost on EUR/USD (1.2 pip spread × $0.10/pip)
- ECN: $0.04 spread + $0.07 commission = $0.11 round trip (similar, but tighter spreads benefit scalpers)

**Key consideration:** FXPesa is regulated by CMA (Kenya). Execution quality may not match Tier-1 brokers. Expect occasional wider spreads during low liquidity.

---

## 3. Market Impact

### 3.1 How Large Orders Move Prices

**Market impact** is the effect a trader's order has on the price of the asset. It's the cost of demanding liquidity.

**The mechanics:**
1. A market buy order consumes the cheapest available asks
2. If the order exceeds available size at best ask, it "walks up" the book
3. The larger the order relative to available liquidity, the greater the price impact

**Impact formula (simplified):**
```
Price Impact ≈ σ × (Q / V)^0.5

Where:
σ = volatility of the asset
Q = order size
V = average daily volume
```

This is the **square-root law** of market impact — one of the most robust empirical findings in market microstructure.

### 3.2 Temporary vs Permanent Impact

| Type | What It Is | Cause | Duration |
|---|---|---|---|
| **Temporary Impact** | Price displacement during execution | Consuming liquidity from the book | Reverts after execution |
| **Permanent Impact** | Lasting price change after execution | Information content of the trade | Persists (information incorporated) |

**Key insight:** Temporary impact is the cost of demanding liquidity NOW. Permanent impact is the market's assessment that your trade contains information.

**For retail traders ($7 account):**
- Your orders (0.01 lot) have **zero measurable market impact** on major pairs
- Even 1 full lot on EUR/USD is absorbed by the book without a ripple
- Market impact becomes relevant at 10+ lots on majors, or any size on exotic pairs
- Your cost is purely spread + commission, not impact

### 3.3 Almgren-Chriss Model for Optimal Execution

The **Almgren-Chriss framework** (2000) is the foundational model for optimal trade execution. It balances market impact against timing risk.

**Core problem:** You need to sell X shares over time T. Do you trade fast (high impact, low risk) or slow (low impact, high risk)?

**Model components:**

```
Permanent impact:   g(v) = γ × v        (linear in trading rate)
Temporary impact:   h(v) = η × v        (linear in trading rate)
Variance of cost:   Var = σ² × Σ xₖ²   (risk from price moves during execution)

Total cost = Impact cost + Timing risk
Optimal trajectory minimizes: E[cost] + λ × Var[cost]
Where λ = risk aversion parameter
```

**Optimal execution trajectory:**
- For risk-neutral trader: Linear (constant rate over time)
- For risk-averse trader: Front-loaded (trade faster early to reduce uncertainty)
- The more risk-averse, the more you front-load

**Practical application for Alpha Stack:**
With $7 and 0.01 lot positions, Almgren-Chriss is **irrelevant** for your direct trading. However, understanding the concept is valuable:

1. **When scaling up:** If you grow to larger positions, optimal execution becomes critical
2. **Algorithm design:** The principle of "trade proportionally to urgency" applies to any execution logic
3. **Institutional mindset:** Understanding why institutions trade the way they do (TWAP, VWAP, IS algorithms) helps you anticipate their flow

### 3.4 How to Minimize Market Impact with $7 Capital

**You don't have a market impact problem.** With $7 and 0.01 lots, you're in the noise. Your challenges are:

1. **Spread cost** — Your primary enemy (3.43% per round trip)
2. **Slippage** — Can add 0.1–0.5 pips during volatile periods
3. **Commission** — If using ECN, $7/lot round trip matters at small sizes

**What actually matters for a $7 account:**
- Trade only during London-NY overlap (tightest spreads)
- Stick to EUR/USD (tightest spread of any pair)
- Use limit orders when possible
- Trade higher timeframes (target 50+ pips to amortize spread cost)
- Avoid news events (spread blowout)

### 3.5 When Market Impact Becomes Significant

**Rough thresholds for EUR/USD:**

| Order Size | Impact Level | Notes |
|---|---|---|
| 0.01 – 0.1 lot | Negligible | Absorbed by top of book |
| 0.1 – 1 lot | Minimal | Consumes 1–2 price levels |
| 1 – 10 lot | Small | May move price 0.1–0.5 pips |
| 10 – 100 lot | Moderate | Requires execution algorithms |
| 100+ lot | Significant | Needs iceberg orders, TWAP/VWAP |

**For exotic pairs (USD/TRY, EUR/ZAR):** Impact thresholds are 10–100x lower due to thinner books.

---

## 4. Order Flow Analysis

### 4.1 Volume Analysis: Tick Volume vs Real Volume

**Critical distinction in forex:**

| Type | What It Is | Available In | Reliability |
|---|---|---|---|
| **Real Volume** | Actual number of units traded | Futures (CME), centralized exchanges | High — definitive |
| **Tick Volume** | Number of price changes (ticks) | MT4/MT5 forex | Moderate — proxy for activity |

**Why forex only has tick volume:**
Forex is decentralized (OTC). No single exchange records all trades. Your MT5 broker only sees its own flow. Tick volume counts price updates, which correlates with real volume but isn't the same.

**Correlation research:** Studies show tick volume and real volume correlate at 0.85–0.95 on major forex pairs during active sessions. It's a reliable proxy for relative volume comparisons (this hour vs. that hour), even if absolute numbers are meaningless.

**Using tick volume effectively:**
1. **Relative comparisons only** — "Volume is 2x average" is meaningful; "Volume is 10,000 ticks" is not
2. **Volume spikes** — Sudden surges indicate institutional activity regardless of whether volume is "real"
3. **Volume at price** — Areas where volume clusters = areas of institutional interest
4. **Volume divergence** — Rising price with declining volume = weakening trend

### 4.2 On-Balance Volume (OBV)

**Formula:**
```
If close > previous close:
    OBV = previous OBV + current volume
If close < previous close:
    OBV = previous OBV - current volume
If close = previous close:
    OBV = previous OBV
```

**Trading signals:**
1. **Trend confirmation:** OBV moving with price confirms trend strength
2. **Divergence:** OBV rising while price falling = bullish divergence (accumulation)
3. **Breakout validation:** Price breakout confirmed by OBV breakout = higher probability
4. **Leading indicator:** OBV often leads price — it can signal reversals before price turns

**Limitations in forex:**
- Uses tick volume, not real volume
- Single price point (close) doesn't capture intrabar action
- Gap between sessions creates discontinuities

### 4.3 Accumulation/Distribution (A/D) Line

**Formula:**
```
Money Flow Multiplier = ((Close - Low) - (High - Close)) / (High - Low)
Money Flow Volume = MF Multiplier × Volume
A/D Line = previous A/D + Money Flow Volume
```

**Why it's better than OBV for forex:**
- Considers WHERE in the range price closed (not just up/down)
- A close near the high of the bar is more bullish than a close in the middle
- More granular signal for institutional accumulation/distribution

**Trading signals:**
- **A/D rising + price flat** → Quiet accumulation (bullish)
- **A/D falling + price flat** → Quiet distribution (bearish)
- **A/D and price diverging** → High-probability reversal signal

### 4.4 Delta Analysis (Buy vs Sell Volume)

**Delta** = Buy Volume - Sell Volume

This measures net aggression — who is more aggressive, buyers or sellers.

**How to determine buy vs. sell volume in forex:**
Since forex has no centralized tape, you approximate:
- **Uptick rule:** If price moved up from last tick, classify as buying
- **Bid/Ask classification:** If trade occurred at ask price = buyer-initiated (aggressive buying)
- **MT5 approach:** Use `MqlTick` data — compare `last` price to `bid`/`ask` to classify

```python
# Simplified delta calculation for MT5
if tick.last >= tick.ask:
    buy_volume += tick.volume  # Aggressive buyer
elif tick.last <= tick.bid:
    sell_volume += tick.volume  # Aggressive seller
delta = buy_volume - sell_volume
```

**Interpretation:**
- **Positive delta + rising price** → Confirmed buying pressure
- **Negative delta + rising price** → Short covering / weak rally (bearish divergence)
- **Delta spike** → Institutional activity, potential reversal or breakout point
- **Cumulative delta** → Running total shows overall aggression bias over time

### 4.5 Order Flow Footprint Charts

**Footprint charts** (also called cluster charts or volume ladder) show volume traded at each price level within a candle, split by buy/sell aggression.

```
Footprint Chart Example (EUR/USD 5-min candle):

Price   |  Bid×Ask  | Delta  | Total
--------|-----------|--------|-------
1.0855  |  50×120   |  +70   |  170
1.0854  |  80×95    |  +15   |  175
1.0853  |  120×60   |  -60   |  180
1.0852  |  200×45   | -155   |  245  ← Heavy selling absorbed
1.0851  |  150×80   |  -70   |  230
1.0850  |  40×180   | +140   |  220  ← Strong buying
1.0849  |  30×160   | +130   |  190

Volume Profile: POC at 1.0852 (245 contracts)
Candle Delta: Net buying (+20)
```

**Key patterns on footprint charts:**
1. **Absorption:** Large resting orders that absorb aggressive selling without price moving down → bullish
2. **Exhaustion:** High volume at a price level with no follow-through → reversal signal
3. **Imbalance:** Significant buy vs sell ratio at a level (>3:1) → strong directional interest
4. **POC (Point of Control):** Highest volume price level — acts as magnet/resistance

**Availability on MT5:**
MT5 does NOT have native footprint charts. Options:
- **MQL5 Market:** Third-party indicators (e.g., "Order Flow Footprint Chart" by various devs, ~$50–150)
- **External tools:** Sierra Chart, Bookmap, ATAS, NinjaTrader (connect to MT5 data feed)
- **DIY with MQL5:** Use `OnTick()` to record tick-by-tick data, build custom footprint

### 4.6 What MT5 Provides for Order Flow

| Feature | Built-in? | Notes |
|---|---|---|
| Tick volume | ✅ Yes | `Volume` in OHLCV data |
| Real volume | ❌ No | Forex is OTC; not available |
| DOM/Order book | ✅ Yes | `MarketBookGet()` for ECN accounts |
| Tick data | ✅ Yes | `CopyTicks()` for tick-level analysis |
| Time & Sales | ⚠️ Partial | Tick data can reconstruct, but no native tape |
| Footprint charts | ❌ No | Need third-party or custom development |
| Delta calculation | ❌ No | Must build from tick data |
| Cumulative delta | ❌ No | Must build from tick data |

**What you can build on MT5:**
1. Custom tick volume analysis with MQL5
2. Order book imbalance indicator using DOM data
3. Delta approximation using tick-by-tick bid/ask classification
4. Volume profile from tick data
5. VWAP (Volume-Weighted Average Price) from tick volume

---

## 5. Execution Quality

### 5.1 Slippage: Causes and Measurement

**Slippage** = Difference between expected execution price and actual execution price.

**Types:**
| Type | Cause | Direction | Frequency |
|---|---|---|---|
| **Market slippage** | Price moved between order submission and execution | Can be positive or negative | Normal in fast markets |
| **Liquidity slippage** | Insufficient depth at requested price | Always against you | Thin markets, large orders |
| **Latency slippage** | Delay between your platform and broker's server | Against you | Poor connection, distant server |
| **Broker slippage** | Broker deliberately fills at worse price | Against you | Market maker brokers (check broker reputation) |

**Positive slippage exists too:** Sometimes you get filled at a BETTER price than requested (common with ECN brokers during high liquidity).

**Measuring slippage:**
```python
# For each trade
requested_price = order_send_price
actual_fill_price = order_result_price
slippage_pips = (actual_fill_price - requested_price) / pip_size
# For buys: positive slippage = worse fill
# For sells: negative slippage = worse fill

# Track over N trades
avg_slippage = sum(slippages) / N
slippage_std = std(slippages)
# If avg_slippage significantly > 0, broker may be slipping you
```

**Normal slippage ranges:**
- EUR/USD, normal conditions: 0.0–0.3 pips
- EUR/USD, news event: 1.0–5.0+ pips
- Exotic pairs: 1.0–10.0+ pips
- Crypto (BTC/USD): 0.5–50.0+ USD

### 5.2 Requotes and Rejected Orders

**Requote:** Broker says "price has changed, here's the new price, accept?" — common with market maker brokers.

**Causes:**
1. Price moved during processing (legitimate)
2. Broker's LP pulled quotes (liquidity issue)
3. Broker deliberately requotes to avoid filling profitable trades (manipulative)

**Rejected orders:** Order simply fails to execute.
- "No money" — insufficient margin
- "Invalid price" — price too far from current (stale order)
- "Market closed" — trading session ended
- "Off quotes" — broker's LP not providing quotes

**MT5 advantage over MT4:** MT5 uses the **Exchange** execution model which is more transparent. Orders go through an order matching engine, reducing arbitrary requotes.

### 5.3 Fill Rates at Different Times

**Fill rate** = Percentage of orders that execute at the requested price or better.

```
Typical fill rates by session (EUR/USD, ECN broker):

London-NY Overlap (13:00–17:00 GMT):  98–99%  ← Best
London Session (08:00–16:00 GMT):      96–98%
New York Session (13:00–22:00 GMT):    95–97%
Asian Session (00:00–08:00 GMT):       90–95%
Late NY / Pre-Asian (22:00–00:00):     85–92%
Sunday Open:                            70–85%  ← Worst

During NFP release:                    60–80%
During FOMC announcement:              70–85%
```

**Implications for $7 account:**
- Trade during London-NY overlap for best fills
- Avoid Sunday open and late NY session
- Never trade through major news events (NFP, FOMC, CPI) unless strategy specifically calls for it
- Use limit orders during thin sessions to guarantee fill price

### 5.4 Best Execution Practices for Retail

1. **Use limit orders** — Guaranteed price, no slippage, may get positive fills
2. **Set maximum deviation** — MT5 allows max deviation setting (e.g., 5 pips) to reject bad fills
3. **Trade liquid pairs** — EUR/USD, USD/JPY have best execution
4. **Trade liquid sessions** — London-NY overlap
5. **VPS near broker** — Reduce latency (broker server in London → use London VPS)
6. **Avoid market orders during news** — Use limits or don't trade
7. **Monitor execution quality** — Log every fill, track slippage statistics
8. **Choose broker wisely** — ECN/STP > Market Maker for execution quality
9. **Use appropriate order types** — Stop-Limit orders to control slippage on stop entries

### 5.5 Optimal Entry/Exit Timing

**Best times to enter trades (EUR/USD):**
| Time (GMT) | Session | Spread | Liquidity | Slippage | Recommendation |
|---|---|---|---|---|---|
| 00:00–02:00 | Asian | Wide | Low | High | ❌ Avoid |
| 02:00–07:00 | Asian | Moderate | Low-Med | Moderate | ⚠️ Caution |
| 07:00–08:30 | Pre-London | Narrowing | Rising | Low | ✅ Good |
| 08:30–12:00 | London | Tight | High | Very Low | ✅✅ Excellent |
| 12:00–13:00 | Lunch gap | Widens slightly | Drops | Moderate | ⚠️ Caution |
| 13:00–17:00 | London-NY | Tightest | Highest | Lowest | ✅✅✅ Best |
| 17:00–20:00 | NY afternoon | Widening | Falling | Rising | ⚠️ Caution |
| 20:00–22:00 | Late NY | Wide | Low | High | ❌ Avoid |

---

## 6. Market Microstructure Patterns

### 6.1 Opening Range Dynamics

**Opening Range (OR):** The high-low range established in the first 15–60 minutes of a major session.

**London Open (08:00 GMT):**
- Institutional orders from Asian session carry over
- Stop clusters above Asian range high and below Asian range low
- Initial move often "fake" — London opens by hunting Asian session stops
- The true direction often emerges after the first 30–60 minutes
- Opening range breakout strategy: Trade break of OR high/low with the trend

**New York Open (13:00 GMT / 8:00 EST):**
- US institutional money enters
- Often retests London session levels
- Strongest moves happen in first 2 hours
- NFP/FOMC days: Range expands dramatically at 13:30 / 19:00 GMT

**Asian Open (00:00 GMT):**
- Lowest volatility session
- Sets range that London often breaks
- Range-bound strategies work best
- Key levels from previous day's NY close act as anchors

### 6.2 London/NY Session Microstructure

**London Session Characteristics:**
- **Liquidity:** Highest in the world for forex (~35% of global volume)
- **Spread behavior:** Tightens rapidly from 08:00 GMT
- **Order flow:** Institutional, large block orders, trend-setting
- **Key pattern:** London fix at 16:00 GMT (WM/Reuters benchmark) causes large flows
- **Microstructure edge:** London open often "corrects" the Asian range — watch for false breakouts

**New York Session Characteristics:**
- **Liquidity:** Second highest (~20% of global volume)
- **Spread behavior:** Very tight during London overlap, widens after 17:00 GMT
- **Order flow:** US-driven, equity market correlation, news-reactive
- **Key pattern:** US data releases (8:30 EST) cause massive volume spikes
- **Microstructure edge:** NY session often reverses or extends London moves — watch for exhaustion

**Session Overlap (13:00–17:00 GMT):**
- Combined ~55% of global forex volume
- Tightest spreads, deepest liquidity, best execution
- Largest moves of the day typically start here
- Institutional rebalancing occurs during this window

### 6.3 Asian Session Liquidity

**Characteristics:**
- **Lowest liquidity** of the three major sessions
- **Range-bound behavior** — 60-70% of the time, Asian range holds
- **Key participants:** Japanese institutional (pension funds, corporates), Australian banks
- **USD/JPY and AUD/USD** are most active during this session
- **EUR/USD** often consolidates in a 20–40 pip range

**Microstructure patterns:**
1. **Asian range formation:** Price establishes a tight range; this becomes the "box" London breaks
2. **Tokyo fix (00:30 GMT / 9:30 JST):** Large flows for benchmark fixing
3. **Thin book depth:** 50–80% less depth than London session
4. **Wider effective spreads:** Same broker shows 2–3x wider spreads
5. **Stop hunting:** Less common due to thin liquidity, but when it happens, moves are exaggerated

**Strategy implication:** Asian session is best for mean-reversion strategies with tight ranges. Avoid breakout strategies — most breakouts during Asian are false.

### 6.4 News Event Microstructure

**Pre-event (30–60 minutes before):**
- Spreads begin to widen
- Liquidity providers pull quotes (reduce risk)
- Order book thins significantly
- Implied volatility rises in options market
- Smart money positions already in place

**During event (0–5 minutes):**
- **Liquidity void:** Massive gap between buy and sell orders
- Spreads can blow out to 5–20x normal
- Slippage of 5–50 pips is possible on majors
- Orders fill at unpredictable prices
- Stop-loss orders trigger at terrible levels ("stop runs")
- Price moves in "staircase" pattern — gaps between each trade

**Post-event (5–30 minutes):**
- Liquidity gradually returns
- Spreads normalize over 15–60 minutes
- "Recovery" fills may occur (some brokers adjust bad fills)
- Order flow reveals institutional positioning
- Often a retracement of initial spike as market digests news

**Key events and their microstructure impact:**

| Event | Time (GMT) | Impact Level | Spread Blowout | Recovery Time |
|---|---|---|---|---|
| **NFP** | 13:30, 1st Friday | Extreme | 10–20x | 15–30 min |
| **FOMC Decision** | 19:00, scheduled | Extreme | 5–15x | 10–20 min |
| **CPI** | 13:30 | High | 5–10x | 10–15 min |
| **ECB Rate Decision** | 13:45 | High | 5–10x | 10–15 min |
| **BOJ Rate Decision** | 03:00–05:00 | High (JPY) | 5–10x | 15–30 min |
| **GDP** | 13:30 | Moderate | 3–5x | 5–10 min |
| **PMI** | Various | Moderate | 2–4x | 5–10 min |
| **Retail Sales** | 13:30 | Moderate | 2–5x | 5–10 min |

### 6.5 End-of-Day/Week Patterns

**End-of-Day (20:00–22:00 GMT):**
- Liquidity providers close positions
- Spreads widen 2–3x
- "Squaring" — day traders close positions, creating predictable flows
- NY close at 22:00 GMT is the forex "end of day"
- Swap/rollover at 22:00 GMT (or 21:00 UTC) — can create small price dislocations

**End-of-Week (Friday 20:00–22:00 GMT):**
- Widest spreads of the week
- Liquidity drops 50–70% vs. mid-week
- Institutional traders square positions before weekend
- Gap risk is real: Monday open can gap significantly from Friday close
- Avoid holding positions through weekend unless strategy accounts for gap risk

**End-of-Month:**
- Portfolio rebalancing flows (large institutional orders)
- Fixing flows (WM/Reuters 16:00 GMT London, month-end fixing can be 2–5x normal volume)
- Increased volatility in last 2 hours of London session on last business day

**End-of-Quarter:**
- Massive rebalancing by pension funds, sovereign wealth funds
- Window dressing — institutions adjust portfolios for reporting
- Highest volume of the quarter in final 2–3 days
- Can create persistent directional moves unrelated to fundamentals

---

## 7. Practical Application for Alpha Stack ($7 Account)

### 7.1 What Actually Matters at This Scale

| Microstructure Factor | Relevance to $7 Account | Priority |
|---|---|---|
| Order book depth | Low — you don't move the market | ⭐ |
| Bid-ask spread | **CRITICAL** — 3.43% per round trip | ⭐⭐⭐⭐⭐ |
| Market impact | Zero — your orders are noise | ⭐ |
| Order flow (delta) | Moderate — useful for directional bias | ⭐⭐⭐ |
| Slippage | Moderate — adds 0.1–0.5 pips | ⭐⭐⭐ |
| Session timing | **HIGH** — determines spread & fill quality | ⭐⭐⭐⭐ |
| News events | **HIGH** — spread blowout can wipe you out | ⭐⭐⭐⭐ |

### 7.2 Optimal Trading Rules Based on Microstructure

1. **Only trade EUR/USD** — Tightest spread, best liquidity
2. **Only trade 13:00–17:00 GMT** — London-NY overlap, best execution
3. **Never trade through NFP, FOMC, CPI** — Spread blowout risk is existential at $7
4. **Use limit orders exclusively** — Zero slippage, better prices
5. **Target 50+ pips per trade** — Spread cost = 2.4% of target (vs. 24% for 10-pip target)
6. **Set max slippage to 3 pips** — MT5 allows this; reject bad fills
7. **Monitor tick volume for confirmation** — Volume spike = institutional activity = higher probability
8. **Use Asian range as reference** — London often breaks Asian range; trade the breakout direction

### 7.3 Building a Microstructure Dashboard (MT5)

**Recommended custom indicators to build:**

```
1. Spread Monitor
   - Track real-time spread vs. historical average
   - Alert when spread > 2x average
   - Color-code: Green (tight), Yellow (moderate), Red (wide)

2. Session Timer
   - Show current session (Asian/London/NY/Overlap)
   - Display typical spread range for current session
   - Countdown to next session change

3. Tick Volume Analyzer
   - Compare current volume to N-period average
   - Highlight volume spikes (>2x average)
   - Show volume trend (rising/falling)

4. Simple Delta Calculator
   - Classify ticks as buy/sell using bid/ask method
   - Show cumulative delta per candle
   - Highlight delta divergence from price

5. News Event Filter
   - Calendar of high-impact events
   - Auto-disable trading 30 min before/after major events
   - Show historical spread impact of similar events
```

### 7.4 Cost Analysis Summary

```
Trading costs for $7 account (EUR/USD, 0.01 lot):

BEST CASE (London-NY overlap, ECN):
  Spread: 0.3 pips × $0.10 = $0.03
  Commission: $0.07 (round trip)
  Slippage: 0.0 pips (limit order)
  Total: $0.10 per round trip
  As % of account: 1.43%

TYPICAL CASE (London session, Standard):
  Spread: 1.2 pips × $0.10 = $0.12
  Commission: $0.00
  Slippage: 0.1 pips × $0.10 = $0.01
  Total: $0.13 per round trip
  As % of account: 1.86%

WORST CASE (Asian session or news event):
  Spread: 5.0 pips × $0.10 = $0.50
  Commission: $0.00
  Slippage: 2.0 pips × $0.10 = $0.20
  Total: $0.70 per round trip
  As % of account: 10.0%  ← ACCOUNT-KILLING
```

---

## 8. Key Academic References

1. **Almgren & Chriss (2000)** — "Optimal Execution of Portfolio Transactions" — Foundational model for optimal execution
2. **Kyle (1985)** — "Continuous Auctions and Insider Trading" — The Kyle model of market impact
3. **Gatheral (2010)** — "No-dynamic-arbitrage and market impact" — Square-root law of market impact
4. **O'Hara (2015)** — "High frequency market microstructure" — Modern overview of market structure
5. **Harris (2003)** — "Trading and Exchanges" — Comprehensive textbook on market microstructure
6. **Determinants of Bid-Ask Spreads in FX (SMU, 1999)** — Empirical analysis of forex spread determinants
7. **VPIN (Easley, López de Prado, O'Hara, 2012)** — Volume-synchronized probability of informed trading
8. **Order Book Imbalance (arXiv, 2025)** — Slope inversely proportional to market depth

---

*Document compiled: 2026-07-11*
*For Alpha Stack — Institutional-grade microstructure understanding for retail-scale trading.*
