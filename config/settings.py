import os

# Lấy đường dẫn gốc của toàn bộ dự án (Thư mục TRENDSENSE)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Định nghĩa các thư mục cốt lõi
DATA_DIR = os.path.join(BASE_DIR, 'data')
SRC_DIR = os.path.join(BASE_DIR, 'src')

# --- ĐƯỜNG DẪN CHO SCRAPER ---
DB_DIR = os.path.join(DATA_DIR, 'db')
os.makedirs(DB_DIR, exist_ok=True)

DB_FILE = os.path.join(DB_DIR, 'scraped_history.db')
EDGE_PROFILE_DIR = os.path.join(DATA_DIR, 'edge_profile')
DRIVER_PATH = os.path.join(SRC_DIR, 'scraper', 'msedgedriver.exe')

# --- ĐƯỜNG DẪN CHO DATA/AI ---
RAW_FILE = os.path.join(DATA_DIR, 'raw', 'tiktok_full_raw.csv')
PROCESSED_FILE = os.path.join(DATA_DIR, 'processed', 'tiktok_analyzed.csv')