# Alpha Stack — Token & Credential Security Fixes

> **Author:** Auth Fix Agent — Token & Credential Security  
> **Date:** 2026-07-11  
> **Input:** `review_security_auth.md` (findings F-01, F-05, F-06, F-08)  
> **Scope:** Refresh token storage, TOTP secret memory exposure, partial_token design, biometric PIN fallback  
> **Status:** Ready for implementation review

---

## Fix 1: Refresh Token Web Storage — Mandate httpOnly Cookies

**Finding:** F-01 (🔴 Critical)  
**Problem:** Refresh token storage on the web client is unspecified. If stored in `localStorage` or JavaScript-accessible variables, XSS attacks can exfiltrate tokens. The trading platform's attack surface (WebSocket connections, third-party chart libraries, CDN dependencies) makes this a critical exposure.

### Required Changes

#### 1.1 — Cookie Attribute Mandate (Non-Negotiable)

All refresh tokens on the web client **MUST** be stored as cookies with the following attributes:

```
Set-Cookie: refresh_token=<token>;
  HttpOnly;       // Not accessible via JavaScript (blocks XSS exfiltration)
  Secure;         // HTTPS-only transmission
  SameSite=Strict; // No cross-site sending (blocks CSRF)
  Path=/auth;     // Scoped to auth endpoints only
  Max-Age=604800; // 7 days, matching refresh token TTL
```

**Why `SameSite=Strict` over `Lax`:** A trading platform has no legitimate cross-site navigation to auth endpoints. `Strict` provides stronger CSRF protection with no usability cost.

#### 1.2 — Access Token Handling

Access tokens (15-minute TTL) **MUST** exist only in JavaScript memory (closure/variable), never persisted:

```typescript
// ✅ CORRECT — in-memory only
class TokenStore {
  private accessToken: string | null = null;

  setAccessToken(token: string): void {
    this.accessToken = token;
  }

  getAccessToken(): string | null {
    return this.accessToken;
  }

  clearAccessToken(): void {
    this.accessToken = null;
  }
}

// ❌ FORBIDDEN — never do this
localStorage.setItem('access_token', token);
sessionStorage.setItem('access_token', token);
document.cookie = `access_token=${token}`; // access tokens in cookies
```

#### 1.3 — Silent Refresh Mechanism

Implement a background token refresh using the httpOnly cookie:

```typescript
// Token refresh interceptor — runs before each API call
async function refreshAccessToken(): Promise<string> {
  const response = await fetch('/auth/refresh', {
    method: 'POST',
    credentials: 'include', // Sends httpOnly refresh_token cookie
  });

  if (!response.ok) {
    throw new AuthError('REFRESH_FAILED');
  }

  const { access_token } = await response.json();
  tokenStore.setAccessToken(access_token);
  return access_token;
}

// Proactive refresh at 80% of token lifetime (12 min for 15 min TTL)
const REFRESH_BUFFER_MS = 3 * 60 * 1000; // 3 minutes before expiry
let refreshTimer: ReturnType<typeof setTimeout>;

function scheduleRefresh(expiresIn: number) {
  clearTimeout(refreshTimer);
  const delay = Math.max((expiresIn * 1000) - REFRESH_BUFFER_MS, 0);
  refreshTimer = setTimeout(() => refreshAccessToken(), delay);
}
```

#### 1.4 — Server-Side Refresh Endpoint Security

The `/auth/refresh` endpoint **MUST**:

1. Validate the refresh token from the httpOnly cookie (not from request body)
2. Verify the token family (see Fix 1.5 below)
3. Rotate the refresh token (issue a new one, invalidate the old)
4. Return the new access token in the response body and the new refresh token as a new `Set-Cookie` header
5. Never accept refresh tokens from the request body or URL parameters

```python
@app.post("/auth/refresh")
async def refresh_token(request: Request, response: Response):
    # 1. Extract from cookie ONLY
    old_refresh_token = request.cookies.get("refresh_token")
    if not old_refresh_token:
        raise AuthError(401, "No refresh token")

    # 2. Validate and rotate
    token_family = validate_refresh_token(old_refresh_token)
    new_access, new_refresh = rotate_token_pair(token_family)

    # 3. Set new refresh token cookie
    response.set_cookie(
        "refresh_token",
        new_refresh,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/auth",
        max_age=604800,
    )

    # 4. Return access token in body
    return {"access_token": new_access, "expires_in": 900}
```

