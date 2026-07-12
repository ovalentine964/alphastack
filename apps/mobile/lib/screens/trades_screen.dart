import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import '../app.dart';
import '../models/trade.dart';

final tradesProvider = FutureProvider<List<Trade>>((ref) async {
  await Future.delayed(const Duration(milliseconds: 600));
  return [
    Trade(
      id: 't-001',
      symbol: 'BTC/USDT',
      side: TradeSide.long,
      status: TradeStatus.closed,
      entryPrice: 65200.00,
      exitPrice: 67800.00,
      quantity: 0.2,
      pnl: 520.00,
      pnlPercent: 3.99,
      strategy: 'Trend Following',
      openedAt: DateTime.now().subtract(const Duration(days: 2)),
      closedAt: DateTime.now().subtract(const Duration(days: 1)),
    ),
    Trade(
      id: 't-002',
      symbol: 'ETH/USDT',
      side: TradeSide.long,
      status: TradeStatus.closed,
      entryPrice: 3450.00,
      exitPrice: 3380.00,
      quantity: 3.0,
      pnl: -210.00,
      pnlPercent: -2.03,
      strategy: 'Breakout',
      openedAt: DateTime.now().subtract(const Duration(days: 3)),
      closedAt: DateTime.now().subtract(const Duration(days: 2, hours: 12)),
    ),
    Trade(
      id: 't-003',
      symbol: 'SOL/USDT',
      side: TradeSide.short,
      status: TradeStatus.closed,
      entryPrice: 180.00,
      exitPrice: 165.50,
      quantity: 50,
      pnl: 725.00,
      pnlPercent: 8.06,
      strategy: 'Mean Reversion',
      openedAt: DateTime.now().subtract(const Duration(days: 5)),
      closedAt: DateTime.now().subtract(const Duration(days: 4)),
    ),
    Trade(
      id: 't-004',
      symbol: 'AVAX/USDT',
      side: TradeSide.long,
      status: TradeStatus.closed,
      entryPrice: 38.50,
      exitPrice: 41.20,
      quantity: 100,
      pnl: 270.00,
      pnlPercent: 7.01,
      strategy: 'Support Bounce',
      openedAt: DateTime.now().subtract(const Duration(days: 7)),
      closedAt: DateTime.now().subtract(const Duration(days: 6)),
    ),
    Trade(
      id: 't-005',
      symbol: 'BTC/USDT',
      side: TradeSide.long,
      status: TradeStatus.open,
      entryPrice: 67250.00,
      quantity: 0.15,
      stopLoss: 65500.00,
      takeProfit: 72000.00,
      strategy: 'Trend Following',
      openedAt: DateTime.now().subtract(const Duration(hours: 6)),
    ),
    Trade(
      id: 't-006',
      symbol: 'LINK/USDT',
      side: TradeSide.long,
      status: TradeStatus.closed,
      entryPrice: 14.20,
      exitPrice: 15.80,
      quantity: 200,
      pnl: 320.00,
      pnlPercent: 11.27,
      strategy: 'Breakout',
      openedAt: DateTime.now().subtract(const Duration(days: 10)),
      closedAt: DateTime.now().subtract(const Duration(days: 9)),
    ),
  ];
});

enum TradeFilter { all, open, closed, profitable, losing }

final tradeFilterProvider = StateProvider<TradeFilter>((ref) => TradeFilter.all);

