"use client";

import { useEffect, useState } from "react";
import { clsx } from "clsx";
import { Bot, CheckCircle, XCircle, Loader2 } from "lucide-react";
import { getOrchestratorHealth } from "@/lib/api";

interface AgentStatus {
  status: string;
  error?: string;
  agents?: Record<string, { status: string; last_run?: string }>;
  [key: string]: unknown;
}

export function AgentStatusCard() {
  const [health, setHealth] = useState<AgentStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetch = async () => {
      try {
        const data = await getOrchestratorHealth();
        setHealth(data as AgentStatus);
      } catch {
        setHealth({ status: "unreachable" });
      } finally {
        setLoading(false);
      }
    };
    fetch();
    const id = setInterval(fetch, 30_000);
    return () => clearInterval(id);
  }, []);

  const isHealthy = health?.status === "healthy" || health?.status === "running";
  const statusColor = isHealthy
    ? "text-brand-green"
    : health?.status === "unreachable"
      ? "text-brand-muted"
      : "text-brand-red";

  return (
    <div className="bg-brand-surface border border-brand-border rounded-xl">
      <div className="px-4 py-3 border-b border-brand-border flex items-center gap-2">
        <Bot size={16} className="text-brand-accent" />
        <h2 className="text-sm font-semibold">Agent Orchestrator</h2>
      </div>

      <div className="p-4 space-y-3">
        {loading ? (
          <div className="flex items-center justify-center py-4">
            <Loader2 size={20} className="animate-spin text-brand-muted" />
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between">
              <span className="text-xs text-brand-muted">Status</span>
              <div className="flex items-center gap-1.5">
                {isHealthy ? (
                  <CheckCircle size={14} className="text-brand-green" />
                ) : (
                  <XCircle size={14} className="text-brand-red" />
                )}
                <span className={clsx("text-sm font-mono font-medium", statusColor)}>
                  {health?.status ?? "unknown"}
                </span>
              </div>
            </div>

            {health?.error && (
              <div className="text-xs text-brand-red bg-brand-red/5 rounded-md p-2 font-mono">
                {health.error}
              </div>
            )}

            {/* Agent details if available */}
            {health?.agents &&
              Object.entries(health.agents).map(([name, agent]) => (
                <div
                  key={name}
                  className="flex items-center justify-between text-xs"
                >
                  <span className="text-brand-muted capitalize">
                    {name.replace(/_/g, " ")}
                  </span>
                  <span
                    className={clsx(
                      "font-mono",
                      agent.status === "active" || agent.status === "healthy"
                        ? "text-brand-green"
                        : "text-brand-muted"
                    )}
                  >
                    {agent.status}
                  </span>
                </div>
              ))}
          </>
        )}
      </div>
    </div>
  );
}
