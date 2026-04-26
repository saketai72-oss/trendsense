"""
TrendSense AI Core — Modal Serverless GPU
==========================================
Pipeline: POST → Download Video → Whisper + BLIP + EasyOCR (GPU) → Groq AI → Supabase

Triển khai:
  pip install modal
  modal secret create trendsense-secrets GROQ_API_KEY=gsk_xxx DATABASE_URL=postgresql://xxx
  modal deploy services/ai_engine/modal_app.py

Sau khi deploy, ghi lại URL webhook (dạng https://xxx--trendsense-ai-analyze.modal.run)
và đặt vào MODAL_WEBHOOK_URL trong .env + GitHub Secrets.
"""
import modal
import os

# ============================================================
# MODAL APP DEFINITION
# ============================================================
app = modal.App("trendsense-ai")

# --- Base Image: Chứa các thư viện hệ thống (ffmpeg, libgl) ---
base_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("ffmpeg", "libgl1-mesa-glx", "libglib2.0-0")
    .pip_install("fastapi[standard]")
)

# --- Image phân tầng cho GPU ---
gpu_image = (
    base_image
    # Layer 1: Thư viện NẶNG (ít thay đổi → cache lâu dài)
    .pip_install(
        "torch",
        "transformers",
        "faster-whisper",
        "easyocr",
    )
    # Layer 2: Thư viện NHẸ (xử lý video & API)
    .pip_install(
        "groq",
        "yt-dlp",
        "moviepy",
        "opencv-python-headless",
        "Pillow",
        "psycopg2-binary",
        "requests",
    )
)

# --- Image cho Webhook (nhẹ, không GPU) ---
webhook_image = base_image

# Volume persistent để cache model AI (tránh tải lại từ HuggingFace mỗi lần cold start)
model_volume = modal.Volume.from_name("trendsense-models", create_if_missing=True)
MODEL_DIR = "/models"

# 11 danh mục chuẩn TrendSense (inline để Modal không cần import từ project)
STANDARD_CATEGORIES = [
    "🎭 Giải trí", "🎵 Âm nhạc", "🍳 Ẩm thực", "💻 Công nghệ",
    "👗 Thời trang", "📚 Giáo dục", "🏋️ Thể thao", "🐾 Động vật",
    "💄 Làm đẹp", "📰 Tin tức", "💰 Tài chính",
]


# ============================================================
# LAZY MODEL LOADERS (giữ trong globals để tái sử dụng giữa các request)
# ============================================================
_whisper_model = None
_blip_processor = None
_blip_model = None
_ocr_reader = None


def _get_whisper():
    """Load Faster-Whisper model (base, float16 trên CUDA)."""
    global _whisper_model
    if _whisper_model is None:
        import os
        import site
        # CTranslate2 cần libcublas.so.12. Torch đã cài sẵn trong site-packages/nvidia.
        try:
            site_pkgs = site.getsitepackages()[0]
            os.environ["LD_LIBRARY_PATH"] = (
                f"{site_pkgs}/nvidia/cublas/lib:{site_pkgs}/nvidia/cudnn/lib:"
                + os.environ.get("LD_LIBRARY_PATH", "")
            )
        except Exception:
            pass

        from faster_whisper import WhisperModel
        print("[*] Loading Whisper (base, CUDA float16)...")
        _whisper_model = WhisperModel(
            "base", device="cuda", compute_type="float16",
            download_root=f"{MODEL_DIR}/whisper",
        )
        print("[✓] Whisper ready.")
    return _whisper_model


def _get_blip():
    """Load BLIP image captioning model (CUDA)."""
    global _blip_processor, _blip_model
    if _blip_processor is None:
        import torch
        from transformers import BlipProcessor, BlipForConditionalGeneration
        print("[*] Loading BLIP captioning (CUDA)...")
        cache = f"{MODEL_DIR}/blip"
        _blip_processor = BlipProcessor.from_pretrained(
            "Salesforce/blip-image-captioning-base", cache_dir=cache,
        )
        _blip_model = BlipForConditionalGeneration.from_pretrained(
            "Salesforce/blip-image-captioning-base", cache_dir=cache,
        ).to("cuda")
        print("[✓] BLIP ready.")
    return _blip_processor, _blip_model


def _get_ocr():
    """Load EasyOCR reader (Vietnamese + English, GPU)."""
    global _ocr_reader
    if _ocr_reader is None:
        import easyocr
        import logging
        logging.getLogger("easyocr").setLevel(logging.ERROR)
        print("[*] Loading EasyOCR (vi+en, GPU)...")
        _ocr_reader = easyocr.Reader(
            ["vi", "en"], gpu=True,
            model_storage_directory=f"{MODEL_DIR}/easyocr",
        )
        print("[✓] EasyOCR ready.")
    return _ocr_reader


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _save_uploaded_video(video_base64: str, video_id: str, filename: str = "upload.mp4"):
    """Decode base64 video data and save to /tmp. Returns path or None."""
    import base64

    # Determine extension from filename
    ext = "mp4"
    if "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()

    out_path = f"/tmp/{video_id}.{ext}"
    try:
        video_bytes = base64.b64decode(video_base64)
        with open(out_path, "wb") as f:
            f.write(video_bytes)
        print(f"    [✓] Saved uploaded video: {os.path.basename(out_path)} ({len(video_bytes) / 1024 / 1024:.1f} MB)")
        return out_path
    except Exception as e:
        print(f"    [!] Failed to decode uploaded video: {str(e)[:120]}")
        return None


