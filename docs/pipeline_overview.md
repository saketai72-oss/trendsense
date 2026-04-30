# 🎯 Tổng Quan Pipeline Dự Án TrendSense

> **Cập nhật:** 2026-04-30 | **Phiên bản API:** v2.1.0

TrendSense là hệ thống phân tích xu hướng và dự báo khả năng bùng nổ (viral probability) cho video TikTok. Hệ thống vận hành theo kiến trúc **Hybrid Cloud** — kết hợp FastAPI Backend, **Redis Queue (RQ)** xử lý bất đồng bộ, Gemini API/OpenRouter làm LLM chính, và Modal Serverless GPU làm xử lý đa phương thức (fallback/upload).

---

## Kiến Trúc Tổng Quan

```text
┌───────────────────────────────────────────────────────────────────────┐
│                          DATA SOURCES                                 │
│   [TikTok Scraper - Github Actions]       [User Upload - Browser]     │
│       (Rotating Proxy Pool)                          │                │
└───────────────────┬──────────────────────────────────┼────────────────┘
                    │                                  │ 1. Lấy Upload URL
                    ▼                                  ▼
┌───────────────────────────────────────────────────────────────────────┐
│                  FastAPI Backend  (port 8080)                         │
│                  (Rate Limited via SlowAPI + Redis)                   │
│                                                                       │
│   POST /api/analyze-gemini                GET /api/upload-url         │
│   (Scraper Webhook)                       POST /api/analyze           │
└───────────┬──────────────────────────────────┬────────────────────────┘
            │                                  │ 2. Upload video
            ▼                                  ▼
┌───────────────────┐               ┌────────────────────────┐
│   Upstash Redis   │               │   Supabase Storage     │
│   (Task Queue)    │               │   (S3-compatible)      │
└────────┬──────────┘               └──────────┬─────────────┘
         │                                     │
         ▼                                     │ 3. Download
┌───────────────────┐               ┌──────────▼─────────────┐
│  Redis RQ Worker  │               │  Modal Serverless GPU  │
│  (backend/worker) │  ──fail──▶   │  (T4/L4 GPU)           │
│  gemini_engine.py │               │  modal_app.py          │
└────────┬──────────┘               └──────────┬─────────────┘
         │                                     │
         └─────────────┬───────────────────────┘
                       │
                       ▼
          ┌────────────────────────┐
          │   Supabase PostgreSQL  │
          │   (pgvector 768-dim)   │
          └────────────┬───────────┘
                       │
                       ▼
          ┌────────────────────────┐
          │   Next.js Frontend     │
          │   (port 3000)          │
          └────────────────────────┘
```

---

## 1. 📥 Thu Thập Dữ Liệu (Data Ingestion)

Dữ liệu đầu vào đến từ 2 nguồn chính:

### A. TikTok Scraper — Thu thập tự động
- **File:** `services/tiktok_scraper/scraper_main.py`
- **Kích hoạt:** GitHub Actions workflow `.github/workflows/ai_pipeline.yml` — **mỗi 4 giờ** (`cron: '0 */4 * * *'`)
- **Trình duyệt & Chống Block:** Selenium + Undetected Chromedriver + **Xoay vòng Proxy (Residential Proxy Pool)** để chống bị TikTok chặn.
- **Luồng crawl:**
  1. Chọn ngẫu nhiên 1 hashtag từ pool Việt Nam: `#xuhuong`, `#giaitri`, `#vietnam`, `#tintuc`...
  2. `link_crawler.py` thu thập pool link dự phòng (gấp 3x `MAX_VIDEOS = 30`)
  3. Nếu phát hiện bị chặn captcha/access denied → tự động đổi Proxy khác.
  4. `content_parser.py` bóc tách stats: Views, Likes, Comments, Shares, Saves, Create_Time, Caption, Top 5 Comments
  5. **Bộ lọc ngôn ngữ:** `langdetect` — chỉ giữ video tiếng Việt (`lang == 'vi'`)
  6. **Bộ lọc dữ liệu rác:** Bỏ video có `views <= 0`, hoặc `likes > views`
