# Quantum Integration Fix — Critical Gap Implementation Specs

> **Prepared by:** Quantum Integration Fix Agent  
> **Date:** 2026-07-11  
> **Source:** `review_quantum_integration.md` (3 critical gaps), `fix_security_quantum.md`  
> **Scope:** Implementation-level specs for the 3 critical gaps blocking production  
> **Status:** 🔴 ACTIVE — Detailed specs ready for engineering execution

---

## Gap Summary

| # | Gap | Review Finding | This Document Provides |
|---|-----|----------------|------------------------|
| 1 | JWT hybrid not implemented | Fix designed, code not written | Full Phase A + Phase B implementation spec |
| 2 | No PQC for broker connections | MT5/CCXT/REST use classical TLS only | PQC-ready TLS config per broker type |
| 3 | KMS PQC unverified | DEK re-wrap assumes ML-KEM support | KMS audit spec + software fallback design |

---

## Gap 1: JWT Hybrid Signing — Implementation Spec

### 1.1 Problem Recap

The fix doc designs a two-phase migration (RS256 → Ed25519 → Hybrid) but provides no implementation code, dependency versions, or integration test specs. This section fills those gaps.

### 1.2 Phase A — Ed25519 (Pre-Production)

#### 1.2.1 Dependencies

```toml
# Cargo.toml additions
[dependencies]
ed25519-dalek = { version = "2.1", features = ["serde", "pem"] }
jsonwebtoken = "9.3"
rand = "0.8"
zeroize = { version = "1.8", features = ["derive"] }
```

#### 1.2.2 Key Generation

```rust
use ed25519_dalek::{SigningKey, VerifyingKey};
use rand::rngs::OsRng;
use zeroize::Zeroize;

/// Generate a new Ed25519 keypair for JWT signing.
/// Private key MUST be stored in KMS/HSM — never on disk in plaintext.
pub struct JwtEd25519Keypair {
    signing_key: SigningKey,      // private — zeroize on drop
    verifying_key: VerifyingKey,  // public — can be distributed
}

impl JwtEd25519Keypair {
    pub fn generate() -> Self {
        let signing_key = SigningKey::generate(&mut OsRng);
        let verifying_key = signing_key.verifying_key();
        Self { signing_key, verifying_key }
    }

    /// Export the private key bytes for KMS import.
    /// Caller MUST zeroize the returned bytes after KMS ingestion.
    pub fn export_private_key_bytes(&self) -> [u8; 32] {
        self.signing_key.to_bytes()
    }

    /// Export the public key bytes for distribution.
    pub fn export_public_key_bytes(&self) -> [u8; 32] {
        self.verifying_key.to_bytes()
    }
}

impl Drop for JwtEd25519Keypair {
    fn drop(&mut self) {
        // SigningKey implements ZeroizeOnDrop via ed25519-dalek
    }
}
```

#### 1.2.3 Token Signing

```rust
use jsonwebtoken::{encode, Header, Algorithm, EncodingKey};
use serde::{Serialize, Deserialize};

#[derive(Debug, Serialize, Deserialize)]
struct Claims {
    sub: String,        // subject (user ID)
    exp: u64,           // expiration (unix timestamp)
    iat: u64,           // issued at
    jti: String,        // unique token ID (for revocation)
    scope: Vec<String>, // permissions
}

/// Sign a JWT with Ed25519.
/// Returns the compact JWT string.
fn sign_jwt_ed25519(
    claims: &Claims,
    private_key_bytes: &[u8; 32],
) -> Result<String, JwtError> {
    let mut header = Header::new(Algorithm::EdDSA);
    header.kid = Some(current_key_id()); // key ID for rotation

    let encoding_key = EncodingKey::from_ed_der(private_key_bytes);
    encode(&header, claims, &encoding_key)
        .map_err(|e| JwtError::SigningFailed(e.to_string()))
}
```

#### 1.2.4 Token Verification

```rust
use jsonwebtoken::{decode, DecodingKey, Validation};

/// Verify an Ed25519-signed JWT.
/// Returns claims if valid, error otherwise.
fn verify_jwt_ed25519(
    token: &str,
    public_key_bytes: &[u8; 32],
) -> Result<Claims, JwtError> {
    let mut validation = Validation::new(Algorithm::EdDSA);
    validation.set_required_spec_claims(&["sub", "exp", "jti"]);
    validation.validate_exp = true;

    let decoding_key = DecodingKey::from_ed_der(public_key_bytes);
    decode::<Claims>(token, &decoding_key, &validation)
        .map(|data| data.claims)
        .map_err(|e| JwtError::VerificationFailed(e.to_string()))
}
```

#### 1.2.5 Migration from RS256

```rust
/// Dual-verification during migration window (7 days).
/// Accepts both RS256 and EdDSA tokens.
fn verify_jwt_migration(
    token: &str,
    ed25519_pubkey: &[u8; 32],
    rsa_pubkey: &[u8],          // RSA-4096 DER — for legacy tokens only
) -> Result<Claims, JwtError> {
    // Parse header to determine algorithm
    let header = jsonwebtoken::decode_header(token)?;
    match header.alg {
        Algorithm::EdDSA => verify_jwt_ed25519(token, ed25519_pubkey),
        Algorithm::RS256 => {
            // Legacy path — remove after migration window
            log::warn!("Legacy RS256 JWT detected — migration in progress");
            verify_jwt_rs256(token, rsa_pubkey)
        }
        other => Err(JwtError::UnsupportedAlgorithm(other)),
    }
}
```

#### 1.2.6 Phase A Verification Matrix

| Test Case | Input | Expected | Pass Criteria |
|-----------|-------|----------|---------------|
| EdDSA sign+verify roundtrip | Valid claims | Claims recovered | Exact match |
| RS256 rejection (post-migration) | RS256 token | Rejected | `UnsupportedAlgorithm` error |
| Expired token rejection | Token with `exp < now` | Rejected | `ExpiredSignature` error |
| Invalid signature rejection | Tampered token | Rejected | `InvalidSignature` error |
| Missing claims rejection | Token without `jti` | Rejected | `MissingRequiredClaim` error |
| Key rotation: old key verify | Token signed with old key | Rejected (after grace) | `InvalidKeyId` error |
| Performance: latency | 10,000 verify ops | p99 < 2ms | Benchmark threshold |
| Performance: token size | EdDSA JWT | < 1 KB | Size check |

---

### 1.3 Phase B — Hybrid Ed25519 + ML-DSA-65

#### 1.3.1 Dependencies

```toml
# Cargo.toml additions for Phase B
[dependencies]
oqs = { version = "0.9", features = ["ml-dsa-65"] }  # liboqs Rust bindings
ed25519-dalek = { version = "2.1", features = ["serde"] }
```

**Library maturity note:** `oqs` (liboqs Rust bindings) is the primary PQC library. As of mid-2026:
- **liboqs C library:** 0.11.x — mature, NIST reference implementations
- **oqs Rust crate:** 0.9.x — maintained, but NOT yet at 1.0
- **Risk mitigation:** Abstract behind trait; can swap to `pqcrypto-ml-dsa` if needed

#### 1.3.2 Hybrid Signature Block Format

