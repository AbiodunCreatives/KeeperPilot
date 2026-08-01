"use client";

import { Check, Shield } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { ErrorState, LoadingSkeleton, PageHeader } from "@/components/ui/states";
import { api, type Preferences, type RiskLevel } from "@/lib/api";
import { useFetch } from "@/lib/use-fetch";

const riskOptions: { value: RiskLevel; label: string; hint: string }[] = [
  { value: "low", label: "Conservative", hint: "Stable venues, minimal risk of loss" },
  { value: "medium", label: "Balanced", hint: "Allow well-known yield protocols" },
  { value: "high", label: "Aggressive", hint: "Pursue high APY even in risky venues" },
];

function PolicyForm({
  initial,
  onSaved,
}: {
  initial: Preferences;
  onSaved: (updated: Preferences) => void;
}) {
  const [form, setForm] = useState<Preferences>(initial);
  const [assetsInput, setAssetsInput] = useState(initial.preferred_assets.join(", "));
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    setError(null);
    setSaving(true);
    setSaved(false);
    const assets = assetsInput
      .split(",")
      .map((asset) => asset.trim().toUpperCase())
      .filter(Boolean);
    try {
      const updated = await api.updatePreferences({
        risk_level: form.risk_level,
        preferred_assets: assets,
        minimum_yield_difference: form.minimum_yield_difference,
        maximum_gas_cost: form.maximum_gas_cost,
      });
      setForm(updated);
      setAssetsInput(updated.preferred_assets.join(", "));
      setSaved(true);
      onSaved(updated);
      setTimeout(() => setSaved(false), 2500);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Could not save policy");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-[10px] bg-accent-soft text-accent">
              <Shield className="h-4 w-4" aria-hidden />
            </span>
            <CardTitle>Risk tolerance</CardTitle>
          </div>
          <CardDescription>
            How adventurous the agent is allowed to be when picking venues.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {riskOptions.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => setForm({ ...form, risk_level: option.value })}
                className="rounded-[16px] border p-4 text-left transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                style={{
                  borderColor:
                    form.risk_level === option.value ? "var(--accent)" : "var(--border)",
                  background:
                    form.risk_level === option.value ? "var(--accent-soft)" : "var(--surface)",
                }}
                aria-pressed={form.risk_level === option.value}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold">{option.label}</span>
                  {form.risk_level === option.value && (
                    <Check className="h-4 w-4 text-accent" aria-hidden />
                  )}
                </div>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">{option.hint}</p>
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Asset preferences</CardTitle>
          <CardDescription>
            Restrict the agent to these assets (comma separated). Empty = any asset.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Input
            value={assetsInput}
            onChange={(event) => setAssetsInput(event.target.value)}
            placeholder="USDC, USDT, DAI"
            aria-label="Preferred assets"
            autoComplete="off"
          />
          <div className="mt-2 flex flex-wrap gap-1.5">
            {assetsInput
              .split(",")
              .map((asset) => asset.trim().toUpperCase())
              .filter(Boolean)
              .map((asset) => (
                <Badge key={asset} tone="accent">
                  {asset}
                </Badge>
              ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Yield & gas thresholds</CardTitle>
          <CardDescription>
            Minimum APY improvement and maximum gas cost for a move to be worth it.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <Label htmlFor="min-yield">Minimum APY gain (percentage points)</Label>
              <Input
                id="min-yield"
                type="number"
                min={0}
                max={100}
                step={0.1}
                value={form.minimum_yield_difference}
                onChange={(event) =>
                  setForm({ ...form, minimum_yield_difference: Number(event.target.value) })
                }
              />
            </div>
            <div>
              <Label htmlFor="max-gas">Maximum gas cost (USD)</Label>
              <Input
                id="max-gas"
                type="number"
                min={0}
                max={10000}
                step={0.1}
                value={form.maximum_gas_cost}
                onChange={(event) =>
                  setForm({ ...form, maximum_gas_cost: Number(event.target.value) })
                }
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {error && (
        <p className="rounded-[12px] bg-danger-soft px-4 py-2.5 text-[13px] text-danger">{error}</p>
      )}

      <div className="flex items-center justify-end gap-3">
        {saved && (
          <span className="flex items-center gap-1.5 text-sm font-medium text-success">
            <Check className="h-4 w-4" aria-hidden />
            Policy saved
          </span>
        )}
        <Button onClick={() => void save()} isLoading={saving}>
          Save policy
        </Button>
      </div>
    </div>
  );
}

export default function PoliciesPage() {
  const prefs = useFetch<Preferences>(() => api.getPreferences(), []);

  return (
    <div className="mx-auto max-w-3xl px-6 py-8">
      <PageHeader
        title="Policies"
        description="The rules the agent must satisfy before it drafts any move. You stay in control."
      />

      {prefs.loading && <LoadingSkeleton rows={4} />}
      {prefs.error && <ErrorState message={prefs.error} onRetry={prefs.reload} />}

      {prefs.data && (
        <PolicyForm
          key={prefs.data.updated_at ?? "default"}
          initial={prefs.data}
          onSaved={() => prefs.reload()}
        />
      )}
    </div>
  );
}
