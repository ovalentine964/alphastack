// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'signal.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

Signal _$SignalFromJson(Map<String, dynamic> json) => Signal(
      id: json['id'] as String,
      symbol: json['symbol'] as String,
      direction: $enumDecode(_$SignalDirectionEnumMap, json['direction']),
      strength: $enumDecode(_$SignalStrengthEnumMap, json['strength'],
          unknownValue: SignalStrength.moderate),
      strategyId: json['strategy_id'] as String,
      confidence: (json['confidence'] as num).toDouble(),
      entryPrice: (json['entry_price'] as num?)?.toDouble(),
      stopLoss: (json['stop_loss'] as num?)?.toDouble(),
      takeProfit: (json['take_profit'] as num?)?.toDouble(),
      riskReward: (json['risk_reward'] as num?)?.toDouble(),
      reason: json['reason'] as String? ?? '',
      createdAt: DateTime.parse(json['created_at'] as String),
      expiresAt: json['expires_at'] == null
          ? null
          : DateTime.parse(json['expires_at'] as String),
      isActive: json['is_active'] as bool? ?? true,
    );

Map<String, dynamic> _$SignalToJson(Signal instance) => <String, dynamic>{
      'id': instance.id,
      'symbol': instance.symbol,
      'direction': _$SignalDirectionEnumMap[instance.direction]!,
      'strength': _$SignalStrengthEnumMap[instance.strength]!,
      'strategy_id': instance.strategyId,
      'confidence': instance.confidence,
      'entry_price': instance.entryPrice,
      'stop_loss': instance.stopLoss,
      'take_profit': instance.takeProfit,
      'risk_reward': instance.riskReward,
      'reason': instance.reason,
      'created_at': instance.createdAt.toIso8601String(),
      'expires_at': instance.expiresAt?.toIso8601String(),
      'is_active': instance.isActive,
    };

const _$SignalDirectionEnumMap = {
  SignalDirection.buy: 'buy',
  SignalDirection.sell: 'sell',
  SignalDirection.long: 'long',
  SignalDirection.short: 'short',
  SignalDirection.neutral: 'neutral',
};

const _$SignalStrengthEnumMap = {
  SignalStrength.weak: 'weak',
  SignalStrength.moderate: 'moderate',
  SignalStrength.strong: 'strong',
  SignalStrength.veryStrong: 'very_strong',
};

ConfluenceFactor _$ConfluenceFactorFromJson(Map<String, dynamic> json) =>
    ConfluenceFactor(
      name: json['name'] as String,
      weight: (json['weight'] as num).toDouble(),
      score: (json['score'] as num).toDouble(),
      description: json['description'] as String?,
    );

Map<String, dynamic> _$ConfluenceFactorToJson(ConfluenceFactor instance) =>
    <String, dynamic>{
      'name': instance.name,
      'weight': instance.weight,
      'score': instance.score,
      'description': instance.description,
    };

const _$SignalStatusEnumMap = {
  SignalStatus.active: 'active',
  SignalStatus.triggered: 'triggered',
  SignalStatus.expired: 'expired',
  SignalStatus.cancelled: 'cancelled',
};
