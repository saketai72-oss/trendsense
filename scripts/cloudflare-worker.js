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
    const debug = url.searchParams.get('debug') === '1';

    if (!tag) {
      return jsonResponse({ error: 'Missing ?tag= parameter' }, 400, corsHeaders);
    }

    // Debug mode: trả về chi tiết để inspect
    if (debug) {
      try {
        const cookies = await fetchCookies();
        const hashtagUrl = `https://www.tiktok.com/tag/${encodeURIComponent(tag)}`;
        const html = await fetchPage(hashtagUrl, cookies);
        const videoCount = (html.match(/\/video\/\d+/g) || []).length;

        // Thử API
        let apiResult = 'not tried';
        try {
          const apiVideos = await fetchFromAPI(tag, 10, cookies);
          apiResult = `${apiVideos.length} videos found`;
        } catch (e) {
          apiResult = `error: ${e.message}`;
        }

        return jsonResponse({
          tag,
          html_length: html.length,
          video_links_in_html: videoCount,
          api_result: apiResult,
          cookies_found: Object.keys(cookies),
          title: (html.match(/<title>(.*?)<\/title>/) || [])[1] || 'none',
          has_rehydration: html.includes('__UNIVERSAL_DATA_FOR_REHYDRATION__'),
          has_sigi_state: html.includes('SIGI_STATE'),
        }, 200, corsHeaders);
      } catch (e) {
        return jsonResponse({ error: e.message }, 500, corsHeaders);
      }
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
  const videos = new Set();

  // Bước 1: Visit TikTok homepage để lấy cookies (msToken, ttwid)
  const cookies = await fetchCookies();

  // Bước 2: Gọi TikTok internal API với cookies
  const apiVideos = await fetchFromAPI(tag, maxCount, cookies);
  for (const url of apiVideos) {
    videos.add(url);
    if (videos.size >= maxCount) break;
  }

  // Bước 3: Fallback — parse HTML nếu API fail
  if (videos.size === 0) {
    try {
      const hashtagUrl = `https://www.tiktok.com/tag/${encodeURIComponent(tag)}`;
      const html = await fetchPage(hashtagUrl, cookies);
      const links = extractVideoLinks(html, maxCount);
      for (const link of links) {
        videos.add(link);
        if (videos.size >= maxCount) break;
      }
    } catch (e) {
      // HTML fallback failed
    }
  }

  return [...videos].slice(0, maxCount);
}

const BROWSER_HEADERS = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
  'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
  'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8',
  'Accept-Encoding': 'gzip, deflate, br',
  'Sec-CH-UA': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
  'Sec-CH-UA-Mobile': '?0',
  'Sec-CH-UA-Platform': '"Windows"',
  'Sec-Fetch-Dest': 'document',
  'Sec-Fetch-Mode': 'navigate',
  'Sec-Fetch-Site': 'none',
  'Sec-Fetch-User': '?1',
  'Upgrade-Insecure-Requests': '1',
  'Cache-Control': 'max-age=0',
};

async function fetchCookies() {
  const cookieMap = {};
  try {
    const resp = await fetch('https://www.tiktok.com/', {
      headers: BROWSER_HEADERS,
      redirect: 'follow',
    });
    const setCookies = resp.headers.getSetCookie?.() || [];
    for (const sc of setCookies) {
      const [pair] = sc.split(';');
      const eqIdx = pair.indexOf('=');
      if (eqIdx > 0) {
        cookieMap[pair.slice(0, eqIdx).trim()] = pair.slice(eqIdx + 1).trim();
      }
    }
  } catch (e) {
    // Cookie fetch failed
  }
  return cookieMap;
}

async function fetchFromAPI(tag, maxCount, cookies) {
  const videos = [];

  // TikTok web API — cần msToken và ttwid
  const cookieStr = Object.entries(cookies)
    .map(([k, v]) => `${k}=${v}`)
    .join('; ');

  const params = new URLSearchParams({
    aid: '1988',
    app_name: 'tiktok_web',
    device_platform: 'web',
    region: 'VN',
    priority_region: '',
    os: 'windows',
    browser: 'Chrome',
    browser_version: '131',
    browser_language: 'en',
    screen_width: '1920',
    screen_height: '1080',
    cpu_core_num: '8',
    device_memory: '8',
    platform: 'PC',
    downlink: '10',
    effective_type: '4g',
    round_trip_time: '50',
    msToken: cookies.msToken || '',
  });

  // Thử nhiều API endpoints
  const endpoints = [
    `https://www.tiktok.com/api/challenge/item_list/?${params.toString()}&challengeID=${tag}&count=${Math.min(maxCount, 30)}&cursor=0`,
    `https://www.tiktok.com/api/search/general/full/?${params.toString()}&keyword=${tag}&count=${Math.min(maxCount, 30)}&cursor=0&search_id=0`,
  ];

  for (const apiUrl of endpoints) {
    try {
      const resp = await fetch(apiUrl, {
        headers: {
          ...BROWSER_HEADERS,
          'Accept': 'application/json, text/plain, */*',
          'Referer': `https://www.tiktok.com/tag/${tag}`,
          'Origin': 'https://www.tiktok.com',
          'Cookie': cookieStr,
        },
        redirect: 'follow',
      });

      if (!resp.ok) continue;

      const data = await resp.json();

      // Parse itemList từ response
      const items = data.itemList || data.data || [];
      for (const item of items) {
        const author = item.author?.uniqueId || item.author?.unique_id;
        const id = item.id || item.video_id;
        if (author && id) {
          videos.push(`https://www.tiktok.com/@${author}/video/${id}`);
          if (videos.length >= maxCount) return videos;
        }
      }

      // Parse từ search results
      if (data.data) {
        for (const result of data.data) {
          const item = result.item || result;
          const author = item.author?.uniqueId || item.author?.unique_id;
          const id = item.id || item.video_id;
          if (author && id) {
            videos.push(`https://www.tiktok.com/@${author}/video/${id}`);
            if (videos.length >= maxCount) return videos;
          }
        }
      }

      if (videos.length > 0) return videos;
    } catch (e) {
      continue;
    }
  }

  return videos;
}

async function fetchPage(url, cookies = {}) {
  const cookieStr = Object.entries(cookies).map(([k, v]) => `${k}=${v}`).join('; ');

  const response = await fetch(url, {
    headers: {
      ...BROWSER_HEADERS,
      ...(cookieStr ? { 'Cookie': cookieStr } : {}),
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
