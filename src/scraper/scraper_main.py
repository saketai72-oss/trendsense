import os
import sys
import re
import time
import random
import csv
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from browser import init_driver
from utils import parse_like_count
from captcha import solve_rotate_captcha
# Gọi bộ công cụ database mới vào
from database import init_db, is_scraped, mark_as_scraped, extract_video_id

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from config import settings

CSV_FILE = settings.RAW_FILE

def main():
    # 1. KHỞI ĐỘNG DATABASE
    init_db()
    
    driver = init_driver()
    driver.get("https://www.tiktok.com/explore")

    print("👉 Đang tải TikTok với Profile đã lưu...")
    time.sleep(8)

    # 2. CUỘN TÌM LINK MỚI 
    number_of_videos = 30
    links = []
    scroll_attempts = 0
    print(f"[*] Lướt tìm {number_of_videos} video mới toanh...")
    
    while len(links) < number_of_videos and scroll_attempts < number_of_videos :
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        videos = driver.find_elements(By.CSS_SELECTOR, "a[href*='/video/']")
        for v in videos:
            raw_link = v.get_attribute("href")
            video_id = extract_video_id(raw_link)
            
            # Chỉ nạp link nếu ID hợp lệ, CHƯA có trong Database, và chưa nằm trong list chờ
            if video_id and not is_scraped(video_id):
                clean_link = raw_link.split('?')[0]
                if clean_link not in links:
                    links.append(clean_link)
                    print(f"  + Đã chốt được video mới ({len(links)}/{number_of_videos}) - ID: {video_id}")
                    
            if len(links) == number_of_videos: 
                break
        scroll_attempts += 1

    print("\n===== BẮT ĐẦU CÀO DỮ LIỆU =====\n")

    # 3. VÀO TỪNG LINK ĐỂ CÀO
    for i, link in enumerate(links, 1):
        print(f"\n[{i}/{len(links)}] Đang cào: {link}")
        driver.get(link)
        time.sleep(4)

        html = driver.page_source
        
        # 1. Bóc Caption (Vẫn dùng cách cũ vì text có nhiều ký tự đặc biệt)
        caption = "Không tìm thấy"
        try:
            start = html.find('"desc":"') + len('"desc":"')
            end = html.find('","createTime"', start)
            caption = html[start:end]
        except: pass

        # 2. Dùng hàm Regex để moi CHÍNH XÁC dãy số của tất cả các chỉ số
        def get_real_stat(pattern, text):
            # re.findall sẽ lôi cổ TẤT CẢ các con số khớp với từ khóa ra khỏi HTML
            matches = re.findall(pattern, text)
            if not matches: 
                return "0"
            
            # Ép tất cả thành số nguyên và chọn thằng To Nhất (chính là số liệu thật)
            numbers = [int(m) for m in matches if str(m).isdigit()]
            return str(max(numbers)) if numbers else "0"

        # Regex được nâng cấp để bắt được cả trường hợp TikTok bọc ngoặc kép quanh số
        view = get_real_stat(r'"playCount"\s*:\s*"?(\d+)"?', html)
        like = get_real_stat(r'"diggCount"\s*:\s*"?(\d+)"?', html)
        comment = get_real_stat(r'"commentCount"\s*:\s*"?(\d+)"?', html)
        share = get_real_stat(r'"shareCount"\s*:\s*"?(\d+)"?', html)
        save = get_real_stat(r'"collectCount"\s*:\s*"?(\d+)"?', html)

        create_time = get_real_stat(r'"createTime"\s*:\s*"?(\d+)"?', html)
        
        # Mở Comment
        try:
            comment_btn = driver.find_element(By.CSS_SELECTOR, "[data-e2e='comment-icon']")
            ActionChains(driver).move_to_element(comment_btn).perform()
            time.sleep(random.uniform(0.8, 2.5)) 
            driver.execute_script("arguments[0].click();", comment_btn)
            time.sleep(random.uniform(2.0, 4.0)) 
        except: pass

        print("  [*] Đang tải bình luận...")
        
        # Chờ comment load / Check Captcha
        comments_loaded = False
        for _ in range(7):
            time.sleep(1)
            if driver.find_elements(By.CSS_SELECTOR, "[data-e2e='comment-level-1']"):
                comments_loaded = True
                break
                
        # Gọi module giải Captcha nếu cần
        if not comments_loaded and comment != "0": 
            print("  [!] Đụng Captcha Xoay Hình...")
            solve_rotate_captcha(driver)
            # Sau khi giải xong, ép nó check lại comment để đi tiếp
            
        # Cuộn comment
        for _ in range(4): 
            current_comments = driver.find_elements(By.CSS_SELECTOR, "[data-e2e='comment-level-1']")
            if current_comments:
                try:
                    driver.execute_script("arguments[0].scrollIntoView(true);", current_comments[-1])
                    time.sleep(random.uniform(1.2, 3.1)) 
                except: break

        # Gom Text
        comments_data = []
        try:
            for cmt in driver.find_elements(By.CSS_SELECTOR, "[data-e2e='comment-level-1']"):
                c_text = cmt.text
                if not c_text.strip(): continue 

                c_like_str, c_like_num = "0", 0
                try:
                    wrapper = cmt.find_element(By.XPATH, "../../..")
                    lines = wrapper.text.split('\n')
                    for line in reversed(lines[-3:]):
                        num = parse_like_count(line)
                        if num > 0:
                            c_like_num = num
                            c_like_str = line
                            break
                    comments_data.append({"text": c_text.replace('\n', ' '), "likes_num": c_like_num})
                except: pass
        except: pass
            
        comments_data.sort(key=lambda x: x["likes_num"], reverse=True)
        
        # Lọc trùng
        unique_comments = []
        seen_texts = set()
        for item in comments_data:
            if item["text"] not in seen_texts:
                unique_comments.append(item)
                seen_texts.add(item["text"])
                
        top_5_comments = unique_comments[:5]

        # 4. CHỐT HẠ: CÀO THÀNH CÔNG THÌ LƯU VÀO DATABASE
        video_id = extract_video_id(link)
        if video_id:
            mark_as_scraped(video_id)
            print(f"  [*] Đã cất ID {video_id} vào kho dữ liệu chống trùng.")
            
