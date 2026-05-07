"""
Hashtag Fetcher — Thu thập video URLs từ TikTok hashtag bằng TikTokApi.

Tự động lấy ms_token từ Selenium browser cookies → truyền cho TikTokApi.
TikTokApi dùng Playwright để tạo browser session hợp lệ với TikTok.
"""
import os
import sys
import asyncio

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))


def _extract_ms_token_from_driver(driver) -> str:
    """Trích xuất ms_token từ Selenium browser cookies."""
    try:
        for c in driver.get_cookies():
            if c.get("name") == "msToken":
                return c["value"]
    except Exception:
        pass
    return os.environ.get("ms_token", "")


def fetch_via_tiktokapi(tag: str, max_videos: int = 90, driver=None, proxy: str = None) -> list[str]:
    """
    Dùng TikTokApi để lấy video từ hashtag.
    Cần ms_token (tự động lấy từ Selenium browser cookies hoặc env var).
    """
    try:
        from TikTokApi import TikTokApi
    except ImportError:
        print("  [!] TikTokApi chưa cài. Chạy: pip install TikTokApi")
        return []

    ms_token = ""
    if driver:
        ms_token = _extract_ms_token_from_driver(driver)
    if not ms_token:
        ms_token = os.environ.get("ms_token", "")
    if not ms_token:
        print("  [!] Thiếu ms_token. Đảm bảo browser đã load TikTok hoặc set env var ms_token.")
        return []

    async def _fetch():
        video_urls = []
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
                        video_urls.append(url)

        except Exception as e:
            print(f"  [!] TikTokApi error: {type(e).__name__}: {str(e)[:200]}")

        return video_urls

    try:
        return asyncio.run(_fetch())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_fetch())
        finally:
            loop.close()


def fetch_hashtag_videos(tag: str, max_videos: int = 90, driver=None, proxy: str = None) -> list[str]:
    """
    Thu thập video URLs từ TikTok hashtag bằng TikTokApi.

    Args:
        tag: Tên hashtag (không có #)
        max_videos: Số video tối đa
        driver: Selenium WebDriver (để lấy ms_token cookies)
        proxy: Proxy URL (tùy chọn)

    Returns:
        list[str]: Danh sách video URLs (có thể rỗng).
    """
    print(f"  [TikTokApi] Thử cho #{tag}...")
    urls = fetch_via_tiktokapi(tag, max_videos=max_videos, driver=driver, proxy=proxy)
    if urls:
        print(f"  [✓] TikTokApi: Tìm thấy {len(urls)} video")
        return urls
    print("  [✗] TikTokApi thất bại.")
    return []
