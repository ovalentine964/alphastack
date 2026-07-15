# AlphaStack Mobile App — UI/UX QA Audit Results

**Date:** 2026-07-16  
**Scope:** Full screen-by-screen audit of `apps/mobile/lib/`  
**Verdict:** App is structurally solid with good architecture, but has **critical data issues** (mock data in 2 screens), **theme inconsistencies**, and **many non-functional UI elements**.

---

## 1. Screen-by-Screen Audit

### 1.1 `dashboard_screen.dart` — ✅ Mostly Good

| State | Handled? | Notes |
|-------|----------|-------|
| Loading | ✅ | Skeleton cards with shimmer animation |
| Error | ✅ | Error card with retry button, error message displayed |
| Empty | ✅ | Empty state card with icon and message |
| Data | ✅ | Portfolio card, positions list, signals list |

**Issues Found:**
- **BUG:** Portfolio balance uses hardcoded `baseBalance = 100000.0` — the server doesn't provide actual account balance, so all P&L percentages are relative to a fake $100K. The `totalBalance` and `totalEquity` values shown to the user are fabricated estimates.
- **DEAD CODE:** `_SectionHeader` "View All" buttons for both Active Positions and Recent Signals have empty `onViewAll: () {}` — tapping does nothing.
- **DEAD CODE:** `_ConnectionBanner` has a "Settings" TextButton with empty `onPressed: () {}` — does not navigate to settings.
- **DEAD CODE:** `_NotificationButton` has `onPressed: () {}` — tapping the bell icon does nothing.

### 1.2 `trades_screen.dart` — 🔴 Critical: Mock Data

**Issues Found:**
- **CRITICAL BUG:** `tradesProvider` returns **hardcoded mock data** with a 600ms simulated delay. It does NOT call `ApiService().getTrades()`. The entire trade history screen shows fabricated data regardless of backend state.
- **BUG:** Sort options in the filter bottom sheet (`_SortOption`) do nothing — `onTap: () => Navigator.pop(context)` just closes the sheet. Sorting is completely unimplemented.
- **BUG:** All hardcoded trades are `status: TradeStatus.closed` except one — the mock data doesn't reflect real trading activity.

### 1.3 `signals_screen.dart` — 🟡 Mostly Good with Issues

| Feature | Status | Notes |
|---------|--------|-------|
| Confluence scores | ✅ | Circular gauge + percentage display |
| Entry/SL/TP | ✅ | Price levels shown in signal card |
| Risk/Reward | ✅ | R:R ratio displayed |
| Factors | ✅ | Shown as tags (max 5) |
| Detail sheet | ✅ | Full signal detail with all fields |
| Filters | ✅ | Direction, confidence, pair filters work |
| Advanced filters | 🟡 | Pair filter works, timeframe filter is dead |

