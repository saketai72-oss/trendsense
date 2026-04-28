import os
import time
import json
import logging
import requests
from fastapi import BackgroundTasks
from google import genai
from google.genai import types
from core.config import service_settings as settings
from core.db.models import update_ai_results, insert_video_metadata
from services.tiktok_scraper.video_downloader import download_video
from services.ai_engine.math_utils import calculate_metrics

logger = logging.getLogger(__name__)

# Cấu hình Gemini Client (google-genai SDK mới)
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))

STANDARD_CATEGORIES = [
    "🎭 Giải trí", "🎵 Âm nhạc", "🍳 Ẩm thực", "💻 Công nghệ",
    "👗 Thời trang", "📚 Giáo dục", "🏋️ Thể thao", "🐾 Động vật",
    "💄 Làm đẹp", "📰 Tin tức", "💰 Tài chính",
]

def _delete_local_file(file_path):
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
            logger.info(f"🗑️ Đã xoá file nội bộ: {file_path}")
        except Exception as e:
            logger.error(f"Lỗi khi xoá file nội bộ {file_path}: {e}")

def _delete_gemini_file(file_name):
    try:
        client.files.delete(name=file_name)
        logger.info(f"🗑️ Đã xoá file trên Gemini: {file_name}")
    except Exception as e:
        logger.error(f"Lỗi khi xoá file trên Gemini {file_name}: {e}")

def _trigger_modal_fallback(video_data: dict):
    """Fallback gọi sang Modal nếu Gemini gặp sự cố hệ thống (429, 500, Timeout, IP Blocked)."""
    from core.config.backend_settings import MODAL_WEBHOOK_URL
    if not MODAL_WEBHOOK_URL:
        logger.error("❌ Không có MODAL_WEBHOOK_URL để fallback.")
        return
        
    logger.info(f"🔄 Kích hoạt Fallback sang Modal cho video {video_data.get('video_id')}")
    try:
        resp = requests.post(MODAL_WEBHOOK_URL, json=video_data, timeout=15)
        if resp.status_code == 200:
            logger.info(f"✅ Đã fallback sang Modal thành công.")
        else:
            logger.error(f"❌ Modal Fallback lỗi HTTP {resp.status_code}: {resp.text[:80]}")
    except Exception as e:
        logger.error(f"❌ Lỗi kết nối Modal Fallback: {e}")

