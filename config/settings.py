import os
from dotenv import load_dotenv

# Lấy đường dẫn gốc của toàn bộ dự án (Thư mục TRENDSENSE)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Đánh thức file .env dậy
load_dotenv(os.path.join(BASE_DIR, '.env'), override=True)

# --- DATABASE CONFIG (SUPABASE) ---
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("FATAL: DATABASE_URL not found in .env! TremdSense requires a PostgreSQL database to run.")

# Định nghĩa các thư mục cốt lõi
DATA_DIR = os.path.join(BASE_DIR, 'data')
SRC_DIR = os.path.join(BASE_DIR, 'src')

# --- BẢO MẬT & API KEYS ---
HF_TOKEN = os.getenv("HUGGINGFACE_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
MODAL_WEBHOOK_URL = os.getenv("MODAL_WEBHOOK_URL", "")

# --- ĐƯỜNG DẪN CHO SCRAPER ---
EDGE_PROFILE_DIR = os.path.join(DATA_DIR, 'edge_profile')
DRIVER_PATH = os.path.join(SRC_DIR, 'scraper', 'msedgedriver.exe')


# --- ĐƯỜNG DẪN CHO MODEL AI ---
MODEL_DIR = os.path.join(DATA_DIR, 'models')
os.makedirs(MODEL_DIR, exist_ok=True)

MODEL_PATH = os.path.join(MODEL_DIR, 'rf_model.joblib')
METRICS_PATH = os.path.join(MODEL_DIR, 'metrics.json')

# --- ĐƯỜNG DẪN CHO VIDEO DOWNLOAD ---
VIDEOS_DIR = os.path.join(DATA_DIR, 'videos')
os.makedirs(VIDEOS_DIR, exist_ok=True)

# === BIẾN TOÀN CỤC ĐIỀU KHIỂN ===
MAX_VIDEOS = 3
SLIDING_WINDOW_DAYS = 14  # Chỉ train trên data 2 tuần gần nhất

# --- CẤU HÌNH TẢI VIDEO ---
DOWNLOAD_VIDEOS = True          # Bật/tắt tải video MP4
DOWNLOAD_VIRAL_ONLY = False      # Tải TẤT CẢ video, không chỉ video viral
VIRAL_DOWNLOAD_THRESHOLD = 50   # Ngưỡng % để kích hoạt tải
VIDEO_RETENTION_DAYS = 14        # Tự động xoá video cũ hơn N ngày
MAX_VIDEO_SIZE_MB = 15          # Xoá video nếu > 15MB sau khi tải
MAX_VIDEO_DURATION = 180        # Bỏ qua video dài hơn 3 phút
VIDEO_FORMAT = 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'  # Chuẩn 480p, có fallback nếu không có

# --- CẤU HÌNH PHÂN LOẠI DANH MỤC ---
ZERO_SHOT_MODEL = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"
CATEGORY_SEPARATOR = "|"       # Dấu phân cách giữa các danh mục
MAX_CATEGORIES = 3             # Tối đa 3 danh mục cho mỗi video
RULE_MIN_SCORE = 1             # Score tối thiểu để gán danh mục (rule-based)
ZERO_SHOT_THRESHOLD = 0.3     # Ngưỡng confidence cho zero-shot AI

# --- CẤU HÌNH MULTIMODAL AI (Phân tích Video toàn diện) ---
# 1. Vision (Hình ảnh tĩnh)
VISION_CAPTION_MODEL = "Salesforce/blip-image-captioning-base"   # Model sinh mô tả frame
VISION_CLIP_MODEL = "openai/clip-vit-base-patch32"               # Model xác minh danh mục
VISION_KEYFRAMES = 4           # Số frame trích xuất để nhìn bối cảnh
VISION_CATEGORY_OVERRIDE_THRESHOLD = 0.6  # Ngưỡng confidence để CLIP ghi đè danh mục

# 2. Audio (Nhận diện giọng nói)
WHISPER_MODEL = "base"         # "tiny", "base", "small", v.v.
WHISPER_COMPUTE_TYPE = "int8"  # int8 nhanh và nhẹ cho CPU

# 3. OCR (Nhận diện chữ trên màn hình)
OCR_LANG = ['vi', 'en']        # Ngôn ngữ EasyOCR
OCR_FRAMES = 2                 # Số frame để quét OCR (Tiết kiệm CPU)

# 4. LLM (Ollama Tổng Hợp — Dùng cho local dev)
OLLAMA_MODEL = "llama3:8b"     # Có thể đổi lại phi3 nếu máy yếu
OLLAMA_URL = "http://localhost:11434/api/generate"

# 5. Cloud AI (Modal + Groq — Dùng cho production)
# GROQ_API_KEY và MODAL_WEBHOOK_URL được set ở phần trên