import { tauriBridge } from "./tauri-bridge";
import type {
  HealthResponse,
  OrchestratorRunResult,
  PipelineSignal,
  Trade,
  PortfolioPosition,
  PortfolioSummary,
  PerformanceMetrics,
  EquityCurveResponse,
  PnlHistoryPoint,
  WinRateData,
  RiskMetrics,
  AppSettings,
  LoopStatus,
  AgiMemoryStats,
  MarketTicker,
  AuthTokens,
} from "./types";

/**
 * AlphaStack REST API client for the Tauri desktop app.
 * Wired to the refactored Python backend (live_server.py).
 *
 * Endpoints:
 *   /health                          — system health
 *   /orchestrator/run                — full 5-agent pipeline
 *   /api/v1/signals[/active]         — pipeline signals
 *   /api/v1/trades                   — trade CRUD
 *   /api/v1/portfolio[/summary|pnl]  — portfolio data
 *   /api/v1/analytics/*              — performance, equity, risk
 *   /api/v1/loop/*                   — trading loop control
 *   /api/v1/agi/*                    — AGI memory & planning
 *   /api/v1/settings                 — app settings
 *   /api/v1/auth/*                   — JWT auth
 */
class ApiClient {
  private _baseUrl = "http://localhost:8000";
  private _token: string | null = null;
  private _refreshToken: string | null = null;

  async init(): Promise<void> {
    const saved = await tauriBridge.getSetting<string>("apiEndpoint");
    if (saved) this._baseUrl = saved.replace(/\/+$/, "");
    const token = await tauriBridge.getSetting<string>("authToken");
    if (token) this._token = token;
    const refresh = await tauriBridge.getSetting<string>("refreshToken");
    if (refresh) this._refreshToken = refresh;
  }

  get baseUrl(): string {
    return this._baseUrl;
  }

  setBaseUrl(url: string): void {
    this._baseUrl = url.replace(/\/+$/, "");
  }

  get token(): string | null {
    return this._token;
  }

  setTokens(tokens: AuthTokens): void {
    this._token = tokens.access_token;
    this._refreshToken = tokens.refresh_token;
    tauriBridge.setSetting("authToken", tokens.access_token).catch(() => {});
    tauriBridge.setSetting("refreshToken", tokens.refresh_token).catch(() => {});
  }

  clearAuth(): void {
    this._token = null;
    this._refreshToken = null;
    tauriBridge.deleteSetting("authToken").catch(() => {});
    tauriBridge.deleteSetting("refreshToken").catch(() => {});
  }

  // ── Core request helper ──────────────────────────────────