#### 1.5 — Race Condition Grace Window (F-02 Companion Fix)

To prevent multi-tab logouts during simultaneous refresh:

```python
GRACE_WINDOW_SECONDS = 10

def rotate_token_pair(token_family: TokenFamily) -> tuple[str, str]:
    old_token = token_family.current_token
    new_refresh = generate_refresh_token()
    new_access = generate_access_token(token_family.user_id)

    # Mark old token as "rotating" with grace window expiry
    old_token.status = TokenStatus.ROTATING
    old_token.grace_expires_at = utcnow() + timedelta(seconds=GRACE_WINDOW_SECONDS)
    old_token.replaced_by = hash_token(new_refresh)

    # Store new token
    token_family.current_token_hash = hash_token(new_refresh)
    save_token_family(token_family)

    return new_access, new_refresh

def validate_refresh_token(raw_token: str) -> TokenFamily:
    token_hash = hash_token(raw_token)
    token = find_token_by_hash(token_hash)

    if token is None:
        raise AuthError(401, "Invalid refresh token")

    if token.status == TokenStatus.ACTIVE:
        return token.family

    if token.status == TokenStatus.ROTATING:
        if utcnow() < token.grace_expires_at:
            # Within grace window — allow but flag for monitoring
            log_audit("refresh_token_grace_window_used", token.family.user_id)
            return token.family
        else:
            # Outside grace window — token family compromised
            revoke_token_family(token.family, reason="stale_rotated_token")
            raise AuthError(401, "Token expired — re-authenticate required")

    if token.status == TokenStatus.REVOKED:
        # Revoked token reused — possible theft
        revoke_token_family(token.family, reason="revoked_token_reuse")
        raise AuthError(401, "Token revoked — re-authenticate required")

    raise AuthError(401, "Invalid token state")
```

#### 1.6 — Pre-Launch Verification Checklist

Add to the deployment checklist:

- [ ] `grep -r "localStorage.*token\|sessionStorage.*token" --include="*.ts" --include="*.js"` returns zero results
- [ ] All `Set-Cookie` headers for `refresh_token` include `HttpOnly`, `Secure`, `SameSite=Strict`
- [ ] `/auth/refresh` endpoint only reads from cookies
- [ ] CSP headers block `unsafe-inline` and `unsafe-eval` (reduces XSS impact)
- [ ] Content-Security-Policy includes `connect-src` whitelist for API endpoints

---

## Fix 2: TOTP Secret Memory Exposure — Zeroize After Use

**Finding:** F-05 (🟠 High)  
**Problem:** The `FieldEncryptor` class caches DEK keys indefinitely in `self._key_cache`. Plaintext TOTP secrets exist in memory during verification. Memory dump attacks (crash dumps, cold boot, process introspection) could expose secrets.

### Required Changes

#### 2.1 — Zeroize TOTP Plaintext After Verification

Implement a secure zeroization pattern for all in-memory TOTP secrets:

```python
import ctypes
import sys
from contextlib import contextmanager
from typing import Generator

@contextmanager
def secure_secret(plaintext: bytes) -> Generator[bytearray, None, None]:
    """
    Context manager that zeroes sensitive data after use.
    Prevents plaintext secrets from lingering in memory.
    """
    buffer = bytearray(plaintext)
    try:
        yield buffer
    finally:
        # Overwrite with zeros
        for i in range(len(buffer)):
            buffer[i] = 0
        # Prevent Python from optimizing away the zeroing
        # (compiler barrier equivalent)
        ctypes.memset(id(buffer) + bytes.__basicsize__, 0, len(buffer))


def verify_totp(encrypted_secret: bytes, user_key: bytes, code: str) -> bool:
    """Verify TOTP code with immediate secret zeroization."""
    # Decrypt the TOTP secret
    plaintext_secret = decrypt_field(encrypted_secret, user_key)

    try:
        with secure_secret(plaintext_secret) as secret:
            # Generate expected TOTP code using the secret
            expected = pyotp.TOTP(secret.decode('utf-8')).now()
            return hmac.compare_digest(code, expected)
    finally:
        # Explicitly clear the reference
        plaintext_secret = None
```

