"use client";

import React, { createContext, useContext, useEffect, useState, useCallback } from "react";

interface User {
  id: number;
  email: string;
  business_name: string | null;
  square_connected: boolean;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, businessName?: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

const API = "http://localhost:8000";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Restore session from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem("auth");
    if (stored) {
      try {
        const data = JSON.parse(stored);
        setToken(data.token);
        setRefreshToken(data.refreshToken);
        setUser(data.user);
      } catch {}
    }
    setLoading(false);
  }, []);

  const persist = (t: string, rt: string, u: User) => {
    setToken(t);
    setRefreshToken(rt);
    setUser(u);
    localStorage.setItem("auth", JSON.stringify({ token: t, refreshToken: rt, user: u }));
  };

  const login = async (email: string, password: string) => {
    const res = await fetch(`${API}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Login failed" }));
      throw new Error(err.detail || "Login failed");
    }
    const data = await res.json();
    persist(data.access_token, data.refresh_token, data.user);
  };

  const register = async (email: string, password: string, businessName?: string) => {
    const res = await fetch(`${API}/api/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, business_name: businessName || null }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Registration failed" }));
      throw new Error(err.detail || "Registration failed");
    }
    const data = await res.json();
    persist(data.access_token, data.refresh_token, data.user);

    // Auto-seed demo data for new users
    await fetch(`${API}/api/auth/seed-demo`, {
      method: "POST",
      headers: { Authorization: `Bearer ${data.access_token}` },
    });
  };

  const logout = () => {
    setToken(null);
    setRefreshToken(null);
    setUser(null);
    localStorage.removeItem("auth");
  };

  const refreshUser = useCallback(async () => {
    if (!token) return;
    const res = await fetch(`${API}/api/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.ok) {
      const data = await res.json();
      setUser(data);
      const stored = localStorage.getItem("auth");
      if (stored) {
        const parsed = JSON.parse(stored);
        parsed.user = data;
        localStorage.setItem("auth", JSON.stringify(parsed));
      }
    }
  }, [token]);

  return (
    <AuthContext.Provider value={{ user, token, loading, login, register, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
