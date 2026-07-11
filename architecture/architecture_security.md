# Alpha Stack — Security Architecture

> **Version:** 1.0 · **Date:** 2026-07-11 · **Author:** Security Architect Agent
> **Scope:** Complete security architecture — authentication, encryption, API security, quantum-resistant cryptography, credential isolation, audit logging, and penetration testing
> **Design Philosophy:** Zero-trust by default, defense-in-depth everywhere, quantum-ready from day one

---

## Table of Contents

1. [Security Architecture Overview](#1-security-architecture-overview)
2. [Authentication System](#2-authentication-system)
3. [Credential Encryption & Storage](#3-credential-encryption--storage)
4. [API Security](#4-api-security)
5. [Quantum-Resistant Cryptography](#5-quantum-resistant-cryptography)
6. [Broker Credential Isolation](#6-broker-credential-isolation)
7. [Audit Logging](#7-audit-logging)
8. [Penetration Testing Strategy](#8-penetration-testing-strategy)
9. [Incident Response Plan](#9-incident-response-plan)
10. [Compliance Mapping](#10-compliance-mapping)
11. [Implementation Roadmap](#11-implementation-roadmap)

---

## 1. Security Architecture Overview

### 1.1 Threat Model

Alpha Stack faces five primary threat categories, ordered by severity:

| # | Threat Category | Attack Vectors | Impact | Likelihood |
|---|----------------|----------------|--------|------------|
| T1 | **Broker Credential Theft** | Malware, memory dumps, MITM, server breach | **Critical** — direct fund loss | High |
| T2 | **Account Takeover** | Credential stuffing, phishing, session hijack | **Critical** — unauthorized trading | High |
| T3 | **API Abuse** | Rate limit bypass, injection, CSRF, XSS | **High** — data exfiltration, manipulation | Medium |
| T4 | **Insider Threat** | Compromised employee, supply chain attack | **High** — data/fund exposure | Low-Medium |
| T5 | **Quantum Decryption** | Harvest-now-decrypt-later on stored data | **Critical** — retroactive decryption | Low (future) |

### 1.2 Defense-in-Depth Model

```
┌──────────────────────────────────────────────────────────────┐
│                    PERIMETER (LAYER 5)                        │
│  WAF · DDoS Protection · Geo-blocking · TLS 1.3 Termination  │
├──────────────────────────────────────────────────────────────┤
│                    API GATEWAY (LAYER 4)                      │
│  Rate Limiting · JWT Validation · CORS · CSP · Request Sanit. │
├──────────────────────────────────────────────────────────────┤
│                    APPLICATION (LAYER 3)                      │
│  RBAC · Input Validation · Output Encoding · CSPRNG           │
├──────────────────────────────────────────────────────────────┤
│                    DATA (LAYER 2)                             │
│  AES-256-GCM at Rest · Field-Level Encryption · Key Rotation │
├──────────────────────────────────────────────────────────────┤
│                    CREDENTIAL VAULT (LAYER 1)                 │
│  OS Keyring · HSM/KMS · Memory Zeroization · Process Isolation│
└──────────────────────────────────────────────────────────────┘
```

### 1.3 Zero-Trust Principles Applied

| Principle | Alpha Stack Implementation |
|-----------|---------------------------|
| **Never trust, always verify** | Every request authenticated + authorized, even internal service-to-service |
| **Least privilege** | RBAC with minimal permissions; broker creds scoped to specific accounts |
| **Assume breach** | Encrypted at rest + in transit; credential isolation limits blast radius |
| **Verify explicitly** | JWT claims validated on every call; no implicit session trust |
| **Micro-segmentation** | Broker credential vault isolated from application logic; separate process/container |

---

## 2. Authentication System

### 2.1 Architecture: Three-Layer Authentication

```
┌─────────────────────────────────────────────────────────────┐
│                    LAYER 1: IDENTITY                          │
│  Email + Password (Argon2id) · Social OAuth (optional)       │
│  Email Verification · Password Complexity Enforcement         │
├─────────────────────────────────────────────────────────────┤
│                    LAYER 2: SECOND FACTOR                     │
│  TOTP (RFC 6238) · WebAuthn/FIDO2 (hardware keys)           │
│  Biometric (mobile/desktop) · Backup Codes (8 single-use)    │
├─────────────────────────────────────────────────────────────┤
│                    LAYER 3: SESSION                            │
│  JWT Access Token (15 min) · Refresh Token (7 days)          │
│  Device Binding · IP Fingerprinting · Idle Timeout            │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 JWT Token Architecture

**Signing Algorithm:** RS256 (RSA + SHA-256) — asymmetric, so the auth server holds the private key and all services can verify with the public key.

```json
// Access Token Payload
{
  "header": {
    "alg": "RS256",
    "typ": "JWT",
    "kid": "as-key-2026-q3"          // Key ID for rotation
  },
  "payload": {
    "sub": "usr_a1b2c3d4",           // User ID (UUID)
    "email": "trader@example.com",
    "iss": "https://api.alphastack.io",
    "aud": "alphastack-app",
    "iat": 1752250800,
    "exp": 1752251700,                // 15 minutes
    "tier": "pro",
    "roles": ["trader", "api_access"],
    "email_verified": true,
    "2fa_verified": true,
    "device_id": "dev_x7y8z9",       // Device binding
    "ip_hash": "sha256:ab3f..."       // IP fingerprint (not raw IP)
  }
}
```

**Key Rotation Strategy:**
- RSA-4096 keypair for JWT signing
- New key generated every 90 days
- Old key retained for 30 days (grace period for in-flight tokens)
- `kid` header allows clients to fetch the correct public key from JWKS endpoint
- Emergency rotation: immediate key revocation + force re-authentication

### 2.3 Two-Factor Authentication (TOTP)

**Implementation:**

```
Enable 2FA Flow:
  1. Server generates TOTP secret (256-bit CSPRNG)
  2. Secret encrypted with user's derived key (AES-256-GCM)
  3. QR code rendered: otpauth://totp/AlphaStack:user@email?secret=XXX&issuer=AlphaStack
  4. User scans with authenticator app
  5. User enters verification code
  6. Server validates (±1 window tolerance = ±30 seconds)
  7. 8 backup codes generated (each hashed with Argon2id)
  8. Backup codes shown ONCE to user (never stored in plaintext)
  9. 2FA marked as enabled

Login with 2FA:
  Step 1: email + password → returns partial_token + requires_2fa: true
  Step 2: partial_token + TOTP code → returns full access_token + refresh_token
  Alternative: partial_token + backup_code → backup code invalidated after use
```

**Backup Code Handling:**
- 8 codes generated, each 8 characters (alphanumeric, excluding ambiguous chars)
- Each code hashed with Argon2id before storage
- Stored as `{ code_hash: "...", used: false, used_at: null }`
- After use, `used = true, used_at = now()`
- User can regenerate (invalidates all previous codes)

### 2.4 WebAuthn / FIDO2 (Phase 2)

For hardware security key support (YubiKey, Titan Key):

```
Registration:
  1. Client requests challenge from server
  2. Browser calls navigator.credentials.create() with challenge
  3. Hardware key generates keypair, signs challenge
  4. Public key + credential ID sent to server
  5. Server stores credential (user_id, credential_id, public_key, sign_count)

Authentication:
  1. Server sends challenge + allowed credentials
  2. Browser calls navigator.credentials.get()
  3. Hardware key signs challenge (requires physical touch)
  4. Server verifies signature + increments sign_count
  5. Full access token issued
```

### 2.5 Biometric Authentication (Mobile/Desktop)

```
Desktop (Tauri):
  - Windows Hello (fingerprint / face)
  - macOS Touch ID / Face ID
  - Linux: fingerprint via fprintd (where available)
  - Biometric unlocks OS Keyring → retrieves refresh token → silent re-auth

Mobile (Future):
  - iOS: Face ID / Touch ID via LocalAuthentication framework
  - Android: BiometricPrompt API (fingerprint, face, iris)
  - Biometric unlocks Keystore → retrieves stored credentials
```

### 2.6 Session Management

```python
# Session Data Model
@dataclass
class Session:
    session_id: UUID
    user_id: UUID
    device_id: str                # SHA-256 hash of device fingerprint
    device_name: str              # "Chrome on Windows" / "Tauri Desktop"
    ip_address: str               # Hashed for privacy
    user_agent: str
    refresh_token_hash: str       # Argon2id hash of refresh token
    created_at: datetime
    expires_at: datetime
    last_active_at: datetime
    is_revoked: bool
    revoke_reason: Optional[str]  # "password_change", "user_logout_all", "suspicious"

# Session Limits
MAX_SESSIONS_PER_USER = 10
IDLE_TIMEOUT_WEB = 15 * 60       # 15 minutes
IDLE_TIMEOUT_DESKTOP = 4 * 60 * 60  # 4 hours
IDLE_TIMEOUT_MOBILE = 30 * 60    # 30 minutes
REFRESH_TOKEN_LIFETIME = 7 * 24 * 60 * 60  # 7 days
```

**Session Invalidation Triggers:**
- Password change → all sessions except current
- 2FA enabled/disabled → all sessions except current
- "Logout all devices" → all sessions
- Suspicious activity detected → targeted session
- Refresh token rotation → old token invalidated (one-time use)

### 2.7 Password Policy

```yaml
password_policy:
  min_length: 12
  max_length: 128
  require_uppercase: true
  require_lowercase: true
  require_digit: true
  require_special: true
  # Banned patterns
  disallow_common_passwords: true    # Check against HaveIBeenPwned (k-anonymity)
  disallow_email_in_password: true
  disallow_sequential_chars: 4       # "abcd", "1234"
  disallow_repeated_chars: 3         # "aaa"
  # Hashing
  algorithm: argon2id
  memory_cost: 65536                 # 64 MB
  time_cost: 3
  parallelism: 4
  salt_length: 16
  # History
  password_history: 5                # Cannot reuse last 5 passwords
  min_age: 1 day                     # Minimum time before password change
  max_age: 365 days                  # Force rotation annually
```

---

## 3. Credential Encryption & Storage

### 3.1 Encryption Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                 ENCRYPTION KEY HIERARCHY                          │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │  MASTER KEY (HSM / KMS / Device Secure Enclave)         │     │
│  │  - Never exposed to application code                     │     │
│  │  - Managed by infrastructure (AWS KMS / HashiCorp Vault) │     │
│  └──────────────────────┬──────────────────────────────────┘     │
│                         │ derive                                 │
│  ┌──────────────────────▼──────────────────────────────────┐     │
│  │  DATA ENCRYPTION KEY (DEK)                               │     │
│  │  - AES-256-GCM per-tenant / per-user                     │     │
│  │  - Rotated every 90 days                                 │     │
│  │  - Stored encrypted (wrapped by Master Key)              │     │
│  └──────────────────────┬──────────────────────────────────┘     │
│                         │ encrypt                                │
│  ┌──────────────────────▼──────────────────────────────────┐     │
│  │  ENCRYPTED DATA                                         │     │
│  │  - Broker credentials, API keys, TOTP secrets            │     │
│  │  - Each field: nonce(12B) + ciphertext + tag(16B)        │     │
│  └─────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 OS Keyring Integration (Desktop — Rust)

Broker credentials are stored in the operating system's native secure storage. They **never** touch disk in plaintext and **never** leave the device.

```rust
// Cargo.toml dependencies
// keyring = "3"         // Cross-platform keyring
// zeroize = "1"         // Secure memory zeroing
// age = "0.11"          // File-based encryption fallback
// ring = "0.17"         // Cryptographic primitives

use keyring::Entry;
use zeroize::Zeroize;

const SERVICE_NAME: &str = "com.alphastack.credentials";

/// Store broker credentials in OS keyring
/// 
/// Platform backends:
/// - Windows:  Windows Credential Manager (DPAPI-protected)
/// - macOS:    Keychain Services (user password + ACL)
/// - Linux:    Secret Service / GNOME Keyring / KWallet (login password)
pub fn store_broker_credential(
    account_id: &str,
    credential_type: &str,  // "server", "login", "password", "api_key", "api_secret"
    value: &str,
) -> Result<(), SecurityError> {
    let entry = Entry::new(SERVICE_NAME, &format!("{account_id}.{credential_type}"))
        .map_err(|e| SecurityError::KeyringError(e.to_string()))?;
    
    entry.set_password(value)
        .map_err(|e| SecurityError::KeyringError(e.to_string()))?;
    
    Ok(())
}

/// Retrieve broker credential from OS keyring
pub fn load_broker_credential(
    account_id: &str,
    credential_type: &str,
) -> Result<String, SecurityError> {
    let entry = Entry::new(SERVICE_NAME, &format!("{account_id}.{credential_type}"))
        .map_err(|e| SecurityError::KeyringError(e.to_string()))?;
    
    entry.get_password()
        .map_err(|e| SecurityError::KeyringError(e.to_string()))
}

/// Delete broker credential from OS keyring
pub fn delete_broker_credential(
    account_id: &str,
    credential_type: &str,
) -> Result<(), SecurityError> {
    let entry = Entry::new(SERVICE_NAME, &format!("{account_id}.{credential_type}"))
        .map_err(|e| SecurityError::KeyringError(e.to_string()))?;
    
    entry.delete_credential()
        .map_err(|e| SecurityError::KeyringError(e.to_string()))
}

/// Secure memory wrapper — zeros buffer after use
pub struct SecureString {
    data: Vec<u8>,
}

impl SecureString {
    pub fn new(s: &str) -> Self {
        Self { data: s.as_bytes().to_vec() }
    }
    
    pub fn as_str(&self) -> &str {
        std::str::from_utf8(&self.data).unwrap_or("")
    }
}

impl Drop for SecureString {
    fn drop(&mut self) {
        self.data.zeroize();
    }
}
```

### 3.3 Encrypted File Fallback

When the OS keyring is unavailable (headless Linux server, container):

```rust
use age::secrecy::Secret;
use std::fs;

/// Derive encryption key from master password or device entropy
fn derive_key(master_password: &str, salt: &[u8]) -> [u8; 32] {
    use argon2::{Argon2, Algorithm, Version, Params};
    
    let mut key = [0u8; 32];
    let params = Params::new(65536, 3, 4, Some(32)).unwrap();
    let argon2 = Argon2::new(Algorithm::Argon2id, Version::V0x13, params);
    argon2.hash_password_into(master_password.as_bytes(), salt, &mut key).unwrap();
    key
}

/// Encrypt credential data using age (X25519 + ChaCha20-Poly1305)
fn encrypt_credential(data: &str, key: &[u8; 32]) -> Result<Vec<u8>, SecurityError> {
    let recipient = age::x25519::Identity::from_bytes(key)
        .to_public();
    let encrypted = age::encrypt(&recipient, data.as_bytes())
        .map_err(|e| SecurityError::EncryptionError(e.to_string()))?;
    Ok(encrypted)
}

/// Store encrypted credential to file
fn store_encrypted_file(
    account_id: &str,
    credential_type: &str,
    encrypted_data: &[u8],
) -> Result<(), SecurityError> {
    let config_dir = dirs::config_dir()
        .ok_or(SecurityError::ConfigDirNotFound)?;
    let cred_dir = config_dir.join("alphastack").join("credentials");
    fs::create_dir_all(&cred_dir)?;
    
    let file_path = cred_dir.join(format!("{account_id}.{credential_type}.enc"));
    fs::write(&file_path, encrypted_data)?;
    
    // Set restrictive permissions (owner-only read/write)
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        fs::set_permissions(&file_path, fs::Permissions::from_mode(0o600))?;
    }
    
    Ok(())
}
```

### 3.4 Server-Side Credential Encryption (API Keys, TOTP Secrets)

For credentials that must be stored server-side (API keys for programmatic access, TOTP secrets for 2FA):

```python
# Server-side field-level encryption using Fernet (AES-128-CBC + HMAC)
# Upgraded to AES-256-GCM for production

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os
import base64

class FieldEncryptor:
    """AES-256-GCM field-level encryption with key versioning."""
    
    def __init__(self, kms_client):
        self.kms = kms_client
        self._key_cache = {}  # version -> key
    
    def encrypt(self, plaintext: str, key_version: str = "current") -> str:
        """Encrypt a field value. Returns: base64(version:nonce:ciphertext:tag)"""
        key = self._get_dek(key_version)
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)  # 96-bit nonce for GCM
        
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
        
        # Pack: version (4B) + nonce (12B) + ciphertext + tag (16B)
        packed = key_version.encode() + b":" + nonce + ciphertext
        return base64.b64encode(packed).decode()
    
    def decrypt(self, encrypted: str) -> str:
        """Decrypt a field value."""
        packed = base64.b64decode(encrypted)
        parts = packed.split(b":", 1)
        key_version = parts[0].decode()
        nonce_and_ct = parts[1]
        
        key = self._get_dek(key_version)
        aesgcm = AESGCM(key)
        nonce = nonce_and_ct[:12]
        ciphertext = nonce_and_ct[12:]
        
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode()
    
    def _get_dek(self, version: str) -> bytes:
        """Get Data Encryption Key from KMS (cached)."""
        if version not in self._key_cache:
            self._key_cache[version] = self.kms.generate_data_key(
                KeyId=f"alphastack-dek-{version}",
                KeySpec="AES_256"
            )["Plaintext"]
        return self._key_cache[version]
```

### 3.5 Key Rotation Policy

| Key Type | Rotation Period | Method | Downtime |
|----------|----------------|--------|----------|
| JWT signing key (RSA-4096) | 90 days | Dual-key overlap (30-day grace) | Zero |
| Field encryption DEK | 90 days | Re-encrypt in background | Zero |
| TOTP secrets | Never (unless compromised) | User re-enrollment | User action required |
| Broker credentials | User-initiated | Re-store in keyring | User action required |
| Master key (KMS/HSM) | 1 year | KMS automatic rotation | Zero |
| Refresh token | 7 days | Automatic rotation on use | Zero |

### 3.6 Memory Security

```rust
use zeroize::{Zeroize, ZeroizeOnDrop};

/// Secure credential container that zeros memory on drop
#[derive(ZeroizeOnDrop)]
pub struct BrokerCredentials {
    pub server: String,
    pub login: String,
    pub password: String,
    pub api_key: Option<String>,
    pub api_secret: Option<String>,
}

/// Usage pattern — credentials exist in memory only while needed
pub async fn execute_trade(creds: &BrokerCredentials, order: &Order) -> Result<Fill> {
    // Credentials are in scope only during this function
    // After return, Drop impl zeros all fields
    
    let connector = connect_to_broker(&creds.server, &creds.login, &creds.password).await?;
    let result = connector.place_order(order).await?;
    // connector.disconnect() called, credentials no longer needed
    Ok(result)
}
// creds.password is now zeroed in memory
```

### 3.7 Keyring Platform Details

| Platform | Backend | Protection | Keyring Locked When |
|----------|---------|------------|---------------------|
| Windows | Credential Manager | DPAPI (user-scoped) | User logs out |
| macOS | Keychain Services | User password + ACL | Screen lock / sleep |
| Linux | Secret Service (D-Bus) | Login password | Session ends |
| iOS | Keychain Services | Device passcode + biometric | Device locked |
| Android | Keystore (hardware-backed) | Biometric / PIN | Device locked |
| Docker/Server | HashiCorp Vault / AWS KMS | TLS + token auth | Token expiry |

---

## 4. API Security

### 4.1 Rate Limiting

**Implementation:** Token bucket algorithm via the `governor` crate (Rust) or `slowapi` (Python/FastAPI).

```yaml
rate_limits:
  # Authentication endpoints (strict)
  /api/v1/auth/login:
    rate: 5/15m              # 5 attempts per 15 minutes per IP
    burst: 3                 # Allow burst of 3 rapid attempts
    block_duration: 30m      # Block for 30 minutes after limit exceeded
    
  /api/v1/auth/register:
    rate: 3/1h               # 3 registrations per hour per IP
    
  /api/v1/auth/password-reset:
    rate: 3/1h               # 3 reset requests per hour per email
    
  /api/v1/auth/2fa/verify:
    rate: 5/15m              # 5 TOTP attempts per 15 minutes
    block_duration: 1h       # Lock 2FA for 1 hour after limit (requires backup code)

  # API endpoints (standard)
  /api/v1/*:
    rate: 100/1m             # 100 requests per minute per authenticated user
    burst: 50
    
  # Trading endpoints (moderate)
  /api/v1/orders/*:
    rate: 30/1m              # 30 order operations per minute
    burst: 10
    
  # Data endpoints (generous)
  /api/v1/market-data/*:
    rate: 300/1m             # 300 data requests per minute
    burst: 100

  # WebSocket connections
  /ws/*:
    rate: 10/1m              # 10 new connections per minute per IP
    max_connections: 5        # Max 5 concurrent WS connections per user
```

**Account Lockout Policy:**
- 5 failed login attempts → 15-minute lockout
- 10 failed attempts in 1 hour → 1-hour lockout + email notification
- 20 failed attempts in 24 hours → account locked + manual unlock required
- Lockout counter resets on successful login
- Lockout is per-IP + per-account (both tracked)

### 4.2 CORS (Cross-Origin Resource Sharing)

```yaml
cors_policy:
  allowed_origins:
    - "https://app.alphastack.io"           # Production web app
    - "https://staging.alphastack.io"       # Staging
    - "tauri://localhost"                    # Tauri desktop (local)
    - "https://tauri.localhost"              # Tauri desktop (HTTPS local)
  
  allowed_methods:
    - GET
    - POST
    - PUT
    - DELETE
    - PATCH
    - OPTIONS
  
  allowed_headers:
    - Authorization
    - Content-Type
    - X-Request-ID
    - X-Device-ID
    - X-CSRF-Token
  
  exposed_headers:
    - X-Rate-Limit-Remaining
    - X-Rate-Limit-Reset
    - X-Request-ID
  
  allow_credentials: true
  max_age: 86400            # Cache preflight for 24 hours
  
  # Block all other origins (default deny)
  # No wildcard (*) ever — credentials require explicit origins
```

### 4.3 Content Security Policy (CSP)

```yaml
csp_policy:
  # Strict CSP for web application
  default-src: "'self'"
  script-src: "'self'"                     # No inline scripts, no eval
  style-src: "'self' 'unsafe-inline'"      # Allow inline styles for UI frameworks
  img-src: "'self' data: https:"           # Allow data URIs and HTTPS images
  font-src: "'self'"                       # Self-hosted fonts only
  connect-src: 
    - "'self'"
    - "wss://api.alphastack.io"            # WebSocket for real-time data
    - "https://api.alphastack.io"          # REST API
  frame-src: "'none'"                      # No iframes
  object-src: "'none'"                     # No plugins
  base-uri: "'self'"                       # Prevent base tag injection
  form-action: "'self'"                    # Forms only submit to self
  frame-ancestors: "'none'"                # Prevent clickjacking
  upgrade-insecure-requests: true          # Force HTTPS
  
  # Report violations
  report-uri: "https://api.alphastack.io/csp-report"
  report-to: "csp-endpoint"
```

### 4.4 HTTP Security Headers

```yaml
security_headers:
  Strict-Transport-Security: "max-age=63072000; includeSubDomains; preload"
  X-Content-Type-Options: "nosniff"
  X-Frame-Options: "DENY"
  X-XSS-Protection: "0"                    # Disabled — CSP handles this
  Referrer-Policy: "strict-origin-when-cross-origin"
  Permissions-Policy: "camera=(), microphone=(), geolocation=(), payment=()"
  X-Request-ID: "${uuid}"                  # For request tracing
  Cache-Control: "no-store"                # For authenticated responses
  Pragma: "no-cache"
```

### 4.5 Input Validation & Sanitization

```python
# Pydantic models enforce strict input validation at API boundary

from pydantic import BaseModel, Field, validator
from typing import Optional
import re

class LoginRequest(BaseModel):
    email: str = Field(..., max_length=254)
    password: str = Field(..., min_length=12, max_length=128)
    totp_code: Optional[str] = Field(None, pattern=r'^\d{6}$')
    
    @validator('email')
    def validate_email(cls, v):
        # Strict email validation
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', v):
            raise ValueError('Invalid email format')
        return v.lower().strip()

class OrderRequest(BaseModel):
    symbol: str = Field(..., pattern=r'^[A-Z]{3,6}/[A-Z]{3,6}$')  # EUR/USD format
    side: str = Field(..., pattern=r'^(buy|sell)$')
    order_type: str = Field(..., pattern=r'^(market|limit|stop)$')
    quantity: float = Field(..., gt=0, le=1000000)
    price: Optional[float] = Field(None, gt=0)
    stop_loss: Optional[float] = Field(None, gt=0)
    take_profit: Optional[float] = Field(None, gt=0)
    
    @validator('price')
    def validate_price_for_limit(cls, v, values):
        if values.get('order_type') in ('limit', 'stop') and v is None:
            raise ValueError('Price required for limit/stop orders')
        return v

# SQL Injection prevention: parameterized queries only (SQLAlchemy ORM)
# NoSQL Injection prevention: schema validation on all document inputs
# Command Injection prevention: no shell=True; use subprocess with list args
# Path Traversal prevention: sanitize all file paths, use allowlists
```

### 4.6 CSRF Protection

```python
# Double-submit cookie pattern for web clients

from fastapi import Request, HTTPException
from secrets import compare_digest

CSRF_COOKIE_NAME = "alphastack_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"

async def validate_csrf(request: Request):
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return  # Safe methods don't need CSRF
    
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    header_token = request.headers.get(CSRF_HEADER_NAME)
    
    if not cookie_token or not header_token:
        raise HTTPException(403, "CSRF token missing")
    
    if not compare_digest(cookie_token, header_token):
        raise HTTPException(403, "CSRF token mismatch")
```

### 4.7 Request Signing (API Keys)

For programmatic API access (bots, integrations):

```python
import hmac
import hashlib
import time

def verify_api_request(api_key: str, timestamp: str, signature: str, 
                       method: str, path: str, body: str, api_secret: str) -> bool:
    """
    HMAC-SHA256 request signing.
    
    Signature = HMAC-SHA256(api_secret, 
        f"{timestamp}\n{method}\n{path}\n{sha256(body)}")
    """
    # Reject if timestamp is >5 minutes old (replay protection)
    if abs(time.time() - int(timestamp)) > 300:
        return False
    
    payload = f"{timestamp}\n{method}\n{path}\n{hashlib.sha256(body.encode()).hexdigest()}"
    expected = hmac.new(
        api_secret.encode(), 
        payload.encode(), 
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected)
```

### 4.8 Geo-Blocking

```yaml
geo_blocking:
  # Blocked jurisdictions (regulatory compliance)
  blocked_countries:
    - "US"     # United States — SEC/CFTC restrictions
    - "KP"     # North Korea — sanctions
    - "IR"     # Iran — sanctions
    - "SY"     # Syria — sanctions
    - "CU"     # Cuba — sanctions
  
  # Implementation
  method: "maxmind_geolite2"  # IP geolocation
  action: "block"              # Block registration + API access
  error_message: "Alpha Stack is not available in your jurisdiction."
  
  # VPN detection (basic)
  block_known_vpn_ips: true
  block_tor_exit_nodes: true
  # Note: Determined users can bypass — this is a compliance layer, not security
```

---

## 5. Quantum-Resistant Cryptography

### 5.1 The Quantum Threat to Alpha Stack

**Harvest Now, Decrypt Later (HNDL):**
The most immediate quantum threat. Adversaries can capture encrypted traffic and stored data TODAY and decrypt it when cryptographically relevant quantum computers (CRQCs) arrive. For financial trading data, this means:

- **API traffic captured today** could reveal trading strategies, positions, and P&L in 10-20 years
- **Stored broker credentials** (if encrypted with RSA/ECC) could be decrypted retroactively
- **JWT tokens** captured in transit could be forged once RSA is broken

**Timeline Assessment (based on research):**

| Milestone | Estimated Year | Confidence | Impact on Alpha Stack |
|-----------|---------------|------------|----------------------|
| NIST PQC standards finalized | **2024** (done) | High | Standards available |
| Early PQC deployment (Google, Cloudflare) | **2025-2026** | High | Industry momentum |
| Regulatory mandates for PQC | **2027-2030** | Medium | Compliance deadline |
| CRQC capable of breaking RSA-2048 | **2035-2045** | Low-Medium | Data-at-risk deadline |
| Full PQC migration in financial services | **2030-2035** | Medium | Migration window |

**Priority:** Begin PQC migration NOW for data-at-rest and long-lived secrets. Data-in-transit can follow industry TLS standards.

### 5.2 NIST Post-Quantum Cryptography Standards

Finalized in 2024, these are the algorithms Alpha Stack will adopt:

| Standard | Algorithm | Type | Use Case in Alpha Stack |
|----------|-----------|------|------------------------|
| **FIPS 203 (ML-KEM)** | CRYSTALS-Kyber | Lattice-based KEM | Key exchange for TLS, credential encryption |
| **FIPS 204 (ML-DSA)** | CRYSTALS-Dilithium | Lattice-based signature | JWT signing, document signing, code signing |
| **FIPS 205 (SLH-DSA)** | SPHINCS+ | Hash-based signature | Backup signature scheme (conservative choice) |
| **FN-DSA** | FALCON | Lattice-based signature | Compact signatures for constrained environments |

### 5.3 Hybrid Cryptography Strategy

During the transition period (2026-2035), Alpha Stack uses **hybrid** schemes — classical + post-quantum combined. If either scheme is broken, the other still provides protection.

```
HYBRID KEY EXCHANGE (TLS):
┌─────────────────────────────────────────────────────┐
│  Client Hello                                        │
│  ├── X25519 key share (classical ECDH)              │
│  └── ML-KEM-768 key share (post-quantum KEM)        │
│                                                      │
│  Server Hello                                        │
│  ├── X25519 key share                               │
│  └── ML-KEM-768 key share                           │
│                                                      │
│  Shared Secret = X25519_SS || ML-KEM-768_SS         │
│  (concatenated, then fed into HKDF)                  │
│                                                      │
│  Security: secure if EITHER algorithm is secure      │
└─────────────────────────────────────────────────────┘

HYBRID SIGNATURES (JWT):
┌─────────────────────────────────────────────────────┐
│  JWT Header:                                         │
│  {                                                   │
│    "alg": "Ed25519",           // Classical          │
│    "alg2": "ML-DSA-65",        // Post-quantum       │
│    "kid": "as-hybrid-2026-q3"                        │
│  }                                                   │
│                                                      │
│  JWT Signature:                                      │
│    sig_classical = Ed25519.sign(header.payload)      │
│    sig_pq = ML-DSA-65.sign(header.payload)           │
│    signature = sig_classical || sig_pq               │
│                                                      │
│  Verification:                                       │
│    Valid if BOTH signatures verify                   │
│    (defense-in-depth: both must pass)                │
└─────────────────────────────────────────────────────┘
```

### 5.4 Crypto-Agility Framework

Alpha Stack implements a **crypto-agility** layer — the ability to swap cryptographic algorithms without code rewrites:

```rust
/// Crypto-agility abstraction
pub trait KeyEncapsulation {
    fn generate_keypair() -> (PublicKey, PrivateKey);
    fn encapsulate(pk: &PublicKey) -> (Ciphertext, SharedSecret);
    fn decapsulate(sk: &PrivateKey, ct: &Ciphertext) -> SharedSecret;
}

pub trait SignatureScheme {
    fn generate_keypair() -> (VerifyingKey, SigningKey);
    fn sign(sk: &SigningKey, message: &[u8]) -> Signature;
    fn verify(pk: &VerifyingKey, message: &[u8], sig: &Signature) -> bool;
}

/// Algorithm registry — swap implementations at runtime
pub enum AlgorithmSet {
    Classical,          // X25519 + Ed25519
    PostQuantum,        // ML-KEM-768 + ML-DSA-65
    Hybrid,             // Both combined (default)
}

impl AlgorithmSet {
    pub fn kem(&self) -> Box<dyn KeyEncapsulation> {
        match self {
            Self::Classical => Box::new(X25519),
            Self::PostQuantum => Box::new(MlKem768),
            Self::Hybrid => Box::new(HybridKem::new(X25519, MlKem768)),
        }
    }
    
    pub fn signature(&self) -> Box<dyn SignatureScheme> {
        match self {
            Self::Classical => Box::new(Ed25519),
            Self::PostQuantum => Box::new(MlDsa65),
            Self::Hybrid => Box::new(HybridSignature::new(Ed25519, MlDsa65)),
        }
    }
}
```

### 5.5 PQC Migration Roadmap

```
Phase 1 (Q3 2026): CRYPTOGRAPHIC AUDIT
├── Inventory all RSA/ECC dependencies
├── Identify "harvest now, decrypt later" exposure
├── Classify data by sensitivity and retention period
└── Prioritize: long-lived secrets first

Phase 2 (Q4 2026): HYBRID DEPLOYMENT (Internal)
├── Deploy hybrid TLS for internal service-to-service
├── Test ML-KEM-768 key exchange in staging
├── Benchmark PQC performance impact
└── Update crypto-agility abstraction layer

Phase 3 (Q1 2027): HYBRID DEPLOYMENT (External)
├── Enable hybrid TLS for client-facing APIs
├── Implement hybrid JWT signing (Ed25519 + ML-DSA-65)
├── Re-encrypt stored credentials with PQC-resistant DEKs
└── Update API documentation for PQC-aware clients

Phase 4 (2027-2028): FULL PQC MIGRATION
├── Migrate all TLS to PQC-only (when industry support is ready)
├── Deprecate classical-only algorithms
├── PQC-signed code and binaries
└── PQC for broker connection encryption (where supported)

Phase 5 (2028+): MONITOR & ADAPT
├── Track quantum hardware progress (IBM, Google roadmaps)
├── Adjust key sizes if attacks improve
├── Participate in NIST PQC migration working groups
└── Test quantum random number generation (QRNG) integration
```

### 5.6 Quantum Random Number Generation (QRNG)

For cryptographic nonces, key generation, and Monte Carlo simulations:

```python
# QRNG integration options

# Option 1: Cloud QRNG (free/cheap)
import requests

def get_quantum_random_bytes(n_bytes: int = 32) -> bytes:
    """Fetch true quantum random numbers from ANU QRNG API."""
    response = requests.get(
        f"https://qrng.anu.edu.au/API/jsonI.php?length={n_bytes}&type=uint8",
        timeout=5
    )
    data = response.json()
    return bytes(data["data"])

# Option 2: Hardware QRNG (production)
# ID Quantique Quantis USB device — 4 Mbit/s true random
# Plugged into server, accessed via /dev/quantum-rng

# Option 3: IBM Quantum (free tier)
# Generate random bits using quantum measurement
# ~100 bits/second — too slow for bulk, fine for key generation
```

### 5.7 Blockchain/Wallet Quantum Security

For Alpha Stack's crypto trading component:

| Current Crypto | Quantum Threat | Mitigation |
|---------------|----------------|------------|
| Bitcoin ECDSA (secp256k1) | Broken by Shor's algorithm | Use new addresses (hide pubkey until spend); monitor Bitcoin PQC upgrade proposals |
| Ethereum ECDSA | Same as Bitcoin | EIP-4337 account abstraction enables PQC signatures |
| TLS (ECDHE) | Broken by Shor's | Hybrid TLS (X25519 + ML-KEM) |
| AES-256 | Grover: effective 128-bit security | **Still sufficient** — no action needed |
| SHA-256 | Grover: effective 128-bit security | **Still sufficient** — no action needed |
| Argon2id | Not quantum-vulnerable | **Still sufficient** — memory-hard |

**Key insight:** AES-256 and SHA-256 remain quantum-resistant. The threat is specifically to public-key cryptography (RSA, ECC, ECDSA).

---

## 6. Broker Credential Isolation

### 6.1 Architecture: Credential Vault Isolation

The most critical security boundary in Alpha Stack. Broker credentials are isolated at **five levels**:

```
┌───────────────────────────────────────────────────────────────┐
│                    ISOLATION LEVEL 1: PROCESS                   │
│  Broker credential operations run in a separate process         │
│  from the main application. Memory dumps cannot capture creds.  │
├───────────────────────────────────────────────────────────────┤
│                    ISOLATION LEVEL 2: MEMORY                    │
│  Credentials loaded into memory only during active connection.  │
│  Zeroized immediately after use. No plaintext persistence.      │
├───────────────────────────────────────────────────────────────┤
│                    ISOLATION LEVEL 3: STORAGE                   │
│  OS Keyring (device-local) or HSM (server). Encrypted at rest. │
│  Never stored in application database or config files.          │
├───────────────────────────────────────────────────────────────┤
│                    ISOLATION LEVEL 4: NETWORK                   │
│  Broker credentials NEVER transmitted to Alpha Stack servers.   │
│  Device → Broker (direct). No intermediary.                     │
├───────────────────────────────────────────────────────────────┤
│                    ISOLATION LEVEL 5: ACCESS CONTROL            │
│  Each broker account scoped to its owner. No cross-user access. │
│  RBAC: only the account holder + system processes can access.   │
└───────────────────────────────────────────────────────────────┘
```

### 6.2 Broker Credential Lifecycle

```
┌─────────────┐     ┌──────────────┐     ┌───────────────┐
│  USER        │     │  TAURI IPC   │     │  RUST BACKEND │
│  enters      │────►│  (in-memory  │────►│  validates    │
│  credentials │     │  only)       │     │  format       │
└─────────────┘     └──────────────┘     └───────┬───────┘
                                                  │
                                    ┌─────────────▼──────────────┐
                                    │  STORE IN OS KEYRING       │
                                    │  (DPAPI/Keychain/SecretSvc)│
                                    │  Entry: {account}.{field}  │
                                    └─────────────┬──────────────┘
                                                  │
                              ┌────────────────────┼────────────────────┐
                              │                    │                    │
                    ┌─────────▼─────────┐ ┌────────▼────────┐ ┌────────▼────────┐
                    │  MT5 BRIDGE       │ │  CCXT CONNECTOR │ │  REST API       │
                    │  (Windows VM)     │ │  (Crypto)       │ │  (OANDA, etc.)  │
                    │  creds loaded     │ │  creds loaded   │ │  creds loaded   │
                    │  → used → zeroed  │ │  → used → zeroed│ │  → used → zeroed│
                    └───────────────────┘ └─────────────────┘ └─────────────────┘

NEVER HAPPENS:
  ✗ Credentials sent to Alpha Stack cloud servers
  ✗ Credentials stored in database (PostgreSQL, Redis, etc.)
  ✗ Credentials in log files
  ✗ Credentials in environment variables (runtime)
  ✗ Credentials transmitted over unencrypted channels
```

### 6.3 Multi-Broker Credential Isolation

When a user connects multiple brokers, each credential set is independently encrypted and isolated:

```rust
/// Each broker account has its own encryption context
pub struct BrokerVault {
    accounts: HashMap<String, BrokerAccount>,
}

pub struct BrokerAccount {
    id: String,                    // UUID
    label: String,                 // User-assigned name
    broker_type: BrokerType,       // MT5, CCXT, REST, FIX
    platform: TradingPlatform,     // FXPesa, Binance, OANDA
    credential_ref: CredentialRef, // Keyring entry reference (not the creds themselves)
    status: ConnectionStatus,
    created_at: DateTime<Utc>,
    last_connected: Option<DateTime<Utc>>,
}

/// Credential reference — points to keyring, doesn't contain secrets
pub struct CredentialRef {
    service: String,     // "com.alphastack.broker"
    entry_prefix: String, // "{account_id}"
    fields: Vec<String>,  // ["server", "login", "password", "api_key", "api_secret"]
}

/// Load credentials only when needed, zero after use
impl BrokerVault {
    pub async fn connect(&self, account_id: &str) -> Result<BrokerConnection> {
        let account = self.accounts.get(account_id)
            .ok_or(SecurityError::AccountNotFound)?;
        
        // Load credentials from keyring
        let creds = self.load_and_decrypt(account)?;
        
        // Establish connection
        let conn = match account.broker_type {
            BrokerType::MT5 => Mt5Connector::connect(&creds).await?,
            BrokerType::CCXT => CcxtConnector::connect(&creds).await?,
            BrokerType::REST => RestConnector::connect(&creds).await?,
        };
        
        // Credentials are zeroed when creds goes out of scope
        // (ZeroizeOnDrop implementation)
        
        Ok(conn)
    }
}
```

### 6.4 Credential Access Audit

Every credential access event is logged (without the credential value):

```json
{
  "event": "credential_access",
  "timestamp": "2026-07-11T14:30:00Z",
  "user_id": "usr_a1b2c3d4",
  "account_id": "brk_x7y8z9",
  "broker": "FXPesa",
  "action": "load_for_connection",
  "source_ip": "192.168.1.100",
  "device_id": "dev_abc123",
  "result": "success",
  "duration_ms": 45
}
```

### 6.5 MT5 Bridge Security

The MT5 bridge service (Windows VM) is the most sensitive component:

```
┌─────────────────────────────────────────────────────────┐
│                    MT5 BRIDGE SECURITY                    │
│                                                           │
│  Network:                                                │
│  ├── TLS 1.3 mutual authentication (mTLS)               │
│  ├── Certificate pinning (desktop ↔ bridge)              │
│  ├── No public internet exposure (VPN/tunnel only)       │
│  └── Firewall: allow only desktop app IP                 │
│                                                           │
│  Process:                                                │
│  ├── Runs as dedicated Windows service (limited user)    │
│  ├── No admin privileges                                 │
│  ├── Credential memory: encrypted with DPAPI             │
│  ├── Credentials loaded per-session, zeroed on disconnect│
│  └── Crash dump collection disabled (prevents memory leak)│
│                                                           │
│  Monitoring:                                             │
│  ├── Health check endpoint (no credentials exposed)      │
│  ├── Connection status reporting                         │
│  ├── Anomaly detection (unusual trade patterns)          │
│  └── Auto-disconnect on suspicious activity              │
└─────────────────────────────────────────────────────────┘
```

### 6.6 Secretless Broker Connection (OAuth2 Brokers)

For brokers that support OAuth2 (OANDA, Interactive Brokers):

```
User clicks "Connect Broker" →
  Alpha Stack opens broker's OAuth2 authorization URL
  User authenticates directly on broker's website
  Broker redirects with authorization code
  Alpha Stack exchanges code for access_token + refresh_token
  Tokens stored in OS Keyring (encrypted)
  Token used for API calls — user's password NEVER touches Alpha Stack

Token Refresh:
  access_token expires (1 hour typical)
  Silent refresh via refresh_token
  If refresh fails → user re-authorizes (broker login page)
```

**Advantage:** Alpha Stack never sees the user's broker password. The OAuth2 flow is broker-mediated.

---

## 7. Audit Logging

### 7.1 Audit Log Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    AUDIT LOGGING SYSTEM                        │
│                                                                │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    │
│  │ Application  │───►│ Log Pipeline │───►│  Storage     │    │
│  │ Events       │    │ (Structured) │    │  (Append-    │    │
│  │              │    │              │    │   Only)      │    │
│  └──────────────┘    └──────────────┘    └──────────────┘    │
│         │                                      │              │
│         │              ┌──────────────┐        │              │
│         └─────────────►│  Alerting    │◄───────┘              │
│                        │  (Real-time) │                        │
│                        └──────────────┘                        │
└──────────────────────────────────────────────────────────────┘
```

### 7.2 Event Categories & Retention

| Category | Events | Retention | Storage |
|----------|--------|-----------|---------|
| **Authentication** | Login, logout, failed attempts, 2FA, password changes | 2 years | ClickHouse (hot) + S3 (cold) |
| **Authorization** | Permission denied, role changes, API key creation | 2 years | ClickHouse + S3 |
| **Trading** | Orders placed/filled/cancelled, position changes | 7 years (regulatory) | ClickHouse + S3 |
| **Credential** | Credential stored/loaded/deleted (never values) | 2 years | ClickHouse + S3 |
| **System** | Config changes, deployments, key rotations | 3 years | Loki + S3 |
| **Security** | Rate limit hits, blocked IPs, CSP violations, anomalies | 5 years | ClickHouse + S3 |
| **Data Access** | API data queries, export/download requests | 1 year | ClickHouse |

### 7.3 Audit Log Schema

```json
{
  "version": "1.0",
  "id": "evt_1234567890abcdef",
  "timestamp": "2026-07-11T14:30:00.123Z",
  "category": "trading",
  "action": "order_placed",
  "actor": {
    "type": "user",
    "id": "usr_a1b2c3d4",
    "email_hash": "sha256:ab3f...",      // Hashed for privacy
    "ip_hash": "sha256:cd4e...",
    "device_id": "dev_x7y8z9",
    "user_agent": "AlphaStack/1.0 Desktop"
  },
  "resource": {
    "type": "order",
    "id": "ord_f1e2d3c4",
    "broker_account": "brk_x7y8z9",
    "symbol": "EUR/USD"
  },
  "details": {
    "side": "buy",
    "order_type": "market",
    "quantity": 0.01,
    "price": 1.08542,
    "stop_loss": 1.08200,
    "take_profit": 1.09000,
    "strategy_step": 12,
    "confidence_score": 0.85
  },
  "outcome": {
    "status": "success",
    "broker_order_id": "12345678",
    "fill_price": 1.08543,
    "fill_time_ms": 245,
    "slippage_pips": 0.1
  },
  "integrity": {
    "hash": "sha256:...",
    "previous_hash": "sha256:...",    // Chain for tamper detection
    "signed_by": "alphastack-audit"
  }
}
```

### 7.4 Tamper-Proof Audit Trail

Audit logs use a **hash chain** for tamper detection:

```python
import hashlib
import json

class AuditLogger:
    def __init__(self):
        self.previous_hash = "GENESIS"
    
    def log(self, event: dict) -> str:
        """Append event to audit log with hash chain."""
        event["integrity"] = {
            "previous_hash": self.previous_hash,
            "timestamp": self._now_iso(),
        }
        
        # Compute hash of this event
        event_bytes = json.dumps(event, sort_keys=True).encode()
        event_hash = hashlib.sha256(event_bytes).hexdigest()
        event["integrity"]["hash"] = event_hash
        
        # Store (append-only)
        self._store(event)
        
        # Update chain
        self.previous_hash = event_hash
        
        return event_hash
    
    def verify_chain(self, events: list[dict]) -> bool:
        """Verify the integrity of the audit log chain."""
        prev_hash = "GENESIS"
        for event in events:
            stored_hash = event["integrity"]["hash"]
            stored_prev = event["integrity"]["previous_hash"]
            
            if stored_prev != prev_hash:
                return False  # Chain broken
            
            # Recompute hash
            event_copy = {k: v for k, v in event.items() if k != "integrity"}
            event_copy["integrity"] = {
                "previous_hash": stored_prev,
                "timestamp": event["integrity"]["timestamp"],
            }
            computed = hashlib.sha256(
                json.dumps(event_copy, sort_keys=True).encode()
            ).hexdigest()
            
            if computed != stored_hash:
                return False  # Event tampered
            
            prev_hash = stored_hash
        
        return True
```

### 7.5 Anomaly Detection Alerts

```yaml
audit_alerts:
  # Authentication anomalies
  - name: "brute_force_detection"
    condition: "failed_logins > 10 in 5m from same IP"
    severity: "critical"
    action: "block_ip + notify_user + notify_admin"
    
  - name: "impossible_travel"
    condition: "login from country A then country B within 1 hour"
    severity: "high"
    action: "require_2fa + notify_user"
    
  - name: "new_device_login"
    condition: "login from unrecognized device"
    severity: "medium"
    action: "notify_user_email"

  # Trading anomalies
  - name: "unusual_volume"
    condition: "order_volume > 10x average for user"
    severity: "high"
    action: "hold_order + require_approval"
    
  - name: "rapid_fire_orders"
    condition: "orders > 50 in 1 minute"
    severity: "high"
    action: "pause_trading + notify_user"
    
  - name: "off_hours_trading"
    condition: "trading outside user's normal hours"
    severity: "low"
    action: "log_only"

  # Credential anomalies
  - name: "credential_access_spike"
    condition: "credential_loads > 20 in 1 hour"
    severity: "critical"
    action: "lock_broker_accounts + notify_user"
    
  - name: "multi_broker_simultaneous"
    condition: "connect to > 3 brokers simultaneously"
    severity: "medium"
    action: "log + notify_user"
```

---

## 8. Penetration Testing Strategy

### 8.1 Testing Phases

```
┌─────────────────────────────────────────────────────────────────┐
│                 PENETRATION TESTING LIFECYCLE                     │
│                                                                   │
│  Phase 1: AUTOMATED (Continuous)                                 │
│  ├── SAST: Static Application Security Testing (every commit)    │
│  ├── DAST: Dynamic Application Security Testing (weekly)         │
│  ├── Dependency scanning: CVE checks (daily)                     │
│  └── Container image scanning (every build)                      │
│                                                                   │
│  Phase 2: INTERNAL (Quarterly)                                   │
│  ├── Red team exercises by security team                         │
│  ├── API fuzzing (protocol-level testing)                        │
│  ├── Credential isolation verification                           │
│  └── Social engineering simulations                              │
│                                                                   │
│  Phase 3: EXTERNAL (Annually + Pre-Launch)                       │
│  ├── Third-party penetration test (certified firm)               │
│  ├── Bug bounty program (after launch)                           │
│  └── Compliance audit (PCI DSS, SOC 2 if applicable)            │
└─────────────────────────────────────────────────────────────────┘
```

### 8.2 Automated Security Testing (CI/CD Integration)

```yaml
# .github/workflows/security.yml

name: Security Pipeline
on: [push, pull_request]

jobs:
  sast:
    name: Static Analysis
    runs-on: ubuntu-latest
    steps:
      # Rust code analysis
      - name: Cargo Audit
        run: cargo audit                    # CVE check for Rust dependencies
      
      - name: Clippy Security Lints
        run: cargo clippy -- -W clippy::all  # Security-related warnings
      
      # Python code analysis
      - name: Bandit
        run: bandit -r src/ -f json         # Python security linter
      
      - name: Safety
        run: safety check                    # Python dependency CVE check
      
      # Secrets detection
      - name: TruffleHog
        uses: trufflesecurity/trufflehog@main
        with:
          path: ./
          extra_args: --only-verified

  dast:
    name: Dynamic Analysis
    runs-on: ubuntu-latest
    needs: build
    steps:
      - name: OWASP ZAP
        uses: zaproxy/action-full-scan@v0.4.0
        with:
          target: 'http://localhost:8000'
          
      - name: Nuclei
        run: nuclei -u http://localhost:8000 -t cves/

  container-scan:
    name: Container Security
    runs-on: ubuntu-latest
    steps:
      - name: Trivy
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: 'alphastack:latest'
          format: 'sarif'
          severity: 'CRITICAL,HIGH'
```

### 8.3 Attack Surface Map

```
┌─────────────────────────────────────────────────────────────────┐
│                    ATTACK SURFACE MAP                             │
│                                                                   │
│  EXTERNAL (Internet-facing)                                       │
│  ├── Web Application (React SPA)                                 │
│  │   ├── XSS (stored, reflected, DOM-based)                      │
│  │   ├── CSRF                                                     │
│  │   ├── Clickjacking                                            │
│  │   └── Client-side logic bypass                                │
│  ├── REST API (FastAPI)                                          │
│  │   ├── Authentication bypass                                   │
│  │   ├── Authorization escalation                                │
│  │   ├── Injection (SQL, NoSQL, command)                         │
│  │   ├── Rate limit bypass                                       │
│  │   └── Business logic flaws                                    │
│  ├── WebSocket Server                                            │
│  │   ├── Message injection                                       │
│  │   ├── Connection hijacking                                    │
│  │   └── Denial of service (connection exhaustion)               │
│  └── OAuth2 Callbacks                                            │
│      ├── Redirect URI manipulation                               │
│      └── Authorization code interception                         │
│                                                                   │
│  INTERNAL (Network-isolated)                                      │
│  ├── MT5 Bridge Service                                          │
│  │   ├── Credential extraction from memory                       │
│  │   ├── mTLS bypass                                             │
│  │   └── Message tampering (desktop ↔ bridge)                    │
│  ├── Event Bus (Redis Streams)                                   │
│  │   ├── Unauthorized stream access                              │
│  │   └── Message injection/spoofing                              │
│  └── Database (TimescaleDB / ClickHouse)                         │
│      ├── SQL injection                                           │
│      ├── Privilege escalation                                    │
│      └── Data exfiltration                                       │
│                                                                   │
│  CLIENT-SIDE                                                     │
│  ├── Tauri Desktop App                                           │
│  │   ├── Keyring access (OS-level exploit required)              │
│  │   ├── IPC message tampering                                   │
│  │   └── Binary patching                                         │
│  └── Mobile App (Future)                                         │
│      ├── Reverse engineering                                     │
│      ├── Rooted/jailbroken device bypass                         │
│      └── Local storage extraction                                │
└─────────────────────────────────────────────────────────────────┘
```

### 8.4 Penetration Test Scenarios

#### Scenario 1: Broker Credential Extraction

```
Objective: Attempt to extract broker credentials from the system
Steps:
  1. Attempt to read OS Keyring entries (expect: denied without user auth)
  2. Memory dump of running application (expect: credentials zeroed)
  3. Intercept IPC messages (expect: TLS-encrypted, no plaintext creds)
  4. Access encrypted file fallback (expect: AES-256-GCM, key not extractable)
  5. Server-side credential access (expect: credentials never on server)
Pass Criteria: Zero broker credentials extracted in plaintext
```

#### Scenario 2: Account Takeover

```
Objective: Gain unauthorized access to a user's account
Steps:
  1. Credential stuffing with known breach databases
  2. Brute force login (expect: rate limiting + lockout)
  3. Session token theft (expect: httpOnly, Secure, SameSite=Strict)
  4. JWT forgery (expect: RS256, private key not accessible)
  5. 2FA bypass (expect: TOTP required, backup codes single-use)
  6. Password reset abuse (expect: token expiry, single-use)
Pass Criteria: Account takeover not achieved within 40-hour engagement
```

#### Scenario 3: Trading Manipulation

```
Objective: Execute unauthorized or manipulated trades
Steps:
  1. Order parameter injection (expect: Pydantic validation rejects)
  2. Replay attack on order submission (expect: nonce + timestamp)
  3. WebSocket message injection (expect: authentication on connect)
  4. Broker connector exploitation (expect: sandboxed, validated)
  5. Risk engine bypass (expect: gateway-level enforcement, not prompt-level)
Pass Criteria: No unauthorized trades executed; no risk limits bypassed
```

#### Scenario 4: Data Exfiltration

```
Objective: Extract sensitive trading data or user information
Steps:
  1. SQL injection on API endpoints (expect: parameterized queries)
  2. GraphQL introspection (if applicable) (expect: disabled in production)
  3. IDOR (Insecure Direct Object Reference) on user data
  4. Export endpoint abuse (expect: rate limiting + authorization)
  5. Log file access (expect: no credentials in logs, log access restricted)
Pass Criteria: No sensitive data extracted beyond authorized scope
```

### 8.5 Bug Bounty Program (Post-Launch)

```yaml
bug_bounty:
  platform: "HackerOne"  # or "Bugcrowd"
  
  scope:
    in_scope:
      - "app.alphastack.io"
      - "api.alphastack.io"
      - "Tauri desktop application"
      - "Mobile applications (when launched)"
    
    out_of_scope:
      - "Third-party broker platforms"
      - "Social engineering of employees"
      - "Physical attacks"
      - "Denial of service"
  
  rewards:
    critical: "$5,000 - $15,000"    # Credential theft, account takeover, fund access
    high: "$1,000 - $5,000"         # Authentication bypass, data exfiltration
    medium: "$250 - $1,000"         # XSS, CSRF, rate limit bypass
    low: "$50 - $250"               # Information disclosure, minor issues
  
  response_sla:
    acknowledge: "24 hours"
    triage: "72 hours"
    remediate_critical: "7 days"
    remediate_high: "30 days"
    remediate_medium: "90 days"
```

### 8.6 Security Tools Stack

| Tool | Purpose | Frequency |
|------|---------|-----------|
| **cargo-audit** | Rust dependency CVE scanning | Every commit |
| **bandit** | Python security linting | Every commit |
| **TruffleHog** | Secrets detection in code | Every commit |
| **OWASP ZAP** | Dynamic API testing | Weekly |
| **Nuclei** | Known vulnerability scanning | Weekly |
| **Trivy** | Container image scanning | Every build |
| **Burp Suite** | Manual penetration testing | Quarterly |
| **ffuf** | API endpoint fuzzing | Quarterly |
| **sqlmap** | SQL injection testing | Quarterly |
| **nmap** | Network service discovery | Monthly |
| **Wireshark** | Traffic analysis (MT5 bridge) | As needed |

---

## 9. Incident Response Plan

### 9.1 Severity Levels

| Level | Definition | Example | Response Time |
|-------|-----------|---------|---------------|
| **SEV-1 (Critical)** | Active fund loss or credential compromise | Broker credentials stolen, unauthorized trades | 15 minutes |
| **SEV-2 (High)** | Account takeover or data breach | Mass account compromise, API key leak | 1 hour |
| **SEV-3 (Medium)** | Security vulnerability exploited | XSS payload executed, rate limit bypass | 4 hours |
| **SEV-4 (Low)** | Potential vulnerability discovered | Dependency CVE, misconfiguration | 24 hours |

### 9.2 Incident Response Playbook

```
DETECTION (0-15 min):
├── Automated alert triggered (anomaly detection, WAF, log analysis)
├── On-call engineer acknowledges
├── Initial assessment: scope, severity, active threat?
└── Escalate if SEV-1 or SEV-2

CONTAINMENT (15-60 min):
├── SEV-1: Immediately revoke all sessions + API keys for affected users
├── SEV-1: Lock broker credential access (disable keyring reads)
├── SEV-1: Block attacking IPs at WAF/firewall
├── SEV-2: Force password reset for affected users
├── SEV-2: Rotate API keys
└── Preserve evidence (logs, memory dumps, network captures)

ERADICATION (1-24 hours):
├── Patch vulnerability
├── Remove attacker access
├── Rotate all potentially compromised keys/secrets
├── Re-encrypt affected data with new keys
└── Deploy fix to production

RECOVERY (24-72 hours):
├── Restore from clean backups if needed
├── Gradually re-enable services
├── Monitor for re-compromise
└── Verify all security controls operational

POST-INCIDENT (1-2 weeks):
├── Root cause analysis (blameless post-mortem)
├── Update incident response playbook
├── Implement additional controls to prevent recurrence
├── Notify affected users (GDPR: 72 hours if personal data)
└── File regulatory reports if required
```

### 9.3 Emergency Credential Revocation

```python
# Emergency: revoke all broker credentials for a user
async def emergency_revoke_all_credentials(user_id: str, reason: str):
    """Nuclear option: invalidate all broker access for a user."""
    
    # 1. Revoke all sessions
    await db.sessions.revoke_all(user_id, reason=f"emergency: {reason}")
    
    # 2. Invalidate all refresh tokens
    await db.refresh_tokens.revoke_all(user_id)
    
    # 3. Disable broker connections (keyring entries left intact but unusable)
    await db.broker_accounts.disable_all(user_id)
    
    # 4. Notify user via all channels
    await notify_user(user_id, 
        subject="URGENT: All broker connections suspended",
        body=f"Reason: {reason}. Please re-authenticate and re-verify 2FA."
    )
    
    # 5. Log emergency action
    await audit_log.log({
        "category": "security",
        "action": "emergency_credential_revocation",
        "user_id": user_id,
        "reason": reason,
        "operator": "system"  # or admin user ID
    })
```

---

## 10. Compliance Mapping

### 10.1 Security Controls to Regulations

| Security Control | GDPR | Kenya DPA | MiCA | PCI DSS | ISO 27001 |
|-----------------|------|-----------|------|---------|-----------|
| Encryption at rest (AES-256-GCM) | Art. 32 | §41 | Art. 67 | Req. 3.4 | A.10.1 |
| Encryption in transit (TLS 1.3) | Art. 32 | §41 | Art. 67 | Req. 4.1 | A.13.1 |
| Access control (RBAC) | Art. 25 | §41 | Art. 68 | Req. 7.1 | A.9.1 |
| Audit logging | Art. 30 | §41 | Art. 68 | Req. 10.1 | A.12.4 |
| Breach notification (72h) | Art. 33 | §43 | Art. 107 | Req. 12.10 | A.16.1 |
| Data minimization | Art. 5(1)(c) | §26 | — | Req. 3.1 | A.8.2 |
| MFA | Art. 32 | §41 | Art. 67 | Req. 8.3 | A.9.4 |
| Penetration testing | Art. 32 | §41 | — | Req. 11.3 | A.12.6 |
| Key management | Art. 32 | §41 | — | Req. 3.5 | A.10.1 |
| Incident response | Art. 33-34 | §43 | Art. 107 | Req. 12.10 | A.16.1 |

### 10.2 Data Classification

| Class | Description | Encryption | Access | Retention |
|-------|-------------|------------|--------|-----------|
| **SECRET** | Broker passwords, API secrets, TOTP secrets | AES-256-GCM (field-level) | Keyring only | Until user deletes |
| **CONFIDENTIAL** | User PII, email, trading history | AES-256-GCM (at rest) | Authenticated user | Account lifetime + 7 years |
| **INTERNAL** | Strategy parameters, ML model configs | TLS (in transit) | Authenticated user | 3 years |
| **PUBLIC** | Market data, public API docs | None required | Anyone | Indefinite |

---

## 11. Implementation Roadmap

### Phase 1: Security Foundation (Weeks 1-4)

- [ ] Implement Argon2id password hashing
- [ ] JWT with RS256 signing + JWKS endpoint
- [ ] OS Keyring integration (Rust `keyring` crate)
- [ ] Encrypted file fallback with `age`
- [ ] TLS 1.3 for all connections
- [ ] CORS + CSP headers
- [ ] Rate limiting on auth endpoints
- [ ] Input validation (Pydantic models)
- [ ] Basic audit logging (auth events)

### Phase 2: Credential Isolation (Weeks 4-8)

- [ ] Broker credential vault (keyring-based)
- [ ] Memory zeroization (`zeroize` crate)
- [ ] MT5 bridge mTLS
- [ ] Credential access audit logging
- [ ] Encrypted field storage (server-side)
- [ ] KMS integration for DEK management
- [ ] Session management + device binding

### Phase 3: Advanced Auth (Weeks 8-12)

- [ ] TOTP 2FA implementation
- [ ] WebAuthn/FIDO2 support
- [ ] Biometric auth (desktop)
- [ ] Backup code system
- [ ] Account lockout policies
- [ ] Impossible travel detection
- [ ] OAuth2 for REST API brokers

### Phase 4: Quantum Readiness (Weeks 12-16)

- [ ] Cryptographic dependency audit
- [ ] Crypto-agility abstraction layer
- [ ] Hybrid TLS testing (X25519 + ML-KEM-768)
- [ ] Hybrid JWT signing (Ed25519 + ML-DSA-65)
- [ ] QRNG integration for key generation
- [ ] PQC performance benchmarking

### Phase 5: Security Hardening (Weeks 16-20)

- [ ] Full audit logging system (hash chain)
- [ ] Anomaly detection + alerting
- [ ] CSP violation reporting
- [ ] WAF deployment
- [ ] DDoS protection
- [ ] Container image scanning (CI/CD)
- [ ] SAST/DAST integration

### Phase 6: External Validation (Weeks 20-24)

- [ ] Third-party penetration test
- [ ] Bug bounty program launch
- [ ] SOC 2 Type I preparation
- [ ] ISO 27001 gap analysis
- [ ] Incident response playbook testing (tabletop exercise)
- [ ] Compliance mapping documentation

---

## Appendix A: Cryptographic Primitives Reference

| Primitive | Algorithm | Key Size | Use Case | Quantum Safe? |
|-----------|-----------|----------|----------|---------------|
| Symmetric Encryption | AES-256-GCM | 256-bit | Data at rest, field encryption | ✅ Yes (128-bit effective) |
| Key Exchange | X25519 | 256-bit | TLS key exchange | ❌ No (use ML-KEM) |
| Key Exchange (PQC) | ML-KEM-768 | 768-bit | Hybrid TLS key exchange | ✅ Yes |
| Digital Signature | Ed25519 | 256-bit | JWT signing, code signing | ❌ No (use ML-DSA) |
| Digital Signature (PQC) | ML-DSA-65 | ~1952-byte sig | Hybrid JWT signing | ✅ Yes |
| Hash | SHA-256 | 256-bit | Integrity, passwords (via Argon2) | ✅ Yes (128-bit effective) |
| Hash | SHA-3-256 | 256-bit | Alternative hash | ✅ Yes |
| Password Hash | Argon2id | Configurable | Password storage | ✅ Yes |
| KDF | HKDF-SHA-256 | Configurable | Key derivation | ✅ Yes |
| MAC | HMAC-SHA-256 | 256-bit | API request signing | ✅ Yes |
| CSPRNG | OS-provided | N/A | Nonces, key generation | ✅ Yes |
| QRNG | Quantum measurement | N/A | True randomness | ✅ Yes |

## Appendix B: Security Dependencies (Rust)

```toml
[dependencies]
# Cryptography
ring = "0.17"                    # AES-GCM, HKDF, ECDSA
age = "0.11"                     # File encryption (X25519 + ChaCha20-Poly1305)
argon2 = "0.5"                   # Password hashing
zeroize = "1"                    # Secure memory zeroing
jsonwebtoken = "9"               # JWT encode/decode
p256 = "0.13"                    # NIST P-256 (for compatibility)

# Keyring
keyring = "3"                    # OS keyring access

# TLS
rustls = "0.23"                  # Pure Rust TLS implementation
tokio-rustls = "0.26"            # Async TLS for tokio

# Rate Limiting
governor = "0.8"                 # Token bucket rate limiter

# Security Headers
tower-http = "0.5"               # HTTP middleware (CORS, headers)

[dev-dependencies]
# Security Testing
cargo-audit = "0.20"             # Dependency vulnerability scanning
```

## Appendix C: Security Dependencies (Python)

```toml
[project]
dependencies = [
    "cryptography>=43.0",        # Fernet, AES-GCM, X25519
    "argon2-cffi>=23.1",         # Password hashing (Python bindings)
    "pyotp>=2.9",                # TOTP generation/validation
    "python-jose[cryptography]>=3.3",  # JWT (backup)
    "slowapi>=0.1.9",            # Rate limiting for FastAPI
    "pydantic>=2.5",             # Input validation
]
```

---

*This document should be reviewed quarterly and updated as threats evolve, quantum hardware progresses, and regulatory requirements change.*
