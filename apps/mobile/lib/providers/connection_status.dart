import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/api_service.dart';

/// Connection lifecycle states.
enum ConnectionStatus { disconnected, connecting, authenticated, connected, error }

/// State class that holds connection info.
class ConnectionInfo {
  final ConnectionStatus state;
  final String message;
  final bool isHealthy;

  const ConnectionInfo({
    required this.state,
    required this.message,
    this.isHealthy = false,
  });

  ConnectionInfo copyWith({
    ConnectionStatus? state,
    String? message,
    bool? isHealthy,
  }) {
    return ConnectionInfo(
      state: state ?? this.state,
      message: message ?? this.message,
      isHealthy: isHealthy ?? this.isHealthy,
    );
  }

  bool get isConnected => state == ConnectionStatus.authenticated || state == ConnectionStatus.connected;
  bool get isConnecting => state == ConnectionStatus.connecting;
  bool get isDisconnected => state == ConnectionStatus.disconnected;
}

/// Notifier that manages the app connection lifecycle.
class ConnectionStatusNotifier extends StateNotifier<ConnectionInfo> {
  final ApiService _api;
  Timer? _healthTimer;

  ConnectionStatusNotifier(this._api)
      : super(const ConnectionInfo(
          state: ConnectionStatus.disconnected,
          message: 'Not connected',
        ));

  /// Check health and authenticate if needed.
  Future<void> connect() async {
    state = state.copyWith(
      state: ConnectionStatus.connecting,
      message: 'Connecting...',
    );

    try {
      // Step 1: Check backend health
      final healthy = await _api.checkHealth();
      if (!healthy) {
        state = const ConnectionInfo(
          state: ConnectionStatus.disconnected,
          message: 'Backend unreachable',
          isHealthy: false,
        );
        return;
      }

      // Step 2: Authenticate (with stored keys or demo credentials)
      state = state.copyWith(
        state: ConnectionStatus.connecting,
        message: 'Authenticating...',
        isHealthy: true,
      );

      final authSuccess = await _api.autoAuthenticate();

      if (authSuccess) {
        state = const ConnectionInfo(
          state: ConnectionStatus.authenticated,
          message: 'Connected',
          isHealthy: true,
        );
      } else {
        // Auth failed but backend is healthy — stay connected in read-only mode
        state = const ConnectionInfo(
          state: ConnectionStatus.connected,
          message: 'Connected (demo mode)',
          isHealthy: true,
        );
      }
    } catch (e) {
      state = ConnectionInfo(
        state: ConnectionStatus.disconnected,
        message: 'Connection error: $e',
        isHealthy: false,
      );
    }
  }

  /// Disconnect and clear auth state.
  Future<void> disconnect() async {
    await _api.clearAuth();
    state = const ConnectionInfo(
      state: ConnectionStatus.disconnected,
      message: 'Disconnected',
    );
  }

  /// Start periodic health checks (every 30 seconds).
  void startHealthMonitor() {
    _healthTimer?.cancel();
    _healthTimer = Timer.periodic(const Duration(seconds: 30), (_) async {
      if (state.state == ConnectionStatus.authenticated) {
        final healthy = await _api.checkHealth();
        if (!healthy) {
          state = state.copyWith(
            state: ConnectionStatus.disconnected,
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
final connectionStatusProvider =
    StateNotifierProvider<ConnectionStatusNotifier, ConnectionInfo>((ref) {
  final notifier = ConnectionStatusNotifier(ApiService());
  // Auto-connect on creation
  notifier.connect();
  notifier.startHealthMonitor();
  ref.onDispose(() {
    notifier.stopHealthMonitor();
  });
  return notifier;
});
