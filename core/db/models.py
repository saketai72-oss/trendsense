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
                    category TEXT[],
                    video_description TEXT,
                    ai_status VARCHAR(20) DEFAULT 'pending',
                    is_rescraped BOOLEAN DEFAULT FALSE
                )
            ''')
            # Trend Alignment Score columns (kept for backward compat during migration)
            for col_sql in [
                "ALTER TABLE videos ADD COLUMN IF NOT EXISTS video_duration REAL",
                "ALTER TABLE videos ADD COLUMN IF NOT EXISTS video_orientation VARCHAR(10)",
                "ALTER TABLE videos ADD COLUMN IF NOT EXISTS scene_cut_count INTEGER",
                "ALTER TABLE videos ADD COLUMN IF NOT EXISTS trend_alignment_score REAL",
                "ALTER TABLE videos ADD COLUMN IF NOT EXISTS trend_insights JSONB",
                "ALTER TABLE videos ADD COLUMN IF NOT EXISTS audio_transcript TEXT",
                "ALTER TABLE videos ADD COLUMN IF NOT EXISTS user_id UUID",
            ]:
                try:
                    cursor.execute(col_sql)
                except Exception:
                    pass  # Column may already exist

            # ── Users table ──
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255),
                    display_name VARCHAR(100),
                    avatar_url TEXT,
                    auth_provider VARCHAR(20) DEFAULT 'local',
                    provider_id VARCHAR(255),
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            ''')

            # ── Refresh tokens table ──
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS refresh_tokens (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    token_hash VARCHAR(255) UNIQUE NOT NULL,
                    expires_at TIMESTAMPTZ NOT NULL,
                    revoked BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            ''')

            # ── Video analyses table (upload-specific analysis data) ──
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS video_analyses (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    video_id TEXT UNIQUE NOT NULL,
                    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
                    video_duration REAL,
                    video_orientation VARCHAR(10),
                    scene_cut_count INTEGER,
                    trend_alignment_score REAL,
                    trend_insights JSONB,
                    audio_transcript TEXT,
                    video_description TEXT,
                    top_keywords TEXT,
                    video_sentiment TEXT,
                    positive_score REAL DEFAULT 0,
                    category TEXT[],
                    ai_status VARCHAR(20) DEFAULT 'pending',
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            ''')

            # Indexes
            for idx_sql in [
                'CREATE INDEX IF NOT EXISTS idx_is_rescraped ON videos(is_rescraped)',
                'CREATE INDEX IF NOT EXISTS idx_ai_status ON videos(ai_status)',
                'CREATE INDEX IF NOT EXISTS idx_scrape_date ON videos(scrape_date)',
                'CREATE INDEX IF NOT EXISTS idx_category ON videos(category)',
                'CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)',
                'CREATE INDEX IF NOT EXISTS idx_users_provider ON users(auth_provider, provider_id)',
                'CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id)',
                'CREATE INDEX IF NOT EXISTS idx_refresh_tokens_hash ON refresh_tokens(token_hash)',
                'CREATE INDEX IF NOT EXISTS idx_video_analyses_video ON video_analyses(video_id)',
                'CREATE INDEX IF NOT EXISTS idx_video_analyses_user ON video_analyses(user_id)',
                'CREATE INDEX IF NOT EXISTS idx_video_analyses_status ON video_analyses(ai_status)',
                'CREATE INDEX IF NOT EXISTS idx_videos_user ON videos(user_id)',
            ]:
                try:
                    cursor.execute(idx_sql)
                except Exception:
                    pass

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

            # Kiểm tra xem có bình luận mới hay không
            has_new_comments = any(
                str(data_dict.get(f'top{i}_cmt', '')).strip() for i in range(1, 6)
            )

            if has_new_comments:
                # Có bình luận mới → cập nhật cả comments và reset ai_status để phân tích lại
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
                        caption = EXCLUDED.caption,
                        top1_cmt = EXCLUDED.top1_cmt,
                        top1_likes = EXCLUDED.top1_likes,
                        top2_cmt = EXCLUDED.top2_cmt,
                        top2_likes = EXCLUDED.top2_likes,
                        top3_cmt = EXCLUDED.top3_cmt,
                        top3_likes = EXCLUDED.top3_likes,
                        top4_cmt = EXCLUDED.top4_cmt,
                        top4_likes = EXCLUDED.top4_likes,
                        top5_cmt = EXCLUDED.top5_cmt,
                        top5_likes = EXCLUDED.top5_likes,
                        ai_status = 'pending'
                '''
            else:
                # Không có bình luận mới → chỉ cập nhật stats cơ bản, giữ nguyên comments cũ
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

def delete_video(video_id):
    """Xóa video khỏi DB và history khi link chết hoặc rác"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM videos WHERE video_id = %s", (video_id,))
            cursor.execute("DELETE FROM history WHERE video_id = %s", (video_id,))
            conn.commit()
            print(f"  [🗑️] Đã xóa video {video_id} khỏi database.")
            return True
    except Exception as e:
        print(f"[ERROR] Failed to delete video {video_id}: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def get_all_video_links():
    """Lấy toàn bộ link video và bình luận hiện có để phục vụ detect language fallback"""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT video_id, link, caption, 
                       top1_cmt, top2_cmt, top3_cmt, top4_cmt, top5_cmt 
                FROM videos 
                ORDER BY scrape_date DESC
            """)
            return cursor.fetchall()
    finally:
        conn.close()

def update_rescraped_stats_only(video_id, data_dict):
    """
    Chỉ cập nhật stats cơ bản, giữ nguyên bình luận cũ.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            query = '''
                UPDATE videos SET
                    caption = %s, views = %s, likes = %s, comments = %s,
                    shares = %s, saves = %s, create_time = %s,
                    scrape_date = %s, is_rescraped = TRUE
                WHERE video_id = %s
            '''
            cursor.execute(query, (
                data_dict.get('caption', ''),
                int(data_dict.get('views', 0)),
                int(data_dict.get('likes', 0)),
                int(data_dict.get('comments', 0)),
                int(data_dict.get('shares', 0)),
                int(data_dict.get('saves', 0)),
                int(data_dict.get('create_time', 0)),
                data_dict.get('scrape_date', datetime.now().date().isoformat()),
                video_id
            ))
            conn.commit()
            return True
    except Exception as e:
        print(f"[ERROR] Failed to update stats for {video_id}: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def update_rescraped_metadata(video_id, data_dict):
    """
    Cập nhật data sau khi cào lại, đánh dấu is_rescraped = True.
    Reset ai_status về 'pending' để pipeline AI phân tích lại.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            query = '''
                UPDATE videos SET
                    caption = %s, views = %s, likes = %s, comments = %s,
                    shares = %s, saves = %s, create_time = %s,
                    scrape_date = %s, is_rescraped = TRUE,
                    top1_cmt = %s, top1_likes = %s,
                    top2_cmt = %s, top2_likes = %s,
                    top3_cmt = %s, top3_likes = %s,
                    top4_cmt = %s, top4_likes = %s,
                    top5_cmt = %s, top5_likes = %s,
                    ai_status = 'pending'
                WHERE video_id = %s
            '''
            cursor.execute(query, (
                data_dict.get('caption', ''),
                int(data_dict.get('views', 0)),
                int(data_dict.get('likes', 0)),
                int(data_dict.get('comments', 0)),
                int(data_dict.get('shares', 0)),
                int(data_dict.get('saves', 0)),
                int(data_dict.get('create_time', 0)),
                data_dict.get('scrape_date', datetime.now().date().isoformat()),
                data_dict.get('top1_cmt', ''), int(data_dict.get('top1_likes', 0)),
                data_dict.get('top2_cmt', ''), int(data_dict.get('top2_likes', 0)),
                data_dict.get('top3_cmt', ''), int(data_dict.get('top3_likes', 0)),
                data_dict.get('top4_cmt', ''), int(data_dict.get('top4_likes', 0)),
                data_dict.get('top5_cmt', ''), int(data_dict.get('top5_likes', 0)),
                video_id
            ))
            conn.commit()
            return True
    except Exception as e:
        print(f"[ERROR] Failed to update rescraped video {video_id}: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def get_high_potential_videos(threshold=40.0):
    """Lấy danh sách video có tiềm năng viral cao (> threshold)"""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT * FROM videos 
                WHERE viral_probability > %s OR engagement_rate > %s
                ORDER BY viral_probability DESC
            """, (threshold, threshold))
            return cursor.fetchall()
    finally:
        conn.close()

def update_viral_metrics_only(video_id, res):
    """
    Chỉ cập nhật các chỉ số toán học và sentiment, giữ nguyên category và description.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            query = '''
                UPDATE videos SET
                    video_sentiment = %s, positive_score = %s, views_per_hour = %s,
                    engagement_rate = %s, viral_velocity = %s, viral_probability = %s,
                    ai_status = 'completed'
                WHERE video_id = %s
            '''
            cursor.execute(query, (
                res.get('video_sentiment'), res.get('positive_score', 0), res.get('views_per_hour', 0),
                res.get('engagement_rate', 0), res.get('viral_velocity', 0), res.get('viral_probability', 0),
                video_id
            ))
            conn.commit()
            return True
    except Exception as e:
        print(f"[ERROR] Failed to update viral metrics for {video_id}: {e}")
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
                    ai_status = %s
                WHERE video_id = %s
            '''
            cat_str = res.get('category', '')
            cat_list = [c.strip() for c in cat_str.split('|')] if cat_str else []
            
            ai_status = res.get('ai_status', 'completed')
            
            cursor.execute(query, (
                cat_list, res.get('video_description'), res.get('top_keywords'),
                res.get('video_sentiment'), res.get('positive_score', 0), res.get('views_per_hour', 0),
                res.get('engagement_rate', 0), res.get('viral_velocity', 0), res.get('viral_probability', 0),
                ai_status, video_id
            ))
            conn.commit()
    except Exception as e:
        conn.rollback()
    finally:
        conn.close()


