# Alpha Stack — Session Management Authentication Fixes

> **Author:** Auth Fix Agent — Session Management  
> **Date:** 2026-07-11  
> **Source:** `review_security_auth.md` — Findings F-01, F-02, F-10  
> **Scope:** Session-related authentication issues ONLY  
> **Status:** READY FOR IMPLEMENTATION

---

## Summary

| ID | Severity | Finding | Fix Status |
|----|----------|---------|------------|
| F-10 | 🟠 High | Session fixation in 2FA flow | ✅ Fixed |
| F-02 | 🟠 High | Refresh token race condition | ✅ Fixed |
| F-01 | 🔴 Critical | Refresh token cookie attributes | ✅ Fixed |

All three findings are interrelated — they affect how sessions are created, maintained, and secured across the authentication lifecycle.

---

## 1. F-10 — Session Fixation in 2FA Flow

**Problem:** The 2FA flow returns a `partial_token` after password verification, which is upgraded to a full session after TOTP verification. If the session ID is established *before* 2FA completion and not regenerated, an attacker who pre-sets a session cookie can hijack the session after the victim completes 2FA. This is a classic session fixation attack (OWASP ASVS 4.0 §3.3).

**Root Cause:** Session identifier persists across authentication boundaries (password → 2FA → full session).

**Fix: Mandate Session ID Regeneration at Every Auth Step**

### 1.1 Session Lifecycle with Regeneration

```
┌─────────────────────────────────────────────────────────────────┐
│                    AUTHENTICATION FLOW                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [1] Anonymous Request                                          │
│      └─ Session created: SID_A (unauthenticated)                │
│                                                                 │
│  [2] Password Verification                                      │
│      ├─ Validate credentials                                    │
│      ├─ DESTROY SID_A                                           │
│      ├─ GENERATE SID_B (new session ID)                         │
│      ├─ Store: { state: "pending_2fa", uid, ip_hash }           │
│      ├─ Issue partial_token (5min TTL, zero permissions)        │
│      └─ Set-Cookie: session_id=SID_B (new)                      │
│                                                                 │
│  [3] TOTP Verification                                          │
│      ├─ Validate TOTP code                                      │
│      ├─ DESTROY SID_B                                           │
│      ├─ GENERATE SID_C (new session ID)                         │
│      ├─ Store: { state: "authenticated", uid, roles, ... }      │
│      ├─ Issue access_token + refresh_token                      │
│      └─ Set-Cookie: session_id=SID_C (new)                      │
│                                                                 │
│  ✅ Attacker's pre-set SID_A is invalidated at step [2]         │
│  ✅ Even if attacker knew SID_A, it's destroyed before 2FA      │
│  ✅ SID_B is destroyed before full session is granted            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Implementation Requirements

```python
# Session manager interface — REGENERATE on every auth boundary

class SessionManager:
    """Session lifecycle manager with fixation prevention."""

    async def regenerate_session(
        self,
        old_session_id: str,
        new_auth_state: AuthState,
        context: AuthContext
    ) -> str:
        """
        Destroy old session, create new one atomically.

        MUST be called at every authentication boundary:
        - After password verification (unauthenticated → pending_2fa)
        - After 2FA verification (pending_2fa → authenticated)
        - After passwordless login verification
        - After biometric unlock
        - After OAuth2 callback completion

        Returns: new session ID
        """
        # 1. Destroy old session (invalidates any pre-set session IDs)
        await self.store.delete(old_session_id)

        # 2. Generate cryptographically random new session ID
        new_sid = secrets.token_urlsafe(32)  # 256-bit entropy

        # 3. Create new session with new state
        await self.store.create(
            session_id=new_sid,
            state=new_auth_state,
            user_id=context.user_id,
            device_id=context.device_id,
            ip_hash=hash_ip(context.ip_address),
            created_at=now(),
            expires_at=compute_expiry(new_auth_state),
        )

        # 4. Audit log the regeneration
        await self.audit.log(
            event="session_regenerated",
            old_sid_hash=hash_sid(old_session_id),
            new_sid_hash=hash_sid(new_sid),
            reason=new_auth_state.value,
            user_id=context.user_id,
            ip=context.ip_address,
        )

        return new_sid
