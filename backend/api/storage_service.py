"""
TrendSense — Supabase Storage Service
=======================================
Tạo Presigned URL để Frontend upload video thẳng lên Supabase Storage.
SUPABASE_SERVICE_KEY chỉ được dùng ở đây (backend). Tuyệt đối không
expose key này xuống Next.js.

Flow:
    1. FastAPI gọi create_upload_url(video_id, filename)
       → Supabase tạo signed URL (PUT) cho frontend
    2. Frontend upload trực tiếp lên Supabase (không qua FastAPI)
    3. FastAPI gọi create_download_url(path) để Modal có thể tải file
"""
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


def _get_supabase_client():
    """Lazy-load Supabase client để tránh lỗi import khi chưa có key."""
    from core.config.backend_settings import SUPABASE_URL, SUPABASE_SERVICE_KEY
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise RuntimeError(
            "Thiếu cấu hình Supabase: SUPABASE_URL và SUPABASE_SERVICE_KEY phải có trong .env"
        )
    from supabase import create_client
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def create_upload_url(video_id: str, filename: str, expires_in: int = 600) -> Tuple[str, str]:
    """
    Tạo Presigned URL để frontend upload video lên Supabase Storage.

    Args:
        video_id:   ID video (dùng làm thư mục trong bucket)
        filename:   Tên file gốc (e.g. "clip.mp4")
        expires_in: Thời gian URL còn hạn (giây, mặc định 10 phút)

    Returns:
        Tuple[upload_url, storage_path]
        - upload_url:    URL đã ký để PUT file
        - storage_path:  Đường dẫn trong bucket (e.g. "uploads/upload_abc123/clip.mp4")
    """
    from core.config.backend_settings import SUPABASE_BUCKET

    supabase = _get_supabase_client()

    # Normalize filename để tránh path traversal
    safe_filename = filename.replace("/", "_").replace("..", "_") or "video.mp4"
    storage_path = f"uploads/{video_id}/{safe_filename}"

    # Tạo signed upload URL (PUT method)
    response = supabase.storage.from_(SUPABASE_BUCKET).create_signed_upload_url(storage_path)

    # Supabase SDK trả về dict với key 'signedURL' hoặc 'signed_url' tuỳ version
    upload_url = (
        response.get("signedURL")
        or response.get("signed_url")
        or response.get("url")
    )
    if not upload_url:
        raise RuntimeError(f"Supabase không trả về upload URL: {response}")

    logger.info(f"[Storage] Tạo upload URL cho {video_id}: {storage_path}")
    return str(upload_url), storage_path


def create_download_url(storage_path: str, expires_in: int = 3600) -> str:
    """
    Tạo Signed Download URL để Modal Worker tải video về.

    Args:
        storage_path: Đường dẫn trong bucket (e.g. "uploads/upload_abc123/clip.mp4")
        expires_in:   Thời hạn URL (giây, mặc định 1 giờ)

    Returns:
        Signed download URL (GET)
    """
    from core.config.backend_settings import SUPABASE_BUCKET

    supabase = _get_supabase_client()

    response = supabase.storage.from_(SUPABASE_BUCKET).create_signed_url(
        storage_path, expires_in
    )

    signed_url = (
        response.get("signedURL")
        or response.get("signed_url")
        or response.get("url")
    )
    if not signed_url:
        raise RuntimeError(f"Supabase không trả về download URL: {response}")

    logger.info(f"[Storage] Tạo download URL cho: {storage_path}")
    return str(signed_url)


def delete_file(storage_path: str) -> bool:
    """
    Xoá file khỏi Supabase Storage sau khi Modal đã xử lý xong.
    Không raise exception — chỉ log lỗi.
    """
    from core.config.backend_settings import SUPABASE_BUCKET
    try:
        supabase = _get_supabase_client()
        supabase.storage.from_(SUPABASE_BUCKET).remove([storage_path])
        logger.info(f"[Storage] Đã xoá file: {storage_path}")
        return True
    except Exception as e:
        logger.warning(f"[Storage] Không thể xoá {storage_path}: {e}")
        return False
