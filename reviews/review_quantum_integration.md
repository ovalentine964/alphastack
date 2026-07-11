# Quantum Integration Review — Alpha Stack

> **Reviewer:** Quantum Integration Review Agent  
> **Date:** 2026-07-11  
> **Scope:** Validate quantum-resistant security, integration path realism, algorithm identification, PQC migration plan, threat timeline, and gap analysis  
> **Documents Reviewed:** `architecture_security.md`, `fix_security_quantum.md`, `research_quantum_unsolved.md`, `research_06_quantum_agi_future_tech.md`  
> **Overall Verdict:** 🟡 **SOUND WITH GAPS** — Architecture is well-designed; several areas need strengthening before production

---

## Executive Summary

The Alpha Stack quantum integration is **impressively thorough for a system under active development**. The security architecture demonstrates genuine understanding of both the quantum threat landscape and post-quantum countermeasures. The research documents show awareness of the gap between quantum hype and reality. However, there are **5 critical issues**, **7 high-priority gaps**, and **12 medium-priority improvements** that must be addressed.

**Key strengths:**
- Hybrid cryptography strategy is correct and well-designed
- Crypto-agility abstraction layer is forward-thinking
- HNDL (Harvest Now, Decrypt Later) threat is properly identified as the #1 near-term quantum risk
- Quantum-inspired algorithms correctly separated from quantum hardware requirements
- PQC migration roadmap is phased and realistic

**Key weaknesses:**
- JWT implementation contradicts quantum-resistant design (acknowledged in fix doc, but not yet implemented)
- Bitcoin Taproot exposure was missed in original architecture (fix doc addresses this)
- No quantum-safe key exchange for broker connections
- Quantum timeline estimates may be optimistic on some fronts and pessimistic on others
- QRNG integration is described but lacks fallback/reliability design

---

## Validation 1: Is Quantum-Resistant Security Properly Implemented?

### Verdict: 🟡 **DESIGNED BUT NOT IMPLEMENTED — Critical contradictions remain**

#### What's Correct

1. **Hybrid cryptography strategy** (Section 5.3) is textbook-correct:
   - X25519 + ML-KEM-768 for key exchange
   - Ed25519 + ML-DSA-65 for signatures
   - "Both must be broken" security guarantee is the right approach during transition

2. **Crypto-agility framework** (Section 5.4) is well-architected:
   - Trait-based abstraction (`KeyEncapsulation`, `SignatureScheme`)
   - Algorithm registry with runtime swapping
   - This is exactly what NIST recommends for PQC migration

3. **AES-256 and SHA-256 assessment** (Section 5.7) is correct:
   - Grover's algorithm reduces AES-256 to 128-bit effective security — still sufficient
   - SHA-256 similarly remains quantum-resistant
   - Argon2id is not quantum-vulnerable (memory-hard, not algebraic)

4. **NIST PQC algorithm selection** (Section 5.2) is appropriate:
   - ML-KEM-768 (NIST Level 3) provides strong security margin
   - ML-DSA-65 (NIST Level 3) for signatures — good balance of size and security
   - SPHINCS+ as backup — correct conservative choice (hash-based, different security assumptions)

#### Critical Issues

| # | Issue | Severity | Status |
|---|-------|----------|--------|
| 1 | **JWT RS256 contradiction** — Sections 2.2/3.5 specify RS256 (RSA-4096) while Section 5.3 specifies hybrid Ed25519+ML-DSA-65 | 🔴 CRITICAL | Fix designed in `fix_security_quantum.md`, **not yet implemented** |
| 2 | **No PQC for broker connections** — MT5 bridge uses mTLS with classical certificates; broker APIs use classical TLS | 🔴 CRITICAL | Not addressed in any document |
| 3 | **Audit log hash chain uses SHA-256 only** — While SHA-256 is quantum-resistant for collision resistance, the hash chain integrity model should be updated to reflect quantum-aware threat assessment | 🟡 MEDIUM | Not addressed |
| 4 | **KMS key wrapping algorithm unspecified** — Section 3.1 shows DEK wrapped by Master Key but doesn't specify if the wrapping uses RSA/ECC (quantum-vulnerable) or AES (quantum-safe) | 🟡 MEDIUM | Needs clarification |

