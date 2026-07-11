# Financial Crises, Black Swans & Alpha Stack Survival Playbook

> **Purpose:** Catalog historical market crises, analyze their mechanics, and define institutional-grade response protocols for Alpha Stack (AI trading system).
>
> **Last Updated:** 2026-07-11

---

## Table of Contents

1. [Forex Crises](#1-forex-crises)
2. [Crypto Crashes](#2-crypto-crashes)
3. [Flash Crashes](#3-flash-crashes)
4. [Pandemic & Geopolitical Events](#4-pandemic--geopolitical-events)
5. [Alpha Stack Response Architecture](#5-alpha-stack-response-architecture)
6. [Tail Risk Management](#6-tail-risk-management)
7. [Lessons Synthesis](#7-lessons-synthesis)

---

## 1. Forex Crises

### 1.1 Swiss Franc Unpegging — 15 January 2015

| Metric | Detail |
|---|---|
| **Pair** | EUR/CHF |
| **Move** | -30% in ~15 minutes (1.20 → 0.85 intraday) |
| **Trigger** | SNB abandoned 1.20 EUR/CHF floor (maintained since Sep 2011) |
| **Duration of chaos** | ~2 hours of illiquidity |
| **Aftermath** | Alpari UK bankrupt, FXCM needed $300M bailout, Interactive Brokers lost $120M |

**Key mechanics:**
- The 1.20 floor was considered "guaranteed" by the SNB. Vast positioning built on this assumption.
- When removed, there was literally **no bid** between 1.20 and ~0.85. Order books were empty.
- Stop-losses triggered at market with zero liquidity → massive slippage (some fills at 0.75).
- Retail brokers went negative-equity; clients owed money to brokers.
- The SNB had signaled commitment to the floor just days before.

**Alpha Stack lesson:** No central bank peg is permanent. Concentrated positioning around "guaranteed" levels creates catastrophic tail risk. The system must treat any currency peg as a **potential discontinuity** and limit exposure accordingly.

---

### 1.2 Asian Financial Crisis — 1997-1998

| Metric | Detail |
|---|---|
| **Currencies hit** | THB, IDR, MYR, KRW, PHP |
| **THB devaluation** | ~50% (pegged at 25/USD → floated to 56) |
| **IDR collapse** | From 2,400/USD to 16,800/USD (-85%) |
| **Trigger** | Thailand's current account deficit + speculative attacks on THB peg |
| **Contagion** | Spread from Thailand → Malaysia → Indonesia → South Korea → Russia → LTCM |

**Key mechanics:**
- Fixed exchange rates + large current account deficits = vulnerability.
- George Soros and hedge funds attacked the peg via forward contracts.
- Central banks burned through reserves defending, then capitulated.
- Capital flight accelerated: stock markets fell 40-80% in USD terms.
- Correlation across "Asian Tiger" economies went to ~1.0 during the crisis.
- LTCM collapse (1998) was a direct aftermath — "convergence trades" failed when correlations broke down.

**Alpha Stack lesson:** Contagion risk in correlated emerging market currencies is extreme. Position sizing must account for the possibility that **all EM positions lose simultaneously**. Reserve depletion by central banks is a leading indicator of peg failure.

---

### 1.3 Black Wednesday — 16 September 1992

| Metric | Detail |
|---|---|
| **Pair** | GBP/DEM (precursor to EUR) |
| **Move** | ~15% in one day |
| **Trigger** | UK forced to exit ERM (Exchange Rate Mechanism) |
| **Key player** | Soros reportedly made $1B+ shorting GBP |
| **UK cost** | £3.3B in reserves spent defending the peg in one day |

**Key mechanics:**
- UK joined ERM at an overvalued rate (2.95 DEM/GBP).
- High UK interest rates + recession made the peg unsustainable.
- Soros accumulated massive short GBP positions, knowing the BoE would exhaust reserves.
- BoE raised rates twice in one day (10% → 12% → 15%) — still failed.
- George Soros: "I knew the system would break."

**Alpha Stack lesson:** Interest rate differential analysis + reserve adequacy monitoring can identify unsustainable pegs. When a central bank is fighting the market with rate hikes AND reserve intervention simultaneously, the peg is near breaking.

---

### 1.4 Turkish Lira Crisis — 2018

| Metric | Detail |
|---|---|
| **Pair** | USD/TRY |
| **Move** | ~40% depreciation in 2018 (3.8 → 6.9) |
| **Trigger** | Political interference with central bank, US sanctions, inflation spiral |
| **Peak crisis** | August 2018 — TRY lost 20% in one week |

**Key mechanics:**
- President Erdogan insisted on low interest rates despite 15%+ inflation ("interest rates are the mother of all evil").
- CBRT independence was undermined — governors fired for raising rates.
- US sanctions over detained pastor Andrew Brunson triggered the acute phase.
- Dollarization accelerated as domestic confidence collapsed.
- Carry trade unwinding amplified the move.

**Alpha Stack lesson:** Political risk in EM currencies is a **first-order factor**. Central bank independence is a critical input. Carry trades in politically unstable regimes carry asymmetric downside.

---

### 1.5 Argentine Peso Crises — 2018 & 2023

| Metric | Detail |
|---|---|
| **2018** | ARS lost ~50% (20 → 40/USD), IMF $57B bailout |
| **2023** | Official rate 180 → 350 after Milei devaluation (Dec 2023) |
| **Pattern** | Recurring: currency board → crisis → devaluation → repeat |

**Key mechanics:**
- Argentina has had **9 sovereign defaults** and multiple currency regimes.
- Capital controls create parallel markets (blue dollar rate) — true price discovery happens offshore.
- IMF programs repeatedly failed to restore confidence.
- Inflation exceeded 100% in 2023 before Milei's shock therapy.

**Alpha Stack lesson:** Avoid countries with chronic fiscal imbalances and capital controls. If trading ARS, recognize that the official rate is a fiction — use parallel market rates for true valuation.

---

## 2. Crypto Crashes

### 2.1 LUNA/UST Collapse — May 2022

| Metric | Detail |
|---|---|
| **Assets** | LUNA (native token), UST (algorithmic stablecoin) |
| **Destruction** | ~$60 billion in total value wiped |
| **LUNA price** | $80 → $0.0001 (effectively zero) |
| **UST depeg** | $1.00 → $0.10 |
| **Timeline** | ~5 days (May 7-12, 2022) |

**Key mechanics:**
- UST was an **algorithmic stablecoin** — maintained its peg via an arbitrage mechanism with LUNA (mint UST by burning LUNA, redeem UST for LUNA).
- Anchor Protocol offered 19.5% APY on UST deposits — created massive artificial demand.
- The "death spiral": UST depeg → panic redemption → more LUNA minted → LUNA price drops → more UST depeg → repeat.
- Luna Foundation Guard (LFG) deployed $3B in BTC reserves to defend the peg — failed.
- Do Kwon's arrogance and refusal to acknowledge risks accelerated confidence loss.
- Contagion: Three Arrows Capital (3AC), Celsius, Voyager, BlockFi all collapsed in subsequent weeks.

**Alpha Stack lesson:** Algorithmic stablecoins are **inherently reflexive** — the mechanism that maintains the peg is the same mechanism that destroys it during stress. Never hold significant capital in algo-stablecoins. Monitor stablecoin backing ratios and depeg events as early warning signals.

---

### 2.2 FTX Collapse — November 2022

| Metric | Detail |
|---|---|
| **Exchange** | FTX (valued at $32B at peak) |
| **Customer losses** | ~$8 billion in missing customer funds |
| **Trigger** | CoinDesk revealed Alameda Research's balance sheet was mostly FTT tokens |
| **Timeline** | ~10 days (Nov 2-11, 2022) |
| **Aftermath** | Sam Bankman-Fried sentenced to 25 years |

**Key mechanics:**
- Alameda Research (sister trading firm) had secret access to FTX customer deposits.
- Alameda's balance sheet was heavily concentrated in FTT (FTX's own token) — circular value.
- Binance CEO CZ announced he would sell FTT holdings → bank run on FTX.
- $6B in withdrawals in 72 hours → FTX couldn't honor redemptions.
- Revealed as outright fraud — customer funds commingled with trading operations.

**Alpha Stack lesson:** Exchange counterparty risk is existential. Never hold >5% of capital on any single exchange. Prefer DEXs or self-custody. Monitor exchange proof-of-reserves. If an exchange's native token is a significant part of its own balance sheet — run.

---

### 2.3 Bitcoin Flash Crashes

| Event | Date | Move | Cause |
|---|---|---|---|
| **March 2020** | Mar 12-13 | -50% ($8K → $3.8K) | COVID panic, liquidity vacuum |
| **May 2021** | May 19 | -54% ($64K → $30K) | China ban + Elon tweets + leverage flush |
| **June 2022** | Jun 13-18 | -40% ($30K → $17.6K) | 3AC/Celsius contagion |
| **FTX crash** | Nov 2022 | -25% ($21K → $15.5K) | FTX collapse contagion |

**Common mechanics:**
- Crypto has **no circuit breakers** — moves happen 24/7/365.
- Leverage in crypto is extreme (100x available on some platforms).
- Cascading liquidations: price drops → liquidations → forced selling → more drops.
- Weekend/Asia-session liquidity is thin → amplified moves.
- Stablecoin depegs during crashes add to chaos.

**Alpha Stack lesson:** Crypto has no central authority to halt trading. Leverage amplification is orders of magnitude worse than equities. Position sizing must be conservative enough to survive 50%+ drawdowns without liquidation. Auto-deleveraging mechanisms must be in place.

---

### 2.4 DeFi Exploits

| Event | Date | Loss | Method |
|---|---|---|---|
| **Ronin Bridge** | Mar 2022 | $625M | Compromised validator keys |
| **Wormhole** | Feb 2022 | $320M | Smart contract bug |
| **Nomad Bridge** | Aug 2022 | $190M | Replica contract vulnerability |
| **Curve Finance** | Jul 2023 | $70M | Vyper compiler reentrancy bug |
| **Euler Finance** | Mar 2023 | $197M | Flash loan attack |

**Alpha Stack lesson:** Smart contract risk is unquantifiable by traditional means. Protocol-level diversification is essential. Monitor governance proposals, contract upgrades, and audit reports. Use time-delayed deposits in new protocols. Bridge risk is the highest risk category in DeFi.

---

## 3. Flash Crashes

### 3.1 The 2010 Flash Crash — 6 May 2010

| Metric | Detail |
|---|---|
| **Index** | Dow Jones Industrial Average |
| **Move** | -9.2% (~1,000 points) in 5 minutes, then recovery |
| **Trigger** | Large sell order by Waddell & Reed ($4.1B e-mini futures) |
| **Duration** | ~36 minutes (2:32 PM - 3:08 PM ET) |
| **Weirdness** | Accenture traded at $0.01, P&G at $0.01, Sotheby's at $99,999.99 |

**Key mechanics:**
- A single large sell algorithm (Waddell & Reed's "sell 75,000 e-minis" program) overwhelmed the order book.
- High-frequency market makers withdrew liquidity simultaneously (hot potato effect).
- Stub quotes (placeholder prices at $0.01 or $99,999) were hit because no real orders existed.
- Cross-market arbitrage broke down — ETFs decoupled from their underlying assets.
- Circuit breakers didn't exist at the individual stock level (implemented after this event).

**Alpha Stack lesson:** Flash crashes exploit the **withdrawal of liquidity** precisely when it's needed most. Market makers have no obligation to provide liquidity. The system must not assume continuous markets. Implement stock-level circuit breakers and avoid market orders during volatility spikes.

---

### 3.2 2015 ETF Flash Crash — 24 August 2015

| Metric | Detail |
|---|---|
| **Affected** | 1,278 stocks and ETFs, including major names |
| **Move** | S&P 500 futures -5% at open, some ETFs down 30%+ |
| **Trigger** | China devaluation fears + overnight futures limit-down |
| **Duration** | ~15 minutes after market open |

**Key mechanics:**
- LULD (Limit Up/Limit Down) halt mechanism malfunctioned — stocks opened with wide price bands.
- Market makers refused to open stocks, creating massive gaps.
- ETFs like VTI (Total Stock Market) traded at 10%+ discounts to NAV.
- Options market makers couldn't price options → stopped quoting.
- Retail investors saw flash losses of 30%+ on diversified ETF holdings.

**Alpha Stack lesson:** Opening auctions after overnight crashes are **extremely dangerous**. Never use market orders at the open during high-volatility regimes. ETF NAV discounts during stress are a structural feature, not a bug. The system should monitor ETF premiums/discounts as a stress indicator.

---

### 3.3 Yen Flash Crashes

| Event | Date | Move | Cause |
|---|---|---|---|
| **Jan 2019** | Jan 3 | USD/JPY -4% in 7 minutes | Algorithmic stop-hunt during illiquid Asia session |
| **Aug 2019** | Aug 2 | USD/JPY -1.5% in minutes | Escalating US-China trade tensions |
| **Multiple** | Various | 0.5-1% moves in seconds | Recurring during Japan holidays |

**Key mechanics:**
- JPY crosses are heavily traded by retail carry traders → stop-loss clustering.
- During illiquid hours (Asia session, Japan holidays), a small trigger cascades through stops.
- Japanese retail traders (Mrs. Watanabe) have concentrated stop levels → predictable targets.
- Algorithms detect the cascade and front-run the stop hunt.

**Alpha Stack lesson:** Time-of-day liquidity analysis is critical. Avoid concentrated stop-loss levels that algorithms can detect. Illiquid session trading requires wider stops and smaller positions.

---

## 4. Pandemic & Geopolitical Events

### 4.1 COVID-19 Crash — February-March 2020

| Metric | Detail |
|---|---|
| **S&P 500** | -34% (Feb 19 → Mar 23, 23 trading days) |
| **Volatility** | VIX peaked at 82.69 (highest since 2008) |
| **Circuit breakers** | Triggered 4 times in 10 days (Mar 9, 12, 16, 18) |
| **Credit markets** | IG spreads tripled, HY spreads quadrupled |
| **Oil** | WTI went negative (-$37.63 on Apr 20) |
| **Recovery** | S&P 500 recovered to all-time high by Aug 2020 (~5 months) |

**Key mechanics:**
- Speed was unprecedented — fastest 30% decline in history.
- **Everything correlated to 1.0.** Stocks, bonds, gold, crypto, real estate — all sold simultaneously.
- "Cash is the only hedge" was the lesson — even Treasuries sold off initially (liquidity squeeze).
- Fed intervention was massive: zero rates, unlimited QE, corporate bond buying, Main Street lending.
- The recovery was equally V-shaped, punishing anyone who stayed hedged too long.

**Alpha Stack lesson:** Pandemic events create **correlation convergence** where diversification fails. Cash is the ultimate hedge. Fed intervention can reverse crashes rapidly — the system must be prepared to re-enter after extreme dislocations. The speed of the decline means manual intervention is too slow — automated circuit breakers are essential.

---

### 4.2 Russia-Ukraine War — February 2022

| Metric | Detail |
|---|---|
| **Russian market** | MOEX fell -45% in one week, then closed for a month |
| **RUB** | USD/RUB spiked from 75 to 150+ (then recovered to 50) |
| **Energy** | Brent crude surged from $90 to $130 |
| **Wheat** | +40% in two weeks |
| **Contagion** | European banks with Russian exposure took massive write-downs |

**Key mechanics:**
- Russia was cut off from SWIFT → inability to settle transactions.
- Moscow Exchange closed for weeks → no exit for foreign investors.
- Commodities spiked as Russia is a major energy/grain exporter.
- Counterparty risk in European banks with Russian exposure spiked.
- Ruble initially collapsed, then **strengthened** due to capital controls + energy revenue.

**Alpha Stack lesson:** Geopolitical events can create **binary outcomes** that are impossible to model probabilistically. Position limits on country-specific exposure must be enforced. Commodity supply chain analysis becomes critical. Capital controls can trap positions — always assess exit liquidity.

---

## 5. Alpha Stack Response Architecture

### 5.1 Circuit Breakers (Multi-Layer)

```
LAYER 1: POSITION LEVEL
├── Per-trade stop-loss: -2% of portfolio (hard stop, no override)
├── Trailing stop: -3% from peak position value
├── Time-based exit: Close positions held >48h during crisis regime
└── Slippage circuit breaker: If execution slippage >0.5%, pause new entries

LAYER 2: PORTFOLIO LEVEL
├── Daily drawdown limit: -5% (trades paused for 24h)
├── Weekly drawdown limit: -10% (positions reduced by 50%)
├── Monthly drawdown limit: -15% (full de-risk to cash equivalent)
└── Max drawdown: -20% (system halt, human intervention required)

LAYER 3: REGIME LEVEL
├── VIX > 30: Reduce position sizes by 50%
├── VIX > 50: Reduce to 25% normal size, widen stops 2x
├── VIX > 70: Cash-only mode, no new positions
└── Correlation spike (>0.8 cross-asset): Activate hedging mode

LAYER 4: SYSTEM LEVEL
├── Exchange connectivity loss >30s: Close all positions on that exchange
├── Data feed anomaly: Cross-validate with backup feeds, halt if inconsistent
├── Order rejection rate >10%: Pause all trading
└── Latency spike >10x normal: Cancel all open orders
```

### 5.2 Max Drawdown Limits

| Stage | Drawdown | Action | Rationale |
|---|---|---|---|
| **Green** | 0-3% | Normal operations | Within expected variance |
| **Yellow** | 3-7% | Reduce new position size by 50%, tighten stops | Elevated risk, protect capital |
| **Orange** | 7-12% | Close all positions with >5% unrealized loss, hedge remaining | Significant risk, defensive posture |
| **Red** | 12-18% | Close 75% of all positions, move to cash | Crisis mode, capital preservation |
| **Black** | >18% | Close ALL positions, halt trading, alert human | System failure or unprecedented event |

### 5.3 Correlation Monitoring

```python
# Pseudocode for real-time correlation monitoring
class CorrelationMonitor:
    def __init__(self):
        self.window_short = 20   # 20-period rolling correlation
        self.window_long = 100   # 100-period baseline
        self.alert_threshold = 0.7  # Correlation spike threshold
        
    def check_regime(self, returns_matrix):
        current_corr = rolling_correlation(returns_matrix, self.window_short)
        baseline_corr = rolling_correlation(returns_matrix, self.window_long)
        correlation_spike = current_corr - baseline_corr
        
        # Cross-asset correlation convergence = crisis signal
        if mean(correlation_spike) > self.alert_threshold:
            trigger_regime_change("CRISIS")
            activate_hedging_mode()
            reduce_position_sizes(factor=0.5)
            
        # Sector correlation breakdown = rotation signal
        if sector_correlation_divergence() > threshold:
            trigger_regime_change("ROTATION")
            
    def check_contagion(self):
        # Monitor CDS spreads, TED spread, LIBOR-OIS
        credit_stress = credit_spread_z_score()
        if credit_stress > 2.0:
            reduce_exposure_to("credit_sensitive_assets")
        if credit_stress > 3.0:
            reduce_exposure_to("all_risk_assets")
```

### 5.4 Position Reduction Algorithm

When crisis signals are detected, positions should be reduced in this priority order:

1. **Highest beta positions** — most sensitive to market moves
2. **Illiquid positions** — hardest to exit during stress
3. **Leveraged positions** — highest margin call risk
4. **Correlated positions** — redundant risk in crisis
5. **Newest positions** — least conviction, most vulnerable

Reduction should be **gradual** to avoid signaling and causing further market impact:
- Target reduction: 50% over 2-4 hours, not all at once
- Use TWAP (Time-Weighted Average Price) algorithms
- Avoid executing during the first/last 30 minutes of trading sessions

### 5.5 News/Sentiment Crisis Detection

```
MONITORING INPUTS:
├── Financial news NLP (sentiment scoring, entity recognition)
├── Social media velocity (Twitter/X, Reddit, Telegram)
├── Central bank communications (FOMC, ECB, BOJ, PBOC)
├── Geopolitical event feeds (Bloomberg, Reuters)
├── Economic data surprises (actual vs. consensus)
└── Options market signals (put/call ratio, skew, term structure)

CRISIS SIGNAL DETECTION:
├── Sentiment velocity: 3σ negative move in <1 hour → ALERT
├── Volume spike: 5x normal volume with negative price action → ALERT
├── Central bank emergency action (unscheduled rate cut/hike) → ALERT
├── Geopolitical escalation keywords: "war", "sanctions", "invasion" → ALERT
└── Economic data miss >2σ → MONITOR (not always crisis, but elevated risk)

RESPONSE PROTOCOL:
1. Signal detected → Verify with secondary source (cross-validation)
2. If confirmed → Trigger regime change to CRISIS mode
3. Activate position reduction algorithm
4. Increase hedging (options, inverse ETFs, VIX exposure)
5. Log all actions for post-crisis review
```

### 5.6 Emergency Stop-Loss Framework

| Level | Trigger | Action | Recovery |
|---|---|---|---|
| **Soft Stop** | Single position -3% | Reduce by 50%, tighten remaining | Normal conditions |
| **Hard Stop** | Single position -5% | Close entire position | Re-evaluate thesis |
| **Portfolio Stop** | Daily P&L -4% | Close all losing positions | Next session |
| **Emergency Stop** | Hourly P&L -8% | Close ALL positions immediately | Manual review required |
| **System Kill** | Any single trade -10% | Halt ALL trading, close everything | Human override only |

---

## 6. Tail Risk Management

### 6.1 VaR Limitations

**Value at Risk (VaR)** is the industry standard for risk measurement but has critical failures:

| Limitation | Explanation | Crisis Example |
|---|---|---|
| **Assumes normal distribution** | Markets have fat tails — extreme events are 100-1000x more likely than Gaussian predicts | 2008: "25-sigma events" happening daily |
| **Backward-looking** | Based on historical data that doesn't capture unprecedented events | COVID crash faster than any historical precedent |
| **False precision** | "99% VaR of $10M" sounds precise but says nothing about the 1% | LTCM had "low" VaR before collapse |
| **Aggregation problem** | Portfolio VaR ≠ sum of component VaRs (diversification assumption) | Correlations → 1 in crises, VaR massively understated |
| **Doesn't capture liquidity risk** | Assumes positions can be closed at current prices | Swiss franc: no bids for 30%+ |
| **Procyclical** | Low VaR in calm markets → more leverage → more vulnerability | Pre-2008 bank risk models |

### 6.2 CVaR (Conditional Value at Risk) / Expected Shortfall

CVaR measures the **average loss in the worst X% of cases**, addressing VaR's blind spot.

```
VaR (95%):    "We won't lose more than $X 95% of the time"
CVaR (95%):   "In the worst 5% of cases, our average loss is $Y"

CVaR = E[Loss | Loss > VaR]

Example:
- Portfolio: $100M
- VaR (95%): $5M (we won't lose >$5M 95% of the time)
- CVaR (95%): $12M (but when we DO lose, average loss is $12M)

CVaR tells you about the SHAPE of the tail, not just the threshold.
```

**Why CVaR > VaR for Alpha Stack:**
1. CVaR is a **coherent risk measure** (satisfies subadditivity) — VaR is not
2. CVaR captures the **severity** of tail events, not just their probability
3. CVaR encourages better diversification (VaR can be gamed)
4. Regulatory direction (Basel III/IV) is moving toward CVaR

### 6.3 Stress Testing Framework

**Historical Scenario Stress Tests:**

| Scenario | Market Impact | What to Test |
|---|---|---|
| **2008 GFC** | S&P -57%, Credit spreads +600bps | Portfolio survival, leverage exposure |
| **2020 COVID** | S&P -34% in 23 days | Speed of response, circuit breaker triggers |
| **2015 CHF** | EUR/CHF -30% in minutes | Forex peg break survival, slippage impact |
| **2022 LUNA** | -99.99% in 5 days | Crypto counterparty exposure, stablecoin risk |
| **1997 Asian** | Currencies -50-85% | EM exposure, contagion modeling |
| **2010 Flash Crash** | -9.2% in 5 min, then recovery | Liquidity withdrawal, market order risk |

**Hypothetical Stress Tests:**

| Scenario | Description | Expected Impact |
|---|---|---|
| **US-China conflict** | Military escalation, sanctions, supply chain disruption | Equities -30%, commodities +50%, USD strength |
| **US debt default** | Technical default on Treasuries | Risk-free rate explodes, all correlations break |
| **AI bubble burst** | Tech concentration unwind (top 7 stocks) | NASDAQ -40%, rotation to value |
| **Hyperinflation** | USD inflation exceeds 20% | Bonds collapse, commodities surge, social unrest |
| **Quantum computing threat** | Cryptographic breaks | Crypto → 0, banking system compromised |

### 6.4 Scenario Analysis Process

```
STEP 1: IDENTIFY SCENARIOS
├── Historical replays (known events)
├── Hypothetical stress (plausible but unprecedented)
├── Reverse stress testing (what would kill us?)
└── Emerging risks (new threats not yet realized)

STEP 2: MODEL TRANSMISSION CHANNELS
├── Direct price impact (how much does asset X move?)
├── Correlation changes (which correlations spike/break?)
├── Liquidity impact (can we exit positions?)
├── Margin/funding impact (do we face margin calls?)
└── Operational impact (do systems/exchanges still work?)

STEP 3: QUANTIFY PORTFOLIO IMPACT
├── Mark-to-market loss
├── Realized loss (if positions must be closed)
├── Margin call amount
├── Funding gap
└── Maximum drawdown path

STEP 4: DEFINE RESPONSE PLAYBOOKS
├── Pre-positioned hedges for each scenario
├── Automatic triggers (circuit breakers)
├── Manual escalation procedures
├── Communication plan (stakeholders)
└── Recovery criteria (when to re-enter)

STEP 5: BACKTEST & ITERATE
├── Run scenarios monthly
├── Compare predicted vs. actual impact during real events
├── Update models based on new data
└── Add new scenarios as risks emerge
```

---

## 7. Lessons Synthesis

### 7.1 Universal Crisis Patterns

From analyzing all the crises above, these patterns are universal:

| Pattern | Description | Frequency |
|---|---|---|
| **Liquidity withdrawal** | Market makers exit precisely when needed most | Every crisis |
| **Correlation convergence** | "Diversified" portfolios move in lockstep | 90% of crises |
| **Leverage cascade** | Forced selling begets more forced selling | 80% of crises |
| **Contagion** | Problems in one market spread to others | 85% of crises |
| **False bottom** | Initial recovery followed by second leg down | 60% of crises |
| **Policy response** | Central bank intervention stabilizes markets (eventually) | 95% of crises |
| **Speed increase** | Each crisis is faster than the last (algorithmic acceleration) | Trend |

### 7.2 Alpha Stack Survival Principles

1. **Assume the worst.** Every "impossible" event has eventually happened. Model for it.
2. **Liquidity is oxygen.** Without it, nothing else matters. Always maintain cash reserves.
3. **Correlations lie.** They look good in calm markets and disappear in crises.
4. **Speed kills.** Automated circuit breakers are essential — humans are too slow.
5. **Size is risk.** The #1 predictor of survival is position sizing, not entry timing.
6. **Hedges are insurance.** They cost money in calm markets. Pay the premium.
7. **Exchanges are counterparty risk.** Diversify, verify, and limit exposure.
8. **Central banks matter.** Their actions can reverse any technical setup.
9. **Fat tails are real.** Gaussian models underestimate extreme events by 100-1000x.
10. **The recovery is the opportunity.** Crisis = opportunity for those who survive.

### 7.3 Alpha Stack Crisis Readiness Checklist

```
PRE-CRISIS (BUILD DURING CALM):
□ Circuit breakers tested and operational
□ Drawdown limits configured at all levels
□ Correlation monitoring active
□ News/sentiment detection pipeline live
□ Emergency stop-loss procedures documented
□ Stress tests run monthly with current portfolio
□ Cash reserve maintained (minimum 20% of portfolio)
□ Exchange diversification (no single exchange >5%)
□ Hedge positions sized appropriately
□ Historical scenario responses pre-programmed

DURING CRISIS:
□ Circuit breakers trigger automatically
□ Position reduction algorithm activates
□ Correlation monitoring detects regime change
□ News feed confirms crisis signal
□ All actions logged for post-crisis review
□ Human operator notified (if escalation needed)
□ Communication to stakeholders initiated

POST-CRISIS:
□ Review all automated actions
□ Compare predicted vs. actual drawdown
□ Update stress test scenarios
□ Adjust circuit breaker thresholds if needed
□ Document lessons learned
□ Identify new risk factors
□ Plan re-entry criteria
□ Update this document
```

---

## Appendix: Crisis Timeline & Market Impact

```
YEAR  EVENT                    EQUITY IMPACT    CURRENCY IMPACT    DURATION    RECOVERY
1992  Black Wednesday          -2% (UK)         GBP -15%           1 day       6 months
1997  Asian Crisis             -40 to -80%      EM FX -50-85%      18 months   3-5 years
1998  LTCM / Russia            -20%             RUB -70%           3 months    6 months
2000  Dot-com crash            -78% (NASDAQ)    Moderate           30 months   7 years
2008  Global Financial Crisis  -57% (S&P)       Mixed              18 months   4 years
2010  Flash Crash              -9.2% (5 min)    None               36 min      Same day
2015  CHF Unpeg                Minimal equities CHF +30%           2 hours     Permanent
2015  China/ETF Flash Crash    -5% at open      CNY -3%            15 min      1 week
2018  Turkish Lira             -20% (BIST)      TRY -40%           6 months    Partial
2020  COVID Crash              -34% (S&P)       USD strength       23 days     5 months
2022  LUNA/UST                 -99.99% (LUNA)   UST depeg          5 days      Never
2022  FTX Collapse             -25% (BTC)       N/A                10 days     14 months
2022  Russia-Ukraine           -45% (MOEX)      RUB -50% (initial) Ongoing     Partial
```

---

*"The market can stay irrational longer than you can stay solvent." — John Maynard Keynes*

*"In a crisis, all correlations go to one." — Every risk manager ever*

*"The time to repair the roof is when the sun is shining." — John F. Kennedy*

---

> **Document maintained by:** Alpha Stack Research Division
> **Review cadence:** Quarterly, or after any crisis event
> **Next review:** 2026-10-11
