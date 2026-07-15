import { create } from "zustand";
import { api } from "../lib/api";
import { wsClient } from "../lib/websocket";
import type { Portfolio, Position, Trade } from "../lib/types";

interface TradeState {
  portfolio: Portfolio;
  positions: Position[];
  trades: Trade[];
  loading: boolean;
  error: string | null;

  fetchPortfolio: () => Promise<void>;
  fetchPositions: () => Promise<void>;
  fetchTrades: (limit?: number) => Promise<void>;
  fetchAll: () => Promise<void>;

  // WebSocket-driven mutations
  updatePosition: (pos: Position) => void;
  addPosition: (pos: Position) => void;
  removePosition: (id: string) => void;
  addTrade: (trade: Trade) => void;
  updatePortfolio: (p: Portfolio) => void;

  // WS subscription setup
  subscribeToUpdates: () => () => void;
}

const defaultPortfolio: Portfolio = {
  balance: 0,
  equity: 0,
  unrealizedPnl: 0,
  realizedPnl: 0,
  dayPnl: 0,
  totalReturn: 0,
};

export const useTradeStore = create<TradeState>((set, get) => ({
  portfolio: defaultPortfolio,
  positions: [],
  trades: [],
  loading: false,
  error: null,

  fetchPortfolio: async () => {
    try {
      const portfolio = await api.getPortfolio();
      set({ portfolio, error: null });
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  fetchPositions: async () => {
    try {
      const positions = await api.getPositions();
      set({ positions, error: null });
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  fetchTrades: async (limit = 100) => {
    try {
      const trades = await api.getTrades(limit);
      set({ trades, error: null });
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  fetchAll: async () => {
    set({ loading: true });
    try {
      await Promise.allSettled([
        get().fetchPortfolio(),
        get().fetchPositions(),
        get().fetchTrades(),
      ]);
    } finally {
      set({ loading: false });
    }
  },

  updatePosition: (pos) =>
    set((s) => ({
      positions: s.positions.map((p) => (p.id === pos.id ? pos : p)),
    })),

  addPosition: (pos) =>
    set((s) => ({
      positions: [...s.positions, pos],
    })),

  removePosition: (id) =>
    set((s) => ({
      positions: s.positions.filter((p) => p.id !== id),
    })),

  addTrade: (trade) =>
    set((s) => ({
      trades: [trade, ...s.trades].slice(0, 200),
    })),

  updatePortfolio: (p) => set({ portfolio: p }),

  subscribeToUpdates: () => {
    const unsub = wsClient.subscribe((msg) => {
      if (!msg.channel && !msg.type) return;

      switch (msg.type) {
        case "position_update":
          if (msg.data) get().updatePosition(msg.data as Position);
          break;
        case "position_opened":
          if (msg.data) get().addPosition(msg.data as Position);
          break;
        case "position_closed":
          if (msg.data) get().removePosition((msg.data as Position).id);
          break;
        case "trade_executed":
        case "trade_updated":
          if (msg.data) get().addTrade(msg.data as Trade);
          break;
        case "portfolio_update":
          if (msg.data) get().updatePortfolio(msg.data as Portfolio);
          break;
      }

      // Also handle channel-based messages
      switch (msg.channel) {
        case "trades":
          if (msg.data) get().addTrade(msg.data as Trade);
          break;
        case "portfolio":
          if (msg.data) get().updatePortfolio(msg.data as Portfolio);
          break;
      }
    });
    return unsub;
  },
}));
