import 'package:flutter/material.dart';
import '../app.dart';

class PortfolioCard extends StatelessWidget {
  final double totalBalance;
  final double totalEquity;
  final double totalPnl;
  final double totalPnlPercent;
  final double dayPnl;
  final double dayPnlPercent;
  final int activePositions;

  const PortfolioCard({
    super.key,
    required this.totalBalance,
    required this.totalEquity,
    required this.totalPnl,
    required this.totalPnlPercent,
    required this.dayPnl,
    required this.dayPnlPercent,
    required this.activePositions,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isProfit = totalPnl >= 0;
    final isDayProfit = dayPnl >= 0;

    return Container(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            AlphaStackApp.cardDark,
            AlphaStackApp.cardDark.withBlue(30),
          ],
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AlphaStackApp.borderDark, width: 1),
      ),
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Portfolio',
                style: theme.textTheme.titleMedium?.copyWith(
                  color: AlphaStackApp.textSecondary,
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: AlphaStackApp.accentBlue.withAlpha(30),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  '$activePositions active',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: AlphaStackApp.accentBlue,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),

          // Total Balance
          Text(
            _formatCurrency(totalBalance),
            style: theme.textTheme.headlineLarge?.copyWith(
              fontSize: 32,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            'Total Balance',
            style: theme.textTheme.bodyMedium,
          ),
          const SizedBox(height: 20),

          // Metrics row
          Row(
            children: [
              _MetricTile(
                label: 'Total P&L',
                value: _formatPnl(totalPnl),
                percent: _formatPercent(totalPnlPercent),
                isProfit: isProfit,
              ),
              Container(
                width: 1,
                height: 40,
                color: AlphaStackApp.borderDark,
              ),
              _MetricTile(
                label: 'Day P&L',
                value: _formatPnl(dayPnl),
                percent: _formatPercent(dayPnlPercent),
                isProfit: isDayProfit,
              ),
              Container(
                width: 1,
                height: 40,
                color: AlphaStackApp.borderDark,
              ),
              _MetricTile(
                label: 'Equity',
                value: _formatCurrency(totalEquity),
                isNeutral: true,
              ),
            ],
          ),
        ],
      ),
    );
  }

  static String _formatCurrency(double value) {
    if (value >= 1000000) {
      return '\$${(value / 1000000).toStringAsFixed(2)}M';
    } else if (value >= 1000) {
      return '\$${(value / 1000).toStringAsFixed(2)}K';
    }
    return '\$${value.toStringAsFixed(2)}';
  }

  static String _formatPnl(double value) {
    final prefix = value >= 0 ? '+' : '';
    return '$prefix\$${value.abs().toStringAsFixed(2)}';
  }

  static String _formatPercent(double value) {
    final prefix = value >= 0 ? '+' : '';
    return '$prefix${value.toStringAsFixed(2)}%';
  }
}

class _MetricTile extends StatelessWidget {
  final String label;
  final String value;
  final String? percent;
  final bool isProfit;
  final bool isNeutral;

  const _MetricTile({
    required this.label,
    required this.value,
    this.percent,
    this.isProfit = false,
    this.isNeutral = false,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final color = isNeutral
        ? AlphaStackApp.textPrimary
        : isProfit
            ? AlphaStackApp.accentGreen
            : AlphaStackApp.accentRed;

    return Expanded(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Text(
            value,
            style: theme.textTheme.titleMedium?.copyWith(
              color: color,
              fontWeight: FontWeight.w600,
            ),
          ),
          if (percent != null) ...[
            const SizedBox(height: 2),
            Text(
              percent!,
              style: theme.textTheme.bodySmall?.copyWith(
                color: color.withAlpha(200),
              ),
            ),
          ],
          const SizedBox(height: 4),
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
