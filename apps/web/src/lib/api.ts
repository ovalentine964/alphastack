const BASE = "/api/v1";

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    // FastAPI returns errors as {"detail": "..."}
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

// Portfolio
// Server: GET /portfolio → positions list, GET /portfolio/pnl → P&L summary,
//         GET /portfolio/performance → performance metrics
export const getPortfolio = () => request("/portfolio");
export const getPortfolioPnl = () => request("/portfolio/pnl");
export const getPortfolioPerformance = () =>
  request("/portfolio/performance");

// Positions (alias — server returns positions at /portfolio)
export const getPositions = () => request("/portfolio");

// Trades
// Server uses page_size (not limit)
export const getTrades = (pageSize = 100) =>
  request(`/trades?page_size=${pageSize}`);
export const getTrade = (id: string) => request(`/trades/${id}`);

// Signals
export const getSignals = (params?: Record<string, string>) => {
  const qs = params ? "?" + new URLSearchParams(params).toString() : "";
  return request(`/signals${qs}`);
};
// Server has no single-signal endpoint; fetch list and filter client-side
export const getSignal = async (id: string) => {
  const data = await request<{ signals: Array<{ id: string }> }>(
    `/signals/history`
  );
  const found = data.signals.find((s) => s.id === id);
  if (!found) throw new Error(`Signal ${id} not found`);
  return found;
};

// Analytics — wired to server's actual endpoints
export const getPerformance = () => request("/portfolio/performance");
export const getEquityCurve = (_days = 90) =>
  // No dedicated equity-curve endpoint yet; return PnL summary as proxy
  request("/portfolio/pnl");
export const getWinRate = () => request("/portfolio/pnl");

// Settings — server has no /settings yet; uses /config for read-only
export const getSettings = () => request("/config");
export const updateSettings = async (data: Record<string, unknown>) => {
  // No PUT /settings on server yet; return current config as acknowledgment
  console.warn("Settings update not yet supported by server", data);
  return request("/config");
};

// Health — lives at root /health, not under /api/v1
export const getHealth = async () => {
  const res = await fetch("/health");
  if (!res.ok) throw new Error(`Health check failed: ${res.status}`);
  return res.json();
};
