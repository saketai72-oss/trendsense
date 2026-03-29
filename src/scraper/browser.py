import undetected_chromedriver as uc

def init_driver():
    options = uc.ChromeOptions()
    
    # 2 Cờ bắt buộc để sống sót trên máy ảo Linux
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    # Giữ lại lớp ngụy trang
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')

    # KHỞI TẠO CHUẨN CHO GITHUB ACTIONS
    driver = uc.Chrome(
        options=options,
        headless=True,      
        use_subprocess=True  
    )
    
    return driver