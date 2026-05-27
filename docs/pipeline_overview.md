# 🎯 Tổng Quan Pipeline Dự Án TrendSense

> **Cập nhật:** 2026-05-09 | **Phiên bản API:** v3.0.0

TrendSense là hệ thống phân tích xu hướng và dự báo khả năng bùng nổ (viral probability) cho video TikTok. Hệ thống vận hành theo kiến trúc **Hybrid Cloud** — kết hợp FastAPI Backend, **Redis Queue (RQ)** xử lý bất đồng bộ, Gemini API/OpenRouter làm LLM chính, Modal Serverless GPU làm xử lý đa phương thức, và Next.js Frontend với Supabase Realtime.

---

## Kiến Trúc Tổng Quan

```text
┌───────────────────────────────────────────────────────────────────────┐
│                          DATA SOURCES                                 │
│   [TikTok Scraper - Local Scheduler]       [User Upload - Browser]     │
│   (Undetected Chromedriver + Proxy)                    │              │
│   [CAPTCHA Solver: captchaapi.hacodev.io.vn]           │              │
└───────────────────┬──────────────────────────────────┼────────────────┘
                    │                                  │ 1. Lấy Upload URL
                    ▼                                  ▼
┌───────────────────────────────────────────────────────────────────────┐
│                  FastAPI Backend  (port 8080)                         │
│                  (Rate Limited via SlowAPI + Redis)                   │
│                                                                       │
│   POST /api/analyze-gemini                GET /api/upload-url         │
│   (Scraper Webhook, 60/min/IP)           POST /api/analyze (5/hr/IP) │
│   POST /api/analyze-gemini → RQ Queue    → storage_service.py         │
│                                           → Supabase Presigned URL    │
└───────────┬──────────────────────────────────┬────────────────────────┘
            │                                  │ 2. Upload video
            ▼                                  ▼
┌───────────────────┐               ┌────────────────────────┐
│   Upstash Redis   │               │   Supabase Storage     │
│   (Task Queue:    │               │   (S3-compatible)      │
│    gemini_jobs)   │               └──────────┬─────────────┘
└────────┬──────────┘                          │
         │                                     │ 3. Download (Signed URL)
         ▼                                     ▼
┌───────────────────┐               ┌────────────────────────┐
│  Redis RQ Worker  │               │  Modal Serverless GPU  │
│  (backend/worker) │  ──fail──▶   │  (T4/L4 GPU)           │
│  gemini_engine.py │ (Fallback)   │  modal_app.py          │
│  embedding_svc.py │ OpenRouter   │  Whisper + BLIP + OCR  │
└────────┬──────────┘               └──────────┬─────────────┘
         │                                     │
         └─────────────┬───────────────────────┘
                       │
                       ▼
          ┌────────────────────────┐
          │   Supabase PostgreSQL  │
          │   (pgvector 3072-dim)  │
          │   embedding_service.py │
          └────────────┬───────────┘
                       │
                       ▼
          ┌────────────────────────┐
          │   Next.js Frontend     │
          │   (port 3000)          │
          │   + Supabase Realtime  │
          └────────────────────────┘
```

---

## 1. 📥 Thu Thập Dữ Liệu (Data Ingestion)

Dữ liệu đầu vào đến từ 2 nguồn chính:

### A. TikTok Scraper — Thu thập tự động
- **Entry point:** `services/tiktok_scraper/scraper_main.py` → `main()`
- **Trình duyệt & Chống Block:** `browser.py` — Undetected Chromedriver (headless, 1920×1080, GPU disabled, custom user-agent) + **Xoay vòng Proxy** (`PROXY_LIST` env var, JSON array hoặc comma-separated).
- **Giải CAPTCHA:** `captcha.py` — Giải TikTok rotate CAPTCHA bằng cách gửi ảnh đến `captchaapi.hacodev.io.vn/tiktok/rotate`, sau đó mô phỏng kéo slider với easing curve + overshoot correction.
- **Luồng crawl:**
  1. Chọn ngẫu nhiên 1 hashtag từ pool Việt Nam: `#xuhuong`, `#giaitri`, `#vietnam`, `#tintuc`...
  2. `link_crawler.py` — Thu thập pool link dự phòng (gấp 3x `MAX_VIDEOS = 30`), bỏ qua video đã scrape (`is_scraped()`).
  3. Nếu phát hiện bị chặn (`is_blocked()` kiểm tra captcha/access denied/robot) → tự động đổi Proxy khác.
  4. `content_parser.py` — Bóc tách stats từ HTML: ưu tiên parse JSON embedded (`__UNIVERSAL_DATA_FOR_REHYDRATION__` hoặc `SIGI_STATE`), fallback regex. Trích xuất: Views, Likes, Comments, Shares, Saves, Create_Time, Caption.
  5. **Bộ lọc dữ liệu rác:** Bỏ video có `views <= 0`, hoặc `likes > views`, hoặc `comments > views`.
  6. **Bộ lọc ngôn ngữ:** Đối với video lấy từ Selenium (cần parse HTML), áp dụng kết hợp kiểm tra ký tự có dấu tiếng Việt và `langdetect` — ưu tiên giữ video có dấu, fallback `langdetect` cho caption không dấu. Đối với video lấy từ TikTokApi (đã được lọc theo hashtag Việt), **bỏ qua kiểm tra ngôn ngữ** vì đã tin tưởng vào nguồn dữ liệu.
