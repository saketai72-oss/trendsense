import os
import pandas as pd
import requests
from apify_client import ApifyClient
from dotenv import load_dotenv

# ==========================================
# PHẦN 1: CẤU HÌNH BIẾN TOÀN CỤC & BẢO MẬT
# ==========================================
MAX_VIDEOS_TO_SCRAPE = 2 # Đặt bao nhiêu, lấy CHÍNH XÁC bấy nhiêu!

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__)) 
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR)) 
DATA_DIR = os.path.join(PROJECT_ROOT, "data", "raw")
CSV_FILE_PATH = os.path.join(DATA_DIR, "tiktok_full_raw.csv")

os.makedirs(DATA_DIR, exist_ok=True)
load_dotenv(dotenv_path=os.path.join(PROJECT_ROOT, ".env"))

API_TOKEN = os.getenv("APIFY_API_TOKEN")

if not API_TOKEN:
    print("[!] LỖI: Không tìm thấy API Token.")
    exit()

client = ApifyClient(API_TOKEN)

# ==========================================
# PHẦN 2: CÀO DỮ LIỆU TỐI ƯU CHI PHÍ (1 BƯỚC DUY NHẤT)
# ==========================================
print(f"\n[*] Đang cào CHÍNH XÁC {MAX_VIDEOS_TO_SCRAPE} video để tiết kiệm Credit...")

run_input = {
    "hashtags": ["xuhuong", "viral"], 
    "maxItems": MAX_VIDEOS_TO_SCRAPE, # TỪ KHÓA QUYỀN LỰC ÉP BOT DỪNG LẠI
    "maxComments": 15, 
    "commentsPerPost": 15,
    "shouldDownloadVideos": False,
    "shouldDownloadCovers": False
}

# Chỉ gọi Apify ĐÚNG 1 LẦN duy nhất
run = client.actor("clockworks/tiktok-scraper").call(run_input=run_input)
raw_items = list(client.dataset(run["defaultDatasetId"]).iterate_items())

print(f"[*] Đã cào xong {len(raw_items)} video gốc. Đang móc nối Comment...")

# ==========================================
# PHẦN 3: TỰ ĐỘNG TẢI COMMENT MIỄN PHÍ TỪ LINK PHỤ
# ==========================================
for item in raw_items:
    dataset_url = item.get("commentsDatasetUrl")
    item["comments"] = [] # Mặc định là rỗng để tránh lỗi
    
    # Nếu Apify có để lại link kho comment phụ, mình tự dùng Python tải về cho đỡ tốn tiền
    if dataset_url:
        try:
            res = requests.get(dataset_url)
            if res.status_code == 200:
                item["comments"] = res.json()
        except Exception as e:
            pass

# ==========================================
# PHẦN 4: LƯU KHO DATA LAKE RAW
# ==========================================
df_new = pd.json_normalize(raw_items)

if 'webVideoUrl' in df_new.columns:
    df_new.rename(columns={'webVideoUrl': 'Link'}, inplace=True)

if os.path.exists(CSV_FILE_PATH):
    df_old = pd.read_csv(CSV_FILE_PATH, low_memory=False)
    df_final = pd.concat([df_old, df_new], ignore_index=True)
    if 'Link' in df_final.columns:
        df_final.drop_duplicates(subset=['Link'], keep='last', inplace=True) 
else:
    df_final = df_new

df_final.to_csv(CSV_FILE_PATH, index=False, encoding='utf-8-sig')

print(f"\n[*] THÀNH CÔNG RỰC RỠ! Đã lấy chuẩn {len(raw_items)} video kèm Comment.")