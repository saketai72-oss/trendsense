-- =============================================
-- Migration 003 — CHUNK 3: Add user_id to videos
-- Chạy SAU khi Chunk 1 thành công
-- =============================================

ALTER TABLE videos ADD COLUMN IF NOT EXISTS user_id UUID;
CREATE INDEX IF NOT EXISTS idx_videos_user ON videos(user_id);
