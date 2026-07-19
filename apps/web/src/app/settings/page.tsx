"use client";

import { useEffect, useState } from "react";
import { Save, RefreshCw } from "lucide-react";
import type { AppSettings } from "@/types";
import * as api from "@/lib/api";

const defaultSettings: AppSettings = {
  notifications: {
    email_enabled: true,
    push_enabled: true,
    signal_alerts: true,
    trade_alerts: true,
    price_alerts: false,
  },
  display: {
    theme: "dark",
    language: "en",
    timezone: "UTC",
    currency: "USD",
    decimal_places: 2,
  },
  risk: {
    max_position_size_pct: 5.0,
    max_daily_loss_pct: 2.0,
    max_drawdown_pct: 10.0,
    auto_stop_loss: true,
    default_risk_reward: 2.0,
  },
  trading: {
    default_order_type: "limit",
    confirmation_required: true,
    auto_close_on_target: false,
    paper_trading: true,
  },
};

export default function SettingsPage() {
  const [settings, setSettings] = useState<AppSettings>(defaultSettings);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .getSettings()
      .then(setSettings)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      const result = await api.updateSettings(settings);
      setSettings(result.settings);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      console.error("Save settings failed:", err);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <RefreshCw size={24} className="animate-spin text-brand-muted" />
      </div>
    );
  }

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

      {/* Trading Preferences */}
      <section className="bg-brand-surface border border-brand-border rounded-xl p-6 space-y-4">
        <h2 className="text-lg font-semibold">Trading Preferences</h2>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-brand-muted mb-1">
              Default Order Type
            </label>
            <select
              value={settings.trading.default_order_type}
              onChange={(e) =>
                setSettings({
                  ...settings,
                  trading: {
                    ...settings.trading,
                    default_order_type: e.target.value,
                  },
                })
              }
              className="w-full bg-brand-bg border border-brand-border rounded-md px-3 py-2 text-sm text-brand-text focus:outline-none focus:ring-1 focus:ring-brand-green"
            >
              <option value="market">Market</option>
              <option value="limit">Limit</option>
              <option value="stop">Stop</option>
              <option value="stop_limit">Stop Limit</option>
            </select>
          </div>
          <div className="flex items-end gap-4">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={settings.trading.confirmation_required}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    trading: {
                      ...settings.trading,
                      confirmation_required: e.target.checked,
                    },
                  })
                }
                className="rounded border-brand-border bg-brand-bg text-brand-green focus:ring-brand-green"
              />
              <span className="text-sm">Confirm Orders</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={settings.trading.paper_trading}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    trading: {
                      ...settings.trading,
                      paper_trading: e.target.checked,
                    },
                  })
                }
                className="rounded border-brand-border bg-brand-bg text-brand-green focus:ring-brand-green"
              />
              <span className="text-sm">Paper Trading</span>
            </label>
          </div>
        </div>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={settings.trading.auto_close_on_target}
            onChange={(e) =>
              setSettings({
                ...settings,
                trading: {
                  ...settings.trading,
                  auto_close_on_target: e.target.checked,
                },
              })
            }
            className="rounded border-brand-border bg-brand-bg text-brand-green focus:ring-brand-green"
          />
          <span className="text-sm">Auto-close on target reached</span>
        </label>
      </section>

      {/* Risk Parameters */}
      <section className="bg-brand-surface border border-brand-border rounded-xl p-6 space-y-4">
        <h2 className="text-lg font-semibold">Risk Parameters</h2>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-brand-muted mb-1">
              Max Position Size (%)
            </label>
            <input
              type="number"
              step="0.1"
              value={settings.risk.max_position_size_pct}
              onChange={(e) =>
                setSettings({
                  ...settings,
                  risk: {
                    ...settings.risk,
                    max_position_size_pct: Number(e.target.value),
                  },
                })
              }
              className="w-full bg-brand-bg border border-brand-border rounded-md px-3 py-2 text-sm text-brand-text font-mono focus:outline-none focus:ring-1 focus:ring-brand-green"
            />
          </div>
          <div>
            <label className="block text-xs text-brand-muted mb-1">
              Max Daily Loss (%)
            </label>
            <input
              type="number"
              step="0.1"
              value={settings.risk.max_daily_loss_pct}
              onChange={(e) =>
                setSettings({
                  ...settings,
                  risk: {
                    ...settings.risk,
                    max_daily_loss_pct: Number(e.target.value),
                  },
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
              step="0.1"
              value={settings.risk.max_drawdown_pct}
              onChange={(e) =>
                setSettings({
                  ...settings,
                  risk: {
                    ...settings.risk,
                    max_drawdown_pct: Number(e.target.value),
                  },
                })
              }
              className="w-full bg-brand-bg border border-brand-border rounded-md px-3 py-2 text-sm text-brand-text font-mono focus:outline-none focus:ring-1 focus:ring-brand-green"
            />
          </div>
          <div>
            <label className="block text-xs text-brand-muted mb-1">
              Default Risk/Reward
            </label>
            <input
              type="number"
              step="0.1"
              value={settings.risk.default_risk_reward}
              onChange={(e) =>
                setSettings({
                  ...settings,
                  risk: {
                    ...settings.risk,
                    default_risk_reward: Number(e.target.value),
                  },
                })
              }
              className="w-full bg-brand-bg border border-brand-border rounded-md px-3 py-2 text-sm text-brand-text font-mono focus:outline-none focus:ring-1 focus:ring-brand-green"
            />
          </div>
        </div>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={settings.risk.auto_stop_loss}
            onChange={(e) =>
              setSettings({
                ...settings,
                risk: {
                  ...settings.risk,
                  auto_stop_loss: e.target.checked,
                },
              })
            }
            className="rounded border-brand-border bg-brand-bg text-brand-green focus:ring-brand-green"
          />
          <span className="text-sm">Auto stop-loss</span>
        </label>
      </section>

      {/* Notifications */}
      <section className="bg-brand-surface border border-brand-border rounded-xl p-6 space-y-4">
        <h2 className="text-lg font-semibold">Notifications</h2>
        <div className="space-y-3">
          {(
            [
              ["email_enabled", "Email Notifications"],
              ["push_enabled", "Push Notifications"],
              ["signal_alerts", "Signal Alerts"],
              ["trade_alerts", "Trade Alerts"],
              ["price_alerts", "Price Alerts"],
            ] as const
          ).map(([key, label]) => (
            <label key={key} className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={settings.notifications[key]}
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
      </section>

      {/* Display */}
      <section className="bg-brand-surface border border-brand-border rounded-xl p-6 space-y-4">
        <h2 className="text-lg font-semibold">Display</h2>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-brand-muted mb-1">
              Timezone
            </label>
            <select
              value={settings.display.timezone}
              onChange={(e) =>
                setSettings({
                  ...settings,
                  display: { ...settings.display, timezone: e.target.value },
                })
              }
              className="w-full bg-brand-bg border border-brand-border rounded-md px-3 py-2 text-sm text-brand-text focus:outline-none focus:ring-1 focus:ring-brand-green"
            >
              <option value="UTC">UTC</option>
              <option value="America/New_York">New York</option>
              <option value="America/Chicago">Chicago</option>
              <option value="America/Los_Angeles">Los Angeles</option>
              <option value="Europe/London">London</option>
              <option value="Europe/Berlin">Berlin</option>
              <option value="Asia/Tokyo">Tokyo</option>
              <option value="Asia/Shanghai">Shanghai</option>
              <option value="Asia/Hong_Kong">Hong Kong</option>
              <option value="Asia/Singapore">Singapore</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-brand-muted mb-1">
              Currency
            </label>
            <select
              value={settings.display.currency}
              onChange={(e) =>
                setSettings({
                  ...settings,
                  display: { ...settings.display, currency: e.target.value },
                })
              }
              className="w-full bg-brand-bg border border-brand-border rounded-md px-3 py-2 text-sm text-brand-text focus:outline-none focus:ring-1 focus:ring-brand-green"
            >
              <option value="USD">USD</option>
              <option value="EUR">EUR</option>
              <option value="GBP">GBP</option>
              <option value="JPY">JPY</option>
              <option value="BTC">BTC</option>
            </select>
          </div>
        </div>
      </section>
    </div>
  );
}
