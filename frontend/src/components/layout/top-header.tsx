"use client";

import { usePathname, useRouter } from "next/navigation";
import { Bell, ChevronDown, LogOut, Search, Zap } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

import { ThemeToggle } from "./theme-toggle";

const pageTitles: Record<string, string> = {
  "/": "Ask AI Agent",
  "/overview": "Overview",
  "/positions": "Positions",
  "/opportunities": "Opportunities",
  "/executions": "Executions",
  "/policies": "Policies",
  "/wallets": "Wallets",
  "/settings": "Settings",
};

export function TopHeader() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();
  const [query, setQuery] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const title = pageTitles[pathname] ?? "KeeperPilot";

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        const input = document.querySelector<HTMLInputElement>("#global-search");
        input?.focus();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    function onClick(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  function submitSearch(event: React.FormEvent) {
    event.preventDefault();
    router.push(`/opportunities?q=${encodeURIComponent(query.trim())}`);
  }

  return (
    <header className="flex h-16 shrink-0 items-center gap-4 border-b border-border bg-background px-5">
      {/* Breadcrumb / title */}
      <div className="flex min-w-0 items-baseline gap-2">
        <span className="hidden text-sm text-subtle-foreground sm:inline">Workspace</span>
        <span className="hidden text-subtle-foreground sm:inline" aria-hidden>
          /
        </span>
        <h1 className="truncate text-[15px] font-semibold tracking-tight">{title}</h1>
      </div>

      {/* Global search */}
      <form onSubmit={submitSearch} className="mx-auto hidden w-full max-w-[400px] md:block">
        <div className="relative">
          <Search
            className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-subtle-foreground"
            aria-hidden
          />
          <input
            id="global-search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search opportunities…"
            aria-label="Search opportunities"
            className="h-10 w-full rounded-full border border-border bg-surface pl-10 pr-16 text-sm text-foreground placeholder:text-subtle-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background"
          />
          <kbd className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 rounded-md border border-border bg-surface-muted px-1.5 py-0.5 text-[10px] font-medium text-subtle-foreground">
            ⌘K
          </kbd>
        </div>
      </form>

      {/* Right actions */}
      <div className="ml-auto flex items-center gap-1.5 md:ml-0">
        <button
          type="button"
          onClick={() => router.push("/opportunities?scan=1")}
          className="hidden h-10 items-center gap-2 rounded-[18px] bg-accent px-4 text-sm font-medium text-accent-foreground transition-colors hover:bg-accent-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:inline-flex"
        >
          <Zap className="h-4 w-4" aria-hidden />
          Run scan
        </button>

        <button
          type="button"
          aria-label="Notifications"
          className="relative flex h-10 w-10 items-center justify-center rounded-[14px] text-muted-foreground transition-colors hover:bg-surface-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Bell className="h-4.5 w-4.5" aria-hidden />
          <span className="absolute right-2.5 top-2.5 h-1.5 w-1.5 rounded-full bg-accent" aria-hidden />
        </button>

        <ThemeToggle />

        {/* User menu */}
        <div ref={menuRef} className="relative">
          <button
            type="button"
            onClick={() => setMenuOpen((open) => !open)}
            aria-haspopup="menu"
            aria-expanded={menuOpen}
            className="flex h-10 items-center gap-2 rounded-full border border-border bg-surface pl-1 pr-2.5 transition-colors hover:border-border-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-surface-strong text-xs font-semibold uppercase text-foreground">
              {user?.email?.[0] ?? "K"}
            </span>
            <ChevronDown className="h-3.5 w-3.5 text-subtle-foreground" aria-hidden />
          </button>
          {menuOpen && (
            <div
              role="menu"
              className={cn(
                "animate-pop absolute right-0 top-12 z-50 w-56 rounded-[16px] border border-border bg-surface p-1.5",
                "shadow-[0_12px_40px_rgba(0,0,0,0.08)]",
              )}
            >
              <div className="border-b border-border px-3 py-2.5">
                <p className="truncate text-sm font-medium">{user?.email}</p>
                <p className="text-xs text-subtle-foreground">Signed in</p>
              </div>
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setMenuOpen(false);
                  logout();
                  router.push("/login");
                }}
                className="mt-1 flex h-10 w-full items-center gap-2.5 rounded-[12px] px-3 text-sm text-danger transition-colors hover:bg-danger-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <LogOut className="h-4 w-4" aria-hidden />
                Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
