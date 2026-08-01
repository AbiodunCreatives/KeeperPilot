"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useSyncExternalStore,
} from "react";

import { api, type User } from "@/lib/api";

interface AuthState {
  user: User | null;
  token: string | null;
  ready: boolean;
  login: (email: string) => Promise<User>;
  logout: () => void;
}

const TOKEN_KEY = "keeperpilot_token";
const USER_KEY = "keeperpilot_user";

const AuthContext = createContext<AuthState>({
  user: null,
  token: null,
  ready: false,
  login: async () => {
    throw new Error("AuthProvider not mounted");
  },
  logout: () => {},
});

interface StoredAuth {
  token: string | null;
  user: User | null;
}

const emptyAuth: StoredAuth = { token: null, user: null };

let cachedAuth: StoredAuth | null = null;
const authListeners = new Set<() => void>();

function readStorage(): StoredAuth {
  if (typeof window === "undefined") return emptyAuth;
  const token = window.localStorage.getItem(TOKEN_KEY);
  if (!token) return emptyAuth;
  let user: User | null = null;
  const raw = window.localStorage.getItem(USER_KEY);
  if (raw) {
    try {
      user = JSON.parse(raw) as User;
    } catch {
      user = null;
    }
  }
  return { token, user };
}

function getAuthSnapshot(): StoredAuth {
  if (!cachedAuth) cachedAuth = readStorage();
  return cachedAuth;
}

function subscribeAuth(listener: () => void) {
  authListeners.add(listener);
  return () => {
    authListeners.delete(listener);
  };
}

function commitAuth(next: StoredAuth) {
  cachedAuth = next;
  authListeners.forEach((listener) => listener());
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const snapshot = useSyncExternalStore(subscribeAuth, getAuthSnapshot, () => emptyAuth);
  const { user, token } = snapshot;

  const login = useCallback(async (email: string) => {
    const response = await api.register(email);
    window.localStorage.setItem(TOKEN_KEY, response.access_token);
    window.localStorage.setItem(USER_KEY, JSON.stringify(response.user));
    commitAuth({ token: response.access_token, user: response.user });
    return response.user;
  }, []);

  const logout = useCallback(() => {
    window.localStorage.removeItem(TOKEN_KEY);
    window.localStorage.removeItem(USER_KEY);
    commitAuth(emptyAuth);
  }, []);

  const value = useMemo(
    () => ({ user, token, ready: true, login, logout }),
    [user, token, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  return useContext(AuthContext);
}
