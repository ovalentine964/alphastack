import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../models/trade.dart';
import '../models/signal.dart';
import '../models/agent_status.dart';

// ─── Exceptions ──────────────────────────────────────────────────────────────

class ApiException implements Exception {
  final String message;
  final int? statusCode;
  final bool isNetworkError;
  ApiException(this.message, {this.statusCode, this.isNetworkError = false});

  @override
  String toString() => 'ApiException($statusCode): $message';
}

class OfflineException extends ApiException {
  OfflineException() : super('No network connection', isNetworkError: true);
}

// ─── Response Cache Entry ────────────────────────────────────────────────────

class _CacheEntry {
  final dynamic data;
  final DateTime fetchedAt;
  final Duration ttl;

  _CacheEntry(this.data, {this.ttl = const Duration(minutes: 5)})
      : fetchedAt = DateTime.now();

  bool get isExpired => DateTime.now().difference(fetchedAt) > ttl;
}

// ─── API Service ─────────────────────────────────────────────────────────────

class ApiService {
  static const String _baseUrlKey = 'api_base_url';
  static const String _tokenKey = 'auth_token';
  static const String _refreshTokenKey = 'refresh_token';
  static const String _binanceApiKey = 'binance_api_key';
  static const String _binanceApiSecret = 'binance_api_secret';
  static const String _mimoApiKey = 'mimo_api_key';
  static const String _isTestnetKey = 'is_testnet';
  static const String defaultBaseUrl = 'https://alphastack.fly.dev/api/v1';

  // Retry / timeout config
  static const int _maxRetries = 3;
  static const Duration _baseRetryDelay = Duration(seconds: 1);
  static const Duration _requestTimeout = Duration(seconds: 15);
  static const Duration _healthTimeout = Duration(seconds: 5);

  final FlutterSecureStorage _storage = const FlutterSecureStorage();
  String? _baseUrl;
  String? _authToken;
  String? _refreshToken;
  bool _isOffline = false;

  // In-memory response cache (endpoint → entry)
  final Map<String, _CacheEntry> _cache = {};

  // Singleton
  static final ApiService _instance = ApiService._internal();
  factory ApiService() => _instance;
  ApiService._internal();

  // ── Offline state ──────────────────────────────────────────────────

  bool get isOffline => _isOffline;
  final _offlineController = StreamController<bool>.broadcast();
  Stream<bool> get offlineStream => _offlineController.stream;

  void _setOffline(bool value) {
    if (_isOffline != value) {
      _isOffline = value;
      _offlineController.add(value);
    }
  }

  // ── Base URL ───────────────────────────────────────────────────────

  Future<String> get baseUrl async {
    _baseUrl ??= await _storage.read(key: _baseUrlKey) ?? defaultBaseUrl;
    return _baseUrl!;
  }

  Future<void> setBaseUrl(String url) async {
    _baseUrl = url;
    await _storage.write(key: _baseUrlKey, value: url);
  }

  /// Derive the base origin (without /api/v1) for system endpoints.
  Future<String> get _baseOrigin async {
    final base = await baseUrl;
    // Strip /api/v1 suffix if present
    if (base.endsWith('/api/v1')) {
      return base.substring(0, base.length - 7);
    }
    return base;
  }

  // ── Auth Token ─────────────────────────────────────────────────────

  Future<void> setAuthToken(String token) async {
    _authToken = token;
    await _storage.write(key: _tokenKey, value: token);
  }

  Future<void> setRefreshToken(String token) async {
    _refreshToken = token;
    await _storage.write(key: _refreshTokenKey, value: token);
  }

  Future<void> clearAuth() async {
    _authToken = null;
    _refreshToken = null;
    await _storage.delete(key: _tokenKey);
    await _storage.delete(key: _refreshTokenKey);
  }

  // ── API Key Storage ────────────────────────────────────────────────

  Future<void> storeApiKeys({
    required String binanceApiKey,
    required String binanceApiSecret,
    String? mimoApiKey,
    bool isTestnet = true,
  }) async {
    await _storage.write(key: _binanceApiKey, value: binanceApiKey);
    await _storage.write(key: _binanceApiSecret, value: binanceApiSecret);
    await _storage.write(key: _isTestnetKey, value: isTestnet.toString());
    if (mimoApiKey != null && mimoApiKey.isNotEmpty) {
      await _storage.write(key: _mimoApiKey, value: mimoApiKey);
    }
  }

