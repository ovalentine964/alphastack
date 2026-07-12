import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../models/trade.dart';
import '../models/signal.dart';

class ApiException implements Exception {
  final String message;
  final int? statusCode;
  ApiException(this.message, {this.statusCode});

  @override
  String toString() => 'ApiException($statusCode): $message';
}

class ApiService {
  static const String _baseUrlKey = 'api_base_url';
  static const String _tokenKey = 'auth_token';
  static const String _defaultBaseUrl = 'http://localhost:8000/api/v1';

  final FlutterSecureStorage _storage = const FlutterSecureStorage();
  String? _baseUrl;
  String? _authToken;

  // Singleton
  static final ApiService _instance = ApiService._internal();
  factory ApiService() => _instance;
  ApiService._internal();

  Future<String> get baseUrl async {
    _baseUrl ??= await _storage.read(key: _baseUrlKey) ?? _defaultBaseUrl;
    return _baseUrl!;
  }

  Future<void> setBaseUrl(String url) async {
    _baseUrl = url;
    await _storage.write(key: _baseUrlKey, value: url);
  }

  Future<void> setAuthToken(String token) async {
    _authToken = token;
    await _storage.write(key: _tokenKey, value: token);
  }

  Future<void> clearAuth() async {
    _authToken = null;
    await _storage.delete(key: _tokenKey);
  }

  Future<Map<String, String>> _headers() async {
    _authToken ??= await _storage.read(key: _tokenKey);
    return {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      if (_authToken != null) 'Authorization': 'Bearer $_authToken',
    };
  }

  Future<dynamic> _get(String endpoint, {Map<String, String>? queryParams}) async {
    final base = await baseUrl;
    final uri = Uri.parse('$base/$endpoint').replace(queryParameters: queryParams);
    final headers = await _headers();

    final response = await http.get(uri, headers: headers).timeout(
      const Duration(seconds: 30),
    );

    return _handleResponse(response);
  }

  Future<dynamic> _post(String endpoint, {Map<String, dynamic>? body}) async {
    final base = await baseUrl;
    final uri = Uri.parse('$base/$endpoint');
    final headers = await _headers();

    final response = await http
        .post(uri, headers: headers, body: jsonEncode(body ?? {}))
        .timeout(const Duration(seconds: 30));

    return _handleResponse(response);
  }

  dynamic _handleResponse(http.Response response) {
    if (response.statusCode >= 200 && response.statusCode < 300) {
      if (response.body.isEmpty) return null;
      return jsonDecode(response.body);
    }

    String message;
    try {
      final body = jsonDecode(response.body);
      message = body['message'] ?? body['error'] ?? response.body;
    } catch (_) {
      message = response.body;
    }

    throw ApiException(message, statusCode: response.statusCode);
  }

  // ─── Portfolio ────────────────────────────────────────────

  Future<Map<String, dynamic>> getPortfolioSummary() async {
    final data = await _get('portfolio/summary');
    return data as Map<String, dynamic>;
  }

  Future<List<Position>> getActivePositions() async {
    final data = await _get('portfolio/positions') as List;
    return data.map((e) => Position.fromJson(e)).toList();
  }

  // ─── Trades ──────────────────────────────────────────────

  Future<List<Trade>> getTrades({int page = 1, int limit = 50}) async {
    final data = await _get(
      'trades',
      queryParams: {
        'page': page.toString(),
        'limit': limit.toString(),
      },
    ) as List;
    return data.map((e) => Trade.fromJson(e)).toList();
  }

  Future<Trade> getTrade(String id) async {
    final data = await _get('trades/$id');
    return Trade.fromJson(data);
  }

  // ─── Signals ─────────────────────────────────────────────

  Future<List<Signal>> getActiveSignals() async {
    final data = await _get('signals/active') as List;
    return data.map((e) => Signal.fromJson(e)).toList();
  }

  Future<List<Signal>> getSignals({int page = 1, int limit = 50}) async {
    final data = await _get(
      'signals',
      queryParams: {
        'page': page.toString(),
        'limit': limit.toString(),
      },
    ) as List;
    return data.map((e) => Signal.fromJson(e)).toList();
  }

  // ─── Analytics ───────────────────────────────────────────

  Future<Map<String, dynamic>> getPerformanceAnalytics({
    String period = '30d',
  }) async {
    final data = await _get(
      'analytics/performance',
      queryParams: {'period': period},
    );
    return data as Map<String, dynamic>;
  }

  Future<List<Map<String, dynamic>>> getPnlHistory({
    String period = '30d',
  }) async {
    final data = await _get(
      'analytics/pnl-history',
      queryParams: {'period': period},
    ) as List;
    return data.cast<Map<String, dynamic>>();
  }

  Future<Map<String, dynamic>> getRiskMetrics() async {
    final data = await _get('analytics/risk');
    return data as Map<String, dynamic>;
  }

  // ─── Auth ────────────────────────────────────────────────

  Future<Map<String, dynamic>> authenticate({
    required String apiKey,
    required String apiSecret,
  }) async {
    final data = await _post('auth/login', body: {
      'apiKey': apiKey,
      'apiSecret': apiSecret,
    });
    if (data['token'] != null) {
      await setAuthToken(data['token']);
    }
    return data as Map<String, dynamic>;
  }

  // ─── Health ──────────────────────────────────────────────

  Future<bool> checkHealth() async {
    try {
      final base = await baseUrl;
      final uri = Uri.parse('$base/../health');
      final response = await http.get(uri).timeout(
        const Duration(seconds: 5),
      );
      return response.statusCode == 200;
    } catch (_) {
      return false;
    }
  }
}