```

### 1.3 partial_token Constraints

The `partial_token` issued after password verification (before 2FA) must be tightly scoped:

```yaml
partial_token:
  type: "opaque_nonce"           # NOT a JWT — no claims, no signature
  entropy: 256_bits              # cryptographically random
  ttl: 300_seconds               # 5 minutes maximum
  scope: "/auth/2fa/verify ONLY" # zero access to any other endpoint
  single_use: true               # consumed on use, cannot replay
  binding:
    ip_hash: required            # bound to originating IP
    device_fingerprint: required # bound to originating device
    session_id: required         # bound to the regenerated session (SID_B)
  storage:
    web: "httpOnly cookie"       # never in localStorage or JS
    desktop: "OS keyring"        # never in process memory
    mobile: "FlutterSecureStorage"
```

### 1.4 Session State Machine

```yaml
session_states:
  unauthenticated:
    description: "No valid credentials presented"
    allowed_transitions: ["pending_2fa", "authenticated"]
    ttl: 15_minutes

  pending_2fa:
    description: "Password verified, awaiting TOTP"
    allowed_transitions: ["authenticated", "destroyed"]
    ttl: 5_minutes              # strict — don't leave partial sessions hanging
    permissions: NONE           # cannot access any resource

  authenticated:
    description: "Fully verified"
    allowed_transitions: ["destroyed"]
    ttl: platform_dependent     # web: 15min idle, desktop: 30min, mobile: 30min

  destroyed:
    description: "Session invalidated"
    allowed_transitions: NONE
    terminal: true
```

### 1.5 Additional Regeneration Triggers

Beyond the 2FA flow, session IDs MUST be regenerated on:

| Trigger | Reason |
|---------|--------|
| Password change | Prevent session continuation by attacker who knew old password |
| 2FA enable/disable | Security config change invalidates session context |
| "Logout all devices" | All sessions destroyed, fresh start |
| Role/permission change | Session claims may be stale |
| Elevated privilege request | Sensitive operations get fresh session |

---

## 2. F-02 — Refresh Token Race Condition

**Problem:** Refresh token rotation invalidates the old token on use. When multiple tabs or devices attempt to refresh simultaneously using the same token, the first succeeds and the second fails — logging out the user. This is a known UX-breaking issue with strict rotation.

**Root Cause:** No coordination mechanism for concurrent refresh attempts; no grace window for recently-rotated tokens.

**Fix: Token Family Tracking with Grace Window and Mutex**

### 2.1 Token Family Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                   TOKEN FAMILY MODEL                         │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Login → RT_1 (family: F_abc123, gen: 1)                    │
│                                                              │
│  Tab A refreshes:                                            │
│    RT_1 → validated → RT_2 issued (gen: 2)                   │
│    RT_1 marked "rotated" with 10s grace window               │
│                                                              │
│  Tab B refreshes (within 10s):                               │
│    RT_1 → found as "rotated" within grace → ALLOWED          │
│    RT_2 already exists → return RT_2 (no new token issued)   │
│    Tab B gets same RT_2, no conflict                         │
│                                                              │
│  Attacker uses RT_1 (outside grace window):                  │
│    RT_1 → found as "rotated" OUTSIDE grace → THEFT DETECTED  │
│    Revoke ENTIRE family F_abc123 → all sessions terminated   │
│    Alert user, force re-authentication                       │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 Refresh Token Data Model

```sql
CREATE TABLE refresh_tokens (
    token_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token_hash      BYTEA NOT NULL,              -- Argon2id hash of the token
    family_id       UUID NOT NULL,               -- groups all tokens from one login
    user_id         UUID NOT NULL REFERENCES users(id),
    device_id       UUID NOT NULL,
    generation      INTEGER NOT NULL,            -- increments on each rotation
    state           TEXT NOT NULL DEFAULT 'active',
        -- 'active'    : current valid token
        -- 'rotated'   : replaced, within grace window
        -- 'revoked'   : explicitly invalidated
        -- 'compromised': theft detected, family revoked
    rotated_at      TIMESTAMPTZ,                 -- when state changed to 'rotated'
    grace_expires   TIMESTAMPTZ,                 -- rotated_at + grace_window
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at      TIMESTAMPTZ NOT NULL,        -- hard expiry (7 days from creation)
    ip_hash         BYTEA,                       -- IP at time of issuance
    device_fingerprint_hash BYTEA,

    INDEX idx_refresh_family (family_id),
    INDEX idx_refresh_user (user_id),
    INDEX idx_refresh_hash (token_hash)
);
```

### 2.3 Mutex-Based Refresh Implementation

The mutex prevents concurrent requests from creating duplicate tokens:

```python
import asyncio
from datetime import timedelta

