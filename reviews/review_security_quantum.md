# Quantum-Resistant Security Review — Alpha Stack

> **Reviewer:** Security Review Agent (Quantum-Resistant Specialist)  
> **Date:** 2026-07-11  
> **Scope:** Post-quantum cryptography implementation, hybrid schemes, crypto wallet protection, harvest-now-decrypt-later mitigation, timeline assessment, and gap analysis  
> **Documents Reviewed:** `architecture_security.md`, `research_quantum_unsolved.md`, `research_06_quantum_agi_future_tech.md`  
> **Overall Verdict: ✅ SOUND with MODERATE GAPS — strong foundation, needs hardening in specific areas**

---

## Executive Summary

Alpha Stack's security architecture demonstrates **above-average quantum readiness** for a 2026-era system. The hybrid X25519 + ML-KEM-768 approach is architecturally sound, the crypto-agility framework is well-designed, and the PQC migration roadmap is realistic. However, several critical gaps exist that could undermine the quantum-resistant posture if not addressed before deployment.

**Risk Rating:** 🟡 MEDIUM — Quantum threat is not imminent (10-20 years for CRQC), but "harvest now, decrypt later" exposure is **active today** for any data encrypted with classical-only schemes.

---

## 1. Post-Quantum Cryptography Implementation — VALIDATION

### 1.1 Algorithm Selection ✅ CORRECT

| Choice | Assessment | Notes |
|--------|------------|-------|
| ML-KEM-768 (FIPS 203) for key exchange | ✅ Correct | NIST standard, appropriate security level (roughly equivalent to AES-192) |
| ML-DSA-65 (FIPS 204) for signatures | ✅ Correct | NIST standard, good balance of signature size vs security |
| SLH-DSA (FIPS 205) as backup | ✅ Correct | Hash-based, conservative fallback if lattice assumptions break |
| FN-DSA (FALCON) noted | ⚠️ Caution | FALCON implementation is notoriously hard to constant-time; avoid unless expert review confirms side-channel resistance |

### 1.2 NIST Standard References ✅ ACCURATE

The architecture correctly references:
- **FIPS 203** = ML-KEM (Module-Lattice-Based Key-Encapsulation Mechanism)
- **FIPS 204** = ML-DSA (Module-Lattice-Based Digital Signature Algorithm)
- **FIPS 205** = SLH-DSA (Stateless Hash-Based Digital Signature Algorithm)

These were finalized by NIST in August 2024. The naming is correct.

### 1.3 Security Level Assessment ⚠️ NEEDS CLARIFICATION

The architecture doesn't explicitly state the NIST security levels:

| Algorithm | NIST Level | Equivalent Classical | Assessment |
|-----------|-----------|---------------------|------------|
| ML-KEM-512 | 1 | AES-128 | Not used (good — too low for financial data) |
| **ML-KEM-768** | 3 | AES-192 | ✅ Used — appropriate for financial systems |
| ML-KEM-1024 | 5 | AES-256 | Not used — consider for master keys |
| **ML-DSA-65** | 3 | AES-192 | ✅ Used — appropriate for JWT signing |
| ML-DSA-87 | 5 | AES-256 | Not used — consider for long-lived certificates |

**Recommendation:** ML-KEM-768 + ML-DSA-65 is the correct sweet spot for a trading system. Level 3 provides adequate security margin without excessive key/signature sizes. For **master keys and root certificates** with 20+ year lifetimes, consider upgrading to ML-KEM-1024 + ML-DSA-87.

### 1.4 Crypto-Agility Framework ✅ WELL DESIGNED

The `AlgorithmSet` enum pattern with trait objects (`Box<dyn KeyEncapsulation>`, `Box<dyn SignatureScheme>`) is a textbook crypto-agility implementation. This allows:

- Runtime algorithm switching without code rewrites
- Gradual migration from Classical → Hybrid → PostQuantum
- Emergency algorithm swap if a vulnerability is discovered in ML-KEM or ML-DSA

**One concern:** The trait-based approach uses dynamic dispatch, which could be susceptible to timing side-channels if the compiler doesn't inline consistently. Ensure cryptographic operations are constant-time regardless of dispatch path.

