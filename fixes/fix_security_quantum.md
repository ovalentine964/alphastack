# Quantum-Resistant Security Fix Plan — Critical Gaps

> **Prepared by:** Quantum Security Fix Agent  
> **Date:** 2026-07-11  
> **Source:** `review_security_quantum.md` — Critical Gap Remediation  
> **Scope:** 3 critical gaps requiring immediate resolution before production  
> **Status:** 🔴 ACTIVE — Blocking production deployment

---

## Fix Summary

| # | Gap | Severity | Fix Status | Target Completion |
|---|-----|----------|------------|-------------------|
| 1 | JWT RS256/RSA contradiction | 🔴 CRITICAL | Fix designed — awaiting implementation | Before production |
| 2 | Bitcoin Taproot P2TR exposure | 🔴 CRITICAL | Strategy defined — awaiting implementation | Before production |
| 3 | HNDL data remediation missing | 🔴 CRITICAL | Phase 3.5 designed — awaiting integration | Q2-Q3 2027 |

---

## Fix 1: JWT RS256/RSA → Hybrid PQC Signatures

### Problem

Sections 2.2 and 3.5 of `architecture_security.md` specify:
- **Algorithm:** RS256 (RSA + SHA-256)
- **Key:** RSA-4096 keypair
- **Rotation:** 90-day rotation cycle

This directly contradicts the quantum-resistant design in Section 5.3 which specifies hybrid Ed25519 + ML-DSA-65. RSA-4096 is breakable by Shor's algorithm. All JWT tokens signed with RS256 are forgeable once a CRQC exists. Captured tokens (HNDL exposure) can be forged retroactively.

### Root Cause

The JWT implementation (Section 2.2) was written before the quantum-resistant design (Section 5.3) was finalized. The production config was never updated to reflect the hybrid approach.

### Fix: Hybrid JWT Signing Migration

#### Phase A — Immediate (Pre-Production): Ed25519 Classical

Replace RS256 with Ed25519 as an interim step. Ed25519 is not quantum-resistant, but it eliminates RSA dependency and is a prerequisite for the hybrid scheme.

```yaml
# BEFORE (vulnerable)
jwt:
  algorithm: RS256
  key_type: RSA-4096
  rotation_days: 90

# AFTER — Phase A (interim, pre-production)
jwt:
  algorithm: EdDSA
  key_type: Ed25519
  rotation_days: 90
  note: "Phase A — classical interim, hybrid follows in Phase 4"
```

**Code changes required:**
- Replace `jsonwebtoken::Algorithm::RS256` with `jsonwebtoken::Algorithm::EdDSA`
- Generate Ed25519 keypair via `ed25519_dalek`
- Update JWT header `alg` field
- Update all token verification call sites

#### Phase B — Phase 4 (2028): Hybrid Ed25519 + ML-DSA-65

Deploy the full hybrid signing scheme as designed in Section 5.3:

```
Hybrid JWT Signature Construction:
┌─────────────────────────────────────────────────┐
│  header.payload (UTF-8 bytes)                   │
│         │                                        │
│    ┌────┴────┐                                   │
│    ▼         ▼                                   │
│ Ed25519   ML-DSA-65                              │
│  .sign()   .sign()                               │
│    │         │                                   │
│    └────┬────┘                                   │
│         ▼                                        │
│  sig_classical || sig_pq                         │
│  (64 bytes)    (3,309 bytes)                     │
│         │                                        │
│         ▼                                        │
│  Hybrid Signature Block ≈ 3,373 bytes            │
└─────────────────────────────────────────────────┘
```

**Critical implementation requirements:**

1. **Constant-time verification:** Both signatures MUST be verified regardless of individual outcomes. No short-circuit on first failure.

