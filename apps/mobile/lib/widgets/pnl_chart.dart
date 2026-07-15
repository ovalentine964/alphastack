import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:intl/intl.dart';
import '../app.dart';

class PnlChart extends StatelessWidget {
  final List<PnlDataPoint> data;
  final String title;
  final double height;
  final bool showGrid;
  final bool showLabels;

  const PnlChart({
    super.key,
    required this.data,
    this.title = 'Cumulative P&L',
    this.height = 220,
    this.showGrid = true,
    this.showLabels = true,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    if (data.isEmpty) {
      return SizedBox(
        height: height,
        child: Center(
          child: Text(
            'No data available',
            style: theme.textTheme.bodyMedium,
          ),
        ),
      );
    }

    final isOverallProfit = data.last.value >= 0;
    final lineColor =
        isOverallProfit ? AlphaStackApp.accentGreen : AlphaStackApp.accentRed;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (title.isNotEmpty) ...[
          Text(
            title,
            style: theme.textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            '${data.length} data points',
            style: theme.textTheme.bodySmall?.copyWith(
              color: AlphaStackApp.textSecondary,
            ),
          ),
          const SizedBox(height: 16),
        ],
        SizedBox(
          height: height,
          child: LineChart(
            LineChartData(
              gridData: FlGridData(
                show: showGrid,
                drawVerticalLine: false,
                horizontalInterval: _calculateInterval(),
                getDrawingHorizontalLine: (value) {
                  return FlLine(
                    color: AlphaStackApp.borderDark.withAlpha(100),
                    strokeWidth: 0.5,
                  );
                },
              ),
              titlesData: FlTitlesData(
                leftTitles: AxisTitles(
                  sideTitles: SideTitles(
                    showTitles: showLabels,
                    reservedSize: 60,
                    getTitlesWidget: (value, meta) {
                      return Text(
                        _formatAxisValue(value),
                        style: TextStyle(
                          color: AlphaStackApp.textSecondary,
                          fontSize: 10,
                        ),
                      );
                    },
                  ),
                ),
                bottomTitles: AxisTitles(
                  sideTitles: SideTitles(
                    showTitles: showLabels,
                    reservedSize: 30,
                    interval: (data.length / 5).ceilToDouble().clamp(1, double.infinity),
                    getTitlesWidget: (value, meta) {
                      final idx = value.toInt();
                      if (idx < 0 || idx >= data.length) {
                        return const SizedBox.shrink();
                      }
                      return Padding(
                        padding: const EdgeInsets.only(top: 8),
                        child: Text(
                          DateFormat('MM/dd').format(data[idx].date),
                          style: TextStyle(
                            color: AlphaStackApp.textSecondary,
                            fontSize: 10,
                          ),
                        ),
                      );
                    },
                  ),
                ),
                topTitles: const AxisTitles(
                  sideTitles: SideTitles(showTitles: false),
                ),
                rightTitles: const AxisTitles(
                  sideTitles: SideTitles(showTitles: false),
                ),
              ),
              borderData: FlBorderData(show: false),
              lineTouchData: LineTouchData(
                touchTooltipData: LineTouchTooltipData(
                  tooltipBgColor: AlphaStackApp.surfaceDark,
                  getTooltipItems: (spots) {
                    return spots.map((spot) {
                      final point = data[spot.x.toInt()];
                      return LineTooltipItem(
                        '\$${point.value.toStringAsFixed(2)}\n',
                        TextStyle(
                          color: point.value >= 0
                              ? AlphaStackApp.accentGreen
                              : AlphaStackApp.accentRed,
                          fontWeight: FontWeight.w600,
                          fontSize: 13,
                        ),
                        children: [
                          TextSpan(
                            text: DateFormat('MMM dd, yyyy').format(point.date),
                            style: TextStyle(
                              color: AlphaStackApp.textSecondary,
                              fontSize: 11,
                              fontWeight: FontWeight.normal,
                            ),
                          ),
                        ],
                      );
                    }).toList();
                  },
                ),
              ),
              lineBarsData: [
                LineChartBarData(
                  spots: List.generate(
                    data.length,
                    (i) => FlSpot(i.toDouble(), data[i].value),
                  ),
                  isCurved: true,
                  curveSmoothness: 0.2,
                  color: lineColor,
                  barWidth: 2.5,
                  dotData: const FlDotData(show: false),
                  belowBarData: BarAreaData(
                    show: true,
                    gradient: LinearGradient(
                      begin: Alignment.topCenter,
                      end: Alignment.bottomCenter,
                      colors: [
                        lineColor.withAlpha(40),
                        lineColor.withAlpha(0),
                      ],
                    ),
                  ),
                ),
              ],
              extraLinesData: ExtraLinesData(
                horizontalLines: [
                  HorizontalLine(
                    y: 0,
                    color: AlphaStackApp.textSecondary.withAlpha(60),
                    strokeWidth: 1,
                    dashArray: [5, 5],
                  ),
                ],
              ),
            ),
            duration: const Duration(milliseconds: 300),
          ),
        ),
      ],
    );
  }

  double _calculateInterval() {
    if (data.isEmpty) return 1;
    final values = data.map((d) => d.value).toList();
    final min = values.reduce((a, b) => a < b ? a : b);
    final max = values.reduce((a, b) => a > b ? a : b);
    final range = (max - min).abs();
    if (range == 0) return 1;
    return (range / 4).ceilToDouble();
  }

  static String _formatAxisValue(double value) {
    if (value.abs() >= 1000000) {
      return '\$${(value / 1000000).toStringAsFixed(1)}M';
    }
    if (value.abs() >= 1000) {
      return '\$${(value / 1000).toStringAsFixed(1)}K';
    }
    return '\$${value.toStringAsFixed(0)}';
  }
}

class PnlDataPoint {
  final DateTime date;
  final double value;

  const PnlDataPoint({required this.date, required this.value});
}
