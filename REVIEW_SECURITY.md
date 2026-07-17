# AlphaStack Security Audit Report

**Date:** 2026-07-17  
**Scope:** Full codebase security review  
**Auditor:** Automated Security Audit Agent  
**Classification:** CONFIDENTIAL — For internal use only

---

## Executive Summary

AlphaStack has a well-designed security architecture on paper (the `security/` module shows thoughtful design with Argon2id, AES-256-GCM, RS256 JWT, TOTP 2FA, audit hash-chains). However, **the production server (`live_server.py`) does not use most of this infrastructure.** It implements a stripped-down auth system with critical vulnerabilities. This gap between designed security and deployed security is the single biggest risk.

**Risk Rating: HIGH** — This system handles real money and has multiple exploitable weaknesses.

---

## A. Critical Vulnerabilities

### A1. Hardcoded JWT Secret Fallback — `CRITICAL`

**File:** `live_server.py:682-685`

```python
_JWT_SECRET = os.environ.get("ALPHASTACK_JWT_SECRET")
if not _JWT_SECRET:
    _JWT_SECRET = hashlib.sha256(b"alphastack-dev-secret-v1").hexdigest()
```

**Impact:** If `ALPHASTACK_JWT_SECRET` is not set (or Fly.io secrets fail to propagate — see C3), the JWT signing secret is a **deterministic value visible in source code**. Any attacker can forge valid JWT tokens and gain full API access, including the ability to place trades with real money.

**Severity:** CRITICAL — Full authentication bypass.

### A2. Hardcoded Encryption Master Key Fallback — `CRITICAL`

**File:** `encryption.py:240-242`

```python
# Dev fallback – deterministic key (NEVER use in production)
return hashlib.sha256(b"alphastack-dev-master-key").digest()
```

**Impact:** If `ALPHASTACK_MASTER_KEY` is not set, all encrypted credentials (broker API keys, passwords, TOTP secrets) are encrypted with a key derivable from publicly visible source code. An attacker with access to the encrypted credential files can decrypt everything.

**Severity:** CRITICAL — Complete credential compromise.

### A3. HS256 JWT Instead of RS256 — `CRITICAL`

**File:** `live_server.py:691,699,703`

```python
_JWT_ALGO = "HS256"
# ...
return jwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALGO)
return jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGO])
```

**Impact:** The security module (`auth.py`) correctly implements RS256 with asymmetric keys. But `live_server.py` uses HS256 with a symmetric secret. This means:
- The same secret is used for signing AND verification
- If the secret leaks (see A1), tokens can be forged
- No key rotation support
- No JWKS endpoint for key distribution

**Severity:** CRITICAL — Combined with A1, this is a complete auth bypass.

### A4. Username Comparison Not Constant-Time — `HIGH`

**File:** `live_server.py:730`

```python
if uname != _ADMIN_USER or not hmac.compare_digest(_ADMIN_HASH, hashlib.sha256(pwd.encode()).hexdigest()):
```

**Impact:** The password hash comparison uses `hmac.compare_digest` (good), but the username comparison uses `!=` (bad). This leaks timing information about the valid username. An attacker can enumerate the admin username character by character.

**Severity:** HIGH — Username enumeration via timing attack.

---

## B. Authentication & Authorization

### B1. Dual Auth Systems — Confusion Risk — `HIGH`

The codebase has **two completely separate auth implementations**:

| Feature | `security/auth.py` (designed) | `live_server.py` (deployed) |
|---|---|---|
| Algorithm | RS256 (asymmetric) | HS256 (symmetric) |
| Password hashing | Argon2id | SHA-256 (!) |
| 2FA | TOTP with backup codes | None |
| Sessions | Server-side with device binding | None (stateless) |
| Rate limiting | Token-bucket with blocking | Simple sliding window |
| Key rotation | Supported | Not supported |

**Impact:** The production server uses **SHA-256 for password verification** (via `hmac.compare_digest` of SHA-256 hash), not Argon2id. SHA-256 is not a password hashing function — it's fast and vulnerable to brute-force/rainbow table attacks.

