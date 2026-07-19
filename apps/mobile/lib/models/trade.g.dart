// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'trade.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

Trade _$TradeFromJson(Map<String, dynamic> json) => Trade(
      id: json['id'] as String,
      symbol: json['symbol'] as String,
      side: $enumDecode(_$TradeSideEnumMap, json['side'],
          unknownValue: TradeSide.buy),
      status: $enumDecode(_$TradeStatusEnumMap, json['status'],
          unknownValue: TradeStatus.open),
      entryPrice: (json['entry_price'] as num?)?.toDouble(),
      exitPrice: (json['exit_price'] as num?)?.toDouble(),
      quantity: (json['quantity'] as num).toDouble(),
      pnl: (json['pnl'] as num?)?.toDouble(),
      stopLoss: (json['stop_loss'] as num?)?.toDouble(),
      takeProfit: (json['take_profit'] as num?)?.toDouble(),
      strategyId: json['strategy_id'] as String?,
      openedAt: DateTime.parse(json['opened_at'] as String),
      closedAt: json['closed_at'] == null
          ? null
          : DateTime.parse(json['closed_at'] as String),
      notes: json['notes'] as String? ?? '',
    );

Map<String, dynamic> _$TradeToJson(Trade instance) => <String, dynamic>{
      'id': instance.id,
      'symbol': instance.symbol,
      'side': _$TradeSideEnumMap[instance.side]!,
      'status': _$TradeStatusEnumMap[instance.status]!,
      'entry_price': instance.entryPrice,
      'exit_price': instance.exitPrice,
      'quantity': instance.quantity,
      'pnl': instance.pnl,
      'stop_loss': instance.stopLoss,
      'take_profit': instance.takeProfit,
      'strategy_id': instance.strategyId,
      'opened_at': instance.openedAt.toIso8601String(),
      'closed_at': instance.closedAt?.toIso8601String(),
      'notes': instance.notes,
    };

const _$TradeSideEnumMap = {
  TradeSide.buy: 'buy',
  TradeSide.sell: 'sell',
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
      side: $enumDecode(_$TradeSideEnumMap, json['side'],
          unknownValue: TradeSide.buy),
      quantity: (json['quantity'] as num).toDouble(),
      entryPrice: (json['entry_price'] as num).toDouble(),
      currentPrice: (json['current_price'] as num).toDouble(),
      unrealizedPnl: (json['unrealized_pnl'] as num).toDouble(),
      unrealizedPnlPercent: (json['unrealized_pnl_pct'] as num).toDouble(),
      weightPct: (json['weight_pct'] as num?)?.toDouble() ?? 0,
    );

Map<String, dynamic> _$PositionToJson(Position instance) => <String, dynamic>{
      'symbol': instance.symbol,
      'side': _$TradeSideEnumMap[instance.side]!,
      'quantity': instance.quantity,
      'entry_price': instance.entryPrice,
      'current_price': instance.currentPrice,
      'unrealized_pnl': instance.unrealizedPnl,
      'unrealized_pnl_pct': instance.unrealizedPnlPercent,
      'weight_pct': instance.weightPct,
    };

TradeCreate _$TradeCreateFromJson(Map<String, dynamic> json) => TradeCreate(
      symbol: json['symbol'] as String,
      side: json['side'] as String,
      quantity: (json['quantity'] as num).toDouble(),
      price: (json['price'] as num?)?.toDouble(),
      stopLoss: (json['stop_loss'] as num?)?.toDouble(),
      takeProfit: (json['take_profit'] as num?)?.toDouble(),
      strategyId: json['strategy_id'] as String?,
      notes: json['notes'] as String? ?? '',
    );

Map<String, dynamic> _$TradeCreateToJson(TradeCreate instance) =>
    <String, dynamic>{
      'symbol': instance.symbol,
      'side': instance.side,
      'quantity': instance.quantity,
      'price': instance.price,
      'stop_loss': instance.stopLoss,
      'take_profit': instance.takeProfit,
      'strategy_id': instance.strategyId,
      'notes': instance.notes,
    };
