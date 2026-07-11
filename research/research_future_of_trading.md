# The Future of Trading: 2026–2035
## Strategic Research Report for Alpha Stack

**Date:** July 11, 2026  
**Scope:** Forex, Crypto, and Cross-Asset Trading Evolution  
**Purpose:** Inform Alpha Stack architecture and strategy decisions

---

## Executive Summary

The trading landscape is undergoing its most significant structural transformation since the shift from open-outcry to electronic markets. Five converging forces will reshape forex and crypto trading over the next decade:

1. **CBDCs** will rewire the plumbing of foreign exchange
2. **Tokenized real-world assets** are already a $35.7B market and accelerating
3. **DEXs are maturing** into viable alternatives to centralized exchanges
4. **AI-native market microstructure** will make algorithmic trading the default, not the edge
5. **Regulatory frameworks** are crystallizing globally (MiCA, US stablecoin laws, Kenya CMA)

The window to build infrastructure for this new paradigm is **now**. Systems designed for traditional forex + crypto spot will be obsolete by 2030.

---

## 1. Central Bank Digital Currencies (CBDCs)

### Current State (July 2026)

| Region | CBDC | Status | Notes |
|--------|------|--------|-------|
| **China** | e-CNY (Digital Yuan) | **Live** — largest pilot globally | 260M+ wallets, integrated with WeChat/Alipay, cross-border via mBridge |
| **Nigeria** | eNaira | **Live** since Oct 2021 | Low adoption, lessons in UX pitfalls |
| **Bahamas** | Sand Dollar | **Live** since Oct 2020 | First national CBDC |
| **Jamaica** | JAM-DEX | **Live** since Jun 2022 | Legal tender status |
| **EU** | Digital Euro | **Preparation phase** (since Nov 2023) | Expected launch: 2028–2029 |
| **UK** | Digital Pound ("Britcoin") | **Design phase** | Expected: 2028–2030 |
| **India** | Digital Rupee (e₹) | **Pilot** — wholesale + retail | RBI running extensive pilots |
| **Brazil** | Drex (Digital Real) | **Pilot** — advanced testing | Smart contract integration planned |
| **Russia** | Digital Ruble | **Pilot** with select banks | Sanctions-driven urgency |
| **Japan** | Digital Yen | **Pilot phase** | Conservative approach |
| **US** | FedNow (not CBDC) / No CBDC plans | **No CBDC** under current administration | FedNow instant payment system live; CBDC politically blocked |
| **Australia** | eAUD | **Research/pilot** | RBA cautious, exploring use cases |

### Key Multi-CBDC Initiatives

- **mBridge** (BIS + China, UAE, Thailand, Saudi Arabia, Hong Kong): Cross-border CBDC settlement. Already settled $22B+ in transactions. This is the prototype for CBDC-to-CBDC forex.
- **Project Dunbar** (BIS + Singapore, Australia, Malaysia, South Africa): Multi-CBDC platform for shared settlement.
- **Project Icebreaker** (BIS + Israel, Norway, Sweden): Retail cross-border CBDC payments.
- **Project Mariana** (BIS + France, Switzerland, Singapore): DeFi-style CBDC forex using AMMs.

### Impact on Forex Trading

**By 2028–2030:**
- **Settlement collapses from T+2 to near-instant.** CBDCs enable atomic settlement — delivery-versus-payment in seconds, not days.
- **24/7 forex markets become inevitable.** CBDCs don't close at 5pm New York time. The "weekend gap" dies.
- **CBDC-to-CBDC direct exchange** starts bypassing SWIFT and traditional correspondent banking for major pairs (e-CNY ↔ digital EUR, etc.).
- **Reduced role of USD as intermediary.** Currently, many forex pairs route through USD (e.g., THB → USD → BRL). CBDC corridors enable direct cross.

**By 2030–2035:**
- **FX market microstructure changes fundamentally.** With instant settlement, the "settlement risk premium" disappears, tightening spreads.
- **Programmable money** enables conditional FX settlement (escrow-like, regulatory hold until compliance checks pass).
- **Privacy tensions** escalate. CBDCs give central banks unprecedented visibility into cross-border flows. This will drive demand for privacy-preserving compliance tech.

### Privacy Implications

Most CBDCs use a **tiered privacy model**:
- Small transactions: private to the user (like cash)
- Large transactions: visible to regulators
- Cross-border: visible to both country's regulators