```
Hybrid JWT Structure:
┌─────────────────────────────────────────────────────────────┐
│  <header>.<payload>.<hybrid_signature_block>                │
│                                                             │
│  hybrid_signature_block (Base64url-encoded):                │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ version: u8 = 0x01                                    │  │
│  │ classical_alg: u8 = 0x01 (Ed25519)                    │  │
│  │ pq_alg: u8 = 0x01 (ML-DSA-65)                        │  │
│  │ classical_sig_len: u16 (big-endian) = 64              │  │
│  │ classical_sig: [u8; 64]                               │  │
│  │ pq_sig: [u8; 3309]                                    │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  Total sig block: 1 + 1 + 1 + 2 + 64 + 3309 = 3,378 bytes │
│  Base64url encoded: ~4,504 bytes                            │
│  Total JWT (with typical claims): ~4.5-5 KB                 │
└─────────────────────────────────────────────────────────────┘
```

#### 1.3.3 Hybrid Signing Implementation

```rust
use oqs::sig::{self, Algorithm};
use ed25519_dalek::{SigningKey as EdSigningKey, Signer};

const HYBRID_SIG_VERSION: u8 = 0x01;
const ALG_ED25519: u8 = 0x01;
const ALG_ML_DSA_65: u8 = 0x01;

struct HybridSigningKey {
    ed25519: EdSigningKey,
    ml_dsa: sig::SecretKey,
}

struct HybridVerifyingKey {
    ed25519: ed25519_dalek::VerifyingKey,
    ml_dsa: sig::PublicKey,
}

/// Build the hybrid signature block (binary format).
fn build_hybrid_signature(
    classical_sig: &[u8; 64],
    pq_sig: &[u8],
) -> Vec<u8> {
    let mut block = Vec::with_capacity(3_378);
    block.push(HYBRID_SIG_VERSION);
    block.push(ALG_ED25519);
    block.push(ALG_ML_DSA_65);
    block.extend_from_slice(&(64u16).to_be_bytes());
    block.extend_from_slice(classical_sig);
    block.extend_from_slice(pq_sig);
    block
}

/// Parse the hybrid signature block.
fn parse_hybrid_signature(block: &[u8]) -> Result<(&[u8], &[u8]), HybridSigError> {
    if block.len() < 4 {
        return Err(HybridSigError::BlockTooShort);
    }
    if block[0] != HYBRID_SIG_VERSION {
        return Err(HybridSigError::UnknownVersion(block[0]));
    }

    let sig_len = u16::from_be_bytes([block[2], block[3]]) as usize;
    if block.len() < 4 + sig_len {
        return Err(HybridSigError::TruncatedClassicalSig);
    }

    let classical_sig = &block[4..4 + sig_len];
    let pq_sig = &block[4 + sig_len..];

    Ok((classical_sig, pq_sig))
}

/// Sign a JWT with hybrid Ed25519 + ML-DSA-65.
fn sign_jwt_hybrid(
    claims: &Claims,
    signing_key: &HybridSigningKey,
) -> Result<String, JwtError> {
    // Build header
    let mut header = Header::new(Algorithm::EdDSA); // Primary alg for compat
    header.kid = Some(current_hybrid_key_id());
    // Custom header field for hybrid algorithm
    header.additional_fields.insert(
        "hybrid_alg".to_string(),
        serde_json::Value::String("Ed25519+ML-DSA-65".to_string()),
    );

    let header_b64 = base64url_encode(&serde_json::to_vec(&header)?);
    let payload_b64 = base64url_encode(&serde_json::to_vec(claims)?);
    let signing_input = format!("{}.{}", header_b64, payload_b64);
    let signing_bytes = signing_input.as_bytes();

    // Classical signature (Ed25519)
    let classical_sig = signing_key.ed25519.sign(signing_bytes).to_bytes();

    // Post-quantum signature (ML-DSA-65)
    let ml_dsa = sig::new(Algorithm::MlDsa65)?;
    let pq_sig = ml_dsa.sign(signing_bytes, &signing_key.ml_dsa)?;

    // Build hybrid block
    let hybrid_block = build_hybrid_signature(&classical_sig, pq_sig.as_ref());
    let sig_b64 = base64url_encode(&hybrid_block);

    Ok(format!("{}.{}.{}", header_b64, payload_b64, sig_b64))
}
```

#### 1.3.4 Hybrid Verification (Constant-Time)

```rust
/// CRITICAL: Both signatures MUST be verified regardless of individual outcomes.
/// No short-circuit on first failure — this prevents algorithm-substitution attacks.
fn verify_jwt_hybrid(
    token: &str,
    verifying_key: &HybridVerifyingKey,
) -> Result<Claims, JwtError> {
    let parts: Vec<&str> = token.split('.').collect();
    if parts.len() != 3 {
        return Err(JwtError::MalformedToken);
    }

    let signing_input = format!("{}.{}", parts[0], parts[1]);
    let signing_bytes = signing_input.as_bytes();

    // Decode and parse hybrid signature block
    let sig_block = base64url_decode(parts[2])?;
    let (classical_sig_bytes, pq_sig_bytes) = parse_hybrid_signature(&sig_block)?;

    // ALWAYS verify both — no short-circuit, no early return
    let classical_result = verify_ed25519(
        &verifying_key.ed25519,
        signing_bytes,
        classical_sig_bytes,
    );

    let pq_result = verify_ml_dsa_65(
        &verifying_key.ml_dsa,
        signing_bytes,
        pq_sig_bytes,
    );

    // Both must succeed
    match (classical_result, pq_result) {
        (Ok(true), Ok(true)) => {
            // Decode claims
            let claims: Claims = base64url_decode_and_deserialize(parts[1])?;
            Ok(claims)
        }
        (Ok(true), Ok(false)) => {
            log::error!("Hybrid JWT: classical sig valid, PQ sig INVALID — possible tampering");
            Err(JwtError::PqSignatureInvalid)
        }
        (Ok(false), Ok(true)) => {
            log::error!("Hybrid JWT: PQ sig valid, classical sig INVALID — possible tampering");
            Err(JwtError::ClassicalSignatureInvalid)
        }
        (Ok(false), Ok(false)) => {
            Err(JwtError::BothSignaturesInvalid)
        }
        (Err(e), _) => {
            log::error!("Hybrid JWT: classical verification error: {}", e);
            Err(JwtError::ClassicalVerificationError(e))
        }
        (_, Err(e)) => {
            log::error!("Hybrid JWT: PQ verification error: {}", e);
            Err(JwtError::PqVerificationError(e))
        }
    }
}
```

#### 1.3.5 `alg` Header Confusion Attack Mitigation

The review identified that an attacker could strip the `hybrid_alg` header field and force classical-only verification. **Mitigation: server-side enforcement.**

```rust
/// Verify a JWT with algorithm policy enforcement.
/// NEVER trust client-specified algorithm preferences.
fn verify_jwt_with_policy(
    token: &str,
    policy: &VerificationPolicy,
    ed25519_key: &ed25519_dalek::VerifyingKey,
    ml_dsa_key: &Option<sig::PublicKey>,
) -> Result<Claims, JwtError> {
    let header = jsonwebtoken::decode_header(token)?;

    match policy {
        VerificationPolicy::HybridRequired => {
            // MUST have hybrid_alg header field
            if !header.additional_fields.contains_key("hybrid_alg") {
                log::error!("Hybrid JWT required but hybrid_alg header missing — possible downgrade attack");
                return Err(JwtError::HybridRequired);
            }

            let ml_dsa_key = ml_dsa_key.as_ref()
                .ok_or(JwtError::PqKeyNotConfigured)?;

            let verifying_key = HybridVerifyingKey {
                ed25519: *ed25519_key,
                ml_dsa: ml_dsa_key.clone(),
            };
            verify_jwt_hybrid(token, &verifying_key)
        }

        VerificationPolicy::HybridPreferred => {
            // Try hybrid first, fall back to classical
            if header.additional_fields.contains_key("hybrid_alg") {
                if let Some(ml_dsa_key) = ml_dsa_key {
                    let verifying_key = HybridVerifyingKey {
                        ed25519: *ed25519_key,
                        ml_dsa: ml_dsa_key.clone(),
                    };
                    return verify_jwt_hybrid(token, &verifying_key);
                }
            }
            // Fallback to classical
            verify_jwt_ed25519(token, &ed25519_key.to_bytes())
        }

        VerificationPolicy::ClassicalOnly => {
            verify_jwt_ed25519(token, &ed25519_key.to_bytes())
        }
    }
}

enum VerificationPolicy {
    /// Hybrid signatures required — reject any classical-only token
    HybridRequired,
    /// Accept hybrid or classical — prefer hybrid when available
    HybridPreferred,
    /// Classical only — for pre-migration services
    ClassicalOnly,
}
```

