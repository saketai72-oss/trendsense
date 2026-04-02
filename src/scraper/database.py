import os
import sqlite3
import sys
from datetime import datetime, timedelta

# Khai báo đường dẫn gốc để import được config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from config import settings

DB_FILE = settings.DB_FILE


def _get_conn():
    """Tạo connection với WAL mode cho tốc độ ghi cao"""
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Khởi tạo database và tạo bảng nếu chưa có"""
    conn = _get_conn()
    cursor = conn.cursor()

    # Bảng chống trùng (giữ nguyên)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS history (
            video_id TEXT PRIMARY KEY
        )
    ''')

    # Bảng lưu trữ toàn bộ dữ liệu video
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS videos (
            video_id TEXT PRIMARY KEY,
            link TEXT,
            caption TEXT,
            views INTEGER DEFAULT 0,
            likes INTEGER DEFAULT 0,
            comments INTEGER DEFAULT 0,
            shares INTEGER DEFAULT 0,
            saves INTEGER DEFAULT 0,
            create_time INTEGER DEFAULT 0,
            scrape_date TEXT,
            top1_cmt TEXT, top1_likes INTEGER DEFAULT 0,
            top2_cmt TEXT, top2_likes INTEGER DEFAULT 0,
            top3_cmt TEXT, top3_likes INTEGER DEFAULT 0,
            top4_cmt TEXT, top4_likes INTEGER DEFAULT 0,
            top5_cmt TEXT, top5_likes INTEGER DEFAULT 0,
            views_per_hour REAL,
            engagement_rate REAL,
            viral_velocity REAL,
            positive_score REAL,
            video_sentiment TEXT,
            top_keywords TEXT,
            viral_probability REAL,
            sentiment_analyzed INTEGER DEFAULT 0
        )
    ''')

    # Index cho truy vấn theo ngày (sliding window)
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_scrape_date ON videos(scrape_date)
    ''')
    # Index cho truy vấn NLP cache
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_sentiment ON videos(sentiment_analyzed)
    ''')

    conn.commit()
    conn.close()


# =====================================================
# CÁC HÀM CŨ (GIỮ NGUYÊN CHO SCRAPER)
# =====================================================

def is_scraped(video_id):
    """Kiểm tra xem video đã bị cào chưa"""
    conn = _get_conn()
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM history WHERE video_id = ?', (video_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None


def mark_as_scraped(video_id):
    """Lưu ID video vào bảng history sau khi cào xong"""
    conn = _get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO history (video_id) VALUES (?)', (video_id,))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()


def extract_video_id(url):
    """Cắt lấy đúng cái dãy số ID từ link TikTok"""
    try:
        return url.split('/video/')[1].split('?')[0]
    except:
        return None


# =====================================================
# CÁC HÀM MỚI CHO PIPELINE TÁCH TRAIN/INFERENCE
# =====================================================

def save_video(video_id, data_dict):
    """Ghi 1 video vào bảng videos (INSERT OR REPLACE)"""
    conn = _get_conn()
    cursor = conn.cursor()

    # Đảm bảo có scrape_date
    if 'scrape_date' not in data_dict or not data_dict['scrape_date']:
        data_dict['scrape_date'] = datetime.now().date().isoformat()

    cursor.execute('''
        INSERT OR REPLACE INTO videos (
            video_id, link, caption, views, likes, comments, shares, saves,
            create_time, scrape_date,
            top1_cmt, top1_likes, top2_cmt, top2_likes,
            top3_cmt, top3_likes, top4_cmt, top4_likes,
            top5_cmt, top5_likes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        video_id,
        data_dict.get('link', ''),
        data_dict.get('caption', ''),
        data_dict.get('views', 0),
        data_dict.get('likes', 0),
        data_dict.get('comments', 0),
        data_dict.get('shares', 0),
        data_dict.get('saves', 0),
        data_dict.get('create_time', 0),
        data_dict['scrape_date'],
        data_dict.get('top1_cmt', ''),
        data_dict.get('top1_likes', 0),
        data_dict.get('top2_cmt', ''),
        data_dict.get('top2_likes', 0),
        data_dict.get('top3_cmt', ''),
        data_dict.get('top3_likes', 0),
        data_dict.get('top4_cmt', ''),
        data_dict.get('top4_likes', 0),
        data_dict.get('top5_cmt', ''),
        data_dict.get('top5_likes', 0),
    ))
    conn.commit()
    conn.close()


def save_videos_batch(video_list):
    """Ghi nhiều video vào bảng videos cùng lúc"""
    for video_id, data_dict in video_list:
        save_video(video_id, data_dict)
    print(f"[+] Đã ghi {len(video_list)} video vào SQLite.")


def get_unanalyzed_videos():
    """Lấy danh sách video chưa chạy NLP sentiment"""
    conn = _get_conn()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM videos 
        WHERE sentiment_analyzed = 0 AND views > 0
        ORDER BY scrape_date DESC
    ''')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def update_sentiment(video_id, sentiment_data):
    """Cập nhật kết quả NLP + đánh cờ đã phân tích"""
    conn = _get_conn()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE videos SET
            views_per_hour = ?,
            engagement_rate = ?,
            viral_velocity = ?,
            positive_score = ?,
            video_sentiment = ?,
            top_keywords = ?,
            sentiment_analyzed = 1
        WHERE video_id = ?
    ''', (
        sentiment_data.get('views_per_hour', 0),
        sentiment_data.get('engagement_rate', 0),
        sentiment_data.get('viral_velocity', 0),
        sentiment_data.get('positive_score', 0),
        sentiment_data.get('video_sentiment', ''),
        sentiment_data.get('top_keywords', ''),
        video_id,
    ))
    conn.commit()
    conn.close()


def update_prediction(video_id, viral_probability):
    """Cập nhật kết quả dự đoán viral cho 1 video"""
    conn = _get_conn()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE videos SET viral_probability = ? WHERE video_id = ?
    ''', (viral_probability, video_id))
    conn.commit()
    conn.close()


def update_predictions_batch(predictions):
    """Cập nhật kết quả dự đoán cho nhiều video cùng lúc
    predictions: list of (video_id, viral_probability)
    """
    conn = _get_conn()
    cursor = conn.cursor()
    cursor.executemany('''
        UPDATE videos SET viral_probability = ? WHERE video_id = ?
    ''', predictions)
    conn.commit()
    conn.close()
    print(f"[+] Đã cập nhật xác suất viral cho {len(predictions)} video.")


def get_recent_videos(days=None):
    """Lấy video trong N ngày gần nhất (sliding window cho training)"""
    if days is None:
        days = settings.SLIDING_WINDOW_DAYS

    cutoff_date = (datetime.now() - timedelta(days=days)).date().isoformat()
    conn = _get_conn()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM videos 
        WHERE scrape_date >= ? AND sentiment_analyzed = 1 AND views > 0
        ORDER BY scrape_date DESC
    ''', (cutoff_date,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_all_analyzed_videos():
    """Lấy toàn bộ video đã xử lý xong cho Dashboard"""
    conn = _get_conn()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM videos 
        WHERE sentiment_analyzed = 1 AND views > 0
        ORDER BY viral_probability DESC NULLS LAST
    ''')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]