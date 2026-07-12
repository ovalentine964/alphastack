const BASE = "/api";

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json();
}

// Portfolio
export const getPortfolio = () => request("/portfolio");
export const getPositions = () => request("/positions");

// Trades
export const getTrades = (limit = 100) =>
  request(`/trades?limit=${limit}`);
export const getTrade = (id: string) => request(`/trades/${id}`);

// Signals
export const getSignals = (params?: Record<string, string>) => {
  const qs = params ? "?" + new URLSearchParams(params).toString() : "";
  return request(`/signals${qs}`);
};
export const getSignal = (id: string) => request(`/signals/${id}`);

// Analytics
export const getPerformance = () => request("/analytics/performance");
export const getEquityCurve = (days = 90) =>
  request(`/analytics/equity-curve?days=${days}`);
export const getWinRate = () => request("/analytics/win-rate");

// Settings
export const getSettings = () => request("/settings");
export const updateSettings = (data: Record<string, unknown>) =>
  request("/settings", {
    method: "PUT",
    body: JSON.stringify(data),
  });

// Health
export const getHealth = () => request("/health");
