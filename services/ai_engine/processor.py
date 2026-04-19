import os
import pandas as pd
from core.config import service_settings as settings
from core.db.models import update_ai_results
from services.tiktok_scraper.video_downloader import download_video
from services.ai_engine.multimodal_engine import analyze_multimodal
from services.ai_engine.math_utils import calculate_metrics
from services.ai_engine.nlp_utils import clean_text, extract_smart_keywords
from services.ai_engine.sentiment_engine import analyze_batch
from services.ai_engine.prediction_engine import run_viral_prediction
from services.ai_engine.categorizer import categorize_video

def process_video_item(video_data):
    """
    Quy trình xử lý hoàn chỉnh cho 1 video:
    Compute Metrics -> Sentiment -> Categorize -> Multimodal -> Prediction -> Update DB
    """
    vid = video_data['video_id']
    url = video_data.get('link', '')
    caption = video_data.get('caption', '')
    
    # 1. Tính toán Metrics (Tương tác)
    views = video_data.get('views', 0) or 0
    likes = video_data.get('likes', 0) or 0
    comments = video_data.get('comments', 0) or 0
    shares = video_data.get('shares', 0) or 0
    saves = video_data.get('saves', 0) or 0
    create_time = video_data.get('create_time', 0) or 0

    vph, er, velocity = calculate_metrics(
        views=views, likes=likes, comments=comments,
        shares=shares, saves=saves, create_time=create_time
    )

    # 2. Phân tích Sentiment & Keywords
    sentiment = "⚪ KHÔNG CÓ BÌNH LUẬN"
    positive_score = 0.0
    comments_to_analyze = []
    all_text_for_keywords = clean_text(str(caption))
    
    for c_idx in range(1, 6):
        cmt = video_data.get(f'top{c_idx}_cmt', '')
        if cmt and str(cmt).strip():
            txt = clean_text(str(cmt))
            comments_to_analyze.append(txt[:512])
            all_text_for_keywords += " " + txt

    if comments_to_analyze:
        ai_sentiment_results = analyze_batch(comments_to_analyze)
        if ai_sentiment_results:
            total_stars = sum(int(res['label'].split()[0]) for res in ai_sentiment_results)
            avg_stars = total_stars / len(ai_sentiment_results)
            positive_score = round((avg_stars / 5) * 100, 2)

            if avg_stars >= 3.5:
                sentiment = "🟢 TÍCH CỰC"
            elif avg_stars <= 2.5:
                sentiment = "🔴 TIÊU CỰC"
            else:
                sentiment = "🟡 TRUNG LẬP"

    smart_kws = extract_smart_keywords(all_text_for_keywords)
    top_keywords = ", ".join(smart_kws[:5]) if smart_kws else ""

    # 3. Phân loại danh mục ban đầu
    initial_category = categorize_video(vid, caption)

    ai_results_dict = {
        'video_description': "Không tải được MP4 để phân tích Multimodal.",
        'category': initial_category,
        'top_keywords': top_keywords,
        'video_sentiment': sentiment,
        'positive_score': positive_score,
        'views_per_hour': vph,
        'engagement_rate': er,
        'viral_velocity': velocity,
        'viral_probability': 0.0
    }

    # 4. Tải và chạy Multimodal AI
    file_path = None
    try:
        file_path = download_video(url, vid)
        if file_path and os.path.exists(file_path):
            summary, o_cat, _, _, _ = analyze_multimodal(file_path, caption)
            ai_results_dict['video_description'] = summary
            
            # Tie-breaker logic cho Category
            if initial_category == "🌍 Khác" or not initial_category:
                ai_results_dict['category'] = o_cat
            
            print(f"    ✨ AI Summary: {summary[:100]}...")
    except Exception as e:
        print(f"    [!] Multimodal Error: {e}")
    finally:
        if file_path and os.path.exists(file_path):
            try: os.remove(file_path)
            except: pass

    # 5. Dự báo Viral
    try:
        df_single = pd.DataFrame([{
            'video_id': vid, 'views': views, 'likes': likes,
            'comments': comments, 'shares': shares, 'saves': saves,
            'create_time': create_time, 'positive_score': positive_score,
            'views_per_hour': vph
        }])
        df_pred = run_viral_prediction(df_single)
        if not df_pred.empty:
            ai_results_dict['viral_probability'] = float(df_pred.iloc[0]['viral_probability'])
    except Exception as e:
        print(f"    [!] Prediction Error: {e}")

    # 6. Cập nhật kết quả lên Cloud
    update_ai_results(vid, ai_results_dict)
    return True
