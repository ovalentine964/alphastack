import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

const _storage = FlutterSecureStorage();

// ─── Theme ───────────────────────────────────────────────────────────────────

/// Dark mode enabled (default: true).
final darkModeProvider = StateNotifierProvider<BoolNotifier, bool>((ref) {
  return BoolNotifier(key: 'pref_dark_mode', defaultValue: true);
});

// ─── Security ────────────────────────────────────────────────────────────────

/// Biometric auth enabled.
final biometricEnabledProvider = StateNotifierProvider<BoolNotifier, bool>((ref) {
  return BoolNotifier(key: 'pref_biometric', defaultValue: false);
});

/// PIN lock enabled.
final pinEnabledProvider = StateNotifierProvider<BoolNotifier, bool>((ref) {
  return BoolNotifier(key: 'pref_pin_enabled', defaultValue: false);
});

/// Stored PIN hash (read-only getter provider).
final pinHashProvider = FutureProvider<String?>((ref) async {
  return await _storage.read(key: 'pref_pin_hash');
});

// ─── Notifications ───────────────────────────────────────────────────────────

/// Push notifications enabled.
final notificationsEnabledProvider = StateNotifierProvider<BoolNotifier, bool>((ref) {
  return BoolNotifier(key: 'pref_notifications', defaultValue: true);
});

/// Auto-refresh enabled.
final autoRefreshProvider = StateNotifierProvider<BoolNotifier, bool>((ref) {
  return BoolNotifier(key: 'pref_auto_refresh', defaultValue: true);
});

// ─── Signal Alerts ───────────────────────────────────────────────────────────

/// Notify on new signals.
final signalAlertNewProvider = StateNotifierProvider<BoolNotifier, bool>((ref) {
  return BoolNotifier(key: 'pref_signal_alert_new', defaultValue: true);
});

/// Notify only high-confidence signals.
final signalAlertHighConfidenceProvider = StateNotifierProvider<BoolNotifier, bool>((ref) {
  return BoolNotifier(key: 'pref_signal_alert_high_conf', defaultValue: false);
});

// ─── Risk Alerts ─────────────────────────────────────────────────────────────

/// Max drawdown percentage (5, 10, 15, 20).
final maxDrawdownProvider = StateNotifierProvider<DoubleNotifier, double>((ref) {
  return DoubleNotifier(key: 'pref_max_drawdown', defaultValue: 10.0);
});

/// Daily loss limit percentage.
final dailyLossLimitProvider = StateNotifierProvider<DoubleNotifier, double>((ref) {
  return DoubleNotifier(key: 'pref_daily_loss_limit', defaultValue: 5.0);
});

/// Circuit breaker alerts enabled.
final circuitBreakerEnabledProvider = StateNotifierProvider<BoolNotifier, bool>((ref) {
  return BoolNotifier(key: 'pref_circuit_breaker', defaultValue: true);
});

// ─── Trading ─────────────────────────────────────────────────────────────────

/// Selected exchange: 'binance' or 'binance_testnet'.
final exchangeProvider = StateNotifierProvider<StringNotifier, String>((ref) {
  return StringNotifier(key: 'pref_exchange', defaultValue: 'binance_testnet');
});

/// Max position size as % of portfolio.
final maxPositionSizeProvider = StateNotifierProvider<DoubleNotifier, double>((ref) {
  return DoubleNotifier(key: 'pref_max_position_size', defaultValue: 5.0);
});

/// Max leverage (1-10).
final maxLeverageProvider = StateNotifierProvider<IntNotifier, int>((ref) {
  return IntNotifier(key: 'pref_max_leverage', defaultValue: 3);
});

/// Max concurrent positions (1-10).
final maxConcurrentPositionsProvider = StateNotifierProvider<IntNotifier, int>((ref) {
  return IntNotifier(key: 'pref_max_concurrent_pos', defaultValue: 5);
});

/// Default timeframe.
final timeframeProvider = StateNotifierProvider<StringNotifier, String>((ref) {
  return StringNotifier(key: 'pref_timeframe', defaultValue: '4h');
});

// ─── Appearance ──────────────────────────────────────────────────────────────

/// Language code: 'en', 'sw', 'fr'.
final languageProvider = StateNotifierProvider<StringNotifier, String>((ref) {
  return StringNotifier(key: 'pref_language', defaultValue: 'en');
});

/// Currency code: 'USD', 'KES', 'EUR', 'GBP', 'BTC'.
final currencyProvider = StateNotifierProvider<StringNotifier, String>((ref) {
  return StringNotifier(key: 'pref_currency', defaultValue: 'USD');
});

// ─── Generic Notifiers ───────────────────────────────────────────────────────

class BoolNotifier extends StateNotifier<bool> {
  final String _key;
  BoolNotifier({required String key, required bool defaultValue})
      : _key = key,
        super(defaultValue) {
    _load();
  }

  Future<void> _load() async {
    final val = await _storage.read(key: _key);
    if (val != null) state = val == 'true';
  }

  Future<void> toggle() async {
    state = !state;
    await _storage.write(key: _key, value: state.toString());
  }

  Future<void> set(bool value) async {
    state = value;
    await _storage.write(key: _key, value: value.toString());
  }
}

class DoubleNotifier extends StateNotifier<double> {
  final String _key;
  DoubleNotifier({required String key, required double defaultValue})
      : _key = key,
        super(defaultValue) {
    _load();
  }

  Future<void> _load() async {
    final val = await _storage.read(key: _key);
    if (val != null) state = double.tryParse(val) ?? state;
  }

  Future<void> set(double value) async {
    state = value;
    await _storage.write(key: _key, value: value.toString());
  }
}

class IntNotifier extends StateNotifier<int> {
  final String _key;
  IntNotifier({required String key, required int defaultValue})
      : _key = key,
        super(defaultValue) {
    _load();
  }

  Future<void> _load() async {
    final val = await _storage.read(key: _key);
    if (val != null) state = int.tryParse(val) ?? state;
  }

  Future<void> set(int value) async {
    state = value;
    await _storage.write(key: _key, value: value.toString());
  }
}

class StringNotifier extends StateNotifier<String> {
  final String _key;
  StringNotifier({required String key, required String defaultValue})
      : _key = key,
        super(defaultValue) {
    _load();
  }

  Future<void> _load() async {
    final val = await _storage.read(key: _key);
    if (val != null) state = val;
  }

  Future<void> set(String value) async {
    state = value;
    await _storage.write(key: _key, value: value);
  }
}