**Severity:** HIGH — Weak password storage in production.

### B2. Single Admin Account — `MEDIUM`

```python
_ADMIN_USER = os.environ.get("ALPHASTACK_ADMIN_USER", "")
_ADMIN_HASH = os.environ.get("ALPHASTACK_ADMIN_HASH", "")
```

**Impact:** Only one admin user is supported. No role-based access control (RBAC). No user registration. No multi-user support. The designed `auth.py` has roles and tiers, but none of it is wired into production.

**Severity:** MEDIUM — No access control granularity.

### B3. In-Memory Token Blocklist — `HIGH`

```python
_TOKEN_BLOCKLIST: set[str] = set()
_TOKEN_BLOCKLIST_MAX: int = 10000
```

**Impact:**
- **Lost on restart:** All revoked tokens become valid again after server restart
- **Arbitrary eviction:** `set.pop()` removes an arbitrary element, not the oldest. This means revoked tokens may be removed while newer ones stay, or vice versa
- **No persistence:** No Redis/DB backing — single-instance only
- **Bounded size:** 10K limit means blocklist can overflow under heavy logout/refresh activity

**Severity:** HIGH — Token revocation is unreliable.

### B4. No Session Management in Production — `HIGH`

The designed `SessionManager` in `auth.py` tracks sessions with device binding, IP hashing, and revocation. The production server has **none of this**. Tokens are stateless — there's no way to:
- Track active sessions
- Revoke all sessions for a user
- Detect session hijacking
- Enforce concurrent session limits

**Severity:** HIGH — No session control for a real-money trading system.

### B5. Refresh Token Rotation — Partial Implementation — `MEDIUM`

```python
# One-time-use: revoke old refresh token
old_jti = payload.get("jti", "")
if old_jti:
    if len(_TOKEN_BLOCKLIST) >= _TOKEN_BLOCKLIST_MAX:
        _TOKEN_BLOCKLIST.pop()  # Arbitrary removal!
    _TOKEN_BLOCKLIST.add(old_jti)
```

**Impact:** Refresh token rotation is attempted but:
- `set.pop()` is non-deterministic (removes arbitrary element)
- Blocklist is in-memory (lost on restart)
- No detection of refresh token reuse (theft detection)

**Severity:** MEDIUM — Refresh token theft is undetectable.

---

## C. Secrets Management

### C1. Broker Credentials in Environment Variables — `MEDIUM`

```python
BINANCE_API_KEY = _sanitize_str(os.environ.get("BINANCE_API_KEY", ""))
BINANCE_API_SECRET = _sanitize_str(os.environ.get("BINANCE_API_SECRET", ""))
# ...
token = os.environ.get("OANDA_API_TOKEN", "")
account_id = os.environ.get("OANDA_ACCOUNT_ID", "")
```

**Impact:** Broker credentials (which control real money) are passed as plain environment variables. While this is common, it means:
- Credentials appear in `docker inspect`, `/proc/1/environ`, process listings
- Logs may inadvertently capture them
- No encryption at rest for env vars in the container

**Severity:** MEDIUM — Credential exposure in container environments.

### C2. No `.env.example` at Root — `LOW`

The `.env.example` exists at `infra/docker/.env.example` but not at the project root. The `config.py` reads `.env` from the working directory, but there's no root-level template showing required variables.

**Severity:** LOW — Configuration confusion.

### C3. Fly.io Secrets May Not Reach the App — `HIGH`

**File:** `fly.toml`

```toml
[env]
  PORT = "8000"
```

The `fly.toml` only sets `PORT` in the `[env]` section. All sensitive values (`ALPHASTACK_JWT_SECRET`, `BINANCE_API_KEY`, `OANDA_API_TOKEN`, etc.) must be set via `fly secrets set`. However:

1. **Fly secrets are not available during build** — `test_startup.py` runs during `docker build` (line: `RUN python3 test_startup.py`), which means it can't access Fly secrets. This likely causes build failures or forces test defaults.

