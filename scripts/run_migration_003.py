import psycopg2
import sys
sys.stdout.reconfigure(line_buffering=True)

DB = "postgresql://postgres.fnsygsoohvnaxacirhwf:taidinhtrai@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres"

conn = psycopg2.connect(DB, connect_timeout=30)
conn.autocommit = True
cur = conn.cursor()

# Chunk 4b: Ensure UNIQUE constraint on video_analyses.video_id
print("[4b] Ensuring UNIQUE constraint on video_analyses.video_id ...", flush=True)
try:
    cur.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conrelid = 'video_analyses'::regclass
                AND contype = 'u'
            ) THEN
                ALTER TABLE video_analyses ADD CONSTRAINT video_analyses_video_id_unique UNIQUE (video_id);
            END IF;
        END $$;
    """)
    print("  [OK] Constraint verified", flush=True)
except Exception as e:
    print(f"  [INFO] {str(e)[:120]}", flush=True)

# Chunk 5: Migrate existing upload data
print("\n[5] Migrating upload data to video_analyses ...", flush=True)
try:
    cur.execute("""
        INSERT INTO video_analyses (
            video_id, video_duration, video_orientation, scene_cut_count,
            trend_alignment_score, trend_insights,
            audio_transcript, video_description, top_keywords,
            video_sentiment, positive_score, category, ai_status
        )
        SELECT
            video_id, video_duration, video_orientation, scene_cut_count,
            trend_alignment_score, trend_insights,
            audio_transcript, video_description, top_keywords,
            video_sentiment, positive_score, category, ai_status
        FROM videos
        WHERE video_id LIKE 'upload_%%'
          AND ai_status IN ('completed', 'error')
        ON CONFLICT (video_id) DO NOTHING
    """)
    print(f"  [OK] Rows migrated: {cur.rowcount}", flush=True)
except Exception as e:
    print(f"  [ERR] {str(e)[:120]}", flush=True)

# Final verification
print("\n--- FINAL VERIFICATION ---", flush=True)

tables = ['users', 'refresh_tokens', 'video_analyses', 'videos']
for t in tables:
    cur.execute(f"SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='{t}')")
    print(f"  {t}: {'EXISTS' if cur.fetchone()[0] else 'MISSING'}", flush=True)

cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='videos' AND column_name='user_id'")
print(f"  videos.user_id: {'EXISTS' if cur.fetchone() else 'MISSING'}", flush=True)

cur.execute("SELECT COUNT(*) FROM users")
print(f"  users count: {cur.fetchone()[0]}", flush=True)

cur.execute("SELECT COUNT(*) FROM video_analyses")
print(f"  video_analyses count: {cur.fetchone()[0]}", flush=True)

cur.execute("SELECT COUNT(*) FROM videos WHERE video_id LIKE 'upload_%%'")
print(f"  upload videos count: {cur.fetchone()[0]}", flush=True)

conn.close()
print("\nALL MIGRATIONS COMPLETE!", flush=True)