  Future<Map<String, String?>> getStoredApiKeys() async {
    return {
      'binanceApiKey': await _storage.read(key: _binanceApiKey),
      'binanceApiSecret': await _storage.read(key: _binanceApiSecret),
      'mimoApiKey': await _storage.read(key: _mimoApiKey),
      'isTestnet': await _storage.read(key: _isTestnetKey),
    };
  }

  Future<bool> hasStoredKeys() async {
    final apiKey = await _storage.read(key: _binanceApiKey);
    final apiSecret = await _storage.read(key: _binanceApiSecret);
    return apiKey != null &&
        apiKey.isNotEmpty &&
        apiSecret != null &&
        apiSecret.isNotEmpty;
  }

  Future<String?> getBinanceApiKey() async {
    return await _storage.read(key: _binanceApiKey);
  }

  Future<String?> getBinanceApiSecret() async {
    return await _storage.read(key: _binanceApiSecret);
  }

  Future<String?> getMimoApiKey() async {
    return await _storage.read(key: _mimoApiKey);
  }

  Future<bool> isTestnet() async {
    final val = await _storage.read(key: _isTestnetKey);
    return val != 'false';
  }

  Future<void> setTestnet(bool testnet) async {
    await _storage.write(key: _isTestnetKey, value: testnet.toString());
  }

  Future<void> clearApiKeys() async {
    await _storage.delete(key: _binanceApiKey);
    await _storage.delete(key: _binanceApiSecret);
    await _storage.delete(key: _mimoApiKey);
    await _storage.delete(key: _isTestnetKey);
    await clearAuth();
    _cache.clear();
  }

  // ── HTTP helpers with retry + caching ──────────────────────────────

  Future<Map<String, String>> _headers() async {
    _authToken ??= await _storage.read(key: _tokenKey);
    return {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      if (_authToken != null) 'Authorization': 'Bearer $_authToken',
    };
  }

