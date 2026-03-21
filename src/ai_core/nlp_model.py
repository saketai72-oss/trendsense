import pandas as pd
import re
import os
import sys
import ast  
from transformers import pipeline
import time
import math

# Khai báo cho Python biết thư mục gốc ở đâu để import file settings
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from config import settings

# ==========================================
# PHẦN 1: CẤU HÌNH ĐƯỜNG DẪN TỪ SETTINGS
# ==========================================
# Nhận đường dẫn trực tiếp từ Trạm điều phối trung tâm
INPUT_FILE = settings.RAW_FILE 
OUTPUT_FILE = settings.PROCESSED_FILE

# ==========================================
# PHẦN 2: KHỞI TẠO MÔ HÌNH AI & HÀM BỔ TRỢ
# ==========================================
print("[*] Đang tải 'khối óc' AI NLP (bert-base-multilingual)...")
nlp_model = pipeline("sentiment-analysis", model="nlptown/bert-base-multilingual-uncased-sentiment")

def clean_text(text):
    if pd.isna(text): 
        return ""
    text = str(text).lower()
    text = re.sub(r'http\S+', '', text)
    text = re.sub(r'[^\w\s\u0102-\u1EF9]', ' ', text) 
    return text.strip()

def get_sentiment(text):
    if not text:
        return "Neutral", 3 
    try:
        result = nlp_model(text[:512])[0]
        stars = int(result['label'].split()[0]) 
        if stars >= 4: return "Positive", stars 
        elif stars <= 2: return "Negative", stars 
        else: return "Neutral", stars  
    except Exception:
        return "Neutral", 3

# ==========================================
# PHẦN 3: TIỀN XỬ LÝ (DATA CLEANING) & AI CHẤM ĐIỂM
# ==========================================
print(f"\n[*] Đang đọc Hồ dữ liệu Raw tại: {INPUT_FILE}")
try:
    df_raw = pd.read_csv(INPUT_FILE, low_memory=False)
except FileNotFoundError:
    print("[!] LỖI: Không tìm thấy file Raw. Hãy chạy apify_bot.py trước!")
    exit()

clean_data_list = []
print(f"[*] Bắt đầu dọn rác và dùng AI phân tích {len(df_raw)} video...")

for index, row in df_raw.iterrows():
    # 1. RÚT TRÍCH CHỈ SỐ CƠ BẢN TỪ FILE RAW
    views = pd.to_numeric(row.get('playCount', 0), errors='coerce')
    likes = pd.to_numeric(row.get('diggCount', 0), errors='coerce')
    comments = pd.to_numeric(row.get('commentCount', 0), errors='coerce')
    shares = pd.to_numeric(row.get('shareCount', 0), errors='coerce')
    saves = pd.to_numeric(row.get('collectCount', 0), errors='coerce')
    
    # --- TÍNH TỐC ĐỘ TĂNG TRƯỞNG (HEURISTIC) ---
    create_time = pd.to_numeric(row.get('createTime', 0), errors='coerce')
    current_time = int(time.time()) 
    
    views_per_hour = 0
    if create_time > 0:
        age_seconds = current_time - create_time
        age_hours = age_seconds / 3600
        if age_hours <= 0: age_hours = 0.1 
        views_per_hour = round(views / age_hours, 2)

    # Tính Trend Score
    trend_score = 0
    if views >= 5000:
        engagement_points = (likes * 1) + (comments * 2) + (saves * 3) + (shares * 4)
        base_rate = (engagement_points / views) * 100
        # Nhân hệ số khuếch đại bằng Logarit để thưởng cho view to
        trend_score = round(base_rate * math.log10(views), 2)
    else:
        trend_score = 0 
        
    clean_row = {
        'Link': row.get('Link', ""),
        'Caption': row.get('text', ""),
        'Views': views,
        'Likes': likes,
        'Comments': comments,
        'Shares': shares,
        'Saves': saves,
        'Views_Per_Hour': views_per_hour,
        'Trend_Score': trend_score
    }

    # 2. RÚT TRÍCH 10 COMMENT TỪ CỤC JSON
    raw_comments_str = row.get('comments', '[]')
    top_10_texts = []
    
    if pd.notna(raw_comments_str) and isinstance(raw_comments_str, str) and raw_comments_str != '[]':
        try:
            comments_list = ast.literal_eval(raw_comments_str)
            if isinstance(comments_list, list):
                sorted_cmts = sorted(comments_list, key=lambda x: x.get('diggCount', 0), reverse=True)
                top_10_texts = [c.get('text', '') for c in sorted_cmts[:10]]
        except Exception:
            pass

    while len(top_10_texts) < 10:
        top_10_texts.append("")

    # 3. AI BẮT ĐẦU ĐỌC VÀ CHẤM ĐIỂM (CHỈ ĐỌC COMMENT)
    total_stars = 0
    valid_comments = 0
    
    for i in range(10):
        val = str(top_10_texts[i]).strip()
        clean_row[f'Top{i+1}_Cmt'] = val
        
        if val != "" and val.lower() != "nan":
            cleaned_cmt = clean_text(val)
            if cleaned_cmt:
                _, stars = get_sentiment(cleaned_cmt)
                total_stars += stars
                valid_comments += 1
                
    # 4. TỔNG HỢP ĐIỂM 
    if valid_comments > 0:
        avg_stars = total_stars / valid_comments
        clean_row['Positive_Score'] = round((avg_stars / 5) * 100, 2) 
        
        if avg_stars >= 3.5: 
            clean_row['Video_Sentiment'] = "🟢 TÍCH CỰC"
        elif avg_stars <= 2.5: 
            clean_row['Video_Sentiment'] = "🔴 TIÊU CỰC / TRANH CÃI"
        else: 
            clean_row['Video_Sentiment'] = "🟡 TRUNG LẬP"
    else:
        clean_row['Positive_Score'] = 0
        clean_row['Video_Sentiment'] = "⚪ KHÔNG CÓ BÌNH LUẬN"
        
    clean_data_list.append(clean_row)

# ==========================================
# PHẦN 4: LƯU VÀO KHO DỮ LIỆU CHÍN (PROCESSED)
# ==========================================
df_clean = pd.DataFrame(clean_data_list)
df_clean.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')

print(f"\n[*] XONG! Đã dọn dẹp và phân tích thành công.")
print(f"[*] Dữ liệu chín đã sẵn sàng cho Dashboard tại: \n[*] {OUTPUT_FILE}")