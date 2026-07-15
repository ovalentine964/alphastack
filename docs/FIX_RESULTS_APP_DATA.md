# Fix Results: Mock Data → Real API Calls

**Date:** 2026-07-16  
**Status:** ✅ Complete

---

## 1. trades_screen.dart

### Issue
`tradesProvider` returned hardcoded mock `Trade` objects (6 fake trades) with a simulated 600ms delay.

### Fix
Replaced with a single call to `ApiService().getTrades()`, which hits the real backend endpoint `GET /api/v1/trades` with pagination support, retry logic, and caching.

**Before:**
```dart
final tradesProvider = FutureProvider<List<Trade>>((ref) async {
  await Future.delayed(const Duration(milliseconds: 600));
  return [ Trade(id: 't-001', ...), Trade(id: 't-002', ...), ... ];
});
```

**After:**
```dart
import '../services/api_service.dart';

final tradesProvider = FutureProvider<List<Trade>>((ref) async {
  return await ApiService().getTrades();
});
```

**No breaking changes** — provider name, return type, and all consumers remain identical.

---

## 2. analytics_screen.dart — Providers

### Issue
Three providers returned hardcoded mock data with simulated delays:
- `performanceProvider` — fake metrics (winRate: 68.5, totalPnl: 18420.75, etc.)
- `pnlHistoryProvider` — 30 generated `PnlDataPoint` objects with synthetic noise
- `winRateHistoryProvider` — 10 generated `WinRatePoint` objects

### Fix

#### `performanceProvider`
Now calls `ApiService().getPerformanceAnalytics(period: period)` and reactively re-fetches when the selected period changes.

```dart
final performanceProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  final period = ref.watch(analyticsPeriodProvider);
  return await ApiService().getPerformanceAnalytics(period: period);
});
```

#### `pnlHistoryProvider`
Now calls `ApiService().getPnlHistory(period: period)` and converts the raw JSON response into `PnlDataPoint` objects. Reactively re-fetches on period change.

```dart
final pnlHistoryProvider = FutureProvider<List<PnlDataPoint>>((ref) async {
  final period = ref.watch(analyticsPeriodProvider);
  final data = await ApiService().getPnlHistory(period: period);
  return data.map((e) => PnlDataPoint(
    date: DateTime.parse(e['date'] as String),
    value: (e['value'] as num).toDouble(),
  )).toList();
});
```

#### `winRateHistoryProvider`
Now calls `ApiService().getWinRate()` and converts the response's `history` list into `WinRatePoint` objects. Falls back to empty list if `history` key is missing.

```dart
final winRateHistoryProvider = FutureProvider<List<WinRatePoint>>((ref) async {
  final data = await ApiService().getWinRate();
  final history = data['history'] as List? ?? [];
  return history.map((e) => WinRatePoint(
    label: e['label'] as String? ?? '',
    winRate: (e['win_rate'] as num?)?.toDouble() ?? 0,
    trades: (e['trades'] as num?)?.toInt() ?? 0,
  )).toList();
});
```

---

## 3. analytics_screen.dart — Strategy Breakdown

### Issue
`_buildStrategyBreakdown` used hardcoded `_StrategyData` list with 4 fake strategies.

### Fix
- Created `strategyBreakdownProvider` that calls `ApiService().getPerformanceAnalytics()` and extracts the `strategies` array from the response
- Updated `_buildStrategyBreakdown` to accept `List<_StrategyData>` as a parameter instead of generating its own data
- Updated the `build` method to use `.when()` for loading/error handling on the strategy breakdown section

```dart
final strategyBreakdownProvider = FutureProvider<List<_StrategyData>>((ref) async {
  final data = await ApiService().getPerformanceAnalytics();
  final strategies = data['strategies'] as List? ?? [];
  return strategies.map((e) => _StrategyData(
    e['name'] as String? ?? 'Unknown',
    (e['trades'] as num?)?.toInt() ?? 0,
    (e['win_rate'] as num?)?.toDouble() ?? 0,
    (e['pnl'] as num?)?.toDouble() ?? 0,
  )).toList();
});
```

---

## API Endpoints Used

| Provider | API Method | Endpoint | Cache TTL |
|---|---|---|---|
| `tradesProvider` | `getTrades()` | `GET /api/v1/trades` | 2 min |
| `performanceProvider` | `getPerformanceAnalytics()` | `GET /api/v1/analytics/performance` | 5 min |
| `pnlHistoryProvider` | `getPnlHistory()` | `GET /api/v1/analytics/pnl-history` | 5 min |
| `winRateHistoryProvider` | `getWinRate()` | `GET /api/v1/analytics/win-rate` | 5 min |
| `strategyBreakdownProvider` | `getPerformanceAnalytics()` | `GET /api/v1/analytics/performance` | 5 min |

## Error Handling
All providers use Riverpod's built-in `.when(data:, loading:, error:)` pattern. The existing loading skeletons and error containers in the UI are preserved — no UI changes were needed.

## Breaking Changes
**None.** All provider names, types, and consumer widgets remain unchanged. The only difference is the data source.
