import sys
import os
import time
import random
from datetime import datetime

# Thêm đường dẫn gốc để import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from langdetect import detect, detect_langs, LangDetectException
except ImportError:
    print("[!] Thiếu thư viện langdetect. Hãy chạy: pip install langdetect")
    sys.exit(1)

from services.tiktok_scraper.browser import init_driver
from core.db.models import (
    get_all_video_links, 
    delete_video, 
    update_rescraped_stats_only,
    extract_video_id
)
from services.tiktok_scraper.content_parser import extract_basic_stats

def detect_language_robust(caption, existing_comments=[]):
    """
    Detect ngôn ngữ với cơ chế fallback sang comments cũ nếu caption không đủ thông tin.
    """
    text_to_check = caption.strip()
    
    # 1. Thử detect caption mới nhất vừa cào
    if len(text_to_check) > 10:
        try:
            langs = detect_langs(text_to_check)
            top_lang = langs[0]
            if top_lang.lang in ['vi', 'en'] and top_lang.prob > 0.8:
                return top_lang.lang
        except LangDetectException:
            pass

    # 2. Fallback sang comments cũ từ database (vì không cào lại comments)
    if existing_comments:
        combined_comments = " ".join([c for c in existing_comments if c]).strip()
        if len(combined_comments) > 10:
            try:
                langs = detect_langs(combined_comments)
                top_lang = langs[0]
                if top_lang.lang in ['vi', 'en']:
                    return top_lang.lang
            except LangDetectException:
                pass
    
    return "unknown"

def main():
    print("🚀 Bắt đầu tiến trình cào lại STATS (Bỏ qua bình luận)...")
    
    video_list = get_all_video_links()
    total = len(video_list)
    print(f"📊 Tìm thấy {total} video cần cập nhật.")

    if total == 0:
        print("Done!")
        return

    driver = init_driver()
    
    processed = 0
    deleted_dead = 0
    deleted_lang = 0
    updated = 0

    try:
        for item in video_list:
            video_id = item['video_id']
            link = item['link']
            processed += 1
            
            print(f"\n[{processed}/{total}] Đang xử lý: {link}")

            try:
                driver.get(link)
                time.sleep(random.uniform(2.5, 4.0)) # Giảm thời gian chờ vì không cần load comment
                
                if "video-not-found" in driver.current_url or "404" in driver.title:
                    print(f"  [❌] Video không tồn tại.")
                    delete_video(video_id)
                    deleted_dead += 1
                    continue

                html = driver.page_source
                stats = extract_basic_stats(html)
                
                if stats['Views'] == 0 and stats['Likes'] == 0:
                    if "Video này không có sẵn" in html or "This video is unavailable" in html:
                        print(f"  [❌] Video không có sẵn.")
                        delete_video(video_id)
                        deleted_dead += 1
                        continue
                    else:
                        print(f"  [⚠️] Không tìm thấy stats. Có thể bị chặn. Bỏ qua.")
                        continue

                # Lọc ngôn ngữ sử dụng caption mới và comments cũ từ DB
                existing_comments = [
                    item.get('top1_cmt'), item.get('top2_cmt'), 
                    item.get('top3_cmt'), item.get('top4_cmt'), item.get('top5_cmt')
                ]
                lang = detect_language_robust(stats['Caption'], existing_comments)
                print(f"  [🌐] Ngôn ngữ: {lang}")

                if lang not in ['vi', 'en']:
                    print(f"  [✂️] Xóa video ngoại ngữ: {lang}")
                    delete_video(video_id)
                    deleted_lang += 1
                    continue

                # Cập nhật STATS ngay lập tức
                data_dict = {
                    'caption': stats['Caption'],
                    'views': stats['Views'],
                    'likes': stats['Likes'],
                    'comments': stats['Comments'],
                    'shares': stats['Shares'],
                    'saves': stats['Saves'],
                    'create_time': stats['Create_Time'],
                    'scrape_date': datetime.now().date().isoformat()
                }

                if update_rescraped_stats_only(video_id, data_dict):
                    print(f"  [✅] Đã cập nhật STATS thành công.")
                    updated += 1
                
                # Nghỉ ngắn hơn vì chỉ cào stats (ít bị nghi ngờ hơn)
                wait_time = random.uniform(4, 10)
                time.sleep(wait_time)

            except Exception as e:
                print(f"  [🔥] Lỗi: {e}")
                continue

    finally:
        print("\n" + "="*50)
        print("🏁 HOÀN THÀNH CẬP NHẬT STATS")
        print(f"   - Tổng duyệt: {processed}")
        print(f"   - Cập nhật thành công: {updated}")
        print(f"   - Xóa chết/ngôn ngữ: {deleted_dead + deleted_lang}")
        print("="*50)
        driver.quit()

if __name__ == "__main__":
    main()
