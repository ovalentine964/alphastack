// ── Portfolio ─────────────────────────────────────────────
export interface Portfolio {
  balance: number;
  equity: number;
  unrealizedPnl: number;
  realizedPnl: number;
  dayPnl: number;
  totalReturn: number;
}

// ── Position ─────────────────────────────────────────────
export interface Position {
  id: string;
  symbol: string;
  side: "LONG" | "SHORT";
  qty: number;
  entry: number;
  current: number;
  pnl: number;
  pnlPct: number;
  openedAt: string;
}

// ── Trade ────────────────────────────────────────────────
export interface Trade {
  id: string;
  symbol: string;
  side: "BUY" | "SELL";
  qty: number;
  price: number;
  pnl?: number;
  strategy: string;
  executedAt: string;
}

// ── Signal ───────────────────────────────────────────────
export interface Signal {
  id: string;
  symbol: string;
  direction: "LONG" | "SHORT";
  strategy: string;
  confidence: number;
  confluence: number;
  factors: string[];
  status: "active" | "expired" | "triggered";
  createdAt: string;
  expiresAt: string;
}

// ── Analytics ────────────────────────────────────────────
export interface PerformanceMetrics {
  totalTrades: number;
  winRate: number;
  sharpeRatio: number;
  maxDrawdown: number;
  profitFactor: number;
  avgWin: number;
  avgLoss: number;
  bestTrade: number;
  worstTrade: number;
  totalReturn: number;
  annualizedReturn: number;
  volatility: number;
}

export interface EquityPoint {
  date: string;
  equity: number;
}

export interface WinRateData {
  symbol: string;
  winRate: number;
  trades: number;
}

export interface RiskMetrics {
  valueAtRisk: number;
  maxDrawdown: number;
  currentDrawdown: number;
  beta: number;
  correlation: number;
  volatility: number;
  concentrationRisk: number;
}

// ── Settings ─────────────────────────────────────────────
export interface AppSettings {
  apiEndpoint: string;
  wsEndpoint: string;
  binanceApiKey: string;
  binanceApiSecret: string;
  useTestnet: boolean;
  mimoApiKey: string;
  maxPositionSize: number;
  maxDailyLoss: number;
  maxDrawdown: number;
  notificationsEnabled: boolean;
  autoRefresh: boolean;
}

// ── WebSocket ────────────────────────────────────────────
export interface WSMessage {
  channel?: string;
  type?: string;
  data?: unknown;
  ts?: number;
}

// ── API ──────────────────────────────────────────────────
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
}
