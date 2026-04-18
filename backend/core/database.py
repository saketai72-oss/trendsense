"""
Database layer for the backend API.
Connects to Supabase PostgreSQL and provides query functions.
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from backend.config.settings import DATABASE_URL


def get_connection():
    """Tạo kết nối tới Supabase PostgreSQL"""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn


def get_all_analyzed_videos(page: int = 1, per_page: int = 20,
                            category: str = None, sentiment: str = None,
                            search: str = None, sort_by: str = "viral_probability",
                            sort_order: str = "desc", min_viral: float = 0):
    """
    Lấy video đã phân tích với phân trang + lọc.
    Trả về (list[dict], total_count).
    """
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

            where_sql = " AND ".join(where_clauses)

            # Valid sort columns
            valid_sorts = {
                "viral_probability", "views", "likes", "engagement_rate",
                "viral_velocity", "views_per_hour", "positive_score",
                "scrape_date", "comments", "shares"
            }
            if sort_by not in valid_sorts:
                sort_by = "viral_probability"

            order = "DESC" if sort_order.lower() == "desc" else "ASC"

            # Count total
            cur.execute(f"SELECT COUNT(*) as total FROM videos WHERE {where_sql}", params)
            total = cur.fetchone()["total"]

            # Fetch page
            offset = (page - 1) * per_page
            cur.execute(
                f"""SELECT * FROM videos WHERE {where_sql}
                    ORDER BY {sort_by} {order} NULLS LAST
                    LIMIT %s OFFSET %s""",
                params + [per_page, offset]
            )
            rows = cur.fetchall()

            return rows, total
    finally:
        conn.close()


def get_video_by_id(video_id: str):
    """Lấy chi tiết 1 video."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM videos WHERE video_id = %s", (video_id,))
            return cur.fetchone()
    finally:
        conn.close()


def get_dashboard_stats():
    """Lấy thống kê tổng quan cho dashboard."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    COUNT(*) as total_videos,
                    COALESCE(SUM(views), 0) as total_views,
                    COALESCE(SUM(likes), 0) as total_likes,
                    COALESCE(SUM(comments), 0) as total_comments,
                    COALESCE(SUM(shares), 0) as total_shares,
                    COALESCE(SUM(saves), 0) as total_saves,
                    COALESCE(AVG(CASE WHEN engagement_rate < 100 THEN engagement_rate END), 0) as avg_engagement,
                    COALESCE(AVG(views_per_hour), 0) as avg_vph,
                    COALESCE(AVG(viral_velocity), 0) as avg_velocity,
                    COUNT(CASE WHEN viral_probability > 50 THEN 1 END) as viral_count,
                    COUNT(DISTINCT scrape_date) as scrape_days
                FROM videos WHERE views > 0
            """)
            return cur.fetchone()
    finally:
        conn.close()


def get_category_stats():
    """Lấy thống kê theo danh mục."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    category,
                    COUNT(*) as count,
                    COALESCE(AVG(viral_velocity), 0) as avg_velocity,
                    COALESCE(AVG(viral_probability), 0) as avg_viral,
                    COALESCE(AVG(engagement_rate), 0) as avg_engagement,
                    COALESCE(SUM(views), 0) as total_views
                FROM videos
                WHERE views > 0 AND category IS NOT NULL
                GROUP BY category
                ORDER BY avg_velocity DESC
            """)
            return cur.fetchall()
    finally:
        conn.close()


def get_sentiment_stats():
    """Lấy thống kê cảm xúc."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT video_sentiment, COUNT(*) as count
                FROM videos
                WHERE views > 0 AND video_sentiment IS NOT NULL
                GROUP BY video_sentiment
            """)
            return cur.fetchall()
    finally:
        conn.close()


def get_top_keywords(limit: int = 30):
    """Lấy top keywords từ tất cả video."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT top_keywords FROM videos
                WHERE views > 0 AND top_keywords IS NOT NULL AND top_keywords != ''
            """)
            rows = cur.fetchall()

            # Aggregate keywords
            from collections import Counter
            kw_counter = Counter()
            for row in rows:
                kws = row["top_keywords"]
                if kws:
                    for k in kws.split(","):
                        k = k.strip()
                        if k:
                            kw_counter[k] += 1

            return [{"keyword": k, "count": c} for k, c in kw_counter.most_common(limit)]
    finally:
        conn.close()


def get_timeline_data():
    """Lấy dữ liệu timeline theo ngày."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    scrape_date,
                    COUNT(*) as video_count,
                    COALESCE(AVG(views), 0) as avg_views,
                    COALESCE(AVG(viral_probability), 0) as avg_viral
                FROM videos
                WHERE views > 0 AND scrape_date IS NOT NULL
                GROUP BY scrape_date
                ORDER BY scrape_date DESC
                LIMIT 30
            """)
            return cur.fetchall()
    finally:
        conn.close()


def insert_user_video(video_id: str, url: str):
    """Insert a user-submitted video for on-demand analysis."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO videos (video_id, link, ai_status, scrape_date, views)
                VALUES (%s, %s, 'user_pending', CURRENT_DATE, 0)
                ON CONFLICT (video_id) DO NOTHING
            """, (video_id, url))
            conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
