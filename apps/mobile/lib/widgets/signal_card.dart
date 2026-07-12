import 'package:flutter/material.dart';
import '../app.dart';
import '../models/signal.dart';

class SignalCard extends StatelessWidget {
  final Signal signal;
  final VoidCallback? onTap;

  const SignalCard({
    super.key,
    required this.signal,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isBuy = signal.isBuy;
    final directionColor =
        isBuy ? AlphaStackApp.accentGreen : AlphaStackApp.accentRed;

    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        decoration: BoxDecoration(
          color: AlphaStackApp.cardDark,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AlphaStackApp.borderDark, width: 1),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 14, 16, 0),
              child: Row(
                children: [
                  // Symbol
                  Text(
                    signal.symbol,
                    style: theme.textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(width: 8),
                  // Direction badge
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: directionColor.withAlpha(30),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      isBuy ? 'BUY' : 'SELL',
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                        color: directionColor,
                        letterSpacing: 0.5,
                      ),
                    ),
                  ),
                  const Spacer(),
                  // Timeframe
                  if (signal.timeframe != null)
                    Text(
                      signal.timeframe!,
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: AlphaStackApp.textSecondary,
                      ),
                    ),
                ],
              ),
            ),

            // Confluence Score
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
              child: Row(
                children: [
                  _ConfluenceGauge(score: signal.confluenceScore),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Confluence: ${signal.confluenceLabel}',
                          style: theme.textTheme.bodyMedium?.copyWith(
                            color: _confluenceColor(signal.confluenceScore),
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          '${(signal.confluenceScore * 100).toStringAsFixed(0)}% confidence',
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: AlphaStackApp.textSecondary,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),

            // Price levels
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 14, 16, 0),
              child: Row(
                children: [
                  _PriceLevel(
                    label: 'Entry',
                    value: _formatPrice(signal.entryPrice),
                  ),
                  if (signal.targetPrice != null)
                    _PriceLevel(
                      label: 'Target',
                      value: _formatPrice(signal.targetPrice!),
                      color: AlphaStackApp.accentGreen,
                    ),
                  if (signal.stopLoss != null)
                    _PriceLevel(
                      label: 'Stop',
                      value: _formatPrice(signal.stopLoss!),
                      color: AlphaStackApp.accentRed,
                    ),
                  if (signal.riskRewardRatio > 0)
                    _PriceLevel(
                      label: 'R:R',
                      value: '${signal.riskRewardRatio.toStringAsFixed(1)}x',
                      color: AlphaStackApp.accentBlue,
                    ),
                ],
              ),
            ),

            // Factors
            if (signal.factors.isNotEmpty)
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 14),
                child: Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: signal.factors.take(5).map((factor) {
                    return Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: AlphaStackApp.surfaceDark,
                        borderRadius: BorderRadius.circular(6),
                        border: Border.all(
                          color: AlphaStackApp.borderDark,
                          width: 0.5,
                        ),
                      ),
                      child: Text(
                        factor,
                        style: theme.textTheme.bodySmall?.copyWith(
                          fontSize: 11,
                          color: AlphaStackApp.textSecondary,
                        ),
                      ),
                    );
                  }).toList(),
                ),
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

  static Color _confluenceColor(double score) {
    if (score >= 0.8) return AlphaStackApp.accentGreen;
    if (score >= 0.6) return const Color(0xFF7EE787);
    if (score >= 0.4) return AlphaStackApp.accentOrange;
    if (score >= 0.2) return AlphaStackApp.accentRed;
    return const Color(0xFFF85149);
  }
}

class _ConfluenceGauge extends StatelessWidget {
  final double score;

  const _ConfluenceGauge({required this.score});

  @override
  Widget build(BuildContext context) {
    final color = SignalCard._confluenceColor(score);

    return SizedBox(
      width: 44,
      height: 44,
      child: Stack(
        alignment: Alignment.center,
        children: [
          SizedBox(
            width: 44,
            height: 44,
            child: CircularProgressIndicator(
              value: score,
              strokeWidth: 4,
              backgroundColor: AlphaStackApp.borderDark,
              valueColor: AlwaysStoppedAnimation<Color>(color),
              strokeCap: StrokeCap.round,
            ),
          ),
          Text(
            '${(score * 100).toInt()}',
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w700,
              color: color,
            ),
          ),
        ],
      ),
    );
  }
}

class _PriceLevel extends StatelessWidget {
  final String label;
  final String value;
  final Color? color;

  const _PriceLevel({
    required this.label,
    required this.value,
    this.color,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Expanded(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: theme.textTheme.bodySmall?.copyWith(
              color: AlphaStackApp.textSecondary,
              fontSize: 11,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            '\$$value',
            style: theme.textTheme.bodyMedium?.copyWith(
              color: color ?? AlphaStackApp.textPrimary,
              fontWeight: FontWeight.w600,
              fontFamily: 'monospace',
            ),
          ),
        ],
      ),
    );
  }
}