- **Lưu DB:** `insert_video_metadata()` → bảng `videos` với `ai_status = 'pending'`, đồng thời `mark_as_scraped()` vào bảng `history`.
- **Kích hoạt AI:** `_trigger_ai_pipeline()`:
  - **Primary:** `POST` đến `GEMINI_WEBHOOK_URL` (mặc định `http://localhost:8000/api/analyze-gemini`). Nếu nhận 202 → OK.
  - **Fallback:** Nếu backend trả 429/5xx hoặc không reachable → `_fallback_llm_analysis()` phân tích trực tiếp bằng OpenRouter (10 free models) / Groq (text-only, không cần video gốc). **Modal KHÔNG được sử dụng cho scraper** — chỉ dành cho user upload.

### B. User Uploads — Tải lên chủ động
- **Endpoint:** `GET /api/upload-url` và `POST /api/analyze` (`backend/api/routes.py`)
- **Giới hạn:** 100 MB, định dạng MP4/MOV/AVI/WebM/MKV
- **Quota hàng ngày:** Free (2 video/ngày), Pro 49k (10 video/ngày). Nâng cấp qua trang `/upgrade` với tích hợp SePay webhook.
- **Storage:** `storage_service.py` — Supabase SDK tạo Presigned PUT URL. Path format: `uploads/{video_id}/{sanitized_filename}`.
- **Luồng xử lý:**
  1. Client gọi `GET /api/upload-url` (`{filename, content_type}`) → Kiểm tra quota `check_video_quota(user_id)` → nhận `{video_id, upload_url, storage_path}`. Backend pre-insert video vào DB (`insert_user_video()`, `ai_status='user_pending'`).
  2. Client `PUT` file video thẳng lên Supabase Storage URL (giảm tải cho Backend).
  3. Client gọi `POST /api/analyze` kèm `video_id`, `storage_path`, `caption` (tùy chọn). Rate limit: **5 requests/giờ/IP**.
  4. Backend tạo Signed Download URL từ Supabase → gửi webhook (chứa `storage_url`) sang `MODAL_WEBHOOK_URL`.
- **Phân tích:** Modal GPU Worker nhận URL, tải xuống trực tiếp từ Supabase Storage, chạy full pipeline → trả về **Trend Alignment Score**.
- **Realtime cập nhật:** Frontend sử dụng **Supabase Realtime** (`postgres_changes` trên bảng `videos`) để nhận status update tức thì. Fallback: polling `GET /api/analyze/{video_id}` mỗi 8 giây.

---

## 2. 🧠 Động Cơ AI (AI Processing Engine)

Hai luồng xử lý song song, ưu tiên theo thứ tự:

### A. Pipeline Gemini 2.5 Flash — Primary (Scraper Videos)
- **File:** `backend/api/gemini_engine.py` → `process_video_with_gemini(video_data)`
- **Kích hoạt:** Webhook `POST /api/analyze-gemini` → Đẩy Job vào **Redis Queue** (`gemini_jobs`, timeout 900s). Retry schedule: 60s, 180s, 600s (tối đa 3 lần). Fallback: nếu Redis không khả dụng → spawn daemon thread.
- **Luồng xử lý 12 bước (chạy ngầm trong Worker):**
  1. `time.sleep(4)` — Rate-limit guard (15 req/min quota protection).
  2. `insert_video_metadata()` — đảm bảo record tồn tại trong DB.
  3. **Download video:** `yt-dlp` qua `video_downloader.py`. Nếu bị chặn IP (403/blocked) → kích hoạt `_trigger_modal_fallback()`.
  4. **Upload lên Gemini File API:** `client.files.upload(file=local_path)`.
  5. **Xóa file local** ngay lập tức để giải phóng ổ cứng.
  6. **Polling trạng thái:** Chờ `state == ACTIVE` (timeout 180s, check mỗi 5s). Fails nếu state = FAILED.
  7. **Inference:** `gemini-2.5-flash` (temperature=0.3), yêu cầu JSON output. Trả về: summary, category, sentiment, positive_score, keywords, audio_transcript.
  8. **Validate category** against `STANDARD_CATEGORIES` (10 danh mục tiếng Việt trong `backend_settings.py`).
  9. **Tính metrics:** `calculate_metrics()` → views_per_hour, engagement_rate, viral_velocity.
  10. **Lưu DB:** `update_ai_results()` → cập nhật tất cả kết quả, `ai_status="completed"`.
  11. **Sinh Semantic Embeddings:** `embedding_service.update_video_embedding()` (non-blocking, errors swallowed). Sử dụng Gemini `gemini-embedding-001` → vector 3072 chiều.
  12. **Dọn dẹp:** Xóa file trên Gemini File API.
- **Error handling:**
  - 429 `RESOURCE_EXHAUSTED` (daily quota) → `_fallback_llm_analysis()` ngay (retry vô nghĩa khi quota đã hết).
  - 429/503 temporary rate limit → sleep 60s rồi re-raise (RQ retry với backoff: 60s→180s→600s).
  - Timeout/500/RuntimeError/IP blocked → `_fallback_llm_analysis()` (OpenRouter → Groq).
  - Nếu Fallback text-only cũng fail → `_fallback_error_db()` ghi `ai_status='error'`.