---

## 2. Hybrid X25519 + ML-KEM-768 — SOUNDNESS ASSESSMENT

### 2.1 Key Exchange Hybrid ✅ SOUND

```
Shared Secret = X25519_SS || ML-KEM-768_SS → HKDF
```

**Assessment:** This is the correct approach. The concatenation-then-HKDF pattern ensures:
- If X25519 is broken (quantum), ML-KEM-768 still protects the shared secret
- If ML-KEM is broken (lattice assumption fails), X25519 still protects against classical attacks
- HKDF binding prevents "mixing" attacks where an attacker manipulates one component

**Critical validation point:** The HKDF step is essential. Simply concatenating two shared secrets without key derivation would be vulnerable to a class of attacks where one component is manipulated. The architecture correctly specifies HKDF — ✅.

### 2.2 Signature Hybrid ✅ SOUND (with caveats)

```
sig_classical = Ed25519.sign(header.payload)
sig_pq = ML-DSA-65.sign(header.payload)
signature = sig_classical || sig_pq
// Valid if BOTH signatures verify
```

**Assessment:** "Both must pass" is the correct policy for defense-in-depth. However:

**⚠️ Caveat 1 — JWT Size:** ML-DSA-65 signatures are ~3,309 bytes. Combined with Ed25519 (64 bytes), the JWT signature block alone is ~3,373 bytes. For a typical JWT payload, the total token could be **4-5 KB** vs ~500 bytes for RS256. This impacts:
- HTTP header size limits (some proxies cap at 8 KB)
- WebSocket message overhead
- Mobile/bandwidth-constrained clients

**Recommendation:** Consider using JWT only for access tokens (short-lived, 15 min). For refresh tokens and long-lived credentials, use opaque tokens stored server-side to avoid the size overhead.

**⚠️ Caveat 2 — Verification Order:** The architecture says "Valid if BOTH signatures verify" but doesn't specify verification order. For side-channel resistance, always verify both signatures in constant time (don't short-circuit on first failure). This prevents timing-based oracle attacks.

### 2.3 Missing: TLS Hybrid Configuration ⚠️ GAP

The architecture describes the hybrid key exchange conceptually but doesn't provide concrete TLS configuration. In 2026, the practical implementation depends on:

- **OpenSSL 3.5+:** Supports ML-KEM via `oqs-provider`
- **rustls 0.23+:** Does NOT yet support ML-KEM natively as of mid-2026
- **BoringSSL:** Google's fork supports X25519Kyber768 (hybrid) since Chrome 124

**Gap:** If using `rustls` (as specified in Appendix B), hybrid TLS may not be available without custom implementation or switching to OpenSSL bindings.

**Recommendation:** Evaluate `liboqs` (Open Quantum Safe) bindings for Rust, or switch to `openssl` crate for TLS termination until `rustls` adds native PQC support.

---

## 3. Crypto Wallet Quantum Protection — VALIDATION

### 3.1 Blockchain-Specific Threats ✅ IDENTIFIED

The architecture correctly identifies:

| Blockchain | Algorithm | Quantum Threat | Status in Architecture |
|-----------|-----------|---------------|----------------------|
| Bitcoin | ECDSA secp256k1 | Shor's algorithm | ✅ Identified |
| Ethereum | ECDSA secp256k1 | Shor's algorithm | ✅ Identified |
| TLS | ECDHE | Shor's algorithm | ✅ Mitigated via hybrid |
| AES-256 | Symmetric | Grover (128-bit effective) | ✅ Correctly noted as sufficient |
| SHA-256 | Hash | Grover (128-bit effective) | ✅ Correctly noted as sufficient |

### 3.2 Bitcoin-Specific Protection ⚠️ INCOMPLETE

The architecture says: *"Use new addresses (hide pubkey until spend)"* — this is correct for P2PKH/P2SH addresses where the public key is not revealed until the first spend. However:

