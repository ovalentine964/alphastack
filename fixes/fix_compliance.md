# Compliance Fix — 5 Regulatory Gaps

**Prepared:** 2026-07-11
**Status:** Actionable compliance implementation guide
**Reference Sources:** `research_regulatory.md`, `research_tax_accounting.md`, `review_5_curriculum_compliance.md`

---

## Overview

The regulatory review identified 5 compliance gaps that must be addressed before Alpha Stack launches. This document provides **specific requirements, recommended actions, and implementation steps** for each gap.

| # | Gap | Severity | Priority |
|---|-----|----------|----------|
| 1 | Consumer Protection Act 2012 (ToS compliance) | 🔴 High | Immediate |
| 2 | POCAMLA detail (if handling funds) | 🔴 High | Pre-launch |
| 3 | Market manipulation liability | 🔴 High | Pre-launch |
| 4 | IP/Trademark registration (KIPI) | 🟡 Medium | Within 30 days |
| 5 | National Payment System Act (if processing payments) | 🟡 Medium | Pre-launch |

---

## Gap 1: Consumer Protection Act 2012 (ToS Compliance)

### 1.1 Legal Basis

Kenya's **Consumer Protection Act, 2012** (CPA) applies to all suppliers of goods and services, including digital financial products. Key provisions relevant to Alpha Stack:

- **Section 12:** Unfair contract terms are voidable — terms that create a significant imbalance in rights to the detriment of the consumer are unenforceable
- **Section 15:** Misleading or deceptive conduct is prohibited — marketing claims about trading performance, returns, or system capabilities must be substantiated
- **Section 16:** False representations about services are criminal offenses
- **Section 48:** Consumers have the right to redress — accessible dispute resolution must be provided
- **Section 56:** Supplier must provide clear, understandable contract terms before the consumer commits

### 1.2 Specific Requirements for Alpha Stack's ToS

| Requirement | CPA Section | What Alpha Stack Must Do |
|------------|-------------|--------------------------|
| Plain language | S.56 | All ToS terms must be in clear, non-technical language — no buried legalese |
| Fair terms | S.12 | Cannot unilaterally vary terms, impose excessive penalties, or exclude liability for negligence |
| No misleading claims | S.15-16 | Cannot guarantee returns, promise profits, or claim "risk-free" trading |
| Risk disclosure | S.15 | Must prominently display: "Trading involves significant risk of loss. Past performance is not indicative of future results." |
| Refund/cancellation | S.48 | Must offer a reasonable cancellation and refund policy (recommend 14-day cooling-off for subscriptions) |
| Dispute resolution | S.48 | Must provide accessible complaint mechanism — email, in-app, or ombudsman |
| Liability limitations | S.12 | Limitation of liability clauses must be reasonable — blanket exclusions are voidable |
| Data use consent | S.12 + DPA 2019 | Must obtain explicit consent for data collection and processing |

### 1.3 Recommended ToS Structure

```
Terms of Service — Alpha Stack

1. Definitions & Interpretation
2. Service Description & Limitations
   - Alpha Stack is a software/trading tool, NOT a licensed investment adviser
   - No guarantee of profits; all trading involves risk
3. User Eligibility
   - Age: 18+ years
   - Jurisdiction: Not available in restricted jurisdictions (US, etc.)
   - Must accept risk acknowledgment
4. Risk Disclosure (PROMINENTLY DISPLAYED)
   - Full risk warning per CMA and CPA requirements
   - Leverage risk warning
   - Capital at risk disclaimer
5. Account & Access
   - Account creation, credentials, security obligations
6. Payment Terms
   - Subscription fees, billing cycles, payment methods
   - Taxes and VAT
7. Refund & Cancellation Policy
   - 14-day cooling-off period for new subscriptions
   - Pro-rata refunds for mid-cycle cancellations
   - No refund for completed trading periods where service was consumed
8. Intellectual Property
   - Alpha Stack retains all IP in algorithms, software, branding
   - Users receive limited license to use the platform
   - No reverse engineering, copying, or redistribution
9. User Obligations
   - Accurate registration information
   - Responsible use; no market manipulation
   - Compliance with local laws
10. Limitation of Liability
    - Alpha Stack is not liable for trading losses
    - Liability capped at fees paid in the preceding 12 months
    - Does not exclude liability for fraud, negligence causing injury, or death
11. Indemnification
    - User indemnifies Alpha Stack against claims arising from misuse
12. Termination
    - Either party may terminate with 30 days notice
    - Immediate termination for breach of terms
13. Dispute Resolution
    - Negotiation → Mediation → Arbitration (Nairobi, under Kenya Arbitration Act 1995)
    - Governing law: Republic of Kenya
14. Data Protection
    - Link to Privacy Policy (DPA 2019 compliant)
15. Amendments
    - 30 days notice for material changes
    - Continued use = acceptance
16. Severability
    - Invalid clauses do not affect remaining terms
```

