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

# ── Authentication (JWT) ──────────────────────────────
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-in-production-use-openssl-rand-hex-32")
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
JWT_REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# ── OAuth: Google ─────────────────────────────────────
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
# Backend URL for OAuth callbacks (must point to FastAPI directly, not through Next.js proxy)
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8080")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", f"{BACKEND_URL}/api/auth/google/callback")

# ── OAuth: GitHub ─────────────────────────────────────
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
GITHUB_REDIRECT_URI = os.getenv("GITHUB_REDIRECT_URI", f"{BACKEND_URL}/api/auth/github/callback")