**Gap 1:** P2WPKH (SegWit) and P2TR (Taproot) addresses have different exposure profiles:
- **P2WPKH:** Public key hash is visible, but pubkey only revealed on spend — same as P2PKH ✅
- **P2TR (Taproot):** The x-only public key is embedded in the address itself — **public key is always exposed** ⚠️

**Gap 2:** No mention of the "one-time use" principle. If an address is reused (common with exchanges), the public key is permanently exposed to quantum attack.

**Gap 3:** No mention of the race condition: an attacker with a CRQC could derive the private key from a broadcast transaction's public key and front-run the confirmation. Bitcoin's ~10-minute block time creates a vulnerability window.

**Recommendation:** For any Alpha Stack-controlled Bitcoin wallets:
- Use P2PKH/P2SH (not P2TR) for maximum quantum protection
- Never reuse addresses
- Sweep funds to new addresses periodically
- Monitor Bitcoin Improvement Proposals for PQC migration

### 3.3 Ethereum-Specific Protection ⚠️ INCOMPLETE

The architecture mentions *"EIP-4337 account abstraction enables PQC signatures"* — this is directionally correct but premature:

**Reality check (2026):** EIP-4337 (Account Abstraction) is live but does NOT yet support PQC signature schemes. The `UserOperation` signature validation is flexible enough to support them in theory, but no PQC signature verifier has been deployed on Ethereum mainnet.

**Recommendation:** Monitor Ethereum's PQC roadmap. The account abstraction path is correct, but don't rely on it being available before 2028-2030.

### 3.4 Wallet Key Management ⚠️ GAP

The architecture doesn't address:

1. **HD wallet derivation keys:** BIP-32/39/44 hierarchical deterministic wallets use ECDSA for master key derivation. If the master public key is exposed, all derived keys are compromised.

2. **Multi-signature wallets:** If using ECDSA-based multisig, all signers must migrate simultaneously to PQC — coordination challenge.

3. **Hardware wallet compatibility:** No hardware wallet (Ledger, Trezor) supports PQC as of 2026. Any PQC wallet solution would need to be software-based initially.

**Recommendation:** For now, the best protection for crypto wallets is:
- Cold storage (air-gapped) for long-term holdings
- Address rotation (never reuse)
- Small balances per address (limit exposure)
- Monitor chain-specific PQC upgrade proposals

---

## 4. Harvest Now, Decrypt Later (HNDL) — MITIGATION ASSESSMENT

### 4.1 HNDL Threat Recognition ✅ EXCELLENT

The architecture correctly identifies HNDL as the most immediate quantum threat. The classification in the threat model is appropriate:

> **T5: Quantum Decryption** — Harvest-now-decrypt-later on stored data — **Critical** impact, **Low (future)** likelihood

This is the correct framing: the attack is happening now (data collection), but the decryption capability is future.

### 4.2 HNDL Exposure Inventory ⚠️ INCOMPLETE

The architecture identifies general HNDL risks but doesn't provide a specific exposure inventory. Here's what should be assessed:

| Data Type | Current Encryption | HNDL Exposure | Priority |
|-----------|-------------------|---------------|----------|
| **API traffic (TLS)** | TLS 1.3 (ECDHE) | 🔴 HIGH — captured in transit, RSA/ECC broken later | P1 |
| **JWT tokens (transit)** | RS256 / Ed25519 | 🔴 HIGH — captured tokens can be forged | P1 |
| **Stored credentials** | AES-256-GCM (wrapped by KMS) | 🟡 MEDIUM — AES-256 quantum-safe, but KMS key exchange may not be | P2 |
| **Audit logs** | AES-256-GCM at rest | 🟢 LOW — symmetric encryption is quantum-resistant | P3 |
| **Database records** | AES-256-GCM at rest | 🟢 LOW — same as above | P3 |
| **Backup tapes** | AES-256-GCM | 🟡 MEDIUM — if key exchange for backup encryption uses RSA/ECC | P2 |
| **Historical API keys** | Argon2id hashed | 🟢 LOW — password hashing is quantum-resistant | P3 |

### 4.3 HNDL Mitigation Strategy ✅ CORRECT APPROACH

