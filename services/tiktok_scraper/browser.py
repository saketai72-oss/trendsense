import undetected_chromedriver as uc
import os
import json
import random
import platform

# Ngăn lỗi "Exception ignored in: <function Chrome.__del__>" trên Windows
if hasattr(uc.Chrome, '__del__'):
    _original_del = uc.Chrome.__del__
    def _safe_del(self):
        try:
            _original_del(self)
        except OSError:
            pass
    uc.Chrome.__del__ = _safe_del


# ── Proxy Pool ────────────────────────────────────────────────────
def _load_proxy_pool() -> list:
    """
    Đọc danh sách proxy từ biến môi trường PROXY_LIST.
    Hỗ trợ 2 định dạng:
      - JSON array: '["http://user:pass@host:port", ...]'
      - Comma-separated: "http://user:pass@host1:port,http://user:pass@host2:port"
    Trả về list rỗng nếu không có cấu hình (scraper chạy không proxy).
    """
    raw = os.environ.get("PROXY_LIST", "").strip()
    if not raw:
        return []
    try:
        pool = json.loads(raw)
        if isinstance(pool, list):
            return [p.strip() for p in pool if p.strip()]
    except json.JSONDecodeError:
        pass
    # Fallback: comma-separated
    return [p.strip() for p in raw.split(",") if p.strip()]


def get_random_proxy() -> str | None:
    """Chọn ngẫu nhiên 1 proxy từ pool. Trả về None nếu pool rỗng."""
    pool = _load_proxy_pool()
    if not pool:
        return None
    return random.choice(pool)


# ── Block Detection ────────────────────────────────────────────────
BLOCK_SIGNALS = [
    "robot", "captcha", "unusual traffic", "403", "access denied",
    "verify you are human", "security check", "just a moment",
    "enable javascript", "tiktok.com/login",  # redirect to login = block
]


def is_blocked(driver) -> bool:
    """
    Kiểm tra xem TikTok có đang block trình duyệt không.
    Trả về True nếu phát hiện block signal trong title hoặc body.
    """
    try:
        page_title = (driver.title or "").lower()
        # Kiểm tra title trước (nhanh)
        for signal in BLOCK_SIGNALS:
            if signal in page_title:
                print(f"[🚫 BLOCK] Phát hiện tín hiệu block trong title: '{page_title}'")
                return True

        # Kiểm tra body text (chậm hơn nhưng chắc chắn hơn)
        try:
            body_text = driver.find_element("tag name", "body").text.lower()[:500]
            for signal in ["captcha", "robot", "unusual traffic", "verify you are human"]:
                if signal in body_text:
                    print(f"[🚫 BLOCK] Phát hiện tín hiệu block trong body: '{signal}'")
                    return True
        except Exception:
            pass

        return False
    except Exception:
        return False


# ── Driver Init ───────────────────────────────────────────────────
def init_driver(proxy: str | None = None):
    """
    Khởi tạo Undetected ChromeDriver.

    Args:
        proxy: URL proxy dạng "http://user:pass@host:port" hoặc None

    Returns:
        uc.Chrome instance
    """
    options = uc.ChromeOptions()

    # Cấu hình ẩn danh
    options.add_argument('--headless=new')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
    options.page_load_strategy = 'eager'

    # Gắn proxy nếu có
    if proxy:
        options.add_argument(f'--proxy-server={proxy}')
        print(f"[🔀 PROXY] Đang dùng: {proxy.split('@')[-1] if '@' in proxy else proxy}")
    else:
        print("[*] Không có proxy — dùng IP thật (có thể bị block trên GitHub Actions).")

    # Tìm Chrome binary trên Windows
    chrome_path = None
    if platform.system() == 'Windows':
        paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
        ]
        for p in paths:
            if os.path.exists(p):
                chrome_path = p
                break

    # Lấy version_main từ env (CI detect) hoặc để None (local auto-detect)
    v_main = os.environ.get("CHROME_VERSION_MAIN")
    v_main = int(v_main) if v_main else None

    driver = uc.Chrome(
        options=options,
        browser_executable_path=chrome_path,
        use_subprocess=True,
        version_main=v_main,
    )

    driver.set_page_load_timeout(60)
    driver.implicitly_wait(10)

    return driver