### B. Pipeline Modal Serverless GPU — User Upload Only
- **File:** `services/ai_engine/modal_app.py` (1232 lines)
- **Mục đích:** Xử lý đa phương thức CHO USER UPLOADS. Không còn dùng làm fallback cho Scraper.
- **Hạ tầng:** Modal App `trendsense-ai`, GPU T4 hoặc L4, tối đa 3 containers. Persistent volume `trendsense-models` tại `/models` cho cache HuggingFace models.
- **Webhook:** `@modal.fastapi_endpoint(method="POST")` → nhận request → spawn `process_video` trên GPU container (fire-and-forget, trả `{status: "queued"}` ngay).

**Luồng xử lý Modal — `process_video(video_data)`:**

| Bước | Mô tả | Model/Tool |
|------|-------|-----------|
| 1 | Tải video (Supabase Signed URL hoặc TikTok URL) | `requests` / `yt-dlp` |
| 2 | Trích xuất frames (4 frames BLIP, 2 frames OCR) từ 10%-90% video | `OpenCV` |
| 3a | Audio → Text (max 30s) | `Faster-Whisper base` (CUDA, **int8** quantization) |
| 3b | Vision → Caption | `BLIP` (`Salesforce/blip-image-captioning-base`, CUDA) |
| 3c | Screen Text | `EasyOCR` (vi+en, GPU) |
| 4 | Tổng hợp tất cả → JSON | **OpenRouter** (10 free models, thử tuần tự) → **Groq** fallback |
| 5 | Cleanup: giải phóng GPU memory (`gc.collect()`, xóa model singletons) | |
| 6 | Sinh Semantic Embeddings | Gemini `gemini-embedding-001` (3072-dim) → pgvector (non-blocking) |
| 7a | **Scraper video:** Tính metrics → Lưu Supabase | `_calculate_metrics()` + `_update_supabase()` |
| 7b | **Upload video:** Trích xuất metadata + Trend Alignment | `_extract_video_metadata()` + `_score_trend_alignment()` + `_generate_trend_insights()` |

**LLM fallback chain trong Modal (`_call_groq()`):**
1. **OpenRouter** (primary, thử free models, mỗi model 2 attempts):
   - `meta-llama/llama-3.3-70b-instruct:free` → `google/gemma-4-31b-it:free` → `deepseek/deepseek-v4-flash:free` → `qwen/qwen3-next-80b-a3b-instruct:free` → `openai/gpt-oss-120b:free` → `nvidia/nemotron-3-super-120b-a12b:free` → `openrouter/free`
2. **Groq** (fallback, 4 models, 4 attempts với backoff):
   - `llama-3.3-70b-versatile` → `llama-3.1-8b-instant` → `llama3-8b-8192`

**Phân nhánh theo loại video trong Modal:**
- Chú ý: Hiện tại Modal chỉ phục vụ luồng **Upload path**. Luồng Scraper path đã bị loại bỏ khỏi Modal và chuyển hoàn toàn sang OpenRouter text-only để tiết kiệm chi phí GPU.

### C. Pipeline Local (CPU) — Dự phòng / CI
- **File:** `services/ai_engine/processor.py` → `process_video_item(video_data)`
- **Entry point:** `services/ai_engine/ai_core_main.py` → `run_ai_worker(reprocess_all=False)`
- **Mục đích:** Pipeline CPU-based chạy trên máy local hoặc CI, sử dụng Ollama thay vì Groq/Modal.
- **Luồng xử lý:**
  1. `calculate_metrics()` — Tính VPH, engagement rate, viral velocity.
  2. `sentiment_engine.analyze_batch()` — BERT multilingual (`nlptown/bert-base-multilingual-uncased-sentiment`) trên caption và nội dung video → positive_score + sentiment label.
  3. `categorizer.categorize_video()` — Rule-based keyword matching (12 categories) → fallback zero-shot (`mDeBERTa-v3-base-mnli-xnli`).
  4. `nlp_utils.clean_text()` + `extract_smart_keywords()` — Keyword extraction bằng `underthesea` (Vietnamese NLP).
  5. `video_downloader.download_video()` — yt-dlp download.
  6. `multimodal_engine.analyze_multimodal()` — Whisper (CPU, int8) + BLIP (CPU) + EasyOCR (CPU) → Ollama (`llama3:8b`) tổng hợp.
  7. `prediction_engine.run_viral_prediction()` — Random Forest inference.
  8. `update_ai_results()` — Lưu tất cả vào Supabase.

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
- `get_trending_categories()` — Top categories theo avg viral_velocity 14 ngày
- `get_trending_keywords()` — Keywords từ video có velocity > median (dùng `PERCENTILE_CONT(0.5)`)
- `get_duration_stats_by_category()` — MEDIAN duration viral theo category (tối thiểu 3 mẫu)
- `get_viral_audio_transcripts()` — Top 30 transcripts của video viral nhất

**Groq sinh nhận xét:** `_generate_trend_insights()` gọi Groq `llama-3.3-70b-versatile` để viết `overall_comment`, `top_strength`, `top_improvement` bằng tiếng Việt. Fallback: template-based nếu LLM fail.

**Kết quả lưu vào DB:** `video_duration`, `video_orientation`, `scene_cut_count`, `trend_alignment_score`, `trend_insights` (JSONB), `audio_transcript`

---

## 4. 📈 Động Cơ Dự Báo Viral (Prediction Engine)

