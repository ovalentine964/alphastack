import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import '../app.dart';
import '../models/agent_status.dart';
import '../services/api_service.dart';
import '../services/websocket_service.dart';

// ─── Providers ───────────────────────────────────────────────────────────────

final agentHealthProvider = FutureProvider<AgentPipelineStatus>((ref) async {
  return await ApiService().getOrchestratorHealth();
});

final systemStatusProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  return await ApiService().getSystemStatus();
});

// ─── Screen ──────────────────────────────────────────────────────────────────

class AgentStatusScreen extends ConsumerStatefulWidget {
  const AgentStatusScreen({super.key});

  @override
  ConsumerState<AgentStatusScreen> createState() => _AgentStatusScreenState();
}

class _AgentStatusScreenState extends ConsumerState<AgentStatusScreen> {
  final _ws = WebSocketService();
  StreamSubscription? _agentSub;

  @override
  void initState() {
    super.initState();
    _agentSub = _ws.agentStatusUpdates.listen((data) {
      if (mounted) {
        // Refresh on system broadcast
        ref.invalidate(agentHealthProvider);
        ref.invalidate(systemStatusProvider);
      }
    });
  }

  @override
  void dispose() {
    _agentSub?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final agentHealth = ref.watch(agentHealthProvider);
    final systemStatus = ref.watch(systemStatusProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Pipeline Health'),
        actions: [
          IconButton(
            icon: const Icon(Icons.play_circle_outline_rounded, size: 22),
            tooltip: 'Trigger Pipeline Run',
            onPressed: () => _triggerPipeline(context),
          ),
          IconButton(
            icon: const Icon(Icons.sync_rounded, size: 22),
            onPressed: () {
              ref.invalidate(agentHealthProvider);
              ref.invalidate(systemStatusProvider);
            },
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(agentHealthProvider);
          ref.invalidate(systemStatusProvider);
        },
        color: AlphaStackApp.accentBlue,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            // Overall status banner
            agentHealth.when(
              data: (data) => _buildOverallStatus(data),
              loading: () => _buildSkeleton(height: 80),
              error: (e, _) => _buildConnectionError(e),
            ),
            const SizedBox(height: 16),

            // Agent cards
            agentHealth.when(
              data: (data) => _buildAgentGrid(context, data),
              loading: () => Column(
                children: List.generate(
                    5, (_) => Padding(
                          padding: const EdgeInsets.only(bottom: 8),
                          child: _buildSkeleton(height: 100),
                        )),
              ),
              error: (e, _) => const SizedBox.shrink(),
            ),
            const SizedBox(height: 16),

            // Orchestrator details
            agentHealth.when(
              data: (data) => _buildOrchestratorDetails(context, data.orchestrator),
              loading: () => const SizedBox.shrink(),
              error: (_, __) => const SizedBox.shrink(),
            ),
            const SizedBox(height: 16),

            // System info
            systemStatus.when(
              data: (data) => _buildSystemInfo(context, data),
              loading: () => const SizedBox.shrink(),
              error: (_, __) => const SizedBox.shrink(),
            ),
            const SizedBox(height: 80),
          ],
        ),
      ),
    );
  }

  Widget _buildOverallStatus(AgentPipelineStatus status) {
    Color color;
    IconData icon;
    String label;
    String subtitle;

    if (status.allHealthy) {
      color = AlphaStackApp.accentGreen;
      icon = Icons.check_circle_rounded;
      label = 'All Systems Operational';
      subtitle = '${status.agents.length} agents healthy';
    } else if (status.anyDead) {
      color = AlphaStackApp.accentRed;
      icon = Icons.error_rounded;
      label = 'Pipeline Degraded';
      subtitle = 'One or more agents unreachable';
    } else {
      color = AlphaStackApp.accentOrange;
      icon = Icons.warning_rounded;
      label = 'Partial Degradation';
      subtitle = 'Some agents experiencing issues';
    }

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            color.withAlpha(25),
            color.withAlpha(10),
          ],
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withAlpha(80)),
      ),
      child: Row(
        children: [
          Container(
            width: 48,
            height: 48,
            decoration: BoxDecoration(
              color: color.withAlpha(30),
              shape: BoxShape.circle,
            ),
            child: Icon(icon, color: color, size: 28),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w700,
                    color: color,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  subtitle,
                  style: TextStyle(
                    fontSize: 13,
                    color: AlphaStackApp.textSecondary,
                  ),
                ),
              ],
            ),
          ),
          // Live indicator
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(
              color: color,
              shape: BoxShape.circle,
              boxShadow: [
                BoxShadow(color: color.withAlpha(100), blurRadius: 6, spreadRadius: 2),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAgentGrid(BuildContext context, AgentPipelineStatus status) {
    return Column(
      children: [
        _AgentCard(
          name: 'News Agent',
          icon: Icons.newspaper_rounded,
          health: status.news,
        ),
        const SizedBox(height: 8),
        _AgentCard(
          name: 'Strategy Agent',
          icon: Icons.psychology_rounded,
          health: status.strategy,
        ),
        const SizedBox(height: 8),
        _AgentCard(
          name: 'Risk Agent',
          icon: Icons.shield_rounded,
          health: status.risk,
        ),
        const SizedBox(height: 8),
        _AgentCard(
          name: 'Execution Agent',
          icon: Icons.rocket_launch_rounded,
          health: status.execution,
        ),
        const SizedBox(height: 8),
        _AgentCard(
          name: 'Reflection Agent',
          icon: Icons.auto_awesome_rounded,
          health: status.reflection,
        ),
      ],
    );
  }

  Widget _buildOrchestratorDetails(BuildContext context, OrchestratorHealth orch) {
    final theme = Theme.of(context);
    final cb = orch.circuitBreaker;

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
          Row(
            children: [
              const Icon(Icons.hub_rounded, size: 18, color: AlphaStackApp.accentBlue),
              const SizedBox(width: 8),
              Text('Orchestrator', style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600)),
            ],
          ),
          const SizedBox(height: 16),
          _InfoRow('Human-in-the-Loop', orch.humanInTheLoop ? 'Enabled' : 'Disabled'),
          _InfoRow('HITL Threshold', '${(orch.hitlThreshold * 100).toStringAsFixed(0)}%'),
          if (cb != null) ...[
            const Divider(height: 20),
            Text('Circuit Breaker', style: theme.textTheme.bodySmall?.copyWith(color: AlphaStackApp.textSecondary)),
            const SizedBox(height: 8),
            _InfoRow('State', cb.state.toUpperCase(), _cbStateColor(cb.state)),
            _InfoRow('Failures', '${cb.failureCount} / ${cb.failureThreshold}'),
            _InfoRow('Successes', '${cb.successCount}'),
            if (cb.lastFailureAgeS != null)
              _InfoRow('Last Failure', '${cb.lastFailureAgeS!.toStringAsFixed(0)}s ago'),
          ],
        ],
      ),
    );
  }

  Widget _buildSystemInfo(BuildContext context, Map<String, dynamic> data) {
    final theme = Theme.of(context);
    final components = data['components'] as Map<String, dynamic>? ?? {};

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
          Row(
            children: [
              const Icon(Icons.dns_rounded, size: 18, color: AlphaStackApp.accentBlue),
              const SizedBox(width: 8),
              Text('System', style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600)),
            ],
          ),
          const SizedBox(height: 16),
          _InfoRow('Platform', '${data['platform'] ?? 'Unknown'}'),
          _InfoRow('Python', '${data['python_version'] ?? 'Unknown'}'),
          _InfoRow('Environment', '${data['environment'] ?? 'Unknown'}'),
          _InfoRow('Uptime', _formatUptime(data['uptime_seconds'])),
          if (components.isNotEmpty) ...[
            const Divider(height: 20),
            ...components.entries.map((e) =>
                _InfoRow(e.key, e.value.toString(), _componentColor(e.value.toString()))),
          ],
        ],
      ),
    );
  }

  Future<void> _triggerPipeline(BuildContext context) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AlphaStackApp.surfaceDark,
        title: const Text('Trigger Pipeline Run'),
        content: const Text('Run the full orchestrator pipeline for BTC/USDT (1h)?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          ElevatedButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Run')),
        ],
      ),
    );

    if (confirmed != true) return;

    try {
      final result = await ApiService().triggerPipelineRun();
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Pipeline triggered: ${result['status'] ?? 'started'}'),
            backgroundColor: AlphaStackApp.accentGreen,
          ),
        );
        // Refresh health data
        ref.invalidate(agentHealthProvider);
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed: $e'),
            backgroundColor: AlphaStackApp.accentRed,
          ),
        );
      }
    }
  }

  Widget _buildConnectionError(Object error) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AlphaStackApp.cardDark,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AlphaStackApp.accentRed.withAlpha(80)),
      ),
      child: Column(
        children: [
          const Icon(Icons.cloud_off_rounded, color: AlphaStackApp.accentRed, size: 32),
          const SizedBox(height: 8),
          const Text('Cannot reach orchestrator', style: TextStyle(fontWeight: FontWeight.w600)),
          const SizedBox(height: 4),
          Text(
            error.toString(),
            style: const TextStyle(color: AlphaStackApp.textSecondary, fontSize: 12),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 4),
          const Text(
            'Ensure the backend is running and connected.',
            style: TextStyle(color: AlphaStackApp.textSecondary, fontSize: 11),
          ),
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
    );
  }

  static Color _cbStateColor(String state) {
    switch (state) {
      case 'closed':
        return AlphaStackApp.accentGreen;
      case 'open':
        return AlphaStackApp.accentRed;
      case 'half_open':
        return AlphaStackApp.accentOrange;
      default:
        return AlphaStackApp.textSecondary;
    }
  }

  static Color _componentColor(String status) {
    if (status == 'healthy') return AlphaStackApp.accentGreen;
    if (status.contains('unhealthy')) return AlphaStackApp.accentRed;
    return AlphaStackApp.accentOrange;
  }

  static String _formatUptime(dynamic seconds) {
    if (seconds == null) return 'Unknown';
    final s = (seconds as num).toDouble();
    if (s < 60) return '${s.toStringAsFixed(0)}s';
    if (s < 3600) return '${(s / 60).toStringAsFixed(0)}m';
    if (s < 86400) return '${(s / 3600).toStringAsFixed(1)}h';
    return '${(s / 86400).toStringAsFixed(1)}d';
  }
}

