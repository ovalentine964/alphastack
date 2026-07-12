# Alpha Stack — Cost Model & Unit Economics Architecture

**Version:** 1.0
**Date:** 2026-07-13
**Status:** Architecture Design
**Dependencies:** Market Focus, TCA Engine, Pricing Strategy

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Design Philosophy](#2-design-philosophy)
3. [Problem Cost Quantification](#3-problem-cost-quantification)
4. [Alpha Stack Value Delivery](#4-alpha-stack-value-delivery)
5. [Unit Economics](#5-unit-economics)
6. [Revenue Architecture](#6-revenue-architecture)
7. [Cost Structure](#7-cost-structure)
8. [Integration Points](#8-integration-points)
9. [Implementation Roadmap](#9-implementation-roadmap)

---

## 1. Executive Summary

### Problem

Retail traders globally lose $50–100 billion annually. In Africa, loss rates are 85–95% (higher than the global 74–89%). The cost includes not just trading losses but transaction fees, time opportunity cost, psychological harm, and signal/course scams. Alpha Stack addresses the root causes: emotional trading, lack of systematic risk management, and information asymmetry.

### Solution

A **value-aligned cost model** where Alpha Stack's revenue is directly proportional to the value it delivers. Outcome-based pricing means users only pay when the system generates profits. This creates a natural unit economic engine: better signals → more user profits → more revenue → more R&D → better signals.

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Pricing model | Outcome-based (10–20% of profits) | Aligned incentives, lowest barrier |
| Revenue target | $300K–$1M ARR in Year 1 | Conservative for 5K–20K users |
| Cost structure | $0 data costs, minimal infra | Free API tiers, run locally at start |
| Value proposition | $11K–$42K/year savings per trader | Eliminates emotional trading, 24/7 monitoring |
| Break-even | Month 6–9 at 5,000 users | Low burn rate, bootstrappable |

---

## 2. Design Philosophy

### P1: Value Before Revenue
If Alpha Stack doesn't save traders money, it shouldn't make money. Outcome-based pricing enforces this structurally.

### P2: Zero Marginal Cost Data
All data sources use free tiers. The edge comes from combination and analysis, not from paying for premium feeds.

### P3: Bootstrappable Economics
At $7 capital, the system must be buildable with $0 infrastructure budget. Local execution, free APIs, community distribution.

### P4: Compound Value
Each user's trading data improves the system for all users. More data → better models → better signals → more users → more data.

---

## 3. Problem Cost Quantification

### Global Retail Trader Losses

| Metric | Value |
|--------|-------|
| Active retail forex/CFD traders | ~12 million |
| Loss rate | 74–89% (ESMA) |
| Average annual loss per losing trader | $5,500–$11,000 |
| **Total annual retail losses** | **$50–100 billion** |

### Loss Attribution

| Cause | % of Losses | Annual Cost |
|-------|------------|-------------|
| Emotional trading (fear/greed/revenge) | 30–40% | $15–42B |
| No systematic approach | 25–30% | $13–32B |
| Poor risk management | 20–25% | $10–26B |
| Information asymmetry | 10–15% | $5–16B |
| Transaction costs | 5–10% | $3–11B |

### African Trader Losses (Kenya Specific)

| Cost Category | Per Trader/Year | All Kenyan Traders |
|---------------|----------------|-------------------|
| Trading losses (85% × avg $2K account) | $1,700 | $340M–$850M |
| Scam broker losses | $200–500 | $40M–$250M |
| M-Pesa & transaction fees | $50–100 | $10M–$50M |
| Signal/course scams | $100–300 | $20M–$150M |
| **Total annual cost** | **$2,050–$2,600** | **$410M–$1.3B** |

### Time Cost

| Activity | Hours/Week | Hours/Year | Opportunity Cost |
|----------|-----------|-----------|-----------------|
| Chart watching | 15–30 | 780–1,560 | $3,120–$15,600 |
| Analysis & research | 5–10 | 260–520 | $1,040–$5,200 |
| Strategy hopping | 3–8 | 156–416 | $624–$4,160 |
| **Total** | **25–53** | **1,300–2,756** | **$5,200–$27,560** |

---

## 4. Alpha Stack Value Delivery

### Per-Trader Annual Savings

| Feature | Problem Solved | Est. Savings/Year |
|---------|---------------|-------------------|
| Emotional trading elimination | Revenge trading, fear/greed | $2,000–$8,000 |
| 24/7 monitoring | Missed opportunities | $1,500–$5,000 |
| Systematic risk management | Oversizing, blowups | $3,000–$10,000 |
| Multi-agent analysis | Information asymmetry | $1,000–$4,000 |
| Time savings (automation) | 15–30 hrs/week → 2–5 | $2,000–$10,000 |
| Strategy consistency | No more strategy-hopping | $1,000–$3,000 |
| Reduced transaction costs | Better execution | $500–$2,000 |
| **Total per trader** | | **$11,000–$42,000/year** |

### ROI Scenarios

| Account Size | Current Annual Loss | Alpha Stack Reduction | Savings | AS Fee (15% of profits) | User Net Benefit |
|-------------|--------------------|-----------------------|---------|------------------------|-----------------|
| $500 | $400 | 50% | $200 | $0 (no profit yet) | $200 saved |
| $2,000 | $1,700 | 60% | $1,020 | $0–$150 | $870–$1,020 |
| $10,000 | $8,000 | 65% | $5,200 | $300–$780 | $4,420–$4,900 |
| $50,000 | $25,000 | 70% | $17,500 | $1,500–$3,500 | $14,000–$16,000 |

---

## 5. Unit Economics

### Revenue Per User

| Pricing Model | Effective ARPU/Month | Annual |
|---------------|---------------------|--------|
| Outcome-based only | $5–$25 | $60–$300 |
| Hybrid ($20 base + 5% profits) | $20–$40 | $240–$480 |
| Subscription ($30/mo) | $30 | $360 |

### Cost Per User

| Cost Item | Monthly | Notes |
|-----------|---------|-------|
| Data feeds | $0 | Free API tiers |
| Signal computation | $0.05–$0.50 | AI inference (local or cheap cloud) |
| Payment processing | $0.30–$1.50 | M-Pesa/Flutterwave fees |
| Support (amortized) | $0.50–$1.00 | Community-driven, AI-assisted |
| **Total per user** | **$0.85–$3.00** | |

### Unit Economics Summary

| Metric | Value |
|--------|-------|
| ARPU (outcome-based) | $10–$25/month |
| Cost per user | $0.85–$3.00/month |
| **Gross margin** | **70–97%** |
| LTV (12-month retention) | $120–$300 |
| CAC (community-driven) | $0.50–$5 |
| **LTV:CAC ratio** | **24:1 – 600:1** |

---

## 6. Revenue Architecture

### Revenue Projection (Conservative)

| Scenario | Year 1 Users | ARPU/Mo | Annual Revenue |
|----------|-------------|---------|---------------|
| Conservative | 5,000 | $10 | $600K |
| Moderate | 15,000 | $15 | $2.7M |
| Aggressive | 50,000 | $20 | $12M |

### Revenue by Phase

| Phase | Users | Model | Revenue |
|-------|-------|-------|---------|
| Phase 1 (Kenya, M1–12) | 5K–20K | B2C outcome-based | $300K–$1M |
| Phase 2 (SE Asia, M12–24) | 50K–100K | B2B2C + B2C | $2M–$8M |
| Phase 3 (Global, M24–48) | 200K+ | B2B + B2C premium | $10M–$50M+ |

### Outcome-Based Pricing Engine

```
User profits > $0 → Alpha Stack takes 15%
User profits = $0 → Alpha Stack takes $0
User profits < $0 → Alpha Stack takes $0

High watermark: Only charge on NEW profits above previous peak
Monthly cap: $30 maximum fee
Minimum: $0 (no profit, no fee)
```

---

## 7. Cost Structure

### Infrastructure Costs by Phase

| Phase | Monthly Cost | Per User | Notes |
|-------|-------------|---------|-------|
| Phase 1 (0–5K users) | $50–$200 | $0.01–$0.04 | Local/free tier infrastructure |
| Phase 2 (5K–50K users) | $500–$2,000 | $0.01–$0.04 | Cloud VPS, managed DB |
| Phase 3 (50K–200K users) | $5,000–$20,000 | $0.03–$0.10 | Kubernetes, dedicated infra |
| Phase 4 (200K+ users) | $20,000–$100,000 | $0.05–$0.50 | Full production infrastructure |

### Cost Categories

| Category | Phase 1 | Phase 2 | Phase 3 |
|----------|---------|---------|---------|
| Compute (signal generation) | $0 (local) | $100–$500 | $2K–$10K |
| Database | $0 (SQLite) | $50–$200 | $500–$2K |
| Payment processing | 2–3% of revenue | 2–3% | 1.5–2.5% |
| Support | $0 (community) | $200–$500 | $2K–$5K |
| Marketing | $0 (organic) | $500–$2K | $5K–$20K |
| **Total** | **$50–$200** | **$1K–$4K** | **$10K–$40K** |

### Break-Even Analysis

| Users | Monthly Revenue | Monthly Cost | Break-Even? |
|-------|----------------|-------------|-------------|
| 1,000 | $10K | $200 | ✅ Yes |
| 5,000 | $50K | $500 | ✅ Yes |
| 10,000 | $100K | $1K | ✅ Yes |

**Break-even point: ~500 users at $10 ARPU = $5K/month revenue.**

---

## 8. Integration Points

### With TCA Engine
- Transaction cost data feeds into user savings calculations
- Cost savings are part of the value proposition

### With Market Focus
- Revenue projections by market phase
- Payment infrastructure costs by region
- CAC estimates by distribution channel

### With Pricing/Billing
- Outcome-based fee calculation
- High-watermark management
- Multi-currency support (USD, KES, NGN)

### With Strategy Engine
- Signal quality metrics feed into value delivery tracking
- Win rate and R:R data used for user-facing performance dashboards

---

## 9. Implementation Roadmap

### Phase 1: Foundation (Months 1–3)
- [ ] Outcome-based pricing engine
- [ ] User profit tracking and high-watermark system
- [ ] M-Pesa payment integration
- [ ] Basic revenue dashboard

### Phase 2: Optimization (Months 3–6)
- [ ] A/B test pricing models (outcome vs hybrid vs subscription)
- [ ] User segmentation by value delivery
- [ ] Churn prediction and retention analytics
- [ ] LTV/CAC tracking by channel

### Phase 3: Scale (Months 6–12)
- [ ] Multi-currency billing engine
- [ ] Broker partnership rev-share model
- [ ] Institutional pricing tier
- [ ] Financial reporting and compliance

### Phase 4: Enterprise (Months 12+)
- [ ] Revenue forecasting models
- [ ] Unit economics dashboard (real-time)
- [ ] Investor-ready financial metrics
- [ ] Tax optimization across jurisdictions

---

*Architecture document for Alpha Stack Cost Model & Unit Economics. Based on research findings: retail traders lose $50–100B annually. Alpha Stack saves $11K–$42K per trader per year. Unit economics: 70–97% gross margin, LTV:CAC of 24:1–600:1.*
