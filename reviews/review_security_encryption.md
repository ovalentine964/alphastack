# Alpha Stack — Security Review: Encryption Architecture

> **Review Type:** Encryption Architecture Security Review
> **Reviewer:** Security Review Agent (Encryption)
> **Date:** 2026-07-11
> **Documents Reviewed:** `architecture_security.md`, `architecture_data_storage.md`
> **Status:** PRE-IMPLEMENTATION — Design Review
> **Risk Rating:** MODERATE — Strong design with actionable findings

---

## Executive Summary

Alpha Stack's encryption architecture is **well-designed for its threat model** — a desktop-first trading platform handling broker credentials and financial data. The design demonstrates strong fundamentals: AES-256-GCM for symmetric encryption, Argon2id for password hashing, OS keyring integration for credential storage, and a clear crypto-agility path toward post-quantum cryptography.

**Overall Assessment: 7.5/10** — Solid foundation with specific gaps to address before implementation.

| Area | Rating | Notes |
|------|--------|-------|
| Credential encryption (AES-256-GCM) | ✅ Strong | Correct algorithm, nonce, and key hierarchy |
| Rust keyring implementation | ⚠️ Good | Correct usage, but has gaps in the file fallback |
| Broker credential isolation | ✅ Strong | 5-layer isolation is exemplary |
| Data at rest encryption | ⚠️ Partial | Application-level good; disk/DB encryption deferred to Phase 2+ |
| Data in transit encryption | ✅ Strong | TLS 1.3, mTLS for bridge, hybrid TLS planned |
| Key management | ⚠️ Moderate | Key hierarchy defined but key derivation in fallback has issues |
| Quantum readiness | ✅ Forward-looking | Hybrid strategy is correct approach |

---

## Validation Results

### 1. Is Credential Encryption Correct (AES-256-GCM)? ✅ YES — with notes

**Findings:**

| Item | Status | Detail |
|------|--------|--------|
| Algorithm selection | ✅ Correct | AES-256-GCM is the industry standard for authenticated encryption |
| Nonce generation | ✅ Correct | `os.urandom(12)` — 96-bit nonce via CSPRNG, appropriate for GCM |
| Nonce uniqueness risk | ⚠️ LOW RISK | `os.urandom(12)` collision probability is negligible for per-field encryption, but no explicit nonce-reuse detection is implemented |
| Key size | ✅ Correct | 256-bit keys used throughout |
| Authentication tag | ✅ Correct | GCM appends 16-byte authentication tag to ciphertext |
| Associated Data (AAD) | ❌ MISSING | `AESGCM.encrypt(nonce, plaintext, None)` — AAD is `None`. Should bind context (user_id, field_name, key_version) to prevent ciphertext swapping attacks |
| Field-level encryption | ✅ Correct | Each sensitive field encrypted independently with unique nonce |

**Issue #1: Missing Associated Authenticated Data (AAD)**
- **Severity:** MEDIUM
- **Location:** `architecture_security.md` §3.4, `architecture_data_storage.md` §8.2
- **Detail:** Both `FieldEncryptor.encrypt()` and `encrypt_credentials()` pass `None` as AAD. Without AAD, an attacker who can modify the database could swap encrypted fields between users/accounts without detection.
- **Recommendation:** Bind context as AAD:
  ```python
  aad = f"{user_id}:{field_name}:{key_version}".encode()
  ciphertext = aesgcm.encrypt(nonce, plaintext, aad)
  ```

**Issue #2: Fernet Mentioned Then Abandoned**
- **Severity:** LOW
- **Location:** `architecture_security.md` §3.4 comment
- **Detail:** Comment says "Fernet (AES-128-CBC + HMAC) Upgraded to AES-256-GCM for production" — the Fernet mention is misleading. Fernet uses AES-128-CBC, not AES-256. The actual implementation correctly uses AES-256-GCM, but the comment could confuse auditors.
- **Recommendation:** Remove the Fernet reference entirely; document only the actual AES-256-GCM implementation.

