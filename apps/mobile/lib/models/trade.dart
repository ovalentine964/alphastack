import 'package:json_annotation/json_annotation.dart';

part 'trade.g.dart';

@JsonSerializable()
class Trade {
  final String id;
  final String symbol;
  final TradeSide side;
  final TradeStatus status;
  final double entryPrice;
  final double? exitPrice;
  final double quantity;
  final double? pnl;
  final double? pnlPercent;
  final double? stopLoss;
  final double? takeProfit;
  final String? signalId;
  final String? strategy;
  final DateTime openedAt;
  final DateTime? closedAt;
  final Map<String, dynamic>? metadata;

  const Trade({
    required this.id,
    required this.symbol,
    required this.side,
    required this.status,
    required this.entryPrice,
    this.exitPrice,
    required this.quantity,
    this.pnl,
    this.pnlPercent,
    this.stopLoss,
    this.takeProfit,
    this.signalId,
    this.strategy,
    required this.openedAt,
    this.closedAt,
    this.metadata,
  });

  factory Trade.fromJson(Map<String, dynamic> json) => _$TradeFromJson(json);
  Map<String, dynamic> toJson() => _$TradeToJson(this);

  bool get isOpen => status == TradeStatus.open;
  bool get isClosed => status == TradeStatus.closed;
  bool get isProfit => (pnl ?? 0) > 0;
  bool get isLong => side == TradeSide.long;

  double get unrealizedPnl => pnl ?? 0;
  Duration get duration =>
      (closedAt ?? DateTime.now()).difference(openedAt);
}

@JsonSerializable()
class Position {
  final String symbol;
  final TradeSide side;
  final double entryPrice;
  final double currentPrice;
  final double quantity;
  final double unrealizedPnl;
  final double unrealizedPnlPercent;
  final double? stopLoss;
  final double? takeProfit;
  final DateTime openedAt;

  const Position({
    required this.symbol,
    required this.side,
    required this.entryPrice,
    required this.currentPrice,
    required this.quantity,
    required this.unrealizedPnl,
    required this.unrealizedPnlPercent,
    this.stopLoss,
    this.takeProfit,
    required this.openedAt,
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
