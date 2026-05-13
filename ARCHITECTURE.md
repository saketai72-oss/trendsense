# System Architecture — TrendSense

## 1. Project Overview

### Project Name
TrendSense

### Purpose
A hybrid‑cloud trend analysis and viral prediction platform for TikTok videos. It combines automated TikTok scraping, AI‑powered video analysis, user video uploads with trend alignment scoring, and a real‑time Next.js dashboard.

### Main Goals
- Predict viral probability of TikTok videos using engagement metrics.
- Extract trending content (keywords, hashtags, categories) from high‑probability videos.
- Provide a Trend Alignment Score for user‑uploaded videos based on current trends.
- Offer a real‑time dashboard for monitoring and search.

---

## 2. Tech Stack

| Layer | Technologies |
|-------|--------------|
| Backend | FastAPI (Python 3.11), Redis (Upstash), RQ, SlowAPI |
| AI & ML | Gemini 2.5 Flash, Gemini Embedding, OpenRouter (10 free models), Groq, Whisper (int8), BLIP, EasyOCR, scikit‑learn (Random Forest) |
| GPU Serverless | Modal (T4/L4, persistent volume) |
| Database | Supabase PostgreSQL + pgvector |
| Storage | Supabase Storage (S3‑compatible) |
| Frontend | Next.js 16.2.4 (App Router), React 19, Tailwind CSS v4, Supabase Realtime |
| Scraping | Undetected Chromedriver, yt‑dlp, CAPTCHA API |
| Scheduling | Local Windows Task Scheduler / `run_scraper_scheduled.bat` |

---

## 3. System Architecture

```text
[ TikTok / User Upload ]
        │
        ▼
┌───────────────────────────────────────┐
│          FastAPI Backend              │
│  (rate‑limited, Redis + SlowAPI)      │
└───────────────┬───────────────────────┘
                │
                ├────────────────────┐
                ▼                    ▼
        ┌─────────────┐      ┌─────────────┐
        │ Redis (RQ)  │      │   Modal     │
        │ gemini_jobs │      │ (GPU)       │
        └──────┬──────┘      └──────┬──────┘
               │                    │
               ▼                    ▼
        ┌─────────────┐      ┌─────────────┐
        │  Gemini     │      │  Whisper    │
        │  2.5 Flash  │      │  + BLIP     │
        │  (primary)  │      │  + OCR      │
        └──────┬──────┘      └──────┬──────┘
               │                    │
               └──────────┬─────────┘
                          ▼
                ┌─────────────────────┐
                │  Supabase PostgreSQL│
                │      (pgvector)     │
                └──────────┬──────────┘
                           ▼
                ┌─────────────────────┐
                │  Next.js Frontend   │
                │  (Realtime updates) │
                └─────────────────────┘
```

**Key design choices:**
- Primary AI path: Gemini 2.5 Flash via Redis RQ worker.
- Fallback path: Modal Serverless GPU (T4/L4) with OpenRouter → Groq.
- User uploads: Presigned URLs → Supabase Storage → Modal GPU → Trend Alignment Score.
- Semantic search: `gemini-embedding-001` → 3072‑dim vectors in pgvector.
- No ORM: Raw SQL (`psycopg2`) in `core/db/models.py`.

---

## 4. Folder Structure

```text
TrendSense/
├── backend/
│   ├── api/               # FastAPI routes, Gemini engine, LLM client, embedding service, storage service
│   ├── auth/              # JWT authentication, OAuth
│   ├── middleware/        # Rate limiting, logging
│   ├── main.py            # FastAPI app entry point
│   └── worker.py          # RQ worker (gemini_jobs)
├── core/
│   ├── config/            # Environment‑specific settings
│   └── db/                # Raw SQL connections, schema, CRUD operations
├── services/
│   ├── ai_engine/         # Modal GPU app, local CPU pipeline, prediction engine, sentiment, categorizer
│   └── tiktok_scraper/    # Browser automation, CAPTCHA solving, content parsing, video download
├── frontend/              # Next.js App Router application
├── data/                  # Model files (rf_model.joblib), downloaded videos, local DB
├── scripts/               # Utility scripts (fix misclassifications, migrations, etc.)
└── docs/                  # Documentation (pipeline overview, local setup, architecture templates)
```

---

## 5. Database Architecture

### Main Tables