---

### 2. Is the Rust Keyring Implementation Secure? ✅ MOSTLY — with gaps

**Findings:**

| Item | Status | Detail |
|------|--------|--------|
| Crate selection | ✅ Correct | `keyring = "3"` — cross-platform, well-maintained |
| Entry naming | ✅ Correct | `com.alphastack.credentials` as service, `{account_id}.{credential_type}` as key |
| Platform backends | ✅ Correct | DPAPI (Windows), Keychain (macOS), Secret Service (Linux) |
| Error handling | ✅ Correct | All keyring operations wrapped with `Result<_, SecurityError>` |
| `SecureString` / `ZeroizeOnDrop` | ✅ Correct | `zeroize = "1"` crate properly used for memory zeroing |
| Keyring unavailable fallback | ⚠️ CONCERN | File-based fallback uses `age` crate (X25519 + ChaCha20-Poly1305), but key derivation is problematic |

**Issue #3: Key Derivation in File Fallback Uses Raw Key as X25519 Identity**
- **Severity:** HIGH
- **Location:** `architecture_security.md` §3.3
- **Detail:** The `derive_key()` function produces a 32-byte Argon2id output, which is then fed directly into `age::x25519::Identity::from_bytes(key)`. This is a **type confusion**: Argon2id output is a symmetric key, but X25519 expects a private scalar. The `age` crate's `Identity::from_bytes()` expects 32 bytes of X25519 private key material, not an arbitrary derived key. While this may "work" (the bytes are interpreted as a scalar), it violates the `age` format specification and may produce weak keys if the Argon2id output doesn't have the correct scalar properties.
- **Recommendation:** Either:
  - (a) Use `age` with a passphrase directly (`age::Encryptor::with_user_passphrase()` which does proper scrypt KDF internally), OR
  - (b) Use the derived key with a symmetric cipher like ChaCha20-Poly1305 directly (via the `ring` or `chacha20poly1305` crate), bypassing X25519 entirely.

**Issue #4: File Fallback Permissions Are Correct But Incomplete**
- **Severity:** LOW
- **Location:** `architecture_security.md` §3.3
- **Detail:** `Permissions::from_mode(0o600)` is correct for the credential file, but the parent directory `config_dir/alphastack/credentials/` is created with `fs::create_dir_all()` which defaults to 0o755. The directory should also be 0o700.
- **Recommendation:** Set directory permissions to 0o700 after creation.

**Issue #5: No Credential File Integrity Check**
- **Severity:** MEDIUM
- **Location:** `architecture_security.md` §3.3
- **Detail:** The encrypted file fallback has no integrity verification before decryption. While `age` uses ChaCha20-Poly1305 (authenticated encryption), there's no file-level tamper detection (e.g., file hash stored in keyring or separate location). An attacker who replaces the encrypted file could cause a denial of service or trigger unexpected error paths.
- **Recommendation:** Store a SHA-256 hash of the encrypted file in a separate location (or in the keyring entry metadata) and verify before decryption.

---

### 3. Is Broker Credential Isolation Proper? ✅ YES — Exemplary

**Findings:**

| Isolation Layer | Status | Detail |
|-----------------|--------|--------|
| Level 1: Process | ✅ Correct | Credential operations in separate process from main app |
| Level 2: Memory | ✅ Correct | `ZeroizeOnDrop` on `BrokerCredentials` struct |
| Level 3: Storage | ✅ Correct | OS Keyring or HSM — never in application database |
| Level 4: Network | ✅ Correct | Credentials never transmitted to Alpha Stack servers |
| Level 5: Access Control | ✅ Correct | Per-user, per-account scoping with RBAC |
| Credential lifecycle | ✅ Correct | Load → use → zero pattern enforced |
| Audit logging | ✅ Correct | All credential access logged (without values) |
| OAuth2 flow | ✅ Correct | Broker password never touches Alpha Stack for OAuth2 brokers |
| MT5 bridge mTLS | ✅ Correct | Mutual TLS with certificate pinning |
| Crash dump disabled | ✅ Correct | Prevents credential leakage via memory dumps |

