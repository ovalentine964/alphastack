import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:fl_chart/fl_chart.dart';
import '../app.dart';
import '../widgets/pnl_chart.dart';

final analyticsPeriodProvider = StateProvider<String>((ref) => '30d');

final performanceProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  await Future.delayed(const Duration(milliseconds: 500));
  return {
    'totalTrades': 156,
    'winRate': 68.5,
    'profitFactor': 2.14,
    'sharpeRatio': 1.87,
    'maxDrawdown': -8.3,
    'avgWin': 425.50,
    'avgLoss': -198.20,
    'bestTrade': 1250.00,
    'worstTrade': -580.00,
    'totalPnl': 18420.75,
    'consecutiveWins': 8,
    'consecutiveLosses': 3,
  };
});

final pnlHistoryProvider = FutureProvider<List<PnlDataPoint>>((ref) async {
  await Future.delayed(const Duration(milliseconds: 600));
  final now = DateTime.now();
  return List.generate(30, (i) {
    final base = 100000 + (i * 300.0);
    final noise = (i % 3 == 0 ? -1 : 1) * (i * 50.0);
    return PnlDataPoint(
      date: now.subtract(Duration(days: 30 - i)),
      value: base + noise + (i * i * 2.0),
    );
  });
});

final winRateHistoryProvider = FutureProvider<List<WinRatePoint>>((ref) async {
  await Future.delayed(const Duration(milliseconds: 700));
  return List.generate(10, (i) {
    return WinRatePoint(
      label: 'W${i + 1}',
      winRate: 55 + (i * 1.5) + (i % 2 == 0 ? 5 : -3),
      trades: 12 + (i % 4),
    );
  });
});

class AnalyticsScreen extends ConsumerWidget {
  const AnalyticsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final performance = ref.watch(performanceProvider);
    final pnlHistory = ref.watch(pnlHistoryProvider);
    final winRateHistory = ref.watch(winRateHistoryProvider);
    final period = ref.watch(analyticsPeriodProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Analytics'),
        actions: [
          PopupMenuButton<String>(
            icon: const Icon(Icons.calendar_today_rounded, size: 20),
            onSelected: (v) =>
                ref.read(analyticsPeriodProvider.notifier).state = v,
            itemBuilder: (_) => [
              _periodItem('7d', '7 Days', period),
              _periodItem('30d', '30 Days', period),
              _periodItem('90d', '90 Days', period),
              _periodItem('1y', '1 Year', period),
            ],
            color: AlphaStackApp.surfaceDark,
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // P&L Chart
          pnlHistory.when(
            data: (data) => Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AlphaStackApp.cardDark,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AlphaStackApp.borderDark),
              ),
              child: PnlChart(data: data, height: 200),
            ),
            loading: () => _buildSkeleton(height: 250),
            error: (e, _) => _buildError('P&L Chart', e),
          ),
          const SizedBox(height: 16),

          // Key Metrics Grid
          performance.when(
            data: (data) => _buildMetricsGrid(context, data),
            loading: () => _buildSkeleton(height: 200),
            error: (e, _) => _buildError('Metrics', e),
          ),
          const SizedBox(height: 16),

          // Win Rate Chart
          winRateHistory.when(
            data: (data) => _buildWinRateChart(context, data),
            loading: () => _buildSkeleton(height: 200),
            error: (e, _) => _buildError('Win Rate', e),
          ),
          const SizedBox(height: 16),

          // Strategy Breakdown
          _buildStrategyBreakdown(context),
          const SizedBox(height: 16),

