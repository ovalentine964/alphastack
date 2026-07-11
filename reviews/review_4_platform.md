# Review 4 — Platform Architecture Validation

> **Date:** 2026-07-11  
> **Scope:** Validate coherence of multi-platform architecture across desktop, web, mobile, and broker layers  
> **Reports Reviewed:** 8 research documents

---

## Executive Summary

The platform research contains **strong individual reports** but suffers from **critical cross-document inconsistencies** that undermine the multi-platform vision. The most severe issue: three different frontend frameworks are recommended (Tauri/React for desktop, Next.js/React for web, Flutter/Dart for mobile) despite a separate multi-platform research report recommending a single Flutter codebase for all platforms. The broker connector layer is well-designed in abstraction but has practical deployment gaps across platforms. Authentication is fragmented with no unified cross-device identity.

**Overall Coherence Score: 5.5/10** — Individual pieces are solid; the assembly is not.

---

## 1. Multi-Platform Strategy Consistency

### ❌ CRITICAL: Framework Fragmentation

| Platform | Report Recommends | Framework | Language |
|----------|------------------|-----------|----------|
| Desktop | `research_12_desktop_app_architecture.md` | **Tauri 2.x** | Rust + React/TS |
| Web | `research_web_app.md` | **Next.js 15** | React/TS |
| Mobile | `research_mobile_app.md` | **Flutter** | Dart |
| Multi-Platform | `research_multi_platform.md` | **Flutter** (all platforms) | Dart |

**The contradiction:** The multi-platform research explicitly recommends Flutter for all 6 platforms (Android, iOS, Web, Windows, macOS, Linux) with ~95% code sharing. Yet the three platform-specific reports each chose different frameworks, resulting in:

- **3 separate codebases** to maintain (Tauri/Rust, Next.js/React, Flutter/Dart)
- **~0% UI code sharing** between desktop and mobile
- **~60% logic sharing** between web and desktop (both React) but 0% with mobile
- **3 different state management approaches** (Zustand for desktop/web, Riverpod/Bloc for Flutter)
- **3 different build pipelines** (Tauri bundler, Next.js/Vite, Flutter build)

### What Should Have Happened

The multi-platform research should have been the **binding document** that constrained the platform-specific research. Instead, each platform report was written independently, optimizing locally rather than globally.

### Possible Resolutions

| Option | Approach | Tradeoff |
|--------|----------|----------|
| **A: Adopt Flutter everywhere** | Rewrite desktop as Flutter Desktop, web as Flutter Web, mobile as Flutter | Maximum code sharing (~95%); loses Tauri's tiny binaries and React ecosystem |
| **B: Adopt React everywhere** | Desktop = Tauri + React, Web = Next.js, Mobile = React Native | Good sharing (~65%); 3 frameworks but shared language (TS) |
| **C: Accept fragmentation** | Keep all 3, invest in shared backend/API layer | Most flexibility; highest maintenance cost |
| **D: Shared Rust core + platform UIs** | Rust core compiled as WASM (web), native lib (desktop/mobile), platform-specific UIs | Best performance; complex build pipeline |

**Recommendation:** Option B (React everywhere) is the pragmatic choice given the desktop report already committed to Tauri + React. React Native for mobile shares TypeScript, component patterns, and npm ecosystem with the desktop/web codebases. This gives ~65% code sharing with the lowest migration cost.

---

## 2. Broker Connector Cross-Platform Compatibility

### ⚠️ SIGNIFICANT: Connector Layer Platform Gaps

The broker connector abstraction (`BrokerConnector` ABC in `research_hybrid_broker_architecture.md`) is well-designed but has platform-specific deployment problems:

| Connector | Desktop (Tauri) | Web (Next.js) | Mobile (Flutter) |
|-----------|----------------|---------------|-----------------|
| **MT5 (Python)** | ✅ Works via Python sidecar | ⚠️ Requires desktop running | ❌ No Python runtime on mobile |
| **CCXT (Python)** | ✅ Works via Python sidecar | ⚠️ Requires desktop running | ❌ No Python runtime on mobile |
| **OANDA (REST)** | ✅ Via Rust or Python | ✅ Direct from browser (via BFF) | ✅ HTTP client in Dart |
| **IBKR (TCP)** | ✅ Via Python sidecar | ❌ Cannot run TWS in browser | ❌ No TCP sockets on mobile |

