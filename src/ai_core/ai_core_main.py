"""
AI Core Main — Luồng Inference chạy mỗi 4 giờ.
1. Đọc video MỚI chưa phân tích từ SQLite
2. Chạy NLP Sentiment CHỈ trên comment chưa xử lý (cache)
3. Predict viral probability bằng model đã train sẵn
4. Ghi kết quả ngược lại vào SQLite
"""
import pandas as pd
import os
import sys
from collections import Counter

# Nạp config từ thư mục gốc
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from config import settings

# Nạp database
sys.path.append(os.path.join(settings.SRC_DIR, 'scraper'))
from database import init_db, get_unanalyzed_videos, update_sentiment, \
    update_predictions_batch, get_all_analyzed_videos

# Nạp các module AI tự viết
from math_utils import calculate_metrics
from nlp_utils import clean_text, extract_keywords
from sentiment_engine import analyze_batch
from prediction_engine import run_viral_prediction


def process_new_videos():
    """Xử lý CHỈ các video chưa được phân tích NLP (sentiment_analyzed = 0)"""
    print("\n" + "=" * 60)
    print("🧠 AI CORE — CHẾ ĐỘ INFERENCE (Chỉ xử lý video mới)")
    print("=" * 60)

    init_db()

    # 1. Lấy video chưa phân tích
    new_videos = get_unanalyzed_videos()

    if not new_videos:
        print("[*] ✅ Không có video mới cần xử lý. Mọi thứ đã cập nhật.")
        return

    print(f"[*] Tìm thấy {len(new_videos)} video mới chưa phân tích.")

    global_word_counter = Counter()

    # 2. Xử lý từng video: tính metrics + chuẩn bị NLP
    comments_to_analyze = []
    comment_tracker = []  # (video_index, comment_index)

    for idx, video in enumerate(new_videos):
        # Tính metrics
        views = video.get('views', 0) or 0
        likes = video.get('likes', 0) or 0
        comments = video.get('comments', 0) or 0
        shares = video.get('shares', 0) or 0
        saves = video.get('saves', 0) or 0
        create_time = video.get('create_time', 0) or 0

        views_per_hour, engagement_rate, viral_velocity = calculate_metrics(
            views=views, likes=likes, comments=comments,
            shares=shares, saves=saves, create_time=create_time
        )

        # Lưu metrics tạm vào dict
        new_videos[idx]['_views_per_hour'] = views_per_hour
        new_videos[idx]['_engagement_rate'] = engagement_rate
        new_videos[idx]['_viral_velocity'] = viral_velocity
        new_videos[idx]['_total_stars'] = 0
        new_videos[idx]['_valid_comments'] = 0

        # Xử lý top comments
        video_words = []
        for i in range(1, 6):
            raw_cmt = video.get(f'top{i}_cmt', '')
            txt = clean_text(str(raw_cmt)) if raw_cmt else ""

            if txt:
                comments_to_analyze.append(txt[:512])
                comment_tracker.append((idx, i))

                words = extract_keywords(txt)
                video_words.extend(words)

        top_video_keywords = [word for word, count in Counter(video_words).most_common(3)]
        new_videos[idx]['_top_keywords'] = ", ".join(top_video_keywords)
        global_word_counter.update(video_words)

    # 3. NLP Sentiment chạy trên TOÀN BỘ comments chưa phân tích
    if comments_to_analyze:
        print(f"[*] AI đang chấm điểm {len(comments_to_analyze)} bình luận MỚI...")
        ai_results = analyze_batch(comments_to_analyze)

        if ai_results:
            for (vid_idx, cmt_idx), res in zip(comment_tracker, ai_results):
                stars = int(res['label'].split()[0])
                new_videos[vid_idx]['_total_stars'] += stars
                new_videos[vid_idx]['_valid_comments'] += 1
    else:
        print("[*] Không có bình luận mới cần phân tích NLP.")

    # 4. Tổng hợp điểm & ghi kết quả vào SQLite
    print("[*] Đang lưu kết quả phân tích vào SQLite...")
    for video in new_videos:
        total_stars = video['_total_stars']
        valid_comments = video['_valid_comments']

        if valid_comments > 0:
            avg_stars = total_stars / valid_comments
            positive_score = round((avg_stars / 5) * 100, 2)

            if avg_stars >= 3.5:
                sentiment = "🟢 TÍCH CỰC"
            elif avg_stars <= 2.5:
                sentiment = "🔴 TIÊU CỰC"
            else:
                sentiment = "🟡 TRUNG LẬP"
        else:
            positive_score = 0
            sentiment = "⚪ KHÔNG CÓ BÌNH LUẬN"

        # Ghi vào SQLite + đánh cờ sentiment_analyzed = 1
        update_sentiment(video['video_id'], {
            'views_per_hour': video['_views_per_hour'],
            'engagement_rate': video['_engagement_rate'],
            'viral_velocity': video['_viral_velocity'],
            'positive_score': positive_score,
            'video_sentiment': sentiment,
            'top_keywords': video['_top_keywords'],
        })

    print(f"[✓] Đã phân tích xong {len(new_videos)} video mới.")

    # 5. Predict viral bằng model sẵn trên TOÀN BỘ video đã xử lý
    print("\n[*] Đang predict xác suất viral cho toàn bộ video...")
    all_videos = get_all_analyzed_videos()

    if all_videos:
        df_all = pd.DataFrame(all_videos)
        df_result = run_viral_prediction(df_all)

        # Ghi kết quả predict ngược lại SQLite
        if 'viral_probability' in df_result.columns:
            predictions = [
                (row['viral_probability'], row['video_id'])
                for _, row in df_result.iterrows()
                if pd.notna(row.get('viral_probability'))
            ]
            if predictions:
                update_predictions_batch(predictions)

    # 6. In thống kê
    if global_word_counter:
        print("\n" + "=" * 40)
        print("🔥 TOP 15 TỪ KHÓA XUẤT HIỆN NHIỀU NHẤT (batch mới):")
        for word, count in global_word_counter.most_common(15):
            print(f"   - {word.replace('_', ' ')}: {count} lần")
        print("=" * 40)

    print(f"\n✅ AI CORE HOÀN TẤT! Đã xử lý {len(new_videos)} video mới.")


if __name__ == "__main__":
    process_new_videos()