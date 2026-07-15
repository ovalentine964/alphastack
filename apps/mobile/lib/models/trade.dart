import 'package:json_annotation/json_annotation.dart';

part 'trade.g.dart';

@JsonSerializable()
class Trade {
  final String id;
  final String symbol;
  @JsonKey(unknownEnumValue: TradeSide.long)
  final TradeSide side;
  @JsonKey(unknownEnumValue: TradeStatus.open)
  final TradeStatus status;
  @JsonKey(name: 'entry_price')
  final double entryPrice;
  @JsonKey(name: 'exit_price')
  final double? exitPrice;
  final double quantity;
  final double? pnl;
  @JsonKey(name: 'stop_loss')
  final double? stopLoss;
  @JsonKey(name: 'take_profit')
  final double? takeProfit;
  @JsonKey(name: 'strategy_id')
  final String? strategyId;
  @JsonKey(name: 'opened_at')
  final DateTime openedAt;
  @JsonKey(name: 'closed_at')
  final DateTime? closedAt;
  final String notes;

  const Trade({
    required this.id,
    required this.symbol,
    required this.side,
    required this.status,
    required this.entryPrice,
    this.exitPrice,
    required this.quantity,
    this.pnl,
    this.stopLoss,
    this.takeProfit,
    this.strategyId,
    required this.openedAt,
    this.closedAt,
    this.notes = '',
  });

  factory Trade.fromJson(Map<String, dynamic> json) => _$TradeFromJson(json);
  Map<String, dynamic> toJson() => _$TradeToJson(this);

  bool get isOpen => status == TradeStatus.open;
  bool get isClosed => status == TradeStatus.closed;
  bool get isProfit => (pnl ?? 0) > 0;
  bool get isLong => side == TradeSide.long;

  double get unrealizedPnl => pnl ?? 0;
  Duration get duration => (closedAt ?? DateTime.now()).difference(openedAt);

  /// Compute P&L percent from entry/exit prices when not provided by server.
  double? get pnlPercent {
    if (pnl == null) return null;
    final base = entryPrice * quantity;
    if (base == 0) return null;
    return (pnl! / base) * 100;
  }

  /// Backward-compat alias for UI screens that reference `strategy`.
  String? get strategy => strategyId;

  /// Backward-compat alias for UI screens that reference `signalId`.
  String? get signalId => null;
}

@JsonSerializable()
class Position {
  final String symbol;
  @JsonKey(unknownEnumValue: TradeSide.long)
  final TradeSide side;
  final double quantity;
  @JsonKey(name: 'entry_price')
  final double entryPrice;
  @JsonKey(name: 'current_price')
  final double currentPrice;
  @JsonKey(name: 'unrealized_pnl')
  final double unrealizedPnl;
  @JsonKey(name: 'unrealized_pnl_pct')
  final double unrealizedPnlPercent;
  @JsonKey(name: 'weight_pct')
  final double weightPct;

  const Position({
    required this.symbol,
    required this.side,
    required this.quantity,
    required this.entryPrice,
    required this.currentPrice,
    required this.unrealizedPnl,
    required this.unrealizedPnlPercent,
    this.weightPct = 0,
  });

  factory Position.fromJson(Map<String, dynamic> json) =>
      _$PositionFromJson(json);
  Map<String, dynamic> toJson() => _$PositionToJson(this);

  bool get isProfit => unrealizedPnl > 0;
  bool get isLong => side == TradeSide.long;
  double get positionValue => currentPrice * quantity;
}

enum TradeSide {
  @JsonValue('long')
  long,
  @JsonValue('short')
  short,
  @JsonValue('buy')
  buy,
  @JsonValue('sell')
  sell,
}

enum TradeStatus {
  @JsonValue('open')
  open,
  @JsonValue('closed')
  closed,
  @JsonValue('cancelled')
  cancelled,
  @JsonValue('pending')
  pending,
}
