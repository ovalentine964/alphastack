"use client";

import { useEffect } from "react";
import { PortfolioCard } from "@/components/Dashboard/PortfolioCard";
import { PositionsTable } from "@/components/Dashboard/PositionsTable";
import { TradingChart } from "@/components/Charts/TradingChart";
import { useTradeStore } from "@/stores/tradeStore";
import { useSignalStore } from "@/stores/signalStore";
import { clsx } from "clsx";
import { Activity } from "lucide-react";

export default function DashboardPage() {
  const { trades, fetchTrades } = useTradeStore();
  const { signals, fetchSignals } = useSignalStore();

  useEffect(() => {
    fetchTrades(20);
    fetchSignals();
  }, [fetchTrades, fetchSignals]);

  const recentSignals = signals.filter((s) => s.status === "active").slice(0, 5);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Dashboard</h1>

      <PortfolioCard />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <TradingChart data={[]} height={350} symbol="Portfolio" />
        </div>

        <div className="bg-brand-surface border border-brand-border rounded-xl">
          <div className="px-4 py-3 border-b border-brand-border flex items-center gap-2">
            <Activity size={16} className="text-brand-green" />
            <h2 className="text-sm font-semibold">Recent Signals</h2>
          </div>
          <div className="divide-y divide-brand-border/50">
            {recentSignals.length === 0 ? (
              <p className="px-4 py-6 text-center text-brand-muted text-sm">
                No active signals
              </p>
            ) : (
              recentSignals.map((sig) => (
                <div key={sig.id} className="px-4 py-3">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-sm font-medium">
                      {sig.symbol}
                    </span>
                    <span
                      className={clsx(
                        "px-2 py-0.5 rounded text-xs font-medium",
                        sig.direction === "LONG"
                          ? "bg-brand-green/10 text-brand-green"
                          : "bg-brand-red/10 text-brand-red"
                      )}
                    >
                      {sig.direction}
                    </span>
                  </div>
                  <div className="mt-1 flex items-center justify-between text-xs text-brand-muted">
                    <span>{sig.strategy}</span>
                    <span>Confidence: {(sig.confidence * 100).toFixed(0)}%</span>
                  </div>
                  <div className="mt-2 h-1.5 bg-brand-border rounded-full overflow-hidden">
                    <div
                      className={clsx(
                        "h-full rounded-full",
                        sig.confluence >= 0.7
                          ? "bg-brand-green"
                          : sig.confluence >= 0.4
                            ? "bg-yellow-400"
                            : "bg-brand-red"
                      )}
                      style={{ width: `${sig.confluence * 100}%` }}
                    />
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <PositionsTable />

        <div className="bg-brand-surface border border-brand-border rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-brand-border">
            <h2 className="text-sm font-semibold">Recent Trades</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-brand-muted text-xs border-b border-brand-border">
                  <th className="px-4 py-2 text-left">Time</th>
                  <th className="px-4 py-2 text-left">Symbol</th>
                  <th className="px-4 py-2 text-left">Side</th>
                  <th className="px-4 py-2 text-right">Price</th>
                  <th className="px-4 py-2 text-right">P&L</th>
                </tr>
              </thead>
              <tbody>
                {trades.slice(0, 10).map((t) => (
                  <tr
                    key={t.id}
                    className="border-b border-brand-border/50 hover:bg-brand-border/10"
                  >
                    <td className="px-4 py-2 text-xs text-brand-muted">
                      {new Date(t.executedAt).toLocaleTimeString()}
                    </td>
                    <td className="px-4 py-2 font-mono">{t.symbol}</td>
                    <td className="px-4 py-2">
                      <span
                        className={clsx(
                          "text-xs font-medium",
                          t.side === "BUY"
                            ? "text-brand-green"
                            : "text-brand-red"
                        )}
                      >
                        {t.side}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-right font-mono">
                      {t.price.toFixed(2)}
                    </td>
                    <td
                      className={clsx(
                        "px-4 py-2 text-right font-mono",
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
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
