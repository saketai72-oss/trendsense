import re
import time
import random
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from utils import parse_like_count
from captcha import solve_rotate_captcha

def get_real_stat(pattern, text):
    matches = re.findall(pattern, text)
    if not matches: return "0"
    numbers = [int(m) for m in matches if str(m).isdigit()]
    return str(max(numbers)) if numbers else "0"

def extract_basic_stats(html):
    caption = "Không tìm thấy"
    try:
        start = html.find('"desc":"') + len('"desc":"')
        end = html.find('","createTime"', start)
        caption = html[start:end]
    except: pass

    return {
        'Caption': caption,
        'Views': parse_like_count(get_real_stat(r'"playCount"\s*:\s*"?(\d+)"?', html)),
        'Likes': parse_like_count(get_real_stat(r'"diggCount"\s*:\s*"?(\d+)"?', html)),
        'Comments': parse_like_count(get_real_stat(r'"commentCount"\s*:\s*"?(\d+)"?', html)),
        'Shares': parse_like_count(get_real_stat(r'"shareCount"\s*:\s*"?(\d+)"?', html)),
        'Saves': parse_like_count(get_real_stat(r'"collectCount"\s*:\s*"?(\d+)"?', html)),
        'Create_Time': get_real_stat(r'"createTime"\s*:\s*"?(\d+)"?', html)
    }

def extract_top_comments(driver, has_comments_to_load):
    try:
        comment_btn = driver.find_element(By.CSS_SELECTOR, "[data-e2e='comment-icon']")
        ActionChains(driver).move_to_element(comment_btn).perform()
        time.sleep(random.uniform(0.8, 2.5)) 
        driver.execute_script("arguments[0].click();", comment_btn)
        time.sleep(random.uniform(2.0, 4.0)) 
    except: pass

    print("  [*] Đang tải bình luận...")
    comments_loaded = False
    for _ in range(7):
        time.sleep(1)
        if driver.find_elements(By.CSS_SELECTOR, "[data-e2e='comment-level-1']"):
            comments_loaded = True
            break
            
    if not comments_loaded and has_comments_to_load: 
        print("  [!] Đụng Captcha Xoay Hình...")
        solve_rotate_captcha(driver)
        
        # --- THÊM ĐOẠN NÀY ĐỂ ÉP ĐỢI ---
        print("  [*] Giải xong! Đang chờ TikTok duyệt và tải bình luận...")
        time.sleep(5) # Bắt buộc phải cho nó 5 giây để load comment ra màn hình
        
        # Kiểm tra lại xem comment đã thực sự hiện ra chưa
        if not driver.find_elements(By.CSS_SELECTOR, "[data-e2e='comment-level-1']"):
            print("  [!] TikTok vẫn chặn hoặc mạng lỗi, bỏ qua video này.")
            return [] # Trả về list rỗng, không cào nữa

    for _ in range(4): 
        current_comments = driver.find_elements(By.CSS_SELECTOR, "[data-e2e='comment-level-1']")
        if current_comments:
            try:
                driver.execute_script("arguments[0].scrollIntoView(true);", current_comments[-1])
                time.sleep(random.uniform(1.2, 3.1)) 
            except: break

    comments_data = []
    try:
        for cmt in driver.find_elements(By.CSS_SELECTOR, "[data-e2e='comment-level-1']"):
            c_text = cmt.text
            if not c_text.strip(): continue 

            c_like_num = 0
            try:
                wrapper = cmt.find_element(By.XPATH, "../../..")
                lines = wrapper.text.split('\n')
                for line in reversed(lines[-3:]):
                    num = parse_like_count(line)
                    if num > 0:
                        c_like_num = num
                        break
                comments_data.append({"text": c_text.replace('\n', ' '), "likes_num": c_like_num})
            except: pass
    except: pass
        
    comments_data.sort(key=lambda x: x["likes_num"], reverse=True)
    
    unique_comments = []
    seen_texts = set()
    for item in comments_data:
        if item["text"] not in seen_texts:
            unique_comments.append(item)
            seen_texts.add(item["text"])
            
    top_5 = unique_comments[:5]
    print(f"  [>] Kết quả: Thu hoạch được {len(top_5)} bình luận hợp lệ.")
    return top_5