### 1.4 Implementation Steps

| Step | Action | Owner | Deadline |
|------|--------|-------|----------|
| 1 | Draft ToS following structure above | Legal | Week 1 |
| 2 | Engage Kenyan consumer protection lawyer for review | Legal | Week 2 |
| 3 | Add CPA-compliant risk disclaimers to all marketing materials | Marketing | Week 2 |
| 4 | Implement in-app risk acknowledgment checkbox (must tick before first trade) | Dev | Week 3 |
| 5 | Build cancellation/refund flow in billing system | Dev | Week 3 |
| 6 | Set up dispute resolution email (complaints@alphastack.io) | Ops | Week 1 |
| 7 | Add "Terms" and "Privacy" links to every page footer | Dev | Week 1 |
| 8 | Implement 14-day cooling-off period logic in subscription system | Dev | Week 3 |

### 1.5 Key Prohibitions (What NOT to Include)

- ❌ "Alpha Stack guarantees returns" — this is a criminal offense under S.16 CPA
- ❌ "We are not liable for anything" — blanket liability exclusion is voidable under S.12
- ❌ "We may change terms at any time without notice" — unfair under S.12
- ❌ "No refunds under any circumstances" — violates consumer right to redress under S.48
- ❌ Buried arbitration clauses in small print — must be prominent

---

## Gap 2: POCAMLA Compliance (If Handling Funds)

### 2.1 Legal Basis

The **Proceeds of Crime and Anti-Money Laundering Act (POCAMLA)** (2009, amended) and associated **Anti-Money Laundering Regulations** impose obligations on any person or entity that handles, processes, or facilitates financial transactions.

**Trigger condition:** POCAMLA obligations are activated if Alpha Stack:
- Holds user funds (even temporarily in escrow)
- Facilitates deposits or withdrawals to/from broker accounts
- Processes payments for trading subscriptions
- Provides a platform where value is transferred between parties

If Alpha Stack is purely a software tool (users connect their own broker accounts directly), POCAMLA obligations are reduced but not eliminated — the platform still acts as an "accountant, legal practitioner, or other relevant person" under the Act if it provides financial services.

### 2.2 Specific Obligations

| Obligation | POCAMLA Section | Requirement |
|-----------|----------------|-------------|
| Customer Due Diligence (CDD) | S.45 | Verify identity of all users before providing services |
| Enhanced Due Diligence (EDD) | S.46 | Additional checks for high-risk customers (PEPs, high-value accounts) |
| Record Keeping | S.46 | Retain all transaction and identification records for 7 years |
| Suspicious Transaction Reporting (STR) | S.44 | Report suspicious transactions to the Financial Reporting Centre (FRC) |
| Beneficial Ownership | S.45A | Identify and verify beneficial owners of corporate accounts |
| PEP Screening | CMA Circular 2025 | Screen all users against Politically Exposed Persons databases |
| AML/CFT Program | S.47 | Establish internal policies, training, and audit procedures |
| Independent Audit | CMA Guidelines | Annual independent audit of AML/CFT compliance program |

### 2.3 Recommended AML/CFT Program

```
Alpha Stack AML/CFT Compliance Program

1. POLICY FRAMEWORK
   - AML/CFT Policy Document (approved by board/director)
   - Risk-Based Approach (RBA) methodology
   - Sanctions screening policy
   - PEP policy

2. CUSTOMER DUE DILIGENCE (CDD)
   Tier 1 — Basic (all users):
   - Full name, date of birth, national ID / passport
   - Email verification, phone verification
   - Country of residence
   
   Tier 2 — Enhanced (high-risk / high-value):
   - Source of funds declaration
   - Proof of address (utility bill, bank statement)
   - Source of wealth documentation
   - PEP declaration and screening
   - Sanctions screening (OFAC, EU, UN lists)
   
   Tier 3 — Simplified (low-risk, e.g., small subscription-only):
   - Full name, email, phone
   - Country verification (IP geolocation + ID)

3. TRANSACTION MONITORING
   - Automated monitoring for unusual patterns:
     * Large deposits/withdrawals (>KES 1,000,000 or equivalent)
     * Rapid movement of funds in and out
     * Multiple accounts from same IP/device
     * Structuring (splitting transactions to avoid thresholds)
   - Manual review queue for flagged transactions
   - Escalation to MLRO (Money Laundering Reporting Officer)

4. SUSPICIOUS TRANSACTION REPORTING (STR)
   - Report to FRC within 24 hours of determination
   - Use FRC's electronic reporting system
   - Do NOT inform the customer (tipping-off offense under S.48)
   - Maintain internal register of all STRs filed

5. RECORD KEEPING
   - Customer identification: 7 years after relationship ends
   - Transaction records: 7 years from date of transaction
   - STR records: 7 years from date of filing
   - Training records: Duration of employment + 3 years

6. TRAINING
   - All staff: Annual AML/CFT awareness training
   - Customer-facing staff: Enhanced training on red flags
   - MLRO: Specialized training and certification
   - Board/Director: Annual AML/CFT briefing

7. APPOINTMENTS
   - MLRO (Money Laundering Reporting Officer): Designated person responsible for STR filing
   - Deputy MLRO: Backup
   - AML/CFT Compliance Officer: Day-to-day compliance oversight
```

