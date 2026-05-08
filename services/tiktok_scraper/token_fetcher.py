"""
Token Fetcher — Tự động lấy ms_token từ TikTok mà không cần browser.

Sử dụng HTTP request nhẹ (requests) để lấy cookie msToken.
Ưu tiên: Selenium cookies → Auto fetch → Env var.
"""
import os
import sys
import random
import string
import requests

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Browser fingerprints giả lập
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
]


def _generate_device_id() -> str:
    """Tạo device_id giả để tăng credibility."""
    return "".join(random.choices(string.digits, k=19))


def fetch_ms_token_via_http(proxy: str = None) -> str:
    """
    Lấy ms_token bằng HTTP request đến TikTok.
    TikTok set cookie msToken khi visit trang bất kỳ.

    Args:
        proxy: Proxy URL (tùy chọn)

    Returns:
        ms_token string hoặc rỗng nếu thất bại
    """
    headers = {
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }

    proxies = {"http": proxy, "https": proxy} if proxy else None

    # Thử nhiều endpoint
    urls_to_try = [
        "https://www.tiktok.com/",
        "https://www.tiktok.com/foryou",
        "https://www.tiktok.com/explore",
    ]

    for url in urls_to_try:
        try:
            resp = requests.get(
                url,
                headers=headers,
                proxies=proxies,
                timeout=15,
                allow_redirects=True,
            )

            # Tìm msToken trong cookies
            for cookie in resp.cookies:
                if cookie.name == "msToken" and cookie.value:
                    token = cookie.value
                    if len(token) > 20:  # msToken thường dài > 20 chars
                        print(f"  [✓] Auto ms_token: {token[:20]}... (từ {url})")
                        return token

        except requests.RequestException:
            continue

    return ""


def fetch_ms_token_via_api(proxy: str = None) -> str:
    """
    Lấy ms_token qua TikTok internal API endpoint.
    Endpoint này trả về token mà không cần load full page.
    """
    headers = {
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.tiktok.com/",
        "Origin": "https://www.tiktok.com",
    }

    proxies = {"http": proxy, "https": proxy} if proxy else None

    # TikTok's internal token endpoint
    api_urls = [
        "https://www.tiktok.com/api/comment/list/?aid=1988&app_name=tiktok_web&device_platform=web&region=VN&priority_region=&os=windows&browser=Chrome&browser_version=131&browser_language=en&screen_width=1920&screen_height=1080&cpu_core_num=8&device_memory=8&platform=PC&downlink=10&effective_type=4g&round_trip_time=50&msToken=",
        "https://www.tiktok.com/api/search/general/full/?aid=1988&keyword=test&msToken=",
    ]

    for url in api_urls:
        try:
            resp = requests.get(
                url,
                headers=headers,
                proxies=proxies,
                timeout=15,
                allow_redirects=True,
            )

            # Tìm msToken trong response cookies
            for cookie in resp.cookies:
                if cookie.name == "msToken" and cookie.value and len(cookie.value) > 20:
                    token = cookie.value
                    print(f"  [✓] Auto ms_token (API): {token[:20]}...")
                    return token

        except requests.RequestException:
            continue

    return ""


def get_ms_token(driver=None, proxy: str = None) -> str:
    """
    Lấy ms_token theo thứ tự ưu tiên:
    1. Selenium browser cookies (nếu driver có sẵn)
    2. Auto fetch qua HTTP request
    3. Environment variable

    Args:
        driver: Selenium WebDriver (optional)
        proxy: Proxy URL (optional)

    Returns:
        ms_token string hoặc rỗng
    """
    # 1. Từ Selenium cookies
    if driver:
        try:
            for c in driver.get_cookies():
                if c.get("name") == "msToken" and c.get("value"):
                    token = c["value"]
                    if len(token) > 20:
                        print(f"  [✓] ms_token từ Selenium cookies: {token[:20]}...")
                        return token
        except Exception:
            pass

    # 2. Auto fetch qua HTTP
    token = fetch_ms_token_via_http(proxy=proxy)
    if token:
        return token

    # 3. Thử qua API endpoint
    token = fetch_ms_token_via_api(proxy=proxy)
    if token:
        return token

    # 4. Env var
    token = os.environ.get("ms_token", "")
    if token:
        print(f"  [✓] ms_token từ env var: {token[:20]}...")
        return token

    print("  [!] Không lấy được ms_token từ mọi nguồn.")
    return ""