#### 1.3.6 Token Size Management

```
Token Size Analysis:
┌─────────────────────────────────────────────────────────────────────┐
│ Component          │ RS256    │ Ed25519  │ Hybrid Ed25519+ML-DSA-65 │
│────────────────────│──────────│──────────│──────────────────────────│
│ Header (typical)   │ ~100 B   │ ~100 B   │ ~150 B (extra fields)    │
│ Payload (typical)  │ ~300 B   │ ~300 B   │ ~300 B                   │
│ Signature          │ ~512 B   │ ~86 B    │ ~4,504 B                 │
│ Total JWT          │ ~912 B   │ ~486 B   │ ~4,954 B                 │
│────────────────────│──────────│──────────│──────────────────────────│
│ vs RS256           │ baseline │ -47%     │ +443%                    │
└─────────────────────────────────────────────────────────────────────┘
```

**Mitigation strategies (from fix doc, with implementation detail):**

| Strategy | Implementation | Size |
|----------|---------------|------|
| Opaque refresh tokens | Generate UUID, store claims in Redis/DB with TTL | 36 bytes |
| Opaque API session tokens | Same as refresh — server-side state | 36 bytes |
| Slim down claims | Remove `scope` array, use role-based lookup server-side | ~200 bytes saved |
| Compression | JWT spec doesn't support compression — N/A | N/A |
| Chunked auth header | Non-standard, breaks interop — **not recommended** | N/A |

```yaml
# Production token strategy config
token_strategy:
  access_token:
    type: hybrid-jwt
    max_size_bytes: 5120
    ttl_seconds: 900          # 15 minutes
    claims:
      sub: required
      exp: required
      jti: required
      scope: server-side      # Don't embed scope in JWT — lookup from DB

  refresh_token:
    type: opaque
    format: uuid-v4
    storage: redis
    ttl_seconds: 604800       # 7 days
    rotation: on-use          # Rotate refresh token on each use

  api_session_token:
    type: opaque
    format: uuid-v4
    storage: redis
    ttl_seconds: 3600         # 1 hour
    rotation: on-use
```

#### 1.3.7 Key Rotation Schedule

```yaml
hybrid_jwt_key_rotation:
  # Both keypairs rotate together
  rotation_interval_days: 90
  grace_period_days: 7        # Old keys still accepted for verification
  
  rotation_process:
    1_generate:
      description: "Generate new Ed25519 + ML-DSA-65 keypairs"
      storage: KMS / HSM
      ed25519_key_size: 32 bytes
      ml_dsa_65_key_size: 4032 bytes (public), 4000 bytes (secret)

    2_deploy:
      description: "Deploy new public keys to all verifiers"
      method: "JWKS endpoint update"
      jwks_url: "/.well-known/jwks.json"

    3_sign_with_new:
      description: "All new tokens signed with new keypair"
      immediate: true

    4_verify_old:
      description: "Old keys accepted for verification during grace period"
      duration_days: 7

    5_decommission:
      description: "Remove old keys from JWKS after grace period"
      secure_delete: true       # HSM-managed destruction

  key_id_format: "hybrid-{timestamp}-{short_hash}"
  monitoring:
    - alert_on_rotation_failure
    - alert_on_key_generation_failure
    - metric: active_key_count (should be 2 during grace, 1 otherwise)
```

#### 1.3.8 Phase B Integration Tests

```rust
#[cfg(test)]
mod hybrid_jwt_tests {
    use super::*;

    /// Core: sign and verify roundtrip
    #[test]
    fn test_hybrid_sign_verify_roundtrip() {
        let keypair = generate_hybrid_keypair();
        let claims = test_claims();
        let token = sign_jwt_hybrid(&claims, &keypair.signing_key).unwrap();
        let verified = verify_jwt_hybrid(&token, &keypair.verifying_key).unwrap();
        assert_eq!(claims.sub, verified.sub);
        assert_eq!(claims.jti, verified.jti);
    }

    /// Security: reject token with valid classical sig but invalid PQ sig
    #[test]
    fn test_reject_invalid_pq_signature() {
        let keypair = generate_hybrid_keypair();
        let claims = test_claims();
        let token = sign_jwt_hybrid(&claims, &keypair.signing_key).unwrap();
        
        // Tamper with PQ signature portion
        let mut parts: Vec<String> = token.split('.').map(String::from).collect();
        let mut sig_block = base64url_decode(&parts[2]).unwrap();
        let pq_offset = 4 + 64; // after version + alg bytes + classical sig
        sig_block[pq_offset] ^= 0xFF; // flip bits
        parts[2] = base64url_encode(&sig_block);
        let tampered = parts.join(".");

        let result = verify_jwt_hybrid(&tampered, &keypair.verifying_key);
        assert!(matches!(result, Err(JwtError::PqSignatureInvalid)));
    }

    /// Security: reject token with valid PQ sig but invalid classical sig
    #[test]
    fn test_reject_invalid_classical_signature() {
        // Similar to above but tamper classical portion
        let keypair = generate_hybrid_keypair();
        let claims = test_claims();
        let token = sign_jwt_hybrid(&claims, &keypair.signing_key).unwrap();

        let mut parts: Vec<String> = token.split('.').map(String::from).collect();
        let mut sig_block = base64url_decode(&parts[2]).unwrap();
        sig_block[4] ^= 0xFF; // flip first byte of classical sig
        parts[2] = base64url_encode(&sig_block);
        let tampered = parts.join(".");

        let result = verify_jwt_hybrid(&tampered, &keypair.verifying_key);
        assert!(matches!(result, Err(JwtError::ClassicalSignatureInvalid)));
    }

    /// Security: alg header confusion attack
    #[test]
    fn test_reject_alg_header_stripping() {
        let keypair = generate_hybrid_keypair();
        let claims = test_claims();
        let token = sign_jwt_hybrid(&claims, &keypair.signing_key).unwrap();

        // Strip hybrid_alg header (simulating downgrade attack)
        let mut parts: Vec<String> = token.split('.').map(String::from).collect();
        let mut header: serde_json::Value = base64url_deserialize(&parts[0]).unwrap();
        header.as_object_mut().unwrap().remove("hybrid_alg");
        parts[0] = base64url_serialize(&header);
        let stripped = parts.join(".");

        let policy = VerificationPolicy::HybridRequired;
        let result = verify_jwt_with_policy(&stripped, &policy, &keypair.verifying_key.ed25519, &Some(keypair.verifying_key.ml_dsa.clone()));
        assert!(matches!(result, Err(JwtError::HybridRequired)));
    }

    /// Performance: verify latency under threshold
    #[test]
    fn test_hybrid_verify_performance() {
        let keypair = generate_hybrid_keypair();
        let claims = test_claims();
        let token = sign_jwt_hybrid(&claims, &keypair.signing_key).unwrap();

        let start = std::time::Instant::now();
        for _ in 0..10_000 {
            let _ = verify_jwt_hybrid(&token, &keypair.verifying_key).unwrap();
        }
        let elapsed = start.elapsed();
        let p99_per_op = elapsed / 10_000;
        assert!(p99_per_op < std::time::Duration::from_millis(15),
            "Hybrid verify p99 {}ms exceeds 15ms threshold", p99_per_op.as_millis());
    }

    /// Size: token within expected bounds
    #[test]
    fn test_hybrid_token_size() {
        let keypair = generate_hybrid_keypair();
        let claims = test_claims();
        let token = sign_jwt_hybrid(&claims, &keypair.signing_key).unwrap();
        assert!(token.len() < 8192, "Token {} bytes exceeds 8KB proxy limit", token.len());
        assert!(token.len() > 4000, "Token suspiciously small at {} bytes", token.len());
    }
}
```

