import { tauriBridge } from "./tauri-bridge";
import type {
  Portfolio,
  Position,
  Trade,
  Signal,
  PerformanceMetrics,
  EquityPoint,
  WinRateData,
  RiskMetrics,
  AppSettings,
} from "./types";

/**
 * AlphaStack REST API client for the Tauri desktop app.
 * Reads the base URL from persistent settings (defaults to localhost:8000).
 */
class ApiClient {
  private _baseUrl = "http://localhost:8000/api/v1";

  async init(): Promise<void> {
    const saved = await tauriBridge.getSetting<string>("apiEndpoint");
    if (saved) this._baseUrl = saved;
  }

  get baseUrl(): string {
    return this._baseUrl;
  }

  setBaseUrl(url: string): void {
    this._baseUrl = url.replace(/\/+$/, "");
  }

  private async request<T>(path: string, options?: RequestInit): Promise<T> {
    const token = await tauriBridge.getSetting<string>("authToken");
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...((options?.headers as Record<string, string>) ?? {}),
    };
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const res = await fetch(`${this._baseUrl}${path}`, {
      ...options,
      headers,
    });

    if (!res.ok) {
      const body = await res.text().catch(() => "");
      throw new Error(`API ${res.status}: ${body || res.statusText}`);
    }
    return res.json();
  }

  // ── Auth ──────────────────────────────────────────────
  async login(
    apiKey: string,
    apiSecret: string
  ): Promise<{ token: string }> {
    return this.request("/auth/login", {
      method: "POST",
      body: JSON.stringify({ apiKey, apiSecret }),
    });
  }

  // ── Portfolio ─────────────────────────────────────────
  async getPortfolio(): Promise<Portfolio> {
    return this.request("/portfolio/summary");
  }

  async getPositions(): Promise<Position[]> {
    return this.request("/portfolio/positions");
  }

  // ── Trades ────────────────────────────────────────────
  async getTrades(limit = 100): Promise<Trade[]> {
    return this.request(`/trades?limit=${limit}`);
  }

  async getTrade(id: string): Promise<Trade> {
    return this.request(`/trades/${id}`);
  }

  // ── Signals ───────────────────────────────────────────
  async getSignalsActive(): Promise<Signal[]> {
    return this.request("/signals/active");
  }

  async getSignals(params?: Record<string, string>): Promise<Signal[]> {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return this.request(`/signals${qs}`);
  }

  // ── Analytics ─────────────────────────────────────────
  async getPerformance(): Promise<PerformanceMetrics> {
    return this.request("/analytics/performance");
  }

  async getPnlHistory(period = "1M"): Promise<EquityPoint[]> {
    return this.request(`/analytics/pnl-history?period=${period}`);
  }

  async getEquityCurve(days = 90): Promise<EquityPoint[]> {
    return this.request(`/analytics/equity-curve?days=${days}`);
  }

  async getWinRate(): Promise<WinRateData[]> {
    return this.request("/analytics/win-rate");
  }

  async getRisk(): Promise<RiskMetrics> {
    return this.request("/analytics/risk");
  }

  // ── Settings ──────────────────────────────────────────
  async getSettings(): Promise<AppSettings> {
    return this.request("/settings");
  }

  async updateSettings(data: Partial<AppSettings>): Promise<void> {
    await this.request("/settings", {
      method: "PUT",
      body: JSON.stringify(data),
    });
  }

  // ── Health ────────────────────────────────────────────
  async getHealth(): Promise<{ status: string }> {
    const base = this._baseUrl.replace(/\/api\/v1\/?$/, "");
    const res = await fetch(`${base}/health`);
    if (!res.ok) throw new Error(`Health check failed: ${res.status}`);
    return res.json();
  }
}

export const api = new ApiClient();
