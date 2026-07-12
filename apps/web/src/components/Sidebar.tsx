"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { clsx } from "clsx";
import {
  LayoutDashboard,
  ArrowLeftRight,
  Radio,
  BarChart3,
  Settings,
} from "lucide-react";

const nav = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/trades", label: "Trades", icon: ArrowLeftRight },
  { href: "/signals", label: "Signals", icon: Radio },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-56 bg-brand-surface border-r border-brand-border flex flex-col">
      <div className="p-4 border-b border-brand-border">
        <h1 className="text-xl font-bold text-brand-green tracking-wider">
          ⚡ AlphaStack
        </h1>
        <p className="text-xs text-brand-muted mt-1">Trading Dashboard</p>
      </div>
      <nav className="flex-1 p-2 space-y-1">
        {nav.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={clsx(
              "flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors",
              pathname === href
                ? "bg-brand-green/10 text-brand-green"
                : "text-brand-muted hover:text-brand-text hover:bg-brand-border/30"
            )}
          >
            <Icon size={18} />
            {label}
          </Link>
        ))}
      </nav>
      <div className="p-4 border-t border-brand-border text-xs text-brand-muted">
        v0.1.0
      </div>
    </aside>
  );
}
