import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

enum WebSocketState { disconnected, connecting, connected, error, reconnecting }

class WebSocketMessage {
  final String type;
  final Map<String, dynamic> data;
  final DateTime timestamp;

  WebSocketMessage({
    required this.type,
    required this.data,
    DateTime? timestamp,
  }) : timestamp = timestamp ?? DateTime.now();

  factory WebSocketMessage.fromJson(Map<String, dynamic> json) {
    // Server uses two shapes:
    //   Control messages: {"type": "auth_ok", "user_id": "..."}
    //                     {"type": "pong", "ts": ...}
    //                     {"type": "heartbeat", "ts": ...}
    //   Broadcast messages: {"channel": "prices", "data": {...}, "ts": ...}
    //
    // Normalise both into (type, data).
    final String type;
    final Map<String, dynamic> data;

    if (json.containsKey('channel') && json.containsKey('data')) {
      // Broadcast message — use channel name as type
      type = json['channel'] as String;
      data = json['data'] as Map<String, dynamic>? ?? {};
    } else {
      type = json['type'] as String? ?? 'unknown';
      data = json['data'] as Map<String, dynamic>? ?? {};
    }

    DateTime ts;
    if (json['ts'] != null) {
      final raw = json['ts'];
      ts = raw is num
          ? DateTime.fromMillisecondsSinceEpoch((raw * 1000).toInt())
          : DateTime.tryParse(raw.toString()) ?? DateTime.now();
    } else if (json['timestamp'] != null) {
      ts = DateTime.tryParse(json['timestamp'].toString()) ?? DateTime.now();
    } else {
      ts = DateTime.now();
    }

    return WebSocketMessage(type: type, data: data, timestamp: ts);
  }
}

class WebSocketService {
  static const String _wsUrlKey = 'ws_url';
  static const String _defaultWsUrl = 'ws://localhost:8000/ws';

  final FlutterSecureStorage _storage = const FlutterSecureStorage();

  WebSocketChannel? _channel;
  WebSocketState _state = WebSocketState.disconnected;
  Timer? _heartbeatTimer;
  Timer? _reconnectTimer;
  int _reconnectAttempts = 0;
  static const int _maxReconnectAttempts = 10;
  static const Duration _heartbeatInterval = Duration(seconds: 25);
  static const Duration _reconnectBaseDelay = Duration(seconds: 2);
  bool _disposed = false;

  // Stream controllers
  final _stateController = StreamController<WebSocketState>.broadcast();
  final _messageController = StreamController<WebSocketMessage>.broadcast();
  final _positionUpdateController =
      StreamController<Map<String, dynamic>>.broadcast();
  final _signalUpdateController =
      StreamController<Map<String, dynamic>>.broadcast();
  final _tradeUpdateController =
      StreamController<Map<String, dynamic>>.broadcast();
  final _portfolioUpdateController =
      StreamController<Map<String, dynamic>>.broadcast();
  final _priceUpdateController =
      StreamController<Map<String, dynamic>>.broadcast();
  final _agentStatusController =
      StreamController<Map<String, dynamic>>.broadcast();

  // Public streams
  Stream<WebSocketState> get stateStream => _stateController.stream;
  Stream<WebSocketMessage> get messageStream => _messageController.stream;
  Stream<Map<String, dynamic>> get positionUpdates =>
      _positionUpdateController.stream;
  Stream<Map<String, dynamic>> get signalUpdates =>
      _signalUpdateController.stream;
  Stream<Map<String, dynamic>> get tradeUpdates =>
      _tradeUpdateController.stream;
  Stream<Map<String, dynamic>> get portfolioUpdates =>
      _portfolioUpdateController.stream;
  Stream<Map<String, dynamic>> get priceUpdates =>
      _priceUpdateController.stream;
  Stream<Map<String, dynamic>> get agentStatusUpdates =>
      _agentStatusController.stream;

  WebSocketState get state => _state;
  bool get isConnected => _state == WebSocketState.connected;

  // Singleton
  static final WebSocketService _instance = WebSocketService._internal();
  factory WebSocketService() => _instance;
  WebSocketService._internal();

  /// Derive WS URL from stored API base URL.
  Future<String> get _resolvedWsUrl async {
    final stored = await _storage.read(key: _wsUrlKey);
    if (stored != null && stored.isNotEmpty) return stored;

    // Derive from REST base URL
    final restBaseUrl = await _storage.read(key: 'api_base_url') ?? '';
    if (restBaseUrl.isNotEmpty) {
      // Convert https://host/api/v1 → wss://host/ws
      // Convert http://host/api/v1 → ws://host/ws
      try {
        final uri = Uri.parse(restBaseUrl);
        final scheme = uri.scheme == 'https' ? 'wss' : 'ws';
        return '$scheme://${uri.host}${uri.port != 80 && uri.port != 443 ? ':${uri.port}' : ''}/ws';
      } catch (_) {}
    }

    return _defaultWsUrl;
  }

