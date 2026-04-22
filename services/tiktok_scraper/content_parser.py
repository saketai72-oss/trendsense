import re
import json
import time
import random
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from services.tiktok_scraper.utils import parse_like_count
from services.tiktok_scraper.captcha import solve_rotate_captcha


def _extract_video_json(html):
    """
    Trích xuất dữ liệu JSON nhúng từ HTML TikTok.
    TikTok luôn nhúng toàn bộ data vào thẻ script đặc biệt.
    Trả về dict chứa thông tin video chính xác (không bị lẫn video khác).
    """
    # Phương pháp 1: __UNIVERSAL_DATA_FOR_REHYDRATION__ (TikTok hiện tại)
    pattern = r'<script\s+id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>'
    match = re.search(pattern, html, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            scope = data.get("__DEFAULT_SCOPE__", {})

            # Đường dẫn đến video detail trong JSON
            video_detail = scope.get("webapp.video-detail", {})
            item_info = video_detail.get("itemInfo", {})
            item = item_info.get("itemStruct", {})

            if item and item.get("id"):
                return item
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

    # Phương pháp 2: SIGI_STATE (TikTok cũ / fallback)
    pattern2 = r'<script\s+id="SIGI_STATE"[^>]*>(.*?)</script>'
    match2 = re.search(pattern2, html, re.DOTALL)
    if match2:
        try:
            data = json.loads(match2.group(1))
            # Trong SIGI_STATE, video data nằm ở ItemModule
            item_module = data.get("ItemModule", {})
            if item_module:
                # Lấy video đầu tiên (video chính đang xem)
                for vid_id, item in item_module.items():
                    if isinstance(item, dict) and item.get("id"):
                        return item
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

    return None


def _safe_int(value, default=0):
    """Chuyển đổi an toàn sang int"""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def extract_basic_stats(html):
    """
    Bóc tách stats video từ HTML TikTok.
    ƯU TIÊN: Parse JSON nhúng (chính xác, chỉ lấy data video đang xem).
    FALLBACK: Regex trên JSON block của video chính (không dùng max toàn trang nữa).
    """
    # === PHƯƠNG PHÁP CHÍNH: Parse JSON nhúng ===
    item = _extract_video_json(html)
    if item:
        stats = item.get("stats", {})
        return {
            'Caption': item.get("desc", "Không tìm thấy"),
            'Views': _safe_int(stats.get("playCount", 0)),
            'Likes': _safe_int(stats.get("diggCount", 0)),
            'Comments': _safe_int(stats.get("commentCount", 0)),
            'Shares': _safe_int(stats.get("shareCount", 0)),
            'Saves': _safe_int(stats.get("collectCount", 0)),
            'Create_Time': str(_safe_int(item.get("createTime", 0))),
        }

    # === FALLBACK: Regex nhưng chỉ trên block JSON đầu tiên ===
    print("  [!] Không parse được JSON nhúng, dùng fallback regex (giới hạn block đầu tiên)...")
    return _extract_stats_regex_safe(html)


def _extract_stats_regex_safe(html):
    """
    Fallback: Dùng regex nhưng AN TOÀN hơn cách cũ.
    Thay vì findall + max toàn trang, chỉ lấy GIÁ TRỊ ĐẦU TIÊN tìm thấy.
    Giá trị đầu tiên trong HTML thường là video chính (server render).
    """
    def get_first_match(pattern, text):
        """Lấy giá trị ĐẦU TIÊN khớp pattern (không phải max)"""
        match = re.search(pattern, text)
        if match:
            try:
                return str(int(match.group(1)))
            except (ValueError, IndexError):
                pass
        return "0"

    caption = "Không tìm thấy"
    try:
        start = html.find('"desc":"') + len('"desc":"')
        end = html.find('","createTime"', start)
        if start > 7 and end > start:
            caption = html[start:end]
    except:
        pass

    return {
        'Caption': caption,
        'Views': _safe_int(get_first_match(r'"playCount"\s*:\s*"?(\d+)"?', html)),
        'Likes': _safe_int(get_first_match(r'"diggCount"\s*:\s*"?(\d+)"?', html)),
        'Comments': _safe_int(get_first_match(r'"commentCount"\s*:\s*"?(\d+)"?', html)),
        'Shares': _safe_int(get_first_match(r'"shareCount"\s*:\s*"?(\d+)"?', html)),
        'Saves': _safe_int(get_first_match(r'"collectCount"\s*:\s*"?(\d+)"?', html)),
        'Create_Time': get_first_match(r'"createTime"\s*:\s*"?(\d+)"?', html),
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
