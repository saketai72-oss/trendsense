"""
TrendSense API — Video Routes
All endpoints for video data, stats, and analysis.
"""
from fastapi import APIRouter, Query, HTTPException, UploadFile, File, Form, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
import math
import re
import hashlib
import base64

from core.db.models import (
    get_all_analyzed_videos, get_video_by_id,
    get_dashboard_stats, get_category_stats,
    get_sentiment_stats, get_top_keywords,
    get_timeline_data, insert_user_video,
)
from core.config.backend_settings import STANDARD_CATEGORIES

router = APIRouter()


# ──────────────────────────────────────────────────
# GET /api/videos — Paginated + Filtered Video List
# ──────────────────────────────────────────────────
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

    rows, total = get_all_analyzed_videos(
        page=page, per_page=per_page,
        categories=cat_list, sentiment=sentiment,
        search=search, sort_by=sort_by,
        sort_order=sort_order, min_viral=min_viral,
    )

    # Serialize date/decimal fields
    videos = []
    for row in rows:
        video = dict(row)
        for key in video:
            val = video[key]
            if hasattr(val, 'isoformat'):
                video[key] = val.isoformat()
            elif isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                video[key] = 0
        videos.append(video)

    return {
        "videos": videos,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": math.ceil(total / per_page) if per_page > 0 else 0,
    }


