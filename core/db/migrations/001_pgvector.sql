-- TrendSense — pgvector Migration
-- Bật extension vector và thêm cột embedding vào bảng videos
-- Dùng cho Google Gemini gemini-embedding-001 (3072 dimensions)

-- 1. Bật extension pgvector (Yêu cầu tài khoản có quyền SUPERUSER trên Supabase)
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Thêm cột embedding vào bảng videos
ALTER TABLE videos ADD COLUMN IF NOT EXISTS embedding vector(3072);

-- 3. Index: Supabase pgvector hiện tại giới hạn 2000 dims cho IVFFlat/HNSW.
--    Với ~2000 rows, sequential scan đủ nhanh (< 50ms).
--    Khi Supabase nâng cấp pgvector >= 0.7.0, bỏ comment dòng dưới:
-- CREATE INDEX idx_videos_embedding
--     ON videos USING hnsw (embedding vector_cosine_ops);