This creates a **compliance layer** that Alpha Stack could integrate — real-time KYC/AML verification embedded in the settlement flow rather than bolted on afterward.

### Timeline Summary

| Timeframe | What Happens |
|-----------|--------------|
| 2026–2027 | e-CNY expands cross-border; EU digital euro in active development; India/Brazil pilots mature |
| 2028–2029 | Digital euro launches; mBridge expands to 20+ countries; CBDC forex corridors for G10 currencies |
| 2030–2032 | Major economies have live CBDCs; traditional correspondent banking for major pairs starts declining |
| 2033–2035 | CBDC-to-CBDC forex becomes mainstream for institutional; retail follows; programmable FX contracts standard |

---

## 2. Tokenized Real-World Assets (RWA)

### Current Market (Live Data from RWA.xyz, July 2026)

The tokenization market is no longer theoretical — it's a **$35.7 billion** distributed asset market:

**Top Tokenized Government Securities:**
| Fund | AUM | Growth (30d) |
|------|-----|-------------|
| Hashnote USYC (US T-Bills) | $3.1B | -1.08% |
| BlackRock BUIDL | $2.9B | **+28.76%** |
| Ondo USDY | $2.2B | +0.15% |
| Franklin Templeton BENJI | $1.6B + $760.9M | Stable |
| WisdomTree WTGXX | $764.5M | +7% |

**Tokenized Stocks (Exploding):**
| Token | AUM | Notes |
|-------|-----|-------|
| FIGon (Robinhood) | **$1.2B** | +2,051% — Hyperliquid-listed tokenized stock |
| LLYon (Eli Lilly) | $119.5M | +868% |
| AMDon | $60M | +205% |
| MELIon (MercadoLibre) | $46.5M | +280% |

Robinhood has launched **dozens of tokenized stocks** on-chain as of July 2026 — Meta, Alphabet, SPY, QQQ, Palantir, and many more. This is a watershed moment.

**Tokenized Commodities:**
- Tether Gold (XAUT): $2.5B
- PAX Gold (PAXG): $1.8B
- Gold is the leading tokenized commodity by a massive margin

**Tokenized Credit/Debt:**
- Janus Henderson JAAA (CLO): $689M
- Multiple tokenized credit strategies emerging ($500M+ TPT30, $353M STAC)

**By Blockchain Network:**
| Network | RWA Value | Market Share |
|---------|-----------|-------------|
| Ethereum | $16.0B | 44.85% |
| BNB Chain | $5.1B | 14.13% |
| Solana | $3.7B | 10.26% |
| Stellar | $3.0B | 8.42% |
| Avalanche | $2.1B | 5.87% |

**Total Asset Holders: 1,005,765** (up 10.47% in 30 days)

### What This Means for Trading

1. **Fractional ownership is here.** You can buy $1 of BlackRock BUIDL or $10 of tokenized Apple stock. This democratizes portfolio construction.

2. **24/7 trading of traditional assets.** Tokenized stocks and bonds trade on-chain around the clock. The NYSE's 6.5-hour trading day looks increasingly absurd.

3. **Composability.** Tokenized assets can be used as DeFi collateral, combined into automated portfolios, or traded on DEXs alongside crypto-native assets. A single portfolio can hold US T-Bills (via BUIDL), Ethereum, tokenized gold, and tokenized Apple stock — all on-chain.

4. **Cross-margin becomes real.** Your tokenized T-Bill position can margin your forex trades. Collateral unification across asset classes.

5. **The "everything exchange" emerges.** The distinction between a crypto exchange, forex broker, and stock broker dissolves when all assets are tokens on compatible rails.

### Market Projections

