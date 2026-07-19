import { create } from "zustand";
import { api } from "../lib/api";
import { wsClient } from "../lib/websocket";
import type {
  Trade,
  PortfolioPosition,
  PortfolioSummary,
} from "../lib/types";

interface TradeState {
  positions: PortfolioPosition[];
  portfolioSummary: PortfolioSummary | null;
  trades: Trade[];
  loading: boolean;
  error: string | null;

  fetchPortfolio: () => Promise<void>;
  fetchPortfolioSummary: () => Promise<void>;
  fetchTrades: (params?: {
    page?: number;
    status?: string;
    symbol?: string;
  }) => Promise<void>;
  fetchAll: () => Promise<void>;
  createTrade: (data: {
    symbol: string;
    side: string;
    quantity: number;
    price?: number;
    stop_loss?: number;
    take_profit?: number;
    strategy_id?: string;
    notes?: string;
  }) => Promise<Trade>;
  closeTrade: (tradeId: string, exitPrice?: number) => Promise<Trade>;

  // WebSocket-driven mutations
  updatePosition: (symbol: string, data: Partial<PortfolioPosition>) => void;
  addTrade: (trade: Trade) => void;
  updateTrade: (trade: Trade) => void;

  // WS subscription setup
  subscribeToUpdates: () => () => void;
}

export const useTradeStore = create<TradeState>((set, get) => ({
  positions: [],
  portfolioSummary: null,
  trades: [],
  loading: false,
  error: null,

  fetchPortfolio: async () => {
    try {
      const positions = await api.getPortfolio();
      set({ positions, error: null });
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  fetchPortfolioSummary: async () => {
    try {
      const summary = await api.getPortfolioSummary();
      set({ portfolioSummary: summary, error: null });
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  fetchTrades: async (params) => {
    try {
      const result = await api.getTrades(params);
      set({ trades: result.trades, error: null });
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  fetchAll: async () => {
    set({ loading: true });
    try {
      await Promise.allSettled([
        get().fetchPortfolio(),
        get().fetchPortfolioSummary(),
        get().fetchTrades(),
      ]);
    } finally {
      set({ loading: false });
    }
  },

  createTrade: async (data) => {
    const trade = await api.createTrade(data);
    set((s) => ({ trades: [trade, ...s.trades] }));
    return trade;
  },

  closeTrade: async (tradeId, exitPrice) => {
    const trade = await api.closeTrade(tradeId, exitPrice);
    set((s) => ({
      trades: s.trades.map((t) => (t.id === tradeId ? trade : t)),
    }));
    // Refresh portfolio after closing
    get().fetchPortfolio().catch(() => {});
    get().fetchPortfolioSummary().catch(() => {});
    return trade;
  },

  updatePosition: (symbol, data) =>
    set((s) => ({
      positions: s.positions.map((p) =>
        p.symbol === symbol ? { ...p, ...data } : p
      ),
    })),

  addTrade: (trade) =>
    set((s) => ({
      trades: [trade, ...s.trades].slice(0, 200),
    })),

  updateTrade: (trade) =>
    set((s) => ({
      trades: s.trades.map((t) => (t.id === trade.id ? trade : t)),
    })),

  subscribeToUpdates: () => {
    // Typed listeners
    const unsubTrade = wsClient.onTrade((trade) => {
      get().addTrade(trade);
    });

    // Generic listener for portfolio updates
    const unsubGeneric = wsClient.subscribe((msg) => {
      switch (msg.type) {
        case "portfolio_update":
          if (msg.data) {
            const data = msg.data as Record<string, unknown>;
            if (Array.isArray(data.positions)) {
              set({ positions: data.positions as PortfolioPosition[] });
            }
          }
          break;
        case "trade_executed":
        case "trade_updated":
          if (msg.data) get().addTrade(msg.data as Trade);
          break;
      }
    });

    return () => {
      unsubTrade();
      unsubGeneric();
    };
  },
}));
