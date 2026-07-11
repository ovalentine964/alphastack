# Alpha Stack — Authentication Security Review

> **Reviewer:** Security Review Agent — Authentication  
> **Date:** 2026-07-11  
> **Scope:** Authentication architecture, session management, credential handling, 2FA, biometrics, password security  
> **Documents Reviewed:** `architecture_security.md`, `architecture_ui_desktop.md`, `architecture_ui_mobile.md`  
> **Status:** `architecture_broker_connection.md` and `architecture_ui_web.md` were **not found** — findings may be incomplete for broker-specific auth flows and web client auth.

---

## Executive Summary

Alpha Stack's authentication architecture is **well-designed at the blueprint level** — it follows zero-trust principles, uses modern cryptographic primitives, and demonstrates defense-in-depth thinking. However, this review identifies **14 findings** across Critical, High, Medium, and Low severity. Most are implementation-level risks and gaps in specification rather than fundamental design flaws.

| Severity | Count | Summary |
|----------|-------|---------|
| 🔴 **Critical** | 2 | Refresh token storage on web; missing token binding enforcement |
| 🟠 **High** | 4 | TOTP secret caching in memory; partial_token design; biometric fallback gap; session fixation risk |
| 🟡 **Medium** | 5 | JWT claim leakage; backup code entropy; idle timeout gaps; CSRF-JWT interaction; device fingerprint weakness |
| 🟢 **Low** | 3 | Password max age policy; TOTP window tolerance; audit log gaps |

---

## 1. JWT Implementation Review

### 1.1 Architecture Assessment

The JWT design uses **RS256 (RSA + SHA-256)** with asymmetric keys, which is correct for a multi-service architecture:

- ✅ Asymmetric signing (private key on auth server, public key on services)
- ✅ `kid` header for key rotation support
- ✅ JWKS endpoint for public key distribution
- ✅ 15-minute access token lifetime
- ✅ RSA-4096 key size
- ✅ 90-day rotation with 30-day grace period
- ✅ Emergency rotation capability

### 1.2 Findings

#### 🔴 CRITICAL — F-01: Refresh Token Storage Not Specified for Web

**Issue:** The architecture specifies a 7-day refresh token but does **not** clearly define how refresh tokens are stored on the **web client**. The document mentions `httpOnly` cookies in the penetration test acceptance criteria ("session token theft — expect: httpOnly, Secure, SameSite=Strict") but does not mandate this as an implementation requirement.

**Risk:** If refresh tokens are stored in `localStorage` or accessible JavaScript variables, they are vulnerable to XSS exfiltration. Given the trading platform's attack surface (WebSocket connections, third-party chart libraries, potential CDN compromise), this is a critical exposure.

**Recommendation:**
- **Mandate** `httpOnly`, `Secure`, `SameSite=Strict` cookies for refresh tokens on web
- Access tokens should be in memory only (never persisted)
- Document this as a **non-negotiable security requirement** in the implementation spec
- Add a pre-launch checklist item: "Verify no tokens in localStorage/sessionStorage"

#### 🟠 HIGH — F-02: Refresh Token Rotation — Race Condition Not Addressed

**Issue:** The spec states "Refresh token rotation → old token invalidated (one-time use)" but does not address the **race condition** when multiple tabs or devices attempt to refresh simultaneously using the same token.

**Risk:** Legitimate users get logged out when two tabs try to refresh at nearly the same time. The first succeeds and invalidates the token; the second fails and triggers re-authentication. This is a known issue with strict rotation.

**Recommendation:**
- Implement a **grace window** (e.g., 10 seconds) where the old refresh token remains valid after rotation
- Store a token family ID; if a revoked token within the grace window is used, issue a new token but flag the session for monitoring
- If a revoked token *outside* the grace window is used, revoke the entire token family (potential theft)

#### 🟡 MEDIUM — F-03: JWT Claims May Leak Sensitive Data

**Issue:** The access token payload includes `email`, `tier`, `roles`, and `email_verified`. While JWTs are signed, they are **not encrypted** — anyone who intercepts the token can read these claims.

**Risk:** In a shared-computer scenario, browser history, proxy logs, or developer tools could expose user email and account tier.

