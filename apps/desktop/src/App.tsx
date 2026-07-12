import { Routes, Route, Navigate } from "react-router-dom";
import { useEffect } from "react";
import Dashboard from "./components/Dashboard";
import SystemTray from "./components/SystemTray";
import { useAppStore } from "./lib/store";
import { tauriBridge } from "./lib/tauri-bridge";

export default function App() {
  const setAppVersion = useAppStore((s) => s.setAppVersion);
  const setSystemInfo = useAppStore((s) => s.setSystemInfo);

  useEffect(() => {
    // Load app metadata on mount
    tauriBridge.getAppVersion().then(setAppVersion).catch(console.error);
    tauriBridge.getSystemInfo().then(setSystemInfo).catch(console.error);
  }, [setAppVersion, setSystemInfo]);

  return (
    <div className="flex h-screen bg-gray-950 text-gray-100">
      {/* Sidebar navigation */}
      <aside className="flex w-60 flex-col border-r border-gray-800 bg-gray-900">
        <div className="flex h-14 items-center gap-2 border-b border-gray-800 px-4">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500 font-bold text-gray-950">
            A
          </div>
          <span className="text-lg font-semibold tracking-tight">AlphaStack</span>
        </div>
        <nav className="flex-1 space-y-1 px-2 py-4">
          <NavItem to="/dashboard" label="Dashboard" icon="📊" />
          <NavItem to="/portfolio" label="Portfolio" icon="💼" />
          <NavItem to="/markets" label="Markets" icon="📈" />
          <NavItem to="/strategies" label="Strategies" icon="🤖" />
          <NavItem to="/alerts" label="Alerts" icon="🔔" />
          <NavItem to="/settings" label="Settings" icon="⚙️" />
        </nav>
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

function NavItem({ to, label, icon }: { to: string; label: string; icon: string }) {
  const isActive =
    typeof window !== "undefined" && window.location.hash === `#${to}`;

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