### The Core Problem

The broker connector layer is implemented in **Python** (research_hybrid_broker_architecture.md uses Python throughout). Python works as a sidecar in the Tauri desktop app but:

1. **Web app** cannot run Python — it relies on the desktop's built-in FastAPI server (port 9222). If the desktop isn't running, the web app has no data.
2. **Mobile app** cannot run Python at all. Flutter has no Python integration path.
3. **Only REST API brokers** (OANDA) work natively from web/mobile without the desktop intermediary.

### Missing: Platform-Native Connector Implementations

The research should have addressed how each platform implements the connector layer:

| Platform | Recommended Approach |
|----------|---------------------|
| Desktop | Python sidecar (current design) — works |
| Web | Server-side BFF (Next.js API routes) calling broker REST APIs directly |
| Mobile | Native Dart implementations of REST/WebSocket connectors (CCXT-equivalent in Dart, or HTTP calls to a hosted backend) |

### Symbol Normalization Gap

The `SymbolNormalizer` (in `research_hybrid_broker_architecture.md`) is defined in Python. This normalization logic needs to exist in:
- Rust (desktop core engine)
- TypeScript (web API routes)
- Dart (mobile app)

**No research addresses this duplication.**

---

## 3. Authentication Flow Consistency

### ⚠️ SIGNIFICANT: Fragmented Auth Model

Each platform has a different authentication architecture:

| Aspect | Desktop (Tauri) | Web (Next.js) | Mobile (Flutter) |
|--------|----------------|---------------|-----------------|
| **User Login** | JWT (Rust backend) | JWT (httpOnly cookies) | JWT (Dart HTTP client) |
| **Token Storage** | OS Keyring (Rust `keyring` crate) | httpOnly Secure cookie | iOS Keychain / Android Keystore |
| **Broker Creds** | OS Keyring (local only) | ❌ Not available (security) | OS Keychain (local only) |
| **2FA** | TOTP via Rust `totp-rs` | TOTP via server-side | TOTP via Dart package |
| **Biometric** | ❌ Not applicable | WebAuthn (browser) | `local_auth` package |
| **Session Mgmt** | 4-hour idle timeout | 15-min idle timeout | 15-min idle + biometric |

### Issues Identified

1. **No unified user identity service.** Each platform implements auth independently. There's no central auth server that issues tokens consumed by all platforms.

2. **Broker credentials don't sync.** This is by design (security), but it means users must re-enter broker credentials on every device. For a multi-broker system with 3-5 broker connections, this is a significant UX friction.

3. **No cross-device session awareness.** The research mentions "Active Sessions" in settings but doesn't define the API or data model for session management across platforms.

4. **Web can't trade without desktop.** The web app has no broker credential storage, so it can only monitor via the desktop's WebSocket proxy. This makes the "web companion" a read-only dashboard, not a full trading platform.

5. **Inconsistent timeout policies.** Desktop allows 4-hour idle (appropriate for a trading terminal), but web and mobile use 15-minute timeouts. For a trader checking positions on their phone, 15 minutes is too aggressive.

### What's Missing

- A **centralized auth service** (could be the Alpha Stack cloud API) that handles user identity, with broker credentials remaining local
- A **device registration flow** where each platform registers with the central auth service
- A **unified 2FA setup** that works across all platforms (not independent TOTP setups per device)
- **Cross-device credential sharing** via secure enclave (e.g., encrypted credential export/import, or a "pair device" flow)

---

## 4. Platform-Specific Issues Not Addressed

### 4.1 MT5 Windows Dependency

**Severity: HIGH**

The MT5 Python library is **Windows-only**. The desktop research acknowledges this (Wine/Bottles on Linux, native on Windows) but the implications for other platforms are not addressed:

