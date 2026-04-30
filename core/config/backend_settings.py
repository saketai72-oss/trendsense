import os
from core.config.base import *

# Frontend URL for CORS
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Standard Video Categories
STANDARD_CATEGORIES = [
    "Giải trí", "Giáo dục", "Công nghệ", "Ẩm thực", "Thể thao",
    "Làm đẹp & Thời trang", "Đời sống", "Tài chính", "Tin tức", "Khác"
]

# ── Modal ──────────────────────────────────────────────
MODAL_WEBHOOK_URL = os.getenv("MODAL_WEBHOOK_URL", "")

# ── Groq ───────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# ── Upstash Redis (Queue + Rate Limit) ────────────────
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# ── Supabase Storage (Presigned URL upload) ───────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "")          # e.g. https://xxxx.supabase.co
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")  # service_role key — backend only!
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "videos")

# ── OpenRouter (Primary LLM) + Groq (Fallback) ────────
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_DEFAULT_MODEL = os.getenv("OPENROUTER_DEFAULT_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