#### 2.2 — DEK Cache TTL and Eviction

Replace indefinite caching with TTL-based eviction:

```python
import time
from threading import Lock

class SecureFieldEncryptor:
    DEK_CACHE_TTL_SECONDS = 300  # 5 minutes

    def __init__(self):
        self._key_cache: dict[str, tuple[bytes, float]] = {}  # key_id -> (dek, timestamp)
        self._cache_lock = Lock()

    def get_dek(self, key_id: str, kek: bytes) -> bytes:
        """Retrieve DEK with TTL-based caching."""
        with self._cache_lock:
            if key_id in self._key_cache:
                dek, cached_at = self._key_cache[key_id]
                if time.monotonic() - cached_at < self.DEK_CACHE_TTL_SECONDS:
                    return dek
                else:
                    # Expired — zeroize and evict
                    self._zeroize_dek(dek)
                    del self._key_cache[key_id]

        # Cache miss or expired — decrypt DEK from storage
        encrypted_dek = self._fetch_encrypted_dek(key_id)
        dek = self._unwrap_dek(encrypted_dek, kek)

        with self._cache_lock:
            # Evict oldest entries if cache is too large
            if len(self._key_cache) > 64:
                self._evict_oldest()
            self._key_cache[key_id] = (dek, time.monotonic())

        return dek

    def _zeroize_dek(self, dek: bytes) -> None:
        """Overwrite DEK bytes in memory."""
        if isinstance(dek, bytearray):
            for i in range(len(dek)):
                dek[i] = 0
        # If immutable bytes, we can't zeroize — track for GC pressure
        # This is why internal DEKs should be bytearray

    def _evict_oldest(self) -> None:
        """Evict the oldest DEK entry from cache."""
        if not self._key_cache:
            return
        oldest_key = min(self._key_cache, key=lambda k: self._key_cache[k][1])
        dek, _ = self._key_cache.pop(oldest_key)
        self._zeroize_dek(dek)

    def flush_cache(self) -> None:
        """Zeroize and clear all cached DEKs. Call on shutdown."""
        with self._cache_lock:
            for key_id, (dek, _) in self._key_cache.items():
                self._zeroize_dek(dek)
            self._key_cache.clear()
```

#### 2.3 — Auth Server Process Hardening

Disable core dumps and enable memory protection on the auth server:

```bash
#!/bin/bash
# auth-server-start.sh — Hardened process launch

# Disable core dumps for this process
ulimit -c 0

# Prevent ptrace attachment (anti-debugging)
echo 2 > /proc/self/yama/ptrace_scope 2>/dev/null || true

# Set memory lock to prevent swapping sensitive data
# (Requires CAP_IPC_LOCK capability)
export MALLOC_ARENA_MAX=2  # Reduce memory arena fragmentation

exec python -O auth_server.py
```

Add to Docker/systemd configuration:

```yaml
# docker-compose.yml — auth service
services:
  auth:
    security_opt:
      - no-new-privileges:true
    ulimits:
      core: 0          # No core dumps
      nofile: 65536
    read_only: true     # Read-only filesystem
    tmpfs:
      - /tmp:noexec,nosuid,size=64m
```

```ini
# systemd unit override
[Service]
LimitCORE=0
LimitNOFILE=65536
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
NoNewPrivileges=true
MemoryDenyWriteExecute=true
```

#### 2.4 — Rust-Side Zeroize (MT5 Bridge / Native Components)

For Rust components, use the `zeroize` crate (already used for `BrokerCredentials`):

```rust
use zeroize::{Zeroize, ZeroizeOnDrop};

#[derive(Zeroize, ZeroizeOnDrop)]
struct TotpSecret {
    secret_bytes: Vec<u8>,
}

impl TotpSecret {
    fn verify(&self, code: &str) -> bool {
        let totp = totp_rs::TOTP::new(
            totp_rs::Algorithm::SHA1,
            6,
            1,
            30,
            self.secret_bytes.clone(),
        ).expect("valid TOTP config");
        totp.check_current(code).unwrap_or(false)
    }
    // secret_bytes is automatically zeroized when TotpSecret is dropped
}

// Usage — secret exists only in this scope
fn verify_user_totp(encrypted: &[u8], user_key: &[u8], code: &str) -> Result<bool> {
    let decrypted = decrypt_field(encrypted, user_key)?;
    let secret = TotpSecret { secret_bytes: decrypted };
    Ok(secret.verify(code))
    // `secret` is dropped and zeroized here
}
```

