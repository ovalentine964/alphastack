/**
 * TypeScript types aligned with AlphaStack Python Pydantic models.
 *
 * Source: src/alphastack/api/rest/routes/portfolio.py
 *         src/alphastack/api/rest/routes/trades.py
 *         src/alphastack/api/rest/routes/signals.py
 *         src/alphastack/api/rest/routes/analytics.py
 *         src/alphastack/api/rest/routes/system.py
 *         src/alphastack/api/rest/routes/settings.py
 *         src/alphastack/core/models.py
 */

// ─── Enums ────────────────────────────────────────────────────────────────────

export type Side = "buy" | "sell";
export type TradeStatus = "open" | "closed" | "cancelled" | "pending";
export type SignalDirection = "long" | "short" | "neutral";
export type SignalStrength = "weak" | "moderate" | "strong" | "very_strong";
export type PositionSide = "long" | "short" | "flat";

// ─── Portfolio ────────────────────────────────────────────────────────────────

export interface Position {
  symbol: string;
  side: PositionSide;
  quantity: number;
  entry_price: number;
  current_price: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  weight_pct: number;
}

export interface PnLSummary {
  total_realized_pnl: number;
  total_unrealized_pnl: number;
  total_pnl: number;
  today_pnl: number;
  win_rate: number;
  profit_factor: number;
  avg_win: number;
  avg_loss: number;
  best_trade_pnl: number;
  worst_trade_pnl: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
}

export interface PerformanceMetrics {
  total_return_pct: number;
  annualized_return_pct: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  max_drawdown_pct: number;
  calmar_ratio: number;
  volatility_annual_pct: number;
  avg_trade_duration_hours: number;
  expectancy: number;
  recovery_factor: number;
  start_date: string;
  end_date: string;
  trading_days: number;
}

// ─── Trades ───────────────────────────────────────────────────────────────────

export interface Trade {
  id: string;
  symbol: string;
  side: Side;
  quantity: number;
  entry_price: number | null;
  exit_price: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  status: TradeStatus;
  strategy_id: string | null;
  pnl: number | null;
  opened_at: string;
  closed_at: string | null;
  notes: string;
}

export interface TradeListResponse {
  trades: Trade[];
  total: number;
  page: number;
  page_size: number;
}

export interface TradeCreate {
  symbol: string;
  side: Side;
  quantity: number;
  price?: number;
  stop_loss?: number;
  take_profit?: number;
  strategy_id?: string;
  notes?: string;
}

// ─── Signals ──────────────────────────────────────────────────────────────────

export interface Signal {
  id: string;
  symbol: string;
  direction: SignalDirection;
  strength: SignalStrength;
  strategy_id: string;
  confidence: number;
  entry_price: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  risk_reward: number | null;
  reason: string;
  created_at: string;
  expires_at: string | null;
  is_active: boolean;
}

export interface SignalListResponse {
  signals: Signal[];
  total: number;
}

// ─── Analytics ────────────────────────────────────────────────────────────────

export interface EquityPoint {
  date: string;
  equity: number;
  drawdown_pct: number;
}

export interface EquityCurveResponse {
  points: EquityPoint[];
  initial_capital: number;
  current_equity: number;
}

export interface WinRateResponse {
  win_rate: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  breakeven_trades: number;
  avg_win: number;
  avg_loss: number;
  largest_win: number;
  largest_loss: number;
  profit_factor: number;
}

export interface PnlHistoryPoint {
  date: string;
  realized_pnl: number;
  cumulative_pnl: number;
  trade_count: number;
}

export interface RiskMetrics {
  max_drawdown_pct: number;
  current_drawdown_pct: number;
  var_95: number;
  var_99: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  avg_risk_per_trade: number;
  max_consecutive_losses: number;
  risk_reward_avg: number;
}

// ─── System ───────────────────────────────────────────────────────────────────

export interface HealthResponse {
  status: string;
  version: string;
  uptime_seconds: number;
  timestamp: string;
  checks: Record<string, string>;
}

export interface SystemStatus {
  platform: string;
  python_version: string;
  environment: string;
  uptime_seconds: number;
  components: Record<string, string>;
}

// ─── Settings ─────────────────────────────────────────────────────────────────

export interface AppSettings {
  notifications: {
    email_enabled: boolean;
    push_enabled: boolean;
    signal_alerts: boolean;
    trade_alerts: boolean;
    price_alerts: boolean;
  };
  display: {
    theme: string;
    language: string;
    timezone: string;
    currency: string;
    decimal_places: number;
  };
  risk: {
    max_position_size_pct: number;
    max_daily_loss_pct: number;
    max_drawdown_pct: number;
    auto_stop_loss: boolean;
    default_risk_reward: number;
  };
  trading: {
    default_order_type: string;
    confirmation_required: boolean;
    auto_close_on_target: boolean;
    paper_trading: boolean;
  };
}

export interface SettingsUpdateResponse {
  message: string;
  settings: AppSettings;
}

// ─── WebSocket ────────────────────────────────────────────────────────────────

export type WSChannel = "prices" | "trades" | "signals" | "system";

export interface WSAuthMessage {
  type: "auth";
  token: string;
}

export interface WSSubscribeMessage {
  type: "subscribe";
  channels: WSChannel[];
}

export interface WSUnsubscribeMessage {
  type: "unsubscribe";
  channels: WSChannel[];
}

export interface WSPingMessage {
  type: "ping";
}

export interface WSBroadcastMessage {
  channel: WSChannel;
  data: unknown;
  ts: number;
}

export interface WSControlMessage {
  type: string;
  [key: string]: unknown;
}

export type WSMessage = WSBroadcastMessage | WSControlMessage;

export interface PriceUpdate {
  symbol: string;
  price: number;
  bid: number;
  ask: number;
}

// ─── Orchestrator ─────────────────────────────────────────────────────────────

export interface OrchestratorHealth {
  status: string;
  error?: string;
  [key: string]: unknown;
}