### 2.4 Implementation Steps

| Step | Action | Owner | Deadline |
|------|--------|-------|----------|
| 1 | Determine if Alpha Stack will handle funds or connect users to brokers | Product | Immediate |
| 2 | Draft AML/CFT Policy Document | Legal | Week 2 |
| 3 | Appoint MLRO and Deputy MLRO | Management | Week 1 |
| 4 | Implement KYC flow (Tier 1: ID + email + phone) | Dev | Week 4 |
| 5 | Integrate sanctions screening API (e.g., ComplyAdvantage, Refinitiv) | Dev | Week 5 |
| 6 | Implement PEP screening | Dev | Week 5 |
| 7 | Build transaction monitoring rules engine | Dev | Week 6 |
| 8 | Register with FRC as a reporting entity | Legal | Week 2 |
| 9 | Build STR filing workflow (internal + FRC portal) | Dev | Week 6 |
| 10 | Set up 7-year record retention system (encrypted, backed up) | Dev/Infra | Week 4 |
| 11 | Conduct staff AML/CFT training | HR/Compliance | Week 7 |
| 12 | Engage independent auditor for annual AML audit | Legal | Pre-launch |

### 2.5 FRC Registration

- **Financial Reporting Centre (FRC):** https://www.frc.go.ke
- **Contact:** info@frc.go.ke | +254 20 271 8993
- **Registration:** Submit application as a "reporting entity" under POCAMLA
- **Timeline:** Allow 4-8 weeks for registration approval

### 2.6 If Alpha Stack Does NOT Handle Funds

If Alpha Stack operates purely as a software/SaaS tool where users connect their own broker accounts:

- **Full CDD/EDD may not be required** — but recommended for risk mitigation
- **STR obligations still apply** if Alpha Stack becomes aware of suspicious activity
- **Record keeping** of user accounts is still prudent (5 years minimum under DPA, 7 years under POCAMLA if applicable)
- **Recommendation:** Implement basic KYC (email + phone + country) even if not legally mandated — demonstrates due diligence and builds trust

---

## Gap 3: Market Manipulation Liability

### 3.1 Legal Basis

Market manipulation is prohibited under:

- **Capital Markets Act 2023** (Section 34A — Market manipulation and insider dealing)
- **CMA AML/CFT Guidelines** (market abuse provisions)
- **Capital Markets (Securities) (Public Offers, Listing and Disclosure) Regulations**

If Alpha Stack's aggregated trading activity across multiple users creates artificial price movements, the platform operator AND individual users could face CMA enforcement.

### 3.2 Types of Market Manipulation Relevant to Alpha Stack

| Type | Description | Alpha Stack Risk |
|------|-------------|-----------------|
| **Wash trading** | Buying and selling the same instrument to create artificial volume | If multiple Alpha Stack users execute identical trades simultaneously, it could appear as coordinated wash trading |
| **Spoofing** | Placing orders with intent to cancel before execution to move prices | Alpha Stack's algorithm must not place and cancel orders in patterns that move the market |
| **Layering** | Multiple orders at different prices to create false depth | Order placement logic must avoid creating artificial order book depth |
| **Pump and dump** | Coordinated buying to inflate price, then selling | If Alpha Stack signals buy to all users simultaneously on a low-liquidity instrument, this is a risk |
| **Cornering** | Acquiring dominant position to control price | Position size relative to market liquidity must be monitored |
| **Marking the close** | Trading aggressively at market close to influence closing prices | Avoid concentrating trades at specific times |

### 3.3 Risk Factors for Alpha Stack

