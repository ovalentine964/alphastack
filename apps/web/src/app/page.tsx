"use client";

import { useEffect, useState } from "react";
import { PortfolioCard } from "@/components/Dashboard/PortfolioCard";
import { AgentStatusCard } from "@/components/Dashboard/AgentStatusCard";
import { PositionsTable } from "@/components/Dashboard/PositionsTable";
import { TradingChart } from "@/components/Charts/TradingChart";
import { useTradeStore } from "@/stores/tradeStore";
import { useSignalStore } from "@/stores/signalStore";
import { clsx } from "clsx";
import { Activity, Zap } from "lucide-react";
import type { Signal } from "@/types";

export default function DashboardPage() {
  const { trades, fetchTrades } = useTradeStore();
  const { signals, fetchSignals } = useSignalStore();

  useEffect(() => {
    fetchTrades({ page_size: 20 });
    fetchSignals();
    // Refresh trades every 10s
    const id = setInterval(() => fetchTrades({ page_size: 20 }), 10_000);
    return () => clearInterval(id);
  }, [fetchTrades, fetchSignals]);

  const activeSignals = signals.filter((s) => s.is_active).slice(0, 5);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <div className="flex items-center gap-2 text-xs text-brand-muted">
          <div className="w-2 h-2 rounded-full bg-brand-green animate-pulse" />
          Live
        </div>
      </div>

      {/* Portfolio summary cards */}
      <PortfolioCard />

      {/* Agent status + Chart row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <TradingChart data={[]} height={350} symbol="Portfolio" />
        </div>

        {/* Active signals panel */}
        <div className="bg-brand-surface border border-brand-border rounded-xl">
          <div className="px-4 py-3 border-b border-brand-border flex items-center gap-2">
            <Activity size={16} className="text-brand-green" />
            <h2 className="text-sm font-semibold">Active Signals</h2>
            <span className="ml-auto text-xs text-brand-muted font-mono">
              {activeSignals.length}
            </span>
          </div>
          <div className="divide-y divide-brand-border/50">
            {activeSignals.length === 0 ? (
              <p className="px-4 py-6 text-center text-brand-muted text-sm">
                No active signals
              </p>
            ) : (
              activeSignals.map((sig) => (
                <SignalRow key={sig.id} signal={sig} />
              ))
            )}
          </div>
        </div>
      </div>

      {/* Agent status + Positions + Recent trades */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <AgentStatusCard />

        <div className="lg:col-span-2">
          <PositionsTable />
        </div>
      </div>

      {/* Recent trades table */}
      <div className="bg-brand-surface border border-brand-border rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-brand-border flex items-center gap-2">
          <Zap size={16} className="text-brand-accent" />
          <h2 className="text-sm font-semibold">Recent Trades</h2>
          <span className="ml-auto text-xs text-brand-muted font-mono">
            {trades.length} shown
          </span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-brand-muted text-xs border-b border-brand-border">
                <th className="px-4 py-2 text-left">Time</th>
                <th className="px-4 py-2 text-left">Symbol</th>
                <th className="px-4 py-2 text-left">Side</th>
                <th className="px-4 py-2 text-right">Qty</th>
                <th className="px-4 py-2 text-right">Price</th>
                <th className="px-4 py-2 text-left">Status</th>
                <th className="px-4 py-2 text-right">P&L</th>
              </tr>
            </thead>
            <tbody>
              {trades.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-brand-muted">
                    No trades yet
                  </td>
                </tr>
              ) : (
                trades.slice(0, 15).map((t) => (
                  <tr
                    key={t.id}
                    className="border-b border-brand-border/50 hover:bg-brand-border/10 transition-colors"
                  >
                    <td className="px-4 py-2 text-xs text-brand-muted font-mono">
                      {new Date(t.opened_at).toLocaleTimeString()}
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
                      {(t.entry_price ?? 0).toFixed(2)}
                    </td>
                    <td className="px-4 py-2">
                      <span
                        className={clsx(
                          "px-2 py-0.5 rounded text-xs font-medium",
                          t.status === "open"
                            ? "bg-brand-accent/10 text-brand-accent"
                            : t.status === "closed"
                              ? "bg-brand-muted/10 text-brand-muted"
                              : "bg-yellow-400/10 text-yellow-400"
                        )}
                      >
                        {t.status}
                      </span>
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

function SignalRow({ signal }: { signal: Signal }) {
  const strengthColor =
    signal.strength === "very_strong" || signal.strength === "strong"
      ? "text-brand-green"
      : signal.strength === "moderate"
        ? "text-yellow-400"
        : "text-brand-red";

  return (
    <div className="px-4 py-3">
      <div className="flex items-center justify-between">
        <span className="font-mono text-sm font-medium">{signal.symbol}</span>
        <span
          className={clsx(
            "px-2 py-0.5 rounded text-xs font-medium",
            signal.direction === "long"
              ? "bg-brand-green/10 text-brand-green"
              : signal.direction === "short"
                ? "bg-brand-red/10 text-brand-red"
                : "bg-brand-muted/10 text-brand-muted"
          )}
        >
          {signal.direction.toUpperCase()}
        </span>
      </div>
      <div className="mt-1 flex items-center justify-between text-xs text-brand-muted">
        <span>{signal.strategy_id}</span>
        <span className={strengthColor}>{signal.strength}</span>
      </div>
      <div className="mt-1 flex items-center justify-between text-xs text-brand-muted">
        <span>Conf: {(signal.confidence * 100).toFixed(0)}%</span>
        {signal.risk_reward != null && (
          <span>RR: {signal.risk_reward.toFixed(1)}</span>
        )}
      </div>
      <div className="mt-2 h-1.5 bg-brand-border rounded-full overflow-hidden">
        <div
          className={clsx(
            "h-full rounded-full transition-all",
            signal.confidence >= 0.7
              ? "bg-brand-green"
              : signal.confidence >= 0.4
                ? "bg-yellow-400"
                : "bg-brand-red"
          )}
          style={{ width: `${signal.confidence * 100}%` }}
        />
      </div>
    </div>
  );
}
