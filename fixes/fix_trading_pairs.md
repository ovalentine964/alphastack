# Fix: Trading Pairs — Crypto Availability Contradiction Resolution

**Date:** 2026-07-11  
**Issue:** research_07_trading_pairs.md claims FXPesa offers "50+ crypto CFDs" while research_tca.md states "FXPesa does NOT offer crypto CFDs"  
**Status:** ✅ RESOLVED

---

## 1. Root Cause: Both Documents Are Correct — Different Entities

**FXPesa operates under TWO separate legal entities with different product offerings:**

| Attribute | Kenya Entity | Seychelles Entity |
|-----------|-------------|-------------------|
| **Legal Name** | EGM Securities Ltd | Equiti Seychelles Ltd |
| **Regulator** | Kenya CMA (License #107) | Seychelles FSA |
| **URL** | `fxpesa.com/ke-en/` | `fxpesa.com/sc-en/` |
| **Products Menu** | Forex, Indices, Commodities, Shares, ETFs | Forex, Indices, Commodities, Shares, ETFs, **Crypto CFDs**, Gold Options |
| **Crypto Available** | ❌ **NO** | ✅ **YES — 50+ pairs** |
| **Leverage** | Up to 1:400 | Up to 1:2000 (forex), 1:200 (crypto) |
| **Account Types** | Standard, Premier | Micro, Classic, Standard, Premier |
| **Portal** | `portal.fxpesa.com` | `sey.portal.equiticlients.com` |

### Verification Source
- Kenya products page (`/ke-en/products/`): Lists forex, shares, indices, commodities, ETFs. **No crypto in menu or page content.**
- Seychelles crypto page (`/sc-en/products/crypto-cfds/`): Dedicated page with "50+ crypto CFDs", 1:200 leverage, full instrument table.

### Why the Confusion?
The research documents were written by different researchers who assumed "FXPesa" is a single entity. In reality:
- **research_tca.md** references EGM Securities (Kenya CMA #107) — correctly states no crypto
- **research_07_trading_pairs.md** references Equiti Group / FSA Seychelles — correctly lists crypto CFDs

---

## 2. Impact on the Alpha Stack System

### Which Entity Should We Use?

**For $7 capital with crypto access → Seychelles entity (`/sc-en/`)**

Reasons:
1. **Micro Account available** (min deposit $0, 1:500 leverage) — ideal for $7
2. **Crypto CFDs available** — enables the full Alpha Stack asset mix
3. **Higher leverage** — 1:2000 on forex, 1:200 on crypto
4. **Same MT5 platform** — no technical changes needed

**Trade-off:** Seychelles FSA regulation is lighter-touch than Kenya CMA. This is acceptable for a $7 learning account.

### What Changes in the Research?

| Document | Original Claim | Correction |
|----------|---------------|------------|
| **research_tca.md** | "FXPesa does NOT offer crypto CFDs" | FXPesa Kenya (EGM Securities) does not. FXPesa Seychelles (Equiti) DOES offer 50+ crypto CFDs. Specify entity. |
| **research_07_trading_pairs.md** | "FXPesa offers 50+ crypto CFDs" | Correct for Seychelles entity. Add entity specification. |
| **research_hybrid_broker_architecture.md** | Assumes FXPesa = forex only, needs CCXT for crypto | Only true if using Kenya entity. With Seychelles entity, crypto is available natively on MT5. |

---

## 3. Verified FXPesa Seychelles Crypto CFDs (Full List)

### Group 1 — 1:200 Leverage (Viable for $7 Account)

| Symbol | Name | Min Trade | Max Trade | Contract Size |
|--------|------|-----------|-----------|---------------|
| ADAUSD.lv | Cardano | 100 | 4000 | 1 |
| AVAXUSD.lv | Avalanche | 0.1 | 400 | 1 |
| BCHUSD.lv | Bitcoin Cash | 0.01 | 100 | 1 |
| BNBUSD.lv | Binance Coin | 0.1 | 100 | 1 |
| BTCUSD.lv | Bitcoin | 0.001 | 4 | 1 |
| BTCXAU.lv | Bitcoin vs Gold | 0.001 | 1 | 1 |
| DOTUSD.lv | Polkadot | 1 | 1000 | 1 |
| ETHUSD.lv | Ethereum | 0.1 | 50 | 1 |
| HBARUSD.lv | Hedera | 100 | 10000 | 1 |
| LINKUSD.lv | Chainlink | 1 | 500 | 1 |

### Group 2 — 1:10 Leverage (Marginal at $7)

| Symbol | Name | Min Trade |
|--------|------|-----------|
| AAVEUSD.lv | Aave | 0.1 |
| ALGOUSD.lv | Algorand | 10 |
| ATOMUSD.lv | Atom | 1 |
| CFXUSD.lv | Conflux | 10 |
| DOGEUSD.lv | Dogecoin | 100 |
| EOSUSD.lv | EOS | 10 |
| ETCUSD.lv | Ethereum Classic | 1 |
| FILUSD.lv | Filecoin | 0.1 |
| FLOWUSD.lv | Flow | 10 |
| GRTUSD.lv | The Graph | 10 |
| ICPUSD.lv | Internet Computer | 0.01 |
| INJUSD.lv | Injective | 0.1 |
| KNCUSD.lv | Kyber Network | 1 |
| LDOUSD.lv | Lido | 1 |
| LTCUSD.lv | Litecoin | 0.1 |
| MANAUSD.lv | Decentraland | 10 |
| MKRUSD.lv | Maker | 0.001 |
| NEOUSD.lv | NEO | 1 |

### Group 3 — 1:2.5 Leverage (NOT Viable at $7)

APEUSD.lv, AXSUSD.lv, BATUSD.lv, CHZUSD.lv, COMPUSD.lv, CRVUSD.lv, CVXUSD.lv, DYDXUSD.lv, ENJUSD.lv, ENSUSD.lv, FXSUSD.lv, GALAUSD.lv, GMTUSD.lv, IMXUSD.lv, LRCUSD.lv, NEARUSD.lv, OMUSD.lv

### Group 4 — 1:1 Leverage (NOT Viable at $7)

1INCHUSD.lv, ACHUSD.lv, DASHUSD.lv, IOTAUSD.lv, JSTUSD.lv, LPTUSD.lv, MINAUSD.lv

### Additional Symbols (Partial List)

OMGUSD.lv, ONDOUSD.lv, OPUSD.lv, PEPEUSD.lv, PYTHUSD.lv, RENDERUSD.lv, SANDUSD.lv, SHIBUSD.lv, STXUSD.lv, SUIUSD.lv, TIAUSD.lv, TRXUSD.lv, UNIUSD.lv, WLDUSD.lv, XLMUSD.lv, XMRUSD.lv, XRPUSD.lv, XTZUSD.lv, YFIUSD.lv, ZECUSD.lv, ZRXUSD.lv

**Total: 70+ crypto CFDs available on FXPesa Seychelles MT5.**

---

## 4. Corrected Trading Pairs Recommendation

### Option A: FXPesa Seychelles Only (Recommended for $7)

All instruments on one broker, one MT5 account, one platform.

**Forex Core (Alpha Stack Tier 1):**
- EUR/USD — 1.4 pip spread, 1:500 leverage
- GBP/USD — 1.8 pip spread, 1:500 leverage
- XAU/USD (Gold) — 0.28 pip spread, 1:500 leverage

**Forex Secondary (Session-Specific):**
- GBP/JPY — 2.3 pip spread, London beast
- USD/JPY — 1.4 pip spread, macro proxy

**Crypto (Group 1 Only — 1:200 Leverage):**
- BTCUSD.lv — Digital gold, macro-driven
- ETHUSD.lv — #2 crypto, DeFi proxy
- ADAUSD.lv — Cheap per unit, good for micro accounts
- DOTUSD.lv — Infrastructure play

**Why This Works:**
- Single broker = single deposit, single platform, unified P&L
- No need for CCXT integration at this stage
- $7 capital stays consolidated (splitting $7 across two brokers is impractical)
- Crypto CFDs on MT5 use the same order interface as forex

### Option B: Hybrid Approach (For Future — $200+ Capital)

When capital grows, add a dedicated crypto exchange for:
- Lower fees (0.04-0.1% vs CFD spreads)
- More pairs (500+ on Binance vs 70+ on FXPesa)
- Spot ownership (not CFD)
- DeFi/staking access

Architecture: FXPesa (MT5) for forex + Binance/Bybit (CCXT) for crypto
→ Already designed in research_hybrid_broker_architecture.md

---

## 5. Updated Pair Watchlist (Corrected)

### Alpha Stack Core 5 — All Available on FXPesa Seychelles

| # | Pair | Type | Leverage | Spread | Verified |
|---|------|------|----------|--------|----------|
| 1 | XAU/USD | Gold CFD | 1:500 | 0.28 pips | ✅ Kenya + Seychelles |
| 2 | EUR/USD | Major FX | 1:500 | 1.4 pips | ✅ Kenya + Seychelles |
| 3 | GBP/USD | Major FX | 1:500 | 1.8 pips | ✅ Kenya + Seychelles |
| 4 | BTCUSD.lv | Crypto CFD | 1:200 | ~$5 | ✅ **Seychelles only** |
| 5 | GBP/JPY | Cross FX | 1:500 | 2.3 pips | ✅ Kenya + Seychelles |

### Phase 1 ($7–$50): Trade 3 Pairs
- EUR/USD or XAU/USD (lowest cost, best SMC patterns)
- No crypto yet (need more margin buffer)

### Phase 2 ($50–$200): Add Crypto
- BTCUSD.lv — macro plays, 24/6 trading
- ETHUSD.lv — secondary crypto exposure

### Phase 3 ($200+): Full Portfolio
- All 5 core pairs + session rotation
- Consider hybrid architecture (add CCXT crypto exchange)

---

## 6. Key Corrections to Existing Documents

### research_tca.md — Required Changes

1. **Header:** Change "Broker: FXPesa (EGM Securities Ltd, regulated by Kenya CMA #107)" → specify entity clearly
2. **Section 11:** Rewrite "CRYPTO: NOT AVAILABLE ON FXPESA" → "Crypto not available on FXPesa Kenya (EGM Securities). Available on FXPesa Seychelles (Equiti Seychelles, FSA-regulated) with 70+ crypto CFDs at 1:200 leverage."
3. **Section 10:** Remove "Don't trade crypto — FXPesa doesn't offer it" → "Don't trade Group 2–4 crypto (leverage too low for $7). Group 1 crypto (BTC, ETH, ADA, DOT, LINK, BNB, AVAX, BCH, HBAR) at 1:200 leverage is viable."

### research_07_trading_pairs.md — Required Changes

1. **Header:** Add entity specification: "Broker: FXPesa Seychelles (Equiti Seychelles Ltd, FSA-regulated)"
2. **Section 3.1:** Verify all listed symbols match the actual FXPesa Seychelles product list (most are correct, but SOLUSD.lv and XRPUSD.lv need verification — SOLUSD.lv was NOT found in the verified list; XRPUSD.lv WAS found)
3. **Section 3.2:** Leverage groups are confirmed correct from the official page

### research_hybrid_broker_architecture.md — Required Changes

1. Add note: "If using FXPesa Seychelles, crypto CFDs are available natively on MT5. The hybrid CCXT architecture is recommended for Phase 3+ when seeking lower fees, spot ownership, or access to 500+ crypto pairs."
2. The architecture itself remains valid as a future evolution path

---

## 7. Final Answer

**The contradiction is resolved:**

- **research_07 is correct** for FXPesa Seychelles (FSA) — 70+ crypto CFDs, 1:200 leverage
- **research_tca is correct** for FXPesa Kenya (CMA) — no crypto CFDs
- **Both documents failed to specify which FXPesa entity** they were referencing

**Recommendation:** Use FXPesa Seychelles for the Alpha Stack system. This gives access to forex, gold, AND crypto on a single MT5 account with a single $7 deposit. The hybrid CCXT architecture becomes relevant at $200+ capital when seeking lower crypto trading costs.

---

*Resolution based on live verification of fxpesa.com/ke-en/ and fxpesa.com/sc-en/ product pages as of 2026-07-11.*
