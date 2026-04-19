/**
 * TrendSense API Client
 * Centralizes all fetch calls to the FastAPI backend.
 */

// Relative path — Next.js proxies /api/* → http://localhost:8000/api/* via next.config.mjs rewrites.
// This avoids all CORS and cross-origin issues regardless of IPv4/IPv6.
const API_BASE = "/api";

async function fetcher(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });
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

export async function analyzeVideo(url) {
  return fetcher("/analyze", {
    method: "POST",
    body: JSON.stringify({ url }),
  });
}

export async function checkAnalysis(videoId) {
  return fetcher(`/analyze/${videoId}`);
}
