import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../app.dart';
import '../services/api_service.dart';
import '../services/websocket_service.dart';
import '../providers/connection_status.dart';
import '../widgets/portfolio_card.dart';
import '../widgets/position_tile.dart';
import '../widgets/signal_card.dart';
import '../models/trade.dart';
import '../models/signal.dart';

// ─── Providers ───────────────────────────────────────────────────────────────

/// Portfolio P&L summary from the backend.
final portfolioProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  return await ApiService().getPortfolioSummary();
});

/// Active positions from the backend.
final positionsProvider = FutureProvider<List<Position>>((ref) async {
  return await ApiService().getActivePositions();
});

/// Active signals from the backend.
final recentSignalsProvider = FutureProvider<List<Signal>>((ref) async {
  return await ApiService().getActiveSignals();
});

/// Testnet mode flag.
final testnetModeProvider = FutureProvider<bool>((ref) async {
  return await ApiService().isTestnet();
});

// ─── Dashboard Screen ────────────────────────────────────────────────────────

class DashboardScreen extends ConsumerStatefulWidget {
  const DashboardScreen({super.key});

  @override
  ConsumerState<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends ConsumerState<DashboardScreen> {
  final _ws = WebSocketService();
  StreamSubscription? _wsStateSub;
  StreamSubscription? _tradeSub;
  StreamSubscription? _signalSub;

  @override
  void initState() {
    super.initState();
    // Connect WebSocket for real-time updates
    _connectWebSocket();
  }

  Future<void> _connectWebSocket() async {
    // Only connect if we have auth token
    final api = ApiService();
    final keys = await api.getStoredApiKeys();
    if (keys['binanceApiKey'] == null) return;

    await _ws.connect();

    // Listen for trade updates → refresh trades/positions
    _tradeSub = _ws.tradeUpdates.listen((_) {
      if (mounted) {
        ref.invalidate(positionsProvider);
        ref.invalidate(portfolioProvider);
      }
    });

    // Listen for signal updates → refresh signals
    _signalSub = _ws.signalUpdates.listen((_) {
      if (mounted) {
        ref.invalidate(recentSignalsProvider);
      }
    });
  }

  @override
  void dispose() {
    _wsStateSub?.cancel();
    _tradeSub?.cancel();
    _signalSub?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final portfolio = ref.watch(portfolioProvider);
    final positions = ref.watch(positionsProvider);
    final signals = ref.watch(recentSignalsProvider);
    final testnet = ref.watch(testnetModeProvider);

    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            Container(
              width: 32,
              height: 32,
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [AlphaStackApp.accentBlue, AlphaStackApp.accentGreen],
                ),
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Icon(Icons.auto_graph_rounded,
                  size: 20, color: Colors.white),
            ),
            const SizedBox(width: 10),
            const Text('AlphaStack'),
          ],
        ),
        actions: [
          // Testnet / Live badge
          testnet.when(
            data: (isTest) => Container(
              margin: const EdgeInsets.only(right: 4),
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: isTest
                    ? AlphaStackApp.accentOrange.withAlpha(30)
                    : AlphaStackApp.accentRed.withAlpha(30),
                borderRadius: BorderRadius.circular(6),
                border: Border.all(
                  color: isTest
                      ? AlphaStackApp.accentOrange.withAlpha(80)
                      : AlphaStackApp.accentRed.withAlpha(80),
                ),
              ),
              child: Text(
                isTest ? 'TESTNET' : 'LIVE',
                style: TextStyle(
                  fontSize: 10,
                  fontWeight: FontWeight.w700,
                  color: isTest
                      ? AlphaStackApp.accentOrange
                      : AlphaStackApp.accentRed,
                  letterSpacing: 1,
                ),
              ),
            ),
            loading: () => const SizedBox.shrink(),
            error: (_, __) => const SizedBox.shrink(),
          ),
          // WebSocket connection indicator
          const _WsConnectionIndicator(),
          // Offline indicator
          const _OfflineIndicator(),
          // Connection status dot
          const _ConnectionDot(),
          const SizedBox(width: 4),
          const _NotificationButton(),
          _RefreshButton(),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(portfolioProvider);
          ref.invalidate(positionsProvider);
          ref.invalidate(recentSignalsProvider);
          ref.invalidate(testnetModeProvider);
          ApiService().clearCache();
        },
        color: AlphaStackApp.accentBlue,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            // Connection status banner
            const _ConnectionBanner(),
            // Offline banner
            if (ApiService().isOffline) _buildOfflineBanner(),

            // Portfolio Card
            portfolio.when(
              data: (data) => _buildPortfolioFromApi(data),
              loading: () => _buildSkeletonCard(height: 200),
              error: (e, _) => _buildErrorCard('Portfolio', e),
            ),
            const SizedBox(height: 24),

            // Active Positions
            _SectionHeader(
              title: 'Active Positions',
              count: positions.valueOrNull?.length,
              onViewAll: () {},
            ),
            const SizedBox(height: 8),
            positions.when(
              data: (data) {
                if (data.isEmpty) {
                  return _buildEmptyState('No active positions');
                }
                return Container(
                  decoration: BoxDecoration(
                    color: AlphaStackApp.cardDark,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AlphaStackApp.borderDark),
                  ),
                  child: Column(
                    children: data
                        .map((pos) => PositionTile(position: pos))
                        .toList(),
                  ),
                );
              },
              loading: () => _buildSkeletonList(count: 3),
              error: (e, _) => _buildErrorCard('Positions', e),
            ),
            const SizedBox(height: 24),

            // Recent Signals
            _SectionHeader(
              title: 'Recent Signals',
              count: signals.valueOrNull?.length,
              onViewAll: () {},
            ),
            const SizedBox(height: 8),
            signals.when(
              data: (data) {
                if (data.isEmpty) {
                  return _buildEmptyState('No active signals');
                }
                return Column(
                  children: data
                      .take(3)
                      .map((sig) => SignalCard(signal: sig))
                      .toList(),
                );
              },
              loading: () => _buildSkeletonList(count: 2),
              error: (e, _) => _buildErrorCard('Signals', e),
            ),
            const SizedBox(height: 80),
          ],
        ),
      ),
    );
  }

  Widget _buildPortfolioFromApi(Map<String, dynamic> data) {
    // Server PnL response has different field names than the old mock
    final totalRealized = (data['total_realized_pnl'] as num?)?.toDouble() ?? 0;
    final totalUnrealized =
        (data['total_unrealized_pnl'] as num?)?.toDouble() ?? 0;
    final totalPnl = (data['total_pnl'] as num?)?.toDouble() ?? 0;
    final todayPnl = (data['today_pnl'] as num?)?.toDouble() ?? 0;
    final totalTrades = (data['total_trades'] as num?)?.toInt() ?? 0;

    // Estimate balance from PnL (server doesn't provide balance directly)
    // In a real app, this would come from the broker API
    const baseBalance = 100000.0;
    final totalBalance = baseBalance + totalPnl;
    final totalEquity = totalBalance + totalUnrealized;
    final totalPnlPct =
        baseBalance > 0 ? (totalPnl / baseBalance) * 100 : 0.0;
    final dayPnlPct =
        baseBalance > 0 ? (todayPnl / baseBalance) * 100 : 0.0;

    return PortfolioCard(
      totalBalance: totalBalance,
      totalEquity: totalEquity,
      totalPnl: totalPnl,
      totalPnlPercent: totalPnlPct,
      dayPnl: todayPnl,
      dayPnlPercent: dayPnlPct,
      activePositions: totalTrades,
    );
  }

  Widget _buildOfflineBanner() {
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AlphaStackApp.accentOrange.withAlpha(20),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AlphaStackApp.accentOrange.withAlpha(80)),
      ),
      child: const Row(
        children: [
          Icon(Icons.cloud_off_rounded, color: AlphaStackApp.accentOrange, size: 20),
          SizedBox(width: 10),
          Expanded(
            child: Text(
              'Offline — showing cached data',
              style: TextStyle(
                color: AlphaStackApp.accentOrange,
                fontSize: 13,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSkeletonCard({double height = 100}) {
    return Container(
      height: height,
      decoration: BoxDecoration(
        color: AlphaStackApp.cardDark,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AlphaStackApp.borderDark),
      ),
      child: const Center(
        child: CircularProgressIndicator(
          color: AlphaStackApp.accentBlue,
          strokeWidth: 2,
        ),
      ),
    );
  }

  Widget _buildSkeletonList({int count = 3}) {
    return Column(
      children: List.generate(count, (i) {
        return Container(
          margin: const EdgeInsets.only(bottom: 8),
          height: 64,
          decoration: BoxDecoration(
            color: AlphaStackApp.cardDark,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: AlphaStackApp.borderDark),
          ),
        );
      }),
    );
  }

  Widget _buildErrorCard(String label, Object error) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AlphaStackApp.cardDark,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AlphaStackApp.accentRed.withAlpha(80)),
      ),
      child: Column(
        children: [
          const Icon(Icons.error_outline,
              color: AlphaStackApp.accentRed, size: 32),
          const SizedBox(height: 8),
          Text(
            'Failed to load $label',
            style: const TextStyle(color: AlphaStackApp.textPrimary),
          ),
          const SizedBox(height: 4),
          Text(
            error.toString(),
            style: const TextStyle(
              color: AlphaStackApp.textSecondary,
              fontSize: 12,
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 12),
          TextButton.icon(
            onPressed: () {
              ref.invalidate(portfolioProvider);
              ref.invalidate(positionsProvider);
              ref.invalidate(recentSignalsProvider);
            },
            icon: const Icon(Icons.refresh, size: 16),
            label: const Text('Retry'),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyState(String message) {
    return Container(
      padding: const EdgeInsets.all(32),
      decoration: BoxDecoration(
        color: AlphaStackApp.cardDark,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AlphaStackApp.borderDark),
      ),
      child: Center(
        child: Column(
          children: [
            Icon(Icons.inbox_outlined,
                size: 40,
                color: AlphaStackApp.textSecondary.withAlpha(128)),
            const SizedBox(height: 8),
            Text(
              message,
              style: const TextStyle(color: AlphaStackApp.textSecondary),
            ),
          ],
        ),
      ),
    );
  }
}

// ─── Widgets ─────────────────────────────────────────────────────────────────

class _SectionHeader extends StatelessWidget {
  final String title;
  final int? count;
  final VoidCallback? onViewAll;

  const _SectionHeader({
    required this.title,
    this.count,
    this.onViewAll,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Row(
          children: [
            Text(
              title,
              style: theme.textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
            if (count != null) ...[
              const SizedBox(width: 8),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: AlphaStackApp.accentBlue.withAlpha(30),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  '$count',
                  style: const TextStyle(
                    color: AlphaStackApp.accentBlue,
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
          ],
        ),
        if (onViewAll != null)
          TextButton(
            onPressed: onViewAll,
            child: const Text('View All'),
          ),
      ],
    );
  }
}

/// WebSocket connection state indicator in the app bar.
class _WsConnectionIndicator extends StatefulWidget {
  const _WsConnectionIndicator();

  @override
  State<_WsConnectionIndicator> createState() => _WsConnectionIndicatorState();
}

class _WsConnectionIndicatorState extends State<_WsConnectionIndicator> {
  final _ws = WebSocketService();
  WebSocketState _wsState = WebSocketState.disconnected;
  StreamSubscription? _sub;

  @override
  void initState() {
    super.initState();
    _wsState = _ws.state;
    _sub = _ws.stateStream.listen((state) {
      if (mounted) setState(() => _wsState = state);
    });
  }

  @override
  void dispose() {
    _sub?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    Color color;
    String tooltip;

    switch (_wsState) {
      case WebSocketState.connected:
        color = AlphaStackApp.accentGreen;
        tooltip = 'Live data connected';
        break;
      case WebSocketState.connecting:
      case WebSocketState.reconnecting:
        color = AlphaStackApp.accentOrange;
        tooltip = 'Reconnecting...';
        break;
      case WebSocketState.error:
        color = AlphaStackApp.accentRed;
        tooltip = 'Connection error';
        break;
      case WebSocketState.disconnected:
        color = AlphaStackApp.textSecondary;
        tooltip = 'Disconnected';
        break;
    }

    return Tooltip(
      message: tooltip,
      child: Container(
        width: 10,
        height: 10,
        margin: const EdgeInsets.symmetric(vertical: 18),
        decoration: BoxDecoration(
          color: color,
          shape: BoxShape.circle,
          boxShadow: [
            BoxShadow(
              color: color.withAlpha(100),
              blurRadius: 4,
              spreadRadius: 1,
            ),
          ],
        ),
      ),
    );
  }
}

/// Connection status dot (green/red/yellow).
class _ConnectionDot extends ConsumerWidget {
  const _ConnectionDot();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final status = ref.watch(connectionStatusProvider);
    Color color;
    switch (status) {
      case ConnectionStatus.connected:
        color = AlphaStackApp.accentGreen;
        break;
      case ConnectionStatus.connecting:
      case ConnectionStatus.authenticated:
        color = AlphaStackApp.accentOrange;
        break;
      case ConnectionStatus.disconnected:
      case ConnectionStatus.error:
        color = AlphaStackApp.accentRed;
        break;
    }
    return Container(
      width: 8,
      height: 8,
      decoration: BoxDecoration(
        color: color,
        shape: BoxShape.circle,
      ),
    );
  }
}

/// Connection banner at top of dashboard.
class _ConnectionBanner extends ConsumerWidget {
  const _ConnectionBanner();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final status = ref.watch(connectionStatusProvider);
    if (status == ConnectionStatus.connected || status == ConnectionStatus.authenticated) {
      return const SizedBox.shrink();
    }
    Color bgColor;
    Color textColor;
    String text;
    IconData icon;
    switch (status) {
      case ConnectionStatus.disconnected:
        bgColor = AlphaStackApp.accentRed.withAlpha(20);
        textColor = AlphaStackApp.accentRed;
        text = 'Disconnected — set API endpoint in Settings';
        icon = Icons.cloud_off;
        break;
      case ConnectionStatus.connecting:
        bgColor = AlphaStackApp.accentOrange.withAlpha(20);
        textColor = AlphaStackApp.accentOrange;
        text = 'Connecting...';
        icon = Icons.sync;
        break;
      case ConnectionStatus.error:
        bgColor = AlphaStackApp.accentRed.withAlpha(20);
        textColor = AlphaStackApp.accentRed;
        text = 'Connection error — check your settings';
        icon = Icons.error_outline;
        break;
      default:
        return const SizedBox.shrink();
    }
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: textColor.withAlpha(80)),
      ),
      child: Row(
        children: [
          Icon(icon, color: textColor, size: 20),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              text,
              style: TextStyle(
                color: textColor,
                fontSize: 13,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
          TextButton(
            onPressed: () {
              // Navigate to settings
            },
            child: Text('Settings', style: TextStyle(color: textColor)),
          ),
        ],
      ),
    );
  }
}

/// Offline state indicator.
class _OfflineIndicator extends StatelessWidget {
  const _OfflineIndicator();

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<bool>(
      stream: ApiService().offlineStream,
      initialData: ApiService().isOffline,
      builder: (context, snapshot) {
        final isOffline = snapshot.data ?? false;
        if (!isOffline) return const SizedBox.shrink();
        return Tooltip(
          message: 'Offline — showing cached data',
          child: Container(
            margin: const EdgeInsets.symmetric(vertical: 16, horizontal: 4),
            child: const Icon(
              Icons.cloud_off_rounded,
              color: AlphaStackApp.accentOrange,
              size: 18,
            ),
          ),
        );
      },
    );
  }
}

class _NotificationButton extends StatelessWidget {
  const _NotificationButton();

  @override
  Widget build(BuildContext context) {
    return IconButton(
      icon: const Icon(Icons.notifications_outlined),
      onPressed: () {},
    );
  }
}

class _RefreshButton extends ConsumerWidget {
  const _RefreshButton();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return IconButton(
      icon: const Icon(Icons.sync_rounded),
      onPressed: () {
        ref.invalidate(portfolioProvider);
        ref.invalidate(positionsProvider);
        ref.invalidate(recentSignalsProvider);
        ref.invalidate(testnetModeProvider);
        ApiService().clearCache();
      },
    );
  }
}
