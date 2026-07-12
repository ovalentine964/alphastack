// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'trade.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

Trade _$TradeFromJson(Map<String, dynamic> json) => Trade(
      id: json['id'] as String,
      symbol: json['symbol'] as String,
      side: $enumDecode(_$TradeSideEnumMap, json['side']),
      status: $enumDecode(_$TradeStatusEnumMap, json['status']),
      entryPrice: (json['entryPrice'] as num).toDouble(),
      exitPrice: (json['exitPrice'] as num?)?.toDouble(),
      quantity: (json['quantity'] as num).toDouble(),
      pnl: (json['pnl'] as num?)?.toDouble(),
      pnlPercent: (json['pnlPercent'] as num?)?.toDouble(),
      stopLoss: (json['stopLoss'] as num?)?.toDouble(),
      takeProfit: (json['takeProfit'] as num?)?.toDouble(),
      signalId: json['signalId'] as String?,
      strategy: json['strategy'] as String?,
      openedAt: DateTime.parse(json['openedAt'] as String),
      closedAt: json['closedAt'] == null
          ? null
          : DateTime.parse(json['closedAt'] as String),
      metadata: json['metadata'] as Map<String, dynamic>?,
    );

Map<String, dynamic> _$TradeToJson(Trade instance) => <String, dynamic>{
      'id': instance.id,
      'symbol': instance.symbol,
      'side': _$TradeSideEnumMap[instance.side]!,
      'status': _$TradeStatusEnumMap[instance.status]!,
      'entryPrice': instance.entryPrice,
      'exitPrice': instance.exitPrice,
      'quantity': instance.quantity,
      'pnl': instance.pnl,
      'pnlPercent': instance.pnlPercent,
      'stopLoss': instance.stopLoss,
      'takeProfit': instance.takeProfit,
      'signalId': instance.signalId,
      'strategy': instance.strategy,
      'openedAt': instance.openedAt.toIso8601String(),
      'closedAt': instance.closedAt?.toIso8601String(),
      'metadata': instance.metadata,
    };

const _$TradeSideEnumMap = {
  TradeSide.long: 'long',
  TradeSide.short: 'short',
};

const _$TradeStatusEnumMap = {
  TradeStatus.open: 'open',
  TradeStatus.closed: 'closed',
  TradeStatus.cancelled: 'cancelled',
  TradeStatus.pending: 'pending',
};

Position _$PositionFromJson(Map<String, dynamic> json) => Position(
      symbol: json['symbol'] as String,
      side: $enumDecode(_$TradeSideEnumMap, json['side']),
      entryPrice: (json['entryPrice'] as num).toDouble(),
      currentPrice: (json['currentPrice'] as num).toDouble(),
      quantity: (json['quantity'] as num).toDouble(),
      unrealizedPnl: (json['unrealizedPnl'] as num).toDouble(),
      unrealizedPnlPercent: (json['unrealizedPnlPercent'] as num).toDouble(),
      stopLoss: (json['stopLoss'] as num?)?.toDouble(),
      takeProfit: (json['takeProfit'] as num?)?.toDouble(),
      openedAt: DateTime.parse(json['openedAt'] as String),
    );

Map<String, dynamic> _$PositionToJson(Position instance) => <String, dynamic>{
      'symbol': instance.symbol,
      'side': _$TradeSideEnumMap[instance.side]!,
      'entryPrice': instance.entryPrice,
      'currentPrice': instance.currentPrice,
      'quantity': instance.quantity,
      'unrealizedPnl': instance.unrealizedPnl,
      'unrealizedPnlPercent': instance.unrealizedPnlPercent,
      'stopLoss': instance.stopLoss,
      'takeProfit': instance.takeProfit,
      'openedAt': instance.openedAt.toIso8601String(),
    };
