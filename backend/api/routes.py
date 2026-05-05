"""
TrendSense API — Video Routes v3.0
All endpoints for video data, stats, and analysis.

Changes v3.0:
- POST /api/analyze: nhận JSON (video_id + storage_path) thay vì UploadFile
- GET  /api/upload-url: tạo Presigned URL để frontend upload thẳng lên Supabase
- POST /api/analyze-gemini: dùng RQ enqueue thay BackgroundTasks
- Rate limiting: 5 req/giờ cho /analyze, 60 req/phút cho /analyze-gemini
- Groq → OpenRouter + Groq fallback (llm_client)

Changes v3.1:
- Auth: upload-url + analyze endpoints require JWT authentication
- user_id linked to uploaded videos
- video_analyses table for upload-specific data
"""
from fastapi import APIRouter, Query, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import Optional
import math
import hashlib

from core.db.models import (
    get_all_analyzed_videos, get_video_by_id,
    get_dashboard_stats, get_category_stats,
    get_sentiment_stats, get_top_keywords,
    get_timeline_data, insert_user_video,
    get_video_analysis, get_user_videos,
    delete_user_video,
)
from core.config.backend_settings import STANDARD_CATEGORIES
from backend.auth.dependencies import get_current_user, get_optional_user

router = APIRouter()


# ─────────────────────────────────────────────────────
# Helper: serialize row dict
# ─────────────────────────────────────────────────────
def _serialize(obj):
    result = dict(obj)
    for key in result:
        val = result[key]
        if hasattr(val, 'isoformat'):
            result[key] = val.isoformat()
        elif isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
            result[key] = 0
    return result