| Factor | Risk Level | Explanation |
|--------|-----------|-------------|
| All users get same signal at same time | 🔴 High | If 1,000 users all buy EUR/USD at the same second, the aggregate effect is market-moving |
| Low liquidity instruments (exotic pairs, small-cap crypto) | 🔴 High | Alpha Stack's aggregated flow could be a significant % of daily volume |
| High liquidity instruments (major pairs, BTC) | 🟢 Low | Alpha Stack's flow is unlikely to move major markets |
| Position sizing (all users same lot size) | 🟡 Medium | Uniform sizing amplifies coordinated impact |
| Algorithmic execution (no human review) | 🟡 Medium | No human "circuit breaker" to catch manipulation patterns |

### 3.4 Recommended Safeguards

```
Anti-Manipulation Framework

1. POSITION SIZE CAPS (per instrument, per user)
   - Cap individual position size as % of average daily volume (ADV)
   - Recommended: Max 0.1% of ADV per user
   - For low-liquidity instruments: Max 0.01% of ADV
   
2. AGGREGATE FLOW MONITORING
   - Monitor total Alpha Stack user flow per instrument per time window
   - Alert if aggregate flow exceeds 1% of ADV in any 15-minute window
   - Auto-reduce signal frequency if threshold breached
   
3. SIGNAL RANDOMIZATION
   - Introduce slight time randomization (±5 to ±30 seconds) for signal delivery
   - Prevents exact simultaneous execution across all users
   - Staggers entry/exit to reduce coordinated market impact
   
4. DIVERSIFIED SIGNALS
   - Where possible, offer multiple entry/exit points
   - Allow users to set personal entry/exit ranges
   - Reduces uniformity of execution
   
5. LOW-LIQUIDITY CIRCUIT BREAKER
   - If instrument's daily volume < $1M equivalent, restrict signal to max 10% of users
   - Or disable automated signals for low-liquidity instruments entirely
   
6. ORDER PATTERN MONITORING
   - Monitor for spoofing/layering patterns in algorithmic orders
   - Ensure minimum order duration (e.g., orders must remain live for >1 second)
   - Log all order placements and cancellations with timestamps
   
7. ANTI-SPOOFING LOGIC
   - Do not place orders with intent to cancel
   - All limit orders must be genuine (filled or expired by market movement)
   - Implement order-to-trade ratio monitoring
   
8. AUDIT TRAIL
   - Log every signal sent (instrument, direction, timestamp, user count)
   - Log every order placed (price, size, timestamp, fill status)
   - Retain logs for 7 years (aligned with POCAMLA)
   - Make logs available to CMA upon request
```

### 3.5 Implementation Steps

| Step | Action | Owner | Deadline |
|------|--------|-------|----------|
| 1 | Implement ADV calculation for all tradeable instruments | Quant/Dev | Week 4 |
| 2 | Build position size cap logic (per-user, per-instrument, based on ADV) | Dev | Week 5 |
| 3 | Implement aggregate flow monitoring dashboard | Dev | Week 5 |
| 4 | Add signal delivery randomization (±5-30 sec jitter) | Dev | Week 3 |
| 5 | Build low-liquidity circuit breaker | Dev | Week 6 |
| 6 | Implement order pattern monitoring (spoofing/layering detection) | Dev | Week 6 |
| 7 | Create audit log schema and storage (7-year retention) | Dev/Infra | Week 4 |
| 8 | Document anti-manipulation policy | Legal | Week 2 |
| 9 | Engage market abuse lawyer for review of algorithm logic | Legal | Week 3 |
| 10 | Set up quarterly review of manipulation risk metrics | Compliance | Ongoing |

### 3.6 Legal Defenses

If CMA investigates Alpha Stack's trading activity:

- **Best defense:** Documented anti-manipulation framework with automated safeguards
- **Key evidence:** Position size caps, flow monitoring, signal randomization, audit trail
- **Proactive measure:** Consider filing a "no-action letter" request with CMA describing Alpha Stack's safeguards and seeking informal guidance

---

## Gap 4: IP/Trademark Registration (KIPI)

### 4.1 Legal Basis

- **Industrial Property Act 2001** — governs trademarks, patents, industrial designs in Kenya
- **Copyright Act 2001** — protects original literary, musical, and artistic works (includes software source code)
- **Kenya Industrial Property Institute (KIPI)** — the government agency that administers IP registration

### 4.2 What to Protect

| Asset | IP Type | Protection Mechanism | Priority |
|-------|---------|---------------------|----------|
| "ALPHA STACK" name & logo | Trademark | Register with KIPI | 🔴 Immediate |
| Trading algorithms (source code) | Copyright | Automatic (but register for enforcement) | 🟡 Medium |
| System architecture / design documents | Copyright | Automatic | 🟢 Low |
| Brand tagline: "Stack the Alpha. Beat the Market." | Trademark | Register with KIPI | 🟡 Medium |
| Unique UI/UX design elements | Industrial Design | Register with KIPI if distinctive | 🟢 Low |
| Proprietary trading strategies | Trade Secret | Internal controls (NDAs, access restrictions) | 🟡 Medium |