The phased migration roadmap (Phase 1-5, Q3 2026 → 2028+) prioritizes correctly:
1. First: Long-lived secrets and stored data (highest HNDL exposure)
2. Second: Internal service-to-service communication
3. Third: External client-facing APIs
4. Finally: Full PQC migration

**Gap:** The architecture doesn't specify what to do with **already-encrypted historical data**. Data encrypted with RSA-2048 key wrapping before the migration remains vulnerable. A re-encryption strategy for existing data at rest is needed.

**Recommendation:** During Phase 1 (Q3 2026), inventory ALL encrypted data and classify by:
- Encryption method (RSA-wrapped vs ECC-wrapped vs pure AES)
- Data sensitivity and retention period
- Re-encryption feasibility

Then execute a bulk re-encryption pass for all RSA/ECC-wrapped DEKs.

---

## 5. Quantum Threat Timeline Assessment

### 5.1 Architecture's Timeline vs Research Consensus

The architecture provides this timeline:

| Milestone | Architecture Estimate | Research Consensus | Assessment |
|-----------|----------------------|-------------------|------------|
| NIST PQC standards finalized | 2024 (done) | 2024 (done) | ✅ Accurate |
| Early PQC deployment | 2025-2026 | 2025-2026 (Chrome, Cloudflare) | ✅ Accurate |
| Regulatory mandates | 2027-2030 | 2027-2030 (NSA, NIST guidelines) | ✅ Accurate |
| CRQC breaking RSA-2048 | 2035-2045 | 2035-2045 (wide uncertainty) | ✅ Accurate |
| Full PQC migration in finance | 2030-2035 | 2030-2035 | ✅ Accurate |

**Assessment:** The timeline is realistic and aligns with both the research documents and current expert consensus. The architecture correctly identifies the **10-20 year window** for CRQC arrival while emphasizing that HNDL makes this a today problem.

### 5.2 Key Timeline Risks

**Risk 1 — Accelerated Timeline:** Some estimates suggest CRQC could arrive by 2030-2035 (aggressive estimates from Google, IBM). If this happens, the Phase 5 "monitor & adapt" period (2028+) becomes critical.

**Risk 2 — "Q-Day" Surprise:** A breakthrough in quantum error correction or a new algorithm could accelerate the timeline. The architecture's crypto-agility framework is the correct mitigation.

**Risk 3 — Regulatory Acceleration:** The Federal Reserve (Sep 2025) has already published HNDL risk guidance. If regulators mandate PQC for financial systems by 2028 (as some industry groups suggest), the Phase 4-5 timeline may need compression.

### 5.3 Timeline Recommendation

The architecture's phased approach is sound, but I recommend adding a **"Phase 3.5"** between hybrid deployment and full migration:

```
Phase 3.5 (Q2-Q3 2027): HNDL DATA REMEDIATION
├── Bulk re-encrypt all RSA/ECC-wrapped DEKs with PQC-resistant wrapping
├── Re-issue all long-lived certificates with hybrid signatures
├── Rotate all historical API keys
├── Verify no legacy encryption paths remain
└── Document residual HNDL exposure (if any)
```

---

## 6. Quantum Security Gaps — DETAILED ANALYSIS

### 6.1 CRITICAL GAPS (Address before production)

#### Gap 1: JWT RS256 Signing — NOT Quantum-Resistant ❌

**Problem:** Section 2.2 specifies RS256 (RSA + SHA-256) for JWT signing. RSA is broken by Shor's algorithm. While the hybrid Ed25519 + ML-DSA-65 approach is described in Section 5.3, the **actual JWT implementation in Section 2.2 uses RS256**.

**Impact:** All JWT tokens signed with RS256 are forgeable once a CRQC exists. Captured tokens (HNDL) can be forged retroactively.

**Fix:** The production JWT implementation must use the hybrid scheme described in 5.3, not RS256. Update Section 2.2 to reference the hybrid signing as the production configuration.

#### Gap 2: RSA-4096 JWT Key — Quantum-Breakable ❌

**Problem:** Section 2.2 specifies "RSA-4096 keypair for JWT signing" and Section 3.5 lists "JWT signing key (RSA-4096)" with 90-day rotation. RSA-4096 is still broken by Shor's algorithm (just requires more qubits).

