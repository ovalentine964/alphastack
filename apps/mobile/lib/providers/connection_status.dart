import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/api_service.dart';

/// Connection lifecycle: disconnected → connecting → authenticated
enum AppConnectionState { disconnected, connecting, authenticated }

/// State class that holds connection info.
class ConnectionStatus {
  final AppConnectionState state;
  final String message;
  final bool isHealthy;

  const ConnectionStatus({
    required this.state,
    required this.message,
    this.isHealthy = false,
  });

  ConnectionStatus copyWith({
    AppConnectionState? state,
    String? message,
    bool? isHealthy,
  }) {
    return ConnectionStatus(
      state: state ?? this.state,
      message: message ?? this.message,
      isHealthy: isHealthy ?? this.isHealthy,
    );
  }

  bool get isConnected => state == AppConnectionState.authenticated;
  bool get isConnecting => state == AppConnectionState.connecting;
  bool get isDisconnected => state == AppConnectionState.disconnected;
}

/// Notifier that manages the app connection lifecycle.
class ConnectionStatusNotifier extends StateNotifier<ConnectionStatus> {
  final ApiService _api;
  Timer? _healthTimer;

  ConnectionStatusNotifier(this._api)
      : super(const ConnectionStatus(
          state: AppConnectionState.disconnected,
          message: 'Not connected',
        ));

  /// Check health and authenticate if needed.
  Future<void> connect() async {
    state = state.copyWith(
      state: AppConnectionState.connecting,
      message: 'Connecting...',
    );

    try {
      // Step 1: Check backend health
      final healthy = await _api.checkHealth();
      if (!healthy) {
        state = const ConnectionStatus(
          state: AppConnectionState.disconnected,
          message: 'Backend unreachable',
          isHealthy: false,
        );
        return;
      }

      // Step 2: Check if we already have a valid token
      final keys = await _api.getStoredApiKeys();
      final hasToken = (await _api.getBinanceApiKey()) != null;

      // Step 3: Authenticate (with stored keys or demo credentials)
      state = state.copyWith(
        state: AppConnectionState.connecting,
        message: 'Authenticating...',
        isHealthy: true,
      );

      final authSuccess = await _api.autoAuthenticate();

      if (authSuccess) {
        state = const ConnectionStatus(
          state: AppConnectionState.authenticated,
          message: 'Connected',
          isHealthy: true,
        );
      } else {
        state = const ConnectionStatus(
          state: AppConnectionState.disconnected,
          message: 'Authentication failed',
          isHealthy: true,
        );
      }
    } catch (e) {
      state = ConnectionStatus(
        state: AppConnectionState.disconnected,
        message: 'Connection error: $e',
        isHealthy: false,
      );
    }
  }

  /// Disconnect and clear auth state.
  Future<void> disconnect() async {
    await _api.clearAuth();
    state = const ConnectionStatus(
      state: AppConnectionState.disconnected,
      message: 'Disconnected',
    );
  }

  /// Start periodic health checks (every 30 seconds).
  void startHealthMonitor() {
    _healthTimer?.cancel();
    _healthTimer = Timer.periodic(const Duration(seconds: 30), (_) async {
      if (state.state == AppConnectionState.authenticated) {
        final healthy = await _api.checkHealth();
        if (!healthy) {
          state = state.copyWith(
            state: AppConnectionState.disconnected,
            message: 'Connection lost',
            isHealthy: false,
          );
        }
      }
    });
  }

  void stopHealthMonitor() {
    _healthTimer?.cancel();
    _healthTimer = null;
  }

  @override
  void dispose() {
    stopHealthMonitor();
    super.dispose();
  }
}

/// Global connection status provider.
final connectionStateProvider =
    StateNotifierProvider<ConnectionStatusNotifier, ConnectionStatus>((ref) {
  final notifier = ConnectionStatusNotifier(ApiService());
  // Auto-connect on creation
  notifier.connect();
  notifier.startHealthMonitor();
  ref.onDispose(() {
    notifier.stopHealthMonitor();
  });
  return notifier;
});