```rust
// CORRECT: constant-time hybrid verification
fn verify_hybrid_jwt(token: &str, classical_key: &Ed25519PublicKey, pq_key: &MlDsa65PublicKey) -> Result<Claims> {
    let (header_payload, sig_block) = split_token(token)?;
    let (sig_classical, sig_pq) = split_signature_block(sig_block)?;

    // ALWAYS verify both — no short-circuit
    let classical_ok = ed25519::verify(classical_key, header_payload, sig_classical)?;
    let pq_ok = ml_dsa_65::verify(pq_key, header_payload, sig_pq)?;

    // Both must pass
    if classical_ok && pq_ok {
        Ok(decode_claims(header_payload)?)
    } else {
        Err(ValidationError::InvalidSignature)
    }
}
```

2. **JWT size management:** Total token size will be ~4-5 KB. Mitigations:

| Token Type | Strategy | Size Target |
|------------|----------|-------------|
| Access token (15 min) | Hybrid JWT (full) | ~4-5 KB |
| Refresh token (7 days) | Opaque server-side token | ~64 bytes |
| API session token | Opaque server-side token | ~64 bytes |
| Service-to-service | Hybrid JWT (full) | ~4-5 KB |

3. **Key management:**

```yaml
# Phase B production config
jwt:
  hybrid:
    classical:
      algorithm: EdDSA
      key_type: Ed25519
      rotation_days: 90
    post_quantum:
      algorithm: ML-DSA-65
      key_type: ML-DSA-65
      rotation_days: 90
      nist_level: 3
    verification: constant-time-both
    token_strategy:
      access_token: hybrid-jwt
      refresh_token: opaque-server-side
      api_session: opaque-server-side
```

#### Migration Checklist

- [ ] **Phase A:** Replace RS256 → Ed25519 in `jwt` config section
- [ ] **Phase A:** Generate new Ed25519 keypair, deprecate RSA-4096 key
- [ ] **Phase A:** Update all JWT verification call sites
- [ ] **Phase A:** Remove RSA-4096 key material from KMS after rotation completes
- [ ] **Phase A:** Add JWT size monitoring (alert if tokens exceed 8 KB proxy limits)
- [ ] **Phase B:** Integrate `liboqs` ML-DSA-65 for hybrid signing
- [ ] **Phase B:** Implement constant-time dual verification
- [ ] **Phase B:** Migrate refresh/session tokens to opaque server-side
- [ ] **Phase B:** Update JWT validation to accept hybrid signature blocks
- [ ] **Phase B:** Load test with 4-5 KB JWTs under production traffic

#### HNDL Exposure Window

| Period | Algorithm | HNDL Risk | Action |
|--------|-----------|-----------|--------|
| Now → Phase A | RS256 (RSA-4096) | 🔴 HIGH | Captured tokens forgeable by CRQC |
| Phase A → Phase B | Ed25519 | 🟡 MEDIUM | Captured tokens forgeable by CRQC, but shorter exposure |
| Phase B onward | Hybrid Ed25519 + ML-DSA-65 | 🟢 LOW | Both schemes must be broken to forge |

**Residual risk:** Tokens issued before Phase B remain vulnerable. Short access token lifetimes (15 min) limit the exposure window, but any tokens captured before migration are retroactively forgeable. This is unavoidable — document and accept.

---

## Fix 2: Bitcoin Taproot P2TR Public Key Exposure

### Problem

The architecture (Section 5.7) states: *"Use new addresses (hide pubkey until spend)"* — this is correct for P2PKH/P2SH but **incorrect for P2TR (Taproot)**.

**Taproot address structure:**
```
P2TR Address = Bech32m(version || x-only-pubkey)
                              ^^^^^^^^^^^^^^^^
                              Public key is EMBEDDED in address
                              Always visible on-chain
```

This means:
- P2TR public keys are exposed from the moment the address is created
- No "hide pubkey until spend" protection exists for Taproot
- A CRQC attacker can derive private keys from any P2TR address on-chain
- This is worse than P2PKH/P2SH where the pubkey is only revealed on spend

### Threat Model: Quantum Attack on P2TR

