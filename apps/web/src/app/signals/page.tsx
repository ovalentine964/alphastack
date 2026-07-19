"use client";

import { useEffect } from "react";
import { useSignalStore } from "@/stores/signalStore";
import { clsx } from "clsx";
import { Radio, RefreshCw } from "lucide-react";
import type { Signal } from "@/types";

function StrengthBadge({ strength }: { strength: string }) {
  const color =
    strength === "very_strong" || strength === "strong"
      ? "text-brand-green bg-brand-green/10"
      : strength === "moderate"
        ? "text-yellow-400 bg-yellow-400/10"
        : "text-brand-red bg-brand-red/10";
  return (
    <span
      className={clsx(
        "px-2 py-0.5 rounded text-xs font-mono font-medium capitalize",
        color
      )}
    >
      {strength.replace("_", " ")}
    </span>
  );
}

function SignalCard({ signal }: { signal: Signal }) {
  const createdDate = new Date(signal.created_at);
  const expiresDate = signal.expires_at
    ? new Date(signal.expires_at)
    : null;

  return (
    <div className="bg-brand-surface border border-brand-border rounded-xl p-4 hover:border-brand-green/30 transition-colors">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="font-mono font-bold text-lg">{signal.symbol}</span>
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
        <span
          className={clsx(
            "px-2 py-0.5 rounded text-xs font-medium",
            signal.is_active
              ? "bg-brand-green/10 text-brand-green"
              : "bg-brand-muted/10 text-brand-muted"
          )}
        >
          {signal.is_active ? "active" : "inactive"}
        </span>
      </div>

      <div className="space-y-2 text-sm">
        <div className="flex justify-between">
          <span className="text-brand-muted">Strategy</span>
          <span className="font-mono">{signal.strategy_id}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-brand-muted">Confidence</span>
          <span className="font-mono">
            {(signal.confidence * 100).toFixed(1)}%
          </span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-brand-muted">Strength</span>
          <StrengthBadge strength={signal.strength} />
        </div>
        {signal.entry_price != null && (
          <div className="flex justify-between">
            <span className="text-brand-muted">Entry Price</span>
            <span className="font-mono">{signal.entry_price.toFixed(2)}</span>
          </div>
        )}
        {signal.risk_reward != null && (
          <div className="flex justify-between">
            <span className="text-brand-muted">Risk/Reward</span>
            <span className="font-mono">{signal.risk_reward.toFixed(1)}</span>
          </div>
        )}
      </div>

      {/* Confidence bar */}
      <div className="mt-3">
        <div className="h-1.5 bg-brand-border rounded-full overflow-hidden">
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

      {/* Reasoning */}
      {signal.reason && (
        <div className="mt-3 pt-3 border-t border-brand-border/50">
          <p className="text-xs text-brand-muted mb-1">Reasoning</p>
          <p className="text-xs text-brand-text/80">{signal.reason}</p>
        </div>
      )}

      {/* Timestamps */}
      <div className="mt-3 pt-2 border-t border-brand-border/50 flex justify-between text-xs text-brand-muted">
        <span>Created: {createdDate.toLocaleString()}</span>
        {expiresDate && (
          <span>Exp: {expiresDate.toLocaleString()}</span>
        )}
      </div>
    </div>
  );
}

export default function SignalsPage() {
  const { signals, loading, total, filter, fetchSignals, setFilter } =
    useSignalStore();

  useEffect(() => {
    fetchSignals();
  }, [fetchSignals]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold">Signals</h1>
          <span className="text-sm text-brand-muted font-mono">
            {total} total
          </span>
        </div>
        <button
          onClick={() => fetchSignals()}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-1.5 text-sm bg-brand-surface border border-brand-border rounded-md hover:bg-brand-border/30 transition-colors disabled:opacity-50"
        >
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <input
          type="text"
          placeholder="Filter by symbol…"
          value={filter.symbol ?? ""}
          onChange={(e) => {
            setFilter({ ...filter, symbol: e.target.value || undefined });
          }}
          className="bg-brand-surface border border-brand-border rounded-md px-3 py-1.5 text-sm text-brand-text placeholder:text-brand-muted focus:outline-none focus:ring-1 focus:ring-brand-green w-48"
        />
        <select
          value={filter.strategy_id ?? ""}
          onChange={(e) =>
            setFilter({
              ...filter,
              strategy_id: e.target.value || undefined,
            })
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

      {/* Signal cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {signals.length === 0 ? (
          <div className="col-span-full bg-brand-surface border border-brand-border rounded-xl p-12 text-center text-brand-muted">
            <Radio size={48} className="mx-auto mb-4 opacity-30" />
            <p>{loading ? "Loading signals…" : "No signals found"}</p>
          </div>
        ) : (
          signals.map((sig) => <SignalCard key={sig.id} signal={sig} />)
        )}
      </div>
    </div>
  );
}