**Assessment:** The 5-layer isolation model is **exemplary** and exceeds what most trading platforms implement. The key architectural decision — credentials stay on-device and are never sent to Alpha Stack servers — is the single most important security property and is correctly enforced.

**Issue #6: Bridge Crash Dump Disablement Not Verified**
- **Severity:** LOW
- **Location:** `architecture_security.md` §6.5
- **Detail:** "Crash dump collection disabled" is stated but no implementation code or Windows registry/GPO configuration is provided. On Windows, crash dumps are controlled by `HKLM\SOFTWARE\Microsoft\Windows\Windows Error Reporting` and `LocalDumps` keys. This should be automated in the bridge deployment script.
- **Recommendation:** Include a Windows setup script that disables crash dumps and verifies the configuration.

---

### 4. Is Data Encrypted at Rest and In Transit? ⚠️ PARTIALLY — by design

**Data at Rest:**

| Component | Encrypted? | Detail |
|-----------|------------|--------|
| Broker credentials (device) | ✅ YES | OS Keyring (DPAPI/Keychain/Secret Service) |
| Broker credentials (server DB) | ✅ YES | AES-256-GCM field-level encryption |
| TOTP secrets | ✅ YES | AES-256-GCM field-level encryption |
| User passwords | ✅ YES | Argon2id hashing (not reversible) |
| API keys | ✅ YES | SHA-256 hash stored (original shown once) |
| Session tokens | ✅ YES | SHA-256 hash stored |
| Market data (ticks, candles) | ❌ NO | Plaintext in PostgreSQL/TimescaleDB |
| Trade records | ❌ NO | Plaintext in PostgreSQL |
| User PII (email, name) | ❌ NO | Plaintext in PostgreSQL |
| Logs | ❌ NO | Plaintext on disk |
| Backups | ⚠️ DEFERRED | GPG encryption planned for Phase 1, but marked as optional |
| Disk-level (LUKS) | ⚠️ DEFERRED | Phase 2+ for VPS, optional for Phase 1 |

**Data in Transit:**

| Channel | Encrypted? | Detail |
|---------|------------|--------|
| Client ↔ API | ✅ YES | TLS 1.3 (explicitly mandated) |
| Desktop ↔ MT5 Bridge | ✅ YES | mTLS with certificate pinning |
| Internal services | ✅ YES | TLS 1.3 for all service-to-service |
| Redis | ⚠️ PARTIAL | TLS not mentioned; `bind 127.0.0.1` provides network isolation but not encryption |
| PostgreSQL | ⚠️ PARTIAL | SSL mentioned in checklist but not in architecture |
| WebSocket | ✅ YES | WSS (WebSocket over TLS) |

**Issue #7: Backup Encryption Marked as Optional in Phase 1**
- **Severity:** HIGH
- **Location:** `architecture_data_storage.md` §7.2
- **Detail:** The Phase 1 backup script has GPG encryption **commented out** (`# gpg --symmetric...`). Backups of a trading database contain trade history, account balances, and (if any server-side creds exist) encrypted credential blobs. Unencrypted backups on local disk are a significant risk.
- **Recommendation:** Make backup encryption **mandatory from Phase 1**, not optional. Even at $7 capital, GPG encryption adds zero cost and negligible overhead.

**Issue #8: Redis Lacks TLS Configuration**
- **Severity:** MEDIUM
- **Location:** `architecture_data_storage.md` §3.2
- **Detail:** Redis configuration shows `bind 127.0.0.1` (good) and `requirepass` (good), but no TLS configuration. While localhost binding prevents network interception, the defense-in-depth model should include TLS for Redis connections, especially when Redis moves to a separate server in Phase 3.
- **Recommendation:** Document Redis TLS configuration for Phase 2+ and enable it when Redis is on a separate host.

