"use client";

import Link from "next/link";
import { Check, ExternalLink, RefreshCw, X, Ban } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  EmptyState,
  ErrorState,
  LoadingSkeleton,
  PageHeader,
} from "@/components/ui/states";
import { api, type Execution, type ExecutionStatus } from "@/lib/api";
import { useFetch } from "@/lib/use-fetch";
import { formatAmount, shortAddress } from "@/lib/utils";

const statusTone: Record<
  ExecutionStatus,
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

function executionLabel(execution: Execution): string {
  if (execution.asset) {
    return `${formatAmount(execution.amount ?? execution.asset)} ${execution.asset}`;
  }
  return execution.action;
}

export default function ExecutionsPage() {
  const executions = useFetch<Execution[]>(() => api.listExecutions(), []);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  async function act(action: "approve" | "reject" | "cancel" | "refresh", id: string) {
    setActionError(null);
    setBusyId(id);
    try {
      if (action === "approve") await api.approveExecution(id);
      if (action === "reject") await api.rejectExecution(id);
      if (action === "cancel") await api.cancelExecution(id);
      if (action === "refresh") await api.refreshExecution(id);
      executions.reload();
    } catch (exc) {
      setActionError(exc instanceof Error ? exc.message : "Action failed");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <PageHeader
        title="Executions"
        description="Every move the agent has drafted or run. Nothing moves without your explicit approval."
      />

      {actionError && (
        <p className="mb-4 rounded-[12px] bg-danger-soft px-4 py-2.5 text-[13px] text-danger">
          {actionError}
        </p>
      )}

      {executions.loading && <LoadingSkeleton rows={6} />}
      {executions.error && <ErrorState message={executions.error} onRetry={executions.reload} />}

      {executions.data && (
        <>
          {executions.data.length === 0 ? (
            <EmptyState
              title="No executions yet"
              description="Draft a move from the chat or the opportunities page, then approve it here."
              action={
                <Link
                  href="/opportunities?scan=1"
                  className="inline-flex h-9 items-center rounded-lg bg-accent px-3.5 text-sm font-medium text-accent-foreground hover:bg-accent-hover"
                >
                  Find opportunities
                </Link>
              }
            />
          ) : (
            <Card>
              <CardContent className="p-2 sm:p-3">
                {executions.data.map((execution) => {
                  const showApprove = execution.status === "pending";
                  const showReject = execution.status === "pending";
                  const showCancel = execution.status === "pending" || execution.status === "approved";
                  const showRefresh = execution.status === "submitted";
                  const busy = busyId === execution.id;
                  return (
                    <div
                      key={execution.id}
                      className="flex flex-col gap-3 rounded-[14px] px-4 py-4 transition-colors hover:bg-surface-muted/60 sm:flex-row sm:items-center"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-sm font-semibold">
                            {executionLabel(execution)}
                          </span>
                          <Badge tone={statusTone[execution.status] ?? "neutral"}>
                            {execution.status}
                          </Badge>
                        </div>
                        <p className="mt-0.5 text-xs text-muted-foreground">
                          {execution.source_protocol?.replace(/-/g, " ")} →{" "}
                          {execution.target_protocol?.replace(/-/g, " ") ?? execution.action}
                          {" · "}
                          {new Date(execution.created_at).toLocaleString()}
                        </p>
                        {execution.transaction_hash && (
                          <p className="mt-1 flex items-center gap-1.5 font-mono text-[11px] text-subtle-foreground">
                            {shortAddress(execution.transaction_hash, 8)}
                            <a
                              href="https://sepolia.etherscan.io"
                              target="_blank"
                              rel="noopener noreferrer"
                              aria-label="View on explorer"
                              className="text-accent hover:underline"
                            >
                              <ExternalLink className="h-3 w-3" aria-hidden />
                            </a>
                          </p>
                        )}
                        {execution.reason && (
                          <p className="mt-1 text-xs text-danger">{execution.reason}</p>
                        )}
                      </div>

                      <div className="flex flex-wrap items-center gap-1.5">
                        {showRefresh && (
                          <Button size="sm" variant="outline" isLoading={busy} onClick={() => void act("refresh", execution.id)}>
                            <RefreshCw className="h-3.5 w-3.5" aria-hidden />
                            Refresh
                          </Button>
                        )}
                        {showApprove && (
                          <Button size="sm" isLoading={busy} onClick={() => void act("approve", execution.id)}>
                            <Check className="h-3.5 w-3.5" aria-hidden />
                            Approve
                          </Button>
                        )}
                        {showReject && (
                          <Button size="sm" variant="secondary" isLoading={busy} onClick={() => void act("reject", execution.id)}>
                            <X className="h-3.5 w-3.5" aria-hidden />
                            Reject
                          </Button>
                        )}
                        {showCancel && (
                          <Button size="sm" variant="ghost" isLoading={busy} onClick={() => void act("cancel", execution.id)}>
                            <Ban className="h-3.5 w-3.5" aria-hidden />
                            Cancel
                          </Button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
