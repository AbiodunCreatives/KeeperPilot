"use client";

import { ArrowUp, Globe, Mic, Paperclip } from "lucide-react";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function Composer({
  onSubmit,
  disabled,
}: {
  onSubmit: (prompt: string) => void;
  disabled?: boolean;
}) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  function submit() {
    const prompt = value.trim();
    if (!prompt || disabled) return;
    onSubmit(prompt);
    setValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }

  function resize() {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }

  return (
    <div
      className={cn(
        "rounded-[24px] border border-border-strong bg-surface p-2.5 shadow-[0_2px_12px_rgba(0,0,0,0.04)]",
        "focus-within:border-accent/50 focus-within:ring-2 focus-within:ring-accent-ring",
        "transition-colors",
      )}
    >
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(event) => {
          setValue(event.target.value);
          resize();
        }}
        onKeyDown={onKeyDown}
        rows={2}
        placeholder="Describe what you want to create, analyze, or automate…"
        aria-label="Message the agent"
        className="w-full resize-none bg-transparent px-2 py-2 text-[15px] leading-6 text-foreground placeholder:text-subtle-foreground focus:outline-none disabled:opacity-50"
      />

      <div className="flex items-center gap-1 pt-1">
        <button
          type="button"
          aria-label="Attach files"
          className="flex h-9 w-9 items-center justify-center rounded-[12px] text-subtle-foreground transition-colors hover:bg-surface-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Paperclip className="h-4 w-4" aria-hidden />
        </button>
        <button
          type="button"
          aria-label="Global search"
          className="flex h-9 w-9 items-center justify-center rounded-[12px] text-subtle-foreground transition-colors hover:bg-surface-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Globe className="h-4 w-4" aria-hidden />
        </button>
        <button
          type="button"
          aria-label="Voice input"
          className="flex h-9 w-9 items-center justify-center rounded-[12px] text-subtle-foreground transition-colors hover:bg-surface-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Mic className="h-4 w-4" aria-hidden />
        </button>

        <div className="ml-auto">
          <Button
            size="icon"
            onClick={submit}
            disabled={disabled || !value.trim()}
            aria-label="Send message"
            className="h-10 w-10 rounded-full shadow-[0_2px_8px_rgba(255,122,26,0.35)]"
          >
            <ArrowUp className="h-4.5 w-4.5" aria-hidden />
          </Button>
        </div>
      </div>
    </div>
  );
}