---

## Fix 3: Partial Token Design Risk — Validate Scope & Binding

**Finding:** F-06 (🟠 High)  
**Problem:** The 2FA flow returns a `partial_token` after password verification, but its scope, TTL, storage, and binding are unspecified. An overly permissive partial_token could allow resource access before 2FA completion.

### Required Changes

#### 3.1 — Partial Token Specification

Define the partial_token as a **single-use, tightly scoped, short-lived nonce**:

| Property | Value | Rationale |
|----------|-------|-----------|
| **Format** | Opaque random token (256-bit) | Not a JWT — no claims to leak |
| **TTL** | 5 minutes | Enough for TOTP entry; short enough to limit exposure |
| **Scope** | `/auth/2fa/verify` ONLY | Zero access to any other endpoint |
| **Binding** | IP + device fingerprint hash | Prevents token theft and replay from different context |
| **Usage** | Single-use (consumed on verification) | Cannot be replayed |
| **Storage** | Server-side only (Redis/memory with TTL) | Never sent as JWT or persistent cookie |

#### 3.2 — Implementation

```python
import secrets
import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

@dataclass
class PartialToken:
    token_hash: str          # SHA-256 of the raw token
    user_id: str
    device_fingerprint_hash: str
    ip_hash: str
    created_at: datetime
    expires_at: datetime
    consumed: bool = False

PARTIAL_TOKEN_TTL_SECONDS = 300  # 5 minutes

async def create_partial_token(
    user_id: str,
    device_fingerprint: str,
    client_ip: str,
) -> str:
    """Create a partial token after successful password verification."""
    raw_token = secrets.token_urlsafe(32)  # 256 bits
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    partial = PartialToken(
        token_hash=token_hash,
        user_id=user_id,
        device_fingerprint_hash=hashlib.sha256(device_fingerprint.encode()).hexdigest(),
        ip_hash=hashlib.sha256(client_ip.encode()).hexdigest(),
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=PARTIAL_TOKEN_TTL_SECONDS),
    )

    # Store with TTL in Redis
    await redis.setex(
        f"partial_token:{token_hash}",
        PARTIAL_TOKEN_TTL_SECONDS,
        partial.to_json(),
    )

    # Log creation for audit
    await audit_log("partial_token_created", user_id=user_id, ttl=PARTIAL_TOKEN_TTL_SECONDS)

    return raw_token  # Returned to client, never stored server-side


async def consume_partial_token(
    raw_token: str,
    device_fingerprint: str,
    client_ip: str,
) -> str:
    """
    Validate and consume a partial token.
    Returns user_id on success, raises on failure.
    """
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    stored = await redis.get(f"partial_token:{token_hash}")

    if stored is None:
        raise AuthError(401, "Invalid or expired partial token")

    partial = PartialToken.from_json(stored)

    # 1. Check expiration (redundant with Redis TTL, defense in depth)
    if datetime.now(timezone.utc) > partial.expires_at:
        await redis.delete(f"partial_token:{token_hash}")
        raise AuthError(401, "Partial token expired")

    # 2. Check single-use
    if partial.consumed:
        # Token reuse attempt — possible replay attack
        await redis.delete(f"partial_token:{token_hash}")
        await audit_log("partial_token_reuse_detected", user_id=partial.user_id, severity="HIGH")
        raise AuthError(401, "Partial token already used")

    # 3. Verify binding — IP
    current_ip_hash = hashlib.sha256(client_ip.encode()).hexdigest()
    if current_ip_hash != partial.ip_hash:
        await redis.delete(f"partial_token:{token_hash}")
        await audit_log("partial_token_ip_mismatch", user_id=partial.user_id, severity="HIGH")
        raise AuthError(401, "Partial token binding mismatch")

    # 4. Verify binding — device fingerprint
    current_fp_hash = hashlib.sha256(device_fingerprint.encode()).hexdigest()
    if current_fp_hash != partial.device_fingerprint_hash:
        await redis.delete(f"partial_token:{token_hash}")
        await audit_log("partial_token_fp_mismatch", user_id=partial.user_id, severity="HIGH")
        raise AuthError(401, "Partial token binding mismatch")

    # 5. Mark as consumed (single-use)
    partial.consumed = True
    await redis.setex(
        f"partial_token:{token_hash}",
        60,  # Keep for 60s for audit, then auto-expire
        partial.to_json(),
    )

    return partial.user_id
```

