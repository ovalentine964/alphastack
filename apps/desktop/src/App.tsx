import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import { useEffect, useState, useCallback } from "react";
import Dashboard from "./components/Dashboard";
import SystemTray from "./components/SystemTray";
import { useAppStore } from "./lib/store";
import { tauriBridge } from "./lib/tauri-bridge";
import { api } from "./lib/api";
import { wsClient } from "./lib/websocket";
import { useTradeStore } from "./stores/tradeStore";
import { useSignalStore } from "./stores/signalStore";
import type { HealthResponse, ConnectionStatus } from "./lib/types";

export default function App() {
  const setAppVersion = useAppStore((s) => s.setAppVersion);
  const setSystemInfo = useAppStore((s) => s.setSystemInfo);

  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [wsStatus, setWsStatus] = useState<ConnectionStatus>("disconnected");
  const [authReady, setAuthReady] = useState(false);

  // ── Bootstrap: init API, auth, WebSocket ───────────────────
  useEffect(() => {
    const bootstrap = async () => {
      // Load Tauri metadata
      tauriBridge.getAppVersion().then(setAppVersion).catch(() => {});
      tauriBridge.getSystemInfo().then(setSystemInfo).catch(() => {});

      // Init API client (loads saved endpoint + token)
      await api.init();

      // If no token, try demo login
      if (!api.token) {
        try {
          await api.demoLogin();
        } catch {
          console.warn("[App] demo login failed — API may be offline");
        }
      }

      setAuthReady(true);

      // Fetch health
      api.getHealth().then(setHealth).catch(() => {});

      // Connect WebSocket
      if (api.token) {
        wsClient.setToken(api.token);
        wsClient.connect();
      }
    };

    bootstrap();

    // Cleanup
    return () => {
      wsClient.disconnect();
    };
  }, [setAppVersion, setSystemInfo]);

  // ── Subscribe to WS status changes ────────────────────────
  useEffect(() => {
    const unsub = wsClient.onStatusChange(setWsStatus);
    return unsub;
  }, []);

  // ── Subscribe to real-time store updates ───────────────────
  useEffect(() => {
    if (!authReady) return;
    const unsubTrades = useTradeStore.getState().subscribeToUpdates();
    const unsubSignals = useSignalStore.getState().subscribeToUpdates();
    return () => {
      unsubTrades();
      unsubSignals();
    };
  }, [authReady]);

  // ── Periodic health poll ───────────────────────────────────
  useEffect(() => {
    const interval = setInterval(() => {
      api.getHealth().then(setHealth).catch(() => {});
    }, 30_000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex h-screen bg-gray-950 text-gray-100">
      {/* Sidebar navigation */}
      <aside className="flex w-60 flex-col border-r border-gray-800 bg-gray-900">
        <div className="flex h-14 items-center gap-2 border-b border-gray-800 px-4">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500 font-bold text-gray-950">
            A
          </div>
          <span className="text-lg font-semibold tracking-tight">
            AlphaStack
          </span>
        </div>

        <nav className="flex-1 space-y-1 px-2 py-4">
          <NavItem to="/dashboard" label="Dashboard" icon="📊" />
          <NavItem to="/portfolio" label="Portfolio" icon="💼" />
          <NavItem to="/markets" label="Markets" icon="📈" />
          <NavItem to="/strategies" label="Strategies" icon="🤖" />
          <NavItem to="/alerts" label="Alerts" icon="🔔" />
          <NavItem to="/settings" label="Settings" icon="⚙️" />
        </nav>

        {/* Pipeline mini-status in sidebar */}
        <PipelineMiniStatus health={health} wsStatus={wsStatus} />

        <SystemTray />
      </aside>

      {/* Main content area */}
      <main className="flex-1 overflow-auto">
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route
            path="/portfolio"
            element={<Placeholder title="Portfolio" />}
          />
          <Route path="/markets" element={<Placeholder title="Markets" />} />
          <Route
            path="/strategies"
            element={<Placeholder title="Strategies" />}
          />
          <Route path="/alerts" element={<Placeholder title="Alerts" />} />
          <Route
            path="/settings"
            element={<Placeholder title="Settings" />}
          />
        </Routes>
      </main>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// Sidebar Sub-components
// ═══════════════════════════════════════════════════════════════

function PipelineMiniStatus({
  health,
  wsStatus,
}: {
  health: HealthResponse | null;
  wsStatus: ConnectionStatus;
}) {
  const agents = health?.agents ?? [];
  const pipelineOk = health?.pipeline_available ?? false;
  const orchestratorOk = health?.orchestrator_available ?? false;

  return (
    <div className="border-t border-gray-800 px-3 py-2">
      <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-gray-600">
        Pipeline
      </p>

      {/* Agent dots */}
      <div className="flex flex-wrap gap-1">
        {agents.map((agent) => (
          <span
            key={agent}
            title={`${agent} — active`}
            className="h-2 w-2 rounded-full bg-emerald-400"
          />
        ))}
        {agents.length === 0 && (
          <span className="text-[10px] text-gray-600">No agents</span>
        )}
      </div>

      {/* Status line */}
      <div className="mt-1.5 flex items-center gap-2 text-[10px] text-gray-600">
        <span
          className={`h-1.5 w-1.5 rounded-full ${
            pipelineOk ? "bg-emerald-400" : "bg-gray-600"
          }`}
          title={pipelineOk ? "Pipeline ready" : "Pipeline offline"}
        />
        <span>Pipeline</span>
        <span
          className={`h-1.5 w-1.5 rounded-full ${
            orchestratorOk ? "bg-emerald-400" : "bg-gray-600"
          }`}
          title={
            orchestratorOk ? "Orchestrator ready" : "Orchestrator offline"
          }
        />
        <span>Orch</span>
      </div>

      {/* WS status */}
      <div className="mt-1 flex items-center gap-1.5 text-[10px] text-gray-600">
        <span
          className={`h-1.5 w-1.5 rounded-full ${
            wsStatus === "connected"
              ? "bg-emerald-400"
              : wsStatus === "reconnecting"
                ? "bg-yellow-400"
                : "bg-red-400"
          }`}
        />
        <span>WS: {wsStatus}</span>
      </div>
    </div>
  );
}

function NavItem({
  to,
  label,
  icon,
}: {
  to: string;
  label: string;
  icon: string;
}) {
  const location = useLocation();
  const isActive = location.pathname === to;

  return (
    <a
      href={`#${to}`}
      className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
        isActive
          ? "bg-gray-800 text-emerald-400"
          : "text-gray-400 hover:bg-gray-800/50 hover:text-gray-200"
      }`}
    >
      <span className="text-base">{icon}</span>
      {label}
    </a>
  );
}

function Placeholder({ title }: { title: string }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 text-gray-500">
      <span className="text-5xl">🚧</span>
      <h2 className="text-2xl font-semibold text-gray-300">{title}</h2>
      <p>Coming soon — this module is under construction.</p>
    </div>
  );
}