def _download_video(url: str, video_id: str):
    """Tải video từ TikTok vào /tmp bằng yt-dlp. Trả về path hoặc None."""
    import yt_dlp
    import glob

    ydl_opts = {
        "outtmpl": f"/tmp/{video_id}.%(ext)s",
        "format": (
            "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/"
            "best[height<=480][ext=mp4]/best[ext=mp4]/best"
        ),
        "quiet": True,
        "no_warnings": True,
        "retries": 3,
        "socket_timeout": 60,
        "merge_output_format": "mp4",
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        files = glob.glob(f"/tmp/{video_id}.*")
        if files:
            print(f"    [✓] Downloaded: {os.path.basename(files[0])}")
            return files[0]
        return None
    except Exception as e:
        print(f"    [!] yt-dlp error: {str(e)[:120]}")
        return None


def _extract_frames(video_path, total_frames=4, ocr_frames=2):
    """Trích xuất frames cho BLIP (PIL) và EasyOCR (numpy array)."""
    import cv2
    from PIL import Image

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return [], []

    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total <= 0:
        cap.release()
        return [], []

    start_f = int(total * 0.1)
    end_f = int(total * 0.9)
    usable = max(end_f - start_f, 1)
    positions = [start_f + int(usable * (i + 0.5) / total_frames) for i in range(total_frames)]

    pil_frames, cv2_frames = [], []
    for i, pos in enumerate(positions):
        cap.set(cv2.CAP_PROP_POS_FRAMES, min(pos, total - 1))
        ret, frame = cap.read()
        if ret:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_frames.append(Image.fromarray(rgb))
            if i < ocr_frames:
                cv2_frames.append(rgb)

    cap.release()
    return pil_frames, cv2_frames


def _run_whisper(video_path):
    """Trích xuất audio → text bằng Faster-Whisper (GPU)."""
    import tempfile
    from moviepy import VideoFileClip

    mp3_path = None
    try:
        clip = VideoFileClip(video_path)
        if clip.audio is None:
            clip.close()
            return "Không có âm thanh."

        fd, mp3_path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)

        duration = min(clip.duration, 30.0)
        sub = clip.subclipped(0, duration)
        import logging
        logging.getLogger("moviepy").setLevel(logging.ERROR)
        sub.audio.write_audiofile(mp3_path, logger=None)
        clip.close()
        sub.close()

        model = _get_whisper()
        segments, _ = model.transcribe(mp3_path, beam_size=2)
        text = " ".join(seg.text for seg in segments).strip()
        return text if text else "Không nghe được tiếng."

    except Exception as e:
        print(f"    [!] Whisper error: {e}")
        return "Lỗi trích xuất âm thanh."
    finally:
        if mp3_path and os.path.exists(mp3_path):
            try:
                os.remove(mp3_path)
            except Exception:
                pass


def _run_blip(pil_frames):
    """Sinh caption mô tả từng frame bằng BLIP (GPU)."""
    import torch
    if not pil_frames:
        return ""

    processor, model = _get_blip()
    captions = []
    for frame in pil_frames:
        try:
            inputs = processor(frame, return_tensors="pt").to("cuda")
            with torch.no_grad():
                out = model.generate(**inputs, max_new_tokens=50)
            cap = processor.decode(out[0], skip_special_tokens=True).strip()
            if cap and cap not in captions:
                captions.append(cap)
        except Exception:
            pass
    return ". ".join(captions)


def _run_ocr(cv2_frames):
    """Đọc chữ trên màn hình bằng EasyOCR (GPU)."""
    if not cv2_frames:
        return ""

    reader = _get_ocr()
    all_text = []
    for frame in cv2_frames:
        try:
            results = reader.readtext(frame, detail=0, paragraph=True)
            for t in results:
                if t not in all_text and len(t) > 3:
                    all_text.append(t)
        except Exception:
            pass
    return " | ".join(all_text)