2. **Secrets may not propagate** if the app reads them before the Fly runtime injects them (race condition during startup).

3. **No validation** — The app starts silently with fallback secrets if env vars are missing. There's no startup check that rejects missing critical secrets.

**Severity:** HIGH — Production may run with dev fallback secrets silently.

### C4. Sensitive Config Printed to Logs — `MEDIUM`

```python
# start.py:8
print(f"JWT_SECRET: {'set' if os.environ.get('ALPHASTACK_JWT_SECRET') else 'NOT SET'}")
# live_server.py:1702
print(f"🔑 JWT_SECRET set: {bool(os.environ.get('ALPHASTACK_JWT_SECRET'))}")
```

**Impact:** While the actual secret isn't printed, the boolean status is logged. Combined with the deterministic fallback, this tells an attacker whether they can exploit A1.

**Severity:** MEDIUM — Information disclosure.

---

## D. Input Validation

### D1. SQL Injection Defense is Regex-Based — `MEDIUM`

```python
_SQL_INJECTION_PATTERNS = [
    re.compile(r"(?i)\bunion\b.*\bselect\b"),
    re.compile(r"(?i)\bselect\b.*\bfrom\b"),
    # ...
]
```

**Impact:** The codebase uses regex pattern matching for SQL injection prevention. This is a defense-in-depth layer (the primary defense should be parameterized queries). However:
- The patterns can be bypassed with encoding tricks, comments, or case variations
- No evidence of actual SQL database usage in `live_server.py` (it uses in-memory stores)
- The patterns don't cover all injection vectors (e.g., `pg_sleep`, `WAITFOR`, stacked queries)

**Severity:** MEDIUM — Bypassable if database is added later.

### D2. WebSocket Auth — Token Verified Once, Never Refreshed — `HIGH`

```python
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return
    try:
        _decode_token(token)
    except Exception:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return
    # ... runs forever with no re-authentication
```

**Impact:**
- Token is verified only at connection time
- WebSocket connections are long-lived (hours/days)
- If a token is revoked after connection, the WebSocket remains active
- No check against the token blocklist
- Token passed as a query parameter (visible in server logs, browser history, proxy logs)

**Severity:** HIGH — Revoked tokens remain valid for active WebSocket sessions.

### D3. Trade Parameter Validation — Good but Incomplete — `MEDIUM`

The `InputValidator.validate_order()` is comprehensive for basic validation. However:
- No maximum order value check (a user could place a $10M order)
- No daily trade count/volume limits
- No symbol whitelist enforcement (regex allows any alphanumeric symbol)
- Stop-loss/take-profit validation doesn't check for reasonable ranges relative to current price

**Severity:** MEDIUM — Potential for abuse with extreme order parameters.

### D4. No Input Sanitization on Free-Text AI Chat — `MEDIUM`

```python
async def _cmd_fallback(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user_msg = update.message.text
    # ...
    response = await self._ai_model.chat(user_msg, system=system_prompt)
```

**Impact:** User-supplied text is passed directly to the AI model's system prompt construction. This could allow:
- Prompt injection attacks
- Information extraction about the system
- Manipulation of trading recommendations

**Severity:** MEDIUM — AI prompt injection risk.

---

## E. Telegram Bot Security

### E1. Chat ID Authorization — Basic but Functional — `MEDIUM`

```python
def is_authorized(self, chat_id: int | str) -> bool:
    if not self.allowed_chat_ids:
        return str(chat_id) == str(self.chat_id)
    return str(chat_id) in self.allowed_chat_ids
```

**Impact:**
- Authorization is chat-ID based, not user-based
- In group chats, any member of an authorized chat can execute commands
- No per-user authentication within authorized chats
- No audit trail of which user executed which command

**Severity:** MEDIUM — No per-user auth in group chats.

### E2. Notification Queue Sends to Fixed Chat — `LOW`

```python
await self._app.bot.send_message(
    chat_id=self.config.chat_id,
    text=text,
    parse_mode="Markdown",
)
```