**Recommendation:**
- Use opaque subject identifiers (`sub`) only; resolve email/roles server-side
- If claims must be in the token, consider **JWE** (encrypted JWT) for sensitive fields
- At minimum, remove `email` from the access token — the `sub` UUID is sufficient

#### 🟡 MEDIUM — F-04: IP Fingerprint in JWT — False Positives

**Issue:** The JWT includes `ip_hash` (SHA-256 of client IP). This is validated on every request.

**Risk:** Mobile users on cellular networks, users behind corporate NATs, and VPN users change IPs frequently. Strict IP binding will cause frequent, frustrating re-authentications.

**Recommendation:**
- Use IP fingerprinting as a **risk signal**, not a hard validation
- Combine with device fingerprint and behavioral signals for anomaly detection
- Only enforce re-authentication when IP changes *and* other risk signals are elevated

---

## 2. Two-Factor Authentication (TOTP) Review

### 2.1 Architecture Assessment

The TOTP implementation follows RFC 6238 and includes several good practices:

- ✅ 256-bit CSPRNG for secret generation
- ✅ Secrets encrypted with user-derived key (AES-256-GCM)
- ✅ ±1 window tolerance (±30 seconds) — standard
- ✅ Backup codes generated (8 single-use)
- ✅ Backup codes hashed with Argon2id before storage
- ✅ Backup codes shown once, never stored in plaintext
- ✅ Rate limiting on 2FA verification (5 attempts / 15 min)

### 2.2 Findings

#### 🟠 HIGH — F-05: TOTP Secret Cached in Memory During Encryption/Decryption

**Issue:** The `FieldEncryptor` class caches DEK keys in `self._key_cache` (in-memory dictionary). While TOTP secrets are encrypted at rest, the **plaintext TOTP secret exists in memory** during verification operations and the DEK is cached indefinitely.

**Risk:** Memory dump attacks (e.g., crash dumps, cold boot, process introspection) could expose TOTP secrets. The MT5 bridge section explicitly disables crash dumps, but the auth server does not have the same protection specified.

**Recommendation:**
- Zero TOTP secret from memory immediately after verification (use secure memory patterns like Rust's `Zeroize` or Python's `mmap` + `mlock`)
- Implement DEK cache TTL (e.g., 5 minutes) rather than indefinite caching
- Disable core dumps on the auth server process
- Apply the same `BrokerCredentials` zeroization pattern to TOTP secrets

#### 🟠 HIGH — F-06: Partial Token in 2FA Flow — Design Risk

**Issue:** The 2FA flow returns a `partial_token` after password verification, which is then exchanged for a full token after TOTP verification. The spec does not define:
- What the `partial_token` grants access to
- Its expiration time
- How it's stored/transmitted
- Whether it's bound to the same session

**Risk:** If the `partial_token` is overly permissive, has a long TTL, or is not properly scoped, an attacker who captures the password but not the 2FA code could still access limited resources.

**Recommendation:**
- Define `partial_token` scope explicitly: **zero access** to any resource except the `/auth/2fa/verify` endpoint
- Set TTL to **5 minutes maximum**
- Bind to the same IP and device fingerprint as the initial login attempt
- Treat it as a single-use nonce, not a JWT

#### 🟡 MEDIUM — F-07: Backup Code Entropy Is Low

**Issue:** Backup codes are 8 characters, alphanumeric. The spec says "excluding ambiguous chars" but doesn't specify the character set size.

**Risk:** If the character set is ~32 chars (alphanumeric minus ambiguous), 8 characters gives ~2^40 combinations. With the 5-attempt-per-15-min rate limit, brute force is impractical. However, the entropy is still lower than recommended for security-critical codes.

**Recommendation:**
- Increase to **10 characters** minimum, or use a **6-digit numeric + 4-char alpha** format (more memorable)
- Consider using the **Crockford Base32** encoding (32 chars, unambiguous)
- Document the exact character set and resulting entropy

---

## 3. Biometric Authentication Review

### 3.1 Architecture Assessment

#### Desktop (Tauri)
- ✅ Platform-native biometric APIs (Windows Hello, Touch ID, Face ID)
- ✅ Biometric unlocks OS Keyring — credentials never in app memory
- ✅ Silent re-auth via refresh token from keyring

