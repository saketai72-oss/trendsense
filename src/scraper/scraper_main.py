import sys
import os
import time

from browser import init_driver
from database import init_db, extract_video_id, mark_as_scraped
from csv_handler import save_to_csv
from link_crawler import get_trending_links
from content_parser import extract_basic_stats, extract_top_comments

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from config import settings

CSV_FILE = settings.RAW_FILE

def main():
    init_db()
    driver = init_driver()
    driver.get("https://www.tiktok.com/explore")

    print("👉 Đang tải TikTok với Profile đã lưu...")
    time.sleep(8)

    # 1. Tìm danh sách link
    links = get_trending_links(driver, target_count=30)
    
    print("\n===== BẮT ĐẦU CÀO DỮ LIỆU =====\n")
    all_scraped_data = []

    # 2. Xử lý từng link
    for i, link in enumerate(links, 1):
        print(f"\n[{i}/{len(links)}] Đang cào: {link}")
        driver.get(link)
        time.sleep(4)

        # Bóc tách các chỉ số cơ bản
        stats = extract_basic_stats(driver.page_source)
        
        # Bóc tách Top 5 bình luận
        has_comments = stats['Comments'] > 0
        top_5_comments = extract_top_comments(driver, has_comments)

        # 3. Đóng gói dữ liệu
        video_id = extract_video_id(link)
        if video_id:
            mark_as_scraped(video_id)
            print(f"  [*] Đã cất ID {video_id} vào kho chống trùng.")
            
            row_data = {
                'Link': link,
                'Create_Time': stats['Create_Time'],
                'Caption': stats['Caption'],
                'Views': stats['Views'],   
                'Likes': stats['Likes'],
                'Comments': stats['Comments'],
                'Shares': stats['Shares'],
                'Saves': stats['Saves']    
            }
            
            for idx in range(5):
                if idx < len(top_5_comments):
                    row_data[f'Top{idx+1}_Cmt'] = top_5_comments[idx]['text']
                    row_data[f'Top{idx+1}_Likes'] = top_5_comments[idx]['likes_num']
                else:
                    row_data[f'Top{idx+1}_Cmt'] = ""
                    row_data[f'Top{idx+1}_Likes'] = 0
                    
            all_scraped_data.append(row_data)
            print(f"  [*] Đã gom video {video_id} vào danh sách chờ.")
    
    # 4. Lưu và dọn dẹp
    driver.quit()
    save_to_csv(all_scraped_data, CSV_FILE)
    print("\n[+] ĐÃ XONG MẺ CÀO NÀY!")

if __name__ == "__main__":
    main()