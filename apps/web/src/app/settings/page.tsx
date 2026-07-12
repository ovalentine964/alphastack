"use client";

import { useEffect, useState } from "react";
import { Save, RefreshCw } from "lucide-react";

interface Settings {
  broker: {
    name: string;
    apiKey: string;
    apiSecret: string;
    paper: boolean;
  };
  risk: {
    maxPositionSize: number;
    maxDailyLoss: number;
    maxDrawdown: number;
    positionSizingMethod: string;
  };
  notifications: {
    enabled: boolean;
    onTrade: boolean;
    onSignal: boolean;
    onError: boolean;
    webhookUrl: string;
  };
}

const defaultSettings: Settings = {
  broker: { name: "alpaca", apiKey: "", apiSecret: "", paper: true },
  risk: {
    maxPositionSize: 10000,
    maxDailyLoss: 500,
    maxDrawdown: 5,
    positionSizingMethod: "fixed",
  },
  notifications: {
    enabled: true,
    onTrade: true,
    onSignal: true,
    onError: true,
    webhookUrl: "",
  },
};

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings>(defaultSettings);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    fetch("/api/settings")
      .then((r) => (r.ok ? r.json() : defaultSettings))
      .then(setSettings)
      .catch(() => {});
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await fetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(settings),
      });
      if (res.ok) {
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-3xl space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Settings</h1>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 px-4 py-2 bg-brand-green text-brand-bg rounded-md font-medium text-sm hover:bg-brand-green/90 transition-colors disabled:opacity-50"
        >
          {saving ? (
            <RefreshCw size={16} className="animate-spin" />
          ) : (
            <Save size={16} />
          )}
          {saved ? "Saved!" : "Save Changes"}
        </button>
      </div>

      {/* Broker Configuration */}
      <section className="bg-brand-surface border border-brand-border rounded-xl p-6 space-y-4">
        <h2 className="text-lg font-semibold">Broker Configuration</h2>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-brand-muted mb-1">Broker</label>
            <select
              value={settings.broker.name}
              onChange={(e) =>
                setSettings({
                  ...settings,
                  broker: { ...settings.broker, name: e.target.value },
                })
              }
              className="w-full bg-brand-bg border border-brand-border rounded-md px-3 py-2 text-sm text-brand-text focus:outline-none focus:ring-1 focus:ring-brand-green"
            >
              <option value="alpaca">Alpaca</option>
              <option value="interactive_brokers">Interactive Brokers</option>
              <option value="binance">Binance</option>
            </select>
          </div>
          <div className="flex items-end">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={settings.broker.paper}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    broker: { ...settings.broker, paper: e.target.checked },
                  })
                }
                className="rounded border-brand-border bg-brand-bg text-brand-green focus:ring-brand-green"
              />
              <span className="text-sm">Paper Trading</span>
            </label>
          </div>
        </div>
        <div>
          <label className="block text-xs text-brand-muted mb-1">API Key</label>
          <input
            type="password"
            value={settings.broker.apiKey}
            onChange={(e) =>
              setSettings({
                ...settings,
                broker: { ...settings.broker, apiKey: e.target.value },
              })
            }
            className="w-full bg-brand-bg border border-brand-border rounded-md px-3 py-2 text-sm text-brand-text placeholder:text-brand-muted focus:outline-none focus:ring-1 focus:ring-brand-green"
            placeholder="Enter API key"
          />
        </div>
        <div>
          <label className="block text-xs text-brand-muted mb-1">API Secret</label>
          <input
            type="password"
            value={settings.broker.apiSecret}
            onChange={(e) =>
              setSettings({
                ...settings,
                broker: { ...settings.broker, apiSecret: e.target.value },
              })
            }
            className="w-full bg-brand-bg border border-brand-border rounded-md px-3 py-2 text-sm text-brand-text placeholder:text-brand-muted focus:outline-none focus:ring-1 focus:ring-brand-green"
            placeholder="Enter API secret"
          />
        </div>
      </section>

      {/* Risk Parameters */}
      <section className="bg-brand-surface border border-brand-border rounded-xl p-6 space-y-4">
        <h2 className="text-lg font-semibold">Risk Parameters</h2>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-brand-muted mb-1">
              Max Position Size ($)
            </label>
            <input
              type="number"
              value={settings.risk.maxPositionSize}
              onChange={(e) =>
                setSettings({
                  ...settings,
                  risk: { ...settings.risk, maxPositionSize: Number(e.target.value) },
                })
              }
              className="w-full bg-brand-bg border border-brand-border rounded-md px-3 py-2 text-sm text-brand-text font-mono focus:outline-none focus:ring-1 focus:ring-brand-green"
            />
          </div>
          <div>
            <label className="block text-xs text-brand-muted mb-1">
              Max Daily Loss ($)
            </label>
            <input
              type="number"
              value={settings.risk.maxDailyLoss}
              onChange={(e) =>
                setSettings({
                  ...settings,
                  risk: { ...settings.risk, maxDailyLoss: Number(e.target.value) },
                })
              }
              className="w-full bg-brand-bg border border-brand-border rounded-md px-3 py-2 text-sm text-brand-text font-mono focus:outline-none focus:ring-1 focus:ring-brand-green"
            />
          </div>
          <div>
            <label className="block text-xs text-brand-muted mb-1">
              Max Drawdown (%)
            </label>
            <input
              type="number"
              value={settings.risk.maxDrawdown}
              onChange={(e) =>
                setSettings({
                  ...settings,
                  risk: { ...settings.risk, maxDrawdown: Number(e.target.value) },
                })
              }
              className="w-full bg-brand-bg border border-brand-border rounded-md px-3 py-2 text-sm text-brand-text font-mono focus:outline-none focus:ring-1 focus:ring-brand-green"
            />
          </div>
          <div>
            <label className="block text-xs text-brand-muted mb-1">
              Position Sizing
            </label>
            <select
              value={settings.risk.positionSizingMethod}
              onChange={(e) =>
                setSettings({
                  ...settings,
                  risk: { ...settings.risk, positionSizingMethod: e.target.value },
                })
              }
              className="w-full bg-brand-bg border border-brand-border rounded-md px-3 py-2 text-sm text-brand-text focus:outline-none focus:ring-1 focus:ring-brand-green"
            >
              <option value="fixed">Fixed Size</option>
              <option value="percent">Percent of Equity</option>
              <option value="kelly">Kelly Criterion</option>
              <option value="volatility">Volatility-Based</option>
            </select>
          </div>
        </div>
      </section>

      {/* Notifications */}
      <section className="bg-brand-surface border border-brand-border rounded-xl p-6 space-y-4">
        <h2 className="text-lg font-semibold">Notifications</h2>
        <div className="space-y-3">
          {[
            ["enabled", "Enable Notifications"],
            ["onTrade", "Notify on Trades"],
            ["onSignal", "Notify on Signals"],
            ["onError", "Notify on Errors"],
          ].map(([key, label]) => (
            <label key={key} className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={
                  settings.notifications[key as keyof typeof settings.notifications] as boolean
                }
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    notifications: {
                      ...settings.notifications,
                      [key]: e.target.checked,
                    },
                  })
                }
                className="rounded border-brand-border bg-brand-bg text-brand-green focus:ring-brand-green"
              />
              <span className="text-sm">{label}</span>
            </label>
          ))}
        </div>
        <div>
          <label className="block text-xs text-brand-muted mb-1">
            Webhook URL
          </label>
          <input
            type="url"
            value={settings.notifications.webhookUrl}
            onChange={(e) =>
              setSettings({
                ...settings,
                notifications: {
                  ...settings.notifications,
                  webhookUrl: e.target.value,
                },
              })
            }
            className="w-full bg-brand-bg border border-brand-border rounded-md px-3 py-2 text-sm text-brand-text placeholder:text-brand-muted focus:outline-none focus:ring-1 focus:ring-brand-green"
            placeholder="https://hooks.example.com/..."
          />
        </div>
      </section>
    </div>
  );
}
