"use client";

import { useCallback, useRef, useState } from "react";

import { Composer } from "@/components/chat/composer";
import { ExecutionPanel, type AgentStep, type ResultCardData } from "@/components/chat/execution-panel";
import {
  MessageBubble,
  SkeletonBubble,
  type ChatMessage,
} from "@/components/chat/message";
import { SuggestionCard, suggestions } from "@/components/chat/suggestion-cards";

import { runAgent } from "@/lib/agent";

const uid = () => Math.random().toString(36).slice(2, 10);

export function ChatWorkspace() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [thinking, setThinking] = useState(false);
  const [steps, setSteps] = useState<AgentStep[]>([]);
  const [result, setResult] = useState<ResultCardData | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const handleReply = useCallback(async (prompt: string) => {
    setThinking(true);
    setResult(null);

    // Run the agent while steps are revealed progressively.
    const replyPromise = runAgent(prompt);

    // Prime the panel with pending steps as soon as the intent resolves.
    const runningSteps: AgentStep[] = [];
    const finished = await replyPromise;
    runningSteps.push(...finished.steps);
    setSteps(runningSteps);
    setResult(finished.result);

    setMessages((previous) => [
      ...previous,
      {
        id: uid(),
        role: "user",
        content: prompt,
        timestamp: Date.now(),
      },
    ]);

    await new Promise((resolve) => setTimeout(resolve, 420));

    setMessages((previous) => [
      ...previous,
      {
        id: uid(),
        role: "assistant",
        content: finished.message,
        timestamp: Date.now(),
        aiLabel: "Agent analysis",
      },
    ]);
    setThinking(false);
  }, []);

  const submit = useCallback(
    (prompt: string) => {
      void handleReply(prompt);
    },
    [handleReply],
  );

  const empty = messages.length === 0;

  return (
    <div className="flex h-full">
      {/* Conversation column */}
      <div className="flex min-w-0 flex-1 flex-col">
        <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto">
          {empty ? (
            <div className="flex min-h-full flex-col items-center justify-center px-6 py-10">
              {/* Hero orb */}
              <div className="orb relative h-36 w-36 rounded-full">
                <span
                  className="absolute inset-2 rounded-full border border-accent/20 bg-surface/40"
                  aria-hidden
                />
                <span
                  className="absolute inset-0 flex items-center justify-center text-accent"
                  aria-hidden
                >
                  <span className="flex h-16 w-16 items-center justify-center rounded-full bg-surface shadow-[0_8px_30px_rgba(255,122,26,0.25)]">
                    <SparklesIcon />
                  </span>
                </span>
              </div>

              <h2 className="mt-8 text-center text-[42px] font-semibold leading-[1.1] tracking-tight sm:text-[48px]">
                Ask AI Agent
              </h2>
              <p className="mt-3 max-w-md text-center text-base leading-7 text-muted-foreground">
                Your AI assistant watches your positions, evaluates risk-adjusted yield,
                and drafts moves — within policies you define.
              </p>

              <div className="mt-8 w-full max-w-2xl">
                <Composer onSubmit={submit} />
              </div>

              <p className="mt-4 text-center text-xs text-subtle-foreground">
                The agent never moves funds without your approval.
              </p>

              <div className="mt-10 grid w-full max-w-3xl grid-cols-1 gap-4 sm:grid-cols-2">
                {suggestions.map((suggestion, index) => (
                  <SuggestionCard
                    key={suggestion.title}
                    suggestion={suggestion}
                    onPick={submit}
                    index={index}
                  />
                ))}
              </div>
            </div>
          ) : (
            <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-6 py-8">
              {messages.map((message) => (
                <MessageBubble key={message.id} message={message} />
              ))}
              {thinking && <SkeletonBubble />}
            </div>
          )}
        </div>

        {/* Composer pinned at the bottom of the conversation */}
        {!empty && (
          <div className="mx-auto w-full max-w-3xl px-6 pb-6">
            <Composer onSubmit={submit} disabled={thinking} />
          </div>
        )}
      </div>

      {/* Execution context panel */}
      <div className="hidden w-[320px] shrink-0 border-l border-border bg-surface lg:block">
        <ExecutionPanel steps={steps} result={result} running={thinking} />
      </div>
    </div>
  );
}

function SparklesIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3z"
        fill="currentColor"
      />
      <path
        d="M19 15l.9 2.4L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.6L19 15z"
        fill="currentColor"
        opacity="0.7"
      />
    </svg>
  );
}
