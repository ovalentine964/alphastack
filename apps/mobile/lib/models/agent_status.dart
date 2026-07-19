import 'package:json_annotation/json_annotation.dart';

part 'agent_status.g.dart';

/// Represents the health status of the entire AlphaStack orchestrator pipeline.
@JsonSerializable()
class AgentPipelineStatus {
  final OrchestratorHealth orchestrator;
  final AgentHealth news;
  final AgentHealth strategy;
  final AgentHealth risk;
  final AgentHealth execution;
  final AgentHealth reflection;

  const AgentPipelineStatus({
    required this.orchestrator,
    required this.news,
    required this.strategy,
    required this.risk,
    required this.execution,
    required this.reflection,
  });

  factory AgentPipelineStatus.fromJson(Map<String, dynamic> json) =>
      _$AgentPipelineStatusFromJson(json);
  Map<String, dynamic> toJson() => _$AgentPipelineStatusToJson(this);

  /// All agents healthy?
  bool get allHealthy =>
      news.isHealthy &&
      strategy.isHealthy &&
      risk.isHealthy &&
      execution.isHealthy &&
      reflection.isHealthy;

  /// Any agent degraded?
  bool get anyDegraded =>
      news.isDegraded ||
      strategy.isDegraded ||
      risk.isDegraded ||
      execution.isDegraded ||
      reflection.isDegraded;

  /// Any agent dead/unhealthy?
  bool get anyDead =>
      news.isDead || strategy.isDead || risk.isDead || execution.isDead || reflection.isDead;

  /// Overall pipeline status.
  String get overallStatus {
    if (anyDead) return 'unhealthy';
    if (anyDegraded) return 'degraded';
    return 'healthy';
  }

  /// List of all agents for iteration.
  List<AgentHealth> get agents => [news, strategy, risk, execution, reflection];
}

/// Orchestrator-level health info.
@JsonSerializable()
class OrchestratorHealth {
  @JsonKey(name: 'circuit_breaker')
  final CircuitBreakerInfo? circuitBreaker;
  @JsonKey(name: 'human_in_the_loop', defaultValue: false)
  final bool humanInTheLoop;
  @JsonKey(name: 'hitl_threshold', defaultValue: 0.8)
  final double hitlThreshold;

  const OrchestratorHealth({
    this.circuitBreaker,
    this.humanInTheLoop = false,
    this.hitlThreshold = 0.8,
  });

  factory OrchestratorHealth.fromJson(Map<String, dynamic> json) =>
      _$OrchestratorHealthFromJson(json);
  Map<String, dynamic> toJson() => _$OrchestratorHealthToJson(this);
}

@JsonSerializable()
class CircuitBreakerInfo {
  @JsonKey(defaultValue: '')
  final String name;
  @JsonKey(defaultValue: 'closed')
  final String state;
  @JsonKey(name: 'failure_count', defaultValue: 0)
  final int failureCount;
  @JsonKey(name: 'success_count', defaultValue: 0)
  final int successCount;
  @JsonKey(name: 'failure_threshold', defaultValue: 5)
  final int failureThreshold;
  @JsonKey(name: 'recovery_timeout', defaultValue: 60)
  final int recoveryTimeout;
  @JsonKey(name: 'last_failure_age_s')
  final double? lastFailureAgeS;

  const CircuitBreakerInfo({
    this.name = '',
    this.state = 'closed',
    this.failureCount = 0,
    this.successCount = 0,
    this.failureThreshold = 5,
    this.recoveryTimeout = 60,
    this.lastFailureAgeS,
  });

  factory CircuitBreakerInfo.fromJson(Map<String, dynamic> json) =>
      _$CircuitBreakerInfoFromJson(json);
  Map<String, dynamic> toJson() => _$CircuitBreakerInfoToJson(this);

  bool get isClosed => state == 'closed';
  bool get isOpen => state == 'open';
  bool get isHalfOpen => state == 'half_open';
}

/// Individual agent health status.
@JsonSerializable()
class AgentHealth {
  @JsonKey(name: 'agent_id', defaultValue: '')
  final String agentId;
  @JsonKey(name: 'agent_name', defaultValue: '')
  final String agentName;
  @JsonKey(defaultValue: 'healthy')
  final String status;
  @JsonKey(name: 'last_heartbeat')
  final DateTime? lastHeartbeat;
  @JsonKey(name: 'last_success')
  final DateTime? lastSuccess;
  @JsonKey(name: 'last_failure')
  final DateTime? lastFailure;
  @JsonKey(name: 'consecutive_failures', defaultValue: 0)
  final int consecutiveFailures;
  @JsonKey(name: 'total_calls', defaultValue: 0)
  final int totalCalls;
  @JsonKey(name: 'total_failures', defaultValue: 0)
  final int totalFailures;
  @JsonKey(name: 'avg_latency_ms', defaultValue: 0.0)
  final double avgLatencyMs;
  @JsonKey(name: 'p99_latency_ms', defaultValue: 0.0)
  final double p99LatencyMs;
  @JsonKey(name: 'circuit_breaker_state', defaultValue: 'closed')
  final String circuitBreakerState;
  @JsonKey(name: 'uptime_seconds', defaultValue: 0.0)
  final double uptimeSeconds;

  const AgentHealth({
    this.agentId = '',
    this.agentName = '',
    this.status = 'healthy',
    this.lastHeartbeat,
    this.lastSuccess,
    this.lastFailure,
    this.consecutiveFailures = 0,
    this.totalCalls = 0,
    this.totalFailures = 0,
    this.avgLatencyMs = 0.0,
    this.p99LatencyMs = 0.0,
    this.circuitBreakerState = 'closed',
    this.uptimeSeconds = 0.0,
  });

  factory AgentHealth.fromJson(Map<String, dynamic> json) =>
      _$AgentHealthFromJson(json);
  Map<String, dynamic> toJson() => _$AgentHealthToJson(this);

  bool get isHealthy => status == 'healthy';
  bool get isDegraded => status == 'degraded';
  bool get isDead => status == 'dead' || status == 'unhealthy';

  double get successRate =>
      totalCalls > 0 ? ((totalCalls - totalFailures) / totalCalls) * 100 : 100.0;

  String get displayName =>
      agentName.isNotEmpty ? agentName : agentId;

  Duration get uptime => Duration(seconds: uptimeSeconds.round());
}
