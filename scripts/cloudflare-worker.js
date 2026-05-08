/**
 * Cloudflare Worker — TikTok Hashtag Video Fetcher
 *
 * Deploy miễn phí: https://dash.cloudflare.com → Workers → Create
 * Free tier: 100,000 requests/ngày, không cần credit card
 *
 * Usage: GET https://your-worker.workers.dev/?tag=xuhuong&count=50
 * Response: { "tag": "xuhuong", "count": 10, "videos": [...] }
 */

export default {
  async fetch(request, env, ctx) {
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    };

    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    const url = new URL(request.url);
    const tag = url.searchParams.get('tag');
    const count = Math.min(parseInt(url.searchParams.get('count') || '50', 10), 200);

    if (!tag) {
      return jsonResponse({ error: 'Missing ?tag= parameter' }, 400, corsHeaders);
    }

    // Cache key — cache kết quả 5 phút để giảm load
    const cacheKey = `https://cache.tiktok/${tag}/${count}`;
    const cache = caches.default;
    const cached = await cache.match(cacheKey);
    if (cached) return cached;

    try {
      const videos = await fetchTikTokHashtag(tag, count);
      const response = jsonResponse({ tag, count: videos.length, videos }, 200, corsHeaders);

      // Cache 5 phút
      ctx.waitUntil(cache.put(cacheKey, response.clone()));
      return response;
    } catch (err) {
      return jsonResponse({ error: err.message }, 500, corsHeaders);
    }
  },
};

function jsonResponse(data, status, corsHeaders) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...corsHeaders, 'Content-Type': 'application/json' },
  });
}

async function fetchTikTokHashtag(tag, maxCount) {
  const hashtagUrl = `https://www.tiktok.com/tag/${encodeURIComponent(tag)}`;
  const html = await fetchPage(hashtagUrl);
  return extractVideoLinks(html, maxCount);
}

async function fetchPage(url) {
  const response = await fetch(url, {
    headers: {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
      'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8',
      'Accept-Encoding': 'gzip, deflate, br',
      'Sec-Fetch-Dest': 'document',
      'Sec-Fetch-Mode': 'navigate',
      'Sec-Fetch-Site': 'none',
      'Sec-Fetch-User': '?1',
      'Cache-Control': 'no-cache',
    },
    redirect: 'follow',
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }

  return await response.text();
}

function extractVideoLinks(html, maxCount) {
  const videos = new Set();

  // Pattern 1: href="/@username/video/1234567890"
  const pattern1 = /href="(\/@[\w.-]+\/video\/\d+)"/g;
  let match;
  while ((match = pattern1.exec(html)) !== null) {
    videos.add(`https://www.tiktok.com${match[1]}`);
    if (videos.size >= maxCount) break;
  }

  // Pattern 2: Full URLs trong HTML/JSON
  if (videos.size < maxCount) {
    const pattern2 = /https?:\/\/(?:www\.)?tiktok\.com\/@[\w.-]+\/video\/\d+/g;
    while ((match = pattern2.exec(html)) !== null) {
      videos.add(match[0].split('?')[0]);
      if (videos.size >= maxCount) break;
    }
  }

  // Pattern 3: Parse __UNIVERSAL_DATA_FOR_REHYDRATION__ JSON (depth-limited)
  if (videos.size < maxCount) {
    try {
      const rehydrationMatch = html.match(
        /<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>([\s\S]*?)<\/script>/
      );
      if (rehydrationMatch) {
        const data = JSON.parse(rehydrationMatch[1]);
        traverseForVideos(data, videos, maxCount, 0, 10); // max depth = 10
      }
    } catch (e) {
      // JSON parse failed, continue with regex results
    }
  }

  return [...videos].slice(0, maxCount);
}

function traverseForVideos(obj, videos, maxCount, depth, maxDepth) {
  if (!obj || typeof obj !== 'object' || depth > maxDepth || videos.size >= maxCount) return;

  if (Array.isArray(obj)) {
    for (const item of obj) {
      traverseForVideos(item, videos, maxCount, depth + 1, maxDepth);
      if (videos.size >= maxCount) return;
    }
    return;
  }

  // Tìm video items có id + author
  if (obj.id && obj.author?.uniqueId) {
    videos.add(`https://www.tiktok.com/@${obj.author.uniqueId}/video/${obj.id}`);
    if (videos.size >= maxCount) return;
  }

  for (const key of Object.keys(obj)) {
    if (typeof obj[key] === 'object') {
      traverseForVideos(obj[key], videos, maxCount, depth + 1, maxDepth);
      if (videos.size >= maxCount) return;
    }
  }
}
