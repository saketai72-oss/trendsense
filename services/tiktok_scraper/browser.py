import undetected_chromedriver as uc
import os
import re
import subprocess
import json
import random
import platform
import socket
import urllib.parse
import urllib.request
import zipfile
import tempfile

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


def _normalize_proxy(raw: str) -> str | None:
    """
    Chuẩn hóa proxy URL cho Chrome --proxy-server.
    Chrome yêu cầu scheme rõ ràng (http://, https://, socks5://).
    Nếu proxy chỉ có host:port → thêm http://.
    Nếu proxy có user:pass@host:port → giữ nguyên (Chrome hỗ trợ inline auth).
    Trả về None nếu proxy không hợp lệ.
    """
    raw = raw.strip()
    if not raw:
        return None

    # Đã có scheme → dùng nguyên
    if raw.startswith(("http://", "https://", "socks4://", "socks5://")):
        return raw

    # Có @ nhưng không có scheme → user:pass@host:port
    if "@" in raw:
        return f"http://{raw}"

    # Chỉ có host:port
    if re.match(r"^\d{1,3}(\.\d{1,3}){3}:\d+$", raw):
        return f"http://{raw}"

    # hostname:port
    if re.match(r"^[a-zA-Z0-9][\w.-]*:\d+$", raw):
        return f"http://{raw}"

    print(f"[!] Proxy không hợp lệ: '{raw}'")
    return None


def _test_proxy_connectivity(proxy_url: str, timeout: int = 5) -> bool:
    """Kiểm tra nhanh xem proxy có thể kết nối TCP không."""
    try:
        parsed = urllib.parse.urlparse(proxy_url)
        host = parsed.hostname
        port = parsed.port
        if not host or not port:
            return False
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return True
    except (socket.timeout, socket.error, OSError):
        return False


def get_random_proxy() -> str | None:
    """Chọn ngẫu nhiên 1 proxy từ pool, kiểm tra kết nối trước khi trả về."""
    pool = _load_proxy_pool()
    if not pool:
        return None

    # Xáo trộn và thử từng proxy
    random.shuffle(pool)
    for raw in pool:
        proxy = _normalize_proxy(raw)
        if not proxy:
            continue
        if _test_proxy_connectivity(proxy):
            return proxy
        else:
            print(f"[!] Proxy không kết nối được: {raw} — bỏ qua.")

    print("[!] ⚠️ Không có proxy nào khả dụng trong pool!")
    return None


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


# ── Chrome Version Detection ──────────────────────────────────────
def get_chrome_version() -> int | None:
    """Detect installed Chrome major version (Linux & Windows)."""
    os_name = platform.system()
    try:
        if os_name == "Linux":
            result = subprocess.run(
                ["google-chrome", "--version"],
                capture_output=True, text=True, timeout=10,
            )
            match = re.search(r"(\d+)\.\d+\.\d+\.\d+", result.stdout)
            if match:
                return int(match.group(1))

        elif os_name == "Windows":
            result = subprocess.run(
                [
                    "reg", "query",
                    r"HKEY_CURRENT_USER\Software\Google\Chrome\BLBeacon",
                    "/v", "version",
                ],
                capture_output=True, text=True, timeout=10,
            )
            match = re.search(r"version\s+REG_SZ\s+(\d+)\.", result.stdout)
            if match:
                return int(match.group(1))
    except Exception as e:
        print(f"[!] Lỗi detect Chrome version: {e}")
    return None


