"use client";

import { useEffect, useState } from "react";
import { useTradeStore } from "@/stores/tradeStore";
import { clsx } from "clsx";
import { Filter, Plus, X } from "lucide-react";
import type { Side, TradeStatus } from "@/types";
import { createTrade, closeTrade } from "@/lib/api";

export default function TradesPage() {
  const { trades, tradesTotal, fetchTrades, tradesLoading } = useTradeStore();
  const [sideFilter, setSideFilter] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [symbolFilter, setSymbolFilter] = useState("");
  const [page, setPage] = useState(1);

  useEffect(() => {
    fetchTrades({
      page,
      page_size: 50,
      status: statusFilter || undefined,
      symbol: symbolFilter || undefined,
    });
  }, [fetchTrades, page, statusFilter, symbolFilter]);

  // Client-side side filter (backend doesn't filter by side)
  const filtered = sideFilter
    ? trades.filter((t) => t.side === sideFilter)
    : trades;

  const totalPnl = filtered.reduce((s, t) => s + (t.pnl ?? 0), 0);
  const closedTrades = filtered.filter((t) => t.status === "closed");
  const winCount = closedTrades.filter((t) => (t.pnl ?? 0) > 0).length;

  const totalPages = Math.ceil(tradesTotal / 50);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Trade History</h1>
        <div className="flex items-center gap-4 text-sm">
          <span className="text-brand-muted">
            {tradesTotal} total trades
          </span>
          <span
            className={clsx(
              "font-mono font-medium",
              totalPnl >= 0 ? "text-brand-green" : "text-brand-red"
            )}
          >
            P&L: {totalPnl >= 0 ? "+" : ""}
            {totalPnl.toFixed(2)}
          </span>
          {closedTrades.length > 0 && (
            <span className="text-brand-muted">
              Win: {((winCount / closedTrades.length) * 100).toFixed(1)}%
            </span>
          )}
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <Filter size={16} className="text-brand-muted" />
          <select
            value={sideFilter}
            onChange={(e) => {
              setSideFilter(e.target.value);
              setPage(1);
            }}
            className="bg-brand-surface border border-brand-border rounded-md px-3 py-1.5 text-sm text-brand-text focus:outline-none focus:ring-1 focus:ring-brand-green"
          >
            <option value="">All Sides</option>
            <option value="buy">Buy</option>
            <option value="sell">Sell</option>
          </select>
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="bg-brand-surface border border-brand-border rounded-md px-3 py-1.5 text-sm text-brand-text focus:outline-none focus:ring-1 focus:ring-brand-green"
          >
            <option value="">All Statuses</option>
            <option value="open">Open</option>
            <option value="closed">Closed</option>
            <option value="pending">Pending</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </div>
        <input
          type="text"
          placeholder="Filter by symbol…"
          value={symbolFilter}
          onChange={(e) => {
            setSymbolFilter(e.target.value);
            setPage(1);
          }}
          className="bg-brand-surface border border-brand-border rounded-md px-3 py-1.5 text-sm text-brand-text placeholder:text-brand-muted focus:outline-none focus:ring-1 focus:ring-brand-green w-48"
        />
      </div>

      {/* Trades table */}
      <div className="bg-brand-surface border border-brand-border rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-brand-muted text-xs border-b border-brand-border">
                <th className="px-4 py-3 text-left">Time</th>
                <th className="px-4 py-3 text-left">Symbol</th>
                <th className="px-4 py-3 text-left">Side</th>
                <th className="px-4 py-3 text-right">Qty</th>
                <th className="px-4 py-3 text-right">Entry</th>
                <th className="px-4 py-3 text-right">Exit</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3 text-left">Strategy</th>
                <th className="px-4 py-3 text-right">P&L</th>
                <th className="px-4 py-3 text-center">Action</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={10} className="px-4 py-12 text-center text-brand-muted">
                    {tradesLoading ? "Loading…" : "No trades found"}
                  </td>
                </tr>
              ) : (
                filtered.map((t) => (
                  <tr
                    key={t.id}
                    className="border-b border-brand-border/50 hover:bg-brand-border/10 transition-colors"
                  >
                    <td className="px-4 py-2 text-xs text-brand-muted font-mono">
                      {new Date(t.opened_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-2 font-mono font-medium">{t.symbol}</td>
                    <td className="px-4 py-2">
                      <span
                        className={clsx(
                          "px-2 py-0.5 rounded text-xs font-medium",
                          t.side === "buy"
                            ? "bg-brand-green/10 text-brand-green"
                            : "bg-brand-red/10 text-brand-red"
                        )}
                      >
                        {t.side.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-right font-mono">{t.quantity}</td>
                    <td className="px-4 py-2 text-right font-mono">
                      {t.entry_price != null ? t.entry_price.toFixed(2) : "—"}
                    </td>
                    <td className="px-4 py-2 text-right font-mono">
                      {t.exit_price != null ? t.exit_price.toFixed(2) : "—"}
                    </td>
                    <td className="px-4 py-2">
                      <span
                        className={clsx(
                          "px-2 py-0.5 rounded text-xs font-medium",
                          t.status === "open"
                            ? "bg-brand-accent/10 text-brand-accent"
                            : t.status === "closed"
                              ? "bg-brand-muted/10 text-brand-muted"
                              : t.status === "pending"
                                ? "bg-yellow-400/10 text-yellow-400"
                                : "bg-brand-red/10 text-brand-red"
                        )}
                      >
                        {t.status}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-xs text-brand-muted">
                      {t.strategy_id ?? "—"}
                    </td>
                    <td
                      className={clsx(
                        "px-4 py-2 text-right font-mono font-medium",
                        t.pnl != null && t.pnl >= 0
                          ? "text-brand-green"
                          : "text-brand-red"
                      )}
                    >
                      {t.pnl != null
                        ? `${t.pnl >= 0 ? "+" : ""}${t.pnl.toFixed(2)}`
                        : "—"}
                    </td>
                    <td className="px-4 py-2 text-center">
                      {t.status === "open" && (
                        <button
                          onClick={async () => {
                            try {
                              await closeTrade(t.id);
                              fetchTrades({ page, page_size: 50 });
                            } catch (err) {
                              console.error("Close trade failed:", err);
                            }
                          }}
                          className="px-2 py-1 text-xs bg-brand-red/10 text-brand-red rounded hover:bg-brand-red/20 transition-colors"
                        >
                          Close
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="px-3 py-1.5 text-sm bg-brand-surface border border-brand-border rounded-md hover:bg-brand-border/30 disabled:opacity-50 transition-colors"
          >
            Previous
          </button>
          <span className="text-sm text-brand-muted">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
            className="px-3 py-1.5 text-sm bg-brand-surface border border-brand-border rounded-md hover:bg-brand-border/30 disabled:opacity-50 transition-colors"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
