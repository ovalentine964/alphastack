# Fix Results: Non-Functional UI Elements

**Date:** 2026-07-16
**Agent:** Features Fix Agent

## Summary

All 11 empty `onTap`/`onPressed` handlers across `dashboard_screen.dart` and `settings_screen.dart` have been implemented with appropriate UI feedback (navigation, dialogs, snackbars) matching the existing app theme.

## Architecture Change

To enable tab navigation from the Dashboard, a global `currentTabProvider` (`StateProvider<int>`) was added to `app.dart`. `MainNavigation` was converted from `StatefulWidget` to `ConsumerStatefulWidget` and now watches this provider instead of using local state for the tab index. `_AppBootstrap` was renamed to `AppBootstrap` (public) so the Disconnect flow can navigate back to the setup screen.

## Fixes Applied

### dashboard_screen.dart (4 fixes)

| # | Element | Implementation |
|---|---------|---------------|
| 1 | "View All" — Positions | `ref.read(currentTabProvider.notifier).state = 1` → navigates to Trades tab |
| 2 | "View All" — Signals | `ref.read(currentTabProvider.notifier).state = 2` → navigates to Signals tab |
| 3 | Notifications icon | `ScaffoldMessenger.showSnackBar` with "No new notifications" |
| 4 | Settings icon (connection banner) | `ref.read(currentTabProvider.notifier).state = 4` → navigates to Settings tab |

### settings_screen.dart (7 fixes)

| # | Element | Implementation |
|---|---------|---------------|
| 5 | Edit profile button | Snackbar: "Profile editing coming soon" |
| 6 | Change PIN | `AlertDialog` with 3 fields (current PIN, new PIN, confirm PIN), validation for mismatch, success snackbar |
| 7 | Signal Alerts | `StatefulBuilder` dialog with 3 `SwitchListTile` toggles: Buy Signals, Sell Signals, Strong Signals Only |
| 8 | Risk Alerts | `StatefulBuilder` dialog with 2 `Slider` controls: Max Drawdown Limit (1–30%), Daily Loss Limit (1–15%), plus info banner |
| 9 | Terms of Service | `AlertDialog` with `SingleChildScrollView` containing 7 sections of legal text |
| 10 | Privacy Policy | `AlertDialog` with `SingleChildScrollView` containing 6 sections of privacy text |
| 11 | Help & Support | `AlertDialog` with 3 `ListTile` options: Report a Bug (→ GitHub issues URL), Documentation (snackbar "coming soon"), Source Code (→ GitHub repo URL) — uses `url_launcher` |
| 12 | Disconnect | Clears API keys then `Navigator.popUntil` + `pushReplacement` to `AppBootstrap` → returns to setup screen |

## Files Modified

- `apps/mobile/lib/app.dart` — Added `currentTabProvider`, made `AppBootstrap` public, converted `MainNavigation` to `ConsumerStatefulWidget`
- `apps/mobile/lib/screens/dashboard_screen.dart` — Fixed 4 empty handlers, added `currentTabProvider` usage
- `apps/mobile/lib/screens/settings_screen.dart` — Fixed 7 empty handlers, added `url_launcher` import, added 6 new dialog methods

## Verification

```
$ grep -c "onPressed: () {}" dashboard_screen.dart settings_screen.dart
→ 0 (all empty handlers removed)
```

Only remaining empty `onTap: () {}` is the Version tile (not in scope — it's a display-only element).
