"""
TrendSense — Embedding Service (Google Gemini text-embedding-004)
===============================================================
100% cloud — không cần service local nào. Miễn phí với hạn mức cao.
Sinh vector embedding (dim=768) cho transcript + description của video.
Lưu vào cột `embedding vector(768)` trong bảng `videos` (pgvector).

Cài pgvector trước trên Supabase:
    CREATE EXTENSION IF NOT EXISTS vector;
    ALTER TABLE videos ADD COLUMN IF NOT EXISTS embedding vector(768);
    CREATE INDEX IF NOT EXISTS idx_embedding
        ON videos USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
"""
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)

EMBED_MODEL = "text-embedding-004"
EMBED_DIM = 768


def generate_embedding(text: str) -> Optional[List[float]]:
    """
    Gọi Google Gemini API sinh vector cho đoạn text.

    Returns:
        List[float] (dim=768) hoặc None nếu thiếu key / lỗi API
    """
    import os
    gemini_key = os.environ.get("GEMINI_API_KEY", "")

    if not gemini_key:
        logger.debug("[Embed] Không có GEMINI_API_KEY — bỏ qua embedding.")
        return None

    if not text or not text.strip():
        return None

    try:
        from google import genai

        client = genai.Client(api_key=gemini_key)
        response = client.models.embed_content(
            model=EMBED_MODEL,
            contents=text.strip(),
        )
        embedding = response.embeddings[0].values
        logger.debug(f"[Embed] ✅ Sinh embedding (dim={len(embedding)})")
        return embedding

    except Exception as e:
        logger.warning(f"[Embed] Lỗi Gemini Embeddings API: {e}")
        return None


def update_video_embedding(video_id: str, transcript: str, description: str) -> bool:
    """
    Sinh embedding từ transcript + description và lưu vào DB.
    Gọi sau update_ai_results() trong gemini_engine.py.

    Returns:
        True nếu thành công, False nếu bỏ qua (thiếu key / Ollama offline)
    """
    # Ghép text: embedding bao quát cả nội dung nghe + nội dung nhìn
    combined = " ".join(filter(None, [
        str(transcript or "").strip(),
        str(description or "").strip(),
    ])).strip()

    if not combined:
        return False

    embedding = generate_embedding(combined)
    if not embedding:
        return False

    return _save_embedding_to_db(video_id, embedding)


def _save_embedding_to_db(video_id: str, embedding: List[float]) -> bool:
    """Lưu vector embedding vào cột `embedding` trong bảng videos."""
    from core.db.session import get_connection

    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                # pgvector nhận embedding dưới dạng string "[0.1, 0.2, ...]"
                vec_str = "[" + ",".join(f"{v:.8f}" for v in embedding) + "]"
                cur.execute(
                    "UPDATE videos SET embedding = %s::vector WHERE video_id = %s",
                    (vec_str, video_id),
                )
                conn.commit()
            logger.info(f"[Embed] ✅ Đã lưu embedding cho {video_id} (dim={len(embedding)})")
            return True
        except Exception as e:
            conn.rollback()
            logger.warning(
                f"[Embed] Lỗi lưu embedding: {e} "
                "— Kiểm tra pgvector đã được bật chưa: CREATE EXTENSION IF NOT EXISTS vector;"
            )
            return False
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"[Embed] Không kết nối được DB: {e}")
        return False


def semantic_search(query: str, limit: int = 200) -> Optional[List[str]]:
    """
    Tìm kiếm ngữ nghĩa: sinh embedding từ query → trả về list video_id
    theo thứ tự cosine similarity giảm dần (toán tử <=> của pgvector).

    Args:
        query: Chuỗi tìm kiếm từ người dùng
        limit: Số lượng kết quả tối đa (sẽ được filter thêm bởi get_all_analyzed_videos)

    Returns:
        List[str] (video_id theo thứ tự similarity) hoặc None nếu không thể dùng semantic search
    """
    embedding = generate_embedding(query)
    if not embedding:
        return None  # Caller sẽ fallback về ILIKE

    from core.db.session import get_connection
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                vec_str = "[" + ",".join(f"{v:.8f}" for v in embedding) + "]"
                cur.execute(
                    """
                    SELECT video_id
                    FROM videos
                    WHERE embedding IS NOT NULL
                      AND views > 0
                      AND ai_status = 'completed'
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (vec_str, limit),
                )
                rows = cur.fetchall()
                ids = [row[0] for row in rows]
                logger.info(f"[Embed] Semantic search '{query[:30]}' → {len(ids)} kết quả")
                return ids
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"[Embed] Lỗi semantic search: {e} — fallback ILIKE")
        return None