**videos**
| Column              | Type          | Description |
|---------------------|---------------|-------------|
| video_id            | TEXT (PK)     | TikTok video ID or `upload_...` |
| caption             | TEXT          | Original caption |
| views, likes, etc.  | INT           | Engagement stats |
| views_per_hour      | REAL          | Calculated metric |
| engagement_rate     | REAL          | Calculated metric |
| viral_velocity      | REAL          | Calculated metric |
| viral_probability   | REAL          | Model 1 output (0–100) |
| category            | TEXT[]        | Array of category names (1–3) |
| video_sentiment     | TEXT          | `🟢 TÍCH CỰC` / `🔴 TIÊU CỰC` / `🟡 TRUNG LẬP` |
| positive_score      | REAL          | 0–100 sentiment score |
| top_keywords        | TEXT          | Comma‑separated keywords (from AI) |
| audio_transcript    | TEXT          | Whisper output |
| embedding           | vector(3072)  | pgvector semantic embedding |
| ai_status           | VARCHAR(20)   | `pending`, `completed`, `error`, etc. |

**trends_weekly**
| Column          | Type      | Description |
|-----------------|-----------|-------------|
| week_start      | DATE      | Monday of the week |
| keywords        | JSONB     | Top 20 keywords + counts |
| hashtags        | JSONB     | Top 10 hashtags + counts |
| categories      | JSONB     | Category distribution |
| audio_snippets  | JSONB     | Sample transcripts from viral videos |

**video_analyses** (user uploads only)
| Column                  | Type      | Description |
|-------------------------|-----------|-------------|
| video_id                | TEXT (PK) | Same as videos.video_id |
| user_id                 | UUID      | References users table |
| video_duration          | REAL      | Extracted from file |
| video_orientation       | VARCHAR   | `portrait` / `landscape` / `square` |
| scene_cut_count         | INT       | Detected scene changes |
| trend_alignment_score   | REAL      | 0–100 alignment with current trends |
| trend_insights          | JSONB     | Model 2 insights (breakdown, comments) |

**history** – dedup for scraper (stores already scraped video_ids).

---

## 6. API Architecture

### Pattern

```
Client → API Route (FastAPI) → Service Layer (core/db/models.py) → PostgreSQL
```

Routes are defined in `backend/api/routes.py`. Key endpoints:

| Endpoint                     | Method | Description |
|------------------------------|--------|-------------|
| `/api/videos`                | GET    | Paginated + filtered + semantic search |
| `/api/videos/{video_id}`     | GET    | Single video details (scraped or upload) |
| `/api/stats`                 | GET    | Dashboard summary |
| `/api/categories`            | GET    | Category performance |
| `/api/sentiments`            | GET    | Sentiment distribution |
| `/api/keywords`              | GET    | Top keywords across all videos |
| `/api/trending/keywords`     | GET    | Current trend report (Model 2) |
| `/api/upload-url`            | POST   | Generate presigned URL for user upload |
| `/api/analyze`               | POST   | Trigger Modal pipeline (user uploads) |
| `/api/analyze-gemini`        | POST   | Webhook from scraper → enqueue RQ job |
| `/api/my-videos`             | GET    | List user‑uploaded videos |
| `/api/my-videos/{video_id}`  | DELETE | Delete a user video |

**Rules**:
- Rate limiting via SlowAPI + Redis (fallback in‑memory).
- No business logic inside route handlers; delegate to `models.py` functions.
- Input validation using Pydantic models.

---

## 7. Authentication Flow

- JWT‑based authentication (local credentials + Google OAuth).
- Endpoints for upload / analyze require valid JWT.
- Refresh tokens stored in `refresh_tokens` table.
- Middleware verifies token on protected routes.

---

## 8. AI Architecture (Two‑Model Approach)

### Model 1 – Engagement Predictor (Random Forest)
- **Purpose**: Predict `viral_probability` (0–100) for scraped TikTok videos.
- **Features**: Like_Rate, Comment_Rate, Share_Rate, Save_Rate, Positive_Score, Views_Per_Hour.
- **Training**: Weekly (Sunday 00:00 ICT) on last 14 days of data. Top 85% `viral_velocity` as positive class. Stratified 5‑fold CV. Metrics: accuracy, precision, recall, F1, AUC.
- **Storage**: `data/models/rf_model.joblib` + metrics.json.

### Model 2 – Trend Content Analyzer
- **Purpose**: Aggregate trending keywords, hashtags, categories, and audio snippets from videos where `viral_probability ≥ 70%` in last 14 days.
- **Execution**: Automatically after Model 1 training.
- **Output**: Snapshot stored in `trends_weekly` (JSONB).
- **Integration with uploads**: When a user uploads a video, the Modal pipeline loads the latest trend report and computes a secondary alignment score (based on keyword overlap and category popularity). The final `trend_alignment_score` is the average of the deterministic multimodal score and this trend‑based score.