class RefreshTokenService:
    """Refresh token rotation with mutex, grace window, and family tracking."""

    GRACE_WINDOW = timedelta(seconds=10)
    MAX_CONCURRENT_REFRESH = 5  # per family, to prevent abuse

    async def refresh(
        self,
        raw_token: str,
        context: AuthContext
    ) -> TokenPair:
        """
        Rotate refresh token with race condition protection.

        Flow:
        1. Acquire mutex per token family (prevents concurrent rotation)
        2. Validate token
        3. Check state (active, rotated-within-grace, revoked, compromised)
        4. Issue new token pair or reuse existing new token
        5. Release mutex
        """

        # Step 1: Look up token and extract family ID
        token_hash = argon2_hash(raw_token)
        token_record = await self.db.find_by_hash(token_hash)

        if not token_record:
            raise InvalidTokenError("Token not found")

        family_id = token_record.family_id

        # Step 2: Acquire mutex per token family
        # This ensures only ONE refresh happens at a time per login session
        async with self._family_mutex(family_id):
            return await self._do_refresh(token_record, raw_token, context)

    async def _do_refresh(
        self,
        token_record: RefreshTokenRecord,
        raw_token: str,
        context: AuthContext
    ) -> TokenPair:
        """Core refresh logic, protected by family mutex."""

        # --- VALIDATION ---

        # Check hard expiry
        if token_record.expires_at < now():
            await self._revoke_family(token_record.family_id, reason="hard_expiry")
            raise TokenExpiredError("Token expired")

        # Check if token was already rotated
        if token_record.state == "rotated":
            grace_still_valid = (
                token_record.grace_expires
                and token_record.grace_expires > now()
            )

            if grace_still_valid:
                # Race condition: another tab already rotated this token
                # Return the SAME new token that was already issued
                latest_token = await self.db.get_active_token(token_record.family_id)
                if latest_token:
                    # Don't issue a new token — reuse the existing one
                    return TokenPair(
                        access_token=await self._issue_access_token(
                            token_record.user_id, context
                        ),
                        refresh_token=None,  # client already has the new RT
                    )

            # Outside grace window — this is likely a stolen token
            await self._revoke_family(
                token_record.family_id,
                reason="rotated_token_reuse_outside_grace"
            )
            await self._alert_user(
                token_record.user_id,
                event="possible_token_theft",
                detail="Rotated refresh token used outside grace window"
            )
            raise TokenCompromisedError("Token family revoked — possible theft")

        if token_record.state in ("revoked", "compromised"):
            # If ANY revoked token in a family is used, revoke the whole family
            # This catches tokens stolen before rotation occurred
            await self._revoke_family(
                token_record.family_id,
                reason="revoked_token_reuse"
            )
            raise TokenRevokedError("Token revoked")

        if token_record.state != "active":
            raise InvalidTokenError(f"Unexpected token state: {token_record.state}")

        # --- VALIDATE BINDING ---

        if not self._validate_binding(token_record, context):
            await self._revoke_family(
                token_record.family_id,
                reason="binding_mismatch"
            )
            raise BindingMismatchError("Token binding validation failed")

        # --- ROTATE ---

        # Mark current token as rotated (with grace window)
        await self.db.update_state(
            token_id=token_record.token_id,
            state="rotated",
            rotated_at=now(),
            grace_expires=now() + self.GRACE_WINDOW,
        )

        # Generate new refresh token
        new_raw_token = secrets.token_urlsafe(48)  # 384-bit entropy
        new_token_hash = argon2_hash(new_raw_token)

        await self.db.create(
            token_hash=new_token_hash,
            family_id=token_record.family_id,  # same family
            user_id=token_record.user_id,
            device_id=context.device_id,
            generation=token_record.generation + 1,
            state="active",
            expires_at=now() + timedelta(days=7),
            ip_hash=hash_ip(context.ip_address),
            device_fingerprint_hash=hash_fp(context.device_fingerprint),
        )

        # Issue new access token
        access_token = await self._issue_access_token(
            token_record.user_id, context
        )

        return TokenPair(
            access_token=access_token,
            refresh_token=new_raw_token,
        )

    # --- MUTEX IMPLEMENTATION ---

    def _family_mutex(self, family_id: str) -> asyncio.Lock:
        """
        Per-family mutex to prevent concurrent refresh race conditions.

        Uses a dict of locks keyed by family_id.
        Locks are cleaned up after use to prevent memory leaks.
        """
        if family_id not in self._locks:
            self._locks[family_id] = asyncio.Lock()
        return self._locks[family_id]

    # Note: In production with multiple server instances, use Redis-based
    # distributed locks (e.g., Redlock) instead of in-memory asyncio.Lock.
    # For single-instance deployments, asyncio.Lock is sufficient.