def get_videos_for_vision_analysis():
    """Lấy danh sách video cần phân tích bằng Multimodal AI (Thị giác máy tính)."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Ưu tiên video chưa có transcript hoặc status là vision_pending
            cursor.execute("""
                SELECT video_id, caption 
                FROM videos 
                WHERE (ai_status = 'pending' OR ai_status = 'vision_pending')
                ORDER BY scrape_date DESC 
                LIMIT 50
            """)
            rows = cursor.fetchall()
            # Ở môi trường local, video được tải về thư mục 'downloads/'
            import os
            for r in rows:
                # Type safe: video_id is str
                r['video_path'] = os.path.abspath(f"downloads/{r['video_id']}.mp4")
            return rows
    finally:
        conn.close()


def update_vision_results(video_id: str, summary: str, category: str | None = None, 
                         transcript: str | None = None, ocr: str | None = None, 
                         blip: str | None = None):
    """Cập nhật kết quả phân tích thị giác vào DB."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # Nếu chỉ có summary là chuỗi lỗi (truyền 2 tham số)
            if category is None:
                cursor.execute("UPDATE videos SET ai_status = 'error', video_description = %s WHERE video_id = %s", (summary, video_id))
            else:
                import json
                trend_insights = json.dumps({
                    "ocr_text": ocr,
                    "blip_caption": blip
                }, ensure_ascii=False)
                
                cat_list = [c.strip() for c in category.split('|')] if category else []
                
                cursor.execute("""
                    UPDATE videos SET
                        video_description = %s,
                        category = %s,
                        audio_transcript = %s,
                        trend_insights = %s,
                        ai_status = 'completed'
                    WHERE video_id = %s
                """, (summary, cat_list, transcript, trend_insights, video_id))
            conn.commit()
    finally:
        conn.close()

