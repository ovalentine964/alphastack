"use client";

import { useEffect, useState } from "react";
import { TradingChart, OHLCData } from "@/components/Charts/TradingChart";
import { clsx } from "clsx";
import {
  TrendingUp,
  Target,
  BarChart3,
  Calendar,
} from "lucide-react";

interface PerformanceMetrics {
  totalTrades: number;
  winRate: number;
  profitFactor: number;
  sharpeRatio: number;
  maxDrawdown: number;
  avgWin: number;
  avgLoss: number;
  bestTrade: number;
  worstTrade: number;
}

function MetricCard({
  label,
  value,
  icon: Icon,
  color,
}: {
  label: string;
  value: string;
  icon: React.ElementType;
  color?: string;
}) {
  return (
    <div className="bg-brand-surface border border-brand-border rounded-xl p-4">
      <div className="flex items-center gap-2 mb-2">
        <Icon size={16} className="text-brand-muted" />
        <span className="text-xs text-brand-muted">{label}</span>
      </div>
      <p
        className={clsx(
          "text-2xl font-bold font-mono",
          color === "green"
            ? "text-brand-green"
            : color === "red"
              ? "text-brand-red"
              : "text-brand-text"
        )}
      >
        {value}
      </p>
    </div>
  );
}

export default function AnalyticsPage() {
  const [metrics, setMetrics] = useState<PerformanceMetrics | null>(null);
  const [equityCurve, setEquityCurve] = useState<OHLCData[]>([]);
  const [days, setDays] = useState(90);

  useEffect(() => {
    fetch("/api/analytics/performance")
      .then((r) => (r.ok ? r.json() : null))
      .then(setMetrics)
      .catch(() => {});

    fetch(`/api/analytics/equity-curve?days=${days}`)
      .then((r) => (r.ok ? r.json() : []))
      .then(setEquityCurve)
      .catch(() => {});
  }, [days]);

  // Fallback demo metrics
  const m: PerformanceMetrics = metrics ?? {
    totalTrades: 0,
    winRate: 0,
    profitFactor: 0,
    sharpeRatio: 0,
    maxDrawdown: 0,
    avgWin: 0,
    avgLoss: 0,
    bestTrade: 0,
    worstTrade: 0,
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Analytics</h1>
        <div className="flex items-center gap-2">
          <Calendar size={16} className="text-brand-muted" />
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="bg-brand-surface border border-brand-border rounded-md px-3 py-1.5 text-sm text-brand-text focus:outline-none focus:ring-1 focus:ring-brand-green"
          >
            <option value={30}>30 Days</option>
            <option value={60}>60 Days</option>
            <option value={90}>90 Days</option>
            <option value={180}>180 Days</option>
            <option value={365}>1 Year</option>
          </select>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          label="Total Trades"
          value={m.totalTrades.toString()}
          icon={BarChart3}
        />
        <MetricCard
          label="Win Rate"
          value={`${m.winRate.toFixed(1)}%`}
          icon={Target}
          color={m.winRate >= 50 ? "green" : "red"}
        />
        <MetricCard
          label="Profit Factor"
          value={m.profitFactor.toFixed(2)}
          icon={TrendingUp}
          color={m.profitFactor >= 1 ? "green" : "red"}
        />
        <MetricCard
          label="Sharpe Ratio"
          value={m.sharpeRatio.toFixed(2)}
          icon={TrendingUp}
          color={m.sharpeRatio >= 1 ? "green" : "red"}
        />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          label="Max Drawdown"
          value={`${m.maxDrawdown.toFixed(2)}%`}
          icon={TrendingUp}
          color="red"
        />
        <MetricCard
          label="Avg Win"
          value={`$${m.avgWin.toFixed(2)}`}
          icon={TrendingUp}
          color="green"
        />
        <MetricCard
          label="Avg Loss"
          value={`$${m.avgLoss.toFixed(2)}`}
          icon={TrendingUp}
          color="red"
        />
        <MetricCard
          label="Best Trade"
          value={`$${m.bestTrade.toFixed(2)}`}
          icon={TrendingUp}
          color="green"
        />
      </div>

      <TradingChart data={equityCurve} height={400} symbol="Equity Curve" />
    </div>
  );
}