# ──────────────────────────────────────────────────
# GET /api/videos/{video_id} — Single Video Detail
# ──────────────────────────────────────────────────
@router.get("/videos/{video_id}")
def get_video(video_id: str):
    """Lấy chi tiết 1 video."""
    video = get_video_by_id(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    result = dict(video)
    for key in result:
        val = result[key]
        if hasattr(val, 'isoformat'):
            result[key] = val.isoformat()
        elif isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
            result[key] = 0
    return result


# ──────────────────────────────────────────────────
# GET /api/stats — Dashboard Summary
# ──────────────────────────────────────────────────
@router.get("/stats")
def dashboard_stats():
    """Lấy thống kê tổng quan cho dashboard."""
    stats = get_dashboard_stats()
    if not stats:
        return {}

    result = dict(stats)
    for key in result:
        val = result[key]
        if hasattr(val, 'isoformat'):
            result[key] = val.isoformat()
        elif isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
            result[key] = 0
    return result


# ──────────────────────────────────────────────────
# GET /api/categories — Category Stats
# ──────────────────────────────────────────────────
@router.get("/categories")
def categories():
    """Lấy thống kê theo danh mục."""
    rows = get_category_stats()
    result = []
    for row in rows:
        item = dict(row)
        for key in item:
            val = item[key]
            if hasattr(val, 'isoformat'):
                item[key] = val.isoformat()
            elif isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                item[key] = 0
        result.append(item)
    return result


# ──────────────────────────────────────────────────
# GET /api/sentiments — Sentiment Distribution
# ──────────────────────────────────────────────────
@router.get("/sentiments")
def sentiments():
    """Lấy thống kê phân bổ cảm xúc."""
    return get_sentiment_stats()


# ──────────────────────────────────────────────────
# GET /api/keywords — Top Keywords
# ──────────────────────────────────────────────────
@router.get("/keywords")
def keywords(limit: int = Query(30, ge=1, le=100)):
    """Lấy top keywords."""
    return get_top_keywords(limit)


# ──────────────────────────────────────────────────
# GET /api/timeline — Timeline Data
# ──────────────────────────────────────────────────
@router.get("/timeline")
def timeline():
    """Lấy dữ liệu timeline theo ngày thu thập."""
    rows = get_timeline_data()
    result = []
    for row in rows:
        item = dict(row)
        for key in item:
            val = item[key]
            if hasattr(val, 'isoformat'):
                item[key] = val.isoformat()
        result.append(item)
    return result


# ──────────────────────────────────────────────────
# POST /api/analyze — User Video Prediction (Upload)
# ──────────────────────────────────────────────────
MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100 MB


@router.post("/analyze")
async def analyze_video(
    video: UploadFile = File(...),
    caption: str = Form(""),
):
    """
    Nhận video upload + caption từ người dùng.
    Encode base64 rồi gửi tới Modal API để phân tích on-demand.
    Trả về status & video_id ngay lập tức.
    """
    import requests
    from core.config.backend_settings import MODAL_WEBHOOK_URL

    # Validate file type
    allowed_types = {"video/mp4", "video/quicktime", "video/x-msvideo", "video/webm", "video/x-matroska"}
    if video.content_type and video.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Định dạng video không hỗ trợ: {video.content_type}. Chấp nhận: MP4, MOV, AVI, WebM, MKV."
        )

    # Read video bytes
    video_bytes = await video.read()

    if len(video_bytes) == 0:
        raise HTTPException(status_code=400, detail="File video trống.")

    if len(video_bytes) > MAX_VIDEO_SIZE:
        raise HTTPException(status_code=400, detail=f"Video quá lớn. Tối đa {MAX_VIDEO_SIZE // (1024*1024)} MB.")

    # Generate unique video_id from file hash
    file_hash = hashlib.sha256(video_bytes).hexdigest()[:16]
    video_id = f"upload_{file_hash}"

    caption_text = caption.strip()

    # Insert into DB as user_pending
    try:
        insert_user_video(video_id, f"upload://{video_id}")
    except Exception:
        pass  # May already exist

    # Call Modal webhook for on-demand processing
    if not MODAL_WEBHOOK_URL:
        raise HTTPException(status_code=503, detail="Modal webhook chưa được cấu hình")

    # Encode video as base64 for transmission to Modal
    video_b64 = base64.b64encode(video_bytes).decode("utf-8")

    payload = {
        "video_id": video_id,
        "url": "",
        "caption": caption_text,
        "video_base64": video_b64,
        "video_filename": video.filename or "upload.mp4",
        "views": 0, "likes": 0, "comments": 0,
        "shares": 0, "saves": 0, "create_time": 0,
        "top_comments": [],
    }

    try:
        resp = requests.post(MODAL_WEBHOOK_URL, json=payload, timeout=120)
        resp.raise_for_status()
        return {
            "status": "queued",
            "video_id": video_id,
            "message": f"Video {video_id} đang được AI phân tích. Vui lòng chờ 1-3 phút.",
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Lỗi kết nối Modal: {str(e)[:200]}")


# ──────────────────────────────────────────────────
# POST /api/analyze-gemini — Scraper Webhook (Gemini Primary)
# ──────────────────────────────────────────────────
@router.post("/analyze-gemini", status_code=202)
async def analyze_gemini_webhook(
    payload: dict,
    background_tasks: BackgroundTasks
):
    """
    Webhook dành cho Scraper gửi video sang xử lý bằng Gemini 1.5 Flash.
    Trả về 202 Accepted ngay lập tức để không block event loop của FastAPI.
    Quá trình tải yt-dlp và xử lý Gemini được đưa vào background_tasks.
    """
    video_id = payload.get("video_id")
    url = payload.get("url")
    
    if not video_id or not url:
        raise HTTPException(status_code=400, detail="Thiếu video_id hoặc url")

    from backend.api.gemini_engine import process_video_with_gemini
    
    # Ném tác vụ phân tích vào background
    background_tasks.add_task(process_video_with_gemini, payload)
    
    return {
        "status": "queued",
        "video_id": video_id,
        "message": f"Video {video_id} đã đưa vào hàng đợi Gemini 1.5 Flash."
    }


# ──────────────────────────────────────────────────
# GET /api/analyze/{video_id} — Check Analysis Status
# ──────────────────────────────────────────────────
@router.get("/analyze/{video_id}")
def check_analysis(video_id: str):
    """Kiểm tra trạng thái phân tích của video."""
    video = get_video_by_id(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    result = dict(video)
    for key in result:
        val = result[key]
        if hasattr(val, 'isoformat'):
            result[key] = val.isoformat()
        elif isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
            result[key] = 0

    # Determine status
    status = result.get("ai_status", "pending")
    is_done = status == "completed"

    is_upload = video_id.startswith("upload_")
    analysis_type = "content_based" if is_upload else "engagement_based"

    trend_insights = None
    if result.get("trend_insights"):
        import json
        try:
            if isinstance(result["trend_insights"], str):
                trend_insights = json.loads(result["trend_insights"])
            else:
                trend_insights = result["trend_insights"]
        except Exception:
            pass

    # Generate recommendations if completed
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


def _generate_recommendations(video: dict) -> dict:
    """
    Sinh đề xuất tối ưu bằng Groq AI (Llama 3).
    Fallback về static rules nếu Groq không khả dụng.
    """
    from core.config.backend_settings import GROQ_API_KEY

    desc = video.get("video_description", "") or ""
    category = video.get("category", "") or ""
    keywords = video.get("top_keywords", "") or ""
    sentiment = video.get("video_sentiment", "") or ""
    velocity = float(video.get("viral_velocity", 0) or 0)
    engagement = float(video.get("engagement_rate", 0) or 0)
    viral_pct = float(video.get("viral_probability", 0) or 0)

    # Try Groq AI for intelligent recommendations
    if GROQ_API_KEY:
        try:
            import json
            from groq import Groq

            prompt = f"""Bạn là chuyên gia tư vấn nội dung TikTok Việt Nam hàng đầu.

THÔNG TIN VIDEO:
- Mô tả: {desc}
- Danh mục: {category}
- Từ khóa: {keywords}
- Cảm xúc: {sentiment}
- Xác suất viral: {viral_pct:.1f}%
- Engagement rate: {engagement:.1f}%
- Viral velocity: {velocity:.1f}

NHIỆM VỤ: Đưa ra 4 đề xuất cụ thể, thực tế để tăng khả năng viral cho video này.

TRẢ VỀ ĐÚNG JSON:
{{"hook": "Đề xuất cải thiện 3 giây đầu (2-3 câu cụ thể)", "audio": "Đề xuất nhạc nền/âm thanh trending phù hợp (2-3 câu)", "caption_hashtags": "Viết lại caption chuẩn SEO TikTok + 5-8 hashtag tiềm năng", "pacing_cta": "Đề xuất nhịp cắt dựng và Call-To-Action (2-3 câu)"}}"""

            client = Groq(api_key=GROQ_API_KEY)
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.5,
                max_tokens=500,
            )
            data = json.loads(response.choices[0].message.content)
            if all(k in data for k in ["hook", "audio", "caption_hashtags", "pacing_cta"]):
                return data
        except Exception as e:
            print(f"[!] Groq recommendation error: {e}")

    # Fallback: Static rule-based recommendations
    recs = {
        "hook": "Cải thiện 3 giây đầu tiên bằng câu hỏi kích thích hoặc hình ảnh gây sốc để giữ chân người xem.",
        "audio": "Sử dụng nhạc nền đang trending trên TikTok phù hợp với thể loại video.",
        "caption_hashtags": f"Thêm hashtag liên quan: {keywords}. Viết caption ngắn gọn, gợi mở tò mò.",
        "pacing_cta": "Thêm Call-To-Action rõ ràng ở cuối video (Follow, Like, Share). Giữ nhịp cắt nhanh 2-3 giây/cảnh.",
    }

    if engagement < 5:
        recs["hook"] = "⚠️ Engagement rất thấp. Cần hook mạnh hơn: mở đầu bằng conflict, drama hoặc reveal bất ngờ."
    if velocity > 1000:
        recs["pacing_cta"] = "🚀 Video đang lan truyền tốt! Đăng thêm video reaction/tiếp nối ngay trong 24h tới."
    if "TIÊU CỰC" in sentiment:
        recs["audio"] = "⚠️ Cảm xúc tiêu cực. Xem xét tone nhạc nền tích cực hơn, tránh nội dung gây tranh cãi."

    return recs