def get_recent_videos(days=14):
    cutoff = (datetime.now() - timedelta(days=days)).date().isoformat()
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Chỉ lấy các cột cần thiết cho Training để tránh timeout và tốn RAM
            columns = [
                "video_id", "views", "likes", "comments", "shares", "saves", 
                "viral_velocity", "views_per_hour", "positive_score", 
                "video_duration", "scene_cut_count", "video_orientation", 
                "category", "top_keywords"
            ]
            query = f"SELECT {', '.join(columns)} FROM videos WHERE scrape_date >= %s AND ai_status = 'completed' AND views > 0"
            cursor.execute(query, (cutoff,))
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
                            categories: list | None = None, sentiment: str | None = None,
                            search: str | None = None, sort_by: str = "viral_probability",
                            sort_order: str = "desc", min_viral: float = 0,
                            semantic_video_ids: list | None = None):
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            where_clauses = ["views > 0", "ai_status = 'completed'"]
            params = []

            if categories:
                where_clauses.append("category && %s::TEXT[]")
                params.append(categories)
            if sentiment:
                where_clauses.append("video_sentiment = %s")
                params.append(sentiment)
            if semantic_video_ids is not None:
                if len(semantic_video_ids) == 0:
                    # Semantic search yielded no results
                    where_clauses.append("1=0")
                else:
                    where_clauses.append("video_id = ANY(%s)")
                    params.append(semantic_video_ids)
            elif search:
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
            count_row = cur.fetchone()
            total = count_row["total"] if count_row else 0

            offset = (page - 1) * per_page
            # Khi có semantic search, giữ nguyên thứ tự cosine similarity
            # thay vì ghi đè bằng sort_by (mặc định viral_probability)
            if semantic_video_ids is not None and len(semantic_video_ids) > 0:
                order_clause = "array_position(%s::text[], video_id)"
                cur.execute(f"SELECT * FROM videos WHERE {where_sql} ORDER BY {order_clause} LIMIT %s OFFSET %s", params + [semantic_video_ids, per_page, offset])
            else:
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
                SELECT unnest(category) as category, COUNT(*) as count, COALESCE(AVG(viral_velocity), 0) as avg_velocity, COALESCE(AVG(viral_probability), 0) as avg_viral, COALESCE(AVG(engagement_rate), 0) as avg_engagement, COALESCE(SUM(views), 0) as total_views FROM videos WHERE views > 0 AND category IS NOT NULL GROUP BY unnest(category) ORDER BY avg_velocity DESC
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

