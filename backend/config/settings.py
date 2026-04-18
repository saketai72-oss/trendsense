import os
from dotenv import load_dotenv

# Lấy đường dẫn gốc của toàn bộ dự án (Thư mục TRENDSENSE)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Đánh thức file .env dậy
load_dotenv(os.path.join(BASE_DIR, '.env'), override=True)

# --- DATABASE CONFIG (SUPABASE) ---
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("FATAL: DATABASE_URL not found in .env!")

# --- BẢO MẬT & API KEYS ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
MODAL_WEBHOOK_URL = os.getenv("MODAL_WEBHOOK_URL", "")

# --- STANDARD CATEGORIES ---
STANDARD_CATEGORIES = [
    "🎭 Giải trí", "🎵 Âm nhạc", "🍳 Ẩm thực", "💻 Công nghệ",
    "👗 Thời trang", "📚 Giáo dục", "🏋️ Thể thao", "🐾 Động vật",
    "💄 Làm đẹp", "📰 Tin tức", "💰 Tài chính",
]

# --- CORS ---
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