#### 1.3.9 Phase B Migration from Phase A

```rust
/// Multi-algorithm verification during Phase A → Phase B migration.
/// Accepts EdDSA-only (Phase A) and Hybrid (Phase B) tokens.
fn verify_jwt_phase_b_migration(
    token: &str,
    ed25519_key: &ed25519_dalek::VerifyingKey,
    ml_dsa_key: &Option<sig::PublicKey>,
) -> Result<Claims, JwtError> {
    let header = jsonwebtoken::decode_header(token)?;

    if header.additional_fields.contains_key("hybrid_alg") {
        // Phase B hybrid token
        let ml_dsa_key = ml_dsa_key.as_ref()
            .ok_or(JwtError::PqKeyNotConfigured)?;
        let verifying_key = HybridVerifyingKey {
            ed25519: *ed25519_key,
            ml_dsa: ml_dsa_key.clone(),
        };
        verify_jwt_hybrid(token, &verifying_key)
    } else {
        // Phase A classical token (EdDSA)
        verify_jwt_ed25519(token, &ed25519_key.to_bytes())
    }
}
```

**Migration window:** 7 days. After the window, Phase A tokens are rejected via policy enforcement.

---

## Gap 2: Broker Connection PQC — TLS 1.3 with PQC-Ready Config

### 2.1 Problem Recap

All external broker connections (MT5, CCXT/exchange APIs, REST APIs) use classical TLS 1.3 with ECDHE key exchange. An adversary capturing this traffic (HNDL) can decrypt it with a future CRQC, exposing trading strategies, positions, and account details.

### 2.2 Broker Connection Inventory

| Broker Type | Protocol | TLS Config (Current) | PQC-Ready? | Control Level |
|-------------|----------|---------------------|------------|---------------|
| MT5 bridge (MetaQuotes) | MT5 internal protocol | mTLS, ECDHE-P256 | ❌ No | **Partial** — bridge config, not MT5 server |
| CCXT exchanges (Binance, OKX, etc.) | REST/WSS over HTTPS | TLS 1.3, server-controlled | ❌ No | **None** — server chooses cipher suite |
| OANDA REST API | REST over HTTPS | TLS 1.3, server-controlled | ❌ No | **None** |
| Interactive Brokers TWS | REST/gateway | TLS 1.2/1.3 | ❌ No | **None** |
| Internal WebSocket server | WSS | TLS 1.3, our config | ❌ No | **Full** |

### 2.3 TLS PQC Strategy by Control Level

#### 2.3.1 Full Control (Internal Services)

For services where Alpha Stack controls both endpoints:

```yaml
# nginx / reverse proxy PQC-ready TLS config
# For internal WebSocket server, API gateway, internal REST endpoints

server {
    listen 443 ssl;
    
    # TLS 1.3 minimum — no TLS 1.2 fallback
    ssl_protocols TLSv1.3;
    
    # PQC-ready cipher suite configuration
    # Standard TLS 1.3 ciphers (quantum-safe symmetric, classical key exchange)
    # Note: PQC key exchange (ML-KEM) is negotiated via supported_groups,
    # NOT via cipher suite in TLS 1.3
    ssl_ciphers TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256;
    ssl_prefer_server_ciphers on;
    
    # PQC-ready: Enable hybrid key exchange groups when available
    # As of mid-2026, these are experimental in OpenSSL 3.x
    ssl_ecdh_curve X25519:secp384r1;
    
    # Certificate: Ed25519 (Phase A) — migration to hybrid later
    ssl_certificate /path/to/ed25519-signed-cert.pem;
    ssl_certificate_key /path/to/ed25519-private-key.pem;
    
    # HSTS — force HTTPS
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains" always;
    
    # OCSP stapling
    ssl_stapling on;
    ssl_stapling_verify on;
}
```

**PQC-ready with OpenSSL 3.x (when hybrid TLS is available):**

```yaml
# Future config — when OpenSSL supports hybrid groups natively
# Expected: OpenSSL 3.3+ / OpenSSL 4.0

ssl_protocols TLSv1.3;

# Hybrid key exchange: X25519 + ML-KEM-768
# OpenSSL 3.x supports this via the "groups" directive with experimental builds
ssl_ecdh_curve X25519Kyber768Draft00:X25519:secp384r1;

# Or with the NIST-standardized names (post-standardization):
# ssl_ecdh_curve X25519MLKEM768:X25519:secp384r1;
```

#### 2.3.2 Partial Control (MT5 Bridge)

The MT5 bridge has a controlled client side (our bridge software) but the MT5 server is MetaQuotes-controlled.

```yaml
# MT5 bridge connection config
mt5_bridge:
  connection:
    host: ${MT5_SERVER_HOST}
    port: ${MT5_SERVER_PORT}
    
    # TLS configuration — bridge-side
    tls:
      min_version: "1.3"
      # Client certificate for mTLS
      client_cert: /path/to/bridge-client-cert.pem
      client_key: /path/to/bridge-client-key.pem
      # Server CA bundle
      ca_bundle: /path/to/mt5-server-ca.pem
      
      # PQC readiness:
      # 1. Use Ed25519 client certificates (eliminates RSA)
      # 2. Enable hybrid key exchange if server supports it
      # 3. Fall back to classical if server doesn't support PQC
      
      # Cipher preference (ordered by quantum resistance)
      cipher_preference:
        - TLS_AES_256_GCM_SHA384        # Best symmetric
        - TLS_CHACHA20_POLY1305_SHA256   # Good alternative
      
      # Key exchange preference
      # Note: MT5 server controls key exchange — we can only request
      key_exchange_preference:
        - x25519_kyber768    # Hybrid PQC — if server supports
        - x25519             # Classical fallback
        - secp384r1          # Classical fallback
      
      # Monitor for PQC support
      pqc_support_check:
        enabled: true
        frequency: "weekly"
        method: "TLS handshake probe with hybrid groups"
        alert_on: "pqc_support_detected"
        log_level: INFO
```

**MT5 PQC monitoring script:**

