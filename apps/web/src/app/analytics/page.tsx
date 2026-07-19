"use client";

import { useEffect, useState } from "react";
import { TradingChart, OHLCData } from "@/components/Charts/TradingChart";
import { DrawdownChart } from "@/components/Charts/DrawdownChart";
import { clsx } from "clsx";
import {
  TrendingUp,
  Target,
  BarChart3,
  Calendar,
  Shield,
  Activity,
} from "lucide-react";
import type {
  PerformanceMetrics,
  EquityCurveResponse,
  WinRateResponse,
  RiskMetrics,
} from "@/types";
import * as api from "@/lib/api";

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
  const [performance, setPerformance] = useState<PerformanceMetrics | null>(null);
  const [equityCurve, setEquityCurve] = useState<EquityCurveResponse | null>(null);
  const [winRate, setWinRate] = useState<WinRateResponse | null>(null);
  const [risk, setRisk] = useState<RiskMetrics | null>(null);
  const [days, setDays] = useState(90);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchAll = async () => {
      setLoading(true);
      try {
        const [perf, eq, wr, rm] = await Promise.allSettled([
          api.getAnalyticsPerformance(),
          api.getEquityCurve(days),
          api.getWinRate(),
          api.getRiskMetrics(),
        ]);
        if (perf.status === "fulfilled") setPerformance(perf.value);
        if (eq.status === "fulfilled") setEquityCurve(eq.value);
        if (wr.status === "fulfilled") setWinRate(wr.value);
        if (rm.status === "fulfilled") setRisk(rm.value);
      } finally {
        setLoading(false);
      }
    };
    fetchAll();
  }, [days]);

  // Build equity chart data from equity curve points
  const equityChartData: OHLCData[] =
    equityCurve?.points.map((p) => ({
      time: p.date,
      open: p.equity,
      high: p.equity,
      low: p.equity,
      close: p.equity,
    })) ?? [];

  // Drawdown data
  const drawdownData =
    equityCurve?.points.map((p) => ({
      date: p.date,
      drawdown: p.drawdown_pct,
    })) ?? [];

  const m = performance;
  const wr = winRate;
  const r = risk;

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

      {/* Performance metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          label="Total Return"
          value={m ? `${m.total_return_pct.toFixed(2)}%` : "—"}
          icon={TrendingUp}
          color={m && m.total_return_pct >= 0 ? "green" : "red"}
        />
        <MetricCard
          label="Sharpe Ratio"
          value={m ? m.sharpe_ratio.toFixed(2) : "—"}
          icon={BarChart3}
          color={m && m.sharpe_ratio >= 1 ? "green" : "red"}
        />
        <MetricCard
          label="Sortino Ratio"
          value={m ? m.sortino_ratio.toFixed(2) : "—"}
          icon={TrendingUp}
          color={m && m.sortino_ratio >= 1 ? "green" : "red"}
        />
        <MetricCard
          label="Max Drawdown"
          value={m ? `${m.max_drawdown_pct.toFixed(2)}%` : "—"}
          icon={TrendingUp}
          color="red"
        />
      </div>

      {/* Win/loss stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          label="Total Trades"
          value={wr ? wr.total_trades.toString() : "—"}
          icon={Target}
        />
        <MetricCard
          label="Win Rate"
          value={wr ? `${wr.win_rate.toFixed(1)}%` : "—"}
          icon={Target}
          color={wr && wr.win_rate >= 50 ? "green" : "red"}
        />
        <MetricCard
          label="Profit Factor"
          value={wr ? wr.profit_factor.toFixed(2) : "—"}
          icon={TrendingUp}
          color={wr && wr.profit_factor >= 1 ? "green" : "red"}
        />
        <MetricCard
          label="Avg Win"
          value={wr ? `$${wr.avg_win.toFixed(2)}` : "—"}
          icon={TrendingUp}
          color="green"
        />
      </div>

      {/* Risk metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          label="VaR (95%)"
          value={r ? `$${r.var_95.toFixed(2)}` : "—"}
          icon={Shield}
          color="red"
        />
        <MetricCard
          label="Max Consec. Losses"
          value={r ? r.max_consecutive_losses.toString() : "—"}
          icon={Activity}
          color={r && r.max_consecutive_losses > 5 ? "red" : undefined}
        />
        <MetricCard
          label="Risk/Reward Avg"
          value={r ? r.risk_reward_avg.toFixed(2) : "—"}
          icon={TrendingUp}
          color={r && r.risk_reward_avg >= 1.5 ? "green" : "red"}
        />
        <MetricCard
          label="Calmar Ratio"
          value={m ? m.calmar_ratio.toFixed(2) : "—"}
          icon={BarChart3}
          color={m && m.calmar_ratio >= 1 ? "green" : "red"}
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <TradingChart
          data={equityChartData}
          height={400}
          symbol={`Equity Curve (${equityCurve?.current_equity.toFixed(2) ?? "—"})`}
        />
        <DrawdownChart data={drawdownData} height={400} />
      </div>

      {/* Equity curve summary */}
      {equityCurve && (
        <div className="bg-brand-surface border border-brand-border rounded-xl p-4">
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <p className="text-xs text-brand-muted">Initial Capital</p>
              <p className="text-lg font-mono font-semibold">
                ${equityCurve.initial_capital.toFixed(2)}
              </p>
            </div>
            <div>
              <p className="text-xs text-brand-muted">Current Equity</p>
              <p className="text-lg font-mono font-semibold text-brand-green">
                ${equityCurve.current_equity.toFixed(2)}
              </p>
            </div>
            <div>
              <p className="text-xs text-brand-muted">Trading Days</p>
              <p className="text-lg font-mono font-semibold">
                {m?.trading_days ?? equityCurve.points.length}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