- **Lưu DB:** `insert_video_metadata()` → bảng `videos` với `ai_status = 'pending'`
- **Kích hoạt AI:** Gọi `_trigger_ai_pipeline()` → `POST /api/analyze-gemini` (FastAPI). Webhook này sẽ đẩy Job vào Redis Queue.

### B. User Uploads — Tải lên chủ động
- **Endpoint:** `GET /api/upload-url` và `POST /api/analyze` (`backend/api/routes.py`)
- **Giới hạn:** 100 MB, định dạng MP4/MOV/AVI/WebM/MKV
- **Storage:** Tải trực tiếp lên **Supabase Storage** bằng luồng Presigned URL.
- **Luồng xử lý:**
  1. Client gọi `GET /api/upload-url` → nhận Presigned URL và `video_id`.
  2. Client `PUT` file video thẳng lên Supabase Storage URL (giảm tải cho Backend).
  3. Client gọi `POST /api/analyze` kèm `video_id` và `storage_path`.
  4. FastAPI nhận tín hiệu → Gửi webhook (chứa `storage_url`) sang `MODAL_WEBHOOK_URL`.
- **Phân tích:** Modal GPU Worker nhận URL, tải xuống trực tiếp từ Supabase Storage, giải mã, chạy full pipeline → trả về **Trend Alignment Score**.

---

## 2. 🧠 Động Cơ AI (AI Processing Engine)

Hai luồng xử lý song song, ưu tiên theo thứ tự:

### A. Pipeline Gemini 2.5 Flash — Primary (Scraper Videos)
- **File:** `backend/api/gemini_engine.py` và `backend/worker.py`
- **Kích hoạt:** Webhook `POST /api/analyze-gemini` → Đẩy Job vào **Redis Queue (RQ)**.
- **Luồng xử lý 9 bước (chạy ngầm trong Worker):**
  1. `insert_video_metadata()` — đảm bảo record tồn tại trong DB.
  2. **Download video:** `yt-dlp` qua `services/tiktok_scraper/video_downloader.py`. Nếu bị chặn IP → kích hoạt `_trigger_modal_fallback()`.
  3. **Upload lên Gemini File API:** `client.files.upload(file=local_path)`.
  4. **Xóa file local** để giải phóng ổ cứng.
  5. **Polling trạng thái:** Chờ `state == ACTIVE`.
  6. **Inference:** Sinh JSON với model `gemini-2.5-flash`. Trả về tóm tắt, danh mục, sentiment, keywords.
  7. **Sinh Semantic Embeddings:** Gọi Gemini `text-embedding-004` API sinh vector 768 chiều.
  8. **Validate + Tính metrics + Lưu DB:** Lưu các chỉ số tương tác và vector vào Supabase (`update_ai_results()`).
  9. **Dọn dẹp:** Xóa file trên Gemini File API.
- **Fallback tự động (Retry/Modal):** Worker tự retry nếu gặp Rate Limit (429/503). Nếu thất bại hoàn toàn → đẩy sang Modal GPU Fallback.

### B. Pipeline Modal Serverless GPU — Fallback & Upload
- **File:** `services/ai_engine/modal_app.py`
- **Hạ tầng:** Modal App `trendsense-ai`, GPU T4 hoặc L4.
- **LLM AI:** Sử dụng **OpenRouter** (`meta-llama/llama-3.3-70b-instruct:free`) làm primary, fallback sang **Groq** (`llama-3.3-70b-versatile`).
- **Webhook:** `@modal.fastapi_endpoint(method="POST")` — nhận request → spawn xử lý (fire-and-forget).

**Luồng xử lý Modal (GPU Worker):**

| Bước | Mô tả | Model/Tool |
|------|-------|-----------|
| 1 | Tải video (Supabase Signed URL hoặc TikTok URL) | `requests` / `yt-dlp` |
| 2 | Trích xuất frames (4 frames BLIP, 1 frame OCR) | `OpenCV` |
| 3a | Audio → Text | `Faster-Whisper base` (CUDA float16) |
| 3b | Vision → Caption | `BLIP` (CUDA) |
| 3c | Screen Text | `EasyOCR` (vi+en, GPU) |
| 4 | Tổng hợp tất cả → JSON | `OpenRouter Llama-3.3-70B` (fallback Groq) |
| 5a | **Scraper video:** Tính metrics → Lưu Supabase | `_calculate_metrics()` |
| 5b | **Upload video:** Trích xuất metadata + Trend Alignment | `_extract_video_metadata()` + `_score_trend_alignment()` |