#### Detailed Issue Analysis

**Issue 1: JWT RS256 (acknowledged, fix designed)**

The `fix_security_quantum.md` document correctly identifies this as a critical contradiction and designs a two-phase fix:
- Phase A: RS256 → Ed25519 (pre-production)
- Phase B: Ed25519 → Hybrid Ed25519 + ML-DSA-65 (Phase 4, 2028)

**Assessment of the fix:**
- ✅ Constant-time dual verification is correctly specified
- ✅ Token size management strategy (opaque refresh tokens) is practical
- ✅ HNDL exposure window is honestly documented
- ⚠️ The fix targets Phase 4 (2028) for hybrid — this is **too late** if the goal is "quantum-ready from day one" (Section 1.1 philosophy). The HNDL window for JWTs issued between production and 2028 is real.
- ⚠️ No mention of JWT `alg` header confusion attacks — an attacker could strip the `alg2` field and force classical-only verification. Mitigation: server-side enforcement of hybrid verification, never trust client-specified algorithm preferences.

**Issue 2: Broker Connection PQC Gap**

The architecture focuses heavily on PQC for internal systems (JWT, TLS, credential storage) but **completely ignores broker connections**:

- MT5 bridge mTLS: Uses classical X.25519/ECDHE — no hybrid option mentioned
- CCXT/exchange API connections: Standard TLS 1.3 — classical key exchange
- REST API broker connections (OANDA, etc.): Standard TLS — classical

**Risk:** If an adversary captures broker API traffic today (HNDL), they could decrypt it with a future CRQC, revealing trading strategies, positions, and account details. This is the same HNDL risk the architecture correctly identifies for internal data but fails to address for external connections.