```

### 2.4 Distributed Lock for Multi-Instance Deployments

For production with multiple auth server replicas:

```python
import redis.asyncio as redis

class DistributedRefreshLock:
    """Redis-based distributed lock for refresh token rotation."""

    LOCK_TTL = 5  # seconds — prevents deadlocks if process crashes

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    async def acquire(self, family_id: str) -> bool:
        """Acquire lock for token family. Returns True if acquired."""
        key = f"refresh_lock:{family_id}"
        return await self.redis.set(
            key, "locked", nx=True, ex=self.LOCK_TTL
        )

    async def release(self, family_id: str):
        """Release lock for token family."""
        key = f"refresh_lock:{family_id}"
        await self.redis.delete(key)

    @asynccontextmanager
    async def family_lock(self, family_id: str):
        """Context manager for family-scoped locking."""
        retries = 0
        max_retries = 10
        retry_delay = 0.05  # 50ms

        while retries < max_retries:
            if await self.acquire(family_id):
                try:
                    yield
                finally:
                    await self.release(family_id)
                return
            retries += 1
            await asyncio.sleep(retry_delay * (2 ** retries))  # exponential backoff

        raise LockAcquisitionError(
            f"Could not acquire lock for family {family_id} after {max_retries} retries"
        )
```

### 2.5 Grace Window Behavior Summary

| Scenario | Grace Window | Behavior |
|----------|-------------|----------|
| Tab A refreshes, Tab B refreshes 3s later | ✅ Within 10s | Tab B gets same new token, no conflict |
| Tab A refreshes, Tab B refreshes 15s later | ❌ Outside 10s | Tab B's old token rejected, must use new one |
| Attacker replays old token 30s later | ❌ Outside 10s | Token family revoked, user alerted |
| Attacker replays old token 5s later | ✅ Within 10s | Returns same new token, no new access granted |
| Legitimate token reuse (slow network) | ✅ Within 10s | Transparent to user |

### 2.6 Family Revocation on Theft Detection

```python
async def _revoke_family(self, family_id: str, reason: str):
    """
    Revoke ALL tokens in a family.

    Called when:
    - Rotated token reused outside grace window (theft)
    - Revoked token reused (replay attack)
    - Binding mismatch (token used from different device/IP)
    - User triggers "logout all devices"
    """
    await self.db.update_family(
        family_id=family_id,
        state="compromised",
        revoke_reason=reason,
    )

    # Also invalidate all active sessions for this family
    sessions = await self.db.get_sessions_by_family(family_id)
    for session in sessions:
        await self.session_manager.destroy(session.session_id, reason=reason)

    # Audit log
    await self.audit.log(
        event="token_family_revoked",
        family_id=family_id,
        reason=reason,
        affected_sessions=len(sessions),
    )
