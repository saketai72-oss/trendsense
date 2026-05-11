# Project Context — TrendSense

> **Last updated:** 2026-05-10 (updated: local scraping) | Aligned with `docs/pipeline_overview.md` v3.0.0 (scraper moved to local)

## Overview

TrendSense is a hybrid‑cloud trend analysis and viral prediction platform for TikTok videos. It combines:

- Automated TikTok scraping (local scheduled task, undetected browser + proxy rotation) – moved from GitHub Actions to avoid IP blocking
- AI‑powered video analysis (Gemini 2.5 Flash primary, Modal GPU fallback)
- User video uploads with Trend Alignment Score (0–100, Python deterministic)
- Next.js dashboard with real‑time updates (Supabase Realtime)
- Weekly retraining of Random Forest viral probability model

---

## Core Architecture

```
TikTok / User Upload → FastAPI Backend → Redis Queue (RQ) → AI Workers
                                                           ├─ Gemini 2.5 Flash
                                                           └─ Modal GPU (Whisper+BLIP+OCR+LLM)
                                           ↓
                                    Supabase PostgreSQL (pgvector)
                                           ↓
                                    Next.js Frontend (Realtime)
```

**Key design choices:**
- **Primary AI path:** Gemini 2.5 Flash (via Redis RQ worker)
- **Fallback path:** Modal Serverless GPU (T4/L4) with OpenRouter → Groq
- **User uploads:** Presigned URLs → Supabase Storage → Modal GPU → Trend Alignment Score
- **Semantic search:** `gemini-embedding-001` → 3072‑dim vectors in pgvector
- **No ORM:** Raw SQL (`psycopg2`) in `core/db/models.py`

---

## Tech Stack

| Layer | Technologies |
|-------|--------------|
| Backend | FastAPI (Python 3.11), Redis (Upstash), RQ, SlowAPI |
| AI & ML | Gemini 2.5 Flash, Gemini Embedding, OpenRouter (10 free models), Groq, Whisper (int8), BLIP, EasyOCR, scikit‑learn (Random Forest) |
| GPU Serverless | Modal (T4/L4, persistent volume for HF models) |
| Database | Supabase PostgreSQL + pgvector |
| Storage | Supabase Storage (S3‑compatible) |
| Frontend | Next.js 16.2.4 (App Router), React 19, Tailwind CSS v4, Supabase Realtime |
| Scraping | Undetected Chromedriver, yt‑dlp, captchaapi.hacodev.io.vn |
| Scheduling | Local Windows Task Scheduler / `run_scraper_scheduled.bat` (scrape every 4h), weekly retrain & cleanup via local scripts (GitHub Actions deprecated) |

---

## Important Modules

| Directory | Responsibility |
|-----------|----------------|
| `backend/api/` | FastAPI routes, Gemini engine, LLM client, embedding service, storage service |
| `backend/worker.py` | RQ worker consuming `gemini_jobs` (900s timeout) |
| `core/db/` | Raw SQL connection, schema, CRUD, analytics (no ORM) |
| `services/ai_engine/` | Modal GPU app (`modal_app.py`, 1232 lines), local CPU pipeline, prediction engine, sentiment, categorizer, NLP utils |
| `services/tiktok_scraper/` | Browser automation, CAPTCHA solving, content parsing, video download, dedup |
| `frontend/` | Next.js dashboard: `/` (home), `/dashboard` (filters + table), `/analyze` (upload + realtime), `/video/[id]` (details) |
| `scripts/` + `.github/workflows/` (deprecated) | Local scraping orchestrated via `run_scraper_scheduled.bat` (Windows Task Scheduler). Weekly retrain and cleanup run locally. GitHub Actions workflows remain as reference but are no longer active to prevent IP blocking. |

---

## Critical Constraints (from `RULES.md`)

- **Never modify unrelated files** – keep changes isolated.
- **Preserve existing architecture** – service abstraction, module isolation.
- **All providers require fallback** – Gemini → Modal → OpenRouter → Groq.
- **Never hardcode cookies or tokens** – use `.env` and `token_fetcher.py`.
- **Handle retry & rate limits** – scraper has proxy rotation, Gemini has RQ backoff (60/180/600s).
- **Avoid raw SQL outside data layer** – all queries in `core/db/`.
- **New features require tests** – do not delete existing tests without approval.

---

## Data Flow (Simplified)

1. **Scraper pipeline** (every 4h via local scheduler):  
   `run_scraper_scheduled.bat` (triggered by Windows Task Scheduler) → scraper (undetected browser, rotating proxies) → parse stats → for Selenium-sourced videos, run Vietnamese language detection (combined char + langdetect); for TikTokApi-sourced videos (already from Vietnamese hashtags), skip language detection → insert `pending` → webhook to Gemini (or LLM fallback) → AI results → pgvector embedding.
   *(GitHub Actions are disabled to avoid IP blocking; all scraping runs on a local machine.)*

2. **User upload pipeline**:  
   Frontend → `GET /api/upload-url` → `PUT` to Supabase Storage → `POST /api/analyze` (rate‑limited) → Modal GPU → Trend Alignment Score + insights → Supabase Realtime updates frontend.

3. **Weekly retraining** (Sunday 00:00 ICT):  
   Scrape fresh data → train Random Forest (top 20% viral velocity as positive) → commit `rf_model.joblib` → backends load new model on next request.

---

## Environment Variables (Critical)

| Variable | Used By |
|----------|---------|
| `DATABASE_URL` | Backend, scraper, AI engine |
| `GEMINI_API_KEY` | Gemini video analysis & embeddings |
| `OPENROUTER_API_KEY` | LLM fallback chain |
| `GROQ_API_KEY` | Final LLM fallback |
| `MODAL_WEBHOOK_URL` | Modal GPU endpoint |
| `REDIS_URL` | Rate limiting + RQ queue |
| `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` | Storage + Realtime |
| `PROXY_LIST` | Scraper (JSON array or comma‑separated) |

See `.env.example` for full list.

---

## Frontend Features

- **Dark theme** with glassmorphism, neon glow, animated orbs.
- **Real‑time upload status** via Supabase Realtime (falls back to polling every 8s).
- **Dashboard filters**: search (semantic + ILIKE), category multi‑select, sentiment, min viral %, keyword cloud.
- **Video detail**: viral probability circle, metrics grid, performance bars, keyword cloud, TikTok link.
- **Trend Alignment Score** (user uploads): 5‑axis scoring (category, keywords, audio, duration, format) with LLM‑generated insights (Groq).

---

## Notes for Future Development

- **Scraping moved to local** – GitHub Actions workflows are disabled. Use `run_scraper_scheduled.bat` and Windows Task Scheduler to run the scraper every 4 hours. This reduces IP blocking risk.

- **No connection pooling** – each DB call creates a fresh `psycopg2` connection. Acceptable for current scale (<10 req/s).
- **pgvector index** currently disabled because Supabase limits HNSW/IVFFlat to 2000 dimensions. Sequential scan is sufficient for ~2000 rows.
- **Frontend rewrites** to backend via `next.config.mjs` – assume backend at `http://localhost:8080` in dev.
- **Weekly cleanup** resets `viral_probability` for videos older than 14 days to allow re‑prediction with fresh model.
- **Gemini daily quota** – worker sleeps 4s before each inference (15 req/min guard). Exhaustion triggers Modal fallback.