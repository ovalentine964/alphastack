import { useEffect, useState, useCallback } from "react";
import { useTradeStore } from "../stores/tradeStore";
import { useSignalStore } from "../stores/signalStore";
import { api } from "../lib/api";
import { wsClient } from "../lib/websocket";
import type {
  HealthResponse,
  PipelineSignal,
  Trade,
  PortfolioPosition,
  PortfolioSummary,
  WSPriceUpdate,
  LoopStatus,
  RiskLevel,
} from "../lib/types";

export default function Dashboard() {
  const { positions, portfolioSummary, trades, fetchAll: fetchTrades } = useTradeStore();
  const { signals, fetchActiveSignals } = useSignalStore();

  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loopStatus, setLoopStatus] = useState<LoopStatus | null>(null);
  const [prices, setPrices] = useState<Map<string, WSPriceUpdate>>(new Map());
  const [orchestratorRunning, setOrchestratorRunning] = useState(false);
  const [orchestratorError, setOrchestratorError] = useState<string | null>(null);

  // ── Initial data fetch ─────────────────────────────────────
  useEffect(() => {
    api.getHealth().then(setHealth).catch(console.error);
    api.getLoopStatus().then(setLoopStatus).catch(console.error);
    fetchTrades();
    fetchActiveSignals();
  }, [fetchTrades, fetchActiveSignals]);

  // ── WebSocket price updates ────────────────────────────────
  useEffect(() => {
    const unsub = wsClient.onPriceUpdate((update) => {
      setPrices((prev) => {
        const next = new Map(prev);
        next.set(update.symbol, update);
        return next;
      });
    });
    return unsub;
  }, []);

  // ── Run orchestrator ───────────────────────────────────────
  const runOrchestrator = useCallback(async (symbol = "BTC/USDT") => {
    setOrchestratorRunning(true);
    setOrchestratorError(null);
    try {
      await api.runOrchestrator(symbol);
      // Refresh data after orchestrator run
      fetchTrades();
      fetchActiveSignals();
      api.getHealth().then(setHealth).catch(() => {});
    } catch (e) {
      setOrchestratorError((e as Error).message);
    } finally {
      setOrchestratorRunning(false);
    }
  }, [fetchTrades, fetchActiveSignals]);

  // ── Loop control ───────────────────────────────────────────
  const toggleLoop = useCallback(async () => {
    try {
      if (loopStatus?.running) {
        await api.stopLoop();
      } else {
        await api.startLoop();
      }
      const status = await api.getLoopStatus();
      setLoopStatus(status);
    } catch (e) {
      console.error("Loop toggle failed:", e);
    }
  }, [loopStatus]);

  const activeSignals = signals.filter((s) => s.is_active);
  const openTrades = trades.filter((t) => t.status === "open");

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-sm text-gray-500">
            Multi-agent orchestrator &amp; pipeline control
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => runOrchestrator()}
            disabled={orchestratorRunning}
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {orchestratorRunning ? "⏳ Running…" : "🚀 Run Orchestrator"}
          </button>
          <button
            onClick={toggleLoop}
            className={`rounded-lg px-4 py-2 text-sm font-medium text-white ${
              loopStatus?.running
                ? "bg-red-600 hover:bg-red-500"
                : "bg-blue-600 hover:bg-blue-500"
            }`}
          >
            {loopStatus?.running ? "⏹ Stop Loop" : "▶️ Start Loop"}
          </button>
        </div>
      </div>

      {orchestratorError && (
        <div className="rounded-lg border border-red-800 bg-red-900/30 px-4 py-3 text-sm text-red-300">
          Orchestrator error: {orchestratorError}
        </div>
      )}

      {/* ── Agent Status Panel ──────────────────────────────── */}
      <AgentStatusPanel health={health} loopStatus={loopStatus} />

      {/* ── Summary Cards ───────────────────────────────────── */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Portfolio PnL"
          value={formatPnl(portfolioSummary?.total_pnl ?? 0)}
          sub={`${portfolioSummary?.total_trades ?? 0} trades`}
          positive={(portfolioSummary?.total_pnl ?? 0) >= 0}
        />
        <StatCard
          label="Win Rate"
          value={`${(portfolioSummary?.win_rate ?? 0).toFixed(1)}%`}
          sub={`${portfolioSummary?.winning_trades ?? 0}W / ${portfolioSummary?.losing_trades ?? 0}L`}
          positive={(portfolioSummary?.win_rate ?? 0) >= 50}
        />
        <StatCard
          label="Open Positions"
          value={String(positions.length)}
          sub={formatPnl(
            positions.reduce((sum, p) => sum + p.unrealized_pnl, 0)
          )}
          positive={
            positions.reduce((sum, p) => sum + p.unrealized_pnl, 0) >= 0
          }
        />
        <StatCard
          label="Active Signals"
          value={String(activeSignals.length)}
          sub={`${openTrades.length} open trades`}
        />
      </div>

      {/* ── Pipeline Signals ────────────────────────────────── */}
      <div className="rounded-xl border border-gray-800 bg-gray-900/50">
        <div className="flex items-center justify-between border-b border-gray-800 px-4 py-3">
          <h2 className="text-sm font-semibold text-gray-400">
            PIPELINE SIGNALS
          </h2>
          <span className="text-xs text-gray-600">
            {activeSignals.length} active
          </span>
        </div>
        {activeSignals.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-gray-600">
            No active signals — run the orchestrator to generate new ones
          </div>
        ) : (
          <div className="divide-y divide-gray-800">
            {activeSignals.slice(0, 8).map((sig) => (
              <SignalRow key={sig.id} signal={sig} />
            ))}
          </div>
        )}
      </div>

      {/* ── Open Positions & Recent Trades ──────────────────── */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Positions */}
        <div className="rounded-xl border border-gray-800 bg-gray-900/50">
          <div className="border-b border-gray-800 px-4 py-3">
            <h2 className="text-sm font-semibold text-gray-400">POSITIONS</h2>
          </div>
          {positions.length === 0 ? (
            <div className="px-4 py-8 text-center text-sm text-gray-600">
              No open positions
            </div>
          ) : (
            <div className="divide-y divide-gray-800">
              {positions.map((pos) => (
                <PositionRow
                  key={pos.symbol}
                  position={pos}
                  livePrice={prices.get(pos.symbol)}
                />
              ))}
            </div>
          )}
        </div>

        {/* Recent Trades */}
        <div className="rounded-xl border border-gray-800 bg-gray-900/50">
          <div className="border-b border-gray-800 px-4 py-3">
            <h2 className="text-sm font-semibold text-gray-400">
              RECENT TRADES
            </h2>
          </div>
          {trades.length === 0 ? (
            <div className="px-4 py-8 text-center text-sm text-gray-600">
              No trades yet
            </div>
          ) : (
            <div className="divide-y divide-gray-800">
              {trades.slice(0, 8).map((trade) => (
                <TradeRow key={trade.id} trade={trade} />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── Live Prices ─────────────────────────────────────── */}
      <div className="rounded-xl border border-gray-800 bg-gray-900/50">
        <div className="border-b border-gray-800 px-4 py-3">
          <h2 className="text-sm font-semibold text-gray-400">LIVE PRICES</h2>
        </div>
        <div className="divide-y divide-gray-800">
          {["BTC/USDT", "ETH/USDT", "SOL/USDT", "EUR/USD", "GBP/USD"].map(
            (sym) => {
              const p = prices.get(sym);
              return (
                <div
                  key={sym}
                  className="flex items-center justify-between px-4 py-3"
                >
                  <span className="font-mono text-sm font-semibold">
                    {sym}
                  </span>
                  <span className="font-mono text-sm">
                    {p ? formatPrice(p.price, sym) : "—"}
                  </span>
                </div>
              );
            }
          )}
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// Sub-components
// ═══════════════════════════════════════════════════════════════

function AgentStatusPanel({
  health,
  loopStatus,
}: {
  health: HealthResponse | null;
  loopStatus: LoopStatus | null;
}) {
  const agents = health?.agents ?? [];
  const riskLevel: RiskLevel = "low"; // Derived from health when available

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-400">
          AGENT PIPELINE STATUS
        </h2>
        <div className="flex items-center gap-2">
          <span
            className={`h-2 w-2 rounded-full ${
              health?.status === "ok" ? "bg-emerald-400" : "bg-red-400"
            }`}
          />
          <span className="text-xs text-gray-500">
            {health?.status === "ok" ? "System Healthy" : "Degraded"}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {/* Orchestrator */}
        <AgentCard
          name="Orchestrator"
          icon="🧠"
          active={health?.orchestrator_available ?? false}
        />
        {/* Pipeline */}
        <AgentCard
          name="Pipeline"
          icon="⚙️"
          active={health?.pipeline_available ?? false}
        />
        {/* Individual agents */}
        {agents.map((agent) => (
          <AgentCard
            key={agent}
            name={capitalize(agent)}
            icon={agentIcon(agent)}
            active={true}
          />
        ))}
      </div>

      <div className="mt-3 flex items-center gap-4 text-xs text-gray-500">
        {health?.binance_connected !== undefined && (
          <span>
            Exchange:{" "}
            <span
              className={
                health.binance_connected
                  ? "text-emerald-400"
                  : "text-red-400"
              }
            >
              {health.binance_connected ? "Connected" : "Disconnected"}
            </span>
          </span>
        )}
        {health?.oanda_connected !== undefined && (
          <span>
            OANDA:{" "}
            <span
              className={
                health.oanda_connected
                  ? "text-emerald-400"
                  : "text-gray-600"
              }
            >
              {health.oanda_connected ? "Connected" : "Not configured"}
            </span>
          </span>
        )}
        {loopStatus && (
          <span>
            Loop:{" "}
            <span
              className={
                loopStatus.running ? "text-emerald-400" : "text-gray-600"
              }
            >
              {loopStatus.running ? "Running" : "Stopped"}
            </span>
          </span>
        )}
        {health?.uptime_seconds !== undefined && (
          <span>
            Uptime: {formatUptime(health.uptime_seconds)}
          </span>
        )}
        {riskLevel !== "low" && (
          <span className="text-yellow-400">
            ⚠ Risk: {riskLevel}
          </span>
        )}
      </div>
    </div>
  );
}

function AgentCard({
  name,
  icon,
  active,
}: {
  name: string;
  icon: string;
  active: boolean;
}) {
  return (
    <div
      className={`flex flex-col items-center gap-1 rounded-lg border p-2 ${
        active
          ? "border-emerald-800/50 bg-emerald-900/10"
          : "border-gray-800 bg-gray-900/30 opacity-50"
      }`}
    >
      <span className="text-lg">{icon}</span>
      <span className="text-[10px] font-medium text-gray-400">{name}</span>
      <span
        className={`h-1.5 w-1.5 rounded-full ${
          active ? "bg-emerald-400" : "bg-gray-600"
        }`}
      />
    </div>
  );
}

function SignalRow({ signal }: { signal: PipelineSignal }) {
  const isLong = signal.direction === "long";
  const strengthColor =
    signal.strength === "very_strong"
      ? "text-emerald-400"
      : signal.strength === "strong"
        ? "text-emerald-300"
        : signal.strength === "moderate"
          ? "text-yellow-400"
          : "text-gray-400";

  return (
    <div className="flex items-center justify-between px-4 py-3 hover:bg-gray-800/30">
      <div className="flex items-center gap-3">
        <span
          className={`rounded px-1.5 py-0.5 text-xs font-bold ${
            isLong
              ? "bg-emerald-500/10 text-emerald-400"
              : "bg-red-500/10 text-red-400"
          }`}
        >
          {signal.direction.toUpperCase()}
        </span>
        <span className="font-mono text-sm font-semibold">
          {signal.symbol}
        </span>
        <span className={`text-xs ${strengthColor}`}>
          {signal.strength}
        </span>
      </div>
      <div className="flex items-center gap-4">
        <span className="text-xs text-gray-500">
          {(signal.confidence * 100).toFixed(0)}% conf
        </span>
        <span className="text-xs text-gray-500">
          {signal.confluence_score.toFixed(0)} conf.
        </span>
        <span className="font-mono text-sm">
          {formatPrice(signal.entry_price, signal.symbol)}
        </span>
      </div>
    </div>
  );
}

function PositionRow({
  position,
  livePrice,
}: {
  position: PortfolioPosition;
  livePrice?: WSPriceUpdate;
}) {
  const current = livePrice?.price ?? position.current_price;
  const isLong = position.side === "long";
  const pnl = isLong
    ? (current - position.entry_price) * position.quantity
    : (position.entry_price - current) * position.quantity;

  return (
    <div className="flex items-center justify-between px-4 py-3 hover:bg-gray-800/30">
      <div className="flex items-center gap-3">
        <span
          className={`rounded px-1.5 py-0.5 text-xs font-bold ${
            isLong
              ? "bg-emerald-500/10 text-emerald-400"
              : "bg-red-500/10 text-red-400"
          }`}
        >
          {position.side.toUpperCase()}
        </span>
        <span className="font-mono text-sm font-semibold">
          {position.symbol}
        </span>
        <span className="text-xs text-gray-500">
          {position.quantity}
        </span>
      </div>
      <div className="flex items-center gap-4">
        <span className="text-xs text-gray-500">
          {formatPrice(position.entry_price, position.symbol)}
        </span>
        <span className="font-mono text-sm">
          {formatPrice(current, position.symbol)}
        </span>
        <span
          className={`font-mono text-sm font-medium ${
            pnl >= 0 ? "text-emerald-400" : "text-red-400"
          }`}
        >
          {pnl >= 0 ? "+" : ""}
          {pnl.toFixed(2)}
        </span>
      </div>
    </div>
  );
}

function TradeRow({ trade }: { trade: Trade }) {
  const isBuy =
    trade.side === "buy" || trade.side === "long";

  return (
    <div className="flex items-center justify-between px-4 py-3 hover:bg-gray-800/30">
      <div className="flex items-center gap-3">
        <span
          className={`rounded px-1.5 py-0.5 text-xs font-bold ${
            isBuy
              ? "bg-emerald-500/10 text-emerald-400"
              : "bg-red-500/10 text-red-400"
          }`}
        >
          {trade.side.toUpperCase()}
        </span>
        <span className="font-mono text-sm font-semibold">
          {trade.symbol}
        </span>
        <span
          className={`rounded px-1.5 py-0.5 text-xs ${
            trade.status === "open"
              ? "bg-blue-500/10 text-blue-400"
              : trade.status === "closed"
                ? "bg-gray-500/10 text-gray-400"
                : "bg-yellow-500/10 text-yellow-400"
          }`}
        >
          {trade.status}
        </span>
      </div>
      <div className="flex items-center gap-4">
        <span className="text-xs text-gray-500">{trade.quantity}</span>
        <span className="font-mono text-sm">
          {formatPrice(trade.entry_price, trade.symbol)}
        </span>
        {trade.pnl !== null && trade.pnl !== undefined && (
          <span
            className={`font-mono text-sm font-medium ${
              trade.pnl >= 0 ? "text-emerald-400" : "text-red-400"
            }`}
          >
            {trade.pnl >= 0 ? "+" : ""}
            {trade.pnl.toFixed(2)}
          </span>
        )}
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

// ═══════════════════════════════════════════════════════════════
// Helpers
// ═══════════════════════════════════════════════════════════════

function formatPnl(value: number): string {
  const prefix = value >= 0 ? "+$" : "-$";
  return `${prefix}${Math.abs(value).toFixed(2)}`;
}

function formatPrice(price: number | null, symbol: string): string {
  if (price === null || price === undefined) return "—";
  if (symbol.includes("JPY")) return price.toFixed(3);
  if (symbol.includes("/") && !symbol.includes("USDT"))
    return price.toFixed(5);
  if (price < 1) return price.toFixed(4);
  if (price < 100) return price.toFixed(2);
  return price.toFixed(2);
}

function formatUptime(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  const h = Math.floor(seconds / 3600);
  const m = Math.round((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function agentIcon(agent: string): string {
  const icons: Record<string, string> = {
    news: "📰",
    strategy: "📊",
    risk: "🛡️",
    execution: "⚡",
    reflection: "🔍",
  };
  return icons[agent] ?? "🤖";
}
