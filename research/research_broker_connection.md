# Broker Connection & Authentication Research
## For Alpha Stack Platform Design

*Date: 2026-07-11*

---

## Table of Contents

1. [How MT5 Desktop Works](#1-how-mt5-desktop-works)
2. [How MT5 Mobile Works](#2-how-mt5-mobile-works)
3. [MT5 Python Library Connection](#3-mt5-python-library-connection)
4. [Authentication Architecture for Alpha Stack](#4-authentication-architecture-for-alpha-stack)
5. [Multi-Platform Auth Flow](#5-multi-platform-auth-flow)
6. [Security Requirements](#6-security-requirements)
7. [Alpha Stack Recommended Architecture](#7-alpha-stack-recommended-architecture)
8. [Implementation Roadmap](#8-implementation-roadmap)

---

## 1. How MT5 Desktop Works

### 1.1 Initial Setup Flow

1. **Download & Install**: User downloads MT5 terminal from MetaQuotes website or broker-branded version
2. **First Launch**: MT5 opens with a connection dialog or auto-detects broker
3. **Account Creation**:
   - User can open a **demo account** directly from MT5 (File → Open an Account)
   - For **live accounts**, user registers on broker's website first, receives login credentials
   - Some brokers offer in-platform registration via embedded web forms
4. **Connection Configuration**:
   - **Server**: Broker provides a server address (e.g., `BrokerName-Live` or `BrokerName-Demo`)
   - **Login**: Numeric account number (e.g., `12345678`)
   - **Password**: Trader password (for trading operations)
   - **Investor Password**: Read-only access (optional, for monitoring)

### 1.2 Credential Storage (Desktop)

- **Location**: `%APPDATA%\MetaQuotes\Terminal\<instance_id>\`
- **Config file**: `config.ini` stores server names and last-used login
- **Passwords**: MT5 does **NOT** store passwords in plaintext in config files
  - Passwords are stored encrypted using a machine-specific key
  - Stored in the terminal's internal encrypted database
  - The `origin-srv` and `origin-login` entries reference last connection
- **Keychain Integration**: MT5 on macOS uses Keychain for credential storage
- **Windows**: Uses DPAPI (Data Protection API) for encryption at rest

### 1.3 Multi-Broker Support

- **Multiple accounts**: Users can save multiple broker connections
- **Account Navigator**: Left panel shows all configured accounts
- **Quick Switch**: Right-click account → Login, or double-click to switch
- **Each account stores**: server address, login, investor password
- **Trader passwords**: Must be re-entered on switch (not stored per-account for security)
- **Server list**: MT5 downloads available servers from MetaQuotes datacenter

### 1.4 Connection Protocol

- **Protocol**: Proprietary TCP-based protocol (not standard HTTP/REST)
- **Port**: Default port varies by broker (typically 443 or custom)
- **Encryption**: TLS/SSL encrypted connection
- **Authentication**: Login + password sent during connection handshake
- **Keep-alive**: Built-in heartbeat mechanism
- **Reconnection**: Auto-reconnect with exponential backoff on connection loss

### 1.5 Demo vs Live

- **Demo accounts**: Created directly in MT5, virtual money, same features
- **Live accounts**: Require broker KYC verification, real money
- **Same interface**: Identical trading experience, just different server endpoints
- **Account type indicator**: Shown in status bar and account navigator

---

## 2. How MT5 Mobile Works

### 2.1 Setup Flow (iOS/Android)

1. **Download** from App Store / Google Play
2. **First Launch**: Shows server browser or demo account creation
3. **Broker Selection**: Search for broker by name, or enter server manually
4. **Login**: Enter credentials (login ID + password)
5. **Save Credentials**: Option to save password for biometric login

### 2.2 Mobile-Specific Features

- **Biometric Login**: Face ID / Touch ID (iOS) or fingerprint (Android)
  - Credentials stored in iOS Keychain / Android Keystore
  - Biometric gate before decrypting stored password
- **Push Notifications**: Trade alerts, margin calls, price alerts
- **Chart Trading**: Tap-and-hold for quick trade execution
- **Multi-account**: Same account navigator as desktop

### 2.3 Mobile Credential Storage

- **iOS**: Keychain Services with `kSecAttrAccessibleWhenUnlockedThisDeviceOnly`
- **Android**: Android Keystore (hardware-backed when available)
- **Encryption**: AES-256-GCM with keys derived from device-specific material
- **No cloud sync**: Credentials do NOT sync via iCloud/Google backup (by design)
- **Session persistence**: Login session persists until explicit logout or password change

### 2.4 Desktop ↔ Mobile Sync

- **No direct sync**: MT5 does NOT sync accounts between desktop and mobile
- **Same credentials**: User manually enters same broker credentials on each device
- **Broker-side state**: Open positions, orders, history are synced via broker server
- **Settings**: Chart layouts, indicators are device-local (not synced)

---

## 3. MT5 Python Library Connection

### 3.1 MetaTrader5 Python Package

The official `MetaTrader5` package (by MetaQuotes) provides Python API access.

**Critical constraint**: **Windows-only** — the package is a compiled `.pyd` (DLL) that interfaces directly with the MT5 terminal. It does NOT work natively on Linux/macOS.

**Package Details**:
- Latest version: `5.0.5735` (April 2026)
- License: MIT
- Platform: `win_amd64` only
- Python: 3.6 — 3.14

### 3.2 Connection Parameters

```python
import MetaTrader5 as mt5

# Initialize connection to MT5 terminal
mt5.initialize(
    path=r"C:\Program Files\MetaTrader 5\terminal64.exe",  # Path to MT5 terminal
    login=12345678,           # Account login (numeric)
    password="your_password", # Trader password
    server="BrokerName-Live", # Broker server name
    timeout=10000,            # Connection timeout (ms)
    portable=False,           # Portable mode flag
)

# Or connect to already-running terminal
mt5.initialize()

# Then login to specific account
mt5.login(
    login=12345678,
    password="your_password",
    server="BrokerName-Live",
    timeout=10000,
)
```

### 3.3 Connection Flow Internals

1. `mt5.initialize()` — Launches or connects to MT5 terminal process
2. Terminal establishes TCP connection to broker server
3. `mt5.login()` — Authenticates with broker using provided credentials
4. Data synchronization begins (positions, orders, history)
5. API calls are now available (orders, ticks, bars, account info)

### 3.4 Error Handling

```python
# Check initialization
if not mt5.initialize():
    print(f"initialize() failed, error code = {mt5.last_error()}")
    # Returns tuple: (error_code, error_description)
    # Common errors:
    # (-1, 'IPC initialization failed') — terminal not found
    # (-2, 'IPC timeout') — terminal not responding
    # (10013, 'Invalid account') — wrong login
    # (10014, 'Invalid password') — wrong password
    # (10015, 'Authorization failed') — server rejected
    # (10016, 'Invalid server') — server not found

# After login, check account
account_info = mt5.account_info()
if account_info is None:
    print(f"account_info() failed, error code = {mt5.last_error()}")
else:
    print(f"Balance: {account_info.balance}")
    print(f"Server: {account_info.server}")
    print(f"Trade mode: {account_info.trade_mode}")  # 0=demo, 1=live
```

### 3.5 Running MT5 on Linux (for Alpha Stack Backend)

Since the Python package is Windows-only, Linux deployment requires one of:

#### Option A: Wine/Bottles
```bash
# Install Wine
sudo apt install wine64

# Install MT5 terminal under Wine
wine mt5setup.exe

# Run Python with Wine's Python or use the package in a Windows Python venv
# Complex setup, fragile, not recommended for production
```

#### Option B: Cloud MT5 (Recommended)
- Run MT5 on a Windows VPS (AWS EC2 Windows, Azure Windows VM)
- Use MetaTrader5 Python package on that Windows machine
- Expose a REST/WebSocket API from Python to Alpha Stack backend
- Alpha Stack connects to this intermediate service

#### Option C: MT5 Web API
- Some brokers offer REST APIs independent of MT5
- cTrader, OANDA, Interactive Brokers have native REST APIs
- MT5 itself has a Web API but it's broker-dependent

### 3.6 Keeping Connection Alive

```python
import MetaTrader5 as mt5
import time
import threading

class MT5Connection:
    def __init__(self, login, password, server):
        self.login = login
        self.password = password
        self.server = server
        self._connected = False
        self._heartbeat_thread = None

    def connect(self):
        if not mt5.initialize():
            raise ConnectionError(f"MT5 init failed: {mt5.last_error()}")

        authorized = mt5.login(self.login, self.password, self.server)
        if not authorized:
            raise AuthError(f"Login failed: {mt5.last_error()}")

        self._connected = True
        self._start_heartbeat()

    def _start_heartbeat(self):
        def heartbeat():
            while self._connected:
                info = mt5.terminal_info()
                if info is None or not info.connected:
                    self._reconnect()
                time.sleep(30)  # Check every 30 seconds

        self._heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
        self._heartbeat_thread.start()

    def _reconnect(self):
        for attempt in range(5):
            try:
                mt5.login(self.login, self.password, self.server)
                return
            except:
                time.sleep(min(2 ** attempt, 60))
        raise ConnectionError("Reconnection failed after 5 attempts")
```

---

## 4. Authentication Architecture for Alpha Stack

### 4.1 Two-Layer Auth Model

Alpha Stack needs TWO separate authentication layers:

```
┌─────────────────────────────────────────────┐
│  Layer 1: Alpha Stack Account               │
│  - User identity (email/password)           │
│  - App preferences, settings sync           │
│  - Subscription/license management          │
│  - Cloud features (optional)                │
├─────────────────────────────────────────────┤
│  Layer 2: Broker Credentials                │
│  - Broker server, login, password           │
│  - Stored LOCALLY ONLY (never sent to cloud)│
│  - Used to connect to MT5 / broker API      │
│  - Per-account encryption                   │
└─────────────────────────────────────────────┘
```

### 4.2 Alpha Stack User Account System

#### Signup Flow
```
User opens app → Sign Up form:
  ├── Email address
  ├── Password (min 8 chars, complexity rules)
  ├── Display name (optional)
  └── Accept ToS / Privacy Policy

Server creates account:
  ├── Hash password (bcrypt/argon2id)
  ├── Generate email verification token
  ├── Send verification email
  └── Return JWT (pending verification)

User verifies email → Full access granted
```

#### Login Flow
```
User enters email + password:
  ├── Server validates credentials
  ├── Checks email verified
  ├── Generates JWT access token (15 min expiry)
  ├── Generates refresh token (7 day expiry, stored server-side)
  └── Returns tokens to client

Client stores:
  ├── Access token: in memory (not persisted)
  └── Refresh token: httpOnly secure cookie (web) / Keychain (desktop/mobile)
```

#### Password Reset Flow
```
User requests reset → Email with magic link (1 hour expiry)
  → User clicks link → Set new password
  → All existing sessions invalidated
  → Broker credentials remain untouched (local-only)
```

### 4.3 JWT Token Structure

```json
{
  "header": {
    "alg": "RS256",
    "typ": "JWT"
  },
  "payload": {
    "sub": "user_abc123",
    "email": "user@example.com",
    "name": "John Doe",
    "iat": 1689100000,
    "exp": 1689100900,
    "iss": "alphastack",
    "aud": "alphastack-app",
    "tier": "pro",
    "email_verified": true
  }
}
```

### 4.4 Broker Credential Storage (Local-Only)

**CRITICAL PRINCIPLE**: Broker credentials NEVER leave the user's device.

#### Desktop (Tauri / Rust)
```rust
use keyring::Entry;

fn store_broker_creds(account_id: &str, server: &str, login: &str, password: &str) -> Result<()> {
    let service = "com.alphastack.broker";

    // Store in OS keyring (Windows Credential Manager / macOS Keychain / Linux Secret Service)
    Entry::new(service, &format!("{account_id}.server"))?.set_password(server)?;
    Entry::new(service, &format!("{account_id}.login"))?.set_password(login)?;
    Entry::new(service, &format!("{account_id}.password"))?.set_password(password)?;

    Ok(())
}

fn load_broker_creds(account_id: &str) -> Result<(String, String, String)> {
    let service = "com.alphastack.broker";

    let server = Entry::new(service, &format!("{account_id}.server"))?.get_password()?;
    let login = Entry::new(service, &format!("{account_id}.login"))?.get_password()?;
    let password = Entry::new(service, &format!("{account_id}.password"))?.get_password()?;

    Ok((server, login, password))
}
```

#### Fallback: Encrypted File (if keyring unavailable)
```rust
use age::secrecy::Secret;
use std::fs;

// Derive key from user's master password or device-specific entropy
fn encrypt_and_store(account_id: &str, data: &str, key: &[u8]) -> Result<()> {
    let encrypted = age::encrypt(&key_to_recipient(key), data.as_bytes())?;
    let path = get_config_dir().join("broker").join(format!("{account_id}.enc"));
    fs::write(path, encrypted)?;
    Ok(())
}
```

### 4.5 2FA (TOTP) Implementation

```
User enables 2FA:
  ├── Generate TOTP secret (base32)
  ├── Show QR code (otpauth:// URI)
  ├── User enters verification code
  ├── Store encrypted secret server-side
  ├── Generate 8 backup codes (single-use)
  └── Return backup codes to user

Login with 2FA:
  ├── Step 1: email + password → returns partial JWT + requires_2fa flag
  ├── Step 2: TOTP code → returns full JWT + refresh token
  └── Backup code accepted as alternative to TOTP
```

### 4.6 OAuth2 for Web-Based Brokers

Some modern brokers support OAuth2 flows:

```
User clicks "Connect Broker" →
  ├── Opens broker's OAuth authorization URL
  ├── User logs in on broker's website
  ├── Broker redirects back with auth code
  ├── Alpha Stack exchanges code for access token
  ├── Access token stored locally (encrypted)
  └── Used for API calls to broker

Token refresh:
  ├── Access token expires (typically 1 hour)
  ├── Silent refresh using refresh token
  └── Re-authorization if refresh fails
```

**Note**: MT5 does NOT support OAuth. This applies only to REST API brokers (OANDA, IBKR, cTrader).

---

## 5. Multi-Platform Auth Flow

### 5.1 Platform-Specific Implementation

#### Desktop (Tauri)
```
Auth Storage:
├── Alpha Stack account: JWT refresh token → OS Keyring
├── Broker credentials: → OS Keyring (per-account)
├── Session timeout: 4 hours idle → auto-lock
└── Biometric: Not available (desktop)

Keyring mapping:
├── Windows: Credential Manager (DPAPI-protected)
├── macOS: Keychain (with user consent prompt)
└── Linux: Secret Service (GNOME Keyring / KWallet)
```

#### Web
```
Auth Storage:
├── Alpha Stack account: JWT in httpOnly Secure SameSite=Strict cookie
├── Broker credentials: NOT AVAILABLE (security restriction)
├── Session timeout: 15 min idle → require re-auth
└── CSRF: Double-submit cookie pattern

Web Limitation:
└── Cannot connect to MT5 directly from browser
    → Must use backend service that runs MT5 Python on Windows
    → Browser ←REST/WS→ Alpha Stack Backend ←MT5 Protocol→ Broker
```

#### Mobile (Future)
```
Auth Storage:
├── Alpha Stack account: Refresh token → iOS Keychain / Android Keystore
├── Broker credentials: → iOS Keychain / Android Keystore
├── Biometric: Face ID / fingerprint to unlock keychain
├── Session timeout: 15 min idle → biometric re-auth
└── Push notifications: Via APNs/FCM for trade alerts
```

### 5.2 Cross-Platform Session Management

```
User logs in on Device A:
  ├── Server creates session (device_id, ip, user_agent)
  ├── Returns JWT + refresh token
  └── Session visible in "Active Sessions" settings

User logs in on Device B:
  ├── Same flow, separate session
  └── Both devices work independently

User changes password:
  ├── All sessions invalidated (except current)
  ├── All refresh tokens revoked
  └── Broker credentials untouched (local-only)

User enables "Logout all devices":
  ├── All sessions terminated
  └── Push notification to other devices
```

### 5.3 Account State Sync (What Syncs vs What Doesn't)

**Syncs (via Alpha Stack servers)**:
- User profile (name, email, avatar)
- App preferences (theme, language, chart layouts)
- Trading strategy templates (without broker-specific params)
- Subscription/license status
- Watchlists

**Does NOT sync (local-only)**:
- Broker credentials (server, login, passwords)
- API keys
- Active trading sessions
- Connection state

---

## 6. Security Requirements

### 6.1 Credential Protection

| Requirement | Implementation |
|---|---|
| Never store broker passwords in plaintext | OS Keyring or AES-256-GCM encrypted files |
| Never send broker credentials to servers | Client-side only; no network transmission |
| Encrypted at rest | Keyring handles this automatically |
| Encrypted in transit | TLS 1.3 for all API calls |
| Auto-lock after inactivity | 15 min web / 4 hour desktop → re-auth |
| Secure memory handling | Zeroize password buffers after use (Rust) |
| No credential logging | Redact all passwords from logs/errors |

### 6.2 Threat Model

```
Threat: Malware on user's machine
  → Mitigation: OS Keyring (requires OS-level compromise to extract)
  → Mitigation: Auto-lock reduces window

Threat: Man-in-the-middle on API calls
  → Mitigation: TLS 1.3 + certificate pinning
  → Mitigation: Broker creds never transit to Alpha Stack servers

Threat: Server breach
  → Impact: Only Alpha Stack account data exposed
  → Broker creds: NOT on server (zero exposure)
  → Passwords: Argon2id hashed (not reversible)

Threat: Stolen device
  → Mitigation: OS keyring requires device password/biometric
  → Mitigation: Remote session invalidation from another device

Threat: Phishing (fake Alpha Stack app)
  → Mitigation: Code signing (desktop), App Store review (mobile)
  → Mitigation: 2FA protects account even if password phished
```

### 6.3 Security Best Practices Checklist

- [ ] Use `age` or `ring` crate for encryption if keyring unavailable
- [ ] Zeroize all password strings after use (`zeroize` crate in Rust)
- [ ] Implement rate limiting on login endpoint (5 attempts / 15 min)
- [ ] Log auth events (login, logout, failed attempts) without logging credentials
- [ ] Implement account lockout after 10 failed attempts
- [ ] Use RS256 (asymmetric) for JWT signing (not HS256)
- [ ] Rotate JWT signing keys periodically
- [ ] Implement token binding (tie refresh token to device fingerprint)
- [ ] CSP headers on web: `strict-dynamic`, no `unsafe-inline`
- [ ] HSTS with long max-age

---

## 7. Alpha Stack Recommended Architecture

### 7.1 System Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    Alpha Stack Desktop (Tauri)            │
│                                                          │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │ Auth Module  │  │ Broker Mgr   │  │ Trading Engine │  │
│  │             │  │              │  │                │  │
│  │ • Login     │  │ • Add Broker │  │ • Place Order  │  │
│  │ • 2FA       │  │ • Credentials│  │ • Positions    │  │
│  │ • Sessions  │  │ • Connect    │  │ • History      │  │
│  └──────┬──────┘  └──────┬───────┘  └───────┬────────┘  │
│         │                │                   │           │
│  ┌──────▼────────────────▼───────────────────▼────────┐  │
│  │              Rust Backend (Tauri Commands)          │  │
│  │                                                     │  │
│  │  • Keyring integration (credential storage)         │  │
│  │  • Python subprocess management (MT5 bridge)        │  │
│  │  • WebSocket server (UI ↔ Python)                   │  │
│  │  • JWT validation middleware                         │  │
│  └─────────────────────┬──────────────────────────────┘  │
│                        │                                 │
└────────────────────────┼─────────────────────────────────┘
                         │
          ┌──────────────┼──────────────┐
          │              │              │
          ▼              ▼              ▼
   ┌────────────┐ ┌────────────┐ ┌────────────┐
   │ Alpha Stack│ │ MT5 Python │ │ Broker API │
   │ Cloud API  │ │ Bridge     │ │ (REST/OAuth)│
   │            │ │ (Win VM)   │ │            │
   │ • Account  │ │ • MT5 conn │ │ • Direct   │
   │ • Sync     │ │ • Trade    │ │   connection│
   │ • License  │ │ • Data     │ │            │
   └────────────┘ └────────────┘ └────────────┘
```

### 7.2 MT5 Connection Architecture

Since MT5 Python is Windows-only, Alpha Stack needs a bridge:

```
Desktop App (any OS)
    │
    │ WebSocket (localhost or LAN)
    ▼
MT5 Bridge Service (Windows)
    │
    │ MetaTrader5 Python API
    ▼
MT5 Terminal (Windows)
    │
    │ MT5 Protocol (TCP/TLS)
    ▼
Broker Server
```

**Options for MT5 Bridge**:
1. **Local Windows machine**: User runs bridge on their own Windows PC
2. **Cloud Windows VM**: Alpha Stack hosts Windows VMs (adds cost)
3. **Broker REST API**: Skip MT5 entirely for brokers with native APIs (best option)

### 7.3 Credential Flow Diagram

```
USER enters broker credentials in Alpha Stack UI
    │
    ▼
Tauri Frontend (React/Vue/Svelte)
    │
    │ IPC invoke (credentials in memory only)
    ▼
Rust Backend
    │
    ├──→ Store in OS Keyring (encrypted, never transmitted)
    │
    ├──→ Pass to MT5 Bridge (via localhost WebSocket, TLS)
    │
    └──→ MT5 Python uses credentials to connect to broker
         │
         ▼
         Credentials flow: Device → MT5 → Broker (direct)
         Never flow: Device → Alpha Stack Cloud
```

### 7.4 Recommended Tech Stack for Auth

| Component | Technology | Rationale |
|---|---|---|
| Password hashing | Argon2id | Best resistance to GPU attacks |
| JWT library | `jsonwebtoken` (Rust) | Well-maintained, RS256 support |
| TOTP | `totp-rs` | TOTP generation/validation |
| Keyring | `keyring` crate | Cross-platform OS keyring |
| Encryption | `age` or `ring` | File-based fallback encryption |
| TLS | `rustls` | Pure Rust, no OpenSSL dependency |
| Session store | Redis (server-side) | Fast, TTL support for sessions |
| Rate limiting | `governor` crate | Token bucket rate limiter |

### 7.5 Data Model

```
// Server-side (Alpha Stack account)
User {
    id: UUID
    email: String (unique, indexed)
    password_hash: String (argon2id)
    name: String
    totp_secret: Option<EncryptedString>
    totp_enabled: bool
    backup_codes: Vec<EncryptedString>
    tier: Enum[free, pro, enterprise]
    created_at: DateTime
    email_verified: bool
}

Session {
    id: UUID
    user_id: UUID (FK)
    device_id: String
    device_name: String
    ip: String
    user_agent: String
    refresh_token_hash: String
    created_at: DateTime
    expires_at: DateTime
    last_active: DateTime
}

// Local-only (never on server)
BrokerAccount {
    id: UUID (local)
    label: String (user-assigned name)
    broker_name: String
    server: String (stored in keyring)
    login: String (stored in keyring)
    password: String (stored in keyring)
    account_type: Enum[demo, live]
    platform: Enum[mt5, ctrader, oanda, ibkr]
    connected: bool
    last_connected: Option<DateTime>
}
```

---

## 8. Implementation Roadmap

### Phase 1: Core Auth (Weeks 1-2)
- [ ] Alpha Stack user signup/login API (Rust backend)
- [ ] JWT token generation and validation
- [ ] Password hashing with Argon2id
- [ ] Email verification flow
- [ ] Tauri frontend auth screens

### Phase 2: Local Credential Storage (Weeks 2-3)
- [ ] OS Keyring integration (Windows, macOS, Linux)
- [ ] Encrypted file fallback
- [ ] Broker account CRUD (add, edit, delete, list)
- [ ] Credential zeroization on logout/delete

### Phase 3: MT5 Connection (Weeks 3-5)
- [ ] MT5 Python bridge service (Windows)
- [ ] WebSocket communication (desktop ↔ bridge)
- [ ] Connection status monitoring
- [ ] Error handling and reconnection logic
- [ ] Demo account testing

### Phase 4: Security Hardening (Weeks 5-6)
- [ ] 2FA (TOTP) implementation
- [ ] Rate limiting and account lockout
- [ ] Session management and "logout all"
- [ ] Security audit of credential handling
- [ ] Penetration testing

### Phase 5: Multi-Platform (Weeks 6-8)
- [ ] Web dashboard (read-only initially)
- [ ] Cross-platform session management
- [ ] Biometric auth for mobile (if applicable)
- [ ] Account settings sync (non-sensitive data)

---

## Appendix A: MT5 Python API Quick Reference

```python
import MetaTrader5 as mt5

# Initialize
mt5.initialize(path="path/to/terminal64.exe")
mt5.login(login=12345678, password="pass", server="Broker-Live")

# Account info
info = mt5.account_info()
# info.login, info.server, info.balance, info.equity, info.leverage, info.trade_mode

# Terminal info
term = mt5.terminal_info()
# term.connected, term.build, term.name, term.company

# Get bars
rates = mt5.copy_rates_from_pos("EURUSD", mt5.TIMEFRAME_H1, 0, 100)

# Get ticks
ticks = mt5.copy_ticks_from("EURUSD", datetime(2026,1,1), 1000, mt5.COPY_TICKS_ALL)

# Place order
request = {
    "action": mt5.TRADE_ACTION_DEAL,
    "symbol": "EURUSD",
    "volume": 0.1,
    "type": mt5.ORDER_TYPE_BUY,
    "price": mt5.symbol_info_tick("EURUSD").ask,
    "deviation": 20,
    "magic": 123456,
    "comment": "alpha_stack",
    "type_time": mt5.ORDER_TIME_GTC,
    "type_filling": mt5.ORDER_FILLING_IOC,
}
result = mt5.order_send(request)

# Shutdown
mt5.shutdown()
```

## Appendix B: Error Codes

| Code | Meaning | Action |
|---|---|---|
| 0 | Success | — |
| 10004 | Trade server busy | Retry after delay |
| 10006 | Request rejected | Check parameters |
| 10013 | Invalid account | Verify login |
| 10014 | Invalid password | Re-enter password |
| 10015 | Authorization failed | Check server name |
| 10016 | Invalid server | Verify server address |
| 10019 | Not enough money | Check balance |
| 10021 | No price | Wait for quotes |

## Appendix C: Keyring Platform Details

| Platform | Backend | Storage | Protection |
|---|---|---|---|
| Windows | Windows Credential Manager | Per-user vault | DPAPI |
| macOS | Keychain Services | System/default keychain | User password + ACL |
| Linux | Secret Service (D-Bus) | GNOME Keyring / KWallet | Login password |
| iOS | Keychain Services | App-accessible | Device passcode + biometric |
| Android | Keystore | Hardware-backed (if available) | Biometric / PIN |

---

*This document should be updated as Alpha Stack architecture evolves and as broker APIs change.*
