// ═══════════════════════════════════════════════════════════════
// AlphaStack Desktop — TypeScript Types
// Aligned with Python Pydantic models (orchestrator/state.py)
// ═══════════════════════════════════════════════════════════════

// ── Orchestrator / Agent Pipeline ────────────────────────────

export type SignalDirection = "long" | "short" | "flat";
export type RiskLevel = "low" | "medium" | "high" | "critical";
export type TradeAction = "buy" | "sell" | "hold" | "close";
export type OrderType = "market" | "limit" | "stop";
export type TradeStatus = "pending" | "approved" | "rejected" | "executed" | "failed";
export type MessageType = "info" | "warning" | "action" | "question" | "response";
export type NewsImpact = "low" | "medium" | "high" | "critical";

export interface OrchestratorSignal {
  symbol: string;
  side: SignalDirection;
  strength: number; // -1.0 … 1.0
  confluence_score: number; // 0.0 … 1.0
  timeframe: string;
  strategy: string;
  reasoning: string;
  stop_loss: number | null;
  take_profit: number | null;
  entry_price: number | null;
}

export interface TradeDecision {
  id: string;
  signal: OrchestratorSignal | null;
  action: TradeAction;
  symbol: string;
  quantity: number;
  price: number;
  order_type: OrderType;
  status: TradeStatus;
  approved_by: string;
  rejection_reason: string;
  broker: string;
}

export interface RiskStatus {
  drawdown_pct: number;
  daily_loss_pct: number;
  open_positions: number;
  max_positions: number;
  exposure_pct: number;
  correlation_risk: number;
  circuit_breaker_active: boolean;
  circuit_breaker_reason: string;
  risk_level: RiskLevel;
  warnings: string[];
}

export interface NewsAlert {
  id: string;
  headline: string;
  source: string;
  impact: NewsImpact;
  event_type: string;
  affected_symbols: string[];
  timestamp: string;
  recommendation: string;
}

export interface AgentMessage {
  from_agent: string;
  to_agent: string;
  content: string;
  message_type: MessageType;
  timestamp: string;
  metadata: Record<string, unknown>;
}

export interface AlphaStackState {
  market_data: Record<string, unknown>;
  current_symbol: string;
  current_timeframe: string;
  pipeline_context: Record<string, unknown>;
  signals: OrchestratorSignal[];
  trade_decisions: TradeDecision[];
  risk_status: RiskStatus;
  news_alerts: NewsAlert[];
  news_risk_adjustment: number;
  execution_log: Record<string, unknown>[];
  pending_orders: Record<string, unknown>[];
  pre_trade_reflection: Record<string, unknown>;
  performance_summary: Record<string, unknown>;
  strategy_adjustments: Record<string, unknown>[];
  agent_messages: AgentMessage[];
  should_continue: boolean;
  human_approval_required: boolean;
  human_feedback: string;
  error: string;
  run_id: string;
  started_at: string;
  current_node: string;
}

// ── Orchestrator Run Response ────────────────────────────────

export interface OrchestratorRunResult {
  signals: PipelineSignal[];
  risk_status: RiskStatus;
  trade_decisions: TradeDecision[];
  news_alerts: NewsAlert[];
  agent_messages: AgentMessage[];
  performance_summary: Record<string, unknown>;
  execution_log: Record<string, unknown>[];
}

// ── Pipeline Signal (from /signals endpoints) ────────────────

export interface PipelineSignal {
  id: string;
  symbol: string;
  direction: SignalDirection;
  strength: string; // "weak" | "moderate" | "strong" | "very_strong"
  strategy_id: string;
  confidence: number;
  entry_price: number;
  stop_loss: number | null;
  take_profit: number | number[] | null;
  risk_reward: number;
  confluence_score: number;
  reason: string;
  created_at: string;
  expires_at: string;
  is_active: boolean;
  component_scores?: Record<string, number>;
  session?: string;
  structure?: string;
  rsi?: number;
  patterns?: string[];
}

// ── Trade (from /trades endpoints) ───────────────────────────

export interface Trade {
  id: string;
  symbol: string;
  side: string; // "buy" | "sell" | "long" | "short"
  status: string; // "open" | "closed" | "pending"
  entry_price: number | null;
  exit_price: number | null;
  quantity: number;
  pnl: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  strategy_id: string;
  broker_order_id?: string;
  opened_at: string;
  closed_at: string | null;
  notes: string;
}

// ── Portfolio (from /portfolio endpoints) ────────────────────

export interface PortfolioPosition {
  symbol: string;
  side: string;
  quantity: number;
  entry_price: number;
  current_price: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  weight_pct: number;
}

export interface PortfolioSummary {
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

// ── Analytics ────────────────────────────────────────────────

export interface PerformanceMetrics {
  total_return_pct: number;
  sharpe_ratio: number;
  max_drawdown_pct: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  profit_factor: number;
  avg_trade_duration_hours: number;
  expectancy: number;
}

export interface EquityPoint {
  date: string;
  equity: number;
  drawdown_pct?: number;
}

export interface EquityCurveResponse {
  points: EquityPoint[];
  initial_capital: number;
  current_equity: number;
}

export interface PnlHistoryPoint {
  date: string;
  realized_pnl: number;
  cumulative_pnl: number;
  trade_count: number;
}

export interface WinRateData {
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

// ── Health / Status ──────────────────────────────────────────

export interface HealthResponse {
  status: string;
  version: string;
  uptime_seconds: number;
  binance_connected: boolean;
  btc_price: number;
  testnet_configured: boolean;
  oanda_connected: boolean;
  pipeline_available: boolean;
  orchestrator_available: boolean;
  agents: string[];
  event_bus: string;
  timestamp: string;
}

// ── Trading Loop ─────────────────────────────────────────────

export interface LoopStatus {
  running: boolean;
  state: Record<string, unknown>;
  config: Record<string, unknown>;
}

// ── AGI ──────────────────────────────────────────────────────

export interface AgiMemoryStats {
  total_episodes: number;
  lessons_learned: number;
  [key: string]: unknown;
}

// ── Market ───────────────────────────────────────────────────

export interface MarketTicker {
  symbol: string;
  price: number;
  change_24h?: number;
  volume_24h?: number;
  high_24h?: number;
  low_24h?: number;
  bid?: number;
  ask?: number;
  spread?: number;
  source?: string;
}

// ── WebSocket ────────────────────────────────────────────────

export interface WSMessage {
  type: string;
  channel?: string;
  data?: unknown;
  ts?: number;
}

export interface WSPriceUpdate {
  symbol: string;
  price: number;
  change?: number;
  volume?: number;
  bid?: number;
  ask?: number;
  spread?: number;
  source?: string;
}

// ── Settings ─────────────────────────────────────────────────

export interface AppSettings {
  notifications: {
    email_enabled: boolean;
    push_enabled: boolean;
    signal_alerts: boolean;
    trade_alerts: boolean;
  };
  display: {
    theme: string;
    language: string;
    timezone: string;
    currency: string;
  };
  risk: {
    max_position_size_pct: number;
    max_daily_loss_pct: number;
    max_drawdown_pct: number;
    auto_stop_loss: boolean;
  };
  trading: {
    default_order_type: string;
    confirmation_required: boolean;
    paper_trading: boolean;
  };
}

// ── Auth ─────────────────────────────────────────────────────

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: {
    id: string;
    username: string;
    plan: string;
  };
}

// ── Generic ──────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items?: T[];
  trades?: T[];
  signals?: T[];
  total: number;
  page: number;
  page_size: number;
}