def _call_groq(audio_text, ocr_text, blip_text, caption, top_comments):
    """
    Gọi Groq Llama-3 70B — MỘT lệnh duy nhất thay thế 3 model riêng lẻ:
    Tóm tắt + Phân loại + Đánh giá cảm xúc + Trích xuất từ khóa.
    Có retry với exponential backoff nếu Rate Limit 429.
    """
    import json
    import time
    from groq import Groq

    # Cắt gọn độ dài dữ liệu để tránh lỗi 400 (Vượt quá độ dài Context Window của LLM)
    audio_t = str(audio_text)[:3000] if audio_text else ""
    ocr_t = str(ocr_text)[:1500] if ocr_text else ""
    blip_t = str(blip_text)[:1500] if blip_text else ""
    cap_t = str(caption)[:500] if caption else ""

    categories_str = ", ".join(STANDARD_CATEGORIES)
    
    # Chỉ lấy tối đa 15 comments đầu tiên và cắt bớt ký tự nếu quá dài
    safe_comments = []
    for c in (top_comments or [])[:15]:
        text = c.get('text', '')
        if text:
            safe_comments.append(f"  - {str(text)[:200]}")
    comments_str = "\n".join(safe_comments) or "Không có bình luận."


    prompt = f"""Bạn là trợ lý AI phân tích video TikTok Việt Nam.

DỮ LIỆU TRÍCH XUẤT TỪ VIDEO:
1. Âm thanh (Transcript): {audio_t}
2. Chữ trên màn hình (OCR): {ocr_t}
3. Bối cảnh hình ảnh (Vision): {blip_t}
4. Tiêu đề gốc: {cap_t}
5. Top bình luận:
{comments_str}

NHIỆM VỤ:
1. Viết 1 câu tóm tắt nội dung video (~20 từ), ngắn gọn, khách quan, tiếng Việt.
2. Chọn ĐÚNG 1 danh mục phù hợp nhất từ danh sách: [{categories_str}]
3. Đánh giá cảm xúc cộng đồng dựa trên bình luận (nếu có).
4. Trích xuất 3-5 từ khóa chính (tiếng Việt, ưu tiên danh từ/tên riêng).

BẮT BUỘC TRẢ VỀ ĐÚNG ĐỊNH DẠNG JSON SAU (không giải thích thêm):
{{"summary": "câu tóm tắt tiếng Việt", "category": "emoji + tên danh mục", "sentiment": "🟢 TÍCH CỰC", "positive_score": 75, "keywords": ["từ khóa 1", "từ khóa 2"]}}

Lưu ý:
- sentiment chỉ được là 1 trong 3: "🟢 TÍCH CỰC", "🟡 TRUNG LẬP", "🔴 TIÊU CỰC"
- positive_score là số nguyên từ 0 đến 100
- category phải copy chính xác từ danh sách (bao gồm emoji)"""

    client = Groq(api_key=os.environ["GROQ_API_KEY"])

    # Danh sách model theo thứ tự ưu tiên. Nếu Llama 70B hết quota, fallback sang 8B
    models = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "llama3-8b-8192"]

    for attempt in range(5): # Tăng lên 5 lần thử
        try:
            # Chọn model: 2 lần đầu dùng 70b, sau đó fallback sang 8b
            current_model = models[0] if attempt < 2 else (models[1] if attempt < 4 else models[2])
            
            response = client.chat.completions.create(
                model=current_model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=300,
            )
            raw = response.choices[0].message.content
            data = json.loads(raw)

            # --- Validate & normalize category ---
            cat = data.get("category", "🌍 Khác")
            matched = "🌍 Khác"
            for std in STANDARD_CATEGORIES:
                if std.lower() == cat.lower():
                    matched = std
                    break
                # Fuzzy match: bỏ emoji, so sánh tên
                if " " in std and std.split(" ", 1)[-1].lower() in cat.lower():
                    matched = std
                    break
            data["category"] = matched

            # --- Validate sentiment ---
            sentiment = data.get("sentiment", "🟡 TRUNG LẬP")
            if "TÍCH CỰC" in sentiment.upper():
                data["sentiment"] = "🟢 TÍCH CỰC"
            elif "TIÊU CỰC" in sentiment.upper():
                data["sentiment"] = "🔴 TIÊU CỰC"
            else:
                data["sentiment"] = "🟡 TRUNG LẬP"

            # --- Validate positive_score ---
            try:
                score = float(data.get("positive_score", 50))
                data["positive_score"] = max(0.0, min(100.0, score))
            except (ValueError, TypeError):
                data["positive_score"] = 50.0

            # --- Validate keywords ---
            kws = data.get("keywords", [])
            if not isinstance(kws, list):
                kws = []
            data["keywords"] = [str(k) for k in kws[:5]]

            return data

        except Exception as e:
            err_str = str(e).lower()
            if ("rate_limit" in err_str or "429" in err_str) and attempt < 4:
                import random
                wait = 10 + (attempt * 6) + random.uniform(1, 4)  # Đợi 11-14s, 17-20s, 23-26s...
                print(f"    ⏳ Groq Rate Limit (429) → chờ {wait:.1f}s (retry {attempt + 1}/5, next model: {models[0] if attempt + 1 < 2 else models[1]})...")
                time.sleep(wait)
            elif "400" in err_str or "context_length" in err_str:
                print(f"    [!] Groq 400 Bad Request (có thể do text quá dài): {str(e)[:120]}")
                # Nếu text vẫn quá dài, rút gọn thêm nữa cho lần retry sau
                prompt = prompt[:len(prompt)//2] + "\n\n... (Dữ liệu đã bị cắt bớt do quá dài) ... BẮT BUỘC TRẢ VỀ ĐÚNG ĐỊNH DẠNG JSON"
            else:
                print(f"    [!] Groq error: {str(e)[:120]}")
                break

    # Fallback nếu Groq thất bại hoàn toàn
    return {
        "summary": "Lỗi khi gọi Groq AI tổng hợp.",
        "category": "🌍 Khác",
        "sentiment": "🟡 TRUNG LẬP",
        "positive_score": 50.0,
        "keywords": [],
        "ai_status": "error",
    }


def _calculate_metrics(video_data):
    """Tính Views/Hour, Engagement Rate, Viral Velocity (pure Python)."""
    import time as _time
    import math

    # Ép kiểu an toàn về số nguyên
    try:
        views = int(video_data.get("views", 0) or 0)
        likes = int(video_data.get("likes", 0) or 0)
        comments = int(video_data.get("comments", 0) or 0)
        shares = int(video_data.get("shares", 0) or 0)
        saves = int(video_data.get("saves", 0) or 0)
        create_time = int(video_data.get("create_time", 0) or 0)
    except (ValueError, TypeError):
        # Fallback nếu dữ liệu rác
        return {"vph": 0, "er": 0, "velocity": 0}

    current = int(_time.time())
    # Tính tuổi video theo giờ (tối thiểu 0.1h để tránh chia cho 0)
    age_h = max((current - create_time) / 3600, 0.1) if create_time > 0 else 0.1
    vph = round(views / age_h, 2)

    # Điểm tương tác: Like(1) + Cmt(2) + Save(3) + Share(4)
    eng_pts = likes + (comments * 2) + (saves * 3) + (shares * 4)
    er = round((eng_pts / views) * 100, 2) if views > 0 else 0.0

    # Viral Velocity: Tốc độ lan truyền dựa trên VPH và ER theo thang log
    velocity = round((vph * er) / math.log10(age_h + 10), 2)

    return {"vph": vph, "er": er, "velocity": velocity}


def _update_supabase(video_id, results):
    """Ghi kết quả AI vào bảng videos trên Supabase PostgreSQL."""
    import psycopg2

    db_url = os.environ["DATABASE_URL"]
    conn = psycopg2.connect(db_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE videos SET
                    category = %s,
                    video_description = %s,
                    top_keywords = %s,
                    video_sentiment = %s,
                    positive_score = %s,
                    views_per_hour = %s,
                    engagement_rate = %s,
                    viral_velocity = %s,
                    viral_probability = %s,
                    ai_status = %s
                WHERE video_id = %s
                """,
                (
                    [results.get("category")] if results.get("category") not in ["🌍 Khác", "Lỗi"] else [],
                    results.get("video_description", ""),
                    results.get("top_keywords", ""),
                    results.get("video_sentiment", "🟡 TRUNG LẬP"),
                    results.get("positive_score", 0),
                    results.get("views_per_hour", 0),
                    results.get("engagement_rate", 0),
                    results.get("viral_velocity", 0),
                    results.get("viral_probability", 0),
                    results.get("ai_status", "completed"),
                    video_id,
                ),
            )
        conn.commit()
        print(f"    [✓] Đã cập nhật Supabase: {video_id}")
    except Exception as e:
        print(f"    [!] Supabase error: {e}")
        conn.rollback()
    finally:
        conn.close()


def _update_status(video_id, status):
    """Cập nhật ai_status nhanh chóng để Supabase Realtime bắn event về Frontend."""
    import psycopg2
    db_url = os.environ["DATABASE_URL"]
    conn = psycopg2.connect(db_url)
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE videos SET ai_status = %s WHERE video_id = %s", (status, video_id))
        conn.commit()
    except Exception as e:
        print(f"    [!] Status update error: {e}")
        conn.rollback()
    finally:
        conn.close()


# ============================================================
# VIDEO METADATA EXTRACTION
# ============================================================

def _extract_video_metadata(video_path):
    """
    Trích xuất metadata tĩnh từ video file.
    Scene cut detection chạy trên bản resize 360p để tối ưu tài nguyên GPU.
    """
    import cv2
    from moviepy import VideoFileClip

    result = {
        "duration": 0, "orientation": "unknown",
        "scene_cut_count": 0, "width": 0, "height": 0, "fps": 0,
    }

    # 1. Duration từ MoviePy
    try:
        clip = VideoFileClip(video_path)
        result["duration"] = round(clip.duration, 1)
        clip.close()
    except Exception:
        pass

    # 2. Resolution + Orientation từ OpenCV
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return result

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    result["width"], result["height"], result["fps"] = w, h, fps

    if h > w * 1.2:
        result["orientation"] = "portrait"
    elif w > h * 1.2:
        result["orientation"] = "landscape"
    else:
        result["orientation"] = "square"

    # 3. Scene cut detection (resize → 360p, grayscale, frame diff)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    scale = min(360 / max(h, 1), 1.0)
    new_w, new_h = int(w * scale), int(h * scale)
    if new_w < 1:
        new_w = 1
    if new_h < 1:
        new_h = 1

    prev_gray = None
    cuts = 0
    sample_interval = max(int(fps / 5), 1)  # Sample 5 frames/giây

    for i in range(0, total_frames, sample_interval):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ret, frame = cap.read()
        if not ret:
            break

        small = cv2.resize(frame, (new_w, new_h))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

        if prev_gray is not None:
            diff = cv2.absdiff(prev_gray, gray)
            mean_diff = diff.mean()
            if mean_diff > 35:  # Threshold cho scene change
                cuts += 1
        prev_gray = gray

    cap.release()
    result["scene_cut_count"] = cuts
    return result


# ============================================================
# TREND BENCHMARK CACHE (per-container, TTL 2h)
# ============================================================
_benchmark_cache = {}
_CACHE_TTL = 7200  # 2 giờ

# Stopwords cho audio transcript matching
_AUDIO_STOPWORDS = {
    "và", "là", "của", "có", "trong", "với", "cho", "không", "những", "một",
    "các", "khi", "để", "mà", "thì", "được", "này", "người", "tôi", "bạn",
    "the", "to", "a", "is", "of", "it", "in", "for", "this", "that", "you",
    "and", "but", "so", "are", "was", "with", "not", "on", "at", "from",
}


def _get_cached_benchmarks():
    """
    Lấy benchmark data từ Supabase, cache per-container 2h.
    NOTE: Modal serverless = mỗi container có cache riêng. Chấp nhận ở giai đoạn này.
    """
    import time
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from collections import Counter

    now = time.time()
    if _benchmark_cache.get("ts", 0) + _CACHE_TTL > now:
        return _benchmark_cache["data"]

    db_url = os.environ["DATABASE_URL"]
    conn = psycopg2.connect(db_url)
    data = {
        "trending_categories": [],
        "trending_keywords": [],
        "duration_stats": [],
        "viral_transcripts": [],
    }

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 1. Trending categories
            cur.execute("""
                SELECT unnest(category) as category,
                       COUNT(*) as count,
                       COALESCE(AVG(viral_velocity), 0) as avg_velocity,
                       COALESCE(AVG(engagement_rate), 0) as avg_engagement
                FROM videos
                WHERE views > 0 AND ai_status = 'completed'
                  AND scrape_date >= CURRENT_DATE - INTERVAL '14 days'
                  AND category IS NOT NULL
                GROUP BY unnest(category)
                ORDER BY avg_velocity DESC
            """)
            data["trending_categories"] = cur.fetchall()

            # 2. Trending keywords (from videos with velocity > median)
            cur.execute("""
                SELECT top_keywords FROM videos
                WHERE views > 0 AND ai_status = 'completed'
                  AND scrape_date >= CURRENT_DATE - INTERVAL '14 days'
                  AND top_keywords IS NOT NULL AND top_keywords != ''
                  AND viral_velocity > (
                      SELECT COALESCE(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY viral_velocity), 0)
                      FROM videos WHERE views > 0 AND scrape_date >= CURRENT_DATE - INTERVAL '14 days'
                  )
            """)
            rows = cur.fetchall()
            kw_counter = Counter()
            for row in rows:
                for k in row["top_keywords"].split(","):
                    k = k.strip()
                    if k:
                        kw_counter[k] += 1
            data["trending_keywords"] = [{"keyword": k, "count": c} for k, c in kw_counter.most_common(50)]

            # 3. Duration stats by category (MEDIAN, not AVG)
            cur.execute("""
                SELECT
                    unnest(category) as category,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY video_duration) as median_duration,
                    COUNT(*) as sample_count
                FROM videos
                WHERE views > 0 AND ai_status = 'completed'
                  AND scrape_date >= CURRENT_DATE - INTERVAL '14 days'
                  AND category IS NOT NULL
                  AND video_duration IS NOT NULL AND video_duration > 0
                GROUP BY unnest(category)
                HAVING COUNT(*) >= 3
                ORDER BY median_duration ASC NULLS LAST
            """)
            data["duration_stats"] = cur.fetchall()

            # 4. Viral audio transcripts (top 30)
            cur.execute("""
                SELECT video_id, audio_transcript, viral_velocity
                FROM videos
                WHERE views > 0 AND ai_status = 'completed'
                  AND scrape_date >= CURRENT_DATE - INTERVAL '14 days'
                  AND audio_transcript IS NOT NULL
                  AND audio_transcript != ''
                  AND audio_transcript != 'Không nghe được tiếng.'
                  AND audio_transcript != 'Không có âm thanh.'
                ORDER BY viral_velocity DESC
                LIMIT 30
            """)
            data["viral_transcripts"] = cur.fetchall()

    except Exception as e:
        print(f"    [!] Benchmark query error: {e}")
    finally:
        conn.close()

    _benchmark_cache["data"] = data
    _benchmark_cache["ts"] = now
    print(f"    [📊] Loaded benchmarks: {len(data['trending_categories'])} cats, "
          f"{len(data['trending_keywords'])} kws, {len(data['duration_stats'])} dur stats, "
          f"{len(data['viral_transcripts'])} transcripts")
    return data


# ============================================================
# TREND ALIGNMENT SCORER (Python Deterministic)
# ============================================================

def _score_trend_alignment(groq_result, metadata, audio_transcript, benchmarks):
    """
    Tính Trend Alignment Score (0-100) hoàn toàn bằng Python.
    Dynamic weight redistribution nếu audio rỗng (video nhạc/dance).
    """
    has_audio = bool(
        audio_transcript and audio_transcript.strip()
        and audio_transcript not in ["Không nghe được tiếng.", "Không có âm thanh.", "Lỗi trích xuất âm thanh."]
    )

    # --- Dynamic Weights ---
    weights = {"category": 30, "content": 25, "audio": 20, "duration": 15, "format": 10}
    if not has_audio:
        weights.pop("audio")
        total_remaining = sum(weights.values())  # 80
        for k in weights:
            weights[k] = round(weights[k] / total_remaining * 100)
        # → category≈37, content≈31, duration≈19, format≈13

    scores = {}

    # ═══ 1. CATEGORY SCORE ═══
    video_category = groq_result.get("category", "")
    trending_cats = benchmarks.get("trending_categories", [])
    cat_names = [c["category"] for c in trending_cats]
    cat_rank = next((i for i, name in enumerate(cat_names) if name == video_category), 99)

    if cat_rank < 3:
        scores["category"] = {"raw": 1.0, "label": "🔥 Top 3 trending"}
    elif cat_rank < 5:
        scores["category"] = {"raw": 0.7, "label": "📈 Top 5 trending"}
    elif cat_rank < 8:
        scores["category"] = {"raw": 0.4, "label": "📊 Trung bình"}
    else:
        scores["category"] = {"raw": 0.15, "label": "📉 Ít phổ biến"}

    # ═══ 2. CONTENT/KEYWORD SCORE ═══
    video_keywords = set(k.lower().strip() for k in groq_result.get("keywords", []) if k.strip())
    trending_kws = set(k["keyword"].lower() for k in benchmarks.get("trending_keywords", []))

    if video_keywords and trending_kws:
        overlap = len(video_keywords & trending_kws)
        ratio = min(overlap / max(len(video_keywords), 1), 1.0)
        raw = min(ratio * 2.5, 1.0)
        scores["content"] = {"raw": raw, "label": f"{overlap} keywords trùng trend"}
    else:
        scores["content"] = {"raw": 0.2, "label": "Chưa đủ dữ liệu keywords"}

    # ═══ 3. AUDIO SCORE (skip nếu không có giọng nói) ═══
    if has_audio:
        viral_transcripts = benchmarks.get("viral_transcripts", [])
        audio_words = set(audio_transcript.lower().split()) - _AUDIO_STOPWORDS
        trending_audio_words = set()
        for vt in viral_transcripts:
            t = vt.get("audio_transcript", "")
            if t:
                trending_audio_words.update(set(t.lower().split()[:50]) - _AUDIO_STOPWORDS)

        if trending_audio_words and audio_words:
            audio_overlap = len(audio_words & trending_audio_words)
            audio_raw = min(audio_overlap / 10, 1.0)
        else:
            audio_raw = 0.5  # Neutral nếu chưa có benchmark

        label = "🔥 Nội dung audio bám trend" if audio_raw > 0.6 else (
            "📝 Có nội dung audio" if audio_raw > 0.3 else "💬 Audio ít liên quan trend"
        )
        scores["audio"] = {"raw": audio_raw, "label": label}

    # ═══ 4. DURATION SCORE ═══
    duration = metadata.get("duration", 0)
    duration_stats = benchmarks.get("duration_stats", [])
    cat_duration = next((d for d in duration_stats if d["category"] == video_category), None)

    if cat_duration and duration > 0:
        optimal = float(cat_duration.get("median_duration") or 15)
        if optimal <= 0:
            optimal = 15
        deviation = abs(duration - optimal) / max(optimal, 1)
        dur_raw = max(1.0 - deviation, 0)

        if duration <= 15:
            label = f"✅ Ngắn gọn ({duration:.0f}s)"
        elif duration <= 30:
            label = f"📏 Vừa phải ({duration:.0f}s, chuẩn: {optimal:.0f}s)"
        else:
            label = f"⚠️ Dài ({duration:.0f}s, chuẩn viral: {optimal:.0f}s)"
        scores["duration"] = {"raw": dur_raw, "label": label}
    else:
        # Fallback: video ngắn < 30s → tốt, > 60s → kém
        if duration <= 30:
            scores["duration"] = {"raw": 0.7, "label": f"📏 {duration:.0f}s (chưa có benchmark)"}
        else:
            scores["duration"] = {"raw": 0.3, "label": f"⚠️ {duration:.0f}s (có thể quá dài)"}

    # ═══ 5. FORMAT SCORE ═══
    orientation = metadata.get("orientation", "unknown")
    scene_cuts = metadata.get("scene_cut_count", 0)
    fmt_raw = 0.0

    if orientation == "portrait":
        fmt_raw += 0.5
        orient_label = "✅ Dọc (chuẩn TikTok)"
    elif orientation == "square":
        fmt_raw += 0.3
        orient_label = "📐 Vuông"
    else:
        fmt_raw += 0.1
        orient_label = "⚠️ Ngang (không tối ưu cho TikTok)"

    if duration > 15 and scene_cuts >= 3:
        fmt_raw += 0.5
        cut_label = f"✅ {scene_cuts} cắt cảnh (nhịp nhanh)"
    elif duration <= 15:
        fmt_raw += 0.4
        cut_label = f"Video ngắn ({scene_cuts} cuts)"
    else:
        fmt_raw += 0.15
        cut_label = f"⚠️ Chỉ {scene_cuts} cắt cảnh cho video {duration:.0f}s"

    scores["format"] = {"raw": fmt_raw, "label": f"{orient_label} · {cut_label}"}

    # ═══ TÍNH TỔNG ═══
    total = 0
    breakdown = {}
    for key, w in weights.items():
        if key in scores:
            pts = round(scores[key]["raw"] * w, 1)
            total += pts
            breakdown[key] = {
                "score": pts,
                "max": w,
                "pct": round(scores[key]["raw"] * 100),
                "label": scores[key]["label"],
            }

    return {
        "trend_alignment_score": round(min(total, 100), 1),
        "breakdown": breakdown,
        "has_audio": has_audio,
        "weights_used": weights,
    }


# ============================================================
# GROQ TREND INSIGHT GENERATOR
# ============================================================

def _generate_trend_insights(score_result, groq_summary, metadata):
    """
    Groq sinh nhận xét tự nhiên + đề xuất hành động từ scores đã tính bằng Python.
    Groq KHÔNG tự tính điểm — chỉ viết nhận xét dựa trên scores có sẵn.
    """
    import json
    from groq import Groq

    breakdown_str = json.dumps(score_result.get("breakdown", {}), ensure_ascii=False, indent=2)
    total_score = score_result.get("trend_alignment_score", 0)

    prompt = f"""Bạn là chuyên gia tư vấn nội dung TikTok Việt Nam hàng đầu.