- **Web:** Cannot connect to MT5 at all from a browser. Requires the desktop to be running as a relay.
- **Mobile:** Same — no MT5 connectivity. Must use REST API brokers (OANDA, CCXT-based crypto) or a hosted backend.
- **Linux desktop:** Wine/Bottles adds complexity and fragility. The research mentions a "Cloud MT5 (VPS)" fallback but doesn't detail the architecture.

**Unaddressed question:** If the user's primary broker is FXPesa (MT5), how do web and mobile platforms access it? The research implies the desktop must always be running — this is a significant availability constraint.

### 4.2 iOS App Store Licensing

**Severity: HIGH**

The mobile research (`research_mobile_app.md`) correctly identifies that Apple requires financial apps to be "properly licensed in ALL jurisdictions." However:

- No research addresses **what license** Alpha Stack needs
- No research addresses whether Alpha Stack is a **broker** (needs licensing) or a **software tool** (may not)
- The recommendation to "partner with a licensed entity" is vague — which entity? What partnership model?
- If Alpha Stack executes trades on behalf of users, it may be classified as an **investment advisor** in many jurisdictions

### 4.3 Desktop Background Operation

**Severity: MEDIUM**

The desktop research designs for system tray operation (trading continues when minimized). But:

- **macOS App Nap** may throttle background apps — unaddressed
- **Windows battery saver** mode may limit background activity — unaddressed
- **Linux systemd** integration for headless operation (server deployment) — mentioned but not detailed

### 4.4 Web App Offline Capabilities

**Severity: MEDIUM**

The web research mentions PWA and service workers but doesn't address:

- What happens when the WebSocket connection drops during an active trade?
- Can the web app queue orders for later submission? (Research says yes, but no implementation detail)
- How does the web app handle stale cached position data? (Showing old P&L could lead to bad decisions)

### 4.5 Mobile Background Processing on iOS

**Severity: HIGH**

The mobile research correctly identifies that iOS suspends apps after ~30 seconds in background. The recommendation is "use push notifications instead of background monitoring." But:

- Push notifications require a **server-side component** to detect trading signals and send notifications
- The current architecture has the **desktop** as the signal generator — if the desktop is off, no notifications
- No research defines the server-side notification infrastructure

### 4.6 Flutter Web Performance for Trading

**Severity: MEDIUM**

The multi-platform research recommends Flutter Web with CanvasKit renderer. However:

- Flutter Web's CanvasKit renderer downloads ~2MB of WASM on first load
- Canvas rendering in Flutter Web is significantly slower than native Canvas (TradingView Lightweight Charts)
- No trading-specific Flutter Web benchmarks are cited
- The web app research (`research_web_app.md`) independently recommends Next.js — directly contradicting Flutter Web

---

## 5. Data Flow Consistency

### ⚠️ SIGNIFICANT: Desktop as Single Point of Failure

The data flow architecture has a critical dependency:

```
Desktop (Tauri) — Source of Truth
    ├── Runs trading engine (Rust)
    ├── Runs AI models (Python sidecar)
    ├── Connects to MT5 (Python)
    ├── Runs WebSocket server (port 9222)
    └── Runs REST API (FastAPI, port 9223)
         │
         ├── Web app connects via WebSocket/REST
         └── Mobile app connects via WebSocket/REST
```

**Problem:** Web and mobile are **display-only clients** of the desktop. If the desktop is off, web and mobile show nothing.

### What's Missing

1. **Cloud relay service.** No research defines a cloud backend that can relay data from desktop to mobile/web when they're not on the same network. The desktop research mentions Cloudflare Tunnel but this is an optional add-on, not an architecture.

2. **Data persistence layer.** Where is trade history stored? The desktop uses SQLite (local). If the user checks from their phone, can they see yesterday's trades? Not without the desktop running.

3. **Real-time data consistency.** If the desktop streams via WebSocket and the mobile connects later, how does the mobile catch up on missed events? No research defines a replay/resync protocol.

4. **Multi-device write conflicts.** If a user opens a position from the web app (via desktop proxy) and simultaneously modifies it from the mobile app, what happens? No conflict resolution is defined.