**Impact:** All notifications go to a single chat ID. If this chat is a group, sensitive trading information (positions, P&L, signals) is visible to all group members.

**Severity:** LOW — Information disclosure in group contexts.

### E3. No Rate Limiting on Telegram Commands — `MEDIUM`

The Telegram bot has no rate limiting on command handlers. An authorized user (or compromised chat) could spam commands to:
- Overload the trading system
- Trigger excessive API calls to exchanges
- Cause denial of service

**Severity:** MEDIUM — DoS vector.

### E4. Markdown Injection — `LOW`

User messages and trade data are sent with `parse_mode="Markdown"`. If trade data contains Markdown special characters (`*`, `_`, `` ` ``), it could:
- Break message formatting
- Hide content in collapsed sections
- Create misleading display

**Severity:** LOW — Display manipulation.

---

## F. Cryptographic Issues

### F1. SecureString is Best-Effort Only — `LOW`

```python
class SecureString:
    def __del__(self) -> None:
        try:
            self._value = "\x00" * len(self._value)
        except Exception:
            pass
```

**Impact:** Python's garbage collector doesn't guarantee when `__del__` is called, and string interning means the original value may persist in memory. This is acknowledged in the code but worth noting — it's not true zeroization.

**Severity:** LOW — Known Python limitation.

### F2. Audit Hash Chain — Good Implementation — `INFO`

The `AuditLogger` implements a SHA-256 hash chain for tamper detection. This is well-implemented:
- Deterministic hashing with `sort_keys=True`
- Chain restoration from disk on startup
- Verification method for external auditors

**However:** The hash chain is only as secure as the storage. If an attacker can modify the log files, they can recompute the chain. No external notarization (e.g., blockchain anchoring) is implemented.

### F3. Key Rotation Design is Good — `INFO`

The `EncryptionService` supports key versioning with grace periods. DEK wrapping with a master key is correct. The design is solid; the issue is the hardcoded fallback master key (see A2).

### F4. Quantum-Ready Module is Placeholder — `LOW`

```python
def encrypt_hybrid(self, data: bytes, public_key: dict) -> bytes:
    return data  # Placeholder - actual implementation needed
```

**Impact:** The quantum-ready security module contains only placeholder implementations. While not a current vulnerability, it provides false confidence that post-quantum protection exists.

**Severity:** LOW — Misleading code.

---

## G. Compliance Concerns

### G1. No Real CMA Licensing — `HIGH`

The compliance module acknowledges this:
> "This service is provided by a software tool and is not a CMA-licensed investment advisory service."

**Impact:** For a system that executes trades with real money:
- No CMA license for investment advisory
- No client money segregation
- No investor compensation fund participation
- No regulatory reporting capability
- Risk disclosure exists but may not meet CMA formatting requirements

**Severity:** HIGH — Regulatory exposure.

### G2. GDPR/DPA Data Rights — Incomplete — `MEDIUM`

The `ComplianceManager` has methods for data access, erasure, and portability requests, but they only **record** the request — they don't actually process it:
```python
def handle_data_access_request(self, user_id: str) -> dict[str, Any]:
    request = {"user_id": user_id, "request_type": "data_access", ...}
    self._data_access_requests.append(request)
    return request  # Just records, doesn't fulfill
```

**Impact:** Data subject rights requests are acknowledged but not fulfilled. This violates GDPR Art. 15/17/20 and Kenya DPA.

**Severity:** MEDIUM — Regulatory non-compliance.

### G3. No Trade Reporting — `HIGH`

For a real-money trading system, there's no:
- Trade reporting to regulators
- Best execution documentation
- Transaction cost analysis
- Client suitability assessments
- Complaint handling procedure

**Severity:** HIGH — Missing regulatory requirements.

### G4. Data Retention Not Enforced — `MEDIUM`

The `audit.py` defines retention periods (2-7 years by category), but there's no actual deletion mechanism. Old audit logs accumulate indefinitely.

**Severity:** MEDIUM — Storage growth + potential data protection violation.

### G5. No Anti-Money Laundering (AML) Controls — `HIGH`

For a system handling real money:
- No KYC (Know Your Customer) verification
- No transaction monitoring for suspicious patterns
- No sanctions screening
- No AML reporting

**Severity:** HIGH — AML regulatory risk.

---

## H. Fix Recommendations

### H1. Eliminate Hardcoded Fallback Secrets — `CRITICAL FIX`

```python
# REPLACE in live_server.py:
_JWT_SECRET = os.environ.get("ALPHASTACK_JWT_SECRET")
if not _JWT_SECRET:
    raise RuntimeError(
        "FATAL: ALPHASTACK_JWT_SECRET environment variable is required. "
        "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
    )
```

```python
# REPLACE in encryption.py:
@staticmethod
def _load_master_key_from_env() -> bytes:
    b64 = os.environ.get("ALPHASTACK_MASTER_KEY", "")
    if not b64:
        raise RuntimeError(
            "FATAL: ALPHASTACK_MASTER_KEY environment variable is required. "
            "Generate one with: python -c \"import base64, os; print(base64.b64encode(os.urandom(32)).decode())\""
        )
    return base64.b64decode(b64)
```

### H2. Switch to RS256 or Use Proper Password Hashing — `CRITICAL FIX`

**Option A (recommended):** Wire up the existing `security/auth.py` RS256 + Argon2id implementation into `live_server.py`.

**Option B (minimum fix):** Replace SHA-256 password hashing with Argon2id in `live_server.py`:

```python
from argon2 import PasswordHasher
_ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)