Chỉ áp dụng cho **video TikTok được scrape** (có stats thực).

- **File:** `services/ai_engine/prediction_engine.py` → `run_viral_prediction(df)`
- **Model:** Random Forest (`data/models/rf_model.joblib`) — Inference Only
- **Features đầu vào:** `Like_Rate`, `Comment_Rate`, `Share_Rate`, `Save_Rate`, `Positive_Score`, `Views_Per_Hour`
- **Giới hạn:** Chỉ predict video < 14 ngày tuổi (`SLIDING_WINDOW_DAYS`); video cũ hơn tự động gán 0%
- **Output:** `viral_probability` (0–100%)
- **Fallback:** Nếu model file không tồn tại → mặc định 5.0%
- **Retrain:** Local scheduler (Windows Task Scheduler) — mỗi Chủ Nhật 00:00 ICT, chạy `services/ai_engine/train_model.py` và lưu model cục bộ (tuỳ chọn commit)
  - Label: Top 15% theo `viral_velocity` = positive class
  - Algorithm: `RandomForestClassifier(100 estimators, balanced class_weight)`
  - Safety check: Warn nếu accuracy giảm >20% so với model cũ

### Công thức Metrics (`services/ai_engine/math_utils.py`):
```python
age_hours      = max((now - create_time) / 3600, 0.1)
views_per_hour = views / age_hours
engagement_pts = likes + (comments × 2) + (saves × 3) + (shares × 4)
engagement_rate= (engagement_pts / views) × 100
viral_velocity = (views_per_hour × engagement_rate) / log10(age_hours + 10)
```

### Sentiment Analysis (`services/ai_engine/sentiment_engine.py`):
- **Model:** `nlptown/bert-base-multilingual-uncased-sentiment` (multilingual BERT, CPU)
- **Input:** Caption và nội dung video (hoặc top comments nếu có) → batch inference (batch_size=32)
- **Output:** Star rating (1-5) → `positive_score` (0-100) + sentiment label (positive/neutral/negative)

### Phân loại danh mục (`services/ai_engine/categorizer.py`):
- **Primary:** Rule-based keyword matching — 12 categories × ~20 keywords each (Vietnamese + English)
- **Fallback:** Zero-shot classification (`MoritzLaurer/mDeBERTa-v3-base-mnli-xnli`, threshold 0.3)
- **Output:** Pipe-separated string, tối đa 3 categories (`MAX_CATEGORIES`)

### Gợi ý tối ưu (OpenRouter AI):
- **File:** `_generate_recommendations()` trong `backend/api/routes.py`
- **LLM Client:** `backend/api/llm_client.py` — thử 10 OpenRouter free models tuần tự → fallback Groq (`llama-3.3-70b-versatile`)
- **4 đề xuất:** `hook` (3 giây đầu), `audio` (nhạc trending), `caption_hashtags` (SEO TikTok), `pacing_cta` (nhịp cắt + Call-to-Action)
- **Fallback:** Static rule-based recommendations nếu tất cả LLM fail

### Semantic Search (`backend/api/embedding_service.py`):
- **Model:** Google Gemini `gemini-embedding-001` (3072-dim vectors, fallback `gemini-embedding-2`)
- **Lưu:** Cột `embedding vector(3072)` trong bảng `videos` (không index — Supabase pgvector giới hạn 2000 dims cho IVFFlat/HNSW, sequential scan đủ nhanh với ~2000 rows)
- **Search:** `semantic_search(query, limit)` → cosine distance `<=>` operator
- **Integration:** `GET /api/videos?search=...` ưu tiên semantic search, fallback ILIKE nếu fail

---

## 5. 🗄️ Cơ Sở Dữ Liệu (Database Layer)

- **Công nghệ:** Supabase (PostgreSQL) + `psycopg2` (raw SQL, không ORM) — quản lý tại `core/db/`
- **Kết nối:** `core/db/session.py` → `get_connection()` từ `DATABASE_URL`. Không connection pooling — mỗi function tạo connection mới.
- **Migration:** `core/db/migrations/001_pgvector.sql` — Enable pgvector extension + thêm cột `embedding vector(3072)`. `002_pgvector_upgrade_3072.sql` — Upgrade từ 768 → 3072 nếu đã có column cũ (xóa index cũ, đổi dim, không tạo index mới do 2000 dim limit).

### Bảng `videos` — Schema chính:

| Nhóm cột | Các cột |
|----------|---------|
| **Metadata cơ bản** | `video_id (PK)`, `link`, `caption`, `scrape_date`, `create_time` |
| **Engagement stats** | `views`, `likes`, `comments`, `shares`, `saves` |
| **Metrics tính toán** | `views_per_hour`, `engagement_rate`, `viral_velocity`, `viral_probability` |
| **AI Analysis** | `video_description`, `category (TEXT[])`, `video_sentiment`, `positive_score`, `top_keywords`, `audio_transcript`, `embedding (vector 768)` |
| **Upload Analysis** | `video_duration`, `video_orientation`, `scene_cut_count`, `trend_alignment_score`, `trend_insights (JSONB)` |
| **Trạng thái** | `ai_status` (`pending`/`downloading`/`analyzing`/`summarizing`/`completed`/`error`/`user_pending`) |