# --- LƯU KẾT QUẢ VÀO FILE CSV ---
        file_exists = os.path.isfile(CSV_FILE)
        
        with open(CSV_FILE, mode='a', newline='', encoding='utf-8') as f:
            # SỬA LẠI HEADERS CHUẨN XÁC THEO YÊU CẦU CỦA AI
            headers = ['Link', 'Create_Time', 'Caption', 'Views', 'Likes', 'Comments', 'Shares', 'Saves', 
                       'Top1_Cmt', 'Top1_Likes', 'Top2_Cmt', 'Top2_Likes', 
                       'Top3_Cmt', 'Top3_Likes', 'Top4_Cmt', 'Top4_Likes', 
                       'Top5_Cmt', 'Top5_Likes']
            writer = csv.DictWriter(f, fieldnames=headers)
            
            if not file_exists:
                writer.writeheader()
                
            # NHÉT VIEW VÀ SAVE VÀO ROW DATA
            row_data = {
                'Link': link,
                'Create_Time': create_time,
                'Caption': caption,
                'Views': parse_like_count(view),   
                'Likes': parse_like_count(like),
                'Comments': parse_like_count(comment),
                'Shares': parse_like_count(share),
                'Saves': parse_like_count(save)    
            }
            
            for idx in range(5):
                if idx < len(top_5_comments):
                    row_data[f'Top{idx+1}_Cmt'] = top_5_comments[idx]['text']
                    row_data[f'Top{idx+1}_Likes'] = top_5_comments[idx]['likes_num']
                else:
                    row_data[f'Top{idx+1}_Cmt'] = ""
                    row_data[f'Top{idx+1}_Likes'] = 0
                    
            writer.writerow(row_data)
        print(f"  [*] Đã ghi dữ liệu vào file {CSV_FILE}")
        
    driver.quit()
    print("\n[+] ĐÃ XONG MẺ CÀO NÀY!")

if __name__ == "__main__":
    main()