# In login:
if not _ph.verify(stored_hash, password):
    raise HTTPException(401, "Invalid credentials")
```

### H3. Fix Token Blocklist — `HIGH FIX`

Replace in-memory blocklist with Redis or database:

```python
# Use Redis for token blocklist
import redis.asyncio as redis

_token_blocklist_redis = redis.Redis(host='localhost', port=6379, decode_responses=True)

async def _revoke_token(jti: str, ttl_seconds: int = 604800):
    await _token_blocklist_redis.setex(f"revoked:{jti}", ttl_seconds, "1")

async def _is_token_revoked(jti: str) -> bool:
    return await _token_blocklist_redis.exists(f"revoked:{jti}")
```

### H4. Add WebSocket Token Re-validation — `HIGH FIX`

```python
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return
    try:
        claims = _decode_token(token)
    except Exception:
        await websocket.close(code=4001, reason="Invalid token")
        return

    # Periodic re-validation
    last_check = time.time()
    CHECK_INTERVAL = 60  # Re-validate every 60 seconds

    try:
        while True:
            if time.time() - last_check > CHECK_INTERVAL:
                jti = claims.get("jti", "")
                if jti and jti in _TOKEN_BLOCKLIST:
                    await websocket.close(code=4001, reason="Token revoked")
                    return
                last_check = time.time()
            # ... send data ...
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
```

### H5. Add Startup Secret Validation — `HIGH FIX`

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Validate critical secrets at startup
    required_secrets = {
        "ALPHASTACK_JWT_SECRET": os.environ.get("ALPHASTACK_JWT_SECRET"),
        "BINANCE_API_KEY": os.environ.get("BINANCE_API_KEY"),
        "BINANCE_API_SECRET": os.environ.get("BINANCE_API_SECRET"),
    }
    missing = [k for k, v in required_secrets.items() if not v]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")
    # ... rest of startup
```

### H6. Fix `set.pop()` in Blocklist — `MEDIUM FIX`

```python
# Replace arbitrary pop with FIFO eviction
from collections import OrderedDict

_TOKEN_BLOCKLIST: OrderedDict[str, bool] = OrderedDict()
_TOKEN_BLOCKLIST_MAX: int = 10000

def _revoke_token(jti: str):
    if len(_TOKEN_BLOCKLIST) >= _TOKEN_BLOCKLIST_MAX:
        _TOKEN_BLOCKLIST.popitem(last=False)  # Remove oldest
    _TOKEN_BLOCKLIST[jti] = True
```