### Các Bảng Quản Lý Subscription & Payment:
- **`subscriptions`**: `user_id (PK)`, `plan`, `status`, `started_at`, `expires_at`
- **`payments`**: `id (PK)`, `user_id`, `amount`, `plan`, `status`, `reference_code`, `transaction_id`, `paid_at`
- **`daily_usage`**: `user_id (PK)`, `usage_date (PK)`, `videos_analyzed`

### Bảng `history` — Dedup Scraper:
- Lưu `video_id` đã cào để tránh cào lại. `mark_as_scraped()` / `is_scraped()`

### Indexes:
- `idx_ai_status`, `idx_scrape_date`, `idx_category`
- `idx_videos_embedding` — **Tạm bỏ**: Supabase pgvector giới hạn 2000 dims cho IVFFlat/HNSW. Sequential scan đủ nhanh (<50ms) với ~2000 rows. Khi Supabase nâng cấp pgvector >= 0.7.0, tạo lại: `CREATE INDEX idx_videos_embedding ON videos USING hnsw (embedding vector_cosine_ops);`

### Các hàm DB quan trọng (`core/db/models.py`, ~640 lines):

| Hàm | Mục đích |
|-----|---------|
| `init_db()` | Tạo bảng `history`, `videos` nếu chưa tồn tại. ALTER TABLE thêm trend-alignment columns. |
| `insert_video_metadata()` | INSERT/Upsert metadata từ scraper |
| `update_ai_results()` | Cập nhật kết quả AI cho scraper video (category, description, keywords, sentiment, metrics) |
| `update_upload_analysis()` | Cập nhật Trend Alignment Score cho upload video |
| `insert_user_video()` | Insert video upload với `ai_status='user_pending'` |
| `check_video_quota()` | Kiểm tra user còn quota upload theo plan không |
| `complete_payment()` | Xử lý webhook thanh toán thành công, update subscription |
| `get_all_analyzed_videos()` | Phân trang + filter (category/sentiment/search/semantic) + sort cho Dashboard |
| `get_video_by_id()` | Chi tiết 1 video |
| `get_dashboard_stats()` | Tổng hợp stats cho Overview panel |
| `get_category_stats()` | Thống kê theo danh mục (unnest `TEXT[]` array) |
| `get_sentiment_stats()` | Phân bổ cảm xúc (group by) |
| `get_top_keywords()` | Top keywords (Python Counter trên comma-separated strings) |
| `get_timeline_data()` | Daily aggregation 30 ngày |
| `get_trending_categories()` | Benchmark: Top categories 14 ngày |
| `get_trending_keywords()` | Benchmark: Keywords từ video velocity > median |
| `get_duration_stats_by_category()` | Benchmark: Median duration theo category |
| `get_viral_audio_transcripts()` | Benchmark: Top 30 transcripts viral |
| `get_pending_videos()` | Videos cần xử lý AI (`ai_status='pending'`, `views > 0`) |
| `get_recent_videos()` | Completed videos N ngày gần nhất |
| `get_high_potential_videos()` | Videos có viral_probability hoặc engagement_rate > threshold |
| `update_rescraped_stats_only()` | Cập nhật stats khi re-scrape (không đụng comments) |
| `update_rescraped_metadata()` | Cập nhật full metadata khi re-scrape |
| `delete_video()` | Xóa video chết/spam khỏi cả 2 bảng |
| `reset_all_analysis_status()` | Reset toàn bộ về `pending` (re-process) |
| `extract_video_id()` | Trích video ID từ TikTok URL |

---

## 6. 🖥️ Frontend Dashboard (Next.js)

- **Vị trí:** `frontend/` — Next.js 16.2.4 App Router + React 19.2.4 + Tailwind CSS v4
- **Chạy:** Port 3000, proxy sang Backend port 8080 qua `next.config.mjs` rewrites
- **Design:** Dark theme (pure black), glassmorphism cards, neon glow borders, animated background orbs, shimmer skeletons
- **Fonts:** Google Fonts Inter (300-900)
- **Realtime:** Supabase Realtime (`@supabase/supabase-js`) cho phân tích video upload

### Các trang chính:

| Route | File | Nội dung |
|-------|------|---------|
| `/` | `app/page.js` | Trang chủ — Hero section (animated orbs, trust badges: Whisper/BLIP/Groq/RF), How It Works (3 bước), Stats tổng quan (6 StatCards), Top 10 Video Table (sort by viral_probability), Category Ranking (3-6 cards), CTA |
| `/dashboard` | `app/dashboard/page.js` | Dashboard đầy đủ — Sidebar filters (search, category multi-select, sentiment dropdown, min viral % slider, sentiment distribution, keyword cloud) + Main table (sortable, phân trang) + 6 stat cards |
| `/analyze` | `app/analyze/page.js` | Upload & phân tích — Drag-drop upload (100MB max), Supabase Realtime status tracking (5 bước: user_pending→downloading→analyzing→summarizing→completed), hiển thị kết quả 2 chế độ: Content-based (Trend Alignment Score 0-100 với breakdown) hoặc Full AI (viral probability + recommendations) |
| `/video/[id]` | `app/video/[id]/page.js` | Chi tiết video — Caption, description, categories, sentiment, viral circle, metrics grid (6 cards), performance bars, top 5 comments, keyword cloud, link TikTok |

### Components:

