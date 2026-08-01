"use client";

import Link from "next/link";
import { RefreshCw } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  EmptyState,
  ErrorState,
  LoadingSkeleton,
  PageHeader,
} from "@/components/ui/states";
import { api, type ScanReport } from "@/lib/api";
import { useFetch } from "@/lib/use-fetch";
import { formatAmount, shortAddress } from "@/lib/utils";

interface PositionRow {
  key: string;
  wallet: string;
  chain: string;
  protocol: string;
  asset: string;
  amount: string;
  apy: number;
  bestTarget?: { protocol: string; apy: number; delta: number };
}

function buildPositions(report: ScanReport): PositionRow[] {
  const rows = new Map<string, PositionRow>();
  for (const rec of report.recommendations) {
    const key = `${rec.wallet_address}:${rec.current_protocol}:${rec.asset}`;
    const existing = rows.get(key);
    if (!existing) {
      rows.set(key, {
        key,
        wallet: rec.wallet_address,
        chain: rec.chain,
        protocol: rec.current_protocol,
        asset: rec.asset,
        amount: String(rec.amount),
        apy: rec.current_apy,
      });
    }
    const row = rows.get(key)!;
    if (
      rec.allowed &&
      (!row.bestTarget || rec.delta_apy > row.bestTarget.delta)
    ) {
      row.bestTarget = {
        protocol: rec.opportunity.protocol,
        apy: rec.opportunity.apy,
        delta: rec.delta_apy,
      };
    }
  }
  return Array.from(rows.values());
}

export default function PositionsPage() {
  const scan = useFetch<ScanReport>(() => api.scan(), []);

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <PageHeader
        title="Positions"
        description="Every yield position the agent can see across your wallets, with the best move it found for each."
        action={
          <Button variant="secondary" onClick={scan.reload} isLoading={scan.loading}>
            <RefreshCw className="h-4 w-4" aria-hidden />
            Refresh
          </Button>
        }
      />

      {scan.loading && <LoadingSkeleton rows={5} />}
      {scan.error && <ErrorState message={scan.error} onRetry={scan.reload} />}

      {scan.data && (
        <>
          {buildPositions(scan.data).length === 0 ? (
            <EmptyState
              title="No positions tracked"
              description="Connect a wallet with a yield position to see it here."
              action={
                <Link
                  href="/wallets"
                  className="inline-flex h-9 items-center rounded-lg bg-accent px-3.5 text-sm font-medium text-accent-foreground hover:bg-accent-hover"
                >
                  Connect a wallet
                </Link>
              }
            />
          ) : (
            <Card>
              <CardContent className="p-2 sm:p-3">
                <div className="hidden grid-cols-12 gap-4 px-4 py-2 text-[11px] font-semibold uppercase tracking-wider text-subtle-foreground lg:grid">
                  <span className="col-span-3">Position</span>
                  <span className="col-span-2">Wallet</span>
                  <span className="col-span-2">APY</span>
                  <span className="col-span-3">Best move</span>
                  <span className="col-span-2 text-right">Gain</span>
                </div>
                {buildPositions(scan.data).map((row) => (
                  <div
                    key={row.key}
                    className="grid grid-cols-2 items-center gap-3 rounded-[14px] px-4 py-3.5 transition-colors hover:bg-surface-muted/60 lg:grid-cols-12 lg:gap-4"
                  >
                    <div className="col-span-2 flex items-center gap-3 lg:col-span-3">
                      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[12px] bg-accent-soft text-sm font-bold text-accent">
                        {row.asset.slice(0, 2)}
                      </span>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold">
                          {formatAmount(row.amount)} {row.asset}
                        </p>
                        <p className="truncate text-xs text-muted-foreground">
                          <span className="capitalize">{row.protocol.replace(/-/g, " ")}</span>
                          {" · "}chain {row.chain}
                        </p>
                      </div>
                    </div>

                    <div className="hidden lg:col-span-2 lg:block">
                      <p className="truncate font-mono text-[13px]">{shortAddress(row.wallet)}</p>
                    </div>

                    <div className="hidden lg:col-span-2 lg:block">
                      <p className="text-sm font-semibold">{row.apy.toFixed(2)}%</p>
                    </div>

                    <div className="hidden lg:col-span-3 lg:block">
                      {row.bestTarget ? (
                        <Badge tone="accent" className="capitalize">
                          → {row.bestTarget.protocol.replace(/-/g, " ")}
                        </Badge>
                      ) : (
                        <span className="text-xs text-subtle-foreground">No allowed move</span>
                      )}
                    </div>

                    <div className="hidden text-right lg:col-span-2 lg:block">
                      {row.bestTarget ? (
                        <p className="text-sm font-semibold text-accent">
                          +{row.bestTarget.delta.toFixed(2)}pp
                        </p>
                      ) : (
                        <span className="text-xs text-subtle-foreground">—</span>
                      )}
                    </div>

                    {/* Mobile summary */}
                    <div className="col-span-2 flex items-center justify-between lg:hidden">
                      <span className="text-xs text-muted-foreground">{row.apy.toFixed(2)}% APY</span>
                      {row.bestTarget ? (
                        <Badge tone="accent" className="capitalize">
                          → {row.bestTarget.protocol.replace(/-/g, " ")}
                        </Badge>
                      ) : (
                        <span className="text-xs text-subtle-foreground">No move</span>
                      )}
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
