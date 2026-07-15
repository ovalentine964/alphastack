# AlphaStack Mobile — UI Bug Fix Results

**Date:** 2026-07-16  
**Agent:** UI Fix Subagent

---

## Fix 1: Double Dollar Sign in Signal Card

**File:** `apps/mobile/lib/widgets/signal_card.dart`  
**Issue:** `_formatPrice` returned raw numbers while `_PriceLevel` added a `$` prefix via `'\$$value'`. If `_formatPrice` were ever updated to include `$` (as the `signals_screen.dart` version does), the display would show `$$67,250.00`.

**Fix:**
- Updated `_formatPrice` to include the `$` prefix (consistent with `signals_screen.dart`'s version)
- Removed the redundant `$` from `_PriceLevel`'s `Text` widget — now displays `value` directly instead of `'\$$value'`

**Result:** Single `$` prefix on all price values. `_formatPrice` is now the single source of truth for the `$` symbol across both files.

---

## Fix 2: Dead Expression in Filter Bar

**File:** `apps/mobile/lib/screens/signals_screen.dart`  
**Issue:** `_buildFilterBar` contained a dead expression that computed a sorted timeframe list but never assigned it to a variable:
```dart
active.map((s) => s.timeframe).whereType<String>().toSet().toList()
  ..sort();
```

**Fix:** Removed the dead expression entirely. The timeframe data was computed but never used in the filter bar UI (filter bar only has direction and confidence chips).

**Result:** No dead code warnings. Filter bar renders correctly.

---

## Fix 3: Exchange Dialog Not Persisting

**File:** `apps/mobile/lib/screens/settings_screen.dart`  
**Issue:** `_showExchangeDialog` showed a selection dialog but only displayed a snackbar — it never wrote the selection to `exchangeProvider`.

**Fix:** Added `ref.read(exchangeProvider.notifier).set(...)` calls for each exchange option:
- Binance Futures → `'binance'`
- Binance Spot → `'binance_spot'`
- Binance Testnet → `'binance_testnet'`

**Result:** Exchange selection persists to secure storage via `exchangeProvider` and survives app restarts.

---

## Fix 4: Hardcoded `surfaceDark` in Dialog Backgrounds

**File:** `apps/mobile/lib/screens/settings_screen.dart`  
**Issue:** All 12 dialog backgrounds used hardcoded `AlphaStackApp.surfaceDark` instead of reading from the active theme.

**Fix:** Replaced all `backgroundColor: AlphaStackApp.surfaceDark` with `backgroundColor: Theme.of(dialogContext).colorScheme.surface` in every dialog:
- API Endpoint dialog
- Exchange dialog
- Risk Parameters dialog
- Timeframe dialog
- Language dialog
- Currency dialog
- Change PIN dialog
- Signal Alerts dialog
- Risk Alerts dialog
- Terms of Service dialog
- Privacy Policy dialog
- Help & Support dialog
- Disconnect/Logout dialog

**Result:** Dialogs now respect the active theme's surface color, supporting both dark and light modes.

---

## Fix 5: Premature WebSocket Connected State

**File:** `apps/mobile/lib/services/websocket_service.dart`  
**Issue:** `connect()` set `_setState(WebSocketState.connected)` immediately after the TCP connection was established, *before* the server confirmed authentication via `auth_ok`. This meant UI components could show "connected" status before the auth handshake completed.

**Fix:** Removed the premature `_setState(WebSocketState.connected)` from `connect()`. The state now stays as `connecting` until the `auth_ok` handler in `_onMessage` sets it to `connected`. The `_reconnectAttempts` counter is still reset in `connect()` on successful TCP establishment.

**Result:** WebSocket state accurately reflects auth status. UI shows "connecting" until `auth_ok` is received, then transitions to "connected".

---

## Summary

| # | File | Issue | Status |
|---|------|-------|--------|
| 1 | `signal_card.dart` | Double dollar sign | ✅ Fixed |
| 2 | `signals_screen.dart` | Dead expression | ✅ Fixed |
| 3 | `settings_screen.dart` | Exchange persistence | ✅ Fixed |
| 4 | `settings_screen.dart` | Hardcoded surfaceDark | ✅ Fixed |
| 5 | `websocket_service.dart` | Premature connected state | ✅ Fixed |
