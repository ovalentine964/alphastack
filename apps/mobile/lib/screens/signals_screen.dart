import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import '../app.dart';
import '../services/api_service.dart';
import '../widgets/signal_card.dart';
import '../widgets/shimmer_loading.dart';
import '../widgets/state_widgets.dart';
import '../models/signal.dart';

// ─── Providers ──────────────────────────────────────────────

final signalsListProvider = FutureProvider<List<Signal>>((ref) async {
  return await ApiService().getActiveSignals();
});

// Filter state
enum SignalDirectionFilter { all, buy, sell }
enum ConfidenceFilter { all, high, medium, low }

class SignalFilters {
  final SignalDirectionFilter direction;
  final ConfidenceFilter confidence;
  final String? timeframe;
  final String? pair;

  const SignalFilters({
    this.direction = SignalDirectionFilter.all,
    this.confidence = ConfidenceFilter.all,
    this.timeframe,
    this.pair,
  });

  SignalFilters copyWith({
    SignalDirectionFilter? direction,
    ConfidenceFilter? confidence,
    String? timeframe,
    String? pair,
  }) {
    return SignalFilters(
      direction: direction ?? this.direction,
      confidence: confidence ?? this.confidence,
      timeframe: timeframe,
      pair: pair,
    );
  }
}

final signalFiltersProvider =
    StateProvider<SignalFilters>((ref) => const SignalFilters());

// ─── Screen ─────────────────────────────────────────────────

