import os
import sys
from requests import options
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

def init_driver():
    chrome_options = Options()
    
    # --- BỘ 3 QUY TẮC BẮT BUỘC ĐỂ CHẠY TRÊN GITHUB ACTIONS (LINUX) ---
    chrome_options.add_argument('--headless=new')          
    chrome_options.add_argument('--no-sandbox')            
    chrome_options.add_argument('--disable-dev-shm-usage') 
    
    # --- Tùy chọn thêm để ngụy trang, tránh bị block ---
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    # Khởi tạo bằng CHROME 
    driver = webdriver.Chrome(options=chrome_options)
    
    return driver