```

---

## 3. F-01 — Refresh Token Cookie Attributes

**Problem:** The architecture mentions `httpOnly` cookies in penetration test acceptance criteria but does not mandate specific cookie attributes as implementation requirements. If refresh tokens are stored in `localStorage` or accessible JavaScript variables, XSS attacks can exfiltrate them.

**Fix: Mandate Cookie Attributes as Non-Negotiable Security Requirements**

### 3.1 Cookie Attribute Specification

```yaml
# Web client — refresh token storage
# THIS IS A NON-NEGOTIABLE SECURITY REQUIREMENT

refresh_token_cookie:
  # --- REQUIRED ATTRIBUTES (no exceptions) ---

  HttpOnly: true
    # Prevents JavaScript access via document.cookie
    # Mitigates XSS token exfiltration
    # OWASP ASVS 4.0 §3.4.1

  Secure: true
    # Cookie sent only over HTTPS
    # Prevents MITM token interception on HTTP
    # Required for __Host- prefix

  SameSite: Strict
    # Cookie NEVER sent on cross-site requests
    # Strongest CSRF protection
    # Prevents token leakage via links, forms, iframes from other sites
    # Note: breaks OAuth2 redirect flows — use SameSite=Lax for
    #        the OAuth callback endpoint ONLY if needed

  Path: "/"
    # Cookie available for all API paths under the domain

  Max-Age: 604800
    # 7 days — matches refresh token lifetime
    # Cookie expires when token expires

  # --- RECOMMENDED: __Host- PREFIX ---
  # Use __Host-refresh_token as the cookie name
  # This prefix ENFORCES:
  #   - Secure: true (required)
  #   - Path: "/" (required)
  #   - No Domain attribute (prevents subdomain sharing)
  # Browser rejects the cookie if any of these are violated

  Name: "__Host-refresh_token"
    # __Host- prefix provides defense-in-depth
    # Even if a developer accidentally removes Secure flag,
    # the browser will reject the cookie without it

# --- ACCESS TOKEN STORAGE ---
# Access tokens MUST NOT be persisted anywhere

access_token_storage:
  mechanism: "javascript_variable_only"
  location: "In-memory JS variable (e.g., closure, module scope)"
  persistence: NONE
  lifetime: 900  # 15 minutes
  refresh_mechanism: "Silent refresh via httpOnly cookie"
  note: "Lost on page refresh — this is intentional and correct"

# --- PROHIBITED STORAGE (audit these pre-launch) ---
prohibited_storage:
  - localStorage    # Accessible via JS — XSS exfiltration risk
  - sessionStorage  # Accessible via JS — XSS exfiltration risk
  - IndexedDB       # Accessible via JS — XSS exfiltration risk
  - Non-httpOnly cookies  # Accessible via document.cookie
  - URL parameters        # Logged in server/proxy logs
  - URL fragments         # Accessible via JS
```

### 3.2 Set-Cookie Header Examples

```http
# Refresh token response
HTTP/1.1 200 OK
Set-Cookie: __Host-refresh_token=eyJhbG...; Max-Age=604800; Path=/; Secure; HttpOnly; SameSite=Strict

