-- =============================================
-- Migration 003 — CHUNK 5: Migrate existing data
-- Chạy SAU khi Chunk 4 thành công
-- Chỉ migrate video upload đã có kết quả phân tích
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
ON CONFLICT (video_id) DO NOTHING;
