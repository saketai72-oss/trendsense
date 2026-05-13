"""
Model 2 – Trend Content Analyzer
Trích xuất các đặc điểm xu hướng từ những video có viral probability cao (top 20%),
phục vụ đánh giá video user upload và dashboard.

Chạy định kỳ (ví dụ sau mỗi lần train model hoặc hàng tuần).
"""

import sys
import os
import json
from collections import Counter
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from core.db.models import get_connection, get_recent_videos
from core.db.session import get_connection as get_db_conn

# ------------------------------------------------------------
# 1. Lấy danh sách video đang trend (dựa trên viral_probability)
# ------------------------------------------------------------
def get_trending_video_ids(threshold_prob: float = 70.0, days: int = 14) -> List[str]:
    """
    Lấy video_id của những video có viral_probability >= threshold_prob
    và được scrape trong `days` ngày gần nhất.
    """
    cutoff = (datetime.now() - timedelta(days=days)).date().isoformat()
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT video_id FROM videos
                WHERE scrape_date >= %s
                  AND viral_probability >= %s
                  AND ai_status = 'completed'
                ORDER BY viral_probability DESC
            """, (cutoff, threshold_prob))
            rows = cur.fetchall()
            return [row[0] for row in rows]
    finally:
        conn.close()

# ------------------------------------------------------------
# 2. Trích xuất keywords từ nội dung video
# ------------------------------------------------------------
def extract_keywords_from_text(text: str) -> List[str]:
    """
    Sử dụng hàm hiện có trong nlp_utils để lấy keywords thông minh.
    Fallback: tách từ đơn giản nếu không import được.
    """
    try:
        from services.ai_engine.nlp_utils import extract_smart_keywords
        return extract_smart_keywords(text)
    except ImportError:
        # Fallback thô
        import re
        words = re.findall(r'\b\w+\b', text.lower())
        stopwords = {'video', 'clip', 'tiktok', 'fyp', 'foryou', 'trend', 'trending',
                     'xem', 'làm', 'nên', 'bảo', 'nghĩ', 'nói', 'hiểu', 'muốn', 'thích'}
        return [w for w in words if w not in stopwords and len(w) > 2][:10]

def aggregate_trends(video_ids: List[str]) -> Dict[str, Any]:
    """
    Từ danh sách video_id, tổng hợp:
    - Top 20 keywords
    - Top 10 hashtags
    - Phân phối category
    - Các audio transcript nổi bật
    """
    if not video_ids:
        return {
            "keywords": [],
            "hashtags": [],
            "categories": {},
            "audio_snippets": []
        }

    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            # Lấy caption, top_keywords, category, audio_transcript
            cur.execute("""
                SELECT caption, top_keywords, category, audio_transcript
                FROM videos
                WHERE video_id = ANY(%s)
            """, (video_ids,))
            rows = cur.fetchall()
    finally:
        conn.close()

    keyword_counter = Counter()
    hashtag_counter = Counter()
    category_counter = Counter()
    audio_transcripts = []

    for caption, top_keywords_str, category_list, audio_transcript in rows:
        # Keywords từ AI (top_keywords)
        if top_keywords_str:
            for kw in top_keywords_str.split(','):
                kw = kw.strip()
                if kw:
                    keyword_counter[kw] += 1

        # Keywords từ caption (fallback)
        if caption:
            caption_kws = extract_keywords_from_text(caption)
            for kw in caption_kws:
                keyword_counter[kw] += 1

        # Hashtags (bắt đầu bằng # trong caption)
        if caption:
            import re
            hashtags = re.findall(r'#(\w+)', caption)
            for ht in hashtags:
                hashtag_counter[ht.lower()] += 1

        # Category
        if category_list and isinstance(category_list, list):
            for cat in category_list:
                category_counter[cat] += 1

        # Audio snippet (chỉ lấy 200 ký tự đầu)
        if audio_transcript and isinstance(audio_transcript, str):
            audio_transcripts.append(audio_transcript[:200])

    return {
        "keywords": [{"keyword": k, "count": c} for k, c in keyword_counter.most_common(20)],
        "hashtags": [{"hashtag": h, "count": c} for h, c in hashtag_counter.most_common(10)],
        "categories": [{"category": c, "count": cnt} for c, cnt in category_counter.most_common()],
        "audio_snippets": audio_transcripts[:5],
        "total_videos_analyzed": len(video_ids)
    }

# ------------------------------------------------------------
# 3. Lưu báo cáo trend vào database (bảng mới nếu cần)
# ------------------------------------------------------------
def create_trends_table_if_not_exists():
    """Đảm bảo bảng trends_weekly tồn tại để lưu snapshot."""
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS trends_weekly (
                    id SERIAL PRIMARY KEY,
                    week_start DATE NOT NULL,
                    keywords JSONB,
                    hashtags JSONB,
                    categories JSONB,
                    audio_snippets JSONB,
                    total_videos INT,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            conn.commit()
    except Exception as e:
        print(f"[ERROR] Failed to create trends_weekly table: {e}")
        conn.rollback()
    finally:
        conn.close()

def save_weekly_trend_report(report: Dict[str, Any], week_start: Optional[str] = None):
    """
    Lưu báo cáo trend vào bảng trends_weekly.
    week_start: ngày đầu tuần (YYYY-MM-DD), mặc định là thứ Hai tuần này.
    """
    create_trends_table_if_not_exists()
    if week_start is None:
        today = datetime.now().date()
        # Tính thứ Hai tuần này
        week_start = (today - timedelta(days=today.weekday())).isoformat()

    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            # Xóa báo cáo cũ cùng tuần để cập nhật
            cur.execute("DELETE FROM trends_weekly WHERE week_start = %s", (week_start,))
            cur.execute("""
                INSERT INTO trends_weekly (week_start, keywords, hashtags, categories, audio_snippets, total_videos)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                week_start,
                json.dumps(report.get("keywords", [])),
                json.dumps(report.get("hashtags", [])),
                json.dumps(report.get("categories", [])),
                json.dumps(report.get("audio_snippets", [])),
                report.get("total_videos", 0)
            ))
            conn.commit()
    except Exception as e:
        print(f"[ERROR] Failed to save trend report: {e}")
        conn.rollback()
    finally:
        conn.close()