  private async request<T>(path: string, options?: RequestInit): Promise<T> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...((options?.headers as Record<string, string>) ?? {}),
    };
    if (this._token) headers["Authorization"] = `Bearer ${this._token}`;

    const res = await fetch(`${this._baseUrl}${path}`, {
      ...options,
      headers,
    });

    // Auto-refresh on 401
    if (res.status === 401 && this._refreshToken) {
      const refreshed = await this.tryRefresh();
      if (refreshed) {
        headers["Authorization"] = `Bearer ${this._token}`;
        const retry = await fetch(`${this._baseUrl}${path}`, {
          ...options,
          headers,
        });
        if (!retry.ok) {
          const body = await retry.text().catch(() => "");
          throw new Error(`API ${retry.status}: ${body || retry.statusText}`);
        }
        return retry.json();
      }
    }

    if (!res.ok) {
      const body = await res.text().catch(() => "");
      throw new Error(`API ${res.status}: ${body || res.statusText}`);
    }
    return res.json();
  }

  private async tryRefresh(): Promise<boolean> {
    if (!this._refreshToken) return false;
    try {
      const res = await fetch(`${this._baseUrl}/api/v1/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: this._refreshToken }),
      });
      if (!res.ok) return false;
      const data: AuthTokens = await res.json();
      this.setTokens(data);
      return true;
    } catch {
      return false;
    }
  }

  // ── Auth ──────────────────────────────────────────────────

  async login(username: string, password: string): Promise<AuthTokens> {
    const data = await this.request<AuthTokens>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
    this.setTokens(data);
    return data;
  }

  async demoLogin(): Promise<AuthTokens> {
    const data = await this.request<AuthTokens>("/api/v1/auth/demo", {
      method: "POST",
    });
    this.setTokens(data);
    return data;
  }

  async logout(): Promise<void> {
    try {
      await this.request("/api/v1/auth/logout", { method: "POST" });
    } catch {
      // ignore logout errors
    }
    this.clearAuth();
  }

  // ── Health ────────────────────────────────────────────────

  async getHealth(): Promise<HealthResponse> {
    return this.request("/health");
  }

  // ── Orchestrator ──────────────────────────────────────────

  async runOrchestrator(symbol = "BTC/USDT"): Promise<OrchestratorRunResult> {
    return this.request(`/api/v1/orchestrator/run?symbol=${encodeURIComponent(symbol)}`, {
      method: "POST",
    });
  }

  // ── Signals ───────────────────────────────────────────────

  async getSignals(params?: Record<string, string>): Promise<{ signals: PipelineSignal[]; total: number }> {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return this.request(`/api/v1/signals${qs}`);
  }

  async getSignalsActive(): Promise<PipelineSignal[]> {
    return this.request("/api/v1/signals/active");
  }

  // ── Trades ────────────────────────────────────────────────

  async getTrades(params?: {
    page?: number;
    page_size?: number;
    status?: string;
    symbol?: string;
  }): Promise<{ trades: Trade[]; total: number; page: number; page_size: number }> {
    const qs = params
      ? "?" + new URLSearchParams(
          Object.entries(params)
            .filter(([, v]) => v !== undefined)
            .map(([k, v]) => [k, String(v)])
        ).toString()
      : "";
    return this.request(`/api/v1/trades${qs}`);
  }

  async getTrade(id: string): Promise<Trade> {
    return this.request(`/api/v1/trades/${id}`);
  }

  async createTrade(data: {
    symbol: string;
    side: string;
    quantity: number;
    price?: number;
    stop_loss?: number;
    take_profit?: number;
    strategy_id?: string;
    notes?: string;
  }): Promise<Trade> {
    return this.request("/api/v1/trades", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async closeTrade(tradeId: string, exitPrice?: number): Promise<Trade> {
    const qs = exitPrice ? `?exit_price=${exitPrice}` : "";
    return this.request(`/api/v1/trades/${tradeId}/close${qs}`, {
      method: "PUT",
    });
  }

  // ── Portfolio ─────────────────────────────────────────────

  async getPortfolio(): Promise<PortfolioPosition[]> {
    return this.request("/api/v1/portfolio");
  }

  async getPortfolioSummary(): Promise<PortfolioSummary> {
    return this.request("/api/v1/portfolio/summary");
  }

  async getPortfolioPnl(): Promise<PortfolioSummary> {
    return this.request("/api/v1/portfolio/pnl");
  }

  // ── Analytics ─────────────────────────────────────────────

  async getPerformance(period = "30d"): Promise<PerformanceMetrics> {
    return this.request(`/api/v1/analytics/performance?period=${period}`);
  }

  async getEquityCurve(days = 90): Promise<EquityCurveResponse> {
    return this.request(`/api/v1/analytics/equity-curve?days=${days}`);
  }

  async getPnlHistory(period = "30d"): Promise<PnlHistoryPoint[]> {
    return this.request(`/api/v1/analytics/pnl-history?period=${period}`);
  }

  async getWinRate(): Promise<WinRateData> {
    return this.request("/api/v1/analytics/win-rate");
  }

  async getRisk(): Promise<RiskMetrics> {
    return this.request("/api/v1/analytics/risk");
  }

  // ── Trading Loop ──────────────────────────────────────────

  async getLoopStatus(): Promise<LoopStatus> {
    return this.request("/api/v1/loop/status");
  }

  async startLoop(): Promise<Record<string, unknown>> {
    return this.request("/api/v1/loop/start", { method: "POST" });
  }

  async stopLoop(): Promise<Record<string, unknown>> {
    return this.request("/api/v1/loop/stop", { method: "POST" });
  }

  async updateLoopConfig(config: Record<string, unknown>): Promise<Record<string, unknown>> {
    return this.request("/api/v1/loop/config", {
      method: "PATCH",
      body: JSON.stringify(config),
    });
  }

  // ── AGI ───────────────────────────────────────────────────

  async getAgiMemory(): Promise<AgiMemoryStats> {
    return this.request("/api/v1/agi/memory");
  }

  async getAgiLessons(symbol?: string): Promise<{ lessons: unknown[] }> {
    const qs = symbol ? `?symbol=${encodeURIComponent(symbol)}` : "";
    return this.request(`/api/v1/agi/memory/lessons${qs}`);
  }

  async createAgiPlan(symbol = "BTC/USDT", horizonDays = 5): Promise<Record<string, unknown>> {
    return this.request(
      `/api/v1/agi/plan?symbol=${encodeURIComponent(symbol)}&horizon_days=${horizonDays}`,
      { method: "POST" }
    );
  }

  // ── Market ────────────────────────────────────────────────

  async getMarketTickers(): Promise<MarketTicker[]> {
    return this.request("/api/v1/market/tickers");
  }

  async getMarketTicker(symbol: string): Promise<MarketTicker> {
    return this.request(`/api/v1/market/ticker/${encodeURIComponent(symbol)}`);
  }

  // ── Settings ──────────────────────────────────────────────

  async getSettings(): Promise<AppSettings> {
    return this.request("/api/v1/settings");
  }

  async updateSettings(data: Partial<AppSettings>): Promise<{ message: string; settings: AppSettings }> {
    return this.request("/api/v1/settings", {
      method: "PUT",
      body: JSON.stringify(data),
    });
  }
}

export const api = new ApiClient();
