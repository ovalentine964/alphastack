import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../app.dart';
import '../widgets/signal_card.dart';
import '../models/signal.dart';

final signalsListProvider = FutureProvider<List<Signal>>((ref) async {
  await Future.delayed(const Duration(milliseconds: 600));
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
      confidence: 0.82,
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
      confidence: 0.68,
      createdAt: DateTime.now().subtract(const Duration(hours: 1)),
    ),
    Signal(
      id: 'sig-003',
      symbol: 'ETH/USDT',
      direction: SignalDirection.buy,
      status: SignalStatus.active,
      entryPrice: 3520.00,
      targetPrice: 3850.00,
      stopLoss: 3400.00,
      confluenceScore: 0.91,
      factors: [
        'Golden Cross',
        'Bullish Engulfing',
        'Support Bounce',
        'Volume Confirmation',
        'MACD Cross'
      ],
      strategy: 'Trend Following',
      timeframe: '1D',
      confidence: 0.88,
      createdAt: DateTime.now().subtract(const Duration(minutes: 45)),
    ),
    Signal(
      id: 'sig-004',
      symbol: 'AVAX/USDT',
      direction: SignalDirection.buy,
      status: SignalStatus.active,
      entryPrice: 38.50,
      targetPrice: 45.00,
      stopLoss: 35.80,
      confluenceScore: 0.63,
      factors: ['Ascending Triangle', 'Increasing Volume'],
      strategy: 'Breakout',
      timeframe: '4H',
      confidence: 0.59,
      createdAt: DateTime.now().subtract(const Duration(hours: 4)),
    ),
    Signal(
      id: 'sig-005',
      symbol: 'LINK/USDT',
      direction: SignalDirection.sell,
      status: SignalStatus.expired,
      entryPrice: 16.80,
      targetPrice: 14.50,
      stopLoss: 17.50,
      confluenceScore: 0.55,
      factors: ['Double Top', 'RSI Overbought'],
      strategy: 'Reversal',
      timeframe: '4H',
      confidence: 0.52,
      createdAt: DateTime.now().subtract(const Duration(hours: 8)),
      expiresAt: DateTime.now().subtract(const Duration(hours: 2)),
    ),
  ];
});

enum SignalFilter { all, buy, sell, highConfluence }

final signalFilterProvider =
    StateProvider<SignalFilter>((ref) => SignalFilter.all);

class SignalsScreen extends ConsumerWidget {
  const SignalsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final signals = ref.watch(signalsListProvider);
    final filter = ref.watch(signalFilterProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Signals'),
        actions: [
          IconButton(
            icon: const Icon(Icons.tune_rounded),
            onPressed: () {},
          ),
        ],
      ),
      body: signals.when(
        data: (data) {
          final active = data.where((s) => s.isActive).toList();
          final filtered = _applyFilter(active, filter);

          return Column(
            children: [
              // Summary cards
              _buildSummary(data, active),
              // Filters
              _buildFilters(context, ref, filter),
              // Signal list
              Expanded(
                child: filtered.isEmpty
                    ? Center(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(Icons.signal_cellular_off,
                                size: 48,
                                color: AlphaStackApp.textSecondary.withAlpha(100)),
                            const SizedBox(height: 12),
                            Text(
                              'No signals match filter',
                              style: theme.textTheme.bodyMedium,
                            ),
                          ],
                        ),
                      )
                    : ListView.builder(
                        padding: const EdgeInsets.fromLTRB(16, 8, 16, 80),
                        itemCount: filtered.length,
                        itemBuilder: (context, index) {
                          return SignalCard(signal: filtered[index]);
                        },
                      ),
              ),
            ],
          );
        },
        loading: () => const Center(
          child: CircularProgressIndicator(color: AlphaStackApp.accentBlue),
        ),
        error: (e, _) => Center(
          child: Text('Error: $e'),
        ),
      ),
    );
  }

  Widget _buildSummary(List<Signal> all, List<Signal> active) {
    final highConf = active.where((s) => s.confluenceScore >= 0.7).length;
    final avgScore = active.isEmpty
        ? 0.0
        : active.fold<double>(0, (sum, s) => sum + s.confluenceScore) /
            active.length;

    return Container(
      margin: const EdgeInsets.fromLTRB(16, 8, 16, 0),
      child: Row(
        children: [
          _SummaryChip(
            label: 'Active',
            value: '${active.length}',
            color: AlphaStackApp.accentBlue,
          ),
          const SizedBox(width: 8),
          _SummaryChip(
            label: 'High Conf',
            value: '$highConf',
            color: AlphaStackApp.accentGreen,
          ),
          const SizedBox(width: 8),
          _SummaryChip(
            label: 'Avg Score',
            value: '${(avgScore * 100).toStringAsFixed(0)}%',
            color: AlphaStackApp.accentOrange,
          ),
        ],
      ),
    );
  }

  Widget _buildFilters(
      BuildContext context, WidgetRef ref, SignalFilter current) {
    return SizedBox(
      height: 50,
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        children: SignalFilter.values.map((f) {
          final isActive = f == current;
          return Padding(
            padding: const EdgeInsets.symmetric(horizontal: 4),
            child: FilterChip(
              selected: isActive,
              label: Text(_filterLabel(f)),
              onSelected: (_) =>
                  ref.read(signalFilterProvider.notifier).state = f,
              selectedColor: AlphaStackApp.accentBlue.withAlpha(40),
              checkmarkColor: AlphaStackApp.accentBlue,
              labelStyle: TextStyle(
                color: isActive
                    ? AlphaStackApp.accentBlue
                    : AlphaStackApp.textSecondary,
                fontSize: 12,
                fontWeight: isActive ? FontWeight.w600 : FontWeight.normal,
              ),
              side: BorderSide(
                color: isActive
                    ? AlphaStackApp.accentBlue
                    : AlphaStackApp.borderDark,
              ),
              backgroundColor: AlphaStackApp.cardDark,
            ),
          );
        }).toList(),
      ),
    );
  }

  List<Signal> _applyFilter(List<Signal> signals, SignalFilter filter) {
    switch (filter) {
      case SignalFilter.all:
        return signals;
      case SignalFilter.buy:
        return signals.where((s) => s.isBuy).toList();
      case SignalFilter.sell:
        return signals.where((s) => !s.isBuy).toList();
      case SignalFilter.highConfluence:
        return signals.where((s) => s.confluenceScore >= 0.7).toList();
    }
  }

  String _filterLabel(SignalFilter f) {
    switch (f) {
      case SignalFilter.all:
        return 'All';
      case SignalFilter.buy:
        return 'Buy / Long';
      case SignalFilter.sell:
        return 'Sell / Short';
      case SignalFilter.highConfluence:
        return 'High Confluence';
    }
  }
}

class _SummaryChip extends StatelessWidget {
  final String label;
  final String value;
  final Color color;

  const _SummaryChip({
    required this.label,
    required this.value,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 12),
        decoration: BoxDecoration(
          color: AlphaStackApp.cardDark,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: AlphaStackApp.borderDark),
        ),
        child: Column(
          children: [
            Text(
              value,
              style: theme.textTheme.titleLarge?.copyWith(
                color: color,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 2),
            Text(
              label,
              style: theme.textTheme.bodySmall?.copyWith(
                color: AlphaStackApp.textSecondary,
                fontSize: 11,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