**Phân nhánh theo loại video trong Modal:**
- Nếu có `storage_url` → **Upload path** → Trả về Trend Alignment Score.
- Nếu chỉ có `url` → **Scraper path** → Trả về Engagement metrics.

---

## 3. 📐 Trend Alignment Score (Chỉ cho Video Upload)

Khi người dùng upload video, thay vì Viral Probability, hệ thống tính **Trend Alignment Score (0–100)** bằng Python thuần (không phụ thuộc AI để tính điểm):

### Các trục chấm điểm (Dynamic Weights):

| Trục | Trọng số (có audio) | Trọng số (không có audio) | Nguồn dữ liệu |
|------|---------------------|--------------------------|---------------|
| Category | 30% | ~37% | So với trending categories 14 ngày |
| Content/Keyword | 25% | ~31% | So với trending keywords 14 ngày |
| Audio | 20% | ❌ Bỏ qua | So sánh transcript với viral videos |
| Duration | 15% | ~19% | So với median duration theo category |
| Format | 10% | ~13% | Orientation (portrait/landscape) + Scene cuts |

**Benchmark data:** Lấy từ Supabase, cache per-container 2 giờ (`_CACHE_TTL = 7200`):
- `trending_categories` — Top categories theo avg viral_velocity 14 ngày
- `trending_keywords` — Keywords từ video có velocity > median
- `duration_stats` — MEDIAN duration viral theo category (tối thiểu 3 mẫu)
- `viral_transcripts` — Top 30 transcripts của video viral nhất

**Groq sinh nhận xét:** Sau khi có điểm, `_generate_trend_insights()` gọi Groq Llama-3.3-70B để viết `overall_comment`, `top_strength`, `top_improvement` bằng tiếng Việt.

**Kết quả lưu vào DB:** `video_duration`, `video_orientation`, `scene_cut_count`, `trend_alignment_score`, `trend_insights` (JSONB), `audio_transcript`

---

## 4. 📈 Động Cơ Dự Báo Viral (Prediction Engine)

Chỉ áp dụng cho **video TikTok được scrape** (có stats thực).

- **File:** `services/ai_engine/prediction_engine.py`
- **Model:** Random Forest (`data/models/rf_model.joblib`) — Inference Only
- **Features đầu vào:** `Like_Rate`, `Comment_Rate`, `Share_Rate`, `Save_Rate`, `Positive_Score`, `Views_Per_Hour`
- **Giới hạn:** Chỉ predict video < 14 ngày tuổi; video cũ hơn tự động gán 0%
- **Output:** `viral_probability` (0–100%)
- **Retrain:** GitHub Actions `weekly_train.yml` — mỗi Chủ Nhật 00:00 ICT, push model mới lên repo

### Công thức Metrics (`math_utils.py`):
```python
age_hours      = max((now - create_time) / 3600, 0.1)
views_per_hour = views / age_hours
engagement_pts = likes + (comments × 2) + (saves × 3) + (shares × 4)
engagement_rate= (engagement_pts / views) × 100
viral_velocity = (views_per_hour × engagement_rate) / log10(age_hours + 10)
```

### Gợi ý tối ưu (OpenRouter AI):
- **File:** `_generate_recommendations()` trong `backend/api/routes.py`
- **Model:** OpenRouter `meta-llama/llama-3.3-70b-instruct:free` (gọi qua `llm_client.py`)
- **4 đề xuất:** `hook` (3 giây đầu), `audio` (nhạc trending), `caption_hashtags` (SEO TikTok), `pacing_cta` (nhịp cắt + Call-to-Action)
- **Fallback:** Static rule-based recommendations nếu API không khả dụng

---

## 5. 🗄️ Cơ Sở Dữ Liệu (Database Layer)

- **Công nghệ:** Supabase (PostgreSQL) + `psycopg2` — quản lý tại `core/db/`
- **Kết nối:** `core/db/session.py` → `get_connection()` từ `DATABASE_URL`