class SignalsScreen extends ConsumerWidget {
  const SignalsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final signals = ref.watch(signalsListProvider);
    final filters = ref.watch(signalFiltersProvider);

    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            // App bar
            _buildAppBar(context, ref),
            // Content
            Expanded(
              child: signals.when(
                data: (data) {
                  final active = data.where((s) => s.isActive).toList();
                  final filtered = _applyFilters(active, filters);

                  return Column(
                    children: [
                      // Summary row
                      _buildSummary(context, data, active),
                      // Filter chips
                      _buildFilterBar(context, ref, active, filters),
                      // Signal list
                      Expanded(
                        child: filtered.isEmpty
                            ? SingleChildScrollView(
                                physics: const AlwaysScrollableScrollPhysics(),
                                child: Padding(
                                  padding:
                                      const EdgeInsets.symmetric(vertical: 60),
                                  child: EmptyStateCard(
                                    title: 'No signals match filters',
                                    subtitle:
                                        'Try adjusting your filter criteria',
                                    icon: Icons
                                        .signal_cellular_off_rounded,
                                    action: TextButton(
                                      onPressed: () => ref
                                          .read(
                                              signalFiltersProvider.notifier)
                                          .state = const SignalFilters(),
                                      child: const Text('Clear Filters'),
                                    ),
                                  ),
                                ),
                              )
                            : RefreshIndicator(
                                onRefresh: () async {
                                  ref.invalidate(signalsListProvider);
                                },
                                color: AlphaStackApp.accentBlue,
                                child: ListView.builder(
                                  physics:
                                      const AlwaysScrollableScrollPhysics(
                                    parent: BouncingScrollPhysics(),
                                  ),
                                  padding:
                                      const EdgeInsets.fromLTRB(16, 8, 16, 80),
                                  itemCount: filtered.length,
                                  itemBuilder: (context, index) {
                                    return SignalCard(
                                      signal: filtered[index],
                                      onTap: () => _showSignalDetail(
                                          context, filtered[index]),
                                    );
                                  },
                                ),
                              ),
                      ),
                    ],
                  );
                },
                loading: () => _buildLoadingState(),
                error: (e, _) => Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: ErrorStateCard(
                      title: 'Failed to load signals',
                      message: _friendlyError(e),
                      onRetry: () => ref.invalidate(signalsListProvider),
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildAppBar(BuildContext context, WidgetRef ref) {
    return Container(
      padding: const EdgeInsets.fromLTRB(16, 12, 8, 8),
      child: Row(
        children: [
          Text(
            'Signals',
            style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                  fontWeight: FontWeight.w800,
                  fontSize: 24,
                ),
          ),
          const Spacer(),
          IconButton(
            icon: const Icon(Icons.tune_rounded, size: 22),
            onPressed: () => _showFilterSheet(context, ref),
            color: AlphaStackApp.textSecondary,
            tooltip: 'Advanced Filters',
          ),
          IconButton(
            icon: const Icon(Icons.sync_rounded, size: 22),
            onPressed: () => ref.invalidate(signalsListProvider),
            color: AlphaStackApp.textSecondary,
          ),
        ],
      ),
    );
  }

  Widget _buildSummary(
      BuildContext context, List<Signal> all, List<Signal> active) {
    final highConf = active.where((s) => s.confluenceScore >= 0.7).length;
    final avgScore = active.isEmpty
        ? 0.0
        : active.fold<double>(0, (sum, s) => sum + s.confluenceScore) /
            active.length;

    return Container(
      margin: const EdgeInsets.fromLTRB(16, 4, 16, 0),
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

  Widget _buildFilterBar(BuildContext context, WidgetRef ref,
      List<Signal> active, SignalFilters current) {
    // Extract available pairs and timeframes from signals
        active.map((s) => s.timeframe).whereType<String>().toSet().toList()
          ..sort();

    return Container(
      height: 50,
      margin: const EdgeInsets.only(top: 8),
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 12),
        children: [
          // Direction filters
          _FilterChipWidget(
            label: 'All',
            isActive: current.direction == SignalDirectionFilter.all,
            onTap: () => ref.read(signalFiltersProvider.notifier).state =
                current.copyWith(direction: SignalDirectionFilter.all),
          ),
          _FilterChipWidget(
            label: 'Buy / Long',
            isActive: current.direction == SignalDirectionFilter.buy,
            onTap: () => ref.read(signalFiltersProvider.notifier).state =
                current.copyWith(direction: SignalDirectionFilter.buy),
            activeColor: AlphaStackApp.accentGreen,
          ),
          _FilterChipWidget(
            label: 'Sell / Short',
            isActive: current.direction == SignalDirectionFilter.sell,
            onTap: () => ref.read(signalFiltersProvider.notifier).state =
                current.copyWith(direction: SignalDirectionFilter.sell),
            activeColor: AlphaStackApp.accentRed,
          ),
          const SizedBox(width: 4),
          Container(width: 1, color: AlphaStackApp.borderDark),
          const SizedBox(width: 4),
          // Confidence filters
          _FilterChipWidget(
            label: 'High Conf',
            isActive: current.confidence == ConfidenceFilter.high,
            onTap: () => ref.read(signalFiltersProvider.notifier).state =
                current.copyWith(confidence: ConfidenceFilter.high),
            activeColor: AlphaStackApp.accentGreen,
          ),
          _FilterChipWidget(
            label: 'Med Conf',
            isActive: current.confidence == ConfidenceFilter.medium,
            onTap: () => ref.read(signalFiltersProvider.notifier).state =
                current.copyWith(confidence: ConfidenceFilter.medium),
            activeColor: AlphaStackApp.accentOrange,
          ),
        ],
      ),
    );
  }

  List<Signal> _applyFilters(List<Signal> signals, SignalFilters filters) {
    var result = signals;

    // Direction filter
    switch (filters.direction) {
      case SignalDirectionFilter.buy:
        result = result.where((s) => s.isBuy).toList();
        break;
      case SignalDirectionFilter.sell:
        result = result.where((s) => !s.isBuy).toList();
        break;
      case SignalDirectionFilter.all:
        break;
    }

    // Confidence filter
    switch (filters.confidence) {
      case ConfidenceFilter.high:
        result = result.where((s) => s.confluenceScore >= 0.7).toList();
        break;
      case ConfidenceFilter.medium:
        result = result
            .where((s) => s.confluenceScore >= 0.4 && s.confluenceScore < 0.7)
            .toList();
        break;
      case ConfidenceFilter.low:
        result = result.where((s) => s.confluenceScore < 0.4).toList();
        break;
      case ConfidenceFilter.all:
        break;
    }

    // Timeframe filter
    if (filters.timeframe != null) {
      result =
          result.where((s) => s.timeframe == filters.timeframe).toList();
    }

    // Pair filter
    if (filters.pair != null) {
      result = result.where((s) => s.symbol == filters.pair).toList();
    }

    return result;
  }

  void _showFilterSheet(BuildContext context, WidgetRef ref) {
    final signals = ref.read(signalsListProvider).valueOrNull ?? [];
    final active = signals.where((s) => s.isActive).toList();
    final pairs = active.map((s) => s.symbol).toSet().toList()..sort();
    final timeframes = active
        .map((s) => s.timeframe)
        .whereType<String>()
        .toSet()
        .toList()
      ..sort();
    final current = ref.read(signalFiltersProvider);

    showModalBottomSheet(
      context: context,
      backgroundColor: AlphaStackApp.surfaceDark,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) {
        return StatefulBuilder(
          builder: (ctx, setSheetState) {
            return Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text('Advanced Filters',
                          style: Theme.of(ctx).textTheme.titleLarge),
                      TextButton(
                        onPressed: () {
                          ref.read(signalFiltersProvider.notifier).state =
                              const SignalFilters();
                          Navigator.pop(ctx);
                        },
                        child: const Text('Reset'),
                      ),
                    ],
                  ),
                  const SizedBox(height: 20),

                  // Pair filter
                  if (pairs.isNotEmpty) ...[
                    Text('Pair',
                        style: Theme.of(ctx)
                            .textTheme
                            .bodyMedium
                            ?.copyWith(fontWeight: FontWeight.w600)),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        _SheetChip(
                          label: 'All Pairs',
                          isActive: current.pair == null,
                          onTap: () {
                            ref.read(signalFiltersProvider.notifier).state =
                                current.copyWith(pair: null);
                            setSheetState(() {});
                          },
                        ),
                        ...pairs.map((p) => _SheetChip(
                              label: p,
                              isActive: current.pair == p,
                              onTap: () {
                                ref
                                    .read(signalFiltersProvider.notifier)
                                    .state = current.copyWith(pair: p);
                                setSheetState(() {});
                              },
                            )),
                      ],
                    ),
                    const SizedBox(height: 20),
                  ],

                  // Timeframe filter
                  if (timeframes.isNotEmpty) ...[
                    Text('Timeframe',
                        style: Theme.of(ctx)
                            .textTheme
                            .bodyMedium
                            ?.copyWith(fontWeight: FontWeight.w600)),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        _SheetChip(
                          label: 'All',
                          isActive: current.timeframe == null,
                          onTap: () {
                            ref.read(signalFiltersProvider.notifier).state =
                                current.copyWith(timeframe: null);
                            setSheetState(() {});
                          },
                        ),
                        ...timeframes.map((tf) => _SheetChip(
                              label: tf,
                              isActive: current.timeframe == tf,
                              onTap: () {
                                ref
                                    .read(signalFiltersProvider.notifier)
                                    .state = current.copyWith(timeframe: tf);
                                setSheetState(() {});
                              },
                            )),
                      ],
                    ),
                    const SizedBox(height: 20),
                  ],

