# Cross-Platform Architecture Design Review

> **Reviewer:** Cross-Platform Architecture Review Agent  
> **Date:** 2026-07-11  
> **Scope:** Desktop (Tauri 2.x / React), Mobile (Flutter / Dart), Web (MISSING), Channels (OpenClaw)  
> **Status:** ⚠️ Web architecture document not found — review covers available platforms only

---

## Executive Summary

The Alpha Stack multi-platform architecture presents a **well-thought-out but fragmented** design across desktop and mobile, with a strong channel integration layer. The desktop architecture (Tauri + React) is the most complete and serves as the de facto reference implementation. The mobile architecture (Flutter) is comprehensive but diverges significantly from desktop in technology stack, state management, and component patterns. **The absence of a web architecture document is a critical gap** that prevents full cross-platform validation.

**Overall Assessment: CONDITIONAL PASS — with significant risks requiring mitigation.**

| Area | Verdict | Severity |
|------|---------|----------|
| UI Consistency | ⚠️ Partial | Medium |
| Shared Backend | ❌ Not Confirmed | High |
| Auth Flow Consistency | ⚠️ Inconsistent | Medium |
| Platform-Specific Issues | ⚠️ Several Identified | Medium |
| Notification Consistency | ✅ Well-Designed | Low |
| Cross-Platform Risks | ⚠️ Multiple | High |

---

## 1. UI Consistency Across Platforms

### 1.1 Design System Alignment

| Token | Desktop (Tauri) | Mobile (Flutter) | Consistent? |
|-------|----------------|------------------|-------------|
| Background Base | `#0a0a1a` | `#0A0E1A` | ❌ No — slightly different |
| Background Surface | `#111827` | `#111827` | ✅ Yes |
| Background Elevated | `#1f2937` | `#1F2937` | ✅ Yes |
| Text Primary | `#f9fafb` | `#F9FAFB` | ✅ Yes |
| Text Secondary | `#9ca3af` | `#9CA3AF` | ✅ Yes |
| Profit/Bull | `#22c55e` | `#10B981` | ❌ No — different greens |
| Loss/Bear | `#ef4444` | `#EF4444` | ✅ Yes |
| Accent | `#3b82f6` | `#3B82F6` | ✅ Yes |
| Warning | `#f59e0b` | `#F59E0B` | ✅ Yes |
| Font UI | Inter | Inter | ✅ Yes |
| Font Mono | JetBrains Mono | JetBrains Mono | ✅ Yes |
| Spacing Base | 4px | 4px (`xs = 4`) | ✅ Yes |
| Border Radius (cards) | 6px | 8px-12px | ❌ No — mobile uses larger radii |

**Findings:**
- **🔴 Color Drift (Profit/Bull):** Desktop uses `#22c55e` while mobile uses `#10B981`. These are noticeably different greens. Profit/loss colors are the most semantically important colors in a trading app — they MUST be identical.
- **🔴 Background Base Mismatch:** `#0a0a1a` vs `#0A0E1A` — minor but should be unified.
- **🟡 Border Radius Inconsistency:** Desktop uses 6px for cards; mobile uses 8-16px. Acceptable for platform feel, but the difference is large enough to feel like different products.
- **🟡 No Shared Token Source:** There is no single source of truth (e.g., a JSON/CSS variables file) that both platforms consume. Each platform hardcodes its own values. This WILL lead to drift over time.

**Recommendation:**
> Create a shared design token file (JSON or YAML) that both Tauri and Flutter consume at build time. Include all colors, typography, spacing, and border radius values. A single change propagates to all platforms.

### 1.2 Layout & Navigation Consistency

| Aspect | Desktop | Mobile | Notes |
|--------|---------|--------|-------|
| Primary Nav | Left rail (icon bar) | Bottom tab bar | ✅ Platform-appropriate |
| Pages | Dashboard, Trades, Analytics, Agents, Journal, Settings | Dashboard, Trade, Quick Trade, Agents, Settings | ⚠️ Mobile missing Analytics & Journal as standalone pages |
| Dashboard Layout | Multi-panel (resizable) | Single-column scroll | ✅ Platform-appropriate |
| Chart | TradingView LW Charts (full) | Custom Paint + WebView fallback | ⚠️ Different implementations |
| Trade Entry | Dedicated panel + quick bar | Quick trade sheet + swipe actions | ✅ Platform-appropriate |
| Agent Monitoring | Full detail with ReAct traces | Simplified card view | ⚠️ Significant capability gap |

