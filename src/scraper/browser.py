import undetected_chromedriver as uc
import os
import re

def get_chrome_version():
    """Radar dò tìm phiên bản Chrome thực tế đang cài trên máy ảo Linux"""
    try:
        # Gõ lệnh vào Terminal của Linux để check version
        output = os.popen('google-chrome --version').read()
        # Output thường có dạng: "Google Chrome 146.0.7680.164"
        match = re.search(r' (\d+)\.', output)
        if match:
            return int(match.group(1)) # Chỉ lấy 2-3 số đầu (VD: 146)
    except Exception as e:
        print(f"[!] Lỗi dò version: {e}")
    return None

def init_driver():
    options = uc.ChromeOptions()
    
    # Giáp bảo vệ trên Linux
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    # Ngụy trang User-Agent
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')

    # 1. Bật radar dò version
    v_main = get_chrome_version()
    if v_main:
        print(f"[*] Máy ảo Github đang chạy Chrome phiên bản: {v_main}")
    else:
        print("[!] Không dò được version, nhắm mắt tải bừa bản mới nhất...")

    # 2. Khởi tạo tàng hình với đúng version đã dò được
    driver = uc.Chrome(
        options=options,
        headless=True,
        use_subprocess=True,
        version_main=v_main  
    )
    
    return driver