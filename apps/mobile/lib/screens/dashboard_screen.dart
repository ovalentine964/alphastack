import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../app.dart';
import '../widgets/portfolio_card.dart';
import '../widgets/position_tile.dart';
import '../widgets/signal_card.dart';
import '../models/trade.dart';
import '../models/signal.dart';

// Providers
final portfolioProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  // Mock data for initial build; replace with ApiService call
  await Future.delayed(const Duration(milliseconds: 500));
  return {
    'totalBalance': 125430.50,
    'totalEquity': 128750.25,
    'totalPnl': 3319.75,
    'totalPnlPercent': 2.72,
    'dayPnl': 542.30,
    'dayPnlPercent': 0.43,
    'activePositions': 5,
  };
});

final positionsProvider = FutureProvider<List<Position>>((ref) async {
  await Future.delayed(const Duration(milliseconds: 600));
  return [
    Position(
      symbol: 'BTC/USDT',
      side: TradeSide.long,
      entryPrice: 67250.00,
      currentPrice: 68120.50,
      quantity: 0.15,
      unrealizedPnl: 130.58,
      unrealizedPnlPercent: 1.29,
      stopLoss: 65500.00,
      takeProfit: 72000.00,
      openedAt: DateTime.now().subtract(const Duration(hours: 6)),
    ),
    Position(
      symbol: 'ETH/USDT',
      side: TradeSide.long,
      entryPrice: 3520.00,
      currentPrice: 3585.40,
      quantity: 2.5,
      unrealizedPnl: 163.50,
      unrealizedPnlPercent: 1.86,
      openedAt: DateTime.now().subtract(const Duration(hours: 12)),
    ),
    Position(
      symbol: 'SOL/USDT',
      side: TradeSide.short,
      entryPrice: 172.50,
      currentPrice: 168.20,
      quantity: 30,
      unrealizedPnl: 129.00,
      unrealizedPnlPercent: 2.49,
      openedAt: DateTime.now().subtract(const Duration(hours: 3)),
    ),
  ];
});

final recentSignalsProvider = FutureProvider<List<Signal>>((ref) async {
  await Future.delayed(const Duration(milliseconds: 700));
  return [
    Signal(
      id: 'sig-001',
      symbol: 'BTC/USDT',
      direction: SignalDirection.buy,
      status: SignalStatus.active,
      entryPrice: 67250.00,
      targetPrice: 72000.00,
      stopLoss: 65500.00,
      confluenceScore: 0.85,
      factors: ['RSI Oversold', 'Support Level', 'Volume Spike', 'EMA Cross'],
      strategy: 'Mean Reversion',
      timeframe: '4H',
      createdAt: DateTime.now().subtract(const Duration(hours: 2)),
    ),
    Signal(
      id: 'sig-002',
      symbol: 'SOL/USDT',
      direction: SignalDirection.sell,
      status: SignalStatus.active,
      entryPrice: 172.50,
      targetPrice: 155.00,
      stopLoss: 180.00,
      confluenceScore: 0.72,
      factors: ['Resistance Rejection', 'Bearish Divergence', 'High RSI'],
      strategy: 'Breakdown',
      timeframe: '1H',
      createdAt: DateTime.now().subtract(const Duration(hours: 1)),
    ),
  ];
});

class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final portfolio = ref.watch(portfolioProvider);
    final positions = ref.watch(positionsProvider);
    final signals = ref.watch(recentSignalsProvider);

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
              child: const Icon(Icons.auto_graph_rounded, size: 20, color: Colors.white),
            ),
            const SizedBox(width: 10),
            const Text('AlphaStack'),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.notifications_outlined),
            onPressed: () {},
          ),
          IconButton(
            icon: const Icon(Icons.sync_rounded),
            onPressed: () {
              ref.invalidate(portfolioProvider);
              ref.invalidate(positionsProvider);
              ref.invalidate(recentSignalsProvider);
            },
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(portfolioProvider);
          ref.invalidate(positionsProvider);
          ref.invalidate(recentSignalsProvider);
        },
        color: AlphaStackApp.accentBlue,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            // Portfolio Card
            portfolio.when(
              data: (data) => PortfolioCard(
                totalBalance: data['totalBalance'] as double,
                totalEquity: data['totalEquity'] as double,
                totalPnl: data['totalPnl'] as double,
                totalPnlPercent: data['totalPnlPercent'] as double,
                dayPnl: data['dayPnl'] as double,
                dayPnlPercent: data['dayPnlPercent'] as double,
                activePositions: data['activePositions'] as int,
              ),
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
                  children:
                      data.map((sig) => SignalCard(signal: sig)).toList(),
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
          const Icon(Icons.error_outline, color: AlphaStackApp.accentRed, size: 32),
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
                size: 40, color: AlphaStackApp.textSecondary.withAlpha(128)),
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
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
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