ĐIỂM PHÂN TÍCH VIDEO (đã tính sẵn bằng hệ thống, KHÔNG ĐƯỢC thay đổi):
- Tổng điểm bám trend: {total_score}/100
- Chi tiết các trục:
{breakdown_str}
- Tóm tắt video: {groq_summary}
- Thời lượng: {metadata.get('duration', 0)}s | Định dạng: {metadata.get('orientation', 'unknown')} | Cắt cảnh: {metadata.get('scene_cut_count', 0)}

NHIỆM VỤ: Dựa CHÍNH XÁC vào các điểm số trên, viết nhận xét ngắn gọn bằng tiếng Việt.
- Nêu 1 điểm mạnh nổi bật nhất
- Nêu 1-2 đề xuất cải thiện CỤ THỂ, THỰC TẾ (vd: "cắt ngắn xuống 15s", "đổi sang khung dọc")
- Viết nhận xét tổng quan 2-3 câu

TRẢ VỀ ĐÚNG JSON:
{{"overall_comment": "Nhận xét tổng quan 2-3 câu", "top_strength": "Điểm mạnh nổi bật nhất", "top_improvement": "Đề xuất cải thiện quan trọng nhất"}}"""

    try:
        client = Groq(api_key=os.environ["GROQ_API_KEY"])
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.4,
            max_tokens=300,
        )
        data = json.loads(response.choices[0].message.content)
        if "overall_comment" in data:
            return data
    except Exception as e:
        print(f"    [!] Groq insight error: {e}")

    # Fallback: template-based insights
    return {
        "overall_comment": f"Video đạt {total_score}/100 điểm bám trend. Hãy xem chi tiết từng trục để tối ưu.",
        "top_strength": "Xem breakdown chi tiết ở trên.",
        "top_improvement": "Hãy tập trung vào trục có điểm thấp nhất để cải thiện.",
    }


# ============================================================
# UPLOAD ANALYSIS — Supabase Writer
# ============================================================

def _update_supabase_upload(video_id, results):
    """Ghi kết quả Trend Alignment Score vào bảng videos trên Supabase."""
    import psycopg2
    import json

    db_url = os.environ["DATABASE_URL"]
    conn = psycopg2.connect(db_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE videos SET
                    category = %s,
                    video_description = %s,
                    top_keywords = %s,
                    video_sentiment = %s,
                    positive_score = %s,
                    video_duration = %s,
                    video_orientation = %s,
                    scene_cut_count = %s,
                    trend_alignment_score = %s,
                    trend_insights = %s,
                    audio_transcript = %s,
                    ai_status = %s
                WHERE video_id = %s
                """,
                (
                    [results.get("category")] if results.get("category") not in ["🌍 Khác", "Lỗi"] else [],
                    results.get("video_description", ""),
                    results.get("top_keywords", ""),
                    results.get("video_sentiment", "🟡 TRUNG LẬP"),
                    results.get("positive_score", 0),
                    results.get("video_duration"),
                    results.get("video_orientation"),
                    results.get("scene_cut_count"),
                    results.get("trend_alignment_score"),
                    json.dumps(results.get("trend_insights", {}), ensure_ascii=False) if results.get("trend_insights") else None,
                    results.get("audio_transcript", ""),
                    results.get("ai_status", "completed"),
                    video_id,
                ),
            )
        conn.commit()
        print(f"    [✓] Đã cập nhật Supabase (upload): {video_id}")
    except Exception as e:
        print(f"    [!] Supabase upload error: {e}")
        conn.rollback()
    finally:
        conn.close()