| Component | File | Mô tả |
|-----------|------|-------|
| `Navbar` | `app/components/Navbar.js` | Fixed top nav, glassmorphism, links: `/`, `/dashboard`, `/analyze`. Mobile hamburger. CTA "Dự Báo Ngay" |
| `Footer` | `app/components/Footer.js` | 3-column: brand, nav links, tech stack tags (Next.js, FastAPI, Supabase, Modal, Groq, Whisper, BLIP) |
| `StatCard` | `app/components/StatCard.js` | Animated stat card với icon, value, delta indicator, colored glow |
| `ViralBar` | `app/components/ViralBar.js` | Horizontal progress bar: green (<40%), yellow (40-70%), red (70%+) |
| `VideoTable` | `app/components/VideoTable.js` | Sortable data table: Index, Video (caption+desc), Category badges, Viral % bar, Velocity, Views, Engagement %, "Chi tiết" link |

### API Client (`app/lib/api.js`):

| Function | Method | Endpoint | Mục đích |
|----------|--------|----------|---------|
| `getVideos(params)` | GET | `/api/videos?...` | Danh sách video phân trang, filter, sort, search (ưu tiên semantic) |
| `getVideo(videoId)` | GET | `/api/videos/{videoId}` | Chi tiết 1 video |
| `getStats()` | GET | `/api/stats` | Tổng quan stats |
| `getCategories()` | GET | `/api/categories` | Stats theo danh mục |
| `getSentiments()` | GET | `/api/sentiments` | Phân bổ cảm xúc |
| `getKeywords(limit)` | GET | `/api/keywords?limit=N` | Top keywords |
| `getTimeline()` | GET | `/api/timeline` | Timeline 30 ngày (defined, chưa dùng trong pages) |
| `getUploadUrl(filename, contentType)` | POST | `/api/upload-url` | Lấy presigned URL |
| `analyzeVideo(videoId, storagePath, caption)` | POST | `/api/analyze` | Trigger AI pipeline |
| `checkAnalysis(videoId)` | GET | `/api/analyze/{videoId}` | Poll trạng thái + kết quả |

### Supabase Client (`app/lib/supabase.js`):
- Env vars: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- Dùng cho Realtime subscriptions trong trang `/analyze`. Graceful degradation nếu env vars thiếu.

---

## 7. ⚙️ Scheduling — Local Execution (GitHub Actions Disabled)

To avoid IP blocking, all automated scraping and retraining have been moved to local Windows Task Scheduler. The original GitHub Actions workflows are deprecated and kept for reference only.

### Local Scraper Schedule
- **Trigger:** Windows Task Scheduler
- **Script:** `run_scraper_scheduled.bat`
- **Frequency:** Every 4 hours
- **Action:** Runs `services/tiktok_scraper/scraper_main.py` → inserts data → triggers AI pipeline (Gemini primary, Modal fallback)

### Weekly Retraining (Local, Sunday 00:00 ICT)
- **Script:** `services/ai_engine/train_model.py`
- **Action:** Scrape fresh stats (14 days) → train Random Forest → save model locally (optional commit)

### Weekly Cleanup (Local, Sunday 01:00 ICT)
- **Script:** `scripts/reset_viral_predictions.py`
- **Action:** Reset `viral_probability` for videos older than 14 days

*The original `.github/workflows/ai_pipeline.yml`, `weekly_train.yml`, and `weekly_cleanup.yml` are no longer active.*

---

## 8. 🔑 Cấu Hình & Biến Môi Trường

### Backend / API Server (`core/config/backend_settings.py`):

| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `DATABASE_URL` | **REQUIRED** | PostgreSQL connection string (Supabase). Fatal nếu thiếu. |
| `REDIS_URL` | `redis://localhost:6679` | Upstash Redis cho Rate Limit và Task Queue |
| `SUPABASE_URL` | `""` | URL Supabase cho Presigned Upload |
| `SUPABASE_SERVICE_KEY` | `""` | Service key để bypass RLS (chỉ dùng backend) |
| `SUPABASE_BUCKET` | `"videos"` | Tên bucket Storage |
| `OPENROUTER_API_KEY` | `""` | API Key chính cho text generation (10 free models) |
| `OPENROUTER_DEFAULT_MODEL` | `openrouter/free` | Default model (dùng khi chỉ định cụ thể) |
| `GROQ_API_KEY` | `""` | Fallback text generation API |
| `GEMINI_API_KEY` | `""` | Video analysis (Gemini 2.5 Flash) + Semantic Embeddings (gemini-embedding-001, 3072-dim) |
| `MODAL_WEBHOOK_URL` | `""` | URL webhook Modal GPU endpoint |
| `FRONTEND_URL` | `http://localhost:3000` | CORS origin |

### Scraper / AI Engine (`core/config/service_settings.py`):

| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `MAX_VIDEOS` | 30 | Số video tối đa mỗi lần scrape |
| `SLIDING_WINDOW_DAYS` | 14 | Cửa sổ dữ liệu cho train/predict |
| `DOWNLOAD_VIDEOS` | True | Có tải video về không |
| `VIDEO_RETENTION_DAYS` | 30 | Tuổi tối đa video trước khi cleanup |
| `MAX_VIDEO_SIZE_MB` | 15 | Kích thước tối đa khi download |
| `MAX_VIDEO_DURATION` | 180 | Thời lượng tối đa (giây) |
| `ZERO_SHOT_MODEL` | `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli` | Zero-shot classification |
| `VISION_CAPTION_MODEL` | `Salesforce/blip-image-captioning-base` | BLIP captioning |
| `WHISPER_MODEL` | `base` | Whisper model size |
| `WHISPER_COMPUTE_TYPE` | `int8` | Whisper quantization |
| `OCR_LANG` | `['vi', 'en']` | OCR languages |
| `OLLAMA_MODEL` | `llama3:8b` | Local Ollama model |