```
Current State (2026):
┌─────────────────────────────────────────────────────┐
│  P2TR Address on blockchain                         │
│  bc1p... (Bech32m encoded x-only public key)        │
│         │                                           │
│         ▼                                           │
│  Public key visible to ALL observers                │
│         │                                           │
│    [CRQC exists] ──► Shor's algorithm               │
│         │                                           │
│         ▼                                           │
│  Derive private key ──► Steal funds                 │
└─────────────────────────────────────────────────────┘

vs. P2PKH/P2SH (quantum-safer):
┌─────────────────────────────────────────────────────┐
│  P2PKH Address on blockchain                        │
│  1A1zP... (HASH of public key, not key itself)      │
│         │                                           │
│         ▼                                           │
│  Public key HIDDEN until first spend                │
│         │                                           │
│  [CRQC exists] ──► Cannot attack (no pubkey)        │
│         │                                           │
│  Only vulnerable during spend broadcast window      │
└─────────────────────────────────────────────────────┘
```

### Fix: Multi-Layer Address Protection Strategy

#### Layer 1: Address Type Selection Matrix

| Address Type | Quantum Exposure | Recommendation | Use Case |
|-------------|-----------------|----------------|----------|
| **P2PKH** (Legacy `1...`) | 🟢 Pubkey hidden until spend | ✅ Use for cold storage | Long-term holdings |
| **P2SH** (Script `3...`) | 🟢 Pubkey hidden until spend | ✅ Use for cold storage | Long-term holdings (multisig) |
| **P2WPKH** (SegWit `bc1q...`) | 🟢 Pubkey hash only | ✅ Use for active wallets | Day-to-day operations |
| **P2TR** (Taproot `bc1p...`) | 🔴 **Pubkey always exposed** | ❌ Avoid for quantum-sensitive funds | Only for amounts you can afford to lose |

**Decision rule:** Any Bitcoin wallet holding funds that must survive a CRQC event MUST use P2PKH, P2SH, or P2WPKH — **never P2TR**.

#### Layer 2: Address Rotation Strategy

Implement automated address rotation to minimize exposure window:

```
Address Rotation Lifecycle:
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  T=0: Generate fresh address (P2PKH/P2WPKH)                 │
│    │                                                         │
│    ▼                                                         │
│  T=0→90d: Address ACTIVE (receive funds, limited sends)      │
│    │                                                         │
│    ▼                                                         │
│  T=90d: Address marked ROTATION-DUE                          │
│    │                                                         │
│    ▼                                                         │
│  T=90→120d: GRACE PERIOD — new address generated             │
│    │           old address still receives (via notification)  │
│    ▼                                                         │
│  T=120d: SWEEP — all funds moved to new address              │
│    │                                                         │
│    ▼                                                         │
│  T=120d+: Address DEPRECATED — no new receives               │
│            Monitor for late/erroneous deposits               │
│            Public key now permanently exposed (if spent)      │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Rotation parameters:**

```yaml
bitcoin_address_policy:
  # Address type selection
  cold_storage:
    type: P2PKH
    rationale: "Pubkey hidden until spend — maximum quantum protection"
    rotation_days: 365  # Annual rotation for cold storage

  hot_wallet:
    type: P2WPKH
    rationale: "SegWit efficiency, pubkey hash only — good quantum protection"
    rotation_days: 90   # Quarterly rotation for hot wallets

  taproot:
    type: P2TR
    status: PROHIBITED
    rationale: "Public key embedded in address — unacceptable quantum exposure"
    exception: "Only for dust amounts or testing"

  # Rotation mechanics
  rotation:
    grace_period_days: 30
    sweep_deadline_days: 120
    min_sweep_amount_satoshis: 546  # Dust limit
    late_deposit_monitoring_days: 365
