"use client";

import { Activity, Scale, Sparkles, Target, TrendingUp } from "lucide-react";

import { cn } from "@/lib/utils";

const suggestions = [
  {
    icon: Target,
    title: "Scan for yield",
    description: "Find the best venue for every position under your policy.",
    metadata: "Live · policy-aware",
    prompt: "Scan my positions for better yield",
  },
  {
    icon: TrendingUp,
    title: "Move to best yield",
    description: "Draft the top allowed migration for your approval.",
    metadata: "Human-in-the-loop",
    prompt: "Move my funds to the best opportunity",
  },
  {
    icon: Activity,
    title: "Review executions",
    description: "See what the agent has run and what needs approval.",
    metadata: "Live · audit trail",
    prompt: "Show my executions",
  },
  {
    icon: Scale,
    title: "Adjust my policy",
    description: "Tune risk tolerance, assets, and gas limits.",
    metadata: "You stay in control",
    prompt: "Show my current policy",
  },
];

export function SuggestionCard({
  suggestion,
  onPick,
  index,
}: {
  suggestion: (typeof suggestions)[number];
  onPick: (prompt: string) => void;
  index: number;
}) {
  const Icon = suggestion.icon;
  return (
    <button
      type="button"
      onClick={() => onPick(suggestion.prompt)}
      className={cn(
        "animate-pop group flex flex-col rounded-[20px] border border-border bg-surface p-5 text-left",
        "transition-all hover:-translate-y-0.5 hover:border-accent/40 hover:shadow-[0_8px_24px_rgba(0,0,0,0.05)]",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
      )}
      style={{ animationDelay: `${index * 60}ms` }}
    >
      <span className="flex h-10 w-10 items-center justify-center rounded-[14px] bg-accent-soft text-accent transition-transform group-hover:scale-105">
        <Icon className="h-4.5 w-4.5" aria-hidden />
      </span>
      <span className="mt-3 text-[15px] font-semibold tracking-tight">{suggestion.title}</span>
      <span className="mt-1 text-[13px] leading-5 text-muted-foreground">
        {suggestion.description}
      </span>
      <span className="mt-3 inline-flex w-fit items-center gap-1 rounded-full bg-surface-muted px-2 py-0.5 text-[11px] font-medium text-subtle-foreground">
        <Sparkles className="h-3 w-3" aria-hidden />
        {suggestion.metadata}
      </span>
    </button>
  );
}

export { suggestions };