# ------------------------------------------------------------
# 4. Đánh giá video user upload dựa trên trend hiện tại
# ------------------------------------------------------------
def load_latest_trend_report() -> Optional[Dict[str, Any]]:
    """Lấy báo cáo trend của tuần gần nhất."""
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT keywords, hashtags, categories
                FROM trends_weekly
                ORDER BY week_start DESC
                LIMIT 1
            """)
            row = cur.fetchone()
            if row:
                # Parse JSON strings back to lists/dicts if they aren't already parsed (JSONB)
                def _parse(val):
                    if val is None: return []
                    if isinstance(val, (list, dict)): return val
                    try: return json.loads(val)
                    except: return []

                return {
                    "keywords": _parse(row[0]),
                    "hashtags": _parse(row[1]),
                    "categories": _parse(row[2])
                }
            return None
    finally:
        conn.close()

def compute_trend_alignment_for_video(video_keywords: List[str], video_category: str,
                                      trend_report: Dict[str, Any]) -> float:
    """
    Tính điểm alignment (0-100) dựa trên keywords và category.
    trend_report: từ load_latest_trend_report()
    """
    if not trend_report:
        return 50.0  # neutral

    trending_keywords = [kw["keyword"].lower() for kw in trend_report.get("keywords", [])]
    video_kw_lower = [kw.lower() for kw in video_keywords]

    overlap = sum(1 for kw in video_kw_lower if kw in trending_keywords)
    kw_score = min(overlap / max(len(video_kw_lower), 1) * 100, 100)

    # Category matching
    trending_cats = [cat["category"] for cat in trend_report.get("categories", [])]
    cat_score = 100 if video_category in trending_cats else 0

    # Weighted: 70% keywords, 30% category
    alignment = (kw_score * 0.7) + (cat_score * 0.3)
    return round(alignment, 1)

# ------------------------------------------------------------
# 5. Pipeline chính: chạy hàng tuần (được gọi từ train_model.py hoặc cron)
# ------------------------------------------------------------
def run_trend_analysis(threshold_prob: float = 70.0, days: int = 14):
    """
    Pipeline chính:
    - Lấy video trend
    - Tổng hợp báo cáo
    - Lưu vào DB
    """
    print("\n=== Trend Analyzer (Model 2) ===")
    video_ids = get_trending_video_ids(threshold_prob, days)
    print(f"Found {len(video_ids)} trending videos (probability >= {threshold_prob})")
    if not video_ids:
        print("No trending videos found. Skip report.")
        return

    report = aggregate_trends(video_ids)
    save_weekly_trend_report(report)
    print(f"Saved trend report with {len(report['keywords'])} keywords, {len(report['hashtags'])} hashtags")
    return report

if __name__ == "__main__":
    run_trend_analysis()