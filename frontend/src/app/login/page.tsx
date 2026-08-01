"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Landmark, Sparkles } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email);
      router.replace("/");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Could not sign in");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-full flex-col items-center justify-center px-6 py-16">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center text-center">
          <span className="flex h-14 w-14 items-center justify-center rounded-[18px] bg-accent text-accent-foreground shadow-[0_8px_30px_rgba(255,122,26,0.3)]">
            <Landmark className="h-6 w-6" aria-hidden />
          </span>
          <h1 className="mt-5 text-2xl font-semibold tracking-tight">KeeperPilot</h1>
          <p className="mt-1.5 max-w-xs text-sm leading-6 text-muted-foreground">
            Sign in to let your AI DeFi operator watch, analyze, and draft moves for
            your positions.
          </p>
        </div>

        <form onSubmit={submit} className="rounded-[24px] border border-border bg-surface p-6">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@example.com"
            className="mt-1"
          />
          {error && (
            <p className="mt-3 rounded-[12px] bg-danger-soft px-3 py-2 text-[13px] text-danger">
              {error}
            </p>
          )}
          <Button type="submit" isLoading={loading} className="mt-4 w-full" size="lg">
            Continue
          </Button>
          <p className="mt-3 text-center text-xs leading-5 text-subtle-foreground">
            No password needed — we create or sign you in with this email.
          </p>
        </form>

        <p className="mt-6 flex items-center justify-center gap-1.5 text-center text-xs text-subtle-foreground">
          <Sparkles className="h-3.5 w-3.5 text-accent" aria-hidden />
          Fund management executes through KeeperHub. Read the{" "}
          <Link
            href="/"
            className="font-medium text-muted-foreground underline decoration-border-strong underline-offset-2 hover:text-foreground"
          >
            docs
          </Link>
          .
        </p>
      </div>
    </main>
  );
}
