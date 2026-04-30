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

export async function getUploadUrl(filename, contentType = "video/mp4") {
  return fetcher("/upload-url", {
    method: "POST",
    body: JSON.stringify({ filename, content_type: contentType }),
  });
}

export async function analyzeVideo(videoId, storagePath, caption = "") {
  // Call Backend directly via proxy
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