#### 3.3 — Endpoint Access Control Middleware

Ensure the partial_token can **only** be used on the 2FA verification endpoint:

```python
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

PARTIAL_TOKEN_ALLOWED_ENDPOINTS = {"/auth/2fa/verify"}

class PartialTokenScopeMiddleware(BaseHTTPMiddleware):
    """Reject partial tokens on any endpoint except 2FA verify."""

    async def dispatch(self, request: Request, call_next):
        auth_header = request.headers.get("Authorization", "")

        if auth_header.startswith("Bearer partial_"):
            if request.url.path not in PARTIAL_TOKEN_ALLOWED_ENDPOINTS:
                await audit_log(
                    "partial_token_scope_violation",
                    endpoint=request.url.path,
                    severity="HIGH",
                )
                return JSONResponse(
                    status_code=403,
                    content={"error": "Partial token cannot access this resource"},
                )

        return await call_next(request)
```

#### 3.4 — Rate Limiting on Partial Token Creation

Prevent brute-force on the password step by rate-limiting partial token creation:

```python
async def rate_limit_partial_token(user_id: str, client_ip: str) -> None:
    """Rate limit: max 5 partial tokens per 15 minutes per user."""
    key = f"partial_token_rate:{user_id}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, 900)  # 15 minutes

    if count > 5:
        await audit_log("partial_token_rate_limit", user_id=user_id, severity="MEDIUM")
        raise AuthError(429, "Too many login attempts. Try again in 15 minutes.")
```

---

## Fix 4: Biometric PIN Fallback — Secure Fallback Configuration

**Finding:** F-08 (🟠 High)  
**Problem:** The mobile biometric service uses `biometricOnly: false`, allowing device PIN/password to substitute for biometrics. For a financial trading app, this undermines the security intent of biometric authentication.

### Required Changes

#### 4.1 — User-Configurable Biometric Policy

Add a `biometric_policy` setting to user preferences:

```dart
// lib/models/auth_settings.dart

enum BiometricPolicy {
  /// Biometric preferred, PIN/password fallback allowed (default for new users)
  biometricPreferred,

  /// Biometric ONLY — no PIN/password fallback (strict mode)
  biometricOnly,

  /// Disabled — always use password
  disabled,
}

class AuthSettings {
  final BiometricPolicy biometricPolicy;
  final bool biometricForTrades;    // Require biometric for trade execution
  final bool biometricForWithdrawals; // Require biometric for withdrawals
  final Duration reAuthThreshold;   // Time before re-auth is required

  const AuthSettings({
    this.biometricPolicy = BiometricPolicy.biometricPreferred,
    this.biometricForTrades = true,
    this.biometricForWithdrawals = true,
    this.reAuthThreshold = const Duration(minutes: 5),
  });
}
```

#### 4.2 — Platform Biometric Authentication Implementation

