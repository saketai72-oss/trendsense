import sys
import os

# Thêm đường dẫn gốc trước khi import local modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import time
from datetime import datetime

try:
    from langdetect import detect, LangDetectException
except ImportError:
    print("[!] Thiếu thư viện langdetect. Hãy chạy: pip install langdetect")
    sys.exit(1)

from config import settings
from src.scraper.browser import init_driver
from src.scraper.database import init_db, extract_video_id, mark_as_scraped, insert_video_metadata
from src.scraper.link_crawler import get_trending_links
from src.scraper.content_parser import extract_basic_stats, extract_top_comments



def main():
    init_db()
    driver = init_driver()
    driver.get("https://www.tiktok.com/explore")

    print("👉 Đang tải TikTok với Profile đã lưu...")
    time.sleep(8)

    # 1. Tìm danh sách link
    links = get_trending_links(driver, target_count=settings.MAX_VIDEOS)

    print("\n===== BẮT ĐẦU THU THẬP DỮ LIỆU =====\n")
    today = datetime.now().date().isoformat()
    saved_count = 0

    # 2. Xử lý từng link
    for i, link in enumerate(links, 1):
        print(f"\n[{i}/{len(links)}] Đang cào: {link}")
        driver.get(link)
        time.sleep(4)

        # Bóc tách các chỉ số cơ bản
        stats = extract_basic_stats(driver.page_source)

        # Chốt chặn ngôn ngữ: Chỉ lấy video Tiếng Việt
        caption_text = stats.get('Caption', '').strip()
        if caption_text:
            try:
                # Kiểm tra ngôn ngữ của caption
                lang = detect(caption_text)
                if lang != 'vi':
                    print(f"  [✂️] Bỏ qua video quốc tế (Ngôn ngữ: {lang}).")
                    
                    # Vẫn đánh dấu là đã cào để không bị lặp lại lần sau
                    video_id = extract_video_id(link)
                    if video_id:
                        mark_as_scraped(video_id)
                    continue
            except LangDetectException:
                # Nếu caption chỉ toàn emoji hoặc số (không detect được)
                pass

        # Bóc tách Top 5 bình luận
        has_comments = stats['Comments'] > 0
        top_5_comments = extract_top_comments(driver, has_comments)

        # 3. Đóng gói dữ liệu và ghi vào Postgres
        video_id = extract_video_id(link)
        if video_id:
            mark_as_scraped(video_id)
            print(f"  [*] Đã cất ID {video_id} vào kho chống trùng.")

            # Chuẩn bị data cho database
            video_data = {
                'link': link,
                'create_time': stats['Create_Time'],
                'caption': stats['Caption'],
                'views': stats['Views'],
                'likes': stats['Likes'],
                'comments': stats['Comments'],
                'shares': stats['Shares'],
                'saves': stats['Saves'],
                'scrape_date': today,
            }

            # Gắn top comments
            for idx in range(5):
                if idx < len(top_5_comments):
                    video_data[f'top{idx+1}_cmt'] = top_5_comments[idx]['text']
                    video_data[f'top{idx+1}_likes'] = top_5_comments[idx]['likes_num']
                else:
                    video_data[f'top{idx+1}_cmt'] = ""
                    video_data[f'top{idx+1}_likes'] = 0

            # Ghi vào PostgreSQL
            insert_video_metadata(video_id, video_data)
            saved_count += 1
            print(f"  [✓] Đã lưu metadata video {video_id} vào DB.")


    # 4. Dọn dẹp
    print("\n[*] Đang đóng trình duyệt...")
    try:
        driver.quit()
    except Exception as e:
        # Lỗi handle invalid trên Windows thường không gây hại, ta có thể bỏ qua
        pass

    if saved_count == 0 and len(links) > 0:
        print("[!] CẢNH BÁO: Tìm thấy link nhưng không lưu được video nào. Có thể do bị trùng ID hoàn toàn trong DB.")
    
    print(f"\n[+] ĐÃ XONG MẺ CÀO NÀY! Lưu {saved_count} video vào database.")


if __name__ == "__main__":
    main()