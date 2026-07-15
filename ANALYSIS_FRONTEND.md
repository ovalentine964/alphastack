# AlphaStack Frontend Apps — Deep Analysis

> Generated: 2026-07-15 | Covers `apps/mobile/`, `apps/desktop/`, `apps/web/`

---

## Table of Contents

1. [Mobile App (Flutter)](#1-mobile-app-flutter)
2. [Desktop App (Tauri + React)](#2-desktop-app-tauri--react)
3. [Web App (Next.js)](#3-web-app-nextjs)
4. [Cross-App Comparison](#4-cross-app-comparison)
5. [Backend API Contract (Inferred)](#5-backend-api-contract-inferred)

---

## 1. Mobile App (Flutter)

### 1.1 File Structure

```
apps/mobile/
├── pubspec.yaml
├── assets/
│   ├── icons/.gitkeep          (empty placeholder)
│   └── images/.gitkeep         (empty placeholder)
└── lib/
    ├── main.dart               — Entry point
    ├── app.dart                — App shell, theme, bottom nav
    ├── models/
    │   ├── signal.dart         — Signal model + enums
    │   ├── signal.g.dart       — Generated JSON serialization
    │   ├── trade.dart          — Trade + Position models + enums
    │   └── trade.g.dart        — Generated JSON serialization
    ├── screens/
    │   ├── dashboard_screen.dart
    │   ├── trades_screen.dart
    │   ├── signals_screen.dart
    │   ├── analytics_screen.dart
    │   └── settings_screen.dart
    ├── services/
    │   ├── api_service.dart    — REST API client
    │   └── websocket_service.dart — WebSocket client
    └── widgets/
        ├── pnl_chart.dart      — Line chart for cumulative P&L
        ├── portfolio_card.dart  — Portfolio summary card
        ├── position_tile.dart   — Individual position row
        └── signal_card.dart     — Signal display card
```

### 1.2 Tech Stack & Dependencies

| Dependency | Purpose |
|---|---|
| `flutter_riverpod ^2.4.9` | State management (providers) |
| `http ^1.2.0` | REST API calls |
| `web_socket_channel ^2.4.0` | WebSocket connectivity |
| `fl_chart ^0.66.0` | Charts (P&L line, win-rate bar) |
| `local_auth ^2.1.8` | Biometric authentication |
| `flutter_secure_storage ^9.0.0` | Secure key/credential storage |
| `firebase_messaging ^14.7.10` | Push notifications |
| `intl ^0.19.0` | Date/number formatting |
| `google_fonts ^6.1.0` | Inter font family |
| `flutter_svg ^2.0.9` | SVG rendering |
| `cached_network_image ^3.3.1` | Image caching |
| `shimmer ^3.0.0` | Loading skeleton effects |
| `pull_to_refresh ^2.0.0` | Pull-to-refresh gesture |
| `json_annotation / json_serializable` | Type-safe JSON (de)serialization |

**Dart SDK**: `>=3.2.0 <4.0.0`

### 1.3 Screens & Navigation

The app uses a `BottomNavigationBar` with `IndexedStack` for 5 tabs:

| Tab | Icon | Screen | Content |
|---|---|---|---|
| Dashboard | `dashboard_rounded` | `DashboardScreen` | Portfolio summary card, active positions list, recent signals |
| Trades | `candlestick_chart_rounded` | `TradesScreen` | Trade history with filters (all/open/closed/profitable/losing), stats bar |
| Signals | `signal_cellular_alt_rounded` | `SignalsScreen` | Active signals with confluence gauge, filters (all/buy/sell/high-confluence) |
| Analytics | `analytics_rounded` | `AnalyticsScreen` | P&L chart, metrics grid (win rate, Sharpe, drawdown), strategy breakdown, risk analysis |
| Settings | `settings_rounded` | `SettingsScreen` | Connection, security, notifications, trading, appearance, about sections |

### 1.4 Authentication Flow

**There is NO login screen.** The authentication model is implicit:

1. **`ApiService.authenticate()`** exists and accepts `apiKey` + `apiSecret` via POST to `/api/v1/auth/login`
2. On success, it stores a JWT `token` in `FlutterSecureStorage` under key `auth_token`
3. All subsequent API requests attach `Authorization: Bearer <token>` header
4. The **Settings screen** has an "API Keys" tile (manages exchange API keys) and an "API Endpoint" tile that opens a dialog to configure the base URL
5. Biometric auth (`local_auth` package) is wired as a toggle in Settings but **no actual implementation exists** — it's just a `StateProvider<bool>` toggle
6. "Disconnect" button in Settings shows a confirmation dialog but **doesn't actually clear tokens or navigate**

**Assessment**: Auth scaffolding exists but no login flow is implemented. The app would need to either:
- Auto-authenticate with stored credentials on launch
- Show a login screen before reaching MainNavigation
- Currently it will just hit mock data and never call the real API

### 1.5 Settings Screen — API Keys

The Settings screen has these connection/security sections:

- **API Endpoint**: Shows `https://api.alphastack.io`, opens dialog to edit (but doesn't persist via `ApiService.setBaseUrl()`)
- **WebSocket Status**: Shows "Connected" with green dot (hardcoded, not live)
- **Auto Refresh**: Toggle (state only, not wired)
- **Biometric Auth**: Toggle (state only, not wired to `local_auth`)
- **Change PIN**: Tile exists, no implementation
- **API Keys**: Tile says "Manage exchange API keys" — **no actual screen/dialog exists**

### 1.6 API Connection (ApiService)

The `ApiService` is a **singleton** with proper architecture:

- **Base URL**: Defaults to `http://localhost:8000/api/v1`, stored in secure storage
- **Auth**: Bearer token stored in secure storage, auto-attached to headers
- **Endpoints implemented**:
  - `GET portfolio/summary` → portfolio data
  - `GET portfolio/positions` → active positions
  - `GET trades` (paginated) → trade list
  - `GET trades/:id` → single trade
  - `GET signals/active` → active signals
  - `GET signals` (paginated) → signal list
  - `GET analytics/performance` → performance metrics
  - `GET analytics/pnl-history` → P&L history
  - `GET analytics/risk` → risk metrics
  - `POST auth/login` → authenticate with API key/secret
  - `GET health` → health check (hits `$baseUrl/../health`)
- **Error handling**: `ApiException` class with status code parsing
- **Timeout**: 30 seconds on all requests

### 1.7 WebSocket (WebSocketService)

Fully implemented singleton service:

- **URL**: Defaults to `ws://localhost:8000/ws`, stored in secure storage
- **Auth**: Appends `?token=<auth_token>` to WS URL
- **Heartbeat**: Sends `{"type":"ping"}` every 30 seconds
- **Reconnect**: Exponential backoff (2s × 2^attempt), max 10 attempts
- **Message routing** by type:
  - `position_update/opened/closed` → position stream
  - `signal_new/update/expired` → signal stream
  - `trade_executed/updated` → trade stream
  - `portfolio_update` → portfolio stream
  - `pong` → ignored (heartbeat response)
- **Streams exposed**: `stateStream`, `messageStream`, `positionUpdates`, `signalUpdates`, `tradeUpdates`, `portfolioUpdates`

### 1.8 State Management

**Riverpod** with `FutureProvider` and `StateProvider`:

- `portfolioProvider` — `FutureProvider<Map>` (mock data)
- `positionsProvider` — `FutureProvider<List<Position>>` (mock data)
- `recentSignalsProvider` — `FutureProvider<List<Signal>>` (mock data)
- `tradesProvider` — `FutureProvider<List<Trade>>` (mock data)
- `signalsListProvider` — `FutureProvider<List<Signal>>` (mock data)
- `performanceProvider` — `FutureProvider<Map>` (mock data)
- `pnlHistoryProvider` — `FutureProvider<List<PnlDataPoint>>` (mock data)
- `winRateHistoryProvider` — `FutureProvider<List<WinRatePoint>>` (mock data)
- `signalFilterProvider` — `StateProvider<SignalFilter>`
- `tradeFilterProvider` — `StateProvider<TradeFilter>`
- `analyticsPeriodProvider` — `StateProvider<String>`
- `biometricEnabledProvider` — `StateProvider<bool>`
- `notificationsEnabledProvider` — `StateProvider<bool>`
- `darkModeProvider` — `StateProvider<bool>`
- `autoRefreshProvider` — `StateProvider<bool>`

**Critical issue**: All data providers return **hardcoded mock data** with artificial delays. They do NOT call `ApiService` or `WebSocketService`. The services exist but are completely disconnected from the UI.

### 1.9 Implementation Status

| Feature | Status | Notes |
|---|---|---|
| App shell & navigation | ✅ Complete | 5-tab bottom nav, dark theme, Google Fonts |
| Theme system | ✅ Complete | GitHub-dark palette, consistent design tokens |
| Data models | ✅ Complete | Signal, Trade, Position with JSON serialization |
| REST API client | ✅ Complete | Full endpoint coverage, auth, error handling |
| WebSocket client | ✅ Complete | Reconnect, heartbeat, message routing |
| Dashboard screen | ⚠️ Mock data | UI complete, uses hardcoded data |
| Trades screen | ⚠️ Mock data | UI complete with filters, uses hardcoded data |
| Signals screen | ⚠️ Mock data | UI complete with filters/confluence gauge, uses hardcoded data |
| Analytics screen | ⚠️ Mock data | UI complete with charts/metrics, uses hardcoded data |
| Settings screen | ⚠️ Scaffold | UI complete, toggles are state-only, no persistence |
| Authentication | ❌ Not wired | ApiService.auth exists, no login screen or flow |
| Push notifications | ❌ Not wired | Firebase Messaging in deps, no implementation |
| Biometric auth | ❌ Not wired | local_auth in deps, toggle exists but no logic |
| Real-time updates | ❌ Not wired | WebSocket service exists but not connected to UI |

---

## 2. Desktop App (Tauri + React)

### 2.1 File Structure

```
apps/desktop/
├── package.json
├── index.html
├── vite.config.ts
├── tsconfig.json
├── tsconfig.node.json
├── tailwind.config.js
├── postcss.config.js
├── src/
│   ├── main.tsx              — React entry point
│   ├── App.tsx               — Routes, sidebar, layout
│   ├── components/
│   │   ├── Dashboard.tsx     — Market tickers, stat cards, actions
│   │   └── SystemTray.tsx    — Connection status, quick actions
│   ├── lib/
│   │   ├── store.ts          — Zustand store (app metadata)
│   │   └── tauri-bridge.ts   — Tauri IPC wrapper
│   └── styles/
│       └── globals.css       — Tailwind base, scrollbar, drag region
└── src-tauri/
    ├── Cargo.toml
    ├── tauri.conf.json
    ├── build.rs
    └── src/
        ├── main.rs           — Tauri app entry, system tray setup
        └── commands.rs       — Rust IPC commands
```

### 2.2 Tech Stack & Dependencies

**Frontend (React/Vite)**:

| Dependency | Purpose |
|---|---|
| `react ^18.3.1` / `react-dom` | UI framework |
| `react-router-dom ^6.26.0` | Client-side routing (HashRouter) |
| `zustand ^4.5.4` | State management |
| `@tauri-apps/api ^1.6.0` | Tauri IPC bridge |
| `@tauri-apps/plugin-notification` | Native notifications |
| `@tauri-apps/plugin-shell` | Open external URLs |
| `@tauri-apps/plugin-store` | Persistent key-value storage |
| `@tauri-apps/plugin-updater` | Auto-update (not used yet) |
| `clsx ^2.1.1` | Conditional classnames |
| `lucide-react ^0.441.0` | Icons (imported but not used in current code) |
| `tailwindcss ^3.4.10` | Utility CSS |

**Backend (Rust/Tauri)**:

| Dependency | Purpose |
|---|---|
| `tauri ^1` | Desktop framework (system tray, notifications, window management) |
| `serde / serde_json` | JSON serialization |
| `tokio ^1` (full) | Async runtime |
| `chrono ^0.4` | Date/time (in deps, not used in current commands) |
| `uuid ^1` | UUID generation (in deps, not used in current commands) |

### 2.3 Screens & Routes

| Route | Component | Status |
|---|---|---|
| `/` → redirects to `/dashboard` | — | — |
| `/dashboard` | `Dashboard` | ⚠️ Mock data (US stock tickers) |
| `/portfolio` | `Placeholder` | ❌ "Coming soon" |
| `/markets` | `Placeholder` | ❌ "Coming soon" |
| `/strategies` | `Placeholder` | ❌ "Coming soon" |
| `/alerts` | `Placeholder` | ❌ "Coming soon" |
| `/settings` | `Placeholder` | ❌ "Coming soon" |

Sidebar navigation has 6 items with emoji icons. Only Dashboard renders actual content.

### 2.4 Backend API Connection

**There is NO API client.** The desktop app:

- Has no HTTP client for the AlphaStack backend
- Has no WebSocket connection
- The `Dashboard` uses hardcoded mock US stock tickers (AAPL, MSFT, etc.) — **not crypto data**
- No data fetching from the trading engine whatsoever

### 2.5 WebSocket Usage

**None.** No WebSocket client exists in the desktop app.

### 2.6 State Management (Zustand)

Minimal store in `store.ts`:

```typescript
interface AppState {
  appVersion: string | null;
  systemInfo: SystemInfo | null;  // { os, arch, desktop }
  sidebarCollapsed: boolean;
  // setters...
}
```

Only stores app metadata. No trading data state.

### 2.7 Tauri Bridge

`tauri-bridge.ts` wraps native capabilities:

- `sendNotification(title, body)` — OS-level notification
- `toggleWindow()` — Show/hide main window
- `getAppVersion()` — From Tauri config
- `getSystemInfo()` — OS, arch, desktop environment
- `setSetting/getSetting/deleteSetting` — Persistent KV store (`@tauri-apps/plugin-store`)
- `openUrl(url)` — Open in default browser
- `minimizeWindow()` / `toggleFullscreen()` / `closeToTray()` — Window management

### 2.8 System Tray (Rust)

Fully implemented system tray with context menu:

- **Show AlphaStack** / **Hide** — Toggle window visibility
- **Dashboard** / **Portfolio** — Navigate via `window.eval()` hash change
- **Settings** — Navigate to settings
- **Quit** — `process::exit(0)`
- Left-click shows/focuses the window

### 2.9 Tauri Configuration

- **Window**: 1400×900, min 960×640, centered, decorations on
- **Bundle**: `com.alphastack.desktop`, category "Finance"
- **CSP**: Connects to `https://api.alphastack.dev` and `wss://ws.alphastack.dev`
- **System tray**: Template icon, menu on right-click

### 2.10 Implementation Status

| Feature | Status | Notes |
|---|---|---|
| App shell & sidebar | ✅ Complete | Hash routing, dark theme |
| System tray | ✅ Complete | Full menu, window toggle |
| Native notifications | ✅ Complete | Via Tauri plugin |
| Window management | ✅ Complete | Minimize, fullscreen, close-to-tray |
| Persistent settings | ✅ Complete | Via Tauri store plugin |
| Dashboard | ⚠️ Mock data | US stocks, not crypto |
| Portfolio | ❌ Placeholder | "Coming soon" |
| Markets | ❌ Placeholder | "Coming soon" |
| Strategies | ❌ Placeholder | "Coming soon" |
| Alerts | ❌ Placeholder | "Coming soon" |
| Settings | ❌ Placeholder | "Coming soon" |
| API client | ❌ Missing | No HTTP client for backend |
| WebSocket | ❌ Missing | No real-time data |
| Trading features | ❌ Missing | No signal/trade display |

---

## 3. Web App (Next.js)

### 3.1 File Structure

```
apps/web/
├── package.json
├── next.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── postcss.config.mjs
└── src/
    ├── app/
    │   ├── globals.css
    │   ├── layout.tsx         — Root layout with Sidebar
    │   ├── page.tsx           — Dashboard page
    │   ├── trades/page.tsx    — Trade history page
    │   ├── signals/page.tsx   — Signals page
    │   ├── analytics/page.tsx — Analytics page
    │   └── settings/page.tsx  — Settings page
    ├── components/
    │   ├── Sidebar.tsx        — Navigation sidebar
    │   ├── Dashboard/
    │   │   ├── PortfolioCard.tsx — Portfolio summary stats
    │   │   └── PositionsTable.tsx — Open positions table
    │   └── Charts/
    │       └── TradingChart.tsx — Candlestick chart (lightweight-charts)
    ├── lib/
    │   ├── api.ts             — REST API client
    │   └── websocket.ts       — WebSocket client
    └── stores/
        ├── signalStore.ts     — Zustand store for signals
        └── tradeStore.ts      — Zustand store for trades/positions/portfolio
```

### 3.2 Tech Stack & Dependencies

| Dependency | Purpose |
|---|---|
| `next ^15.1.0` | React framework (App Router) |
| `react ^19.0.0` / `react-dom` | UI (React 19!) |
| `zustand ^5.0.0` | State management |
| `lightweight-charts ^4.2.0` | Professional candlestick charting |
| `clsx ^2.1.1` | Conditional classnames |
| `lucide-react ^0.460.0` | Icon library |
| `tailwindcss ^3.4.0` | Utility CSS |
| `@tailwindcss/forms ^0.5.9` | Form styling |

### 3.3 Screens & Pages

| Route | Page | Content |
|---|---|---|
| `/` | `DashboardPage` | Portfolio card, trading chart, recent signals, positions table, recent trades |
| `/trades` | `TradesPage` | Full trade history with side/symbol filters, stats (P&L, win rate) |
| `/signals` | `SignalsPage` | Signal cards with confluence badges, status/strategy filters |
| `/analytics` | `AnalyticsPage` | Performance metrics grid, equity curve chart, period selector |
| `/settings` | `SettingsPage` | Broker config (API keys), risk parameters, notification settings |

### 3.4 API Connection

**`lib/api.ts`** — Clean typed REST client:

- Base path: `/api` (proxied via Next.js rewrites to `http://localhost:8000`)
- Endpoints:
  - `GET /portfolio` — Portfolio summary
  - `GET /positions` — Open positions
  - `GET /trades?limit=` — Trade history
  - `GET /trades/:id` — Single trade
  - `GET /signals?strategy=&status=` — Filtered signals
  - `GET /signals/:id` — Single signal
  - `GET /analytics/performance` — Performance metrics
  - `GET /analytics/equity-curve?days=` — Equity curve data
  - `GET /analytics/win-rate` — Win rate data
  - `GET /settings` — Get settings
  - `PUT /settings` — Update settings
  - `GET /health` — Health check

**Next.js rewrites** in `next.config.ts`:
```typescript
{ source: "/api/:path*", destination: "http://localhost:8000/:path*" }
{ source: "/ws/:path*", destination: "http://localhost:8000/ws/:path*" }
```

### 3.5 WebSocket Usage

**`lib/websocket.ts`** — `WSClient` singleton:

- Connects to `ws(s)://<current-host>/ws`
- Auto-reconnects on close (3-second delay)
- `subscribe(fn)` returns unsubscribe function
- `send(data)` for outbound messages
- `disconnect()` for cleanup

**Not currently wired to any component.** The client exists but no page subscribes to WS messages. The stores have `addTrade`/`updateSignal`/`updatePosition` mutation methods ready for WS-driven updates, but no WS subscription code connects them.

### 3.6 State Management (Zustand)

**`tradeStore.ts`**:

```typescript
interface TradeState {
  portfolio: Portfolio;     // { balance, equity, unrealizedPnl, realizedPnl, dayPnl, totalReturn }
  positions: Position[];    // { id, symbol, side, qty, entry, current, pnl, pnlPct, openedAt }
  trades: Trade[];          // { id, symbol, side, qty, price, pnl, strategy, executedAt }
  loading: boolean;
  fetchPortfolio();         // GET /api/portfolio
  fetchPositions();         // GET /api/positions
  fetchTrades(limit?);      // GET /api/trades
  updatePosition(pos);      // For WS updates
  addTrade(trade);          // For WS updates
}
```

- `PortfolioCard` polls `fetchPortfolio()` every 10 seconds
- `PositionsTable` polls `fetchPositions()` every 5 seconds
- `DashboardPage` fetches trades and signals on mount

**`signalStore.ts`**:

```typescript
interface SignalState {
  signals: Signal[];
  loading: boolean;
  filter: { strategy?: string; status?: string };
  fetchSignals();           // GET /api/signals with filter params
  setFilter(filter);
  addSignal(signal);        // For WS updates
  updateSignal(signal);     // For WS updates
}
```

### 3.7 Charts

**`TradingChart.tsx`** uses `lightweight-charts` (TradingView's library):

- Professional candlestick chart
- Dark theme matching brand colors
- Responsive via ResizeObserver
- Accepts `OHLCData[]` with `{ time, open, high, low, close }`
- Used on Dashboard (empty data) and Analytics (equity curve)

### 3.8 Settings Page

Fully implemented settings form with:

- **Broker Configuration**: Broker selector (Alpaca/IB/Binance), API Key (password field), API Secret (password field), Paper Trading toggle
- **Risk Parameters**: Max Position Size, Max Daily Loss, Max Drawdown %, Position Sizing Method (fixed/percent/kelly/volatility)
- **Notifications**: Enable/disable, on-trade, on-signal, on-error toggles, webhook URL
- **Save**: PUT to `/api/settings` with loading/saved states

### 3.9 Implementation Status

| Feature | Status | Notes |
|---|---|---|
| App shell & sidebar | ✅ Complete | Next.js App Router, dark theme |
| Dashboard | ✅ Functional | Portfolio, positions, trades, signals — all fetching from API |
| Trades page | ✅ Functional | Full table with filters, live data |
| Signals page | ✅ Functional | Card grid with filters, live data |
| Analytics page | ✅ Functional | Metrics + equity curve from API |
| Settings page | ✅ Functional | Full CRUD form, saves to API |
| REST API client | ✅ Complete | Typed, clean, all endpoints |
| Charting | ✅ Complete | Professional candlestick via lightweight-charts |
| WebSocket client | ⚠️ Exists, unused | Client built, not subscribed anywhere |
| Real-time updates | ❌ Not wired | Stores have mutation methods, no WS→store bridge |
| Auth | ❌ None | No login page, no auth tokens |

---

## 4. Cross-App Comparison

### 4.1 Feature Matrix

| Feature | Mobile | Desktop | Web |
|---|---|---|---|
| **Framework** | Flutter 3.2+ | Tauri 1 + React 18 | Next.js 15 + React 19 |
| **State** | Riverpod | Zustand 4 | Zustand 5 |
| **Routing** | Bottom nav (IndexedStack) | HashRouter | App Router |
| **Charts** | fl_chart (custom) | None | lightweight-charts |
| **API Client** | ✅ Full (Dart http) | ❌ None | ✅ Full (fetch) |
| **WebSocket** | ✅ Full impl | ❌ None | ✅ Client only |
| **Auth** | Scaffold (no UI) | ❌ None | ❌ None |
| **Settings** | UI scaffold | ❌ Placeholder | ✅ Full CRUD |
| **Real data** | ❌ All mock | ❌ All mock | ✅ Fetches from API |
| **System tray** | N/A | ✅ Full (Rust) | N/A |
| **Push notifications** | Firebase (unused) | Tauri plugin | ❌ None |
| **Biometric auth** | Package (unused) | N/A | N/A |
| **Design language** | GitHub-dark (custom) | GitHub-dark (Tailwind) | GitHub-dark (Tailwind) |

### 4.2 Maturity Ranking

1. **Web** (most complete) — All pages functional, real API integration, settings CRUD
2. **Mobile** (well-built, disconnected) — Excellent UI/code quality, but all data is mocked; API/WS services exist but aren't wired
3. **Desktop** (early scaffold) — Only dashboard with US stock mock data, 5 of 6 pages are placeholders, no API client

### 4.3 Shared Design System

All three apps use a **GitHub-dark** inspired color palette:

| Token | Hex | Usage |
|---|---|---|
| Background | `#0D1117` | Main background |
| Surface | `#161B22` | Cards, sidebars |
| Card | `#1C2128` | Elevated surfaces (mobile) |
| Border | `#30363D` | Dividers, card borders |
| Green | `#3FB950` / `#00FF88` | Profit, buy, success |
| Red | `#F85149` / `#FF4444` | Loss, sell, error |
| Blue | `#58A6FF` | Accent, links, active |
| Orange | `#D29922` | Warnings (mobile only) |
| Text | `#E6EDF3` | Primary text |
| Muted | `#8B949E` | Secondary text |

---

## 5. Backend API Contract (Inferred)

Based on the mobile `ApiService`, web `api.ts`, and web settings page, the backend is expected to serve:

### REST Endpoints

| Method | Path | Used By | Notes |
|---|---|---|---|
| GET | `/api/v1/portfolio/summary` | Mobile | Portfolio totals |
| GET | `/api/v1/portfolio/positions` | Mobile | Active positions |
| GET | `/api/v1/trades` | Mobile, Web | Paginated (`?page=&limit=` or `?limit=`) |
| GET | `/api/v1/trades/:id` | Mobile, Web | Single trade |
| GET | `/api/v1/signals/active` | Mobile | Active signals only |
| GET | `/api/v1/signals` | Mobile, Web | Filtered (`?strategy=&status=&page=&limit=`) |
| GET | `/api/v1/signals/:id` | Web | Single signal |
| GET | `/api/v1/analytics/performance` | Mobile, Web | Performance metrics |
| GET | `/api/v1/analytics/pnl-history` | Mobile | P&L time series (`?period=`) |
| GET | `/api/v1/analytics/equity-curve` | Web | OHLC equity curve (`?days=`) |
| GET | `/api/v1/analytics/risk` | Mobile | Risk metrics |
| GET | `/api/v1/analytics/win-rate` | Web | Win rate data |
| POST | `/api/v1/auth/login` | Mobile | `{ apiKey, apiSecret }` → `{ token }` |
| GET | `/api/v1/settings` | Web | Get all settings |
| PUT | `/api/v1/settings` | Web | Update settings |
| GET | `/health` | Mobile, Web | Health check |

**Note**: Mobile uses `/api/v1/` prefix, web uses `/api/` (with Next.js rewrite). The desktop CSP references `api.alphastack.dev`.

### WebSocket

| Path | Protocol |
|---|---|
| `/ws` | JSON messages with `{ type, data, timestamp }` |

**Message types expected**:
- `position_update`, `position_opened`, `position_closed`
- `signal_new`, `signal_update`, `signal_expired`
- `trade_executed`, `trade_updated`
- `portfolio_update`
- `ping` / `pong` (heartbeat)

---

## Key Findings & Recommendations

### Critical Gaps

1. **No app actually talks to a real backend** — Mobile is 100% mocked, Desktop has no API client, Web fetches but likely gets errors (no backend running)
2. **No authentication flow** — No login screen on any platform; mobile has the plumbing but no UI
3. **WebSocket is built but unused** — Mobile has a full WS service, Web has a client, but neither connects WS events to UI state
4. **Desktop is a skeleton** — Only 1 of 6 pages has content, and it shows US stocks instead of crypto

### Architecture Strengths

1. **Clean model layer** — Mobile models with `json_serializable` are production-ready
2. **Consistent design** — All three apps share the same dark theme and design language
3. **Well-structured services** — Mobile's `ApiService` and `WebSocketService` are properly architected singletons
4. **Web is functional** — If the backend exists, the web app would work end-to-end
5. **Type safety** — TypeScript on web/desktop, Dart types on mobile

### Next Steps (Priority Order)

1. **Wire mobile data providers to ApiService** — Replace mock data with real API calls
2. **Wire WebSocket to UI** — Connect WS streams to Riverpod/Zustand stores for real-time updates
3. **Build desktop API client** — Port web's `api.ts` pattern or use Tauri's HTTP plugin
4. **Implement authentication** — Login screen on all platforms, token refresh flow
5. **Replace desktop mock data** — Switch from US stocks to crypto trading data
6. **Complete desktop pages** — Portfolio, Markets, Strategies, Alerts, Settings