```dart
// lib/services/biometric_service.dart

import 'package:local_auth/local_auth.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class BiometricService {
  final LocalAuthentication _localAuth;
  final FlutterSecureStorage _secureStorage;
  final AuthSettings _settings;

  BiometricService({
    required LocalAuthentication localAuth,
    required FlutterSecureStorage secureStorage,
    required AuthSettings settings,
  })  : _localAuth = localAuth,
        _secureStorage = secureStorage,
        _settings = settings;

  /// Authenticate with biometrics (or PIN if policy allows).
  /// Returns true on success, false on failure.
  Future<bool> authenticate({
    required String reason,
    required AuthLevel level,
  }) async {
    // Check if biometrics are available
    final canCheckBiometrics = await _localAuth.canCheckBiometrics;
    final isDeviceSupported = await _localAuth.isDeviceSupported();

    if (!canCheckBiometrics || !isDeviceSupported) {
      // No biometric hardware — fall back to password-based auth
      return await _fallbackToPassword(reason, level);
    }

    // Determine if this operation requires biometric-only
    final bool requireBiometricOnly = _shouldRequireBiometricOnly(level);

    try {
      final bool didAuthenticate = await _localAuth.authenticate(
        localizedReason: reason,
        options: AuthenticationOptions(
          stickyAuth: true,                    // Don't dismiss on app switch
          biometricOnly: requireBiometricOnly, // Key setting based on policy
          useErrorDialogs: true,
          sensitiveTransaction: level == AuthLevel.trade ||
                                level == AuthLevel.withdrawal,
        ),
      );

      if (didAuthenticate) {
        await _recordSuccessfulAuth(level);
        return true;
      }

      // Biometric failed — check if PIN fallback is allowed
      if (!requireBiometricOnly) {
        return await _fallbackToPassword(reason, level);
      }

      return false;
    } on PlatformException catch (e) {
      if (e.code == 'LockedOut' || e.code == 'PermanentlyLockedOut') {
        // Too many biometric attempts — require password
        await _notifyLockout(e.code == 'PermanentlyLockedOut');
        return await _fallbackToPassword(reason, level);
      }
      rethrow;
    }
  }

  /// Determine if biometric-only is required based on operation level.
  bool _shouldRequireBiometricOnly(AuthLevel level) {
    switch (_settings.biometricPolicy) {
      case BiometricPolicy.biometricOnly:
        return true; // Always biometric-only
      case BiometricPolicy.biometricPreferred:
        // Require biometric-only for high-risk operations
        return level == AuthLevel.withdrawal;
      case BiometricPolicy.disabled:
        return false; // Should not reach here — handled earlier
    }
  }

  /// Fallback to password-based authentication.
  Future<bool> _fallbackToPassword(String reason, AuthLevel level) async {
    // Navigate to password entry screen
    // This is a full re-authentication, not a shortcut
    final result = await navigator.push(
      MaterialPageRoute(
        builder: (_) => PasswordAuthScreen(
          reason: reason,
          level: level,
        ),
      ),
    );
    return result == true;
  }

  /// Record successful auth for re-auth threshold tracking.
  Future<void> _recordSuccessfulAuth(AuthLevel level) async {
    await _secureStorage.write(
      key: 'last_auth_${level.name}',
      value: DateTime.now().toIso8601String(),
    );
  }

  /// Check if re-authentication is needed based on threshold.
  Future<bool> needsReAuth(AuthLevel level) async {
    final lastAuth = await _secureStorage.read(key: 'last_auth_${level.name}');
    if (lastAuth == null) return true;

    final lastAuthTime = DateTime.parse(lastAuth);
    return DateTime.now().difference(lastAuthTime) > _settings.reAuthThreshold;
  }

  /// Handle biometric lockout.
  Future<void> _notifyLockout(bool permanent) async {
    // Show user notification about lockout
    // For permanent lockout, guide user to security settings
    if (permanent) {
      await showDialog(
        context: navigator.context,
        builder: (_) => BiometricLockoutDialog(
          message: 'Biometric authentication is permanently locked. '
                   'Please reset biometrics in your device security settings.',
        ),
      );
    }
  }
}
```

#### 4.3 — Tiered Authentication Enforcement

Enforce biometric requirements per operation:

```dart
// lib/services/auth_gate.dart

class AuthGate {
  final BiometricService _biometricService;

  /// Gate for trade execution — requires recent biometric auth.
  Future<bool> requireTradeAuth(BuildContext context) async {
    if (await _biometricService.needsReAuth(AuthLevel.trade)) {
      return await _biometricService.authenticate(
        reason: 'Authenticate to execute trade',
        level: AuthLevel.trade,
      );
    }
    return true; // Within re-auth threshold
  }

  /// Gate for withdrawal — always requires biometric (no threshold).
  Future<bool> requireWithdrawalAuth(BuildContext context) async {
    return await _biometricService.authenticate(
      reason: 'Authenticate to process withdrawal',
      level: AuthLevel.withdrawal,
    );
  }

  /// Gate for settings changes.
  Future<bool> requireSettingsAuth(BuildContext context) async {
    return await _biometricService.authenticate(
      reason: 'Authenticate to change security settings',
      level: AuthLevel.settings,
    );
  }
}
```

#### 4.4 — Biometric Policy Selection UI

Provide clear user guidance during onboarding and in settings:

