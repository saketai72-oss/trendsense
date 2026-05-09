"""
Token Fetcher — Tự động lấy ms_token từ TikTok mà không cần browser.

Sử dụng HTTP request nhẹ (requests) để lấy cookie msToken.
Ưu tiên: Selenium cookies → HTTP auto-fetch → Env var.
"""
import os
import sys
import random
import requests

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
]

# Chọn 1 UA nhất quán cho toàn bộ session
_SESSION_UA = random.choice(_USER_AGENTS)


def fetch_ms_token_via_http(proxy: str | None = None) -> str:
    """
    Lấy ms_token bằng HTTP request đến TikTok.
    TikTok set cookie msToken khi visit trang bất kỳ.
    """
    headers = {
        "User-Agent": _SESSION_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
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

    for url in ["https://www.tiktok.com/", "https://www.tiktok.com/explore"]:
        try:
            resp = requests.get(url, headers=headers, proxies=proxies, timeout=15, allow_redirects=True)
            ms_token = resp.cookies.get("msToken")
            if ms_token and len(ms_token) > 20:
                print(f"  [✓] Auto ms_token: {ms_token[:20]}... (từ {url})")
                return ms_token
        except requests.RequestException:
            continue

    return ""


def get_ms_token(driver=None, proxy: str | None = None) -> str:
    """
    Lấy ms_token theo thứ tự ưu tiên:
    1. Selenium browser cookies (nếu driver có sẵn)
    2. Auto fetch qua HTTP request
    3. Environment variable (fallback)
    """
    # 1. Từ Selenium cookies
    if driver:
        try:
            for c in driver.get_cookies():
                if c.get("name") == "msToken" and c.get("value") and len(c["value"]) > 20:
                    print(f"  [✓] ms_token từ Selenium: {c['value'][:20]}...")
                    return c["value"]
        except Exception:
            pass

    # 2. Auto fetch qua HTTP
    token = fetch_ms_token_via_http(proxy=proxy)
    if token:
        return token

    # 3. Env var
    token = os.environ.get("ms_token", "")
    if token:
        print(f"  [✓] ms_token từ env var: {token[:20]}...")
        return token

    print("  [!] Không lấy được ms_token từ mọi nguồn.")
    return ""
