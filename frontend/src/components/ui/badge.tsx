import * as React from "react";

import { cn } from "@/lib/utils";

type BadgeTone = "neutral" | "accent" | "success" | "warning" | "danger" | "info";

const toneClasses: Record<BadgeTone, string> = {
  neutral: "bg-surface-muted text-muted-foreground border border-border",
  accent: "bg-accent-soft text-accent border border-accent/20",
  success: "bg-success-soft text-success border border-success/20",
  warning: "bg-warning-soft text-warning border border-warning/20",
  danger: "bg-danger-soft text-danger border border-danger/20",
  info: "bg-info-soft text-info border border-info/20",
};

export function Badge({
  tone = "neutral",
  className,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { tone?: BadgeTone }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium",
        toneClasses[tone],
        className,
      )}
      {...props}
    />
  );
}

export function Dot({ className }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={cn("inline-block h-1.5 w-1.5 rounded-full bg-current", className)}
    />
  );
}
