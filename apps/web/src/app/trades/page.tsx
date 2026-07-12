"use client";

import { useEffect, useState } from "react";
import { useTradeStore } from "@/stores/tradeStore";
import { clsx } from "clsx";
import { Filter } from "lucide-react";

export default function TradesPage() {
  const { trades, fetchTrades } = useTradeStore();
  const [sideFilter, setSideFilter] = useState<string>("ALL");
  const [symbolFilter, setSymbolFilter] = useState("");

  useEffect(() => {
    fetchTrades(200);
  }, [fetchTrades]);

  const filtered = trades.filter((t) => {
    if (sideFilter !== "ALL" && t.side !== sideFilter) return false;
    if (symbolFilter && !t.symbol.toLowerCase().includes(symbolFilter.toLowerCase()))
      return false;
    return true;
  });

  const totalPnl = filtered.reduce((s, t) => s + (t.pnl ?? 0), 0);
  const winCount = filtered.filter((t) => (t.pnl ?? 0) > 0).length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Trade History</h1>
        <div className="flex items-center gap-4 text-sm">
          <span className="text-brand-muted">
            {filtered.length} trades
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
          <span className="text-brand-muted">
            Win: {filtered.length > 0 ? ((winCount / filtered.length) * 100).toFixed(1) : 0}%
          </span>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <Filter size={16} className="text-brand-muted" />
          <select
            value={sideFilter}
            onChange={(e) => setSideFilter(e.target.value)}
            className="bg-brand-surface border border-brand-border rounded-md px-3 py-1.5 text-sm text-brand-text focus:outline-none focus:ring-1 focus:ring-brand-green"
          >
            <option value="ALL">All Sides</option>
            <option value="BUY">Buy</option>
            <option value="SELL">Sell</option>
          </select>
        </div>
        <input
          type="text"
          placeholder="Filter by symbol…"
          value={symbolFilter}
          onChange={(e) => setSymbolFilter(e.target.value)}
          className="bg-brand-surface border border-brand-border rounded-md px-3 py-1.5 text-sm text-brand-text placeholder:text-brand-muted focus:outline-none focus:ring-1 focus:ring-brand-green w-48"
        />
      </div>

      <div className="bg-brand-surface border border-brand-border rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-brand-muted text-xs border-b border-brand-border">
                <th className="px-4 py-3 text-left">Time</th>
                <th className="px-4 py-3 text-left">Symbol</th>
                <th className="px-4 py-3 text-left">Side</th>
                <th className="px-4 py-3 text-right">Qty</th>
                <th className="px-4 py-3 text-right">Price</th>
                <th className="px-4 py-3 text-left">Strategy</th>
                <th className="px-4 py-3 text-right">P&L</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-brand-muted">
                    No trades found
                  </td>
                </tr>
              ) : (
                filtered.map((t) => (
                  <tr
                    key={t.id}
                    className="border-b border-brand-border/50 hover:bg-brand-border/10 transition-colors"
                  >
                    <td className="px-4 py-2 text-xs text-brand-muted font-mono">
                      {new Date(t.executedAt).toLocaleString()}
                    </td>
                    <td className="px-4 py-2 font-mono font-medium">{t.symbol}</td>
                    <td className="px-4 py-2">
                      <span
                        className={clsx(
                          "px-2 py-0.5 rounded text-xs font-medium",
                          t.side === "BUY"
                            ? "bg-brand-green/10 text-brand-green"
                            : "bg-brand-red/10 text-brand-red"
                        )}
                      >
                        {t.side}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-right font-mono">{t.qty}</td>
                    <td className="px-4 py-2 text-right font-mono">
                      {t.price.toFixed(2)}
                    </td>
                    <td className="px-4 py-2 text-xs text-brand-muted">{t.strategy}</td>
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
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