          // Risk Metrics
          performance.when(
            data: (data) => _buildRiskMetrics(context, data),
            loading: () => _buildSkeleton(height: 150),
            error: (e, _) => _buildError('Risk', e),
          ),
          const SizedBox(height: 80),
        ],
      ),
    );
  }

  PopupMenuItem<String> _periodItem(String value, String label, String current) {
    return PopupMenuItem(
      value: value,
      child: Row(
        children: [
          if (value == current)
            const Icon(Icons.check, size: 16, color: AlphaStackApp.accentBlue)
          else
            const SizedBox(width: 16),
          const SizedBox(width: 8),
          Text(label),
        ],
      ),
    );
  }

  Widget _buildMetricsGrid(BuildContext context, Map<String, dynamic> data) {
    final metrics = [
      _MetricData('Total P&L', '\$${(data['totalPnl'] as double).toStringAsFixed(2)}',
          data['totalPnl'] >= 0 ? AlphaStackApp.accentGreen : AlphaStackApp.accentRed),
      _MetricData('Win Rate', '${data['winRate']}%', AlphaStackApp.accentBlue),
      _MetricData('Profit Factor', '${data['profitFactor']}', AlphaStackApp.accentGreen),
      _MetricData('Sharpe Ratio', '${data['sharpeRatio']}', AlphaStackApp.accentOrange),
      _MetricData('Max Drawdown', '${data['maxDrawdown']}%', AlphaStackApp.accentRed),
      _MetricData('Total Trades', '${data['totalTrades']}', AlphaStackApp.textPrimary),
    ];

    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 2,
        mainAxisSpacing: 8,
        crossAxisSpacing: 8,
        childAspectRatio: 2.2,
      ),
      itemCount: metrics.length,
      itemBuilder: (context, index) {
        final m = metrics[index];
        return Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: AlphaStackApp.cardDark,
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: AlphaStackApp.borderDark),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(
                m.label,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: AlphaStackApp.textSecondary,
                      fontSize: 11,
                    ),
              ),
              const SizedBox(height: 4),
              Text(
                m.value,
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      color: m.color,
                      fontWeight: FontWeight.w700,
                    ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildWinRateChart(BuildContext context, List<WinRatePoint> data) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AlphaStackApp.cardDark,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AlphaStackApp.borderDark),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Win Rate Trend', style: theme.textTheme.titleMedium),
          const SizedBox(height: 16),
          SizedBox(
            height: 150,
            child: BarChart(
              BarChartData(
                alignment: BarChartAlignment.spaceAround,
                maxY: 100,
                barTouchData: BarTouchData(
                  touchTooltipData: BarTouchTooltipData(
                    tooltipBgColor: AlphaStackApp.surfaceDark,
                    getTooltipItem: (group, groupIndex, rod, rodIndex) {
                      return BarTooltipItem(
                        '${data[group.x].winRate.toStringAsFixed(1)}%\n',
                        TextStyle(
                          color: rod.toY >= 60
                              ? AlphaStackApp.accentGreen
                              : AlphaStackApp.accentRed,
                          fontWeight: FontWeight.w600,
                        ),
                        children: [
                          TextSpan(
                            text: '${data[group.x].trades} trades',
                            style: TextStyle(
                              color: AlphaStackApp.textSecondary,
                              fontSize: 11,
                            ),
                          ),
                        ],
                      );
                    },
                  ),
                ),
                titlesData: FlTitlesData(
                  show: true,
                  bottomTitles: AxisTitles(
                    sideTitles: SideTitles(
                      showTitles: true,
                      getTitlesWidget: (value, meta) {
                        return Text(
                          data[value.toInt()].label,
                          style: TextStyle(
                            color: AlphaStackApp.textSecondary,
                            fontSize: 10,
                          ),
                        );
                      },
                    ),
                  ),
                  leftTitles: const AxisTitles(
                    sideTitles: SideTitles(showTitles: false),
                  ),
                  topTitles: const AxisTitles(
                    sideTitles: SideTitles(showTitles: false),
                  ),
                  rightTitles: const AxisTitles(
                    sideTitles: SideTitles(showTitles: false),
                  ),
                ),
                borderData: FlBorderData(show: false),
                gridData: const FlGridData(show: false),
                barGroups: List.generate(data.length, (i) {
                  final d = data[i];
                  return BarChartGroupData(
                    x: i,
                    barRods: [
                      BarChartRodData(
                        toY: d.winRate,
                        color: d.winRate >= 60
                            ? AlphaStackApp.accentGreen
                            : d.winRate >= 50
                                ? AlphaStackApp.accentOrange
                                : AlphaStackApp.accentRed,
                        width: 16,
                        borderRadius: const BorderRadius.vertical(
                            top: Radius.circular(4)),
                        backDrawRodData: BackgroundBarChartRodData(
                          show: true,
                          toY: 100,
                          color: AlphaStackApp.borderDark.withAlpha(60),
                        ),
                      ),
                    ],
                  );
                }),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStrategyBreakdown(BuildContext context) {
    final theme = Theme.of(context);
    final strategies = [
      _StrategyData('Trend Following', 45, 72.5, 8420.50),
      _StrategyData('Mean Reversion', 38, 65.8, 5230.25),
      _StrategyData('Breakout', 42, 62.3, 3150.00),
      _StrategyData('Reversal', 31, 58.1, 1620.00),
    ];

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AlphaStackApp.cardDark,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AlphaStackApp.borderDark),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Strategy Performance', style: theme.textTheme.titleMedium),
          const SizedBox(height: 16),
          ...strategies.map((s) => Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(s.name,
                            style: theme.textTheme.bodyMedium?.copyWith(
                              fontWeight: FontWeight.w500,
                            )),
                        Text(
                          '\$${s.pnl.toStringAsFixed(0)}',
                          style: theme.textTheme.bodyMedium?.copyWith(
                            color: AlphaStackApp.accentGreen,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    Row(
                      children: [
                        Expanded(
                          child: ClipRRect(
                            borderRadius: BorderRadius.circular(4),
                            child: LinearProgressIndicator(
                              value: s.winRate / 100,
                              backgroundColor: AlphaStackApp.borderDark,
                              valueColor: AlwaysStoppedAnimation(
                                s.winRate >= 65
                                    ? AlphaStackApp.accentGreen
                                    : AlphaStackApp.accentOrange,
                              ),
                              minHeight: 6,
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          '${s.winRate.toStringAsFixed(1)}% · ${s.trades} trades',
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: AlphaStackApp.textSecondary,
                            fontSize: 11,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              )),
        ],
      ),
    );
  }

  Widget _buildRiskMetrics(BuildContext context, Map<String, dynamic> data) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AlphaStackApp.cardDark,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AlphaStackApp.borderDark),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Risk Analysis', style: theme.textTheme.titleMedium),
          const SizedBox(height: 16),
          _RiskRow(
              'Avg Win', '\$${(data['avgWin'] as double).toStringAsFixed(2)}',
              AlphaStackApp.accentGreen),
          _RiskRow(
              'Avg Loss', '\$${(data['avgLoss'] as double).abs().toStringAsFixed(2)}',
              AlphaStackApp.accentRed),
          _RiskRow('Best Trade', '\$${(data['bestTrade'] as double).toStringAsFixed(2)}',
              AlphaStackApp.accentGreen),
          _RiskRow('Worst Trade',
              '-\$${(data['worstTrade'] as double).abs().toStringAsFixed(2)}',
              AlphaStackApp.accentRed),
          _RiskRow('Max Consecutive Wins', '${data['consecutiveWins']}',
              AlphaStackApp.accentGreen),
          _RiskRow('Max Consecutive Losses', '${data['consecutiveLosses']}',
              AlphaStackApp.accentRed),
        ],
      ),
    );
  }

  Widget _buildSkeleton({double height = 100}) {
    return Container(
      height: height,
      decoration: BoxDecoration(
        color: AlphaStackApp.cardDark,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AlphaStackApp.borderDark),
      ),
      child: const Center(
        child: CircularProgressIndicator(
            color: AlphaStackApp.accentBlue, strokeWidth: 2),
      ),
    );
  }

  Widget _buildError(String label, Object error) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AlphaStackApp.cardDark,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AlphaStackApp.accentRed.withAlpha(80)),
      ),
      child: Center(child: Text('Failed to load $label')),
    );
  }
}

class _MetricData {
  final String label;
  final String value;
  final Color color;
  _MetricData(this.label, this.value, this.color);
}

class _StrategyData {
  final String name;
  final int trades;
  final double winRate;
  final double pnl;
  _StrategyData(this.name, this.trades, this.winRate, this.pnl);
}

class WinRatePoint {
  final String label;
  final double winRate;
  final int trades;
  WinRatePoint({required this.label, required this.winRate, required this.trades});
}

class _RiskRow extends StatelessWidget {
  final String label;
  final String value;
  final Color color;

  const _RiskRow(this.label, this.value, this.color);

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: AlphaStackApp.textSecondary,
              )),
          Text(value,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: color,
                fontWeight: FontWeight.w600,
              )),
        ],
      ),
    );
  }
}
