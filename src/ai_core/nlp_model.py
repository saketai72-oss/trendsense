import pandas as pd
import re
import os
import sys
import time
import math
from transformers import pipeline

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from config import settings

INPUT_FILE = settings.RAW_FILE 
OUTPUT_FILE = settings.PROCESSED_FILE

print("[*] Đang tải mô hình NLP (bert-base-multilingual)...")
nlp_model = pipeline("sentiment-analysis", model="nlptown/bert-base-multilingual-uncased-sentiment", device=-1)

def clean_text(text):
    if not isinstance(text, str) or pd.isna(text): return ""
    text = text.lower()
    text = re.sub(r'http\S+', '', text)
    text = re.sub(r'[^\w\s\u0102-\u1EF9]', ' ', text) 
    return text.strip()

def process_data():
    print(f"\n[*] Đang đọc dữ liệu tại: {INPUT_FILE}")
    try:
        df_raw = pd.read_csv(INPUT_FILE, low_memory=False)
    except FileNotFoundError:
        print("[!] LỖI: Không tìm thấy file Raw.")
        return
    except pd.errors.EmptyDataError:
        print("[!] LỖI: File Raw đang trống rỗng.")
        return

    clean_data_list = []
    comments_to_analyze = []
    comment_tracker = [] # Lưu vị trí: (row_index, comment_index)

    print(f"[*] Bắt đầu dọn rác và gom dữ liệu của {len(df_raw)} video...")

    for row in df_raw.itertuples():
        # Cập nhật TÊN CỘT CHUẨN XÁC theo file csv do Selenium tạo ra
        views = pd.to_numeric(getattr(row, 'Views', 0), errors='coerce')
        if pd.isna(views): views = 0
        likes = pd.to_numeric(getattr(row, 'Likes', 0), errors='coerce')
        if pd.isna(likes): likes = 0
        comments = pd.to_numeric(getattr(row, 'Comments', 0), errors='coerce')
        if pd.isna(comments): comments = 0
        shares = pd.to_numeric(getattr(row, 'Shares', 0), errors='coerce')
        if pd.isna(shares): shares = 0
        saves = pd.to_numeric(getattr(row, 'Saves', 0), errors='coerce')
        if pd.isna(saves): saves = 0
        
        saves = pd.to_numeric(getattr(row, 'Saves', 0), errors='coerce')
        if pd.isna(saves): saves = 0
        
        # LẤY THỜI GIAN ĐĂNG VÀ TÍNH TỐC ĐỘ TĂNG TRƯỞNG
        create_time = pd.to_numeric(getattr(row, 'Create_Time', 0), errors='coerce')
        if pd.isna(create_time): create_time = 0
        
        current_time = int(time.time())
        age_hours = max((current_time - create_time) / 3600, 0.1) if create_time > 0 else 0.1
        views_per_hour = round(views / age_hours, 2)

        trend_score = 0
        if views >= 5000:
            engagement_points = likes + (comments * 2) + (saves * 3) + (shares * 4)
            base_rate = (engagement_points / views) * 100
            trend_score = round(base_rate * math.log10(views), 2)

        clean_row = {
            'Link': getattr(row, 'Link', ""),
            'Caption': getattr(row, 'Caption', ""),
            'Views': views, 'Likes': likes, 'Comments': comments,
            'Shares': shares, 'Saves': saves,
            'Views_Per_Hour': views_per_hour, 'Trend_Score': trend_score,
            'Total_Stars': 0, 'Valid_Comments': 0
        }

        # Đọc trực tiếp từ 5 cột comment (Top1_Cmt -> Top5_Cmt) thay vì giải mã JSON
        for i in range(1, 6):
            raw_cmt = getattr(row, f'Top{i}_Cmt', "")
            raw_likes = getattr(row, f'Top{i}_Likes', 0)
            
            txt = clean_text(str(raw_cmt)) if pd.notna(raw_cmt) else ""
            
            # Lưu lại vào data sạch
            clean_row[f'Top{i}_Cmt'] = txt
            clean_row[f'Top{i}_Likes'] = raw_likes if pd.notna(raw_likes) else 0
            
            # Đẩy text vào mảng chờ AI xử lý
            if txt and txt.lower() != "nan":
                comments_to_analyze.append(txt[:512]) 
                comment_tracker.append((len(clean_data_list), i))
            
        clean_data_list.append(clean_row)

    print(f"[*] AI đang chấm điểm {len(comments_to_analyze)} bình luận cùng lúc...")
    
    if comments_to_analyze:
        ai_results = nlp_model(comments_to_analyze, batch_size=32, truncation=True)
        
        for (row_idx, cmt_idx), res in zip(comment_tracker, ai_results):
            stars = int(res['label'].split()[0])
            clean_data_list[row_idx]['Total_Stars'] += stars
            clean_data_list[row_idx]['Valid_Comments'] += 1

    for row in clean_data_list:
        if row['Valid_Comments'] > 0:
            avg_stars = row['Total_Stars'] / row['Valid_Comments']
            row['Positive_Score'] = round((avg_stars / 5) * 100, 2) 
            
            if avg_stars >= 3.5: row['Video_Sentiment'] = "🟢 TÍCH CỰC"
            elif avg_stars <= 2.5: row['Video_Sentiment'] = "🔴 TIÊU CỰC"
            else: row['Video_Sentiment'] = "🟡 TRUNG LẬP"
        else:
            row['Positive_Score'] = 0
            row['Video_Sentiment'] = "⚪ KHÔNG CÓ BÌNH LUẬN"
            
        del row['Total_Stars']
        del row['Valid_Comments']

    df_clean = pd.DataFrame(clean_data_list)
    df_clean.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
    print(f"[*] XONG! Dữ liệu đã lưu tại: {OUTPUT_FILE}")

if __name__ == "__main__":
    process_data()