```

#### Layer 3: Spend-Time Quantum Protection

When spending from any address (including P2PKH/P2WPKH), the public key is broadcast. A CRQC attacker could derive the private key and front-run the transaction:

```
Attack Scenario (Spend Race Condition):
┌──────────────────────────────────────────────────────────────┐
│  Block N:   User broadcasts spend tx (reveals pubkey)        │
│  Mempool:   Attacker sees pubkey                             │
│  T+0:       Attacker runs Shor's on pubkey                   │
│  T+???:     Attacker derives private key (time unknown)      │
│  T+???:     Attacker broadcasts competing tx (higher fee)    │
│  Block N+1: Attacker's tx confirmed (front-run)              │
│             User's funds stolen                               │
└──────────────────────────────────────────────────────────────┘
```

**Mitigations:**

1. **Immediate sweep on spend:** When spending, sweep the ENTIRE address balance to a fresh address in the same transaction. Don't leave residual funds on an address whose pubkey has been revealed.

2. **RBF (Replace-By-Fee) monitoring:** If a competing transaction appears on a spent address, immediately broadcast a replacement with higher fees to reclaim funds.

3. **Minimize on-chain transactions:** Use Lightning Network where possible to avoid revealing pubkeys on L1.

```yaml
bitcoin_spend_policy:
  # Always sweep — never leave funds on a revealed-pubkey address
  sweep_on_spend: true
  sweep_output_type: P2PKH  # Sweep to fresh P2PKH address

  # RBF monitoring
  rbf_monitoring: true
  rbf_escalation_fee_rate: "2x current median"
  rbf_alert_threshold_seconds: 600  # Alert if no confirmation in 10 min

  # Prefer Lightning for frequent transactions
  prefer_lightning: true
  lightning_reasoning: "Off-chain — no pubkey exposure on L1"
```

#### Layer 4: Portfolio-Level Quantum Risk Monitoring

```yaml
quantum_risk_monitoring:
  # Track exposure by address type
  metrics:
    - name: btc_p2tr_balance_satoshis
      alert_threshold: 0  # Any P2TR balance is an alert
      severity: CRITICAL

    - name: btc_revealed_pubkey_balance_satoshis
      description: "Balance on addresses where pubkey has been revealed via spend"
      alert_threshold: 10000000  # 0.1 BTC
      severity: HIGH

    - name: btc_address_age_max_days
      description: "Oldest active address age"
      alert_threshold: 120
      severity: MEDIUM

  # Dashboard
  dashboard:
    - total_balance_by_address_type (P2PKH / P2WPKH / P2TR / other)
    - addresses_pending_rotation
    - pubkey_exposure_status (hidden / revealed-on-spend / always-visible)
    - estimated_quantum_risk_score