#### Mobile (Flutter)
- ✅ `local_auth` package with biometric + PIN fallback
- ✅ `FlutterSecureStorage` with platform-specific encryption (Android Keystore, iOS Keychain)
- ✅ Android options: RSA ECB OAEP + AES GCM
- ✅ iOS options: `first_unlock_this_device`, non-synchronizable
- ✅ Tiered authentication levels (view vs. trade vs. settings)
- ✅ Re-authentication threshold (5-minute inactivity)
- ✅ Lockout handling

### 3.2 Findings

#### 🟠 HIGH — F-08: Biometric Fallback to PIN May Bypass Security Intent

**Issue:** The mobile biometric service sets `biometricOnly: false`, meaning a device PIN/password can substitute for biometric authentication.

**Risk:** If the user's primary intent is biometric-only security (e.g., protecting against shoulder surfing, or scenarios where someone knows the device PIN), the PIN fallback undermines this. For a **financial trading application**, biometric-only should be an option.

**Recommendation:**
- Add a `biometricOnly: true` option in settings for users who want stricter security
- Document the trade-off: biometric-only prevents PIN fallback but may lock users out if biometrics fail
- For trade execution, consider requiring biometric regardless of PIN availability

#### 🟡 MEDIUM — F-09: Quick View Mode May Expose Sensitive Data

**Issue:** The mobile app offers a "Quick View" mode that shows limited dashboard access without authentication. The spec says "View prices/dashboard → No auth needed (quick view)" but doesn't define what data is excluded.

**Risk:** If Quick View shows account balance, open positions, or P&L, it exposes financial data to anyone with physical device access.

**Recommendation:**
- Quick View should show **market data only** (prices, charts) — no account-specific data
- No balance, no P&L, no positions, no signals
- Require authentication for any data tied to the user's account
- Add a clear "Sign in for full access" indicator

---

## 4. Session Management Review

### 4.1 Architecture Assessment

The session management design includes several strong controls:

- ✅ Device binding (`device_id` in session)
- ✅ Per-platform idle timeouts (web: 15min, desktop: 4hr, mobile: 30min)
- ✅ Maximum 10 sessions per user
- ✅ Session invalidation on password change, 2FA change, "logout all"
- ✅ Refresh token hashed with Argon2id before storage
- ✅ Session data model includes `revoke_reason`

### 4.2 Findings

#### 🟠 HIGH — F-10: Session Fixation Risk in 2FA Flow

**Issue:** The 2FA flow returns a `partial_token` that is then upgraded to a full session. If the session ID is established *before* 2FA completion and not regenerated, an attacker who can set a session cookie before the victim authenticates could hijack the session after 2FA.

**Risk:** Classic session fixation attack. The attacker pre-sets a session identifier, the victim authenticates and 2FA-verifies using that session, and the attacker now has access.

**Recommendation:**
- **Regenerate session ID** after every authentication step (password verify, 2FA verify)
- Never carry a session identifier across authentication boundaries
- This should be a **mandatory implementation requirement**

#### 🟡 MEDIUM — F-11: Desktop Idle Timeout Is Very Long

**Issue:** Desktop idle timeout is 4 hours. For a financial trading application with access to broker credentials and live trading capability, this is excessively long.

**Risk:** An unattended desktop with Alpha Stack running could be accessed by an unauthorized person for up to 4 hours.

**Recommendation:**
- Default to **30 minutes** for desktop, configurable up to 4 hours
- Require biometric re-authentication for trade execution even within an active session
- Implement **screen lock detection** — auto-lock when the OS screen locks

#### 🟡 MEDIUM — F-12: No Explicit Session Token Binding to TLS

**Issue:** The architecture uses TLS 1.3 but does not specify **token binding** (RFC 8471) or channel binding for session tokens.

**Risk:** If an attacker performs a TLS interception (e.g., corporate proxy, compromised CA), they could capture and replay session tokens.

**Recommendation:**
- Implement **DPoP** (Demonstrating Proof-of-Possession) for access tokens, or at minimum bind tokens to TLS channel via `tls_exporter` value
- This is a defense-in-depth measure; TLS 1.3 with proper certificate validation should prevent most interception