### 4.3 Trademark Registration Process (KIPI)

```
Step-by-Step: Trademark Registration for "ALPHA STACK"

1. TRADEMARK SEARCH (Week 1)
   - Search KIPI database for existing "ALPHA STACK" or similar marks
   - Search in Class 9 (software) and Class 36 (financial services)
   - Online search: https://www.kipi.go.ke
   - If conflict found, modify mark or negotiate with existing holder

2. PREPARE APPLICATION
   Required documents:
   - TM Form 2 (Application for Registration)
   - Clear representation of the mark (logo + word mark)
   - List of goods/services (Nice Classification)
   - Applicant details (name, address, nationality)
   - Priority claim (if applicable, based on foreign filing)
   - Power of Attorney (if filing through agent)
   
   Classes to file in:
   - Class 9: Computer software; downloadable software for trading
   - Class 36: Financial services; trading platform services; financial analysis
   - Class 41: Education; training; providing online courses
   - Class 42: Software as a Service (SaaS); platform as a service

3. FILE APPLICATION (Week 2)
   - Submit to KIPI with prescribed fees
   - Filing fee: ~KES 5,000 per class (~USD 33)
   - Agent fees (if using IP attorney): ~KES 15,000-30,000 per class
   
4. EXAMINATION (Weeks 3-12)
   - KIPI examines the application for:
     * Distinctiveness
     * Conflict with existing marks
     * Compliance with formal requirements
   - May issue examination report with objections
   
5. PUBLICATION (Week 12-16)
   - If accepted, mark is published in the Kenya Industrial Property Journal
   - 60-day opposition period for third parties
   
6. REGISTRATION (Week 16-20)
   - If no opposition, mark is registered
   - Registration certificate issued
   - Valid for 10 years from filing date
   - Renewable indefinitely for 10-year periods

TOTAL TIMELINE: ~4-5 months (no opposition)
TOTAL COST: ~KES 40,000-80,000 for 4 classes (filing + agent fees)
```

### 4.4 International Trademark Protection

| Mechanism | Coverage | When to Use |
|-----------|----------|-------------|
| **Madrid Protocol** | 130+ countries (Kenya is a member) | File one application through KIPI designating target countries |
| **ARIPO** | 22 African countries | For pan-African protection via one filing |
| **OAPI** | 17 French-speaking African countries | If expanding to West/Central Africa |
| **National filings** | Individual countries | For countries not in Madrid/ARIPO |

**Recommendation:** File through KIPI first (Kenya), then extend via Madrid Protocol to key markets (Nigeria, South Africa, Tanzania, UK) once Kenya registration is secured.

### 4.5 Copyright Protection

Software source code is automatically protected under Kenya's Copyright Act 2001 upon creation. However:

- **Register with the Kenya Copyright Board (KECOBO)** for enhanced enforcement capability
- Registration creates a public record and shifts burden of proof in infringement cases
- Filing fee: ~KES 1,000-2,000
- Timeline: 1-2 months

### 4.6 Trade Secret Protection

For proprietary trading strategies that are NOT publicly disclosed:

- **NDAs:** All employees, contractors, and partners must sign NDAs
- **Access controls:** Limit access to algorithm source code on need-to-know basis
- **Code obfuscation:** Obfuscate deployed algorithms
- **Non-compete clauses:** Include in employment contracts (enforceable in Kenya if reasonable)
- **Documentation:** Maintain records of what constitutes trade secrets

### 4.7 Implementation Steps

| Step | Action | Owner | Deadline |
|------|--------|-------|----------|
| 1 | Conduct trademark search on KIPI database | Legal/IP Agent | Week 1 |
| 2 | Engage Kenyan IP attorney / agent | Legal | Week 1 |
| 3 | File trademark application in Classes 9, 36, 41, 42 | IP Agent | Week 2 |
| 4 | Prepare and file logo mark application | IP Agent | Week 2 |
| 5 | Register copyright with KECOBO | Legal | Week 3 |
| 6 | Draft NDAs and non-compete clauses | Legal | Week 2 |
| 7 | Implement access controls for source code | Dev/Infra | Week 3 |
| 8 | Monitor KIPI publication for opposition | IP Agent | Ongoing |
| 9 | File Madrid Protocol extension (after Kenya registration) | IP Agent | Month 6 |
| 10 | Register domain: alphastack.io + .co.ke + .com | Ops | Week 1 |
| 11 | Register social handles: @alphastack (all platforms) | Marketing | Week 1 |

