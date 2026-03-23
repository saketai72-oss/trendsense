import os
from dotenv import load_dotenv

# 1. ĐỊNH VỊ THƯ MỤC GỐC TỰ ĐỘNG
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__)) 
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)

# 2. TẢI BIẾN MÔI TRƯỜNG (.env)
load_dotenv(dotenv_path=os.path.join(PROJECT_ROOT, ".env"))

# 3. KẾT NỐI API KEYS
APIFY_TOKEN = os.getenv("APIFY_API_TOKEN")
HUGGINGFACE_TOKEN = os.getenv("HUGGINGFACE_TOKEN")

# 4. QUẢN LÝ ĐƯỜNG DẪN KHO DỮ LIỆU
RAW_DIR = os.path.join(PROJECT_ROOT, "data", "raw")
PROCESSED_DIR = os.path.join(PROJECT_ROOT, "data", "processed")

# Tự động tạo thư mục nếu chưa có
os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

RAW_FILE = os.path.join(RAW_DIR, "tiktok_full_raw.csv")
PROCESSED_FILE = os.path.join(PROCESSED_DIR, "tiktok_analyzed.csv")

# 5. CẤU HÌNH BOT CÀO DỮ LIỆU
MAX_VIDEOS_TO_SCRAPE = 100
TARGET_KEYWORDS = []