import undetected_chromedriver as uc
import os
import re
import platform

# Ngăn lỗi "Exception ignored in: <function Chrome.__del__>" và [WinError 6] The handle is invalid trên Windows
if hasattr(uc.Chrome, '__del__'):
    _original_del = uc.Chrome.__del__
    def _safe_del(self):
        try:
            _original_del(self)
        except OSError:
            pass
    uc.Chrome.__del__ = _safe_del

def get_chrome_version():
    """Radar thông minh: Tự nhận diện hệ điều hành để dò version Chrome"""
    os_name = platform.system()
    try:
        if os_name == 'Linux':
            # Dò trên máy ảo Github
            output = os.popen('google-chrome --version').read()
            match = re.search(r' (\d+)\.', output)
            if match:
                return int(match.group(1))
                
        elif os_name == 'Windows':
            # Dò trong Registry của máy tính cá nhân
            output = os.popen('reg query "HKEY_CURRENT_USER\\Software\\Google\\Chrome\\BLBeacon" /v version').read()
            match = re.search(r'version\s+REG_SZ\s+(\d+)\.', output)
            if match:
                return int(match.group(1))
    except Exception as e:
        print(f"[!] Lỗi radar dò version: {e}")
    return None

def init_driver():
    options = uc.ChromeOptions()
    
    # 1. Tối ưu cấu hình ẩn danh (CHỐNG WINERROR 6 & TikTok detection)
    options.add_argument('--headless=new') 
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')

    # 2. Radar dò tìm phiên bản Chrome để khớp Driver
    v_main = get_chrome_version()
    if v_main:
        print(f"[*] Radar dò được Chrome phiên bản: {v_main} ({platform.system()})")
    else:
        print("[!] Không dò được version, nhắm mắt tải bừa bản mới nhất...")

    # 3. Hỗ trợ tìm file Chrome trên Windows (Chống lỗi Binary Location)
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

    # 3. Khởi tạo tàng hình
    driver = uc.Chrome(
        options=options,
        browser_executable_path=chrome_path,
        use_subprocess=True,
        version_main=v_main
    )
    
    return driver