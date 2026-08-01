"use client";

import {
  ArrowUpRight,
  Check,
  CheckCircle2,
  Circle,
  Clock3,
  ExternalLink,
  RotateCw,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type StepStatus = "done" | "active" | "pending" | "failed";

export interface AgentStep {
  id: string;
  title: string;
  description: string;
  output?: string;
  status: StepStatus;
}

export interface ResultCardData {
  title: string;
  subtitle: string;
  status: "completed" | "failed" | "submitted";
  metrics: { label: string; value: string }[];
  primaryAction?: { label: string; onClick: () => void };
  linkLabel?: string;
  linkHref?: string;
}

function StepIcon({ status }: { status: StepStatus }) {
  if (status === "done")
    return (
      <span className="flex h-7 w-7 items-center justify-center rounded-full bg-accent-soft text-accent">
        <Check className="h-3.5 w-3.5" aria-hidden />
      </span>
    );
  if (status === "active")
    return (
      <span className="flex h-7 w-7 items-center justify-center rounded-full bg-accent text-accent-foreground">
        <RotateCw className="h-3.5 w-3.5 animate-spin" aria-hidden />
      </span>
    );
  if (status === "failed")
    return (
      <span className="flex h-7 w-7 items-center justify-center rounded-full bg-danger-soft text-danger">
        <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
      </span>
    );
  return (
    <span className="flex h-7 w-7 items-center justify-center rounded-full border border-border bg-surface-muted text-subtle-foreground">
      <Circle className="h-2.5 w-2.5" aria-hidden />
    </span>
  );
}

export function ExecutionPanel({
  steps,
  result,
  running,
}: {
  steps: AgentStep[];
  result: ResultCardData | null;
  running: boolean;
}) {
  const doneCount = steps.filter((step) => step.status === "done").length;
  const total = steps.length;
  const percent = total === 0 ? 0 : Math.round((doneCount / total) * 100);

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="border-b border-border p-5">
        <div className="flex items-center justify-between">
          <h2 className="text-[15px] font-semibold tracking-tight">Execution steps</h2>
          {running && (
            <span className="flex items-center gap-1.5 text-xs font-medium text-accent">
              <Clock3 className="h-3.5 w-3.5" aria-hidden />
              Working…
            </span>
          )}
        </div>
        <div className="mt-4 flex items-center gap-3">
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-strong">
            <div
              className="h-full rounded-full bg-accent transition-[width] duration-500 ease-out"
              style={{ width: `${percent}%` }}
              role="progressbar"
              aria-valuenow={percent}
              aria-valuemin={0}
              aria-valuemax={100}
            />
          </div>
          <span className="text-xs font-medium text-muted-foreground">
            {doneCount}/{total} done
          </span>
        </div>
      </div>

      {/* Steps */}
      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
        {steps.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center">
            <span className="flex h-11 w-11 items-center justify-center rounded-[16px] border border-border bg-surface-muted text-subtle-foreground">
              <ArrowUpRight className="h-5 w-5" aria-hidden />
            </span>
            <p className="text-sm font-medium text-foreground">No execution yet</p>
            <p className="text-xs leading-5 text-muted-foreground">
              Ask the agent to scan your positions or move funds, and each step will
              appear here with its live status.
            </p>
          </div>
        ) : (
          steps.map((step) => (
            <div
              key={step.id}
              className={cn(
                "rounded-[16px] border p-[18px] transition-colors",
                step.status === "active"
                  ? "border-accent/40 bg-accent-soft/40"
                  : "border-border bg-surface",
              )}
            >
              <div className="flex items-start gap-3">
                <StepIcon status={step.status} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium leading-5">{step.title}</p>
                  <p className="mt-0.5 text-[13px] leading-5 text-muted-foreground">
                    {step.description}
                  </p>
                  {step.output ? (
                    <p className="mt-2 rounded-[10px] bg-surface-muted px-2.5 py-1.5 font-mono text-xs text-foreground">
                      {step.output}
                    </p>
                  ) : null}
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Result card */}
      {result ? (
        <div className="border-t border-border p-4">
          <div className="rounded-[16px] border border-border bg-surface-muted/60 p-4">
            <div className="flex items-center gap-2.5">
              <span
                className={cn(
                  "flex h-9 w-9 items-center justify-center rounded-full",
                  result.status === "completed"
                    ? "bg-success-soft text-success"
                    : result.status === "failed"
                      ? "bg-danger-soft text-danger"
                      : "bg-accent-soft text-accent",
                )}
              >
                <CheckCircle2 className="h-4 w-4" aria-hidden />
              </span>
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold">{result.title}</p>
                <p className="truncate text-xs text-muted-foreground">{result.subtitle}</p>
              </div>
              <div className="ml-auto">
                <Badge
                  tone={
                    result.status === "completed"
                      ? "success"
                      : result.status === "failed"
                        ? "danger"
                        : "accent"
                  }
                >
                  {result.status}
                </Badge>
              </div>
            </div>

            <div className="mt-3 grid grid-cols-2 gap-2">
              {result.metrics.map((metric) => (
                <div key={metric.label} className="rounded-[12px] bg-surface p-2.5">
                  <p className="text-[11px] text-subtle-foreground">{metric.label}</p>
                  <p className="mt-0.5 truncate text-[13px] font-semibold">{metric.value}</p>
                </div>
              ))}
            </div>

            <div className="mt-3 flex items-center gap-2">
              {result.primaryAction ? (
                <Button size="sm" className="flex-1" onClick={result.primaryAction.onClick}>
                  {result.primaryAction.label}
                </Button>
              ) : null}
              {result.linkHref ? (
                <a
                  href={result.linkHref}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex h-9 items-center gap-1.5 rounded-lg border border-border-strong bg-surface px-3 text-sm font-medium text-foreground transition-colors hover:border-accent hover:text-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <ExternalLink className="h-3.5 w-3.5" aria-hidden />
                  {result.linkLabel ?? "View"}
                </a>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
