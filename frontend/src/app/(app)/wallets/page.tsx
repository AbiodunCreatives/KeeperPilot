"use client";

import { Plus, Trash2, WalletCards, X } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/input";
import {
  EmptyState,
  ErrorState,
  LoadingSkeleton,
  PageHeader,
} from "@/components/ui/states";
import { api, type Wallet } from "@/lib/api";
import { useFetch } from "@/lib/use-fetch";
import { cn, shortAddress } from "@/lib/utils";

const chains = [
  { value: "11155111", label: "Ethereum Sepolia" },
  { value: "84532", label: "Base Sepolia" },
];

declare global {
  interface Window {
    ethereum?: {
      request: (args: {
        method: string;
        params?: unknown[];
      }) => Promise<unknown>;
    };
  }
}

function ConnectModal({ onClose, onConnected }: { onClose: () => void; onConnected: () => void }) {
  const [address, setAddress] = useState("");
  const [chain, setChain] = useState("11155111");
  const [signature, setSignature] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [challengeId, setChallengeId] = useState<string | null>(null);
  const [step, setStep] = useState<"address" | "sign" | "verify">("address");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const hasInjectedWallet = typeof window !== "undefined" && "ethereum" in window;

  async function requestChallenge() {
    setError(null);
    setBusy(true);
    try {
      const challenge = await api.requestChallenge(address, chain);
      setChallengeId(challenge.challenge_id);
      setMessage(challenge.message);
      setStep("sign");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Could not request challenge");
    } finally {
      setBusy(false);
    }
  }

  async function signWithWallet() {
    if (!window.ethereum || !message) return;
    setError(null);
    setBusy(true);
    try {
      const accounts = (await window.ethereum.request({
        method: "eth_requestAccounts",
      })) as string[];
      if (!accounts.includes(address.toLowerCase())) {
        setError("The wallet you're signing from doesn't match the address entered.");
        setBusy(false);
        return;
      }
      let sig: string;
      try {
        sig = (await window.ethereum.request({
          method: "personal_sign",
          params: [message, address],
        })) as string;
      } catch {
        sig = (await window.ethereum.request({
          method: "personal_sign",
          params: [address, message],
        })) as string;
      }
      setSignature(sig);
      setStep("verify");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Signature request declined");
    } finally {
      setBusy(false);
    }
  }

  async function connect() {
    if (!challengeId) return;
    setError(null);
    setBusy(true);
    try {
      await api.connectWallet(challengeId, address, chain, signature);
      onConnected();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Could not verify signature");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 px-4"
      role="dialog"
      aria-modal="true"
      aria-label="Connect a wallet"
    >
      <div className="animate-pop w-full max-w-md rounded-[24px] border border-border bg-surface p-6 shadow-[0_24px_80px_rgba(0,0,0,0.2)]">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold tracking-tight">Connect a wallet</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="flex h-9 w-9 items-center justify-center rounded-[12px] text-subtle-foreground transition-colors hover:bg-surface-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>

        <div className="mt-4 flex items-center gap-2">
          {["address", "sign", "verify"].map((name, index) => (
            <span key={name} className="flex items-center gap-2 text-[11px] font-medium">
              <span
                className={cn(
                  "flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-semibold",
                  step === name
                    ? "bg-accent text-accent-foreground"
                    : index < ["address", "sign", "verify"].indexOf(step)
                      ? "bg-success text-white"
                      : "bg-surface-muted text-subtle-foreground",
                )}
              >
                {index + 1}
              </span>
              {name}
            </span>
          ))}
        </div>

        {step === "address" && (
          <div className="mt-5 space-y-4">
            <div>
              <Label htmlFor="wallet-address">Wallet address</Label>
              <Input
                id="wallet-address"
                value={address}
                onChange={(event) => setAddress(event.target.value)}
                placeholder="0x…"
                spellCheck={false}
                autoComplete="off"
                className="font-mono"
              />
            </div>
            <div>
              <Label htmlFor="wallet-chain">Chain</Label>
              <Select id="wallet-chain" value={chain} onChange={(event) => setChain(event.target.value)}>
                {chains.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label} ({option.value})
                  </option>
                ))}
              </Select>
            </div>
            <Button className="w-full" onClick={() => void requestChallenge()} isLoading={busy}>
              Request signature challenge
            </Button>
          </div>
        )}

        {step === "sign" && message && (
          <div className="mt-5 space-y-4">
            <p className="text-[13px] text-muted-foreground">
              Sign this message to prove you own{" "}
              <span className="font-mono text-foreground">{shortAddress(address)}</span>:
            </p>
            <pre className="max-h-32 overflow-y-auto rounded-[14px] bg-surface-muted p-3 font-mono text-[11px] leading-5 text-muted-foreground">
              {message}
            </pre>
            {hasInjectedWallet ? (
              <Button className="w-full" onClick={() => void signWithWallet()} isLoading={busy}>
                <WalletCards className="h-4 w-4" aria-hidden />
                Sign with wallet
              </Button>
            ) : (
              <div>
                <Label htmlFor="signature">Paste signature</Label>
                <Input
                  id="signature"
                  value={signature}
                  onChange={(event) => setSignature(event.target.value)}
                  placeholder="0x…"
                  spellCheck={false}
                  autoComplete="off"
                  className="font-mono"
                />
                <Button
                  className="mt-3 w-full"
                  disabled={signature.length < 10}
                  onClick={() => setStep("verify")}
                >
                  Continue
                </Button>
              </div>
            )}
          </div>
        )}

        {step === "verify" && (
          <div className="mt-5 space-y-4">
            <p className="text-[13px] text-muted-foreground">
              Verifying your signature to register{" "}
              <span className="font-mono text-foreground">{shortAddress(address)}</span>.
            </p>
            <Button className="w-full" onClick={() => void connect()} isLoading={busy}>
              Verify & connect
            </Button>
          </div>
        )}

        {error && (
          <p className="mt-4 rounded-[12px] bg-danger-soft px-3 py-2 text-[13px] text-danger">
            {error}
          </p>
        )}
      </div>
    </div>
  );
}