---

## 5. Password Hashing Review

### 5.1 Architecture Assessment

The Argon2id configuration is **excellent**:

- ✅ Algorithm: Argon2id (winner of the Password Hashing Competition)
- ✅ Memory cost: 65,536 KiB (64 MB) — strong
- ✅ Time cost: 3 iterations
- ✅ Parallelism: 4 threads
- ✅ Salt length: 16 bytes (128 bits)
- ✅ Password history: 5 previous passwords blocked
- ✅ Minimum age: 1 day (prevents rapid cycling)
- ✅ HaveIBeenPwned integration (k-anonymity)
- ✅ Minimum length: 12 characters
- ✅ Maximum length: 128 characters (prevents DoS via very long passwords)

### 5.2 Findings

#### 🟡 MEDIUM — F-13: Password Maximum Age of 365 Days May Be Counterproductive

**Issue:** The spec mandates annual password rotation (`max_age: 365 days`).

**Risk:** NIST SP 800-63B (2024) explicitly recommends **against** periodic password changes unless there is evidence of compromise. Forced rotation leads to predictable patterns (e.g., `Password2026!` → `Password2027!`).

**Recommendation:**
- Remove the `max_age` requirement
- Rely on HaveIBeenPwned checks and anomaly detection to trigger password changes
- Keep the `min_age` to prevent rapid cycling
- This aligns with NIST, CISA, and modern security guidance

#### 🟢 LOW — F-14: TOTP Window Tolerance Could Be Tighter

**Issue:** ±1 window tolerance (±30 seconds) is standard but means the server accepts codes up to 60 seconds old.

**Risk:** Very low. This is standard practice. However, with NTP-synced servers, a ±0 window (current period only) is feasible and slightly more secure.

**Recommendation:**
- Current setting is acceptable; document as a conscious trade-off for usability

---

## 6. Cross-Cutting Authentication Vulnerabilities

### 6.1 OAuth2 Callback Security

**Status:** The architecture mentions OAuth2 for REST API brokers (OANDA, Interactive Brokers) with redirect-based flows but does not specify:
- `state` parameter validation (CSRF protection)
- PKCE (Proof Key for Code Exchange) for public clients
- Redirect URI exact matching

**Risk:** Without these, OAuth2 flows are vulnerable to CSRF and authorization code interception.

**Recommendation:**
- **Mandate** `state` parameter with cryptographic randomness
- Implement **PKCE** (S256 method) for all OAuth2 flows
- Validate redirect URI with exact string matching (no wildcards)
- Document these as non-negotiable requirements

### 6.2 Device Fingerprint Strength

**Status:** The session model uses `SHA-256 hash of device fingerprint` for device binding, but the fingerprint components are not specified.

**Risk:** Weak fingerprints (e.g., User-Agent only) are easily spoofed. Strong fingerprints (canvas, WebGL, audio context) are privacy-invasive and can change with browser updates.

**Recommendation:**
- Use a combination of: installed fonts hash, screen resolution, timezone, WebGL renderer, and a stored random device ID
- Accept that fingerprints will change; use them as **risk signals**, not hard identity
- Pair with behavioral biometrics (typing patterns, mouse movement) for high-value operations

### 6.3 Missing Web-Specific Auth Details

**Status:** `architecture_ui_web.md` was **not found**. The security architecture references a web SPA (`https://app.alphastack.io`) but the detailed web auth flow (cookie handling, token refresh in browser, service worker implications) is not specified.

**Risk:** Implementation teams may make inconsistent or insecure choices for the web client.

**Recommendation:**
- Create the web UI architecture document with explicit auth flow specifications
- Define: cookie attributes, token refresh mechanism (silent refresh vs. interceptor), handling of tab visibility changes, and CSP implications for auth endpoints

---

## 7. Compliance & Standards Alignment

