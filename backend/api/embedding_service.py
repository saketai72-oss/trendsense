"""
TrendSense — Embedding Service (Google Gemini gemini-embedding-001)
==================================================================
100% cloud — không cần service local nào. Miễn phí với hạn mức cao.
Sinh vector embedding (dim=3072) cho transcript + description của video.
Lưu vào cột `embedding vector(3072)` trong bảng `videos` (pgvector).

Cài pgvector trước trên Supabase:
    CREATE EXTENSION IF NOT EXISTS vector;
    ALTER TABLE videos ADD COLUMN IF NOT EXISTS embedding vector(3072);
    -- Index: Supabase pgvector giới hạn 2000 dims cho IVFFlat/HNSW.
    -- Với ~2000 rows, sequential scan đủ nhanh (< 50ms).
"""
import logging
import re
import time
from typing import Optional, List

logger = logging.getLogger(__name__)

EMBED_MODEL = "gemini-embedding-001"
EMBED_DIM = 3072


def _parse_retry_delay(error: Exception) -> float:
    """Trích thời gian chờ (giây) từ lỗi 429 của Gemini API.
    Returns:
        >0 : thời gian chờ thực tế từ API (per-minute rate limit, có thể retry)
         0 : API trả 0s (daily quota đã hết, retry vô nghĩa)
        -1 : không parse được (dùng default bên ngoài)
    """
    match = re.search(r"retryDelay['\"]:\s*['\"]?([\d.]+)s", str(error))
    if match:
        return float(match.group(1))  # có thể là 0.0 (daily quota) hoặc >0 (per-minute)
    return -1  # không parse được


def generate_embedding(text: str, max_retries: int = 3) -> Optional[List[float]]:
    """
    Gọi Google Gemini API sinh vector cho đoạn text.
    Tự động retry khi bị 429 (rate limit) với exponential backoff.

    Returns:
        List[float] (dim=3072) hoặc None nếu thiếu key / lỗi API
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

        # Thử model chính, fallback sang model khác nếu 404
        for model_name in [EMBED_MODEL, "gemini-embedding-2"]:
            for attempt in range(max_retries + 1):
                try:
                    response = client.models.embed_content(
                        model=model_name,
                        contents=text.strip(),
                    )
                    embedding = response.embeddings[0].values
                    logger.debug(f"[Embed] ✅ Sinh embedding với {model_name} (dim={len(embedding)})")
                    return embedding
                except Exception as model_err:
                    err_str = str(model_err)

                    # 404: model không tồn tại → thử model khác
                    if "404" in err_str or "NOT_FOUND" in err_str:
                        logger.warning(f"[Embed] Model {model_name} không khả dụng, thử model khác...")
                        break  # thoát vòng retry, sang model tiếp

                    # 429: rate limit → retry với backoff
                    if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                        delay = _parse_retry_delay(model_err)
                        if delay == 0:
                            # API trả 0s → daily quota đã hết, retry vô nghĩa
                            logger.warning("[Embed] 429 Daily quota exhausted (retryDelay=0s)")
                            raise
                        if attempt < max_retries:
                            wait = delay if delay > 0 else 60.0  # fallback 60s nếu không parse được
                            wait *= (2 ** attempt)
                            logger.warning(
                                f"[Embed] 429 Rate limit — chờ {wait:.0f}s rồi thử lại "
                                f"(attempt {attempt + 1}/{max_retries})..."
                            )
                            time.sleep(wait)
                            continue
                        else:
                            raise  # hết retry → raise để caller xử lý

                    # Lỗi khác → raise ngay
                    raise
            else:
                # Nếu vòng retry hết mà model vẫn fail, tiếp tục model khác
                continue

        logger.warning(f"[Embed] Không có model embedding nào khả dụng.")
        return None

    except Exception as e:
        err_str = str(e)
        if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
            raise  # Ném lại 429 để caller biết đây là rate limit, không phải lỗi khác
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
