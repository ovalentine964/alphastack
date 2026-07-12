import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

enum WebSocketState { disconnected, connecting, connected, error }

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
    return WebSocketMessage(
      type: json['type'] as String? ?? 'unknown',
      data: json['data'] as Map<String, dynamic>? ?? {},
      timestamp: json['timestamp'] != null
          ? DateTime.parse(json['timestamp'] as String)
          : DateTime.now(),
    );
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
  static const Duration _heartbeatInterval = Duration(seconds: 30);
  static const Duration _reconnectBaseDelay = Duration(seconds: 2);

  // Stream controllers
  final _stateController = StreamController<WebSocketState>.broadcast();
  final _messageController = StreamController<WebSocketMessage>.broadcast();
  final _positionUpdateController = StreamController<Map<String, dynamic>>.broadcast();
  final _signalUpdateController = StreamController<Map<String, dynamic>>.broadcast();
  final _tradeUpdateController = StreamController<Map<String, dynamic>>.broadcast();
  final _portfolioUpdateController = StreamController<Map<String, dynamic>>.broadcast();

  // Public streams
  Stream<WebSocketState> get stateStream => _stateController.stream;
  Stream<WebSocketMessage> get messageStream => _messageController.stream;
  Stream<Map<String, dynamic>> get positionUpdates => _positionUpdateController.stream;
  Stream<Map<String, dynamic>> get signalUpdates => _signalUpdateController.stream;
  Stream<Map<String, dynamic>> get tradeUpdates => _tradeUpdateController.stream;
  Stream<Map<String, dynamic>> get portfolioUpdates => _portfolioUpdateController.stream;

  WebSocketState get state => _state;
  bool get isConnected => _state == WebSocketState.connected;

  // Singleton
  static final WebSocketService _instance = WebSocketService._internal();
  factory WebSocketService() => _instance;
  WebSocketService._internal();

  Future<void> connect() async {
    if (_state == WebSocketState.connected || _state == WebSocketState.connecting) {
      return;
    }

    _setState(WebSocketState.connecting);

    try {
      String wsUrl = await _storage.read(key: _wsUrlKey) ?? _defaultWsUrl;
      final authToken = await _storage.read(key: 'auth_token');

      if (authToken != null) {
        final separator = wsUrl.contains('?') ? '&' : '?';
        wsUrl = '${wsUrl}${separator}token=$authToken';
      }

      _channel = WebSocketChannel.connect(Uri.parse(wsUrl));

      await _channel!.ready;

      _setState(WebSocketState.connected);
      _reconnectAttempts = 0;

      _channel!.stream.listen(
        _onMessage,
        onError: _onError,
        onDone: _onDone,
      );

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

      // Route to specific streams
      switch (message.type) {
        case 'position_update':
        case 'position_opened':
        case 'position_closed':
          _positionUpdateController.add(message.data);
          break;
        case 'signal_new':
        case 'signal_update':
        case 'signal_expired':
          _signalUpdateController.add(message.data);
          break;
        case 'trade_executed':
        case 'trade_updated':
          _tradeUpdateController.add(message.data);
          break;
        case 'portfolio_update':
          _portfolioUpdateController.add(message.data);
          break;
        case 'pong':
          // Heartbeat response, ignore
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
    if (_state != WebSocketState.disconnected) {
      _setState(WebSocketState.disconnected);
      _scheduleReconnect();
    }
  }

  void _startHeartbeat() {
    _heartbeatTimer?.cancel();
    _heartbeatTimer = Timer.periodic(_heartbeatInterval, (_) {
      send({'type': 'ping'});
    });
  }

  void _scheduleReconnect() {
    if (_reconnectAttempts >= _maxReconnectAttempts) {
      debugPrint('Max reconnect attempts reached');
      return;
    }

    final delay = _reconnectBaseDelay * (1 << _reconnectAttempts);
    _reconnectAttempts++;

    debugPrint('Reconnecting in ${delay.inSeconds}s (attempt $_reconnectAttempts)');
    _reconnectTimer = Timer(delay, connect);
  }

  void send(Map<String, dynamic> message) {
    if (_channel != null && _state == WebSocketState.connected) {
      _channel!.sink.add(jsonEncode(message));
    }
  }

  void subscribe(String channel) {
    send({'type': 'subscribe', 'channel': channel});
  }

  void unsubscribe(String channel) {
    send({'type': 'unsubscribe', 'channel': channel});
  }

  void _setState(WebSocketState newState) {
    _state = newState;
    _stateController.add(newState);
  }

  void dispose() {
    disconnect();
    _stateController.close();
    _messageController.close();
    _positionUpdateController.close();
    _signalUpdateController.close();
    _tradeUpdateController.close();
    _portfolioUpdateController.close();
  }
}