```

#### Migration Checklist

- [ ] Audit all existing Bitcoin addresses — classify by type (P2PKH/P2WPKH/P2TR)
- [ ] **IMMEDIATE:** Sweep any P2TR holdings to P2PKH/P2WPKH addresses
- [ ] Document current pubkey exposure state for each address
- [ ] Implement address rotation automation (90-day cycle for hot, 365-day for cold)
- [ ] Implement sweep-on-spend for all address types
- [ ] Set up RBF monitoring for spend transactions
- [ ] Deploy quantum risk dashboard
- [ ] Document Lightning Network usage policy for high-frequency transactions
- [ ] Create incident response plan for CRQC surprise scenario

---

## Fix 3: Phase 3.5 — HNDL Data Remediation

### Problem

The architecture's phased migration roadmap (Phases 1-5, Q3 2026 → 2028+) correctly prioritizes PQC migration but has a critical gap: **no plan for already-encrypted historical data**. Data encrypted with RSA-2048/ECC key wrapping before migration remains vulnerable to HNDL attacks. A CRQC attacker who captured this data in transit (or breaches storage) can decrypt it retroactively.

### Exposure Inventory

| Data Category | Current Encryption | Key Exchange | HNDL Exposure | Volume Estimate | Remediation |
|--------------|-------------------|--------------|---------------|-----------------|-------------|
| **Historical TLS sessions** | TLS 1.3 (ECDHE + AES-256-GCM) | ECDHE (X25519) | 🔴 HIGH | Unknown — all past TLS sessions | Irrecoverable (data in transit, already captured) |
| **JWT tokens (issued before Phase A)** | RS256 signature | RSA-4096 | 🔴 HIGH | All tokens issued before migration | Re-issue (invalidate all legacy tokens) |
| **KMS-wrapped DEKs** | AES-256-GCM DEKs, wrapped by RSA-2048/ECC KMS | RSA-2048 / ECDH | 🔴 HIGH | All stored credentials | **Bulk re-wrap DEKs** |
| **Backup encryption** | AES-256-GCM, key exchange via RSA/ECC | RSA/ECC | 🟡 MEDIUM | All backup archives | **Re-encrypt backups** |
| **Database field encryption** | AES-256-GCM per-field, DEK wrapped by RSA | RSA-2048 | 🟡 MEDIUM | Sensitive PII fields | **Re-wrap DEKs** |
| **Age-encrypted credential files** | X25519 + ChaCha20-Poly1305 | X25519 | 🟡 MEDIUM | Credential files | **Re-encrypt with PQC wrapper** |
| **Audit logs at rest** | AES-256-GCM (disk encryption) | OS/hardware | 🟢 LOW | All audit logs | No action (symmetric is quantum-safe) |
| **Argon2id-hashed passwords** | Argon2id | N/A (hash) | 🟢 LOW | All user passwords | No action (memory-hard is quantum-safe) |

### Phase 3.5: HNDL Data Remediation Plan

**Timeline:** Q2-Q3 2027 (between Phase 3 hybrid deployment and Phase 4 full migration)

**Objective:** Eliminate all classical-only key exchange/wrapping for stored data, reducing HNDL exposure to near-zero for data at rest.

#### Step 1: Complete Exposure Inventory (Week 1-2)

```
Discovery Script Requirements:
┌──────────────────────────────────────────────────────────────┐
│ 1. Scan all encrypted data stores                            │
│    - Database columns with encryption markers                │
│    - KMS key metadata (algorithm, creation date)             │
│    - Backup archives (encryption method)                     │
│    - Credential files (age, gpg, custom encryption)          │
│    - Object storage (S3/GCS encryption headers)              │
│                                                              │
│ 2. For each, record:                                         │
│    - Encryption algorithm                                    │
│    - Key exchange / wrapping algorithm                       │
│    - Key ID / DEK ID                                         │
│    - Creation date                                           │
│    - Sensitivity classification                              │
│    - Retention period                                        │
│    - Re-encryption feasibility                               │
│                                                              │
│ 3. Output: HNDL Exposure Registry (see template below)       │
└──────────────────────────────────────────────────────────────┘
```

**HNDL Exposure Registry template:**

```json
{
  "hndl_exposure_registry": {
    "generated": "2027-04-01T00:00:00Z",
    "entries": [
      {
        "id": "entry-001",
        "data_store": "postgres://main/users.pii_fields",
        "encryption": "AES-256-GCM",
        "key_wrapping": "RSA-2048",
        "key_id": "kms-key-abc123",
        "created": "2025-06-15T00:00:00Z",
        "sensitivity": "HIGH",
        "retention_years": 7,
        "hndl_exposure": "HIGH",
        "remediation": "re-wrap-dek",
        "remediation_status": "pending",
        "estimated_records": 150000
      }
    ]
  }
}
```

#### Step 2: DEK Re-Wrapping (Week 3-6)

For data encrypted with AES-256-GCM DEKs that are wrapped by RSA/ECC, the remediation is to **re-wrap the DEKs** with PQC-resistant key wrapping — the underlying data does not need to be re-encrypted.

```
DEK Re-Wrapping Process:
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  Old: DEK ──[RSA-2048 wrap]──► Wrapped DEK (stored)         │
│                                                              │
│  Re-wrap:                                                    │
│  1. Unwrap DEK using old RSA-2048 private key                │
│  2. Re-wrap DEK using new ML-KEM-768 + X25519 hybrid         │
│  3. Store new wrapped DEK                                    │
│  4. Securely destroy old wrapped DEK                         │
│  5. Verify: decrypt sample data with re-wrapped DEK          │
│                                                              │
│  New: DEK ──[ML-KEM-768 + X25519 hybrid wrap]──► Wrapped DEK│
│                                                              │
│  ⚠️ CRITICAL: Do NOT decrypt/re-encrypt the actual data.     │
│     Only re-wrap the DEK. This is orders of magnitude        │
│     faster and avoids a window where data is unprotected.    │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Batch processing strategy:**

