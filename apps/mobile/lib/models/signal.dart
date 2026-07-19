import 'package:json_annotation/json_annotation.dart';

part 'signal.g.dart';

@JsonSerializable()
class Signal {
  final String id;
  final String symbol;
  @JsonKey(name: 'direction', unknownEnumValue: SignalDirection.long)
  final SignalDirection direction;
  @JsonKey(name: 'strength', unknownEnumValue: SignalStrength.moderate)
  final SignalStrength strength;
  @JsonKey(name: 'strategy_id')
  final String strategyId;
  @JsonKey(defaultValue: 0.0)
  final double confidence;
  @JsonKey(name: 'entry_price')
  final double? entryPrice;
  @JsonKey(name: 'stop_loss')
  final double? stopLoss;
  @JsonKey(name: 'take_profit')
  final double? takeProfit;
  @JsonKey(name: 'risk_reward')
  final double? riskReward;
  @JsonKey(defaultValue: '')
  final String reason;
  @JsonKey(name: 'timeframe')
  final String? timeframe;
  @JsonKey(name: 'agent_id')
  final String? agentId;
  @JsonKey(name: 'created_at')
  final DateTime createdAt;
  @JsonKey(name: 'expires_at')
  final DateTime? expiresAt;
  @JsonKey(name: 'is_active', defaultValue: true)
  final bool isActive;

  const Signal({
    required this.id,
    required this.symbol,
    required this.direction,
    required this.strength,
    required this.strategyId,
    required this.confidence,
    this.entryPrice,
    this.stopLoss,
    this.takeProfit,
    this.riskReward,
    this.reason = '',
    this.timeframe,
    this.agentId,
    required this.createdAt,
    this.expiresAt,
    this.isActive = true,
  });

  factory Signal.fromJson(Map<String, dynamic> json) =>
      _$SignalFromJson(json);
  Map<String, dynamic> toJson() => _$SignalToJson(this);

  // ── Convenience getters for UI compatibility ──

  bool get isBuy =>
      direction == SignalDirection.long || direction == SignalDirection.buy;

  bool get isSell =>
      direction == SignalDirection.short || direction == SignalDirection.sell;

  bool get isExpired =>
      expiresAt != null && expiresAt!.isBefore(DateTime.now());

  /// Confluence score as 0–1 float (derived from strength enum).
  double get confluenceScore {
    switch (strength) {
      case SignalStrength.veryStrong:
        return 0.9;
      case SignalStrength.strong:
        return 0.7;
      case SignalStrength.moderate:
        return 0.5;
      case SignalStrength.weak:
        return 0.3;
    }
  }

  /// Human-readable confluence label.
  String get confluenceLabel {
    switch (strength) {
      case SignalStrength.veryStrong:
        return 'Very Strong';
      case SignalStrength.strong:
        return 'Strong';
      case SignalStrength.moderate:
        return 'Moderate';
      case SignalStrength.weak:
        return 'Weak';
    }
  }

  /// Risk/reward ratio (server provides it, or compute from prices).
  double get riskRewardRatio {
    if (riskReward != null && riskReward! > 0) return riskReward!;
    if (takeProfit == null || stopLoss == null || entryPrice == null) return 0;
    final reward = (takeProfit! - entryPrice!).abs();
    final risk = (entryPrice! - stopLoss!).abs();
    if (risk == 0) return 0;
    return reward / risk;
  }

  /// Factors list — the server provides `reason` as a single string.
  /// For UI compatibility we split by comma or return a single-item list.
  List<String> get factors {
    if (reason.isEmpty) return [];
    if (reason.contains(',')) {
      return reason
          .split(',')
          .map((s) => s.trim())
          .where((s) => s.isNotEmpty)
          .toList();
    }
    return [reason];
  }

  /// Backward-compat alias for UI screens that reference `targetPrice`.
  double? get targetPrice => takeProfit;

  /// Backward-compat alias for UI screens that reference `strategy`.
  String? get strategy => strategyId;
}

@JsonSerializable()
class ConfluenceFactor {
  final String name;
  final double weight;
  final double score;
  final String? description;

  const ConfluenceFactor({
    required this.name,
    required this.weight,
    required this.score,
    this.description,
  });

  factory ConfluenceFactor.fromJson(Map<String, dynamic> json) =>
      _$ConfluenceFactorFromJson(json);
  Map<String, dynamic> toJson() => _$ConfluenceFactorToJson(this);

  double get weightedScore => weight * score;
}

enum SignalDirection {
  @JsonValue('buy')
  buy,
  @JsonValue('sell')
  sell,
  @JsonValue('long')
  long,
  @JsonValue('short')
  short,
  @JsonValue('neutral')
  neutral,
}

enum SignalStrength {
  @JsonValue('weak')
  weak,
  @JsonValue('moderate')
  moderate,
  @JsonValue('strong')
  strong,
  @JsonValue('very_strong')
  veryStrong,
}

enum SignalStatus {
  @JsonValue('active')
  active,
  @JsonValue('triggered')
  triggered,
  @JsonValue('expired')
  expired,
  @JsonValue('cancelled')
  cancelled,
}