**Findings:**
- **🟡 Missing Mobile Pages:** Analytics and Journal are not standalone pages on mobile. The desktop has rich analytics (equity curve, P&L heatmap, symbol breakdown, session breakdown) and a full journal with chart replay. Mobile has none of this — these are critical for traders who want to review performance away from their desk.
- **🟡 Chart Implementation Divergence:** Desktop uses TradingView Lightweight Charts (JS/Canvas). Mobile uses a custom Flutter `CustomPaint` engine with a WebView fallback. This means chart rendering, indicator calculations, and drawing tools will behave differently across platforms. Bugs in one won't manifest in the other, and features may diverge.
- **🟢 Navigation Model:** Both platforms use platform-appropriate navigation patterns (rail vs tabs). This is correct.

**Recommendation:**
> Add Analytics and Journal screens to the mobile app (can be simplified versions). Ensure chart feature parity by maintaining a shared indicator calculation library or at minimum a shared specification document.

### 1.3 Data Display Consistency

| Data Point | Desktop Format | Mobile Format | Consistent? |
|------------|---------------|---------------|-------------|
| Price | Monospace, tabular nums, 14-24px | Monospace, 14-28px | ✅ Close enough |
| P&L | Currency + %, green/red | Currency + %, green/red | ✅ Yes |
| Signal Card | Full agent verdicts, confluence score | Simplified (confidence %, entry/SL/TP) | ⚠️ Mobile shows less detail |
| Position Table | Full table with all columns | Horizontal card carousel | ✅ Platform-appropriate |
| Agent Status | Full ReAct trace, detailed metrics | Status dot + latency | ⚠️ Mobile is significantly reduced |

**Recommendation:**
> Ensure that while presentation differs, the same data fields are available on both platforms. Mobile should offer drill-down to access the same detail level as desktop.

---

## 2. Backend Sharing

### 2.1 Current Architecture

| Component | Desktop | Mobile | Shared? |
|-----------|---------|--------|---------|
| Trading Engine | Rust backend (Tauri) → Python sidecar → MT5 | Not specified (assumes REST/WS) | ❓ Unclear |
| Data Layer | Tauri IPC events + WebSocket (localhost:9222) | WebSocket + REST API + Isar DB (local) | ❌ Different patterns |
| State Management | Zustand (React) | Riverpod (Flutter) | ❌ Different frameworks (expected) |
| Chart Data | Tauri events → Lightweight Charts | WebSocket → Custom Paint | ❌ Different pipelines |
| Local Storage | `~/.alphastack/` files (JSON) | Isar DB + FlutterSecureStorage | ❌ Different storage |

**Critical Finding:**
> **🔴 The desktop architecture describes a local-first system** where the Rust core runs on the same machine, communicates via Tauri IPC, and connects to MT5 via a local Python sidecar. The mobile architecture describes a **client-server model** with WebSocket + REST API, implying a remote backend. **These are fundamentally different architectures, and the web architecture (which would bridge them) is missing.**

**The key question is: Does Alpha Stack have a centralized backend, or is it purely local?**