def insert_user_video(video_id: str, url: str, user_id: str | None = None):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO videos (video_id, link, ai_status, scrape_date, views, user_id) "
                "VALUES (%s, %s, 'user_pending', CURRENT_DATE, 0, %s) "
                "ON CONFLICT (video_id) DO NOTHING",
                (video_id, url, user_id)
            )
            conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


# ==========================================
# TREND ALIGNMENT BENCHMARK QUERIES
# ==========================================

def get_trending_categories(days=14):
    """Top categories theo avg viral_velocity trong N ngày gần nhất."""
    cutoff = (datetime.now() - timedelta(days=days)).date().isoformat()
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT unnest(category) as category,
                       COUNT(*) as count,
                       COALESCE(AVG(viral_velocity), 0) as avg_velocity,
                       COALESCE(AVG(engagement_rate), 0) as avg_engagement
                FROM videos
                WHERE views > 0 AND ai_status = 'completed'
                  AND scrape_date >= %s AND category IS NOT NULL
                GROUP BY unnest(category)
                ORDER BY avg_velocity DESC
            """, (cutoff,))
            return cur.fetchall()
    finally:
        conn.close()


def get_trending_keywords(days=14, limit=50):
    """Top keywords từ video viral (velocity > median) trong N ngày gần nhất."""
    cutoff = (datetime.now() - timedelta(days=days)).date().isoformat()
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT top_keywords FROM videos
                WHERE views > 0 AND ai_status = 'completed'
                  AND scrape_date >= %s
                  AND top_keywords IS NOT NULL AND top_keywords != ''
                  AND viral_velocity > (
                      SELECT COALESCE(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY viral_velocity), 0)
                      FROM videos WHERE views > 0 AND scrape_date >= %s
                  )
            """, (cutoff, cutoff))
            rows = cur.fetchall()
            from collections import Counter
            kw_counter = Counter()
            for row in rows:
                for k in row["top_keywords"].split(","):
                    k = k.strip()
                    if k:
                        kw_counter[k] += 1
            return [{"keyword": k, "count": c} for k, c in kw_counter.most_common(limit)]
    finally:
        conn.close()


