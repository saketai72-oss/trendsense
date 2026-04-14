# Kế hoạch Kiến trúc TrendSense Cloud-Native (Selenium Version)

Dự án chuyển đổi từ chạy máy cục bộ sang hoàn toàn trên Cloud sử dụng GitHub Actions, Modal.com, Groq API và Supabase.

---

## 1. Thành phần hệ thống

### A. GitHub Actions (Scraper)
- **Tần suất**: Mỗi 4 tiếng.
- **Công nghệ**: Selenium (undetected-chromedriver) chạy Headless trên Ubuntu.
- **Nhiệm vụ**: Cào danh sách video Trending, bóc tách metadata cơ bản (views, likes, comments).
- **Output**: Gửi HTTP POST (JSON) chứa `video_id`, `url`, `caption` sang Modal API **ngay sau mỗi video** (nhỏ giọt, không gom lô).

### B. Modal Cloud (AI Core)
- **Công nghệ**: Modal.com (Serverless GPU).
- **Nhiệm vụ**:
    - Nhận POST request từ GitHub Actions.
    - Kích hoạt GPU T4 (Free Tier).
    - Tải video trực tiếp từ TikTok vào RAM ảo (/tmp).
    - Chạy **Faster-Whisper** (Chuyển âm thanh thành văn bản).
    - Chạy **BLIP** (Phân tích hình ảnh, sinh caption cho video).
    - Chạy **EasyOCR** (Đọc chữ trên màn hình).
- **LLM**: Gọi **Groq API** (Llama 3) để tổng hợp toàn bộ dữ liệu trên thành 1 câu tóm tắt và phân loại danh mục.

### C. Database (Supabase)
- **Nhiệm vụ**: Lưu trữ kết quả cuối cùng để Dashboard (Streamlit) hiển thị.
- **Lưu đồ**: Modal -> Supabase (Ghi đè hoặc cập nhật vào bảng `videos`).

---

## 2. Tối ưu hóa Modal — Giảm Cold Start

Modal có độ trễ khởi động (Cold Start) ~2-5 giây khi nạp Image vào GPU. Các chiến lược sau giúp giảm thiểu:

### A. Chia nhỏ Image (Layering)

Trong `modal_app.py`, **tách các lệnh `.pip_install()`** theo tầng nặng/nhẹ để Modal tận dụng cache tốt hơn. Khi chỉ sửa code ứng dụng, Modal sẽ tái sử dụng layer thư viện nặng đã build trước đó.

```python
# ❌ SAI: Gộp tất cả vào 1 lệnh — thay đổi bất kỳ thư viện nào sẽ rebuild toàn bộ (~3 phút)
image = modal.Image.debian_slim().pip_install(
    "torch", "transformers", "faster-whisper", "easyocr", "requests", "groq"
)

# ✅ ĐÚNG: Phân tầng — thay đổi thư viện nhẹ chỉ rebuild layer cuối (~10 giây)
image = (
    modal.Image.debian_slim(python_version="3.12")
    # Layer 1: Thư viện NẶNG (ít thay đổi, cache lâu dài)
    .pip_install(
        "torch==2.11.0",
        "transformers==5.4.0",
        "faster-whisper==1.2.1",
        "easyocr==1.7.2",
    )
    # Layer 2: Thư viện NHẸ (hay thay đổi, rebuild nhanh)
    .pip_install(
        "groq",
        "requests",
        "psycopg2-binary",
        "opencv-python-headless",
        "moviepy",
        "Pillow",
    )
)
```

### B. Tải Model vào Volume (Tùy chọn nâng cao)

Mặc định, mỗi lần Modal chạy cold start, Faster-Whisper và BLIP sẽ **tải lại model (~500MB+) từ Hugging Face** về RAM ảo. Dùng `modal.Volume` để lưu sẵn model trên đĩa cứng ảo của Modal:

```python
# Tạo Volume persistent để cache model
model_volume = modal.Volume.from_name("trendsense-models", create_if_missing=True)
MODEL_CACHE_DIR = "/models"

@app.cls(
    image=image,
    gpu="T4",
    volumes={MODEL_CACHE_DIR: model_volume},
    timeout=300,
)
class AIWorker:
    @modal.enter()  # Chạy 1 lần khi container khởi tạo
    def load_models(self):
        from faster_whisper import WhisperModel
        from transformers import BlipProcessor, BlipForConditionalGeneration
        
        # Whisper sẽ tải model vào /models/whisper/ (lần đầu)
        # Lần sau container mới khởi động sẽ đọc từ Volume thay vì tải lại
        self.whisper = WhisperModel(
            "base",
            device="cuda",
            compute_type="float16",
            download_root=f"{MODEL_CACHE_DIR}/whisper"
        )
        
        # BLIP cũng tương tự
        blip_path = f"{MODEL_CACHE_DIR}/blip"
        self.blip_processor = BlipProcessor.from_pretrained(
            "Salesforce/blip-image-captioning-base",
            cache_dir=blip_path
        )
        self.blip_model = BlipForConditionalGeneration.from_pretrained(
            "Salesforce/blip-image-captioning-base",
            cache_dir=blip_path
        ).to("cuda")
        
        model_volume.commit()  # Lưu model vào đĩa cứng ảo
```