| Standard | Requirement | Alpha Stack Status | Gap |
|----------|-------------|-------------------|-----|
| **NIST SP 800-63B** | No periodic password changes | ❌ 365-day rotation mandated | F-13 |
| **NIST SP 800-63B** | Memorized secrets ≥ 8 chars | ✅ 12 chars minimum | — |
| **NIST SP 800-63B** | Rate limiting on auth attempts | ✅ 5/15min per IP | — |
| **OWASP ASVS 4.0** | Session fixation prevention | ⚠️ Not explicitly specified | F-10 |
| **OWASP ASVS 4.0** | Token storage (httpOnly cookies) | ⚠️ Mentioned in pentest criteria, not as requirement | F-01 |
| **OWASP ASVS 4.0** | Refresh token rotation with detection | ⚠️ Rotation specified, race condition not addressed | F-02 |
| **OWASP ASVS 4.0** | OAuth2 state parameter | ❌ Not specified | §6.1 |
| **PCI DSS 4.0** | MFA for all access to CDE | ✅ 2FA architecture present | — |
| **PCI DSS 4.0** | Session timeout ≤ 15 min | ✅ Web: 15min; ⚠️ Desktop: 4hr | F-11 |

---

## 8. Summary of Recommendations

### Critical (Must Fix Before Launch)

| ID | Finding | Recommendation |
|----|---------|----------------|
| F-01 | Refresh token storage unspecified for web | Mandate httpOnly + Secure + SameSite=Strict cookies |
| F-10 | Session fixation in 2FA flow | Regenerate session ID after every auth step |

### High (Fix Before Production)

| ID | Finding | Recommendation |
|----|---------|----------------|
| F-02 | Refresh token race condition | Implement grace window + token family tracking |
| F-05 | TOTP secret memory exposure | Zero after use; disable core dumps on auth server |
| F-06 | Partial token in 2FA flow underspecified | Define scope (zero access), TTL (5min), single-use |
| F-08 | Biometric PIN fallback | Add biometric-only option for high-security users |

### Medium (Fix in Phase 1-2)

| ID | Finding | Recommendation |
|----|---------|----------------|
| F-03 | JWT claims leak PII | Remove email from access token; use opaque sub |
| F-07 | Backup code entropy | Increase to 10 chars or use Crockford Base32 |
| F-09 | Quick View data exposure | Market data only; no account-specific info |
| F-11 | Desktop idle timeout (4hr) | Default 30min; require biometric for trades |
| F-12 | No TLS token binding | Implement DPoP or channel binding |
| F-13 | Forced annual password rotation | Remove; rely on breach detection |

### Low (Track for Phase 2+)

| ID | Finding | Recommendation |
|----|---------|----------------|
| F-04 | IP fingerprint false positives | Use as risk signal, not hard validation |
| F-14 | TOTP window tolerance | Acceptable; document as trade-off |

---

## 9. Positive Findings (What's Done Right)

The architecture demonstrates strong security engineering in several areas:

1. **Argon2id configuration** — Memory cost of 64MB, parallelism of 4, and proper salt length make brute-force attacks computationally expensive
2. **Credential isolation** — Five-level isolation for broker credentials (process, memory, storage, network, access control) is exemplary
3. **Memory zeroization** — `ZeroizeOnDrop` pattern for broker credentials in Rust prevents memory residual exposure
4. **Key rotation** — Dual-key overlap with zero-downtime rotation for JWT signing keys
5. **Audit logging with hash chain** — Tamper-evident logging with cryptographic chaining
6. **Quantum-resistant roadmap** — Proactive PQC migration planning with hybrid cryptography
7. **Backup code hashing** — Argon2id hashing of backup codes (many systems store these in plaintext)
8. **Per-platform idle timeouts** — Context-aware timeout values (web vs. desktop vs. mobile)
9. **Tiered biometric auth** — Different auth levels for view/trade/settings on mobile
10. **Rate limiting** — Comprehensive, per-endpoint rate limits with progressive lockout

---

## 10. Missing Architecture Documents

The following documents were referenced but **not found**:

| Document | Impact on This Review |
|----------|----------------------|
| `architecture_broker_connection.md` | Could not verify broker-specific auth flows (OAuth2, mTLS) |
| `architecture_ui_web.md` | Could not verify web client auth implementation details |

**Recommendation:** These documents should be created and reviewed as part of the authentication security assessment. The web client is particularly critical as it has the largest attack surface.

---

*This review should be revisited after implementation of Phase 1 (Security Foundation) and again before external penetration testing in Phase 6.*