### Supporting AI Components
- **Gemini 2.5 Flash** – primary video analysis (summary, category, sentiment, keywords, transcript).
- **Modal GPU Pipeline** – fallback for scraper and mandatory for user uploads. Uses Whisper (audio), BLIP (frames), EasyOCR (screen text), then calls OpenRouter (10 free models) → Groq fallback.
- **Sentiment Engine** – offline BERT multilingual model (`nlptown/bert-base-multilingual-uncased-sentiment`) for local processing.
- **Categorizer** – rule‑based keyword matching + zero‑shot mDeBERTa fallback. Returns 1–3 categories as an array.
- **Embedding Service** – Gemini `gemini-embedding-001` (3072‑dim) stored in pgvector for semantic search.

---

## 9. State Management

- **Backend**: Stateless (except RQ jobs). State stored in PostgreSQL.
- **Frontend**: Client – React state + Supabase Realtime for live updates. Server – Next.js server components fetch data via API.

---

## 10. Error Handling Rules

- **Backend**: Centralised exception handlers in `main.py`. Never expose raw SQL errors.
- **Scraper**: Retry with backoff (60/180/600s). Proxy rotation on block detection.
- **AI Providers**: Full fallback chain (Gemini → Modal → OpenRouter → Groq). If all fail, mark `ai_status = 'error'`.
- **Frontend**: User‑friendly error messages, fallback to polling when Realtime fails.

---

## 11. Security Rules

- **Never hardcode secrets**: all in `.env`; use `token_fetcher.py` for dynamic tokens.
- **Input validation** using Pydantic for all API requests.
- **Rate limiting** on public endpoints (e.g., `/api/analyze`: 5/hour/IP).
- **CORS** restricted to `FRONTEND_URL`.
- **Presigned URLs** for uploads; backend never handles raw video bytes.

---

## 12. Performance Rules

- **Database**: Indexes on `scrape_date`, `ai_status`, `category`. No pgvector index due to Supabase dimension limit (2000). Sequential scan is sufficient for ~2000 rows.
- **AI Workers**: RQ queues with job timeout 900s. Modal max containers = 3 to avoid rate limits.
- **Frontend**: Lazy load components, use `next/image` for optimisation, debounced search.

---

## 13. Coding Standards

- **Python**: Follow PEP 8. Type hints strongly encouraged.
- **TypeScript**: strict mode enabled, no `any`.
- **Components**: Small, reusable, feature‑based organisation.
- **Naming**: Descriptive, avoid abbreviations.

---

## 14. Deployment Architecture

- **Backend**: Local development on `localhost:8080`. Production can be deployed to Render / any VPS.
- **Frontend**: Vercel (recommended) or local with `npm run dev`.
- **Modal**: `modal deploy services/ai_engine/modal_app.py`.
- **Scraper**: Windows Task Scheduler runs `run_scraper_scheduled.bat` every 4 hours.
- **Weekly retraining**: Windows Task Scheduler runs `train_model.py` Sunday 00:00.

GitHub Actions workflows are deprecated (to avoid IP blocking).

---

## 15. Environment Variables (Critical)

See `.env.example`.

| Variable                     | Used by                         |
|------------------------------|---------------------------------|
| `DATABASE_URL`               | Backend, scraper, AI engine     |
| `GEMINI_API_KEY`             | Gemini video analysis & embeddings |
| `OPENROUTER_API_KEY`         | LLM fallback chain              |
| `GROQ_API_KEY`               | Final LLM fallback              |
| `MODAL_WEBHOOK_URL`          | Modal GPU endpoint              |
| `REDIS_URL`                  | Rate limiting + RQ queue        |
| `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` | Storage + Realtime     |
| `PROXY_LIST`                 | Scraper proxies (JSON array or comma‑separated) |

---

## 16. Current Limitations

- **No connection pooling** – each DB call creates a fresh `psycopg2` connection. Acceptable at <10 req/s.
- **pgvector index disabled** due to Supabase dimension limit (2000). Sequential scan for ~2000 rows.
- **Gemini daily quota** – worker sleeps 4s before each inference (15 req/min guard). Exhaustion triggers Modal fallback.
- **Scraper runs on local Windows** – not suitable for cloud deployment (IP blocking).
- **AI inference latency** – summarisation may take 10–30 seconds.

---

## 17. Future Plans

- Upgrade to Gemini 3 (higher quota, lower latency).
- Add support for multiple categories in `videos.category` (already array, but UI not yet multi‑select).
- Implement automatic model retraining on a dedicated GPU schedule (Modal).
- Add real‑time notifications for trending video alerts.
- Integrate with additional social platforms (Instagram Reels, YouTube Shorts).

---

## 18. Non‑Negotiable Rules (from `RULES.md`)

- Never modify unrelated files.
- Never refactor without approval.
- All AI providers require fallback support.
- Never hardcode cookies or tokens.
- Run scraper locally, not on GitHub Actions.
- Avoid raw SQL outside `core/db/`.
- New features require tests; do not delete existing tests without approval.