```yaml
dek_rewrap_batch:
  batch_size: 1000
  parallelism: 4
  dry_run_first: true  # Verify before committing
  rollback_on_error: true
  progress_tracking: true
  
  verification:
    sample_rate: 0.01  # Verify 1% of re-wrapped DEKs
    method: "decrypt-sample-data-and-compare-hash"
    
  schedule:
    # Run during low-traffic hours
    window: "02:00-06:00 UTC"
    max_duration_hours: 4
    pause_on_alert: true
```

#### Step 3: Credential File Re-Encryption (Week 5-7)

For `age`-encrypted credential files:

```
Option A — Hybrid Wrapper (recommended):
┌──────────────────────────────────────────────────────────────┐
│  1. Decrypt file with existing age (X25519) key              │
│  2. Re-encrypt with:                                         │
│     a. ML-KEM-768 key encapsulation (PQC layer)              │
│     b. Then age encryption (classical layer)                 │
│     Result: file.age.pqc                                     │
│  3. Securely shred original file                             │
│  4. Store new ML-KEM private key in HSM                      │
└──────────────────────────────────────────────────────────────┘

Option B — Direct PQC encryption (if liboqs available):
┌──────────────────────────────────────────────────────────────┐
│  1. Decrypt file with existing age key                       │
│  2. Encrypt directly with ML-KEM-768 + AES-256-GCM          │
│  3. Securely shred original file                             │
│  4. Store ML-KEM private key in HSM                          │
└──────────────────────────────────────────────────────────────┘
```

#### Step 4: Backup Re-Encryption (Week 6-8)

```
Backup Re-Encryption Process:
┌──────────────────────────────────────────────────────────────┐
│  1. Inventory all backup archives                            │
│  2. For each backup:                                         │
│     a. Decrypt with current key                              │
│     b. Re-encrypt with PQC-resistant key wrapping            │
│     c. Generate new integrity hash                           │
│     d. Store re-encrypted backup                             │
│     e. Securely shred old backup                             │
│  3. Verify: spot-check restore from re-encrypted backups     │
│                                                              │
│  ⚠️ Schedule during maintenance windows — this is I/O heavy  │
└──────────────────────────────────────────────────────────────┘
```

#### Step 5: TLS Session Irrecovery — Residual Risk Acceptance (Week 1)

```
┌──────────────────────────────────────────────────────────────┐
│  ⚠️ IMPORTANT: Historical TLS sessions CANNOT be remediated. │
│                                                              │
│  All TLS sessions captured before hybrid TLS deployment      │
│  (Phase 2-3) used ECDHE key exchange. If captured by an      │
│  adversary, these sessions are permanently vulnerable to     │
│  HNDL decryption once a CRQC exists.                        │
│                                                              │
│  This is IRRECOVERABLE. The fix is:                          │
│  1. Deploy hybrid TLS as fast as possible (Phase 2-3)        │
│  2. Document the residual risk                               │
│  3. Accept that pre-migration traffic has HNDL exposure      │
│  4. Focus remediation effort on data at rest (fixable)       │
│                                                              │
│  Residual risk acceptance must be signed by CISO.            │
└──────────────────────────────────────────────────────────────┘
```

#### Step 6: Verification & Documentation (Week 9-10)