**Recommendation:**
- For broker APIs where Alpha Stack controls the TLS configuration: enable hybrid TLS when broker supports it (most don't yet, but monitor)
- For MT5 bridge: document as accepted risk with timeline for migration when MetaQuotes adds PQC support
- Add broker connection PQC status to the migration roadmap

---

## Validation 2: Is the Quantum Computing Integration Path Realistic?

### Verdict: 🟢 **YES — Appropriately cautious and phased**

#### Assessment of the Integration Roadmap

The `research_quantum_unsolved.md` Section 6.5 roadmap is well-calibrated:

| Phase | Timeline | Assessment |
|-------|----------|------------|
| Q3 2026: Foundation | Cryptographic audit, quantum-inspired solvers, QUBO refactor | ✅ Realistic, achievable |
| Q4 2026: Pilot | QRNG integration, QAOA small portfolio test, PQC hybrid internal | ✅ Realistic |
| 2027: Scale | PQC hybrid production, quantum annealing rebalancing, QML experiments | ⚠️ Aggressive but possible |
| 2028-2030: Advantage | Quantum portfolio opt in production, quantum Monte Carlo | ⚠️ Depends on hardware progress |

#### What's Realistic vs Overly Optimistic

**Realistic:**
- ✅ Quantum-inspired algorithms on classical hardware (available NOW, no quantum hardware needed)
- ✅ QRNG integration (production-ready, commercially available)
- ✅ PQC migration (standards finalized, libraries available)
- ✅ QUBO architecture refactor (enables future quantum plug-and-play)
- ✅ Small portfolio QAOA via cloud (10-20 assets, IBM/D-Wave free tiers)

**Potentially Overly Optimistic:**
- ⚠️ "Quantum advantage for portfolio optimization (50+ assets) by 2028-2030" — The research correctly notes this requires 100-500 logical qubits. Current hardware has ~1,000 noisy physical qubits. With error correction overhead (~1000:1), we need ~100,000-500,000 physical qubits. IBM's roadmap targets 100K by 2033. **2030 is optimistic; 2032-2035 is more realistic.**
- ⚠️ "Quantum Monte Carlo for options pricing by 2030-2035" — This requires fault-tolerant QC with 10,000+ logical qubits. The timeline is plausible but the lower bound (2030) is aggressive.
- ⚠️ The QAOA Sharpe Ratio 1.81 result (SquareOne Capital, 2026) is for a 10-stock direct indexing problem. Extrapolating to 50+ stocks assumes hardware scaling that hasn't been demonstrated.

#### What the Integration Path Gets Right

1. **"Quantum as co-processor" pattern** (Section 4.1) — This is the correct architectural pattern. Quantum handles specific NP-hard sub-problems; classical handles everything else.

2. **QUBO formulation from the start** (Section 6.1) — This is the single most impactful architectural decision. By encoding portfolio optimization as QUBO, Alpha Stack can swap in quantum solvers when available without rewriting the optimization logic.

3. **Cost-benefit honesty** (Section 6.4) — The document correctly notes quantum is 10-1000x more expensive per run than classical, justified only where classical CANNOT find good solutions.

4. **The "ignore quantum for trading" advice** (Research 06, Section 5.1) — For a $7 system, this is correct. Quantum offers zero actionable trading edge in 2026. The focus should be on PQC security and quantum-inspired classical algorithms.

---

## Validation 3: Are Quantum-Inspired Algorithms Correctly Identified?

### Verdict: 🟢 **YES — Accurately distinguished from quantum hardware requirements**

#### Correctly Identified Quantum-Inspired Algorithms

| Algorithm | Document | Assessment |
|-----------|----------|------------|
| **Tensor Network Methods** | Research Unsolved §4.2 | ✅ Correctly identified as classical, available NOW, 10-100x speedup over standard SA |
| **Simulated Quantum Annealing** | Research Unsolved §4.2 | ✅ Correct — classical simulation of quantum tunneling, better local minima escape |
| **Quantum Monte Carlo (classical)** | Research Unsolved §4.2 | ✅ Correct — path-integral MC borrowing quantum statistical mechanics concepts |
| **D-Wave SimulatedAnnealingSampler** | Research Unsolved §6.1 | ✅ Correct — this is a classical sampler that runs on classical hardware, no quantum needed |
| **Microsoft QIO** | Research Unsolved §4.2 | ✅ Correct — Azure quantum-inspired optimization, classical hardware |

#### Algorithms Correctly Identified as Requiring Quantum Hardware

| Algorithm | Document | Assessment |
|-----------|----------|------------|
| **QAOA** | Research Unsolved §2.2 | ✅ Correctly requires quantum hardware (IBM, AWS Braket) |
| **Quantum Amplitude Estimation** | Research Unsolved §2.3 | ✅ Correctly requires fault-tolerant QC |
| **Grover's Algorithm** | Research Unsolved §2.4 | ✅ Correctly requires fault-tolerant QC |
| **VQE** | Research Unsolved §2.6 | ✅ Correctly requires NISQ hardware |

#### Missing Quantum-Inspired Approaches

The documents miss several quantum-inspired algorithms that could benefit Alpha Stack:

1. **Quantum-Inspired Tensor Network for Time Series** — Recent work (2025-2026) applies matrix product states (MPS) to financial time series forecasting. Can capture long-range correlations more efficiently than classical RNNs.

2. **Quantum-Inspired Genetic Algorithms** — Using quantum superposition concepts (probability amplitudes) in evolutionary algorithms for strategy parameter optimization. Better exploration of parameter space than standard GA.

3. **Quantum Walk-Based Graph Algorithms** — For network analysis of asset correlations. Can detect community structure in correlation networks more efficiently than classical spectral methods.

4. **Boltzmann Machine variants** — The research mentions Quantum Boltzmann Machines (§1.4 of Research 06) but doesn't distinguish between quantum hardware QBMs and quantum-inspired classical Restricted Boltzmann Machines (RBMs) which are already production-ready for feature learning.

**Recommendation:** Add a "Quantum-Inspired Algorithms Catalog" to the architecture, documenting which classical algorithms borrow quantum concepts and can be deployed immediately.

---

## Validation 4: Is the Post-Quantum Cryptography Migration Plan Sound?

### Verdict: 🟡 **SOUND IN DESIGN, GAPS IN EXECUTION**

#### What's Sound

1. **Phased approach** (Section 5.5) is correct:
   - Audit → Internal hybrid → External hybrid → Full PQC → Monitor
   - This matches NIST's recommended migration pattern

2. **Hybrid-first strategy** is the right call:
   - Classical + PQC combined during transition
   - If either is broken, the other provides protection
   - This is what Google, Cloudflare, and Apple are deploying

3. **Crypto-agility** as a design principle:
   - Trait-based abstraction allows algorithm swaps without code rewrites
   - Algorithm registry enables runtime switching
   - This is forward-thinking and reduces future migration pain

4. **HNDL data remediation** (fix_security_quantum.md, Fix 3):
   - DEK re-wrapping strategy is correct — don't re-encrypt data, just re-wrap the keys
   - Batch processing strategy is practical
   - Residual risk acceptance for historical TLS sessions is honest

#### Gaps in the Migration Plan

| # | Gap | Impact | Recommendation |
|---|-----|--------|----------------|
| 1 | **No library maturity assessment** | HIGH | ML-KEM/ML-DSA libraries (liboqs, pqcrypto) are maturing but not battle-tested. Need dependency risk assessment. |
| 2 | **No performance benchmarking plan** | HIGH | PQC signatures are 10-100x larger than classical. JWT size impact is mentioned but not benchmarked. Need concrete numbers. |
| 3 | **No rollback testing** | MEDIUM | Fix doc mentions rollback mechanisms but no automated rollback testing. What if hybrid TLS causes compatibility issues with older clients? |
| 4 | **Missing certificate migration** | HIGH | TLS certificates using RSA/ECC need migration to PQC. No plan for certificate authority PQC support timeline. |
| 5 | **No HSM/KMS PQC support assessment** | HIGH | The key hierarchy uses HSM/KMS for master keys. Do AWS KMS, HashiCorp Vault, or Azure Key Vault support ML-KEM/ML-DSA wrapping yet? If not, the DEK re-wrapping plan can't execute. |
| 6 | **No client compatibility plan** | MEDIUM | Hybrid JWTs (~4-5 KB) may break clients with token size limits. Need compatibility testing matrix. |
| 7 | **No PQC for age-encrypted files** | MEDIUM | The `age` crate uses X25519 + ChaCha20-Poly1305. No PQC option exists in `age` yet. Fix doc proposes hybrid wrapper but this requires custom implementation. |

#### Critical Dependency: HSM/KMS PQC Support

The entire DEK re-wrapping plan (Fix 3) assumes KMS can wrap DEKs with ML-KEM-768. As of mid-2026:

- **AWS KMS:** Supports ML-KEM (post-quantum TLS) for some services, but KMS key wrapping with ML-KEM is not yet generally available
- **HashiCorp Vault:** PQC support is experimental (liboqs integration)
- **Azure Key Vault:** Supports post-quantum TLS in preview

**Risk:** If KMS PQC support isn't available by Q2-Q3 2027 (Phase 3.5 target), the DEK re-wrapping plan stalls. **Mitigation:** Implement software-based DEK re-wrapping as fallback (unwrap with classical key, re-wrap with ML-KEM in software, store in KMS with classical wrapping as interim double-wrap).

---

## Validation 5: Is the Quantum Threat Timeline Realistic?

### Verdict: 🟡 **GENERALLY REALISTIC, SOME OPTIMISM ON EARLY MILESTONES**

#### Timeline Assessment

| Milestone | Architecture Estimate | Our Assessment | Notes |
|-----------|----------------------|----------------|-------|
| NIST PQC standards finalized | 2024 (done) | ✅ **CORRECT** | FIPS 203/204/205 published Aug 2024 |
| Early PQC deployment (Google, Cloudflare) | 2025-2026 | ✅ **CORRECT** | Chrome supports ML-KEM since 2024; Cloudflare enabled hybrid TLS |
| Regulatory mandates for PQC | 2027-2030 | ✅ **REALISTIC** | NSA CNSA 2.0 mandates 2033 for national security; financial sector likely 2028-2030 |
| CRQC capable of breaking RSA-2048 | 2035-2045 | ⚠️ **WIDE RANGE** | See analysis below |
| Full PQC migration in financial services | 2030-2035 | ⚠️ **OPTIMISTIC** | Large institutions move slowly; 2035-2040 more realistic for "full" |

#### CRQC Timeline Deep Dive

The "2035-2045" range for a CRQC breaking RSA-2048 is honest but deserves scrutiny:

**Factors pushing toward earlier (2035):**
- Google's 105-qubit Willow demonstrated 13,000x error correction improvement (Oct 2025)
- IBM targets 100,000 qubits by 2033
- Microsoft's topological qubit approach could dramatically reduce physical qubit requirements
- China's aggressive quantum investment ($15B+ announced)
- Potential algorithmic breakthroughs (better error correction codes, more efficient Shor implementations)

**Factors pushing toward later (2045):**
- RSA-2048 requires ~4,000 logical qubits = ~20 million physical qubits (current estimates)
- Current hardware: ~1,000-1,121 noisy qubits — need 4-5 orders of magnitude improvement
- Error rates still too high for sustained computation at scale
- No demonstrated quantum advantage for integer factorization beyond toy numbers
- Engineering challenges (cryogenics, interconnects, control electronics) scale super-linearly

**Our assessment:** The architecture's "2035-2045" range is reasonable. The most likely window is **2038-2045** for RSA-2048 specifically. However:

- **RSA-2048 may be broken earlier** if there's an algorithmic breakthrough in quantum factoring
- **RSA-4096 doubles the qubit requirement** — adds ~5-10 years of safety margin
- **The HNDL threat is real TODAY** — data captured now can be decrypted when CRQC arrives, regardless of when that is

**Recommendation:** The architecture should add a "quantum threat escalation" trigger — if any credible source reports a CRQC milestone (e.g., factoring a 2048-bit number, or a credible hardware roadmap accelerating), the migration timeline should compress automatically.

#### The HNDL Timeline Is Correctly Prioritized

The architecture and fix documents correctly identify HNDL as the **immediate** quantum threat, not CRQC. This is the most important insight:

- Adversaries are **already** capturing encrypted traffic
- Financial data has long sensitivity lifetimes (7+ years regulatory retention)
- Data captured in 2026 is vulnerable to decryption in 2035-2045
- **The time to act is NOW, not when CRQC arrives**

This prioritization is correct and should be maintained.

---

## Validation 6: What Quantum Integration Gaps Exist?

### Critical Gaps (Blocking Production)

| # | Gap | Description | Impact |
|---|-----|-------------|--------|
| 1 | **JWT hybrid signing not implemented** | Fix designed but code not written; production will launch with RS256 | All JWTs issued before migration are retroactively forgeable |
| 2 | **No PQC for broker connections** | MT5 bridge, CCXT, REST API brokers all use classical TLS only | HNDL exposure on all trading traffic |
| 3 | **KMS PQC support unverified** | DEK re-wrapping plan assumes ML-KEM support in KMS | Phase 3.5 may stall if KMS doesn't support PQC |

### High-Priority Gaps

| # | Gap | Description | Recommendation |
|---|-----|-------------|----------------|
| 4 | **No quantum-safe key exchange for API authentication** | API request signing uses HMAC-SHA256 (quantum-safe) but the initial API key/secret exchange uses classical TLS | Enable hybrid TLS for API key distribution endpoints |
| 5 | **Certificate migration plan missing** | TLS certificates (RSA/ECC) need migration; no CA PQC timeline tracked | Monitor Let's Encrypt, DigiCert PQC certificate availability |
| 6 | **No PQC performance budget** | PQC operations are slower; no latency budget established for hybrid operations | Benchmark ML-KEM key exchange, ML-DSA signing, set SLOs |
| 7 | **QRNG reliability/fallback not designed** | Section 5.6 describes QRNG options but no fallback if QRNG service is unavailable | Design CSPRNG fallback with QRNG health monitoring |
| 8 | **No quantum threat intelligence feed** | No mechanism to track quantum hardware progress and adjust migration timeline | Subscribe to NIST PQC updates, IBM/Google quantum roadmaps, academic preprints |
| 9 | **Missing PQC for encrypted file fallback** | `age` crate uses X25519 — no PQC option; hybrid wrapper requires custom implementation | Implement ML-KEM wrapper for age-encrypted files or switch to PQC-native file encryption |
| 10 | **Audit log integrity not quantum-hardened** | Hash chain uses SHA-256 (quantum-safe) but the signing of audit logs (mentioned in schema) uses unspecified algorithm | Ensure audit log signing uses ML-DSA or hybrid signatures |

### Medium-Priority Gaps

| # | Gap | Description | Recommendation |
|---|-----|-------------|----------------|
| 11 | **No quantum risk scoring for portfolio** | Research identifies quantum risk to crypto holdings but no automated scoring | Implement per-address-type quantum risk scoring for Bitcoin positions |
| 12 | **Missing PQC for WebSocket connections** | WebSocket server uses TLS but no mention of hybrid TLS for WS | Enable hybrid TLS for WebSocket when client support exists |
| 13 | **No quantum readiness testing** | No test suite validates PQC operations work correctly | Add PQC integration tests: hybrid TLS handshake, hybrid JWT sign/verify, ML-KEM key exchange |
| 14 | **QRNG entropy quality validation missing** | QRNG output needs quality testing (bias, correlation, min-entropy) | Implement QRNG health checks: statistical tests on output stream |
| 15 | **No PQC for OAuth2 flows** | OAuth2 callbacks use classical TLS | Enable hybrid TLS for OAuth2 redirect endpoints |
| 16 | **Missing quantum impact on rate limiting** | PQC operations are slower; rate limits may need adjustment for hybrid-authenticated requests | Benchmark and adjust rate limits for PQC overhead |
| 17 | **No quantum-safe backup encryption** | Backup encryption uses AES-256-GCM (quantum-safe) but key exchange for backup keys is unspecified | Ensure backup key distribution uses ML-KEM |
| 18 | **No PQC for mobile app** | Mobile biometric auth and keychain storage use classical crypto | Plan PQC migration for iOS Keychain / Android Keystore integration |
| 19 | **Missing quantum threat to TOTP** | TOTP uses HMAC-SHA1 (quantum-resistant for collision resistance) but the shared secret exchange uses classical crypto | TOTP itself is quantum-safe; ensure secret distribution uses PQC |
| 20 | **No quantum impact assessment for third-party integrations** | OAuth2 brokers (OANDA, Interactive Brokers) use their own TLS — Alpha Stack can't control PQC status | Document third-party PQC readiness as accepted risk |
| 21 | **No PQC for code signing** | CI/CD pipeline signs binaries; no mention of PQC for code signing certificates | Plan ML-DSA code signing when certificate support available |
| 22 | **Missing quantum-safe randomness for nonce generation** | Nonces use OS CSPRNG (quantum-safe) but QRNG integration could improve quality | Optional QRNG for high-value nonces (key generation, DEK creation) |

---

## Cross-Document Consistency Analysis

### Consistency Issues Between Documents

| Issue | Documents | Resolution |
|-------|-----------|------------|
| **JWT algorithm contradiction** | architecture_security.md §2.2 (RS256) vs §5.3 (hybrid) | Fix doc resolves — Phase A → Phase B migration |
| **Bitcoin address advice** | architecture_security.md §5.7 ("hide pubkey until spend") vs fix_security_quantum.md Fix 2 (P2TR always exposes pubkey) | Fix doc corrects the error |
| **Timeline consistency** | research_quantum_unsolved.md §3.4 (quantum advantage 2028-2030) vs research_06 §1.5 (2030-2035) | Research 06 is more conservative and likely more accurate |
| **Cost estimates** | research_quantum_unsolved.md §6.4 (AWS Braket $100-500/mo) vs research_06 §1.2 (D-Wave free tier) | Both correct for different use cases; not contradictory |
| **PQC library maturity** | All documents assume liboqs/ML-DSA are production-ready | **Not verified** — need actual dependency audit |

### The "Quantum-Ready From Day One" Gap

The security architecture's stated philosophy is "quantum-ready from day one" (Section 1.1). However:

- Production will launch with RS256 JWTs (not quantum-ready)
- Broker connections use classical TLS (not quantum-ready)
- QRNG is described but not integrated (not quantum-ready)
- PQC migration is Phase 4 (Weeks 12-16) — not day one

**Assessment:** The philosophy is aspirational, not literal. This is fine, but the documentation should be updated to say "quantum-ready architecture with phased PQC deployment" rather than implying day-one quantum readiness.

---

## Recommendations Summary

### Immediate (Pre-Production)

1. **Implement Ed25519 JWT signing** (Phase A of Fix 1) — eliminates RSA dependency
2. **Audit KMS PQC support** — verify AWS KMS / HashiCorp Vault ML-KEM capabilities
3. **Benchmark PQC operations** — measure ML-KEM key exchange and ML-DSA signing latency
4. **Add PQC integration tests** — hybrid TLS handshake, hybrid JWT sign/verify
5. **Document broker connection PQC gap** — accepted risk with timeline for remediation

### Short-Term (Q3-Q4 2026)

6. **Deploy quantum-inspired solvers** — replace standard simulated annealing with D-Wave's classical sampler
7. **Integrate QRNG** with CSPRNG fallback — for key generation and high-value nonces
8. **Implement QUBO architecture** — refactor portfolio optimizer for quantum plug-and-play
9. **Set up quantum threat intelligence** — monitor NIST, IBM, Google quantum progress
10. **Design quantum risk dashboard** — track P2TR exposure, address age, pubkey exposure status

### Medium-Term (2027)

11. **Execute Phase 3.5 HNDL remediation** — DEK re-wrapping, credential file re-encryption
12. **Deploy hybrid TLS** for client-facing APIs
13. **Implement hybrid JWT signing** (Phase B of Fix 1)
14. **Begin certificate migration planning** — track CA PQC certificate availability
15. **Pilot quantum annealing** for portfolio rebalancing via D-Wave/IBM cloud

### Long-Term (2028+)

16. **Full PQC migration** when industry support is mature
17. **Quantum portfolio optimization** in production (if hardware scales)
18. **Quantum Monte Carlo** for complex derivatives (when fault-tolerant QC available)
19. **Continuous monitoring** and timeline adjustment based on hardware progress

---

## Conclusion

The Alpha Stack quantum integration demonstrates **strong architectural thinking** and **genuine understanding of the quantum threat landscape**. The hybrid cryptography strategy, crypto-agility framework, and HNDL awareness are all well-designed. The research documents accurately distinguish between quantum hype and actionable reality.

The primary risks are **implementation gaps** — the architecture describes what should be built, but critical pieces (hybrid JWT, broker PQC, KMS verification) remain unbuilt. The fix document addresses the most critical gaps but adds scope that must be tracked.

**The most important takeaway:** The HNDL threat makes quantum security a **today problem**, not a future problem. Every day of production with classical-only cryptography adds to the retroactive decryption exposure window. Prioritize the PQC migration plan accordingly.

**Overall risk rating:** 🟡 **MEDIUM-HIGH** — Well-designed but not yet implemented. Acceptable for initial production with documented accepted risks, but PQC migration must proceed on schedule.

---

*This review should be updated after each migration phase completes and when significant quantum hardware milestones are reached.*