### 4.8 Budget Estimate

| Item | Cost (KES) | Cost (USD) |
|------|-----------|-----------|
| Trademark search (4 classes) | 10,000 | ~65 |
| Trademark filing (4 classes × KES 5,000) | 20,000 | ~130 |
| IP attorney fees (4 classes) | 80,000 | ~520 |
| KECOBO copyright registration | 2,000 | ~13 |
| Domain registration (.io + .co.ke + .com) | 10,000 | ~65 |
| **Total** | **~122,000** | **~800** |

---

## Gap 5: National Payment System Act 2011

### 5.1 Legal Basis

The **National Payment System Act 2011** (NPS Act) and **National Payment System Regulations 2014** regulate all payment systems and payment service providers in Kenya. The Central Bank of Kenya (CBK) administers this framework.

**Trigger condition:** NPS Act licensing is required if Alpha Stack:
- Processes payments on behalf of users (e.g., collecting subscriptions and remitting to brokers)
- Facilitates fund transfers between users or between users and third parties
- Holds user funds in any form (e-wallet, escrow, etc.)
- Issues payment instruments (prepaid cards, virtual accounts)
- Operates a payment system (aggregating, clearing, or settling transactions)

### 5.2 License Categories

| License | Scope | Alpha Stack Applicability |
|---------|-------|--------------------------|
| **Payment Service Provider (PSP)** | Process payments, money transfers | Required if processing subscription payments directly |
| **Electronic Money Issuer (EMI)** | Issue e-money / e-wallets | Required if holding user funds in wallets |
| **Payment Instrument Provider** | Issue cards, prepaid instruments | Not applicable unless issuing Alpha Stack branded cards |
| **System Operator** | Operate a payment/clearing system | Not applicable unless building a proprietary settlement system |

### 5.3 Decision Tree: Does Alpha Stack Need an NPS License?

```
Does Alpha Stack collect payments from users?
├── NO → NPS Act likely does NOT apply
└── YES → How are payments collected?
    ├── Through a licensed third-party (Stripe, M-Pesa, Flutterwave) → NPS license NOT required (third-party holds the license)
    ├── Alpha Stack collects directly into its own account → PSP license MAY be required
    └── Alpha Stack holds funds in user wallets → EMI license REQUIRED
    
Does Alpha Stack facilitate fund transfers?
├── NO → NPS Act does NOT apply
└── YES → PSP license REQUIRED

Does Alpha Stack connect users to brokers for fund deposits?
├── NO → NPS Act does NOT apply
└── YES → Depends on mechanism
    ├── User deposits directly to broker (Alpha Stack only shares referral link) → NPS license NOT required
    ├── Alpha Stack intermediates the transfer → PSP license REQUIRED
    └── Alpha Stack holds funds before forwarding to broker → EMI license REQUIRED
```

### 5.4 Recommended Approach: Use Licensed Third-Party Processors

**To avoid NPS Act licensing entirely:**

| Payment Method | Processor | License Status | Notes |
|---------------|-----------|---------------|-------|
| Mobile Money (M-Pesa) | Safaricom / Lipa na M-Pesa | Licensed by CBK | Dominant payment method in Kenya |
| Card payments | Stripe / Flutterwave | Licensed by CBK / international | Supports Visa, Mastercard |
| Bank transfers | Direct bank API (e.g., Paystack) | Licensed by CBK | For larger amounts |
| Crypto payments | Coinbase Commerce / BitPay | VASP licensed | For crypto-native users |

**By routing all payments through licensed third-party processors, Alpha Stack operates as a "merchant" using their licensed infrastructure — no NPS license needed.**

### 5.5 If Alpha Stack Needs Its Own PSP License

If business model requires direct payment processing:

| Requirement | Details |
|------------|---------|
| **Minimum capital** | KES 10 million (~USD 65,000) for PSP |
| **Incorporation** | Must be incorporated in Kenya |
| **Fit and proper** | Directors and shareholders must pass CBK fit-and-proper test |
| **Technology audit** | CBK audits payment system infrastructure |
| **Risk management** | Documented risk management framework |
| **Security standards** | PCI DSS compliance required |
| **Reporting** | Monthly and annual returns to CBK |
| **AML/CFT** | Full POCAMLA compliance (see Gap 2) |
| **Customer funds** | Segregated trust accounts — cannot commingle with operating funds |
| **Timeline** | 6-12 months for CBK approval |
| **Cost** | Legal + compliance + minimum capital = ~KES 15-20 million total |