class TradesScreen extends ConsumerWidget {
  const TradesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final trades = ref.watch(tradesProvider);
    final filter = ref.watch(tradeFilterProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Trade History'),
        actions: [
          IconButton(
            icon: const Icon(Icons.filter_list_rounded),
            onPressed: () => _showFilterSheet(context, ref),
          ),
        ],
      ),
      body: trades.when(
        data: (data) {
          final filtered = _applyFilter(data, filter);
          return Column(
            children: [
              // Stats bar
              _buildStatsBar(data),
              // Filter chips
              _buildFilterChips(context, ref, filter),
              // Trade list
              Expanded(
                child: filtered.isEmpty
                    ? Center(
                        child: Text(
                          'No trades match filter',
                          style: theme.textTheme.bodyMedium,
                        ),
                      )
                    : ListView.builder(
                        padding: const EdgeInsets.symmetric(horizontal: 16),
                        itemCount: filtered.length,
                        itemBuilder: (context, index) {
                          return _TradeListTile(trade: filtered[index]);
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
          child: Text('Error: $e', style: theme.textTheme.bodyMedium),
        ),
      ),
    );
  }

  Widget _buildStatsBar(List<Trade> trades) {
    final closed = trades.where((t) => t.isClosed).toList();
    final wins = closed.where((t) => t.isProfit).length;
    final losses = closed.where((t) => !t.isProfit).length;
    final totalPnl = closed.fold<double>(0, (sum, t) => sum + (t.pnl ?? 0));
    final winRate = closed.isEmpty ? 0.0 : (wins / closed.length) * 100;

    return Container(
      margin: const EdgeInsets.fromLTRB(16, 8, 16, 0),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AlphaStackApp.cardDark,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AlphaStackApp.borderDark),
      ),
      child: Row(
        children: [
          _StatItem(label: 'Total', value: '${trades.length}'),
          _StatItem(label: 'Win Rate', value: '${winRate.toStringAsFixed(1)}%'),
          _StatItem(
            label: 'P&L',
            value: '${totalPnl >= 0 ? '+' : ''}\$${totalPnl.toStringAsFixed(2)}',
            color: totalPnl >= 0
                ? AlphaStackApp.accentGreen
                : AlphaStackApp.accentRed,
          ),
          _StatItem(label: 'W/L', value: '$wins/$losses'),
        ],
      ),
    );
  }

  Widget _buildFilterChips(
      BuildContext context, WidgetRef ref, TradeFilter current) {
    return SizedBox(
      height: 50,
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        children: TradeFilter.values.map((f) {
          final isActive = f == current;
          return Padding(
            padding: const EdgeInsets.symmetric(horizontal: 4),
            child: FilterChip(
              selected: isActive,
              label: Text(_filterLabel(f)),
              onSelected: (_) =>
                  ref.read(tradeFilterProvider.notifier).state = f,
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

  List<Trade> _applyFilter(List<Trade> trades, TradeFilter filter) {
    switch (filter) {
      case TradeFilter.all:
        return trades;
      case TradeFilter.open:
        return trades.where((t) => t.isOpen).toList();
      case TradeFilter.closed:
        return trades.where((t) => t.isClosed).toList();
      case TradeFilter.profitable:
        return trades.where((t) => t.isProfit).toList();
      case TradeFilter.losing:
        return trades.where((t) => !t.isProfit && t.isClosed).toList();
    }
  }

  String _filterLabel(TradeFilter f) {
    switch (f) {
      case TradeFilter.all:
        return 'All';
      case TradeFilter.open:
        return 'Open';
      case TradeFilter.closed:
        return 'Closed';
      case TradeFilter.profitable:
        return 'Profitable';
      case TradeFilter.losing:
        return 'Losing';
    }
  }

  void _showFilterSheet(BuildContext context, WidgetRef ref) {
    showModalBottomSheet(
      context: context,
      backgroundColor: AlphaStackApp.surfaceDark,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (context) => Container(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Sort By', style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 16),
            _SortOption(title: 'Newest First', icon: Icons.arrow_downward),
            _SortOption(title: 'Oldest First', icon: Icons.arrow_upward),
            _SortOption(title: 'Highest P&L', icon: Icons.trending_up),
            _SortOption(title: 'Lowest P&L', icon: Icons.trending_down),
          ],
        ),
      ),
    );
  }
}

class _TradeListTile extends StatelessWidget {
  final Trade trade;

  const _TradeListTile({required this.trade});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isProfit = trade.isProfit;
    final pnlColor = trade.isClosed
        ? (isProfit ? AlphaStackApp.accentGreen : AlphaStackApp.accentRed)
        : AlphaStackApp.textSecondary;

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AlphaStackApp.cardDark,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AlphaStackApp.borderDark, width: 0.5),
      ),
      child: Row(
        children: [
          // Symbol & Side
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(
                      trade.symbol,
                      style: theme.textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(width: 6),
                    _SideChip(side: trade.side),
                    const SizedBox(width: 6),
                    if (trade.isOpen)
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: AlphaStackApp.accentBlue.withAlpha(30),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: const Text(
                          'OPEN',
                          style: TextStyle(
                            fontSize: 9,
                            fontWeight: FontWeight.w700,
                            color: AlphaStackApp.accentBlue,
                          ),
                        ),
                      ),
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                  '${trade.quantity.toStringAsFixed(4)} @ \$${trade.entryPrice.toStringAsFixed(2)}',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: AlphaStackApp.textSecondary,
                  ),
                ),
                if (trade.strategy != null) ...[
                  const SizedBox(height: 2),
                  Text(
                    trade.strategy!,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: AlphaStackApp.textSecondary,
                      fontSize: 11,
                    ),
                  ),
                ],
              ],
            ),
          ),
          // P&L
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              if (trade.isClosed && trade.pnl != null) ...[
                Text(
                  '${trade.pnl! >= 0 ? '+' : ''}\$${trade.pnl!.abs().toStringAsFixed(2)}',
                  style: theme.textTheme.titleMedium?.copyWith(
                    color: pnlColor,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                if (trade.pnlPercent != null)
                  Text(
                    '${trade.pnlPercent! >= 0 ? '+' : ''}${trade.pnlPercent!.toStringAsFixed(2)}%',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: pnlColor.withAlpha(200),
                    ),
                  ),
              ] else ...[
                Text(
                  'In Progress',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: AlphaStackApp.textSecondary,
                  ),
                ),
              ],
              const SizedBox(height: 4),
              Text(
                DateFormat('MM/dd HH:mm').format(trade.openedAt),
                style: theme.textTheme.bodySmall?.copyWith(
                  color: AlphaStackApp.textSecondary,
                  fontSize: 11,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _SideChip extends StatelessWidget {
  final TradeSide side;
  const _SideChip({required this.side});

  @override
  Widget build(BuildContext context) {
    final isLong = side == TradeSide.long;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
      decoration: BoxDecoration(
        color: (isLong ? AlphaStackApp.accentGreen : AlphaStackApp.accentRed)
            .withAlpha(25),
        borderRadius: BorderRadius.circular(3),
      ),
      child: Text(
        isLong ? 'L' : 'S',
        style: TextStyle(
          fontSize: 10,
          fontWeight: FontWeight.w700,
          color: isLong ? AlphaStackApp.accentGreen : AlphaStackApp.accentRed,
        ),
      ),
    );
  }
}

class _StatItem extends StatelessWidget {
  final String label;
  final String value;
  final Color? color;

  const _StatItem({required this.label, required this.value, this.color});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Expanded(
      child: Column(
        children: [
          Text(
            value,
            style: theme.textTheme.titleMedium?.copyWith(
              color: color ?? AlphaStackApp.textPrimary,
              fontWeight: FontWeight.w600,
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
    );
  }
}

class _SortOption extends StatelessWidget {
  final String title;
  final IconData icon;

  const _SortOption({required this.title, required this.icon});

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: Icon(icon, color: AlphaStackApp.textSecondary, size: 20),
      title: Text(title),
      onTap: () => Navigator.pop(context),
      contentPadding: EdgeInsets.zero,
    );
  }
}
