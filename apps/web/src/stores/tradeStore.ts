import { create } from "zustand";

export interface Position {
  id: string;
  symbol: string;
  side: "LONG" | "SHORT";
  qty: number;
  entry: number;
  current: number;
  pnl: number;
  pnlPct: number;
  openedAt: string;
}

export interface Trade {
  id: string;
  symbol: string;
  side: "BUY" | "SELL";
  qty: number;
  price: number;
  pnl?: number;
  strategy: string;
  executedAt: string;
}

export interface Portfolio {
  balance: number;
  equity: number;
  unrealizedPnl: number;
  realizedPnl: number;
  dayPnl: number;
  totalReturn: number;
}

interface TradeState {
  portfolio: Portfolio;
  positions: Position[];
  trades: Trade[];
  loading: boolean;
  fetchPortfolio: () => Promise<void>;
  fetchPositions: () => Promise<void>;
  fetchTrades: (limit?: number) => Promise<void>;
  updatePosition: (pos: Position) => void;
  addTrade: (trade: Trade) => void;
}

export const useTradeStore = create<TradeState>((set) => ({
  portfolio: {
    balance: 0,
    equity: 0,
    unrealizedPnl: 0,
    realizedPnl: 0,
    dayPnl: 0,
    totalReturn: 0,
  },
  positions: [],
  trades: [],
  loading: false,

  fetchPortfolio: async () => {
    set({ loading: true });
    try {
      const res = await fetch("/api/portfolio");
      if (res.ok) set({ portfolio: await res.json() });
    } finally {
      set({ loading: false });
    }
  },

  fetchPositions: async () => {
    try {
      const res = await fetch("/api/positions");
      if (res.ok) set({ positions: await res.json() });
    } catch {
      /* ignore */
    }
  },

  fetchTrades: async (limit = 100) => {
    try {
      const res = await fetch(`/api/trades?limit=${limit}`);
      if (res.ok) set({ trades: await res.json() });
    } catch {
      /* ignore */
    }
  },

  updatePosition: (pos) =>
    set((s) => ({
      positions: s.positions.map((p) => (p.id === pos.id ? pos : p)),
    })),

  addTrade: (trade) =>
    set((s) => ({ trades: [trade, ...s.trades].slice(0, 200) })),
}));
