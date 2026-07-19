/**
 * API client for AlphaStack backend.
 *
 * All requests go through Next.js server-side API proxy routes
 * (src/app/api/...) which forward to the Python backend.
 *
 * Backend API prefix: /api/v1/ for most routes, / for system routes.
 */

import type {
  Position,
  PnLSummary,
  PerformanceMetrics,
  Trade,
  TradeListResponse,
  TradeCreate,
  Signal,
  SignalListResponse,
  EquityCurveResponse,
  WinRateResponse,
  PnlHistoryPoint,
  RiskMetrics,
  HealthResponse,
  SystemStatus,
  AppSettings,
  SettingsUpdateResponse,
  OrchestratorHealth,
} from "@/types";

// ─── Base request helper ──────────────────────────────────────────────────────

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });

  if (!res.ok) {
    let msg: string;
    try {
      const body = await res.json();
      msg = body.detail || body.message || JSON.stringify(body);
    } catch {
      msg = await res.text().catch(() => "");
    }
    throw new Error(`API ${res.status}: ${msg}`);
  }

  return res.json();
}

// ─── Portfolio ────────────────────────────────────────────────────────────────

/** Current open positions. */
export const getPositions = (): Promise<Position[]> =>
  request("/api/portfolio");

/** P&L summary across all trades. */
export const getPortfolioPnl = (): Promise<PnLSummary> =>
  request("/api/portfolio/pnl");

/** Portfolio performance metrics. */
export const getPerformance = (): Promise<PerformanceMetrics> =>
  request("/api/portfolio/performance");

// ─── Trades ───────────────────────────────────────────────────────────────────

/** List trades with pagination and optional filters. */
export const getTrades = (params?: {
  page?: number;
  page_size?: number;
  status?: string;
  symbol?: string;
}): Promise<TradeListResponse> => {
  const qs = new URLSearchParams();
  if (params?.page) qs.set("page", String(params.page));
  if (params?.page_size) qs.set("page_size", String(params.page_size));
  if (params?.status) qs.set("status", params.status);
  if (params?.symbol) qs.set("symbol", params.symbol);
  const query = qs.toString();
  return request(`/api/trades${query ? `?${query}` : ""}`);
};

/** Get a single trade by ID. */
export const getTrade = (id: string): Promise<Trade> =>
  request(`/api/trades/${id}`);

/** Create a new trade. */
export const createTrade = (data: TradeCreate): Promise<Trade> =>
  request("/api/trades", {
    method: "POST",
    body: JSON.stringify(data),
  });

/** Close an open trade. */
export const closeTrade = (
  id: string,
  exitPrice?: number
): Promise<Trade> => {
  const qs = exitPrice != null ? `?exit_price=${exitPrice}` : "";
  return request(`/api/trades/${id}/close${qs}`, { method: "PUT" });
};

// ─── Signals ──────────────────────────────────────────────────────────────────

/** List active signals. */
export const getSignals = (params?: {
  symbol?: string;
  strategy_id?: string;
}): Promise<SignalListResponse> => {
  const qs = new URLSearchParams();
  if (params?.symbol) qs.set("symbol", params.symbol);
  if (params?.strategy_id) qs.set("strategy_id", params.strategy_id);
  const query = qs.toString();
  return request(`/api/signals${query ? `?${query}` : ""}`);
};

/** Signal history (all signals). */
export const getSignalHistory = (params?: {
  page?: number;
  page_size?: number;
  symbol?: string;
}): Promise<SignalListResponse> => {
  const qs = new URLSearchParams();
  if (params?.page) qs.set("page", String(params.page));
  if (params?.page_size) qs.set("page_size", String(params.page_size));
  if (params?.symbol) qs.set("symbol", params.symbol);
  const query = qs.toString();
  return request(`/api/signals/history${query ? `?${query}` : ""}`);
};

// ─── Analytics ────────────────────────────────────────────────────────────────

/** Performance metrics (delegates to portfolio performance). */
export const getAnalyticsPerformance = (): Promise<PerformanceMetrics> =>
  request("/api/analytics/performance");

/** Equity curve over time. */
export const getEquityCurve = (
  days = 90
): Promise<EquityCurveResponse> =>
  request(`/api/analytics/equity-curve?days=${days}`);

/** Win/loss statistics. */
export const getWinRate = (): Promise<WinRateResponse> =>
  request("/api/analytics/win-rate");

/** Daily PnL history. */
export const getPnlHistory = (period = "30d"): Promise<PnlHistoryPoint[]> =>
  request(`/api/analytics/pnl-history?period=${period}`);

/** Risk analytics. */
export const getRiskMetrics = (): Promise<RiskMetrics> =>
  request("/api/analytics/risk");

// ─── Settings ─────────────────────────────────────────────────────────────────

/** Get current runtime settings. */
export const getSettings = (): Promise<AppSettings> =>
  request("/api/settings");

/** Update runtime settings (partial). */
export const updateSettings = (
  data: Partial<AppSettings>
): Promise<SettingsUpdateResponse> =>
  request("/api/settings", {
    method: "PUT",
    body: JSON.stringify(data),
  });

// ─── System ───────────────────────────────────────────────────────────────────

/** Health check. */
export const getHealth = (): Promise<HealthResponse> =>
  request("/api/system/health");

/** System status. */
export const getSystemStatus = (): Promise<SystemStatus> =>
  request("/api/system/status");

/** Orchestrator health. */
export const getOrchestratorHealth = (): Promise<OrchestratorHealth> =>
  request("/api/system/orchestrator/health");

/** Trigger orchestrator run. */
export const triggerOrchestratorRun = (data: {
  symbol?: string;
  timeframe?: string;
  market_data?: Record<string, unknown>;
}): Promise<unknown> =>
  request("/api/system/orchestrator/run", {
    method: "POST",
    body: JSON.stringify(data),
  });
