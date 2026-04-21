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
                    [results.get("category", "🎭 Giải trí")] if results.get("category") != "🌍 Khác" else [],
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
# MAIN GPU PROCESSING FUNCTION
# ============================================================
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

    # ── BƯỚC 1: Tải video từ TikTok vào /tmp ──
    print("  [1/5] 📥 Downloading video...")
    _update_status(video_id, "downloading")
    video_path = _download_video(url, video_id)

    if not video_path:
        _update_supabase(video_id, {
            "video_description": "Không tải được video từ TikTok.",
            "category": "🌍 Khác",
            "video_sentiment": "🟡 TRUNG LẬP",
            "positive_score": 50.0,
            "top_keywords": "",
            "views_per_hour": 0, "engagement_rate": 0,
            "viral_velocity": 0, "viral_probability": 0,
            "ai_status": "error",
        })
        print(f"  ❌ Failed: {video_id} (download error)")
        return {"status": "error", "video_id": video_id, "reason": "download_failed"}

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

        # ── BƯỚC 5: Tính metrics + Ghi Supabase ──
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