### Frontend:

| Biến | Mô tả |
|------|-------|
| `BACKEND_URL` | Backend URL cho Next.js rewrites (default `http://localhost:8080`) |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase URL cho Realtime |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon key cho Realtime |

### Scraper CI:

| Biến | Mô tả |
|------|-------|
| `PROXY_LIST` | JSON array hoặc comma-separated proxies cho scraper |
| `GEMINI_WEBHOOK_URL` | Gemini backend endpoint (default `http://localhost:8000/api/analyze-gemini`) |

### 10 Danh Mục Chuẩn (`STANDARD_CATEGORIES` trong `backend_settings.py`):
```
Giải trí | Giáo dục | Công nghệ | Ẩm thực | Thể thao
Làm đẹp & Thời trang | Đời sống | Tài chính | Tin tức | Khác
```

### 12 Danh Mục Scraper (`CATEGORIES` trong `categorizer.py`):
```
🎭 Giải trí | 🎵 Âm nhạc | 🍳 Ẩm thực | 💻 Công nghệ | 👗 Thời trang
📚 Giáo dục | 🏋️ Thể thao | 🐾 Động vật | 💄 Làm đẹp | 📰 Tin tức
💰 Tài chính | 🏠 Đời sống
```

---

## 9. 📁 Cấu Trúc Thư Mục

```text
TrendSense/
├── backend/
│   ├── main.py                    # FastAPI app (v3.0.0), lifespan, CORS, rate limit
│   ├── worker.py                  # RQ worker subprocess (gemini_jobs queue, 900s timeout)
│   ├── requirements.txt           # Python dependencies (17 packages)
│   └── api/
│       ├── routes.py              # 11 REST endpoints (mounted at /api)
│       ├── gemini_engine.py       # Gemini 2.5 Flash video analysis pipeline
│       ├── llm_client.py          # Unified LLM client (OpenRouter 10 models → Groq)
│       ├── embedding_service.py   # pgvector semantic search (gemini-embedding-001, 3072-dim)
│       ├── storage_service.py     # Supabase Storage presigned URLs
│       └── rate_limiter.py        # SlowAPI limiter (Redis primary, in-memory fallback)
├── core/
│   ├── config/
│   │   ├── base.py                # Shared config (DATABASE_URL, HF_TOKEN, GROQ, MODAL)
│   │   ├── backend_settings.py    # Backend-specific (Redis, Supabase, OpenRouter, CORS)
│   │   └── service_settings.py    # Scraper + AI engine config (thresholds, models, paths)
│   └── db/
│       ├── session.py             # psycopg2 connection factory
│       ├── models.py              # All DB schema + CRUD + analytics (~640 lines)
│       └── migrations/
│           ├── 001_pgvector.sql          # pgvector extension + embedding column vector(3072)
│           └── 002_pgvector_upgrade_3072.sql  # Upgrade 768→3072 (drop old index)
├── services/
│   ├── ai_engine/
│   │   ├── modal_app.py           # Modal serverless GPU (1232 lines, T4/L4)
│   │   ├── processor.py           # Local pipeline orchestrator (CPU)
│   │   ├── ai_core_main.py        # Local AI entry point
│   │   ├── multimodal_engine.py   # Local multimodal (Whisper+BLIP+OCR+Ollama, CPU)
│   │   ├── prediction_engine.py   # Random Forest viral prediction (inference)
│   │   ├── train_model.py         # Weekly model retraining
│   │   ├── model_manager.py       # Save/load sklearn models (joblib)
│   │   ├── categorizer.py         # Rule-based + zero-shot classification (12 categories)
│   │   ├── sentiment_engine.py    # BERT multilingual sentiment (nlptown)
│   │   ├── math_utils.py          # VPH, engagement rate, viral velocity
│   │   ├── nlp_utils.py           # Vietnamese keyword extraction (underthesea)
│   │   └── requirements.txt       # AI engine dependencies
│   └── tiktok_scraper/
│       ├── scraper_main.py        # Main scraper entry point
│       ├── browser.py             # Undetected Chromedriver + proxy rotation
│       ├── link_crawler.py        # Video URL collection (3x buffer)
│       ├── content_parser.py      # Stats extraction (JSON + regex fallback)
│       ├── captcha.py             # TikTok rotate CAPTCHA solver (external API)
│       ├── video_downloader.py    # yt-dlp video download
│       ├── utils.py               # parse_like_count (K/M suffixes)
│       └── requirements.txt       # Scraper dependencies
├── frontend/
│   ├── app/
│   │   ├── page.js                # Home page (hero, stats, trending table, categories)
│   │   ├── layout.js              # Root layout (Inter font, Vietnamese metadata)
│   │   ├── globals.css            # Dark theme, glassmorphism, neon, animations
│   │   ├── dashboard/page.js      # Dashboard (filters, sortable table, pagination)
│   │   ├── analyze/page.js        # Upload + Realtime analysis + results
│   │   ├── video/[id]/page.js     # Video detail (metrics, comments, keywords)
│   │   ├── lib/
│   │   │   ├── api.js             # API client (10 functions)
│   │   │   └── supabase.js        # Supabase client for Realtime
│   │   └── components/
│   │       ├── Navbar.js           # Fixed nav, glassmorphism, mobile menu
│   │       ├── Footer.js           # 3-column footer, tech stack tags
│   │       ├── StatCard.js         # Animated stat card
│   │       ├── ViralBar.js         # Color-coded viral probability bar
│   │       └── VideoTable.js       # Sortable video data table
│   ├── next.config.mjs            # API proxy rewrites to backend
│   └── package.json               # Next.js 16.2.4, React 19.2.4, Tailwind v4
├── data/
│   ├── models/                    # rf_model.joblib + metrics.json
│   ├── videos/                    # Downloaded video files (temp)
│   └── db/                        # Local DB files
├── scripts/
│   ├── run.py                     # Legacy local runner (outdated paths)
│   ├── reset_viral_predictions.py # Reset viral_probability for old videos
│   ├── backfill_embeddings.py     # Backfill embedding cho video completed nhưng thiếu vector
│   ├── migrate_v2.py              # DB migration scripts
│   └── ...                        # Other utility scripts
├── .github/workflows/
│   ├── ai_pipeline.yml            # Scrape + AI every 4 hours
│   ├── weekly_train.yml           # Model retrain Sunday midnight
│   └── weekly_cleanup.yml         # Viral status reset Sunday 1am
├── render.yaml                    # Render deployment (free tier, Singapore)
├── .env.example                   # All environment variables template
└── README.md                      # Project overview
```