def process_video_with_gemini(video_data: dict):
    """
    Luồng xử lý chính với Gemini 1.5 Flash (chạy ngầm trong BackgroundTasks):
    1. Tải video bằng yt-dlp (Có bắt lỗi IP Blocked để fallback).
    2. Upload lên Gemini API và Polling trạng thái.
    3. Sinh JSON phân tích.
    4. Tính metrics và lưu DB.
    5. Xoá file dọn dẹp ổ cứng.
    """
    video_id = video_data.get("video_id")
    url = video_data.get("url", "")
    caption = video_data.get("caption", "")

    logger.info(f"🚀 Bắt đầu xử lý Gemini cho {video_id}")
    
    # Đảm bảo video đã tồn tại trong DB (nếu Scraper chưa kịp insert)
    insert_video_metadata(video_id, video_data)
    
    # BƯỚC 1: Tải video
    # Chúng ta cần bắt log từ yt-dlp để biết có bị chặn IP không
    local_path = None
    try:
        local_path = download_video(url, video_id)
    except Exception as e:
        err_msg = str(e).lower()
        if "blocked" in err_msg or "403" in err_msg:
            logger.warning(f"⚠️ IP local bị chặn khi tải {video_id}. Đang chuyển hướng sang Modal...")
            _trigger_modal_fallback(video_data)
            return
        raise e

    if not local_path or not os.path.exists(local_path):
        logger.error(f"❌ Không thể tải video {video_id} (Có thể bị xoá hoặc bị chặn).")
        # Thử kiểm tra xem có phải do bị chặn ngầm không (yt-dlp đôi khi không văng exception)
        # Nếu link vẫn sống mà không tải được -> Khả năng cao là IP block
        logger.warning(f"⚠️ Link video {video_id} không tải được file. Thử đẩy sang Modal làm phương án cuối...")
        _trigger_modal_fallback(video_data)
        return

    gemini_file = None
    try:
        # BƯỚC 2: Upload lên Gemini
        logger.info(f"📤 Uploading lên Gemini File API: {local_path}")
        try:
            gemini_file = client.files.upload(file=local_path)
        except Exception as upload_err:
            raise RuntimeError(f"Lỗi hệ thống Gemini khi upload: {upload_err}")
            
        # BƯỚC 3: Xoá ngay file local để giải phóng ổ cứng
        _delete_local_file(local_path)

        # BƯỚC 4: Polling chờ trạng thái ACTIVE
        logger.info(f"⏳ Đang chờ Gemini xử lý video...")
        timeout_seconds = 180
        start_wait = time.time()
        
        # Ở SDK mới, state có thể là chuỗi hoặc Enum, ta kiểm tra cả hai
        while True:
            gemini_file = client.files.get(name=gemini_file.name)
            state = str(gemini_file.state).upper()
            
            if "ACTIVE" in state:
                break
            if "FAILED" in state:
                raise RuntimeError(f"Gemini xử lý file bị LỖI (FAILED).")
                
            if time.time() - start_wait > timeout_seconds:
                raise TimeoutError("Gemini xử lý video quá lâu (> 3 phút).")
            
            time.sleep(5)

        logger.info(f"✅ File Gemini đã sẵn sàng (ACTIVE). Bắt đầu suy luận...")

        # BƯỚC 5: Gọi Inference
        prompt = f"""Bạn là trợ lý AI phân tích video TikTok Việt Nam. Hãy xem video này và các thông tin sau:
Tiêu đề gốc (Caption): {caption}
Bình luận (Top comments): {json.dumps(video_data.get('top_comments', []), ensure_ascii=False)}

NHIỆM VỤ:
1. Viết 1 câu tóm tắt nội dung video (~20 từ), ngắn gọn, khách quan, tiếng Việt.
2. Chọn ĐÚNG 1 danh mục phù hợp nhất từ danh sách: {', '.join(STANDARD_CATEGORIES)}
3. Đánh giá cảm xúc cộng đồng dựa trên bình luận hoặc nội dung video. (sentiment chỉ được là 1 trong 3: "🟢 TÍCH CỰC", "🟡 TRUNG LẬP", "🔴 TIÊU CỰC")
4. Đánh giá điểm tích cực (positive_score) từ 0 đến 100.
5. Trích xuất 3-5 từ khóa chính (tiếng Việt).
6. Phải bóc tách hoặc tóm tắt lời thoại tiếng Việt trong video và gán vào trường `audio_transcript`. Nếu video chỉ có nhạc nền, không có người nói, bắt buộc trả về chuỗi rỗng "" cho trường `audio_transcript`. Không được bịa ra text giải thích tiếng nhạc.

BẮT BUỘC TRẢ VỀ ĐÚNG ĐỊNH DẠNG JSON.
"""
        # BƯỚC 5: Gọi Inference
        selected_model = "gemini-2.5-flash"
        logger.info(f"🤖 Đang sử dụng model: {selected_model}")
        response = client.models.generate_content(
            model=selected_model,
            contents=[gemini_file, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.3,
            )
        )

        raw_json = response.text
        logger.info(f"🎯 Gemini Output: {raw_json[:150]}...")
        result = json.loads(raw_json)

        # BƯỚC 6: Validate Category và tính toán Metrics
        cat = result.get("category", "🌍 Khác")
        matched = "🌍 Khác"
        for std in STANDARD_CATEGORIES:
            if std.lower() == cat.lower() or (" " in std and std.split(" ", 1)[-1].lower() in cat.lower()):
                matched = std
                break
        
        # Calculate Metrics
        vph, er, velocity = calculate_metrics(
            views=video_data.get("views", 0),
            likes=video_data.get("likes", 0),
            comments=video_data.get("comments", 0),
            shares=video_data.get("shares", 0),
            saves=video_data.get("saves", 0),
            create_time=video_data.get("create_time", 0)
        )

        # BƯỚC 7: Cập nhật DB
        final_data = {
            "video_description": result.get("summary", ""),
            "category": matched,
            "video_sentiment": result.get("sentiment", "🟡 TRUNG LẬP"),
            "positive_score": result.get("positive_score", 50.0),
            "top_keywords": ", ".join(result.get("keywords", [])[:5]),
            "audio_transcript": result.get("audio_transcript", ""),
            "views_per_hour": vph,
            "engagement_rate": er,
            "viral_velocity": velocity,
            "ai_status": "completed",
        }

        update_ai_results(video_id, final_data)
        logger.info(f"✅ Hoàn thành luồng Gemini cho video {video_id}")

    except Exception as e:
        logger.error(f"❌ Lỗi luồng Gemini ({video_id}): {e}")
        err_msg = str(e).lower()
        
        # Chỉ Fallback nếu là lỗi hệ thống (Timeout, RuntimeError, API Limit)
        if "timeout" in err_msg or "runtimeerror" in err_msg or "429" in err_msg or "503" in err_msg or "500" in err_msg:
            logger.info("📡 Phát hiện lỗi hệ thống API -> Kích hoạt Fallback sang Modal.")
            _trigger_modal_fallback(video_data)
        else:
            _fallback_error_db(video_id, f"Lỗi Gemini: {str(e)[:50]}")
    
    finally:
        # BƯỚC 8: Xoá file Gemini để giải phóng Quota
        if gemini_file and hasattr(gemini_file, 'name'):
            _delete_gemini_file(gemini_file.name)
        _delete_local_file(local_path)


def _fallback_error_db(video_id, reason="Lỗi xử lý"):
    update_ai_results(video_id, {
        "video_description": reason,
        "category": "Lỗi",
        "video_sentiment": "🟡 TRUNG LẬP",
        "positive_score": 50.0,
        "ai_status": "error"
    })