**Impact:** Even with 90-day rotation, captured JWT verification keys could allow token forgery.

**Fix:** Migrate to Ed25519 + ML-DSA-65 hybrid signing as specified in the quantum-resistant section. The rotation period is fine, but the algorithm must change.

#### Gap 3: `age` Encryption Library — Classical-Only ⚠️

**Problem:** Section 3.3 uses the `age` encryption library (X25519 + ChaCha20-Poly1305) for the encrypted file fallback. `age` uses X25519 for key exchange — not quantum-resistant.

**Impact:** Any encrypted credential files created with `age` are vulnerable to HNDL attacks.

**Fix:** Either:
- (a) Wrap the `age` encryption with an additional ML-KEM layer (hybrid approach)
- (b) Use `liboqs` for direct PQC encryption of credential files
- (c) Accept the risk if credential files are only stored locally and never transmitted

### 6.2 HIGH-PRIORITY GAPS (Address within 6 months)

#### Gap 4: Fernet (AES-128-CBC) — Weak by Modern Standards ⚠️

**Problem:** Section 3.4 mentions "Fernet (AES-128-CBC + HMAC)" as a baseline, though it notes "Upgraded to AES-256-GCM for production." Fernet uses AES-128, which provides only 64-bit security against Grover's algorithm.

**Impact:** If any production code still uses Fernet, it's not quantum-safe.

**Fix:** Ensure the production codebase uses AES-256-GCM exclusively. Remove all Fernet references. AES-256 provides 128-bit quantum security (sufficient).

#### Gap 5: API Request Signing (HMAC-SHA256) — Not Addressed ⚠️

**Problem:** Section 4.7 uses HMAC-SHA256 for API request signing. While HMAC-SHA256 is quantum-resistant (Grover only halves the security to 128-bit), the architecture doesn't discuss whether the API keys themselves are transmitted via quantum-resistant channels.

**Impact:** If API secrets are exchanged via RSA/ECC-protected channels, they're vulnerable to HNDL.

**Fix:** Ensure API key provisioning uses PQC-protected channels. The HMAC-SHA256 signing itself is fine.

#### Gap 6: OAuth2 Token Exchange — Classical TLS ⚠️

**Problem:** Section 6.6 describes OAuth2 flows for broker connections. These use standard TLS (ECDHE) for the token exchange. If captured, the authorization codes and tokens could be decrypted once ECDHE is broken.

**Impact:** Broker OAuth2 tokens captured in transit could be used to access user accounts retroactively.

**Fix:** When broker APIs support PQC TLS (likely 2028+), ensure OAuth2 flows use hybrid TLS. In the interim, the short lifetime of OAuth2 authorization codes (typically 10 minutes) limits HNDL exposure.

### 6.3 MEDIUM-PRIORITY GAPS (Address within 12 months)

#### Gap 7: QRNG Dependency on External Service ⚠️

**Problem:** Section 5.6 proposes QRNG from the ANU Quantum Random Number Generator API. This creates a dependency on an external service for cryptographic randomness. If the service is compromised or unavailable, the system falls back to CSPRNG.

**Impact:** Not a direct quantum vulnerability, but reduces the security margin.

**Recommendation:** Use QRNG as a supplementary entropy source, not the primary one. The OS CSPRNG (which is already quantum-resistant) should remain the primary source, with QRNG mixed in as additional entropy.

#### Gap 8: MT5 Bridge TLS — No PQC Path Specified ⚠️

**Problem:** Section 6.5 specifies "TLS 1.3 mutual authentication (mTLS)" for the MT5 bridge but doesn't discuss PQC migration for this internal channel.

**Impact:** If an attacker captures MT5 bridge traffic today, they could decrypt it when CRQC arrives. Broker credentials transmitted over this channel would be exposed.

**Fix:** Add PQC migration for internal mTLS to the roadmap (Phase 2 or 3).

#### Gap 9: TOTP Secret Storage — Classical Key Wrapping ⚠️