def get_duration_stats_by_category(days=14):
    """Thống kê MEDIAN duration của video viral vs tất cả, theo category."""
    cutoff = (datetime.now() - timedelta(days=days)).date().isoformat()
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    unnest(category) as category,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY video_duration) as median_duration,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (
                        ORDER BY CASE WHEN viral_velocity > 0 THEN video_duration END
                    ) as viral_median_duration,
                    COUNT(*) as sample_count
                FROM videos
                WHERE views > 0 AND ai_status = 'completed'
                  AND scrape_date >= %s AND category IS NOT NULL
                  AND video_duration IS NOT NULL AND video_duration > 0
                GROUP BY unnest(category)
                HAVING COUNT(*) >= 3
                ORDER BY viral_median_duration ASC NULLS LAST
            """, (cutoff,))
            return cur.fetchall()
    finally:
        conn.close()


def get_viral_audio_transcripts(days=14, limit=30):
    """Lấy audio transcript của top video viral gần nhất."""
    cutoff = (datetime.now() - timedelta(days=days)).date().isoformat()
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT video_id, audio_transcript, viral_velocity
                FROM videos
                WHERE views > 0 AND ai_status = 'completed'
                  AND scrape_date >= %s
                  AND audio_transcript IS NOT NULL
                  AND audio_transcript != ''
                  AND audio_transcript != 'Không nghe được tiếng.'
                  AND audio_transcript != 'Không có âm thanh.'
                ORDER BY viral_velocity DESC
                LIMIT %s
            """, (cutoff, limit))
            return cur.fetchall()
    finally:
        conn.close()


def update_upload_analysis(video_id, results):
    """Cập nhật kết quả Trend Alignment Score cho video upload.
    Writes to video_analyses table (split from videos)."""
    import json
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Upsert into video_analyses
            cur.execute("""
                INSERT INTO video_analyses (
                    video_id, user_id, category, video_description, top_keywords,
                    video_sentiment, positive_score, video_duration, video_orientation,
                    scene_cut_count, trend_alignment_score, trend_insights,
                    audio_transcript, ai_status
                ) VALUES (
                    %s,
                    (SELECT user_id FROM videos WHERE video_id = %s),
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (video_id) DO UPDATE SET
                    category = EXCLUDED.category,
                    video_description = EXCLUDED.video_description,
                    top_keywords = EXCLUDED.top_keywords,
                    video_sentiment = EXCLUDED.video_sentiment,
                    positive_score = EXCLUDED.positive_score,
                    video_duration = EXCLUDED.video_duration,
                    video_orientation = EXCLUDED.video_orientation,
                    scene_cut_count = EXCLUDED.scene_cut_count,
                    trend_alignment_score = EXCLUDED.trend_alignment_score,
                    trend_insights = EXCLUDED.trend_insights,
                    audio_transcript = EXCLUDED.audio_transcript,
                    ai_status = EXCLUDED.ai_status,
                    updated_at = NOW()
            """, (
                video_id, video_id,
                results.get('category', []),
                results.get('video_description', ''),
                results.get('top_keywords', ''),
                results.get('video_sentiment', '🟡 TRUNG LẬP'),
                results.get('positive_score', 0),
                results.get('video_duration'),
                results.get('video_orientation'),
                results.get('scene_cut_count'),
                results.get('trend_alignment_score'),
                json.dumps(results.get('trend_insights', {}), ensure_ascii=False),
                results.get('audio_transcript', ''),
                results.get('ai_status', 'completed'),
            ))

            # Also update ai_status on videos table for Supabase Realtime
            cur.execute(
                "UPDATE videos SET ai_status = %s WHERE video_id = %s",
                (results.get('ai_status', 'completed'), video_id)
            )
            conn.commit()
    except Exception as e:
        print(f"[ERROR] Failed to update upload analysis for {video_id}: {e}")
        conn.rollback()
    finally:
        conn.close()


# ==========================================
# AUTHENTICATION — USER CRUD
# ==========================================

def create_user(email: str, password_hash: str | None = None, display_name: str | None = None,
                avatar_url: str | None = None, auth_provider: str = "local",
                provider_id: str | None = None):
    """Create a new user. Returns the user dict or None on failure."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO users (email, password_hash, display_name, avatar_url,
                                   auth_provider, provider_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING *
            """, (email, password_hash, display_name, avatar_url, auth_provider, provider_id))
            user = cur.fetchone()
            conn.commit()
            return dict(user) if user else None
    except Exception as e:
        print(f"[ERROR] Failed to create user: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()


def get_user_by_id(user_id: str | None):
    """Get user by UUID."""
    if not user_id:
        return None
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE id = %s AND is_active = TRUE", (user_id,))
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_email(email: str | None):
    """Get user by email address."""
    if not email:
        return None
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE email = %s", (email,))
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_provider(provider: str, provider_id: str):
    """Get user by OAuth provider and provider ID."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM users WHERE auth_provider = %s AND provider_id = %s",
                (provider, provider_id)
            )
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def update_user_login(user_id: str | None):
    """Update the user's last activity timestamp."""
    if not user_id:
        return
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET updated_at = NOW() WHERE id = %s",
                (user_id,)
            )
            conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()


