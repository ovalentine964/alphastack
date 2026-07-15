import { useState, useEffect } from "react";
import {
  SectionHeader,
  Card,
  Toggle,
  Spinner,
} from "./ui";
import { useSettingsStore } from "../stores/settingsStore";
import { tauriBridge } from "../lib/tauri-bridge";
import { wsClient } from "../lib/websocket";
import { api } from "../lib/api";
import {
  Key,
  Wifi,
  WifiOff,
  Shield,
  Bell,
  Save,
  Check,
  AlertTriangle,
  ExternalLink,
  Trash2,
} from "lucide-react";

export default function Settings() {
  const {
    settings,
    loaded,
    saving,
    saved,
    loadSettings,
    saveSettings,
    testConnection,
  } = useSettingsStore();

  const [form, setForm] = useState(settings);
  const [connectionTest, setConnectionTest] = useState<{
    ok: boolean;
    message: string;
  } | null>(null);
  const [testing, setTesting] = useState(false);
  const [showSecrets, setShowSecrets] = useState(false);

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  useEffect(() => {
    if (loaded) setForm(settings);
  }, [loaded, settings]);

  const update = (key: keyof typeof form, value: unknown) => {
    setForm((f) => ({ ...f, [key]: value }));
  };

  const handleSave = async () => {
    await saveSettings(form);
    // Re-authenticate if API endpoint changed
    if (form.apiEndpoint !== settings.apiEndpoint) {
      api.setBaseUrl(form.apiEndpoint);
    }
    if (form.wsEndpoint !== settings.wsEndpoint) {
      wsClient.setUrl(form.wsEndpoint);
    }
  };

  const handleTestConnection = async () => {
    setTesting(true);
    setConnectionTest(null);
    // Temporarily apply the form's endpoint
    api.setBaseUrl(form.apiEndpoint);
    const result = await testConnection();
    setConnectionTest(result);
    setTesting(false);
    // Restore original if we weren't saving
    api.setBaseUrl(settings.apiEndpoint);
  };

  const handleClearCredentials = async () => {
    await tauriBridge.clearCredentials();
    setForm((f) => ({
      ...f,
      binanceApiKey: "",
      binanceApiSecret: "",
      mimoApiKey: "",
    }));
  };

  if (!loaded) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner size={32} />
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      <SectionHeader title="Settings" subtitle="Configure your trading environment">
        <div className="flex items-center gap-2">
          {saved && (
            <span className="flex items-center gap-1 text-sm text-emerald-400">
              <Check size={14} /> Saved
            </span>
          )}
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
          >
            {saving ? <Spinner size={14} /> : <Save size={14} />}
            Save Settings
          </button>
        </div>
      </SectionHeader>

      {/* ── Connection ─────────────────────────────────── */}
      <Card className="p-5">
        <div className="mb-4 flex items-center gap-2">
          <Wifi size={18} className="text-blue-400" />
          <h2 className="text-sm font-semibold text-gray-300">
            Connection
          </h2>
        </div>

        <div className="space-y-4">
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-500">
              API Endpoint
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={form.apiEndpoint}
                onChange={(e) => update("apiEndpoint", e.target.value)}
                className="flex-1 rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 outline-none focus:border-blue-500"
                placeholder="http://localhost:8000/api/v1"
              />
              <button
                onClick={handleTestConnection}
                disabled={testing}
                className="flex items-center gap-1 rounded-lg border border-gray-700 px-3 py-2 text-sm text-gray-300 hover:bg-gray-800 disabled:opacity-50"
              >
                {testing ? <Spinner size={14} /> : <Wifi size={14} />}
                Test
              </button>
            </div>
            {connectionTest && (
              <p
                className={`mt-1 text-xs ${connectionTest.ok ? "text-emerald-400" : "text-red-400"}`}
              >
                {connectionTest.message}
              </p>
            )}
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-gray-500">
              WebSocket Endpoint
            </label>
            <input
              type="text"
              value={form.wsEndpoint}
              onChange={(e) => update("wsEndpoint", e.target.value)}
              className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 outline-none focus:border-blue-500"
              placeholder="ws://localhost:8000/ws"
            />
          </div>
        </div>
      </Card>

      {/* ── API Keys ───────────────────────────────────── */}
      <Card className="p-5">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Key size={18} className="text-yellow-400" />
            <h2 className="text-sm font-semibold text-gray-300">
              API Keys
            </h2>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowSecrets(!showSecrets)}
              className="text-xs text-gray-500 hover:text-gray-300"
            >
              {showSecrets ? "Hide" : "Show"} keys
            </button>
            <button
              onClick={handleClearCredentials}
              className="flex items-center gap-1 text-xs text-red-400 hover:text-red-300"
              title="Clear all stored credentials"
            >
              <Trash2 size={12} /> Clear
            </button>
          </div>
        </div>

        <div className="space-y-4">
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-500">
              Binance API Key
            </label>
            <input
              type={showSecrets ? "text" : "password"}
              value={form.binanceApiKey}
              onChange={(e) => update("binanceApiKey", e.target.value)}
              className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 outline-none focus:border-blue-500"
              placeholder="Enter your Binance API key"
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-gray-500">
              Binance Secret Key
            </label>
            <input
              type={showSecrets ? "text" : "password"}
              value={form.binanceApiSecret}
              onChange={(e) => update("binanceApiSecret", e.target.value)}
              className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 outline-none focus:border-blue-500"
              placeholder="Enter your Binance secret key"
            />
          </div>

          <div className="flex items-center justify-between rounded-lg border border-gray-700 bg-gray-800/50 px-4 py-3">
            <div>
              <p className="text-sm font-medium text-gray-300">
                Testnet Mode
              </p>
              <p className="text-xs text-gray-500">
                {form.useTestnet
                  ? "Using Binance testnet — no real funds at risk"
                  : "Using live Binance — real funds!"}
              </p>
            </div>
            <Toggle
              checked={form.useTestnet}
              onChange={(v) => update("useTestnet", v)}
            />
          </div>

          {!form.useTestnet && (
            <div className="flex items-start gap-2 rounded-lg border border-yellow-600/30 bg-yellow-600/5 px-3 py-2">
              <AlertTriangle
                size={16}
                className="mt-0.5 shrink-0 text-yellow-500"
              />
              <p className="text-xs text-yellow-400">
                Live trading mode is active. Real funds may be at risk.
                Ensure your API keys have appropriate permissions.
              </p>
            </div>
          )}

          <div>
            <label className="mb-1 block text-xs font-medium text-gray-500">
              Xiaomi MiMo API Key
            </label>
            <input
              type={showSecrets ? "text" : "password"}
              value={form.mimoApiKey}
              onChange={(e) => update("mimoApiKey", e.target.value)}
              className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 outline-none focus:border-blue-500"
              placeholder="Enter your MiMo API key"
            />
            <p className="mt-1 text-xs text-gray-600">
              Used for AI-powered signal analysis
            </p>
          </div>
        </div>
      </Card>

      {/* ── Risk Management ────────────────────────────── */}
      <Card className="p-5">
        <div className="mb-4 flex items-center gap-2">
          <Shield size={18} className="text-emerald-400" />
          <h2 className="text-sm font-semibold text-gray-300">
            Risk Management
          </h2>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-500">
              Max Position Size ($)
            </label>
            <input
              type="number"
              value={form.maxPositionSize}
              onChange={(e) =>
                update("maxPositionSize", Number(e.target.value))
              }
              className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 outline-none focus:border-blue-500"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-500">
              Max Daily Loss ($)
            </label>
            <input
              type="number"
              value={form.maxDailyLoss}
              onChange={(e) =>
                update("maxDailyLoss", Number(e.target.value))
              }
              className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 outline-none focus:border-blue-500"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-500">
              Max Drawdown (%)
            </label>
            <input
              type="number"
              value={form.maxDrawdown}
              onChange={(e) =>
                update("maxDrawdown", Number(e.target.value))
              }
              className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 outline-none focus:border-blue-500"
            />
          </div>
        </div>
      </Card>

      {/* ── Notifications ──────────────────────────────── */}
      <Card className="p-5">
        <div className="mb-4 flex items-center gap-2">
          <Bell size={18} className="text-purple-400" />
          <h2 className="text-sm font-semibold text-gray-300">
            Notifications
          </h2>
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-300">
              Desktop Notifications
            </span>
            <Toggle
              checked={form.notificationsEnabled}
              onChange={(v) => update("notificationsEnabled", v)}
            />
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-300">Auto Refresh</span>
            <Toggle
              checked={form.autoRefresh}
              onChange={(v) => update("autoRefresh", v)}
            />
          </div>
        </div>
      </Card>

      {/* ── About ──────────────────────────────────────── */}
      <Card className="p-5">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-gray-300">
              AlphaStack Desktop
            </h2>
            <p className="text-xs text-gray-500">v0.1.0 — Smart Trading Terminal</p>
          </div>
          <button
            onClick={() => tauriBridge.openUrl("https://alphastack.dev")}
            className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300"
          >
            Documentation <ExternalLink size={12} />
          </button>
        </div>
      </Card>
    </div>
  );
}
