"use client";

import { Check, Copy, MoreHorizontal, RefreshCw, Pencil } from "lucide-react";
import { useState } from "react";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
  aiLabel?: string;
}

function renderRich(text: string) {
  return text.split("\n").map((line, lineIndex) => (
    <span key={lineIndex} className="block min-h-[1.5em]">
      {line.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((part, index) => {
        if (part.startsWith("**") && part.endsWith("**")) {
          return (
            <strong key={index} className="font-semibold text-foreground">
              {part.slice(2, -2)}
            </strong>
          );
        }
        if (part.startsWith("`") && part.endsWith("`")) {
          return (
            <code
              key={index}
              className="rounded-md bg-surface-muted px-1.5 py-0.5 font-mono text-[0.85em] text-accent"
            >
              {part.slice(1, -1)}
            </code>
          );
        }
        return <span key={index}>{part}</span>;
      })}
    </span>
  ));
}

function MessageActions({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      /* clipboard unavailable */
    }
  }

  return (
    <div className="mt-2 flex items-center gap-0.5" aria-label="Message actions">
      <button
        type="button"
        onClick={copy}
        aria-label="Copy"
        className="flex h-8 w-8 items-center justify-center rounded-[10px] text-subtle-foreground transition-colors hover:bg-surface-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        {copied ? (
          <Check className="h-3.5 w-3.5 text-success" aria-hidden />
        ) : (
          <Copy className="h-3.5 w-3.5" aria-hidden />
        )}
      </button>
      <button
        type="button"
        aria-label="Edit"
        className="flex h-8 w-8 items-center justify-center rounded-[10px] text-subtle-foreground transition-colors hover:bg-surface-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Pencil className="h-3.5 w-3.5" aria-hidden />
      </button>
      <button
        type="button"
        aria-label="Retry"
        className="flex h-8 w-8 items-center justify-center rounded-[10px] text-subtle-foreground transition-colors hover:bg-surface-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <RefreshCw className="h-3.5 w-3.5" aria-hidden />
      </button>
      <button
        type="button"
        aria-label="More"
        className="flex h-8 w-8 items-center justify-center rounded-[10px] text-subtle-foreground transition-colors hover:bg-surface-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <MoreHorizontal className="h-3.5 w-3.5" aria-hidden />
      </button>
    </div>
  );
}

export function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div
          className="animate-rise max-w-[75%] rounded-[20px] border border-border bg-surface-muted px-4 py-3 text-sm leading-6 text-foreground"
        >
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="animate-rise flex max-w-[75%] flex-col">
      <div className="rounded-[20px] border border-border bg-surface px-4 py-3 shadow-[0_1px_2px_rgba(0,0,0,0.03)]">
        {message.aiLabel && (
          <span className="mb-2 inline-flex items-center gap-1.5 rounded-full bg-accent-soft px-2 py-0.5 text-[11px] font-semibold text-accent">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" aria-hidden />
            {message.aiLabel}
          </span>
        )}
        <div className="text-sm leading-6 text-muted-foreground">
          {renderRich(message.content)}
        </div>
      </div>
      <MessageActions text={message.content} />
    </div>
  );
}

export function SkeletonBubble() {
  return (
    <div
      className="flex max-w-[75%] flex-col"
      aria-label="Agent is thinking"
      aria-busy
    >
      <div className="rounded-[20px] border border-border bg-surface px-4 py-3">
        <div className="flex items-center gap-1.5">
          {[0, 1, 2].map((dot) => (
            <span
              key={dot}
              className="h-2 w-2 animate-bounce rounded-full bg-accent/60 [animation-delay:120ms]"
              style={{ animationDelay: `${dot * 150}ms` }}
              aria-hidden
            />
          ))}
        </div>
      </div>
    </div>
  );
}
