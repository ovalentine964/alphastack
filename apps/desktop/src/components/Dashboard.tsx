import { useEffect, useState } from "react";
import { tauriBridge } from "../lib/tauri-bridge";

interface MarketTicker {
  symbol: string;
  price: number;
  change: number;
  changePercent: number;
}

const MOCK_TICKERS: MarketTicker[] = [
  { symbol: "AAPL", price: 189.84, change: 2.31, changePercent: 1.23 },
  { symbol: "MSFT", price: 422.56, change: -1.45, changePercent: -0.34 },
  { symbol: "GOOGL", price: 176.23, change: 3.87, changePercent: 2.24 },
  { symbol: "AMZN", price: 201.4, change: 0.92, changePercent: 0.46 },
  { symbol: "NVDA", price: 134.66, change: 5.12, changePercent: 3.95 },
  { symbol: "TSLA", price: 263.41, change: -4.23, changePercent: -1.58 },
];

export default function Dashboard() {
  const [tickers] = useState<MarketTicker[]>(MOCK_TICKERS);
  const [watchlist, setWatchlist] = useState<string[]>([]);

  useEffect(() => {
    // Load saved watchlist from Tauri store
    tauriBridge
      .getSetting<string[]>("watchlist")
      .then((v) => v && setWatchlist(v))
      .catch(() => {});
  }, []);

  const totalValue = tickers.reduce((acc, t) => acc + t.price, 0);
  const totalChange = tickers.reduce((acc, t) => acc + t.change, 0);

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-sm text-gray-500">
            Real-time market overview
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() =>
              tauriBridge.sendNotification(
                "Market Alert",
                "AAPL crossed your target price!"
              )
            }
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500"
          >
            Test Notification
          </button>
        </div>
      </div>

      {/* Portfolio summary cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Portfolio Value"
          value={`$${totalValue.toFixed(2)}`}
          sub={`${totalChange >= 0 ? "+" : ""}${totalChange.toFixed(2)} today`}
          positive={totalChange >= 0}
        />
        <StatCard
          label="Day's Gain"
          value={`${totalChange >= 0 ? "+" : ""}$${totalChange.toFixed(2)}`}
          sub={`${((totalChange / totalValue) * 100).toFixed(2)}%`}
          positive={totalChange >= 0}
        />
        <StatCard label="Positions" value={String(tickers.length)} sub="Active" />
        <StatCard
          label="Alerts"
          value={String(watchlist.length)}
          sub="Watching"
        />
      </div>

      {/* Market tickers */}
      <div className="rounded-xl border border-gray-800 bg-gray-900/50">
        <div className="border-b border-gray-800 px-4 py-3">
          <h2 className="text-sm font-semibold text-gray-400">MARKET TICKERS</h2>
        </div>
        <div className="divide-y divide-gray-800">
          {tickers.map((t) => (
            <TickerRow key={t.symbol} ticker={t} />
          ))}
        </div>
      </div>

      {/* Quick actions */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <ActionCard
          title="Portfolio Analysis"
          description="View detailed breakdown of your holdings"
          icon="📊"
        />
        <ActionCard
          title="Strategy Builder"
          description="Create and backtest trading strategies"
          icon="🤖"
        />
        <ActionCard
          title="Market Scanner"
          description="Scan for opportunities across markets"
          icon="🔍"
        />
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  sub,
  positive,
}: {
  label: string;
  value: string;
  sub?: string;
  positive?: boolean;
}) {
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
      <p className="text-xs font-medium text-gray-500">{label}</p>
      <p className="mt-1 text-2xl font-bold">{value}</p>
      {sub && (
        <p
          className={`mt-1 text-xs ${
            positive === true
              ? "text-emerald-400"
              : positive === false
                ? "text-red-400"
                : "text-gray-500"
          }`}
        >
          {sub}
        </p>
      )}
    </div>
  );
}

function TickerRow({ ticker }: { ticker: MarketTicker }) {
  const isPositive = ticker.change >= 0;

  return (
    <div className="flex items-center justify-between px-4 py-3 hover:bg-gray-800/30">
      <div className="flex items-center gap-3">
        <span className="font-mono text-sm font-semibold">{ticker.symbol}</span>
      </div>
      <div className="flex items-center gap-4">
        <span className="font-mono text-sm">${ticker.price.toFixed(2)}</span>
        <span
          className={`rounded px-2 py-0.5 text-xs font-medium ${
            isPositive
              ? "bg-emerald-500/10 text-emerald-400"
              : "bg-red-500/10 text-red-400"
          }`}
        >
          {isPositive ? "+" : ""}
          {ticker.changePercent.toFixed(2)}%
        </span>
      </div>
    </div>
  );
}

function ActionCard({
  title,
  description,
  icon,
}: {
  title: string;
  description: string;
  icon: string;
}) {
  return (
    <button className="flex items-start gap-4 rounded-xl border border-gray-800 bg-gray-900/50 p-4 text-left transition-colors hover:border-gray-700 hover:bg-gray-800/50">
      <span className="text-2xl">{icon}</span>
      <div>
        <h3 className="text-sm font-semibold">{title}</h3>
        <p className="mt-1 text-xs text-gray-500">{description}</p>
      </div>
    </button>
  );
}