export default function WalletsPage() {
  const wallets = useFetch<Wallet[]>(() => api.listWallets(), []);
  const [showConnect, setShowConnect] = useState(false);
  const [revoking, setRevoking] = useState<string | null>(null);

  async function revoke(id: string) {
    setRevoking(id);
    try {
      await api.revokeWallet(id);
      wallets.reload();
    } finally {
      setRevoking(null);
    }
  }

  return (
    <div className="mx-auto max-w-4xl px-6 py-8">
      <PageHeader
        title="Wallets"
        description="Wallets the agent can move funds on behalf of. Signatures are verified on-chain."
        action={
          <Button onClick={() => setShowConnect(true)}>
            <Plus className="h-4 w-4" aria-hidden />
            Connect wallet
          </Button>
        }
      />

      {wallets.loading && <LoadingSkeleton rows={4} />}
      {wallets.error && <ErrorState message={wallets.error} onRetry={wallets.reload} />}

      {wallets.data && (
        <>
          {wallets.data.length === 0 ? (
            <EmptyState
              title="No wallets connected"
              description="Connect a wallet to let the agent scan and manage its yield positions."
              action={
                <Button onClick={() => setShowConnect(true)}>
                  <Plus className="h-4 w-4" aria-hidden />
                  Connect wallet
                </Button>
              }
            />
          ) : (
            <div className="space-y-3">
              {wallets.data.map((wallet) => (
                <Card key={wallet.id}>
                  <CardContent className="flex items-center gap-4 p-5">
                    <span className="flex h-10 w-10 items-center justify-center rounded-[14px] bg-accent-soft text-accent">
                      <WalletCards className="h-4.5 w-4.5" aria-hidden />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="flex items-center gap-2 font-mono text-sm font-semibold">
                        {shortAddress(wallet.address, 8)}
                        <Badge tone={wallet.status === "active" ? "success" : "neutral"}>
                          {wallet.status}
                        </Badge>
                      </p>
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        chain {wallet.chain} · added {new Date(wallet.created_at).toLocaleDateString()}
                      </p>
                    </div>
                    {wallet.status === "active" && (
                      <Button
                        size="sm"
                        variant="ghost"
                        isLoading={revoking === wallet.id}
                        onClick={() => void revoke(wallet.id)}
                      >
                        <Trash2 className="h-3.5 w-3.5" aria-hidden />
                        Revoke
                      </Button>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </>
      )}

      {showConnect && (
        <ConnectModal
          onClose={() => setShowConnect(false)}
          onConnected={() => {
            setShowConnect(false);
            wallets.reload();
          }}
        />
      )}
    </div>
  );
}
