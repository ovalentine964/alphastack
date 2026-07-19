import { create } from "zustand";
import type {
  Position,
  Trade,
  TradeListResponse,
  PnLSummary,
  PerformanceMetrics,
} from "@/types";
import * as api from "@/lib/api";

// ─── Portfolio slice ──────────────────────────────────────────────────────────

interface PortfolioState {
  positions: Position[];
  pnl: PnLSummary | null;
  performance: PerformanceMetrics | null;
  positionsLoading: boolean;
  pnlLoading: boolean;

  fetchPositions: () => Promise<void>;
  fetchPnl: () => Promise<void>;
  fetchPerformance: () => Promise<void>;
  updatePosition: (pos: Position) => void;
}

// ─── Trades slice ─────────────────────────────────────────────────────────────

interface TradeState {
  trades: Trade[];
  tradesTotal: number;
  tradesLoading: boolean;

  fetchTrades: (params?: {
    page?: number;
    page_size?: number;
    status?: string;
    symbol?: string;
  }) => Promise<void>;
  addTrade: (trade: Trade) => void;
  updateTrade: (trade: Trade) => void;
}

// ─── Combined store ───────────────────────────────────────────────────────────

type StoreState = PortfolioState & TradeState;

export const useTradeStore = create<StoreState>((set) => ({
  // ── Portfolio state ───────────────────────────────────────────────────────
  positions: [],
  pnl: null,
  performance: null,
  positionsLoading: false,
  pnlLoading: false,

  fetchPositions: async () => {
    set({ positionsLoading: true });
    try {
      const positions = await api.getPositions();
      set({ positions });
    } catch (err) {
      console.error("[store] fetchPositions failed:", err);
    } finally {
      set({ positionsLoading: false });
    }
  },

  fetchPnl: async () => {
    set({ pnlLoading: true });
    try {
      const pnl = await api.getPortfolioPnl();
      set({ pnl });
    } catch (err) {
      console.error("[store] fetchPnl failed:", err);
    } finally {
      set({ pnlLoading: false });
    }
  },

  fetchPerformance: async () => {
    try {
      const performance = await api.getPerformance();
      set({ performance });
    } catch (err) {
      console.error("[store] fetchPerformance failed:", err);
    }
  },

  updatePosition: (pos) =>
    set((s) => ({
      positions: s.positions.map((p) =>
        p.symbol === pos.symbol ? pos : p
      ),
    })),

  // ── Trades state ──────────────────────────────────────────────────────────
  trades: [],
  tradesTotal: 0,
  tradesLoading: false,

  fetchTrades: async (params) => {
    set({ tradesLoading: true });
    try {
      const data: TradeListResponse = await api.getTrades(params);
      set({ trades: data.trades, tradesTotal: data.total });
    } catch (err) {
      console.error("[store] fetchTrades failed:", err);
    } finally {
      set({ tradesLoading: false });
    }
  },

  addTrade: (trade) =>
    set((s) => ({
      trades: [trade, ...s.trades].slice(0, 200),
      tradesTotal: s.tradesTotal + 1,
    })),

  updateTrade: (trade) =>
    set((s) => ({
      trades: s.trades.map((t) => (t.id === trade.id ? trade : t)),
    })),
}));
