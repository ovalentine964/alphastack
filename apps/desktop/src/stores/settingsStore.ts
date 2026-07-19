import { create } from "zustand";
import { tauriBridge } from "../lib/tauri-bridge";
import { api } from "../lib/api";
import { wsClient } from "../lib/websocket";
import type { AppSettings, HealthResponse } from "../lib/types";

interface SettingsState {
  settings: AppSettings;
  connectionInfo: {
    apiEndpoint: string;
    wsEndpoint: string;
  };
  loaded: boolean;
  saving: boolean;
  saved: boolean;

  loadSettings: () => Promise<void>;
  saveSettings: (updates: Partial<AppSettings>) => Promise<void>;
  testConnection: () => Promise<{ ok: boolean; message: string; health?: HealthResponse }>;
  setEndpoints: (api: string, ws: string) => void;
}

const defaults: AppSettings = {
  notifications: {
    email_enabled: true,
    push_enabled: true,
    signal_alerts: true,
    trade_alerts: true,
  },
  display: {
    theme: "dark",
    language: "en",
    timezone: "UTC",
    currency: "USD",
  },
  risk: {
    max_position_size_pct: 5.0,
    max_daily_loss_pct: 2.0,
    max_drawdown_pct: 10.0,
    auto_stop_loss: true,
  },
  trading: {
    default_order_type: "limit",
    confirmation_required: true,
    paper_trading: true,
  },
};

export const useSettingsStore = create<SettingsState>((set, get) => ({
  settings: { ...defaults },
  connectionInfo: {
    apiEndpoint: "http://localhost:8000",
    wsEndpoint: "ws://localhost:8000/ws",
  },
  loaded: false,
  saving: false,
  saved: false,

  loadSettings: async () => {
    // Load connection endpoints from Tauri store
    const apiEndpoint =
      (await tauriBridge.getSetting<string>("apiEndpoint")) ?? "http://localhost:8000";
    const wsEndpoint =
      (await tauriBridge.getSetting<string>("wsEndpoint")) ?? "ws://localhost:8000/ws";

    set({
      connectionInfo: { apiEndpoint, wsEndpoint },
    });

    // Wire up API and WebSocket
    api.setBaseUrl(apiEndpoint);
    wsClient.setUrl(wsEndpoint);

    // Try to load settings from backend
    try {
      const backendSettings = await api.getSettings();
      set({ settings: backendSettings, loaded: true });
    } catch {
      // Backend unavailable — use defaults
      set({ settings: { ...defaults }, loaded: true });
    }
  },

  saveSettings: async (updates) => {
    set({ saving: true, saved: false });
    try {
      // Save to backend
      try {
        const result = await api.updateSettings(updates);
        set({ settings: result.settings });
      } catch {
        // Backend unavailable — merge locally
        const merged = { ...get().settings };
        if (updates.notifications)
          merged.notifications = { ...merged.notifications, ...updates.notifications };
        if (updates.display)
          merged.display = { ...merged.display, ...updates.display };
        if (updates.risk) merged.risk = { ...merged.risk, ...updates.risk };
        if (updates.trading)
          merged.trading = { ...merged.trading, ...updates.trading };
        set({ settings: merged });
      }

      set({ saved: true });
      setTimeout(() => set({ saved: false }), 2000);
    } finally {
      set({ saving: false });
    }
  },

  testConnection: async () => {
    try {
      const health = await api.getHealth();
      return {
        ok: health.status === "ok",
        message: `Connected — v${health.version}, ${health.agents.length} agents active`,
        health,
      };
    } catch (e) {
      return {
        ok: false,
        message: `Failed: ${(e as Error).message}`,
      };
    }
  },

  setEndpoints: (apiEndpoint, wsEndpoint) => {
    set({ connectionInfo: { apiEndpoint, wsEndpoint } });
    api.setBaseUrl(apiEndpoint);
    wsClient.setUrl(wsEndpoint);
    tauriBridge.setSetting("apiEndpoint", apiEndpoint).catch(() => {});
    tauriBridge.setSetting("wsEndpoint", wsEndpoint).catch(() => {});
  },
}));
