import { create } from "zustand";
import type { Signal, SignalListResponse, SignalDirection, SignalStrength } from "@/types";
import * as api from "@/lib/api";

interface SignalState {
  signals: Signal[];
  total: number;
  loading: boolean;
  filter: {
    symbol?: string;
    strategy_id?: string;
  };

  fetchSignals: () => Promise<void>;
  fetchHistory: (params?: {
    page?: number;
    page_size?: number;
    symbol?: string;
  }) => Promise<void>;
  setFilter: (filter: { symbol?: string; strategy_id?: string }) => void;
  addSignal: (signal: Signal) => void;
  updateSignal: (signal: Signal) => void;
}

export const useSignalStore = create<SignalState>((set, get) => ({
  signals: [],
  total: 0,
  loading: false,
  filter: {},

  fetchSignals: async () => {
    set({ loading: true });
    try {
      const { filter } = get();
      const data: SignalListResponse = await api.getSignals(filter);
      set({ signals: data.signals, total: data.total });
    } catch (err) {
      console.error("[signalStore] fetchSignals failed:", err);
    } finally {
      set({ loading: false });
    }
  },

  fetchHistory: async (params) => {
    set({ loading: true });
    try {
      const data: SignalListResponse = await api.getSignalHistory(params);
      set({ signals: data.signals, total: data.total });
    } catch (err) {
      console.error("[signalStore] fetchHistory failed:", err);
    } finally {
      set({ loading: false });
    }
  },

  setFilter: (filter) => set({ filter }),

  addSignal: (signal) =>
    set((s) => ({
      signals: [signal, ...s.signals],
      total: s.total + 1,
    })),

  updateSignal: (signal) =>
    set((s) => ({
      signals: s.signals.map((sig) =>
        sig.id === signal.id ? signal : sig
      ),
    })),
}));
