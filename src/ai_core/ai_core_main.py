import pandas as pd
import os
import sys
from collections import Counter

# Nạp config từ thư mục gốc của bạn
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from config import settings

# Nạp các module tự viết
from math_utils import calculate_metrics
from nlp_utils import clean_text, extract_keywords
from sentiment_engine import analyze_batch
from prediction_engine import run_viral_prediction

INPUT_FILE = settings.RAW_FILE 
OUTPUT_FILE = settings.PROCESSED_FILE

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
    comment_tracker = [] 
    global_word_counter = Counter()

    print(f"[*] Bắt đầu dọn rác và phân tích dữ liệu của {len(df_raw)} video...")

    for row in df_raw.itertuples():
        views = pd.to_numeric(getattr(row, 'Views', 0), errors='coerce')
        likes = pd.to_numeric(getattr(row, 'Likes', 0), errors='coerce')
        comments = pd.to_numeric(getattr(row, 'Comments', 0), errors='coerce')
        shares = pd.to_numeric(getattr(row, 'Shares', 0), errors='coerce')
        saves = pd.to_numeric(getattr(row, 'Saves', 0), errors='coerce')
        create_time = pd.to_numeric(getattr(row, 'Create_Time', 0), errors='coerce')
        
        # Gọi hàm tính toán
        views_per_hour, engagement_rate, viral_velocity = calculate_metrics(
            views=0 if pd.isna(views) else views,
            likes=0 if pd.isna(likes) else likes,
            comments=0 if pd.isna(comments) else comments,
            shares=0 if pd.isna(shares) else shares,
            saves=0 if pd.isna(saves) else saves,
            create_time=0 if pd.isna(create_time) else create_time
        )

        clean_row = {
            'Link': getattr(row, 'Link', ""),
            'Caption': getattr(row, 'Caption', ""),
            'Views': views, 'Likes': likes, 'Comments': comments,
            'Shares': shares, 'Saves': saves,
            'Views_Per_Hour': views_per_hour, 
            'Engagement_Rate(%)': engagement_rate,
            'Viral_Velocity': viral_velocity,
            'Total_Stars': 0, 'Valid_Comments': 0
        }

        video_words = [] 

        for i in range(1, 6):
            raw_cmt = getattr(row, f'Top{i}_Cmt', "")
            raw_likes = getattr(row, f'Top{i}_Likes', 0)
            
            txt = clean_text(str(raw_cmt)) if pd.notna(raw_cmt) else ""
            clean_row[f'Top{i}_Cmt'] = txt
            clean_row[f'Top{i}_Likes'] = raw_likes if pd.notna(raw_likes) else 0
            
            if txt:
                comments_to_analyze.append(txt[:512]) 
                comment_tracker.append((len(clean_data_list), i))
                
                # Gọi hàm bóc tách từ khóa
                words = extract_keywords(txt)
                video_words.extend(words)

        top_video_keywords = [word for word, count in Counter(video_words).most_common(3)]
        clean_row['Top_Keywords'] = ", ".join(top_video_keywords)
        global_word_counter.update(video_words)
        
        clean_data_list.append(clean_row)

    print(f"[*] AI đang chấm điểm {len(comments_to_analyze)} bình luận cùng lúc...")
    
    # Gọi hàm AI
    ai_results = analyze_batch(comments_to_analyze)
    
    if ai_results:
        for (row_idx, cmt_idx), res in zip(comment_tracker, ai_results):
            stars = int(res['label'].split()[0])
            clean_data_list[row_idx]['Total_Stars'] += stars
            clean_data_list[row_idx]['Valid_Comments'] += 1

    # Tổng hợp điểm số
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

    # Xuất file
    df_clean = pd.DataFrame(clean_data_list)
    
    if not df_clean.empty:
        df_clean = run_viral_prediction(df_clean)
        
    df_clean.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
    
    print(f"[*] XONG! Dữ liệu đã lưu tại: {OUTPUT_FILE}")
    print("\n" + "="*40)
    print("🔥 TOP 15 TỪ KHÓA XUẤT HIỆN NHIỀU NHẤT:")
    for word, count in global_word_counter.most_common(15):
        print(f"   - {word.replace('_', ' ')}: {count} lần")
    print("="*40 + "\n")

if __name__ == "__main__":
    process_data()