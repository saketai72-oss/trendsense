-- =============================================
-- Migration 003 — CHUNK 4b: Ensure UNIQUE constraint
-- Chạy nếu bảng video_analyses đã tồn tại nhưng thiếu UNIQUE
-- (Phòng trường hợp chạy chunk 4 bị timeout giữa chừng)
-- =============================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'video_analyses'::regclass
        AND contype = 'u'
        AND conname LIKE '%video_id%'
    ) THEN
        ALTER TABLE video_analyses ADD CONSTRAINT video_analyses_video_id_key UNIQUE (video_id);
    END IF;
END $$;