### Data Flow Matrix

| Data Type | Desktop Source | Web Access | Mobile Access | Offline? |
|-----------|---------------|------------|---------------|----------|
| Live prices | MT5/CCXT → Rust → WS | Via desktop WS | Via desktop WS | ❌ |
| Positions | MT5/CCXT → Rust → WS | Via desktop WS | Via desktop WS | ❌ |
| Trade history | SQLite (local) | Via desktop REST | Via desktop REST | ❌ |
| AI signals | Python → Rust → WS | Via desktop WS | Via desktop WS | ❌ |
| Settings | Local config | No sync | No sync | ✅ (local) |
| Charts | Local data + live feed | Via desktop | Via desktop | Partial |

**Everything depends on the desktop being online.** This is a fundamental architectural limitation that none of the research addresses as a solvable problem.

---

## 6. Unaddressed Platform Risks

### Risk 1: No Cloud Backend = No True Multi-Platform

| Impact | Likelihood | Description |
|--------|-----------|-------------|
| **Critical** | **Certain** | Web and mobile are useless without the desktop running. Users expect mobile apps to work independently. |

**Mitigation:** Define a cloud backend (even a lightweight one) that can:
- Store trade history and account state
- Relay signals to mobile via push notifications
- Provide a read-only API when the desktop is offline
- Host a lightweight version of the trading engine for always-on operation

### Risk 2: Three Frameworks = Three Teams

| Impact | Likelihood | Description |
|--------|-----------|-------------|
| **High** | **Likely** | Maintaining Tauri (Rust), Next.js (React), and Flutter (Dart) requires expertise in three ecosystems. A solo developer or small team cannot maintain all three effectively. |

**Mitigation:** Consolidate to two frameworks maximum (e.g., React/TypeScript for web + desktop via Tauri, React Native for mobile).

### Risk 3: MT5 Platform Lock-In

| Impact | Likelihood | Description |
|--------|-----------|-------------|
| **High** | **Certain** | MT5's Windows-only Python library forces a Windows dependency for forex trading. This limits deployment options and creates a single point of failure. |

**Mitigation:** Prioritize REST API brokers (OANDA) for multi-platform support. Use MT5 only on desktop, with OANDA as the primary broker for web/mobile.

### Risk 4: App Store Rejection

| Impact | Likelihood | Description |
|--------|-----------|-------------|
| **High** | **Likely** | Apple's financial app requirements are strict. Without proper licensing documentation, the iOS app will be rejected. |

**Mitigation:** Begin licensing research immediately. Consider launching Android-only first (less strict review). Partner with a licensed broker entity.

### Risk 5: Credential Management Complexity

| Impact | Likelihood | Description |
|--------|-----------|-------------|
| **Medium** | **Certain** | Broker credentials stored locally on each device with no sync means users with 3 devices × 5 brokers = 15 credential entries to manage. |

**Mitigation:** Implement a secure credential export/import flow (encrypted file, QR code pairing, or cloud-synced encrypted vault with user-held keys).

### Risk 6: No Offline Trading Capability

| Impact | Likelihood | Description |
|--------|-----------|-------------|
| **Medium** | **Likely** | Mobile users expect to at least VIEW their positions offline. The current architecture requires live connection to desktop for any data. |

**Mitigation:** Implement local caching on mobile (SQLite/Hive) with last-known positions and prices. Show staleness indicators.

### Risk 7: WebSocket Reliability on Mobile Networks

| Impact | Likelihood | Description |
|--------|-----------|-------------|
| **Medium** | **Likely** | Mobile networks frequently drop connections (tunnels, handoffs, poor coverage). WebSocket reconnection on mobile is unreliable. |

**Mitigation:** Implement HTTP polling fallback for mobile when WebSocket fails. Use push notifications for critical alerts instead of relying on persistent connections.

### Risk 8: Desktop Resource Contention

| Impact | Likelihood | Description |
|--------|-----------|-------------|
| **Medium** | **Possible** | Tauri desktop runs Rust core + Python sidecar + MT5 (under Wine on Linux) + WebSocket server. Resource contention on low-end machines could affect trading performance. |

