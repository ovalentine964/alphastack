import { create } from "zustand";
import { api } from "../lib/api";
import { wsClient } from "../lib/websocket";
import type { PipelineSignal } from "../lib/types";

interface SignalState {
  signals: PipelineSignal[];
  loading: boolean;
  error: string | null;
  filter: { strategy_id?: string; symbol?: string; is_active?: boolean };

  fetchSignals: () => Promise<void>;
  fetchActiveSignals: () => Promise<void>;
  setFilter: (filter: {
    strategy_id?: string;
    symbol?: string;
    is_active?: boolean;
  }) => void;

  // WebSocket-driven mutations
  addSignal: (signal: PipelineSignal) => void;
  updateSignal: (signal: PipelineSignal) => void;
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
      if (filter.strategy_id) params.strategy_id = filter.strategy_id;
      if (filter.symbol) params.symbol = filter.symbol;
      const result = await api.getSignals(
        Object.keys(params).length ? params : undefined
      );
      set({ signals: result.signals, error: null });
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
    set((s) => ({
      signals: [signal, ...s.signals].filter(
        (sig, i, arr) => arr.findIndex((x) => x.id === sig.id) === i
      ),
    })),

  updateSignal: (signal) =>
    set((s) => ({
      signals: s.signals.map((sig) =>
        sig.id === signal.id ? { ...sig, ...signal } : sig
      ),
    })),

  removeSignal: (id) =>
    set((s) => ({
      signals: s.signals.filter((sig) => sig.id !== id),
    })),

  subscribeToUpdates: () => {
    // Typed signal listener
    const unsubSignal = wsClient.onSignal((signal) => {
      get().addSignal(signal);
    });

    // Generic listener for signal lifecycle events
    const unsubGeneric = wsClient.subscribe((msg) => {
      switch (msg.type) {
        case "signal_new":
          if (msg.data) get().addSignal(msg.data as PipelineSignal);
          break;
        case "signal_update":
          if (msg.data) get().updateSignal(msg.data as PipelineSignal);
          break;
        case "signal_expired":
          if (msg.data) {
            const sig = msg.data as PipelineSignal;
            get().updateSignal({ ...sig, is_active: false });
          }
          break;
      }
    });

    return () => {
      unsubSignal();
      unsubGeneric();
    };
  },
}));
