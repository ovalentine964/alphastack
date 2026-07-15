import { create } from "zustand";
import { tauriBridge } from "../lib/tauri-bridge";
import { api } from "../lib/api";
import { wsClient } from "../lib/websocket";
import type { AppSettings } from "../lib/types";

interface SettingsState {
  settings: AppSettings;
  loaded: boolean;
  saving: boolean;
  saved: boolean;

  loadSettings: () => Promise<void>;
  saveSettings: (updates: Partial<AppSettings>) => Promise<void>;
  testConnection: () => Promise<{ ok: boolean; message: string }>;
}

const defaults: AppSettings = {
  apiEndpoint: "http://localhost:8000/api/v1",
  wsEndpoint: "ws://localhost:8000/ws",
  binanceApiKey: "",
  binanceApiSecret: "",
  useTestnet: true,
  mimoApiKey: "",
  maxPositionSize: 1000,
  maxDailyLoss: 500,
  maxDrawdown: 10,
  notificationsEnabled: true,
  autoRefresh: true,
};

export const useSettingsStore = create<SettingsState>((set, get) => ({
  settings: { ...defaults },
  loaded: false,
  saving: false,
  saved: false,

  loadSettings: async () => {
    const keys = Object.keys(defaults) as (keyof AppSettings)[];
    const loaded: Record<string, unknown> = {};

    for (const key of keys) {
      const val = await tauriBridge.getSetting(key);
      if (val !== null) loaded[key] = val;
    }

    const settings = { ...defaults, ...loaded } as AppSettings;
    set({ settings, loaded: true });

    // Wire up API and WebSocket with saved settings
    api.setBaseUrl(settings.apiEndpoint);
    wsClient.setUrl(settings.wsEndpoint);
  },

  saveSettings: async (updates) => {
    set({ saving: true, saved: false });
    try {
      const merged = { ...get().settings, ...updates };
      // Persist each changed key via Tauri secure store
      for (const [key, value] of Object.entries(updates)) {
        await tauriBridge.setSetting(key, value);
      }
      set({ settings: merged, saved: true });

      // Reconfigure API/WS if endpoints changed
      if (updates.apiEndpoint) api.setBaseUrl(updates.apiEndpoint);
      if (updates.wsEndpoint) wsClient.setUrl(updates.wsEndpoint);

      // Reset saved indicator after 2s
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
        message: `Connected — ${health.status}`,
      };
    } catch (e) {
      return {
        ok: false,
        message: `Failed: ${(e as Error).message}`,
      };
    }
  },
}));