- If **local-first**: Mobile cannot access the same trading engine unless it connects to the desktop over the network (the desktop's WebSocket on `localhost:9222` would need to be exposed — a security concern).
- If **cloud backend**: Both desktop and mobile should connect to the same API. But the desktop architecture doesn't describe a cloud API — it describes local Tauri IPC.

**This is the single most critical cross-platform risk.**

**Recommendation:**
> Define a clear backend architecture:
> 1. **Option A (Local-first):** Desktop acts as the hub; mobile connects to it over LAN/WAN. Requires secure API exposure, authentication, and NAT traversal.
> 2. **Option B (Cloud backend):** Extract the trading engine into a cloud service. Both desktop and mobile connect via the same REST/WebSocket API. Desktop Tauri becomes a thin client.
> 3. **Option C (Hybrid):** Desktop runs locally with full engine; cloud service handles sync, notifications, and mobile access.
>
> Document this decision in a shared `architecture_backend.md`.

### 2.2 WebSocket Protocol

Desktop exposes `localhost:9222` for web/mobile companions (Section 15.1 of desktop architecture). However:
- No WebSocket message schema is defined
- No authentication mechanism for the WebSocket is specified
- No reconnection protocol is documented
- Mobile uses a different WebSocket client pattern (Riverpod stream providers)

**Recommendation:**
> Define a shared WebSocket protocol specification (JSON schema, message types, auth handshake, heartbeat, reconnection behavior) that both desktop and mobile implement identically.

---

## 3. Authentication Flow Consistency

### 3.1 Desktop Authentication

- **Credentials:** MT5 login/password stored in OS keychain
- **App Lock:** Not specified (no biometric/PIN mentioned)
- **Session:** Implicit — app runs with OS-level security

### 3.2 Mobile Authentication

- **Credentials:** MT5 login/password stored in FlutterSecureStorage (Android Keystore / iOS Keychain)
- **App Lock:** Biometric (Face ID / Touch ID / fingerprint) with PIN fallback
- **Session:** Explicit — lock screen on app launch and resume after 5 minutes
- **Auth Levels:** View prices (no auth), View positions (biometric once), Execute trades (biometric every time), Change settings (biometric + confirmation)

### 3.3 Channel Authentication

- **Telegram:** Chat ID whitelist + pairing verification
- **Discord:** Guild + role-based access
- **WhatsApp:** Phone number whitelist
- **Command Authorization:** Read commands (any authenticated user), Control commands (primary user only), Admin commands (primary user + logged)

### 3.4 Gaps & Inconsistencies

| Issue | Severity | Description |
|-------|----------|-------------|
| **No Desktop App Lock** | 🔴 High | Desktop has no biometric/PIN lock. Anyone with access to the computer can view positions, execute trades, and change settings. Mobile has robust biometric auth. This is a serious security gap for a financial application. |
| **No Cross-Platform Session Sync** | 🟡 Medium | If a user logs in on desktop and mobile, there's no mechanism to sync session state. If they pause trading on one platform, does the other know? |
| **Channel Auth ≠ App Auth** | 🟡 Medium | Channel authentication (chat ID whitelist) is separate from app authentication (biometric). A compromised Telegram account could issue trading commands. Consider requiring biometric confirmation for destructive channel commands. |
| **No 2FA Specified** | 🟡 Medium | Neither platform implements two-factor authentication for sensitive operations. The mobile mentions "Biometric + 2FA" for viewing sensitive data (Section 10.1) but doesn't specify the 2FA mechanism. |

**Recommendation:**
> 1. Add app lock (PIN + optional biometric) to the desktop app
> 2. Define a shared authentication state that both platforms can reference
> 3. Implement trade execution confirmation via channel (e.g., approve a trade on Telegram that was initiated on desktop)
> 4. Specify the 2FA mechanism for mobile's "sensitive data" access level

---

## 4. Platform-Specific Issues

### 4.1 Desktop (Tauri 2.x)

| Issue | Severity | Description |
|-------|----------|-------------|
| **Linux MT5 via Wine** | 🔴 High | MT5 runs via Wine on Linux. This is inherently fragile — Wine updates can break MT5, and the Python sidecar bridge adds latency and failure modes. The architecture acknowledges this ("Monitor Wine process health") but doesn't specify recovery behavior. |
| **System Tray Fragmentation** | 🟡 Medium | GNOME uses AppIndicator extension (not always installed); KDE has native tray. The architecture notes "Test both" but doesn't specify fallback behavior when tray is unavailable. |
| **No Auto-Update Mechanism** | 🟡 Medium | Desktop mentions "Auto-update: Toggle On" in settings but doesn't describe the update mechanism. Tauri supports auto-updates via `tauri-plugin-updater`, but it needs a distribution server. |
| **Custom Titlebar Risks** | 🟡 Medium | Custom titlebars on Linux can conflict with tiling window managers (i3, Sway, Hyprland). The architecture doesn't address this. |

### 4.2 Mobile (Flutter)

| Issue | Severity | Description |
|-------|----------|-------------|
| **No Offline Trading Capability** | 🔴 High | The architecture mentions "Offline Mode" (Section 12) but trading requires a live connection. The offline mode likely only covers viewing cached data. This should be explicit. |
| **Custom Chart Engine Maintenance** | 🟡 Medium | Building a custom candlestick chart engine in Flutter (CustomPaint) is a significant engineering effort. The fallback to TradingView in WebView adds complexity. Maintaining two chart engines doubles the bug surface. |
| **Isar DB Deprecation Risk** | 🟡 Medium | Isar v4 is listed as a dependency. Isar has had maintenance concerns in the Flutter community. Consider drift (formerly moor) or sqflite as alternatives. |
| **Voice Commands Scope** | 🟢 Low | Voice commands (Section 14) are ambitious but not critical for launch. The `speech_to_text` and `flutter_tts` packages are mature but voice accuracy for financial terms (pip, lot, forex pairs) may be poor. |

### 4.3 Channels (OpenClaw)

| Issue | Severity | Description |
|-------|----------|-------------|
| **WhatsApp API Cost** | 🟡 Medium | WhatsApp Business API (via Twilio or Meta) has per-message costs. High-frequency trading alerts could generate significant costs. The architecture doesn't discuss cost controls. |
| **Signal (Matrix) Integration** | 🟡 Medium | Signal doesn't have an official bot API. The architecture lists "Signal (Matrix)" which implies using a Matrix bridge. This adds infrastructure complexity and may violate Signal's ToS. |
| **No Rate Limiting** | 🟡 Medium | The notification engine doesn't specify rate limits per channel. A volatile market could trigger dozens of alerts per minute, potentially hitting Telegram's rate limits (30 messages/second to different chats, 20 messages/minute to the same chat). |

---

## 5. Notification System Consistency

### 5.1 Cross-Channel Notification Matrix

The channel architecture defines a clean priority system (P0-P3) with routing rules:

| Priority | Desktop | Mobile | Telegram | WhatsApp | Email |
|----------|---------|--------|----------|----------|-------|
| P0 (Critical) | OS notification + sound | Push (FCM/APNs) + vibration | Immediate | Immediate | Immediate |
| P1 (High) | OS notification + sound | Push + vibration | Immediate | Immediate | — |
| P2 (Medium) | Toast + sound | In-app banner | Primary only | — | — |
| P3 (Low) | Toast | In-app | Scheduled | — | Scheduled |

**Findings:**
- **✅ Notification Priority System:** Well-designed with clear routing rules. P0 events fan out to all channels; P2/P3 are batched. This is solid.
- **✅ Quiet Hours:** Properly implemented with P0 override. Sensible design.
- **✅ Channel-Specific Formatting:** Each channel has appropriately adapted message formats (Telegram: markdown + inline keyboards; WhatsApp: plain text; Discord: embeds; Email: HTML).
- **⚠️ Desktop Notification Coverage:** The desktop architecture defines 9 notification types with per-channel toggles (Section 6.2). The channel architecture defines event types but doesn't map 1:1 to the desktop's notification settings. Need to ensure parity.
- **⚠️ Mobile Push vs Channel Push:** Mobile receives push notifications via FCM/APNs AND channel notifications (e.g., Telegram). A trade signal could appear twice — once as a Telegram message and once as a mobile push. The architecture doesn't define deduplication logic.

**Recommendation:**
> 1. Map desktop notification settings 1:1 to channel notification types
> 2. Implement deduplication: if the user has the Telegram app installed on their phone, suppress the FCM push for events already delivered via Telegram bot
> 3. Add cost estimation for WhatsApp notifications based on expected alert frequency

### 5.2 Acknowledgment System

The P0 acknowledgment system is well-designed:
- Sends to all channels
- 5-minute ack timer
- Escalation to SMS if no ack
- Logging of unacknowledged events

**Gap:** The acknowledgment flow doesn't specify how desktop and mobile coordinate. If a P0 event is acknowledged on Telegram, does the desktop notification dismiss? Does the mobile notification clear?

**Recommendation:**
> Implement a shared acknowledgment state (via the backend) so that acknowledging a P0 event on any platform clears it on all others.

---

## 6. Cross-Platform Risks

### 6.1 Risk Register

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| 1 | **No unified backend** — desktop and mobile may operate on different data sources | High | Critical | Define backend architecture (local vs cloud vs hybrid) immediately |
| 2 | **Design token drift** — colors, spacing, typography diverge over time | High | Medium | Create shared design token file consumed by both platforms at build time |
| 3 | **Feature parity gap** — desktop has Analytics, Journal, full Agent monitoring; mobile does not | High | Medium | Prioritize mobile Analytics and Journal pages; accept simplified versions |
| 4 | **Chart behavior divergence** — two independent chart engines will behave differently | Medium | Medium | Create shared chart specification document; consider shared indicator calculation library |
| 5 | **Desktop security gap** — no app lock on desktop | Medium | High | Implement PIN/biometric lock on desktop |
| 6 | **Wine fragility (Linux)** — MT5 via Wine can break on system updates | Medium | High | Containerize Wine/MT5; provide automatic recovery; monitor health |
| 7 | **Notification duplication** — same event pushed via multiple channels to same device | Medium | Low | Implement deduplication logic in notification engine |
| 8 | **WhatsApp cost overrun** — high-frequency alerts generate per-message costs | Medium | Medium | Implement per-channel rate limits and daily cost caps |
| 9 | **WebSocket security** — desktop exposes localhost:9222 without auth | Medium | High | Implement token-based authentication for WebSocket connections |
| 10 | **Cross-platform session state** — pausing trading on one platform doesn't sync to others | Low | Medium | Implement shared session state via backend |

### 6.2 Critical Path Dependencies

```
                    ┌─────────────────────┐
                    │  Define Backend      │
                    │  Architecture        │ ◄── BLOCKS EVERYTHING
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
     ┌────────▼──────┐ ┌──────▼───────┐ ┌──────▼───────┐
     │ Desktop:      │ │ Mobile:      │ │ Web:         │
     │ Add app lock  │ │ Add Analytics│ │ Create       │
     │ Secure WS     │ │ Add Journal  │ │ architecture │
     │               │ │ Align tokens │ │ document     │
     └───────────────┘ └──────────────┘ └──────────────┘
```

---

## 7. Missing Web Architecture

### 7.1 Impact

The `architecture_ui_web.md` file was not found. This is a significant gap because:

1. **Web is the natural bridge** between desktop and mobile — it shares the browser runtime with desktop (React/TypeScript) and provides mobile-responsive access without app installation.
2. **Backend API definition** — a web architecture would force the team to define the REST/WebSocket API that both desktop and mobile should consume.
3. **Shared component library** — a web architecture could establish a shared React component library that the Tauri desktop app also uses, reducing duplication.

### 7.2 Recommendation

Create `architecture_ui_web.md` covering:
- Framework choice (React/Next.js recommended for code sharing with Tauri)
- Shared API contract with desktop and mobile
- Responsive breakpoints (desktop already defines 1024px+; web needs mobile breakpoints too)
- Authentication flow (browser-based — OAuth, session cookies, or token)
- Real-time data strategy (WebSocket or SSE)
- Feature parity target (which desktop features are web-accessible?)

---

## 8. Recommendations Summary

### Immediate (Before Implementation)

| # | Action | Owner | Priority |
|---|--------|-------|----------|
| 1 | **Define backend architecture** — local, cloud, or hybrid | Architecture Lead | 🔴 Critical |
| 2 | **Create shared design tokens file** (JSON/YAML) consumed by all platforms | Design Lead | 🔴 Critical |
| 3 | **Create `architecture_ui_web.md`** | Web Architect | 🔴 Critical |
| 4 | **Add desktop app lock** (PIN + biometric) | Desktop Architect | 🔴 Critical |
| 5 | **Define WebSocket protocol specification** | Backend Lead | 🟡 High |

### Short-Term (Phase 1-2)

| # | Action | Owner | Priority |
|---|--------|-------|----------|
| 6 | Align profit/loss color across platforms (`#22c55e` everywhere) | Design Lead | 🟡 High |
| 7 | Add Analytics and Journal to mobile | Mobile Architect | 🟡 High |
| 8 | Implement notification deduplication across channels | Channel Architect | 🟡 High |
| 9 | Add WebSocket authentication (token-based) | Backend Lead | 🟡 High |
| 10 | Implement per-channel rate limiting for notifications | Channel Architect | 🟡 Medium |

### Medium-Term (Phase 3+)

| # | Action | Owner | Priority |
|---|--------|-------|----------|
| 11 | Create shared chart specification document | Chart Lead | 🟡 Medium |
| 12 | Implement cross-platform session sync | Backend Lead | 🟡 Medium |
| 13 | Containerize Wine/MT5 for Linux reliability | Desktop Architect | 🟡 Medium |
| 14 | Add WhatsApp cost controls and monitoring | Channel Architect | 🟡 Medium |
| 15 | Evaluate Isar alternatives for mobile local DB | Mobile Architect | 🟢 Low |

---

## 9. Conclusion

The Alpha Stack architecture demonstrates strong individual platform designs — the desktop architecture is particularly thorough, and the channel architecture is well-engineered. However, the cross-platform story has significant gaps:

1. **No unified backend definition** — this is the #1 risk and blocks coherent multi-platform development.
2. **No web architecture** — the natural bridge platform is missing.
3. **Design token drift** — colors and spacing are already inconsistent between desktop and mobile.
4. **Feature parity gap** — mobile is missing Analytics and Journal.
5. **Desktop security gap** — no app lock on a financial application.

If these issues are addressed before implementation begins, the architecture has a strong foundation. The channel integration via OpenClaw is particularly well-designed and represents a genuine competitive advantage.

**Verdict: CONDITIONAL PASS** — address the 5 critical items above before proceeding to implementation.

---

*Review completed by Cross-Platform Architecture Review Agent — 2026-07-11*
