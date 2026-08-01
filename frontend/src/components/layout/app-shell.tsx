"use client";

import { useState } from "react";

import { cn } from "@/lib/utils";

import { Sidebar } from "./sidebar";
import { TopHeader } from "./top-header";

export function AppShell({
  children,
  contextPanel,
}: {
  children: React.ReactNode;
  contextPanel?: React.ReactNode;
}) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className="flex h-full overflow-hidden">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((value) => !value)} />

      <div className="flex min-w-0 flex-1 flex-col">
        <TopHeader />
        <main className="min-h-0 flex-1 overflow-y-auto">{children}</main>
      </div>

      {contextPanel ? (
        <aside
          className={cn(
            "hidden h-full shrink-0 border-l border-border bg-surface lg:block",
            "w-[320px]",
          )}
        >
          {contextPanel}
        </aside>
      ) : null}
    </div>
  );
}
