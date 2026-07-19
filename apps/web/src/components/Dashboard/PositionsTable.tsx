"use client";

import { useEffect } from "react";
import { useTradeStore } from "@/stores/tradeStore";
import { clsx } from "clsx";

export function PositionsTable() {
  const { positions, fetchPositions, positionsLoading } = useTradeStore();

  useEffect(() => {
    fetchPositions();
    const id = setInterval(fetchPositions, 5_000);
    return () => clearInterval(id);
  }, [fetchPositions]);

  return (
    <div className="bg-brand-surface border border-brand-border rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border-brand-border flex items-center justify-between">
        <h2 className="text-sm font-semibold">Open Positions</h2>
        <span className="text-xs text-brand-muted font-mono">
          {positions.length} {positions.length === 1 ? "position" : "positions"}
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-brand-muted text-xs border-b border-brand-border">
              <th className="px-4 py-2 text-left">Symbol</th>
              <th className="px-4 py-2 text-left">Side</th>
              <th className="px-4 py-2 text-right">Qty</th>
              <th className="px-4 py-2 text-right">Entry</th>
              <th className="px-4 py-2 text-right">Current</th>
              <th className="px-4 py-2 text-right">P&L</th>
              <th className="px-4 py-2 text-right">P&L %</th>
              <th className="px-4 py-2 text-right">Weight</th>
            </tr>
          </thead>
          <tbody>
            {positions.length === 0 ? (
              <tr>
                <td
                  colSpan={8}
                  className="px-4 py-8 text-center text-brand-muted"
                >
                  {positionsLoading ? "Loading…" : "No open positions"}
                </td>
              </tr>
            ) : (
              positions.map((p) => (
                <tr
                  key={p.symbol}
                  className="border-b border-brand-border/50 hover:bg-brand-border/10 transition-colors"
                >
                  <td className="px-4 py-2 font-mono font-medium">
                    {p.symbol}
                  </td>
                  <td className="px-4 py-2">
                    <span
                      className={clsx(
                        "px-2 py-0.5 rounded text-xs font-medium",
                        p.side === "long"
                          ? "bg-brand-green/10 text-brand-green"
                          : p.side === "short"
                            ? "bg-brand-red/10 text-brand-red"
                            : "bg-brand-muted/10 text-brand-muted"
                      )}
                    >
                      {p.side.toUpperCase()}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-right font-mono">
                    {p.quantity}
                  </td>
                  <td className="px-4 py-2 text-right font-mono">
                    {p.entry_price.toFixed(2)}
                  </td>
                  <td className="px-4 py-2 text-right font-mono">
                    {p.current_price.toFixed(2)}
                  </td>
                  <td
                    className={clsx(
                      "px-4 py-2 text-right font-mono font-medium",
                      p.unrealized_pnl >= 0
                        ? "text-brand-green"
                        : "text-brand-red"
                    )}
                  >
                    {p.unrealized_pnl >= 0 ? "+" : ""}
                    {p.unrealized_pnl.toFixed(2)}
                  </td>
                  <td
                    className={clsx(
                      "px-4 py-2 text-right font-mono",
                      p.unrealized_pnl_pct >= 0
                        ? "text-brand-green"
                        : "text-brand-red"
                    )}
                  >
                    {p.unrealized_pnl_pct >= 0 ? "+" : ""}
                    {p.unrealized_pnl_pct.toFixed(2)}%
                  </td>
                  <td className="px-4 py-2 text-right font-mono text-brand-muted">
                    {p.weight_pct.toFixed(1)}%
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