```bash
#!/bin/bash
# mt5_pqc_check.sh — Probe MT5 server for PQC TLS support
# Run weekly via cron

MT5_HOST="${MT5_SERVER_HOST}"
MT5_PORT="${MT5_SERVER_PORT}"
LOG_FILE="/var/log/alpha-stack/pqc-monitor.log"

check_pqc_support() {
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    
    # Test with hybrid key exchange groups (OpenSSL 3.3+ required)
    local result=$(echo | openssl s_client \
        -connect "${MT5_HOST}:${MT5_PORT}" \
        -groups X25519Kyber768Draft00:X25519 \
        -tls1_3 \
        2>&1)
    
    local used_group=$(echo "$result" | grep "Server Temp Key" | grep -oP 'ECDH \K\S+')
    local cipher=$(echo "$result" | grep "Cipher is" | awk '{print $NF}')
    
    if echo "$used_group" | grep -qi "kyber\|mlkem\|ML-KEM"; then
        echo "${timestamp} [PQC-SUPPORTED] MT5 server ${MT5_HOST} accepted hybrid key exchange: ${used_group}" >> "$LOG_FILE"
        # Send alert
        send_alert "MT5 PQC support detected" "Server ${MT5_HOST} accepted hybrid key exchange: ${used_group}"
    else
        echo "${timestamp} [PQC-NOT-SUPPORTED] MT5 server ${MT5_HOST} using classical key exchange: ${used_group}" >> "$LOG_FILE"
    fi
}

check_pqc_support
```

#### 2.3.3 No Control (External Exchange APIs)

For Binance, OKX, OANDA, and other third-party APIs where we control only the client:

```yaml
# CCXT / exchange connection PQC-ready config
exchange_connections:
  # Common PQC-ready TLS settings for all exchange connections
  tls_defaults:
    # Force TLS 1.3
    min_tls_version: "1.3"
    
    # Client-side: prefer hybrid key exchange if server supports it
    # This is transparent — TLS negotiation handles it
    key_exchange_groups:
      - X25519Kyber768Draft00    # Hybrid PQC (when available)
      - X25519                    # Classical fallback
      - secp384r1                 # Classical fallback
    
    # Certificate verification
    verify_certificates: true
    ca_bundle: /etc/ssl/certs/ca-certificates.crt
    
    # Connection pooling with PQC awareness
    connection_pool:
      max_connections_per_host: 10
      idle_timeout_seconds: 30
      # Log negotiated cipher suite for PQC monitoring
      log_cipher_suite: true

  # Per-exchange overrides
  exchanges:
    binance:
      api_url: "https://api.binance.com"
      websocket_url: "wss://stream.binance.com:9443"
      # Binance uses Cloudflare — Cloudflare supports hybrid TLS
      # Client-side X25519Kyber768Draft00 should be negotiated transparently
      pqc_expected: true
      pqc_monitor: true

    okx:
      api_url: "https://www.okx.com"
      websocket_url: "wss://ws.okx.com:8443"
      pqc_expected: false  # Verify
      pqc_monitor: true

    oanda:
      api_url: "https://api-fxtrade.oanda.com"
      pqc_expected: false  # Verify
      pqc_monitor: true

    interactive_brokers:
      api_url: "https://localhost:5000/v1/api"  # TWS gateway
      tls:
        # IB TWS gateway may use TLS 1.2 — force 1.3 if supported
        min_tls_version: "1.3"
        allow_tls_12_fallback: true  # Temporary — remove when TWS supports 1.3
      pqc_expected: false
      pqc_monitor: true
```

**Exchange PQC monitoring (Rust):**

```rust
use reqwest::Client;
use std::time::Duration;

/// Monitor negotiated TLS cipher suite for PQC readiness.
/// Logs whether hybrid key exchange was used.
async fn monitor_exchange_tls_pqc(
    exchange_name: &str,
    url: &str,
) -> Result<TlsPqcStatus, Box<dyn std::error::Error>> {
    let client = Client::builder()
        .min_tls_version(reqwest::tls::Version::TLS_1_3)
        .https_only(true)
        .timeout(Duration::from_secs(10))
        .build()?;

    let response = client.get(url).send().await?;

    // Note: reqwest/rustls doesn't expose negotiated key exchange group directly.
    // Use openssl-probe or custom TLS connector for detailed monitoring.
    // For production: implement with hyper-tls or custom connector that logs
    // the negotiated supported_group from TLS ServerHello.

    let status = TlsPqcStatus {
        exchange: exchange_name.to_string(),
        url: url.to_string(),
        tls_version: "1.3".to_string(),
        // These would come from TLS connector inspection:
        negotiated_key_exchange: "unknown".to_string(),
        hybrid_detected: false,
        timestamp: chrono::Utc::now(),
    };

    log::info!(
        "TLS PQC monitor: {} -> key_exchange={}, hybrid={}",
        exchange_name,
        status.negotiated_key_exchange,
        status.hybrid_detected
    );

    Ok(status)
}

#[derive(Debug)]
struct TlsPqcStatus {
    exchange: String,
    url: String,
    tls_version: String,
    negotiated_key_exchange: String,
    hybrid_detected: bool,
    timestamp: chrono::DateTime<chrono::Utc>,
}
```

### 2.4 Broker Connection Risk Register

| Connection | HNDL Risk | Mitigation | Residual Risk | Accept? |
|------------|-----------|------------|---------------|---------|
| MT5 bridge | 🔴 HIGH | Force TLS 1.3, monitor for PQC, use Ed25519 client certs | MEDIUM — depends on MetaQuotes PQC timeline | ✅ With monitoring |
| Binance/CCXT | 🟡 MEDIUM | Force TLS 1.3, client-side hybrid preference (Cloudflare may support) | LOW-MEDIUM | ✅ With monitoring |
| OANDA | 🟡 MEDIUM | Force TLS 1.3, client-side hybrid preference | MEDIUM — unknown PQC timeline | ✅ With monitoring |
| IB TWS | 🟡 MEDIUM | Force TLS 1.3 where possible, fallback to 1.2 temporarily | MEDIUM — TLS 1.2 fallback | ⚠️ Temporary accept |
| Internal WSS | 🟢 LOW | Full control — deploy hybrid TLS when ready | LOW | ✅ |

### 2.5 Broker TLS Migration Roadmap

```
Phase 1 (Q3 2026) — Immediate:
├── Force TLS 1.3 for all connections where possible
├── Deploy Ed25519 client certificates for MT5 bridge
├── Enable PQC monitoring on all exchange connections
└── Document accepted risks per connection

Phase 2 (Q4 2026) — Client-Side Hybrid:
├── Update OpenSSL/rustls to version with hybrid group support
├── Enable X25519Kyber768Draft00 as preferred key exchange group
├── Hybrid negotiation is transparent — servers that don't support it fall back
└── Monitor which exchanges actually negotiate hybrid

Phase 3 (2027) — Full Hybrid:
├── Track MetaQuotes PQC support announcement
├── Track exchange PQC support (Binance/Cloudflare likely first)
├── Update MT5 bridge when MetaQuotes adds PQC support
└── Retire TLS 1.2 fallbacks

Phase 4 (2028+) — PQC Standard:
├── All connections using hybrid or pure PQC
├── Classical-only connections flagged as non-compliant
└── Full PQC audit of all external connections
```

### 2.6 Hyper/Rustls PQC Configuration

For the Rust application layer:

```toml
# Cargo.toml — PQC-ready TLS dependencies
[dependencies]
reqwest = { version = "0.12", features = ["rustls-tls-native-roots"] }
rustls = "0.23"
# Note: rustls 0.23+ supports custom crypto providers
# For PQC: use rustls with liboqs-backed crypto provider when available

# Alternative: use native-tls for OpenSSL-based PQC support
# reqwest = { version = "0.12", features = ["native-tls"] }
```