**Problem:** Section 2.3 describes TOTP secrets encrypted with "user's derived key (AES-256-GCM)." The AES-256 part is quantum-safe, but the key derivation/exchange mechanism isn't specified as PQC-resistant.

**Impact:** If the DEK wrapping uses RSA/ECC, the TOTP secrets could be decrypted retroactively.

**Fix:** Ensure the key hierarchy uses PQC-resistant key wrapping for DEKs.

#### Gap 10: Backup Code Storage — No Quantum Threat Analysis ⚠️

**Problem:** Section 2.3 describes backup codes hashed with Argon2id. Argon2id is quantum-resistant (memory-hard), but the backup codes themselves are only 8 characters alphanumeric. Grover's algorithm could provide a quadratic speedup for brute-force.

**Impact:** Low — 8-character alphanumeric with Argon2id's memory-hardness makes quantum brute-force impractical. But the architecture should document this analysis.

### 6.4 LOW-PRIORITY GAPS (Monitor)

#### Gap 11: Hash Chain for Audit Logs — SHA-256 ✅ (but document)

**Problem:** Section 7.4 uses SHA-256 for the audit log hash chain. SHA-256 provides 128-bit quantum security via Grover's algorithm — sufficient.

**Status:** No action needed, but should be documented in the quantum-safety table.

#### Gap 12: Password Hashing — Argon2id ✅ (sufficient)

**Problem:** Argon2id with 64MB memory cost is quantum-resistant. Memory-hardness prevents quantum speedup.

**Status:** No action needed. Correctly identified in the architecture.

#### Gap 13: CSPRNG — OS-Provided ✅ (sufficient)

**Problem:** OS-provided CSPRNG (e.g., `/dev/urandom`) is quantum-resistant — it uses entropy pools that are not susceptible to quantum attacks.

**Status:** No action needed.

---

## 7. Comparative Assessment

### 7.1 How Alpha Stack Compares to Industry

| Capability | Alpha Stack (2026) | Google/Cloudflare (2026) | Typical FinTech (2026) | Assessment |
|-----------|-------------------|-------------------------|----------------------|------------|
| Hybrid TLS (X25519 + ML-KEM) | Planned (Phase 2-3) | ✅ Deployed (Chrome 124+) | ❌ Not started | 🟡 Behind leaders, ahead of industry |
| Hybrid JWT signing | Designed (not implemented) | N/A (not JWT-based) | ❌ RS256 only | 🟢 Ahead of most |
| Crypto-agility framework | ✅ Designed | ✅ Internal | ❌ Hardcoded | 🟢 Ahead of most |
| HNDL threat awareness | ✅ Documented | ✅ Active mitigation | ⚠️ Vague awareness | 🟢 Ahead of most |
| QRNG integration | ✅ Planned | ✅ (Cloudflare) | ❌ None | 🟢 Ahead of most |
| PQC migration roadmap | ✅ Phased (2026-2028+) | ✅ Active | ❌ No plan | 🟡 Good roadmap, execution TBD |

### 7.2 Maturity Model Assessment

```
Quantum Readiness Maturity:

Level 1: Unaware        ─── Most startups (2026)
Level 2: Aware          ─── Some fintechs
Level 3: Planning       ─── Alpha Stack ← YOU ARE HERE
Level 4: Implementing   ─── Google, Cloudflare, IBM
Level 5: Deployed       ─── (Nobody fully yet, 2026)
```

Alpha Stack is at **Level 3 (Planning)** with a clear path to Level 4. This is ahead of the financial industry average but behind quantum-forward tech companies.

---

## 8. Specific Technical Corrections

### 8.1 Corrections Required in architecture_security.md

