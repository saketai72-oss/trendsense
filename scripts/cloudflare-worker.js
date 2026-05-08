/**
 * Cloudflare Worker — TikTok Hashtag Video Fetcher
 * 
 * Deploy miễn phí tại: https://dash.cloudflare.com → Workers → Create
 * Free tier: 100,000 requests/ngày, không cần credit card
 * 
 * Usage: GET https://your-worker.workers.dev/?tag=xuhuong&count=50
 * 
 * Response: { "videos": ["https://tiktok.com/@user/video/123", ...] }
 */

export default {
  async fetch(request, env, ctx) {
    // CORS headers
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
    const count = parseInt(url.searchParams.get('count') || '50', 10);

    if (!tag) {
      return new Response(
        JSON.stringify({ error: 'Missing ?tag= parameter' }),
        { status: 400, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }

    try {
      const videos = await fetchTikTokHashtag(tag, count);
      return new Response(
        JSON.stringify({ tag, count: videos.length, videos }),
        { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    } catch (err) {
      return new Response(
        JSON.stringify({ error: err.message }),
        { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }
  },
};

async function fetchTikTokHashtag(tag, maxCount) {
  const videos = new Set();
  const hashtagUrl = `https://www.tiktok.com/tag/${encodeURIComponent(tag)}`;

  // Strategy 1: Fetch HTML page và parse video links
  try {
    const html = await fetchPage(hashtagUrl);
    const links = extractVideoLinks(html);
    for (const link of links) {
      videos.add(link);
      if (videos.size >= maxCount) break;
    }
  } catch (e) {
    // Strategy 2: Thử TikTok internal API
    try {
      const apiLinks = await fetchViaAPI(tag, maxCount);
      for (const link of apiLinks) {
        videos.add(link);
        if (videos.size >= maxCount) break;
      }
    } catch (e2) {
      // Both strategies failed
    }
  }

  return [...videos].slice(0, maxCount);
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

function extractVideoLinks(html) {
  const videos = [];

  // Pattern 1: href="/@username/video/1234567890"
  const pattern1 = /href="(\/@[\w.-]+\/video\/\d+)"/g;
  let match;
  while ((match = pattern1.exec(html)) !== null) {
    videos.push(`https://www.tiktok.com${match[1]}`);
  }

  // Pattern 2: Full URLs in JSON data
  const pattern2 = /https?:\/\/(?:www\.)?tiktok\.com\/@[\w.-]+\/video\/\d+/g;
  while ((match = pattern2.exec(html)) !== null) {
    videos.push(match[0].split('?')[0]);
  }

  // Pattern 3: Extract from __UNIVERSAL_DATA_FOR_REHYDRATION__ JSON
  try {
    const rehydrationMatch = html.match(/<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>([\s\S]*?)<\/script>/);
    if (rehydrationMatch) {
      const data = JSON.parse(rehydrationMatch[1]);
      // Navigate the JSON structure to find video items
      const traverse = (obj) => {
        if (!obj || typeof obj !== 'object') return;
        if (Array.isArray(obj)) {
          obj.forEach(item => traverse(item));
          return;
        }
        // Look for video items with id and author
        if (obj.id && obj.author && obj.author.uniqueId) {
          const url = `https://www.tiktok.com/@${obj.author.uniqueId}/video/${obj.id}`;
          videos.push(url);
        }
        if (obj.video_id && obj.author_unique_id) {
          const url = `https://www.tiktok.com/@${obj.author_unique_id}/video/${obj.video_id}`;
          videos.push(url);
        }
        // Recurse into child objects
        for (const key of Object.keys(obj)) {
          if (typeof obj[key] === 'object') {
            traverse(obj[key]);
          }
        }
      };
      traverse(data);
    }
  } catch (e) {
    // JSON parse failed, continue with regex results
  }

  // Deduplicate
  return [...new Set(videos)];
}

async function fetchViaAPI(tag, count) {
  // TikTok's internal challenge/hashtag API
  const apiUrl = `https://www.tiktok.com/api/challenge/item_list/?aid=1988&challengeID=${tag}&count=${count}&cursor=0`;

  const response = await fetch(apiUrl, {
    headers: {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
      'Accept': 'application/json',
      'Referer': `https://www.tiktok.com/tag/${tag}`,
    },
  });

  if (!response.ok) {
    throw new Error(`API HTTP ${response.status}`);
  }

  const data = await response.json();
  const videos = [];

  if (data.itemList) {
    for (const item of data.itemList) {
      if (item.author && item.author.uniqueId && item.id) {
        videos.push(`https://www.tiktok.com/@${item.author.uniqueId}/video/${item.id}`);
      }
    }
  }

  return videos;
}
