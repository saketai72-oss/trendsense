import os
import sys
import pandas as pd
from datetime import datetime

# Thêm đường dẫn gốc để import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.db.models import get_high_potential_videos, update_viral_metrics_only
from services.ai_engine.math_utils import calculate_metrics
from services.ai_engine.sentiment_engine import analyze_batch
from services.ai_engine.prediction_engine import run_viral_prediction
from services.ai_engine.nlp_utils import clean_text

def main():
    print("[*] Bat dau phan tich lai cac chi so Viral cho video tiem nang (>40%)...")
    
    # 1. Lấy danh sách video tiềm năng cao
    videos = get_high_potential_videos(threshold=40.0)
    total = len(videos)
    print(f"[*] Tim thay {total} video can xu ly.")

    if total == 0:
        print("Done!")
        return

    processed = 0
    updated = 0

    for video in videos:
        vid = video['video_id']
        processed += 1
        print(f"\n[{processed}/{total}] Processing Video ID: {vid}")

        # Lấy stats hiện tại từ database
        views = video.get('views', 0)
        likes = video.get('likes', 0)
        comments_count = video.get('comments', 0)
        shares = video.get('shares', 0)
        saves = video.get('saves', 0)
        create_time = video.get('create_time', 0)
        caption = video.get('caption', '')

        # 2. Tính toán lại Metrics toán học (VPH, ER, Velocity)
        vph, er, velocity = calculate_metrics(
            views=views, likes=likes, comments=comments_count,
            shares=shares, saves=saves, create_time=create_time
        )

        # 3. Tính toán lại Sentiment (dựa trên comments cũ trong DB)
        sentiment = video.get('video_sentiment', "KHONG CO BINH LUAN")
        positive_score = video.get('positive_score', 0.0)
        
        comments_to_analyze = []
        for c_idx in range(1, 6):
            cmt = video.get(f'top{c_idx}_cmt', '')
            if cmt and str(cmt).strip():
                txt = clean_text(str(cmt))
                comments_to_analyze.append(txt[:512])

        if comments_to_analyze:
            ai_sentiment_results = analyze_batch(comments_to_analyze)
            if ai_sentiment_results:
                total_stars = sum(int(res['label'].split()[0]) for res in ai_sentiment_results)
                avg_stars = total_stars / len(ai_sentiment_results)
                positive_score = round((avg_stars / 5) * 100, 2)

                if avg_stars >= 3.5:
                    sentiment = "TICH CUC"
                elif avg_stars <= 2.5:
                    sentiment = "TIEU CUC"
                else:
                    sentiment = "TRUNG LAP"

        # 4. Dự báo lại Viral Probability
        viral_prob = 0.0
        try:
            df_single = pd.DataFrame([{
                'video_id': vid, 'views': views, 'likes': likes,
                'comments': comments_count, 'shares': shares, 'saves': saves,
                'create_time': create_time, 'positive_score': positive_score,
                'views_per_hour': vph
            }])
            df_pred = run_viral_prediction(df_single)
            if not df_pred.empty:
                viral_prob = float(df_pred.iloc[0]['viral_probability'])
        except Exception as e:
            print(f"    [!] Prediction Error: {e}")

        # 5. Cập nhật vào Database (Chỉ các chỉ số viral)
        res_dict = {
            'video_sentiment': sentiment,
            'positive_score': positive_score,
            'views_per_hour': vph,
            'engagement_rate': er,
            'viral_velocity': velocity,
            'viral_probability': viral_prob
        }

        if update_viral_metrics_only(vid, res_dict):
            print(f"    [OK] Da cap nhat: ER: {video['engagement_rate']}% -> {er}% | Prob: {video['viral_probability']}% -> {viral_prob}%")
            updated += 1
        else:
            print(f"    [ERR] That bai khi cap nhat Video ID: {vid}")

    print("\n" + "="*50)
    print("HOAN THANH PHAN TICH LAI")
    print(f"   - Tổng video duyệt: {processed}")
    print(f"   - Cập nhật thành công: {updated}")
    print("="*50)

if __name__ == "__main__":
    main()
