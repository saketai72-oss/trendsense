"""
Migration 004: Move upload analysis data from videos → video_analyses
=====================================================================
Chạy SAU khi deploy code mới (Modal + Backend).
An toàn chạy lại nhiều lần (idempotent).

Usage:
    python scripts/migrate_004_upload_to_analyses.py
"""
import psycopg2
import sys

sys.stdout.reconfigure(line_buffering=True)

DB = "postgresql://postgres.fnsygsoohvnaxacirhwf:taidinhtrai@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres"

conn = psycopg2.connect(DB, connect_timeout=30)
conn.autocommit = True
cur = conn.cursor()

# ── Step 1: Migrate upload data from videos → video_analyses ──
print("[1] Migrating upload analysis data to video_analyses ...", flush=True)
try:
    cur.execute("""
        INSERT INTO video_analyses (
            video_id, user_id, category, video_description, top_keywords,
            video_sentiment, positive_score, video_duration, video_orientation,
            scene_cut_count, trend_alignment_score, trend_insights,
            audio_transcript, ai_status
        )
        SELECT
            v.video_id,
            v.user_id,
            COALESCE(v.category, '{}'),
            COALESCE(v.video_description, ''),
            COALESCE(v.top_keywords, ''),
            COALESCE(v.video_sentiment, '🟡 TRUNG LẬP'),
            COALESCE(v.positive_score, 0),
            v.video_duration,
            v.video_orientation,
            v.scene_cut_count,
            v.trend_alignment_score,
            v.trend_insights,
            COALESCE(v.audio_transcript, ''),
            COALESCE(v.ai_status, 'completed')
        FROM videos v
        WHERE v.video_id LIKE 'upload_%%'
          AND v.ai_status IN ('completed', 'error')
        ON CONFLICT (video_id) DO UPDATE SET
            user_id = COALESCE(EXCLUDED.user_id, video_analyses.user_id),
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
    """)
    print(f"  [OK] Rows upserted: {cur.rowcount}", flush=True)
except Exception as e:
    print(f"  [ERR] {e}", flush=True)

# ── Step 2: Clean up analysis columns in videos (set to defaults) ──
print("\n[2] Cleaning analysis columns in videos table ...", flush=True)
try:
    cur.execute("""
        UPDATE videos SET
            video_description = NULL,
            top_keywords = NULL,
            video_sentiment = NULL,
            positive_score = 0,
            video_duration = NULL,
            video_orientation = NULL,
            scene_cut_count = NULL,
            trend_alignment_score = NULL,
            trend_insights = NULL,
            audio_transcript = NULL
        WHERE video_id LIKE 'upload_%%'
          AND ai_status IN ('completed', 'error')
          AND video_id IN (SELECT video_id FROM video_analyses)
    """)
    print(f"  [OK] Rows cleaned: {cur.rowcount}", flush=True)
except Exception as e:
    print(f"  [ERR] {e}", flush=True)

# ── Step 3: Verify ──
print("\n--- VERIFICATION ---", flush=True)

cur.execute("SELECT COUNT(*) FROM video_analyses")
print(f"  video_analyses total: {cur.fetchone()[0]}", flush=True)

cur.execute("SELECT COUNT(*) FROM video_analyses WHERE video_id LIKE 'upload_%%'")
print(f"  video_analyses (upload): {cur.fetchone()[0]}", flush=True)

cur.execute("SELECT COUNT(*) FROM videos WHERE video_id LIKE 'upload_%%' AND ai_status IN ('completed','error')")
print(f"  videos (upload completed/error): {cur.fetchone()[0]}", flush=True)

cur.execute("""
    SELECT COUNT(*) FROM videos v
    WHERE v.video_id LIKE 'upload_%%'
      AND v.ai_status IN ('completed','error')
      AND NOT EXISTS (SELECT 1 FROM video_analyses va WHERE va.video_id = v.video_id)
""")
remaining = cur.fetchone()[0]
print(f"  videos NOT yet in video_analyses: {remaining}", flush=True)

conn.close()
print("\nMIGRATION 004 COMPLETE!", flush=True)
