"use client";

import { useEffect } from "react";
import { useTradeStore } from "@/stores/tradeStore";
import { TrendingUp, TrendingDown, Wallet, DollarSign } from "lucide-react";
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
  const { portfolio, fetchPortfolio } = useTradeStore();

  useEffect(() => {
    fetchPortfolio();
    const id = setInterval(fetchPortfolio, 10_000);
    return () => clearInterval(id);
  }, [fetchPortfolio]);

  const pnlColor =
    portfolio.dayPnl > 0 ? "green" : portfolio.dayPnl < 0 ? "red" : undefined;

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <div className="bg-brand-surface border border-brand-border rounded-xl p-4">
        <Stat label="Balance" value={fmt(portfolio.balance)} icon={Wallet} />
      </div>
      <div className="bg-brand-surface border border-brand-border rounded-xl p-4">
        <Stat label="Equity" value={fmt(portfolio.equity)} icon={DollarSign} />
      </div>
      <div className="bg-brand-surface border border-brand-border rounded-xl p-4">
        <Stat
          label="Day P&L"
          value={fmt(portfolio.dayPnl)}
          icon={portfolio.dayPnl >= 0 ? TrendingUp : TrendingDown}
          color={pnlColor}
        />
      </div>
      <div className="bg-brand-surface border border-brand-border rounded-xl p-4">
        <Stat
          label="Total Return"
          value={`${portfolio.totalReturn >= 0 ? "+" : ""}${portfolio.totalReturn.toFixed(2)}%`}
          icon={portfolio.totalReturn >= 0 ? TrendingUp : TrendingDown}
          color={portfolio.totalReturn >= 0 ? "green" : "red"}
        />
      </div>
    </div>
  );
}
