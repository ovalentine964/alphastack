"use client";

import { useEffect } from "react";
import { useTradeStore } from "@/stores/tradeStore";
import { TrendingUp, TrendingDown, Wallet, DollarSign, BarChart3, Target } from "lucide-react";
import { clsx } from "clsx";

function Stat({
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
    <div className="flex items-center gap-3">
      <div
        className={clsx(
          "p-2 rounded-lg",
          color === "green"
            ? "bg-brand-green/10 text-brand-green"
            : color === "red"
              ? "bg-brand-red/10 text-brand-red"
              : "bg-brand-accent/10 text-brand-accent"
        )}
      >
        <Icon size={20} />
      </div>
      <div>
        <p className="text-xs text-brand-muted">{label}</p>
        <p className="text-lg font-semibold font-mono">{value}</p>
      </div>
    </div>
  );
}

function fmt(n: number): string {
  return n.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  });
}

export function PortfolioCard() {
  const { pnl, positions, fetchPnl, fetchPositions } = useTradeStore();

  useEffect(() => {
    fetchPnl();
    fetchPositions();
    const id = setInterval(() => {
      fetchPnl();
      fetchPositions();
    }, 10_000);
    return () => clearInterval(id);
  }, [fetchPnl, fetchPositions]);

  // Compute portfolio value from positions
  const totalValue = positions.reduce(
    (sum, p) => sum + p.current_price * p.quantity,
    0
  );
  const totalUnrealized = positions.reduce(
    (sum, p) => sum + p.unrealized_pnl,
    0
  );

  const todayPnl = pnl?.today_pnl ?? 0;
  const totalPnl = pnl?.total_pnl ?? 0;
  const winRate = pnl?.win_rate ?? 0;

  return (
    <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
      <div className="bg-brand-surface border border-brand-border rounded-xl p-4">
        <Stat
          label="Positions Value"
          value={fmt(totalValue)}
          icon={Wallet}
        />
      </div>
      <div className="bg-brand-surface border border-brand-border rounded-xl p-4">
        <Stat
          label="Unrealized P&L"
          value={fmt(totalUnrealized)}
          icon={totalUnrealized >= 0 ? TrendingUp : TrendingDown}
          color={totalUnrealized >= 0 ? "green" : "red"}
        />
      </div>
      <div className="bg-brand-surface border border-brand-border rounded-xl p-4">
        <Stat
          label="Today P&L"
          value={fmt(todayPnl)}
          icon={todayPnl >= 0 ? TrendingUp : TrendingDown}
          color={todayPnl >= 0 ? "green" : "red"}
        />
      </div>
      <div className="bg-brand-surface border border-brand-border rounded-xl p-4">
        <Stat
          label="Total P&L"
          value={fmt(totalPnl)}
          icon={DollarSign}
          color={totalPnl >= 0 ? "green" : "red"}
        />
      </div>
      <div className="bg-brand-surface border border-brand-border rounded-xl p-4">
        <Stat
          label="Win Rate"
          value={`${winRate.toFixed(1)}%`}
          icon={Target}
          color={winRate >= 50 ? "green" : "red"}
        />
      </div>
    </div>
  );
}