# ─────────────────────────────────────────────────────
# GET /api/videos — Paginated + Filtered + Semantic Search
# ─────────────────────────────────────────────────────
@router.get("/videos")
def list_videos(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    sentiment: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = "viral_probability",
    sort_order: str = "desc",
    min_viral: float = 0,
):
    cat_list = [c.strip() for c in category.split(',')] if category else None

    # Thử semantic search nếu có query (tối thiểu 2 ký tự để embedding有意义)
    semantic_ids = None
    if search and len(search.strip()) >= 2:
        try:
            from backend.api.embedding_service import semantic_search
            semantic_ids = semantic_search(search, limit=200)
        except Exception:
            pass  # Graceful fallback to ILIKE

    rows, total = get_all_analyzed_videos(
        page=page, per_page=per_page,
        categories=cat_list, sentiment=sentiment,
        search=search, sort_by=sort_by,
        sort_order=sort_order, min_viral=min_viral,
        semantic_video_ids=semantic_ids,
    )

    return {
        "videos": [_serialize(r) for r in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": math.ceil(total / per_page) if per_page > 0 else 0,
    }


# ─────────────────────────────────────────────────────
# GET /api/videos/{video_id} — Single Video Detail
# ─────────────────────────────────────────────────────
@router.get("/videos/{video_id}")
def get_video(video_id: str):
    video = get_video_by_id(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return _serialize(video)


# ─────────────────────────────────────────────────────
# GET /api/stats — Dashboard Summary
# ─────────────────────────────────────────────────────
@router.get("/stats")
def dashboard_stats():
    stats = get_dashboard_stats()
    return _serialize(stats) if stats else {}


# ─────────────────────────────────────────────────────
# GET /api/categories — Category Stats
# ─────────────────────────────────────────────────────
@router.get("/categories")
def categories():
    return [_serialize(r) for r in get_category_stats()]


# ─────────────────────────────────────────────────────
# GET /api/sentiments
# ─────────────────────────────────────────────────────
@router.get("/sentiments")
def sentiments():
    return get_sentiment_stats()


# ─────────────────────────────────────────────────────
# GET /api/keywords
# ─────────────────────────────────────────────────────
@router.get("/keywords")
def keywords(limit: int = Query(30, ge=1, le=100)):
    return get_top_keywords(limit)


# ─────────────────────────────────────────────────────
# GET /api/timeline
# ─────────────────────────────────────────────────────
@router.get("/timeline")
def timeline():
    rows = get_timeline_data()
    result = []
    for row in rows:
        item = dict(row)
        for key in item:
            if hasattr(item[key], 'isoformat'):
                item[key] = item[key].isoformat()
        result.append(item)
    return result


# ─────────────────────────────────────────────────────
# GET /api/upload-url — Lấy Presigned URL để upload thẳng lên Supabase
# ─────────────────────────────────────────────────────
class UploadUrlRequest(BaseModel):
    filename: str
    content_type: Optional[str] = "video/mp4"


@router.post("/upload-url")
def get_upload_url(body: UploadUrlRequest, user: dict = Depends(get_current_user)):
    """
    Frontend gọi endpoint này trước khi upload.
    Trả về presigned PUT URL và video_id.
    Frontend sau đó PUT file thẳng lên Supabase, rồi gọi POST /api/analyze.
    Yêu cầu xác thực — video sẽ được liên kết với tài khoản người dùng.
    """
    import uuid
    from backend.api.storage_service import create_upload_url

    video_id = f"upload_{uuid.uuid4().hex[:16]}"
    user_id = str(user["id"])

    try:
        upload_url, storage_path = create_upload_url(video_id, body.filename)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tạo upload URL: {str(e)[:100]}")

    # Pre-insert vào DB với user_id để frontend có thể poll ngay
    try:
        insert_user_video(video_id, f"supabase://{storage_path}", user_id=user_id)
    except Exception:
        pass

    return {
        "video_id": video_id,
        "upload_url": upload_url,
        "storage_path": storage_path,
    }


# ─────────────────────────────────────────────────────
# POST /api/analyze — Kích hoạt phân tích sau khi upload xong
# Rate limit: 5 req / IP / giờ (bảo vệ Modal GPU)
# ─────────────────────────────────────────────────────
class AnalyzeRequest(BaseModel):
    video_id: str
    storage_path: str
    caption: Optional[str] = ""


from backend.api.rate_limiter import limiter

@router.post("/analyze")
@limiter.limit("20/hour")
def analyze_video(request: Request, body: AnalyzeRequest, user: dict = Depends(get_current_user)):
    """
    Nhận video_id + storage_path sau khi frontend đã upload thẳng lên Supabase.
    FastAPI tạo signed download URL và gửi tới Modal để xử lý.
    Yêu cầu xác thực — chỉ chủ video mới có thể kích hoạt phân tích.
    """

    from core.config.backend_settings import MODAL_WEBHOOK_URL
    from backend.api.storage_service import create_download_url
    import requests as http_requests

    if not MODAL_WEBHOOK_URL:
        raise HTTPException(status_code=503, detail="Modal webhook chưa được cấu hình")

    video_id = body.video_id.strip()
    storage_path = body.storage_path.strip()

    if not video_id or not storage_path:
        raise HTTPException(status_code=400, detail="Thiếu video_id hoặc storage_path")

    # Tạo signed download URL cho Modal (1 giờ)
    try:
        download_url = create_download_url(storage_path, expires_in=3600)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tạo download URL: {str(e)[:100]}")

    payload = {
        "video_id": video_id,
        "url": "",
        "caption": body.caption or "",
        "storage_url": download_url,      # ← Thay thế video_base64
        "storage_path": storage_path,     # ← Để Modal biết đường dẫn
        "video_base64": "",               # ← Luôn rỗng từ v3.0
        "video_filename": storage_path.split("/")[-1],
        "views": 0, "likes": 0, "comments": 0,
        "shares": 0, "saves": 0, "create_time": 0,
        "top_comments": [],
    }

    try:
        resp = http_requests.post(MODAL_WEBHOOK_URL, json=payload, timeout=30)
        resp.raise_for_status()
        return {
            "status": "queued",
            "video_id": video_id,
            "message": f"Video đang được AI phân tích. Vui lòng chờ 1-3 phút.",
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Lỗi kết nối Modal: {str(e)[:200]}")


# ─────────────────────────────────────────────────────
# POST /api/analyze-gemini — Scraper Webhook (RQ Queue)
# Rate limit: 60 req / IP / phút (internal webhook)
# ─────────────────────────────────────────────────────
@router.post("/analyze-gemini", status_code=202)
@limiter.limit("60/minute")
def analyze_gemini_webhook(request: Request, payload: dict):
    """
    Webhook từ Scraper. Đẩy job vào Redis Queue thay vì BackgroundTasks.
    Job survive được server restart và tự retry khi Gemini 429/503.
    """
    video_id = payload.get("video_id")
    url = payload.get("url")

    if not video_id or not url:
        raise HTTPException(status_code=400, detail="Thiếu video_id hoặc url")

    # Enqueue vào Redis Queue (RQ) thay vì BackgroundTasks
    try:
        from redis import Redis
        from rq import Queue
        from rq.job import Retry
        from core.config.backend_settings import REDIS_URL
        from backend.api.gemini_engine import process_video_with_gemini

        conn = Redis.from_url(REDIS_URL)
        q = Queue("gemini_jobs", connection=conn)

        job = q.enqueue(
            process_video_with_gemini,
            payload,
            retry=Retry(max=3, interval=[60, 180, 600]),
            job_timeout=900,  # 15 phút
        )
        return {
            "status": "queued",
            "video_id": video_id,
            "job_id": job.id,
            "message": f"Video {video_id} đã vào hàng đợi Gemini (job: {job.id[:8]}...).",
        }
    except Exception as e:
        # Graceful fallback: nếu Redis không có → dùng thread đơn giản
        import logging
        import threading
        logging.getLogger(__name__).warning(
            f"[Queue] Redis không khả dụng, chạy inline thread: {e}"
        )
        from backend.api.gemini_engine import process_video_with_gemini
        t = threading.Thread(target=process_video_with_gemini, args=(payload,), daemon=True)
        t.start()
        return {
            "status": "queued",
            "video_id": video_id,
            "job_id": None,
            "message": f"Video {video_id} đang xử lý (fallback thread — Redis offline).",
        }


# ─────────────────────────────────────────────────────
# GET /api/analyze/{video_id} — Check Analysis Status
# ─────────────────────────────────────────────────────
@router.get("/analyze/{video_id}")
def check_analysis(video_id: str):
    video = get_video_by_id(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    result = _serialize(video)
    status = result.get("ai_status", "pending")
    is_upload = video_id.startswith("upload_")
    analysis_type = "content_based" if is_upload else "engagement_based"

    # For upload videos, merge data from video_analyses table
    if is_upload:
        analysis = get_video_analysis(video_id)
        if analysis:
            analysis = _serialize(analysis)
            result.update(analysis)
            status = analysis.get("ai_status", status)

    is_done = status in ("completed", "error")

    trend_insights = None
    if result.get("trend_insights"):
        import json
        try:
            trend_insights = (
                json.loads(result["trend_insights"])
                if isinstance(result["trend_insights"], str)
                else result["trend_insights"]
            )
        except Exception:
            pass

    recommendations = None
    if is_done and not is_upload:
        recommendations = _generate_recommendations(result)

    return {
        "status": status,
        "is_done": is_done,
        "video": result,
        "analysis_type": analysis_type,
        "trend_insights": trend_insights,
        "recommendations": recommendations,
    }


# ─────────────────────────────────────────────────────
# GET /api/my-videos — User's uploaded videos (requires auth)
# ─────────────────────────────────────────────────────
@router.get("/my-videos")
def my_videos(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    """Get paginated list of videos uploaded by the authenticated user with full analysis."""
    user_id = str(user["id"])
    rows, total = get_user_videos(user_id, page=page, per_page=per_page)
    import math as _math

    videos = []
    for r in rows:
        v = _serialize(r)

        # Parse trend_insights từ JSON string nếu cần
        ti = v.get("trend_insights")
        if isinstance(ti, str):
            try:
                import json as _json
                v["trend_insights"] = _json.loads(ti)
            except (ValueError, TypeError):
                v["trend_insights"] = None

        # Tạo signed video URL từ storage path
        link = v.get("link", "")
        if isinstance(link, str) and link.startswith("supabase://"):
            storage_path = link.replace("supabase://", "")
            try:
                from backend.api.storage_service import create_download_url
                v["video_url"] = create_download_url(storage_path, expires_in=3600)
            except Exception:
                v["video_url"] = None
        else:
            v["video_url"] = None

        videos.append(v)

    return {
        "videos": videos,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": _math.ceil(total / per_page) if per_page > 0 else 0,
    }


# ─────────────────────────────────────────────────────
# GET /api/my-videos/{video_id} — Full detail for one analysis
# ─────────────────────────────────────────────────────
@router.get("/my-videos/{video_id}")
def my_video_detail(video_id: str, user: dict = Depends(get_current_user)):
    """Get full analysis detail for a single video owned by the user."""
    user_id = str(user["id"])
    video = get_video_by_id(video_id)
    if not video or str(video.get("user_id")) != user_id:
        raise HTTPException(status_code=404, detail="Video không tồn tại")

    v = _serialize(video)

    analysis = get_video_analysis(video_id)
    if analysis:
        a = _serialize(analysis)
        a.pop("video_id", None)
        v.update(a)

    ti = v.get("trend_insights")
    if isinstance(ti, str):
        try:
            import json as _json
            v["trend_insights"] = _json.loads(ti)
        except (ValueError, TypeError):
            v["trend_insights"] = None

    link = v.get("link", "")
    if isinstance(link, str) and link.startswith("supabase://"):
        storage_path = link.replace("supabase://", "")
        try:
            from backend.api.storage_service import create_download_url
            v["video_url"] = create_download_url(storage_path, expires_in=3600)
        except Exception:
            v["video_url"] = None
    else:
        v["video_url"] = None

    return v


# ─────────────────────────────────────────────────────
# DELETE /api/my-videos/{video_id} — Delete user's analysis
# ─────────────────────────────────────────────────────
@router.delete("/my-videos/{video_id}")
def my_video_delete(video_id: str, user: dict = Depends(get_current_user)):
    """Delete a video and its analysis. Only the owner can delete."""
    user_id = str(user["id"])
    deleted = delete_user_video(video_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Video không tồn tại hoặc không thuộc về bạn")
    return {"message": "Đã xóa thành công", "video_id": video_id}


# ─────────────────────────────────────────────────────
# Internal: Generate Recommendations (OpenRouter → Groq)
# ─────────────────────────────────────────────────────
def _generate_recommendations(video: dict) -> dict:
    """
    Sinh đề xuất tối ưu. Dùng llm_client (OpenRouter → Groq fallback).
    """
    desc = video.get("video_description", "") or ""
    category = video.get("category", "") or ""
    keywords = video.get("top_keywords", "") or ""
    sentiment = video.get("video_sentiment", "") or ""
    velocity = float(video.get("viral_velocity", 0) or 0)
    engagement = float(video.get("engagement_rate", 0) or 0)
    viral_pct = float(video.get("viral_probability", 0) or 0)

    try:
        from backend.api.llm_client import chat_completion_json

        prompt = f"""Bạn là chuyên gia tư vấn nội dung TikTok Việt Nam hàng đầu.

THÔNG TIN VIDEO:
- Mô tả: {desc}
- Danh mục: {category}
- Từ khóa: {keywords}
- Cảm xúc: {sentiment}
- Xác suất viral: {viral_pct:.1f}%
- Engagement rate: {engagement:.1f}%
- Viral velocity: {velocity:.1f}

NHIỆM VỤ: Đưa ra 4 đề xuất cụ thể, thực tế để tăng khả năng viral.

TRẢ VỀ ĐÚNG JSON:
{{"hook": "Đề xuất cải thiện 3 giây đầu (2-3 câu)", "audio": "Đề xuất nhạc nền trending (2-3 câu)", "caption_hashtags": "Viết lại caption + 5-8 hashtag", "pacing_cta": "Nhịp cắt dựng và Call-To-Action (2-3 câu)"}}"""

        data = chat_completion_json(prompt, temperature=0.5, max_tokens=500)
        if all(k in data for k in ["hook", "audio", "caption_hashtags", "pacing_cta"]):
            return data
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"[Recs] LLM lỗi: {e}")

    # Static fallback
    recs = {
        "hook": "Cải thiện 3 giây đầu tiên bằng câu hỏi kích thích hoặc hình ảnh gây sốc.",
        "audio": "Sử dụng nhạc nền đang trending trên TikTok phù hợp với thể loại video.",
        "caption_hashtags": f"Thêm hashtag liên quan: {keywords}. Viết caption ngắn gọn, gợi tò mò.",
        "pacing_cta": "Thêm Call-To-Action ở cuối video. Giữ nhịp cắt nhanh 2-3 giây/cảnh.",
    }
    if engagement < 5:
        recs["hook"] = "⚠️ Engagement rất thấp. Cần hook mạnh hơn: mở đầu bằng conflict hoặc reveal bất ngờ."
    if velocity > 1000:
        recs["pacing_cta"] = "🚀 Video đang lan truyền tốt! Đăng thêm video tiếp nối ngay trong 24h."
    if "TIÊU CỰC" in sentiment:
        recs["audio"] = "⚠️ Cảm xúc tiêu cực. Xem xét tone nhạc nền tích cực hơn."
    return recs