### H7. Add Telegram Rate Limiting — `MEDIUM FIX`

```python
from collections import defaultdict
import time

_command_timestamps: dict[str, list[float]] = defaultdict(list)

def _check_command_rate(user_id: str, limit: int = 10, window: int = 60) -> bool:
    now = time.time()
    _command_timestamps[user_id] = [
        t for t in _command_timestamps[user_id] if t > now - window
    ]
    if len(_command_timestamps[user_id]) >= limit:
        return False
    _command_timestamps[user_id].append(now)
    return True
```

### H8. Add Fly.io Secrets Validation — `MEDIUM FIX`

Add to `Dockerfile` or a startup script:

```python
# start.py
required = ["ALPHASTACK_JWT_SECRET", "BINANCE_API_KEY", "BINANCE_API_SECRET"]
missing = [k for k in required if not os.environ.get(k)]
if missing and os.environ.get("ALPHASTACK_ENV") == "prod":
    print(f"❌ FATAL: Missing production secrets: {', '.join(missing)}")
    print("Set them with: fly secrets set KEY=value")
    sys.exit(1)
```

### H9. Wire Up the Security Module — `HIGH FIX` (Architecture)

The biggest architectural fix is to **use the security module that was built:**

1. Replace `live_server.py`'s inline auth with `security/auth.py`'s `AuthManager`
2. Use `JWTManager` with RS256 instead of HS256
3. Use `CredentialVault` for broker credentials instead of env vars
4. Use `SessionManager` for session tracking
5. Use `AuditLogger` for trade audit trail
6. Wire `ComplianceManager` for geo-blocking and consent

### H10. Add Input Validation for AI Chat — `MEDIUM FIX`

```python
async def _cmd_fallback(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user_msg = update.message.text
    
    # Sanitize input
    if len(user_msg) > 2000:
        await update.message.reply_text("Message too long (max 2000 chars)")
        return
    
    # Strip potential prompt injection patterns
    from alphastack.security.validators import InputValidator
    check = InputValidator.sanitize_string(user_msg, max_length=2000, allow_html=False)
    if not check:
        await update.message.reply_text("Invalid input detected")
        return
    
    user_msg = check.sanitized
    # ... continue with AI chat
```

---

## Summary of Findings by Severity

| Severity | Count | Key Issues |
|----------|-------|------------|
| **CRITICAL** | 3 | Hardcoded JWT secret, Hardcoded encryption key, HS256 instead of RS256 |
| **HIGH** | 8 | SHA-256 passwords, in-memory blocklist, no session management, WebSocket auth, no startup validation, no CMA license, no AML, security module not wired |
| **MEDIUM** | 10 | Single admin, regex SQL injection, AI prompt injection, Telegram rate limiting, GDPR incomplete, data retention, set.pop() eviction |
| **LOW** | 3 | SecureString limits, quantum placeholder, no root .env.example |

---

## Priority Action Plan

1. **Immediate (before any production deployment):**
   - [ ] Eliminate hardcoded fallback secrets (A1, A2)
   - [ ] Add startup validation that refuses to start without required secrets
   - [ ] Switch from HS256 to RS256 or use the existing `auth.py` module

2. **Before handling real money:**
   - [ ] Wire up `security/auth.py` properly (Argon2id, sessions, 2FA)
   - [ ] Implement persistent token blocklist (Redis)
   - [ ] Add WebSocket token re-validation
   - [ ] Obtain CMA license or clearly document regulatory status

3. **Before public launch:**
   - [ ] Implement AML/KYC controls
   - [ ] Fulfill GDPR/DPA data rights requests
   - [ ] Add trade reporting capability
   - [ ] Add Telegram rate limiting
   - [ ] Implement proper data retention and deletion

---

*This audit identified 24 findings across 7 categories. The 3 critical findings should be addressed before any production deployment. The security module (`security/`) contains well-designed implementations that are not being used by the production server — wiring them in would resolve the majority of findings.*