**Mitigation:** Profile resource usage early. Consider separating the trading engine into a standalone service that can run headless on a server.

---

## 7. Recommendations Summary

### Immediate Actions (Before Implementation)

| # | Action | Priority |
|---|--------|----------|
| 1 | **Resolve framework fragmentation.** Choose max 2 frameworks. Recommended: Tauri + React (desktop/web), React Native (mobile). | 🔴 Critical |
| 2 | **Define cloud backend architecture.** At minimum: auth service, trade history API, push notification relay. | 🔴 Critical |
| 3 | **Design cross-platform auth flow.** Central auth server + local broker credential storage with device registration. | 🔴 Critical |
| 4 | **Address MT5 platform dependency.** Prioritize OANDA as the primary multi-platform forex broker. MT5 desktop-only. | 🟠 High |
| 5 | **Research licensing requirements.** Engage legal counsel for iOS App Store compliance. | 🟠 High |
| 6 | **Define offline data strategy.** What caches locally on each platform? How stale is acceptable? | 🟡 Medium |

### Architecture Corrections

| Current Design | Problem | Recommended Fix |
|---------------|---------|-----------------|
| Desktop = only backend | Web/mobile are useless without desktop | Add lightweight cloud backend |
| Python broker connectors | Can't run on mobile/web | Port to TypeScript (web) and Dart (mobile), or use hosted backend |
| No credential sync | Users re-enter creds on every device | Encrypted credential export/import or cloud vault |
| Flutter for mobile only | 0% code sharing with desktop/web | Use React Native (shares TS with Tauri/Next.js) |
| No offline mobile support | Mobile requires live desktop connection | Local SQLite cache + push notifications |

---

## 8. Coherence Matrix

| Dimension | Desktop | Web | Mobile | Cross-Platform | Score |
|-----------|---------|-----|--------|---------------|-------|
| Framework choice | ✅ Well-justified | ✅ Well-justified | ✅ Well-justified | ❌ Inconsistent | 5/10 |
| Broker connectivity | ✅ Full (via Python) | ⚠️ Depends on desktop | ⚠️ REST only | ❌ No unified path | 4/10 |
| Authentication | ✅ Secure design | ✅ Standard patterns | ✅ Platform-appropriate | ❌ No unified identity | 5/10 |
| Data flow | ✅ Well-designed locally | ⚠️ Desktop-dependent | ⚠️ Desktop-dependent | ❌ No cloud layer | 4/10 |
| Security | ✅ Strong (Rust, keyring) | ✅ Strong (httpOnly, CSP) | ✅ Strong (Keychain/Keystore) | ⚠️ Credential fragmentation | 7/10 |
| Offline support | ✅ Local SQLite | ⚠️ PWA basics only | ❌ Not addressed | ❌ No strategy | 3/10 |
| Build/deploy | ✅ CI/CD defined | ✅ Standard (Vercel) | ⚠️ App store risk | ⚠️ 3 separate pipelines | 5/10 |
| **Overall** | **7/10** | **6/10** | **5/10** | **3/10** | **5.5/10** |

---

## 9. Conclusion

The individual research reports are **thorough and well-reasoned** within their respective domains. The desktop architecture (Tauri + Rust + Python sidecar) is particularly strong. The broker connector abstraction is well-designed. The security model is sound.

However, the **cross-platform story is broken.** Three different frontend frameworks, no cloud backend, desktop-dependent web/mobile, and no unified authentication create a system that is really three separate applications loosely connected by WebSocket, not a coherent multi-platform product.

**The fix is architectural, not incremental.** Before writing code, the team must:
1. Choose a unified frontend strategy (max 2 frameworks)
2. Define what the cloud backend looks like (even minimal)
3. Design the cross-platform auth and data sync flows
4. Decide if "multi-platform" means "one product, many screens" or "three related products"

Without these decisions, implementation will produce three diverging codebases that share a name but not a codebase.

---

*Validation completed by platform research review agent. 8 documents analyzed.*
