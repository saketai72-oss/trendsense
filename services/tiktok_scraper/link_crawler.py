"""
Link Crawler — Thu thập link video TikTok từ hashtag/challenge.

Thứ tự ưu tiên:
1. hashtag_fetcher (TikTokApi → ScrapFly) — open-source, anti-bot
2. Selenium DOM scraping — fallback cuối cùng
"""
import time
import sys
import os
import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from core.config import service_settings as settings
from core.db.models import is_scraped, extract_video_id
from services.tiktok_scraper.hashtag_fetcher import fetch_hashtag_videos

BUFFER_MULTIPLIER = 3


def _save_debug_snapshot(driver, label="debug"):
    try:
        os.makedirs("debug_snapshots", exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = f"debug_snapshots/{label}_{ts}.png"
        source_path = f"debug_snapshots/{label}_{ts}.html"
        driver.save_screenshot(screenshot_path)
        with open(source_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print(f"  [📸] Đã lưu debug snapshot: {screenshot_path}")
        return screenshot_path
    except Exception as e:
        print(f"  [!] Không thể lưu debug snapshot: {e}")
        return None


def get_trending_links(driver, target_count=settings.MAX_VIDEOS):
    """
    Thu thập link video từ hashtag page.

    Ưu tiên: TikTokApi → ScrapFly → Selenium DOM fallback.
    """
    buffer_target = target_count * BUFFER_MULTIPLIER
    links = []

    print(f"[*] Lướt tìm tối đa {buffer_target} link dự phòng (cần {target_count} video Việt)...")

    # Parse tag từ URL hiện tại
    current_url = driver.current_url
    tag = current_url.split("/tag/")[-1].split("?")[0].strip("/") if "/tag/" in current_url else ""

    if not tag:
        print(f"  [!] Không parse được tag từ URL: {current_url}")
        return links

    # === CHIẾN LƯỢC 1: hashtag_fetcher (TikTokApi) ===
    raw_urls = fetch_hashtag_videos(tag, max_videos=buffer_target, driver=driver)

    for url in raw_urls:
        video_id = extract_video_id(url)
        if video_id and not is_scraped(video_id):
            clean_link = url.split('?')[0]
            if clean_link not in links:
                links.append(clean_link)
                print(f"  + Chốt video MỚI: {video_id} ({len(links)}/{buffer_target})")
        if len(links) >= buffer_target:
            break

    # === CHIẾN LƯỢC 2: Selenium DOM scraping (fallback cuối) ===
    if not links:
        print("[*] Fallback: Selenium DOM scraping...")
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/video/']"))
            )
        except:
            pass

        debug_saved = False
        for scroll_round in range(30):
            if len(links) >= buffer_target:
                break

            elems = driver.find_elements(By.CSS_SELECTOR, "a[href*='/video/']")
            for e in elems:
                try:
                    href = e.get_attribute("href")
                    if not href:
                        continue
                    video_id = extract_video_id(href)
                    if video_id and not is_scraped(video_id):
                        clean_link = href.split('?')[0]
                        if clean_link not in links:
                            links.append(clean_link)
                            print(f"  + Chốt video MỚI (DOM): {video_id} ({len(links)}/{buffer_target})")
                except:
                    continue

            if scroll_round == 3 and not links and not debug_saved:
                _save_debug_snapshot(driver, label="no_videos")
                debug_saved = True

            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

    if not links:
        print("[!] ⚠️ CẢNH BÁO: Không tìm thấy link nào từ mọi chiến lược.")
        _save_debug_snapshot(driver, label="final_no_videos")
    else:
        print(f"[✓] Thu thập được {len(links)} link ứng viên.")

    return links