                  // Apply button
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton(
                      onPressed: () => Navigator.pop(ctx),
                      child: const Text('Apply Filters'),
                    ),
                  ),
                  const SizedBox(height: 8),
                ],
              ),
            );
          },
        );
      },
    );
  }

  void _showSignalDetail(BuildContext context, Signal signal) {
    final isBuy = signal.isBuy;
    final directionColor =
        isBuy ? AlphaStackApp.accentGreen : AlphaStackApp.accentRed;

    showModalBottomSheet(
      context: context,
      backgroundColor: AlphaStackApp.surfaceDark,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) {
        return DraggableScrollableSheet(
          initialChildSize: 0.7,
          maxChildSize: 0.9,
          minChildSize: 0.4,
          expand: false,
          builder: (ctx, scrollController) {
            return ListView(
              controller: scrollController,
              padding: const EdgeInsets.all(24),
              children: [
                // Handle bar
                Center(
                  child: Container(
                    width: 40,
                    height: 4,
                    margin: const EdgeInsets.only(bottom: 20),
                    decoration: BoxDecoration(
                      color: AlphaStackApp.borderDark,
                      borderRadius: BorderRadius.circular(2),
                    ),
                  ),
                ),

                // Header
                Row(
                  children: [
                    Text(
                      signal.symbol,
                      style:
                          Theme.of(ctx).textTheme.headlineMedium?.copyWith(
                                fontWeight: FontWeight.w800,
                              ),
                    ),
                    const SizedBox(width: 10),
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: directionColor.withAlpha(30),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        isBuy ? 'BUY / LONG' : 'SELL / SHORT',
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w700,
                          color: directionColor,
                          letterSpacing: 0.5,
                        ),
                      ),
                    ),
                    const Spacer(),
                    if (signal.timeframe != null)
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 10, vertical: 4),
                        decoration: BoxDecoration(
                          color: AlphaStackApp.cardDark,
                          borderRadius: BorderRadius.circular(6),
                          border:
                              Border.all(color: AlphaStackApp.borderDark),
                        ),
                        child: Text(
                          signal.timeframe!,
                          style: Theme.of(ctx)
                              .textTheme
                              .bodyMedium
                              ?.copyWith(
                                fontWeight: FontWeight.w600,
                              ),
                        ),
                      ),
                  ],
                ),
                const SizedBox(height: 24),

                // Confluence score
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: AlphaStackApp.cardDark,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AlphaStackApp.borderDark),
                  ),
                  child: Row(
                    children: [
                      SizedBox(
                        width: 64,
                        height: 64,
                        child: CircularProgressIndicator(
                          value: signal.confluenceScore,
                          strokeWidth: 6,
                          backgroundColor: AlphaStackApp.borderDark,
                          valueColor: AlwaysStoppedAnimation(
                            _confluenceColor(signal.confluenceScore),
                          ),
                          strokeCap: StrokeCap.round,
                        ),
                      ),
                      const SizedBox(width: 16),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Confluence: ${signal.confluenceLabel}',
                              style: Theme.of(ctx)
                                  .textTheme
                                  .titleMedium
                                  ?.copyWith(
                                    fontWeight: FontWeight.w600,
                                    color: _confluenceColor(
                                        signal.confluenceScore),
                                  ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              '${(signal.confluenceScore * 100).toStringAsFixed(0)}% confidence · ${signal.factors.length} factors',
                              style: Theme.of(ctx)
                                  .textTheme
                                  .bodySmall
                                  ?.copyWith(
                                    color: AlphaStackApp.textSecondary,
                                  ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),

                // Price levels
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: AlphaStackApp.cardDark,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AlphaStackApp.borderDark),
                  ),
                  child: Column(
                    children: [
                      _DetailRow(
                          'Entry Price',
                          _formatPrice(signal.entryPrice ?? 0),
                          AlphaStackApp.textPrimary),
                      if (signal.targetPrice != null) ...[
                        const Divider(height: 16),
                        _DetailRow(
                            'Take Profit',
                            _formatPrice(signal.targetPrice!),
                            AlphaStackApp.accentGreen),
                      ],
                      if (signal.stopLoss != null) ...[
                        const Divider(height: 16),
                        _DetailRow('Stop Loss',
                            _formatPrice(signal.stopLoss!), AlphaStackApp.accentRed),
                      ],
                      if (signal.riskRewardRatio > 0) ...[
                        const Divider(height: 16),
                        _DetailRow(
                            'Risk/Reward',
                            '${signal.riskRewardRatio.toStringAsFixed(2)}x',
                            AlphaStackApp.accentBlue),
                      ],
                    ],
                  ),
                ),
                const SizedBox(height: 16),

                // Strategy & metadata
                if (signal.strategy != null)
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: AlphaStackApp.cardDark,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: AlphaStackApp.borderDark),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Strategy',
                            style: Theme.of(ctx)
                                .textTheme
                                .bodySmall
                                ?.copyWith(
                                  color: AlphaStackApp.textSecondary,
                                )),
                        const SizedBox(height: 4),
                        Text(signal.strategy!,
                            style: Theme.of(ctx)
                                .textTheme
                                .titleMedium
                                ?.copyWith(fontWeight: FontWeight.w600)),
                        if (signal.confidence > 0) ...[
                          const SizedBox(height: 8),
                          Text(
                              'AI Confidence: ${(signal.confidence * 100).toStringAsFixed(0)}%',
                              style: Theme.of(ctx)
                                  .textTheme
                                  .bodySmall
                                  ?.copyWith(
                                    color: AlphaStackApp.textSecondary,
                                  )),
                        ],
                      ],
                    ),
                  ),
                const SizedBox(height: 16),

                // Factors
                if (signal.factors.isNotEmpty)
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: AlphaStackApp.cardDark,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: AlphaStackApp.borderDark),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Confluence Factors',
                            style: Theme.of(ctx)
                                .textTheme
                                .bodySmall
                                ?.copyWith(
                                  color: AlphaStackApp.textSecondary,
                                )),
                        const SizedBox(height: 12),
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: signal.factors.map((f) {
                            return Container(
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 12, vertical: 6),
                              decoration: BoxDecoration(
                                color: AlphaStackApp.surfaceDark,
                                borderRadius: BorderRadius.circular(8),
                                border: Border.all(
                                    color: AlphaStackApp.borderDark,
                                    width: 0.5),
                              ),
                              child: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  const Icon(Icons.check_circle_outline,
                                      size: 14,
                                      color: AlphaStackApp.accentGreen),
                                  const SizedBox(width: 6),
                                  Text(f,
                                      style: Theme.of(ctx)
                                          .textTheme
                                          .bodySmall),
                                ],
                              ),
                            );
                          }).toList(),
                        ),
                      ],
                    ),
                  ),
                const SizedBox(height: 16),

                // Timestamps
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: AlphaStackApp.cardDark,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AlphaStackApp.borderDark),
                  ),
                  child: Column(
                    children: [
                      _DetailRow(
                          'Created',
                          DateFormat('MMM dd, yyyy HH:mm')
                              .format(signal.createdAt),
                          AlphaStackApp.textSecondary),
                      if (signal.expiresAt != null) ...[
                        const Divider(height: 16),
                        _DetailRow(
                            'Expires',
                            DateFormat('MMM dd, yyyy HH:mm')
                                .format(signal.expiresAt!),
                            signal.isExpired
                                ? AlphaStackApp.accentRed
                                : AlphaStackApp.textSecondary),
                      ],
                    ],
                  ),
                ),
                const SizedBox(height: 32),
              ],
            );
          },
        );
      },
    );
  }

  Widget _buildLoadingState() {
    return Column(
      children: [
        const SizedBox(height: 60),
        for (int i = 0; i < 4; i++)
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
            child: SkeletonCard(height: 140, margin: EdgeInsets.zero),
          ),
      ],
    );
  }

  static Color _confluenceColor(double score) {
    if (score >= 0.8) return AlphaStackApp.accentGreen;
    if (score >= 0.6) return const Color(0xFF7EE787);
    if (score >= 0.4) return AlphaStackApp.accentOrange;
    return AlphaStackApp.accentRed;
  }

  static String _formatPrice(double price) {
    if (price >= 1000) return '\$${price.toStringAsFixed(2)}';
    if (price >= 1) return '\$${price.toStringAsFixed(4)}';
    return '\$${price.toStringAsFixed(6)}';
  }

  String _friendlyError(Object error) {
    final msg = error.toString();
    if (msg.contains('not configured')) {
      return 'API keys not configured. Go to Settings → API Keys.';
    }
    return msg.replaceAll('Exception: ', '');
  }
}

