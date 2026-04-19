import time
from selenium.webdriver.common.by import By
from database import is_scraped, extract_video_id
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from core.config import service_settings as settings

# Hệ số nhân: Thu thập gấp bao nhiêu lần target để dự phòng bị lọc ngôn ngữ
BUFFER_MULTIPLIER = 3


def get_trending_links(driver, target_count=settings.MAX_VIDEOS):
    """
    Thu thập link video từ trang Explore.
    Luôn thu gấp BUFFER_MULTIPLIER lần target_count để dự phòng
    bị lọc ngôn ngữ (video quốc tế) → tránh lãng phí thời gian.
    """
    buffer_target = target_count * BUFFER_MULTIPLIER
    links = []
    scroll_attempts = 0
    MAX_SCROLLS = 50
    print(f"[*] Lướt tìm tối đa {buffer_target} link dự phòng (cần {target_count} video Việt)...")
    
    while len(links) < buffer_target and scroll_attempts < MAX_SCROLLS:
        # Kiểm tra xem có video nào trên trang không
        videos = driver.find_elements(By.CSS_SELECTOR, "a[href*='/video/']")
        
        if not videos:
            print(f"  [?] Không thấy video nào ở lần lướt {scroll_attempts+1}... Có thể do Captcha hoặc mạng chậm.")
            time.sleep(3)

        for v in videos:
            try:
                raw_link = v.get_attribute("href")
                video_id = extract_video_id(raw_link)
                
                if video_id:
                    if not is_scraped(video_id):
                        clean_link = raw_link.split('?')[0]
                        if clean_link not in links:
                            links.append(clean_link)
                            print(f"  + Chốt video MỚI: {video_id} ({len(links)}/{buffer_target})")
                    else:
                        pass
                
                if len(links) >= buffer_target: 
                    break
            except: continue
            
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.5)  # Giảm từ 2s → 1.5s (headless không cần render)
        scroll_attempts += 1
        
    if not links:
        print("[!] ⚠️ CẢNH BÁO: Cuối cùng vẫn không tìm thấy link nào. Kiểm tra lại trình duyệt (có thể bị Captcha).")
    else:
        print(f"[✓] Thu thập được {len(links)} link ứng viên.")
        
    return links
