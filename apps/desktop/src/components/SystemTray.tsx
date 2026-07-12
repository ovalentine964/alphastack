import { useEffect, useState } from "react";
import { tauriBridge } from "../lib/tauri-bridge";
import { useAppStore } from "../lib/store";

/**
 * System tray status widget shown at the bottom of the sidebar.
 * Displays connection status and quick actions.
 */
export default function SystemTray() {
  const appVersion = useAppStore((s) => s.appVersion);
  const [connected, setConnected] = useState(true);

  useEffect(() => {
    // Simulate connection monitoring
    const interval = setInterval(() => {
      setConnected(Math.random() > 0.05); // 95% uptime simulation
    }, 10000);

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="border-t border-gray-800 p-3">
      {/* Connection status */}
      <div className="flex items-center gap-2 text-xs">
        <span
          className={`h-2 w-2 rounded-full ${
            connected ? "bg-emerald-400" : "bg-red-400"
          }`}
        />
        <span className="text-gray-500">
          {connected ? "Connected" : "Reconnecting…"}
        </span>
      </div>

      {/* Quick actions */}
      <div className="mt-2 flex gap-1">
        <button
          onClick={() => tauriBridge.toggleWindow()}
          className="rounded px-2 py-1 text-xs text-gray-500 transition-colors hover:bg-gray-800 hover:text-gray-300"
          title="Toggle window"
        >
          📌
        </button>
        <button
          onClick={() => tauriBridge.sendNotification("AlphaStack", "Test notification")}
          className="rounded px-2 py-1 text-xs text-gray-500 transition-colors hover:bg-gray-800 hover:text-gray-300"
          title="Test notification"
        >
          🔔
        </button>
      </div>

      {/* Version */}
      {appVersion && (
        <p className="mt-2 text-[10px] text-gray-600">v{appVersion}</p>
      )}
    </div>
  );
}
