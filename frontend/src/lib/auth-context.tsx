"use client";

import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react";

interface User {
  id: number;
  username: string;
  email: string | null;
  name: string;
  role: string;
  is_active: boolean;
}

interface AuthContextType {
  user: User | null;
  accessToken: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshAccessToken: () => Promise<string | null>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refreshAccessToken = useCallback(async (): Promise<string | null> => {
    try {
      const res = await fetch("/api/auth/refresh", {
        method: "POST",
        credentials: "include",
      });
      if (!res.ok) return null;
      const data = await res.json();
      setAccessToken(data.access_token);
      return data.access_token;
    } catch {
      return null;
    }
  }, []);

  const fetchMe = useCallback(async (token: string): Promise<User | null> => {
    try {
      const res = await fetch("/api/auth/me", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) return null;
      return await res.json();
    } catch {
      return null;
    }
  }, []);

  // 초기 로드: refresh_token으로 access_token 복구
  useEffect(() => {
    (async () => {
      const token = await refreshAccessToken();
      if (token) {
        const me = await fetchMe(token);
        setUser(me);
      }
      setIsLoading(false);
    })();
  }, [refreshAccessToken, fetchMe]);

  const refreshUser = useCallback(async () => {
    if (accessToken) {
      const me = await fetchMe(accessToken);
      if (me) setUser(me);
    }
  }, [accessToken, fetchMe]);

  const login = async (username: string, password: string) => {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
      credentials: "include",
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || "로그인에 실패했습니다.");
    }
    const data = await res.json();
    setAccessToken(data.access_token);
    const me = await fetchMe(data.access_token);
    setUser(me);
  };

  const logout = async () => {
    try {
      await fetch("/api/auth/logout", {
        method: "POST",
        headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
        credentials: "include",
      });
    } catch {
      // ignore
    }
    setUser(null);
    setAccessToken(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        accessToken,
        isLoading,
        isAuthenticated: !!user,
        login,
        logout,
        refreshAccessToken,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