@app.function(
    image=gpu_image,
    gpu="T4",
    secrets=[modal.Secret.from_name("trendsense-secrets")],
    volumes={MODEL_DIR: model_volume},
    timeout=600,
    max_containers=3,  # Giới hạn 3 container tải video/chạy AI cùng lúc để tránh rate limit của Groq
)
def process_video(video_data: dict):
    """
    Pipeline xử lý hoàn chỉnh cho 1 video TikTok (chạy trên GPU T4):
    Download → Whisper → BLIP → EasyOCR → Groq AI → Metrics → Supabase
    """
    video_id = video_data.get("video_id", "unknown")
    url = video_data.get("url", "")
    caption = video_data.get("caption", "")

    print(f"\n{'=' * 60}")
    print(f"🎬 MODAL AI WORKER — Processing: {video_id}")
    print(f"{'=' * 60}")

    # ── BƯỚC 1: Lấy video (Upload base64 hoặc Download từ URL) ──
    video_base64 = video_data.get("video_base64", "")
    video_filename = video_data.get("video_filename", "upload.mp4")

    if video_base64:
        print("  [1/5] 📂 Decoding uploaded video...")
        _update_status(video_id, "downloading")
        video_path = _save_uploaded_video(video_base64, video_id, video_filename)
    else:
        print("  [1/5] 📥 Downloading video from URL...")
        _update_status(video_id, "downloading")
        video_path = _download_video(url, video_id)

    if not video_path:
        _update_supabase(video_id, {
            "video_description": "Không thể xử lý video (tải/giải mã thất bại).",
            "category": "🌍 Khác",
            "video_sentiment": "🟡 TRUNG LẬP",
            "positive_score": 50.0,
            "top_keywords": "",
            "views_per_hour": 0, "engagement_rate": 0,
            "viral_velocity": 0, "viral_probability": 0,
            "ai_status": "error",
        })
        print(f"  ❌ Failed: {video_id} (video acquisition error)")
        return {"status": "error", "video_id": video_id, "reason": "video_acquisition_failed"}

    try:
        # ── BƯỚC 2: Trích xuất frames ──
        print("  [2/5] 🖼️ Extracting frames...")
        _update_status(video_id, "analyzing")
        pil_frames, cv2_frames = _extract_frames(video_path, total_frames=4, ocr_frames=1)

        # ── BƯỚC 3: Chạy 3 AI models đa phương thức ──
        print("  [3/5] 🎧 Running Whisper (Audio → Text)...")
        audio_text = _run_whisper(video_path)
        print(f"         Audio: {audio_text[:80]}...")

        print("        👁️ Running BLIP (Vision → Caption)...")
        blip_text = _run_blip(pil_frames)
        print(f"         Vision: {blip_text[:80]}...")

        print("        📝 Running EasyOCR (Screen → Text)...")
        ocr_text = _run_ocr(cv2_frames)
        print(f"         OCR: {ocr_text[:80]}...")

        # ── BƯỚC 4: Groq tổng hợp tất cả (1 lệnh thay 3 model) ──
        print("  [4/5] 🧠 Calling Groq AI (Summarize + Categorize + Sentiment)...")
        _update_status(video_id, "summarizing")
        groq_result = _call_groq(
            audio_text, ocr_text, blip_text, caption,
            video_data.get("top_comments", []),
        )

        # PHÂN TÍCH LẠI: Nếu AI trả về "🌍 Khác" (không khớp danh mục), thử gọi lại lần 2
        if groq_result.get("category") == "🌍 Khác" and groq_result.get("ai_status", "completed") != "error":
            print("    ⚠️ AI trả về danh mục '🌍 Khác'. Đang tiến hành phân tích lại lần nữa...")
            # Thêm một chút thay đổi vào prompt để ép AI phải chọn
            groq_result = _call_groq(
                audio_text, ocr_text, blip_text, caption + " (Vui lòng PHÂN TÍCH KỸ và CHỌN 1 TRONG CÁC DANH MỤC ĐÃ CHO, KHÔNG ĐƯỢC BỎ QUA)",
                video_data.get("top_comments", []),
            )
            
            # Nếu phân tích lại vẫn là "🌍 Khác" -> Đánh dấu là lỗi luôn
            if groq_result.get("category") == "🌍 Khác":
                print("    [!] Vẫn không thể phân loại. Đánh dấu video này là LỖI.")
                groq_result["ai_status"] = "error"
                groq_result["category"] = "Lỗi"

        # ── BƯỚC 5: Phân nhánh theo loại video ──
        is_upload = bool(video_data.get("video_base64", ""))

        if is_upload:
            print("  [5/6] 📐 Extracting video metadata...")
            metadata = _extract_video_metadata(video_path)
            
            print("  [6/6] 🎯 Computing Trend Alignment Score...")
            benchmarks = _get_cached_benchmarks()
            score_result = _score_trend_alignment(groq_result, metadata, audio_text, benchmarks)
            
            # Groq sinh nhận xét
            insights = _generate_trend_insights(score_result, groq_result.get("summary", ""), metadata)
            
            final = {
                "video_description": groq_result.get("summary", ""),
                "category": groq_result.get("category", "🌍 Khác"),
                "video_sentiment": groq_result.get("sentiment", "🟡 TRUNG LẬP"),
                "positive_score": groq_result.get("positive_score", 50.0),
                "top_keywords": ", ".join(groq_result.get("keywords", [])[:5]),
                "video_duration": metadata.get("duration", 0),
                "video_orientation": metadata.get("orientation", "unknown"),
                "scene_cut_count": metadata.get("scene_cut_count", 0),
                "trend_alignment_score": score_result.get("trend_alignment_score", 0),
                "trend_insights": {**score_result, **insights},
                "audio_transcript": audio_text,
                "ai_status": groq_result.get("ai_status", "completed"),
            }

            _update_supabase_upload(video_id, final)

            # Persist model cache vào Volume (cho lần cold start tiếp theo)
            try:
                model_volume.commit()
            except Exception:
                pass  # Bỏ qua nếu API thay đổi

            print(f"\n  ✅ HOÀN THÀNH: {video_id}")
            print(f"     🏷️ {final['category']} | Trend Alignment Score: {final['trend_alignment_score']}")

            return {"status": "completed", "video_id": video_id}
            
        else:
            print("  [5/5] 📊 Computing metrics & writing to Supabase...")
            metrics = _calculate_metrics(video_data)

            final = {
                "video_description": groq_result.get("summary", ""),
                "category": groq_result.get("category", "🌍 Khác"),
                "video_sentiment": groq_result.get("sentiment", "🟡 TRUNG LẬP"),
                "positive_score": groq_result.get("positive_score", 50.0),
                "top_keywords": ", ".join(groq_result.get("keywords", [])[:5]),
                "views_per_hour": metrics["vph"],
                "engagement_rate": metrics["er"],
                "viral_velocity": metrics["velocity"],
                "viral_probability": 0.0,  # Sẽ được tính bởi weekly_train workflow
                "ai_status": groq_result.get("ai_status", "completed"),
            }

            _update_supabase(video_id, final)

            # Persist model cache vào Volume (cho lần cold start tiếp theo)
            try:
                model_volume.commit()
            except Exception:
                pass  # Bỏ qua nếu API thay đổi

            print(f"\n  ✅ HOÀN THÀNH: {video_id}")
            print(f"     🏷️ {final['category']} | {final['video_description'][:60]}...")
            print(f"     📊 VPH={metrics['vph']} | ER={metrics['er']}% | Velocity={metrics['velocity']}")

            return {"status": "completed", "video_id": video_id}

    finally:
        # Dọn dẹp video khỏi /tmp (Analyze & Destroy)
        if video_path and os.path.exists(video_path):
            try:
                os.remove(video_path)
                print(f"    🗑️ Cleaned up: {os.path.basename(video_path)}")
            except Exception:
                pass


# ============================================================
# WEBHOOK ENDPOINT (Lightweight, KHÔNG cần GPU)
# ============================================================
@app.function(image=webhook_image)
@modal.fastapi_endpoint(method="POST")
def analyze(video_data: dict):
    """
    POST /analyze — Nhận video data từ GitHub Actions Scraper.
    Spawn xử lý GPU bất đồng bộ, trả kết quả ngay lập tức.

    Body JSON:
    {
        "video_id": "7384...",
        "url": "https://www.tiktok.com/@user/video/7384...",
        "caption": "...",
        "views": 123456,
        "likes": 5000,
        "comments": 200,
        "shares": 100,
        "saves": 300,
        "create_time": 1713100000,
        "top_comments": [{"text": "...", "likes": 50}, ...]
    }
    """
    video_id = video_data.get("video_id", "unknown")
    print(f"📨 Received: {video_id} → Spawning GPU worker...")

    # Fire-and-forget: spawn xử lý nặng trên container GPU khác
    process_video.spawn(video_data)

    return {
        "status": "queued",
        "video_id": video_id,
        "message": f"Video {video_id} đã được đưa vào hàng đợi GPU.",
    }