# ── ChromeDriver Version Matching ────────────────────────────────
def _download_matching_chromedriver(chrome_version: int) -> str | None:
    """
    Download ChromeDriver khớp chính xác với Chrome version đã cài.
    Dùng Chrome for Testing JSON API (không phụ thuộc uc.Patcher auto-download).

    Trả về đường dẫn chromedriver đã patch, hoặc None nếu thất bại.
    """
    # Bước 1: Lấy version đầy đủ từ Chrome binary
    full_version = None
    if platform.system() == "Linux":
        for binary in ["google-chrome", "google-chrome-stable", "chromium-browser", "chromium"]:
            try:
                result = subprocess.run(
                    [binary, "--version"], capture_output=True, text=True, timeout=10
                )
                match = re.search(r"(\d+\.\d+\.\d+\.\d+)", result.stdout)
                if match:
                    full_version = match.group(1)
                    break
            except FileNotFoundError:
                continue
    elif platform.system() == "Windows":
        # Thử registry trước (đáng tin cậy hơn chrome.exe --version trên Windows)
        try:
            result = subprocess.run(
                ["reg", "query", r"HKEY_CURRENT_USER\Software\Google\Chrome\BLBeacon", "/v", "version"],
                capture_output=True, text=True, timeout=10,
            )
            match = re.search(r"version\s+REG_SZ\s+(\d+\.\d+\.\d+\.\d+)", result.stdout)
            if match:
                full_version = match.group(1)
        except Exception:
            pass

    if not full_version:
        print(f"[!] Không lấy được full version string cho Chrome {chrome_version}")
        return None

    print(f"[*] Chrome full version: {full_version}")

    # Bước 2: Query Chrome for Testing API để tìm ChromeDriver matching
    try:
        api_url = "https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json"
        req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())

        # Detect platform + architecture đúng cho Chrome for Testing
        system = platform.system()
        machine = platform.machine().lower()
        if system == "Linux":
            platform_key = "linux-arm64" if machine in ("aarch64", "arm64") else "linux64"
        elif system == "Windows":
            platform_key = "win64"
        elif system == "Darwin":
            platform_key = "mac-arm64" if machine == "arm64" else "mac-x64"
        else:
            platform_key = "linux64"
        print(f"[*] Platform: {system}/{machine} → {platform_key}")

        driver_url = None

        # Tìm version khớp chính xác trước
        for v in data.get("versions", []):
            if v.get("version") == full_version:
                downloads = v.get("downloads", {}).get("chromedriver", [])
                for dl in downloads:
                    if dl.get("platform") == platform_key:
                        driver_url = dl["url"]
                        break
                break

        # Nếu không tìm thấy exact match, tìm version gần nhất cùng major
        if not driver_url:
            for v in reversed(data.get("versions", [])):
                if v.get("version", "").startswith(f"{chrome_version}."):
                    downloads = v.get("downloads", {}).get("chromedriver", [])
                    for dl in downloads:
                        if dl.get("platform") == platform_key:
                            driver_url = dl["url"]
                            print(f"[*] Không có ChromeDriver {full_version}, dùng {v['version']} thay thế")
                            break
                    if driver_url:
                        break

        if not driver_url:
            print(f"[!] Không tìm thấy ChromeDriver cho Chrome {chrome_version} trên API")
            return None

        # Bước 3: Download và extract
        dest_dir = os.path.join(tempfile.gettempdir(), f"chromedriver_{chrome_version}")
        dest_path = os.path.join(
            dest_dir,
            "chromedriver.exe" if platform.system() == "Windows" else "chromedriver",
        )

        if os.path.exists(dest_path):
            print(f"[*] ChromeDriver đã có sẵn: {dest_path}")
        else:
            os.makedirs(dest_dir, exist_ok=True)
            zip_path = os.path.join(dest_dir, "chromedriver.zip")
            print(f"[*] Đang download ChromeDriver từ: {driver_url}")
            urllib.request.urlretrieve(driver_url, zip_path)

            with zipfile.ZipFile(zip_path, "r") as zf:
                for name in zf.namelist():
                    if name.endswith("chromedriver") or name.endswith("chromedriver.exe"):
                        # Extract vào dest_dir
                        with zf.open(name) as src, open(dest_path, "wb") as dst:
                            dst.write(src.read())
                        break

            os.chmod(dest_path, 0o755)
            os.remove(zip_path)

            # Verify binary hợp lệ (tránh Exec format error)
            if platform.system() != "Windows":
                try:
                    result = subprocess.run(
                        [dest_path, "--version"], capture_output=True, text=True, timeout=10
                    )
                    if result.returncode != 0 and "cannot execute" in (result.stderr + result.stdout).lower():
                        print(f"[!] ChromeDriver binary không chạy được trên kiến trúc này ({machine})")
                        os.remove(dest_path)
                        return None
                except OSError as e:
                    if "Exec format error" in str(e):
                        print(f"[!] ChromeDriver sai kiến trúc: {machine}")
                        os.remove(dest_path)
                        return None

            print(f"[*] Đã download ChromeDriver: {dest_path}")

        # Bước 4: Patch để bypass bot detection
        patcher = uc.Patcher(executable_path=dest_path)
        if not patcher.is_binary_patched(dest_path):
            patcher.executable_path = dest_path
            patcher.patch_exe()
            print(f"[*] Đã patch ChromeDriver (bypass detection)")

        return dest_path

    except Exception as e:
        print(f"[!] Lỗi download ChromeDriver: {type(e).__name__}: {str(e)[:200]}")
        return None


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
        normalized = _normalize_proxy(proxy)
        if normalized:
            options.add_argument(f'--proxy-server={normalized}')
            display_proxy = normalized.split('@')[-1] if '@' in normalized else normalized
            print(f"[🔀 PROXY] Đang dùng: {display_proxy}")
        else:
            print(f"[!] Proxy không hợp lệ, chạy không proxy.")
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

    # Detect Chrome version — bắt buộc cho uc 3.5.5
    v_main = get_chrome_version()
    if v_main:
        print(f"[*] Chrome v{v_main} ({platform.system()})")
    else:
        print("[!] Không detect được Chrome version")

    # Download đúng ChromeDriver khớp Chrome binary — ưu tiên Chrome for Testing API
    driver_path = None
    if v_main:
        driver_path = _download_matching_chromedriver(v_main)

    # Fallback 1: tìm chromedriver trong PATH → copy về /tmp để uc patch được
    if not driver_path:
        import shutil
        system_cd = shutil.which("chromedriver")
        if system_cd:
            tmp_cd = os.path.join(tempfile.gettempdir(), "chromedriver_uc")
            shutil.copy2(system_cd, tmp_cd)
            os.chmod(tmp_cd, 0o755)
            driver_path = tmp_cd
            print(f"[*] Dùng system chromedriver (copy → {tmp_cd})")

    # Fallback 2: dùng uc Patcher (có thể mismatch nhưng tốt hơn nothing)
    if not driver_path:
        print("[*] Fallback: dùng uc.Patcher để download ChromeDriver...")
        patcher = uc.Patcher(version_main=v_main)
        patcher.auto()
        driver_path = patcher.executable_path

    print(f"[*] ChromeDriver: {driver_path}")

    # Pre-patch chromedriver TRƯỚC khi tạo uc.Chrome
    # để uc.Chrome.__init__ thấy binary đã patched và skip auto()
    try:
        patcher = uc.Patcher(executable_path=driver_path)
        if not patcher.is_binary_patched(driver_path):
            patcher.executable_path = driver_path
            patcher.patch_exe()
            print(f"[*] Đã patch ChromeDriver")
        else:
            print(f"[*] ChromeDriver đã được patch sẵn")
    except Exception as e:
        print(f"[!] Patch warning: {e}")

    # Monkey-patch: chặn uc.Chrome gọi patcher.auto() lần nữa
    _orig_auto = uc.Patcher.auto
    uc.Patcher.auto = lambda self: getattr(self, 'executable_path', None)

    try:
        driver = uc.Chrome(
            options=options,
            browser_executable_path=chrome_path,
            driver_executable_path=driver_path,
            use_subprocess=True,
            version_main=v_main,
        )
    finally:
        # Khôi phục patcher.auto gốc
        uc.Patcher.auto = _orig_auto

    driver.set_page_load_timeout(60)
    driver.implicitly_wait(10)

    return driver