### Bảng `videos` — Schema chính:

| Nhóm cột | Các cột |
|----------|---------|
| **Metadata cơ bản** | `video_id (PK)`, `link`, `caption`, `scrape_date`, `create_time` |
| **Engagement stats** | `views`, `likes`, `comments`, `shares`, `saves` |
| **Top comments** | `top1_cmt..top5_cmt`, `top1_likes..top5_likes` |
| **Metrics tính toán** | `views_per_hour`, `engagement_rate`, `viral_velocity`, `viral_probability` |
| **AI Analysis** | `video_description`, `category (TEXT[])`, `video_sentiment`, `positive_score`, `top_keywords`, `audio_transcript`, `embedding (vector 768)` |
| **Upload Analysis** | `video_duration`, `video_orientation`, `scene_cut_count`, `trend_alignment_score`, `trend_insights (JSONB)` |
| **Trạng thái** | `ai_status` (`pending`/`downloading`/`analyzing`/`summarizing`/`completed`/`error`/`user_pending`), `is_rescraped` |

### Bảng `history` — Dedup Scraper:
- Lưu `video_id` đã cào để tránh cào lại. `mark_as_scraped()` / `is_scraped()`

### Indexes:
- `idx_ai_status`, `idx_scrape_date`, `idx_category`, `idx_is_rescraped`

### Các hàm DB quan trọng (`core/db/models.py`):

| Hàm | Mục đích |
|-----|---------|
| `insert_video_metadata()` | Insert/Upsert metadata từ scraper |
| `update_ai_results()` | Cập nhật kết quả Gemini/Modal cho scraper video |
| `update_upload_analysis()` | Cập nhật Trend Alignment Score cho upload video |
| `get_all_analyzed_videos()` | Phân trang + lọc + sort cho Dashboard |
| `get_dashboard_stats()` | Tổng hợp stats cho Overview panel |
| `get_category_stats()` | Thống kê theo danh mục (unnest array) |
| `get_trending_categories()` | Benchmark: Top categories 14 ngày |
| `get_trending_keywords()` | Benchmark: Keywords từ video velocity > median |
| `get_duration_stats_by_category()` | Benchmark: Median duration theo category |
| `get_viral_audio_transcripts()` | Benchmark: Top 30 transcripts viral |

---

## 6. 🖥️ Frontend Dashboard (Next.js)

- **Vị trí:** `frontend/` — Next.js App Router
- **Chạy:** Port 3000, proxy sang Backend port 8080

### Các trang chính:

| Route | File | Nội dung |
|-------|------|---------|
| `/` | `app/page.js` | Dashboard chính — Stats tổng quan, Category chart, Sentiment pie, Timeline, Top Keywords, Video list có filter/sort/search |
| `/dashboard` | `app/dashboard/` | Dashboard mở rộng |
| `/analyze` | `app/analyze/` | Giao diện upload video + hiển thị Trend Alignment Score |
| `/video/[id]` | `app/video/` | Chi tiết từng video + Recommendations |

### Các API endpoints Frontend sử dụng:

| Endpoint | Mục đích |
|----------|---------|
| `GET /api/stats` | Tổng quan: total videos, views, likes, viral count... |
| `GET /api/videos` | Danh sách video có phân trang, filter category/sentiment, sort, search |
| `GET /api/videos/{id}` | Chi tiết 1 video |
| `GET /api/categories` | Stats theo danh mục (count, avg_velocity, avg_viral) |
| `GET /api/sentiments` | Phân bổ cảm xúc |
| `GET /api/keywords?limit=30` | Top keywords |
| `GET /api/timeline` | Dữ liệu timeline 30 ngày |
| `POST /api/analyze` | Upload video để phân tích |
| `GET /api/analyze/{video_id}` | Poll trạng thái phân tích + lấy kết quả |

---

## 7. ⚙️ GitHub Actions Workflows

### `ai_pipeline.yml` — Mỗi 4 giờ
```
Cron: 0 */4 * * *
Chạy: services.tiktok_scraper.scraper_main
Secrets: DATABASE_URL, MODAL_WEBHOOK_URL
Mục đích: Cào TikTok trending → Insert DB → Trigger AI pipeline
```

