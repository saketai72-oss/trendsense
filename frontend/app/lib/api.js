/**
 * TrendSense API Client
 * Centralizes all fetch calls to the FastAPI backend.
 * Attaches JWT access token to authenticated requests.
 */

// Relative path — Next.js proxies /api/* → http://localhost:8000/api/* via next.config.mjs rewrites.
const API_BASE = "/api";

function getStoredToken() {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem("ts_access_token");
  } catch {
    return null;
  }
}

function getStoredRefreshToken() {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem("ts_refresh_token");
  } catch {
    return null;
  }
}

function setStoredTokens(accessToken, refreshToken) {
  if (typeof window === "undefined") return;
  try {
    if (accessToken) localStorage.setItem("ts_access_token", accessToken);
    if (refreshToken) localStorage.setItem("ts_refresh_token", refreshToken);
    // Notify AuthContext to sync React state
    window.dispatchEvent(new CustomEvent("ts:tokens-refreshed", {
      detail: { access_token: accessToken, refresh_token: refreshToken },
    }));
  } catch {
    // Storage unavailable
  }
}

async function tryRefreshToken() {
  const refreshToken = getStoredRefreshToken();
  if (!refreshToken) return null;

  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    setStoredTokens(data.access_token, data.refresh_token);
    return data.access_token;
  } catch {
    return null;
  }
}

async function fetcher(path, options = {}, retryOn401 = true) {
  const headers = { ...options.headers };
  const token = getStoredToken();

  // Only set Content-Type for non-FormData requests
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  // Attach JWT token if available
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  // If 401 and we haven't retried yet, try refreshing the token
  if (res.status === 401 && retryOn401 && token) {
    const newToken = await tryRefreshToken();
    if (newToken) {
      headers["Authorization"] = `Bearer ${newToken}`;
      const retryRes = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers,
      });
      if (!retryRes.ok) {
        const err = await retryRes.json().catch(() => ({}));
        throw new Error(err.detail || `API error: ${retryRes.status}`);
      }
      return retryRes.json();
    }
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `API error: ${res.status}`);
  }
  return res.json();
}

export async function getVideos(params = {}) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") query.set(k, v);
  });
  return fetcher(`/videos?${query.toString()}`);
}

export async function getVideo(videoId) {
  return fetcher(`/videos/${videoId}`);
}

export async function getStats() {
  return fetcher("/stats");
}

export async function getCategories() {
  return fetcher("/categories");
}

export async function getSentiments() {
  return fetcher("/sentiments");
}

export async function getKeywords(limit = 30) {
  return fetcher(`/keywords?limit=${limit}`);
}

export async function getTimeline() {
  return fetcher("/timeline");
}

export async function getUploadUrl(filename, contentType = "video/mp4") {
  return fetcher("/upload-url", {
    method: "POST",
    body: JSON.stringify({ filename, content_type: contentType }),
  });
}

export async function analyzeVideo(videoId, storagePath, caption = "") {
  return fetcher("/analyze", {
    method: "POST",
    body: JSON.stringify({
      video_id: videoId,
      storage_path: storagePath,
      caption: caption,
    }),
  });
}

export async function checkAnalysis(videoId) {
  return fetcher(`/analyze/${videoId}`);
}

export async function getMyVideos(page = 1, perPage = 20) {
  return fetcher(`/my-videos?page=${page}&per_page=${perPage}`);
}

export async function getMyVideoDetail(videoId) {
  return fetcher(`/my-videos/${videoId}`);
}

export async function deleteMyVideo(videoId) {
  return fetcher(`/my-videos/${videoId}`, { method: "DELETE" });
}

// Auth API functions
export async function authLogin(email, password) {
  return fetcher("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function authRegister(email, password, displayName) {
  return fetcher("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, display_name: displayName }),
  });
}

export async function authLogout(refreshToken) {
  return fetcher("/auth/logout", {
    method: "POST",
    body: refreshToken ? JSON.stringify({ refresh_token: refreshToken }) : undefined,
  });
}

export async function authGetMe() {
  return fetcher("/auth/me");
}