---

### 5. Is Key Management Secure? ⚠️ MODERATE — well-designed but with implementation gaps

**Key Hierarchy Assessment:**

| Layer | Status | Detail |
|-------|--------|--------|
| Master Key (KMS/HSM) | ✅ Correct | Managed by infrastructure, never exposed to app |
| DEK (Data Encryption Key) | ⚠️ CONCERN | Cached in memory (`_key_cache` dict) with no TTL or eviction |
| JWT signing (RSA-4096) | ✅ Correct | Asymmetric, 90-day rotation, 30-day grace period |
| TOTP secrets | ✅ Correct | 256-bit CSPRNG, encrypted before storage |
| Password hashing | ✅ Correct | Argon2id with 64MB memory, 3 iterations, 4 parallelism |
| Backup encryption | ⚠️ DEFERRED | GPG key rotation planned but not specified |

**Issue #9: DEK Cache Has No TTL or Eviction**
- **Severity:** MEDIUM
- **Location:** `architecture_security.md` §3.4
- **Detail:** `self._key_cache[version] = self.kms.generate_data_key(...)` caches DEKs indefinitely in a Python dict. If the application process is long-running, DEKs persist in memory far longer than needed. The KMS `generate_data_key` call returns a `Plaintext` key that should be zeroized after use or cached with a short TTL.
- **Recommendation:** Implement cache TTL (e.g., 1 hour) and use `zeroize` on eviction. In Rust, this would use `ZeroizeOnDrop` on the key container.

**Issue #10: Key Rotation for DEKs Is 90 Days But No Re-encryption Automation**
- **Severity:** MEDIUM
- **Location:** `architecture_security.md` §3.5
- **Detail:** The key rotation table says DEKs are "Rotated every 90 days" with "Re-encrypt in background" method. However, no background re-encryption job is described. Without re-encryption, old DEKs must be retained indefinitely, expanding the key management surface.
- **Recommendation:** Implement a background re-encryption job that:
  1. Generates a new DEK version
  2. Reads all fields encrypted with the old DEK
  3. Re-encrypts with the new DEK
  4. Verifies integrity
  5. Retires the old DEK after verification

**Issue #11: No Key Escrow or Recovery Mechanism**
- **Severity:** MEDIUM
- **Location:** `architecture_security.md` (not addressed)
- **Detail:** If the master key is lost (KMS failure, accidental deletion), all encrypted data is permanently unrecoverable. The document mentions KMS automatic rotation but not key escrow or recovery procedures.
- **Recommendation:** Document KMS key recovery procedures, including cross-region key replication and break-glass access procedures.

---

### 6. What Encryption Vulnerabilities Exist?

#### Critical/High Findings

| # | Vulnerability | Severity | CVSS Est. | Exploitability |
|---|--------------|----------|-----------|----------------|
| V1 | Argon2id output used as X25519 private key in file fallback | HIGH | 7.5 | Medium — requires access to encrypted file + understanding of key derivation |
| V2 | Backup encryption optional in Phase 1 | HIGH | 7.1 | Low — requires local disk access |
| V3 | No AAD in AES-256-GCM field encryption | MEDIUM | 5.9 | Medium — requires database write access |

#### Medium Findings

| # | Vulnerability | Severity | CVSS Est. | Exploitability |
|---|--------------|----------|-----------|----------------|
| V4 | DEK cache has no TTL/eviction | MEDIUM | 5.3 | Medium — requires memory access |
| V5 | No key recovery/escrow mechanism | MEDIUM | 5.0 | Low — operational risk, not attack |
| V6 | Redis TLS not configured | MEDIUM | 4.8 | Low — localhost binding mitigates |
| V7 | No encrypted file integrity verification | MEDIUM | 4.5 | Low — requires file replacement |
| V8 | No DEK re-encryption automation | MEDIUM | 4.3 | Low — operational risk |

#### Low Findings

