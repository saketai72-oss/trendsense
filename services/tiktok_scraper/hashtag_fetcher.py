"""
Hashtag Fetcher — Thu thập video URLs từ TikTok hashtag bằng TikTokApi.

Tự động lấy ms_token từ Selenium cookies → HTTP auto-fetch → Env var.
TikTokApi dùng Playwright để tạo browser session hợp lệ với TikTok.
"""
import os
import sys
import asyncio
import subprocess

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from services.tiktok_scraper.token_fetcher import get_ms_token


def _ensure_playwright_browsers() -> bool:
    """Kiểm tra và cài đặt Playwright Chromium nếu chưa có."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        print("  [✓] Playwright Chromium khả dụng.")
        return True
    except Exception as e:
        print(f"  [!] Playwright Chromium lỗi: {type(e).__name__}: {str(e)[:200]}")
        print("  [!] Đang thử cài đặt...")
        try:
            subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                check=True, capture_output=True, timeout=120
            )
            subprocess.run(
                [sys.executable, "-m", "playwright", "install-deps", "chromium"],
                check=True, capture_output=True, timeout=120
            )
            print("  [✓] Đã cài Playwright Chromium.")
            return True
        except Exception as install_err:
            print(f"  [!] Không thể cài Playwright: {install_err}")
            return False


def fetch_via_tiktokapi(tag: str, max_videos: int = 90, driver=None, proxy: str = None) -> list[str]:
    """
    Dùng TikTokApi để lấy video từ hashtag.
    Cần ms_token (tự động lấy từ Selenium → HTTP fetch → env var).
    """
    try:
        from TikTokApi import TikTokApi
    except ImportError:
        print("  [!] TikTokApi chưa cài. Chạy: pip install TikTokApi")
        return []

    # Lấy ms_token tự động (Selenium → HTTP → env)
    ms_token = get_ms_token(driver=driver, proxy=proxy)
    if not ms_token:
        return []

    # Kiểm tra Playwright browsers trước khi chạy
    if not _ensure_playwright_browsers():
        print("  [!] Playwright browsers không khả dụng. Bỏ qua TikTokApi.")
        return []

    async def _fetch():
        video_data = []  # List of (url, stats_dict)
        try:
            async with TikTokApi() as api:
                create_kwargs = {
                    "ms_tokens": [ms_token],
                    "num_sessions": 1,
                    "sleep_after": 3,
                }
                if proxy:
                    create_kwargs["proxies"] = [proxy]

                await api.create_sessions(**create_kwargs)

                hashtag = api.hashtag(name=tag)
                async for video in hashtag.videos(count=max_videos):
                    data = video.as_dict
                    author_id = data.get("author", {}).get("uniqueId", "") or data.get("author", {}).get("unique_id", "")
                    video_id = data.get("id", "")
                    if video_id:
                        if author_id:
                            url = f"https://www.tiktok.com/@{author_id}/video/{video_id}"
                        else:
                            url = f"https://www.tiktok.com/@_/video/{video_id}"

                        # Lấy stats trực tiếp từ TikTokApi
                        stats = data.get("stats", {})
                        video_info = {
                            "caption": data.get("desc", ""),
                            "views": stats.get("playCount", 0),
                            "likes": stats.get("diggCount", 0),
                            "comments": stats.get("commentCount", 0),
                            "shares": stats.get("shareCount", 0),
                            "saves": stats.get("collectCount", 0),
                            "create_time": data.get("createTime", 0),
                            "author": author_id,
                        }
                        video_data.append((url, video_info))

        except Exception as e:
            err_name = type(e).__name__
            err_msg = str(e)[:300]
            if err_name == "EmptyResponseException":
                print(f"  [!] TikTokApi: {err_name} — TikTok trả về rỗng.")
                print(f"      Nguyên nhân: IP bị block, ms_token hết hạn, hoặc hashtag không tồn tại.")
            elif "browser" in err_msg.lower() or "executable" in err_msg.lower():
                print(f"  [!] TikTokApi: {err_name} — Playwright browser không tìm thấy.")
                print(f"      Chạy: playwright install chromium && playwright install-deps chromium")
            elif "ms_token" in err_msg.lower() or "cookie" in err_msg.lower() or "403" in err_msg:
                print(f"  [!] TikTokApi: {err_name} — ms_token hết hạn hoặc bị block.")
                print(f"      Cập nhật ms_token mới từ TikTok (F12 → Application → Cookies).")
            else:
                print(f"  [!] TikTokApi: {err_name}: {err_msg}")

        return video_data

    try:
        return asyncio.run(_fetch())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_fetch())
        finally:
            loop.close()


def fetch_hashtag_videos(tag: str, max_videos: int = 90, driver=None, proxy: str = None) -> tuple[list[str], dict]:
    """
    Thu thập video URLs + stats từ TikTok hashtag bằng TikTokApi.

    Returns:
        tuple: (list[url], dict{url: stats_dict})
    """
    print(f"  [TikTokApi] Thử cho #{tag}...")
    video_data = fetch_via_tiktokapi(tag, max_videos=max_videos, driver=driver, proxy=proxy)
    if video_data:
        urls = [item[0] for item in video_data]
        stats_map = {item[0]: item[1] for item in video_data}
        print(f"  [✓] TikTokApi: Tìm thấy {len(urls)} video (có stats)")
        return urls, stats_map
    print("  [✗] TikTokApi thất bại.")
    return [], {}
