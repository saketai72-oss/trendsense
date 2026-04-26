/**
 * TrendSense API Client
 * Centralizes all fetch calls to the FastAPI backend.
 */

// Relative path — Next.js proxies /api/* → http://localhost:8000/api/* via next.config.mjs rewrites.
// This avoids all CORS and cross-origin issues regardless of IPv4/IPv6.
const API_BASE = "/api";

async function fetcher(path, options = {}) {
  const headers = { ...options.headers };

  // Only set Content-Type for non-FormData requests
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
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

export async function analyzeVideo(videoFile, caption = "") {
  const formData = new FormData();
  formData.append("video", videoFile);
  formData.append("caption", caption);

  // Bypass Next.js proxy (which has a 10MB body size limit) and call Backend directly
  const res = await fetch("http://127.0.0.1:8080/api/analyze", {
    method: "POST",
    body: formData,
  });
  
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `API error: ${res.status}`);
  }
  return res.json();
}

export async function checkAnalysis(videoId) {
  return fetcher(`/analyze/${videoId}`);
}

