"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  BarChart3,
  BookOpen,
  ChevronsLeft,
  ChevronsRight,
  Gauge,
  HelpCircle,
  Landmark,
  MessagesSquare,
  PanelLeft,
  Scale,
  Settings,
  Sparkles,
  Target,
  WalletCards,
} from "lucide-react";

import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

const navGroups: {
  label: string;
  items: { href: string; label: string; icon: React.ComponentType<{ className?: string }> }[];
}[] = [
  {
    label: "Workspace",
    items: [
      { href: "/", label: "Ask AI Agent", icon: Sparkles },
      { href: "/overview", label: "Overview", icon: Gauge },
      { href: "/opportunities", label: "Opportunities", icon: Target },
      { href: "/positions", label: "Positions", icon: BarChart3 },
    ],
  },
  {
    label: "Operations",
    items: [
      { href: "/executions", label: "Executions", icon: Activity },
      { href: "/policies", label: "Policies", icon: Scale },
      { href: "/wallets", label: "Wallets", icon: WalletCards },
    ],
  },
];

function NavLink({
  href,
  label,
  icon: Icon,
  collapsed,
}: {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  collapsed: boolean;
}) {
  const pathname = usePathname();
  const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
  return (
    <Link
      href={href}
      title={collapsed ? label : undefined}
      className={cn(
        "group flex h-11 items-center gap-3 rounded-[12px] px-3 text-sm font-medium transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        active
          ? "border border-border bg-surface text-foreground shadow-[0_1px_2px_rgba(0,0,0,0.04)]"
          : "text-muted-foreground hover:bg-surface-muted hover:text-foreground",
        collapsed && "justify-center px-0",
      )}
    >
      <Icon
        className={cn(
          "h-4 w-4 shrink-0 transition-colors",
          active ? "text-accent" : "text-subtle-foreground group-hover:text-foreground",
        )}
      />
      {!collapsed && <span>{label}</span>}
    </Link>
  );
}

export function Sidebar({
  collapsed,
  onToggle,
}: {
  collapsed: boolean;
  onToggle: () => void;
}) {
  const { user } = useAuth();

  return (
    <aside
      className={cn(
        "flex h-full flex-col border-r border-border bg-background transition-[width] duration-300 ease-out",
        collapsed ? "w-[72px]" : "w-[232px]",
      )}
    >
      {/* Top: logo + workspace + collapse */}
      <div
        className={cn(
          "flex h-16 items-center gap-2.5 border-b border-border px-4",
          collapsed && "justify-center px-0",
        )}
      >
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[12px] bg-accent text-accent-foreground">
          <Landmark className="h-4.5 w-4.5" aria-hidden />
        </span>
        {!collapsed && (
          <div className="flex min-w-0 flex-col">
            <span className="truncate text-[15px] font-semibold tracking-tight">
              KeeperPilot
            </span>
            <span className="truncate text-[11px] text-subtle-foreground">
              Autonomous DeFi Operator
            </span>
          </div>
        )}
        {!collapsed && (
          <button
            type="button"
            onClick={onToggle}
            aria-label="Collapse sidebar"
            className="ml-auto flex h-8 w-8 items-center justify-center rounded-[10px] text-subtle-foreground transition-colors hover:bg-surface-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <ChevronsLeft className="h-4 w-4" aria-hidden />
          </button>
        )}
      </div>

      {/* Collapsed toggle pill */}
      {collapsed && (
        <button
          type="button"
          onClick={onToggle}
          aria-label="Expand sidebar"
          className="mx-2 mt-3 flex h-9 items-center justify-center rounded-[12px] text-subtle-foreground transition-colors hover:bg-surface-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <ChevronsRight className="h-4 w-4" aria-hidden />
        </button>
      )}

      {/* Primary action */}
      {!collapsed && (
        <div className="px-3 pt-4">
          <Link
            href="/"
            className="flex h-11 items-center gap-2 rounded-full bg-accent px-4 text-sm font-medium text-accent-foreground transition-colors hover:bg-accent-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <MessagesSquare className="h-4 w-4" aria-hidden />
            New chat
          </Link>
        </div>
      )}
      {collapsed && (
        <div className="px-2 pt-4">
          <Link
            href="/"
            aria-label="New chat"
            className="flex h-11 items-center justify-center rounded-full bg-accent text-accent-foreground transition-colors hover:bg-accent-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <MessagesSquare className="h-4 w-4" aria-hidden />
          </Link>
        </div>
      )}

      {/* Navigation groups */}
      <nav className="flex-1 overflow-y-auto px-3 py-4">
        {navGroups.map((group) => (
          <div key={group.label} className={cn("mb-6", collapsed && "mb-4")}>
            {!collapsed && (
              <p className="mb-1.5 px-3 text-[11px] font-semibold uppercase tracking-wider text-subtle-foreground">
                {group.label}
              </p>
            )}
            <div className="flex flex-col gap-0.5">
              {group.items.map((item) => (
                <NavLink
                  key={item.href}
                  href={item.href}
                  label={item.label}
                  icon={item.icon}
                  collapsed={collapsed}
                />
              ))}
            </div>
          </div>
        ))}
      </nav>

      {/* Bottom utility */}
      <div
        className={cn(
          "flex flex-col gap-0.5 border-t border-border px-3 py-3",
          collapsed && "items-center px-0",
        )}
      >
        <NavLink href="/settings" label="Settings" icon={Settings} collapsed={collapsed} />
        <NavLink href="#" label="Help Center" icon={HelpCircle} collapsed={collapsed} />
        <NavLink href="#" label="Documentation" icon={BookOpen} collapsed={collapsed} />

        {/* User profile */}
        <div
          className={cn(
            "mt-2 flex items-center gap-3 rounded-[14px] border border-border bg-surface p-2",
            collapsed && "w-fit border-0 bg-transparent p-1",
          )}
        >
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-surface-strong text-xs font-semibold uppercase text-foreground">
            {user?.email?.[0] ?? "K"}
          </span>
          {!collapsed && (
            <div className="min-w-0 flex-1">
              <p className="truncate text-[13px] font-medium">{user?.email ?? "Guest"}</p>
              <p className="text-[11px] text-subtle-foreground">Free plan</p>
            </div>
          )}
          {!collapsed && (
            <PanelLeft className="h-4 w-4 text-subtle-foreground" aria-hidden />
          )}
        </div>
      </div>
    </aside>
  );
}