# Access token returned in response body (NOT in cookie)
Content-Type: application/json
{
    "access_token": "eyJhbG...",
    "expires_in": 900,
    "token_type": "Bearer"
}
```

### 3.3 SameSite=Strict Impact and Mitigation

`SameSite=Strict` means the cookie is NEVER sent on cross-origin requests. This has implications:

| Scenario | Impact | Mitigation |
|----------|--------|------------|
| User clicks link to app from email | Cookie not sent on navigation | App detects no session, redirects to login — acceptable |
| OAuth2 callback from broker | Cookie not sent on redirect | Use `SameSite=Lax` for the callback endpoint ONLY, or handle via POST with CSRF token |
| Embedded in iframe on other site | Cookie not sent | This is the desired behavior — prevent framing |
| API call from same origin | Cookie sent normally | No impact |

**For OAuth2 Callbacks:** If the app uses OAuth2 for broker connections (e.g., Interactive Brokers, OANDA), the callback redirect needs session context. Solutions:

```yaml
oauth2_callback_handling:
  option_1: "Use SameSite=Lax for the callback endpoint only"
    # Lax allows cookies on top-level navigations (redirects)
    # but blocks cross-site POST/iframe
    # Acceptable for OAuth2 redirect callbacks

  option_2: "Use POST-based callback with CSRF token"
    # OAuth2 provider POSTs back with authorization code
    # Include CSRF token in state parameter, validate on callback
    # Keeps SameSite=Strict on all cookies

  recommended: option_2
    # Maintains strictest cookie policy
    # CSRF protection via state parameter is standard OAuth2 practice
```

### 3.4 Content Security Policy (CSP) Alignment

The cookie protections should be complemented by CSP headers that limit XSS risk:

```yaml
# CSP headers for the web application
content_security_policy:
  default-src: "'self'"
  script-src: "'self'"  # No inline scripts, no eval
  connect-src: "'self' https://api.alphastack.io wss://ws.alphastack.io"
  frame-ancestors: "'none'"  # Prevent clickjacking
  base-uri: "'self'"
  form-action: "'self'"

  # This CSP makes XSS harder, providing defense-in-depth
  # Even if XSS occurs, httpOnly cookies are still protected
```

### 3.5 Pre-Launch Verification Checklist

```markdown
## Cookie Security Verification (run before EVERY release)

- [ ] Refresh token cookie has `HttpOnly: true`
- [ ] Refresh token cookie has `Secure: true`
- [ ] Refresh token cookie has `SameSite=Strict` (or `Lax` for OAuth callback only)
- [ ] Refresh token cookie uses `__Host-` prefix
- [ ] No tokens stored in `localStorage` (grep all JS/TS source)
- [ ] No tokens stored in `sessionStorage` (grep all JS/TS source)
- [ ] No tokens in non-httpOnly cookies (check Set-Cookie headers)
- [ ] Access token exists only in JS memory (not persisted)
- [ ] CSP headers present and correct
- [ ] Cookie scope matches domain (no wildcard Domain)
- [ ] Verify in browser DevTools: Application → Cookies shows correct flags
- [ ] Verify with `curl -v` that Set-Cookie headers have all required attributes
```

### 3.6 Monitoring and Alerting

```yaml
cookie_security_monitoring:
  # Alert if any of these are detected in production responses:
  alerts:
    - name: "Missing HttpOnly on refresh cookie"
      condition: "Set-Cookie header for refresh_token without HttpOnly"
      severity: critical

    - name: "Missing Secure on refresh cookie"
      condition: "Set-Cookie header for refresh_token without Secure"
      severity: critical

    - name: "Missing SameSite on refresh cookie"
      condition: "Set-Cookie header for refresh_token without SameSite"
      severity: high

    - name: "Token in localStorage detected"
      condition: "CSP report or JS audit finds localStorage token"
      severity: critical

    - name: "Missing __Host- prefix"
      condition: "Set-Cookie header for refresh_token without __Host- prefix"
      severity: medium
