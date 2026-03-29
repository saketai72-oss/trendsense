import undetected_chromedriver as uc
import os
import re
import platform

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
    
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')

    # 1. Bật radar thông minh
    v_main = get_chrome_version()
    if v_main:
        print(f"[*] Radar dò được Chrome phiên bản: {v_main} ({platform.system()})")
    else:
        print("[!] Không dò được version, nhắm mắt tải bừa bản mới nhất...")

    # 2. Hỗ trợ tìm file Chrome trên Windows (Chống lỗi Binary Location)
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
        browser_executable_path=chrome_path, # Tự động chèn nếu là Windows
        headless=True,
        use_subprocess=True,
        version_main=v_main
    )
    
    return driver