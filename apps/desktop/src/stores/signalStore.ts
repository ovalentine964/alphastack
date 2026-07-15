import { create } from "zustand";
import { api } from "../lib/api";
import { wsClient } from "../lib/websocket";
import type { Signal } from "../lib/types";

interface SignalState {
  signals: Signal[];
  loading: boolean;
  error: string | null;
  filter: { strategy?: string; status?: string };

  fetchSignals: () => Promise<void>;
  fetchActiveSignals: () => Promise<void>;
  setFilter: (filter: { strategy?: string; status?: string }) => void;

  // WebSocket-driven mutations
  addSignal: (signal: Signal) => void;
  updateSignal: (signal: Signal) => void;
  removeSignal: (id: string) => void;

  subscribeToUpdates: () => () => void;
}

export const useSignalStore = create<SignalState>((set, get) => ({
  signals: [],
  loading: false,
  error: null,
  filter: {},

  fetchSignals: async () => {
    set({ loading: true });
    try {
      const params: Record<string, string> = {};
      const { filter } = get();
      if (filter.strategy) params.strategy = filter.strategy;
      if (filter.status) params.status = filter.status;
      const signals = await api.getSignals(
        Object.keys(params).length ? params : undefined
      );
      set({ signals, error: null });
    } catch (e) {
      set({ error: (e as Error).message });
    } finally {
      set({ loading: false });
    }
  },

  fetchActiveSignals: async () => {
    set({ loading: true });
    try {
      const signals = await api.getSignalsActive();
      set({ signals, error: null });
    } catch (e) {
      set({ error: (e as Error).message });
    } finally {
      set({ loading: false });
    }
  },

  setFilter: (filter) => set({ filter }),

  addSignal: (signal) =>
    set((s) => ({ signals: [signal, ...s.signals] })),

  updateSignal: (signal) =>
    set((s) => ({
      signals: s.signals.map((sig) =>
        sig.id === signal.id ? signal : sig
      ),
    })),

  removeSignal: (id) =>
    set((s) => ({
      signals: s.signals.filter((sig) => sig.id !== id),
    })),

  subscribeToUpdates: () => {
    const unsub = wsClient.subscribe((msg) => {
      switch (msg.type) {
        case "signal_new":
          if (msg.data) get().addSignal(msg.data as Signal);
          break;
        case "signal_update":
          if (msg.data) get().updateSignal(msg.data as Signal);
          break;
        case "signal_expired":
          if (msg.data) {
            const sig = msg.data as Signal;
            get().updateSignal({ ...sig, status: "expired" });
          }
          break;
      }

      if (msg.channel === "signals" && msg.data) {
        get().addSignal(msg.data as Signal);
      }
    });
    return unsub;
  },
}));
