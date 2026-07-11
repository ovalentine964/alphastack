# Alpha Stack — Regulatory & Compliance Research

**Prepared:** 2026-07-11  
**Purpose:** Map laws and regulations applicable to automated/algorithmic trading systems in Kenya, Africa, and globally so Alpha Stack is built legally compliant.

---

## Table of Contents

1. [Kenya Regulatory Landscape](#1-kenya-regulatory-landscape)
2. [African Markets Overview](#2-african-markets-overview)
3. [Global Regulatory Frameworks](#3-global-regulatory-frameworks)
4. [Crypto & Digital Assets](#4-crypto--digital-assets)
5. [Alpha Stack Specific Requirements](#5-alpha-stack-specific-requirements)
6. [Data Protection](#6-data-protection)
7. [Action Items & Compliance Roadmap](#7-action-items--compliance-roadmap)

---

## 1. Kenya Regulatory Landscape

### 1.1 Capital Markets Authority (CMA)

The CMA is Kenya's primary financial regulator, established in 1989 under the **Capital Markets Act** (now updated as **Capital Markets Act 2023**). It oversees all capital markets intermediaries, including online forex brokers.

**Key legislation:**
- Capital Markets Act 2023 (replaced the Cap 485A)
- Capital Markets (Online Forex Trading) Regulations, 2017
- Virtual Asset Service Providers Act, 2025 (new — covers crypto/digital assets)
- AML/CFT Guidelines (updated 2023–2025)

### 1.2 Licensed Non-Dealing Online Forex Brokers in Kenya (14 as of July 2026)

| # | Broker | License # | Notes |
|---|--------|-----------|-------|
| 1 | EGM Securities (FXPesa) | 107 | First CMA-licensed retail broker (2018). STP/execution-only. |
| 2 | SCFM Ltd (Scope Markets) | 123 | Also CySEC, FSCA regulated |
| 3 | Pepperstone Markets Kenya | 128 | Global broker, CMA-licensed |
| 4 | Exinity Capital East Africa | 135 | FXTM/Alpari group |
| 5 | HFM Investments (HF Markets) | 155 | HotForex brand |
| 6 | Windsor Markets Kenya | 156 | Windsor Brokers |
| 7 | Exness KE Limited | 162 | Global broker |
| 8 | Ingot KE Limited | 173 | |
| 9 | Admirals KE Limited | 178 | Admiral Markets |
| 10 | FP Markets Limited | 193 | |
| 11 | IC Markets (KE) | 199 | |
| 12 | Anzo Capital Limited | 219 | |
| 13 | TPXmglobal Kenya | 233 | |
| 14 | Ava Trade Kenya | 262 | Most recently licensed |

**Broker compliance requirements:**
- Must be incorporated in Kenya or have a local branch
- Minimum capital: **KES 50 million** (~USD 330,000)
- Client fund segregation in trust accounts
- Monthly and annual reporting to CMA
- Mandatory dispute resolution mechanism
- All advertisements pre-approved by CMA
- Leverage: up to 1:400 for non-dealing brokers

### 1.3 CMA's Stance on Algorithmic & Automated Trading

**Current status (2025–2026):**
- Kenya's CMA does **not have a specific algo trading licensing regime** comparable to MiFID II's algo trading rules
- However, the CMA has been **actively expanding its regulatory perimeter**:
  - **Robo-Advisory Permits (2025–2026):** CMA proposed expanding the definition of "investment advisor" to cover digital platforms providing automated, algorithm-driven investment advice with minimal human input
  - **Intermediary Service Platform License:** New license category for operators of digital apps that aggregate, market, and distribute capital markets products
  - **Regulatory Sandbox:** CMA operates a sandbox (since 2019) for testing innovative capital markets products — this is a viable entry point for Alpha Stack

**Implication for Alpha Stack:**
- If Alpha Stack provides **trading signals or automated execution**, it could fall under the expanded "robo-advisory" or "intermediary service platform" definitions
- If Alpha Stack is purely **software sold to traders** (not executing on their behalf), it may not require a CMA license — but this is a grey area
- The CMA sandbox is a strong option for testing the product in a compliant environment

### 1.4 FXPesa Licensing Details

- **Entity:** EGM Securities Limited, trading as FXPesa
- **License:** CMA License #107, Non-Dealing Online Forex Broker
- **Parent:** Equiti Group (also holds FCA, SCA, CySEC licenses)
- **Model:** STP (Straight-Through Processing) execution-only — does not take risk against clients
- **Relevance:** If Alpha Stack integrates with FXPesa for trade execution, Alpha Stack users would trade through a CMA-regulated entity

### 1.5 Tax on Forex & Crypto Profits in Kenya

**Forex trading profits:**
- Kenya does **not have a specific capital gains tax on forex trading profits** for individuals
- However, the Kenya Revenue Authority (KRA) may classify forex trading income as:
  - **Business income** (taxed at graduated rates up to 30% for individuals, 30% corporate rate)
  - **Rental/trading income** under the Income Tax Act
- Broker withholding: CMA-licensed brokers do not withhold tax on client profits
- **Important:** The KRA has been increasing scrutiny of online forex traders; traders should maintain records

**Crypto profits:**
- The **Virtual Asset Service Providers Act, 2025** was recently enacted
- Crypto taxation is evolving; KRA may treat crypto gains as income
- No specific crypto capital gains tax framework yet, but the new VASP Act may introduce reporting requirements

**Digital Services Tax:**
- Kenya introduced a **Digital Assets Tax** at 3% on gains from digital asset transfers (Finance Act 2023)
- This may apply to crypto transactions

### 1.6 Data Protection Act 2019

Kenya's Data Protection Act (2019) is modeled on GDPR principles:
- **Data Protection Commissioner** oversees compliance
- Requires lawful basis for processing personal data
- Data subject rights: access, rectification, erasure, portability
- Cross-border data transfer restrictions (adequacy or safeguards required)
- **Financial data** is considered sensitive and requires enhanced protection
- Data breach notification required within 72 hours
- Appointment of a Data Protection Officer (DPO) may be required for large-scale processing

---

## 2. African Markets Overview

### 2.1 Nigeria

**Regulators:**
- **Securities and Exchange Commission (SEC Nigeria):** Primary capital markets regulator
- **Central Bank of Nigeria (CBN):** Regulates forex and banking

**Key points:**
- Nigeria's SEC published **Rules on Digital Assets** (2022) — one of Africa's first comprehensive crypto frameworks
- CBN previously banned banks from facilitating crypto transactions (2021), but this was **lifted in 2023**
- No specific algo trading regulations, but SEC regulates investment advice and fund management
- Nigeria has a large retail forex trading population, mostly via offshore brokers
- SEC requires registration for investment advisers, fund managers, and securities exchanges

**Alpha Stack implication:** Nigeria is a large potential market but requires careful navigation of CBN forex rules and SEC securities regulations.

### 2.2 South Africa

**Regulator:** Financial Sector Conduct Authority (FSCA)

**Key points:**
- FSCA is the most sophisticated African regulator for financial markets
- **Crypto assets declared a financial product** (2022) — crypto service providers must be licensed
- Forex trading is legal through FSCA-licensed ODP (Over-the-Counter Derivative Provider) brokers
- FSCA has issued guidance on **algorithmic trading** in the context of JSE (Johannesburg Stock Exchange) rules
- South Africa has exchange controls — residents have a **R1 million discretionary allowance** per year for foreign investment

**Alpha Stack implication:** South Africa is the most regulated African market. If targeting SA users, compliance with FSCA licensing and exchange controls is critical.

### 2.3 Tanzania, Uganda, Rwanda

**Tanzania:**
- Capital Markets and Securities Authority (CMSA) regulates capital markets
- Forex trading is largely unregulated at retail level
- No specific algo trading rules
- Crypto is not formally regulated

**Uganda:**
- Capital Markets Authority of Uganda (CMA Uganda) — CMA Kenya has a partnership
- Limited retail forex regulation
- No specific algo trading framework
- Financial Institutions Act 2004 is the primary financial law

**Rwanda:**
- Capital Market Authority (CMA Rwanda)
- Developing capital markets
- No specific algo trading or crypto regulations
- Part of the East African Community (EAC) which has harmonization directives

**Cross-border challenges:**
- No unified African regulatory framework for algo trading
- Each country has different licensing requirements
- East African Community (EAC) has some harmonization but limited in capital markets
- Payment processing across borders varies significantly (mobile money dominant in East Africa)

---

## 3. Global Regulatory Frameworks

### 3.1 EU — MiFID II / MiFIR

**Algorithmic trading rules (MiFID II, Articles 17-18):**
- Firms engaging in algo trading must be **authorized as investment firms**
- Must have **risk controls and circuit breakers** in place
- **Kill switch** functionality required
- Market making algorithms must maintain continuous quotes
- **Annual self-assessment** and regulatory reporting
- High-frequency traders must register as market makers or face restrictions
- Pre-trade and post-trade transparency requirements
- Best execution obligations

**Relevance to Alpha Stack:** If targeting EU users, MiFID II compliance is required. The algo trading rules are the most comprehensive globally.

### 3.2 United States — SEC & CFTC

**SEC (Securities):**
- Regulates securities markets, including equity algo trading
- **Regulation ATS** — applies to alternative trading systems
- **Rule 15c3-5** (Market Access Rule) — requires risk controls for direct market access
- Investment advisers must register under the **Investment Advisers Act of 1940**
- Robo-advisers subject to the same fiduciary duties as human advisers

**CFTC (Derivatives/Futures/Forex):**
- Regulates forex for US persons — only **CFTC-registered Retail Foreign Exchange Dealers (RFEDs)** can offer retail forex
- **Regulation AT** proposed rules for algorithmic trading in futures markets
- Requires registration for anyone providing trading advice for compensation
- Algorithmic traders must maintain records and implement risk controls

**Relevance to Alpha Stack:** US market is extremely regulated. Alpha Stack should NOT target US users without proper licensing. Geo-blocking recommended.

### 3.3 United Kingdom — FCA

**Key requirements:**
- Algorithmic trading requires **FCA authorization** as an investment firm
- **SYSC 6.3** — systems and controls for algorithmic trading
- MiFID II rules retained post-Brexit (onshored as UK MiFIR)
- Robo-advisers must be authorized and provide suitability assessments
- FCA has a **Regulatory Sandbox** and **Innovation Hub** for fintech
- Consumer Duty rules (2023) — products must deliver good outcomes for consumers

### 3.4 Japan — FSA

**Key requirements:**
- Financial Instruments and Exchange Act (FIEA) governs all trading
- Algorithmic trading requires notification to the FSA
- Investment advisory businesses require registration
- Japan has strict leverage limits on retail forex (1:25 for FX)
- Crypto asset exchange services must register with the FSA

### 3.5 Singapore — MAS

**Key requirements:**
- **Securities and Futures Act (SFA)** governs trading
- Capital Markets Services (CMS) license required for providing trading signals/advice
- MAS has issued **Guidelines on Provision of Digital Advisory Services** (2018)
- Risk management requirements for algo trading
- **Payment Services Act (2019)** governs crypto — requires licensing for DPT (Digital Payment Token) services
- MAS has a regulatory sandbox for fintech

---

## 4. Crypto & Digital Assets

### 4.1 EU — MiCA (Markets in Crypto-Assets Regulation)

**Effective:** Full application from December 2024

**Key requirements:**
- **Authorization required** for Crypto-Asset Service Providers (CASPs)
- Covers: exchanges, custody, transfer, advice, portfolio management
- White paper requirements for token issuers
- Stablecoin regulation (ARTs and EMTs)
- Consumer protection and market abuse rules
- Travel Rule compliance (AML)

### 4.2 US — SEC vs CFTC Jurisdictional Split

- **SEC:** Considers many crypto tokens as securities (Howey Test)
- **CFTC:** Considers Bitcoin and Ethereum as commodities
- Ongoing jurisdictional debate — legislation pending
- SEC enforcement actions against unregistered crypto platforms
- No unified federal crypto framework yet

### 4.3 Kenya — Crypto Stance

**Virtual Asset Service Providers Act, 2025:**
- Kenya has now enacted comprehensive crypto regulation
- VASPs (Virtual Asset Service Providers) must register/obtain licenses
- AML/CFT requirements apply to crypto transactions
- CMA plays a role in oversight
- Previously, crypto operated in a grey area — now formalized

### 4.4 KYC/AML Requirements (Cross-Cutting)

**Kenya AML/CFT framework:**
- Proceeds of Crime and Anti-Money Laundering Act (POCAMLA)
- CMA's AML/CFT Guidelines (updated 2023–2025):
  - Customer Due Diligence (CDD) mandatory
  - Enhanced Due Diligence (EDD) for high-risk clients
  - Politically Exposed Persons (PEPs) screening (2025 circular)
  - Beneficial Ownership identification (2025 circular)
  - Suspicious Transaction Reporting to FRC (Financial Reporting Centre)
  - Independent audit of AML/CFT compliance programs

---

## 5. Alpha Stack Specific Requirements

### 5.1 Is Algo Trading Legal in Kenya?

**Yes, but with nuances:**
- There is **no specific ban** on algorithmic trading in Kenya
- Retail traders using EAs (Expert Advisors) on MT4/MT5 is common and legal
- The CMA does not require individual traders to be licensed to use algo strategies
- However, **providing algo trading services to others** may trigger licensing requirements under the expanded robo-advisory and intermediary platform definitions

### 5.2 Does Alpha Stack Need a License?

**It depends on what Alpha Stack does:**

| Alpha Stack Model | Likely License Needed |
|---|---|
| Sells trading software/indicators to traders (tool) | **None** (software product) |
| Provides trading signals for compensation | **Investment Adviser** or **Robo-Advisory** license (under new CMA rules) |
| Executes trades on behalf of users | **Fund Manager** or **Dealing license** |
| Aggregates/provides access to broker platforms | **Intermediary Service Platform** license (new category) |
| Operates as a fund/PAMM | **Collective Investment Scheme** or **Fund Manager** license |

**Recommended approach:**
- **Phase 1:** Position as a software/educational tool (no license needed)
- **Phase 2:** If offering signals or copy trading, explore CMA Regulatory Sandbox
- **Phase 3:** If scaling, apply for appropriate CMA license

### 5.3 Outcome-Based Pricing Legal Structure

**Considerations:**
- **Profit-sharing / performance fees** are common in fund management but require licensing
- In Kenya, charging a percentage of profits could be construed as **carrying on investment business** — requiring CMA licensing
- **Alternative structures:**
  - Fixed subscription fees (SaaS model) — no license needed
  - Freemium model with premium features
  - Affiliate/referral commissions from brokers (common and legal)
  - Revenue share with CMA-licensed partners

### 5.4 Risk Disclosure Requirements

If providing trading-related services, Alpha Stack must include:
- **"Trading involves significant risk of loss"** disclaimer
- **Past performance is not indicative of future results**
- Leverage risk warnings (CMA requires this for forex products)
- Clear statement that Alpha Stack is not a licensed investment adviser (if applicable)
- Users should consult qualified financial advisors

### 5.5 Terms of Service Requirements

Must address:
- Service description and limitations
- User eligibility (age, jurisdiction)
- Risk acknowledgment
- Payment terms and refund policy
- Intellectual property
- Limitation of liability
- Governing law (Kenya recommended)
- Dispute resolution (arbitration recommended)
- Termination conditions
- Data handling (link to Privacy Policy)

---

## 6. Data Protection

### 6.1 GDPR (EU Users)

If Alpha Stack has EU users:
- Lawful basis for processing (consent, legitimate interest, etc.)
- Data Protection Impact Assessment (DPIA) for high-risk processing
- Right to erasure, portability, access
- Data breach notification (72 hours to supervisory authority)
- Data Processing Agreements with sub-processors
- Privacy by design and by default
- Appoint EU representative if no EU establishment
- Potential fines: up to €20M or 4% of global annual turnover

### 6.2 Kenya Data Protection Act 2019

For Kenyan users:
- Registration with the Office of the Data Protection Commissioner (ODPC)
- Lawful basis for processing personal data
- Data subject rights aligned with GDPR
- Cross-border transfer restrictions
- Financial data is sensitive — enhanced protections
- DPO appointment may be required
- Breach notification within 72 hours

### 6.3 Financial Data Security Requirements

**Recommended standards:**
- **PCI DSS** compliance if handling payment card data
- **ISO 27001** for information security management
- **SOC 2 Type II** for SaaS platforms
- Encryption at rest and in transit (TLS 1.2+)
- Multi-factor authentication (MFA)
- Regular penetration testing
- Access controls and audit logging
- Data backup and disaster recovery plans

---

## 7. Action Items & Compliance Roadmap

### Immediate (Pre-Launch)

- [ ] Draft comprehensive **Terms of Service** with risk disclaimers
- [ ] Draft **Privacy Policy** compliant with Kenya DPA and GDPR
- [ ] Register with **ODPC** (Kenya Data Protection Commissioner)
- [ ] Implement **KYC/AML** procedures (if handling user funds/data)
- [ ] Add **risk warnings** to all trading-related content
- [ ] Implement **data encryption** (at rest and in transit)
- [ ] Set up **geo-blocking** for restricted jurisdictions (US, and any others)
- [ ] Consult a **Kenyan capital markets lawyer** for specific guidance on Alpha Stack's model

### Short-Term (0–6 months)

- [ ] Explore **CMA Regulatory Sandbox** application
- [ ] Obtain **legal opinion** on whether Alpha Stack's model requires CMA licensing
- [ ] Implement **PCI DSS** compliance for payment processing
- [ ] Build **audit trail** for all trading activities
- [ ] Consider **Kenyan incorporation** for local entity

### Medium-Term (6–18 months)

- [ ] Apply for **CMA license** if offering signals/advisory services
- [ ] Implement **MiCA compliance** if targeting EU crypto users
- [ ] Expand to **South Africa** (FSCA compliance)
- [ ] Implement **ISO 27001** certification
- [ ] Build **regulatory reporting** capabilities

### Key Contacts & Resources

- **CMA Kenya:** https://www.cma.or.ke | complaints@cma.or.ke | +254 20 2264900
- **CMA Sandbox:** https://sandbox.cma.or.ke
- **Kenya Data Protection Commissioner:** https://www.odpc.go.ke
- **Financial Reporting Centre (AML):** https://www.frc.go.ke
- **KRA (Tax):** https://www.kra.go.ke

---

## Summary of Key Findings

| Area | Status | Risk Level | Action |
|---|---|---|---|
| Algo trading in Kenya | Legal for retail traders | 🟢 Low | No immediate action |
| Providing trading signals | Likely requires license | 🟡 Medium | Legal opinion needed |
| Software tool (SaaS) | No license needed | 🟢 Low | Proceed with ToS |
| CMA Regulatory Sandbox | Available | 🟢 Low | Strong entry point |
| Crypto services | VASP Act 2025 applies | 🟡 Medium | Monitor regulations |
| Data Protection (Kenya) | DPA 2019 applies | 🟡 Medium | Register with ODPC |
| Data Protection (EU/GDPR) | Applies if EU users | 🔴 High | Geo-block or comply |
| Tax on profits | Business income tax | 🟡 Medium | Advise users to consult KRA |
| KYC/AML | Required for financial services | 🟡 Medium | Implement if handling funds |
| US market | Highly restricted | 🔴 High | Geo-block US users |

---

**⚠️ Disclaimer:** This research is for informational purposes only and does not constitute legal advice. Engage a qualified Kenyan capital markets attorney and data protection lawyer before launching Alpha Stack.
