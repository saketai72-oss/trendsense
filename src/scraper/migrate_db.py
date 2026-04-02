"""
Script chạy 1 lần duy nhất: Import dữ liệu từ CSV cũ vào SQLite.
Sau khi chạy xong, có thể xoá file CSV cũ.

Cách dùng:
    python src/scraper/migrate_db.py
"""
import pandas as pd
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from config import settings

# Import database module từ cùng thư mục
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database import init_db, save_video, extract_video_id


def migrate():
    print("=" * 60)
    print("🔄 BẮT ĐẦU MIGRATION: CSV → SQLite")
    print("=" * 60)

    # 1. Khởi tạo database với schema mới
    init_db()
    print("[✓] Database schema đã sẵn sàng.")

    migrated_count = 0

    # 2. Đọc file RAW CSV
    if os.path.exists(settings.RAW_FILE):
        print(f"\n[*] Đang đọc file RAW: {settings.RAW_FILE}")
        try:
            df_raw = pd.read_csv(settings.RAW_FILE, low_memory=False)
            print(f"    → Tìm thấy {len(df_raw)} dòng.")

            # Lọc bỏ rác: không có Views hoặc Views = 0
            df_raw['Views'] = pd.to_numeric(df_raw.get('Views', 0), errors='coerce').fillna(0)
            df_clean = df_raw[df_raw['Views'] > 0].copy()
            print(f"    → Sau lọc rác còn {len(df_clean)} dòng hợp lệ.")

            for _, row in df_clean.iterrows():
                link = str(row.get('Link', ''))
                video_id = extract_video_id(link)
                if not video_id:
                    continue

                data = {
                    'link': link,
                    'caption': str(row.get('Caption', '')),
                    'views': int(row.get('Views', 0)),
                    'likes': int(pd.to_numeric(row.get('Likes', 0), errors='coerce') or 0),
                    'comments': int(pd.to_numeric(row.get('Comments', 0), errors='coerce') or 0),
                    'shares': int(pd.to_numeric(row.get('Shares', 0), errors='coerce') or 0),
                    'saves': int(pd.to_numeric(row.get('Saves', 0), errors='coerce') or 0),
                    'create_time': int(pd.to_numeric(row.get('Create_Time', 0), errors='coerce') or 0),
                    'scrape_date': '2026-04-01',  # Ngày gần đúng cho data cũ
                }

                # Chuyển top comments nếu có
                for i in range(1, 6):
                    cmt_col = f'Top{i}_Cmt'
                    likes_col = f'Top{i}_Likes'
                    data[f'top{i}_cmt'] = str(row.get(cmt_col, '')) if pd.notna(row.get(cmt_col, '')) else ''
                    data[f'top{i}_likes'] = int(pd.to_numeric(row.get(likes_col, 0), errors='coerce') or 0)

                save_video(video_id, data)
                migrated_count += 1

            print(f"    [✓] Đã import {migrated_count} video từ RAW CSV.")
        except Exception as e:
            print(f"    [!] Lỗi đọc RAW CSV: {e}")
    else:
        print(f"[!] Không tìm thấy file RAW: {settings.RAW_FILE}")

    # 3. Xử lý file PROCESSED CSV (lấy thêm sentiment đã phân tích)
    if os.path.exists(settings.PROCESSED_FILE):
        print(f"\n[*] Đang đọc file PROCESSED: {settings.PROCESSED_FILE}")
        try:
            df_proc = pd.read_csv(settings.PROCESSED_FILE, low_memory=False)
            print(f"    → Tìm thấy {len(df_proc)} dòng.")

            updated = 0
            for _, row in df_proc.iterrows():
                link = str(row.get('Link', ''))
                video_id = extract_video_id(link)
                if not video_id:
                    continue

                # Import các cột đã phân tích từ processed
                from database import _get_conn
                conn = _get_conn()
                cursor = conn.cursor()

                positive_score = float(pd.to_numeric(row.get('Positive_Score', 0), errors='coerce') or 0)
                video_sentiment = str(row.get('Video_Sentiment', ''))
                top_keywords = str(row.get('Top_Keywords', ''))
                viral_prob = float(pd.to_numeric(row.get('Viral_Probability_%', 0), errors='coerce') or 0)
                views_per_hour = float(pd.to_numeric(row.get('Views_Per_Hour', 0), errors='coerce') or 0)
                engagement_rate = float(pd.to_numeric(row.get('Engagement_Rate(%)', 0), errors='coerce') or 0)
                viral_velocity = float(pd.to_numeric(row.get('Viral_Velocity', 0), errors='coerce') or 0)

                cursor.execute('''
                    UPDATE videos SET
                        views_per_hour = ?,
                        engagement_rate = ?,
                        viral_velocity = ?,
                        positive_score = ?,
                        video_sentiment = ?,
                        top_keywords = ?,
                        viral_probability = ?,
                        sentiment_analyzed = 1
                    WHERE video_id = ?
                ''', (
                    views_per_hour, engagement_rate, viral_velocity,
                    positive_score, video_sentiment, top_keywords,
                    viral_prob, video_id
                ))

                if cursor.rowcount > 0:
                    updated += 1

                conn.commit()
                conn.close()

            print(f"    [✓] Đã cập nhật sentiment/predict cho {updated} video từ PROCESSED CSV.")
        except Exception as e:
            print(f"    [!] Lỗi đọc PROCESSED CSV: {e}")

    # 4. Tổng kết
    print(f"\n{'=' * 60}")
    print(f"✅ MIGRATION HOÀN TẤT!")
    print(f"   → Tổng video đã import: {migrated_count}")
    print(f"   → Database: {settings.DB_FILE}")
    print(f"\n💡 Bây giờ có thể xoá các file CSV cũ:")
    print(f"   - {settings.RAW_FILE}")
    print(f"   - {settings.PROCESSED_FILE}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    migrate()