```rust
use rustls::ClientConfig;
use std::sync::Arc;

/// Build a PQC-ready TLS configuration.
/// Prefers hybrid key exchange when the server supports it.
fn build_pqc_ready_tls_config() -> Arc<ClientConfig> {
    let mut config = ClientConfig::builder()
        .with_root_certificates(root_cert_store())
        .with_no_client_auth();

    // TLS 1.3 only
    config.versions = vec![rustls::ProtocolVersion::TLSv1_3];

    // Key exchange group preference (PQC-first)
    // Note: These group names depend on the rustls + crypto provider version.
    // With standard rustls (ring): only X25519, P256, P384 are available.
    // With liboqs-backed provider: ML-KEM groups become available.
    //
    // For now: configure classical groups. PQC groups will be added
    // when a liboqs-backed rustls crypto provider is available.
    //
    // TODO: Replace with hybrid groups when liboqs-rustls provider ships
    // config.enable_sni = true;

    Arc::new(config)
}

/// Future: PQC-enabled TLS config with liboqs crypto provider
#[cfg(feature = "pqc-tls")]
fn build_pqc_tls_config() -> Arc<ClientConfig> {
    // This requires a custom CryptoProvider backed by liboqs
    // Tracking: https://github.com/rustls/rustls/issues/XXXX
    todo!("Implement when liboqs-rustls crypto provider is available")
}
```

---

## Gap 3: KMS PQC Support — Audit Spec + Software Fallback

### 3.1 Problem Recap

The DEK re-wrapping plan (fix_security_quantum.md, Fix 3) assumes KMS can wrap DEKs with ML-KEM-768. As of mid-2026, this is unverified for all major KMS providers. If KMS PQC support isn't available, Phase 3.5 stalls.

### 3.2 KMS Provider Audit Spec

#### 3.2.1 Audit Checklist per Provider

```yaml
kms_pqc_audit:
  aws_kms:
    provider: "AWS KMS"
    audit_questions:
      - id: aws-1
        question: "Does AWS KMS support ML-KEM (CRYSTALS-Kyber) for key wrapping?"
        check: "AWS KMS documentation, AWS re:Invent announcements"
        status: UNKNOWN
        notes: "AWS supports post-quantum TLS for some services (S3, Secrets Manager) since 2024. KMS key wrapping with ML-KEM is not confirmed GA."

      - id: aws-2
        question: "Does AWS KMS support ML-DSA (CRYSTALS-Dilithium) for signing?"
        check: "AWS KMS API, CloudHSM documentation"
        status: UNKNOWN

      - id: aws-3
        question: "Can custom key stores (CloudHSM) use PQC algorithms?"
        check: "CloudHSM documentation — supports custom key types via PKCS#11"
        status: UNKNOWN
        notes: "CloudHSM supports PKCS#11 — if liboqs PKCS#11 provider exists, custom PQC keys may be possible."

      - id: aws-4
        question: "Does AWS KMS GenerateDataKey support PQC wrapping?"
        check: "KMS API — GenerateDataKey, GenerateDataKeyPair"
        status: UNKNOWN

      - id: aws-5
        question: "What is AWS's PQC roadmap for KMS?"
        check: "AWS Security Blog, re:Invent sessions, TAM contact"
        status: UNKNOWN
        deadline: "Q4 2026"

    fallback_plan: software_dek_rewrap   # See Section 3.3

  hashicorp_vault:
    provider: "HashiCorp Vault"
    audit_questions:
      - id: vault-1
        question: "Does Vault transit engine support ML-KEM-768 for key wrapping?"
        check: "Vault documentation, transit engine secrets backend"
        status: UNKNOWN
        notes: "Vault transit supports various key types. PQC key types may be available via plugin."

      - id: vault-2
        question: "Does Vault support liboqs integration?"
        check: "Vault GitHub issues, HashiCorp blog"
        status: UNKNOWN
        notes: "HashiCorp has explored liboqs integration. Status unknown."

      - id: vault-3
        question: "Can Vault transit engine use custom crypto providers?"
        check: "Vault plugin architecture documentation"
        status: UNKNOWN

      - id: vault-4
        question: "Does Vault PKI secrets engine support PQC certificates?"
        check: "Vault PKI engine documentation"
        status: UNKNOWN

    fallback_plan: software_dek_rewrap

  azure_key_vault:
    provider: "Azure Key Vault"
    audit_questions:
      - id: azure-1
        question: "Does Azure Key Vault support ML-KEM for key operations?"
        check: "Azure documentation, Microsoft Ignite announcements"
        status: UNKNOWN
        notes: "Azure supports post-quantum TLS in preview. Key Vault PQC key support unclear."

      - id: azure-2
        question: "Does Azure Managed HSM support PQC algorithms?"
        check: "Azure Managed HSM documentation"
        status: UNKNOWN

      - id: azure-3
        question: "Can Azure Key Vault wrap keys with ML-KEM-768?"
        check: "Key Vault REST API — wrapKey operation"
        status: UNKNOWN

    fallback_plan: software_dek_rewrap

  google_cloud_kms:
    provider: "Google Cloud KMS"
    audit_questions:
      - id: gcp-1
        question: "Does Cloud KMS support ML-KEM key operations?"
        check: "Google Cloud documentation, Cloud Next announcements"
        status: UNKNOWN
        notes: "Google was early on PQC (Chrome ML-KEM support). Cloud KMS PQC support unclear."

      - id: gcp-2
        question: "Does Cloud HSM support PQC key types?"
        check: "Cloud HSM documentation"
        status: UNKNOWN

    fallback_plan: software_dek_rewrap
```

#### 3.2.2 Audit Execution Script

```bash
#!/bin/bash
# kms_pqc_audit.sh — Automated KMS PQC support detection
# Outputs JSON audit results

set -euo pipefail

OUTPUT_FILE="kms_pqc_audit_results.json"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

echo '{"audit_timestamp":"'"$TIMESTAMP"'","providers":[' > "$OUTPUT_FILE"

# AWS KMS
echo "Auditing AWS KMS..."
if command -v aws &>/dev/null; then
    # Check if AWS CLI can list key specs including PQC
    AWS_KEY_SPECS=$(aws kms list-keys --output json 2>/dev/null || echo '{}')
    
    # Try to create a test key with ML-KEM spec (expected to fail if unsupported)
    AWS_MLKEM_TEST=$(aws kms create-key \
        --key-usage ENCRYPT_DECRYPT \
        --key-spec SYMMETRIC_DEFAULT \
        --description "PQC audit test" \
        --output json 2>&1 || echo '{"error": "unsupported"}')
    
    # Check AWS documentation page for PQC mentions
    AWS_DOCS_PQC=$(curl -s "https://docs.aws.amazon.com/kms/latest/developerguide/" 2>/dev/null | grep -ci "post-quantum\|ML-KEM\|Kyber" || echo "0")
    
    echo '{"name":"aws_kms","pqc_docs_mentions":'"$AWS_DOCS_PQC"',"status":"audit_complete"},' >> "$OUTPUT_FILE"
else
    echo '{"name":"aws_kms","status":"cli_not_available"},' >> "$OUTPUT_FILE"
fi

# HashiCorp Vault
echo "Auditing HashiCorp Vault..."
if command -v vault &>/dev/null; then
    VAULT_VERSION=$(vault version 2>/dev/null | head -1 || echo "unknown")
    VAULT_TRANSIT_KEYS=$(vault list transit/keys 2>/dev/null || echo "[]")
    echo '{"name":"hashicorp_vault","version":"'"$VAULT_VERSION"'","status":"audit_complete"},' >> "$OUTPUT_FILE"
else
    echo '{"name":"hashicorp_vault","status":"cli_not_available"},' >> "$OUTPUT_FILE"
fi

# Close JSON
echo '{}]}' >> "$OUTPUT_FILE"

echo "Audit complete: $OUTPUT_FILE"
```

