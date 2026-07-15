import { clsx } from "clsx";
import { Loader2 } from "lucide-react";

// ── Stat Card ─────────────────────────────────────────────
export function StatCard({
  label,
  value,
  sub,
  positive,
  accent,
}: {
  label: string;
  value: string;
  sub?: string;
  positive?: boolean;
  accent?: "green" | "red" | "blue";
}) {
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
      <p className="text-xs font-medium text-gray-500">{label}</p>
      <p
        className={clsx(
          "mt-1 text-2xl font-bold",
          accent === "green" && "text-emerald-400",
          accent === "red" && "text-red-400",
          accent === "blue" && "text-blue-400"
        )}
      >
        {value}
      </p>
      {sub && (
        <p
          className={clsx(
            "mt-1 text-xs",
            positive === true
              ? "text-emerald-400"
              : positive === false
                ? "text-red-400"
                : "text-gray-500"
          )}
        >
          {sub}
        </p>
      )}
    </div>
  );
}

// ── Section Header ────────────────────────────────────────
export function SectionHeader({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between">
      <div>
        <h1 className="text-2xl font-bold">{title}</h1>
        {subtitle && <p className="text-sm text-gray-500">{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}

// ── Card wrapper ──────────────────────────────────────────
export function Card({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={clsx(
        "rounded-xl border border-gray-800 bg-gray-900/50",
        className
      )}
    >
      {children}
    </div>
  );
}

// ── Empty state ───────────────────────────────────────────
export function EmptyState({
  icon,
  title,
  description,
}: {
  icon: string;
  title: string;
  description: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12 text-gray-500">
      <span className="text-4xl">{icon}</span>
      <p className="text-sm font-medium text-gray-300">{title}</p>
      <p className="text-xs">{description}</p>
    </div>
  );
}

// ── Loading spinner ───────────────────────────────────────
export function Spinner({ size = 20 }: { size?: number }) {
  return (
    <Loader2
      size={size}
      className="animate-spin text-gray-500"
    />
  );
}

// ── Badge ─────────────────────────────────────────────────
export function Badge({
  children,
  variant = "default",
}: {
  children: React.ReactNode;
  variant?: "default" | "green" | "red" | "blue" | "yellow";
}) {
  const colors = {
    default: "bg-gray-700 text-gray-300",
    green: "bg-emerald-500/15 text-emerald-400",
    red: "bg-red-500/15 text-red-400",
    blue: "bg-blue-500/15 text-blue-400",
    yellow: "bg-yellow-500/15 text-yellow-400",
  };
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
        colors[variant]
      )}
    >
      {children}
    </span>
  );
}

// ── Toggle switch ─────────────────────────────────────────
export function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label?: string;
}) {
  return (
    <label className="flex cursor-pointer items-center gap-3">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={clsx(
          "relative inline-flex h-6 w-11 items-center rounded-full transition-colors",
          checked ? "bg-emerald-600" : "bg-gray-700"
        )}
      >
        <span
          className={clsx(
            "inline-block h-4 w-4 rounded-full bg-white transition-transform",
            checked ? "translate-x-6" : "translate-x-1"
          )}
        />
      </button>
      {label && <span className="text-sm text-gray-300">{label}</span>}
    </label>
  );
}

// ── P&L formatter ─────────────────────────────────────────
export function formatPnl(value: number): string {
  const prefix = value >= 0 ? "+" : "";
  return `${prefix}$${value.toFixed(2)}`;
}

export function formatPercent(value: number): string {
  const prefix = value >= 0 ? "+" : "";
  return `${prefix}${value.toFixed(2)}%`;
}

export function formatCurrency(value: number): string {
  return `$${value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
