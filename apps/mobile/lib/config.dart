import 'package:shared_preferences/shared_preferences.dart';

/// Central configuration for the AlphaStack mobile app.
///
/// Stores backend URL and other runtime settings in shared_preferences.
/// Falls back to sensible defaults when no user preference is stored.
class AppConfig {
  static const String _keyBackendUrl = 'alphastack_backend_url';
  static const String _keyWsUrl = 'alphastack_ws_url';
  static const String _keyFirstLaunch = 'alphastack_first_launch';
  static const String _keyLastConnected = 'alphastack_last_connected';

  // ── Default URLs ──────────────────────────────────────────────────────────

  /// Default backend URL for local development.
  static const String defaultBackendUrl = 'http://localhost:8000/api/v1';

  /// Production backend URL (update this when deploying).
  static const String productionBackendUrl = 'https://alphastack.fly.dev/api/v1';

  /// Default WebSocket URL for local development.
  static const String defaultWsUrl = 'ws://localhost:8000/ws';

  /// Production WebSocket URL.
  static const String productionWsUrl = 'wss://alphastack.fly.dev/ws';

  // ── Singleton ─────────────────────────────────────────────────────────────

  static AppConfig? _instance;

  late SharedPreferences _prefs;

  AppConfig._();

  static Future<AppConfig> getInstance() async {
    if (_instance == null) {
      _instance = AppConfig._();
      _instance!._prefs = await SharedPreferences.getInstance();
    }
    return _instance!;
  }

  // ── Backend URL ───────────────────────────────────────────────────────────

  /// Get the configured backend API URL.
  /// Returns stored value, or [defaultBackendUrl] if none is set.
  String get backendUrl =>
      _prefs.getString(_keyBackendUrl) ?? defaultBackendUrl;

  /// Set the backend API URL.
  Future<bool> setBackendUrl(String url) async {
    // Derive WS URL from backend URL
    final wsUrl = _deriveWsUrl(url);
    await _prefs.setString(_keyWsUrl, wsUrl);
    return await _prefs.setString(_keyBackendUrl, url);
  }

  /// Reset backend URL to default.
  Future<bool> resetBackendUrl() async {
    await _prefs.remove(_keyWsUrl);
    return await _prefs.setString(_keyBackendUrl, defaultBackendUrl);
  }

  // ── WebSocket URL ─────────────────────────────────────────────────────────

  /// Get the configured WebSocket URL.
  /// Auto-derives from backend URL if not explicitly set.
  String get wsUrl {
    final stored = _prefs.getString(_keyWsUrl);
    if (stored != null && stored.isNotEmpty) return stored;
    return _deriveWsUrl(backendUrl);
  }

  /// Derive WebSocket URL from REST API base URL.
  static String _deriveWsUrl(String restUrl) {
    try {
      final uri = Uri.parse(restUrl);
      final scheme = uri.scheme == 'https' ? 'wss' : 'ws';
      final port = (uri.port != 80 && uri.port != 443) ? ':${uri.port}' : '';
      return '$scheme://${uri.host}$port/ws';
    } catch (_) {
      return defaultWsUrl;
    }
  }

  // ── First Launch ──────────────────────────────────────────────────────────

  /// Whether this is the first launch (no backend URL configured yet).
  bool get isFirstLaunch => _prefs.getBool(_keyFirstLaunch) ?? true;

  /// Mark first launch as complete.
  Future<bool> markLaunched() async {
    return await _prefs.setBool(_keyFirstLaunch, false);
  }

  // ── Connection Tracking ───────────────────────────────────────────────────

  /// Timestamp of last successful connection (milliseconds since epoch).
  int? get lastConnectedMs => _prefs.getInt(_keyLastConnected);

  /// Record a successful connection.
  Future<bool> recordConnection() async {
    return await _prefs.setInt(
      _keyLastConnected,
      DateTime.now().millisecondsSinceEpoch,
    );
  }

  // ── Utilities ─────────────────────────────────────────────────────────────

  /// Whether the current backend URL is the production URL.
  bool get isProduction =>
      backendUrl == productionBackendUrl ||
      backendUrl.startsWith('https://alphastack.fly.dev');

  /// Whether the current backend URL is localhost.
  bool get isLocalhost =>
      backendUrl.contains('localhost') ||
      backendUrl.contains('127.0.0.1') ||
      backendUrl.contains('10.0.2.2');

  /// Clear all stored configuration.
  Future<void> clearAll() async {
    await _prefs.remove(_keyBackendUrl);
    await _prefs.remove(_keyWsUrl);
    await _prefs.remove(_keyFirstLaunch);
    await _prefs.remove(_keyLastConnected);
  }
}
