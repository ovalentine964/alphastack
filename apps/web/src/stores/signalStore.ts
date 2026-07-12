import { create } from "zustand";

export interface Signal {
  id: string;
  symbol: string;
  direction: "LONG" | "SHORT";
  strategy: string;
  confidence: number;
  confluence: number;
  factors: string[];
  status: "active" | "expired" | "triggered";
  createdAt: string;
  expiresAt: string;
}

interface SignalState {
  signals: Signal[];
  loading: boolean;
  filter: { strategy?: string; status?: string };
  fetchSignals: () => Promise<void>;
  setFilter: (filter: { strategy?: string; status?: string }) => void;
  addSignal: (signal: Signal) => void;
  updateSignal: (signal: Signal) => void;
}

export const useSignalStore = create<SignalState>((set, get) => ({
  signals: [],
  loading: false,
  filter: {},

  fetchSignals: async () => {
    set({ loading: true });
    try {
      const params = new URLSearchParams();
      const { filter } = get();
      if (filter.strategy) params.set("strategy", filter.strategy);
      if (filter.status) params.set("status", filter.status);
      const res = await fetch(`/api/signals?${params}`);
      if (res.ok) set({ signals: await res.json() });
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
}));