| # | Vulnerability | Severity | CVSS Est. | Exploitability |
|---|--------------|----------|-----------|----------------|
| V9 | Credential file parent directory permissions too open | LOW | 3.5 | Low — requires local access |
| V10 | Fernet comment misleading in code | LOW | 0.0 | N/A — documentation only |
| V11 | MT5 bridge crash dump disablement not automated | LOW | 3.1 | Low — requires Windows access |

#### Informational

| # | Finding | Detail |
|---|---------|--------|
| I1 | AES-256 quantum resistance | AES-256 provides 128-bit security against Grover's algorithm — sufficient |
| I2 | Argon2id quantum resistance | Memory-hard nature is not reduced by quantum — sufficient |
| I3 | SHA-256 quantum resistance | 128-bit effective security against Grover — sufficient |
| I4 | RSA-4096 JWT signing vulnerable to Shor's | Correctly identified; hybrid migration (Ed25519 + ML-DSA-65) planned |
| I5 | X25519 key exchange vulnerable to Shor's | Correctly identified; hybrid TLS (X25519 + ML-KEM-768) planned |

---

## Detailed Recommendations

### Priority 1 — Fix Before Implementation

**R1: Fix File Fallback Key Derivation (V1)**
```rust
// BEFORE (incorrect — Argon2id output as X25519 identity):
let key = derive_key(master_password, salt);
let recipient = age::x25519::Identity::from_bytes(key).to_public();
let encrypted = age::encrypt(&recipient, data.as_bytes());

// AFTER (option A — use age passphrase mode):
let encryptor = age::Encryptor::with_user_passphrase(
    Secret::new(master_password.to_string())
);
let mut encrypted = vec![];
let mut writer = encryptor.wrap_output(&mut encrypted)?;
writer.write_all(data.as_bytes())?;
writer.finish()?;

// AFTER (option B — use ring directly):
use ring::aead::{Aad, LessSafeKey, Nonce, UnboundKey, AES_256_GCM};
let unbound = UnboundKey::new(&AES_256_GCM, &derived_key)?;
let key = LessSafeKey::new(unbound);
let nonce = Nonce::assume_unique_for_key(nonce_bytes);
let mut in_out = plaintext.to_vec();
key.seal_in_place_append_tag(nonce, Aad::empty(), &mut in_out)?;
```

**R2: Make Backup Encryption Mandatory (V2)**
```bash
# Remove comments, make encryption default:
gpg --batch --yes --symmetric --cipher-algo AES256 \
    --output "$BACKUP_DIR/alphastack_${TIMESTAMP}.dump.gpg" \
    "$BACKUP_DIR/alphastack_${TIMESTAMP}.dump"
rm "$BACKUP_DIR/alphastack_${TIMESTAMP}.dump"
```

**R3: Add AAD to AES-256-GCM Encryption (V3)**
```python
# In FieldEncryptor.encrypt():
aad = f"{key_version}:{field_name}".encode()
ciphertext = aesgcm.encrypt(nonce, plaintext, aad)

# In decrypt():
plaintext = aesgcm.decrypt(nonce, ciphertext, aad)
```

### Priority 2 — Fix During Implementation

**R4: Add DEK Cache TTL**
```python
import time

class FieldEncryptor:
    def __init__(self, kms_client, cache_ttl_seconds=3600):
        self.kms = kms_client
        self._key_cache = {}  # version -> (key, timestamp)
        self._cache_ttl = cache_ttl_seconds
    
    def _get_dek(self, version: str) -> bytes:
        if version in self._key_cache:
            key, ts = self._key_cache[version]
            if time.time() - ts < self._cache_ttl:
                return key
        key = self.kms.generate_data_key(...)["Plaintext"]
        self._key_cache[version] = (key, time.time())
        return key
```

**R5: Implement DEK Re-encryption Background Job**
- Create a Celery/scheduled task that re-encrypts all DEK-encrypted fields on rotation
- Use a two-phase commit: encrypt with new DEK, verify, delete old DEK reference

