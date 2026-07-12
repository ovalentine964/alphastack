import 'package:json_annotation/json_annotation.dart';

part 'signal.g.dart';

@JsonSerializable()
class Signal {
  final String id;
  final String symbol;
  final SignalDirection direction;
  final SignalStatus status;
  final double entryPrice;
  final double? targetPrice;
  final double? stopLoss;
  final double confluenceScore;
  final List<String> factors;
  final String? strategy;
  final String? timeframe;
  final double? confidence;
  final DateTime createdAt;
  final DateTime? expiresAt;
  final DateTime? triggeredAt;
  final Map<String, dynamic>? metadata;

  const Signal({
    required this.id,
    required this.symbol,
    required this.direction,
    required this.status,
    required this.entryPrice,
    this.targetPrice,
    this.stopLoss,
    required this.confluenceScore,
    required this.factors,
    this.strategy,
    this.timeframe,
    this.confidence,
    required this.createdAt,
    this.expiresAt,
    this.triggeredAt,
    this.metadata,
  });

  factory Signal.fromJson(Map<String, dynamic> json) =>
      _$SignalFromJson(json);
  Map<String, dynamic> toJson() => _$SignalToJson(this);

  bool get isActive => status == SignalStatus.active;
  bool get isBuy => direction == SignalDirection.buy;
  bool get isExpired =>
      expiresAt != null && expiresAt!.isBefore(DateTime.now());

  double get riskRewardRatio {
    if (targetPrice == null || stopLoss == null) return 0;
    final reward = (targetPrice! - entryPrice).abs();
    final risk = (entryPrice - stopLoss!).abs();
    if (risk == 0) return 0;
    return reward / risk;
  }

  String get confluenceLabel {
    if (confluenceScore >= 0.8) return 'Very Strong';
    if (confluenceScore >= 0.6) return 'Strong';
    if (confluenceScore >= 0.4) return 'Moderate';
    if (confluenceScore >= 0.2) return 'Weak';
    return 'Very Weak';
  }
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
