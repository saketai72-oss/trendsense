import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
from config import settings

def get_connection():
    """Tạo kết nối trực tiếp tới Supabase PostgreSQL"""
    conn = psycopg2.connect(settings.DATABASE_URL)
    conn.autocommit = False
    return conn

def init_db():
    """Khởi tạo database PostgreSQL trên Supabase"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # Bảng lưu lịch sử video
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
                    create_time BIGINT DEFAULT 0,
                    scrape_date DATE DEFAULT CURRENT_DATE,

                    -- Top Comments
                    top1_cmt TEXT, top1_likes INTEGER DEFAULT 0,
                    top2_cmt TEXT, top2_likes INTEGER DEFAULT 0,
                    top3_cmt TEXT, top3_likes INTEGER DEFAULT 0,
                    top4_cmt TEXT, top4_likes INTEGER DEFAULT 0,
                    top5_cmt TEXT, top5_likes INTEGER DEFAULT 0,

                    -- AI Analysis Fields
                    views_per_hour REAL DEFAULT 0,
                    engagement_rate REAL DEFAULT 0,
                    viral_velocity REAL DEFAULT 0,
                    positive_score REAL DEFAULT 0,
                    video_sentiment TEXT,
                    top_keywords TEXT,
                    viral_probability REAL DEFAULT 0,
                    category TEXT,
                    video_description TEXT,

                    -- Status Flags
                    ai_status VARCHAR(20) DEFAULT 'pending'
                )
            ''')

            # Index tối ưu hóa
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_ai_status ON videos(ai_status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_scrape_date ON videos(scrape_date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_category ON videos(category)')

            conn.commit()
            print("[OK] Supabase Schema initialized successfully.")
    except Exception as e:
        print(f"[ERROR] Failed to init schema: {e}")
        conn.rollback()
    finally:
        conn.close()

def insert_video_metadata(video_id, data_dict):
    """Ghi dữ liệu thô từ TikTok (UPSERT nếu trùng ID)"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            query = '''
                INSERT INTO videos (
                    video_id, link, caption, views, likes, comments, shares, saves,
                    create_time, scrape_date, ai_status,
                    top1_cmt, top1_likes, top2_cmt, top2_likes,
                    top3_cmt, top3_likes, top4_cmt, top4_likes,
                    top5_cmt, top5_likes
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (video_id) DO UPDATE SET
                    views = EXCLUDED.views,
                    likes = EXCLUDED.likes,
                    comments = EXCLUDED.comments,
                    shares = EXCLUDED.shares,
                    saves = EXCLUDED.saves,
                    caption = EXCLUDED.caption
            '''
            cursor.execute(query, (
                video_id,
                data_dict.get('link', ''),
                data_dict.get('caption', ''),
                data_dict.get('views', 0),
                data_dict.get('likes', 0),
                data_dict.get('comments', 0),
                data_dict.get('shares', 0),
                data_dict.get('saves', 0),
                data_dict.get('create_time', 0),
                data_dict.get('scrape_date', datetime.now().date().isoformat()),
                data_dict.get('top1_cmt', ''), data_dict.get('top1_likes', 0),
                data_dict.get('top2_cmt', ''), data_dict.get('top2_likes', 0),
                data_dict.get('top3_cmt', ''), data_dict.get('top3_likes', 0),
                data_dict.get('top4_cmt', ''), data_dict.get('top4_likes', 0),
                data_dict.get('top5_cmt', ''), data_dict.get('top5_likes', 0)
            ))

            cursor.execute('INSERT INTO history (video_id) VALUES (%s) ON CONFLICT DO NOTHING', (video_id,))
            conn.commit()
    except Exception as e:
        print(f"[ERROR] insert_video_metadata failed: {e}")
        conn.rollback()
    finally:
        conn.close()

def is_scraped(video_id):
    """Kiểm tra video đã tồn tại trong history"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('SELECT 1 FROM history WHERE video_id = %s', (video_id,))
            return cursor.fetchone() is not None
    finally:
        conn.close()

def mark_as_scraped(video_id):
    """Lưu ID video vào history"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('INSERT INTO history (video_id) VALUES (%s) ON CONFLICT DO NOTHING', (video_id,))
            conn.commit()
    finally:
        conn.close()

def get_pending_videos():
    """Lấy danh sách video chờ xử lý AI"""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT * FROM videos WHERE ai_status = 'pending' AND views > 0 ORDER BY scrape_date DESC")
            return cursor.fetchall()
    finally:
        conn.close()

def update_ai_results(video_id, res):
    """Cập nhật kết quả AI tổng hợp"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            query = '''
                UPDATE videos SET
                    category = %s, video_description = %s, top_keywords = %s,
                    video_sentiment = %s, positive_score = %s, views_per_hour = %s,
                    engagement_rate = %s, viral_velocity = %s, viral_probability = %s,
                    ai_status = 'completed'
                WHERE video_id = %s
            '''
            cursor.execute(query, (
                res.get('category'), res.get('video_description'), res.get('top_keywords'),
                res.get('video_sentiment'), res.get('positive_score', 0), res.get('views_per_hour', 0),
                res.get('engagement_rate', 0), res.get('viral_velocity', 0), res.get('viral_probability', 0),
                video_id
            ))
            conn.commit()
    except Exception as e:
        print(f"[ERROR] update_ai_results failed: {e}")
        conn.rollback()
    finally:
        conn.close()

def get_recent_videos(days=14):
    """Lấy video cho training (Sliding Window)"""
    cutoff = (datetime.now() - timedelta(days=days or 14)).date().isoformat()
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute('SELECT * FROM videos WHERE scrape_date >= %s AND ai_status = "completed" AND views > 0', (cutoff,))
            return cursor.fetchall()
    finally:
        conn.close()

def get_all_analyzed_videos():
    """Lấy toàn bộ video cho Dashboard"""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute('SELECT * FROM videos WHERE views > 0 ORDER BY viral_probability DESC NULLS LAST, scrape_date DESC')
            return cursor.fetchall()
    finally:
        conn.close()

def reset_all_analysis_status():
    """Reset TOÀN BỘ database để AI Core có thể phân tích lại từ đầu"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE videos SET ai_status = 'pending'")
            conn.commit()
            print("[✓] Reset all videos to 'pending' success.")
    finally:
        conn.close()

def extract_video_id(url):
    try: return url.split('/video/')[1].split('?')[0]
    except: return None

if __name__ == "__main__":
    init_db()