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
    MAX_SCROLLS = 200
    print(f"[*] Lướt tìm {target_count} video mới toanh...")
    
    while len(links) < target_count and scroll_attempts < MAX_SCROLLS:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        videos = driver.find_elements(By.CSS_SELECTOR, "a[href*='/video/']")
        for v in videos:
            raw_link = v.get_attribute("href")
            video_id = extract_video_id(raw_link)
            
            if video_id and not is_scraped(video_id):
                clean_link = raw_link.split('?')[0]
                if clean_link not in links:
                    links.append(clean_link)
                    print(f"  + Đã chốt được video mới ({len(links)}/{target_count}) - ID: {video_id}")
                    
            if len(links) == target_count: 
                break
        scroll_attempts += 1
        
    return links