  /// Attempt to silently refresh the access token.
  Future<bool> _tryRefreshToken() async {
    _refreshToken ??= await _storage.read(key: _refreshTokenKey);
    if (_refreshToken == null) return false;

    try {
      final base = await baseUrl;
      final uri = Uri.parse('$base/auth/refresh');
      final response = await http
          .post(
            uri,
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({'refresh_token': _refreshToken}),
          )
          .timeout(_requestTimeout);

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final newAccess = data['access_token'] as String?;
        final newRefresh = data['refresh_token'] as String?;
        if (newAccess != null) {
          await setAuthToken(newAccess);
        }
        if (newRefresh != null) {
          await setRefreshToken(newRefresh);
        }
        return true;
      }
    } catch (_) {
      // Refresh failed — user must re-authenticate
    }
    return false;
  }

  Future<dynamic> _get(
    String endpoint, {
    Map<String, String>? queryParams,
    bool useCache = true,
    Duration? cacheTtl,
    bool useBaseOrigin = false,
  }) async {
    final host = useBaseOrigin ? await _baseOrigin : await baseUrl;
    final uri = Uri.parse('$host/$endpoint').replace(queryParameters: queryParams);
    final cacheKey = uri.toString();

    // Return cached data if valid
    if (useCache && _cache.containsKey(cacheKey) && !_cache[cacheKey]!.isExpired) {
      return _cache[cacheKey]!.data;
    }

    final headers = await _headers();
    dynamic result;

    for (int attempt = 0; attempt <= _maxRetries; attempt++) {
      try {
        final response = await http
            .get(uri, headers: headers)
            .timeout(_requestTimeout);

        result = _handleResponse(response);

        // Cache successful response
        if (useCache) {
          _cache[cacheKey] = _CacheEntry(
            result,
            ttl: cacheTtl ?? const Duration(minutes: 5),
          );
        }

        _setOffline(false);
        return result;
      } on TimeoutException {
        if (attempt == _maxRetries) {
          _setOffline(true);
          // Fall back to cache if available
          if (_cache.containsKey(cacheKey)) {
            return _cache[cacheKey]!.data;
          }
          throw ApiException('Request timed out after ${_maxRetries + 1} attempts',
              isNetworkError: true);
        }
      } on http.ClientException {
        if (attempt == _maxRetries) {
          _setOffline(true);
          if (_cache.containsKey(cacheKey)) {
            return _cache[cacheKey]!.data;
          }
          throw ApiException('Network error', isNetworkError: true);
        }
      } on ApiException catch (e) {
        // Handle 401 — try token refresh once
        if (e.statusCode == 401 && attempt == 0) {
          final refreshed = await _tryRefreshToken();
          if (refreshed) {
            // Retry with new token (don't count as retry)
            final newHeaders = await _headers();
            try {
              final response = await http
                  .get(uri, headers: newHeaders)
                  .timeout(_requestTimeout);
              result = _handleResponse(response);
              if (useCache) {
                _cache[cacheKey] = _CacheEntry(result,
                    ttl: cacheTtl ?? const Duration(minutes: 5));
              }
              _setOffline(false);
              return result;
            } catch (_) {
              // Fall through to normal retry
            }
          }
        }
        if (attempt == _maxRetries) rethrow;
      }

      // Exponential backoff
      if (attempt < _maxRetries) {
        await Future.delayed(_baseRetryDelay * (1 << attempt));
      }
    }

    return result;
  }

  Future<dynamic> _post(String endpoint, {Map<String, dynamic>? body}) async {
    final base = await baseUrl;
    final uri = Uri.parse('$base/$endpoint');
    final headers = await _headers();

    for (int attempt = 0; attempt <= _maxRetries; attempt++) {
      try {
        final response = await http
            .post(uri, headers: headers, body: jsonEncode(body ?? {}))
            .timeout(_requestTimeout);

        final result = _handleResponse(response);
        _setOffline(false);
        return result;
      } on TimeoutException {
        if (attempt == _maxRetries) {
          _setOffline(true);
          throw ApiException('Request timed out', isNetworkError: true);
        }
      } on http.ClientException {
        if (attempt == _maxRetries) {
          _setOffline(true);
          throw ApiException('Network error', isNetworkError: true);
        }
      } on ApiException catch (e) {
        if (e.statusCode == 401 && attempt == 0) {
          final refreshed = await _tryRefreshToken();
          if (refreshed) {
            final newHeaders = await _headers();
            try {
              final response = await http
                  .post(uri, headers: newHeaders, body: jsonEncode(body ?? {}))
                  .timeout(_requestTimeout);
              final result = _handleResponse(response);
              _setOffline(false);
              return result;
            } catch (_) {}
          }
        }
        if (attempt == _maxRetries) rethrow;
      }

      if (attempt < _maxRetries) {
        await Future.delayed(_baseRetryDelay * (1 << attempt));
      }
    }

    return null;
  }

  Future<dynamic> _put(String endpoint, {Map<String, dynamic>? body}) async {
    final base = await baseUrl;
    final uri = Uri.parse('$base/$endpoint');
    final headers = await _headers();

    for (int attempt = 0; attempt <= _maxRetries; attempt++) {
      try {
        final response = await http
            .put(uri, headers: headers, body: jsonEncode(body ?? {}))
            .timeout(_requestTimeout);

        final result = _handleResponse(response);
        _setOffline(false);
        return result;
      } on TimeoutException {
        if (attempt == _maxRetries) {
          _setOffline(true);
          throw ApiException('Request timed out', isNetworkError: true);
        }
      } on http.ClientException {
        if (attempt == _maxRetries) {
          _setOffline(true);
          throw ApiException('Network error', isNetworkError: true);
        }
      } on ApiException catch (e) {
        if (e.statusCode == 401 && attempt == 0) {
          final refreshed = await _tryRefreshToken();
          if (refreshed) {
            final newHeaders = await _headers();
            try {
              final response = await http
                  .put(uri, headers: newHeaders, body: jsonEncode(body ?? {}))
                  .timeout(_requestTimeout);
              final result = _handleResponse(response);
              _setOffline(false);
              return result;
            } catch (_) {}
          }
        }
        if (attempt == _maxRetries) rethrow;
      }

      if (attempt < _maxRetries) {
        await Future.delayed(_baseRetryDelay * (1 << attempt));
      }
    }

    return null;
  }

  dynamic _handleResponse(http.Response response) {
    if (response.statusCode >= 200 && response.statusCode < 300) {
      if (response.body.isEmpty) return null;
      return jsonDecode(response.body);
    }

    // Handle 401 — trigger offline state for UI
    if (response.statusCode == 401) {
      throw ApiException('Authentication required — please log in again',
          statusCode: 401);
    }

    // Handle 429 — rate limited
    if (response.statusCode == 429) {
      final retryAfter = response.headers['retry-after'];
      throw ApiException(
          'Rate limited. Retry after ${retryAfter ?? '?'} seconds',
          statusCode: 429);
    }

    String message;
    try {
      final body = jsonDecode(response.body);
      message = body['detail'] ?? body['message'] ?? body['error'] ?? response.body;
    } catch (_) {
      message = response.body;
    }

    throw ApiException(message, statusCode: response.statusCode);
  }

  /// Clear cached responses (e.g. after settings change or manual refresh).
  void clearCache() => _cache.clear();

  // ─── Portfolio ────────────────────────────────────────────────────

  Future<Map<String, dynamic>> getPortfolioSummary() async {
    final data = await _get('portfolio/pnl', cacheTtl: const Duration(minutes: 2));
    return data as Map<String, dynamic>;
  }

  Future<List<Position>> getActivePositions() async {
    final data = await _get('portfolio', cacheTtl: const Duration(minutes: 1)) as List;
    return data.map((e) => Position.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<Map<String, dynamic>> getPerformanceMetrics() async {
    final data = await _get('portfolio/performance', cacheTtl: const Duration(minutes: 5));
    return data as Map<String, dynamic>;
  }

  // ─── Trades ──────────────────────────────────────────────────────

  Future<List<Trade>> getTrades({int page = 1, int limit = 50, String? statusFilter}) async {
    final queryParams = <String, String>{
      'page': page.toString(),
      'page_size': limit.toString(),
    };
    if (statusFilter != null) {
      queryParams['status'] = statusFilter;
    }
    final data = await _get(
      'trades',
      queryParams: queryParams,
      cacheTtl: const Duration(minutes: 2),
    );
    final items = (data['trades'] ?? data) as List;
    return items.map((e) => Trade.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<Trade> getTrade(String id) async {
    final data = await _get('trades/$id');
    return Trade.fromJson(data);
  }

  Future<Trade> createTrade(TradeCreate trade) async {
    final data = await _post('trades', body: trade.toJson());
    return Trade.fromJson(data);
  }

  Future<Trade> closeTrade(String tradeId, {double? exitPrice}) async {
    final queryParams = exitPrice != null ? {'exit_price': exitPrice.toString()} : null;
    final base = await baseUrl;
    final uri = Uri.parse('$base/trades/$tradeId/close').replace(queryParameters: queryParams);
    final headers = await _headers();
    final response = await http.put(uri, headers: headers).timeout(_requestTimeout);
    final result = _handleResponse(response);
    return Trade.fromJson(result);
  }

  // ─── Signals ─────────────────────────────────────────────────────

  Future<List<Signal>> getActiveSignals({String? symbol, String? strategyId}) async {
    final queryParams = <String, String>{};
    if (symbol != null) queryParams['symbol'] = symbol;
    if (strategyId != null) queryParams['strategy_id'] = strategyId;
    final data = await _get(
      'signals',
      queryParams: queryParams.isNotEmpty ? queryParams : null,
      cacheTtl: const Duration(minutes: 1),
    );
    final items = (data['signals'] ?? data) as List;
    return items.map((e) => Signal.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<List<Signal>> getSignals({int page = 1, int limit = 50, String? symbol}) async {
    final queryParams = <String, String>{
      'page': page.toString(),
      'page_size': limit.toString(),
    };
    if (symbol != null) queryParams['symbol'] = symbol;
    final data = await _get(
      'signals/history',
      queryParams: queryParams,
      cacheTtl: const Duration(minutes: 2),
    );
    final items = (data['signals'] ?? data) as List;
    return items.map((e) => Signal.fromJson(e as Map<String, dynamic>)).toList();
  }

  // ─── Analytics ───────────────────────────────────────────────────

  Future<Map<String, dynamic>> getPerformanceAnalytics({
    String period = '30d',
  }) async {
    final data = await _get('analytics/performance',
        cacheTtl: const Duration(minutes: 5));
    return data as Map<String, dynamic>;
  }

  Future<List<Map<String, dynamic>>> getPnlHistory({
    String period = '30d',
  }) async {
    final data = await _get(
      'analytics/pnl-history',
      queryParams: {'period': period},
      cacheTtl: const Duration(minutes: 5),
    ) as List;
    return data.cast<Map<String, dynamic>>();
  }

  Future<Map<String, dynamic>> getRiskMetrics() async {
    final data = await _get('analytics/risk',
        cacheTtl: const Duration(minutes: 5));
    return data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> getWinRate() async {
    final data = await _get('analytics/win-rate',
        cacheTtl: const Duration(minutes: 5));
    return data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> getEquityCurve({int days = 90}) async {
    final data = await _get(
      'analytics/equity-curve',
      queryParams: {'days': days.toString()},
      cacheTtl: const Duration(minutes: 5),
    );
    return data as Map<String, dynamic>;
  }

  // ─── Agent / Orchestrator Status ──────────────────────────────────

  Future<AgentPipelineStatus> getOrchestratorHealth() async {
    final data = await _get(
      'orchestrator/health',
      useBaseOrigin: true,
      useCache: false,
    );
    return AgentPipelineStatus.fromJson(data as Map<String, dynamic>);
  }

  Future<Map<String, dynamic>> getSystemStatus() async {
    final data = await _get(
      'status',
      useBaseOrigin: true,
      useCache: false,
    );
    return data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> triggerPipelineRun({
    String symbol = 'BTC/USDT',
    String timeframe = '1h',
  }) async {
    final base = await _baseOrigin;
    final uri = Uri.parse('$base/orchestrator/run');
    final headers = await _headers();
    final response = await http
        .post(
          uri,
          headers: headers,
          body: jsonEncode({
            'symbol': symbol,
            'timeframe': timeframe,
          }),
        )
        .timeout(const Duration(seconds: 60));
    return _handleResponse(response) as Map<String, dynamic>;
  }

  // ─── Auth ────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> authenticate({
    required String apiKey,
    required String apiSecret,
  }) async {
    final data = await _post('auth/login', body: {
      'username': apiKey,
      'password': apiSecret,
      'apiKey': apiKey,
      'apiSecret': apiSecret,
    });
    final accessToken = data['access_token'] as String?;
    final refreshToken = data['refresh_token'] as String?;
    if (accessToken != null) {
      await setAuthToken(accessToken);
    }
    if (refreshToken != null) {
      await setRefreshToken(refreshToken);
    }
    return data as Map<String, dynamic>;
  }

  /// Auto-authenticate using stored keys, or demo credentials if none stored.
  Future<bool> autoAuthenticate() async {
    try {
      final apiKey = await getBinanceApiKey();
      final apiSecret = await getBinanceApiSecret();

      if (apiKey != null && apiKey.isNotEmpty &&
          apiSecret != null && apiSecret.isNotEmpty) {
        try {
          await authenticate(apiKey: apiKey, apiSecret: apiSecret);
          return true;
        } catch (_) {
          // Regular login failed — fall through to demo
        }
      }

      return await _demoAuthenticate();
    } catch (e) {
      debugPrint('Auto-authenticate failed: $e');
      return false;
    }
  }

  Future<bool> _demoAuthenticate() async {
    try {
      final base = await baseUrl;
      final uri = Uri.parse('$base/auth/demo');
      final response = await http
          .post(uri, headers: {'Content-Type': 'application/json'})
          .timeout(_requestTimeout);

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final accessToken = data['access_token'] as String?;
        final refreshToken = data['refresh_token'] as String?;
        if (accessToken != null) await setAuthToken(accessToken);
        if (refreshToken != null) await setRefreshToken(refreshToken);
        return true;
      }
    } catch (e) {
      debugPrint('Demo authenticate failed: $e');
    }
    return false;
  }

  // ─── Health ──────────────────────────────────────────────────────

  Future<bool> checkHealth() async {
    try {
      final origin = await _baseOrigin;
      final uri = Uri.parse('$origin/health');
      final response = await http.get(uri).timeout(_healthTimeout);
      final healthy = response.statusCode == 200;
      _setOffline(!healthy);
      return healthy;
    } catch (_) {
      _setOffline(true);
      return false;
    }
  }

  // ─── Connection Status ────────────────────────────────────────────

  Future<Map<String, dynamic>> getConnectionStatus() async {
    final result = <String, dynamic>{
      'healthy': false,
      'authenticated': false,
      'message': 'Unknown',
    };

    try {
      final healthy = await checkHealth();
      result['healthy'] = healthy;

      if (healthy) {
        final hasKeys = await hasStoredKeys();
        if (hasKeys) {
          final hasToken =
              (_authToken ?? await _storage.read(key: _tokenKey)) != null;
          result['authenticated'] = hasToken;
          result['message'] = hasToken
              ? 'Connected and authenticated'
              : 'Backend reachable, authentication pending';
        } else {
          result['message'] = 'Backend reachable, API keys not configured';
        }
      } else {
        result['message'] = 'Backend unreachable';
      }
    } catch (e) {
      result['message'] = 'Connection check failed: $e';
    }

    return result;
  }

  // ─── Cleanup ──────────────────────────────────────────────────────

  void dispose() {
    _offlineController.close();
  }
}
