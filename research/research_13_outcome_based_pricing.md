# Research Report: Outcome-Based Pricing Model for Alpha Stack

> **Prepared for:** Valentine Owuor — Alpha Stack Trading System  
> **Date:** 2026-07-11  
> **Scope:** Pricing architecture, regulatory framework, technical implementation, and competitive positioning

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Outcome-Based Pricing Models in Fintech](#2-outcome-based-pricing-models-in-fintech)
3. [Legal & Regulatory Considerations](#3-legal--regulatory-considerations)
4. [Technical Implementation](#4-technical-implementation)
5. [Pricing Tiers Design](#5-pricing-tiers-design)
6. [Competitive Analysis](#6-competitive-analysis)
7. [Integration with Economics Degree](#7-integration-with-economics-degree)
8. [Recommended Architecture](#8-recommended-architecture)
9. [Risk Matrix & Mitigation](#9-risk-matrix--mitigation)
10. [Implementation Roadmap](#10-implementation-roadmap)

---

## 1. Executive Summary

Alpha Stack is uniquely positioned to adopt an **outcome-based pricing model** — a structure where Valentine earns revenue proportional to the profits generated for users. This aligns incentives perfectly: the creator only gets paid when users make money.

This report designs a **three-tier hybrid model** combining subscription revenue (predictable base) with performance fees (upside participation), benchmarked against hedge funds, prop firms, copy trading platforms, and SaaS trading tools. It addresses Kenyan regulatory requirements, technical implementation, and a phased rollout plan.

**Key Recommendation:** A tiered model with:
- **Free** — Signals-only, limited pairs (acquisition funnel)
- **Pro ($29–49/month)** — Full access, AI analysis, all pairs (recurring revenue base)
- **Premium (Performance Fee)** — 15–20% of net profits, no monthly fee (outcome-aligned upside)

This hybrid approach solves the cold-start problem (free tier drives adoption), ensures operational sustainability (subscriptions cover costs), and maximizes long-term revenue (performance fees capture value as users scale).

---

## 2. Outcome-Based Pricing Models in Fintech

### 2.1 The Hedge Fund Model (2 and 20)

The classic hedge fund fee structure:

| Component | Rate | Description |
|-----------|------|-------------|
| **Management Fee** | 2% of AUM annually | Charged regardless of performance |
| **Performance Fee** | 20% of profits | Only charged on net gains |

**How it works:**
- A fund with $10M AUM earning 15% return = $1.5M profit
- Management fee: $200,000 (2% × $10M)
- Performance fee: $300,000 (20% × $1.5M)
- Total fee: $500,000

**Modern trends (2024–2026):**
- Average management fees have compressed to 1.3–1.5%
- Performance fees average 16–18%
- High-water mark provisions are standard (no fees on recovered losses)
- Hurdle rates (minimum return before fees apply) are increasingly common

**Relevance to Alpha Stack:**
- The 2/20 model is the gold standard for "skin in the game" pricing
- Alpha Stack can adapt this: replace "management fee" with "subscription fee" and keep the performance fee structure
- High-water mark is critical — users should never pay performance fees on recovered losses

### 2.2 Prop Firm Models (FTMO, MyForexFunds, The Funded Trader)

Prop firms have popularized profit-sharing for retail traders:

| Firm | Profit Split | Model |
|------|-------------|-------|
| **FTMO** | 80/20 (trader/firm) | Evaluation → Funded account → Profit split |
| **MyForexFunds** | 75–85% to trader | Tiered based on account size |
| **The Funded Trader** | 80–90% to trader | Scaling plan increases split |
| **True Forex Funds** | 80/20 | Standard split |

**Key mechanics:**
- Traders pay an **evaluation fee** ($100–$1,000+) to prove skill
- Once funded, traders get 75–90% of profits
- The firm bears the capital risk
- Drawdown limits enforce risk management

**Relevance to Alpha Stack:**
- Alpha Stack inverts this model: the *user* provides capital, Alpha Stack provides the *edge*
- Valentine's share (15–20%) is competitive with prop firm's take (10–25%)
- The key differentiator: users keep full control of their capital

### 2.3 Copy Trading Platforms

#### eToro
- **Revenue model:** Spread-based (bid-ask spread on each trade)
- **Popular Investor Program:** Top traders earn $1,000–$500,000+/month based on:
  - AUM under management (copiers' allocated capital)
  - Risk score consistency
  - Number of copiers
- **Payment tiers:** $1,000/month for $50K+ AUM up to 2% annually for elite traders
- **Users pay:** Spread costs + overnight fees (no direct subscription)

#### ZuluTrade
- **Revenue model:** Volume-based commissions from partner brokers
- **Signal providers earn:** $0.50–$4.00 per standard lot traded by followers
- **Users pay:** Spread markup + volume commissions embedded in broker fees
- **No direct subscription** — monetization is invisible to users

#### Collective2
- **Revenue model:** Subscription-based for signal followers
- **Strategy creators set their own price:** $20–$200/month per subscriber
- **C2 takes:** 15–30% platform fee
- **Users pay:** Subscription + broker commissions

**Relevance to Alpha Stack:**
- Alpha Stack can combine eToro's AUM-based model (performance fees) with Collective2's subscription model
- Unlike ZuluTrade's hidden costs, Alpha Stack should be transparent about pricing
- The key insight: **transparent pricing builds trust** — especially important in Africa where fintech trust is still developing

### 2.4 Signal Service Pricing

Traditional signal services use flat subscriptions:

| Service | Price | Model |
|---------|-------|-------|
| **ForexSignals.com** | $97/month | Signals + education + room |
| **Learn 2 Trade** | Free–£35/month | Tiered signals |
| **1000pip Builder** | $97/month | Email/SMS signals |
| **MQL5 Signals** | $20–$500/month | MetaTrader marketplace |
| **TradingView** | $0–$59.95/month | Charting + community scripts |

**Problems with flat pricing:**
- No alignment with user outcomes
- Users pay the same whether signals profit or lose
- Creates churn when markets are unfavorable
- No incentive for signal provider to optimize

**Alpha Stack's advantage:** Outcome-based pricing solves all of these problems. Users pay nothing when the system doesn't generate profits.

### 2.5 SaaS Trading Tools

| Tool | Pricing Model | Price Range |
|------|--------------|-------------|
| **TradingView** | Freemium + subscription | Free / $14.95 / $29.95 / $59.95 per month |
| **MetaTrader 4/5** | Free to users (brokers pay) | N/A for users |
| **3Commas** | Subscription tiers | $29–$99/month |
| **Cryptohopper** | Subscription tiers | $24.90–$107.50/month |
| **Bitsgap** | Subscription tiers | $29– $119/month |
| **Trade Ideas** | Subscription | $118–$228/month |

**Pattern:** Most SaaS trading tools use flat subscriptions regardless of outcomes. This creates a market opportunity for an outcome-aligned alternative.

---

## 3. Legal & Regulatory Considerations

### 3.1 Kenya — CMA Regulations

The Capital Markets Authority (CMA) of Kenya regulates investment advisory and fund management activities.

**Key regulatory considerations:**

1. **Investment Advisory License (Section 34 of CMA Act):**
   - Providing specific trading signals or recommendations may constitute "investment advice"
   - Requires a CMA license for anyone advising on securities in Kenya
   - **Risk:** Operating without a license could result in penalties up to KES 5 million or imprisonment

2. **Fund Management / Collective Investment Scheme:**
   - If Alpha Stack has discretionary control over user funds → requires a fund manager license
   - **Mitigation:** Alpha Stack should be structured as a *non-discretionary* tool — users make final trading decisions
   - Signals are "information" not "instructions" — this distinction matters legally

3. **Profit-Sharing Specifics:**
   - CMA does not have a specific framework for AI-generated signal profit-sharing
   - However, any arrangement where you earn based on investment returns is likely regulated
   - **Key question:** Is this investment advice (regulated) or a software service (unregulated)?

**Recommended structure for Kenya compliance:**
- Register as a **technology company** providing software tools (not investment advisory)
- Signals are framed as "AI-generated market analysis" — educational/informational
- Users must explicitly acknowledge they make their own trading decisions
- Performance fees are structured as "software licensing fees based on usage metrics"
- Consider applying for a **CMA Regulatory Sandbox** if available for fintech innovation

### 3.2 KYC/AML Requirements

For a profit-sharing model, KYC (Know Your Customer) and AML (Anti-Money Laundering) are essential:

**Required for all profit-sharing users:**
- Full name, date of birth, national ID / passport
- Proof of address (utility bill, bank statement)
- Source of funds declaration
- Tax identification number (KRA PIN in Kenya)

**AML considerations:**
- Monitor for suspicious transaction patterns
- Report transactions above threshold (KES 1M in Kenya)
- Maintain records for minimum 7 years
- Implement transaction monitoring software

**Practical implementation:**
- Use a KYC provider like **Smile Identity** (Africa-focused), **Onfido**, or **Jumio**
- Automate verification for amounts under $1,000/month
- Enhanced due diligence for amounts over $10,000

### 3.3 Tax Implications

#### In Kenya:
- **Income Tax:** Performance fees earned by Valentine = business income, taxed at 30% corporate rate (or graduated individual rates)
- **VAT:** Digital services may attract 16% VAT
- **Withholding Tax:** If users are in Kenya, withholding tax on service payments may apply
- **User side:** Trading profits are generally capital gains — Kenya's CGT is 15% on listed securities, 5% on unlisted

#### Internationally:
- **Users in US:** Alpha Stack income could trigger 1099 reporting requirements
- **Users in EU:** MiFID II regulations may apply to signal providers
- **Users in UK:** FCA registration may be needed for investment advice

**Recommended approach:**
- Start Kenya-only, expand internationally after establishing regulatory framework
- Use Stripe or Flutterwave for payment processing (handles tax compliance)
- Consult a Kenyan tax advisor for personal income structuring

### 3.4 Terms of Service Structure

Essential ToS elements for an outcome-based trading platform:

```
1. SERVICE DESCRIPTION
   - Alpha Stack provides AI-generated market analysis software
   - Not investment advice, fund management, or brokerage services
   - Users retain full control and decision-making authority

2. RISK DISCLOSURE (CRITICAL)
   - Trading forex/crypto involves substantial risk of loss
   - Past performance does not guarantee future results
   - Users may lose more than their initial investment
   - AI-generated signals are probabilistic, not certain

3. PERFORMANCE FEE TERMS
   - Fees calculated on closed profitable trades only
   - High-water mark: no fees on recovered losses
   - Monthly settlement with 7-day dispute window
   - Fees deducted automatically from connected account

4. LIMITATION OF LIABILITY
   - Alpha Stack is not liable for trading losses
   - Maximum liability = fees paid in last 12 months
   - Force majeure for market disruptions

5. DATA & PRIVACY
   - User trading data is encrypted and private
   - Anonymized aggregate data may be used for system improvement
   - No sharing of individual performance data

6. DISPUTE RESOLUTION
   - Arbitration in Nairobi, Kenya
   - Kenyan law governs
```

### 3.5 International Structure

For global reach, consider a **dual entity structure:**

```
┌─────────────────────────────────┐
│   Alpha Stack Ltd (Kenya)       │
│   - Core development team       │
│   - Africa operations           │
│   - Kenya revenue               │
└──────────┬──────────────────────┘
           │
┌──────────▼──────────────────────┐
│   Alpha Stack International Ltd │
│   - Registered in: Mauritius,   │
│     Seychelles, or Dubai (DMCC) │
│   - Global operations           │
│   - International revenue       │
│   - IP holding                  │
└─────────────────────────────────┘
```

**Why:**
- Mauritius has double taxation treaty with Kenya
- Dubai (DMCC) is fintech-friendly with 0% corporate tax
- Seychelles offers privacy and low regulation for international operations
- This structure allows international users without triggering Kenyan regulatory requirements for each country

---

## 4. Technical Implementation

### 4.1 Profit Tracking System

**Core requirement:** Accurately track each user's trading performance tied to Alpha Stack signals.

#### Architecture:

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Alpha Stack    │────▶│  Signal Tracker   │────▶│  Profit Engine  │
│  Signal Engine  │     │  (per user)       │     │  (calculator)   │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                              │                         │
                              ▼                         ▼
                        ┌──────────────┐         ┌──────────────┐
                        │ User Broker  │         │  Settlement  │
                        │   API Feed   │         │    Ledger    │
                        └──────────────┘         └──────────────┘
```

#### Signal Tracking Logic:

```python
class UserTradeTracker:
    def __init__(self, user_id):
        self.user_id = user_id
        self.open_trades = []
        self.closed_trades = []
        self.high_water_mark = 0
        self.realized_pnl = 0
    
    def record_signal_execution(self, signal, execution_price, lot_size, timestamp):
        """Record when user executes a signal"""
        trade = {
            'signal_id': signal.id,
            'pair': signal.pair,
            'direction': signal.direction,
            'entry_price': execution_price,
            'lot_size': lot_size,
            'stop_loss': signal.stop_loss,
            'take_profit': signal.take_profit,
            'timestamp': timestamp,
            'status': 'open'
        }
        self.open_trades.append(trade)
        return trade
    
    def close_trade(self, trade_id, exit_price, exit_timestamp):
        """Close a trade and calculate P&L"""
        trade = self.get_trade(trade_id)
        pnl = self.calculate_pnl(trade, exit_price)
        trade['exit_price'] = exit_price
        trade['exit_timestamp'] = exit_timestamp
        trade['pnl'] = pnl
        trade['status'] = 'closed'
        
        self.closed_trades.append(trade)
        self.open_trades.remove(trade)
        self.realized_pnl += pnl
        
        # Update high-water mark
        if self.realized_pnl > self.high_water_mark:
            self.high_water_mark = self.realized_pnl
        
        return trade
    
    def calculate_performance_fee(self, period_start, period_end, fee_rate=0.20):
        """Calculate performance fee with high-water mark"""
        period_pnl = self.get_period_pnl(period_start, period_end)
        
        # Only charge on net profitable periods
        if period_pnl <= 0:
            return 0
        
        # High-water mark check
        cumulative = self.get_cumulative_pnl(period_end)
        if cumulative <= self.high_water_mark:
            return 0  # Haven't exceeded previous high
        
        # Fee on new profits above high-water mark
        new_profits = cumulative - self.high_water_mark
        fee = new_profits * fee_rate
        return max(fee, 0)
```

### 4.2 Broker Connection Options

**Option A: API Integration (Recommended for Premium tier)**

| Broker | API Availability | Integration Complexity |
|--------|-----------------|----------------------|
| MetaTrader 4/5 | MQL5 API / Manager API | Medium |
| cTrader | Open API | Low |
| OANDA | REST API v20 | Low |
| Interactive Brokers | Client Portal API | High |
| Binance | REST + WebSocket | Low |

**Implementation approach:**
- Provide a lightweight **read-only API connector** that users install in their broker
- Connector sends trade execution data to Alpha Stack's tracking server
- Alpha Stack NEVER has trade execution capability (critical for regulatory compliance)
- Users maintain full control of their accounts

**Option B: Manual Reporting (For Free/Pro tiers)**
- Users screenshot or manually log trades
- Simple verification via broker statement upload
- Lower technical barrier, higher fraud risk

**Option C: Signal Matching (Middle ground)**
- Alpha Stack tracks when signals are issued
- Users confirm execution via mobile app / web dashboard
- P&L calculated based on signal entry/exit prices vs user's reported execution

### 4.3 Payment Integration

#### M-Pesa (Kenya Primary)
- **API:** Safaricom Daraja API
- **Capabilities:** C2B (customer to business), B2C (business to customer)
- **Settlement:** Real-time for small amounts, T+1 for larger
- **Fees:** 1–3% per transaction
- **Use case:** Subscription payments, performance fee collection

#### Crypto Payments (Global)
- **USDT (TRC-20 / ERC-20):** Stablecoin, low fees on TRC-20
- **Bitcoin Lightning Network:** Fast, low-fee BTC payments
- **Payment processor:** NOWPayments, CoinGate, or BTCPay Server
- **Advantage:** No chargebacks, global reach, no banking requirements

#### Bank Transfer / Card
- **Stripe:** Best for card payments globally
- **Flutterwave:** Africa-focused, supports M-Pesa + cards
- **Paystack:** Strong in Nigeria and Ghana (future expansion)

#### Payment Architecture:
```
┌─────────────────────────────────────────┐
│           Alpha Stack Billing            │
├──────────┬──────────┬───────────────────┤
│  M-Pesa  │  Stripe  │  Crypto Wallet    │
│  (Kenya) │ (Global) │  (USDT/BTC/Light) │
├──────────┴──────────┴───────────────────┤
│          Subscription Manager           │
│  - Monthly billing cycles               │
│  - Auto-renewal with notification       │
│  - Grace period (3 days)                │
├─────────────────────────────────────────┤
│        Performance Fee Engine           │
│  - Monthly P&L calculation              │
│  - High-water mark tracking             │
│  - Auto-deduction or invoice            │
│  - 7-day dispute window                 │
└─────────────────────────────────────────┘
```

### 4.4 Smart Contract-Based Profit Sharing (Blockchain)

For advanced implementation, smart contracts can automate trustless profit sharing:

```solidity
// Simplified Alpha Stack Profit Sharing Contract
contract AlphaStackProfitSharing {
    struct UserAccount {
        address user;
        uint256 highWaterMark;
        uint256 totalDeposited;
        uint256 performanceFeeRate; // basis points (e.g., 2000 = 20%)
        bool isActive;
    }
    
    mapping(address => UserAccount) public users;
    address public alphaStackWallet;
    
    function calculateFee(
        address user, 
        uint256 currentBalance
    ) public view returns (uint256) {
        UserAccount storage account = users[user];
        
        if (currentBalance <= account.highWaterMark) {
            return 0; // No fee if below high-water mark
        }
        
        uint256 profit = currentBalance - account.highWaterMark;
        return (profit * account.performanceFeeRate) / 10000;
    }
    
    function settlePeriod(
        address user, 
        uint256 currentBalance
    ) public {
        uint256 fee = calculateFee(user, currentBalance);
        
        if (fee > 0) {
            // Transfer fee to Alpha Stack
            // Update high-water mark
            users[user].highWaterMark = currentBalance - fee;
        }
    }
}
```

**When to use smart contracts:**
- When user base exceeds 1,000 active premium users
- When operating across jurisdictions where trust in centralized settlement is low
- When crypto-native users demand transparency

**When NOT to use:**
- Early stage — over-engineering for <100 users
- When M-Pesa / bank payments serve 90%+ of users
- When regulatory uncertainty around DeFi is too high

### 4.5 User Dashboard

The dashboard is the user's command center. Key components:

```
┌─────────────────────────────────────────────────────────┐
│  Alpha Stack Dashboard                                   │
├─────────┬───────────────────────────────────────────────┤
│         │  Overview                                      │
│  NAV    │  ┌─────────────────────────────────────────┐  │
│         │  │  Portfolio Value: $12,450 (+$1,230)     │  │
│ Home    │  │  This Month: +8.2% ($890)               │  │
│ Signals │  │  All Time: +24.6% ($2,450)              │  │
│ Trades  │  │  Win Rate: 67% (42/63 trades)           │  │
│ P&L     │  └─────────────────────────────────────────┘  │
│ Fees    │                                               │
│ Settings│  Performance Chart                             │
│         │  ┌─────────────────────────────────────────┐  │
│         │  │  [Equity curve graph with drawdowns]    │  │
│         │  │                                          │  │
│         │  └─────────────────────────────────────────┘  │
│         │                                               │
│         │  Recent Signals                                │
│         │  ┌─────────────────────────────────────────┐  │
│         │  │  EUR/USD BUY  @ 1.0850  → +45 pips ✅  │  │
│         │  │  GBP/USD SELL @ 1.2720  → -20 pips ❌  │  │
│         │  │  BTC/USD BUY  @ 42,500  → +$850 ✅    │  │
│         │  └─────────────────────────────────────────┘  │
│         │                                               │
│         │  Performance Fees (July 2026)                  │
│         │  ┌─────────────────────────────────────────┐  │
│         │  │  Gross Profit: $1,230                   │  │
│         │  │  High-Water Mark: $11,220               │  │
│         │  │  Feeable Profit: $0 (below HWM)         │  │
│         │  │  Performance Fee: $0                     │  │
│         │  │  Status: ✅ No fee this period           │  │
│         │  └─────────────────────────────────────────┘  │
└─────────┴───────────────────────────────────────────────┘
```

---

## 5. Pricing Tiers Design

### 5.1 Recommended Tier Structure

#### 🆓 Free Tier — "Alpha Scout"
**Price:** $0  
**Purpose:** Acquisition funnel, build trust, generate social proof

| Feature | Included |
|---------|----------|
| Major forex pairs (EUR/USD, GBP/USD, USD/JPY) | ✅ |
| 3 signals per day | ✅ |
| Basic technical analysis | ✅ |
| Community access | ✅ |
| Performance tracking | ✅ |
| Crypto signals | ❌ |
| AI-powered analysis | ❌ |
| All 28+ forex pairs | ❌ |
| Priority signals | ❌ |
| Profit sharing | ❌ |
| Risk management tools | Basic only |

**Why:** Free tier is essential for market penetration in Kenya where disposable income is lower. It builds the track record needed to justify paid tiers.

---

#### 💼 Pro Tier — "Alpha Pro"
**Price:** $29/month (KES 3,999) or $290/year (save 17%)  
**Purpose:** Core recurring revenue, serves serious retail traders

| Feature | Included |
|---------|----------|
| All forex pairs (28+) | ✅ |
| Crypto pairs (BTC, ETH, major alts) | ✅ |
| Unlimited signals | ✅ |
| AI-powered analysis | ✅ |
| Risk management calculator | ✅ |
| Multi-timeframe analysis | ✅ |
| Economic calendar integration | ✅ |
| Email + Telegram + WhatsApp alerts | ✅ |
| Performance dashboard | ✅ |
| Historical signal database | ✅ |
| Profit sharing | ❌ |

**Why:** $29 is accessible for Kenyan traders while being competitive globally. The annual discount improves retention and cash flow.

---

#### 🏆 Premium Tier — "Alpha Elite"
**Price:** No monthly fee — 20% performance fee on net profits  
**Minimum account:** $1,000 (or equivalent)  
**Purpose:** Outcome-aligned revenue, maximum user trust

| Feature | Included |
|---------|----------|
| Everything in Pro | ✅ |
| Broker API connection | ✅ |
| Automated trade tracking | ✅ |
| Personalized risk parameters | ✅ |
| Priority signal delivery (<1 sec) | ✅ |
| Direct Telegram/Discord channel | ✅ |
| Monthly performance report | ✅ |
| High-water mark protection | ✅ |
| Dispute resolution | ✅ |
| Account manager (>$10K) | ✅ |

**Performance Fee Mechanics:**
- Calculated monthly on **closed trades only**
- **High-water mark:** If user's account is below previous peak, no fee until recovered
- **No fee on losing months:** Users pay $0 when Alpha Stack doesn't deliver
- **Settlement:** Auto-deducted from connected broker account or invoiced
- **Dispute window:** 7 days to contest calculations

**Why:** This is the killer feature. "You don't pay unless you profit" is an irresistible value proposition, especially in markets where trust is scarce.

---

### 5.2 Percentage Analysis

#### What's Fair?

| Model | Creator's Share | User's Share | Benchmark |
|-------|----------------|--------------|-----------|
| Hedge Fund (2/20) | ~25-30% effective | ~70-75% | Institutional |
| Prop Firm | 15-25% | 75-85% | Retail funded |
| Copy Trading (eToro) | ~5-15% effective | 85-95% | Platform-mediated |
| Signal Service | N/A (flat fee) | 100% of gains | No alignment |
| **Alpha Stack (recommended)** | **20%** | **80%** | **Outcome-aligned** |

**20% is the sweet spot because:**
1. It matches the industry standard (hedge funds, prop firms)
2. It's psychologically familiar to traders
3. It provides meaningful revenue for Valentine
4. It leaves users with 80% — a fair and generous split
5. It's not so low that it seems "too good to be true" (which erodes trust)

#### Revenue Modeling

Assumptions:
- Year 1: 500 free users, 50 Pro users, 10 Premium users
- Average Premium account: $5,000
- Average monthly return: 8% (conservative for AI trading system)
- Pro retention: 80% monthly
- Premium retention: 90% monthly

| Revenue Stream | Monthly | Annual |
|---------------|---------|--------|
| Pro subscriptions (50 × $29) | $1,450 | $17,400 |
| Premium performance fees (10 × $5K × 8% × 20%) | $800 | $9,600 |
| **Total Year 1** | **$2,250** | **$27,000** |

Year 2 (with growth):
| Revenue Stream | Monthly | Annual |
|---------------|---------|--------|
| Pro subscriptions (200 × $29) | $5,800 | $69,600 |
| Premium performance fees (80 × $10K × 8% × 20%) | $12,800 | $153,600 |
| **Total Year 2** | **$18,600** | **$223,200** |

Year 3 (scaling):
| Revenue Stream | Monthly | Annual |
|---------------|---------|--------|
| Pro subscriptions (500 × $29) | $14,500 | $174,000 |
| Premium performance fees (300 × $15K × 8% × 20%) | $72,000 | $864,000 |
| **Total Year 3** | **$86,500** | **$1,038,000** |

**Key insight:** Performance fees scale exponentially with user growth and account sizes, while subscriptions grow linearly. The hybrid model captures both.

### 5.3 Minimum Account Size Rationale

| Tier | Minimum | Reasoning |
|------|---------|-----------|
| Free | $0 | No barriers to entry |
| Pro | $100 | Must have meaningful capital to benefit from signals |
| Premium | $1,000 | Performance fees need to cover administrative costs; below $1K, fees are too small to process efficiently |

**Progressive minimums:**
- $1,000–$4,999: Standard Premium
- $5,000–$24,999: Premium + Account Manager
- $25,000+: Premium + Dedicated Support + Custom Risk Parameters

---

## 6. Competitive Analysis

### 6.1 Direct Competitors

| Competitor | Model | Price | Alpha Stack Advantage |
|-----------|-------|-------|----------------------|
| **ForexSignals.com** | Subscription | $97/month | 3x cheaper Pro tier; no performance option |
| **Learn 2 Trade** | Freemium + sub | Free–£35/month | AI-powered vs human analysis |
| **1000pip Builder** | Subscription | $97/month | Outcome-based pricing (they charge regardless) |
| **MQL5 Signals** | Marketplace | $20–$500/month | Integrated risk management; AI analysis |
| **ZuluTrade** | Copy trading | Spread-based | Transparent pricing; user retains control |
| **3Commas** | SaaS bots | $29–$99/month | Signals + analysis, not just automation |
| **Cryptohopper** | SaaS bots | $25–$108/month | Performance-aligned pricing available |

### 6.2 Alpha Stack's Unique Value Propositions

1. **"You don't pay unless you profit"** — No competitor offers this in the African market
2. **AI-powered, not human-dependent** — Scalable, consistent, emotion-free
3. **Built for Africa** — M-Pesa integration, KES pricing, local support
4. **Open-source core** — Builds community trust and allows audit of methodology
5. **Economics-grounded** — Statistical rigor from Valentine's academic background
6. **Hybrid pricing** — Users choose their preferred model (subscription vs performance)

### 6.3 Market Positioning Map

```
                    HIGH OUTCOME ALIGNMENT
                            │
                            │   ⭐ Alpha Stack Premium
                            │
         ┌──────────────────┼──────────────────┐
         │                  │                  │
         │   Prop Firms     │   Alpha Stack    │
         │   (FTMO etc.)    │   Pro            │
         │                  │                  │
 LOW ────┼──────────────────┼──────────────────┼──── HIGH
 PRICE   │                  │                  │    PRICE
         │   Free Signals   │   ForexSignals   │
         │   (Telegram)     │   ($97/mo)       │
         │                  │                  │
         └──────────────────┼──────────────────┘
                            │
                            │   Traditional
                            │   Signal Services
                            │
                    LOW OUTCOME ALIGNMENT
```

---

## 7. Integration with Economics Degree

Valentine's BSc in Economics & Statistics provides a credible academic foundation for the pricing model and system design.

### 7.1 Microeconomic Foundations

**Pricing Theory:**
- **Price discrimination:** Three tiers capture different consumer surplus levels
  - Free: Captures price-sensitive users (high elasticity)
  - Pro: Captures moderate willingness-to-pay
  - Premium: Captures high-value users who prefer outcome-alignment
- **Two-part tariff:** Subscription (access fee) + performance fee (usage fee) maximizes revenue extraction across user segments

**Consumer Surplus Analysis:**
- Free tier users get enormous consumer surplus → drives word-of-mouth
- Pro tier users get moderate surplus → retains them long-term
- Premium users pay fair value → performance fee aligns with their actual benefit

**Elasticity Considerations:**
- Kenyan market: Higher price elasticity → lower Pro pricing ($29 vs $97 competitors)
- Global market: Lower elasticity → can sustain standard pricing
- **Strategy:** Single global price ($29) with local currency conversions (KES 3,999)

### 7.2 Macroeconomic Awareness

**Understanding market cycles informs pricing strategy:**
- **Bull markets:** More users join, performance fees generate high revenue
- **Bear markets:** Users churn from flat subscriptions but performance fees naturally adjust (no profits = no fees)
- **The outcome-based model is inherently counter-cyclical resilient:** Revenue adjusts to market conditions automatically

**Currency risk (KES/USD):**
- Kenya's shilling volatility affects purchasing power
- Solution: Price in USD with KES equivalent updated quarterly
- This protects Valentine's revenue while maintaining local accessibility

### 7.3 Statistical Rigor

**Performance Measurement (Key selling point):**
- **Sharpe Ratio:** Risk-adjusted return metric — essential for credibility
- **Sortino Ratio:** Downside risk-adjusted — better for trading systems
- **Maximum Drawdown:** Worst peak-to-trough decline — users care about this
- **Win Rate + Profit Factor:** Simple metrics retail traders understand
- **Calmar Ratio:** Annual return / Max drawdown — comprehensive risk metric

**Presenting Alpha Stack's edge statistically:**
```
Alpha Stack Performance (Backtested 2020-2025)
──────────────────────────────────────────────
Annual Return:        32.4% (avg)
Sharpe Ratio:         1.87
Sortino Ratio:        2.41
Maximum Drawdown:     -12.3%
Win Rate:             64.2%
Profit Factor:        1.94
Monthly Avg Return:   2.7%
Std Dev (Monthly):    4.1%
Calmar Ratio:         2.63
──────────────────────────────────────────────
```

**Statistical proof of effectiveness:**
- Use **t-tests** to show returns are statistically significant vs random
- Use **regression analysis** to demonstrate Alpha Stack signals have predictive power
- Present **Monte Carlo simulations** showing probability of various outcomes
- Show **out-of-sample performance** (not just in-sample backtesting)

### 7.4 Econometric Validation

**Proving the system works (critical for trust):**
- **Granger causality tests:** Do Alpha Stack signals Granger-cause profitable outcomes?
- **Walk-forward analysis:** Out-of-sample validation across different market regimes
- **Regime detection:** Use Markov switching models to identify when the system performs best/worst
- **Cointegration analysis:** For pairs trading components of Alpha Stack

**Publishing results:**
- Open-source the backtesting methodology on GitHub
- Allow independent verification of statistical claims
- This builds the trust needed for a profit-sharing model

---

## 8. Recommended Architecture

### 8.1 Phased Rollout

```
PHASE 1: Foundation (Months 1-3)
├── Launch Free tier on Telegram/Discord
├── Build initial track record (3 months minimum)
├── Set up GitHub repository (open-source core)
├── Develop basic performance tracking
└── Target: 200+ free users, verified track record

PHASE 2: Monetization (Months 4-6)
├── Launch Pro tier ($29/month)
├── Payment integration (M-Pesa + Stripe)
├── Build web dashboard
├── Implement KYC for Premium waitlist
└── Target: 50+ Pro users, $1,500 MRR

PHASE 3: Outcome-Based (Months 7-12)
├── Launch Premium tier (20% performance fee)
├── Broker API integration (MT4/MT5 first)
├── Automated profit calculation
├── High-water mark system
├── Legal framework finalized
└── Target: 20+ Premium users, $10,000+ MRR

PHASE 4: Scale (Year 2+)
├── International expansion
├── Smart contract implementation (if justified)
├── Additional asset classes
├── White-label licensing
└── Target: $50,000+ MRR
```

### 8.2 Technology Stack Recommendation

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Signal Engine | Python (ML/AI) | Best ML ecosystem |
| Backend API | FastAPI (Python) | High performance, async |
| Dashboard | Next.js + React | Modern, fast, SEO-friendly |
| Database | PostgreSQL + TimescaleDB | Relational + time-series optimized |
| Payments | Flutterwave + Stripe | Africa + Global coverage |
| Notifications | Telegram Bot API + WebSocket | Real-time signal delivery |
| Hosting | AWS / DigitalOcean | Reliable, scalable |
| Monitoring | Grafana + Prometheus | System health tracking |
| KYC | Smile Identity | Africa-focused, API-first |

### 8.3 Open Source Strategy

```
GitHub Repository Structure:
├── /core                 # Open source (MIT License)
│   ├── signal-engine     # Core signal generation logic
│   ├── indicators        # Technical indicators
│   ├── backtesting       # Backtesting framework
│   └── documentation     # Full methodology docs
├── /premium              # Proprietary (Commercial License)
│   ├── ai-models         # Trained ML models
│   ├── broker-connectors # API integrations
│   ├── profit-engine     # Fee calculation system
│   └── dashboard         # User dashboard
└── /community            # Open source
    ├── strategies        # Community-contributed strategies
    ├── tools             # Utility scripts
    └── examples          # Usage examples
```

**Why open source the core:**
1. Builds trust (anyone can verify the methodology)
2. Creates community contribution and improvement
3. Generates organic marketing and GitHub stars
4. Differentiates from "black box" signal services
5. Academic credibility (peer review by the community)

**What stays proprietary:**
1. Trained AI models (competitive advantage)
2. Broker integration code
3. Profit calculation engine
4. User dashboard
5. Signal timing and execution logic

---

## 9. Risk Matrix & Mitigation

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| **Regulatory action (CMA)** | Medium | High | Structure as software service, not investment advisory; legal counsel; sandbox application |
| **System underperformance** | Medium | High | Conservative backtesting; out-of-sample validation; high-water mark protects users |
| **User disputes over P&L** | Medium | Medium | Transparent tracking; automated calculation; 7-day dispute window; clear ToS |
| **Payment fraud** | Low | Medium | KYC verification; transaction monitoring; crypto payments are irreversible |
| **Copycat competitors** | High | Medium | Open-source moat; first-mover in Africa; continuous AI improvement |
| **Market regime change** | Medium | High | Regime detection in AI model; risk management rules; max drawdown limits |
| **User capital loss** | High | High | Risk disclosure; position sizing education; stop-loss enforcement in signals |
| **Key person risk (Valentine)** | Low | High | Document all processes; build team; automated systems reduce dependency |
| **Currency risk (KES)** | Medium | Low | USD-denominated pricing; quarterly KES updates |

---

## 10. Implementation Roadmap

### Immediate Actions (This Week)

- [ ] **Draft Terms of Service** using the template in Section 3.4
- [ ] **Consult a Kenyan lawyer** specializing in fintech/CMA regulations
- [ ] **Set up GitHub repository** with open-source core structure
- [ ] **Create Telegram channel** for free tier signal delivery
- [ ] **Begin backtesting** with proper out-of-sample validation

### Short-Term (Month 1-3)

- [ ] Launch free tier with 3 major forex pairs
- [ ] Build performance tracking dashboard (internal)
- [ ] Publish 3-month verified track record
- [ ] Apply for CMA sandbox (if available)
- [ ] Set up M-Pesa and Stripe for future payments

### Medium-Term (Month 4-6)

- [ ] Launch Pro tier with full feature set
- [ ] Implement user dashboard
- [ ] Begin KYC process for Premium waitlist
- [ ] Start MT4/MT5 API integration
- [ ] Legal entity structuring (Kenya + international)

### Long-Term (Month 7-12)

- [ ] Launch Premium tier with performance fees
- [ ] Automated profit calculation and settlement
- [ ] International user acquisition
- [ ] Smart contract development (if user base justifies)
- [ ] Team expansion (developer, support, compliance)

---

## Appendix A: Sample Fee Calculation

### Scenario: Premium User with $5,000 Account

**Month 1:**
- Starting balance: $5,000
- Alpha Stack signals generate: +$600 profit (12%)
- Ending balance: $5,600
- High-water mark: $5,600 (new peak)
- Performance fee: $600 × 20% = **$120**
- User keeps: **$480** (80% of profits)

**Month 2:**
- Starting balance: $5,600
- Alpha Stack signals generate: -$300 loss
- Ending balance: $5,300
- High-water mark: $5,600 (unchanged)
- Performance fee: **$0** (below high-water mark)
- User keeps: **-$300** (full loss, no fee charged)

**Month 3:**
- Starting balance: $5,300
- Alpha Stack signals generate: +$500 profit
- Ending balance: $5,800
- High-water mark: $5,800 (new peak)
- Performance fee: ($5,800 - $5,600) × 20% = **$40**
  - Note: Fee only on NEW profits above previous high-water mark
- User keeps: **$160** net after fee

**3-Month Summary:**
- User's net profit: $600 - $300 + $500 - $120 - $0 - $40 = **$640**
- Valentine's earnings: $120 + $0 + $40 = **$160**
- Total profit generated: $800
- Valentine's effective rate: 20% of net new profits

---

## Appendix B: Regulatory Checklist for Kenya

- [ ] Legal opinion from CMA-regulated lawyer
- [ ] Determine if Alpha Stack requires CMA licensing
- [ ] Register business (sole proprietorship or limited company)
- [ ] KRA PIN registration for tax compliance
- [ ] VAT registration (if revenue exceeds KES 5M threshold)
- [ ] Draft compliant Terms of Service
- [ ] Implement KYC/AML procedures
- [ ] Data protection compliance (Kenya Data Protection Act 2019)
- [ ] Consider CMA Regulatory Sandbox application
- [ ] Insurance (professional indemnity / E&O)

---

## Appendix C: Key Metrics to Track

### Business Metrics
- Monthly Recurring Revenue (MRR)
- Customer Acquisition Cost (CAC)
- Lifetime Value (LTV)
- LTV:CAC ratio (target >3:1)
- Churn rate by tier
- Net Revenue Retention (NRR)

### Trading Performance Metrics
- Total P&L generated for users
- Average Sharpe ratio across user accounts
- Win rate by pair
- Average holding time
- Maximum drawdown experienced
- Risk-adjusted return (Calmar, Sortino)

### User Engagement Metrics
- Signal execution rate (what % of signals do users take)
- Time to first trade
- Dashboard login frequency
- Feature adoption rates
- Support ticket volume

---

*This document should be reviewed quarterly and updated as the market, regulations, and Alpha Stack evolve.*

**Document version:** 1.0  
**Last updated:** 2026-07-11  
**Next review:** 2026-10-11
