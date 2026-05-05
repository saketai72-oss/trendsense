-- =============================================
-- Migration 003 — CHUNK 4: Video Analyses Table
-- Chạy SAU khi Chunk 1 thành công
-- =============================================

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
);

CREATE INDEX IF NOT EXISTS idx_video_analyses_video ON video_analyses(video_id);
CREATE INDEX IF NOT EXISTS idx_video_analyses_user ON video_analyses(user_id);
CREATE INDEX IF NOT EXISTS idx_video_analyses_status ON video_analyses(ai_status);