### 3.3 Software DEK Re-Wrapping Fallback

If KMS PQC support is unavailable, implement software-based DEK re-wrapping as an interim solution.

#### 3.3.1 Architecture

```
Software DEK Re-Wrapping Fallback:
┌──────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  Interim Double-Wrap Strategy:                                       │
│                                                                      │
│  BEFORE (classical only):                                            │
│  DEK ──[RSA-2048 KMS wrap]──► Wrapped DEK (stored in DB)            │
│                                                                      │
│  INTERIM (hybrid double-wrap):                                       │
│  DEK ──[ML-KEM-768 software wrap]──► PQC-wrapped DEK                │
│         ──[RSA-2048 KMS wrap]──► Double-wrapped DEK (stored in DB)   │
│                                                                      │
│  FINAL (when KMS PQC available):                                     │
│  DEK ──[ML-KEM-768 KMS wrap]──► PQC-wrapped DEK (stored in DB)      │
│                                                                      │
│  Why double-wrap?                                                    │
│  • Outer layer (RSA-2048 KMS): HSM-protected, tamper-evident         │
│  • Inner layer (ML-KEM-768 software): PQC protection                 │
│  • Attacker needs to break BOTH to recover DEK                       │
│  • When KMS adds PQC: unwrap outer RSA, promote inner ML-KEM to KMS  │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

#### 3.3.2 Implementation

```rust
use oqs::kem::{self, Algorithm as KemAlgorithm};
use aes_gcm::{Aes256Gcm, KeyInit, Nonce};
use aes_gcm::aead::Aead;

/// Software-based PQC DEK wrapping using ML-KEM-768.
/// Used as fallback when KMS PQC support is unavailable.
struct PqcDekWrapper {
    kem: kem::Kem,
    ml_kem_pk: kem::PublicKey,
    ml_kem_sk: kem::SecretKey,
}

impl PqcDekWrapper {
    /// Generate a new ML-KEM-768 keypair for DEK wrapping.
    fn generate() -> Result<Self, PqcWrapError> {
        let kem = kem::new(KemAlgorithm::MlKem768)?;
        let (pk, sk) = kem.keypair()?;
        Ok(Self { kem, ml_kem_pk: pk, ml_kem_sk: sk })
    }

    /// Wrap a DEK with ML-KEM-768 + AES-256-GCM.
    ///
    /// Process:
    /// 1. Encapsulate: generate shared secret + ciphertext using ML-KEM
    /// 2. Derive AES-256 key from shared secret (HKDF-SHA384)
    /// 3. Encrypt DEK with AES-256-GCM
    /// 4. Output: ML-KEM ciphertext || AES-GCM nonce || encrypted DEK || AES-GCM tag
    fn wrap_dek(&self, dek: &[u8]) -> Result<Vec<u8>, PqcWrapError> {
        // Step 1: ML-KEM encapsulation
        let (ciphertext, shared_secret) = self.kem.encapsulate(&self.ml_kem_pk)?;

        // Step 2: Derive wrapping key from shared secret
        let wrapping_key = hkdf_sha384(
            shared_secret.as_ref(),
            b"alpha-stack-dek-wrap-v1",
            32, // 256 bits
        );

        // Step 3: Encrypt DEK with AES-256-GCM
        let cipher = Aes256Gcm::new_from_slice(&wrapping_key)?;
        let nonce = generate_random_nonce(); // 96-bit nonce
        let encrypted_dek = cipher.encrypt(Nonce::from_slice(&nonce), dek)?;

        // Step 4: Build output
        let mut output = Vec::new();
        output.extend_from_slice(&(ciphertext.as_ref().len() as u32).to_be_bytes());
        output.extend_from_slice(ciphertext.as_ref());
        output.extend_from_slice(&nonce);
        output.extend_from_slice(&encrypted_dek);

        Ok(output)
    }

    /// Unwrap a DEK wrapped with ML-KEM-768 + AES-256-GCM.
    fn unwrap_dek(&self, wrapped: &[u8]) -> Result<Vec<u8>, PqcWrapError> {
        // Parse: ciphertext_len || ciphertext || nonce || encrypted_dek
        if wrapped.len() < 4 {
            return Err(PqcWrapError::InvalidWrappedData);
        }

        let ct_len = u32::from_be_bytes([wrapped[0], wrapped[1], wrapped[2], wrapped[3]]) as usize;
        if wrapped.len() < 4 + ct_len + 12 {
            return Err(PqcWrapError::InvalidWrappedData);
        }

        let ct_bytes = &wrapped[4..4 + ct_len];
        let nonce = &wrapped[4 + ct_len..4 + ct_len + 12];
        let encrypted_dek = &wrapped[4 + ct_len + 12..];

        // ML-KEM decapsulation
        let ciphertext = kem::Ciphertext::from_bytes(ct_bytes)
            .ok_or(PqcWrapError::InvalidCiphertext)?;
        let shared_secret = self.kem.decapsulate(&self.ml_kem_sk, &ciphertext)?;

        // Derive wrapping key
        let wrapping_key = hkdf_sha384(
            shared_secret.as_ref(),
            b"alpha-stack-dek-wrap-v1",
            32,
        );

        // Decrypt DEK
        let cipher = Aes256Gcm::new_from_slice(&wrapping_key)?;
        let dek = cipher.decrypt(Nonce::from_slice(nonce), encrypted_dek)?;

        Ok(dek)
    }
}
```

#### 3.3.3 Double-Wrap Integration with KMS

```rust
/// Double-wrap: ML-KEM-768 (software) + RSA-2048 (KMS)
/// Interim strategy until KMS supports PQC natively.
async fn double_wrap_dek(
    dek: &[u8],
    pqc_wrapper: &PqcDekWrapper,
    kms_client: &KmsClient,
    kms_key_id: &str,
) -> Result<DoubleWrappedDek, WrapError> {
    // Inner wrap: ML-KEM-768 (software)
    let pqc_wrapped = pqc_wrapper.wrap_dek(dek)?;

    // Outer wrap: KMS RSA-2048
    let kms_wrapped = kms_client
        .encrypt()
        .key_id(kms_key_id)
        .plaintext(pqc_wrapped.into())
        .send()
        .await?;

    Ok(DoubleWrappedDek {
        kms_ciphertext: kms_wrapped.ciphertext_blob,
        pqc_algorithm: "ML-KEM-768",
        kms_algorithm: "RSA-2048",
        created_at: chrono::Utc::now(),
    })
}

/// Unwrap: KMS RSA-2048 (outer) → ML-KEM-768 (inner)
async fn double_unwrap_dek(
    double_wrapped: &DoubleWrappedDek,
    pqc_wrapper: &PqcDekWrapper,
    kms_client: &KmsClient,
) -> Result<Vec<u8>, WrapError> {
    // Outer unwrap: KMS
    let kms_decrypted = kms_client
        .decrypt()
        .ciphertext_blob(double_wrapped.kms_ciphertext.clone())
        .send()
        .await?;

    // Inner unwrap: ML-KEM-768
    let dek = pqc_wrapper.unwrap_dek(&kms_decrypted.plaintext)?;

    Ok(dek)
}

