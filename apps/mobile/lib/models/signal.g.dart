// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'signal.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

Signal _$SignalFromJson(Map<String, dynamic> json) => Signal(
      id: json['id'] as String,
      symbol: json['symbol'] as String,
      direction: $enumDecode(_$SignalDirectionEnumMap, json['direction']),
      status: $enumDecode(_$SignalStatusEnumMap, json['status']),
      entryPrice: (json['entryPrice'] as num).toDouble(),
      targetPrice: (json['targetPrice'] as num?)?.toDouble(),
      stopLoss: (json['stopLoss'] as num?)?.toDouble(),
      confluenceScore: (json['confluenceScore'] as num).toDouble(),
      factors: (json['factors'] as List<dynamic>)
          .map((e) => e as String)
          .toList(),
      strategy: json['strategy'] as String?,
      timeframe: json['timeframe'] as String?,
      confidence: (json['confidence'] as num?)?.toDouble(),
      createdAt: DateTime.parse(json['createdAt'] as String),
      expiresAt: json['expiresAt'] == null
          ? null
          : DateTime.parse(json['expiresAt'] as String),
      triggeredAt: json['triggeredAt'] == null
          ? null
          : DateTime.parse(json['triggeredAt'] as String),
      metadata: json['metadata'] as Map<String, dynamic>?,
    );

Map<String, dynamic> _$SignalToJson(Signal instance) => <String, dynamic>{
      'id': instance.id,
      'symbol': instance.symbol,
      'direction': _$SignalDirectionEnumMap[instance.direction]!,
      'status': _$SignalStatusEnumMap[instance.status]!,
      'entryPrice': instance.entryPrice,
      'targetPrice': instance.targetPrice,
      'stopLoss': instance.stopLoss,
      'confluenceScore': instance.confluenceScore,
      'factors': instance.factors,
      'strategy': instance.strategy,
      'timeframe': instance.timeframe,
      'confidence': instance.confidence,
      'createdAt': instance.createdAt.toIso8601String(),
      'expiresAt': instance.expiresAt?.toIso8601String(),
      'triggeredAt': instance.triggeredAt?.toIso8601String(),
      'metadata': instance.metadata,
    };

const _$SignalDirectionEnumMap = {
  SignalDirection.buy: 'buy',
  SignalDirection.sell: 'sell',
  SignalDirection.long: 'long',
  SignalDirection.short: 'short',
};

const _$SignalStatusEnumMap = {
  SignalStatus.active: 'active',
  SignalStatus.triggered: 'triggered',
  SignalStatus.expired: 'expired',
  SignalStatus.cancelled: 'cancelled',
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
