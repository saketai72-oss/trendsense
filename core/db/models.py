import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
from core.db.session import get_connection

# ==========================================
# SCHEMA INITIALIZATION
# ==========================================

def init_db():
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS history (
                    video_id TEXT PRIMARY KEY
                )
            ''')
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
                    top1_cmt TEXT, top1_likes INTEGER DEFAULT 0,
                    top2_cmt TEXT, top2_likes INTEGER DEFAULT 0,
                    top3_cmt TEXT, top3_likes INTEGER DEFAULT 0,
                    top4_cmt TEXT, top4_likes INTEGER DEFAULT 0,
                    top5_cmt TEXT, top5_likes INTEGER DEFAULT 0,
                    views_per_hour REAL DEFAULT 0,
                    engagement_rate REAL DEFAULT 0,
                    viral_velocity REAL DEFAULT 0,
                    positive_score REAL DEFAULT 0,
                    video_sentiment TEXT,
                    top_keywords TEXT,
                    viral_probability REAL DEFAULT 0,
                    category TEXT,
                    video_description TEXT,
                    ai_status VARCHAR(20) DEFAULT 'pending'
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_ai_status ON videos(ai_status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_scrape_date ON videos(scrape_date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_category ON videos(category)')
            conn.commit()
    except Exception as e:
        print(f"[ERROR] Failed to init schema: {e}")
        conn.rollback()
    finally:
        conn.close()

# ==========================================
# SCRAPER & AI PIPELINE DATA LOGIC
# ==========================================

def insert_video_metadata(video_id, data_dict):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            views = int(data_dict.get('views', 0))
            likes = int(data_dict.get('likes', 0))
            comments = int(data_dict.get('comments', 0))
            shares = int(data_dict.get('shares', 0))
            saves = int(data_dict.get('saves', 0))
            create_time = int(data_dict.get('create_time', 0))

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
                video_id, data_dict.get('link', ''), data_dict.get('caption', ''),
                views, likes, comments, shares, saves, create_time,
                data_dict.get('scrape_date', datetime.now().date().isoformat()),
                data_dict.get('top1_cmt', ''), int(data_dict.get('top1_likes', 0)),
                data_dict.get('top2_cmt', ''), int(data_dict.get('top2_likes', 0)),
                data_dict.get('top3_cmt', ''), int(data_dict.get('top3_likes', 0)),
                data_dict.get('top4_cmt', ''), int(data_dict.get('top4_likes', 0)),
                data_dict.get('top5_cmt', ''), int(data_dict.get('top5_likes', 0))
            ))
            conn.commit()
            return True
    except Exception as e:
        conn.rollback()
        return False
    finally:
        conn.close()

def is_scraped(video_id):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('SELECT 1 FROM history WHERE video_id = %s', (video_id,))
            return cursor.fetchone() is not None
    finally:
        conn.close()

def mark_as_scraped(video_id):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('INSERT INTO history (video_id) VALUES (%s) ON CONFLICT DO NOTHING', (video_id,))
            conn.commit()
    finally:
        conn.close()

def extract_video_id(url: str):
    """
    Trích xuất Video ID từ TikTok URL.
    Ví dụ: https://www.tiktok.com/@abc/video/123456789 -> 123456789
    """
    if not url:
        return None
    try:
        if "/video/" in url:
            return url.split("/video/")[1].split("?")[0].strip("/")
        return None
    except Exception:
        return None

def get_pending_videos():
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT * FROM videos WHERE ai_status = 'pending' AND views > 0 ORDER BY scrape_date DESC")
            return cursor.fetchall()
    finally:
        conn.close()

def update_ai_results(video_id, res):
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
        conn.rollback()
    finally:
        conn.close()

def get_recent_videos(days=14):
    cutoff = (datetime.now() - timedelta(days=days)).date().isoformat()
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT * FROM videos WHERE scrape_date >= %s AND ai_status = 'completed' AND views > 0", (cutoff,))
            return cursor.fetchall()
    finally:
        conn.close()

def reset_all_analysis_status():
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE videos SET ai_status = 'pending'")
            conn.commit()
    finally:
        conn.close()

# ==========================================
# BACKEND API DATA LOGIC
# ==========================================

def get_all_analyzed_videos(page: int = 1, per_page: int = 20,
                            category: str = None, sentiment: str = None,
                            search: str = None, sort_by: str = "viral_probability",
                            sort_order: str = "desc", min_viral: float = 0):
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            where_clauses = ["views > 0"]
            params = []

            if category:
                where_clauses.append("category = %s")
                params.append(category)
            if sentiment:
                where_clauses.append("video_sentiment = %s")
                params.append(sentiment)
            if search:
                where_clauses.append("(caption ILIKE %s OR video_description ILIKE %s OR top_keywords ILIKE %s)")
                like = f"%{search}%"
                params.extend([like, like, like])
            if min_viral > 0:
                where_clauses.append("viral_probability >= %s")
                params.append(min_viral)

            where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
            valid_sorts = {"viral_probability", "views", "likes", "engagement_rate", "viral_velocity", "views_per_hour", "positive_score", "scrape_date", "comments", "shares"}
            if sort_by not in valid_sorts: sort_by = "viral_probability"
            order = "DESC" if sort_order.lower() == "desc" else "ASC"

            cur.execute(f"SELECT COUNT(*) as total FROM videos WHERE {where_sql}", params)
            total = cur.fetchone()["total"]

            offset = (page - 1) * per_page
            cur.execute(f"SELECT * FROM videos WHERE {where_sql} ORDER BY {sort_by} {order} NULLS LAST LIMIT %s OFFSET %s", params + [per_page, offset])
            return cur.fetchall(), total
    finally:
        conn.close()

def get_video_by_id(video_id: str):
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM videos WHERE video_id = %s", (video_id,))
            return cur.fetchone()
    finally:
        conn.close()

def get_dashboard_stats():
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT COUNT(*) as total_videos, COALESCE(SUM(views), 0) as total_views, COALESCE(SUM(likes), 0) as total_likes, COALESCE(SUM(comments), 0) as total_comments, COALESCE(SUM(shares), 0) as total_shares, COALESCE(SUM(saves), 0) as total_saves, COALESCE(AVG(CASE WHEN engagement_rate < 100 THEN engagement_rate END), 0) as avg_engagement, COALESCE(AVG(views_per_hour), 0) as avg_vph, COALESCE(AVG(viral_velocity), 0) as avg_velocity, COUNT(CASE WHEN viral_probability > 50 THEN 1 END) as viral_count, COUNT(DISTINCT scrape_date) as scrape_days FROM videos WHERE views > 0
            """)
            return cur.fetchone()
    finally:
        conn.close()

def get_category_stats():
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT category, COUNT(*) as count, COALESCE(AVG(viral_velocity), 0) as avg_velocity, COALESCE(AVG(viral_probability), 0) as avg_viral, COALESCE(AVG(engagement_rate), 0) as avg_engagement, COALESCE(SUM(views), 0) as total_views FROM videos WHERE views > 0 AND category IS NOT NULL GROUP BY category ORDER BY avg_velocity DESC
            """)
            return cur.fetchall()
    finally:
        conn.close()

def get_sentiment_stats():
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT video_sentiment, COUNT(*) as count FROM videos WHERE views > 0 AND video_sentiment IS NOT NULL GROUP BY video_sentiment")
            return cur.fetchall()
    finally:
        conn.close()

def get_top_keywords(limit: int = 30):
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT top_keywords FROM videos WHERE views > 0 AND top_keywords IS NOT NULL AND top_keywords != ''")
            rows = cur.fetchall()
            from collections import Counter
            kw_counter = Counter()
            for row in rows:
                kws = row["top_keywords"]
                if kws:
                    for k in kws.split(","):
                        k = k.strip()
                        if k: kw_counter[k] += 1
            return [{"keyword": k, "count": c} for k, c in kw_counter.most_common(limit)]
    finally:
        conn.close()

def get_timeline_data():
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT scrape_date, COUNT(*) as video_count, COALESCE(AVG(views), 0) as avg_views, COALESCE(AVG(viral_probability), 0) as avg_viral FROM videos WHERE views > 0 AND scrape_date IS NOT NULL GROUP BY scrape_date ORDER BY scrape_date DESC LIMIT 30")
            return cur.fetchall()
    finally:
        conn.close()

def insert_user_video(video_id: str, url: str):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO videos (video_id, link, ai_status, scrape_date, views) VALUES (%s, %s, 'user_pending', CURRENT_DATE, 0) ON CONFLICT (video_id) DO NOTHING", (video_id, url))
            conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