**R6: Configure Redis TLS for Phase 2+**
```conf
# redis.conf — Phase 2+
tls-port 6380
port 0  # Disable non-TLS port
tls-cert-file /etc/redis/tls/redis.crt
tls-key-file /etc/redis/tls/redis.key
tls-ca-cert-file /etc/redis/tls/ca.crt
tls-auth-clients optional  # or 'yes' for mutual TLS
```

### Priority 3 — Address During Hardening

**R7:** Set credential file directory permissions to 0o700
**R8:** Add encrypted file integrity hash (stored separately)
**R9:** Automate MT5 bridge crash dump disablement
**R10:** Document KMS key recovery/escrow procedures
**R11:** Remove misleading Fernet comment from codebase

---

## Quantum Readiness Assessment

The quantum-resistant cryptography section is **well-architected**. Key observations:

| Aspect | Assessment |
|--------|------------|
| Threat timeline | Realistic (CRQC for RSA-2048: 2035-2045) |
| HNDL risk correctly identified | ✅ Harvest-now-decrypt-later is the immediate threat |
| Hybrid approach | ✅ Correct — classical + PQC combined provides defense-in-depth |
| Algorithm selection | ✅ Correct — ML-KEM-768, ML-DSA-65, SPHINCS+ are NIST standards |
| Crypto-agility | ✅ Excellent — trait-based abstraction allows algorithm swapping |
| AES-256 assessment | ✅ Correct — 128-bit quantum security is sufficient |
| Migration roadmap | ✅ Reasonable — Phase 1 audit, Phase 2-3 hybrid, Phase 4 full PQC |
| QRNG integration | ⚠️ OPTIONAL — CSPRNG is sufficient; QRNG adds complexity for marginal benefit |

**Note on QRNG:** The ANU QRNG API dependency introduces a network call into the key generation path. For production, prefer OS CSPRNG (`/dev/urandom`, `CryptGenRandom`) which is cryptographically secure and has no network dependency. QRNG is a nice-to-have for defense-in-depth but should not be in the critical path.

---

## Comparison to Industry Standards

| Standard | Alpha Stack | Requirement | Gap |
|----------|-------------|-------------|-----|
| **NIST SP 800-175B** (Guideline for Using Crypto) | AES-256-GCM, Argon2id, RSA-4096 | Approved algorithms | None |
| **PCI DSS 4.0** Req. 3.4-3.6 | Field-level encryption, key rotation | Encrypt PAN at rest | N/A (no card data) |
| **GDPR Art. 32** | Encryption at rest + transit | Appropriate technical measures | Disk encryption deferred |
| **OWASP ASVS 4.0** V6 (Crypto) | AES-256-GCM, no ECB/CBC, proper key management | Authenticated encryption | AAD missing |
| **FIPS 140-3** | Not required but principles applied | Approved algorithms, key management | KMS integration deferred |
| **Kenya DPA §41** | Encryption at rest + transit | Appropriate safeguards | Disk encryption deferred |

---

## Conclusion

Alpha Stack's encryption architecture is **fundamentally sound** and demonstrates security awareness beyond typical startup-level implementations. The 5-layer broker credential isolation model is particularly noteworthy — it correctly identifies the most critical asset (broker credentials enabling fund access) and applies defense-in-depth.

The three most impactful items to address before implementation:

1. **Fix the X25519 key derivation bug** in the file fallback (V1) — this is a cryptographic correctness issue
2. **Make backup encryption mandatory** from Phase 1 (V2) — trivial fix, significant risk reduction
3. **Add AAD to AES-256-GCM** (V3) — prevents ciphertext swapping attacks

With these three fixes implemented, the encryption architecture would rate **8.5/10** for a pre-implementation design, which is strong for a system that hasn't yet been built.

---

*This review is valid as of the design documents reviewed. A follow-up review should occur after Phase 1 implementation to verify that code matches the architecture.*
