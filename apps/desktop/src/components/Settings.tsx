import { useState, useEffect } from "react";
import { useSettingsStore } from "../stores/settingsStore";
import { tauriBridge } from "../lib/tauri-bridge";
import type { AppSettings } from "../lib/types";

export default function Settings() {
  const {
    settings,
    connectionInfo,
    loaded,
    saving,
    saved,
    loadSettings,
    saveSettings,
    testConnection,
    setEndpoints,
  } = useSettingsStore();

  const [form, setForm] = useState<AppSettings>(settings);
  const [apiEndpoint, setApiEndpoint] = useState(connectionInfo.apiEndpoint);
  const [wsEndpoint, setWsEndpoint] = useState(connectionInfo.wsEndpoint);
  const [connectionTest, setConnectionTest] = useState<{
    ok: boolean;
    message: string;
  } | null>(null);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  useEffect(() => {
    if (loaded) {
      setForm(settings);
      setApiEndpoint(connectionInfo.apiEndpoint);
      setWsEndpoint(connectionInfo.wsEndpoint);
    }
  }, [loaded, settings, connectionInfo]);

  const updateSection = <K extends keyof AppSettings>(
    section: K,
    updates: Partial<AppSettings[K]>
  ) => {
    setForm((f) => ({
      ...f,
      [section]: { ...f[section], ...updates },
    }));
  };

  const handleSave = async () => {
    // Save endpoints locally
    setEndpoints(apiEndpoint, wsEndpoint);
    // Save settings to backend
    await saveSettings(form);
  };

  const handleTestConnection = async () => {
    setTesting(true);
    setConnectionTest(null);
    const result = await testConnection();
    setConnectionTest({ ok: result.ok, message: result.message });
    setTesting(false);
  };

  if (!loaded) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-emerald-500 border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Settings</h1>
          <p className="text-sm text-gray-500">
            Configure your trading environment
          </p>
        </div>
        <div className="flex items-center gap-2">
          {saved && (
            <span className="text-sm text-emerald-400">✓ Saved</span>
          )}
          <button
            onClick={handleSave}
            disabled={saving}
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save Settings"}
          </button>
        </div>
      </div>

      {/* ── Connection ─────────────────────────────────── */}
      <Card title="🌐 Connection">
        <div className="space-y-4">
          <div>
            <Label>API Endpoint</Label>
            <div className="flex gap-2">
              <input
                type="text"
                value={apiEndpoint}
                onChange={(e) => setApiEndpoint(e.target.value)}
                className="flex-1 rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 outline-none focus:border-emerald-500"
                placeholder="http://localhost:8000"
              />
              <button
                onClick={handleTestConnection}
                disabled={testing}
                className="rounded-lg border border-gray-700 px-3 py-2 text-sm text-gray-300 hover:bg-gray-800 disabled:opacity-50"
              >
                {testing ? "Testing…" : "Test"}
              </button>
            </div>
            {connectionTest && (
              <p
                className={`mt-1 text-xs ${
                  connectionTest.ok ? "text-emerald-400" : "text-red-400"
                }`}
              >
                {connectionTest.message}
              </p>
            )}
          </div>
          <div>
            <Label>WebSocket Endpoint</Label>
            <input
              type="text"
              value={wsEndpoint}
              onChange={(e) => setWsEndpoint(e.target.value)}
              className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 outline-none focus:border-emerald-500"
              placeholder="ws://localhost:8000/ws"
            />
          </div>
        </div>
      </Card>

      {/* ── Risk Management ────────────────────────────── */}
      <Card title="🛡️ Risk Management">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <NumberInput
            label="Max Position Size (%)"
            value={form.risk.max_position_size_pct}
            onChange={(v) =>
              updateSection("risk", { max_position_size_pct: v })
            }
          />
          <NumberInput
            label="Max Daily Loss (%)"
            value={form.risk.max_daily_loss_pct}
            onChange={(v) =>
              updateSection("risk", { max_daily_loss_pct: v })
            }
          />
          <NumberInput
            label="Max Drawdown (%)"
            value={form.risk.max_drawdown_pct}
            onChange={(v) =>
              updateSection("risk", { max_drawdown_pct: v })
            }
          />
        </div>
        <div className="mt-4 flex items-center justify-between">
          <div>
            <p className="text-sm text-gray-300">Auto Stop-Loss</p>
            <p className="text-xs text-gray-500">
              Automatically set stop-loss on new positions
            </p>
          </div>
          <Toggle
            checked={form.risk.auto_stop_loss}
            onChange={(v) => updateSection("risk", { auto_stop_loss: v })}
          />
        </div>
      </Card>

      {/* ── Trading ────────────────────────────────────── */}
      <Card title="⚙️ Trading">
        <div className="space-y-4">
          <div>
            <Label>Default Order Type</Label>
            <select
              value={form.trading.default_order_type}
              onChange={(e) =>
                updateSection("trading", { default_order_type: e.target.value })
              }
              className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 outline-none focus:border-emerald-500"
            >
              <option value="market">Market</option>
              <option value="limit">Limit</option>
              <option value="stop">Stop</option>
            </select>
          </div>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-300">Confirmation Required</p>
              <p className="text-xs text-gray-500">
                Require confirmation before executing trades
              </p>
            </div>
            <Toggle
              checked={form.trading.confirmation_required}
              onChange={(v) =>
                updateSection("trading", { confirmation_required: v })
              }
            />
          </div>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-300">Paper Trading</p>
              <p className="text-xs text-gray-500">
                Simulate trades without real funds
              </p>
            </div>
            <Toggle
              checked={form.trading.paper_trading}
              onChange={(v) =>
                updateSection("trading", { paper_trading: v })
              }
            />
          </div>
        </div>
      </Card>

      {/* ── Notifications ──────────────────────────────── */}
      <Card title="🔔 Notifications">
        <div className="space-y-3">
          <ToggleRow
            label="Signal Alerts"
            description="Get notified on new pipeline signals"
            checked={form.notifications.signal_alerts}
            onChange={(v) =>
              updateSection("notifications", { signal_alerts: v })
            }
          />
          <ToggleRow
            label="Trade Alerts"
            description="Get notified on trade executions"
            checked={form.notifications.trade_alerts}
            onChange={(v) =>
              updateSection("notifications", { trade_alerts: v })
            }
          />
          <ToggleRow
            label="Push Notifications"
            description="Enable desktop push notifications"
            checked={form.notifications.push_enabled}
            onChange={(v) =>
              updateSection("notifications", { push_enabled: v })
            }
          />
          <ToggleRow
            label="Email Notifications"
            description="Send alerts to your email"
            checked={form.notifications.email_enabled}
            onChange={(v) =>
              updateSection("notifications", { email_enabled: v })
            }
          />
        </div>
      </Card>

      {/* ── Display ────────────────────────────────────── */}
      <Card title="🎨 Display">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <Label>Theme</Label>
            <select
              value={form.display.theme}
              onChange={(e) =>
                updateSection("display", { theme: e.target.value })
              }
              className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 outline-none focus:border-emerald-500"
            >
              <option value="dark">Dark</option>
              <option value="light">Light</option>
            </select>
          </div>
          <div>
            <Label>Currency</Label>
            <select
              value={form.display.currency}
              onChange={(e) =>
                updateSection("display", { currency: e.target.value })
              }
              className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 outline-none focus:border-emerald-500"
            >
              <option value="USD">USD</option>
              <option value="EUR">EUR</option>
              <option value="GBP">GBP</option>
              <option value="JPY">JPY</option>
            </select>
          </div>
          <div>
            <Label>Timezone</Label>
            <input
              type="text"
              value={form.display.timezone}
              onChange={(e) =>
                updateSection("display", { timezone: e.target.value })
              }
              className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 outline-none focus:border-emerald-500"
            />
          </div>
          <div>
            <Label>Language</Label>
            <select
              value={form.display.language}
              onChange={(e) =>
                updateSection("display", { language: e.target.value })
              }
              className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 outline-none focus:border-emerald-500"
            >
              <option value="en">English</option>
              <option value="zh">中文</option>
              <option value="ja">日本語</option>
            </select>
          </div>
        </div>
      </Card>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// Helper components
// ═══════════════════════════════════════════════════════════════

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-5">
      <h2 className="mb-4 text-sm font-semibold text-gray-300">{title}</h2>
      {children}
    </div>
  );
}

function Label({ children }: { children: React.ReactNode }) {
  return (
    <label className="mb-1 block text-xs font-medium text-gray-500">
      {children}
    </label>
  );
}

function Toggle({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <button
      onClick={() => onChange(!checked)}
      className={`relative h-6 w-11 rounded-full transition-colors ${
        checked ? "bg-emerald-600" : "bg-gray-700"
      }`}
    >
      <span
        className={`absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white transition-transform ${
          checked ? "translate-x-5" : ""
        }`}
      />
    </button>
  );
}

function ToggleRow({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between">
      <div>
        <p className="text-sm text-gray-300">{label}</p>
        <p className="text-xs text-gray-500">{description}</p>
      </div>
      <Toggle checked={checked} onChange={onChange} />
    </div>
  );
}

function NumberInput({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
}) {
  return (
    <div>
      <Label>{label}</Label>
      <input
        type="number"
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 outline-none focus:border-emerald-500"
      />
    </div>
  );
}