def link_oauth_provider(user_id: str | None, provider: str, provider_id: str, avatar_url: str | None = None):
    """Link an OAuth provider to an existing user account."""
    if not user_id:
        return
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE users SET
                    auth_provider = %s, provider_id = %s,
                    avatar_url = COALESCE(%s, avatar_url),
                    updated_at = NOW()
                WHERE id = %s
            """, (provider, provider_id, avatar_url, user_id))
            conn.commit()
    except Exception as e:
        print(f"[ERROR] Failed to link OAuth provider: {e}")
        conn.rollback()
    finally:
        conn.close()


# ── Refresh Token Management ─────────────────────────────────────────────────

def store_refresh_token(user_id: str, token_hash: str, expires_at):
    """Store a hashed refresh token in the database."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
                VALUES (%s, %s, %s)
            """, (user_id, token_hash, expires_at))
            conn.commit()
    except Exception as e:
        print(f"[ERROR] Failed to store refresh token: {e}")
        conn.rollback()
    finally:
        conn.close()


def get_refresh_token(token_hash: str):
    """Get a refresh token by its hash."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM refresh_tokens WHERE token_hash = %s AND expires_at > NOW()",
                (token_hash,)
            )
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def revoke_refresh_token(token_hash: str):
    """Revoke a single refresh token."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE refresh_tokens SET revoked = TRUE WHERE token_hash = %s",
                (token_hash,)
            )
            conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()


def revoke_all_user_tokens(user_id: str):
    """Revoke all refresh tokens for a user (logout from all devices)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE refresh_tokens SET revoked = TRUE WHERE user_id = %s AND revoked = FALSE",
                (user_id,)
            )
            conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()


def cleanup_expired_tokens():
    """Delete expired and revoked refresh tokens (run periodically)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM refresh_tokens WHERE expires_at < NOW() OR revoked = TRUE"
            )
            conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()


# ── Video Analyses Queries ───────────────────────────────────────────────────

def get_video_analysis(video_id: str):
    """Get upload analysis results for a video from video_analyses table."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM video_analyses WHERE video_id = %s", (video_id,))
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def get_user_videos(user_id: str, page: int = 1, per_page: int = 20):
    """Get paginated list of videos uploaded by a user with full analysis results."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            offset = (page - 1) * per_page
            cur.execute("""
                SELECT v.video_id, v.link, v.caption, v.scrape_date, v.ai_status,
                       va.trend_alignment_score, va.video_sentiment, va.category,
                       va.video_description, va.positive_score, va.created_at as analyzed_at,
                       va.video_duration, va.video_orientation, va.scene_cut_count,
                       va.trend_insights, va.audio_transcript, va.top_keywords
                FROM videos v
                LEFT JOIN video_analyses va ON v.video_id = va.video_id
                WHERE v.user_id = %s
                ORDER BY v.scrape_date DESC
                LIMIT %s OFFSET %s
            """, (user_id, per_page, offset))
            rows = cur.fetchall()

            cur.execute(
                "SELECT COUNT(*) as total FROM videos WHERE user_id = %s",
                (user_id,)
            )
            count_row = cur.fetchone()
            total = count_row["total"] if count_row else 0

            return [dict(r) for r in rows], total
    finally:
        conn.close()


def delete_user_video(video_id: str, user_id: str) -> bool:
    """Delete a video and its analysis. Only deletes if the video belongs to the user."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM video_analyses WHERE video_id = %s AND user_id = %s",
                (video_id, user_id)
            )
            cur.execute(
                "DELETE FROM videos WHERE video_id = %s AND user_id = %s",
                (video_id, user_id)
            )
            conn.commit()
            return cur.rowcount > 0
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()