```yaml
verification_checklist:
  - [ ] All DEKs re-wrapped with PQC-resistant wrapping
  - [ ] Spot-check: 5% of re-wrapped DEKs successfully decrypt data
  - [ ] All credential files re-encrypted
  - [ ] All backups re-encrypted
  - [ ] No legacy encryption paths remain (scan confirms zero)
  - [ ] Old key material securely destroyed (HSM audit log)
  - [ ] HNDL Exposure Registry updated — all entries show "remediated"
  - [ ] Residual risk documented (historical TLS sessions)
  - [ ] CISO sign-off on residual risk acceptance
  - [ ] Updated quantum threat model reflecting post-remediation state
```

#### Phase 3.5 Timeline

```
Q2-Q3 2027:
┌──────────────────────────────────────────────────────────────┐
│ Week 1-2:   Exposure inventory & registry creation           │
│ Week 3-6:   DEK re-wrapping (batch processing)              │
│ Week 5-7:   Credential file re-encryption                    │
│ Week 6-8:   Backup re-encryption                             │
│ Week 1:     Residual risk documentation (parallel)           │
│ Week 9-10:  Verification & CISO sign-off                     │
│ Week 11:    Legacy key material destruction                  │
│ Week 12:    Phase 3.5 complete — report to stakeholders      │
└──────────────────────────────────────────────────────────────┘
```

#### Updated Migration Roadmap

```
Phase 1 (Q3 2026):        Internal PQC foundations
Phase 2 (Q4 2026):        Hybrid key exchange deployment
Phase 3 (Q1 2027):        Hybrid signature deployment
Phase 3.5 (Q2-Q3 2027):   HNDL DATA REMEDIATION ◄── NEW
Phase 4 (Q4 2027):        Full hybrid JWT + external APIs
Phase 5 (2028+):          Monitor, adapt, full PQC migration
```

---

## Cross-Cutting Concerns

### Key Material Destruction

When replacing classical keys with PQC-resistant keys:

1. **HSM-managed keys:** Mark as deactivated in HSM, retain for audit, schedule destruction after verification period (30 days)
2. **Software keys:** Use secure deletion (multi-pass overwrite or crypto-shred)
3. **Backup keys:** Destroy after re-encryption is verified
4. **Audit trail:** Log all key destruction events with timestamp, key ID, reason, and approver

### Rollback Plan

Each fix includes rollback capability:

| Fix | Rollback Mechanism | Rollback Window |
|-----|-------------------|-----------------|
| JWT Phase A (Ed25519) | Revert to RS256 (keep RSA key material available) | 7 days post-deploy |
| JWT Phase B (Hybrid) | Fall back to Ed25519-only (keep hybrid key material) | 14 days post-deploy |
| Bitcoin address rotation | Old addresses remain valid (funds not lost) | 365 days |
| DEK re-wrapping | Keep old wrapped DEKs until verification passes | Until verified |

### Testing Requirements

| Fix | Test Type | Criteria |
|-----|-----------|----------|
| JWT Phase A | Integration | All auth flows pass with Ed25519 |
| JWT Phase A | Performance | Token size < 1 KB, latency < 5ms |
| JWT Phase B | Integration | All auth flows pass with hybrid |
| JWT Phase B | Performance | Token size < 5 KB, latency < 15ms |
| JWT Phase B | Security | Constant-time verification confirmed |
| Bitcoin rotation | Functional | Funds sweep correctly to new addresses |
| Bitcoin rotation | Monitoring | Alerts fire for P2TR detection |
| DEK re-wrap | Data integrity | 100% of re-wrapped DEKs decrypt correctly |
| DEK re-wrap | Performance | Batch completes within maintenance window |

---

## Approval & Sign-Off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Security Architect | | | |
| CISO | | | |
| Lead Developer | | | |
| DevOps Lead | | | |

---

*This fix plan should be reviewed and updated as each fix is implemented. Track progress in the project management system with the tag `quantum-fix`.*
