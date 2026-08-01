"use client";

import Link from "next/link";
import { Activity, ArrowUpRight, Target, WalletCards } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  EmptyState,
  ErrorState,
  LoadingSkeleton,
  PageHeader,
} from "@/components/ui/states";
import { api, type Execution, type ScanReport, type Wallet } from "@/lib/api";
import { useFetch } from "@/lib/use-fetch";
import { formatApy, formatAmount, shortAddress } from "@/lib/utils";

const statusTone: Record<
  string,
  "neutral" | "accent" | "success" | "warning" | "danger" | "info"
> = {
  pending: "warning",
  approved: "info",
  submitted: "accent",
  completed: "success",
  failed: "danger",
  rejected: "neutral",
  cancelled: "neutral",
};

function StatCard({
  label,
  value,
  hint,
  icon: Icon,
  href,
}: {
  label: string;
  value: string;
  hint: string;
  icon: React.ComponentType<{ className?: string }>;
  href: string;
}) {
  return (
    <Link href={href} className="group block">
      <Card className="h-full transition-colors group-hover:border-accent/40">
        <CardContent className="p-5">
          <div className="flex items-center justify-between">
            <span className="text-[13px] font-medium text-muted-foreground">{label}</span>
            <span className="flex h-8 w-8 items-center justify-center rounded-[10px] bg-accent-soft text-accent">
              <Icon className="h-4 w-4" aria-hidden />
            </span>
          </div>
          <p className="mt-2 text-[28px] font-semibold tracking-tight">{value}</p>
          <p className="mt-0.5 flex items-center gap-1 text-xs text-subtle-foreground">
            {hint}
            <ArrowUpRight className="h-3 w-3 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" aria-hidden />
          </p>
        </CardContent>
      </Card>
    </Link>
  );
}

export default function OverviewPage() {
  const wallets = useFetch<Wallet[]>(() => api.listWallets(), []);
  const scan = useFetch<ScanReport>(() => api.scan(), []);
  const executions = useFetch<Execution[]>(() => api.listExecutions(), []);

  const loading = wallets.loading || scan.loading || executions.loading;
  const error = wallets.error || scan.error || executions.error;

  if (loading) {
    return (
      <div className="mx-auto max-w-6xl px-6 py-8">
        <PageHeader title="Overview" />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={index} className="h-32 animate-pulse rounded-[20px] bg-surface-muted" />
          ))}
        </div>
        <div className="mt-6">
          <LoadingSkeleton rows={4} />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-6xl px-6 py-8">
        <PageHeader title="Overview" />
        <ErrorState message={error} onRetry={wallets.reload} />
      </div>
    );
  }

  const activeWallets = (wallets.data ?? []).filter((w) => w.status === "active");
  const report = scan.data;
  const recent = (executions.data ?? []).slice(0, 5);

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <PageHeader
        title="Overview"
        description="A live snapshot of your portfolio, the agent's latest analysis, and recent activity."
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Active wallets"
          value={String(activeWallets.length)}
          hint="Connected to KeeperHub"
          icon={WalletCards}
          href="/wallets"
        />
        <StatCard
          label="Actionable moves"
          value={String(report?.allowed_count ?? 0)}
          hint="Allowed by your policy"
          icon={Target}
          href="/opportunities"
        />
        <StatCard
          label="Executions"
          value={String(recent.length)}
          hint="All time"
          icon={Activity}
          href="/executions"
        />
        <StatCard
          label="Best APY gain"
          value={
            report?.recommendations.some((r) => r.allowed)
              ? `+${report.recommendations[0].delta_apy.toFixed(2)}pp`
              : "—"
          }
          hint="Top allowed move"
          icon={ArrowUpRight}
          href="/opportunities"
        />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Agent briefing */}
        <Card className="lg:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Latest analysis</CardTitle>
            <Link
              href="/opportunities?scan=1"
              className="text-sm font-medium text-accent hover:underline"
            >
              View opportunities
            </Link>
          </CardHeader>
          <CardContent>
            {report ? (
              <>
                <p className="rounded-[14px] bg-surface-muted p-4 text-sm leading-7 text-muted-foreground">
                  {report.summary}
                </p>
                <div className="mt-4 space-y-2.5">
                  {report.recommendations.slice(0, 3).map((rec, index) => (
                    <div
                      key={`${rec.wallet_address}:${rec.current_protocol}:${rec.opportunity.protocol}`}
                      className="flex items-center gap-3 rounded-[14px] border border-border p-3"
                    >
                      <span className="text-sm font-semibold text-subtle-foreground">
                        {index + 1}
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium">
                          {rec.asset} · {formatAmount(rec.amount)} on{" "}
                          <span className="capitalize">{rec.current_protocol.replace(/-/g, " ")}</span>
                        </p>
                        <p className="truncate text-xs text-muted-foreground">
                          {shortAddress(rec.wallet_address)} · chain {rec.chain}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-semibold text-accent">
                          +{rec.delta_apy.toFixed(2)}pp
                        </p>
                        <p className="text-xs text-subtle-foreground">
                          {formatApy(rec.current_apy)} → {formatApy(rec.opportunity.apy)}
                        </p>
                      </div>
                      <Badge tone={rec.allowed ? "success" : "neutral"}>
                        {rec.allowed ? "Allowed" : "Blocked"}
                      </Badge>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <EmptyState
                title="Nothing analyzed yet"
                description="Run a scan to see how your positions compare against available yield."
                action={
                  <Link
                    href="/opportunities?scan=1"
                    className="inline-flex h-9 items-center gap-2 rounded-lg bg-accent px-3.5 text-sm font-medium text-accent-foreground hover:bg-accent-hover"
                  >
                    <Target className="h-4 w-4" aria-hidden />
                    Run scan
                  </Link>
                }
              />
            )}
          </CardContent>
        </Card>

        {/* Recent executions */}
        <Card>
          <CardHeader>
            <CardTitle>Recent executions</CardTitle>
          </CardHeader>
          <CardContent>
            {recent.length === 0 ? (
              <EmptyState
                title="No executions yet"
                description="Draft a move from the chat or opportunities and approve it here."
              />
            ) : (
              <div className="space-y-2.5">
                {recent.map((execution) => (
                  <Link
                    key={execution.id}
                    href="/executions"
                    className="flex items-center gap-3 rounded-[14px] border border-border p-3 transition-colors hover:border-accent/40"
                  >
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px] bg-surface-muted text-subtle-foreground">
                      <Activity className="h-3.5 w-3.5" aria-hidden />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">
                        {execution.asset ?? "Execution"}
                      </p>
                      <p className="truncate text-xs text-muted-foreground">
                        {execution.source_protocol?.replace(/-/g, " ")} →{" "}
                        {execution.target_protocol?.replace(/-/g, " ")}
                      </p>
                    </div>
                    <Badge tone={statusTone[execution.status] ?? "neutral"}>
                      {execution.status}
                    </Badge>
                  </Link>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
