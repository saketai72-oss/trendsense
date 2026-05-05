-- Migration 003: Auth System + Split Upload Analysis from Videos
-- Run this migration to add authentication tables and split video analysis data.
-- Safe to run multiple times (IF NOT EXISTS guards).

-- =============================================
-- 1. USERS TABLE
-- =============================================
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255),              -- NULL for OAuth-only users
    display_name VARCHAR(100),
    avatar_url TEXT,
    auth_provider VARCHAR(20) DEFAULT 'local',  -- 'local', 'google', 'github'
    provider_id VARCHAR(255),                -- OAuth provider user ID
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_provider ON users(auth_provider, provider_id);

-- =============================================
-- 2. REFRESH TOKENS TABLE (for JWT rotation)
-- =============================================
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) UNIQUE NOT NULL,  -- SHA256 hash of refresh token
    expires_at TIMESTAMPTZ NOT NULL,
    revoked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_hash ON refresh_tokens(token_hash);

-- =============================================
-- 3. VIDEO ANALYSES TABLE (split from videos)
--    Stores upload-specific analysis results
-- =============================================
CREATE TABLE IF NOT EXISTS video_analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id TEXT UNIQUE NOT NULL REFERENCES videos(video_id) ON DELETE CASCADE,
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

-- =============================================
-- 4. ADD user_id TO VIDEOS TABLE
-- =============================================
ALTER TABLE videos ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_videos_user ON videos(user_id);

-- =============================================
-- 5. MIGRATE EXISTING UPLOAD DATA
--    Move upload analysis columns from videos → video_analyses
--    Only for videos that have upload-specific data
-- =============================================
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
WHERE video_id LIKE 'upload_%'
  AND ai_status IN ('completed', 'error')
  AND NOT EXISTS (
      SELECT 1 FROM video_analyses va WHERE va.video_id = videos.video_id
  )
ON CONFLICT DO NOTHING;