### 5.6 M-Pesa Integration (Recommended Primary Payment Channel)

Since M-Pesa is the dominant payment method in Kenya (93%+ mobile money market share):

- **Lipa na M-Pesa (Paybill):** Register a Paybill number with Safaricom for business collections
- **M-Pesa API:** Integrate for automated subscription billing
- **Paybill registration:** Apply through Safaricom Business portal
- **Fees:** 1-2.5% per transaction (negotiable for volume)
- **Settlement:** T+1 to T+3 to business bank account
- **No NPS license needed** — Safaricom holds the EMI license

### 5.7 Implementation Steps

| Step | Action | Owner | Deadline |
|------|--------|-------|----------|
| 1 | Decision: Does Alpha Stack need to hold user funds? | Product | Immediate |
| 2 | If NO: Route all payments through licensed third-party processors | Dev | Week 3 |
| 3 | Register M-Pesa Paybill number | Ops | Week 2 |
| 4 | Integrate Stripe/Flutterwave for card payments | Dev | Week 4 |
| 5 | Implement subscription billing system (recurring payments) | Dev | Week 4 |
| 6 | If YES (hold funds): Begin PSP license application to CBK | Legal | Week 1 |
| 7 | If YES: Engage CBK licensing consultant | Legal | Week 2 |
| 8 | If YES: Prepare minimum capital (KES 10M) | Finance | Month 3 |
| 9 | Implement PCI DSS compliance (if handling card data) | Dev/Infra | Week 6 |
| 10 | Set up payment reconciliation and reporting | Finance/Dev | Week 5 |

### 5.8 Budget Estimate (Third-Party Processor Route)

| Item | Cost (KES) | Cost (USD) | Frequency |
|------|-----------|-----------|-----------|
| M-Pesa Paybill registration | 1,000 | ~7 | One-time |
| Stripe/Flutterwave setup | 0 | 0 | Free (transaction fees only) |
| Transaction fees (M-Pesa, ~2%) | Variable | Variable | Per transaction |
| PCI DSS compliance (if handling cards) | 200,000-500,000 | 1,300-3,300 | Annual |
| **Total setup** | **~201,000-501,000** | **~1,300-3,300** | One-time + annual |

### 5.9 Budget Estimate (Own PSP License Route)

| Item | Cost (KES) | Cost (USD) |
|------|-----------|-----------|
| Minimum capital (locked) | 10,000,000 | ~65,000 |
| Legal fees (CBK application) | 2,000,000 | ~13,000 |
| Technology audit | 500,000 | ~3,300 |
| PCI DSS certification | 500,000 | ~3,300 |
| Compliance setup | 500,000 | ~3,300 |
| **Total** | **~13,500,000** | **~88,000** |

---

## Implementation Roadmap

### Phase 1: Immediate (Weeks 1-2)

| # | Action | Gap Addressed |
|---|--------|--------------|
| 1 | Engage Kenyan legal counsel (capital markets + consumer protection + IP) | All |
| 2 | File trademark application with KIPI (Classes 9, 36, 41, 42) | Gap 4 |
| 3 | Register domain + social handles | Gap 4 |
| 4 | Draft ToS following CPA-compliant structure | Gap 1 |
| 5 | Draft AML/CFT Policy Document | Gap 2 |
| 6 | Appoint MLRO | Gap 2 |
| 7 | Decision: Payment processing model (third-party vs. own PSP) | Gap 5 |

### Phase 2: Pre-Launch (Weeks 3-6)

| # | Action | Gap Addressed |
|---|--------|--------------|
| 8 | Implement KYC flow (basic + enhanced tiers) | Gap 2 |
| 9 | Integrate sanctions/PEP screening | Gap 2 |
| 10 | Build transaction monitoring | Gap 2 |
| 11 | Implement position size caps and aggregate flow monitoring | Gap 3 |
| 12 | Add signal delivery randomization | Gap 3 |
| 13 | Implement order pattern monitoring | Gap 3 |
| 14 | Integrate M-Pesa + Stripe/Flutterwave | Gap 5 |
| 15 | Build subscription billing with cancellation/refund flows | Gap 1, 5 |
| 16 | Add risk disclaimers to all UI and marketing | Gap 1 |
| 17 | Set up 7-year record retention system | Gap 2, 3 |
| 18 | Register with FRC as reporting entity | Gap 2 |

### Phase 3: Post-Launch (Months 2-6)

