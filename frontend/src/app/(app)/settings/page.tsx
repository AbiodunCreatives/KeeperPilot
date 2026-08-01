"use client";

import { useRouter } from "next/navigation";
import { LogOut } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/states";
import { useAuth } from "@/lib/auth";

export default function SettingsPage() {
  const { user, logout } = useAuth();
  const router = useRouter();

  return (
    <div className="mx-auto max-w-3xl px-6 py-8">
      <PageHeader title="Settings" description="Your account and preferences." />

      <div className="space-y-5">
        <Card>
          <CardHeader>
            <CardTitle>Account</CardTitle>
            <CardDescription>How you&apos;re signed in.</CardDescription>
          </CardHeader>
          <CardContent className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <span className="flex h-11 w-11 items-center justify-center rounded-full bg-surface-strong text-sm font-semibold uppercase">
                {user?.email?.[0] ?? "K"}
              </span>
              <div>
                <p className="text-sm font-semibold">{user?.email}</p>
                <p className="text-xs text-muted-foreground">
                  Member since{" "}
                  {user?.created_at
                    ? new Date(user.created_at).toLocaleDateString()
                    : "—"}
                </p>
              </div>
            </div>
            <Button variant="secondary" size="sm">
              Manage profile
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Danger zone</CardTitle>
            <CardDescription>Sign out of this device.</CardDescription>
          </CardHeader>
          <CardContent className="flex items-center justify-between gap-4">
            <p className="text-[13px] leading-5 text-muted-foreground">
              You&apos;ll need your email to sign back in.
            </p>
            <Button
              variant="danger"
              onClick={() => {
                logout();
                router.push("/login");
              }}
            >
              <LogOut className="h-4 w-4" aria-hidden />
              Sign out
            </Button>
          </CardContent>
        </Card>

        <p className="text-xs leading-5 text-subtle-foreground">
          KeeperPilot executes fund movements through KeeperHub. Wallets are never
          controlled directly by this app — you sign every ownership proof.
        </p>
      </div>
    </div>
  );
}
