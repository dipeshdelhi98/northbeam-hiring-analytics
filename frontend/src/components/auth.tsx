"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, getToken, setToken, type Me } from "@/lib/api";

interface AuthState {
  me: Me | null;
  ready: boolean; // false until we know whether a stored session is valid
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [ready, setReady] = useState(false);

  const loadMe = useCallback(async () => {
    if (!getToken()) {
      setMe(null);
      setReady(true);
      return;
    }
    try {
      setMe(await api<Me>("/api/me"));
    } catch {
      setMe(null);
    } finally {
      setReady(true);
    }
  }, []);

  useEffect(() => {
    loadMe();
    const onOut = () => setMe(null);
    window.addEventListener("nb:signed-out", onOut);
    return () => window.removeEventListener("nb:signed-out", onOut);
  }, [loadMe]);

  const signIn = useCallback(
    async (email: string, password: string) => {
      const { access_token } = await api<{ access_token: string }>("/api/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      setToken(access_token);
      await loadMe();
    },
    [loadMe],
  );

  const signOut = useCallback(() => {
    setToken(null);
    setMe(null);
  }, []);

  return <AuthContext.Provider value={{ me, ready, signIn, signOut }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth outside AuthProvider");
  return ctx;
}