| Section | Issue | Correction |
|---------|-------|------------|
| 2.2 | RS256 for JWT | Change to hybrid Ed25519 + ML-DSA-65 (or note "Phase 1: RS256, Phase 4: Hybrid") |
| 2.2 | RSA-4096 for JWT signing | Change to Ed25519 + ML-DSA-65 hybrid keypair |
| 3.3 | `age` library (X25519) | Add note about PQC wrapper or alternative |
| 3.4 | Fernet mentioned | Remove or explicitly note "only AES-256-GCM in production" |
| 5.3 | Hybrid JWT "Valid if BOTH signatures verify" | Add: "Verify in constant-time, no short-circuit" |
| 5.7 | "Use new addresses (hide pubkey until spend)" | Add: "P2TR (Taproot) exposes pubkey — use P2PKH/P2SH for quantum protection" |
| Appendix A | Missing FALCON warning | Add: "FN-DSA (FALCON): Requires expert side-channel review; not recommended for production without formal verification" |

### 8.2 Additions Recommended

| Section | Addition |
|---------|----------|
| 5.1 | Add explicit HNDL exposure inventory table (see Section 4.2 above) |
| 5.5 | Add "Phase 3.5: HNDL Data Remediation" between Phases 3 and 4 |
| 5.7 | Add Bitcoin address type analysis (P2PKH vs P2WPKH vs P2TR) |
| 5.7 | Add Ethereum PQC timeline reality check (EIP-4337 doesn't support PQC yet) |
| Appendix A | Add NIST security level column (1, 3, 5) |
| New | Add "Quantum Threat Model" section with specific attack scenarios |

---

## 9. Recommendations — Priority Order

### Immediate (Before Production Launch)

1. **🔴 Fix JWT algorithm:** Replace RS256 with Ed25519 (classical-only initially, hybrid in Phase 4). RS256 is the single biggest HNDL exposure in the current design.

2. **🔴 Add HNDL exposure inventory:** Document every piece of data encrypted with classical-only algorithms and set remediation deadlines.

3. **🟡 Remove Fernet references:** Ensure only AES-256-GCM is used in production code paths.

### Short-Term (Q3-Q4 2026)

4. **🟡 Audit `age` library usage:** Either wrap with PQC layer or accept documented risk for local-only credential files.

5. **🟡 Add PQC TLS evaluation:** Assess `liboqs` or OpenSSL 3.5+ for hybrid TLS in Rust. The `rustls` gap needs a decision.

6. **🟡 Document internal TLS PQC path:** MT5 bridge, inter-service communication, and database connections need PQC migration plans.

### Medium-Term (2027)

7. **🟢 Execute Phase 3.5 (HNDL remediation):** Re-encrypt all RSA/ECC-wrapped DEKs.

8. **🟢 Deploy hybrid TLS for external APIs:** When client support is ready.

9. **🟢 Add constant-time verification:** For hybrid JWT signature verification.

### Long-Term (2028+)

10. **🟢 Monitor blockchain PQC upgrades:** Bitcoin and Ethereum PQC migration proposals.

11. **🟢 Evaluate QRNG as entropy supplement:** Not primary, but additional entropy source.

12. **🟢 Full PQC migration:** When industry support is mature.

---

## 10. Conclusion

Alpha Stack's quantum-resistant security architecture is **well-designed and forward-thinking**. The hybrid approach, crypto-agility framework, and phased migration roadmap are all correct in principle. The main issues are:

1. **Implementation gap:** The production JWT configuration (RS256) contradicts the quantum-resistant design (hybrid Ed25519 + ML-DSA-65). This must be resolved before deployment.

2. **HNDL exposure gap:** The architecture recognizes the threat but doesn't provide a concrete exposure inventory or remediation plan for existing encrypted data.

3. **Library-level gaps:** The `age` library and potential `rustls` limitations need explicit workarounds or documented risk acceptance.

4. **Wallet protection gap:** The crypto wallet quantum protection is high-level and needs specific, actionable measures for Bitcoin address types and Ethereum account abstraction.

**Overall: The architecture is sound at the design level. The gaps are implementation details that can be addressed in the first 6 months of the roadmap.** The quantum threat timeline (10-20 years for CRQC) provides adequate runway, but HNDL exposure makes PQC migration a **today** priority for long-lived secrets.

**Final Risk Rating: 🟡 MEDIUM — Well-designed, needs implementation hardening.**

---

*This review should be re-evaluated quarterly, or whenever NIST publishes updated PQC implementation guidance, or when a significant quantum computing milestone is reached.*