```

---

## 4. Integration: How All Three Fixes Work Together

```
┌─────────────────────────────────────────────────────────────────────┐
│              COMPLETE SESSION LIFECYCLE (FIXED)                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐                                                   │
│  │ Login Request │                                                   │
│  └──────┬───────┘                                                   │
│         ▼                                                           │
│  [SID_A] Password Verified                                          │
│    ├─ DESTROY SID_A (F-10: prevent fixation)                        │
│    ├─ CREATE SID_B (F-10: new session)                              │
│    ├─ Issue partial_token (5min, single-use)                        │
│    └─ Set-Cookie: __Host-session_id=SID_B (F-01: httpOnly+Secure)  │
│         ▼                                                           │
│  [SID_B] TOTP Verified                                              │
│    ├─ DESTROY SID_B (F-10: prevent fixation)                        │
│    ├─ CREATE SID_C (F-10: new session)                              │
│    ├─ Issue access_token (15min, in-memory)                         │
│    ├─ Issue refresh_token (7d, in token family)                     │
│    ├─ Set-Cookie: __Host-refresh_token=RT_1 (F-01: strict attrs)   │
│    └─ Set-Cookie: __Host-session_id=SID_C                           │
│         ▼                                                           │
│  [Authenticated] Tab A calls refresh                                │
│    ├─ ACQUIRE family mutex (F-02: prevent race)                     │
│    ├─ Validate RT_1 → mark as "rotated" + 10s grace                 │
│    ├─ Issue RT_2 (same family, gen+1)                               │
│    ├─ Issue new access_token                                        │
│    ├─ Set-Cookie: __Host-refresh_token=RT_2 (F-01: strict attrs)   │
│    └─ RELEASE mutex                                                 │
│         ▼                                                           │
│  [Authenticated] Tab B calls refresh (within 10s)                   │
│    ├─ ACQUIRE family mutex (F-02: waits for Tab A)                  │
│    ├─ Validate RT_1 → found "rotated" within grace                  │
│    ├─ Return existing RT_2 (no new token)                           │
│    ├─ Issue new access_token                                        │
│    └─ RELEASE mutex                                                 │
│         ▼                                                           │
│  [Attacker] Replays RT_1 (outside grace)                            │
│    ├─ Validate RT_1 → found "rotated" OUTSIDE grace                 │
│    ├─ REVOKE entire family (F-02: theft detection)                  │
│    ├─ DESTROY all sessions (F-10: kill all)                         │
│    ├─ ALERT user                                                    │
│    └─ Force re-authentication                                       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 5. Testing Requirements

### 5.1 Session Fixation Tests

| Test | Expected Result |
|------|----------------|
| Pre-set session cookie before login | Cookie invalidated after password verify |
| Replay old session ID after 2FA | Old SID returns 401 |
| Two rapid login attempts | Each gets unique session ID |
| Session ID in URL parameter | Rejected (must be in cookie only) |

### 5.2 Refresh Token Race Condition Tests

| Test | Expected Result |
|------|----------------|
| Two tabs refresh simultaneously | Both succeed, same new token issued |
| Old token replayed within 10s grace | Returns same new token, no error |
| Old token replayed after 15s | Token family revoked, user alerted |
| 100 concurrent refresh requests | Mutex serializes them, no duplicate tokens |
| Server crash during refresh | Distributed lock expires (5s TTL), no deadlock |

### 5.3 Cookie Attribute Tests

| Test | Expected Result |
|------|----------------|
| Inspect Set-Cookie header | Has HttpOnly, Secure, SameSite=Strict, __Host- prefix |
| JS attempts `document.cookie` | Refresh token not visible |
| HTTP (non-HTTPS) request | Cookie not sent |
| Cross-site request from other domain | Cookie not sent |
| Cookie without __Host- prefix | Browser rejects it |

---

## 6. Implementation Priority

| Priority | Fix | Effort | Blocks Launch? |
|----------|-----|--------|----------------|
| **P0** | F-10: Session regeneration in 2FA flow | Medium | ✅ Yes |
| **P0** | F-01: Cookie attributes mandated | Low | ✅ Yes |
| **P1** | F-02: Refresh token mutex + grace window | High | ✅ Yes |
| **P1** | F-02: Distributed lock (multi-instance) | Medium | Before scaling |
| **P2** | Monitoring and alerting | Low | Before production |

---

*This document addresses ONLY session management fixes. For TOTP memory exposure (F-05), partial token design (F-06), biometric fallback (F-08), and other findings, see `fix_security_auth.md`.*
