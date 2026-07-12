"use client";

import { useEffect } from "react";
import { useTradeStore } from "@/stores/tradeStore";
import { clsx } from "clsx";

export function PositionsTable() {
  const { positions, fetchPositions } = useTradeStore();

  useEffect(() => {
    fetchPositions();
    const id = setInterval(fetchPositions, 5_000);
    return () => clearInterval(id);
  }, [fetchPositions]);

  return (
    <div className="bg-brand-surface border border-brand-border rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border-brand-border">
        <h2 className="text-sm font-semibold">Open Positions</h2>
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
            </tr>
          </thead>
          <tbody>
            {positions.length === 0 ? (
              <tr>
                <td
                  colSpan={7}
                  className="px-4 py-8 text-center text-brand-muted"
                >
                  No open positions
                </td>
              </tr>
            ) : (
              positions.map((p) => (
                <tr
                  key={p.id}
                  className="border-b border-brand-border/50 hover:bg-brand-border/10 transition-colors"
                >
                  <td className="px-4 py-2 font-mono font-medium">
                    {p.symbol}
                  </td>
                  <td className="px-4 py-2">
                    <span
                      className={clsx(
                        "px-2 py-0.5 rounded text-xs font-medium",
                        p.side === "LONG"
                          ? "bg-brand-green/10 text-brand-green"
                          : "bg-brand-red/10 text-brand-red"
                      )}
                    >
                      {p.side}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-right font-mono">{p.qty}</td>
                  <td className="px-4 py-2 text-right font-mono">
                    {p.entry.toFixed(2)}
                  </td>
                  <td className="px-4 py-2 text-right font-mono">
                    {p.current.toFixed(2)}
                  </td>
                  <td
                    className={clsx(
                      "px-4 py-2 text-right font-mono font-medium",
                      p.pnl >= 0 ? "text-brand-green" : "text-brand-red"
                    )}
                  >
                    {p.pnl >= 0 ? "+" : ""}
                    {p.pnl.toFixed(2)}
                  </td>
                  <td
                    className={clsx(
                      "px-4 py-2 text-right font-mono",
                      p.pnlPct >= 0 ? "text-brand-green" : "text-brand-red"
                    )}
                  >
                    {p.pnlPct >= 0 ? "+" : ""}
                    {p.pnlPct.toFixed(2)}%
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