**Lợi ích**: Cold start giảm từ ~30s (tải từ HF) xuống ~5s (đọc từ Volume).

---

## 3. Groq — Chống Rate Limit

Groq Llama-3 cực nhanh nhưng có giới hạn **30 requests/phút** (Free Tier). Chiến lược xử lý:

### A. Gửi Request Nhỏ Giọt (Drip-Feed)

Trong `scraper_main.py` (GitHub Actions), **gửi từng video** sang Modal API ngay sau khi cào xong, thay vì gom 20 video rồi POST cùng lúc:

```python
# Trong vòng lặp cào video:
for i, link in enumerate(links, 1):
    # ... cào metadata ...
    
    # Gửi NGAY video này sang Modal để xử lý
    response = requests.post(
        MODAL_API_URL,
        json={"video_id": vid, "url": link, "caption": caption},
        timeout=120
    )
    
    # Modal xử lý xong 1 video (Whisper + BLIP + Groq) mất ~15-30 giây
    # Tự nhiên tạo ra khoảng cách giữa các request gửi lên Groq
    # → Không bị Rate Limit!
```

### B. Retry với Exponential Backoff (Trong Modal)

Nếu Groq trả về lỗi `429 (Rate Limit)`, Modal sẽ tự động retry:

```python
import time
from groq import Groq

def call_groq_with_retry(prompt, max_retries=3):
    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.3,
            )
            return response.choices[0].message.content
        except Exception as e:
            if "rate_limit" in str(e).lower() and attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)  # 2s, 4s, 8s
                print(f"⏳ Groq Rate Limit, chờ {wait}s...")
                time.sleep(wait)
            else:
                raise
```

---

## 4. Các bước triển khai

1. **Cấu hình Modal API**: Tạo `src/ai_core/modal_app.py` với Image phân tầng và Volume cache.
2. **Tích hợp Groq**: Sửa `src/ai_core/multimodal_engine.py` — thay Ollama bằng Groq SDK + retry logic.
3. **Cập nhật Scraper**: Sửa `src/scraper/scraper_main.py` — POST nhỏ giọt từng video sang Modal.
4. **Thiết lập GitHub Actions**: Cập nhật `.github/workflows/ai_pipeline.yml` với đầy đủ secrets.
5. **Cấu hình Secrets**: Nạp toàn bộ biến môi trường (xem bảng bên dưới).
6. **Dọn dẹp Workspace**: Xóa các file test, script cũ và model local không còn sử dụng.

---

## 5. Bảng Biến Môi Trường & Secrets

### A. File `.env` (Local Development)

| Biến | Giá trị mẫu | Mô tả |
|------|-------------|-------|
| `DATABASE_URL` | `postgresql://user:pass@host:port/db` | Connection string Supabase |
| `GROQ_API_KEY` | `gsk_xxxxxxxxxxxx` | API key từ [console.groq.com](https://console.groq.com) |
| `MODAL_TOKEN_ID` | `ak-xxxxxxxx` | Token ID từ Modal (`modal token new`) |
| `MODAL_TOKEN_SECRET` | `as-xxxxxxxx` | Token Secret từ Modal (`modal token new`) |
| `HUGGINGFACE_TOKEN` | `hf_xxxxxxxxxxxx` | (Tùy chọn) Token HuggingFace nếu dùng model private |

### B. GitHub Actions Secrets (Settings → Secrets → Actions)

| Secret Name | Mô tả | Cách lấy |
|-------------|--------|----------|
| `DATABASE_URL` | Connection string Supabase (giống `.env`) | Supabase Dashboard → Settings → Database → URI |
| `GROQ_API_KEY` | API key Groq Cloud | [console.groq.com/keys](https://console.groq.com/keys) → Create API Key |
| `MODAL_TOKEN_ID` | Modal authentication ID | Chạy `modal token new` trên terminal → copy ID |
| `MODAL_TOKEN_SECRET` | Modal authentication secret | Chạy `modal token new` trên terminal → copy Secret |

### C. Modal Secrets (Trong `modal_app.py`)

Modal cần truy cập Groq và Supabase **từ bên trong container**. Cấu hình qua Modal Dashboard hoặc CLI:

```bash
# Tạo secret group trên Modal
modal secret create trendsense-secrets \
    GROQ_API_KEY=gsk_xxxxxxxxxxxx \
    DATABASE_URL=postgresql://user:pass@host:port/db
```

Sau đó mount trong code:
```python
@app.function(
    image=image,
    gpu="T4",
    secrets=[modal.Secret.from_name("trendsense-secrets")],
)
def analyze_video(video_data: dict):
    # os.environ["GROQ_API_KEY"] và os.environ["DATABASE_URL"]
    # tự động có sẵn bên trong container
    ...
```

---

## 6. Lợi ích
- **0đ Chi phí**: Tận dụng triệt để Free Tier của Modal, GitHub, Groq và Supabase.
- **Tự động 100%**: Không cần treo máy tính cá nhân.
- **Tốc độ**: Groq và GPU T4 xử lý nhanh gấp nhiều lần so với CPU máy local.
- **Cold Start tối ưu**: Image layering + Volume cache giảm thời gian khởi động container.
- **Không bị Rate Limit**: Drip-feed strategy + exponential backoff bảo vệ quota Groq.