// ─── Widgets ─────────────────────────────────────────────────────────────────

class _AgentCard extends StatelessWidget {
  final String name;
  final IconData icon;
  final AgentHealth health;

  const _AgentCard({
    required this.name,
    required this.icon,
    required this.health,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final statusColor = _statusColor(health.status);

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AlphaStackApp.cardDark,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AlphaStackApp.borderDark),
      ),
      child: Column(
        children: [
          Row(
            children: [
              Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(
                  color: statusColor.withAlpha(25),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(icon, size: 20, color: statusColor),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(name, style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600)),
                    Text(
                      health.displayName.isNotEmpty ? health.displayName : health.agentId,
                      style: theme.textTheme.bodySmall?.copyWith(color: AlphaStackApp.textSecondary),
                    ),
                  ],
                ),
              ),
              _StatusBadge(status: health.status),
            ],
          ),
          const SizedBox(height: 12),
          // Metrics row
          Row(
            children: [
              _MetricChip(
                label: 'Calls',
                value: '${health.totalCalls}',
                color: AlphaStackApp.accentBlue,
              ),
              const SizedBox(width: 8),
              _MetricChip(
                label: 'Failures',
                value: '${health.totalFailures}',
                color: health.totalFailures > 0 ? AlphaStackApp.accentRed : AlphaStackApp.textSecondary,
              ),
              const SizedBox(width: 8),
              _MetricChip(
                label: 'Avg Latency',
                value: '${health.avgLatencyMs.toStringAsFixed(0)}ms',
                color: AlphaStackApp.accentOrange,
              ),
              const SizedBox(width: 8),
              _MetricChip(
                label: 'Uptime',
                value: _formatDuration(health.uptime),
                color: AlphaStackApp.textSecondary,
              ),
            ],
          ),
          // Success rate bar
          if (health.totalCalls > 0) ...[
            const SizedBox(height: 12),
            Row(
              children: [
                Text(
                  'Success Rate',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: AlphaStackApp.textSecondary,
                    fontSize: 11,
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(3),
                    child: LinearProgressIndicator(
                      value: health.successRate / 100,
                      backgroundColor: AlphaStackApp.borderDark,
                      valueColor: AlwaysStoppedAnimation(
                        health.successRate >= 95
                            ? AlphaStackApp.accentGreen
                            : health.successRate >= 80
                                ? AlphaStackApp.accentOrange
                                : AlphaStackApp.accentRed,
                      ),
                      minHeight: 4,
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  '${health.successRate.toStringAsFixed(1)}%',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: AlphaStackApp.textSecondary,
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }

  static Color _statusColor(String status) {
    switch (status) {
      case 'healthy':
        return AlphaStackApp.accentGreen;
      case 'degraded':
        return AlphaStackApp.accentOrange;
      case 'dead':
      case 'unhealthy':
        return AlphaStackApp.accentRed;
      default:
        return AlphaStackApp.textSecondary;
    }
  }

  static String _formatDuration(Duration d) {
    if (d.inDays > 0) return '${d.inDays}d';
    if (d.inHours > 0) return '${d.inHours}h';
    if (d.inMinutes > 0) return '${d.inMinutes}m';
    return '${d.inSeconds}s';
  }
}

class _StatusBadge extends StatelessWidget {
  final String status;

  const _StatusBadge({required this.status});

  @override
  Widget build(BuildContext context) {
    Color color;
    String label;

    switch (status) {
      case 'healthy':
        color = AlphaStackApp.accentGreen;
        label = 'HEALTHY';
        break;
      case 'degraded':
        color = AlphaStackApp.accentOrange;
        label = 'DEGRADED';
        break;
      case 'dead':
      case 'unhealthy':
        color = AlphaStackApp.accentRed;
        label = 'DOWN';
        break;
      default:
        color = AlphaStackApp.textSecondary;
        label = status.toUpperCase();
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withAlpha(25),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: color.withAlpha(80)),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 10,
          fontWeight: FontWeight.w700,
          color: color,
          letterSpacing: 0.5,
        ),
      ),
    );
  }
}

class _MetricChip extends StatelessWidget {
  final String label;
  final String value;
  final Color color;

  const _MetricChip({
    required this.label,
    required this.value,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Column(
        children: [
          Text(
            value,
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: color,
            ),
          ),
          Text(
            label,
            style: const TextStyle(
              fontSize: 10,
              color: AlphaStackApp.textSecondary,
            ),
          ),
        ],
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  final String label;
  final String value;
  final Color? valueColor;

  const _InfoRow(this.label, this.value, [this.valueColor]);

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: theme.textTheme.bodyMedium?.copyWith(color: AlphaStackApp.textSecondary)),
          Text(
            value,
            style: theme.textTheme.bodyMedium?.copyWith(
              color: valueColor ?? AlphaStackApp.textPrimary,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}