```dart
// lib/screens/security_settings_screen.dart

class BiometricPolicyTile extends StatelessWidget {
  final BiometricPolicy currentPolicy;
  final ValueChanged<BiometricPolicy> onChanged;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Biometric Authentication',
          style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 8),
        _buildOption(
          context,
          policy: BiometricPolicy.biometricOnly,
          title: 'Biometric Only (Recommended)',
          subtitle: 'Requires fingerprint or face ID for all sensitive actions. '
                    'No PIN/password fallback. Most secure option.',
          icon: Icons.fingerprint,
        ),
        _buildOption(
          context,
          policy: BiometricPolicy.biometricPreferred,
          title: 'Biometric Preferred',
          subtitle: 'Biometrics used when available, device PIN/password as backup. '
                    'Withdrawals always require biometric.',
          icon: Icons.face,
        ),
        _buildOption(
          context,
          policy: BiometricPolicy.disabled,
          title: 'Password Only',
          subtitle: 'All actions require password entry. No biometric shortcuts.',
          icon: Icons.lock_outline,
        ),
        const SizedBox(height: 16),
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: Colors.amber.shade50,
            borderRadius: BorderRadius.circular(8),
          ),
          child: Row(
            children: [
              const Icon(Icons.info_outline, color: Colors.amber),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  'Biometric-only mode prevents anyone with your device PIN '
                  'from accessing your trading account. If biometrics fail, '
                  'you will need to reset via email verification.',
                  style: TextStyle(color: Colors.amber.shade900, fontSize: 13),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}
```

#### 4.5 — Secure Biometric Fallback Flow

When biometric-only mode is enabled and biometrics fail, provide a secure recovery path:

```
Biometric Failure (biometric-only mode)
    │
    ├── User has backup codes → Enter backup code → Re-setup biometrics
    │
    ├── User has no backup codes →
    │       Email verification link → Full re-authentication → Re-setup biometrics
    │
    └── Account locked (too many attempts) →
            Email support + identity verification → Manual unlock
```

```dart
/// Recovery flow when biometric-only mode user is locked out.
Future<void> handleBiometricLockout(BuildContext context) async {
  final hasBackupCodes = await _checkBackupCodesExist();

  if (hasBackupCodes) {
    // Offer backup code entry
    final code = await showDialog<String>(
      context: context,
      builder: (_) => BackupCodeEntryDialog(),
    );
    if (code != null && await _verifyBackupCode(code)) {
      // Allow access and prompt to re-register biometrics
      await _promptBiometricReRegistration(context);
    }
  } else {
    // Send email verification for account recovery
    await _sendRecoveryEmail();
    if (context.mounted) {
      showDialog(
        context: context,
        builder: (_) => RecoveryEmailSentDialog(),
      );
    }
  }
}
```

---

## Summary of Changes

| Fix | Finding | Severity | Core Change |
|-----|---------|----------|-------------|
| Fix 1 | F-01 + F-02 | 🔴 Critical | Mandate httpOnly cookies for refresh tokens; grace window for rotation |
| Fix 2 | F-05 | 🟠 High | Zeroize TOTP secrets after use; DEK cache TTL; process hardening |
| Fix 3 | F-06 | 🟠 High | Partial token: opaque nonce, 5-min TTL, single-use, IP+device bound |
| Fix 4 | F-08 | 🟠 High | User-configurable biometric policy; tiered auth; secure fallback flow |

### Implementation Priority

1. **Fix 1** (Critical) — Must be implemented before any web client deployment
2. **Fix 3** (High) — Must be implemented before 2FA goes live
3. **Fix 2** (High) — Should be implemented in Phase 1 (Security Foundation)
4. **Fix 4** (High) — Should be implemented before mobile beta release

### Testing Requirements

- **Fix 1:** Verify no tokens in localStorage via automated browser scan; test multi-tab refresh; test refresh token rotation race condition
- **Fix 2:** Verify TOTP secret zeroization via memory dump analysis; verify DEK cache eviction
- **Fix 3:** Test partial_token scope enforcement; test IP/fingerprint binding; test single-use enforcement; test 5-min expiry
- **Fix 4:** Test biometric-only mode blocks PIN fallback; test lockout recovery; test tiered auth enforcement

---

*This document addresses findings F-01, F-02, F-05, F-06, and F-08 from `review_security_auth.md`. For other findings (F-03, F-04, F-07, F-09–F-14), see the respective fix documents.*
