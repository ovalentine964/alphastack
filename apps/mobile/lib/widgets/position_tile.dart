import 'package:flutter/material.dart';
import '../app.dart';
import '../models/trade.dart';

class PositionTile extends StatelessWidget {
  final Position position;
  final VoidCallback? onTap;

  const PositionTile({
    super.key,
    required this.position,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isProfit = position.isProfit;
    final pnlColor = isProfit ? AlphaStackApp.accentGreen : AlphaStackApp.accentRed;

    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: AlphaStackApp.cardDark,
          border: Border(
            bottom: BorderSide(color: AlphaStackApp.borderDark.withAlpha(128), width: 0.5),
          ),
        ),
        child: Row(
          children: [
            // Symbol & Side
            Expanded(
              flex: 3,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Text(
                        position.symbol,
                        style: theme.textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      const SizedBox(width: 6),
                      _SideBadge(side: position.side),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(
                    '${position.quantity.toStringAsFixed(4)} @ ${_formatPrice(position.entryPrice)}',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: AlphaStackApp.textSecondary,
                    ),
                  ),
                ],
              ),
            ),

            // Current Price
            Expanded(
              flex: 2,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    _formatPrice(position.currentPrice),
                    style: theme.textTheme.bodyLarge?.copyWith(
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    _formatPercentChange(position.unrealizedPnlPercent),
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: pnlColor,
                    ),
                  ),
                ],
              ),
            ),

            const SizedBox(width: 12),

            // P&L
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(
                  _formatPnl(position.unrealizedPnl),
                  style: theme.textTheme.titleMedium?.copyWith(
                    color: pnlColor,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  'P&L',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: AlphaStackApp.textSecondary,
                    fontSize: 11,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  static String _formatPrice(double price) {
    if (price >= 1000) return price.toStringAsFixed(2);
    if (price >= 1) return price.toStringAsFixed(4);
    return price.toStringAsFixed(6);
  }

  static String _formatPnl(double pnl) {
    final prefix = pnl >= 0 ? '+' : '';
    return '$prefix\$${pnl.abs().toStringAsFixed(2)}';
  }

  static String _formatPercentChange(double pct) {
    final prefix = pct >= 0 ? '+' : '';
    return '$prefix${pct.toStringAsFixed(2)}%';
  }
}

class _SideBadge extends StatelessWidget {
  final TradeSide side;

  const _SideBadge({required this.side});

  @override
  Widget build(BuildContext context) {
    final isLong = side == TradeSide.long;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: (isLong ? AlphaStackApp.accentGreen : AlphaStackApp.accentRed)
            .withAlpha(30),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        isLong ? 'LONG' : 'SHORT',
        style: TextStyle(
          fontSize: 10,
          fontWeight: FontWeight.w700,
          color: isLong ? AlphaStackApp.accentGreen : AlphaStackApp.accentRed,
          letterSpacing: 0.5,
        ),
      ),
    );
  }
}