**Issues Found:**
- **BUG (Won't Compile):** `_buildFilterBar` has a dead expression: `active.map((s) => s.timeframe).whereType<String>().toSet().toList()..sort();` — this computes a list and discards the result (no assignment). Likely a leftover from an incomplete refactor.
- **BUG:** `Signal.timeframe` getter always returns `null` because the server doesn't provide this field. The timeframe filter in the advanced filter sheet will never show any options, making it completely non-functional.
- **BUG:** `SignalCard._PriceLevel` widget prepends `$` to the value, but `SignalCard._formatPrice()` already includes `$`. Result: prices display as `$$67,250.00` (double dollar sign).
- **BUG:** The advanced filter sheet reads `current` from the provider once but uses `StatefulBuilder` — when `_SheetChip` `onTap` calls `ref.read(signalFiltersProvider.notifier).state = current.copyWith(...)`, the sheet's local state and provider state can desync because `current` is captured at build time, not re-read.

### 1.4 `analytics_screen.dart` — 🔴 Critical: Mock Data

**Issues Found:**
- **CRITICAL BUG:** ALL THREE providers (`performanceProvider`, `pnlHistoryProvider`, `winRateHistoryProvider`) return **hardcoded mock data** with simulated delays. None call `ApiService().getPerformanceAnalytics()`, `getPnlHistory()`, or `getRiskMetrics()`.
- **CRITICAL BUG:** `_buildStrategyBreakdown` uses hardcoded strategy data — not from the API at all.
- **BUG:** `analyticsPeriodProvider` (7d/30d/90d/1y) is wired to the UI but **changing the period has no effect** — the mock data generators ignore it entirely.
- **BUG:** `PnlDataPoint` is defined in `pnl_chart.dart` but referenced in `analytics_screen.dart` — this works but is an odd import pattern.

### 1.5 `settings_screen.dart` — 🟡 Good with Non-Functional Items

| Dialog | Works? | Notes |
|--------|--------|-------|
| API Endpoint | ✅ | Saves URL, validates format |
| Exchange selection | ❌ | Shows snackbar but doesn't persist selection to `exchangeProvider` |
| Risk Parameters | ✅ | Sliders work, saved via providers |
| Timeframe | ✅ | Selection persisted via `timeframeProvider` |
| Language | ✅ | Selection persisted via `languageProvider` |
| Currency | ✅ | Selection persisted via `currencyProvider` |
| Logout/Disconnect | ✅ | Clears keys, shows confirmation |

**Issues Found:**
- **BUG:** Exchange selection dialog shows 3 options but none update `exchangeProvider`. Tapping any option just shows a snackbar and closes.
- **DEAD CODE:** "Change PIN" → `onTap: () => _showSnackBar(context, 'PIN change coming soon')`
- **DEAD CODE:** "Signal Alerts" → `onTap: () => _showSnackBar(context, 'Signal alerts configured')`
- **DEAD CODE:** "Risk Alerts" → `onTap: () => _showSnackBar(context, 'Risk alerts configured')`
- **DEAD CODE:** "Terms of Service" → `onTap: () => _showSnackBar(context, 'Terms of Service')`
- **DEAD CODE:** "Privacy Policy" → `onTap: () => _showSnackBar(context, 'Privacy Policy')`
- **DEAD CODE:** "Help & Support" → `onTap: () => _showSnackBar(context, 'Help & Support')`
- **DEAD CODE:** Profile edit button `onPressed: () {}` — does nothing.
- **BUG:** Disconnect clears keys but doesn't restart the app or navigate to the first-launch setup screen. User is left on a broken settings screen with cleared credentials.

### 1.6 `api_keys_screen.dart` — ✅ Solid

| Feature | Status | Notes |
|---------|--------|-------|
| Key loading | ✅ | Loads from secure storage on init |
| Key saving | ✅ | Saves to secure storage, verifies connection |
| Validation | ✅ | Required fields, minimum length checks |
| Testnet toggle | ✅ | Warning dialog before enabling live |
| Help card | ✅ | Instructions for getting keys |
| Connection test | ✅ | Health check with status display |

**Issues Found:**
- **MINOR:** Test connection only checks health endpoint, doesn't verify that the stored API keys are valid credentials.
- **MINOR:** No visual feedback (e.g., success icon) after keys are saved — only a snackbar that disappears.

---

## 2. Navigation Audit

### 2.1 Bottom Navigation Bar — ✅ Works

- 5 tabs: Dashboard, Trades, Signals, Analytics, Settings
- `IndexedStack` preserves state across tab switches ✅
- Icons and labels are correct ✅
- `BottomNavigationBarType.fixed` used (no shifting animation) ✅
- `elevation: 8` applied ✅

### 2.2 Screen Transitions

| Transition | Works? | Notes |
|------------|--------|-------|
| Tab switching | ✅ | Instant, state preserved |
| Settings → API Keys | ✅ | `MaterialPageRoute` push |
| Signal list → Signal detail | ✅ | `showModalBottomSheet` with `DraggableScrollableSheet` |
| Filter sheets | ✅ | `showModalBottomSheet` for trades/signals filters |
| First launch → Main app | ✅ | `setState` toggle on `_ready` |

### 2.3 Back Button Behavior — ✅ OK

- Android back button handled by default `Navigator` behavior
- Modal bottom sheets dismiss on back (default Flutter behavior)
- No custom `WillPopScope` / `PopScope` overrides needed for current screens

---

## 3. Data Flow Audit

### 3.1 `ApiService` — ✅ Well-Implemented

| Feature | Status | Notes |
|---------|--------|-------|
| Singleton pattern | ✅ | `static final _instance` |
| Retry with exponential backoff | ✅ | 3 retries, 1s/2s/4s delays |
| Request caching | ✅ | In-memory cache with per-endpoint TTL |
| Offline fallback | ✅ | Returns cached data when offline |
| Token refresh | ✅ | Silent refresh on 401, then retry |
| Rate limit handling | ✅ | 429 detected with retry-after |
| Secure storage | ✅ | `FlutterSecureStorage` for all credentials |
| Response caching | ✅ | TTL-based, cleared on refresh/settings change |

**Endpoints mapped:**

| Method | Endpoint | Used by |
|--------|----------|---------|
| `GET` | `portfolio/pnl` | Dashboard ✅ |
| `GET` | `portfolio` | Dashboard (positions) ✅ |
| `GET` | `trades` | **NOT USED** — trades screen uses mock data 🔴 |
| `GET` | `trades/$id` | Available but unused |
| `GET` | `signals` | Dashboard + Signals screen ✅ |
| `GET` | `signals/history` | Available but unused |
| `GET` | `analytics/performance` | **NOT USED** — analytics screen uses mock data 🔴 |
| `GET` | `analytics/pnl-history` | **NOT USED** 🔴 |
| `GET` | `analytics/risk` | **NOT USED** 🔴 |
| `GET` | `analytics/win-rate` | **NOT USED** 🔴 |
| `POST` | `auth/login` | API Keys screen ✅ |
| `POST` | `auth/refresh` | Auto-refresh on 401 ✅ |
| `GET` | `health` (relative) | Connection check ✅ |

**Issues Found:**
- **BUG:** `checkHealth()` constructs URL as `$base/../health` — if `base` is `http://host:8000/api/v1`, this resolves to `http://host:8000/api/health` (one level up). This works but is fragile and non-obvious. Should use explicit endpoint path.
- **BUG:** `getActivePositions()` calls `GET /portfolio` but the field is called `positions` in the response — if the server returns a different shape, parsing will fail silently.

### 3.2 `WebSocketService` — ✅ Solid

| Feature | Status | Notes |
|---------|--------|-------|
| Auto-reconnect | ✅ | Exponential backoff, max 10 attempts |
| Heartbeat | ✅ | 25s ping interval, responds to server heartbeats |
| Auth handshake | ✅ | Sends auth token as first message |
| Channel subscriptions | ✅ | Auto-subscribes after auth_ok |
| Message routing | ✅ | Prices, trades, signals, system channels |
| State management | ✅ | Stream-based state with broadcast controllers |

**Issues Found:**
- **BUG:** `connect()` sets `_setState(WebSocketState.connected)` immediately after sending auth, before receiving `auth_ok` from the server. If auth fails, the state briefly shows "connected" before switching to "error". Should wait for `auth_ok` before marking connected.
- **MINOR:** `dispose()` doesn't check if already disposed — calling twice will close already-closed stream controllers.

### 3.3 Providers — 🟡 Mixed

| Provider | Data Source | Status |
|----------|-------------|--------|
| `portfolioProvider` | `ApiService().getPortfolioSummary()` | ✅ Real API |
| `positionsProvider` | `ApiService().getActivePositions()` | ✅ Real API |
| `recentSignalsProvider` | `ApiService().getActiveSignals()` | ✅ Real API |
| `testnetModeProvider` | `ApiService().isTestnet()` | ✅ Secure storage |
| `signalsListProvider` | `ApiService().getActiveSignals()` | ✅ Real API |
| `tradesProvider` | Hardcoded mock list | 🔴 Mock data |
| `performanceProvider` | Hardcoded mock map | 🔴 Mock data |
| `pnlHistoryProvider` | Hardcoded mock list | 🔴 Mock data |
| `winRateHistoryProvider` | Hardcoded mock list | 🔴 Mock data |
| `connectionStatusProvider` | `ApiService()` health check | ✅ Real API |
| All `app_preferences` providers | `FlutterSecureStorage` | ✅ Persistent |

### 3.4 Error Handling — ✅ Good

- Network errors caught with retries + exponential backoff ✅
- 401 triggers silent token refresh ✅
- 429 rate limiting detected ✅
- Offline state tracked and broadcast via stream ✅
- UI shows error cards with retry buttons ✅
- Cache fallback when offline ✅

---

## 4. UI/UX Issues

### 4.1 Theme Consistency — 🟡 Multiple Dark-Only Issues

**Hardcoded dark theme colors in:**
- `_AppBootstrap._showUpdateDialog()` — uses `AlphaStackApp.surfaceDark` for dialog background
- `SettingsScreen._showApiDialog()` — uses `AlphaStackApp.surfaceDark`
- `SettingsScreen._showRiskDialog()` — uses `AlphaStackApp.surfaceDark`
- `SettingsScreen._showTimeframeDialog()` — uses `AlphaStackApp.surfaceDark`
- `SettingsScreen._showLanguageDialog()` — uses `AlphaStackApp.surfaceDark`
- `SettingsScreen._showCurrencyDialog()` — uses `AlphaStackApp.surfaceDark`
- `SettingsScreen._showExchangeDialog()` — uses `AlphaStackApp.surfaceDark`
- `SettingsScreen._showLogoutDialog()` — uses `AlphaStackApp.surfaceDark`
- `TradesScreen._showFilterSheet()` — uses `AlphaStackApp.surfaceDark`
- `SignalsScreen._showFilterSheet()` — uses `AlphaStackApp.surfaceDark`
- `SignalsScreen._showSignalDetail()` — uses `AlphaStackApp.surfaceDark`
- `DashboardScreen._buildSkeletonCard()` — uses `AlphaStackApp.cardDark`
- `DashboardScreen._buildSkeletonList()` — uses `AlphaStackApp.cardDark`
- `DashboardScreen._buildErrorCard()` — uses `AlphaStackApp.cardDark`
- `DashboardScreen._buildEmptyState()` — uses `AlphaStackApp.cardDark`
- All `_SettingsTile` — leading icon uses `AlphaStackApp.textSecondary` (dark mode value)
- `PortfolioCard` — gradient uses `AlphaStackApp.cardDark`

**Impact:** When user switches to light mode, all dialogs, sheets, skeleton loaders, and many card backgrounds remain dark. The app looks broken in light mode.

### 4.2 Responsive Layout — ⚠️ Limited Testing

- Orientation locked to portrait only (`setPreferredOrientations`) — acceptable for trading app
- No tablet-specific layouts
- `GridView` in analytics uses fixed `crossAxisCount: 2` — may look cramped on small screens
- `ListView` used throughout — scrolls correctly on all screen sizes

### 4.3 Loading States — ✅ Good

- Shimmer animation widget implemented (`ShimmerLoading`) ✅
- Skeleton cards for loading states ✅
- Progress indicators on buttons during async operations ✅
- Connection status indicators in app bar ✅

### 4.4 Error Messages — ✅ Mostly User-Friendly

- Error cards show icon + title + error details ✅
- Retry buttons provided on all error states ✅
- `_friendlyError()` in signals screen converts technical errors to user-friendly messages ✅
- Connection status banners explain the issue ✅

**Issue:** Raw `error.toString()` shown in dashboard error cards — may expose technical details like stack traces.

---

## 5. Missing / Non-Functional Features

### 5.1 Critical (Breaks Core Functionality)

| # | Location | Issue | Severity |
|---|----------|-------|----------|
| 1 | `trades_screen.dart` `tradesProvider` | Returns hardcoded mock data — never calls API | 🔴 Critical |
| 2 | `analytics_screen.dart` `performanceProvider` | Returns hardcoded mock data — never calls API | 🔴 Critical |
| 3 | `analytics_screen.dart` `pnlHistoryProvider` | Returns hardcoded mock data — never calls API | 🔴 Critical |
| 4 | `analytics_screen.dart` `winRateHistoryProvider` | Returns hardcoded mock data — never calls API | 🔴 Critical |
| 5 | `analytics_screen.dart` `_buildStrategyBreakdown` | Hardcoded strategy data — not from API | 🔴 Critical |

### 5.2 High (Broken Functionality)

| # | Location | Issue | Severity |
|---|----------|-------|----------|
| 6 | `signal_card.dart` `_PriceLevel` | Double dollar sign (`$$67,250.00`) — `_formatPrice` includes `$`, widget adds another | 🟠 High |
| 7 | `signals_screen.dart` `_buildFilterBar` | Dead expression — timeframe list computed but not assigned | 🟠 High |
| 8 | `settings_screen.dart` Exchange dialog | Selection doesn't persist — no call to `exchangeProvider` | 🟠 High |
| 9 | `websocket_service.dart` `connect()` | Sets state to `connected` before `auth_ok` received | 🟠 High |
| 10 | All theme-aware dialogs | Hardcoded `surfaceDark` backgrounds — broken in light mode | 🟠 High |
| 11 | `settings_screen.dart` Disconnect | Clears keys but doesn't restart or navigate to setup | 🟠 High |

### 5.3 Medium (Non-Functional UI Elements)

| # | Location | Element | Issue |
|---|----------|---------|-------|
| 12 | `dashboard_screen.dart` | "View All" (Positions) | `onViewAll: () {}` — empty handler |
| 13 | `dashboard_screen.dart` | "View All" (Signals) | `onViewAll: () {}` — empty handler |
| 14 | `dashboard_screen.dart` | "Settings" button in banner | `onPressed: () {}` — empty handler |
| 15 | `dashboard_screen.dart` | Notification bell | `onPressed: () {}` — empty handler |
| 16 | `dashboard_screen.dart` | Edit profile button | `onPressed: () {}` — empty handler |
| 17 | `settings_screen.dart` | "Change PIN" | Shows snackbar only |
| 18 | `settings_screen.dart` | "Signal Alerts" | Shows snackbar only |
| 19 | `settings_screen.dart` | "Risk Alerts" | Shows snackbar only |
| 20 | `settings_screen.dart` | "Terms of Service" | Shows snackbar only |
| 21 | `settings_screen.dart` | "Privacy Policy" | Shows snackbar only |
| 22 | `settings_screen.dart` | "Help & Support" | Shows snackbar only |
| 23 | `analytics_screen.dart` | Period selector (7d/30d/90d/1y) | Updates provider but data doesn't change (mock) |
| 24 | `trades_screen.dart` | Sort options (Newest/Oldest/P&L) | Closes sheet, doesn't sort |

### 5.4 Low (Minor Issues)

| # | Location | Issue |
|---|----------|-------|
| 25 | `signal.dart` | `timeframe` getter always returns `null` — server doesn't provide it |
| 26 | `api_service.dart` `checkHealth()` | Uses `$base/../health` — fragile URL construction |
| 27 | `dashboard_screen.dart` | Error card shows raw `error.toString()` — may leak technical details |
| 28 | `shimmer_loading.dart` | Hardcoded dark colors in shader — won't look right in light mode |
| 29 | `signals_screen.dart` | Filter sheet state/provider desync — `current` captured at build time |
| 30 | `app.dart` `_showUpdateDialog` | `canLaunchUrl` is deprecated — should use `launchUrl` directly |

---

## 6. Summary

### What Works Well
- **Architecture:** Riverpod providers, singleton services, secure storage — clean and maintainable
- **Dashboard:** Real API integration with proper loading/error/empty states
- **Signals:** Full-featured with confluence scores, price levels, factors, detail sheets, and filters
- **API Service:** Robust with retry, caching, offline fallback, token refresh
- **WebSocket:** Proper reconnect logic, heartbeat, channel subscriptions
- **Navigation:** IndexedStack preserves state, proper push navigation
- **API Keys:** Full CRUD with validation, testnet warning, help card

### What Needs Fixing (Priority Order)
1. **Trades & Analytics screens** — Replace mock data with real API calls (the service methods already exist!)
2. **Theme consistency** — Use `Theme.of(context)` instead of hardcoded `AlphaStackApp.surfaceDark`/`cardDark` in all dialogs and sheets
3. **Double dollar sign** in `SignalCard._PriceLevel` — remove `$` prefix from `_formatPrice` or from widget
4. **Dead expression** in `_buildFilterBar` — fix or remove the timeframe computation
5. **Exchange dialog** — Wire up to `exchangeProvider`
6. **WebSocket auth** — Don't set `connected` until `auth_ok` received
7. **Empty handlers** — Either implement or remove non-functional buttons/tiles
8. **Disconnect flow** — Navigate to first-launch setup after clearing keys
