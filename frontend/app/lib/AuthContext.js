"use client";
import { createContext, useContext, useState, useEffect, useCallback } from "react";

const AuthContext = createContext(null);

const API_BASE = "/api";

// Token storage keys
const ACCESS_TOKEN_KEY = "ts_access_token";
const REFRESH_TOKEN_KEY = "ts_refresh_token";
const USER_KEY = "ts_user";

function getStoredToken(key) {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function setStoredToken(key, value) {
  if (typeof window === "undefined") return;
  try {
    if (value) localStorage.setItem(key, value);
    else localStorage.removeItem(key);
  } catch {
    // Storage unavailable
  }
}

// Cookie cho edge middleware (flag lightweight, không chứa secret)
function setAuthCookie(value) {
  if (typeof document === "undefined") return;
  if (value) {
    document.cookie = "ts_auth=1; path=/; max-age=604800; SameSite=Lax";
  } else {
    document.cookie = "ts_auth=; path=/; max-age=0";
  }
}

function getStoredUser() {
  const raw = getStoredToken(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [accessToken, setAccessToken] = useState(null);
  const [refreshToken, setRefreshToken] = useState(null);
  const [loading, setLoading] = useState(true);

  // Initialize from localStorage on mount
  useEffect(() => {
    const storedAccess = getStoredToken(ACCESS_TOKEN_KEY);
    const storedRefresh = getStoredToken(REFRESH_TOKEN_KEY);
    const storedUser = getStoredUser();

    if (storedAccess && storedUser) {
      setAccessToken(storedAccess);
      setRefreshToken(storedRefresh);
      setUser(storedUser);
      setAuthCookie(true);
    }
    setLoading(false);

    // Listen for token refresh events from api.js
    function handleTokenRefresh(e) {
      const { access_token, refresh_token } = e.detail || {};
      if (access_token) setAccessToken(access_token);
      if (refresh_token) setRefreshToken(refresh_token);
      // Re-read user from localStorage in case it was updated
      const freshUser = getStoredUser();
      if (freshUser) setUser(freshUser);
    }
    window.addEventListener("ts:tokens-refreshed", handleTokenRefresh);
    return () => window.removeEventListener("ts:tokens-refreshed", handleTokenRefresh);
  }, []);

  const saveTokens = useCallback((data) => {
    const { access_token, refresh_token, user: userData } = data;
    setAccessToken(access_token);
    setRefreshToken(refresh_token);
    setUser(userData);
    setStoredToken(ACCESS_TOKEN_KEY, access_token);
    setStoredToken(REFRESH_TOKEN_KEY, refresh_token);
    setStoredToken(USER_KEY, JSON.stringify(userData));
    setAuthCookie(true);
  }, []);

  const clearTokens = useCallback(() => {
    setAccessToken(null);
    setRefreshToken(null);
    setUser(null);
    setStoredToken(ACCESS_TOKEN_KEY, null);
    setStoredToken(REFRESH_TOKEN_KEY, null);
    setStoredToken(USER_KEY, null);
    setAuthCookie(false);
  }, []);

  // Register with email/password
  const register = useCallback(async (email, password, displayName) => {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email,
        password,
        display_name: displayName || null,
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Đăng ký thất bại");
    }
    saveTokens(data);
    return data.user;
  }, [saveTokens]);

  // Login with email/password
  const login = useCallback(async (email, password) => {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Đăng nhập thất bại");
    }
    saveTokens(data);
    return data.user;
  }, [saveTokens]);

  // Logout
  const logout = useCallback(async () => {
    try {
      if (accessToken) {
        await fetch(`${API_BASE}/auth/logout`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${accessToken}`,
          },
          body: refreshToken ? JSON.stringify({ refresh_token: refreshToken }) : undefined,
        });
      }
    } catch {
      // Ignore logout errors
    }
    clearTokens();
  }, [accessToken, refreshToken, clearTokens]);

  // Refresh access token
  const refreshAccessToken = useCallback(async () => {
    if (!refreshToken) {
      clearTokens();
      return null;
    }
    try {
      const res = await fetch(`${API_BASE}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      if (!res.ok) {
        clearTokens();
        return null;
      }
      const data = await res.json();
      saveTokens(data);
      return data.access_token;
    } catch {
      clearTokens();
      return null;
    }
  }, [refreshToken, saveTokens, clearTokens]);

  // OAuth: redirect to provider
  const loginWithGoogle = useCallback(() => {
    window.location.href = `${API_BASE}/auth/google`;
  }, []);

  const loginWithGithub = useCallback(() => {
    window.location.href = `${API_BASE}/auth/github`;
  }, []);

  // Handle OAuth callback (called from /auth/callback page)
  const handleOAuthCallback = useCallback((params) => {
    const access_token = params.get("access_token");
    const refresh_token = params.get("refresh_token");
    const expires_in = params.get("expires_in");

    if (access_token && refresh_token) {
      // Decode user info from JWT payload (without verification — server already verified)
      try {
        const payload = JSON.parse(atob(access_token.split(".")[1]));
        const userData = {
          id: payload.sub,
          email: payload.email,
        };
        saveTokens({
          access_token,
          refresh_token,
          expires_in: parseInt(expires_in) || 1800,
          user: userData,
        });
        return true;
      } catch {
        // Failed to decode — still save tokens, fetch /me later
        saveTokens({
          access_token,
          refresh_token,
          expires_in: parseInt(expires_in) || 1800,
          user: { id: "", email: "" },
        });
        return true;
      }
    }
    return false;
  }, [saveTokens]);

  const value = {
    user,
    accessToken,
    refreshToken,
    loading,
    isAuthenticated: !!user && !!accessToken,
    register,
    login,
    logout,
    refreshAccessToken,
    loginWithGoogle,
    loginWithGithub,
    handleOAuthCallback,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