  /// Connect to the WebSocket server.
  ///
  /// The server expects:
  /// 1. TCP/WebSocket connection
  /// 2. First message within 10s: {"type": "auth", "token": "<jwt>"}
  /// 3. Server responds: {"type": "auth_ok", ...} or {"type": "auth_error", ...}
  /// 4. Then subscribe to channels
  Future<void> connect() async {
    if (_state == WebSocketState.connected ||
        _state == WebSocketState.connecting) {
      return;
    }

    _setState(WebSocketState.connecting);

    try {
      String wsUrl = await _resolvedWsUrl;

      _channel = WebSocketChannel.connect(Uri.parse(wsUrl));

      // Wait for the WebSocket to be ready
      await _channel!.ready;

      // The server requires auth as the FIRST message within 10 seconds.
      final authToken = await _storage.read(key: 'auth_token');
      if (authToken != null) {
        _send({'type': 'auth', 'token': authToken});
      } else {
        debugPrint('WebSocket: No auth token available — sending anonymous auth');
        _send({'type': 'auth', 'token': ''});
      }

      // Listen for messages
      _channel!.stream.listen(
        _onMessage,
        onError: _onError,
        onDone: _onDone,
      );

      // We wait for auth_ok in _onMessage to confirm auth.
      _reconnectAttempts = 0;

      _startHeartbeat();
    } catch (e) {
      debugPrint('WebSocket connect error: $e');
      _setState(WebSocketState.error);
      _scheduleReconnect();
    }
  }

  void disconnect() {
    _heartbeatTimer?.cancel();
    _reconnectTimer?.cancel();
    _reconnectAttempts = _maxReconnectAttempts; // prevent reconnect
    _channel?.sink.close();
    _channel = null;
    _setState(WebSocketState.disconnected);
  }

  void _onMessage(dynamic rawData) {
    try {
      final json = jsonDecode(rawData as String) as Map<String, dynamic>;
      final message = WebSocketMessage.fromJson(json);

      _messageController.add(message);

      // Route to specific streams based on channel/type
      switch (message.type) {
        // ── Auth responses ───────────────────────────────────
        case 'auth_ok':
          debugPrint('WebSocket authenticated: user=${message.data['user_id']}');
          _setState(WebSocketState.connected);
          // Auto-subscribe to all channels after successful auth
          subscribeAll(['prices', 'trades', 'signals', 'system']);
          break;

        case 'auth_error':
          debugPrint('WebSocket auth error: ${message.data['detail']}');
          _setState(WebSocketState.error);
          break;

        // ── Broadcast channels (server → client) ─────────────
        case 'prices':
          _priceUpdateController.add(message.data);
          _portfolioUpdateController.add(message.data);
          break;
        case 'trades':
          _tradeUpdateController.add(message.data);
          break;
        case 'signals':
          _signalUpdateController.add(message.data);
          break;
        case 'system':
          _agentStatusController.add(message.data);
          debugPrint('System: ${message.data}');
          break;

        // ── Control messages ─────────────────────────────────
        case 'subscribed':
          debugPrint('WS subscribed: ${message.data}');
          break;
        case 'unsubscribed':
          debugPrint('WS unsubscribed: ${message.data}');
          break;

        // ── Server heartbeat → respond with pong ─────────────
        case 'heartbeat':
          _send({'type': 'pong'});
          break;

        case 'pong':
          // Response to our ping — connection is alive
          break;

        case 'error':
          debugPrint('WS server error: ${message.data}');
          break;

        default:
          debugPrint('Unknown WS message type: ${message.type}');
      }
    } catch (e) {
      debugPrint('WebSocket parse error: $e');
    }
  }

  void _onError(dynamic error) {
    debugPrint('WebSocket error: $error');
    _setState(WebSocketState.error);
    _scheduleReconnect();
  }

  void _onDone() {
    debugPrint('WebSocket closed');
    _heartbeatTimer?.cancel();
    if (_state != WebSocketState.disconnected && !_disposed) {
      _setState(WebSocketState.disconnected);
      _scheduleReconnect();
    }
  }

  void _startHeartbeat() {
    _heartbeatTimer?.cancel();
    _heartbeatTimer = Timer.periodic(_heartbeatInterval, (_) {
      if (_state == WebSocketState.connected) {
        _send({'type': 'ping'});
      }
    });
  }

  void _scheduleReconnect() {
    if (_reconnectAttempts >= _maxReconnectAttempts || _disposed) {
      debugPrint('Max reconnect attempts reached or disposed');
      return;
    }

    // Cap the delay at 60 seconds
    final delaySec =
        (_reconnectBaseDelay.inSeconds * (1 << _reconnectAttempts))
            .clamp(2, 60);
    final delay = Duration(seconds: delaySec);
    _reconnectAttempts++;

    _setState(WebSocketState.reconnecting);
    debugPrint(
        'Reconnecting in ${delay.inSeconds}s (attempt $_reconnectAttempts)');
    _reconnectTimer = Timer(delay, () {
      if (!_disposed) connect();
    });
  }

  /// Send a raw JSON message. Only sends if connected.
  void send(Map<String, dynamic> message) {
    if (_channel != null && _state == WebSocketState.connected) {
      _send(message);
    }
  }

  /// Internal send that doesn't check state (used for auth handshake).
  void _send(Map<String, dynamic> message) {
    try {
      _channel?.sink.add(jsonEncode(message));
    } catch (e) {
      debugPrint('WebSocket send error: $e');
    }
  }

  void subscribe(String channel) {
    send({'type': 'subscribe', 'channels': [channel]});
  }

  void subscribeAll(List<String> channels) {
    send({'type': 'subscribe', 'channels': channels});
  }

  void unsubscribe(String channel) {
    send({'type': 'unsubscribe', 'channels': [channel]});
  }

  void _setState(WebSocketState newState) {
    if (_state == newState) return;
    _state = newState;
    _stateController.add(newState);
  }

  void dispose() {
    _disposed = true;
    disconnect();
    _stateController.close();
    _messageController.close();
    _positionUpdateController.close();
    _signalUpdateController.close();
    _tradeUpdateController.close();
    _portfolioUpdateController.close();
    _priceUpdateController.close();
    _agentStatusController.close();
  }
}