| # | Action | Gap Addressed |
|---|--------|--------------|
| 19 | Conduct penetration testing and security audit | Gap 1 (CPA service quality) |
| 20 | Complete independent AML audit | Gap 2 |
| 21 | Monitor KIPI trademark publication for opposition | Gap 4 |
| 22 | File Madrid Protocol extension for international trademark | Gap 4 |
| 23 | Quarterly manipulation risk metrics review | Gap 3 |
| 24 | Submit CPA-compliant advertising to CMA for pre-approval (if required) | Gap 1 |
| 25 | Annual compliance review across all 5 gaps | All |

---

## Compliance Budget Summary

| Category | Estimated Cost (KES) | Estimated Cost (USD) |
|----------|---------------------|---------------------|
| Legal counsel (initial engagement) | 500,000 | 3,300 |
| Trademark registration (4 classes) | 122,000 | 800 |
| AML/CFT implementation | 300,000 | 2,000 |
| Sanctions/PEP screening API | 200,000/year | 1,300/year |
| Payment processing setup | 201,000-501,000 | 1,300-3,300 |
| Security audit / pen testing | 300,000 | 2,000 |
| Independent AML audit | 400,000/year | 2,600/year |
| Developer time (compliance features) | Internal | Internal |
| **Total (Year 1, third-party payments)** | **~2,023,000-2,323,000** | **~13,300-15,300** |
| **Total (Year 1, own PSP license)** | **~15,322,000-15,823,000** | **~100,000-103,000** |

---

## Key Contacts

| Organization | Purpose | Contact |
|-------------|---------|---------|
| **CMA Kenya** | Capital markets regulation | complaints@cma.or.ke | +254 20 2264900 |
| **CBK** | Payment system licensing | info@centralbank.go.ke | +254 20 286 0000 |
| **FRC** | AML/CFT reporting | info@frc.go.ke | +254 20 271 8993 |
| **KIPI** | Trademark registration | info@kipi.go.ke | +254 20 238 2522 |
| **KECOBO** | Copyright registration | info@kecobo.go.ke | +254 20 271 5570 |
| **ODPC** | Data protection registration | info@odpc.go.ke | +254 20 299 3000 |
| **Safaricom Business** | M-Pesa Paybill registration | business@safaricom.co.ke | 100 (from Safaricom) |

---

## Appendix: Compliance Checklist

### Pre-Launch Checklist

- [ ] **Gap 1:** ToS drafted and reviewed by consumer protection lawyer
- [ ] **Gap 1:** Risk disclaimers added to all pages and marketing materials
- [ ] **Gap 1:** In-app risk acknowledgment checkbox implemented
- [ ] **Gap 1:** Cancellation/refund policy implemented (14-day cooling-off)
- [ ] **Gap 1:** Dispute resolution mechanism active (complaints@alphastack.io)
- [ ] **Gap 2:** AML/CFT Policy Document approved
- [ ] **Gap 2:** MLRO appointed
- [ ] **Gap 2:** KYC flow implemented (Tier 1 minimum)
- [ ] **Gap 2:** Sanctions screening integrated
- [ ] **Gap 2:** Transaction monitoring active
- [ ] **Gap 2:** Registered with FRC
- [ ] **Gap 2:** 7-year record retention system operational
- [ ] **Gap 3:** Position size caps implemented (per-user, per-instrument, ADV-based)
- [ ] **Gap 3:** Aggregate flow monitoring active
- [ ] **Gap 3:** Signal delivery randomization enabled
- [ ] **Gap 3:** Low-liquidity circuit breaker active
- [ ] **Gap 3:** Order pattern monitoring (anti-spoofing) active
- [ ] **Gap 3:** 7-year audit log retention operational
- [ ] **Gap 4:** Trademark application filed with KIPI
- [ ] **Gap 4:** Domain registered (.io, .co.ke, .com)
- [ ] **Gap 4:** Social handles registered
- [ ] **Gap 4:** NDAs signed by all employees/contractors
- [ ] **Gap 5:** Payment processor integrated (M-Pesa + Stripe/Flutterwave)
- [ ] **Gap 5:** Subscription billing system operational
- [ ] **Gap 5:** Payment reconciliation system active

### Quarterly Review Checklist

- [ ] Review and update ToS for regulatory changes
- [ ] Review AML/CFT transaction monitoring thresholds
- [ ] Review manipulation risk metrics
- [ ] Check KIPI trademark status
- [ ] Review payment processing fees and settlement times
- [ ] Conduct staff compliance training refresher
- [ ] Independent AML audit (annual)

---

**⚠️ Disclaimer:** This document is for planning and implementation purposes only and does not constitute legal advice. All compliance actions should be reviewed and approved by qualified Kenyan legal counsel before implementation. Regulatory requirements change; verify all positions against current legislation.
