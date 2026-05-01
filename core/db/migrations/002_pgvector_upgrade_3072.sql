-- TrendSense — pgvector Migration: Upgrade 768 → 3072
-- Chạy migration này nếu bảng videos đã có cột embedding vector(768)
-- (Gemini text-embedding-004 → gemini-embedding-001, dim: 768 → 3072)

-- 1. Xóa index cũ (nếu tồn tại)
DROP INDEX IF EXISTS idx_videos_embedding;

-- 2. Xóa dữ liệu embedding cũ (không tương thích với dim mới)
UPDATE videos SET embedding = NULL WHERE embedding IS NOT NULL;

-- 3. Đổi chiều vector từ 768 → 3072
ALTER TABLE videos ALTER COLUMN embedding TYPE vector(3072);

-- 4. Bỏ qua tạo index: Supabase pgvector hiện tại giới hạn 2000 dims cho cả
--    IVFFlat và HNSW. Với ~2000 rows, sequential scan đủ nhanh (< 50ms).
--    Khi Supabase nâng cấp pgvector >= 0.7.0, có thể tạo index lại:
--    CREATE INDEX idx_videos_embedding
--        ON videos USING hnsw (embedding vector_cosine_ops);