---

## 🔄 Data Flow — Tóm Tắt Đầy Đủ

### Luồng Scraper (TikTok → Dashboard):
```text
Local Scheduler (mỗi 4h)
  → scraper_main.py (Undetected Chromedriver + Proxy Rotation + CAPTCHA solver)
  → content_parser.py (parse HTML → stats)
  → langdetect filter (Vietnamese only)
  → insert_video_metadata() → Supabase (ai_status=pending)
  → _trigger_ai_pipeline():
      [Primary] POST /api/analyze-gemini
          → Redis Queue (gemini_jobs) nhận Job
          → Redis Worker (gemini_engine.py):
              → sleep(4) rate-limit guard
              → yt-dlp download video
              → Gemini File API upload → poll ACTIVE
              → gemini-2.5-flash inference → JSON (summary, category, sentiment, keywords)
              → validate category + calculate_metrics()
              → update_ai_results() → Supabase (ai_status=completed)
              → embedding_service → gemini-embedding-001 (3072-dim) → pgvector (non-blocking)
              → cleanup Gemini file
              [Nếu fail] → _fallback_to_llm() (OpenRouter/Groq text-only)
      [Fallback — Backend không khả dụng] _fallback_llm_analysis():
          → OpenRouter (10 free models) → Groq fallback
          → Text-only phân tích (caption + stats) → JSON
          → calculate_metrics() → update_ai_results() → Supabase
  → Next.js Dashboard hiển thị
```

### Luồng Upload (User Video → Trend Alignment):
```text
User upload video (browser)
  → GET /api/upload-url → storage_service.py → Presigned URL + video_id
  → PUT file trực tiếp lên Supabase Storage
  → POST /api/analyze (rate limit 5/hr/IP, kèm storage_path + caption)
      → Backend insert_user_video() (ai_status=user_pending)
      → Tạo Signed Download URL → gửi webhook sang MODAL_WEBHOOK_URL
          → Modal GPU Worker (T4/L4):
              → Download từ Supabase Storage URL
              → Whisper (audio transcript, max 30s) + BLIP (4 frames) + EasyOCR (2 frames)
              → OpenRouter (10 free models) → Groq fallback → JSON
              → _extract_video_metadata() (duration, orientation, scene cuts)
              → _score_trend_alignment() (Python deterministic, 5 axes)
              → _generate_trend_insights() (Groq commentary)
              → _update_supabase_upload() (ai_status=completed)
  → Supabase Realtime push → Frontend nhận instant update
  → Fallback: Frontend polls GET /api/analyze/{video_id} mỗi 8s
  → Hiển thị Trend Alignment Score (0-100) + breakdown + insights
```

### Luồng Weekly Retrain (Random Forest):
```text
Local Scheduler (Chủ Nhật 00:00 ICT)
  → scraper_main.py (cào stats mới nhất)
  → train_model.py:
      → get_recent_videos(14 days)
      → Feature engineering (Like_Rate, Comment_Rate, Share_Rate, Save_Rate, Positive_Score, VPH)
      → Label: Top 15% viral_velocity = positive
      → RandomForestClassifier(100, balanced) → 80/20 split
      → Safety check: warn nếu accuracy giảm >20%
      → save_model() → rf_model.joblib + metrics.json
  → git commit + push → main branch [skip ci]
  → Backend load model mới ở request tiếp theo
```

### Luồng Weekly Viral Reset:
```text
Local Scheduler (Chủ Nhật 01:00 ICT)
  → reset_viral_predictions.py
  → UPDATE videos SET viral_probability = 0 WHERE scrape_date < now - 14 days
  → Cho phép re-predict với model mới train