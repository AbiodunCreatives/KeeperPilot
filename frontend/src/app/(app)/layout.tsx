"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { useAuth } from "@/lib/auth";

export default function DashboardLayout({
  children,
  contextPanel,
}: {
  children: React.ReactNode;
  contextPanel?: React.ReactNode;
}) {
  const { user, ready } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (ready && !user) {
      router.replace("/login");
    }
  }, [ready, user, router]);

  if (!ready || !user) {
    return null;
  }

  return <AppShell contextPanel={contextPanel}>{children}</AppShell>;
}
