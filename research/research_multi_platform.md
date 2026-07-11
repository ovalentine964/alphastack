# Multi-Platform Architecture Research
## Institutional-Grade AI Trading System — Desktop + Web + Mobile

*Research Date: 2026-07-11*

---

## 1. Cross-Platform Framework Comparison

### Framework Overview (2025-2026 State)

| Framework | Language | Desktop | Web | Mobile | Code Sharing | Bundle Size | Native Feel |
|---|---|---|---|---|---|---|---|
| **Flutter** | Dart | ✅ Win/Mac/Linux | ✅ | ✅ iOS/Android | ~95% single codebase | Medium-Large | Good (custom render) |
| **React Native + React** | JS/TS | ❌ (need Electron/Tauri) | ✅ (React) | ✅ iOS/Android | ~60-70% (shared logic) | Medium | Excellent (native widgets) |
| **Tauri v2** | Rust + Web (JS/TS) | ✅ Win/Mac/Linux | ✅ (companion) | ✅ iOS/Android (beta) | ~70-80% | Tiny (uses OS webview) | Good |
| **Electron** | JS/TS | ✅ Win/Mac/Linux | ✅ (separate) | ❌ | ~50-60% | Huge (~150MB+) | Medium |
| **Kotlin Multiplatform** | Kotlin | ✅ | ⚠️ (WASM experimental) | ✅ iOS/Android | ~60-80% (logic only) | Small | Excellent (native UI) |
| **.NET MAUI** | C# | ✅ Win/Mac | ❌ | ✅ iOS/Android | ~70-80% | Medium | Good (MS ecosystem) |
| **Dioxus** | Rust | ✅ | ✅ | ✅ (experimental) | ~85% | Tiny | Early-stage |

### Deep-Dive: Top Candidates

#### Flutter (Recommended for Single-Codebase Maximum)
**Pros:**
- True single codebase for all 6 platforms (Android, iOS, Web, Windows, macOS, Linux)
- Dart compiles to native ARM code (mobile) and JS (web)
- Excellent charting libraries (fl_chart, syncfusion, TradingView lightweight charts via webview)
- Hot reload accelerates development
- Strong backing (Google), massive ecosystem (pub.dev)
- Used in production by financial apps (Nubank, Kotak Securities trading platform)
- Custom rendering engine (Skia/Impeller) = consistent UI everywhere

**Cons:**
- Web performance: not as fast as native JS frameworks for heavy DOM manipulation
- Desktop: relatively newer, some platform integrations require plugins
- Dart is less popular than JS/TS (smaller talent pool)
- Large binary sizes for desktop (~30-50MB)
- Web SEO is weak (SPA-only, no SSR without workarounds)
- Impeller renderer still maturing on desktop

**Best for:** Maximum code sharing, consistent UI, mobile-first with desktop/web expansion