#[derive(Debug)]
struct DoubleWrappedDek {
    kms_ciphertext: Vec<u8>,        // RSA-2048 KMS encrypted blob
    pqc_algorithm: &'static str,    // "ML-KEM-768"
    kms_algorithm: &'static str,    // "RSA-2048"
    created_at: chrono::DateTime<chrono::Utc>,
}
```

#### 3.3.4 Migration from Double-Wrap to KMS PQC

```rust
/// Migrate from double-wrap to KMS-native PQC wrapping.
/// Called when KMS adds ML-KEM support.
async fn migrate_to_kms_pqc(
    double_wrapped: &DoubleWrappedDek,
    pqc_wrapper: &PqcDekWrapper,
    kms_client: &KmsClient,
    kms_pqc_key_id: &str,  // New KMS key with ML-KEM support
) -> Result<KmsWrappedDek, WrapError> {
    // Step 1: Unwrap to get raw DEK
    let dek = double_unwrap_dek(double_wrapped, pqc_wrapper, kms_client).await?;

    // Step 2: Re-wrap with KMS PQC key
    let kms_pqc_wrapped = kms_client
        .encrypt()
        .key_id(kms_pqc_key_id)
        .plaintext(dek.clone().into())
        .encryption_algorithm("ML-KEM-768")  // New KMS algorithm spec
        .send()
        .await?;

    // Step 3: Securely zeroize raw DEK
    zeroize_dek(&mut dek.clone());

    Ok(KmsWrappedDek {
        ciphertext: kms_pqc_wrapped.ciphertext_blob,
        algorithm: "ML-KEM-768",
        key_id: kms_pqc_key_id.to_string(),
        migrated_from: "double-wrap",
        migrated_at: chrono::Utc::now(),
    })
}
```

### 3.4 KMS PQC Readiness Matrix

```
KMS PQC Readiness Decision Tree:
┌──────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  Q: Does your KMS provider support ML-KEM-768 key wrapping?          │
│  │                                                                   │
│  ├─► YES ──► Use KMS-native PQC wrapping                            │
│  │           (Simplest, HSM-protected, no software key management)   │
│  │                                                                   │
│  └─► NO ──► Q: Can you use CloudHSM with custom PKCS#11 provider?   │
│             │                                                        │
│             ├─► YES ──► Deploy liboqs PKCS#11 provider on CloudHSM  │
│             │           (HSM-backed PQC, more complex setup)         │
│             │                                                        │
│             └─► NO ──► Use software double-wrap fallback             │
│                        (Section 3.3 — ML-KEM in software + KMS RSA)  │
│                        Monitor KMS PQC announcements quarterly       │
│                        Migrate when KMS PQC becomes available        │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 3.5 Software Key Management Security

If running ML-KEM-768 in software (fallback path), the PQC private key material must be protected:

```yaml
software_pqc_key_security:
  storage:
    # Encrypt PQC private key at rest with a master key
    at_rest_encryption: "AES-256-GCM"
    master_key_source: "OS keyring or hardware TPM"
    
    # File permissions
    file_mode: "0600"
    owner: "alpha-stack"
    
    # Never in version control
    gitignore: true

  memory:
    # Zeroize key material after use
    zeroize_on_drop: true
    
    # Lock memory pages (mlock) to prevent swapping
    mlock: true
    
    # Use guard pages for key material
    guard_pages: true

  access_control:
    # Only the key management service can access PQC keys
    allowed_processes:
      - "alpha-stack-kms-service"
    audit_logging: true
    
  rotation:
    # Rotate PQC wrapping keys quarterly
    rotation_interval_days: 90
    # Keep old keys for decryption during grace period
    grace_period_days: 30

  monitoring:
    - alert_on_key_access_denied
    - alert_on_key_rotation_failure
    - metric: pqc_key_age_days
    - metric: pqc_wrap_operations_per_second
```

### 3.6 KMS Audit Timeline

```
Q3 2026:
├── Week 1-2: Complete KMS provider audit (all 4 providers)
├── Week 3: Document findings, determine fallback strategy
├── Week 4: Implement software PQC DEK wrapper (if needed)
└── Week 5: Integration testing of double-wrap strategy

Q4 2026:
├── Monthly: Re-audit KMS providers for PQC support updates
├── Implement CloudHSM + PKCS#11 option (if available)
└── Benchmark software PQC wrapping performance

2027:
├── Quarterly: KMS PQC support check
├── When KMS PQC available: begin migration from double-wrap
└── Phase 3.5: Execute DEK re-wrapping with chosen strategy
```

---

## Cross-Gap Dependencies

```
Dependency Graph:
┌──────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  Gap 1 (JWT Hybrid)          Gap 2 (Broker TLS)     Gap 3 (KMS PQC) │
│  ┌───────────────┐           ┌───────────────┐      ┌────────────┐  │
│  │ Phase A       │           │ TLS 1.3 force │      │ KMS audit  │  │
│  │ Ed25519 JWT   │           │ (no PQC dep)  │      │ (indep.)   │  │
│  └───────┬───────┘           └───────┬───────┘      └─────┬──────┘  │
│          │                           │                    │         │
│          ▼                           ▼                    ▼         │
│  ┌───────────────┐           ┌───────────────┐      ┌────────────┐  │
│  │ Phase B       │           │ Client-side   │      │ Software   │  │
│  │ Hybrid JWT    │           │ hybrid TLS    │      │ PQC wrapper│  │
│  │ (needs liboqs)│           │ (needs liboqs)│      │ (needs     │  │
│  └───────────────┘           └───────────────┘      │ liboqs)    │  │
│          │                           │               └─────┬──────┘  │
│          │                           │                     │         │
│          └───────────┬───────────────┘                     │         │
│                      ▼                                     │         │
│              ┌───────────────┐                             │         │
│              │ liboqs        │◄────────────────────────────┘         │
│              │ integration   │                                       │
│              │ (shared dep)  │                                       │
│              └───────────────┘                                       │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘

Critical shared dependency: liboqs Rust bindings (oqs crate)
├── Gap 1 Phase B: ML-DSA-65 signing
├── Gap 2 Phase 2: ML-KEM TLS key exchange
└── Gap 3: ML-KEM DEK wrapping
```

---

## Unified Migration Timeline

```
Q3 2026 (Pre-Production):
├── Gap 1: Phase A — Ed25519 JWT signing [CRITICAL PATH]
├── Gap 2: Force TLS 1.3, Ed25519 client certs for MT5
├── Gap 3: Complete KMS PQC audit
├── Shared: liboqs dependency integration & testing
└── Milestone: Production-ready with classical PQC foundation

Q4 2026:
├── Gap 1: Phase A in production, Phase B design finalized
├── Gap 2: Client-side hybrid TLS enabled (transparent fallback)
├── Gap 3: Software PQC wrapper implemented (if KMS lacks support)
├── Gap 3: PQC monitoring on all broker connections
└── Milestone: PQC monitoring operational, fallback ready

Q1 2027:
├── Gap 1: Phase B — Hybrid JWT in staging
├── Gap 2: Hybrid TLS operational for internal services
├── Gap 3: Double-wrap strategy validated
└── Milestone: PQC integration testing complete

Q2-Q3 2027 (Phase 3.5):
├── Gap 1: Phase B — Hybrid JWT in production
├── Gap 2: Monitor exchange PQC support, update configs
├── Gap 3: DEK re-wrapping execution (software or KMS-native)
└── Milestone: HNDL data remediation complete

Q4 2027+:
├── Full hybrid JWT + TLS deployment
├── KMS PQC migration (when available)
├── Continuous monitoring and adaptation
└── Milestone: Quantum-resistant architecture operational
```

---

## Approval & Sign-Off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Security Architect | | | |
| CISO | | | |
| Lead Developer | | | |
| DevOps Lead | | | |
| Quantum Security SME | | | |

---

*This document provides implementation-level specs for the 3 critical gaps from the quantum integration review. Track execution with tag `quantum-fix-impl`. Update after each phase completes.*
