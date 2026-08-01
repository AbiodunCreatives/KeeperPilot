"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowRight, RefreshCw, Search, ShieldCheck, ShieldX } from "lucide-react";
import { useCallback, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  EmptyState,
  ErrorState,
  LoadingSkeleton,
  PageHeader,
} from "@/components/ui/states";
import { api, type Recommendation, type ScanReport } from "@/lib/api";
import { useFetch } from "@/lib/use-fetch";
import { formatApy, formatAmount, shortAddress } from "@/lib/utils";

function policyCheckBadges(rec: Recommendation) {
  const failed = rec.checks.filter((check) => !check.passed);
  return failed.map((check) => ({
    rule: check.rule,
    detail: check.detail,
  }));
}

export default function OpportunitiesPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const query = searchParams.get("q") ?? "";
  const autoScan = searchParams.get("scan") === "1";

  const scan = useFetch<ScanReport>(() => api.scan(), [autoScan]);
  const [creating, setCreating] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const recommendations = useMemo(() => {
    if (!scan.data) return [];
    const needle = query.trim().toLowerCase();
    if (!needle) return scan.data.recommendations;
    return scan.data.recommendations.filter((rec) =>
      [rec.asset, rec.current_protocol, rec.opportunity.protocol, rec.chain]
        .join(" ")
        .toLowerCase()
        .includes(needle),
    );
  }, [scan.data, query]);

  const execute = useCallback(
    async (rec: Recommendation) => {
      setActionError(null);
      setCreating(rec.opportunity.protocol);
      try {
        const wallets = await api.listWallets();
        const wallet = wallets.find((w) => w.address === rec.wallet_address);
        if (!wallet) {
          setActionError(
            `Wallet ${shortAddress(rec.wallet_address)} isn't registered — connect it on the Wallets page.`,
          );
          return;
        }
        await api.createExecution(
          wallet.id,
          rec.asset,
          rec.current_protocol,
          rec.opportunity.protocol,
        );
        router.push("/executions");
      } catch (exc) {
        setActionError(exc instanceof Error ? exc.message : "Could not draft execution");
      } finally {
        setCreating(null);
      }
    },
    [router],
  );

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <PageHeader
        title="Opportunities"
        description="Every candidate move the agent evaluated, ranked by APY gain and gated by your policy."
        action={
          <div className="flex items-center gap-2">
            {actionError && (
              <p className="max-w-xs text-xs text-danger">{actionError}</p>
            )}
            <Button variant="secondary" onClick={scan.reload} isLoading={scan.loading}>
              <RefreshCw className="h-4 w-4" aria-hidden />
              Rescan
            </Button>
          </div>
        }
      />

      {/* Policy summary strip */}
      {scan.data && (
        <div className="mb-5 flex flex-wrap items-center gap-3">
          <Badge tone="success">
            <ShieldCheck className="h-3 w-3" aria-hidden />
            {scan.data.allowed_count} allowed
          </Badge>
          <Badge tone="neutral">
            <ShieldX className="h-3 w-3" aria-hidden />
            {scan.data.blocked_count} blocked
          </Badge>
          <span className="text-xs text-subtle-foreground">
            Scanned {scan.data.scanned_at ? new Date(scan.data.scanned_at).toLocaleString() : ""}
          </span>
        </div>
      )}

      {/* Search filter */}
      <div className="relative mb-5 max-w-md">
        <Search
          className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-subtle-foreground"
          aria-hidden
        />
        <input
          value={query}
          onChange={(event) => {
            const value = event.target.value.trim();
            const params = new URLSearchParams(searchParams.toString());
            if (value) params.set("q", value);
            else params.delete("q");
            router.replace(`/opportunities?${params.toString()}`);
          }}
          placeholder="Filter by asset or protocol…"
          aria-label="Filter opportunities"
          className="h-10 w-full rounded-full border border-border bg-surface pl-10 pr-4 text-sm text-foreground placeholder:text-subtle-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background"
        />
      </div>

      {scan.loading && <LoadingSkeleton rows={6} />}
      {scan.error && <ErrorState message={scan.error} onRetry={scan.reload} />}

      {scan.data && (
        <>
          {recommendations.length === 0 ? (
            <EmptyState
              title={query ? "No matches" : "No opportunities evaluated"}
              description={
                query
                  ? `Nothing matches “${query}”. Try a different asset or protocol.`
                  : "Connect a wallet with a position, then run a scan."
              }
            />
          ) : (
            <div className="space-y-3">
              {recommendations.map((rec) => {
                const blockedBy = policyCheckBadges(rec);
                return (
                  <Card key={`${rec.wallet_address}:${rec.current_protocol}:${rec.opportunity.protocol}`}>
                    <CardContent className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center">
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-[15px] font-semibold">
                            {formatAmount(rec.amount)} {rec.asset}
                          </span>
                          <span className="text-sm text-subtle-foreground">
                            {shortAddress(rec.wallet_address)}
                          </span>
                          <Badge tone={rec.allowed ? "success" : "neutral"}>
                            {rec.allowed ? "Allowed" : "Blocked"}
                          </Badge>
                        </div>
                        <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[13px] text-muted-foreground">
                          <span className="capitalize">{rec.current_protocol.replace(/-/g, " ")}</span>
                          <ArrowRight className="h-3.5 w-3.5 text-subtle-foreground" aria-hidden />
                          <span className="font-medium text-accent">
                            <span className="capitalize">{rec.opportunity.protocol.replace(/-/g, " ")}</span>
                          </span>
                          <span className="text-subtle-foreground">
                            · {formatApy(rec.current_apy)} → {formatApy(rec.opportunity.apy)}
                          </span>
                        </div>
                        {blockedBy.length > 0 && (
                          <div className="mt-2 flex flex-wrap gap-1.5">
                            {blockedBy.map((rule) => (
                              <span
                                key={rule.rule}
                                className="rounded-full bg-danger-soft px-2 py-0.5 text-[11px] font-medium text-danger"
                              >
                                {rule.rule}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>

                      <div className="flex items-center gap-4 sm:flex-col sm:items-end sm:gap-2">
                        <div className="text-right">
                          <p className="text-lg font-semibold tracking-tight text-accent">
                            +{rec.delta_apy.toFixed(2)}pp
                          </p>
                          <p className="text-[11px] text-subtle-foreground">
                            est. gas ${rec.opportunity.estimated_gas.toFixed(2)}
                          </p>
                        </div>
                        {rec.allowed ? (
                          <Button
                            size="sm"
                            isLoading={creating === rec.opportunity.protocol}
                            onClick={() => void execute(rec)}
                          >
                            Draft move
                          </Button>
                        ) : (
                          <Button size="sm" variant="secondary" disabled>
                            Policy blocks
                          </Button>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </>
      )}

      {!scan.data && !scan.loading && !scan.error && (
        <EmptyState
          title="Run a scan to get started"
          description="Evaluate every position against the market and your policy."
          action={
            <Link
              href="/opportunities?scan=1"
              className="inline-flex h-9 items-center rounded-lg bg-accent px-3.5 text-sm font-medium text-accent-foreground hover:bg-accent-hover"
            >
              Scan now
            </Link>
          }
        />
      )}
    </div>
  );
}