#### Tauri v2 (Rust Backend + Web Frontend)
**Pros:**
- Tiny binaries (uses OS webview — ~2-5MB vs Electron's 150MB+)
- Rust backend = memory-safe, high-performance for financial computation
- Web frontend = use React/Vue/Svelte for UI
- v2 adds mobile support (iOS/Android) — still beta
- Security-first architecture (sandboxed IPC)
- Can share web frontend between Tauri desktop and browser deployment

**Cons:**
- Mobile support in v2 is still maturing (as of 2025)
- Rust learning curve for the team
- Webview differences across platforms can cause subtle bugs
- No single codebase for mobile — mobile uses same Rust core but webview behavior differs
- Smaller ecosystem than Flutter/React

**Best for:** Teams with Rust expertise wanting lightweight desktop + web, accepting mobile gaps

#### React Native + React (Web)
**Pros:**
- Largest ecosystem (npm), massive developer pool
- React Native for mobile, React for web — share component logic
- React Native for Windows/macOS exists (Microsoft maintains RN-Windows)
- Mature tooling, battle-tested at scale (Meta, Microsoft, Discord)
- Excellent for complex UIs with rich interaction patterns
- Can use react-native-web for code sharing between RN and React

**Cons:**
- NOT a single codebase — need separate desktop solution (Electron/Tauri)
- React Native for Windows/macOS has small community
- Mobile and web share ~60-70% logic but UI needs adaptation
- Three codebases effectively: RN (mobile), React (web), Electron/Tauri (desktop)
- More complex build pipeline

**Best for:** Teams already in the JS/TS ecosystem, prioritizing mobile UX quality

#### Kotlin Multiplatform (KMP)
**Pros:**
- Share business logic (networking, data, domain) across all platforms
- Native UI on each platform = best possible UX per platform
- JetBrains actively developing Compose Multiplatform for shared UI
- Excellent for Android-first teams expanding to iOS
- Strong typing, coroutines for async

**Cons:**
- Compose Multiplatform for iOS/web/desktop is still maturing
- Without Compose MP, you need separate UI per platform
- Web target (WASM) is experimental
- Smaller ecosystem than JS/Dart
- Desktop support via Compose is JVM-based (large runtime)

**Best for:** Android-heavy teams wanting shared logic with native UI per platform

### Code Sharing Matrix

| Layer | Flutter | RN+React | Tauri v2 | KMP |
|---|---|---|---|---|
| Business Logic | 100% shared | ~70% shared | ~80% shared (Rust core) | ~90% shared |
| Data Models | 100% shared | ~80% shared | ~80% shared | 100% shared |
| UI Components | ~95% shared | ~40% shared | ~60% shared (web only) | ~30% shared |
| Platform APIs | ~80% (plugins) | ~60% (bridges) | ~70% (plugins) | ~50% (expect/actual) |
| Networking | 100% shared | 100% shared | 100% shared | 100% shared |
| **Total Sharing** | **~95%** | **~60-65%** | **~70-75%** | **~70-75%** |

---

## 2. Architecture Patterns for Multi-Platform

### Pattern A: Shared Backend + Platform-Specific Frontends

```
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  Desktop App │  │   Web App   │  │  Mobile App  │
│  (Tauri/Elec)│  │  (React/Vue)│  │ (RN/Flutter) │
└──────┬───────┘  └──────┬──────┘  └──────┬───────┘
       │                 │                 │
       └────────────┬────┴─────────────────┘
                    │  REST / WebSocket / gRPC
              ┌─────▼──────┐
              │  API Server │
              │  (Backend)  │
              └─────────────┘
```

- **Pros:** Each platform optimized, team autonomy
- **Cons:** 3x frontend code, 3x maintenance, UI inconsistencies
- **Used by:** Bloomberg Terminal (separate apps per platform)

### Pattern B: Shared Business Logic + Platform UI (Recommended)

```
┌──────────────────────────────────────────────────┐
│              SHARED CORE (Rust/Dart/Kotlin)        │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │  Domain   │ │ Trading  │ │  Data Layer      │  │
│  │  Models   │ │ Strategy │ │  (API/WS/Cache)  │  │
│  └──────────┘ └──────────┘ └──────────────────┘  │
└──────────────────────┬───────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
┌──────────────┐ ┌──────────┐ ┌──────────────┐
│  Desktop UI  │ │  Web UI  │ │  Mobile UI   │
│  (Flutter/   │ │ (Flutter │ │  (Flutter/   │
│   Tauri)     │ │  Web)    │ │   Native)    │
└──────────────┘ └──────────┘ └──────────────┘
```

- **Pros:** Shared domain logic, platform-optimized UI
- **Cons:** Still some platform-specific code
- **Used by:** Spotify (shared audio engine, native UIs)

### Pattern C: Single Codebase (Flutter/NativeScript)

```
┌────────────────────────────────────────┐
│         SINGLE CODEBASE                │
│         (Flutter / Dart)               │
│                                        │
│  ┌──────────┐ ┌──────────────────┐    │
│  │  Shared  │ │  Platform Adapters│    │
│  │  Logic   │ │  (notifications,  │    │
│  │  + UI    │ │   file system,    │    │
│  └──────────┘ │   camera, etc.)   │    │
│               └──────────────────┘    │
└────────────┬──────┬──────────┬────────┘
             ▼      ▼          ▼
         Desktop   Web      Mobile
```

- **Pros:** Maximum code sharing (~95%), single team, single test suite
- **Cons:** Platform edge cases, web performance tradeoffs
- **Used by:** Google Ads app, Nubank, various fintech

### How Major Apps Do It

| App | Desktop | Web | Mobile | Approach |
|---|---|---|---|---|
| **TradingView** | Electron | React | React Native | Pattern A — separate frontends, shared backend |
| **Discord** | Electron | React | React Native (iOS/Android) | Pattern A — shared React logic, Electron desktop |
| **Notion** | Electron | React | React Native | Pattern A — React core, platform wrappers |
| **Spotify** | Native (CEF) | React | Native (iOS/Android) | Pattern B — shared C++ core, native UIs |
| **Slack** | Electron | React | Native (iOS/Android) | Pattern A — Electron desktop, native mobile |
| **Figma** | Electron | React | Native | Pattern A — C++ engine, React UI |
| **Linear** | Electron | React | React Native | Pattern A — React everywhere with wrappers |

**Key Insight:** Most successful multi-platform apps use **Pattern A** (separate frontends) because platform UX expectations differ significantly. However, they invest heavily in shared component libraries and design systems.

### Monorepo vs Polyrepo

| Aspect | Monorepo | Polyrepo |
|---|---|---|
| Code sharing | Easy (direct imports) | Hard (packages/SDKs) |
| CI/CD complexity | High (build matrix) | Medium (per-repo) |
| Team autonomy | Lower (shared tree) | Higher |
| Dependency management | Simpler | Complex versioning |
| **Recommendation** | ✅ For shared-core architecture | For fully separate teams |

**Recommendation for Trading System:** Monorepo with Turborepo/Nx:
```
alpha-stack/
├── packages/
│   ├── core/              # Shared domain logic, strategies, models
│   ├── api-client/        # Shared API/WebSocket client
│   ├── ui-components/     # Shared component library
│   └── utils/             # Shared utilities
├── apps/
│   ├── desktop/           # Tauri or Flutter desktop
│   ├── web/               # Flutter Web or React
│   └── mobile/            # Flutter mobile or RN
├── services/
│   ├── trading-engine/    # Rust/Python backend
│   └── data-pipeline/     # Market data ingestion
└── tools/
    └── scripts/           # Build, deploy, CI
```

---

## 3. State Synchronization

### Challenge: Keeping Desktop, Web, and Mobile in Sync

An institutional trading system has critical real-time state:
- Open positions & PnL
- Order book & market data
- Strategy signals & execution status
- Risk limits & alerts
- User settings & watchlists

### Architecture: Real-Time Sync Layer

```
┌──────────────────────────────────────────────────┐
│                 SYNC ENGINE                       │
│                                                   │
│  ┌─────────┐  ┌───────────┐  ┌───────────────┐  │
│  │  State   │  │  Conflict │  │   Offline     │  │
│  │  Store   │  │  Resolver │  │   Queue       │  │
│  │ (Redux/  │  │           │  │               │  │
│  │  Riverpod│  │           │  │               │  │
│  └────┬─────┘  └─────┬─────┘  └───────┬───────┘  │
│       │              │                │           │
│       └──────────────┴────────────────┘           │
│                      │                            │
│              ┌───────▼───────┐                    │
│              │  WebSocket    │                    │
│              │  Manager      │                    │
│              │  (auto-recon) │                    │
│              └───────────────┘                    │
└──────────────────────────────────────────────────┘
```

### WebSocket-Based Real-Time Sync

**Protocol Design:**
```json
// Server → Client: State delta
{
  "type": "state_delta",
  "channel": "portfolio",
  "patch": { "positions.BTC. unrealized_pnl": 1234.56 },
  "timestamp": 1689012345678,
  "seq": 42
}

// Client → Server: Action
{
  "type": "action",
  "action": "place_order",
  "payload": { "symbol": "BTC/USDT", "side": "buy", "qty": 0.1 },
  "idempotency_key": "uuid-xxx"
}
```

**Key Patterns:**
1. **Delta sync** — send only changes, not full state
2. **Sequence numbers** — detect missed messages, request re-sync
3. **Heartbeat** — detect stale connections (critical for trading)
4. **Channel subscriptions** — client subscribes to relevant data streams
5. **Idempotent operations** — safe to retry on reconnect

### Offline-First Architecture

**Layer Model:**
```
┌─────────────────────────────────────┐
│         UI Layer (Reactive)          │ ← Always reads from local
├─────────────────────────────────────┤
│     Local State Store (SQLite/       │ ← Single source of truth for UI
│     Hive/Isar + In-Memory Cache)     │
├─────────────────────────────────────┤
│     Sync Engine (CRDT / OT)         │ ← Handles conflict resolution
├─────────────────────────────────────┤
│     Network Layer (WebSocket + REST) │ ← When online
└─────────────────────────────────────┘
```

**Offline-First Rules for Trading:**
1. **Reads:** Always from local store (instant UI)
2. **Writes:** Write locally first, queue for sync
3. **Trading operations:** MUST require online connection (can't place orders offline)
4. **Configuration changes:** Sync when reconnected
5. **Market data:** Cache locally, show staleness indicator when offline

### Conflict Resolution Strategies

| Data Type | Strategy | Rationale |
|---|---|---|
| **Positions/PnL** | Server wins | Server is authoritative for financial data |
| **User settings** | Last-write-wins (LWW) | Conflicts rare, simple resolution |
| **Watchlists** | CRDT (Set merge) | Additive operations, merge naturally |
| **Strategy configs** | Server wins + version check | Prevent conflicting strategy states |
| **Chart layouts** | LWW with user prompt | User can choose on conflict |

**For critical trading state:** Use **server-authoritative** model. Clients display server state; only UI preferences use client-side conflict resolution.

### Recommended Sync Libraries by Framework

| Framework | State Management | Sync Library |
|---|---|---|
| **Flutter** | Riverpod + drift (SQLite) | Custom WebSocket + drift streams |
| **React/RN** | Zustand/Jotai + TanStack Query | Socket.io + react-query invalidation |
| **Tauri + React** | Zustand + SQLite (via Rust) | Custom Rust WebSocket + React context |
| **KMP** | KMM StateFlow + SQLDelight | Ktor WebSocket + SQLDelight flows |

---

## 4. Shared vs Platform-Specific Components

### What CAN Be Shared (Cross-Platform)

| Component | Sharing Strategy | Notes |
|---|---|---|
| **Domain Models** | 100% shared | Positions, orders, strategies, signals |
| **API Client** | 100% shared | REST + WebSocket protocols |
| **Trading Logic** | 100% shared | Strategy evaluation, risk calculations |
| **Chart Data Processing** | 100% shared | OHLCV aggregation, indicator computation |
| **Auth/Session** | 100% shared | Token management, refresh logic |
| **Notification Logic** | ~80% shared | Event → notification mapping |
| **Configuration** | 100% shared | Settings schema, defaults |
| **Utility Functions** | 100% shared | Date/time, math, formatting |

### What MUST Be Platform-Specific

| Component | Why Platform-Specific | Implementation |
|---|---|---|
| **Push Notifications** | Different APIs (FCM/APNs/Web Push) | Platform adapter pattern |
| **File System** | Different sandboxing per OS | Platform plugin |
| **Biometric Auth** | Face ID / Fingerprint / Windows Hello | Platform plugin |
| **System Tray** | Desktop only | Desktop-specific code |
| **Deep Linking** | Different URL schemes per platform | Platform handler |
| **Chart Rendering** | Canvas (web) vs Skia (native) vs WebView | See below |
| **Keyboard Shortcuts** | Different conventions per OS | Platform keymap |
| **Window Management** | Desktop-only (multi-window, always-on-top) | Desktop-specific |

### Chart Rendering: The Hard Problem

Charts are the most complex shared component in a trading system.

**Option 1: WebView Charts (TradingView Lightweight)**
```
┌─────────────────────────────────┐
│  TradingView Lightweight Charts │ ← Runs in WebView on all platforms
│  (JavaScript/Canvas)            │
└─────────────────────────────────┘
```
- ✅ Identical rendering everywhere
- ✅ TradingView's proven charting engine
- ❌ Performance overhead from WebView bridge
- ❌ Touch interactions differ from native

**Option 2: Native Charting per Platform**
- ✅ Best performance and native feel
- ❌ 3x development effort
- ❌ Visual inconsistencies across platforms

**Option 3: Flutter Custom Painting (Recommended for Flutter)**
```
┌─────────────────────────────────┐
│  CustomPaint / Canvas API       │ ← Flutter's rendering engine
│  (Dart → Skia/Impeller)        │
└─────────────────────────────────┘
```
- ✅ Single implementation, renders natively everywhere
- ✅ Full control over performance optimization
- ✅ Can match TradingView quality
- ❌ Must build charting engine from scratch or adapt

**Option 4: Hybrid Approach (Recommended for React/TAURI)**
```
Desktop: TradingView Charting Library (full) or custom Canvas
Web:     TradingView Lightweight Charts
Mobile:  TradingView Lightweight Charts in WebView
```

### Notification Handling Matrix

| Platform | Push Technology | Badge Support | Sound | Rich Media |
|---|---|---|---|---|
| **Android** | FCM | ✅ | ✅ | ✅ |
| **iOS** | APNs | ✅ | ✅ | ✅ |
| **Web** | Web Push API | ❌ | Limited | Limited |
| **macOS** | APNs / NSUserNotification | ✅ | ✅ | ✅ |
| **Windows** | WNS / Toast | ✅ | ✅ | ✅ |
| **Linux** | libnotify / D-Bus | ❌ | ✅ | Limited |

**Strategy:** Abstract notification interface in shared layer, platform implementations handle delivery:

```dart
// Shared interface
abstract class NotificationService {
  Future<void> showTradeAlert(TradeAlert alert);
  Future<void> showRiskWarning(RiskWarning warning);
  Future<void> showPriceAlert(PriceAlert alert);
}

// Platform implementations
class AndroidNotificationService extends NotificationService { ... }
class IOSNotificationService extends NotificationService { ... }
class WebNotificationService extends NotificationService { ... }
```

---

## 5. Build & Deployment Pipeline

### CI/CD Matrix for Multi-Platform

```
┌─────────────────────────────────────────────────────┐
│                    CI/CD Pipeline                     │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │  Shared   │  │  Lint +  │  │  Unit + Integ    │  │
│  │  Core     │→ │  Type    │→ │  Tests           │  │
│  │  Build    │  │  Check   │  │                  │  │
│  └──────────┘  └──────────┘  └────────┬─────────┘  │
│                                        │             │
│        ┌───────────────┬───────────────┼──────┐     │
│        ▼               ▼               ▼      ▼     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───┐  │
│  │  Desktop  │  │   Web    │  │ Android  │  │iOS│  │
│  │  Build    │  │  Build   │  │  Build   │  │Bld│  │
│  │ Win/Mac/  │  │ SPA +    │  │  AAB +   │  │IPA│  │
│  │ Linux     │  │ Deploy   │  │  APK     │  │   │  │
│  └──────────┘  └──────────┘  └──────────┘  └───┘  │
│        │               │               │      │     │
│        ▼               ▼               ▼      ▼     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───┐  │
│  │  Auto-   │  │  CDN +   │  │  Play    │  │App│  │
│  │  Update  │  │  Deploy  │  │  Store   │  │Str│  │
│  │  Server  │  │          │  │          │  │   │  │
│  └──────────┘  └──────────┘  └──────────┘  └───┘  │
└─────────────────────────────────────────────────────┘
```

### Platform-Specific Build Configurations

| Platform | Build Tool | Output | Signing | Distribution |
|---|---|---|---|---|
| **Windows** | Tauri/MSIX or Flutter | `.msix` / `.exe` | Code signing cert | Auto-update server / Winget |
| **macOS** | Tauri/DMG or Flutter | `.dmg` / `.app` | Apple Developer ID | Auto-update / Homebrew |
| **Linux** | Tauri/AppImage or Flutter | `.AppImage` / `.deb` | GPG (optional) | AppImage / Snap / Flatpak |
| **Web** | Vite / Flutter build | Static SPA | N/A | CDN (Vercel/Cloudflare) |
| **Android** | Gradle | `.aab` / `.apk` | Keystore | Play Store / Direct |
| **iOS** | Xcode | `.ipa` | Apple Distribution Cert | App Store / TestFlight |

### Auto-Update Mechanisms

| Platform | Mechanism | Library/Service |
|---|---|---|
| **Tauri** | Built-in updater | `tauri-plugin-updater` |
| **Electron** | electron-updater | `electron-updater` (S3/GitHub) |
| **Flutter Desktop** | Custom | `auto_updater` package or custom |
| **Android** | In-app updates | Google Play Core API |
| **iOS** | App Store | Standard review process |
| **Web** | Always latest | CDN deployment, service worker cache |

### Recommended CI/CD Tools

- **GitHub Actions** — Best for monorepo, matrix builds
- **Turborepo** — Monorepo build orchestration, caching
- **Fastlane** — iOS/Android signing and deployment
- **Tauri Action** — GitHub Action for Tauri desktop builds
- **Flutter Action** — GitHub Action for Flutter builds

---

## 6. Recommended Architecture for Alpha Stack

### Decision Matrix: Scoring Each Approach

| Criteria (Weight) | Flutter | RN+React+Tauri | Tauri+React | KMP+Compose |
|---|---|---|---|---|
| Code sharing (25%) | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Trading UI quality (20%) | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Performance (15%) | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Ecosystem/maturity (15%) | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| Development speed (10%) | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| Web experience (10%) | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| Desktop experience (5%) | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Weighted Score** | **4.10** | **3.90** | **4.05** | **3.55** |

### 🏆 Recommended Architecture: Flutter + Rust Backend

```
┌──────────────────────────────────────────────────────────────┐
│                    ALPHA STACK — MULTI-PLATFORM               │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                 SHARED CORE (Rust)                       │  │
│  │  ┌───────────┐ ┌────────────┐ ┌──────────────────────┐ │  │
│  │  │  Trading   │ │   Risk     │ │  Market Data         │ │  │
│  │  │  Engine    │ │   Engine   │ │  Pipeline            │ │  │
│  │  │  (strats,  │ │  (limits,  │ │  (WebSocket ingest,  │ │  │
│  │  │  signals)  │ │  margin)   │ │  normalization)      │ │  │
│  │  └───────────┘ └────────────┘ └──────────────────────┘ │  │
│  │  ┌───────────┐ ┌────────────┐ ┌──────────────────────┐ │  │
│  │  │  Order    │ │  Portfolio  │ │  Notification        │ │  │
│  │  │  Manager  │ │  Tracker   │ │  Engine              │ │  │
│  │  └───────────┘ └────────────┘ └──────────────────────┘ │  │
│  └────────────────────────┬───────────────────────────────┘  │
│                           │ gRPC / REST / WebSocket           │
│  ┌────────────────────────┴───────────────────────────────┐  │
│  │              FLUTTER APPLICATION LAYER                   │  │
│  │                                                          │  │
│  │  ┌─────────────────────────────────────────────────┐   │  │
│  │  │            SHARED FLUTTER CODE (~95%)             │   │  │
│  │  │                                                   │   │  │
│  │  │  ┌──────────┐ ┌──────────┐ ┌────────────────┐   │   │  │
│  │  │  │  Domain  │ │  State   │ │  Shared UI     │   │   │  │
│  │  │  │  Models  │ │  (River- │ │  Components    │   │   │  │
│  │  │  │          │ │  pod)    │ │  (charts,      │   │   │  │
│  │  │  │          │ │          │ │  forms, cards) │   │   │  │
│  │  │  └──────────┘ └──────────┘ └────────────────┘   │   │  │
│  │  │  ┌──────────┐ ┌──────────┐ ┌────────────────┐   │   │  │
│  │  │  │  API     │ │  Sync    │ │  Business      │   │   │  │
│  │  │  │  Client  │ │  Engine  │ │  Logic         │   │   │  │
│  │  │  └──────────┘ └──────────┘ └────────────────┘   │   │  │
│  │  └─────────────────────────────────────────────────┘   │  │
│  │                                                          │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────┐  │  │
│  │  │ Platform │  │ Platform │  │ Platform │  │  Web │  │  │
│  │  │ Desktop  │  │ Android  │  │  iOS     │  │ SPA  │  │  │
│  │  │ Adapters │  │ Adapters │  │ Adapters │  │Config│  │  │
│  │  │ (~3%)    │  │ (~2%)    │  │ (~2%)    │  │(~1%) │  │  │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### Why Flutter + Rust Backend?

1. **Single codebase for all 6 platforms** — Flutter handles Android, iOS, Web, Windows, macOS, Linux from one Dart codebase
2. **Rust backend** — Memory-safe, high-performance for trading engine, strategy execution, and risk calculations. Compiles to native. Excellent WebSocket performance.
3. **~95% code sharing** — Only platform adapters (~5%) differ
4. **Trading-specific:** Flutter's CustomPaint enables building professional-grade charts (candlesticks, depth charts, indicators) in a single implementation
5. **Faster time-to-market** — One team, one codebase, one test suite
6. **Proven in fintech** — Nubank (100M+ users), Kotak Securities trading app, Google Pay

### What to Share vs What to Keep Separate

| SHARED (in Flutter/Dart) | SEPARATE (Platform-Specific) |
|---|---|
| All UI screens and components | Push notification delivery (FCM/APNs/Web Push) |
| Chart rendering (CustomPaint) | System tray integration (desktop) |
| State management (Riverpod) | Biometric authentication |
| API/WebSocket client | File picker / document export |
| Navigation / routing | Deep linking configuration |
| Form validation | Window management (desktop) |
| Theme / design system | Auto-update mechanism |
| Business logic | Platform-specific gestures |
| Local storage (drift/SQLite) | Keyboard shortcuts per OS |

### Alternative Recommendation: Tauri + React (If Team Has Rust Expertise)

If the team has strong Rust skills and wants the lightest possible desktop app:

```
┌──────────────────────────────────────────────────────┐
│  SHARED RUST CORE (trading engine, data, strategies)  │
│  Compiled as:                                          │
│  • Native library for Tauri desktop                   │
│  • WASM module for web                                │
│  • Native library for mobile (via FFI)                │
├──────────────────────────────────────────────────────┤
│  REACT FRONTEND (shared across web + Tauri)           │
│  • React + TypeScript                                 │
│  • TradingView Lightweight Charts                     │
│  • Zustand for state                                  │
│  • Same components in browser and desktop webview     │
├──────────────────────────────────────────────────────┤
│  REACT NATIVE (mobile)                                │
│  • Shares ~60% logic with React web                   │
│  • Native navigation and gestures                     │
│  • react-native-web bridges some components           │
└──────────────────────────────────────────────────────┘
```

- ✅ Tiny desktop binaries (~3MB)
- ✅ Best-in-class web experience (native React)
- ✅ Rust performance for trading engine
- ❌ Three frontends to maintain (Tauri/React, React Web, RN Mobile)
- ❌ Mobile via Tauri v2 still beta
- ❌ ~65% total code sharing vs Flutter's ~95%

### Development Timeline Estimates

#### Flutter + Rust Approach (Recommended)

| Phase | Duration | Deliverable |
|---|---|---|
| **Phase 1:** Core + Web | 8-10 weeks | Trading engine (Rust) + Flutter Web SPA |
| **Phase 2:** Desktop | 3-4 weeks | Flutter Desktop builds (Win/Mac/Linux) |
| **Phase 3:** Mobile | 4-5 weeks | Flutter Mobile (Android/iOS) |
| **Phase 4:** Polish + Platform | 3-4 weeks | Notifications, auto-update, app store prep |
| **Total** | **18-23 weeks** | Full multi-platform release |

#### Tauri + React + RN Approach

| Phase | Duration | Deliverable |
|---|---|---|
| **Phase 1:** Core + Web | 8-10 weeks | Trading engine (Rust) + React Web |
| **Phase 2:** Desktop | 4-5 weeks | Tauri desktop wrapper |
| **Phase 3:** Mobile | 6-8 weeks | React Native mobile app |
| **Phase 4:** Polish + Platform | 3-4 weeks | Platform integrations |
| **Total** | **21-27 weeks** | Full multi-platform release |

### Technology Stack Summary

```
┌─────────────────────────────────────────────────┐
│              ALPHA STACK — TECH STACK            │
│                                                  │
│  Backend:    Rust (trading engine, data, risk)   │
│  Frontend:   Flutter / Dart (all platforms)      │
│  State:      Riverpod + drift (SQLite)           │
│  Charts:     Custom Flutter Paint engine         │
│  API:        gRPC (internal) + REST (external)   │
│  Real-time:  WebSocket (market data, signals)    │
│  Sync:       Custom delta-sync over WebSocket    │
│  Storage:    SQLite (local) + Redis (server)     │
│  CI/CD:      GitHub Actions + Turborepo          │
│  Desktop:    Flutter Desktop + auto_updater      │
│  Web:        Flutter Web (CanvasKit renderer)    │
│  Mobile:     Flutter (Android + iOS)             │
└─────────────────────────────────────────────────┘
```

### Risk Mitigation

| Risk | Mitigation |
|---|---|
| Flutter Web performance | Use CanvasKit (Skia) renderer, not HTML; optimize with `RepaintBoundary` |
| Flutter Desktop maturity | Desktop is GA since Flutter 3.0; use stable channel, test on all OS |
| Dart talent shortage | Dart is easy to learn for JS/TS devs; 2-3 week ramp-up |
| Chart rendering quality | Build custom chart engine using CustomPaint; reference TradingView's API design |
| Platform-specific bugs | Maintain platform-specific integration tests in CI matrix |
| Rust backend complexity | Use `tokio` for async, `tonic` for gRPC; start simple, iterate |

---

## Appendix: Quick Decision Guide

```
START
  │
  ├── Want MAXIMUM code sharing (95%+), single team?
  │   └── → Flutter + Rust Backend ✅
  │
  ├── Want BEST web experience + tiny desktop?
  │   └── → Tauri + React + RN (accept 3 frontends)
  │
  ├── Team is JS/TS only, no Rust/Dart?
  │   └── → Electron + React + React Native
  │
  ├── Want NATIVE UI on each platform?
  │   └── → Kotlin Multiplatform + Compose (Android-first)
  │
  └── Microsoft/.NET ecosystem?
      └── → .NET MAUI + Blazor WebAssembly
```

**Bottom line:** For an institutional-grade AI trading system that must work across Desktop (Linux, Windows, macOS), Web, and Mobile (Android, iOS), **Flutter + Rust backend** provides the optimal balance of code sharing (~95%), development speed (single codebase), performance (Rust for computation, Flutter for UI), and platform coverage (all 6 platforms from one codebase).
