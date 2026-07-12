"use client";

import { useEffect } from "react";
import { useSignalStore } from "@/stores/signalStore";
import { clsx } from "clsx";
import { Radio, RefreshCw } from "lucide-react";

function ConfluenceBadge({ score }: { score: number }) {
  const pct = (score * 100).toFixed(0);
  const color =
    score >= 0.7
      ? "text-brand-green bg-brand-green/10"
      : score >= 0.4
        ? "text-yellow-400 bg-yellow-400/10"
        : "text-brand-red bg-brand-red/10";
  return (
    <span className={clsx("px-2 py-0.5 rounded text-xs font-mono font-medium", color)}>
      {pct}%
    </span>
  );
}

export default function SignalsPage() {
  const { signals, loading, filter, fetchSignals, setFilter } = useSignalStore();

  useEffect(() => {
    fetchSignals();
  }, [fetchSignals]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Signals</h1>
        <button
          onClick={() => fetchSignals()}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-1.5 text-sm bg-brand-surface border border-brand-border rounded-md hover:bg-brand-border/30 transition-colors disabled:opacity-50"
        >
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      <div className="flex items-center gap-4">
        <select
          value={filter.status ?? ""}
          onChange={(e) =>
            setFilter({ ...filter, status: e.target.value || undefined })
          }
          className="bg-brand-surface border border-brand-border rounded-md px-3 py-1.5 text-sm text-brand-text focus:outline-none focus:ring-1 focus:ring-brand-green"
        >
          <option value="">All Statuses</option>
          <option value="active">Active</option>
          <option value="expired">Expired</option>
          <option value="triggered">Triggered</option>
        </select>
        <select
          value={filter.strategy ?? ""}
          onChange={(e) =>
            setFilter({ ...filter, strategy: e.target.value || undefined })
          }
          className="bg-brand-surface border border-brand-border rounded-md px-3 py-1.5 text-sm text-brand-text focus:outline-none focus:ring-1 focus:ring-brand-green"
        >
          <option value="">All Strategies</option>
          <option value="momentum">Momentum</option>
          <option value="mean_reversion">Mean Reversion</option>
          <option value="breakout">Breakout</option>
          <option value="ml_ensemble">ML Ensemble</option>
        </select>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {signals.length === 0 ? (
          <div className="col-span-full bg-brand-surface border border-brand-border rounded-xl p-12 text-center text-brand-muted">
            <Radio size={48} className="mx-auto mb-4 opacity-30" />
            <p>No signals found</p>
          </div>
        ) : (
          signals.map((sig) => (
            <div
              key={sig.id}
              className="bg-brand-surface border border-brand-border rounded-xl p-4 hover:border-brand-green/30 transition-colors"
            >
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className="font-mono font-bold text-lg">{sig.symbol}</span>
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
                <span
                  className={clsx(
                    "px-2 py-0.5 rounded text-xs font-medium",
                    sig.status === "active"
                      ? "bg-brand-green/10 text-brand-green"
                      : sig.status === "triggered"
                        ? "bg-brand-accent/10 text-brand-accent"
                        : "bg-brand-muted/10 text-brand-muted"
                  )}
                >
                  {sig.status}
                </span>
              </div>

              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-brand-muted">Strategy</span>
                  <span className="font-mono">{sig.strategy}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-brand-muted">Confidence</span>
                  <span className="font-mono">
                    {(sig.confidence * 100).toFixed(1)}%
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-brand-muted">Confluence</span>
                  <ConfluenceBadge score={sig.confluence} />
                </div>
              </div>

              {sig.factors.length > 0 && (
                <div className="mt-3 pt-3 border-t border-brand-border/50">
                  <p className="text-xs text-brand-muted mb-1">Factors</p>
                  <div className="flex flex-wrap gap-1">
                    {sig.factors.map((f, i) => (
                      <span
                        key={i}
                        className="px-2 py-0.5 bg-brand-border/30 rounded text-xs text-brand-muted"
                      >
                        {f}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <div className="mt-3 pt-2 border-t border-brand-border/50 flex justify-between text-xs text-brand-muted">
                <span>Created: {new Date(sig.createdAt).toLocaleString()}</span>
                <span>Exp: {new Date(sig.expiresAt).toLocaleString()}</span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