- **BCG/ADDX estimate:** $16 trillion in tokenized assets by 2030
- **Citi GPS estimate:** $4–5 trillion by 2030
- **Conservative consensus:** $2–5 trillion by 2030, $10T+ by 2035
- The current $35.7B is the early-adopter phase. Institutional FOMO is kicking in (BlackRock's BUIDL growing 28% in a single month).

---

## 3. DEX Evolution

### Current State (2026)

**The DEX landscape has matured significantly:**

- **Uniswap v4** (launched 2024): Hooks system enabling custom pool logic, limit orders, dynamic fees — blurring the line between AMM and order book.
- **dYdX v4**: Fully decentralized order-book DEX on its own Cosmos chain. 60+ perpetual markets, sub-second finality.
- **Hyperliquid**: High-performance order-book DEX with tokenized stocks (FIGon at $1.2B AUM). Closing the UX gap with CEXs.
- **Aerodrome/Base DEX ecosystem**: Coinbase's Base chain driving DEX adoption.
- **Raydium/Jupiter (Solana)**: Solana DEXs processing billions in volume with CEX-like speed.

**DEX Volume Trends:**
- DEX:CEX spot volume ratio has climbed from ~5% (2022) to ~15–20% (2026)
- Perps DEX volume growing even faster as dYdX and Hyperliquid capture market share from Binance/Bybit

### Key DEX Limitations Being Solved

| Limitation | Status in 2026 | Direction |
|-----------|----------------|-----------|
| Liquidity | Improving rapidly — concentrated liquidity (Uni v3/v4), professional market makers on-chain | CEX parity by ~2028 |
| Speed | Solana: 400ms blocks; App-chains (dYdX): sub-second | Already "fast enough" for most strategies |
| UX | Smart wallets, account abstraction, gasless transactions | Near parity with CEXs |
| Order types | Uni v4 hooks, native limit orders on most DEXs | Full feature parity emerging |
| MEV | PBS (Proposer-Builder Separation), encrypted mempools, MEV auctions | Ongoing battle, but mitigations improving |
| Cross-chain | Bridges still risky but improving; intent-based protocols (Across, LI.FI) | Multi-chain trading becoming seamless |

### DEX vs CEX Convergence

The trend is **hybrid models**:
- **CEXs adding DEX features**: Binance, OKX integrating DeFi wallets and on-chain trading
- **DEXs adding CEX features**: Order books, fiat on-ramps, KYC tiers
- **The winner is "intent-based" trading**: Users express "I want to swap X for Y at best price" and solvers compete to fill the order across CEX and DEX venues

By 2030, the distinction between DEX and CEX will be a **backend implementation detail**, not a user-facing difference.

### Impact on Alpha Stack

- **Execution routing must become multi-venue.** Optimal execution will require routing across DEXs (Uni, dYdX, Hyperliquid) AND CEXs simultaneously.
- **On-chain settlement** means your settlement layer IS the blockchain. No more waiting for broker confirmations.
- **MEV protection** becomes a core trading concern. Alpha Stack needs MEV-aware execution (private mempools, Flashbots Protect, etc.).
- **Cross-chain arbitrage** becomes a new alpha source as tokenized assets trade across multiple chains.

---

## 4. AI-Native Markets

### The Paradigm Shift

This is the most underappreciated trend. We're moving from **markets where humans trade and AI assists** to **markets where AI trades and humans observe**.

**Evidence of the shift:**

1. **Algorithmic trading already dominates** traditional markets (~70–80% of US equity volume). In crypto, it's even higher (~85–90% on major exchanges).

2. **AI agents are becoming economic actors.** In 2025–2026:
   - AI agents autonomously manage DeFi positions (yield farming, liquidation protection)
   - Agent-to-agent protocols are emerging (e.g., AI agents paying other AI agents for data, compute, services)
   - The "agent economy" is nascent but growing: autonomous agents that hold wallets, make payments, trade assets

3. **Market microstructure changes when most participants are AI:**
   - **Faster price discovery** — no cognitive lag, no emotional bias
   - **Tighter spreads** — competition among AI market makers compresses margins
   - **More correlated moves** — if many AIs use similar data/features, herding increases
   - **New forms of alpha** — adversarial ML, detecting other agents' strategies, exploiting systematic biases in AI models

### Agent-to-Agent Trading Protocols

Emerging frameworks:
- **MCP (Model Context Protocol)** + wallet integration: AI agents that can call financial APIs and execute trades
- **Gnosis Safe + AI signers**: Multi-sig wallets with AI agent keys
- **Intent-based protocols**: AI agents express trading intents, solver networks fill them
- **Prediction market agents**: AI agents that trade on Polymarket, Metaculus based on information synthesis

### What "AI-Native Market Microstructure" Looks Like

By 2030–2035:
- **Most liquidity providers are AI agents** competing on ML models, not human intuition
- **Market making** is almost entirely algorithmic, with AI agents providing liquidity across DEXs, CEXs, and dark pools simultaneously
- **News/sentiment is processed in milliseconds** by NLP agents — the "human reaction to news" edge disappears
- **Strategy decay accelerates** — alpha from any single signal decays faster because AI agents discover and exploit it quicker
- **Meta-strategies emerge**: AI agents that adaptively switch between strategies based on regime detection
- **Adversarial dynamics**: AI agents trying to detect and exploit other AI agents' patterns (an AI "arms race")

### Implications for Alpha Stack

- **The edge is NOT the algorithm** — it's the data, the infrastructure speed, and the adaptability of the system
- **Regime detection becomes critical** — knowing WHEN to switch strategies matters more than any single strategy
- **Multi-model ensemble approaches** outperform single-model strategies
- **Latency still matters** but in different ways — it's about data processing speed and decision-making frequency, not just order execution speed
- **Self-improving systems** that adapt their own strategies will outperform static ones

---

## 5. Regulatory Evolution

### Global Regulatory Landscape

#### EU — MiCA (Markets in Crypto-Assets)
- **Fully effective** since December 2024
- Comprehensive framework covering crypto-asset issuance, service providers, market abuse
- Stablecoin regulation (asset-referenced tokens, e-money tokens)
- CASP (Crypto-Asset Service Provider) licensing required
- **Impact on Alpha Stack**: If operating in EU, need CASP license or partner with licensed entity. Algorithmic trading is permitted but subject to market abuse rules.

#### United States
- **CLARITY Act** (2025–2026): Bipartisan bill establishing crypto market structure
- **GENIUS Act**: Stablecoin regulation framework passed in 2025
- SEC shifting from enforcement-first to framework-based regulation
- CFTC gaining jurisdiction over crypto commodities (BTC, ETH)
- **Impact**: Regulatory clarity improving. Algorithmic trading is legal and regulated under existing securities/commodities laws. Key concern: registration requirements for automated trading systems.

#### Kenya — CMA (Capital Markets Authority)
- Developing crypto regulatory framework
- Sandbox approach — testing before regulating
- **Impact**: Africa represents a massive growth market. Early entry with compliant infrastructure wins.

#### Key Global Trends
1. **Travel Rule** compliance for crypto transfers (FATF recommendation) — becoming universal
2. **Stablecoin regulation** crystallizing globally — well-regulated stablecoins (USDC, regulated EURC) gain advantage
3. **AI trading regulation** is nascent but coming — EU AI Act classifies financial AI as "high-risk"
4. **Cross-border coordination** improving — IOSCO, FATF setting standards

### Impact on Algorithmic/AI Trading Legality

- Algorithmic trading is **legal everywhere** — the concern is market manipulation, not automation
- **AI-specific regulation** is emerging:
  - EU AI Act: High-risk classification for financial AI → requires explainability, human oversight, risk management
  - US: No federal AI trading regulation yet, but SEC monitoring
  - Trend: **Transparency and auditability requirements** for AI trading systems
- **Key requirement trend**: Ability to explain why the AI made a specific trade (model interpretability)

### Compliance Requirements for AI Trading Systems

By 2028–2030, expect requirements for:
1. **Model documentation**: What data, what architecture, what risk controls
2. **Kill switches**: Ability to halt automated trading instantly
3. **Audit trails**: Complete record of every decision and data input
4. **Human oversight**: Designated human who can intervene
5. **Risk limits**: Pre-defined position limits, loss limits, exposure limits
6. **Regular testing**: Stress testing, scenario analysis, model validation

---

## 6. Infrastructure Changes

### Connectivity

**5G/6G:**
- 5G is already deployed globally; 6G expected ~2030
- Ultra-low latency: 5G delivers <10ms latency; 6G targets <1ms
- Enables mobile-first trading with desktop-class execution speed
- Edge computing at cell towers reduces round-trip time

**Starlink / LEO Satellite Internet:**
- Already providing 20–40ms latency in remote areas
- By 2028: Starlink V2 with laser inter-satellite links — potential for **lower latency than fiber** on long-haul routes (light travels faster in vacuum than glass)
- Trading firms are already using microwave/millimeter-wave links. LEO satellites add another option.
- **Impact**: Geographic advantage erodes. A trader in Nairobi can get similar latency to one in London.

### Edge Computing for Trading

- **Cloud edge locations** (AWS Local Zones, Azure Edge Zones) bringing compute closer to exchange matching engines
- **Co-location** remains important but edge computing reduces the gap
- **Inference at the edge**: Running AI/ML models for signal generation at the edge, not in a central cloud
- By 2030: Expect "edge-native" trading architectures where data ingestion, feature computation, and model inference all happen within milliseconds of the exchange

### Quantum Computing & Quantum Internet

**Quantum Computing (relevant timeline: 2030–2035):**
- Current quantum computers: ~1,000–10,000 qubits, noisy
- By 2030: Expected 100K+ qubit systems with error correction
- **Impact on trading**:
  - Portfolio optimization: Quantum can solve NP-hard optimization problems that classical computers approximate
  - Monte Carlo simulations: Quantum speedup for risk calculations
  - **Cryptography threat**: Current encryption (RSA, ECC) becomes vulnerable. Post-quantum cryptography migration is essential.
  - Early quantum advantage in specific finance problems by ~2030–2032

**Quantum Internet (timeline: 2035+):**
- Quantum key distribution (QKD) for unhackable communication
- Quantum-secured trading links between institutions
- Not an immediate concern but worth monitoring

### T+0 Settlement

- **Already happening**: Crypto settles T+0 (or rather, block-time settlement: seconds)
- **US equities**: Moved to T+1 in May 2024. T+0 is next.
- **India**: Already at T+1 for equities
- **Forex**: CLS Bank exploring T+0 via distributed ledger
- **By 2030**: T+0 becomes the standard for most asset classes
- **Impact**: Massive reduction in settlement risk, margin requirements, and capital locked up in transit

### Infrastructure Summary for Alpha Stack

| Technology | Relevance | Timeline | Priority |
|-----------|-----------|----------|----------|
| 5G/LEO satellite | Latency equalization globally | Now–2028 | Medium |
| Edge computing | Faster signal generation + execution | Now–2028 | High |
| T+0 settlement | Capital efficiency, reduced risk | Now–2030 | Critical |
| Quantum-safe crypto | Security against future quantum attacks | 2028–2032 | Start planning now |
| Quantum computing | Optimization, simulation | 2030–2035 | Monitor |
| Quantum internet | Secure comms | 2035+ | Watch only |

---

## 7. What Alpha Stack Should Do Now to Prepare

### Architecture Decisions (Future-Proofing)

#### 1. Multi-Venue, Multi-Asset from Day One
- **Don't build "forex only" or "crypto only"** — build an abstraction layer that treats forex, crypto, tokenized stocks, tokenized bonds, and commodities as the same thing: **tradable token pairs on settlement rails**
- The tokenization wave means the same architecture should handle EUR/USD, BTC/USDT, and BUIDL/USDC

#### 2. Chain-Agnostic Settlement Layer
- Support Ethereum, Solana, Base, Stellar, Avalanche (the top 5 RWA chains)
- Use intent-based protocols (Across, LI.FI, Socket) for cross-chain execution
- Design for CBDC integration — the settlement rails will change, but the trading logic shouldn't

#### 3. AI-Native Architecture
- **Every component should be API-first and agent-friendly**
- Data pipeline should support real-time ML feature computation
- Strategy layer should support model hot-swapping (deploy new models without downtime)
- Include model monitoring, drift detection, and automated rollback

#### 4. Compliance-First Design
- Build audit logging into the core, not as an afterthought
- Implement kill switches at every level (strategy, venue, asset, system-wide)
- Design for the coming AI explainability requirements
- Support tiered KYC (small = anonymous, large = full KYC — matching CBDC model)

#### 5. Latency-Minded but Not Latency-Obsessed
- For most strategies, 100ms is fine. Don't over-optimize for sub-millisecond at the expense of flexibility
- Focus latency optimization on: data ingestion → feature computation → model inference → order routing
- Edge deployment capability for when it matters

### Skills to Develop

| Skill Area | Why | How to Build |
|-----------|-----|-------------|
| **Smart contract development** | Interacting with DeFi, DEXs, tokenized assets | Solidity, Rust (Solana), Move (Aptos/Sui) |
| **MEV research** | Understanding and defending against MEV | Study Flashbots, MEV auction mechanics |
| **Cross-chain protocols** | Multi-chain trading is the future | Study bridges, intents, messaging protocols (LayerZero, Axelar) |
| **ML/AI for finance** | Competitive table stakes, not edge | Regime detection, ensemble methods, reinforcement learning |
| **Regulatory tech** | Compliance becomes a product feature | Travel Rule compliance, on-chain KYC, audit trail systems |
| **RWA tokenization** | Understanding the asset class | Study Securitize, Centrifuge, Ondo Finance, Maple |
| **CBDC integration** | The new forex plumbing | Study mBridge, Project Mariana, CBDC APIs |

### Partnerships to Consider

1. **Tokenization platforms**: Securitize (powers BlackRock BUIDL), Centrifuge, Ondo Finance — access to tokenized T-bills, credit, stocks
2. **DEX aggregators**: 1inch, Paraswap, Jupiter — best execution across DEXs
3. **Intent solvers**: UniswapX, CoW Protocol, Across — intent-based execution
4. **Compliance providers**: Chainalysis, Elliptic, TRM Labs — on-chain AML/KYC
5. **Data providers**: Dune Analytics, The Graph, RWA.xyz — on-chain analytics
6. **Cloud edge providers**: AWS Local Zones, Akamai — low-latency global deployment
7. **CBDC pilot programs**: If possible, participate in mBridge or Project Mariana testing

### Market Positioning

**Alpha Stack should position as: "The AI-native execution platform for the tokenized economy."**

Key differentiators to build:
1. **Unified trading across forex, crypto, and tokenized RWA** — no one else does this well
2. **AI-optimized execution** — smart order routing that considers DEX, CEX, and dark pool venues
3. **Compliance built in** — audit trails, kill switches, explainability — not bolted on
4. **CBDC-ready** — when digital euros and digital yuan launch, Alpha Stack is already connected
5. **Agent-friendly API** — designed for AI agents as primary users, not just humans

### Priority Roadmap

**Phase 1 (Now – Q4 2026): Foundation**
- [ ] Multi-venue architecture design (forex + crypto + tokenized assets)
- [ ] DEX integration (Uniswap, dYdX, Hyperliquid)
- [ ] Tokenized asset data feeds (RWA.xyz API, on-chain oracles)
- [ ] Compliance logging infrastructure
- [ ] Basic AI/ML pipeline for signal generation

**Phase 2 (2027): Expansion**
- [ ] Tokenized stock/bond trading (Ondo, Securitize assets)
- [ ] Cross-chain execution (Ethereum + Solana + Base minimum)
- [ ] Intent-based execution routing
- [ ] Advanced ML models (regime detection, ensemble)
- [ ] MEV protection integration

**Phase 3 (2028–2029): CBDC Era**
- [ ] CBDC settlement integration (digital euro, e-CNY corridors)
- [ ] 24/7 multi-asset trading capability
- [ ] Edge computing deployment for latency-sensitive strategies
- [ ] Regulatory compliance certifications (MiCA, US framework)
- [ ] Agent-to-agent trading protocol support

**Phase 4 (2030+): AI-Native Markets**
- [ ] Fully autonomous trading agents
- [ ] Quantum-resistant security
- [ ] Cross-CBDC forex (bypassing traditional rails)
- [ ] Self-evolving strategy frameworks
- [ ] Prediction market and RWA composability

---

## Appendix: Key Data Points

### RWA Market Snapshot (July 11, 2026)
- **Total Distributed RWA Value:** $35.70B (+9.00% in 30 days)
- **Total Represented Asset Value:** $375.09B (+7.41% in 30 days)
- **Total Asset Holders:** 1,005,765 (+10.47% in 30 days)
- **Total Stablecoin Value:** $300.41B (+0.84% in 30 days)
- **Total Stablecoin Holders:** 272.43M (+2.81% in 30 days)
- **Top RWA Chain:** Ethereum ($16.0B, 44.85% market share)
- **Fastest Growing RWA Chain:** Avalanche (+58.34% in 30 days)

### Top Tokenized Assets by AUM
1. Tether Gold (XAUT): $2.5B
2. BlackRock BUIDL: $2.9B
3. Ondo USDY: $2.2B
4. Hashnote USYC: $3.1B
5. Franklin Templeton iBENJI: $1.6B

### Stablecoin Market
1. USDT: $190.4B
2. USDC: $72.8B
3. USDS: $7.5B
4. DAI: $4.6B
5. USD1 (Trump-associated): $4.5B

---

## Sources

- RWA.xyz — Live tokenized asset analytics (accessed July 11, 2026)
- Atlantic Council CBDC Tracker
- BIS Innovation Hub project reports
- EU MiCA regulation text
- dYdX, Uniswap, Hyperliquid documentation
- BlackRock, Franklin Templeton, Ondo Finance public disclosures
- BCG/ADDX tokenization market projections
- Citi GPS "Money, Tokens, and Games" report
- FSB Cross-border Payments Roadmap

---

*This report reflects the state of the market as of July 2026 and projections based on current trajectories. The pace of change in this space is accelerating — this document should be updated quarterly.*
