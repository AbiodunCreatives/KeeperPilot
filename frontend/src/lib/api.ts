"use client";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

export type RiskLevel = "low" | "medium" | "high";

export type WalletStatus = "active" | "revoked";

export type ExecutionStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "submitted"
  | "completed"
  | "failed"
  | "cancelled";

export interface User {
  id: string;
  email: string;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface Wallet {
  id: string;
  address: string;
  chain: string;
  status: WalletStatus;
  created_at: string;
}

export interface Challenge {
  challenge_id: string;
  address: string;
  chain: string;
  nonce: string;
  message: string;
  expires_at: string;
}

export interface Preferences {
  risk_level: RiskLevel;
  preferred_assets: string[];
  minimum_yield_difference: number;
  maximum_gas_cost: number;
  updated_at?: string | null;
}

export interface Opportunity {
  protocol: string;
  asset: string;
  chain: string;
  apy: number;
  risk_level: RiskLevel;
  estimated_gas: number;
}

export interface PolicyCheck {
  rule: string;
  passed: boolean;
  detail: string;
}

export interface Recommendation {
  wallet_address: string;
  chain: string;
  current_protocol: string;
  asset: string;
  amount: string;
  current_apy: number;
  opportunity: Opportunity;
  delta_apy: number;
  allowed: boolean;
  reasons: string[];
  checks: PolicyCheck[];
}

export interface ScanReport {
  scanned_at: string;
  recommendation_count: number;
  allowed_count: number;
  blocked_count: number;
  summary: string;
  recommendations: Recommendation[];
}

export interface Execution {
  id: string;
  wallet_id: string | null;
  action: string;
  status: ExecutionStatus;
  source_protocol: string | null;
  target_protocol: string | null;
  transaction_hash: string | null;
  gas_used: string | null;
  amount: string | null;
  asset: string | null;
  reason: string | null;
  created_at: string;
  completed_at: string | null;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export class ApiClient {
  constructor(
    private readonly baseUrl = API_URL,
    private readonly getToken: () => string | null = () =>
      typeof window !== "undefined"
        ? window.localStorage.getItem("keeperpilot_token")
        : null,
  ) {}

  private headers(extra?: Record<string, string>): Record<string, string> {
    const token = this.getToken();
    return {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...extra,
    };
  }

  private async request<T>(
    method: string,
    path: string,
    body?: unknown,
  ): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method,
      headers: this.headers(),
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
    });

    if (!response.ok) {
      let detail = `${response.status} ${response.statusText}`;
      try {
        const payload = (await response.json()) as { detail?: unknown };
        if (typeof payload.detail === "string") {
          detail = payload.detail;
        } else if (Array.isArray(payload.detail)) {
          detail = payload.detail
            .map((item) =>
              typeof item === "object" && item !== null && "msg" in item
                ? String((item as { msg: string }).msg)
                : String(item),
            )
            .join(", ");
        }
      } catch {
        /* non-JSON error body — keep the status text */
      }
      throw new ApiError(detail, response.status);
    }

    if (response.status === 204) {
      return undefined as T;
    }
    return (await response.json()) as T;
  }

  get<T>(path: string): Promise<T> {
    return this.request<T>("GET", path);
  }

  post<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>("POST", path, body);
  }

  put<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>("PUT", path, body);
  }

  // ---- auth ----
  register(email: string): Promise<TokenResponse> {
    return this.post<TokenResponse>("/api/auth/register", { email });
  }

  // ---- wallets ----
  listWallets(): Promise<Wallet[]> {
    return this.get<Wallet[]>("/api/wallets");
  }

  requestChallenge(address: string, chain: string): Promise<Challenge> {
    return this.post<Challenge>("/api/wallets/challenge", { address, chain });
  }

  connectWallet(
    challengeId: string,
    address: string,
    chain: string,
    signature: string,
  ): Promise<Wallet> {
    return this.post<Wallet>("/api/wallets/connect", {
      challenge_id: challengeId,
      address,
      chain,
      signature,
    });
  }

  revokeWallet(walletId: string): Promise<{ id: string; status: WalletStatus }> {
    return this.post(`/api/wallets/${walletId}/revoke`);
  }

  // ---- preferences / policy ----
  getPreferences(): Promise<Preferences> {
    return this.get<Preferences>("/api/preferences");
  }

  updatePreferences(
    patch: Partial<Preferences>,
  ): Promise<Preferences> {
    return this.put<Preferences>("/api/preferences", patch);
  }

  // ---- decisions ----
  scan(): Promise<ScanReport> {
    return this.get<ScanReport>("/api/decisions/scan");
  }

  // ---- executions ----
  listExecutions(): Promise<Execution[]> {
    return this.get<Execution[]>("/api/executions");
  }

  createExecution(
    walletId: string,
    asset: string,
    sourceProtocol: string,
    targetProtocol: string,
  ): Promise<Execution> {
    return this.post<Execution>("/api/executions", {
      wallet_id: walletId,
      asset,
      source_protocol: sourceProtocol,
      target_protocol: targetProtocol,
    });
  }

  approveExecution(id: string): Promise<Execution> {
    return this.post<Execution>(`/api/executions/${id}/approve`);
  }

  rejectExecution(id: string): Promise<Execution> {
    return this.post<Execution>(`/api/executions/${id}/reject`);
  }

  cancelExecution(id: string): Promise<Execution> {
    return this.post<Execution>(`/api/executions/${id}/cancel`);
  }

  refreshExecution(id: string): Promise<Execution> {
    return this.post<Execution>(`/api/executions/${id}/refresh`);
  }
}

export const api = new ApiClient();
