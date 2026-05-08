"""
Worker Fetcher — Gọi Cloudflare Worker để lấy video links từ TikTok hashtag.

Cloudflare Worker chạy trên CDN IP (không bị TikTok block như datacenter).
Free tier: 100,000 requests/ngày.

Setup:
1. Deploy scripts/cloudflare-worker.js lên Cloudflare Workers (miễn phí)
2. Set env var CF_WORKER_URL = https://your-worker.workers.dev
"""
import os
import sys
import requests

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))


def fetch_via_worker(tag: str, max_videos: int = 90) -> list[str]:
    """
    Lấy video links từ TikTok hashtag qua Cloudflare Worker.

    Args:
        tag: Tên hashtag (không có #)
        max_videos: Số video tối đa

    Returns:
        list[str]: Danh sách video URLs
    """
    worker_url = os.environ.get("CF_WORKER_URL", "").strip().rstrip("/")
    if not worker_url:
        print("  [!] CF_WORKER_URL chưa set. Deploy Cloudflare Worker và set env var.")
        print("      Xem: scripts/cloudflare-worker.js")
        return []

    try:
        resp = requests.get(
            f"{worker_url}/",
            params={"tag": tag, "count": max_videos},
            timeout=30,
        )

        if resp.status_code != 200:
            print(f"  [!] Worker error: HTTP {resp.status_code}: {resp.text[:200]}")
            return []

        data = resp.json()
        videos = data.get("videos", [])

        if videos:
            print(f"  [✓] Worker: Tìm thấy {len(videos)} video cho #{tag}")
        else:
            print(f"  [!] Worker: 0 video cho #{tag} (có thể bị block hoặc tag không tồn tại)")

        return videos

    except requests.RequestException as e:
        print(f"  [!] Worker request failed: {type(e).__name__}: {str(e)[:200]}")
        return []
    except Exception as e:
        print(f"  [!] Worker error: {type(e).__name__}: {str(e)[:200]}")
        return []
