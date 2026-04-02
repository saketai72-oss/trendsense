import time
from selenium.webdriver.common.by import By
from database import is_scraped, extract_video_id
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from config import settings

def get_trending_links(driver, target_count=settings.MAX_VIDEOS):
    links = []
    scroll_attempts = 0
    MAX_SCROLLS = 50
    print(f"[*] Lướt tìm {target_count} video mới toanh...")
    
    while len(links) < target_count and scroll_attempts < MAX_SCROLLS:
        # Kiểm tra xem có video nào trên trang không
        videos = driver.find_elements(By.CSS_SELECTOR, "a[href*='/video/']")
        
        if not videos:
            print(f"  [?] Không thấy video nào ở lần lướt {scroll_attempts+1}... Có thể do Captcha hoặc mạng chậm.")
            # Chụp ảnh (ẩn) để debug nếu cần, nhưng tạm thời đợi lâu hơn
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
                            print(f"  + Chốt video MỚI: {video_id} ({len(links)}/{target_count})")
                    else:
                        # LOG NÀY QUAN TRỌNG: Để biết bạn đã cào hết trend cũ chưa
                        pass # Nếu in quá nhiều sẽ bị rác log, tôi sẽ chỉ in nếu 10 lần liên tiếp skip
                
                if len(links) >= target_count: 
                    break
            except: continue
            
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        scroll_attempts += 1
        
    if not links:
        print("[!] ⚠️ CẢNH BÁO: Cuối cùng vẫn không tìm thấy link nào. Kiểm tra lại trình duyệt (có thể bị Captcha).")
        
    return links