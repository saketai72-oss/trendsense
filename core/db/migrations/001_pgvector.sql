-- TrendSense — pgvector Migration
-- Bật extension vector và thêm cột embedding vào bảng videos
-- Dùng cho Google Gemini text-embedding-004 (768 dimensions)

-- 1. Bật extension pgvector (Yêu cầu tài khoản có quyền SUPERUSER trên Supabase)
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Thêm cột embedding vào bảng videos
ALTER TABLE videos ADD COLUMN IF NOT EXISTS embedding vector(768);

-- 3. Tạo index ivfflat để tăng tốc độ tìm kiếm semantic (cần phải có data mới tạo index hiệu quả nhất)
-- Dùng vector_cosine_ops cho cosine similarity (<=>)
CREATE INDEX IF NOT EXISTS idx_videos_embedding
    ON videos USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