### `weekly_train.yml` — Chủ Nhật 00:00 ICT
```
Cron: 0 17 * * 0 (UTC)
Bước 1: Cào stats mới nhất
Bước 2: python -m services.ai_engine.train_model
Bước 3: git push data/models/rf_model.joblib + metrics.json lên main
Mục đích: Retrain Random Forest model hàng tuần
```

### `weekly_cleanup.yml`
```
Mục đích: Dọn dẹp dữ liệu/video cũ hơn VIDEO_RETENTION_DAYS (14 ngày)
```

---

## 8. 🔑 Cấu Hình & Biến Môi Trường

| Biến | Nơi dùng | Mô tả |
|------|----------|-------|
| `DATABASE_URL` | Toàn bộ backend | PostgreSQL connection string (Supabase) |
| `REDIS_URL` | `backend/main.py`, `worker.py` | Upstash Redis cho Rate Limit và Task Queue |
| `SUPABASE_URL` | `storage_service.py` | URL Supabase cho Presigned Upload |
| `SUPABASE_SERVICE_KEY` | `storage_service.py` | Service key để bypass RLS (chỉ dùng backend) |
| `OPENROUTER_API_KEY` | `llm_client.py` | API Key chính cho text generation (LLaMA 3.3) |
| `GEMINI_API_KEY` | `gemini_engine.py` | API key tạo Semantic Embeddings và phân tích đa phương thức |
| `GROQ_API_KEY` | `llm_client.py` | Fallback text generation API |
| `MODAL_WEBHOOK_URL` | `scraper_main.py`, `routes.py` | URL webhook Modal endpoint |
| `PROXY_LIST` | `browser.py` | Danh sách Proxy dạng JSON Array để scraper xoay vòng |

### 11 Danh Mục Chuẩn (STANDARD_CATEGORIES):
```
🎭 Giải trí | 🎵 Âm nhạc | 🍳 Ẩm thực | 💻 Công nghệ | 👗 Thời trang
📚 Giáo dục | 🏋️ Thể thao | 🐾 Động vật | 💄 Làm đẹp | 📰 Tin tức | 💰 Tài chính
```

---

## 🔄 Data Flow — Tóm Tắt Đầy Đủ

### Luồng Scraper (TikTok → Dashboard):
```text
GitHub Actions (mỗi 4h)
  → scraper_main.py (Selenium + Proxy Rotation)
  → insert_video_metadata() → Supabase (ai_status=pending)
  → POST /api/analyze-gemini
      → Redis Queue (RQ) nhận Job
      → Redis Worker (gemini_engine.py):
          → yt-dlp download video
          → Gemini 2.5 Flash: Vision + Audio analysis → JSON
          → Gemini Embeddings: Text-embedding-004 → pgvector
          → calculate_metrics() → update_ai_results()
          [Nếu fail liên tục] → Đẩy sang Modal GPU Fallback
  → Next.js Dashboard hiển thị
```

### Luồng Upload (User Video → Trend Alignment):
```text
User upload video (browser)
  → GET /api/upload-url → Nhận Presigned URL
  → PUT file trực tiếp lên Supabase Storage
  → POST /api/analyze (kèm storage_path)
      → Backend insert_user_video() (ai_status=user_pending)
      → Gửi webhook chứa storage_url sang MODAL_WEBHOOK_URL
          → Modal GPU Worker (T4/L4):
              → Download từ Supabase Storage URL
              → Whisper (audio transcript) + BLIP + EasyOCR
              → OpenRouter LLaMA 3.3 70B (tổng hợp JSON)
              → _score_trend_alignment() (Python deterministic)
              → _generate_trend_insights()
              → _update_supabase_upload() (ai_status=completed)
  → Frontend polls GET /api/analyze/{video_id}
  → Hiển thị Trend Alignment Score
```

### Luồng Weekly Retrain (Random Forest):
```
GitHub Actions (Chủ Nhật 00:00 ICT)
  → scraper_main.py (cào stats mới)
  → train_model.py (train Random Forest trên completed videos < 14 ngày)
  → git push rf_model.joblib + metrics.json → main branch
  → Backend load model mới ở request tiếp theo
```