// ─── Helper Widgets ─────────────────────────────────────────

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

class _FilterChipWidget extends StatelessWidget {
  final String label;
  final bool isActive;
  final VoidCallback onTap;
  final Color? activeColor;

  const _FilterChipWidget({
    required this.label,
    required this.isActive,
    required this.onTap,
    this.activeColor,
  });

  @override
  Widget build(BuildContext context) {
    final color = activeColor ?? AlphaStackApp.accentBlue;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4),
      child: FilterChip(
        selected: isActive,
        label: Text(label),
        onSelected: (_) => onTap(),
        selectedColor: color.withAlpha(40),
        checkmarkColor: color,
        labelStyle: TextStyle(
          color: isActive ? color : AlphaStackApp.textSecondary,
          fontSize: 12,
          fontWeight: isActive ? FontWeight.w600 : FontWeight.normal,
        ),
        side: BorderSide(
          color: isActive ? color : AlphaStackApp.borderDark,
        ),
        backgroundColor: AlphaStackApp.cardDark,
      ),
    );
  }
}

class _SheetChip extends StatelessWidget {
  final String label;
  final bool isActive;
  final VoidCallback onTap;

  const _SheetChip({
    required this.label,
    required this.isActive,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(
          color: isActive
              ? AlphaStackApp.accentBlue.withAlpha(30)
              : AlphaStackApp.cardDark,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(
            color: isActive
                ? AlphaStackApp.accentBlue
                : AlphaStackApp.borderDark,
          ),
        ),
        child: Text(
          label,
          style: TextStyle(
            color:
                isActive ? AlphaStackApp.accentBlue : AlphaStackApp.textSecondary,
            fontSize: 13,
            fontWeight: isActive ? FontWeight.w600 : FontWeight.normal,
          ),
        ),
      ),
    );
  }
}

class _DetailRow extends StatelessWidget {
  final String label;
  final String value;
  final Color valueColor;

  const _DetailRow(this.label, this.value, this.valueColor);

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label,
            style: theme.textTheme.bodyMedium
                ?.copyWith(color: AlphaStackApp.textSecondary)),
        Text(value,
            style: theme.textTheme.bodyMedium?.copyWith(
              color: valueColor,
              fontWeight: FontWeight.w600,
            )),
      ],
    );
  }
}
